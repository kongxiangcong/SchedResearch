# R1–R13 科研回溯：proposal 台账、收敛判断与模型研究主线

更新：2026-09-08。文件名保留历史 `r1_r10`，当前范围已经覆盖 R1–R12。**下一轮以公开架构依据下的硬件模型仿真为研究方式，研究强静态联合计算映射、张量放置、NoC 路径与发送窗口，以及共享资源和分作用域 completion 对完整模块执行的影响。** 用户明确没有 Wormhole 设备，不要求先取得真实板卡。现有 R12 环境与探针允许继续模型研究；尚不足以宣称强 Wormhole P0 已准入、P1/H1 已成立，或立即开发 Rh。

本次完整阅读更新前两份活动台账，回到 R1/R2 原始候选与 R3–R12 关键报告/结果核对；没有重跑历史性能实验。详细逐文件阅读范围、结果入口和执行分级见 [当前进度表](../research_progress.md)。更新前原字节保存在 [本文件快照](../r13/history/retrospective_before_r13.md)，SHA-256 `5e9104aa406887c7452b438df267a72cdca523a43c4937d24513f6b4e1249a5b`；[进度表快照](../r13/history/research_progress_before_r13.md) 为 `4b7698a7a4a17208925d098ede7555b7823cbc34a966aa1fbd767bfae1e384ab`。R1–R12 冻结报告、代码、合同、结果与 hash 文件不改。本文后半的旧 §1–9 是历史原文，其“当前”“下一步”均为当时决策，不继续约束本轮方向。

## R13 第一阶段追加：模型可运行，尚无新算法结论

2026-09-08，已在新会话实际实现参考硬件DES、独立tick检查器和16B数据/epoch审计，并接通真实TETRA来源seed。576项冻结有限小图全集和168次预选见证回放全部合法，名义最优81136 tick（2253.7778 model cycles）；最少总流量按登记规则选出的84124 tick计划比最优慢3.6827%。这是**局部Hmodel估价边界**，不能直接归于编译算法。依赖/latency下界估价的最小并列项包含最优，故其问题是分辨力和打平，不能说所有粗估价都有严格排序反转。[实际报告](../r13/experiment_report.md)、[独立全表核查](../r13/artifacts/micro_independent_analysis.json)

反证同样保留：预选等总协议流量的路径对名义输出持平，分离输入channel在26参数点全部持平。source合法提前复用相对保守ACK等待名义改善3.8495%，但强P0也拥有此能力，且BN=1时改善为0。没有将这项消融当作新方法收益；26点也未测试exact计划的失配稳健性。

**当前门：M0内部实现资格已有证据，限定NPE跨工具执行因WSL访问拒绝尚缺；完整强P0组合和Hcompiler未完成，M1整门/M2未通过。** 一个保守TETRA seed的资源偏序并不与canonical C同空间，不能以其较长时间当作弱分母。下一步只补共同计划/地址/顺序能力和真实P0搜索轨迹，再决定算法残差；不启动新增runtime或完整MLP性能六配置。[下一步资格合同](../r13/p0_qualification_next.md)

以下R1–R12重审和旧轮次正文继续作为历史记录保留；它们的更新措辞不覆盖本节新增的R13执行事实。

## R1–R12重审时的判断：问题已收窄，尚无新的收益结论

1. **历史实验没有证明动态调度普遍无效，也没有证明公开多 tile/NoC 架构上的强静态已经足够。** R3 小图证明信息价值可存在；R4/R5 关闭的是已测通用 ready，R9 关闭具名回看动作收益主张，R10 的触发器根本没有改序，R11 关闭完整 GDN cold-weight/staged ABI 的驻留候选。每个判决只在其硬件、工作量、数值和合法动作合同内成立。
2. **旧模型不是一条连续逼近 Wormhole 的模型链。** R5 有 bank、逐请求、outstanding、credit 与反压，不能说“没有通信”；R8 比较 peer/staging 账本，R9/R10 又固定为单 EXT 写回再读，R11 改为双核 staged ABI。真实 NoC 路径、分布式 controller/channel 与 completion 作用域没有持续进入同一联合优化空间。重新建模有理由，但模型更细本身不保证新贡献。
3. **R5 静态驻留正例已在 R11 的完整模块合同中失败，不能仍将其写成当前首选待验证方向。** 该结果不否定 warm-weight、融合、跨层或其他存储合同，却不足以支持继续延长同一候选。R9 的静态分片/traffic 结果保留为具体数据移动动机，不能与 R5 收益相加。
4. **R12 接通了真实软件工具与公开语义证据，但没有完成强目标基线或完整模块性能实验。** 96 个流量计划、56 个事件和 tt-npe API 粗估价不能代替完整 DFG 资源/完成模型。STREAM/TETRA 已有 placement/routing/容量/BD/DMA/FIFO/lifetime 相关能力；这些应先成为 P0，宽泛的“联合规划”“DFG 合同”“缩小等待范围”不能直接宣称原创。
5. **R12 红队撤回了一个看似支持新方向的真实 fixture 判断。** 2conv 中“分配完整缓冲区，所以必须完整 all-gather”不成立。这个反证要求下一轮从消费者实际访问集合推导远端数据需求，再估算资源负载；不能先调高费用再把分析周期变化称为发现。

