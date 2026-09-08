# R13 独立回放检查器设计与证据边界

日期：2026-09-08。本文从属于 [当前执行合同](proposal_contract.md)，不是第二份性能合同。检查器的作用是检查具名参考模型的实现一致性；不提供 Wormhole 芯片精度认证。设计开始时尚未获得主 DES 的冻结接口，因此本文先列必须覆盖的性质与反例，实际实现覆盖以运行回执为准。

## 实现独立性

主执行器使用事件队列跳至下一事件；独立检查器使用整数 tick 逐步推进，用独立的状态集合、循环、仲裁与有理服务预算实现。不得导入主 DES、调用其路由或服务 duration 函数，亦不得用主 DES 生成的完成时间作为 checker 的输入条件。可以读取相同的纯 JSON 工作负载、参数与模型规则。

冻结输入应含活动任务及其依赖、初始内存 16B 块身份、地址/owner、payload 精确范围、请求类型与 NoC、允许 issue 的窗口、计算服务需求、源/目标/接收/结果容量。输出至少含分离事件、逐块读取/写入和 flit/credit 轨迹，便于不只比对最终 makespan。对完整输出、final ACK 和 quiescent 三个时点分别比较。

若主 DES 实现仍只覆盖网络 packet 层，checker 的通过结论也只限网络层，不能据此将全 DFG 的 M0 判为通过。未实现功能必须列为未验证，不能通过空例或同时省略而获得 PASS。

## 必须冻结的服务规则

以下表已按实现后的 [服务状态机接口 v1](machine_contract.md) 统一单位与账本；该接口是执行规则依据。`1 model cycle = 36 tick`，公开的 cycle 数值不能直接当整数 tick。此处修正初稿文字，不改变任何性能参数。

| 对象 | 可检查的规则 |
|---|---|
| 时间 | 所有完成/到达/credit 返回先批量生效，再为该 tick 统一仲裁。零时逻辑闭包不可让容器遍历顺序改变结果；服务发生于区间还是边界须明确。 |
| 链路 | 32B/flit；每有向 link 每 model cycle 至多启动一 flit，即启动间隔 36 tick。router-link 传播 9 cycle = 324 tick；NIU 邻接采用 5 cycle = 180 tick。传播与启动间隔分离。 |
| 路由 | 独立生成 10×12 torus：NoC0 +x 后 +y，NoC1 −y 后 −x。request、response、ACK、notification 分别完整计路；返回路径不取请求边反向。 |
| VC | 每 hop 的 dateline/class/buddy 编码和释放时机明示；同 hop 同 VC 的 packet 排他；不同 VC 是否 interleave 由共同仲裁决定。未知硬件策略只能标为模型规则。 |
| Router buffer | 每 inbound port 64 flit，16 VC 各保底 1 flit，48 flit 共享；每 VC 可再占至多 15 flit。共享池不能按 VC 复制。 |
| 预留与 credit | `available_credit + reserved + occupied + cooling = capacity`；reserved 包括已经发出尚未到达的 flit。物理占有为 `reserved + occupied`；cooling 是已释放但上游尚未收到 credit 的容量。credit 返回从实际释放时刻开始延迟，本地已空空间与上游可用 credit 分账。 |
| NIU queue | BN 是显式的研究参数，不等同 router buffer。source-read 生成的数据与 target-write 等待的数据分别有有界状态。 |
| L1 | 16B 原子读/写；公开 bank 吞吐上限按每 cycle 一次 16B 访问理解，不能写成每 tick。当前具名模型为非本地访问保守地占用每块 `36/ηN` tick，同 bank 的两块顺序生效；该服务量不是已测 bank 延迟。各 NoC 分立两读/两写口，不能复制共享 bank，也不能合并独立 NoC 口。 |
| DRAM | 同 group/channel 地址的多个 endpoint 共用物理 channel；读写合计服务预算，而非分别给满带宽。不同 channel 可并行。 |
| 分数吞吐 | 独立整数分子预算实现给定有理 rate，不按每 flit 向上取整。冻结空闲时预算累积/封顶/重新激活规则；避免空闲积攒无限 burst。 |
| 完成 | `source_last_read` 来自全部实际源读完成；`target_visible` 来自最后目标内存写；ACK、通知与 consumer 最后读分开。 |

