"""R3-compatible atomic-resource execution with auditable R4 timing.

No FIFO/backpressure or bounded total history claim. Calendar is an exogenous
absolute-time available-bandwidth model, not measured DRAM or a bank simulator.
"""
from dataclasses import dataclass, asdict
import hashlib
import heapq
import math
import random
from sim.hardware_model import Ports
from sim.metrics import cost, descriptor_size


@dataclass(frozen=True)
class Environment:
    seed: int
    mode: str = 'deterministic'
    amplitude: float = 0.5
    period: float = 256
    busy_fraction: float = 0.5
    busy_rate: float = 0.25

    def factor(self, task):
        if task.kind != 'memory' or self.mode not in ('service', 'combined'):
            return 1.0
        h = hashlib.sha256(f'{self.seed}:{task.tid}'.encode()).digest()
        return 1 + self.amplitude * (2 * random.Random(int.from_bytes(h[:8], 'big')).random() - 1)

    def phase(self):
        return random.Random(self.seed + 937).random() * self.period

    def finish(self, task, start):
        work = task.predicted * self.factor(task)
        if task.kind != 'memory' or self.mode not in ('calendar', 'combined'):
            return start + work, []
        left, time, segments = work, start, []
        phase = self.phase()
        while left > 1e-9:
            p = (time + phase) % self.period
            busy = p < self.busy_fraction * self.period - 1e-10
            rate = self.busy_rate if busy else 1.0
            boundary = self.busy_fraction * self.period if busy else self.period
            available = max(1e-8, boundary - p)
            dt = min(available, left / rate)
            segments.append([time, time + dt, rate])
            time += dt
            left -= dt * rate
        return time, segments


class Prepared:
    def __init__(self, contract, hardware):
        contract.validate(hardware)
        self.contract, self.hardware = contract, hardware
        self.tasks = {t.tid: t for t in contract.workload.tasks}
        self.preds = {x: [] for x in self.tasks}
        self.succs = {x: [] for x in self.tasks}
        for i, e in enumerate(contract.workload.edges):
            self.preds[e.consumer].append(i)
            self.succs[e.producer].append((i, e.consumer))
        self.descriptor_bytes = {x: descriptor_size(t, len(self.preds[x])) for x, t in self.tasks.items()}


