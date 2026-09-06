"""Run paired-seed ablations. python -B -m experiments.run --seeds 20"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
from dataclasses import asdict, replace
from sim.compiler import compile_candidates, select_static
from sim.execution import simulate, verify_trace
from sim.hardware_model import Hardware
from sim.hardware_model.latency import sample
from sim.scheduler.oracle import exact_orders, clairvoyant_heuristic
from sim.workload.motifs import arrival_reversal, synthetic, tile


ROOT = Path(__file__).resolve().parent


def configurations():
    out = []
    def add(name, shape="pipeline", cov=.6, cores=2, clusters=1, chips=1, stages=3,
            pieces=1, vary=("memory", "communication"), tail=0.0, **hw):
        out.append(dict(name=name, shape=shape, cov=cov, cores=cores, clusters=clusters,
                        chips=chips, stages=stages, pieces=pieces, vary=vary, tail=tail,
                        hardware=asdict(Hardware(**hw))))
    for shape in ("chain", "fork_join", "diamond", "critical_background", "pipeline", "llm_prefill", "llm_decode", "dit_cfg"):
        add(shape + "_deterministic", shape=shape, cov=0)
        add(shape + "_memory_cov06", shape=shape)
    for cov in (.1, .3, 1.0):
        add(f"uncertainty_{cov}", shape="fork_join", cov=cov)
    add("heavy_tail", shape="fork_join", cov=.3, tail=.05)
    for cores in (4, 8):
        add(f"cores_{cores}", cores=cores)
    for clusters in (2, 4):
        for dist in (False, True):
            add(f"clusters_{clusters}_{'local' if dist else 'central'}", clusters=clusters, stages=2,
                distributed=dist, issue_cycle=2, dispatch_latency=1, completion_latency=1,
                wakeup_cycle=2, issue_width=2, wakeup_width=2)
        # Same TOTAL entry/byte/issue/wakeup budgets: isolate sharding from replication.
        for dist in (False, True):
            multiplier = 1 if dist else clusters
            add(f"equal_budget_clusters_{clusters}_{'local' if dist else 'central'}", clusters=clusters, stages=2,
                distributed=dist, window=16 * multiplier, byte_window=4096 * multiplier,
                issue_cycle=2, dispatch_latency=1, completion_latency=1, wakeup_cycle=2,
                issue_width=multiplier, wakeup_width=multiplier)
    for chips in (2, 4):
        for vary in (("memory",), ("communication",), ("memory", "communication")):
            add(f"chips_{chips}_{'_'.join(vary)}", chips=chips, stages=2, vary=vary,
                issue_cycle=2, dispatch_latency=1, completion_latency=1, wakeup_cycle=2)
    for pieces in (1, 2, 4):
        for overhead in (0, 2):
            add(f"grain_{pieces}_cost_{overhead}", stages=2, pieces=pieces,
                issue_cycle=overhead, dispatch_latency=overhead, completion_latency=overhead,
                wakeup_cycle=overhead, issue_width=1, wakeup_width=1)
    for window in (2, 8, 32):
        add(f"window_{window}", window=window, issue_cycle=1, completion_latency=1,
            wakeup_cycle=1, dispatch_latency=1)
    for width in (1, 2, 8):
        add(f"wakeup_{width}", shape="fork_join", cores=4, issue_cycle=1,
            completion_latency=2, wakeup_cycle=4, wakeup_width=width)
    add("byte_window_256", byte_window=256, issue_cycle=1, completion_latency=1)
    return out


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def summary(rows):
    output = []
    for name in dict.fromkeys(r["config"] for r in rows):
        subset = [r for r in rows if r["config"] == name]
        policies = {p: [r for r in subset if r["policy"] == p] for p in ("A", "A2", "B", "C")}
        item = {"config": name, "seeds": len(policies["A"]), "tasks": subset[0]["tasks"]}
        for p, samples in policies.items():
            values = [r["latency"] for r in samples]
            item[p + "_mean"] = statistics.mean(values)
            item[p + "_p95"] = sorted(values)[max(0, math.ceil(.95 * len(values)) - 1)]
        # Paired per-seed latency reduction; CI covers synthetic sampling only.
        for p in ("B", "C"):
            gain = [100 * (a["latency"] - b["latency"]) / a["latency"]
                    for a, b in zip(policies["A2"], policies[p])]
            mean = statistics.mean(gain)
            se = statistics.stdev(gain) / math.sqrt(len(gain)) if len(gain) > 1 else 0
            item[p + "_paired_reduction_pct"] = mean
            item[p + "_normal95_low"] = mean - 1.96 * se
            item[p + "_normal95_high"] = mean + 1.96 * se
            item[p + "_wins"] = sum(x > 1e-9 for x in gain)
            item[p + "_losses"] = sum(x < -1e-9 for x in gain)
        output.append(item)
    return output


def counterexample(directory):
    w = arrival_reversal()
    options = compile_candidates(w)
    samples = [dict(load0=80, load1=120, vpu0=20, vpu1=20),
               dict(load0=120, load1=80, vpu0=20, vpu1=20)]
    static = select_static(options, Hardware(), samples)
    # For this graph the only two consequential static choices are VPU0/1 order.
    table = []
    for order in (("vpu0", "vpu1"), ("vpu1", "vpu0")):
        c = replace(static, resource_order={**static.resource_order, "vpu": order},
                    admission_order=("load0", "load1", *order))
        table.append({"vpu_order": order, "latencies": [simulate(c, Hardware(), d, "A").latency for d in samples]})
    result = {"evidence": "exact bounded synthetic counterexample, not measured NPU",
              "distribution": "equiprobable (80,120) and (120,80); mean100 CoV0.2; no storage alias",
              "static_orders_exhausted": table, "static_expected_latency": 150,
              "dynamic_expected_latency": 140, "latency_reduction_pct": 100 / 15,
              "exact_oracle_latencies": [exact_orders(static, d)[0] for d in samples],
              "descriptor_contract": static.descriptors(),
              "traces": {p: [simulate(static, Hardware(), d, p).trace for d in samples] for p in ("A", "B")}}
    write_json(directory / "counterexample.json", result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--training-seeds", type=int, default=8)
    parser.add_argument("--filter", default="")
    parser.add_argument("--output", default="r3")
    args = parser.parse_args()
    if args.seeds < 2 or args.training_seeds < 1:
        parser.error("at least two test seeds and one training seed required")
    destination = ROOT / "results" / args.output
    destination.mkdir(parents=True, exist_ok=True)
    configs = [c for c in configurations() if args.filter in c["name"]]
    write_json(ROOT / "configs" / (args.output + ".json"), {"test_seeds": list(range(args.seeds)),
               "training_seeds": list(range(10000, 10000 + args.training_seeds)), "configs": configs})
    counterexample(destination)
    rows = []
    metric_file = (destination / "metrics.jsonl").open("w", encoding="utf-8")
    for cfg in configs:
        w = tile(synthetic(cfg["shape"], cfg["cores"], cfg["clusters"], cfg["chips"], cfg["stages"]), cfg["pieces"])
        h = Hardware(**cfg["hardware"])
        options = compile_candidates(w)
        mean_static = select_static(options, h)
        training = [sample(w, seed, cfg["cov"], cfg["tail"], vary=cfg["vary"])
                    for seed in range(10000, 10000 + args.training_seeds)]
        robust_static = select_static(options, h, training)
        for seed in range(args.seeds):
            durations = sample(w, seed, cfg["cov"], cfg["tail"], vary=cfg["vary"])
            duration_digest = hashlib.sha256(json.dumps(durations, sort_keys=True).encode()).hexdigest()
            for policy, contract, simulator_policy in (("A", mean_static, "A"), ("A2", robust_static, "A"),
                                                       ("B", robust_static, "B"), ("C", robust_static, "C")):
                r = simulate(contract, h, durations, simulator_policy)
                verify_trace(contract, r, h)
                row = {"config": cfg["name"], "seed": seed, "policy": policy, "tasks": len(w.tasks),
                       "latency": r.latency, "compiler_priority": contract.compiler_policy,
                       "duration_sha256": duration_digest,
                       "ready_queue_mean": r.metrics["ready_queue_mean"],
                       "state_bits": r.metrics["abstract_state_bits"],
                       "wakeup_messages": r.metrics["wakeup_messages"],
                       "candidate_checks": r.metrics["candidate_checks"]}
                rows.append(row)
                metric_file.write(json.dumps({**row, "metrics": r.metrics}, sort_keys=True) + "\n")
                if seed == 0:
                    write_json(destination / "traces" / f"{cfg['name']}_{policy}.json", r.trace)
            if seed == 0:
                write_json(destination / "contracts" / f"{cfg['name']}.json", {
                    "descriptors": robust_static.descriptors(), "admission_order": robust_static.admission_order,
                    "resource_order": robust_static.resource_order, "buffers": [asdict(b) for b in robust_static.buffers],
                    "compiler_policy": robust_static.compiler_policy, "durations": durations})
        current = summary([r for r in rows if r["config"] == cfg["name"]])[0]
        print(f"{cfg['name']}: n={len(w.tasks)} A2={current['A2_mean']:.2f} B={current['B_mean']:.2f} C={current['C_mean']:.2f} B_gain={current['B_paired_reduction_pct']:.2f}%", flush=True)
        # Progressive results are useful even if a long sweep is interrupted.
        write_json(destination / "summary.json", summary(rows))
    metric_file.close()
    with (destination / "samples.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader(); writer.writerows(rows)
    summaries = summary(rows)
    with (destination / "summary.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summaries[0]) if summaries else [])
        writer.writeheader(); writer.writerows(summaries)
    sources = sorted(list((ROOT.parent / "sim").rglob("*.py")) + [Path(__file__)])
    write_json(destination / "manifest.json", {"command": f"python -B -m experiments.run --seeds {args.seeds} --training-seeds {args.training_seeds} --filter '{args.filter}' --output {args.output}",
               "evidence_level": "uncalibrated synthetic event simulation only", "configs": len(configs),
               "test_samples": len(rows), "sources_sha256": {str(p.relative_to(ROOT.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}})


if __name__ == "__main__":
    main()
