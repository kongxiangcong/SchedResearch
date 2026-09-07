# R3实验报告：存在调度机会，但尚未证明大规模动态硬件值得

日期：2026-09-05。由 `python -X utf8 -B -m experiments.make_report` 从当前完整结果生成。

## 1. 结果与证据级别

完成 **49配置 × 20 test seeds × A/A2/B/C = 3920次执行**。另有四任务exact反例与72个minimum-window/开销点（每点两个确定场景，穷举6种静态admission/order合同）。14项自动测试通过；保存196条seed0 traces，全部通过资源互斥/最小依赖可见性检查；13个源文件hash与实验manifest一致。trace检查的排队时序覆盖限制见第6节。

B相对同合同A2：10个配置均值为正、17负、22零；C有0个配置mean优于B。A2在11个配置中mean反而输给A，有限训练静态不是普遍更强。正/负数量未按统计显著性筛选，也不是独立真实workload的胜率。

**结论：** R2的必要条件已被严格反例否定；本轮更大motif大多数没有值得增加硬件的优势。更复杂C没有继续理由。Hybrid仍是值得研究的边界，但本轮不确认独立论文贡献或真实设备性能。

![R3 evidence](figures/r3_evidence.png)

可导出图：[PDF](figures/r3_evidence.pdf)。图中B/C对A2的配对区间只反映synthetic分布采样误差，不覆盖模型误差；展示case为解释机制选择，不代替下方全表。

## 2. 四任务：精确存在性、最小窗口与增量成本

两独立DMA分别唤醒共享VPU上的20cycle任务，DMA时长等概率(80,120)/(120,80)。固定地址，无复用，CoV0.2且有界。两个VPU固定顺序的期望均150；B每场景140，达到每场景下界120+20。latency reduction=6.667%，speedup=1.07143。不存在把naive sequential当baseline的问题。

有限window包括运行中和等待中的resident task。W2会让等待较晚producer的descriptor挡住尚未admit的替代任务；W3暴露它，W4不再增加收益。以下common cost为0，额外派发成本只向B收费：

| Window | B额外dispatch/task | 最优静态期望 | B期望 | 延迟降低 | B部分state bits |
|---:|---:|---:|---:|---:|---:|
| 1 | 0 | 240.0 | 240.0 | 0.000% | 229 |
| 1 | 4 | 240.0 | 256.0 | -6.667% | 229 |
| 1 | 8 | 240.0 | 272.0 | -13.333% | 229 |
| 2 | 0 | 150.0 | 150.0 | 0.000% | 290 |
| 2 | 4 | 150.0 | 160.0 | -6.667% | 290 |
| 2 | 8 | 150.0 | 170.0 | -13.333% | 290 |
| 3 | 0 | 150.0 | 140.0 | 6.667% | 351 |
| 3 | 4 | 150.0 | 148.0 | 1.333% | 351 |
| 3 | 8 | 150.0 | 156.0 | -4.000% | 351 |
| 4 | 0 | 150.0 | 140.0 | 6.667% | 412 |
| 4 | 4 | 150.0 | 148.0 | 1.333% | 412 |
| 4 | 8 | 150.0 | 156.0 | -4.000% | 412 |

所有点总descriptor估计234B；351/412等state数只是本图的部分逻辑位预算，不是PPA或量产规格。W3在额外8cycle时变成156，比最优静态150慢4%。因此最小窗口并不保证划算，也不能从本例推导所有NPU用3项就够。

## 3. 大图主比较与强静态核对

A采用8种离线list-schedule候选择预测最优；A2用8个独立训练seed选择固定顺序。B/C使用A2的同DAG、mapping、地址、priority、admission与hardware。A2/B配对隔离选序自由；A列则用于发现B是否只是胜一个较差的静态选择。A/A2都还不是生产级全局最优。

