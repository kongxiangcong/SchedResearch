"""Functional replay tests: the plan's own chunk accesses, against an oracle.

The replay consumes the *plan* - its ops, deps, chunks, placements and slot
overwrites - and compares values against an independent algebraic oracle.
It deliberately produces no cycles and no bandwidth. Mutations of shard
sources, write ranges, the cast, or reuse dependencies must be caught either
by the checker or by the replay itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from schedinfra.analysis.plan_replay import (  # noqa: E402
    PlanReplay,
    ReplayIncapable,
    build_tiny_mlp_plan,
    compare,
    oracle_mlp,
    replay_tiny_fixture,
    tiny_external_values,
)
from schedinfra.plan.checker import check_plan  # noqa: E402
from schedinfra.plan.schema import ChunkRef  # noqa: E402


# --------------------------------------------------------------------------
# positive: both fixture styles replay to the oracle
# --------------------------------------------------------------------------
@pytest.mark.parametrize("style", ["resident", "naive"])
def test_fixture_replays_to_oracle(style):
    result = replay_tiny_fixture(style=style)
    assert result["passed"], result
    assert result["metrics"]["relative_l2"] <= result["tolerance_max"]
    assert result["evaluation_kind"] == "functional_replay"


def test_replay_uses_deps_not_static_order():
    """Shuffling static_order (any legal one) cannot change replay values:
    the engine derives its own order from deps."""
    plan = build_tiny_mlp_plan(style="resident")
    values = tiny_external_values(plan)
    result_a = PlanReplay(plan).run(values)
    # a different, still-legal topological order as the declared static order
    order = plan.order()
    order.reverse()  # not topological at all - replay must not care
    plan.static_order = order
    result_b = PlanReplay(plan).run(values)
    key = sorted(result_a.outputs)[0]
    assert np.array_equal(result_a.outputs[key], result_b.outputs[key])


def test_resident_fixture_passes_the_checker():
    plan = build_tiny_mlp_plan(style="resident")
    assert check_plan(plan).ok


# --------------------------------------------------------------------------
# mutations must be caught
# --------------------------------------------------------------------------
def _oracle_for(plan, values):
    shapes = plan.metadata["shapes"]
    i, h = shapes["i"], shapes["h"]

    def assemble(name, count):
        return np.concatenate([values[f"{name}#{j}"] for j in range(count)], axis=1)

    return oracle_mlp(
        values["x#0"],
        assemble("w_gate", i // shapes["n_tile"]),
        assemble("w_up", i // shapes["n_tile"]),
        assemble("w_down", h // shapes["n_tile_down"]),
    )


def test_mutated_shard_source_is_caught_by_replay():
    """silu.0/silu.1 read each other's G chunk (declarations kept consistent,
    so the checker stays green): only the value-level replay can see this.
    Uses the naive (all-DRAM) fixture so no slot-reuse edge tracks the
    reader identity - the mutation is invisible to every structural check."""
    plan = build_tiny_mlp_plan(style="naive")
    plan.op("silu.0").reads = (ChunkRef("G", 1),)
    plan.op("silu.1").reads = (ChunkRef("G", 0),)
    plan.chunks["G#0"].consumers = ("silu.1",)
    plan.chunks["G#1"].consumers = ("silu.0",)
    assert check_plan(plan).ok  # structurally legal: it is a different (wrong) plan

    values = tiny_external_values(plan)
    result = PlanReplay(plan).run(values)
    oracle_y = _oracle_for(plan, values)
    replay_y = result.assembled_output(plan.metadata["shapes"]["m_pad"])
    metrics = compare(replay_y, oracle_y)
    assert metrics["relative_l2"] > plan.metadata["numeric_replay"]["tolerance"]["max"]


def test_omitted_cast_is_caught_by_replay():
    """down reads A32 directly, skipping the BF16 cast (R13 adversarial case):
    declarations are kept consistent; the checker passes, values must not."""
    plan = build_tiny_mlp_plan(style="naive")  # DRAM residency keeps the mutation simple
    shapes = plan.metadata["shapes"]
    n_chunks = shapes["i"] // shapes["n_tile"]
    n_down = shapes["h"] // shapes["n_tile_down"]
    for k in range(n_down):
        down = plan.op(f"down.{k}")
        down.reads = tuple(ChunkRef("A32", j) for j in range(n_chunks)) + (down.reads[-1],)
    for j in range(n_chunks):
        plan.chunks[f"A32#{j}"].consumers = (f"cast.{j}",) + tuple(f"down.{k}" for k in range(n_down))
        plan.chunks[f"A16#{j}"].consumers = ()
    assert check_plan(plan).ok

    values = tiny_external_values(plan)
    result = PlanReplay(plan).run(values)
    oracle_y = _oracle_for(plan, values)
    replay_y = result.assembled_output(plan.metadata["shapes"]["m_pad"])
    metrics = compare(replay_y, oracle_y)
    assert metrics["relative_l2"] > plan.metadata["numeric_replay"]["tolerance"]["max"]


def test_mutated_write_range_is_reported_incapable():
    """An op whose produced bytes differ from the chunk declaration is not a
    numeric mismatch; the replay must refuse the guarantee."""
    plan = build_tiny_mlp_plan(style="resident")
    plan.chunks["G#0"].size_bytes //= 2  # declaration no longer matches the write
    values = tiny_external_values(plan)
    with pytest.raises(ReplayIncapable):
        PlanReplay(plan).run(values)


def test_broken_reuse_dependency_is_caught_by_checker():
    """Remove the edge justifying a ping-pong slot reuse: the checker must
    reject before any execution is even considered."""
    plan = build_tiny_mlp_plan(style="resident")
    # gate.4 (core 0, round 2) reuses the slot of G#0, justified by silu.0
    gate4 = plan.op("gate.4")
    assert "silu.0" in gate4.deps
    gate4.deps = ()
    result = check_plan(plan)
    assert not result.ok
    assert any(e["code"] == "unsafe_overwrite" for e in result.errors)


def test_premature_overwrite_is_caught_by_replay_slot_semantics():
    """A physical slot holds one value at a time: if the bytes a plan reads
    have been overwritten by a foreign chunk, the replay refuses the read."""
    plan = build_tiny_mlp_plan(style="resident")
    replay = PlanReplay(plan)
    g0 = plan.chunks["G#0"]
    slot = (g0.placement.level, g0.placement.core, g0.placement.slot)
    replay.slots[slot] = ("intruder#0", np.zeros((1, 1), dtype=np.float32))
    with pytest.raises(ReplayIncapable):
        replay._read(ChunkRef("G", 0))
