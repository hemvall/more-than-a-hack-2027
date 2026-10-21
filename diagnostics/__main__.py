"""Run with python -m diagnostics --data-dir PATH --output runs/data-audit.json."""

import argparse
import json
import math
import subprocess
import sys
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

from games import GAME, GAMES, asset_paths, half_video_blocks, source_frames
from starter.load_smart_tagging import load as load_tags

from .alignment import audit_homography, audit_tags
from .tracking import audit_tracking, read_slots


def audit_video(path: Path, expected: int, fps: float) -> dict:
    """Count decoded frames using ffprobe; never estimate from duration."""
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
               "-show_entries", "stream=nb_read_frames,avg_frame_rate",
               "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=600)
    streams = json.loads(result.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("video must contain a readable primary video stream")
    count = int(streams[0]["nb_read_frames"])
    rate = float(Fraction(streams[0]["avg_frame_rate"]))
    return {"status": "pass" if count == expected and abs(rate - fps) < 1e-6 else "fail",
            "decoded_frames": count, "expected_frames": expected, "fps": rate,
            "expected_fps": fps,
            "note": "Counts and average FPS do not establish visual synchronization."}


def run_audit(data_dir: str | None, source: str, check_video: bool,
              jump_speed: float) -> dict:
    paths = {key: Path(value) for key, value in asset_paths(data_dir=data_dir, source=source).items()}
    expected = source_frames(source)
    game = GAMES[GAME]
    blocks = half_video_blocks(GAME) if source == "tactical" else []
    checks = {}

    def run(name, operation):
        try:
            checks[name] = operation()
        except (OSError, ValueError, TypeError, KeyError, ET.ParseError,
                subprocess.SubprocessError, ZeroDivisionError, OverflowError) as error:
            # Avoid emitting raw asset rows or video output into logs.
            checks[name] = {"status": "error", "error_type": type(error).__name__,
                            "message": f"Could not audit {name}; check input files and format locally."}

    run("tracking", lambda: audit_tracking(paths["atd_raw"], read_slots(paths["atd_meta"]),
        expected, blocks, game["fps"], game["pitch"], jump_speed))
    run("homography", lambda: audit_homography(paths["homography"], expected))
    if source == "tactical":
        run("smart_tagging", lambda: audit_tags(load_tags(data_dir=data_dir), expected, blocks))
    else:
        checks["smart_tagging"] = {"status": "not_applicable"}
    if check_video:
        run("video", lambda: audit_video(paths["video"], expected, game["fps"]))
    else:
        checks["video"] = {"status": "not_checked", "message": "Use --check-video with ffprobe installed."}
    statuses = {check["status"] for check in checks.values()}
    status = "error" if "error" in statuses else "fail" if "fail" in statuses else "pass"
    return {"schema_version": 1, "source": source, "status": status, "checks": checks,
            "scope": "Structural checks of supplied assets; not proof of visual alignment.",
            "timeline_note": "Broadcast has its own timeline; tactical half boundaries are not applied."
            if source == "broadcast" else "ATD frame_id - 1; homography frame; round(tag seconds * 25)."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", help="Bundle root; otherwise use MTAH_DATA_DIR or data/")
    parser.add_argument("--source", choices=["tactical", "broadcast"], default="tactical")
    parser.add_argument("--output", type=Path, default=Path("runs/data-audit.json"))
    parser.add_argument("--check-video", action="store_true", help="Decode/count frames with ffprobe (can take minutes)")
    parser.add_argument("--jump-speed", type=float, default=15.0, help="Suspicious adjacent slot movement in m/s")
    args = parser.parse_args(argv)
    if not math.isfinite(args.jump_speed) or args.jump_speed <= 0:
        parser.error("--jump-speed must be finite and positive")
    report = run_audit(args.data_dir, args.source, args.check_video, args.jump_speed)
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except OSError as error:
        print(f"Cannot write report: {error}", file=sys.stderr)
        return 2
    for name, check in report["checks"].items():
        print(f"{name}: {check['status']}")
    print(f"Local report: {args.output}")
    return {"pass": 0, "fail": 1, "error": 2}[report["status"]]


if __name__ == "__main__":
    sys.exit(main())
