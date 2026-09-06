# 下一阶段真实设备测量门

日期：2026-09-05。当前未指定或提供目标芯片、设备权限及其测量接口。本文件冻结可执行的最低测量合同，供取得设备后直接实例化；**不宣称已执行设备实验，不预选下一架构，也不将 R5 研究参数当作目标芯片规格。** 已有来源见 [resource_evidence.md](resource_evidence.md) 与 [来源清单](sources/resource_source_manifest.json)。

要回答的问题是：强静态已完成合法 mapping、fusion、tiling、memory planning、prefetch 和主要资源排程后，实际服务变化造成的端到端损失有多大，其中多少可由因果可观测信息恢复。资源拥塞、性能方差和动态派发收益分别测量。

## 1. 一次测量必须固定的对象

| 固定对象 | 最低记录 | 防止的混淆 |
| --- | --- | --- |
| 设备与软件 | 芯片/板卡修订、固件/驱动/runtime/compiler版本、编译参数、每个二进制SHA-256、kernel清单、实际启用的资源限制 | 把编译器升级、驱动变更或硬件扩容当作调度收益 |
| Workload | 模型repo/revision、子图边界、shape、dtype、tile、MAC/ops、真实payload bytes；输入/随机权重/初始state hash；输出验收规则 | 把缩feature宽、不同精度、少算工作或未执行的上游producer混进对照 |
| 地址与内存 | tensor布局、对齐、物理/设备地址或可追溯映射、capacity、RF/SRAM/外存驻留、alias/last-reader边、warm/cold状态 | 随机地址、额外buffer、缓存驻留和spill变化制造对照差异 |
| 时钟与系统状态 | NPU/内存/互连/CPU设定及实际频率、温度、供电/功耗模式、CPU亲和性；无法锁频时记录实际变化 | 将DVFS、热节流、主机抖动归为完成顺序信息价值 |
| 运行边界 | host-submit、设备开始、最终结果可见、host-fence返回的可用时间戳及对应时钟域 | 将CPU launch/等待成本与NPU执行时间混为一谈 |
| 背景干扰 | master身份、程序/输入hash、读写比例、地址范围、工作集、offered与实际bytes、起止/相位seed | 将不可复现的系统噪声当作可控外部服务，或把调度自身流量当外生流量 |

采用已经冻结的 [全宽切片规格](full_width_specs.json) 是一个可选起点；只执行两个projection tiles或两个state heads就按该范围报告。目标若不支持该BF16/FP32路径，先换成目标实际支持的合法实现并重新冻结数值、bytes和kernel边界；不能将INT8硬件宣传值直接代入BF16结果。真实权重质量与随机数据下的执行一致性分别验收。

每个对照内部固定同一 binary/layout/input。允许更强静态生成新的binary或地址计划，但必须逐个保存版本、数值/工作量与内存合同，明确这是compiler对照。随后在同一已选合同内比较运行时策略，避免动态同时获得更多buffer或不同tiling。

## 2. 最低观测集与可作出的判断

| 观测 | 最低字段/计量单位 | 使用边界 |
| --- | --- | --- |
| 端到端elapsed | 每次运行的设备elapsed cycles或设备时间；另列host submit→fence elapsed；注明finish是interrupt、retirement还是payload visible | 以端到端elapsed为主指标；若仅有host时间，只能报告含软件成本的端到端结果，不能归因设备内部等待 |
| 实际traffic | 每port的read/write requested、accepted、completed有效bytes；能读取时另列bus beat数、突发数、padding/重传 | 校验固定工作的bytes守恒；额定带宽不等于实际有效吞吐，bytes减少属于traffic优化 |
| DMA outstanding | 配置上限、观测峰值、均值/时间积分、达到上限的周期或拒收计数；记录统计边界是request accepted到何时释放 | 满额不等于关键路径损失；credit在last beat还是目标可见释放必须写清 |
| Request latency | 请求ID/command ID、接受、首beat、末beat、目标可见时间；若无trace，保留明确边界的latency buckets及overflow计数 | 接受→数据返回与返回→consumer可读分开；只有总histogram时不能重建完成反转与因果调度机会 |
| Compute active | 每core/engine的active、data-starved、dependency-wait或等价实际支持计数；保存核频和计数器定义 | 固定shape稠密compute先测确定需求；多engine active之和不等于wall-time利用率或token/s |
| Shared-memory/NoC | 设备实际暴露的bank/request arbitration等待、return queue占用、credit starvation或backpressure周期 | 不假设任意芯片都有这些计数器；无该观测就标不可辨认，不能用邻近计数器直接代替 |
| Dependency/visibility | 可获得时记录task-ready、issue、producer完成/可见及consumer开始，保留具名依赖与资源域 | 只有它与资源空闲时间同时可见，才能辨认合法替代任务；局部ready仍不证明最终收益 |

