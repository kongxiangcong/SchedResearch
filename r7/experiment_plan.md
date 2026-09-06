# R7 preregistration: executable Phoenix microkernel and measurement access

Date: 2026-09-05. Target is the local Phoenix as a measurement-capability candidate, not an assertion that it is the R1 architecture target. R1–R6 results and manifests remain immutable. No previous performance experiment will be rerun.

## Research Question → Hypothesis

1. Can the installed XRT 2.17.0 / driver 10.1109.8.110 execute a project-owned host harness with fixed binary, instruction stream, input and layout, explicit buffers and exact copy verification? H1: the existing runtime may expose sufficient public ABI without a driver upgrade or complete SDK installation.
2. Is a single compute kernel's complete ABI, shape/dtype/layout and numerical oracle available for this exact stack? H2: installed GEMM assets alone may be insufficient; a matched host implementation or documented prebuilt educational kernel may establish access.
3. Can actual traffic, compute-active and request/limit observations be authenticated? H3: installed host profiling may measure API elapsed only. This permits screening, but does not establish device resource attribution.

Evidence: exact R6 XRT sources, functioning vendor 1 GiB copy, installed DLLs/xclbins/instructions. Limits: no current strong-static compute kernel, controlled background, device cycles/traffic/compute/request counters, clock trace or R1 checkout. Sources and exported ABI will be checked before any call; no guessed instructions, malformed commands or inferred GEMM layouts will be submitted.

## Strong Baseline

For capability calibration only, preserve the vendor-supported copy instruction stream and exact 1 GiB input/output shape. Fixed deterministic input, poisoned output, pre-run input/binary/instruction hashes and BO address/size records strengthen reproducibility. This is **not** a strong-static research workload or a claim of optimal copy implementation. Do not shrink a buffer or patch a command stream without a supported shape contract.

Any compute baseline must first have complete source-backed shape/dtype, memory and argument contracts, deterministic known inputs and full output comparison. Prefer a prebuilt kernel matched to the installed stack. Absence of legal tiling/prefetch/compiler controls prevents calling it strong-static.

## Discriminative Experiment

E0: verify historical hashes; capture relevant installed exports and exact-revision headers/implementation. Test read-only device/open/xclbin metadata access in a subprocess before allocation/execution.

E1: only after verified ABI, create a bounded host harness. Separate allocation/init/hash, sync-to-device, launch→wait, sync-from-device, hash/compare and process elapsed. Save logs on each stage and raw return/status values. At most 10 calibration launches per kernel; start with one. Retain failures. A public zero-work command can calibrate empty device run only if its semantics are documented; a no-launch host timer is explicitly just host timer overhead.

E2: execute one complete, source-backed compute fixture if available, then a bounded calibration set only if numerical acceptance succeeds. Unsupported/incomplete ABI is a stop, not a reason to guess register/command contents. Exact integer fixtures preferred when using BF16 to avoid ambiguous tolerances. Payload bytes and operations are declared logical quantities, never actual hardware traffic/activity.

E3: inspect profiling implementations and local plugin availability. If a project-local documented configuration can produce a defined observable, pre-register an addendum specifying on/off order and at most 10 paired calibration blocks before running it. Save failure/overflow. Do not enable global profiling. If no supported instrument exists, instrumentation overhead is unknown, not zero.

## Stop and decision gates

Stop dependent device work on ABI inconsistency, unsupported API, missing kernel contract, timeout, runtime error or numerical mismatch. Investigate source and revise a new explicit addendum before another path. Do not upgrade drivers, mutate system runtime files, install a complete environment or substitute an uncalibrated simulator.

Accept only the actually demonstrated access level; Refine SDK/measurement interfaces for missing items. No residual-loss or dynamic-scheduler experiment until the kernel and minimum observation contract is established. Calibration samples are not train/validation/test confirmation data.

The later mechanism gate remains: independent train/validation/test; selected strong-static fixed binary residual; causal observations and finite legal actions; net elapsed improvement ≥5%, 95% paired CI lower bound >0, ≥30 independent paired blocks per condition/session, second session with fresh phases, ≥2 non-extreme interference conditions and quiet mean regression ≤1%. No gate evaluation in R7 access calibration.
