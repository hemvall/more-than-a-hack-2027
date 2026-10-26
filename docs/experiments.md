# Reproducible reference runs

Issue #6 establishes a stable reference before changing possession detection.
The next steps and issue dependencies are in [ROADMAP.md](../ROADMAP.md).
This runner implements no new possession algorithm and does not tune parameters.

Use Python 3.11 and install `requirements-dev.txt`. Run from the repository root
with a clean Git checkout:

```bash
python -m experiments run
```

The default copies all four supplied baseline CSVs to a fresh local directory,
runs the official validator on each, and invokes the unchanged official evaluator
against the public ground truth with bootstrap disabled. No match assets are needed.
The four fixed windows come from `starter.baseline.VARIANTS`; none is selected as
the "best" using public scores.

To regenerate the same reference algorithm from the local tactical tracking:

```bash
python -m experiments run --mode regenerate --data-dir data --seed 0
```

The runner calls the supplied baseline's existing functions and writes new outputs
under `runs/experiments/`. It never calls the baseline CLI with its default output
directory, so the supplied reference CSVs are not overwritten. New run CSVs use LF
newlines for byte-stable output across platforms. The default data location also
honors `MTAH_DATA_DIR`. No video or broadcast data is needed.

Each run has a unique UTC/UUID directory containing:

- `manifest.json`: status, execution stage, full configuration, seed, code revision,
  clean/dirty Git state, runtime versions, input/output SHA-256 hashes, split and
  evaluator/metadata fingerprints, scores, timings, limitations and reproduction arguments.
- `requirements.lock.txt`: exact installed versions of NumPy, pandas and the listed
  installed transitive runtime packages; Python/platform are recorded separately.
- `predictions/`: the four new local CSVs, validated before scoring.
- `evaluation/`: the official scoreboard, full JSON reports and transition CSVs,
  including missed/spurious transitions and fragmentation for inspection in a viewer.
- `logs/`: local validator and scorer output. The runner prints no match details.

On failure the manifest records the stage, error type and elapsed time. A failed or
unfinished run cannot become comparison evidence. Previous runs are never overwritten.
Use `--runs-dir runs/another-folder` if needed; the CLI only permits outputs under
the repository's ignored `runs/` or `artifacts/` trees.

## Reproduction and comparison

Check out the recorded revision, recreate its Python environment, install the saved
runtime pins, provide the same inputs and execute the manifest's `reproduction.argv`
from its recorded repository root. Verify input hashes when moving a run to another
machine. Generated CSV bytes should match; timestamps, run IDs and runtime will differ.
The seed is recorded and set, though the supplied baseline is deterministic and
the public pipeline check uses no bootstrap sampling.

```bash
python -m experiments compare runs/experiments/FIRST runs/experiments/SECOND
```

Comparison checks successful completion, clean revisions, identical environment,
evaluation split, ground truth, official evaluator, game, source, seed and variants.
It also verifies that saved prediction files still match their recorded hashes.
Same-mode runs must have identical input hashes. Cross-mode comparison supports
checking supplied versus regenerated predictions, but their runtimes are not directly
comparable. It prints second-minus-first metrics and whether prediction hashes match.
No automatic ranking or stable-run promotion is performed. Keep the supplied baselines
and a recorded clean revision as the stable reference when future components are added.
For an ablation, change one component on its issue branch and use the same permitted
validation protocol; this initial runner only supports the fixed reference algorithm.

`--allow-dirty` permits development checks but marks the run as unreproducible from
its commit alone and disallows using it as comparison evidence.

## Limits

The public five minutes check frame alignment, file validity and metric plumbing.
They must not train a model, tune thresholds or select methods. Public score deltas
do not establish generalization. This first runner deliberately accepts only this
public pipeline-check split; external validation requires a separate documented
dataset protocol under #3, with a frozen test set under #9. Never use the private
ground truth or manually annotate/correct the provided match.

All manifests, locks, logs, predictions and detailed reports stay local. They may
contain private paths, hashes or reconstructable data. Do not commit or upload them.
The runtime lock is a record for the reported platform, not a cross-platform package
distribution or a substitute for checking platform compatibility.
