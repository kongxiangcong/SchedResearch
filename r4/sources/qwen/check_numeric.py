"""Repeat the source-derived Qwen algebra/state check, with no model weights."""
from pathlib import Path
import hashlib, json
import numpy as np
from r4.qwen_lowering import build_cases


def main():
    results=[]
    for seed in (7,19,37,101,709):
        for case in build_cases(seed):
            actual=case.evaluate()
            errors={k:float(np.max(np.abs(actual[k]-case.reference[k]))) for k in case.outputs}
            assert max(errors.values())<1e-10,(seed,case.name,errors)
            results.append({'seed':seed,'linear_seed_offset':1,'case':case.name,'outputs':errors,
                            'nodes':len(case.nodes),'dense_macs':sum(n.macs for n in case.nodes),
                            'vpu_operation_estimate':sum(n.vector_ops for n in case.nodes)})
    root=Path(__file__).resolve().parents[3]
    files=['r4/qwen_lowering.py','r4/graph.py','r4/sources/qwen/config.json',
           'r4/sources/qwen/modeling_qwen3_5.py']
    record={'method':'independent direct NumPy reference versus task-node algebra; float64, random weights',
            'not_validated':['trained model quality','BF16 numerical error','installed Transformers execution','production compiler','real NPU'],
            'numpy_version':np.__version__,'source_sha256':{f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in files},
            'results':results,'pass':True}
    (Path(__file__).resolve().parent/'numeric_check.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'pass':True,'cases':len(results),'max_abs_error':max(max(x['outputs'].values()) for x in results)}))


if __name__=='__main__':main()
