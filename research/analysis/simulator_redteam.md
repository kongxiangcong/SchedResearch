# R3 Simulator 独立科学审计

日期：2026-09-05。审计者与 `sim/` 实现者分离。本轮只读取实现、运行独立小例及测试、反馈问题并写此报告；没有直接修改 `sim/`、`tests/` 或实验runner。审计覆盖全部 `sim/**/*.py`、`tests/test_sim.py`、`experiments/run.py`、`experiments/oracle_probe.py`、`experiments/minimum_window.py`、README与结果摘要。

**当前结论：它是能够产生可解释反例、保持固定映射/地址并比较有限调度机制的未校准事件模型。没有发现现有实验的核心completion循环偷看未来或遗漏同时刻完成的问题。独立审计发现了三个契约/泛化缺陷，已反馈并由实现者修复；还存在明确的模型保真度和验证覆盖限制，不能据此宣称strong compiler的理论上界、真实LLM/DiT收益或最小硬件面积。**

## 1. 实际发现并处理的缺陷

### F1：物理span可以小于声明输出大小 — 已修复并独立复核

初审时 `Contract.validate`只检查buffer owner、readers、domain，`validate_storage`只要求size>0、地址对齐和不超capacity。将声明256B输出的buffer改成size=1，validation仍通过，导致capacity和alias证明失真。独立探针输出 `UNDER_SIZED_BUFFER_ACCEPTED`。

实现者现已在 `sim/compiler/__init__.py:23–29,45–53` 检查output_bytes正整数和span覆盖，在 `sim/memory/__init__.py:27–30` 检查地址/size为整数。相同探针现输出：

```text
span CORRECT_REJECT buffer size does not cover task output bytes
```

影响范围：正常allocator原先已分配足够的64B对齐span，因此已生成的标准sweep地址不受影响；漏洞影响外部/手动contract验证和后续memory reuse研究。

### F2：有限窗口下静态admission可能隐藏所需队头 — 已修复并独立复核

两个独立任务a、b共用resource r，admission=(a,b)、固定resource order=(b,a)、window=1。原validator认为data DAG无环、resource order无环即可通过，但仅a进入window，a等待尚未admit的b，最终死锁。独立探针确认 `STATIC_ADMISSION_VALIDATED` 后抛出 `RuntimeError deadlock`。

实现者现要求admission也是包含静态resource顺序边的拓扑线性化（`sim/compiler/__init__.py:55–70`）。相同探针现在提前拒绝：

```text
admission CORRECT_REJECT admission order incompatible with static resource order; bounded-window progress unproven
```

此条件是**保守的充分条件**，不宣称是所有window下合法admission的完整判定；大window本可接受部分不一致顺序，但本原型选择简单可证明的contract。正常compiler从同一dispatch序产生admission/resource order，原标准sweep不触发问题。

该修复一度会拒绝runner中仅交换VPU resource order而不交换admission的反例枚举，已及时反馈；实现者同步修改 `experiments/run.py` 的counterexample构造，使两种顺序各有兼容的admission。

### F3：sync barrier被误标data，generic tile可将全barrier拆开 — 已修复

初审时 `synthetic.add`统一产生data边，multi-cluster barrier入/出边也如此；`tile`仅对non-data边建立all-to-all。因此在多cluster图上调用tile会把barrier变成对应tile同步，不符合README承诺。

实现者现于 `sim/workload/motifs.py:18–22` 将sync两端的边标为completion，`tile:124–129`保留non-data的全交叉依赖，并新增 `test_tiling_keeps_sync_barriers`。本轮grain sweep本来只用single-cluster pipeline，因而该缺陷不影响原grain结果，但修复对扩展研究必要。

### F4：Descriptor byte双authority — 根任务发现，现已修复

本审计读取到的版本已由 `sim/metrics/__init__.py:13–15` 的同一 `descriptor_size` 同时服务admission和report（`sim/execution.py:23–25`、metrics:27–28），且有一致性测试。假想wire长度不等于JSON字节数或R1 0x8长度，应保留此标注。

## 2. 核心模拟语义检查

