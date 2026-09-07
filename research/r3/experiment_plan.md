# R3实验计划与执行覆盖

日期：2026-09-05。本轮先完成有限证伪闭环，再决定R4；不承诺完整模型、RTL或工业复现。

| 阶段 | 实验 | 判断目标 | 当前状态/产物 |
|---|---|---|---|
| 历史审计 | 完整R1/R2；原toy21点重现；同刻事件/编号扰动 | 历史数字能否重现、结论是否越界 | 已执行，[audit](../analysis/r1_r2_audit.md)与原样hash |
| 存在性 | 四任务、两场景、固定地址，无reuse/heavy-tail | ready顺序的信息价值 | 已执行，穷举static与exact oracle |
| 核心语义 | typed deps、last-reader alias、visibility、atomic资源、同刻completion | 排除错误提速 | 已自动测试；独立红队见[simulator_redteam](../analysis/simulator_redteam.md) |
| 强基线 | A多priority候选；A2独立training选择；B/C同合同 | 动态是否只胜差静态 | 已执行，A2失利也报告；非全局最优 |
| Synthetic | chain、fork/join、diamond、pipeline、critical+background | 哪些图有/无机会 | 多seed已执行 |
| Workload motifs | LLM prefill/decode、独立DiT CFG/AdaLN/denoising链 | 是否值得提取真实模型图 | 已执行结构模型；未导出真实模型 |
| 大小/成本 | cores、clusters、chips、window/bytes、grain、issue/wakeup | 成本拐点与可见并行度 | 已执行聚合资源模型；等预算分域对照单列 |
| 最小硬件 | W=1/2/3/4，common/extra动态开销 | 最小充分window与break-even | 已执行72配置点×两确定场景，无需随机CI |
| 大图future信息 | clairvoyant候选调度 | 提示还可优化的空间 | 已执行小样本heuristic probe，**非精确oracle/上界** |
| 真实请求/模型 | LLM/DiT graph与tensor bytes、实际延迟 | 真实workload成立性 | 未执行，R4首要证据门 |
| 详细硬件 | DRAM/NoC闭环、finite credit/epoch、RTL面积/Fmax | scalable机制和PPA | 未执行，不以抽象bit预算代替 |

## 配对与复现规则

默认20个test seeds和8个training seeds隔离；随机因子由seed+task id生成。粒度切分共享原task因子，避免人工平均方差。所有完成驱动策略使用同样duration样本；资源竞争由争用产生。改动语义后重跑相关配置并更新source hash；报告只引用最后完整结果。

`minimum_window`单独固定等概率两场景，在每个window/common-cost下穷举6种拓扑admission与投影resource顺序选择最优静态。B使用其同一合同，额外成本明确仅向B收费；保持work/data/resources不变。

## 最重要的未覆盖项

LLM/DiT名称只是motif，没有真实model export、attention数值、MoE动态路由或token吞吐；默认地址全分离，alias路径只在correctness测试中覆盖，未跑完整memory-capacity co-optimization；core/cluster/chip任务都有人工服务常数；SRAM/NoC为整task原子占用，未建bank beat/packet/credit；中央/分域都保留全图metadata与event history。

这些限制决定本轮结论只能是“反驳错误必要条件、筛掉缺乏收益的简单候选、建立可运行测量工具”，不能宣告一套架构在真实设备有效。