| 配置 | task数 | A均值 | A2均值 | B均值 | C均值 | B对A2配对降低 | 近似95%区间 |
|---|---:|---:|---:|---:|---:|---:|---:|
| chain_deterministic | 12 | 540.00 | 540.00 | 540.00 | 540.00 | 0.000% | [0.000, 0.000] |
| chain_memory_cov06 | 12 | 544.52 | 544.52 | 544.52 | 544.52 | 0.000% | [0.000, 0.000] |
| fork_join_deterministic | 10 | 170.00 | 170.00 | 170.00 | 170.00 | 0.000% | [0.000, 0.000] |
| fork_join_memory_cov06 | 10 | 169.42 | 169.42 | 169.42 | 169.42 | 0.000% | [0.000, 0.000] |
| diamond_deterministic | 11 | 185.00 | 185.00 | 185.00 | 185.00 | 0.000% | [0.000, 0.000] |
| diamond_memory_cov06 | 11 | 183.87 | 183.87 | 183.87 | 183.87 | 0.000% | [0.000, 0.000] |
| critical_background_deterministic | 14 | 180.00 | 180.00 | 180.00 | 180.00 | 0.000% | [0.000, 0.000] |
| critical_background_memory_cov06 | 14 | 183.84 | 183.84 | 188.11 | 190.11 | -2.383% | [-4.441, -0.324] |
| pipeline_deterministic | 30 | 613.00 | 613.00 | 613.00 | 613.00 | 0.000% | [0.000, 0.000] |
| pipeline_memory_cov06 | 30 | 623.53 | 623.53 | 623.53 | 623.53 | 0.000% | [0.000, 0.000] |
| llm_prefill_deterministic | 36 | 648.00 | 648.00 | 648.00 | 663.00 | 0.000% | [0.000, 0.000] |
| llm_prefill_memory_cov06 | 36 | 673.44 | 679.82 | 673.60 | 673.60 | 0.919% | [0.156, 1.683] |
| llm_decode_deterministic | 36 | 1365.00 | 1365.00 | 1365.00 | 1365.00 | 0.000% | [0.000, 0.000] |
| llm_decode_memory_cov06 | 36 | 1346.62 | 1347.97 | 1347.97 | 1354.03 | 0.000% | [0.000, 0.000] |
| dit_cfg_deterministic | 96 | 1527.00 | 1527.00 | 1527.00 | 1602.00 | 0.000% | [0.000, 0.000] |
| dit_cfg_memory_cov06 | 96 | 1527.35 | 1527.35 | 1523.08 | 1562.61 | 0.281% | [0.136, 0.426] |
| uncertainty_0.1 | 10 | 169.90 | 169.90 | 169.90 | 169.90 | 0.000% | [0.000, 0.000] |
| uncertainty_0.3 | 10 | 169.70 | 169.70 | 169.70 | 169.70 | 0.000% | [0.000, 0.000] |
| uncertainty_1.0 | 10 | 169.06 | 169.06 | 169.06 | 169.06 | 0.000% | [0.000, 0.000] |
| heavy_tail | 10 | 174.22 | 174.22 | 174.22 | 174.22 | 0.000% | [0.000, 0.000] |
| cores_4 | 60 | 705.49 | 705.49 | 705.49 | 710.85 | 0.000% | [0.000, 0.000] |
| cores_8 | 120 | 1006.52 | 1006.52 | 990.33 | 1079.33 | 1.718% | [-0.919, 4.355] |
| clusters_2_central | 50 | 629.75 | 629.75 | 657.09 | 657.09 | -4.312% | [-5.821, -2.803] |
| clusters_2_local | 50 | 629.22 | 629.22 | 655.69 | 655.69 | -4.176% | [-5.701, -2.651] |
| equal_budget_clusters_2_central | 50 | 629.75 | 629.75 | 657.09 | 657.09 | -4.312% | [-5.821, -2.803] |
| equal_budget_clusters_2_local | 50 | 631.22 | 631.22 | 657.69 | 657.69 | -4.162% | [-5.686, -2.638] |
| clusters_4_central | 98 | 830.81 | 838.52 | 839.26 | 839.26 | -0.189% | [-1.724, 1.346] |
| clusters_4_local | 98 | 829.74 | 836.16 | 835.15 | 835.15 | 0.028% | [-1.423, 1.479] |
| equal_budget_clusters_4_central | 98 | 829.74 | 836.87 | 836.04 | 836.04 | 0.002% | [-1.506, 1.511] |
| equal_budget_clusters_4_local | 98 | 831.74 | 839.10 | 837.22 | 837.22 | 0.132% | [-1.335, 1.598] |
| chips_2_memory | 50 | 624.52 | 624.52 | 651.95 | 651.95 | -4.418% | [-6.022, -2.814] |
| chips_2_communication | 50 | 618.02 | 618.02 | 664.59 | 664.59 | -7.530% | [-7.841, -7.219] |
| chips_2_memory_communication | 50 | 629.22 | 629.22 | 655.69 | 655.69 | -4.176% | [-5.701, -2.651] |
| chips_4_memory | 98 | 832.54 | 832.54 | 843.25 | 843.25 | -1.327% | [-2.461, -0.192] |
| chips_4_communication | 98 | 818.54 | 822.24 | 865.11 | 865.11 | -5.237% | [-5.621, -4.853] |
| chips_4_memory_communication | 98 | 829.74 | 836.87 | 836.04 | 836.04 | 0.002% | [-1.506, 1.511] |
| grain_1_cost_0 | 20 | 427.39 | 429.23 | 429.23 | 443.62 | 0.000% | [0.000, 0.000] |
| grain_1_cost_2 | 20 | 471.58 | 473.34 | 483.63 | 483.63 | -2.159% | [-2.732, -1.585] |
| grain_2_cost_0 | 40 | 338.52 | 338.52 | 339.21 | 360.56 | -0.239% | [-1.196, 0.719] |
| grain_2_cost_2 | 40 | 382.98 | 382.98 | 380.36 | 397.34 | 0.677% | [-0.412, 1.766] |
| grain_4_cost_0 | 80 | 336.74 | 338.23 | 335.98 | 354.87 | 0.643% | [0.190, 1.096] |
| grain_4_cost_2 | 80 | 410.29 | 410.29 | 402.10 | 408.64 | 1.948% | [1.120, 2.775] |
| window_2 | 30 | 655.53 | 655.53 | 673.11 | 673.11 | -2.692% | [-3.228, -2.156] |
| window_8 | 30 | 655.53 | 655.53 | 684.94 | 684.94 | -4.484% | [-5.312, -3.657] |
| window_32 | 30 | 655.53 | 655.53 | 684.94 | 684.94 | -4.484% | [-5.312, -3.657] |
| wakeup_1 | 18 | 197.94 | 192.82 | 192.82 | 192.82 | 0.000% | [0.000, 0.000] |
| wakeup_2 | 18 | 184.33 | 181.60 | 181.60 | 181.60 | 0.000% | [0.000, 0.000] |
| wakeup_8 | 18 | 179.69 | 179.69 | 179.69 | 179.69 | 0.000% | [0.000, 0.000] |
| byte_window_256 | 30 | 638.53 | 638.53 | 665.99 | 665.99 | -4.298% | [-5.143, -3.454] |

