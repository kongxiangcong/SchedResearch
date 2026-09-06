"""R11 static FIFO graph. No imports from historic implementations."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
C = json.loads((ROOT / 'contract.json').read_text())
H = C['hardware']
D, HEADS, HIDDEN = 128, 32, 2560
STATE = HEADS * D * D * 4
CONV = 8192 * 4 * 4
PARAM = CONV + 64 * 4 + 128 * 4
WEIGHTS = 2 * (2560 * 12352 + 4096 * 2560)


def rf_peak(tile, depth, tokens):
    recurrence = depth * (128 * tile * 4 + tokens * ((256 + tile + 2) * 4 + tile * 4)) + 4096
    projection = depth * (128 * 64 * 4 + tokens * 128 * 4) + tokens * 64 * 4
    return max(recurrence, projection, 65536)


def plans(variant):
    return [dict(variant=variant, tile=v, depth=p, order=o,
                 name=f'{variant}-v{v}-p{p}-{o}')
            for v in (32, 64, 128) for p in (1, 2)
            for o in (('head', 'token') if variant == 'baseline' else ('head',))
            if rf_peak(v, p, 4) <= H['rf_bytes_per_core']]


class Builder:
    def __init__(self, plan, mode):
        self.plan, self.mode = plan, mode
        self.cmd, self.last = [], {}
        m = 4 if mode == 'prefill' else 1
        sizes = [('state', STATE), ('conv_state', CONV), ('small_params', PARAM),
                 ('hidden', m * 2560 * 2), ('raw_projection', m * 12352 * 4),
                 ('prepared', m * HEADS * (3 * D + 2) * 4),
                 ('core_output', m * HEADS * D * 4), ('normalized', m * HEADS * D * 4),
                 ('module_output', m * 2560 * 4), ('weight_slots', 4 * 128 * 64 * 2)]
        self.allocations = []
        base = 0
        for name, size in sizes:
            base = (base + 255) // 256 * 256
            self.allocations.append(dict(name=name, base=base, size=size))
            base += size
        self.vmem_peak = base
        assert base <= H['vmem_bytes']

    def add(self, res, kind, category, deps=(), size=0, ops=0, macs=0, **extra):
        deps = list(deps)
        if res != 'BARRIER' and res in self.last:
            deps.append(self.last[res])
        deps = sorted(set(x for x in deps if x is not None))
        i = len(self.cmd)
        assert all(x < i for x in deps)
        self.cmd.append(dict(id=i, res=res, kind=kind, category=category,
                             deps=deps, bytes=int(size), ops=int(ops), macs=int(macs), **extra))
        if res != 'BARRIER':
            self.last[res] = i
        return i

    def barrier(self, deps, category):
        return self.add('BARRIER', 'barrier', category, deps)

    def project(self, width, kdim, m, start, label, input_dtype):
        # Full source widths; pack a/b into one 64-column output tile, no missing work.
        done = start
        for wave in range((width // 64 + 1) // 2):
            prev_mac, rf_owner, vmem_owner = [done, done], {}, {}
            for k in range(kdim // 128):
                for core in range(2):
                    col = wave * 2 + core
                    if col >= width // 64:
                        continue
                    slot = k % self.plan['depth']
                    key = (core, slot)
                    load = self.add('EXT', 'transfer', label + '_weight',
                                    (done, vmem_owner.get(key)), 128 * 64 * 2,
                                    core=core, slot=slot, wave=wave, k=k)
                    feed = self.add('LOCAL', 'transfer', label + '_feed',
                                    (load, rf_owner.get(key)),
                                    128 * 64 * 2 + m * 128 * input_dtype,
                                    core=core, slot=slot, wave=wave, k=k)
                    unpack = self.add(f'VPU{core}', 'compute', label + '_unpack',
                                      (feed,), ops=128 * 64 + (m * 128 if input_dtype == 2 else 0))
                    mac = self.add(f'MXU{core}', 'compute', label + '_mac',
                                   (unpack, prev_mac[core]), macs=m * 128 * 64,
                                   core=core, wave=wave, k=k)
                    prev_mac[core], rf_owner[key], vmem_owner[key] = mac, mac, feed
            drains = []
            for core in range(2):
                if wave * 2 + core < width // 64:
                    drains.append(self.add('LOCAL', 'transfer', label + '_output',
                                           (prev_mac[core],), m * 64 * 4, core=core))
            done = self.barrier(drains, label + '_wave_visible')
        return done

    def prepare(self, m, start):
        ends = []
        for group in range(16):
            core = group % 2
            # One Q/K pair and two V heads: 512 convolution channels, 4 gate scalars/token.
            read = self.add('LOCAL', 'transfer', 'prepare_read', (start,),
                            size=m * 512 * 4 + 2 * 512 * 4 * 4 + m * 4 * 4 + 4 * 4,
                            group=group, core=core)
            # conv: 4 mul + 3 add/channel; SiLU 16+3; qk norm (sq/add, rsqrt16, scale), q scale;
            # beta sigmoid16+3; g softplus16+2 + exp(A)16 + mul + exp(g)16.
            ops = m * (512 * 26 + 256 * 3 + 2 * 16 + 128 + 2 * (19 + 18 + 16 + 1 + 16))
            comp = self.add(f'VPU{core}', 'compute', 'prepare_compute', (read,), ops=ops, group=group)
            wr = self.add('LOCAL', 'transfer', 'prepare_write', (comp,),
                          size=m * 2 * (3 * D + 2) * 4 + 512 * 4 * 4, group=group)
            ends.append(wr)
        return self.barrier(ends, 'prepared_visible')

    def recur(self, m, start, variant):
        tile, depth = self.plan['tile'], self.plan['depth']
        if variant == 'resident':
            jobs = [(h, v, tuple(range(m))) for h in range(16) for v in range(128 // tile)]
        elif self.plan['order'] == 'head':
            jobs = [(h, v, (t,)) for h in range(16) for t in range(m) for v in range(128 // tile)]
        else:
            jobs = [(h, v, (t,)) for t in range(m) for h in range(16) for v in range(128 // tile)]
        state_last, slot_last, loaded, ends = {}, {}, {}, []

        def load_job(j):
            h, v, ts = jobs[j]
            slot = j % depth
            ret = []
            for core in range(2):
                key = (2 * h + core, v)
                a = self.add('LOCAL', 'transfer', 'state_read',
                             (start, state_last.get(key), slot_last.get((core, slot))),
                             128 * tile * 4, head=key[0], value_tile=v, tokens=list(ts), slot=slot)
                b = self.add('LOCAL', 'transfer', 'recurrence_operands', (a,),
                             len(ts) * (256 + tile + 2) * 4, head=key[0], value_tile=v,
                             tokens=list(ts), slot=slot)
                ret.append(b)
            loaded[j] = ret

        for j, (h, v, ts) in enumerate(jobs):
            if j not in loaded:
                load_job(j)
            # Prefetch next independent job pair, never a version not yet written.
            if depth == 2 and j + 1 < len(jobs):
                nh, nv, _ = jobs[j + 1]
                if (nh, nv) != (h, v) and j + 1 not in loaded:
                    load_job(j + 1)
            prev = loaded[j]
            for t in ts:
                comps = [self.add(f'VPU{core}', 'compute', 'recurrence_compute',
                                  (prev[core],), ops=7 * 128 * tile,
                                  head=2 * h + core, token=t, value_tile=v, tile=tile)
                         for core in range(2)]
                prev = [self.add('LOCAL', 'transfer', 'recurrence_output', (comps[core],),
                                 tile * 4, head=2 * h + core, token=t, value_tile=v)
                        for core in range(2)]
            for core in range(2):
                key = (2 * h + core, v)
                wr = self.add('LOCAL', 'transfer', 'state_write', (prev[core],), 128 * tile * 4,
                              head=key[0], value_tile=v, tokens=list(ts), slot=j % depth)
                state_last[key], slot_last[(core, j % depth)] = wr, wr
                ends.append(wr)
        return self.barrier(ends, 'recurrence_visible')

    def norm(self, m, start):
        ends = []
        for head in range(HEADS):
            core = head % 2
            read = self.add('LOCAL', 'transfer', 'norm_read', (start,), m * 128 * 8 + 128 * 4,
                            head=head)
            # RMS(sum sq/div/eps/rsqrt), scale norm-weight, SiLU(z) and multiply gate.
            ops = m * (128 * 25 + 18)
            op = self.add(f'VPU{core}', 'compute', 'norm_compute', (read,), ops=ops)
            ends.append(self.add('LOCAL', 'transfer', 'norm_write', (op,), m * 128 * 4, head=head))
        return self.barrier(ends, 'norm_visible')

    def module(self, m, start, variant, invocation):
        incoming = [self.add('EXT', 'transfer', category, (start,), size=size, invocation=invocation)
                    for category, size in [('state_load', STATE), ('conv_load', CONV),
                                           ('parameter_load', PARAM), ('hidden_load', m * 2560 * 2)]]
        ready = self.barrier(incoming, 'module_inputs_visible')
        proj = self.project(12352, 2560, m, ready, 'input_projection', 2)
        prepared = self.prepare(m, proj)
        recur = self.recur(m, prepared, variant)
        normalized = self.norm(m, recur)
        out = self.project(2560, 4096, m, normalized, 'output_projection', 4)
        finish = [self.add('EXT', 'transfer', category, (out,), size=size, invocation=invocation)
                  for category, size in [('state_store', STATE), ('conv_store', CONV),
                                         ('module_output_store', m * 2560 * 4)]]
        return self.barrier(finish, 'module_return_and_RF_clobber')

    def build(self):
        prev = None
        for invocation in range(1 if self.mode == 'prefill' else 4):
            # Candidate canonicalizes at strict release/clobber boundary: m=1 has no reuse.
            variant = self.plan['variant'] if self.mode == 'prefill' else 'baseline'
            prev = self.module(4 if self.mode == 'prefill' else 1, prev, variant, invocation)
        return dict(commands=self.cmd, allocations=self.allocations,
                    metadata=dict(plan=self.plan, mode=self.mode, vmem_peak=self.vmem_peak,
                                  rf_peak=rf_peak(self.plan['tile'], self.plan['depth'],
                                                  4 if self.mode == 'prefill' else 1),
                                  state_bytes=STATE, dense_weight_bytes_per_invocation=WEIGHTS,
                                  output_bytes=4 * 2560 * 4,
                                  evidence='static shape/traffic graph, not timed tensor arithmetic'))


def build(plan, mode='prefill'):
    return Builder(plan, mode).build()


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def metrics(graph):
    bycat, byres = {}, {}
    for c in graph['commands']:
        bycat[c['category']] = bycat.get(c['category'], 0) + c['bytes']
        byres[c['res']] = byres.get(c['res'], 0) + c['bytes']
    return dict(bytes_by_category=bycat, bytes_by_resource=byres,
                ops=sum(c['ops'] for c in graph['commands']),
                macs=sum(c['macs'] for c in graph['commands']),
                commands=len(graph['commands']))


def qualifications():
    rows = []
    for variant in ('baseline', 'resident'):
        for p in plans(variant):
            g = build(p)
            m = metrics(g)
            assert m['macs'] == 4 * 42106880
            assert sum(c['ops'] for c in g['commands'] if c['category'] == 'recurrence_compute') == 4 * 32 * 7 * 128 * 128
            cat = m['bytes_by_category']
            assert cat['state_read'] + cat['state_write'] == (8 if variant == 'baseline' else 2) * STATE
            assert cat['state_load'] + cat['state_store'] == 2 * STATE
            assert g['metadata']['rf_peak'] <= H['rf_bytes_per_core']
            rows.append(dict(plan=p, graph_sha256=digest(g), metrics=m,
                             capacity=g['metadata'], eligible=True))
    # Same complete invocation ABI, canonical finite static plans on both sides.
    p = plans('baseline')[0]
    a = build(p, 'decode')
    b = build(dict(p, variant='resident', name=p['name'].replace('baseline', 'resident')), 'decode')
    assert a['commands'] == b['commands']
    return dict(status='PASS', prefill=rows,
                decode=dict(status='EXCLUDED_NO_INTERVENTION', equal_commands=True,
                            graph_sha256=digest(a['commands']), metrics=metrics(a),
                            proof='Four output-visible invocation boundaries; all RF/VMEM clobbered; every head state read and written each token. Other caller time is not modeled.'))

