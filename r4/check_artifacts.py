"""Final source, original-result, evidence, and document-link integrity check."""
from pathlib import Path
import hashlib
import json
import re
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
R4=ROOT/'r4'
OUT=ROOT/'experiments/results/r4'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    main_manifest=json.loads((OUT/'manifest.json').read_text())
    probe=json.loads((OUT/'priority_probe/manifest.json').read_text())
    assert main_manifest['status']==probe['status']=='complete'
    assert main_manifest['executions']==70*32*6
    assert probe['executions']==70*32*2
    for rel,sha in main_manifest['source_hashes'].items():
        assert digest(ROOT/rel)==sha,rel
    assert digest(R4/'priority_probe.py')==probe['probe_source_sha256']
    assert digest(OUT/'manifest.json')==probe['main_manifest_sha256']
    snapshot=json.loads((R4/'r3_snapshot/manifest.json').read_text())
    for rel,sha in snapshot['sources'].items():
        assert digest(R4/'r3_snapshot'/rel)==sha,rel
        if rel.startswith('sim/'):
            assert digest(ROOT/rel)==sha,rel
    for rel,sha in snapshot['prior_results'].items():
        assert digest(ROOT/rel)==sha,rel
    evidence_count=0
    for file in (R4/'sources/qwen/manifest.json',R4/'sources/qwen/tensor_header_manifest.json',R4/'sources/flux/source_manifest.json'):
        data=json.loads(file.read_text(encoding='utf-8'))
        for row in data['files']:
            rel=row.get('file',row.get('path'))
            if rel and 'sha256' in row:
                assert digest(file.parent/rel)==row['sha256'],str(file.parent/rel)
                evidence_count+=1
    missing=[]
    documents=list(R4.glob('*.md'))+[ROOT/'README.md']
    for doc in documents:
        for link in re.findall(r'\[[^\]]*\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
            link=link.strip('<>')
            if '://' in link or link.startswith('#'):
                continue
            target=unquote(link.split('#')[0])
            if target and not (doc.parent/target).exists():
                missing.append([str(doc.relative_to(ROOT)),link])
    assert not missing,missing
    required=('model_registry.md','problem.md','hypotheses.md','experiment_plan.md','experiment_report.md',
        'rejected_refined_directions.md','next_round.md','redteam_report.md')
    assert all((R4/p).exists() for p in required)
    active={str((OUT/p).resolve()) for p in main_manifest['active_counterfactual_artifacts']}
    ignored=[p for p in (OUT/'counterfactuals').glob('*.json') if str(p.resolve()) not in active]
    own=OUT/'artifact_integrity.json'
    paths=[ROOT/'README.md']
    for base in (R4,OUT):
        paths += [p for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p!=own and p not in ignored]
    hashes={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    result={'status':'PASS','source_hashes_verified':len(main_manifest['source_hashes']),
        'official_source_files_verified':evidence_count,'r3_snapshot_files_verified':len(snapshot['sources']),
        'prior_result_files_unchanged':len(snapshot['prior_results']),'documents_checked':len(documents),
        'main_executions':main_manifest['executions'],'priority_executions':probe['executions'],
        'active_counterfactuals':len(active),'inactive_interrupted_probe_files':[p.relative_to(ROOT).as_posix() for p in ignored],
        'artifact_sha256':hashes,'scope':'integrity and link check; numerical/timing replay is separately reported by independent redteam'}
    own.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print({k:v for k,v in result.items() if k!='artifact_sha256'})


if __name__=='__main__':
    main()
