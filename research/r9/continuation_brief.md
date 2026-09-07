# R9 交接：自主建立研究硬件规格，开始共享资源残差实验

用户在2026-09-05明确要求：**“同意你的下一轮计划，新开会话，开始下一轮的实施。硬件规格以你为主，你来建模，后续再替换成真实 TARS 规格。”**

这是新的执行授权。R8 的“等待当前权威 TARS 路径后才建具体硬件/时序合同”停止条件，**在下一轮研究模型范围内被该指令取代**。不要再追问TARS目录、要求用户提供硬件参数，或只交计划。直接选取合理、明确、可替换的参考硬件数值合同，实现并运行最小判别实验。真实TARS校准是后续阶段，不是本轮入口门。

## 科研目标与诚实边界

问题仍是：编译器完成合法 mapping/layout/驻留/tiling/prefetch/静态排程之后，**两cluster、每cluster两core**的具名共享资源是否留下显著损失？它属于不可避免供给、静态规划不足，还是在既有DMA仲裁之外仍有有限可恢复的信息价值？成功是有证据的Accept/Refine/Reject，不以得到正收益为目标。

R9 reference hardware是本轮明确被研究的对象，规格由agent选择并论证。参数及动作能力都标为研究选择，不冒充当前TARS事实。模型中的精确结果可以作为条件性架构结论；未经实机/RTL校准，不能称真实TARS残差、实际性能收益或PPA。硬件规格后续集中替换，避免把常量散落在workload/policy代码中；不为此建立多provider兼容平台。

## 首读与已完成证据

1. 根 `research_progress.md` 与本文件。
2. `r8/experiment_report.md`、`r8/target_contract.json`、`r8/source_contract_audit.md`、`r8/hierarchy_static_audit.md`、`r8/redteam_report.md`。
3. `r8/results/resource_payload_ledger.json`、`r8/contract_experiment.py`，需要时读完整数值NPZ；不要重复R8已过的CPU数值实验代替新进展。
4. `r5/measurement_gate.md`、`analysis/problem_definition.md`、`analysis/compiler_contract_requirements.md`；有用时读取既有request-level实现，先决定复用边界，不重跑旧大实验。

先运行 `python -X utf8 -B r8/check_history.py` 与 `python -X utf8 -B r8/check_results.py`。R8保存6账本、20core/100分配、18数值、70事件序；独立复算通过。原始R4–R7路径清单依旧完整。R8结论：静态mapping改变输入复制/partial代价，split-K不保证bitwise，精确wait/release能满足单payload安全；未发现实际硬件收益。

R5已测通用ready候选继续关闭（最好收费+0.1821%且CI跨零）；其负结果不外推未测多cluster。约33%旧投影差分不是固定binary实机干扰。GDN驻留正结果只覆盖2head/4prepared token。R7是Phoenix固定copy/INT8功能与host elapsed；本轮不回到SDK/PMU适配。

## 下一轮直接实施的最小闭环

1. **冻结参考硬件合同。** 两cluster×两core为主，一cluster×两core为局部控制。自主选定核心吞吐/geometry、可用VMEM/保留区、cluster DMA队列/channel/outstanding、全局共享外存服务、buffer/credit、completion时点与静态可调项。每个数值注明历史启发/公开规则/纯研究选择及敏感性范围；没有依据的参数也可作为显式假设，不伪称校准。先一个具名共享DMA/外存路径，不铺完整NoC/chiplet。
2. **固定真实来源工作量与合法性。** 优先承接Qwen down fullK9216/N128/M32；M1若纳入必须按参考硬件明示tail或padding并计实际工作。BF16输入/权重、FP32 partial与归约顺序由本轮数值合同明确许可，不能把实数等价偷换成官方bitwise。统一外存X/W起点和外存Y终点。N-shard/K-shard均进入静态候选；input multicast/外存staging/direct peer作为明确且分别收费的规格/路线对照，不能免费给某policy新增带宽。
3. **实现小而完整的资源执行路径。** 将账本落到actual modeled requests、容量/资源占用、prefetch/slot reuse和destination-visible事件；按bytes与共享服务推进，支持单次完成批处理、端到端结束判定与审计。模型背景服务使用共同、预登记的绝对时间到达/资源供给过程；不能把另一policy的请求延迟trace直接强塞进来或只按task抽随机时长。不要先写新scheduler。
4. **建立strong-static和下界。** 同资源预算搜索合法mapping、tiling、layout/驻留、单双buffer、prefetch/resource order/outstanding，允许已有work-conserving DMA仲裁；独立train/validation/test，tiny类做exact或可证明下界。区分同selected-static在quiet/干扰下的损失、静态变体消除的损失，以及同合同干预恢复的损失。不能比较两核/四核后把更多算力叫调度收益。
5. **预登记1–3问与判别实验，然后实际执行。** 至少回答：(a)损失主要由供给/严格依赖还是静态不足导致？(b)既有仲裁和更强静态之后有没有因果可观测的合法替代动作且改变最终结束？只在前两项显示空间时研究一个有界且收费的最小干预；模型内零成本oracle/单动作反事实可作筛查，不当可实现机制。
6. **Result→Red-team→Accept/Refine/Reject。** 保留负结果、故障fixture和全部复核材料。若最优/强静态接近资源下界或模型中的可恢复上界不足，就关闭该具名候选；若发现稳定条件性残差，报告所需参数范围、反例/失效区间、静态搜索缺口与最小后续验证。不要把任意挑出的极端参数正例当研究发现。

不要求用户为routine参数选择或每个ticket再次批准。以能回答问题的最小模型为止；增加复杂度必须说明将区分哪两个仍竞争的解释。可用独立审查方法；如果使用 research 等明确要求委派的技能，遵循该技能，否则遵循当前任务实际可用的多agent规则，不继承旧会话的proactive授权。

## 性能与机制门

参考模型可使用≥5%收费净elapsed、95%paired CI下界>0、每条件每session≥30独立paired blocks、第二独立相位集、至少两个非极端干扰、quiet均值回退≤1%作为**模型内筛查门**，并保留独立train/validation/test。模型session是独立生成相位组，不是实机session；若做有限分布全枚举，可给精确期望而不伪造CI。后续真实硬件确认仍必须独立满足原设备门，模型通过不能替代。

新硬件机制的最终接受仍需真实残差、strong-static不能消除、因果可观测、有限合法动作与收费收益。当前用户允许先在明确参考硬件上探索这种机会；因此不能因缺真实TARS规格而停止所有模型实验，也不能因模型出现正结果就宣称最终机制门已通过。

## 文件与进度维护

目录 `D:/dsh-proj/SchedResarch` 非Git仓库。新实现/计划/规格/结果放 `r9/`，保留R1–R8、根README及所有旧manifest。不要改R8被冻结的next_target_intake来覆盖历史；本文件记录新用户决策及其优先级。

交接已将当前R8根表备份到 `r9/history/r8_research_progress.md`，根表追加 `R8→R9：自主研究规格（计划）`，另有 `r9/history/aligned_research_progress.md` 和 `r9/handoff_integrity.json`。该manifest只冻结明确交接文件，不冻结未来整个R9。

R9实验前可补充新的事前计划；完成后保留本次计划行及原行，另加实际结果八字段行，并保存新父子关系。已有R8 checker会通过snapshot认证R8并允许后继根表新增行，不改其代码/清单。用户要求在新任务开始实施，收到本交接后直接推进到实质结果。
