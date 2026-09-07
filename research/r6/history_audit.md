# R6 independent R4/R5 history audit

Date: 2026-09-05. **PASS within the saved software-artifact boundary.** This audit independently read frozen source and result artifacts; it did not rerun R1–R5 performance experiments, edit historical files, or measure hardware. Machine-readable findings are in [history_audit.json](history_audit.json). The first audit was performed while the root progress table still matched its R5 hash.

## Integrity and version lineage

The R4 manifest [artifact_integrity.json](../experiments/results/r4/artifact_integrity.json) contains **612 paths**, including the root [README.md](../README.md). All 612 files were present and matched SHA-256. That README is frozen at `e3bb86187ac01e0446444a837a33dba5cb3e27f7a742a5d224db816cc8f33829`; R6 must preserve it.

The R5 [artifact_integrity.json](../r5/artifact_integrity.json) contains **262 paths**, including the cross-round [research_progress.md](../research_progress.md). All 262 matched at the audit start. The original progress digest is `3e9147e5c53781d9c82fc7da98306b18b689a82ef15fd392765681eaadda10c8`. `r5/check_integrity.py` hashes every non-cache R5 file except its own manifest and then adds the root progress table.

Before changing the root table, byte-copy it into an R6 history snapshot and verify the original digest. Preserve every R5 file and the original manifest. Record the original manifest digest, logical path `research_progress.md`, snapshot physical path and digest, and the successor root digest. An R6 history verifier can then check the original R5 manifest using exactly that documented path substitution. The original R5 verifier should report the live progress table as changed after a legitimate successor edit. Do not run `r5/check_integrity.py --freeze`, or the writing `r4/check_artifacts.py`, to make changed history appear unchanged.

## Independently recomputed main evidence

The auditor reconstructed execution totals from saved training, validation, and test arrays; checked frozen source/preregistration hashes; verified disjoint splits and the training shortlist/validation winner; recomputed all paired percentage means and frozen bootstrap intervals (4,096 resamples, NumPy seed 9417); and authenticated saved replay receipts. No simulator or event-loop implementation was needed for those calculations.

| Check | Result |
| --- | --- |
| Main configurations and executions | 42 configurations, including 36 request configurations; 7,094 executions |
| Held-out policy rows | 1,512 |
| In-memory request replay receipts | 1,296 PASS receipts; 12,886,560 request events represented |
| Previously saved detailed replay receipt | 126 traces; 1,073,880 request events |
| B0 request means | 2 positive / 18 negative / 16 zero; 0 pass 5% plus positive CI lower bound |
| B2 request means | 2 positive / 34 negative / 0 zero; 0 pass 5% plus positive CI lower bound |
| Best B0 | +0.164912319%; 95% CI [-0.025303824%, +0.345772449%] |
| Best paid B2 | +0.182134731%; 95% CI [-0.008211875%, +0.353421412%] |

Both best means occur at `request__qwen_projection__o1_combined`, an uncalibrated capacity-stress configuration. The R5 general ready-scheduling candidate remains rejected in its declared experimental family. This does not establish target hardware performance, PPA, or a universal scheduling impossibility result.

**One important qualification for R6:** the roughly +33.147740% Qwen and +33.218743% FLUX penalties compare independently trained and selected static plans for quiet and combined conditions. The saved `selected_plan` objects differ in both comparisons. These are model penalties after separately retuning static, not the fixed-binary/layout interference measurement required by the R6 measurement gate. Large interference loss is also not itself dynamically recoverable loss.

## Independently recomputed residency control

Fresh train 3200/3201, validation 3300/3301, and test 3400–3411 are mutually disjoint and disjoint from the main experiment. Saved search/test arrays account for exactly **928 executions**. Statistics were recomputed with the frozen bootstrap seed 9437. The existing independent replay receipt covers 24 retained traces and 73,728 requests; its source hash and artifact hash match. Detailed event replay was not repeated in this audit.

| Configuration | Static RF residency gain | 95% CI | Resident B0 vs S | Resident B2 vs S |
| --- | ---: | ---: | ---: | ---: |
| Reference quiet | 16.013380% | [16.013380%, 16.013380%] | 0 | -0.071487% |
| Reference combined | 24.027219% | [23.567670%, 24.450200%] | 0 | -0.095403% |
| Outstanding=1 combined | 7.155083% | [6.862467%, 7.479297%] | 0 | -0.015134% |
| Return slots=1 combined | 11.852688% | [11.607290%, 12.097524%] | 0 | -0.057820% |

