# 科学问题线

更新：2026-09-14。与[实验能力线](experimental-capabilities.md)共同构成项目唯一持续维护的研究进度入口。本文按问题和转向组织，不把轮次编号、工具接通或测试数量当作研究结论。

本次整理读取实际源码、历史报告和已存结果；下述实验数字均为历史回执所载，未重跑历史性能、数值或求解器实验。本次目录验证单列在[整理记录](../reorganization-2026-09-14.md)。计划、已实现、已有验证记录、未完成四种状态分别记载；历史报告中的“本次通过”不代表本轮重新验证。

## 当前问题与决策

长期问题仍是：Qwen / FLUX.2 场景下，编译器确定合法数据流、映射和生命周期后，哪些损失可由静态规划消除，哪些需要依赖实际完成状态的执行？目前没有得到充分证据支持的新调度硬件收益主张。

**当前工作阶段是开源研究基础设施准入。** R13 后的[首轮提示词](../archive/prompts/infra-round-1.md)明确允许替换 Wormhole/R13 底座，不再要求先完成 R13 人工微图的强 P0 才搭建实验环境；[第二轮提示词](../archive/prompts/infra-round-2.md)又选择先修复计划检查器、接通 STREAM 静态评估，而没有选择自建执行器。最新代码已有计划与功能回放、分析型静态评估，执行后端仍未实现。不能把旧交接中“建议建执行核心”的建议写成已经选定或实现的路线。

R13 的模型研究结果仍有效，但处于保留的独立研究分支；新的基础设施不是 R13 Hcompiler/M1/M2 的补签。STREAM 的 Ironwood 示例、ONNXim 的四核配置、Wormhole 参考模型分别有自己的硬件合同，不能拼接性能证据。

## 问题一：完成信息是否值得新增动态调度机制？

| 阶段与问题 | 假设、历史实验及结论 | 边界与方向转变 |
|---|---|---|
| R1–R2：静态计划会失去什么？ | R1 为 C1–C10 选题筛选；R2 为 21 点 toy 和 P1–P5 路线。没有完成新硬件性能闭环。 | R2 的“无复用无收益”“重尾必要”不是可继续使用的前提。[原始审计](../../research/analysis/r1_r2_audit.md) |
| R3：信息价值存在吗？ | 无复用、有界轻抖动四任务例：固定最优期望 150，免费 ready 140；每 task 收费 8 cycle 后变为 156。另有 49 配置、3,920 次合成执行。 | 存在性成立，成本可吞掉收益；复杂 C 未获支持。事件批量完成修正了 R2 的同刻仲裁偏差。转向来源图和更强静态。[报告](../../research/r3/experiment_report.md) |
| R4：来源图、强化静态后是否仍成立？ | 七类来源缩尺图，13,440 主执行；4,480 次后验 priority 修正。收费方案无一通过 5% 门；修正后最好约 +0.1968%，区间跨零。 | 后验修正不能作为独立确认；可行动等待不等于最终 elapsed 可恢复。转向全宽与资源行为。[报告](../../research/r4/experiment_report.md)、[红队](../../research/r4/redteam_report.md) |
| R5：细化资源能否救活 ready？ | 7,094 主执行；bank/request/outstanding/credit/返回反压，36 请求配置无 5% 达门。投影供给损失约 33% 与几乎无调度收益可以并存。 | 关闭已测通用 ready；未校准来源切片，非整模型、非所有策略。[报告](../../research/r5/experiment_report.md) |
| R9：多 cluster 共享 EXT 损失是否可恢复？ | 204 静态候选、180 paired blocks、2,880 单动作反事实。最好收费回看均值约 0.0210%、CI 跨零；主范围平均免费上界约 1.6%–1.9%。 | 35% 条件最大上界 5.1579%，严格逐 phase 关闭门未通过；回看选择也不是 causal policy。转向更紧下界及带宽比例。[报告](../../research/r9/experiment_report.md) |
| R10：剩余上界是松界还是动作空间？ | 两种硬件各 960 候选；有限 credit/串联下界解释部分 gap，仍留约 10%–13% 平均上界。固定收费规则 1,440 次观察、0 次实际改序。 | 关闭该触发规则收益主张；没有识别实际触发改序的效果，也未证明所有顺序无价值。停止以同类触发器延长未决。[报告](../../research/r10/experiment_report.md)、[收敛审查](../../research/analysis/r9_r10_convergence_review.md) |

