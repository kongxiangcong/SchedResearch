"""Command line entry point for the infrastructure.

    python -m schedinfra.cli plan-check   --m 32
    python -m schedinfra.cli cpu-reference --m 1 32
    python -m schedinfra.cli backend-audit
    python -m schedinfra.cli inventory    --m 32

Every command writes its evidence under ``runs/`` and prints a short summary.
Commands are additive: none of them overwrite an existing run directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analysis import cpu_reference
from .backend.onnxim import OnnximBackend
from .plan.schema import HardwareProfile
from .repo import INFRA_DIR, sha256_json
from .runner import new_run_dir, run_plans
from .workload.qwen_mlp import MLPModule

HARDWARE = INFRA_DIR / "configs" / "hardware" / "onnxim_tpuv4_c4.json"


def _cmd_plan_check(args: argparse.Namespace) -> int:
    backend = OnnximBackend() if args.backend == "onnxim" else None
    out = new_run_dir(f"plan-check-M{args.m}")
    manifest = run_plans(args.m, HARDWARE, out, backend=backend, mode=args.mode)
    for entry in manifest["plans"]:
        print(json.dumps({
            "plan": entry["name"],
            "plan_id": entry["plan_id"],
            "check_ok": entry["check"]["ok"],
            "errors": entry["check"]["error_count"],
            "warnings": entry["check"]["warning_count"],
            "backend_executed": entry["backend"]["executed"],
        }, ensure_ascii=False))
    print(json.dumps({"run_dir": str(out),
                      "host_wall_seconds": manifest["host_wall_seconds"]}, ensure_ascii=False))
    return 0


def _cmd_cpu_reference(args: argparse.Namespace) -> int:
    out = new_run_dir("cpu-reference") / "cpu_reference.json"
    result = cpu_reference.run(args.m, out)
    print(json.dumps({
        "all_passed": result["all_passed"],
        "M": [c["M"] for c in result["cases"]],
        "relative_l2": [c["source_algebra_error"]["relative_l2"] for c in result["cases"]],
        "padded_M": [c["padded_M"] for c in result["cases"]],
        "host_wall_seconds": result["total_host_wall_seconds"],
        "output": str(out),
    }, indent=2, ensure_ascii=False))
    return 0 if result["all_passed"] else 1


def _cmd_backend_audit(args: argparse.Namespace) -> int:
    backend = OnnximBackend()
    audit = backend.source_audit()
    audit["diagnosis"] = backend.diagnose()
    out = new_run_dir("backend-audit")
    out.mkdir(parents=True, exist_ok=True)
    (out / "onnxim_source_audit.json").write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for name, cap in audit["capabilities"].items():
        print(f"{name:42s} {cap['source']:12s} {cap['verified']}")
    print(json.dumps({"output": str(out / "onnxim_source_audit.json"),
                      "source_present": audit["source_present"]}, ensure_ascii=False))
    return 0


def _cmd_inventory(args: argparse.Namespace) -> int:
    module = MLPModule(args.m)
    payload = {"workload": f"qwen3.5-4b.mlp.M{args.m}", "inventory": module.inventory(),
               "identity_hash": sha256_json(module.inventory())}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="schedinfra", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan-check", help="generate plans, check legality, attempt backend execution")
    p.add_argument("--m", type=int, default=32)
    p.add_argument("--backend", choices=["none", "onnxim"], default="onnxim")
    p.add_argument("--mode", choices=["native", "research"], default="research")
    p.set_defaults(func=_cmd_plan_check)

    p = sub.add_parser("cpu-reference", help="independent CPU numerical reference")
    p.add_argument("--m", type=int, nargs="+", default=[1, 32])
    p.set_defaults(func=_cmd_cpu_reference)

    p = sub.add_parser("backend-audit", help="record the ONNXim source capability audit")
    p.set_defaults(func=_cmd_backend_audit)

    p = sub.add_parser("inventory", help="print the sourced workload inventory")
    p.add_argument("--m", type=int, default=32)
    p.set_defaults(func=_cmd_inventory)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
