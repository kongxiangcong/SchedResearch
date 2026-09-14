# 实验能力线

更新：2026-09-14。科学问题与方向判定见[科学问题线](scientific-questions.md)。这是能力进度的唯一维护入口；局部 README 只说明如何使用，JSON 回执和阶段报告记录历史事实。

**当前能力：计划检查和功能回放可用；固定 STREAM 分析型静态评估有已存成功回执；新 infra 的执行后端未实现。** R13 自身有具名微图 DES，不能据此称 `schedinfra` 已有执行后端。本次未重跑下表中的历史数值、性能或求解器实验，历史 PASS 均按现存报告/回执记载。本次检查范围和结果见[整理记录](../reorganization-2026-09-14.md)。

## 能力如何演进

| 阶段 | 源码/合同与能力 | 历史验证依据 | 当前可用范围和缺口 |
|---|---|---|---|
| R1–R2 | 原始候选、toy，`r1-base/`、`r2-ooo-npu/` | [R1/R2 审计](../../research/analysis/r1_r2_audit.md)与 `analysis/evidence/` | 选题与局部反例；非完整执行模型。 |
| R3 | [sim](../../research/sim/README.md) 的 workload/compiler/memory/engine/NoC/scheduler/metrics；公共 `experiments/`、`tests/` | [报告](../../research/r3/experiment_report.md)，14 基础测试、3,920 合成执行、独立 trace 检查的历史记录 | 同刻完成批处理；资源整 task 原子占用，仍有 O(N+E) 状态；非 packet/RTL。 |
| R4 | 官方 Qwen/FLUX 来源缩尺、静态搜索、数值与因果对照；R3 快照 | [产物地图](../../research/r4/README.md)、数值/红队记录 | 真实来源缩尺图，未校准全模型性能。 |
| R5 | full-K/full-head 请求服务、bank/outstanding/credit/返回反压及驻留控制 | [报告](../../research/r5/experiment_report.md)，1,296 fine test 的历史 request 审计 | 全宽切片不是完整 GDN/完整 NoC；静态与收费策略可在固定合同中比较。 |
| R6–R7 | Phoenix host、固定 BO/input、copy/INT8 GEMM、ABI 与 profiler 审计 | [R6](../../research/r6/README.md)、[R7](../../research/r7/README.md)：4 copy + 4 GEMM 功能记录 | 主机 host elapsed，不是 compute-active/bytes/request 计量；通用 timestamp/trace 有桩，研究 kernel/受控背景未准入。旧环境可用性本轮未实机检查。 |
| R8 | 分片/bytes/数值许可账本、单 payload 可见性偏序 | [报告](../../research/r8/experiment_report.md)：18 数值比较、70 线性扩展 | 有条件安全证书；不是并发完整归约、物理 credit 或设备验证。 |
| R9–R10 | EXT→DMA→VMEM staged 参考服务、静态搜索、paired 外生背景、串联下界、收费动作 | [R9](../../research/r9/README.md)、[R10 报告](../../research/r10/experiment_report.md)；608 / 1,104 保存轨迹的历史独立检查 | 具名两 cluster 模型；理想 local 端口和有限搜索，不是 TARS 校准。R10 动作数为零。 |
| R11 | 完整 32-head GDN 单层数值、容量/生命周期、prefill 与 strict decode | [实现语义](../../research/r11/implementation_semantics.md)、[独立审计](../../research/r11/independent_audit.md)：76 + 4 数值、122 trace | cold-weight/staged ABI 参考模型，完整模块资格不代表驻留收益成立。 |
| 重审包、R12 | 固定公开 Wormhole 来源、Windows 独立依赖、STREAM/TETRA、tt-npe、完整 MLP 账本、路由/事件/affine 探针 | [R12 README](../../research/r12/README.md)、[资格摘要](../../research/r12/artifacts/qualification_summary.json)、[最终审计](../../research/r12/independent_research_audit.md) | 96 计划为流量账本；56 事件为条件功能。历史 NPE Release、45 C++/10 Python/API 成功；CLI 字段错误使整体 setup 非零。不是完整 DFG/原生执行。 |
| R13 | 事件 DES、独立 tick、有限队列/credit、逐 16B/epoch、真实 TETRA seed lowering | [报告](../../research/r13/experiment_report.md)、[冻结清单](../../research/r13/artifact_integrity.json) | 微图模型与数值已有资格；一般编译器、强 P0、完整 MLP 时序未完成。 |
| infra 首轮 | `workload`、plan IR、初版 checker、CPU reference、runner/CLI、ONNXim source audit | [首轮 JSON](../archive/infra/round-1.json)、[选型报告](../archive/infra/round-1-source-audit.md) | 16 测试是当时覆盖，后续发现覆写安全/整层屏障错误，不能沿用为当前完整安全证明；执行层 NOT_RUN。 |
| infra 第二轮 | 偏序覆写安全修复、结构拒绝、三层准入、fail-closed、计划功能回放、STREAM driver | [第二轮 JSON](../archive/infra/round-2.json)及下表源码/运行目录 | 历史 42 测试；PLAN_SAFE、STATIC_EVAL_READY 有限定证据；RUNTIME_READY 否。 |

