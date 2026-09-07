"""Post-red-team compiler residency control on fresh split seeds.

No frozen runtime file or dynamic policy changes. Two re-trained compiler
lowerings differ only by retaining each GDN state in already-budgeted private RF
across four prepared tokens. This post-hoc control is not an architecture gate.
"""
from __future__ import annotations
from dataclasses import asdict, replace
from pathlib import Path
import gzip
import hashlib
import json
import statistics
import time
from functools import lru_cache
import numpy as np
from r5.model import Graph, Hardware, Plan, recurrent
from r5.resource_sim import Environment, simulate
from r5.static_plans import STRATEGIES, COLORS, SPACINGS, topological, neighbors
from r5.replay_audit import audit

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'resident_control_results'
TRAIN = (3200, 3201)
VALID = (3300, 3301)
TEST = tuple(range(3400, 3412))
FROZEN = ('model.py', 'resource_sim.py', 'coarse_sim.py', 'static_plans.py', 'run_experiments.py', 'replay_audit.py')


@lru_cache(maxsize=1)
def numerical_liveout_contract():
    specs = json.loads((ROOT/'full_width_specs.json').read_text())
    numbers = json.loads((ROOT/'numerical_checks.json').read_text())
    spec = specs['qwen_gdn']
    assert spec['tokens'] == 4 and spec['selected_value_heads'] == [0,1]
    assert spec['output_bytes'] == 4096 and spec['final_state_bytes'] == 131072
    assert numbers['specs_sha256'] == hashlib.sha256((ROOT/'full_width_specs.json').read_bytes()).hexdigest()
    verified = []
    for row in numbers['checks']:
        if row['case'] != spec['case']: continue
        for key, shape, size in (('o_all_tokens',[4,2,128],4096),('S_final',[2,128,128],131072)):
            tensor = row['tensors'][key]
            assert tensor['shape'] == shape and tensor['storage_dtype'] == 'FP32' and tensor['logical_storage_bytes'] == size
        assert row['o_all_tokens']['status'] == row['S_every_token']['status'] == 'PASS'
        verified.append({'seed':row['seed'], 'all_four_outputs_sha256':row['tensors']['o_all_tokens']['sha256_little_endian_payload'],
                         'final_state_sha256':row['tensors']['S_final']['sha256_little_endian_payload']})
    assert len(verified) == 3
    return {'scope':'authenticated existing mathematical oracle outputs; no timed tensor-payload execution',
            'numerical_checks_sha256':hashlib.sha256((ROOT/'numerical_checks.json').read_bytes()).hexdigest(),
            'per_token_outputs':[{'producer':f'delta{h}.{t}','output':f'o{h}.{t}','shape':[128],'dtype':'FP32','bytes':512,'residence':'private RF pinned through slice end'} for h in range(2) for t in range(4)],
            'final_state_shape':[2,128,128], 'final_state_dtype':'FP32', 'verified_numerical_seeds':verified}


def hashes():
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in FROZEN}


def resident_graph(color=0, hw=Hardware()):
    original = recurrent(color, hw); commands = []
    for command in original.commands:
        if command.kind == 'compute':
            token = int(command.cid.rsplit('.', 1)[1])
            deps = command.deps if token == 0 else (f'delta{command.core}.{token-1}',)
            commands.append(replace(command, deps=deps))
        elif command.kind == 'dma' or command.cid.startswith('state_read') and command.cid.endswith('.0') or command.cid.startswith('state_write') and command.cid.endswith('.3'):
            commands.append(command)
    meta = dict(original.metadata)
    meta.update({'state_local_traffic_bytes': 2*meta['state_bytes'],
                 'output_RF_liveout_bytes':4096, 'output_RF_liveouts':numerical_liveout_contract()['per_token_outputs'],
                 'scope': 'post-red-team static RF-residency control: same two full heads/four prepared tokens; initial state DMA/read and final SRAM write; four outputs retained in RF',
                 'lifetime': 'S remains in private RF from initial read through all four ordered delta updates until final write; prepared inputs and all four outputs remain budgeted',
                 'control_class': 'compiler residency, no new runtime policy'})
    graph = Graph('qwen_gdn_state_rf_resident_control', tuple(commands), meta)
    graph.validate(hw)
    validate_equivalence(original, graph, hw)
    return graph


