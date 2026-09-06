# R6 真实测量记录与程序校验合同

日期：2026-09-05。继承 [R5 测量门](../r5/measurement_gate.md)。本轮交付是数据合同与校验程序，不包含硬件观测、性能估计或机制验收。`measurement_template.json` 无运行记录；`test_measurements.py` 只在临时目录构造带 `fixture=true` 的合成结构测试，不能作为设备数据。

## 资格与结论边界

`validate_measurements.py` 只用 Python 标准库，读取记录及其引用的实际文件，输出：

| 字段 | 含义 |
| --- | --- |
| `record_valid` | JSON 结构、身份引用、摘要及已提供值的一致性未触发拒绝项。不是实测真实性证明。 |
| `device_screening_eligible` | 非 fixture、声明并确认物理 NPU 执行、有已完成且数值通过的有效 elapsed 与可核验原始 artifact 的记录，可进入设备瓶颈筛查。只有 host elapsed 时包括软件成本。 |
| `mechanism_gate_eligible` | 已满足本文件程序化测量资格条件，可继续做独立因果/统计/合法性审计。该值不表示残差、5%收益或机制成立。 |
| `performance_gate_evaluated` | **始终为 false**。本程序不计算性能门，不生成性能数字。 |
| `errors` / `blockers` | 错误使记录无效；blocker 保留原记录但禁止机制资格。 |

`evidence.level` 只能为 `unavailable`、`device`、`rtl_config`、`cpu`、`functional_sdk`。后四类不能互相代用，只有 `device` 可进入设备门。公开 RTL 配置的机制检查仍属 `rtl_config`。软件自测打印 NPU 名称、SDK 成功返回、CPU 输出正确均不证明物理 NPU 执行；执行来源必须另经审计。程序无法认证人为声明或证明一个日志没有伪造。

```
python -X utf8 -B r6/validate_measurements.py r6/measurement_template.json
python -X utf8 -B r6/validate_measurements.py actual_record.json --require-mechanism
python -X utf8 -B r6/test_measurements.py
```

实际 Windows Python 路径与执行回执存于 `fixtures/measurement_test_results.json`。退出码 `0` 表示记录有效（可仍不具备机制资格），`1` 表示无效；传 `--require-mechanism` 时有效但不合格返回 `2`。相对 artifact 路径默认从记录所在目录解析；可指定 `--base-dir`。

## 冻结对象

顶层包含 `schema_version=r6.measurement.v1`、`purpose=screening|mechanism_gate`、`fixture`、`evidence`、`artifacts`、`instrumentation`、`contracts`、`preregistration`、`conditions`、`comparisons`、`strong_static`、`calibration`、`runs`。允许补充源日志字段；程序只对这里说明的字段提供检查保证。

`artifacts` 每项为 `id/path/sha256`。文件必须存在且 bytes 的 SHA256 相符；原始日志、二进制、输入、布局、软件清单、数值验收与微测回执分别留档。不得为了匹配摘要改写旧文件。实际文件摘要只证明当前对应关系，不构成独立时间戳或事前注册证明。

`contracts` 每项为 `id/sha256/data`。`sha256` 是以下精确规范的摘要：

```python
hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()
```

程序同时导出 `canonical_hash(data)` 供采集程序调用。`preregistration` 同样用 `sha256/data` 结构。实际运行前保存不可覆盖的合同和时间证据；事后重新算 hash 不等于事前冻结。

合同 `data` 至少包含：

| 字段 | 内容 |
| --- | --- |
| `semantic_workload_sha256` / `_artifact_id` | 不随 fusion/tiling 改变的数学工作量与输出规则；明确全模型、子图或切片边界。 |
| `binary_sha256` / `_artifact_id` | 实际执行的编译产物；无法导出/追踪二进制时该缺口禁止机制资格。 |
| `layout_sha256` / `_artifact_id` | tensor 地址、alignment、alias、驻留和 last-reader 计划。 |
| `input_sha256` / `_artifact_id`、`initial_state_sha256` / `_artifact_id` | 实际输入、权重、初态；无状态也应有明确的空状态描述 artifact。 |
| `software_sha256` / `_artifact_id` | 芯片/板卡修订、固件、driver/runtime/compiler 版本及约束清单。 |
| `frequency` | `configured_hz` 是具名时钟域到频率的映射；`actual_tolerance_pct` 必须冻结。应记录实际可控的 NPU/内存/互连/CPU 时钟。 |
| `implementation` | `dtype/kernels/shapes/compiler_options/ops/output_acceptance`。只填写设备实际支持且真实执行的 dtype/kernel。 |
| `memory` | `capacity_bytes/address_mapping/residency_scope/alias_last_reader/warm_cold_rule`。RF 的逐层、逐 token 生存区间必须明确。 |

