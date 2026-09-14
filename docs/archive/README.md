# 阶段归档索引

这里保存独立历史价值的提示词、选型审计、结构化交接和旧布局。归档文中的“当前”“下一轮”“必须”均属于当时任务，最新进度只读[科学问题线](../progress/scientific-questions.md)和[实验能力线](../progress/experimental-capabilities.md)。

## 集中存放的材料

| 路径 | 历史价值与原位置 |
|---|---|
| [infra 首轮提示词](prompts/infra-round-1.md) | 从固定 R13 底座转为优先开源基础设施；原根 `SchedResearch_next_round_infra_prompt.md` |
| [infra 第二轮提示词](prompts/infra-round-2.md) | 选择计划修复/STREAM 静态评估；原根 `SchedResearch_round2_repair_and_static_eval_prompt_COMPLETED.md` |
| [首轮结构化交接](infra/round-1.json) | PARTIAL、原计划身份、B1/B2/B3 验收；原 `research/infra_open_source/handoff_2026-09-09_round1.json` |
| [第二轮结构化交接](infra/round-2.json) | 修复因果、身份变化、成功/失败运行；原 `research/infra_open_source/handoff.json` |
| [首轮选型源码审计](infra/round-1-source-audit.md) | ONNXim 源码定位、读取覆盖与环境尝试；原 `research/infra_open_source/report.md`，首轮状态已过时 |
| [R3/R4 历史首页](stages/r3-r4-homepage.md) | 当时完整解释；原 `research/README.md`，内部链接以 `research/` 为原始基准 |
| [初次归档布局](layout/initial-layout.md) | 曾用兼容路径的历史方案，已失效 |
| [此前迁移复现记录](layout/reproduction-before-2026-09-14.md) | 旧迁移的测试/重跑事实，不计作本轮验证 |

8 项迁移均保留原始字节与 SHA-256，精确映射见 [migration-map.json](migration-map.json)。归档中的命令、JSON path 与阅读记录保留当时字面值；使用时按该表转换，未迁移的 `research/...` 仍以仓库根解析。归档不是可直接执行的最新任务书。

归档 Markdown 历史链接先按表中原位置解析相对路径，再应用 migration-map。旧绝对 `D:/dsh-proj/SchedResarch/rN/...` 对应现 `research/rN/...`；固定提交 URL 不改。删除的活动文件在映射中列出替代入口。当前导航已使用新路径；保留原文不伪装其当时读过新文件。

## 原位冻结归档

下列材料统一在此索引管理，但物理路径不搬动；相对路径和哈希是复现合同的一部分。

| 原位路径 | 保留原因 |
|---|---|
| [重审证据包](../../SchedResearch_reassessment_evidence_20260907/proposal_contract.md)、[哈希](../../SchedResearch_reassessment_evidence_20260907/sha256.json) | R12/R13 冻结代码以根固定路径核验五项输入，包内证据与 Python 见证是一个单元 |
| [历史进度原文](../../research/research_progress.md) | R5–R10 检查/冻结/lineage 脚本读取此路径或原表行；停止维护，严格历史 successor 检查在匹配副本执行 |
| [R3 快照](../../research/r4/r3_snapshot/manifest.json) | 原源码/README/结果身份，不能去重或改链接 |
| `research/r6/history/` … `research/r13/history/` | 父子阶段、对齐前后、successor、R13 前台账原字节；重复字节承担 lineage 证明 |
| [R8 交接](../../research/r8/continuation_brief.md)、[R9 交接](../../research/r9/continuation_brief.md)、[R11 交接](../../research/r11/continuation_brief.md) | 被 handoff/history integrity 绑定，解释当时范围与决定 |
| [R11 successor](../../research/r11/successor_research_progress.md)、[R13 下一步合同](../../research/r13/p0_qualification_next.md) | 最终判决与未执行计划，保留冻结身份，不再持续维护 |
| `research/r3/` … `research/r13/` 的报告、计划、preregistration、amendments、审计和清单 | 阶段问题、先验门、反证与失败归因，不因路线变更删除 |
| `research/literature/scoop_steps/`、`research/analysis/` 独立分析 | 当时检索/判断与纠错，有来源或独立解释价值，并非当前进度 |

## 已整合并删除

删除 `research/analysis/r1_r10_research_retrospective.md`、infra 两份 `handoff*_to_chatgpt.md`，共三份重复台账/交接。问题、15 项候选状态、转向、边界、能力修复和验收条件均已进入两条进度线；R13 前回顾仍在冻结 history，infra 两轮 JSON 与首轮源码审计保留。没有删除实验产物、来源、失败运行或 lineage 文件。

以后提示词归 `prompts/<topic>-<stage>.md`，独立历史回执归具名子目录并保留身份。日常直接维护两条进度线，不新增 handoff/successor 副本；只有需要冻结时才建立新的具名快照和清单。
