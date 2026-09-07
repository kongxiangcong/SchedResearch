# Step 2 — Search and Deduplicate

日期：2026-09-05。状态：完成当前限定scope；未取得全文的候选保留限制。

# 全量学术检索报告

日期：2026-09-05。包含全部返回项，未因低相关度、撤回或缺字段而隐藏条目；索引元数据未经全部逐项核验，不能当作可靠书目。
## Display ALL results

首次CLI运行：arxiv=15, dblp=0, open_alex=15, openreview=0, semantic_scholar=0, crossref=15；42 unique，3 cross-source duplicates。原始rank完整保存在 [stdout](sources/paper_search_2024_2026.stdout.txt)。
随后为了保存摘要结构化重跑相同3 queries/6 sources：arxiv=15, dblp=0, open_alex=15, openreview=0, semantic_scholar=6, crossref=15；47 unique，4 duplicates；无 min-score 过滤。本表严格保持这次脚本的rank顺序。两次API结果不同是网络可用性变化，不能将新增条目误报为时间趋势。

| # | Title | Date | Venue | Citations | Score | Sources |
|---|---|---|---|---|---|---|
| [1](http://arxiv.org/abs/2605.23764v2) | HyperParallel-MoE: Multi-Core Interleaved Scheduling for Fast MoE Training on Ascend NPUs | 2026-05-22 | arXiv | 0 | 8 | arxiv |
| [2](https://www.semanticscholar.org/paper/e7cf30bd43deb8aec5ba762bbf4f8580176a13b7) | Design of Dynamic Scheduling Algorithm for Parallel Data Processing in Multi-Core Chips | 2025-05-16 | 2025 2nd International Conference on Intelligent Computing and Robotics (ICICR) | 0 | 7 | semantic_scholar,crossref |
| [3](https://www.semanticscholar.org/paper/a1ea5b916228bd88b391567eb2d57a5bf02dc6ff) | Dynamic Loop Fusion in High-Level Synthesis | 2025-01-24 | Symposium on Field Programmable Gate Arrays | 1 | 6 | semantic_scholar |
| [4](http://arxiv.org/abs/2605.21203v1) | Supporting Dynamic Control-Flow Execution for Runtime Reconfigurable Processors | 2026-05-20 | arXiv | 0 | 6 | arxiv |
| [5](http://arxiv.org/abs/2604.12891v1) | TCL: Enabling Fast and Efficient Cross-Hardware Tensor Program Optimization via Continual Learning | 2026-04-14 | arXiv | 0 | 6 | arxiv |
| [6](https://www.semanticscholar.org/paper/98d9ddb8b4bdcbff97c1feea5fc12f57e8580f34) | FR-EAHTS: federated reinforcement learning for enhanced task scheduling with hierarchical load balancing and dynamic power adjustment in multi-core systems | 2025-04-03 | Telecommunications Systems | 6 | 5 | semantic_scholar |
| [7](https://www.semanticscholar.org/paper/f049740aeeadc9a4e285bd2eb9d2067c5f1e5511) | Energy efficient dynamic scheduling of dependent tasks for multi‐core real‐time systems using delay techniques | 2024-10-02 | Concurrency and Computation | 1 | 5 | semantic_scholar |
| [8](https://www.semanticscholar.org/paper/c62346882ff331883f77cbac65ccae4c4885db30) | Dynamic Multi-Core Task Scheduling for Real-Time Hybrid Simulation Model in Power Grid: A Deep Reinforcement Learning-Based Method | 2025-12-24 | Applied Sciences | 0 | 5 | semantic_scholar |
| [9](https://www.semanticscholar.org/paper/332883a6451a22113ad15f51bee5ebd0311cee97) | Dynamic Thermal-Aware Scheduling Using Physics-Informed POD-Galerkin Thermal Simulation Model for Multi-Core Processors : Invited Paper | 2024-11-02 | International Green and Sustainable Computing Conference | 0 | 5 | semantic_scholar |
| [10](https://doi.org/10.1016/j.iotcps.2024.03.001) | WITHDRAWN: Non-work conserving dynamic scheduling of moldable gang tasks on multicore systems | 2024-03-01 | Internet of Things and Cyber-Physical Systems | 0 | 5 | open_alex |
| [11](http://arxiv.org/abs/2606.26701v1) | SegFold: Accelerating Sparse GEMM with a Fine-Grained Dynamic Dataflow | 2026-06-25 | arXiv | 0 | 5 | arxiv |
| [12](https://doi.org/10.1109/jiot.2026.3727005) | Dynamic Task Scheduling for Heterogeneous Multi-core Baseband Processors in IIoT | 2026 | IEEE Internet of Things Journal | 0 | 5 | crossref |
| [13](https://doi.org/10.2139/ssrn.6749762) | An Algorithm-Hardware Co-Optimized Accelerator for Efficient Deep GCN Inference with Hybrid Dataflow and Dynamic Pruning | 未知 |  | 0 | 5 | crossref |
| [14](https://doi.org/10.1109/tpds.2024.3430063) | InSS: An Intelligent Scheduling Orchestrator for Multi-GPU Inference With Spatio-Temporal Sharing | 2024-07-18 | IEEE Transactions on Parallel and Distributed Systems | 24 | 4 | open_alex |
| [15](https://doi.org/10.1145/3649329.3655979) | Partitioned Scheduling and Parallelism Assignment for Real-Time DNN Inference Tasks on Multi-TPU | 2024-06-23 |  | 8 | 4 | open_alex |
| [16](https://doi.org/10.1109/gcce62371.2024.10760930) | MTST: A Multi-Task Scheduling Transformer Accelerator for Edge Computing | 2024-10-29 | 2024 IEEE 13th Global Conference on Consumer Electronics (GCCE) | 4 | 4 | crossref |
| [17](https://doi.org/10.48550/arxiv.2601.03708) | MHRC-Bench: A Multilingual Hardware Repository-Level Code Completion benchmark | 2026-01-07 | arXiv (Cornell University) | 0 | 4 | open_alex |
| [18](https://doi.org/10.48550/arxiv.2510.14719) | Tawa: Automatic Warp Specialization for Modern GPUs with Asynchronous References | 2025-10-16 | arXiv (Cornell University) | 0 | 4 | open_alex |
| [19](http://arxiv.org/abs/2510.05632v1) | From Principles to Practice: A Systematic Study of LLM Serving on Multi-core NPUs | 2025-10-07 | arXiv | 0 | 4 | arxiv |
| [20](https://doi.org/10.2139/ssrn.5625286) | DFTS-MCS: Dynamic Fault-tolerant Scheduling for Mixed-criticality Systems on Heterogeneous Multi-core Processors | 2026-06 | Journal of Systems Architecture | 0 | 4 | crossref |
| [21](https://doi.org/10.52843/cassyni.qrrjjy.3) | NektarIR: A Domain-Specific Compiler for High-Order Finite Element Operations on Heterogeneous Hardware | 未知 |  | 0 | 4 | crossref |
| [22](https://doi.org/10.1016/j.future.2024.04.038) | ADS-CNN: Adaptive Dataflow Scheduling for lightweight CNN accelerator on FPGAs | 2024-09 | Future Generation Computer Systems | 13 | 3 | crossref |
| [23](https://doi.org/10.1109/tpds.2024.3508275) | Slark: A Performance Robust Decentralized Inter-Datacenter Deadline-Aware Coflows Scheduling Framework With Local Information | 2024-11-28 | IEEE Transactions on Parallel and Distributed Systems | 3 | 3 | open_alex |
| [24](https://doi.org/10.21203/rs.3.rs-3853411/v1) | DMDP: A Dynamic Multi-Delta Prefetcher with Customizable Runtime Quality-Aware Feedback | 未知 |  | 1 | 3 | crossref |
| [25](https://doi.org/10.1109/icsrs63046.2024.10927459) | Predictive Age-Aware Runtime Remapping for Many-Core Systems | 2024-11-20 |  | 0 | 3 | open_alex |
| [26](https://doi.org/10.1007/978-3-031-61763-8_9) | Dynamic Tuning of Core Counts to Maximize Performance in Object-Based Runtime Systems | 2024-01-01 | Lecture notes in computer science | 0 | 3 | open_alex |
| [27](https://doi.org/10.1007/978-981-96-1551-3_21) | FusionFrame: A Fusion Dataflow Scheduling Framework for DNN Accelerators via Analytical Modeling | 2025-01-01 | Lecture notes in computer science | 0 | 3 | open_alex |
| [28](http://arxiv.org/abs/2508.07009v1) | Neural Channel Knowledge Map Assisted Scheduling Optimization of Active IRSs in Multi-User Systems | 2025-08-09 | arXiv | 0 | 3 | arxiv |
| [29](http://arxiv.org/abs/2411.00734v2) | Multilayer Dataflow: Orchestrate Butterfly Sparsity to Accelerate Attention Computation | 2024-11-01 | arXiv | 0 | 3 | arxiv |
| [30](http://arxiv.org/abs/2408.15429v1) | Generation of Compiler Backends from Formal Models of Hardware | 2024-08-27 | arXiv | 0 | 3 | arxiv |
| [31](https://doi.org/10.2139/ssrn.6905503) | TT-QEC: An Open-Source Hardware-Native MLIR Compiler for Quantum Error Correction Decoding | 未知 |  | 0 | 3 | crossref |
| [32](https://doi.org/10.21203/rs.3.rs-3924118/v1) | Differential Testing Solidity Compiler through Deep Contract Manipulation and Mutation | 未知 |  | 0 | 3 | crossref |
| [33](https://doi.org/10.2139/ssrn.6963023) | Service Dependency Intelligence for Contract-aware Agent Design in Enterprise Microservice Architectures | 未知 |  | 0 | 3 | crossref |
| [34](https://doi.org/10.1109/lca.2024.3484648) | ONNXim: A Fast, Cycle-Level Multi-Core NPU Simulator | 2024-07-01 | IEEE Computer Architecture Letters | 19 | 2 | open_alex,arxiv |
| [35](https://doi.org/10.1145/3694715.3695949) | Icarus: Trustworthy Just-In-Time Compilers with Symbolic Meta-Execution | 2024-11-04 |  | 17 | 2 | open_alex |
| [36](https://doi.org/10.1145/3626202.3637556) | Survival of the Fastest: Enabling More Out-of-Order Execution in Dataflow Circuits | 2024-04-01 |  | 8 | 2 | open_alex |
| [37](https://doi.org/10.1109/dsd64264.2024.00052) | Seal5: Semi-Automated LLVM Support for RISC-V ISA Extensions Including Autovectorization | 2024-08-28 |  | 6 | 2 | open_alex |
| [38](https://doi.org/10.1145/3748173.3779568) | Towards Scheduling of Pipelined Dataflow Graphs in MLIR | 2026-02-05 |  | 0 | 2 | open_alex |
| [39](http://arxiv.org/abs/2407.05459v1) | Hiring for An Uncertain Task: Joint Design of Information and Contracts | 2024-07-07 | arXiv | 0 | 2 | arxiv |
| [40](http://arxiv.org/abs/2501.00655v1) | Finding Missed Code Size Optimizations in Compilers using LLMs | 2024-12-31 | arXiv | 0 | 2 | arxiv |
| [41](http://arxiv.org/abs/2401.16448v1) | LLM4SecHW: Leveraging Domain Specific Large Language Model for Hardware Debugging | 2024-01-28 | arXiv | 0 | 2 | arxiv |
| [42](https://doi.org/10.1109/mm.2026.3671071) | Dataflow-Reconfigurable CNN Accelerator Design | 2026-05 | IEEE Micro | 0 | 2 | crossref |
| [43](https://doi.org/10.1109/iccvdm66874.2025.11290078) | Feature-Stationary Dataflow Enabled Diffusion Transformer Accelerator | 2025-09-12 | 2025 6th International Conference on Computer Vision and Data Mining (ICCVDM) | 0 | 2 | crossref |
| [44](http://arxiv.org/abs/2407.10216v1) | Applications of Particle Accelerators | 2024-07-14 | arXiv | 0 | 1 | arxiv |
| [45](http://arxiv.org/abs/2606.25159v1) | Accelerator Complex Evolution at Fermilab | 2026-06-23 | arXiv | 0 | 1 | arxiv |
| [46](http://arxiv.org/abs/2509.14410v1) | Consideration of REBCO rapid-cycling diploe magnet for staged muon acceleration | 2025-09-17 | arXiv | 0 | 1 | arxiv |
| [47](https://doi.org/10.1680/fcmh.66526.135) | Completion of the works | 2024-01-01 | FIDIC 2017: The Contract Manager’s Handbook | 0 | 1 | crossref |
### Model Knowledge

回忆来源仅用于补召回，随后全部查阅primary。它们是明确放宽年份的foundational追溯，不混进2024–2026 API计数。

| Title | Year | Venue | Notes |
|---|---|---|---|
| [SPDI Scheduling for EDGE Architectures](https://www.cs.utexas.edu/~lin/papers/pact04.pdf) | 2004 | PACT | model-recall → 正文核验；静态mapping动态issue |
| [VTA](https://arxiv.org/abs/1807.04188) | 2018/2019 | arXiv/IEEE Micro | model-recall → 正文核验；dependency queues |
| [TaskStream](https://par.nsf.gov/servlets/purl/10320225) | 2022 | ASPLOS | model-recall → 正文核验；typed task hints |
| [ASPEN](https://papers.neurips.cc/paper_files/paper/2023/hash/d899a31938c7838965b589d9b14a5ca6-Abstract-Conference.html) | 2023 | NeurIPS | model-recall → 正文核验；offline tile DAG、DSE |

完整摘要：[structured JSON](../sources/paper_search_structured.json)。初次42、补采47；没有进行no-hit novelty inference。