合同语义与资源合法性仍须人工/工具独立审核。特别是四个预先准备 token、两个 head 的驻留实验，不能仅改 scope 文字就代表完整 autoregressive decode；应证明 producer 执行、token 依赖、跨层 RF 争用与 spill，并保存真实地址/编译器计划。

## 观测与缺失值

每项观测为 `{"value": ..., "instrument_id": "..."}`；未知为 `{"value": null, "unknown_reason": "接口缺失的具体原因"}`。**0 是实测的零，不是未知值。** 已知 value 携带 unknown_reason 会被拒绝。身份、环境或捕获质量尚未知时，可用 null 加同级 `unknown_reasons` 说明；程序对捕获质量未知会阻止机制资格。

每个 instrument 包含 `id/definition/unit/clock_domain/sampling_boundary/bit_width/wrap_handling/multiplex_handling/reset_rule`，以及 `clock_sync.method/max_error_ns`。同一时钟域也要明确说明；零误差必须有依据。计数定义需说明 elapsed 的终点为 interrupt、retirement 或 payload visible，request 的 credit 从 accepted 到何时释放，是否覆盖主机提交/等待。程序检查定义存在；实际语义、单位和采样开销通过微测审核。

每次 `run` 有 `id/status/contract_id/raw_artifact_id/numerical_pass/condition_id/session_id/split/phase_seed/captured_at`。`status` 为 completed/failed/timeout；失败不能删掉来筛选结果。`split` 为 pilot/train/validation/test。原始采集日志要保存每个提交、fence、可见时刻与输出验收结果；数值通过布尔值只是一项待审计声明。

`metrics` 必须列出五个观测键；不可用也要记录 null+原因：

| 键 | value 形式 / 程序检查 |
| --- | --- |
| `elapsed_device_ns` | 正数设备 elapsed；缺失可作 host 筛查，不能进入机制资格。 |
| `elapsed_host_ns` | 正数 host submit→fence；机制资格不要求设备未暴露的 host timer。 |
| `traffic` | `ports` 数组，每项 `id` 和 `read/write_requested/accepted/completed_bytes` 六个实际非负有效字节计数；要求 requested ≥ accepted ≥ completed。不同端口完成字节分别保留。 |
| `compute_active` | `engines` 数组，每项 `id/active_cycles/elapsed_cycles`，active ≤ 该 engine 的 elapsed。不可将多 engine 求和当 wall utilization。 |
| `request_observation` | `kind/boundary_definition/counters`；kind 为 request_trace、limit 或 latency_buckets，见下。 |

`limit` 需要 `configured_limit/observed_peak/at_limit_cycles`，peak 不得超过同域 limit。`latency_buckets` 需要严格递增的 `bucket_upper_bounds_ns`、多一个尾区间的 `bucket_counts`，以及 `counters.observed_requests` 等于 bucket 总数；尾区间是合法超量程延迟类别，**不是 trace 丢失**。`request_trace` 需要 `trace_artifact_id` 指向请求级原始 ID/accepted/first-beat/last-beat/visible 记录。仅 histogram 或 limit 不能证明完成反转或合法替代任务存在；该因果门在资格检查之后独立进行。

`capture_quality` 包含 `dropped_records/overflow_count/unhandled_wraps`，三项均须为已知整数 0 才能进入机制资格；丢失或溢出保留原 run 并单列重采，不补零。`actual_frequency_hz` 按合同域逐项采集，超出预定容差会阻止机制资格。`background_actual_bytes` 是实际背景有效流量，不能由 offered bytes 代替。环境 `temperature_c/power_mode/cpu_affinity/other_master_traffic` 应保存在 run 或原始日志中；不可观测项说明原因。当前程序不会推断未暴露的系统状态。

## 三类配对合同