**未决项与重开条件：** 已测规则保持关闭。若另提运行时动作，先固定同一强静态计划、地址、工作量、资源和数值许可，证明动作实际触发且改变完整终点，再用独立条件支付观察、选择、通知及执行成本。大干扰、大上界或存在 ready task 都不是正收益证据。旧 5% 门属于具名旧合同，不能随意移植到新模型。

## 问题二：数据移动与生命周期是否已有静态解？

| 阶段 | 历史证据 | 解释及剩余问题 |
|---|---|---|
| R5 驻留控制 | 两 head、四个 prepared token，928 控制执行；静态 RF 驻留改善 7.155%–24.027%，resident B0=S。 | 支持该切片静态优化，不能直接推出完整 GDN、自回归或外存流量同比下降。 |
| R6–R7 功能与容量门 | 32-head 单层 state 2 MiB、24 GDN 层共 48 MiB；Phoenix copy 和固定 INT8 GEMM 有功能回执。 | 相邻同层 token 之间经过其他层，容量和合法持久性必须另证；48 MiB 不等于每 token 必走外存。功能工具并未识别强静态后残差。[R6](../../research/r6/experiment_report.md)、[R7](../../research/r7/experiment_report.md) |
| R8 分片与安全 | full K=9216/N=128、M=1/32；18 CPU 比较、70 个单 payload 线性扩展。37 个错误序是结构反例。 | partial 是否必要取决于 mapping；split-K 容差通过不等于允许改变归约。source-last-read、destination-visible、consumer-last-read 不能混用，静态 wait/release 可满足已测安全合同。[报告](../../research/r8/experiment_report.md) |
| R9 静态 mapping | quiet C2K 47,776 vs C2N 55,912 cycles，改善 14.5514%。 | 是共同 EXT/broadcast/staging 合同下的输入复制与 partial 流量取舍，不是新 direct fabric 或动态恢复收益。 |
| R11 完整 GDN 单层 | 76 数值 block、4 decode callback、122 保存 trace 的历史审计；local state read/write 16,777,216→4,194,304 B，external 88,863,488 B 不变。quiet −0.015670637%，背景 A/B −0.599174254%/−0.605967308%。 | **关闭完整 32-head、四 token prefill、cold-weight/staged ABI 驻留候选。** strict decode 的 RF/VMEM clobber 使两图相同，没有合法干预。不能把 R5 正例继续写成完整模块待验证成果。[报告](../../research/r11/experiment_report.md)、[结果](../../research/r11/results.json) |

warm weights、跨层融合、其他存储合同未测；它们需要新的具体问题、容量/生命周期与公平基线，而不是恢复旧候选。FLUX.2 单块建议仍是[范围提案](../../research/analysis/flux2_small_experiment_recommendation.md)，不是完整 FLUX.2 实验；MoE/稀疏/3D memory 也没有因稠密图负结果自动升级为主线。

## 问题三：真实来源的资源与完成语义会改变联合编译吗？

### 重审与 R12：先纠正需求，再谈模型

[2026-09-07 重审合同](../../SchedResearch_reassessment_evidence_20260907/proposal_contract.md)转向 Wormhole B0 的 placement、routing、window、wait scope 联合问题。动机不是追逐正结果，而是旧阶段更换过硬件与路径合同，不能把单 EXT/staged 负结果外推至分布式 controller、双 NoC。H0 是正确移植强 STREAM/TETRA 加已有原生能力即可吸收损失；H1 才是新联合计划的额外价值；H2 是固定强计划后仍需付费运行时动作的条件备选。

R12 建立公开来源、固定依赖、完整 MLP 工作量，核对 28,800 路由组合、96 个流量计划和 56 事件条件性功能图。它们不是完整时序搜索。tt-npe 的历史构建/API 成果仅用于粗筛，native G0 与完整 H1/H2 未完成。[报告](../../research/r12/experiment_report.md)、[资格摘要](../../research/r12/artifacts/qualification_summary.json)

