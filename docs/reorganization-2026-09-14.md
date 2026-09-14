# 2026-09-14 目录与进度整理记录

本次只整理目录、引用和文档。没有新增算法/实验功能、修改实验源码、重跑历史性能/完整数值/求解器、制作网页、提交或推送。

## 新组织与维护入口

- `docs/progress/scientific-questions.md`：[科学问题线](progress/scientific-questions.md)，覆盖原始候选、R1–R13、重审与 R13 后两轮基础设施转向。
- `docs/progress/experimental-capabilities.md`：[实验能力线](progress/experimental-capabilities.md)，按源码、模型、计划/检查器、数值、静态评估和执行后端记能力及证据。
- `docs/archive/`：阶段提示词、JSON 交接、源码审计、旧首页/布局，及[原位冻结归档索引](archive/README.md)。
- `research/`：保持实验单元完整；当前 `infra_open_source` 内已有 src/configs/experiments/tests/runs/scripts/docs 的职责分隔，历史 sim/各轮及结果不拆散。
- `references/`：外部阅读导出。根 README 与 research/infra README 变为使用导航，不再各自维护研究状态。

新文件采用描述用途的小写名称；固定 Python 包名、轮次名与冻结输入名保留。没有为统一外观增加兼容目录、重复源码或第二套运行状态。

## 迁移与删除

**8 项原字节迁移，3 项整合后删除。** 每项旧路径、新路径/替代入口和 SHA-256 见 [migration-map.json](archive/migration-map.json)。新增 Git 属性保护归档原始字节，避免后续行尾转换改变迁移哈希。

| 操作 | 内容 |
|---|---|
| 迁移 2 份根提示词 | `docs/archive/prompts/infra-round-1.md`、`infra-round-2.md` |
| 迁移 2 份结构化交接及 1 份独立源码审计 | `docs/archive/infra/round-1.json`、`round-2.json`、`round-1-source-audit.md` |
| 迁移旧研究首页与 2 份布局/复现文档 | `docs/archive/stages/`、`docs/archive/layout/` |
| 删除重复活动回顾 | `research/analysis/r1_r10_research_retrospective.md`；原始候选/历史判定已整合，R13 前原文仍在冻结 history |
| 删除重复 Markdown 交接 2 份 | infra 的 `handoff_to_chatgpt.md`、`handoff_2026-09-09_round1_to_chatgpt.md`；能力细节进入能力线，两轮 JSON 保留 |

删除前已检查 Python 引用、handoff/history manifest 和复现路径。没有运行入口依赖被删除的三份文档；历史字面阅读记录通过映射表解析。当前 README/环境文档已改用新入口。归档原文的历史链接/命令保持字节原样，使用索引中的原始目录与迁移映射，不冒充最新可直接运行说明。

**原位保留的两类例外：** `research/research_progress.md` 是历史检查器读取的兼容于当时合同的证据文件，停止维护；根重审包是 R12/R13 冻结代码固定路径输入。各轮 history/continuation/successor/manifests 亦保留原位，经归档索引统一管理。这些重复承担证据与 lineage 作用，删除或修改会破坏复现，故没有按“重复文字”清除。

## 核验依据与证据边界

本次梳理了全部非第三方 Markdown 路径、顶层目录和未按 R 编号命名的文件；读取原进度/回顾、R12/R13 报告与合同、两轮 infra 提示词/交接/选型审计。核对当前 checker 的全部读者依赖判定、结构拒绝、容量口径、ONNXim execute 拒绝、STREAM driver、CPU reference 及工作区定位源码。

直接读取 R12 qualification、R13 micro independent analysis 与冻结清单、infra plan-check manifest、数值/功能回放和 STREAM 成功/失败结果。23,886/25,136、12,808 与 Cast/容量失败字段来自实际 JSON；不是本次执行所得。对更早轮次按历史报告、旧综合台账及具名结果入口整理，没有声称重放全部原始轨迹。

本次未恢复未提供的外部 review/subagent_tasks/随附反例文档，未重新检索文献或核验实时板卡/WSL/网络能力。代码可见、来源审计、已存运行记录和本次运行检查在两条进度线中分开。

## 本次验证

机器可读记录见 [verification-2026-09-14.json](archive/layout/verification-2026-09-14.json)。

| 检查 | 结果 |
|---|---|
| 整理前后字节保护 | 基线覆盖 1,644 个已跟踪/证据/用户文件；除具名文档编辑和 3 项删除外，无非预期修改或缺失；8 项迁移 SHA 相同 |
| 用户工作区 | 原有 `.workbuddy/` 的 4 个文件原字节保留；未暂存、覆盖或清理 |
| infra runs | 214 个现存运行文件原字节保留，包括失败日志/结果 |
| R12 原生冻结检查 | `freeze_artifacts.py --check`：52/52 通过 |
| R13 原生冻结检查 | **未通过**：68 项中仅 `.gitignore` 与 manifest 不符；整理前 SHA 与整理后 SHA 完全相同，属于原有不一致；其余 67 项匹配。未改清单或冻结文件 |
| 根运行入口 | help、cwd=`research/`、禁写字节码检查通过；入口源码未改 |
| infra CLI | 已有环境加载与 help 通过，未执行会生成研究结果的 CLI |
| infra 现有测试 | 37 项通过；5 项 runner 测试在 pytest tmp_path 初始化时因 WinError 5 拒绝访问而未执行。独立 TEMP basetemp 重试同样阻断，没有算作 42 项本次通过 |
| 当前导航 | 新两条进度线、根/局部 README、复现、归档索引及环境文档的本地链接检查；具体数量记录在机器回执 |

历史“42 测试通过”、R13 744 项模型执行与其他轮次 PASS 仍只归属于原回执时点。测试临时目录权限和 R13 既有 `.gitignore` 哈希差异未在本轮扩大为环境/实验修复任务。