以上硬件、数值与执行粒度有多次变更，不是同一个模拟器不断提高精度。依赖源码/环境归所在实验，冻结代码不抽取成“通用库”；共享可维护实现为 `sim` 和 `infra_open_source/src/schedinfra`。

## R13 实现与资格明细

| 能力 | 代码与已存回执 | 验证范围与未完成项 |
|---|---|---|
| 硬件来源/服务构造 | [hardware_model.json](../../research/r13/hardware_model.json)、[model_builder.py](../../research/r13/model_builder.py)、[machine_contract](../../research/r13/machine_contract.md) | 10×12 torus/双 NoC、6 组×2 channel、共享 bank 等具名模型；未公开仲裁/NIU/效率仍为假设，无厂商周期精度声明。 |
| DES 与独立 tick | [event_machine.py](../../research/r13/event_machine.py)、[independent_checker.py](../../research/r13/independent_checker.py)、[差分回执](../../research/r13/artifacts/checker_differential.json) | 17 基础测试、209 差分实例（115 完成/94 预期死锁）、8 错误规则被检出；验证声明模型，不证明任意输入活性。 |
| 构造与值/epoch | [trace_audit.py](../../research/r13/trace_audit.py)、[builder](../../research/r13/artifacts/checker_builder.json)、[trace qualification](../../research/r13/artifacts/trace_qualification.json) | 52 构造/算术检查不计为性能运行；4 完整图逐 16B、9 非法变异；有限集成 9 项。 |
| 完整 MLP 数值 | [numerical_reference.py](../../research/r13/numerical_reference.py)、[合同](../../research/r13/numerical_contract.json)、[回执](../../research/r13/artifacts/numerical_qualification.json) | H2560/I9216，M1/32/128，BF16 RNE、规定 FP32 归约及全部中间逐位对照；相对 FP64 L2 0.162382%/0.165065%/0.165844%，仅固定生成样本。未完成全 MLP 资源计划/六配置时序。 |
| 微图执行 | [run_micro.py](../../research/r13/run_micro.py)、[独立全表分析](../../research/r13/artifacts/micro_independent_analysis.json)、[最优 tick 复核](../../research/r13/artifacts/checker_optimum.json) | 576+168 执行，最优 6,120 操作独立回放是事后资格；原始大 JSON/trace 部分仅本地，不假称本轮复跑。 |
| TETRA / NPE 接缝 | [baseline intake](../../research/r13/baseline_intake.md)、[lowering](../../research/r13/lower_tetra.py)、[审查](../../research/r13/tetra_lower_independent_audit.md) | 一个保守 seed 合法；无完整共同 P0 组合/预算。NPE projection 有源码但 R13 跨工具执行未完成，R12 旧成功不能补签。 |

## 当前 schedinfra 源码与证据逐层核对

下列路径相对于 `research/infra_open_source/`；源码入口可从[局部 README](../../research/infra_open_source/README.md)查找。本次实际阅读实现与已存 JSON，而不是只复述交接状态。

