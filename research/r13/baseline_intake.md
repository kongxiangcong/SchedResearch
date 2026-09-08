# R13 强基线接入核查

日期：2026-09-08。执行依据：[proposal_contract.md](proposal_contract.md) 是唯一当前合同。本文是源码与依赖接入记录，不追加第二套验收门；R12 审计末尾的板卡/native 要求属于冻结历史，不能作为 R13 前置。

**结论：真实 live-candidate 导出、micro目标IO/路径输入适配及一个保留来源决策/资源次序的F seed已实际运行通过；完整R13 P0 portfolio尚未准入。** 下文保留从工具链到真实候选、再到限定seed的推进证据，最新seed范围见§7。仅重放原 2conv JSON、把原分析 cycles 换成仿真 cycles，均不能证明已给原方法相同优化机会。

## 1. 本次实际执行与证据边界

初始 intake 执行了必要的 import / 整数求解 / 保存 IR 结构校验。随后按本会话实施要求，新增进程内只读观察器，并实际运行官方2conv管线取得live对象；新结果均在R13，不覆盖R12。未运行 R13 目标 P0、未修改固定依赖源码。

| 检查 | 本次结果 |
|---|---|
| Python | `research/r12/.venv/Scripts/python.exe`，3.13.12 |
| 固定 STREAM | commit `75748cc17e7c43add5a7d0d8f080841eb26531c4`；`git status --porcelain` 为空 |
| 实际 import | `stream.api` 来自本仓库 `research/r12/deps/stream/stream/api.py`；`TransferAndTensorAllocator` 成功导入 |
| 依赖版本 | stream-dse 1.14.1；ortools 9.15.6755；zigzag-dse 3.8.5；numpy 2.5.3；pydantic 2.11.10；xdsl 0.29.1 |
| GSCIP sentinel | 实际求解 `min x, 2x >= 5, x integer, 0 <= x <= 10`；`OPTIMAL`，`x=3`，objective=3，gap=0；这只证明 solver 可用 |
| 保存 IR | `AllocationIR.model_validate_json` 校验成功，schema 1.5，7 个 mapping nodes；SHA256 `78b52519d5a781620cecbf5dc4b1ec080f7d137d695f8afca5d1e7030f48ed32` |
| 保存 IR 的历史值 | total=12808、per_iteration=12808、overlap=0、最后目标=10、overlays=[]；这些是 R12 已保存输出，本次没有重新测量它们 |
| 当前资格 | `r13_p0_qualified=false`；导入和整数 sentinel 不证明目标资源、数值、事件和强基线已准入 |

### 已完成的 live-candidate 导出

实现：[export_tetra.py](export_tetra.py)。成功输出：[tetra_export.json](artifacts/tetra_export.json)，353057 bytes；消费接口：[JSON Schema](artifacts/tetra_export.schema.json)，Draft2020-12，schema ID `r13.tetra-live-candidate.v1`。Schema描述成功的候选接入记录，不是底层DES ModelPlan；ID只在同一导出运行内稳定，不声称跨进程保持同一编号。

实际使用原public generic API、原parser、原scheduler、原TETRA和原GSCIP。临时观察钩子仅在当前Python进程包装其输入/返回值，在`finally`恢复；每个原函数仍以原参数运行。未使用上游plugin overlay，固定源码执行前后均clean。此处“只读”指对上游算法及源码的观察；它仍运行优化管线并在R13写日志。

| 本次成功管线 | 实际结果 |
|---|---|
| 完整管线墙钟时间 | 12.4558453秒，含观察器开销，不是编译方法比较 |
| 导出范围 | 1个fusion group，1个live allocator，11个transfer-graph节点，10份tensor choice列表，5份path choice列表及选中项 |
| path候选数 | 总5个，均为上游此fixture真实产生；不是R13共同候选全集 |
| 第一级目标 | latency（含DMA项）=12814，bound=12814，OPTIMAL |
| 第二级目标 | offchip_traffic=2019328，bound相等，OPTIMAL |
| 第三级目标 | buffering=10，bound相等，OPTIMAL |
| 原分析总latency | 12808 cycles；与R12保存值一致，不是R13硬件模型时间 |
| 预算设置 | 保留上游默认；threads、random_seed、time_limit均None，完整SolveParameters已记录。没有把这次intake当预算公平的P0/P1比较 |
| 共享资源 | 5个path都引用同一个真实link对象ID；没有把字符串相同与对象相同混淆，也没有新增bus带宽 |

