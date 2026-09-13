"""Functional replay of a plan, bound to the plan's own chunk accesses.

Purpose and non-purpose
-----------------------
This engine *executes the plan*: it walks a topological order derived from
``deps`` (never ``static_order``), reads and writes the exact chunks the plan
declares, honours physical placement (an on-chip slot holds one value at a
time - a new occupant overwrites the old), and applies the operator semantics
from the plan's ``numeric_replay`` metadata.

It exists to verify **values, reads/writes and overwrites** against an
independent algebraic oracle. It produces **no cycles and no bandwidth**, and
it is not a simulator: there is no time here at all.

If a plan lacks the replay metadata, or its semantics cannot be honoured,
the engine reports that it cannot give the required guarantee - it never
silently approximates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..plan.schema import ChunkRef, HardwareProfile, Plan


class ReplayIncapable(RuntimeError):
    """The plan does not provide what a faithful replay requires."""


def bf16_rne(values: np.ndarray) -> np.ndarray:
    """FP32 -> BF16 round-to-nearest-even, returned as exactly-representable FP32."""
    arr = np.ascontiguousarray(values, dtype=np.float32)
    bits = arr.view(np.uint32)
    lsb = (bits >> 16) & np.uint32(1)
    rounded = bits + np.uint32(0x7FFF) + lsb
    return (rounded & np.uint32(0xFFFF0000)).view(np.float32)


def _silu(x: np.ndarray) -> np.ndarray:
    return (x / (1.0 + np.exp(-x.astype(np.float64)))).astype(np.float32)


@dataclass
class ReplayResult:
    executed_ops: list[str]
    outputs: dict[str, np.ndarray]  # Y chunk key -> value
    checks: dict[str, Any] = field(default_factory=dict)

    def assembled_output(self, m_rows: int) -> np.ndarray:
        """All Y chunks concatenated along axis 1, padding rows removed."""
        keys = sorted(self.outputs, key=lambda k: int(k.rsplit("#", 1)[1]))
        full = np.concatenate([self.outputs[k] for k in keys], axis=1)
        return full[:m_rows]


class PlanReplay:
    """Executes one plan over concrete input values."""

    def __init__(self, plan: Plan):
        self.plan = plan
        meta = plan.metadata.get("numeric_replay")
        if not meta:
            raise ReplayIncapable(
                f"plan {plan.name!r} carries no numeric_replay metadata; "
                f"its semantics are not declared, so no replay guarantee can be given"
            )
        self.meta = meta
        self.dram: dict[str, np.ndarray] = {}
        self.slots: dict[tuple[str, int, int], tuple[str, np.ndarray]] = {}
        self.outputs: dict[str, np.ndarray] = {}

    # -- value access through the plan's own declarations -----------------
    @staticmethod
    def _declared_elements(chunk) -> int:
        """Element count implied by the chunk's declared bytes and dtype.

        Replay values are stored as float32; a BF16 chunk's values are BF16
        values represented exactly in float32 (the R13 convention), so the
        binding between plan and value is the *element count*, not raw bytes.
        """
        dtype_bytes = {"BF16": 2, "FP32": 4}[chunk.dtype]
        if chunk.size_bytes % dtype_bytes:
            raise ReplayIncapable(
                f"chunk {chunk.key} declares {chunk.size_bytes} B of {chunk.dtype}, "
                f"not a whole number of elements"
            )
        return chunk.size_bytes // dtype_bytes

    def _write(self, key: str, value: np.ndarray) -> None:
        chunk = self.plan.chunks[key]
        value = np.ascontiguousarray(value)
        expected = self._declared_elements(chunk)
        if value.size != expected:
            raise ReplayIncapable(
                f"op wrote {value.size} elements into chunk {key} "
                f"which declares {expected}; write range differs from the plan"
            )
        if chunk.on_chip:
            slot = (chunk.placement.level, chunk.placement.core, chunk.placement.slot)
            self.slots[slot] = (key, value)  # overwrite semantics of a physical slot
        else:
            self.dram[key] = value

    def _read(self, ref: ChunkRef) -> np.ndarray:
        chunk = self.plan.chunks[ref.key]
        if chunk.on_chip:
            slot = (chunk.placement.level, chunk.placement.core, chunk.placement.slot)
            held = self.slots.get(slot)
            if held is None or held[0] != ref.key:
                raise ReplayIncapable(
                    f"op reads {ref.key} from {slot} but the slot holds "
                    f"{held[0] if held else 'nothing'}; the plan overwrote it before this read"
                )
            return held[1]
        return self.dram[ref.key]

    # -- execution ---------------------------------------------------------
    def _topological_order(self) -> list[str]:
        """Kahn order from deps only; ties broken by id. static_order is not used."""
        indeg = {op.id: len(op.deps) for op in self.plan.ops}
        succ: dict[str, list[str]] = {op.id: [] for op in self.plan.ops}
        for op in self.plan.ops:
            for dep in op.deps:
                succ[dep].append(op.id)
        ready = sorted(op_id for op_id, d in indeg.items() if d == 0)
        order: list[str] = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            for nxt in sorted(succ[node]):
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    ready.append(nxt)
            ready.sort()
        if len(order) != len(self.plan.ops):
            raise ReplayIncapable("dependency graph has a cycle; no execution order exists")
        return order

    def _execute_op(self, op_id: str) -> None:
        op = self.plan.op(op_id)
        kind = op.kind
        if kind == "gemm":
            # out = concat(reads[:-1], axis=1) @ reads[-1]
            if len(op.reads) < 2:
                raise ReplayIncapable(f"gemm {op.id} has fewer than two reads")
            lhs_parts = [self._read(r) for r in op.reads[:-1]]
            lhs = lhs_parts[0] if len(lhs_parts) == 1 else np.concatenate(lhs_parts, axis=1)
            rhs = self._read(op.reads[-1])
            result = lhs.astype(np.float32) @ rhs.astype(np.float32)
        elif kind == "silu":
            result = _silu(self._read(op.reads[0]))
        elif kind == "mul":
            result = self._read(op.reads[0]).astype(np.float32) * self._read(op.reads[1]).astype(np.float32)
        elif kind == "cast_bf16":
            result = bf16_rne(self._read(op.reads[0]))
        else:
            raise ReplayIncapable(f"op {op.id} has unregistered kind {kind!r}")
        if len(op.writes) != 1:
            raise ReplayIncapable(f"op {op.id} writes {len(op.writes)} chunks; replay expects exactly one")
        self._write(op.writes[0].key, result)
        if op.writes[0].tensor == "Y":
            self.outputs[op.writes[0].key] = result

    def run(self, external_values: dict[str, np.ndarray]) -> ReplayResult:
        """Load external chunks (inputs/weights), then execute every op."""
        for key, value in external_values.items():
            if key not in self.plan.chunks:
                raise ReplayIncapable(f"external value {key} is not a chunk of this plan")
            self._write(key, np.ascontiguousarray(value))
        order = self._topological_order()
        for op_id in order:
            self._execute_op(op_id)
        return ReplayResult(executed_ops=order, outputs=dict(self.outputs))


def oracle_mlp(x: np.ndarray, w_gate: np.ndarray, w_up: np.ndarray, w_down: np.ndarray) -> np.ndarray:
    """Independent algebraic oracle: down(SiLU(gate(x)) * up(x)) in float64.

    Shares no code with the replay engine; the comparison tolerance is part of
    the plan's numeric_replay licence, not of this function.
    """
    g = x.astype(np.float64) @ w_gate.astype(np.float64)
    u = x.astype(np.float64) @ w_up.astype(np.float64)
    s = g / (1.0 + np.exp(-g))
    a = s * u
    a16 = bf16_rne(a.astype(np.float32))  # the explicit cast is part of the algebra
    return a16.astype(np.float64) @ w_down.astype(np.float64)


def compare(result_y: np.ndarray, oracle_y: np.ndarray) -> dict[str, Any]:
    diff = result_y.astype(np.float64) - oracle_y
    denom = float(np.linalg.norm(oracle_y)) or 1.0
    return {
        "relative_l2": float(np.linalg.norm(diff) / denom),
        "max_abs": float(np.max(np.abs(diff))) if diff.size else 0.0,
    }


# --------------------------------------------------------------------------
# Tiny fixture: a small MLP-shaped plan exercising the same IR machinery.
# It is a *fixture*, not the Qwen module; its workload_id says so.
# --------------------------------------------------------------------------
def build_tiny_mlp_plan(
    style: str = "resident",
    m_pad: int = 32,
    h: int = 64,
    i: int = 512,
    n_tile: int = 64,
    n_tile_down: int = 32,
    cores: int = 2,
) -> Plan:
    """Small plan with the same structure as the reference generators.

    Values are small enough that the replay runs in milliseconds, letting the
    test compare against the independent oracle exactly. ``style`` is
    "resident" (on-chip residency + ping-pong slot reuse) or "naive" (all
    intermediates in DRAM, whole-layer barriers). The defaults give 8 column
    chunks over 2 cores, so ping-pong slot reuse genuinely triggers.
    """
    from ..plan.schema import (
        LEVEL_DRAM,
        LEVEL_SPAD,
        Chunk,
        Plan,
        PlanOp,
        Placement,
    )

    if style not in {"resident", "naive"}:
        raise ValueError(style)
    resident = style == "resident"
    if i % n_tile or h % n_tile_down:
        raise ValueError("n_tile must divide i and n_tile_down must divide h")

    hardware = HardwareProfile(
        profile_id="tiny_replay_fixture", cores=cores,
        spad_bytes_per_core=1 << 20, accum_bytes_per_core=0,
    )
    chunks: dict[str, Chunk] = {}
    ops: list[PlanOp] = []
    resident_note = "on-chip ping-pong residency" if resident else "all intermediates in DRAM"

    x_ref = ChunkRef("x", 0)
    chunks[x_ref.key] = Chunk(x_ref, m_pad * h * 2, "BF16", "<external>", (), Placement(LEVEL_DRAM))

    n_chunks = i // n_tile
    n_down = h // n_tile_down

    def weight(name: str, rows: int, block: int, idx: int) -> ChunkRef:
        ref = ChunkRef(name, idx)
        chunks[ref.key] = Chunk(ref, rows * block * 2, "BF16", "<external>", (), Placement(LEVEL_DRAM))
        return ref

    def place_for(kind: str, core: int, rnd: int) -> tuple[Placement, str | None, str | None]:
        """Ping-pong slot selection for the resident style; returns
        (placement, reuse_of, previous_last_reader)."""
        base = {"G": 0, "U": 2, "S": 4, "A32": 6}[kind]
        slot = base + (rnd % 2)
        previous = slot_owner.get((core, slot))
        last_reader = None
        if previous is not None and rnd >= 2:
            prev = chunks[previous]
            last_reader = prev.consumers[-1] if prev.consumers else prev.producer
        return Placement(LEVEL_SPAD, core, slot), previous if last_reader else None, last_reader

    slot_owner: dict[tuple[int, int], str] = {}
    ids = {
        stage: [f"{stage}.{j}" for j in range(n_chunks)]
        for stage in ("gate", "up", "silu", "mul", "cast")
    }

    for j in range(n_chunks):
        core = j % cores
        rnd = j // cores
        wg, wu = weight("w_gate", h, n_tile, j), weight("w_up", h, n_tile, j)

        g_ref = ChunkRef("G", j)
        if resident:
            g_place, g_reuse, g_reader = place_for("G", core, rnd)
            deps_g = (g_reader,) if g_reader else ()
            slot_owner[(core, g_place.slot)] = g_ref.key
        else:
            g_place, g_reuse, deps_g = Placement(LEVEL_DRAM), None, ()
        chunks[g_ref.key] = Chunk(g_ref, m_pad * n_tile * 4, "FP32", f"gate.{j}", (f"silu.{j}",),
                                  g_place, reuse_of=g_reuse)
        ops.append(PlanOp(f"gate.{j}", "gemm", core, (x_ref, wg), (g_ref,),
                          macs=m_pad * h * n_tile, elements=m_pad * n_tile, deps=deps_g))
        chunks[wg.key].consumers = (f"gate.{j}",)

        u_ref = ChunkRef("U", j)
        if resident:
            u_place, u_reuse, u_reader = place_for("U", core, rnd)
            deps_u = (u_reader,) if u_reader else ()
            slot_owner[(core, u_place.slot)] = u_ref.key
        else:
            u_place, u_reuse, deps_u = Placement(LEVEL_DRAM), None, ()
        chunks[u_ref.key] = Chunk(u_ref, m_pad * n_tile * 4, "FP32", f"up.{j}", (f"mul.{j}",),
                                  u_place, reuse_of=u_reuse)
        ops.append(PlanOp(f"up.{j}", "gemm", core, (x_ref, wu), (u_ref,),
                          macs=m_pad * h * n_tile, elements=m_pad * n_tile, deps=deps_u))
        chunks[wu.key].consumers = (f"up.{j}",)

        s_ref = ChunkRef("S", j)
        if resident:
            s_place, s_reuse, s_reader = place_for("S", core, rnd)
            deps_s = ("gate.%d" % j,) + ((s_reader,) if s_reader else ())
            slot_owner[(core, s_place.slot)] = s_ref.key
        else:
            s_place, s_reuse, deps_s = Placement(LEVEL_DRAM), None, tuple(ids["gate"])
        chunks[s_ref.key] = Chunk(s_ref, m_pad * n_tile * 4, "FP32", f"silu.{j}", (f"mul.{j}",),
                                  s_place, reuse_of=s_reuse)
        ops.append(PlanOp(f"silu.{j}", "silu", core, (g_ref,), (s_ref,), 0, m_pad * n_tile, deps=deps_s))

        a_ref = ChunkRef("A32", j)
        if resident:
            a_place, a_reuse, a_reader = place_for("A32", core, rnd)
            deps_a = (f"silu.{j}", f"up.{j}") + ((a_reader,) if a_reader else ())
            slot_owner[(core, a_place.slot)] = a_ref.key
        else:
            a_place, a_reuse = Placement(LEVEL_DRAM), None
            deps_a = tuple(ids["silu"]) + tuple(ids["up"])
        chunks[a_ref.key] = Chunk(a_ref, m_pad * n_tile * 4, "FP32", f"mul.{j}", (f"cast.{j}",),
                                  a_place, reuse_of=a_reuse)
        ops.append(PlanOp(f"mul.{j}", "mul", core, (s_ref, u_ref), (a_ref,), 0, m_pad * n_tile, deps=deps_a))

        a16_ref = ChunkRef("A16", j)
        a16_place = Placement(LEVEL_SPAD, core, 16 + rnd) if resident else Placement(LEVEL_DRAM)
        chunks[a16_ref.key] = Chunk(a16_ref, m_pad * n_tile * 2, "BF16", f"cast.{j}", (), a16_place)
        deps_cast = (f"mul.{j}",) if resident else tuple(ids["mul"])
        ops.append(PlanOp(f"cast.{j}", "cast_bf16", core, (a_ref,), (a16_ref,), 0, m_pad * n_tile,
                          deps=deps_cast))

    for k in range(n_down):
        y_ref = ChunkRef("Y", k)
        wd = weight("w_down", i, n_tile_down, k)
        chunks[y_ref.key] = Chunk(y_ref, m_pad * n_tile_down * 4, "FP32", f"down.{k}", (),
                                  Placement(LEVEL_DRAM))
        reads = tuple(ChunkRef("A16", j) for j in range(n_chunks)) + (wd,)
        ops.append(PlanOp(f"down.{k}", "gemm", k % cores, reads, (y_ref,),
                          macs=m_pad * i * n_tile_down, elements=m_pad * n_tile_down,
                          deps=tuple(ids["cast"])))
        chunks[wd.key].consumers = (f"down.{k}",)
    for j in range(n_chunks):
        chunks[ChunkRef("A16", j).key].consumers = tuple(f"down.{k}" for k in range(n_down))
    chunks[x_ref.key].consumers = tuple(ids["gate"] + ids["up"])

    # The tiny fixture's down reads A16 from other cores in the resident style,
    # exactly like the real generator: a movement contract stub is declared so
    # that *functional* replay may proceed, clearly marked as fixture-only.
    metadata = {
        "generator": "build_tiny_mlp_plan",
        "style": style,
        "residency": resident_note,
        "movement_contract": (
            {"kind": "fixture_direct_spad_read", "scope": "functional replay only; "
             "asserts values, not timing"} if resident else None
        ),
        "numeric_replay": {
            "schema": "schedresearch.infra.numeric_replay.v1",
            "layout": "row-major 2-D tensors [M_pad, N]; chunks are column blocks of one tensor",
            "chunk_slices": {"x": "whole",
                             "w_gate": {"axis": 1, "block": n_tile}, "w_up": {"axis": 1, "block": n_tile},
                             "w_down": {"axis": 1, "block": n_tile_down},
                             "G": {"axis": 1, "block": n_tile}, "U": {"axis": 1, "block": n_tile},
                             "S": {"axis": 1, "block": n_tile}, "A32": {"axis": 1, "block": n_tile},
                             "A16": {"axis": 1, "block": n_tile}, "Y": {"axis": 1, "block": n_tile_down}},
            "op_semantics": {"gemm": "out = concat(reads[:-1], axis=1) @ reads[-1]",
                             "silu": "elementwise x*sigmoid(x) in FP32",
                             "mul": "elementwise product in FP32",
                             "cast_bf16": "FP32 -> BF16 RNE, stored as exactly-representable FP32"},
            "dtypes": {"x": "BF16", "w_gate": "BF16", "w_up": "BF16", "w_down": "BF16",
                       "G": "FP32", "U": "FP32", "S": "FP32", "A32": "FP32", "A16": "BF16", "Y": "FP32"},
            "tolerance": {"metric": "relative_l2_vs_float64_oracle", "max": 1e-4,
                          "note": "functional replay only; produces no cycles and no bandwidth"},
        },
        "shapes": {"m_pad": m_pad, "h": h, "i": i, "n_tile": n_tile, "n_tile_down": n_tile_down},
    }
    static_order: list[str] = []
    if not resident:
        # Interleaved creation order cannot satisfy the whole-layer barriers;
        # declare the stage-major schedule explicitly (as the real naive
        # generator does).
        static_order = (
            ids["gate"] + ids["up"] + ids["silu"] + ids["mul"] + ids["cast"]
            + [f"down.{k}" for k in range(n_down)]
        )
    return Plan(name=f"tiny_{style}", workload_id=f"tiny-mlp-fixture.M{m_pad}",
                hardware=hardware, ops=ops, chunks=chunks, static_order=static_order,
                metadata=metadata)


def tiny_external_values(plan: Plan, seed: int = 20260914) -> dict[str, np.ndarray]:
    """Deterministic external values for the tiny fixture, BF16-quantised."""
    shapes = plan.metadata["shapes"]
    m_pad, h, i = shapes["m_pad"], shapes["h"], shapes["i"]
    rng = np.random.default_rng(seed)
    values: dict[str, np.ndarray] = {"x#0": bf16_rne(rng.uniform(-1, 1, (m_pad, h)).astype(np.float32))}
    for key, chunk in plan.chunks.items():
        tensor = chunk.ref.tensor
        if not tensor.startswith("w_"):
            continue
        rows = h if tensor in ("w_gate", "w_up") else i
        block = shapes["n_tile"] if tensor in ("w_gate", "w_up") else shapes["n_tile_down"]
        scale = 1.0 / np.sqrt(rows)
        values[key] = bf16_rne(rng.uniform(-scale, scale, (rows, block)).astype(np.float32))
    return values


def replay_tiny_fixture(style: str = "resident", seed: int = 20260914) -> dict[str, Any]:
    """One complete fixture replay, compared against the independent oracle."""
    plan = build_tiny_mlp_plan(style=style)
    values = tiny_external_values(plan, seed=seed)
    replay = PlanReplay(plan)
    result = replay.run(values)
    shapes = plan.metadata["shapes"]
    m_pad, h, i = shapes["m_pad"], shapes["h"], shapes["i"]

    def assemble(name: str, block: int, count: int) -> np.ndarray:
        return np.concatenate([values[f"{name}#{j}"] for j in range(count)], axis=1)

    oracle_in = {
        "x": values["x#0"],
        "w_gate": assemble("w_gate", shapes["n_tile"], i // shapes["n_tile"]),
        "w_up": assemble("w_up", shapes["n_tile"], i // shapes["n_tile"]),
        "w_down": assemble("w_down", shapes["n_tile_down"], h // shapes["n_tile_down"]),
    }
    oracle_y = oracle_mlp(**oracle_in)
    replay_y = result.assembled_output(m_pad)
    metrics = compare(replay_y, oracle_y)
    tolerance = plan.metadata["numeric_replay"]["tolerance"]["max"]
    return {
        "plan_id": plan.plan_id,
        "style": style,
        "seed": seed,
        "executed_ops": len(result.executed_ops),
        "metrics": metrics,
        "tolerance_max": tolerance,
        "passed": metrics["relative_l2"] <= tolerance,
        "evaluation_kind": "functional_replay",
        "note": "values, reads/writes and overwrites only; no cycles, no bandwidth",
    }
