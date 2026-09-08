# R13 P0 下一步资格缺口与执行接缝

2026-09-08。本文依据当前源码与保存回执，给出下一份可执行合同应解决的缺口；**只增加说明，不修改已绑定 hash 的模型、编译接入代码、登记或结果**。本轮交付可以包含 M0 核心实现资格及 Hmodel 小图证据；当前没有完整强 P0 portfolio、没有已比较的 P1，M1 的 Hcompiler 与 M2 均不签 PASS。最终模型门及 Hmodel 数值以正式实验报告为准。

依据：[主合同 §§5–8](proposal_contract.md)、[小图方法审查](micro_design_audit.md)、[真实接入记录 §7](baseline_intake.md)、[有限集合 runner](run_micro.py)、[串行执行登记](preregistration_serial.json)。本文检查了真实 TETRA lower 回执和登记字段，没有再跑性能搜索，也没有把计划写成执行证据。

## 1. 已经成立的事实分别是什么

| 项目 | 当前事实 | 资格边界 |
|---|---|---|
| 真实 STREAM/TETRA | 固定源码的 scheduler、allocator 和 GSCIP 已实际运行；目标输入适配提供 12 个物理 channel 身份与双 NoC 有向资源，导出真实 selected tensor/path、slot、depth/reuse 和逐阶段求解状态 | 原始 whole-transfer 成本是候选生成器的目标；其 626 cycles 不是 F makespan，也不是 F 最优证明 |
| 一个 TETRA 来源 seed | [lower 回执](artifacts/tetra_lower_receipt.json) 的 `resource_order` 准入：24 个 tensor views、12 项 payload、8 个 compute、2127 条原 schedule 次序义务；共同 F 与独立 trace/builder 审计通过 | 计算位置与 NoC 由外层 p0000 输入固定；只支持这次选中的 depth=1。不是搜索了全部 mapping，更不是完整 portfolio |
| seed 的实际模型时间 | output-visible 128724 ticks，final ACK 133368 ticks，quiescent 133944 ticks；36 ticks/model cycle | 一个具名合法计划的时间，没有宣称性能改善；不能作为唯一“强 P0”分母 |
| 当前 C | `small_plan_space()` 明确生成 576 个参数向量，`micro_graph()` 按共同控制与地址规则生成执行图 | 有限集合的完整枚举是 exact 参照；不等于原 TETRA、SoMa 或新编译器搜索 |
| 现有预算前缀 | runner 登记 `[16,48,96,192,576]`，`rank_summary()` 按 plan ID 排序形成 lexical enumeration prefixes | 这是枚举覆盖轨迹；没有已实现的 P0/P1 方法调用序列，不能改名为它们的逐阶段 incumbent |

上游三阶段 `OPTIMAL` 证明各自模型目标在该次 allocator 问题内达到界，不证明外层 mapping 全空间最优，也不证明 F 目标最优。当前源码仍有共享 link 排斥、张量放置和 reuse/depth 变量；把它描述为“只看 byte-hops 的编译器”会错误削弱基线。[R12 固定源码核查 §§3–4](../r12/baseline_source_audit.md)

## 2. C 的现有能力及没有开放的能力

当前集合为：2 个 producer 位置组 × 2 个 consumer 顺序 × 3 个 chain1 输入 placement × 8 个 load/peer/output NoC 三元组 × 3 个 chain1 首次 load 窗口 × 2 个 source 复用 guard = 576。4 个计算角色只有 4 种位置安排；三类 transfer 的 NoC 由全部链和 epoch 共用。输出位置固定，chain0 输入位置固定。

| 决策 | 已在 C 内 | 不应据此声称已实现 |
|---|---|---|
| mapping/placement | 上述 4 种角色安排；chain1 输入同 channel 别名、同组另一 channel、另一组 | 任意 tile 排列；任意 input/output/中间 tensor 放置与分条 |
| 路由 | 8 个角色级 NoC 三元组，对应完整合法物理路由 | 每 transfer/epoch 独立选网；任意路径或 multicast |
| window/wait | chain1 第 0 代 load 的 0/32/64-cycle 初始窗口；全图 source-observed/ACK guard 二选一 | 一般事件锚定 window、独立预取/写回时刻、通用资源次序搜索 |
| 生命周期 | 两代在固定单 source/receive/result span 上合法复用，控制与 token 费用相同 | buffer 地址分配、驻留深度、双缓冲、延迟写回/预取联合搜索 |
| 图与粒度 | 每项 1 KiB、两链两代、固定 `times2` 与 `plus3` | tiling/fusion/重算/完整 MLP 的 MAC、cast 和中间张量优化 |

