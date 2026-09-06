# R1–R10 科研回溯：proposal 台账、收敛判断与下一步

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