| 层 | 已实现与依据 | 当前限制 |
|---|---|---|
| 工作量 | `workload/qwen_mlp.py` 读取 R13 数值合同；M32 的 3×32×2560×9216 = 2,264,924,160 MAC，BF16 三权重 141,557,760 B | 来源与代数正确不代表模型精度/时序后端数值正确。完整 FLUX 模块未在新 infra 准入。 |
| 计划 IR/生成 | `plan/schema.py`、`generators.py`；naive / resident 各 100 op；naive ID 修正为 `d3a4c6c861535e7f`，边 1170→1476；resident `738420509c6733af`、292 边 | 真整层屏障修复不能被旧首轮数据覆盖；5,308,416 B 是 resident 逻辑值尺寸和，不是节省的流量或任意交错峰值。 |
| 结构和覆写检查 | `plan/checker.py` 验证引用、唯一 producer、拓扑序、物理 (level/core/slot/byte range) 重叠；`dead_before` 要求全部旧读者为新写者传递前驱，含 EXTERNAL；不依赖 `reuse_of` 存在 | 覆写安全依据 deps 偏序；容量峰值仍仅对声明 static_order。PLAN_SAFE 不代表任意交错不溢出或真实硬件安全。 |
| 三层准入 | `plan/lowering.py`：logical semantics → source-audit backend expressibility → physical lowering | resident 有 134 个无 movement contract 的远程片上读，NOT_READY；naive 的 READY 只表示该准入层，不代表 ONNXim execute 已实现。 |
| runner/身份 | `runner.py` 非法计划不调用 backend；manifest v2 分别记录 workload/contract/hardware/backend/policy hash；新运行目录拒绝覆盖 | plan_id 不是整个实验身份。合法也不能越过未实现的后端。 |
| CPU reference | `analysis/cpu_reference.py` 直接加载冻结 R13 实现；[M1/32 回执](../../research/infra_open_source/runs/2026-09-13T18-05-51Z_cpu-reference/cpu_reference.json) | 两套归约逐位相同；NumPy 2.3.5 与合同 2.5.3 是显式偏差。infra 未复验 M128、未测主机峰值内存。 |
| 计划功能回放 | `analysis/plan_replay.py` 按 deps、chunk/slot 语义执行，与独立 FP64 oracle 对照；[resident](../../research/infra_open_source/runs/2026-09-13T17-52-35Z_plan-replay-resident/replay_result.json)、[naive](../../research/infra_open_source/runs/2026-09-13T17-52-36Z_plan-replay-naive/replay_result.json) | tiny fixture relative_l2 约 6.93e-5 ≤ 1e-4；覆盖源分片/cast/复用变异；无 cycles/带宽，不能外推完整维度计划回放。 |
| ONNXim | `backend/onnxim.py` 明确 `execution_adapter_implemented=False`，execute 无条件抛 BackendUnavailable；固定上游 `a1e86296e080fa1c82f8ad3f1b6de1079c192afc` | source_only：每 tile flush、core↔DRAM 路由、整层屏障、Cast 为 Dummy；无构建/原生测试/执行成功证据。环境改善不能消除语义阻断。 |
| STREAM | `backend/stream_static.py` 固定 R12 checkout `75748cc17e7c43add5a7d0d8f080841eb26531c4`，核对干净工作树，调用原生 generic API | 分析模型与 solver，不强制执行 schedinfra 计划；不用它签 B1–B3。 |

## STREAM 静态评估：成功、偏差和失败一起保留

| 已存运行 | 结果 | 解释 |
|---|---|---|
| [native smoke](../../research/infra_open_source/runs/2026-09-13T18-04-49Z_stream-native-smoke/result.json) | 2conv + tpu_like_quad_core：12,808 analytical cycles | 与 R12 同 commit 相同，与上游文档 14,344 不同；不是校准或追数后吻合。 |
| [Cast 诊断](../../research/infra_open_source/runs/2026-09-13T17-54-17Z_stream-cast-diagnostic/result.json) | 无 Cast parser | 诊断运行完成与特性缺失并存；Cast 能力 PARTIAL。 |
| [小硬件 MLP](../../research/infra_open_source/runs/2026-09-13T18-09-33Z_stream-qwen-mlp/result.json) | 不可行，33.84 MB vs 2 MiB/core | 不删除失败或说所有上游硬件已支持。 |
| [Ironwood 全融合](../../research/infra_open_source/runs/2026-09-13T18-15-06Z_stream-qwen-mlp/result.json) | 不可行，3.21 MB vs 2 MiB 的受限 core | 后续明确改用 per-layer 切分，不是全融合通过。 |
| [Ironwood per-layer MLP](../../research/infra_open_source/runs/2026-09-13T18-19-30Z_stream-qwen-mlp/result.json) | M32/H2560/I9216；occupancy 23,886、span 25,136，solver OPTIMAL/gap 0，structure_changed=false | 不称两个执行计划加速。零 initializer 仅服务 shape/bitwidth 分析，无实际 BF16 算术；Mul 直接 BF16 输出，cast 转换算术未收费。 |

