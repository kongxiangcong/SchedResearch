"""Reformat observed search results and record the manual abstract-level triage."""
from pathlib import Path
import json
import re
import sys
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, r'C:\Users\72449\.agents\skills\paper-search\scripts')
from postprocess import dedup, rank

queries = ['multi core NPU runtime dynamic scheduling', 'accelerator dataflow task scheduling',
           'compiler dependency contract hardware completion dispatch']
raw = json.loads((ROOT/'literature/sources/paper_search_structured.json').read_text(encoding='utf-8'))
ranked, dropped = rank(dedup(raw), queries)
now = '2026-09-05'
manual = {
'HyperParallel-MoE': ('异构NPU的MoE training overlap','静态tile taskflow与event queues','在compiler中暴露通信/compute依赖','Ascend MoE训练',2),
'Supporting Dynamic Control-Flow': ('可重构processor的microcode控制流','循环/条件跳转/异常支持','让runtime reconfiguration支持更广程序','可重构处理器',1),
'TCL:': ('跨hardware的tensor程序调优成本','采样+Mamba cost model+持续蒸馏','减少调优数据与跨平台迁移成本','DL compiler',1),
'WITHDRAWN:': ('不确定到达的moldable gang tasks','动态选择时间和核数','non-work-conserving placement可改善makespan','multicore实时任务；已撤回',1),
'SegFold:': ('稀疏GEMM的reuse/负载冲突','小窗口动态reuse、partial work remapping','静态dataflow错过runtime稀疏结构','SpGEMM accelerator',2),
'Dynamic Task Scheduling for Heterogeneous': ('待核验：异构baseband任务','摘要未取得；不能仅凭标题认定机制','待核验','IIoT baseband',0),
'An Algorithm-Hardware': ('深GCN的计算与精度问题','dynamic pruning+hybrid dataflow','提前节点收敛可减工作量','GCN accelerator；不是固定DAG等价调度',1),
'InSS:': ('multiGPU online inference干扰与SLO','latency model+placement/resource/batch优化','显式估计共置干扰','GPU serving',1),
'Partitioned Scheduling': ('multiTPU实时gang inference可调度性','固定partition与统一parallelism level','严格分区避免scheduling anomalies','Edge TPU实时推理',1),
'MTST:': ('待核验：边缘transformer多任务','摘要未取得，保留后续候选','待核验','edge transformer accelerator',0),
'MHRC-Bench:': ('硬件repository代码补全评测','benchmark与标签','补齐HDL评测缺口','LLM代码生成；不相关',0),
'Tawa:': ('GPU异构单元编程与流水开销','aref+自动warp specialization','高层异步引用隐藏producer-consumer同步细节','LLM GPU kernels',2),
'From Principles to Practice': ('multi-core NPU LLM利用率','simulation+TP/core placement/PD优化','架构与serving策略协同','LLM多核NPU',2),
'DFTS-MCS:': ('待核验：mixed-criticality fault tolerance','摘要未取得','待核验','实时multicore',0),
'Design of Dynamic Scheduling Algorithm': ('multicore高负载调度','priority+IMCT+adaptive resource allocation','综合紧迫度/资源/依赖','PARSEC CPU任务',1),
'NektarIR:': ('异构HPC代码生成','domain IR到MLIR/LLVM','从领域操作生成不同hardware代码','有限元CFD；非NPU任务调度',0),
'ADS-CNN:': ('待核验：CNN dataflow调度','摘要未取得','待核验；不能把adaptive dataflow等同runtime OoO','FPGA CNN',0),
'Slark:': ('跨数据中心coflow信息受限','分布式agent与局部信息robust optimization','局部状态可减全局协调','coflow网络调度',1),
'DMDP:': ('prefetch预测覆盖与质量','多delta模式+runtime质量反馈','根据准确度及时性和污染调节预取','CPU预取；非task DAG',1),
'Predictive Age-Aware': ('manycore热/traffic不平衡导致aging','runtime任务remapping','平衡核心与通信使用','manycore可靠性',1),
'Dynamic Tuning of Core Counts': ('待核验：object runtime core count','摘要未取得','待核验','object-based runtime',0),
'FusionFrame:': ('待核验：DNN融合dataflow','摘要未取得','待核验','DNN compiler',0),
'Neural Channel': ('无线多用户channel状态与调度','neural CKM+stable matching','以历史信道预测减少开销','无线通信；非NPU执行',0),
'Multilayer Dataflow:': ('butterfly sparse attention访问不规则','混合稀疏network+streaming dataflow','数据复用与structured sparsity协同','attention accelerator',1),
'Generation of Compiler Backends': ('compiler backend开发与正确性','形式hardware模型+自动推理','从hardware语义自动生成backend','博士论文/FPGA编译',1),
'TT-QEC:': ('量子纠错低延迟','MLIR/Tensix kernel+抽象验证','host-free驻留执行','量子纠错；Blackhole结果为预测未实测',1),
'Differential Testing Solidity': ('Solidity compiler测试','Transformer contract生成+差分测试','自动制造compiler缺陷输入','区块链；不相关',0),
'Service Dependency Intelligence': ('企业service接口依赖','静态repository扫描graph','减少agent改动引发的API不一致','微服务软件；不相关',0),
'ONNXim:': ('多核NPU模拟速度/保真','确定compute+cycle DRAM/NoC','保留争用而抽象规则计算','NPU simulator',2),
'Icarus:': ('JIT实现安全','symbolic meta-execution','静态验证JIT生成程序集合','JavaScript JIT；非调度',0),
'Survival of the Fastest:': ('dataflow相同op实例HOL','扩展同op多实例OoO','跨操作OoO不等于跨实例OoO','dynamic HLS',2),
'Seal5:': ('RISC-V扩展compiler生成','ISA模型到LLVM patterns','减少工具链维护','ISA/compiler工具',0),
'Towards Scheduling of Pipelined': ('CPU-FPGA NN流水与循环graph','MLIR dataflow dialect+token scheduler','macro-dataflow跨外存流水','CPU-FPGA SoC',2),
'Hiring for An Uncertain Task:': ('economic contracts信息设计','优化激励合约算法','合约表达能力与求解复杂性','机制设计；不相关',0),
'Finding Missed Code Size': ('compiler missed optimization','LLM输入生成+差分测试','简化编译器测试','C/C++/Rust/Swift compiler；不相关',0),
'LLM4SecHW:': ('hardware debugging','领域LLM','自动debug知识','硬件安全；非任务调度',0),
'Dataflow-Reconfigurable CNN': ('待核验：CNN dataflow可重配','摘要未取得','待核验','CNN accelerator',0),
'Feature-Stationary': ('待核验：DiT data reuse','摘要未取得','不能凭题名认定runtime机制','DiT accelerator',0),
'Applications of Particle': ('粒子加速器应用','非计算体系结构','不相关','物理加速器',0),
'Accelerator Complex Evolution': ('Fermilab设施改造','非计算体系结构','不相关','粒子物理',0),
'Consideration of REBCO': ('muon磁体设计','非计算体系结构','不相关','粒子物理',0),
'Completion of the works': ('建筑合同条款','非计算体系结构','不相关','合同管理',0),
'FR-EAHTS:': ('待核验：multicore hierarchical调度','摘要未取得','待核验','多核调度',0),
'Dynamic Multi-Core Task': ('电网仿真任务调度','DRL与attention建模DAG','根据graph调任务优先级','power-grid simulation',1),
'Energy efficient dynamic': ('dependent实时任务能源','ASAP/ALAP mobility调度','时序slack支持能源优化','multicore实时系统',1),
'Dynamic Thermal-Aware': ('CPU温度控制','POD-Galerkin预测+dynamic TAS','降低热模型运行成本','multicore热管理',1),
'Dynamic Loop Fusion': ('irregular sibling loops依赖阻塞','monotonic address分析+runtime disambiguation','利用compiler约束免除地址history搜索','dynamic HLS',2),
}

