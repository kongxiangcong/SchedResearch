# Step 3 — Abstract-Level Triage

日期：2026-09-05。状态：完成可取得摘要的初筛；无abstract条目标为未评分/待核验，0是保守临时值而非排除证明。所有API摘要原样保存在JSON。

- **Paper 1**
  - Title: HyperParallel-MoE: Multi-Core Interleaved Scheduling for Fast MoE Training on Ascend NPUs
  - Date: 2026-05-22
  - Problem framing: 异构NPU的MoE training overlap
  - Core mechanism: 静态tile taskflow与event queues
  - Key insight: 在compiler中暴露通信/compute依赖
  - Application domain: Ascend MoE训练
  - Overlap score: 2/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2605.23764v2；arxiv

- **Paper 2**
  - Title: Design of Dynamic Scheduling Algorithm for Parallel Data Processing in Multi-Core Chips
  - Date: 2025-05-16
  - Problem framing: multicore高负载调度
  - Core mechanism: priority+IMCT+adaptive resource allocation
  - Key insight: 综合紧迫度/资源/依赖
  - Application domain: PARSEC CPU任务
  - Overlap score: 1/4 （abstract初筛）
  - Source: https://www.semanticscholar.org/paper/e7cf30bd43deb8aec5ba762bbf4f8580176a13b7；semantic_scholar,crossref

- **Paper 3**
  - Title: Dynamic Loop Fusion in High-Level Synthesis
  - Date: 2025-01-24
  - Problem framing: irregular sibling loops依赖阻塞
  - Core mechanism: monotonic address分析+runtime disambiguation
  - Key insight: 利用compiler约束免除地址history搜索
  - Application domain: dynamic HLS
  - Overlap score: 2/4 （abstract初筛）
  - Source: https://www.semanticscholar.org/paper/a1ea5b916228bd88b391567eb2d57a5bf02dc6ff；semantic_scholar

- **Paper 4**
  - Title: Supporting Dynamic Control-Flow Execution for Runtime Reconfigurable Processors
  - Date: 2026-05-20
  - Problem framing: 可重构processor的microcode控制流
  - Core mechanism: 循环/条件跳转/异常支持
  - Key insight: 让runtime reconfiguration支持更广程序
  - Application domain: 可重构处理器
  - Overlap score: 1/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2605.21203v1；arxiv

- **Paper 5**
  - Title: TCL: Enabling Fast and Efficient Cross-Hardware Tensor Program Optimization via Continual Learning
  - Date: 2026-04-14
  - Problem framing: 跨hardware的tensor程序调优成本
  - Core mechanism: 采样+Mamba cost model+持续蒸馏
  - Key insight: 减少调优数据与跨平台迁移成本
  - Application domain: DL compiler
  - Overlap score: 1/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2604.12891v1；arxiv

- **Paper 6**
  - Title: FR-EAHTS: federated reinforcement learning for enhanced task scheduling with hierarchical load balancing and dynamic power adjustment in multi-core systems
  - Date: 2025-04-03
  - Problem framing: 待核验：multicore hierarchical调度
  - Core mechanism: 摘要未取得
  - Key insight: 待核验
  - Application domain: 多核调度
  - Overlap score: 0/4 （abstract缺失，临时值）
  - Source: https://www.semanticscholar.org/paper/98d9ddb8b4bdcbff97c1feea5fc12f57e8580f34；semantic_scholar

- **Paper 7**
  - Title: Energy efficient dynamic scheduling of dependent tasks for multi‐core real‐time systems using delay techniques
  - Date: 2024-10-02
  - Problem framing: dependent实时任务能源
  - Core mechanism: ASAP/ALAP mobility调度
  - Key insight: 时序slack支持能源优化
  - Application domain: multicore实时系统
  - Overlap score: 1/4 （abstract初筛）
  - Source: https://www.semanticscholar.org/paper/f049740aeeadc9a4e285bd2eb9d2067c5f1e5511；semantic_scholar

