# R8 层级与 strong-static 公平性审计

日期：2026-09-05。只读审计现有 R3 源码与 R1 历史证据，新增本文件；未运行旧实验，未修改 R1–R7。本文没有实机时序或收益结论。R1 的源码引用是当时审计留下的出处，尚未重新定位当前权威 TARS checkout，不能标为本轮已核验的当前实现。

## 1. 决策

**保留多 cluster 问题，优先完成 down-projection 的 bytes/驻留/完成合同判别；不继续扩大 R3 scheduler/NoC 模型。** R3 足以证明有限抽象里的信息价值，但不能回答两个 cluster 是否争用同一外存供给、跨 cluster payload 如何到达消费者、真实 completion/release 各指什么。它的所谓 SRAM 与 R1 每 core VMEM 也不是同一存储拓扑。

本轮选定的最小工作是 Qwen FFN down 的 `K=9216,N=128,M in {1,32}`：比较四 core 各 `N=32,full K` 的输出切分，与每 cluster `K=4608`、其两 core 各 `N=64` 的 K 切分。FP32 partial 从 cluster 1 发给 cluster 0，每 core `256*M` bytes，两个发送共 `512*M` bytes。账本采用冷 weights、private VMEM 输入副本假设；不将该逻辑写入量直接称为实测 DRAM bytes。两方案对应相同实数矩阵运算，但 K 切分改变归约顺序，尚未证明 bitwise 或目标精度合同合法。

## 2. R3 现存层级语义：哪些确实存在

| 项目 | 代码实际行为 | R8 可复用内容与边界 |
| --- | --- | --- |
| 拓扑 | `sim/workload/motifs.py:67-79` 按 `cores*clusters*chips` 创建 task，每 core 自有 MXU/VPU 字符串资源；每 cluster 新建 DMA/SRAM 字符串资源。 | 可复用命名和固定映射的概念，不能据此确认 DMA 后端是独立外存通道。未建共享 DRAM 端口，新增 cluster 自动增加局部 load 服务并发。 |
| SRAM/VMEM | `motifs.py:79-88` 的 load、norm、KV task 原子独占 cluster SRAM；`sim/memory/__init__.py:14-23` 则按 task domain 顺序分配独立输出地址。 | R1 历史锚点是每 core VMEM；R3 cluster SRAM 整 task 互斥并不等于该物理路径。无 bank/端口访问序列，也无真正驻留求解。 |
| 容量 | `sim/hardware_model/__init__.py:16` 默认 `memory_capacity=1<<28`；`sim/memory/__init__.py:27-33` 对每个域内地址范围单独检查该上限。 | 参数名看似全局，语义是每域地址上限；cluster 增长使总可寻址存储增加。集中/分域控制切换不改变物理 task domain，故同 cluster 数两种控制组织的这一预算相同。 |
| 跨 cluster 链路 | `sim/noc/__init__.py:4-9` 的同 chip 跨 cluster transfer 只占一个 `chipX.noc` 互斥资源。 | 没有方向/字节率/包/信用/输入输出缓冲或并行链路；每次 transfer 的服务时间独立给定。 |
| 跨 chip 链路 | 同文件用 source egress、destination ingress、单一 `interchip.link` 三资源同时独占。 | 是抽象 link task，不含封装、协议、NoP、hop、拓扑路由或接收缓冲，不能验收 chiplet。 |
| Payload | `motifs.py:98-99` 给 exchange 固定服务时间 25；`sim/workload/__init__.py:11` 的默认 task output 为 256 bytes。 | 服务时间不由 bytes/bandwidth 得出。exchange 输出归 source task domain；没有 destination tensor span/generation 与消费者逐项绑定，不能拿 task 输出 bytes 当链路流量。 |
| 阶段依赖 | `motifs.py:101-105` 在全部 exchange 后建全局 barrier，下一阶段每 core 均等待它。 | 这是刻意加入的阶段同步，不是由实际模型 tensor 局部依赖推导。它可抹平局部释放机会；不能拿它否定无需全局 barrier 的实际图。 |
| Completion | `sim/execution.py:109-123` 在 task finish 释放全部资源、descriptor，然后给每条后继边排目标域 wakeup port；只有一个统一 completion latency。 | `data/completion/WAR/WAW/reduction` 的运行时可见性均归入同一事件流程；source last-read、local store visible、remote visible、event publication、credit return 未分离。 |
| 跨域通知 | `sim/execution.py:117-120` 将通知排入目标 wakeup 端口，cross-domain 仅累加指标。 | 没有跨域传播时延、传输流量与 backpressure 的区别；全图 task/edge 与 delivered history 仍全局保存。 |
| 完成终点 | `sim/execution.py:169` 以所有 task 最大 finish 为 latency。 | 无最终 host-visible event 的尾延迟；需在新目标合同声明最终完成点。 |

