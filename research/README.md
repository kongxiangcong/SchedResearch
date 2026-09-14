# 研究工作区导航

项目进度统一见[科学问题线](../docs/progress/scientific-questions.md)和[实验能力线](../docs/progress/experimental-capabilities.md)。本页只介绍目录，不单独维护阶段状态。

| 目录 | 用途与入口 |
|---|---|
| [infra_open_source](infra_open_source/README.md) | 当前开源实验基础设施；源码、配置、用例、测试、运行证据各自分目录 |
| [sim](sim/README.md)、`experiments/`、`tests/` | 共用 R3 模型与历史实验，结果在 `experiments/results/` |
| `r1-base/`、`r2-ooo-npu/`、`r3/` … `r13/` | 原始候选、冻结源码/合同、阶段报告、审计及结果；完整目录是复现单元 |
| `analysis/` | 问题定义、独立分析、纠错、范围建议；重复活动回顾已并入两条进度线 |
| `literature/` | 文献登记、检索与原始来源；当时判断不代表本轮重新检索 |
| `research_progress.md` | **停止维护的历史进度原文**；R5–R10 检查器直接读取或校验历史行，因复现依赖保留原位。不能作为最新进度 |

旧 R3/R4 首页已归入[阶段归档](../docs/archive/README.md)。所有 history、continuation brief、successor progress、冻结 manifest 由同一归档索引登记，不再作为活动交接入口。

从仓库根运行历史命令使用 `python run.py ...`，相对路径按本目录解析。详见[复现说明](../docs/reproduction.md)。
