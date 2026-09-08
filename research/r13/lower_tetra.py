"""Lower a real TETRA micro candidate's placements and ordering into R13 F.

Two interpretations are explicit: global whole-slot barriers, and source-aware
resource-order constraints. Neither uses upstream analytical cycles as F time.
The latter preserves every selected shared-resource transfer order and compute
order; it does not preserve global barriers between disjoint resources.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from graphlib import CycleError, TopologicalSorter
import gzip
import hashlib
import json
from pathlib import Path
import time

from event_machine import simulate
from independent_checker import audit_builder_rules
from model_builder import HARDWARE, micro_graph
from trace_audit import audit_trace, digest_json

HERE = Path(__file__).resolve().parent


def require(value, message):
    if not value:
        raise ValueError(message)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding_core(blocks):
    head = blocks[0].split("/")
    require(all(b.split("/")[:-1] == head[:-1] for b in blocks), "cross-domain tensor span")
    if head[0] == "dram":
        return 4 + int(head[1])*2 + int(head[2])
    coord = [int(x) for x in head[1].split(",")]
    return HARDWARE["active_tiles_4"].index(coord)


def source_intake(record, spec):
    require(record["passed"] and record["physical_input_checks"]["passed"], "target candidate export failed")
    require(len(record["groups"]) == 1, "one group only")
    group = record["groups"][0]
    require(len(group["allocators"]) == 1, "one allocator only")
    allocator = group["allocators"][0]
    selected = allocator["selected"]
    placement = {x["tensor_id"]: [c["core_id"] for c in x["cores"]] for x in selected["tensor_allocations"]}
    depth = {x["tensor_id"]: x["depth"] for x in selected["tensor_depths"]}
    require(all(v == 1 for v in depth.values()), "this lowering implements selected depth1 only")
    require(all(x["stop_level"] == -1 or isinstance(x["stop_level"], int) for x in selected["tensor_reuse_levels"]), "invalid reuse level")
    selected_paths = {x["transfer_id"]: x["path"] for x in selected["transfer_allocations"]}
    slots = {x["node_id"]: x["slot"] for x in allocator["slot_of"]}
    nodes = {n["id"]: n for n in allocator["workload"]["nodes"]}
    by_name = {n["name"]: n for n in nodes.values()}
    ledger = {x["transaction"]: x for x in record["physical_payloads"]}
    packets = {p["id"]: p for p in spec["metadata"]["packets"]}
    tensor_spans = {}
    executable = {}

    def assign(tid, blocks):
        require(placement[tid] == [binding_core(blocks)], f"selected tensor placement mismatch {tid}")
        require(depth[tid] == 1, f"unsupported selected depth {tid}")
        require(tid not in tensor_spans or tensor_spans[tid] == blocks, f"inconsistent span for {tid}")
        tensor_spans[tid] = blocks

    for transaction, item in ledger.items():
        node = by_name[item["transfer"]]
        path = selected_paths[node["id"]]
        require(path["id"] == item["path_id"], f"unselected payload path {transaction}")
        packet_id = transaction + ("/response" if item["role"] == "load" else "/data")
        packet = packets[packet_id]
        for key in ("src", "dst", "noc", "payload_bytes"):
            require(packet[key] == item[key], f"F payload differs {transaction} {key}")
        require(packet["links"] == item["ordered_payload_links"], f"F route differs {transaction}")
        tags = spec["metadata"]["tags"]
        src = [b for op in packet["read_ops"] for b in tags[op]["blocks"]]
        dst = [b for op in packet["write_ops"] for b in tags[op]["blocks"]]
        require(src == item["source_blocks"] and dst == item["target_blocks"], f"F blocks differ {transaction}")
        require(len(node["inputs"]) == len(node["outputs"]) == 1, "unicast unary transfer only")
        assign(node["inputs"][0]["id"], src)
        assign(node["outputs"][0]["id"], dst)
        require([c["core_id"] for c in path["sources"]] == [binding_core(src)], "selected path source differs")
        require([c["core_id"] for c in path["targets"]] == [binding_core(dst)], "selected path target differs")
        executable[node["id"]] = {"node": node["name"], "kind": "transfer", "slot": slots[node["id"]],
            "entries": [transaction+"/issue"], "terminal": spec["metadata"]["events"][transaction+"/observed"],
            "transaction": transaction, "packet": packet_id, "resources": item["allocator_resource_names"]}
    compute_mapping = {x["node_name"]: x for x in group["mapping_after_schedule"]["nodes"]}
    for node in nodes.values():
        if node["type"] != "ComputationNode":
            continue
        require(node["operator"] in ("R13TimesTwo", "R13PlusThree"), "unknown source arithmetic")
        name = node["name"]
        assignment = compute_mapping[name]["resource_allocation"]
        require(len(assignment) == 1 and len(assignment[0]["cores"]) == 1, "fixed single core required")
        core = assignment[0]["cores"][0]
        stem, role = name.split("/")
        source = ledger[stem+("/load" if role == "producer" else "/peer")]["target_blocks"]
        target = ledger[stem+("/peer" if role == "producer" else "/output")]["source_blocks"]
        assign(node["inputs"][0]["id"], source)
        assign(node["outputs"][0]["id"], target)
        require(core["core_id"] == binding_core(source) == binding_core(target), "compute moved from selected core")
        entries = sorted(j["id"] for j in spec["jobs"] if j["id"].startswith(name+"/read"))
        require(len(entries) == 32, "expected32 pairwise local reads")
        executable[node["id"]] = {"node": name, "kind": "compute", "slot": slots[node["id"]],
            "entries": entries, "terminal": spec["metadata"]["events"][name+"/published"],
            "core_id": core["core_id"]}
    require(len(ledger) == 12 and len(executable) == 20, "not the complete two-chain/two-generation seed")
    require(set(tensor_spans) == set(depth), "some selected tensor/depth has not been lowered")
    logical_bits = {x["tensor"]["id"]: x["tensor"]["footprint_bits"] for x in allocator["tensor_choices"]}
    for tid, blocks in tensor_spans.items():
        require(len(blocks)*128 == logical_bits[tid], f"tensor footprint changed {tid}")
    return executable, {"selected_tensor_views": len(tensor_spans), "selected_depths": depth,
        "selected_reuse_stop_levels": selected["tensor_reuse_levels"],
        "tensor_address_views": tensor_spans,
        "alias_policy": "distinct logical tensor views may share a registered span only under F read/write and cross-generation guards; no extra physical slot is allocated"}


def lower(record, mode):
    spec = micro_graph(record["plan"])
    executable, intake = source_intake(record, spec)
    jobs = {j["id"]: j for j in spec["jobs"]}
    obligations = []

    def add(before, after, reason):
        for entry in after["entries"]:
            for dep in before:
                if dep not in jobs[entry]["deps"]:
                    jobs[entry]["deps"].append(dep)
                obligations.append({"predecessor_operation": dep, "successor_job": entry, "reason": reason})

    if mode == "whole_slot":
        buckets = defaultdict(list)
        for node in executable.values():
            buckets[node["slot"]].append(node)
        prior = []
        for slot in sorted(buckets):
            for node in buckets[slot]:
                add([n["terminal"] for n in prior], node, f"all prior whole slots before slot{slot}")
            prior += buckets[slot]
    elif mode == "resource_order":
        per_core = defaultdict(list)
        per_resource = defaultdict(list)
        for node in executable.values():
            if node["kind"] == "compute":
                per_core[node["core_id"]].append(node)
            else:
                for resource in node["resources"]:
                    per_resource[resource].append(node)
        for core, users in per_core.items():
            users.sort(key=lambda n: (n["slot"], n["node"]))
            for before, after in zip(users, users[1:]):
                require(before["slot"] < after["slot"], "same-slot compute conflict in original candidate")
                add([before["terminal"]], after, f"selected compute core{core} order")
        for resource, users in per_resource.items():
            users.sort(key=lambda n: (n["slot"], n["node"]))
            for before, after in zip(users, users[1:]):
                require(before["slot"] < after["slot"], "same-slot transfer resource conflict in original candidate")
                drains = [f"{job['id']}:{i}" for job in spec["jobs"] if job["packet"] == before["packet"]
                          for i, operation in enumerate(job["ops"]) if resource in operation["resources"]]
                require(drains, f"selected resource absent from F {resource}")
                add(drains, after, f"selected transfer resource order {resource}")
    else:
        raise ValueError(mode)
    cycle = None
    dependencies = {j["id"]: {dep.rsplit(":", 1)[0] for dep in j["deps"]} for j in spec["jobs"]}
    try:
        tuple(TopologicalSorter(dependencies).static_order())
    except CycleError as error:
        cycle = error.args[1]
    info = {"mode": mode, "executable_nodes": list(executable.values()), "intake": intake,
        "added_order_obligations": obligations, "dependency_cycle": cycle,
        "whole_slot_barriers_preserved": mode == "whole_slot",
        "preserved_in_resource_order_mode": ["selected computation/tensor/path placement", "selected depth1 tensor views", "compute order on each selected core", "transfer order on each selected physical shared resource"],
        "not_preserved_in_resource_order_mode": ["global barriers between disjoint resources", "upstream analytical timestamps"],
        "lowering_added_F_steps": ["paid command issue and actual requests/responses/ACK", "per16B source reads and target visibility", "paid notifications and explicit epoch observations", "receiver token return after last consumer read", "source/receive/output address reuse guards", "finite router/NIU credits and bank/port service", "full output-visible/final-ACK/quiescent accounting"],
        "time_conversion": "all constraints are event-completion anchors; F uses36ticks/cycle; no upstream cycle value converted into a release time"}
    spec["metadata"]["tetra_lowering"] = {k: v for k, v in info.items() if k not in ("intake", "added_order_obligations")}
    return spec, info


def run_mode(record, mode, artifact_dir):
    started = time.perf_counter()
    spec, info = lower(record, mode)
    execution = simulate(spec)
    audit = audit_trace(spec, execution)
    builder_audit = audit_builder_rules(spec, HARDWARE)
    timings = {x["id"]: x for x in execution["operations"]}
    order_failures = [edge for edge in info["added_order_obligations"]
        if edge["predecessor_operation"] not in timings or edge["successor_job"]+":0" not in timings
        or timings[edge["predecessor_operation"]]["end"] > timings[edge["successor_job"]+":0"]["start"]]
    admitted = not info["dependency_cycle"] and execution["status"] == "ok" and audit["passed"] and builder_audit["passed"] and not order_failures
    result = {"mode": mode, "bounded_seed_admitted": admitted,
        "status": "admitted" if admitted else "rejected", "lowering": info,
        "execution_status": execution["status"], "trace_audit": audit, "builder_rules_audit": builder_audit,
        "order_obligations_checked": len(info["added_order_obligations"]), "order_failure_count": len(order_failures),
        "order_failures": order_failures[:10], "wall_seconds": time.perf_counter()-started,
        "spec_sha256": digest_json(spec), "trace_sha256": digest_json(execution)}
    if admitted:
        events = spec["metadata"]["events"]
        result["modeled_ticks"] = {
            "output_visible": max(timings[ref["output"]["visible"]]["end"] for ref in spec["metadata"]["refs"]),
            "final_ack": max(timings[op]["end"] for name,op in events.items() if name.endswith("/observed")),
            "quiescent": execution["quiescent"],
        }
        result["modeled_cycles"] = {k:v/HARDWARE["ticks_per_cycle"] for k,v in result["modeled_ticks"].items()}
    else:
        result["rejection"] = "original global slots conflict with finite-span cross-generation reuse" if info["dependency_cycle"] else "execution or independent audit failed"
    for kind, value in (("spec", spec), ("trace", execution)):
        path=artifact_dir / f"tetra_lower_{mode}_{kind}.json.gz"
        with gzip.GzipFile(filename=str(path),mode="wb",mtime=0) as stream:
            stream.write(json.dumps(value,sort_keys=True,separators=(",",":" )).encode())
        result[kind+"_file"] = path.name
        result[kind+"_file_sha256"] = file_hash(path)
    return result


def main():
    path=HERE/"artifacts/tetra_micro_p0000_target.json"
    record=json.loads(path.read_text(encoding="utf-8"))
    output={"schema":"r13.tetra-to-F-seed-admission.v1", "source_candidate":path.name,
        "source_sha256":file_hash(path), "producer_sha256":file_hash(Path(__file__)),
        "source_files":{p:file_hash(HERE/p) for p in ("model_builder.py","event_machine.py","trace_audit.py","independent_checker.py","hardware_model.json")},
        "p0_portfolio_qualified":False, "new_algorithm_benefit_claimed":False,
        "methods":[]}
    for mode in ("whole_slot","resource_order"):
        result=run_mode(record,mode,path.parent)
        output["methods"].append(result)
        print(json.dumps({"mode":mode,"status":result["status"],"cycle":result["lowering"]["dependency_cycle"],
            "modeled_cycles":result.get("modeled_cycles"),"trace_audit_passed":result["trace_audit"]["passed"]},ensure_ascii=False),flush=True)
    (path.parent/"tetra_lower_receipt.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return 0 if output["methods"][1]["bounded_seed_admitted"] else 1


if __name__=="__main__":
    raise SystemExit(main())
