# R9–R10 科研收敛独立审查

本文件是 2026-09-05 对冻结 R9–R10 的新增独立解释审查。只读了原始计划、结果报告、下界证明、审计及完成回执，并直接复算 Stage B diagnostics 的动作计数；没有重跑实验、改写历史判决或修改冻结工件。R10 历史报告所说“当时没有第二位研究员或 subagent 审查”仍成立，本文件不能反向改写它。[R10 历史审查范围](D:/dsh-proj/SchedResarch/r10/redteam_report.md:3)

**本次判断：已经足够决定停止投入当前具名动态机制，但不足以证明共享 EXT 上所有合法选序都没有收益。** R9 已测单动作族、R10 四次 busy/idle 规则均应维持 Reject；R10 剩余约 10%–13% 平均恢复上界仍是未决的数学/算法空间。这个区别允许现在停止机制开发，而无须先完成一个全域无收益证明。[R9 决定](D:/dsh-proj/SchedResarch/r9/experiment_report.md:107)、[R10 决定](D:/dsh-proj/SchedResarch/r10/experiment_report.md:48)

| 待判断问题 | 已有证据 | 本次判断 |
|---|---|---|
| R10 是否实验没跑完？ | Stage B 回执为 COMPLETE，360 test 配对、720 traces、96 diagnostics；两个 hardware gate 均 false。1,440 次 A/B elapsed 重放回执为 PASS。[完成回执](D:/dsh-proj/SchedResarch/r10/causal_results/completion.json:2)、[重放回执](D:/dsh-proj/SchedResarch/r10/replay_receipt.json:2) | 已登记实验跑完；不能把未获正结果称为实验尚未完成。这里引用的是已保存回执，本审查未重新运行 checker。 |
| B 是否有效否定实际改序收益？ | 360 test 块实际动作 0 次，1,440 次观察全部见另一 local busy；主 workload 没有覆盖实际触发分支。[审计回执](D:/dsh-proj/SchedResarch/r10/causal_results/audit_results.json:11)、[覆盖限制](D:/dsh-proj/SchedResarch/r10/redteam_report.md:9) | 否。干预没有发生，实际改序的效果没有被识别。它有效否定“这个固定观察窗口和 busy/idle 触发规则可带来 5%”的主张。 |
| 是随机没触发还是触发假设不适合？ | 规则只在 EXT epoch 64–67 观察；已测连续 read 窗口中，RR 刚给另一 cluster 送过 read，另一侧始终 busy。[登记](D:/dsh-proj/SchedResarch/r10/causal_plan.md:5)、[机制解释](D:/dsh-proj/SchedResarch/r10/redteam_report.md:22) | 当前证据直接指向该观察窗口缺少其假定的 idle receiver；没有证据表明增加相同分布样本会修复识别问题。此判断不外推全部 epoch 或其他 workloads。 |
| R9 大 gap 是否已解释？ | EXT128 固定旧 static 的上界均值从约 17.8%–18.3% 降到约 9.6%–11.5%；DMA32 收紧小，35%尤其小。[同一 static 的旧/新界](D:/dsh-proj/SchedResarch/r10/experiment_report.md:14) | 部分由松下界解释，尤其 EXT128；没有把余量归因唯一化。收紧约 8 个百分点不是执行速度提升 8%。 |
| 960 静态候选后能排除 compiler 优化？ | DMA32/20% 两组实际改善 0.105187%/0.106113%，名义 CI 下界为正，但35%为0；仍未覆盖新 tile、3-buffer、packet size、任意 node priority、全顺序。[实际差分](D:/dsh-proj/SchedResarch/r10/experiment_report.md:18)、[有限搜索](D:/dsh-proj/SchedResarch/r10/redteam_report.md:19) | 排除了“已搜参数交互能消除该大 gap”这一强解释；没有排除所有静态优化。0.106% 只能归 compiler 参数效果，且没有多重比较校正。 |
| 可以进入最小硬件机制或 PPA？ | 原门要求每 hardware 的两个背景、两组 session 均达到净 gain≥5%、paired CI下界>0，每格≥30配对块且 quiet回退≤1%。两 hardware 都失败。[原门](D:/dsh-proj/SchedResarch/r10/causal_plan.md:11)、[结果](D:/dsh-proj/SchedResarch/r10/experiment_report.md:44) | 不可以。quiet 小回退只满足一个必要条件；没有机制正接受，更没有实际目标/PPA接受。 |

