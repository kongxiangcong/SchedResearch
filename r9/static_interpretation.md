# R9 静态方案与资源下界的物理解释

本文只读取冻结的参考合同、实现、预登记候选和结果文件；不改 simulator，不加结果导向的候选或参数。数值是参考模型选择，不是 R1 参数复现、当前 TARS 规格或硅后证据。

## 可解析的最低 traffic

固定 M32/K9216/N128，X、W 为每元素 2 B，最终 Y 与 partial 为每元素 4 B。令：

- `X = 32 × 9216 × 2 = 589,824 B`。
- `W = 128 × 9216 × 2 = 2,359,296 B`。
- `Y = 32 × 128 × 4 = 16,384 B`。

只允许合同内的 intra-cluster multicast；没有跨 cluster 广播、压缩、缓存命中或免费 prepacked 输入。

| Mapping | 有 multicast 的最低 EXT bytes | 无 multicast 的 EXT bytes | 必需 local DMA bytes |
| --- | ---: | ---: | ---: |
| C2N | `2X + W + Y = 3,555,328` | `4X + W + Y = 4,734,976` | 每 cluster `2X + W/2 + Y/2 = 2,367,488` |
| C2K | `X + W + 3Y = 2,998,272` | `2X + W + 3Y = 3,588,096` | cluster 0 `X + W/2 + 2Y = 1,802,240`；cluster 1 `X + W/2 + Y = 1,785,856` |
| C1N 局部控制 | `X + W + Y = 2,965,504` | `2X + W + Y = 3,555,328` | 单 cluster `2X + W + Y = 3,555,328` |

C2N 两个 cluster 都要全 X；cluster 内广播最多使每个 cluster 只从 EXT 读一次 X。C2K 的两个 cluster 各取一半 K，因此全芯片合计只要一次 X；代价是一个完整 Y 大小的 partial 经同一个 EXT 写一次、再读一次。这里 `3Y` 包含最终 Y store 与两次 staging，不增加任何独立带宽。C1N 无 staging，但两个 core 的私有 VMEM 都要接收 X，广播不减少 local DMA traffic。

本 workload 的所有已登记 tile/source spans 都按 32 B beat 对齐，gather 和 row 因而不会改变这些总 bytes；它们改变 packet 数与可重叠时点。全部 W 元素各读取一次。resident X 与 tile X 都只传所属的同一批元素，驻留不是减少已重复读取 X 的额外 cache 优化。

在主问题仅含 C2N/C2K 的前提下，全局最低 EXT traffic 是 C2K+multicast 的 **2,998,272 B**。这个说法只是两种已声明算法/映射的解析 byte 最小值，不是所有 NPU 算法、所有切分和所有架构的下界。若把 C1N 也纳入，最低 EXT bytes 会降到 2,965,504，不能继续套用 C2K 的数值。与此同时，C1N 的单 cluster DMA 下界在主参考速率下是 `3,555,328 / 64 = 55,552 cycle`，所以仅比较 EXT bytes 会错判 C1N。

## 哪一种 upper bound

`resource_lower_bound(graph, hw, environment)` 是同一 graph 的乐观资源下界：共享 EXT 在共同绝对供给过程中的最早可完成时刻、各 cluster 聚合 local DMA cycles、各 core 聚合 compute/reduce cycles的最大值。它不计依赖链、request latency、visibility 或有限窗口成本，方向为 `L ≤ 可实现 elapsed`。因此 `(T-L)/T` 限制的是保持该 graph 工作量与资源合同的零成本恢复比例，而不是证明某个已实现动作能恢复这么多。

主参考 selected C2K 已达到上述两种 main mapping 的最低 EXT bytes；主参考下该 EXT 项又支配其他聚合资源项。因此它的 **EXT 部分**也给出了跨这两个 main mapping 的合法乐观时间下界。更一般的参数下必须逐 mapping 算资源下界后取最小值；不能把某个 mapping 较大的 core/local-DMA 下界当作所有 mapping 的公共下界。

## 冻结选择与已有 train 证据

