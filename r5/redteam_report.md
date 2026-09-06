# R5 independent scientific red-team

Date: 2026-09-05. Initial review was written before R5 executions. This document is maintained by the independent red-team agent. It distinguishes software/model consistency from real-device evidence. Neither a passing trace audit nor a request-level simulator establishes silicon fidelity or architecture novelty.

## R4 facts and limits reviewed independently

Reviewed `r4/engine.py`, `lowering.py`, `graph.py`, `static_search.py`, Qwen/FLUX lowering, model registry, main and red-team reports, `analysis/runtime_uncertainty.md`, and `r4/prior_art_delta.md`.

1. R4 tasks reserve unary engine/SRAM/DMA bundles for their full service interval. The memory task factor is keyed by task identity. The calendar is absolute-time service availability. There are no request queues, DMA outstanding transactions, bank arbitration, data-return credits, or finite completion FIFO backpressure. This is a known abstraction boundary, not proof that those effects are important.
2. R4 checks numerical algebra and reorderings using random FP64 data. Declared BF16/FP32 storage bytes are not a measured precision implementation. Its full model source dimensions are known, but executed graphs use reduced dimensions. Expanding only byte counts without correct MAC counts, reductions, layouts, traffic, and lifetimes would not cure this limitation.
3. The static baseline is a train-only bounded local order search followed by validation selection. It is stronger than the inherited pool, but not a production compiler, exhaustive full-graph optimum, or reproduction of PipeThreader/Stream/LATTICE. Scope must remain conditional on the declared mapping, tiling, memory plan, and order search.
4. R4's fixed mapping/address and explicit last-reader dependencies are valuable invariants. A new model must preserve these invariants across policies and recompute endogenous queues when policy changes.
5. The R4 result rejects stable net benefit for the tested general ready-dispatch policies in the tested models. It does not reject all priority rules, all dynamic memory arbitration, all shared-machine interference, or all end-side NPUs. Its posthoc priority probe is diagnostic, not fresh confirmatory evidence.

## Threats that could reverse an R5 conclusion

| Threat | Bias introduced | Required control |
| --- | --- | --- |
| Freeze the elapsed memory duration from another policy | Counts the old policy's queueing as immutable service | Freeze raw bytes, request identity, service requirement, and absolute external arrivals; regenerate internal queueing for each policy |
| Whole tensor read/write or bytes-only scaling | Manufactures bandwidth/working-set bottlenecks that valid tiles can avoid | Derive every tiled MAC/byte count from source dimensions; document operand reuse, partial reductions, and live spans |
| Dynamic gets deeper prefetch or extra outstanding entries | Confounds information value with capacity | Equal slots, buffers, outstanding limit and credits; static may prefetch all legally permitted descriptors |
| Isolated one-bank saturation | Can remove every legal ordering choice | Include controlled independent-bank and shared-bandwidth cases; restrict any negative conclusion to covered configurations |
| Optimizer sees test interference phases | Produces clairvoyant baseline while calling it deployable static | Disjoint train/validation/test and immutable selected plans before test evaluation; oracle explicitly separate |
| Dynamic inherits weak/misaligned priority | Turns an avoidable deterministic schedule mismatch into a mechanism verdict | Include static-order-derived priority with the same legal admission contract; do not claim this exhausts all policies |
| Static can choose order but never intentionally pace prefetch | Attributes avoidable queue/HOL pressure to unknown completion information | Include feasible static queue-depth/release-spacing controls or clearly bound the baseline to work-conserving fixed orders |
| Completion FIFO measured but never throttles producer | Reports bounded state without preserving semantics | Full FIFO must delay the relevant delivery/completion/release boundary; verify no event loss and eventual progress |
| Arbiter ties depend on event insertion or task names | Synthetic repeatable positive/negative direction | Stable declared arbitration and simultaneous-event batching; permutation/invariance checks when identities have no semantic priority |
| Give independent random compute duration to dense fixed work | Injects opportunity unsupported by hardware evidence | Compute deterministic unless a separate, sourced work-variation hypothesis is being tested |
| Sensitivity-selected positive after many configurations | Replaces falsification with search for a proposal | Preserve all configurations, predeclare gate; any posthoc promising region needs fresh holdout evidence |

## Minimal discriminative model and controls

The minimum useful added fidelity is a source-dimension-correct tiled subgraph with fixed mapping and explicit memory lifetimes, paired with transaction-level shared memory service. It need not become a complete NoC/DRAM/cycle-accurate NPU platform. Transactions should expose request arrival, service begin/end, return readiness, credit acquire/release, and consumer visibility. Their byte count and arbitration domain must be explicit.

