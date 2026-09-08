"""Compile explicit memory/network/DFG actions to the R13 service machine.

All addresses in tags identify 16-byte blocks. Values are checked after the
simulation against its actual read/write completion events, not task labels.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from fractions import Fraction
from itertools import permutations, product
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HARDWARE = json.loads((ROOT / "hardware_model.json").read_text(encoding="utf-8"))
TICKS = HARDWARE["ticks_per_cycle"]


def coord(c):
    return f"{c[0]},{c[1]}"


def route(src, dst, noc):
    if noc not in (0, 1) or any(not 0 <= c[i] < (10, 12)[i] for c in (src, dst) for i in (0, 1)):
        raise ValueError("invalid physical coordinate or NoC")
    point = list(src)
    edges = []
    for axis in ((0, 1) if noc == 0 else (1, 0)):
        dateline = 0
        direction = 1 if noc == 0 else -1
        while point[axis] != dst[axis]:
            before = tuple(point)
            point[axis] = (point[axis] + direction) % (10, 12)[axis]
            if (direction == 1 and point[axis] == 0) or (direction == -1 and before[axis] == 0):
                dateline = 1
            edges.append((before, tuple(point), axis, dateline))
    return edges


def physical_channel(endpoint, byte_address, size):
    if size <= 0 or byte_address < 0 or byte_address + size > 2**31:
        raise ValueError("invalid DRAM range")
    ch = byte_address // 2**30
    if (byte_address + size - 1) // 2**30 != ch:
        raise ValueError("split channel-crossing transfers")
    for group, endpoints in enumerate(HARDWARE["dram_groups"]):
        if list(endpoint) in endpoints:
            return group, ch
    raise ValueError("unknown DRAM endpoint")


def scenarios():
    nominal = HARDWARE["nominal"]
    points = [dict(nominal)]
    for key, values in HARDWARE["axes"].items():
        points += [dict(nominal, **{key: v}) for v in values if v != nominal[key]]
    for n, d, c, credit in product((0.5, 0.75), (0.5, 0.75), (0.25, 0.5), (9, 18)):
        points.append(dict(nominal, eta_n=n, eta_d=d, eta_c=c, credit_cycles=credit))
    points += [dict(nominal, control_scale=c) for c in (0.5, 2)]
    seen = set()
    result = []
    for point in points:
        key = tuple(sorted(point.items()))
        if key not in seen:
            seen.add(key)
            result.append(point)
    return result


class Builder:
    def __init__(self, params=None, *, tie_break="ascending", bank_layout="interleaved"):
        self.params = dict(HARDWARE["nominal"], **(params or {}))
        self.spec = {"buffers": {}, "groups": {}, "jobs": [], "tie_break": tie_break}
        self.bank_layout = bank_layout
        self.tags = {}
        self.events = {}
        self.memory = {}
        self.expected = {}
        self.packets = []
        self.scope_previous = {}

    def ticks(self, cycles):
        value = Fraction(str(cycles)) * TICKS
        if value.denominator != 1:
            raise ValueError(f"unrepresentable cycles {cycles}")
        return int(value)

    def rate_ticks(self, size, bytes_per_cycle):
        value = Fraction(size * TICKS, 1) / Fraction(str(bytes_per_cycle))
        if value.denominator != 1:
            raise ValueError("service not exactly representable at registered tick")
        return int(value)

    def queue(self, name, capacity=None, delay=0):
        config = {"capacity": capacity, "credit_delay": delay}
        if name in self.spec["buffers"] and self.spec["buffers"][name] != config:
            raise ValueError(f"conflicting queue {name}")
        self.spec["buffers"][name] = config
        return name

    def vc_queue(self, pool, vc, *, router):
        delay = self.ticks(self.params["credit_cycles"])
        cap = 16 if router else self.params["niu_buffer_flits"]
        if pool not in self.spec["groups"]:
            members = [self.queue(f"{pool}/vc{k:02}", cap, delay) for k in range(16)]
            self.spec["groups"][pool] = {"members": members, "guaranteed": 1 if router else 0,
                "shared": 48 if router else cap, "per_member": cap}
        return f"{pool}/vc{vc:02}"

    def add(self, jid, ops, *, deps=(), packet=None, flit=0, tail=True, release=0):
        if any(j["id"] == jid for j in self.spec["jobs"]):
            raise ValueError(f"duplicate job {jid}")
        job = {"id": jid, "packet": packet or jid, "flit": flit, "tail": tail,
               "release": release, "deps": list(deps), "ops": []}
        for k, operation in enumerate(ops):
            op = deepcopy(operation)
            tag = op.pop("tag", None)
            if tag is not None:
                self.tags[f"{jid}:{k}"] = tag
            job["ops"].append(op)
        self.spec["jobs"].append(job)
        return f"{jid}:{len(ops)-1}"

    def signal(self, name, deps, *, tile=None, noc=0, cycles=0, primitive="logic"):
        q = self.queue(f"signal/{name}")
        scale = 1 if primitive == "timer" else self.params["control_scale"]
        latency = self.ticks(Fraction(str(cycles)) * Fraction(str(scale)))
        resources = {} if not latency or tile is None else {f"control/{coord(tile)}/{noc}": latency}
        result = self.add(name, [{"queue": q, "resources": resources, "latency": latency,
                                  "tag": {"kind": "signal", "name": name, "primitive": primitive}}], deps=deps)
        self.events[name] = result
        return result

    def span(self, tile, address, size, *, dram=False):
        if size % 16 or address % 16:
            raise ValueError("unaligned span")
        if dram:
            group, ch = physical_channel(tile, address, size)
            owner = f"dram/{group}/{ch}"
            base = (address % 2**30) // 16
        else:
            if address < 65536 or address + size > HARDWARE["public_fixed"]["l1_bytes_per_tile"]:
                raise ValueError("L1 span outside payload space")
            owner = f"l1/{coord(tile)}"
            base = address // 16
        return [f"{owner}/{base+i}" for i in range(size // 16)]

    def memory_op(self, queue, tile, blocks, *, noc, write, dram=False, tag=None, local=False):
        if not blocks:
            return {"queue": queue, "resources": {}, "latency": 0}
        size = 16 * len(blocks)
        if dram:
            domain = "/".join(blocks[0].split("/")[:3])
            duration = self.rate_ticks(size, 24 * self.params["eta_d"])
            resources = {domain: duration}
            offsets = [self.rate_ticks(16*(i+1), 24*self.params["eta_d"]) for i in range(len(blocks))]
        else:
            # Paired 16B lanes, rather than a single resource shared by NoCs.
            duration = self.rate_ticks(32, 32 * (1 if local else self.params["eta_n"]))
            interface = "local" if local else f"noc{noc}"
            resources = {f"l1_port/{coord(tile)}/{interface}/{'write' if write else 'read'}": duration}
            banks = Counter(0 if self.bank_layout == "mono" else int(b.rsplit("/", 1)[1]) % 16 for b in blocks)
            for bank, count in banks.items():
                resources[f"bank/{coord(tile)}/{bank}"] = count * duration
            counts = Counter()
            offsets = []
            for block in blocks:
                bank = 0 if self.bank_layout == "mono" else int(block.rsplit("/",1)[1]) % 16
                counts[bank] += 1
                offsets.append(counts[bank] * duration)
            duration = max(offsets)
        if tag is not None:
            tag = dict(tag, block_completion_ticks=offsets)
        return {"queue": queue, "resources": resources, "latency": duration, "tag": tag}

    def packet(self, name, src, dst, noc, *, payload_src=(), payload_dst=(), deps=(),
               packet_class=0, kind="write_request", immediate=None, src_dram=False, dst_dram=False):
        size = 16 * len(payload_src)
        if immediate is not None:
            if len(payload_dst) != 1:
                raise ValueError("immediate is one16B block")
            size = 0  # immediate32 is carried by one header; destination16B write is still charged
        elif len(payload_src) != len(payload_dst):
            raise ValueError("different source/destination length")
        if size > 8192 or size % 16:
            raise ValueError("single aligned packet required")
        prep_cycles = self.params["niu_processing_cycles"]
        prep = self.add(name + "/prepare", [{"queue": self.queue(f"prepare/{name}"),
            "resources": {f"niu_prepare/{coord(src)}/{noc}": self.ticks(prep_cycles)} if prep_cycles else {},
            "latency": self.ticks(prep_cycles)}], deps=deps)
        ndata = (size + 31) // 32
        vc0 = packet_class << 1
        edges = route(src, dst, noc)
        packet_ends, reads, writes = [], [], []
        link_names = []
        for f in range(ndata + 1):
            jid = f"{name}/f{f:03}"
            srcblocks = list(payload_src[(f-1)*2:f*2]) if f else []
            dstblocks = list(payload_dst[(f-1)*2:f*2]) if f else ([] if immediate is None else list(payload_dst))
            q0 = self.queue(f"source_work/{coord(src)}/{noc}/{vc0}")
            readtag = {"kind": "read", "blocks": srcblocks, "value_key": jid} if srcblocks else None
            ops = [self.memory_op(q0, src, srcblocks, noc=noc, write=False, dram=src_dram, tag=readtag)]
            if srcblocks:
                reads.append(f"{jid}:0")
            q = self.vc_queue(f"niu_out/{coord(src)}/{noc}", vc0, router=False)
            link = f"link/{noc}/niu({coord(src)})->r({coord(src)})"
            ops.append({"queue": q, "resources": {link: TICKS}, "latency": 5*TICKS, "lock": f"{link}/vc{vc0}"})
            link_names_f = [link]
            q = self.vc_queue(f"router_in/{noc}/{coord(src)}/niu", vc0, router=True)
            vc = vc0
            for a, b, axis, dateline in edges:
                next_vc = (dateline << 3) | vc0
                link = f"link/{noc}/r({coord(a)})->r({coord(b)})"
                ops.append({"queue": q, "resources": {link: TICKS}, "latency": 9*TICKS, "lock": f"{link}/vc{next_vc}"})
                link_names_f.append(link)
                q = self.vc_queue(f"router_in/{noc}/{coord(b)}/axis{axis}", next_vc, router=True)
                vc = next_vc
            link = f"link/{noc}/r({coord(dst)})->niu({coord(dst)})"
            ops.append({"queue": q, "resources": {link: TICKS}, "latency": 5*TICKS, "lock": f"{link}/vc{vc}"})
            link_names_f.append(link)
            q = self.vc_queue(f"niu_in/{coord(dst)}/{noc}", vc, router=False)
            writetag = ({"kind": "write", "blocks": dstblocks, "value_key": jid,
                         "immediate": immediate} if dstblocks else None)
            ops.append(self.memory_op(q, dst, dstblocks, noc=noc, write=True, dram=dst_dram, tag=writetag))
            end = self.add(jid, ops, deps=[prep], packet=name, flit=f, tail=f == ndata)
            packet_ends.append(end)
            if dstblocks:
                writes.append(end)
            link_names = link_names_f
        self.packets.append({"id": name, "kind": kind, "src": list(src), "dst": list(dst), "noc": noc,
            "payload_bytes": size if immediate is None else 4, "network_flits": ndata+1,
            "class": packet_class, "links": link_names, "read_ops": reads, "write_ops": writes})
        return {"done": packet_ends, "read": reads, "write": writes}

    def transaction(self, name, src, dst, noc, srcblocks, dstblocks, *, deps=(), read=False,
                    scope="peer", immediate=None, src_dram=False, dst_dram=False):
        initiator = dst if read else src
        scope_key = (tuple(initiator), noc, scope)
        prior = self.scope_previous.get(scope_key)
        issue = self.signal(name+"/issue", list(deps)+([prior] if prior else []), tile=initiator,
                            noc=noc, cycles=4, primitive="command_issue")
        if read:
            request = self.packet(name+"/request", dst, src, noc, deps=[issue], kind="read_request")
            data = self.packet(name+"/response", src, dst, noc, deps=request["done"],
                payload_src=srcblocks, payload_dst=dstblocks, packet_class=3,
                kind="read_response", src_dram=src_dram, dst_dram=dst_dram)
            visible = self.signal(name+"/visible", data["done"])
            ack = self.signal(name+"/observed", [visible], tile=initiator, noc=noc,
                              cycles=2, primitive="local_completion_observe")
        else:
            data = self.packet(name+"/data", src, dst, noc, deps=[issue], payload_src=srcblocks,
                payload_dst=dstblocks, packet_class=1 if immediate is not None else 0,
                kind="notification" if immediate is not None else "write_request",
                immediate=immediate, src_dram=src_dram, dst_dram=dst_dram)
            visible = self.signal(name+"/visible", data["done"])
            feedback = self.packet(name+"/ack", dst, src, noc, deps=[visible], packet_class=3, kind="write_ack")
            ack = self.signal(name+"/observed", feedback["done"], tile=initiator, noc=noc,
                              cycles=2, primitive="local_completion_observe")
        source = self.signal(name+"/source_last_read", data["read"] or [issue])
        local_release = self.signal(name+"/source_observed", [source], tile=src, noc=noc,
                                    cycles=2, primitive="local_completion_observe") if not read else source
        self.scope_previous[scope_key] = ack
        return {"issue": issue, "visible": visible, "observed": ack,
                "source_last_read": source, "source_observed": local_release}

    def observe(self, name, tile, blocks, epoch, *, deps, noc):
        read = self.add(name+"/read", [self.memory_op(self.queue(f"control_read/{name}"), tile,
            blocks, noc=noc, write=False, local=True,
            tag={"kind": "observe", "blocks": blocks, "expected_epoch": epoch})], deps=deps)
        return self.signal(name, [read], tile=tile, noc=noc, cycles=2,
                           primitive="receive_notification_observe")

    def compute(self, name, tile, srcblocks, dstblocks, *, deps, transform):
        reads = []
        keys = []
        for index in range(0, len(srcblocks), 2):
            jid = f"{name}/read{index//2:03}"
            keys.append(jid)
            tag = {"kind": "read", "blocks": srcblocks[index:index+2], "value_key": jid}
            reads.append(self.add(jid, [self.memory_op(self.queue(f"local_reads/{coord(tile)}"), tile,
                srcblocks[index:index+2], noc=0, write=False, local=True, tag=tag)], deps=deps))
        lastread = self.signal(name+"/last_read", reads)
        duration = self.ticks(Fraction(32, 1) / Fraction(str(self.params["eta_c"])))
        calc = self.add(name+"/calc", [{"queue": self.queue(f"compute/{coord(tile)}"),
            "resources": {f"compute/{coord(tile)}": duration}, "latency": duration,
            "tag": {"kind": "compute", "inputs": keys, "output": name, "transform": transform}}], deps=reads)
        writes = []
        for index in range(0, len(dstblocks), 2):
            jid = f"{name}/write{index//2:03}"
            tag = {"kind": "compute_write", "blocks": dstblocks[index:index+2],
                   "value_key": name, "offset": index}
            writes.append(self.add(jid, [self.memory_op(self.queue(f"local_writes/{coord(tile)}"), tile,
                dstblocks[index:index+2], noc=0, write=True, local=True, tag=tag)], deps=[calc]))
        done = self.signal(name+"/published", writes, tile=tile, cycles=2, primitive="publish")
        return {"done": done, "last_read": lastread}


def small_plan_space():
    tiles = [tuple(c) for c in HARDWARE["active_tiles_4"]]
    result = []
    for producers in ((tiles[0], tiles[1]), (tiles[2], tiles[3])):
        consumers = [t for t in tiles if t not in producers]
        for order, placement, nocs in product(permutations(consumers),
                ("same_channel_alias", "same_group_other_channel", "separate_group"), product((0,1), repeat=3)):
            for offset, source_wait in product((0,32,64), ("source", "ack")):
                result.append({"id": f"p{len(result):04}", "producers": [list(t) for t in producers],
                    "consumers": [list(t) for t in order], "placement": placement, "nocs": list(nocs),
                    "chain1_offset_cycles": offset, "source_wait": source_wait})
    return result


def micro_graph(plan, params=None, *, payload_bytes=1024, generations=2,
                tie_break="ascending", bank_layout="interleaved"):
    b = Builder(params, tie_break=tie_break, bank_layout=bank_layout)
    refs = []
    for chain in range(2):
        prod, cons = plan["producers"][chain], plan["consumers"][chain]
        endpoint = (0,0) if chain == 0 else ((0,5) if plan["placement"] == "separate_group" else (0,1))
        channel_offset = 2**30 if chain == 1 and plan["placement"] == "same_group_other_channel" else 0
        src = b.span(prod, 0x10000, payload_bytes)
        recv = b.span(cons, 0x20000, payload_bytes)
        result = b.span(cons, 0x30000, payload_bytes)
        notice = b.span(cons, 0x40000, 16)
        token = b.span(prod, 0x40000, 16)
        b.memory.update({key: -1 for key in src+recv+result+notice+token})
        previous = None
        for epoch in range(generations):
            stem = f"c{chain}e{epoch}"
            inputblocks = b.span(endpoint, channel_offset+chain*0x10000+epoch*0x1000, payload_bytes, dram=True)
            outputblocks = b.span((0,5), 0x100000+(chain*generations+epoch)*0x1000, payload_bytes, dram=True)
            values = [(chain+1)*1_000_000 + epoch*10_000 + i for i in range(len(inputblocks))]
            b.memory.update(zip(inputblocks, values))
            b.expected.update(zip(outputblocks, [2*x+3 for x in values]))
            wait = [] if previous is None else [previous["peer"]["source_observed" if plan["source_wait"] == "source" else "observed"]]
            if chain == 1 and epoch == 0 and plan["chain1_offset_cycles"]:
                wait.append(b.signal(stem+"/window", [], cycles=plan["chain1_offset_cycles"], primitive="timer"))
            load = b.transaction(stem+"/load", endpoint, prod, plan["nocs"][0], inputblocks, src,
                                 deps=wait, read=True, scope="load", src_dram=True)
            compute = b.compute(stem+"/producer", prod, src, src, deps=[load["observed"]], transform="times2")
            peer_deps = [compute["done"]] + ([] if previous is None else [previous["token_ready"]])
            peer = b.transaction(stem+"/peer", prod, cons, plan["nocs"][1], src, recv, deps=peer_deps)
            notify = b.transaction(stem+"/notify", prod, cons, plan["nocs"][1], [], notice,
                                    deps=[peer["observed"]], scope="notify", immediate=epoch)
            ready = b.observe(stem+"/consumer_ready", cons, notice, epoch,
                              deps=[notify["visible"]], noc=plan["nocs"][1])
            cons_deps = [ready] + ([] if previous is None else [previous["output"]["source_observed"]])
            consumer = b.compute(stem+"/consumer", cons, recv, result, deps=cons_deps, transform="plus3")
            returned = b.transaction(stem+"/token", cons, prod, plan["nocs"][1], [], token,
                                     deps=[consumer["last_read"]], scope="token", immediate=epoch)
            token_ready = b.observe(stem+"/token_ready", prod, token, epoch,
                                    deps=[returned["visible"]], noc=plan["nocs"][1])
            output = b.transaction(stem+"/output", cons, (0,5), plan["nocs"][2], result, outputblocks,
                                   deps=[consumer["done"]], scope="output", dst_dram=True)
            previous = {"peer": peer, "token_ready": token_ready, "output": output}
            refs.append({"chain": chain, "epoch": epoch, "load": load, "peer": peer,
                         "notify": notify, "consumer": consumer, "output": output,
                         "consumer_ready": ready, "token_ready": token_ready})
    b.spec["metadata"] = {"plan": deepcopy(plan), "params": b.params, "bank_layout": bank_layout, "tags": b.tags,
        "events": b.events, "memory_initial": b.memory, "memory_expected": b.expected,
        "packets": b.packets, "refs": refs, "payload_bytes": payload_bytes,
        "l1_payload_span_bytes": 6*payload_bytes + 4*16,
        "code_control_reserve_per_tile": 65536, "rf_scratch_per_tile": 2048,
        "claim": "declared micro DFG only; not full MLP or native execution"}
    return b.spec


def audit_values(spec, execution):
    metadata = spec["metadata"]
    memory = dict(metadata["memory_initial"])
    values = {}
    failures = []
    records = []
    for index, op in enumerate(execution["operations"]):
        tag = metadata["tags"].get(op["id"])
        if tag and "block_completion_ticks" in tag:
            for block_index, offset in enumerate(tag["block_completion_ticks"]):
                records.append((op["start"]+offset, op["id"], block_index, tag))
        elif tag:
            records.append((op["end"], op["id"], None, tag))
    records.sort(key=lambda item: (item[0], item[1], -1 if item[2] is None else item[2]))
    reads = writes = 0
    for timestamp, op_id, block_index, tag in records:
        kind = tag["kind"]
        if kind == "read":
            values.setdefault(tag["value_key"], [None]*len(tag["blocks"]))
            try:
                values[tag["value_key"]][block_index] = memory[tag["blocks"][block_index]]
            except KeyError as err:
                failures.append({"op": op_id, "uninitialized": str(err)})
                values[tag["value_key"]][block_index] = -999
            reads += 1
        elif kind == "write":
            value = (tag["immediate"] if tag.get("immediate") is not None
                     else values.get(tag["value_key"], [-999]*len(tag["blocks"]))[block_index])
            memory[tag["blocks"][block_index]] = value
            writes += 1
        elif kind == "compute":
            data = [x for key in tag["inputs"] for x in values.get(key, [-999])]
            values[tag["output"]] = [2*x if tag["transform"] == "times2" else x+3 for x in data]
        elif kind == "compute_write":
            value = values.get(tag["value_key"], [])[tag["offset"]+block_index]
            memory[tag["blocks"][block_index]] = value
            writes += 1
        elif kind == "observe":
            actual = memory.get(tag["blocks"][block_index])
            if actual != tag["expected_epoch"]:
                failures.append({"op": op_id, "expected_epoch": tag["expected_epoch"], "actual": actual})
            reads += 1
    for key, expected in metadata["memory_expected"].items():
        if memory.get(key) != expected:
            failures.append({"block": key, "expected": expected, "actual": memory.get(key)})
    timing = {op["id"]: op for op in execution["operations"]}
    for refs in metadata["refs"]:
        if refs["consumer_ready"] in timing and refs["peer"]["visible"] in timing:
            if timing[refs["consumer_ready"]]["end"] < timing[refs["peer"]["visible"]]["end"]:
                failures.append({"kind": "early_consumer", "chain": refs["chain"], "epoch": refs["epoch"]})
    return {"passed": execution["status"] == "ok" and not failures, "checked_output_blocks": len(metadata["memory_expected"]),
            "read_16B_blocks": reads, "written_16B_blocks": writes, "failures": failures[:20]}
