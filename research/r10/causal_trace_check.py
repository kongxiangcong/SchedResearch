"""Independent, read-only R9 trace audit. Does not import the event simulator.

Usage: python -X utf8 -B r9/independent_check.py --results r9/results
The output certificate covers the explicitly listed detailed traces, not hardware.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import gzip
import hashlib
import heapq
import json
import math
from pathlib import Path
import random

EPS = 1e-7


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def same(a, b):
    return abs(float(a) - float(b)) <= EPS * max(1.0, abs(float(a)), abs(float(b)))


def read_json(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def environment_values(environment):
    return (float(environment.get("period", environment.get("period_cycles", 8192))),
            float(environment.get("duty", 0)), float(environment.get("phase", 0)))


def available_cycles(start, end, environment):
    """Integral of a periodic absolute-time on/off supply, independently computed."""
    require(end + EPS >= start, "negative service interval")
    period, duty, phase = environment_values(environment)
    require(period > 0 and 0 <= duty < 1, "invalid supply")
    if duty == 0:
        return end - start
    blocked = 0.0
    first = math.floor((start - phase - period * duty) / period)
    last = math.ceil((end - phase) / period)
    for index in range(first, last + 1):
        left = phase + index * period
        right = left + duty * period
        blocked += max(0.0, min(end, right) - max(start, left))
    return max(0.0, end - start - blocked)


def earliest_supply_finish(work_cycles, environment):
    """Optimistic finish if all work were eligible at time zero, no latency."""
    if work_cycles <= 0:
        return 0.0
    _, duty, _ = environment_values(environment)
    lo, hi = 0.0, work_cycles / (1 - duty) + environment_values(environment)[0]
    for _ in range(90):
        middle = (lo + hi) / 2
        if available_cycles(0.0, middle, environment) >= work_cycles:
            hi = middle
        else:
            lo = middle
    return hi


def overlaps(a, b):
    return (a["space"] == b["space"] and a.get("owner", -1) == b.get("owner", -1)
            and a["address"] < b["address"] + b["size"]
            and b["address"] < a["address"] + a["size"])


def normalize_region(region):
    return (region["space"], int(region.get("owner", -1)),
            int(region["address"]), int(region["size"]))


def region_contains(outer, inner):
    return (outer["space"] == inner["space"] and outer.get("owner", -1) == inner.get("owner", -1)
            and outer["address"] <= inner["address"]
            and inner["address"] + inner["size"] <= outer["address"] + outer["size"])


def check_nonoverlap(intervals, label, capacity=1):
    events = []
    for start, end, identity in intervals:
        require(end + EPS >= start, f"{label}: negative duration {identity}")
        if end - start > EPS:
            events.append((start, 1, str(identity)))
            events.append((end, -1, str(identity)))
    count = peak = 0
    for _, delta, identity in sorted(events):
        count += delta
        peak = max(peak, count)
        require(count <= capacity, f"{label}: capacity {capacity} exceeded at {identity}")
    require(count == 0, f"{label}: unmatched intervals")
    return peak


def check_address_hazards(accesses):
    """Check actual transfer/compute live intervals, independent of graph dependency intent."""
    grouped = defaultdict(list)
    for access in accesses:
        start, end, mode, identity, region = access
        if end - start > EPS:
            grouped[(region["space"], region.get("owner", -1))].append(access)
    compared = 0
    for group in grouped.values():
        active = []
        for access in sorted(group, key=lambda a: (a[0], a[1], str(a[3]))):
            start, end, mode, identity, region = access
            active = [other for other in active if other[1] > start + EPS]
            for other in active:
                if identity == other[3] or (mode == other[2] == "read"):
                    continue
                compared += 1
                require(not overlaps(region, other[4]),
                        f"address hazard: {identity} {mode} overlaps {other[3]} {other[2]}")
            active.append(access)
    return compared


def check_contiguous_cover(regions, expected_size, label):
    segments = sorted((r["address"], r["address"] + r["size"]) for r in regions)
    cursor = 0
    for left, right in segments:
        require(left == cursor and right > left, f"{label}: gap/overlap at {cursor}, got {left}:{right}")
        cursor = right
    require(cursor == expected_size, f"{label}: covered {cursor}, expected {expected_size}")


def check_uniform_cover(regions, expected_size, multiplicity, label):
    events = Counter()
    for region in regions:
        left, right = region["address"], region["address"] + region["size"]
        require(0 <= left < right <= expected_size, f"{label}: source range")
        events[left] += 1
        events[right] -= 1
    require(events and min(events) == 0 and max(events) == expected_size, f"{label}: source endpoints")
    active = 0
    previous = 0
    for address, delta in sorted(events.items()):
        if address > previous:
            require(active == multiplicity, f"{label}: source cover {active}, expected {multiplicity}")
        active += delta
        previous = address
    require(active == 0, f"{label}: source coverage unbalanced")


def region_coverage_signature(regions):
    events = Counter()
    for region in regions:
        key = (region["space"], region.get("owner", -1))
        events[(*key, region["address"])] += 1
        events[(*key, region["address"] + region["size"])] -= 1
    return {key: value for key, value in events.items() if value}


def audit_trace(envelope):
    hardware, graph = envelope["hardware"], envelope["graph"]
    environment = envelope.get("environment", {})
    result = envelope["result"]
    trace = result.get("trace", result)
    requests, operations = trace["requests"], trace["operations"]
    nodes = {node["id"]: node for node in graph["nodes"]}
    require(len(nodes) == len(graph["nodes"]), "duplicate node id")
    packets = {packet["id"]: (node, packet)
               for node in graph["nodes"] for packet in node.get("packets", [])}
    require(len(packets) == sum(len(n.get("packets", [])) for n in nodes.values()), "duplicate packet id")
    for node in nodes.values():
        if "packets" in node:
            for key, packet_key in (("reads", "source_spans"), ("writes", "destination_spans")):
                require(region_coverage_signature(node[key]) == region_coverage_signature(
                    [region for packet in node["packets"] for region in packet[packet_key]]), "command/packet span coverage")
    seen = {request["id"]: request for request in requests}
    require(len(seen) == len(requests), "duplicate request")
    require(set(seen) == set(packets), "request coverage/missed bytes")
    operation_by_id = {op["id"]: op for op in operations}
    expected_ops = {identity for identity, node in nodes.items() if node["kind"] in ("compute", "reduce")}
    require(set(operation_by_id) == expected_ops, "compute/reduce operation coverage")
    completed = {}
    started = {}
    ext_intervals, accesses = [], []
    cluster_intervals, credit_intervals, slot_intervals = defaultdict(list), defaultdict(list), defaultdict(list)
    core_intervals = defaultdict(list)
    ext_bytes, logical_bytes, multicast_local_extra = 0, 0, 0
    local_bytes, core_cycles = Counter(), Counter()
    allocations = graph["allocations"]
    by_owner = defaultdict(list)
    for allocation in allocations:
        require(allocation["size"] > 0 and allocation["address"] >= 0, "invalid allocation")
        by_owner[(allocation["space"], allocation.get("owner", -1))].append(allocation)
    for (space, owner), group in by_owner.items():
        ordered = sorted(group, key=lambda a: a["address"])
        for previous, following in zip(ordered, ordered[1:]):
            require(previous["address"] + previous["size"] <= following["address"],
                    f"physical allocations overlap {space}/{owner}")
        if space == "vmem":
            limit = hardware["vmem_bytes_per_core"]
            if "vmem_usable_bytes" in hardware:
                limit = hardware["vmem_reserved_bytes_per_core"] + hardware["vmem_usable_bytes"]
            require(min(a["address"] for a in group) >= hardware["vmem_reserved_bytes_per_core"], "VMEM reserved region")
            require(max(a["address"] + a["size"] for a in group) <= limit, "VMEM capacity")
        elif space == "ext_scratch":
            require(max(a["address"] + a["size"] for a in group) <= hardware["external_scratch_bytes"],
                    "scratch capacity")
    for request in requests:
        identity = request["id"]
        node, packet = packets[identity]
        require(request["node_id"] == node["id"], "request node mismatch")
        require(request["cluster"] == node["cluster"], "request cluster mismatch")
        for key in ("external_bytes", "local_bytes", "source_spans", "destination_spans"):
            require(request[key] == packet[key], f"packet {identity}: altered {key}")
        require(packet["logical_bytes"] > 0, "zero/negative packet")
        require(packet["logical_bytes"] <= hardware["packet_bytes"], "packet payload capacity")
        external_spans = (packet["source_spans"] if node["kind"] == "dma_read" else packet["destination_spans"])
        require(sum(r["size"] for r in external_spans) == packet["logical_bytes"], "logical source byte count")
        beat = hardware["bus_beat_bytes"]
        expected_external = sum(((r["address"] + r["size"] + beat - 1) // beat - r["address"] // beat) * beat
                                for r in external_spans)
        require(packet["external_bytes"] == expected_external, "beat-rounded external traffic")
        local_spans = (packet["destination_spans"] if node["kind"] == "dma_read" else packet["source_spans"])
        require(packet["local_bytes"] == sum(r["size"] for r in local_spans), "local/multicast byte count")
        require(packet["local_bytes"] <= hardware["transport_bytes_per_slot"], "transport byte capacity")
        cluster = request["cluster"]
        ext_start, ext_end = request["external_start"], request["external_end"]
        local_start, local_end = request["local_start"], request["local_end"]
        accept, visible = request["accept"], request["visible"]
        require(accept >= 0 and visible >= accept, "invalid lifetime")
        if node["kind"] == "dma_read":
            require(ext_start + EPS >= accept + hardware["request_latency_cycles"], "read latency")
            require(local_start + EPS >= ext_end, "local read before external data")
            require(same(request["source_last_read"], ext_end), "read source last-reader")
            require(same(visible, local_end + hardware["visibility_cycles"]), "read destination visibility")
        else:
            require(node["kind"] == "dma_write", "invalid DMA kind")
            require(local_start + EPS >= accept + hardware["request_latency_cycles"], "write latency")
            require(ext_start + EPS >= local_end, "external write before local source read")
            require(same(request["source_last_read"], local_end), "write source last-reader")
            require(same(visible, ext_end + hardware["visibility_cycles"]), "write destination visibility")
        segments = request["external_segments"]
        require(segments and segments[0][0] + EPS >= ext_start and same(segments[-1][1], ext_end),
                "external segment endpoints")
        service = 0.0
        previous = ext_start
        for left, right in segments:
            require(left + EPS >= previous and right > left, "invalid external segments")
            require(same(available_cycles(left, right, environment), right - left), "service during reserved background")
            service += right - left
            previous = right
        require(same(service * hardware["external_bytes_per_cycle"], packet["external_bytes"]), "external serviced bytes")
        require(same(available_cycles(ext_start, ext_end, environment) * hardware["external_bytes_per_cycle"],
                     packet["external_bytes"]), "external completion/service curve")
        require(same((local_end - local_start) * hardware["cluster_dma_bytes_per_cycle"], packet["local_bytes"]),
                "local serviced bytes")
        ext_intervals.append((ext_start, ext_end, identity))
        cluster_intervals[cluster].append((local_start, local_end, identity))
        credit_intervals[cluster].append((accept, visible, identity))
        slot = request["transport_slot"]
        require(0 <= slot < hardware["transport_slots_per_cluster"], "invalid transport slot")
        slot_intervals[(cluster, slot)].append((accept, visible, identity))
        for mode, key, finish in (("read", "source_spans", request["source_last_read"]),
                                  ("write", "destination_spans", visible)):
            for region in packet[key]:
                require(region["size"] > 0 and region["address"] >= 0, "invalid transfer span")
                if region["space"] in ("vmem", "ext_scratch"):
                    require(any(region_contains(a, region) for a in by_owner[(region["space"], region.get("owner", -1))]),
                            "transfer outside allocated storage")
                accesses.append((accept, finish, mode, identity, region))
        completed[node["id"]] = max(completed.get(node["id"], 0), visible)
        started[node["id"]] = min(started.get(node["id"], accept), accept)
        ext_bytes += packet["external_bytes"]
        logical_bytes += packet["logical_bytes"]
        local_bytes[cluster] += packet["local_bytes"]
        if node["kind"] == "dma_read":
            multicast_local_extra += packet["local_bytes"] - packet["logical_bytes"]
    for op in operations:
        node = nodes[op["id"]]
        require(op["end"] >= op["start"] >= 0, "invalid operation interval")
        require(same(op["end"] - op["start"], node["duration"]), "compute duration")
        if graph.get("scope", "main") != "tiny":
            expected_operand = sum(r["size"] for r in node["reads"] + node["writes"])
            require(expected_operand == node["operand_bytes"], "compute operand traffic")
            if node["kind"] == "compute":
                require(node["macs"] == node["m"] * node["n"] * node["k"], "MAC work")
                expected_duration = max(node["macs"] / hardware["macs_per_core_cycle"],
                                        expected_operand / hardware["core_operand_bytes_per_cycle"])
            else:
                require(node["adds"] == sum(r["size"] for r in node["writes"]) / hardware["workload"]["partial_output_bytes"],
                        "reduction work")
                expected_duration = max(node["adds"] / hardware["reduction_adds_per_cycle"],
                                        expected_operand / hardware["core_operand_bytes_per_cycle"])
            require(same(node["duration"], expected_duration + hardware["compute_startup_cycles"]), "core throughput contract")
        core = node["core"]
        core_intervals[core].append((op["start"], op["end"], op["id"]))
        core_cycles[core] += node["duration"]
        for mode, key in (("read", "reads"), ("write", "writes")):
            for region in node[key]:
                require(any(region_contains(a, region) for a in by_owner[(region["space"], region.get("owner", -1))]),
                        "compute outside allocated storage")
                accesses.append((op["start"], op["end"], mode, op["id"], region))
        completed[op["id"]], started[op["id"]] = op["end"], op["start"]
    require(set(completed) == set(nodes), "node completion coverage")
    for node in nodes.values():
        for dependency in node["deps"]:
            require(dependency in nodes, "unknown dependency")
            require(started[node["id"]] + EPS >= completed[dependency],
                    f"early consumer {node['id']} before destination visible/dependency {dependency}")
    if "node_completion" in trace:
        require(set(trace["node_completion"]) == set(completed), "node completion report coverage")
        require(all(same(trace["node_completion"][key], value) for key, value in completed.items()), "node completion report")
    commands = trace.get("command_intervals")
    require(commands is not None, "missing command admission trace")
    dma_ids = {identity for identity, node in nodes.items() if node["kind"].startswith("dma_")}
    require({entry["id"] for entry in commands} == dma_ids and len(commands) == len(dma_ids), "command admission coverage")
    command_groups = defaultdict(list)
    for entry in commands:
        identity = entry["id"]
        require(entry["cluster"] == nodes[identity]["cluster"], "command cluster")
        require(entry["start"] <= started[identity] + EPS and same(entry["end"], completed[identity]), "command live interval")
        require(all(entry["start"] + EPS >= completed[dep] for dep in nodes[identity]["deps"]), "command admission before dependency")
        command_groups[entry["cluster"]].append((entry["start"], entry["end"], identity))
    for cluster, intervals in command_groups.items():
        check_nonoverlap(intervals, f"command slots cluster {cluster}", hardware["dma_command_slots_per_cluster"])
    check_nonoverlap(ext_intervals, "shared EXT")
    peaks = {}
    for cluster, intervals in cluster_intervals.items():
        check_nonoverlap(intervals, f"local DMA cluster {cluster}", hardware["dma_channels_per_cluster"])
    for core, intervals in core_intervals.items():
        check_nonoverlap(intervals, f"core {core}")
    outstanding = envelope.get("config", {}).get("outstanding", hardware["dma_outstanding_per_cluster"])
    for cluster, intervals in credit_intervals.items():
        peaks[str(cluster)] = check_nonoverlap(intervals, f"outstanding/credit cluster {cluster}",
                                              min(outstanding, hardware["dma_outstanding_per_cluster"],
                                                  hardware["transport_slots_per_cluster"]))
    for slot, intervals in slot_intervals.items():
        check_nonoverlap(intervals, f"transport slot {slot}")
    decisions = trace.get("ext_decisions")
    require(decisions is not None and len(decisions) == len(requests), "external decision coverage")
    ext_ready = {r["id"]: (r["accept"] + hardware["request_latency_cycles"]
                           if nodes[r["node_id"]]["kind"] == "dma_read" else r["local_end"]) for r in requests}
    remaining = set(seen)
    ready_order = sorted((time, identity) for identity, time in ext_ready.items())
    ready_heap = list(ready_order)
    ready_index, eligible = 0, set()
    previous_end = 0
    changed_choices = 0
    for index, decision in enumerate(decisions):
        time = decision["time"]
        require(decision["decision_index"] == index, "external decision index")
        while ready_index < len(ready_order) and ready_order[ready_index][0] <= time + EPS:
            identity = ready_order[ready_index][1]
            if identity in remaining:
                eligible.add(identity)
            ready_index += 1
        require(set(decision["candidates"]) == eligible and len(decision["candidates"]) == len(eligible),
                "external decision eligible alternatives")
        require(decision["chosen"] in eligible and decision["default"] in eligible, "external chosen/default eligibility")
        while ready_heap and ready_heap[0][1] not in remaining:
            heapq.heappop(ready_heap)
        require(same(time, max(previous_end, ready_heap[0][0])), "external not work-conserving")
        chosen = seen[decision["chosen"]]
        require(decision["cost_cycles"] in (0, 2, 10), "unregistered intervention charge")
        changed_choices += int(decision["chosen"] != decision["default"])
        require(same(chosen["external_start"], time + decision["cost_cycles"]), "intervention cost missing from external path")
        previous_end = chosen["external_end"]
        remaining.remove(chosen["id"])
        eligible.remove(chosen["id"])
    require(changed_choices <= 1, "more than one external intervention")
    for cluster in cluster_intervals:
        local_ready = {r["id"]: (r["external_end"] if nodes[r["node_id"]]["kind"] == "dma_read"
                                  else r["accept"] + hardware["request_latency_cycles"])
                       for r in requests if r["cluster"] == cluster}
        previous_end = 0
        local_heap = [(time, identity) for identity, time in local_ready.items()]
        heapq.heapify(local_heap)
        for start, end, identity in sorted(cluster_intervals[cluster]):
            while local_heap and local_heap[0][1] not in local_ready:
                heapq.heappop(local_heap)
            require(same(start, max(previous_end, local_heap[0][0])), "local DMA not work-conserving")
            previous_end = end
            del local_ready[identity]
    hazard_comparisons = check_address_hazards(accesses)
    elapsed = result.get("elapsed", result.get("elapsed_cycles"))
    require(elapsed is not None, "missing final elapsed")
    final = max(completed[identity] for identity in graph["output_nodes"])
    require(same(elapsed, final), "final external output finish")
    require(max(completed.values()) <= final + EPS, "unfinished work after output")
    output_regions = [region for node in nodes.values() for packet in node.get("packets", [])
                      for region in packet["destination_spans"] if region["space"] == "ext_y"]
    shape = hardware["workload"]
    if graph.get("scope", "main") != "tiny":
        require(sum(n.get("macs", 0) for n in nodes.values()) == shape["M"] * shape["N"] * shape["K"], "full model MAC coverage")
        shards = {shard["core"]: shard for shard in graph["shards"]}
        for core, shard in shards.items():
            compute = sorted([node for node in nodes.values() if node["kind"] == "compute" and node["core"] == core],
                             key=lambda node: node["k_start"])
            cursor = shard["k_start"]
            for node in compute:
                require(node["k_start"] == cursor and node["k_end"] == cursor + node["k"], "tile K gap/overlap")
                require(node["m"] == shape["M"] and node["n"] == shard["n_end"] - shard["n_start"], "tile M/N work")
                require(all(node[axis] % multiple == 0 for axis, multiple in zip(("m", "n", "k"), hardware["geometry"])),
                        "core geometry/tail permission")
                # Verify the selected tile actually consumes the external tensor
                # rows owned by this core, including resident-X packed row stride.
                for tensor, source_space, width_bytes in (("x", "ext_x", shape["input_bytes"]),
                                                           ("w", "ext_w", shape["weight_bytes"])):
                    producers = [nodes[dep] for dep in node["deps"] if nodes[dep]["kind"] == "dma_read"
                                 and nodes[dep]["reads"] and nodes[dep]["reads"][0]["space"] == source_space]
                    require(len(producers) == 1, "unique operand producer")
                    producer = producers[0]
                    resident = tensor == "x" and envelope.get("config", graph["config"])["resident_x"]
                    low, high = (shard["k_start"], shard["k_end"]) if resident else (node["k_start"], node["k_end"])
                    row_range = range(shape["M"]) if tensor == "x" else range(shard["n_start"], shard["n_end"])
                    expected_sources = [(source_space, -1, (row * shape["K"] + low) * width_bytes,
                                         (high - low) * width_bytes) for row in row_range]
                    require([normalize_region(r) for r in producer["reads"]] == expected_sources, "operand external row/tile identity")
                    destinations = [r for r in producer["writes"] if r["owner"] == core]
                    require(len(destinations) == 1, "operand packed destination")
                    base = destinations[0]["address"]
                    if resident:
                        expected_local = [("vmem", core, base + (row * (high - low) + node["k_start"] - low) * width_bytes,
                                           node["k"] * width_bytes) for row in range(shape["M"])]
                    else:
                        expected_local = [("vmem", core, base, len(row_range) * node["k"] * width_bytes)]
                    operand_reads = [r for r in node["reads"] if any(region_contains(a, r) and f".{tensor}." in a["label"]
                                     for a in by_owner[("vmem", core)])]
                    require([normalize_region(r) for r in operand_reads] == expected_local, "operand packed local row/tile identity")
                cursor = node["k_end"]
            require(cursor == shard["k_end"], "shard K completion")
        for ncolumn in range(shape["N"]):
            intervals = sorted((s["k_start"], s["k_end"]) for s in shards.values() if s["n_start"] <= ncolumn < s["n_end"])
            cursor = 0
            for left, right in intervals:
                require(left == cursor and right > left, "mapping K/N gap/overlap")
                cursor = right
            require(cursor == shape["K"], "mapping full K/N coverage")
        check_contiguous_cover(output_regions, shape["M"] * shape["N"] * shape["partial_output_bytes"], "external Y")
        sources = [region for node in nodes.values() for packet in node.get("packets", [])
                   for region in packet["source_spans"]]
        check_uniform_cover([r for r in sources if r["space"] == "ext_w"],
                            shape["N"] * shape["K"] * shape["weight_bytes"], 1, "external W")
        config = envelope.get("config", graph.get("config", {}))
        mapping = config["mapping"]
        x_copies = {"C2N": 4, "C2K": 2, "C1N": 2}[mapping]
        if config["multicast"]:
            x_copies //= 2
        check_uniform_cover([r for r in sources if r["space"] == "ext_x"],
                            shape["M"] * shape["K"] * shape["input_bytes"], x_copies, "external X")
        stage_written = sum(r["size"] for node in nodes.values() for packet in node.get("packets", [])
                            for r in packet["destination_spans"] if r["space"] == "ext_scratch")
        stage_read = sum(r["size"] for r in sources if r["space"] == "ext_scratch")
        expected_stage = shape["M"] * shape["N"] * shape["partial_output_bytes"] if mapping == "C2K" else 0
        require(stage_read == stage_written == expected_stage, "split-K external staging write/read accounting")
    bound = max(earliest_supply_finish(ext_bytes / hardware["external_bytes_per_cycle"], environment),
                max(local_bytes.values(), default=0) / hardware["cluster_dma_bytes_per_cycle"],
                max(core_cycles.values(), default=0))
    require(bound <= elapsed + EPS, "resource lower-bound direction")
    return {"status": "PASS", "requests": len(requests), "operations": len(operations),
            "nodes": len(nodes), "external_bytes": ext_bytes, "logical_bytes": logical_bytes,
            "cluster_dma_bytes": dict(local_bytes), "multicast_local_extra_bytes": multicast_local_extra,
            "independent_lower_bound": bound, "elapsed": elapsed,
            "zero_cost_recovery_upper_percent": 100 * (elapsed - bound) / elapsed,
            "credit_peaks": peaks, "hazard_comparisons": hazard_comparisons}


def audit_experiment(directory, manifest, reports):
    """Recompute split/selection/pairing and descriptive CIs without runner imports."""
    registration = read_json(directory / "prerun_registration.json")
    completion = read_json(directory / "completion.json")
    selected = read_json(directory / "selection.json")["selected"]
    phases = registration["phases"]
    for name, seed, count in (("train", 910000, 8), ("validation", 920000, 8),
                               ("test_s1", 930000, 30), ("test_s2", 940000, 30)):
        rng = random.Random(seed)
        expected = [{"block": block, "phase": rng.random() * 8192} for block in range(count)]
        require(phases[name] == expected, "pre-registered independent phase stream")
    all_phases = [entry["phase"] for group in phases.values() for entry in group]
    require(len(set(all_phases)) == 76, "train/validation/test phase reuse")
    catalog = {entry["id"]: entry["config"] for entry in registration["candidate_pool"]}
    require(len(catalog) == registration["candidate_count"], "candidate registration coverage")
    training = read_json(directory / "training.json")
    validation = read_json(directory / "validation.json")
    require({entry["id"] for entry in training} == set(catalog) and len(training) == len(catalog), "training candidate coverage")
    conditions = ("quiet", "reserved20", "reserved35")
    def score(entry, condition):
        values = entry["elapsed"][condition]
        return sum(values) / len(values), entry["id"]
    for entry in training + validation:
        require(entry["config"] == catalog[entry["id"]], "registered candidate mutation")
        if entry["legal"]:
            require(len(entry["elapsed"]["quiet"]) == 1, "quiet deterministic training count")
            require(all(len(entry["elapsed"][c]) == 8 for c in conditions[1:]), "training/validation phase count")
    shortlist = set()
    for mapping in ("C1N", "C2N", "C2K"):
        for multicast in (False, True):
            group = [entry for entry in training if entry["legal"] and entry["config"]["mapping"] == mapping
                     and entry["config"]["multicast"] == multicast]
            for condition in conditions:
                shortlist.update(entry["id"] for entry in sorted(group, key=lambda row: score(row, condition))[:4])
    require({entry["id"] for entry in validation} == shortlist and len(validation) == len(shortlist), "train-only validation shortlist")
    for scope in ("main", "C1N", "C2N", "C2K"):
        group = [entry for entry in validation if entry["legal"] and
                 ((entry["config"]["mapping"] != "C1N") if scope == "main" else entry["config"]["mapping"] == scope)]
        for condition in conditions:
            require(selected[scope][condition] == min(group, key=lambda row: score(row, condition))["id"], "validation-only selection")
    by_path = {entry["path"]: report for entry, report in zip(manifest["traces"], reports)}
    require(len(by_path) == len(manifest["traces"]), "duplicate trace manifest path")
    rows = read_json(directory / "test_pairs.json")
    expected_keys = {(session, condition, block) for session in (1, 2) for condition in conditions for block in range(30)}
    require({(r["session"], r["condition"], r["block"]) for r in rows} == expected_keys and len(rows) == 180, "independent paired block coverage")
    for row in rows:
        condition, session, block = row["condition"], row["session"], row["block"]
        require(row["phase"] == phases[f"test_s{session}"][block]["phase"], "paired absolute phase")
        require(row["quiet_config_id"] == selected["main"]["quiet"] and row["strong_config_id"] == selected["main"][condition], "fixed selected static")
        trace_audit = by_path[row["strong_trace"]]
        require(same(row["strong_elapsed"], trace_audit["elapsed"]), "test elapsed/trace mismatch")
        require(same(row["strong_lower_bound"], trace_audit["independent_lower_bound"]), "independent lower bound mismatch")
    summary = read_json(directory / "summary.json")
    metrics = {
        "fixed_static_loss_pct": lambda r: 100 * (r["quiet_selected_elapsed"] / r["quiet_reference_elapsed"] - 1),
        "strong_static_gain_pct": lambda r: 100 * (1 - r["strong_elapsed"] / r["quiet_selected_elapsed"]),
        "remaining_zero_cost_upper_pct": lambda r: 100 * (1 - r["strong_lower_bound"] / r["strong_elapsed"]),
        "strong_elapsed": lambda r: r["strong_elapsed"],
        "best_sampled_single_action_free_pct": lambda r: 100 * (1 - r["best_free_elapsed"] / r["strong_elapsed"]),
        "best_sampled_single_action_charged_pct": lambda r: 100 * (1 - r["best_charged_elapsed"] / r["strong_elapsed"])}
    for session in (1, 2):
        for condition in conditions:
            group = [r for r in rows if r["session"] == session and r["condition"] == condition]
            for key, function in metrics.items():
                values = [function(r) for r in group]
                mean = math.fsum(values) / 30
                variance = math.fsum((v - mean) ** 2 for v in values) / 29
                margin = 2.045229642132703 * math.sqrt(variance / 30)
                expected = (mean, min(values), max(values), mean - margin, mean + margin)
                record = summary[f"s{session}.{condition}"][key]
                actual = (record["mean"], record["min"], record["max"], *record["ci95_t"])
                require(record["n"] == 30 and all(same(a, b) for a, b in zip(actual, expected)), "paired t CI independent recomputation")
    require(completion["test_pair_count"] == 180 and completion["trace_count"] == len(reports), "completion counts")
    require(completion["model_sha256"] == digest(directory.parent / "model.py"), "frozen model identity")
    require(completion["runner_sha256"] == digest(directory.parent / "run_experiment.py"), "frozen runner identity")
    return {"status": "PASS", "candidate_count": len(catalog), "validation_shortlist": len(shortlist),
            "independent_phase_values": 76, "paired_blocks": 180, "summary_statistics_recomputed": 36,
            "selection": selected, "scope": "recorded train/validation selection and test pairing; finite candidate pool, no exhaustive-static claim"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=Path(__file__).parent / "results")
    args = parser.parse_args()
    manifest_path = args.results / "trace_manifest.json"
    manifest = read_json(manifest_path)
    reports = []
    for entry in manifest["traces"]:
        path = args.results / entry["path"]
        require("sha256" not in entry or digest(path) == entry["sha256"], f"trace manifest digest: {path}")
        envelope = read_json(path)
        require(envelope["config"] == envelope["graph"]["config"], "trace config/graph mismatch")
        if entry["stage"] in ("test", "control", "counterfactual", "sensitivity"):
            prereg = read_json(args.results / "prerun_registration.json")
            condition = entry["condition"]
            expected_env = {"period": 8192, "duty": {"quiet": 0, "reserved20": .2, "reserved35": .35}[condition],
                            "phase": prereg["phases"][f"test_s{entry['session']}"][entry["block"]]["phase"]}
            require(envelope["environment"] == expected_env, "trace common absolute environment")
            if entry["stage"] != "sensitivity":
                require(envelope["hardware"] == prereg["hardware"], "main hardware changed")
        try:
            report = audit_trace(envelope)
        except Exception as error:
            raise AssertionError(f"{entry['path']}: {error}") from error
        reports.append({"path": entry["path"], "sha256": digest(path), **report})
    require(bool(reports), "no listed traces")
    experiment_audit = audit_experiment(args.results, manifest, reports)
    certificate = {"status": "PASS", "scope": "independent R9 reference-model trace audit; no target validation",
                   "checker_sha256": digest(__file__), "trace_manifest_sha256": digest(manifest_path),
                   "audited_traces": len(reports), "requests": sum(r["requests"] for r in reports),
                   "operations": sum(r["operations"] for r in reports), "experiment_audit": experiment_audit, "traces": reports}
    (args.results / "audit_results.json").write_text(json.dumps(certificate, indent=2), encoding="utf8")
    print(json.dumps({k: v for k, v in certificate.items() if k != "traces"}))


if __name__ == "__main__":
    main()
