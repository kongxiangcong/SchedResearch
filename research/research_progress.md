# 科研方向探索进度表：R1–R13

更新：2026-09-08。**当前主线是在有公开架构依据的 Wormhole B0 类多 tile、双 NoC、分布式外存控制器系统上，建立硬件执行模型，研究强静态编译器如何联合选择计算映射、张量放置、通信路径与发送窗口，并检验真实架构所规定的资源、完成及可见性语义是否改变计划与完整模块 elapsed。** 用户已明确没有 Wormhole 板卡，本轮目标是模型仿真研究。板卡、远程设备、固件实测与物理 PPA 不作为这条模型主线的前置条件；任何结论仍须注明模型依据、假设与适用范围。

不再固定“每 cluster 两核”或等待当前 TARS/Phoenix 入口。R1–R11 的硬件、工作量、数值和运行时合同各不相同，不能拼接成一台已经得到验证的目标，也不能把各轮负结果扩展为所有多 cluster/NoC/3D memory 方案无效。3D memory 保留为需要独立架构与成本依据的比较对象，不给 Wormhole 模型免费增加带宽。

本次更新只维护活动台账，不改写 R1–R12 冻结实验。旧进度的原字节副本在 [R13 前进度快照](r13/history/research_progress_before_r13.md)，SHA-256 为 `4b7698a7a4a17208925d098ede7555b7823cbc34a966aa1fbd767bfae1e384ab`；另一活动台账原字节在 [回溯快照](r13/history/retrospective_before_r13.md)，SHA-256 为 `5e9104aa406887c7452b438df267a72cdca523a43c4937d24513f6b4e1249a5b`。下方历史正文保留当时的判决与建议；其中“当前”“下一步”“真实测量门”均属于当时合同，当前方向以本节及 [R1–R12 回溯](analysis/r1_r10_research_retrospective.md) 为准。

## R13 第一阶段实际进展（2026-09-08）

本轮已从方向合同进入硬件建模与仿真实验；没有要求或执行Wormhole板卡。实现了有限buffer/credit的主DES、独立tick检查器、逐16B值/epoch与复用审计；完整MLP的CPU数值合同和2conv实际需求回归通过。小图预登记576项名义全集与6个冻结见证×26参数及12个结构对照，共744次执行，全部合法；最优计划又通过独立6120操作tick复核。[R13实验报告](r13/experiment_report.md)、[全部数据](r13/artifacts/micro_nominal.json)

有限C内最优p0024/p0072的输出为2253.7778 model cycles；两种最少总流量估价按登记规则选中p0000，2336.7778，比exact慢3.6827%。这支持局部Hmodel，不支持Hcompiler。预选等总协议流量路径对名义持平；分离输入channel在26点均未缩短主终点；合法source复用相对ACK等待名义改善3.8495%，但它也是P0合法能力，且一个参数点改善归零，不能计为新编译器收益。

真实STREAM/TETRA已经运行并准入一个保守资源偏序seed；同一个p0000参数标签不等于同一个完整执行图，不能拿该seed与canonical C最优直接宣布击败强P0。**M0内部实现资格已有证据，限定NPE跨工具运行因当前WSL访问拒绝尚缺；完整P0组合及Hcompiler未完成，M1整门和M2不通过。** 下一步在R13内优先补共同计划/地址/顺序能力与真实P0预算轨迹，按结果决定是否继续算法投入；未运行完整MLP性能六配置。[下一步资格合同](r13/p0_qualification_next.md)

下方R1–R12部分保留此前的历史更新；“本次未重跑”属于那次维护。本轮新运行分别归档于R13，没有覆盖R12结果或改写冻结实验。

## R1–R12完整进度与证伪边界

以下数字为原轮次的执行记录，本次维护核对报告与关键已存结果，**没有复跑 R1–R12 性能实验或重新执行 R12 求解器**。不能把报告中的 PASS 写成本次重新跑出的 PASS。