- **Paper 8**
  - Title: Dynamic Multi-Core Task Scheduling for Real-Time Hybrid Simulation Model in Power Grid: A Deep Reinforcement Learning-Based Method
  - Date: 2025-12-24
  - Problem framing: 电网仿真任务调度
  - Core mechanism: DRL与attention建模DAG
  - Key insight: 根据graph调任务优先级
  - Application domain: power-grid simulation
  - Overlap score: 1/4 （abstract初筛）
  - Source: https://www.semanticscholar.org/paper/c62346882ff331883f77cbac65ccae4c4885db30；semantic_scholar

- **Paper 9**
  - Title: Dynamic Thermal-Aware Scheduling Using Physics-Informed POD-Galerkin Thermal Simulation Model for Multi-Core Processors : Invited Paper
  - Date: 2024-11-02
  - Problem framing: CPU温度控制
  - Core mechanism: POD-Galerkin预测+dynamic TAS
  - Key insight: 降低热模型运行成本
  - Application domain: multicore热管理
  - Overlap score: 1/4 （abstract初筛）
  - Source: https://www.semanticscholar.org/paper/332883a6451a22113ad15f51bee5ebd0311cee97；semantic_scholar

- **Paper 10**
  - Title: WITHDRAWN: Non-work conserving dynamic scheduling of moldable gang tasks on multicore systems
  - Date: 2024-03-01
  - Problem framing: 不确定到达的moldable gang tasks
  - Core mechanism: 动态选择时间和核数
  - Key insight: non-work-conserving placement可改善makespan
  - Application domain: multicore实时任务；已撤回
  - Overlap score: 1/4 （abstract初筛）
  - Source: https://doi.org/10.1016/j.iotcps.2024.03.001；open_alex

- **Paper 11**
  - Title: SegFold: Accelerating Sparse GEMM with a Fine-Grained Dynamic Dataflow
  - Date: 2026-06-25
  - Problem framing: 稀疏GEMM的reuse/负载冲突
  - Core mechanism: 小窗口动态reuse、partial work remapping
  - Key insight: 静态dataflow错过runtime稀疏结构
  - Application domain: SpGEMM accelerator
  - Overlap score: 2/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2606.26701v1；arxiv

- **Paper 12**
  - Title: Dynamic Task Scheduling for Heterogeneous Multi-core Baseband Processors in IIoT
  - Date: 2026
  - Problem framing: 待核验：异构baseband任务
  - Core mechanism: 摘要未取得；不能仅凭标题认定机制
  - Key insight: 待核验
  - Application domain: IIoT baseband
  - Overlap score: 0/4 （abstract缺失，临时值）
  - Source: https://doi.org/10.1109/jiot.2026.3727005；crossref

- **Paper 13**
  - Title: An Algorithm-Hardware Co-Optimized Accelerator for Efficient Deep GCN Inference with Hybrid Dataflow and Dynamic Pruning
  - Date: 未知
  - Problem framing: 深GCN的计算与精度问题
  - Core mechanism: dynamic pruning+hybrid dataflow
  - Key insight: 提前节点收敛可减工作量
  - Application domain: GCN accelerator；不是固定DAG等价调度
  - Overlap score: 1/4 （abstract初筛）
  - Source: https://doi.org/10.2139/ssrn.6749762；crossref

- **Paper 14**
  - Title: InSS: An Intelligent Scheduling Orchestrator for Multi-GPU Inference With Spatio-Temporal Sharing
  - Date: 2024-07-18
  - Problem framing: multiGPU online inference干扰与SLO
  - Core mechanism: latency model+placement/resource/batch优化
  - Key insight: 显式估计共置干扰
  - Application domain: GPU serving
  - Overlap score: 1/4 （abstract初筛）
  - Source: https://doi.org/10.1109/tpds.2024.3430063；open_alex

