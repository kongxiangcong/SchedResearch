# R3 文献审查结论

日期：2026-09-05。详细证据见 [registry](../literature/prior_art_registry.md)、[foundational](../literature/foundational_work.md)、[recent](../literature/recent_work_2024_2026.md)、[novelty redteam](../analysis/novelty_redteam.md)。

Hybrid 是有独立实验意义的设计空间，但“编译依赖 + completion dispatch”的范式已经成熟，不能成为贡献标题。文献并未支持一个通用结论：所有 NPU 都应更动态，或所有调度都能静态完成。关键是原始 DAG 的合法并行、实际剩余方差、资源状态信息的可观察性和控制成本。

本轮最重要的新增邻域是 LATTICE（2026 v3）：它把地址复用和spill语义作为memory plan contract交给时序优化。因此R2将该组合视为尚未被覆盖的编译器内核需要重审。TaskStream 已经有coreMask、sizehint、typed edge和hierarchical dataflow；ASPEN已有离线tile DAG、dependency counter、分布式ready执行。只把这些移植到NPU不能形成可靠delta。

强静态基线至少应借鉴Rammer/Welder的tile/fusion/memory优化、PipeThreader的异构sTask/sEU流水、TileLink/HyperParallel-MoE的通信compute overlap。VTA和Gemmini告诉我们：access-execute decoupling与依赖安全本身已有成熟低成本机制；把全局静态DMA序列换成work-conserving arbitration所获收益，应与更复杂的task OoO分开。

保留的研究方向是**测定最少动态硬件的有效边界**：固定mapping/address/contract，先测小窗口dependency-ready dispatch是否足够，再衡量更复杂runtime priority与层次协调的净收益。多cluster/chip必须计completion传播、shared-resource contention、credit和bank/链路条件；scale增加可能扩大方差，也可能放大调度成本或消灭独立工作，不能预设单调提速。

openNVDLA2026硬件scheduler论文的约30%提升主要来自host操作调度开销，不能成为本题runtime uncertainty的正面证据。Pistil的Hot Chips2026官方题录确认了20chiplet端侧SLM场景存在，但未读poster正文前不推断其调度机制。

后续paper shape应以实验可推翻的句子表达：在何种共享通信条件和ready-window预算内，B是否逼近更复杂C；在哪些图/方差/成本区间A就足够。若本地sim只能支持synthetic存在性，就明确止于存在性；LLM/DiT产品结论需要真实trace或经校准的memory/NoC模型。
