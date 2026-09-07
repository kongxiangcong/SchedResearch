"""R11 independent full-module numerical fixtures; no simulator import or timing.

BF16-packed external dense weights/hidden, explicit FP32 intermediate permission.
Two separate arithmetic paths: tiled FP32 production/recurrence/output and untiled
FP64 source-algebra oracle. Synthetic weights, no official optimized kernel run.
"""
from __future__ import annotations

import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import argparse
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np

ROOT = Path(__file__).resolve().parent
CONTRACT = json.loads((ROOT / 'contract.json').read_text(encoding='utf8'))
H, D, NH, NK, T = 2560, 128, 32, 16, 4
EPS = 1e-6
TOL_REF = CONTRACT['numeric']['fp32_reference_tolerance']
TOL_VARIANT = CONTRACT['numeric']['same_lowering_tolerance']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def packed_bf16(x):
    return (np.asarray(x, dtype=np.float32).view(np.uint32) >> 16).astype('<u2')


def bf16(x):
    z = np.asarray(x, dtype=np.float32)
    assert np.isfinite(z).all()
    bits = z.view(np.uint32)
    return ((bits + np.uint32(0x7fff) + ((bits >> 16) & 1)) & np.uint32(0xffff0000)).view(np.float32)


def record(x, storage='FP32'):
    x = np.asarray(x)
    assert np.isfinite(x).all()
    payload = packed_bf16(x).tobytes() if storage == 'BF16' else x.astype('<f4').tobytes()
    if storage == 'BF16':
        assert np.all((x.view(np.uint32) & 0xffff) == 0)
    return {'shape': list(x.shape), 'storage_dtype': storage,
            'logical_bytes': len(payload), 'sha256': digest(payload),
            'minimum': float(x.min()), 'maximum': float(x.max()),
            'nonzero_elements': int(np.count_nonzero(x))}


def compare(actual, reference, tolerance):
    assert actual.shape == reference.shape
    assert np.isfinite(actual).all() and np.isfinite(reference).all()
    error = np.abs(actual.astype(np.float64) - reference.astype(np.float64))
    allowed = tolerance['atol'] + tolerance['rtol'] * np.abs(reference.astype(np.float64))
    result = {'status': 'PASS' if np.all(error <= allowed) else 'FAIL',
              'elements': actual.size, 'max_abs_error': float(error.max(initial=0)),
              'max_error_over_allowed': float(np.max(error / allowed, initial=0)), **tolerance}
    if result['status'] != 'PASS':
        raise AssertionError(result)
    return result


def weights():
    rng = np.random.default_rng(CONTRACT['numeric']['weights_seed'])
    result = {}
    for name, k, n in (('qkv', H, 8192), ('z', H, 4096), ('b', H, 32),
                       ('a', H, 32), ('out', 4096, H)):
        result[name] = bf16(rng.normal(0, 1 / np.sqrt(k), (k, n)).astype(np.float32))
    result['conv'] = bf16(rng.normal(0, 0.25, (8192, 4)).astype(np.float32))
    result['A_log'] = rng.uniform(-3, -1, (NH,)).astype(np.float32)
    result['dt_bias'] = rng.uniform(-1, 0, (NH,)).astype(np.float32)
    result['norm'] = rng.uniform(0.8, 1.2, (D,)).astype(np.float32)
    return result


def fixture(seed):
    rng = np.random.default_rng(seed)
    return {
        'hidden': bf16(rng.normal(0, 0.3, (T, H)).astype(np.float32)),
        'state_initial': rng.normal(0, 0.03, (NH, D, D)).astype(np.float32),
        'conv_initial': rng.normal(0, 0.2, (8192, 4)).astype(np.float32),
    }


def tiled_projection(x, weight):
    """K128 ascending, N64, FP32 accumulation after each K tile."""
    assert x.dtype == weight.dtype == np.float32
    result = np.empty((len(x), weight.shape[1]), dtype=np.float32)
    for n in range(0, weight.shape[1], 64):
        width = min(64, weight.shape[1] - n)
        acc = np.zeros((len(x), width), dtype=np.float32)
        for k in range(0, weight.shape[0], 128):
            acc += x[:, k:k + 128] @ weight[k:k + 128, n:n + width]
        result[:, n:n + width] = acc
    return result