`r3/experiment_report.md` 第 4、6 节已明确承认分域仅分片 issue/wakeup/admission、没有层次协议，以及整 task 独占、默认无地址复用、无有限 credit/epoch/分布式死锁验证。上述是对该历史边界的源码确认，没有推翻或重解释历史结果。

## 3. equal-budget 覆盖到哪里

`experiments/run.py:36-47` 的普通 `clusters_*_local` 每域复制窗口和端口。`sim/execution.py:28-32,66-75` 确实为每个控制域创建一套 issue/wakeup/descriptor admission 资源，因此原普通配置比较包含增加硬件。

`equal_budget_*` 对 N 个 cluster 采用：local 每域 16 entries、4096 descriptor bytes、1 issue lane、1 wakeup lane；central 分别乘 N。它固定了**总 resident descriptor entries/descriptor bytes/issue/wakeup lanes**，issue/wakeup cycle 也相同。它没有构建 wires/clock/queues 的物理成本；不能理解为 PPA 完全相同。descriptor byte_window 不是 payload memory capacity。

两种不同实验要分开：

1. **一个 cluster 双核 → 两个 cluster 四核的扩容控制组：**可以按明确合同复制 core/VMEM/局部 DMA，但需逐项报告增加量；不能把容量/带宽翻倍称为控制机制收益。一个 cluster 的两核仍是局部控制组，不应强迫它与四核有同算力后再声称自然扩展。
2. **固定两个 cluster 四核，比较静态方案或控制组织：**必须保持下表预算及数值语义相同；如果新增通道、scratch 或通知带宽，它是额外硬件，单列并收费。

| 必须共同固定的预算 | 需要明确的归属/单位 |
| --- | --- |
| 四个 core 的 MXU/VPU/TMU、频率、dtype、运算量 | 每 core，含 padding/tail、精度及 reduction 约束；不能只比逻辑 FLOPs。 |
| Private VMEM 与任何 cluster SRAM | 每 core/cluster 容量、保护区、对齐、bank、端口；weights/input/output/partial/descriptor/control scratch 都有去处；不能把四块私有内存当一个可任意分配的池。 |
| DMA engine/queue/outstanding | 每 cluster 的 request 接收能力与真正 data-service 能力分别记账；共享后端总 outstanding/credit 不因控制域拆分免费增加。 |
| 外存服务与路径 | 同一 memory controller 的总读写带宽、端口、队列、地址分布及服务合同；是否支持一次读后复制/广播尚未知。 |
| 跨 cluster 数据路径 | 每方向带宽、source read/destination write 端口、路由是否与外存 DMA 共用、credit/缓冲与端点容量；partial bytes 与其他流量的竞争由合同决定。 |
| 控制预算 | 总 descriptor entries/bytes、issue/wakeup throughput、event namespace/history、polling/messages、跨域传播、控制能耗或额外 cycle；相同分区损失不等于相同 PPA。 |
| 驻留和生命周期 | 初始/最终状态、冷/热 weights、输入是否已驻留、所有最后 reader、buffer generation、reuse 时点；重复 token/state 不能凭空免费常驻。 |
| 工作量/终点 | 相同有效输入、输出、精度合同、端到端测量起止；部分结果的 source completion 不能代替最终 output visible。 |

## 4. 强静态动作的来源分层

“有 compiler owner / proof”不意味着“已经是校准后的最优 plan”。“R3 能表达”也不意味着“当前 TARS 可执行”。

