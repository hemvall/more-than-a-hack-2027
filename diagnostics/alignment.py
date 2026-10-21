"""Validate homography indexing and Smart Tagging on their own timelines."""

import csv
import math
from collections import Counter
from pathlib import Path

from starter.load_smart_tagging import KICKOFF_VIDEO_FRAMES

MATRIX_COLUMNS = [f"h{row}{col}" for row in range(3) for col in range(3)]


def determinant(m: list[float]) -> float:
    a, b, c, d, e, f, g, h, i = m
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def audit_homography(path: Path, expected: int) -> dict:
    errors = Counter()
    count = usable = 0
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"frame", "valid", "reprojection_error", *MATRIX_COLUMNS}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("homography is missing required columns")
        for index, row in enumerate(reader):
            count += 1
            try:
                frame = int(row["frame"])
                flag = int(row["valid"])
                matrix = [float(row[key]) for key in MATRIX_COLUMNS]
                error = float(row["reprojection_error"])
            except (ValueError, TypeError):
                errors["malformed_rows"] += 1
                continue
            if frame != index:
                errors["incorrect_frame_index"] += 1
            if flag not in (0, 1):
                errors["invalid_flags"] += 1
            elif flag:
                # Normalize first: homographies are defined up to scale.
                scale = max(abs(value) for value in matrix)
                finite = all(math.isfinite(value) for value in matrix)
                if not finite or scale == 0:
                    errors["unusable_valid_matrices"] += 1
                elif abs(determinant([value / scale for value in matrix])) <= 1e-15:
                    errors["unusable_valid_matrices"] += 1
                else:
                    usable += 1
                if not math.isfinite(error) or error < 0:
                    errors["invalid_reprojection_errors"] += 1
            elif not all(math.isnan(value) for value in matrix):
                errors["invalid_flag_with_non_nan_matrix"] += 1
    if count != expected:
        errors["row_count_mismatch"] += 1
    return {"status": "fail" if errors else "pass", "rows": count,
            "expected_frames": expected, "usable_matrices": usable,
            "errors": dict(errors)}


def audit_tags(events: list[dict], expected: int, blocks: list,
               anchors: dict | None = None) -> dict:
    """Use half-open intervals; kickoff containment is a coarse timing check."""
    anchors = KICKOFF_VIDEO_FRAMES if anchors is None else anchors
    errors = Counter()
    codes = Counter()
    teams = Counter()
    half_counts = Counter()
    kickoff_hits = {name: False for name in anchors}
    half_windows = {f"{half}{'st' if half == 1 else 'nd'} half": (start, end)
                    for half, start, end in blocks}
    unknown_halves = 0
    for event in events:
        start, end = event["start_frame"], event["end_frame"]
        code = (event["code"] or "").strip().lower()
        tags = {str(key).strip().lower(): str(value or "").strip().lower()
                for key, value in event["tags"].items()}
        half = tags.get("half", "")
        codes[code or "unknown"] += 1
        teams[tags.get("team") or "unknown"] += 1
        half_counts[half or "unknown"] += 1
        if not 0 <= start < end <= expected:
            errors["invalid_intervals"] += 1
            continue
        if half in half_windows:
            first, last = half_windows[half]
            if end <= first or start > last:
                errors["half_timeline_mismatch"] += 1
        else:
            unknown_halves += 1
        if code == "set pieces" and tags.get("type") == "kick off (start)":
            for name, anchor in anchors.items():
                if half == name.lower() and start <= anchor < end:
                    kickoff_hits[name] = True
    if not events:
        errors["empty_tagging"] += 1
    return {"status": "fail" if errors else "pass", "events": len(events),
            "errors": dict(errors), "codes": dict(codes), "teams": dict(teams),
            "halves": dict(half_counts), "unknown_half_tags": unknown_halves,
            "kickoff_containment": kickoff_hits,
            "warnings": [] if all(kickoff_hits.values()) else
            ["A kickoff tag is missing or does not contain its anchor; inspect locally."],
            "note": "Automatic tags are noisy. Containment does not prove frame-exact synchronization."}
