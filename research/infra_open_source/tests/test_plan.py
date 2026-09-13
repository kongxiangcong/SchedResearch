"""Tests for the plan IR, the legality checker and the reference generators.

These are infrastructure tests, not research results. They assert that the
machinery rejects illegal plans and accepts legal ones, and that two plans
which differ structurally really are different plans.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from schedinfra.plan.checker import check_plan  # noqa: E402
from schedinfra.plan.generators import naive_layered_plan, resident_pipelined_plan  # noqa: E402
from schedinfra.plan.schema import LEVEL_DRAM, LEVEL_SPAD, HardwareProfile, Placement  # noqa: E402
from schedinfra.workload.qwen_mlp import MLPModule, padded_m  # noqa: E402

HW_PATH = Path(__file__).resolve().parents[1] / "configs" / "hardware" / "onnxim_tpuv4_c4.json"


@pytest.fixture(scope="module")
def hardware() -> HardwareProfile:
    return HardwareProfile.from_file(HW_PATH)


# --------------------------------------------------------------------------
# workload accounting
# --------------------------------------------------------------------------
def test_padding_rule():
    assert padded_m(1) == 32
    assert padded_m(32) == 32
    assert padded_m(33) == 64
    assert padded_m(128) == 128


def test_inventory_matches_frozen_contract():
    """The R13 contract fixes 3 x 2560 x 9216 BF16 weights = 141,557,760 B."""
    module = MLPModule(32)
    assert module.weight_bytes() == 141_557_760
    assert module.logical_macs() == 3 * 32 * 2560 * 9216
    assert module.padded_macs() == module.logical_macs()  # M=32 needs no padding
    # M=1 is padded to 32, so its padded work equals M=32's logical work.
    assert MLPModule(1).padded_macs() == module.logical_macs()


def test_cast_is_charged_even_for_m32():
    cast = MLPModule(32).cast_work()
    assert cast["elements"] == 32 * 9216
    assert cast["logical_read_bytes"] == 32 * 9216 * 4
    assert cast["logical_write_bytes"] == 32 * 9216 * 2


# --------------------------------------------------------------------------
# generators produce legal plans
# --------------------------------------------------------------------------
def test_naive_plan_passes(hardware):
    plan = naive_layered_plan(MLPModule(32), hardware)
    result = check_plan(plan)
    assert result.ok, result.errors


def test_resident_plan_passes(hardware):
    plan = resident_pipelined_plan(MLPModule(32), hardware)
    result = check_plan(plan)
    assert result.ok, result.errors


def test_the_two_plans_are_different_plans(hardware):
    """B1, at the plan level: same workload, same hardware, different plan."""
    naive = naive_layered_plan(MLPModule(32), hardware)
    resident = resident_pipelined_plan(MLPModule(32), hardware)
    assert naive.plan_id != resident.plan_id
    # and the difference is structural, not cosmetic
    assert naive.summary()["resident_bytes_by_level"] != resident.summary()["resident_bytes_by_level"]
    assert len(naive.edges()) != len(resident.edges())


def test_renaming_a_plan_does_not_change_its_identity(hardware):
    a = naive_layered_plan(MLPModule(32), hardware)
    b = naive_layered_plan(MLPModule(32), hardware)
    b.name = "something_else"
    assert a.plan_id == b.plan_id


def test_whole_layer_barrier_is_present_in_naive_only(hardware):
    naive = naive_layered_plan(MLPModule(32), hardware)
    resident = resident_pipelined_plan(MLPModule(32), hardware)
    naive_silu = naive.op("silu.5")
    resident_silu = resident.op("silu.5")
    # naive waits on every gate chunk; resident only on its own
    assert len(naive_silu.deps) == 18
    assert resident_silu.deps == ("gate.5",)


# --------------------------------------------------------------------------
# checker rejects illegal plans (negative cases)
# --------------------------------------------------------------------------
def _naive(hardware) -> "object":
    return naive_layered_plan(MLPModule(32), hardware)


def test_missing_dependency_is_rejected(hardware):
    plan = naive_layered_plan(MLPModule(32), hardware)
    # silu.0 reads G#0; drop the dependency on its producer
    plan.op("silu.0").deps = tuple(d for d in plan.op("silu.0").deps if d != "gate.0")
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "missing_dependency" for e in result.errors)


def test_capacity_overflow_is_rejected(hardware):
    plan = resident_pipelined_plan(MLPModule(32), hardware)
    # inflate one resident chunk beyond the whole scratchpad
    plan.chunks["G#0"].size_bytes = hardware.spad_bytes_per_core + 1
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "capacity_exceeded" for e in result.errors)


def test_premature_slot_reuse_is_rejected(hardware):
    plan = resident_pipelined_plan(MLPModule(32), hardware)
    # force chunk 1 to reuse the slot of a chunk that is still live
    plan.chunks["G#1"].placement = Placement(LEVEL_SPAD, plan.chunks["G#0"].placement.core,
                                             plan.chunks["G#0"].placement.slot)
    plan.chunks["G#1"].reuse_of = "G#0"
    plan.op("gate.1").deps = ()  # remove the order edge that justified reuse
    result = check_plan(plan)
    assert not result.ok
    codes = {e["code"] for e in result.errors}
    assert codes & {"slot_conflict", "premature_reuse", "reuse_without_order_edge"}


def test_reuse_without_an_order_edge_is_rejected(hardware):
    plan = resident_pipelined_plan(MLPModule(32), hardware)
    plan.chunks["S#0"].reuse_of = "G#0"
    plan.chunks["S#0"].placement = Placement(LEVEL_SPAD, plan.chunks["G#0"].placement.core,
                                             plan.chunks["G#0"].placement.slot)
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] in {"premature_reuse", "reuse_without_order_edge", "slot_conflict"}
               for e in result.errors)


def test_dependency_cycle_is_rejected(hardware):
    plan = naive_layered_plan(MLPModule(32), hardware)
    plan.op("gate.0").deps = ("silu.0",)
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "dependency_cycle" for e in result.errors)


def test_unknown_chunk_reference_is_rejected(hardware):
    plan = naive_layered_plan(MLPModule(32), hardware)
    plan.op("gate.0").reads = plan.op("gate.0").reads + (__import__(
        "schedinfra.plan.schema", fromlist=["ChunkRef"]).ChunkRef("does_not_exist", 0),)
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "unknown_chunk" for e in result.errors)


def test_consumer_declaration_mismatch_is_rejected(hardware):
    plan = naive_layered_plan(MLPModule(32), hardware)
    plan.chunks["G#0"].consumers = ()
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "consumer_declaration_mismatch" for e in result.errors)


def test_checker_does_not_mutate_the_plan(hardware):
    plan = naive_layered_plan(MLPModule(32), hardware)
    before = copy.deepcopy(plan.to_dict())
    check_plan(plan)
    assert plan.to_dict() == before