来源分别为 [R3](../r3/experiment_report.md)、[R5](../r5/experiment_report.md)、[R9](../r9/experiment_report.md)、[R10](../r10/experiment_report.md)、[R11](../r11/experiment_report.md)、[R12](../r12/experiment_report.md) 与 [基线源码审计](../r12/baseline_source_audit.md)。上述是历史取证与本次范围判断，不是新一轮文献检索或性能结果。

## R1–R12 按轮次收敛

| 轮次 | 已得到的证据 | 不能跨出的边界 |
|---|---|---|
| R1 | 责任边界、C1–C10 及保留 D1–D5 的选题论证。 | 五个保留方向无性能闭环；被筛除与被实验证伪不同。 |
| R2 | toy 局部现象与 P1–P5 的原始定义。 | 无复用/重尾必要性和最优静态/oracle 标签已撤回。 |
| R3 | 3,920 合成执行；精确例固定 150、免费 ready 140、每 task 加 8 cycle 后 156。 | 存在性不等于可承受成本或实际模块收益，有限窗口外仍有全图历史状态。 |
| R4 | 来源缩尺图、强静态/因果检查，13,440 主执行与 4,480 priority 修正。 | 无收费方案通过 5% 门；后验修正不是独立确认，全宽和完整 NoC 未建模。 |
| R5 | 全宽来源切片与请求资源细化，36 组无 5% 达门；两 head 静态驻留 7.155%–24.027%。 | 原通用 ready 关闭；驻留只是四个 prepared token 的局部控制，约 33% 投影差分不是固定 binary 设备干扰。 |
| R6 | Phoenix copy 功能与 host 时间；32-head/跨层 state 生命周期检查。 | 没有强静态残差或设备性能归因；不能把 48 MiB state 直接当每 token 外存量。 |
| R7 | 四次固定 copy、四次 INT8 GEMM 全量数值通过；profiler/编译接口缺口明确。 | 只有具名 fixture 功能，不是 BF16、研究 kernel 或 strong-static 性能接受；不阻塞模型路线。 |
| R8 | 分片与路径 bytes、18 CPU 数值比较、70 个单 payload 扩展。 | split-K 容差通过不等于数值许可；37 个错误序不是错误概率或设备故障。 |
| R9 | 204 静态候选；quiet C2K 比 C2N 快 14.5514%，属于固定 EXT/broadcast/staging 合同的静态流量选择。 | 大供给损失不是同量恢复机会；最好收费回看均值 0.0210%、CI 跨零，最大 5.1579% 上界使严格关闭门失败。 |
| R10 | 两硬件各 960 候选；部分松上界被 credit/串联下界解释；固定规则 1,440 观察。 | 0 次实际改序，不能说动作价值已被否定；残余约 10%–13% 平均上界不是加速。 |
| R11 | 完整 32-head GDN 数值/容量/生命周期及 122 保存轨迹审计；local state bytes 显著下降。 | quiet −0.015670637%、两背景约 −0.60%；strict decode 两图相同。关闭这一完整模块 cold-weight/staged ABI 驻留候选。 |
| R12 | 公开 Wormhole 来源、工具构建、实际 TETRA、完整 MLP 账本、路由/事件小图与反证。 | 工具/条件功能通过不等于完整目标模型或性能通过；真实 2conv full-copy 诊断撤回，native 旧门原判保留。 |

各轮详细条件与来源在 [进度表](../research_progress.md) 和本文后半历史条目。当前仍无得到充分证据支持的新增硬件收益 proposal；这只是成熟度判断，不把物理 PPA/板卡验收设为软件或架构模型论文的通用必要条件。

## 原始候选账本如何继承

正式编号仍为 **R1 C1–C10 十项 + R2 P1–P5 五项**；D1–D5 不另计。原定义可从当前仓库路径阅读：[R1 候选表](../r1-base/redteam_claim_frameworks.md)、[R2 §九–十一](../r2-ooo-npu/research.md)。后半旧表保存 15 项原记录；R11/R12 带来的状态更新如下。

| 候选 | 截至 R12 的状态变化 |
|---|---|
| R1 C1/D1、C3/D3、C4/D4、C5/D5 | remapper、3D 近存、阵列分区和原 direct fabric 主实验仍未完成。R12 引入真实 NoC 来源，不等于这些原机制获证或全部重开。 |
| R1 C2/D2 | R8 单 payload 与 R12 两代事件继续澄清 source-last-read、destination-visible、consumer-last-read 的安全义务；未证明必须新增 generation-lease 硬件，静态或已有 runtime 合同仍是强基线。 |
| R1 C6/C7/C8/C9/C10 | 原选题淘汰、合并或未测储备状态保持；不把后续调度负结果倒写成这些方向的性能试验。 |
| R2 P1 | 宽泛“memory plan→合法执行合同”原创性不能恢复。R5 具体驻留正例经 R11 完整模块未过门；R12 发现既有基线更强。新模型下具体联合优化问题可继续，但需独立识别额外耦合与净收益。 |
| R2 P2 | 已测 ready 与具名触发规则维持关闭。R12 未建立强 P1 后的残差，不开 Rh；没有全域不可能性结论。 |
| R2 P3 | 数据相关 quasi-static 变体仍未完成原工作量/性能验证，不因 P2 的规则化图结果被否定；本轮也不自动改成 MoE 主线。 |
| R2 P4 | Phoenix 功能/计量工作和 R12 工具链有成果，真实目标残差仍未测。用户现要求模型研究，可以由来源约束的服务模型与参数敏感性推进，不等待物理测量，也不声称模型等同实测。 |
| R2 P5 | DAE、预取、双缓冲、重叠以及既有 runtime 仲裁继续作为强基线；无独立新硬件贡献主张。 |

