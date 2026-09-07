# 2024–2026 最新邻域

核验：2026-09-05。用首发时间与当前版本分别登记；网页 crawl 日期不是论文发表日期。数字均是作者所报，不是本地复现。正文深度分为 D（方法/范围已读）、A（摘要已读）、M（官方题录/目录已核验）；不使用“搜不到”证明新颖。

| 工作 | 版本/年份与深度 | 已支持的结论 | 对本研究的要求 |
|---|---|---|---|
| [LATTICE: Constraint-Directed Scheduling, Memory Planning, and Pipeline Refinement for NPUs](https://arxiv.org/abs/2607.17422) | v1 2026-07-19 原名 DAN-Scheduler；v3 2026-08-04 改名 LATTICE；预印本 D | §III 把地址、spill events、reuse edges 组成 memory-plan contract；§IV-D 在其约束内优化资源顺序；§V 是静态单核 replay | R2 推荐的 memory-reuse/partial-order contract 不能再宽泛声称新颖；重点差异必须是剩余不确定性和实际硬件状态成本 |
| [PipeThreader: Software-Defined Pipelining for Efficient DNN Execution](https://www.usenix.org/conference/osdi25/presentation/cheng) | OSDI 2025 D | §3 的 sTask/sEU 与二维 sProgram 明确绑定任务到异构单元与顺序，以 barrier task 保持依赖 | MXU/VPU/DMA overlap 很可能已可静态编译；不能以未流水基线论证动态 |
| [TileLink: Generating Efficient Compute-Communication Overlapping Kernels using Tile-Centric Primitives](https://arxiv.org/html/2503.20313) | 2025 预印本 D（§3–4、§7） | notify/wait 带 release/acquire；shape/rank/channel mapping；MoE 动态 mapping 用 runtime-filled lookup tables | 跨芯片 completion 必须表示可见性；通信编译契约、动态表实例化已有先例 |
| [Linear Layouts: Robust Code Generation of Efficient Tensor Computation Using F2](https://arxiv.org/html/2505.23819) | 首发 2025，当前版本 2026；D（§3–4） | 用二进制矩阵统一 Triton tensor/resource layouts 与转换 | 有助 WHERE/address/bank 表达；不能替代 WHEN、epoch、memory visibility 或资源所有权 |
| [Tawa: Automatic Warp Specialization for Modern GPUs with Asynchronous References](https://arxiv.org/html/2510.14719) | 2025 v2 D（摘要、目录、§III） | asynchronous references 抽象 producer-consumer 通信，编译自动 partition/pipeline | “编译器输出异步依赖”已是强编译器方向；需对照而非把收益归因到新硬件 |
| [A fully hardware-managed scheduling architecture for AI accelerators](https://link.springer.com/article/10.1007/s44443-026-00513-z) | 2026 JKSU CIS D | OCSR 显式编码依赖、opcode 对应 engine、32 ROB、按 completion 派发；CNN 实验主要消除 CPU 调度开销 | 最近任务级 NPU 硬件先例。论文未分离出 strong-static-ready baseline 上的 OoO 增益 |
| [HyperParallel-MoE](https://arxiv.org/html/2605.23764) | 2026 预印本 D（调度模型） | 多核 interleaving、静态 task queues、跨 Cube/Vector 事件同步 | 真实 NPU MoE pipeline 参考；training/大系统收益不能外推端侧 inference |
| [From Principles to Practice: A Systematic Study of LLM Serving on Multi-core NPUs](https://arxiv.org/html/2510.05632) | 2025 预印本 A/部分正文 | NPU LLM serving、算子内并行与调度的系统研究 | 是 workload/分解线索，不是已经完成硬件 OoO 的证据 |
| [SegFold: Accelerating Sparse GEMM with a Fine-Grained Dynamic Dataflow](https://arxiv.org/abs/2606.26701) | ISCA 2026（作者 arXiv comments 标明 accepted），A | 小窗口动态寻找 reuse、work assignment 和 partial work remapping；面向 SpGEMM | sparse workload 的动态 reuse/load balance已有强架构邻域；稀疏数据依赖不能偷换成 dense latency uncertainty |
| [Survival of the Fastest: Enabling More Out-of-Order Execution in Dataflow Circuits](https://github.com/EPFL-LAP/fpga24-more-ooo) | FPGA 2024 A+作者代码说明 | 区分不同 operation 的乱序和同一 operation 多实例的重排 | “dataflow 已经 OoO 所以没有更多自由度”错误；buffer/tag/ordering 代价需要单列 |
| [CRUSH: A Credit-Based Approach for Functional Unit Sharing in Dynamically Scheduled HLS](https://doi.org/10.1145/3669940.3707273) | ASPLOS 2025 M | 已核验题名与 credit-based FU sharing 的研究范围 | credit/backpressure 不是新概念；正文 PDF 链接本轮 404，具体算法不作确认 |
| [Mosaic: Exploiting Instruction-Level Parallelism on Deep Learning Accelerators with iTex Tessellation](https://doi.org/10.1145/3676641.3716262) | ASPLOS 2025 M | 官方会议目录确认该 DLA instruction-level parallelism 工作 | 是 core 内粒度方向必须继续全文读取的阻断条目；不依据题目猜 OoO 结构 |
| [AccelFlow: Orchestrating an On-Package Ensemble of Fine-Grained Accelerators for Microservices](https://experts.illinois.edu/en/publications/accelflow-orchestrating-an-on-package-ensemble-of-fine-grained-ac/) | HPCA 2026 A+作者 slides | CPU 构造 traces；accelerators 执行 trace 和 branch，减少 CPU 往返 | completion routing/heterogeneous orchestration 有先例；其 microservice 场景与 NPU 静态 DAG 区分 |
| [TEMP: A Memory Efficient Physical-aware Tensor Partition-Mapping Framework on Wafer-scale Chips](https://arxiv.org/abs/2512.14256) | 2025 preprint / HPCA2026目录 M/A | tensor partition/mapping 需考虑物理拓扑与通信冲突 | static-global mapping 本身应 topology-aware；不能给 dynamic 独享拓扑信息 |
| [ONNXim](https://arxiv.org/abs/2406.08051) | 2024 IEEE CAL M/A | 多核 NPU 周期级仿真工具 | 支持后续验证 memory/NoC uncertainty；本轮选型详见框架调研 |
| [SoMa: DRAM Communication Scheduling Space for DNN Accelerators](https://arxiv.org/abs/2501.12634) | 2025 预印本，继承 R2 尚未正文重读 | 静态 DRAM communication schedule 邻域 | DMA 预取/延迟 store 是强静态的一部分 |

HPCA 2026 [官方目录](https://2026.hpca-conf.org/program/program-hpca-2026/Detailed-Timeline) 还列出 ReThermal（静/动态 thermal scheduling）、LRM-GPU（multi-chiplet synchronization）、SFD（spatial accelerator segment fusion）、FACE（PD overlapping）。本轮只确认其存在与标题，不将目录代替方法审计，也不将这些“可能相关”条目塞进已确认 novelty 比较。

## ASPEN 与 DASO 的名称核验

[ASPEN](https://papers.neurips.cc/paper_files/paper/2023/hash/d899a31938c7838965b589d9b14a5ca6-Abstract-Conference.html) 实际是 **NeurIPS 2023**，是必须追溯的近邻：离线 tile DAG，运行时 distributed scheduling engine + Ready Pool；本轮下载正文并读 §3–5。其 CPU proof-of-concept 不等于 NPU 硬件已实现，但算法原理明显重合。

本轮对 `DASO accelerator scheduling`、`DASO NPU`、`DASO dynamic inference` 的检索，没有核验到同名 NPU 调度架构。可确认的 [DASO 2021](https://arxiv.org/abs/2104.05588) 是 distributed asynchronous and selective optimization，改动多 GPU training 的梯度同步频率。不能把改变训练更新语义的异步优化，作为保持精确 inference semantics 的 OoO 先例；也不能宣称同名 NPU 工作不存在。

## 最直接的两项更新

1. LATTICE v3 §V 明确 abstract 掉 dynamic arrivals、continuous batching、sub-buffer access phases 和 multi-core compilation；这是范围边界，**不是**“别人没做所以我们有论文”的证明。其四外部基线均在共同 replay backend 重实现政策，作者明确不是 vendor stacks，引用结果时必须保留限定。
2. openNVDLA 2026 正文 Table 6 列 scheduler **15 mW**，而 R2 写 13 mW。表同时列 741 mW 与 1.75%，数值比例本身不一致（15/741≈2.02%）；只可信地记录“作者 table 列这些数值，存在内在不一致”。0.462 mm² 是该 28nm 合成设计，不是本研究 scoreboarding 的面积估计。其论文主要收益来自 host launch/interrupt，不能据此推导 runtime latency tolerance 有 30%。
