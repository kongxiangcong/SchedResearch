# Step 5 — Full-Paper Deep Dive

日期：2026-09-05。状态：完成当前限定scope；未取得全文的候选保留限制。

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



## Extraction log

### aspen.fetch.log
```text
ok: extractor=pdftotext -layout pdf_bytes=1016283 txt_bytes=71982 txt_lines=986
D:/dsh-proj/SchedResarch/literature/sources/papers/aspen.txt

```
### dan_scheduler.fetch.log
```text
ok: extractor=pdftotext -layout pdf_bytes=1113219 txt_bytes=101984 txt_lines=993
D:/dsh-proj/SchedResarch/literature/sources/papers/dan_scheduler.txt

```
### hwsch2026.fetch.log
```text
ok: extractor=pdftotext -layout pdf_bytes=993407 txt_bytes=82710 txt_lines=845
D:/dsh-proj/SchedResarch/literature/sources/papers/hwsch2026.txt

```
### pipethreader.fetch.log
```text
ok: extractor=pdftotext -layout pdf_bytes=1321125 txt_bytes=142589 txt_lines=1308
D:/dsh-proj/SchedResarch/literature/sources/papers/pipethreader.txt

```
### spdi.fetch.log
```text
curl: (35) Recv failure: Connection was reset
FAILED: download error for https://citeseerx.ist.psu.edu/document?doi=3195af2e8ce905d27e5e896b73263c73f01e9375&repid=rep1&type=pdf

```
### spdi_ut.fetch.log
```text
curl: (55) Send failure: Connection was aborted
FAILED: download error for https://www.cs.utexas.edu/~lin/papers/pact04.pdf

```
### taskstream.fetch.log
```text
ok: extractor=pdftotext -layout pdf_bytes=1538203 txt_bytes=137538 txt_lines=1100
D:/dsh-proj/SchedResarch/literature/sources/papers/taskstream.txt

```
### vta.fetch.log
```text
ok: extractor=pdftotext -layout pdf_bytes=632617 txt_bytes=56953 txt_lines=504
D:/dsh-proj/SchedResarch/literature/sources/papers/vta.txt

```