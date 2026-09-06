# R9 reference architecture experiment

Start with [experiment_report.md](experiment_report.md). The reference hardware lives in [reference_hardware.json](reference_hardware.json); it is not a current TARS specification.

The completed experiment keeps the shared EXT → cluster DMA → private VMEM resource path explicit, including multicast replication, staged split-K partials, finite credits, source last-reader and destination visibility. It preserves the R1–R8 artifacts and rejects a new scheduler claim for the sampled single-action family. Strong-interference phases and changed EXT/DMA ratios remain explicitly unresolved.

Use a fresh directory to reproduce the registered run:

```powershell
python -X utf8 -B r9/run_experiment.py --output r9/reproduction_new --workers 4
python -X utf8 -B r9/independent_check.py --results r9/reproduction_new
```

`check_tests.py` independently verifies a finite exact class and failure fixtures. `check_results.py` verifies the original frozen result artifacts and appended history. See the report for evidence boundaries, sensitivity limits and the next discriminative question.
