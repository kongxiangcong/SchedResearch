# R13 小图实验方法独立审查

2026-09-08。本文只审查当前 [proposal_contract.md](proposal_contract.md) 下的小图实验设计、已有运行证据和可支持的结论，不扩张候选集合，不实现性能 runner，也不改变 M0/M1/M2 门。**P0 与 P1 最后都完整枚举相同集合时，零最优值差距首先是有限集合上的数学事实，不能包装成“原 TETRA/SoMa 启发式已被证明普遍足够”。** 应将该最优值证书与穷举前各方法的搜索表现分开。

## 1. 当前 C 究竟包括什么

本次检查 [model_builder.py](model_builder.py) 的 `small_plan_space`（299–310行）、`micro_graph`（313–365行）及其路由、内存、事务和完成语义。构造共有：

| 维度 | 当前选择 | 个数 |
|---|---|---:|
| Producer位置组 | 活动tile的前两个或后两个；组内chain顺序固定 | 2 |
| Consumer位置顺序 | 另外两个tile的两个排列 | 2 |
| 输入placement | 同channel别名 / 同组另一channel / 另一组 | 3 |
| NoC三元组 | load、peer、output各选0/1；两条chain、所有epoch共享此三元组 | 8 |
| 初始发送窗口 | 仅chain1、epoch0的首次load绝对release为0/32/64 cycles | 3 |
| source复用等待 | 前一peer的source_observed或ACK observed；全图共用该选择 | 2 |
| 合计 | `2*2*3*8*3*2` | **576** |

这576项是参数向量的显式有限全集。合法全集应定义为 `V={p∈C | F执行终止，且共同资源/值/生命周期检查通过}`；非法、死锁、未完成者不当作高延迟合法样本，所有失败ID和原因均保留。如果V为空，不存在可报告的有限最优值。

当前C**没有**一般tiling/fusion、额外source/receive/result slot、任意事件锚定发送窗口、独立per-transfer或per-epoch NoC、一般资源顺序变量。Compute角色位置也只覆盖4种安排，不是4个具名角色的24种全排列。所有输出固定到group1/channel0的`(0,5)`端点；chain0输入固定group0/channel0，只有chain1输入选择上述3种placement。它也没有完整MLP的MAC/数值/分块结构。

因此，当前C可以作为第一版可穷举的具名资格空间，但报告应明确它是对主合同开放决策的**收窄实例**。`chain1_offset_cycles`不应被写成已经实现了一般send-window优化；`source_wait`不应被写成完整SoMa内存分配算法。不能以“对C公平”证明已经给所有原生编译器/所有合法计划同样自由度。

## 2. P0穷举兜底之后，零差距能说明什么

令 `F*(C)=min_{p∈V}F(p)`，F为同一精细模型、同一输入/输出状态和参数。若P0最后的增强层确实检查了整个C，则 `F(P0-exhaustive)=F*(C)`。同样限定在C的P1不可能更小；若P1也枚举整个C，两者等值按定义成立。发现非零“P1超越P0全集最优”应先调查非法样本过滤、遗漏候选、不同资源/输入、评价口径、未完成枚举或实现错误。

| 观察 | 可支持 | 不可支持 |
|---|---|---|
| 两侧完成C后差距0 | 在这一模型、参数、合法集合、预算足够穷举的条件下，没有剩余目标值空间；不值得为当前C继续增加求解机制 | 普遍H0；完整MLP没有价值；联合编译无价值；原TETRA或SoMa启发式已达到全局最优 |
| P0普通细化在穷举前已达到F* | 这些具名细化方法在该小图、该搜索预算下足以找到C内最优；记录首次达到最优的调用数与时间 | 大规模可扩展性，未开放窗口/tiling上的最优，实际芯片加速或论文新颖性 |
| P0只有枚举完毕才达到F* | 一个可复现的有限空间oracle/工程兜底；不能将穷举替换算法之后的零差距归功于原启发式 | “已有强编译器轻易吸收全部收益”或启发式搜索效率结论 |
| 粗估价选中p，F(p)>F* | Hmodel在当前合法集合上的regret，需进一步给出具体遗漏耦合 | 新编译算法贡献、动态硬件必要性、完整模块3%门通过 |
| 某些同预算前缀下P1较好，最后都归零 | 有限搜索预算下的搜索质量信号，值得单独报告 | 信息价值或硬件能力优势；不能把有限预算差距说成突破静态最优 |