def validate_equivalence(original, resident, hw):
    a, b = {c.cid:c for c in original.commands}, {c.cid:c for c in resident.commands}
    assert original.metadata['rf_bytes_per_core'] == resident.metadata['rf_bytes_per_core'] == 73760 <= hw.rf_capacity
    assert original.metadata['state_bytes'] == resident.metadata['state_bytes'] == 131072
    for key in ('prepared_vector_bytes_per_core', 'tokens', 'heads', 'dtype'):
        assert original.metadata[key] == resident.metadata[key]
    liveout = numerical_liveout_contract()
    assert sum(x['bytes'] for x in liveout['per_token_outputs']) == resident.metadata['output_RF_liveout_bytes'] == 4096
    for vector in liveout['per_token_outputs']:
        assert vector['producer'] in a and vector['producer'] in b
    for core in range(2):
        for token in range(4):
            x = f'delta{core}.{token}'
            before, after = asdict(a[x]), asdict(b[x])
            before.pop('deps'); after.pop('deps'); assert before == after
            if token: assert b[x].deps == (f'delta{core}.{token-1}',)
        for x in (f'state_init{core}', f'state_read{core}.0', f'state_write{core}.3'):
            assert a[x] == b[x]
    assert len(resident.commands) == 14 and len(original.commands) == 26
    assert sum(c.ops for c in original.commands) == sum(c.ops for c in resident.commands) == 917504
    for graph, local_bytes in ((original, 1048576), (resident, 262144)):
        assert sum(s.size for c in graph.commands if c.kind in ('read','write') for s in c.spans) == local_bytes
        assert sum(s.size for c in graph.commands if c.kind == 'dma' for s in c.spans) == 131072
    return {'status': 'PASS', 'proof': 'structural retained arithmetic and per-head update order; common initial/final state transfer and RF output budget; not numerical payload replay',
            'ops_both': 917504, 'initial_external_bytes_both': 131072,
            'local_bytes_original': 1048576, 'local_bytes_resident': 262144,
            'rf_bytes_per_core_both': 73760, 'output_RF_liveout_bytes_both': 4096,
            'numerical_liveout_contract':liveout}


def candidates(builder, hw):
    plans, seen, graphs = [], set(), {}
    for color in COLORS:
        graph = graphs[color] = builder(color, hw)
        for strategy in STRATEGIES:
            order = topological(graph, strategy, hw)
            for spacing in SPACINGS:
                key = (order, color, spacing)
                if key in seen: continue
                seen.add(key)
                plans.append(Plan(order, color, spacing, f'{strategy}-c{color}-p{spacing}'))
    return plans, graphs


def interval(values):
    rng = np.random.default_rng(9437); data = np.array(values)
    samples = data[rng.integers(0, len(data), (4096, len(data)))].mean(axis=1)
    return [float(x) for x in np.quantile(samples, [.025, .975])]


def run_lowering(label, builder, hw, mode):
    plans, graphs = candidates(builder, hw); initial_count = len(plans); checked = 0
    training, known = [], {p.name:p for p in plans}
    seen = {(p.order,p.bank_color,p.dma_spacing) for p in plans}
    def run(plan, seed, policy='S', extra=0):
        nonlocal checked
        graph = graphs[plan.bank_color]
        result = simulate(graph, hw, plan, Environment(seed, mode), policy, extra, detailed=True)
        result['independent_audit'] = audit(graph, result); checked += 1
        return result
    def train(plan):
        times = [run(plan, seed)['latency'] for seed in TRAIN]
        training.append({'plan':asdict(plan), 'latencies':times, 'mean':statistics.mean(times)})
    for plan in plans: train(plan)
    training.sort(key=lambda x:(x['mean'],x['plan']['name']))
    local_count = 0
    while local_count < 64:
        best = known[training[0]['plan']['name']]; batch = []
        for order in neighbors(graphs[best.bank_color], best):
            signature = (order,best.bank_color,best.dma_spacing)
            if signature in seen: continue
            seen.add(signature)
            batch.append(Plan(order,best.bank_color,best.dma_spacing,f'local{local_count+len(batch):03}'))
            if len(batch) >= min(16,64-local_count): break
        if not batch: break
        for plan in batch: known[plan.name]=plan; train(plan)
        local_count += len(batch)
        training.sort(key=lambda x:(x['mean'],x['plan']['name']))
    validation = []
    for entry in training[:3]:
        plan = known[entry['plan']['name']]
        times = [run(plan, seed)['latency'] for seed in VALID]
        validation.append({'plan':asdict(plan), 'latencies':times, 'mean':statistics.mean(times)})
    validation.sort(key=lambda x:(x['mean'],x['plan']['name']))
    selected = known[validation[0]['plan']['name']]; rows = []; traces = []
    for seed in TEST:
        outputs = {}
        for tag, policy, extra in (('S','S',0), ('B0','B',0), ('B2','B',2)):
            result = run(selected,seed,policy,extra)
            outputs[tag] = {'latency':result['latency'], 'metrics':result['metrics'], 'independent_audit':result['independent_audit']}
            if seed == TEST[0]:
                result['graph'] = asdict(graphs[selected.bank_color])
                path = OUT/f'{label}__{seed}__{tag}.json.gz'
                with gzip.open(path,'wt',encoding='utf-8',compresslevel=3) as stream: json.dump(result,stream,separators=(',',':'))
                traces.append(path.name)
        rows.append({'seed':seed,'results':outputs})
    return {'label':label,'hardware':asdict(hw),'mode':mode,'initial_plan_count':initial_count,'local_plan_count':local_count,
            'selected_plan':asdict(selected),'training':training,'validation':validation,'rows':rows,'trace_files':traces,
            'all_executions_independently_audited':checked,
            'mean_latency':{tag:statistics.mean(row['results'][tag]['latency'] for row in rows) for tag in ('S','B0','B2')}}