| 静态动作 | 已有依据 | 尚缺的事实/优化维度 |
| --- | --- | --- |
| Core mapping、tile、loop、overlap intent | R1 `live_evidence_audit.md:30,45` 保存 DataflowPlanIR 的历史实现出处。 | 多 cluster 合法 mapping 集合、down projection 两种拆分的数值/设备合法性；历史同步 builder 固定 core 0/1 (`:120`)，multi-cluster deferred (`:70`)。 |
| 物理 layout、地址、容量、lifetime | R1 `:47,79-86` 有 generic placement、bank footprint、double buffer 历史实现；R3 仅做顺序无复用 allocation 和 alias safety。 | 联合 layout/bank/capacity 搜索并不存在于 R3。R1 first-fit 和 bank separation advisory 不是强静态优化上界。 |
| Double buffering / prefetch | R1 `:30,36,86` 有固定 K-step 双缓冲 intent，Controller RTL 默认单 slot、参数 2 才 pipeline。 | compiler plan 与实际 Controller 消费的一致性未闭合；任意深度、prefetch distance、自适应 slots 尚不能当现成合法旋钮。 |
| 驻留/fusion | R1 MovementSync 历史记录 availability/residency/reuse proof (`:32`)。 | 任意跨 cluster producer-consumer fusion、保留整层/全 token weights/state 的容量、输入到达时序未证明；证明字段不是 full-model 驻留收益。 |
| 路由/通信 | R1 `:32,48` 有 local_vmem/shared_dma/ddr_ingress/ddr_store/ddr_materialized 等有限 route。 | NoC/SDMA/NUMA vocabulary 缺失 (`:70,146`)，历史 direct-link 能力识别还有不一致 (`:217`)；不能假设 zero-copy 跨 cluster VMEM 访问或广播。 |
| 静态 resource order | R3 `sim/compiler/__init__.py:82-125` 有 8 个固定 mapping 顺序候选及独立训练选择。 | 固定地址、固定映射、固定 tiling、固定 allocation；`compile_candidates` 先用默认 Hardware 生成候选。A2 不是全静态最优。 |
| 小图 exact | `sim/scheduler/oracle.py:8-15` 明确限制 fixed mapping、unary resource、nonpreemptive、zero overhead。 | 不覆盖 alternate placement/tiling、带宽/credit、数值归约或两种 down 映射全部静态动作。 |
| 静态多队列 + 既有仲裁 | R1 有 per-core queue 和共享 DMA 的历史结构 (`:59,120,211`)。 | 共享 DMA 是否只服务全局固定顺序，还是在已就绪 per-core 请求间 work-conserving 仲裁，需要当前 target 核对。不能把既有仲裁也能恢复的等待归为新增 scheduler 贡献。 |

## 5. 选定 down-projection 账本需要的限定

以下推导仅依赖所选切片的维度和 BF16 operand / FP32 partial 假设，不是设备访问计数：

| 项目 | 输出切分：4 core 各 N32，全 K9216 | K 切分：2 cluster 各 K4608，各 2 core N64 |
| --- | ---: | ---: |
| 每 core cold weight bytes | `9216*32*2 = 589824` | `4608*64*2 = 589824` |
| 全体 weight bytes | `2359296` | `2359296` |
| 每 core private input copy bytes | `M*9216*2 = 18432*M` | `M*4608*2 = 9216*M` |
| 全体 private input copy bytes | `73728*M` | `36864*M` |
| 跨 cluster FP32 partial payload | 此拆分本身不要求 | `2*(M*64*4) = 512*M` |

K 切分表面少 `36864*M` 的输入副本写入，但额外有 partial 传输和累加。**这些列不能直接相减得出 DRAM 节约、elapsed 改善或必需 interconnect 带宽。** 原因是：

- 若外存一次输入 read 可多播到四 VMEM，两方案的 off-chip read 可能相同；若每 VMEM 都独立 ingress，才对应上述副本流量。私有内存写入减少是否改善共享瓶颈，取决于实际广播/DMA/端口路径。
- K 切分的 partial 要 source memory read、链路服务、destination memory write 和 FP32 reduction；这是不同资源的工作，不能只按 payload size 与 input ingress bytes 同价相抵。
- 输出切分四 core 保留各自 N32 输出；K 切分最终输出集中在 cluster 0 两 core 的 N64 分块。必须声明输出目标位置与下一层消费方式，并补齐 gather/重新分布成本；否则终点不同。
- 一个 cluster 双核控制组若分别做 N64 全 K，每 core weights 是 `1179648` bytes；它不是四核候选中每 core weights 一样的布局，需独立容量账本。
- M=1 的数学切片未证明是 M=1 的物理执行开销。R1 历史 target 有 M/N/K multiple=32 (`live_evidence_audit.md:131`)，需注明是否有合法 tail/padding 以及 padding 的 compute、input/output traffic，不自动把 M1 当 MXU 原生无填充执行。
- 缺少完整 tensor lifetime 时不能只凭矩阵总尺寸宣布 fits；计算期 ACT/WGT/OUT/accumulator/PARAM、接收 partial、双缓冲和保护区必须同时核对。R1 私有 VMEM 数值若复用，应标历史锚点。
- K split 的中间 rounding、FP32 accumulator spill/reload、最终 BF16 cast、归约算子次序必须落到数值合同；同一实数公式不证明相同浮点输出。

此时 strong-static 还缺：input multicast/replication 的合法选择、output location、per-core bank layout、tile sizes/padding、buffer depth/prefetch order、weight residency across repeated calls、跨 cluster partial 路由和 reduction placement。上述有的为尚未证实的合法动作，有的为 R3 未搜索的静态维度；不得统称为动态可恢复残差。

