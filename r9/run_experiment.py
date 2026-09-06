"""Pre-registered R9 reference experiment. New output directories only."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import random
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
HERE = ROOT / "r9"
CONDITIONS = {"quiet": 0.0, "reserved20": 0.2, "reserved35": 0.35}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def cid(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]


def pool():
    """Finite structured pool, intentionally not all Cartesian interactions."""
    configs = {}
    def add(c):
        configs[cid(c)] = c
    for mapping in ("C2N", "C2K", "C1N"):
        for ktile, multicast, buffers, order in itertools.product((256, 512, 1024), (False, True), (1, 2), ("xw", "wx")):
            base = dict(mapping=mapping, ktile=ktile, buffers=buffers, prefetch=buffers,
                        resident_x=False, multicast=multicast, layout="gather", order=order,
                        reverse=False, outstanding=4)
            add(base)
            # Orthogonal probes around the double-buffer x-first anchors. Main
            # lattice already jointly crosses mapping, tiling, replication,
            # buffering and operand order; these add restricted interactions.
            if buffers == 2 and order == "xw":
                for field, values in (("layout", ("row",)), ("reverse", (True,)),
                                      ("outstanding", (1, 2)), ("resident_x", (True,)),
                                      ("prefetch", (1,))):
                    for val in values:
                        add({**base, field: val})
        for multicast, order, layout in itertools.product((False, True), ("xw", "wx"), ("gather", "row")):
            add(dict(mapping=mapping, ktile=0, buffers=1, prefetch=1, resident_x=True,
                     multicast=multicast, layout=layout, order=order, reverse=False, outstanding=4))
    return [{"id": k, "config": configs[k]} for k in sorted(configs)]


def environments(seed, n):
    rng = random.Random(seed)
    return [{"block": i, "phase": rng.random() * 8192.0} for i in range(n)]


def env(phase, condition):
    return {"period": 8192.0, "duty": CONDITIONS[condition], "phase": phase}


def evaluate_job(job):
    from r9.model import build_graph, simulate, resource_lower_bound
    record, hw, phases = job
    try:
        graph = build_graph(hw, record["config"])
    except (ValueError, AssertionError) as exc:
        return {**record, "legal": False, "reason": str(exc)}
    quiet = simulate(graph, hw, env(0, "quiet"))
    values = {"quiet": [quiet["elapsed"]]}
    lbs = {"quiet": [resource_lower_bound(graph, hw, env(0, "quiet"))]}
    for condition in ("reserved20", "reserved35"):
        values[condition], lbs[condition] = [], []
        for p in phases:
            e = env(p["phase"], condition)
            result = simulate(graph, hw, e)
            values[condition].append(result["elapsed"])
            lbs[condition].append(resource_lower_bound(graph, hw, e))
    return {**record, "legal": True, "elapsed": values, "lower_bound": lbs,
            "external_bytes": quiet["external_bytes"], "packet_count": quiet["packet_count"]}


def evaluate(records, hw, phases, workers, label):
    jobs = [(r, hw, phases) for r in records]
    outputs = []
    if workers == 1:
        it = map(evaluate_job, jobs)
        for i, output in enumerate(it, 1):
            outputs.append(output)
            if i % 20 == 0:
                print(f"{label} {i}/{len(records)}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            for i, output in enumerate(executor.map(evaluate_job, jobs, chunksize=2), 1):
                outputs.append(output)
                if i % 20 == 0:
                    print(f"{label} {i}/{len(records)}", flush=True)
    return outputs


def mean(record, condition):
    return statistics.mean(record["elapsed"][condition])


def choose(training, hw, validation_phases, workers, label):
    eligible = [r for r in training if r["legal"]]
    shortlisted = {}
    for mapping, multicast, condition in itertools.product(("C2N", "C2K", "C1N"), (False, True), CONDITIONS):
        group = [r for r in eligible if r["config"]["mapping"] == mapping and r["config"]["multicast"] == multicast]
        for r in sorted(group, key=lambda r: (mean(r, condition), r["id"]))[:4]:
            shortlisted[r["id"]] = {"id": r["id"], "config": r["config"]}
    validation = evaluate(list(shortlisted.values()), hw, validation_phases, workers, label)
    selected = {}
    for scope in ("main", "C1N", "C2N", "C2K"):
        group = [r for r in validation if r["legal"] and
                 ((r["config"]["mapping"] != "C1N") if scope == "main" else r["config"]["mapping"] == scope)]
        selected[scope] = {c: min(group, key=lambda r: (mean(r, c), r["id"]))["id"] for c in CONDITIONS}
    return validation, selected


def stats(values):
    n = len(values)
    mu = statistics.mean(values)
    # All confirmatory comparisons have n=30 independent paired phase blocks.
    # For deterministic quiet no sampling uncertainty is invented.
    if n == 1 or all(v == values[0] for v in values):
        interval = [mu, mu]
    else:
        assert n == 30, n
        margin = 2.045229642132703 * statistics.stdev(values) / n ** 0.5
        interval = [mu - margin, mu + margin]
    return {"n": n, "mean": mu, "ci95_t": interval, "min": min(values), "max": max(values)}


def summarize(rows):
    summary = {}
    for session, condition in itertools.product((1, 2), CONDITIONS):
        block = [r for r in rows if r["session"] == session and r["condition"] == condition]
        if not block:
            continue
        summary[f"s{session}.{condition}"] = {
            "fixed_static_loss_pct": stats([100 * (r["quiet_selected_elapsed"] / r["quiet_reference_elapsed"] - 1) for r in block]),
            "strong_static_gain_pct": stats([100 * (1 - r["strong_elapsed"] / r["quiet_selected_elapsed"]) for r in block]),
            "remaining_zero_cost_upper_pct": stats([100 * (1 - r["strong_lower_bound"] / r["strong_elapsed"]) for r in block]),
            "strong_elapsed": stats([r["strong_elapsed"] for r in block]),
            "best_sampled_single_action_free_pct": stats([100 * (1 - r["best_free_elapsed"] / r["strong_elapsed"]) for r in block]),
            "best_sampled_single_action_charged_pct": stats([100 * (1 - r["best_charged_elapsed"] / r["strong_elapsed"]) for r in block]),
            "scope": "paired simulated phase blocks; sampled best-action includes no-action and is hindsight, not a causal policy"
        }
    return summary


def trace_save(out, entries, name, hw, e, config, graph, result, **metadata):
    relative = "traces/" + name + ".json.gz"
    path = out / relative
    with gzip.open(path, "wt", encoding="utf8", compresslevel=5) as stream:
        json.dump({"hardware": hw, "environment": e, "config": config,
                   "graph": graph, "result": result}, stream, separators=(",", ":"))
    entries.append({"path": relative, "sha256": sha(path), **metadata})
    return relative


def alternative_actions(result):
    decisions = [d for d in result.get("ext_decisions", []) if len(d["candidates"]) >= 2]
    # Fixed coverage budget, not expanded after observing a positive result.
    sample = decisions[:4] + decisions[-4:]
    unique = {d["decision_index"]: d for d in sample}
    actions = []
    for index, d in sorted(unique.items()):
        alt = next(r for r in d["candidates"] if r != d["chosen"])
        actions.append({"decision_index": index, "choose_request": alt})
    return actions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--skip-sensitivity", action="store_true", help="Diagnostic only; full R9 completion requires sensitivity")
    args = parser.parse_args()
    from r9.model import load_hardware, build_graph, simulate, resource_lower_bound
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "traces").mkdir()
    started = time.time()
    hw = load_hardware()
    records = pool()
    catalog = {r["id"]: r["config"] for r in records}
    phases = {"train": environments(910000, 8), "validation": environments(920000, 8),
              "test_s1": environments(930000, 30), "test_s2": environments(940000, 30)}
    registered = {"created_utc": datetime.now(timezone.utc).isoformat(), "hardware": hw,
                  "files": {str(p.relative_to(ROOT)): sha(p) for p in (HERE / "reference_hardware.json", HERE / "experiment_plan.md", HERE / "prerun_clarifications.md", HERE / "source_and_scope_audit.md", HERE / "run_experiment.py", HERE / "model.py", ROOT / "r4/sources/qwen/config.json", ROOT / "r4/sources/qwen/modeling_qwen3_5.py")},
                  "candidate_count": len(records), "candidate_pool": records, "phases": phases,
                  "counterfactual": "first4 and last4 eligible EXT arbitration epochs, one first nonselected alternative, zero and 8cycle charge, no-action included; hindsight screen only"}
    save(out / "prerun_registration.json", registered)
    training = evaluate(records, hw, phases["train"], args.workers, "train")
    save(out / "training.json", training)
    validation, selected = choose(training, hw, phases["validation"], args.workers, "validation")
    save(out / "validation.json", validation)
    save(out / "selection.json", {"selected": selected, "validation_rule": "per mapping/input mode/environment train top4; validation minimum, canonical id breaks ties", "frozen_before_test_utc": datetime.now(timezone.utc).isoformat()})
    print("SELECTED " + json.dumps(selected), flush=True)
    trace_entries, rows, counterfactuals, controls = [], [], [], []
    qid = selected["main"]["quiet"]
    qgraph = build_graph(hw, catalog[qid])
    qtime = simulate(qgraph, hw, env(0, "quiet"))["elapsed"]
    graphs = {key: build_graph(hw, catalog[key]) for key in set(i for scope in selected.values() for i in scope.values())}
    for session in (1, 2):
        for condition in CONDITIONS:
            sid = selected["main"][condition]
            graph = graphs[sid]
            for p in phases[f"test_s{session}"]:
                block = p["block"]
                e = env(p["phase"], condition)
                sr = simulate(graph, hw, e, detailed=True)
                qr = sr if sid == qid else simulate(qgraph, hw, e, detailed=True)
                stem = f"s{session}.{condition}.b{block:02d}"
                strong_path = trace_save(out, trace_entries, stem + ".strong", hw, e, catalog[sid], graph, sr, stage="test", session=session, condition=condition, block=block, role="strong")
                if sid != qid:
                    trace_save(out, trace_entries, stem + ".quietselected", hw, e, catalog[qid], qgraph, qr, stage="test", session=session, condition=condition, block=block, role="quietselected")
                best = {0: (sr["elapsed"], None, None), 8: (sr["elapsed"], None, None)}
                for action in alternative_actions(sr):
                    for cost in (0, 8):
                        intervention = {**action, "cost_cycles": cost}
                        ir = simulate(graph, hw, e, detailed=False, intervention=intervention)
                        counterfactuals.append({"session": session, "condition": condition, "block": block, "config_id": sid,
                                               "baseline_elapsed": sr["elapsed"], "elapsed": ir["elapsed"], "intervention": intervention})
                        if ir["elapsed"] < best[cost][0]:
                            best[cost] = (ir["elapsed"], intervention, None)
                for cost, (elapsed, intervention, _) in best.items():
                    if intervention is not None:
                        br = simulate(graph, hw, e, detailed=True, intervention=intervention)
                        trace_save(out, trace_entries, stem + f".action{cost}", hw, e, catalog[sid], graph, br, stage="counterfactual", session=session, condition=condition, block=block, intervention=intervention)
                rows.append({"session": session, "condition": condition, "block": block, "phase": p["phase"],
                             "quiet_config_id": qid, "strong_config_id": sid, "quiet_reference_elapsed": qtime,
                             "quiet_selected_elapsed": qr["elapsed"], "strong_elapsed": sr["elapsed"],
                             "strong_lower_bound": resource_lower_bound(graph, hw, e),
                             "best_free_elapsed": best[0][0], "best_charged_elapsed": best[8][0], "strong_trace": strong_path})
                for scope in ("C1N", "C2N", "C2K"):
                    ctrlid = selected[scope][condition]
                    cr = sr if ctrlid == sid else (qr if ctrlid == qid else simulate(graphs[ctrlid], hw, e, detailed=True))
                    if ctrlid not in {sid, qid}:
                        trace_save(out, trace_entries, stem + ".control." + scope, hw, e, catalog[ctrlid], graphs[ctrlid], cr,
                                   stage="control", session=session, condition=condition, block=block, role=scope)
                    controls.append({"session": session, "condition": condition, "block": block, "scope": scope,
                                     "config_id": ctrlid, "elapsed": cr["elapsed"], "external_bytes": cr["external_bytes"],
                                     "lower_bound": resource_lower_bound(graphs[ctrlid], hw, e)})
            print(f"TEST s{session} {condition} complete; {len(counterfactuals)} action executions", flush=True)
            save(out / "test_pairs.json", rows)
            save(out / "counterfactuals.json", counterfactuals)
            save(out / "trace_manifest.json", {"traces": trace_entries})
    save(out / "controls.json", controls)
    save(out / "summary.json", summarize(rows))
    sensitivity = []
    if not args.skip_sensitivity:
        variants = [(key, value) for key in ("external_bytes_per_cycle", "cluster_dma_bytes_per_cycle", "macs_per_core_cycle", "request_latency_cycles") for value in hw["sensitivity"][key] if value != hw[key]]
        variants.append(("vmem_bytes_per_core", 262144 + hw["vmem_reserved_bytes_per_core"]))
        # Restricted sensitivity pool is fixed structurally, before seeing outcomes.
        probes = [r for r in records if r["config"]["mapping"] != "C1N" and r["config"]["buffers"] == 2
                  and r["config"]["prefetch"] == 2 and not r["config"]["resident_x"] and r["config"]["layout"] == "gather"
                  and r["config"]["order"] == "xw" and not r["config"]["reverse"] and r["config"]["outstanding"] == 4]
        for key, value in variants:
            vh = {**hw, key: value}
            label = f"sensitivity.{key}.{value}"
            tr = evaluate(probes, vh, phases["train"], args.workers, label)
            shortlist = {min([r for r in tr if r["legal"]], key=lambda r: (mean(r, c), r["id"]))["id"] for c in CONDITIONS}
            vr = evaluate([r for r in probes if r["id"] in shortlist], vh, phases["validation"], args.workers, label + ".val")
            chosen = {c: min(vr, key=lambda r: (mean(r, c), r["id"]))["id"] for c in CONDITIONS}
            test = []
            for c in CONDITIONS:
                g = build_graph(vh, catalog[chosen[c]])
                for session in (1, 2):
                    for p in phases[f"test_s{session}"]:
                        e = env(p["phase"], c)
                        rr = simulate(g, vh, e, detailed=p["block"] == 0)
                        lb = resource_lower_bound(g, vh, e)
                        test.append({"condition": c, "session": session, "block": p["block"], "elapsed": rr["elapsed"], "lower_bound": lb, "upper_pct": 100 * (1 - lb / rr["elapsed"])})
                        if p["block"] == 0:
                            trace_save(out, trace_entries, label + f".{c}.s{session}", vh, e, catalog[chosen[c]], g, rr, stage="sensitivity", condition=c, session=session, block=0)
            sensitivity.append({"field": key, "value": value, "scope": "restricted static retraining; no mechanism confirmation", "training": tr, "validation": vr, "selected": chosen, "test": test})
            save(out / "sensitivity.json", sensitivity)
            save(out / "trace_manifest.json", {"traces": trace_entries})
            print(label + " complete", flush=True)
    save(out / "completion.json", {"completed_utc": datetime.now(timezone.utc).isoformat(), "host_runner_seconds": time.time() - started,
                                   "test_pair_count": len(rows), "action_executions": len(counterfactuals), "trace_count": len(trace_entries),
                                   "sensitivity_variants": len(sensitivity), "registration_sha256": sha(out / "prerun_registration.json"),
                                   "selection_sha256": sha(out / "selection.json"), "hardware_sha256": sha(HERE / "reference_hardware.json"),
                                   "model_sha256": sha(HERE / "model.py"), "runner_sha256": sha(HERE / "run_experiment.py")})
    print("COMPLETE " + str(out), flush=True)


if __name__ == "__main__":
    main()
