"""Per-sample clairvoyant heuristic: feasible schedule, NEVER labelled a bound."""
import json
from pathlib import Path
from sim.workload.motifs import synthetic
from sim.compiler import compile_candidates, select_static
from sim.hardware_model import Hardware
from sim.hardware_model.latency import sample
from sim.execution import simulate
from sim.scheduler.oracle import clairvoyant_heuristic


def main():
    rows = []
    for shape in ("chain", "critical_background", "llm_prefill", "dit_cfg"):
        w = synthetic(shape)
        c = select_static(compile_candidates(w), Hardware())
        for seed in range(5):
            d = sample(w, seed, .6)
            rows.append({"shape": shape, "seed": seed, "A_mean_schedule": simulate(c, Hardware(), d, "A").latency,
                         "B_same_contract": simulate(c, Hardware(), d, "B").latency,
                         "clairvoyant_heuristic": clairvoyant_heuristic(c, d).latency})
    path = Path(__file__).parent / "results" / "r3" / "clairvoyant_probe.json"
    path.write_text(json.dumps({"semantics": "same fixed mapping, same zero-overhead hardware; future durations known only by clairvoyant heuristic; not exact and not an upper/lower bound", "rows": rows}, indent=2) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
