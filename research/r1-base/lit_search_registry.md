# TARS NPU / LLM 软硬协同研究：可审计学术检索登记

检索日期：2026-09-01（Asia/Shanghai）

实体范围：仅 `publication`；未检索 trial。

用途：为五个候选专利/论文方向建立先行研究池和可核验引用集。本登记不是专利新颖性/FTO 检索，也不把“检索未命中”解释为“没有相关工作”。

## 1. 边界、方法与状态词

- 主题：
  1. 3D/2.5D/chiplet/stacked-memory-aware mapping and scheduling；
  2. 面向可配置加速器的软硬件协同；
  3. on-chip scratchpad/VMEM banking、placement、lifetime 与 double buffering；
  4. Descriptor/command stream、访问-执行解耦、数据搬运与同步；
  5. LLM 融合、特殊函数/向量通路与自适应精度执行。
- 纳入：体系结构、EDA、编译映射、加速器、片上存储、Transformer/LLM 硬件论文；接受预印本，但必须明确标注。
- 排除：仅讨论通用软件优化且没有硬件执行机制的工作；与主题无关的同名论文；Crossref 返回的视频/补充材料 DOI；trial。
- `核心·已核验`：已调用 `get_paper_by_id`，并通过 `expected` 对题名、`authors[0]`、年份、venue（arXiv 条目无 venue）及 DOI/arXiv ID 做字段级核验，状态为 `verified`。
- `正式论文候选·未逐条核验`：检索得到 DOI/正式 venue，但没有进入本轮核心逐条核验集。
- `预印本候选`：仅以 arXiv 记录纳入；不能表述成同行评审论文。
- 相关性排序仅用于初筛，不代表证据质量、影响力或新颖性。

TARS 对接基线采用当前仓库可见的实际对象：Descriptor 0x8 的 FAMILY/BUFFER 分工，DDR → VMEM → TMU/MXU 数据路径，以及 connected Controller/RTL 中每核 4 MiB、22-bit、8-bank VMEM。它们只是研究问题的锚点，不自动证明某个新方案已被 active authority、Controller、RTL 或 Hardware Admission 接受。

## 2. 检索运行审计

### 2.1 `search_papers` MCP 故障与同版本回退

直接调用 `mcp__nature_academic_search__search_papers` 时，以下调用均在产生 `search_run` 之前失败：

- 显式四源：`crossref, arxiv, openalex, semantic_scholar`；
- 默认 publication 源；
- Crossref、OpenAlex、arXiv、Semantic Scholar 四次单源探针。

共同错误为：`Search failed: asyncio.run() cannot be called from a running event loop`。因为没有生成 `search_run`，这些失败调用不能声称任何 source 已被实际查询。随后使用同一插件、同一版本 `nature-academic-search==0.3.0` 的官方 `workflow run --approve` 路径完成发现与去重；核心记录仍全部通过 MCP `get_paper_by_id + expected` 核验。

### 2.2 十次成功的 publication 检索

第一轮是宽检索，尝试 Crossref、arXiv、OpenAlex、Semantic Scholar；第二轮是针对经典工作的 Crossref + arXiv 定向检索。所有 `sources_skipped=[]`。

| 运行 | 查询摘要 | `search_run.run_id` / UTC | 原始→去重 | `sources_queried` | `sources_succeeded` | `sources_skipped` | `errors` |
|---|---|---|---:|---|---|---|---|
| 1 | 3D stacked / HBM / chiplet / mapping | `4bd62402-09c0-4284-b3a5-d755b7d3885b` / `2026-09-01T08:54:00.819712Z` | 20→20 | Crossref, arXiv, OpenAlex, Semantic Scholar | Crossref, arXiv | [] | OpenAlex 429；Semantic Scholar 429 |
| 2 | reconfigurable accelerator / compiler-architecture co-design | `2fdaf02b-db66-4d36-bf8a-27b7cae221b2` / `2026-09-01T08:53:59.120739Z` | 20→19 | Crossref, arXiv, OpenAlex, Semantic Scholar | Crossref, arXiv | [] | OpenAlex 429；Semantic Scholar 429 |
| 3 | scratchpad / bank / lifetime / double buffer | `7143094a-5e5c-4fb6-a034-0c1a301f97d4` / `2026-09-01T08:53:57.692581Z` | 20→20 | Crossref, arXiv, OpenAlex, Semantic Scholar | Crossref, arXiv | [] | OpenAlex 429；Semantic Scholar 429 |
| 4 | descriptor / command / DAE / DMA / synchronization | `73f0bddc-3c39-4ee9-8818-366705999c14` / `2026-09-01T08:53:59.839455Z` | 20→19 | Crossref, arXiv, OpenAlex, Semantic Scholar | Crossref | [] | arXiv 429；OpenAlex 429；Semantic Scholar 429 |
| 5 | LLM fusion / Softmax / Norm / RoPE / precision | `6b13b0c5-c983-4e71-b477-bd44b23c16db` / `2026-09-01T08:53:59.895796Z` | 20→20 | Crossref, arXiv, OpenAlex, Semantic Scholar | Crossref, arXiv | [] | OpenAlex 429；Semantic Scholar malformed response |
| 1b | TETRIS / Neurocube / Simba 定向补检 | `e4e31f4a-373b-4b6c-a9f7-04061b1ad01a` / `2026-09-01T08:56:59.809368Z` | 20→20 | Crossref, arXiv | Crossref, arXiv | [] | 无 |
| 2b | MAERI / Eyeriss v2 / Gemmini / Timeloop 定向补检 | `3cb1dadc-e932-419f-8d83-caba86f7a965` / `2026-09-01T08:56:59.076375Z` | 20→19 | Crossref, arXiv | Crossref, arXiv | [] | 无 |
| 3b | CoSA / Marvel / Interstellar / ZigZag / LOMA 定向补检 | `58702bb2-bef9-45b4-9188-4002ff4618cc` / `2026-09-01T08:57:00.971613Z` | 20→20 | Crossref, arXiv | Crossref, arXiv | [] | 无 |
| 4b | VTA / Gemmini / Cambricon / DMA / token 定向补检 | `198087e3-f639-4b2a-8707-d5451717f9e8` / `2026-09-01T08:56:59.122107Z` | 20→20 | Crossref, arXiv | Crossref, arXiv | [] | 无 |
| 5b | Softermax / FlashAttention / SpAtten / Sanger / ELSA 定向补检 | `f0790dca-ae13-44a5-b671-9221674d1bf9` / `2026-09-01T08:56:59.688551Z` | 20→19 | Crossref, arXiv | Crossref, arXiv | [] | 无 |

