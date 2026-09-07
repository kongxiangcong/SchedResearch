# 由 R1 语义提炼的最小研究 Execution Contract

日期：2026-09-05。本文定义一个可独立实现的小型研究原型需求，不声称复现当前 `llmSched` 源码、活动 Descriptor 0x8、Controller 或 RTL。源证据来自完整阅读的 R1/R2，审计见[r1_r2_audit.md](r1_r2_audit.md)。多核、多 cluster、多 chip 均是本轮显式建模的研究配置。

**目标是将离线复杂推理压缩成硬件可逐事件消费的有限记录：给定绑定、地址、必须保持的顺序和资源预算，硬件仅判断当前任务能否执行并记录真实完成。** Contract 应保留足够的合法顺序自由度，但不能将未证明的地址复用交给runtime猜测。

## 1. 从 R1 继承什么

R1的九阶段链条和owner划分（`r1-base/live_evidence_audit.md:14–53`）可以在研究原型中压缩为五个模块：

```text
Workload DAG + tensor views
  → Task decomposition + static mapping + cost hints
  → Physical buffer plan + explicit dependency closure
  → Execution contract + independently decoded descriptors
  → Hardware model consumes descriptors, completion trace verifies the contract
```

| R1 owner/语义 | 小原型中必须保留的内容 | 首版无需复刻 |
|---|---|---|
| GraphClusterIR | 节点/边/输出身份，task来源，blocked/unsupported状态 | 完整frontend、graph importer、全部operator合法化 |
| DataflowPlanIR | 有限task分解、core/cluster/engine固定绑定、静态推荐顺序 | 原生产的strategy类层次和所有GEMM候选 |
| StreamTensorPlanIR | producer/consumer，逻辑tensor与storage view区别，dtype/bytes/layout引用 | 全套layout语言、任意layout搜索 |
| PhysicalMemoryPlanIR | base/span/lifetime安全，alias/reuse的最后reader约束，容量与对齐 | Controller内重新first-fit、复制生产placement实现 |
| MovementSyncPlanIR | 显式load/store/transfer、completion visibility、跨域事件 | 无需求的通用路由搜索或所有网络协议 |
| CoreExecutionPlanIR | 必须保持的partial order与一个静态线性化 | 把静态总序强加到所有对照scheduler |
| RuntimeLaunch/Descriptor | 每域明确队列，包括空队列；版本、task id、真实长度 | 原0x8字节兼容层、旧发布机制 |
| DescriptorSemanticReport | 解码后检查绑定/依赖/地址一致，执行后检查task/事件语义 | 宣称软件检查就是RTL numerical admission |

这些取舍对应R1的关键限制：generic placement已存在，但mirror/epoch还属规划（live:84–106）；CoreExecution并不是周期最优schedule（live:33）；旧Controller重新寻址（live:35–38）；cost没有校准、关键计数器没有live反馈（live:152–163）。

## 2. Contract 必须回答的五个问题

| 问题 | 离线输出 | 运行时所需动作 |
|---|---|---|
| WHEN can it run? | `wait_events`或等价pred集合，必要release/reduction边 | 计数降至0、输入可见、任务尚未发射 |
| WHERE can it run? | 固定`chip/cluster/core/engine`和静态route；若研究迁移则显式eligible集合 | 核对目标域；首版不重映射、不重寻址 |
| WHAT resource is required? | 引擎、DMA/outstanding slot、SRAM bank/port、link等单位和占用阶段 | 在资源足够时原子reserve，完成相应阶段再release |
| WHAT event wakes successors? | 明确producer task的哪种完成：engine-done、store-visible或remote-visible | 产生一次命名事件，更新有限后继/consumer计数 |
| WHAT ordering remains? | RAW、物理alias的WAR/WAW、归约、外部可见side effect、必要channel顺序 | 不绕过合法性边；静态priority只用于多个合法ready task之间 |

完整模型图、tensor高层语义、shape传播、lifetime推理、loop合法化、graph搜索留在compiler。将所有task字段直接复制进硬件表不算压缩；要分别报告静态描述符、片上resident窗口、动态状态和遥测trace的大小。

## 3. 最小记录与扩展字段

### 3.1 首版必需记录