- **Paper 15**
  - Title: Partitioned Scheduling and Parallelism Assignment for Real-Time DNN Inference Tasks on Multi-TPU
  - Date: 2024-06-23
  - Problem framing: multiTPU实时gang inference可调度性
  - Core mechanism: 固定partition与统一parallelism level
  - Key insight: 严格分区避免scheduling anomalies
  - Application domain: Edge TPU实时推理
  - Overlap score: 1/4 （abstract初筛）
  - Source: https://doi.org/10.1145/3649329.3655979；open_alex

- **Paper 16**
  - Title: MTST: A Multi-Task Scheduling Transformer Accelerator for Edge Computing
  - Date: 2024-10-29
  - Problem framing: 待核验：边缘transformer多任务
  - Core mechanism: 摘要未取得，保留后续候选
  - Key insight: 待核验
  - Application domain: edge transformer accelerator
  - Overlap score: 0/4 （abstract缺失，临时值）
  - Source: https://doi.org/10.1109/gcce62371.2024.10760930；crossref

- **Paper 17**
  - Title: MHRC-Bench: A Multilingual Hardware Repository-Level Code Completion benchmark
  - Date: 2026-01-07
  - Problem framing: 硬件repository代码补全评测
  - Core mechanism: benchmark与标签
  - Key insight: 补齐HDL评测缺口
  - Application domain: LLM代码生成；不相关
  - Overlap score: 0/4 （abstract初筛）
  - Source: https://doi.org/10.48550/arxiv.2601.03708；open_alex

- **Paper 18**
  - Title: Tawa: Automatic Warp Specialization for Modern GPUs with Asynchronous References
  - Date: 2025-10-16
  - Problem framing: GPU异构单元编程与流水开销
  - Core mechanism: aref+自动warp specialization
  - Key insight: 高层异步引用隐藏producer-consumer同步细节
  - Application domain: LLM GPU kernels
  - Overlap score: 2/4 （abstract初筛）
  - Source: https://doi.org/10.48550/arxiv.2510.14719；open_alex

- **Paper 19**
  - Title: From Principles to Practice: A Systematic Study of LLM Serving on Multi-core NPUs
  - Date: 2025-10-07
  - Problem framing: multi-core NPU LLM利用率
  - Core mechanism: simulation+TP/core placement/PD优化
  - Key insight: 架构与serving策略协同
  - Application domain: LLM多核NPU
  - Overlap score: 2/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2510.05632v1；arxiv

- **Paper 20**
  - Title: DFTS-MCS: Dynamic Fault-tolerant Scheduling for Mixed-criticality Systems on Heterogeneous Multi-core Processors
  - Date: 2026-06
  - Problem framing: 待核验：mixed-criticality fault tolerance
  - Core mechanism: 摘要未取得
  - Key insight: 待核验
  - Application domain: 实时multicore
  - Overlap score: 0/4 （abstract缺失，临时值）
  - Source: https://doi.org/10.2139/ssrn.5625286；crossref

- **Paper 21**
  - Title: NektarIR: A Domain-Specific Compiler for High-Order Finite Element Operations on Heterogeneous Hardware
  - Date: 未知
  - Problem framing: 异构HPC代码生成
  - Core mechanism: domain IR到MLIR/LLVM
  - Key insight: 从领域操作生成不同hardware代码
  - Application domain: 有限元CFD；非NPU任务调度
  - Overlap score: 0/4 （abstract初筛）
  - Source: https://doi.org/10.52843/cassyni.qrrjjy.3；crossref

- **Paper 22**
  - Title: ADS-CNN: Adaptive Dataflow Scheduling for lightweight CNN accelerator on FPGAs
  - Date: 2024-09
  - Problem framing: 待核验：CNN dataflow调度
  - Core mechanism: 摘要未取得
  - Key insight: 待核验；不能把adaptive dataflow等同runtime OoO
  - Application domain: FPGA CNN
  - Overlap score: 0/4 （abstract缺失，临时值）
  - Source: https://doi.org/10.1016/j.future.2024.04.038；crossref

