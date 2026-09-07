# R1 / R2 完整阅读与批判性审计

日期：2026-09-05。审计对象是本目录保留的七个文件，均已逐段完整阅读。未访问用户的 `llmSched / llm_sched` 源码，也未把历史报告中的实现、RTL 或性能数字当成当前设备实测。原文件未修改。

**结论：R1 提供了值得继承的编译契约边界；R2 的主要数值可以复现，但从这些数值推导出的必要条件不成立。应保留“强静态基线、显式内存安全、命名完成事件、先测方差”的方法，撤回“没有内存复用就没有动态收益”“必须重尾”“收益只在 DMA 仲裁”的普遍结论。** 本次已使用 R2 原始模拟器构造无复用、有界低方差的严格反例，并定位同时刻完成事件的任务编号偏差。

## 1. 覆盖与证据等级

以下行号均指本次实际读取的本地文件，报告内引用的外部源码路径仅是历史文献中的定位信息。

| 文件 | 完整覆盖 | 摘要与审计定位 |
|---|---:|---|
| `r1-base/five_directions.md` | 1–431；35,046 B | 从当前 TARS 单 cluster 双核约束出发，提出 remapper、generation lease、3D attention、阵列分区、双核 fabric 五个硬件方向；包含最低实验与停止条件。其方向排序属于当时选题判断，不能当作本轮动态调度问题的答案。 |
| `r1-base/live_evidence_audit.md` | 1–249；40,720 B | 最重要的编译流程/IR/Descriptor/物理存储/同步责任记录；标注实现、活动 authority、规划、缺失，指出 compiler 与 Controller 重复规划、VMEM 范围不一致、queue 单位不一致、计数器未接通。其文件名中的 live 只指 2026-09-01 当时的查阅。 |
| `r1-base/lit_search_registry.md` | 1–260；37,018 B | 五个主题的 59 条候选出版物、26 条书目字段核验、十次检索运行及失败源。适合作为查找线索；明确不是全文机制核验，不能据其“可辩护空白”直接宣布 novelty。 |
| `r1-base/redteam_claim_frameworks.md` | 1–646；54,446 B | 10→5 漏斗，每个方向有硬件实体、编译输入、状态机、独立项骨架、MVP、反证与先例。保留其成本/故障/停止条件，警惕将现有技术加项目名、epoch、receipt、固定参数的组合直接当创新。 |
| `r2-ooo-npu/research.md` | 1–273；34,319 B | 将执行模式分为 self-timed 与 static-assignment，提出显式 partial order、方差门、命名事件三步；以对称多流 LOAD→COMP 玩具模型得出最高约 4.5% 的局部收益，并过度收敛到 memory reuse。 |
| `r2-ooo-npu/literature-register.md` | 1–89；11,498 B | 覆盖调度分类、EDGE/SPDI、任务硬件、分配-调度联合优化、工业同步和模拟器。核验强度混合，部分来自引用/记忆/镜像/二手站；表题仍写 Round 4，不能作为完整同行全文 claim chart。 |
| `r2-ooo-npu/toy-sim/r4sim.py` | 1–287；11,035 B | 无外部依赖的资源互斥离散事件模型，固定映射、均值关键路径优先、可选 reuse/coupling 与时长噪声。没有地址、容量、SRAM bank、NoC、跨 chip、描述符解码或调度硬件成本。 |

本次当前可确认的事实分为：①七个本地文件的内容；②原脚本本机复现的 synthetic 输出；③可手算的四任务反例与同刻完成反例。历史 compiler/RTL 事实需要后续真实 artifact 或源代码导入才能重新验证；真实 NPU 延迟分布、DiT/LLM 收益、面积功耗和论文 novelty 仍未由本审计确认。

原文件 SHA-256：

```text
r1-base/five_directions.md          428bc9be7ffe089f37cd5582af424b2a7339a0bd41f7894bbf6f9d08ac0edcd7
r1-base/live_evidence_audit.md      e91b8441c36f29df9c9bd7017b83fb0c4519dc53a86e3cf5fb9fff65c7b85871
r1-base/lit_search_registry.md     d1703042a8eddc7dfc5488db6309c131149710ca9a0da950dea5f19317c3b499
r1-base/redteam_claim_frameworks.md 0f161f03953f916344bfd77c8110437e7a6cc6ec92547e95c26c3d0573d3ed19
r2-ooo-npu/research.md             cefe0edd53bf40fca7ba4676e916ffb0774fa53b757afa9d981c0317dff2f37b
r2-ooo-npu/literature-register.md  1878ba7da89c911d74c8c391f38be1e467ba9f4320586d8f4e569a238ca066fa
r2-ooo-npu/toy-sim/r4sim.py        97329f8ac75116053a35effa8c18f5798919a795d853df60ff98f149f1636c6d
```

