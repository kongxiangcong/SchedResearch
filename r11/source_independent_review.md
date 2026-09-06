# R11 独立来源、算术与生命周期复核

2026-09-05；研究来源审阅子任务。先完整读取 `continuation_brief.md` 与 `reporting_addendum.md`，并只读检查 R5/R6 与回溯文档。本文在 R11 性能结果之前形成，不读取或判断 R11 性能。`research` skill 的一手来源核验方式用于本独立子任务；未下载新来源，未执行官方模型、真实设备或 RTL。

## 1. 来源身份与证据边界

模型固定为 `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`，实现为 Transformers `f62dc9bf2c90353b442a56e74391fbb8c689b55e`。以下 SHA256 由本次直接读取文件重新计算，与 R6 冻结 manifest 相符；全部旧文件未修改。

| 冻结本地来源 | SHA256 |
| --- | --- |
| `r6/sources/qwen/config.json` | `ddc63e1c717afa86c865bb5e01313d89d72bb53b97ad4a8a03ba8510c0621670` |
| `r6/sources/qwen/modeling_qwen3_5.py` | `458360c8072e6130580639170ad3e645b975512dbabae31eab5f92de5f0f09ef` |
| `r6/sources/qwen/cache_utils.py` | `702144bb44553f6339ea1bf23c8205a708bb5f8c7c09cb3a2db484182646743c` |
| `r6/sources/qwen/generation_utils.py` | `84ec1a610091eea57ba0d5a672662054a22f0c2c7f6462f18cf5b3232f697594` |
| `r5/model.py` | `201c39b5073f7e1f4b7f0e3e6d269ea4cdcf32908bf9237db6e01ea011fd849a` |
| `r5/resident_control.py` | `b9d0c270730b99f57705ae536228e787ca1451b04c39f77ef0febbab1552192c` |
| `r5/resident_control_independent_audit.json` | `89974f16535e0583f77868b0edb71225f00b8ec7a534f551a516fcb973a59584` |
| `r6/source_evidence.md` | `2dca3f3dee78bfc2597397cb615f276c02726bdf13a8f4cf66d4ff46527046c6` |
| `r6/residency_audit.json` | `56fe0c05b0cf9471dd6fa6d455de48128a2c31b9da7b1d3cb9573ebdd3f43029` |