- **Paper 23**
  - Title: Slark: A Performance Robust Decentralized Inter-Datacenter Deadline-Aware Coflows Scheduling Framework With Local Information
  - Date: 2024-11-28
  - Problem framing: 跨数据中心coflow信息受限
  - Core mechanism: 分布式agent与局部信息robust optimization
  - Key insight: 局部状态可减全局协调
  - Application domain: coflow网络调度
  - Overlap score: 1/4 （abstract初筛）
  - Source: https://doi.org/10.1109/tpds.2024.3508275；open_alex

- **Paper 24**
  - Title: DMDP: A Dynamic Multi-Delta Prefetcher with Customizable Runtime Quality-Aware Feedback
  - Date: 未知
  - Problem framing: prefetch预测覆盖与质量
  - Core mechanism: 多delta模式+runtime质量反馈
  - Key insight: 根据准确度及时性和污染调节预取
  - Application domain: CPU预取；非task DAG
  - Overlap score: 1/4 （abstract初筛）
  - Source: https://doi.org/10.21203/rs.3.rs-3853411/v1；crossref

- **Paper 25**
  - Title: Predictive Age-Aware Runtime Remapping for Many-Core Systems
  - Date: 2024-11-20
  - Problem framing: manycore热/traffic不平衡导致aging
  - Core mechanism: runtime任务remapping
  - Key insight: 平衡核心与通信使用
  - Application domain: manycore可靠性
  - Overlap score: 1/4 （abstract初筛）
  - Source: https://doi.org/10.1109/icsrs63046.2024.10927459；open_alex

- **Paper 26**
  - Title: Dynamic Tuning of Core Counts to Maximize Performance in Object-Based Runtime Systems
  - Date: 2024-01-01
  - Problem framing: 待核验：object runtime core count
  - Core mechanism: 摘要未取得
  - Key insight: 待核验
  - Application domain: object-based runtime
  - Overlap score: 0/4 （abstract缺失，临时值）
  - Source: https://doi.org/10.1007/978-3-031-61763-8_9；open_alex

- **Paper 27**
  - Title: FusionFrame: A Fusion Dataflow Scheduling Framework for DNN Accelerators via Analytical Modeling
  - Date: 2025-01-01
  - Problem framing: 待核验：DNN融合dataflow
  - Core mechanism: 摘要未取得
  - Key insight: 待核验
  - Application domain: DNN compiler
  - Overlap score: 0/4 （abstract缺失，临时值）
  - Source: https://doi.org/10.1007/978-981-96-1551-3_21；open_alex

- **Paper 28**
  - Title: Neural Channel Knowledge Map Assisted Scheduling Optimization of Active IRSs in Multi-User Systems
  - Date: 2025-08-09
  - Problem framing: 无线多用户channel状态与调度
  - Core mechanism: neural CKM+stable matching
  - Key insight: 以历史信道预测减少开销
  - Application domain: 无线通信；非NPU执行
  - Overlap score: 0/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2508.07009v1；arxiv

- **Paper 29**
  - Title: Multilayer Dataflow: Orchestrate Butterfly Sparsity to Accelerate Attention Computation
  - Date: 2024-11-01
  - Problem framing: butterfly sparse attention访问不规则
  - Core mechanism: 混合稀疏network+streaming dataflow
  - Key insight: 数据复用与structured sparsity协同
  - Application domain: attention accelerator
  - Overlap score: 1/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2411.00734v2；arxiv

- **Paper 30**
  - Title: Generation of Compiler Backends from Formal Models of Hardware
  - Date: 2024-08-27
  - Problem framing: compiler backend开发与正确性
  - Core mechanism: 形式hardware模型+自动推理
  - Key insight: 从hardware语义自动生成backend
  - Application domain: 博士论文/FPGA编译
  - Overlap score: 1/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2408.15429v1；arxiv

- **Paper 31**
  - Title: TT-QEC: An Open-Source Hardware-Native MLIR Compiler for Quantum Error Correction Decoding
  - Date: 未知
  - Problem framing: 量子纠错低延迟
  - Core mechanism: MLIR/Tensix kernel+抽象验证
  - Key insight: host-free驻留执行
  - Application domain: 量子纠错；Blackhole结果为预测未实测
  - Overlap score: 1/4 （abstract初筛）
  - Source: https://doi.org/10.2139/ssrn.6905503；crossref

