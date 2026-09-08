#!/usr/bin/env python3
"""Read-only arithmetic checks and a request-link lower-bound witness.

This is NOT a timing simulator, hardware experiment, or historical experiment rerun.
The NoC example uses raw Wormhole NoC0 coordinates on unharvested tiles and
only its documented X-then-Y request routes without wraparound. It does not
model ACK/response traffic, NIU queues, VC credits, memory service or consumers.
Its lower bounds are NOT predicted module runtimes or achieved speedups.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

Coord = tuple[int, int]
Edge = tuple[Coord, Coord]


def noc0_nonwrapping_path(src: Coord, dst: Coord) -> list[Edge]:
    if not (0 <= src[0] <= dst[0] < 10 and 0 <= src[1] <= dst[1] < 12):
        raise ValueError("This witness only supports non-wrapping NoC0 paths.")
    x, y = src
    edges: list[Edge] = []
    while x < dst[0]:
        nxt = (x + 1, y)
        edges.append(((x, y), nxt))
        x, y = nxt
    while y < dst[1]:
        nxt = (x, y + 1)
        edges.append(((x, y), nxt))
        x, y = nxt
    return edges


def request_link_accounting(flows: list[tuple[Coord, Coord]], payload: int = 1024) -> dict:
    flit_bytes = 32
    if payload <= 0 or payload > 8192 or payload % flit_bytes:
        raise ValueError("Use an aligned, single-packet write payload for this witness.")
    request_flits = 1 + payload // flit_bytes  # one header plus data
    loads: Counter[Edge] = Counter()
    paths = []
    for src, dst in flows:
        route = noc0_nonwrapping_path(src, dst)
        for link in route:
            loads[link] += request_flits
        paths.append({"source_raw_noc0": src, "destination_raw_noc0": dst,
                      "links": route, "request_flits": request_flits})
    return {
        "paths": paths,
        "total_payload_bytes": len(flows) * payload,
        "total_request_flits_injected": len(flows) * request_flits,
        "total_request_link_flits": sum(loads.values()),
        "request_link_loads_flits": {f"{a}->{b}": n for (a, b), n in sorted(loads.items())},
        "request_link_service_lower_bound_cycles_at_1_flit_per_cycle": max(loads.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON output path; no repository files are touched.")
    args = parser.parse_args()
    r9_elapsed = 47776
    r9_lb = Fraction(2998272, 64)
    r11_base, r11_candidate = Fraction("3448328.125"), Fraction("3448868.5")
    overlap = request_link_accounting([((1, 1), (3, 1)), ((2, 1), (3, 2))])
    separated = request_link_accounting([((1, 1), (2, 2)), ((2, 1), (3, 2))])
    assert overlap["total_payload_bytes"] == separated["total_payload_bytes"] == 2048
    assert overlap["total_request_link_flits"] == separated["total_request_link_flits"] == 132
    assert overlap["request_link_service_lower_bound_cycles_at_1_flit_per_cycle"] == 66
    assert separated["request_link_service_lower_bound_cycles_at_1_flit_per_cycle"] == 33
    output = {
        "date": "2026-09-07",
        "evidence_level": "independent arithmetic / request-link bound only",
        "project_commit": "a947b563356610cf4dbb05995debf18fc3054e66",
        "isa_commit": "5287a62727350bcef35f7b411d1b8a706172ec4c",
        "r9": {"elapsed_cycles_reported": r9_elapsed, "external_payload_bytes_reported": 2998272,
               "external_bandwidth_bytes_per_cycle_reported": 64,
               "external_payload_service_lower_bound_cycles_recomputed": float(r9_lb),
               "fixed_traffic_latency_reduction_ceiling_pct_recomputed": float(100 * (r9_elapsed - r9_lb) / r9_elapsed)},
        "r11": {"local_state_bytes_reduction_pct_recomputed": float(100 * (1 - Fraction(4194304, 16777216))),
                "quiet_elapsed_baseline_reported": float(r11_base), "quiet_elapsed_candidate_reported": float(r11_candidate),
                "quiet_latency_reduction_pct_recomputed": float(100 * (r11_base - r11_candidate) / r11_base)},
        "noc_request_link_witness": {
            "overlapping_plan": overlap, "separated_plan": separated,
            "interpretation": "Same injected bytes and total request byte-hops, different maximum directed-link load. An aggregate-byte server cannot preserve this distinction.",
            "limits": "Not an end-to-end timing result, not a 2x speedup claim, not a STREAM comparison. No ACK/response, finite buffer, VC, NIU, DDR or consumer simulation. Raw coordinates require unharvested tile verification on a real device. Only a placement change is demonstrated; no runtime reordering occurs."
        },
    }
    text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)

if __name__ == "__main__":
    main()
