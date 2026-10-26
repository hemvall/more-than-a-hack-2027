"""Record and compare fixed reference-baseline runs; public scores check plumbing only."""

import hashlib
import importlib.metadata
import json
import platform
import random
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from games import GAME, GAMES, asset_paths, source_frames
from starter import baseline

ROOT = Path(__file__).resolve().parents[1]
NOTICE = "Public five-minute pipeline check only; not training, tuning or generalization evidence."
METRICS = ("spell_f1_mean", "macro_f1", "n_gt_spells", "n_pred_spells",
           "spell_count_error", "fragmentation")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def git_state() -> dict:
    def git(*args):
        return subprocess.check_output(["git", "-C", str(ROOT), *args])
    status = git("status", "--porcelain=v1", "--untracked-files=all")
    return {"revision": git("rev-parse", "HEAD").decode().strip(),
            "dirty": bool(status.strip())}


def runtime_versions() -> dict:
    versions = {}
    for name in ("numpy", "pandas", "python-dateutil", "six", "pytz", "tzdata"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return versions


def checked_command(argv: list[str], log: Path) -> None:
    # Subprocess output may contain asset details: retain it locally, never echo it.
    with log.open("w", encoding="utf-8") as handle:
        result = subprocess.run(argv, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT,
                                text=True, check=False)
    if result.returncode:
        raise RuntimeError("local command failed; inspect the run logs")


def run(mode: str, seed: int, output_root: Path, data_dir: str | None = None,
        allow_dirty: bool = False) -> Path:
    state = git_state()
    if state["dirty"] and not allow_dirty:
        raise ValueError("Commit changes first, or use --allow-dirty for an unreproducible development run")
    if mode not in ("supplied", "regenerate") or not 0 <= seed <= 2**32 - 1:
        raise ValueError("invalid mode or seed")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    folder = output_root / run_id
    folder.mkdir(parents=True, exist_ok=False)
    predictions, logs = folder / "predictions", folder / "logs"
    predictions.mkdir()
    logs.mkdir()
    started = time.perf_counter()
    config = {"mode": mode, "seed": seed, "game": GAME, "source": "tactical",
              "fps": GAMES[GAME]["fps"], "pitch_metres": list(GAMES[GAME]["pitch"]),
              "n_frames": source_frames(),
              "variants": [{"name": name, "half_window": window} for name, window in baseline.VARIANTS]}
    gt = ROOT / "evaluation" / "gt" / f"{GAME}_possession_gt_public.csv"
    manifest = {"schema_version": 1, "run_id": run_id, "status": "running", "stage": "setup",
                "created_utc": datetime.now(timezone.utc).isoformat(), "config": config,
                "git": state, "environment": {"python": platform.python_version(),
                "platform": platform.platform(), "packages": runtime_versions()},
                "evaluation": {"split": "public-pipeline-check", "purpose": NOTICE,
                               "bootstrap": 0},
                "inputs": {}, "outputs": {}, "scores": {}, "timings_seconds": {},
                "limitations": [NOTICE, "No model selection or automatic best-run promotion.",
                                "Slot identities and missing-ball handling are inherited from the baseline."]}
    if state["dirty"]:
        manifest["limitations"].append("Uncommitted source: revision alone cannot reproduce this run.")
    argv = ["python", "-m", "experiments", "run", "--mode", mode, "--seed", str(seed)]
    if mode == "regenerate":
        data_dir = str(Path(data_dir).resolve() if data_dir else
                       Path(asset_paths()["atd_raw"]).resolve().parents[1])
        argv += ["--data-dir", data_dir]
    if allow_dirty:
        argv.append("--allow-dirty")
    manifest["reproduction"] = {"cwd": str(ROOT), "argv": argv,
                                "checkout": state["revision"]}
    path = folder / "manifest.json"
    write_json(path, manifest)
    try:
        (folder / "requirements.lock.txt").write_text(
            "# Python " + platform.python_version() + "; runtime packages installed for this run\n"
            + "".join(f"{name}=={version}\n" for name, version in sorted(
                manifest["environment"]["packages"].items())), encoding="utf-8")
        manifest["evaluation"]["ground_truth_sha256"] = sha256(gt)
        manifest["evaluation"]["metadata_sha256"] = sha256(gt.with_name(gt.stem + "_meta.json"))
        manifest["evaluation"]["official_code_sha256"] = {
            name: sha256(ROOT / "evaluation" / name) for name in
            ("possession_metrics.py", "run_evaluation.py", "validate_submission.py")}
        manifest["stage"] = "prediction"
        write_json(path, manifest)
        step = time.perf_counter()
        random.seed(seed)
        baseline.np.random.seed(seed)
        if mode == "supplied":
            for name, _ in baseline.VARIANTS:
                source = ROOT / "evaluation" / "results" / f"{name}.csv"
                manifest["inputs"][name] = {"sha256": sha256(source), "kind": "supplied-baseline"}
                shutil.copyfile(source, predictions / source.name)
        else:
            assets = asset_paths(data_dir=data_dir)
            for key in ("atd_meta", "atd_raw"):
                source = Path(assets[key])
                manifest["inputs"][key] = {"path": str(source), "sha256": sha256(source)}
            codes = baseline.nearest_player_labels(assets["atd_raw"],
                baseline.team_of_each_track(assets["atd_meta"]), source_frames(), GAMES[GAME]["pitch"])
            for name, window in baseline.VARIANTS:
                baseline.write_submission(str(predictions / f"{name}.csv"), baseline.smooth(codes, window))
        manifest["timings_seconds"]["prediction"] = time.perf_counter() - step
        manifest["stage"] = "validation"
        write_json(path, manifest)
        step = time.perf_counter()
        for name, _ in baseline.VARIANTS:
            submission = predictions / f"{name}.csv"
            # Canonical newlines make new run outputs portable; supplied files stay untouched.
            submission.write_bytes(submission.read_bytes().replace(b"\r\n", b"\n"))
            checked_command([sys.executable, str(ROOT / "evaluation" / "validate_submission.py"),
                             str(submission)], logs / f"{name}-validation.log")
            manifest["outputs"][name] = {"sha256": sha256(submission),
                                         "path": str(submission.relative_to(folder))}
        manifest["timings_seconds"]["validation"] = time.perf_counter() - step
        manifest["stage"] = "evaluation"
        write_json(path, manifest)
        step = time.perf_counter()
        checked_command([sys.executable, str(ROOT / "evaluation" / "run_evaluation.py"),
                         "--gt", "public", "--results", str(predictions), "--out", str(folder / "evaluation"),
                         "--bootstrap", "0", "--no-detail"], logs / "evaluation.log")
        for name, _ in baseline.VARIANTS:
            result = json.loads((folder / "evaluation" / "reports" / f"{name}.json").read_text())
            scores = {metric: result[metric] for metric in METRICS}
            scores["transitions"] = {tau: {key: values[key] for key in
                ("n_matched", "n_missed", "n_spurious")} for tau, values in result["transitions"].items()}
            scores["possessions_by_iou"] = result["spell_f1"]
            manifest["scores"][name] = scores
        manifest["timings_seconds"]["evaluation"] = time.perf_counter() - step
        manifest["status"] = "complete"
        manifest["stage"] = "complete"
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error_type"] = type(error).__name__
        raise
    finally:
        manifest["timings_seconds"]["total"] = time.perf_counter() - started
        write_json(path, manifest)
    return path


def compare(first: Path, second: Path) -> dict:
    paths = [path / "manifest.json" if path.is_dir() else path for path in (first, second)]
    runs = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    for path, value in zip(paths, runs):
        if value.get("schema_version") != 1 or value.get("status") != "complete":
            raise ValueError("Only completed schema-1 runs can be compared")
        if value["git"]["dirty"]:
            raise ValueError("Dirty development runs cannot be used as comparison evidence")
        expected_names = {variant["name"] for variant in value["config"]["variants"]}
        if set(value["outputs"]) != expected_names or set(value["scores"]) != expected_names:
            raise ValueError("Run is missing expected predictions or scores")
        for artifact in value["outputs"].values():
            prediction = (path.parent / artifact["path"]).resolve()
            if not prediction.is_relative_to(path.parent.resolve()) or sha256(prediction) != artifact["sha256"]:
                raise ValueError("Saved prediction is outside the run or its hash has changed")
    a, b = runs
    if a["evaluation"] != b["evaluation"]:
        raise ValueError("Evaluation split, ground truth or official evaluator differs")
    for key in ("game", "source", "seed", "variants", "fps", "pitch_metres", "n_frames"):
        if a["config"][key] != b["config"][key]:
            raise ValueError(f"Incompatible configuration: {key}")
    input_hashes = [{key: item["sha256"] for key, item in value["inputs"].items()} for value in runs]
    if a["config"]["mode"] == b["config"]["mode"] and input_hashes[0] != input_hashes[1]:
        raise ValueError("Input provenance differs; compare runs over the same source data")
    if a["environment"] != b["environment"]:
        raise ValueError("Runtime environments differ; reproduce in the same environment first")
    deltas = {name: {metric: b["scores"][name][metric] - a["scores"][name][metric]
                     for metric in METRICS} for name in a["scores"]}
    return {"purpose": NOTICE, "first": a["run_id"], "second": b["run_id"],
            "deltas_second_minus_first": deltas,
            "identical_prediction_bytes": {name: a["outputs"][name]["sha256"] == b["outputs"][name]["sha256"]
                                           for name in a["outputs"]},
            "runtime_comparable": a["config"]["mode"] == b["config"]["mode"],
            "runtime_seconds": {"first": a["timings_seconds"], "second": b["timings_seconds"]}}
