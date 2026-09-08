# R12 共享总线守恒探针

2026-09-08，含独立 affine 红队后的更正。**参数化 full-payload 共享总线反例成立：若明确要求全部 262,144 bits 远程传输，一个共享 128 bit/cycle 资源被计为 512 cycles，而守恒下界为 2,048。真实 2conv 却不能直接套这个需求前提：最终是空间宽切分，对齐分片只需要 49,152 bits 的远端 halo，对应必要服务界 384 cycles。** 原先仅凭 allocation footprint 将其判为 full all-gather 的推断已撤回。独立反事实得到 14,344 的运行事实保留，但只代表 full-payload 合同下的条件性分析敏感度，不是已确认的 2conv 成本修复、Wormhole bug 或 H1 结果。

固定提交：`75748cc17e7c43add5a7d0d8f080841eb26531c4`。本次只读固定源码，执行 [shared_resource_probe.py](shared_resource_probe.py)，保存 [结构化结果](artifacts/shared_resource_probe.json)。脚本使用实际 STREAM 的 `Tensor/TransferNode/Core/Accelerator/MulticastPathPlan` 及路径生成器，不用鸭子类型伪造函数输入。上游 checkout 前后保持干净。原始 2conv 求解结果来自另一已完成的 smoke；该探针本身没有重求解，随后独立进行的分析性反事实见末节。

## 确切条件与守恒证明

取四个 core，每 core 初始唯一持有完整张量的四分之一；结束时各 core 都需要完整张量。输入是 16,384 个 16-bit word，共 262,144 bits；每 core 起始 4,096 word，另缺 12,288 word。没有额外初始副本、压缩或重算。

允许最强反解释：共享 bus 能免费广播给全部其他 core。此时每个不同 word 仍必须在共享 bus 上出现至少一次；四个源的不同 word 合集恰为全部 16,384 word。因此：

```text
minimum_shared_bus_payload = 16,384 × 16 = 262,144 bits
minimum_shared_bus_cycles = ceil(262,144 / 128) = 2,048
upstream_cost = ceil(262,144 / (128 × 4)) = 512
```

没有广播时，四个目标合计需要 49,152 个远端 word，即 786,432 bits / 128 = 6,144 cycles；本次采用更乐观的 2,048，避免把未定义的广播能力变成额外收费。512 cycles 的共享 bus 最多服务 65,536 bits，只有必需不同 payload 的四分之一。

## 本次真实类型执行

| 条件 | 路径来源 | 上游 cycles | 乐观守恒 cycles | 判断 |
|---|---|---:|---:|---|
| 一个 source → 四个 targets，单共享 bus | 上游 factory + path planner | 2,048 | 2,048 | 正控制，广播基数一致 |
| 四个 sources → 一个 target，单共享 bus | 同上 | 2,048 | 2,048 | 正控制，gather 基数一致 |
| 两 core 分片 → 两 core 全复制，单共享 bus | 同上 | 1,024 | 2,048 | 低计费 |
| 四 core 分片 → 四 core 全复制，单共享 bus | 同上 | 512 | 2,048 | 低计费 |
| 四个 sources → 四个不同 targets，单共享 bus | 同上 | 512 | 2,048 | 低计费，同 source/target ID 不是必要条件 |
| 四份等大 slice 各走一条独立链路 | 显式构造上游 `MulticastPathPlan`；不是 all-pairs planner 的输出 | 512 | 每 link 512 | 正控制，不能全局删除合法链路并行 |

共享 bus 五组均通过上游 `AcceleratorFactory.create_core_graph` 构建；全部 graph edges 共用 **同一 Python `CommunicationLink` 实例**，每条所选 plan 的 `links_used` 仅该一个对象。分别四条独立链路的正控制明确具有四个不同资源。

## 真实 2conv 是否另行补收了四份费用

原始 [allocation_ir.json](results/baseline_smoke/allocation_ir.json) 显示：Conv1 输出 `conv1_out` 在四个 core 上各分配 65,536 bits；Conv2 的 transfer output `conv1_out_1` 在四个 core 上各分配 262,144 bits。**这些仅是分配 footprint，不证明每个 consumer 必须读取全部 tensor。** 独立 affine 核查推翻了此前“输出通道分片、全 all-gather 必需”的解释，见下一节。

