# R4 模型冻结登记

核验日期：2026-09-05。这里的模型名均是研究 workload。没有下载大权重或运行完整模型。

| 目标 | 冻结版本 | 实际规模与许可 | 本轮结构 |
|---|---|---|---|
| LLM | `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` | 文本4,205,751,296；完整发布物4,659,865,088；Apache-2.0 | 32层，3×GatedDeltaNet+1×gated GQA循环；dense SwiGLU；分别验证单token cached decode |
| 图像主网络 | `black-forest-labs/FLUX.2-klein-4B@e7b7dc27f91deacad38e78976d1f2b499d76a294` | 3,875,544,576；Apache-2.0；step/guidance distilled | 5双流+20单流；H3072、24heads；官方4步、CFG1；主实验无unconditional分支 |
| CFG语义对照 | `black-forest-labs/FLUX.2-klein-base-4B@a3b4f4849157f664bdbc776fd7453c2783562f4d` | 同级主网络；Apache-2.0；无上述蒸馏 | BFL合并batch2B一次调用；Diffusers两次调用；未混入主仿真 |

Qwen 完整发布物含333,514,240 vision参数与120,599,552 MTP参数；选定文本普通 decode 路径不执行这些部分。BF16/FP32文本权重约8.412GB，完整payload约9.320GB，均未计激活和状态。单个真实 linear 层 recurrent state 已有2MiB FP32；这与缩尺图约0.2MiB总SRAM的容量问题不同。[官方配置](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/config.json)

FLUX 主网络之外还需 Qwen3-4B 文本编码器4,022,468,096参数（不是Qwen3.5），以及按官方源码构造公式计得84,046,115参数的VAE。合计约7.982B trainable；VAE计数未与weight header核对。主网络BF16 weight-only约7.751GB，不能叫4GB显存。BFL默认外部text encoder是FP8，HF冻结pipeline的text配置/index是BF16；本轮不混算成一套实测驻留内存。[官方模型卡](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/blob/e7b7dc27f91deacad38e78976d1f2b499d76a294/README.md)

源码冻结：Transformers `f62dc9bf2c90353b442a56e74391fbb8c689b55e`；BFL `flux2@50fe5162777813d869182b139e83b10743caef15`；Diffusers核对 `c5469b7ceb606edd7ba6570dcd17d38590a18db6`。模型dtype、完整source shapes、具体模块公式、来源失败记录与许可逐项见 [Qwen证据](qwen_model_evidence.md)、[FLUX证据](flux_model_evidence.md)。Qwen独立通用技术报告未核验到正文，明确以配置、tensor headers和源码作结构证据。

| 数值图 | 缩尺shape | dtype和边界 |
|---|---|---|
| Qwen full decode | H80/I288/Q16/KV4/head8/cache16/新token1 | FP64随机数值；模拟BF16，显式FP32 overrides；保留gate、partial RoPE、KV live-out |
| Qwen linear decode | H80/I288/QK16/V32/key4/value4/conv4/token1 | FP64随机；recurrent与规定参数以4B计；保留conv和S live-out |
| FLUX double/single | H64/heads4/head16/MLP192/image16+text8/time16 | FP64随机；模拟BF16 bytes；图像语义/质量未验；真实modulation/联合attention/SiLU门控 |

进一步 attention aggregate/conditioning-resident 图是同一缩尺数学的编译边界敏感性，保留被隐藏中间结果的内部scratch预算。FP64等价不等于BF16舍入等价、官方kernel执行或真实模型质量。

机器可复查证据：`sources/qwen/manifest.json`、`sources/qwen/tensor_header_manifest.json`、`sources/flux/source_manifest.json`、`sources/flux/parameter_counts.json`。完整R4运行时源码hash、shape/bytes/layout/readers/address、seed、所有trace位于 `../experiments/results/r4/`。
