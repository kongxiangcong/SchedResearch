# R5 preregistered experiment contract

Status: frozen before train/validation/test performance comparisons. A one-case
pipeline/credit smoke test preceded this contract; it did not compare policies.
The requested R1–R4 table, falsification boundary, unresolved questions and proposed
discriminative experiment were delivered before any R5 performance execution.

## Question and competing explanations

After a compiler chooses mapping, storage layout, lifetimes and an execution
order, can a measured runtime resource uncertainty cause recoverable loss?
A: completion-ready ordering has little marginal value. B: missing resource
behavior changes prior conclusions. A and B are not mutually exclusive.
This round tests conditional models of that question, not a real NPU claim.

## Frozen workloads and scope

Three unscaled-inner-dimension source slices: Qwen3.5 K2560 M1 two fused N128
gate/up output tiles; FLUX2 K3072 M32 two fused N128 output tiles; two full
128x128 FP32 GDN state heads for four tokens. These are source-derived slices,
not full models, compiler exports, hardware traces or an end-to-end application.
An output tile includes 64 gate and 64 up channels, not 128 of each.

Projection lowering uses K128 blocking, explicit full-byte requests, shared SRAM,
SRAM-to-RF feed, two SRAM/RF buffers per core and FP32 K-ordered accumulation.
Compute does not lock a memory bank. GDN prepared inputs and all four outputs
are resident in RF; the state starts in external memory and is transferred once,
then remains in SRAM between tokens. GDN initialization/spill is an assumption.
Numerical full-width validation is separate from timed request/address replay;
the performance simulator does not execute tensor payloads.

## Strong static baseline (bounded compiler search)

For every hardware/environment configuration independently, enumerate six
topological-order heuristics (source, critical path, breadth, core-major,
DMA-first, compute-first), three bank colors (0,1,3), and three fixed DMA command
spacings (0,64,1024 cycles). Deduplicate identical full priorities/layout/pacing
(global priorities also break shared command-issue ties).
All plans preserve identical arithmetic, data, declared storage and lifetimes.
Train on seeds 1000,1001. Refine the best plan by up to64 legal adjacent
per-engine-order swaps, evaluated in batches of16 on the same training seeds;
retain unchanged arithmetic/layout/pacing and reject any dependency violation.
The budget is fixed before results, and is a static-baseline improvement, not a
new runtime policy. Select the best three training plans, choose by mean
validation latency on seeds 1100,1101 (deterministic tie-break). Test once on
2000..2011. No test-seed plan selection. Seed-independent cases can be memoized.
Static is fixed per-engine ordering with dependency/credit self-timing and fixed
pacing; it cannot observe latency samples to reorder. Search adds explicit
layout/pacing axes but is not a superset of R4's24 priorities/128 local moves.
Neither establishes optimality over all compiler tilings,
timed schedules, prefetch policies or production compilers.

B0: ready-based bypass using exactly selected static priorities/layout/pacing,
same resources and zero extra dispatch cost. B2: same with two extra cycles per
command. The latter is a sensitivity, not measured hardware area/power cost.
No new scheduler policy or dynamic-priority tuning is allowed this round.

## Frozen configuration matrix

Each workload: reference hardware under none, latency, bank_background,
bus_background, combined; combined with outstanding=1,4,32 (reference16),
return_slots=1,2 (reference8), bank arbitration=fifo (reference ready-bank),
and banks=1 at unchanged aggregate SRAM bandwidth (reference8).
Total 12 configurations x 3 slices. Background interruption is absolute-time,
period512/duty25%, phase determined by seed. A single bank is interrupted;
changing bank count also changes the share of aggregate capacity affected, so
the one-bank row is a stress case, not isolated equal-interference sensitivity.
Request latency has bounded +/-50% variation around64 cycles keyed by seed and
logical request. No cache, DRAM row, thermal or frequency noise is invented.

All numeric hardware settings are hypothesis ranges, not device calibration.
Real sources support finite resources/counters, not the particular BF16 target,
bank count, bandwidth or distribution. DMA return slots are reserved before
external transfer and released after destination SRAM visibility: one explicit
receiver/backpressure contract, not all real DMA designs.

Resource-granularity contrast: same graph/bytes/arithmetic and compiler search
in an atomic pooled-memory backend on reference none/combined (six cases).
It lacks per-request outstanding, destination return credits and bank queues.
This comparison changes abstractions and cannot uniquely identify one feature.

## Discriminative measurements

Primary: paired whole-slice latency S/B0/B2 and mean percentage gain, bootstrap
95% confidence interval (4096 paired-seed bootstrap samples). Secondary: payload
bandwidth, compute utilization, order-blocked union time, credit/return stalls,
request counts and peaks. Stall counters overlap and do not equal reclaimable
wall-clock time. Report external-byte/BW lower bound and maximum possible gain
relative to it; it is a loose bound, not a prediction of scheduler recovery.
Environment-induced loss compares independently trained matching static plans
against noise-free reference; hardware sensitivities retrain every baseline.
Do not call all such differences runtime uncertainty: deterministic RTT/credits
and layout contention may be compiler/resource-capacity issues.

## Validation and falsification gates

Before main comparisons: analytic service/credit/backpressure tests; full-width
numerical oracle; independent byte/dependency/address/lifetime replay on every
request-backend test execution in memory, saving seed2000 S/B0/B2 traces in every
case for offline inspection. A tiny six-command enumeration separately reports exact
optima only within all legal fixed priority/self-timed orders for its finite
environment set. Source/manifests and seeds must make every row reproducible.

Proposal gate: at least5% mean B0 gain with CI lower bound>0 on two source slices
under reference realistic-structure resource settings, surviving B2 and strong
static validation, plus identified observable uncertainty and plausible finite
state/cost path. The5% is a screening threshold, not a proven PPA break-even.
Stress-only positives motivate a measured hardware question, never a proposal.
No positive results or no gate passage => close the generic completion-ready
candidate in this tested family; report negative evidence and unresolved target
hardware calibration/coverage. Do not add new heuristics or sweep latencies to
obtain a positive. Any correctness fix must be logged and affected runs rerun.

Next decision can be targeted device measurements, compiler/layout/resource
co-design, strong static sufficiency within the tested class, or rejection.
Finding a new architecture is not the success criterion.
