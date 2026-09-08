# R12 共享资源发现的独立研究审计

日期：2026-09-08。只读审查本轮探针、已保存 solver artifacts、固定 STREAM 相关源码，以及本轮报告/README；实际运行了独立反向几何枚举与 hash 复核。没有重跑路由测试，没有运行新的 optimizer/原探针，没有修改上游或原始结果。

## 判定与证据层次

**本次红队推翻了最初把真实 2conv 归类为“输出通道分片→全输入复制”的判断。最终分片维度是空间 `ox`；262,144 bit 是张量/分配范围，不能用来证明该 fixture 必需传过 bus 的数据量。真实 2conv 的 512 cycles 因此不能仅用 2,048 这个所谓下界判为违规。** 初始报告中“已证明真实 fixture 低计费”“已修复该 fixture 守恒错误”等表述应撤回。

参数化的单共享 bus 反例仍成立：若另行固定 shards→full replicas 合同，且完整 262,144 bit 的不同源数据均有远端需求，则共享 128 bit/cycle bus 即使支持理想广播，也至少需要 2,048 cycles。固定成本函数仅因 source/target 数量相等便把带宽乘 4，没有检查独立链路/数据需求，因而存在前提遗漏。这个参数化发现不能宣称 Wormhole bug、完整 P0 已修好、新方法更快或 native G0 通过。

需区分三个证据层次：

1. `shared_resource_probe.py` 的真实上游类型与 path planner 验证了函数如何接收数据、共享 bus 是什么对象以及为何返回 512。
2. 探针的 word-owner 集合明确设定 source shards 与目标需求，独立证明该设定下的 2,048 下界。单独创建一个 `Tensor` 加 identity operand map，**不会把 source 所有权/target 需求自动编码到 latency helper**。
3. 真实 2conv 已保存结果确认同样的单 bus 路径、512 slot 与分配容量，但最终 operand map 揭示空间分片。层次 2 的全复制需求合同不适用该真实 fixture；不能从 memory occupancy 的分配大小推出所有分配字节都必需传输。下文记录发现和更正过程。

## 独立核查范围

| 材料 | 本次检查内容 |
|---|---|
| `shared_resource_probe.py` | 全文；实际类型调用、五个 shared case、disjoint control、word owner、原结果补收费检查与 hash |
| `shared_resource_probe.md` | 全文；数学前提、原结果解释、修正域与非性能边界 |
| `artifacts/shared_resource_probe.json` | 已保存 case/下界/原 fixture 摘要；使用只读脚本核验全部 6 个源码 hash、3 个 fixture artifact hash及 producer hash |
| `results/baseline_smoke/result.json` | 全文；固定提交、真实 path、iterations、总量、资格 flags |
| `results/baseline_smoke/allocation_ir.json` | `mapping_nodes`、`tiling`、`steady_state`、`latency`、`performance` 完整相关字段 |
| `.../tetra/slot_latency_breakdown.yaml` | 全文；全部 slot、tensor reuse 与 contributor |
| `.../group_0/mapping.yaml`、`core_cost_lut.yaml` | 全文；初始 mapping 与 compute LUT；不能当最终执行图完整证明 |
| `.../tetra/steady_state_trace_compact.json` | 相关 transfer events 与 otherData；非全文逐事件验证 |
| 固定 STREAM | 下表列明函数；没有扫描无关研究方案 |
| `experiment_report.md`、`README.md` | 全文；native G0、计量、最优性和收益的措辞边界 |
| `shared_resource_affine_audit.py`、`artifacts/shared_resource_affine_audit.json` | 全文；保存的实际 operand map、最终 SVG/IR 维度绑定、枚举边界、明确的 ownership 假设；另用不调用 affine 库的反向几何枚举核对结果 |

固定 STREAM 本次 `git rev-parse HEAD` 确认仍为 `75748cc17e7c43add5a7d0d8f080841eb26531c4`。只读 hash 复算结果：6/6 相关源码、3/3 既有 fixture artifacts、探针脚本均与 `shared_resource_probe.json` 记录一致。

## 对主要反解释的核查

