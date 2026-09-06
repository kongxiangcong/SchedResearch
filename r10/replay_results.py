"""Read saved registrations and re-execute all A/B test elapsed pairs.

Complements independent trace audit with engine reproducibility, not an
independent simulator. New receipt only; refuses to overwrite any output.
"""
import sys,json,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from r10.model import build_graph,simulate
from r10.causal_model import simulate as causal_simulate
from r9.independent_check import read_json,same,digest

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);a=ap.parse_args();out=ROOT/a.output
    assert not out.exists(),'refuse existing receipt'
    reg=read_json(ROOT/'r10/results/registration.json');cat={r['id']:r['config'] for r in reg['candidates']}
    old=read_json(ROOT/'r9/results/sensitivity.json');oldcat={}
    for label,kv in [('EXT128',('external_bytes_per_cycle',128)),('DMA32',('cluster_dma_bytes_per_cycle',32))]:
        v=next(v for v in old if (v['field'],v['value'])==kv);c={r['id']:r['config'] for r in v['training']};oldcat[label]={k:c[i] for k,i in v['selected'].items()}
    count=0
    for r in read_json(ROOT/'r10/results/test_pairs.json'):
        hw=reg['hardware'][r['hardware']];e=dict(period=8192.,duty={'quiet':0.,'reserved20':.2,'reserved35':.35}[r['condition']],phase=r['phase'])
        for c,key in [(cat[r['selected_id']],'elapsed'),(oldcat[r['hardware']][r['condition']],'old_elapsed')]:
            g=build_graph(hw,c);actual=simulate(g,hw,e)['elapsed'];assert same(actual,r[key]),(r,key);count+=1
        if count%120==0:print('A replay executions',count,flush=True)
    for r in read_json(ROOT/'r10/causal_results/test_pairs.json'):
        hw=reg['hardware'][r['hardware']];e=dict(period=8192.,duty={'quiet':0.,'reserved20':.2,'reserved35':.35}[r['condition']],phase=r['phase']);g=build_graph(hw,cat[r['static_id']])
        for causal,key in [(False,'baseline'),(True,'causal')]:
            rr=causal_simulate(g,hw,e,causal=causal);assert same(rr['elapsed'],r[key]),(r,key);count+=1
            if causal:assert rr['intervention_applied']==r['action_applied']
        if count%120==0:print('A+B replay executions',count,flush=True)
    receipt=dict(status='PASS',elapsed_executions=count,A_pairs=360,B_pairs=360,scope='same-engine independent rerun; separate from independent checker',script_sha256=digest(Path(__file__)))
    out.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt))
if __name__=='__main__':main()
