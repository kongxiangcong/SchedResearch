# R9 首跑前实现补注

性能主实验尚未运行。以下细化事前计划，不依据 R9 性能结果。

- 绝对时间供给使用连续 reference cycle，允许 0.2×8192=1638.4 和 0.35×8192=2867.2 的非整数区间。预留条件为 `((t-phase) % period) < duty*period`，因此负起点的前一周期也生效；所有方案在 t=0 用同一个 phase 开始。
- C2K 每 cluster K4608，Ktile1024 的最后一个 tile 是 K512，仍满足 32 倍数；实际 bytes/MAC 按真实 tile 宽度计。M 只用32，没有 M1 隐式 padding。
- strong-static 是有限结构化候选池：主网格交叉 mapping、Ktile、输入单播/cluster广播、单双buffer、X/W顺序；在双buffer、X先行锚点上增加 row layout、reverse core order、outstanding1/2、X全驻留和prefetch1单维探针；另含全驻留候选。未穷尽所有维度的联合组合，不声称静态全局最优。池由 run_experiment.py 的 pool() 在看到数据前生成并逐项保存。
- 主确认每 session 每条件30独立相位块。gain 为逐 block 的百分比再求均值，CI 使用 n=30、df29 的双侧 t 值2.045229642。quiet 是确定性重复，零宽区间不是实机稳定性证据。
- 单动作反事实固定检查最早4个与最晚4个存在多个 ready 外存请求的决策点，每处仅检查按当前候选列表的第一个非默认选项；分别收费0/8 cycle，完整重新执行。最晚决策点及事后选最佳结果包含未来知识；这是回看筛查，没有实现或验证 causal mechanism。可选择 no-action 的最优恢复量不用于声称 quiet 回退门通过。
- 敏感性逐一改变外存带宽、cluster DMA 带宽、核吞吐、请求固定延迟的上下端及VMEM可用256KiB。每个变体在预定义双buffer/gather/X先行/outstanding4的 mapping×Ktile×multicast 子池内独立train/validation选取，使用原独立test相位作配对敏感性比较。它不是新增机制确认，也不是每一变体完整strong-static最优搜索。
- 对每个已选固定合同，`L=max(共享外存累计可服务必需bytes的最早时间, 各cluster DMA必需bytes/速率, 各core必需compute时间)` 是放松先后约束的乐观下界。因此 `(T-L)/T` 上界只用于该合同内重排；不把它叫可恢复损失的实测值。若使用跨mapping最小bytes，另说明它覆盖的合法动作集合。
- 共享带宽预留直接减少前台可用供给，模型允许服务在预留起点暂停/终点恢复。这不是 packet不可抢占背景队列模型；后续真实目标若采用不同仲裁，需替换合同重测。

tiny exact 与独立 trace checker 会单独保存代码和回执；故障注入只操作内存中的证据副本，不修改正常原始trace。
