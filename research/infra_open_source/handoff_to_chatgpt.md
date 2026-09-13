# 本轮交接（第 2 轮）：检查器修复 + STREAM 静态评估接通

**分层判决：PLAN_SAFE = 是；STATIC_EVAL_READY = 是；RUNTIME_READY = 否。**

计划层的安全性已经从"声明顺序下的必要条件检查"升级为"对完整偏序可证明的覆写安全"；
STREAM 分析型静态评估在固定 commit 上真实跑通（原生 smoke + Qwen MLP 两种静态配置）；
**仍然没有任何执行后端跑过**——所有 cycles 数字都标注 `evaluation_kind=analytical_static`，
runner 对非法计划 fail-closed，ONNXim 适配器明确标记 NOT IMPLEMENTED，零伪造。

起点：第 1 轮 HEAD `4db062e`（判决 PARTIAL），旧交接已归档为
`handoff_2026-09-09_round1.json` / `handoff_2026-09-09_round1_to_chatgpt.md`。

---

## 1. P0：检查器复用安全修复（A1/A2）

**Bug（修复前）**：旧代码用 `any(reader in predecessors)` 判定 slot 覆写安全——
P 写 A、R1/R2 都读 A、Q 覆写 A 的 slot，只要 Q 等了 R1/R2 中**任意一个**就放行。

**修复后**：`check_overwrite_safety` 对同一 (level, core, slot) 上字节区间相交的 chunk
两两判定 `dead_before(old, new)`——旧值的**每一个** reader（含 EXTERNAL/初始驻留）
都必须是新写者的传递前驱；可达性只从 `deps` 推导，**绝不使用 static_order**。
安全性来源是实际的 (level/core/slot/字节区间) 重叠，`reuse_of` 注解只做一致性校验。

**反例前后对照**：

| 场景 | 修复前 | 修复后 |
|---|---|---|
| Q 只等 R1（漏 R2）就覆写 A | **错误接受** | 拒绝 |
| Q 等齐 R1+R2 后覆写 A | 接受 | 接受 |
| 无 `reuse_of` 注解的裸同 slot 覆写 | 不检查 | 同样按上述规则判定 |

**naive 生成器整层屏障修复**：silu/mul/cast 原来只依赖前一阶段的**增长前缀**，
现在 `silu.{j}` 依赖全部 gate、`mul.{j}` 依赖全部 silu+up、`cast.{j}` 依赖全部 mul
（真整层屏障，由 `test_naive_is_a_true_whole_layer_barrier` 验证）。
诚实后果：naive plan_id 从 `dbe43cc256081c5a` 变为 `d3a4c6c861535e7f`，依赖边 1170→1476。

**结构校验**（新增 `check_structure`，失败即停后续分析）：重复 id、core 越界、
chunk key 与 producer 一致性、level 合法性、size>0、offset≥0、producer/writes 双向唯一、
consumer 读源存在、EXTERNAL/初始驻留一致性。`deps` 引用缺失 op 时给出**结构化拒绝**
（`unknown_dependency`），不再 KeyError/RecursionError。
`resident_bytes_by_level` 更名 `resident_value_bytes_sum`，并注明：是逻辑值尺寸之和，
**不是**流量、**不是**节省的 DRAM 字节、**不是**峰值。

**顺序语义分层**（报告里显式区分）：
- 依赖与覆写安全：对**所有与 deps 一致的执行**成立（偏序完备）；
- 容量峰值：仅对**声明的 static_order** 成立，不是任意交错下的硬件峰值；
- `static_order` 本身会被校验必须是合法拓扑序。

## 2. P0：fail-closed runner 与身份（A3）

- 非法计划**绝不调用** `backend.execute`；间谍后端测试确认零调用；
  拒绝原因在 CLI 与 manifest `admission.illegal_plans` 中一致。
- ONNXim 适配器显式标记 `execution_adapter_implemented=False`，`execute()` 抛
  `BackendUnavailable` 并注明 NOT IMPLEMENTED；`probe_environment()` 是**实时**探测
  （binary/cmake/conan），与 2026-09-09 历史阻断分开记录；能力结论标注 `source_only`。
- 新运行目录拒绝覆盖。
- manifest v2 中 workload/contract/hardware/backend/policy 各自有独立内容身份（hash），
  plan_id 只是计划身份，不是整个实验的身份。

## 3. P0：表达力分层（A4）

三层准入：逻辑语义（checker）→ 后端可表达性（逐特性源码审计结论）→ 物理下降
（READY/NOT_READY）。
- `resident_pipelined` 有 **134 个远程片上读**（down.* 读其他核的 A16#k）且无 movement
  contract → `physical_lowering_status=NOT_READY`，理由写明"远程读永远不免费"。