建议同时报告 `upstream_seed`、`tetra_port_refined`、通信感知候选、具名lifetime/window邻域、`P0-exhaustive`与独立exact枚举器。最后两者可以共享已核验的F表来节省执行，但算法轨迹必须按其事前规定的访问顺序记录；不能先看F全表再把最优ID放进P0/P1的第一个邻域。

主对比保留穷举前每个阶段的候选ID、合法性、incumbent、累计F查询数、实际新增F计算数、solver wall time、seed生成时间和未用预算。至少保留共同前缀budget；如果只控制F查询数，没有控制真实求解/生成墙钟，结论就限定为**相同F查询预算**。使用缓存重放出的查询序列也不能被当作实际编译墙钟。原TETRA seed的真实求解费用不能静默免费，完整C枚举费用不能只算给一方。

一条合适的最终措辞是：“在已冻结的576项小图集合C上，P0增强组合经过完整枚举达到该集合的精确最优；P1没有额外目标值空间。穷举前的启发式表现另列。该结论仅关闭当前集合上的新增算法收益主张，不外推到完整MLP或未开放决策。”

## 3. 保留真实TETRA种子，避免归因被后端覆盖

[baseline_intake.md](baseline_intake.md) 与 [target导出](artifacts/tetra_micro_p0000_target.json) 已记录实际运行原scheduler/TETRA/GSCIP，同时增加显式physical IO、12个channel容量身份及合法payload路径。这个成果是实质性的源/后端接入。当前记录仍明确 `r13_p0_qualified=false`、`completion_and_control_semantics_qualified=false`、`window_refinement_completed=false`，原分析latency626不是F的时间。

还需避免三种偷换：

1. `p0000`的计算位置和外层NoC已由输入固定；原TETRA在该输入内求解，不能称它独立从576项中发现了p0000。保持这一候选生成来源，随后外层展开/邻域修改使用另一个清楚的名称。
2. lowering若改变原slots、buffering/reuse或张量驻留决策，应保存原决策、改变后决策及原因。目标地址复用恢复与合法控制补齐属于具名后端适配；若原schedule次序被完全覆盖，最终不能仍叫“原TETRA schedule”。
3. 自写source/ACK二选一加窗口邻域可以称受已有生命周期方法启发的常规细化，不能称已经复现SoMa搜索器。精确枚举器也不是新P1算法。

同空间允许P0访问全部C是公平性的重要条件，但**允许访问**、**已有方法能表达**、**实际在预算内找到**是三件事。最终表格应该分别证实，不用一个总PASS替代。

## 4. 三见证族须先按账本选pair，再读取timing

配对程序先只读源/所有权、地址、packet和资源账本。保存全部合格pair或按事前确定的ID顺序选代表，冻结pair ID及ledger hash，之后才关联F时序。既有单元资格trace的时间可以用于模型检查，但不能据它挑选更大收益的见证pair。没有严格配对时报告未找到及混杂项，不临时改变C、packet类或归因规则。

完整1KiB、两链两代图应包含40个packet、424个network flit：4个read request、4个33-flit read response、8个33-flit peer/output write、8个单flit通知/返还token、16个单flit write ACK。每条flit路径另含两段NIU邻接，所以固定848个NIU flit-hops。该静态数量由当前代码合同推导；实际执行必须另核对resource launch ledger。

不能以`payload_bytes*hops`替代全部网络服务：立即通知的逻辑payload是4B，但携带它的header占一个32B flit。建议保存十种事务角色的独立向量：load request/response、peer data/ACK、notify data/ACK、token data/ACK、output data/ACK。每项同时列packet数、flit数、router flit-hops、NIU flit-hops、logical payload byte-hops。`32*flit-hops`表示有明确单位的网络承载量，不能与仅逻辑payload byte-hops混用。内部credit目前为注册的独立延迟token，不是模型中不存在的NoC payload packet。