`results/selection.json` 对 main 的 quiet、20% 和 35% 条件都选中 `107df77bc857`：C2K、Ktile256、双 buffer、prefetch2、tile X、intra-cluster multicast、gather、xw、reverse、outstanding4。对应每个 K shard 有 18 个 256 tile，实际模型 MAC 覆盖不变。

reverse=True 与 forward anchor `c81660618e33` 在已有 train 的 quiet 和全部 phase 上完全相同；选择来自 canonical ID tie-break。不能宣称反向 core 顺序带来收益。

以下只摘录已冻结 training.json 中围绕 forward anchor 的已有候选；它们有助于解释实现行为，不是独立 test 的逐因素因果验证，也不构成事后扩池：

| 既有候选变化 | quiet elapsed / cycle | EXT bytes | packets |
| --- | ---: | ---: | ---: |
| anchor：C2K256 / multicast / 双 buffer / gather / outstanding4 | 47,776 | 2,998,272 | 732 |
| 无 multicast | 56,984 | 3,588,096 | 876 |
| Ktile512 | 48,680 | 2,998,272 | 732 |
| Ktile1024（最后 tile512） | 49,704 | 2,998,272 | 732 |
| resident X，仍 Ktile256 | 48,216 | 2,998,272 | 732 |
| row packetization | 48,188 | 2,998,272 | 5,832 |
| outstanding1 | 58,416 | 2,998,272 | 732 |
| outstanding2 | 47,800 | 2,998,272 | 732 |
| prefetch1，仍预留双 buffer | 48,024 | 2,998,272 | 732 |
| 单 buffer / prefetch1 | 48,024 | 2,998,272 | 732 |

multicast 的差异首先有明确 byte 解释；其额外 destination 在 local DMA 中照计。tile256 更早释放下一步可计算输入与可复用 slots，降低依赖和收尾空隙；不能把它解释成总 bytes 下降。gather 用合法源跨度合并减少短请求数量，源数组仍为共同 row-major。outstanding1 会显著压缩 latency/EXT/local/visibility 的流水并发，outstanding2 已很接近4。resident X 在这个不重读同一 X 元素的 workload 中没有 traffic 优势，且完整 resident-X command 可见性会延后依赖计算的开始。

## 独立 test：已观察结果与停止门

读取完整 `summary.json` 与 `controls.json`，每条件每 session 有30个独立 paired phase blocks。main 的 quiet-selected 与干扰下重新选出的 static 是同一 ID，因此 **strong-static elimination 为0**：这不能解释成静态无价值，而是 quiet 时已选到同一套强静态。

| 条件 | Session | 同一 static 干扰损失均值 | 零成本剩余 upper 均值 / 最大值 | 已采样最佳收费单动作均值 |
| --- | ---: | ---: | ---: | ---: |
| quiet | 1、2 | 0% | 1.9424% / 1.9424% | 0% |
| 20%预留 | 1 | 24.7543% | 1.7077% / 4.2404% | 0.0210% |
| 20%预留 | 2 | 25.3070% | 1.6066% / 4.0514% | 0.0080% |
| 35%预留 | 1 | 52.8112% | 1.8776% / 5.1579% | 0% |
| 35%预留 | 2 | 53.0114% | 1.8092% / 5.1579% | 0% |

20%条件收费动作均值的95% paired t CI分别为 `[-0.0030%, 0.0451%]` 与 `[-0.0037%, 0.0197%]`；均跨0且远低于5%。动作集合只采每条 trace 最前4和最后4个有分歧的 EXT epoch，每处取第一个非默认 eligible alternative，并含 no-action。它是有限的 hindsight screen，不是全动作枚举或可部署因果策略。收费8 cycle有时通过改变后续资源顺序反而比同一动作免费执行结束更早，故“已采样免费动作”也不应被叫作所有收费动作的上界；真正的公共零成本上界来自独立资源下界。

**预登记的两个干扰条件、两 session、每个 block 的 upper 都低于5%的关闭门未通过。** 35%条件两 session 都有5.1579%的 block；不得用均值低于5%替代原条件，也不得据此关闭所有同合同选序机制。已测有界单动作没有达到接受门，可以拒绝它；35%条件的严格全相位/全合法顺序恢复空间仍未决。

