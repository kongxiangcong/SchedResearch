"""Toy discrete-event model: self-timed (fixed per-resource order) vs
static-assignment (dynamic per-resource order) dispatch on an NPU-like
machine with per-core compute engines and a shared or per-core DMA.

Not a TARS-calibrated model. Purpose: bound the *order-freedom* gain as a
function of independent streams, cores, latency variance and memory-reuse
false dependencies.
"""
import heapq
import math
import random
import statistics
import sys
from dataclasses import dataclass, field


@dataclass
class Task:
    tid: int
    kind: str            # "load" or "comp"
    resource: str        # "dma" / "dma0" ... or "core0" ...
    mean: float
    preds: set = field(default_factory=set)
    succs: set = field(default_factory=set)
    prio: float = 0.0


def build(streams, ops_per_stream, cores, shared_dma, reuse_pressure,
          long_c=100.0, short_c=10.0, long_l=60.0, short_l=15.0):
    """Each stream is a serial chain of ops (long/short alternating), like one
    transformer block per stream. Each op = LOAD (on DMA) -> COMP (on core).
    reuse_pressure in [0,1]: fraction of cross-stream buffer-reuse WAR edges
    posted: COMP(s, j+1) must finish before LOAD(s+1, j) may start, i.e. the
    same address range is reused by the next stream's same op.
    """
    tasks = []
    grid = {}
    for s in range(streams):
        core = f"core{s % cores}"
        dma = "dma" if shared_dma else f"dma{s % cores}"
        for j in range(ops_per_stream):
            long = (j % 2 == 0)
            ld = Task(len(tasks), "load", dma, long_l if long else short_l)
            tasks.append(ld)
            cp = Task(len(tasks), "comp", core, long_c if long else short_c)
            tasks.append(cp)
            grid[(s, j)] = (ld, cp)
            ld.succs.add(cp.tid); cp.preds.add(ld.tid)
            if j > 0:
                prev_cp = grid[(s, j - 1)][1]
                prev_cp.succs.add(ld.tid); ld.preds.add(prev_cp.tid)
    rng = random.Random(7)
    for s in range(streams - cores):
        for j in range(ops_per_stream - 1):
            if rng.random() < reuse_pressure:
                a = grid[(s, j + 1)][1]      # reader of buffer (s,j) output
                b = grid[(s + cores, j)][0]  # next stream on same core reuses the address
                a.succs.add(b.tid); b.preds.add(a.tid)
    # static priority = longest path to sink using mean durations
    order = topo(tasks)
    for t in reversed(order):
        t.prio = t.mean + max((tasks[x].prio for x in t.succs), default=0.0)
    return tasks


def topo(tasks):
    indeg = {t.tid: len(t.preds) for t in tasks}
    ready = [t.tid for t in tasks if indeg[t.tid] == 0]
    out = []
    while ready:
        x = ready.pop()
        out.append(tasks[x])
        for y in tasks[x].succs:
            indeg[y] -= 1
            if indeg[y] == 0:
                ready.append(y)
    assert len(out) == len(tasks), "cycle"
    return out


def simulate(tasks, durations, fixed_order=None):
    """Event-driven execution. If fixed_order is given (dict resource ->
    list of tids), each resource dispatches strictly in that order (self-timed).
    Otherwise each free resource picks the ready task with highest prio
    (static assignment, dynamic ordering)."""
    n = len(tasks)
    remaining = {t.tid: len(t.preds) for t in tasks}
    done_time = {}
    busy_until = {}
    ready = {}       # resource -> set of ready tids
    ptr = {}         # resource -> index into fixed order
    for t in tasks:
        ready.setdefault(t.resource, set())
        busy_until.setdefault(t.resource, 0.0)
        ptr.setdefault(t.resource, 0)
    for t in tasks:
        if remaining[t.tid] == 0:
            ready[t.resource].add(t.tid)
    events = []      # (time, tid)
    now = 0.0
    started = set()

    def try_dispatch(res):
        nonlocal now
        if busy_until[res] > now + 1e-12:
            return
        if fixed_order is not None:
            lst = fixed_order[res]
            if lst and isinstance(lst[0], list):
                # per-core lanes on a shared resource: each lane is in-order,
                # the shared resource arbitrates dynamically among lane heads
                # (models TARS: per-core in-order DMA issue, shared channel).
                cands = []
                for li, lane in enumerate(lst):
                    p = ptr.setdefault((res, li), 0)
                    if p < len(lane) and lane[p] in ready[res]:
                        cands.append((li, lane[p]))
                if not cands:
                    return
                li, pick = max(cands, key=lambda c: (tasks[c[1]].prio, -c[1]))
                ptr[(res, li)] += 1
            else:
                if ptr[res] >= len(lst):
                    return
                nxt = lst[ptr[res]]
                if nxt not in ready[res]:
                    return
                pick = nxt
                ptr[res] += 1
        else:
            if not ready[res]:
                return
            pick = max(ready[res], key=lambda x: (tasks[x].prio, -x))
        ready[res].discard(pick)
        started.add(pick)
        fin = now + durations[pick]
        busy_until[res] = fin
        heapq.heappush(events, (fin, pick))

    for res in list(ready):
        try_dispatch(res)
    while events:
        now, tid = heapq.heappop(events)
        done_time[tid] = now
        for y in tasks[tid].succs:
            remaining[y] -= 1
            if remaining[y] == 0:
                ready[tasks[y].resource].add(y)
        for res in list(ready):
            try_dispatch(res)
    if len(done_time) != n:
        return float("inf")  # deadlock in fixed-order mode
    return max(done_time.values())


