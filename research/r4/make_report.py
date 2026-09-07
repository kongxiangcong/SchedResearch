"""Generate the R4 result narrative and figure from frozen saved samples."""
from pathlib import Path
import csv
import gzip
import hashlib
import json
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'experiments/results/r4'
R4=ROOT/'r4'


def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    assert manifest['status']=='complete'
    for rel,digest in manifest['source_hashes'].items():
        assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==digest, rel
    rows=list(csv.DictReader((OUT/'summary.csv').open(encoding='utf-8')))
    for r in rows:
        for k in ('latency_mean','latency_p95','paired_reduction_pct','ci95_low','ci95_high'):
            r[k]=float(r[k])
    b=[r for r in rows if r['policy']=='B2']
    by={(r['config'],r['policy']):r for r in rows}
    positive=sum(r['paired_reduction_pct']>1e-8 for r in b)
    gate=[r for r in b if r['paired_reduction_pct']>=5 and r['ci95_low']>0]
    s8faster=sum(by[(r['config'],'S8')]['latency_mean'] < by[(r['config'],'S')]['latency_mean']-1e-8 for r in b)
    exact=json.loads((OUT/'exact_probe.json').read_text())
    interventions=json.loads((OUT/'counterfactual_summary.json').read_text())
    improved=sum(r['reduction_cycles']>1e-8 for r in interventions)
    worsened=sum(r['reduction_cycles']<-1e-8 for r in interventions)
    numerical=json.loads((OUT/'numeric_schedule_checks.json').read_text())
    error=max(v for r in numerical for v in r['max_abs_error'].values())
    probe_rows=list(csv.DictReader((OUT/'priority_probe/summary.csv').open(encoding='utf-8')))
    charged=[r for r in probe_rows if r['policy']=='B_order2']
    probe_best=max(charged,key=lambda r:float(r['paired_reduction_pct']))
    probe_positive=sum(float(r['paired_reduction_pct'])>1e-8 for r in charged)
    probe_manifest=json.loads((OUT/'priority_probe/manifest.json').read_text())
    probe_text=f'''### 3.1 后验修正：让动态priority跟随优化静态

主B采用原始critical-path priority，而S已通过离线搜索改变资源序。为排除可修复的hint不匹配，另运行 **70×32×2={probe_manifest['executions']:,}次**：先用nominal确定环境回放S，把dispatch全序转成静态priority，再按相同地址/工作/外部环境测试B_order0/B_order2。所有hint在读取test评分前冻结；这仍是看到主结果后的后验校正，不是新硬件或独立确认实验。

B_order0为10正/33负/27零；收费B_order2为{probe_positive}正/{len(charged)-probe_positive}负，最高 **{float(probe_best['paired_reduction_pct']):+.3f}%**，配对95%区间 **[{float(probe_best['ci95_low']):+.3f},{float(probe_best['ci95_high']):+.3f}]%**，仍无5%门通过。这个最高行是 `{probe_best['config']}`。修正hint显著减少部分退化，说明原始负值不能全归于动态机制固有缺陷；但没有改变本轮暂不扩硬件的决定。[完整校正汇总](../experiments/results/r4/priority_probe/summary.csv)、[独立来源/参数清单](../experiments/results/r4/priority_probe/manifest.json)

红队另对主B0两处约0.10%小正例做训练trace静态修复：只用12训练B trace导出额外固定资源序，再由8 validation选择。每配置得到2个unique候选，最终仍选原S，未消除微小正值；这不证明全图静态最优。[后验静态探针](../experiments/results/r4/redteam_static_probe.json)

主实验与priority校正合计 **{manifest['executions']+probe_manifest['executions']:,}次执行**，不把训练搜索或tiny枚举混入该总数。主420与校正140个seed0调度数值检查分开保存，全部通过。
'''
    selected=[r for r in b if r['group'] in ('main','fusion_conditioning_sensitivity')]
    stat_lines=[]
    for r in selected:
        s=by[(r['config'],'S')];b0=by[(r['config'],'B0')];h=by[(r['config'],'H2')]
        stat_lines.append(f"| {r['case']} | {r['mode']} | {s['latency_mean']:.2f} | {b0['paired_reduction_pct']:+.3f}% | {r['paired_reduction_pct']:+.3f}% [{r['ci95_low']:+.3f},{r['ci95_high']:+.3f}] | {h['paired_reduction_pct']:+.3f}% |")
    # Inspect actual per-seed traces for opportunity/cost summaries.
    metrics=[]
    for conf in manifest['configurations']:
        path=OUT/f"{conf['id']}.traces.jsonl.gz"
        with gzip.open(path,'rt',encoding='utf-8') as f:
            for line in f:
                x=json.loads(line)
                metrics.append({'config':conf['id'],'group':conf['group'],'mode':conf['mode'],'case':conf['case'],
                    'seed':x['seed'],'policy':x['label'],'latency':x['latency'],**x['metrics']})
    opportunity=[m for m in metrics if m['policy']=='S']
    nonzero=sum(m['opportunity_union_cycles']>1e-8 for m in opportunity)
    inverted=sum(m['ready_order_inversions']>0 for m in opportunity)
    perconfig=[]
    for r in b:
        ms=[m for m in opportunity if m['config']==r['config']]
        bms=[m for m in metrics if m['config']==r['config'] and m['policy']=='B2']
        perconfig.append({'config':r['config'], 'static_opportunity_union_mean':statistics.mean(m['opportunity_union_cycles'] for m in ms),
            'static_opportunity_fraction_mean':statistics.mean(m['opportunity_union_cycles']/m['latency'] for m in ms),
            'static_inversion_rate_mean':statistics.mean(m['ready_order_inversion_rate'] for m in ms),
            'B2_abstract_state_bits':bms[0]['abstract_state_bits'],
            'descriptor_bytes_estimate':bms[0]['descriptor_bytes_estimate'],
            'static_order_metadata_bytes':bms[0]['resource_order_bytes'],
            'B2_ready_queue_peak':max(m['ready_queue_peak'] for m in bms),
            'B2_wakeup_queue_peak':max(m['wakeup_queue_peak'] for m in bms),
            'B2_completion_queue_peak':max(m['completion_queue_peak'] for m in bms),
            'B2_issue_utilization_mean':statistics.mean(m['issue_service_utilization'] for m in bms),
            'B2_wakeup_utilization_mean':statistics.mean(m['wakeup_service_utilization'] for m in bms),
            'B2_candidate_checks_mean':statistics.mean(m['candidate_checks'] for m in bms),
            'B2_resource_utilization_mean':{resource:statistics.mean(m['resource_utilization'][resource] for m in bms) for resource in bms[0]['resource_utilization']}})
    (OUT/'opportunity_cost_summary.json').write_text(json.dumps(perconfig,indent=2),encoding='utf-8')
    best=max(b,key=lambda r:r['paired_reduction_pct'])
    worst=min(b,key=lambda r:r['paired_reduction_pct'])
    conclusion=('收费 B2 未有配置通过预登记5%证据门，暂不扩展有限总事件硬件。' if not gate else '存在通过数值门的配置，但缩尺与未校准服务仍阻止真实硬件结论。')
    report=f'''# R4 阶段实验报告：先检验真实来源子图的剩余机会

日期：2026-09-05。**{conclusion}** 本轮完成官方版本核验→真实源码缩尺图→独立数值检查→强化静态→实际仿真→独立红队闭环。这里“真实来源”指官方计算结构可追溯；并非完整4B形状、真实训练权重或真实NPU性能。

## 1. 本轮完成与主结果

- 7种源图边界（4基础、3 attention/conditioning 优化），共 **{len(b)}配置 × {len(manifest['test_seeds'])}独立test seeds × 6策略 = {manifest['executions']:,}次**主执行。所有执行完整trace保存在压缩JSONL，合同、地址、shape、各tensor bytes/readers、搜索候选与源hash一并冻结。
- 收费B2相对S：{positive}个配置mean为正，{sum(r['paired_reduction_pct'] < -1e-8 for r in b)}负，{sum(abs(r['paired_reduction_pct'])<=1e-8 for r in b)}零；通过5%且区间下界>0门槛的配置 **{len(gate)}**。这是重叠合成配置的计数，不是模型总体胜率。
- 最大B2改善为 **{best['paired_reduction_pct']:+.3f}%**（`{best['config']}`），最差 **{worst['paired_reduction_pct']:+.3f}%**（`{worst['config']}`）。完整零成本增量B0、B8与H2均公开，未筛掉退化。
- 更强静态S是24优先级池+128次合法顺序局部候选、独立validation选择，仍是有预算的搜索。S8在{ s8faster }个配置test均值上快于S；因此不能宣称S是全图最优。确定性结果不能归为未知完成信息。
- 原始七任务source FFN切片：52拓扑序投影6个资源序；最优固定期望 **{exact['optimal_static']['mean']:.1f} cycle**，B **{exact['B_mean']:.1f}**，逐场景clairvoyant均值 **{exact['clairvoyant_mean']:.1f}**；局部搜索exact gap **{exact['search_exact_gap_pct']:.1f}%**。只对指定二点分布、零控制成本、此固定映射成立。
- {len(numerical)}个实际调度数值重放（每配置seed0的全部6策略）输出/状态与独立FP64参考最大绝对误差 **{error:.3g}**。它不验证BF16舍入、模型质量或实际物理payload；物理alias另由独立trace checker验。

## 2. 模型与工作范围

Qwen官方4B文本部分4.206B、完整发布物4.660B；本轮具有GatedDeltaNet与gated GQA两种有状态文本层。FLUX.2-klein-4B主网络3.876B，4步step/guidance distilled；文本编码器另4.022B，VAE另约0.084B。主实验CFG=1单次条件调用，未强加cond/uncond双分支。[完整模型冻结](model_registry.md)、[Qwen来源](qwen_model_evidence.md)、[FLUX来源](flux_model_evidence.md)

Qwen H80/I288，保留原head比例但head维缩小32倍；FLUX H64/heads4、image16/text8。下表cycle全部来自这些缩尺图，不能换算token/s或image/s。数值计算为随机权重FP64；容量模型默认BF16并仅通过显式表覆盖FP32 recurrent/参数。

Source-level融合已经保留QKV/gate-up，FFN按intermediate两片、attention按head或query-row两片；编译器再合并同核单消费者VPU链。operand pack预取、双槽/core与显式last-reader WAR共同服务所有策略；live-out缓存/状态钉到调用结束。attention aggregate是精确数学组合的边界对照，内部scratch和流量仍计费；它没有实现online softmax或FlashAttention。FLUX conditioning-resident对照将每步共享producer移出单block边界，仍计读取；整pipeline仍须每step支付共享计算一次。

## 3. 对照与结果

S8：继承8候选池、train选固定计划。S：扩展24 priorities和128个合法局部移动、validation选冻结计划。B0：completion-ready，只有共同控制成本；B2/B8另加2/8cycle每task决策/dispatch延迟。H2保留MXU/VPU顺序，仅DMA/SRAM按ready仲裁，并加2cycle。所有策略同一mapping/address/legal DAG/工作量/环境；没有test未来时长挑静态计划。

训练10000..10011，validation20000..20007，test0..31。模型随机权重family builder种子7，linear/single实际种子8。S8与S各只选一次；各策略每seed共享同一环境hash。日历场景固定绝对时间可用服务，相同task的时长可能因开始时刻改变；应用排队重新计算。

主/融合边界全表，正数表示比S快。区间是32个合成seed的近似配对均值95%区间，仅反映采样误差，不含模型误差，也未做多重比较校正。

| case | uncertainty | S mean cycle | B0改善 | B2改善 [95%] | H2改善 |
|---|---|---:|---:|---:|---:|
{chr(10).join(stat_lines)}

全部70配置和B8、p95、SRAM高水位见 [summary.csv](../experiments/results/r4/summary.csv)；逐seed见 [samples.csv](../experiments/results/r4/samples.csv)。

{probe_text}

## 4. 等待是否真的可恢复

S的{len(opportunity)}条trace中，{nonzero}条有非零“全部依赖和地址合法、所需资源与issue lane空闲”的替代任务等待并集，{inverted}条出现相邻资源序的依赖就绪反转。这些计数不是critical-path收益，也不是各task等待之和。

seed0最多选6个候选单动作干预，共{len(interventions)}个离线反事实：{improved}次缩短结束时间、{worsened}次增加，{len(interventions)-improved-worsened}次不变。它们从S的真实机会点提前一个合法任务，随后继续原资源顺序，使用同一外部环境；只衡量这一动作的最终makespan因果效果，不声称求得最优在线策略或固定critical path。改变calendar相位时，效果也包括后续任务重新遇到的背景服务。

因此“出现ready inversion”“某时有空闲资源”“某个局部动作有效”和“整个B策略净获益”必须分别报告。B能抢先占用DMA/SRAM，也可能让后到的关键消费被非关键预取阻塞；它不提高带宽，且所有task额外控制成本都会计入。实际机会/成本摘要在 [opportunity_cost_summary.json](../experiments/results/r4/opportunity_cost_summary.json)，逐动作结果在 [counterfactual_summary.json](../experiments/results/r4/counterfactual_summary.json)。

## 5. 硬件、敏感性与成本

主假设为单cluster双core，一共享DMA/1 outstanding，每core MXU+VPU，两个静态SRAM端口、4MiB共享容量，DMA32B/cycle、每SRAM端口64B/cycle、每core1024 MAC/cycle、VPU32估计ops/cycle。R1与Arm官方文档只是量级参照；没有把这个BF16组合命名为量产芯片。

主模型的同核MXU/VPU全程共享port，无法同核重叠，故另外跑**四个半带宽端口**（总128B/cycle不变）：MXU与VPU/DMA绑定不同端口，允许同核异构流水。这个对照与DMA16/64、SRAM1port、operand1/4slot、容量2/8MiB都各自重新训练静态。它们不是等面积比较；容量扫描未扩满小图需求不能证明真实4B不受容量限制。Qwen真实单层S本身已有2MiB。

资源整task原子保留，dispatch也占资源；aggregate attention保留双engine。MAC/SRAM算术模型没有阵列填充、实际bank/beat/flit/credit，32×32仅是R1 tile量级锚点，不是实现过的array timing。compute确定；独立外生DMA倍率U[0.5,1.5]；周期256、半周期0.25服务率的共享背景日历及组合，均未校准。不同随机源与调度排队分开。

共同issue1/cycle、dispatch1、completion1、wakeup1/cycle，128 resident/32KiB descriptor窗口。所有trace有ready/notification/completion峰值、resource占用率、issue/wakeup服务率、candidate scans及独立task-wait分类。日历下service utilization为占用区间，不是有效字节吞吐。

Descriptor沿用假想48+5×fanin+8×resources bytes；state是带完整done/delivered/通知history的部分logical bits。静态order metadata独立列出，输入/地址layout完整在JSON合同中；模拟器实际消费Python Contract，未作二进制decode。没有有限总事件状态、FIFO credit/backpressure、RTL、面积/Fmax/能耗数据。

主B2在本批图的部分state预算1,529–7,421 bits，descriptor估计851–3,654B，ready峰值2–10、待通知峰值2–7；平均issue端口利用率各配置最大0.581%，wakeup最大0.835%。低平均服务率不等于burst时延无关，也不证明面积可忽略。完整resource占用率、queue和控制成本已逐配置导出。

## 6. 独立审计与可复现性

[独立红队报告](redteam_report.md) 和 [checker](redteam_checks.py) 逐项记录live-out复用、非事件时刻干预、静态metadata漏计、admission截断inversion、融合scratch、dtype字符串启发式等发现与修复。主sweep在最终修复后重新运行，源码hash不匹配会拒绝完成。主报告不把checker PASS升级为真实芯片验收。

```powershell
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B -m r4.qwen_lowering
python -X utf8 -B -m r4.flux_lowering
python -X utf8 -B -m r4.run
python -X utf8 -B -m r4.exact_probe
python -X utf8 -B -m r4.redteam_checks
python -X utf8 -B -m r4.redteam_checks --artifacts
python -X utf8 -B -m r4.priority_probe
python -X utf8 -B -m r4.redteam_priority_audit
python -X utf8 -B -m r4.redteam_static_probe
python -X utf8 -B -m r4.make_report
python -X utf8 -B -m r4.check_artifacts
```

Python {manifest['python']} / NumPy {manifest['numpy']} / Matplotlib生成图；无新安装依赖、无大权重、无Git提交。原始R3源码快照与27文件hash、257旧结果hash见 [r3_snapshot/manifest.json](r3_snapshot/manifest.json)。执行源码、所有参数/seeds、运行计数见 [manifest.json](../experiments/results/r4/manifest.json)。counterfactual只认manifest中active清单，避免中断试跑残留混批。

## 7. 阶段决策

{conclusion} 即使某个更细边界出现局部机会，也还缺全宽状态/权重tile、实测服务日历与独立硬件代价，不能声称“所有强编译器之后必然需要OoO”。当前没有确认论文或专利novelty。[假设台账](hypotheses.md)、[拒绝/细化方向](rejected_refined_directions.md)、[下一轮](next_round.md)、[最近先例差异](prior_art_delta.md)。

![R4 paired latency reduction](figures/r4_results.png)
'''
    (R4/'experiment_report.md').write_text(report,encoding='utf-8')
    # Static publication-ready figure; units and scaling are visible in label.
    fig,axes=plt.subplots(1,2,figsize=(13,7),gridspec_kw={'width_ratios':[1.4,1]})
    for ax,group,title in ((axes[0],'main','Four source-derived scaled blocks'),(axes[1],'fusion_conditioning_sensitivity','Aggregate attention / resident conditioning')):
        rr=[r for r in b if r['group']==group]
        names=[r['case'].replace('qwen35_','Q ').replace('flux2_klein4b_','F ').replace('_scaled','').replace('_attention_aggregate_cond_resident',' opt').replace('_attention_fused',' fused')+' / '+r['mode'] for r in rr]
        xs=[r['paired_reduction_pct'] for r in rr]
        err=[[r['paired_reduction_pct']-r['ci95_low'] for r in rr],[r['ci95_high']-r['paired_reduction_pct'] for r in rr]]
        ax.barh(range(len(rr)),xs,color=['#2b807a' if x>=0 else '#a15b4b' for x in xs],alpha=.9)
        ax.errorbar(xs,range(len(rr)),xerr=err,fmt='none',ecolor='#26323e',capsize=2,linewidth=1)
        ax.set_yticks(range(len(rr)),names,fontsize=7);ax.invert_yaxis();ax.axvline(0,color='#52616b',lw=.8)
        ax.set_title(title,fontsize=11);ax.set_xlabel('B2 reduction vs searched static (%)\n32 synthetic paired seeds; not hardware speedup',fontsize=8)
        ax.grid(axis='x',alpha=.15)
    fig.suptitle('R4: source semantics verified; scheduling service remains uncalibrated',fontsize=13)
    fig.tight_layout()
    (R4/'figures').mkdir(exist_ok=True)
    fig.savefig(R4/'figures/r4_results.png',dpi=160)
    fig.savefig(R4/'figures/r4_results.pdf')
    plt.close(fig)
    decision={'B2_positive':positive,'B2_gate_configs':[r['config'] for r in gate],
        'best_B2':best,'worst_B2':worst,'S8_faster_configs':s8faster,
        'static_trace_count':len(opportunity),'static_traces_with_opportunity':nonzero,
        'static_traces_with_inversion':inverted,'counterfactuals_improved':improved,'counterfactuals_worsened':worsened,
        'numeric_max_abs_error':error}
    (OUT/'decision_summary.json').write_text(json.dumps(decision,indent=2),encoding='utf-8')
    print(json.dumps(decision,indent=2))


if __name__=='__main__':
    main()