结果指纹：

- 1 `sha256:361a0b24dd78eb2a91472d57af5a58542c41fe94c6908bdc59d769ceaae7b98d`
- 2 `sha256:9134904e61974edccf689bbbdf020a48ab33e6fd06936f6c99e4f7c7e264cf3f`
- 3 `sha256:06ef31f258d852eeedba01ec64d4b8f1ca657e8cb49fc7ec272be4fc01125cb0`
- 4 `sha256:949f0fc2345926015e0eeec24dacc55a7ad1b435e9779fcccf22b9f54402616b`
- 5 `sha256:f587f1d11cf3af4ba86c04e923a52eec2eb87dd81428a5ef03789769471c2caa`
- 1b `sha256:31eef05c2be856aed371f53add02f0dcf2e596901ad581c0064a894cbba9e1c6`
- 2b `sha256:835a8921d54dc84f20d0d94f7f038c2819c4dc60a9116074dbad17677419ce5e`
- 3b `sha256:c4dde461c24b94a102de63c9be6b648bcfdf44899dae08ca970f11e4d4796d50`
- 4b `sha256:08b450dde91b2140f13951ce505fa5c52aadcee2cf4ced23c8463c95d2768017`
- 5b `sha256:d0222a4ce1f713bcef9e5d4181b32a9e7fcafaacd73f7cbd74c7b9696bf7839e`

OpenAlex 与 Semantic Scholar 的失败是限流/响应错误，不是“零结果”。第二轮只重试已成功且最有产出的 Crossref、arXiv。PubMed 与 Europe PMC 不适合本体系结构主题，未被本轮显式请求。Google Scholar、Web of Science、Scopus、CNKI、万方未连接，不能声称覆盖。

## 3. 方向一：3D/HBM/Chiplet 感知的 Descriptor 映射与热-带宽协同调度

**研究命题。** 让硬件公开 HBM channel/vault、chiplet/NoP、带宽、功耗与热预算；llmSched 同时选择 DDR 分布、BUFFER subgraph 搬运、core/chiplet 放置和 FAMILY tile 顺序；Controller 依据 Descriptor 中的放置类别与 credit 执行。硬件创新不只是“用了 HBM”，而是 channel-local DMA/near-data compute、热/带宽计数器及可验证的映射约束。

**TARS 端到端锚点。** 以一个 Gemma4 GEMM 为例：完整 DDR tensor 按 channel 着色 → BUFFER 把当前 subgraph 搬入 core-local VMEM → FAMILY 在 VMEM 内选 tile → MXU 执行；新方案只改变放置/调度和硬件通道选择，不把 DDR stride 误当 tile stride。

### 候选池（11，含 5 个已核验核心）

