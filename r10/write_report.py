"""Render derived R10 reports from preserved numeric evidence; no experiments."""
from pathlib import Path
import json,math,statistics
P=Path(__file__).resolve().parent
def read(p):return json.loads((P/p).read_text(encoding='utf8'))
def write(p,s):(P/p).write_text(s,encoding='utf8')
def f(x):return f'{x:.6f}'
def main():
    a=read('results/summary.json');b=read('causal_results/summary.json');rows=read('results/test_pairs.json');pairs=read('causal_results/test_pairs.json')
    aa=read('results/audit_results.json');ba=read('causal_results/audit_results.json');require=assert_pass
    require(aa);require(ba)
    boundary=[]
    for hw in ('EXT128','DMA32'):
        for session in (1,2):
            group=[r for r in rows if r['hardware']==hw and r['session']==session and r['condition']=='reserved35']
            r=max(group,key=lambda r:1-r['bounds']['tight']/r['elapsed']);lo=r['bounds']['tight'];hi=r['elapsed'];phase=r['phase'];period=8192.
            intervals=[[phase+i*period,phase+i*period+.35*period] for i in range(math.floor((lo-phase)/period)-1,math.ceil((hi-phase)/period)+1)]
            intervals=[v for v in intervals if v[1]>lo and v[0]<hi]
            boundary.append(dict(hardware=hw,session=session,block=r['block'],phase=phase,elapsed=hi,bounds=r['bounds'],gap_upper_pct=100*(1-lo/hi),blackouts_intersecting_bound_to_elapsed=intervals,trace=r['trace']))
    write('results/phase_boundary.json',json.dumps(boundary,indent=2)+'\n')
    t=['# R10 实验报告：下界收紧，动态空间仍未判明\n',
       'R10 已完成实施、独立计算复核与新相位确认。**证据支持“R9 大 gap 部分来自松下界”，未支持“联合静态已消除 gap”，也未支持新增机制。剩余空间继续 Refine。** 全部结果是自主参考合同的模拟周期；没有真实 TARS、实机 session、RTL 或 PPA 接受。\n',
       '## Research Question → Hypothesis\n',
       'R9 EXT128/DMA32 敏感性中的约16%–20%最大恢复上界，是松下界、静态不足还是动态可恢复空间？三种解释不互斥。R10 先检验串联 EXT→local DMA 与有限 credit 的必要等待，再检验静态参数交互，最后测试一个新登记的有限收费因果规则。R9 原有35%最大5.157867%的严格关闭门失败保持原判，未被R10重新解释为通过。\n',
       '## Strong Baseline 与合同\n',
       '`model.py` 与冻结 R9 模型逐字节相同。基础数值在 `reference_hardware.json`，两项独立覆盖在 `contract_delta.json` 及结果 registration：EXT128=(EXT128,DMA64)，DMA32=(EXT64,DMA32)，单位B/cycle。保持两cluster各两core；C1N只作局部控制。广播local两份照计，split-K通过同一个EXT写/读，源为共同row-major X/W，终点是全部Y外存可见。两种研究FP32算法许可、未物化每trace BF16乘加的边界均不变。\n',
       '每硬件960个注册静态候选全部合法：864个联合网格与R9原204项去重合并。联合交叉mapping、Ktile、广播、buffers/prefetch、resident-X、row/gather、xw/wx、outstanding；保留原reverse/full-K/C1N探针。每硬件8 train/8 validation新相位，train分组top4并集各29项进入validation。主候选仅C2N/C2K，C1N独立选择。Stage A两组各30配对块/条件，共360块；总34,358次Stage A模拟执行，非全静态最优证明。\n',
       '主选择均为C2K/K256/双buffer/prefetch2/gather/outstanding4/tile-X。quiet无广播、reverse；20%均广播且W先；35% EXT128为广播W先，DMA32为广播X先reverse。quiet与R9选择elapsed相同，reverse不应解释为收益。比较中的“旧静态”是R9敏感性已选方案在R10新相位重新执行，不是复用旧延迟轨迹。\n',
       '## Discriminative Experiment A：下界与静态\n',
       '新增三项必要条件与R9资源下界取max：逐packet串联最小credit占用总量/Q；DAG关键路径放松；每段EXT停供期内，至多Q个已持有credit的read packet能继续贡献local服务。后者显式把write-local全部放松为免费，避免错误地声称停供时local完全不能工作。证明见 `bound_proof.md`。独立checker用禁用local服务尾段的补集积分，与runner的capacity二分实现不同；不读某policy的等待trace。所有上界均固定graph/Q；不能当跨mapping全局下界。\n',
       '以下每格30个独立paired blocks。静态增益是实际elapsed变化；其他列只是免费恢复上界，不能相加或称为已实现收益。旧上界与新上界列均先固定旧static，以隔离下界收紧；末列才用于新static。\n',
       '| 硬件/背景/session | 旧静态原上界均值% | 旧静态新上界均值% | 联合静态实际增益% [95% CI] | 新静态新上界均值/最大% |\n|---|---:|---:|---:|---:|\n']
    for hw in ('EXT128','DMA32'):
        for c in ('reserved20','reserved35'):
            for s in (1,2):
                v=a[f'{hw}.s{s}.{c}'];g=v['static_gain_pct'];u=v['new_tight_upper_pct']
                t.append(f"| {hw}/{c}/s{s} | {f(v['old_aggregate_upper_pct']['mean'])} | {f(v['old_tight_upper_pct']['mean'])} | {f(g['mean'])} [{f(g['ci95_t'][0])}, {f(g['ci95_t'][1])}] | {f(u['mean'])}/{f(u['max'])} |\n")
    t += ['\nEXT128 的下界松弛得到明显确认；DMA32 的收紧较小，35%尤甚。DMA32/20%的W先静态改善约0.106%，两个session的名义95% CI下界均>0，但35%无改善；这只支持一个很小的compiler参数效应，不能解释原大gap。CI未作多重比较校正。EXT128的静态差分CI均跨0，个别大正/负phase保留，不择优报告。\n',
          '35%边界检查继续保留：四个hardware/session的最大上界及与[L,T]相交的绝对预留区间已写入 `results/phase_boundary.json`，相位0/8191（包括负起点预留段）另有fixture。所有背景/session均仍有>5%的已测上界，严格逐block关闭门失败；没有连续phase域证明。\n',
          '## Discriminative Experiment B：有限收费因果规则\n',
          'Stage A确认仍有空间后、Stage B运行前登记 `causal_plan.md`。固定使用A已选static；B另用8/8/30/30个新相位（1110000–1140000 seeds），不与A或R9重用。train/validation只有固定规则诊断，不调参、不选择另一个policy。96个诊断配对、360个独立test配对，所有test baseline/causal详细轨迹都保存。\n',
          '仅在EXT序号64–67中最多观察四次，每次实际收费2cycle；若默认read面向busy local，而另一个cluster的read head面向idle local，则至多改序一次再收费8cycle。无未来相位、baseline trace、graph criticality或末决策回看。所有费用都在服务前计入并重算后续事件，观察失败也收费。Python模型保留原全局trace计数器；规则的等价控制状态只需要饱和至68的7bit计数器和done bit，未实现RTL或PPA。\n',
          f"**关键限制：{sum(r['action_applied'] for r in pairs)}/360个test块实际触发改序。** 所有块只执行四次观察并支付8cycle。审计确认另一侧busy的观察数为{ba['other_busy_samples']}/{ba['observations']}。因此这批结果是固定观察/触发规则的失败，不能用来声称已对实际DMA改序价值做了有效负面确认。少量正gain也只能来自观察延迟改变后续排队与绝对相位，不能归因于一次未发生的改序。\n",
          '| 硬件/背景/session | 收费净elapsed增益均值% | 95% paired CI |\n|---|---:|---:|\n']
    for hw in ('EXT128','DMA32'):
        for c in ('quiet','reserved20','reserved35'):
            for s in (1,2):
                v=b[f'{hw}.test_s{s}.{c}'];t.append(f"| {hw}/{c}/s{s} | {f(v['mean'])} | [{f(v['ci95_t'][0])}, {f(v['ci95_t'][1])}] |\n")
    t += ['\n两个hardware均未过≥5%净gain与正CI下界的机制门。quiet最大回退EXT128为0.027226%、DMA32为0.013897%，虽≤1%，其余必要条件失败，不能据此接受机制。保留固定规则的所有负值和未触发结果，不在同批test上改阈值或追正例。模拟session不等于实机session。\n',
          '## Result → Red-team → Accept / Refine / Reject\n',
          f"独立计算审计通过：A {aa['traces']} traces / {aa['requests']:,} requests / {aa['operations']:,} compute-reduce；B {ba['traces']} traces / {ba['requests']:,} requests / {ba['operations']:,} compute-reduce，共{aa['traces']+ba['traces']}条详细轨迹。A所有新static测试、每格首块旧static与C1N做完整trace审计；旧static其余块只保存数值，全部下界由代表graph独立重算，不能声称这些未保存trace也逐request审计过。B全部360 baseline/action对都逐request审计。\n",
          '新增30个bound/改序/两序两相位tiny fixtures通过，两个错误bound检出；B漏收观察费故障检出。tiny终点仍仅local-visible，非完整主图最优证明。checker是独立计算实现，不是另一位研究员或实机验收；没有使用subagent。详细攻击面与未决见 `redteam_report.md`。\n',
          '- **Accept（条件性）**：停供期有限credit造成的串联供给约束确实解释了部分松上界；960项静态/新相位执行及独立核验闭环有效。DMA32/20%有很小的静态参数效应。\n',
          '- **Reject（具名规则）**：本轮四次busy/idle观察规则达到5%净收益的主张；触发器没有产生实际改序，不能进入最小硬件机制/PPA探索。\n',
          '- **Refine（核心未决）**：剩余约10%–13%的平均上界仍可能含下界松弛、有限静态遗漏或动态空间。没有证明全部不可避免供给，也没有证明存在这么大的可恢复收益。后续应先建立带完整compute→外存Y终点的有限credit两资源顺序松弛/小规模exact证书，并核验实际可触发且会改变尾部的观测；任何新规则必须新登记、新相位，不复用本轮test调参。R5通用ready仍关闭。\n',
          '## 复验与历史\n\n```powershell\npython -X utf8 -B r10/check_results.py\npython -X utf8 -B r10/independent_check.py\npython -X utf8 -B r10/check_causal.py\npython -X utf8 -B r10/check_tests.py\npython -X utf8 -B r9/check_results.py\npython -X utf8 -B r8/check_history.py\npython -X utf8 -B r8/check_results.py\n```\n',
          '完整重跑A用 `python -X utf8 -B r10/run_experiment.py --output r10/reproduction_new --workers 4`，runner拒绝已有目录。重放全部A/B测试用 `python -X utf8 -B r10/replay_results.py --output r10/replay_new.json`，共1,440次重新执行并逐项比较elapsed，拒绝覆盖回执；这是同引擎可重复性，不冒充独立模拟器。B原runner只供首跑，默认输出目录已经存在，不应直接覆盖。仅复核优先用checkers。模型/runner host秒数是脚本耗时，不是NPU性能。历史648个R9 named artifacts、R1–R8与根README保持原样；R10父快照与新lineage独立保存，根进度只追加。目录非Git仓库，无commit/push。\n']
    write('experiment_report.md',''.join(t))
def assert_pass(x):assert x['status']=='PASS'
if __name__=='__main__':main()
