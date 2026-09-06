# R11 complete GDN static-residency experiment

Date: 2026-09-05. This is a reference-model experiment under an explicitly registered, uncalibrated hardware contract. It is not Phoenix, TARS, RTL, PPA, production, or whole-model acceptance.

## Research Question → Hypothesis

Can the R5 local-state traffic reduction survive a complete Qwen3.5 GDN layer, with all 32 value heads and legal input availability, while improving net elapsed time by at least 5%? The preregistered hypothesis was positive for a known four-token prefill/continuation block and explicitly uncertain for strict autoregressive decode.

## Strong Baseline and candidate

The frozen source is Qwen3.5-4B config/revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` and Transformers implementation revision `f62dc9bf2c90353b442a56e74391fbb8c689b55e`. The module includes qkv/z/a/b projections, causal depthwise convolution, q/k normalization and beta/g preparation, gated-delta recurrence, gated RMSNorm, and out projection. The experiment uses 32 value heads, 16 key heads, 128×128 FP32 recurrent state, four tokens, two cores, 128 KiB RF/core and 4 MiB VMEM. Dense weights are BF16-packed and expanded to FP32; intermediates and state are FP32 under the registered reference permission.

Both variants use identical cold-weight staged projections, tiling choices, barriers, port service, resources, initial/final locations, arithmetic work, outputs and final states. The strengthened baseline writes every head state after each token. The resident candidate keeps each head state through the four known prefill tokens and writes it once. Static choices were selected independently from the registered finite plans (value tile 32/64/128, depth 1/2; baseline head/token order, resident head order), with train then top-three validation. The held-out selections were `baseline-v64-p2-head` and `resident-v64-p2-head`.

## Discriminative experiment and numerical qualification

The capacity/traffic qualification passed for every registered plan. The selected graphs allocate 3,013,376 B VMEM and peak at 81,984 B RF/core. Both execute 168,427,520 dense MACs and the same recurrence work. External bytes are identical at 88,863,488 B. Local traffic is 109,135,104 B for the baseline and 96,552,192 B for the resident candidate; the complete-layer state read/write portion falls from 16,777,216 B to 4,194,304 B. This is a 12,582,912 B local-state reduction, not a free capacity increase.

The independent numerical runner checked all 76 preregistered prefill fixtures across six value-tile/order traversals and every token output, every-token state, final recurrent state and final convolution cache. It also checked four strict-AR callback representatives, where the next hidden vector is generated only after the previous module output and caches are complete. All checks passed; the largest FP64-source comparison absolute error was 2.6633e-7 under the registered 2e-5/2e-4 tolerance. The source's optimized prefill chunk kernel was not executed; the checked recurrence is source-semantic and the timed traces do not execute tensor arithmetic.

## Result

The quiet held-out pair was 3,448,328.125 cycles baseline versus 3,448,868.5 resident, a **−0.015670637%** resident gain. With the fixed 20% blackout background and independent paired phases, group A (30 blocks) was **−0.599174254%**, 95% paired t interval **[−0.610049107%, −0.588299401%]**; group B was **−0.605967308%**, interval **[−0.617565500%, −0.594369116%]**. The preregistered 5% gate therefore fails in quiet and in both independent background groups. The sign is consistently negative: local state traffic falls, but the state dependency and static order cost more elapsed time under this complete cold-weight staged ABI.

Strict autoregressive decode is a separate result. Under the registered ABI, only one hidden input is available per invocation; the next input is released after output/state visibility and the caller clobbers RF/VMEM. The independently rebuilt four-invocation graphs are identical for baseline and resident, so there is no lawful intervention to time and no decode gain claim. This closes the candidate for this explicit decode ABI; it does not prove that every cross-layer allocation or warm-weight contract cannot reuse state.

## Red-team and independent audit

The independent checker did not import the runner's graph or timing functions. It rebuilt command service from the contract, replayed all 122 saved traces, checked causal dependencies and every resource FIFO predecessor, integrated additive blackout phases, checked non-overlapping VMEM allocations, reconstructed source-derived state and MAC totals, verified lower bounds and paired seed alignment, and recomputed the statistics. It returned PASS. Historical R8–R10 checkers also returned PASS with all frozen manifests unchanged. The audit and raw traces are listed in [independent_audit.md](independent_audit.md), [independent_audit.json](independent_audit.json), [results.json](results.json), and [results/](results/).

## Continue/Close decision

**Prefill: 本轮未获支持，方向关闭。** The complete 32-head static-residency candidate under the registered cold-weight, staged reference ABI did not meet the 5% gate despite passing numerical, capacity, lifecycle and independent replay checks. **Strict decode: 本轮未获支持，方向关闭** for the same explicit output-visible/clobber ABI because the candidate and strengthened baseline are identical. This closes the complete-module candidate and its registered ABI investment; it does not claim mathematical impossibility for other hardware, warm-weight, fused, cross-layer, or storage contracts. No new hardware or scheduler proposal is justified by this result.

## Reproduction

From `D:/dsh-proj/SchedResarch`: `python -B -X utf8 r11/numerical.py`; `python -B -X utf8 -m r11.run_experiments`; `python -B -X utf8 r11/independent_audit.py`. The first command regenerates numerical payloads; the second regenerates qualification, train/validation selection and held-out traces; the third independently audits the saved traces. The report, manifest, lineage, successor progress and the updated retrospective preserve the evidence boundary and all R1–R10 history.
