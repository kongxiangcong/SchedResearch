# R6：真实设备存在，但当前接口尚不能识别强静态后的残差

日期：2026-09-05。**决定：进入目标 kernel 与测量接口的补齐阶段（Refine measurement/implementation），继续关闭 R5 已测的通用 ready scheduler 候选。** 本轮实际运行了本机 Phoenix NPU 的厂商自测，并核验了其源码语义；没有得到强静态之后的受控干扰残差数据，因此既不能宣布“真实机器静态已足够”，也不能提出新动态架构。

预登记见 [experiment_plan.md](experiment_plan.md)，措辞及证据修正见 [amendments.md](amendments.md)。本轮执行顺序为：历史审计 → 设备只读盘点 → 预登记 → 厂商执行/观测检查 → 精确来源核验 → 驻留范围反证 → 合同校验与独立红队。所有新增产物在r6；不通过追加模拟参数寻找正结果。

## 1. R5后仍未解决的问题与假设

| Research Question | Hypothesis | 本轮判别方法 | Result / Verdict |
| --- | --- | --- | --- |
| 真实合法强静态后，是否还有稳定且有意义的端到端干扰残差？ | H1：可能存在，但R5不能证明真实机器存在。 | 先认证本机kernel、计时、traffic、compute-active及request/limit/latency接口，再决定能否执行固定binary实验。 | 有真实copy执行；最低观测与strong-static合同不满足。**未识别，Refine测量，非负性能结果。** |
| R5的RF驻留控制是否代表完整autoregressive decode？ | H2：两head、四prepared token不足以建立跨层/跨token合法驻留。 | 官方模型shape/cache/generation来源及独立容量/生命周期推导。 | 每GDN层2MiB FP32 state，24层共48MiB/B=1；下一token需经过其他层。**拒绝直接外推；保留切片静态正结果。** |
| 剩余损失是否能由因果观测与有限动作收费恢复？ | H3：必须先证实真实残差、strong-static、观测和合法动作，才谈机制。 | 将固定binary干扰、compiler变体与同合同动态恢复分开设门。 | 前置门未通过，**不启动机制实验；R5候选维持关闭。** |

独立[历史审计](history_audit.md)重算了主42配置/7094执行、驻留928执行与相应统计，认证原回执，无需重跑R1–R5。R5约33%的投影差分使用quiet/combined分别重训后的不同静态计划，不能当本轮固定binary干扰证据。R5最好收费ready +0.1821%且CI跨零的结论不变。

## 2. 实际发现与执行到的证据等级

本机是AMD Ryzen 7 7840H，PnP精确设备为AMD IPU Device，驱动10.1109.8.110（2023-12-14）。XRT2.17.0、源码hash `42cba83aee86b253c49eccd484646e91d062468d`，枚举 `0065:00:01.0 / RyzenAI-Phoenix / Ready Yes`。这纠正了“当前没有可访问NPU”的潜在假设，但不将Phoenix的memory层次等同R5机器。

| 证据 | 本轮实际结果 | 能证明的范围 |
| --- | --- | --- |
| vendor `verify`，1次 | 返回码0，PASSED，无Error日志 | DPU_PDI_0提交/等待smoke；**没有数值比较**。源码的catch后状态可被PASSED覆盖，因此不能只读标签。 |
| vendor `df-bw`，1次 | 返回码0，PASSED；1GiB输入/输出的268435456个int32逐元素比较通过 | 真实设备搬运功能及host launch→wait2测量边界；未测试GEMM、BF16/FP32算术、GDN或完整模型。 |
| `examine -r all` | device healthy；AIE/memory-tile/shim/partition信息不可用，mem_topology报No such query request (148) | 现有CLI报告不能提供本研究的最低细粒度观测；不证明硬件内部没有PMU或其他API。 |
| 软件/编译器盘点 | 当前Python3.14、Anaconda3.12、uv3.11未找到onnxruntime/npu/pyxrt等Python包；Windows系统目录有XRT/ORT/VitisAI DLL及BF16命名xclbin | runtime部署文件存在；尚未认证可重编译的合法研究kernel、dtype/shape接口、输入布局或counter API。 |
| 已有llmSched | 离线compiler环境可import，已有512bit packed descriptors和估算报告；非Phoenix binary，无设备验收回执 | 可执行离线compiler基础，不是生产kernel或实测trace；不是R1所述TARS目录。 |
| 公开RTL/本地RTL盘点 | R5留存的是Gemmini来源片段；PATH缺构建工具，WSL无发行版；riscv_npu_alias只有3文档 | primary-source规则；**本轮没有RTL执行、目标性能校准或PPA验收**。 |