def prepare32(x, cache, w):
    qkv = tiled_projection(x, w['qkv'])
    z = tiled_projection(x, w['z']).reshape(len(x), NH, D)
    a = tiled_projection(x, w['a'])
    b = tiled_projection(x, w['b'])
    history = cache.copy()
    convolved = []
    for t in range(len(x)):
        history = np.concatenate((history[:, 1:], qkv[t, :, None]), axis=1)
        y = np.sum(history * w['conv'], axis=1, dtype=np.float32)
        convolved.append(y / (np.float32(1) + np.exp(-y)))
    mixed = np.stack(convolved)
    q = mixed[:, :2048].reshape(len(x), NK, D)
    k = mixed[:, 2048:4096].reshape(len(x), NK, D)
    v = mixed[:, 4096:].reshape(len(x), NH, D)
    q = q / np.sqrt(np.sum(q*q, axis=-1, keepdims=True, dtype=np.float32) + np.float32(EPS))
    q = np.repeat(q / np.float32(np.sqrt(D)), 2, axis=1)
    k = np.repeat(k / np.sqrt(np.sum(k*k, axis=-1, keepdims=True, dtype=np.float32) + np.float32(EPS)), 2, axis=1)
    beta = np.float32(1) / (np.float32(1) + np.exp(-b))
    g = -np.exp(w['A_log']) * np.logaddexp(np.float32(0), a + w['dt_bias'])
    return {'q': q, 'k': k, 'v': v, 'beta': beta, 'g': g, 'z': z,
            'conv_final': history, 'mixed_qkv': mixed}


def recurrence32(p, initial, value_tile, order):
    """Actual 32-head payload execution, with selected static traversal."""
    states = np.empty((len(p['q']), NH, D, D), dtype=np.float32)
    output = np.empty((len(p['q']), NH, D), dtype=np.float32)
    state = initial.copy()
    coordinates = ((t, h) for h in range(NH) for t in range(len(p['q']))) if order == 'head' else (
        (t, h) for t in range(len(p['q'])) for h in range(NH))
    for t, h in coordinates:
        decay = np.exp(p['g'][t, h])
        for v0 in range(0, D, value_tile):
            block = state[h, :, v0:v0 + value_tile] * decay
            prediction = np.sum(block * p['k'][t, h, :, None], axis=0, dtype=np.float32)
            delta = (p['v'][t, h, v0:v0 + value_tile] - prediction) * p['beta'][t, h]
            block += p['k'][t, h, :, None] * delta[None, :]
            output[t, h, v0:v0 + value_tile] = np.sum(
                block * p['q'][t, h, :, None], axis=0, dtype=np.float32)
            state[h, :, v0:v0 + value_tile] = block
        states[t, h] = state[h]
    return output, states


def gated32(core, z, w):
    variance = np.mean(core * core, axis=-1, keepdims=True, dtype=np.float32)
    normalized = core / np.sqrt(variance + np.float32(EPS))
    return (normalized * w['norm']) * (z / (np.float32(1) + np.exp(-z)))


def oracle64(x, initial, cache, w):
    """Independent untiled dense+temporal-window+matrix recurrence source oracle."""
    x = x.astype(np.float64)
    projected = x @ w['qkv']
    z = (x @ w['z']).reshape(len(x), NH, D)
    beta = 1 / (1 + np.exp(-(x @ w['b'])))
    g = -np.exp(w['A_log']) * np.logaddexp(0, x @ w['a'] + w['dt_bias'])
    history = np.concatenate((cache.astype(np.float64), projected.T), axis=1)
    mixed = np.empty_like(projected)
    for t in range(len(x)):
        conv = np.einsum('cf,cf->c', history[:, t + 1:t + 5], w['conv'])
        mixed[t] = conv / (1 + np.exp(-conv))
    qraw, kraw = mixed[:, :2048].reshape(len(x), NK, D), mixed[:, 2048:4096].reshape(len(x), NK, D)
    q = np.repeat(qraw / np.sqrt(np.einsum('thk,thk->th', qraw, qraw)[..., None] + EPS) / np.sqrt(D), 2, axis=1)
    k = np.repeat(kraw / np.sqrt(np.einsum('thk,thk->th', kraw, kraw)[..., None] + EPS), 2, axis=1)
    values = mixed[:, 4096:].reshape(len(x), NH, D)
    current = initial.astype(np.float64).copy()
    outputs, states = [], []
    for t in range(len(x)):
        decayed = current * np.exp(g[t])[:, None, None]
        pred = np.matmul(k[t, :, None, :], decayed).squeeze(1)
        correction = beta[t, :, None] * (values[t] - pred)
        current = decayed + np.matmul(k[t, :, :, None], correction[:, None, :])
        outputs.append(np.matmul(q[t, :, None, :], current).squeeze(1))
        states.append(current.copy())
    core = np.stack(outputs)
    rms = np.sqrt(np.einsum('thv,thv->th', core, core)[..., None] / D + EPS)
    gated = core / rms * w['norm'] * z / (1 + np.exp(-z))
    final = gated.reshape(len(x), NH * D) @ w['out']
    return {'core_outputs': core, 'states_every_token': np.stack(states), 'module_outputs': final,
            'conv_final': history[:, -4:], 'q': q, 'k': k, 'v': values, 'beta': beta, 'g': g, 'z': z}