## 必需反例与正控制

| 编号 | 变异/构造 | 必須判定 |
|---|---|---|
| C01 | 一条无争用多 flit 路径 | 与可手算启动/传播流水一致；不能当整包逐 hop 存转。 |
| C02 | 两条物理独立有向 link，同时跨过同一 router | 应可同时服务；router 节点不能被错误当成单 server。 |
| C03 | 共用一个有向出口、不同 VC | 合计每 model cycle 至多启动一 flit，最久未获服务队列优先；不同 VC 可依法交错。 |
| C04 | 同 VC 后一 packet 在前一 tail 之前插入 | 拒绝；逐 hop 尾部释放与在途状态仍要区分。 |
| C05 | 从某 inbound port 的多个 VC 累积 >48 共享 flit | 拒绝；不可各自享有 48 flit。 |
| C06 | 入链时不预留，只在到达时计容量 | 必须被容量/credit checker 拒绝，即使一次输出仍正确。 |
| C07 | 释放时立刻退 credit 或在 arrival 前退 credit | 拒绝早退；BN=1 与长 RTT 应真正触发反压。 |
| C08 | 同一 channel 通过不同 DRAM endpoint 服务 | 合并物理 channel 预算；另一 channel 并行作为正控制。 |
| C09 | 两 NoC 同 tick 访问不同 L1 bank / 相同 bank | 前者可用独立接口并行；后者受共同 bank 限制。 |
| C10 | `sent` 后覆盖尚未读取的 source 16B 后缀 | 以不同块/epoch 的真实内容拒绝，而非仅靠最后标量 checksum。 |
| C11 | NIU 已收到 tail 但 target 最后写未完成便 consume | 拒绝；不同 bank 服务可形成有效的非原子前缀。 |
| C12 | ACK 到达即返还尚有 consumer reader 的 receive slot | 拒绝；source slot、receive slot、result span 不互相代用。 |
| C13 | 正确 source-last-read 后、旧远端 ACK 前覆写 source | 应允许，若所有源 reader 确实结束；不能额外强制远端消费完成。 |
| C14 | 两请求的 ACK 乱序，在相同 scope 用一个增量指定任意请求完成 | 拒绝；scope、ID 和 outstanding 上限独立记账。 |
| C15 | 两个服务同刻完成；输入任务/字典迭代顺序翻转 | 在冻结 tie-break 未改变时，完整轨迹应相同。 |
| C16 | 合法起始状态但事件停滞、仍有 pending 请求/credit | 报告未终止及等待原因；不得把当前最大完成时间当合法结果。 |
| C17 | 输出已可见但末尾通知/ACK/credit 尚未返回 | 输出时间可单报，但 quiescent 不能提前；下一 invocation 不可免费重用。 |
| C18 | ηN/ηD 取 0.75，长 burst 后夹空闲再启动 | 验证有理预算与空闲规则；短包逐个 ceiling 不得无说明降低持续吞吐。 |

R12 全复制共享 bus 与真实 2conv affine/halo 分开验收：明确 full-copy 需求时保留 2048-cycle payload 下界；连续对齐 owner 的 halo 需求为 49152 bit，对应 384-cycle 必要服务下界。checker 不从 buffer footprint 自动产生 full all-gather，也不从该必要界推断已实现 512-cycle 协议。

## 最小验收产物

运行回执登记：输入与参数文件 SHA-256、实际 checker 命令、Python 版本、fixtures 数、对比字段、所有 mismatch、成功拒绝的变异、尚未实现的性质。通过全轨迹差分与负例后才扩大流量/候选规模。回执保存于 `artifacts/checker_*.json`。

