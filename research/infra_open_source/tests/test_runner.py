"""Fail-closed admission tests for the runner.

The legality checker is a real gate: an illegal plan must never reach
``backend.execute``. These tests use a spy backend that counts calls, and
verify the rejection is consistent between the per-plan entry and the
run-level manifest state.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from schedinfra.plan.generators import naive_layered_plan, resident_pipelined_plan  # noqa: E402
from schedinfra.plan.schema import HardwareProfile  # noqa: E402
from schedinfra.runner import new_run_dir, run_plans  # noqa: E402
from schedinfra.workload.qwen_mlp import MLPModule  # noqa: E402

HW_PATH = Path(__file__).resolve().parents[1] / "configs" / "hardware" / "onnxim_tpuv4_c4.json"


class SpyBackend:
    """Counts executions; an illegal plan must keep the counter at zero."""

    name = "spy"
    upstream_commit = None
    patch_identity = None
    execution_adapter_implemented = True  # it *can* execute - it must still not be called

    def __init__(self) -> None:
        self.calls: list[str] = []

    def capabilities(self):
        return None

    class _Result:
        def as_dict(self):
            return {"backend": "spy", "executed": True, "metrics": {}, "artifacts": [],
                    "blocker": None}

    def execute(self, plan, run_dir):
        self.calls.append(plan.name)
        return self._Result()


def _plans(hardware):
    module = MLPModule(32)
    legal = naive_layered_plan(module, hardware)
    illegal = resident_pipelined_plan(module, hardware)
    # make the second plan illegal: drop the dependency of silu.0 on its producer
    illegal.op("silu.0").deps = ()
    return [legal, illegal]


def test_illegal_plan_never_reaches_the_backend(tmp_path):
    hardware = HardwareProfile.from_file(HW_PATH)
    spy = SpyBackend()
    manifest = run_plans(32, HW_PATH, tmp_path / "run", plans=_plans(hardware), backend=spy)

    assert spy.calls == ["naive_layered"], f"backend saw an illegal plan: {spy.calls}"
    by_name = {e["name"]: e for e in manifest["plans"]}
    rejected = by_name["resident_pipelined"]
    assert rejected["check"]["ok"] is False
    assert rejected["backend"]["executed"] is False
    assert rejected["backend"]["skipped"] == "check_failed"
    # run-level state is consistent with the per-plan rejection
    assert manifest["admission"]["overall"] == "REJECTED"
    assert manifest["admission"]["illegal_plans"] == ["resident_pipelined"]
    assert manifest["admission"]["all_plans_legal"] is False


def test_all_legal_plans_are_admitted_and_executed(tmp_path):
    hardware = HardwareProfile.from_file(HW_PATH)
    module = MLPModule(32)
    spy = SpyBackend()
    plans = [naive_layered_plan(module, hardware), resident_pipelined_plan(module, hardware)]
    manifest = run_plans(32, HW_PATH, tmp_path / "run", plans=plans, backend=spy)
    assert spy.calls == ["naive_layered", "resident_pipelined"]
    assert manifest["admission"]["overall"] == "ADMITTED"


def test_run_identities_are_separate(tmp_path):
    """plan/hardware/contract/backend/policy identities are distinct fields;
    plan_id is not forced to double as the whole-experiment identity."""
    manifest = run_plans(32, HW_PATH, tmp_path / "run", plan_names=["naive_layered"])
    ids = manifest["identities"]
    assert ids["hardware"]["content_sha256"]
    assert ids["contract"]["sha256"]
    assert ids["workload"]["graph_hash"]
    assert "backend" in ids and "policy" in ids
    plan_id = manifest["plans"][0]["plan_id"]
    assert plan_id != ids["workload"]["graph_hash"]


def test_run_directory_is_never_overwritten(tmp_path):
    out = tmp_path / "run"
    run_plans(32, HW_PATH, out, plan_names=["naive_layered"])
    with pytest.raises(FileExistsError):
        run_plans(32, HW_PATH, out, plan_names=["naive_layered"])


def test_new_run_dir_is_unique(tmp_path, monkeypatch):
    monkeypatch.setattr("schedinfra.runner.RUNS_DIR", tmp_path)
    a = new_run_dir("x")
    a.mkdir(parents=True)
    b = new_run_dir("x")
    assert a != b
