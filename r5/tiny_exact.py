"""Exhaustive finite-priority-class probe, not a global hardware oracle.

The six-command graph and two environments are fixed in this source before
observing outcomes. Every topological priority order is enumerated; no search
or parameter tuning is performed. Existing model/backend files are read only.
"""
from dataclasses import asdict
import hashlib
import itertools
import json
from pathlib import Path
import statistics

from r5.model import Command, Graph, Hardware, Plan, Span
from r5.resource_sim import Environment, simulate

ROOT = Path(__file__).resolve().parents[1]
LATENCY_SEEDS = tuple(range(61000, 61008))


def frozen_graph(hw):
    commands = (
        Command("load_A", "dma", 0, "dma", (), (Span(0, 512, "A operands"),)),
        Command("load_B", "dma", 0, "dma", (), (Span(1024, 512, "B operands"),)),
        Command("read_A", "feed0", 0, "read", ("load_A",), (Span(0, 512, "A SRAM to RF"),)),
        Command("read_B", "feed0", 0, "read", ("load_B",), (Span(1024, 512, "B SRAM to RF"),)),
        Command("compute_A", "mxu0", 0, "compute", ("read_A",), cycles=24),
        Command("compute_B", "mxu0", 0, "compute", ("read_B",), cycles=40),
    )
    graph = Graph("tiny_two_dma_read_compute_chains", commands, {
        "rf_bytes_per_core": 1024, "scope": "synthetic control graph, not Qwen/FLUX source workload",
        "address_safety": "two disjoint immutable 512-byte operands; DMA writer before read; private RF holds both",
        "mapping": "two admitted DMA commands feeding one local-read engine and one compute engine on core0",
        "compute_cycles": {"A": 24, "B": 40}, "random_compute": False,
    })
    graph.validate(hw)
    return graph


def all_topological_priorities(graph):
    orders = []
    for order in itertools.permutations(command.cid for command in graph.commands):
        rank = {cid: i for i, cid in enumerate(order)}
        if all(rank[parent] < rank[command.cid] for command in graph.commands for parent in command.deps):
            orders.append(order)
    return orders


def reduction(base, candidate):
    return 100 * (base - candidate) / base


def evaluate_case(name, graph, hw, orders, environments):
    # This is a completely specified finite distribution. Every scenario has
    # known probability 1/N for expected-value enumeration, not a train/test
    # experiment or a claim about a continuous request-latency distribution.
    candidate_results = []
    for index, order in enumerate(orders):
        plan = Plan(order=order, name=f"topological_{index:02}")
        latencies = [simulate(graph, hw, plan, env, policy="S")["latency"] for env in environments]
        candidate_results.append({"id": index, "order": list(order), "latencies": latencies,
                                  "expected_latency": statistics.mean(latencies)})
    best = min(candidate_results, key=lambda row: (row["expected_latency"], row["id"]))
    selected_plan = Plan(order=tuple(best["order"]), name=f"expected_static_{best['id']:02}")
    clairvoyant = []
    traces = []
    for scenario, env in enumerate(environments):
        oracle = min(candidate_results, key=lambda row: (row["latencies"][scenario], row["id"]))
        clairvoyant.append({"scenario": scenario, "environment": asdict(env), "probability": 1 / len(environments),
                            "order_id": oracle["id"], "latency": oracle["latencies"][scenario]})
        static_trace = simulate(graph, hw, selected_plan, env, policy="S", detailed=True)
        assert abs(static_trace["latency"] - best["latencies"][scenario]) < 1e-8
        ready0 = simulate(graph, hw, selected_plan, env, policy="B", extra=0, detailed=True)
        ready2 = simulate(graph, hw, selected_plan, env, policy="B", extra=2, detailed=True)
        traces.append({"scenario": scenario, "static": static_trace, "ready_extra0": ready0, "ready_extra2": ready2})
    oracle_mean = statistics.mean(row["latency"] for row in clairvoyant)
    ready0_mean = statistics.mean(row["ready_extra0"]["latency"] for row in traces)
    ready2_mean = statistics.mean(row["ready_extra2"]["latency"] for row in traces)
    assert oracle_mean <= best["expected_latency"] + 1e-8
    return {"case": name, "environments": [asdict(env) for env in environments],
            "probabilities": [1 / len(environments)] * len(environments),
            "static_candidate_count": len(candidate_results), "candidates": candidate_results,
            "optimal_expected_static_in_class": best,
            "clairvoyant_optimum_each_scenario_in_class": clairvoyant,
            "clairvoyant_expected_latency_in_class": oracle_mean,
            "static_to_clairvoyant_reduction_pct": reduction(best["expected_latency"], oracle_mean),
            "ready_hint": "the exact expected-static winner's fixed priority; no per-scenario priority selection",
            "ready_extra0_mean": ready0_mean, "ready_extra2_mean": ready2_mean,
            "ready_extra0_reduction_pct": reduction(best["expected_latency"], ready0_mean),
            "ready_extra2_reduction_pct": reduction(best["expected_latency"], ready2_mean),
            "traces": traces, "simulator_executions": len(orders)*len(environments) + 3*len(environments)}


