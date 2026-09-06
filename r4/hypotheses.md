# R4 假设与机制台账

2026-09-05。Keep仅保留有边界的研究问题，不确认论文贡献；以下实际结果以 [实验报告](experiment_report.md) 与机器数据为准。预登记门：收费B2延迟降低≥5%，配对区间下界>0。后验诊断明确另列。

## H1：强静态后存在足以支付派发成本的完成顺序机会

- **Hypothesis**：真实来源的小图在优化fusion、地址、预取、双缓冲与资源顺序后，仍有显著、动态可恢复的等待。
- **Why it may work**：静态知道合法空间，却不知道本次DMA服务和外部master相位；独立head/FFN/query-row分支可能先完成。
- **Runtime uncertainty**：独立DMA外生服务因子、绝对时间背景服务；compute固定；自身资源排队重新产生。
- **Closest prior art**：SPDI、ASPEN、TaskStream、HwSch；强静态参照PipeThreader、Stream、LATTICE。
- **Difference**：本轮测试端侧固定mapping/address下的边际价值与成本，不把completion counter当新机制。
- **Strongest baseline**：S，24-priority池+128合法局部移动，独立train/validation；另公开S8和tiny exact。
- **Minimum experiment**：Qwen两类decode层、FLUX两类block，同图同地址同随机环境，比较S/B0/B2/B8/H2。
- **Expected observation**：收费B2通过预登记5%门，且可由trace解释为不可预见的合法producer先后。
- **Failure condition**：只在弱静态/未融合/零控制成本中出现小收益，或提前工作阻塞更关键消费者。
- **Actual result**：70配置×32test×6策略=13,440执行；B2/B8/H2全部配置mean为负。B0仅3正，最高+0.104663%；两个区间下界>0的小正例均在split-port Qwen，B2后消失。57配置耗尽局部搜索预算，不能宣称S全图最优，但本轮未支持收费动态扩张。
- **Keep/Modify/Reject**：**Reject当前代表性收益主张；Keep边界问题**。缩尺/未校准不能用于否定真实4B或其他动态策略。

## H2：仅改compiler priority即可恢复优化静态的选择质量

- **Hypothesis**：强静态改变资源顺序后，动态沿用原始CP hints会破坏已优化的预取/关键流；冻结静态发射序导出的priority可能显著减少退化。
- **Why it may work**：信息已由离线搜索得到，硬件只需要不同静态priority值，不需要新CAM/pressure算术。
- **Runtime uncertainty**：仍只使用当前completion/ready；静态priority来自nominal环境，不能读取test时长。
- **Closest prior art**：TaskStream size/core hints、ASPEN ready priority、LATTICE静态资源序；本轮无新颖性主张。
- **Difference**：隔离“动态算法提示不匹配”与“运行时信息没有价值”，是诊断消融。
- **Strongest baseline**：主实验S及B0/B2，mapping/address/reuse完全保留。
- **Minimum experiment**：S在nominal确定时长回放一次，以dispatch全序生成priority；全部70配置、同test seeds重新执行B0/B2；另对两小正例用训练B trace增加固定静态候选。
- **Expected observation**：若退化来自提示不匹配，B的负值缩小；如仍未通过成本门，不扩硬件。
- **Failure condition**：必须偷看test future、动态改mapping或增加资源才能得到收益；或提升仍不足付成本。
- **Actual result**：主结果后的后验校正共4,480次执行：B_order0为10正/33负/27零，B_order2为2正/68负；最佳+0.1968%，95%区间[-0.1522,+0.5458]，两个收费正例均跨零，仍无5%门通过。红队训练trace静态诊断在两配置都经validation选回原S，没有消除主B0约0.10%的微小正值。不得将后验选型后的相同test区间当新独立确认。
- **Keep/Modify/Reject**：**Modify**，提示一致性确能减少部分退化；保留为必要对照，仍不推进新的动态硬件。

## H3：attention融合与conditioning预计算后，剩余分支仍有价值

- **Hypothesis**：把可隐藏在kernel内部的attention阶段和每步共享conditioning移出调度边界后，completion-ready收益仍存在。
- **Why it may work**：双流后续FFN或不同head/tile依然可能独立完成；但预期机会变少。
- **Runtime uncertainty**：外部操作数服务和分支完成相位；没有虚构FLUX distilled的unconditional分支。
- **Closest prior art**：FlashAttention系列的IO边界、PipeThreader异构流水、Stream layer fusion。
- **Difference**：本轮只做数学aggregate边界与内部scratch收费，未实现FlashAttention或复现上述编译器。
- **Strongest baseline**：同一聚合图上的S，包含双缓冲与validation；原非聚合图仅作边界敏感性。
- **Minimum experiment**：Qwen full两head组attention聚合；FLUX double/single聚合+conditioning resident；保持输出/状态数值等价。
- **Expected observation**：净收益不依赖公开score/prob中间task，也不依赖重复计算全模型conditioning。
- **Failure condition**：融合后收益消失；隐藏中间结果实际上漏掉scratch/traffic；CFG分支不存在。
- **Actual result**：三个增强图在两种端口组织下均未使B2越过S；所有聚合score/prob内部scratch、读写流量与每core预留已显式计费。数值重排通过，聚合并非真实online-softmax kernel验收。
- **Keep/Modify/Reject**：**Reject本轮收益主张；Keep强融合边界作为后续最低要求**。

