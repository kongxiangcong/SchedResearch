"""Read-only R1--R4 hash/statistic audit; writes only a new R5 audit receipt.

This does not rerun an experiment or certify simulator fidelity.
"""
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def read_json(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def rows(name):
    with (ROOT / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def digest(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def counts(values):
    values = list(values)
    return {"positive": sum(x > 1e-9 for x in values),
            "negative": sum(x < -1e-9 for x in values),
            "zero": sum(abs(x) <= 1e-9 for x in values)}


def main():
    receipts = {}
    r4_integrity = read_json("experiments/results/r4/artifact_integrity.json")
    bad = [name for name, sha in r4_integrity["artifact_sha256"].items()
           if digest(name) != sha]
    assert not bad, bad
    receipts["R4_frozen_artifacts"] = len(r4_integrity["artifact_sha256"])
    snapshot = read_json("r4/r3_snapshot/manifest.json")
    for name, sha in snapshot["sources"].items():
        assert digest("r4/r3_snapshot/" + name) == sha, name
        if name.startswith("sim/"):
            assert digest(name) == sha, name
    for name, sha in snapshot["prior_results"].items():
        assert digest(name) == sha, name
    receipts["R3_snapshot_sources"] = len(snapshot["sources"])
    receipts["R3_prior_results"] = len(snapshot["prior_results"])
    r3_manifest = read_json("experiments/results/r3/manifest.json")
    for name, sha in r3_manifest["sources_sha256"].items():
        assert digest(name) == sha, name
    receipts["R3_current_sources"] = len(r3_manifest["sources_sha256"])
    old_audit = (ROOT / "analysis/r1_r2_audit.md").read_text(encoding="utf-8")
    originals = sorted((ROOT / "r1-base").glob("*.md")) + [
        ROOT / "r2-ooo-npu/research.md", ROOT / "r2-ooo-npu/literature-register.md",
        ROOT / "r2-ooo-npu/toy-sim/r4sim.py"]
    original_hashes = {p.relative_to(ROOT).as_posix(): digest(p) for p in originals}
    assert all(sha in old_audit for sha in original_hashes.values())
    receipts["R1_R2_original_files"] = len(original_hashes)

    r3 = rows("experiments/results/r3/summary.csv")
    r3_statistics = {
        "configurations": len(r3), "executions": r3_manifest["test_samples"],
        "B_vs_A2": counts(float(x["B_paired_reduction_pct"]) for x in r3),
        "C_mean_faster_than_B": sum(float(x["C_mean"]) < float(x["B_mean"]) - 1e-9 for x in r3),
        "A2_mean_slower_than_A": sum(float(x["A2_mean"]) > float(x["A_mean"]) + 1e-9 for x in r3),
    }
    r4 = rows("experiments/results/r4/summary.csv")
    samples = rows("experiments/results/r4/samples.csv")
    probe = rows("experiments/results/r4/priority_probe/summary.csv")
    probe_samples = rows("experiments/results/r4/priority_probe/samples.csv")
    policies = {}
    for policy in sorted({x["policy"] for x in r4 + probe}):
        selected = [x for x in r4 + probe if x["policy"] == policy]
        best = max(selected, key=lambda x: float(x["paired_reduction_pct"]))
        policies[policy] = {**counts(float(x["paired_reduction_pct"]) for x in selected),
            "best_config": best["config"], "best_pct": float(best["paired_reduction_pct"]),
            "best_ci95": [float(best["ci95_low"]), float(best["ci95_high"])],
            "gate_count": sum(float(x["paired_reduction_pct"]) >= 5 and float(x["ci95_low"]) > 0 for x in selected)}
    # Independently recalculate each R4 paired sample mean and interval.
    main_index = {(x["config"], x["seed"], x["policy"]): x for x in samples}
    by_policy = defaultdict(list)
    environments = defaultdict(set)
    for sample in samples + probe_samples:
        key = sample["config"], sample["seed"]
        environments[key].add(sample["environment_hash"])
        base = main_index[(*key, "S")]
        value = 100 * (float(base["latency"]) - float(sample["latency"])) / float(base["latency"])
        by_policy[(sample["config"], sample["policy"])].append(value)
    assert all(len(hashes) == 1 for hashes in environments.values())
    for row in r4 + probe:
        values = by_policy[(row["config"], row["policy"])]
        mean = statistics.mean(values)
        half = 1.96 * statistics.stdev(values) / len(values) ** 0.5
        assert abs(mean - float(row["paired_reduction_pct"])) < 1e-8
        assert abs(mean - half - float(row["ci95_low"])) < 1e-8
        assert abs(mean + half - float(row["ci95_high"])) < 1e-8
    static = [x for x in samples if x["policy"] == "S"]
    cf = read_json("experiments/results/r4/counterfactual_summary.json")
    r4_statistics = {
        "main_executions": len(samples), "posthoc_priority_executions": len(probe_samples),
        "summary_rows_recomputed": len(r4) + len(probe), "common_environment_groups": len(environments),
        "policies": policies, "static_trace_count": len(static),
        "static_with_opportunity": sum(float(x["opportunity_union_cycles"]) > 1e-9 for x in static),
        "static_with_inversion": sum(float(x["ready_order_inversion_rate"]) > 1e-9 for x in static),
        "mean_opportunity_fraction_pct": 100 * statistics.mean(float(x["opportunity_union_cycles"]) / float(x["latency"]) for x in static),
        "counterfactual_counts": counts(x["reduction_cycles"] for x in cf),
        "counterfactual_all_applied": all(x["applied"] for x in cf),
    }
    result = {"status": "PASS", "scope": "existing artifact integrity and summary recalculation only; no R5 performance experiment or real-device validation",
              "hash_receipts": receipts, "original_sha256": original_hashes,
              "r3": r3_statistics, "r4": r4_statistics,
              "auditor_sha256": digest("r5/audit_existing_artifacts.py")}
    out = ROOT / "r5/history_audit.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
