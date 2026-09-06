"""Verify frozen R1-R7 lineage and R8 handoff; never freezes future R8 results."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
R8=ROOT/'r8'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise RuntimeError(str(message))
def rows(p):return [x for x in p.read_text(encoding='utf8').splitlines() if x.startswith('| R')]
def preserve(parent,child):
    a,b=rows(parent),rows(child);ac,bc=Counter(a),Counter(b)
    require(all(bc[x]==n for x,n in ac.items()),'Historical row changed/removed/duplicated')
    require([x for x in b if x in ac]==a,'Historical row order changed')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--require-handoff',action='store_true');args=parser.parse_args()
    handoff=read(R8/'handoff_integrity.json');counts={}
    for p,h in handoff['parent_manifests'].items():require(sha(ROOT/p)==h,p)
    mappings=[('r7','r7/artifact_integrity.json','sha256','r8/history/r7_research_progress.md',686),
              ('r6','r6/artifact_integrity.json','sha256','r7/history/r6_research_progress.md',89),
              ('r5','r5/artifact_integrity.json','sha256','r6/history/r5_research_progress.md',262),
              ('r4','experiments/results/r4/artifact_integrity.json','artifact_sha256',None,612)]
    for label,manifest,key,snapshot,count in mappings:
        expected=read(ROOT/manifest)[key];require(len(expected)==count,label)
        for logical,digest in expected.items():
            physical=snapshot if logical=='research_progress.md' and snapshot else logical
            require(sha(ROOT/physical)==digest,{'round':label,'logical':logical,'physical':physical})
        counts[label]=count
    for p,h in handoff['handoff_files'].items():require(sha(ROOT/p)==h,p)
    r7line=read(ROOT/'r7/history_lineage.json');r6line=read(ROOT/'r6/history_lineage.json')
    require(sha(ROOT/'r8/history/r7_research_progress.md')==r7line['successor_progress']['sha256'],'R7 snapshot lineage')
    require(sha(ROOT/'r7/history/r6_research_progress.md')==r7line['r6_progress_snapshot']['sha256']==r6line['successor_progress']['sha256'],'R6 snapshot lineage')
    require(sha(ROOT/'r6/history/r5_research_progress.md')==r6line['r5_progress_snapshot']['sha256'],'R5 snapshot lineage')
    require(handoff['progress_lineage']['parent_sha256']==sha(ROOT/'r8/history/r7_research_progress.md'),'Handoff parent')
    require(handoff['progress_lineage']['successor_sha256']==sha(ROOT/'r8/history/aligned_research_progress.md'),'Handoff successor')
    preserve(ROOT/'r8/history/r7_research_progress.md',ROOT/'r8/history/aligned_research_progress.md')
    preserve(ROOT/'r8/history/aligned_research_progress.md',ROOT/'research_progress.md')
    if args.require_handoff:require(sha(ROOT/'research_progress.md')==handoff['progress_lineage']['successor_sha256'],'Root evolved after handoff; use new successor evidence')
    print(json.dumps({'status':'PASS','historical_paths':counts,'handoff_files':len(handoff['handoff_files']),'historical_rows_preserved':len(rows(ROOT/'r8/history/r7_research_progress.md'))-1,'current_root_is_handoff':sha(ROOT/'research_progress.md')==handoff['progress_lineage']['successor_sha256'],'scope':'history and scope-alignment handoff, not R8 experimental acceptance'}))

if __name__=='__main__':main()