## 2. R1 应继承的编译与执行语义

R1 的九阶段链条是本轮小型原型的语义来源，而不是要求复制生产项目全部 IR：

```text
GraphClusterIR
→ DataflowPlanIR
→ StreamTensorPlanIR
→ PhysicalMemoryPlanIR
→ MovementSyncPlanIR
→ CoreExecutionPlanIR
→ RuntimeLaunchIR
→ DescriptorEmissionIR
→ DescriptorSemanticReportIR
```

来源：`live_evidence_audit.md:14–22,26–53`；`five_directions.md:48–84`。

| 语义层 | R1 的具体记录 | 本轮应保留的约束 | 尚不能声称 |
|---|---|---|---|
| DAG 与模型语义 | GraphClusterIR 保存节点、边、边界和 blocked evidence；当时不做 graph fusion 或 multi-cluster repartition（live:28）。 | 模型语义、task 化和调度顺序分开；每个 task 可追溯至图节点/分片。 | 当前目录能编译真实完整模型。 |
| Task/mapping | GEMM 只有 single_map/seq_m/chn_n 三类候选，逐 op 合法性和浅层排序；ACT/WGT 固定 k-step 双缓冲意图（live:29–30）。 | 固定 mapping、tile 和允许引擎集合由 compiler 确定；runtime 不能默认迁移已有地址。 | R1 已提供足够强的静态全图 scheduler。 |
| Storage View | 完整 DDR tensor 的 stride 表示 backing storage；compact VMEM、BUFFER subgraph、FAMILY tile 是不同层（five:76–82；lit:72–74）。 | 地址、layout、tile 视图与传输长度独立建模，禁止把 tensor stride 当 tile adjacency。 | Linear Layouts 必然是研究核心。 |
| Memory Planning | placement/lifetime/alias/capacity/compute-read proof 是 PhysicalMemory owner；当前 generic lifetime-aware first-fit、K-step modulo-2；mirror frame、epoch 和 bank-cost search 尚属规划（live:31,84–106）。 | 物理地址单一 authority；释放必须依据最后一次实际读/写完成及可见性。 | 旧的总序 lifetime 对任意乱序仍安全。 |
| Dependency/visibility | MovementSync 负责 route、availability、residency、reuse 与静态 deadlock proof；当时词汇无 NoC/SDMA（live:32,48）。 | 数据依赖、内存复用边、通信可见性边分别编码；硬件只消费已经确定的事件关系。 | 纯 SIGNAL 已证明目标 payload 可读。 |
| Execution semantics | CoreExecution 是逐核动作序、cycle upper bound 为 None，策略 static_order_only_not_final_schedule（live:33）。 | 需要区分法律偏序与静态推荐顺序；硬件只能在允许的偏序内选择。 | 静态 legality 等价于周期性能最优或 RTL numerical PASS。 |
| Launch/Descriptor | 每 target core 显式 queue，空 core 也有空 package；0x8 header/family/buffer/loop，最多39×64-bit words、5 BUFFER slots、DEP/SIGNAL/CRC（live:34,112–127）。 | 包版本、entry identity、实际字节长度与队列 credit；不得在原0x8中悄加新语义。 | 原二进制格式已支持新事件、slot epoch 或任意 ready window。 |
| Hardware consumption | Controller/ref model 和 RTL 仍二次切 GEMM sublayer、重新算地址；RTL默认1 slot，2 slot为参数化路径（live:35–38）。 | 研究原型直接执行 compiler 已发出的 binding，检测非法契约，不能 silently repair。 | 已消除生产 compiler 与 Controller 的双重 authority。 |

R1 最有价值的是识别“静态计划能描述哪里”与“真实执行何时安全”的断层。其 `runtime 不拥有 task order` 原则（five:84；live:49–51）应在本轮改写为：**compiler 拥有合法执行空间与禁止交换的顺序；hardware 拥有该空间中的实时选择。** 将旧总序永远保留会在定义上消灭用户要研究的问题；改变总序又必须重建所有依赖于总序的安全证明。

