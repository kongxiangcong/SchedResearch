# Runtime uncertainty：来源、可消除部分与机会

日期：2026-09-05。下表是机制分析与待测假设；不是目标NPU实测。R1记录的analytical cost不能代替延迟分布。工业动机及核验层级见 [industry_architecture.md](../literature/industry_architecture.md)。

## 1. 不要把所有慢都叫随机计算延迟

对任务 i，把观测时间分解为：descriptor可见/等待、依赖可见等待、资源排队、实际执行或数据服务、完成传播。实际执行的duration与等待时间分别记录，避免把同一DMA阻塞同时计入memory stall和resource stall。

| 不确定性 | 静态可知/可改善 | 无法完全提前消除的条件 | 最小建模与可利用信息 |
|---|---|---|---|
| Compute latency variation | 固定shape/dtype、dense阵列、固定频率下常近确定；padding/尾块可计算 | 数据相关稀疏跳零、提前退出、DVFS/热限制等确实改变周期或时间 | 默认compute不加随机；特设variable-work场景。DVFS区分cycles与ns，不能独立随机化所有task |
| Memory latency | 已知地址可改layout/预取/顺序，静态可预测一部分row locality | DRAM refresh、row-buffer状态、其他master、cache misses及memory queue | 请求/返回事件；下一轮用Ramulator，当前只以synthetic服务分布作敏感性 |
| DMA contention | 已知本应用需求可排队、双缓冲、分通道 | 多核实际到达次序、外部DMA、queue credit/outstanding变化 | 独立DMA容量与memory服务；不能把多通道等同无限带宽 |
| Shared SRAM contention | bank映射、读写数量、可错开tile通常可优化 | 多engine相位漂移，动态请求冲突 | bank/port resource bundle；动态可错开需求，不能生成额外端口 |
| NoC contention | route/流量字节、静态时分/placement可知 | 不同源到达相位、backpressure、仲裁、队头阻塞 | 链路/注入资源、完成事件；当前聚合资源不等于flit模型 |
| Producer-consumer timing | 数据边完全可知、pipeline可规划 | producer的真实完成与写入可见时刻 | completion event只在consumer可读时满足；图本身不是新随机源 |
| Heterogeneous engine latency | MXU/VPU/TMU时长不同是静态异质性 | 不同engine服务方差/启动开销/同步到达导致失配 | 各engine独立服务模型；**不同不等于不可预测** |
| Load imbalance | 固定tile数/shape可均衡、改partition | MoE token分布、可变序列、请求到达或稀疏性 | 比较固定mapping下的选序与允许迁移的上界，二者不能混称OoO |
| Synchronization | DAG依赖和必要barrier可分析，过度同步可静态删 | straggler、事件网络阻塞、接收buffer无credit | wait/signal及epoch；同步成本不等同算子执行时间 |
| Inter-cluster communication | shared SRAM/NoC路径与collective树可预排 | cluster间进度漂移和共享注入资源竞争 | local events+远程完成，测fanout和注入压力 |
| Inter-chip communication | mapping、消息大小、collective order可预排 | link/交换机排队、其他通信、同步尾部、不同chip进度 | 分层completion/credits；同一消息的可见时延和数据占用分开 |

