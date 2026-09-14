# 运行与复现约定

当前目录见[根 README](../README.md)，研究状态见[科学问题线](progress/scientific-questions.md)和[实验能力线](progress/experimental-capabilities.md)。本次只迁移外围文档；Python 包、实验输入/输出、环境、`run.py` 和所有实验 CLI 保持原入口。

## 历史实验

```powershell
python run.py --help
python run.py -m unittest discover -s tests -v
```

启动器使用同一解释器、UTF-8、禁写字节码，设置 cwd/PYTHONPATH 为 `research/` 并传递退出码。相对参数按 `research/` 解析；不要从根直接 `python -m r4.run`。手动方式为先进入 `research/` 再执行历史命令。

生成器可能覆盖结果：不要在唯一冻结目录直接运行 numerical/run_experiments/finalize/record_progress/prepare_handoff。需要重放时，复制该轮与依赖到独立工作副本，保持相对关系、原 manifest 和输入，在副本生成新结果并另记身份；不覆盖原清单。

专用环境与 CLI 见 [R12](../research/r12/README.md)、[R13](../research/r13/README.md)。从根执行只读冻结检查：

```powershell
python -B -X utf8 research/r12/freeze_artifacts.py --check
python -B -X utf8 research/r13/freeze_artifacts.py --check
```

这些命令检查字节与清单一致，不执行原性能/数值实验。缺少 trace/依赖时不能宣称完整复现。

## 当前基础设施

```powershell
Set-Location research/infra_open_source
. ./scripts/env.ps1
python -B -m schedinfra.cli --help
python -B -m pytest tests -q -p no:cacheprovider

# 下列命令创建新的 runs/<timestamp>_<purpose>/ 证据
python -B -m schedinfra.cli plan-check --m 32
python -B -m schedinfra.cli plan-replay --style resident
python -B -m schedinfra.cli plan-replay --style naive
python -B -m schedinfra.cli cpu-reference --m 1 32
python -B -m schedinfra.cli stream-eval native-smoke
python -B -m schedinfra.cli stream-eval cast-diagnostic
python -B -m schedinfra.cli stream-eval qwen-mlp --hardware tpu_v7_ironwood
```

Git Bash 使用 `source scripts/env.sh`。脚本包含本机 user-site 配置；新环境按 requirements 安装并使用自己的解释器，不假定本机版本/网络状态恒定。STREAM 依赖 R12 固定 checkout/venv，CLI 为它隔离导入路径；不要把 Python 3.14 user-site 注入 Python 3.13 进程。

逻辑 ADMITTED 不代表执行成功：resident 缺远程移动合同，ONNXim execute 未实现。STREAM 是 analytical_static；功能回放无 cycles。能力结论由能力线维护。

## 历史路径与归档

旧 `rN/`、`sim/`、`analysis/`、`experiments/` 已在此前迁入 `research/`。本次文档[精确映射](archive/migration-map.json)记录旧→新路径；外部书签需转换，固定提交路径仍按原提交解释。

`research/research_progress.md` 已停止维护但必须保留：R8/R9 检查历史行，R10 检查 successor 前缀，R5–R7 部分校验要求当时进度 SHA。严格阶段检查在最新汇总上本来就可能不适用，不因整理重写代码或 hash。

执行严格阶段检查时，在独立工作副本使用对应 lineage 快照作为 `research_progress.md`，例如 R6 存于 `r7/history/r6_research_progress.md`、R7 存于 `r8/history/r7_research_progress.md`；具体以 manifest 映射为准。当前原位证据不替换，旧交接生成脚本不用于今日维护。

根重审包同样原位保留，使 R12/R13 冻结代码不变。归档提示词/JSON 的旧字面路径按[索引](archive/README.md)的原始基准和映射解析，最新命令以本文及对应 CLI 为准。

## 验证归属

本轮结果见[整理记录](reorganization-2026-09-14.md)。此前迁移重跑过的 R2/R4/R11 记录位于[历史复现文档](archive/layout/reproduction-before-2026-09-14.md)，其中“本次”不是 2026-09-14。本轮没有重跑历史性能或生成冻结证据。
