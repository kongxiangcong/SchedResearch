# R4 FLUX.2 官方模型与 lowering 证据

核验日期：2026-09-05。证据等级为**官方模型卡/配置/源码核验 + 缩尺随机权重数学检查**。没有下载大权重、运行完整 pipeline、测量模型质量或验收真实 NPU。本文按 research skill 使用原始来源；下载清单、原 URL、冻结 revision、字节数、SHA-256 和抓取时间在 `r4/sources/flux/source_manifest.json`。

## 选择与版本冻结

主 workload 选择 **FLUX.2 [klein] 4B distilled**。该官方公开版本正好属于用户指定的 4B 类，不需要虚构或截取 9B/32B 网络。Base 版本用于说明 CFG 语义，不混进主实验任务图。[官方 distilled 模型卡](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/e7b7dc27f91deacad38e78976d1f2b499d76a294/README.md)、[Base 模型卡](https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B/blob/a3b4f4849157f664bdbc776fd7453c2783562f4d/README.md)。

| 项目 | 冻结标识 | 用途 |
|---|---|---|
| HF 主模型/pipeline | `black-forest-labs/FLUX.2-klein-4B@e7b7dc27f91deacad38e78976d1f2b499d76a294` | 主选，step + guidance distilled |
| HF Base 对照 | `black-forest-labs/FLUX.2-klein-base-4B@a3b4f4849157f664bdbc776fd7453c2783562f4d` | 无 step/guidance 蒸馏 |
| BFL 官方实现 | `black-forest-labs/flux2@50fe5162777813d869182b139e83b10743caef15` | 数学公式的主来源 |
| Diffusers 实现 | `huggingface/diffusers@c5469b7ceb606edd7ba6570dcd17d38590a18db6` | pipeline/CFG 调用差异核对 |
| ARM 驱动参照 | `ARM-software/CMSIS-Ethos-U@79d0fccfe59cab7fd0cab97c65050d2824c5269f` | 硬件参数量级参照 |

两套 4B 模型权重均 Apache-2.0；代码仓库 `LICENSE.md` 和两套模型 `LICENSE.md` 已下载并分别 hash。不能将其推广为 FLUX.2 全系列许可；官方 9B 与 dev 行使用不同条款。[冻结官方 README 模型表](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/README.md)、[4B 许可](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/e7b7dc27f91deacad38e78976d1f2b499d76a294/LICENSE.md)。

