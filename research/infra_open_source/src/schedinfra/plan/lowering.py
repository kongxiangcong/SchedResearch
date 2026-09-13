"""Layered admission assessment for a plan.

Three separate questions, answered separately - a plan v1 document is a
*logical candidate*, never a completed physical execution plan:

1. **logical_semantics** - does the plan pass the legality checker
   (``checker.check_plan``)? This is necessary for everything else.
2. **backend_expressibility** - can a named backend express the features the
   plan uses (residency, explicit slot reuse, remote reads, policy control)?
   Verdicts come from the backend's capability audit and stay labelled with
   their evidence level (``source_only`` until executed).
3. **physical_lowering** - may this plan enter physical lowering *now*?
   Currently the only hard rule: a plan whose ops read on-chip data from a
   different core needs an explicit movement / remote-access contract. No
   contract => ``NOT_READY``. A free remote read is never assumed.
"""

from __future__ import annotations

from typing import Any

from .checker import CheckResult
from .schema import Plan

READY = "READY"
NOT_READY = "NOT_READY"
EXPRESSIBLE_UNVERIFIED = "EXPRESSIBLE_UNVERIFIED"
NOT_EXPRESSIBLE = "NOT_EXPRESSIBLE"

# Plan features and how they map onto audited backend capabilities.
def plan_features(plan: Plan) -> dict[str, Any]:
    on_chip = [c for c in plan.chunks.values() if c.on_chip]
    return {
        "uses_on_chip_residency": bool(on_chip),
        "uses_explicit_slot_reuse": any(c.reuse_of for c in on_chip),
        "remote_reads": plan.remote_reads(),
        "has_movement_contract": bool(plan.metadata.get("movement_contract")),
    }


def assess_physical_lowering(plan: Plan) -> dict[str, Any]:
    features = plan_features(plan)
    remote = features["remote_reads"]
    if remote and not features["has_movement_contract"]:
        return {
            "status": NOT_READY,
            "reason": (
                f"{len(remote)} remote on-chip reads (e.g. {remote[0][0]} reads {remote[0][1]} "
                f"from another core) and no movement/remote-access contract is declared; "
                f"a remote read is never free"
            ),
            "remote_read_count": len(remote),
        }
    if remote:
        return {
            "status": READY,
            "reason": "remote reads are covered by the declared movement contract",
            "remote_read_count": len(remote),
            "movement_contract": plan.metadata["movement_contract"],
        }
    return {"status": READY, "reason": "no remote on-chip reads", "remote_read_count": 0}


def assess_backend_expressibility(plan: Plan, backend_capabilities: dict[str, dict[str, str]] | None) -> dict[str, Any]:
    """Verdict per used feature, from a backend capability audit.

    ``backend_capabilities`` maps capability name -> {"source", "verified",
    "evidence"} (see ``backend/onnxim.py``). ``None`` means no backend is
    configured, in which case expressibility is simply not claimed.
    """
    features = plan_features(plan)
    if backend_capabilities is None:
        return {"status": "NOT_ASSESSED", "reason": "no backend configured", "features": features}

    needed: dict[str, str] = {}
    if features["uses_on_chip_residency"]:
        needed["same_core_cross_operator_residency"] = "cross-operator scratchpad residency"
    if features["uses_explicit_slot_reuse"]:
        needed["explicit_slot_reuse"] = "explicit slot reuse"
    if features["remote_reads"]:
        needed["core_to_core_communication"] = "core-to-core data exchange"

    verdicts: dict[str, dict[str, str]] = {}
    worst = EXPRESSIBLE_UNVERIFIED
    for capability, label in needed.items():
        cap = backend_capabilities.get(capability, {"source": "unknown", "verified": "not_run", "evidence": ""})
        verdicts[capability] = {
            "feature": label,
            "source": cap["source"],
            "verified": cap["verified"],
            "evidence": cap.get("evidence", ""),
        }
        if cap["source"] == "unsupported":
            worst = NOT_EXPRESSIBLE
    return {"status": worst, "features": features, "capability_verdicts": verdicts,
            "note": "verdicts are source-audit level until the backend executes one"}


def assess_plan(plan: Plan, check: CheckResult,
                backend_capabilities: dict[str, dict[str, str]] | None = None) -> dict[str, Any]:
    """The three-layer admission record attached to every plan run."""
    logical = "PASS" if check.ok else "FAIL"
    expressibility = assess_backend_expressibility(plan, backend_capabilities)
    lowering = assess_physical_lowering(plan)
    if not check.ok:
        # A logically illegal plan never reaches the lowering question.
        lowering = {"status": NOT_READY, "reason": "logical semantics failed; lowering not evaluated"}
    return {
        "logical_semantics": logical,
        "backend_expressibility": expressibility,
        "physical_lowering_status": lowering["status"],
        "physical_lowering": lowering,
    }
