# R8 来源审计：两核 cluster 到最小多 cluster 合同

日期：2026-09-05。范围：只读 R1/R3/R5/R6 历史材料，核对少量官方来源，形成 R8 合同输入；没有执行 TARS/Phoenix kernel，没有修改旧轮文件。本文是来源与结构审计，不是校准性能结果。

**决定：Accept 有来源的工作量与依赖账本作为下一步；Refine 当前目标合同；不据此提出 scheduler、直连或 chiplet。** 当前能证实的是历史 TARS 单 cluster 双核记录、固定 Qwen FFN 的数学结构，以及 R8 可检查的有限合同。不能证实当前 TARS 已实现多 cluster、跨 cluster payload/完成协议，或静态优化后的真实损失。

## 1. 标签与来源优先级

| 标签 | 精确含义 |
| --- | --- |
| **H：历史实现记录** | R1 在 2026-09-01 对原 checkout 的源码/typed authority/连接 RTL 审计。本文当前重读了这份记录，但没有重新打开原 checkout；R1 的 [I]/[A] 不升级为当前设备事实。 |
| **V：当前核验** | 本次实际读到的本地冻结源、hash 匹配、固定官方网页内容。只覆盖所读对象；源码形状不代表目标执行许可。 |
| **E：外部规则** | 官方软件/协议文档在其自身平台的规定，只用于提醒必须明确的合同字段，不继承其性能、硬件行为或 API 到 TARS。 |
| **R：研究假设** | R8 主动选择的实验边界、拓扑、数值形式、布局与事件不变量；可做结构验证，尚无目标 admission 或校准。 |

来源顺序为：当前目标活动输入与 connected RTL（本次缺失）→ 冻结历史源码审计 H → 固定官方工作量源 V → 外部规则 E → 显式假设 R。根 [进度表](D:/dsh-proj/SchedResarch/research_progress.md:5) 与 [交接范围](D:/dsh-proj/SchedResarch/r8/continuation_brief.md:7) 已明确这个边界。旧 R1 的 remapper/3D/lease/fabric 排名不是本轮优先级。

## 2. TARS 来源账本与不能填成事实的空白

以下代码路径与行号是 **R1 冻结记录中的原 checkout 相对定位**，用于取得当前根后精确复核；本报告不伪造这些缺失文件的当前绝对链接。

