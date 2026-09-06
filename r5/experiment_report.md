# R5：先区分资源损失、静态优化与动态信息价值

日期：2026-09-05。**决定：在本轮全宽来源切片、冻结资源参数与已测试策略范围内，正式淘汰通用 completion-ready scheduler 的新增架构方向；下一阶段进入真实目标设备的测量门，先检验编译器驻留和资源供给之后是否还有剩余损失。没有形成新 architecture proposal。**

这不是“为了配合 proposal 换一套实验”。R4 的收费收益前置门没有通过；R5 进一步改变工作量尺度和资源抽象来检查这一负结论。新的证据支持收窄问题，而不是保证一定找到新机制。尚未证明真实端侧 NPU 不存在有价值的 runtime uncertainty，也没有证明生产编译器已经足够。

跨轮八字段证据链见 [科研方向探索进度表](../research_progress.md)。实验前的五项输出已先行给出，随后执行了 [预登记合同](experiment_plan.md)；审查修正与后验控制保存在 [amendments.md](amendments.md)。

## 1. R4 的证伪边界与本轮问题

R4 排除了**当前缩尺模型、覆盖的来源图、静态候选与收费策略**能够稳定超过5%门槛的收益主张；120次单动作实验的16改善/84变慢/20不变，直接否定“只要有合法等待机会就有最终收益”。继承优化静态priority后，收费B_order2最好仅+0.1968%，区间跨零，仍不支持继续增加机制。

R4 没有排除全宽tensor/state/weight、请求级排队、有限outstanding、返回credit、共享bank与真实时变服务的重要性，也未穷尽所有在线策略。每命令2cycle不是实测PPA。不能从R4推导“真实NPU没有动态机会”。

本轮保留三个问题：

1. 全宽工作中的损失，是字节数/带宽和资源容量决定的，还是有能通过改变任务顺序恢复的部分？
2. 请求、bank与有限返回缓冲的细化，会不会改变静态/ready的相对结论？
3. 剩余损失是否先能由合法静态驻留、布局、预取和资源顺序消除？

A“当前ready机制边际价值小”和B“旧模型遗漏资源行为”可以同时成立。本轮能检验模拟器内的条件性解释，不能在没有真实设备数据时判定B是否准确描述目标机器。

## 2. Hypothesis → Strong baseline → Discriminative experiment

使用官方冻结来源的三个切片：Qwen3.5 fullK2560、M1，FLUX2 fullK3072、M32，均为两个fusedN128输出tile（每tile64 gate+64 up）；GDN为两个完整128×128 FP32 state head及4个prepared输入token。projection保留所有K128步骤、BF16字节、FP32累加、合法地址和双缓冲；没有缩小内部K维度。它们仍是**切片端到端**，不是完整模型端到端。

细模型逐256B请求执行：有限DMA outstanding、逐请求有界延迟、共享外存带宽、有限返回槽、串行DMA fabric、bank仲裁及SRAM→RF feed。返回槽在外部传输前预留，destination SRAM可见后释放credit。compute不占着整个SRAM端口。另以相同DAG、bytes和MAC执行atomic pooled-memory对照；该粗模型不保留逐请求队列，既不是细模型下界，也不是校准基准。

每个硬件/环境配置单独训练静态：6种topological heuristics ×3种bank color ×3种DMA pacing，去重后projection54、GDN36候选，再最多64个合法相邻资源顺序交换。train1000/1001，训练前三进入validation1100/1101，选定一次后在2000..2011测试。搜索增加了layout/pacing轴，**不是R4搜索空间的超集，也非最优生产编译器证明**。

S为固定per-engine order、依赖/credit自定时及固定pacing。B0以同一选定priority/layout/pacing允许ready绕过阻塞队首，免费额外控制；B2每命令加2cycle。所有策略使用相同逻辑请求、地址、字节、外生样本与容量，排队随各策略重新演化。调度模型保留完整图历史，不是有限总状态硬件实现。

主矩阵为36个request配置：3切片×12设置，包括无扰动、latency、单bank背景、外存背景、combined，以及O=1/4/32、返回槽1/2、FIFO bank仲裁、固定总SRAM带宽的单bank压力控制。另有6个atomic配置。参数在比较前冻结；没有追加寻找正收益的调度策略或噪声扫描。

阶段门为至少两个参考来源切片B0均值≥5%、区间下界>0，并在B2后保留收益，再检查因果观测、有限状态和成本。5%仅是研究筛选门，不是已知面积功耗盈亏点。压力配置正值不能直接打开proposal门。

## 3. Result：更大资源损失没有带来对应调度收益

