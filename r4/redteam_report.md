# R4 独立科学与模拟器审计

审计日期：2026-09-05。审计者独立于 `engine.py`、`lowering.py`、`static_search.py` 与模型转写实现者；仅新增本报告、独立检查/静态诊断脚本和一手文献 delta/evidence。R1/R2/R3 原始材料未修改。主实验与事后 compiler-hint 校正的全部已保存执行记录均已独立复核。

## 当前判定与证据等级

**已通过数学小图与抽象执行合同检查；尚不能宣称真实 4B workload 性能、生产编译器、RTL 或设备验收。** 七张 source-derived 缩尺图（包含最终 VPU chain fusion 和三个 attention/conditioning 变体）的输出和新状态，在每图 20 种随机合法执行次序下与独立 NumPy reference 一致。504 条独立 trace 回放通过实际 issue/wakeup/admission、资源和地址互斥、绝对时间服务积分及可恢复等待并集检查，覆盖默认端口、单项窗口/慢唤醒、分离引擎端口。详细结果由 [redteam_checks.json](../experiments/results/r4/redteam_checks.json) 保存，命令为：

```powershell
python -X utf8 -B -m r4.redteam_checks
```

模型来源核验、公式转写、物理合同和性能实验是不同证据。reference 不调用图 Node.run，能够查出图拆分和重排差异；但图与 reference 都为本地 NumPy 转写，未执行官方 Transformers/FLUX PyTorch 模块，也未下载真实 checkpoint 权重。这里的 float64 一致性不能证明 BF16/FP32 设备数值误差、真实生成质量或 tile kernel 正确。

## 实际发现、处理与独立复核

| 编号 | 发现 | 处理与证据 |
| --- | --- | --- |
| R4-F1 | 初版 memory planner 只计算子图内部 readers，没有把 `case.outputs` 的 KV、conv、recurrent 状态当作调用边界 live-out。独立探针确认 `kv_next` 地址随后分配给 `ffn_swiglu1`；`conv_next`/`state_next` 也被后续任务覆盖。`Case.evaluate` 每 tensor 独立数组会掩盖这个问题。 | 主实现者禁止含 live-out 的旧 owner 被后续任务复用，并补终端观察者生命周期。独立 `check_tensor_contract` 检查 live-out owner 的所有可达后继都不重叠；四基础 case 已通过。早先地址可复用于最终 output 是安全的，问题仅是产生 live-out 后再次覆盖，审计没有把前向复用误判成漏洞。 |
| R4-F2 | 机会时间 `max(now, next_issue_slot)` 可能没有对应普通 completion/wakeup 事件。若只在相等时间应用 intervention，反事实可能永远不触发。 | 主实现者在推进事件时钟时纳入干预时间。独立三任务探针中机会为 `[5,100]`，A=120，单次合法提前执行变为110，`intervention_applied=True`。不能把一次干预的局部改善自动外推成全动态政策最优。 |
| R4-F3 | fast search 通过 `order=` 参数改变资源顺序，而原 `Contract.resource_order` 为空时，直接使用其 cost 会漏记静态顺序 metadata。 | detailed cost 现消费与本次 order 相符的 projected resource orders。状态统计仍是部分 logical bits，不是 decoder/queue/PPA 验收。 |
| R4-F4 | 初版 inversion 用 `ready_at`，包含 late admission 的截断，不能纯归为依赖完成先后。 | 现用每 task 全部 incoming notification 的最大 delivery 时间计算 dependency readiness；trace 的 `ready` 另保留 `max(admission, incoming delivery)` 供派发检查。 |
| R4-F5 | attention/VPU 聚合后若仅删除外部中间 tensor，会把内部暂存与传输隐去。 | 已按 materialized 内部暂存补容量和读写量；每 core 预留最大 scratch，普通 tensor 地址从其后分配。独立检查所有最终七图 metadata、地址与 SRAM demand 通过。保守聚合节点通过不代表实现 FlashAttention。 |
| R4-F6 | dtype 默认值曾按名字含 `state` 推断4字节，使 FLUX 普通 `img_state`/`txt_state` 激活被误计 FP32。 | 主实现者将 lowering 与 fusion 两处统一为 BF16 默认，仅采用显式 `storage_bytes` override；旧 sweep 已停止后重跑。独立断言捕获旧错误并验证修复，避免名字影响性能。 |

## 独立验证覆盖