def clean(x): return str(x if x is not None else '未知').replace('|','/').replace('\n',' ')
def info(p):
    for k,v in manual.items():
        if p['title'].lower().startswith(k.lower()): return v
    return ('未完成内容判读','待核验','待核验','待核验',0)

rows=['| # | Title | Date | Venue | Citations | Score | Sources |','|---|---|---|---|---|---|---|']
for i,p in enumerate(ranked,1):
    rows.append(f"| [{i}]({p['url']}) | {clean(p['title'])} | {clean(p.get('publication_date') or p.get('year'))} | {clean(p.get('venue'))} | {p.get('citation_count',0)} | {p.get('relevance_score',0)} | {','.join(p.get('found_in',[]))} |")
counts=', '.join(f'{k}={len(v)}' for k,v in raw.items())
unique=len(ranked); duplicates=sum(map(len,raw.values()))-unique
terms=['scheduling','dynamic','dataflow','compiler','multi-core']
freq=Counter({t:sum(t in p['title'].lower() for p in ranked) for t in terms})
accepted=[p for p in ranked if p.get('venue') and not any(t in (p.get('venue') or '').lower() for t in ['arxiv','ssrn']) and not p['title'].startswith('WITHDRAWN')]
top=sorted(accepted,key=lambda p:p.get('citation_count',0),reverse=True)[:5]
authors=Counter(); nums=Counter()
for p in ranked:
    if p.get('authors'):
        a=p['authors'][0];authors[a]+=p.get('citation_count',0);nums[a]+=1