def simulate(prepared, env, policy='A', order=None, hardware=None, detailed=False, intervention=None):
    p = prepared
    c, hw, tasks = p.contract, hardware or p.hardware, p.tasks
    assert policy in ('A', 'B', 'H')
    order = tuple(order or c.admission_order)
    if policy in ('A', 'H') and not order:
        raise ValueError('static order required')
    # Order is topological and generated/validated by compiler; only trial
    # permutations proven topological are supplied to the fast search path.
    resources = {r for t in tasks.values() for r in t.resources}
    orders = {r: [x for x in order if r in tasks[x].resources] for r in resources}
    ptr = {r: 0 for r in resources}
    issue, wake = Ports(hw.issue_width, hw.issue_cycle), Ports(hw.wakeup_width, hw.wakeup_cycle)
    delivered, done, admitted, issued = set(), set(), set(), set()
    remaining, ready_at, admitted_at = {}, {}, {}
    occupied, running = {}, set()
    events, trace, notifications, admission_log = [], [], [], []
    index, bytes_used, serial, now = 0, 0, 0, 0.0
    waits = {k: 0.0 for k in ('admission', 'dependency', 'memory_resource', 'engine_resource', 'static_order', 'issue')}
    metrics = {'opportunity_union_cycles': 0.0, 'opportunity_resource_cycles': {r: 0.0 for r in resources},
        'resource_reserved_cycles': {r: 0.0 for r in resources}, 'resource_service_cycles': {r: 0.0 for r in resources},
        'ready_queue_peak': 0, 'wakeup_queue_peak': 0, 'completion_queue_peak': 0,
        'descriptor_bytes_peak': 0, 'window_peak': 0, 'candidate_checks': 0,
        'issue_count': 0, 'wakeup_messages': 0, 'ready_area': 0.0}
    opportunities, intervention_applied = [], False

    def push(time, typ, payload):
        nonlocal serial
        serial += 1
        heapq.heappush(events, (time, typ, serial, payload))

    def head(x):
        if policy == 'B':
            return True
        needed = tasks[x].resources
        if policy == 'H':
            # Minimal resource-aware comparison: keep compute engine order,
            # arbitrate DMA and shared SRAM by readiness. No remapping.
            needed = tuple(r for r in needed if r.endswith(('.mxu', '.vpu')))
        return all(orders[r][ptr[r]] == x for r in needed)

    while len(done) < len(tasks):
        while events and events[0][0] <= now + 1e-9:
            at, typ, seq, payload = heapq.heappop(events)
            if typ == 0:
                x = payload
                running.remove(x); done.add(x); admitted.remove(x)
                bytes_used -= p.descriptor_bytes[x]
                for r in tasks[x].resources:
                    del occupied[r]
                for edge_id, y in p.succs[x]:
                    enqueue = now + hw.completion_latency
                    visible = wake.reserve(enqueue)
                    notifications.append({'edge': edge_id, 'producer': x, 'consumer': y,
                        'completion_time': now, 'enqueue': enqueue, 'delivery': visible,
                        'completion_serial': seq, 'notification_sequence': len(notifications)})
                    push(visible, 1, (edge_id, y))
                    metrics['wakeup_messages'] += 1
            else:
                edge_id, y = payload
                delivered.add(edge_id)
                if y in admitted:
                    remaining[y] -= 1
                    if not remaining[y]:
                        ready_at[y] = now
        while index < len(order):
            x = order[index]
            if len(admitted) >= hw.window or bytes_used + p.descriptor_bytes[x] > hw.byte_window:
                break
            admitted.add(x); admitted_at[x] = now
            bytes_used += p.descriptor_bytes[x]
            remaining[x] = sum(e not in delivered for e in p.preds[x])
            if not remaining[x]:
                ready_at[x] = now
            admission_log.append({'task': x, 'time': now, 'bytes': p.descriptor_bytes[x]})
            index += 1
        metrics['window_peak'] = max(metrics['window_peak'], len(admitted))
        metrics['descriptor_bytes_peak'] = max(metrics['descriptor_bytes_peak'], bytes_used)
        ready = [x for x in admitted if x not in issued and remaining[x] == 0]
        metrics['ready_queue_peak'] = max(metrics['ready_queue_peak'], len(ready))
        ranked = sorted(ready, key=lambda x: (-c.priority[x], x))
        if intervention and not intervention_applied and abs(now - intervention['time']) < 1e-8 and intervention['task'] in ranked:
            ranked.remove(intervention['task']); ranked.insert(0, intervention['task'])
        retry = []
        for x in ranked:
            metrics['candidate_checks'] += 1
            forced = bool(intervention and not intervention_applied and x == intervention['task'] and abs(now - intervention['time']) < 1e-8)
            if (not forced and not head(x)) or any(r in occupied for r in tasks[x].resources):
                continue
            if issue.next() > now + 1e-9:
                retry.append(issue.next()); continue
            issue.reserve(now)
            issued.add(x); running.add(x)
            start = now + hw.dispatch_latency
            finish, segments = env.finish(tasks[x], start)
            if forced:
                intervention_applied = True
            for r in tasks[x].resources:
                occupied[r] = x
                while ptr[r] < len(orders[r]) and orders[r][ptr[r]] in issued:
                    ptr[r] += 1
                metrics['resource_reserved_cycles'][r] += finish - now
                metrics['resource_service_cycles'][r] += finish - start
            trace.append({'task': x, 'dispatch': now, 'start': start, 'finish': finish,
                'sequence': len(trace), 'resources': list(tasks[x].resources),
                'service': finish - start, 'nominal_work': tasks[x].predicted,
                'external_factor': env.factor(tasks[x]), 'calendar_segments': segments,
                'admitted': admitted_at[x], 'ready': ready_at[x], 'forced_escape': forced})
            metrics['issue_count'] += 1
            push(finish, 0, x)
        if len(done) == len(tasks):
            break
        metrics['completion_queue_peak'] = max(metrics['completion_queue_peak'], len(running))
        metrics['wakeup_queue_peak'] = max(metrics['wakeup_queue_peak'], sum(e[1] == 1 for e in events))
        future = ([events[0][0]] if events else []) + retry
        if intervention and not intervention_applied and intervention['time'] > now + 1e-9:
            future.append(intervention['time'])
        if not future:
            raise RuntimeError('deadlock')
        next_time = min(future)
        dt = next_time - now
        ready = [x for x in admitted if x not in issued and remaining[x] == 0]
        metrics['ready_area'] += len(ready) * dt
        alternate = [x for x in ready if not head(x) and all(r not in occupied for r in tasks[x].resources)]
        # The physical opportunity includes a usable issue lane, not merely a
        # ready alternative whose engine is occupied. Count wall-time UNION.
        useful_start = max(now, issue.next())
        if alternate and useful_start < next_time - 1e-9:
            gap = next_time - useful_start
            metrics['opportunity_union_cycles'] += gap
            touched = {r for x in alternate for r in tasks[x].resources}
            for r in touched:
                metrics['opportunity_resource_cycles'][r] += gap
            if detailed:
                opportunities.append({'time': useful_start, 'until': next_time,
                                      'alternatives': sorted(alternate), 'resources': sorted(touched)})
        if detailed:
            for x in tasks:
                if x in issued:
                    continue
                if x not in admitted:
                    key = 'admission'
                elif remaining[x]:
                    key = 'dependency'
                elif any(r in occupied for r in tasks[x].resources):
                    key = 'memory_resource' if any(r in occupied and ('dma' in r or 'sram' in r) for r in tasks[x].resources) else 'engine_resource'
                elif not head(x):
                    key = 'static_order'
                else:
                    key = 'issue'
                waits[key] += dt
        now = next_time
    latency = max(x['finish'] for x in trace)
    metrics['ready_queue_mean'] = metrics.pop('ready_area') / latency
    metrics['resource_utilization'] = {r: v / latency for r, v in metrics['resource_service_cycles'].items()}
    metrics['resource_reserved_utilization'] = {r: v / latency for r, v in metrics['resource_reserved_cycles'].items()}
    metrics['task_wait_cycles_not_wall_stall'] = waits if detailed else None
    metrics['issue_service_utilization'] = len(tasks) * hw.issue_cycle / (hw.issue_width * latency)
    metrics['wakeup_service_utilization'] = metrics['wakeup_messages'] * hw.wakeup_cycle / (hw.wakeup_width * latency)
    pairs = {(a, b) for ids in orders.values() for a, b in zip(ids, ids[1:])}
    metrics['ready_order_pairs'] = len(pairs)
    dependency_ready = {x: 0.0 for x in tasks}
    for event in notifications:
        dependency_ready[event['consumer']] = max(dependency_ready[event['consumer']], event['delivery'])
    metrics['ready_order_inversions'] = sum(dependency_ready[b] < dependency_ready[a] - 1e-9 for a, b in pairs)
    metrics['ready_order_inversion_rate'] = metrics['ready_order_inversions'] / max(1, len(pairs))
    metrics['intervention_applied'] = intervention_applied
    if detailed:
        from dataclasses import replace
        metrics.update(cost(replace(c, admission_order=order, resource_order=orders), hw, 'A' if policy == 'A' else 'B', 1))
        metrics['dependency_ready_times'] = dependency_ready
    return {'latency': latency, 'trace': trace if detailed else [],
        'notifications': notifications if detailed else [], 'admissions': admission_log if detailed else [],
        'opportunities': opportunities, 'metrics': metrics, 'environment': asdict(env),
        'policy': policy, 'hardware': asdict(hw)}