- 核映射置换用例：`permute_plan_cores` 只改 core 字段，checker 仍通过。
- 数值许可：生成器附带 schema/shape-slice/layout/op 语义/dtype/容差元数据。
- **功能回放引擎**（`analysis/plan_replay.py`）：按 deps 拓扑序执行计划自己的 chunk
  读写、遵守物理 slot 覆写语义，对照独立 float64 oracle。tiny fixture 两种风格
  （resident 乒乓 slot / naive DRAM+整层屏障）都通过，relative_l2 ≈ 6.93e-05 ≤ 1e-4。
  变异捕捉：分片源改错、省略 cast、reuse 依赖断裂（checker）、提前覆写（slot 守卫）。
  **无 cycles、无带宽、无伪造时序。**

## 4. P1：STREAM 静态评估（真实进度）

环境：R12 固定 checkout `75748cc17e7c43add5a7d0d8f080841eb26531c4`（运行前后均干净），
R12 venv（Python 3.13.12，stream-dse 1.14.1 / ortools 9.15.6755 / numpy 2.5.3）。

| 运行 | 结果 | 证据目录 |
|---|---|---|
| 原生 smoke（上游 2conv + tpu_like_quad_core） | **PASS**，12808 cycles | `runs/2026-09-13T18-04-49Z_stream-native-smoke` |
| Cast 诊断 | **PARTIAL**：`No parser registered for ONNX op type 'Cast'` | `runs/2026-09-13T17-54-17Z_stream-cast-diagnostic` |
| Qwen MLP（H=2560/I=9216/M=32） | **PASS**（含声明偏差） | `runs/2026-09-13T18-19-30Z_stream-qwen-mlp` |

诚实记录：
- 原生 smoke 实测 12808 ≠ 上游文档 14344；该差异**继承自 R12**（R12 同 commit 实测也是
  12808），未修改上游去追数。
- 合同的显式 FP32→BF16 cast 无法建节点（PARTIL，不替代）；MLP 模型中 Mul 直接按 BF16
  输出，位宽/物化与合同一致，但 cast 的算术工作量（M×I 次转换）未计任何节点。
- 硬件选型过程有失败记录：tpu_like_quad_core 实测不可行（33.84 MB 驻留 vs 2 MiB/核），
  ironwood 全融合也不可行（3.21 MB vs 2 MiB，上游文档化）→ 最终用上游大芯片示例
  **tpu_v7_ironwood** + `fusion_cut_points=per-layer`。
- 同一命名硬件、同一 per-layer 切分下两种合法静态配置：pipelining=occupancy
  **23886 cycles** vs pipelining=span **25136 cycles**；两者均 OPTIMAL（gscip, gap 0），
  **选中的结构相同（structure_changed=false）**——如实报告，不声称任何加速。

全部标注 `evaluation_kind=analytical_static`，**永不**标注 RUNTIME_READY。

## 5. 测试与身份

- 测试：**16 → 42 passed**（`python -m pytest tests -q`，4.15s）。新增：P/R1/R2/Q 反例族
  （5）、结构校验族、runner fail-closed 族（5）、replay 族（8）。
- 关键身份：naive `d3a4c6c861535e7f`（修复后）/ resident `738420509c6733af`（不变）；
  合同 sha256 `0fb2c74f…`；STREAM commit `75748cc…`；ONNXim commit `a1e86296…`，
  patch_identity=null；qwen_mlp_m32.onnx sha256 `e707a11d…`。

## 6. 复现方法

```bash
cd research/infra_open_source
. ./scripts/env.ps1            # 或 source scripts/env.sh
python -m pytest tests -q                                # 42 passed
python -m schedinfra.cli plan-check --m 32               # 三层准入 + fail-closed
python -m schedinfra.cli plan-replay --style resident    # 功能回放 vs oracle
python -m schedinfra.cli stream-eval native-smoke        # STREAM 原生 smoke
python -m schedinfra.cli stream-eval cast-diagnostic     # Cast 缺失诊断
python -m schedinfra.cli stream-eval qwen-mlp --hardware tpu_v7_ironwood
python -m schedinfra.cli cpu-reference --m 1 32          # CPU 数值参考（不变）
```

## 7. 遗留缺口（下一轮唯一目标）

**RUNTIME 层**。B1/B2/B3 的验收条件（见归档的第 1 轮 handoff）仍未在执行层满足。
计划层与分析静态层已不再阻塞这个决定：请授权 (a) 有界最小 tile 级执行核心
（~1–2 kLOC，复用本轮已证明安全的计划 IR+checker），或 (b) 提供 Linux/WSL2 主机
重新准入 ONNXim（范围收窄到不要求跨算子驻留）。

其他遗留：容量峰值仍是声明顺序口径；STREAM 无法建模 cast；resident 计划需 movement
contract 才能 READY；CPU 参考 numpy 2.3.5 vs 合同钉 2.5.3（显式偏差）；
tpu_v7_ironwood 是上游示例硬件而非实测目标。