- **数值与输入纯度**：从 `reads/writes` 自行构建依赖；随机挑 ready node，验证全部 externally visible output，包括 Qwen 新 KV、conv 和 recurrent 状态。逐 node 验证没有未声明的原位修改，拒绝重复 writer、未定义输入、source annotation 缺失和 nonfinite 输出。
- **地址与容量**：逐 tensor 检查 shape×storage bytes、pack 范围、不重叠的同任务输出及每个源 reader 的 data edge；运行时按 writer dispatch 到所有 reader finish 的物理 ownership 区间检查地址别名。独立双 reader 负例在缺一个 WAR 时被拒绝，补全两个 reader 后通过。
- **通知与控制端口**：不用 simulator 的 `Ports` 代码，从已保存 trace 重建 lane 的最早可用时间；检查 notification 无丢失重复、producer finish→enqueue→实际排队 delivery、consumer 不早于 delivery 发射、descriptor admission 与容量限制。window=1、completion latency=10、wakeup cycle=5 的 late-admission 图对 A/B/H 都得到17 cycle。
- **背景服务**：用周期积分的闭式表达式重建 `[start,finish]` 中 busy 总时长，不调用 `Environment.finish`；确认积分服务量等于固定 task demand×外生 factor，compute 没有随机化。对浮点边界仅允许小于 `1e-7` cycle 的 segment nudge；总积分守恒照常检查。
- **机会等待**：从 dispatch/finish/admission/delivery/issue-port-release 的时间切分，重建每段合法 ready 替代任务和空闲资源，独立累加 wall-time union，与 simulator 指标一致。任务等待总和只标 `task_wait_cycles_not_wall_stall`，没有当成端到端 latency。
- **回归保护**：独立核对 R3 的257份旧结果与12个公共 sim Python 文件 SHA-256；与保存的 R3 manifest 相同。
- **tiny exact**：不用 event simulator，独立穷举7任务的5040个排列，得到52个合法 topology、6个不同资源顺序；以依赖/资源 earliest-time 递推得到最优静态期望3665 cycle，两个 clairvoyant 场景也均为3665。与主程序枚举一致，局部搜索 exact gap=0；该图 B 同为3665。这个负例不证明所有 source 图无收益。

## 强静态与因果归因边界

`static_search.optimize` 使用 target hardware 的 deterministic ready schedule 构造24种 priority 候选，再在独立 training 环境上评价合法 topological insertion 邻域；最终 validation 只挑计划，不指导局部搜索。test 参数不出现在该接口中。每次候选保留原图、mapping、buffer spans/reuse edges；不会因候选改变容量或总服务需求。

这是**有预算的局部搜索**。移动范围为±1/±2/±4，总序投影为各 resource 顺序；候选库去重后往往小于24。它没有证明 full-graph 最优，没有 joint mapping/tiling/fusion 优化，也没有执行 Stream/PipeThreader/LATTICE 的外部实现。tiny exact 的声明只能落在实际枚举的固定图、资源、服务场景和控制成本范围内。

固定 task 服务样本用于外生 task-service 实验；日历实验固定绝对时间背景服务，政策改变 start 后 duration 可以不同。这是共同环境而非同逐任务时长，属于合理区分。真实内存的调度诱发队列、bank/beat/credit 交互还没有建模。

机会等待的存在与 end-to-end 缩短不同。独立重放确认的是“当时确有合法可执行替代任务”，只有干预或配对最终 makespan 才能回答是否推进关键路径。确定性控制中若动态胜静态，首先说明本地固定顺序搜索还留下结构性 slack，不能归为未知完成顺序的信息价值。

## 不应隐藏的架构限制

1. 每 task 从 dispatch 到 finish 原子占有全部资源；默认 MXU/VPU task 都占其 core 绑定的 SRAM port，因此同 core 的 MXU/VPU 无法同时执行，即使数学独立。已增加 `split_engine_ports`：4个半带宽端口保持128 B/cycle合计带宽，MXU 与 VPU/DMA 静态分离，使同 core 可重叠。它仍是研究端口假设，非 bank/beat 设备模型；两类结果应分开解释。
2. 当前 graph 规模是缩尺单层/单块。Qwen 的完整 KV copy、FLUX 每次子图显式计算全模型可共享的 conditioning，以及 aggregate attention 的内部 scratch/phase 表示，都是强编译器还有优化余地的地方。
3. BF16/FP32 bytes 是存储/计费约定，NumPy 数组为 float64。未证明实际 layout vectorization、量化转换、array occupancy、bank conflicts；VPU nonlinear operation counts 也未校准。
4. `done/delivered`、notification history 与完整依赖 metadata 仍随图增长；有限 descriptor window 不等于有限总事件状态。没有有限 FIFO backpressure、credit、epoch/slot reuse 协议或二进制 descriptor decode roundtrip。
5. 含日历节流的 `resource_service_cycles` 表示该资源被任务占用的服务区间；不是有效字节带宽利用率。task issue rate 也不是 token/s 或 image/s。

本轮先例判定见 [prior_art_delta.md](prior_art_delta.md)。目前没有证据支持宽泛 `compiler contract + completion dispatch` 的 novelty；只有收费实测残余机会足够时，才有理由深入有界事件生命周期机制。

## 最终实验产物复核