| 对象 | H：历史内容与原始定位 | R8 必须显式化 / 当前未知 | 可点击历史证据 |
| --- | --- | --- | --- |
| cluster/core 归属 | `hardware_specs/tars/target_hardware_spec.yaml:6–39`：1 cluster、2 core；每核 MXU/VPU/TMU/VMEM，cluster 共享 DMA/Controller。 | 当前 topology、实例 ID、共享范围是否改变。多 cluster 是待建合同。 | [live:59](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:59) |
| per-core compute | MXU `modules/mxu.yaml:3–32`：32×32 WS、accumulator depth 64、M/N/K 为 32 倍数。TMU 3 个 64B 端口、7-D AGU/backpressure。 | BF16 输入、FP32 partial/累加/导出许可，实际 reduction tree、M=1 padding 与可用 kernel；不能以几何一致代替许可。 | [live:60](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:60)、[live:131](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:131) |
| per-core VMEM | `modules/vmem.yaml:3–97`：4 MiB、8 banks/4 pairs，ACT/WGT/OUT 为 64B pair，PARAM/DMA 为 32B single-bank。 | 可访问容量、保留区、pair/remap、读写端口与冲突代价；没有来源可把它变成 cluster 共享 SRAM。 | [live:79](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:79) |
| VMEM 容量冲突 | typed data `[0,0x3FF000)`；connected Controller 排除最后 64 KiB，使用 `[0,0x3F0000)`；Wayfinder 第三套区间是规划。 | 先取得唯一活动容量/保护区，不能挑最大区间；用较小交集只能是保守研究容量，不能修复原 authority。 | [live:89](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:89) |
| cluster DMA | `modules/dma.yaml:3–27`：1 channel/1 outstanding、32B beat、12.8 Gbps、`supports_inter_core=false`。 | 这些是历史参数，不是有效实测带宽。多个 cluster 的 DMA 是否共用外存端口、读写服务/队列与实际 accepted/completed bytes 均缺。 | [five:31](D:/dsh-proj/SchedResarch/r1-base/five_directions.md:31)、[live:211](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:211) |
| core link / payload | target link 仅 synchronization；movement route 词汇有 local VMEM/shared DMA/DDR，名称中出现 `direct_core_link` 不等于 target 有 payload link。 | 每个跨域 tensor 必须有实际 route。经 DDR 物化是可选研究路线；跨 cluster DDR 可寻址、完成与可见性仍待目标核验。 | [live:32](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:32)、[five:303](D:/dsh-proj/SchedResarch/r1-base/five_directions.md:303) |
| topology 扩展 | schema 容器可描述多个 cluster；public chain 显式 defer `multi_cluster_scheduling`；root 模块无 NoC/SDMA/3D/NUMA。 | schema 能装多个 ID 不证明 graph repartition、route、launch、credit 或完成通路已实现。 | [live:70](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:70) |
| payload/materialization | StreamTensor 分离 DDR backing stride、compact VMEM、FAMILY tile；RoPE/PARAM readiness 与独立 preprocessor 尚有 join 缺口。 | payload hash、shape/dtype/layout、实际 span/传输长度、生成完成与 launch admission 要逐项关联；地址存在不证明 bytes 到位。 | [five:76](D:/dsh-proj/SchedResarch/r1-base/five_directions.md:76)、[live:162](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:162) |
| residency/reuse | generic lifetime-aware first-fit、K-step modulo-2 ping/pong 已记录；bank separation advisory；mirror/epoch/bank search 仍规划。 | 核间/跨 kernel 可持久性、全部 reader 集合、workspace 与其他层存活量、spill、outstanding read 释放点。旧总序 lifetime 不能直接许可新次序。 | [live:84](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:84)、[contract:98](D:/dsh-proj/SchedResarch/analysis/compiler_contract_requirements.md:98) |
| dependencies | MovementSync 输出 availability/residency/reuse/static-deadlock evidence；task sync 硬编码 `(0,1)`、occurrence refs。 | 分开 RAW、WAR/WAW、数值顺序与目标可见边；共享资源容量约束不是一条必需语义总序。 | [live:120](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:120)、[audit:106](D:/dsh-proj/SchedResarch/analysis/r1_r2_audit.md:106) |
| completion / queues | Controller 队头等待 DEP、执行后 SIGNAL/推进；0x8 最多39×64-bit words，5 BUFFER slots。typed 64 entries 与 RTL 4096B 限制不等价。 | `accepted`、`source-read-done`、`store-visible`、`destination-visible`、`consumer-final-read-done` 分别绑定谁/哪份 bytes。旧 SIGNAL 没有已证明的跨 cluster 可见性语义。 | [live:112](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:112)、[live:119](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:119)、[live:125](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:125) |
| authority / telemetry | Compiler 已分配地址，Controller/reference/RTL 仍重算 sublayer/VMEM；strategy 不是 latency model，contention uncalibrated；busy/bytes/stall 输入接0。 | 同一计划的实际地址/数值/trace agreement；真实 bytes、compute-active、服务/等待分解、频率与仪表开销。 | [live:35](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:35)、[live:152](D:/dsh-proj/SchedResarch/r1-base/live_evidence_audit.md:152) |

**H/R：没有理由从上述记录推出“当前 compiler 已充分优化”。** 历史静态实现候选浅、first-fit/固定双缓冲，且执行端重新规划；strong-static 是 R8 要建立并独立核验的基线。[历史局限](D:/dsh-proj/SchedResarch/analysis/r1_r2_audit.md:68)

## 3. 当前 TARS 精确缺失入口

**V：本次在指定历史文档中只找到原项目相对结构，没有找到已认证的绝对 TARS 顶层根。** 不扫描整盘，不重跑另一 compiler。R6 的 `D:/workspace/llmSched` 是旧离线 compiler，`D:/workspace/riscv_npu_alias` 仅文档；二者不能补 TARS 证据。[R6 边界](D:/dsh-proj/SchedResarch/r6/experiment_report.md:27)、[交接](D:/dsh-proj/SchedResarch/r8/continuation_brief.md:33)

