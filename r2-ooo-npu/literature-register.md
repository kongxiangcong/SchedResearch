# Round 4 文献登记：dependency contract + dynamic dispatch

检索日期：2026-09-03

方法：Web 检索打开 DOI / arXiv / 会议 proceedings / 作者主页 / 官方文档核对题名、年份与 venue。Semantic Scholar API 在本轮触发 429（无 API key），未能用于批量核对。

- **已核验**：本轮打开过原始页面或官方 PDF，题名与年份一致。
- **引用中核验**：仅在其他已核验文献的正文/参考文献中看到。
- **记忆/未核验**：来自训练记忆，本轮未重新核对；使用前应复核。

标记沿用 round 2/3：**【审】** 同行评审、**【预】** 预印本、**【技】** 官方文档/工程说明。

## 1. 执行模型分类与调度理论（判定“它是什么”）

| 文献 | 年份 / venue | 标识符 | 核验 | 与本轮的关系 |
|---|---|---|---|---|
| Lee & Ha, Scheduling Strategies for Multiprocessor Real-Time DSP【审】 | 1989 GLOBECOM | DOI 10.1109/GLOCOM.1989.64160 | 已核验（DOI 页 + Ptolemy 页） | 四分类：fully dynamic / static-assignment / self-timed / fully static；本方向 = static-assignment，TARS 今天 = self-timed |
| Ha & Lee, Quasi-static Scheduling for Multiprocessor DSP【审】 | 1991 ISCAS | DOI 10.1109/ISCAS.1991.176346 | 已核验（DOI 页） | 数据相关构造（if/loop/recursion）的准静态调度；P3 的先例 |
| Ha, Compile-Time Scheduling of Dataflow Program Graphs with Dynamic Constructs（博士论文） | 1992 UC Berkeley | ptolemy.berkeley.edu | 已核验 | 四分类的完整定义文本 |
| Sriram & Lee, Determining the Order of Processor Transactions in Statically Scheduled Multiprocessors【审】 | 1997 J. VLSI Signal Processing | DOI 10.1023/A:1007956226232 | 已核验（Ptolemy PDF） | ordered transactions：编译期定通信顺序、硬件强制执行；可选到与 self-timed 无性能损失的顺序 |
| Bambha & Bhattacharyya, Communication Strategies for Shared-Bus Embedded Multiprocessors【审】 | 2005 ACM TECS | DOI 10.1145/1086228.1086233 | 已核验（DOI 页 + UMD PDF） | 概率执行时间下 OT / ST / FD 的 crossover 实验：低变异性 OT 优，变异性升高后 ST、FD 依次胜出；本轮表 B-1 的理论对照 |
| Policella, Cesta, Oddi, Smith, Generating Robust Schedules through Temporal Flexibility【审】 | 2004 ICAPS | icaps04 proceedings | 已核验 | Partial Order Schedule 定义、鲁棒性度量、resource-envelope 与 earliest-start 两种生成法 |
| Policella, Cesta, Oddi, Smith, From Precedence Constraint Posting to Partial Order Schedules【审】 | 2007 AI Communications | CMU RI 页 | 已核验 | PCP：张贴最少前序约束使任意时间可行解资源可行；“合法执行空间”的正式先例 |
| Stuijk, Geilen, Basten, Exploring Trade-offs in Buffer Requirements and Throughput Constraints for SDF Graphs【审】 | 2006 DAC | — | 记忆/未核验 | 自定时 SDF 的 buffer–吞吐 Pareto；FIFO 深度版的“复用 ↔ 自由度” |
| Bhattacharyya 等，Shared Memory Implementations of SDF Specifications【审】 | 2000 DATE | DATE 2000 proceedings PDF | 已核验 | SDF buffer 共享的 lifetime 模型 |

## 2. 编译器：分配 ↔ 调度自由度

