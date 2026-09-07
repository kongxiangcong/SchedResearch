"""Independent source/spec/graph accounting audit, not tensor execution replay.

Does not import numerical or simulator execution helpers. Existing numerical
checks are authenticated and cross-checked as reports, not rerun or upgraded
to a timed payload-execution proof. Optional completed coarse/request artifacts
are inspected for equal arithmetic/traffic work; latency equality is not required.
"""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import math
from r5.model import Hardware, build

ROOT = Path(__file__).resolve().parents[1]
R5 = ROOT / 'r5'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def work_signature(graph):
    commands = graph.commands
    return {
        'commands': len(commands), 'MACs': sum(c.macs for c in commands),
        'modeled_vector_ops': sum(c.ops for c in commands),
        'external_bytes': sum(s.size for c in commands if c.kind == 'dma' for s in c.spans),
        'local_read_bytes': sum(s.size for c in commands if c.kind == 'read' for s in c.spans),
        'local_write_bytes': sum(s.size for c in commands if c.kind == 'write' for s in c.spans),
    }


def lifetime_audit(graph):
    """All overlapping SRAM accesses with >=1 writer need DAG order.

    This is a graph/address proof; it does not infer data payload identity.
    RF ping-pong and accumulation order receive separate explicit checks.
    """
    ancestors = {}
    for c in graph.commands:
        ancestors[c.cid] = set(c.deps)
        for dep in c.deps: ancestors[c.cid].update(ancestors[dep])
    checked = 0
    for i, a in enumerate(graph.commands):
        for b in graph.commands[i + 1:]:
            if a.kind not in ('dma', 'write') and b.kind not in ('dma', 'write'): continue
            overlaps = any(max(sa.address, sb.address) < min(sa.address + sa.size, sb.address + sb.size)
                           for sa in a.spans for sb in b.spans)
            if overlaps:
                assert a.cid in ancestors[b.cid] or b.cid in ancestors[a.cid], ('unordered_alias', a.cid, b.cid)
                checked += 1
    return checked


