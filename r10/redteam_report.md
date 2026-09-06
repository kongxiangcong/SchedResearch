# R10 Red-team：独立计算复核与未决边界

这是独立checker实现的计算审计及本任务的解释审查，没有第二位研究员或subagent审查，也没有实机验证。checker不导入model/runner；fixture producer和同引擎replay另行标注。

## 已通过的证据

- Stage A：960个候选由独立Cartesian生成器和R9冻结204项重建；两hardware各960合法、29项validation shortlist。8/8/30/30相位重建，选择与60组指标均值/95% t CI复算。384条详细trace、299,136 requests、28,392 compute/reduce通过。360个新static测试完整审计；旧static和C1N各12个首块trace审计，其他旧static elapsed不是逐request审计，但全部旧static下界由代表graph独立重算。
- Stage B：720条trace、561,600 requests、53,280 compute/reduce、360个baseline/causal配对通过。独立从enqueue/service时刻重建RR/FIFO默认head、local busy bit及收费逻辑，1440次观察、0次实际改序，每block实收8cycle。所有1440次观察中，另一侧local都busy。
- Bounds：30个fixture包含两hardware、credit1/2/4、广播开关、相位0/8191、两次显式R9式单动作，以及tiny两序两相位。独立算法核对lower_bound<=elapsed；人为抬高tight/删去credit项两例检出。tiny仍是local-visible终点，不是主图最优证明。B漏收观察费检出；本轮没有对B实际触发分支取得主workload执行覆盖。
- R9基础模型在r10逐字节复制，没有修改图、服务、address或仲裁语义。B副本仅新增固定观察分支；复制的R9 trace validator允许0/2/10费用，并把“改序次数”与“收费观察次数”分开计数。没有为通过审计放宽bytes/credit/visibility/工作保持条件。

## 主动质疑与判决

| 质疑 | 检查与结果 |
|---|---|
| 新下界把既有等待当必需等待？ | 只读graph work、绝对供给和Q；没有使用baseline内生等待。blackout bound只限制read-local服务，write-local全部放松，不把write停供期间错误禁止。 |
| 把多个下界直接相加导致过强？ | 使用max；credit、dependency、blackout均独立必要条件。proof与独立补集积分有不同实现。有限fixtures与数值核对不能代替适用假设，证明范围限固定graph/Q。 |
| 上界收紧就算实际性能收益？ | 明确分为旧static旧界、旧static新界、实际static elapsed差和新static新界。EXT128约8个百分点的收紧不是恢复了8%执行时间。 |
| 960项是静态全局最优？ | 不是。无新增tile尺寸、三buffer、packet尺寸、任意node priority、全顺序等。范围刻意有限，不能否定所有compiler优化。 |
| quiet reverse优于forward？ | elapsed相同的ID tie-break；报告不把reverse当收益。 |
| DMA32约0.106%可算机制成功？ | 是20%背景下W先的极小static参数效应；35%为0。名义CI未做多重比较校正，更远低于5%。 |
| B近零gain证明实际改序无价值？ | **否。实际改序0次。** 两cluster RR的已测早期连续read窗口内，另一cluster刚收到read，local始终busy。该触发器找不到它假设的idle receiver。只拒绝此固定观察规则，不拒绝实际可触发的其他动作。 |
| B少量正gain没有动作是错误？ | 2cycle观察收费四次，改变后续内生排队和与绝对预留相位的关系；独立完整trace与同引擎重放核对。不能把小正值归到未发生的改序。 |
| quiet回退<=1%就可进入硬件探索？ | 否；5%净gain、正CI、两个背景/两session等条件缺一不可。本轮两个hardware都未过，且没有真实目标/PPA。 |
| 用test调触发阈值或再挑窗口？ | 没有。B只有一条预登记固定规则；保留未触发负结果，未追加第二轮追正规则。train/validation为该固定规则诊断，不是择优池。 |
| 历史R9的35%关闭门被新下界替换？ | 没有。R10新参数新确认单独登记；R9的5.157867%与原失败判决不改。R10自己的严格逐block门也失败。 |
| 模型性能是不是数值正确或实机接受？ | 不物化每trace BF16乘加；沿用来源跨度→compute tile身份检查。研究FP32 split-K许可不等于官方bitwise/质量。没有TARS、完整NoC/peer/chiplet、RTL/PPA或实机session。 |

## Accept / Refine / Reject

Accept串联供给导致部分上界松弛的条件性证据，以及固定范围内的实验可复验性。Reject已登记四次busy/idle观察规则能达到机制收益门的主张。Refine余下约10%–13%平均upper：供给约束仍可能不够紧、静态池仍有限、真正可触发的动态动作仍未判明。不能从这个负结果关闭所有EXT选序，更不能重开R5通用ready或宣布新硬件必要。

下一次有判别力的进展应是完整外存Y终点的小图顺序/credit证书与实际可触发观测，而不是拿本轮test重新选择阈值。两模拟session的抽样不替代实机session；所有模型费率与观测能力仍需目标合同/PPA校准。
