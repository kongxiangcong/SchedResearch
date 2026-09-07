# R9 来源、分片流量与可恢复性边界独立审计

日期：2026-09-05。本文独立核对冻结的官方源、R8 账本/红队与 R9 授权，新增此文件；不修改旧轮、不执行旧实验、不选择 scheduler。研究对象现在允许自主参考硬件建模，真实 TARS 缺席不再阻塞本轮实施。[新授权](D:/dsh-proj/SchedResarch/r9/continuation_brief.md:3)

**审计结论：来源足以固定 full-K9216、N=[0,128)、M32 的 down 子问题；硬件能力、FP32 输出与 split-K 许可必须明确标为本轮研究选择。共享外存的有效下界可以排除同合同 5% 的恢复空间，但“背景使执行变慢”或“DMA 饱和”各自都不能证明动态机制价值。** 下列是实施前的来源和方法审查，不认证尚未产生的 R9 数值结果或时序轨迹。

## 1. 当前读到的第一手证据与标签

本文用 **S** 表示当前实际读取并核验 hash 的冻结官方源；**H** 表示旧轮的历史实现审计；**R** 表示本轮研究选择；**D** 表示从明确合同独立推导的公式；**E** 表示其他平台的官方规则、仅限其所说明的问题。S/H 都不能自动成为当前 TARS 参数。

| 对象 | 当前核验 | 可用结论及边界 |
| --- | --- | --- |
| S：Qwen3.5-4B config | 本地 SHA-256 `ddc63e1c717afa86c865bb5e01313d89d72bb53b97ad4a8a03ba8510c0621670`，与冻结 manifest 一致 | text dtype=BF16、hidden=2560、intermediate=9216、SiLU；不规定 NPU 累加树或有效吞吐。 |
| S：Transformers MLP 实现 | 本地 SHA-256 `458360c8072e6130580639170ad3e645b975512dbabae31eab5f92de5f0f09ef`，当前读取 822–835 行 | `down_proj` 为无 bias 的 I→H；输入是 `SiLU(gate(x))*up(x)`。 |
| S：保存的 tensor-header 提取记录 | SHA-256 `0cfea86881cb17b746b5b8150bf7ce35605756141c1ab365b1c4df9e962d372a`，与 manifest 一致 | down weight 为 `[2560,9216]` BF16；这是已保存的 header 提取记录，未重新下载权重 payload。 |
| H：TARS 几何/VMEM/DMA | 当前读取 R8 对 R1 的来源追溯 | 32×32 MXU、4 MiB VMEM、cluster DMA 等仅为历史启发；未读取当前 TARS connected RTL。 |

第一手源定位：[本地 config](D:/dsh-proj/SchedResarch/r5/sources/qwen/config.json:7)、[本地 MLP 源码](D:/dsh-proj/SchedResarch/r5/sources/qwen/modeling_qwen3_5.py:822)、[header 提取记录](D:/dsh-proj/SchedResarch/r5/sources/qwen/representative_weight_shapes.json:1)、[来源 manifest](D:/dsh-proj/SchedResarch/r5/sources/resource_source_manifest.json:5)。固定 upstream 身份来自 [Qwen revision 清单](D:/dsh-proj/SchedResarch/r5/sources/qwen/r4_manifest.json:3)：[Qwen config @851bf6e](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/config.json) 与 [Transformers @f62dc9b](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L822-L835)。本次核验冻结本地内容，不把这些固定版本描述为 upstream 最新版。H 的直接入口是 [R8 source audit](D:/dsh-proj/SchedResarch/r8/source_contract_audit.md:19)。

**R：本轮选 N 的前128列和 M32 prepared 输入，研究 FP32 输出。** 这是完整 down 的 1/20 输出宽度，不是完整 down/MLP、真实激活分布或 autoregressive 输入到达过程。R8 明确冻结 FP32 partial 和输出；如果 R9 改为 BF16 最终输出，必须同时计最终 cast、输出 bytes，并对所有 mapping 使用同一合同。[R8 target workload](D:/dsh-proj/SchedResarch/r8/target_contract.json:30)、[R8 来源/输出边界红队](D:/dsh-proj/SchedResarch/r8/redteam_report.md:17)