## H4：最小resource-aware修正足够，是否应保留更复杂调度

- **Hypothesis**：H只放开共享DMA/SRAM的ready仲裁、保留compute顺序，能比全B更好保护静态pipeline。
- **Why it may work**：大部分结构性决策已编译；只对真实共享资源到达差异做本地选择。
- **Runtime uncertainty**：DMA完成、可见事件与SRAM占有；无年龄/压力运算或未来服务时间。
- **Closest prior art**：VTA队列/依赖token、Gemmini访问执行解耦、传统self-timed多引擎队列。
- **Difference**：已知机制形态的成本对照，非新架构。
- **Strongest baseline**：S与B2；H2同样增量收费2cycle/task。
- **Minimum experiment**：70同预算配置，比较H2、B2与S；split-port对照允许同核MXU与VPU/DMA重叠。
- **Expected observation**：H2稳定胜S并保留更复杂B收益，而不用完整resource-order放开。
- **Failure condition**：H2仍慢于S，或优势来自复制端口、SRAM与控制服务能力。
- **Actual result**：H2在70配置mean均负。不同端口配置不是等面积；split-ports仅匹配128B/cycle总SRAM额定带宽，不能宣称组织本身免费。
- **Keep/Modify/Reject**：**Reject扩张当前H机制；Keep作为有源依据的弱动态基线**。

## H5：有合法空闲机会就能减少critical-path等待

- **Hypothesis**：S出现合法ready替代任务且资源/issue lane空闲时，提前它通常改善结束时间。
- **Why it may work**：推进后继的最早release可能填掉后续关键泡泡。
- **Runtime uncertainty**：实际完成与通知可见状态；反事实重新积分同一绝对时间环境。
- **Closest prior art**：资源约束critical-path分析、LATTICE CPE；本轮没有提出新因果算法。
- **Difference**：明确分离union opportunity与实际end-to-end action effect，避免累计task wait偷换成stall。
- **Strongest baseline**：冻结S的真实trace；干预之后回到同一静态资源序。
- **Minimum experiment**：每配置seed0最多6个单动作合法绕过；完整trace独立检查。
- **Expected observation**：多数干预缩短结束时间，而非只让某task更早开始。
- **Failure condition**：局部早执行改变共享资源相位，拖慢更关键工作；或关键终点毫无变化。
- **Actual result**：2,240个S trace中1,227有机会，union平均占latency0.917%；120个已生效干预16改善、84变差、20不变。最大单次改善130cycle，来自FLUX double four-slot source边界，不能外推总体动态收益。
- **Keep/Modify/Reject**：**Reject“有机会就有收益”；Keep联合测量**。

## H6：该进入有限总事件前沿/epoch硬件

- **Hypothesis**：compiler输出有限事件生命周期，在late admission/completion、slot复用和有限FIFO下保留大部分有价值收益。
- **Why it may work**：动态有效区可能只是小活动前沿，能压缩O(N+E)历史。
- **Runtime uncertainty**：迟到completion、通知backpressure与slot generation；本轮参考仍保留全history。
- **Closest prior art**：TaskStream有限表、bounded dataflow、LATTICE memory contract、HwSch OCSR。
- **Difference**：只有总状态/服务率/收益Pareto的具体实测差别才可能形成后续delta，目前未建立。
- **Strongest baseline**：完整history B、已优化S、有限FIFO且同总预算的候选；后两种新硬件尚未实现。
- **Minimum experiment**：先通过H1成本门，再实现event lifecycle、有限FIFO、late/duplicate/stale事件与回收协议。
- **Expected observation**：收益证据充足后，小总状态保留大部分净收益。
- **Failure condition**：前置收益不足，或状态压缩只是把开销移到descriptor/全图表。
- **Actual result**：主实验H1门未通过；不继续扩有限总事件协议。当前1,529–7,421 logical state bits只是缩尺有限图的部分预算，静态descriptor估计851–3,654B，不能据此给出硬件规格。
- **Keep/Modify/Reject**：**Defer机制实现；Reject现在优先投入硬件**。保留全history参考与未来证据门，不制造架构/novelty结论。