### 2.1 R1 的硬件锚点与限制

历史记录中的 TARS-SC 是 1 cluster、2 core、每 core MXU/VPU/TMU/4 MiB VMEM、32×32 WS MXU、8 banks/4 bank-pairs，cluster 共享1 channel/1 outstanding DMA，core link仅同步（live:59–73,79；five:26–34）。这些参数可用于构造一个“R1-inspired”配置，不能当作新多 cluster/multi-chip 架构已存在。

R1 自己指出三处具体不一致：typed VMEM data/PARAM 分界与连接 RTL 保护区不同（live:89–106）；queue entry数量与 RTL4096B限制不同（live:123–127）；Controller重新寻址与PhysicalMemory唯一owner目标冲突（live:35–38）。另有 strategy 排名不是 latency model、analytical contention unavailable、busy/stall计数器输入接0（live:152–163）。因此“现有静态 compiler 很强”不能从 R1 当前实现推出；本轮须自行建立强静态基线并报告其剩余优化空间。

### 2.2 R1 五方向的本轮处理

| 原方向 | 本轮决定 | 原因 |
|---|---|---|
| D1 bank-pair remapper | 保留为资源竞争模型或后续对照，暂停作为主线 | 其收益依赖真实bank冲突且必须超过base/padding；修正文档映射不等于架构贡献（five:122–139；redteam:143–164）。动态派发不应与新增remapper同时打开后混算收益。 |
| D2 generation lease | 修改为按需要出现的安全机制候选 | 应先判断是否允许多代复用、乱序完成及tag重用；严格单outstanding/顺序路径下可能不需要GLT（five:143–181；redteam:231–252）。优先比较静态reuse边+完成计数与复杂range checker。 |
| D3 3D attention window | 本轮不作为主假设 | 它改变计算位置/外存流量，无法用于证明同硬件上的调度收益；保留作为未来多chip/NMP异构场景（five:196–244）。 |
| D4 partitioned MXU | 本轮暂停 | 它改变算力组织和供数路径，必须单独测面积/带宽，不能混入调度收益（five:248–295）。 |
| D5 双核stream/reduce | 修改为通信模型及通信完成契约 | 有无payload需求要靠DAG分片证明；以显式transfer和目标可见completion建模，不能把新增直连带宽收益归于调度（five:299–348）。 |

R1 的先例登记适合继续使用，但多处“尚未覆盖 TARS 多record/slot/epoch/receipt的组合”（lit:92,118,144,171）仅说明特定系统实现不同，未证明技术效果不同。必须用最近工作逐要素对照：其依赖何时形成、任务窗口多大、资源如何占用、完成如何发布、内存复用如何保证，才能谈独立贡献。

## 3. R2 提出的真实问题与错误收敛

### 3.1 保留的分析

R2识别同核依赖原先隐含于queue retirement、跨核同步按源序列消费、memory lifetime依赖total-order index（research:46–53）。这些都是从顺序执行进入可变次序时必须正面解决的语义变化。它还要求强于naive sequential的self-timed基线、独立考虑descriptor间DAE、先测延迟分布、保持归约顺序（research:98–145,173–203,250）。这些方向正确且可直接形成小型原型验收条件。

“固定mapping+完成驱动就绪派发”与static-assignment/SPDI/dataflow存在清晰历史联系，不能把它整体包装成CPU Tomasulo。R2的术语纠偏应保留；但“就是CDC6600式scoreboard”仍太具体：计数器+显式后继事件既可实现task dataflow，也可实现head-only自定时队列，是否有关联wakeup、逐任务窗口、WAR/WAW跟踪要看具体结构，不能凭无重命名就等同scoreboard。

### 3.2 必须撤回或收窄的断言

