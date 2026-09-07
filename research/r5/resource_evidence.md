# R5 真实来源片段与资源行为证据

核验日期：2026-09-05。此文只建立可复现来源、形状和判别实验边界；没有运行设备、完整模型或新 R5 性能实验。继承 R4 冻结模型而非追逐最新版。所有文件逐项 SHA256 及访问失败在 [`sources/resource_source_manifest.json`](sources/resource_source_manifest.json)；数值公式在 [`sources/fullwidth_shape_manifest.json`](sources/fullwidth_shape_manifest.json)。

## 1. 可以实际构造的全宽代表片段

“全宽”仅指保留真实 reduction K、head dimension 或 recurrent state dimension；选少量输出 tiles/heads 不等于完整层、完整 4B 模型或真实模型质量。BF16 按 2 B、FP32 按 4 B；不假设 INT4 量化，不把参数数当显存占用。

### Qwen3.5-4B

冻结模型 `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`，Transformers `f62dc9bf2c90353b442a56e74391fbb8c689b55e`，文本 H=2560、FFN I=9216、GQA Q=16/KV=4/head=256，GatedDeltaNet key-head=16/value-head=32/keydim=valuedim=128。此结构是三次 GDN 加一次 gated GQA 的重复，不能替换为标准 attention。[冻结官方配置](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/config.json)

对于一个 cached token，源码 recurrent core 使用 FP32，state 为 `S[batch, value_heads, 128, 128]`。一个完整 head 为 65,536 B（64 KiB），两个为 128 KiB，全层 32 heads 为 2 MiB。相邻两个 value heads 共享 repeat-interleave 后的同一个 q/k head，但拥有不同 state、value、beta、decay。core 每步执行 `S'=exp(g)S; delta=(v-k^T S')beta; S_new=S'+k delta^T; o=q^T S_new`；按 scalar add/multiply 计，不含 exp、q/k L2norm、query scale 与外层操作，恰为 `7*128*128=114688` operations/head/token。可保留随机非零 S 与完整 128 维来核对分块实现。[官方 recurrent 与调用源码 L436–659](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L436)

State 是 live-in/live-out；若驻留本地 SRAM，不能强制每 token 从 DRAM 重新读取。只有确定 spill 的情况下，state 外存读写下界才是 128 KiB/head/token。source 逐算子实现可能多次访问中间 state，strong static 必须允许 fused recurrence 和分块寄存器复用；不同实现的 SRAM pass 数应显式计量，不能套用源码临时张量个数作为最低交通量。两个 heads 的 core 是 source-derived slice，若不执行 conv、a/b/z projection、gated RMSNorm 与输出 projection，应明确这些是外部已生成 inputs/consumers，不能称整个 GDN block。

| Projection 片段 | 真实 reduction K | 输出 tile N | BF16 权重 bytes | M 个 token 的矩阵乘 MAC |
|---|---:|---:|---:|---:|
| FFN gate 或 up | 2560 | 128 | 655,360（640 KiB） | M×2560×128 |
| GQA q+gate、k、v 的输出 slice | 2560 | 128 | 655,360 | M×2560×128 |
| GQA o projection | 4096 | 128 | 1,048,576（1 MiB） | M×4096×128 |
| FFN down | 9216 | 128 | 2,359,296（2.25 MiB） | M×9216×128 |

FFN 应计算 `SiLU(xW_gate^T) * xW_up^T`，两份 640 KiB tile 共 1.25 MiB；这是真实 gated FFN 输入输出 slice，未含 down 完整 fan-in。GQA q projection 输出另含同宽 sigmoid gate；N128 slice 小于256维完整 head，只能验证 projection 数据流，不独自验证 attention。完整 GQA attention 子问题至少还需完整 q/k head、部分 RoPE（rotary fraction 0.25）、KV live-in/live-out 和 output gating。矩阵权重 shape 由 R4 tensor headers 与源码共同核对。[官方 MLP/GQA 源码](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L747)

### FLUX.2-klein-4B

冻结 `black-forest-labs/FLUX.2-klein-4B@e7b7dc27f91deacad38e78976d1f2b499d76a294`，BFL `flux2@50fe5162777813d869182b139e83b10743caef15`。H=3072、24 heads×128、MLP I=9216、5双流+20单流。distilled 主路径沿用 R4 的 CFG=1，无 unconditional 分支；选择 full-K FFN/projection tile 不构造额外 CFG 并行性。[官方配置](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/e7b7dc27f91deacad38e78976d1f2b499d76a294/transformer/config.json)

| Projection 片段 | K | N tile | BF16 weight bytes | 语义边界 |
|---|---:|---:|---:|---|
| double FFN gate/up、single linear1 slices | 3072 | 128 | 786,432（768 KiB）/份 | gate/up两份1.5 MiB；MAC=MKN/份 |
| double FFN down | 9216 | 128 | 2,359,296（2.25 MiB） | 需要完整 I 输入 |
| single linear2 | 12288 | 128 | 3,145,728（3 MiB） | 实际拼接 attention H 与 MLP I |

