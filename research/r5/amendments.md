# R5 audit and amendment log

The frozen main contract is `experiment_plan.md`; its hash is in
`results/run_manifest.json`. This log does not overwrite that contract.

## Before main execution

- Independent source/analytic review corrected GDN RF storage to73,760 bytes per
  core: state65,536 + four-token prepared vectors6,176 + live outputs2,048.
- Background bank selection changed from a hardcoded modulo8 to modulo the
  configured bank count. The one-bank sensitivity still affects a greater share
  of aggregate capacity, and is labelled a stress case.
- Static order-opportunity accounting now excludes DMA commands forbidden by
  the selected pacing. This changes an opportunity counter, not dispatch logic.
- Removed a claim that the new compiler pool is globally stronger than R4.
  Added up to64 training-only legal resource-order swaps before main results.
  R5 expands layout/pacing but does not contain every R4 optimization.
- Nine independent tests and coarse timing/byte tests passed before the main run.

## During main execution: independent checker packaging

The red team briefly appended a post-run CLI to `replay_audit.py`. Those additions
were moved to the separate `artifact_audit.py`, restoring the exact frozen
`replay_audit.py` SHA256
`419ac0573027d04c1c9d966be6f14fe299648dbb70389acb56e926ea195a1c76`.
The original per-trace audit function and performance simulator were unchanged.
The final artifact audit verifies all runtime hashes against the frozen manifest.

## Post-registration compiler control (not a new mechanism)

Independent source-contract review identified that the GDN slice's declared RF
capacity can retain its two selected state heads across the four prepared input
tokens. Thus the main graph's per-token SRAM round trips are a lowering choice,
not capacity-mandated traffic. They cannot support a claim that strong static
has exhausted its options.

`resident_control.py` therefore adds an explicitly posthoc static lifetime
control: same arithmetic, initial state transfer, output contract and hardware;
read each head once, process four tokens in RF, write final state once. No new
dynamic policy. It compares fresh training3200/3201, validation3300/3301 and
test3400..3411 on reference none/combined and outstanding1/return1 combined.
Preserve original main results and report both lowerings. This is a correction
to baseline coverage, not an attempt to pass the architecture proposal gate.

The control applies to this four-token prepared-input slice. It does not prove
state can remain in RF throughout a full multilayer/autoregressive workload;
all32 value heads and other operators may compete for the same storage, and
future decode-token inputs are not available ahead of generation.
