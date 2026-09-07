"""Closed-loop request/bank/credit model. This is NOT calibrated DRAM/NoC.

DMA credit is returned only after destination SRAM visibility. Finite return
slots backpressure the external data bus. Local feed requests share the banks;
MXU uses ping-pong RF and never locks SRAM for its entire compute phase.
"""
from dataclasses import dataclass, asdict
from collections import deque
import hashlib
import heapq
import math
import random
from r5.model import bursts


@dataclass(frozen=True)
class Environment:
    seed: int = 0
    mode: str = 'none'
    period: float = 512
    duty: float = .25
    latency_amplitude: float = .5

    def phase(self):
        return random.Random(self.seed+31977).random()*self.period

    def latency(self,cid,index,base):
        if self.mode not in ('latency','combined'):
            return base
        data=hashlib.blake2b(f'{self.seed}:{cid}:{index}'.encode(),digest_size=8).digest()
        u=int.from_bytes(data,'big')/(2**64-1)
        return base*(1+self.latency_amplitude*(2*u-1))

    def finish(self,start,work,resource,bank=0,bank_count=8):
        apply=(resource=='external' and self.mode in ('bus_background','combined')) or (resource=='bank' and self.mode in ('bank_background','combined') and bank==self.seed%bank_count)
        if not apply:
            return start+work
        now,left=start,work
        phase=self.phase()
        while left>1e-8:
            p=(now+phase)%self.period
            boundary=self.period*self.duty
            if p<boundary-1e-8:
                now+=boundary-p
            else:
                dt=min(left,max(1e-8,self.period-p))
                now+=dt;left-=dt
        return now


