# R5: resource uncertainty before architecture

Start with [research progress](../research_progress.md), [experiment report](experiment_report.md)
and [red-team report](redteam_report.md). Historical R1–R4 artifacts are preserved.

This is a reproducible, conditional simulator investigation. Official model
dimensions and public resource mechanisms ground the contracts; hypothetical
timing does not become a target NPU calibration. Source slices are not full-model
end-to-end measurements. No new scheduler architecture is proposed.

## Reproduction

Run from the repository root with Python and NumPy. The recorded environment
uses Python3.14, NumPy2.3.5 on Windows. No trained model download is required.

```powershell
python -X utf8 -B -m r5.audit_existing_artifacts
python -X utf8 -B -m unittest r5.test_resource_sim
python -X utf8 -B -m r5.coarse_sim
python -X utf8 -B -m r5.numerical
python -X utf8 -B -m r5.tiny_exact
python -X utf8 -B -m r5.run_experiments --workers 3
python -X utf8 -B -m r5.summarize
python -X utf8 -B -m r5.artifact_audit --results r5/results
python -X utf8 -B -m r5.source_contract_audit
python -X utf8 -B -m r5.resident_control
python -X utf8 -B -m r5.check_integrity
```

The simulation commands regenerate their result files. To preserve this frozen
run, give `run_experiments` an alternate `--output` directory and point
`artifact_audit --results` there; the default summarizer reads the frozen default
directory. `check_integrity` checks the delivered snapshot, so intended changes
or regenerated provenance must be reviewed before freezing another snapshot.
Training and validation are deterministic bounded searches, and test seeds are
disjoint. Main run plus fresh-seed compiler control may take several minutes.

## Files and evidence boundaries

- `experiment_plan.md`: original pre-registration and falsification gate;
  `amendments.md`: review fixes and posthoc compiler-residency control.
- `model.py`: full-width source-slice lowering and storage contract;
  `resource_sim.py`: closed-loop requests, banks, credits and return backpressure;
  `coarse_sim.py`: matched-work atomic abstraction contrast.
- `static_plans.py`: compiler candidate orders, layout colors, pacing and legal
  local order changes. No test-informed plan or new online policy.
- `numerical.py` / `numerical_checks.json`: BF16 input/weight rounding and FP32
  accumulation/full-size GDN arithmetic; separate from timed payload execution.
- `test_resource_sim.py` / `replay_audit.py`: independent analytic, byte, timing,
  capacity, address/visibility checks; `artifact_audit.py`: post-run statistics,
  frozen source, selection and stored-trace verification.
- `tiny_exact_results.json`: exhaustive finite-priority-class probe, including
  a separately labelled future-information optimum.
- `results/all_cases.md` and per-case JSON: all42 main cases, searches and paired
  tests. Request test traces are independently checked before discard; three
  seed2000 traces per case remain as compressed detailed inspection artifacts.
- `resident_control.py`: fresh-seed GDN compiler lifetime control; preserves
  original results and removes unnecessary intermediate state traffic.
- `resource_evidence.md`, `source_contract_audit.json`, `sources/`: source facts
  and frozen evidence; `measurement_gate.md`: the next real-device measurement
  contract, still unexecuted.

Resource wait counters overlap; they are not a sum of recoverable wall time.
External service occupancy includes interruption stalls and must not be read as
payload-active cycles. B2 adds two cycles per command as sensitivity, not PPA.
The shared-bank/fabric model is not a calibrated DRAM, flit NoC or RTL design.