**0 动作需要分两层解释。** 对“固定规则能提升 elapsed”这个 proposal，实验有判别力：它确实运行、收费、没有触发，也没有过门，故应拒绝，而不是无限延长。对“任何可观测动作能利用剩余空间”这个更宽 proposal，本轮没有产生处理组和对照组之间的实际改序差异，因此识别失败。这是实验设计对核心问题覆盖不足，不是算力不足或漏跑 test。直接读取 `diagnostics.json` 得到 96/96 的 `action_applied=false`，与 test 的 0/360 一致；原登记又明确 train/validation 只是固定规则诊断、不得调参且必须跑完 test，所以继续完成 test 符合当时登记，但不新增真实动作效应的信息。[诊断原始数据](D:/dsh-proj/SchedResarch/r10/causal_results/diagnostics.json:1)、[诊断用途和完整执行要求](D:/dsh-proj/SchedResarch/r10/causal_plan.md:9)、[未触发结果解释](D:/dsh-proj/SchedResarch/r10/experiment_report.md:28)

**大上界不是一个有 10% 收益的 proposal。** 对固定 graph/Q，若真实可达最优为 T*、已证下界为 L、当前 static 为 T，则 L≤T*≤T，因此 0≤(T−T*)/T≤(T−L)/T。右边约 10%–13% 并不给左边任何正下界。R10 的 lower bound 取多个必要条件的 max，并继续放松排队、依赖干扰和部分 local 服务；它没有求出完整主图最优序列，也不能把某一 mapping 的下界直接作为所有 mapping 的公共下界。[证明方向及范围](D:/dsh-proj/SchedResarch/r10/bound_proof.md:3)、[具体放松](D:/dsh-proj/SchedResarch/r10/bound_proof.md:6)、[结果未决](D:/dsh-proj/SchedResarch/r10/experiment_report.md:50)

R9 主参考的结论比 R10 敏感性范围更接近可停止：干扰慢约25%/53%，但平均恢复上界仅约1.6%–1.9%；已测收费单动作最高条件均值0.0210%、CI跨0、35%为0。这支持“不为已测动作族造 scheduler”。不过 R9 的35%已测最大上界5.1579%使事前逐block全小于5%的强关闭门失败，不能被平均值替代；R10新硬件范围也继续失败。因此“工程上停止”与“原强关闭门通过”必须分开记录。[R9 指标](D:/dsh-proj/SchedResarch/r9/experiment_report.md:63)、[关闭门边界](D:/dsh-proj/SchedResarch/r9/experiment_report.md:71)、[R10 新门结果](D:/dsh-proj/SchedResarch/r10/experiment_report.md:24)

**收益方向的证据分级。** 已看到较大的合法静态 mapping/traffic 差异：主参考相同四核预算的 C2K 相对 C2N quiet 快14.5514%，来自减少重复 X 外存流量并支付真实 partial staging；这支持继续分析 compiler/数据移动合同，但不构成新 scheduler 或新架构的收益。既有训练还展示 multicast、outstanding 和 gather 的价值，属于解释性训练对照，不能冒充新的独立 test 消融。R10新确认只有 DMA32/20%的约0.106%静态效应。当前没有稳定≥5%的新增动态机制收益。[mapping 和真实 bytes](D:/dsh-proj/SchedResarch/r9/static_interpretation.md:17)、[四核比较](D:/dsh-proj/SchedResarch/r9/experiment_report.md:47)、[训练证据界限](D:/dsh-proj/SchedResarch/r9/static_interpretation.md:39)、[R10 小静态效应](D:/dsh-proj/SchedResarch/r10/experiment_report.md:23)