`comparisons` 每项包含 `id/kind/baseline_contract_id/candidate_contract_id`。参与配对的 run 另外记录 `comparison_id/pair_id/arm/pair_order`，arm 为 baseline/candidate，order 为 0/1。每 pair 精确两次、同 session/split/phase_seed；每条件内既有 baseline 先也有 candidate 先。采集器应预先随机化顺序；程序只检查顺序确实变化，不以交替顺序冒充随机化证明。随机化 seed/顺序表保存在 preregistration 的 artifact。

| kind | 固定关系 |
| --- | --- |
| `fixed_binary_interference` | 完整合同一致；baseline 是隔离，candidate 是指定干扰条件；每端口完成 payload bytes 一致。 |
| `compiler_variant` | 允许 binary/layout/implementation/memory 改变；语义工作量、输入、初态、software、frequency 不变；同干扰条件。允许 traffic 改变，但应作为静态优化收益解释。 |
| `dynamic_recovery` | 完整合同一致且两 arm 都必须引用 `strong_static.selected_contract_id`；同条件，完成 payload bytes 一致。不能借更多 buffer、新 tiling 或少搬 bytes 冒充调度恢复。 |

每个 dynamic 非隔离 test 条件必须被选中静态合同的 fixed-binary test 对照覆盖；两者各自满足样本/新 session 门，不要求相同 session ID。intervention 包含 `policy_artifact_id/causal_instrument_ids/finite_state_bytes/control_latency_charged/extra_traffic_charged/frequency_effect_charged`。这些声明与文件引用须审计，不代表 RTL 或 PPA 通过。

`conditions` 以 `id/isolation/extreme` 冻结。非隔离条件还需 `master_id/program_sha256/input_sha256/read_write_ratio/address_range/working_set_bytes/offered_bytes/phase_rule`。paired arm 共用 condition 与 phase_seed，实际返回顺序允许因真实交互而不同；不得重放另一策略的延迟来制造公平。

## 事前停止门

空模板已经记录研究价值门，仍需在目标确认后冻结具体工作量、样本量、seed/顺序表与时间证据：

- 净 elapsed 改善至少 **5%**，95% paired CI 下界 **>0**；每个确认条件/独立 session 分别成立。设备残差还须有独立同 binary 证据，不能将全部干扰损失称为可恢复等待。
- 每条件每 session 至少 **30 个独立 paired blocks**，至少 **两个新 session**；每个比较至少 **两个非极端干扰条件**，dynamic 另含隔离回退对照。
- 隔离回退容忍度预设 **1%**，是 R6 的研究决策值，非芯片规格；如根据不计入确认的 pilot 修订，必须在新 test 前冻结。程序检查预设存在，不计算回退是否合格。
- train、validation、test seed 集不相交；跨 test session 用新 phase seed；同一比较/条件/session 内不得重复 seed 来虚增独立样本。
- 保留失败/超时和异常，不能跑到显著或按效果删样本。test 后改策略需标后验诊断并换新 test。

strong-static 声明 `selected_on=validation/test_used_for_selection=false`，保存 selection artifact 与搜索预算。九个维度 `fusion_residency/tiling/reuse/buffering/capacity/bank_layout/prefetch/resource_order/outstanding` 各有 `status=evaluated|unsupported/reason/artifact_id`。unsupported 不能只写无权限，而须有目标能力证据；未覆盖的可用优化会阻止人工 strong-static 接受。

calibration 包含 `empty_run/known_bytes_copy/single_compute/instrumentation_overhead`，每项 `verified/artifact_id`；还需 `overhead_charged=true`。保存原始开启/关闭仪表数据、开销和定义核对。程序检查声明和文件可核验；误差容忍度、校准是否正确及动态费用是否完整仍需独立审计。

达到本程序资格后仍可能 Reject：真实残差不足、静态已消除、仅未来信息可恢复、无合法替代任务、收费后净收益不足。只有全部科研门成立才探索机制；这份程序不能代替任何一项效果/因果/合法性证明。

## 拒绝测试范围

`fixtures/measurement_tests.log` 与 `fixtures/measurement_test_results.json` 是 **synthetic schema / fixture evidence**。覆盖当前文件与冻结合同摘要变更、缺失观测/无理由 null、0 冒充未知、混合同、compiler 语义变化、split 泄漏、重复 seed、样本不足/单 session、单极端点、未变化配对顺序、完成 payload 改变、过晚注册、频率漂移、trace overflow、非设备来源，以及选中静态/残差条件绑定。没有保存或声称任何 fake hardware measurement。