第一次尝试已完成TETRA三阶段求解，随后观察器将已求解`memory_allocation`中的bare `Core`误作可迭代集合，后置导出失败。保留 [attempt1](artifacts/tetra_export_attempt1.json) 和 [首次日志](logs/tetra_export/console_attempt1.log)。仅修正观察器对上游允许的该结构的处理后必要重跑，得到上述成功结果；不是改变优化器来追逐数值。[成功日志](logs/tetra_export/console.log) 与该次管线文件位于独立R13目录。

[独立导出检查](artifacts/tetra_export_checks.json) 校验了10个选中tensor placement属于真实候选、path候选引用与共享link身份、三阶段bound、exporter hash；另使用独立affine AST解释对18个operand/坐标组合核对源卷积公式。根据本次live最终mapping确认两层均按ox四等分，并在明确的同序连续所有权假设下重新枚举Conv2输入需求：8192/16384/16384/8192 remote bits，总49152 bits，仍得到384个payload服务cycles下界。该需求检查没有调用R12枚举实现；不证明原512-cycle传输协议，也不把完整复制2048界移入真实2conv。

JSON Schema已提供并解析为合法JSON；当前venv未安装通用`jsonschema`验证器，本次不冒称执行了完整Draft2020-12验证。导出器结构/候选断言及上述语义检查实际通过，具体检查状态均记录在JSON。完整目标P0仍为false：未补Wormhole坐标与双NoC各packet路由、多channel alias、source-slice物化和分离完成事件。

复现成功导出的命令（始终写入R13目录）：

```powershell
& research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/export_tetra.py
```

必要 smoke 可在项目根目录复现，使用 `-B` 不写入固定依赖的字节码；它不会重跑历史优化或写结果文件：

```powershell
@'
from pathlib import Path
import sys
source = (Path.cwd() / 'research/r12/deps/stream').resolve()
sys.path.insert(0, str(source))
import stream.api as api
from stream.opt.allocation.constraint_optimization.transfer_and_tensor_allocation import TransferAndTensorAllocator
from stream.opt.solver import create_solver, SolverBackend, SolverVarType
from stream.ir.allocation import AllocationIR
assert Path(api.__file__).resolve().is_relative_to(source)
s = create_solver(SolverBackend.ORTOOLS_GSCIP, 'r13_intake_only')
x = s.add_var(vtype=SolverVarType.INTEGER, lb=0, ub=10, name='x')
s.add_constr(2*x._raw >= 5, name='bound')
s.set_objective(x._raw, sense='minimize')
s.optimize()
assert x.X == 3 and s.solve_stats().status == 'OPTIMAL'
p = Path('research/r12/results/baseline_smoke/allocation_ir.json')
a = AllocationIR.model_validate_json(p.read_text(encoding='utf-8'))
print(api.__file__, TransferAndTensorAllocator.__name__)
print(s.solve_stats(), x.X, a.schema_version, len(a.mapping_nodes))
'@ | & research/r12/.venv/Scripts/python.exe -X utf8 -B -
```

## 2. 真实调用接口与应捕获的位置

以下行号均指上述固定提交，不以 latest 文档替代源码。live观察导出已实现；目标资源、窗口与F适配仍待实现。