| R2 断言与定位 | 审计结论 |
|---|---|
| “没有内存复用收益恒为0”“只有重尾+复用才存在机会”（research:15,165,197–199,229–230,237） | 错误的普遍命题。第5节给出无reuse、bounded CoV0.2、最优固定顺序仍输给ready dispatch的反例。R2同形stream实验的0值只能描述其生成器与策略组合。 |
| “最优静态调度损失3%–8%”（research:15,116） | 未实现最优静态搜索。代码只是一次按均值关键路径的greedy list schedule（r4sim:156–192）；没有针对分布优化固定顺序，也没有最优性证明/下界。 |
| “oracle static-assignment”（research:123–127,262–264） | 原代码SA只看已ready与固定prio（r4sim:130–138），不知道未来时长，不是clairvoyant oracle；也不枚举最优在线策略。不能把SA结果当理论收益上界。 |
| “只有DMA跨核仲裁有持续价值”（research:140,157,201,271） | 它比较的是单一对称生成器，且lane-ST已经包含跨lane动态优先级仲裁；没有SRAM、NoC、异构引擎或通信模型，不能推出其余层没有价值。 |
| “更少复用优于复用+乱序，因此主要是compiler问题”（research:199,237） | 该模型没有地址和容量。reuse=0免费获得更多物理内存自由度，却不支付额外SRAM、spill或带宽成本；这不是同容量方案的公平比较。只证明所加边可能降低此图并行性。 |
| “≤13 descriptor窗口”由4096B/39word推得（research:52,135,233–234） | 不成立。4096B/8=512word，13只是在每条均39word时可放入的完整entry数。实际约束是sum(words_i)≤512；要推出通用entry上界，需要最小长度或独立entry限制。新contract格式更不能沿用该上界。 |
| “scoreboard面积功耗可忽略”（research:145,234） | 不成立为当前硬件结论。另一设计、工艺、功能集合的mm²/mW不能直接缩放；比较器、wakeup wire、端口、时序、缓存/取指和fanout不是计数器bits之和。 |
| “跨核计数式同步在任何乱序下无定义”（research:49,154,232） | 过强。若只在保留每条通道publish/consume顺序的局部窗口重排，仍可有定义；真正要求是不能自由重排而继续默认旧隐式匹配。命名event是候选解，也应比较保持通道序的窄解。 |
| “丢失可重放性就无法admission”（research:166,234） | 顺序可变不妨碍按task/event身份检查partial order、资源排他、输出与数值。需要重写验证器，不等于丧失验证能力。精确确定性可能是产品目标，不能预设为科研约束。 |
| “内存边+跨核边能成环”（research:108,168） | 一般情况下成立，但已提交生成器没有保存失败fixture。当前coupling每次向op索引前进，reuse向更高同核stream组前进；在所示2/8核偶数配置下可按(stream-group,op)排序，不能用其早期未保存的cycle失败作当前复现实验证据。 |
| “合法合同包含所有资源边”（research:106,258） | 需要区分：数据/alias/归约产生必须保持的边；可共享资源往往只需容量约束与原子仲裁。将单DMA所有任务编成固定边会消灭正要测的动态选择。 |

### 3.3 文献证据的局限

R2登记的“已核验”只表示打开题名/年份相符的页面（literature-register:5–9），不是全文机制、图表、基线和全部结论已核验。有的入口是ResearchGate、镜像、二手博客、其他论文引用（同文件:49–53,61–68）。research:217–223中“这些工作都没有联合优化/证书”“30%全部来自CPU开销”等强排除/归因，需要原文对应页和实验分解重核，不能由摘要或题名完成。

本审计没有重新联网替这些旧条目背书；本轮文献代理另做当前一手来源核验。“范式有先例”足以否定宽泛的新颖性口号，但不足以否定在硬件状态下界、分布式wakeup、通信可见性、bounded legal window、调度开销与收益Pareto上的具体架构研究空间。

## 4. R2 模拟器公平性与可解释性审计