The core distinctions are (1) deterministic internally induced contention, (2) fixed external interference with unknown phase, and (3) policy-induced arrival changes. At least a zero-interference control and factor-isolation cases must be retained. A deterministic contention loss removable by offline scheduling/layout/outstanding tuning is a compiler or provisioning issue until proven otherwise. A large total interference slowdown is not a recoverable scheduling opportunity.

The user's explanations A and B need not be mutually exclusive. Finer shared-resource behavior may cause a large slowdown that R4 could not represent, while general completion-ready scheduling still recovers little or nothing. Report separately the resource/interference penalty, benefit of stronger static tuning, paid causal dynamic benefit, and any strictly labelled future-information probe. Only the latter two, together with observability and cost, speak to a potential mechanism.

Comparison needs a strong fixed plan, completion-ready replay with aligned static hints, and a strictly labelled information upper bound or offline intervention. Every policy uses the same work, layout, buffers, raw service environment and controller capacity. A future-aware heuristic is not an upper bound on all schedules unless the declared finite search is exhaustive; call it a clairvoyant probe otherwise.

## Analytic acceptance tests requested before R5 result interpretation

1. Isolated request has the stated setup plus byte-service time. Total requested, served and returned bytes match, with no duplicate IDs.
2. Same-bank transactions serialize; independent banks can overlap only up to the shared ingress/return bottleneck. A bandwidth ablation must not silently add aggregate bandwidth.
3. Outstanding=1 versus 2 has an analytically predictable latency-hiding case. Credits return only at the documented boundary and never exceed capacity.
4. A one-entry return/completion FIFO with a slow consumer propagates backpressure at the documented producer boundary; no early data visibility, event loss, or unsafe slot reuse.
5. With exogenous variability disabled, seeds do not change service or arbitration. Compute demand is constant across all environments.
6. Exogenous arrival/calendar hashes match across policies; internal queue timings are allowed and expected to differ.
7. A tiny graph enumerates legal static plans and shows the exactness boundary. Test-seed-specific enumeration is reported separately as clairvoyant.
8. Same-time completion processing and innocuous identifier renaming do not change outcomes except for explicitly declared identity-based priority.
9. Source numerical checks include full source widths or clearly distinguish full-width structural/byte validation from smaller numerical validation. FP64 agreement alone does not establish BF16 rounding or trained model quality.

## Interpretation gates

- **Accept further bottleneck study:** a declared realistic source slice has substantial reproducible loss due to a specified uncertainty; static controls cannot remove it within the admitted optimization space; and the loss has observable timing/resource causes. This accepts a research question, not a hardware proposal.
- **Accept mechanism exploration:** additionally show that a finite, causal observation and legal action recover enough end-to-end latency after stated control costs. PPA remains a separate gate. Do not infer utility from waiting-time sums.
- **Refine simulator/workload:** analytic/model checks fail, static gap remains material, or the observed effect is driven by a disputed traffic/granularity assumption. Fix or bound that uncertainty before interpreting performance.
- **Reject the tested direction:** the declared sweep and strongest available controls reveal no stable sufficient net opportunity. Preserve negative results; do not add scheduler complexity or tune until a positive appears.

## R5 implementation and artifact audit

### Pre-main implementation review and corrections

Reviewed `model.py`, `resource_sim.py`, `coarse_sim.py`, `static_plans.py`, `run_experiments.py`, and the independent numerical and tiny-exact code. Three concrete issues were reported and corrected before the main comparison:

1. GDN's RF budget counted only 2 KiB beyond the 64 KiB state despite declaring all four tokens' prepared inputs and outputs resident. The corrected budget is 73,760 bytes per core: 65,536 state + 6,176 prepared inputs + 2,048 outputs. It remains below the assumed 128 KiB, but the earlier accounting would have misstated a capacity boundary.
2. Background bank selection was originally `seed % 8` regardless of bank count. The backend now passes the configured bank count, guaranteeing the selected bank exists. The one-bank case loses a larger fraction of aggregate capacity under the same one-bank interruption; it is explicitly a stress case rather than an equal-interference ablation.
3. The task-order opportunity counter omitted fixed DMA pacing when testing alternative legality. It now requires DMA pacing to permit issue. This changes opportunity accounting, not execution latency.

The phrase implying this baseline dominates R4 was removed: R4 already had order local search. R5 adds bank coloring and command pacing and up to 64 legal adjacent-resource-order candidates, but is not a superset of R4's search and not a production-static optimum. Two training and two validation seeds are a limited characterization of the uncertainty distribution. There is no test-seed selection of plans.

### Analytic and metamorphic tests

`python -X utf8 -B -m r5.test_resource_sim` passes **9 test methods**, including the following independently derived results:

