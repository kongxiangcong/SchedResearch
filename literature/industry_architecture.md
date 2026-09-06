# 工业体系结构核验：Jalapeño与静态/动态边界

核验日期：2026-09-05。只记录本轮实际取得的证据，区分厂商声明、会议材料、二手信息、架构推论与猜测。厂商测得的系统优势不等于某个微结构机制的因果收益。

## 1. Jalapeño：先确定证据层级

| 主张 | 级别 | 实际证据与限制 |
|---|---|---|
| OpenAI与Broadcom公布定制LLM推理加速器Jalapeño | **confirmed fact：官方发布事实** | [OpenAI 2026-06-24](https://openai.com/index/openai-broadcom-jalapeno-inference-chip/)；不把发布日期当产品大规模部署日期 |
| 已进行公开模型测试；强调计算、内存、网络协同 | **confirmed fact：官方声明/自报结果** | [OpenAI 2026-08-25](https://openai.com/index/jalapeno-first-results/)；本轮未独立复现实验 |
| 局部放置模型状态/KV，显式通信、可预测同步，AI辅助mapping/placement/scheduling | **confirmed fact：已公开的编程模型描述** | 同一官方文章“Architecting…”和“We used AI…”两节；没有披露完整ISA/事件协议 |
| 2026-08-25 Hot Chips有OpenAI架构演讲 | **confirmed fact：会议记录** | [会议日程AI 2](https://hc2026.hotchips.org/)：“You Can Just Build … Chips”，Richard Ho、Ravi Narayanaswami、Chris Leary |
| sliced HBM/local view、专用低延迟collective网与一般NoC、spatial模型 | **credible secondary information** | [ServeTheHome现场报道](https://www.servethehome.com/openai-jalapeno-asic-at-hot-chips-2026/)列出slides25/26/30。本轮取得文字与图片URL，未取得官方PDF正文，也未成功读取图像像素；不能升级为独立读图核验 |
| 核内L1 cache与out-of-order issue，tensor/vector共享局部存储 | **secondary detail，尚未官方原图交叉确认** | [TechInsights架构文章](https://www.techinsights.com/openai-jalapeno-inference-chip-architecture)检索索引、[技术分析博客](https://zartbot.github.io/blog/arch/jalapeno/en.html)及其他报道给出细节；TechInsights全文本轮读取失败，博客混有“若我设计”的推测，**不作为confirmed** |
| 特定ROB大小、rename、memory disambiguation、cache替换/一致性、指令窗口宽度 | **speculation / 未建立** | 本轮没有原始证据，研究harness不采用这些参数，也不称Jalapeño实现Tomasulo |
| 系统优势主要来自OoO | **不成立的因果推断** | 系统比较同时改变HBM、拓扑、并行规模、kernel和功率归一化；没有iso-resource OoO ablation |

截至上述官方说明，仍在生产资格、软件成熟和规模验证阶段，计划年末开始部署。不能把实验室结果描述为已经完成大规模生产验收。[官方状态](https://openai.com/index/jalapeno-first-results/)

本轮对Jalapeño最有用的**architectural inference**是：静态局部放置与显式通信，可以和局部延迟容忍共存。它们不是互斥阵营。即使之后核实核内OoO，也只说明该层采用动态机制，不说明跨chip由一个全图动态scheduler统筹。

## 2. 专利：检索线索不是产品实现证据

从[专利索引文章](https://patentlyze.com/openai-jalapeno-chip-patents/)追到以下publication IDs，再尝试USPTO原文及Google Patents。USPTO返回403，Google Patents本轮返回Internal Error，故**未完成原始权利要求核验**。这里保留检索线索，不据其判断法律状态/可专利性，也不据此断言Jalapeño使用CIM。

| 线索 | 二手标题/范围 | 原文链接 | 本轮证据层级 |
|---|---|---|---|
| US20260161359A1 | memory与processor堆叠，KV lookup | [USPTO publication](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/20260161359) / [Google Patents](https://patents.google.com/patent/US20260161359A1/en) | metadata为二手待核验；原文不可达 |
| US20260154218A1 | tiled compute-in-memory architecture | [USPTO publication](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/20260154218) / [Google Patents](https://patents.google.com/patent/US20260154218A1/en) | 同上，不能推断产品采用 |
| US20260244403A1 | zero detection / gating | [Google Patents](https://patents.google.com/patent/US20260244403A1/en) | 同上；跳零电源门控不自动意味着可变执行周期 |

不能因标题“Seven patents behind Jalapeño”就视为对应关系。申请可能描述其他产品、后续代际或未实施方案；连续申请的申请日也不等同优先权日。后续要做专利方向，需要补原始claim chart与family/priority检索，本轮不出授权或法律新颖性意见。

## 3. 可直接核验的其他工业/开源架构

| 系统 | 已打开的一手材料 | 对软硬件边界的意义 | 不应推出什么 |
|---|---|---|---|
| TPU v1 | [ISCA2017作者论文摘要](https://arxiv.org/abs/1704.04760) | 软件管理片上内存、确定性执行以匹配tail latency | 不能把TPU所有后续代际都归为同一机制 |
| Groq TSP | [作者论文](https://pkamath.com/publications/papers/tsp-isca20.pdf)、[厂商论文页](https://groq.humain.ai/groq-isca-paper-2020/)；PDF本轮web读取失败，厂商/作者索引可核对题名和deterministic设计 | 硬件提供可预测时序，编译器可控制producer-consumer流 | 它证明另一种可行选择，不能证明任何共享外部memory NPU都能确定到每周期 |
| AWS NeuronCore-v2 | [官方架构说明](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/about-neuron/arch/neuron-hardware/neuron-core-v2.html) | Tensor/Vector/Scalar/GPSIMD异构engine，软件管理SRAM与compiler prefetch | 异构不等于动态随机延迟；不根据v2文档代写v3/v4架构 |
| Tenstorrent TT-Metalium | [circular buffer API](https://docs.tenstorrent.com/tt-metal/latest/tt-metalium/tt_metal/apis/kernel_apis/circular_buffers/circular_buffers.html) | producer/consumer通过reserve/push/wait/pop表达数据/空间可用性 | 队列流控并不等于任意ready task越过队头 |
| Gemmini | [官方源码README](https://github.com/ucb-bar/gemmini) | load/store/execute分离、跨controller乱序与controller内有序共存 | 不能因有ROB就照搬CPU微结构解释 |
| NVDLA | [官方unit description](https://nvdla.org/hw/v1/ias/unit_description.html) | 多engine、数据通路和配置行为是复用底座 | 不能把基于openNVDLA的2026论文当原始NVDLA能力 |
| MLIR async | [官方dialect](https://mlir.llvm.org/docs/Dialects/AsyncDialect/) | async token/value/group可以表达合同前端 | dialect不提供硬件资源调度/alias正确性证明 |

Gaudi/Ascend/AIE与更多学术工业近邻见[registry](prior_art_registry.md)。没有当前一手读取的具体数字在本表不重复列出。

## 4. 为什么scratchpad/static长期合理

规则dense算子中，数据复用、访问地址、tile footprint和算量静态可知。scratchpad可避免tag/replacement开销，让每字节的驻留与DMA可控；显式DMA适合长burst、双缓冲、可预测局部通信。专用阵列并不需要CPU规模的分支推测/重命名。编译器承担复杂性可能换来更简单的数据通路与可预测尾延迟。[TPU v1](https://arxiv.org/abs/1704.04760)、[NeuronCore-v2](https://awsdocs-neuron.readthedocs-hosted.com/en/latest/about-neuron/arch/neuron-hardware/neuron-core-v2.html)

但软件管理存储并不意味着所有资源时序确定；buffer容量有限、访问距离不同、DMA/网络争用、复杂异构小kernel的固定同步成本仍可造成等待。手动安排每次搬运还会使compiler和kernel编写复杂。动态机制可能付硬件成本换取对到达次序的适应；这是待量化的因果解释，不能仅因新芯片出现就认为它必然优于静态。

## 5. 四组trade-off不是单一开关

| 取舍 | 静态/显式一侧的收益 | 动态一侧的收益 | 对方的代价/反例 |
|---|---|---|---|
| Predictability vs latency tolerance | 可分析最坏时序、重复执行稳定 | 吸收相位误差、当前ready任务先执行 | 动态可能提高尾部和局部资源拥塞；静态也能用self-timed同步 |
| Static optimization vs runtime adaptability | 全图联合layout/fusion/memory/schedule | 根据实际completion修正局部顺序 | 缺少独立工作时无效；贪心非抢占可能阻塞即将ready的关键任务 |
| Scratchpad vs cache | 可控驻留、无替换冲突、显式带宽 | 自动命中/预取、减少细碎搬运管理、容忍部分不规则访问 | cache有miss/tag/带宽/污染成本；scratchpad也可配小cache与异步队列 |
| Compiler complexity vs scheduler complexity | 离线有时间做全图优化和证明 | runtime局部决策及时 | 动态硬件仍需编译器提供合法空间；静态约束太保守则硬件无自由 |

最值得检验的组合不是“抛弃静态”，而是将**可提前证明的正确性与局部性固定下来，仅让无法提前知道的就绪先后留在硬件**。这仍是已有范式；研究贡献需要来自具体硬件结构与受限成本下的定量优势。

## 6. 检索/获取限制

已打开上述OpenAI官方文章与会议日程。Hot Chips全proceedings链接的web获取失败；直接获取会议HTML曾返回HTTP406。STH HTML可读取并提取slide25/29/30的图片URL，但web image open返回non-retryable safe-open错误，未绕过下载来展示。TechInsights全文获取失败；USPTO原文403。将这些“未读到”明确保留，避免把本轮覆盖误说成完整工业披露审计。