def check_block(seed, w32, w64, outdir):
    f = fixture(seed)
    input_records = {name: record(x, 'BF16' if name == 'hidden' else 'FP32') for name, x in f.items()}
    p = prepare32(f['hidden'], f['conv_initial'], w32)
    reference = oracle64(f['hidden'], f['state_initial'], f['conv_initial'], w64)
    preparation_checks = {name: compare(p[name], reference[name], TOL_REF)
                          for name in ('q', 'k', 'v', 'beta', 'g', 'z', 'conv_final')}
    variants = []
    core_reference = state_reference = None
    gated = []
    for tile in (32, 64, 128):
        for order in ('head', 'token'):
            core, states = recurrence32(p, f['state_initial'], tile, order)
            if core_reference is None:
                core_reference, state_reference = core.copy(), states.copy()
            checks = {
                'all_core_outputs_vs_fp64': compare(core, reference['core_outputs'], TOL_REF),
                'all_states_vs_fp64': compare(states, reference['states_every_token'], TOL_REF),
                'all_core_outputs_vs_first_lowering': compare(core, core_reference, TOL_VARIANT),
                'all_states_vs_first_lowering': compare(states, state_reference, TOL_VARIANT),
            }
            variants.append({'value_tile': tile, 'order': order, 'checks': checks,
                             'core_outputs': record(core), 'state_final': record(states[-1]),
                             'states_every_token': [record(s) for s in states]})
            gated.append(gated32(core, p['z'], w32).reshape(T, NH * D))
    # Batch independent variants to reduce interpreter overhead. K/N tile and
    # accumulation order remain identical for every individual output row.
    all_module = tiled_projection(np.concatenate(gated), w32['out']).reshape(6, T, H)
    for i, variant in enumerate(variants):
        variant['checks']['all_module_outputs_vs_fp64'] = compare(all_module[i], reference['module_outputs'], TOL_REF)
        variant['checks']['all_module_outputs_vs_first_lowering'] = compare(all_module[i], all_module[0], TOL_VARIANT)
        variant['module_outputs'] = record(all_module[i])
    assert input_records == {name: record(x, 'BF16' if name == 'hidden' else 'FP32') for name, x in f.items()}
    path = outdir / f'prefill_{seed}.npz'
    np.savez_compressed(path, hidden_bf16=packed_bf16(f['hidden']), module_outputs=all_module[0],
                        core_outputs=core_reference, state_final=state_reference[-1], conv_final=p['conv_final'])
    return {'seed': seed, 'status': 'PASS', 'inputs': input_records, 'input_unchanged': True,
            'preparation_checks': preparation_checks, 'variants': variants,
            'payload_file': path.relative_to(ROOT).as_posix(), 'payload_sha256': digest(path.read_bytes())}


def next_hidden_callback(seed, completed_outputs, completion_records):
    # The callback is invoked only after the preceding complete module output
    # and final caches exist. It does not receive pre-generated future inputs.
    token = len(completed_outputs)
    assert token >= 1 and len(completion_records) == token
    previous = completed_outputs[-1]
    rng = np.random.default_rng(np.random.SeedSequence([seed, token, 0xA11]))
    return bf16(np.float32(0.3) * np.tanh(previous) + rng.normal(0, 0.2, (H,)).astype(np.float32))


