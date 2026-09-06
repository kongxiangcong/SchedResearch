# 粒度、术语与最小动态状态

日期：2026-09-05。本文件为架构分析；与本轮实际实现的边界见 [sim/README.md](../sim/README.md)。

## 1. 两根轴：调度对象与调度域

instruction、micro-op、tile、kernel、task、subgraph是工作粒度；core、cluster、chip是控制/放置域。二者不能排成一条“越往下越粗”的尺度。可以在cluster域调度tile，也可以在core内调度跨engine的task。

| 对象粒度 | 暴露自由度 | 状态/决策开销 | 最合适的初始证伪 |
|---|---|---|---|
| micro-op/instruction | 很细的局部ILP、load-use latency | 大窗口、operand tags、每周期多issue；若推测则还要恢复机制 | 长kernel内部的真实load stall；先和编译软件流水比较 |
| tile | 局部data-ready、异构pipeline、partial通信 | task数量与fanout快速上升、buffer lifetime复杂 | 扫tile工作量/事件数/窗口；找收益饱和点 |
| kernel/task | engine边界、DMA/compute异步重叠 | 描述符和计数可较少 | fork-join、producer-consumer和独立流；作为R3主粒度 |
| subgraph | 很低调度率、局部编译可强优化 | 子图内部不暴露机会、不可抢占时易堵关键流 | 用macro task与显式tile DAG比较，保持总工作和I/O |

| 域 | 动态信息 | 最小局部机制 | 全局约束 |
|---|---|---|---|
| core | engine busy、local完成、buffer槽 | 小window、static-priority ready选择 | 数值顺序、local alias、load/store可见性 |
| cluster | shared DMA/SRAM/NoC端口和credit | 分engine ready queue、共享arbiter | 原子资源占用或无死锁多阶段申请 |
| chip | 跨cluster完成/通信队列 | 命名远程event、local dispatch | 有限event-ID、消息可靠性、backpressure |
| multi-chip | 消息/collective完成、straggler | 预映射通信计划+局部事件 | 远程写可见、buffer epoch、collective序及故障边界 |

## 2. 严格用词

| 名称 | 必须具备/典型核心 | 本研究何时可以这么叫 |
|---|---|---|
| Tomasulo | tag-based operand tracking、reservation stations、消除寄存器名相关的重命名/结果广播 | 仅在真的实现相应operand/rename语义时；普通task counter不够 |
| Scoreboard | 跟踪hazard/资源/就绪，典型经典版本无rename | 可称dependency scoreboard，但注明与CDC6600寄存器hazard发现的区别 |
| Reservation station | 等待operand/依赖和FU的有界条目 | 存wait refs的task window可叫RS-like，不因此拥有CPU全部OoO语义 |
| Dataflow machine | 操作数/token触发运算，常有tag匹配与空间执行 | task图仅事件驱动，宜更窄称dynamic dataflow/task scheduler |
| Hardware task scheduler | 有限状态管理任务、资源分配和dispatch | R3的准确大类；不天然包含动态DAG分析 |
| Dependency-driven execution | 按显式依赖决定可执行性 | FIFO跨engine token也属于它，未必可越过同engine队头 |
| Asynchronous execution | 发起与完成分离，允许重叠 | 双缓冲/显式DMA足够；异步不等于乱序 |
| Latency-tolerant dispatch | 等待某任务时执行合法替代任务 | 当前最合适的工作名称；不承诺能消除关键链 |
| Distributed task graph execution | 图的任务在多个域执行并交换完成信息 | 不要求每个域理解全图或支持迁移 |
| Hierarchical scheduler | 分层决策，local与上层有不同职责 | 按cluster复制同一arbiter只算分域dispatch；还未实现完整层次协调 |