需要特别解释的观察：

- Prefill motif的B对A2为+0.919%，但A=673.44已优于B=673.60，不能据此宣称strong compiler无法解决。
- DiT motif为+0.281%，统计上虽有一致小改善，但远小于5%研究筛选阈值；它是手写CFG/AdaLN结构，不是真实DiT测量。
- 两chip communication-only为-7.530%，动态更慢。阶段barrier和非抢占resource order让“通信越随机、动态越值钱”不成立。
- 确定性链/多个规则pipeline为零；随机链也可以为零。后者是缺乏可利用自由度，不是延迟确定。
- 粒度扫描保持粗task的同一噪声因子和总服务工作量。细粒度带来的pipeline重叠也能被静态compiler利用，不能把它全部归给dynamic。

## 4. 集中与分域：相同预算仍未见优势

原clusters_*_local每域复制端口/窗口，所以只作扩硬件的对照。equal_budget_*固定总entry/bytes/issue/wakeup预算：local每域16项/4096B/1 issue/1 wakeup，central按实际域数乘总量。两者保持同样物理任务资源，端口服务和窗口分配方式不同；没有建布线距离或真正层次协议。

| 域数 | Central B latency | Local B latency | Local相对central延迟降低 |
|---:|---:|---:|---:|
| 2 | 657.088 | 657.688 | -0.091% |
| 4 | 836.038 | 837.221 | -0.142% |

