# R3 假设台账

日期：2026-09-05。实际数字以 [experiment_report.md](experiment_report.md) 和机器结果为准。Keep表示保留研究问题，不是确认论文贡献；Reject只针对明确写出的主张或本轮机制。

## H-A：Strong static + lightweight dependency scoreboard 是否已经足够

- **Hypothesis**：固定mapping下，静态priority的B能取得更复杂C的大部分收益。
- **Why it may work**：compiler已知criticality和资源，硬件最重要的新信息可能只是当前哪些task完成。
- **Runtime uncertainty exploited**：producer ready先后、memory/communication服务变化。
- **Closest prior art**：SPDI/EDGE、VTA、Gemmini、ASPEN、HwSch；[registry](../literature/prior_art_registry.md)。
- **Difference from prior art**：目标是强静态后有限状态的边际收益定量，不是发明counter。
- **Strongest baseline**：A/A2和四任务全排列最优固定顺序；C与B保持mapping/地址相同。
- **Minimum experiment**：同图同seed比较A、A2、B、C；计state/window/issue/wakeup。
- **Expected observation**：B接近C，收益集中于绕过未ready队头。
- **Failure condition**：有因果可见的runtime资源信息使C稳定显著胜B，且足以付额外控制成本。
- **Actual result**：本轮C没有在配置均值上超过B；大部分B增益也很小或为负。B不因优于这个C就自动值得增加到A上。
- **Keep / Modify / Reject**：**Modify**，暂保留B作为最低动态对照，不能宣称它已覆盖所有复杂scheduler。

## H-B：更复杂OoO是否显著超过A中的轻量机制

- **Hypothesis**：加入ready age与当前resource ready pressure可更好选序。
- **Why it may work**：实时排队可能暴露静态critical-path rank没有捕捉的拥塞或饥饿。
- **Runtime uncertainty exploited**：已观测队列与完成进度；无future duration。
- **Closest prior art**：ASPEN priority/ready pool、TaskStream、硬件task调度。
- **Difference from prior art**：本轮C只是可替换启发式，未主张新算法。
- **Strongest baseline**：B同合同同成本；C还额外计age状态，其算术关键路径未额外收费，因此性能比较对C偏乐观。
- **Minimum experiment**：critical+background、异构pipeline、cluster/chip共享资源，多seed配对。
- **Expected observation**：若成立，C平均至少额外3%且多数图无回退。
- **Failure condition**：C不胜B，或优先后台任务反而堵关键任务。
- **Actual result**：未观察到配置均值上C>B，部分C显著变慢。
- **Keep / Modify / Reject**：**Reject当前C**；不以此证明所有复杂OoO无效。下一种机制必须针对已定位的具体失败trace，不盲目加policy。

## H-C：有价值的动态调度是否只在cluster/chip通信层

- **Hypothesis**：核内近确定，只有通信尾部给出不可静态消除的收益。
- **Why it may work**：规模放大远程到达相位、fanout和straggler。
- **Runtime uncertainty exploited**：link/NoC完成与credit。
- **Closest prior art**：distributed task graph/TaskStream、ASTRA-sim体系与通信执行模型。
- **Difference from prior art**：要找端侧固定mapping下局部动态的规模拐点，而非提出“分层”这一常见词。
- **Strongest baseline**：A/A2含通信节点/阶段barrier；central-local还需等总控制预算。
- **Minimum experiment**：分别只扰动memory、只扰动communication、二者扰动；core/cluster/chip分开。
- **Expected observation**：通信-only的B稳定胜A2，core-only近零。
- **Failure condition**：核内也有严格收益反例，或通信变慢时没有可绕过工作。
- **Actual result**：四任务局部反例已推翻“只在通信层”的全称命题；多chip带barrier motif中的B存在明显负收益。
- **Keep / Modify / Reject**：**Reject exclusivity；Modify机制候选**。不能因规模大就收敛到communication-aware调度；应先暴露真实局部消费机会。

## H-D：核心问题应改称latency-tolerant task dispatch

- **Hypothesis**：问题是合法任务的延迟容忍，而非寄存器重命名或CPU式推测执行。
- **Why it may work**：DAG、地址和语义已静态确定，只有完成/资源状态动态。
- **Runtime uncertainty exploited**：不同来源任务ready顺序翻转。
- **Closest prior art**：static-assignment、SPDI、task dataflow、VTA。
- **Difference from prior art**：目前无宽泛机制差异，必须再找具体有限状态设计的delta。
- **Strongest baseline**：强self-timed静态、编译的双缓冲/异构pipeline。
- **Minimum experiment**：无rename、无ROB、无dynamic dependency analysis的B是否就能达到四任务oracle。
- **Expected observation**：仅completion+ready选择足以获得严格存在性收益。
- **Failure condition**：收益实际依赖动态mapping、alias重命名或speculation。
- **Actual result**：四任务中B达到140的每场景exact下界，未用上述复杂机制。
- **Keep / Modify / Reject**：**Keep作为准确名称**，不把重命名研究方向当作novelty或有效性证明。