- **Paper 32**
  - Title: Differential Testing Solidity Compiler through Deep Contract Manipulation and Mutation
  - Date: 未知
  - Problem framing: Solidity compiler测试
  - Core mechanism: Transformer contract生成+差分测试
  - Key insight: 自动制造compiler缺陷输入
  - Application domain: 区块链；不相关
  - Overlap score: 0/4 （abstract初筛）
  - Source: https://doi.org/10.21203/rs.3.rs-3924118/v1；crossref

- **Paper 33**
  - Title: Service Dependency Intelligence for Contract-aware Agent Design in Enterprise Microservice Architectures
  - Date: 未知
  - Problem framing: 企业service接口依赖
  - Core mechanism: 静态repository扫描graph
  - Key insight: 减少agent改动引发的API不一致
  - Application domain: 微服务软件；不相关
  - Overlap score: 0/4 （abstract初筛）
  - Source: https://doi.org/10.2139/ssrn.6963023；crossref

- **Paper 34**
  - Title: ONNXim: A Fast, Cycle-Level Multi-Core NPU Simulator
  - Date: 2024-07-01
  - Problem framing: 多核NPU模拟速度/保真
  - Core mechanism: 确定compute+cycle DRAM/NoC
  - Key insight: 保留争用而抽象规则计算
  - Application domain: NPU simulator
  - Overlap score: 2/4 （abstract初筛）
  - Source: https://doi.org/10.1109/lca.2024.3484648；open_alex,arxiv

- **Paper 35**
  - Title: Icarus: Trustworthy Just-In-Time Compilers with Symbolic Meta-Execution
  - Date: 2024-11-04
  - Problem framing: JIT实现安全
  - Core mechanism: symbolic meta-execution
  - Key insight: 静态验证JIT生成程序集合
  - Application domain: JavaScript JIT；非调度
  - Overlap score: 0/4 （abstract初筛）
  - Source: https://doi.org/10.1145/3694715.3695949；open_alex

- **Paper 36**
  - Title: Survival of the Fastest: Enabling More Out-of-Order Execution in Dataflow Circuits
  - Date: 2024-04-01
  - Problem framing: dataflow相同op实例HOL
  - Core mechanism: 扩展同op多实例OoO
  - Key insight: 跨操作OoO不等于跨实例OoO
  - Application domain: dynamic HLS
  - Overlap score: 2/4 （abstract初筛）
  - Source: https://doi.org/10.1145/3626202.3637556；open_alex

- **Paper 37**
  - Title: Seal5: Semi-Automated LLVM Support for RISC-V ISA Extensions Including Autovectorization
  - Date: 2024-08-28
  - Problem framing: RISC-V扩展compiler生成
  - Core mechanism: ISA模型到LLVM patterns
  - Key insight: 减少工具链维护
  - Application domain: ISA/compiler工具
  - Overlap score: 0/4 （abstract初筛）
  - Source: https://doi.org/10.1109/dsd64264.2024.00052；open_alex

- **Paper 38**
  - Title: Towards Scheduling of Pipelined Dataflow Graphs in MLIR
  - Date: 2026-02-05
  - Problem framing: CPU-FPGA NN流水与循环graph
  - Core mechanism: MLIR dataflow dialect+token scheduler
  - Key insight: macro-dataflow跨外存流水
  - Application domain: CPU-FPGA SoC
  - Overlap score: 2/4 （abstract初筛）
  - Source: https://doi.org/10.1145/3748173.3779568；open_alex

- **Paper 39**
  - Title: Hiring for An Uncertain Task: Joint Design of Information and Contracts
  - Date: 2024-07-07
  - Problem framing: economic contracts信息设计
  - Core mechanism: 优化激励合约算法
  - Key insight: 合约表达能力与求解复杂性
  - Application domain: 机制设计；不相关
  - Overlap score: 0/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2407.05459v1；arxiv