def check_decode(seed, w32, w64, outdir):
    f = fixture(seed)
    hidden = f['hidden'][:1].copy()
    initial32, cache32 = f['state_initial'].copy(), f['conv_initial'].copy()
    initial64, cache64 = initial32.astype(np.float64), cache32.astype(np.float64)
    completed, records, states, core_all, hidden_all = [], [], [], [], []
    for token in range(T):
        if token:
            hidden = next_hidden_callback(seed, completed, records)[None, :]
        hidden_all.append(hidden.copy())
        p = prepare32(hidden, cache32, w32)
        core, state = recurrence32(p, initial32, 64, 'head')
        output = tiled_projection(gated32(core, p['z'], w32).reshape(1, NH * D), w32['out'])
        ref = oracle64(hidden, initial64, cache64, w64)
        checks = {'module_output': compare(output, ref['module_outputs'], TOL_REF),
                  'core_output': compare(core, ref['core_outputs'], TOL_REF),
                  'state': compare(state, ref['states_every_token'], TOL_REF),
                  'conv': compare(p['conv_final'], ref['conv_final'], TOL_REF)}
        initial32, cache32 = state[-1], p['conv_final']
        initial64, cache64 = ref['states_every_token'][-1], ref['conv_final']
        completed.append(output[0].copy())
        states.append(initial32.copy())
        core_all.append(core[0].copy())
        records.append({'token': token, 'release_after_completed_tokens': token,
                        'hidden': record(hidden, 'BF16'), 'module_output': record(output),
                        'state': record(initial32), 'conv': record(cache32), 'checks': checks,
                        'callback_reads_future_hidden': False})
    path = outdir / f'decode_{seed}.npz'
    np.savez_compressed(path, hidden_bf16=packed_bf16(np.concatenate(hidden_all)),
                        module_outputs=np.stack(completed), core_outputs=np.stack(core_all),
                        state_final=states[-1], conv_final=cache32)
    return {'seed': seed, 'status': 'PASS', 'invocations': records,
            'initial_state': record(f['state_initial']), 'initial_conv': record(f['conv_initial']),
            'payload_file': path.relative_to(ROOT).as_posix(), 'payload_sha256': digest(path.read_bytes()),
            'scope': 'synthetic post-output callback enforces causal availability; not execution of other model layers or token sampling'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    outdir = ROOT / 'numerical_data'
    outdir.mkdir(exist_ok=True)
    started = time.perf_counter()
    s = CONTRACT['splits']
    seeds = (list(range(s['train_start'], s['train_start'] + s['train_n'])) +
             list(range(s['validation_start'], s['validation_start'] + s['validation_n'])) +
             list(range(s['test_A_start'], s['test_A_start'] + s['test_n_per_group'])) +
             list(range(s['test_B_start'], s['test_B_start'] + s['test_n_per_group'])))
    if args.smoke:
        seeds = seeds[:1]
    w32 = weights()
    weight_records = {name: record(x, 'BF16' if name in ('qkv', 'z', 'b', 'a', 'out', 'conv') else 'FP32')
                      for name, x in w32.items()}
    w64 = {name: x.astype(np.float64) for name, x in w32.items()}
    rows = []
    for seed in seeds:
        row = check_block(seed, w32, w64, outdir)
        rows.append(row)
        print(json.dumps({'prefill_seed': seed, 'status': 'PASS', 'completed': len(rows), 'total': len(seeds)}), flush=True)
    decode_seeds = [s['train_start']] if args.smoke else [s['train_start'], s['validation_start'], s['test_A_start'], s['test_B_start']]
    decode = []
    for seed in decode_seeds:
        decode.append(check_decode(seed, w32, w64, outdir))
        print(json.dumps({'decode_seed': seed, 'status': 'PASS'}), flush=True)
    assert weight_records == {name: record(x, 'BF16' if name in ('qkv', 'z', 'b', 'a', 'out', 'conv') else 'FP32')
                              for name, x in w32.items()}
    checks = [check for row in rows for variant in row['variants'] for check in variant['checks'].values()]
    result = {'status': 'PASS', 'smoke': args.smoke, 'evidence_level': 'source-semantic complete GDN module synthetic numerical execution; separate from timing',
              'source_sha256': digest(Path(__file__).read_bytes()), 'contract_sha256': digest((ROOT / 'contract.json').read_bytes()),
              'official_source_sha256': digest((ROOT.parent / CONTRACT['source']['implementation']).read_bytes()),
              'runtime': {'python': platform.python_version(), 'numpy': np.__version__},
              'numeric_contract': CONTRACT['numeric'], 'weights': weight_records, 'weights_unchanged': True,
              'prefill_blocks': len(rows), 'variant_checks': len(checks), 'prefill': rows,
              'decode_blocks': len(decode), 'decode': decode,
              'max_abs_error': max(c['max_abs_error'] for c in checks),
              'max_error_over_allowed': max(c['max_error_over_allowed'] for c in checks),
              'wall_seconds_numerical_only': time.perf_counter() - started,
              'limitations': [
                  'No trained weights, official Transformers/FLA execution, target device or simulator arithmetic.',
                  'Source-semantic FP32 intermediates; source BF16 cast boundaries are intentionally not emulated.',
                  'Official prefill uses chunk algebra; tested static sequential recurrence is the same source recurrence semantics, not that optimized implementation.',
                  'All 76 preregistered prefill blocks checked; strict-AR callback checked on four disjoint split representatives.',
                  'Trace arithmetic is not materialized; performance uses common shape/cost and links these checked input payload identities.'
              ]}
    target = ROOT / ('numerical_smoke_results.json' if args.smoke else 'numerical_results.json')
    target.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps({'status': 'PASS', 'file': target.name, 'prefill_blocks': len(rows), 'decode_blocks': len(decode),
                      'max_abs_error': result['max_abs_error'], 'seconds': result['wall_seconds_numerical_only']}), flush=True)


if __name__ == '__main__':
    main()
