# R12 强基线源码准入审计

日期：2026-09-08。固定 STREAM commit：`75748cc17e7c43add5a7d0d8f080841eb26531c4`，包版本 `1.14.1`。本报告依据该提交的官方源码；网页上的 latest 文档只用于交叉定位。没有修改 STREAM 源码，没有构造 Wormhole 性能结果。

## 结论

STREAM/TETRA 可以作为本轮**必须先移植并加强的编译基线**，其现有 placement、路径候选、驻留、双缓冲、slot 资源排斥和 AIE 同步实现已经覆盖相当一部分问题。安装不需要商业求解器：固定提交默认使用 OR-Tools GSCIP；Gurobi 是可选 extra。成功运行官方 2conv 只能准入工具链，不能准入 Wormhole P0。

当前最具体的三个移植问题是：多个外存 endpoint 与共享 controller 的身份如何进入原生输入/输出放置；Wormhole 两条合法 NoC 路径如何替换通用最短路径候选；源读完、目标可见、通知和等待范围如何连接到合法 buffer 生命周期。这些首先属于后端建模工作。只有正确移植后的 P0 仍留下完整模块残差，才支持进一步研究新方法，符合[本轮合同](../../SchedResearch_reassessment_evidence_20260907/proposal_contract.md)。

## 安装约束与真实入口

| 项目 | 本次核实 | 执行要求 |
|---|---|---|
| Python | `requires-python >=3.12`；固定 package metadata 为 `stream-dse 1.14.1` | 使用本轮独立 venv；避免其他 checkout 的 editable import 干扰。 |
| 基础依赖 | `zigzag-dse==3.8.5`、`cerberus`、`ortools>=9.15`、`pydantic>=2,<2.12`、`xdsl>=0.29.1,<0.30` | `pip install -e <固定源码目录>` 后冻结实际 transitive versions。不能把这些宽范围当完整 lock。 |
| MCP extra | 源码明确记录 `fastmcp` 传递依赖与固定 xdsl / typing-extensions / pydantic 冲突 | 本轮不安装 `[mcp]`，无需借升级 xdsl 改变冻结来源。 |
| 商业 solver | `[gurobi]` 才安装 gurobipy；Gurobi backend 创建/求解要求有效许可 | 默认选 `ortools_gscip`。`import gurobipy` 或装好 wheel 不能证明许可可用。 |
| AIE 工具链 | `stream-setup-aie` 是另一个安装入口，服务 AMD AIE codegen；平台 wheel 限制在 Linux x86_64 / CPython 3.12 或 3.13 | Wormhole 研究的 generic CO smoke 不需要 AIE 工具链，更不需要装 AMD 驱动。 |
| 上游软件许可 | 此提交 `LICENSE:1–19` 为 MIT；`pyproject.toml:31` 的 BSD classifier 与 LICENSE 不一致 | 保留上游 LICENSE 与版权声明，记录 metadata 差异，不据 classifier 改写来源许可。 |

