"""Independent 16-byte value, epoch and lifetime audit of the named R13 micro DFG.

The auditor consumes a pure-data graph and an execution trace. It does not call
the builder's audit_values, the DES, or the tick checker. The command-line
qualification generates traces externally and then mutates values/times to
exercise rejection. This is a 16B block contract, not arbitrary byte masking.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import time


HERE = Path(__file__).resolve().parent


def digest_json(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def audit_trace(spec: dict, execution: dict) -> dict:
    """Audit this model's two-chain micro contract; do not infer generic DFG proof."""
    faults = []

    def check(condition, code, **details):
        if not condition:
            faults.append({"code": code, **details})
        return condition

    metadata = spec.get("metadata", {})
    tags = metadata.get("tags", {})
    jobs = {job["id"]: job for job in spec.get("jobs", [])}
    declared = {f"{jid}:{index}": op for jid, job in jobs.items() for index, op in enumerate(job["ops"])}
    observed = execution.get("operations", [])
    timings = {op["id"]: op for op in observed}
    check(execution.get("status") == "ok", "execution_not_complete")
    check(len(timings) == len(observed), "duplicate_trace_operation")
    check(set(timings) == set(declared), "operation_coverage", missing=sorted(set(declared)-set(timings))[:10], extra=sorted(set(timings)-set(declared))[:10])
    if set(timings) != set(declared):
        return {"passed": False, "failures": faults, "scope": "Incomplete trace cannot prove value or lifetime semantics"}
    for oid, op in declared.items():
        trace = timings[oid]
        check(isinstance(trace["start"], int) and isinstance(trace["end"], int) and trace["start"] >= 0, "invalid_time", op=oid)
        check(trace["end"]-trace["start"] == op["latency"], "operation_latency_mismatch", op=oid)
        check(trace.get("resources") == op.get("resources", {}) and trace["queue"] == op["queue"], "trace_spec_resource_mismatch", op=oid)
    for jid, job in jobs.items():
        first = timings[f"{jid}:0"]
        check(first["start"] >= job.get("release", 0), "early_release", job=jid)
        for dep in job.get("deps", []):
            check(dep in timings and first["start"] >= timings[dep]["end"], "dependency_time_violation", job=jid, dependency=dep)
        for index in range(1, len(job["ops"])):
            check(timings[f"{jid}:{index}"]["start"] >= timings[f"{jid}:{index-1}"]["end"], "flit_stage_overlap", job=jid, stage=index)

    params = metadata["params"]
    hardware = json.loads((HERE / "hardware_model.json").read_text(encoding="utf-8"))
    tick = hardware["ticks_per_cycle"]
    # Derive block completion offsets independently from the registered service
    # equations, not from any helper function in model_builder.
    memory_kinds = {"read", "write", "compute_write", "observe"}
    block_events = []
    intervals = defaultdict(list)
    offsets_for = {}
    for oid, tag in tags.items():
        if not check(oid in timings, "tag_without_operation", op=oid):
            continue
        if tag["kind"] not in memory_kinds:
            continue
        blocks = tag["blocks"]
        check(len(blocks) == len(set(blocks)) and bool(blocks), "duplicate_or_empty_block_access", op=oid)
        offsets = tag.get("block_completion_ticks")
        if not check(isinstance(offsets, list) and len(offsets) == len(blocks), "missing_individual_16B_completion", op=oid):
            continue
        domains = {"/".join(block.split("/")[:-1]) for block in blocks}
        check(len(domains) == 1, "cross_domain_memory_operation", op=oid)
        if blocks[0].startswith("dram/"):
            quantum = Fraction(16*tick, 1) / (24*Fraction(str(params["eta_d"])))
            predicted = [quantum*(i+1) for i in range(len(blocks))]
            check(declared[oid]["resources"] == {next(iter(domains)): quantum*len(blocks)}, "dram_block_service_resource_mismatch", op=oid)
        else:
            port_names = [key for key in declared[oid]["resources"] if key.startswith("l1_port/")]
            check(len(port_names) == 1, "missing_or_multiple_l1_interfaces", op=oid)
            port = port_names[0] if port_names else ""
            local = "/local/" in port
            quantum = Fraction(tick, 1) / (1 if local else Fraction(str(params["eta_n"])))
            counts = Counter()
            predicted = []
            for block in blocks:
                bank = 0 if metadata["bank_layout"] == "mono" else int(block.rsplit("/", 1)[1]) % 16
                counts[bank] += 1
                predicted.append(counts[bank]*quantum)
            tile = blocks[0].split("/")[1]
            direction = "write" if tag["kind"] in {"write", "compute_write"} else "read"
            valid_ports = {f"l1_port/{tile}/{interface}/{direction}" for interface in ("local", "noc0", "noc1")}
            check(port in valid_ports, "wrong_l1_interface_owner_or_direction", op=oid)
            expected_resources = {f"bank/{tile}/{bank}": n*quantum for bank, n in counts.items()}
            expected_resources[port] = quantum
            check(declared[oid]["resources"] == expected_resources, "l1_block_service_resource_mismatch", op=oid)
        check(all(value.denominator == 1 for value in predicted), "unrepresentable_block_service", op=oid)
        check(offsets == predicted, "block_completion_formula_mismatch", op=oid, actual=offsets, expected=[str(v) for v in predicted])
        check(max(offsets) == declared[oid]["latency"], "last_block_not_operation_completion", op=oid)
        offsets_for[oid] = offsets
        for index, (block, offset) in enumerate(zip(blocks, offsets, strict=True)):
            end = timings[oid]["start"] + offset
            begin = end - quantum
            check(isinstance(offset, int) and offset > 0 and end <= timings[oid]["end"], "invalid_block_completion", op=oid, index=index)
            intervals[block].append({"start": begin, "end": end, "op": oid, "write": tag["kind"] in {"write", "compute_write"}})
            block_events.append((end, oid, index))
    for block, accesses in intervals.items():
        ordered = sorted(accesses, key=lambda record: (record["start"], record["end"], record["op"]))
        active = []
        for access in ordered:
            active = [prior for prior in active if prior["end"] > access["start"]]
            for prior in active:
                check(not (prior["write"] or access["write"]), "overlapping_block_read_write", block=block, prior=prior["op"], current=access["op"])
            active.append(access)

    packets = {packet["id"]: packet for packet in metadata["packets"]}
    refs = sorted(metadata["refs"], key=lambda ref: (ref["chain"], ref["epoch"]))
    count = metadata["payload_bytes"] // 16
    check(metadata["payload_bytes"] % 16 == 0, "nonblock_payload")
    check({ref["chain"] for ref in refs} == {0, 1}, "not_two_chain_fixture")
    check(len({(r["chain"], r["epoch"]) for r in refs}) == len(refs), "duplicate_epoch_reference")
    initial = metadata["memory_initial"]
    expected_memory = {}
    expected_reads = {}
    expected_writes = {}
    expected_control = {}
    all_role_spans = {}
    initial_identity = {}
    protocol_records = []
    reuse_records = []

    def flatten(ops):
        return [block for oid in ops for block in tags[oid]["blocks"]]

    def role_ops(stem, role, kind):
        return sorted(oid for oid, tag in tags.items() if oid.startswith(stem+"/"+role+"/") and tag["kind"] == kind)

    def transaction_times(stem, role, packet_id):
        prefix = stem+"/"+role
        events = metadata["events"]
        p = packets[packet_id]
        data_operations = [timings[f"{jid}:{len(job['ops'])-1}"]["end"] for jid, job in jobs.items() if job["packet"] == packet_id]
        visible = timings[events[prefix+"/visible"]]
        last_read = timings[events[prefix+"/source_last_read"]]
        observed_ack = timings[events[prefix+"/observed"]]
        read_complete = max((timings[oid]["start"] + max(offsets_for.get(oid, [0])) for oid in p["read_ops"]), default=timings[events[prefix+"/issue"]]["end"])
        check(visible["start"] >= max(data_operations), "visible_before_all_packet_delivery", transaction=prefix)
        check(last_read["start"] >= read_complete, "source_release_before_last_actual_read", transaction=prefix)
        if role == "load":
            request = packets[prefix+"/request"]
            check(request["src"] == p["dst"] and request["dst"] == p["src"] and request["noc"] == p["noc"], "read_response_request_mismatch", transaction=prefix)
            check(observed_ack["start"] >= visible["end"], "read_observed_before_visibility", transaction=prefix)
        else:
            ack_packet = packets[prefix+"/ack"]
            check(ack_packet["src"] == p["dst"] and ack_packet["dst"] == p["src"] and ack_packet["noc"] == p["noc"], "ack_packet_mismatch", transaction=prefix)
            ack_arrival = max(timings[f"{jid}:{len(job['ops'])-1}"]["end"] for jid, job in jobs.items() if job["packet"] == ack_packet["id"])
            check(timings[prefix+"/ack/prepare:0"]["start"] >= visible["end"], "ack_before_target_visibility", transaction=prefix)
            check(observed_ack["start"] >= ack_arrival, "ack_observed_before_arrival", transaction=prefix)
        protocol_records.append({"transaction": prefix, "last_actual_source_read": read_complete, "source_release": last_read["end"], "target_visible": visible["end"], "ack_observed": observed_ack["end"]})

    for ref in refs:
        chain, epoch = ref["chain"], ref["epoch"]
        stem = f"c{chain}e{epoch}"
        load = packets[stem+"/load/response"]
        peer = packets[stem+"/peer/data"]
        output = packets[stem+"/output/data"]
        src = flatten(load["write_ops"])
        receive = flatten(peer["write_ops"])
        result = flatten(role_ops(stem, "consumer", "compute_write"))
        dram_input = flatten(load["read_ops"])
        dram_output = flatten(output["write_ops"])
        spans = {"src": src, "receive": receive, "result": result, "input": dram_input, "output": dram_output}
        for name, blocks in spans.items():
            check(len(blocks) == len(set(blocks)) == count, "role_coverage", role=stem+"/"+name)
        all_role_spans[(chain, epoch)] = spans
        check(not (set(src)&set(receive) or set(src)&set(result) or set(receive)&set(result)), "src_receive_result_alias", chain=chain, epoch=epoch)
        values = [(chain+1)*1_000_000+epoch*10_000+i for i in range(count)]
        for index, block in enumerate(dram_input):
            check(initial.get(block) == values[index], "initial_epoch_or_block_value", chain=chain, epoch=epoch, index=index)
            initial_identity[block] = (chain, epoch, index, "input")
        final = [2*v+3 for v in values]
        expected_memory.update(zip(dram_output, final))
        for role, opids, block_order, stage_values, stage in (
            ("load", load["read_ops"], dram_input, values, "input"),
            ("producer", role_ops(stem, "producer", "read"), src, values, "input"),
            ("peer", peer["read_ops"], src, [2*v for v in values], "times2"),
            ("consumer", role_ops(stem, "consumer", "read"), receive, [2*v for v in values], "times2"),
            ("output", output["read_ops"], result, final, "plus3"),
        ):
            check(flatten(opids) == block_order, "reader_span_or_order_mismatch", role=stem+"/"+role)
            identity_by_block = {block: (value, (chain, epoch, i, stage)) for i, (block, value) in enumerate(zip(block_order, stage_values, strict=True))}
            for oid in opids:
                for index, block in enumerate(tags[oid]["blocks"]):
                    if block in identity_by_block:
                        expected_reads[(oid, index)] = identity_by_block[block]
        for role, opids, stage_values, stage in (
            ("load", load["write_ops"], values, "input"),
            ("producer", role_ops(stem, "producer", "compute_write"), [2*v for v in values], "times2"),
            ("peer", peer["write_ops"], [2*v for v in values], "times2"),
            ("consumer", role_ops(stem, "consumer", "compute_write"), final, "plus3"),
            ("output", output["write_ops"], final, "plus3"),
        ):
            i = 0
            for oid in opids:
                for index in range(len(tags[oid]["blocks"])):
                    if i < count:
                        expected_writes[(oid, index)] = (stage_values[i], (chain, epoch, i, stage))
                    i += 1
            check(i == count, "writer_span_coverage", role=stem+"/"+role)
        for role, ready in (("notify", "consumer_ready"), ("token", "token_ready")):
            packet = packets[stem+"/"+role+"/data"]
            control_blocks = flatten(packet["write_ops"])
            observe_ops = role_ops(stem, ready, "observe")
            check(len(control_blocks) == 1 and flatten(observe_ops) == control_blocks, "control_observe_address_mismatch", role=stem+"/"+role)
            for oid in observe_ops:
                check(tags[oid]["expected_epoch"] == epoch, "control_expected_epoch_corrupt", op=oid)
                for index in range(len(tags[oid]["blocks"])):
                    expected_control[(oid, index)] = (epoch, (chain, epoch, 0, role))
            for oid in packet["write_ops"]:
                check(tags[oid].get("immediate") == epoch, "stale_control_payload", op=oid)
                for index in range(len(tags[oid]["blocks"])):
                    expected_writes[(oid, index)] = (epoch, (chain, epoch, 0, role))
            observation_end = max((timings[oid]["end"] for oid in observe_ops), default=0)
            ready_trace = timings[ref[ready]]
            check(ready_trace["start"] >= observation_end, "ready_before_control_observation", role=stem+"/"+role)
        check(timings[ref["consumer_ready"]]["end"] >= timings[ref["peer"]["visible"]]["end"], "consumer_ready_before_payload_visible", chain=chain, epoch=epoch)
        for role, pid in (("load", stem+"/load/response"), ("peer", stem+"/peer/data"), ("notify", stem+"/notify/data"), ("token", stem+"/token/data"), ("output", stem+"/output/data")):
            transaction_times(stem, role, pid)
    check(expected_memory == metadata["memory_expected"], "metadata_final_expectation_not_source_algebra")
    for role in ("input", "output"):
        role_blocks = [block for spans in all_role_spans.values() for block in spans[role]]
        check(len(role_blocks) == len(set(role_blocks)), "cross_epoch_or_chain_dram_alias", role=role)
    for role in ("src", "receive", "result"):
        chain0 = set(all_role_spans[(0, 0)][role])
        chain1 = set(all_role_spans[(1, 0)][role])
        check(not chain0 & chain1, "cross_chain_l1_slot_alias", role=role)

    by_ref = {(ref["chain"], ref["epoch"]): ref for ref in refs}
    for ref in refs:
        chain, epoch = ref["chain"], ref["epoch"]
        if epoch == 0:
            continue
        previous = by_ref.get((chain, epoch-1))
        if not check(previous is not None, "nonconsecutive_epochs", chain=chain, epoch=epoch):
            continue
        for role in ("src", "receive", "result"):
            check(all_role_spans[(chain, epoch)][role] == all_role_spans[(chain, epoch-1)][role], "unregistered_cross_epoch_slot_change", chain=chain, role=role)
        guards = (
            ("source", timings[ref["load"]["issue"]]["start"], timings[previous["peer"]["source_observed"]]["end"]),
            ("receive", timings[ref["peer"]["issue"]]["start"], timings[previous["token_ready"]]["end"]),
            ("result", min(timings[oid]["start"] for oid in role_ops(f"c{chain}e{epoch}", "consumer", "compute_write")), timings[previous["output"]["source_observed"]]["end"]),
        )
        for role, reuse, release in guards:
            check(reuse >= release, "early_"+role+"_reuse", chain=chain, epoch=epoch, reuse_start=reuse, release_observed=release)
            reuse_records.append({"chain": chain, "epoch": epoch, "role": role, "reuse_start": reuse, "release_observed": release})

    # Values include a provenance identity so the same scalar cannot hide a
    # stale epoch/block or notification accidentally coming from another chain.
    memory = {block: (value, initial_identity.get(block)) for block, value in initial.items()}
    captured = {}
    calculations = {}
    timeline = []
    reads = writes = controls = 0
    events = [(t, oid, index, "block") for t, oid, index in block_events]
    events += [(timings[oid]["end"], oid, -1, "compute") for oid, tag in tags.items() if tag["kind"] == "compute"]
    for timestamp, oid, index, category in sorted(events):
        tag = tags[oid]
        if category == "compute":
            data = [v for key in tag["inputs"] for v in captured.get(key, [])]
            check(len(data) == count and all(v is not None for v in data), "compute_incomplete_inputs", op=oid)
            if len(data) != count or any(v is None for v in data):
                continue
            transform = tag["transform"]
            check(transform in {"times2", "plus3"}, "unknown_transform", op=oid)
            values = []
            for value, identity in data:
                if identity is None:
                    values.append((None, None))
                    continue
                chain, epoch, logical_index, stage = identity
                check(stage == ("input" if transform == "times2" else "times2"), "compute_stage_identity", op=oid)
                values.append((2*value if transform == "times2" else value+3, (chain, epoch, logical_index, transform)))
            calculations[tag["output"]] = values
            continue
        block = tag["blocks"][index]
        kind = tag["kind"]
        if kind == "read":
            actual = memory.get(block, (None, None))
            expected = expected_reads.get((oid, index))
            check(expected is not None and actual == expected, "read_value_or_identity", op=oid, block=block, expected=expected, actual=actual)
            captured.setdefault(tag["value_key"], [None]*len(tag["blocks"]))[index] = actual
            reads += 1
        elif kind == "observe":
            actual = memory.get(block, (None, None))
            expected = expected_control.get((oid, index))
            check(expected is not None and actual == expected, "observed_control_value_or_identity", op=oid, expected=expected, actual=actual)
            controls += 1
        else:
            expected = expected_writes.get((oid, index))
            if kind == "write" and tag.get("immediate") is not None:
                actual = (tag["immediate"], None if expected is None else expected[1])
            elif kind == "write":
                data = captured.get(tag["value_key"], [])
                actual = data[index] if index < len(data) else (None, None)
            else:
                data = calculations.get(tag["value_key"], [])
                position = tag["offset"]+index
                actual = data[position] if position < len(data) else (None, None)
            check(expected is not None and actual == expected, "written_value_or_identity", op=oid, block=block, expected=expected, actual=actual)
            memory[block] = actual
            writes += 1
        timeline.append((timestamp, oid, index, block, memory.get(block)))
    for block, expected in expected_memory.items():
        check(memory.get(block, (None, None))[0] == expected, "final_output_value", block=block, expected=expected, actual=memory.get(block))
    check(len(expected_reads) == reads, "data_read_event_coverage", expected=len(expected_reads), actual=reads)
    check(len(expected_writes) == writes, "data_write_event_coverage", expected=len(expected_writes), actual=writes)
    check(len(expected_control) == controls == len(refs)*2, "control_observation_event_coverage", expected=len(refs)*2, actual=controls)
    return {
        "schema": "r13.independent-trace-audit.v1", "passed": not faults,
        "checked_output_blocks": len(expected_memory), "data_read_16B_blocks": reads,
        "written_16B_blocks_including_controls": writes, "observed_control_16B_blocks": controls,
        "individual_memory_completion_events": len(block_events), "all_declared_operation_times_checked": len(declared),
        "block_timeline_sha256": digest_json(timeline), "protocol_boundaries": protocol_records,
        "reuse_guards": reuse_records, "failure_count": len(faults), "failures": faults[:30],
        "verified_scope": "Named two-chain integer micro DFG: each16B data block contains four identical32-bit words; notification immediate32 replicates its epoch into the four words; distinct blocks and epochs retain distinct identities",
        "not_verified": ["arbitrary per-byte masks or sub16B tearing", "full MLP floating point execution or performance", "physical chip memory ordering beyond this registered model", "router/credit liveness and resource-capacity correctness (separate checker)", "all possible interleavings not present in the supplied traces", "physical RF allocation or vendor instruction lowering"],
    }


