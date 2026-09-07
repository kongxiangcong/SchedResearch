"""Fixture producer only; independent checker never imports this module."""
import sys,json,itertools
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from r10.model import build_graph,simulate,load_hardware
from r10.bounds import lower_bounds
from r10.independent_check import verify_bounds
from r9.independent_check import audit_trace,require
from r9.check_tests import tiny_graph,tiny_expected

def main():
    hw=load_hardware();records=[];faults=[]
    for label,override in [('EXT128',{'external_bytes_per_cycle':128}),('DMA32',{'cluster_dma_bytes_per_cycle':32})]:
        h=hw|override
        for q,mc,phase in itertools.product((1,2,4),(False,True),(0.,8191.)):
            c=dict(mapping='C2K',ktile=256,buffers=2,prefetch=2,outstanding=q,multicast=mc)
            g=build_graph(h,c);e=dict(period=8192.,duty=.35,phase=phase);r=simulate(g,h,e,True)
            en=dict(hardware=h,config=g['config'],graph=g,environment=e,result=r)
            b=lower_bounds(g,h,e);verify_bounds(en,b);report=audit_trace(en)
            records.append(dict(label=label,q=q,multicast=mc,phase=phase,bounds=b,elapsed=r['elapsed'],requests=report['requests']))
            if q==4 and mc and phase==8191:
                d=next(d for d in r['ext_decisions'] if len(d['candidates'])>1)
                alt=next(p for p in d['candidates'] if p!=d['default'])
                ar=simulate(g,h,e,True,dict(decision_index=d['decision_index'],choose_request=alt,cost_cycles=8))
                ae=en|{'result':ar};verify_bounds(ae,b);audit_trace(ae)
                records.append(dict(label=label,action_fixture=True,bounds=b,elapsed=ar['elapsed'],requests=len(ar['requests'])))
    # Directly enumerate both legal first choices in the original tiny fixture.
    th=hw|dict(clusters=1,external_bytes_per_cycle=64,cluster_dma_bytes_per_cycle=64)
    tg=tiny_graph(th)
    for phase,order in itertools.product((0,13),('ab','ba')):
        e=dict(period=32.,duty=.25,phase=phase)
        r=simulate(tg,th,e,True,None if order=='ab' else dict(decision_index=0,choose_request='b:p',cost_cycles=0))
        en=dict(hardware=th,config=tg['config'],graph=tg,environment=e,result=r)
        b=lower_bounds(tg,th,e);verify_bounds(en,b);require(r['elapsed']==tiny_expected(order,phase)[0],'tiny exact finish')
        records.append(dict(tiny=True,order=order,phase=phase,elapsed=r['elapsed'],bounds=b,requests=len(r['requests'])))
    for name,claimed in [('inflated_tight',b|{'tight':r['elapsed']+1}),('omitted_credit',b|{'credit':0})]:
        try:verify_bounds(en,claimed)
        except AssertionError as err:faults.append(dict(name=name,status='DETECTED',reason=str(err)))
        else:raise AssertionError('bad bound not detected')
    cert=dict(status='PASS',fixtures=len(records),faults=faults,records=records,scope='bound direction and tiny local-visible exact only; not main optimum')
    (ROOT/'r10/results/bound_tests.json').write_text(json.dumps(cert,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in cert.items() if k!='records'}))
if __name__=='__main__':main()
