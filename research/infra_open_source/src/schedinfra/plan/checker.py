"""Legality checker for candidate plans.

What is guaranteed, and over which executions
---------------------------------------------
Two different strengths of statement are kept strictly separate:

* **Partial-order guarantees (every legal execution).** Dependency,
  producer/consumer coverage, exclusivity, cycle-freedom and
  **physical-overwrite safety** are checked against the dependency partial
  order. If the checker accepts a plan on these, *every* execution that
  respects ``deps`` is safe on them.
* **Declared-order statements (one schedule only).** The capacity/peak walk
  uses the plan's declared ``static_order`` - one linear extension of the DAG.
  A backend that interleaves differently could still overflow, so peak
  residency is reported as ``static_order``-scoped and nothing more.
  ``static_order`` never becomes a hidden ordering constraint on a backend:
  it is not part of ``deps``, it is verified to be a genuine topological
  order, and no safety verdict depends on it.

Physical-overwrite safety (the fixed rule)
------------------------------------------
Before a chunk may occupy bytes that overlap a *different* live chunk (same
level/core/slot, intersecting byte ranges - see ``schema.Placement``), the
writer op must have **every** reader of the old chunk among its transitive
predecessors (conservative op-completion; an event that transitively
dominates all readers would also do, but is not modelled yet). It is not
enough to wait for *one* reader, and the optional ``reuse_of`` annotation
plays no role in deciding whether this check runs.

Fail-fast structure
-------------------
Unknown ids, duplicate ids or structural inconsistencies produce a structured
rejection and stop every later analysis that would depend on those fields, so
a KeyError or a recursion error can never mask the original error.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .schema import EXTERNAL, LEVEL_ACCUM, LEVEL_DRAM, LEVEL_SPAD, Plan

LEGAL_LEVELS = (LEVEL_DRAM, LEVEL_SPAD, LEVEL_ACCUM)


def _tensor_of(key: str) -> str:
    return key.rsplit("#", 1)[0]


@dataclass
class CheckResult:
    ok: bool = True
    errors: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    stats: dict[str, object] = field(default_factory=dict)

    def fail(self, code: str, detail: str) -> None:
        self.ok = False
        self.errors.append({"code": code, "detail": detail})

    def warn(self, code: str, detail: str) -> None:
        self.warnings.append({"code": code, "detail": detail})

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
            "stats": self.stats,
            "safety_scope": {
                "dependency_and_overwrite_safety": "all executions consistent with deps",
                "capacity_peak": "declared static_order only - not a hardware peak under arbitrary interleaving",
                "resident_value_bytes_sum": "sum of logical value sizes placed on-chip; not traffic, not saved DRAM bytes",
            },
        }


def _transitive_predecessors(plan: Plan) -> dict[str, set[str]]:
    """op -> every op that must complete before it, transitively."""
    succ: dict[str, list[str]] = {op.id: [] for op in plan.ops}
    for op in plan.ops:
        for dep in op.deps:
            succ[dep].append(op.id)

    preds: dict[str, set[str]] = {op.id: set() for op in plan.ops}
    # Process in topological order so each node's set is complete when used.
    indeg = {op.id: len(op.deps) for op in plan.ops}
    queue = [op.id for op in plan.ops if indeg[op.id] == 0]
    order: list[str] = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for nxt in succ[node]:
            preds[nxt] |= preds[node] | {node}
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    if len(order) != len(plan.ops):
        # Cycle: fall back to a direct-only approximation; cycle check reports it.
        for op in plan.ops:
            preds[op.id] = set(op.deps)
    return preds


def check_structure(plan: Plan, result: CheckResult) -> None:
    """Schema-level consistency. Nothing after this may KeyError on the plan."""
    op_ids = [op.id for op in plan.ops]
    op_id_set = set(op_ids)
    if len(op_id_set) != len(op_ids):
        seen: set[str] = set()
        dupes = sorted({x for x in op_ids if x in seen or seen.add(x)})
        result.fail("duplicate_op_id", f"plan contains duplicate op ids: {dupes}")

    chunk_key_set = set(plan.chunks)
    if len(chunk_key_set) != len(plan.chunks):
        result.fail("duplicate_chunk_key", "plan.chunks contains duplicate keys")

    writes: dict[str, str] = {}  # chunk key -> writing op id
    for op in plan.ops:
        if not (0 <= op.core < plan.hardware.cores):
            result.fail(
                "bad_core",
                f"op {op.id} assigned to core {op.core} outside 0..{plan.hardware.cores - 1}",
            )
        for dep in op.deps:
            if dep not in op_id_set:
                result.fail("unknown_dep", f"op {op.id} depends on unknown op {dep}")
        for ref in (*op.reads, *op.writes):
            if ref.key not in plan.chunks:
                result.fail("unknown_chunk", f"op {op.id} references undeclared chunk {ref.key}")
        for ref in op.writes:
            if ref.key in writes:
                result.fail(
                    "multiple_writers",
                    f"chunk {ref.key} written by both {writes[ref.key]} and {op.id}",
                )
            writes[ref.key] = op.id

    for key, chunk in plan.chunks.items():
        # Value-level sanity.
        if chunk.size_bytes <= 0:
            result.fail("bad_size", f"chunk {key} has non-positive size {chunk.size_bytes}")
        if chunk.ref.tensor != _tensor_of(key) or chunk.key != key:
            result.fail("chunk_key_corrupt", f"chunk {key} key does not match its ref")
        # Placement legality.
        level = chunk.placement.level
        if level not in LEGAL_LEVELS:
            result.fail("bad_level", f"chunk {key} placed on unknown level {level!r}")
        if chunk.on_chip:
            if not (0 <= chunk.placement.core < plan.hardware.cores):
                result.fail(
                    "bad_core",
                    f"chunk {key} placed on core {chunk.placement.core} outside 0..{plan.hardware.cores - 1}",
                )
            if chunk.placement.slot < 0:
                result.fail("bad_slot", f"chunk {key} on {level} has no slot index")
            if chunk.placement.offset < 0:
                result.fail("bad_offset", f"chunk {key} has negative offset {chunk.placement.offset}")
        # Producer <-> writes bidirectional, unique.
        if chunk.producer == EXTERNAL:
            if key in writes:
                result.fail(
                    "producer_declaration_mismatch",
                    f"chunk {key} is declared external but op {writes[key]} writes it",
                )
        else:
            if chunk.producer not in op_id_set:
                result.fail("unknown_producer", f"chunk {key} produced by unknown op {chunk.producer}")
            elif writes.get(key) != chunk.producer:
                result.fail(
                    "producer_declaration_mismatch",
                    f"chunk {key} declares producer {chunk.producer} but writes say {writes.get(key)}",
                )
        for consumer in chunk.consumers:
            if consumer not in op_id_set:
                result.fail("unknown_consumer", f"chunk {key} consumed by unknown op {consumer}")


def check_acyclic(plan: Plan, result: CheckResult) -> None:
    colour: dict[str, int] = {op.id: 0 for op in plan.ops}
    succ: dict[str, list[str]] = {op.id: list(op.deps) for op in plan.ops}  # reversed edges

    def visit(node: str, stack: list[str]) -> None:
        colour[node] = 1
        for nxt in succ[node]:
            if colour.get(nxt, 0) == 1:
                result.fail("dependency_cycle", "cycle: " + " -> ".join([*stack, node, nxt]))
            elif colour.get(nxt, 0) == 0:
                visit(nxt, [*stack, node])
        colour[node] = 2

    for op in plan.ops:
        if colour[op.id] == 0:
            visit(op.id, [])


def check_dataflow(plan: Plan, result: CheckResult, preds: dict[str, set[str]]) -> None:
    for op in plan.ops:
        for ref in op.reads:
            chunk = plan.chunks[ref.key]
            if chunk.producer != EXTERNAL and chunk.producer not in preds[op.id]:
                result.fail(
                    "missing_dependency",
                    f"op {op.id} reads {ref.key} but its producer {chunk.producer} "
                    f"is not ordered before it (no dependency edge, direct or transitive)",
                )

    for key, chunk in plan.chunks.items():
        readers = [op.id for op in plan.ops if any(r.key == key for r in op.reads)]
        for consumer in chunk.consumers:
            consumer_op = plan.op(consumer)
            if not any(r.key == key for r in consumer_op.reads):
                result.fail(
                    "consumer_declaration_mismatch",
                    f"chunk {key} lists {consumer} as a consumer but that op does not read it",
                )
        for reader in readers:
            if reader not in chunk.consumers:
                result.fail(
                    "consumer_declaration_mismatch",
                    f"op {reader} reads {key} but the chunk does not list it as a consumer",
                )


def check_static_order(plan: Plan, result: CheckResult) -> None:
    """``static_order`` must be a genuine topological order of the DAG.

    A permutation of the op set that violates a dependency is not a schedule;
    accepting it would let the capacity walk pretend impossible orderings.
    """
    order = plan.order()
    op_ids = [op.id for op in plan.ops]
    if sorted(order) != sorted(op_ids):
        result.fail("bad_static_order", "static_order is not a permutation of the op set")
        return
    if len(set(order)) != len(order):
        result.fail("bad_static_order", "static_order contains duplicates")
        return
    position = {op_id: i for i, op_id in enumerate(order)}
    violations = [
        (dep, op.id)
        for op in plan.ops
        for dep in op.deps
        if position[dep] >= position[op.id]
    ]
    if violations:
        shown = ", ".join(f"{a}!<{b}" for a, b in violations[:5])
        result.fail(
            "static_order_not_topological",
            f"static_order is not a linear extension of deps ({len(violations)} violations, e.g. {shown})",
        )


def check_overwrite_safety(plan: Plan, result: CheckResult, preds: dict[str, set[str]]) -> None:
    """Physical-overwrite safety over the dependency partial order.

    For every pair of *distinct* chunks whose bytes physically overlap (same
    level/core/slot, intersecting ranges), one of them must be provably dead
    before the other is written - in **every** execution consistent with
    ``deps``. "Y is dead before X is written" means: every reader of Y is a
    transitive predecessor of X's producer (and if Y has no readers but an
    in-plan producer, that producer must also precede, so the write itself is
    not racing). An EXTERNAL chunk is always the older side (it exists before
    the plan starts). If neither direction is justified the plan is rejected.

    This deliberately does not use the declared ``static_order``: positional
    luck in one schedule says nothing about other legal interleavings.
    """
    by_slot: dict[tuple[str, int, int], list] = {}
    for chunk in plan.chunks.values():
        if chunk.on_chip:
            by_slot.setdefault(
                (chunk.placement.level, chunk.placement.core, chunk.placement.slot), []
            ).append(chunk)

    def dead_before(old, new) -> bool:
        """True when `old` is provably dead before `new` is written."""
        if new.producer == EXTERNAL:
            return False  # staged data is present from the start; it cannot be the newer side
        required = list(old.consumers)
        if not required and old.producer != EXTERNAL:
            required = [old.producer]
        return all(src in preds[new.producer] for src in required)

    for slot, chunks_here in by_slot.items():
        for i, a in enumerate(chunks_here):
            for b in chunks_here[i + 1:]:
                if not a.overlaps(b):
                    continue
                if a.producer == EXTERNAL and b.producer == EXTERNAL:
                    result.fail(
                        "unsafe_overwrite",
                        f"initial residents {a.key} and {b.key} overlap in {slot}; "
                        f"staging two live values over the same bytes is corrupt",
                    )
                    continue
                if a.producer == b.producer:
                    result.fail(
                        "unsafe_overwrite",
                        f"chunks {a.key} and {b.key} written by the same op {a.producer} "
                        f"overlap in {slot}",
                    )
                    continue
                # EXTERNAL is always the older side.
                older, newer = (a, b) if a.producer == EXTERNAL else (b, a) if b.producer == EXTERNAL else (None, None)
                if older is not None:
                    if not dead_before(older, newer):
                        readers = list(older.consumers)
                        result.fail(
                            "unsafe_overwrite",
                            f"chunk {newer.key} (producer {newer.producer}) overlaps initial "
                            f"resident {older.key} in {slot}; readers {readers} of {older.key} "
                            f"are not all ordered before {newer.producer}",
                        )
                    continue
                if not (dead_before(a, b) or dead_before(b, a)):
                    readers_a = list(a.consumers)
                    readers_b = list(b.consumers)
                    result.fail(
                        "unsafe_overwrite",
                        f"chunks {a.key} (producer {a.producer}, readers {readers_a}) and "
                        f"{b.key} (producer {b.producer}, readers {readers_b}) overlap in {slot} "
                        f"and neither side is provably dead before the other is written "
                        f"(waiting for one reader is not enough: every reader must complete)",
                    )


def check_capacity_and_reuse(plan: Plan, result: CheckResult, preds: dict[str, set[str]]) -> None:
    """Declared-order capacity walk (peaks) + reuse annotation consistency.

    Capacity/peak numbers are statements about the declared ``static_order``
    only. Overwrite *safety* is NOT decided here; see
    ``check_overwrite_safety``.
    """
    order = plan.order()
    position = {op_id: i for i, op_id in enumerate(order)}

    live: dict[tuple[str, int, int], list[str]] = {}  # slot -> live chunk keys
    used: dict[tuple[int, str], int] = {}  # (core, level) -> bytes currently resident
    peak: dict[tuple[int, str], int] = {}

    def occupy(chunk_key: str) -> None:
        chunk = plan.chunks[chunk_key]
        slot = (chunk.placement.level, chunk.placement.core, chunk.placement.slot)
        if chunk_key not in live.get(slot, []):
            live.setdefault(slot, []).append(chunk_key)
            level_core = (chunk.placement.core, chunk.placement.level)
            used[level_core] = used.get(level_core, 0) + chunk.size_bytes
            peak[level_core] = max(peak.get(level_core, 0), used[level_core])

    def release(chunk_key: str) -> None:
        chunk = plan.chunks[chunk_key]
        slot = (chunk.placement.level, chunk.placement.core, chunk.placement.slot)
        if chunk_key in live.get(slot, []):
            live[slot].remove(chunk_key)
            level_core = (chunk.placement.core, chunk.placement.level)
            used[level_core] = max(0, used.get(level_core, 0) - chunk.size_bytes)

    # Initial residents (external inputs/weights staged on-chip) occupy their
    # slots before any op runs.
    for key, chunk in plan.chunks.items():
        if chunk.initial_resident:
            occupy(key)

    for op_id in order:
        op = plan.op(op_id)

        # A chunk becomes resident when its producer runs.
        for ref in op.writes:
            chunk = plan.chunks[ref.key]
            if chunk.on_chip:
                occupy(ref.key)

        # A chunk is released once its last declared consumer has run
        # (within the declared static order).
        for ref in op.reads:
            chunk = plan.chunks[ref.key]
            if not chunk.on_chip:
                continue
            remaining = [c for c in chunk.consumers if position[c] > position[op_id]]
            if not remaining:
                release(ref.key)

    # Capacity (declared-order statement).
    for (core, level), peak_bytes in peak.items():
        capacity = plan.hardware.level_capacity(level)
        if peak_bytes > capacity:
            result.fail(
                "capacity_exceeded",
                f"core {core} {level} peak residency {peak_bytes} B exceeds capacity {capacity} B "
                f"(peak over the declared static_order)",
            )
    # Unreleased residents at end of plan (leaks / missing drain).
    for slot, keys in live.items():
        for chunk_key in keys:
            result.warn(
                "resident_not_released",
                f"chunk {chunk_key} in {slot} is never released by the end of the plan "
                f"(output residency or missing drain - must be intentional and charged)",
            )

    result.stats["peak_residency_bytes"] = {f"core{c}.{lvl}": v for (c, lvl), v in peak.items()}
    result.stats["peak_residency_scope"] = "declared static_order only"
    result.stats["capacity_bytes"] = {
        f"core{c}.{lvl}": plan.hardware.level_capacity(lvl) for (c, lvl) in peak
    }

    # ``reuse_of`` annotation consistency. The annotation never gates safety;
    # when present it must at least point at a chunk it physically overlaps.
    for chunk in plan.chunks.values():
        if not chunk.reuse_of:
            continue
        previous = plan.chunks.get(chunk.reuse_of)
        if previous is None:
            result.fail("bad_reuse_ref", f"chunk {chunk.key} reuses unknown chunk {chunk.reuse_of}")
            continue
        if not chunk.overlaps(previous):
            result.fail(
                "reuse_slot_mismatch",
                f"chunk {chunk.key} claims to reuse {chunk.reuse_of} but they do not "
                f"physically overlap (level/core/slot/byte-range differ)",
            )


def check_plan(plan: Plan) -> CheckResult:
    result = CheckResult()

    check_structure(plan, result)
    if not result.ok:
        # Unknown / duplicate ids make every later analysis unreliable; stop
        # here so no KeyError or recursion error can mask the original error.
        result.stats["analysis_stopped_at"] = "structure"
        return result

    check_acyclic(plan, result)
    if not result.ok:
        result.stats["analysis_stopped_at"] = "dependency_cycle"
        return result

    preds = _transitive_predecessors(plan)

    check_dataflow(plan, result, preds)
    if not result.ok:
        result.stats["analysis_stopped_at"] = "dataflow"
        return result

    check_static_order(plan, result)
    if not result.ok:
        result.stats["analysis_stopped_at"] = "static_order"
        return result

    check_overwrite_safety(plan, result, preds)
    check_capacity_and_reuse(plan, result, preds)
    if not result.ok:
        result.stats["analysis_stopped_at"] = "capacity_and_reuse"
    result.stats["ops"] = len(plan.ops)
    result.stats["chunks"] = len(plan.chunks)
    result.stats["remote_reads"] = len(plan.remote_reads())
    return result
