"""Command line entry point for the infrastructure.

    python -m schedinfra.cli plan-check   --m 32
    python -m schedinfra.cli cpu-reference --m 1 32
    python -m schedinfra.cli backend-audit
    python -m schedinfra.cli inventory    --m 32
    python -m schedinfra.cli plan-replay  --style resident
    python -m schedinfra.cli stream-eval  native-smoke | cast-diagnostic | qwen-mlp

Every command writes its evidence under ``runs/`` and prints a short summary.
Commands are additive: none of them overwrite an existing run directory.
``plan-check`` is fail-closed: it exits nonzero when any plan is illegal.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .analysis import cpu_reference, plan_replay
from .backend.onnxim import OnnximBackend
from .backend import stream_static
from .plan.schema import HardwareProfile
from .repo import INFRA_DIR, ROOT, sha256_json
from .runner import new_run_dir, run_plans
from .workload.qwen_mlp import MLPModule

HARDWARE = INFRA_DIR / "configs" / "hardware" / "onnxim_tpuv4_c4.json"
STREAM_VENV_PYTHON = ROOT / "research" / "r12" / ".venv" / "Scripts" / "python.exe"


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
            "logical_semantics": entry["admission"]["logical_semantics"],
            "physical_lowering_status": entry["admission"]["physical_lowering_status"],
            "backend_executed": entry["backend"]["executed"],
        }, ensure_ascii=False))
    print(json.dumps({"run_dir": str(out),
                      "admission": manifest["admission"]["overall"],
                      "host_wall_seconds": manifest["host_wall_seconds"]}, ensure_ascii=False))
    return 0 if manifest["admission"]["all_plans_legal"] else 1


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
                      "execution_adapter_implemented": audit["execution_adapter_implemented"],
                      "source_present": audit["source_present"]}, ensure_ascii=False))
    return 0


def _cmd_inventory(args: argparse.Namespace) -> int:
    module = MLPModule(args.m)
    payload = {"workload": f"qwen3.5-4b.mlp.M{args.m}", "inventory": module.inventory(),
               "identity_hash": sha256_json(module.inventory())}
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _cmd_plan_replay(args: argparse.Namespace) -> int:
    """Functional replay of the tiny fixture plan against the independent oracle."""
    out = new_run_dir(f"plan-replay-{args.style}")
    out.mkdir(parents=True, exist_ok=True)
    result = plan_replay.replay_tiny_fixture(style=args.style, seed=args.seed)
    (out / "replay_result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    print(json.dumps({"output": str(out / "replay_result.json")}, ensure_ascii=False))
    return 0 if result["passed"] else 1


def _cmd_stream_eval(args: argparse.Namespace) -> int:
    """Run the pinned STREAM static evaluation under its own R12 environment."""
    if not STREAM_VENV_PYTHON.is_file():
        print(json.dumps({"passed": False,
                          "blocker": f"R12 STREAM environment missing: {STREAM_VENV_PYTHON}"},
                         ensure_ascii=False))
        return 1
    out = new_run_dir(f"stream-{args.stream_command}")
    command = [str(STREAM_VENV_PYTHON), "-X", "utf8", "-B",
               str(Path(stream_static.__file__)), args.stream_command, "--output", str(out)]
    if args.stream_command == "qwen-mlp":
        command += ["--hardware", args.hardware]
    # The R12 venv is self-contained; an inherited PYTHONPATH (e.g. this
    # host's Python-3.14 site-packages) must not shadow its pinned packages.
    import os

    env = {k: v for k, v in os.environ.items() if k.upper() != "PYTHONPATH"}
    completed = subprocess.run(command, env=env)
    return completed.returncode


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

    p = sub.add_parser("plan-replay", help="functional replay of the tiny fixture plan")
    p.add_argument("--style", choices=["resident", "naive"], default="resident")
    p.add_argument("--seed", type=int, default=20260914)
    p.set_defaults(func=_cmd_plan_replay)

    p = sub.add_parser("stream-eval", help="pinned STREAM analytical static evaluation (R12 env)")
    p.add_argument("stream_command", choices=["native-smoke", "cast-diagnostic", "qwen-mlp"])
    p.add_argument("--hardware", choices=["tpu_like_quad_core", "tpu_v7_ironwood"],
                   default="tpu_v7_ironwood",
                   help="upstream hardware for qwen-mlp (quad-core measured infeasible for the full module)")
    p.set_defaults(func=_cmd_stream_eval)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
