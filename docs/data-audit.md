# Data alignment and quality audit

Run from the repository root with Python 3.11. The audit uses the standard library
and the supplied Smart Tagging loader; it does not require kloppy or private labels.

```bash
python -m diagnostics --data-dir /path/to/bundle
```

The bundle should contain the tactical/ and optional broadcast/ folders described
in DATA.md. Without --data-dir, MTAH_DATA_DIR or the repository's data/ folder is used.
The command prints check statuses and writes a local JSON report to runs/data-audit.json.

To also verify the actual video's decoded frame count and average frame rate,
install FFmpeg (including ffprobe) and run:

```bash
python -m diagnostics --check-video
```

This decodes the video and can take several minutes. It times out after twenty minutes;
use `--video-timeout SECONDS` for a slower machine. Decoder errors fail the check even
when the decoded frame count matches.
The canonical video filename is preferred. If it is missing, the audit accepts exactly
one numbered download variant such as `BAR-ATH_tactical-002.mp4`. Multiple variants
are an error: choose the intended recording explicitly, without renaming your data:

```bash
python -m diagnostics --video data/tactical/BAR-ATH_tactical-002.mp4
```

`--video` implies `--check-video`; its path is relative to the current directory.
Without this flag, video is explicitly marked not_checked. Structural checks can pass
without video verification: that is not a claim that the full dataset is synchronized.

## What is checked

- ATD: every ID must appear exactly once in order, from 1 through the source's frame
  count. Count and endpoint agreement alone cannot hide duplicates, gaps or reordering.
- Metadata: two distinct teams and a known team for each slot. Slots are not people.
- Observations: x,y,speed tuples, expected slot count, finite or NaN values, and paired
  missing coordinates. Missing ball observations are expected, not a structural failure.
- Quality: ball coverage, gap count, longest gap, mean tracked-player count, empty-player
  frames and frames with more than 22 tracks, separately for all frames and each tactical half.
- Slot continuity: observed frames, reappearances after gaps and suspicious adjacent-frame
  jumps. Default threshold is 15 m/s; change it with --jump-speed. This is a heuristic,
  not evidence that a particular player's identity changed. Out-of-pitch observations are
  counted for inspection rather than rejected, since players and the ball can leave the pitch.
- Homography: exact zero-based indexing, required columns, valid flags, finite usable
  matrices and nonnegative reprojection errors. Invalid matrices must contain NaNs.
- Smart Tagging: half-open frame intervals, video bounds, code/team/half
  counts, and containment of both published kickoff anchors. Missing kickoff containment
  produces an explicit warning status because tags are automatic and approximate.
  Tags outside their named graded half and unknown half tags also produce warnings,
  with counts retained in the report. Graded windows define scoring coverage, not
  permitted annotation boundaries; automatic phases can reach ungraded footage.
  Warnings require local inspection and do not establish a clock offset. Containment cannot establish
  frame-exact alignment. Unknown/N/A team tags are reported without inventing a team.

The ATD conversion is frame_id - 1, not the private tracking offsets in games.py.
Smart Tagging uses round(seconds * 25); homography already uses video-frame indices.
The second graded half begins before its kickoff. Reports use the graded half boundaries
from games.half_video_blocks, not kickoff-to-whistle estimates.

## Broadcast

```bash
python -m diagnostics --source broadcast --output runs/broadcast-audit.json
```

Broadcast uses its own expected length and has no Smart Tagging. Tactical half boundaries
are deliberately not applied. This command does not align broadcast to tactical video.

## Reading results

Exit 0: no structural failures (status pass or warning; review warnings and not_checked entries).
Exit 1: structural or requested video checks failed.
Exit 2: a required input/dependency could not be read, parsing failed, or report writing failed.
Argparse also returns 2 for invalid arguments.

Malformed ATD rows produce counts; ambiguous alignment suppresses coverage and slot
summaries so missing file rows are not misreported as natural ball occlusions.
The JSON includes a schema_version and check-specific counters. It contains aggregate
quality information, not per-frame tracking exports. Keep generated reports local and
review the competition terms before sharing any derived information.

Failures in supplied assets are findings, not instructions to change those assets or
the official constants. A negative reprojection error remains a failure: do not use
that error value as a confidence weight. A decoded video length that differs from
tracking/homography remains a failure, even by one frame. Do not trim, pad or shift a
recording to hide it. Keep broadcast optional until its timeline is resolved; it never
changes the tactical submission length. Report discrepancies to the data provider
through the competition's permitted channels if needed.

Passing these checks does not verify physical correctness. Review synchronized overlays
at both kickoffs and representative passages locally before relying on the data.
The implementation's tests use synthetic fixtures. Local real-data reports stay under
ignored `runs/`; they are not test fixtures and are not committed.
Video inspection is for debugging only. Do not manually label or correct this match,
or tune parameters on its public five-minute ground truth; see RULES.md.

## Tests

```bash
python -m unittest discover -s tests -v
```

Tests cover duplicate/missing/reordered frames, malformed observations, per-half coverage,
slot gaps versus jumps, invalid homographies, half-open tagging, separate source timelines,
missing inputs, CLI output and video frame-count mismatch. CI requires no gated assets.
