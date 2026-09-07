# R6 independent red-team review

Date: 2026-09-05. Final verdict: **PASS with explicit evidence limits. The bounded evidence supports refining target-kernel and measurement access; it does not establish an architecture opportunity or a negative residual-loss result.** The completed source document, experiment report, measurement contract, progress table and history lineage have been independently reviewed. Machine-readable checks are in [redteam_audit.json](redteam_audit.json).

## Scientific claims and evidence boundary

| Claim | Independent assessment |
| --- | --- |
| A local NPU can execute something | Supported: XRT reports RyzenAI-Phoenix, and one verify plus one copy selftest completed; receipts and raw stdout/stderr hashes match |
| Verify establishes numerical correctness | Rejected: the matching XRT source submits and waits without checking output; it can overwrite a caught failure with `PASSED` |
| df-bw measures Gsample/s or actual AXI bandwidth | Rejected: its numerator is a 1 GiB allocation constant, divided by host launch-to-wait2 elapsed; bus accepted/completed bytes are not counted |
| There is a measured fixed-binary interference loss | Not measured: zero controlled interference pairs, zero static variants, zero dynamic variants |
| Static is sufficient on Phoenix, or dynamic cannot help it | Unanswered: no target strong-static workload or residual-loss experiment was executed |
| R5 prepared-token residency generalizes to full decode | Rejected as an extrapolation: recurrent state and token-generation lifetimes differ; capacity arithmetic does not predict device traffic |
| R6 passes a mechanism or PPA gate | No: actual traffic, compute activity, defined request/limit observations, target kernel contract and causal recovery are not available |

The main decision is **Refine measurement/kernel access**. R5's tested completion-ready candidate remains closed within its original family. H1 (real residual loss after strong static) remains unmeasured, and H3 (causal paid recovery) remains untested. This is a valid evidence-driven stop; it is not a failed search for a positive proposal.

## Vendor diagnostic audit

All three retained diagnostic receipts (`vendor_verify`, `vendor_df_bw`, `report_all`) have return code 0, no timeout, the same unchanged preregistration hash, and matching raw stdout/stderr digests. The local runtime reports XRT commit `42cba83aee86b253c49eccd484646e91d062468d`; the fetched `TestIPU.cpp` and `TestDF_bandwidth.cpp` use that exact revision. Source consistency is stronger than inferring semantics from the tool name, but these are still vendor selftests and not a compiler/runtime performance acceptance of the research workload.

Independent in-memory mutations confirm `checked_test` rejects each of `PASSED` plus an `Error` log, `FAILED`, and duplicated named tests, for both verify and df-bw. The original JSON and text output have no Error log. No diagnostic was rerun.

The copy test allocates 1 GiB input and 1 GiB output, initializes `268,435,456` int32 values using `rand()%4096`, launches the DPU instruction stream, waits with `wait2`, then syncs and compares every output value. Reported internal timing is **0.359610 host seconds**. Printed **2.780787 GS/s** equals `1 / elapsed` within print precision; interpreted from the source it is a nominal **GiB per host second for one payload direction**. It is neither Gsample/s nor the sum of measured read and write traffic. Allocation, initialization, input/instruction sync, output sync and comparison lie outside that timer. Whole-process host elapsed is a separate 5.6665504 seconds.

The summary properly keeps actual request bytes, device elapsed, outstanding/return limits, request latency, compute activity and input hash unknown. Binary hashes were collected after the run; there is no claim of a preregistered fixed address/input/frequency contract. The 800/400 MHz clock values are a later report, not a sampled run-frequency trace. The raw `123` power field is withheld from PPA inference. These limitations block resource attribution while preserving the functional result.

## Cross-token residency audit

Independent arithmetic from the frozen official configuration confirms 24 GDN layers, 32 value heads per layer, and 128×128 FP32 state per head. At batch 1 this is 65,536 bytes/head, 2,097,152 bytes/GDN layer, and **48 MiB** across the 24 layers. The count excludes convolution state, attention KV, weights, activations and scratch. It is conditional on the declared FP32 state contract.

The R5 control has only two heads, four prepared tokens, an assumed two-core RF budget, and no intervening layer occupancy. Ordinary autoregressive execution traverses the rest of the decoder and produces the next token before its corresponding next-layer input exists. The source check therefore invalidates direct extrapolation from that control; it does not imply 48 MiB must all sit in RF, that a target must spill every state to external memory, or that 48 MiB creates any particular latency. Legal other memory levels, sharding, precision, placement and compiler choices remain open. The JSON correctly leaves target RF capacity and mandatory external state traffic null.

## Measurement tooling review

The validator is explicitly a documentary/schema gate. `performance_gate_evaluated` remains false. A structurally complete synthetic fixture is barred from both hardware screening and mechanism eligibility. Independent in-memory negative cases reject missing request observations, overflow, NaN elapsed values, and a dynamic comparison switched to an unselected static contract. These checks validate the tool, not NPU behavior; no fixture is saved as measured data.

Two material weaknesses were identified during review and corrected: dynamic comparisons initially could use a different contract from the selected strong static, and fixed-binary residual controls could cover a disjoint set of interference conditions. Both fixes were independently retested using in-memory mutations, and both rejected the inconsistent records. Training/validation/test selection declarations, clock/traffic definitions and verified artifact references remain necessary but cannot automatically prove that real inputs are truthful or causal. Independent raw-trace and numerical audit is still required before any hardware decision.

A documented test invocation initially failed because module mode could not find the same-directory validator import. README now uses the supported direct script invocation, with no compatibility layer. The retained fixture receipt records 22 passing synthetic tests; its code/document/template hashes match. Independently invoking the empty template with `--require-mechanism` returns Python exit code **2**, `record_valid=true`, `mechanism_gate_eligible=false`, and `performance_gate_evaluated=false`, as documented. The template and synthetic tests contain no confirmation device data.

## Completed history and document review

The separate [history audit](history_audit.md) checked the R4 and R5 frozen manifests, saved statistics, residency scope, and the bounded older compiler directories. R4 root README must stay unchanged; the root progress successor must retain and reference the R5 byte-identical snapshot instead of overwriting its old hash. No R1–R5 performance experiment was repeated for this review.

Final checks verified 21 newly captured source files and 8 inherited source digests; 5 failed access attempts remain explicitly recorded. R4's 612 frozen paths still match. All 262 R5 manifest paths match when the one declared root-progress path maps to the byte-identical snapshot. The root successor digest and parent-manifest digests match `history_lineage.json`; all eight historical research rows plus their header are preserved, and both R6 rows are contiguous with the original Markdown table. Local document links resolve.

The final report explicitly states zero confirmation train/validation/test data and zero interference/static/dynamic comparisons. The source document distinguishes the unexecuted public RTL configurations from the executed Phoenix selftest. Capacity arithmetic is kept separate from mandatory traffic and hardware benefit. No blocking red-team findings remain. The root agent may now freeze the R6 artifact manifest; this audit did not freeze it or rewrite any R4/R5 artifact.
