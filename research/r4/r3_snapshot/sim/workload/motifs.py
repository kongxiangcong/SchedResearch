"""Inspectable synthetic DAGs. LLM/DiT labels denote structure, not model traces."""
from sim.workload import Task, Edge, Workload
from sim.noc import transfer_resources


def arrival_reversal():
    return Workload("arrival_reversal", (
        Task("load0", "memory", ("dma0",), 100),
        Task("load1", "memory", ("dma1",), 100),
        Task("vpu0", "compute", ("vpu",), 20),
        Task("vpu1", "compute", ("vpu",), 20)),
        (Edge("load0", "vpu0"), Edge("load1", "vpu1")),
        "Bounded arrival reversal; two independent sources and one shared engine; no aliases.")


def synthetic(shape="pipeline", cores=2, clusters=1, chips=1, stages=3):
    tasks, edges, task_kinds = [], [], {}
    def add(tid, kind, res, time, domain="chip0.cluster0", deps=()):
        tasks.append(Task(tid, kind, tuple(res), time, domain))
        task_kinds[tid] = kind
        edges.extend(Edge(p, tid, "completion" if kind == "sync" or task_kinds[p] == "sync" else "data") for p in deps)
        return tid
    if shape == "chain":
        previous = None
        for i in range(stages * 4):
            previous = add(f"t{i:03}", "memory" if i % 3 == 0 else "compute",
                           ("dma",) if i % 3 == 0 else ("mxu",), 15 if i % 3 == 0 else 60,
                           deps=() if previous is None else (previous,))
    elif shape in {"fork_join", "diamond", "critical_background"}:
        root = add("root", "compute", ("vpu0",), 10)
        tails = []
        for c in range(cores * 2):
            load = add(f"b{c}.load", "memory", (f"dma{c % cores}",), 20 + c * 5, deps=(root,))
            tail = add(f"b{c}.compute", "compute", (f"mxu{c % cores}",), 100 if c == 0 else 20, deps=(load,))
            tails.append(tail)
        add("join", "compute", ("vpu0",), 20, deps=tuple(tails))
        if shape == "critical_background":
            for i in range(cores * 2):
                add(f"background{i}", "compute", (f"mxu{i % cores}",), 30)
        if shape == "diamond":
            add("final", "memory", ("dma0",), 15, deps=("join",))
    elif shape == "dit_cfg":
        previous_step = ()
        for step in range(stages):
            conditioning = add(f"step{step}.conditioning", "compute", ("conditioning.vpu",), 15, deps=previous_step)
            branch_outputs = []
            for branch in ("cond", "uncond"):
                core_outputs = []
                for c in range(cores):
                    domain = "chip0.cluster0"
                    prefix = f"step{step}.{branch}.core{c}"
                    engine = f"{domain}.core{c}"
                    load = add(prefix + ".load", "memory", (domain + ".dma", domain + ".sram"), 25, domain, previous_step)
                    adaln = add(prefix + ".adaln", "compute", (engine + ".vpu", domain + ".sram"), 12,
                                domain, (conditioning, load))
                    qkv = add(prefix + ".qkv", "compute", (engine + ".mxu",), 70, domain, (adaln,))
                    attn = add(prefix + ".attention", "compute", (engine + ".mxu",), 40, domain, (qkv,))
                    softmax = add(prefix + ".softmax", "compute", (engine + ".vpu",), 15, domain, (attn,))
                    ffn = add(prefix + ".ffn", "compute", (engine + ".mxu",), 90, domain, (softmax,))
                    gate = add(prefix + ".gate", "compute", (engine + ".vpu",), 8, domain, (ffn, adaln))
                    core_outputs.append(gate)
                branch_outputs.append(add(f"step{step}.{branch}.gather", "communication", ("chip0.noc",), 15,
                                          deps=tuple(core_outputs)))
            join = add(f"step{step}.cfg_combine", "compute", ("conditioning.vpu",), 12, deps=tuple(branch_outputs))
            previous_step = (join,)
    else:
        total = cores * clusters * chips
        previous = {}
        for stage in range(stages):
            next_previous = {}
            for c in range(total):
                chip = c // (cores * clusters)
                cluster = (c // cores) % clusters
                local = c % cores
                domain = f"chip{chip}.cluster{cluster}"
                engine = f"{domain}.core{local}"
                prefix = f"s{stage:02}.c{c:02}"
                deps = () if c not in previous else (previous[c],)
                load = add(prefix + ".load", "memory", (domain + ".dma", domain + ".sram"),
                           20 + 5 * (c % 3), domain, deps)
                norm = add(prefix + ".norm", "compute", (engine + ".vpu", domain + ".sram"), 8, domain, (load,))
                # Q/K/V or AdaLN-conditioned attention are motifs only; fixed model constants are arbitrary.
                q = add(prefix + ".q", "compute", (engine + ".mxu",), 60, domain, (norm,))
                if shape in {"llm_prefill", "dit_cfg"}:
                    kv = add(prefix + ".kv", "memory", (domain + ".dma", domain + ".sram"), 35, domain, (norm,))
                    attention_deps = (q, kv)
                elif shape == "llm_decode":
                    kv = add(prefix + ".kv", "memory", (domain + ".dma", domain + ".sram"), 180, domain, (norm,))
                    attention_deps = (q, kv)
                else:
                    attention_deps = (q,)
                v = add(prefix + ".softmax", "compute", (engine + ".vpu",), 12, domain, attention_deps)
                ff = add(prefix + ".ffn", "compute", (engine + ".mxu",), 90, domain, (v,))
                if clusters * chips > 1:
                    peer = (c + cores) % total
                    dst_chip = peer // (cores * clusters)
                    dst_cluster = (peer // cores) % clusters
                    ff = add(prefix + ".exchange", "communication",
                             transfer_resources(chip, cluster, dst_chip, dst_cluster), 25, domain, (ff,))
                next_previous[c] = ff
            if clusters * chips > 1:
                # Barrier across partitions: a deliberate counterexample to automatic scale=>freedom.
                barrier = add(f"s{stage:02}.barrier", "sync", ("barrier",), 1,
                              deps=tuple(next_previous.values()))
                previous = {c: barrier for c in next_previous}
            else:
                previous = next_previous
    return Workload(shape, tuple(tasks), tuple(edges),
                    "Synthetic structural motif; uncalibrated service constants; no tensor numerics or full-model claim.")


def tile(workload, pieces):
    """Assume perfectly separable corresponding tiles; work and mapping are preserved.

    Full-operation synchronization/reduction dependencies remain full barriers.
    This changes legal overlap via an explicit semantic assumption, not a measured lowering.
    """
    if pieces == 1:
        return workload
    tasks = tuple(Task(f"{t.tid}.tile{i}", t.kind, t.resources, t.predicted / pieces,
                       t.domain, max(64, (t.output_bytes + pieces - 1) // pieces))
                  for t in workload.tasks for i in range(pieces))
    edges = []
    for e in workload.edges:
        if e.kind == "data":
            edges.extend(Edge(f"{e.producer}.tile{i}", f"{e.consumer}.tile{i}", e.kind) for i in range(pieces))
        else:
            edges.extend(Edge(f"{e.producer}.tile{i}", f"{e.consumer}.tile{j}", e.kind)
                         for i in range(pieces) for j in range(pieces))
    return Workload(workload.name + f"_tiles{pieces}", tasks, tuple(edges), workload.description + " Independent corresponding tiles assumed.")
