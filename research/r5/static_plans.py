"""Frozen bounded compiler search; no test data or runtime samples here."""
import heapq
from r5.model import Plan, build


STRATEGIES=('source','critical','breadth','core_major','dma_first','compute_first')
COLORS=(0,1,3)
SPACINGS=(0,64,1024)


def topological(graph, strategy, hw):
    commands={c.cid:c for c in graph.commands}
    index={c.cid:i for i,c in enumerate(graph.commands)}
    succ={x:[] for x in commands}
    remaining={x:len(c.deps) for x,c in commands.items()}
    depth={}
    for x,c in commands.items():
        for d in c.deps:succ[d].append(x)
        depth[x]=max((depth[d]+1 for d in c.deps),default=0)
    critical={}
    for c in reversed(graph.commands):
        service=(c.cycles if c.kind=='compute' else sum(s.size for s in c.spans)/(hw.external_bw if c.kind=='dma' else hw.sram_bw))
        critical[c.cid]=service+max((critical[y] for y in succ[c.cid]),default=0)
    def key(x):
        c=commands[x]
        if strategy=='source':v=(index[x],)
        elif strategy=='critical':v=(-critical[x],)
        elif strategy=='breadth':v=(depth[x],index[x])
        elif strategy=='core_major':v=(c.core,depth[x])
        elif strategy=='dma_first':v=(c.kind!='dma',depth[x],-critical[x])
        elif strategy=='compute_first':v=(c.kind!='compute',-critical[x])
        else:raise ValueError(strategy)
        return v+(index[x],x)
    heap=[key(x) for x,n in remaining.items() if not n];heapq.heapify(heap)
    order=[]
    while heap:
        x=heapq.heappop(heap)[-1];order.append(x)
        for y in succ[x]:
            remaining[y]-=1
            if not remaining[y]:heapq.heappush(heap,key(y))
    assert len(order)==len(commands)
    return tuple(order)


def candidates(workload,hw):
    plans=[];seen=set()
    for color in COLORS:
        graph=build(workload,color,hw)
        for strategy in STRATEGIES:
            order=topological(graph,strategy,hw)
            # Global priority affects shared command issue arbitration, even
            # if per-engine queues coincide, so retain that tie-breaking order.
            for spacing in SPACINGS:
                signature=(order,color,spacing)
                if signature in seen:continue
                seen.add(signature)
                plans.append(Plan(order,color,spacing,f'{strategy}-c{color}-p{spacing}'))
    return plans


def neighbors(graph,plan):
    queues={}
    commands={c.cid:c for c in graph.commands}
    for x in plan.order:queues.setdefault(commands[x].engine,[]).append(x)
    index={x:i for i,x in enumerate(plan.order)}
    for engine,queue in sorted(queues.items()):
        for a,b in zip(queue,queue[1:]):
            order=list(plan.order);ia,ib=index[a],index[b]
            order[ia],order[ib]=order[ib],order[ia]
            seen=set();legal=True
            for x in order:
                if not set(commands[x].deps)<=seen:
                    legal=False;break
                seen.add(x)
            if legal:yield tuple(order)