当前回溯的 R5 正信号范围描述正确：2 heads、4 个 prepared tokens、73,760 B/core；完整层与真实输入生命周期尚待 R11 验证。[回溯 L79–83](../analysis/r1_r10_research_retrospective.md#L79)。原报告四个条件的结果不能当作完整层基线。[R5 红队 L110–123](../r5/redteam_report.md#L110)

## 2. 完整形状与必须覆盖的数值合同

官方配置为 hidden=2560、key heads=16、value heads=32、Dk=Dv=128、conv width=4、32 个文本层，其中 24 个 linear-attention 层，state dtype 为 FP32。[config L16–70](../r6/sources/qwen/config.json#L16)

对 B=1，完整 recurrent state 是 `S[32,128,128]`，共有 524,288 个 FP32 元素、2,097,152 B。一 head 是 65,536 B。4-token 输出 `O[4,32,128]` 是 16,384 个 FP32 元素、65,536 B，最终 state 保持完整形状；不能以两个 head 的结果乘以 16 替代所有 head 的数值检查。相邻两个 value heads 使用同一个 q/k head，但有独立 state、v、beta、g。[形状与重复 L505–511、611–620](../r6/sources/qwen/modeling_qwen3_5.py#L505)

按源码，将已投影、卷积和激活后的 q/k 转 FP32 后作 L2 norm：`x / sqrt(sum(x*x)+1e-6)`，并把 q 额外除以 `sqrt(128)`。令 `q_t`、`k_t` 是此 prepared 值，`b_t=sigmoid(in_proj_b(x_t))`，`g_t=-exp(A_log)*softplus(in_proj_a(x_t)+dt_bias)`，每 head 的递推为：

```text
S_decay = exp(g_t) * S_previous
prediction[v] = sum_k S_decay[k,v] * k_t[k]
delta[v] = (v_t[v] - prediction[v]) * beta_t
S_new[k,v] = S_decay[k,v] + k_t[k] * delta[v]
o_t[v] = sum_k S_new[k,v] * q_t[k]
```

decay 必须先于 prediction，输出必须读更新后的 state；g 是 log decay，不能再把 exp(g) 当成 g 传一次。该语义可直接核验[官方递推 L450–495](../r6/sources/qwen/modeling_qwen3_5.py#L450)、[L2norm L290–295](../r6/sources/qwen/modeling_qwen3_5.py#L290)、[beta/g L615–620](../r6/sources/qwen/modeling_qwen3_5.py#L615)。将 reduction 中 D 个乘法、D−1 个加法以及 delta 的两个逐元素运算一起精确计算，不含 exp/norm/scale 时每 head/token 是 `7*128^2=114,688` add/multiply operations；完整 32 heads、4 tokens 是 14,680,064 operations。

所有测试至少应保留逐 token 输出和最终 state；额外保存每步 state 可帮助定位差错。独立 oracle 不应调用被测 recurrence 更新函数。可使用显式标量/向量递推与不同组织的矩阵形式交叉比较；有限精度容差需提前固定，固定 seed 且输入不可变、所有值 finite。随机数值验证只能证明这份来源合同及实现的数值一致性，不能宣称训练权重精度或官方 kernel 已执行。

## 3. “完整 GDN 单层”的边界不能含混

`Qwen3_5GatedDeltaNet` 完整模块从 hidden states 到 hidden-size 输出还包含 qkv、z、a、b 四份 projection；8192 channels 的 causal depthwise conv+SiLU；q/k norm、beta/g；gated RMSNorm 和 out projection。[构造 L518–545](../r6/sources/qwen/modeling_qwen3_5.py#L518)、[生产 L563–620](../r6/sources/qwen/modeling_qwen3_5.py#L563)、[消费 L650–661](../r6/sources/qwen/modeling_qwen3_5.py#L650)

| 组件 | 来源矩阵/公式 | 完整每 token 工作 |
| --- | --- | ---: |
| in_proj_qkv | 2560 × (2×16×128+32×128) | 20,971,520 MAC |
| in_proj_z | 2560 × (32×128) | 10,485,760 MAC |
| in_proj_b 与 in_proj_a | 两份 2560 × 32 | 163,840 MAC |
| out_proj | 4096 × 2560 | 10,485,760 MAC |
| dense projections 合计 | 42,106,880 权重元素 | 42,106,880 MAC/token |
| depthwise conv | 8192 channels × 4 taps | 32,768 MAC/token；边缘仍计 padding/既有 cache 合同 |

这些 dense 权重若 FP32 为 168,427,520 B，若 BF16 为 84,213,760 B；尚未包含 conv 权重、A/dt/norm 参数。此表是逻辑工作量，不是强制外存交通：同一已知 token block 可重用每个合法 weight tile，不能对每个 token 重载整个矩阵。所有生产、缓冲和消费成本若在性能模型外，只能称“完整 32-head recurrent core”，不能称整个 GDN 模块的最终 elapsed。若主指标要求完整模块，则必须实现或显式收费并核验这些共同组件、输入输出位置与 live ranges。层外 MLP/residual、32 层模型不属于此 GDN 模块。

源码 prefill 默认选择 chunk recurrence，而普通 cached seq_len=1 选择 recurrent recurrence。[dispatch L622–647](../r6/sources/qwen/modeling_qwen3_5.py#L622)。4-token 顺序 scan 是合法数学 lowering，但不能伪称已经运行来源的默认 chunk kernel；强基线比较的算法选择范围须明确。若使用 sequential recurrence 作为两边共同算术，应报告该范围，避免把更广义“最强 prefill kernel”当成已经证明。源码对 core output 回转输入 dtype，并在 gated norm 中有 FP32 与输入 dtype 的转换。[output cast L493–494](../r6/sources/qwen/modeling_qwen3_5.py#L493)、[gated norm L223–232](../r6/sources/qwen/modeling_qwen3_5.py#L223)。FP32 全模块 reference 最易避免未说明的 BF16 rounding，但必须明确 FP32 projection 吞吐是新参考假设，不能冒用 R5 的 hypothetical BF16 校准。

## 4. 合法已知 block 与严格 autoregressive 必须分开

**已知 4-token block：** 在本层前置所有层完成这个已知序列块后，`hidden_states[1,4,2560]` 是合法本层输入；qkv/z/a/b projections 针对全部 seq_len，causal conv 只用当前及过去的 projection，不依赖未来未知 token。可以先完成共同生产，再将 4-token prepared payload 缓存在 SRAM，按 head wave 逐 token 更新完整 32 heads。这不需要同时在 RF 中容纳全层 state，但生产所需 hidden inputs、权重 tiles、conv cache、z、prepared payload、输出和相关读写必须收费。[projection 与 conv L557–598](../r6/sources/qwen/modeling_qwen3_5.py#L557)、[causal conv L247–287](../r6/sources/qwen/modeling_qwen3_5.py#L247)

**严格 autoregressive：** 同层 token t+1 的真实 hidden input 必须在 token t 完整模型前向、logits/token 选择以及下一 token 前置层之后才可释放。来源按 layer 顺序更新 hidden states，并在 generation 循环前向后采样/argmax，再追加 token。[层循环 L1286–1300](../r6/sources/qwen/modeling_qwen3_5.py#L1286)、[generation L3017–3073](../r6/sources/qwen/generation_utils.py#L3017)。禁止预置四个未来 prepared 输入，禁止把 arbitrary release gap 调成有利参数。可预登记依赖屏障：完成本 token 全模块输出和必要 cache 保存后离开本层；RF 由共同的后续/前置工作复用，下一合法输入到达时该层 RF state 无效。由此得到的关闭结论只适用于这个明确的 time-multiplexed RF 合同，不能证明真实目标绝无跨层保留区。

24 层 recurrent state 的 48 MiB 是来源逻辑容量，不推出 48 MiB 每 token 必须 DRAM 读写。框架 `mark_static_address` 只描述 tensor 地址/graph capture；不保证物理 RF 持久性。[cache L1025–1048](../r6/sources/qwen/cache_utils.py#L1025)。同样，RF clobber 是 R11 参考硬件/执行合同应明确声明的条件，不是官方 Python 源码自动证明的硬件事实。

## 5. 与 R5 一致的可行单一参考合同

最小可解释选择是沿用 R5 的两个 core、每 core 128 KiB RF、共享 4 MiB SRAM，保留 R5 请求模型的 granule=256 B、EXT=32 B/cycle、fabric=64 B/cycle、8 banks 合计 SRAM=128 B/cycle、external latency=64 cycles、outstanding=16、return slots=8、VPU=32 ops/cycle。以上全是研究参考值；既非 Phoenix/U85/Gemmini 配置，也未获得真实 TARS 校准。[R5 Hardware L53–75](../r5/model.py#L53)。不得将 R9 的 VMEM 数值未经说明加入。若 R11 简化 request 模型或增加 FP32 dense capability，必须集中列差异与不能逐项复现 R5 百分比的原因。

一个 4-token 完整 block 的直接容量证书：

| 逻辑对象 | FP32 bytes |
| --- | ---: |
| 32-head state，全放共享 SRAM | 2,097,152 |
| 全 32-head、4-token duplicated prepared q/k/v/beta/g | 197,632 |
| 4-token recurrence outputs | 65,536 |
| 每 core 一个 head state | 65,536 |
| 每 core 此 head 的 4-token prepared payload | 6,176 |
| 每 core 此 head 的 4-token recurrence outputs | 2,048 |
| 每 core 上述同时驻留合计 | 73,760 |

只需 16 个 two-head waves，所有 32 heads 均实际执行。这个最低证书只含 recurrence 数据；完整模块还须登记 conv cache、hidden/z/intermediate、output、weight staging 和 scratch。可用物理地址分区及实际 live ranges 保证 shared SRAM 峰值≤4 MiB，不能只把循环里的重复分配当成同一有效缓冲。prepared q/k duplicated 的计数是方便的上界，允许静态共享但两边相同。

R5 的 M=4 projection 双缓冲若每 core 两份 `[128,128]` BF16 weight tile、两份 `[4,128]` BF16 input tile、`[4,128]` FP32 accumulator，需 69,632 B/core。它与 73,760 B resident recurrence 同时存在时是 143,392 B，超过 128 KiB；因此不能宣称两者免费重叠。要么使用共同的分阶段 producer/recurrence/consumer，要么对两边同时调整 tile/buffer 并验证容量。FP32 projection buffer 更大，尤其须核验。[R5 projection allocation L90–137](../r5/model.py#L90)

相同 state 在 shared SRAM 起终、4 token 条件下：non-cross-token resident baseline 的 state SRAM↔RF 为 `2*4*32*65536=16,777,216 B`，head-wave 4-token resident 为 `2*32*65536=4,194,304 B`，减少 12,582,912 B。此差分是合法已知 block 的预期资格检查，不能直接转换为 elapsed 收益。若初始/最终在 EXT，两边相同 state EXT 起终总量为 4,194,304 B；必须分开记，不把本地节省称作 EXT 节省。

在严格 autoregressive 的每 token shared-SRAM 边界、RF 跨调用失效合同下，32 heads 每 token 均各 load/save 一次；4 token 两方案均为 16,777,216 B，因此该干预不产生 state-transfer 差分。可以先作解析资格关闭，不必大跑同一静态动作来伪装判别实验。该证明依赖明确的输出/释放/RF 复用边界，并非由全层 2 MiB 大于 RF 独自推出。

## 6. 红队检查项与可继续范围

需要拦截的实质错误：把 producer 之外的 prepared 输入当完整模块；按两个 heads 放大而不逐个计算 32 heads；prefill 顺序 scan 被称作官方 chunk kernel；baseline 被禁止共同合法 fusion/weight reuse；R5 BF16 假设冒充 FP32 实测吞吐；省略 producer/consumer 或 final cache visibility；同一 RF 双重占用；将 cache tensor 固定地址当持久寄存器；给 decode 提前未来输入；由 48 MiB 直接宣布 DRAM 必须流量；用 test 调 tile/相位以追正。

来源核验结论：合法已知 block 的 32-head 静态驻留具有真实可构造的本地交通差分，值得进入已预登记的性能判别；实际收益需要完整共同成本与独立模拟审计决定。严格 autoregressive 若采用上述显式 RF 复用边界，同一候选没有跨 token 动作资格，可以形成该范围的关闭证书。本文不预填最终性能判决，不支持新硬件或动态 scheduler，也不支持完整模型加速主张。