```text
ExecutionContract
  schema_version
  workload_id / contract_id / hardware_config_id
  tasks[]
  buffers[]
  event_bindings[]
  per_domain_descriptor_streams[]

TaskDescriptor
  task_id
  operation_kind                load / compute / store / transfer
  fixed_binding                 chip, cluster, core, engine
  wait_events[]                 event_id, optionally generation
  completion_event              semantic completion, not merely issue
  resource_requirements[]       resource_id, units, hold/release stage
  input_buffer_refs[]
  output_buffer_refs[]
  nominal_service_cost          units explicitly cycles or time
  static_priority               optional optimization hint

BufferBinding
  buffer_id / logical_value_id
  memory_space / owner_domain
  base_bytes / span_bytes / alignment_bytes
  dtype / storage_view_ref
  writer_task / reader_tasks
  reuse_group                   optional
  slot / generation             only if IDs or addresses are recycled in flight
```

工程实现可将pred表示和wait_events合并为一个规范依赖表示，不保留两个会漂移的authority。后继索引可由compiler预计算，入度counter从该同一表示初始化。硬件可选择存successor list、compressed wait mask或稀疏event→consumer映射，它们是待比较的编码，并非必须同时存在。

首版使用单次DAG、全局唯一task/event id且完成记录永不重用时，**不必为每个事件增加epoch表**。只有循环实例、bounded window槽复用、重试/迟到completion能够与新实例混淆时，generation才必要；其位宽、回绕drain与reset协议必须纳入模型，不能假设无限tag免费。

### 3.2 可选hint应有独立消融

| Hint | 可以帮助什么 | 不能代表什么 |
|---|---|---|
| predicted latency | 离线排序、静态dispatch priority、估计slack | 真实本次结束时刻 |
| critical-path rank | 多ready任务的有限priority选择 | clairvoyant最优下一步 |
| expected memory/communication cost | 短任务/重访存任务的静态分级 | 未观测的DRAM队列或NoC状态 |
| locality | 在允许映射集合内减少移动；首版固定mapping时只供分析 | 硬件可以自动迁移固定地址operand |
| resource pressure | 静态候选priority、cluster仲裁hint | 消除实际resource capacity约束 |
| layout/Linear Layouts | 压缩地址序列、确定byte/bank footprint | 动态调度获益或独立novelty的先验保证 |

动态policy可观察已完成事件、当前credit/queue、已耗时与当前资源可用性；不能读取simulation预先抽样但硬件尚未知的future durations。oracle是单独policy和证据标签。

## 4. 内存安全不能继续依赖旧总序

R2指出R1 lifetime以`start_order_index/end_order_index`定义，依赖`same_core_queue_retirement`（`r2-ooo-npu/research.md:48–50`）。这些是历史记录中的顺序执行证明，进入ready dispatch后必须重建。

对于复用同一物理区间的逻辑值A、B，若B覆盖A，应至少保证：

```text
writer(A) completion-visible → every reader(A) may start
every last read of A completes → writer(B) may start
```

其中“last reader”是所有可能并行reader的集合，不是原总序里编号最大的一项。若A仍有异步store/DMA-read访问，该访问也属于reader。部分重叠的span需要按实际区间处理；只比较buffer名称或slot数字不够。多writer的WAW和读-改-写操作要显式编码。

最小实现可以采用两种独立模式：

1. **No-reuse control：**所有buffer地址分离且总容量足够。用于隔离pure data dependency和runtime uncertainty；不能称同容量最优。
2. **Fixed-capacity reuse：**compiler分配具体span，从真实reader集合添加safe reuse边，验证完整图无环，所有地址在每个合法执行中安全。超容量则拒绝或加入真实spill transfer；不得免费加内存。

将reuse边加到某个已经合法的静态参考顺序中时，只允许沿该参考顺序建立不会倒置已有路径的关系，或显式检查全部边无环。若成环，可以改变reuse选择或重新调度/分配；不能在运行时silently删除依赖。

capacity可行不等于bank性能可行。首版把SRAM bank或port作为显式有限资源是一种抽象；若整task全程独占bank，需注明可能过保守。若不建cycle-level memory accesses，就不能报告精确bank conflict count或bank-level性能预测。

## 5. Completion、同步与数值语义

R1记录header DEP/SIGNAL、逐核队头等待与退休推进（live:117–127）；R2记录按来源序号消费（research:49）。自由重排不能继续让“第k次signal”隐式指代“第k个consumer”。

首版采用命名的`event_id`，建立唯一producer→后继关联。也应保留一个较弱基线：维持每条通信通道的publish/consume序，仅在不破坏通道序的局部窗口交换；若它已取得相同收益，则不必更换全部同步网络。

不同事件必须区分：

