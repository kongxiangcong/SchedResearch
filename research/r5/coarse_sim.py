"""Matched full-width DAG with command-atomic pooled memory service.

This is a fidelity contrast, NOT an identical/calibrated resource model.
Preserves commands, spans/bytes, MACs, engine slots, policy order and pacing.
Loses per-burst RTT/issue, request credits, return FIFO, and spatial bank rules.
One DMA command pays one RTT, then external, fabric, pooled-SRAM service.
"""
from collections import deque
from dataclasses import asdict
import heapq
from r5.resource_sim import Environment


def _pooled_sram_finish(now, work, hw, env):
    """Flatten one interrupted bank into 1/banks aggregate capacity loss.

    Unlike Environment.finish(..., bank_count=hw.banks), this intentionally
    discards the target bank's address identity while retaining its phase/duty.
    """
    if env.mode not in ('bank_background', 'combined'):
        return now + work
    left = work
    while left > 1e-8:
        phase = (now + env.phase()) % env.period
        boundary = env.period * env.duty
        blocked = phase < boundary - 1e-8
        rate = 1 - 1 / hw.banks if blocked else 1
        interval = max(1e-8, (boundary if blocked else env.period) - phase)
        elapsed = interval if rate == 0 else min(interval, left / rate)
        now += elapsed
        left -= elapsed * rate
    return now


