"""Reference plan generators for the sourced Qwen MLP.

Two generators are provided because the round brief requires comparing plans
that are *legal and explainable*, including a naive reference. They differ in
real structure - residency, core mapping, dependency granularity and slot
reuse - not just in a name:

``naive_layered``
    Every intermediate is materialised to DRAM. Each operator stage is a
    whole-layer barrier: chunk j+1 of stage S+1 cannot start until every chunk
    of stage S has finished. This is the deliberately conservative reference.

``resident_pipelined``
    Gate/up output chunks stay in the producing core's scratchpad; SiLU, the
    elementwise multiply and the BF16 cast are fused onto the same core.
    Progress is per chunk, so chunk j+1 of a stage may run while chunk j is
    still being consumed. G/U/S/A32 use ping-pong slots whose reuse is
    justified by an explicit dependency on the previous occupant's last reader.
    A16 does not reuse a slot, because `down` reduces over the whole I
    dimension and therefore keeps every A16 chunk live until the end.

Neither generator claims its plan is faster. Nothing here contains a cycle or
a bandwidth number, because nothing here has been executed on a timing backend.
"""

from __future__ import annotations

from ..workload.qwen_mlp import H, I, MLPModule
from .schema import (
    LEVEL_DRAM,
    LEVEL_SPAD,
    Chunk,
    ChunkRef,
    HardwareProfile,
    Plan,
    PlanOp,
    Placement,
)

DTYPE_BYTES = {"BF16": 2, "FP32": 4}

# Ping-ponged resident tensors and their slot bases.
PINGPONG_KINDS = {"G": 0, "U": 1, "S": 2, "A32": 3}
A16_SLOT_BASE = 16  # never reused: live until the down reduction completes


