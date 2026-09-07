"""Independent request/command trace checker for the declared R5 model.

Does not import the event loop or its arbitration helpers. This is conservation,
timing, queue-capacity, visibility and address-safety evidence, not calibration.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import math
import random


def close(a, b, label, eps=1e-7):
    assert abs(a-b) <= eps*max(1, abs(a), abs(b)), (label, a, b)


def occupancy(intervals, capacity, label):
    events = [(a, 1) for a, b in intervals] + [(b, -1) for a, b in intervals]
    current = peak = 0
    for time, delta in sorted(events):
        current += delta
        assert 0 <= current <= capacity, (label, time, current, capacity)
        peak = max(peak, current)
    assert current == 0
    return peak


def disjoint(intervals, label):
    rows = sorted(intervals)
    for a, b in zip(rows, rows[1:]):
        assert a[1] <= b[0] + 1e-7, (label, a, b)


def calendar_available(start, end, environment):
    """Integrate service availability using closed-form periodic busy overlap."""
    period = environment['period']
    busy = period * environment['duty']
    phase = random.Random(environment['seed'] + 31977).random() * period

    def busy_integral(t):
        shifted = t + phase
        periods = math.floor(shifted / period)
        residue = shifted - periods*period
        return periods*busy + min(residue, busy)

    return (end-start) - (busy_integral(end)-busy_integral(start))


def audit(graph, result):
    commands = {c.cid: c for c in graph.commands}
    trace = result['commands']
    byid = {r['task']: r for r in trace}
    assert len(trace) == len(commands) and set(byid) == set(commands), 'command conservation'
    hw, env = result['hardware'], result['environment']
    order = result['plan']['order']
    assert len(order) == len(commands) and set(order) == set(commands)
    metrics = result['metrics']
    requests = result['requests']
    reqid = {r['rid']: r for r in requests}
    assert len(reqid) == len(requests), 'duplicate request'
    expected = {}
    command_requests = defaultdict(list)
    for c in graph.commands:
        index = 0
        for s in c.spans:
            for offset in range(0, s.size, hw['granule']):
                expected[f'{c.cid}:{index}'] = (c.cid, index, s.address+offset, min(hw['granule'], s.size-offset))
                index += 1
    assert set(reqid) == set(expected), ('request conservation', set(reqid)-set(expected), set(expected)-set(reqid))
    for rid, r in reqid.items():
        cid, index, address, size = expected[rid]
        assert (r['task'], r['index'], r['address'], r['bytes']) == (cid, index, address, size)
        c, t = commands[cid], byid[cid]
        assert r['origin'] == c.kind
        assert r['issued'] >= t['start']-1e-7
        assert r['visible'] <= t['finish']+1e-7
        assert r['bank'] == address//hw['granule'] % hw['banks']
        assert r['bank_start'] >= r['bank_arrival']-1e-7
        close(r['bank_end'], r['visible'], 'bank visibility')
        bank_work = size/(hw['sram_bw']/hw['banks'])
        bank_bg = env['mode'] in ('bank_background', 'combined') and r['bank'] == env['seed'] % hw['banks']
        if bank_bg:
            close(calendar_available(r['bank_start'], r['bank_end'], env), bank_work, 'bank service integral')
        else:
            close(r['bank_end']-r['bank_start'], bank_work, 'bank service')
        if c.kind == 'dma':
            factor = 1
            if env['mode'] in ('latency', 'combined'):
                digest = hashlib.blake2b(f"{env['seed']}:{cid}:{index}".encode(), digest_size=8).digest()
                u = int.from_bytes(digest, 'big') / (2**64-1)
                factor += env['latency_amplitude']*(2*u-1)
            close(r['external_latency'], hw['external_latency']*factor, 'raw external latency')
            close(r['mature'], r['issued']+r['external_latency'], 'mature request')
            assert r['external_start'] >= r['mature']-1e-7
            close(r['return_reserved'], r['external_start'], 'return slot reservation')
            work = size/hw['external_bw']
            if env['mode'] in ('bus_background', 'combined'):
                close(calendar_available(r['external_start'], r['external_end'], env), work, 'external service integral')
            else:
                close(r['external_end']-r['external_start'], work, 'external service')
            assert r['fabric_start'] >= r['external_end']-1e-7
            close(r['fabric_end']-r['fabric_start'], hw['fabric_latency']+size/hw['fabric_bw'], 'fabric service')
            close(r['bank_arrival'], r['fabric_end'], 'DMA bank arrival')
            close(r['credit_release'], r['visible'], 'DMA credit release')
        else:
            close(r['bank_arrival'], r['issued'], 'local bank arrival')
        command_requests[cid].append(r)
    ordered = sorted(trace, key=lambda r:r['sequence'])
    assert [r['sequence'] for r in ordered] == list(range(len(trace)))
    for a, b in zip(ordered, ordered[1:]):
        assert b['dispatch'] >= a['dispatch']+hw['issue_cycle']-1e-7, 'command issue capacity'
    engine_intervals = defaultdict(list)
    for cid, c in commands.items():
        t = byid[cid]
        assert (t['engine'], t['core'], t['kind']) == (c.engine, c.core, c.kind)
        close(t['start'], t['dispatch']+hw['dispatch']+result['extra_dispatch'], 'command dispatch latency')
        close(t['visible'], t['finish']+hw['notification'], 'completion visibility')
        for dep in c.deps:
            assert t['dispatch'] >= byid[dep]['visible']-1e-7, ('dependency', dep, cid)
        if c.kind == 'compute':
            close(t['finish']-t['start'], c.cycles, 'deterministic compute')
        else:
            close(t['finish'], max(r['visible'] for r in command_requests[cid]), 'memory command finish')
            if c.kind != 'dma':
                occupancy([(r['issued'],r['visible']) for r in command_requests[cid]], hw['local_outstanding'], f'local credits {cid}')
        engine_intervals[c.engine].append((t['dispatch'], t['finish']))
    for engine, intervals in engine_intervals.items():
        kind = next(c.kind for c in graph.commands if c.engine == engine)
        occupancy(intervals, hw['dma_commands'] if kind == 'dma' else 1, f'engine {engine}')
    if result['policy'] == 'S':
        for engine in engine_intervals:
            expected_order = [x for x in order if commands[x].engine == engine]
            actual_order = [r['task'] for r in ordered if r['engine'] == engine]
            assert expected_order == actual_order, ('static resource order', engine)
    dma = [r for r in requests if r['origin'] == 'dma']
    dma_issue = sorted(r['issued'] for r in dma)
    assert all(b >= a+hw['request_issue']-1e-7 for a,b in zip(dma_issue,dma_issue[1:])), 'DMA request issue capacity'
    peak_o = occupancy([(r['issued'],r['visible']) for r in dma], hw['outstanding'], 'DMA outstanding')
    peak_r = occupancy([(r['return_reserved'],r['visible']) for r in dma], hw['return_slots'], 'return slots')
    disjoint([(r['external_start'],r['external_end']) for r in dma], 'external bus')
    disjoint([(r['fabric_start'],r['fabric_end']) for r in dma], 'fabric')
    for bank in range(hw['banks']):
        disjoint([(r['bank_start'],r['bank_end']) for r in requests if r['bank']==bank], f'bank {bank}')
    injected = sorted(requests,key=lambda r:r['bank_start'])
    for a,b in zip(injected,injected[1:]):
        assert b['bank_start'] >= a['bank_start']+a['bytes']/hw['sram_bw']-1e-7, 'aggregate SRAM injection bandwidth'
    # Conservative command-span hazard check: overwrite starts only after every
    # overlapping reader/writer command completes. This matches the compiler's
    # declared whole-feed RF transfer lifetime, not a more permissive byte proof.
    memory_commands = [c for c in graph.commands if c.spans]
    predecessors = {}
    for c in graph.commands:
        predecessors[c.cid] = set(c.deps)
        for dep in c.deps:
            predecessors[c.cid].update(predecessors[dep])
    for i,a in enumerate(memory_commands):
        for b in memory_commands[i+1:]:
            if a.kind == b.kind == 'read':
                continue
            overlap = any(max(x.address,y.address)<min(x.address+x.size,y.address+y.size) for x in a.spans for y in b.spans)
            if overlap:
                assert a.cid in predecessors[b.cid] or b.cid in predecessors[a.cid], ('SRAM lifetime depends on unproven execution order',a.cid,b.cid)
                ta,tb = byid[a.cid],byid[b.cid]
                assert ta['finish']<=tb['start']+1e-7 or tb['finish']<=ta['start']+1e-7, ('overlapping SRAM owners',a.cid,b.cid)
    # A reported order-wait interval is an opportunity existence indicator,
    # not recoverable critical path. Even existence must respect pacing.
    waits = result.get('order_wait',[])
    disjoint([(r['start'],r['end']) for r in waits],'order-wait time union')
    for wait in waits:
        assert result['policy']=='S' and wait['end']>wait['start'] and wait['alternatives']
        at = wait['start']
        for cid in wait['alternatives']:
            c,t = commands[cid],byid[cid]
            assert t['dispatch']>at+1e-7, ('already issued alternative',cid)
            assert all(byid[x]['visible']<=at+1e-7 for x in c.deps), ('not ready alternative',cid)
            occupied = sum(r['dispatch']<=at+1e-7 and r['finish']>at+1e-7 for r in trace if r['engine']==c.engine)
            assert occupied < (hw['dma_commands'] if c.kind=='dma' else 1), ('occupied alternative engine',cid)
            if c.kind=='dma':
                before = [r['dispatch'] for r in trace if r['kind']=='dma' and r['dispatch']<=at+1e-7]
                if before:
                    assert at>=max(before)+result['plan']['dma_spacing']-1e-7, ('alternative violates DMA pacing',cid,at)
    close(metrics['task_order_blocked_union'],sum(r['end']-r['start'] for r in waits),'order-wait union')
    for key,origin in [('external_bytes','dma'),('local_read_bytes','read'),('local_write_bytes','write')]:
        assert metrics[key] == sum(r['bytes'] for r in requests if r['origin']==origin), key
    assert metrics['fabric_bytes'] == metrics['external_bytes']
    assert metrics['request_count'] == len(requests)
    assert metrics['dma_outstanding_peak'] == peak_o
    assert metrics['return_slots_peak'] == peak_r
    close(metrics['external_service_cycles'],sum(r['external_end']-r['external_start'] for r in dma),'external occupancy')
    close(metrics['fabric_service_cycles'],sum(r['fabric_end']-r['fabric_start'] for r in dma),'fabric occupancy')
    for bank in range(hw['banks']):
        close(metrics['bank_service_cycles'][bank],sum(r['bank_end']-r['bank_start'] for r in requests if r['bank']==bank),'bank occupancy')
    assert metrics['issue_count'] == len(commands)
    assert metrics['notification_count'] == sum(len(c.deps) for c in graph.commands)
    close(result['latency'],max(r['visible'] for r in trace),'end-to-end latency')
    deliveries = {r['task']:r['time'] for r in result['deliveries']}
    assert len(result['deliveries']) == len(commands) and set(deliveries)==set(commands)
    for cid,time in deliveries.items():
        close(time,byid[cid]['visible'],'delivery log')
    return {'status':'PASS','commands':len(commands),'requests':len(requests),
            'external_bytes':metrics['external_bytes'],'peak_outstanding':peak_o,
            'peak_return_slots':peak_r,'scope':'independent conservation/timing/capacity/visibility/address replay; no real-device calibration'}
