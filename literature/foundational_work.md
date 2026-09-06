# 基础先例与严格分类

核验日期：2026-09-05。本文承接 R2，所有“确认”指公开材料实际支持的机制，不代表本地复现。

## 执行模型先拆成独立轴

“static / dynamic”至少涉及 dependency discovery、placement、per-resource order、issue time 四轴。完整 DAG 静态已知时，硬件仍然可能动态决定就绪任务的顺序；静态顺序也可以由 completion 自定时推进。仅看到异步指令、完成事件或 ROB，不能据此判断一个系统具有任意 ready-set 重排能力。

| 名称 | 核心判据 | 与本研究的关系 |
|---|---|---|
| Fully static | placement、顺序、发射时刻均在离线确定 | 有精确时序保证时有意义；不能作为唯一静态基线 |
| Self-timed static | placement 和各资源顺序固定，按实际完成推进 | 必须包含的强静态基线；DMA/compute 可以交叠 |
| Static-assignment | placement 固定，各资源执行顺序动态选择 | 是候选 Hybrid 的调度分类，但不指定具体微结构 |
| Fully dynamic | placement、顺序、时刻动态决定 | 不意味着必须动态发现依赖，显式 DAG 同样可以动态 mapping |
| Scoreboard | 维护数据/结构冲突，满足条件后允许执行 | 泛称任务状态表容易与 CDC 6600 混淆，应说明是否动态判 RAW/WAR/WAW |
| Tomasulo | reservation stations、tag 化操作数/重命名、完成广播等机制 | 显式 task DAG + counter 不自动需要这些机制；ROB 不是原始 Tomasulo 的定义要件 |
| Reservation station | 待执行项及其操作数/依赖就绪信息的结构 | 是组件，不是完整执行模型 |
| Dependency-driven task dispatch | 显式事件触发 ready，按资源状态派发 | 最贴近本轮最小原型的中性名称 |
| Distributed / hierarchical | 状态及决策的空间组织方式 | 与上述静/动态分类正交 |