该比较没有证明分布式更好；它也不能证明central实际布线可扩展。当前所谓local只分片issue/wakeup与admission，全图metadata仍存在；hierarchical scheduler未实现。

## 5. 利用率与控制成本（B，跨20 seeds平均）

| 配置 | MXU busy | VPU busy | DMA busy | Ready均值 | issue利用率 | wakeup数 | descriptor B | 部分state bits |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| chain_memory_cov06 | 88.2% | — | 11.8% | 0.00 | 未收费 | 11 | 727 | 1509 |
| llm_prefill_memory_cov06 | 67.0% | 8.9% | 50.6% | 0.26 | 未收费 | 40 | 2360 | 4732 |
| dit_cfg_memory_cov06 | 78.8% | 11.0% | 18.8% | 1.27 | 未收费 | 124 | 6188 | 13411 |
| chips_2_communication | 45.3% | 6.0% | 14.3% | 0.73 | 3.8% | 52 | 3316 | 6486 |
| grain_4_cost_2 | 74.7% | 10.0% | 23.6% | 3.32 | 39.8% | 72 | 5096 | 9465 |
| wakeup_1 | 31.2% | 15.6% | 38.0% | 0.62 | 2.3% | 24 | 1128 | 2574 |

busy是task服务时间/总延迟，多个同类resource等权平均；reserved利用率另含dispatch设置，原始JSONL也保留。issue利用率是建模端口服务占用率；0开销下不能将其解释成真实scheduler空闲。task throughput为Ntasks/latency，不能换成tokens/s。

各样本还保存admission/dependency/memory-resource/communication-resource/engine/static-order/issue等待、各resource idle、critical-path ratio、candidate checks和state breakdown。task等待类别排他，但跨task相加**不等于**端到端stall。cache miss、DRAM refresh和NoC flit stall未实现，不能从聚合资源字段推导。

## 6. 正确性、模型局限与可复现性

独立审计修复了buffer span不足、有限窗口admission/静态顺序不兼容、barrier被错误当tile data edge三个输入/扩展缺口。当前结果按修复后源码重跑。trace checker独立查每task唯一、基础可见性和resource不重叠，但未独立重建全部wakeup/issue排队；这些由专门单元测试覆盖。详见 [simulator redteam](../analysis/simulator_redteam.md)。

模型仍有重要局限：整task原子独占SRAM/DMA/NoC bundle；服务分布人工且缺相关拥塞；无真实model export/数值；地址默认不复用，capacity联合优化未测；finite window之外还有O(N+E)history/通知状态；无有限credit回压/epoch回绕/分布式死锁验证；C额外算术延迟未收费。descriptor只是可检查JSON表示和假想bytes，**没有binary decoder roundtrip**。

这些局限使本轮足以反驳R2必要条件、证明特定图的信息价值并筛选策略，但不足以证明真实端侧NPU收益或最小硬件总状态。未通过实际workload+强静态+详细时序+PPA证据门，所以最终架构暂不锁定。

复现（目录根，Python标准库运行仿真；画图另需matplotlib/numpy）：

```powershell
python -X utf8 -B -m unittest discover -s tests -v
python -X utf8 -B -m experiments.run --seeds 20 --training-seeds 8
python -X utf8 -B -m experiments.oracle_probe
python -X utf8 -B -m experiments.check_results
python -X utf8 -B -m experiments.minimum_window
python -X utf8 -B -m experiments.make_report
```

[完整CSV](../experiments/results/r3/summary.csv) · [逐seed样本](../experiments/results/r3/samples.csv) · [全部metrics](../experiments/results/r3/metrics.jsonl) · [源码manifest](../experiments/results/r3/manifest.json) · [产物检查](../experiments/results/r3/artifact_check.json) · [minimum-window原始结果](../experiments/results/minimum_window/results.json)