| 层次 | 确切接口与来源 | R13 使用方式与限制 |
|---|---|---|
| 官方 generic 入口 | `stream.api.optimize_allocation_co_generic(hardware, workload, experiment_id, output_path, ..., backend='ortools_gscip', constraint_selection, intra_core_tiling, fusion_cut_points, instrumentation, hardware_budget)`；[api.py:304–351](../r12/deps/stream/stream/api.py) | ONNX 源算子输入；把所有新输出写到 R13。官方返回 `StageContext`，总 latency 只是原分析指标。 |
| 内存中源图入口 | `optimize_allocation_co_generic_workload(hardware, workload: Workload, ...)`；同文件354–393 | 可复用源 affine IR，避免没有 ONNX round-trip 的算子丢失；需显式表示 R13 数值 cast 等语义，不把缺失算子吞掉。 |
| 显式 mapping 入口 | `optimize_allocation_co_with_mapping(hardware, workload, mapping, ..., enable_codegen=False, backend=..., constraint_selection=...)`；同文件65–190 | 使用真实手写/生成 mapping 候选并保持 AIE codegen 关闭。`npu='npu2'` 默认值不是 Wormhole 模型身份。 |
| allocation stage | `ConstraintOptimizationAllocationStage.find_best_tensor_transfer_allocation()`；[allocation stage:67–88](../r12/deps/stream/stream/stages/allocation/constraint_optimization_allocation.py) | 构造真实 scheduler 并执行 `run()`，stage 把 `workload/mapping/scheduler` 放入 context。 |
| 排程与分配交接 | `SteadyStateScheduler.run()`；[scheduler:282–381](../r12/deps/stream/stream/cost_model/steady_state_scheduler.py) | 在 transfer graph、mapping、cost LUT、SSIS 建好后，调用资源感知 `get_timeslots`，创建真实 TETRA。最有用的导出点在 `tta.solve()` 返回之后、局部 `tta` 消失之前。 |
| TETRA 直接接口 | `TransferAndTensorAllocator(workload, timeslots, accelerator, iterations, ssis, multiplicities, mapping, cost_lut, *, context, backend, constraint_selection, ...)`；[allocator:104–218](../r12/deps/stream/stream/opt/allocation/constraint_optimization/transfer_and_tensor_allocation.py) | 适配后的实体/候选必须满足这些真实类型；不需要重写 MILP。`timeslots` 已在构造时固定。 |
| 真实返回值 | `tta.solve()` 返回 `(tensor_reuse_levels, tensor_depths, tensor_allocations, transfer_allocations, memory_allocations, total_latency, overlap, latency_per_iteration)`；同文件2030–2073 | 前五项是决策，后三项是其原分析模型数值。不得直接把后者填入 F 的事件时间。 |
| 求解阶段统计 | `ORToolsBackend._optimize_lexicographic`；[solver:1056–1076](../r12/deps/stream/stream/opt/solver/solver.py) | 三个 objective 分阶段调用 `mathopt.solve`，最终 `_result` 覆盖前阶段。捕获每次调用的 termination、primal/dual bound、objective、参数与时间，不能只用最后 `solve_stats()`。 |

现有 `stream.instrumentation` 是 out-of-tree stage observer 入口；见 [instrumentation.py:19–64](../r12/deps/stream/stream/instrumentation.py)。它适合观察各 stage 的 context，但默认接口不会让已经退出 `run()` 的局部 `tta` 重新可见。需要一个显式、受限的 allocator 观察钩子或受审查的派生 scheduler；不能假定只给 `instrumentation={...}` 就已捕获内层候选及每阶段 solver 信息。该入口遇到缺失插件会 warning 后继续，因此 R13 wrapper 必须另外要求导出完整，否则判 intake 失败。

### 建议的导出接口

当前导出已落实下面`capture_allocation`所需信息（脚本实现名为`Capture`）；其余lower/refine仍为待实现接口。候选记录与唯一模型schema之间需显式编译，不创建第二套执行器：

```python
capture_allocation(
    original_workload,   # 节点身份、operand affine maps、dimension namespace
    scheduler,          # transformed workload、mapping、SSIS、iteration multiplicity
    allocator,          # fixed slots、全部 choices、选中 choices、reuse/depth
    solve_phase_records,
) -> CandidateRecord

lower_demand(candidate, frozen_source_demand, frozen_resources) -> ModelPlan
refine_windows(plan, common_action_space, evaluator_F, common_budget) -> SearchResult
```

`CandidateRecord` 至少需保存：输入与固定源码 hash；原图到 tiled/transfer 图的节点对应；每个计算节点的有序 core tuple、inter/intra-core 分块；张量 subview 与 operand affine map 的原文及维度对照；每个 transfer 的候选及选定 source/target、有身份的共享 link 集合；SSIS、firing/reuse stop/depth；slot/order；所有阶段 solver 记录。选择未知或丢失必须报错，不采用隐式 scalar latency 或整 tensor 复制 fallback。

Wormhole 路由在上游 `MulticastPathPlan` 之外还需登记 `noc_id`、有序有向路径以及 request/response/ACK/notification 的独立 packet 类。`links_used` 本身只是资源集合，不是完整 packet 路径树。应通过合法路径候选的显式 ID 关联到共同模型，而不是从 `str(link)` 或 scalar hops 反推 NoC。

## 3. 哪些能力可复用，哪些须适配