| 状态 | 文献 | 年份 | 标识符/来源 | 对 TARS 的直接价值 |
|---|---|---:|---|---|
| 核心·已核验·同行评审 | TETRIS: Scalable and Efficient Neural Network Acceleration with 3D Memory | 2017 | [DOI](https://doi.org/10.1145/3037697.3037702) | 3D memory 与 NN 数据流/分区联合设计基线；可对照 TARS 的 BUFFER/FAMILY 两级调度。 |
| 核心·已核验·同行评审 | Neurocube: A Programmable Digital Neuromorphic Architecture with High-Density 3D Memory | 2016 | [DOI](https://doi.org/10.1109/ISCA.2016.41) | vault/logic-layer 计算与高密度 3D memory 的组织方式。 |
| 核心·已核验·同行评审 | Simba: Scaling Deep-Learning Inference with Multi-Chip-Module-Based Architecture | 2019 | [DOI](https://doi.org/10.1145/3352460.3358302) | 36-chiplet MCM、分布式存储与层映射；适合作为 TARS 多核/未来 chiplet 扩展基线。 |
| 核心·已核验·同行评审 | Hardware-Software Co-Design of a Collaborative DNN Accelerator for 3D Stacked Memories with Multi-Channel Data | 2024 | [DOI](https://doi.org/10.1109/ASP-DAC58780.2024.10473935) | HBM3 logic-layer 的带宽、面积、功耗/热约束协同探索。 |
| 核心·已核验·同行评审 | Multi-Objective Hardware-Mapping Co-Optimisation for Multi-DNN Workloads on Chiplet-Based Accelerators | 2024 | [DOI](https://doi.org/10.1109/TC.2024.3386067) | chiplet、NoP、层映射、能耗/时延/面积 Pareto 联合搜索。 |
| 正式论文候选·未逐条核验 | Hybrid compile and run-time memory management for a 3D-stacked reconfigurable accelerator | 2013 | [DOI](https://doi.org/10.1109/CASES.2013.6662514) | 编译期与运行期共同管理 3D-stack memory，是动态拥塞/热反馈的早期参照。 |
| 正式论文候选·未逐条核验 | SPACX: Silicon Photonics-based Scalable Chiplet Accelerator for DNN Inference | 2022 | [DOI](https://doi.org/10.1109/HPCA53966.2022.00066) | chiplet scale-out 与互连代价建模。 |
| 预印本候选 | Gemini: Mapping and Architecture Co-exploration for Large-scale DNN Chiplet Accelerators | 2023 | [arXiv:2312.16436](https://arxiv.org/abs/2312.16436) | architecture-mapping co-exploration；可比较 TARS 的静态 profile 与候选硬件参数联合搜索。 |
| 预印本候选 | Dataflow-Architecture Co-Design for 2.5D DNN Accelerators using Wireless Network-on-Package | 2020 | [arXiv:2011.14755](https://arxiv.org/abs/2011.14755) | 2.5D NoP multicast 与 dataflow 共同设计。 |
| 正式论文候选·未逐条核验 | 3D-PLANE: A 3D-stacked DRAM-based Programmable SLM Accelerator | 2025 | [DOI](https://doi.org/10.1145/3716368.3735285) | 可编程 near-memory 路径及 stack 内数据复用。 |
| 正式论文候选·未逐条核验 | 3D-SubG: A 3D Stacked Hybrid Processing Near/In-Memory Accelerator for Subgraph GNNs | 2025 | [DOI](https://doi.org/10.1109/DAC63849.2025.11132830) | subgraph 粒度的 near/in-memory 分工，可借鉴但工作负载不同。 |

**可辩护空白。** TETRIS/EnX3D 主要优化 CNN/NN 的 3D-memory 资源分配，Simba/MOHaM 主要优化 MCM/chiplet 映射；它们没有覆盖 TARS 这种“DDR Storage View → Descriptor BUFFER subgraph → compact VMEM → FAMILY tile → TMU/MXU”的显式契约，也没有把 Descriptor 版本/执行回执纳入热-带宽闭环。差异化工作应是：**Descriptor 可验证的多通道/多 chiplet placement contract + 硬件 credit/thermal feedback + LLM 异构算子映射**，而不是再次做一般性的 DNN mapping DSE。

**最小实验。** Gemma4 prefill 中 GEMM、Softmax、RMSNorm 混合序列；比较单通道/轮询、仅带宽优化、带宽+热+NoP 联合优化；报告 P99 latency、HBM bytes、NoP hops、峰值温度、能耗、Descriptor 数量及数值一致性。

## 4. 方向二：面向可配置 MXU/TMU/互连的有界重构软硬协同

**研究命题。** 将 TARS 从“固定算子对应固定硬件路径”推进为有界可重构结构：可选择 MXU array partition、数据流、lane grouping、稀疏/稠密模式、精度和 TMU route；编译端对每个 Descriptor profile 选择配置并计入重构代价；硬件端提供可原子切换、可回读的配置 epoch。

**边界。** 本方向优化“结构与数据流配置”，不优化 Softmax/RMSNorm/RoPE 的数值近似；后者留给方向五，避免两个 idea 重复。

### 候选池（11，含 5 个已核验核心）

| 状态 | 文献 | 年份 | 标识符/来源 | 对 TARS 的直接价值 |
|---|---|---:|---|---|
| 核心·已核验·同行评审 | Eyeriss v2: A Flexible Accelerator for Emerging Deep Neural Networks on Mobile Devices | 2019 | [DOI](https://doi.org/10.1109/JETCAS.2019.2910232) | 层次 mesh 与稠密/稀疏 DNN 的灵活映射。 |
| 核心·已核验·同行评审 | MAERI: Enabling Flexible Dataflow Mapping over DNN Accelerators via Reconfigurable Interconnects | 2018 | [DOI](https://doi.org/10.1145/3296957.3173176) | 重构互连支持多种 dataflow，是 MXU/TMU 可配置路由的直接基线。 |
| 核心·已核验·同行评审 | Timeloop: A Systematic Approach to DNN Accelerator Evaluation | 2019 | [DOI](https://doi.org/10.1109/ISPASS.2019.00042) | 体系结构与 mapping 的统一表示、性能/能耗评估。 |
| 核心·已核验·同行评审 | ReAAP: A Reconfigurable and Algorithm-Oriented Array Processor with Compiler-Architecture Co-Design | 2022 | [DOI](https://doi.org/10.1109/TC.2022.3213177) | 编译器-阵列结构协同与算法导向配置。 |
| 核心·已核验·同行评审 | Gemmini: Enabling Systematic Deep-Learning Architecture Evaluation via Full-Stack Integration | 2021 | [DOI](https://doi.org/10.1109/DAC18074.2021.9586216) | 参数化生成器、编程栈、SoC 资源争用与实芯片验证。 |
| 正式论文候选·未逐条核验 | Plasticine: A Reconfigurable Accelerator for Parallel Patterns | 2018 | [DOI](https://doi.org/10.1109/MM.2018.032271058) | 粗粒度可重构数据路径与 pattern 映射。 |
| 正式论文候选·未逐条核验 | Adapt-Flow: A Flexible DNN Accelerator Architecture for Heterogeneous Dataflow Implementation | 2022 | [DOI](https://doi.org/10.1145/3526241.3530311) | 异构 dataflow 在同一加速器中的配置选择。 |
| 正式论文候选·未逐条核验 | Eyeriss: An Energy-Efficient Reconfigurable Accelerator for Deep Convolutional Neural Networks | 2017 | [DOI](https://doi.org/10.1109/JSSC.2016.2616357) | row-stationary 与片上通信/存储权衡的经典实芯片基线。 |
| 正式论文候选·未逐条核验 | Convolutional Neural Network Accelerator with Reconfigurable Dataflow | 2018 | [DOI](https://doi.org/10.1109/ISOCC.2018.8649988) | dataflow 切换的直接硬件实现候选。 |
| 正式论文候选·未逐条核验 | DPSA: A Framework for Dataflow Aware Precision Scalable DNN Accelerator Design | 2023 | [DOI](https://doi.org/10.1109/ICFTIC59930.2023.10455811) | dataflow 与精度扩展共同配置。 |
| 正式论文候选·未逐条核验 | HASS: Hardware-Aware Sparsity Search for Dataflow DNN Accelerator | 2024 | [DOI](https://doi.org/10.1109/FPL64840.2024.00043) | 硬件约束进入稀疏结构搜索。 |

**可辩护空白。** MAERI/Eyeriss/ReAAP 证明“可重构有价值”，Timeloop/Gemmini 提供 DSE/full-stack 方法，但多数围绕 CNN 或通用 tensor array。TARS 可以研究：**同一 Descriptor family 下，硬件 configuration epoch、重构开销、VMEM bank/route 与 LLM operator phase 的联合选择**；配置必须由 profile/version 约束并可 fail-closed，而不是任意 bitstream 或软件提示。

**最小实验。** 固定 Gemma4 一层，依次执行 GEMM → RMSNorm → RoPE → Softmax；比较固定结构、逐 op 贪心配置、计入切换代价的 whole-layer 配置；报告利用率、切换周期/能耗、VMEM traffic、端到端 latency、面积开销和配置一致性错误检测率。

## 5. 方向三：VMEM bank-aware placement、lifetime/reuse 与 double buffering 共优化

**研究命题。** 让 `PhysicalMemoryPlanIR` 不只满足容量与不重叠，还联合选择 base/span、bank color、lifetime、alias/reuse、ping-pong mirror step；硬件提供明确 bank remap/仲裁模型和冲突计数器，Controller 不再重新分配地址。创新点是“静态可证明 placement + 动态 bank evidence”的闭环。

**TARS 端到端锚点。** 对一个 K 分块 GEMM：ACT/WGT ping-pong 与 OUT singleton 在 4 MiB VMEM 中按 lifetime 分配；每个 slot 的地址映射到 8 banks；DMA 搬下一块时 MXU 计算当前块；冲突预测和 RTL counter 必须对同一 Descriptor 地址达成一致。

### 候选池（11，含 5 个已核验核心）

| 状态 | 文献 | 年份 | 标识符/来源 | 对 TARS 的直接价值 |
|---|---|---:|---|---|
| 核心·已核验·同行评审 | LOMA: Fast Auto-Scheduling on DNN Accelerators through Loop-Order-based Memory Allocation | 2021 | [DOI](https://doi.org/10.1109/AICAS51828.2021.9458493) | loop order 与层次 memory allocation 联合搜索。 |
| 核心·已核验·同行评审 | Pin or Fuse? Exploiting Scratchpad Memory to Reduce Off-Chip Data Transfer in DNN Accelerators | 2023 | [DOI](https://doi.org/10.1145/3579990.3580017) | feature-map residency、fusion 与容量约束联合选择。 |
| 核心·已核验·同行评审 | Interstellar: Using Halide's Scheduling Language to Analyze DNN Accelerators | 2020 | [DOI](https://doi.org/10.1145/3373376.3378514) | loop blocking、片上局部性与硬件资源分配的统一描述。 |
| 核心·已核验·同行评审 | ZigZag: Enlarging Joint Architecture-Mapping Design Space Exploration for DNN Accelerators | 2021 | [DOI](https://doi.org/10.1109/TC.2021.3059962) | operand-specific uneven mapping 与 memory hierarchy DSE。 |
| 核心·已核验·同行评审 | DORY: Automatic End-to-End Deployment of Real-World DNNs on Low-Cost IoT MCUs | 2021 | [DOI](https://doi.org/10.1109/TC.2021.3066883) | 显式 DMA、约束求解 tiling 与 double buffering。 |
| 预印本候选 | CoSA: Scheduling by Constrained Optimization for Spatial Accelerators | 2021 | [arXiv:2105.01898](https://arxiv.org/abs/2105.01898) | 将算子/硬件 mapping 表达为可确定求解的约束问题；此处只核算预印本记录。 |
| 预印本候选 | Marvel: A Data-centric Compiler for DNN Operators on Spatial Accelerators | 2020 | [arXiv:2002.07752](https://arxiv.org/abs/2002.07752) | 将 off-chip/on-chip mapping 空间分解，优先降低数据搬运。 |
| 正式论文候选·未逐条核验 | Integrated scratchpad memory optimization and task scheduling for MPSoC architectures | 2006 | [DOI](https://doi.org/10.1145/1176760.1176809) | SPM allocation 与 task schedule 联合优化的经典参照。 |
| 正式论文候选·未逐条核验 | Compiler-Directed Scratchpad Memory Management | 2005 | [DOI](https://doi.org/10.1007/11599555_2) | 编译器显式管理 SPM 的基础工作。 |
| 正式论文候选·未逐条核验 | A Vector-Length Agnostic Compiler for the Connex-S Accelerator with Scratchpad Memory | 2020 | [DOI](https://doi.org/10.1145/3406536) | 向量长度变化下的 scratchpad 编译映射。 |
| 正式论文候选·未逐条核验 | Memory coloring: a compiler approach for scratchpad memory management | 2005 | [DOI](https://doi.org/10.1109/PACT.2005.27) | memory coloring 与 TARS bank color 的概念基线。 |

**可辩护空白。** 现有工作常优化 loop/memory capacity、层融合或一般 SPM 分配，但较少同时要求：一份 workload placement authority 产生 Descriptor BUFFER base、编译时证明 lifetime/alias/bank collision、RTL 用同一 remap 公式执行、运行时 counter 回证。TARS 的差异化创新应是：**Descriptor-bound bank-colored lifetime allocation + ping-pong epoch + hardware conflict receipt**。它与方向一的区别是只研究 core-local VMEM，不研究 HBM/channel/chiplet topology。

**最小实验。** 选 GEMM、Softmax、RMSNorm 三类不同访问模式；比较容量优先、bank-aware、bank+lifetime+double-buffer 三种 planner；报告峰值 live bytes、DDR bytes、bank collision、仲裁等待、DMA/compute overlap、吞吐与数值一致性。

## 6. 方向四：自描述 Descriptor 命令流、解耦 DMA/执行与硬件依赖记分牌

**研究命题。** 将 Descriptor stream 变成硬件可自治执行的任务图：BUFFER 搬运、FAMILY compute、store 各有 task id、依赖 token、credit 与 completion；DMA、TMU、MXU 可乱序准备但按依赖提交；Controller/firmware 只负责队列推进和错误归因。硬件贡献是多队列、scoreboard、credit/back-pressure、completion FIFO 与 Descriptor integrity check。

**TARS 端到端锚点。** `load ACT/WGT → GEMM → store OUT` 三个 Descriptor task：load 与上一 tile 的 compute 重叠；scoreboard 只有在相应 slot/epoch 完成后放行 GEMM；错误回执带 exact task/Descriptor identity，避免依赖全局 barrier 或 CPU polling。

### 候选池（12，含 5 个已核验核心）

| 状态 | 文献 | 年份 | 标识符/来源 | 对 TARS 的直接价值 |
|---|---|---:|---|---|
| 核心·已核验·同行评审 | PISA-DMA: Processing-in-Memory Instruction Set Architecture Using DMA | 2023 | [DOI](https://doi.org/10.1109/ACCESS.2023.3238812) | 用 DMA descriptor 同时表达 opcode/operand 与 descriptor list；和 TARS Descriptor 最直接。 |
| 核心·已核验·同行评审 | A decoupled access-execute architecture for reconfigurable accelerators | 2018 | [DOI](https://doi.org/10.1145/3203217.3203267) | 将 fetch/access plane 与 processing plane 分离。 |
| 核心·已核验·同行评审 | Efficient data supply for hardware accelerators with prefetching and access/execute decoupling | 2016 | [DOI](https://doi.org/10.1109/MICRO.2016.7783749) | 自动 program slicing、prefetch 与 accelerator DAE。 |
| 核心·已核验·同行评审 | Cambricon: An Instruction Set Architecture for Neural Networks | 2016 | [DOI](https://doi.org/10.1109/ISCA.2016.42) | NN ISA 与硬件/编译边界的经典参照。 |
| 核心·已核验·预印本 | A Hardware-Software Blueprint for Flexible Deep Learning Specialization（VTA 技术报告的当前 arXiv 题名） | 2018 | [arXiv:1807.04188](https://arxiv.org/abs/1807.04188) | task-level pipeline、load/compute/store 队列与依赖；只按预印本记录引用。 |
| 正式论文候选·未逐条核验 | Deriving Efficient Data Movement from Decoupled Access/Execute Specifications | 2009 | [DOI](https://doi.org/10.1007/978-3-540-92990-1_14) | 从显式 access/execute 规格导出 DMA、复用与软件流水。 |
| 正式论文候选·未逐条核验 | BAX: A Bundle Adjustment Accelerator With Decoupled Access/Execute Architecture for Visual Odometry | 2020 | [DOI](https://doi.org/10.1109/ACCESS.2020.2988527) | 真实加速器上的 DAE、流式数据供应与专用计算。 |
| 正式论文候选·未逐条核验 | Decoupled Access/Execute Computer Architectures | 1984 | [DOI](https://doi.org/10.1145/357401.357403) | access/execute queue 与同步的体系结构源头。 |
| 正式论文候选·未逐条核验 | DianNao: A Small-Footprint High-Throughput Accelerator for Ubiquitous Machine-Learning | 2014 | [DOI](https://doi.org/10.1145/2541940.2541967) | 专用加速器指令/缓冲/控制的对照基线。 |
| 预印本候选 | XDMA: A Distributed, Extensible DMA Architecture for Layout-Flexible Data Movements in Heterogeneous Multi-Accelerator SoCs | 2025 | [arXiv:2508.08396](https://arxiv.org/abs/2508.08396) | 分布式 DMA、硬件 address generation 与搬运中 layout transform。 |
| 正式论文候选·未逐条核验 | AExec: Asynchronous Multi-accelerator Execution and Management Mechanism | 2026 | [DOI](https://doi.org/10.1145/3801487.3801807) | 非阻塞 launch、completion queue 与多加速器异步管理。 |
| 正式论文候选·未逐条核验 | Compiler Support for Speculation in Decoupled Access/Execute Architectures | 2025 | [DOI](https://doi.org/10.1145/3708493.3712695) | DAE 中推测、依赖和回退路径。 |

**可辩护空白。** PISA-DMA 关注 PIM opcode 进入 DMA descriptor，VTA/DAE 关注 load-compute-store 解耦，Cambricon 关注 NN ISA；尚未覆盖 TARS 的多 record Descriptor、BUFFER/FAMILY 所有权、VMEM slot/epoch、版本化 release identity 与 completion receipt 的组合。差异化主张应落在：**Descriptor identity 驱动的硬件 scoreboard + slot/epoch hazard checking + 异步 completion/error receipt**，而不是泛化地提出“命令队列”或“DMA 与计算重叠”。

**最小实验。** 以连续 16 个 GEMM K-tile 的 load/compute/store 为主例；比较全局 barrier、双队列、带 task-id/credit/scoreboard 的三种硬件；故意注入 stale epoch、DMA fault、队列 back-pressure，测吞吐、控制开销、错误定位精度和无死锁性质。

## 7. 方向五：LLM 非线性算子融合、共享特殊函数通路与误差受控自适应精度

**研究命题。** 为 Softmax/LayerNorm/RMSNorm/RoPE/GEGLU 构建共享 reduction + LUT/PWL + reciprocal/rsqrt + vector permute 通路；编译端根据 shape、数值范围与精度预算选择 exact/approx mode、tile fusion 和 FP16/BF16/INT/mixed precision；Descriptor 固化 mode 与误差契约，硬件返回 saturation/iteration/error 观测。

**边界。** 本方向优化 LLM 非线性数值路径、融合和误差保证；不改变 MXU/TMU 总体互连/阵列拓扑，避免与方向二重复。

### 候选池（14，含 6 个已核验核心）

| 状态 | 文献 | 年份 | 标识符/来源 | 对 TARS 的直接价值 |
|---|---|---:|---|---|
| 核心·已核验·同行评审 | Softermax: Hardware/Software Co-Design of an Efficient Softmax for Transformers | 2021 | [DOI](https://doi.org/10.1109/DAC18074.2021.9586134) | Softmax 数值变换与硬件实现协同，是 TMU 特殊函数路径的核心基线。 |
| 核心·已核验·同行评审 | ITA: An Energy-Efficient Attention and Softmax Accelerator for Quantized Transformers | 2023 | [DOI](https://doi.org/10.1109/ISLPED58423.2023.10244348) | quantized attention/Softmax 的共享数据路径与能效。 |
| 核心·已核验·同行评审 | SpAtten: Efficient Sparse Attention Architecture with Cascade Token and Head Pruning | 2021 | [DOI](https://doi.org/10.1109/HPCA51647.2021.00018) | 输入相关 pruning、progressive quantization 和专用 top-k 硬件。 |
| 核心·已核验·同行评审 | Sanger: A Co-Design Framework for Enabling Sparse Attention using Reconfigurable Architecture | 2021 | [DOI](https://doi.org/10.1145/3466752.3480125) | 稀疏 attention 模式与可重构架构协同。 |
| 核心·已核验·同行评审 | ELSA: Hardware-Software Co-design for Efficient, Lightweight Self-Attention Mechanism in Neural Networks | 2021 | [DOI](https://doi.org/10.1109/ISCA52012.2021.00060) | self-attention 的算法-硬件近似协同及精度/能效权衡。 |
| 核心·已核验·预印本记录 | FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness | 2022 | [arXiv:2205.14135](https://arxiv.org/abs/2205.14135) | exact online Softmax、SRAM/HBM tiling 与 fusion；本登记核验的是 arXiv 记录，论文另有 NeurIPS 2022 版本。 |
| 正式论文候选·未逐条核验 | ULSeq-TA: Ultra-Long Sequence Attention Fusion Transformer Accelerator Supporting Grouped Sparse Softmax and Dual-Path Sparse LayerNorm | 2024 | [DOI](https://doi.org/10.1109/TCAD.2023.3329039) | Softmax/LayerNorm 双路径与长序列融合。 |
| 正式论文候选·未逐条核验 | A3: Accelerating Attention Mechanisms in Neural Networks with Approximation | 2020 | [DOI](https://doi.org/10.1109/HPCA47549.2020.00035) | attention approximation + ASIC，是误差受控模式的基线。 |
| 正式论文候选·未逐条核验 | SALO: An Efficient Spatial Accelerator Enabling Hybrid Sparse Attention Mechanisms for Long Sequences | 2022 | [DOI](https://doi.org/10.1145/3489517.3530504) | 长序列 sparse attention 的空间映射。 |
| 正式论文候选·未逐条核验 | RoPIM: A Processing-in-Memory Architecture for Accelerating Rotary Positional Embedding in Transformer Models | 2025 | [DOI](https://doi.org/10.1109/LCA.2025.3535470) | RoPE 专用 bank/row mapping、数据重排与 MAC；和 TARS RoPE family 直接相关。 |
| 预印本候选 | SOLE: Hardware-Software Co-design of Softmax and LayerNorm for Efficient Transformer Inference | 2025 | [arXiv:2510.17189](https://arxiv.org/abs/2510.17189) | Softmax 与 LayerNorm 共享/协同近似；明确为预印本。 |
| 正式论文候选·未逐条核验 | LightningRMS: A High-Throughput Mixed-Precision RMSNorm Accelerator for Transformer Inference | 2026 | [DOI](https://doi.org/10.1145/3787109.3815212) | RMSNorm 专用 mixed-precision 路径；与 TARS RMSNorm family 直接相关。 |
| 正式论文候选·未逐条核验 | AO-BFP: An Adaptive Mixed-Precision and Outlier-Aware Block Floating-Point Accelerator for Large Language Model Inference | 2026 | [DOI](https://doi.org/10.23919/DATE69613.2026.11539329) | 输入/离群值感知的动态精度硬件。 |
| 预印本候选 | Efficient Matrix Implementation for Rotary Position Embedding（RoME） | 2026 | [arXiv:2604.09742](https://arxiv.org/abs/2604.09742) | 把 RoPE 重写成统一 matrix transform，利于 Cube/MXU 与 vector/TMU 融合；明确为预印本。 |

**可辩护空白。** Softermax/ITA 多聚焦 Softmax，SpAtten/Sanger/ELSA 聚焦 attention 稀疏或近似，FlashAttention 聚焦 GPU IO-aware exact kernel，RoPIM/LightningRMS 又分别只覆盖 RoPE/RMSNorm。TARS 可形成不同贡献：**一个 Descriptor-controlled、跨 Softmax/RMSNorm/RoPE 的共享特殊函数通路；编译端联合决定 fusion、精度和近似参数；硬件给出可核查的数值/饱和观测**。专利点应落在共享 datapath、mode transition、误差预算传播和 Descriptor 硬件执行的组合，而不是单独声称 PWL/LUT 或 operator fusion。

**最小实验。** Gemma4 attention block：Q/K RMSNorm → RoPE → QK GEMM → Softmax → AV GEMM；比较逐 op DDR round-trip、VMEM-resident exact fusion、误差受控 mixed-precision fusion；报告端到端 latency/energy、VMEM/DDR bytes、面积、SFU 利用率、最大/平均数值误差及模型任务指标。

## 8. 核心记录的 MCP 字段核验总表

以下 26 条均实际调用了 `mcp__nature_academic_search__get_paper_by_id` 且传入 `expected`。DOI 条目核验字段为 `title + authors[0] + year + journal + doi`；arXiv 条目为 `title + authors[0] + year + arxiv_id`。所有列出的字段均为 `match`，总状态均为 `verified`。

> Crossref 对 TETRIS、Simba、MAERI、Interstellar 的 `title` 字段只返回简称；MCP 核验使用其 registry 简称，正文展示的完整标题由论文官方页面补足。不能把这个字段级限制隐去。

| 方向 | ID | MCP 返回题名 | 首位作者 | 年份 | 核验状态 |
|---:|---|---|---|---:|---|
| 1 | `10.1145/3037697.3037702` | TETRIS | Mingyu Gao | 2017 | verified |
| 1 | `10.1109/ISCA.2016.41` | Neurocube: A Programmable Digital Neuromorphic Architecture with High-Density 3D Memory | Duckhwan Kim | 2016 | verified |
| 1 | `10.1145/3352460.3358302` | Simba | Yakun Sophia Shao | 2019 | verified |
| 1 | `10.1109/ASP-DAC58780.2024.10473935` | Hardware-Software Co-Design of a Collaborative DNN Accelerator for 3D Stacked Memories with Multi-Channel Data | Tom Glint | 2024 | verified |
| 1 | `10.1109/TC.2024.3386067` | Multi-Objective Hardware-Mapping Co-Optimisation for Multi-DNN Workloads on Chiplet-Based Accelerators | Abhijit Das | 2024 | verified |
| 2 | `10.1109/JETCAS.2019.2910232` | Eyeriss v2: A Flexible Accelerator for Emerging Deep Neural Networks on Mobile Devices | Yu-Hsin Chen | 2019 | verified |
| 2 | `10.1145/3296957.3173176` | MAERI | Hyoukjun Kwon | 2018 | verified |
| 2 | `10.1109/ISPASS.2019.00042` | Timeloop: A Systematic Approach to DNN Accelerator Evaluation | Angshuman Parashar | 2019 | verified |
| 2 | `10.1109/TC.2022.3213177` | ReAAP: A Reconfigurable and Algorithm-Oriented Array Processor with Compiler-Architecture Co-Design | Jianwei Zheng | 2022 | verified |
| 2 | `10.1109/DAC18074.2021.9586216` | Gemmini: Enabling Systematic Deep-Learning Architecture Evaluation via Full-Stack Integration | Hasan Genc | 2021 | verified |
| 3 | `10.1109/AICAS51828.2021.9458493` | LOMA: Fast Auto-Scheduling on DNN Accelerators through Loop-Order-based Memory Allocation | Arne Symons | 2021 | verified |
| 3 | `10.1145/3579990.3580017` | Pin or Fuse? Exploiting Scratchpad Memory to Reduce Off-Chip Data Transfer in DNN Accelerators | Hyuk-Jin Jeong | 2023 | verified |
| 3 | `10.1145/3373376.3378514` | Interstellar | Xuan Yang | 2020 | verified |
| 3 | `10.1109/TC.2021.3059962` | ZigZag: Enlarging Joint Architecture-Mapping Design Space Exploration for DNN Accelerators | Linyan Mei | 2021 | verified |
| 3 | `10.1109/TC.2021.3066883` | DORY: Automatic End-to-End Deployment of Real-World DNNs on Low-Cost IoT MCUs | Alessio Burrello | 2021 | verified |
| 4 | `10.1109/ACCESS.2023.3238812` | PISA-DMA: Processing-in-Memory Instruction Set Architecture Using DMA | Won Jun Lee | 2023 | verified |
| 4 | `10.1145/3203217.3203267` | A decoupled access-execute architecture for reconfigurable accelerators | George Charitopoulos | 2018 | verified |
| 4 | `10.1109/MICRO.2016.7783749` | Efficient data supply for hardware accelerators with prefetching and access/execute decoupling | Tao Chen | 2016 | verified |
| 4 | `10.1109/ISCA.2016.42` | Cambricon: An Instruction Set Architecture for Neural Networks | Shaoli Liu | 2016 | verified |
| 4 | `arXiv:1807.04188` | A Hardware-Software Blueprint for Flexible Deep Learning Specialization | Thierry Moreau | 2018 | verified（预印本） |
| 5 | `10.1109/DAC18074.2021.9586134` | Softermax: Hardware/Software Co-Design of an Efficient Softmax for Transformers | Jacob R. Stevens | 2021 | verified |
| 5 | `10.1109/ISLPED58423.2023.10244348` | ITA: An Energy-Efficient Attention and Softmax Accelerator for Quantized Transformers | Gamze Islamoglu | 2023 | verified |
| 5 | `10.1109/HPCA51647.2021.00018` | SpAtten: Efficient Sparse Attention Architecture with Cascade Token and Head Pruning | Hanrui Wang | 2021 | verified |
| 5 | `10.1145/3466752.3480125` | Sanger: A Co-Design Framework for Enabling Sparse Attention using Reconfigurable Architecture | Liqiang Lu | 2021 | verified |
| 5 | `10.1109/ISCA52012.2021.00060` | ELSA: Hardware-Software Co-design for Efficient, Lightweight Self-Attention Mechanism in Neural Networks | Tae Jun Ham | 2021 | verified |
| 5 | `arXiv:2205.14135` | FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness | Tri Dao | 2022 | verified（预印本记录） |

核验结果分组：`verified=26`，`mismatch=0`，`not_found=0`，`manual_needed=0`。工作流自动生成的候选级 `verification.json` 因 `workflow_lookup_not_configured` 将非核心候选标为 `manual_needed`；本登记没有把这些候选伪装成已核验引用。

## 9. 不计入 publication 数量的官方技术/项目资料

这些页面用于理解实现或核对论文全名，不替代论文元数据，也不计入每方向的候选数量：

- TETRIS 作者项目页（官方学术主页）：[Stanford MAST Lab](https://mast.stanford.edu/pubs/tetris_scalable_and_efficient_neural_network_acceleration_with_3d_memory/)
- Simba 作者项目页（官方研究页面）：[NVIDIA Research](https://research.nvidia.com/publication/2019-10_simba-scaling-deep-learning-inference-multi-chip-module-based-architecture)
- Gemmini 官方代码与引用说明：[ucb-bar/gemmini](https://github.com/ucb-bar/gemmini)
- VTA 官方发布说明：[Apache TVM VTA announcement](https://tvm.apache.org/2018/07/12/vta-release-announcement.html)
- ZigZag 官方 publication 索引：[ZigZag documentation](https://kuleuven-micas.github.io/zigzag/publications.html)
- SpAtten 官方项目页：[MIT HAN Lab](https://hanlab.mit.edu/projects/spatten)
- RoPIM 作者项目页：[Yonsei CASLAB](https://caslab-yonsei.github.io/publications/cal25-yjeon/)
- FlashAttention 官方实现：[Dao-AILab/flash-attention](https://github.com/Dao-AILab/flash-attention)

## 10. 下一步检索缺口

1. **专利/FTO。** 当前只有论文与官方技术资料，不能用于判定专利可申请性；需对 CNIPA、Google Patents、Espacenet、WIPO 按五个具体 claim 组合另做专利族/权利要求检索。
2. **失败源重试。** OpenAlex、Semantic Scholar 遭 429/坏响应；应在限流恢复后按已记录 query 单源重试，并只富化带 DOI/arXiv 强标识符的记录。
3. **机构数据库。** Web of Science、Scopus、IEEE Xplore 全文检索、ACM DL 高级检索、CNKI/万方未连接；正式综述或查新需要人工/机构账户补检。
4. **全文证据。** 当前核心条目完成的是书目身份核验，不等于全文结论复核。进入最终论文 related work 或专利说明书前，需逐篇读取方法、硬件参数、评价 workload 和 limitations，形成 claim-to-prior-art 对照矩阵。
5. **TARS 实测。** 上述五个方向都是研究提案，不是当前实现事实；最终选题前应从同一 Gemma4 layer 获取 baseline 的 Descriptor trace、DDR/VMEM traffic、bank conflict、TMU/MXU utilization、Controller stall 与数值误差，确认问题确实存在且足够大。