| 项目 | 审计结果 | 证据与范围 |
|---|---|---|
| 同刻completion | 通过 | `sim/execution.py:105–128`在仲裁前清空同timestamp的completion/立即通知；R2的逐事件抢占错误没有继承。测试指定同时ready的高priority consumer先发射。 |
| 原子资源bundle | 通过模型检查 | execution:137–159只在所有resource空闲时取得全部资源；从dispatch到finish占有，避免持有部分资源再等待的内部死锁。 |
| 有限issue/wakeup带宽 | 实现语义清楚 | `Ports.reserve`记录每lane下次可用时刻；issue排队受width/cycle限制，wakeup按destination scheduler domain排队。cycle=0是理想无开销对照，不是有限频率硬件。 |
| Late admission通知历史 | 通过独立探针 | `delivered`保留已通知edge，admit时只数尚未delivered的pred。window1下a,b两个独立producer→z，零通知延迟latency=3；completion_latency10、wakeup_width1/cycle5时z在16发射、latency=17。无丢唤醒。 |
| 地址复用 | 在声明语义内保守安全 | `validate_storage`对每对同域重叠span要求old writer及所有data readers均可达new writer。不是总序interval复用。没有真实payload/numerics，无法证明算子内容正确。 |
| 偏序依赖 | 通过 | 数据、completion、WAR/WAW/reduction都等待producer完成可见；无推测绕过。拓扑校验拒绝重复端点、悬空依赖、环。 |
| 映射 | 对照间相同 | Task.resources/domain来自编译输入，B/C不迁移task/operand，不动态发现RAW。资源是字符串表示的一元server，尚无单独硬件资源目录核验。 |
| 事件完成含义 | 可解释但抽象 | finish代表本模型output-visible实体完成，另加固定completion latency和wakeup排队；DMA issue不触发consumer。跨域transfer本身是独立task。 |

有限wakeup时，同刻消息的仲裁仍由确定的completion/edge顺序决定。这是明确的FCFS式模型选择，不同于R2在无限wakeup下漏掉同刻ready集合；若研究priority-aware completion network，应单独替换该仲裁策略。

## 3. Baseline 公平性

### 3.1 A / A2 比naive sequential强，但不是最优静态compiler

`sim/compiler/__init__.py`的候选池为critical-path、shortest、longest、fanout与4个固定random priority，每个在名义duration下生成一次list schedule，然后取每resource固定顺序。A使用名义时长选择；A2用独立training samples选择固定候选。

主runner训练seed为10000起，测试seed为0起（`experiments/run.py:130–147`），A2在test循环外选定；B/C共用A2的mapping、address、DAG、priority、admission。每trial duration字典与digest对所有policy相同。未发现测试时长泄漏给A2或B/C。

限制：只有8个priority候选，没有局部顺序搜索、CP-SAT/ILP、memory planning、mapping/tiling优化；某些priority会产生相同resource order，实际不同候选可能更少。候选生成还先使用默认零开销Hardware，而非针对目标window/issue代价重新搜索。A2只用8训练seed，可能比名义A差。这些限制已在README标注，报告应使用“本候选池最优/训练选择的静态schedule”，不得写“强静态compiler也无法进一步优化”。

对确定性控制组，读取结果中的8个主要motif均为A2=B，C在llm_prefill与dit_cfg出现退化；没有通过隐藏deterministic负结果制造动态必胜。此观察支持实验基线的最低合理性，不能代替更强静态搜索。

### 3.2 B / C 没有偷看未来

`sim/scheduler/__init__.py:4–9`中的C只用compiler priority、已ready年龄、当前ready集合资源pressure。实际duration仅在选定task后用于生成finish事件（execution:146–159），不会参与rank。它是固定mapping下的age+pressure启发式，**不是Fully Dynamic、不是重新分析依赖、不是所有复杂OoO的代表**。

C与B在主sweep使用相同issue和dispatch延迟，C额外运算只预算state而未增加决策时延，因此C的性能比较偏乐观；不能直接把C−B的收益/无收益归为真实硬件Pareto。`minimum_window.py`另加dynamic-only dispatch cost是一项有用的机制成本探针，但仍仅限四任务图。

### 3.3 Oracle 标签