这些能力使 C 足以检查模型排序和特定等待消融，却不足以覆盖主合同 §6 的强 portfolio。允许某方法访问 C、某方法能表达 C、该方法实际在预算内找到某个结果，要分别给出证据。完整枚举 C 可以作为工程兜底或 oracle；若将其并入一个增强组合，名称应显式包含 `exhaustive`，同时保留穷举前的方法表现。不能用“穷举后零差距”替原论文的搜索效率或完整编译器能力背书。

## 3. 最先要补的接缝：plan ID 不等于执行计划身份

当前 canonical p0000 由 `micro_graph(p0000)` 生成；已准入 seed 由 `lower_tetra.lower(record, "resource_order")` 在该图上增加源 schedule 的资源偏序。相同 p0000 标签只表示其空间、NoC、初始窗口和 guard 参数相同。**这两个图具有不同的次序约束；尚无证据证明该 seed 就是 C 中某个完整执行图。** F 相同、硬件相同仍不足以推出候选能力相同。

下一份合同应明确区分：

- `C`：保留本轮 576 项 canonical 图及其结果。`F*(C)` 只对共同审计通过的合法子集取最小值。
- `seed_tau`：当前真实 TETRA 来源的资源偏序 seed，独立保存来源、地址解释、原顺序和 F 新增控制；它当前可作后端资格样本。
- `Cq`：下一轮事前登记的共同候选集合，显式包含位置、地址/深度、窗口及资源偏序身份。若要与 seed 比较，须证明 seed 的规范化计划属于 Cq，或明确其只是集合外的补充参考。

不能先删除 seed 的源次序，再将 canonical p0000 的结果命名为“原 TETRA schedule”。可在保留原 seed 的前提下运行具名的 `TETRA-seeded refinement`；每次放宽/替换的次序及来源都要登记，形成另一个候选。

建议新增一个独立版本的编译计划接口，再接现有 F，而非重写执行器。最小字段如下；这是待实现接口，不是当前已有 schema：

| 字段 | 必须表达的内容 |
|---|---|
| `source` | method 名称、固定 upstream commit、输入/export hash、solver 各阶段状态；派生候选保留 parent hash |
| `compute_and_access` | 算子/分片身份、真实 affine/source slice、计算位置和数值合同 |
| `tensor_storage` | 逻辑 view 到物理 channel/tile、地址块、slot/depth、驻留/复用许可；禁止由独立逻辑 tensor 默认增加容量 |
| `transfers` | 稳定 transaction ID、src/dst/bytes、NoC、有序物理 links；公共后端补齐全部协议包类 |
| `ordering` | compute 与 transfer 的偏序、具体完成事件锚点、window；分别标记 upstream 决策、搜索变更和正确性必需的后端控制 |
| `identity_and_checks` | 规范化计划 hash、Cq 成员资格、环/容量/值/生命周期检查；F 参数、spec/trace/auditor hash |

现有接入口可以直接复用：`port_micro_tetra.py` 的 physical IO/path adapter；导出的 `physical_payloads[]`、`selected`、`slot_of`；`lower_tetra.py` 的 `source_intake()` 与具名 resource-order 解释。后续应新增版本及输出目录，保留这次 hash 绑定产物。当前 `depth != 1` 的明确拒绝不能改成默默折叠到单缓冲；depth2 真正接入后要有地址/容量/交错反例及独立审计。

## 4. 尚缺的 SoMa 风格能力及真实方法定义