必须保留的撤回：先前由完整 buffer 分配推断真实 2conv 必须 full-payload all-gather，最终 affine 访问审计证明不成立。实际 halo 需求 49,152 bit，共享 128 bit/cycle 的必要界是 384；显式 full-copy 的 2,048 界属于另一个合同。调整费用后的优化器变化只是条件性敏感度，不能称修复了真实 fixture 的成本。[独立审计](../../research/r12/independent_research_audit.md)、[R13 需求回归](../../research/r13/artifacts/demand_checks.json)

### R13：已有模型内见证，没有 Hcompiler 接受

R13 将问题明确为无板卡前提的公开来源参考模型。已实现 DES、有限 buffer/credit、独立 tick 和逐 16B 值/epoch 审计；内部资格已有历史验证。NPE 的本轮跨工具执行当时被 WSL 拒绝，因此不写“整条 M0 全通过”。[完整报告](../../research/r13/experiment_report.md)

| 子问题 | 已存证据与结论 | 准确边界 |
|---|---|---|
| 聚合流量能否选择最好计划？ | 576 个共同合法候选 + 168 见证/结构对照，共 744 执行。p0024/p0072 最优 81,136 ticks = 2,253.7778 model cycles；粗流量按固定打平选 p0000 为 2,336.7778。 | p0000 相对 exact regret 3.6827%；改用 exact 的时间减少为 3.5519%，分母不同。只支持有限 C 的 Hmodel，不是新算法收益。[全表独立分析](../../research/r13/artifacts/micro_independent_analysis.json) |
| 是否只因打平选错？ | payload/full-protocol traffic 的 24 个最小并列项全部错过 exact，其最好项仍慢 1.695918%。 | 依赖/latency 下界的最小并列集含 exact，只能说分辨力不足，不是严格排序反转。 |
| 共享/分离路径与 channel 是否改善终点？ | 预选等总协议流量 W1 名义持平，26 点仅 1 点约 +0.142553%；W2 分离输入 channel 全部 26 点持平。 | 更分散资源不必缩短关键路径；W1 每 flow 路径有混杂，不能单独归因链路争用。 |
| source 提前释放是否有价值？ | W3 合法 source 观察相对 ACK 等待，名义 +3.8495%，26 点范围 0–7.7391%。 | 强 P0 也有该能力，且一点为零；不是新编译器或全域严格正向结果。26 点没有重搜 exact 或验证其失配稳健性。 |
| 是否击败强 TETRA？ | 真实 TETRA 来源 seed 经 source-aware lowering、2,127 条顺序义务与数据审计，F 输出 3,575.6667 model cycles；直接 global-slot 屏障下降产生环并被拒。 | seed 比 canonical C 多保守偏序，同 p0000 标签不等于同完整图。不能把 3,575.67 对 2,253.78 宣称击败强 P0。[准入审查](../../research/r13/tetra_lower_independent_audit.md) |

完整 H=2560/I=9216、M=1/32/128 CPU 数值合同已有历史资格；完整 MLP 的六配置性能模拟未启动。**完整 P0 组合、同预算搜索轨迹、P1/Hcompiler 未完成，M1 整门和 M2 未通过。** 若重开此分支，按[资格合同](../../research/r13/p0_qualification_next.md)先补共同计划/地址/顺序空间、SoMa-style 生命周期/搬运顺序、双缓冲/窗口和实际 P0 预算；强 P0 吸收残差则接受工程或负结果。无板卡不阻塞模型研究，模型结果也不等同实测。

## R13 之后：基础设施为何成为当前优先事项？

| 决策阶段 | 实际改变与验证状态 | 对科学问题的影响 |
|---|---|---|
| 开源底座首轮（2026-09-09） | 优先复用开源后端，新增 `schedinfra` 工作量、计划 IR、检查器和 CPU 参考；审计 ONNXim，环境与跨算子驻留/核间通信/Cast 语义均有阻断。首轮判决 PARTIAL。 | 放开固定 Wormhole/R13 底座要求，先获得可运行的研究能力。B1/B2/B3 执行验收均 NOT_RUN。[结构化回执](../archive/infra/round-1.json) |
| 计划修复与静态评估（2026-09-13 UTC / 09-14 本地） | 修复任一读者即可覆写的错误及 naive 屏障，加入 fail-closed、三层准入、功能回放；接通固定 STREAM 的静态分析。 | PLAN_SAFE / STATIC_EVAL_READY 为具名能力状态，RUNTIME_READY 仍否。测试通过不证明任意交错容量安全。[结构化回执](../archive/infra/round-2.json) |
| STREAM 完整维度 MLP | occupancy 23,886 vs span 25,136 analytical cycles，选中结构相同；Cast 不能建节点，转换算术未收费。 | 两种静态配置的代价不是两种已执行计划加速；不能支持 Hcompiler、动态收益或合同完整的 MLP 性能结论。 |