def main():
    hw = Hardware(name="tiny_fixed_before_outcome", granule=256, dma_commands=2,
                  outstanding=4, return_slots=2, request_issue=1, external_latency=40,
                  external_bw=16, fabric_bw=32, fabric_latency=2, banks=4, sram_bw=64,
                  local_outstanding=2, dispatch=1, issue_cycle=1, notification=1,
                  sram_capacity=4096, rf_capacity=2048, bank_arbitration="ready_bank")
    graph = frozen_graph(hw)
    orders = all_topological_priorities(graph)
    assert len(orders) == 20  # C(6,3) ways to interleave two length-three chains.
    scenarios = [
        ("deterministic", [Environment(seed=0, mode="none")]),
        ("request_latency_finite_eight_point", [Environment(seed=seed, mode="latency", latency_amplitude=.5)
                                               for seed in LATENCY_SEEDS]),
    ]
    cases = [evaluate_case(name, graph, hw, orders, envs) for name, envs in scenarios]
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
              for name in ("r5/tiny_exact.py", "r5/model.py", "r5/resource_sim.py")}
    result = {"status": "PASS", "source_hashes": hashes, "graph": asdict(graph), "hardware": asdict(hw),
        "scope": "exact enumeration of 20 topological command-priority orders under fixed self-timed backend semantics and a fully specified finite distribution",
        "static_class": "S fixed per-engine order induced by a topological total priority; eager issue under that priority; fixed addresses, mapping, no explicit release delays, bank color0, DMA spacing0",
        "clairvoyant_class": "best of the same 20 S plans separately for each known complete environment; a class-restricted lower latency envelope, not a hardware-wide bound",
        "ready_class": "B uses chosen expected-static priority, completion readiness, same resources/requests; extra0 still pays shared control costs, extra2 adds2 cycles per command",
        "distribution_scope": "8 listed seeds are the exhaustive equiprobable finite request-latency distribution, not held-out samples or a proof for the underlying continuous generator",
        "does_not_enumerate": ["arbitrary timed release schedules", "different mapping/tiling/buffering/address plans", "request/bank arbitration policies", "all dynamic policies", "hardware resource changes"],
        "no_positive_result_requirement": "graph, hardware, two cases and seed set fixed before first evaluation; no tuning loop",
        "simulator_executions": sum(case["simulator_executions"] for case in cases), "cases": cases,
        "evidence_limit": "synthetic exact-class simulator probe; not independent backend timing proof, real-device acceptance, or a global hardware opportunity limit"}
    output = ROOT / "r5/tiny_exact_results.json"
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "executions": result["simulator_executions"],
                     "cases": [{key: case[key] for key in ("case", "static_to_clairvoyant_reduction_pct",
                         "ready_extra0_reduction_pct", "ready_extra2_reduction_pct")} for case in cases]}, indent=2))


if __name__ == "__main__":
    main()
