"""Limited request-flow projection into R13 F and the already installed tt-npe.

No ACK/notification, DFG lifecycle, or DRAM validation is inferred from this
comparison. NPE Transfer is its API transaction abstraction, not an expanded
flit/response trace. This script never installs tools or adjusts parameters to
match estimates. The Linux entry point runs inside the existing R12 WSL distro.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parent
PAIRS = {
    "overlap": [((1, 1), (3, 1)), ((2, 1), (3, 2))],
    "separated": [((1, 1), (2, 2)), ((2, 1), (3, 2))],
}
TIMESTEPS = [32, 64, 128, 256]
MARKER = "R13_NPE_PROJECTION_JSON="


def cases():
    return [{"id": f"{shape}_{size}B_{count}flow", "shape": shape,
             "payload_bytes_per_flow": size, "flows": count, "noc": 0,
             "transfers": [{"src_xy": list(src), "dst_xy": list(dst)}
                           for src, dst in pairs[:count]]}
            for size in (1024, 8192) for count in (1, 2) for shape, pairs in PAIRS.items()]


def direct_paths(case):
    """Independently construct the positive-x then positive-y request edges."""
    paths = []
    for transfer in case["transfers"]:
        x, y = transfer["src_xy"]
        dx, dy = transfer["dst_xy"]
        edges = []
        for _ in range((dx - x) % 10):
            nx = (x + 1) % 10
            edges.append(((x, y), (nx, y)))
            x = nx
        for _ in range((dy - y) % 12):
            ny = (y + 1) % 12
            edges.append(((x, y), (x, ny)))
            y = ny
        paths.append(edges)
    return paths


def classify(delta):
    return "overlap_slower" if delta > 0 else "neutral" if delta == 0 else "overlap_faster"


def linux_npe():
    result = {"status": "failed", "rows": [], "hardware_measurement": False,
              "input_level": "one npe.Transfer API transaction per write-like Tensix-to-Tensix flow, num_packets=1; no manual request/ACK expansion"}
    try:
        import tt_npe_pybind as npe
        binary = Path(npe.__file__).resolve()
        expected = Path("/opt/schedresearch-r12/install/tt-npe/lib").resolve()
        if not binary.is_relative_to(expected):
            raise RuntimeError(f"Unexpected NPE binary {binary}")
        result["module"] = str(binary)
        result["module_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
        for timestep in TIMESTEPS:
            for case in cases():
                cfg = npe.Config()
                cfg.device_name = "wormhole_b0"
                cfg.congestion_model_name = "fast"
                cfg.cycles_per_timestep = timestep
                cfg.infer_injection_rate_from_src = True
                cfg.set_verbosity_level(0)
                workload = npe.Workload()
                phase = npe.Phase()
                for transfer in case["transfers"]:
                    sx, sy = transfer["src_xy"]
                    dx, dy = transfer["dst_xy"]
                    # Coord is device,row,column: y precedes x.
                    phase.addTransfer(npe.Transfer(case["payload_bytes_per_flow"], 1,
                        npe.Coord(0, sy, sx), npe.Coord(0, dy, dx), 0, 0, npe.NocType.NOC_0))
                workload.addPhase(phase)
                api = npe.InitAPI(cfg)
                if api is None:
                    raise RuntimeError("NPE InitAPI returned None")
                stats = api.runNPE(workload)
                if not isinstance(stats, npe.Stats):
                    raise RuntimeError(f"NPE did not return Stats: {stats}")
                devices = {str(device): {"completed": state.completed,
                    "estimated_cycles": state.estimated_cycles,
                    "estimated_cong_free_cycles": state.estimated_cong_free_cycles,
                    "overall_avg_noc0_link_util": state.overall_avg_noc0_link_util}
                    for device, state in stats.per_device_stats.items()}
                if len(devices) != 1 or not all(row["completed"] for row in devices.values()):
                    raise RuntimeError(f"NPE did not complete the one-device workload: {devices}")
                result["rows"].append({"case_id": case["id"], "cycles_per_timestep": timestep,
                                       "devices": devices})
        result["status"] = "executed"
    except Exception as error:
        result["error"] = {"type": type(error).__name__, "message": str(error),
                           "traceback": traceback.format_exc()}
    print(MARKER + json.dumps(result, ensure_ascii=False), flush=True)
    return result


def run_f():
    from event_machine import simulate
    from model_builder import Builder, TICKS
    rows = []
    for case in cases():
        builder = Builder()
        finals = []
        for index, transfer in enumerate(case["transfers"]):
            size = case["payload_bytes_per_flow"]
            src, dst = transfer["src_xy"], transfer["dst_xy"]
            source = builder.span(src, 0x10000, size)
            target = builder.span(dst, 0x20000, size)
            # Raw request projection: one packet, one header, payload flits,
            # source/target memory service. Deliberately no transaction wrapper.
            packet = builder.packet(f"flow{index}", src, dst, 0,
                                    payload_src=source, payload_dst=target)
            finals.extend(packet["done"])
        execution = simulate(builder.spec)
        end = {operation["id"]: operation["end"] for operation in execution["operations"]}
        paths = direct_paths(case)
        counts = Counter(edge for path in paths for edge in path)
        actual_network = sum(value for resource, value in execution["resource_launches"].items()
                             if resource.startswith("link/"))
        flits = case["payload_bytes_per_flow"] // 32 + 1
        expected_network = sum((len(path) + 2) * flits for path in paths)
        expected_router = sum(len(path) * flits for path in paths)
        actual_router = sum(value for resource, value in execution["resource_launches"].items()
                            if resource.startswith("link/") and "niu(" not in resource)
        rows.append({"case": case, "status": execution["status"],
            "request_target_visible_ticks": max(end[operation] for operation in finals),
            "request_target_visible_model_cycles": max(end[operation] for operation in finals) / TICKS,
            "quiescent_ticks": execution["quiescent"],
            "request_router_edges": [[[list(a), list(b)] for a, b in path] for path in paths],
            "request_payload_byte_hops": sum(len(path) * case["payload_bytes_per_flow"] for path in paths),
            "request_flit_hops_including_header": expected_router,
            "network_flit_hops_including_niu": expected_network,
            "shared_router_edges": [[list(a), list(b)] for (a, b), count in counts.items() if count > 1],
            "actual_router_launches": actual_router,
            "actual_all_network_launches": actual_network,
            "ledger_passed": actual_network == expected_network and actual_router == expected_router,
            "packet_kinds": [packet["kind"] for packet in builder.packets]})
    return rows


def decode_process(raw):
    # wsl.exe service errors on this host are UTF-16LE; native Python output is
    # UTF-8. Retain both decoded text and raw byte hashes in the receipt.
    return raw.decode("utf-16le" if raw.count(b"\0") > len(raw) // 4 else "utf-8", errors="replace")


def host_main():
    files = [ROOT / "npe_projection.py", ROOT / "model_builder.py", ROOT / "event_machine.py",
             ROOT / "hardware_model.json", ROOT.parent / "r12/deps/tt-npe/tt_npe/cpp/include/device_models/wormhole_b0.hpp",
             ROOT.parent / "r12/deps/tt-npe/tt_npe/cpp/pybind/bindings.cpp"]
    hashes_before = {str(path.relative_to(ROOT.parent.parent)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in files}
    rows = run_f()
    drive = ROOT.drive.rstrip(":").lower()
    linux_script = f"/mnt/{drive}/" + "/".join(ROOT.parts[1:]) + "/npe_projection.py"
    command = ["wsl.exe", "-d", "SchedResearch-R12", "--exec", "/usr/bin/env",
               "PYTHONPATH=/opt/schedresearch-r12/install/tt-npe/lib",
               "/opt/schedresearch-r12/venv-npe/bin/python", "-X", "utf8", "-B", linux_script, "--linux-npe"]
    process_info = {"command": command}
    npe_result = {"status": "not_executed", "rows": []}
    try:
        process = subprocess.run(command, capture_output=True, timeout=60, check=False)
        stdout, stderr = decode_process(process.stdout), decode_process(process.stderr)
        process_info.update(returncode=process.returncode, stdout=stdout, stderr=stderr,
                            stdout_sha256=hashlib.sha256(process.stdout).hexdigest(),
                            stderr_sha256=hashlib.sha256(process.stderr).hexdigest())
        candidates = [line[len(MARKER):] for line in stdout.splitlines() if line.startswith(MARKER)]
        if candidates:
            npe_result = json.loads(candidates[-1])
        else:
            npe_result["reason"] = "WSL process did not reach the NPE probe; see captured process error"
    except Exception as error:
        process_info["error"] = {"type": type(error).__name__, "message": str(error)}
        npe_result["reason"] = "WSL invocation failed before returning a NPE result"

    contrasts = []
    for size in (1024, 8192):
        for count in (1, 2):
            sides = {shape: next(row for row in rows if row["case"]["id"] == f"{shape}_{size}B_{count}flow")
                     for shape in PAIRS}
            delta_ticks = sides["overlap"]["request_target_visible_ticks"] - sides["separated"]["request_target_visible_ticks"]
            delta = delta_ticks / 36
            contrast = {"payload_bytes_per_flow": size, "flows": count,
                        "F_overlap_minus_separated_ticks": delta_ticks,
                        "F_overlap_minus_separated_cycles": delta, "F_trend": classify(delta_ticks),
                        "equal_request_byte_hops": sides["overlap"]["request_payload_byte_hops"] == sides["separated"]["request_payload_byte_hops"],
                        "NPE": [], "cross_tool_trend": "not_executed"}
            if npe_result["status"] == "executed":
                for step in TIMESTEPS:
                    estimates = {shape: next(row for row in npe_result["rows"] if row["case_id"] == f"{shape}_{size}B_{count}flow"
                                             and row["cycles_per_timestep"] == step)["devices"]["0"]["estimated_cycles"]
                                 for shape in PAIRS}
                    npe_delta = estimates["overlap"] - estimates["separated"]
                    contrast["NPE"].append({"cycles_per_timestep": step,
                                            "overlap_minus_separated_cycles": npe_delta,
                                            "trend": classify(npe_delta), "estimated_cycles": estimates,
                                            "trend_agrees_with_F": classify(npe_delta) == classify(delta)})
                contrast["cross_tool_trend"] = "all_tested_timesteps_agree" if all(row["trend_agrees_with_F"] for row in contrast["NPE"]) else "neutral_or_disagreement_present"
            contrasts.append(contrast)
    hashes_after = {str(path.relative_to(ROOT.parent.parent)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in files}
    report = {"schema": "r13.npe-request-projection.v1", "created_utc": datetime.now(timezone.utc).isoformat(),
              "command": "research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/npe_projection.py",
              "passed": npe_result["status"] == "executed" and hashes_before == hashes_after,
              "cross_tool_status": npe_result["status"], "source_hashes": hashes_before,
              "source_unchanged_during_run": hashes_before == hashes_after,
              "F_rows": rows, "contrasts": contrasts, "NPE": npe_result, "process": process_info,
              "scope": {"common": "Tensix-to-Tensix unicast NoC0 request payload, fixed endpoints, 1 or 2 simultaneous flows, 1KiB/8KiB; compare only coarse congestion trend",
                        "F": "expanded one-header-plus-data-flit request with source/target L1 service, finite VC/NIU queues, nominal parameters, no ACK/notice; target-visible and credit-quiescent are separate",
                        "NPE": "one API Transfer per flow, num_packets=1, inferred source injection, fast congestion model; no manual ACK/response/header expansion, no trusted native golden",
                        "not_compared": "real hardware accuracy, full transaction completion, remote visibility, epoch/slot lifecycle, DRAM, DFG, or compiler speedup",
                        "parameters": "F parameters unchanged; NPE timestep 32/64/128/256 all preregistered by this script; no fitting or tuning"},
              "route_source_check": {"status": "source_read_not_runtime_route_output",
                                     "source": "research/r12/deps/tt-npe/tt_npe/cpp/include/device_models/wormhole_b0.hpp:320-356",
                                     "result": "fixed C++ NoC0 increments col then row, NoC1 decrements row then col; mapped Coord(device,row=y,col=x); matches declared directional paths",
                                     "api_source": "research/r12/deps/tt-npe/tt_npe/cpp/pybind/bindings.cpp:262-289",
                                     "unfitted_cost_difference": "fixed NPE table: 1024B transfer bandwidth27.4 and8192B30.0 B/cycle, WORKER injection28.1; F nominal NIU efficiency0.75 plus explicit finite queue/credit. These are different contracts; no numeric matching criterion."}}
    destination = ROOT / "artifacts" / "npe_projection.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"cross_tool_status": report["cross_tool_status"], "F_cases": len(rows),
                      "F_all_ledger_passed": all(row["ledger_passed"] for row in rows),
                      "source_unchanged": report["source_unchanged_during_run"], "output": str(destination)}, ensure_ascii=False))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linux-npe", action="store_true")
    args = parser.parse_args()
    if args.linux_npe:
        outcome = linux_npe()
        raise SystemExit(0 if outcome["status"] == "executed" else 1)
    host_main()