### W1：等总量路径分布并不自动等于纯链路争用因果

本次只做静态算术枚举，**未读取576项F timing**：固定offset=0和source_wait=source后留下96个空间/NoC点；独立按方向取模计算所有上述协议角色的路径，以placement和各角色全协议flit-hops向量分组。共有46对在此等量条件下、跨chain共享router-link负载不同；再要求每条具名packet的hop数也相同，配对数为0。

例：p0000/p0144具有相同placement和每种角色的全协议flit-hops，但跨chain共享router负载指标 `Σ_l min(demand_chain0(l),demand_chain1(l))` 分别为378/380；每条flow的路径长度分配改变了。此数仅为静态共享需求，不是实际排队时长。该次枚举没有写入或修改候选，也没有运行性能搜索。

因此当前C存在可用的**等总量空间/路由对照**，但不能单凭两项makespan不同就声称差异全部来自共享link争用。还应列出逐packet路径长度、每条链的无争用依赖关键路界、逐NIU/channel/bank负载和实际等待。如果per-flow距离或NIU争用也变了，按多资源/路径分布耦合解释。若要给纯link争用主张，需要满足更严格的控制条件；本次不扩C去凑该条件。

当前 [NPE投影](artifacts/npe_projection.json) 的overlap/separated仅含无ACK request；它可作局部服务控制，不能拿其“等request hops”替换完整协议pair资格。

### W2：channel与endpoint alias

最干净的C内比较是固定其他所有维度，仅将 `same_channel_alias` 改为 `same_group_other_channel`：chain1仍走`(0,1)`端点，相同packet路由，仅地址跨到另一物理channel。按实际block的group/channel累计服务，核对所有读写共用总预算；另一channel可并行是共同硬件预算中已有资源的合法利用。

`separate_group`还把chain1端点改到`(0,5)`，会同时改变路由、NIU和与固定output channel的争用，不能单独归因为“更多DRAM带宽”。两组都仍有相同12个物理channel；alias不能被计成新增容量或服务资源。完整账本应显示load和output的共同channel占用，不能只看输入。

### W3：完成事件与复用

固定除 `source_wait` 外的全部字段，source/ACK二选一具有完全相同源需求、物理地址、packet与资源账本。它是检验合法源提前释放的自然对照；必须在实际trace看到所有旧source reader完成、付费source_observed之后的新load issue，以及与旧peer ACK的时间关系。不能从开关名字推出已经发生了有效提前。

接收slot另须等consumer最后读取及实际token观察；结果slot另须等旧output的source读取及付费观察。通知必须既有实际控制word读取，又满足目标payload可见。报告输出可见、final ACK和quiescent三个时点，允许“发生提前但makespan无改善”的负结果。P0本来就应拥有合法source提前释放；它相对保守ACK等待的收益属于消融，不自动计为P1贡献。

## 5. 当前M0证据与尚缺项

以下是本次审查时的状态，后续新增运行应由正式M0报告引用对应回执更新，不能把本文的条件判断当作已执行：

| 检查 | 已有真实证据 | 尚未由该证据证明 |
|---|---|---|
| 数值/源需求 | 完整M1/32/128 CPU量化合同、独立需求回归通过 | 完整MLP物理分块、RF/L1容量和DES执行 |
| 状态机一致性 | 17单测、209差分fixture、8规则变异；[checker回执](artifacts/checker_differential.json) | 未执行的物理网络/工作负载路径及所有控制交错 |
| 构建器真实微图 | [checker_builder.json](artifacts/checker_builder.json)：64B NoC1及1KiB NoC0两张完整图与tick checker一致；52张图完成构造公式检查 | 52项不是已运行的时序敏感性；不自动覆盖576项合法性 |
| 16B值与复用 | [trace_qualification.json](artifacts/trace_qualification.json)：4张完整1KiB图、9非法变异；实际逐块/epoch/控制word检查 | 未观测交错的全序证明、任意byte mask、RF实体分配 |
| 三见证族 | 静态pair资格可建立；原request投影已有局部F趋势 | 完整协议三族的实际触发、逐资源归因、所选完整pair的共同checker结果尚需正式运行汇总 |
| tt-npe | 固定C++方向/API粒度与成本表源码核查 | 本轮跨工具**没有执行**：WSL返回E_ACCESSDENIED，NPE没有时间或趋势样本；不能引用R12历史PASS补齐 |

