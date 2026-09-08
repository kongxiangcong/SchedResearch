# R13 TETRA seed lower 的独立审查

2026-09-08。结论：`resource_order` 是一个真实 TETRA 输入/输出可追溯、在当前 F 合同中合法的 **p0000 seed 适配**。它保留了指定的计算位置、张量驻留 core、payload 路径和资源偏序，但尚不能称完整 P0 portfolio 已准入，也不能作为证明新增编译算法收益的强基线分母。

本次只读审查，未重跑 TETRA、DES 或候选搜索，未修改模型与成本。实际执行的是对归档 JSON/gzip 的完整解析、来源/内容哈希核验，以及对已归档轨迹再次运行独立 `audit_trace`、`audit_builder_rules` 和全部 lower 偏序义务检查。下列周期数来自原回执；此次复核没有产生新的性能样本。

## 阅读与复核范围

| 材料 | 本次检查 | 支持的判断 |
|---|---|---|
| [port_micro_tetra.py](port_micro_tetra.py) 全文，尤其 `R13PhysicalPaths`、`target_accelerator`、`target_scheduler_class`、`source_graph`、`main` | 检查源码 | 真实上游调用链、目标输入适配、固定选择域和模型边界。 |
| [lower_tetra.py](lower_tetra.py) 全文，尤其 `source_intake`、`lower`、`run_mode` | 检查源码 | 实际导入的选择、额外偏序、地址绑定和准入条件。 |
| [目标 seed 导出](artifacts/tetra_micro_p0000_target.json) | 完整解析；核对所有 tensor/path 的候选数、选择、三阶段求解记录及物理账本 | 24 个 tensor 各只有一个 core 选择；12 个 transfer 各只有一个 path；当前全部 depth=1、reuse stop=-1。 |
| [lower 回执](artifacts/tetra_lower_receipt.json) 及其两组归档 spec/trace | 完整解析；压缩文件字节哈希与解压后规范 JSON 哈希全部匹配；复核 admitted trace | 合法性检查和 2127 条偏序义务通过，仅适用于该具体 seed。 |
| 固定 STREAM `steady_state_scheduler.py:280–355`、`transfer_and_tensor_allocation.py:104–168`、`workload.py:902–997` | 检查原始源码 | slot 顺序在 allocator 求解前由资源感知拓扑启发式产生，不是 GSCIP 联合优化的排程决策。 |

固定 STREAM commit 为 `75748cc17e7c43add5a7d0d8f080841eb26531c4`。导出回执记载源码前后干净；本次另外核对 port producer、lower producer、model builder、DES、独立检查器、轨迹审计器、hardware JSON 的当前 SHA-256 与回执一致。目标导出 SHA-256 为 `1679bc3563be378e29b24018960f96966dd51cfca941978ce93203c520affb48`，lower producer 为 `945e909b780c6e28a0adea18a94fd444d382612555b74aa81033cc7a1157feee`。

## 哪些决策来自真实 TETRA

port 运行原 `SteadyStateScheduler.run()` 和 `TransferAndTensorAllocator.solve()`，使用可追溯的 workload、mapping、allocation/path 对象；定向扩展主要提供物理 IO、channel 和路径输入。`--target` 分支使用 4 个 compute core、12 个物理 DRAM channel 和 480 条有向 router link，不再使用旧 shared-bus 投影。计算需求为明确注册的整数微图代理，不能归为真实矩阵内核测量。

三阶段 GSCIP 记录均为 OPTIMAL，目标/界依次为 latency 632/632、offchip traffic 196608/196608、buffering 24/24。但本次输入已固定 p0000 的计算位置、NoC 和放置：24 个 tensor 的 `choices` 均长 1，12 个 transfer 的 `choices` 也均长 1；一个 fused group，迭代/倍率均为 1。该结果证明真实求解器处理了这个受限问题，不能证明它搜索过 576 种联合决策。导出顶层 `analysis_latency_cycles=626` 与阶段目标 632 分开记录，lower 未将任一数值转换为 F release 时间或黄金性能值。

尤其需要区分 slot 与 solver 决策。上游 `steady_state_scheduler.py:305–307` 先取得 `self.ssw.get_timeslots(self.mapping)`，再将它传给 allocator；后者 `:124` 直接保存为 `self.slot_of`。`workload.py:902–997` 使用有深度优先倾向的拓扑排序，并依据可选 core/link 资源集合安排同 slot 共存。lower 保留的是这一**原调度器启发式的资源顺序**，而非三阶段 GSCIP 求得的全局最优资源顺序。

## Lower 保留和增加的约束