| 轮次 | 已完成的研究工作 | 有效结论与当前状态 |
|---|---|---|
| R1 | 原始 C1–C10 候选、责任边界与 10→5 选题筛选；D1–D5 是 C1–C5 的重命名。 | 没有性能闭环。remapper、3D 近存、阵列分区、direct fabric 等未被后续调度实验统一证伪；筛选淘汰与实验证伪分开。 |
| R2 | 21 点 toy 比较，定义 P1–P5：方差感知静态 memory plan、部分序动态派发、quasi-static 变体、方差计量、DAE 基线。 | 局部观察保留；“无复用无收益”“重尾必要”已被 R3 反证。15 个正式编号是候选条目数，不是 15 项完成实验或贡献。 |
| R3 | 3,920 次合成执行及精确四任务例、窗口/收费扫描。 | 无复用、有界轻抖动下固定期望 150→ready 140；每 task 收费 8 cycle 后 156。证明存在性，未证明真实来源图、复杂 C 或更大层级有净收益。 |
| R4 | 官方来源缩尺图，13,440 主执行、4,480 后验 priority 修正；强静态、exact 与 120 单动作反事实。 | 收费策略均未通过 5% 门；修正后最好约 +0.1968%，区间跨零。可行动等待不等于可恢复最终 elapsed；有限静态搜索不是全局最优。 |
| R5 | full-K/full-head 切片、bank/request/outstanding/credit/返回反压，7,094 主执行；另 928 驻留控制与 207 tiny 执行。 | 36 请求配置无 5% 达门，关闭已测通用 ready 候选。两 head/四 prepared token 静态驻留改善 7.155%–24.027%；仅该切片成立，不能外推完整 GDN 或自回归。 |
| R6 | Phoenix copy 功能与 host 计时语义、测量能力核查；完整 state 容量/生命周期审查。 | 有真实 copy 功能，无已选强静态残差证据。32 head 为 2 MiB state、24 层 48 MiB 不推出每 token 必走外存。此设备分支不是当前模型研究阻塞项。 |
| R7 | 固定输入/BO 的 4 次 1 GiB copy 与 4 次 INT8 GEMM，两个新进程/每 kernel；定位 profiler/kernel 缺口。 | 固定 fixture 数值通过，不是 BF16/完整模型、strong-static 或设备性能收益接受。保留功能成果，停止无对应研究问题的 SDK 扩张。 |
| R8 | Qwen down full K=9216、N=128、M=1/32 的分片/bytes 账本；18 CPU 数值比较；70 个单 payload 线性扩展。 | partial 是否必需取决于 mapping/数值许可/路径；容差通过不等于允许 split-K。安全偏序可由静态 wait/release 满足，37 个结构错误不是概率或硬件 bug。 |
| R9 | 两 cluster 各两核、自主单 EXT staged 路径；204 静态候选、180 paired blocks、2,880 单动作反事实。 | quiet C2K 47,776 vs C2N 55,912 cycle，静态流量取舍改善 14.5514%；主范围供给损失大但平均免费恢复上界约 1.6%–1.9%。收费回看最佳均值仅 0.0210%、区间跨零；35% 条件最大上界 5.1579%，严格关闭门未通过。 |
| R10 | 两套带宽比、各 960 静态候选，有限 credit/串联下界；新相位固定观察规则；1,104 保存轨迹。 | 部分大 gap 来自松下界；剩余约 10%–13% 上界不是收益。1,440 次观察、0 次实际改序，关闭该触发规则收益主张，未识别所有合法改序价值。 |
| R11 | 完整 32-head GDN 单层、四 token prefill 与 strict decode，76 数值 block、4 callback、122 保存轨迹审计。 | local state bytes 降低，但 quiet −0.015670637%、两背景约 −0.60%；cold-weight/staged ABI 下候选关闭。strict decode 调用清除 RF/VMEM 后两图相同，无合法驻留干预；不外推 warm/fused/跨层合同。 |
| R12 | 固定公开来源、独立环境和实际 STREAM/TETRA/tt-npe 工具；路由/完成小图、完整 MLP 工作量、共享资源探针与 affine 红队。 | 接受具名离线子项；尚无合格的完整 Wormhole 强 P0、P1 模型性能比较或 H1/H2 支持。真实 2conv 必传 full-payload 的推断被反证并撤回，不能把条件干预包装为成本修复。 |

## R12 新增证据：做到了哪一层

| 对象与结果入口 | R12 实际完成 | 解释边界 |
|---|---|---|
| [来源与阅读覆盖](r12/reading_coverage.md)、[工作量](r12/artifacts/workload_intake.json) | 证据包六文件全文、五项登记原字节 hash 匹配；完整 Qwen MLP H=2560/I=9216，三权重共 141,557,760 B（135 MiB），M=1/32/128 的 MAC 分别为 70,778,880 / 2,264,924,160 / 9,059,696,640。 | 只证明冻结来源与逻辑工作量。四份历史 Git 内容按声明的 LF/CRLF 表示匹配，工作树原字节仅 2/4 匹配；没有下载权重或完成 BF16 kernel 数值/布局证明。 |
| [路由与候选摘要](r12/artifacts/qualification_summary.json) | 28,800 个端点/NoC 组合；96 个预登记离散计划，每计划 12,288 B payload；最大有向链路流量为 132–202 flit，包含 load/peer/output 请求、响应与 ACK。 | 未计通知和 credit-return 包、NIU 链路/服务、router credit、compute/controller 时间。不是 96 个完整 elapsed 的强静态搜索结果；旧 66/33 request-only 见证也不等于 2 倍模块加速。 |
| [事件独立结果](r12/artifacts/independent_checks.json) | 两链、两代、两源 slot 加独立接收/输出 span：56 事件、10 条登记 HB 义务全部由可达性证明；四类错误规则均被拒绝。每事件优先生成的 56 条合法序数值回放通过。 | 56 次回放不是全部拓扑序穷举；DAG 证明限定声明的事件抽象，不证明 CPU↔NIU 原生顺序、物理 credit/网络活性。新一代 compute 可早于旧 ACK，不能全局串行化不同完成作用域。 |
| [原始 TETRA](r12/results/baseline_smoke/result.json)、[基线审计](r12/baseline_source_audit.md) | 真正 SCIP 整数 sentinel 与官方 2conv 完整分析管线通过；导出 5 条真实 transfer path，未改上游；原始 latency 为 12,808。 | 工具入口已通，generic/AIE 合同不能自动成为 Wormhole P0。既有 placement/routing、容量、DMA/BD/FIFO/lifetime 能力应吸收为基线，不能直接称新颖性。 |
| [共享资源探针](r12/shared_resource_probe.md)、[最终 affine 回执](r12/artifacts/shared_resource_affine_audit.json) | 显式 full-copy 合同下一个 128 bit/cycle bus 传 262,144 必需 bits 的 2,048 下界与 helper 512 不符；四条独立链路的 512 正控制成立。实际 2conv 的 z6/z13 都是 ox 空间分片；连续、对齐、同序 ownership 见证仅需六列 halo，共 49,152 远端 bits，必要服务界 384。 | 分配 footprint 不等于 consumer 数据需求。该见证足以撤回真实 2conv 的 2,048 无条件下界；512 未被否定，也未证明可实现。需区分数学最小需求与实际搬运合同。 |
| [保留的费用干预](r12/results/shared_resource_counterfactual/result.json) | 临时进程将具名 transfer 收费 512→2,048 后真实 TETRA 重新求解，得到 14,344；mapping/fusion 与原始相同。40 次 helper 调用中 8 次匹配，5 次来自 allocator。 | 原合同将 footprint 当 full all-gather 的前提被随后 affine 审计推翻。只保留 full-payload 合同下的条件性成本敏感度；不是已确认的 P0 修复、计划排序变化、H1 或 Wormhole 性能结果。 |
| [tt-npe 环境](r12/artifacts/npe_environment.json)、[Linux 说明](r12/linux_environment.md) | 固定官方源码在独立 Ubuntu 24.04/GCC12 构建；C++ 45/45、pytest 10/10；官方 Python API 示例估计 437 cycles。 | `ready_for_coarse_api_use=true`，但官方 CLI 的 Stats/DeviceStats 字段不匹配，整体验收 `passed=false`。golden=450 没有独立实测依据；API 粗模型和其测试不能代替完整 DFG timing/完成语义验证。 |