所需最少外部信息是一项：**当前权威 TARS 顶层 checkout 路径（其下应包含 hardware_specs/tars 与 external/tars-npu-ctrl）**。取得后可自行读取下列精确项目，不要求用户手工整理全部合同：

1. 根身份/commit/dirty 状态、`hardware_specs/tars/target_hardware_spec.yaml` 及 `modules/{mxu,vpu,tmu,vmem,dma,controller}.yaml`。
2. `inputs/descriptor_releases/active-release.json` 及其指向的 authority/wire；`src/llmSched/src/llm_sched/orchestrator/authority_chain_constants.py`、`public_authority_chain.py`。
3. `_physical_memory.py`、`_movement_sync.py`、`_core_execution.py`、`task_synchronization.py`；确认新的 mapping、跨域 route 和数值许可是否真实进入公共链。
4. `external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_controller.sv`、`rtl/top/tars_npu_core_top.sv` 与 reference planner；确认实际 connected top、地址 owner、参数、完成语义、计数器连接，再读其已有最小 testbench/运行入口。

原 R1 记录没有当前 revision/连接配置的授权性保证；根存在仍不足以认证全部接口。若未取得入口，继续以下 R 工作，停止目标硬件收益归因。Phoenix 的固定 copy/GEMM 无法回答 split-K partial 何时对另一个 TARS cluster 可见，因此本轮来源审计不推动 Phoenix SDK 适配。

## 4. 当前核验的 Qwen 工作量来源

**V：固定官方配置** `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` 的 text config 是 BF16、hidden=2560、intermediate=9216、SiLU。**V：固定 Transformers** `f62dc9bf2c90353b442a56e74391fbb8c689b55e` 的 `Qwen3_5MLP` 定义 gate/up 为 H→I、down 为 I→H，均无 bias，forward 是 `down(SiLU(gate(x))*up(x))`。这支持 down 的 full K=9216 与完整 output N=2560。[官方配置](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/config.json)、[固定官方实现](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L822-L835)

本次本地 SHA-256 与 R5 已存 manifest 对上，读取到原始源内容；未下载权重 payload：

| 本地冻结源 | SHA-256 | 核验内容 |
| --- | --- | --- |
| [config.json](D:/dsh-proj/SchedResarch/r5/sources/qwen/config.json:7) | `ddc63e1c717afa86c865bb5e01313d89d72bb53b97ad4a8a03ba8510c0621670` | text dtype、H、I |
| [modeling_qwen3_5.py](D:/dsh-proj/SchedResarch/r5/sources/qwen/modeling_qwen3_5.py:822) | `458360c8072e6130580639170ad3e645b975512dbabae31eab5f92de5f0f09ef` | MLP 定义及 down 算式 |
| [representative_weight_shapes.json](D:/dsh-proj/SchedResarch/r5/sources/qwen/representative_weight_shapes.json:1) | `0cfea86881cb17b746b5b8150bf7ce35605756141c1ab365b1c4df9e962d372a` | 已存 header 提取记录：down [2560,9216]、BF16 |

对应 [冻结来源 manifest](D:/dsh-proj/SchedResarch/r5/sources/resource_source_manifest.json:5)。官方 config 的 raw URL 本次首开失败，blob 页面成功；没有将失败报成核验成功。GitHub raw 本次可读，网页抽取行号与本地物理行号不同，本报告采用本地源/固定 GitHub 行链接。

**R：R8 slice** 取 N=128（完整 output 的 1/20）、M∈{1,32}，输入是已准备好的 BF16 `[M,9216]`；其来源是同一 MLP down 的数学子问题，不是完整 MLP、真实 gate/up 激活分布或 autoregressive 运行。全 slice BF16 权重为 `9216×128×2=2,359,296 B`，每个四核均分为 `589,824 B`；所选输出范围必须在 manifest 中固定。

**H/R：M=1 不是历史 target 的 native M 合法值。** 若使用 Mpad=32，必须指定零行由本地生成还是由 DDR 搬入、输出有效行 mask、实际 MAC/访存；不能把逻辑 M=1 bytes/MAC 冒充 TARS 执行量。M=32 仅满足历史几何约束，仍不认证 BF16 输入与 FP32 partial 可导出。