本次已全文读 [R13 合同](proposal_contract.md)、[独立合同红队](../analysis/r13_model_contract_redteam.md)，以及固定 ISA checkout 的 NoC README、RoutingPaths、Ordering、Counters、L1、DRAM README。固定来源 commit 为 `5287a62727350bcef35f7b411d1b8a706172ec4c`。这些源码文档说明结构与语义，未执行任何板卡测试。

## 第一版实际实现状态

收到 [服务状态机接口 v1](machine_contract.md) 后，已实现 [independent_checker.py](independent_checker.py) 的 `simulate(spec)`，按每 model cycle 36 个整数 tick 逐 tick 扫描；未导入 DES 或其构建器。实现已入队/在途预留/credit cooling 的分账、group 共享池、资源启动间隔、尾 flit 传播后 VC 释放、初始 admission/FIFO 与具名仲裁。统一接口的 `operations`、`job_end`、`quiescent`、`buffer_peaks` 与 `resource_launches` 可用于全轨迹差分。

[单测](test_independent_checker.py) 的17项手算与状态检查已实际通过，详见 [运行回执](artifacts/checker_unit_receipt.json)。其中一跳、header 加一 data flit、全 ready 的末尾到达为720 ticks，credit清空为1188 ticks；单 flit buffer、入链传播10 ticks、实际释放后90 ticks返 credit 时，第二次注入只能在100 ticks启动。还检查了同/异 VC 交错、共享池、独立 link、共同 bank/channel、零时间依赖、同刻输入顺序不变性、重复操作不可被结果聚合吞掉与死锁。用 `test_independent_checker.py --receipt` 重新运行并生成回执。

这些单测未证明源/目标/消费及数值构建器。尤其接口把每个 operation 的 latency/II 作为纯数据输入，独立状态机只能检验该输入规则的一致执行，不能独立发现两实现共同收到的错误服务 duration。来源参数到 operation 的独立解析检查、16B 内容/epoch 验证及真实事务图仍是 M0 所需的另外证据。

随后对主 DES 的公开 `simulate` API 实际进行9个手算 fixture 加200个固定 seed 合成状态机的差分，核对全部操作的start/end/queue/resource/lock与完成/峰值。首次检查发现11个 deadlock 样例仅在 `quiescent` 字段不一致：两实现对“最后进度”计法不同；全部操作和资源轨迹一致。由于死锁根本不存在清空时刻，双方经合同澄清统一为 `quiescent=null`，诊断时点另列。首次失败回执保留在 [修正前记录](artifacts/checker_differential_before_deadlock_contract.json)，[复验209例](artifacts/checker_differential.json) 零差异，其中94例双方均识别为死锁，115例完成；并非把死锁当低性能样本。

[8项服务规则变异](artifacts/checker_rule_mutations.json)全部被检出，包含提前退credit、取消有限reservation、复制channel/bank、删VC锁、错误合并独立出口、hop latency当II和复制shared pool。其方法是给主执行器改变后的规则，再对照独立引擎执行原冻结规则；这说明所选fixture能区分这些错误规则，不冒称已完成16B epoch变异。可用 `test_independent_checker.py --differential` 和 `--mutations` 复现。此处固定seed是实现压力回归，不产生物理timing置信区间。

## 构建器独立审查与实际完整微图回放

在未读取主 DES 推进实现的前提下，全文审查 `model_builder.py` 与 `hardware_model.json`。发现并向主实现者报告两项具体问题：

1. 第一版两个16B块共享单一值生效事件，mono-bank虽占两次服务却同时生效，不能支持声明的逐块部分访问。主实现已新增每个16B块的 `block_completion_ticks`，mono-bank按注册的保守服务量顺序生效，并把 `bank_layout` 写入输入元数据。
2. 第一版固定发送窗口复用了普通signal，导致 `control_scale` 同时缩放计划的窗口。主实现已给 timer 单独语义，只改变控制primitive费用时固定窗口不变。通知与token的实际本地L1读取也已显式加入，primitive费用另外收取。

