from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    tid: str
    kind: str
    resources: tuple[str, ...]
    predicted: float
    domain: str = "cluster0"
    output_bytes: int = 256


@dataclass(frozen=True)
class Edge:
    producer: str
    consumer: str
    kind: str = "data"  # data, completion, WAR, WAW, reduction


@dataclass(frozen=True)
class Workload:
    name: str
    tasks: tuple[Task, ...]
    edges: tuple[Edge, ...]
    description: str


def topology(workload):
    ids = [t.tid for t in workload.tasks]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("tasks must be nonempty and identities unique")
    succ = {x: [] for x in ids}
    remaining = {x: 0 for x in ids}
    pairs = set()
    for e in workload.edges:
        if e.producer not in succ or e.consumer not in succ:
            raise ValueError("unknown dependency endpoint")
        if e.kind not in {"data", "completion", "WAR", "WAW", "reduction"}:
            raise ValueError("unknown dependency type")
        if (e.producer, e.consumer) in pairs:
            raise ValueError("duplicate dependency pair")
        pairs.add((e.producer, e.consumer))
        remaining[e.consumer] += 1
        succ[e.producer].append(e.consumer)
    ready = sorted(x for x in ids if remaining[x] == 0)
    order = []
    while ready:
        x = ready.pop(0)
        order.append(x)
        for y in sorted(succ[x]):
            remaining[y] -= 1
            if remaining[y] == 0:
                ready.append(y)
        ready.sort()
    if len(order) != len(ids):
        raise ValueError("dependency cycle")
    return order