## 5. 最小多 cluster 合同建议

以下全部为 **R**；是可执行账本/事件检查器的合同，不是新的 TARS wire，不增设完整 NoC。

| 字段 | 最小选择与约束 |
| --- | --- |
| topology | `chip0/{c0,c1}/{core0,core1}`；每核独立 MXU/VPU/TMU/VMEM，每 cluster 一个 DMA。单 cluster 双核作规模控制；同一双 cluster 内比较静态 mapping。 |
| shared resource | 为每条 movement 标 cluster DMA 与显式外存 endpoint；是否共用一个外存服务资源作为待核验项。只登记容量/credit/bytes，未校准前不填 latency/bandwidth 推收益。 |
| payload route | 无 direct payload link 假设。跨 cluster partial 路线写为 `src VMEM → DDR scratch → dst VMEM`，每阶段各自含 byte count、源/目的地址及完成事件；这条跨 cluster 路线本身仍未得到 TARS admission。 |
| memory | 每核 capacity、保留区、workspace、input/weight/output/partial span 逐项记账；DDR scratch 独立容量。权重能放入 VMEM 不代表可跨 kernel/层永久常驻；cold/resident 必須同起始状态比较。 |
| dependencies | 一个规范 typed edge 集合，区分 data-visible、last-read reuse、数值归约。两资源任务共用 DMA 只需互斥/credit，不自动加入语义边。 |
| completion | 显式分开 command acceptance、source-read done、DDR store visible、destination VMEM visible、consumer final read done。payload 未到目标不得成功唤醒；source 释放等全部 reader 完成。 |
| event identity | 有限一次性 DAG 可以使用唯一 ID；不复用、不重试的情况下不默认增加 epoch 表。若复用槽、运行多次、重复/迟到 completion 可混淆，另加 generation/最大在途/drain 协议并收费。 |
| finite budgets | 总 descriptor bytes、所有 cluster 加起来的 event/queue/issue/wakeup/storage 预算单列。按域复制四个窗口不能与一个同深度总窗口当作同硬件。 |
| legal execution | 先强静态 self-timed：合法 mapping/layout/驻留/tiling/prefetch/资源顺序及通信通道序。没有真实残差之前不添加 ready 选择器。 |

这些字段延续 [最小 Execution Contract](D:/dsh-proj/SchedResarch/analysis/compiler_contract_requirements.md:33)、[完成事件分类](D:/dsh-proj/SchedResarch/analysis/compiler_contract_requirements.md:116)、[域/资源预算](D:/dsh-proj/SchedResarch/analysis/compiler_contract_requirements.md:188)；这些旧文件自身同样只声明研究原型。