| 能力 | 原实现可保留的部分 | R13 必须补足的部分 |
|---|---|---|
| 源图、分块、fusion | 真实 STREAM workload、mapping 与融合阶段；保留源维度和有序核心索引 | 由消费者访问关系推导真正搬运集合；显式 BF16/FP32/cast、归约树和 padding。各计算位置/tiling/fusion 的外层候选须独立列出与计预算。 |
| TETRA 选择 | `x_tensor_choice`、`y_path_choice`、coherence、容量、reuse stop 和 buffering MILP | 路径和放置 choices 应来自相同 R13 合法集合；外存 endpoint 不能误当独立 controller 带宽。 |
| 资源感知 slots | `Workload.get_timeslots(mapping)` 按拓扑优先级安放，slot 内对同类 core/link 候选做联合回溯；[workload.py:902–997](../r12/deps/stream/stream/workload/workload.py) | 原次序可作为真实 seed，但不能把它当所有合法 R13 时间次序的边界。P0 的共同 window/order refinement 必须能采用合法提前释放、预取和不同资源重叠。 |
| 共享路径排斥 | `_link_contention_constraints` 对同 slot / 同 `CommunicationLink` 的使用量设约束；allocator950–960 | 此处只表示 whole-transfer slot 资源使用，没有渐进 flit/credit 等待。共享 link 对象保持身份；两个 NoC 不能合成一个资源。 |
| 驻留与双缓冲 | `force_double_buffering`、`z_stop`、`tiles_needed_levels`、容量约束 | 既有聚合 tile 数不是地址复用证明；在 F 中映射为具体 slot/span，付出源读/目标写/通知/消费者读取时间，source slot 与 receive slot 分开。 |
| AIE FIFO/BD/DMA | 同领域资源建模方式及真实既有 wait scope 可以作为已有能力证据 | AIE2 限额和共享 memory-column 规则不是 R13 NIU 事实，需目标 namespace / context 合同。开了 constraint toggle 但未注册目标规则不算通过。 |
| 发送与完成 | 上游 AIE lowering 有 descriptor 回收/输出到达等待；不是完全缺少 wait 优化 | TETRA 中没有原生一般 release window 或 `source_last_read` / `target_visible` / `notification_observed` 时间变量。R13 后端提供合法事件约束，并让 P0 与 P1 同样使用。 |
| 成本与选择 | 保留上游目标作为一个带来源的候选生成器及诊断指标 | 完整模型 F 是所有方法的最终 evaluator。不能以单传输近似时长替代拥塞状态，不能把成本 oracle 偏差说成原方法没能力表达放置。 |

两个特别容易误读的源码事实：

1. **计算 placement 并非当前内层 TETRA 的任意联合变量。** `SteadyStateScheduler.determine_possible_memory_allocations` 在合并目的 core 时断言各计算节点只有一个 resource allocation，scheduler958–966 的外部 input/output 也固定返回单个 offchip core；allocator1196–1207 对 computation slot 使用 cost LUT 中最大 latency，而不是一般的 placement-conditional computation time。合理接入是保留真实 STREAM 外层候选展开，再对给定计算/分块候选调用原 TETRA；不得宣称内层一次 solve 已搜遍全部 compute mapping。
2. **原 scalar 分析目标不是 F。** allocator1520–1563 的第一级是 `total_lat + max_core_dma_in + max_core_dma_out`（启用 DMA 时），随后最小 offchip traffic 和 buffering。只把它输出的一个 incumbent 重放于 F，并称“同模型最强 P0”，会混淆成本模型误差和搜索能力。必须补共同候选/F 选择及 window refinement；若后来用 F 成本替换或扩展了 MILP，应明确叫“适配的 TETRA”，列出改动和原算法保留项，不叫原封不动官方算法。

## 4. IR 能证明和不能证明的内容

本次直接检查 [保存的 allocation IR](../r12/results/baseline_smoke/allocation_ir.json) 及 [Mapping.get_ir:174–244](../r12/deps/stream/stream/mapping/mapping.py)。JSON 保留 core IDs、inter-core split、memory allocation、fusion、runtime args 和摘要统计。路径序列化只保存 `sources`、`targets`、`hops`，丢失 `links_used` 的实体身份；也未保存完成事件、地址 span、packet 类或每个消费者的访问集合。

[R12 baseline_smoke.py](../r12/baseline_smoke.py) 已从真实 scheduler 导出 `links_used` 的字符串，足以定位当时 shared bus，但不是可无损回放的 R13 路由表示。其 `tensor_bits` 是 footprint；不等于必传 bytes。