主合同要求至少一种 SoMa 风格生命周期与搬运顺序搜索。当前 source/ACK 二选一与三个初始窗口没有完成此项；TETRA 的 depth/reuse 导出也不等于该搜索已经在 F 执行。主合同已登记 SoMa 的 tensor lifetime、预取、延迟写回与 buffer 分配联合探索；本轮未运行其作者搜索器，不宣称已复现。[主合同 §2、§6](proposal_contract.md)

最小有意义的补充，应让候选至少可以联合改变以下决策，而非只对一个固定图换打分器：

1. 下一代 input 的合法预取锚点、output 的合法写回锚点及不同 transfer 的先后；不得通过延迟主指标边界把输出写回免费排除。
2. 与上述搬运次序配套的 source/receive/result 地址与单/双 slot 选择，计算驻留区间和实际峰值容量；可用容量对全部方法相同，真实分配字节与控制开销逐项计入。
3. 依赖 source-last-read、target-visible、consumer-last-read、通知/token 观察的合法 release。P0 本来就允许合法提前释放，不能把这一权限独占给 P1。

上述列表是**候选能力要求**，不是一个已实现的 SoMa 算法。实际 method 还须单独固定初始化、状态表示、邻域或决策次序、接受规则、终止条件、seed 和 tie-break。优先复用可运行的原搜索实现并给出函数/输入/输出对应；若论文实现不适配当前 unary 图，保留具体阻断记录，选择有完整定义的具名移植。若另写受 SoMa 启发的方法，应明确叫“R13 的 SoMa-style baseline”，说明保留与偏离处，不能冒称作者代码或只凭名称通过资格。

小图可以先固定 tiling 与融合边界，把它们标为本次资格问题的固定条件；这只能准入一个**受限空间的方法组件**。完整 MLP 阶段仍必须让 portfolio 包含合法 fusion、prefetch、双缓冲与 wait-scope 能力，不能将小图的固定项偷换成已通过这些能力的验证。

## 5. 最小、可证伪的后续合同

建议下一步先做具名的 `P0q` 编译接入资格实验，不立即发明 P1，不将其称为已经完成 M1。执行顺序为：

1. **固定问题与公共边界。** 延续两链两代 1 KiB 源图、数值与冷起终状态、已注册硬件/协议和主指标。新增地址/顺序字段使用独立版本，公开假设保持原值。当前 C 与已知结果保留为开发/回归资料，不能再称盲测。
2. **冻结有限 Cq。** 按上一节能力明确列出地址/slot 候选、可用事件锚点、window 离散值与合法偏序生成规则；静态生成规范化 manifest，给出总数、去重规则、每个自由度和排除项。在读取其新 F 排行前冻结。若全集太大，先收窄具名资格实例，或给出可核查下界/gap；不能看到性能后截掉不利分支并仍称 exact。
3. **冻结真实 P0q 方法。** 至少保存真实 TETRA seed、TETRA 来源的共同 refinement、通信感知空间候选、上一节已定义且实际可运行的生命周期/搬运顺序搜索。TETRA 的外层 mapping 枚举与内层原 MILP 各自具名；原 inner solver 不因自造一个启发式而被替换。组件输出全部进入同一个 PlanIR、F 与独立审计。`best_P0q` 是各组件共同总预算内的最好合法输出。
4. **单独取得 exact 参照。** 对合法 `Vq ⊆ Cq` 求 `F*(Cq)`。oracle 与 compiler 方法隔离：搜索只能通过本次预算内的 evaluator 查询得到 F 值，不能读取完整排名表后改种子或邻域。缓存可避免重复执行，但不能免除方法的逻辑查询记账。
5. **记录并反证。** 在共同预算前缀比较 `gap_B = F(best_P0q(B))/F*(Cq)-1`，同时列原 seed、每组件与 portfolio incumbent。若无合法结果，记录资格失败；不把死锁当慢样本。若 `gap_B=0`，关闭该空间/预算上的新增目标值空间；若只在短预算有 gap，结论是具名方法的搜索效率问题；若 gap 来自不相同的地址/窗口权限，先修公平性。存在 gap 尚不证明任何新算法有效。
6. **再决定 M1/M2。** 只有清楚的残差值得设计 P1，并事前冻结它的 method 与相同能力/预算比较。小图残差不能替代完整模块；M2 仍需主合同的六配置、完整 MLP、名义与失配评估及门槛，当前均未由此实验完成。