**E：外部独立校验提醒。** Linux 官方 DMA 文档区分 coherent/streaming 映射，并说明 coherent memory 仍需适当内存 barrier，重复 CPU/device 访问 streaming buffer 时也需对应同步。这支持“有地址/发出标志不足以替代可见性合同”的审计问题；不表示 TARS 要使用 Linux DMA API、cache flush 或某个 CPU fence。[Linux DMA API Guide](https://docs.kernel.org/core-api/dma-api-howto.html#types-of-dma-mappings)

## 6. N-shard 与 split-K：先把静态解释账算清

**R：共同边界**为同一 `[M,9216]` prepared 输入、同一 `[128,9216]` BF16 权重 slice、四核相同硬件总预算、最终相同逻辑输出。必须另外冻结初始 input/weights 所在存储域、是否已有副本、最终 output 必须在 DDR 还是 c0 VMEM。否则不同 endpoint 本身会制造“通信收益”。

| 项 | N-output shard | K-by-cluster / N-by-core |
| --- | --- | --- |
| 每核矩阵子问题 | K=9216、N=32；四核覆盖互不重叠的 N | 每 cluster K=4608；各 core N=64；两个 cluster 对同一 N 生成 partial |
| 总权重 / 每核 | 2,359,296 B / 589,824 B | 同左 |
| 输入各核各从共同 DDR 冷载、无 multicast | 4×M×9216×2 = **73,728M B** | 4×M×4608×2 = **36,864M B** |
| 跨 cluster reduction payload | 对此 down slice 可为0；下一算子的 gather 另计 | c1 两核各 `[M,64]` FP32 partial，共 **512M B** |
| 经 DDR 物化 partial 的逻辑 endpoint bytes | 0，除非规定最终位置须 gather | partial 写+读共 **1,024M B**，不能把一份 payload 算成单向一次总流量 |
| 数值合并 | 每个输出维度只在一个核做 full-K reduction | c0 等本地与远端 partial 后按固定形式加和；FP32 partial 增加 storage/读取/写出与加法 |

这里的 bytes 是**所选无 multicast、紧凑 layout、逻辑 M 的合同算术**。它们不是实际 AXI bytes，不计未经定义的 burst padding、M padding、cache、prefetch 重读或 hidden buffer。选取实际布局后应逐 request 审计。给 split-K 计 partial 却不给 N-shard 计重复输入会误导；给 N-shard 免费 multicast 或给 split-K 免费 initial K partition 同样不公平。

N-shard 消除这一次跨 cluster partial reduction，不等于它必然更快；在上述初始条件下它多载输入。若最终结果只需 DDR 全局可读，四个 N-shard 可各自写 disjoint output，无必需 gather-to-c0。若后继要求 c0 驻留，N-shard 也要计 gather。若 gate/up 融合后 activation 原本按 K 分片驻留，必须将 producer placement/通信纳入共同边界；不能把 prepared-input slice 当融合 MLP 的总成本。

**E/R：split-K 数值许可门。** 官方 PyTorch 文档说明浮点非结合，数学相同操作不保证 bitwise 相同；BF16 GEMM 的中间累加/截断还受 backend 影响。因此 `sum(K)` 与 `sum(K0)+sum(K1)` 是实数代数等价，不能自动称现有 BF16/FP32 kernel 等价。FP32 partial 只是 R8 选择，需记录乘法、累加、partial 导出、最终加和/回写每一处 dtype 和 rounding；CPU fixture 应同时保留精确可表示控制与非平凡 rounding case、误差分布和不通过项。任何 fixture 容差通过均不授权 TARS 编译器重排归约，也不代表模型精度通过。[PyTorch 2.8 numerical accuracy](https://docs.pytorch.org/docs/2.8/notes/numerical_accuracy.html)

## 7. 具判别力的来源结论与停止门

1. **Research Question：跨 cluster partial/完成边界是否是不可避免的共享资源损失？** Hypothesis：在固定 slice 下，相当部分需求由静态 partition/起终位置决定。Strong baseline：比较上述两个静态映射，统一 logical output、资源与数据起点，列出合法性未决项。Discriminative experiment：复算全部 bytes/读者/lifetime，以有限事件枚举证实 premature signal、source early reuse 和 shared scratch alias 必须被拒绝；不仿造时间随机数。若 N-shard 合法且删除 partial，结论仅是“此移动非 workload 必需”；其整体代价仍须含输入与后继布局。
2. **Research Question：payload done 与 completion 可以合并成一个未标作用域的事件吗？** Hypothesis：同一简单跨域路线已经需要可区分的到位/释放事实。实验应删除目标可见或 last-reader 边构造危险次序，再检查显式边能否排除。该结果属于结构合同必需性，不是“需要新的 hardware event network”，现有有序协议若已保证相同顺序就足够。
3. **停止机制门：** 当前来源没有固定 strong-static binary 在目标上的真实 residual、不确定性的因果观测、合法恢复动作或收费净 elapsed。到此只 Accept ledger/invariants，Refine 当前 target；不接受 DMA scheduler/direct link/NoC/chiplet 性能主张。若残差由 layout/residency/static mapping 消除，则归为 compiler/co-design；若必需资源 bytes 或严格依赖已达下界且没有合法替代动作，停止动态恢复。真实残差仍未知，不等于零，也不延伸 R5 ready 负结果到所有多 cluster。

后续是否进入性能实验，仍服从 [R8 交接门](D:/dsh-proj/SchedResarch/r8/continuation_brief.md:37)：目标合同与最低观测先成立；独立 train/validation/test、固定 selected-static、≥5% 净 elapsed、95% paired CI 下界>0、每条件每 session≥30 独立 paired blocks、第二 session 新相位、两个非极端干扰、quiet 均值回退≤1%。本审计没有生成这类样本。