| 文献 | 年份 / venue | 标识符 | 核验 | 与本轮的关系 |
|---|---|---|---|---|
| Goodman & Hsu, Code Scheduling and Register Allocation in Large Basic Blocks【审】 | 1988 ICS | DOI 10.1145/55364.55407 | 已核验（DOI 页） | 寄存器复用引入 storage-related dependency 限制后调度；DAG-driven 分配 |
| Pinter, Register Allocation with Instruction Scheduling【审】 | 1993 PLDI | DOI 10.1145/155090.155114 | 已核验（DOI 页） | parallel interference graph：不引入伪依赖的最优分配；门 A 的算法骨架 |
| Bradlee, Eggers, Henry, Integrating Register Allocation and Instruction Scheduling for RISCs【审】 | 1991 ASPLOS | DOI 10.1145/106972.106986 | 引用中核验（Pinter 参考文献） | 相位次序问题 |
| Beaty 等，CRAIG: Combining Instruction Scheduling and Register Assignment | — | MSU Denver PDF | 已核验（PDF） | 对 Pinter 方法的解读与改进 |
| Safe Optimized Static Memory Allocation for Parallel Deep Learning【审】 | 2023 MLSys | proceedings.mlsys.org | 已核验 | 给定并行流，求可证明安全的最小复用约束集 + offset 分配；MindSpore |
| COSMA: Combined Scheduling, Memory Allocation and Tensor Replacement…【预】 | 2023 | arXiv 2311.18246 | 已核验 | 调度/分配/替换联合优化以最小化 off-chip 访存 |
| Rammer: Enabling Holistic DL Compiler Optimizations with rTasks【审】 | 2020 OSDI | USENIX PDF | 已核验 | rTask 静态时空调度；inter-/intra-operator 并行 |
| nncase: End-to-End Compiler for LLM Deployment on Heterogeneous Storage【预】 | 2025 | arXiv 2512.21571 | 已核验 | SAT 求解 buffer 复用；buffer schedule 两阶段 |
| ExecuTorch Compiler Memory Planning【技】 | 持续 | docs.pytorch.org | 已核验 | greedy-by-size lifetime 复用的工程现状 |

## 3. 静态放置 + 动态发射 / 任务级乱序硬件

| 文献 | 年份 / venue | 标识符 | 核验 | 与本轮的关系 |
|---|---|---|---|---|
| Nagarajan, Kushwaha, Burger, McKinley, Lin, Keckler, Static Placement, Dynamic Issue (SPDI) Scheduling for EDGE Architectures【审】 | 2004 PACT | UT Austin PDF | 已核验 | SPDI 执行模型与调度器需考虑 locality/contention/speculation |
| Burger 等，Scaling to the End of Silicon with EDGE Architectures【审】 | 2004 IEEE Computer | PDF | 已核验 | SPDI vs SPSI（VLIW）vs DPDI（超标量）的分类 |
| Smith 等，Compiling for EDGE Architectures【审】 | 2006 CGO | PDF | 已核验 | 编译器显式编码依赖、硬件不再动态发现 |
| Etsion 等，Task Superscalar: An Out-of-Order Task Pipeline【审】 | 2010 MICRO | DOI 10.1109/MICRO.2010.13 | 已核验 | 任务级乱序流水，硬件动态检测任务间依赖 |
| Kumar, Hughes, Nguyen, Carbon: Architectural Support for Fine-Grained Parallelism on CMPs【审】 | 2007 ISCA | — | 引用中核验（Task Superscalar 参考文献 + scispace 页） | 硬件任务队列与 work stealing |
| Tan 等，Picos: A Hardware Runtime Architecture Support for OmpSs【审】 | 2015 FGCS | ScienceDirect | 已核验（摘要页） | Task Superscalar 的硬件实现 |
| Dadu & Nowatzki, TaskStream: Accelerating Task-Parallel Workloads by Recovering Program Structure【审】 | 2022 ASPLOS | — | 引用中核验（UCLA 博士论文） | 空间加速器上的任务级动态调度框架 |
| Parashar 等，Triggered Instructions【审】 | 2013 ISCA | — | 引用中核验（UCLA 博士论文：PE 级乱序需 tag matching，面积 >3×） | PE 级数据触发执行的面积代价 |
| Abts 等，Think Fast: A Tensor Streaming Processor (TSP)【审】 | 2020 ISCA | DOI 10.1109/ISCA45697.2020.00023 | 已核验（ResearchGate 页） | 消灭所有 reactive 元件以获得确定性；本方向前提的反例 |
| Intel 专利 US6557095B1, Scheduling Operations Using a Dependency Matrix | 2003 | Google Patents | 已核验 | 依赖矩阵调度器的专利先例（硬件结构层面） |

## 4. 工业 NPU 的依赖驱动执行

