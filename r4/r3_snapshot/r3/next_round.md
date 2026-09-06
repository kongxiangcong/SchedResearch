# 下一轮：按证据阻塞顺序推进

R3日期：2026-09-05。下一轮不预设“必须有动态收益”。最优先任务是找真实可恢复bubble，而非增加scheduler类型。

## Gate 1：把真实workload信息补齐

以一个开源LLM和一个DiT的单block为单位固定版本、shape/dtype/batch/seq/CFG，实现可复查的graph→task lowering。llmSched源码不在目录，不能假装import它；可通过独立export schema接收R1式图/descriptor记录，或用开源模型前端重建必要语义。至少真实体现QKV/GQA、KV读写、RMSNorm/SwiGLU、AdaLN/conditioning/CFG与归约顺序。

先比较强fusion、QKV或CFG折叠、tile流水、double buffering、layout和memory reuse。只保留优化后仍存在的task自由度；不要根据模型框图预设分支还在。

验收：同一lowering可输出静态计划与合同；独立检查tensor bytes、alias last-read和通信完成；至少一个数值小case验证保持语义。没有这一步，motif实验始终不能升级为真实LLM/DiT结论。

## Gate 2：残余不确定性与更强静态

收集或详细模拟每task的release/issue/finish/data-visible与queue/credit变化。优先LPDDR/共享SoC master等端侧条件；多chip再增加实际链路/collective。区分预测模型误差、外生方差、调度诱发排队、DVFS时间变化；测ready-order inversion和相关性。

静态基线升级到资源预约/局部交换搜索、更多训练样本，以及Stream/LATTICE式memory-constrained timing优化。保留独立validation选择静态policy，测试集冻结。对能求解的小子图加入最优静态/两场景exact，避免A2过拟合产生虚假亮点。

验收：收费B至少在代表图上有可解释稳定收益；同时报告无收益和回退。若强静态已填满关键瓶颈，停止硬件扩张。

## Gate 3：有限总状态，而不仅有限resident window

把目前O(N+E)history/通知表替换为真正有界的event frontiers；compiler输出event lifespan/region/epoch关系。实现late-completion、slot重用、有限FIFO、credits和无deadlock进展验证。

最小对照：head-only/self-timed FIFO、当前full-history B、候选bounded-state B。固定总descriptor bytes、SRAM、issue/wakeup带宽，扫描前沿宽度/跨域fanout/图规模。若压缩只把开销转移到descriptor或全局表，应如实拒绝。

验收：最小state在给定性能ε内保留大部分实际收益；丢失/重复/迟到event不会改变数值或误唤醒。

## Gate 4：选择层级与硬件实现

仅当收益和元数据结构都明确，再选core、cluster或chip的本地控制位置。比较central、distributed和真正hierarchical时，固定总端口与queue预算，并补wire/remote visibility成本。CPU式CAM/rename/ROB只有有明确语义需要才加入。

将最小候选写成RTL级微结构：entry定义、状态机、读写端口、每周期completion/wakeup/issue带宽、仲裁路径、外部credit协议。合成至少两个window/fanout参数点，报告面积/Fmax/energy的实测或估计来源。

## Gate 5：论文/专利novelty重新核验

对SPDI/TaskStream/ASPEN/HwSch/LATTICE更新逐机制对照和最接近claim；2026工作跟踪到实际版本/正文，不依赖检索摘要的旧标题。对工业Jalapeño补官方slides/ISA证据；对相关专利补原始claims、family与priority日期，不把专利申请当硅实现。

只有能够写出“先例做了X且有约束Y，我们通过具体硬件机制Z在相同预算下获得已测收益”才形成投稿方向。若最终静态最好，R3的反例、负结果与边界分析仍应保留，方向可收窄为cost-model/calibration或compiler-assisted asynchronous resource control。