最低闭环需要 **elapsed + traffic + compute-active + 至少一个有定义的request/limit/latency观测**。如果设备只提供elapsed，仍可做隔离/干扰及compiler对照并测量性能损失，但只能作为瓶颈筛查，不能通过新硬件机制门。

时间戳跨时钟域必须有同步/换算规则和误差界；计数器要记录位宽、wrap、multiplex、reset与采样点。先用空运行、已知bytes的单搬运、单compute校验定义及采集开销，量化instrumentation开启/关闭的elapsed差。trace丢记录或overflow的运行应单列并重采，不能填补成零stall。

公开测量能力的参照是 Arm U85 TRM 的 request stall、outstanding-limit stall、AXI latency buckets、MAC active；这说明分类有工程依据，不说明用户设备具备同名接口。[冻结Arm TRM](https://documentation-service.arm.com/static/67b5ba01ce2747241fce860f)、[CMSIS配置来源](https://github.com/ARM-software/CMSIS-Ethos-U/blob/79d0fccfe59cab7fd0cab97c65050d2824c5269f/source/README.md#L150)。Gemmini的transaction ID、bank和返回ready代码可用于核对某个明确RTL配置的规则；其验证不能替代目标NPU测量。[冻结Gemmini DMA](https://github.com/ucb-bar/gemmini/blob/8c3f9923a44a2fe2c7930587be297d6d4f8c09ca/src/main/scala/gemmini/DMA.scala#L396)

## 3. 有判别力的运行矩阵

在模型、binary和地址冻结后，按以下顺序采集；先注册全部条件和停止标准，不因某次结果好看才追加干扰强度。

1. **隔离、固定频率**：固定warm/cold策略与state初值，验证数值、bytes、compute-active和重复运行方差。若相同binary在无干扰下已经存在稳定大stall，先查确定性布局、容量、kernel和静态排程。
2. **受控固定相位干扰**：同一个背景程序从事先指定的相位启动，至少包含无背景和两个冻结负载等级；分别记录background实际traffic。固定相位可重复性用于识别时间相关服务，而非模拟不可知未来。
3. **受控随机相位干扰**：背景程序与强度不变，仅从预先冻结的seed表改变相位；同一个paired block里的静态/候选策略使用同一背景程序、相位设定和工作量。设备排队受两者交互影响时允许实际完成顺序不同，不能强制重用另一策略的延迟trace。
4. **新session复验**：重新启动背景与测试程序，使用独立测试相位，检查结论是否仅来自缓存、热状态或某次系统状态。无法控制的其他master流量作为观测协变量保存，不能事后按策略有利方向筛除。

随机化每个paired block的策略执行先后，以削弱热漂移/时间趋势；保留每次run和pair的ID、顺序、状态、失败/超时、所有原始计数，不只保存均值。隔离与干扰之间的损失要在**同binary**下比较；compiler改进和运行时恢复另外报告。

建议先用不计入确认结果的10次pilot核对工具与方差，然后冻结样本量；确认批每条件至少30个独立paired blocks，并在另一session复验。存在时间相关性时按session/block计算区间，不能将同一次长trace的数千个request当作数千个独立端到端样本。p95/p99只在独立运行数足够且区间可报告时作主张；30次不用于可靠宣称p99。样本量由预期误差范围和pilot方差预定，不能“跑到显著”为止。

## 4. Strong-static controls 与归因

静态基线至少覆盖目标真实支持的：融合/算子驻留、合法K/N/M tiling、activation/weight reuse、单/双缓冲、SRAM/RF容量、合法bank地址安排、prefetch深度或间隔、资源顺序与有限队列/outstanding配置。不存在的硬件能力不能通过软件计划免费获得。具体搜索预算、候选、收敛迹象和未搜索维度必须公开。

使用独立training干扰相位优化计划、validation选一次、test只评价；新session是外部稳定性检查。依据test结果改priority、tile或prefetch的工作标为后验诊断，若要确认正结果必须冻结后重新使用新test。若能在tiny约束类中枚举，报告该类最优及gap；有限类clairvoyant不是任意hardware schedule上界。

每组至少分开回答：

- 同一静态binary在隔离与干扰下损失多少，哪些计数随之改变。
- 更强compiler/layout/prefetch能消除多少，是否改变bytes或内存需求。
- 剩余时间内有没有合法替代任务和可用资源；仅histogram时明确无法证明。
- 用当前可观测信息进行合法干预后，最终elapsed是否改善，是否只是提前占用资源拖慢后来的关键工作。
- 增量控制延迟、descriptor/queue状态、额外流量及可能的频率下降是否已经收费。面积/能耗未测时保留为后续独立门，不能从logical bits推出PPA合算。

不累加各task等待冒充端到端stall；各资源busy/stall可能同时发生，必须报告重叠，或以明确优先级分类得到互斥wall-time区间。也不把端到端干扰损失全部叫可恢复等待。

## 5. 决策与停止门

| 观测结果 | 下一决定 |
| --- | --- |
| 请求/bytes/时间戳定义无法核对，采样改变执行明显，数值或容量/alias不合法 | **Refine measurement/implementation**：修复或限定测量能力；不依据该数据推导架构。 |
| 隔离与干扰下的损失都小于预定有意义尺度，或没有可重复残差 | **Reject** 当前runtime-uncertainty候选；保留负结果和已测包络，不继续扩scheduler。 |
| 损失显著，但合法静态布局、fusion、tiling或prefetch可稳定消除 | **Compiler或compiler/hardware co-design**：围绕已定位的静态合同/接口限制继续；无需默认增加动态scheduler。 |
| 剩余损失主要是不可回避的总bytes/带宽或严格依赖，合法提前执行不减少结束时间 | **Reject** 当前ready-dispatch干预；其他容量/流量研究必须另立问题和基线，不把它自动包装为后继proposal。 |
| 有稳定残差，但仅完整未来trace的clairvoyant能恢复，现有硬件观测不足 | **Refine observability**：先验证有限因果观测能否预测可行动的资源状态；不宣称已有可实现机制。 |
| 稳定端到端损失、strong-static不能消除、因果可观测信息可利用、有限合法动作收费后通过预定门 | **Accept mechanism exploration**：只围绕该已测瓶颈建立最小机制原型；总状态、backpressure、RTL/PPA随后单独验收。 |

可沿用5%净elapsed改善及配对区间下界大于0作为阶段筛选门，但必须在测量前登记并说明它是研究价值阈值。至少在独立test相位/session成立、不能只选一个强干扰点；记录无干扰回退与其预定容忍度。若达不到门，正式淘汰该**已测workload/资源包络中的候选**，不外推所有端侧NPU。

没有真实设备时，可先保存以上参数模板、对应计数器映射缺口和可复现微测试输入；现有请求级sim或某个公开RTL的规则检查继续标为simulation/RTL-config evidence。外部有效性门保持未通过，不把缺设备改写成存在新架构机会。