当前源码和回执的逐层核对、环境与复现入口见[实验能力线](experimental-capabilities.md)。完整数值参考、tiny 计划回放、STREAM 分析和后端执行是四种不同证据，不能互相补齐缺失层。

## 原始候选的继承与未决项

正式候选是 R1 C1–C10 与 R2 P1–P5 共 15 项；D1–D5 是 C1–C5 重命名，不重复计数。原定义见 [R1](../../research/r1-base/redteam_claim_frameworks.md)、[R2](../../research/r2-ooo-npu/research.md)。

| 候选 | 当前继承状态 |
|---|---|
| C1/D1 VMEM remapper | 机制设计，未完成同基线性能/RTL 比较，暂停；未被调度负结果证伪。 |
| C2/D2 generation lease | 安全条件经 R8/R12/R13 与新 checker 部分澄清；新 lease 硬件必要性未证。 |
| C3/D3 3D KV/attention 近存 | 无近存流量/能耗/热/时延闭环，未测储备。 |
| C4/D4 bank-coupled 阵列分区 | 无同面积/供数/带宽比较，未测暂停。 |
| C5/D5 direct stream/gather/reduce fabric | 分片账本有进展，原 direct fabric 未实现验证。 |
| C6 template、C7 counter selector、C10 precision replay | 原选题淘汰，非性能实验证伪；C7 不等于 P3。 |
| C8 thermal placement、C9 fault-map 降级 | C8 合并至 C3；C9 未测储备。 |
| P1 flexibility-certified memory plan | 宽泛合同原创性不能恢复；具体驻留正例在 R11 完整合同失败，新共同空间优化仍需证据。 |
| P2 partial-order 动态派发 | 具名 ready/触发规则维持关闭；全域不可能性未证。 |
| P3 数据相关 quasi-static 变体 | MoE/可变 batch 等原目标尚未完成研究，不能外推稠密图负结果。 |
| P4 方差与边界计量 | 功能/模型工具有成果，真实目标强静态后残差未测。 |
| P5 decoupled access/execute | 预取、双缓冲、重叠为强基线，没有独立新硬件收益接受。 |

共享 Softmax/RMSNorm/RoPE SFU 和 DMA-adjacent operand physicalization 两个旁支仍停在讨论；R3 event-frontier 总状态回收是未实施候选。H-A…H-H、策略 B/C、配置数量和 infra 两轮都不是新增成熟 proposal。

## 下一步判定与维护方式

1. **当前能力线继续，算法结论暂不升级。** 先确定能保留外部计划、显式计费远程移动/复用/完成语义的执行合同。是否选有界自建核心，或缩小需求重新准入 ONNXim，尚无已实施决定。提供 Linux 也不能自动解决 ONNXim 的语义缺口。
2. 执行验收必须覆盖 B1 外部映射被实际保留、B2 生命周期/按需启动/流量可观测、B3 同合同可替换发行策略，再比较完整 MLP 两份合法计划；固定 seed 与身份可复现。此前不得把 analytical cycles 当 runtime 证据。
3. 若回到 R13，先过共同强 P0 门；若选择新目标，重新冻结工作量、数值、硬件、成本和净收益门，不能继承 R13 3% 或旧 5% 为自动通过条件。新颖性需另查原始文献，本轮没有重新检索。

后续每次研究更新在本文记录“问题→假设→已存实验→结论/反证→边界→转向原因→下一判定”，同时在能力线更新支撑它的实现和验证层级。阶段报告和冻结记录只作为引用证据，不再新增 successor_progress 或 handoff 作为第三份活动台账。