## R12 的实际成果与一次撤回

固定来源与工具入口已经建立：Windows 项目独立环境、固定 STREAM/TETRA，另有独立 WSL2 Ubuntu 24.04/GCC12 的 tt-npe。完整 Qwen MLP 的 H=2560/I=9216、135 MiB 三权重与 M=1/32/128 全工作量已核算，没有下载权重、执行完整 BF16 kernel 或证明原生布局。输入证据包六文件全文已读、五项登记原字节 hash 匹配；Qwen 历史四文件按明确 LF/CRLF 表示匹配，工作树原字节只有 2/4 匹配，不能把归一化结果写成 raw 全通过。[阅读覆盖](../r12/reading_coverage.md)、[工作量账本](../r12/workload_intake.md)

路由侧核对 28,800 个端点/NoC 组合；96 个离散计划各 12,288 B payload，最大有向链路 132–202 flit。账本包括 load、peer、output 的请求/响应/ACK，但未计通知/credit-return 包、NIU 服务、router credit、计算及 controller 时间。两链、两代、两源 slot 加独立接收/结果 span 的 56 事件，10 条已登记 HB 义务由可达性证明；四类错误规则被拒绝，另 56 条优先拓扑序数值回放通过。它们分别是流量与条件性功能证据，不能称 96 个完整时序计划的最优搜索或全部执行序的物理正确性验证。[原始摘要](../r12/artifacts/qualification_summary.json)、[独立结果](../r12/artifacts/independent_checks.json)

真实 SCIP/TETRA 官方 2conv 管线已通过，导出五条 transfer path，原始分析周期 12,808。共享 bus helper 按端点数量使用 `chains`：**若明确要求所有 262,144 bits 经过同一 128 bit/cycle bus，2,048 是乐观守恒下界，512 低计费；四条独立链路各分担四分之一则可以是 512。** 这一参数化反例成立，但实际 Tensor 与分配 footprint 本身没有定义这个完整远端需求合同。[探针与源码链](../r12/shared_resource_probe.md)

实际 2conv 最终 affine maps 把 Conv1 z6、Conv2 z13 都映射到 `ox`，不是输出 channel。两算子按相同 core 顺序作连续对齐四等分的合法 ownership 见证中，远端需求为六列 `{7,8,15,16,23,24}`，共 3,072 个 16-bit word，即 **49,152 bits / 128 = 384 个必要服务 cycles**。独立反向几何枚举得到相同结果。这个数学见证不证明现有 native 地址/搬运程序采用了 selective halo，却足以推翻“计算强制完整 262,144 bits 远程”的原断言。512 未被该界否定，也未证明能包含完整协议、局部复制、零填充与完成开销。[affine 回执](../r12/artifacts/shared_resource_affine_audit.json)、[独立审计](../r12/independent_research_audit.md)

在反证前已执行的临时费用 overlay 原样保留：具名 transfer 512→2,048 后重新运行真实 TETRA 得到 14,344，mapping/fusion 与原始相同；40 次 helper 调用中 8 次匹配，5 次来自 allocator。它只能回答 full-payload 费用合同下优化器如何响应，**不能称已确认的 P0 修复、真实 2conv 低估、计划变化或 H1 收益**。初始事前合同的 footprint→full all-gather 理由已经被后续审计明确撤回；预登记存在不能挽救一个被反证的前提。[保留原合同](../r12/shared_resource_counterfactual_contract.json)、[保留原运行](../r12/results/shared_resource_counterfactual/result.json)

tt-npe 的固定构建、45/45 C++ 和 10/10 pytest 通过，官方 Python API 示例估计 437 cycles，使用 `fast` 模型、32-cycle timestep 和 injection-rate inference；golden=450 没有本项目独立实测依据。官方 CLI 因 `Stats.wallclock_runtime_us` 与 `DeviceStats` 字段位置不匹配而失败，因此 `ready_for_coarse_api_use=true` 与总体 `passed=false` 同时保留。可用的粗估价器是模型研究工具，不是完整 DFG 执行、completion 或收益误差的独立真值。[环境回执](../r12/artifacts/npe_environment.json)、[API 示例](../r12/artifacts/npe/example_api_20260908T010242Z.json)

## R13 待测：多 tile 模型中的完成事件与联合静态编译

当前最具体的问题是：在同一目标模型、工作量、数值规则、初末位置与存储预算下，**consumer 实际需求、共享 link/channel/NIU 资源、source-last-read 与 destination-visible 的差异，是否共同改变最佳静态 mapping/placement/routing/send-window，并产生超出正确重定向既有编译器的完整模块净收益？** 确定性 DFG 固定必要决策与合法约束，执行仍可按依赖和资源自定时；不预设新增 descriptor、队列、同步编码或 scheduler。

新轮次先落实三项可判别工作：

