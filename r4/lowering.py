"""Source operations -> fixed engines, operand DMA packs, safe ping-pong memory.

The input is a source-transcribed scaled graph, not an exported production IR.
R3 Contract/Buffer/Task semantics remain authoritative. Public sim is unchanged.
"""
from dataclasses import dataclass, asdict, replace
import math
from sim.workload import Task, Edge, Workload, topology
from sim.memory import Buffer
from sim.compiler import Contract
from sim.hardware_model import Hardware


@dataclass(frozen=True)
class Target:
    name: str = 'two_core'
    cores: int = 2
    dma_bytes_cycle: float = 32
    sram_bytes_cycle_per_port: float = 64
    mxu_macs_cycle: float = 1024
    vpu_ops_cycle: float = 32
    memory_capacity: int = 4 * 1024 * 1024
    sram_ports: int = 2
    sram_binding: str = 'core'
    operand_slots: int = 2
    dma_startup: float = 8
    engine_startup: float = 1
    # This is an analytical aggregate tile demand, not cycle-accurate array use.
    compute_tile: tuple = (32, 32)

    def hardware(self, extra=0):
        return Hardware(window=128, byte_window=32768, issue_width=1,
            issue_cycle=1, dispatch_latency=1 + extra, completion_latency=1,
            wakeup_width=1, wakeup_cycle=1, memory_capacity=self.memory_capacity)


