# R9 事前登记：共享外存供给与静态剩余空间

登记阶段：参考合同已选定，R9 性能实验尚未运行。用户授权自主建模；真实 TARS 参数留给后续替换。所有新工件在 r9，历史不改。

1. **RQ1 / H1**：Qwen down M32/K9216/N128 在共享 EXT 路径上的干扰损失，主要是否来自共同供给减少？同一个 quiet-selected static 在 quiet、20% 和 35% 外存预留背景下配对。计算每条计划的资源下界，不能把不同静态各自重训差分叫固定计划损失。
2. **RQ2 / H2**：mapping、cluster 内广播、驻留、tile、单双 buffer、prefetch、layout、顺序和 outstanding 是否已消除可恢复部分？对同硬件的 C2N/C2K 建有限但明确的 strong-static 候选池；C1N 只作局部控制。每个环境重新从 train/validation 选静态，再在独立 test 比较。不是全静态最优的证明。
3. **RQ3 / H3**：strong-static 后还有超过 5% 的同合同顺序恢复空间吗？先用共同供给曲线与不可删除 bytes/MAC 的乐观资源下界给上界 `(T-L)/T`，再做一个合法 DMA 选择的单动作反事实。反事实只改一个已经 eligible 的请求选择，重算其后全部内生服务；不复用其他 policy 的延迟 trace。可报 zero-cost 上界与每动作 8 cycle 的研究收费结果，不把回看式最佳动作叫 causal policy。

主参考数值与能力集中于 reference_hardware.json。初始为同一 row-major 外存 X/W，终点为全 Y 外存可见；允许两种明确 FP32 算法，不假称官方 bitwise。仅 shared-EXT-cluster-DMA-VMEM，split-K 经同一个外存服务写后读；本轮不增加 peer link 或完整 NoC。

背景是**绝对时间资源供给**：每 8192 cycle 周期内 `[phase,phase+duty*period)` 的外存服务预留给其他客户，duty=0/0.20/0.35；服务可跨预留区暂停。每运行从 t=0 开始，phase 由独立随机 seed 预先产生并保存。同一 block 的所有方案共享 phase，任何方案均不得改变此过程。它是固定带宽预留抽象，不模拟背景请求队列，也不证明真实 DRAM 干扰分布。

Train：8 个独立 phase；validation：8 个新 phase。为减少重复成本，先以 quiet 与 train 均值筛选每 mapping/输入方式/环境的前 4 项，再在 validation 择优；完整候选及筛选规则落盘。Test：两组独立模拟 phase sessions，每条件每组 30 个独立 paired blocks。seed 系列 910000(train)、920000(validation)、930000/940000(test)。禁止以 test 改候选或参数。报告 paired mean gain 与 95% t CI；另报按资源下界得到的零成本恢复上界及其有限样本范围。模拟 session 不是实机 session。

tiny exact 使用同一引擎、两个 DMA 请求链与明确枚举的合法资源顺序，在两个固定背景相位全枚举；下界须独立复算。完整主工作量全 requests 的 bytes、容量、last-reader、可见性与最终结束审计；故障 fixture 必須检测漏传、过早消费、复用和 credit 超限。

停止门：主参考两个非极端背景、两 session 的 strong-static 若最大 zero-cost 恢复上界不足 5%，关闭**本参考主条件的额外 DMA 选序候选**。更宽敏感性若不满足同样界，标为未决，不能外推关闭。若上界有空间但单动作无净恢复，只拒绝已测单动作，不能宣称所有机制无价值。只有同合同合法因果动作、≥5% 收费净 elapsed、95% paired CI 下界>0、quiet 回退≤1% 都成立，才探查一个有界最小机制；即使通过也只有模型筛查，最终接受待真实目标。

红队重点：带宽重复赠予、广播 local bytes 遗漏、原始 layout 免费预打包、出站与入站 staging 少计、有限窗口队頭人为失能、测试泄漏、相位不是共同时间、下界方向错误、初始与结束位置不一致、同刻事件顺序偏差。结果保留负值和失效范围。