def audit_projection(name, spec, official_k, official_i, color):
    hw = Hardware(); graph = build(name, color, hw); commands = {c.cid: c for c in graph.commands}
    k, m, n, cores, step = spec['K_full'], spec['M'], spec['packed_N_per_core'], spec['cores'], spec['K_step']
    assert k == official_k and spec['full_intermediate_width'] == official_i
    assert n == spec['gate_N_per_core'] + spec['up_N_per_core'] == 128 and cores == 2
    assert spec['selected_intermediate_indices'] == [[0, 64], [64, 128]]
    assert 128 <= official_i and k % step == 0
    weights, inputs, accum, output = 2*cores*k*n, 2*m*k, 4*cores*m*n, 4*cores*m*(n//2)
    expected = {'commands': 1 + cores*(k//step)*3 + cores*4, 'MACs': cores*m*k*n,
                'modeled_vector_ops': cores*8*m*(n//2), 'external_bytes': weights + inputs,
                'local_read_bytes': weights + cores*inputs + accum, 'local_write_bytes': accum + output}
    assert work_signature(graph) == expected
    assert spec['exact_dense_MACs'] == expected['MACs']
    assert spec['logical_bytes'] == {'shared_x': inputs, 'weights_both_cores': weights,
                                   'FP32_projection_both_cores': accum, 'FP32_SwiGLU_both_cores': output}
    input_start = commands['input'].spans[0].address
    for core in range(cores):
        activation_coverage = []
        for i in range(k//step):
            load = commands[f'load.c{core}.k{i:02}']; feed = commands[f'feed.c{core}.k{i:02}']; mac = commands[f'mac.c{core}.k{i:02}']
            assert load.spans[0].size == 2*step*n and feed.spans[0] == type(load.spans[0])(load.spans[0].address, load.spans[0].size, feed.spans[0].purpose)
            assert mac.macs == m*step*n and feed.cid in mac.deps
            assert commands['input'].cid in feed.deps and load.cid in feed.deps
            activation_coverage.append((feed.spans[1].address, feed.spans[1].size))
            if i:
                assert f'mac.c{core}.k{i-1:02}' in mac.deps
            if i >= 2:
                assert f'feed.c{core}.k{i-2:02}' in load.deps  # last SRAM reader before slot overwrite
                assert f'mac.c{core}.k{i-2:02}' in feed.deps  # RF slot reuse after prior MAC
                assert load.spans[0].address == commands[f'load.c{core}.k{i-2:02}'].spans[0].address
        assert activation_coverage == [(input_start+i*2*m*step, 2*m*step) for i in range(k//step)]
    rf = 2*(2*step*n + 2*m*step) + 4*m*n
    assert graph.metadata['rf_bytes_per_core'] == rf <= hw.rf_capacity
    assert max(s.address+s.size for c in graph.commands for s in c.spans) <= graph.metadata['sram_high_water_bytes'] <= hw.sram_capacity
    return {'workload': name, 'bank_color': color, 'work': expected, 'rf_bytes_per_core': rf,
            'alias_pairs_ordered': lifetime_audit(graph), 'source_dimensions': {'K': k, 'intermediate': official_i},
            'status': 'PASS', 'address_payload_execution_proved': False}


def audit_gdn(spec, cfg, color):
    hw = Hardware(); graph = build('qwen_gdn_state', color, hw); commands = {c.cid: c for c in graph.commands}
    d, heads, tokens = cfg['linear_key_head_dim'], len(spec['selected_value_heads']), spec['tokens']
    assert d == cfg['linear_value_head_dim'] == spec['Dk'] == spec['Dv'] == 128
    assert cfg['linear_num_value_heads'] == spec['source_value_heads'] == 32
    assert cfg['linear_num_value_heads']//cfg['linear_num_key_heads'] == 2
    assert spec['selected_value_heads'] == [0, 1] and spec['shared_source_key_head'] == 0
    state = 4*heads*d*d; prepared = 4*tokens*heads*(3*d+2); outputs = 4*tokens*heads*d
    assert spec['initial_state_bytes'] == spec['final_state_bytes'] == state
    assert spec['prepared_vector_bytes'] + spec['prepared_scalar_bytes'] == prepared
    assert spec['output_bytes'] == outputs and spec['full_layer_state_bytes'] == 4*32*d*d
    expected = {'commands': heads*(1+tokens*3), 'MACs': 0, 'modeled_vector_ops': heads*tokens*7*d*d,
                'external_bytes': state, 'local_read_bytes': tokens*state, 'local_write_bytes': tokens*state}
    assert work_signature(graph) == expected
    # MAC-equivalent report and exact scalar count use different conventions.
    assert spec['MAC_equivalent_reductions_and_outer_updates'] == 3*heads*tokens*d*d
    rf = 4*d*d + prepared//heads + outputs//heads
    assert graph.metadata['rf_bytes_per_core'] == rf <= hw.rf_capacity
    for head in range(heads):
        for t in range(tokens):
            read, compute, write = (commands[f'{prefix}{head}.{t}'] for prefix in ('state_read', 'delta', 'state_write'))
            assert read.cid in compute.deps and compute.cid in write.deps
            assert (f'state_init{head}' if not t else f'state_write{head}.{t-1}') in read.deps
    return {'workload': 'qwen_gdn_state', 'bank_color': color, 'work': expected,
            'rf_bytes_per_core': rf, 'alias_pairs_ordered': lifetime_audit(graph), 'status': 'PASS',
            'state_RF_residency_over_four_tokens_fits_capacity': True,
            'intermediate_SRAM_roundtrips_are_not_forced_by_capacity': True,
            'address_payload_execution_proved': False}


def existing_results_audit():
    """Read completed summaries only. Incomplete main runs are labelled a snapshot."""
    rows = []; by_workload = {}
    for path in sorted((R5/'results').glob('*__*.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        graph = build(data['workload'], data['selected_plan']['bank_color'], Hardware(**data['hardware']))
        work = work_signature(graph)
        for row in data['rows']:
            for result in row['results'].values():
                for key in ('external_bytes', 'local_read_bytes', 'local_write_bytes'):
                    assert result['metrics'][key] == work[key], (path.name, row['seed'], key)
        by_workload.setdefault(data['workload'], set()).add(json.dumps(work, sort_keys=True))
        rows.append({'file': str(path.relative_to(ROOT)), 'sha256': digest(path), 'backend': data['backend'],
                     'workload': data['workload'], 'policy_seed_rows': len(data['rows'])*3,
                     'work_signature': work, 'status': 'PASS'})
    assert all(len(values) == 1 for values in by_workload.values())
    return {'completed_summaries_at_audit': rows, 'completeness_claim': 'snapshot only; main experiment may still be running',
            'equal_coarse_request_work_claim': 'all observed backends match source graph bytes/MACs; latency/resources differ by design',
            'not_asserted': ['equal latency', 'same bank addresses across independently selected layouts', 'timed execution of numerical payloads']}


def main():
    specs = json.loads((R5/'full_width_specs.json').read_text()); numbers = json.loads((R5/'numerical_checks.json').read_text())
    q = json.loads((R5/'sources/qwen/config.json').read_text())['text_config']; f = json.loads((R5/'sources/flux/config.json').read_text())
    assert numbers['status'] == 'PASS' and numbers['datasets'] == 9 and numbers['comparisons'] == 18
    assert numbers['specs_sha256'] == digest(R5/'full_width_specs.json')
    assert numbers['source_sha256'] == specs['numerical_source_sha256'] == digest(R5/'numerical.py')
    for source in specs['source_files']:
        assert digest(ROOT/source['local_path']) == source['sha256']
    assert digest(R5/'sources/qwen/config.json') == digest(ROOT/'r4/sources/qwen/config.json')
    assert digest(R5/'sources/flux/config.json') == digest(ROOT/'r4/sources/flux/FLUX.2-klein-4B/transformer/config.json')
    numeric_rows = []
    for row in numbers['checks']:
        spec_name = next(name for name in ('qwen_projection', 'flux_projection', 'qwen_gdn') if specs[name]['case'] == row['case'])
        assert row['seed'] in specs['seeds'] and row['inputs_unchanged']
        for tensor in row['tensors'].values():
            assert math.prod(tensor['shape'])*(2 if tensor['storage_dtype'] == 'BF16' else 4) == tensor['logical_storage_bytes']
            assert len(tensor['sha256_little_endian_payload']) == 64
        if spec_name != 'qwen_gdn':
            s = specs[spec_name]; ts = row['tensors']; assert ts['x']['shape'] == [s['M'], s['K_full']]
            assert ts['packed_weight']['shape'] == [s['cores'], s['K_full'], s['packed_N_per_core']]
            assert ts['packed_weight']['logical_storage_bytes'] == s['logical_bytes']['weights_both_cores']
        else:
            assert row['tensors']['S_initial']['shape'] == [2, 128, 128]
            assert row['tensors']['S_final']['shape'] == [2,128,128] and row['tensors']['S_final']['logical_storage_bytes'] == 131072
            assert row['tensors']['o_all_tokens']['shape'] == [4,2,128] and row['tensors']['o_all_tokens']['logical_storage_bytes'] == 4096
        for entry in row.values():
            if isinstance(entry, dict) and 'max_error_over_allowed' in entry:
                assert entry['status'] == 'PASS' and entry['max_error_over_allowed'] <= 1
        numeric_rows.append({'case': row['case'], 'seed': row['seed'], 'status': 'REPORT_CONSISTENT_NOT_RERUN'})
    graph_rows = []
    for color in (0, 1, 3):
        graph_rows.append(audit_projection('qwen_projection', specs['qwen_projection'], q['hidden_size'], q['intermediate_size'], color))
        graph_rows.append(audit_projection('flux_projection', specs['flux_projection'], f['attention_head_dim']*f['num_attention_heads'], int(f['attention_head_dim']*f['num_attention_heads']*f['mlp_ratio']), color))
        graph_rows.append(audit_gdn(specs['qwen_gdn'], q, color))
    limitations = [
        'Projection preserves source full K and 64 gate+64 up/core, but excludes FFN down, norm/modulation producers, residual, attention/CFG and complete block/model.',
        'Projection shared input is externally loaded once, then read once per core; weights each transfer exactly once per Kstep, not whole-tensor repeated loads.',
        'Projection drain->SRAM->VPU read is an explicit engine-interface assumption; source mathematics alone does not require this traffic.',
        'GDN q/k/v/beta/g and four-token outputs are prepared/resident in private RF; their production, new-token timing and external transfer costs are excluded.',
        'GDN state begins external and pays one initial DMA; this is not a measured steady-state state-spill requirement.',
        'GDN RF budget 73760B/core permits keeping S across four tokens; modeled intermediate SRAM roundtrips are not forced by capacity, so baseline is bounded by this fixed lowering.',
        'Prepared four-token GDN inputs exclude real autoregressive inter-token execution and RF occupation by other layers; a four-token residency control is not a full-model decode claim.',
        'SwiGLU 8ops/element and MXU fill32cycles are performance-model conventions, not exact source operation costs or device calibration.',
        'Graph alias/RF lifetime proof and numerical math checks are separate; no numerical payload is executed by the timing model, and no official trained framework/production compiler/device acceptance is claimed.',
    ]
    result = {'status': 'PASS_WITH_COVERAGE_LIMITATIONS', 'source_graphs': graph_rows, 'numeric_report_checks': numeric_rows,
              'observed_performance_summaries': existing_results_audit(), 'limitations': limitations,
              'audited_file_sha256': {str(p.relative_to(ROOT)): digest(p) for p in (R5/'model.py', R5/'full_width_specs.json', R5/'numerical_checks.json', R5/'numerical.py', R5/'coarse_sim.py', R5/'resource_sim.py', Path(__file__))}}
    (R5/'source_contract_audit.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'graph_cases': len(graph_rows), 'numeric_reports': len(numeric_rows), 'completed_summaries': len(result['observed_performance_summaries']['completed_summaries_at_audit'])}))


if __name__ == '__main__':
    main()
