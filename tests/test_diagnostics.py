"""Synthetic fixtures only: no competition data is needed or embedded here."""

import csv
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from diagnostics.__main__ import audit_video, main, run_audit
from diagnostics.alignment import MATRIX_COLUMNS, audit_homography, audit_tags
from diagnostics.tracking import audit_tracking, read_slots


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / "tracking.txt"
        self.homography = self.root / "homography.csv"
        self.slots = ["home", "away"]
        self.blocks = [(1, 0, 1), (2, 4, 5)]

    def write_raw(self, ids=range(1, 7), balls=None, players=None):
        balls = balls or ["0.5,0.5,1"] * 6
        players = players or ["0.2,0.3,1;0.7,0.8,1"] * 6
        self.raw.write_text("".join(f"{i}:{p}:{b}\n" for i, p, b in zip(ids, players, balls)))

    def tracking(self):
        return audit_tracking(self.raw, self.slots, 6, self.blocks, 25, (105.3, 68))

    def write_homography(self, frames=range(6), valid="1", matrix=None):
        matrix = matrix or [1, 0, 0, 0, 1, 0, 0, 0, 1]
        with self.homography.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["frame", *MATRIX_COLUMNS, "reprojection_error", "valid"])
            for frame in frames:
                writer.writerow([frame, *matrix, 0.1, valid])

    def test_ball_gaps_and_half_denominators(self):
        self.write_raw(balls=["NaN,NaN,NaN"] * 2 + ["0.5,0.5,1"] * 4)
        result = self.tracking()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["windows"]["1"]["ball"]["coverage_fraction"], 0)
        self.assertEqual(result["windows"]["2"]["ball"]["coverage_fraction"], 1)
        self.assertEqual(result["windows"]["all"]["ball"]["longest_gap_frames"], 2)

    def test_duplicate_and_missing_ids_cannot_cancel_each_other(self):
        self.write_raw(ids=[1, 2, 2, 4, 5, 6])
        result = self.tracking()
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["errors"]["duplicate_ids"], 1)
        self.assertEqual(result["errors"]["missing_ids"], 1)
        self.assertEqual(result["windows"], {})

    def test_reordered_rows_fail_even_with_correct_endpoints(self):
        self.write_raw(ids=[1, 3, 2, 4, 5, 6])
        self.assertEqual(self.tracking()["errors"]["out_of_order_ids"], 1)

    def test_zero_based_or_wrong_source_ids_fail(self):
        self.write_raw(ids=range(6))
        self.assertEqual(self.tracking()["errors"]["out_of_range_ids"], 1)
        self.assertEqual(self.tracking()["status"], "fail")

    def test_malformed_rows_slot_count_and_partial_coordinates(self):
        self.write_raw(players=["0.2,0.3,1"] * 6)
        self.assertEqual(self.tracking()["errors"]["wrong_slot_counts"], 6)
        self.write_raw(balls=["NaN,0.5,1"] * 6)
        self.assertEqual(self.tracking()["errors"]["partial_coordinates"], 6)
        self.raw.write_text("not an ATD row\n")
        self.assertEqual(self.tracking()["errors"]["malformed_rows"], 1)

    def test_reappearance_does_not_count_as_adjacent_jump(self):
        self.write_raw(players=["0.1,0.3,1;0.7,0.8,1", "NaN,NaN,NaN;0.7,0.8,1",
                                "0.9,0.3,1;0.7,0.8,1", "0.1,0.3,1;0.7,0.8,1",
                                "0.1,0.3,1;0.7,0.8,1", "0.1,0.3,1;0.7,0.8,1"])
        result = self.tracking()["slots"][0]
        self.assertEqual(result["reappearances"], 1)
        self.assertEqual(result["suspicious_jumps"], 1)

    def test_metadata_unknown_team_is_rejected(self):
        path = self.root / "meta.xml"
        path.write_text('<root><Team id="h"/><Team id="a"/><Player teamId="x"/></root>')
        with self.assertRaises(ValueError):
            read_slots(path)

    def test_homography_order_and_valid_flags(self):
        self.write_homography()
        self.assertEqual(audit_homography(self.homography, 6)["status"], "pass")
        self.write_homography(frames=[0, 2, 1, 3, 4, 5])
        self.assertEqual(audit_homography(self.homography, 6)["status"], "fail")
        self.write_homography(valid="2")
        self.assertEqual(audit_homography(self.homography, 6)["errors"]["invalid_flags"], 6)

    def test_missing_homography_is_valid_only_when_flagged(self):
        self.write_homography(valid="0", matrix=[float("nan")] * 9)
        self.assertEqual(audit_homography(self.homography, 6)["status"], "pass")
        self.write_homography(valid="1", matrix=[float("nan")] * 9)
        self.assertEqual(audit_homography(self.homography, 6)["status"], "fail")

    def test_singular_and_scaled_homographies(self):
        self.write_homography(matrix=[1] * 9)
        self.assertEqual(audit_homography(self.homography, 6)["status"], "fail")
        self.write_homography(matrix=[1e-8, 0, 0, 0, 1e-8, 0, 0, 0, 1e-8])
        self.assertEqual(audit_homography(self.homography, 6)["status"], "pass")

    def event(self, start=0, end=2, half="1st Half"):
        return {"start_frame": start, "end_frame": end, "code": "SET PIECES",
                "tags": {"Half": half, "Type": "Kick Off (Start)", "Team": "N/A"}}

    def test_tags_use_half_open_end_and_case_insensitive_labels(self):
        result = audit_tags([self.event(0, 1)], 6, self.blocks, {"1st Half": 1})
        self.assertFalse(result["kickoff_containment"]["1st Half"])
        result = audit_tags([self.event(0, 2, "1ST HALF")], 6, self.blocks, {"1st Half": 1})
        self.assertTrue(result["kickoff_containment"]["1st Half"])
        self.assertEqual(result["teams"]["n/a"], 1)

    def test_tag_wrong_half_and_out_of_bounds(self):
        for event in [self.event(0, 2, "2nd Half"), self.event(-1, 2), self.event(2, 2)]:
            with self.subTest(event=event):
                self.assertEqual(audit_tags([event], 6, self.blocks)["status"], "fail")

    def test_missing_data_is_an_error_not_a_pass(self):
        result = run_audit(str(self.root), "tactical", False, 15)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["checks"]["video"]["status"], "not_checked")

    def test_broadcast_does_not_reuse_tactical_halves_or_tags(self):
        with patch("diagnostics.__main__.read_slots", return_value=self.slots), \
             patch("diagnostics.__main__.audit_tracking", return_value={"status": "pass"}) as track, \
             patch("diagnostics.__main__.audit_homography", return_value={"status": "pass"}):
            result = run_audit(str(self.root), "broadcast", False, 15)
        self.assertEqual(track.call_args.args[2:4], (164488, []))
        self.assertEqual(result["checks"]["smart_tagging"]["status"], "not_applicable")

    def test_video_decoded_count_mismatch(self):
        output = json.dumps({"streams": [{"nb_read_frames": "5", "avg_frame_rate": "25/1"}]})
        with patch("diagnostics.__main__.subprocess.run", return_value=subprocess.CompletedProcess([], 0, output)):
            self.assertEqual(audit_video(self.root / "video.mp4", 6, 25)["status"], "fail")

    def test_cli_end_to_end_with_synthetic_bundle(self):
        folder = self.root / "tactical"
        folder.mkdir()
        self.write_raw()
        self.write_homography()
        (folder / "BAR-ATH_tactical_atd.txt").write_text(self.raw.read_text())
        (folder / "BAR-ATH_tactical_homography.csv").write_text(self.homography.read_text())
        (folder / "BAR-ATH_tactical_atd.xml").write_text(
            '<root><Team id="home"/><Team id="away"/>'
            '<Player teamId="home"/><Player teamId="away"/></root>')
        (folder / "BAR-ATH_tactical_smart_tagging.xml").write_text(
            '<root><instance><start>0</start><end>0.08</end><code>SET PIECES</code>'
            '<label><group>Half</group><text>1st Half</text></label>'
            '<label><group>Type</group><text>Kick Off (Start)</text></label></instance>'
            '<instance><start>0.16</start><end>0.24</end><code>SET PIECES</code>'
            '<label><group>Half</group><text>2nd Half</text></label>'
            '<label><group>Type</group><text>Kick Off (Start)</text></label></instance></root>')
        output = self.root / "audit.json"
        with patch("diagnostics.__main__.source_frames", return_value=6), \
             patch("diagnostics.__main__.half_video_blocks", return_value=self.blocks), \
             patch("diagnostics.alignment.KICKOFF_VIDEO_FRAMES", {"1st Half": 1, "2nd Half": 4}):
            code = main(["--data-dir", str(self.root), "--output", str(output)])
        report = json.loads(output.read_text())
        self.assertEqual(code, 0)
        self.assertEqual(report["checks"]["tracking"]["windows"]["2"]["ball"]["frames"], 2)
        self.assertTrue(all(report["checks"]["smart_tagging"]["kickoff_containment"].values()))
        self.assertEqual(report["checks"]["video"]["status"], "not_checked")

    def test_cli_writes_json_on_missing_data_and_rejects_bad_threshold(self):
        output = self.root / "reports" / "audit.json"
        code = main(["--data-dir", str(self.root), "--output", str(output)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.read_text())["schema_version"], 1)
        with self.assertRaises(SystemExit):
            main(["--jump-speed", "nan"])


if __name__ == "__main__":
    unittest.main()
