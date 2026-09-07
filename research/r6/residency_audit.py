"""Source-shape/lifetime arithmetic, not a performance or target-memory model."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    spec_path = ROOT/'r5/full_width_specs.json'
    specs = json.loads(spec_path.read_text(encoding='utf8'))
    for item in specs['source_files']:
        assert digest(ROOT/item['local_path']) == item['sha256']
    config_path = ROOT/'r4/sources/qwen/config.json'
    config = json.loads(config_path.read_text(encoding='utf8'))['text_config']
    layer_types = config['layer_types']
    layers = [i for i, kind in enumerate(layer_types) if kind == 'linear_attention']
    heads = config['linear_num_value_heads']
    dk, dv = config['linear_key_head_dim'], config['linear_value_head_dim']
    fp32_bytes = 4
    state_head = dk*dv*fp32_bytes
    state_layer = heads*state_head
    total = len(layers)*state_layer
    assert len(layer_types) == config['num_hidden_layers'] == 32
    assert (len(layers), heads, dk, dv) == (24,32,128,128)
    assert state_layer == specs['qwen_gdn']['full_layer_state_bytes']
    assert 2*state_head == specs['qwen_gdn']['initial_state_bytes']
    result = {
        'evidence_level': 'source-derived exact storage arithmetic, batch=1 FP32 recurrent-state contract; no target execution',
        'hypothesis': 'R5 two-head prepared-token residency cannot establish full autoregressive RF residency',
        'source_hashes': {'r4/sources/qwen/config.json':digest(config_path), 'r5/full_width_specs.json':digest(spec_path)},
        'batch':1, 'layers':len(layer_types), 'gdn_layer_indices':layers,
        'value_heads_per_gdn_layer':heads, 'Dk':dk,'Dv':dv,
        'state_bytes_per_head':state_head,'state_bytes_per_gdn_layer':state_layer,
        'state_bytes_all_gdn_layers':total,'state_MiB_all_gdn_layers':total/2**20,
        'r5_two_head_state_bytes':2*state_head,
        'r5_prepared_tokens':4,
        'r5_assumed_RF_bytes_per_core':128*1024,
        'r5_assumed_core_count':2,
        'full_layer_state_to_r5_total_RF_ratio':state_layer/(2*128*1024),
        'all_gdn_state_to_r5_total_RF_ratio':total/(2*128*1024),
        'same_layer_next_token_interval': {
            'layer_forward_steps':len(layer_types),
            'intervening_other_layer_forwards':len(layer_types)-1,
            'assumption':'ordinary serial autoregressive generation using the frozen implementation; no speculative/known-future inputs',
            'excludes':'remaining same-layer operators, final norm/logits/sample and next-token embedding time',
        },
        'target_RF_capacity_bytes':None,
        'target_RF_capacity_unknown_reason':'Phoenix RF accessibility/capacity for this kernel and compiler allocation not obtained',
        'target_required_external_state_traffic_bytes':None,
        'target_traffic_unknown_reason':'capacity arithmetic does not determine actual hierarchy residency, spills, precision, placement, or transfer counts',
        'verdict':'REJECT direct full-model extrapolation; REFINE real compiler lifetime/allocation contract',
        'limits':['Not all 48 MiB must be in RF; other memory levels and sharding are legal.',
                  '48 MiB excludes conv state, attention KV, activations, weights and operator scratch.',
                  'R5 RF capacity is a research assumption, not Phoenix hardware capacity.',
                  'No latency, throughput, energy, or mandatory external-traffic conclusion.']
    }
    out = ROOT/'r6/residency_audit.json'
    out.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2))

if __name__ == '__main__':
    main()