`sim/scheduler/oracle.py:9–41`枚举tiny DAG的全部拓扑排列，投影每一元资源顺序，零开销下自定时回放。对于固定映射、非抢占、原子资源bundle、最多8任务且完整window，这确实覆盖每个可行schedule所诱导的资源次序，可以称此受限模型的exact oracle；不覆盖动态mapping、不同内存或grain。

`clairvoyant_heuristic:44–48`把实际duration当预测后重新运行8候选池，明确不是exact，也不是理论性能上界/下界。`oracle_probe.py`中的输出同样明确只是一份可行heuristic结果。这一标签正确。后续若给它传入手工reuse的contract，需注意重编译会重新allocate storage，不保留任意外部地址plan；当前probe均为默认no-reuse图。

`minimum_window.py`对四任务二场景枚举全部topological admission与投影resource order，B使用A在同一common costs下选出的冻结contract，并另加dynamic-only dispatch cost；这种对照偏向保护static，适合计算该小例的break-even，但不能从最小window=某值推导NPU的一般最小硬件。

## 4. 不应混为实现bug的模型局限

| 局限 | 当前实现/披露 | 不能推出的结论 |
|---|---|---|
| 完整graph/event metadata常驻 | execution维护done和delivered；metrics预算N+E history，并为至多E个待通知事件预算储存 | 有限descriptor window不等于总硬件state为O(window)。 |
| 没有有限notification FIFO/backpressure | 待通知最多受整个有限DAG edge数上界；无独立credit容量，README明确 | 无法验证真实分布式网络死锁、饱和wakeup吞吐或小常数队列可行性。 |
| 全ready扫描零选择时延 | Python排序/pressure计算，candidate_checks记录操作量，issue端口另建模 | 不等价于高fanout、高window的真实arbiter critical path。 |
| Descriptor未往返解码 | 导出 `descriptors()`供检查；execution实际消费Contract/workload对象，wire bytes为假想模型 | 未实现R1格式或硬件decoder，不是二进制contract end-to-end验收。 |
| 无独立resource registry | graph中的新resource字符串成为新一元engine | 不能声称已验证所有binding属于某真实TargetHardwareSpec。 |
| SRAM/DMA/NoC粒度粗 | 一个task整个service期间占有其全部resource；跨chip只有link/egress/ingress一元资源 | 不是bank/beat、packet/flit、时分带宽共享模型；拥塞影响可能过保守。 |
| No-reuse默认布局 | allocator给每task唯一256B级输出，容量默认256MiB/域 | 未验证R1 4MiB下memory planning或reuse自由度收益；state/address存在不等于真实tensor容量。 |
| 外部uncertainty合成 | 以task-id hash抽lognormal，memory/communication可选；compute默认不变 | 没有真实DRAM refresh/cache miss/NoC背景流量的时间相关性证据。 |
| Heavy-tail加均值 | 5%×4会将受影响服务平均需求提高15% | 与非tail组差异不能单独解释成高阶尾部/方差效应。 |
| Workload结构motif | LLM/DiT没有模型导出、真实shape、数值、MoE/GQA或完整attention语义 | 不是真实LLM token/s、DiT frames/s或端侧设备性能结论。 |
| Grain依赖放宽是假设 | 对应tile能独立消费，parent噪声共享保留总service；non-data全barrier | 未证明真实Softmax/Attention/CFG可如此tile，不应把结果称编译器合法化完成。 |

Grain配置保持总service work和parent噪声因子，不再因碎片独立抽样而悄悄降低方差，这是公平性改进。但每tile至少64B输出、descriptor和dependency数量增长，memory/metadata随粒度变化；报告应明确这些都是成本，而不是免费细化。

## 5. Central / local 比较是否等预算

普通`clusters_*_central/local`配置给每domain相同window、issue width和wakeup width，因此local增加域数时复制控制容量。这组只能回答“复制本地资源的设计效果”，不能单独证明分布式组织更好。

`equal_budget_clusters_*`显式使central窗口/bytes/issue/wakeup总数等于local所有域之和（`experiments/run.py:41–47`）。这组可以比较控制服务的集中/分片效应，但仍有下列差异与限制：