硬件来源核查还明确了 endpoint、共享域与物理 channel 的区别：同组多个 NIU 访问同一空间不提供独立带宽，低/高 1 GiB 又对应两个物理 channel，不能把整个组压成一条串行通道。公开 router inbound buffer/VC 保底/共享池参数已有依据；仍未明确的服务与 credit 时序应显式标为模型参数。详见 [硬件来源审计](r12/hardware_source_audit.md) 和 [R12 报告](r12/experiment_report.md)。

## R13 初始合同（已由上方实际进展更新）：多 tile 模型中的完成事件与联合静态编译

R12 冻结的 [预登记](r12/preregistration.json) 包含 board/harvest、native backend 与校准要求；[原回执](r12/artifacts/qualification_summary.json) 的 `G0_native=NOT_PASSED`、`G1/G2=NOT_TESTED`、`G3=NOT_OPEN` 保持原判。**用户此次明确的是研究方式变更：后续另立模型仿真合同，不等待板卡，也不把旧 native 门改称已经通过。** 硬件语义要来自固定公开依据；未公开的量采用明示假设、合理范围与敏感性分析。板卡数据如将来可得，可作为外部校验，当前缺少它不等于不能开展模型科研。

R13问题是：**在同一数值、工作量、初末位置、容量与硬件模型下，把逐 source-slice 的 consumer 需求、共享资源服务与分作用域 completion 引入强静态联合 placement/routing/send-window 后，是否改变所选合法计划，并带来超出正确重定向已有编译器的完整模块净收益？** 该问题已进入有限小图模型实验；完整模块仍未执行。

下一轮先完成源语义到模型动作的对应、逐需求/资源守恒、容量/完成/复用/终止的独立检查，再将现有 STREAM/TETRA 能力正确移植并强化为 P0；对更精确资源与 completion 的作用作同合同消融。用小规模 exact/必要下界、独立实现和参数敏感性区分模型错误、基线不足与可重复的计划变化。**[R13 proposal contract](r13/proposal_contract.md) 已确定为执行合同**，规定 M0 模型资格、M1 可识别残差、M2 完整模块与稳健性三门；Hmodel 的模型排序证据与 Hcompiler 的额外搜索价值分别判定。该段是启动时合同；实际执行状态以本表顶部 R13 第一阶段和 [R13 报告](r13/experiment_report.md) 为准。

若正确重定向的已有方法已经吸收全部收益，接受 H0 或归入工程结果；若额外建模改变排名但无完整模块净收益，记录负结果。只有强 P1 之后出现具名残差与可行动信息，才另开收费有界 runtime/Rh；当前不启动新硬件 scheduler。旧 R5 ready、R10 观察规则和 R11 cold-weight 驻留候选保持各自关闭状态。

## 本次阅读覆盖与执行分级

| 材料 | 本次维护实际检查 | 依据与边界 |
|---|---|---|
| 本文件与 [回溯台账](analysis/r1_r10_research_retrospective.md) 的更新前全文 | 完整阅读，含 R11 末尾追加；保存原字节快照并计算 hash。 | 历史叙事与当前决策分开；不丢弃旧判决。 |
| [R1 C1–C10 原定义](r1-base/redteam_claim_frameworks.md) 候选表及前 155 行；[R2 P1–P5](r2-ooo-npu/research.md) §九至§十一 | 阅读原始候选定义与边界。 | 15 个正式编号；D1–D5 不重复计数。未读取其他方案初稿、演示或解析副本。 |
| [R3](r3/experiment_report.md) §1–3、[R4](r4/experiment_report.md) §1–3.1、[R5](r5/experiment_report.md) §1–6 | 核对关键原报告段落及准确分母、收费与外推限制。 | 属于本次核对报告，历史执行数量不升级成本次复跑。 |
| [R6](r6/experiment_report.md) §1–4、[R7](r7/experiment_report.md) 问题/实现/结果/计量表、[R8](r8/experiment_report.md) 主结果与数值/偏序 | 核对原报告。 | 区分设备功能、host 秒数、逻辑 bytes、CPU 数值及抽象安全证明。 |
| [R9](r9/experiment_report.md) 主结果/单动作/敏感性、[R10](r10/experiment_report.md) 全文、[R11](r11/experiment_report.md) 全文 | 核对原报告、固定路径及 ABI 边界。 | 大供给损失与恢复上界分开；R10 零动作、R11 完整模块负结果保留。 |
| [R12](r12/experiment_report.md)、[独立研究审计](r12/independent_research_audit.md)、[共享资源探针](r12/shared_resource_probe.md)、[预登记](r12/preregistration.json) | 本次完整阅读；核对已存 qualification、NPE 环境等 JSON 字段。 | R12 实际源码/求解/affine 执行是已完成实验事实；此轮维护没有重跑，2conv 初始推断撤回。 |
| 本次实际执行 | 两份历史快照与原正文保留检查；输入证据包五项 hash；R12 冻结检查器核对 52 项通过；R13 完成 DES、独立回放、数据审计、576 项名义全集和 168 项见证回放。 | 没有板卡/NPE成功执行、没有完整MLP性能仿真或R1–R12历史性能复跑。R1–R12冻结报告、代码、结果和hash文件不改。 |