一个可审计的边界例子是 `s1.reserved35.b27`，phase=`4496.963182387463`：乐观 EXT 下界为69,785.6 cycle，早于随后预留区间 `[70,032.9632, 72,900.1632)`；selected-static结束于73,580.8，跨过了该预留窗口。5.1579%的大 pointwise upper 与这个周期边界一致。这只是已观察供给曲线的解释，既没有证明有合法动作能避开窗口，也没有事后收紧或替换预登记下界。

局部控制同时说明 mapping 的收益不能归到新机制头上。quiet 的 main 为47,776 cycle，C2N为55,912，C1N为56,512；对应main相对收益14.5514%和15.4587%。在两 session 合并的逐block描述性均值中，20%/35%条件main相对C2N为14.4310%/14.9620%，相对C1N为13.4163%/13.7616%。这些是合法静态映射/资源使用方式的比较，不是 scheduler净收益，也不是核心数量变化的纯因果效应。

## 敏感性范围与失效条件

runner 的敏感性是一次只改一个数值：EXT rate 32/128、cluster DMA rate 32/128、MAC rate512/2048、request latency4/36，以及 VMEM usable256KiB。其他字段固定。VMEM 探针用 total=`262144 + 65536` 来保留原保留区，而不是把256KiB误当含保留区总容量。

敏感性重训池限定为 C2N/C2K、tile256/512/1024、multicast 开/关、双 buffer、prefetch2、gather、tile X、xw、forward、outstanding4；共12个结构性候选，可能因小 VMEM 被判非法。它省略 C1N、resident X、row、reverse、低 outstanding、单 buffer 和其他交互，因此若出现大 upper bound，只能报告范围未决，不能推断全静态仍有同样空间。每条件只按 train 最优 ID 进入三条件合并的 validation shortlist，也弱于主实验每 mapping/input-mode top4 的选择规则。

读取完整9组 `sensitivity.json`，下表是各条件合并两个session、共60个block的 **upper最大值**，不是实际可恢复收益：

| 一次改变的参数 | quiet upper | 20% upper最大 | 35% upper最大 |
| --- | ---: | ---: | ---: |
| EXT rate32 B/cycle | 0.5941% | 1.8500% | 2.3442% |
| EXT rate128 B/cycle | 4.1655% | 19.8588% | 19.2159% |
| cluster DMA rate32 B/cycle | 2.1679% | 15.8944% | 15.4100% |
| cluster DMA rate128 B/cycle | 1.6129% | 3.9756% | 4.9512% |
| MAC512/core/cycle | 4.0000% | 5.8240% | 6.2206% |
| MAC2048/core/cycle | 1.8109% | 4.1397% | 5.0856% |
| request latency4 cycle | 1.8931% | 4.1775% | 5.2814% |
| request latency36 cycle | 2.1390% | 4.5664% | 5.4409% |
| VMEM usable256KiB/core | 1.9424% | 4.2404% | 5.1579% |

EXT128和DMA32的quiet选择改为C2K256无multicast；干扰条件仍选择multicast。这说明用额外EXT读取替代较长的单次multicast local服务，可能在quiet更利于该实现的有限窗口流水；不是广播总local bytes变少，也不能得出广播总有益或总有害。它们的干扰upper分别达到约20%与16%，公共供给+聚合资源下界在那里更松，当前证据不能确认具体机制能填补这些空间。MAC512、MAC2048、两种latency及小VMEM也未满足所有已测干扰block均低于5%的强关闭条件。

小VMEM有4/12候选因容量不足被排除：C2N/C2K的tile1024各两种输入方式。selected tile256在归约接收core只需112KiB净VMEM，发送core需104KiB，因此这一次缩容不改变selected结果；这不等于完整驻留、其他工作量或未测试容量都不敏感。

单参数变化不覆盖参数交互；phase过程只是周期供给预留；没有改变packet/beat、command/transport数量、visibility、operand rate、reduction rate、VMEM bank等选择；没有真实TARS校准。所有这些结果均为模型内的条件性筛查。没有正机制接受，也没有将主参考的负结果外推到全部多cluster。
