# SchedResearch

研究多核 NPU 中静态数据流规划、数据移动与编译器约束下的动态执行。全过程包含 R1–R13，以及随后不按 R 编号命名的开源实验基础设施工作。

研究进度只维护两份文档：

- [科学问题线](docs/progress/scientific-questions.md)：问题、假设、结论、证据边界、转向原因与下一判定条件。
- [实验能力线](docs/progress/experimental-capabilities.md)：源码、模型、计划/检查器、数值、静态评估及执行后端的演进和缺口。

截至 2026-09-14，schedinfra 已有计划检查、功能回放及 STREAM 分析型静态评估的历史验证记录；执行后端未实现。R13 有独立微图模型结果，完整强 P0 / Hcompiler / MLP 性能门尚未完成。工具接通不构成算法收益证据。

## 目录

| 路径 | 用途 |
|---|---|
| `docs/progress/` | 两份持续维护的研究进度 |
| `docs/archive/` | 阶段提示词、结构化交接、历史布局与原位归档索引 |
| `docs/reproduction.md` | 当前运行与复现约定 |
| `research/infra_open_source/src/schedinfra/` | 当前工作量、计划、检查器、回放、后端接口与 CLI |
| `research/infra_open_source/configs/` | 固定版本、硬件和工作量配置 |
| `research/infra_open_source/experiments/`、`tests/` | 能力用例与测试（均位于 infra_open_source 内） |
| `research/infra_open_source/runs/` | 不覆盖的具名运行证据，包含失败记录 |
| `research/infra_open_source/scripts/`、`docs/` | 局部环境入口与使用说明 |
| `research/sim/`、`research/experiments/`、`research/tests/` | 共用历史模型、实验入口/结果与测试 |
| `research/r1-base/`、`research/r2-ooo-npu/`、`research/r3/` … `research/r13/` | 按合同封装的历史复现单元 |
| `research/analysis/`、`research/literature/` | 独立分析、文献登记与来源 |
| `references/` | 外部阅读资料原始导出 |
| `research/research_progress.md` | 原位历史证据，旧检查器依赖，不再维护 |
| `SchedResearch_reassessment_evidence_20260907/` | 原位冻结输入包，R12/R13 按固定路径校验 |
| `run.py` | 历史 Python 模块统一根入口 |

源码、结果和合同保留在同一复现单元；不横向搬散冻结轮次的 artifacts/results/history/sources。阶段历史统一由[归档索引](docs/archive/README.md)管理。新目录和文件采用含义明确的小写名称；Python 包及历史冻结名称保留。vendor、deps、venv 等本地环境不随 Git 分发。

## 使用

从根运行 `python run.py --help` 查看历史入口。当前基础设施进入 `research/infra_open_source`，执行 `. ./scripts/env.ps1` 后运行 `python -B -m schedinfra.cli --help`。

完整命令、测试与避免覆盖结果的方法见[复现说明](docs/reproduction.md)和[infra 使用说明](research/infra_open_source/README.md)。新 clone 不包含全部大 trace、依赖或设备环境，紧凑回执不是完整重放。

本轮仅整理目录和文档，没有新增研究功能、复跑历史性能、自动提交或推送。[迁移、删除及验证记录](docs/reorganization-2026-09-14.md)。
