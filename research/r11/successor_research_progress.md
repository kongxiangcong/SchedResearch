# R11 successor progress snapshot

This successor preserves the R10 parent snapshots recorded in `r11/history_lineage.json` and appends one completed R11 row. The root `research_progress.md` receives the same eight-field row as an append-only update.

| Round | Research Question | Hypothesis | Experiment | Key Result | Verdict | Remaining Uncertainty | Next Decision |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R11：完整GDN单层静态驻留 | 完整32-head GDN单层、合法已知四token输入下，保留state能否在共同成本和强静态baseline上减少净elapsed；严格decode是否仍有合法干预？ | Prefill可减少每token state读写；严格decode可能因输入释放和RF clobber不具备同样复用。 | 预登记完整 qkv/z/a/b、conv、gated-delta、norm、out module；76数值prefill blocks、4 decode callback representatives；有限静态计划独立train/validation；quiet与两组30 paired background blocks；122 traces独立复核。 | 数值/容量/生命周期/审计均PASS；32-head state 2,097,152 B，local state read/write 16,777,216→4,194,304 B，external 88,863,488 B共同；quiet −0.015670637%；A −0.599174254% CI [−0.610049107,−0.588299401]；B −0.605967308% CI [−0.617565500,−0.594369116]；decode graphs identical。 | **Prefill：本轮未获支持，方向关闭；decode：本轮未获支持，方向关闭。** 关闭该完整模块、cold-weight、staged ABI候选，不声称所有驻留数学不可能。 | 真实TARS/Phoenix kernel、warm-weight、跨层融合/存储合同未测；官方prefill chunk kernel与设备计量未执行；结果是参考模型证据。 | 停止该候选投入与动态机制扩张；保留原始证据。只有新硬件/融合/权重驻留合同和新的可判别问题，才另行预登记，不用本轮负结果外推全域。 |

Evidence: [experiment report](experiment_report.md), [results](results.json), [independent audit](independent_audit.md), [numerical results](numerical_results.json), [qualification](qualification_results.json), [source review](source_independent_review.md), [history verification](history_verification.md).