| 项目 | 源码位置 | 影响与后续要求 |
|---|---|---|
| 同形串行stream | 28–63 | 每stream完全相同的12个长短交替op，LOAD依赖上一个COMP；没有同一op的Q/K/V分支、SwiGLU gate/up、AdaLN conditioning、store或数值。这强烈限制可观察的ready-order变化。 |
| 单compute resource/core | 39–45 | MXU和VPU折叠为同一互斥core，不能回答异构引擎重叠的价值。 |
| 仅边概率代表reuse | 52–58 | 没有物理地址/byte footprint/SRAM capacity，不能做容量约束下的memory规划结论；也未验证WAR读者就是实际最后读者。 |
| coupling无字节、无网络 | 211–237 | 跨核依赖被直接加边，zero transfer latency；不能称为communication-aware实验或multi-cluster证据。 |
| static只是CP列表启发式 | 156–192 | “强静态”至少应加入多优先级/局部顺序搜索、分布训练、test seed隔离；小图枚举给出最优或gap。 |
| dynamic无scheduler成本 | 103–150 | 全图resident、无限ready容量，每次完成扫描所有resource，wakeup/issue/arbitration/descriptor成本均0；无法回答Minimum Necessary Dynamic Hardware。 |
| 平滑/重尾实验同时换噪声作用域 | 195–207,240,277–282 | base默认dma_only=True，tail/couple/tailcouple改False，即compute也有lognormal抖动；tail还作用所有task。增益不能仅归于重尾或耦合。应固定noise scope逐因子扫。 |
| 重尾增加平均服务需求 | 205–206 | 5%乘4导致对应均值增加15%；未归一化，不能只解释为方差变化。 |
| 不确定性不是内生争用 | 195–207 | 按task抽独立时长，缺少与绝对时间/共享链路队列/请求量相关的background contention。调度改变请求重叠后duration是否应改变也无法表达。 |
| 同刻事件逐个完成就发射 | 142–150,184–191 | 同timestamp的高优先级consumer可能尚未被唤醒，就被低编号producer的consumer抢占资源；第6节已复现220对120的编号偏差。 |
| 统计证据有限 | 240–263 | 200 paired samples是好的起点，但只有一个固定seed与单图seed，输出仅均值，无CI、p95/p99、variant数量、失败比例；没有report seed、配置、原始trace到报告的可追溯工件。 |
| 基线定义偏离历史TARS | 248–254 | 从每资源序推DMA per-core lane，不强制“同核一次仅一pending descriptor”；它已经支持跨descriptor的DMA/compute解耦，应称优化self-timed baseline，不能称当前硬件精确复现。 |

ST、lane-ST、SA三者使用同一trial duration字典（r4sim:257–261），这一paired比较应保留。将改mapping、更换内存容量、增DMA channel、新增NoC宽度和换调度策略分别做ablation，才能定位动态信息本身的贡献。

## 5. 原值复现与无复用严格反例

可重跑证据：[audit_r2.py](evidence/audit_r2.py)、[r2_audit_results.json](evidence/r2_audit_results.json)。脚本只import原toy，不修改源码，不访问llmSched；运行前后SHA-256相同。命令：

```powershell
python -B -X utf8 analysis/evidence/audit_r2.py
```

200 trials、reuse graph seed7、duration seed1，表B-1的7组×3reuse都已复现。以下数值是SA相对lane-ST的**latency reduction**，不是speedup倍率：

| streams/cores/DMA | 条件（CoV0.6） | reuse0 | reuse0.5 | reuse1 |
|---|---|---:|---:|---:|
| 4/2/shared | base，DMA-only noise | 0 | 0 | 0 |
| 4/2/shared | tail | 0 | 0 | 0 |
| 4/2/shared | coupling | 0 | 1.159% | 1.125% |
| 4/2/shared | tail+coupling | 0 | 1.147% | 1.374% |
| 8/2/shared | tail+coupling | 0 | 4.521% | 2.707% |
| 32/8/per-core | base，DMA-only noise | 0 | 0.127% | 0 |
| 32/8/per-core | tail+coupling | 0 | 3.551% | 3.879% |

R2表B-2的8/2/shared tail+coupling同样复现：reuse0时lane=4772.48494；reuse0.5时lane=5141.64245、SA=4909.20608。数值成立于该模型；不能因此排除其他DAG或得出同容量SRAM下的优势。

### 5.1 不需要重尾或内存伪依赖的最小例子

固定映射为两个独立DMA producer，后继竞争同一VPU。地址完全分离，没有WAR/WAW、buffer reuse、迁移或推测：

```text
DMA0 ── RAW ─→ V0 (20 cycles) ┐
                             ├─ V0、V1共用一个非抢占VPU
DMA1 ── RAW ─→ V1 (20 cycles) ┘
```

两种场景等概率发生：DMA时长分别为(80,120)和(120,80)，每个DMA均值100、CoV0.2，分布有界且非重尾。静态compiler知道完整DAG、映射、地址和该分布，但不知道本次哪一支先完成。

| 场景 | 固定V0→V1 | 固定V1→V0 | completion-ready |
|---|---:|---:|---:|
| DMA0=80，DMA1=120 | 140 | 160 | 140 |
| DMA0=120，DMA1=80 | 160 | 140 | 140 |
| 等概率期望 | **150** | **150** | **140** |

