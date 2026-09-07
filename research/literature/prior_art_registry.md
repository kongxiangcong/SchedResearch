# Prior-art registry

检索/核验日期：2026-09-05。这是研究证据登记，不是列出的每篇都已全文阅读。

状态：**D**=原始全文中方法、假设、范围有针对性读取；**A**=原始摘要/部分正文；**M**=官方会议/作者题录；**I**=继承 R2，本轮未重新核验。来源事实与本研究推论分列。原始批量输出和网络错误在 [sources](sources)，完整表在 [search_report.md](search_report.md)，7 篇深读在 [novelty_redteam.md](../analysis/novelty_redteam.md)。

| ID | 工作 / 年份 / primary source | 状态 | 已支持的事实 | 本研究用途或限制 |
|---|---|---|---|---|
| F01 | [Tomasulo, An Efficient Algorithm for Exploiting Multiple Arithmetic Units, 1967](https://courses.grainger.illinois.edu/ece511/fa2005/papers/Tomasulo.1967.IBMJRD.pdf) | A/部分原文 | common data bus、register tags、多算术单元 | 不把 ready counter 统称 Tomasulo |
| F02 | [Thornton, Design of a Computer: The Control Data 6600, 1970](https://archive.computerhistory.org/resources/text/CDC/cdc.6600.thornton.design_of_a_computer_the_control_data_6600.1970.102630394.pdf) | M | 原著可追溯 scoreboard | 本轮未细读，不推断硬件面积 |
| F03 | [Lee–Ha, Scheduling Strategies for Multiprocessor Real-Time DSP, 1989](https://doi.org/10.1109/GLOCOM.1989.64160) | M+后继原文引用 | FS/ST/SA/FD 分类源头 | SA 不自动规定 hazard detection |
| F04 | [Bambha–Bhattacharyya, Communication Strategies for Shared-Bus Embedded Multiprocessors, 2005](https://doi.org/10.1145/1086228.1086233) | D/摘要与§2 | OT/ST/dynamic 随 variance 与同步代价出现 crossover | DOI 对应 EMSOFT；不是任意 NPU 的定理 |
| F05 | [SPDI Scheduling for EDGE Architectures, PACT 2004](https://www.cs.utexas.edu/~lin/papers/pact04.pdf) | D | 静态放置、显式消费者、dynamic issue | 最直接范式先例；SPEC2000/指令粒度 |
| F06 | [A static-placement, dynamic-issue framework for CGRA loop accelerator, DATE 2017](https://past.date-conference.com/proceedings-archive/2017/pdf/0586.pdf) | A/正文开头 | PE token buffers 支持动态 issue | SPDI 用于 accelerator 也非新颖 |
| F07 | [Task Superscalar, MICRO 2010](https://upcommons.upc.edu/bitstream/handle/2117/11445/05695528.pdf) | D/§I+架构概述 | task 输入输出的动态 dependency discovery、memory-object renaming、分布式前端 | 编译显式图可省依赖发现，硬件task调度已存在 |
| F08 | [Carbon, ISCA 2007](https://doi.org/10.1145/1250662.1250683) | A | hardware 支持细粒度 task distribution 以减软件开销 | 不等于 completion uncertainty 收益 |
| F09 | [TaskStream, ASPLOS 2022](https://par.nsf.gov/servlets/purl/10320225) | D | typed edges、coreMask、sizehint、NoC、有限状态 | 与 hierarchical contract-guided dispatch 接近 |
| F10 | [VTA, 2018/2019](https://arxiv.org/abs/1807.04188) | D | load/compute/store、RAW/WAR queues、compiler dependency bits | 最小 self-timed overlap baseline |
| F11 | [Gemmini, 官方源码文档](https://github.com/ucb-bar/gemmini) | D/README ROB/DAE/DMA | 跨 controller OoO；各 controller in-order；banked scratchpad 与 DMA | 不应只因名为 ROB 就归类完整 CPU OoO |
| F12 | [ASPEN, NeurIPS 2023](https://papers.neurips.cc/paper_files/paper/2023/hash/d899a31938c7838965b589d9b14a5ca6-Abstract-Conference.html) | D | offline tile DAG、DSE、Ready Pool、atomic parent count | 分布式软件机制近邻，NPU成本未给出 |
| S01 | [Rammer, OSDI 2020](https://www.usenix.org/conference/osdi20/presentation/ma) | A | rTask 静态时空 co-scheduling | 强静态不能局限 operator串行 |
| S02 | [Welder, OSDI 2023](https://www.usenix.org/conference/osdi23/presentation/shi) | A | tile graph 中联合 memory hierarchy 优化 | fusion/reuse/prefetch基线 |
| S03 | [Safe Optimized Static Memory Allocation for Parallel Deep Learning, MLSys 2023](https://proceedings.mlsys.org/paper_files/paper/2023/file/676d8419c61f299feb88c28b40edd3b1-Paper-mlsys2023.pdf) | A/正文问题定义 | 并行streams安全复用与offset分配 | partial-order lifetime先例 |
| S04 | [PipeThreader, OSDI 2025](https://www.usenix.org/conference/osdi25/presentation/cheng) | D | sTask/sEU、固定二维sProgram、barrier refs | 异构流水强静态邻域 |
| S05 | [LATTICE, arXiv2607.17422v3, 2026](https://arxiv.org/html/2607.17422) | D | memory plan contract、reuse edges、plan-preserving timing search | 直接修正R2所推memory contract novelty |
| S06 | [TileLink, 2025](https://arxiv.org/html/2503.20313) | D/§3–4,§7 | tile signal/data primitives；acquire/release；static/dynamic mapping | 通信契约、可见性与MoE实例化 |
| S07 | [Linear Layouts, 2025起](https://arxiv.org/html/2505.23819) | D/§3–4 | binary linear algebra tensor layouts | 只解决layout子问题，不包含依赖生命周期 |
| S08 | [Tawa, 2025](https://arxiv.org/html/2510.14719) | A/§III概述 | aref 自动warp specialization与流水 | 可对照编译器生成异步合同 |
| N01 | [HwSch/openNVDLA, JKSU CIS2026](https://link.springer.com/article/10.1007/s44443-026-00513-z) | D | OCSR、64bit指令、32ROB、CNN/host overhead评估 | 非 strong-static OoO gain证据 |
| N02 | [HyperParallel-MoE, 2026](https://arxiv.org/html/2605.23764) | A/调度正文 | static tile taskflow、跨AIC/AIV事件 | 强NPU静态异构通信流水参照 |
| N03 | [LLM Serving on Multi-core NPUs, 2025](https://arxiv.org/html/2510.05632) | A | 多层模拟与parallelism/core placement/PD策略 | 模型分解与现实静态optimizations |
| N04 | [SegFold, ISCA2026](https://arxiv.org/abs/2606.26701) | A | dynamic reuse/work remapping用于SpGEMM | 稀疏动态结构近邻；不等于dense uncertainty |
| N05 | [ONNXim, CAL2024](https://arxiv.org/abs/2406.08051) | A | deterministic tile compute、DRAM/NoC周期模型 | 核心runtime uncertainty建模依据 |
| N06 | [Survival of the Fastest, FPGA2024](https://github.com/EPFL-LAP/fpga24-more-ooo) | A+源码说明 | dataflow同op多实例重排 | finer OoO仍有额外tag/queue代价 |
| N07 | [CRUSH, ASPLOS2025](https://doi.org/10.1145/3669940.3707273) | M | credit-based FU sharing研究 | 全文下载失败，不给算法细节 |
| N08 | [Mosaic/iTex, ASPLOS2025](https://doi.org/10.1145/3676641.3716262) | M | DLA ILP研究存在 | core-level OoO方向的待读阻断项 |
| N09 | [AccelFlow, HPCA2026](https://experts.illinois.edu/en/publications/accelflow-orchestrating-an-on-package-ensemble-of-fine-grained-ac/) | A+作者slides | traces驱动on-package accelerator序列与branch | heterogeneous hardware orchestration已有先例 |
| N10 | [TEMP, 2025/HPCA2026](https://arxiv.org/abs/2512.14256) | M/A | wafer-scale physical-aware partition/mapping | 拓扑必须给静态同等信息 |
| N11 | [Pistil, Hot Chips2026 poster](https://hc2026.hotchips.org/) | M | 标题确认16nm、20chiplet2.5D、端侧distributed SLM；Harvard/Lockheed Martin | 未取得poster架构正文，不猜scheduler/cache/测量结果 |
| N12 | [DASO, 2021](https://arxiv.org/abs/2104.05588) | A | 异步/分层gradient synchronization | 改training语义，与精确inference dispatch分开 |
| E01 | [CUDA Graphs 官方契约](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/cuda-graphs.html) | D/§4.2.1,4.2.2,4.2.6 | whole graph实例化、dependency完成后可调度、device graph launch | API行为确认；不反推出未公开硬件ready queue实现 |
| E02 | [Programmatic Dependent Launch](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/programmatic-dependent-launch.html) | A | consumer可在producer整体完成前启动，需显式同步 | task complete与data-ready不是同一事件 |
| I01 | [Pinter, PLDI1993](https://doi.org/10.1145/155090.155114) | I | R2记录register allocation与scheduling自由度 | 需后续准确方法复核 |
| I02 | [Goodman–Hsu, ICS1988](https://doi.org/10.1145/55364.55407) | I | R2记录storage dependencies | 同上 |
| I03 | [COSMA, 2023](https://arxiv.org/abs/2311.18246) | I | R2记录schedule/allocation/replacement联合问题 | 与LATTICE差异需细读 |
| I04 | [SoMa, 2025](https://arxiv.org/abs/2501.12634) | I | R2记录DRAM communication schedule search | DMA arbitration新颖性红队待读 |

## 证据分层

- **Confirmed fact**：上表 D/A/M 中相应原始来源实际披露的内容；M 只确认题录存在，A 不声称读完整方法。
- **Credible secondary information**：本学术主结论尽量不用。搜索聚合仅用于定位PDF；工业细节另见 industry_architecture.md。
- **Architectural inference**：上述“研究用途”列与 R3 建议是比较后推论。跨领域的相似性不是已证明性能等价。
- **Speculation**：任何“尚未有work覆盖”“少量state面积可忽略”“多chip必然更有用”都不作为确认事实。

## 缺口登记

2026的Mosaic全文、HPCA2026若干候选、Pistil正文、动态HLS完整实现，以及R2继承的Pinter/partial-order/SDF文献仍可继续扩展。本轮已足以否定宽泛 novelty 宣称，但不足以证明某个更窄机制已有或没有独占新颖性。专利应另做逐权利要求对照。
