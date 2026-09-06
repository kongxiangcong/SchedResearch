"""R9's single reference path: payload DAG, finite DMA credits, common EXT supply.

No sampled task latencies, learned scheduler, peer link, or hidden bandwidth.
The graph and detailed trace are deliberately ordinary JSON-compatible objects.
"""
from __future__ import annotations

import heapq
import json
import math
from pathlib import Path


def load_hardware(path=None):
    return json.loads(Path(path or Path(__file__).with_name("reference_hardware.json")).read_text(encoding="utf-8"))


def service_segments(start, work_cycles, environment):
    """Available EXT intervals, from an absolute-time periodic reservation."""
    period = float(environment.get("period", 8192))
    duty = float(environment.get("duty", 0))
    phase = float(environment.get("phase", 0)) % period
    if not 0 <= duty < 1 or period <= 0 or work_cycles < 0:
        raise ValueError("invalid supply contract")
    if work_cycles == 0:
        return []
    if duty == 0:
        return [[float(start), float(start + work_cycles)]]
    time, remaining, segments = float(start), float(work_cycles), []
    while remaining > 1e-9:
        position = (time - phase) % period
        reserved = duty * period
        if position < reserved - 1e-9:
            time += reserved - position
            position = reserved
        available = period - position
        if available < 1e-9:
            time += 1e-8
            continue
        used = min(remaining, available)
        segments.append([time, time + used])
        time += used
        remaining -= used
    return segments


def service_finish(start, work_cycles, environment):
    segments = service_segments(start, work_cycles, environment)
    return segments[-1][1] if segments else float(start)


def _region(space, owner, address, size):
    return {"space": space, "owner": owner, "address": int(address), "size": int(size)}


def _split_regions(regions, offset, count):
    result, consumed = [], 0
    for region in regions:
        low, high = max(offset, consumed), min(offset + count, consumed + region["size"])
        if high > low:
            result.append(_region(region["space"], region["owner"], region["address"] + low - consumed, high - low))
        consumed += region["size"]
    if sum(x["size"] for x in result) != count:
        raise ValueError("packet region coverage")
    return result


