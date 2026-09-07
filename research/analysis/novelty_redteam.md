# 新颖性红队：可保留的是待验证问题，不是既定机制

日期：2026-09-05。范围：学术 novelty screening；不替代专利权利要求检索。R1 是用户编译器的历史记录，源码不在本目录；本文不把 R1 的代码路径当作当前可验证实现。

## Verdict

**Level 2 — High Overlap**，针对“编译器给映射/依赖合同，NPU 通过 completion 动态派发 ready tasks”这一机制主张。最接近的 2026 openNVDLA 硬件调度论文在核心机制、协同 insight 和 AI accelerator 应用域三轴重合；其实际评估主要针对 CPU 调度开销，与本研究希望解释的 runtime uncertainty 尚有区别。EDGE/SPDI、VTA、ASPEN、TaskStream 分别覆盖静态放置动态发射、token 合同、离线 tile DAG 分布式 ready dispatch、带静态提示的层次 task dataflow。这个判级是选定轴下的人工检索结论，不是“还剩一轴即可发表”。

R2 的 memory-planning 子方向也不能继续宽泛声称“尚未同时覆盖”：**LATTICE v3 已明确将 static memory plan 作为 verifiable scheduling contract，并以地址复用边约束后续 timing refinement**。它不是 runtime dynamic hardware 研究，但直接覆盖 R2 建议的一大段编译器内核。[当前原文](https://arxiv.org/html/2607.17422)。

## Delta

目前不能写出带有“已获得可测收益”的可靠 delta。可以保留下面的**条件式研究问题**：

> 相比 LATTICE 的静态单核 memory-plan-constrained timing refinement，以及 TaskStream 的 task structure recovery，本研究拟在相同已优化 mapping/address/partial order 下，找出端侧多核 NPU 的共享通信资源完成不确定性何时需要额外调度自由度，并定量检验有限窗口、有限 wakeup 带宽的局部硬件是否获得足以支付成本的收益。

该句不能被当成已证明 contribution。它必须经过 realistic contention、强静态训练/测试隔离、信息对等与状态成本扫描；若收益消失，结论应改为“静态 compiler + self-timed queues 足够”。

## Decomposed claim

- **Problem framing**：编译期图/地址已知、执行完成时刻未知的 NPU，比较同一合法执行空间中的强静态与动态 dispatch。
- **Core mechanism**：编译器编码依赖、合法位置与资源条件；运行时仅维护有限 completion/ready/resource 状态。
- **Key insight**：将全图 reasoning 离线化，只把剩余运行时信息交给硬件，避免重复实现复杂 scheduler。
- **Application domain**：端侧多核/多 cluster/多 chip AI accelerator，LLM 与 DiT 的 inference execution。

## Structured papers

全量 API 原始检索及逐条筛选见 [search_report.md](../literature/search_report.md) 与 [step3.md](../literature/scoop_steps/step3.md)。下表是正文优先读取的 7 篇；补充工程与其他学术条目见 [prior_art_registry.md](../literature/prior_art_registry.md)。这 7 篇按机制威胁与新近程度选择，不以 citation 数自动排序。

| 候选 | 选择理由 | 阅读证据与局限 |
|---|---|---|
| SPDI / EDGE 2004 | 静态 placement + dynamic issue + locality/contention 完整范式 | 作者 PDF §1–3、§4–5；本地下载失败，使用完整 PDF 解析正文 |
| VTA 2018/2019 | 编译 dependency bits + load/compute/store queues | 本地 PDF §3.1、§4–5；不能推断同队列 ready-set 任意重排 |
| TaskStream 2022 | typed task edges、coreMask、sizehint、hierarchical dataflow | 本地 PDF §2.2、§3.1/3.4、§4–5；高层自动 compiler 是 future work |
| ASPEN 2023 | 离线 tile graph + completion counters + distributed schedulers | 本地 PDF §3.1–3.3、§4–5；CPU prototype，cache/coherence 与 scratchpad 不同 |
| PipeThreader 2025 | 静态 task/异构 engine 调度已经消除很多 pipeline bubble | 本地 PDF §3.1–3.2、§4、§5；不是低层 warp dispatch 的替代 |
| HwSch/openNVDLA 2026 | 最近 NPU execution/dependency instruction + ROB/OCSR | 本地 PDF §3.1–3.4、§4；CNN，主要 host overhead，不能支持 LLM latency uncertainty 收益 |
| LATTICE 2026 v3 | memory plan contract + reuse order + legal pipeline refinement | 本地 PDF §III、§IV-D/E、§V；single-core deterministic replay，不是 device silicon 测量 |

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

## R2 必须修改的判断

| 原判断 | 红队结论 |
|---|---|
| 本方向在微结构上就是 CDC 6600 scoreboard | 过强。counter/event task scheduler 是中性描述；必须说明有无 hazard discovery、operand tags、renaming、commit |
| 无复用边时动态收益恒为零 | 只在 R2 toy 中成立，不是一般 DAG 定理。乱序回避 HOL 可以纯由不同 producer 完成顺序造成 |
| 只有 heavy tail 才有价值 | 无依据泛化。分布相关性、图宽度、瓶颈位置、有限窗口和 policy 决定收益；有界双峰或外部 contention 也可能足够 |
| 动态无法解决 DMA/bank conflict | 不增加物理带宽，但可选择不同 bank/consumer、限制并发、避免关键流阻塞；须对照静态优化与测通信代价 |
| 全部工业 token NPU 都覆盖 ready-set OoO | token self-timed 与同 engine 重排不同；可以证明范式不新，不能证明具体能力等价 |
| 少量计数器相对 4MiB SRAM 面积可忽略 | 字节小不等于 control 成本小。read/write ports、wakeup bandwidth、arbitration timing、事件别名验证均需计入 |
| memory reuse + verifiable contract 未被同时覆盖 | LATTICE v3 已直接覆盖大段静态问题，必须重新界定 delta |
| R2 4.5% 表明方向应该移回 compiler | 只能说明其狭窄 toy 的结果；用户本轮扩展多 cluster/chip 合理，是否成立需要新增实验 |

## 最有杀伤力的否定实验

1. 同一 DAG、mapping、memory contract、task granularity、DMA outstanding 与预取深度；静态使用多 policy/局部改良，不能只用一次关键路径排序。
2. 正常噪声先在训练 seeds/distribution 上选最优静态顺序，测试用不同 seeds。若静态每次拿到真实 duration，就将其明确命名为 clairvoyant static oracle；runtime 不能知道未完成 task 的剩余寿命。
3. baseline 加入 self-timed 跨引擎队列、共享 DMA work-conserving arbitration，单独报告“消除 host overhead”“放开 order”“增加资源”“改善 mapping”四项。
4. B 只增加有限 ready window + counter；C 允许更强 priority 或合法位置集合。若 C 的收益来自 mapping/地址/容量变化，不能说是复杂 OoO 超过 scoreboard。
5. 同时扫 task 长度、ready width、fanout、wakeup bandwidth、窗口、completion latency。更细 DAG 必须付 descriptor 和控制开销。
6. 多 chip 要计入 event delivery latency、reliable credit 和 visibility，集中调度必须受同等带宽约束；不允许无限速中央 ready oracle。
7. 若强静态加简单 DMA arbitration 已取得大部分收益，拒绝大窗口核心 OoO；若收益只在通信，改称 communication-aware latency-tolerant dispatch；若所有收益来自额外 SRAM，归因于 capacity 而非 reorder。