## 历史正文：截至 R11 的逐轮证据与当时决策

以下保留更新前正文。其范围与建议均为历史记录；尤其旧 TARS/Phoenix 入口和真实板卡门不再约束当前模型仿真主线。原始标题为“科研方向探索进度表”。

更新：2026-09-05，用户已确认R8范围与推进顺序。**科研主线：以每cluster两核为基点，建立多cluster NPU目标合同，定位强静态优化后具体共享资源问题，再决定是否需要有限运行时硬件。** 多chip/chiplet作为证据驱动的后续扩展；Phoenix是辅助测量平台。R7功能结果接受、R5已测ready候选继续关闭；R8已完成来源/静态分片账本、CPU数值与单payload偏序闭环；R8尚无真实残差或性能结论；用户现已授权R9自主建立参考硬件规格并实施模型实验，后续替换真实TARS，当前不再等待TARS入口。

Verdict 中“支持/否定”只作用于该行实验边界。R1 的外部编译器事实是历史记录；R6只读核查的 `D:/workspace/llmSched` 是另一个旧版离线compiler根，未认证R1 TARS当前实现。R6有真实NPU copy功能证据，仍无研究kernel/完整4B模型性能、RTL或PPA验收。R5原版保存在 [R5快照](r6/history/r5_research_progress.md)，R6原版已在本次修改前保存在 [R6快照](r7/history/r6_research_progress.md)；父子关系见 [R6 lineage](r6/history_lineage.json)与[R7 lineage](r7/history_lineage.json)。R7单GEMM是INT8固定fixture，非BF16/GDN/完整模型或strong-static性能验收。

历史措辞补注：R5行的约33%是**不同环境各自静态重训后的投影模型差分**，不是固定binary的实机干扰实测。为保留已冻结历史，原行不改写；R7未采集新的受控干扰残差。

当前范围与维护规则：单cluster双核为局部控制组；多cluster、每cluster两核为优先待建研究合同，尚非已实现目标；R3多chip是抽象模型，不能等同chiplet封装/协议验证。R4/R5的强化负结果主要覆盖单cluster双核已测包络，不外推多cluster全域。下一步先做目标资源/数据移动/可见性与合法静态动作核验，只有能回答具名目标问题时才继续Phoenix profiler/SDK工作。

本次用户对齐与新任务交接见 [R8 continuation brief](r8/continuation_brief.md)。修改根表前已保存 [R7原版快照](r8/history/r7_research_progress.md)，新旧映射见 [handoff integrity](r8/handoff_integrity.json)，历史复核用 `python -X utf8 -B r8/check_history.py`；不重写R4–R7旧清单。