def coarse_simulate(graph, hw, plan, env=Environment(), policy='S', extra=0, detailed=False):
    """Same command-policy API as resource_sim.simulate, coarser services.

    external_latency is paid once/command using env.latency(cid,0,...), not
    once/request. Environment's time background is shared; request-level random
    samples cannot be identical after requests are collapsed. Bank background
    preserves aggregate interruption, discards target-bank routing. No finite
    hw.outstanding/return_slots/local_outstanding or hw.request_issue is modeled.
    """
    assert policy in ('S', 'B')
    graph.validate(hw)
    cmds = {c.cid: c for c in graph.commands}
    assert set(plan.order) == set(cmds) and len(plan.order) == len(cmds)
    rank = {x: i for i, x in enumerate(plan.order)}
    successors = {x: [] for x in cmds}
    remaining = {c.cid: len(c.deps) for c in graph.commands}
    for c in graph.commands:
        for dep in c.deps: successors[dep].append(c.cid)
    queues = {}
    for x in plan.order: queues.setdefault(cmds[x].engine, []).append(x)
    pointers = {e: 0 for e in queues}; engines = {e: set() for e in queues}
    ready = {x for x in cmds if not remaining[x]}
    issued = set(); visible = set(); trace = {}; deliveries = []; order_wait = []
    pending = {r: deque() for r in ('external', 'fabric', 'sram')}
    busy = {r: False for r in pending}; events = []; serial = 0; now = 0.
    issue_next = 0.; dma_next = 0.
    m = {'external_bytes': 0, 'local_read_bytes': 0, 'local_write_bytes': 0,
         'fabric_bytes': 0, 'external_service_cycles': 0., 'fabric_service_cycles': 0.,
         'sram_service_cycles': 0., 'task_order_blocked_union': 0., 'ready_peak': 0,
         'max_live_commands': 0, 'issue_count': 0, 'notification_count': 0,
         'command_scans': 0, 'pooled_queue_peak': 0}

    def push(time, kind, x):
        nonlocal serial
        serial += 1; heapq.heappush(events, (time, serial, kind, x))

    def finish(x):
        trace[x]['finish'] = now; engines[cmds[x].engine].remove(x)
        push(now + hw.notification, 'visible', x)

    while len(visible) < len(cmds):
        while events and events[0][0] <= now + 1e-8:
            _, _, kind, x = heapq.heappop(events); c = cmds[x]
            if kind == 'activate':
                size = sum(s.size for s in c.spans)
                if c.kind == 'compute': push(now + c.cycles, 'compute_done', x)
                elif c.kind == 'dma':
                    m['external_bytes'] += size; m['fabric_bytes'] += size
                    push(now + env.latency(x, 0, hw.external_latency), 'mature', x)
                else:
                    m['local_' + ('read' if c.kind == 'read' else 'write') + '_bytes'] += size
                    pending['sram'].append(x)
            elif kind == 'mature': pending['external'].append(x)
            elif kind == 'compute_done': finish(x)
            elif kind == 'visible':
                visible.add(x); trace[x]['visible'] = now
                deliveries.append({'task': x, 'time': now})
                for y in successors[x]:
                    remaining[y] -= 1; m['notification_count'] += 1
                    if not remaining[y]: ready.add(y)
            else:
                resource = kind.removesuffix('_done'); busy[resource] = False
                if resource == 'external': pending['fabric'].append(x)
                elif resource == 'fabric': pending['sram'].append(x)
                elif resource == 'sram': finish(x)
                else: raise AssertionError(kind)
        if len(visible) == len(cmds): break
        if now >= issue_next - 1e-8:
            for x in sorted(ready, key=rank.get):
                c = cmds[x]; m['command_scans'] += 1
                if policy == 'S' and queues[c.engine][pointers[c.engine]] != x: continue
                if len(engines[c.engine]) >= (hw.dma_commands if c.kind == 'dma' else 1): continue
                if c.kind == 'dma' and now < dma_next - 1e-8: continue
                issued.add(x); ready.remove(x); engines[c.engine].add(x)
                while pointers[c.engine] < len(queues[c.engine]) and queues[c.engine][pointers[c.engine]] in issued:
                    pointers[c.engine] += 1
                trace[x] = {'task': x, 'kind': c.kind, 'engine': c.engine, 'core': c.core,
                            'dispatch': now, 'start': now + hw.dispatch + extra, 'sequence': len(trace)}
                push(now + hw.dispatch + extra, 'activate', x); m['issue_count'] += 1
                issue_next = now + hw.issue_cycle
                if c.kind == 'dma': dma_next = now + plan.dma_spacing
                if hw.issue_cycle: break
        for resource in pending:
            if busy[resource] or not pending[resource]: continue
            x = pending[resource].popleft(); busy[resource] = True
            size = sum(s.size for s in cmds[x].spans)
            if resource == 'external': end = env.finish(now, size / hw.external_bw, 'external')
            elif resource == 'fabric': end = now + hw.fabric_latency + size / hw.fabric_bw
            else: end = _pooled_sram_finish(now, size / hw.sram_bw, hw, env)
            trace[x][resource + '_start'] = now; trace[x][resource + '_end'] = end
            m[resource + '_service_cycles'] += end - now
            push(end, resource + '_done', x)
        m['ready_peak'] = max(m['ready_peak'], len(ready))
        m['max_live_commands'] = max(m['max_live_commands'], sum(map(len, engines.values())))
        m['pooled_queue_peak'] = max(m['pooled_queue_peak'], sum(map(len, pending.values())))
        future = [events[0][0]] if events else []
        if ready and issue_next > now + 1e-8: future.append(issue_next)
        if any(cmds[x].kind == 'dma' for x in ready) and dma_next > now + 1e-8: future.append(dma_next)
        if not future: raise RuntimeError(f'coarse deadlock {graph.name}: {ready}')
        nxt = min(future); alternatives = []
        if policy == 'S' and issue_next <= now + 1e-8:
            for x in ready:
                c = cmds[x]; cap = hw.dma_commands if c.kind == 'dma' else 1
                if len(engines[c.engine]) < cap and queues[c.engine][pointers[c.engine]] != x:
                    if c.kind != 'dma' or dma_next <= now + 1e-8: alternatives.append(x)
        if alternatives:
            m['task_order_blocked_union'] += nxt - now
            if detailed: order_wait.append({'start': now, 'end': nxt, 'alternatives': sorted(alternatives)})
        now = nxt
    latency = max(t['visible'] for t in trace.values())
    for resource in pending: m[resource + '_occupancy'] = m[resource + '_service_cycles'] / latency
    m['external_bus_occupancy'] = m['external_occupancy']
    m['external_payload_bw'] = m['external_bytes'] / latency
    m['compute_busy'] = {e: sum(c.cycles for c in graph.commands if c.engine == e and c.kind == 'compute') / latency for e in queues if e.startswith(('mxu', 'vpu'))}
    m['scheduler_state_scope'] = 'full graph history; atomic resource commands; no hardware size claim'
    return {'latency': latency, 'metrics': m, 'commands': list(trace.values()) if detailed else [],
            'requests': [], 'deliveries': deliveries if detailed else [], 'order_wait': order_wait,
            'environment': asdict(env), 'hardware': asdict(hw), 'plan': asdict(plan),
            'policy': policy, 'extra_dispatch': extra, 'backend': 'command_atomic_pooled',
            'modeling_losses': ['no perrequest outstanding/return credits or request issue interval',
              'one RTT per DMA command, not per burst; collapsed latency samples',
              'pooled SRAM: no address-bank routing/arbitration; background spatially averaged',
              'whole-command FIFO external/fabric/SRAM occupancy, no beat interleaving']}


if __name__ == '__main__':
    from dataclasses import replace
    from r5.model import Graph, Hardware, Plan, Command, Span, build
    hw = Hardware(granule=16, external_bw=4, external_latency=3, fabric_bw=8,
                  fabric_latency=2, sram_bw=16, dispatch=0, notification=0, issue_cycle=0)
    g = Graph('analytic', (Command('d', 'dma', 0, 'dma', (), (Span(0, 16, 'test'),)),
                           Command('c', 'mxu0', 0, 'compute', ('d',), cycles=9)), {'rf_bytes_per_core': 0})
    assert coarse_simulate(g, hw, Plan(('d', 'c')))['latency'] == 21
    for name in ('qwen_projection', 'flux_projection', 'qwen_gdn_state'):
        hw = Hardware(); g = build(name, hw=hw); p = Plan(tuple(c.cid for c in g.commands))
        for policy in ('S', 'B'):
            r = coarse_simulate(g, hw, p, Environment(4, 'combined'), policy, detailed=True)
            assert len(r['commands']) == len(g.commands)
            assert r['metrics']['external_bytes'] == sum(s.size for c in g.commands if c.kind == 'dma' for s in c.spans)
    print('coarse analytic timing + 6 source-graph execution/byte-conservation cases passed')