## 6. 最有判别力的当前实验：先精确检查 payload/completion/release 偏序

**Research question：**在 K split 的一个具名 partial 传输中，哪些事件才允许目标消费与 source/destination slot 复用？这比增加随机延迟更直接：如果合同把 DMA accepted 当 remote visible，观察到的“快”可能是不合法读取；如果把整 task completion 当唯一 release，又可能人为延长 source slot lifetime。

**Hypothesis：** source last-read 和 destination payload visibility 是不同的安全事件；有限、具名的事件合同足以拒绝 early-consume/early-reuse，无需引入新的 ready scheduler。该假设只检查安全性与表达能力，不提出性能收益。

**Strong-static baseline：**固定上述映射、地址、partial bytes 和有限 buffer，compiler 构造完整合法事件依赖；使用 self-timed wait。两种 down 映射都先保留，没有来源证明 K split 为更强基线。通知与存储释放可以静态编排，事件到达仍由实际完成触发。

对 cluster 1 的每个 `N64` partial，最小事件集合为：

1. `produce_visible(src, generation)`：source partial 已在 DMA 可读位置；本地 compute 完成是否蕴含此事件须明确。
2. `transfer_accepted`：描述符/credit 接收，不能用于消费者 readiness。
3. `source_last_read`：本次传输不再读取该 source generation；只对相应 source slot reuse 放行。
4. `destination_payload_visible(dst, generation)`：完整 `256*M` bytes 已在目标合法可读位置。
5. `completion_delivered(event_id, generation)`：与具体 span/generation 绑定的成功通知，必须发生在相应 payload 可见之后。
6. `consumer_read` / `consumer_last_read`：读取 partial 做 reduction，最后一次读取后才允许目标 incoming slot 重用。
7. `source_reuse`、`destination_reuse`：分别受最后 reader 约束；不能互相替代。

在明确假设 source staging 或无 staging 后，再规定 `source_last_read` 与 `destination_payload_visible` 的关系；不能为了方便枚举把不存在的硬件保证填入偏序。最小程序枚举这些有限事件的所有拓扑序，独立检查每次 read 的 generation 和 reuse 冲突。注入两种故障：以 accepted 提前发 success；以 accepted 或错误域的 completion 提前 release。保留合法和不合法序列的具体反例。

**判别输出：**合法合同的全部枚举序列安全；两个故障合同各有最小坏序列。若不成立，先修合同/检查器；若成立，只接受此条件模型的安全语义，不能据此接受真实性能机制。参数化每次传输 payload，使检查对象与 down 账本一致，但 bytes 大小本身不产生 synthetic 时间。

**停止门：**完成上述有限安全检查和两映射容量/bytes 账本后，不再增加 simulator 控制复杂度。获得当前 TARS 路径、合法静态 lowering 与上述具名事件可观测性前，真实 residual/可恢复性结论保持未测。对 Phoenix 也只允许回答能迁移到某个具名事件的观测问题，copy elapsed 本身不区分这些事件。

## 7. 红队：最容易产生伪阳性的入口

- 两个 cluster 免费复制 shared-memory 带宽、outstanding、VMEM 或 notify lanes，再称层级控制收益。
- 将逻辑 private input copy bytes 当唯一 off-chip 流量，忽略 multicast、cached/resident 输入或输出再分布。
- 让早发 completion 的消费者读到抽象“已经存在”的数据，遗漏真实 payload/generation；由不合法依赖得到更短 makespan。
- 锁住比目标 ISA 更弱的全局 DMA 总序，却不给 strong-static 已有 per-core request 队列/仲裁。两 independent ready request 的 arrival reversal 本身不足以证明需要新增机制。
- 对 K split 放松 FP32 reduction 次序或 padding，对输出切分保留更严格约束，算术或物理工作量不公平。
- 把可由静态 bank/layout/residency/reduction placement 修复的问题称为服务不确定性；或把必需 bytes 的供给不足称为 scheduler 等待。
- 将 source release 与 destination visibility 合一：前者过晚会制造容量压力，前者过早会造成 silent overwrite；二者都不应成为“dynamic gain”。
- 将枚举的结构安全证书、数学 bytes 下界或存在反例包装为 calibrated cycles、实机 residual 或可迁移到所有多 cluster 的性能结论。

**结论：Refine。** R3 层级语义没有覆盖本轮要问的共享供给与 payload/completion 合同；选择当前 bytes/生命周期枚举是减少歧义的可执行下一步。两种 down 静态映射的优劣保持未定，新的 scheduler 候选尚无接受依据。
