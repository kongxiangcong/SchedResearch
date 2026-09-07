"""Full-width source slices and explicit staged commands.

Qwen/FLUX projection output axes are tiles, not reduced hidden dimensions.
This is a research compiler contract, not production llm_sched export.
"""
from dataclasses import dataclass, asdict, replace
import hashlib
import json
from pathlib import Path


@dataclass(frozen=True)
class Span:
    address: int
    size: int
    purpose: str


@dataclass(frozen=True)
class Command:
    cid: str
    engine: str
    core: int
    kind: str  # dma / read / write / compute
    deps: tuple
    spans: tuple = ()
    cycles: float = 0
    macs: int = 0
    ops: int = 0
    source: str = ''


@dataclass(frozen=True)
class Graph:
    name: str
    commands: tuple
    metadata: dict

    def validate(self, hw):
        ids={c.cid for c in self.commands}
        assert len(ids)==len(self.commands)
        seen=set()
        for c in self.commands:
            assert set(c.deps)<=seen, ('not topological',c.cid,c.deps)
            seen.add(c.cid)
            assert c.kind in ('dma','read','write','compute')
            for s in c.spans:
                assert s.address>=0 and s.address%hw.granule==0
                assert s.size>0 and s.address+s.size<=hw.sram_capacity
        assert self.metadata['rf_bytes_per_core']<=hw.rf_capacity


@dataclass(frozen=True)
class Hardware:
    name: str = 'request'
    granule: int = 256
    dma_commands: int = 2
    outstanding: int = 16
    return_slots: int = 8
    request_issue: float = 1
    external_latency: float = 64
    external_bw: float = 32
    fabric_bw: float = 64
    fabric_latency: float = 2
    banks: int = 8
    sram_bw: float = 128
    local_outstanding: int = 8
    mxu_macs_cycle: float = 1024
    vpu_ops_cycle: float = 32
    dispatch: float = 1
    issue_cycle: float = 1
    notification: float = 1
    sram_capacity: int = 4*1024*1024
    rf_capacity: int = 128*1024
    bank_arbitration: str = 'ready_bank'


@dataclass(frozen=True)
class Plan:
    order: tuple
    bank_color: int = 0
    dma_spacing: float = 0
    name: str = ''


QWEN='https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py'
FLUX='https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/model.py'


