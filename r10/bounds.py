"""Trace-independent necessary conditions, proof in bound_proof.md."""
import math
from r10.model import resource_lower_bound, service_finish

def blackouts(t, env):
    p, d, phase = env['period'], env['duty'], env['phase']
    if not d:
        return []
    return [max(0., min(t, phase+i*p+d*p)-max(0., phase+i*p))
            for i in range(math.floor((-phase-d*p)/p), math.ceil((t-phase)/p)+1)]

def lower_bounds(graph, hw, env):
    E, D = hw['external_bytes_per_cycle'], hw['cluster_dma_bytes_per_cycle']
    lat, vis = hw['request_latency_cycles'], hw['visibility_cycles']
    q = min(graph['config']['outstanding'], hw['dma_outstanding_per_cluster'], hw['transport_slots_per_cluster'])
    credit, blackout = [], []
    for cluster in range(hw['clusters']):
        ns = [n for n in graph['nodes'] if 'packets' in n and n['cluster']==cluster]
        ps = [p for n in ns for p in n['packets']]
        rp = [p for n in ns if n['kind']=='dma_read' for p in n['packets']]
        credit.append(sum(lat+vis+p['external_bytes']/E+p['local_bytes']/D for p in ps)/q)
        R = sum(p['local_bytes'] for p in rp)
        B = sum(sorted((p['local_bytes'] for p in rp), reverse=True)[:q])
        def capacity(t):
            return D*t-sum(max(0.,D*l-B) for l in blackouts(t,env))
        lo, hi = 0., R/D/(1-env['duty'])+env['period']
        for _ in range(65):
            mid=(lo+hi)/2
            if capacity(mid)<R: lo=mid
            else: hi=mid
        blackout.append(lo)
    done, remaining = {}, list(graph['nodes'])
    while remaining:
        ready=[n for n in remaining if all(x in done for x in n['deps'])]
        if not ready: raise ValueError('cyclic graph')
        for n in ready:
            s=max((done[x] for x in n['deps']),default=0.)
            if 'packets' not in n:
                done[n['id']]=s+n['duration']
            else:
                ps=n['packets']; a=s+lat
                emin=min(p['external_bytes']/E for p in ps)
                lmin=min(p['local_bytes']/D for p in ps)
                et=sum(p['external_bytes']/E for p in ps)
                lt=sum(p['local_bytes']/D for p in ps)
                if n['kind']=='dma_read':
                    v=max(service_finish(a,et,env), service_finish(a,emin,env)+lt,
                          max(service_finish(a,p['external_bytes']/E,env)+p['local_bytes']/D for p in ps))
                else:
                    v=max(service_finish(a+lmin,et,env),a+lt,
                          max(service_finish(a+p['local_bytes']/D,p['external_bytes']/E,env) for p in ps))
                done[n['id']]=v+vis
            remaining.remove(n)
    parts={'aggregate':resource_lower_bound(graph,hw,env),'credit':max(credit),
           'blackout':max(blackout),'dependency':max(done[x] for x in graph['output_nodes'])}
    return parts | {'tight':max(parts.values())}