topauthors=authors.most_common(5)
parts=[f'# 全量学术检索报告\n\n日期：{now}。包含全部返回项，未因低相关度、撤回或缺字段而隐藏条目；索引元数据未经全部逐项核验，不能当作可靠书目。',
       '## Display ALL results\n\n首次CLI运行：arxiv=15, dblp=0, open_alex=15, openreview=0, semantic_scholar=0, crossref=15；42 unique，3 cross-source duplicates。原始rank完整保存在 [stdout](sources/paper_search_2024_2026.stdout.txt)。',
       f'随后为了保存摘要结构化重跑相同3 queries/6 sources：{counts}；{unique} unique，{duplicates} duplicates；无 min-score 过滤。本表严格保持这次脚本的rank顺序。两次API结果不同是网络可用性变化，不能将新增条目误报为时间趋势。\n', '\n'.join(rows),
       '### Model Knowledge\n\n回忆来源仅用于补召回，随后全部查阅primary。它们是明确放宽年份的foundational追溯，不混进2024–2026 API计数。\n\n| Title | Year | Venue | Notes |\n|---|---|---|---|\n| [SPDI Scheduling for EDGE Architectures](https://www.cs.utexas.edu/~lin/papers/pact04.pdf) | 2004 | PACT | model-recall → 正文核验；静态mapping动态issue |\n| [VTA](https://arxiv.org/abs/1807.04188) | 2018/2019 | arXiv/IEEE Micro | model-recall → 正文核验；dependency queues |\n| [TaskStream](https://par.nsf.gov/servlets/purl/10320225) | 2022 | ASPLOS | model-recall → 正文核验；typed task hints |\n| [ASPEN](https://papers.neurips.cc/paper_files/paper/2023/hash/d899a31938c7838965b589d9b14a5ca6-Abstract-Conference.html) | 2023 | NeurIPS | model-recall → 正文核验；offline tile DAG、DSE |',
       '## Overview\n\nQueries：'+' / '.join(f'`{q}`' for q in queries)+f'。范围2024–2026，每query每source最多5项；第二次得到{unique}唯一项。源覆盖不完整，OpenReview 0并不能证明会议没有相关工作；摘要缺失项保留为待核验。关键词命中会带来粒子accelerator、经济contract等噪声。',
       '## Trends\n\n当前样本展示2025–2026的异构NPU taskflow、warp-specialization、跨核placement、稀疏动态dataflow与token编译等邻域。样本由关键词与每query限额决定，且SS/DBLP网络失败，不能据此推断发表数量增速、venue份额或研究热度。',
       '## Key themes\n\n- 静态异构taskflow与异步compiler：HyperParallel-MoE、Tawa、Towards Scheduling of Pipelined Dataflow Graphs in MLIR。\n- 多核NPU/serving建模：ONNXim、From Principles to Practice、Multi-TPU partitioning。\n- 动态dataflow粒度：SegFold、Survival of the Fastest、Dynamic Loop Fusion。\n- 更外层资源与实时调度：InSS、age-aware remapping、thermal-aware scheduling。\n- 检索噪声/不同语义：particle accelerators、economic contracts、Solidity testing；不进入本研究正面论证。',
       '## Keywords frequency\n\n只计title中substring出现的paper数，不是全文词频。\n\n| Keyword | Count |\n|---|---|\n'+'\n'.join(f'| {k} | {v} |' for k,v in freq.most_common()),
       '## Most cited by accepted paper\n\n以下按API的venue非预印本字段初筛，**不是逐篇验收录证明**；withdrawn剔除，citation snapshot可能错配。不能用此排名决定最危险prior art。\n\n| Rank | Title | Year | Citations |\n|---|---|---|---|\n'+'\n'.join(f"| {i} | [{clean(p['title'])}]({p['url']}) | {p.get('year')} | {p.get('citation_count')} |" for i,p in enumerate(top,1)),
       '## Most cited by first author\n\n仅聚合这次返回记录；作者字段来自API，含可能错误的聚合书目，未用于研究主结论。\n\n| Rank | Author | Papers in set | Total citations |\n|---|---|---|---|\n'+'\n'.join(f'| {i} | {clean(a)} | {nums[a]} | {n} |' for i,(a,n) in enumerate(topauthors,1)),
       '## Recommendations for reading\n\n1. SPDI：先掌握placement/issue的经典边界。\n2. VTA/Gemmini：理解self-timed跨engine并行与同queue重排的差异。\n3. TaskStream/ASPEN：审查typed hints与distributed ready机制的近邻。\n4. PipeThreader/TileLink：构造能流水通信和异构compute的强静态对手。\n5. LATTICE与openNVDLA2026：分别阻断memory contract和NPU硬件dependency dispatch的宽泛novelty。',
       '## 错误与检索限制\n\n错误逐字保留如下。系统locale造成的中文乱码保持原样；不将失败转换为“0篇已穷尽”。',
       '### 首次 CLI stderr\n\n```text\n'+(ROOT/'literature/sources/paper_search_2024_2026.stderr.txt').read_text(encoding='utf-8',errors='replace')+'\n```',
       '### 结构化运行 stderr\n\n```text\n'+(ROOT/'literature/sources/paper_search_structured.stderr.txt').read_text(encoding='utf-8',errors='replace')+'\n```',
       '## Metadata corrections\n\n- arXiv2607.17422当前为LATTICE v3，不使用旧DAN-Scheduler标题作为当前引用。\n- 支持Dynamic Control-Flow条目的arXiv日期是2026、DOI含2023；未把两者合并成“2026会议”。\n- 缺失year/abstract的Crossref条目未删，不能确认在时间窗内。\n- WITHDRAWN条目明确撤回，不用于支持结论。\n- 首次CLI和第二次结构化检索都未经完整原文核验；每条证据深度在step3和registry。']