- **Paper 40**
  - Title: Finding Missed Code Size Optimizations in Compilers using LLMs
  - Date: 2024-12-31
  - Problem framing: compiler missed optimization
  - Core mechanism: LLM输入生成+差分测试
  - Key insight: 简化编译器测试
  - Application domain: C/C++/Rust/Swift compiler；不相关
  - Overlap score: 0/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2501.00655v1；arxiv

- **Paper 41**
  - Title: LLM4SecHW: Leveraging Domain Specific Large Language Model for Hardware Debugging
  - Date: 2024-01-28
  - Problem framing: hardware debugging
  - Core mechanism: 领域LLM
  - Key insight: 自动debug知识
  - Application domain: 硬件安全；非任务调度
  - Overlap score: 0/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2401.16448v1；arxiv

- **Paper 42**
  - Title: Dataflow-Reconfigurable CNN Accelerator Design
  - Date: 2026-05
  - Problem framing: 待核验：CNN dataflow可重配
  - Core mechanism: 摘要未取得
  - Key insight: 待核验
  - Application domain: CNN accelerator
  - Overlap score: 0/4 （abstract缺失，临时值）
  - Source: https://doi.org/10.1109/mm.2026.3671071；crossref

- **Paper 43**
  - Title: Feature-Stationary Dataflow Enabled Diffusion Transformer Accelerator
  - Date: 2025-09-12
  - Problem framing: 待核验：DiT data reuse
  - Core mechanism: 摘要未取得
  - Key insight: 不能凭题名认定runtime机制
  - Application domain: DiT accelerator
  - Overlap score: 0/4 （abstract缺失，临时值）
  - Source: https://doi.org/10.1109/iccvdm66874.2025.11290078；crossref

- **Paper 44**
  - Title: Applications of Particle Accelerators
  - Date: 2024-07-14
  - Problem framing: 粒子加速器应用
  - Core mechanism: 非计算体系结构
  - Key insight: 不相关
  - Application domain: 物理加速器
  - Overlap score: 0/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2407.10216v1；arxiv

- **Paper 45**
  - Title: Accelerator Complex Evolution at Fermilab
  - Date: 2026-06-23
  - Problem framing: Fermilab设施改造
  - Core mechanism: 非计算体系结构
  - Key insight: 不相关
  - Application domain: 粒子物理
  - Overlap score: 0/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2606.25159v1；arxiv

- **Paper 46**
  - Title: Consideration of REBCO rapid-cycling diploe magnet for staged muon acceleration
  - Date: 2025-09-17
  - Problem framing: muon磁体设计
  - Core mechanism: 非计算体系结构
  - Key insight: 不相关
  - Application domain: 粒子物理
  - Overlap score: 0/4 （abstract初筛）
  - Source: http://arxiv.org/abs/2509.14410v1；arxiv

- **Paper 47**
  - Title: Completion of the works
  - Date: 2024-01-01
  - Problem framing: 建筑合同条款
  - Core mechanism: 非计算体系结构
  - Key insight: 不相关
  - Application domain: 合同管理
  - Overlap score: 0/4 （abstract缺失，临时值）
  - Source: https://doi.org/10.1680/fcmh.66526.135；crossref

## 定向web / model-recall补充

7个正文候选的全部字段、机制与scope见以下正文记录（此段按同一4轴计分，不自动优待model recall）。

## Comparison result

- **Proposed work**
  - Title: Minimum Necessary Dynamic Hardware（研究目标，未定论文题目）
  - Date: 2026-09-05
  - Source: 本目录 R3 的待验证假设
  - Problem framing: 已知 DAG 和静态分配下的剩余 runtime latency uncertainty。
  - Core mechanism: 显式 contract 与有限状态 completion-driven ready dispatch。
  - Key insight: compiler 消除能离线解决的决策，hardware 只处理实时信息。
  - Application domain: edge LLM/DiT，多核到多 chip NPU。

