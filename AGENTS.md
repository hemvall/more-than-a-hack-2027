# Repository instructions

Read CONTRIBUTING.md before making changes.

- Every change needs an existing GitHub issue and its own branch from main.
- Branches: <type>/<issue>-<short-description>; experiment/<issue>-<idea> for experiments.
- Commit subjects and PR titles: type(#issue): description, for example feat(#12): add experiment runner. Optional breaking marker: feat(#12)!: description.
- Keep all commits in a PR linked to the branch's issue. Rebase instead of creating merge commits.
- Open a PR targeting main, with Closes #<issue>. Never push directly to main. Do not merge without user authorization.
- Run the relevant checks listed in CONTRIBUTING.md. Report failures and unrun checks honestly.
- Keep the official evaluator, public ground truth and supplied baselines unchanged. Put new implementation in separate modules. Upstream updates require their own issue and explicit review.
- Never commit restricted match assets, private annotations, generated predictions or secrets. Do not send competition data or extracts to hosted/cloud LLMs.
- Algorithm PRs need configuration, seed, split, scores, runtime, limitations and reproduction commands. Public-window gains alone are not evidence of generalization.
- For work on behalf of hemvall, configure author name hemvall and email 79575047+hemvall@users.noreply.github.com. Other contributors use their own identity.
