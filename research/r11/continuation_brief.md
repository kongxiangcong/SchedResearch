# R11 用户确认的收敛实验交接

日期：2026-09-05。状态：用户已同意方向与开启新任务直接实施。本文件整理本轮讨论的最终窄范围；优先于此前回溯报告较宽的“驻留、分片、分层存储”建议。尚无R11实验结果。

## 已确认的结论

R1–R10正式编号候选台账有15项，不等于15个独立贡献。已测通用completion-ready不支持新增硬件；R9/R10额外EXT选序未获支持，R10虽然全部跑完，但0实际改序，不能证明所有改序无价值。当前停止动态机制搜索，不继续R10换触发器，不把残余upper当收益。

R5和R8/R9是两个工作负载上的观察：R5发现保留state可减少本地重复搬运；R8/R9发现分工不同会改变复制与partial搬运。它们不是一个必须串行完成的项目。本轮只回到R5的正信号，借用后续严格账本/审计方法；不同时启动分片、新存储硬件或scheduler。

R5事实：两个GDN heads，4个已prepared token，每core一个65536B FP32 state，输入输出加总73760B/core，在假定128KiB RF/core内合法。静态驻留四条件elapsed改善16.013%、24.027%、7.155%、11.853%；resident B0=S，B2退化。本地state-transfer bytes从1048576降至262144，外部state bytes仍131072。不是完整模型、跨层decode或新硬件收益。

R6约束：完整单层32heads的FP32 state为2MiB，24层为48MiB/B1。同层下一autoregressive token前有31个其他层forward；未来prepared q/k/v不能提前送给当前kernel。48MiB既不要求全放RF，也不推出每token必须全走外存。

## 本轮唯一问题

**完整GDN单层、真实输入可用顺序下，静态驻留能否合法地减少重复state搬运，并保留足够的最终elapsed收益？**

不是新硬件设计轮次，不承诺完整模型提速或论文新颖性。用户授权自行选择并集中登记参考硬件与必要假设，后续替换真实目标；不等待真实TARS、设备或SDK来启动参考模型实验。

## 首先读取和核验

1. `analysis/r1_r10_research_retrospective.md`、`analysis/r9_r10_convergence_review.md`、本交接和 `research_progress.md`。本交接的窄范围为最终用户确认。
2. `r5/experiment_report.md` 第5节、`r5/redteam_report.md` 驻留控制部分、`r5/resident_control.py`、`r5/resident_control_results.json`、`r5/resident_control_independent_audit.json`；需要时读 `r5/model.py`、`r5/resource_sim.py` 和来源合同。
3. `r6/experiment_report.md` 第4节、`r6/source_evidence.md`、`r6/residency_audit.json`，沿冻结官方来源核对真实单层算术与输入生命周期。
4. `r10/check_results.py`、`r9/check_results.py`、`r8/check_history.py`、`r8/check_results.py`只读执行确认历史。R10 1148 named artifacts、R9 648 named artifacts不能更改。

## 先预登记，再实施

在看到R11性能结果前保存experiment_plan、集中hardware/source/数值合同、候选/输入划分及判决规则。以真实来源重建完整单层32heads，验证全部输出和最终state，不能只有两head放大计数。计时若不物化每trace算术，必须明确独立数值oracle与性能执行的证据边界。

分别处理两种输入合同：

- 来源支持的合法已知token块（例如prefill）：先证明哪些prepared输入可同时获得，生产/缓冲成本及其他存储占用照计。不能凭名称假设四token免费同时可用。
- 严格autoregressive decode：不得提前提供未来输入，不得无成本假设跨其他层保持RF。单层的token间输入release/存储占用边界必须显式声明，不用任意有利间隔制造收益。

这两种合同用于限制同一驻留假设的适用范围，不扩成两个大工程。可以得出“仅合法token块成立、decode关闭”，但不得把一个模式的正结果推广到另一个。

主比较：相同完整工作、容量、数值顺序、初始state位置、逐token输出与最终state位置下，强化的非跨token驻留静态baseline vs 合法驻留静态方案。两边给予相同tiling/prefetch/资源顺序优化预算；必要时有限head/token/tile顺序仅作为静态控制。已有硬件就能实现的收益归compiler。不能免费增加RF、VMEM、带宽、跨层持久性或预知输入；不要混合R5和R9的硬件参数而不说明新合同。

先完成最小功能/触发资格检查：证明两lowering合法且确实产生不同state传输量；若全层容量或输入生命周期在所有预登记适用模式中已解析排除收益，可形成带可复算证书的关闭结论，不为形式上凑大实验继续跑无效干预。

通过资格检查后：用新的独立train/validation/test输入与外生相位，完整重算各计划内生排队。记录逐层级state/operand实际bytes、容量峰值、transfer/visibility、最终elapsed与必要下界。优先quiet和一个事前固定的非极端背景，不进行追正参数扫描。强静态选择不读test。

## 必须形成的判决

性能效应门建议预登记为至少5%的净单层elapsed改善；这属于R11自己的探索门，不改写前轮门。随机背景确认使用两组独立模拟相位、每条件每组至少30 independent paired blocks、95%paired CI下界>0。确定性条件报告精确差分及独立功能/模型复核，不把重复相同执行当独立统计证据。具体候选、主条件和门必须在性能首跑前固定。

最终报告必须明确给出范围内的投入决定：

- **成立，可以继续探索**：至少一个事前指定的真实合法输入模式，在完整32heads、共同成本和强化baseline下通过预登记性能门，且数值/容量/生命周期/独立审计通过。指出仅适用于哪个模式，是compiler驻留正信号；下一阶段才考虑迁移，不能自动提出新硬件。
- **本轮未获支持，方向关闭**：预登记模式中，容量/真实输入顺序消除了原复用机会，或完成实验后收益不达门。关闭的是该完整单层静态驻留候选的继续投入，不伪称所有驻留优化的数学不可能性。保留负值与证据，不用同批test改参数继续追正。
- 如prefill成立、decode不成立，分别判决，总结为仅保留明确的正范围。不能只写笼统Refine或再次只交计划。若实现/审计失败，应先修复再下科学判断；真实无法完成时如实说明阻塞，不能把缺证据伪造为实验证伪。

闭环顺序：Research Question → Hypothesis → Strong Baseline → Discriminative Experiment → Result → Red-team → Continue/Close。复核要独立于被测实现重算关键bytes/时序/统计；可遵循新任务实际技能与multi-agent规则，不继承旧主动委派权限。

## 历史与交付

目录非Git仓库；全部新实现/结果放r11。旧模型只读或复制到r11并标明版本差异，不覆盖R1–R10、根README、旧manifest。本交接创建前已保存R10最新根进度父快照，R11新父子关系见history_lineage.json。根research_progress只允许在保留原字节/全部旧行顺序的基础上追加计划与实际八字段结果；完成时保存R11 successor及独立结果清单。

交付：预登记、来源/硬件/数值与生命周期合同、可执行runner与checker、原始结果、独立审计、完整报告、简短成立/关闭结论、复验命令和更新后的进度。新任务直接做完，不再询问是否开始，不回到广泛环境搭建，也不启动R10额外收尾实验。