源码 `SiLUActivation` 将输入分成 x1/x2，再做 `SiLU(x1)*x2`。single `linear1` 将 qkv 和两路 MLP 打包，不能把所有 projections 独立 DMA、独立 norm 而限制 static fusion。已给定 conditioning 后，norm/modulation 可融合或驻留；若不执行 time/conditioning producers，应明确边界。研究用 M=1/16/64 是 token tile 敏感性，不代表某个固定分辨率的完整 denoise iteration。[官方 BFL model.py L390–566](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/model.py#L390)

**共同 accounting 约束（本研究推导）：**每次 full-K tile 权重只传一次；K 分块总 bytes 必须等于 `dtype_bytes*K*N`，禁止每个 partial task 重载整个矩阵。强静态可 K-tiling、gate/up packing、double buffering、activation reuse 和合法地址安排；两 policy 固定同一 traffic、容量、mapping 与融合边界。FLOPs 若用 MAC=2ops 必须标明，不能混作硬件实际每周期吞吐。循环内驻留与跨迭代 cache reuse 分开报告。

## 2. 公开资源事实与不能据此推出的结论

| 证据 | 可确认事实 | 无法由该证据定量确认 |
|---|---|---|
| Arm CMSIS-Ethos-U `79d0fcc...` README L150–194 | U85 SRAM 每 port 上限读12/写16；EXT 随配置读32或64/写32；SRAM/EXT port 数随 MAC 配置变化，软件设定 port/region | 目标机器实际启用值、内部bank数、平均延迟、共享背景流量、BF16支持 |
| Arm U85 TRM r0p0 Issue05 pp24–26、64–71、115–116 | 集成能力与软件限制共同约束 outstanding；128-bit AXI、可配置 port striping；weight read buffer 可接受 OoO arrivals；PMU 可区分 request stall、limit stall、AXI latency buckets 与 MAC active | 各 stall 的真实占比、是否 critical path、哪个 scheduler 能恢复、面积/功耗 |
| Gemmini `8c3f992...` README、Configs.scala、Scratchpad.scala、DMA.scala | 示例有 banked scratchpad、load/store/execute queues、有限 DMA transaction IDs、bank及回传ready握手；默认配置4个single-port scratchpad banks、128-bit DMA、64B最大transaction | 不是通用NPU规格，也不是用户目标设备实值；INT8默认吞吐不能用于BF16/FP32校准 |

来源：[CMSIS 冻结 README](https://github.com/ARM-software/CMSIS-Ethos-U/blob/79d0fccfe59cab7fd0cab97c65050d2824c5269f/source/README.md#L150)、[Arm TRM（本地冻结PDF带hash）](https://documentation-service.arm.com/static/67b5ba01ce2747241fce860f)、[Gemmini 配置](https://github.com/ucb-bar/gemmini/blob/8c3f9923a44a2fe2c7930587be297d6d4f8c09ca/src/main/scala/gemmini/Configs.scala#L44)、[scratchpad ready](https://github.com/ucb-bar/gemmini/blob/8c3f9923a44a2fe2c7930587be297d6d4f8c09ca/src/main/scala/gemmini/Scratchpad.scala#L126)、[DMA transaction IDs/backpressure](https://github.com/ucb-bar/gemmini/blob/8c3f9923a44a2fe2c7930587be297d6d4f8c09ca/src/main/scala/gemmini/DMA.scala#L396)。

U85 TRM 首章定位 TOSA/TFLite integer profiles，上述 BF16/FP32 图不是已经证明可在 U85 直接执行的模型。此处借鉴公开机制和测量分类；并未选定 U85 实现目标。bank 数、每bank带宽、credit数量、return FIFO深度、burst服务/背景到达过程，只要不是某个明确实例的实测或参数配置，均应标“研究假设”。

**尚不能量化：**真实 memory bank mapping/仲裁细则、NoC topology/路由/VC/credit深度、DVFS/thermal/DRAM refresh引起的时变服务、background traffic 的时间相关性、实际指令/状态成本。本轮公开证据不足以将任一因素认定为主要瓶颈；也没有证据保证这些效应提高 completion-ready 收益。系统仲裁本身已有动态响应，不等于需要新增 task scheduler。

## 3. 最有判别力的两个实验（建议，尚非结果）

### E1：同一 traffic 的资源细化消融

**问题：**R4 的 task-atomic 抽象是否隐藏了足够大的资源等待，而且这些等待是可恢复的？使用上述一个2-head state core及一个全K gated FFN tile，控制两者的spill/resident选择，跑：L0 task-atomic；L1 burst/byte service；L2固定总带宽的bank routing与有限outstanding/return FIFO。每种层级重新优化 strong static 的顺序、预取距离、Ktile、地址bank安排；同一层内各policy保持相同容量/traffic/mapping。compute默认确定性。先做无外生扰动；再引入事先冻结、独立train/validation/test、与task编号无关的时间相关外部服务流，保持每个seed的共同外生样本。不得因增加bank数顺带放大总memory带宽。

**判别：**若细化显著增加 E2E loss，但bank-aware static可消除，则归入 compiler/布局问题；若损失只随总bytes/BW增加且合法提前任务无critical-path反事实收益，则支持当前ready机制弱；若正确静态训练后仍有稳定残差，且受硬件可观测的实时队列/服务状态预测，才保留具体uncertainty。不能把新模型造成的所有latency增长都叫runtime opportunity：L0/L2基准服务定义不同，应把同L2 deterministic/no-background参考、realized-background损失、policy恢复分开。

**门槛：**事先冻结有意义的净收益阈值（可沿用R4 5%作为研究决策门槛，不称经济盈亏实值）；包括收费控制结果。只在通过时研究有限状态机制；否则淘汰本轮采样参数包络内该候选。报告单bank/credit饱和/return-FIFO满/无合法替代/关键依赖/compute busy的互斥墙钟分类，以及请求数/bytes守恒、completion inversion和少量paired intervention，不将task等待求和冒充wall time。

### E2：现实测量门槛或公开RTL反证

**问题：**E1出现的残差在真实机器是否存在，还是参数假设制造？最小设备测试是固定编译二进制/地址/输入，隔离与带受控背景内存流两条件，固定频率后采集端到端elapsed cycles、memory bytes、outstanding-limit stalls、request stalls、return latency histogram和MAC active；重复多次并保存背景相位。增加静态prefetch/地址优化并重复。设备不可用时，固定Gemmini RTL配置对地址冲突/credit saturation微测试，只能校验模拟器规则与该RTL一致，不能校准Qwen/FLUX端侧性能。

**判别：**如果真实测量没有明显runtime残差，或strong static可稳定解决，拒绝新scheduler proposal；若残差存在但只影响特定资源，则下一问题改为该具体瓶颈的最小观测与干预。E1不能独自区分“真实机器无机会”与“本轮未采样到真实参数”，E2才可推进外部有效性。没有设备或RTL实测，不声称 realistic accepted。

## 4. 来源失败、复现与证据等级

`python -X utf8 -B r5/sources/freeze_resource_evidence.py` 冻结/复核本地来源；`python -X utf8 -B r5/sources/derive_fullwidth_shapes.py` 生成全部shape/bytes/ops公式。GitHub API 的Gemmini HEAD请求受403 rate limit拒绝，随后 `git ls-remote HEAD` 成功冻结commit，再按SHA获取源码。web工具对Arm PDF的多个find请求均失败，已保存失败；直接PDF下载和PyMuPDF提取成功并定位页码，不能将搜索失败解释成文档不存在相关机制。

证据等级：模型结构和resource机制为primary-source verified；shape/byte/ops为source-derived；数值语义须由本轮随机小case另外验证；性能数值、RTL、设备、面积功耗均未在本子任务验证。原 R4 文件未修改，也未新写架构proposal。

### 后续证据更新（保留上述实验前记录）

当前 [`numerical_checks.json`](numerical_checks.json) 已记录3 seeds×3 source-derived cases、18项 FP32/BF16-rounded 数学比较通过；最大绝对误差 `1.7881393432617188e-7`。这验证随机来源片段的数学重排，不是官方权重质量、官方 kernel 或带地址的性能执行。[`source_contract_audit.json`](source_contract_audit.json) 独立认证其source/spec hash、全K/state shape、bytes/MAC与性能图一致，检查3个workloads×3个地址colors的SRAM alias依赖及RF槽生命周期；性能simulator仍不执行这些数值payload。

审计还发现一个需要检验的静态编译器控制：GDN声明的73,760 B/core RF预算可容纳state及4个token全部prepared输入/输出，原图逐token SRAM往返不由容量强制。因此另设 [`resident_control.py`](resident_control.py)，保留完整算术、初次state DMA及最终state/output liveout，只让state跨4步驻留RF，使用fresh train/validation/test、同class静态优化与原图比较。它是红队后的编译器控制，不能计入预注册的新架构正结果门槛。projection的MXU drain→SRAM→VPU read同样属于声明接口边界，源数学本身不强制这段交通。

该控制的最终 [`resident_control_results.json`](resident_control_results.json) 包含4配置、928次经过独立request审计的训练/validation/test执行；首heldout seed共24条完整trace含graph/plan/source hash。相同算术与外存初次载入、相同RF容量下，跨4步驻留使local SRAM traffic由1,048,576 B降至262,144 B；strong static延迟在none/ref-combined/o1-combined/r1-combined分别改善16.013%、24.027%、7.155%、11.853%。各配置resident B0均与resident S完全相同，B2均退化。此结果支持“固定lowering中有可由静态memory planning消除的交通”，没有支持新的动态scheduler。8个逐token输出向量与最终state合同显式关联已有数值oracle，仍没有timing simulator执行数值payload的证据。

实际autoregressive token之间会执行其他层，可能占用RF；这个微图假设全部4-token inputs已备好且其他层不占RF。因此上述驻留收益不能外推为实际完整模型decode收益。下一步若讨论编译器/硬件协同，需要先测实际RF可访问性、状态跨层生命周期和强编译器是否已经采用相应驻留；本结果不要求新增硬件。