在进入M1性能归因前，实质上仍需把所选三族完整pair的功能、终止、解析下界、资源账本和独立回放接成一条证据链。对全部进入排名的C候选执行统一合法性检查；抽样tick差分不能替代每项值/所有权检查。对BN/credit等关键端点至少确认实际反压和终止行为，不能用52项构造成功推断时序稳健性。若网络结构或仲裁改变，则另列结构对照，不把它们称为随机误差或置信区间。

WSL受限只说明本轮NPE交叉参考缺失，不说明模型原则上必须上板；也不应改装多套模拟平台来回避记录。可以继续独立内部模型研究，但正式门判决必须明确“内部实现资格/限定跨工具未验证”的范围，不能把所有第7节验证层都写成已完成。

## 6. 本次审查覆盖

本次全文读取当前model_builder、hardware_model、machine_contract、trace_audit，以及baseline_intake的目标适配段、checker_design与已有checker/trace/NPE运行回执；定向检查port_micro_tetra的源图、main、真实求解及physical输入比较段。大型target导出只解析状态、源图/求解与physical输入摘要，未逐字人工阅读全部tensor数组。另实际执行上述96项静态全协议路径账本枚举，没有读取新小图性能排行、重跑F或修改模型。本文既不宣称M1已通过，也不提前宣称Hcompiler差距已经为0。

## 7. 名义全集及冻结见证完成后的独立复核

本节是随后真实运行后的追加，前文第5–6节保留当时的审查状态。实际输入为 [serial注册](preregistration_serial.json)、[576项名义结果](artifacts/micro_nominal.json) 和 [168项见证结果](artifacts/micro_witnesses.json)。独立复算保存于 [micro_independent_analysis.json](artifacts/micro_independent_analysis.json)。本次没有调用runner的rank/ledger函数，也没有导入或重跑DES/tick checker。

**覆盖和身份通过。** 独立重建笛卡尔积，576个参数向量、ID顺序、candidate SHA-256均与注册完全一致；名义结果恰好每个ID一次，无缺失、重复或额外项。独立重建的13点单因素与16点交互去重并集共24点，加两个非名义控制倍率得到26点；6个冻结见证覆盖26点及两项结构对照，共168个唯一配置。两份运行回执的source hashes、registration raw-byte hash与当前文件一致。

744个保存结果行均为valid/engine-ok，audit_passed=true且没有audit_failures，完整输出块数均256、unfinished=0，输出可见≤完成观察≤quiescent，tick/cycle换算一致。六个见证的名义重放与名义全集中的spec hash、trace hash、时刻和估价完全相同。168行实际link服务均等于逐link flit数乘36 ticks，channel服务均等于实际读写bytes除以注册的`24*eta_d`再换算ticks；每行40 packet、424 flit与848 NIU flit-hops账本一致。

这里“复核每行audit”指检查完整保存表中的审核回执与输出/终止字段，**不是重新运行744条值轨迹**。这两份摘要结果只保存raw trace的hash，没有全部raw trace bytes；本次不能单凭hash独立重新认证那些未提供的原字节。已有真正的逐块审计执行由各行回执及trace资格记录支持。

### 7.1 Exact与粗估价：区分严格错序和无法打破并列

从576行独立取最小值，C内exact输出可见为 **81,136 ticks（2,253.777778 model cycles）**，并列计划恰为p0024与p0072。该结果与runner摘要一致。以下regret统一使用`(F(chosen)-F*)/F*`，不是算法speedup指标。

