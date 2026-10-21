"""Stream ATD records and summarize quality without loading kloppy datasets."""

import math
import xml.etree.ElementTree as ET
from pathlib import Path


def read_slots(path: Path) -> list[str]:
    """Return team IDs in the metadata's slot order, not player identities."""
    root = ET.parse(path).getroot()
    teams = [team.get("id") for team in root.iter("Team")]
    slots = [player.get("teamId") for player in root.iter("Player")]
    if len(teams) != 2 or len(set(teams)) != 2 or None in teams:
        raise ValueError("ATD metadata must define two distinct team IDs")
    if not slots or any(team not in teams for team in slots):
        raise ValueError("ATD metadata has no slots or a slot references an unknown team")
    return slots


def observation(group: str) -> tuple[float, float, float]:
    """Read the documented x,y,speed tuple. NaN is allowed; infinity is not."""
    values = tuple(float(value) for value in group.split(","))
    if len(values) != 3 or any(math.isinf(value) for value in values):
        raise ValueError("expected x,y,speed with finite numbers or NaN")
    return values


def present(point: tuple[float, float, float]) -> bool:
    return math.isfinite(point[0]) and math.isfinite(point[1])


def coverage(mask: list[bool]) -> dict:
    longest = current = gaps = 0
    for value in mask:
        if value:
            current = 0
        else:
            gaps += current == 0
            current += 1
            longest = max(longest, current)
    return {
        "frames": len(mask), "present_frames": sum(mask),
        "missing_frames": len(mask) - sum(mask), "gap_count": gaps,
        "longest_gap_frames": longest,
        "coverage_fraction": sum(mask) / len(mask) if mask else None,
    }


def audit_tracking(path: Path, slots: list[str], expected: int, blocks: list,
                   fps: float, pitch: tuple, jump_speed: float = 15.0) -> dict:
    """Check every ID in file order; quality summaries require exact alignment.

    Jump speed is a diagnostic threshold in m/s, not proof of an identity swap.
    Missing observations reset adjacency so gaps cannot create artificial jumps.
    """
    seen = bytearray(expected)
    ball_mask = [False] * expected
    player_counts = [0] * expected
    errors = {name: 0 for name in (
        "malformed_rows", "out_of_range_ids", "duplicate_ids", "out_of_order_ids",
        "wrong_slot_counts", "partial_coordinates")}
    per_slot = [{"slot": i + 1, "team_id": team, "observed_frames": 0,
                 "reappearances": 0, "suspicious_jumps": 0} for i, team in enumerate(slots)]
    previous = [None] * len(slots)
    ever_seen = [False] * len(slots)
    outside = 0
    rows = 0
    last_id = None
    for rows, line in enumerate(path.open(encoding="utf-8"), start=1):
        try:
            frame_text, players_text, ball_text = line.strip().split(":")
            frame_id = int(frame_text)
            players = [observation(group) for group in players_text.split(";")]
            ball = observation(ball_text)
        except (ValueError, TypeError):
            errors["malformed_rows"] += 1
            previous = [None] * len(slots)
            continue
        if last_id is not None and frame_id <= last_id:
            errors["out_of_order_ids"] += 1
        last_id = frame_id
        if not 1 <= frame_id <= expected:
            errors["out_of_range_ids"] += 1
            continue
        frame = frame_id - 1
        if seen[frame]:
            errors["duplicate_ids"] += 1
            continue
        seen[frame] = 1
        if len(players) != len(slots):
            errors["wrong_slot_counts"] += 1
            continue
        for point in [ball, *players]:
            errors["partial_coordinates"] += math.isnan(point[0]) != math.isnan(point[1])
            if present(point) and not (0 <= point[0] <= 1 and 0 <= point[1] <= 1):
                outside += 1
        ball_mask[frame] = present(ball)
        player_counts[frame] = sum(present(point) for point in players)
        for i, point in enumerate(players):
            if not present(point):
                previous[i] = None
                continue
            stats = per_slot[i]
            stats["observed_frames"] += 1
            prev = previous[i]
            if ever_seen[i] and (prev is None or prev[0] != frame - 1):
                stats["reappearances"] += 1
            if prev is not None and prev[0] == frame - 1:
                speed = math.hypot((point[0] - prev[1]) * pitch[0],
                                   (point[1] - prev[2]) * pitch[1]) * fps
                stats["suspicious_jumps"] += speed > jump_speed
            previous[i] = (frame, point[0], point[1])
            ever_seen[i] = True
    errors["missing_ids"] = expected - sum(seen)
    aligned = rows == expected and not any(errors.values())
    summaries = {}
    if aligned:
        for name, start, end in [("all", 0, expected - 1), *blocks]:
            counts = player_counts[start:end + 1]
            summaries[str(name)] = {
                "first_frame": start, "last_frame": end,
                "ball": coverage(ball_mask[start:end + 1]),
                "mean_tracked_players": sum(counts) / len(counts),
                "frames_without_players": counts.count(0),
                "frames_over_22_players": sum(count > 22 for count in counts),
            }
    return {"status": "pass" if aligned else "fail", "records": rows,
            "expected_frames": expected, "errors": errors,
            "out_of_bounds_observations": outside, "windows": summaries,
            "slots": per_slot if aligned else [], "jump_threshold_m_s": jump_speed,
            "note": "Slot jumps and reappearances are indicators, not confirmed identity switches."}