真实 2conv 的纠错必须保留：Conv1 的 z6 与 Conv2 的 z13 都是局部维度 D1/ox，不是 output channel。按两算子同序连续四等分所有权，远端 halo 分别为8192/16384/16384/8192 bits，总49152 bits，在128 bit/cycle shared bus 下是384个 payload 服务 cycles。该所有权见证不证明任何真实512-cycle协议；也不能把 full payload 的2048界套回该计算。读取依据是 [shared_resource_affine_audit.json](../r12/artifacts/shared_resource_affine_audit.json) 的保存 operand maps、最终维度对照与需求枚举，本次未复跑枚举。

因此 R13 对该回归应比较源访问集合、所有权与实际 packet payload，而不能仅断言 `upstream_path_cycles >= tensor_bits / bus_bandwidth`。另行的完整复制合同可测试后一守恒命题，两种测试拥有不同输入合同。

## 5. 保持 P0 强度的最小实施顺序

1. **来源与需求接通。** 先做只读 live capture，在真实 STREAM 流程中产出上节字段；独立 checker 复核维度、所有权和 exact 消费集合。保存导出失败必须使目标准入失败。
2. **显式硬件适配。** 统一 core↔物理坐标、DRAM tensor stripe↔channel↔endpoint alias、合法 NoC 路径候选。通用 shortest-simple-path 不可直接成为任意可编程 Wormhole 路径；单 offchip 默认身份需要有审查记录的后端适配，不能通过增加虚拟 memory core 偷增容量或带宽。
3. **分开保存原算法与增强。** 原 TETRA 产出的决策/分析目标记为 `upstream_seed`；相同后端合法化及 F window/order refinement 记为 `tetra_port_refined`。补充通信感知 placement、预取/双缓冲/最小合法等待、SoMa 风格生命周期/搬运次序搜索。最后选整个 P0 portfolio 中 F makespan 最小的合法计划。
4. **对微图显式登记候选全集。** 与 P1 同样开放 placement、channel、合法双 NoC、有限事件锚定窗口/资源次序和源提前释放。不能只让 P0 在 TETRA 默认截断路径表中选，而给 P1 完整集合。若 exact oracle 已枚举同全集，它是该集合的上界/最优参照，不是“新算法”本身；若强 P0 也得到它，接受 H0。
5. **冻结预算并逐层归因。** 记录每阶段 solve status/bound/gap、线程/seed、编译 wall time、F evaluator calls 和共享缓存策略。成本近似选错造成 Hmodel，不自动成为 Hcompiler。观察到拥塞慢只可更新排序/下界，不能将仍合法的候选作为不可行项剪掉。

第1步的live观测导出已实现并执行，不要求板卡或更换依赖。目标硬件、source-slice与事件合法化仍须显式完成；当前导出故意保留`noc_id=null`、`ordered_packet_path_available=false`和`r13_p0_qualified=false`，不将toy候选改名为可执行R13 plan。独立小图F验证可与该后端接入并行，但不能据此提前宣布完整P0准入或Hcompiler收益。

## 6. 已实际运行 R13 micro 源图的真实 TETRA 候选

脚本：[port_micro_tetra.py](port_micro_tetra.py)。输入：[inputs_micro/p0000](inputs_micro/p0000/)，对应`small_plan_space()`的p0000；结果：[tetra_micro_p0000.json](artifacts/tetra_micro_p0000.json)，[独立输入/分配检查](artifacts/tetra_micro_p0000_checks.json)。这是新的R13 unary小图输入，不是把2conv输出改名。

### 能表达且已执行的部分

固定STREAM的`ComputationNode`可接收具名unary算子及identity affine operand maps。此次以`R13TimesTwo`和`R13PlusThree`明确记录源运算语义；每个tensor为`i32[64,4]`、1024bytes，每16B块的4个lane取同一整数，各块/代/链不同，与micro_graph的块身份和`2*x+3`关系一致。该接口表达的是已知源DFG和分配问题，TETRA不负责执行算术；没有把其求解成功升级为数值执行证明。

四个计算位置为当前R13注册坐标。两条链分别展开两代，含8个真实计算节点、4个InEdge、4个OutEdge；原scheduler自动生成12个transfer，得到28节点的真实分配图。显式`Mapping`固定每个计算节点的单一位置；原TETRA仍执行其tensor/path/reuse选择与三阶段目标。

使用上游已支持的`CoreCostLUT/CoreCostEntry`，显式提供注册的`32/eta_c=64`个算术服务cycles；没有运行未知算子的scalar fallback，也没有把这个数值命名为Tensix kernel测量。局部读写、通知、发包、生命周期与争用将在F中统一计费，本次TETRA whole-transfer候选分析没有这些细节。