def _packetize(node_id, sources, destination_groups, direction, hw, layout):
    size = sum(x["size"] for x in sources)
    if any(sum(x["size"] for x in group) != size for group in destination_groups):
        raise ValueError("source/destination byte mismatch")
    # row packetization ends at each external row boundary, in either direction.
    ext_regions = sources if direction == "dma_read" else destination_groups[0]
    stops = []
    if layout == "row":
        running = 0
        for region in ext_regions:
            running += region["size"]
            stops.append(running)
    else:
        stops = [size]
    packets, offset = [], 0
    for stop in stops:
        while offset < stop:
            count = min(int(hw["packet_bytes"]), stop - offset)
            src = _split_regions(sources, offset, count)
            destinations = [_split_regions(group, offset, count) for group in destination_groups]
            ext = src if direction == "dma_read" else destinations[0]
            beat = int(hw["bus_beat_bytes"])
            ext_bytes = sum(((x["address"] % beat + x["size"] + beat - 1) // beat) * beat for x in ext)
            local_bytes = count * len(destinations) if direction == "dma_read" else count
            packets.append({"id": f"{node_id}:p{len(packets):04d}", "logical_bytes": count,
                            "external_bytes": ext_bytes, "local_bytes": local_bytes,
                            "source_spans": src, "destination_spans": [x for group in destinations for x in group]})
            offset += count
    return packets


def build_graph(hw, config):
    defaults = {"mapping": "C2N", "ktile": 512, "buffers": 2, "prefetch": 2,
                "resident_x": False, "multicast": True, "layout": "gather", "order": "xw",
                "reverse": False, "outstanding": 4}
    cfg = defaults | dict(config)
    if cfg["mapping"] not in {"C2N", "C2K", "C1N"} or cfg["ktile"] not in {0, 256, 512, 1024}:
        raise ValueError("unsupported static geometry")
    if cfg["buffers"] not in {1, 2} or cfg["prefetch"] not in {1, 2} or cfg["prefetch"] > cfg["buffers"]:
        raise ValueError("illegal buffering/prefetch")
    if cfg["outstanding"] not in {1, 2, 4} or cfg["layout"] not in {"row", "gather"} or cfg["order"] not in {"xw", "wx"}:
        raise ValueError("illegal static action")
    work = hw["workload"]
    m, k, n = (int(work[x]) for x in ("M", "K", "N"))
    ibytes, wbytes, pbytes = (int(work[x]) for x in ("input_bytes", "weight_bytes", "partial_output_bytes"))
    count = 2 if cfg["mapping"] == "C1N" else 4
    shards = []
    for core in range(count):
        if cfg["mapping"] == "C2K":
            ns, ne, ks, ke = (core % 2) * (n // 2), (core % 2 + 1) * (n // 2), (core // 2) * (k // 2), (core // 2 + 1) * (k // 2)
        else:
            ns, ne, ks, ke = core * (n // count), (core + 1) * (n // count), 0, k
        shards.append({"core": core, "cluster": core // 2, "n_start": ns, "n_end": ne, "k_start": ks, "k_end": ke})
    if hw["clusters"] < (count + 1) // 2 or hw["cores_per_cluster"] != 2:
        raise ValueError("reference topology mismatch")
    allocations, banks, tiles = [], {}, {}
    for shard in shards:
        core, nk, nn = shard["core"], shard["k_end"] - shard["k_start"], shard["n_end"] - shard["n_start"]
        tile = cfg["ktile"] or nk
        tiles[core] = [(start, min(start + tile, shard["k_end"])) for start in range(shard["k_start"], shard["k_end"], tile)]
        maxk = min(tile, nk)
        offset = int(hw["vmem_reserved_bytes_per_core"])
        banks[core] = {}
        sizes = [("x", m * (nk if cfg["resident_x"] else maxk) * ibytes, 1 if cfg["resident_x"] else cfg["buffers"]),
                 ("w", nn * maxk * wbytes, cfg["buffers"]), ("p", m * nn * pbytes, 1)]
        if cfg["mapping"] == "C2K" and core < 2:
            sizes.append(("recv", m * nn * pbytes, 1))
        for name, size, slots in sizes:
            banks[core][name] = []
            for slot in range(slots):
                reg = _region("vmem", core, offset, size)
                allocations.append(reg | {"label": f"c{core}.{name}.{slot}"})
                banks[core][name].append(reg)
                offset += size
        usable_override = hw.get("vmem_usable_bytes")
        limit = int(hw["vmem_bytes_per_core"]) if usable_override is None else int(hw["vmem_reserved_bytes_per_core"]) + int(usable_override)
        if offset > limit:
            raise ValueError(f"VMEM capacity exceeded core {core}: {offset} > {limit}")
    nodes = []
    def transfer(nid, cluster, deps, sources, destinations, kind="dma_read"):
        packets = _packetize(nid, sources, destinations, kind, hw, cfg["layout"])
        node = {"id": nid, "kind": kind, "cluster": cluster, "deps": sorted(set(deps)),
                "reads": sources, "writes": [x for g in destinations for x in g], "packets": packets}
        nodes.append(node)
        return nid
    def input_regions(shard, start, end, tensor):
        if tensor == "x":
            return [_region("ext_x", -1, (row * k + start) * ibytes, (end - start) * ibytes) for row in range(m)]
        return [_region("ext_w", -1, (row * k + start) * wbytes, (end - start) * wbytes) for row in range(shard["n_start"], shard["n_end"])]
    def xdest(core, index, start, end):
        reg = banks[core]["x"][0 if cfg["resident_x"] else index % cfg["buffers"]]
        return [_region("vmem", core, reg["address"], m * (end - start) * ibytes)]
    xids = {}
    core_order = list(range(count))
    if cfg["reverse"]:
        core_order.reverse()
    groups = ([core_order[i:i + 2] for i in range(0, count, 2)] if cfg["multicast"] else [[core] for core in core_order])
    if cfg["resident_x"]:
        for group in groups:
            first = group[0]
            shard = shards[first]
            nid = f"x.res.{'.'.join(map(str,group))}"
            transfer(nid, first // 2, [], input_regions(shard, shard["k_start"], shard["k_end"], "x"),
                     [xdest(core, 0, shard["k_start"], shard["k_end"]) for core in group])
            for core in group:
                xids[core] = nid
    for index in range(len(tiles[0])):
        pending_x = {}
        if not cfg["resident_x"]:
            for group in groups:
                first = group[0]
                start, end = tiles[first][index]
                nid = f"x.t{index}.{'.'.join(map(str,group))}"
                deps = [f"mac.c{core}.t{index-cfg['prefetch']}" for core in group] if index >= cfg["prefetch"] else []
                pending_x[first] = (nid, first // 2, deps, input_regions(shards[first], start, end, "x"),
                                    [xdest(core, index, start, end) for core in group])
                for core in group:
                    xids[core] = nid
        wids = {}
        def add_x():
            for args in pending_x.values():
                transfer(*args)
        def add_w():
            for core in core_order:
                shard = shards[core]
                start, end = tiles[core][index]
                reg = banks[core]["w"][index % cfg["buffers"]]
                dest = _region("vmem", core, reg["address"], (shard["n_end"] - shard["n_start"]) * (end - start) * wbytes)
                nid = f"w.c{core}.t{index}"
                deps = [f"mac.c{core}.t{index-cfg['prefetch']}"] if index >= cfg["prefetch"] else []
                transfer(nid, core // 2, deps, input_regions(shard, start, end, "w"), [[dest]])
                wids[core] = nid
        if cfg["order"] == "xw":
            add_x(); add_w()
        else:
            add_w(); add_x()
        for core in core_order:
            shard = shards[core]
            start, end = tiles[core][index]
            nn, kk = shard["n_end"] - shard["n_start"], end - start
            xr = banks[core]["x"][0 if cfg["resident_x"] else index % cfg["buffers"]]
            if cfg["resident_x"]:
                xreads = [_region("vmem", core, xr["address"] + (row * (shard["k_end"] - shard["k_start"]) + start - shard["k_start"]) * ibytes, kk * ibytes) for row in range(m)]
            else:
                xreads = [_region("vmem", core, xr["address"], m * kk * ibytes)]
            wr = banks[core]["w"][index % cfg["buffers"]]
            pr = banks[core]["p"][0]
            operand = m * kk * ibytes + nn * kk * wbytes + pr["size"] * (2 if index else 1)
            macs = m * nn * kk
            deps = [xids[core], wids[core]] + ([f"mac.c{core}.t{index-1}"] if index else [])
            nodes.append({"id": f"mac.c{core}.t{index}", "kind": "compute", "core": core, "cluster": core // 2,
                          "deps": deps, "reads": xreads + [_region("vmem", core, wr["address"], nn * kk * wbytes)] + ([pr] if index else []),
                          "writes": [pr], "m": m, "n": nn, "k": kk, "k_start": start, "k_end": end,
                          "macs": macs, "operand_bytes": operand,
                          "duration": max(macs / hw["macs_per_core_cycle"], operand / hw["core_operand_bytes_per_cycle"]) + hw["compute_startup_cycles"]})
    final_index = len(tiles[0]) - 1
    output_nodes = []
    if cfg["mapping"] == "C2K":
        needed = m * n * pbytes
        if needed > hw["external_scratch_bytes"]:
            raise ValueError("external staging capacity exceeded")
        for core in core_order:
            if core < 2:
                continue
            target = core - 2
            source = banks[core]["p"][0]
            scratch = _region("ext_scratch", -1, target * source["size"], source["size"])
            allocations.append(scratch | {"label": f"stage.c{core}"})
            send = transfer(f"stage.write.c{core}", 1, [f"mac.c{core}.t{final_index}"], [source], [[scratch]], "dma_write")
            receive = transfer(f"stage.read.c{target}", 0, [send], [scratch], [[banks[target]["recv"][0]]])
            pr, rr = banks[target]["p"][0], banks[target]["recv"][0]
            adds = pr["size"] // pbytes
            nodes.append({"id": f"reduce.c{target}", "kind": "reduce", "core": target, "cluster": 0,
                          "deps": [f"mac.c{target}.t{final_index}", receive], "reads": [pr, rr], "writes": [pr],
                          "adds": adds, "operand_bytes": 3 * pr["size"],
                          "duration": max(adds / hw["reduction_adds_per_cycle"], 3 * pr["size"] / hw["core_operand_bytes_per_cycle"]) + hw["compute_startup_cycles"]})
        final_cores = [core for core in core_order if core < 2]
    else:
        final_cores = core_order
    for core in final_cores:
        shard = shards[core]
        dest = [_region("ext_y", -1, (row * n + shard["n_start"]) * pbytes, (shard["n_end"] - shard["n_start"]) * pbytes) for row in range(m)]
        prior = f"reduce.c{core}" if cfg["mapping"] == "C2K" else f"mac.c{core}.t{final_index}"
        output_nodes.append(transfer(f"y.c{core}", core // 2, [prior], [banks[core]["p"][0]], [dest], "dma_write"))
    ext_bytes, local_bytes, core_cycles = 0, [0] * int(hw["clusters"]), [0.0] * (int(hw["clusters"]) * int(hw["cores_per_cluster"]))
    for priority, node in enumerate(nodes):
        node["priority"] = priority
        if "packets" in node:
            ext_bytes += sum(p["external_bytes"] for p in node["packets"])
            local_bytes[node["cluster"]] += sum(p["local_bytes"] for p in node["packets"])
        else:
            core_cycles[node["core"]] += node["duration"]
    return {"schema": "r9.payload-graph.v1", "config": cfg, "workload": work.copy(), "shards": shards,
            "allocations": allocations, "nodes": nodes, "output_nodes": output_nodes,
            "external_bytes": ext_bytes, "cluster_dma_bytes": local_bytes, "core_cycles": core_cycles,
            "macs": sum(node.get("macs", 0) for node in nodes), "packet_count": sum(len(node.get("packets", [])) for node in nodes)}


def resource_lower_bound(graph, hw, environment):
    """Optimistic concurrent lower bound: unavoidable bytes and core occupancy."""
    ext = service_finish(0, graph["external_bytes"] / hw["external_bytes_per_cycle"], environment)
    return max([ext] + [x / hw["cluster_dma_bytes_per_cycle"] for x in graph["cluster_dma_bytes"]] + graph["core_cycles"])


def simulate(graph, hw, environment, detailed=False, intervention=None):
    nodes = {node["id"]: node for node in graph["nodes"]}
    cluster_count = int(hw["clusters"])
    core_count = cluster_count * int(hw["cores_per_cluster"])
    deps_left = {nid: len(node.get("deps", [])) for nid, node in nodes.items()}
    children = {nid: [] for nid in nodes}
    for nid, node in nodes.items():
        for dep in node.get("deps", []):
            if dep not in nodes:
                raise ValueError(f"missing dependency {dep}")
            children[dep].append(nid)
    ready_dma = [[] for _ in range(cluster_count)]
    ready_compute = [[] for _ in range(core_count)]
    def ready(nid):
        node = nodes[nid]
        target = ready_dma[node["cluster"]] if node["kind"].startswith("dma_") else ready_compute[node["core"]]
        heapq.heappush(target, (node.get("priority", 0), nid))
    for nid, remaining in deps_left.items():
        if remaining == 0:
            ready(nid)
    commands = [[] for _ in range(cluster_count)]
    command_pointer = [0] * cluster_count
    cmd_state, packets = {}, {}
    active_count = [0] * cluster_count
    free_slots = [list(range(int(hw["transport_slots_per_cluster"]))) for _ in range(cluster_count)]
    local_queues, ext_queues = [[] for _ in range(cluster_count)], [[] for _ in range(cluster_count)]
    local_busy, core_busy = [False] * cluster_count, [False] * core_count
    external_busy, external_next = False, 0
    events, serial, time = [], 0, 0.0
    completed, operations, decisions = {}, [], []
    peak_credits, peak_commands = [0] * cluster_count, [0] * cluster_count
    decision_count, applied = 0, False
    def event(at, kind, ident):
        nonlocal serial
        serial += 1
        heapq.heappush(events, (float(at), serial, kind, ident))
    def finish_node(nid, at):
        if nid in completed:
            raise RuntimeError("duplicate completion")
        completed[nid] = at
        for child in children[nid]:
            deps_left[child] -= 1
            if deps_left[child] == 0:
                ready(child)
    def enqueue_stage(pid):
        packet = packets[pid]
        (ext_queues if packet["direction"] == "dma_read" else local_queues)[packet["cluster"]].append(pid)
    limit = min(int(graph.get("config", {}).get("outstanding", hw["dma_outstanding_per_cluster"])), int(hw["dma_outstanding_per_cluster"]))
    while len(completed) < len(nodes):
        # All completions sharing this timestamp commit before admission/arbitration.
        while events and events[0][0] <= time + 1e-9:
            _, _, kind, ident = heapq.heappop(events)
            if kind == "compute":
                core_busy[nodes[ident]["core"]] = False
                finish_node(ident, time)
            elif kind == "latency":
                enqueue_stage(ident)
            elif kind == "external":
                external_busy = False
                packet = packets[ident]
                if packet["direction"] == "dma_read":
                    packet["source_last_read"] = time
                    local_queues[packet["cluster"]].append(ident)
                else:
                    event(time + hw["visibility_cycles"], "visible", ident)
            elif kind == "local":
                packet = packets[ident]
                local_busy[packet["cluster"]] = False
                if packet["direction"] == "dma_read":
                    event(time + hw["visibility_cycles"], "visible", ident)
                else:
                    packet["source_last_read"] = time
                    ext_queues[packet["cluster"]].append(ident)
            elif kind == "visible":
                packet = packets[ident]
                packet["visible"] = time
                cluster, nid = packet["cluster"], packet["node_id"]
                active_count[cluster] -= 1
                free_slots[cluster].append(packet["transport_slot"])
                cmd_state[nid]["visible"] += 1
                if cmd_state[nid]["visible"] == len(nodes[nid]["packets"]):
                    removed_index = commands[cluster].index(nid)
                    commands[cluster].pop(removed_index)
                    if removed_index < command_pointer[cluster]:
                        command_pointer[cluster] -= 1
                    if commands[cluster]:
                        command_pointer[cluster] %= len(commands[cluster])
                    else:
                        command_pointer[cluster] = 0
                    finish_node(nid, time)
            else:
                raise RuntimeError(kind)
        for core in range(core_count):
            if not core_busy[core] and ready_compute[core]:
                _, nid = heapq.heappop(ready_compute[core])
                node = nodes[nid]
                core_busy[core] = True
                finish = time + node["duration"]
                operations.append({"id": nid, "start": time, "end": finish})
                event(finish, "compute", nid)
        for cluster in range(cluster_count):
            while ready_dma[cluster] and len(commands[cluster]) < hw["dma_command_slots_per_cluster"]:
                _, nid = heapq.heappop(ready_dma[cluster])
                commands[cluster].append(nid)
                cmd_state[nid] = {"next": 0, "visible": 0, "start": time}
            peak_commands[cluster] = max(peak_commands[cluster], len(commands[cluster]))
            while active_count[cluster] < limit and free_slots[cluster] and commands[cluster]:
                eligible = [nid for nid in commands[cluster] if cmd_state[nid]["next"] < len(nodes[nid]["packets"])]
                if not eligible:
                    break
                # RR among admitted commands that still have payload to issue.
                start_index = command_pointer[cluster] % len(commands[cluster])
                nid = next(commands[cluster][(start_index + j) % len(commands[cluster])] for j in range(len(commands[cluster]))
                           if commands[cluster][(start_index + j) % len(commands[cluster])] in eligible)
                command_pointer[cluster] = (commands[cluster].index(nid) + 1) % len(commands[cluster])
                node, state = nodes[nid], cmd_state[nid]
                payload = node["packets"][state["next"]]
                if payload["logical_bytes"] * (len({x["owner"] for x in payload["destination_spans"]}) if node["kind"] == "dma_read" else 1) > hw["transport_bytes_per_slot"]:
                    raise ValueError("transport slot capacity exceeded")
                pid = payload["id"]
                packets[pid] = dict(payload) | {"node_id": nid, "direction": node["kind"], "cluster": cluster,
                                             "accept": time, "transport_slot": free_slots[cluster].pop(0)}
                state["next"] += 1
                active_count[cluster] += 1
                peak_credits[cluster] = max(peak_credits[cluster], active_count[cluster])
                event(time + hw["request_latency_cycles"], "latency", pid)
            if not local_busy[cluster] and local_queues[cluster]:
                pid = local_queues[cluster].pop(0)
                packet = packets[pid]
                finish = time + packet["local_bytes"] / hw["cluster_dma_bytes_per_cycle"]
                packet.update(local_start=time, local_end=finish)
                local_busy[cluster] = True
                event(finish, "local", pid)
        if not external_busy and any(ext_queues):
            candidates = [pid for queue in ext_queues for pid in queue]
            chosen_cluster = next((external_next + i) % cluster_count for i in range(cluster_count) if ext_queues[(external_next + i) % cluster_count])
            default = ext_queues[chosen_cluster][0]
            chosen, cost = default, 0.0
            if intervention is not None and decision_count == intervention["decision_index"]:
                value = intervention["choose_request"]
                chosen = candidates[value] if isinstance(value, int) else value
                if chosen not in candidates:
                    raise ValueError("intervention selected ineligible request")
                cost = float(intervention.get("cost_cycles", 8))
                if cost < 0:
                    raise ValueError("negative intervention cost")
                chosen_cluster = packets[chosen]["cluster"]
                applied = True
            if detailed:
                decisions.append({"decision_index": decision_count, "time": time, "candidates": candidates,
                                  "default": default, "chosen": chosen, "cost_cycles": cost})
            decision_count += 1
            external_next = (chosen_cluster + 1) % cluster_count
            ext_queues[chosen_cluster].remove(chosen)
            packet = packets[chosen]
            start = time + cost
            segments = service_segments(start, packet["external_bytes"] / hw["external_bytes_per_cycle"], environment)
            finish = segments[-1][1] if segments else start
            packet.update(external_start=start, external_end=finish, external_segments=segments)
            external_busy = True
            event(finish, "external", chosen)
        if len(completed) == len(nodes):
            break
        if not events:
            raise RuntimeError(f"deadlock: {len(completed)}/{len(nodes)}")
        time = events[0][0]
    if intervention is not None and not applied:
        raise ValueError("intervention decision index never occurred")
    elapsed = max((completed[nid] for nid in graph["output_nodes"]), default=time)
    result = {"elapsed": elapsed, "external_bytes": graph["external_bytes"], "cluster_dma_bytes": graph["cluster_dma_bytes"],
              "core_cycles": graph["core_cycles"], "packet_count": len(packets),
              "peaks": {"credits": peak_credits, "commands": peak_commands,
                        "vmem_bytes": [sum(a["size"] for a in graph.get("allocations", []) if a["space"] == "vmem" and a["owner"] == core) for core in range(core_count)],
                        "scratch_bytes": sum(a["size"] for a in graph.get("allocations", []) if a["space"] == "ext_scratch")},
              "all_outputs_visible": all(nid in completed for nid in graph["output_nodes"]),
              "lower_bound": resource_lower_bound(graph, hw, environment),
              "ext_decision_count": decision_count, "intervention_applied": applied}
    if detailed:
        result.update(graph=graph, environment=dict(environment), operations=operations,
                      requests=list(packets.values()), ext_decisions=decisions, node_completion=completed,
                      command_intervals=[{"id": nid, "cluster": nodes[nid]["cluster"], "start": state["start"], "end": completed[nid]}
                                         for nid, state in cmd_state.items()])
    return result