| Check | Analytic expectation and observed result |
| --- | --- |
| One 256-byte DMA | 1 dispatch + 64 response latency + 8 external bus + 6 fabric + 16 bank + 1 notification = **96 cycles**; destination visibility and credit return at 95 |
| Two local requests, two banks | Different banks overlap at fixed 128 B/cycle aggregate injection: **8 cycles**, versus **10** when both addresses hit the same bank |
| Outstanding credits | Two requests with the declared small deterministic test parameters take **28 cycles at O=1**, **16 at O=2**; credit returns at destination SRAM visibility |
| Return FIFO/backpressure | Two requests take **18 cycles with one return slot**, **16 with two**; second external transfer waits for the first destination-visible release |
| Noise and common samples | Zero-noise seeds produce identical command/request traces; reordered plans preserve raw per-request latencies and calendar environment while changing endogenous issue times |
| Simultaneous events | Two equal-time producers are committed before their join; nonsemantic producer renaming preserves the **16-cycle** result |
| Full-width source contracts | Six Qwen/FLUX/GDN S/B executions pass conservation, timing, credit, last-reader, in-place state and byte/MAC accounting checks |
| Negative checker controls | Duplicate request, early visibility, wrong byte size, and early credit release are all rejected |

The bank background test also covers 1/2/4/8 configured banks and multiple seeds. Six additional command-atomic source executions pass a separate stage/occupancy/integral checker. These are bounded model validation cases, not target-hardware acceptance.

`replay_audit.py` does not import the event loop or its arbitration helpers. It reconstructs expected requests from declared spans, independently integrates periodic availability, checks service demand, shared bandwidth, all capacities, dependency visibility, no overlapping resource service, request/byte conservation, command completion, and partial-order proofs of shared-memory lifetime. It checks that reported legal alternatives also obey pacing. It does not independently reproduce every arbiter choice or prove globally work-conserving issuance.

During the main-run startup window, added post-run CLI/coarse checks were separated into `artifact_audit.py`; `replay_audit.py` was restored byte-for-byte to the run manifest hash `419ac0573027d04c1c9d966be6f14fe299648dbb70389acb56e926ea195a1c76`. No performance model or runner was changed by the red-team. The final artifact audit must verify this and all runtime hashes.

### Final artifact results

**PASS for the declared software/abstract-machine consistency boundary; no device-performance acceptance.** The main run completed 42 configurations, 7,094 train/validation/test executions, and 1,512 held-out policy results. `python -X utf8 -B -m r5.artifact_audit --results r5/results` independently checked all training means, training shortlists, validation selection, paired means, bootstrap intervals, and source/preregistration hashes.

All 1,296 request-backend held-out executions invoked the frozen independent checker in memory, with a stored receipt per result. The retained 126 detailed traces (108 request, 18 command-atomic) were additionally loaded from disk and replayed: **1,073,880 retained request events**. Retention covers seed 2000 in each configuration; other held-out seeds retain parameters/results/audit receipts and can be regenerated. Train/validation main executions do not have independent detailed replay receipts. See `results/independent_replay_audit.json`.

| Main policy contrast | Positive / negative / zero configuration means | Largest positive mean |
| --- | --- | --- |
| Request B0 versus S | 2 / 18 / 16 | +0.164912%, O=1 stress, CI [-0.025304%, +0.345772%] |
| Request B2 versus S | 2 / 34 / 0 | +0.182135%, O=1 stress, CI [-0.008212%, +0.353421%] |
| Command-atomic B0 versus S | 0 / 0 / 6 | zero |
| Command-atomic B2 versus S | 0 / 6 / 0 | none |

No configuration passes the registered 5% screen, including before extra dispatch cost. The two positive B2 means are small stress-case values with intervals crossing zero; they are not evidence to reopen the architecture gate.

The independent tiny probe retains all 20 legal topological priority plans for a six-command graph. Under its declared eight-point equiprobable request-latency distribution, exact expected static latency within that class is 198.247656 cycles, the separately clairvoyant class envelope is 194.195588, B0 is 195.122656, and B2 is 201.997656. All 27 retained S/B0/B2 traces passed the independent checker, recorded in `tiny_exact_trace_audit.json`. This shows the model can exhibit small completion information value while costs erase it; the finite synthetic class is not a full-source or device-wide bound.

### Posthoc compiler-residency falsification control

The GDN slice retained state in SRAM between its four prepared tokens even though the declared RF budget could hold state, inputs, and outputs throughout. This is a weaker compiler lowering, not evidence of inherently uncertain state traffic. An explicitly posthoc control on fresh train 3200/3201, validation 3300/3301, and test 3400..3411 reran both original and RF-resident lowerings with the same compiler search and policies.

