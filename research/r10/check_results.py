"""Named R10 evidence integrity and ordered parent/successor preservation."""
from pathlib import Path
import json,hashlib,itertools
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=ROOT/'r10';manifest=read(p/'results_manifest.json')
    for path,expected in manifest['files'].items():assert sha(ROOT/path)==expected,path
    lineage=read(p/'history_lineage.json');parent=ROOT/lineage['parent_snapshot'];successor=ROOT/lineage['successor_snapshot']
    assert sha(parent)==lineage['parent_sha256'];assert sha(successor)==lineage['successor_sha256']
    assert successor.read_bytes().startswith(parent.read_bytes()),'parent bytes rewritten'
    assert (ROOT/'research_progress.md').read_bytes().startswith(successor.read_bytes()),'frozen successor changed'
    assert sha(ROOT/'r9/results_manifest.json')==lineage['frozen_r9_manifest_sha256']
    old=read(ROOT/'r9/results_manifest.json')
    for path,expected in old['files'].items():assert sha(ROOT/path)==expected,path
    assert sha(p/'model.py')==sha(ROOT/'r9/model.py')
    rows=[s for s in successor.read_text(encoding='utf8').splitlines() if s.startswith('| R10：')]
    assert len(rows)==3 and all(len(s.split('|'))==10 for s in rows),'eight-field progress rows'
    for filename in ('results/audit_results.json','causal_results/audit_results.json','results/bound_tests.json','replay_receipt.json'):
        assert read(p/filename)['status']=='PASS',filename
    assert read(p/'results/audit_results.json')['checker_sha256']==sha(p/'independent_check.py')
    assert read(p/'causal_results/audit_results.json')['checker_sha256']==sha(p/'check_causal.py')
    a=read(p/'results/registration.json')['phases'];b=read(p/'causal_results/registration.json')['phases']
    r9=read(ROOT/'r9/results/prerun_registration.json')['phases']
    av=sum(a.values(),[]);bv=sum(b.values(),[]);ov=[v['phase'] for group in r9.values() for v in group]
    assert len(set(av+bv+ov))==len(av+bv+ov),'cross-round phase overlap'
    summary=read(p/'causal_results/summary.json');completion=read(p/'causal_results/completion.json')
    for h in ('EXT128','DMA32'):
        gate=all(summary[f'{h}.test_s{s}.{c}']['mean']>=5 and summary[f'{h}.test_s{s}.{c}']['ci95_t'][0]>0 for s,c in itertools.product((1,2),('reserved20','reserved35'))) and all(summary[f'{h}.test_s{s}.quiet']['min']>=-1 for s in (1,2))
        assert gate==completion['gate'][h]==False
    print(json.dumps(dict(status='PASS',named_artifacts=len(manifest['files']),R9_artifacts_preserved=len(old['files']),new_progress_rows=len(rows),A_pairs=360,B_pairs=360,total_detailed_traces=1104,scope='reference-model evidence; residual dynamic space unresolved; no hardware acceptance')))
if __name__=='__main__':main()