def _weight_chunks(chunks: dict, name: str, rows: int, cols: int, n_tile: int, dtype: str) -> list[ChunkRef]:
    refs = []
    for j in range(0, cols, n_tile):
        ref = ChunkRef(name, j // n_tile)
        chunks[ref.key] = Chunk(
            ref=ref,
            size_bytes=rows * n_tile * DTYPE_BYTES[dtype],
            dtype=dtype,
            producer="<external>",
            consumers=(),
            placement=Placement(LEVEL_DRAM),
        )
        refs.append(ref)
    return refs


def naive_layered_plan(
    module: MLPModule,
    hardware: HardwareProfile,
    n_tile: int = 512,
    n_tile_down: int = 256,
) -> Plan:
    """Layer-at-a-time, DRAM-materialised, whole-layer barriers."""
    if I % n_tile or H % n_tile_down:
        raise ValueError("n_tile must divide I and n_tile_down must divide H")

    chunks: dict[str, Chunk] = {}
    ops: list[PlanOp] = []
    mp = module.m_pad
    cores = hardware.cores

    x_ref = ChunkRef("x", 0)
    chunks[x_ref.key] = Chunk(x_ref, mp * H * 2, "BF16", "<external>", (), Placement(LEVEL_DRAM))
    w_gate = _weight_chunks(chunks, "w_gate", H, I, n_tile, "BF16")
    w_up = _weight_chunks(chunks, "w_up", H, I, n_tile, "BF16")
    w_down = _weight_chunks(chunks, "w_down", I, H, n_tile_down, "BF16")

    n_chunks = len(w_gate)
    gate_ids, up_ids = [], []
    for j, (wg, wu) in enumerate(zip(w_gate, w_up)):
        for name, weight in (("gate", wg), ("up", wu)):
            out = ChunkRef("G" if name == "gate" else "U", j)
            chunks[out.key] = Chunk(out, mp * n_tile * 4, "FP32", f"{name}.{j}", (), Placement(LEVEL_DRAM))
            ops.append(
                PlanOp(id=f"{name}.{j}", kind="gemm", core=j % cores, reads=(x_ref, weight),
                       writes=(out,), macs=mp * H * n_tile, elements=mp * n_tile, deps=())
            )
            chunks[weight.key].consumers = (f"{name}.{j}",)
        gate_ids.append(f"gate.{j}")
        up_ids.append(f"up.{j}")

    silu_ids, mul_ids, cast_ids = [], [], []
    for j in range(n_chunks):
        g_ref, u_ref = ChunkRef("G", j), ChunkRef("U", j)
        chunks[g_ref.key].consumers = (f"silu.{j}",)
        chunks[u_ref.key].consumers = (f"mul.{j}",)

        s_ref = ChunkRef("S", j)
        chunks[s_ref.key] = Chunk(s_ref, mp * n_tile * 4, "FP32", f"silu.{j}", (f"mul.{j}",), Placement(LEVEL_DRAM))
        ops.append(PlanOp(f"silu.{j}", "silu", j % cores, (g_ref,), (s_ref,), 0, mp * n_tile,
                          deps=tuple(gate_ids),
                          notes="whole-layer barrier: waits on ALL gate chunks"))
        silu_ids.append(f"silu.{j}")

        a_ref = ChunkRef("A32", j)
        chunks[a_ref.key] = Chunk(a_ref, mp * n_tile * 4, "FP32", f"mul.{j}", (f"cast.{j}",), Placement(LEVEL_DRAM))
        ops.append(PlanOp(f"mul.{j}", "mul", j % cores, (s_ref, u_ref), (a_ref,), 0, mp * n_tile,
                          deps=tuple(silu_ids) + tuple(up_ids)))
        mul_ids.append(f"mul.{j}")

        a16_ref = ChunkRef("A16", j)
        chunks[a16_ref.key] = Chunk(a16_ref, mp * n_tile * 2, "BF16", f"cast.{j}", (), Placement(LEVEL_DRAM))
        ops.append(PlanOp(f"cast.{j}", "cast_bf16", j % cores, (a_ref,), (a16_ref,), 0, mp * n_tile,
                          deps=tuple(mul_ids)))
        cast_ids.append(f"cast.{j}")

    n_down = H // n_tile_down
    for k in range(n_down):
        y_ref = ChunkRef("Y", k)
        chunks[y_ref.key] = Chunk(y_ref, mp * n_tile_down * 4, "FP32", f"down.{k}", (), Placement(LEVEL_DRAM))
        reads = tuple(ChunkRef("A16", j) for j in range(n_chunks)) + (w_down[k],)
        ops.append(PlanOp(f"down.{k}", "gemm", k % cores, reads, (y_ref,), macs=mp * I * n_tile_down,
                          elements=mp * n_tile_down, deps=tuple(cast_ids),
                          notes="reduction over the full I dimension: needs every A16 chunk"))
        chunks[w_down[k].key].consumers = (f"down.{k}",)
    for j in range(n_chunks):
        chunks[ChunkRef("A16", j).key].consumers = tuple(f"down.{k}" for k in range(n_down))
    chunks[x_ref.key].consumers = tuple(gate_ids + up_ids)

    return Plan(
        name="naive_layered", workload_id=f"qwen3.5-4b.mlp.M{module.m}", hardware=hardware,
        ops=ops, chunks=chunks,
        metadata={"generator": "naive_layered_plan", "n_tile": n_tile, "n_tile_down": n_tile_down,
                  "residency": "all intermediates materialised to DRAM",
                  "barriers": "whole-layer between every operator stage"},
    )


def resident_pipelined_plan(
    module: MLPModule,
    hardware: HardwareProfile,
    n_tile: int = 512,
    n_tile_down: int = 256,
    slots_per_core: int = 2,
) -> Plan:
    """Per-chunk pipelining with cross-operator scratchpad residency."""
    if I % n_tile or H % n_tile_down:
        raise ValueError("n_tile must divide I and n_tile_down must divide H")

    chunks: dict[str, Chunk] = {}
    ops: list[PlanOp] = []
    mp = module.m_pad
    cores = hardware.cores

    x_ref = ChunkRef("x", 0)
    chunks[x_ref.key] = Chunk(x_ref, mp * H * 2, "BF16", "<external>", (), Placement(LEVEL_DRAM))
    w_gate = _weight_chunks(chunks, "w_gate", H, I, n_tile, "BF16")
    w_up = _weight_chunks(chunks, "w_up", H, I, n_tile, "BF16")
    w_down = _weight_chunks(chunks, "w_down", I, H, n_tile_down, "BF16")

    slot_owner: dict[tuple[int, str, int], str] = {}

    def allocate(kind: str, core: int, rnd: int, extra_deps: tuple[str, ...]) -> tuple[int, str | None, tuple[str, ...]]:
        """Ping-pong slot for `kind`; reuse is only claimed once the previous
        occupant has a reader, and that reader is added as a real dependency."""
        slot = PINGPONG_KINDS[kind] * slots_per_core + (rnd % slots_per_core)
        previous = slot_owner.get((core, LEVEL_SPAD, slot))
        deps = list(extra_deps)
        reuse_of = None
        if previous is not None and rnd >= slots_per_core:
            reuse_of = previous
            prev = chunks[previous]
            deps.append(prev.consumers[-1] if prev.consumers else prev.producer)
        return slot, reuse_of, tuple(deps)

    cast_ids: list[str] = []
    n_chunks = len(w_gate)
    for j in range(n_chunks):
        core = j % cores
        rnd = j // cores  # how many chunks this core has handled before

        g_ref = ChunkRef("G", j)
        slot_g, reuse_g, deps_g = allocate("G", core, rnd, ())
        chunks[g_ref.key] = Chunk(g_ref, mp * n_tile * 4, "FP32", f"gate.{j}", (f"silu.{j}",),
                                  Placement(LEVEL_SPAD, core, slot_g), reuse_of=reuse_g)
        slot_owner[(core, LEVEL_SPAD, slot_g)] = g_ref.key
        ops.append(PlanOp(f"gate.{j}", "gemm", core, (x_ref, w_gate[j]), (g_ref,),
                          macs=mp * H * n_tile, elements=mp * n_tile, deps=deps_g))
        chunks[w_gate[j].key].consumers = (f"gate.{j}",)

        u_ref = ChunkRef("U", j)
        slot_u, reuse_u, deps_u = allocate("U", core, rnd, ())
        chunks[u_ref.key] = Chunk(u_ref, mp * n_tile * 4, "FP32", f"up.{j}", (f"mul.{j}",),
                                  Placement(LEVEL_SPAD, core, slot_u), reuse_of=reuse_u)
        slot_owner[(core, LEVEL_SPAD, slot_u)] = u_ref.key
        ops.append(PlanOp(f"up.{j}", "gemm", core, (x_ref, w_up[j]), (u_ref,),
                          macs=mp * H * n_tile, elements=mp * n_tile, deps=deps_u))
        chunks[w_up[j].key].consumers = (f"up.{j}",)

        s_ref = ChunkRef("S", j)
        slot_s, reuse_s, deps_s = allocate("S", core, rnd, (f"gate.{j}",))
        chunks[s_ref.key] = Chunk(s_ref, mp * n_tile * 4, "FP32", f"silu.{j}", (f"mul.{j}",),
                                  Placement(LEVEL_SPAD, core, slot_s), reuse_of=reuse_s)
        slot_owner[(core, LEVEL_SPAD, slot_s)] = s_ref.key
        ops.append(PlanOp(f"silu.{j}", "silu", core, (g_ref,), (s_ref,), 0, mp * n_tile, deps=deps_s,
                          notes="starts when this chunk's G is visible, not when the whole layer ends"))

        a_ref = ChunkRef("A32", j)
        slot_a, reuse_a, deps_a = allocate("A32", core, rnd, (f"silu.{j}", f"up.{j}"))
        chunks[a_ref.key] = Chunk(a_ref, mp * n_tile * 4, "FP32", f"mul.{j}", (f"cast.{j}",),
                                  Placement(LEVEL_SPAD, core, slot_a), reuse_of=reuse_a)
        slot_owner[(core, LEVEL_SPAD, slot_a)] = a_ref.key
        ops.append(PlanOp(f"mul.{j}", "mul", core, (s_ref, u_ref), (a_ref,), 0, mp * n_tile, deps=deps_a))

        # A16 stays live until the down reduction, so it gets its own slot.
        a16_ref = ChunkRef("A16", j)
        slot16 = A16_SLOT_BASE + rnd
        chunks[a16_ref.key] = Chunk(a16_ref, mp * n_tile * 2, "BF16", f"cast.{j}", (),
                                    Placement(LEVEL_SPAD, core, slot16))
        ops.append(PlanOp(f"cast.{j}", "cast_bf16", core, (a_ref,), (a16_ref,), 0, mp * n_tile,
                          deps=(f"mul.{j}",)))
        cast_ids.append(f"cast.{j}")

    n_down = H // n_tile_down
    for k in range(n_down):
        y_ref = ChunkRef("Y", k)
        chunks[y_ref.key] = Chunk(y_ref, mp * n_tile_down * 4, "FP32", f"down.{k}", (), Placement(LEVEL_DRAM))
        reads = tuple(ChunkRef("A16", j) for j in range(n_chunks)) + (w_down[k],)
        ops.append(PlanOp(f"down.{k}", "gemm", k % cores, reads, (y_ref,), macs=mp * I * n_tile_down,
                          elements=mp * n_tile_down, deps=tuple(cast_ids),
                          notes="reduction over the full I dimension: needs every A16 chunk"))
        chunks[w_down[k].key].consumers = (f"down.{k}",)
    for j in range(n_chunks):
        chunks[ChunkRef("A16", j).key].consumers = tuple(f"down.{k}" for k in range(n_down))
    chunks[x_ref.key].consumers = tuple(
        [f"gate.{j}" for j in range(n_chunks)] + [f"up.{j}" for j in range(n_chunks)]
    )

    return Plan(
        name="resident_pipelined", workload_id=f"qwen3.5-4b.mlp.M{module.m}", hardware=hardware,
        ops=ops, chunks=chunks,
        metadata={"generator": "resident_pipelined_plan", "n_tile": n_tile, "n_tile_down": n_tile_down,
                  "residency": "G/U/S/A32/A16 resident in the producing core's scratchpad",
                  "barriers": "none between pointwise stages; the I reduction remains a barrier",
                  "slot_reuse": f"ping-pong over {slots_per_core} slots per core for G/U/S/A32, "
                                f"with an explicit dependency on the previous occupant's last reader; "
                                f"A16 is not reused"},
    )