def projection(name, k, m, color=0, hw=Hardware()):
    n,kt=128,128
    assert k%kt==0
    stages=k//kt
    input_bytes=m*k*2
    source=QWEN if name.startswith('qwen') else FLUX
    commands=[Command('input','dma',0,'dma',(),(Span(0,input_bytes,'shared BF16 input full K'),),source=source)]
    # Data is blocked [Kstep, M, 128], preserving all K. The numerical checker
    # uses the same mathematical slices. Each SRAM weight buffer has two slots.
    slotsize=kt*n*2
    weight_base=((input_bytes+4095)//4096)*4096
    output_base=weight_base+4*(slotsize+4096)
    for i in range(stages):
        for core in range(2):
            slot=i%2
            addr=weight_base+(core*2+slot)*(slotsize+4096)+core*color*hw.granule
            load=f'load.c{core}.k{i:02}'
            feed=f'feed.c{core}.k{i:02}'
            mac=f'mac.c{core}.k{i:02}'
            loaddeps=() if i<2 else (f'feed.c{core}.k{i-2:02}',)
            commands.append(Command(load,'dma',core,'dma',loaddeps,(Span(addr,slotsize,'BF16 fused gate/up weight K tile'),),source=source))
            feeddeps=('input',load)+(() if i<2 else (f'mac.c{core}.k{i-2:02}',))
            commands.append(Command(feed,f'feed{core}',core,'read',feeddeps,
                (Span(addr,slotsize,'weight SRAM to ping-pong RF'),Span(i*m*kt*2,m*kt*2,'shared input K tile')),
                source=source))
            macdeps=(feed,)+(() if not i else (f'mac.c{core}.k{i-1:02}',))
            macs=m*kt*n
            commands.append(Command(mac,f'mxu{core}',core,'compute',macdeps,
                cycles=macs/hw.mxu_macs_cycle+32,macs=macs,source=source))
    for core in range(2):
        outaddr=output_base+core*65536
        commands.append(Command(f'drain{core}',f'feed{core}',core,'write',(f'mac.c{core}.k{stages-1:02}',),
            (Span(outaddr,m*n*4,'FP32 accumulated projection output'),),source=source))
        commands.append(Command(f'actread{core}',f'feed{core}',core,'read',(f'drain{core}',),
            (Span(outaddr,m*n*4,'FP32 gate/up to VPU'),),source=source))
        commands.append(Command(f'swiglu{core}',f'vpu{core}',core,'compute',(f'actread{core}',),
            cycles=8*m*(n//2)/hw.vpu_ops_cycle,ops=8*m*(n//2),source=source))
        commands.append(Command(f'out{core}',f'feed{core}',core,'write',(f'swiglu{core}',),
            (Span(outaddr+32768,m*(n//2)*4,'FP32 SwiGLU live-out'),),source=source))
    meta={'K':k,'M':m,'fused_N_per_core':n,'cores':2,'Kstep':kt,'Ksteps':stages,
        'weight_bytes':2*k*n*2,'input_bytes':input_bytes,'weight_macs':2*m*k*n,
        'rf_bytes_per_core':2*(slotsize+m*kt*2)+m*n*4,
        'sram_high_water_bytes':output_base+65536+32768+m*(n//2)*4,
        'source':source,'bank_color':color,'dtype':'BF16 inputs/weights, FP32 accumulation/output',
        'scope':'full source hidden K; output tile contains64 gate+64 up per core; includes all K steps, excludes FFN down and rest of block',
        'layout':'input[Kstep,M,128], weight[Kstep,128,128]; two SRAM slots + two RF slots/core; accumulation order K ascending',
        'lifetime':'SRAM weight slot last reader=feed; RF slot last reader=mac; input throughout; final output pinned',
        'compute_model':'32 cycle fill per K tile plus MAC/1024, explicit SRAM->RF feed overlaps previous MAC using two RF slots; hypothetical BF16 target'}
    graph=Graph(name,tuple(commands),meta);graph.validate(hw);return graph


def recurrent(color=0,hw=Hardware()):
    d,tokens=128,4
    size=d*d*4
    commands=[]
    for core in range(2):
        addr=core*(size+4096)+core*color*hw.granule
        commands.append(Command(f'state_init{core}','dma',core,'dma',(),(Span(addr,size,'full FP32 state head'),),source=QWEN))
    for t in range(tokens):
        for core in range(2):
            addr=core*(size+4096)+core*color*hw.granule
            deps=(f'state_init{core}',) if t==0 else (f'state_write{core}.{t-1}',)
            commands.append(Command(f'state_read{core}.{t}',f'feed{core}',core,'read',deps,(Span(addr,size,'S key128 x value128'),),source=QWEN))
            commands.append(Command(f'delta{core}.{t}',f'vpu{core}',core,'compute',(f'state_read{core}.{t}',),
                cycles=7*d*d/hw.vpu_ops_cycle,ops=7*d*d,source=QWEN))
            commands.append(Command(f'state_write{core}.{t}',f'feed{core}',core,'write',(f'delta{core}.{t}',),
                (Span(addr,size,'updated S visible before next token'),),source=QWEN))
    meta={'heads':2,'key_dim':d,'value_dim':d,'tokens':tokens,'source':QWEN,'bank_color':color,
        'state_bytes':2*size,'state_external_bytes':2*size,'state_local_traffic_bytes':2*2*tokens*size,
        'rf_bytes_per_core':size+tokens*(3*d+2)*4+tokens*d*4,'sram_high_water_bytes':2*(size+4096),
        'dtype':'FP32 state and prepared inputs','scope':'two real-size value heads and4 sequential tokens; prepared q/k/beta/g/v resident in private RF; excludes projection/conv/norm and full layer',
        'prepared_vector_bytes_per_core':tokens*(3*d+2)*4,
        'lifetime':'state in-place writer ordered after all preceding token readers/compute; new-token input availability is an assumption for this state micrograph',
        'compute_model':'7D^2 add/mul ops per head token, exp/qk-normalization precomputed; output dot included, output vector RF live-out'}
    graph=Graph('qwen_gdn_state',tuple(commands),meta);graph.validate(hw);return graph


def build(name,color=0,hw=Hardware()):
    if name=='qwen_projection':
        return projection(name,2560,1,color,hw)
    if name=='flux_projection':
        return projection(name,3072,32,color,hw)
    if name=='qwen_gdn_state':
        return recurrent(color,hw)
    raise ValueError(name)


def bursts(command,hw):
    result=[]
    for s in command.spans:
        for offset in range(0,s.size,hw.granule):
            result.append((s.address+offset,min(hw.granule,s.size-offset)))
    return result


def source_manifest():
    root=Path(__file__).resolve().parents[1]
    paths=list((root/'r5').glob('*.py'))
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