| 事件 | 对后继的意义 |
|---|---|
| command accepted / DMA issued | 消耗queue或outstanding credit；通常不使operand可读 |
| producer engine finished | arithmetic结束；是否已写到目标memory由硬件模型定义 |
| local store visible | 本域consumer可读取特定buffer generation |
| transfer remote-visible | 所有需要的bytes在目标域可见；之后才可唤醒远端consumer |
| release / final read done | 指定物理slot可重用；不代表整个模型已完成 |
| task error | 不产生正常success event；记录失败/取消，禁止下游消费未定义值 |

K维累加、softmax partial或跨核reduction的浮点顺序必须保持原contract规定。只有明确允许数值容差或给出数学/实现等价规则，才能将其改成可交换归约。Graph合法性验证与数值执行验证分开；首版若只模拟时长，应称语义/资源仿真，不称真实算子数值正确。

## 6. 最小硬件状态从事件消费方式推导

Hypothesis A的候选最小设计是：每resident task一个remaining-dependency counter、一份可用资源状态、一个本地ready结构、一个bounded issue arbiter，加上实际需要的completion传输。Task table、scoreboard、RS并不是要求额外各造一套。

```text
completion event
  → update explicit consumers' remaining counters
  → newly-zero tasks enter local ready structure
  → choose a task allowed by binding and current resource credits
  → atomically acquire all start resources and issue
  → resource model executes and emits semantic completion
```

一次性DAG的状态可由`remaining_count`、issued/finished位和ready队列成员关系定义；应选择单一规范表示，避免同时维护互相冲突的ready布尔、status表、scoreboard和多个队列。对于error/取消/多阶段执行，需增加必要状态并实际计费。

状态成本至少分开计算：

```text
dynamic bits ≈ resident_tasks × (remaining-count bits + lifecycle bits)
             + queue_entries × task-ID bits
             + event/generation tracking bits
             + resource/credit bits

static descriptor bytes = encoded fixed task + dependency + binding records
wakeup work = completion edges/messages actually traversed
arbiter work = eligible entries considered per issue
```

计数器位宽至少ceil(log2(max fan-in+1))；task/event id由window与复用协议决定。上述是state proxy，不是面积、功耗或Fmax。还要报告comparator数量/宽度、read/write端口、wakeup扇出、比较树深度、队列push/pop带宽、每cycle发射数及其延迟，不能用与4MiB SRAM的bit数比较代替成本验证。

采用event-driven宿主程序不意味着硬件每完成一个任务可以免费扫描全图。若模型用Python扫描实现语义，性能模型须另计wakeup/selection/dispatch latency或bandwidth；trace内记录这些延迟才能做粒度break-even。

### 6.1 必须实现的事件阶段

同timestamp遵循：全部完成事件→释放到期资源→所有依赖更新→remote visibility到达→ready集合更新→按建模issue/wakeup带宽仲裁。零延迟事件要通过明确delta-step或禁止规则保证终止。

该要求由原R2同刻完成编号偏差直接触发：仅换等价producer id会从220变120，见[audit结果](evidence/r2_audit_results.json)。如果真实scheduler一次只能处理一个completion，应让队列/端口模型显式决定耗时和顺序，而不是事件heap自动定义微架构。

## 7. 三类baseline的契约边界

| 基线 | Compiler输出 | Runtime选择 | 公平性要求 |
|---|---|---|---|
| A：Strong Static | 同一DAG/mapping/address/legal dependencies；为每resource或lane离线定序，可有跨engine预取流水 | self-timed等待完成；必要共享资源仲裁需写清楚 | 不是全局naive sequential；多种离线启发式/局部搜索，分布优化和独立测试seed；小图给最优gap |
| B：Completion-ready，static mapping | 与A相同合法合同与物理资源；静态priority | 可越过阻塞任务选择合法ready者 | 不改地址、增加bank/带宽，不读取future duration；计window/issue/wakeup成本 |
| C：Stronger Dynamic | 同一基本合同；若允许remapping须另列eligible绑定与数据搬运契约 | 利用当前资源/communication队列、criticality等已观测信息 | 与B分开单项消融，不能把多DMA/更多SRAM收益算作policy收益 |
| Oracle/下界 | 同一资源、依赖、容量 | 小图枚举或已知future的离线最优；大图只给可证下界 | CP/list heuristic即使知道时长也不是精确oracle；resource/critical path lower bound也不是可执行schedule |