- **SPDI / EDGE**
  - Title: Static Placement, Dynamic Issue (SPDI) Scheduling for EDGE Architectures
  - Date: 2004
  - Source: [作者全文](https://www.cs.utexas.edu/~lin/papers/pact04.pdf)
  - Problem framing: 多 ALU 与非均匀片上延迟，compiler placement 与 runtime issue 协同；partial match。
  - Core mechanism: ISA 显式消费者位置，输入到达后 issue；match。
  - Key insight: 分离 placement/issue，避免全动态 placement 与集中关联搜索的成本；match。
  - Application domain: SPEC2000、TRIPS 指令/block；differ。
  - Assumptions & scope: §2 有 block dataflow 与 cache misses，不能直接搬用边缘 NPU task 成本。
  - Closest-passage evidence: §1 的 direct instruction communication；§2 的 independent operations on same unit；§4 SPEC2000 评估。
  - Refined overlap: 两轴 match、framing partial；**Level 3 — Medium Overlap**。

- **VTA**
  - Title: A Hardware–Software Blueprint for Flexible Deep Learning Specialization
  - Date: 2018 预印本 / 2019 IEEE Micro 版本
  - Source: [arXiv 原文](https://arxiv.org/abs/1807.04188)
  - Problem framing: flexible DNN accelerator 与 compute/memory overlap；partial。
  - Core mechanism: command queues + RAW/WAR dependency queues，编译 virtual threads；partial，非任意 task ready-set。
  - Key insight: 编译依赖位支持低成本 access-execute decoupling；match。
  - Application domain: edge DNN acceleration；match（本轮 LLM/DiT 是较窄子域）。
  - Assumptions & scope: §3.1 的 load/compute/store，§4 调优，§5 FPGA CNN。
  - Closest-passage evidence: §3.1 Architecture Overview、Exposing Task-Level Pipeline Parallelism、§5 Evaluation。
  - Refined overlap: 两轴 match、两轴 partial；**Level 3 — Medium Overlap**。若主张退化成“有同步合同即新”，则与 VTA 的重合更高。

- **TaskStream**
  - Title: TaskStream: Accelerating Task-Parallel Workloads by Recovering Program Structure
  - Date: 2022-02，ASPLOS 2022
  - Source: [全文](https://par.nsf.gov/servlets/purl/10320225)
  - Problem framing: irregular tasks 使空间架构失去结构/reuse，恢复负载平衡与流水；partial。
  - Core mechanism: task-edge annotations、legal coreMask、sizehint、有限 task/stream tables、NoC；match 于宽泛协同机制。
  - Key insight: 少量先验结构允许低开销 runtime 恢复并行和复用；match。
  - Application domain: CGRA、多核 irregular workloads；partial，非 edge dense LLM/DiT。
  - Assumptions & scope: §3.4 的高层自动编译器未实现；§5 的 DSAGEN/gem5 与 28nm 合成，不应把其面积百分比移植。
  - Closest-passage evidence: §2.2 coreMask/sizehint/typed edges；§3.1 hierarchical composition；§3.4/§5 scope。
  - Refined overlap: 两轴 match、两轴 partial；**Level 3 — Medium Overlap**。

- **ASPEN**
  - Title: ASPEN: Breaking Operator Barriers for Efficient Parallelization of Deep Neural Networks
  - Date: 2023，NeurIPS 2023
  - Source: [会议全文](https://proceedings.neurips.cc/paper_files/paper/2023/file/d899a31938c7838965b589d9b14a5ca6-Paper-Conference.pdf)
  - Problem framing: operator barriers 遮住 tile-level 并行、快慢资源利用不充分；partial。
  - Core mechanism: offline tile DAG、每 node parent count、完成时 atomic increment、distributed traversal 和 Ready Pool；match 于算法。
  - Key insight: graph reasoning 离线化，执行完成局部唤醒，异步分布共享 ready work；match。
  - Application domain: DNN CPU inference prototype；partial。
  - Assumptions & scope: §3.1 调 tile 粒度以减 scheduling overhead；§3.3 work stealing、priority queue；没有 NPU bank/epoch/credit 成本证明。
  - Closest-passage evidence: §3.1 graph file；§3.2 Algorithm 1；§3.3/§4 Ready Pool 与 CPU evaluation。
  - Refined overlap: 两轴 match、两轴 partial；**Level 3 — Medium Overlap**。

- **PipeThreader**
  - Title: PipeThreader: Software-Defined Pipelining for Efficient DNN Execution
  - Date: 2025-07，OSDI 2025
  - Source: [会议页与全文](https://www.usenix.org/conference/osdi25/presentation/cheng)
  - Problem framing: GPU 异构单元之间的 pipeline 机会被高层抽象隐藏；partial。
  - Core mechanism: compiler 搜索 sProg[sEU][order]、barrier task；differ，固定顺序不是 ready-set 动态重排。
  - Key insight: 让 compiler 知道真实异构 engine，比依赖隐式硬件调度更充分；match 于合理边界。
  - Application domain: DNN/attention 等 GPU kernels；partial。
  - Assumptions & scope: §3.2 精确表示 per-sEU order；正文明确不替代 thread/warp dispatch；跨 GPU 扩展有通信 sEU。
  - Closest-passage evidence: §2 的 scope；§3.1 specialized units；§3.2 sProgram 与 barrier references。
  - Refined overlap: 一轴 match、两轴 partial；**Level 4 — Low Overlap**（机制 novelty）；但对 performance baseline 的威胁极高。

- **HwSch/openNVDLA**
  - Title: A fully hardware-managed scheduling architecture for AI accelerators
  - Date: 2026，Journal of King Saud University Computer and Information Sciences
  - Source: [出版方全文](https://link.springer.com/article/10.1007/s44443-026-00513-z)
  - Problem framing: host-side per-operator scheduling overhead；partial，论文动机也涉及 varying completion。
  - Core mechanism: compiler OCSR allocation/dependency encoding，opcode 指定 engine，source-ready/target-idle/ROB-free 时派发；match。
  - Key insight: offline graph analysis 后硬件直接消费 scheduling instructions；match。
  - Application domain: edge AI accelerator；match，实测为 CNN。
  - Assumptions & scope: §3.3 32 ROB；§4.3 明确 tested networks 的 parallel issue 收益有限；缺少强静态硬件队列对照。
  - Closest-passage evidence: §3.1.2 batch instruction workflow；§3.2 OCSR source/destination；§4.3 CNN attribution。
  - Refined overlap: 三轴 match、一轴 partial；**Level 2 — High Overlap**。

- **LATTICE**
  - Title: LATTICE: Constraint-Directed Scheduling, Memory Planning, and Pipeline Refinement for NPUs
  - Date: 2026-08-04 v3；旧索引名称 DAN-Scheduler
  - Source: [当前 arXiv 正文](https://arxiv.org/html/2607.17422)
  - Problem framing: scheduling 改 lifetime，memory plan 反过来约束合法时序；match 于 R2 子方向，partial 于 runtime uncertainty 主线。
  - Core mechanism: Pmem=(layout, events, reuse edges)，Efixed=precedence+spill+reuse，静态 CPE 改 resource order；partial。
  - Key insight: memory plan 必须成为可验证执行合同而非只交付 offset；match。
  - Application domain: general-purpose NPU lowered command DAG；match。
  - Assumptions & scope: §V 是静态单核 command replay，未编码源模型 shape/SKU/compiler version；四 baseline 政策重实现；没有真实 runtime 方差。
  - Closest-passage evidence: §III-B Eq.8；§III-C Eq.10–11；§IV-D CPE；§V-B evaluation scope。
  - Refined overlap: 两轴 match、两轴 partial；**Level 3 — Medium Overlap** 于当前 runtime 主张。对 R2 的“新 memory contract”表述为高度乃至完整机制重合。