另指出同地址读写的同时刻裁决不能依赖trace展示顺序；这部分由独立数据/epoch审计处理。主图中的接收可用条件通过本地notice读取满足，notice发起须等peer ACK；slot token同样通过本地读取观察。其依赖使用模型本地可观察事件，没有让发起方直接读取隐藏的远端write完成时刻。

`audit_builder_rules` 不调用构建器的 `route`、`rate_ticks` 或 `memory_op`。它从模距离独立构造正/负方向与维序的链路，从packet类别与实际16B block标签核对header/data和返回流量，并从登记的参数重新计算bank/port/channel资源、逐块offset、NIU/router共享池与credit。DRAM endpoint到group的映射另外核对了固定tt-npe `wormhole_b0.hpp` 的controller映射（其坐标字段为row/column，按对应关系换成x/y）。此处的NIU效率同时影响注册场景中的bank服务占有，是保守模型规则，不是已测L1 bank延迟。

[构建器资格回执](artifacts/checker_builder.json) 实际完成两个完整的两链/两代微图：64B、全NoC1、同组异channel；以及1KiB、全NoC0、同channel别名。两图所有operation时间/资源/锁、job完成、峰值及quiescent均与独立tick回放一致；网络实际启动次数与独立全packet类别链路账本一致。对应quiescent为53920和89020 ticks；这些是模型资格数值，不是编译器收益。优化后的独立扫描耗时约5.54秒和32.65秒，仍逐tick推进，不跳过时间。

同一回执还对26个预登记参数/控制点×两种bank布局的52张64B微图执行了独立**构造与服务算术检查**，全部通过；这些52项没有执行敏感性性能比较，不能被计为M2测试。两个执行图及52个构造检查期间记录的六个来源文件哈希未改变。复现命令为 `test_independent_checker.py --micro`。

本检查器的结论至此仍是状态机、登记服务规则和两张完整微图的实现资格。完整数值/epoch、明确非法复用反例、三见证族的实际触发、强P0与小图全集以及完整MLP门，应分别引用负责它们的运行回执；不能仅凭本文件把M0/M1/M2一并签为通过。

## 限定 tt-npe 投影：当前未执行跨工具比较

已实现 [npe_projection.py](npe_projection.py)，复用既有 `SchedResearch-R12` 发行版、`/opt/schedresearch-r12/venv-npe/bin/python` 与固定安装模块，不安装新环境。脚本为NPE每条flow创建一个 `npe.Transfer`（`num_packets=1`），其绑定说明是近似一次异步读/写调用的API抽象；不是已展开的request/response/ACK flit trace。坐标显式使用 `Coord(device=0,row=y,col=x)`。F端使用 `Builder.packet` 的无ACK纯request投影，包含header、payload flit、有限buffer/credit及源/目标L1服务；不使用完整transaction wrapper。

同一固定NoC0下，`overlap=[(1,1)→(3,1),(2,1)→(3,2)]` 与 `separated=[(1,1)→(2,2),(2,1)→(3,2)]` 的request payload/hop总量一致，前者两flow共用一条有向router边，后者不共享。F端已实际完成1/2flow×1/8KiB共8项，全部header/data/link账本符合独立路径统计。单flow两种路径均同时间；双flow下，overlap比separated的request目标可见时间分别多154⅔ model cycles（1KiB）和1398 model cycles（8KiB）。这些是**无返回协议的服务投影**，不是完整transaction的等hop见证、完整DFG收益或编译器贡献。

