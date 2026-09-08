"""Event-driven finite-buffer service machine; see machine_contract.md.

No hardware-specific cost is hidden in the executor. Topology/transaction
builders supply operations; functional correctness is checked independently.
"""
from __future__ import annotations

from collections import defaultdict
import heapq
from typing import Any


def simulate(spec: dict[str, Any]) -> dict[str, Any]:
    buffers = spec["buffers"]
    groups = spec.get("groups", {})
    group_for = {}
    for gid, group in groups.items():
        for q in group["members"]:
            if q not in buffers or q in group_for:
                raise ValueError(f"invalid or duplicate group member {q}")
            group_for[q] = gid
    jobs = {j["id"]: j for j in spec["jobs"]}
    if len(jobs) != len(spec["jobs"]):
        raise ValueError("duplicate job id")
    all_ops = {f"{jid}:{k}" for jid, j in jobs.items() for k in range(len(j["ops"]))}
    for jid, j in jobs.items():
        if not j["ops"] or j.get("release", 0) < 0:
            raise ValueError(f"invalid job {jid}")
        if not set(j.get("deps", [])) <= all_ops:
            raise ValueError(f"unknown dependency in {jid}")
        for op in j["ops"]:
            if op["queue"] not in buffers or op["latency"] < 0:
                raise ValueError(f"invalid operation in {jid}")
            if any(v <= 0 or not isinstance(v, int) for v in op.get("resources", {}).values()):
                raise ValueError("resource intervals must be positive integer ticks")
    for name, b in buffers.items():
        if b["capacity"] is not None and b["capacity"] < 1:
            raise ValueError(f"invalid capacity {name}")
        if b.get("credit_delay", 0) < 0:
            raise ValueError("negative credit delay")

    queues: dict[str, list[tuple[int, str, int]]] = {q: [] for q in buffers}
    counts = {q: {"reserved": 0, "occupied": 0, "cooling": 0} for q in buffers}
    peaks = {q: 0 for q in buffers}
    physical_peaks = {q: 0 for q in buffers}
    last_service = {q: -1 for q in buffers}
    available: dict[str, int] = defaultdict(int)
    launches: dict[str, int] = defaultdict(int)
    locks: dict[str, str] = {}
    completed: dict[str, int] = {}
    job_end: dict[str, int] = {}
    operations: list[dict] = []
    pending = set(jobs)
    eligible = set()
    deps_left = {jid: len(set(j.get("deps", []))) for jid, j in jobs.items()}
    dependents = defaultdict(list)
    for jid, j in jobs.items():
        for dep in set(j.get("deps", [])):
            dependents[dep].append(jid)
    active_queues = set()
    events: list[tuple[int, int, str, Any]] = []
    serial = 0
    now = 0
    actual_last = 0
    transitions = 0

    def event(t: int, kind: str, payload: Any) -> None:
        nonlocal serial
        serial += 1
        heapq.heappush(events, (t, serial, kind, payload))

    def used(q: str) -> int:
        return sum(counts[q].values())

    def can_reserve(q: str) -> bool:
        b = buffers[q]
        if b["capacity"] is not None and used(q) >= b["capacity"]:
            return False
        gid = group_for.get(q)
        if gid:
            g = groups[gid]
            if used(q) >= g["per_member"]:
                return False
            shared = sum(max(used(member) - g["guaranteed"], 0) for member in g["members"])
            increment = int(used(q) >= g["guaranteed"])
            if shared + increment > g["shared"]:
                return False
        return True

    def record(q: str) -> None:
        n = used(q)
        if min(counts[q].values()) < 0:
            raise AssertionError((q, counts[q]))
        cap = buffers[q]["capacity"]
        if cap is not None and n > cap:
            raise AssertionError((q, n, cap))
        peaks[q] = max(peaks[q], n)
        physical_peaks[q] = max(physical_peaks[q], counts[q]["reserved"] + counts[q]["occupied"])
        gid = group_for.get(q)
        if gid:
            g = groups[gid]
            assert sum(max(used(m) - g["guaranteed"], 0) for m in g["members"]) <= g["shared"]

    def arrive(jid: str, k: int, reserved: bool) -> None:
        q = jobs[jid]["ops"][k]["queue"]
        if reserved:
            counts[q]["reserved"] -= 1
        counts[q]["occupied"] += 1
        heapq.heappush(queues[q], (now, jid, k))
        active_queues.add(q)
        record(q)

    for jid, j in jobs.items():
        if not deps_left[jid]:
            event(j.get("release", 0), "admit", jid)

    status = "ok"
    while True:
        # All completions at this tick precede any arbitration. Zero-time
        # completions created by a dispatch return through this phase too.
        while events and events[0][0] == now:
            _, _, kind, payload = heapq.heappop(events)
            if kind == "wake":
                continue
            if kind == "admit":
                eligible.add(payload)
                continue
            actual_last = max(actual_last, now)
            if kind == "credit":
                counts[payload]["cooling"] -= 1
                record(payload)
            elif kind == "done":
                jid, k = payload
                job = jobs[jid]
                op = job["ops"][k]
                completed[f"{jid}:{k}"] = now
                for waiting in dependents.get(f"{jid}:{k}", []):
                    deps_left[waiting] -= 1
                    if not deps_left[waiting]:
                        event(max(now, jobs[waiting].get("release", 0)), "admit", waiting)
                lock = op.get("lock")
                if lock and job["tail"]:
                    assert locks.get(lock) == job["packet"]
                    del locks[lock]
                if k + 1 < len(job["ops"]):
                    arrive(jid, k + 1, True)
                else:
                    job_end[jid] = now
            else:
                raise AssertionError(kind)

        # A job is admitted only once the application dependencies and the
        # first queue's capacity both permit it.
        for jid in sorted(eligible):
            j = jobs[jid]
            if j.get("release", 0) <= now and all(dep in completed for dep in j.get("deps", [])):
                q = j["ops"][0]["queue"]
                if can_reserve(q):
                    arrive(jid, 0, False)
                    pending.remove(jid)
                    eligible.remove(jid)

        feasible = []
        for q in active_queues:
            contents = queues[q]
            if not contents:
                continue
            _, jid, k = contents[0]
            j = jobs[jid]
            op = j["ops"][k]
            if any(available[r] > now for r in op.get("resources", {})):
                continue
            if k + 1 < len(j["ops"]) and not can_reserve(j["ops"][k + 1]["queue"]):
                continue
            if op.get("lock") in locks and locks[op["lock"]] != j["packet"]:
                continue
            feasible.append((last_service[q], q, jid, k))

        if feasible:
            rank = min(f[0] for f in feasible)
            tied = [f for f in feasible if f[0] == rank]
            _, q, jid, k = sorted(tied, key=lambda f: (f[1], f[2]),
                                  reverse=spec.get("tie_break", "ascending") == "descending")[0]
            j = jobs[jid]
            op = j["ops"][k]
            heapq.heappop(queues[q])
            if not queues[q]:
                active_queues.remove(q)
            counts[q]["occupied"] -= 1
            counts[q]["cooling"] += 1
            event(now + buffers[q].get("credit_delay", 0), "credit", q)
            if k + 1 < len(j["ops"]):
                nq = j["ops"][k + 1]["queue"]
                counts[nq]["reserved"] += 1
                record(nq)
            last_service[q] = now
            for r, ii in op.get("resources", {}).items():
                available[r] = now + ii
                launches[r] += 1
                event(now + ii, "wake", None)
            if op.get("lock"):
                locks[op["lock"]] = j["packet"]
            record(q)
            operations.append({"id": f"{jid}:{k}", "start": now,
                               "end": now + op["latency"], "queue": q,
                               "resources": op.get("resources", {}), "lock": op.get("lock")})
            event(now + op["latency"], "done", (jid, k))
            transitions += 1
            if transitions > spec.get("max_operations", 10_000_000):
                raise RuntimeError("operation budget exceeded")
            continue

        if events:
            now = events[0][0]
            continue
        if len(job_end) != len(jobs) or locks:
            status = "deadlock"
        break

    return {"status": status, "operations": operations, "job_end": job_end,
            "quiescent": actual_last if status == "ok" else None,
            "stopped_at": now, "buffer_peaks": peaks,
            "physical_buffer_peaks": physical_peaks, "resource_launches": dict(launches),
            "unfinished_jobs": sorted(set(jobs) - set(job_end)),
            "waiting_queues": {q: [(jid, k) for _, jid, k in qs] for q, qs in queues.items() if qs},
            "pending_jobs": sorted(pending), "locks_at_end": dict(locks),
            "final_buffers": counts}