| 粗估价 | 最小估价值 | 最小并列数 | 预登记字典序选择 | 该选择F / regret | 并列集合的F最小–最大 |
|---|---:|---:|---|---|---|
| payload router byte-hops | 59,392 | 24 | p0000 | 84,124 / 3.682706% | 82,512–94,780 |
| full-protocol flit-hops | 3,048 | 24 | p0000 | 84,124 / 3.682706% | 82,512–94,780 |
| dependency/declared-latency下界 | 42,392 ticks | 8 | p0000 | 84,124 / 3.682706% | 81,136–87,492 |

两种traffic估价的最小24项相同，最好的并列项为p0144/p0192、82,512 ticks。即使允许用F挑选这一并列集合中的最好项，仍比exact高 **1.695918%**，且两项exact的traffic分数严格大于最小值。因此可以确认：这些纯流量标量在当前C中严格排错了至少一组合法计划，最小值分辨不足不只是字典序偶然性。

第三项的最小8项是`p0000,p0001,p0024,p0025,p0048,p0049,p0072,p0073`，已经包含两个exact。**对这一最小选择问题，只能说粗下界分辨力不足，预登记字典序造成了3.682706% regret；不能把它写成该估价严格将p0000排在exact前面。** 二者在粗分数上相等。此处不推断该估价在全表其他位置是否存在严格错序。

`zero_contention_critical_path`代码标签对应的是仅含依赖与声明latency的DAG下界；它省略resource II，连单packet内部flit串行化也不计，不能解释为已经测得的无争用单流时间。nominal lexical enumeration在前48项已遇到p0024；这是顺序遍历覆盖事实，不是具名新搜索算法结果。完整strong P0 portfolio和Hcompiler仍未准入。

### 7.2 26点差值必须包含零结果

下表差值始终为 **a减b**，正值表示a更慢，单位为model ticks。26点是固定6个见证计划的重放；不会在测试点重选计划或重编译。

| 对照(a−b) | 名义output差 | 26点output差范围 | 负 / 零 / 正点数 | 观察 |
|---|---:|---:|---|---|
| W1 p0384−p0528 | 0 | 0–300 | 0 / 25 / 1 | 等总量链路见证绝大多数点没有输出改善 |
| W2 p0000−p0048（同组另一channel） | 0 | 0–0 | 0 / 26 / 0 | 分开输入channel并未缩短这组完整小图 |
| W2 p0000−p0096（另一group） | −7,888 | −26,928至−4,844 | 26 / 0 / 0 | 另一group始终更慢，且伴随端点/路由与output争用变化 |
| W3 p0001−p0000（ACK等待减source等待） | 3,368 | 0–6,108 | 0 / 1 / 25 | 合法source提前释放通常有益，但存在零收益点；这是P0也拥有的能力 |

唯一的W1非零output点与唯一的W3零收益点都是 **BN=1，其余参数名义**。W1在该点相差300 ticks，其他25点output完全相同；其final completion-observed和quiescent却在26点均相差300–324 ticks，名义差324。不能只展示尾控制差异便声称完整输出加速，也不能只展示output=0而隐藏尾控制变化。

W1两项全协议总量同为5,632 flit-hops，跨chain共享router需求分别为872/944，max单link需求均204 flits。这里共享需求更大的p0528反而清空较早；它不是“共享需求越少一定越快”的正例。per-packet距离、资源位置与排队仍是共同解释因素，不能由单个overlap标量推出因果。

W2两种对照和W3的final completion-observed/quiescent差值分别与其output差值相同。结构对照也保留：mono-bank名义下W3差2,868 ticks；descending tie-break下差3,044，而ascending/interleaved名义为3,368。W1两项结构对照仍是output差0、尾控制差324；同组另一channel仍全为0；另一group仍更慢。

### 7.3 本次能关闭的主张与仍然开放的工作

这次确认的是有限C中**纯流量估价的严格错序**、下界估价的并列分辨不足，以及完成/复用和资源位置在具名完整小图中的影响。26点并未重放名义exact的p0024/p0072，所以不能宣称它们的名义排名或3.682706%诊断regret已通过参数稳健性验证。当前结果也没有同模型强P0与新P1的公平算法比较，不构成Hcompiler或完整MLP/M2。NPE跨工具执行仍缺失；本次结果不改变该状态。