1. **模型资格。** 固定 Wormhole B0 公开版本，把 tile/双 NoC 方向、endpoint alias、物理 channel、共享资源容量及完成作用域映射为明确模型动作；未知时序单列参数及范围。对数据需求、资源守恒、容量、复用、部分写入、完成与终止提供独立 checker/解析见证。公开语义与建模假设分开，不因为没有板卡而放弃这些检查。
2. **强 P0 与同合同消融。** 先移植并强化 STREAM/TETRA 已有 mapping、placement、routing、buffer/prefetch、DMA/FIFO 和 lifetime 能力；允许强基线利用 source-local 数据与合法 halo/分片，拒绝拿缓冲 footprint 替代必传量。再逐项比较资源服务与分作用域 completion 的增量影响；所有方案共享硬件、计算/数值、实际 bytes、初末位置与成本。不得让新增方法独占正确硬件知识。
3. **完整模块判决与停止条件。** 小规模 exact、独立资源下界、不同实现的参考模型和参数敏感性共同检查计划排名与完整输出可见时间。若已有方法吸收全部收益，接受 H0/工程解释；若只有微图/极端参数或下界变化，记录负结果或未决。只有完整模块非极端条件下的稳健净改善才继续 P1；强 P1 后仍有具名残差才另行讨论收费 Rh，当前不实现。

R12 冻结合同的 `G0_native=NOT_PASSED`、`G1/G2=NOT_TESTED`、`G3=NOT_OPEN` 不改判。[原预登记](../r12/preregistration.json) 要求原生后端、board/harvest 与校准；这些是该轮冻结目标，**不作为用户现在要求的模型路线阻塞项**。[R13 proposal contract](../r13/proposal_contract.md) 已确定为后续唯一执行合同，使用 M0 模型资格、M1 可识别残差、M2 完整模块与稳健性三门，分别判定 Hmodel 的模型排序变化与 Hcompiler 的额外搜索价值。M2 保留至少两个非退化完整配置 3% 净改善，并要求事前参数失配范围内保持正向；约 1 个百分点是同模型数值细化对相对收益的稳定性目标，不能称为板卡实测精度。本文只解释历史与方向，具体实现/矩阵/门槛以该合同为准。

此前“先做设备门”“只能回到 GDN 驻留”均历史化。无需重新进行无边界 Phoenix SDK 建设，也不直接恢复 R5/R10/R11 已关闭候选。3D memory 可在具有独立公开资源/热/成本合同后比较，不预先锁定 MoE 或把它拼接到 Wormhole 免费供带宽。**R13 启动时方向与合同已确定；后续实际 DES、独立回放和有限小图结果见本文顶部追加段与 [R13 报告](../r13/experiment_report.md)。R13 不开启 Hruntime/Rh 实验。**

## 本次证据等级与历史原文说明

本次维护执行的是文件阅读、已存结果字段核对、原字节快照/hash 与文本更新检查。R3–R11 执行量及 PASS 属于对应报告记载；R12 源码/工具/affine 求解事实依据其已存报告和回执，本次没有重新执行。完整阅读两份活动台账、R1/R2 原候选定义与 R12 最终纠错；R3–R9 按关键问题选择原报告章节，R10/R11 报告全文核对。具体章节与范围在 [阅读覆盖表](../research_progress.md)。没有访问仓库其他方案初稿、演示或解析副本，没有借本次维护改写冻结结果。

下文保留更新前正文，以记录 R10 后的建议和 R11 的实际否定过程。旧正文中的 Windows 绝对链接可能缺少现有 `research/` 层级，核查时按上述当前相对链接定位；旧标题为“R1–R10 科研回溯：proposal 台账、收敛判断与下一步”。

## 历史正文：R10 决策及 R11 追加

日期：2026-09-05。本文件是R10冻结后的新回溯意见，不改任何历史实验判决。本次核查R10、R9、R8结果及历史check均PASS；三路独立复核分别覆盖R1–R3候选、R4–R8证据和R9–R10收敛性。没有进行新的性能实验或新颖性检索。文中的当前建议是基于本项目证据的资源投入判断，区别于历史报告的原决定。

## 1. 直接结论

1. **正式编号台账有15个候选条目：R1 C1–C10十项，R2 P1–P5五项。** R1 D1–D5是C1–C5的重命名保留，不另加五项。R3–R10主要推进或拆解这些路线，没有形成又一批获得收益支持的新架构提案。15不是15个独立贡献，也不是15个都做完了实验；其中有被合并的点子、工程基线和测量工作。
2. **获得新硬件收益支持并完成目标/PPA接受的proposal为0。** 特定小图证明动态信息可以有价值，但不等于真实工作负载上的新机制已经成立。
3. **通用completion-ready方向在已测范围可以收敛为负结果并停止投入。** R4/R5在强化基线、来源图及全宽有限资源之后仍不达门。R9/R10的具名EXT选序/观察规则也不支持硬件开发；但“所有EXT顺序都无价值”尚未证明。
4. **R10已经跑完，核心识别没有完成。** B规则在所有测试块0次实际改序，是触发假设失败；不能把只观察收费的结果当实际改序无价值的负证据。这里不是漏跑，也不是多补相同样本便可解决。
5. **建议停止当前规则化Qwen投影上的新增动态仲裁/调度机制搜索，回到静态数据移动与状态生命周期。** 最近的逻辑分岔是R8/R9“mapping/traffic vs 额外选序”；最明确的已有正实验是R5 GDN驻留。两者可汇入“容量与合法生命周期约束下的数据移动最小化”下一主线。