机制证据与近邻见 [prior art registry](../literature/prior_art_registry.md)。例如[Gemmini](https://github.com/ucb-bar/gemmini)跨load/store/execute controller有顺序自由，各controller内部仍有序，不能被概括成“完全静态”或“CPU式OoO”。

## 3. Execution contract：静态复杂度压缩到哪里

编译器负责graph reasoning、合法placement、alias、layout/bank映射、数值归约和资源需求。硬件消费的是：

```text
task_id, epoch
engine / placement binding
payload / addresses / sizes
wait events or predecessor count + successor notification table
completion event and visibility scope
resource footprint / buffer ownership
static priority (optional)
```

对应WHEN、WHERE、WHAT resource、WHAT wakes it、WHAT ordering。完整DAG不必放进全关联搜索结构；但依赖信息并没有消失：它存在descriptor、successor表、事件命名空间或静态流结构中。降低动态SRAM的设计可能增加descriptor带宽或静态存储，必须同时报告。

data edge、WAR/WAW alias edge、numerical-order edge、communication edge属于legal order；共享独占资源通常交给arbiter，不要默认给所有resource任务再加固定先后边，否则正好消灭要测的自由度。复用边属于物理地址下真实必须遵守的限制，运行时不能称其“伪”就跳过。

完成事件必须表示需要的可见性：MXU计算结束不必然意味着远程consumer可读。对远程DMA，源buffer何时可复用、目的buffer何时可读可能是两个事件。多轮循环复用ID需要epoch/generation和最大在途证明，防止旧完成误唤醒新任务。

Linear Layouts可用于推导placement、bank footprint与局部性，但不是同步协议或dependency counter。只有在压缩resource footprint/地址规则时出现测得的元数据优势，才值得纳入核心贡献；否则先用简单显式layout。

## 4. Minimum Necessary Dynamic Hardware

起点：有限resident task状态、依赖计数或wait references、ready集合、engine/resource busy或credit、完成通路及一个static-priority arbiter。task状态可包含unadmitted/waiting/ready/running/done，但不能拿Python对象大小当硬件面积。

逐项可删性：单后继链不需要通用counter；编译固定fan-in可以编码wait mask；只用FIFO可不建全关联RS；固定mapping不需要work stealing。本轮固定物理地址、显式保持alias先后且不动态消除名相关，因此不需要rename；这与控制推测是不同问题，非推测机器也可以用rename消除WAR/WAW。是否需要ROB/退休或恢复结构，应由precise exception、replay和外部可见性要求决定；本轮单次无故障DAG未要求这些机制。一个可靠本地域可暂不需要分布式协议；没有反馈边的有限DAG可用一次性event IDs。不要一次装入所有候选结构。

成本符号（抽象bit/操作计数，不是PPA）：

\[
S_{task}\approx W[b_{id}+b_{state}+\lceil\log_2(F_{in}+1)\rceil+b_{prio}+b_{resource}+b_{epoch}]
\]

\[
S_{edge}\approx |E|b_{id},\quad S_{ready}\approx Qb_{id},\quad
\lambda_{wake}\approx\lambda_{complete}\bar F_{out}.
\]

W为resident window，Q为ready queue深度。对于分域计数，local/remote fanout分开。若W项每项K个wait refs与P个completion通道广播匹配，朴素比较规模为O(WKP)；successor-indexed counter将它换成scatter updates及存储端口冲突，不是无代价O(1)。

平均完成率λ与fanout的乘积只给必要带宽；burst还要求排队容量。为避免控制饱和，issue rate≥实际任务启动率且wakeup service>长期平均arrival。若P个engine平均每g周期结束一个task，粗略λ≈P/g；g越小越可能先耗尽scheduler而非算力。

对平均任务工作g、单次开销h，完全串行暴露时overhead fraction约h/(g+h)；有重叠时不能直接相加，必须仿真。一个工作点的目标是：在equal area/bandwidth或明确cost budget下，找到最小W、issue宽度、wakeup带宽，使性能距离最好的可实施策略不超过预先定义ε。

## 5. 集中、分布、层次化

| 结构 | 优点 | 风险 | 公平比较 |
|---|---|---|---|
| Centralized | 完成/资源观察简单；全局ready选择 | 全局fanout、wire latency、端口和仲裁路径 | 固定总issue/wakeup带宽、总state，不能只给分布式更多硬件 |
| Distributed local | 大量local edges不出域，近数据、线短 | 局部队列不均、远程credit/事件、跨域反压 | 同样mapping与跨域流量；统计remote事件而非只看local效率 |
| Hierarchical | local处理多数task，上层只处理少量跨域事件或配额 | 上层状态仍可能增长，重复计数/coordination复杂 | 上下层各自延迟与traffic、总state，明确层间契约 |
| Static global + local dynamic | 不迁移、地址简单；局部以completion消除相位误差 | 无法修复严重mapping imbalance | 与更强静态global mapping、离线路由及调度比较 |

初始首选是实验比较，不是承诺层次结构获胜。若动态收益只在DMA仲裁处存在，应收窄为communication/resource-aware asynchronous execution；若强静态已经足够，应拒绝新增复杂结构。
