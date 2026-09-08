"""Offline all-order event obligations and directed-link accounting, with no clock model.

This is a finite contract checker, not a NoC simulator or a strong compiler.
Ordering edges that require a native backend remain explicit assumptions.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
from itertools import permutations, product
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
Coord = tuple[int, int]  # physical position in NoC0 raw coordinate space
DRAM_GROUPS = (
    ((0, 0), (0, 1), (0, 11)), ((0, 5), (0, 6), (0, 7)),
    ((5, 0), (5, 1), (5, 11)), ((5, 2), (5, 9), (5, 10)),
    ((5, 3), (5, 4), (5, 8)), ((5, 5), (5, 6), (5, 7)),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def route(src: Coord, dst: Coord, noc: int) -> list[tuple[Coord, Coord]]:
    if noc not in (0, 1) or any(not (0 <= c[0] < 10 and 0 <= c[1] < 12) for c in (src, dst)):
        raise ValueError("Expected NoC 0/1 and physical NoC0 raw coordinates")
    current = list(src)
    edges = []
    axes, direction = ((0, 1), 1) if noc == 0 else ((1, 0), -1)
    for axis in axes:
        while current[axis] != dst[axis]:
            old = tuple(current)
            current[axis] = (current[axis] + direction) % (10, 12)[axis]
            edges.append((old, tuple(current)))
    return edges


def dram_channel(endpoint: Coord, address: int, size: int = 1024) -> tuple[int, int]:
    if size <= 0 or address < 0 or address + size > 2**31:
        raise ValueError("Only GDDR6 data space, positive non-crossing spans")
    channel = address // 2**30
    if (address + size - 1) // 2**30 != channel:
        raise ValueError("Split channel-crossing spans before accounting")
    for group, endpoints in enumerate(DRAM_GROUPS):
        if endpoint in endpoints:
            return group, channel
    raise ValueError("Not a DRAM endpoint")


def packet_accounting(transfers: list[dict]) -> dict:
    """Aligned 1..8192B unicast packets; include response/ACK, no notification.

    src/dst identify payload movement, while read requests move dst -> src.
    Counts router-router links only; finite buffers/NIU occupancy not estimated.
    """
    loads = Counter()
    classes = Counter()
    channel_bytes = Counter()
    for transfer in transfers:
        src, dst = transfer["src"], transfer["dst"]
        size, noc, kind = transfer["bytes"], transfer["noc"], transfer["kind"]
        if size <= 0 or size > 8192 or size % 32 or kind not in ("read", "write"):
            raise ValueError("Use aligned positive single packets and read/write")
        packets = ([(dst, src, 1, "read_request"), (src, dst, 1 + size // 32, "read_response")]
                   if kind == "read" else
                   [(src, dst, 1 + size // 32, "write_request"), (dst, src, 1, "write_ack")])
        for start, finish, flits, category in packets:
            classes[category] += flits
            for a, b in route(start, finish, noc):
                loads[(noc, a, b)] += flits
        endpoint = src if kind == "read" else dst
        if any(endpoint in group for group in DRAM_GROUPS):
            channel_bytes[dram_channel(endpoint, transfer.get("address", 0), size)] += size
    return {
        "payload_bytes": sum(t["bytes"] for t in transfers),
        "injected_flits_by_type": dict(sorted(classes.items())),
        "router_link_flits": sum(loads.values()),
        "max_directed_link_flits": max(loads.values(), default=0),
        "links": {str(k): v for k, v in sorted(loads.items())},
        "channel_payload_bytes": {str(k): v for k, v in sorted(channel_bytes.items())},
    }


def topology_checks() -> dict:
    cases = 0
    for src, dst in product(product(range(10), range(12)), repeat=2):
        for noc in (0, 1):
            edges = route(src, dst, noc)
            # Independent closed-form signed torus distance, not reverse path.
            expected = ((dst[0] - src[0]) % 10 + (dst[1] - src[1]) % 12 if noc == 0 else
                        (src[0] - dst[0]) % 10 + (src[1] - dst[1]) % 12)
            require(len(edges) == expected, "route length")
            require(not edges or (edges[0][0] == src and edges[-1][1] == dst), "route endpoints")
            require(len(edges) == len(set(edges)), "route loop")
            cases += 1
    require(route((1, 1), (2, 1), 0) == [((1, 1), (2, 1))], "NoC0 direction")
    require(len(route((2, 1), (1, 1), 0)) == 9, "ACK wraparound")
    require(route((2, 2), (1, 1), 1) == [((2, 2), (2, 1)), ((2, 1), (1, 1))], "NoC1 Y then X")
    require(dram_channel((0, 0), 0) == dram_channel((0, 1), 0), "alias identity")
    require(dram_channel((0, 0), 0) != dram_channel((0, 1), 2**30), "two channels per group")
    require(dram_channel((0, 0), 0) != dram_channel((0, 5), 0), "distinct groups")
    return {"all_pair_route_cases": cases, "status": "PASS", "live_harvest_verified": False}


def enumerate_plans() -> dict:
    """96 static choices for a fixed four-tile full traffic graph, no timing rank.

    End-to-end transfers: load, peer, output. Two generations; each emits 1KiB.
    All initial tensors exist. Input, peer and output NoCs vary jointly.
    Different placements can change byte-hops, hence this is not the equal-hop witness.
    """
    tiles = ((1, 1), (2, 1), (3, 1), (3, 2))
    plans = []
    for producers in (((1, 1), (2, 1)), ((3, 1), (3, 2))):
        consumers = tuple(t for t in tiles if t not in producers)
        for consumer_order in permutations(consumers):
            for placement in ("same_channel_alias", "same_group_other_channel", "separate_group"):
                for nocs in product((0, 1), repeat=3):
                    transfers = []
                    for chain in range(2):
                        endpoint = (0, 0) if chain == 0 else ((0, 5) if placement == "separate_group" else (0, 1))
                        address = (2**30 if chain == 1 and placement == "same_group_other_channel" else 0) + chain * 0x1000
                        for generation in range(2):
                            transfers.extend([
                                {"kind": "read", "src": endpoint, "dst": producers[chain], "bytes": 1024, "address": address + 1024 * generation, "noc": nocs[0]},
                                {"kind": "write", "src": producers[chain], "dst": consumer_order[chain], "bytes": 1024, "noc": nocs[1]},
                                {"kind": "write", "src": consumer_order[chain], "dst": (0, 5), "bytes": 1024, "address": 0x10000 + 1024 * (chain * 2 + generation), "noc": nocs[2]},
                            ])
                    plans.append({"producers": producers, "consumers": consumer_order, "input_placement": placement,
                                  "nocs_load_peer_output": nocs, **packet_accounting(transfers)})
    require(len(plans) == 96, "frozen candidate space")
    require({p["payload_bytes"] for p in plans} == {12288}, "equal work")
    return {"candidate_count": len(plans), "plans": plans,
            "status": "accounting only; no output-visible time, no optimal-plan claim",
            "omits": ["notification and credit-return packets", "NIU links/service", "router credits", "compute and controller times"],
            "min_max_link_flits": min(p["max_directed_link_flits"] for p in plans),
            "max_max_link_flits": max(p["max_directed_link_flits"] for p in plans)}


def graph(mode: str) -> tuple[dict[str, set[str]], list[tuple[str, str, str]]]:
    dag: dict[str, set[str]] = {}
    obligations = []
    stages = ("load_issue", "load_visible", "compute", "write_issue", "accepted", "sent",
              "source_read", "received", "visible", "ack", "notify", "consume", "store_read", "output_visible")
    for c, g in product(range(2), repeat=2):
        name = lambda s: f"c{c}.g{g}.{s}"
        for stage in stages:
            dag[name(stage)] = set()
        for a, b in zip(stages, stages[1:]):
            if (a, b) not in (("ack", "notify"),):
                dag[name(b)].add(name(a))
        wait = "received" if mode == "receive_is_visible" else "source_read" if mode == "source_is_visible" else "ack"
        dag[name("notify")].add(name(wait))
        # receive-slot token: prior consumer has read all input; result has a separate span.
        if g:
            previous = lambda s: f"c{c}.g{g-1}.{s}"
            source_wait = "sent" if mode == "sent_is_source_done" else "source_read"
            # Guard issue, not completion: a DMA can overwrite individual 16B
            # units long before the entire load becomes visible.
            dag[name("load_issue")].add(previous(source_wait))
            dest_wait = "ack" if mode == "ack_releases_destination" else "consume"
            dag[name("write_issue")].add(previous(dest_wait))
            # Separate ID per generation; consumer result span reusable only after store read.
            dag[name("consume")].add(previous("store_read"))
            obligations.extend([(previous("source_read"), name("load_issue"), "source slot reuse"),
                                (previous("consume"), name("write_issue"), "receive slot credit"),
                                (previous("store_read"), name("consume"), "consumer result reuse")])
        obligations.append((name("visible"), name("consume"), "destination visibility"))
    return dag, obligations


def ancestors(dag: dict[str, set[str]], node: str) -> set[str]:
    seen = set()
    pending = list(dag[node])
    while pending:
        item = pending.pop()
        if item not in seen:
            seen.add(item)
            pending.extend(dag[item])
    return seen


def topological(dag: dict[str, set[str]], priority: str | None = None) -> list[str]:
    done = set()
    order = []
    preferred = ancestors(dag, priority) | {priority} if priority else set()
    while len(done) < len(dag):
        ready = [n for n in dag if n not in done and dag[n] <= done]
        require(bool(ready), "cycle / abstract deadlock")
        node = min(ready, key=lambda n: (n not in preferred, n))
        done.add(node)
        order.append(node)
    return order


def replay(order: list[str]) -> dict:
    source, capture, destination, result, outputs = {}, {}, {}, {}, {}
    for event in order:
        chain, generation, stage = event.split(".")
        c, g = int(chain[1:]), int(generation[1:])
        key = c, g
        if stage == "load_visible":
            source[c] = c * 100 + g * 7 + 3
        elif stage == "compute":
            source[c] *= 2
        elif stage == "source_read":
            capture[key] = source[c]
        elif stage == "visible":
            destination[c] = capture[key]
        elif stage == "consume":
            result[c] = destination.get(c, -1000) + 3
        elif stage == "store_read":
            outputs[key] = result[c]
    expected = {(c, g): 2 * (c * 100 + g * 7 + 3) + 3 for c, g in product(range(2), repeat=2)}
    return {"numeric_ok": outputs == expected, "actual": {str(k): v for k, v in outputs.items()},
            "expected": {str(k): v for k, v in expected.items()}}


def event_checks() -> dict:
    results = {}
    for mode in ("native_scoped_contract", "sent_is_source_done", "receive_is_visible", "source_is_visible", "ack_releases_destination"):
        dag, obligations = graph(mode)
        order = topological(dag)
        failures = []
        for before, after, invariant in obligations:
            if before not in ancestors(dag, after):
                # Credit misuse becomes numerical corruption when the newly issued
                # packet commits before the previous consumer reads its receive span.
                target = (after.replace("write_issue", "visible") if invariant == "receive slot credit" else
                          after.replace("load_issue", "load_visible") if invariant == "source slot reuse" else after)
                counterexample = topological(dag, target)
                require(counterexample.index(after) < counterexample.index(before), "must witness missing HB")
                failures.append({"invariant": invariant, "required": [before, after],
                                 "counterexample_order": counterexample, "replay": replay(counterexample)})
        if mode == "native_scoped_contract":
            require(not failures and replay(order)["numeric_ok"], "safe contract")
            early_reuse = topological(dag, "c0.g1.load_visible")
            require(early_reuse.index("c0.g1.load_visible") < early_reuse.index("c0.g0.ack"), "scope must permit early source reuse")
            require(replay(early_reuse)["numeric_ok"], "early source reuse must preserve payload")
        else:
            require(bool(failures), f"mutation must fail: {mode}")
            require(any(not f["replay"]["numeric_ok"] for f in failures), f"numeric counterexample required: {mode}")
        results[mode] = {"events": len(dag), "obligations": len(obligations), "failures": failures,
                         "status": "PASS" if not failures else "EXPECTED_REJECTION", "one_valid_order_replay": replay(order)}
    return {"proof": "For each required A before B, reachability in a finite DAG is equivalent to all linear extensions respecting A before B. Missing edges produce actual legal topological counterexamples, replayed with integer payloads.",
            "limits": "HB proof is conditional on listed backend edges. No claim about physical credit buffers, native CPU memory ordering, partial 16-byte accesses or network deadlock. Payload replay is one exact scalar replicated across a 1KiB span.",
            "result": results}


def evidence_integrity() -> dict:
    package = REPO / "SchedResearch_reassessment_evidence_20260907"
    expected = json.loads((package / "sha256.json").read_text(encoding="utf-8"))
    entries = {}
    for name, digest in expected.items():
        data = (package / name).read_bytes()
        raw = hashlib.sha256(data).hexdigest()
        lf = hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        require(raw == digest or lf == digest, f"Evidence content mismatch: {name}")
        entries[name] = {"expected": digest, "raw_sha256": raw, "lf_sha256": lf,
                         "status": "raw_match" if raw == digest else "LF_content_match_only"}
    spec = importlib.util.spec_from_file_location("frozen_bound", package / "bound_witness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    saved = json.loads((package / "bound_witness_result.json").read_text())
    for key, flows in [("overlapping_plan", [((1,1),(3,1)),((2,1),(3,2))]),
                       ("separated_plan", [((1,1),(2,2)),((2,1),(3,2))])]:
        actual = json.loads(json.dumps(module.request_link_accounting(flows)))
        require(actual == saved["noc_request_link_witness"][key], "Frozen witness replay mismatch")
    return {"package_files": entries, "bound_witness_replayed": True, "historical_performance_rerun": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "qualification.json")
    args = parser.parse_args()
    output = {"schema": "r12.offline-qualification.v1", "evidence_level": "source-derived accounting and conditional functional proof",
              "preregistration_sha256": hashlib.sha256((ROOT / "preregistration.json").read_bytes()).hexdigest(),
              "integrity": evidence_integrity(), "topology": topology_checks(),
              "static_candidates": enumerate_plans(), "events": event_checks(),
              "gates": {"G0_native": "NOT_PASSED", "G1": "NOT_TESTED", "G2": "NOT_TESTED", "G3": "NOT_OPEN"}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    summary = {"schema": output["schema"], "evidence_level": output["evidence_level"],
               "preregistration_sha256": output["preregistration_sha256"], "integrity": output["integrity"],
               "topology": output["topology"], "static_candidates": {k: v for k, v in output["static_candidates"].items() if k != "plans"},
               "events": {k: {"status": v["status"], "events": v["events"], "obligations": v["obligations"],
                                "rejected_obligations": len(v["failures"])} for k, v in output["events"]["result"].items()},
               "gates": output["gates"], "raw_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest()}
    args.output.with_name("qualification_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS (offline scope only)", "routes": output["topology"]["all_pair_route_cases"],
                      "candidates": output["static_candidates"]["candidate_count"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