原始[设备清单](evidence/host_inventory.json)、[verify](evidence/verify_report.json)、[df-bw](evidence/df_bw_report.json)、[全报告](evidence/device_report_all.json)与[语义摘要](device_probe_summary.json)均有hash和执行回执。只盘点已列出的目录、环境与PATH，不声称穷尽整个机器。D:/riallto实际是旧driver/RadeonML发布包，不因目录名认定完整Riallto开发SDK已安装。

df-bw打印 `Total duration=0.359610s`、`2.780787 GS/s`。精确[XRT源码](sources/xrt/TestDF_bandwidth.cpp)用1GiB常量除以host chrono时间，数值对应单向逻辑payload的GiB/host秒；不是Gsample/s，也不是实际AXI accepted/completed bytes。计时不含初始化、输入同步、输出同步与逐元素验收；完整进程耗时5.667s另存。因此不把0.359610s称为设备kernel cycles或完整应用elapsed，不把两个逻辑1GiB相加冒充实际总线计数。

这只有单次能力探测，无锁频、无受控background、未保存input BO hash和设备地址；binary及DLL的hash在自测后盘点保存，不能回称为实验前固定合同。没有p95/p99、CI、速度提升或资源瓶颈主张。报告中的H=800MHz/MP-IPU=400MHz是事后静态快照，运行频率未采集；123W字段没有可认证的传感器依据，禁止用于功耗结论。

## 3. Strong static目前缺什么

现有copy自测不是研究的strong-static baseline。要开展H1，至少需要一个可重现的目标kernel包：支持的dtype/shape与完整输入输出oracle，compiler/runtime版本与命令，binary及layout/input hash，实际地址/alias/驻留/容量计划，真实可调的tiling、fusion、buffer、prefetch和资源序。不得将系统目录中名为bf16的xclbin视为任意BF16投影都已可运行；也不得将INT8默认RTL配置代入BF16结果。

以独立train相位优化有限静态候选，validation选择一次，再固定该合同测quiet与受控干扰。新compiler binary的收益单列；动态恢复必须绑定同一已选强静态合同，不能用另一份较弱baseline。当前没有这个目标合同，离线llmSched输出也未接入Phoenix，因此没有理由重跑旧模拟实验或增加ready策略。

## 4. 驻留边界：来源支持什么

[来源核验](source_evidence.md)和可重算的[residency_audit.json](residency_audit.json)给出batch=1、FP32 recurrent-state合同：

| 范围 | State存储 | 与R5的关系 |
| --- | ---: | --- |
| 1个128×128 head | 65,536B | 仍未包含工作向量/输出 |
| R5两个head | 131,072B | 每core一head，连4token prepared输入与输出73,760B/core；在假定128KiB/core下合法 |
| 官方单GDN层32head | 2MiB | 为R5假定两core总RF的8倍，仅说明同容量不能同时全驻留 |
| 官方24个GDN层 | 48MiB | 全部recurrent state；尚不含conv/KV、激活、权重、scratch |

普通串行自回归中，同一层下一token再次执行之前有31个其他层forward，外加同层剩余算子、logits/sample/embedding等工作；未来token的prepared q/k/v等不是提前已知。本轮拒绝把“四次连续局部更新”直接当“完整模型连续生成四token”。

**48MiB并不要求全部放RF，也不推出48MiB必须每token走外存。** 实际dtype、分片、片上其他存储、状态压缩和compiler spill位置都未测；Phoenix RF容量和可寻址性仍unknown。R5静态memory planning改善7.155%–24.027%仍是有效切片结论，既不扩成整模型收益，也不被本轮容量推导撤销。