直接读取实际求解产生的 `pipeline/upstream-2conv/group_0/tetra/slot_latency_breakdown.yaml`，并核对 [result.json](results/baseline_smoke/result.json)：

- `Transfer(conv1_out)` 只出现于 **slot 4**，只有一个 transfer contributor；`raw_path_cycles=512`，`active_latency_absent_loops=512`，`slot_latency_cycles=512`。
- iterations=1，overlap=0；源/目标 tensor reuse ledger 都是 1。该 slot 没有 compute contributor；没有因 compute 把修正费用隐藏。
- 全部 slot 的和恰为 12,808，与总 latency 一致；不存在最终再乘 4 的补收。
- YAML 中 `reuse_factor` 和 `contribution` debug 字段是 null；不能把 null 当 0 或已检查值。上述判断使用有值的 slot/active 字段、独立 tensor reuse ledger、iterations 和总和，另检查实际代码链。

**附加 full-payload 传输要求后的固定 plan 纯算术替换**：`12,808 − 512 + 2,048 = 14,344`。该值恰与上游文档示例参考值一致，但不能证明实际 2conv 需要全部 payload 经过 bus。此算术没有重新优化、没有修正完整执行模型、没有设备测量；相等本身不能证明文档的计算合同或因果来源。

## Affine 红队更正：真实 2conv 是空间分片，只能证明 halo 需求

[shared_resource_affine_audit.py](shared_resource_affine_audit.py) 从原 smoke 的 `core_cost_lut.pickle` 恢复真实 `ComputationNode.operand_mapping`，读取最终 `steady_state_workload_final.svg` 的局部维度顺序，并绑定最终 IR 的 inter-core tiling。没有重新求解。机器证据与输入 hash 见 [affine audit JSON](artifacts/shared_resource_affine_audit.json)。

两 Conv 的局部维度实际顺序是 `(b,ox,oy,fx,fy,c,k)`，输入 affine map 为 `(b,c,oy+fy−1,ox+fx−1)`，输出为 `(b,k,oy,ox)`。最终 Conv1 局部维度是 `(z10,z6,z5,z2,z3,z4,z9)`，最终 Conv2 是 `(z10,z13,z12,z7,z8,z9,z11)`；因此分片 `z6/4` 与 `z13/4` 都是局部 **D1=ox**，与初始 mapping 的 D1 一致。输出 channel 分别为 z9、z11，并非分片轴。

独立执行真实 affine map 的有限访问枚举，给出合法的连续、对齐 source/consumer ox 分片见证；每组都保留全输出高度和全部输入 channel，clip 掉 padding：

| core | 输出 ox 区间 | consumer 所需输入 x 列 | 已有 source words | distinct input words | 远端 halo 列 | remote bits |
|---:|---|---|---:|---:|---|---:|
| 0 | `[0,8)` | 0–8 | 4,096 | 4,608 | 8 | 8,192 |
| 1 | `[8,16)` | 7–16 | 4,096 | 5,120 | 7、16 | 16,384 |
| 2 | `[16,24)` | 15–24 | 4,096 | 5,120 | 15、24 | 16,384 |
| 3 | `[24,32)` | 23–31 | 4,096 | 4,608 | 23 | 8,192 |

远端六列为 `{7,8,15,16,23,24}`，合计 `6×32×16×16=49,152 bits`；每个远端 word 只被一个相邻目标需要，理想广播也不再减少这个基数，单 bus 必要服务界为 **384 cycles**。512 没有被这个界否定；本审计同样不证明 512 已能包含真实协议、地址复用、零填充、局部复制与完成开销。