| Round | Research Question | Hypothesis | Experiment | Key Result | Verdict | Remaining Uncertainty | Next Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R1：边界与候选 | 编译器已决定什么，哪些硬件缺口值得先测？ | remap、generation lease、近存 attention、阵列分区、双核 fabric 各有可测收益或安全作用。 | 历史源码/IR/Descriptor/RTL 文档审计，10→5 候选与反证门；**没有性能仿真闭环**。 | 记录了 memory/dependency/execution authority；指出重复寻址、未接通的性能计数器等缺口。五方案收益均未测。 | **继承合同与证据分级；候选尚未得到收益支持。** | 当前外部实现是否变化；真实 bank、流量、hazard、利用率和硬件成本。 | 先问静态计划后是否还有值得动态处理的信息，不继承 R1 的架构优先级。 |
| R2：原始探索 | 固定 mapping 的动态派发何时超过 self-timed 固定资源序？ | 机会主要依赖 memory reuse、重尾与 DMA 仲裁。 | 对称 LOAD→COMP toy，21 表格点×200 paired trials；弱静态列表、免费动态、无物理容量。 | 表格点可复现，最高局部改善约4.521%；但实验变化同时混入 compute 噪声/均值变化等因素。 | **保留局部观察；撤回必要条件与“最优静态/oracle”标签。** | 是否为生成器限制、静态不足、缺少异构资源和不公平容量比较。 | 用精确反例审查普遍命题，并建立显式地址与共同成本合同。 |
| R2→R3：回溯反证 | 无复用、非重尾是否真的不可能有动态信息价值？ | “无复用无收益”“重尾必要”是普遍命题。 | 4任务、两独立 producer、共享 VPU；等概率(80,120)/(120,80)，consumer各20，无 alias。 | 最优固定期望150，ready140，改善6.667%；原 toy 另有同刻完成编号导致220/120偏差。 | **两个必要条件被严格反例否定；特定图的信息价值得到支持。** | 存在性不代表真实 workload 的频率、收益规模或可承受成本。 | 修复批量完成语义，在同合同、强一些的静态与收费动态上扩大覆盖。 |
| R3：存在性到范围 | 动态的局部信息价值能否推广，复杂策略是否值得？ | 轻量 ready B 能稳定超过静态；age/pressure C 或更大层级可能更好。 | 49配置×20 test seeds×A/A2/B/C=3,920执行；8候选静态池；窗口/成本/粒度/层级扫描。 | B对A2：10正/17负/22零；C无配置均值优于B；A2有11配置慢于A。Prefill +0.919%但A已更快；DiT +0.281%；两chip通信−7.530%。 | **仅保留有条件的信息价值；拒绝扩张当前C与“规模越大越值钱”。** | 手写motif、人工服务、整task资源；静态候选不足；有限窗口外仍有O(N+E)历史。 | 先导出官方模型子图、数值与更强静态，收益门通过后才谈有限总事件硬件。 |
| R4：真实来源、强静态与因果机会 | 官方来源、融合/预取/双缓冲/地址合法之后，ready能否把等待变成净收益？ | 有合法替代任务的等待通常有端到端价值，收费动态可超过强化静态。 | 7种源码缩尺图；70×32×6=13,440主执行；24-priority+128局部移动、独立train/validation/test；tiny exact；120单动作反事实。 | B2/H2/B8的70配置均值全负；机会并集平均占延迟0.917%，干预16改善/84变慢/20不变；7任务exact：S=B=clairvoyant=3665。 | **当前收费收益主张未过门；“有机会就有收益”被反例及干预否定。** | 全宽tensor/state/weight、合法kernel tiling、bank/beat/credit/内生排队未建模；强静态仍非全图最优；无设备校准。 | 区分机制价值小与模型遗漏关键资源行为，优先寻找真实瓶颈，暂停新scheduler。 |
| R4：提示一致性后验检查 | 主B的退化是否只是没有继承S优化后的优先级？ | 用名义静态dispatch序形成priority可消除主要退化并恢复净收益。 | 同70配置/32 test seeds，冻结名义hint后4,480执行；另从训练trace补静态候选。 | 校正减少部分退化；收费B_order2：2正/68负，最好+0.1968%，95%[-0.1522,+0.5458]；没有配置通过5%门。 | **支持“hint影响退化”；仍未支持收费机制；这是后验探索。** | 复用test不能当独立确认；未穷尽在线policy；2cycle只是研究成本假设，无PPA。 | 新实验使用新seed/预登记，以服务行为和信息价值作消融，不继续调参追正结果。 |
| R5：全宽与资源细化 | R4负结果来自机制价值小，还是遗漏了关键资源行为？ | 全K/full-head、bank、outstanding与返回反压可能产生强静态后可恢复的损失。 | 3全宽来源切片×12request配置+6atomic对照，7,094执行；布局/预取/顺序重训，独立train/val/test；tiny20序全枚举；全部1,296 fine test逐request审计。 | 干扰下投影延迟增加约33%，但B0无收益或退化；36组无5%达门，B2最好+0.1821%且CI跨零；quiet固定流量重排上限Qwen1.43%、FLUX3.96%。 | **支持资源行为影响执行；否定已测通用ready能提供足够净收益。A/B可同时成立，未证明真实机器的B。** | 参数未校准、source slice非整模型、有限静态搜索、fabric非完整NoC；GDN原lowering还有静态驻留空间。 | 不增加scheduler；先以合法RF驻留检查GDN损失是否已能静态消除。 |
| R5：红队后的compiler控制 | GDN每token state SRAM往返是否必要？ | 既有RF可保留这两个head跨4个prepared token，损失可能属于静态memory planning。 | 后验控制保留原主结果；新train3200/val3300/test3400系列、同静态搜索、4配置/928执行；逐token输出及Sfinal合同、全request独立审计。 | 合法RF驻留改善7.155%–24.027%（无扰动16.013%）；resident B0=S，B2均退化。 | **支持该切片的compiler驻留优化；继续拒绝通用ready硬件提案。** | 仅2head与prepared4token；真实32head、跨层RF占用及自回归输入时序未验证；无设备/PPA。 | 按设备测量合同检查strong static之后的剩余损失；没有稳定残差则关闭，有静态解则转compiler/co-design，满足观测/有限状态/净收益门才提出新机制。 |
| R6：真实执行与测量能力 | 当前到底能在什么真实目标上执行，现有接口能否识别强静态后的残差？ | 本机可能有可执行NPU，但设备存在和自测PASSED不足以建立资源/性能合同。 | 只读设备/SDK/compiler/RTL盘点；预登记后Phoenix vendor verify一次、1GiB copy df-bw一次；精确XRT源码对照；原始回执hash与独立红队。 | Phoenix Ready且copy逐268435456个int32比较通过；0.359610s为host launch→wait2，GS/s标签来自1GiB常量/host秒；没有实际bytes、compute-active、request/limit观测，0干扰pair。 | **接受设备copy功能证据；Refine measurement/kernel access。真实残差未识别，未新增性能否定结论。** | 合法dtype/compute kernel与compiler导出、固定BO/input/频率、计数器定义；R1 TARS当前入口仍未知。 | 先取得匹配目标的kernel SDK和trace接口，校验空运行/已知bytes/单compute/采集开销，再冻结strong-static配对实验；不扩scheduler。 |
| R6：驻留外推与研究门 | R5两个head四prepared token能否代表真实跨层/跨token驻留，什么证据才能重开机制？ | 完整autoregressive的state集合与输入时序不同；H1与因果恢复不能由切片正结果推定。 | 官方固定config/cache/generation来源；独立shape/生命周期容量复算；测量合同校验与故障fixture，绑定selected-static残差/动态对照。 | 24 GDN层×32head×128×128×4B=48MiB/B=1；同层相邻token之间有31个其他层forward；不能推出每token外存traffic。fixture只验软件，不计设备样本。 | **拒绝整模型RF驻留直接外推；保留R5静态控制正结果。H1/H3未测，机制门关闭。** | 真实RF可访问性、跨kernel持久性、spill/其他存储层级和强静态已消除多少仍未知。 | 先测selected-static固定binary残差；仅在独立test/session的真实残差、因果观测、有限动作及收费净收益都成立后提出机制。 |
| R7：固定功能入口 | 当前旧Phoenix栈能否在不升级driver下执行自行固定输入、BO与数值检查的copy及单compute？ | 公共XRT ABI与早期官方Phoenix预构建GEMM可形成完整host/指令/布局合同。 | 25份精确头文件+426个DLL导出构建局部host；原厂C++独立核对200B序列/4MiB packing/oracle；两个新进程每kernel 1+3次实机。 | 4次1GiB copy各268435456words零差异；4次INT8 1×2048×2048 GEMM各2048outputs与oracle完全相同；binary/input/指令hash及BO地址保存。 | **Accept固定功能入口；支持本机该合同的兼容性。不是strong-static或收益通过。** | 仅预构建device binary、固定小值fixture；BF16/FP32、可调device编译、运行频率及受控背景未验证；调用次序耗时变化原因不明。 | 已不必重复泛化SDK盘点；先把通过数值的kernel接入同context profiler与合法静态编译接口。 |
| R7：计量入口与停止门 | 现有timestamp/trace导出能否给最低观测，缺口能否定位到明确接口？ | 导出存在可能仅是桩；Windows专用AIE profiler依赖匹配插件、kernel和事件合同。 | 安装DLL导出RVA/机器码审计；同SHA Windows profiler源码；16个xclbin元数据检查；独立回执/输出红队。 | 通用timestamp/trace返回常量或直接return；其他4个xclbin有XDP_KERNEL，但已测copy/GEMM无；限定目录缺匹配插件/metadata。仅host elapsed，无actual bytes/compute-active/request。 | **Refine profiling/compiler合同；完整校准与机制门未过。缺测量不判真实残差为零。** | 真device no-op、instrumentation开销、counter/reset/wrap/时钟域及强静态搜索未建立；0确认/干扰/静态/动态比较。 | 取得适配Phoenix的XDP/AI Engine profiler工程与device编译入口；完成校准后再冻结strong-static配对实验，R5 ready仍关闭。 |

