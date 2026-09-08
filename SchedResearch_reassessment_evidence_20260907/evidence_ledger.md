# SchedResearch 科研重审：取证与检索附录

日期：2026-09-07；项目固定提交：`a947b563356610cf4dbb05995debf18fc3054e66`。
本附录登记实际阅读范围，不将全文获取等同全文阅读，也不将历史 PASS 记为本次复跑。项目没有写入或冻结结果修改。

## 本次执行边界
本次仅执行 `bound_witness.py` 的算术与 request-link 下界验证。未运行历史性能实验，未运行新模拟器，未测真实设备。

## 项目阅读覆盖
| 路径 | 阅读位置 | 证据等级 | 依据/边界 |
|---|---|---|---|
| [research/research_progress.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/research_progress.md) | 全文，含 R10/R11 末尾追加 | 历史报告阅读 | 逐轮结论有明确合同边界；旧投入建议不作为本次选题约束 |
| [research/analysis/r1_r10_research_retrospective.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/analysis/r1_r10_research_retrospective.md) | 全文，含 R11 追加 | 历史报告阅读 | 正式候选台账、关闭/未测区分 |
| [research/r1-base/redteam_claim_frameworks.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r1-base/redteam_claim_frameworks.md) | 1–150 行：C1–C10 定义表及 D1 开头 | 节选阅读 | 仅核查原始候选定义；不把历史 TARS 当作新硬件 |
| [research/r2-ooo-npu/research.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r2-ooo-npu/research.md) | 228–360 行：原始 P1–P5 及末尾 | 节选阅读 | quasi-static 变体原已提出；宽泛必要条件被 R3 撤回 |
| [research/r3/experiment_report.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r3/experiment_report.md) | 全文 | 历史报告阅读 | 150/140 存在性；收费可达 156；并非真实 NoC |
| [research/r3/architecture_proposal.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r3/architecture_proposal.md) | 全文 | 历史报告阅读 | window 外的 O(N+E) 状态及成本边界 |
| [research/analysis/static_vs_dynamic.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/analysis/static_vs_dynamic.md) | 全文 | 历史报告阅读 | 固定资源序 + self-timed，不是固定启动周期 |
| [research/r4/experiment_report.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r4/experiment_report.md) | §1–§4、§5 开头 | 节选阅读 | 强静态、因果单动作对照；未独立读取全部 raw trace |
| [research/r5/experiment_report.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r5/experiment_report.md) | 全文，含 compiler residency 控制 | 历史报告阅读 | request/bank/credit 已测；非完整 NoC |
| [research/r5/model.py](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r5/model.py) | 全文 | 源码检查 | 资源配置、图与请求粒度；不是 router 模型 |
| [research/r5/resource_sim.py](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r5/resource_sim.py) | 80–245 行 | 源码检查 | 同周期批量完成，return credit，串行 fabric，本地 bank；总 SRAM BW 不因 bank 数增加 |
| [research/r8/experiment_report.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r8/experiment_report.md) | 全文 | 历史报告阅读 | direct peer/staging 字节与有限可见性枚举；未测时序 |
| [research/r8/source_contract_audit.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r8/source_contract_audit.md) | 全文 | 历史报告阅读 | split-K 非 bitwise；物理路由与数值准入分开 |
| [research/r9/reference_hardware.json](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r9/reference_hardware.json) | 全文 | 合同检查 | 单全局 EXT，两 cluster DMA，cross-cluster staging，无本地 bank/NoC |
| [research/r9/model_notes.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r9/model_notes.md) | 全文 | 合同/模型说明检查 | ready-command 准入及 RR 是 baseline 自带行为 |
| [research/r9/model.py](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r9/model.py) | 全文 | 源码检查 | external_busy；read/write 两段服务；credit、完成和可见性 |
| [research/r9/experiment_report.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r9/experiment_report.md) | 全文 | 历史报告阅读 + 独立算术复算 | 47,776；2,998,272 B；46,848 下界；1.9424% 固定流量余量 |
| [research/r10/reference_hardware.json](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r10/reference_hardware.json) | 全文 | 合同检查 | 继承 R9 参考硬件；对照 contract_delta |
| [research/r10/contract_delta.json](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r10/contract_delta.json) | 全文 | 合同检查 | EXT128/DMA32 与观察/动作收费 |
| [research/r10/experiment_report.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r10/experiment_report.md) | 全文 | 历史报告阅读 | 1,440 次观察，0 次实际改序；不是全面动作否定 |
| [research/r11/contract.json](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r11/contract.json) | 全文 | 合同检查 | 独立双核、共享 local/EXT、cold-weight、staged ABI、strict decode clobber |
| [research/r11/simulator.py](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r11/simulator.py) | 全文 | 源码检查 | 资源顺序已编码在 DFG；不是 R9 的连续细化 |
| [research/r11/model.py](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r11/model.py) | 1–100 行：Builder.add 及资源前驱 | 源码检查 | last[res] 插入 FIFO 顺序边 |
| [research/r11/experiment_report.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r11/experiment_report.md) | 全文 | 历史报告阅读 + 独立算术复算 | local-state −75%，external bytes 不变，完整 elapsed 未改善 |
| [research/r11/independent_audit.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r11/independent_audit.md) | 全文 | 历史审计报告阅读 | 122 trace PASS 是历史审计；本次没有重放它们 |
| [research/r11/results.json](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/r11/results.json) | quiet aggregate 与开头配对结果；长文件未全读 | 已有结果部分检查 | 核对 quiet 值、固定 external bytes；非全部 trace 审计 |
| [research/literature/prior_art_registry.md](https://github.com/kongxiangcong/SchedResearch/blob/a947b563356610cf4dbb05995debf18fc3054e66/research/literature/prior_art_registry.md) | 全文 | 既有登记阅读 | 继承条目不等于本次全文核验；逐项分开 |

## 外部原文和代码
| 来源 | 版本与阅读范围 | 缺口/限制 |
|---|---|---|
| [Tenstorrent memory guide](https://docs.tenstorrent.com/tt-metal/latest/tt-metalium/tt_metal/advanced_topics/memory_for_kernel_developers.html) | 官方在线文档，2026-09-07 获取；内存与 NoC 开发者合同正文 | 非 coherence；多个 DRAM endpoint 可共享 controller；未测设备 |
| [Wormhole ISA NoC](https://github.com/tenstorrent/tt-isa-documentation/tree/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC) | 5287a62727350bcef35f7b411d1b8a706172ec4c；README/Ordering/RoutingPaths 全文；MemoryMap 1–180、Counters 1–155、Coordinates 1–130 | 计数器、请求发起、源读完、目的写完的事件不同；队列深度与板卡参数仍需确认 |
| [STREAM/TETRA](https://github.com/KULeuven-MICAS/stream/tree/75748cc17e7c43add5a7d0d8f080841eb26531c4) | 75748cc17e7c43add5a7d0d8f080841eb26531c4 / 1.14.1；官方 hardware/mapping 文档；TransferAndTensorAllocator 1–230；utils.py 全文；DMA constraint 搜索 | 当前实现已有 capacity/FIFO/BD/DMA、placement/routing；路径估价函数不是 VC 周期模型；原始正式论文全文未获取 |
| [tt-npe](https://github.com/tenstorrent/tt-npe/tree/341da058f0b65e51d3643fb36f011a0784abedff) | 341da058f0b65e51d3643fb36f011a0784abedff；README，npeAPI.cpp 全文，npeEngine.cpp 1–250 | fast 拥塞估价；n−2 dependency 是 2-VC 效果近似，不是逐 flit credit；未运行 |
| [ttsim](https://github.com/tenstorrent/ttsim) | 在线 README；功能仿真入口说明 | 未证明可作周期/吞吐校准，未运行 |
| [TPU v4](https://arxiv.org/abs/2304.01433) | TPU v4 论文；§3.5 和 Fig.7（PDF 第6页图像） | SparseCore tile–HBM channel 关联，不能外推 TensorCore 或把 ICI 当片内 NoC |
| [Groq ISCA 2022](https://groq.com/isca-2022-paper/) | DOI 10.1145/3470496.3527405；作者全文取得，重点 §2.3、§3–4 | 静态 compute/communication 与软件流控；非 Wormhole 透明替代合同 |
| [Simba](https://research.nvidia.com/publication/2019-10_simba-scaling-deep-learning-inference-multi-chip-module-based-architecture) | MICRO 2019；另定位作者 CACM 后续；作者题录/摘要；原 PDF 多入口下载失败 | 未声称完整核验原论文算法、全部参数或实现 |
| [Occamy](https://pulp-platform.github.io/occamy/rm/1_overview.html) | 公开手册；论文 2406.15068 / 2501.07330 题录；手册和论文元数据 | cluster DMA、HBM、AXI；手册与论文容量版本不一致；原论文全文未成功获取 |
| [TETRIS](https://web.stanford.edu/~mgao12/pubs/tetris.asplos17.pdf) | ASPLOS 2017，10.1145/3037697.3037702；架构 §3、算法 §4、方法 §5、相关工作；Fig.2/3 图像核验 | 16 vault；每 vault 多 bank 共享 TSV；论文架构，非产品；不是 BF16 Qwen 原生硬件 |
| [nn_dataflow](https://github.com/stanford-mast/nn_dataflow/blob/master/README.rst) | README blob d53c0c3b01c935a65bf1e26aa9dbcf6aae26a9c0；README 全文 | TETRIS/TANGRAM dataflow/partition/pipeline 作者入口；不等于原 cycle simulator 完整发布 |
| [Neurocube](https://casl.gatech.edu/2016/09/neurocube-isca-2016-paper-makes-news/) | ISCA 2016；作者机构页面及 TETRIS 的直接引用 | 原文全文未取得；不使用未核验的产品参数 |
| [Tesseract](https://doi.org/10.1145/2749469.2750386) | ISCA 2015；一手题录/摘要，另定位作者 retrospective 2306.15577 | 图处理 PIM，原始全文未获取，不等于 DNN 编译合同 |
| [HD-MoE](https://arxiv.org/abs/2509.09420) | v1；ICCAD 2025 DOI 10.1109/ICCAD66269.2025.11240984；原文 hardware/mapping/online/evaluation 方法；作者代码 | offline TP/EP + node/link balance + online pre-broadcast 是直接近邻 |
| [HD-MoE code](https://github.com/angerybob/HD-MoE/tree/94ba08ecaa01bbfe3ace2c56aab1698cdfcc7f8f) | 94ba08ecaa01bbfe3ace2c56aab1698cdfcc7f8f；README 全文；simulator.py 1–230；node_allocation.py 1–295 | 逐链路 chunk calendar，不是 VC/DRAM cycle model；入口参数签名需资格核查；未运行 |
| [HDA-MoE](https://github.com/angerybob/HDA-MoE) | README blob 786e7d628c9824c137ded4312387a210d183dd4f；作者 README 全文 | 作者称 TCAD accepted；尚无最终 DOI/取得的全文；容量/拓扑/动态/gating 扩展，gating 改路由应另立数值合同 |
| [Expert Streaming](https://arxiv.org/abs/2603.27624) | 2026 预印本；§IV–V、实现与约束正文 | 动态 trajectory + micro-expert + overlap；prototype/evaluation 限制不能忽略；未获取作者代码 |
| [DeepStack](https://arxiv.org/html/2604.04750v1) | v1，2026 预印本；§4.1.3/4.1.4 模型、DSE/功耗热方法 | bank 映射、逐链路字节与 3D DSE 已覆盖；非 NIU/VC/visibility 精确执行模型；未核查代码 |
| [LATTICE / DAN](https://arxiv.org/html/2607.17422v3) | 同一 arXiv 编号；v1 DAN-Scheduler，v3 LATTICE；v3 §I–IV、评估开头；v1 元数据 | 同一工作版本演进，不能列成独立两篇；memory-plan-preserving scheduling 已有 |
| [Event Tensor](https://arxiv.org/html/2604.13327v1) | v1，2026 预印本；§II–III 等方法正文 | 事件依赖与 compiled tile runtime 已有；GPU 开销不可移植 |
| [TaskStream](https://polyarch.cs.ucla.edu/papers/asplos2022-taskstream.pdf) | ASPLOS 2022 作者 PDF；§2 typed task graph、§6 讨论、参考文献 | typed edges/coreMask/NoC/动态执行；文中已有 bisection 瓶颈讨论；非本次硬件成本 |
| [ASPEN](https://papers.neurips.cc/paper_files/paper/2023/file/d899a31938c7838965b589d9b14a5ca6-Paper-Conference.pdf) | NeurIPS 2023 正式版；§3.1–3.3 和算法1 | offline tile DAG + distributed scheduling engines + Ready Pool；CPU 成本不能借用 |
| [SoMa](https://arxiv.org/html/2501.12634) | HPCA 2025 作者原文；§II–V、评估与 artifact 入口 | fusion/tiling/prefetch/delayed store/buffer allocation 已有；未检查作者源代码 |
| [TileLink](https://arxiv.org/html/2503.20313) | 2025 原文；§3 方法与 mapping/synchronization | tile-level data/signal、acquire/release、compute/comm 解耦已存在 |
| [Mozart / ESP](https://experts.illinois.edu/en/publications/mozart-taming-taxes-and-composing-accelerators-with-shared-memory/) | PACT 2024 DOI 10.1145/3656019.3676896；作者机构题录与摘要 | ASI/control tax/data tax；未取得本次可核查全文，不借用其端到端费用 |
| [Bounded process-network execution](https://ptolemy.berkeley.edu/publications/papers/99/HMAD/html/pn.html) | Ptolemy 官方说明；Parks 1995 作者入口；PN 说明正文；thesis PDF 失败 | 有界 FIFO 可引入额外死锁；不把无限队列语义当物理证明 |
| [ZigZag](https://kuleuven-micas.github.io/zigzag/hardware.html) | 官方在线文档；hardware model 说明 | 单核估价/数据流，不是原生 Wormhole kernel 周期校准 |
| [Timeloop / Accelergy](https://timeloop.csail.mit.edu/) | 官方入口；架构/映射/成本角色 | 候选估价与能耗组件；未运行 |
| [BookSim2](https://github.com/booksim/booksim2) | 作者 README；工具能力 | 需要目标 routing/VC/credit adapter；支持 torus 不等于复现 Wormhole |
| [Ramulator2](https://github.com/CMU-SAFARI/ramulator2) | 作者 README；工具能力 | 不能默认 GDDR6/controller 合同已支持或已经校准；未运行 |
| [3D thermal follow-up search](https://doi.org/10.1145/3806645.3820075) | 2026 HPDC 检索结果；题录/摘要检索，打开全文失败 | 只列新增近邻与缺口，不用于具体方法或性能主张 |

## 检索记录
检索日期均为 2026-09-07。检索服务用于定位，关键判断采用一手来源；GitHub 文件通过已连接 GitHub 工具读取。以下为实际检索的关键词族归并，不声称穷尽所有组合。
| 问题组 | 关键词 | 实际检索来源 | 结果 |
|---|---|---|---|
| 硬件 | multi-cluster accelerator NoC DMA shared DRAM; Tensix NoC DRAM controller; TPU SparseCore HBM channel; Groq TSP compiler scheduled communication; Occamy cluster DMA HBM; Simba communication aware data placement | 官方 docs、作者/大学页面、arXiv、GitHub connector | A 首选 Wormhole；Occamy 合同版本需进一步固定 |
| 3D | 3D stacked memory neural network accelerator vault scheduling; bank local near memory processing compiler mapping; TETRIS Neurocube Tesseract; 3D logic memory hybrid bonding NoC scheduling | 作者 PDF、arXiv、出版社题录、作者 GitHub | TETRIS 可追溯论文合同；DeepStack/HD/HDA 提高广义联合规划新颖性风险 |
| 编译/执行 | static dataflow graph bounded out of order accelerator runtime; compiler memory plan dependency scheduling contract; communication memory placement routing co optimization DNN accelerator; STREAM TETRA tensor placement transfer routing; hardware task manager heterogeneous accelerator dependency synchronization | 作者论文、官方文档、GitHub code search | 不能把 contract/completion dispatch、tensor placement 或有限 DMA 配额作为新贡献 |
| 近邻 | MoE 3D near memory hybrid dynamic parallelism; expert streaming chiplet scheduling; finite buffer dataflow scheduling deadlock; compiler controlled NoC injection scheduling | arXiv、作者仓库、Ptolemy 官方资料 | 区分形状确定的内生争用与 routing 揭示后的工作量；保留反证 |

## 引文追踪
TETRIS 原文 → Neurocube；TETRIS 作者代码 → TANGRAM 后续。HD-MoE 原文/仓库 → 2026-09-02 链接的 HDA-MoE。DAN v1 → 同 arXiv 编号 LATTICE v3，按同一工作处理。TaskStream 方法及 §6 网络割瓶颈 → 复核强映射不能被弱化的反证。STREAM 正式论文题录 → 2026-09-01 当前作者实现，功能增量不反向归属 2025 原文。前后向检索不是完整引文数据库覆盖。

## 独立计算结果
R9：2,998,272 / 64 = 46,848 cycles；固定 bytes 的 elapsed 最大缩短比例 = 1.9423978567%。
R11：state local bytes 减少 75%；quiet elapsed 缩短比例 = −0.0156706375%。
NoC0：两条 1 KiB 单包写请求，每包 1 个 header + 32 个 data flit。两计划总请求量和总 byte-hops 相同；共享链路计划最重链路 66 flit，分离计划 33 flit。这仅区分 request-link 服务下界，不能推出完整模块 2× 加速，不能证明新方法超过 STREAM，也不是乱序机制实验。

## 运行
```bash
python bound_witness.py --output bound_witness_result.json
```
该命令仅写指定输出文件。对实机需先检查 SoC descriptor/harvest mask；例子使用未 harvest 的 NoC0 raw coordinate，不是某一实际板卡检测结果。

## 下一轮立项门的建议
主线：先验证真实 NoC 完成与共享资源合同是否改变强联合编译计划的优劣；优先编译器求解与原生异步执行，不先发明硬件。备选：只有静态残差、可触发动作、合法窗口与收费净收益同时成立，才测固定 mapping/address 的有界 runtime。
最小主实验：四个活动 Tensix tile、两个真实 controller domain、两条 load→compute→peer→consumer 链、两个可复用 buffer slot；在强 TETRA/原生 pipeline 之上比较带明确 source-last-read、destination-visible 和共享资源约束的计划。必须先通过功能与事件 oracle，再报告完整输出可见的 elapsed。
新颖性失败条件：现有优化器只需正常配置或直接接入正确 controller/path/容量约束即可达到相同结果；此时是后端建模/移植，不支持新调度器论文主张。
性能阈值只能在成本/误差协议冻结后使用：建议编译器/有界 runtime 各自净完整模块改善 3%，模型误差审计不高于约 1 个百分点；runtime gross recovery 还应至少覆盖两倍暴露控制成本。该阈值是本轮建议而非任何硬件的物理常数，结果之前固定。

## 未完成项
- R6/R7 原始报告、原始设备回执未重新读取；依据两份完整台账
- R4 报告只读取指定主要章节；R4/R5/R9/R10 原始 timing traces 未独立重放
- R11 results.json 仅部分读取；122 traces 审计仅为历史报告记载
- Simba/Occamy/Neurocube/Tesseract/STREAM 正式论文和 Mozart 全文未完成取得或逐章核验
- HDA-MoE 接受状态来自作者仓库，最终发表 DOI 与完整稿未取得
- 未进行完整前后向引文数据库穷尽检索，不宣称没有其他先例
- 没有可用的原生硬件端到端成本校准；ttsim 不能替代周期数据
- TETRIS 部分表格页截图失败；引用参数取自可读正文，架构图截图成功
