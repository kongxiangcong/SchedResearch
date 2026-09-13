"""Candidate execution plan IR and plan identity.

Why this exists
---------------
The round brief asks for a *research* plan interface that sits between a
workload and a backend, and for two things to be true of it:

* a plan must be externally supplied and must survive into the backend
  unchanged, and
* two plans that differ in mapping, addressing, lifetime or order must be
  *different plans*, not the same plan with a different name.

So identity is content-addressed: ``plan_id`` is a hash over the normalised
plan, not a label chosen by whoever generated it.

What this IR deliberately does NOT contain
------------------------------------------
No cycles, no bandwidth numbers, no latency model. Those belong to a backend.
A plan states *what* is computed where, *which* data lives where, and *which
orderings* are required. Anything timing-related is produced by executing it.

Modelling choices, stated explicitly
------------------------------------
* Granularity is a **chunk**: a contiguous piece of a logical tensor
  (typically one tile row-block). Chunks are the unit of placement, transfer
  and lifetime.
* ``deps`` is a *partial order* over ops. A timing backend is free to issue in
  any order consistent with it; it may not drop an edge.
* ``static_order`` is one declared linear extension, used by the checker as the
  reference schedule for capacity and reuse legality. It is a legalisation aid,
  not a timing prediction (see ``checker.py`` for the exact limitation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..repo import sha256_json

LEVEL_DRAM = "dram"
LEVEL_SPAD = "spad"
LEVEL_ACCUM = "accum"

# Sentinel producer for module inputs and weights: present before the plan
# starts, so no op produces them and no dependency edge is required.
EXTERNAL = "<external>"


def chunk_key(tensor: str, index: int) -> str:
    return f"{tensor}#{index}"


@dataclass(frozen=True)
class ChunkRef:
    tensor: str
    index: int

    @property
    def key(self) -> str:
        return chunk_key(self.tensor, self.index)

    def as_dict(self) -> dict[str, Any]:
        return {"tensor": self.tensor, "index": self.index}


@dataclass(frozen=True)
class Placement:
    """Where a chunk physically lives while it is resident."""

    level: str  # dram | spad | accum
    core: int = -1  # -1 for DRAM
    slot: int = -1  # buffer slot index within that core/level
    offset: int = 0  # byte offset inside the slot

    def as_dict(self) -> dict[str, Any]:
        return {"level": self.level, "core": self.core, "slot": self.slot, "offset": self.offset}


@dataclass
class Chunk:
    ref: ChunkRef
    size_bytes: int
    dtype: str
    producer: str  # op id that writes it
    consumers: tuple[str, ...] = ()  # op ids that read it
    placement: Placement = Placement(LEVEL_DRAM)
    reuse_of: str | None = None  # key of the chunk whose slot this reuses

    @property
    def key(self) -> str:
        return self.ref.key

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "tensor": self.ref.tensor,
            "index": self.ref.index,
            "size_bytes": self.size_bytes,
            "dtype": self.dtype,
            "producer": self.producer,
            "consumers": list(self.consumers),
            "placement": self.placement.as_dict(),
            "reuse_of": self.reuse_of,
        }


@dataclass
class PlanOp:
    id: str
    kind: str  # gemm | silu | mul | cast_bf16 | load | store | pointwise
    core: int
    reads: tuple[ChunkRef, ...] = ()
    writes: tuple[ChunkRef, ...] = ()
    macs: int = 0
    elements: int = 0
    deps: tuple[str, ...] = ()  # op ids that must complete first
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "core": self.core,
            "reads": [r.as_dict() for r in self.reads],
            "writes": [w.as_dict() for w in self.writes],
            "macs": self.macs,
            "elements": self.elements,
            "deps": list(self.deps),
            "notes": self.notes,
        }


@dataclass
class HardwareProfile:
    profile_id: str
    cores: int
    spad_bytes_per_core: int
    accum_bytes_per_core: int
    precision_bytes: int = 2
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path) -> "HardwareProfile":
        import json
        from pathlib import Path

        data = json.loads(Path(path).read_text(encoding="utf-8"))
        derived = data.get("derived", {})
        return cls(
            profile_id=data["profile_id"],
            cores=data["cores"],
            spad_bytes_per_core=derived.get(
                "spad_usable_bytes_per_core", data["per_core"]["spad_size_kb"] * 1024
            ),
            accum_bytes_per_core=derived.get(
                "accum_usable_bytes_per_core", data["per_core"]["accum_spad_size_kb"] * 1024
            ),
            precision_bytes=data.get("precision_bytes", 2),
            raw=data,
        )

    def level_capacity(self, level: str) -> int:
        if level == LEVEL_SPAD:
            return self.spad_bytes_per_core
        if level == LEVEL_ACCUM:
            return self.accum_bytes_per_core
        return 0  # DRAM has no capacity limit we model

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "cores": self.cores,
            "spad_bytes_per_core": self.spad_bytes_per_core,
            "accum_bytes_per_core": self.accum_bytes_per_core,
            "precision_bytes": self.precision_bytes,
        }


@dataclass
class Plan:
    """One complete, externally supplied candidate execution plan."""

    name: str
    workload_id: str
    hardware: HardwareProfile
    ops: list[PlanOp]
    chunks: dict[str, Chunk]
    static_order: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ---- derived structure -------------------------------------------
    def op(self, op_id: str) -> PlanOp:
        for op in self.ops:
            if op.id == op_id:
                return op
        raise KeyError(op_id)

    def order(self) -> list[str]:
        return list(self.static_order) if self.static_order else [op.id for op in self.ops]

    def edges(self) -> list[tuple[str, str]]:
        edges: list[tuple[str, str]] = []
        for op in self.ops:
            for dep in op.deps:
                edges.append((dep, op.id))
        return edges

    # ---- identity ------------------------------------------------------
    def canonical(self) -> dict[str, Any]:
        """Normalised projection used for hashing.

        `name` and free-form `metadata` are excluded: renaming a plan must not
        change its identity, and changing any structural field must.
        """
        return {
            "workload_id": self.workload_id,
            "hardware": self.hardware.as_dict(),
            "ops": [op.as_dict() for op in sorted(self.ops, key=lambda o: o.id)],
            "chunks": [self.chunks[k].as_dict() for k in sorted(self.chunks)],
            "static_order": self.order(),
        }

    @property
    def plan_id(self) -> str:
        return sha256_json(self.canonical())[:16]

    def summary(self) -> dict[str, Any]:
        per_core: dict[int, int] = {}
        for op in self.ops:
            per_core[op.core] = per_core.get(op.core, 0) + 1
        resident = {}
        for chunk in self.chunks.values():
            if chunk.placement.level in (LEVEL_SPAD, LEVEL_ACCUM):
                resident[chunk.placement.level] = resident.get(chunk.placement.level, 0) + chunk.size_bytes
        return {
            "name": self.name,
            "plan_id": self.plan_id,
            "workload_id": self.workload_id,
            "hardware": self.hardware.profile_id,
            "ops": len(self.ops),
            "ops_per_core": per_core,
            "chunks": len(self.chunks),
            "resident_bytes_by_level": resident,
            "total_macs": sum(op.macs for op in self.ops),
            "edges": len(self.edges()),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "schedresearch.infra.plan.v1",
            "name": self.name,
            "plan_id": self.plan_id,
            "workload_id": self.workload_id,
            "hardware": self.hardware.as_dict(),
            "ops": [op.as_dict() for op in self.ops],
            "chunks": {k: v.as_dict() for k, v in self.chunks.items()},
            "static_order": self.order(),
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, sort_keys=False)


def distinct(a: Plan, b: Plan) -> bool:
    """True when two plans are structurally different, not merely differently named."""
    return a.plan_id != b.plan_id


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
