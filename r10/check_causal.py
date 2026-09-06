"""Independent trace reconstruction of bounded causal rule and costs."""
import sys,json,random,statistics,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from r10.causal_trace_check import audit_trace,read_json,digest,require,same

def rule_check(en):
    r=en['result'];packets={p['id']:p for p in r['requests']};applied=False;observed=0;total=0;next_cluster=0;other_busy_samples=0
    insertion={p['id']:i for i,p in enumerate(r['requests'])}
    def queue_key(p):
        read=p['direction']=='dma_read'
        return (p['accept']+en['hardware']['request_latency_cycles'] if read else p['local_end'],p['accept'] if read else p['local_start'],int(not read),insertion[p['id']])
    for d in r['ext_decisions']:
        active_clusters={packets[x]['cluster'] for x in d['candidates']}
        dc=next_cluster if next_cluster in active_clusters else 1-next_cluster
        default_head=min((packets[x] for x in d['candidates'] if packets[x]['cluster']==dc),key=queue_key)
        require(default_head['id']==d['default'],'RR FIFO default reconstruction')
        chosen=d['default'];cost=0
        if not applied and 64<=d['decision_index']<=67:
            observed+=1;cost=2;t=d['time'];default=packets[chosen];c=default['cluster'];other=1-c
            # local service has been started for this same timestamp before EXT
            # arbitration. Complete-at-t is idle; start-at-t is busy.
            busy={x:any(p['cluster']==x and p['local_start']<=t+1e-8 and p['local_end']>t+1e-8 for p in packets.values()) for x in (0,1)}
            other_busy_samples+=int(busy[other])
            alternatives=[packets[pid] for pid in d['candidates'] if packets[pid]['cluster']==other]
            if alternatives:
                # EXT queue enqueued at read latency expiry or write local end.
                head=min(alternatives,key=queue_key)
                if default['direction']=='dma_read' and busy[c] and not busy[other] and head['direction']=='dma_read':
                    chosen=head['id'];cost=10;applied=True
        require(d['chosen']==chosen,'causal choice reconstruction')
        require(d['cost_cycles']==cost,'causal observation/action charge')
        total+=cost
        next_cluster=1-packets[d['chosen']]['cluster']
    require(observed<=4 and total<=16,'bounded observer budget')
    require(r['intervention_applied']==applied,'action applied flag')
    return dict(observations=observed,charge=total,action=applied,other_busy_samples=other_busy_samples)

def main():
    out=ROOT/'r10/causal_results';reg=read_json(out/'registration.json');rows=read_json(out/'test_pairs.json');summary=read_json(out/'summary.json')
    require(digest(ROOT/'r10/causal_plan.md')==reg['plan_sha256'],'causal plan freeze')
    require(digest(ROOT/'r10/causal_model.py')==reg['model_sha256'],'causal model freeze')
    require(digest(ROOT/'r10/run_causal.py')==reg['runner_sha256'],'causal runner freeze')
    require(digest(ROOT/'r10/results/selection.json')==reg['stage_a_selection_sha256'],'baseline selection freeze')
    seen=[]
    for name,seed,n in [('train',1110000,8),('validation',1120000,8),('test_s1',1130000,30),('test_s2',1140000,30)]:
        rng=random.Random(seed);expected=[rng.random()*8192 for _ in range(n)];require(reg['phases'][name]==expected,'new phase stream');seen+=expected
    prior=read_json(ROOT/'r10/results/registration.json')['phases'];require(len(set(seen))==76 and not(set(seen)&set(sum(prior.values(),[]))),'stage phase independence')
    require(len(rows)==360,'causal pair count')
    hashes={r['path']:r['sha256'] for r in read_json(out/'trace_manifest.json')};reports=[];faults=[];rules=[]
    for i,row in enumerate(rows,1):
        expected_env=dict(period=8192.,duty={'quiet':0.,'reserved20':.2,'reserved35':.35}[row['condition']],phase=reg['phases'][row['split']][row['block']])
        ens={}
        for role in ('baseline','causal'):
            p=out/row[role+'_trace'];require(digest(p)==hashes[row[role+'_trace']],'trace hash');en=read_json(p);ens[role]=en
            require(en['hardware']==reg['hardware'][row['hardware']] and en['environment']==expected_env,'common contract')
            ar=audit_trace(en);require(same(ar['elapsed'],row[role]),'elapsed binding');reports.append(ar)
        require(ens['baseline']['graph']==ens['causal']['graph'],'identical work graph')
        require(all(d['cost_cycles']==0 and d['chosen']==d['default'] for d in ens['baseline']['result']['ext_decisions']),'static baseline')
        rule=rule_check(ens['causal']);require(rule['charge']==row['total_charge'] and rule['action']==row['action_applied'],'rule result binding')
        rules.append(rule)
        require(same(row['gain_pct'],100*(1-row['causal']/row['baseline'])),'paired gain')
        if i==1:
            from copy import deepcopy
            broken=deepcopy(ens['causal']);broken['result']['ext_decisions'][64]['cost_cycles']=0
            try:rule_check(broken)
            except AssertionError as err:faults.append(str(err))
            else:raise AssertionError('missing observation fee undetected')
        if i%30==0:print('causal audit pairs',i,flush=True)
    for key,s in summary.items():
        h,split,c=key.split('.');v=[r['gain_pct'] for r in rows if (r['hardware'],r['split'],r['condition'])==(h,split,c)];require(len(v)==30,'cell count')
        mu=math.fsum(v)/30;margin=2.045229642132703*statistics.stdev(v)/math.sqrt(30)
        require(all(same(x,y) for x,y in zip([mu,min(v),max(v),mu-margin,mu+margin],[s['mean'],s['min'],s['max'],*s['ci95_t']])),'independent CI')
    completion=read_json(out/'completion.json');require(completion['traces']==len(reports)==720,'trace coverage')
    cert=dict(status='PASS',pairs=len(rows),traces=len(reports),requests=sum(r['requests'] for r in reports),operations=sum(r['operations'] for r in reports),faults_detected=faults,checker_sha256=digest(Path(__file__)),observations=sum(r['observations'] for r in rules),actions=sum(r['action'] for r in rules),other_busy_samples=sum(r['other_busy_samples'] for r in rules))
    (out/'audit_results.json').write_text(json.dumps(cert,indent=2),encoding='utf8');print(json.dumps(cert))
if __name__=='__main__':main()
