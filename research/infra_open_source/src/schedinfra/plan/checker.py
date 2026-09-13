"""Legality checker for candidate plans.

Scope and honesty about it
--------------------------
These checks are *necessary* conditions on a static plan. They operate on the
plan's declared ``static_order`` (one linear extension of the dependency DAG).
That makes them timing-independent and therefore checkable without a backend,
but it also means:

* **Capacity and reuse are checked against the declared order.** A timing
  backend that interleaves differently could still overflow. So this is a
  plan-legality gate, not a substitute for observing real residency.
* **Dependency, coverage and exclusivity checks are order-independent** and do
  hold for every legal execution.

Every check reports *why* it failed. A rejection is a result, not a crash.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .schema import EXTERNAL, LEVEL_ACCUM, LEVEL_SPAD, Plan


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
    op_ids = {op.id for op in plan.ops}
    if len(op_ids) != len(plan.ops):
        result.fail("duplicate_op_id", "plan contains duplicate op ids")

    for op in plan.ops:
        for dep in op.deps:
            if dep not in op_ids:
                result.fail("unknown_dep", f"op {op.id} depends on unknown op {dep}")
        for ref in (*op.reads, *op.writes):
            if ref.key not in plan.chunks:
                result.fail("unknown_chunk", f"op {op.id} references undeclared chunk {ref.key}")

    for key, chunk in plan.chunks.items():
        if chunk.producer != EXTERNAL and chunk.producer not in op_ids:
            result.fail("unknown_producer", f"chunk {key} produced by unknown op {chunk.producer}")
        for consumer in chunk.consumers:
            if consumer not in op_ids:
                result.fail("unknown_consumer", f"chunk {key} consumed by unknown op {consumer}")
        if chunk.placement.level in (LEVEL_SPAD, LEVEL_ACCUM):
            if not (0 <= chunk.placement.core < plan.hardware.cores):
                result.fail("bad_core", f"chunk {key} placed on core {chunk.placement.core} outside 0..{plan.hardware.cores - 1}")


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


def check_dataflow(plan: Plan, result: CheckResult) -> None:
    preds = _transitive_predecessors(plan)

    writes: dict[str, list[str]] = {}
    for op in plan.ops:
        for ref in op.writes:
            writes.setdefault(ref.key, []).append(op.id)
    for key, producers in writes.items():
        if len(producers) > 1:
            result.fail("multiple_writers", f"chunk {key} written by {producers}")

    for op in plan.ops:
        for ref in op.reads:
            chunk = plan.chunks.get(ref.key)
            if chunk is None:
                continue  # already reported
            if chunk.producer != EXTERNAL and chunk.producer not in preds[op.id]:
                result.fail(
                    "missing_dependency",
                    f"op {op.id} reads {ref.key} but its producer {chunk.producer} "
                    f"is not ordered before it (no dependency edge, direct or transitive)",
                )

    for key, chunk in plan.chunks.items():
        for consumer in chunk.consumers:
            consumer_op = plan.op(consumer)
            if not any(r.key == key for r in consumer_op.reads):
                result.fail(
                    "consumer_declaration_mismatch",
                    f"chunk {key} lists {consumer} as a consumer but that op does not read it",
                )
        for op in plan.ops:
            if any(r.key == key for r in op.reads) and op.id not in chunk.consumers:
                result.fail(
                    "consumer_declaration_mismatch",
                    f"op {op.id} reads {key} but the chunk does not list it as a consumer",
                )
        if chunk.ref.tensor != _tensor_of(key):
            result.fail("chunk_key_corrupt", f"chunk {key} key does not match its ref")


def _tensor_of(key: str) -> str:
    return key.rsplit("#", 1)[0]


def check_capacity_and_reuse(plan: Plan, result: CheckResult) -> None:
    """Walk the declared static order, tracking residency, peak and reuse."""
    order = plan.order()
    if sorted(order) != sorted(op.id for op in plan.ops):
        result.fail("bad_static_order", "static_order is not a permutation of the op set")
        return
    if len(set(order)) != len(order):
        result.fail("bad_static_order", "static_order contains duplicates")
        return

    live: dict[tuple[str, int, int], str] = {}  # (level, core, slot) -> chunk key
    used: dict[tuple[int, str], int] = {}  # (core, level) -> bytes currently resident
    peak: dict[tuple[int, str], int] = {}
    resident_at_free: dict[str, int] = {}

    for op_id in order:
        op = plan.op(op_id)

        # A chunk becomes resident when its producer runs.
        for ref in op.writes:
            chunk = plan.chunks.get(ref.key)
            if chunk is None or chunk.placement.level not in (LEVEL_SPAD, LEVEL_ACCUM):
                continue
            key = (chunk.placement.level, chunk.placement.core, chunk.placement.slot)
            level_core = (chunk.placement.core, chunk.placement.level)
            if key in live:
                previous = live[key]
                if previous == chunk.key:
                    continue
                result.fail(
                    "slot_conflict",
                    f"chunk {chunk.key} placed in {key} while {previous} is still resident; "
                    f"a slot may only be reused after the previous chunk is released",
                )
            live[key] = chunk.key
            used[level_core] = used.get(level_core, 0) + chunk.size_bytes
            peak[level_core] = max(peak.get(level_core, 0), used.get(level_core, 0))

        # A chunk is released once its last declared consumer has run.
        for ref in op.reads:
            chunk = plan.chunks.get(ref.key)
            if chunk is None or chunk.placement.level not in (LEVEL_SPAD, LEVEL_ACCUM):
                continue
            remaining = [
                c for c in chunk.consumers if order.index(c) > order.index(op_id)
            ]
            if remaining:
                continue  # still needed
            key = (chunk.placement.level, chunk.placement.core, chunk.placement.slot)
            level_core = (chunk.placement.core, chunk.placement.level)
            if live.get(key) == chunk.key:
                del live[key]
                used[level_core] = max(0, used.get(level_core, 0) - chunk.size_bytes)
                resident_at_free[chunk.key] = order.index(op_id)

    # Capacity
    for (core, level), peak_bytes in peak.items():
        capacity = plan.hardware.level_capacity(level)
        if peak_bytes > capacity:
            result.fail(
                "capacity_exceeded",
                f"core {core} {level} peak residency {peak_bytes} B exceeds capacity {capacity} B",
            )
    # Unreleased residents at end of plan (leaks / missing drain).
    for key, chunk_key in live.items():
        result.warn(
            "resident_not_released",
            f"chunk {chunk_key} in {key} is never released by the end of the plan "
            f"(output residency or missing drain - must be intentional and charged)",
        )

    result.stats["peak_residency_bytes"] = {f"core{c}.{lvl}": v for (c, lvl), v in peak.items()}
    result.stats["capacity_bytes"] = {
        f"core{c}.{lvl}": plan.hardware.level_capacity(lvl) for (c, lvl) in peak
    }

    # Reuse legality: a slot reuse must be justified by an explicit order edge.
    for chunk in plan.chunks.values():
        if not chunk.reuse_of:
            continue
        previous = plan.chunks.get(chunk.reuse_of)
        if previous is None:
            result.fail("bad_reuse_ref", f"chunk {chunk.key} reuses unknown chunk {chunk.reuse_of}")
            continue
        if previous.placement.slot != chunk.placement.slot or previous.placement.core != chunk.placement.core:
            result.fail(
                "reuse_slot_mismatch",
                f"chunk {chunk.key} claims to reuse {chunk.reuse_of} but the slots differ",
            )
            continue
        freed_at = resident_at_free.get(previous.key)
        if freed_at is None:
            result.fail(
                "premature_reuse",
                f"chunk {chunk.key} reuses the slot of {previous.key}, which is never released",
            )
            continue
        allocated_at = order.index(chunk.producer)
        if allocated_at < freed_at:
            result.fail(
                "premature_reuse",
                f"chunk {chunk.key} is produced at position {allocated_at} but its slot is only "
                f"freed at {freed_at} (reuse before the previous chunk's last read)",
            )
            continue
        # A static reuse also needs a real order edge, not just positional luck.
        required = list(previous.consumers) or [previous.producer]
        preds = _transitive_predecessors(plan)
        if not any(src in preds[chunk.producer] for src in required):
            result.fail(
                "reuse_without_order_edge",
                f"chunk {chunk.key} reuses {previous.key} but no dependency edge orders "
                f"{required} before its producer",
            )


def check_plan(plan: Plan) -> CheckResult:
    result = CheckResult()
    check_structure(plan, result)
    check_acyclic(plan, result)
    check_dataflow(plan, result)
    check_capacity_and_reuse(plan, result)
    result.stats["ops"] = len(plan.ops)
    result.stats["chunks"] = len(plan.chunks)
    return result
