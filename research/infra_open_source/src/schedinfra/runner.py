"""The repeatable research entry point: plan -> check -> execute -> summarise.

Fail-closed admission
---------------------
The legality checker is a real gate, not a report: when ``check.ok`` is false
for a plan, ``backend.execute`` is **never** called for it. The run manifest
records the rejection, and the run's overall admission state reflects it.

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

Run identity
------------
A run directory is created fresh and never overwritten. Plan, hardware,
numerical contract, backend commit/patch, policy and inputs each carry their
own content identity in the manifest; ``plan_id`` remains the identity of the
plan only, not of the whole experiment.
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
from .plan.lowering import assess_plan
from .plan.schema import HardwareProfile, Plan
from .repo import RUNS_DIR, sha256_file, sha256_json
from .workload.qwen_mlp import MLPModule, contract_identity, workload_identity

GENERATORS = {
    "naive_layered": naive_layered_plan,
    "resident_pipelined": resident_pipelined_plan,
}

GENERATOR_VERSION = "generators.v2"  # v2: naive is a true whole-layer barrier


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


def backend_identity(backend: Any) -> dict[str, Any]:
    if backend is None:
        return {"name": None, "upstream_commit": None, "patch_identity": None,
                "execution_adapter_implemented": False}
    return {
        "name": getattr(backend, "name", "unknown"),
        "upstream_commit": getattr(backend, "upstream_commit", None),
        "patch_identity": getattr(backend, "patch_identity", None),
        "execution_adapter_implemented": getattr(backend, "execution_adapter_implemented", False),
    }


def run_plans(
    m: int,
    hardware_path: Path,
    out_dir: Path,
    plan_names: list[str] | None = None,
    plans: list[Plan] | None = None,
    backend: Any = None,
    mode: str = "research",
) -> dict[str, Any]:
    """Generate (or accept) plans, check them, and execute *legal* ones only.

    ``plans`` allows externally supplied candidates (the B1 story); when None
    the named generators are used. An illegal plan is never executed.
    """
    started = time.perf_counter()
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"run directory {out_dir} is not empty; runs are never overwritten")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "plans").mkdir(exist_ok=True)
    (out_dir / "checks").mkdir(exist_ok=True)

    hardware = HardwareProfile.from_file(hardware_path)
    module = MLPModule(m)
    if plans is None:
        plans = build_plans(module, hardware, plan_names)

    backend_caps = getattr(backend, "capabilities", None)
    if callable(backend_caps):
        backend_caps = backend_caps()

    results = []
    for plan in plans:
        (out_dir / "plans" / f"{plan.name}.json").write_text(plan.to_json(), encoding="utf-8")
        check = check_plan(plan)
        (out_dir / "checks" / f"{plan.name}.json").write_text(
            json.dumps(check.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        admission = assess_plan(plan, check, backend_caps)
        entry: dict[str, Any] = {
            "name": plan.name,
            "plan_id": plan.plan_id,
            "summary": plan.summary(),
            "check": check.as_dict(),
            "admission": admission,
        }
        if not check.ok:
            # Fail closed: an illegal plan never reaches the backend.
            entry["backend"] = {
                "backend": getattr(backend, "name", None),
                "executed": False,
                "skipped": "check_failed",
                "blocker": {"exception": "PlanRejected",
                            "detail": f"plan failed legality check with {len(check.errors)} error(s); "
                                      f"backend.execute was not called"},
            }
        elif backend is not None:
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

    all_legal = all(entry["check"]["ok"] for entry in results)
    manifest = {
        "schema": "schedresearch.infra.run.v2",
        "run_id": out_dir.name,
        "mode": mode,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "admission": {
            "all_plans_legal": all_legal,
            "overall": "ADMITTED" if all_legal else "REJECTED",
            "illegal_plans": [e["name"] for e in results if not e["check"]["ok"]],
        },
        "identities": {
            "workload": workload_identity(m),
            "contract": contract_identity(),
            "hardware": {
                "profile_id": hardware.profile_id,
                "source_path": str(hardware_path),
                "content_sha256": sha256_file(hardware_path),
            },
            "backend": backend_identity(backend),
            "policy": {"mode": mode, "generator_version": GENERATOR_VERSION,
                       "plan_names": plan_names or list(GENERATORS)},
        },
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
    """A unique, never-reused run directory under ``runs/``."""
    stamp = time.strftime("%Y-%m-%dT%H-%M-%SZ", time.gmtime())
    candidate = RUNS_DIR / f"{stamp}_{prefix}"
    suffix = 1
    while candidate.exists():
        candidate = RUNS_DIR / f"{stamp}_{prefix}_{suffix}"
        suffix += 1
    return candidate