## 5. 可执行测量程序与校准缺口

`capture_probe.py`保存显式命令、UTC起止、host进程elapsed、退出码、timeout和stdout/stderr原字节；`summarize_probes.py`拒绝PASSED附带Error的报告，并核对原回执hash和带宽算式。`residency_audit.py`验证冻结来源hash并重算存储范围。它们已经对真实回执/来源执行。

[measurement_schema.md](measurement_schema.md)、[模板](measurement_template.json)和`validate_measurements.py`提供后续记录的可执行入口：未知用null+原因，校验artifact/contract hash、split隔离、pair顺序、session、数值/overflow、实际traffic与观测边界，将screening与mechanism eligibility分开。测试数据明确标fixture；校验器**不计算或宣布5%性能通过**。当前无确认实验，train/validation/test样本数均为0，不将E0两次自测算为确认seed。

| R5最低合同项 | E0状态 | 下一步必须取得的具体证据 |
| --- | --- | --- |
| 正确kernel/dtype及strong-static | 只有int32 copy全量比较；verify非数值；BF16算术未执行 | 与本机旧Phoenix/XRT匹配的kernel SDK/ABI、可重编译微kernel与数值oracle、compiler memory/tile/prefetch导出 |
| elapsed | host launch→wait2和整进程时间 | 明确目标可见/retirement/fence边界；设备时间若不可用，维持host screening标签 |
| 实际bytes | 只有逻辑BO大小 | accepted/completed read/write bytes或可校验的bus/transaction trace；padding另列 |
| compute-active | 无 | 真实compute微kernel及定义清楚的active/starved计数；零/空运行对照 |
| request/limit/latency | 无 | 至少一个带接受/释放边界的request latency、outstanding/return limit或stall观测；先校验单搬运与counter wrap/reset/overflow |
| 频率/热与instrumentation开销 | 仅事后快照，无sensor轨迹 | 锁定或记录实际运行频率；采集开启/关闭对照及时间同步误差 |
| 受控background | 未建立 | 具名master、固定程序/输入、相位seed、offered与actual bytes，两个预登记等级 |

本轮已校验“测量程序到底测什么”，**没有完成性能模型参数校准**。缺接口时不填0、不用CPU测试补成NPU验证、不把公开RTL跑通当Phoenix校准。Gemmini另有BF16配置源码；需要单独配置elaboration、数值和RTL trace验收，默认INT8和BF16配置也不能混用。

## 6. Red-team → Decision与下一门

独立[红队报告](redteam_report.md)审查回执解释、驻留推导、测量记录拒绝路径和历史版本关系。关键修正是防止“另一个弱静态合同的动态对照”借用strong-static标签；同时保留vendor PASSED不可靠、source参数不是实测和input/频率未固定的限制。

下一步决策是取得**目标kernel/compiler合同和可认证观测接口**；若仍以本机Phoenix作为候选，只缺匹配当前driver/XRT的开发/trace入口，而不是一台泛泛的“NPU”。如果研究目标其实是R1 TARS，则首先需要其当前checkout与设备/RTL运行入口；当前找到的旧llmSched不能代替它。已向用户一次性询问目标/现有SDK位置，同时完成了以上独立工作。

接口具备后先做空运行、已知bytes搬运、单compute及instrumentation开销，10次pilot仅定工具与方差；随后冻结候选、背景等级与样本量。每确认条件至少30独立paired blocks，第二session新相位复验，train/validation/test隔离。沿用预登记5%净收益、95%配对CI下界>0、至少两个非极端干扰条件、quiet平均回退≤1%的研究筛选门。只有真实残差、强静态不能消除、因果观测、有限动作和收费收益全部成立才开机制；否则按合同关闭已测候选或转compiler。

**本轮结果是有实机执行支撑的测量能力决策，不是新的硬件收益结果。** R1–R5否定结论完整保留；没有增加模拟器复杂度、scheduler、RTL或PPA主张。