## 2. 数值许可不由 shape 或随机容差推出

**S：**官方 MLP 源码仅定义 `Linear` 与函数组合，不规定 FP32 ascending-K 的累加次序、partial 导出、跨 cluster 加法或 FP32 最终输出。**E：**PyTorch 官方数值说明指出浮点运算顺序可能改变结果，相同数学运算不保证逐 bit 相同；BF16 GEMM 的中间精度也可能受 backend 选择影响。该说明本次实际联网读取，只支持数值边界，不提供 TARS 行为。[PyTorch 2.8 numerical accuracy](https://docs.pytorch.org/docs/2.8/notes/numerical_accuracy.html)

**H：**R8 保存的六组 split-K 随机结果均与有序 FP32 基线有 bit 差异，抵消反例是 ordered=1、split=0、FP64=2。18 个诊断容差通过并不授权新目标重关联。本次重读其独立审计，不重跑 CPU 实验替代 R9 进展。[R8 数值红队](D:/dsh-proj/SchedResarch/r8/redteam_report.md:17)

**R：R9 可明确许可两种不同的研究算法。** 至少冻结 BF16 X/W、乘积精度、每个 partial 的 FP32 累加/rounding、Ktile 跨 tile 是否持续同一 accumulator、最终 `P0+P1` 的 FP32 操作和 FP32/BF16 输出。可以声明“允许这两种研究数值合同、以条件模型比较资源”，不能声明已经获得官方 bitwise 或模型质量接受。M32 可满足所选32倍数几何；M1 若以后加入，必须独立明确 Mpad、零值生成、mask、实际 MAC 和实际传输，不沿用逻辑 M1 代价。[R8 numerical boundary](D:/dsh-proj/SchedResarch/r8/experiment_report.md:47)

## 3. D：统一起终点下的精确算术

以下全部是本审计独立推导，条件为 M=32、K=9216、N=128，BF16 X/W、FP32 partial/Y；紧凑且无 tail 的实际 payload；X/W 初始各一份在共享外存，最终完整 Y 外存可见；不跨 cluster 广播、无免费初始副本。静态 packing 可改变布局，但如需要运行时 pack/unpack，其计算和流量必须补齐。

定义 `B_X=2MK=589,824 B`，`B_W=2KN=2,359,296 B`，`B_Y=4MN=16,384 B`。原始有用工作为 `MKN=37,748,736 MAC`；四核均分各 `9,437,184 MAC`，两核控制各 `18,874,368 MAC`。这里只计 MAC，不把一 MAC 的“两次 FLOP”误用为两次硬件 issue。

| 方案 | 每核有效矩阵 | 全体 private VMEM X 写入 | 无 multicast 外存 X 读 | 仅 cluster 内双核 multicast 外存 X 读 |
| --- | --- | ---: | ---: | ---: |
| C1N：一 cluster 两核 | M32,K9216,N64 | `2B_X=1,179,648` | `2B_X=1,179,648` | `B_X=589,824` |
| C2N：两 cluster 四核 | M32,K9216,N32 | `4B_X=2,359,296` | `4B_X=2,359,296` | `2B_X=1,179,648` |
| C2K：cluster 切 K，core 切 N | M32,K4608,N64 | `2B_X=1,179,648` | `2B_X=1,179,648` | `B_X=589,824` |

**multicast 是明确的 R 能力选择。** 每 cluster 一次外存读可交付两个 private VMEM 副本，不代表两个 VMEM 只写一次，也不代表两个 cluster 可共享一次读。必须对复制网络/写端口规定带宽和接收条件：若共同捕获，两个目标都要有空间与 credit；若允许分别到达，要提供并计费中间缓冲与独立 visibility。不能让 multicast 请求只等待较快目标就释放另一目标槽。

C2K 的 cluster1 两核各输出 `4*M*(N/2)=8,192 B` 的 FP32 partial，合计 `B_P=16,384 B`。经外存 staging 是 `B_P` 写 + `B_P` 读 = **32,768 B**；还要在目标做 `MN=4,096` 次 FP32 adds。按读两个 FP32 partial、写一个 FP32 结果计，局部 reduction 的显式数据访问为 `12MN=49,152 B`，若在 accumulator/RF 中驻留则须注明对应的实际端口合同，不能直接加成外存 traffic。

| FP32 Y 外存总 payload | C1N | C2N | C2K，external staging |
| --- | ---: | ---: | ---: |
| 所有 X ingress 为单播 | 3,555,328 | 4,734,976 | 3,588,096 |
| 仅 cluster 内双核 multicast | 2,965,504 | 3,555,328 | 2,998,272 |

各行均为 `W + X外存读 + Y写 + staging写读`。C2K 相对 C2N 的 payload 减少分别为 `70/289=24.221453%` 与 `34/217=15.668203%`；这是 bytes 比例，**不是 elapsed 收益**。C1N 与 C2N/C2K 增减了核数，不能称调度收益。

若允许全四核一次外存读的跨 cluster multicast，则 C2N、C2K 的 X 读都能为 `B_X`；这是更强且不同的网络合同，不能与“仅 cluster 内 multicast”混用。若比较 direct peer，则 C2K 外存少32,768 B，但 peer 链路增加16,384 B，source/destination VMEM 端口、链路容量、buffer、credit 和完成事件另列。缺乏链路实现时可以把它留作未纳入比较的路线，不能将 staging 删除后称免费加速。[R8 路由与公平性边界](D:/dsh-proj/SchedResarch/r8/hierarchy_static_audit.md:36)

同一 cold invocation 的 full-resident payload live-set 下界：C1N 每核1,777,664 B；C2N 每核1,183,744 B；C2K source 每核892,928 B、receiver 每核901,120 B。它们不含保留区、descriptor、额外双缓冲或 transport。因此参数冻结后还需每核逐 span 核验；四核总容量富余不能救某一 private VMEM 超限。跨 invocation 常驻需要另立初始状态，不能少计此次冷载。[R8 分配边界](D:/dsh-proj/SchedResarch/r8/redteam_report.md:28)

## 4. R：必须由参考硬件合同自己负责的选择

以下没有本轮已核验的目标来源；即使采用历史相同数值，也应写“研究选择，受 H 启发”：

- 两 cluster、每 cluster 两核；MXU 几何、有效 MAC/cycle、启动/排空开销，VPU reduction rate。
- private VMEM 容量/保留区、端口峰值、bank 是否显式；若不建 bank 则不得报告 bank stall 预测。
- cluster DMA channel、队列、outstanding 上限与 credit 归还时点；全局外存总服务和读写/方向切换规则。
- X multicast、跨 cluster staging、地址布局/striding、resident/tile 读取方式、source capture 与目标可见性。
- request/burst 粒度、padding、descriptor 传递和 issue 成本；无模型项必须明确抽象掉，不能一边声称完整 bus bytes 一边省略。
- 背景强度/周期/相位分布以及 service 规则；参数敏感性表必须在主 test 结果前选定，且包括至少两个非极端干扰。

将这些数字集中在单一参考合同，再从合同派生 request 与资源成本。允许专项敏感性覆盖各假设，不要求搭建通用平台。默认保留已有 work-conserving DMA 仲裁；若问题只在全局队头阻塞的弱基线出现，不能据此提出新 scheduler。[R8 strong-static 公平性](D:/dsh-proj/SchedResarch/r8/hierarchy_static_audit.md:58)、[R9 实施授权](D:/dsh-proj/SchedResarch/r9/continuation_brief.md:27)

## 5. D：共享外存下界能排除什么

考虑固定 mapping/bytes 的一次执行。从 `t=0` 到最终 Y visible，设强静态实际结束为 `T_S`，任何同合同合法零成本干预的结束为 `T_A`。令 `c(t)` 是**与 policy 无关**、所有前景请求都已准备就绪时每时刻最多可获的共享外存 payload 服务率，`A(t)=integral_0^t c(u)du`。如每次执行必须服务至少 B bytes，则

```text
L_bytes = inf { t : A(t) >= B }
T_A >= L_bytes
gain(A,S) = 1 - T_A/T_S <= 1 - L_bytes/T_S.
```

**证明：**任一合法执行到时间 t 获得的服务不超过潜在服务 A(t)；完成必须交付 B bytes。允许所有请求在0时刻 ready 仅放松依赖/容量，因此形成下界；实际计算/最后 store 的等待可能使可实现最优更慢。若 `1-L_bytes/T_S < 5%`，则该合同的任意仅重排、且不新增带宽/减少 bytes 的零成本动作都无法达5%，收费动作更不能。等价检查是 `T_S < L_bytes/0.95`。可再取 `L=max(L_bytes,L_compute,L_dependency,...)`，但每个额外下界必须单独证明有效，不能把可重叠的 compute 和 memory 需求简单相加。

这一区间是**恢复空间的上界**，不是已经恢复的收益，也不是实际剩余损失。若下界 gap 大于5%，只能保留未决；不能据此证明有合法动作、因果可观测信息或可实现机制。若所有请求有时无法供给，外存实际 active 很高仍可能存在最后一段可优化尾部；必须计算整个最终完成差额，不能靠平均 utilization 宣告关闭。

### 固定背景过程与内生排队的陷阱

预登记的绝对时间背景 **到达过程** 可以跨 policy 共用；由其与前景竞争产生的延迟、已完成背景 bytes 和前景服务空隙通常是内生的。不能把 selected-static 的 observed service trace 当另一 policy 的 `c(t)`，也不能把其背景 completion trace固定后推出“不可恢复”下界。

若参考合同直接规定独立的背景保留时隙/前景可用带宽日历，`c(t)` 可直接来自该外生日历。若实现真实背景 request 和共同仲裁，则应单独构造“前景自0起始终 backlogged”的放松，并证明它给出的累计服务上限支配所有准许动作；固定背景优先级/配额有时能简化证明。若支配性无法证明，退回更弱但安全的物理最大带宽下界 `B/R_max`。背景 arrival 固定并不自动让 observed foreground service 固定。[共同过程约束](D:/dsh-proj/SchedResarch/r5/measurement_gate.md:49)

### mapping、统计与有限类限定

- 同一 selected-static 的单动作重排可使用其必需 B；允许改变 mapping/multicast 的更大类必须对所有许可方案取有效下界的最小值，不能用 C2N 较大字节数限制 C2K。
- 逐 pair 的百分比改善上界是 `u_i=1-L_i/T_Si`；若报告平均逐 pair 百分比，就比较 `mean(u_i)`。若主指标是均值 elapsed 比，则上界为 `1-sum(L_i)/sum(T_Si)`。这两种统计量不可混用。
- 在有限相位分布全枚举时可报告精确期望；抽样相位应报告估计与独立模型 session。30个 paired blocks 是30次独立运行过程，不能把一条 trace 的 requests 当30个独立样本。
- tiny exact 仅认证被枚举的固定资源、动作、依赖和相位类。它用于暴露事件语义/仲裁偏差或静态 gap，不证明完整 Qwen 切片全静态最优。

这些方法边界沿用 [最小合同的 baseline 定义](D:/dsh-proj/SchedResarch/analysis/compiler_contract_requirements.md:165) 与 [测量/归因门](D:/dsh-proj/SchedResarch/r5/measurement_gate.md:65)，本节公式与证明为本次独立推导。

## 6. 最有判别力的预登记实验与红队风险

建议将本轮1–3个未解问题写成以下可分别关闭的对象，而不以正收益为成功条件：

| Research Question | Hypothesis | Strong baseline | Discriminative result / 决定 |
| --- | --- | --- | --- |
| 干扰后的损失是否主要为必需供给？ | 给定合法静态和共同外存，强静态已经逼近不可避免服务需求。 | 同一 selected-static 在 quiet/两个干扰下，完整 requests、容量和 Y-visible endpoint。 | 有效下界将恢复上限压到5%以下则关闭具名重排候选；大 gap 仅 Refine。 |
| 映射/tiling/预取是否解释剩余差异？ | C2K输入复用、tile 重叠或驻留已能解释弱静态损失。 | 独立 train/validation 选择的 mapping、multicast/unicast、full/tiled residency、单/双buffer、outstanding、固定顺序；既有仲裁共同保留。 | 报告新增静态相对原 selected-static 消除量，若已足够则转 compiler/static 结论。 |
| 固定合同中还有影响最终结束的动作吗？ | 可观察的 ready/credit 状态允许一项合法动作减少尾部。 | 先计算有效恢复上界，再执行有界单动作反事实，保持地址、bytes、能力与绝对时间背景。 | oracle 无恢复或收费收益不足则 Reject；oracle 有恢复而因果策略无效则 Refine observability；只有收费因果动作过模型门才继续。 |

关键伪阳性入口：

1. **起终点变化：**给 N-shard 加必需 gather、给 split-K 免费 K-partition 初始驻留，或在 source last-read 时提前宣布 Y 完成。
2. **多播不收费：**外存少读被正确记录，但 DMA/VMEM delivery 被少写，或隐藏一个无限 multicast return buffer。
3. **漏掉真实工作：**tile 程序只计一个 prototype tile、K4608 尾块漏算、padding不计、full-resident凭总片上容量许可。
4. **last-reader错绑：**双buffer复用在 DMA accepted/compute issued 时释放，或 remote staging scratch 被尚未读取的下一次写覆盖；数据 ready 必须绑定完整目标 span/generation。
5. **选择偏差：**test上调tile/priority/相位、按policy抽task时长、筛除坏相位，或把未来 service 信息当在线观测。
6. **弱静态制造机制：**强制所有 requests 串行/队头阻塞，却让候选调用现有 work-conserving 仲裁。
7. **下界用错：**selected-static 的实际延迟 trace 被当作不可避免服务，或将多个可重叠等待之和称端到端残差。
8. **证据越界：**模型参数筛查过门被称 TARS 收益、sim session 被称实机复验、有限 buffer/event bits 被称 PPA。

审查应保存失败 fixture、每个请求 accepted/source-last-read/destination-visible、全部 reader 释放、资源容量峰值、外存分项 bytes，以及最终所有 Y spans 的可见完成。R8 的单 sentinel 70序证明不能替代这些新执行审计。[R8 红队未覆盖清单](D:/dsh-proj/SchedResarch/r8/redteam_report.md:64)

## 7. 本审计决定

**Accept**：冻结官方源支持该 down 子问题；上述共同边界下 bytes/MAC/live-set 算术；有明确前提的共享服务恢复上界。**Refine**：由 R9 单一规格落实数值/硬件/背景合同，将全部 tile 和 payload 链展开为可审计执行。**Reject**：以真实 TARS 缺失再次停止授权建模，以及以本轮参考模型结果宣称当前 TARS、硅后收益或 PPA。

本文件完成来源与实验设计独立审查；主实现/结果和最终红队由对应 R9 工件另外认证。未修改 R1–R8、根 README、根表或任何旧 manifest。

## 8. 新写入参考合同与事前计划的具体复核

主代理随后提供了 [reference_hardware.json](D:/dsh-proj/SchedResarch/r9/reference_hardware.json:1) 和 [experiment_plan.md](D:/dsh-proj/SchedResarch/r9/experiment_plan.md:1)。本节审查其当前设计；不认证随后实现与最终冻结版本。

**已支持的设计选择：**合同标明 reference cycles、无 GHz/实机时间声称；32×32理想1024 MAC/cycle、4 MiB/核减64 KiB保留区明确区分历史启发与研究选择。全局 EXT64 B/cycle 与每 cluster DMA64 B/cycle 是独立资源，增加第二 cluster 不复制 EXT。仅 cluster 内 multicast 对 DMA 收两份 payload 并保留两个目标的 credit；只有 external staging 路径，写和读共同占 EXT。两种 FP32 算法由本轮主动许可，并明确不主张 bitwise/模型质量。source-row/gather 都从同一原始外存 layout 起点枚举 span，未免费 prepack。每条 Y store 的外存 visibility 是共同结束点。

**供给下界适用：**计划采用绝对时间外存预留日历，背景不建立请求队列；因此前景可用率是独立 `c(t)`，本审计第5节证明可以直接适用。必须继续称“固定带宽预留模型”：它故意不涵盖前景改变背景排队/服务的反馈，不能把这种抽象当完整真实 DRAM 干扰。

**运行前需要准确落实的细节，已反馈主代理：**

- 背景区间在 phase 接近周期末时的 wrap 定义，以及 `0.20*8192=1638.4`、`0.35*8192=2867.2` cycle 的连续时间或整cycle rounding规则，应由一个实现权威决定并保存；不能在下界和引擎分别取不同整。
- `C2K K=4608, Ktile=1024` 的真实 tile 长度必须为 `1024,1024,1024,1024,512`；tail512仍满足32倍数几何。所有请求、MAC、startup和buffer复用按实际tile枚举。
- source-last-read 放行源复用、destination-visible 放行消费者、所有 compute/DMA reader 最后读取放行目标槽复用，三者应在实际审计中分别检查。只检查 compute readers 的 alias 规则不足以保护尚未 source-capture 的异步输出 store。
- `core_operand_bytes_per_cycle` 是独立理想端口模型；每个tile的具体 operand 读取次数/阵列内复用假设需固定，不能将唯一tensor尺寸称物理SRAM访问实测量。当前合同不含bank/cache/refresh/retry，相关性能预测应保持排除。

**静态候选与下界命名：**计划的有限池覆盖 C2N/C2K、输入方式、Ktile/full、full-X驻留、1/2槽、预取、X/W顺序、core次序、gather/row和outstanding，但这仍不是全部合法编译计划。应保留三个不同对象：

1. **固定 selected-static 合同的下界：**以该mapping/有效bytes和资源预算限制同合同单动作选序；这是本轮“额外 DMA 选序”关闭门最直接的证据。
2. **枚举候选池的共同下界：**对池中每个计划的有效下界取最小；只约束这一个池。train筛选/validation择优没有穷举次序时，其选择器仍不是全静态最优。
3. **全部已准许 mapping/traffic 的共同下界：**需要独立证明允许的重用/路由/分片方式中最低必需bytes，不能仅因对有限池取了最小就改称全局。如果证据只能支持固定mapping或池范围，应直接保留较窄名称。

主参考四核 C2K multicast 的理论外存 payload 为2,998,272 B；这可以成为当前两种具名分片、当前冷起点、当前staging/广播合同的字节下界候选。是否是所有已准许静态操作的共同最低需求，须核验准许集合确实没有额外的分片、跨cluster输入复制路径或不同归约位置；本文件不以一个数字代替此证明。

**阶段结论：Accept 本次设计收敛，可进入实现。** 既定两个非极端预留强度、两组各30独立paired blocks、独立train/validation/test、单参数敏感性及收费8 cycle都写入事前计划。其信息量足以关闭具体参考主条件的选序候选；若敏感性出现较大下界gap，按计划应标未决，不能借主条件负结果外推关闭。