| 项目 | `resource_order` 的实际行为 |
|---|---|
| 计算位置 | 核对 8 个计算节点的 selected 单 core，与 F 的 source/target 驻留 core 一致。 |
| 张量位置与大小 | 核对 24 个逻辑 view 的 core、8192-bit footprint、depth=1；为它们绑定 F 已登记物理 span。没有导入一套上游逐地址分配。 |
| 路径 | 对 12 个 payload 逐项核对被选 path ID、src/dst/NoC、1024B、完整有向 route 和实际源/目标 16B 块。request、ACK、通知是 F 补充的有成本工作。 |
| 单 core 计算顺序 | 按上游 slot 排序，将前计算 `published` 完成加到下一计算全部 local-read job 的依赖。 |
| 共享 transfer 资源顺序 | 对每条被选 payload 资源，收集前 transfer 使用该资源的所有操作，将它们的完成加到后 transfer 的 `ISSUE` 依赖。 |
| 上游全局 slot 屏障 | 不保留不同资源之间的全局屏障；不保留分析时间戳。 |
| 执行与复用义务 | 保留 F 的请求/返回、逐块源读和目标可见、source-release、显式 notice/token 观察、跨代地址保护、有限 buffer/credit 和 bank/port/channel 服务。 |

共享资源 lower 边是**额外保守约束**。它要求“前 packet 在该资源上的全部操作已完成，后事务才可 issue”；原本仅为保持资源进入顺序，后事务通常可以提前完成命令、源读或上游网络工作，等待到该共享资源再受序约束。现在的 lower 会禁止这种合法预取/流水，可能拉大 F 时间。它是可审查的合法适配，但尚不能称对 TETRA 的最佳 F 细化，不能把随后放松这些边得到的收益直接归因于新算法。

接口还有一个未来扩展边界：`source_intake` 只明确拒绝非 depth=1；对 reuse level 的 guard 实际接受任意整数，并未实现一般的复用层级 lower。当前 24 项 stop=-1，因此不影响这一个 seed；扩展 portfolio 前须拒绝未实现层级或补全语义，不能仅凭类型检查宣称 reuse 选择已保留。

## 多个逻辑 tensor 绑定同一 source span

回执的 24 个逻辑 view 实际对应 14 组不同物理 span：8 个不同的 DRAM input/output span，以及 6 个 L1 payload span。每个 producer 的 source 地址 `0x10000` 同时映射本链两个 epoch 的 input 与 doubled，共 4 个逻辑 view；每个 consumer 的 receive `0x20000` 和 result `0x30000` 各承载两个 epoch。L1 物理 payload 仍为 6KiB，控制块另计，2KiB RF scratch/tile 另计。

这不是 TETRA 选出了跨逻辑 tensor 的原位别名。port 给上游的是 core 容量与逻辑 tensor，lower 再绑定 F 的固定地址生命周期。当前合法性来自具体 F 操作：producer 先把完整 input 读入 RF，再原位写 doubled；下一代 load 等上一代 peer 的 source-release 可观察事件；receive 重用等旧 consumer 最后读与 token 观察；result 覆写等旧 output 源读释放。独立数据轨迹复核确认了这些约束和不同块/epoch 的数值身份。

因此可以说“selected core、footprint 和 depth1 view 已核对并合法映射至注册 span”，不能说“原 TETRA 的逐地址分配与全部逻辑生命周期原样保留”。上述复核也不是对未执行排程或任意张量原位变换的证明。

## 两种 lower 的证据结果

`whole_slot` 被拒绝，有依赖环且执行 deadlock。典型环涉及 chain1 epoch1 load 在上游 slot6、epoch0 peer 在 slot7；F 的 source 跨代保护要求旧 peer 先完成源读，新 load 才能开始，全局屏障却反向要求先完成新 load。该冲突说明“直接全局 slot 屏障 + 新的有限地址复用合同”不兼容，不能据此说原 TETRA 在其自身内存合同下非法，更不能使用这个失败结果作收益分母。

`resource_order` 的已有执行为 `ok`，无依赖环。本次重查归档 trace 的 2127 条新增偏序义务，失败数为 0；独立 builder 规则检查通过 40 packets、3048 link operations、1296 memory operations、2576 个 16B 块；独立数值/生命周期审计通过 256 个输出块、1280 个数据读取块、1288 个含控制写入块、8 个控制观察、2576 个独立内存完成事件及 4584 个操作时间。

| 归档 F 指标 | ticks | model cycles |
|---|---:|---:|
| output visible | 128724 | 3575⅔ |
| final ACK observed | 133368 | 3704⅔ |
| quiescent | 133944 | 3720⅔ |

这些是具名模型中合法 seed 的时间，不是芯片测量、跨工具精度证明或编译器收益。此处未新增一次逐 tick 全回放；此前模型资格的独立 tick 回放也不能自动替代该具体 lower trace 的回放。

## 对当前 gate 的判定

回执明确保留 `p0_portfolio_qualified=false` 和 `new_algorithm_benefit_claimed=false`，与本次审查一致。当前只能登记一个可追溯、已通过功能及偏序检查的 TETRA seed。完整 P0 仍需同候选域/预算下的强基线选择、允许的 F 细化和窗口调整、其他合同规定的 portfolio 成员、搜索/最优性边界，以及完整模块结果。576 个 F 候选的枚举即使完成，也不自动完成这些基线义务。

M0 的跨工具步骤也必须独立列出：tt-npe 实际执行仍受 WSL `E_ACCESSDENIED` 阻断，固定源码规则检查不等于跨工具执行通过。不能把该 seed 准入或本地枚举改写成“完整跨工具链已通过”。
