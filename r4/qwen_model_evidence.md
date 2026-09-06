# Qwen3.5-4B：官方版本、真实结构与缩尺数值证据

核验日期：2026-09-05。此处冻结的是用户指定的研究 workload，不是 Codex 代理模型。已阅读本仓库 README 与 R3 下一轮证据门；未访问外部 `llmSched/llm_sched`，未改动 `sim/`，不声称生产编译器或真实 NPU 验收。

## 1. 选型与来源冻结

选择官方公开、非 gated 的 `Qwen/Qwen3.5-4B` post-trained checkpoint，revision **`851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`**。HF API 显示该 revision 最后修改时间为 2026-03-02T00:52:52Z；原模型卡区分了 language model 和 vision encoder，并将语言模型标为约 4B。[冻结模型卡](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/README.md)、[冻结配置](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/config.json)、[revision API](https://huggingface.co/api/models/Qwen/Qwen3.5-4B/revision/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a)。

模型随附 **Apache-2.0** LICENSE，已原样保存；源码文件的授权也是 Apache-2.0。这里记录发布物的许可声明，不推断训练数据的许可范围。[模型 LICENSE](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/LICENSE)。

实现依据为 Qwen/Hugging Face 共同署名的 Transformers `modeling_qwen3_5.py`，另保留其生成源 `modular_qwen3_5.py` 与 configuration 文件，冻结 Transformers revision **`f62dc9bf2c90353b442a56e74391fbb8c689b55e`**。[冻结实现](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py)。模型配置中残留的 `transformers_version=4.57.0.dev0` 不是本研究实际运行版本；本轮未安装或执行完整 Transformers，实际执行环境是 NumPy 2.3.5/Python 3.14。

技术报告核验边界：模型卡正式指向 [Qwen3.5 官方发布博文](https://qwen.ai/blog?id=qwen3.5)，当前访问得到动态网页壳，未取得可引用正文。官方 [QwenLM/Qwen3.5](https://github.com/QwenLM/Qwen3.5) 当前重定向到 Qwen3.8 仓库，但保留 Qwen3.5 发布记录。定向检索未确认一个适用于该 4B checkpoint 的独立 Qwen3.5 通用技术报告；检索出现的 Qwen3.5-Omni、Qwen3、RobotManip 报告不作为该模型结构的替代证据。**结构以冻结 config、张量 header 和源码为准**，不把检索不到表述成“报告不存在”。

可复现抓取：`python -X utf8 -B r4/sources/qwen/fetch_evidence.py`。全部下载文件的 SHA256 与解析 URL 见 `r4/sources/qwen/manifest.json`。GitHub REST API 首次查询因共享匿名配额返回 403，随后以 `git ls-remote` 取得 main SHA 并抓取 immutable raw source；HF 网页首次 fetch 超时，改用同一官方 repo 的 raw/resolve 接口成功。

## 2. “4B”与实际参数、存储范围

为了避免把模型名直接当精确参数，本轮只读取两个官方 `.safetensors` 文件的长度前缀与 JSON header，分别保存 11,160 和 79,064 字节 header；**没有读取或保存 tensor payload，也没有下载完整权重**。根据 shape 求积，逐模块精确计数如下。其总数同时与 HF safetensors API metadata 一致。[官方 tensor index](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/model.safetensors.index.json)。

| 发布物模块 | BF16 参数数 | FP32 参数数 | 总参数数 |
|---|---:|---:|---:|
| `model.language_model` | 4,205,747,456 | 3,840 | **4,205,751,296** |
| `model.visual` | 333,514,240 | 0 | **333,514,240** |
| `mtp` | 120,599,552 | 0 | **120,599,552** |
| 整个 checkpoint | 4,659,861,248 | 3,840 | **4,659,865,088** |

因此这是官方约 4.206B 文本网络、约 4.660B 整体发布物。配置 `tie_word_embeddings=true`，不能再重复增加一份完整 LM head；index/header 实际只计存储张量一次。源码 `_keys_to_ignore_on_load_unexpected=[r"^mtp.*"]` 表示所选普通 Transformers 路径不执行已发布的 MTP 模块；本轮也不建模 MTP。

推导存储量：整个 checkpoint 张量 payload 为 **9,319,737,856 字节**，文本网络为 **8,411,510,272 字节**；这还不是运行时总内存。KV、线性状态、激活、调度工作区、量化 scale/metadata 都另计。即使采用理想 4-bit 权重，参数×0.5 字节也只是未含量化开销的理论权重下界，不是本轮实测显存占用。

精确 header、hash 与模块计数在 `r4/sources/qwen/tensor_header_manifest.json`，复现命令 `python -X utf8 -B r4/sources/qwen/fetch_tensor_headers.py`；实际第 0 与第 3 层共 25 个张量 shape/dtype 提取见 `representative_weight_shapes.json`。

## 3. 真实结构与状态

文本配置为 32 层、hidden 2560、FFN intermediate 9216、词表 248320、native maximum position 262144、SiLU FFN、epsilon 1e-6、无 attention bias，layer_types 精确为 **8 组“3 个 Gated DeltaNet + 1 个 gated full attention”**。4B 变体使用 dense `Qwen3_5MLP`；不能把模型卡家族简介中的 sparse MoE 宣传直接投射到这个变体。[配置](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/config.json)、[DecoderLayer 与 MLP](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L822-L910)。

所有 text decoder 层先 input RMSNorm，再 token mixer，再 residual；随后 post-attention RMSNorm、SwiGLU FFN、residual。普通 `Qwen3_5RMSNorm` 是 **`x / sqrt(mean(x²)+eps) * (1+w)`**，与直接乘 w 的规范不同。线性注意力输出的 `Qwen3_5RMSNormGated` 则使用直接 w 并在 norm 后乘 **SiLU(z)**。源码在相关 norm/decay/recurrent 数值阶段转 FP32；本轮 FP64 校验不覆盖 BF16 舍入。[RMSNorm](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L839-L855)、[RMSNormGated](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L216-L234)。

### Full-attention 层（实际第 3 层）

Q heads 16，KV heads 4，head_dim 256。`q_proj` 权重 **[8192,2560]**，每个 head 先取得 `[q_256,gate_256]`；**不是先全部 Q 再全部 gate**。K/V projection 各 [1024,2560]，Q/K 分别进行 per-head zero-centered RMSNorm，再对前 **64** 个维度做 partial RoPE，其余 192 维直通。Q/K 的旋转之后更新 KV cache。GQA 每组 KV 服务 4 个 Q heads；输出先乘 sigmoid(gate)，再通过 [2560,4096] 的 `o_proj`。[Attention 源码](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L747-L819)。

单 token decode 在位置 L 的 query 对 cache 中 0..L 的 key 全合法；没有未来列时不需要另造 causal barrier。BF16 每层 K/V cache 为 `B×L×2×4×256×2 = 4096BL` 字节。8 个 full 层、B=1、L=2048 时为 64 MiB（由配置推导，非实测）。RoPE 配置保留 mrope_interleaved/section=[11,11,10]；**text-only 同一 token 的 t/h/w positions 相等**，本轮采用其普通 partial-RoPE 退化，不覆盖不同 multimodal position 输入。

### Linear-attention 层（实际第 0 层）

Q/K heads 16、V heads 32，key/value head_dim 均 128；depthwise causal conv kernel 4。官方已将 QKV 投影融合为 [8192,2560]，其中 Q 2048、K 2048、V 4096。Z 为 [4096,2560]，B/A 分别 [32,2560]。conv 权重 [8192,1,4]、无 bias，conv 后 SiLU。Q/K 做 L2norm，并将 Q/K heads 各 repeat_interleave 2 次；Q 再除 sqrt(128)。[GatedDeltaNet 源码](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L502-L661)。

按 value head 的单 token recurrence，S 的布局是 **[key_dim,value_dim]**：

```text
q = L2Norm(q_raw) / sqrt(key_dim)
k = L2Norm(k_raw)
beta = sigmoid(b)
g = -exp(A_log) * softplus(a + dt_bias)
S_decayed = exp(g) * S_previous
delta = beta * (v - k^T S_decayed)
S_next = S_decayed + outer(k, delta)
o = q^T S_next
gated_o = RMS(o) * norm_weight * SiLU(z)
mixed = concat_heads(gated_o) @ out_proj^T
```

这是本轮直接跟随的 PyTorch reference recurrent 路径；prefill 会走 chunked Delta rule，本轮不拿单 token recurrence 的调度收益外推 prefill。[recurrent rule](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L436-L494)。

线性层不持有随 L 增长的 KV cache，而持有 conv_state 和 recurrent_state。配置规定 `mamba_ssm_dtype=float32`；每层 FP32 recurrent S 为 `B×32×128×128×4 = 2,097,152B`，BF16 conv state 取长度 4 为 `B×8192×4×2 = 65,536B`。24 层、B=1 的 recurrent state 合计 48 MiB，conv state 1.5 MiB（推导）。**单层真实 S 已是 2 MiB**，故缩尺小图能放进研究 SRAM 不等于真实整个 4B 模型或所有状态都能驻留片上。

### FFN 与 vision 边界

每层 gate/up 权重各 [9216,2560]，down [2560,9216]；`down(SiLU(gate(x))*up(x))`。gate 与 up 可以融合输出轴；两个 intermediate tiles 的 down 输出是 partial sums，必须归约完才能与 residual 相加。fusion 后无需保留人为的 gate/up 独立 producer 唤醒机会。

真实发布物还含 24 层 vision encoder（hidden1024/intermediate4096/16 heads），3D patch kernel `[2,16,16]`、3 input channels，spatial merge 2，投影到文本 hidden2560。R4 此文件只交付 text decoder 两类块，**不覆盖 vision encoder、视觉 merge、完整多模态 pipeline、token embedding、LM head、MTP**；Qwen text decode 没有 FLUX 式 CFG 双分支。[Vision 配置](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/config.json)。

## 4. 已实现的来源可追溯小图

`r4/qwen_lowering.py::build_cases(seed=7)` 返回两个 `r4.graph.Case`；每个 Node 有源码位置、真实/研究 fusion 标签、输入/输出、MXU/VPU、固定 core0/1 与运算量。所有 weight 数值为种子随机生成，**不加载真实训练权重**。采用原有头数，hidden/intermediate/head_dim **各除 32**，所以缩尺依然保留原来的 query/KV 与 QK/V head 比例、mixer-width/hidden-width 比例。

| 数值 case | 缩尺 shape | nodes | 精确 dense MAC |
|---|---|---:|---:|
| `qwen35_full_decode` | H80/I288；Q16/KV4；D8；partial RoPE2；previous KV length16；1 decode token | 21 | 109,312 |
| `qwen35_linear_decode` | H80/I288；QK16/V32；Dk=Dv=4；conv4；1 decode token | 20 | 115,200 |

前向图中输入 norm 与 residual 未删；full 图包含两组 query-head tile 的 QK→softmax→AV 独立支路；linear 图保留 conv 与 decay/gate 的独立 VPU 分支，以及两组可独立更新的 recurrent heads。两者都将 FFN 划为两个 intermediate tiles，各 tile 内 gate/up 合并，并完成正确 down partial reduction。最初投影进一步将兼容线性投影按输出轴合并，是数学上可行的研究编译选择；并没有宣称生产 NPU kernel 已具备这些 fusion。

常量尽量按实际可融合 projection 打包，避免每个标量单独 DMA。空间 tiling 是查询这些异构依赖的缩尺数值实验，不是全维度 4B 性能估计。MAC 计数是这些矩阵乘法的准确算术计数；`vector_ops` 对 exp/sqrt/reduction/copy 使用操作数估计，**不是延迟测量**。full 图为了使用独立 SSA `kv_next` 显式物化全 cache，VPU copy 已按整 cache 元素收费；其实现可能弱于合法的原地 append，属于后续强化点，不能当作最强真实 KV memory planning 的证据。

## 5. 数值检查与同步含义

已运行 `python -X utf8 -B -m r4.qwen_lowering`。reference 不调用图 Node：full attention 按 head 直接计算；Delta rule 按 head/key/value 直接循环；FFN 将两块重组成完整矩阵计算，而图逐 tile 计算。比较最终 output **及所有新的 KV、conv、recurrent 状态**，不是只比较最终激活。主 seed 最大绝对差 6.661338147750939e-16。

另运行 `python -X utf8 -B -m r4.sources.qwen.check_numeric`，5 个独立输入/随机权重种子、2 种 case，共 10 个检查全部通过，最大绝对差仍为 6.661338147750939e-16。结果、NumPy 版本与源码 SHA256 在 `r4/sources/qwen/numeric_check.json`。这证明已转写公式与独立 NumPy 参考之间的小 shape 数值一致；不构成执行官方 framework、BF16 相容、真实模型质量或生产编译器验收。

每个 tensor 唯一 writer；previous state 保持只读，next state 为独立输出。所有 state live-out 必须保持到子图结束并跨调用导出；不能仅因其内部最后 reader 已执行就回收。独立红队已指出公共 lowering 若仅考虑内部 readers，会错误重用 KV/state 输出地址；该问题由主任务修复 memory planner 后再验收。`Case.evaluate()` 的独立 NumPy arrays 本身不能发现真实物理地址复用错误，因此数值与物理 trace 验证必须分别记录。

关键数据生命周期：input residual 要存到 mixer residual 完成；normalized 在投影完成后释放；KV next 是两支 QK/AV 的共享只读输入并且是 live-out；attention 的 gate 必须存到各 head context 合并并门控；linear S_next 既产生 context 又作为 live-out，conv_next 也是 live-out；FFN x 被两 tile 的 GU projection 读取，两份 partial 输出在最终 reduce/residual 后结束。具体 byte/layout/address/last-reader 由 `r4/lowering.py` 的 case artifact 记录，这里不重复造第二个地址规划 authority。

## 6. 本子任务结论

官方约 4B workload 可以准确冻结，且这个变体**确有两种不同的有状态 mixer**。本轮已完成来源→缩尺完整文本单层图→独立数值检查；来源图在强 projection/FFN fusion 后仍有可解释的 head/tile 并行支路。但这些支路是否形成有意义、可恢复且足以抵消控制开销的等待，需要主实验与更强静态对照决定。不能从结构并行性直接断言动态调度有效，也不能把这两张缩尺 decode 图称为整个 Qwen3.5-4B 的实测性能。