(ROOT/'literature/search_report.md').write_text('\n\n'.join(parts),encoding='utf-8')

stepdir=ROOT/'literature/scoop_steps';stepdir.mkdir(exist_ok=True)
records=[f'# Step 3 — Abstract-Level Triage\n\n日期：{now}。状态：完成可取得摘要的初筛；无abstract条目标为未评分/待核验，0是保守临时值而非排除证明。所有API摘要原样保存在JSON。']
for i,p in enumerate(ranked,1):
    framing,mechanism,insight,domain,score=info(p)
    records.append(f"- **Paper {i}**\n  - Title: {p['title']}\n  - Date: {p.get('publication_date') or p.get('year') or '未知'}\n  - Problem framing: {framing}\n  - Core mechanism: {mechanism}\n  - Key insight: {insight}\n  - Application domain: {domain}\n  - Overlap score: {score}/4 {'（abstract缺失，临时值）' if not p.get('abstract') else '（abstract初筛）'}\n  - Source: {p['url']}；{','.join(p.get('found_in',[]))}")
records.append('## 定向web / model-recall补充\n\n7个正文候选的全部字段、机制与scope见以下正文记录（此段按同一4轴计分，不自动优待model recall）。')
red=(ROOT/'analysis/novelty_redteam.md').read_text(encoding='utf-8')
records.append(red[red.index('## Comparison result'):red.index('## R2 必须修改')])
(stepdir/'step3.md').write_text('\n\n'.join(records),encoding='utf-8')

steps={
1: ('Decompose the Novelty', red[red.index('## Decomposed claim'):red.index('## Structured papers')]),
2: ('Search and Deduplicate', '\n'.join(parts[:5])+'\n\n完整摘要：[structured JSON](../sources/paper_search_structured.json)。初次42、补采47；没有进行no-hit novelty inference。'),
4: ('Identify High-Potential Candidates', red[red.index('## Structured papers'):red.index('## Comparison result')]+'\n\nAPI中SegFold、Tawa、Survival等也符合≥2筛选；在7篇上限内优先取机制直接匹配/覆盖R2核心论点的条目。遗漏威胁保留在registry，不因上限被认定不相关。'),
5: ('Full-Paper Deep Dive', red[red.index('## Comparison result'):red.index('## R2 必须修改')]+'\n\n## Extraction log\n\n'+ '\n'.join(f'### {p.name}\n```text\n{p.read_text(encoding="utf-8",errors="replace")}\n```' for p in sorted((ROOT/'literature/sources').glob('*.fetch.log')))),
6: ('Compare Against Proposed Novelty',red[red.index('## Comparison result'):red.index('## R2 必须修改')]),
7: ('Articulate the Delta',red[red.index('## Verdict'):red.index('## Decomposed claim')]),
}
for n,(name,body) in steps.items():
    (stepdir/f'step{n}.md').write_text(f'# Step {n} — {name}\n\n日期：{now}。状态：完成当前限定scope；未取得全文的候选保留限制。\n\n'+body,encoding='utf-8')
(stepdir/'status.md').write_text('# Scoop-check进度\n\n2026-09-05。当前工具没有TaskCreate，使用文件记录7步。\n\n'+ '\n'.join(f'- Step {i}: completed，见step{i}.md。' for i in range(1,8))+'\n\nCompleted表示本轮筛选/记录完成，不表示文献穷尽或新颖性已证明。',encoding='utf-8')
print(f'wrote complete {unique}-paper search report, 7 step logs, status; {sum(bool(p.get("abstract")) for p in ranked)} abstracts available')
