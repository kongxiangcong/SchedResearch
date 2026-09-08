# R13 模型合同独立审查：精确需求、共享资源与分离完成事件

日期：2026-09-08。本文提出并反审下一轮最小模型合同；不是新的性能结果，也不是另一份执行合同。**[R13 当前执行合同](../r13/proposal_contract.md)具有优先权**；本文的实现细节与敏感性矩阵是供其采纳的建议，不自动形成第二套门槛。本次只写本文，未改 R12、输入证据包或历史实验，未实现 DES，未复跑旧大实验。

**建议继续一条主线：从实际 operand demand 出发，在公开 Wormhole B0 拓扑与事务语义约束下，联合选择计算/张量位置、合法双 NoC 和静态发送窗口，检验完成事件与缓冲生命周期是否改变强静态计划的排序。** 无板卡不构成这项模型研究的停止条件。结论应写成“在明确模型与参数域内成立”；板卡、tt-metal native 执行、实测误差约1个百分点均不作为本轮准入门。R12 的 `G0_native=NOT_PASSED` 继续作为历史事实保留，不能将它改写成通过，也不能继续把它作为本轮模型实验的阻断。

## 1. 先明确可证伪的问题

令同一离散计划全集为 `C`，完整语义模型为 `M_full(θ)`，其中 `θ` 是公开标注的时序/仲裁场景。研究三个不同问题：

1. **需求与资源是否正确？** 每个被消费的元素有正确来源；共享链路/channel 的服务守恒；每次读到合法 epoch。这是模型正确性问题。
2. **粗完成模型是否选错计划？** 将粗成本选出的计划重新在 `M_full(θ)` 中执行，是否比同一 `C` 内的最优/强静态计划更差？这是模型充分性问题。
3. **新求解方法是否有额外价值？** 在 P0 同样获得完整语义、相同候选和预算后，候选方法是否更快找到更好计划或更有规模地求解？这是算法问题。

问题2的正结果不能直接回答问题3。给现有优化器补正确资源/生命周期约束就得到同样结果，应归为 P0 吸收、建模工程或负结果。generic joint mapping/placement/routing、DFG 表示、依赖执行和 scoped wait 不单独宣称新颖性。[R12 强基线审计](../r12/baseline_source_audit.md)、[冻结提案合同](../../SchedResearch_reassessment_evidence_20260907/proposal_contract.md)

## 2. 公开事实与模型假设分账

采用来源状态 `public_exact`、`public_approx_or_peak`、`scenario_assumption`；再单列“模型已验证/尚未验证”，不能把有源码等同于实现正确。

| 项目 | 可固定的公开内容 | 本轮不能冒领的精度 |
|---|---|---|
| 物理网络 | 10×12 torus；NoC0 物理 +x 后 +y；NoC1 −y 后 −x；NoC1 raw 坐标须转换；保留非活动 tile 的转发 router | 采用明确的文档全芯片结构实例与活动 tile 子集，不能称某 SKU 的实际 harvest 配置 |
| 合法路径 | 请求、响应、ACK 分别按所用 NoC 的确定性路由走；返回不沿请求边倒走 | 不提供任意 k-shortest path、不在一个事务里免费切换 ACK 网络 |
| 数据包与完成 | 32B flit；一个 header，最多256个 data flit；L1 读写以16B单元作用；源读完、目标写完、ACK与通知分开 | packet 非原子；一个 transfer-duration 不能兼任所有完成点 |
| DRAM 身份 | 六个 group，每组3 endpoint、6 NIU共享2GiB；每组两个1GiB物理 channel；地址最高这一级位决定channel | 同channel的endpoint不能复制带宽；同group两channel也不能无依据合成一个全串行server |
| NoC 服务 | 邻接router link可每cycle发一个flit，公开hop latency为9cycles；NIU相邻hop约5cycles | 链路启动间隔1不等于每包每跳占用9；约5不能冒领已校准精确值 |
| Router buffer | 每inbound port共2KiB，16个VC各保底32B，余1.5KiB共享，各VC最多再占480B | 不能把共享池复制到每VC；详细credit返回和仲裁微时序仍须指定模型规则 |
| L1 | 每Tensix 1464KiB；16 bank各每cycle一次16B读或写；每NoC有两条128bit读、两条128bit写连接 | 不能无依据令两个NoC共享单个L1服务口，也不能忽略bank冲突却声称完整L1模型 |
| 计算 | FPU公开指令吞吐/延迟随fidelity、指令和操作数模式变化；有理论峰值 | kernel有效吞吐、padding、unpack/pack/SFPU重叠不能直接取满峰值，M=1尤其不能按满利用率GEMM处理 |
| 同步/控制 | counter scope有明确规则；sent早于源最后读取；目标NIU收尾flit早于目标内存完成；Baby RISCV fence无效 | 本模型可定义具名的有序发布/轮询primitive并给出费用假设；不需要先跑native，但不能把它写成已实现的native指令序列 |

