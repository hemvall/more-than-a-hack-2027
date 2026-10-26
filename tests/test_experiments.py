"""Regression checks use public supplied baselines, synthetic records and no gated assets."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.__main__ import main
from experiments.runner import ROOT, compare, run, sha256, write_json
from starter.baseline import VARIANTS


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def record(self):
        prediction = self.root / "synthetic.csv"
        prediction.write_text("frame,label\n0,H\n", encoding="utf-8")
        return {"schema_version": 1, "status": "complete", "run_id": "synthetic",
                "git": {"revision": "abc", "dirty": False},
                "config": {"mode": "supplied", "game": "synthetic", "source": "tactical",
                           "fps": 25, "pitch_metres": [105.3, 68], "n_frames": 1,
                           "seed": 0, "variants": [{"name": "reference", "half_window": 0}]},
                "evaluation": {"split": "public-pipeline-check", "ground_truth_sha256": "gt",
                               "official_code_sha256": {"scorer": "fixed"}},
                "inputs": {"reference": {"sha256": "input"}}, "environment": {"python": "fixture"},
                "outputs": {"reference": {"sha256": sha256(prediction), "path": prediction.name}},
                "scores": {"reference": {"spell_f1_mean": 0.5, "macro_f1": 0.6,
                    "n_gt_spells": 2, "n_pred_spells": 3, "spell_count_error": 1, "fragmentation": 1.5}},
                "timings_seconds": {"total": 1.0}}

    def test_comparison_deltas_and_cross_mode_runtime_warning(self):
        first, second = self.record(), self.record()
        second["config"]["mode"] = "regenerate"
        second["scores"]["reference"]["spell_f1_mean"] = 0.75
        for name, value in (("first.json", first), ("second.json", second)):
            write_json(self.root / name, value)
        result = compare(self.root / "first.json", self.root / "second.json")
        self.assertEqual(result["deltas_second_minus_first"]["reference"]["spell_f1_mean"], 0.25)
        self.assertFalse(result["runtime_comparable"])
        self.assertTrue(result["identical_prediction_bytes"]["reference"])

    def test_comparison_rejects_incompatible_or_unfinished_evidence(self):
        changes = [(("evaluation", "ground_truth_sha256"), "other"),
                   (("evaluation", "official_code_sha256"), {"scorer": "changed"}),
                   (("config", "seed"), 1), (("config", "variants"), []),
                   (("git", "dirty"), True), (("inputs", "reference"), {"sha256": "other"}),
                   (("environment", "python"), "different")]
        first = self.record()
        write_json(self.root / "first.json", first)
        for keys, value in changes:
            second = copy.deepcopy(first)
            second[keys[0]][keys[1]] = value
            write_json(self.root / "second.json", second)
            with self.subTest(keys=keys), self.assertRaises(ValueError):
                compare(self.root / "first.json", self.root / "second.json")
        for status in ("running", "failed"):
            second = self.record()
            second["status"] = status
            write_json(self.root / "second.json", second)
            with self.subTest(status=status), self.assertRaises(ValueError):
                compare(self.root / "first.json", self.root / "second.json")

    def test_dirty_tree_is_rejected_before_creating_a_run(self):
        with patch("experiments.runner.git_state", return_value={"dirty": True, "revision": "abc"}):
            with self.assertRaises(ValueError):
                run("supplied", 0, self.root / "runs")
        self.assertFalse((self.root / "runs").exists())

    def test_comparison_rejects_changed_prediction_bytes(self):
        write_json(self.root / "first.json", self.record())
        (self.root / "synthetic.csv").write_text("frame,label\n0,A\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            compare(self.root / "first.json", self.root / "first.json")

    def test_failed_validator_leaves_failed_manifest_and_no_scores(self):
        with patch("experiments.runner.git_state", return_value={"dirty": False, "revision": "abc"}), \
             patch("experiments.runner.checked_command", side_effect=RuntimeError("fixture failure")):
            with self.assertRaises(RuntimeError):
                run("supplied", 0, self.root)
        manifest = json.loads(next(self.root.glob("*/manifest.json")).read_text())
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["stage"], "validation")
        self.assertEqual(manifest["scores"], {})
        self.assertEqual(manifest["error_type"], "RuntimeError")
        self.assertGreater(manifest["timings_seconds"]["total"], 0)

    def test_cli_rejects_output_outside_ignored_folders_and_bad_parameters(self):
        for argv in (["run", "--runs-dir", str(self.root)], ["run", "--seed", "-1"],
                     ["run", "--data-dir", "unused"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit):
                main(argv)

    def test_supplied_baselines_end_to_end_leave_official_inputs_untouched(self):
        protected = [ROOT / "evaluation" / "results" / f"{name}.csv" for name, _ in VARIANTS]
        protected += list((ROOT / "evaluation" / "gt").glob("*public*"))
        before = {str(path): sha256(path) for path in protected}
        with patch("experiments.runner.git_state", return_value={"dirty": False, "revision": "fixture"}):
            manifest_path = run("supplied", 0, self.root)
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(len(manifest["scores"]), 4)
        self.assertAlmostEqual(manifest["scores"]["baseline_smooth125"]["spell_f1_mean"], 0.4242424242)
        self.assertAlmostEqual(manifest["scores"]["baseline_smooth50"]["macro_f1"], 0.6207331924)
        self.assertIn("n_missed", manifest["scores"]["baseline_raw"]["transitions"]["25"])
        self.assertEqual(before, {str(path): sha256(path) for path in protected})
        self.assertTrue((manifest_path.parent / "requirements.lock.txt").is_file())
        self.assertTrue((manifest_path.parent / "evaluation" / "reports" /
                         "baseline_smooth50_transitions.csv").is_file())
        result = compare(manifest_path, manifest_path)
        self.assertTrue(all(result["identical_prediction_bytes"].values()))