Lee–Ha 1989 的四分类在后续作者文献中明确复述；本轮直接读取 Bambha–Bhattacharyya 2005 正文 §2 支持这些定义。R2 把 DOI `10.1145/1086228.1086233` 记成 TECS，但该 DOI 的会议版是 **EMSOFT 2005**，后续 journal 版本应另登记，不能混写。[EMSOFT 官方目录](https://www.sigbed.org/emsoft-info/confs/emsoft2005.html)、[论文正文](https://citeseerx.ist.psu.edu/document?doi=dcb1e054c92129c9fc0845dc017171966bf9a1fe&repid=rep1&type=pdf)、[Lee 团队书目](https://ptolemy.berkeley.edu/books/Systems/chapters/Bibliography.pdf)。

## CPU、EDGE 和 dataflow

Tomasulo 1967 的原始问题是从顺序指令流中发掘多个算术单元的并行，通过寄存器 tag 和 common data bus 保持必要依赖。它不是“所有完成驱动调度器”的统称。端侧 NPU 已静态得到地址和依赖时，可以省去相当一部分动态依赖发现和重命名工作；是否还需有限对象版本、提交顺序或精确异常，取决于 execution semantics。[Tomasulo 原文，摘要与实现说明](https://courses.grainger.illinois.edu/ece511/fa2005/papers/Tomasulo.1967.IBMJRD.pdf)。CDC 6600 的 scoreboard 历史来源可由 [Thornton 原著](https://archive.computerhistory.org/resources/text/CDC/cdc.6600.thornton.design_of_a_computer_the_control_data_6600.1970.102630394.pdf) 追溯；本轮未完成该书全文核验，因此不以历史实现细节论证面积。

EDGE/SPDI 是概念上极近的先例。PACT 2004 §1–2 把编译器决定 ALU placement、指令中显式给出消费者位置、硬件按输入到达 issue 分开；§3 调度考虑 locality、contention 和 speculation，§4–5 在 SPEC2000 与分布式 ALU 模型上评估。它不仅覆盖“静态 mapping + 动态发射”，也早已讨论避免集中关联搜索和片上通信延迟。区别是指令/block 与通用程序语义；不是本研究的多层 NPU memory-lifetime contract 或 workload 校准。[作者全文](https://www.cs.utexas.edu/~lin/papers/pact04.pdf)。

SPDI 也已扩展到 CGRA：DATE 2017 在 PE 增加 token buffer，由编译器静态映射操作与连线、运行时竞争发射，评估对比 REGIMap/RS/EPIMap。这阻断“从 CPU SPDI 换成加速器即新颖”的说法；不能将其 kernel/loop 数字外推为 LLM/DiT 收益。[会议论文](https://past.date-conference.com/proceedings-archive/2017/pdf/0586.pdf)。

## 硬件任务调度与层次 dataflow

Task Superscalar（MICRO 2010）从标注输入/输出的任务流中**动态发现依赖**，其前端支持分布式 dependency decoding，并考虑内存对象重命名。论文 §I、Fig.2 和 §IV 区分前端和后端，实验是 scientific workloads。显式 compiler graph 可以绕过其依赖发现成本，但不能把“硬件调度 task”当新机制。[作者机构全文](https://upcommons.upc.edu/bitstream/handle/2117/11445/05695528.pdf)。

Carbon（ISCA 2007）研究把细粒度 task 的软件排队开销移到硬件；其名称、作者与研究动机已核验，但本轮未完成作者全文方法细读，因此只作为 task-queue/work-distribution 先例，不作为最接近机制的最终判断依据。[论文 DOI](https://doi.org/10.1145/1250662.1250683)。Picos 是后续 OmpSs 硬件 runtime 邻域，沿用 R2 待继续核验，不宣称本轮已重读。

TaskStream（ASPLOS 2022）比“全动态硬件重新理解任务”更接近用户的协同边界。§2.2 以 typed edges 表达 creation/streaming/batching，`coreMask` 给合法位置，`sizehint` 给工作量提示，`depDistance` 表示 streaming 关系；§3.1 将 task 与指令 dataflow 层次结合。§3.4 说明自动高层编译器仍是未来工作。§4 的 Delta 有 mesh NoC、banked scratchpad、shared cache 和有限 task/stream 状态，§5 使用 gem5/DSAGEN。它直接威胁“给硬件少量编译提示，局部调度同时兼顾通信与负载”的宽泛主张。[全文](https://par.nsf.gov/servlets/purl/10320225)。

## 强静态与 memory freedom 的历史

固定 buffer 配置和程序结构不意味着静态排程只能顺序执行。Rammer（OSDI 2020）用 rTask 静态时空 co-scheduling 暴露跨/内算子并行；Welder（OSDI 2023）在 tile graph 上搜索 memory hierarchy 内的复用/融合。因此动态收益必须对照经过相同分解、融合、prefetch 和 memory 优化的静态版本。[Rammer](https://www.usenix.org/conference/osdi20/presentation/ma)、[Welder](https://www.usenix.org/conference/osdi23/presentation/shi)。

MLSys 2023 的 Safe Optimized Static Memory Allocation for Parallel Deep Learning 输入包含计算图和 execution streams，先证明两 tensor 是否可安全复用，再按 reuse/contiguity constraints 分配 offset。它处理并行执行下的静态安全，但不能据摘要推断为“选择 runtime reordering contract 使收益最大”。[会议全文](https://proceedings.mlsys.org/paper_files/paper/2023/file/676d8419c61f299feb88c28b40edd3b1-Paper-mlsys2023.pdf)。R2 中 Pinter/Goodman、partial-order scheduling、SDF buffer-throughput Pareto 是合理追溯线索，本轮仅将其列为继承条目；精确 novelty 判断首先受已全文核验的 LATTICE 2026 阻断。

Bambha–Bhattacharyya 的 shared-bus/SDF 实验显示调度开销与时间波动会改变 OT/ST/dynamic 的相对优势。这个结果支持测 crossover，**不证明**任意 DAG 下“只有重尾有效”或“没有复用边即动态无效”。其图、通信模型和策略与本轮不同，阈值必须重测。[原文摘要及 §2](https://citeseerx.ist.psu.edu/document?doi=dcb1e054c92129c9fc0845dc017171966bf9a1fe&repid=rep1&type=pdf)。