技术依据是上述源码/配置及 [BFL Klein 技术介绍](https://bfl.ai/blog/flux2-klein-towards-interactive-visual-intelligence)。本轮不引用未经取得的训练技术报告，不从市场性能表推导 NPU cycle。

## 结构、参数与内存范围

冻结的 `transformer/config.json` 对应 `Flux2Transformer2DModel`；BFL `Klein4BParams` 给出相同结构：hidden 3072、24 heads、head dimension 128、5 double-stream blocks、20 single-stream blocks、MLP ratio 3、image input 128、context input 7680、4 个 RoPE axis 各 32 维、theta 2000、无 guidance embedding。它是 rectified-flow transformer，不能用“标准顺序 attention→FFN DiT block”统一替代双流/单流的实际计算。[配置](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/e7b7dc27f91deacad38e78976d1f2b499d76a294/transformer/config.json)、[BFL 参数与模块](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/model.py#L36-L113)。

| 组成 | 可复现参数数 | 证据 |
|---|---:|---|
| 生成主 transformer | 3,875,544,576 | 按源码矩阵尺寸求和，等于冻结 HF API `safetensors.total` |
| Qwen3-4B text encoder | 4,022,468,096 | 配置公式等于官方 sharded index `total_parameters`；tied embedding 仅计一次 |
| VAE | 84,046,115 trainable | 按官方 `autoencoder.py` 的 Conv/GroupNorm/Resnet 构造公式求和，未读取 weight/header；另有 257 个非参数 BN buffer 元素 |
| 全 pipeline trainable 合计 | 7,982,058,787 | 前三项的算术和；不表示同时驻留 |

复现：`python -X utf8 -B r4/sources/flux/parameter_audit.py`；输出 `parameter_counts.json`。主网络和文本编码器的两个独立计数通过断言。[文本编码器 index](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/e7b7dc27f91deacad38e78976d1f2b499d76a294/text_encoder/model.safetensors.index.json)、[文本配置](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/e7b7dc27f91deacad38e78976d1f2b499d76a294/text_encoder/config.json)、[VAE 配置](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/e7b7dc27f91deacad38e78976d1f2b499d76a294/vae/config.json)、[VAE 实现](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/autoencoder.py)。

主网络 BF16 **weight-only** 大小为 7,751,089,152 bytes（约 7.22 GiB）；它不是 4 GB，也不等于运行显存。主网络加 BF16 文本权重已达 15,796,025,344 bytes，此外还有 VAE、activation、attention scratch、缓存、allocator 开销。offload、量化与阶段驻留能改变峰值；这里未测量峰值。以上 byte 量是参数数乘 2 的推导。

HF pipeline 的文本编码器配置/index 为 BF16；BFL 参考加载器则选择 `Qwen/Qwen3-4B-FP8`。因此不能把 BFL 默认路径、HF BF16 pipeline 和 hypothetical 全 BF16 权重相加后称为同一种实测部署。VAE 配置还声明 `force_upcast=true`。[BFL text loader](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/text_encoder.py#L366-L436)、[HF VAE 配置](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/e7b7dc27f91deacad38e78976d1f2b499d76a294/vae/config.json)。

## Conditioning、CFG 与状态

Klein4B 的 text encoder 是 **Qwen3-4B**，与本项目另一个 workload Qwen3.5 无关。参考实现以 max length 512 编码 prompt，`enable_thinking=False`，`use_cache=False`，取 hidden states 9、18、27 后沿通道拼接：`[B,512,3*2560] = [B,512,7680]`。编码结果可供多个 denoising step 使用。BFL loader 没有在调用中 pin 外部 FP8 repo；本研究选择的 HF pipeline 把文本配置和 index 冻结在同一个 pipeline revision，不声称验证了外部 FP8 权重。[文本源码](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/text_encoder.py#L366-L436)。

`timestep_embedding(t,256)` 对 `1000*t` 做 sin/cos；两层 SiLU MLP 得到 vec。`SiLU(vec)` 经过 image/text 各 `H→6H` modulation，分成两组 `(shift,scale,gate)`；single modulation 为 `H→3H`。这些 modulation 在同类全部 blocks 间共享计算，不能每 block 额外创造一套权重或 conditioning 计算。实际 `guidance_embeds=false`。[模型 forward](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/model.py#L115-L166)、[modulation](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/model.py#L400-L413)。

| 路径 | 实际 denoise 执行 |
|---|---|
| 4B distilled 主选 | BFL 默认固定 4 steps、guidance 1.0；每步一次 batch B conditional transformer；无运行时 unconditional CFG 分支 |
| 4B Base / BFL | 默认 50 steps、guidance 4；每步将 uncond/cond 合并为 batch 2B，**一次** model call，再 `p=p_u+g*(p_c-p_u)` |
| 4B Base / Diffusers | `guidance_scale>1 && !is_distilled` 时每步 conditional、negative 两次 transformer call，随后同一 CFG 公式 |

这两种 Base 调用数差异是实现选择；不能凭数学上存在两分支就推断硬件可并行免费执行。主图没有人为复制 CFG 分支。[BFL variant defaults](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/util.py#L15-L75)、[BFL denoise/CFG](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/sampling.py#L269-L411)、[Diffusers CFG](https://github.com/huggingface/diffusers/blob/c5469b7ceb606edd7ba6570dcd17d38590a18db6/src/diffusers/pipelines/flux2/pipeline_flux2_klein.py#L849-L875)。

本轮选择 text-to-image、无 reference tokens 的 block。官方当前 code 包含 reference-image KV extraction/cache 分支，但 `util.py` 将 `use_kv_cache` 绑定于独立的 `flux.2-klein-9b-kv` 变体；不能把该缓存机制算作本次普通 Klein4B T2I 的跨步 KV。普通无 ref 时联合 attention 对 text/image 均 bidirectional，`causal_attn_fn` 这个函数名不代表给全部 token 加自回归 causal mask。Image editing/VAE 条件编码和 9B-KV 不在本次数值/仿真接受范围。[variant 表](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/util.py#L40-L51)、[attention 实现](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/model.py#L756-L815)。

## Block 公式与 lowering

记 `LN` 为无 affine LayerNorm、epsilon 1e-6；`RMS` 为带 head scale 的 RMSNorm、epsilon 1e-6；`aLN(x;s,c)=(1+c)LN(x)+s`。权重均按数学输入×输出记，NumPy 存储方向是 torch Linear 权重的转置。

Double stream 对 `s∈{img,txt}`：

1. `u_s=aLN(x_s;shift1_s,scale1_s)`；`qkv_s=u_s Wqkv_s`；reshape 成 `[B,heads,Ls,d]`，q/k 依次 RMS、4-axis RoPE。
2. 联合 `K=[Ktxt;Kimg]`，`V=[Vtxt;Vimg]`；`A_s=softmax(Q_s Kᵀ/√d)V`。按 query stream 分行做 attention 精确等价，所有 query 的分母都覆盖联合 keys。
3. `r_s=x_s+gate1_s*(A_s Wo_s)`。
4. `z_s=aLN(r_s;shift2_s,scale2_s)`；`[g_s,v_s]=z_s Wexpand_s`，宽度 `2*(3H)`；`y_s=r_s+gate2_s*((SiLU(g_s)*v_s) Wcontract_s)`。

Single stream 输入已经是 `[txt;img]`：

1. `u=aLN(x;shift,scale)`；**一次融合 linear1** 输出 `[QKV,gate,value]`，宽度 `3H+2*(3H)=9H`。
2. Q/K normalize/RoPE 后做联合 attention；另一个分支做 `m=SiLU(gate)*value`。
3. **一次 linear2** 将 `concat(attention,m)` 的 `4H` 压回 H；`y=x+gate_mod*(concat(...) Wlinear2)`。

这两组公式来自官方类 `_prepare_qkv/_apply_residuals` 与 `_qkv/_out`，不是 R3 手写 motif 的改名。[double block](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/model.py#L524-L661)、[single block](https://github.com/black-forest-labs/flux2/blob/50fe5162777813d869182b139e83b10743caef15/src/flux2/model.py#L437-L506)。

`r4/flux_lowering.py` 提供 `build_cases(seed=7)`，生成 double 34 nodes、single 15 nodes。缩尺为 hidden64、heads4、head16、MLP192、image16 tokens/text8 tokens、RoPE axes `[4,4,4,4]`。Double 还缩小 input channels 为 image16/context96；time embedding 从256缩到16。它们测试实际分支/归一化/gating/RoPE 语义，不代表 full width block 的 cycle 或图像质量。

原始图的融合边界：norm+AdaLN、QK normalization+RoPE、gated residual+下一 norm 合并；保留 dense projection；single 保留官方 fused linear1。剩余独立分支为双流 QKV preparation、联合 attention 的 query rows、双流 postattention/MLP，以及 single attention 与 SiLU-gated MLP。原始图显式 materialize attention scores，**不能声称已压过 FlashAttention/online-softmax 一类更强 attention fusion**。single 最后 concat 的 staging 假设能与 linear2 合并，成本模型必须说明这一点。

`build_optimized_cases(seed=7)` 保留原始 `build_cases`，另提供 double23 nodes、single7 nodes 的更强边界敏感性：将各 QK→softmax→AV 三段精确 composition 合为 `engine="MXU+VPU"`，MAC/vector_ops 分别求和，内部 score/probability 生命周期不暴露给 scheduler；成本模型必须在整个聚合时段保守占用 MXU、VPU、SRAM。它是聚合 kernel 的边界假设，不是实现/校准过的 FlashAttention。与此同时，移出 timestep/timeMLP/modulation producer，以原图数值结果作为 block initial modulation，仍计输入读取；metadata 保留移出节点及其 MAC/vector_ops，任何整 pipeline 外推必须每步付这些共享 producer 一次。数值 reference 仍是原始独立公式。

聚合并未消除 materialized score/probability：`metadata.internal_scratch` 按原始图 tensor shapes 保存各 aggregate 节点两者 BF16 bytes 的保守和，`traffic_bytes` 为两者各写一次、读一次的总和，`scope` 明确为 engine-internal materialized scratch。root compiler/harness 必须为每core预留最大 scratch，并计内部 SRAM traffic，不能通过删除公开中间 tensor 来免费获得容量/带宽。double image aggregate 为6144B scratch/12288B traffic、text为3072B/6144B；single为9216B/18432B（均为缩尺数值推导）。

每个 tensor 的 shape、数值 bytes、研究 BF16 bytes 假设、producer、**全部 readers**、release 条件、payload hash 在 `lowering_tensor_manifest.json`。动态排程不能把某一静态序列中的最后 reader ID 当成全序证明；安全释放条件是全部 readers 完成。初始 tensor 与每个输出只有一个 writer；别名复用由上层 compiler 的完整 reader 集合和地址依赖处理。MAC 按这些缩尺 dense shapes 计数；`vector_ops` 为研究估计，未经指令吞吐校准。

数值复现：

```powershell
python -X utf8 -B -m r4.flux_lowering
python -X utf8 -B -m r4.sources.flux.audit_lowering
```

seeds 7、19、31，各四类图（double/single × 原始/增强），共12个配置，各做原序和随机合法拓扑序；最大误差 `2.220446049250313e-16`。reference 独立展开公式，不调用 Node.run。输出为 `lowering_numeric_audit.json`；这证明 NumPy float64 数学改写的一致性，**未运行官方 PyTorch kernel，未验证官方 BF16/FP32 casting 路径与真实权重质量**。独立红队会额外检查合法重排和多 reader 生命周期。

## 端侧硬件来源与可用范围

Arm 第一方 Ethos-U85 发布说明给出 128–2048 INT8 MAC/cycle、1GHz 时最高 4 TOPS、29–267KB internal SRAM、最高六条128-bit AXI5接口，并明确 INT8 weights、INT8/INT16 activations。这是低功耗边缘 NPU 的量级证据，不能当作 BF16 支持证据，也不证明研究中的双 core MXU/VPU mapping 对应量产硬件。[Arm 发布说明](https://newsroom.arm.com/blog/ethos-u85)、[产品页](https://www.arm.com/products/silicon-ip-cpu/ethos/ethos-u85)。

冻结官方 CMSIS driver README 给出 2048-MAC 配置4个 SRAM ports、2个 EXT ports；SRAM 每端口最大 outstanding reads12/writes16，EXT reads64/writes32。1024 配置为2 SRAM+2 EXT；512 配置为2 SRAM+1 EXT。128-bit 端口在理想每周期一拍时16B/cycle是算术上限，不是本轮测量的持续带宽；必须把 controller arbitration、外部 DRAM 与背景占用作为不同假设。[官方 driver 配置表](https://github.com/ARM-software/CMSIS-Ethos-U/blob/79d0fccfe59cab7fd0cab97c65050d2824c5269f/source/README.md)。

因此本轮 simulator 的 core 数、shared SRAM 容量、DMA 个数、MXU/VPU 服务率与 BF16 支持都需要标记为**研究假设**。以上来源帮助挑选敏感性量级，不能把合成参数组合命名为“Ethos-U85 仿真”。

## 明确不接受的外推

- 保留官方架构的缩尺 graph，仍然不是完整4B真实形状/权重运行；latency 不可换算成 images/s 或质量。
- 数学 graph 可并行不等于 SRAM/地址/端口允许；joint KV 与 residual 多 reader 必须进入 memory contract。
- 基础图的显式 attention score 开销可能被更强 fusion 降低；无源权重/真实编译器/真实硬件数据时不宣称静态已被充分压强。
- 没有由这些模型来源确认任何 scheduler 论文/专利 novelty，也没有为新硬件机制提供生产验收。