| 文献 | 年份 / venue | 标识符 | 核验 | 与本轮的关系 |
|---|---|---|---|---|
| Moreau 等，A Hardware–Software Blueprint for Flexible Deep Learning Specialization（VTA）【预】 | 2018 | arXiv 1807.04188 | 已核验 | load/compute/store 三队列 + RAW/WAR 依赖 token；编译器（TVM virtual thread）生成 token；最直接的“编译器合同 + 硬件按依赖执行”先例 |
| VTA Hardware Guide【技】 | 持续 | tvm docs（onnxruntime-tvm 镜像） | 已核验 | 依赖队列语义与伪代码 |
| Intel Gaudi 3 AI Accelerator White Paper【技】 | 2024 | presidio/aspsys PDF | 已核验 | Sync Manager：等待计数事件、触发 MME/TPC/DMA；Graph Compiler 决定全部依赖与调度 |
| Kaplan, Intel Gaudi 3 (Hot Chips 2024)【技】 | 2024 | hc2024.hotchips.org PDF | 已核验 | SM 职责、MME–TPC 流水切片 |
| AscendNPU-IR Auto-Sync【技】 | 持续 | ascendnpu-ir.gitcode.com | 已核验 | set_flag/wait_flag、pipe barrier、event-ID 分配、冗余同步消除；每 pipe 顺序执行 |
| HyperParallel-MoE（Ascend）【预】 | 2026 | arXiv 2605.23764 | 已核验 | CTQ/VTQ 静态任务流 + 事件驱动同步；“所有依赖分析与顺序决策离线完成” |
| AMD WP552, AI Engine Adaptive Data Flow Programming【技】 | — | docs.amd.com | 已核验 | 编译器分配 lock/buffer/DMA descriptor；ping/pong lock |
| Xilinx mlir-aie ObjectFIFO（PR #3298、#2898、issue #3281）【技】 | 2025–2026 | GitHub | 已核验 | lock acquire/release 的静态 vs 动态 bookkeeping；buffer depth 作为静态重命名深度 |
| Tenstorrent Metalium / TT-Lang dataflow buffer【技】 | 2025–2026 | GitHub、tt-awesome、clehaxze.tw | 已核验 | circular buffer + 硬件 semaphore/mutex；Tensix Sync 单元 8 个 4-bit semaphore |
| Operator Fusion for LLM Inference on the Tensix Architecture【预】 | 2026 | arXiv 2606.09879 | 已核验 | reader/compute/writer 三 kernel 流水；token/fence 同步 |
| M100: An Orchestrated Dataflow Architecture Powering General AI Computing【预】 | 2026 | arXiv 2604.17862 | 已核验 | 每 PE 按派发顺序执行、跨 PE 乱序完成、软件管同步 |
| A Fully Hardware-Managed Scheduling Architecture for AI Accelerators【审】 | 2026 J. King Saud Univ. CIS | DOI 10.1007/s44443-026-00513-z | 已核验 | openNVDLA 上 OCSR + 32 项 ROB 乱序算子调度；28 nm 0.462 mm²、13 mW；30% 收益来自消除 CPU 调度开销；作者注明算子级并行有限 |

## 5. 方差与 DRAM 侧建模（门 B 的工具与背景）

| 文献 | 年份 / venue | 标识符 | 核验 | 与本轮的关系 |
|---|---|---|---|---|
| ONNXim: A Fast, Cycle-Level Multi-Core NPU Simulator【审】 | 2024 IEEE CAL | DOI 10.1109/LCA.2024.3484648；arXiv 2406.08051 | 已核验 | 计算确定、DRAM/NoC 周期级建模（Ramulator）；门 B 回放器的候选骨架 |
| MoCA: Memory-Centric, Adaptive Execution for Multi-Tenant DNNs【审】 | 2023 HPCA | DOI 10.1109/HPCA56546.2023.10071035 | 已核验 | 多租户下访存速率的硬件监控与节流 |
| SoMa: DRAM Communication Scheduling Space for DNN Accelerators【预】 | 2025 | arXiv 2501.12634 | 已核验 | 预取/延迟存储的时序调度空间；静态侧的对照 |

## 6. 沿用 round 1–3 登记、本轮未重复核验

PISA-DMA、DAE（Smith 1984）、Cambricon ISA、Diffy、Cambricon-D、Ditto、EXION、TeaCache、DiT-XL/2、FlashAttention、FuseMax、FLAT、Timeloop、CoSA、ZigZag。

## 7. 覆盖与局限

- 检索主题：调度分类与鲁棒调度理论、寄存器分配 ↔ 调度、DNN 编译器内存规划、SPDI/任务级乱序硬件、工业 NPU 同步机制、NPU 算子级硬件调度器、NPU 方差建模。
- 未连接：Google Scholar、IEEE Xplore 全文、专利数据库（仅 Google Patents 一条）；Semantic Scholar API 因 429 未用于批量核对；未做逐权利要求检索。
- 本轮新增 2025–2026 条目（M100、openNVDLA-2026 调度器、HyperParallel-MoE、Tensix fusion、mlir-aie 动态 ObjectFIFO）表明“编译器合同 + 硬件事件派发”是当前工业 NPU 的默认形态，且至少一篇 2026 年论文已在 NPU 上实现算子级乱序调度器。