def static_list_schedule(tasks):
    """List scheduling with mean durations -> per-resource order."""
    means = {t.tid: t.mean for t in tasks}
    # reuse the dynamic simulator with mean durations to derive an order
    order = {}
    n = len(tasks)
    remaining = {t.tid: len(t.preds) for t in tasks}
    busy_until = {t.resource: 0.0 for t in tasks}
    ready = {t.resource: set() for t in tasks}
    for t in tasks:
        if remaining[t.tid] == 0:
            ready[t.resource].add(t.tid)
    events = []
    now = 0.0
    seq = {r: [] for r in ready}

    def dispatch(res):
        if busy_until[res] > now + 1e-12 or not ready[res]:
            return
        pick = max(ready[res], key=lambda x: (tasks[x].prio, -x))
        ready[res].discard(pick)
        seq[res].append(pick)
        fin = now + means[pick]
        busy_until[res] = fin
        heapq.heappush(events, (fin, pick))

    for r in ready:
        dispatch(r)
    while events:
        now, tid = heapq.heappop(events)
        for y in tasks[tid].succs:
            remaining[y] -= 1
            if remaining[y] == 0:
                ready[tasks[y].resource].add(y)
        for r in ready:
            dispatch(r)
    return seq


def sample_durations(tasks, cov, rng, dma_only=False, tail_p=0.0, tail_x=4.0):
    out = {}
    for t in tasks:
        c = cov if (t.kind == "load" or not dma_only) else 0.0
        if c <= 0:
            v = t.mean
        else:
            sigma = math.sqrt(math.log(1 + c * c))
            mu = math.log(t.mean) - sigma * sigma / 2
            v = rng.lognormvariate(mu, sigma)
        if tail_p > 0 and rng.random() < tail_p:
            v *= tail_x
        out[t.tid] = v
    return out


def add_cross_core_coupling(tasks, streams, cores, ops_per_stream, every=4):
    """Pair stream s (core s%cores) with stream s^1 (its sibling on another
    core when cores>1): every `every`-th op of each needs the sibling's
    previous op output (models head-split partial-sum exchange)."""
    by_key = {}
    for t in tasks:
        pass
    # rebuild grid from ids: tasks were appended (ld, cp) per (s, j)
    idx = 0
    grid = {}
    for s in range(streams):
        for j in range(ops_per_stream):
            grid[(s, j)] = (tasks[idx], tasks[idx + 1])
            idx += 2
    for s in range(streams):
        sib = s ^ 1
        if sib >= streams or (sib % cores) == (s % cores):
            continue
        for j in range(every, ops_per_stream, every):
            prod = grid[(sib, j - 1)][1]
            cons = grid[(s, j)][0]
            prod.succs.add(cons.tid); cons.preds.add(prod.tid)
    order = topo(tasks)
    for t in tasks:
        t.prio = 0.0
    for t in reversed(order):
        t.prio = t.mean + max((tasks[x].prio for x in t.succs), default=0.0)


def run(streams, cores, shared_dma, cov, reuse, trials=200, dma_only=True,
        tail_p=0.0, couple=False):
    tasks = build(streams, 12, cores, shared_dma, reuse)
    if couple:
        add_cross_core_coupling(tasks, streams, cores, 12)
    fixed = static_list_schedule(tasks)
    # TARS-like baseline: shared DMA order fixed per core lane, arbitrated
    # dynamically across cores; compute order fixed per core.
    lanes = dict(fixed)
    if shared_dma and "dma" in lanes:
        per_core = {}
        for tid in lanes["dma"]:
            s = tasks[tid].tid // (2 * 12)   # stream id
            per_core.setdefault(s % cores, []).append(tid)
        lanes["dma"] = [per_core[c] for c in sorted(per_core)]
    rng = random.Random(1)
    st, lane, sa = [], [], []
    for _ in range(trials):
        d = sample_durations(tasks, cov, rng, dma_only=dma_only, tail_p=tail_p)
        st.append(simulate(tasks, d, fixed))
        lane.append(simulate(tasks, d, lanes))
        sa.append(simulate(tasks, d, None))
    mst, mlane, msa = statistics.mean(st), statistics.mean(lane), statistics.mean(sa)
    return mst, mlane, msa, (mst - msa) / mst * 100.0, (mlane - msa) / mlane * 100.0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "base"
    print(f"mode={mode}")
    print("streams cores dma      cov   reuse | self-timed  lane-ST  static-assign  gain%vsST  gain%vsLane")
    configs = []
    for cores, shared in ((2, True), (2, False), (8, False)):
        for streams in (cores, 2 * cores, 4 * cores):
            for cov in (0.1, 0.3, 0.6):
                for reuse in (0.0, 0.5, 1.0):
                    configs.append((streams, cores, shared, cov, reuse))
    kw = {}
    if mode == "tail":
        kw = dict(tail_p=0.05, dma_only=False)
    elif mode == "couple":
        kw = dict(couple=True, dma_only=False)
    elif mode == "tailcouple":
        kw = dict(tail_p=0.05, couple=True, dma_only=False)
    for streams, cores, shared, cov, reuse in configs:
        mst, mlane, msa, g, gl = run(streams, cores, shared, cov, reuse, **kw)
        print(f"{streams:7d} {cores:5d} {'shared' if shared else 'percore':8s} "
              f"{cov:4.1f} {reuse:5.1f} | {mst:10.0f} {mlane:8.0f} {msa:13.0f} "
              f"{g:9.1f} {gl:11.1f}")