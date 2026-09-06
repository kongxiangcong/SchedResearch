# R4：真实来源子图经过强化静态后，还剩什么等待

日期：2026-09-05。继承 R1 的图、固定 mapping、storage view、命名 completion、last-reader 与显式 WAR/WAW 合同；继承 R3 的独立编译/事件 harness，原始 sim 与 R1/R2/R3 结果保留。外部 llmSched 不在本目录，本轮没有接触或验收其当前实现。

核心问题是：已知图和固定容量下，运行时获得的完成信息，能否恢复强静态留下且会影响结束时间的等待，并抵偿控制成本。等待的存在、合法替代任务存在、资源实际空闲、提前执行改善 critical path、硬件成本可接受，是五个不同判断。

本轮将 R3 motif 升级为官方配置/源码可追溯的小图：Qwen3.5 两种文本 decoder、FLUX.2 klein 两种 flow-transformer block。官方版本是真实约4B，实际数值与时序图仍是明确缩尺。来源与公式正确性、随机权重数值正确性、抽象时序对照、实物验收分开。

编译工作先于动态：投影合并、FFN gate/up 融合、合法 head/intermediate/query-row 分片、同核 VPU 链融合、异步 operand-pack 预取、1/2/4槽内存计划敏感性、全 reader 的安全复用与 live-out 钉住。进一步对照 attention aggregate 与已驻留 FLUX conditioning；保留内部 scratch 和流量。没有实现完整 4B 全维 K tiling、量化部署、online-softmax kernel 或生产级 mapping/fusion 搜索。

静态 S 在独立训练集探索资源顺序，再由 validation 冻结；S8 是原八候选池。小型真实 FFN tile 子图另做有限两点分布精确最优。动态 B 只读已完成/已就绪/资源状态，没有未来 service time；H 仅放开 DMA/SRAM 仲裁，保留 compute 顺序。两者不重新分配地址。

背景环境按绝对时间定义，调度改变请求时刻时重新积分；独立外生 DMA 服务因子固定在 task-id+seed，应用自身排队由资源模型重新产生。稠密 compute 不加随机。当前日历仍是假设，不能冒充 LPDDR refresh 或实测 SoC 争用。

先例已经覆盖宽泛的 compiler contract + completion dispatch，且 LATTICE/Stream/PipeThreader 使弱静态基线无法支持论文结论。本轮只判断可恢复等待的证据是否改善，不预选 OoO、CAM/ROB、跨 chip 或 bounded event table。只有收费收益经过更强融合、端口组织和独立测试后仍有意义，才进入有限总事件状态；否则保留负结果并收窄下一轮。
