# R11 historical verification

Status: PASS. All four required historical checkers ran read-only with `python -B -X utf8`; all returned exit code 0. These are historical integrity checks, not R11 numerical or performance evidence.

| Checker | Result | Verified scope |
| --- | --- | --- |
| `python -B -X utf8 r10/check_results.py` | PASS | {"named_artifacts": 1148, "R9_artifacts_preserved": 648, "new_progress_rows": 3, "A_pairs": 360, "B_pairs": 360, "total_detailed_traces": 1104} |
| `python -B -X utf8 r9/check_results.py` | PASS | {"named_files": 648, "handoff_files": 3, "historical_rows_preserved": 17, "actual_R9_rows": 2} |
| `python -B -X utf8 r8/check_history.py` | PASS | {"historical_paths": {"r7": 686, "r6": 89, "r5": 262, "r4": 612}, "handoff_files": 5, "historical_rows_preserved": 12, "current_root_is_handoff": false} |
| `python -B -X utf8 r8/check_results.py` | PASS | {"listed_artifacts": 34, "historical_rows_preserved": 13, "actual_R8_rows": 2, "root_is_this_successor": false} |

Frozen manifests and R11 handoff metadata have identical SHA-256 before and after these checker invocations. The complete command stdout, manifest digests, and four handoff digests are in [history_verification.json](history_verification.json).

The four immutable named handoff files are:

- `r11/continuation_brief.md` — `187225d6d10c71d524571fe4ed86589af5528e39482b86001807246697a0bc60`
- `r11/prepare_handoff.py` — `bb026e88eed01f6aa6d5dce83364ab2e0920b5f1dfd7f595872f3baeba08e370`
- `r11/history/r10_research_progress.md` — `df99c7045682658680a28105114b68c6fa521ca1311460322fd9b99d6394c7d4`
- `r11/history/aligned_research_progress.md` — `436d346261e9e5df1f6e0aed0ed08262e2274c15befff2586f23675bd46dd5a1`

The R10 parent progress snapshot is an exact byte prefix of the aligned R11 handoff progress snapshot. The aligned snapshot is an exact byte prefix of current root `research_progress.md`. Future actual-result rows must append while preserving all previous bytes and row order, with exactly eight result fields; preserve both existing snapshots and create a new R11 successor/final lineage.

Allowed changes: add new implementation/results under `r11`; append actual-result rows to root `research_progress.md`; update `analysis/r1_r10_research_retrospective.md` under the explicit reporting addendum while retaining R1–R10 history and the original filename. Do not alter frozen R1–R10 artifacts, old manifests, root README, or the four named handoff files. The initial `r11/history_lineage.json` and `r11/handoff_integrity.json` were also left unchanged during this verification.