固定证据：[路由](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/RoutingPaths.md#L3-L63)、[NoC结构/VC/服务](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/README.md#L3-L68)、[DRAM地址](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/DRAMTile/README.md#L3-L41)、[DRAM带宽与router buffer](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/DRAMTile/README.md#L64-L70)、[L1结构与端口](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/TensixTile/L1.md#L3-L53)、[FPU吞吐与fidelity](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/TensixTile/TensixCoprocessor/MatrixUnit.md#L21-L75)。

NIU内部排队、channel队列/仲裁/turnaround、clock关联、L1地址到bank的实际布局、kernel利用率等不能统一写成“Wormhole参数”。采用聚合模型的部分应显式写 `scenario_assumption`。例如“无bank冲突layout下每NoC最多32B/cycle的本地读/写服务”是公开上限下的限定模型，不是完整L1仿真。若最终解释依赖两个NoC的bank冲突，应加bank/port模型重新求解，而非随意降低一个总带宽凑结果。

## 3. 需求合同必须先于通信成本

为每个最终计算分片保存：全局迭代域、operand affine map、有效坐标集合、padding规则、dtype、归约顺序和最终物理owner。对目标计算片`t`，先构造其实际读取集合`D(t)`，再减去其合法初始/先前驻留副本`L(t)`；剩余集合决定远端需求。所有权、分配范围、实际读集合、物化搬运集合四者分别登记。

一个 full-copy transfer 可以有意多搬消费者不读的字节；应明确这是执行计划选择。强 P0 同样可以选合法的 selective transfer/local reuse，而不能因旧 IR 分配了完整buffer就强迫 P0 复制全部tensor。若选择 gather、replication 或multicast，保存每个源slice→目标集合与逐有向link的发生次数；不得仅靠`links_used`集合或source/target数量推出并行带宽。

R12反例是必须保留的回归：真实2conv的`z6/z13`对应`ox`空间分片。在连续对齐且core顺序一致的owner见证下，只需六列远端halo，共49,152bit；128bit/cycle共享bus的必要payload服务界为384cycles。它推翻“该计算必需完整262,144bit过bus”的推断，却既不证明已有512cycles计划可实现，也不证明现有transfer真的选择了该halo执行。另行显式规定全复制需求的共享bus反例仍成立。[affine回执](../r12/artifacts/shared_resource_affine_audit.json)、[独立纠错审计](../r12/independent_research_audit.md)

微图可以逐16B块记录不同的`(tensor, element, epoch)`与整数数据，不能继续用同一标量复制整个1KiB来检验部分写入。全模块可用紧凑区间/affine集合保存元素身份与独立数值执行器，避免为每个网络事件复制整张量；但依赖、padding和归约不能只靠总MAC数准入。

## 4. 最小 DES：事务与数据推进共同生成完成事件

### 4.1 一个内核、分层精度

推荐主模型采用**有限缓冲的flit级cut-through离散事件推进**。链接启动间隔与传播延迟分离；先实现单芯片、普通对齐单包read/nonposted write、固定普通VC协议，不启用VC_LINKED、特殊priority和需要额外reservation协议的broadcast。完整MLP在该子集中可以用显式unicast实现；研究结果必须限定在此动作空间，不能因此声称击败厂商所有multicast方案。

不要为每个候选先跑一次NPE再拿返回duration拼DFG。也不要在packet开始时一次锁住整条路径直到packet结束：这会人为消除cut-through和相邻pipeline。默认模型不能用store-and-forward来代替公开的cut-through语义。

可先做无限router buffer的调试模式，检验事件守恒；它只是放松模型。进入主排序结论前启用公开buffer约束和具名credit规则。fluid bandwidth sharing或store-and-forward可以保留为具名结构消融/实现对照，不称cycle-accurate；如果排序仅在这些替代结构上出现，不能外推至主模型。

### 4.2 最小状态

| 状态 | 需要保存的最少内容 |
|---|---|
| Memory span | tensor/epoch、owner、地址区间、已写16B块、每个块尚存reader、保留/释放事件；source、receive、consumer-result分别计容量 |
| Compute task | 精确输入域、读取/输出时刻规则、固定计算资源、服务需求、输出发布事件；任务不能在输入尚不可见时偷读 |
| Transaction | request ID与scope、发起器、src/dst、NoC、payload块、源已读取集合、目标已写集合、request/response/ACK/通知状态 |
| Network | 每个有向出口的下次可服务时刻；每inbound port/VC排队与buffer占用；在途flit、预留credit和返回credit；按packet维护每hop VC占有 |
| Endpoint/NIU/channel | 路由端口与本地内存服务分开；endpoint→group/channel别名；真实共享服务预算；队列及仲裁策略具有独立参数来源 |
| Control | 模型primitive的提交、轮询/等待与通知开销；可用ID、counter在途计数、slot token、epoch；没有免费全知remote完成信号 |

packet只要header/前缀可转发就能进入下一跳，尾flit未到不妨碍前缀推进。同一VC上的packet排他与不同VC的flit交织按公开规则保留。dateline/buddy选择和credit返回若只能实现近似，必须列为模型策略并审查死锁；不能把“硬件常用模式无死锁”借给一个任意写出的VC分配器。

buffer记账同时包含已驻留与已为在途flit预留的容量。应能检查`free + reserved + occupied = capacity`；返回credit不能在物理空间尚未释放时提前生效，也不能把credit控制当作免费的反向payload flit。具体返回通道/延迟未获完整来源时，采用显式延迟token模型并标注抽象；它不冒领真实credit wire时序。

### 4.3 事件定义不可再合并

以L1→L1 nonposted write为例：

`issue → first-hop accepted → 各16B source read → 各data flit推进 → 各16B target write → target_visible → ACK生成/返回 → ACK_observed → notification发起/传输/观察 → consumer_ready`。

这不是要求整包source read完成后才允许首flit出发。源读、网络推进与目标写可以流式重叠。`source_last_read`是该源范围**所有尚需reader的最后一次实际读取**；`target_visible`仅是目标最后一块内存写完成；`consumer_ready`还需要通知已被观察和模型发布/消费顺序成立。目标可见不能被定义成“write+notification”，通知也不能凭空发生在目标可见时。

源slot复用至少受`source_last_read → 下一load_issue`约束，不能只约束下一load最终visible。receive slot复用受`consumer_last_read → 下一写issue`约束；旧ACK不能返还consumer尚未读完的slot。consumer-result span由输出DMA的最后源读取释放。read需另有请求路径、remote source服务、响应路径、返回L1写入和完成观测，不是把write方向翻转后复用一个duration。

模型R0可用源端`OUTGOING_ID`与`OUTSTANDING_ID`的具名观测作为primitive，不必先有tt-metal代码；但所有P0/P1均获得相同scope隔离和费用。ACK乱序时，同scope的一个增量不能标记任意指定请求完成；16个ID和8bit计数等公开上限保留。command accepted、sent counter、目标NIU收到最后flit均不能提早提供可见性。[Counters](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/Counters.md#L119-L173)、[Ordering](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/Ordering.md#L5-L32)

### 4.4 事件驱动的确定性与可检查性

同一timestamp采用固定的两阶段规则：先统一完成已到期的服务/释放，再统一收集ready请求并按具名仲裁选择下一服务；通过零时长逻辑边达固定点后推进到下个正时长事件。不能让Python容器遍历顺序隐式决定硬件优先级。算法不能知道仲裁器的隐藏未来状态，P0/P1也不能分别使用不同的同时间事件处理规则。

检测“还有未完成工作但事件队列为空/无合法服务”并输出等待图，区分应用依赖环、buffer复用环与模型credit/VC错误。检测到模拟器死锁不能直接宣称真实Wormhole死锁。若使用批量推进连续flit来运行全MLP，先在微图逐事件版上证明相同完成时间、顺序、内存与credit状态；不能把批量优化暗中改成fluid服务。

## 5. 强静态基线：同样可优化发送窗口与生命周期

| 名称 | 明确地位 |
|---|---|
| `P0_ported` | 固定STREAM/TETRA真实入口，在新数据需求、拓扑、channel别名和完整事件模型中重定向；保留来源和每阶段solver状态 |
| `P0_strong` | `P0_ported`加现成静态搜索/局部改进/有限枚举，覆盖相同tiling、位置、复制、合法NoC、prefetch、buffer、wait scope与send window；作为主要性能对照 |
| `P_exact(C)` | 微图在显式有限候选全集`C`内枚举/精确约束求解所得最优，独立复放验证；不是所有连续发送时间或所有mapping的全局最优 |
| `P1_candidate` | 若提出事件冲突反馈/约束生成等方法，同样接入完整模型，接受相同预算与warm start；与强P0比较求解质量、规模和时间 |
| `P_coarse` | 完成合并、仅byte-hops或保守全scope wait等诊断消融；明确不是唯一强基线 |

资源/RAW/WAR/WAW等正确性反例可加可行性约束；拥塞慢计划只可加有依据的成本/下界或引导搜索，不能把它当非法candidate删除。P0/P1共享候选manifest、数据、总资源、模型参数、初始状态、最终输出位置、目标函数、solver时限/种子与搜索预算。额外接收slot、NIU queue或L1容量不得只给P1。

微图先使用R12的96个离散placement/NoC选择作为可复用起点，但它没有穷举全部计算位置，不能称全空间。新增send window应冻结为有限值，例如两条链的具名阶段相对release offset取`{0,32,64}`模型cycle；这是1KiB/32B单链序列化单位的离散设计网格，不是硬件时序值。若候选太多，应在运行前固定更小子集/分层搜索，报告全集与剪枝证明，不在看到收益后缩减对手搜索。

发送offset只推迟合法issue，仍需满足输入发布、slot token和local wait。不要允许优化器直接排每个router flit或读取模拟器内部target_visible来发通知；这些不是当前编译器动作。能优化的scope/wait集合事先列出，而不是让P1凭离线未来时间免费绕过P0的完成通知。

主要指标为合同规定的模块入口到全部输出及完成状态可见时间；另报payload最后可见、最终确认、协议quiescent时间。若caller必须等最终ACK才能返回，不能把它剔除。必须同时报告逐link/channel/NIU/L1服务、排队、source/receive/result lifetime、峰值存储、compute-active、控制动作及费用。不同计划各自演化其内生队列，不复用基线结束时间。

## 6. 三个见证家族与反例

| 家族 | 构造与保持项 | 支持/否定什么 |
|---|---|---|
| W1：共享link与分离link | 从合法双NoC候选中，在运行任何时间模型前按完整request/response/ACK账本挑出相同payload、尽可能相同总flit-hops且共享程度不同的pair；固定计算和内存域 | 只比较request byte-hops不足以隔离拥塞；找不到完整等hop pair就如实报告剩余差异，不继续称严格等hop见证 |
| W2：endpoint别名与channel | 三组对照：同group/同channel不同endpoint、同group另一channel、另一group；逻辑输入与总字节一致，各span地址不重叠；显式列出路径差异和每channel服务 | 别名不能复制带宽；同group另一channel不能被错误完全串行。路径造成的收益与channel造成的收益分账 |
| W3：source/target/consumer生命期 | 四活动tile、两链、至少两epoch，使source、receive、result复用都实际触发；保留相同全部span预算；给P0最小合法scope | 容许下一epoch source更新早于旧ACK且数值正确，同时必须拒绝目标slot提早覆写；完成分离若只让弱全局barrier受益，H1不成立 |

W3的gap首先由有限队列、共享出口和目标内存服务自然形成；不要凭空给目标加一个专门制造收益的“随机可见延迟”。参数场景中的额外NIU处理时间可有明确位置，但必须同时测试去掉它，区分依赖该假设的条件结果。

回归至少保留：CMD0/sent误当source释放、NIU received误当visible、outgoing误当remote visible、ACK误当consumer释放、不同ID响应乱序、局部重复地址、同channel多endpoint、跨NoC返回路径、16B前缀覆写。还要加入2conv容量→需求的失败回归，以及显式all-gather与disjoint-link两个正控制。[R12硬件反例](../r12/hardware_source_audit.md)、[R12资格checker](../r12/qualification.py)

## 7. 可执行的敏感性矩阵建议

先冻结公开拓扑、flit大小、链路启动间隔、9cycle router hop和公开buffer容量；不把这些当作任意调参旋钮。NIU相邻hop的`~5`可用5作为公开近似实例并明确标签，必要时单独做3/5/10的近似敏感性；不能宣称这个区间覆盖实际芯片。

以下矩阵是**研究者设定的条件性场景**，用来观察结论是否依赖单点；不是Wormhole参数估计、概率分布或现实置信区间。所有值在测试前冻结。单位为NoC参考cycle，不能直接输出实机微秒。

| 场景参数 | 名义值与离散集合 | 解释 |
|---|---|---|
| NIU本地内存有效服务因子`ηN` | 名义0.75；`{0.5,0.75,1}`×每NoC读/写32B/cycle公开上限 | 在最小无bank冲突抽象中降低有效服务；读/写分别计，不把双NoC合并。1是上限场景 |
| channel有效服务因子`ηD` | 名义0.75；`{0.5,0.75,1}`×24B/参考cycle | 24取文档12GT/s与1GHz参考点的理论值；同时冻结这个参考clock合同。读写共享该channel总服务预算，1是理论上限 |
| 计算有效率`ηC` | 名义0.5；`{0.25,0.5,1}`×固定fidelity/操作形状的理论服务能力 | 必须先计padding与实际tile指令工作；1不是实际kernel效率。SiLU/elementwise/unpack/pack分别记服务，不能只缩放三次GEMM |
| NIU内部数据buffer`BN` | 名义4；`{1,4,16}`个flit | 无公开精确值的结构场景，不能标成NIU真实queue depth；公开router buffer不随之改变 |
| credit返回延迟`δcredit` | 名义18；`{9,18,36}`cycle，自下游释放起计 | 以公开hop量级构造的敏感性档位；入链传播/已预留容量另计，不能双收或提前返还 |
| NIU额外处理`δNIU` | 名义9；`{0,9,18}`cycle/具名事务阶段 | 与约5cycle的NIU-router hop分开；0是去除未知额外处理的控制，不能悄悄叠加在每个flit上 |

控制primitive也须具名费用。在冻结其参考服务表后统一乘`{0.5,1,2}`；另给零控制费用只作乐观上界。不能使用这里的控制倍率证明Rh在现实上可回本。如果某primitive尚无可用服务拆分，先保持符号参数/报告break-even值，不编造“真实单动作cycle”。

建议执行次序与规模：

1. **微图：13个时序点。** 六参数名义点 + 每轴另外两档，三个见证家族均跑同一个预登记有限候选与exact oracle。另独立改变公平仲裁tie-break，检查结论是否仅由ID排序产生。
2. **交互：16个预登记点。** 固定`BN=4, δNIU=9`，对`ηN∈{0.5,0.75}`、`ηD∈{0.5,0.75}`、`ηC∈{0.25,0.5}`、`δcredit∈{9,18}`做完整笛卡尔积；不会只靠某个理论满速上限点。
3. **完整MLP：分阶段进入。** 按当前执行合同，在名义点跑4/8活动tile×M=1/32/128的六项cold配置，每项保留全部12个DRAM channel；完整需求与事件验证后再跑上述16点。warm只在可行驻留集合固定后另开表，不伪称135MiB权重能驻留四/八tile L1。报告每一点，而不是只挑最优两点。
4. 每个场景做两种比较：双方均针对该场景重优化，观察模型内最优价值；双方名义点计划固定后跨场景复放，观察参数错配敏感性。两者不可混在同一“收益”数字里。

若暂不建bank-aware L1，主结果名称须包含该限定。补入bank冲突/不同合法layout或取消无限内部queue等结构细化后，原计划应原样复放并允许双方重优化。结构改变不能包装成参数噪声；参数矩阵也不证明结构误差已经被覆盖。

## 8. 微图oracle与完整MLP各自负责什么

微图oracle负责有限`C`内最优性、所有被检查动作的合法性、资源守恒、部分读写与终止。可使用独立CP-SAT/MILP或穷举离散计划加独立事件复放；若优化器和验证器共享同一个错误packet duration，第二个solver并不提供独立证据。记录所有阶段incumbent/bound/gap、候选数和未展开分支。

完整模块固定`down(SiLU(gate(X))*up(X))`，H=2560、I=9216、M=1/32/128，三权重合计135MiB。保留三次矩阵运算、激活、乘法、通信、归约与最终完整输出；不能只测down切片。M=1输入只有当前token，不能预给未来token；M=32/128的prefill输入在合同入口确已存在。[工作量账本](../r12/workload_intake.md)

数值模型可先采用显式数学dtype/归约树与软件oracle，不要求native BF16 kernel；若时序模型按某fidelity指令计费，数值/精度合同必须与之相容。FP64算法oracle加BF16理论满速不能直接叫“同一实现”。允许将数值正确与架构服务场景作为两项独立资格，但必须标明接口关系尚未证明，不靠放宽误差掩盖少算/重排。

MLP报告有限搜索内的best known，除非有可审查bound，否则不称全局最优。引擎规模不可承受时，先实现经微图等价验证的批处理；需要改变六个主配置或候选规模时先修订执行合同，不能暗中减少后仍称原合同已完成。不要改成局部子层指标后继续叫完整MLP。

## 9. NPE只承担限定交叉检查

固定NPE的`WormholeB0DeviceModel::unicastRoute`明确实现10×12双向异序torus，可用于独立路由比对。它的`modelCongestion`在时间步内累加link/NIU需求，再以最大瓶颈作一次带宽降额；默认时间步128cycles。固定源码还硬编码read的若干坐标分类延迟、write的`40+10×hops`，以及按packet size查表的带宽。它们是估价器合同，不是source-last-read/target-visible的精确时间点。[路由实现](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/tt_npe/cpp/include/device_models/wormhole_b0.hpp#L320-L356)、[带宽降额](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/tt_npe/cpp/include/device_models/wormhole_b0.hpp#L55-L188)、[硬编码latency与带宽表](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/tt_npe/cpp/include/device_models/wormhole_b0.hpp#L420-L476)、[配置](https://github.com/tenstorrent/tt-npe/blob/341da058f0b65e51d3643fb36f011a0784abedff/tt_npe/cpp/include/npeConfig.hpp#L17-L28)

可交叉检查：坐标/路由、静态trace字节与资源分布、无拥塞同质传输与明显共享link的限定拥塞趋势。先明确trace事件是API transaction还是已展开packet，防止adapter再次生成request/ACK而双重计费；不支持同一语义时只比共同覆盖的部分。对其时间步可做32/64/128/256敏感性，但这只能揭示NPE离散化，不校准自建模型。

不把NPE输出当oracle，不要求DES每例吻合某个NPE cycle，不靠调未知NIU/credit参数逼近NPE；两个近似器相等不等于现实准确。NPE无法提供的目标内存可见、scope等待、应用buffer token和完整计算，由本轮具名模型自行负责。

## 10. 已知确定性服务为何通常不需要新增runtime

在固定输入图、初态、服务参数、合法动作、确定性仲裁和相同硬件资源下，一个runtime策略会产生确定的执行轨迹。如果静态计划表示能够表达其中的发起次序/等待/延迟动作，这条轨迹可离线重放或编译为静态计划，并用相同合法guard执行。因此：**此合同中runtime没有新增信息价值；有限候选集外或更强搜索得到的收益，不等于硬件乱序必要性。**

上述论证有明确边界：静态候选集必须能表达该轨迹；编译器须获知相同固定服务/初态；不能忽略runtime额外资源或静态计时primitive成本。微图runtime若击败`P_exact(C)`，先检查它是否用了`C`之外的动作，而不是宣布打破静态上界。有限预算下在线启发式胜过离线启发式可说明求解/执行成本取舍，仍不是信息论优势。

不为打开Rh而加入独立随机抖动、未经来源的refresh噪声、随机compute时间或预知未来的oracle。未来若研究未知输入/外生流量，应另冻结可引用的扰动来源、静态策略可用信息、runtime观测延迟与动作费、绝对时间配对及独立内生队列；没有这些证据，本轮就关闭新增runtime分支，继续静态编译研究。

## 11. 本轮模型门与判停

以下仅解释当前执行合同的门，执行条件以该合同为准。

| 门 | 条件与动作 |
|---|---|
| M0：模型资格 | 需求/数值、所有具名完成事件、16B部分访问、地址epoch、packet/NIU/channel/link守恒、有限buffer credit和终止通过；小oracle与独立复放一致；所用仲裁和未知参数全部具名。无需板卡 |
| M1：微图残差 | 三家族在强P0后检查模型充分性/排序；微图有限全集最优作参照。若只有alias/需求bug修正或已有solver接完整语义便吸收，记录工程/负结果，不保护P1 |
| M2：完整模型价值 | 六项完整MLP、相同资源与候选、参数域逐点报告。当前合同要求名义非退化配置至少两项净模型makespan改善≥3%，且对应配置在预登记参数失配域内保持正向；这是研究筛选门，不能称设备3%收益，也不保留无法在无板卡下证明的实测1个百分点误差门 |

冻结时还应给求解与仿真预算、名义点和参数域，不在看到结果后降低门槛。确定性重复仅可检查复现性，不产生timing CI/p95/p99；敏感性范围是条件集合，不是现实概率。

以下任一结果应停止相应主张：

- 仅合并完成/全局barrier/错误tensor需求的弱对照落后；强P0已得到相同计划。
- 排序差只来自P1额外候选、存储、带宽、隐藏remote事件或未计控制。
- 结果依赖单个假定NIU/credit点，在预登记非极端场景不稳定：收窄成参数条件结论，不能宣称普遍Wormhole收益。
- 精确需求、守恒或credit证明失败：暂停性能解释，修正模型；不以增加样本掩盖系统性错误。
- 新求解方法没有比现有方法更好的质量/规模/预算证据：保留模型研究或关闭算法新颖性主张。
- 新runtime仅在人为随机扰动或静态动作被削弱时胜出：关闭Rh；不妨碍完成静态编译方向。

## 本次阅读与检查范围

全文读冻结proposal、R12 `qualification.py`、强基线审计、硬件审计与自身2conv独立纠错记录；本次定向重读固定ISA的NoC README/RoutingPaths、DRAM地址与performance、L1全文及MatrixUnit 1–130行。定向核查固定NPE的Wormhole路由、拥塞服务、latency/带宽表、engine timestep推进和配置；线上打开固定官方Counters与NPE源码作来源确认。最后全文复核当前R13执行合同，接受其六个主配置与门槛优先。未读其他初稿/演示，未重跑旧性能实验；本文全部新建议均是设计，不是已实现结果。

向执行合同主编报告的两项具体风险是：FP32中间结果进入down时，须明确BF16输入量化边界或相应FP32计算路径/费用，不能按未转换的FP32数学语义搭配BF16 FPU峰值；W1等hop比较须覆盖实际request/response/ACK/notification，不能把request-only见证升级成全通信等hop。另建议在主output-visible指标之外报告final-ACK/quiescent，保留尾部控制与资源状态。主编负责将接受的修正写入唯一执行合同。
