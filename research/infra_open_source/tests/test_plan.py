"""Tests for the plan IR, the legality checker and the reference generators.

These are infrastructure tests, not research results. They assert that the
machinery rejects illegal plans and accepts legal ones, and that two plans
which differ structurally really are different plans.

The targeted counterexamples from the previous review round (P writes A,
R1/R2 read A, Q overwrites A's slot) are regression tests here with proper
assertions - not a diagnostic script that always exits zero.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from schedinfra.plan.checker import check_plan  # noqa: E402
from schedinfra.plan.generators import (  # noqa: E402
    naive_layered_plan,
    permute_plan_cores,
    resident_pipelined_plan,
)
from schedinfra.plan.lowering import assess_plan  # noqa: E402
from schedinfra.plan.schema import (  # noqa: E402
    LEVEL_DRAM,
    LEVEL_SPAD,
    Chunk,
    ChunkRef,
    HardwareProfile,
    Plan,
    PlanOp,
    Placement,
)
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
    cast["logical_read_bytes"] == 32 * 9216 * 4
    cast["logical_write_bytes"] == 32 * 9216 * 2


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
    assert naive.summary()["resident_value_bytes_sum"] != resident.summary()["resident_value_bytes_sum"]
    assert len(naive.edges()) != len(resident.edges())


def test_resident_value_bytes_sum_is_not_a_peak(hardware):
    """The renamed summary field is a sum of logical value sizes, nothing else."""
    resident = resident_pipelined_plan(MLPModule(32), hardware)
    summary = resident.summary()
    assert "resident_value_bytes_sum" in summary
    assert "resident_bytes_by_level" not in summary
    # every on-chip chunk counted once, regardless of lifetime or overlap
    expected = sum(c.size_bytes for c in resident.chunks.values() if c.on_chip)
    assert summary["resident_value_bytes_sum"]["spad"] == expected


def test_renaming_a_plan_does_not_change_its_identity(hardware):
    a = naive_layered_plan(MLPModule(32), hardware)
    b = naive_layered_plan(MLPModule(32), hardware)
    b.name = "something_else"
    assert a.plan_id == b.plan_id


def test_naive_is_a_true_whole_layer_barrier(hardware):
    """Every stage waits on the COMPLETE previous stage, not a growing prefix."""
    naive = naive_layered_plan(MLPModule(32), hardware)
    n_chunks = 18  # I // 512
    for j in (0, 5, n_chunks - 1):
        assert len(naive.op(f"silu.{j}").deps) == n_chunks
        assert len(naive.op(f"mul.{j}").deps) == 2 * n_chunks
        assert len(naive.op(f"cast.{j}").deps) == n_chunks
    resident = resident_pipelined_plan(MLPModule(32), hardware)
    assert resident.op("silu.5").deps == ("gate.5",)


def test_core_permutation_is_a_legal_mapping_control_case(hardware):
    """Two plans that differ ONLY in core assignment: real mapping control."""
    base = resident_pipelined_plan(MLPModule(32), hardware)
    cores = hardware.cores
    permutation = [(c + 1) % cores for c in range(cores)]
    permuted = permute_plan_cores(base, permutation)
    assert permuted.plan_id != base.plan_id
    assert check_plan(permuted).ok
    # identical except core fields
    for op_a, op_b in zip(base.ops, permuted.ops):
        assert op_a.id == op_b.id and op_a.deps == op_b.deps
        assert op_b.core == permutation[op_a.core]
    for key in base.chunks:
        a, b = base.chunks[key], permuted.chunks[key]
        if a.on_chip:
            assert b.placement.core == permutation[a.placement.core]
            assert b.placement.slot == a.placement.slot


def test_resident_plan_remote_reads_block_physical_lowering(hardware):
    """down reads A16 from other cores; without a movement contract the plan
    is a logical candidate only and must not default to free remote reads."""
    resident = resident_pipelined_plan(MLPModule(32), hardware)
    check = check_plan(resident)
    admission = assess_plan(resident, check)
    assert admission["logical_semantics"] == "PASS"
    assert admission["physical_lowering_status"] == "NOT_READY"
    assert resident.remote_reads(), "expected remote reads in the resident plan"
    naive = naive_layered_plan(MLPModule(32), hardware)
    admission_naive = assess_plan(naive, check_plan(naive))
    assert admission_naive["physical_lowering_status"] == "READY"


# --------------------------------------------------------------------------
# checker rejects illegal plans (negative cases)
# --------------------------------------------------------------------------
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
    assert codes & {"slot_conflict", "premature_reuse", "reuse_without_order_edge", "unsafe_overwrite"}


def test_reuse_without_an_order_edge_is_rejected(hardware):
    plan = resident_pipelined_plan(MLPModule(32), hardware)
    plan.chunks["S#0"].reuse_of = "G#0"
    plan.chunks["S#0"].placement = Placement(LEVEL_SPAD, plan.chunks["G#0"].placement.core,
                                             plan.chunks["G#0"].placement.slot)
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] in {"premature_reuse", "reuse_without_order_edge", "slot_conflict",
                             "unsafe_overwrite"} for e in result.errors)


def test_dependency_cycle_is_rejected(hardware):
    plan = naive_layered_plan(MLPModule(32), hardware)
    plan.op("gate.0").deps = ("silu.0",)
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "dependency_cycle" for e in result.errors)


def test_unknown_chunk_reference_is_rejected(hardware):
    plan = naive_layered_plan(MLPModule(32), hardware)
    plan.op("gate.0").reads = plan.op("gate.0").reads + (ChunkRef("does_not_exist", 0),)
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "unknown_chunk" for e in result.errors)
    # structured rejection stops later analysis instead of crashing
    assert result.stats.get("analysis_stopped_at") == "structure"


def test_unknown_dep_is_a_structured_rejection_not_a_crash(hardware):
    plan = naive_layered_plan(MLPModule(32), hardware)
    plan.op("gate.0").deps = ("ghost.op",)
    result = check_plan(plan)  # must not raise KeyError
    assert not result.ok
    assert any(e["code"] == "unknown_dep" for e in result.errors)
    assert result.stats.get("analysis_stopped_at") == "structure"


def test_consumer_declaration_mismatch_is_rejected(hardware):
    plan = naive_layered_plan(MLPModule(32), hardware)
    plan.chunks["G#0"].consumers = ()
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "consumer_declaration_mismatch" for e in result.errors)


def test_producer_declaration_mismatch_is_rejected(hardware):
    plan = naive_layered_plan(MLPModule(32), hardware)
    plan.chunks["G#0"].producer = "gate.1"  # writes still say gate.0
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "producer_declaration_mismatch" for e in result.errors)


def test_static_order_must_be_topological(hardware):
    plan = naive_layered_plan(MLPModule(32), hardware)
    order = plan.order()
    # swap a consumer before its producer: still a permutation, not a schedule
    i_gate, i_silu = order.index("gate.0"), order.index("silu.0")
    order[i_gate], order[i_silu] = order[i_silu], order[i_gate]
    plan.static_order = order
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "static_order_not_topological" for e in result.errors)


def test_illegal_values_are_rejected(hardware):
    plan = resident_pipelined_plan(MLPModule(32), hardware)
    plan.chunks["G#0"].size_bytes = 0
    plan.chunks["G#1"].placement = Placement(LEVEL_SPAD, 0, 0, offset=-4)
    plan.op("gate.2").core = hardware.cores + 3
    plan.chunks["U#0"].placement = Placement("l3_cache", 0, 0)
    result = check_plan(plan)
    assert not result.ok
    codes = {e["code"] for e in result.errors}
    assert {"bad_size", "bad_offset", "bad_core", "bad_level"} <= codes
    assert result.stats.get("analysis_stopped_at") == "structure"


def test_checker_does_not_mutate_the_plan(hardware):
    plan = naive_layered_plan(MLPModule(32), hardware)
    before = copy.deepcopy(plan.to_dict())
    check_plan(plan)
    assert plan.to_dict() == before


# --------------------------------------------------------------------------
# The P / R1,R2 / Q counterexample family (partial-order reuse safety)
# --------------------------------------------------------------------------
def _overwrite_case(q_deps: tuple[str, ...], annotate: bool) -> Plan:
    """P writes A to a slot; R1 and R2 both read A; Q writes B over the slot."""
    hw = HardwareProfile(profile_id="counterexample", cores=1,
                         spad_bytes_per_core=1 << 20, accum_bytes_per_core=0)
    a_ref, b_ref = ChunkRef("A", 0), ChunkRef("B", 0)
    chunks = {
        a_ref.key: Chunk(a_ref, 100, "FP32", "P", ("R1", "R2"),
                         Placement(LEVEL_SPAD, 0, 0)),
        b_ref.key: Chunk(b_ref, 100, "FP32", "Q", (),
                         Placement(LEVEL_SPAD, 0, 0),
                         reuse_of=a_ref.key if annotate else None),
    }
    ops = [
        PlanOp("P", "gemm", 0, (), (a_ref,), 0, 25, ()),
        PlanOp("R1", "silu", 0, (a_ref,), (), 0, 25, ("P",)),
        PlanOp("R2", "silu", 0, (a_ref,), (), 0, 25, ("P",)),
        PlanOp("Q", "gemm", 0, (), (b_ref,), 0, 25, q_deps),
    ]
    return Plan(name="overwrite_case", workload_id="counterexample",
                hardware=hw, ops=ops, chunks=chunks,
                static_order=["P", "R1", "R2", "Q"])


def test_overwrite_after_only_one_reader_is_rejected():
    """The old any(...) bug: Q waits for R1 only and was accepted. No longer."""
    plan = _overwrite_case(q_deps=("R1",), annotate=True)
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "unsafe_overwrite" for e in result.errors)


def test_overwrite_after_all_readers_is_accepted():
    plan = _overwrite_case(q_deps=("R1", "R2"), annotate=True)
    result = check_plan(plan)
    assert result.ok, result.errors


def test_overwrite_safety_does_not_need_the_reuse_annotation():
    """Deleting reuse_of must not disable the check: safety is derived from
    the physical level/core/slot/byte-range, not from an optional annotation."""
    plan = _overwrite_case(q_deps=("R1",), annotate=False)
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "unsafe_overwrite" for e in result.errors)


def test_initial_resident_counts_towards_capacity():
    """External on-chip chunks exist before the plan starts and are charged."""
    hw = HardwareProfile(profile_id="tiny", cores=1, spad_bytes_per_core=1000,
                         accum_bytes_per_core=0)
    w_ref = ChunkRef("w", 0)
    chunks = {w_ref.key: Chunk(w_ref, 1500, "BF16", "<external>", (),
                               Placement(LEVEL_SPAD, 0, 0))}
    plan = Plan(name="initial", workload_id="counterexample", hardware=hw,
                ops=[], chunks=chunks)
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "capacity_exceeded" for e in result.errors)


def test_initial_resident_cannot_be_overwritten_while_read():
    hw = HardwareProfile(profile_id="tiny", cores=1, spad_bytes_per_core=1 << 20,
                         accum_bytes_per_core=0)
    w_ref, b_ref = ChunkRef("w", 0), ChunkRef("B", 0)
    chunks = {
        w_ref.key: Chunk(w_ref, 100, "BF16", "<external>", ("R",),
                         Placement(LEVEL_SPAD, 0, 0)),
        b_ref.key: Chunk(b_ref, 100, "BF16", "Q", (), Placement(LEVEL_SPAD, 0, 0)),
    }
    ops = [
        PlanOp("R", "silu", 0, (w_ref,), (), 0, 25, ()),
        PlanOp("Q", "gemm", 0, (), (b_ref,), 0, 25, ()),  # no edge from R
    ]
    plan = Plan(name="initial_overwrite", workload_id="counterexample", hardware=hw,
                ops=ops, chunks=chunks, static_order=["R", "Q"])
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "unsafe_overwrite" for e in result.errors)