def qualify() -> dict:
    # The generator/executor provide test inputs only. audit_trace above has no
    # dependency on either, and no call to the builder's functional audit.
    from event_machine import simulate
    from model_builder import micro_graph, small_plan_space

    start = time.perf_counter()
    plans = small_plan_space()
    positives = []
    saved = None
    for layout, plan_index in (("interleaved", 0), ("mono", 0), ("interleaved", 287), ("mono", len(plans)-1)):
        spec = micro_graph(plans[plan_index], payload_bytes=1024, generations=2, bank_layout=layout)
        execution = simulate(spec)
        result = audit_trace(spec, execution)
        if not result["passed"]:
            raise ValueError(json.dumps({"positive_rejected": {"layout": layout, "plan": plan_index}, "audit": result}, ensure_ascii=False))
        positives.append({"bank_layout": layout, "plan_index": plan_index, "spec_sha256": digest_json(spec), "trace_sha256": digest_json(execution), "audit": result})
        if layout == "mono" and plan_index == 0:
            saved = (spec, execution)
    base_spec, base_trace = saved
    negatives = []

    def mutate(name, function):
        graph, trace = deepcopy(base_spec), deepcopy(base_trace)
        function(graph, trace)
        outcome = audit_trace(graph, trace)
        if outcome["passed"]:
            raise ValueError("Illegal mutant accepted: "+name)
        negatives.append({"name": name, "rejected": True, "failure_count": outcome.get("failure_count", len(outcome["failures"])), "failure_codes": sorted({f["code"] for f in outcome["failures"]}), "first_failures": outcome["failures"][:3]})

    def stale_control(graph, trace, role):
        tag = next(t for oid, t in graph["metadata"]["tags"].items() if oid.startswith("c0e1/"+role+"/data/") and t["kind"] == "write")
        tag["immediate"] = 0

    mutate("stale_notification_epoch", lambda g, t: stale_control(g, t, "notify"))
    mutate("stale_receive_token_epoch", lambda g, t: stale_control(g, t, "token"))

    def swap_peer_blocks(graph, trace):
        tag = next(t for oid, t in graph["metadata"]["tags"].items() if oid.startswith("c0e0/peer/data/") and t["kind"] == "read" and len(t["blocks"]) == 2)
        tag["blocks"].reverse()

    mutate("different_16B_blocks_swapped_in_one_flit", swap_peer_blocks)

    def atomic32(graph, trace):
        tag = next(t for oid, t in graph["metadata"]["tags"].items() if oid.startswith("c0e0/peer/data/") and t["kind"] == "read" and len(t["blocks"]) == 2)
        tag["block_completion_ticks"] = [max(tag["block_completion_ticks"])]*2

    mutate("mono_bank_two_blocks_falsely_atomic_at_tail", atomic32)

    def move_operation(graph, trace, oid, new_start):
        op = next(o for o in trace["operations"] if o["id"] == oid)
        duration = op["end"]-op["start"]
        op.update(start=new_start, end=new_start+duration)

    mutate("next_load_issue_before_source_release", lambda g, t: move_operation(g, t, "c0e1/load/issue:0", 0))
    mutate("next_peer_issue_before_receive_token", lambda g, t: move_operation(g, t, "c0e1/peer/issue:0", 0))
    mutate("result_overwrite_before_output_last_read", lambda g, t: move_operation(g, t, "c0e1/consumer/write000:0", 0))
    mutate("consumer_ready_without_actual_notification_read", lambda g, t: move_operation(g, t, "c0e0/consumer_ready:0", 0))
    mutate("missing_final_ack_operation", lambda g, t: t["operations"].pop(next(i for i, op in enumerate(t["operations"]) if op["id"].startswith("c0e1/output/ack/f000:"))))
    output = {"schema": "r13.trace-qualification.v1", "status": "passed", "positive_traces": positives, "negative_mutations": negatives, "wall_seconds_not_model_cycles": time.perf_counter()-start, "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "source_file_sha256": {name: hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ("model_builder.py", "event_machine.py", "hardware_model.json")}, "scope": "Four actual full two-chain/two-epoch 1KiB trace audits and nine negative mutations; not a proof over unexecuted schedules"}
    return output


if __name__ == "__main__":
    result = qualify()
    output = HERE / "artifacts/trace_qualification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "positive_traces": len(result["positive_traces"]), "negative_mutations": len(result["negative_mutations"]), "output": str(output)}))
