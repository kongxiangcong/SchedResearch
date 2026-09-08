"""Independent review checks for the R12 offline checker; no timing or native claim."""
from __future__ import annotations

import json
from pathlib import Path

import qualification as q


def raw_coordinate_oracle(src: q.Coord, dst: q.Coord, noc: int) -> list[tuple[q.Coord, q.Coord]]:
    """Build routes in each NoC's own raw space, then convert to physical space."""
    def convert(p: q.Coord) -> q.Coord:
        return p if noc == 0 else (9 - p[0], 11 - p[1])

    start, finish = convert(src), convert(dst)
    dx = (finish[0] - start[0]) % 10
    dy = (finish[1] - start[1]) % 12
    if noc == 0:
        points = [((start[0] + i) % 10, start[1]) for i in range(dx + 1)]
        points += [(finish[0], (start[1] + j) % 12) for j in range(1, dy + 1)]
    else:
        points = [(start[0], (start[1] + j) % 12) for j in range(dy + 1)]
        points += [((start[0] + i) % 10, finish[1]) for i in range(1, dx + 1)]
    physical = [convert(p) for p in points]
    return list(zip(physical, physical[1:]))


def check_routes() -> int:
    count = 0
    tiles = [(x, y) for x in range(10) for y in range(12)]
    for src in tiles:
        for dst in tiles:
            for noc in (0, 1):
                assert q.route(src, dst, noc) == raw_coordinate_oracle(src, dst, noc)
                count += 1
    # Request and response move in opposite endpoint directions, but obey
    # the same NoC's directed routing, with payload on the response for reads.
    read = q.packet_accounting([{"kind": "read", "src": (2, 1), "dst": (1, 1), "bytes": 1024, "noc": 0}])
    write = q.packet_accounting([{"kind": "write", "src": (1, 1), "dst": (2, 1), "bytes": 1024, "noc": 0}])
    assert read["router_link_flits"] == 1 + 9 * 33
    assert write["router_link_flits"] == 33 + 9
    assert q.dram_channel((0, 0), 0) == q.dram_channel((0, 1), 0)
    assert q.dram_channel((0, 0), 0) != q.dram_channel((0, 1), 1 << 30)
    return count


def check_events() -> dict:
    dag, obligations = q.graph("native_scoped_contract")
    # A future load writes the source slot incrementally. Waiting only on its
    # load_visible event is insufficient to prevent overwrite before completion.
    for chain in (0, 1):
        assert f"c{chain}.g0.source_read" in q.ancestors(dag, f"c{chain}.g1.load_issue"), "Guard source reuse before issuing the next DMA"
    assert all(before in q.ancestors(dag, after) for before, after, _ in obligations)
    orders = [q.topological(dag, event) for event in dag]
    assert all(q.replay(order)["numeric_ok"] for order in orders)
    overlap = q.topological(dag, "c0.g1.compute")
    assert overlap.index("c0.g1.compute") < overlap.index("c0.g0.ack"), "Do not overconstrain source reuse by destination ACK"
    assert q.replay(overlap)["numeric_ok"]
    return {"prioritized_topological_replays": len(orders), "early_source_reuse_before_prior_ack": True}


def check_plan_addresses() -> int:
    """Capture generated inputs to reject different tensors at alias addresses."""
    actual = q.packet_accounting
    checked = 0

    def checked_accounting(transfers: list[dict]) -> dict:
        nonlocal checked
        reads = [transfer for transfer in transfers if transfer["kind"] == "read"]
        canonical = [(q.dram_channel(t["src"], t.get("address", 0), t["bytes"]), t.get("address", 0)) for t in reads]
        assert len(canonical) == len(set(canonical)), "Distinct chain/generation inputs alias the same DRAM bytes"
        checked += 1
        return actual(transfers)

    q.packet_accounting = checked_accounting
    try:
        q.enumerate_plans()
    finally:
        q.packet_accounting = actual
    return checked


def main() -> None:
    result = {
        "status": "PASS (offline independent review only)",
        "raw_coordinate_oracle_pairs": check_routes(),
        "events": check_events(),
        "candidate_address_checks": check_plan_addresses(),
        "limits": "Conditional DAG proof and scalar data only; no native kernels, partial-byte simulation, physical credits, network liveness or timing validation.",
    }
    output = Path(__file__).resolve().parent / "artifacts" / "independent_checks.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