来源：[pyproject.toml:22–68](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/pyproject.toml#L22-L68)、[README 安装说明](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/README.md)、[LICENSE](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/LICENSE)、[Gurobi backend:629–637 / 772–784](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/solver/solver.py#L629-L637)。本报告只核实工具配置，不对用户是否持有商业许可作假定。

真实 generic CO 调用链是：

`scripts/main_stream_co.py → optimize_allocation_co_generic → ConstraintOptimizationAllocationStage → SteadyStateScheduler.run → TransferAndTensorAllocator.solve → ORToolsBackend.mathopt.solve`。

CLI 不带 `--mapping` 时自动生成 mapping；`--mapping` 调用手写 mapping API。generic API 返回 `StageContext`，其中有 scheduler、分组及总分析 latency。AIE 的 `main_swiglu.py` / `main_gemm.py` 会硬编码相应 AMD 目标，不能当本轮 Wormhole 入口。见 [CLI:64–95](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/scripts/main_stream_co.py#L64-L95)、[API:304–351](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/api.py#L304-L351)、[allocation stage:67–88](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/stages/allocation/constraint_optimization_allocation.py#L67-L88)、[scheduler:282–381](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/cost_model/steady_state_scheduler.py#L282-L381)。

## 能力边界：不能靠命名推定已经支持

| 本轮问题 | 已检查到的真实能力 | 尚未准入的 Wormhole 合同 |
|---|---|---|
| 计算与张量放置 | mapping 提供 core candidate groups 与 inter/intra-core tiling；TETRA 的 `x_tensor_choice`、`y_path_choice` 联结张量和路径。 | auto mapping 是一个默认候选生成过程；不代表所有分片、fusion、placement 全局最优。需给 P0 足够的相同候选与 DSE 预算。 |
| 路径与共享链路 | `MulticastPathPlan` 包含 sources、targets、links_used；同一 slot 的同一 `CommunicationLink` 使用总和 `<=1`。因此“只知道总 byte-hops、不看共享链路”不是对当前 TETRA 的准确描述。 | 路径库由通用 k-shortest simple paths 和 beam search 形成，不自动遵守 Wormhole NoC0/NoC1 确定性路由和请求/响应路径。必须保留真实物理 torus，并明确合法路径。 |
| 外存/共享 controller | hardware 有 link/bus 资源、每 core 的内存容量/带宽；多个候选可共享一个 link/bus 对象。 | 顶层 `offchip_core_id` 为单值；`InEdge`、`OutEdge` 默认都返回该同一 offchip core。多个 controller 与多个 endpoint 别名不因画多个 memory nodes 就自动成立。 |
| 驻留与双缓冲 | solver 选择 reuse stop level，容量与 `tiles_needed_levels` 联动；默认 transfer context 启用 double buffering。 | 容量目前按所需 tile 数聚合；没有在这里看到按 NoC 源最后读取、目标可见、通知三个事件决定的原生地址复用证明。 |
| FIFO / BD / DMA | TETRA 收集对象 FIFO、BD 和 incoming/outgoing DMA 需求，namespace strategy 加实际限额；当前内建 strategy 为 AIE2。 | `constraint_selection=True` 只代表开关打开；不保证某个自造 Wormhole namespace 注册了正确策略。AIE 限额与邻接共享内存规则不得借用于 NIU。 |
| 发送窗口 | 分支依赖和资源可行性决定 timeslot；相同类资源有候选交集检查；跨 iteration 有 overlap / reuse。 | `slot_of` 在 TETRA 初始化时已固定，MILP 中没有一般的 send release/window 和三事件完成时间变量。先检查现有排程/合法预取可吸收多少残差。 |
| wait / 完成 | AIE lowering 的 `SyncDMAs` 明确区分 descriptor 回收和 output 到达；每 FIFO 的第三次传输等待第一次，序列末尾等待仍在途的传输。 | 这证明生命周期相关 wait 优化已有具体实现。尚未存在可直接执行的 Wormhole CB / NoC / notification 后端；不能将 AIE 机制或费用迁移为 Wormhole 事实。 |

逐项依据：

- placement / reuse / 内存：[TETRA:91–218](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py#L91-L218)、[775–847](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py#L775-L847)、[963–1106](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py#L963-L1106)；[mapping 文档](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/docs/source/mapping.md)。
- 路径候选与排斥：[CommunicationManager:127–131 / 191–260 / 313–357](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/cost_model/communication_manager.py#L191-L260)；[TETRA:950–960](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py#L950-L960)。
- 单 offchip 语义：[hardware 文档](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/docs/source/hardware.md)、[scheduler:957–966](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/cost_model/steady_state_scheduler.py#L957-L966)。这不证明源码无法扩展，只证明**当前默认入口**没有多 controller 原生合同。
- namespace 限额：[context:107–177 / 215–303 / 380–439](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/context.py#L380-L439)；[TETRA DMA:1446–1518](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py#L1446-L1518)。只有 `stream.constraints` 中的 AIE2 内建注册，见 [pyproject:79–86](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/pyproject.toml#L79-L86)。
- timeslot：[Workload.get_timeslots:902–997](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/workload/workload.py#L902-L997)。它按拓扑优先级贪心安放，slot 内候选组合做 backtracking；不是对全局 slot 顺序作 exhaustive MILP。
- 原生 AIE waits：[aie_convert_ofs.py:1617–1666](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/compiler/transforms/aie_convert_ofs.py#L1617-L1666)。本次只读该段，不声称验证或运行了完整 AIE codegen。

`get_transfer_latency_for_path` 使用最窄链路带宽与 tensor bits，并在源/目标一一配对时按并行 chains 分摊，空路径为 0。该函数不读取 VC、credit、packet header、控制器队列或完成/通知事件。因此 path cycles 和完整 Wormhole elapsed 的关系仍需校准；不能把 shortest-path 成本误差当某个 placement 非法的证明。见 [utils.py:308–321](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/utils.py#L308-L321)。

## “最优”必须写清楚

当前 TETRA 开启 DMA 时的第一级目标为 `total_lat + max_core_dma_in + max_core_dma_out`，后续依次最小化 offchip traffic、buffering。它优化了具名模型目标，不等于纯 elapsed 最小。`total_lat` 又来自固定 timeslot 的 slot latency 和 iteration overlap，不是原生设备时间。见 [TETRA:1520–1563](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py#L1520-L1563)。

OR-Tools lexicographic 实现逐目标求解并锁定前级目标，但 `self._result` 被每一阶段覆盖；`solve_stats()` 返回最后一阶段的 objective / status / gap。因此输出的 objective 不能标成 cycles；最后一阶段 `OPTIMAL` / gap=0 也不能单独当作每个前级目标及整个候选生成空间全局最优的证据。后续 P0 性能比较应保留每阶段终止状态、bound 与 incumbent，以及实际纯 elapsed；若不修改固定源码，至少由外部 instrumentation 留下各次 `mathopt.solve` 的完整状态。见 [solver.py:1035–1076](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/solver/solver.py#L1035-L1076)、[1094–1120](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/solver/solver.py#L1094-L1120)。

## 可执行 smoke 与证据等级

本轮 [baseline_smoke.py](baseline_smoke.py) 使用固定源码的 public API 和真实 TETRA 数据结构，不重新实现优化器。它先解 `min x, 2x >= 5, x integer` 的 GSCIP sentinel，要求 `OPTIMAL` 且 `x=3`；随后运行官方 2conv / TPU-like quad-core fixture，打开全部公开 constraint toggles，导出 `AllocationIR`、实际 transfer paths、版本、输入 hash、solver 状态与分析 latency，并检查 scalar fallback 与 overlay 污染。

```powershell
& 'D:/dsh-proj/SchedResarch/research/r12/.venv/Scripts/python.exe' -X utf8 -B 'D:/dsh-proj/SchedResarch/research/r12/baseline_smoke.py'
```

实际结果：[results/baseline_smoke/result.json](results/baseline_smoke/result.json) 为 **PASS**，完整 IR：[results/baseline_smoke/allocation_ir.json](results/baseline_smoke/allocation_ir.json)，日志：[attempt2.log](results/baseline_smoke/attempt2.log)。GSCIP sentinel `OPTIMAL, x=3`；真实 TETRA 完成，最终阶段 `OPTIMAL, gap=0`，分析总 latency **12808 cycles**，5 个可检查的 transfer path，`scalar fallback=false`、无 overlay，STREAM checkout 执行前后 clean。此处为上游分析 fixture 执行证据。

第一次运行同样完成了 TETRA，并得到 12808；其后本轮 smoke 导出代码误把已求解的 `tuple[MulticastPathPlan]` 当成计算 mapping 的嵌套结构，发生 TypeError。修正的只有本轮导出脚本，重跑得到上述 PASS；首次 [attempt1.json](results/baseline_smoke/attempt1.json) 保留。没有修改 upstream 来追逐数值。

上游 README / quick-start 参考值为 **14344**，与本机固定源码及实际依赖组合的 **12808** 不同。该差异尚未归因，不以文档参考值当通过门槛，也不把本机数值解释为改进收益。两者均为 toy 配置分析 cycles，**不是 Wormhole 性能目标或原生硬件结果**。[官方 quick start](https://kuleuven-micas.github.io/stream/getting-started/)与固定 [tests/test_co.py](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/tests/test_co.py)用于定位 smoke；上游测试主要检查结构与正 latency，不执行该网络的数值计算。

本 smoke 显式写出 `wormhole_p0_qualified=false`、`source_visibility_semantics_tested=false`、`controller_domain_semantics_tested=false`，防止工具安装通过被升级为硬件合同通过。

### 从真实输出发现的建模待查项

`Transfer(conv1_out)` 的实际 plan 中，tensor 为 262144 bits，sources 和 targets 均为 `[0,1,2,3]`，`links_used` 只有共享 bus `CL(Any, Any, bw=128)`；上游返回单次 path cost **512 cycles**。源码按相同源/目标数量直接设 `chains=4`，计算为 `262144 / (128 * 4)`，没有在该函数内验证 chains 的链路独立性。假如整个 262144-bit tensor 必須经过这一个共享 bus，光 payload 服务下界应为 2048 cycles；但还需核查该 transfer 的实际分片、multicast/本地保留语义，再判断本例是否确实满足该前提。

因此这是一个有输入和源码位置的**共享链路分摊假设待查项**，不是已复现的原生硬件错误。本轮禁止拿该 toy 分析 latency 作为 Wormhole 校准。这个问题若由正常的共享资源计费修正消失，应归于 P0 准确建模，不属于 P1 新算法贡献。[结构化路径输出](results/baseline_smoke/result.json)、[成本公式](https://github.com/KULeuven-MICAS/stream/blob/75748cc17e7c43add5a7d0d8f080841eb26531c4/stream/opt/allocation/constraint_optimization/utils.py#L308-L321)。

**本轮后续反证：**最终operand maps和SVG确认Conv1切分z6、Conv2切分z13，二者均为ox空间宽度，撤回“真实2conv要求完整all-gather”的推断。对两算子按同序连续四等分的合法所有权见证，精确affine枚举只需49152个远端bits，128 bit/cycle下对应384个payload服务cycles。因此2,048不是该计算的已证必需下界；512也尚未得到原生实现证明。条件性full-payload费用干预确实重求解得14344且mapping/fusion不变，但不能解释为已确认P0修复。[需求审计](artifacts/shared_resource_affine_audit.json)、[独立审计](independent_research_audit.md)

## 强 P0 的后续准入条件

1. **来源与数值固定。** STREAM/ISA/tt-metal 与板卡 descriptor、harvest mask、固件有 hash；Qwen3.5 完整 MLP 的 M/H/I、dtype、归约树、cold/warm 权重与输入/输出位置冻结，BF16/FP32 与 FP64 oracle 的差异单列。
2. **相同硬件资源。** controller 与 endpoint 为不同实体，有显式 alias 映射和共享服务预算；双 NoC 的路由、方向、端点、请求/响应资源合法，不能因多个 endpoint 虚增 controller 带宽。四活动 tile 不删除其他 torus 转发点。
3. **候选不被削弱。** 给 P0 同样的 placement/tiling/fusion/prefetch/双缓冲/合法路径与 wait-scope 优化机会；记录候选计数、搜索预算、solver 每阶段状态及 gap。禁止用 `get_timeslots_simple`、关闭资源约束或只跑默认 auto mapping 作为“最强”结论。
4. **执行事件准入。** 原生 CB / NoC plan 区分 source-last-read、destination-visible、notification；证明每个 reuse 的 last-reader、RAW/WAR/WAW、终止和 credit 守恒。各 witness 家族在真实候选中实际触发，零动作不得进入收益比较。
5. **原生运行对照。** 同一 P0/P1 plan 分别进入 R0/Rd；controller/path/NIU/等待的粗成本先用 tt-npe 筛选，再以实机可观测事件校准。ttsim 功能通过不替代周期数据。
6. **收益与关闭。** 先执行合同 G0/G1，再在至少两个预登记完整配置评价 3% 净 elapsed 与约 1 个百分点相对误差要求。若仅补正常硬件资源、生命周期或 wait 规则即可由已有求解器得到同样计划，应登记为 P0 吸收、后端工程或负结果，不能继续人为保护 H1；H2 仍独立受条件门限制。

## 本审计阅读覆盖

| 文件 | 本次范围 | 证据状态 |
|---|---|---|
| `SchedResearch_reassessment_evidence_20260907/proposal_contract.md` | 全文 | 合同阅读，未修改 |
| 同目录 `evidence_manifest.json`、`evidence_ledger.md` | 全文 | 继承阅读范围与缺口，不将其历史 PASS 升级为本次验证 |
| 固定 STREAM `README.md` / `pyproject.toml` / `LICENSE` / hardware、mapping docs | 全文 | 官方线上验证 + 本地固定源码核实 |
| `scripts/main_stream_co.py`、allocation stage | 全文 | 入口核实 |
| `stream/api.py` | public generic/with-mapping/DSE 定义、backend 验证和转发章节 | 节选源码核实 |
| TETRA allocator | 初始化/候选、placement/path/link/capacity/reuse/FIFO/BD/DMA、目标、solve 段 | 定向源码核实；未声称全文阅读 3200 行 |
| `utils.py` | 全文 | 路径分析成本核实 |
| CommunicationManager / namespace context / Workload | 上述精确行段与相关方法 | 定向源码核实 |
| `solver.py` | backend factory、Gurobi license、OR-Tools optimize/lexicographic/stats 段 | 定向源码核实 |
| `tests/test_co.py`、`tests/unit/test_solver_facade.py` | 全文 | 只读上游验收意图；是否运行见运行回执 |
| AIE `SyncDMAs` | 1617–1666 | 只读已存在 wait 策略；未安装/运行 AIE |

没有读取仓库其他方案初稿、演示材料或其解析副本；没有复跑冻结历史性能结果。科研聊天引用的完整恢复及证据目录其他文件覆盖由本轮总报告记录，本子审计不冒领该范围。
