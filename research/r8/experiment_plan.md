# R8 事前登记：先验 mapping 与跨 cluster payload/completion 合同

日期：2026-09-05。登记在本轮实验执行之前。证据等级：**来源约束的账本、CPU 数值 fixture、有限偏序穷举；未校准、非目标实现、非性能实验**。不新增时序 simulator，不提出新 scheduler，不运行 Phoenix。

## 两个未解决问题与假设

1. **Q1：跨 cluster 归约搬运是否由工作量本身强制，还是随合法静态 mapping 改变？** H1：同一 full-K down-projection 输出切片存在不跨 cluster 归约的 output-sharding；K-sharding 的收益/损失取决于 activation 复制、传输路径及数值许可，不能从“有跨域依赖”推出调度残差。
2. **Q2：共享 DMA 的“完成”足以使远端 consumer 读数据并复用源 buffer 吗？** H2：command accepted、source last-read、destination visible、consumer last-read 是不同边界；将 signal 绑定到过早阶段会允许错误执行。精确静态 wait/release 边足以使本轮有限合同安全；这不要求新增 ready scheduler。

已有证据：R1 历史单 cluster 两核、core-private VMEM、cluster DMA/Controller；多 cluster deferred。R3 没有逐 tensor bytes 和独立 remote-visible 阶段。官方冻结 Qwen MLP down 为 I=9216→H=2560，无 bias；R5 down 输出 N128 的权重为 2,359,296 B。当前 TARS checkout、跨 cluster 数据路径、broadcast、target 数值 admission 均未知。

## 固定工作与范围

- 冻结源：`r4/sources/qwen/config.json` 与 `modeling_qwen3_5.py`，hash 与 `r5/full_width_specs.json` 对照。官方版本不升级。
- `X[M,9216] × W[9216,128] → Y[M,128]`，M∈{1,32}；选择真实 down 的输出轴 [0,128)。输入是**prepared down input**，BF16 X/W，FP32 累加/输出；不执行上游 gate/up、down 剩余输出、norm/residual 或 autoregressive loop。FP32 输出和分组归约是研究合同，不能冒充官方 BF16 kernel 逐 bit 等价。
- 冷数据边界：X/W 初始在共同外部存储，结束时 Y 在外部可见。权重每 slice 只读一次；descriptor、padding、协议包头和运行时实际 traffic 尚未知，单列为未计量项。片段间权重驻留未验证。
- C1N 控制：1 cluster×2 core，每核 N64/full K。C2N：2 cluster×2 core，每核 N32/full K。C2K：cluster 各 K4608，每核 N64，cluster1 FP32 partial 向 cluster0 相应 core 归约，固定 `P0+P1` 次序。
- C1N 仅是局部控制，不能与四核配置称同算力性能比较。C2N/C2K 总算术 MAC、权重、4 个 core、每 core 研究 VMEM 上限及整体 DMA/链路预算相同；分别账列 activation 复制、partial bytes 和 reduction adds，不偷换工作量相等为总算术成本相等。
- 研究容量上限 4 MiB/core 来自历史锚点，**不是当前可用容量认证**。分别列 full-resident 与 Ktile∈{128,512}、1/2 buffer 的静态 live set，不推断 target 已支持、最佳时序或跨层驻留。只用字节对齐布局；target bank mapping、保留区、实际 tile admission 待核验。

## Strong-static baseline 与公平比较

首先允许改变 output/K mapping，固定归约许可，再比较同 mapping 的静态合同。private VMEM delivery 账本采用每个 core 收到自己输入的单播；另给理想 multicast 的共同外存下界，**不混入同一次策略对比**。C2K direct peer route 与 external-staging route 单列互斥合同：后者增加 partial 的外存 write+read，不称免费远程链路。容量、通道数、频率、带宽、outstanding、bank/port 和协议开销全部保持 unknown，不赋造数值进行排名。

合法静态集合必须含明确的 destination-visible wait、source last-read release 和 destination consumer last-read release；若已有多队列/work-conserving DMA 仲裁支持，也属于 static 基线接口，不包装为新 task scheduler。无 target 入口不能声称 exhaustive strong-static 性能最优。

## 判别实验（冻结执行范围）

**E1 账本与数值：**为 3 mappings×2 M 生成逐 core 分片、传输、地址/live-set、严格依赖账本；验证完整 K×N 权重不漏不重、输出覆盖和两种 partial 路径的 bytes 守恒。用 seeds {8107,8119,8131} 均匀随机非零 BF16 X/W，CPU FP32 按 K 顺序逐项累加，C2N/C1N 保持此顺序，C2K 两半各按序、再相加；float64 contraction 为误差参照，诊断容差 `abs_error <= 5e-5 + 5e-5*abs(reference)`，不作为生产 admission。保存每 fixture 的 input/weight/output hashes 与误差，不因 split-K 出现误差改容差。另放一个 BF16 大数抵消 fixture，显式检验 regrouping 不保证 bitwise 相同；失败是预期的数值许可边界，不删除。

**E2 有限事件穷举：**一个具名 partial payload（小整数 sentinel，单源单目的，不代表网络时序），事件 A=accepted、R=source last-read（将 payload 拷入 transport）、V=destination visible、E=consumer event、C=consumer last-read/数值读取、S=source overwrite、D=destination overwrite。物理次序 A<R<V；C 依赖 E；源/目的覆盖各只发生一次。分别枚举：safe (V<E<C, R<S, C<D)；early-event (A<E<C, R<S, C<D)；early-source-reuse (V<E<C, A<S, C<D)；early-destination-reuse (V<E<C, R<S, V<D)；conservative-source-release (V<E<C, V<S, C<D)。遍历各偏序全部线性扩展，执行数据状态而非只检查边；保存每个扩展与读数、错误 witness。对 safe 全部正确作接受，对每个故障出现至少一个错误作判别力验收。

E2 没有概率、时间单位或链路 credit，不计算错误率概率或性能收益。它证明被声明的抽象偏序足够/不足，**不是 TARS 有这些 bug**。conservative-source-release 只比较允许的顺序集合，不把更少顺序解释成延迟损失。当前不复用事件 ID，因此不引入 generation 机制；多代/重试另需合同。

## 停止门与下一决策

- shape/hash、覆盖、容量账、因果读取不一致：保留失败并修正实现，不能发布研究结论；事后改范围需另记 amendment。
- 若 C2N 不需 partial，而 C2K 只在特定路径/数值前提成立：**Accept 静态 mapping/资源合同先行；Refine 目标入口**。不能把 peer bytes 说成全工作量必需。
- 若 safe 全正确、early variants 有反例：**Accept 精确 completion/release 合同的结构必要性；Reject 单凭该证书提出动态调度/新硬件的推论**。不推导完成延迟分布或可恢复等待。
- 无真实 residual、strong-static 可比二进制、因果观测、有限动作及收费收益：停止扩展模拟器和 Phoenix SDK；交付具名缺失接口与下一最小取证动作。
- 后续性能确认仍需独立 train/validation/test，≥5% 净 elapsed、95% paired CI 下界>0、每条件每 session≥30独立 paired blocks、第二 session 新相位、至少两个非极端干扰、quiet 均值回退≤1%；本轮以上计数均为0。

完成后独立红队检查来源、数值许可、预算和归因；根进度表另加实际 R8 八字段行，保留交接计划行及 R1–R7。新父子关系记录在 `r8/history_lineage.json`；不改旧清单和 README。
