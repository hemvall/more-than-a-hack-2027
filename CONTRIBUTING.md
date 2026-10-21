# Contributing

## Issue → branch → commits → PR

Create or select one issue with a goal and acceptance criteria before editing.
Start a dedicated branch from current main, for example chore/12-contribution-workflow.
Allowed prefixes: feat, fix, docs, chore, ci, test, refactor, perf, build, experiment.

Commit subjects and PR titles use our issue-scoped Conventional Commits format:

```
feat(#12): add experiment runner
fix(#18): correct frame alignment
feat(#12)!: change experiment output format
```

Commit types: feat, fix, docs, chore, ci, test, refactor, perf, build, revert.
An experiment branch can use feat or another appropriate commit type.
All commits reference the same issue as the branch; their types can differ.
Rebase onto main instead of adding merge commits. Do not rewrite others' branches.

Open one PR per issue against main. Include a standalone Closes #12 line using your
actual issue number, a change summary and validation evidence. The policy check confirms
that this number refers to an existing issue in this repository, not a pull request.
Use the same issue-scoped format for the squash commit title.
Wait for checks and review before merging. Delete the branch after merge.
Failed experiments can be closed with findings without merging.

## Identity

When working on behalf of hemvall:

```bash
git config user.name hemvall
git config user.email 79575047+hemvall@users.noreply.github.com
```

Other contributors should use their own GitHub identity and noreply email.

## Local checks

Use Python 3.11 and Node 22 for the added tooling:

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
node --test .github/scripts/check-policy.test.cjs
python evaluation/run_evaluation.py --gt public --bootstrap 0 --no-detail
```

Also run the official validator on every generated submission before sending it:
`python evaluation/validate_submission.py path/to/submission.csv`.
CI validates the four supplied baseline files and scores them against the public window.
It needs no private data. It does not measure your model's full-match performance.

Ruff checks our new Python modules. The supplied games.py, starter/ and evaluation/
are excluded from lint to avoid changing upstream code for style.
Add focused tests when behavior changes; avoid tests that only mirror implementation.

## Experiments

Record the code revision, dependency versions, configuration, seed, evaluation split,
spellF1, macroF1, runtime, reproduction command and known regressions.
Compare under the same conditions, keep held-out clips separate and do not claim
generalization from the five-minute public window alone.
Private reports and predictions stay local under runs/, artifacts/ or evaluation/results/.
Publish only summaries permitted by the competition terms.

## Data and evaluator

Keep official evaluation code, public ground truth and supplied baselines unchanged.
New algorithms belong in separate modules. Review upstream updates separately.
Never commit restricted video, tracking, annotations, secrets or reconstructable derived data.
Never upload competition assets or extracts to hosted/cloud LLMs.
The ignore rules are a convenience, not a security boundary: review staged files before pushing.

## GitHub settings

After this PR is merged, a repository administrator should configure main protection:
require pull requests, require the Workflow policy and Repository checks status checks,
require branches to be up to date, block force pushes and deletion, and disallow bypass.
Prefer squash merging and use the PR title as the squash commit title.
Enable Actions on this fork if GitHub has disabled them.

These are server settings; adding this file or CI alone does not enforce a ban on direct pushes.
