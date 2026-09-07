# R4之后：由负结果限定下一轮

R4已经完成一次来源→数值→强静态→仿真→独立审计闭环，产物保留，不从R1重做。主结果未达到新增硬件证据门；下一轮首先补模型保真度，而非增加OoO状态。

1. **全宽最小tile与真实状态容量。** 从冻结Qwen linear层的2MiB FP32 recurrent state或full层4096BL-byte KV开始，导入一段真正可执行的全维tensor切片与K/N tiling；同时支持合法in-place KV append，避免本轮SSA整cache拷贝的保守成本。FLUX从一个3072-wide block的矩阵tile开始，保留每step共享conditioning amortization。验收是完整地址/last-reader/partial reduction证明与实际BF16/FP32随机数值，不要求先下载整pipeline权重。
2. **测量或细化一个共享资源。** 优先真实设备的DMA request/finish/visible、MXU/VPU busy、SRAM port占用、background-master时间线；没有设备时可接入一个transaction-level memory模型，但参数必须有明确来源。把外生服务、时间相关背景、应用内生队列拆开；不再扩大独立随机compute假设。
3. **加强已有静态，修正提示。** 继承R4同容量合同与独立seed划分；继续资源序搜索直到报告收敛迹象，或接入适配当前小图的约束求解。priority探针与训练trace静态候选诊断属于后验探索，若要提出正结果，冻结新方案后用新的train/validation/test和预登记阈值确认。
4. **只有真实净收益成立才启动有限事件协议。** 对full-history B与固定静态同预算，证明剩余机会不是新buffer/带宽/融合变化带来；收费后仍有意义，再设计compiler event frontier/epoch、late admission/completion、slot reuse、有限FIFO/backpressure。现在不宣称已有有限总硬件实现。
5. **最后选层级与novelty。** 单cluster因果收益成立后，才分别增cluster/chip，固定总控制预算并计route/credit/visibility。用TaskStream/ASPEN/HwSch/LATTICE逐机制对照，给具体且已测的state/服务率/收益差异。RTL/PPA仍是之后单独证据门。

建议停止条件保持直接：如果全宽/校准环境下最优可用静态与经过提示修正的最小动态仍近似相等，结束通用completion-ready硬件方向，把可复现负结果、合法合同和trace诊断方法保留。不能为了延续题目在模型中人为增加独立DMA、异步CFG分支或随机compute。

现有本机环境可以直接复现R4；不需要全局安装新依赖。R1/R2/R3原始源码/结果完整保留，当前公共sim未改；本目录无Git提交/推送。
