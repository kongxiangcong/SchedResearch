# 开源实验基础设施使用说明

科学问题与当前判定统一见[科学问题线](../../docs/progress/scientific-questions.md)和[实验能力线](../../docs/progress/experimental-capabilities.md)。本页仅维护使用方法；历史两轮交接和选型审计见[归档索引](../../docs/archive/README.md)。

## 目录与职责

| 路径 | 用途 |
|---|---|
| `src/schedinfra/workload/` | 有来源的 Qwen3.5-4B MLP 工作量 |
| `src/schedinfra/plan/` | IR、生成器、合法性检查及三层准入 |
| `src/schedinfra/analysis/` | 冻结 CPU 参考与计划功能回放 |
| `src/schedinfra/backend/` | ONNXim 能力审计/拒绝执行入口；STREAM 分析型静态评估 |
| `src/schedinfra/runner.py`、`cli.py` | 运行组织、内容身份与命令行 |
| `configs/` | pinned_versions、具名硬件及工作量 |
| `experiments/`、`tests/` | 能力用例和测试 |
| `runs/<UTC时间戳>_<用途>/` | manifest、计划、检查、数值/分析结果及失败回执；禁止覆盖 |
| `scripts/`、`docs/` | 环境脚本与历史环境说明 |
| `vendor/`、`env/`、`patches/` | 本地第三方来源、环境及具名补丁边界；大型依赖不入库 |

输入合同取自 `research/r13/numerical_contract.json`，STREAM checkout/venv 位于 `research/r12/`。这些跨单元依赖保留固定路径，不能单独搬走本目录后直接运行。

## 环境与命令

PowerShell 从本目录执行：

```powershell
. ./scripts/env.ps1
python -B -m schedinfra.cli --help
python -B -m pytest tests -q -p no:cacheprovider
python -B -m schedinfra.cli inventory --m 32
python -B -m schedinfra.cli plan-check --m 32
python -B -m schedinfra.cli cpu-reference --m 1 32
python -B -m schedinfra.cli backend-audit
python -B -m schedinfra.cli plan-replay --style resident
python -B -m schedinfra.cli plan-replay --style naive
python -B -m schedinfra.cli stream-eval native-smoke
python -B -m schedinfra.cli stream-eval cast-diagnostic
python -B -m schedinfra.cli stream-eval qwen-mlp --hardware tpu_v7_ironwood
```

Git Bash 使用 `source scripts/env.sh`。env 脚本包含已有 Windows user-site 路径；新环境按 requirements 和固定依赖建立自己的解释器。STREAM 由 CLI 在 R12 环境中运行，避免混入另一版本的 Python 包。历史网络/环境诊断见 [01_environment](docs/01_environment.md)、[02_environment_blockers](docs/02_environment_blockers.md)，不可视为实时主机状态。

`native` 使用固定上游，`research` 记录具名扩展；`plan-check --mode native|research` 选择模式，身份写入 manifest。命令可能写入新 runs，输出目录拒绝覆盖。

## 如何读输出

- 计划的逻辑合法、后端可表达、物理下降是三层准入；逻辑 ADMITTED 不代表 runtime 成功。
- 功能回放是计划自身语义对照 oracle，无时序/带宽；完整 CPU reference 也不是执行后端数值验收。
- STREAM 输出为 `evaluation_kind=analytical_static`，Cast 等偏差以结果记录为准。
- ONNXim execute 尚未实现，BackendUnavailable 是明确失败，不应替换成伪造结果。

详细验证范围、具名结果路径与待完成条件仅在[实验能力线](../../docs/progress/experimental-capabilities.md)维护。历史报告中的未提交、环境可用性和测试数均属于对应时点。