来源：[R1原台账](D:/dsh-proj/SchedResarch/r1-base/redteam_claim_frameworks.md:53)、[R2原台账](D:/dsh-proj/SchedResarch/r2-ooo-npu/research.md:242)、[R5决定](D:/dsh-proj/SchedResarch/r5/experiment_report.md:92)、[R10决定](D:/dsh-proj/SchedResarch/r10/experiment_report.md:45)。

## 2. 全部正式proposal条目

计数遵循原始文档明确编号，避免把后来每次重新命名、策略参数、实验假设及基础设施重复算作新proposal。R1红队当时的先例/动机判断仅作为历史选题决定，不冒充本次重新检索的新颖性结论。

| 原始ID | 提案 | R1–R10实际进展 | 当前判断与是否做完 |
|---|---|---|---|
| R1 C1→D1 | Descriptor原子配置、保持bank-pair的VMEM remapper | 有地址映射/仲裁动机与原型设计；没有完成该remapper对base/padding强基线的性能/RTL比较。R9/R10理想local端口模型不能检验它。 | **未测、暂停。** 不是被后续调度负结果证伪。 |
| R1 C2→D2 | VMEM generation lease、代际安全与复用 | 有lease/epoch状态机方案；R8只完成单payload先后关系反例，R9/R10验证已有地址/credit/visibility合同。没有证明新GLT硬件必要。 | **安全条件部分澄清，硬件必要性未证。** 静态wait/release可满足已测安全合同。 |
| R1 C3→D3 | 3D逻辑层KV/attention window计算 | 停在机制与成本分析设计，没有真实近存bytes/energy/latency或热模型收益闭环。 | **未测储备。** 不能因P2失败而自动升为优先方向。 |
| R1 C4→D4 | 与VMEM供数耦合的32×32阵列分区/多dataflow | 保留窄的bank-coupled版本；未完成同面积/带宽/供数条件的性能验证。 | **未测、暂停。** |
| R1 C5→D5 | 双核直接stream/gather/reduce fabric | R8检查跨域payload是否必要；R9/R10明确只走同一个EXT写/读staging，未实现所提direct link/reducer。 | **前置工作有进展，原fabric未测。** split-K/static收益不能当它的收益。 |
| R1 C6 | Descriptor template/loop expansion | 在R1选题红队中因动机/先例压力淘汰，没有进入性能试验。 | **选题淘汰，非实验证伪。** |
| R1 C7 | counter-feedback备用plan selector | R1淘汰宽泛“生成多方案、硬件择优”表述，没有具体selector实验。 | **选题淘汰。** 不等同否定R2 P3的数据相关选择问题。 |
| R1 C8 | 3D thermal sensor + placement | 并入D3从属特性，未独立实验。 | **合并，不再独立计活跃proposal。** |
| R1 C9 | MBIST fault-map驱动坏bank/core降级 | 没有当前故障动机与实验，列为储备。 | **未测储备。** |
| R1 C10 | 每tile混合精度overflow detect/replay | R1因缺少具名因果缺陷与先例压力淘汰。 | **选题淘汰，非所有精度重放机制无效。** |
| R2 P1 | Flexibility-certified static memory planning | R3完成合同基础，拒绝“memory plan→合法执行合同本身”宽泛新颖性；R5发现具体RF驻留收益，R8/R9有静态分片/traffic结果。原方差感知复用联合优化算法未形成获证贡献。 | **宽主张不成立，具体静态优化值得收敛。** R5结果不是原P1已全部完成。 |
| R2 P2 | certified partial-order + static-assignment动态派发 | R3证明小图存在性；R4/R5通用ready负结果；R9单动作回看、R10busy/idle规则继续检验更窄剩余空间，均不达门。 | **已测通用机制停止；最新具名规则失败；全域不可能性未证。** |
| R2 P3 | 数据相关循环的quasi-static预验证变体 | 原列MoE专家子集、可变batch等；R3–R10未完成相应真实图/工作量/性能试验。 | **未测。** P2规则稠密图负结果不能外推到它。 |
| R2 P4 | descriptor延迟方差与静态/动态分界计量 | R3合成方法；R6真实copy，R7真实固定INT8 GEMM；缺匹配目标可调kernel、实际bytes/compute-active/request观测。R9/R10自主模型不补成实机计量。 | **工具工作有成果，真实残差实验未完成。** 无法宣称目标静态已足够。 |
| R2 P5 | inter-descriptor decoupled access/execute | 原定位为工程项与P1/P2必备基线；R4–R10静态预取/双buffer/重叠吸收相关能力，但非TARS wire/RTL接受。 | **保留为强基线，无独立新机制收益主张。** |

逐条原始定义：[R1 C1–C10](D:/dsh-proj/SchedResarch/r1-base/redteam_claim_frameworks.md:59)、[R2 P1–P5](D:/dsh-proj/SchedResarch/r2-ooo-npu/research.md:246)。继承/暂停关系：[R1/R2审计](D:/dsh-proj/SchedResarch/analysis/r1_r2_audit.md:72)、[R3架构边界](D:/dsh-proj/SchedResarch/r3/architecture_proposal.md:3)。