- local端口不能跨域借用，负载不平衡会损失利用率；这是该组织的真实抽象代价。
- 所有策略仍读取全图metadata，没有真实层次ownership协议、网络control message route或local SRAM时序。
- wakeup destination用scheduler域分片，notification latency为同一常数，未计不同物理hop长度或远端credit。
- centralized与distributed可能有不同布线/Fmax/计数器端口面积，当前抽象预算不能宣称等面积等功耗。

因此equal-budget数值应解释为“相同entry/byte/service port数量的控制队列模型”，不能解释为已实现hierarchical/distributed硬件。

## 6. Metrics与独立trace验证范围

Metric命名基本诚实：latency为单个有限DAG完成时间；tasks_per_cycle不是token/frame throughput；resource busy与包含dispatch setup的reserved utilization分开；各类wait是排他分类的**task-cycle总和**而不是可相加为wall-clock latency。critical_path_dilation是makespan除以忽略资源/notification的sampled DAG最长路径，不是逐条真实关键路径沿途测量。

`state_bits`已包括history、wakeup/completion queue估计，且明确为partial logical budget。Descriptor大小两处现共用helper。仍缺decoder、metadata cache、ECC、路由、端口与wire；“comparators_upper”只是理想selection比较器数量，不是PPA上界。

独立 `verify_trace`（`sim/execution.py:186–197`）只检查：每task恰好一次、consumer不早于producer.finish+**minimum** completion latency、资源从dispatch到finish不重叠。它未独立复算issue ports、wakeup排队、service duration或descriptor admission的全部时间线。

已做反向探针：a完成后经wakeup_width1/cycle5唤醒独立资源b、c，真实c应在6发射；把c trace手工改为1发射、2完成，当前verifier仍接受，因为只违反排队延迟而未违反minimum visibility。这是**验证覆盖限制，不是已发现simulate执行错误**。本文已通知实现者在README收窄trace验证措辞；若未来主张notification network正确性，必须记录edge delivery/issue事件并独立回放。

Normal95区间是20个合成seed的逐样本paired latency reduction近似区间，只覆盖采样误差；不覆盖architecture/model误差，不应称“真实硬件95%收益置信”。heavy-tail与小样本p95需要更大seed数或稳健统计后再做定量结论。

## 7. 测试与产物一致性

初审独立运行12项unittest全部通过，说明上述F1/F2需要额外对抗输入才能暴露，不能用tests PASS替代语义审计。实现者已补充buffer coverage、static admission、sync barrier测试；本次结束前独立执行 `python -B -X utf8 -m unittest discover -s tests -v`，**14项测试全部通过（0.454s）**。所有R1/R2原文件均未改动。

源码修改后必须重跑并更新结果manifest。审计期间曾实际发现`experiments/results/r3/manifest.json`与当时新compiler/memory/runner SHA不一致，这是并行修复中的中间状态；实现者已在重新运行主sweep。根任务负责最后核对主sweep、oracle_probe、minimum_window各自来源hash与最终代码一致，不能仅重新写manifest来假装旧数来自新码。

## 8. 科研决策建议

保留这个小模型，用它拆开“存在性反例”“policy相对所选静态pool的经验收益”“成本与window敏感性”“真实NPU预测”四种证据等级。当前已完成前两者的一个可解释起点，第三者是抽象参数试验，第四者尚未建立。

下一轮最优先的提升是更强静态候选/小图最优gap、真实或至少时间相关的memory/communication服务模型、同容量的复用实验、有限notification credits与decoder/admission成本。不能在未补这些证据前以B/C某行胜出锁定最终OoO architecture；也不能因对称/同步motif失败就否定所有core/cluster/chip的动态空间。

## 9. 根任务最终产物复核

2026-09-05实现者冻结源码后，根任务再次独立执行14项unittest全部通过；`experiments.check_results`核对13个源文件SHA、980组共同随机样本、3,920条sample/metric和196条trace，返回PASS（仅其声明的验证范围）。minimum-window的13项源码SHA全部匹配最终文件，结果为72行；`experiments.oracle_probe`已按最终源码重新运行。最终报告和PNG/PDF由这批保存结果重新生成，23份入口/研究Markdown的本地链接检查无缺失。该复核解决第7节所述中间状态的manifest不一致，未扩大本文的验证或硬件校准结论。