这已枚举全部两种静态VPU顺序，提前空等或延迟启动producer均不能改善给定顺序；随机固定顺序只是两者混合，期望仍150。因此这里比较的确实是该模型下最优固定顺序。ready策略先执行80时刻就绪的一支，于100结束，后执行120时刻就绪的一支，于140结束；每个场景的下界都是max DMA finish120+后继20=140，策略达到下界。

结果是延迟降低6.6667%、speedup=150/140=1.07143。**它只证明R2必要条件错误，不证明端侧NPU一定存在该分布和足够多的分支。** 真正必要的结构是：某资源的潜在任务具备可交换自由度、运行时就绪信息可能改变合适次序、还有足够工作填充等待；内存reuse通常限制这些自由度，不是其唯一来源。

## 6. 同时刻完成事件的编号偏差

两个producer均在t=10完成；它们分别唤醒同一X资源上的L(100)和H(10)。H后面还有Y资源上的100周期任务，静态CP优先级H=110>L=100。正确的同刻完成语义应先处理t=10所有completion，再按priority派发H：H在10–20，L在20–120，Y在20–120，总长120。

原toy在每次heap pop后立即dispatch（r4sim:142–150；静态建序也如此:184–191）。若L的producer编号较低，L先被唤醒并占X到110，H到120才完成，Y到220；交换两个等价producer编号后结果恢复120。相同逻辑图、资源与时长仅编号不同，原dynamic结果分别为**220/120**，详见JSON。

这不说明第5节原报告所有数值失效：连续随机duration通常不同时完成，原值仍已复现。但基线均值、零方差控制组、整数cycle以及对齐的多核执行会频繁同刻完成，必须在新harness统一采取“同刻完成→全部依赖更新→资源释放→一次仲裁”的事件阶段。若有真实串行wakeup端口，应显式建带宽与仲裁时延，不能让Python task ID暗中充当硬件优先级。

## 7. 交付完整性与跨文档漂移

R1 four-files已经足以恢复主语义，但部分链接仍是旧文件名：five:46,404–407中的repo-evidence/academic-search/idea-redteam不存在；R2 research:7,52的round1目录及270的两个旧R1文件名也不存在。R2引用“round3 R1/R2/R4融合工作”（research:44,169,248–252），当前目录没有这些材料，不能用它证明CFG/fusion必然消灭机会。

R1 redteam:525说单descriptor最多28words，live:113和five后续采用39words；本轮应保留“以具体profile实际bytes计费”的原则，而不挑一个旧数全局套用。redteam:618与lit:38–68的search-run状态不同，可能来自并行子报告/不同回退阶段；没有共同日志前不得合并宣称同一证据链。

## 8. 本轮决策与最低后续条件

| 对象 | Keep / Modify / Reject | 后续动作 |
|---|---|---|
| Compiler压缩图推理为有限执行合同 | Keep，研究抽象 | 以R1语义重建小型DAG→binding→safe dependencies→descriptor链，见[compiler_contract_requirements.md](compiler_contract_requirements.md)。 |
| “给NPU加OoO/Tomasulo”作为宽贡献 | Reject | 分别命名head-only self-timed、ready dispatch、资源感知仲裁、动态placement；不要混称。 |
| R2最高4.5%作为方向上界 | Reject | 只是生成器局部观察；增加分支/异构pipeline/通信争用且使用更强静态基线。 |
| Memory reuse决定legal partial order | Keep，修改为限制因素之一 | 固定容量/地址下比较；同时允许在独立实验中优化地址与buffer count，报告spill和metadata。 |
| 命名event+小窗口 | Keep为候选，非既定答案 | 对照head-only、per-engine FIFO、计数器ready dispatch；测window/state/wakeup/issue的最小充分点。 |
| 完整ROB、rename、CAM式RS | Reject为默认结构 | 只有对应hazard、恢复语义或测得的dispatch收益才引入。 |
| 仅cluster/chip有价值 | 未决 | 先测core、cluster、chip不同范围；规模提升也可能增加关键路径同步、降低独立性。 |
| 必须先接原RTL才可做研究 | Modify | 源码不在目录；先做可解释synthetic模型与正确性验证，真实trace校准为后续证据升级，不虚构现有UAT可用。 |

最小定量闭环应报告同一DAG、同一mapping/address/capacity、同一已采样外界场景下：强固定顺序、轻量completion-ready、更强在线策略和小图oracle的延迟、ready/stall分解、调度状态/issue/wakeup成本。先保留支持与反对动态调度的控制组，再决定哪个层次与机制值得进入真实LLM/DiT图和RTL预算。