另有两个未进入正式漏斗的R1旁支：共享Softmax/RMSNorm/RoPE SFU、DMA-adjacent operand physicalization engine，均停在讨论层面；若统计每个出现过的构想，应在15条正式记录之外另记这两项，不混入“15项全部正式立项”。[原文](D:/dsh-proj/SchedResarch/r1-base/five_directions.md:370)

R3的H-A…H-H是八个假设，B/C是策略，49/70/960是配置或候选数量；R3有限event-frontier回收是P2的后续未实施候选。它们都不新增正式proposal计数。R5驻留、R8静态分片、R9单动作筛查、R10观察规则是后续可单独判断的优化/实验候选，已在上表关联父路线，不能称为新的四项成熟架构提案。[R3假设](D:/dsh-proj/SchedResarch/r3/hypotheses.md:1)、[event frontier](D:/dsh-proj/SchedResarch/r3/architecture_proposal.md:33)

## 3. 按轮次看科研实际推进

| 轮次 | 实际推进 | 对后续有效的结论 |
|---|---|---|
| R1 | 源码/合同边界与10→5候选筛选；无性能闭环。 | 发现可问的问题，没有证明五个硬件方案的收益。 |
| R2 | 21点toy比较与P1–P5路线图。 | 有局部现象；“无复用就无收益、重尾必要”等结论后来被纠正。不能继续沿用这些前提。 |
| R3 | 3,920次合成执行、精确小图、窗口/收费检查。 | 无复用轻抖动小图150→140，证明信息价值可存在；每task收费8cycle后变156。复杂C与扩大层级没有可靠收益。 |
| R4 | 有官方来源的缩尺图、强静态、13,440主执行和priority修正。 | 收费策略没有通过5%门；有合法替代任务不意味着能缩短最终结束。 |
| R5 | 全宽/请求级/finite-credit/返回反压，强化同一ready检验。 | 36组无5%达门，通用ready在已测范围淘汰；另发现静态RF驻留7.155%–24.027%改善。 |
| R6 | Phoenix真实copy与计量语义核验；全模型驻留外推审查。 | 有设备功能，不具备真实强静态残差证据；两head/four prepared tokens不能外推全自回归。 |
| R7 | 自控输入/BO的固定copy与INT8 GEMM功能；计量桩定位。 | 功能入口成立；无研究kernel的受控性能/动态收益，SDK本身不是新proposal。 |
| R8 | 两cluster分片、bytes、CPU数值、单payload安全偏序。 | 先选择合法静态mapping；跨域partial并非所有mapping必需，安全可见性不推出新scheduler。 |
| R9 | 完整参考EXT-DMA-VMEM路径、204静态候选、180paired blocks与2,880单动作反事实。 | 主EXT64供给减少造成大变慢，但平均恢复上界仅1.6%–1.9%；单动作最好收费回看均值0.0210%且CI跨0。35%严格关闭门失败，更宽带宽比未决。 |
| R10 | 960静态候选、串联/credit下界、两hardware360A配对+360B配对。 | 部分gap确属松界；静态改善很小；新规则1,440次观察、0实际改序，尚未识别真正动态空间。 |

数值依据：[R3](D:/dsh-proj/SchedResarch/r3/experiment_report.md:5)、[R4](D:/dsh-proj/SchedResarch/r4/experiment_report.md:5)、[R5](D:/dsh-proj/SchedResarch/r5/experiment_report.md:37)、[R6](D:/dsh-proj/SchedResarch/r6/experiment_report.md:7)、[R7](D:/dsh-proj/SchedResarch/r7/experiment_report.md:13)、[R8](D:/dsh-proj/SchedResarch/r8/experiment_report.md:5)、[R9](D:/dsh-proj/SchedResarch/r9/experiment_report.md:7)、[R10](D:/dsh-proj/SchedResarch/r10/experiment_report.md:9)。

## 4. 当前是否收敛，未决究竟是哪一种

必须分开“科学命题已经解答”“既定实验已完成”和“是否值得继续投资”。

| 对象 | 实验完成度 | 科学结论 | 投入决策 |
|---|---|---|---|
| R1 D1/D3/D4/D5、R2 P3 | 主实验未做 | 不能支持也不能否定 | 保持未测；不因调度失败自动重开全部候选。 |
| R4/R5通用completion-ready | 已完成并强化过基线 | 已测范围没有足够收费收益 | 可以关闭此具名候选，停止增加复杂度。 |
| R6/R7真实残差 | 只有功能/计量资格检查 | 真实收益问题未被测量 | 属于前置实验未完成；不是NPU性能负结果。 |
| R9既定单动作族 | 已执行2,880次反事实 | 不达收益门；但回看不是causal policy | 关闭该收益主张，不开发硬件。 |
| R10固定观察规则 | 96诊断配对与360测试配对均跑完 | 0动作，触发假设失败；实际动作价值未被识别 | 停止此规则；重跑相同种类样本无助于识别。 |
| EXT128/DMA32全合法选序 | 只有必要下界与有限搜索 | 仍有约10%–13%平均恢复上界，但不是可达收益 | 全域未解不等于应继续投入机制；当前证据足以暂停。 |