def simulate(graph,hw,plan,env=Environment(),policy='S',extra=0,detailed=False):
    assert policy in ('S','B')
    graph.validate(hw)
    cmds={c.cid:c for c in graph.commands}
    assert set(plan.order)==set(cmds) and len(plan.order)==len(cmds)
    rank={x:i for i,x in enumerate(plan.order)}
    succ={x:[] for x in cmds};remain={c.cid:len(c.deps) for c in graph.commands}
    for c in graph.commands:
        for x in c.deps:succ[x].append(c.cid)
    queues={}
    for x in plan.order:queues.setdefault(cmds[x].engine,[]).append(x)
    ptr={e:0 for e in queues};engines={e:set() for e in queues}
    issued=set();visible=set();ready={x for x in cmds if not remain[x]}
    traces={};requests={};req_trace=[];events=[];serial=0;now=0.
    issue_next=0.;dma_issue_next=0.;dma_command_next=0.
    active_dma=[];active_local=[];dma_rr=0;local_rr=0
    streams={};cursor={};inflight={};complete={}
    dma_used=0;return_used=0;external_busy=False;fabric_busy=False
    mature=[];fabric_queue=deque();banks=[deque() for _ in range(hw.banks)]
    bank_busy=[False]*hw.banks;bank_rr=0;sram_inject_next=0.
    scheduling=True
    m={'dma_outstanding_peak':0,'return_slots_peak':0,'mature_wait_peak':0,'bank_queue_peak':0,
       'external_bytes':0,'local_read_bytes':0,'local_write_bytes':0,'fabric_bytes':0,
       'external_service_cycles':0.,'fabric_service_cycles':0.,'bank_service_cycles':[0.]*hw.banks,
       'outstanding_blocked_union':0.,'return_backpressure_union':0.,'bank_blocked_union':0.,
       'task_order_blocked_union':0.,'ready_peak':0,'issue_count':0,'notification_count':0,
       'command_scans':0,'max_live_commands':0}
    deliveries=[];order_wait=[]

    def push(t,kind,data):
        nonlocal serial
        serial+=1;heapq.heappush(events,(t,serial,kind,data))

    def done_command(x):
        nonlocal scheduling
        traces[x]['finish']=now
        engines[cmds[x].engine].remove(x)
        if x in active_dma:active_dma.remove(x)
        if x in active_local:active_local.remove(x)
        push(now+hw.notification,'visible',x)
        scheduling=True

    def bank_enqueue(r):
        r['bank_arrival']=now
        bank=(r['address']//hw.granule)%hw.banks
        r['bank']=bank;banks[bank].append(r)

    def request_done(r):
        nonlocal dma_used,return_used
        x=r['task'];inflight[x]-=1;complete[x]+=1
        r['visible']=now
        if r['origin']=='dma':
            dma_used-=1;return_used-=1;r['credit_release']=now
        if detailed:req_trace.append(r)
        if complete[x]==len(streams[x]):done_command(x)

    while len(visible)<len(cmds):
        # All events at a timestamp are committed before any new arbitration.
        while events and events[0][0]<=now+1e-8:
            at,seq,kind,data=heapq.heappop(events)
            if kind=='activate':
                x=data;c=cmds[x]
                if c.kind=='compute':push(now+c.cycles,'compute_done',x)
                else:
                    streams[x]=bursts(c,hw);cursor[x]=0;inflight[x]=0;complete[x]=0
                    (active_dma if c.kind=='dma' else active_local).append(x)
            elif kind=='compute_done':done_command(data)
            elif kind=='visible':
                x=data;visible.add(x);traces[x]['visible']=now
                deliveries.append({'task':x,'time':now})
                for y in succ[x]:
                    remain[y]-=1;m['notification_count']+=1
                    if not remain[y]:ready.add(y)
                scheduling=True
            elif kind=='mature':
                data['mature']=now;heapq.heappush(mature,(now,data['rid'],data))
            elif kind=='external_done':
                external_busy=False;data['external_end']=now;fabric_queue.append(data)
            elif kind=='fabric_done':
                fabric_busy=False;data['fabric_end']=now;bank_enqueue(data)
            elif kind=='bank_done':
                bank_busy[data['bank']]=False;data['bank_end']=now;request_done(data)
            else:raise AssertionError(kind)
        if len(visible)==len(cmds):break
        # Command scheduling is only recomputed after actual relevant changes.
        if scheduling and issue_next<=now+1e-8:
            scheduling=False
            for x in sorted(ready,key=lambda x:rank[x]):
                c=cmds[x];m['command_scans']+=1
                if x in issued:continue
                if policy=='S' and queues[c.engine][ptr[c.engine]]!=x:continue
                cap=hw.dma_commands if c.kind=='dma' else 1
                if len(engines[c.engine])>=cap:continue
                if c.kind=='dma' and now<dma_command_next-1e-8:
                    scheduling=True;continue
                if issue_next>now+1e-8:
                    scheduling=True;break
                issued.add(x);ready.remove(x);engines[c.engine].add(x)
                while ptr[c.engine]<len(queues[c.engine]) and queues[c.engine][ptr[c.engine]] in issued:ptr[c.engine]+=1
                issue_next=now+hw.issue_cycle
                if c.kind=='dma':dma_command_next=now+plan.dma_spacing
                traces[x]={'task':x,'kind':c.kind,'engine':c.engine,'core':c.core,'dispatch':now,
                           'start':now+hw.dispatch+extra,'sequence':len(traces)}
                push(now+hw.dispatch+extra,'activate',x);m['issue_count']+=1
                scheduling=bool(ready)
                if hw.issue_cycle:break
        # Finite globally shared DMA request credits. Round-robin among the
        # already admitted DMA commands is identical for S and B.
        if active_dma and dma_used<hw.outstanding and dma_issue_next<=now+1e-8:
            for offset in range(len(active_dma)):
                idx=(dma_rr+offset)%len(active_dma);x=active_dma[idx]
                if cursor[x]>=len(streams[x]):continue
                i=cursor[x];addr,size=streams[x][i];cursor[x]+=1;inflight[x]+=1
                r={'rid':f'{x}:{i}','task':x,'index':i,'origin':'dma','address':addr,'bytes':size,
                   'issued':now,'external_latency':env.latency(x,i,hw.external_latency)}
                dma_used+=1;dma_issue_next=now+hw.request_issue;dma_rr=(idx+1)%len(active_dma)
                push(now+r['external_latency'],'mature',r)
                break
        # Local RF feeds/drains have bounded requests too. Requests do not lock
        # the whole SRAM port through arithmetic execution.
        for x in tuple(active_local):
            while cursor[x]<len(streams[x]) and inflight[x]<hw.local_outstanding:
                i=cursor[x];addr,size=streams[x][i];cursor[x]+=1;inflight[x]+=1
                r={'rid':f'{x}:{i}','task':x,'index':i,'origin':cmds[x].kind,
                   'address':addr,'bytes':size,'issued':now}
                if cmds[x].kind=='read':m['local_read_bytes']+=size
                else:m['local_write_bytes']+=size
                bank_enqueue(r)
        # External return slot is reserved before data starts moving; full
        # receiver propagates backpressure to the external bus and O credits.
        if not external_busy and mature and return_used<hw.return_slots:
            _,_,r=heapq.heappop(mature);return_used+=1;external_busy=True
            r['return_reserved']=now;r['external_start']=now
            finish=env.finish(now,r['bytes']/hw.external_bw,'external')
            m['external_bytes']+=r['bytes'];m['external_service_cycles']+=finish-now
            push(finish,'external_done',r)
        if not fabric_busy and fabric_queue:
            r=fabric_queue.popleft();fabric_busy=True;r['fabric_start']=now
            finish=now+hw.fabric_latency+r['bytes']/hw.fabric_bw
            m['fabric_bytes']+=r['bytes'];m['fabric_service_cycles']+=finish-now
            push(finish,'fabric_done',r)
        if now>=sram_inject_next-1e-8:
            eligible=[b for b in range(hw.banks) if banks[b] and not bank_busy[b]]
            if eligible:
                if hw.bank_arbitration=='fifo':
                    oldest=min((q[0]['bank_arrival'],q[0]['rid'],b) for b,q in enumerate(banks) if q)[2]
                    chosen=oldest if oldest in eligible else None
                else:
                    chosen=min(eligible,key=lambda b:(b-bank_rr)%hw.banks)
                if chosen is not None:
                    r=banks[chosen].popleft();bank_busy[chosen]=True;bank_rr=(chosen+1)%hw.banks
                    r['bank_start']=now
                    # Aggregate bandwidth remains constant across bank count.
                    service=r['bytes']/(hw.sram_bw/hw.banks)
                    finish=env.finish(now,service,'bank',chosen,hw.banks)
                    m['bank_service_cycles'][chosen]+=finish-now
                    sram_inject_next=now+r['bytes']/hw.sram_bw
                    push(finish,'bank_done',r)
        m['dma_outstanding_peak']=max(m['dma_outstanding_peak'],dma_used)
        m['return_slots_peak']=max(m['return_slots_peak'],return_used)
        m['mature_wait_peak']=max(m['mature_wait_peak'],len(mature))
        m['bank_queue_peak']=max(m['bank_queue_peak'],sum(map(len,banks)))
        m['ready_peak']=max(m['ready_peak'],len(ready))
        m['max_live_commands']=max(m['max_live_commands'],sum(map(len,engines.values())))
        future=[events[0][0]] if events else []
        if scheduling and ready:
            if issue_next>now+1e-8:future.append(issue_next)
            if dma_command_next>now+1e-8:future.append(dma_command_next)
        pending_dma=any(cursor[x]<len(streams[x]) for x in active_dma)
        if pending_dma and dma_used<hw.outstanding and dma_issue_next>now+1e-8:future.append(dma_issue_next)
        bank_pending=any(banks)
        if bank_pending and sram_inject_next>now+1e-8:future.append(sram_inject_next)
        if not future:raise RuntimeError(f'deadlock {graph.name} ready={ready}')
        nxt=min(future);dt=nxt-now
        if pending_dma and dma_used>=hw.outstanding:m['outstanding_blocked_union']+=dt
        if mature and return_used>=hw.return_slots:m['return_backpressure_union']+=dt
        if bank_pending and all(bank_busy[b] for b in range(hw.banks) if banks[b]):m['bank_blocked_union']+=dt
        alternate=[]
        if policy=='S' and issue_next<=now+1e-8:
            for x in ready:
                c=cmds[x];cap=hw.dma_commands if c.kind=='dma' else 1
                paced=(c.kind!='dma' or dma_command_next<=now+1e-8)
                if paced and len(engines[c.engine])<cap and queues[c.engine][ptr[c.engine]]!=x:alternate.append(x)
        if alternate:
            m['task_order_blocked_union']+=dt
            if detailed:order_wait.append({'start':now,'end':nxt,'alternatives':sorted(alternate)})
        now=nxt
    latency=max(t['visible'] for t in traces.values())
    assert dma_used==return_used==0 and not mature and not fabric_queue and not any(banks)
    m['external_bus_occupancy']=m['external_service_cycles']/latency
    m['external_payload_bw']=m['external_bytes']/latency
    m['fabric_occupancy']=m['fabric_service_cycles']/latency
    m['compute_busy']={e:sum(cmds[x].cycles for x in traces if cmds[x].engine==e and cmds[x].kind=='compute')/latency for e in queues if e.startswith(('mxu','vpu'))}
    m['return_buffer_bytes']=hw.return_slots*hw.granule
    m['outstanding_request_metadata_bits_estimate']=hw.outstanding*(64+32+16+4)
    m['scheduler_state_scope']='full graph command/dependency history retained; no bounded-total scheduler proposal'
    m['request_count']=sum(complete.values())
    return {'latency':latency,'metrics':m,'commands':list(traces.values()) if detailed else [],
        'requests':req_trace if detailed else [],'deliveries':deliveries if detailed else [],
        'order_wait':order_wait,'environment':asdict(env),'hardware':asdict(hw),
        'plan':asdict(plan),'policy':policy,'extra_dispatch':extra}