| 反解释 | 独立观察 | 判定 |
|---|---|---|
| 128 是每个 source 的独立 bus 带宽 | factory 对全部 bus edges 复用同一 `CommunicationLink` 对象；link bandwidth 只有一个128值 | 当前参数化 shared-bus 合同不成立该解释 |
| source count=target count 代表四条独立链 | planner 建立 source×target 全配对路径后取 link union；latency helper只检查两者数量 | 数量不能证明 resource disjointness |
| 262,144 已把四份小张量重复算进去了 | `Tensor.size_bits=bitwidth×shape product`；shape=(1,16,32,32)、16bit，恰是一个完整张量 | 不是四份 replicas 总量 |
| 四个 source 每人只发四分之一，因此512正确 | 每个 source 的四分之一确实是65,536bit，但四份不同 shard 都要经过同一共享服务 | 对 shared bus 应相加；对独立 bus 才可并行 |
| 理想广播能降到512 | 广播避免每个 word 向三个 remote core重复收费，但仍要服务所有不同 word 一次 | 采用2,048已给广播最有利条件；6,144不是本轮采用的主下界 |
| source和target同core，是否仅需halo | 参数化 shards→replicas 明确需要全量远端服务；真实2conv最终按ox空间分片，可以只交换边界halo | 不推翻参数化反例；**推翻此前向真实fixture外推2,048必需下界的理由** |
| slot之外又收了四份费用 | 原slot4仅一个contributor，raw/active/slot均512；reuse=1，iter=1，overlap=0；全部slot和=12808 | 未发现该既有结果中有补收 |
| 多次循环重新发射可恢复总量 | 唯一temporal loop factor=1，原result iterations=1；compact trace人为显示i−1/i/i+1以便展示 | 三个显示实例不能当三次实际iterations，更不是四次补费 |
| compute overlap隐藏了成本变化 | slot4没有compute contributor | 对固定slot结构，2,048替换512确实使slot和增加1,536；还不是重新求解结果 |
| 14,344等于文档即证明本bug是全部差异原因 | 只读探针确实算得12808−512+2048=14344 | 数字巧合不能替代文档版本、完整执行合同或干预实验 |

上表的排除范围限于已声明的共享资源合同与固定源码。若真实目标允许其他路径、额外并行资源、不同数据分片、初始副本、压缩或重算，应重新求解与重新计量；本次不以排除这些替代方案来制造 H1。

## 固定源码链