NPE运行前登记了32/64/128/256cycles timestep的全部条件，没有调F参数匹配NPE。但当前会话实际调用指定发行版即返回 `Wsl/Service/E_ACCESSDENIED`（退出码4294967295），尚未进入Python或NPE；枚举发行版也返回同类拒绝访问。原始命令、解码错误文本与stdout/stderr原始字节哈希保存在 [投影回执](artifacts/npe_projection.json)，其 `cross_tool_status=not_executed`、`passed=false`。因此没有NPE新时间、趋势一致性或跨工具PASS，不能沿用R12曾经运行过API来填补本次未执行的比较。

本次能完成的NPE侧核查仅为固定C++ `unicastRoute`（`wormhole_b0.hpp:320–356`）：NoC0先增加col后row，NoC1先减少row后col，与声明方向一致。还核查绑定的API粒度及固定带宽表；1KiB/8KiB表值为27.4/30.0B/cycle、WORKER injection为28.1，而F使用ηN=0.75及显式有限queue/credit。这些成本合同不同，不以数值吻合为准，更不能伪造golden。待环境可调用时，现有脚本可直接运行；本轮继续其他模型工作，无须等待真实板卡。

## 有限集成边界资格

[test_model_integration.py](test_model_integration.py) 在运行前明确选择9项有限边界，实际结果见 [integration_qualification.json](artifacts/integration_qualification.json)。前七项为完整两链/两代微图，均通过独立构建器规则检查、DES与 `trace_audit` 的数据/epoch/复用审核：16B最小payload、32B负向与wrap路径、48B末flit半满且额外NIU处理为零、1KiB且BN=1、32B且credit=36cycles、48B mono-bank，以及16B descending仲裁。最后一项再做独立逐tick回放，全部核心轨迹零差异，quiescent=56180ticks，独立回放耗时约5.41秒。该次运行前后七个来源文件哈希一致。

第八项单独验证最大8192B packet：物理坐标(9,11)到(1,1)沿NoC0跨两维wrap，一个header加256个data flit；512个不同身份16B块的源读/目标写和最终内容通过独立copy审核。该例只有packet，不包含计算scratch、ACK或跨代复用；具名两链 `trace_audit` 对它不适用，回执明确分开。

第九项为**8192B完整微图的预检拒绝**：当前两份RF数据需16384B而预算只有2048B，且4096B的固定DRAM epoch间隔会造成地址重叠。没有运行这个非法输入的性能，没有扩大scratch或改地址预算；该项证明独立预检拒绝，不冒称构建器API已有相同guard。8KiB packet合法不意味着8KiB完整微图合同合法。

九项集成通过只补强这些边界的实现证据。NPE跨工具调用仍为 `not_executed`；因此M0应分别列出“本地模型/功能/守恒/回放已完成”和“限定跨工具步骤未执行”，不能无保留地写整条验证链已通过，也不能把后续有限枚举结果改名为已完成该缺失步骤。

## 枚举完成后最优计划的独立回放

在名义参数的576项有限集合枚举完成后，追加了 [checker_optimum.json](artifacts/checker_optimum.json)：选择并列最优中的 p0024 做1KiB完整微图逐tick复核。这是 **post-enumeration winner verification**，不是事前选定的见证，也没有用checker重新搜索或回放全部576个候选。实际计划与p0000唯一非ID差异为 `nocs=[1,0,0]` 对 `[0,0,0]`，即load使用NoC1。

独立引擎没有接收枚举或DES的时刻作为执行条件。6120个operation的全部核心字段、job完成、buffer峰值和资源启动次数与新DES回放零差异；两者的output-visible、final-ACK、quiescent分别为81136、85456、86032ticks，与归档枚举记录一致。新构造spec和DES trace的规范JSON哈希也与枚举逐项记录一致。独立tick耗时约40.27秒，运行前后八个来源文件哈希稳定，并与枚举使用的公共来源哈希相符。

同一独立trace再次通过16B值/epoch/生命周期审计，独立构建器规则及完整packet链路账本通过。该检查支持有限集合获选计划的实现一致性，不能扩展成集合外全局最优、完整P0准入、新编译器贡献或tt-npe跨工具执行通过。