| R7→R8：范围对齐（计划） | 下一轮以什么目标层级研究强静态之后的共享资源问题？ | 每cluster两核的多cluster合同可提供明确的跨域资源/可见性问题；是否需动态机制仍待证据。 | 用户确认研究主线；复核历史层级范围与R7能力，规划目标合同、数据移动/依赖账本、静态控制及有界验证路径；尚未执行R8实验。 | 已对齐优先级：多cluster目标合同在前，Phoenix测量辅助在后；多chiplet尚无具体实现合同。 | **Accept范围对齐；R8研究假设待测，不新增性能结论。** | 当前权威TARS入口、共享资源拓扑、跨cluster payload/completion合同、合法静态空间及目标可观测性。 | 新任务直接开展R8：建立合同并选一个最有判别力的共享资源问题；完成预登记、最小验证和红队闭环，继续维护本表。 |
| R8：静态分片与资源账本 | 两cluster各两核的跨域partial是否为工作量必需，还是静态mapping/路径取舍？ | Output-shard可免partial；split-K的价值依赖输入复制、route及数值许可，不能直接推出动态残差。 | 事前登记；Qwen down fullK9216/N128、M1/32，3种mapping×2M的6账本；20core/100分配；3seeds×2M×3mapping的18 CPU数值比较，独立复算。 | 同4核权重2359296B；M32单播输入N分片2359296B、K分片1179648B，后者增16384B partial；全部诊断容差通过，但6个split-K结果均非bitwise，抵消反例顺序1/split0/FP64为2。 | **Accept来源约束账本；Refine目标静态准入，不作性能排名。** | 当前TARS根、multicast/staging/peer路线、VMEM保留区和静态搜索；M1非历史native geometry，split-K数值许可未证。 | 先确认当前target及实际共享DMA/外存路径，允许target支持的mapping/layout/驻留/预取与既有仲裁；选择strong-static后才测真实残差。 |
| R8：payload可见性与复用 | DMA接受/最后读/目标可见能否未经证明合并为consumer和slot复用的完成信号？ | 精确静态wait/release或等价阻塞合同足以使有限单payload抽象安全；过早放行可构造错误。 | 五种七事件偏序全部70线性扩展，逐条执行sentinel读取；独立checker复算全部记录及witness，没有时序或设备实验。 | safe5/0错、保守release4/0错；early-event40/26错、early-source6/1错、early-destination15/10错；37是结构错误数非概率。 | **Accept有限安全证书与反例；Reject由此推出target bug、新scheduler或真实收益。** | 仅单次已produce-visible payload；未验两个partial并发、完整reduction/最终store、credit/反压、重试和RTL；真实残差未测。 | 获取目标completion语义并绑定具名span/last-reader；当前停止扩sim/Phoenix SDK，R5通用ready保持关闭，保留未测多cluster空间。 |
| R8→R9：自主研究规格（计划） | 缺少当前TARS参数时，能否先以明确参考硬件完成共享资源残差研究？ | 两cluster各两核的自主规格可支持条件性架构判别；真实性与迁移性后续由TARS替换校准。 | 用户明确授权agent建模并在新任务开始实施；保存R8父快照与R9交接，待冻结参数、strong-static和判别实验。 | 推进边界已变更：TARS路径不再阻塞参考模型；规格/能力/参数均显式假设，不冒充目标事实；尚无R9实验结果。 | **Accept自主规格与实施范围；R9研究假设待测。** | 参考硬件参数敏感性、合法静态空间、供给与可恢复损失分解、后续真实目标迁移。 | 新任务直接建立数值合同、实现最小资源路径、训练强静态并运行判别实验；不继续环境搭建，不预设新scheduler。 |
| R9：参考硬件与共享供给 | 自主两cluster各两核的共享EXT路径中，强静态后的干扰损失属于供给还是新增改序空间？ | mapping/广播/tiling/并发先于机制；大变慢可与小可恢复空间并存。 | 冻结单路径数值合同；Qwen down M32/fullK9216/N128；204静态候选、独立8train/8validation、两组各30paired blocks/条件；608轨迹477312requests独立审计。 | 同一C2K/K256/双buffer方案在三环境均被选；quiet47776cycle，20%背景慢24.75%/25.31%，35%慢52.81%/53.01%；重训消除0；平均免费恢复上界约1.6%–1.9%。 | **Accept条件性供给与强静态证据；不是当前TARS或实机残差。** | 理想DMA/operand端口、固定绝对预留过程、有限静态池、数值与gather/广播的真实目标准入。 | 集中硬件合同可替换；保留真实校准门，不回到Phoenix SDK，不把供给损失当scheduler收益。 |
| R9：单动作筛查与失效范围 | 既有work-conserving仲裁外的一次合法DMA改序能否达到5%收费收益，能否统一关闭更广候选？ | 只有改变最终结束且收益足够的因果动作才值得新增机制；资源上界大只是未决。 | 2880次同合同单动作反事实，0/8cycle收费；tiny两序两相位exact、7故障fixture；9个事前单参数敏感性。 | 收费回看最佳均值最高0.0210%且CI跨0；35%条件为0；但35%免费恢复上界最大5.1579%，EXT128/DMA32敏感性最大19.8588%/15.8944%。 | **Reject已测动作族5%收益主张；Refine严格逐phase关闭门及带宽比例范围，不接受新机制。** | 回看选择非causal；上界松弛、有限credit串联服务与静态搜索不足尚未区分；大gap不是收益。 | 先在具名EXT/DMA比例范围加强串联资源下界与静态交互，再以新相位判别有限因果动作；不追极端参数、不外推关闭所有多cluster。 |