`python -X utf8 -B -m r5.control_audit` independently validated the final control source hash, disjoint splits, plan selection, statistics, unchanged arithmetic commands/per-head state update order, RF capacity, and bytes. It additionally replayed **24 retained traces / 73,728 requests**. The control ran **928 independently checked executions** across training, validation and test. Its source hash is `b9d0c270730b99f57705ae536228e787ca1451b04c39f77ef0febbab1552192c`; main runtime hashes remained unchanged. See `resident_control_independent_audit.json`.

| Compiler-residency control | Static end-to-end gain | Resident B0 versus resident S | Resident B2 versus resident S |
| --- | ---: | ---: | ---: |
| Reference, no uncertainty | 16.013380% | 0 | -0.071487% |
| Reference, combined | 24.027219% | 0 | -0.095403% |
| Outstanding=1, combined | 7.155083% | 0 | -0.015134% |
| Return slots=1, combined | 11.852688% | 0 | -0.057820% |

The two source-equivalent lowerings retain 917,504 vector operations, 131,072 external state bytes, 73,760 RF bytes/core and 4,096 RF output bytes. Static residency reduces local state-transfer traffic from 1,048,576 to 262,144 bytes. This is an informative compiler result that strengthens the negative scheduling finding. It is not a positive dynamic architecture result, nor proof that a real full-model decoder can keep state in RF across tokens.

### Scientific interpretation boundaries for the final decision

- **A and B can both be supported conditionally.** If request-level finite resources substantially change slice latency while B0/B2 remain ineffective, R4 omitted consequential resource behavior but did not thereby overlook a profitable general ready scheduler. A resource-model correction and a mechanism opportunity are different findings.
- **Finite credits are not inherently runtime uncertainty.** With deterministic response latency, outstanding count may limit sustainable request throughput. A large O=1 slowdown can be a predictable provisioning constraint; increasing O in a sensitivity changes hardware resources and is not a speedup attributable to ready scheduling. Likewise, a one-entry return buffer may serialize fixed pipeline stages.
- **The control model is still incomplete.** Notification delay is fixed with no finite completion-event FIFO or notification service queue. The return slots are data-path credits, not a proof of bounded scheduler-event history. The fabric is a single serialized DMA stage, not a flit/virtual-channel NoC model. Local RF feeds reach SRAM banks without a separate modeled NoC route. Compute is an uncalibrated `MAC/rate + fill` or vector operation-count model.
- **Full K does not mean full application.** Source dimensions and payload arithmetic are stronger than R4's reduced hidden widths, but coverage is two gate/up output-axis slices and two recurrent heads. The timed simulator does not execute the numerical payload. It has not established full-layer fusion/layout/mapping optimality, hardware dtype throughput, model quality, energy, or area.
- **RF-resident GDN control is a compiler hypothesis.** The micrograph assumes four tokens' prepared inputs are already resident and no intervening layers contend for RF. Keeping state in RF is therefore a valid static control for this micrograph. Its outcome cannot be extended directly to autoregressive tokens interleaved with the rest of a full model. Any improvement from avoiding deterministic state transfers is not recovered unpredictable waiting.
- **Trace evidence distinguishes opportunity from benefit.** The saved deterministic FLUX comparison has 3,239 cycles of legal static order-wait opportunities, yet S=57,575 and B0=57,879 cycles. B0 admits two core1 weight transfers while the shared input is still in flight; shared input visibility moves from 8,280 to 10,328. Total external payload and service remain identical. The read-only diagnosis in `trace_diagnosis.json` is consistent with earlier prefetch competing against needed shared input. It is a paired-trace explanation, not a one-action intervention proving each command's causal contribution.

## Independent verdict and next falsification gate

**Reject continuing the general completion-ready candidate in this tested family; refine the remaining question around measured resources and compiler residency.** Added full-width source slices, finite DMA/data-return capacities, bank traffic, static layout/pacing/order search, and the stronger GDN residency control still provide no sufficiently large stable ready-dispatch benefit. There is no evidence to justify a more complex or smaller scheduler proposal.

The new model does expose consequential resource behavior: reference bus interference increases the two projection slices' optimized-static latency by roughly 32%; the original GDN slice is sensitive to bank service. But a substantial fraction of modeled GDN cost is removed by a static residency change, and the scheduling policies do not recover the remaining loss. Atomic-versus-request differences mix granularity, pipelining, per-request RTT, finite queues and bank routing; they can be positive or negative and are not a single-factor estimate of missing runtime opportunity.

The defensible next decision is a measurement/contract gate: determine whether a target's attainable compiler output already holds the relevant state and whether DMA outstanding, return buffering, bank/port contention or external-master interference produces a reproducible residual loss. Hardware observations and causal alternatives must then show recoverability beyond retuning the static compiler. If those measurements are unavailable, the conclusion should remain the present conditional negative result. No further simulated mechanism complexity is justified merely because real hardware remains unmeasured.
