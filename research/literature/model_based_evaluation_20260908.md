# 无目标板卡的架构模型科研：评估方法与本轮合同建议

日期：2026-09-08。范围：公开论文评估章节、作者代码及官方工具文档。本文只做文献取证与研究方法建议；未安装新工具、未运行论文实验、未取得新的设备测量。项目原始 `proposal_contract.md` 的 3% / 约 1 个百分点条款已读，历史合同与结果不改写。

本文提出的方法建议由 [R13 当前执行合同](../r13/proposal_contract.md) 收敛为具体范围与 M0/M1/M2 门；后续实验以该合同为准，本文不是另一套独立执行门槛。

## 结论与适用范围

**本轮可以把“依据公开架构建立可审计硬件模型，在模型内研究联合编译计划”作为完整科研路线，无须把购买或获得 Wormhole 板卡设为开工条件。** 这与“预测某块 Wormhole 卡的真实运行时间，误差小于某值”是不同层次的主张。前者要交付模型合同、独立正确性检查、强基线、可复现比较以及假设敏感性；后者才需要目标系统的外部时间参考。

这是对下列文献方法的归纳，而非声称所有架构论文都不需要硬件验证：STREAM 使用既有芯片测量验证模型，再开展离线架构探索；Timeloop 用设计专用模拟器与既有 Eyeriss 结果核验，并明确支持无需逐个编写 RTL/C++ 模型的架构比较；SoMa 在参数化模板上研究调度与资源权衡。作者做过的 RTL、布局后或芯片验证说明他们的特定评估依据，不能自动变成本项目模型的校准证据。[STREAM §IV-C、VI](https://arxiv.org/html/2212.10612v2#S4.SS3)、[Timeloop §VII、VIII-A，PDF 第 7–8 页](https://accelergy.mit.edu/timeloop.pdf#page=7)、[SoMa §V-D、VI-A](https://arxiv.org/html/2501.12634v1#S5.SS4)。

研究对象建议表述为：**公开 Wormhole B0 接口与资源结构约束下的一族多 tile、双 NoC、分布式内存控制器模型**。文档明确的路由、控制器归属、buffer 容量与完成/可见性规则是硬约束；未公开的仲裁、服务时序、NIU 排队等是具名模型假设。最终结论必须附适用参数区域，不能把“符合部分公开接口”改称“Wormhole 周期精确复刻”。

## 阅读覆盖与版本

以下“全文”仅指明确列出的章节，不指整篇论文均已逐字读完。HTML 以章节锚点为准；PDF 页码从第一页起计。STREAM、SoMa、SCALE-Sim、Timeloop、Ramulator 的相关验证/评估段落均实际读取，不只使用摘要。

| 来源 | 本次实际阅读 | 状态与未覆盖部分 |
|---|---|---|
| STREAM，TC 74(1), 237–249，2025；作者 arXiv `2212.10612v2`（2025-10-07 上传） | §III–IV 模型相关段落；**§IV-C 全文及 Table II；§VI 全文、Table III、Fig.14–16 说明** | 已取得期刊对应作者全文；补足旧证据包“正式论文未获取”的缺口。未复跑论文芯片验证。当前 TETRA 不反向归属于论文 WACO。 |
| SoMa，HPCA 2025；`2501.12634v1` | §II、**§V-D、§VI-A/B 全文**；§VII-A 全文、Fig.7 说明；Artifact Appendix A-B/C/E 对应段落 | 评估公式、参数、基线及复现资源已读；没有审计全部作者源代码或复跑 432 项实验。 |
| LATTICE，`2607.17422v3`（2026-08-04） | §V-A、**§V-B 全文/Table II**；§VI-A/B 及边界说明 | 当前按预印本处理，未独立核验 artifact，不称同行评审已确认成果。 |
| Timeloop，ISPASS 2019 | **§VI-C/D/E、§VII-A/B/C 全文**，PDF 第 6–8 页；§VIII-A | 已读具体误差来源；不是只读官方宣传页。未复跑 NVDLA-derived / Eyeriss。 |
| Accelergy，ICCAD 2019 | §1–2；§5.1/5.3 验证段落，PDF 第 6 页；§5.4 开头 | 确认是布局后能耗比较；未完整读取所有 PE breakdown 分析。作者 PDF 从 NVIDIA 官方页面的 manuscript 链接取得。 |
| SCALE-Sim v3，ISPASS 2025；`2504.15377v1` | §III、VI 相关段落；**§VIII Validation 全文；§IX-A/B 全文/Table IV–VI** | 没有把 2025 v3 的验证与后来 TPU 扩展混为一项；未检查完整作者实现。 |
| BookSim2，ISPASS 2013；作者仓库 | 官方 README；作者单位 PDF 的摘要/引言可检索原文 | PDF 直接打开多次失败，**未读取完整验证章节**，不登记任何未见的误差百分比。 |
| Garnet 2.0，gem5 官方文档 | 模型简介、Configuration、Topology、Routing、Router Microarchitecture、Buffer Management、Traversal、Synthetic Traffic | 工具文档覆盖，不是 2009 论文评估章节；该页面没有提供目标系统误差校准数字。 |
| Ramulator 2.0，`2308.11030v1`；当前 2.1 作者文档 | **论文 §III-A/B 全文**；§II 的标准模型例子；2.1 README §1、部分配置/内部实现说明 | 当前 main 已到 2.1。`git ls-remote` 固定到 `72427a1bba3771564c4fb0e494ba02242fd1eaa7`，复读该 commit README；未安装或验证其 GDDR6 实现。 |

检索使用论文全名、工具名与 validation/evaluation 关键词；仅把 arXiv 作者全文、作者/机构 PDF、官方 GitHub 与 gem5 文档作为事实依据。搜索结果中的二手摘要未作为评估结论来源。失败入口包括初始错误 STREAM `v4` 地址、部分 MIT/NVIDIA 旧 PDF 路径、BookSim 作者页面；随后 STREAM 改读实际存在的 `v2`，Timeloop/Accelergy取得有效官方全文，BookSim保留上述阅读限制。

## 八组最相关先例

### 1. STREAM / 当前 TETRA：主要编译基线与分层模型先例

论文把 per-core 解析估价接入 COALA 的内存/通信调度，按最终计算或通信完成定义 latency。§IV-C 固定已报告的 mapping、allocation 与 granularity，对 DepFiN、Jia 等人的多核 AiMC、DIANA 做测量对照；Table II 的 latency accuracy 为 96% / 97% / 97%，这不是本项目的误差界。§VI 随后离线改变核数、dataflow 与资源预算，使用 CACTI 参数及带宽受限通信模型。[作者全文 §IV-C、VI](https://arxiv.org/html/2212.10612v2)。

本轮可直接继承“核心估价—通信/容量—完整调度”分层与等资源比较方法。论文的总线/端口模型没有证明 Wormhole flit/credit/完成语义正确。当前固定代码 `75748cc…` 的 TETRA placement/path MILP 是另一版本的具体基线，需按当前接口移植并保持足够的 fusion、tiling、placement、path、window/wait 搜索机会；不能仅用论文旧配置构造弱 P0。[当前固定 README](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/README.md)。

### 2. SoMa：模型内发送时机、生命周期和 DRAM 重叠的直接先例

§V-D 先估算 compute tile 与 DRAM tensor；DRAM 时间用数据量/带宽，整体时间再由依赖、前序传输、Start/End 与数据 ready 条件合成。§VI-A 采用参数化 edge/cloud 模板，算力参照商用产品，buffer/带宽结合 DSE；unit energy 来自作者 RTL 综合与仿真。§VII-A 扫 buffer、带宽和 batch，展示瓶颈区域变化。它不是对每个探索点都购买芯片的评估流程。[§V-D、VI、VII-A](https://arxiv.org/html/2501.12634v1#S5.SS4)。

直接适用于本轮的，是将预取、延迟写回与存储生命期纳入强软件对照，并画出收益出现/消失的区域。其共享 GBUF、顺序 DRAM tensor 服务不能未经改造替代分布式 controller + 双 NoC；其 RTL energy 校验也不等于本文所需的完整 DFG timing 校准。作者 artifact 的主实验是普通 Linux/C++ 调度搜索；本文只参考方法，不建议先复跑其全套大规模 DSE。[作者 artifact](https://github.com/SET-Scheduling-Project/SoMa-HPCA2025)。

### 3. LATTICE：明确限定主张的确定性 compiler replay

§V-B 在统一 command DAG 上做 tiered-memory planning、augmented-graph timing 与独立 verifier；pipeline 单发射，不同 pipeline 可重叠。Table II 对额外 transfer 明确给出 `150+2q` 的 modeled cycles。论文说明 source network、shape、SKU、compiler version 不完整，使用 artifact 原生单位，并把静态单核作为范围，抽象掉动态到达、sub-buffer access phases 与多核编译。[§V-A/B](https://arxiv.org/html/2607.17422v3#S5.SS2)。

它是“公开模型内可检验主张”的近邻先例，也限制新颖性：固定 memory plan 后的合法时间调整不能重新包装为原创。可借鉴独立 verifier 与同一 timing backend；不能照抄其传输常数作为 Wormhole 参数。该预印本的存在说明一种评估实践，不能单独证明本轮方法已满足发表标准。

### 4. Timeloop / Accelergy：快速估价与物理成本证据要分开

Timeloop §VI-D 的 throughput 模型取各计算/通信资源孤立服务时间的最大值，假设流水填充/排空等额外 stalls 很小。§VII 用专门的 NVDLA-derived 模拟器和既有 Eyeriss 结果验证；少数 layout/transfer-order case 有明显偏差。§VIII 再用模型探索不同架构。这恰好提示本轮不能只取 `max(compute, bytes/BW)` 而遗漏正在研究的时序耦合。[PDF 第 7–8 页](https://accelergy.mit.edu/timeloop.pdf#page=7)。

Accelergy 从 action counts、组件描述与 unit-energy 插件估能耗；§5 在 65nm Eyeriss 布局后结果上验证，所报 5% 是该能耗实验的偏差，既非 elapsed 误差，也非任意架构保证。[Accelergy §5.1–5.3，PDF 第 6 页](https://d1qx31qr3h6wln.cloudfront.net/publications/ICCAD_2019_Accelergy.pdf#page=6)。本轮已有 ZigZag/STREAM 时无需再建立重复 per-core 权威；若后续有明确能耗/PPA 问题，再选择成本插件并公开 technology/action 假设。

### 5. SCALE-Sim v3：增加细节应针对排序敏感的机制

v3 建模 systolic compute、共享 L2、多核划分、SRAM layout/bank stalls，并接入 DRAM 与 energy 模型。§VIII 列明作者使用 systolic/Vegeta RTL、Micron DDR4 Verilog 及布局后能耗数据的验证。§IX-B 有直接相关反例：只看 compute cycles 与加入 DRAM stalls 后，WS/OS 的优劣可反转。这支持“检验模型细化是否改变编译选择”，不支持默认所有模块越详细越好。[§III、VI、VIII、IX-B](https://arxiv.org/html/2504.15377v1)。

本轮可借鉴 iso-compute 划分比较、layout 与队列容量敏感性。Tensix 执行并未被证明等同 systolic-array 模型；不能直接把其 GEMM cycle 当作目标 compute service time。暂不接入完整 SCALE-Sim/Accelergy/Ramulator 组合，只有 compute 或 memory 细节能够翻转结论时再局部引入。[作者 v3 代码](https://github.com/scalesim-project/scale-sim-v3)。

### 6. BookSim2：适合独立 NoC 争用对照，尚不是目标网络复刻

作者描述的是参数化 topology、routing、flow control、router microarchitecture 的周期网络模拟；论文引言明确以 RTL router 的 latency-throughput 特征验证，官方仓库支持 mesh、torus 等拓扑。[作者单位可检索 PDF](https://crd.lbl.gov/assets/pubs_presos/booksimispass.pdf)、[官方代码](https://github.com/booksim/booksim2)。

本轮若需要第二个 NoC evaluator，BookSim2 是合理候选：固定同一 packet/flit trace、合法路径、资源容量和注入条件，对少数共享/分离链路场景逐事件比较。这里是建议，不是已完成的移植。torus 支持不等于两套反向 Wormhole 原生网络、NIU 事务、返回流量和 completion semantics 已匹配；generic VC/default router latency 也不是目标实测参数。本文未读完整验证章节，不提供 RTL 对照的具体误差数字。

### 7. Garnet 2.0：已有 gem5/Ruby 系统时的替代选择

官方文档给出可配置 router/link latency、VC/buffer 深度、credit 流控及可独立运行的 synthetic traffic；默认 router pipeline 与 flit 大小均是工具默认值。它主要嵌在 gem5/Ruby 网络系统中，文档中的 NI 与 coherence protocol buffer 相连。[官方配置与微架构文档](https://www.gem5.org/documentation/general_docs/ruby/garnet-2/)。

本轮没有必须研究 CPU coherence/全系统交互的证据，因此不建议为取得一个 NoC 对照先搭整套 gem5，更不建议 BookSim 与 Garnet 同时接入。只有既有 gem5 frontend 或系统问题使其收益明确时才选 Garnet。本文检查的官方页面未给目标校准结果，不能写成“Garnet 已验证本轮网络”。

### 8. Ramulator 2：DRAM 命令约束的校验，不是整个系统时间的校验

2.0 论文 §III-A 将 8 条 streaming、8 条 random 等强度内存请求生成的 DRAM command trace，喂给配置相同组织/时序的 Micron DDR4 Verilog 模型，检查命令时序与状态转移合法性；§III-B 比较多个模拟器的运行速度。**无 command violation 与模拟器速度比较，都不是目标控制器 latency 误差上界。**[论文 §III](https://arxiv.org/html/2308.11030v1#S3)。

当前官方代码已是 2.1，固定 README 明列 GDDR6/GDDR7 与 HBM 系列；2.0 论文自身也出现 GDDR6 实现例子，不能断言整个系列“不支持 GDDR6”。本轮尚未检查所选实现、地址映射、队列/调度策略如何对应 Wormhole controller。先建共享 domain 服务模型；只有 bank/row/refresh 机制可能改变排序时，才固定具体 revision 和标准参数接入 Ramulator。[2.1 固定 README §1](https://github.com/CMU-SAFARI/ramulator2/blob/72427a1bba3771564c4fb0e494ba02242fd1eaa7/README.md#11-introduction)。

## 不依赖板卡的最小证据链

以下是本次提出的方法建议，不是上述工具已经替本项目完成的工作。

1. **模型合同先于性能。** 每项参数标记为公开架构事实、指定研究配置、推导值或未知假设，附单位、出处、允许区间。禁止用可调常数修正选题想要的结果。原生事件规则保持固定；共享 controller 的多个 endpoint 不能被当成新增独立带宽。
2. **模型内正确性独立检查。** DFG 数值结果、依赖/RAW/WAR/WAW、source last-reader、destination visible、通知、buffer 复用、credit 守恒与终止分别核验。使用小图精确枚举/穷举或独立事件 oracle，并检查单请求公式、链路/控制器字节下界、极限配置。功能正确与性能准确分别记录。
3. **一个主 evaluator。** 主模型同时驱动 compute、NoC、controller、buffer 与等待；每个策略由自己的事件和队列演化，不能重放 P0 的结束时间给 P1。STREAM/TETRA 是搜索/基线的一部分，独立 evaluator 负责评分，避免用同一有偏成本既优化又“证明”收益。tt-npe 的现有 coarse 输出可当交叉参照，不因无板卡而升级成完整 DFG 周期真值。
4. **只在机制需要时细化。** 先让最小模型表达待测的耦合；若结论依赖 packet blocking，再引入一个 NoC 详细对照；若依赖 bank/row 行为，再局部接入 DRAM backend。用可对齐的投影比较，不强求结构不同的模型数值一致，也不把二者一致当作物理真实性证明。
5. **反证强基线。** P0 和 P1 使用同资源、同数值/布局约束、同 workload 与输入可用时刻、可比较 DSE 预算；P0 有同等优化自由。重定向既有求解器若吸收残差，按工程/负结果收敛。完整 MLP 最后输出可见的 modeled makespan 是主指标，局部加速仅作归因。

这里的交叉验证主要检查实现是否服从已声明模型、机制是否可在另一实现复现。RTL 或公开既有测量可以增强局部可信度，**不必把目标板卡、目标 RTL 或全模块设备误差验证设为当前模型科研的硬前置条件**。无这类证据时应限制结论为模型与参数域，而不是填造“硬件误差”。

## 3% 与 1 个百分点门槛如何改写

建议另立模型研究合同，保留历史 G2 原文，仅在新合同中使用 M0/M1/M2。下式为建议记号，具体集合必须在新性能结果前冻结。

令 `T(P,w; θ,s,h)` 表示计划 P、完整 workload w 在参数 θ、结构假设 s、数值精度/时间步 h 下的 modeled makespan；净收益为：

`g(w; θ,s,h) = 100 × [T(P0,w; θ,s,h) − T(P1,w; θ,s,h)] / T(P0,w; θ,s,h)`。

这里 g 的单位是百分比，两个 g 相减才用“百分点”。“净”要求计入模型中由方法增加的搬运、等待、buffer 占有和控制服务；未知硬件开销保留为成本参数/盈亏平衡值。

| 门 | 无板卡条件下建议定义 | 不能声称的结论 |
|---|---|---|
| M0：语义与模型资格 | 上述独立正确性、守恒、终止、解析极限与小图精确检查通过；每类动作实际触发 | 测试通过不等于芯片 timing 已校准 |
| M1：强基线后的残差 | 预登记 witness 与完整模块上，排序差异来自声明的资源/时序耦合；排除弱 P0、漏工作、加资源和非法时序；报告小图最优界及实际搜索预算 | 两个模型输出不同本身不证明新算法价值 |
| M2：模型内性能与稳健性 | 保留至少两个预登记非极端完整模块配置在标称合同下 **g≥3%**；对预登记合理参数域/结构变体逐点报告 g、最坏值、翻转边界、regret 与资源开销。若想声称“整个该域均改善≥3%”，必须该域最小 g 也≥3%；若只是标称≥3%、其余点仍>0，只能作较弱的条件性表述 | 3% 不是实际 Wormhole 加速的保证，也不是学术通用物理常数 |

**删除“无设备也必须证明相对硬件误差≤1 pp”的要求。** 若主模型有时间离散，可保留 `max |g(h)−g(h/2)|≤1 pp` 作为预登记的数值细化目标，并要求关键排序稳定；至少检查更多一级或独立事件实现，避免两个粗粒度点偶合。该差是观察到的数值稳定性指标，未经收敛证明也不应叫严格误差界。若主模型是精确事件推进，则优先精确微例/独立事件顺序对照，不人为引入 timestep 凑 1 pp 门。不同结构模型的差异须单列，不能用 1 pp 对齐阈值掩盖。

参数域至少覆盖本研究真正不确定的 compute/transfer 服务比、NIU outstanding/credit 时延、controller 服务/排队与通知开销；结构变体只包含与公开规则相容的替代解释。公开固定的 controller 归属、容量、路由与完成依赖不作为自由扰动。没有来源支撑的 `0.5×/1×/2×` 之类扫描可以标为 stress scenarios，但不能当作真实参数置信区间。

每次改变硬件参数，应区分两种试验：**重新编译的算法比较**（P0/P1 各自同预算优化）和**冻结计划的脆弱性测试**。只重调 P1 或只让固定 P0 承受新配置会高估贡献；搜索随机种子只支持编译器搜索波动分析，不能制造设备 timing CI。确定性无噪声场景直接报每配置结果。

若可信参数域中存在排序翻转，应给出边界并收窄主张，或转为 Refine/Close；不要事后删除不利点。未知费用可先做 break-even 分析，若正收益仅存在于零费用或人为极端点，则关闭硬件乱序支线。这样允许完整的模型科研得出正结果、条件性结果或负结果，同时保留未来设备校准作为增强证据。