该见证使用按 core 顺序连续对齐的分片；它是源 affine/mapping 所允许的数学数据需求，不是已导出的 native 地址或已执行的 selective-halo kernel。当前 transfer IR 仍可能保守地物化完整中间 tensor，或者 cost path 本身只作近似；二者都必须通过更明确的数据搬运合同区分。**不能再将 2,048 当作本 2conv 计算的无条件必传下界。** 参数化 full all-gather 与四个不同 source/target 的共享 bus 反例则保留，因为它们的完整远端 payload 前提是显式定义的。

## 源码链与反解释

| 固定 STREAM 文件与行段 | 本次检查内容 | 排除/保留的解释 |
|---|---|---|
| `stream/parser/accelerator_factory.py:151–198` | bus 构建全部边时复用一个 `CommunicationLink("Any","Any",128,...)` | 不是四条独立 128-bit/cycle bus |
| `stream/hardware/architecture/noc/communication_link.py:9–66` | bus 实例及固定 bandwidth；未提供 per-source bandwidth multiplier | 128 是一个共享资源的值，不能免费变成 512 |
| `stream/cost_model/communication_manager.py:191–357` | planner 枚举全部 source×target pairs，再将物理 link 去重为 union | `len(sources)==len(targets)` 不证明一一配对或资源不相交；真实 planner 明确是 all-pairs |
| `stream/opt/allocation/constraint_optimization/utils.py:308–349` | 仅按端点数相等且>1设 `chains=n`；用 `tensor_bits/(min_bw*chains)` | docstring 的 disjoint-chains 前提未被函数核验；之后 absent-loop/reuse 只缩放，不补 shared-resource payload |
| `.../transfer_and_tensor_allocation.py:950–960` | 同 slot 同 link 的 path-choice usage 总和≤1 | 只排斥不同 transfer 的同时使用；同一 transfer 内的四个 source 仍作为一个 choice 计费 |
| 同文件 `1193–1207`, `2333–2362` | chosen transfer 的 active latency 直接约束 slot；没有按多源累加 link payload | 未发现该成本链中的四倍补收 |
| 同文件 `1520–1558` | total=iterations×slot sum−overlap；offchip traffic 是下一级目标 | traffic tie-breaker 不会补成该 transfer 的服务时间 |
| `stream/cost_model/steady_state_scheduler.py:282–350`, `943–955` | 一次 TETRA solve 返回总值；iteration 数来自 temporal loops | 本 fixture iterations=1，无其他四次发射 |
| `stream/workload/node.py:58–92`, `tensor.py:9–36` | 真类型与 full tensor bits 定义 | 262,144 是输入 tensor 总 bits，不是已经乘 4 的虚拟流量 |

最强保留解释：对于确实一一配对且资源不相交的等大 slices，除以 chains 合法；本次独立链路正控制支持保留这个分支。source/target 同 cores 且布局相同可本地使用；空间 stencil 分片可以只交换 halo——后者已经由实际 2conv affine 证据支持，因此不是尚待排除的弱假设。多总线、per-source link、压缩或预存副本也可能改变参数化反例的下界，但都需另行定义资源/输入合同。

## 最小可辩护修正域

先将修正严格限于**已识别单一共享 bus，且已证明全部 tensor bits 都是远端必传 payload**的路径：其 aggregate bus payload 不得因 source/target 个数相等被除以 n。在这个显式 full-payload 合同下，可用 `ceil(tensor_bits / bus_bandwidth)` 作乐观收费；仍不保证完整 broadcast、仲裁和完成语义已校准。**目前不能凭实际 2conv 的 footprint 自动判其属于此域。** 必须先分清 full-copy transfer 合同和支持本地复用/halo 的强静态合同。

不能把 `chains=1` 全局应用到所有路径，否则会错误惩罚四条确实独立的链路。不能仅检查 `len(links_used)>=n` 就宣称 disjoint：链路数量不代表每条 slice 所经共享资源互不相交。更普遍的后端应保存 source-slice→target 的数据关系、逐路径 link incidence/multiplicity 与 controller alias，计算每个真实共享资源承载的 bits 下界，再允许有证据的并行。现有 union-of-links 不足以对所有情况恢复这些信息。