证据链为：**R1确定责任边界 → R2暴露toy局限 → R3证明存在但不能推广 → R4得到有来源、有因果检查的负结果 → R5资源细化仍未救活ready，并识别静态驻留解释 → R6找到真实Phoenix并执行copy，但计量不足 → R7取得固定copy/INT8 GEMM数值实证，并把观测缺口定位到profiler/kernel/编译合同 → 用户确认回到每cluster两核的多cluster目标合同，先定位具体共享资源问题，再选择有对应性的计量/静态控制路径。** 旧proposal的收益前置门没有通过；本轮没有为取得正结果另找架构。

来源：[R1/R2原文与审计](analysis/r1_r2_audit.md)、[R3报告](r3/experiment_report.md)、[R4报告](r4/experiment_report.md)、[R4独立红队](r4/redteam_report.md)、[历史审计与复算](r5/history_audit.md)、[R5完整报告](r5/experiment_report.md)、[R5独立红队](r5/redteam_report.md)、[设备测量门](r5/measurement_gate.md)、[R6完整报告](r6/experiment_report.md)、[R6独立红队](r6/redteam_report.md)、[R7完整报告](r7/experiment_report.md)、[R7独立红队](r7/redteam_report.md)。后续结果继续追加，保留原行边界与淘汰决定，不用新的正结果改写旧负结果。

R8实际结果与新父子关系：[完整报告](r8/experiment_report.md)、[目标合同](r8/target_contract.json)、[独立红队](r8/redteam_report.md)、[R8 lineage](r8/history_lineage.json)。当前入口需求收敛为权威TARS顶层checkout路径；历史与R8分别用 `r8/check_history.py`、`r8/check_results.py` 只读复核。

R9用户授权与新任务交接：[continuation brief](r9/continuation_brief.md)、[handoff integrity](r9/handoff_integrity.json)。本次只记录范围变更与计划，R9实际结果另行追加。

R9实际实施与模型内判决：[完整报告](r9/experiment_report.md)、[参考硬件](r9/reference_hardware.json)、[独立红队](r9/redteam_report.md)、[结果清单](r9/results_manifest.json)、[R9 lineage](r9/history_lineage.json)。主参考已测单动作不支持新机制；35%严格关闭门与EXT/DMA比例范围保持未决。