主实验为 **70配置×32 test seeds×6 policies=13,440次执行**。其中16个主配置、28个硬件敏感性、12个attention/conditioning边界和14个分离端口配置。12个training seeds、8个validation seeds与32个test seeds两两不相交。独立程序从保存的 JSON 重建合同，验证selected order正是保存候选中的validation胜者；未发现偷看test service来挑计划。21个执行源码SHA匹配最终manifest。

`python -X utf8 -B -m r4.redteam_checks --artifacts` 已复核全部13,440条trace、120条counterfactual和420项seed0数值执行，并从samples重算全部420行summary的mean、p95、配对百分比与95%区间。结果见 [redteam_artifact_audit.json](../experiments/results/r4/redteam_artifact_audit.json)。没有未被当前run清单引用的残留counterfactual。前述504条独立构造控制检查不计入主样本量。

主结果保留为：

| 相对S的配对均值 | 正 / 负 / 零配置 | 最大改善 | 可解释范围 |
| --- | ---: | ---: | --- |
| B0，只有共同控制成本 | 3 / 64 / 3 | +0.104663% | 两个split-port Qwen service配置约+0.10%，另一个FLUX行约+0.00117%。 |
| B2，每task额外2cycle | 0 / 70 / 0 | -0.222927% | 没有收费正例；最差-9.998495%。 |
| B8，每task额外8cycle | 0 / 70 / 0 | -0.919758% | 费用进一步压倒这批图中的机会。 |
| H2，保留compute顺序 | 0 / 70 / 0 | -0.222927% | 当前resource-aware policy也没有收费正例。 |
| S8旧静态池 | 1 / 50 / 19 | +0.004288% | 更强S在50配置改善旧池，19持平，仍有1行极小退化；57/70搜索用满预算，不是全局最优。 |

这张表不是动态硬件总体胜率，也不是全模型性能。两处B0约+0.10%行的原始95%采样区间在零以上，但没有付额外选择费用，而且这些区间没有多重比较校正。独立两配置诊断把12个training B0执行次序加入固定静态候选（每配置仅产生1个新增unique order），validation仍选择原S，因而该简单静态加强没有消除小正值；这个posthoc诊断同样没有证明最优静态下界。完整参数和逐seed结果见 [redteam_static_probe.json](../experiments/results/r4/redteam_static_probe.json)，入口 [redteam_static_probe.py](redteam_static_probe.py)。

2,240条S执行中1,227条存在正的合法替代任务等待；跨配置等权的每执行`opportunity_union/latency`平均0.917039%，最大16.814899%。这个存在性指标不等于能够全部恢复的critical-path stall。120个离线单次提前执行全部真实触发，其中16缩短、84延长、20无变化。在split-port Qwen full seed0中，B0把`attention_residual`提前到等待中的VPU端口，并推迟某个operand pack，最终只缩短16cycle（9537.903→9521.903），小于其约25cycle的合法机会区间；fused seed3也只缩短16cycle，即使局部机会约246cycle。这说明“有合法ready任务”并不足以保证端到端获益。

### 事后compiler-hint校正

主B继承原critical-path hints，而S已经优化资源顺序。为了避免将hint不匹配当成不可修复的机制缺陷，额外对70配置运行了 **4,480=70×32×2** 次`B_order0/B_order2`。新hint只来自所选S在固定名义deterministic环境下的dispatch次序；图、mapping、地址、服务需求与控制成本不变。源码先冻结全部70个priority plan，再打开test评分表；这是复用现有test集的posthoc探针，不能写成独立confirmatory实验。

独立检查70个hint plan、全部4,480条trace、140项seed0数值与140行统计重算已通过，见 [priority_probe/redteam_audit.json](../experiments/results/r4/priority_probe/redteam_audit.json)，入口为 `python -X utf8 -B -m r4.redteam_priority_audit`。`B_order0`为10正/33负/27零，最高+0.686434%；`B_order2`为2正/68负，两个正均值分别+0.126651%（CI[-0.275177%,+0.528479%]）和+0.196797%（CI[-0.152241%,+0.545835%]），都跨零，无配置达到5%门槛。

hint顺序等于静态名义dispatch序，并不使动态政策等于固定资源序：高优先级任务尚未ready时，动态仍可提前执行别的任务并占住它稍后需要的资源。因此名义deterministic图仍可能退化，不能据此判断checker错误，也不能把同一个hint校正的结果泛化为所有动态priority策略。

**最终科学判定：R4提高了来源与执行证据质量，但这批缩尺、未校准图没有给出足以支付费用的稳定动态收益。** 继续扩张有限总事件状态、ROB或跨chip控制还缺前提。保留小幅局部信息价值、强静态改善与大量反向干预负例，下一轮应先验证全宽合法tile、真实内存服务与实际控制费用；本轮没有确认独立论文或专利novelty。