固定地址并不能让所有内存时延确定；scratchpad也不能消灭外部DRAM/NoC的排队。反过来，某些可预测机器主动移除动态仲裁，减少了需要容忍的不确定性。这是架构取舍，不是编译器必然无能。TPU v1作者明确将确定执行与tail-latency目标联系起来：[ISCA 2017原论文](https://arxiv.org/abs/1704.04760)。

## 2. 六个第一性原理问题的回答

**有哪些真实不确定性？** 最可信的一般来源是共享memory/DMA/NoC到达相位和外部干扰、数据相关工作量、请求长度/路由，以及完成传播。目标设备上是否存在、幅度多少仍要测。dense MAC在固定shape下的大幅独立随机波动不是合理默认。

**是否足以偏离最优顺序？** 不是由CoV一个量决定。关键在竞争同一resource的任务ready次序是否翻转、是否有可替代任务、以及这个翻转是否影响关键路径。bounded小抖动在紧密相接的两个producer附近就能改变顺序；很大的全局共同延迟也可能完全无法隐藏。

**LLM/DiT哪里可能获益？** 多head/tile、独立Q/K/V或SwiGLU两支（前提是没有被融合掉）、MXU/VPU/DMA交错、MoE不均衡及多请求共存、通信完成后局部可继续的tile。优先测真实lowering保留下来的并行，而不是根据算子名字想象。

**哪里高度deterministic？** 固定shape、固定频率且数据全部resident、已软件流水的规则dense阵列通常更接近确定执行。另一个独立轴是**有没有可利用的选择自由度**：单链、不可分的归约、持续满载的单通道带宽瓶颈、被strong fusion完全吸收的中间算子，即使延迟随机，也可能没有能改善端到端表现的替代动作。不能把“无重排收益”误称为“无不确定性”。

**优秀compiler能消除多少bubble？** 没有跨设备通用百分比。先拿掉launch开销、布局/拷贝冗余、可证明多余的barrier，做fusion、双缓冲、prefetch、tile/reduction拆分、静态资源仲裁和memory-aware scheduling；用exact小图与多个离线候选检验。不能先把这些都留给动态然后报告speedup。

**残余stall来自哪里？** 不可提前观察的资源状态、尾部到达/相关性、容量让合法并行减少、有限窗口未暴露ready task、控制带宽不够，以及本来就无法并行的data critical path。只有部分stall是顺序自由可恢复的。

## 3. Workload opportunity map

| Workload | 可能产生的机会 | 强静态先做什么 | 无收益/失效条件 |
|---|---|---|---|
| LLM prefill Attention/QKV | 多head/tile到达、softmax VPU与MXU交错 | QKV融合、FlashAttention式IO缩减/流水、静态head切分 | dense持续满载；attention被单大kernel封装且无tile事件 |
| GQA/KV cache/decode | KV分片不同到达、多个请求/heads并行 | GQA复用、KV局部放置、批处理、prefetch、合适分片 | 单请求长串行链、单DMA已饱和；随机重排不增加带宽 |
| RMSNorm/SwiGLU | reduction→scale、gate/up两支、VPU/MXU交接 | fusion、分片归约、静态software pipeline | 融合后没有独立task；改变浮点归约顺序不被许可 |
| MoE | expert token数不同、all-to-all尾部、局部expert先ready | load-aware静态布局、routing后计划实例化、packing | 数据相关路由的改善被错误归因于OoO；本地全无可执行expert |
| Multi-core tensor partition | 本地tile先完成后局部消费 | balance、通信计算重叠、reduce-scatter/all-gather规划 | 必须全局barrier的后续；动态改变归约顺序影响数值 |
| DiT Attention/FFN/AdaLN | MXU/VPU交错、conditioning先ready、tile/head并行 | static block流水、fusion、conditioning预计算 | 固定尺寸、相同engine负载且repeat step稳定 |
| CFG | cond/uncond两支及其不同进度 | 首先比较batch/M维折叠和buffer代价 | 折叠更快或容量迫使两支串行；不能删掉alias edge |
| Repeated denoising | 多step给profile/calibration机会，局部重用 | cost model随step类别、静态复用/skip决策 | step k+1依赖k结果，不能当独立请求并行；近似cache/跳步是算法变化 |

当前实验仅结构motif，不能把“DiT”名称当真实模型导出证据。需要记录shape、dtype、batch、序列长度、CFG实现、合法数值误差和placement，才可升级为模型级实验。

## 4. 规模扩大不保证收益增加

若独立producer的完成CDF为F，n方join的最晚完成CDF为F(t)^n，n增加可放大尾部。但这依赖独立性；相关拥塞可能让全体一起慢。更多核同时增加可替代任务、通信、同步、wakeup traffic，也可能减小局部task时长、降低控制成本容限。

因此分别sweep：core数、每核并行流、cluster数、chip数、每级带宽、跨域edge比例、fanout、噪声相关性。保持总工作固定（strong scaling）和每核工作固定（weak scaling）两套；不能只增加工作规模就把变化称为scalability。

## 5. 真实测量最小字段

每task记录：stable task/epoch、shape/bytes、预测duration、descriptor到达、dependencies visible、入ready queue、issue、engine开始/结束、最后写入可见、完成事件发送/到达、DMA outstanding、bank冲突、NoC credits和路径。按engine/resource/phase条件化后，测均值、p50/p95/p99、CoV、producer ready inversion率与同域相关性。

对counter做互斥归因；多种同时成立的stall另存bitmask，不能将总task等待直接当end-to-end stall。反事实回放保留同一输入和相同外部环境，对调度诱发的memory/NoC排队重新计算。将一次执行已经排队后的整段duration固定重放，可能失真，因为它是旧策略的结果。
