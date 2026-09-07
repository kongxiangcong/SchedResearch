"""Record source graph shapes, reader sets, and scaled float64 numeric evidence."""
import hashlib
import json
from pathlib import Path
import numpy as np
from r4.flux_lowering import build_cases, build_optimized_cases


def main():
    output = Path(__file__).resolve().parent
    graphs, checks = [], []
    for seed in [7, 19, 31]:
        for case in build_cases(seed) + build_optimized_cases(seed):
            values = case.evaluate()
            errors = {k: float(np.max(np.abs(values[k] - expected))) for k, expected in case.reference.items()}
            assert max(errors.values()) < 1e-11
            # Reorder only through actual dependencies, without original-list order.
            available = set(case.initial)
            pending = list(case.nodes)
            order = []
            rng = np.random.default_rng(seed + 101)
            while pending:
                ready = [n for n in pending if set(n.reads) <= available]
                assert ready, "DAG deadlock"
                picked = ready[int(rng.integers(len(ready)))]
                order.append(picked.name)
                available.update(picked.writes)
                pending.remove(picked)
            reordered = case.evaluate(order)
            reorder_errors = {k: float(np.max(np.abs(reordered[k] - expected))) for k, expected in case.reference.items()}
            assert max(reorder_errors.values()) < 1e-11
            checks.append({"case": case.name, "seed": seed, "errors": errors, "reordered_errors": reorder_errors, "order": order})
            if seed != 7:
                continue
            writer = {k: "initial" for k in case.initial}
            for n in case.nodes:
                for k in n.writes:
                    assert k not in writer, "multiple writers"
                    writer[k] = n.name
            readers = {k: [n.name for n in case.nodes if k in n.reads] for k in values}
            tensors = []
            for key, value in values.items():
                tensors.append({"name": key, "shape": list(value.shape), "numeric_dtype": str(value.dtype),
                                "numeric_bytes": value.nbytes, "logical_bf16_bytes_assumption": value.size * 2,
                                "writer": writer[key], "readers": readers[key],
                                "release_condition": "all listed readers complete" if key not in case.outputs else "external output consumer completes",
                                "sha256_numeric_payload": hashlib.sha256(value.tobytes()).hexdigest()})
            graphs.append({"case": case.name, "metadata": case.metadata, "tensors": tensors,
                           "nodes": [{k: getattr(n, k) for k in ("name", "engine", "reads", "writes", "macs", "vector_ops", "source", "fusion", "core")} for n in case.nodes]})
    summary = {"evidence": "scaled random-weight NumPy float64 mathematical lowering only; official PyTorch/BF16 not executed",
               "checks": checks, "lowering_sha256": hashlib.sha256(Path("r4/flux_lowering.py").read_bytes()).hexdigest()}
    (output / "lowering_numeric_audit.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "lowering_tensor_manifest.json").write_text(json.dumps(graphs, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checks": len(checks), "max_absolute_error": max(max(x["errors"].values()) for x in checks), "tensor_counts": {g["case"]: len(g["tensors"]) for g in graphs}}))


if __name__ == "__main__":
    main()