Independently comparing the saved original/resident S graph for every configuration confirms identical arithmetic command data and preserved per-head state-update order: 917,504 operations, 131,072 external state bytes, and 73,760 RF bytes per core. Local state transfer falls from 1,048,576 to 262,144 bytes. The positive result is a legal static memory-planning control for the declared graph.

That graph has two complete 128×128 FP32 state heads and four tokens whose inputs are already prepared. State, prepared inputs, and outputs fit the assumed private RF, and no other layer uses RF during those tokens. A real autoregressive next-token input depends on intervening model execution; the full head/layer set may compete for the same resources, and ISA/RF access legality has not been measured. The 7%–24% gain therefore cannot establish cross-layer/cross-token RF residency or full-model decoder speedup.

## Bounded compiler and RTL workspace inventory

The root agent identified two additional directories; this auditor inspected them read-only. No `AGENTS.md` exists at their roots or the checked `D:/` and `D:/workspace/` parents; recursive searches excluding environments/Git also found none. This is a bounded directory inventory, not a whole-machine absence claim.

| Directory | Live state | Evidence classification |
| --- | --- | --- |
| `D:/workspace/llmSched` | Git main at `a07043dc1e2b2af42b5077182d1e20b03f34df0c`; user untracked files and `.runs/` preserved, before/after status identical | Offline architecture-evaluation compiler with planning, 512-bit packed descriptors, schedule and performance estimates |
| `D:/workspace/riscv_npu_alias` | Not Git; three files: paper PDF, extracted text, and a 2026-03-06 compiler/runtime specification draft | Documentation; no executable RTL, compiler test, or hardware trace in that directory |

The llmSched environment is actually usable: a `python -X utf8 -B` read-only import succeeds with ONNX 1.20.1, Pydantic 2.12.5, and Typer 0.24.1. No pipeline or test script was run. Its `.runs/` contains 456 existing files. A representative completed decode run has a 227,072-byte packed hex stream, `encoding_bits=512`, `container_format=aligned-flat-v1`. This is real compiler output but there is no authenticated device-load/execute receipt establishing that it is a production target binary, a Phoenix xclbin, or the R1 Descriptor 0x8 format.

`pipeline/performance_estimation.py` calls `estimate_descriptor_analysis`; `planning/schedule_duration.py` derives times from profile lane counts and bandwidth. The directory named `reports/diagnosis/trace` contains `estimated_cycles`, fitted work cycles, and static schedule slots. It is explanatory provenance for an estimator, not a hardware request trace. The checked dual-core target profile declares 128 KiB VMEM/core, 20 GB/s effective DMA bandwidth, and fixed sync costs; these are not Phoenix calibrations.

An inventory of 1,139 files, excluding `.git`, `.venv`, `.worktrees`, Python caches and pytest cache, found no `.v`, `.sv`, `.vhd`, `.vhdl`, `.xclbin`, `.elf`, `.bin`, `.vcd`, or `.fst`. The two registered worktrees are at commit `382bf05ca0092f95b67aa9381f1246a194b3bd2e`; they were enumerated but not deeply inspected. Source/evidence hashes and exact exclusions are recorded in the JSON.

**This is not the R1 TARS root.** R1 cites `src/llmSched/src/llm_sched/orchestrator/`, `hardware_specs/tars/`, `external/tars-npu-ctrl/`, and `inputs/descriptor_releases/active-release.json`; none exists at the checked llmSched root. R1's connected Controller/RTL and 4 MiB VMEM facts cannot be imported into this older 128 KiB-profile compiler. The current location of that R1 TARS checkout remains unestablished by this inspection. The highest independently established level here is a usable offline compiler environment and existing estimated artifacts, with no target calibration or executable RTL evidence from these two directories.

## Completed R6 review and history transition

The completed independent R6 review is in [redteam_report.md](redteam_report.md) and [redteam_audit.json](redteam_audit.json). It supports the bounded functional-device and source findings, with no target residual-loss or mechanism acceptance. Missing target evidence is **unmeasured**, not a new negative performance result. No target mechanism may pass because a host fixture, compiler parser, or uncalibrated model passes its own consistency checks.

The transition was independently verified against [history_lineage.json](history_lineage.json): the original progress is saved byte-for-byte at [history/r5_research_progress.md](history/r5_research_progress.md), with original SHA256 `3e9147e5c53781d9c82fc7da98306b18b689a82ef15fd392765681eaadda10c8`. Both original manifest digests match. All 612 R4 paths and all 262 R5 paths pass using exactly the declared snapshot substitution. The root successor hash matches its lineage record, all eight original research rows plus the header are retained verbatim, and the two R6 rows remain contiguous with the table. Every R4/R5 historical file remains unchanged; the root progress is explicitly a successor, not a silently refrozen R5 artifact.