R10下界从“资源可同时满速”增加停供期有限credit约束，EXT128旧static的平均upper由约18%缩至9.62%–11.49%。这确认一部分缺口来自下界忽略必要约束，不是实现了相同比例加速。960候选没稳定消除大gap。B所有观察中另一cluster都busy，只有观察费扰动了时序；不能从其近零净gain推断发生过有效改序。审计、样本量和重放次数确认执行可信，不能补足实验对核心假设的识别能力。[R10原始判决](D:/dsh-proj/SchedResarch/r10/experiment_report.md:23)、[本轮独立收敛审查](D:/dsh-proj/SchedResarch/analysis/r9_r10_convergence_review.md)

因此，**当前不能收敛成“动态调度在NPU没有价值”，也不能收敛成“发现了约10%–20%的动态收益”。可以收敛成“在本项目已测规则化算子与强静态下，没有支持新增调度/仲裁硬件的证据，继续该机制路线的投入理由不足”。**

## 5. 已经发现哪些收益方向

### 5.1 GDN合法RF驻留：较强的静态正信号

R5在相同算术、容量、初始state、每token输出和最终state合同下，用一次读入、连续处理四个已prepared token、最后写回，取代每token的本地state往返。四条件elapsed改善16.013%、24.027%、7.155%、11.853%；resident B0=S，收费B2仍退化。它表明减少确定性的本地搬运比重新调度这些搬运更有效。[实验](D:/dsh-proj/SchedResarch/r5/experiment_report.md:70)

边界：仅两个head，每core一个65,536B state，加输入输出共73,760B，在假定128KiB RF/core内合法。本地state-transfer bytes从1,048,576降至262,144，而外部state bytes仍131,072；不能称已经减少整模型外存交通。完整单层32head state为2MiB、24层48MiB；同层下个token之前有其他31层forward，未来prepared输入不能免费提前得知。收益对prefill/合法token块与串行decode是否分别存在，尚未验证。[流量边界](D:/dsh-proj/SchedResarch/r5/redteam_report.md:110)、[R6外推审查](D:/dsh-proj/SchedResarch/r6/experiment_report.md:42)

### 5.2 多cluster静态分片与traffic：最近的架构相关正信号

R9 quiet：同四core合同下C2K+cluster广播47,776cycle，C2N+cluster广播55,912cycle，C2K快14.5514%。EXT traffic分别2,998,272与3,555,328B。它是减少输入复制与增加partial staging之间的静态取舍；没有新增直连，也不是scheduler恢复量。静态方案绑定研究FP32数值许可、broadcast/gather能力与共同起终位置，尚未得到真实TARS接受。[R9表与解释](D:/dsh-proj/SchedResarch/r9/experiment_report.md:39)

R10 DMA32/20%的约0.106%W先改善只是小型静态参数效应，35%为0，名义CI未作多重比较校正，不构成足以单独投入的新架构方向。[R10](D:/dsh-proj/SchedResarch/r10/experiment_report.md:23)

上述两项较强正信号不可相加：工作负载、硬件合同和baseline不同。共同启示是减少必需或冗余的数据移动、选择合法状态生命周期与分片，而不是假定存在可被动态硬件填补的大bubble。

## 6. 停止与回溯建议

**建议现在停止：** 通用ready、age/pressure、更大window/更多层级、均匀Qwen投影上的busy/idle阈值或固定动作窗口搜索，以及其RTL/PPA开发。它们没有已观察且收费后足够的可恢复端到端损失作支撑。保留模型与负结果，停止扩张机制，而不是宣布全部体系结构研究失败。

不建议因R10残余upper仍大就进入R11继续换一个触发器。没有动作可能是特定规则过窄，也可能是在选定时刻不存在该机会；目前无法决定。每次通过改参数、扩大模型或换窗口延续未决，会削弱证伪路线的停止意义。R5曾要求先定位真实残差；后续获得更多参考模型证据仍未出现能支持机制的信号。[R5原停止意见](D:/dsh-proj/SchedResarch/r5/redteam_report.md:134)

**回溯的位置：** 若按最近的逻辑分岔，回到R8/R9的“静态mapping和traffic是否已解决问题”，不回到R9的大upper当动态机会。若按最近的清晰收益证据，回到R5“驻留消除本地搬运”的分岔。R6/R7是工具能力分支，不应重新变成无边界SDK建设主线；R2 P1可作为优化问题背景，但其原宽泛novelty已被R3否定，不能重新包装。

## 7. 下一步只建议一条主线

**方向：面向完整单层与真实token可用时序的状态驻留、分片和分层存储数据移动优化。** 保留每cluster两core的研究范围；先用已有存储和静态优化建立正信号，再决定有没有具名硬件缺口。第一工作负载建议GDN，用R5可复算正例作锚点；借用R8/R9的严格bytes/初始终态/可见性账本方法，而不混用不同轮次的RF、VMEM或带宽参数。

新的问题应写成：在固定RF/VMEM/外存容量、合法数值与实际输入到达顺序下，完整32head GDN单层最少需要搬运哪些state和operand？强静态的head/token/tile顺序、驻留与spill能否接近此下界？prefill的合法已知token块与严格autoregressive decode必须分开。

建议下一轮只做一个有明确停止条件的验证：