该合同的最小目的，是区分“现有方法接入后即找到同空间最优”“现有方法在给定预算内没有找到”“候选能力仍不公平”。它不以一定出现正收益为成功标准。如果实际 SoMa-style 接入仍未完成，应保留组件未准入状态，可以继续模型研究，但不能用 exact 兜底把其方法资格勾掉。

## 6. 公平预算与逐阶段 incumbent 的具体记账

当前 576 项完整枚举及 lexical prefixes 可以保留；下一次 compiler 比较需要新增真正的调用记录。每次查询至少保存：`method/stage/seed`、候选及 parent hash、访问序号、首次/重复访问、合法/拒绝原因、F 主/尾时点、组件与 portfolio incumbent、累计逻辑 F 查询数、实际新 F 执行数、候选生成与 solver 时间、累计编译墙钟、剩余预算。每阶段结束另记终止原因及未用预算。

预算规则必须在比较前明确：

- 576 次可以继续作为一个有限 F-query 上限，前缀沿用 `[16,48,96,192,576]`；这不表示新 Cq 只有 576 项，也不保证该预算足以 exact。exact 的计算费用单列且不计为某一方法的“免费知识”。
- portfolio 的所有组件共享总预算，不能每个组件各获 576 次再与只有 576 次的 P1 比；共同缓存的命中可以节省实际评估计算，却仍按预登记方式计算逻辑访问。重复候选策略也须固定。
- seed 的真实导出/求解与 F 验收有费用；TETRA 各级 latency+DMA、traffic、buffering 的 status、bound、incumbent 与时间分别保留，不能只读最后一级 `OPTIMAL`。
- 求解器 threads、seed、每阶段/整体时限和硬件并行配置统一登记。只控制 F 查询数时，结论必须写“相同 F 查询预算”；相同编译墙钟另作约束或实验，不能从缓存重放时间推算。
- P0 与 P1 若最终都枚举完整同一集合，终点等值是有限集合事实；搜索贡献只能来自穷举前的实际轨迹。将访问顺序事后按 F 排名重排会破坏此比较。

## 7. whole-slot 拒绝应如何归因

原 target 候选将 `c1e1/load` 放在 slot6，将 `c1e0/peer` 放在 slot7。当前单 source span 的跨代合法复用要求新 load 等旧 peer 的 source-last-read；若再把全局 slot 解释成“所有较前任务 complete，较后任务才开始”，便形成环。保存的 `whole_slot` trace 实际 deadlock 且审计未完成，已拒绝、不报告 makespan。

这是**原 logical-slot 顺序、此次固定物理地址映射、此次全局屏障解释三者不能同时成立**。上游没有输出这次具体物理 alias 与所有 source-last-read 证明；另一个合法地址分配或不同后端 slot 解释可能成立。不能据此称 TETRA 算法错误、原图必死锁、硬件会死锁，或把“修复该非法移植”算成 P1 加速。

已通过的 `resource_order` 保留每 core 的 compute 次序和每个真实共享资源的 transfer 次序，使用 F 中源感知的完成事件锚定；它不保留不共享资源间的全局屏障或上游解析时刻。这是明确命名的后端解释，不是对原 global-slot 时间的原样复刻。后续只有先证明两种地址/顺序候选均合法，才可比较同步范围的性能代价。

## 8. 本轮交付与未签门

本轮可交付：共同 DES、独立实现/trace 核查和 source/需求反例组成的 **M0 核心证据**；一个 source-aware TETRA seed 的限定准入；冻结 C 的 exact/诊断设计及正式运行得到的 **Hmodel 小图证据**。模型资格报告仍应单列限定跨工具检查的缺失，不能由内部一致性推成芯片精度。

本轮保持未完成：完整强 P0 portfolio、真实 compiler 同预算轨迹、SoMa-style 生命周期/搬运顺序接入、Hcompiler 对比，以及完整 MLP 的 M2 性能与稳健性。没有板卡不是这些模型实验的阻断条件；缺少上述方法和执行证据才是不能签门的具体原因。