def main():
    OUT.mkdir(parents=True,exist_ok=True); frozen = hashes(); started = time.time(); cases = []
    configs = [('ref_none',Hardware(),'none'), ('ref_combined',Hardware(),'combined'),
               ('o1_combined',replace(Hardware(),outstanding=1),'combined'),
               ('r1_combined',replace(Hardware(),return_slots=1),'combined')]
    manifest = {'classification':'post-red-team compiler residency control, not preregistered main architecture-positive evidence',
                'train_seeds':TRAIN,'validation_seeds':VALID,'test_seeds':TEST,
                'configs':[{'label':label,'hardware':asdict(hw),'mode':mode} for label,hw,mode in configs],
                'compiler_search':'six priorities x three colors x three spacings, deduplicated; up to64 same legal adjacent swaps; train then top3 validation; fresh heldout only',
                'frozen_runtime_sha256':frozen,'control_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    for label, hw, mode in configs:
        pair = {}
        for variant, builder in (('original',recurrent), ('resident',resident_graph)):
            row = run_lowering(f'{label}__{variant}',builder,hw,mode)
            (OUT/f'{label}__{variant}.json').write_text(json.dumps(row,indent=2),encoding='utf-8')
            pair[variant] = row
            print(json.dumps({'finished':label,'variant':variant,'mean_latency':row['mean_latency'],'audited':row['all_executions_independently_audited']}),flush=True)
        metrics = {'static_compiler_residency_gain_pct':[], 'resident_B0_vs_resident_S_gain_pct':[],
                   'resident_B2_vs_resident_S_gain_pct':[], 'original_B0_vs_original_S_gain_pct':[]}
        for a,b in zip(pair['original']['rows'],pair['resident']['rows']):
            assert a['seed'] == b['seed']
            old,new = a['results'],b['results']; base,res = old['S']['latency'],new['S']['latency']
            metrics['static_compiler_residency_gain_pct'].append(100*(1-res/base))
            metrics['resident_B0_vs_resident_S_gain_pct'].append(100*(1-new['B0']['latency']/res))
            metrics['resident_B2_vs_resident_S_gain_pct'].append(100*(1-new['B2']['latency']/res))
            metrics['original_B0_vs_original_S_gain_pct'].append(100*(1-old['B0']['latency']/base))
        cases.append({'configuration':label,'source_work_equivalence':validate_equivalence(recurrent(0,hw),resident_graph(0,hw),hw),
                      'mean_latency':{k:v['mean_latency'] for k,v in pair.items()},
                      'effects':{k:{'mean_pct':statistics.mean(v),'ci95_pct':interval(v),'paired_seed_values_pct':v} for k,v in metrics.items()},
                      'executions_audited':sum(v['all_executions_independently_audited'] for v in pair.values())})
    assert hashes() == frozen, 'runtime changed during control'
    result = {'status':'PASS','manifest':manifest,'cases':cases,'total_executions_audited':sum(c['executions_audited'] for c in cases),
              'elapsed_seconds':time.time()-started,'evidence_scope':'source arithmetic/order/liveout structural equivalence plus independent timed request replay; no timed numerical payload execution',
              'limitations':['Post-hoc falsification control with fresh splits; does not reopen main architecture-positive gate.',
                             'Prepared four-token inputs and RF output residency remain assumptions; no token/s or full-layer claim.',
                             'Other layers do not occupy RF in this micrograph; real autoregressive inter-token execution through other layers is excluded. Four-token residency gains cannot be extrapolated to full-model decode.',
                             'Residency is plausible under declared private RF capacity; real MXU/VPU ISA/RF accessibility and PPA are not verified.',
                             'Reduced local traffic is a static compiler change, not recovery from dynamic uncertainty.']}
    (ROOT/'resident_control_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'status':'PASS','configurations':len(cases),'executions_audited':result['total_executions_audited']}),flush=True)


if __name__ == '__main__':
    main()