| R10：串联供给与静态交互（计划） | EXT128与DMA32的R9大恢复上界属于松下界、静态不足还是可行动空间？ | 有限credit在EXT停供期限制local DMA供给；静态联合参数可能消除额外elapsed。 | 已保存R9父快照；新预登记960候选联合搜索、8/8新train/validation与两组30paired blocks；先证明下界再决定因果动作。 | R9/R8三个冻结与历史check均PASS；R10已开始实施，未提前判收益。 | Refine具名带宽比例路径，不重写R9关闭门。 | 更紧下界的tightness、有限池遗漏及收费因果动作空间；无真实硬件或PPA。 | 完成独立复算与新相位确认，按条件关闭、转compiler或测试有限动作。 |


| R10：更紧下界与联合静态 | EXT128/DMA32的大恢复上界中能证明多少只是资源下界松弛，静态交互还能消除多少elapsed？ | 有限credit在EXT停供期限制local供给，联合驻留/布局/预取/顺序可能消除其余损失。 | 两hardware各960合法候选、8/8新train/validation、各29 shortlist、360独立配对块；证明并独立实现credit/停供/依赖下界。 | EXT128旧静态上界均值约18%收紧至9.62%–11.49%；新静态仍约9.79%–11.47%。DMA32/20%仅约0.106%静态改善，35%为0；新上界仍约11.33%–13.15%。 | Accept部分松下界解释；Refine残余，不支持静态已消除大gap或全部不可避免供给。 | 有限静态池、串联下界仍松，所有干扰条件仍未过逐block小于5%关闭门；非真实TARS证据。 | 以完整外存Y终点的小图credit/两资源顺序证书收紧未决空间，不把upper当收益。 |
| R10：新相位收费观察规则 | 可观测busy/idle状态的一次有限EXT改序规则能否在强静态后达到机制门？ | 四个固定观察点可能找到idle接收cluster，收费改序后仍有净elapsed收益。 | 独立预登记新8/8/30/30相位；360 baseline/causal测试配对，2cycle每观察与8cycle动作；720详细trace独立复核，A/B共1440次elapsed重放。 | 1440观察全部另一侧busy，0次实际改序，全部只收8cycle；最高干扰均值0.002796%且CI跨0；quiet回退最高0.027226%。A/B合计1104 trace、860736 requests通过。 | Reject该观察规则的5%收益主张；未有效测试实际触发改序价值，不接受最小硬件机制。 | 平均约10%–13%剩余upper仍可能是松界、静态遗漏或动态空间；模拟session不等于实机，无PPA。 | 保留负结果与未决，不用同批test调阈值；新动作须先证明可触发与端到端作用，再新登记新相位。 |

R10实际结果：[完整报告](r10/experiment_report.md)、[下界证明](r10/bound_proof.md)、[独立复核与红队](r10/redteam_report.md)、[R10 lineage](r10/history_lineage.json)、[结果清单](r10/results_manifest.json)。部分松下界已确认，剩余动态空间未判明；本轮不接受新机制。


| R10→R11：完整单层驻留验证（计划） | R5小切片静态驻留收益在完整GDN单层和真实输入顺序下还能否成立？ | 合法保留state可能减少重复本地搬运；完整容量和token生命周期也可能消除原收益。 | 用户确认只验证驻留；暂停动态选序；保存R10父快照，建立R11交接；新任务先预登记再实施数值、容量、traffic、elapsed和独立复核。 | 已明确窄范围与成立/关闭判决；尚无R11实验结果。 | Accept实验范围；不预判收益，不并行启动分片、新存储硬件或scheduler。 | 完整32heads容量、真实prepared输入可得性、prefill与decode适用差异及共同成本。 | 新任务完成实验，给出成立可继续或未获支持关闭的具名结论，不能只交计划。 |

R11用户确认的窄范围与直接实施交接：[continuation brief](r11/continuation_brief.md)、[handoff integrity](r11/handoff_integrity.json)。

| R11：完整GDN单层静态驻留 | 完整32-head GDN单层、合法已知四token输入下，保留state能否在共同成本和强静态baseline上减少净elapsed；严格decode是否仍有合法干预？ | Prefill可减少每token state读写；严格decode可能因输入释放和RF clobber不具备同样复用。 | 预登记完整 qkv/z/a/b、conv、gated-delta、norm、out module；76数值prefill blocks、4 decode callback representatives；有限静态计划独立train/validation；quiet与两组30 paired background blocks；122 traces独立复核。 | 数值/容量/生命周期/审计均PASS；32-head state 2,097,152 B，local state read/write 16,777,216→4,194,304 B，external 88,863,488 B共同；quiet −0.015670637%；A −0.599174254% CI [−0.610049107,−0.588299401]；B −0.605967308% CI [−0.617565500,−0.594369116]；decode graphs identical。 | **Prefill：本轮未获支持，方向关闭；decode：本轮未获支持，方向关闭。** 关闭该完整模块、cold-weight、staged ABI候选，不声称所有驻留数学不可能。 | 真实TARS/Phoenix kernel、warm-weight、跨层融合/存储合同未测；官方prefill chunk kernel与设备计量未执行；结果是参考模型证据。 | 停止该候选投入与动态机制扩张；保留原始证据。只有新硬件/融合/权重驻留合同和新的可判别问题，才另行预登记，不用本轮负结果外推全域。 |

R11实际结果与证据：[完整报告](r11/experiment_report.md)、[原始结果](r11/results.json)、[独立审计](r11/independent_audit.md)、[数值复核](r11/numerical_results.json)、[R11 successor](r11/successor_research_progress.md)、[最终 lineage](r11/history_lineage_final.json)。