| 固定链接与行号 | 独立核查结论 |
|---|---|
| [AcceleratorFactory 152–197](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/parser/accelerator_factory.py#L152-L197) | `bus_instance` 在整个 connection 内唯一，供各 pair 复用 |
| [CommunicationLink 9–73](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/hardware/architecture/noc/communication_link.py#L9-L73) | 共享对象保持同一bandwidth；不是按source分配独立channel |
| [CommunicationManager 191–311](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/cost_model/communication_manager.py#L191-L311) | 全部source-target pairs与link去重；plan缺少足够的按slice逐link multiplicity |
| [utils 308–339](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/utils.py#L308-L339) | `chains` 由端点数量决定；docstring所需disjoint条件未核查；absent/reuse作用为缩放 |
| [Tensor 19–36](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/workload/tensor.py#L19-L36) | tensor总bit数与full-extent constructor；构造器不定义core所有权 |
| [TETRA 949–960](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py#L949-L960) | 同slot同link排斥不同path choice；没有同一transfer内部多source byte累加 |
| [TETRA 1195–1207](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py#L1195-L1207) 与 [2333–2363](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py#L2333-L2363) | 原成本通过active latency进入slot下界，没有此处四倍补偿 |
| [TETRA 1520–1559](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py#L1520-L1559) | total按iterations与slot和、overlap计算；traffic是次级目标，不能自行补成service cycles |
| [TETRA 963–989](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py#L963-L989) 与 [2677–2715](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py#L2677-L2715) | occupancy是allocation footprint，由single-core shape和residency计算，不是独立字节消费trace |
| [Workload 506–588](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/workload/workload.py#L506-L588) | footprint使用tiling及accessor affine extent；应保留最终operand map以审查真实远端需求 |

## 对报告主张的快速审查

未发现 `experiment_report.md` 或 `README.md` 把离线checker、真实SCIP/TETRA求解或tt-npe粗估价写成native G0或设备计量通过。两者明确保留G0未通过、G1/G2未测试、H1/H2无设备性能证据，以及counter/credit/部分写入/CPU ordering缺口。这些边界应保持。

必须修正涉及真实2conv的“输出通道分片→全输入复制”“全部不同payload必经bus”等陈述；本次最终映射补核已发现这些前提不成立。可保留的研究结论是“真实成本函数存在参数化共享bus反例，真实fixture的数据需求与之不同”。对于实际重求解得到的14,344分析cycles，仅能称为事先具名的full-payload成本干预；该值不能证明修正后更准确，也不能反过来确认初始诊断。

无论最终fixture映射核查如何，都不应把`chains=1`全局施用于独立链路。当前disjoint-chain正控制说明512在其他资源合同下可以合法；修正应恢复“数据需求×真实资源服务”的条件，而非机械删除并行。

## 最终映射补核

本审查发现初始`mapping.yaml`的`D1`与ConvParser原始循环顺序不一致于“输出通道”的描述，要求保留最终映射的实际证据。独立workload代理随后从已保存`core_cost_lut.pickle`恢复实际Conv对象，并对照最终SVG：local循环顺序为`b,ox,oy,fx,fy,c,k`；Conv1对应`(z10,z6,z5,z2,z3,z4,z9)`，Conv2对应`(z10,z13,z12,z7,z8,z9,z11)`；`z6`和`z13`都是大小32的`ox`。这些恢复操作由该代理执行，本审查未另行反序列化。

最终mapping恰在Conv1切`z6/4`、Conv2切`z13/4`，因此原推断中的“channel切分”错误。[精确 affine 枚举脚本](shared_resource_affine_audit.py) 与[回执](artifacts/shared_resource_affine_audit.json)已经取得并全文检查。脚本使用保存的真实 operand map 逐项 `eval`，把有效 NCHW 输入坐标裁剪到实际张量边界；消费者输入 map 不含输出通道 `k`，故固定 `k=0` 不会遗漏各输出通道所需的输入。全宽 `oy` 保留所有有效输入行。

其附加合同必须保留：两个算子均将连续且对齐的四组 `ox` 区间 `[0,8)`、`[8,16)`、`[16,24)`、`[24,32)` 依次分给 core 0–3。这是允许的静态 ownership 见证，**尚未证明已有 native address/transfer 计划采用该顺序**。在此合同下，内部边界的六列 `7,8,15,16,23,24` 各仅被一个远端消费者需要；每列有32行×16通道，合计3,072个不同16bit word，即49,152bit。源副本初始化、额外远端副本、实际地址和transfer仍需后端准入，不能由本枚举自动获得。

本审查另行实际执行了独立的反向几何枚举，不加载 pickle、不调用上游 affine 库、不调用该审计脚本：对每个有效输入 word `(c,y,x)`，检查目标 `ox` 区间是否与 `[x−1,x+1]` 相交；其源 owner 为 `x//8`，异 owner 的需求计为远端。该方法与上游正向枚举得到一致的逐 core 远端 word 数 `[512,1024,1024,512]`、输入需求 `[4608,5120,5120,4608]` 和六列集合。另复算三个原 artifact hash 与该脚本 producer hash，4/4 匹配。算术为 `6×32×16×16 / 128 = 384` 个共享 bus 必要服务 cycles；没有进行原生执行或优化器复跑。

该代理随后将原干预合同与回执的 hash 加入 affine 回执。本审查再次复核最新三个来源、producer、原合同和原结果共6个 hash，以及探针到 affine 回执的引用 hash 与探针 producer hash，全部匹配；最新探针报告/JSON 已同步撤回真实fixture必需full-payload的解释。

因此512大于此见证的384必要下界，不能被原2,048全量下界否定。384仍只是条件性数据服务下界，未包括启动、包头、同步等费用，**既不证明512可实现，也不证明实际既有计划需要恰好49,152bit**。完整数据需求较full-payload干预不同，足以撤回用缓冲容量推出真实示例违规的论证。

这一负面审查结果已经即时通知主代理，要求同步修正总报告和入口说明。保留初始探针回执及分析性干预结果用于追溯，但应追加明确撤回/更正，不把旧结论静默升级成新方法正结果。

更正后再次全文检查`experiment_report.md`和`README.md`：两者均已撤回真实2conv低计费/修复的结论，将14,344收窄为具名full-payload费用敏感度，并保留native G0、完整计量和H1/H2尚未通过的状态。未发现把本轮离线枚举或分析周期升级成设备性能证据的表述。
