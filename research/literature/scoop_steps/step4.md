# Step 4 — Identify High-Potential Candidates

日期：2026-09-05。状态：完成当前限定scope；未取得全文的候选保留限制。

## Structured papers

全量 API 原始检索及逐条筛选见 [search_report.md](../literature/search_report.md) 与 [step3.md](../literature/scoop_steps/step3.md)。下表是正文优先读取的 7 篇；补充工程与其他学术条目见 [prior_art_registry.md](../literature/prior_art_registry.md)。这 7 篇按机制威胁与新近程度选择，不以 citation 数自动排序。

| 候选 | 选择理由 | 阅读证据与局限 |
|---|---|---|
| SPDI / EDGE 2004 | 静态 placement + dynamic issue + locality/contention 完整范式 | 作者 PDF §1–3、§4–5；本地下载失败，使用完整 PDF 解析正文 |
| VTA 2018/2019 | 编译 dependency bits + load/compute/store queues | 本地 PDF §3.1、§4–5；不能推断同队列 ready-set 任意重排 |
| TaskStream 2022 | typed task edges、coreMask、sizehint、hierarchical dataflow | 本地 PDF §2.2、§3.1/3.4、§4–5；高层自动 compiler 是 future work |
| ASPEN 2023 | 离线 tile graph + completion counters + distributed schedulers | 本地 PDF §3.1–3.3、§4–5；CPU prototype，cache/coherence 与 scratchpad 不同 |
| PipeThreader 2025 | 静态 task/异构 engine 调度已经消除很多 pipeline bubble | 本地 PDF §3.1–3.2、§4、§5；不是低层 warp dispatch 的替代 |
| HwSch/openNVDLA 2026 | 最近 NPU execution/dependency instruction + ROB/OCSR | 本地 PDF §3.1–3.4、§4；CNN，主要 host overhead，不能支持 LLM latency uncertainty 收益 |
| LATTICE 2026 v3 | memory plan contract + reuse order + legal pipeline refinement | 本地 PDF §III、§IV-D/E、§V；single-core deterministic replay，不是 device silicon 测量 |



API中SegFold、Tawa、Survival等也符合≥2筛选；在7篇上限内优先取机制直接匹配/覆盖R2核心论点的条目。遗漏威胁保留在registry，不因上限被认定不相关。