42个配置共7,094次训练/验证/测试执行，其中1,512次held-out测试。全部明细和置信区间见 [all_cases.md](results/all_cases.md)，可复算摘要见 [interpretation.json](results/interpretation.json)。

| 请求级主结果 | B0：免费ready | B2：每命令+2cycle |
| --- | ---: | ---: |
| 正均值 / 零 / 负均值配置 | 2 / 16 / 18 | 2 / 0 / 34 |
| 最好均值 | +0.1649% | +0.1821% |
| 最好点95%区间 | [-0.0253%, +0.3458%] | [-0.0082%, +0.3534%] |
| 通过5%门配置 | 0 / 36 | 0 / 36 |

两组微小正值都来自Qwen的O=1或4压力设置，区间均跨零。没有证据支持它们具有稳定收益。B2偶尔比B0更快，是额外延迟改变争用/背景相位的结果，不能据此声称控制成本有益；该干预不是单调的标量减法。

| 切片，参考资源 | 无扰动S cycles | combined S cycles | 两环境分别训练后的延迟增幅 | combined B0 / B2收益 |
| --- | ---: | ---: | ---: | ---: |
| Qwen全K投影 | 41,718 | 55,546.6 | +33.15% | 0 / -0.0558% |
| FLUX全K投影 | 57,575 | 76,700.7 | +33.22% | -1.2792% / -1.2751% |
| GDN原始SRAM往返lowering | 23,318 | 28,149.9 | +20.72% | 0 / -0.1998% |

该增幅是**同一细模型、分别重训静态后的环境差异**，不能冒充固定binary下单一因素的因果损失。单因素行另有保存；有界latency变化并不保证增加延迟。GDN主行还存在下一节解释的静态驻留缺口。

容量压力很大：Qwen/FLUX的O=1延迟分别是相同combined参考的10.60×/10.32×；返回槽1为3.71×/3.65×。这是不同硬件容量之间的条件性差异，说明资源限制可主导执行，却不能证明真实设备具有这些配置或应扩容。ready没有恢复这类容量损失。

全宽投影已接近该合同的外存下界。无扰动时Qwen必须传1,315,840B，32B/cycle至少41,120cycle，S=41,718；**保持字节与带宽不变，任何仅重排机制最多还能改善1.43%**。FLUX的对应上限为3.96%。combined按同一绝对时间服务日历积分，平均宽松上限仍分别仅1.29%/3.90%。这些是固定流量/资源合同的上界约束，不是对改变驻留、压缩或硬件带宽方案的上界。

atomic→request不是单向“变慢”：Qwen无扰动42,300→41,718，FLUX61,679→57,575，GDN combined25,641.8→28,149.9。细化允许了某些真实结构的重叠，也引入了粗模型无法表达的排队；仅看延迟差不能唯一归因某个因素。六组atomic的B0均为零；细化没有产生达门的ready收益。

## 4. 具体退化与有限信息价值

独立 [trace诊断](trace_diagnosis.json) 中，FLUX无扰动S有3,239cycle合法队首阻塞机会。B0提前派发core1的两个weight DMA，使共享input从8,280延后到10,328cycle可见；总external bytes和55,296cycle外存服务不变，最终57,575→57,879cycle，慢304cycle。该证据支持预取争用解释，但它是**配对trace诊断，不是单动作因果干预**。不能把3,239cycle当成可回收的最终时间。

另用固定6命令、20合法topological priorities全枚举，共207次执行：确定性S*=clairvoyant=B0=190，B2=197；8点请求延迟有限分布下，最优固定期望198.2477，逐样本同类clairvoyant194.1956（2.04%），B0=195.1227（1.58%），B2=201.9977（-1.89%）。这说明细模型能呈现非零信息价值，同时显示收费后不足。**精确只指该有限priority/self-timed类**，不含任意timed schedule，不是全硬件理论极限。见 [tiny_exact_results.json](tiny_exact_results.json)。

## 5. Red-team后的静态驻留控制

独立source audit发现：本GDN切片每core只有一个65,536B state，加上4token prepared vectors6,176B和全部输出2,048B，共73,760B，能放入128KiB RF。因此每token读写SRAM不是容量要求。主图的这一选择不能用来主张strong static无法解决。

保留主结果，另做后验、独立seed控制：同算术、同初始外存state、同RF容量、同每token输出与最终state；首次读取后在RF连续处理4token，最后写回一次。两种lowering使用相同静态搜索预算；train3200/3201、validation3300/3301、test3400..3411。没有新动态机制。详见 [resident_control_results.json](resident_control_results.json)。

