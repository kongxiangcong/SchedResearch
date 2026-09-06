"""Conservative same-core VPU chain fusion with explicit live-out preservation."""
from dataclasses import replace
from r4.graph import Node


def fuse_vpu(case):
    nodes = list(case.nodes)
    fused_pairs = []
    values = case.evaluate()
    scratch = dict(case.metadata.get('internal_scratch', {}))
    while True:
        readers = {}
        for n in nodes:
            for x in n.reads:
                readers.setdefault(x, set()).add(n.name)
        changed = False
        for i, a in enumerate(nodes):
            if a.engine != 'VPU':
                continue
            consumers = {y for x in a.writes for y in readers.get(x, set())}
            if len(consumers) != 1:
                continue
            j = next(j for j, n in enumerate(nodes) if n.name in consumers)
            b = nodes[j]
            if b.engine != 'VPU' or b.core != a.core:
                continue
            # Avoid moving a later producer earlier; fusion is inserted at b.
            reads = tuple(dict.fromkeys(a.reads + tuple(x for x in b.reads if x not in a.writes)))
            preserved = tuple(x for x in a.writes if x in case.outputs)
            writes = preserved + b.writes

            def execute(*args, aa=a, bb=b, rr=reads, pp=preserved):
                values = dict(zip(rr, args))
                av = aa.run(*(values[x] for x in aa.reads))
                if len(aa.writes) == 1:
                    av = (av,)
                values.update(zip(aa.writes, av))
                bv = bb.run(*(values[x] for x in bb.reads))
                if len(bb.writes) == 1:
                    bv = (bv,)
                results = tuple(values[x] for x in pp) + tuple(bv)
                return results[0] if len(results) == 1 else results

            fused = Node('fused.' + a.name + '.' + b.name, 'VPU', reads, writes, execute,
                         a.macs+b.macs, a.vector_ops+b.vector_ops,
                         a.source+' ; '+b.source, 'same-core single-consumer VPU chain; '+a.fusion+'; '+b.fusion, a.core)
            removed = tuple(x for x in a.writes if x not in preserved)
            internal = sum(values[x].size * case.metadata.get('storage_bytes', {}).get(x, 2) for x in removed)
            scratch[fused.name] = {'bytes': internal + sum(scratch.get(n.name, {}).get('bytes', 0) for n in (a,b)),
                'traffic_bytes': 2*internal + sum(scratch.get(n.name, {}).get('traffic_bytes', 0) for n in (a,b)),
                'scope': 'conservative materialized internal temporary accounting'}
            nodes[j] = fused
            del nodes[i]
            fused_pairs.append([a.name, b.name])
            changed = True
            break
        if not changed:
            break
    metadata = dict(case.metadata)
    metadata['internal_scratch'] = {n.name: scratch[n.name] for n in nodes if n.name in scratch}
    metadata['compiler_vpu_fusion'] = {'before_nodes': len(case.nodes), 'after_nodes': len(nodes),
        'pairs': fused_pairs, 'scope': 'single-consumer same-core VPU chains; engine-internal intermediate; no cross-engine superkernel assumption'}
    return replace(case, nodes=nodes, metadata=metadata)