def align(x):
    return max(64, ((x + 63) // 64) * 64)


def reachability(workload):
    order = topology(workload)
    succ = {x: set() for x in order}
    for e in workload.edges:
        succ[e.producer].add(e.consumer)
    reaches = {x: set() for x in order}
    for x in reversed(order):
        for y in succ[x]:
            reaches[x].add(y)
            reaches[x].update(reaches[y])
    return reaches


def lower(case, target=Target()):
    values = case.evaluate()
    nodes = {n.name: n for n in case.nodes}
    assert len(nodes) == len(case.nodes)
    storage_widths = case.metadata.get('storage_bytes', {})
    # float64 is ONLY the reference evaluator. Storage is BF16 unless explicitly
    # state FP32; conversions/rounding and model quality are not modeled.
    widths = {k: storage_widths.get(k, 2) for k in values}
    sizes = {k: int(v.size) * widths[k] for k, v in values.items()}
    readers = {k: [] for k in values}
    writer = {}
    for n in case.nodes:
        for key in n.reads:
            readers[key].append(n.name)
        for key in n.writes:
            if key in writer or key in case.initial:
                raise ValueError('SSA tensor identity required')
            writer[key] = n.name
    initial_by_consumer = {}
    shared = []
    for key in case.initial:
        if len(readers[key]) == 1:
            initial_by_consumer.setdefault(readers[key][0], []).append(key)
        elif readers[key]:
            shared.append(key)
    tasks, task_tensors, annotations = [], {}, {}
    packs_by_core = {c: [] for c in range(target.cores)}

    def sram(core, engine='DMA'):
        port = core if target.sram_binding == 'core' else 2*core + int(engine != 'MXU')
        return f'cluster0.sram_port{port % target.sram_ports}'

    def dma(tid, keys, core, pack=False):
        count = sum(sizes[k] for k in keys)
        tasks.append(Task(tid, 'memory', ('cluster0.dma', sram(core)),
                          target.dma_startup + count / target.dma_bytes_cycle,
                          'cluster0', max(1, count)))
        task_tensors[tid] = list(keys)
        for key in keys:
            writer[key] = tid
        annotations[tid] = {'tensor_bytes': count, 'source': 'explicit SRAM-visible DMA',
                            'pack': pack, 'fixed_core': core, 'nominal_demand': tasks[-1].predicted}

    for i, key in enumerate(shared):
        core = nodes[readers[key][0]].core % target.cores
        dma(f'load.shared.{i}', [key], core)
    for n in case.nodes:
        core = n.core % target.cores
        if n.name in initial_by_consumer:
            tid = f'load.pack.{n.name}'
            dma(tid, initial_by_consumer[n.name], core, True)
            packs_by_core[core].append((tid, n.name))
        read_bytes = sum(sizes[k] for k in n.reads)
        write_bytes = sum(sizes[k] for k in n.writes)
        if n.engine == 'MXU+VPU':
            compute = n.macs / target.mxu_macs_cycle + n.vector_ops / target.vpu_ops_cycle
            engines = (f'core{core}.mxu', f'core{core}.vpu')
        elif n.engine == 'MXU':
            compute, engines = n.macs / target.mxu_macs_cycle, (f'core{core}.mxu',)
        elif n.engine == 'VPU':
            compute, engines = n.vector_ops / target.vpu_ops_cycle, (f'core{core}.vpu',)
        else:
            raise ValueError('unsupported source engine')
        scratch = case.metadata.get('internal_scratch', {}).get(n.name, {})
        internal_traffic = scratch.get('traffic_bytes', 0)
        demand = target.engine_startup + max(compute, (read_bytes + write_bytes + internal_traffic) / target.sram_bytes_cycle_per_port)
        ports = tuple(dict.fromkeys((sram(core, 'MXU'), sram(core, 'VPU')))) if n.engine == 'MXU+VPU' else (sram(core, n.engine),)
        tasks.append(Task(n.name, 'compute', engines + ports,
                          max(1.0, demand), 'cluster0', max(1, write_bytes)))
        task_tensors[n.name] = list(n.writes)
        annotations[n.name] = {'reads': list(n.reads), 'writes': list(n.writes), 'source': n.source,
            'fusion': n.fusion, 'macs': n.macs, 'vector_ops': n.vector_ops,
            'read_bytes': read_bytes, 'write_bytes': write_bytes, 'internal_scratch': scratch, 'fixed_core': core,
            'nominal_demand': demand, 'compute_demand': compute,
            'sram_demand': (read_bytes + write_bytes + internal_traffic) / target.sram_bytes_cycle_per_port}
    edges = {}
    for n in case.nodes:
        for key in n.reads:
            edges[(writer[key], n.name)] = Edge(writer[key], n.name, 'data')
    for packs in packs_by_core.values():
        for i, (tid, consumer) in enumerate(packs):
            if i >= target.operand_slots:
                old_writer, last_reader = packs[i - target.operand_slots]
                edges.setdefault((last_reader, tid), Edge(last_reader, tid, 'WAR'))
    workload = Workload(case.name, tuple(tasks), tuple(edges.values()),
        'Source-derived scaled numerical graph; operand packs and safe double buffering; fixed layout/mapping.')
    reaches = reachability(workload)
    buffer_readers = {t.tid: tuple(e.consumer for e in workload.edges if e.producer == t.tid and e.kind == 'data') for t in tasks}
    task_map = {t.tid: t for t in tasks}
    scratch_by_core = {core: max((case.metadata.get('internal_scratch', {}).get(n.name, {}).get('bytes', 0)
        for n in case.nodes if n.core % target.cores == core), default=0) for core in range(target.cores)}
    addresses, spans, next_address = {}, {}, sum(align(b) for b in scratch_by_core.values() if b)
    # Allocate two physical operand slots per core. A slot is not overwritten
    # until the former consumer FINISHES (explicit WAR completion).
    for core, packs in packs_by_core.items():
        for slot in range(target.operand_slots):
            group = [tid for i, (tid, _) in enumerate(packs) if i % target.operand_slots == slot]
            if group:
                size = max(align(task_map[tid].output_bytes) for tid in group)
                for tid in group:
                    addresses[tid], spans[tid] = next_address, size
                next_address += size
    # Other tensors reuse a span only if writer AND ALL actual readers precede
    # the new writer in the existing legal DAG; no static-only lifetime proof.
    slots = []
    for tid in topology(workload):
        if tid in addresses:
            continue
        size = align(task_map[tid].output_bytes)
        match = None
        for slot in slots:
            if slot['size'] >= size and all(not any(k in case.outputs for k in task_tensors[old]) and tid in reaches[old] and all(tid in reaches[r] for r in buffer_readers[old]) for old in slot['owners']):
                match = slot
                break
        if match is None:
            match = {'address': next_address, 'size': size, 'owners': []}
            slots.append(match)
            next_address += size
        addresses[tid], spans[tid] = match['address'], match['size']
        match['owners'].append(tid)
    buffers = tuple(Buffer(t.tid, 'cluster0', addresses[t.tid], spans[t.tid], buffer_readers[t.tid]) for t in tasks)
    cp = {}
    for tid in reversed(topology(workload)):
        cp[tid] = task_map[tid].predicted + max((cp[e.consumer] for e in workload.edges if e.producer == tid), default=0)
    contract = Contract(workload, buffers, cp, tuple(topology(workload)), {}, compiler_policy='r4_unselected')
    contract.validate(target.hardware())
    tensors = {}
    for tid, keys in task_tensors.items():
        offset = 0
        for key in keys:
            tensors[key] = {'shape': list(values[key].shape), 'layout': 'contiguous C; packed views in declared order',
                'storage_element_bytes': widths[key], 'bytes': sizes[key], 'address': addresses[tid] + offset,
                'writer': tid, 'readers': readers[key], 'last_reader_rule': 'pinned through invocation exit' if key in case.outputs else 'all listed readers complete before reuse',
                'live_out': key in case.outputs,
                'numeric_dtype': str(values[key].dtype), 'lifetime': 'writer dispatch through final reader completion'}
            offset += sizes[key]
    info = {'case_metadata': case.metadata, 'target': asdict(target), 'annotations': annotations,
        'tensors': tensors, 'task_tensors': task_tensors, 'sram_high_water_bytes': next_address,
        'unique_allocation_bytes': sum(align(t.output_bytes) for t in tasks), 'internal_scratch_bytes_by_core': scratch_by_core,
        'numeric_scope': 'float64 algebra/reordering; BF16/FP32 bytes are an unvalidated storage assumption',
        'tile_scope': 'each source node is a scaled aggregate tile; no full-width model tiling or compiler optimality claim'}
    return contract, info


def fixed_order(contract, order, name='static'):
    order = tuple(order)
    tasks = {t.tid: t for t in contract.workload.tasks}
    resource_order = {r: tuple(x for x in order if r in tasks[x].resources)
                      for t in tasks.values() for r in t.resources}
    return replace(contract, admission_order=order, resource_order=resource_order,
                   compiler_policy=name)