每项 `evaluation_kind=analytical_static`。Ironwood 是上游示例，不能视为实测研究目标或 Wormhole 替身；OPTIMAL 仅限已建立的优化问题，不是全硬件/全算法最优。更早失败运行、日志、allocation IR、数值回执留在原 `runs/`，没有覆盖或重新归算。

## 环境、运行入口与复现边界

- 历史模块从根 `python run.py ...` 启动，工作目录和相对参数统一为 `research/`。R12/R13 的固定环境和直接 CLI 仍遵循各轮 README；本轮不重建 venv、不拉依赖、不跑会覆盖结果的脚本。
- infra 使用 `research/infra_open_source/scripts/env.ps1` 或 `env.sh` 和 `python -m schedinfra.cli`；源码在 `src/schedinfra/`，配置在 `configs/`，实验入口在 `experiments/`，测试在 `tests/`，证据在 `runs/`。
- 首轮主机 Python 3.14 / NumPy 2.3.5；STREAM 使用 R12 独立 Python 3.13.12 / stream-dse 1.14.1 / ortools 9.15.6755 / NumPy 2.5.3。不要把两环境混用；这些版本是历史记录，不是本轮依赖安装承诺。
- WSL 在 R12 曾可运行 NPE，R13/infra 记录访问拒绝；不把这两时点写成矛盾，也不声明当前系统策略已经重新检查。无 cmake/conan、PyPI 拦截为当时环境记录；实时 probe 与历史 source-only 审计分开。
- 新 clone 不含 `vendor/`、`deps/`、venv、WSL 磁盘及部分原始 trace。缺失本地大产物意味着完整回放证据不可得，不能以紧凑 PASS 标志替代重放。

详细命令与历史检查器的工作副本方式见[复现说明](../reproduction.md)。旧交接引用的 `SchedResearch_R13_research_review.md`、`SchedResearch_subagent_tasks.md`、`infra_review_4db062ed.md` 及随附反例不在本次可见已跟踪文件中；它们的内容不作本轮直接核验依据，保留提示词中的来源线索而不杜撰恢复。

## 未完成能力与准入条件

| 缺口 | 状态 | 下一判定条件 |
|---|---|---|
| B1 外部计划控制 | 计划层已实现，执行层未完成 | 两份共同工作量/硬件计划在实际后端保留映射/顺序选择，有可审计执行产物。 |
| B2 驻留/流水/生命周期 | 偏序检查与 tiny 功能回放有证据，执行层未完成 | 显式 movement、资源/容量/复用与完成合同，观测消费者按需启动及真实建模流量；禁止免费远程读。 |
| B3 策略替换 | 上游源码接口线索，执行验收 NOT_RUN | 同 backend/workload/硬件/数值，替换策略并固定 seed，记录实际动作、完整终点及代价。 |
| 完整数值与物理下降 | 完整 CPU 与 tiny replay 分别成立 | 完整计划自身回放、远程传输和后端数值许可匹配；保留 Cast/padding/归约费用。 |
| 分析合同完整性 | STREAM 路径已实现且有历史运行；Cast 未完成 | 有合法明确的转换建模/收费依据后，才提升合同符合性；不以 dtype 正确代替转换工作。 |
| R13 强 P0/MLP 性能 | 计划，未完成 | 共同能力、真实预算轨迹、完整资源图和门判决；不是当前 infra 启动前置条件。 |

未来每次只在本文更新能力的“计划/实现/验证依据/缺口”，并链接不可覆盖的具名运行目录；科学假设是否成立只在科学问题线判断。能力枚举 `capabilities.json` 为源码审计工件，不是第三份活动研究进度。