实际调用链为：原`AcceleratorParserStage`解析本地输入 → 原`Workload/Mapping/CoreCostLUT` → 原`SteadyStateScheduler.run()` → 原`TransferAndTensorAllocator.solve()` → 原GSCIP，继续用已实现的进程内只读Capture观察。首次输入驱动误向非leaf parser stage传空后继列表，在进入求解前被原Stage构造器拒绝；[attempt1](artifacts/tetra_micro_p0000_attempt1.json)保留，改为合法`LeafStage`后运行成功。该错误不是算法不支持micrograph的证据。

| 本次原TETRA结果 | 数值/状态 |
|---|---|
| 正式scheduler运行墙钟 | 14.583052秒，含导出和可视化开销 |
| 一级latency+DMA目标 | 688，bound=688，OPTIMAL |
| 二级offchip_traffic目标 | 196608，bound相等，OPTIMAL |
| 三级buffering目标 | 24，bound相等，OPTIMAL |
| 原聚合分析latency | 684 cycles；只属于下述candidate projection，不作为F性能指标 |
| 真实导出 | 24份tensor choices、12份path choices、选中分配、SSIS/reuse/depth、原slots及所有求解阶段 |

独立检查实际验证了8个源unary节点、16个identity operand maps、每tensor8192bits、最终compute坐标与p0000一致，以及全部源边在原slots中的拓扑顺序。故“原TETRA不能表达这个unary小图”的说法不成立；真正缺的是目标硬件及执行语义的后端连接。

### 首次micro接入的具体缺口与后续修正

原默认`_retrieve_core_allocation`对本次8个InEdge/OutEdge实际全部返回`[[4]]`，其坐标为`[0,0]`。R13 p0000要求输入经group0的`[0,0]/[0,1]`端点、输出经group1的`[0,5]`端点；把输出同样放到core4并不能满足该合同。此次输入有意标为**single-offchip candidate projection**，用192bit/cycle共享bus生成粗候选，所有tile的payload容量按R13注册值扣除64KiB保留区。这个bus不是NoC、不是12channel模型，也不为R13增加资源；它的分析latency不准进入收益分母。

首次运行确认需要以下四个有界适配点；前3项中的IO/容量身份与合法payload路径已在本节后续运行完成，F协议成本和窗口评价仍未完成：

1. 给`scheduler`和`allocator`两处默认InEdge/OutEdge解析共同提供显式`node -> physical memory core choices`，把目标tensor stripe/channel/endpoint关联到该选择；不能只在YAML画多个memory节点。
2. 通过`MulticastPathPlan`候选与额外packet-plan ID接入实际双NoC合法路径；所有共享link沿用物理身份，request/response/ACK/notification分别进入F。当前bus路径不能直接重标为NoC0。
3. 物理channel的服务身份必须独立于endpoint身份；将默认单offchip surrogate保留作粗模型诊断，不能用其约束替代F中的共享controller合同。
4. 将真实已选计算/张量分配和upstream slots作为seed，依共同source-slice和地址分配合同进入F，并给P0与P1同空间的source-release/window/order refinement。两代source slot、receive slot及token依赖由该合法化步骤显式恢复，不把原DFG中的独立tensor当新增物理缓冲。

此处未修改上游、未另写求解启发式冒充TETRA。首次运行取得真实micro候选，仍未取得通过完整目标合同的micro P0。原projection与失败尝试全部保留；其实际生产脚本原字节另存在 [producer_source.py](inputs_micro/p0000/producer_source.py)，可核对原结果的producer hash。不能把684与DES makespan直接相除，不能因IO投影不准就直接宣布Hcompiler收益。

### 已完成：显式physical IO与真实有向路径接入

同一脚本新增具名`--target`输入适配，结果在 [tetra_micro_p0000_target.json](artifacts/tetra_micro_p0000_target.json)，日志与输入说明在 [inputs_micro/p0000_target](inputs_micro/p0000_target/)。成功运行13.7268645秒；三阶段632/196608/24全部OPTIMAL且bound相等；原whole-transfer分析latency626，仍不是F结果。

实现范围明确如下：

