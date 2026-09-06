"""Nonpreemptive event simulation with atomic resource bundles and explicit wakeups."""
import heapq
import math
from sim.hardware_model import Ports
from sim.metrics import Result, cost, descriptor_size
from sim.scheduler import rank


def simulate(contract, hardware, durations, policy="B"):
    if policy not in {"A", "B", "C"}:
        raise ValueError("unknown scheduler")
    contract.validate(hardware)
    tasks = {t.tid: t for t in contract.workload.tasks}
    if set(durations) != set(tasks) or any(not math.isfinite(x) or x <= 0 for x in durations.values()):
        raise ValueError("service times must be finite, positive, and cover every task")
    if policy == "A" and not contract.resource_order:
        raise ValueError("static execution requires compiled resource order")
    preds = {x: [] for x in tasks}
    succs = {x: [] for x in tasks}
    for i, edge in enumerate(contract.workload.edges):
        preds[edge.consumer].append(i)
        succs[edge.producer].append((i, edge.consumer))
    descriptor_bytes = {x: descriptor_size(t, len(preds[x])) for x, t in tasks.items()}
    if any(size > hardware.byte_window for size in descriptor_bytes.values()):
        raise ValueError("one descriptor exceeds byte admission window")
    domain = {x: hardware.domain(t) for x, t in tasks.items()}
    domains = set(domain.values())
    issue = {d: Ports(hardware.issue_width, hardware.issue_cycle) for d in domains}
    wake = {d: Ports(hardware.wakeup_width, hardware.wakeup_cycle) for d in domains}
    admission = {d: [x for x in contract.admission_order if domain[x] == d] for d in domains}
    pointer = {d: 0 for d in domains}
    byte_used = {d: 0 for d in domains}
    admitted = set()
    done, running, delivered = set(), set(), set()
    remaining = {}
    ready_since = {}
    occupied = {}
    resource_ptr = {r: 0 for r in contract.resource_order}
    events, trace = [], []
    serial = 0
    now = 0.0
    m = {"decision_count": 0, "candidate_checks": 0, "wakeup_messages": 0,
         "cross_domain_wakeups": 0, "ready_queue_peak": 0, "window_peak": 0,
         "completion_queue_peak": 0, "wakeup_queue_peak": 0,
         "descriptor_bytes_peak": 0, "ready_queue_area": 0.0,
         "admission_wait_task_cycles": 0.0, "dependency_wait_task_cycles": 0.0,
         "memory_resource_wait_task_cycles": 0.0, "communication_resource_wait_task_cycles": 0.0,
         "engine_resource_wait_task_cycles": 0.0, "static_order_wait_task_cycles": 0.0,
         "scheduler_issue_wait_task_cycles": 0.0}
    service = {r: 0.0 for t in tasks.values() for r in t.resources}
    reserved = dict(service)

    def push(time, event_type, payload):
        nonlocal serial
        serial += 1
        heapq.heappush(events, (time, event_type, serial, payload))

    def is_head(x):
        return policy != "A" or all(contract.resource_order[r][resource_ptr[r]] == x
                                    for r in tasks[x].resources)

    def admit():
        for d in sorted(domains):
            while pointer[d] < len(admission[d]):
                x = admission[d][pointer[d]]
                if sum(domain[y] == d for y in admitted) >= hardware.window or byte_used[d] + descriptor_bytes[x] > hardware.byte_window:
                    break
                pointer[d] += 1
                admitted.add(x)
                byte_used[d] += descriptor_bytes[x]
                remaining[x] = sum(i not in delivered for i in preds[x])
                if remaining[x] == 0:
                    ready_since[x] = now
        m["window_peak"] = max(m["window_peak"], len(admitted))
        m["descriptor_bytes_peak"] = max(m["descriptor_bytes_peak"], sum(byte_used.values()))

    def ready_set():
        return [x for x in admitted if x not in running and remaining[x] == 0]

    def accumulate(dt):
        ready = ready_set()
        m["ready_queue_peak"] = max(m["ready_queue_peak"], len(ready))
        m["ready_queue_area"] += len(ready) * dt
        for x in tasks:
            if x in done or x in running:
                continue
            if x not in admitted:
                key = "admission_wait_task_cycles"
            elif remaining[x]:
                key = "dependency_wait_task_cycles"
            else:
                blocked = [r for r in tasks[x].resources if r in occupied]
                if any("noc" in r or "link" in r or "egress" in r or "ingress" in r for r in blocked):
                    key = "communication_resource_wait_task_cycles"
                elif any("dma" in r or "sram" in r or "dram" in r for r in blocked):
                    key = "memory_resource_wait_task_cycles"
                elif blocked:
                    key = "engine_resource_wait_task_cycles"
                elif not is_head(x):
                    key = "static_order_wait_task_cycles"
                else:
                    key = "scheduler_issue_wait_task_cycles"
            m[key] += dt

    while len(done) < len(tasks):
        # Drain ALL simultaneous completions and notifications before arbitration.
        while events and events[0][0] <= now + 1e-12:
            _, event_type, _, payload = heapq.heappop(events)
            if event_type == 0:
                x = payload
                running.remove(x); done.add(x); admitted.remove(x)
                byte_used[domain[x]] -= descriptor_bytes[x]
                del remaining[x]
                for r in tasks[x].resources:
                    del occupied[r]
                for edge_id, y in sorted(succs[x]):
                    visibility = wake[domain[y]].reserve(now + hardware.completion_latency)
                    push(visibility, 1, (edge_id, y))
                    m["wakeup_messages"] += 1
                    m["cross_domain_wakeups"] += int(tasks[x].domain != tasks[y].domain)
            else:
                edge_id, y = payload
                delivered.add(edge_id)
                if y in admitted:
                    remaining[y] -= 1
                    if remaining[y] == 0:
                        ready_since[y] = now
        admit()
        m["completion_queue_peak"] = max(m["completion_queue_peak"], sum(x[1] == 0 for x in events))
        m["wakeup_queue_peak"] = max(m["wakeup_queue_peak"], sum(x[1] == 1 for x in events))
        ready = ready_set()
        m["ready_queue_peak"] = max(m["ready_queue_peak"], len(ready))
        pressure = {r: sum(r in tasks[x].resources for x in ready) for r in service}
        ordered = sorted(ready, key=lambda x: (-rank(policy, x, contract.priority,
                         now - ready_since[x], sum(pressure[r] for r in tasks[x].resources)), x))
        retry = []
        for x in ordered:
            m["candidate_checks"] += 1
            if not is_head(x) or any(r in occupied for r in tasks[x].resources):
                continue
            port = issue[domain[x]]
            if port.next() > now + 1e-12:
                retry.append(port.next())
                continue
            port.reserve(now)
            start = now + hardware.dispatch_latency
            finish = start + durations[x]
            running.add(x)
            for r in tasks[x].resources:
                occupied[r] = x
                service[r] += durations[x]
                reserved[r] += durations[x] + hardware.dispatch_latency
                if policy == "A":
                    resource_ptr[r] += 1
            m["decision_count"] += 1
            trace.append({"task": x, "dispatch": now, "start": start, "finish": finish,
                          "sequence": len(trace), "resources": tasks[x].resources,
                          "service": durations[x], "domain": domain[x]})
            push(finish, 0, x)
        m["completion_queue_peak"] = max(m["completion_queue_peak"], len(running))
        if len(done) == len(tasks):
            break
        next_times = ([events[0][0]] if events else []) + retry
        if not next_times:
            raise RuntimeError("deadlock: no completion, wakeup, or issue event can make progress")
        next_time = min(next_times)
        accumulate(next_time - now)
        now = next_time
    latency = max(e["finish"] for e in trace)
    m["ready_queue_mean"] = m.pop("ready_queue_area") / latency
    m["tasks_per_cycle"] = len(tasks) / latency
    m["scheduler_issue_utilization"] = min(1.0, len(tasks) * hardware.issue_cycle / (len(domains) * hardware.issue_width * latency))
    m["scheduling_decisions_per_cycle"] = len(tasks) / latency
    m["resource_utilization"] = {r: service[r] / latency for r in service}
    m["resource_reserved_utilization"] = {r: reserved[r] / latency for r in service}
    m["resource_idle_cycles"] = {r: latency - reserved[r] for r in service}
    cp = {}
    for x in contract.admission_order:
        cp[x] = durations[x] + max((cp[e.producer] for e in contract.workload.edges if e.consumer == x), default=0)
    m["unconstrained_critical_path"] = max(cp.values())
    m["critical_path_dilation"] = latency / max(cp.values())
    m.update(cost(contract, hardware, policy, len(domains)))
    return Result(latency, trace, m)


def verify_trace(contract, result, hardware):
    """Independent safety replay: service, visibility minimum, and resource nonoverlap."""
    by_id = {x["task"]: x for x in result.trace}
    if len(result.trace) != len(contract.workload.tasks) or set(by_id) != {t.tid for t in contract.workload.tasks}:
        raise AssertionError("lost or duplicate task")
    for edge in contract.workload.edges:
        if by_id[edge.consumer]["dispatch"] + 1e-9 < by_id[edge.producer]["finish"] + hardware.completion_latency:
            raise AssertionError("dependency dispatched before data/event became visible")
    for r in {r for t in contract.workload.tasks for r in t.resources}:
        intervals = sorted((x["dispatch"], x["finish"]) for x in result.trace if r in x["resources"])
        if any(b[0] + 1e-9 < a[1] for a, b in zip(intervals, intervals[1:])):
            raise AssertionError("resource overlap")