只有实际数据需求前提获证且实现合同一致时，才可称 P0 成本修复；**当前 2conv 干预不满足这个条件，只是 full-payload 合同的条件性敏感度分析。** 未来若在获证合同下由已有 TETRA 消除差异，可归入 H0 的工程解释；不能把 512→2,048 的成本上调倒写成新编译器性能改善。

## 复现

```powershell
& research/r12/.venv/Scripts/python.exe -X utf8 -B research/r12/shared_resource_probe.py
```

结果同时保存固定源码 hash、实际类型五组案例、独立链路正控制、word 守恒账本及真实 smoke artifacts 的 hash。再次运行只更新本探针 JSON，不覆盖原始 smoke。

## 随后执行的分析性反事实：确实进入 TETRA

在运行之前另写 [counterfactual contract](shared_resource_counterfactual_contract.json)，随后执行 [独立 runner](shared_resource_counterfactual.py)。该事前合同的 `scope_justification` 当时错误地把分配 footprint 当作完整 all-gather 需求；**这个前提已被后续 affine 审计推翻，原合同与运行原样保留为审计历史，不继续当有效 2conv 成本修复合同使用。** 干预实质是对 `Transfer(conv1_out)`、shape `[1,16,32,32]` / 262,144 bits、`COMPUTE_TO_COMPUTE`、source/target 同四个指定 core、单共享 bus128 的路径施加额外 full-payload 收费；其余路径不变。没有修改固定依赖源码。

runner 在单独进程内绑定 `utils.get_transfer_latency_for_path` 和 TETRA allocator 引入的同名函数，再直接调用原 `baseline_smoke.run`；原函数的输入、solver sentinel、constraint toggles、非退化、干净 checkout 等检查全部保留，没有替换或跳过。输出的 `process_overlay` 明确记录干预；`AllocationIR.overlays=[]` 只表明无上游安装式 overlay，不用它宣称该进程未干预。

实际独立输出：[counterfactual result](results/shared_resource_counterfactual/result.json) 与 [重新求解 IR](results/shared_resource_counterfactual/allocation_ir.json)。结果：

| 检查项 | 实际结果 |
|---|---|
| 函数绑定 | utils 与 allocator 两处均确实指向 overlay |
| 调用数 | helper 总计 40 次；其中 8 次满足已登记干预域，全部从 512 改成 2,048；8 是模型/trace/helper 调用次数，不是 8 次硬件动作 |
| 进入真实 allocator | 8 次中 5 次来自 TETRA `_transfer_latency_for_path`，另有 2 次 trace helper 和 1 次最终路径检查 |
| 真实重新求解分析 latency | **14,344**，最终 solver stats 为 OPTIMAL；此 stats 仍具有原 lexicographic 最后阶段的报告范围 |
| 所选 transfer | 单共享 bus 的同一四 core 路径，最终 single-firing cost=2,048 |
| 模型 slot | slot 4 的 raw、active、slot 三值均 2,048；其余 slot 与 iterations/overlap 未造成额外倍率 |
| 所选方案 | `mapping_nodes` 与 `fusion_splits` 均逐 JSON 比较等于原始结果 |
| 固定源码与原结果 | STREAM checkout 前后干净；原始 smoke 的 result/IR SHA-256 前后相同 |

这使 14,344 具有两份清楚区分的条件性证据：前节的**追加 full-payload 要求后的算术**，以及本节**显式 overlay 下真实 TETRA 重新求解**。两者相同，但都不验证“实际 2conv 必传完整 payload”的错误前提，也不是原生硬件时间。本例只展示 full-payload 合同成本敏感度；不能据此宣称已完成 P0 成本修复。本例没有出现计划排序改变，更没有获得 P1/H1 完整 MLP 收益。

以下仅用于复现已记录的条件性 full-payload 干预，不能当修复资格验收；重新研究强 P0 必须先写包含 affine demand/local reuse/halo 的新合同。复现时必须选择一个尚不存在的结果目录；runner 拒绝覆盖已有结果：

```powershell
& research/r12/.venv/Scripts/python.exe -X utf8 -B research/r12/shared_resource_counterfactual.py --output research/r12/results/shared_resource_counterfactual_new
```