该控制928次执行全部通过独立request审计，四组静态改善分别为无扰动16.013%、combined24.027%（95%[23.568%,24.450%]）、O1压力7.155%、返回槽1压力11.853%；resident B0始终与S相同，收费B2退化。**可恢复损失首先落在既有容量下的编译器驻留选择，而非completion-ready硬件。** 这不证明完整Qwen模型也可保留state：当前只含两个head、4token输入已备好、没有其他层争用RF；真实自回归下一token输入尚未生成，32个head/其他层也可能打断驻留。

## 6. 验证与仍未解决的fidelity

- R1–R4历史和冻结文件重新审计，560个R4统计摘要与2,240组paired环境复算；原文、代码与负结果保留。
- 9个独立解析/反例测试通过：已知单请求时序、固定总带宽bank并行、O1/O2、返回反压、零噪声、环境一致性、同刻重命名、地址复用和损坏trace拒绝。
- 9组全宽数值数据、18项FP32对照通过，BF16输入/权重采用round-to-nearest-even；投影最大绝对误差1.79e-7，GDN输出/最终state一致。数值oracle与性能请求执行分离；不是逐payload硬件执行或真实权重质量验证。
- 全部1,296次request held-out执行在内存中独立审计，共12,886,560条请求，检查bytes、时序、bank/credit容量、visibility和地址生命周期；保存108个request与18个atomic详细trace供独立复查。训练/验证不冒充全部独立trace验收。
- tiny选定策略27条trace另经独立检查。后验驻留控制、来源合同、主统计/短名单/validation选择和源码hash均保留独立审计文件。

最终独立复查主126份保存trace共1,073,880条request、全部1,512个test统计行和预登记/source hash；驻留控制24份保存trace共73,728条request另行复查，均PASS。上述928次compiler控制和207次tiny枚举独立于主实验7,094次计数；保存的三部分共8,229次仿真执行，不把数值oracle或解析测试混入性能样本数。

仍未校准：256B bank stripe、bank数、bandwidth、RTT、背景分布、MXU利用率/fill、VPU吞吐、返回credit释放合同。fabric只有DMA经过，local RF流量直接进bank，**没有完整NoC flit/VC/路由credit模型**，没有真实DRAM row/refresh、热/频率轨迹，也未观测这些因素是否重要。Arm/Gemmini资料仅证明有限资源与相关计数器有工程依据，不能把其integer能力套用成BF16目标机参数。见 [resource_evidence.md](resource_evidence.md)。

train/validation各2seed、固定tiling与有限静态搜索限制了基线覆盖。12 test seeds的区间描述所设定分布的采样，不包括模型误差；全矩阵没有满足门槛，因此不从最佳微小均值声称显著收益。无目标设备、生产编译器导出、完整模型、RTL、面积或功耗验收。

## 7. Accept / Refine / Reject 与下一步决策

| 假设或问题 | 判定 | 证据与下一步 |
| --- | --- | --- |
| 放大全宽并细化资源，就能让通用ready恢复足够收益 | **Reject：已测试策略/合同内淘汰** | 36组无一达门，投影接近固定流量下界；不追加更复杂/更小scheduler或参数搜索。 |
| R4的atomic资源抽象可以代表所有关键等待 | **Refine** | 请求级行为改变绝对延迟、排队和退化原因；不等于已证明真实设备遗漏哪一种重要行为。 |
| 有限outstanding/返回槽可能主导执行时间 | **Accept：条件性资源事实** | 固定工作下有大容量压力损失；是否存在于目标机须测，不能据此直接设计新资源。 |
| GDN切片的每token SRAM往返是不可避免的动态损失 | **Reject** | 合法RF驻留静态控制消除一部分交通，获得约7%–24%改善；不能外推全模型。 |
| 当前实验证明strong static在真实NPU已足够 | **Unresolved** | 无生产compiler/设备/全模型验证；不能得出该命题。 |

**下一轮只保留一个测量问题：在目标设备的合法驻留/tiling/prefetch优化后，受控共享流量是否还造成稳定、超过测量误差且足够大的端到端剩余损失？**

执行合同已写入 [measurement_gate.md](measurement_gate.md)：固定实际binary/layout/input/频率，隔离与受控随机相位背景对照，记录elapsed、真实bytes、outstanding-limit、request latency及compute-active；分别测compiler优化和同合同下的动态干预。先用目标实际支持的dtype与kernel，不预定目标芯片或硬件机制。

若无稳定剩余损失，结束候选；若静态驻留/布局可解决，转compiler或明确的compiler/hardware contract研究；只有剩余损失真实存在、观测可得、有限状态干预能恢复足够净收益时，才允许形成新的architecture proposal。当前设备测量尚未执行，下一决策是采集证据，不是继续堆叠simulator复杂度。
