"""Minimal lowering: task graph -> static placement/storage -> dependency contract."""
from dataclasses import dataclass, replace
import math
import random
from sim.workload import topology
from sim.memory import allocate, validate_storage


@dataclass(frozen=True)
class Contract:
    workload: object
    buffers: tuple
    priority: dict
    admission_order: tuple
    resource_order: dict
    predicted_makespan: float = 0.0
    compiler_policy: str = "unselected"

    def validate(self, hardware):
        hardware.validate()
        order = topology(self.workload)
        task_map = {t.tid: t for t in self.workload.tasks}
        for t in task_map.values():
            if not isinstance(t.output_bytes, int) or t.output_bytes <= 0:
                raise ValueError("task output byte count must be a positive integer")
            if not math.isfinite(t.predicted) or t.predicted <= 0:
                raise ValueError("task service time must be finite and positive")
            if not t.resources or len(t.resources) != len(set(t.resources)):
                raise ValueError("each task needs distinct resource names")
        if set(self.priority) != set(order) or any(not math.isfinite(x) for x in self.priority.values()):
            raise ValueError("invalid priority metadata")
        if len(self.admission_order) != len(order) or set(self.admission_order) != set(order):
            raise ValueError("admission order must contain every descriptor once")
        position = {x: i for i, x in enumerate(self.admission_order)}
        if any(position[e.producer] >= position[e.consumer] for e in self.workload.edges):
            raise ValueError("admission order must be topological to guarantee bounded-window progress")
        succ = {x: [] for x in order}
        for e in self.workload.edges:
            succ[e.producer].append(e.consumer)
        reaches = {x: set() for x in order}
        for x in reversed(order):
            for y in succ[x]:
                reaches[x].add(y)
                reaches[x].update(reaches[y])
        if set(b.owner for b in self.buffers) != set(order) or len(self.buffers) != len(order):
            raise ValueError("one output buffer per task is required")
        for b in self.buffers:
            if b.size < task_map[b.owner].output_bytes:
                raise ValueError("buffer size does not cover task output bytes")
            expected = {e.consumer for e in self.workload.edges if e.producer == b.owner and e.kind == "data"}
            if set(b.readers) != expected or b.domain != task_map[b.owner].domain:
                raise ValueError("buffer provenance mismatch")
        validate_storage(self.buffers, reaches, hardware.memory_capacity)
        expected_resources = {r for t in task_map.values() for r in t.resources}
        if self.resource_order:
            if set(self.resource_order) != expected_resources:
                raise ValueError("static resource orders incomplete")
            augmented = list(self.workload.edges)
            from sim.workload import Edge, Workload
            pairs = {(e.producer, e.consumer) for e in augmented}
            for r, tids in self.resource_order.items():
                expected = {t.tid for t in task_map.values() if r in t.resources}
                if set(tids) != expected or len(tids) != len(expected):
                    raise ValueError("static resource order mismatch")
                for a, b in zip(tids, tids[1:]):
                    if (a, b) not in pairs:
                        augmented.append(Edge(a, b, "completion")); pairs.add((a, b))
            topology(Workload("static-order-check", self.workload.tasks, tuple(augmented), ""))
            if any(position[e.producer] >= position[e.consumer] for e in augmented):
                raise ValueError("admission order incompatible with static resource order; bounded-window progress unproven")

    def descriptors(self):
        buffers = {b.owner: b for b in self.buffers}
        return [{"task_id": t.tid, "completion_event": t.tid,
                 "wait": [{"event": e.producer, "kind": e.kind} for e in self.workload.edges if e.consumer == t.tid],
                 "where": t.resources, "domain": t.domain, "predicted_latency": t.predicted,
                 "priority": self.priority[t.tid], "output_address": buffers[t.tid].address,
                 "output_bytes": buffers[t.tid].size}
                for t in self.workload.tasks]


def candidates(workload, random_count=4):
    order = topology(workload)
    tasks = {t.tid: t for t in workload.tasks}
    succ = {x: [] for x in order}
    for e in workload.edges:
        succ[e.producer].append(e.consumer)
    cp = {}
    for x in reversed(order):
        cp[x] = tasks[x].predicted + max((cp[y] for y in succ[x]), default=0)
    policies = {"critical_path": cp,
                "shortest": {x: -tasks[x].predicted for x in order},
                "longest": {x: tasks[x].predicted for x in order},
                "fanout": {x: len(succ[x]) + cp[x] / max(cp.values()) for x in order}}
    for seed in range(random_count):
        rng = random.Random(seed)
        policies[f"random_{seed}"] = {x: rng.random() for x in order}
    return [Contract(workload, allocate(workload), p, tuple(order), {}, compiler_policy=name)
            for name, p in policies.items()]


def compile_candidates(workload):
    from sim.hardware_model import Hardware
    from sim.execution import simulate
    durations = {t.tid: t.predicted for t in workload.tasks}
    result = []
    for contract in candidates(workload):
        trial = simulate(contract, Hardware(), durations, "B")
        orders = {r: [] for t in workload.tasks for r in t.resources}
        starts = sorted(trial.trace, key=lambda e: (e["dispatch"], e["sequence"]))
        task_map = {t.tid: t for t in workload.tasks}
        for entry in starts:
            for r in task_map[entry["task"]].resources:
                orders[r].append(entry["task"])
        result.append(replace(contract, admission_order=tuple(e["task"] for e in starts),
                              resource_order={r: tuple(ids) for r, ids in orders.items()},
                              predicted_makespan=trial.latency))
    return result


def select_static(options, hardware, training=None):
    from sim.execution import simulate
    if training is None:
        training = [{t.tid: t.predicted for t in options[0].workload.tasks}]
    # Disjoint training samples; no test-seed knowledge, fixed mapping for every candidate.
    scores = [sum(simulate(c, hardware, d, "A").latency for d in training) / len(training)
              for c in options]
    return options[min(range(len(options)), key=lambda i: (scores[i], i))]
