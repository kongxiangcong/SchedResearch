"""Execute predetermined resource FIFOs under exogenous service pauses."""
import random
from .model import H, C, metrics


def phases(seed, condition):
    if condition == 'quiet':
        return {}
    rng = random.Random(seed ^ 0x11B10C)
    return {r: rng.randrange(4096) for r in ('EXT', 'LOCAL')}


def service(c):
    res = c['res']
    if res == 'BARRIER':
        return 0.0
    if res == 'EXT':
        return 1 + H['ext_setup_cycles'] + c['bytes'] / H['ext_bytes_per_cycle']
    if res == 'LOCAL':
        return 1 + H['local_setup_cycles'] + c['bytes'] / H['local_bytes_per_cycle']
    if res.startswith('VPU'):
        return 1 + c['ops'] / H['vpu_ops_per_cycle_per_core']
    return 1 + H['projection_fill_cycles'] + c['macs'] / H['fp32_macs_per_cycle_per_core']


def completion(start, work, phase):
    if phase is None:
        return start + work
    t = start
    while work > 1e-10:
        pos = (t + phase) % 4096
        if pos < 819:
            t += 819 - pos
        else:
            avail = 4096 - pos
            use = min(avail, work)
            t += use
            work -= use
    return t


def run(graph, seed, condition, detailed=False):
    phase = phases(seed, condition)
    finish, timing, busy = [], [], {}
    for c in graph['commands']:
        ready = max((finish[x] for x in c['deps']), default=0.0)
        work = service(c)
        end = completion(ready, work, phase.get(c['res']))
        finish.append(end)
        if detailed:
            timing.append([ready, ready, end])
        busy[c['res']] = busy.get(c['res'], 0.0) + work
    elapsed = max(finish)
    return dict(seed=seed, condition=condition, phases=phase, elapsed=elapsed,
                timings=timing if detailed else None,
                lower_bounds=dict(port_service_cycles=busy,
                                  no_blackout_resource_bound=max(busy.values()),
                                  ext_payload_bound=metrics(graph)['bytes_by_resource']['EXT'] / H['ext_bytes_per_cycle']))