Fully Static如果指固定start cycle，和NPU常见的固定顺序但completion自定时不是一回事。主baseline宜以强self-timed固定顺序为A，另设严格time-triggered对照，避免把预测误差导致的全局guardband当作“乱序收益”。

Fully Dynamic如果仍接受compiler给的显式DAG，则仅mapping/order动态，不是动态发现依赖的硬件；真正动态dependency discovery需要地址访问分析与额外硬件，作为不同轴单独建模。报告不能把较强在线priority称为fully dynamic graph analysis。

## 8. 多核、多 cluster、多 chip 的边界

首版建议compiler静态全局mapping+每域本地dispatch；它最符合用户给定的信息分工，同时保留centralized作为对照。拓扑是一组显式domain、共享resource和link，不按目录名称推测通信存在。

| 规模 | 必須显式建模 | 合同新增内容 |
|---|---|---|
| Core | MXU/VPU/DMA是否独立，局部buffer与引擎输入ready | engine绑定、local memory可见事件、必要资源capacity |
| Cluster | shared DMA/SRAM/NoC，local ready queue，控制带宽 | cluster资源id、跨core transfer、原子credit约束 |
| Chip | 跨cluster payload和completion message分别计latency/bandwidth | route或endpoint、目标可见事件、wakeup路由 |
| Multi-chip | 链路序列化、固定/变动delay、collective同步、buffer backpressure | chip endpoint、communication task、send/receive completion匹配与有限credit |

centralized scheduler每完成事件的fanout扫描可能形成瓶颈；distributed/hierarchical则新增消息、远端可见性与协调成本。应统一工作负载与资源，仅替换控制组织：记录resident-ready数量、fan-in/out、events/cycle、remote wakeup bytes、集中表大小、本地表大小、仲裁宽度、scheduler busy。规模增大不必然增加收益：更多同步、更深关键路径、相同瓶颈链路或更少可交换任务也可能使收益降低。

resource acquire要避免部分持有后等待其它资源造成运行时死锁。首版可采用“所有start资源同时可用才原子取得”，或者把DMA/compute/store拆成独立阶段、阶段间有buffer credit。DAG无环不足以证明有限队列/credit的分布式系统无死锁；需单独验证credit循环与progress。

## 9. 编译期、运行期和报告的最小验证

编译期应拒绝：重复task/event id、悬空依赖、图成环、缺少或错误resource、超capacity/对齐的span、不安全的alias reuse、不能执行的跨域transfer、缺失generation协议、wire字段溢出。对没有模型的操作输出unsupported，而不是用固定常数伪装成功。

运行trace应能独立检查：每task最多发射/成功完成一次；发射前所有required事件可见；资源占用不超量；不能覆盖未释放span；重复/stale completion不再次递减新task counter；失败不被当成功；最终输出的所有必要task确实完成；同一合同允许不同合法次序。

测试应以危险行为为中心：两个reader的last-read reuse、跨core delayed visible、同刻completion、多fan-in/out有限wakeup、有限queue backpressure、非法环、非法span、重复/旧代completion、浮点reduction排序锁。单个task和确定性资源饱和链应是动态无收益甚至倒退的控制组。

性能报告至少保留：延迟与吞吐定义、MXU/VPU/DMA/NoC利用率、dependency/resource/memory/communication/scheduler等待、critical-path dilation、ready occupancy、issue与wakeup频率、descriptor实际bytes、动态state bits和架构proxy。多种等待可以重叠，必须明确exclusive主因归属或报告overlapping类别，不能简单求和超过wall time。

粒度扫描应保持总计算/真实传输不变，再显式增加tile/task切分带来的边、descriptor、launch、wakeup和buffer数量；不同粒度如果改变fusion/reuse/traffic，应另报其变化。只有这样才能估计“收益/动态复杂度”，而不是让细粒度自动获得免费并行性。

## 10. 本轮可形成的最小科研判断

契约清晰本身是实验可靠性的前提，不直接等于论文创新。最小闭环先检验：同一静态binding与memory安全合同，head-only self-timed是否已经足够；若ready dispatch有收益，最小window、wakeup bandwidth、resource state是多少；更复杂C相对B的增益是否抵得过控制成本；收益集中在core异构pipeline还是cluster/chip通信。

若轻量B已取得C大部分收益，保留小的硬件机制；若strong A已足够，拒绝不必要动态硬件；若只有通信层有效，应把主张收敛成通信感知的延迟容忍派发；若只有更改memory plan才有效，应报告compiler分配与运行时自由度的联合问题，而不将其假装成核心内OoO胜利。