1. **先验证R5正信号是否能合法扩大。** 完整单层head数量、真实输入可用顺序、全部输出与最终state；禁止为decode提前提供未来token。单层不能自动外推跨层/整模型。
2. **冻结一个存储合同和共同成本。** RF可寻址容量、VMEM保留/并发占用、每条传输路径；相同初始与最终state位置。不能把R5的128KiB RF与R9的4MiB VMEM当成已存在于同一目标的资源。
3. **对比最强现有静态方案。** head-major/token-major/tile顺序、合法驻留、spill与prefetch；报告逐层级实际bytes、资源下界和最终elapsed，单独解释每项收益。
4. **按结果终止或升级。** 若合法生命周期/容量使收益消失，就结束该驻留候选；若既有硬件静态优化已实现稳定收益，收敛为compiler优化结果；只有发现既有接口阻止一个明确有收益的合法数据移动方式，才提出对应的窄硬件合同/存储通路方案，再比较软件强基线及收费收益。

该方向目前是推荐验证的问题，不是已验证的新paper novelty。若目标明确必须是纯硬件贡献，现有证据尚不足以直接给出一个获支持的硬件proposal；不能为了维持标题把静态优化收益重新归到scheduler。当前更值得证明的是数据为什么必须移动、能否少移动，而不是如何给未识别的动态收益设计更复杂控制器。

**可选收尾而非继续主线：** 只有需要更强的理论负结论时，才为R9/R10安排一次预算固定的小规模完整Y终点顺序/credit证书实验。界仍松则记录未决后停止；有实际可恢复动作才考虑新规则的新相位确认。它不应成为转向静态数据移动研究的前置阻塞。

## 8. 本次交付与证据等级

本次是历史回溯和新决策建议；没有改r1–r10冻结文件、根README或research_progress。根README仍保留早期轮次正文，进度表顶部也有历史范围描述，最新状态应以各轮实际报告和本文件的来源链接判断。本次执行的四项完整性核查确认：R10 1,148个named artifacts、R9 648个named artifacts及R8/历史关系均保持有效。这不替代实机验收，也不将历史先例审查视作当前新颖性检索。

## 9. R11 实际结果：完整 GDN 单层静态驻留

R11 按交接要求只验证 R5 的驻留正信号是否能扩大到完整 GDN 单层。冻结来源是 Qwen3.5-4B 配置 `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` 与 Transformers 实现 `f62dc9bf2c90353b442a56e74391fbb8c689b55e`。完整模块包含 qkv/z/a/b 投影、因果深度卷积、q/k 归一化与 beta/g 准备、gated-delta recurrence、gated RMSNorm 和 out projection；范围不外推到其余 decoder 层或整模型。32 个 value heads 的 recurrent state 是 2,097,152 B FP32；参考合同给出 128 KiB RF/core 和 4 MiB VMEM，BF16 packed cold weights 展开为 FP32 中间值。所有新实现和结果在 [r11](../r11/)；R8–R10 四项历史 checker 均 PASS，冻结 manifest 未变。[历史核验](../r11/history_verification.md)

已知四-token prefill 合同下，强化 baseline 每个 token 读写全部 state，驻留候选按 head 保留四个 token 后写回。两者共同执行 168,427,520 MACs、共同外部字节 88,863,488 B；完整 state read/write local bytes 从 16,777,216 B 降到 4,194,304 B，完整 local 总字节从 109,135,104 B 降到 96,552,192 B。selected static plans 是 baseline/resident `v64-p2-head`，两者 RF 峰值 81,984 B/core、VMEM 保留 3,013,376 B。76 个 prefill 数值 block 和四个严格 decode callback 代表均通过独立 FP64 source-algebra 对照，最大绝对误差 2.6633e-7；这证明完整 32-head 输出、每-token state、最终 state/cache 的参考数值与输入生命周期账本，不证明官方 chunk kernel 或真实设备执行。[数值结果](../r11/numerical_results.json)、[资格结果](../r11/qualification_results.json)

性能门是净单层 elapsed 至少 5%。quiet 配对为 baseline 3,448,328.125 cycles、resident 3,448,868.5 cycles，差异 **−0.015670637%**。独立背景 A 的 30 个 paired blocks 均值 **−0.599174254%**，95% 配对 t 区间 **[−0.610049107%, −0.588299401%]**；背景 B 均值 **−0.605967308%**，区间 **[−0.617565500%, −0.594369116%]**。独立审计重放 122 条 held-out traces，重新计算 FIFO、依赖、容量、bytes、blackout、下界和统计，结果 PASS。[R11 报告](../r11/experiment_report.md)、[独立审计](../r11/independent_audit.md)、[原始结果](../r11/results.json)

严格 autoregressive decode 单独判定：下一 hidden 只在上一模块输出与 state 可见后释放，调用边界清除 RF/VMEM。按该 ABI，baseline 与 resident 的四次 invocation 图完全相同，因此没有合法的驻留干预可测；这关闭的是该显式 decode 合同，不是所有跨层、warm-weight 或融合存储合同的数学不可能性。

**R11 决定：prefill——本轮未获支持，方向关闭；strict decode——本轮未获支持，方向关闭。** 关闭对象是完整模块、cold-weight、staged reference ABI 下的静态驻留候选，不是所有驻留优化。当前结论更新为：R5 的两个 head/四个 prepared token 正信号不能在共同完整模块成本下成立；减少确定性 local state traffic 仍可能被 state dependency 和投影/准备成本抵消。下一步停止该候选投入和动态机制扩张；只有提出新的、明确的 warm-weight/fusion/跨层存储合同并重新预登记，才有理由继续，不把本轮负结果外推到未测目标。
