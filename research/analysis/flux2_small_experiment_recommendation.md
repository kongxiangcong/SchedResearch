# FLUX.2 小范围补验证建议

日期：2026-09-05。状态：证据回溯与实验范围建议；不是预登记，没有启动新性能实验，不修改R1–R10冻结工件。

## 已经测过什么

| 轮次 | 对象 | 结果 | 限制 |
|---|---|---|---|
| R3 | 手写DiT CFG/AdaLN motif | 有扰动时B对A2约+0.281%，低于5%门 | 非真实FLUX图或设备 |
| R4 | 官方FLUX.2-klein-4B distilled的double/single block及融合边界对照 | 收费ready不达门；FLUX priority校正最好约+0.197%，95%区间跨0 | H64、4heads、image16/text8；整task资源；attention aggregate仍计materialized scores/probabilities，不是online attention |
| R5 | FLUX fullK3072、M32、两个fusedN128投影tile | 12个请求级条件收费ready均负；combined约−1.2751%；quiet固定traffic改序upper约3.96% | 全K但非完整层；缺attention/gating/fused-output的完整fork/join |
| R9/R10 | Qwen投影、两cluster参考路径 | 新的供给、下界、静态与动作证据 | 没有在同样细模型中确认完整FLUX block |

来源：[R3](D:/dsh-proj/SchedResarch/r3/experiment_report.md:60)、[R4](D:/dsh-proj/SchedResarch/r4/experiment_report.md:22)、[R4校正](D:/dsh-proj/SchedResarch/r4/experiment_report.md:63)、[R5全条件](D:/dsh-proj/SchedResarch/r5/results/all_cases.md:13)、[R5范围](D:/dsh-proj/SchedResarch/r5/experiment_report.md:23)。

## 是否值得补

建议只补一次结构明确的边界实验。已有证据足以停止继续调整已测通用ready；不足以证明真实尺寸完整FLUX block在多cluster/有限容量/强融合之后都没有动态空间。新的问题是完整block数据生命周期及异构分叉是否改变静态与动态的比较，而不是换模型名字再重复projection。

## 最小对象

继续使用冻结的FLUX.2-klein-4B distilled，B=1、T2I、无reference tokens、单denoising step中的一个完整single-stream block。完整H3072、24heads、d128、MLP9216；采用合法512×512输入，1024 image tokens加默认512 text tokens，L1536。此结果不外推更大分辨率、所有block或全pipeline。

选择single的原因：官方有20个single block，其完整边界比double-stream join更小；fused linear1之后才分为attention和SiLU(gate)*value，随后fused linear2与residual。不能把门控支路建成另一条完整两层FFN，不能免费拆分/重排浮点累加。

来源：[模型证据](D:/dsh-proj/SchedResarch/r4/flux_model_evidence.md:23)、[融合公式](D:/dsh-proj/SchedResarch/r4/flux_model_evidence.md:65)、[官方固定revision代码](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/model.py#L437-L483)、[官方固定配置](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/e7b7dc27f91deacad38e78976d1f2b499d76a294/transformer/config.json)。图像token数依据冻结VAE scale8及2×2 packing；当前建议不改模型revision。

## 必要强基线与预算边界

仅一个固定参考硬件，两cluster各两core。先做whole-block数值、地址、临时生命周期和资源账本；输入/权重初始位置与所有输出最终位置固定，完整搬运计费。

静态基线必须有合法tiling、驻留、prefetch和流水，保留fused linear1/linear2，避免人为全tensor barrier。Attention采用有明确running max/sum/accumulator生命周期和Q/K/V/O流量的tiled online-softmax合同；R4旧aggregate不能直接冒称这一强基线。任何数值顺序变更必须显式准入。有限VMEM、credit、DMA、MXU/VPU冲突与所有内生排队仍需计入。

不需要为了这个判别问题运行完整出图pipeline或下载完整大权重。随机/构造输入可以验证block算法与图保持；它们不等于真实权重质量验证，reference-cycle结果也不等于images/s。

## 判别顺序与停止门

1. 新train/validation选择strong-static，再计算whole-block必要资源/依赖下界。保持每个bound的固定graph与动作范围，不能把一种policy的内生trace强制复用给另一种。
2. 若两个背景、两session所有确认块的同合同零成本恢复上界均<5%，关闭该具名合同的额外改序候选；不把均值门偷换成逐block门，不外推连续phase或更大分辨率。
3. 若fusion/online attention/驻留/流水已经实现收益，归静态优化。若界仍松，先确认一个有限动作实际可触发、并能影响完整block结束；无有效触发便停止该规则，不再大量确认只有观察费的运行。
4. 只有出现上述证据才登记收费causal policy，用新相位进行quiet/20%/35%背景、两独立模拟session、每条件每组至少30paired blocks确认。单一shape/hardware下为180个独立block/对照。保持≥5%净elapsed、95%paired CI下界>0及quiet回退≤1%的机制门。
5. 执行前固定候选、观察/动作预算、样本和退出规则。若结果仍无法区分松界与可行动空间，应保留未决后结束本轮，不能通过不断增加policy延续实验。

建议优先级：这项完整FLUX block边界验证，比继续R10相同Qwen投影触发器更有判别力。它与暂停通用ready机制扩张相容；并不预先接受新scheduler，也不撤销R4/R5旧负结果。