- `R13Scheduler`与`R13Allocator`仅覆盖InEdge/OutEdge身份解析、最终output tensor目的放置，以及已固定外层NoC的合法路径候选。通过进程内临时注入让原scheduler构造该allocator子类，`finally`恢复；原scheduler.run、TETRA约束、三个目标与GSCIP solve均继承执行，没有复制优化核心。
- 每个physical DRAM channel只有一个上游`Core`，共12个，每个容量1GiB；alias不是额外capacity Core。compute保持4个当前注册位置和扣除64KiB后的L1容量。`CapacityBackend`只实现Core已经支持的capacity/bandwidth接口，不估计MAC性能或创建第二个执行器。
- DRAM端点属于transfer路由，不属于容量身份：p0000两个input endpoint为`[0,0]/[0,1]`，共同映射group0/channel0/Core4；output endpoint为`[0,5]`、group1/channel0/Core6。实际8个In/Out resolver调用分别返回正确Core，单offchip默认值不再控制IO。
- 两个完整10×12 torus的480条有向router link全部注册；每次payload路由列出有序router/NIU link。共享link复用同一资源对象，NoC0与NoC1使用不同物理名称。局部NoC读写接口和physical channel使用独立、具名服务对象；每channel nominal144bit/cycle、每NoC L1接口192bit/cycle只是注册效率下的原TETRA候选成本输入。
- 12个payload transfer已逐项与共同`micro_graph`比较：src/dst endpoint、NoC、1024bytes、ordered payload links，以及1536个源/目的16B block引用全部一致。整个路径输入中没有surrogate bus。request/response与ACK反向合法路径另保留在记录，完整控制分包/时序/通知费用仍由F实现，不能从whole-transfer成本推断。

机器消费接口为：`physical_payloads[]`的`transaction`（如`c0e0/load`）、`path_id`、`src/dst/noc`、`source_channel/destination_channel`、`source_blocks/target_blocks`和`ordered_payload_links`，连接`groups[0].allocators[0].selected`中的真实path/placement/reuse选择。`physical_resources[]`按物理名称和对象ID给出共享资源，Core坐标对DRAM只代表channel的canonical endpoint；执行必须使用每transfer的`src/dst`端点，不能退回用canonical坐标。

当前是**真实TETRA + 显式目标输入适配的候选生成器**。`r13_p0_qualified=false`保持不变：两代物理source/receive slot、完成/可见性、通知和token依赖尚待共同F lowering，尚未完成同空间window refinement与P0 portfolio。626不是模型性能改善、不能与此前surrogate684或F makespan混比。所有源码执行前后clean。

复现：

```powershell
& research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/port_micro_tetra.py --plan-index 0 --target
```

## 7. 已执行：真实TETRA候选到共同F的限定seed准入

实现：[lower_tetra.py](lower_tetra.py)。本次实际执行回执：[tetra_lower_receipt.json](artifacts/tetra_lower_receipt.json)。输入是上述真实`tetra_micro_p0000_target.json`，不是只读p0000字段后重新安排一个无来源计划。

lower逐项读取并检查真实selected的24份tensor placement/depth、12个selected path及payload ledger、8个compute位置和原28节点slot表。每个逻辑tensor都映射到实际16B块列表；只支持本次求解选中的depth1，其他depth明确拒绝。源输入视图与producer输出视图可在同一已注册source span就地更新，两代也重用该span，均依赖实际last-read与跨代保护；没有为TETRA增加额外物理buffer。必须区分这种地址lowering选择与上游只输出逻辑张量分配的接口。

采用两种事先明示的时序解释并实际执行：

| 解释 | 保留的原计划内容 | 本次判决 |
|---|---|---|
| `whole_slot` | 每个较后slot的任务发行/开始读取，等待所有较前slot的whole-transfer observed或compute published事件 | 拒绝。原c1e1/load在slot6，c1e0/peer在slot7；已注册源地址复用又要求前者等后者source-last-read，形成依赖环。主执行器实际返回deadlock，独立trace审计因不完整而失败；不给这个非法lower性能分母。 |
| `resource_order` | 真实selected placement/path/depth；每core的原compute次序；每个共享原TETRA物理资源上的原transfer次序 | 限定seed准入。每个后续transfer的issue等待前一transfer在该共享资源上的最后实际服务完成，compute次序以published锚定。移除的只是无共享资源之间的全局slot屏障，明确不保留上游分析时刻。 |

`resource_order`实际生成并核对2127条顺序义务，覆盖全部20个可执行源节点。12项payload的src/dst/bytes/路径/块引用再核对一次；F统一生成并收费的新增步骤为command issue、read request/response、ACK、逐16B读写、notification观察、receiver token、source/receive/output复用，以及有限credit/bank/port等待。时间统一为36tick/model cycle，未把上游626cycles等值填为release或执行时长。

