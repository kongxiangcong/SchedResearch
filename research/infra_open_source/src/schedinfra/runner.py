"""The repeatable research entry point: plan -> check -> execute -> summarise.

Two modes are kept separate on purpose:

``native``
    Fixed upstream, nothing patched, no research extensions. Whatever the
    backend does is what upstream does.

``research``
    Named local extensions are enabled. Every extension has to declare itself
    and is recorded in the run manifest.

Both modes share the same public capabilities. A mode switch may never quietly
give one method better storage or communication semantics than another.

If the backend cannot run, the runner records the blocker and stops. It does
not fall back to a stand-in executor, because a green tick from a fake
executor is worse than an honest hole.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .plan.checker import check_plan
from .plan.generators import naive_layered_plan, resident_pipelined_plan
from .plan.schema import HardwareProfile, Plan
from .repo import RUNS_DIR, sha256_file, sha256_json
from .workload.qwen_mlp import MLPModule, contract_identity, workload_identity

GENERATORS = {
    "naive_layered": naive_layered_plan,
    "resident_pipelined": resident_pipelined_plan,
}


def _git_head() -> dict[str, str]:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=15)
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                capture_output=True, text=True, timeout=15)
        return {"commit": out.stdout.strip(), "branch": branch.stdout.strip()}
    except Exception as exc:  # noqa: BLE001
        return {"commit": "", "branch": "", "error": str(exc)}


def build_plans(module: MLPModule, hardware: HardwareProfile, names: list[str] | None = None) -> list[Plan]:
    chosen = names or list(GENERATORS)
    return [GENERATORS[name](module, hardware) for name in chosen]


def run_plans(
    m: int,
    hardware_path: Path,
    out_dir: Path,
    plan_names: list[str] | None = None,
    backend: Any = None,
    mode: str = "research",
) -> dict[str, Any]:
    started = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "plans").mkdir(exist_ok=True)
    (out_dir / "checks").mkdir(exist_ok=True)

    hardware = HardwareProfile.from_file(hardware_path)
    module = MLPModule(m)
    plans = build_plans(module, hardware, plan_names)

    results = []
    for plan in plans:
        (out_dir / "plans" / f"{plan.name}.json").write_text(plan.to_json(), encoding="utf-8")
        check = check_plan(plan)
        (out_dir / "checks" / f"{plan.name}.json").write_text(
            json.dumps(check.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        entry: dict[str, Any] = {
            "name": plan.name,
            "plan_id": plan.plan_id,
            "summary": plan.summary(),
            "check": check.as_dict(),
        }
        if backend is not None:
            try:
                backend_result = backend.execute(plan, out_dir / "backend" / plan.name)
                entry["backend"] = backend_result.as_dict()
            except Exception as exc:  # noqa: BLE001 - record, never fake
                entry["backend"] = {
                    "backend": getattr(backend, "name", "unknown"),
                    "executed": False,
                    "blocker": {"exception": type(exc).__name__, "detail": str(exc)},
                }
        else:
            entry["backend"] = {"backend": None, "executed": False,
                                "blocker": {"exception": "NoBackendConfigured",
                                            "detail": "no executable backend is available in this environment"}}
        results.append(entry)

    manifest = {
        "schema": "schedresearch.infra.run.v1",
        "run_id": out_dir.name,
        "mode": mode,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workload": workload_identity(m),
        "contract": contract_identity(),
        "hardware_profile": asdict(hardware) | {"source_path": str(hardware_path)},
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "host_wall_seconds": None,
        },
        "git": _git_head(),
        "plans": results,
        "host_wall_seconds": round(time.perf_counter() - started, 3),
    }
    manifest["environment"]["host_wall_seconds"] = manifest["host_wall_seconds"]
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    return manifest


def new_run_dir(prefix: str) -> Path:
    stamp = time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    return RUNS_DIR / f"{stamp}_{prefix}"
