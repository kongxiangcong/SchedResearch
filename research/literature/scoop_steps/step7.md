# Step 7 — Articulate the Delta

日期：2026-09-05。状态：完成当前限定scope；未取得全文的候选保留限制。

## Verdict

**Level 2 — High Overlap**，针对“编译器给映射/依赖合同，NPU 通过 completion 动态派发 ready tasks”这一机制主张。最接近的 2026 openNVDLA 硬件调度论文在核心机制、协同 insight 和 AI accelerator 应用域三轴重合；其实际评估主要针对 CPU 调度开销，与本研究希望解释的 runtime uncertainty 尚有区别。EDGE/SPDI、VTA、ASPEN、TaskStream 分别覆盖静态放置动态发射、token 合同、离线 tile DAG 分布式 ready dispatch、带静态提示的层次 task dataflow。这个判级是选定轴下的人工检索结论，不是“还剩一轴即可发表”。

R2 的 memory-planning 子方向也不能继续宽泛声称“尚未同时覆盖”：**LATTICE v3 已明确将 static memory plan 作为 verifiable scheduling contract，并以地址复用边约束后续 timing refinement**。它不是 runtime dynamic hardware 研究，但直接覆盖 R2 建议的一大段编译器内核。[当前原文](https://arxiv.org/html/2607.17422)。

## Delta

目前不能写出带有“已获得可测收益”的可靠 delta。可以保留下面的**条件式研究问题**：

> 相比 LATTICE 的静态单核 memory-plan-constrained timing refinement，以及 TaskStream 的 task structure recovery，本研究拟在相同已优化 mapping/address/partial order 下，找出端侧多核 NPU 的共享通信资源完成不确定性何时需要额外调度自由度，并定量检验有限窗口、有限 wakeup 带宽的局部硬件是否获得足以支付成本的收益。

该句不能被当成已证明 contribution。它必须经过 realistic contention、强静态训练/测试隔离、信息对等与状态成本扫描；若收益消失，结论应改为“静态 compiler + self-timed queues 足够”。