该seed在共同F实际完成：output-visible=128724ticks（3575.666667cycles），final ACK=133368ticks（3704.666667cycles），quiescent=133944ticks（3720.666667cycles）。独立`trace_audit`通过256个输出块、2576次独立内存块完成与4584个操作检查；`audit_builder_rules`通过完整40packet ledger、3048个link操作与有限pool/credit参数检查。所有顺序义务在实际trace中成立。这里报告的是一个限定合法seed的模型时间，不是相对于P0的收益，也不是芯片测量。

压缩的完整输入/轨迹保留为 [资源偏序spec](artifacts/tetra_lower_resource_order_spec.json.gz)、[资源偏序trace](artifacts/tetra_lower_resource_order_trace.json.gz)、[严格slot spec](artifacts/tetra_lower_whole_slot_spec.json.gz)、[严格slot trace](artifacts/tetra_lower_whole_slot_trace.json.gz)，每份约24–73KiB。回执记录压缩文件hash、纯JSON对象hash，以及实际builder/engine/auditor/hardware源码hash，不将后续模型更改默认升级为旧结果已经验证。

[负向接入检查](artifacts/tetra_lower_negative_checks.json)实际拒绝三种变化：篡改selected tensor core、把payload bytes改为512、把未支持的selected depth改为2。严格slot的拒绝说明**这一原slot表与当前地址复用lowering不能同时直接采用**，不说明原TETRA图、另一合法地址计划或真实硬件会死锁。

当前可标为`bounded_seed_admitted=true`的是具名的“TETRA来源、按资源次序做source-aware lowering”的一个seed。它保留原优化决策及可审计顺序，但不是原始global-slot计划的逐项时刻复刻。`p0_portfolio_qualified=false`仍保留；完成同576候选空间的窗口/联合邻域强化、其它P0组成方法与统一预算比较后，才能评价Hcompiler。不能以保守seed作为唯一分母。

复现：

```powershell
& research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/lower_tetra.py
```

## 8. 本次阅读覆盖

| 材料 | 范围 | 状态 |
|---|---|---|
| R13 proposal_contract.md | 全文，包括最新13点+16交互去重并集及控制倍率范围 | 本次阅读，唯一当前合同 |
| R12 baseline_source_audit.md | 全文，包括末尾真实2conv反证与历史门 | 本次阅读；未将旧native门移入R13 |
| R12 baseline_smoke.py、shared_resource_affine_audit.json | 全文 | 本次代码/保存结果核查；随后运行新的R13独立live-export，不覆盖R12 |
| STREAM api.py | generic、in-memory、with-mapping 入口和参数/转发段 | 本次定向源码检查 |
| allocation stage、instrumentation.py | 入口与观察机制 | 本次定向源码检查 |
| steady_state_scheduler.py | run282–381、transfer生成/分配与SSIS724–1090 | 本次定向源码检查 |
| transfer_and_tensor_allocation.py | 初始化/候选91–321、slot1196–1263、目标1520–1563、solve/导出2030–2160 | 本次定向源码检查；不声称全文读取3200行 |
| communication_manager.py | 1–160的path结构/候选常量及入口 | 本次定向源码检查；不是packet模型实现 |
| Workload.get_timeslots、Mapping.get_ir、AllocationIR | timeslots902–997、mapping174–244、IR字段及from_internal结构 | 本次定向源码检查；IR实际解析通过 |
| solver.py | ORTools optimize/lexicographic/stats985–1120 | 本次定向源码检查；另实际执行整数sentinel |
| 新export_tetra.py和新导出 | 实际运行，失败尝试保留；独立检查live数据 | 本次新执行的上游分析fixture/候选证据，仍非目标P0 |
| model_builder.py、hardware_model.json | 全文；当前micro_graph及小图候选 | 本次源DFG与模型合同对接检查 |
| 新port_micro_tetra.py、inputs_micro与导出 | 实际运行原TETRA，独立核对位置/affine/slots | 目标IO/NoC路径输入已接入；F限定seed见后续lower |
| 新lower_tetra.py与源selected/slot/ledger | 两种时序解释实际lower+simulate，独立trace/builder审计；3项负向接入拒绝 | 一个source-aware资源偏序seed通过；完整P0 portfolio未准入 |

未读取其他研究方案初稿、演示材料或解析副本；未修改 R1–R12 的冻结文件；不声称已经完成目标 P0、M1 或完整模块性能评估。
