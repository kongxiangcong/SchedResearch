# R4：Qwen3.5 / FLUX.2 真实来源小图与强化静态对照

先读 [阶段报告](experiment_report.md)、[模型冻结](model_registry.md)、[独立红队](redteam_report.md)。

本轮已完成官方核验、七种缩尺图边界、FP64随机数值与有状态重排检查、编译融合/双缓冲/安全内存计划、强静态、13,440次主仿真和4,480次priority校正。主收费B2在70配置均值上均慢于S；提示修正后最佳+0.197%且区间跨零，仍不扩张有限事件硬件。优先级校正和训练trace静态修复在报告中单列为后验诊断。

实验模型保持单cluster、多core与共享DMA/SRAM的架构边界，完整模型/真实硬件性能仍未验收。所有参数、seeds、源码hash、地址与完整trace位于 [results/r4](../experiments/results/r4/manifest.json)。

| 文件 | 用途 |
|---|---|
| [problem.md](problem.md) / [hypotheses.md](hypotheses.md) | 问题、可证伪假设与实际决定 |
| [experiment_plan.md](experiment_plan.md) | 结果前冻结的划分、成本和解释规则 |
| [experiment_report.md](experiment_report.md) | 全面结果、成本、等待与接受边界 |
| [qwen_model_evidence.md](qwen_model_evidence.md) / [flux_model_evidence.md](flux_model_evidence.md) | 官方模型/源码/参数/许可的冻结证据 |
| [prior_art_delta.md](prior_art_delta.md) | 新近强静态与动态先例差异 |
| [redteam_report.md](redteam_report.md) | 独立数值、物理合同、时序和统计检查 |
| [rejected_refined_directions.md](rejected_refined_directions.md) / [next_round.md](next_round.md) | 拒绝、细化与下轮前置证据 |
| [r3_snapshot/manifest.json](r3_snapshot/manifest.json) | R3源码快照与旧结果完整性 |
| [artifact_integrity.json](../experiments/results/r4/artifact_integrity.json) | 官方证据、执行源码、旧结果、产物哈希与文档链接最终核对 |

主要复现入口：`python -X utf8 -B -m r4.run`；其余完整命令在阶段报告。此目录不是生产llmSched源码，本轮没有Git操作或全局依赖安装。