## H-E：R2的memory reuse与heavy tail是必要条件

- **Hypothesis**：无复用边，或仅有界轻抖动，就不能有动态收益。
- **Why it may work**：R2等形串行流/单DMA局部观察如此。
- **Runtime uncertainty exploited**：R2只充分激发了很窄的负载结构。
- **Closest prior art**：R2 toy与历史DSP静态/动态分类；不能将局部结果当定理。
- **Difference from prior art**：本轮做必要条件反例，不提出新scheduler。
- **Strongest baseline**：枚举四任务所有有意义静态VPU顺序，两场景期望最优。
- **Minimum experiment**：两独立DMA→共享VPU；时长等概率(80,120)/(120,80)，VPU各20，无alias。
- **Expected observation**：若R2正确，最优静态与ready相等。
- **Failure condition**：存在合法B优于所有固定顺序。
- **Actual result**：150→140，latency降低6.667%；CoV0.2，无重尾，无复用。原R2引擎与新harness均复现。
- **Keep / Modify / Reject**：**Reject**。复用限制自由度，是重要协同因素之一，不是收益来源的必要条件。

## H-F：最小窗口能否取得大部分收益，控制开销何时抵消

- **Hypothesis**：有限很小窗口已足够；更大window不会线性增加收益。
- **Why it may work**：只需看见能填当前bubble的独立任务；额外条目可能不增加ready宽度。
- **Runtime uncertainty exploited**：同H-E。
- **Closest prior art**：bounded dataflow/window scheduling、ASPEN粒度选择、经典latency hiding。
- **Difference from prior art**：本轮只是可解释state/benefit标定，尚无新压缩编码。
- **Strongest baseline**：对6种拓扑admission/投影resource order穷举的最优A，每种硬件预算独立离线选择；B用A冻结合同。
- **Minimum experiment**：[minimum_window.py](../experiments/minimum_window.py)扫W=1/2/3/4、common cost=0/1/2、B额外dispatch=0/1/2/4/8/16。
- **Expected observation**：存在最小充分W，超过它收益饱和；额外成本超过可隐藏等待后反转。
- **Failure condition**：收益只在无限window或零成本存在，或状态节省全被event history转移掉。
- **Actual result**：零common cost时W2无收益，W3即150→140，W4不再改善；B额外每task dispatch=4时148，仅1.333%收益；=8时156，倒退4%。这些cycle都是合成单位。总状态含O(E)通知/历史，不能声称已做bounded-total-state机器。
- **Keep / Modify / Reject**：**Keep为方法验证**；“3项足够”只限此图和admission语义，不可移植到实际NPU规格。

## H-G：中央调度会先饱和，分布化值得其状态/通信成本

- **Hypothesis**：local completion更新占多数时，分域能减少集中事件端口等待。
- **Why it may work**：局部连线短、fanout不出域。
- **Runtime uncertainty exploited**：事件burst和跨域完成相位。
- **Closest prior art**：ASPEN distributed scheduling、TaskStream hierarchical dataflow、EDGE。
- **Difference from prior art**：计划比较相同总issue/wakeup/window预算；不是简单复制更多端口。
- **Strongest baseline**：资源匹配的central对照，保留相同全局mapping/addresses。
- **Minimum experiment**：per-domain预算与equal-total-budget两套，记录域数、事件量、实际队列和control利用率。
- **Expected observation**：在相同预算下local减少控制等待，而不是仅因获得更多端口更快。
- **Failure condition**：优势在等预算比较消失，或全局metadata/跨域队列仍为主导。
- **Actual result**：本轮能比较中央与issue/wakeup分片；**没有实现完整分布式credit/ownership协议与hierarchical scheduler**。最终等预算结果见report，不能升级为scalable硬件验证。
- **Keep / Modify / Reject**：**Modify / 未收敛**，保留边界问题，暂不选择层次硬件。

## H-H：memory plan → execution contract是独立novelty

- **Hypothesis**：R2提出的复用约束、合法部分序与可验证合同形成新的编译器内核。
- **Why it may work**：addresses决定合法顺序，确实需要在动态前正确表达。
- **Runtime uncertainty exploited**：该宽泛主张本身并未要求runtime uncertainty。
- **Closest prior art**：LATTICE v3，另外有安全并行memory allocation、SPDI等；见[novelty_redteam](../analysis/novelty_redteam.md)。
- **Difference from prior art**：目前能提出的差别只剩runtime信息与硬件状态Pareto，尚未证实收益。
- **Strongest baseline**：固定memory plan下强静态timing refinement。
- **Minimum experiment**：先做原文claim比对，再做相同contract的static/causal/oracle实验。
- **Expected observation**：若新颖，应有先例未解决、可测的硬件问题。
- **Failure condition**：先例已覆盖“memory plan作为合法时序合同”的核心。
- **Actual result**：LATTICE当前v3明确表达这一合同及复用边；旧索引DAN-Scheduler不能被当另一篇漏掉。
- **Keep / Modify / Reject**：**Reject宽泛novelty；Keep正确性基础设施**。不出论文/专利肯定结论。
