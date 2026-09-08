"""Registered finite-set experiment; no optimizer is presented as new research.

register uses traffic ledgers only. nominal evaluates every member of C once;
witnesses evaluates the preregistered pairs at all 26 parameter points. Failed
plans are retained as rejected, never used as a speedup denominator.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from event_machine import simulate
from model_builder import HARDWARE, TICKS, micro_graph, scenarios, small_plan_space
from trace_audit import audit_trace

ROOT = Path(__file__).resolve().parent
SOURCES = ["proposal_contract.md", "machine_contract.md", "hardware_model.json",
           "model_builder.py", "event_machine.py", "trace_audit.py", "run_micro.py"]


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def hashes():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES}


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write("\n")


def ledger(spec):
    by_role = defaultdict(Counter)
    links = Counter()
    chains = defaultdict(Counter)
    packet_hops = {}
    for p in spec["metadata"]["packets"]:
        role = p["id"].split("/", 1)[1]
        flits, hops = p["network_flits"], len(p["links"])
        by_role[role].update(packets=1, payload_bytes=p["payload_bytes"], flits=flits,
                             flit_hops=flits*hops)
        packet_hops[p["id"]] = hops
        for link in p["links"]:
            links[link] += flits
            chains[p["id"][:2]][link] += flits
    router = {k: v for k, v in links.items() if "niu(" not in k}
    channel_bytes = Counter()
    for tag in spec["metadata"]["tags"].values():
        if tag["kind"] in ("read", "write"):
            for block in tag["blocks"]:
                if block.startswith("dram/"):
                    channel_bytes["/".join(block.split("/")[:3])] += 16
    return {"by_role": {k: dict(v) for k, v in sorted(by_role.items())},
            "full_protocol_flit_hops": sum(links.values()),
            "payload_router_byte_hops": sum(p["payload_bytes"]*(len(p["links"])-2)
                for p in spec["metadata"]["packets"] if p["payload_bytes"] > 4),
            "packet_hops": packet_hops, "link_flits": dict(sorted(links.items())),
            "max_router_link_flits": max(router.values(), default=0),
            "cross_chain_router_shared_flits": sum(min(chains["c0"][k], chains["c1"][k]) for k in router),
            "physical_channel_bytes": dict(sorted(channel_bytes.items()))}


def isolated_critical_path(spec):
    """Same action DAG with only declared latencies, ignoring all contention.

    This output-visible DAG duration is a diagnostic estimator. Finite buffers,
    credit and resource arbitration do not appear in this estimator.
    """
    latencies, releases, deps = {}, {}, {}
    for job in spec["jobs"]:
        for k, op in enumerate(job["ops"]):
            oid = f"{job['id']}:{k}"
            latencies[oid] = op["latency"]
            releases[oid] = job.get("release", 0) if k == 0 else 0
            deps[oid] = job.get("deps", []) if k == 0 else [f"{job['id']}:{k-1}"]
    ends, visiting = {}, set()

    def visit(oid):
        if oid in ends:
            return ends[oid]
        if oid in visiting:
            raise ValueError("cyclic input DAG")
        visiting.add(oid)
        ends[oid] = max([releases[oid]] + [visit(d) for d in deps[oid]]) + latencies[oid]
        visiting.remove(oid)
        return ends[oid]

    return max(visit(r["output"]["visible"]) for r in spec["metadata"]["refs"])


def register(output):
    before = hashes()
    plans = small_plan_space()
    summaries = {}
    # Window/wait choices do not alter bytes or routes; ledger only the 96 bases.
    for plan in plans:
        if plan["chain1_offset_cycles"] == 0 and plan["source_wait"] == "source":
            summaries[plan["id"]] = ledger(micro_graph(plan))
    by_id = {p["id"]: p for p in plans}
    groups = defaultdict(list)
    for pid, data in summaries.items():
        signature = (by_id[pid]["placement"], digest(data["by_role"]))
        groups[signature].append(pid)
    pairs = []
    strict_packet_equal_pairs = 0
    for group in groups.values():
        for i, a in enumerate(group):
            for b in group[i+1:]:
                la, lb = summaries[a], summaries[b]
                delta = abs(la["cross_chain_router_shared_flits"] - lb["cross_chain_router_shared_flits"])
                if not delta:
                    continue
                strict_packet_equal_pairs += la["packet_hops"] == lb["packet_hops"]
                pairs.append((delta, a, b))
    if not pairs:
        raise RuntimeError("No same-full-protocol aggregate traffic witness; do not fabricate a pair")
    delta, a, b = sorted(pairs, key=lambda p: (-p[0], p[1], p[2]))[0]
    selected = [a, b]
    same = plans[0]
    other = next(p for p in plans if all(p[k] == same[k] for k in
        ("producers", "consumers", "nocs", "chain1_offset_cycles", "source_wait"))
        and p["placement"] == "same_group_other_channel")
    group = next(p for p in plans if all(p[k] == same[k] for k in
        ("producers", "consumers", "nocs", "chain1_offset_cycles", "source_wait"))
        and p["placement"] == "separate_group")
    ack = next(p for p in plans if all(p[k] == same[k] for k in
        ("producers", "consumers", "nocs", "chain1_offset_cycles", "placement"))
        and p["source_wait"] == "ack")
    selected += [same["id"], other["id"], group["id"], ack["id"]]
    registration = {
        "schema": "r13.micro-preregistration.v1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "frozen after functional qualification and TETRA seed admission; before exhaustive comparative search",
        "source_sha256": before, "candidates": plans, "candidate_sha256": digest(plans),
        "candidate_count": len(plans), "parameter_points": scenarios(), "parameter_point_count": len(scenarios()),
        "payload_bytes": 1024, "epochs": 2, "tie_break": "ascending", "bank_layout": "interleaved",
        "action_space": "4 role mappings x3 input placements x8 shared load/peer/output NoC triples x3 first-chain1 release windows {0,32,64} x2 source guards; fixed1KiB tiling/single slots, shared protocol and arbitration order",
        "excluded_decisions": ["per-transfer/per-epoch NoC", "general event-relative windows",
            "tiling", "extra buffers", "general compute/transfer resource orders", "multicast", "full MLP"],
        "exact_claim": "minimum of all valid candidates in this finite C only; no continuous or architecture-global optimum",
        "evaluation_budget": {"nominal_exact": len(plans), "witness_parameter_replays": len(set(selected))*len(scenarios()),
            "witness_structural_replays": len(set(selected))*2,
            "reported_budget_prefixes": [16,48,96,192,576],
            "algorithm_status": "No P1 novel optimizer or qualified full strong P0 portfolio yet. Exact enumeration is a reference, not an algorithm improvement."},
        "diagnostic_estimators": ["payload_router_byte_hops", "full_protocol_flit_hops", "zero_contention_critical_path"],
        "diagnostic_selection": "minimum(score,lexical plan id) over COMMON F-valid candidates; report whole tied set F range too; all costs reevaluated by F",
        "witnesses": {
            "links": {"plans": [a,b], "selection": "largest difference in cross-chain shared router-flit demand, among same placement and same per-role aggregate full-protocol ledger; lexical tie break; no F timing inspected",
                "eligible_pairs": len(pairs), "equal_per_packet_hops_pairs": strict_packet_equal_pairs,
                "shared_flit_difference": delta, "ledgers": {a: summaries[a], b: summaries[b]},
                "causal_limit": "same full-protocol aggregate flit-hops does not fix each flow latency or every resource load; report isolated DAG estimate and per-packet routes; cannot attribute whole delta solely to link contention"},
            "channels": {"plans": [same["id"],other["id"],group["id"]],
                "causal_limit": "first pair identical endpoints/routes and changes only second-chain input physical channel; third moves endpoint and changes routes too"},
            "reuse": {"plans": [same["id"],ack["id"]],
                "causal_limit": "valid source-observed guard versus ACK guard is oversynchronization diagnostic, never P1 versus strong P0"}},
        "unique_witness_plans": sorted(set(selected)),
        "sensitivity_scope": "frozen witness plans on 26 registered points plus nominal mono-bank and descending tie-break; not a full Cxparameter recompile study",
        "unknown_costs": "registered research scenarios; no confidence intervals or hardware calibration",
        "decision": "M1 Hcompiler needs a separately admitted fair strong portfolio and proposed algorithm; do not open M2 on coarse-model regret alone"
    }
    assert before == hashes(), "Source changed during registration"
    write_new(output, registration)
    print(json.dumps({"registered": str(output), "candidates": len(plans), "parameters": len(scenarios()),
        "link_pair": [a,b], "pair_count": len(pairs), "strict_per_packet_pairs": strict_packet_equal_pairs,
        "witness_plans": registration["unique_witness_plans"]}), flush=True)


def summarize_execution(spec, result, audit, wall):
    data = spec["metadata"]
    timing = {op["id"]: op for op in result["operations"]}
    ok = result["status"] == "ok" and audit["passed"]
    metric = {"output_visible": None, "final_ack": None, "quiescent": result["quiescent"]}
    lifetimes = []
    if ok:
        metric["output_visible"] = max(timing[r["output"]["visible"]]["end"] for r in data["refs"])
        metric["final_ack"] = max(op["end"] for op in result["operations"] if op["id"].endswith("/observed:0"))
        for r in data["refs"]:
            peer, out = r["peer"], r["output"]
            life = {"chain": r["chain"], "epoch": r["epoch"],
                "load_issue_start": timing[r["load"]["issue"]]["start"],
                "peer_source_last_read": timing[peer["source_last_read"]]["end"],
                "peer_source_observed": timing[peer["source_observed"]]["end"],
                "peer_visible": timing[peer["visible"]]["end"],
                "peer_ack": timing[peer["observed"]]["end"],
                "consumer_ready": timing[r["consumer_ready"]]["end"],
                "consumer_last_read": timing[r["consumer"]["last_read"]]["end"],
                "token_observed": timing[r["token_ready"]]["end"],
                "output_source_last_read": timing[out["source_last_read"]]["end"],
                "output_visible": timing[out["visible"]]["end"]}
            lifetimes.append(life)
    totals = Counter()
    class_wait = Counter()
    resource_detail = Counter()
    # Queue residence is exact; shared-resource causal blame is not assigned.
    jobs = {j["id"]: j for j in spec["jobs"]}
    for op in result["operations"]:
        jid, ktext = op["id"].rsplit(":", 1)
        k = int(ktext)
        j = jobs[jid]
        ready = (timing.get(f"{jid}:{k-1}", {}).get("end", 0) if k else
                 max([j.get("release",0)] + [timing[d]["end"] for d in j.get("deps",[]) if d in timing]))
        class_wait[op["queue"].split("/",1)[0]] += max(0, op["start"]-ready)
        for resource, ii in op["resources"].items():
            totals[resource.split("/",1)[0]] += ii
            resource_detail[resource] += ii
    return {"status": "valid" if ok else "rejected", "engine_status": result["status"],
        "model_ticks": metric, "model_cycles": {k: (None if v is None else v/TICKS) for k,v in metric.items()},
        "spec_sha256": digest(spec), "trace_sha256": digest(result), "wall_seconds": wall,
        "operations": len(result["operations"]), "audit_passed": audit["passed"],
        "audit_failures": audit.get("failures", []), "checked_output_blocks": audit.get("checked_output_blocks"),
        "unfinished_job_count": len(result["unfinished_jobs"]),
        "summed_resource_service_ticks": dict(sorted(totals.items())),
        "summed_queue_residence_ticks": dict(sorted(class_wait.items())),
        "max_finite_queue_credit_used": max((v for q,v in result["buffer_peaks"].items() if spec["buffers"][q]["capacity"] is not None),default=0),
        "source_receive_output_events": lifetimes,
        "per_channel_service_ticks": {k:v for k,v in sorted(resource_detail.items()) if k.startswith("dram/")},
        "per_link_service_ticks": {k:v for k,v in sorted(resource_detail.items()) if k.startswith("link/")},
        "l1_reserved_payload_bytes": data["l1_payload_span_bytes"],
        "interpretation": "queue residence can have simultaneous resource/credit causes; not a causal decomposition or latency sum"}


def evaluate(task):
    plan, params, layout, tie, label, detailed = task
    started = time.perf_counter()
    spec = micro_graph(plan, params, bank_layout=layout, tie_break=tie)
    result = simulate(spec)
    audit = audit_trace(spec, result)
    summary = summarize_execution(spec, result, audit, time.perf_counter()-started)
    traffic = ledger(spec)
    summary.update(plan_id=plan["id"], scenario=label, params=params, bank_layout=layout, tie_break=tie,
        estimator_scores={"payload_router_byte_hops": traffic["payload_router_byte_hops"],
            "full_protocol_flit_hops": traffic["full_protocol_flit_hops"],
            "zero_contention_critical_path": isolated_critical_path(spec)})
    if detailed:
        summary["traffic_ledger"] = traffic
    else:
        summary.pop("source_receive_output_events")
        summary.pop("per_link_service_ticks")
    return summary


def rank_summary(rows):
    valid = [r for r in rows if r["status"] == "valid"]
    if not valid:
        return {"exact": None, "rejected": len(rows)}
    best = min(valid, key=lambda r: (r["model_ticks"]["output_visible"], r["plan_id"]))
    optimum = best["model_ticks"]["output_visible"]
    tied_best = [r["plan_id"] for r in valid if r["model_ticks"]["output_visible"] == optimum]
    estimators = {}
    for score in best["estimator_scores"]:
        winner = min(valid, key=lambda r: (r["estimator_scores"][score],r["plan_id"]))
        tied = [r for r in valid if r["estimator_scores"][score] == winner["estimator_scores"][score]]
        times = [r["model_ticks"]["output_visible"] for r in tied]
        estimators[score] = {"chosen_plan": winner["plan_id"], "chosen_output_ticks": winner["model_ticks"]["output_visible"],
            "regret_percent_of_exact": (winner["model_ticks"]["output_visible"]/optimum-1)*100,
            "coarse_tie_count": len(tied), "coarse_tie_best_F_ticks": min(times), "coarse_tie_worst_F_ticks": max(times)}
    # These prefixes describe enumeration coverage only, never a novel search.
    curve = []
    for calls in (16,48,96,192,576):
        prefix = sorted(rows, key=lambda r:r["plan_id"])[:calls]
        legal = [r for r in prefix if r["status"] == "valid"]
        v = min(legal,key=lambda r:(r["model_ticks"]["output_visible"],r["plan_id"])) if legal else None
        curve.append({"calls":len(prefix), "plan":v["plan_id"] if v else None,
            "output_ticks":v["model_ticks"]["output_visible"] if v else None})
    return {"valid":len(valid),"rejected":len(rows)-len(valid),
        "exact": {"plan":best["plan_id"],"output_ticks":optimum,"cycles":optimum/TICKS,"all_tied_plans":tied_best,
            "final_ack_ticks":best["model_ticks"]["final_ack"],"quiescent_ticks":best["model_ticks"]["quiescent"]},
        "diagnostic_estimators":estimators, "lexical_enumeration_prefixes":curve,
        "Hcompiler": "not tested; no claimed P1 or complete strong P0 portfolio; exact alone cannot establish algorithm novelty"}


def run(args):
    registration = json.loads(args.registration.read_text(encoding="utf-8"))
    before = hashes()
    if before != registration["source_sha256"]:
        raise RuntimeError("Registered sources changed. Freeze a new registration and preserve prior results.")
    plans = registration["candidates"]
    by_id = {p["id"]: p for p in plans}
    tasks = []
    if args.mode == "nominal":
        tasks = [(p,HARDWARE["nominal"],"interleaved","ascending","nominal",False) for p in plans]
    else:
        for index, params in enumerate(registration["parameter_points"]):
            tasks += [(by_id[pid],params,"interleaved","ascending",f"parameter_{index:02}",True)
                      for pid in registration["unique_witness_plans"]]
        for layout,tie,label in (("mono","ascending","mono_nominal"),("interleaved","descending","descending_nominal")):
            tasks += [(by_id[pid],HARDWARE["nominal"],layout,tie,label,True) for pid in registration["unique_witness_plans"]]
    started = time.perf_counter()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():
        raise FileExistsError(args.output)
    rows = []
    for task in tasks:
        rows.append(evaluate(task))
        if len(rows) % 24 == 0 or len(rows) == len(tasks):
            print(json.dumps({"completed":len(rows),"total":len(tasks),
                "valid":sum(r["status"]=="valid" for r in rows),
                "wall_seconds":round(time.perf_counter()-started,2)}),flush=True)
    expected_keys = {(t[0]["id"],t[4]) for t in tasks}
    assert len(rows) == len(tasks) == len(expected_keys)
    assert {(r["plan_id"],r["scenario"]) for r in rows} == expected_keys
    assert digest(plans) == registration["candidate_sha256"]
    rows.sort(key=lambda r:(r["scenario"],r["plan_id"]))
    after = hashes()
    if before != after:
        raise RuntimeError("Source changed during experiment; do not publish timing as frozen-source evidence")
    receipt = {"schema":"r13.micro-experiment.v1","mode":args.mode,
        "created_utc":datetime.now(timezone.utc).isoformat(),"source_sha256":before,
        "source_hash_stable":before==after,"registration_sha256":hashlib.sha256(args.registration.read_bytes()).hexdigest(),
        "evaluations":len(rows),"workers":args.workers,"wall_seconds":time.perf_counter()-started,
        "rows":rows,"summary":rank_summary(rows) if args.mode=="nominal" else None,
        "scope":"modeled micrograph only; no board or complete MLP performance"}
    write_new(args.output,receipt)
    print(json.dumps({"saved":str(args.output),"summary":receipt["summary"]}),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("register","nominal","witnesses"))
    parser.add_argument("--registration",type=Path,default=ROOT/"preregistration_serial.json")
    parser.add_argument("--output",type=Path)
    parser.add_argument("--workers",type=int,choices=(1,),default=1)
    args = parser.parse_args()
    if args.mode == "register":
        register(args.output or args.registration)
    else:
        args.output = args.output or ROOT/"artifacts"/f"micro_{args.mode}.json"
        run(args)