**建议停止的范围。** 现在停止以“均匀 Qwen down 切片上剩余 upper 足够大”为理由继续开发 busy/idle 类 EXT 动态仲裁、继续扩大相同窗口样本、或者开始RTL/PPA。继续换一个触发窗口再跑数百块，很可能只是依次排除弱规则，而不回答是否存在≥5%信息价值。这个资源分配建议来自两轮实际动作证据弱、R10零触发以及现有 gap 的非可达性，不是声称已证明所有合法动态选序无益。[R9 有界回看](D:/dsh-proj/SchedResarch/r9/experiment_report.md:77)、[R10 固定观察规则](D:/dsh-proj/SchedResarch/r10/causal_plan.md:5)、[R10 未决范围](D:/dsh-proj/SchedResarch/r10/redteam_report.md:31)

**若必须完成这一支的科学收尾，只建议一次有界补实验。** 以下是本次新增建议，尚未执行，也不替换 R9/R10 原门：

1. 事前冻结预算、workload、两hardware和动作族，目标为“完整 compute→外存Y 终点的空间证书与动作机会”，不是再提出一个 scheduler。先在开发相位检查是否存在合法动作、它是否改变最终 Y 完成、收益来自改序还是观察造成的等待。小图 exact 应包含完整终点；它用于验证证明/模型，不能直接关闭完整 Qwen 主图。R10当前tiny只有local-visible，正是需要补齐的证据缺口。[当前tiny边界](D:/dsh-proj/SchedResarch/r10/redteam_report.md:9)、[原报告后续方向](D:/dsh-proj/SchedResarch/r10/experiment_report.md:50)
2. 优先求适用于完整已选 graph/Q 的更紧顺序/credit 放松，或对严格具名动作族给出完整机会枚举。若证书证明各预登记条件每个已测块的上界都<5%，可按新登记门关闭该范围；若只穷举最多一次改序，最多关闭该一次动作族。有限小图、有限phase、有限动作的证书不能外推所有多次动作和连续phase域。[下界范围](D:/dsh-proj/SchedResarch/r10/bound_proof.md:3)、[原逐block门](D:/dsh-proj/SchedResarch/r10/experiment_plan.md:15)
3. 只有找到实际改变最终Y且值得收费因果选择的机会，才登记一个新的规则并使用全新 train/validation/test。机会筛查中的未来信息只能标为 oracle/回看；必须证明当前观测可区分该行动，并和强静态及“只等待同样费用”控制对照。特别注意，免费单动作并非自动上界于同一收费动作：新增等待可能改变绝对预留相位，所以要么在 oracle 中允许包含费用导致的等待，要么保持同一收费动作类；不能用简单减费伪造有界收益。[收费改变时序的已有反例](D:/dsh-proj/SchedResarch/r9/static_interpretation.md:68)、[R10 观察费效应](D:/dsh-proj/SchedResarch/r10/redteam_report.md:23)
4. 预算用完仍无可行动机会、仅剩松 gap，或新因果规则仍不能满足原≥5%等门，即停止该支并记录“缺少支持该 proposal 的证据”；不是声称全域无收益。只有完整达到机制门后，才值得最小机制探索。两组模拟phase session仍不是实机session。[机制门与证据层级](D:/dsh-proj/SchedResarch/r10/experiment_plan.md:17)

**回溯建议。** 回到 R9 已站稳的“共同外存起终点、完整 traffic、强静态、供给下界”问题定义，并和更早轮次的正收益证据一起选择新的 workload/数据复用问题。若继续研究动态信息价值，下一 proposal 必须先有“同一固定静态顺序无法同时适应，而运行时可观测状态能够区分的需求差异”的具体场景，再问一个有限观测能否带来净收益；不要仅因当前均匀切片仍有松 upper 而继续。R9–R10本身不足以指定哪个更早 proposal 是最佳回溯点，需由R1–R8全局审查决定；它们足以说明当前触发器支线应停止。[R9 稳固的建模与strong-static证据](D:/dsh-proj/SchedResarch/r9/experiment_report.md:107)、[R10接受与未决的界限](D:/dsh-proj/SchedResarch/r10/experiment_report.md:48)

本审查的最终状态建议是：**R9已测单动作族 Reject；R10四次 busy/idle规则 Reject；供给约束解释部分 gap Accept；均匀切片上“剩余动态恢复空间”科学上未决，但机制投资决策可收敛为暂停/停止；最多保留一次有固定预算的空间证书补实验。** 没有新增性能结果，没有实机或PPA接受，不重开R5通用ready。
