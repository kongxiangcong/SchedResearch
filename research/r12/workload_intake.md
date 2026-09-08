# R12 完整 Qwen MLP 工作量准入

2026-09-08。结论：**固定来源内容、完整 MLP 代数及逻辑工作量通过本次检查；原生数值、布局、资源和性能准入尚未完成。** 本文负责工作量入口，不把 R8 的 down 切片或其 CPU 容差结果升级为 Wormhole B0 的完整模块结果。

执行入口：[workload_intake.py](workload_intake.py)。本次实际生成：[workload_intake.json](artifacts/workload_intake.json)。仅使用 Python 标准库及 Git，没有导入 Transformers、下载权重、运行旧性能模型或访问设备。

## 来源身份与 Windows 行尾问题

来源内容固定在项目 `a947b563356610cf4dbb05995debf18fc3054e66`。R8 引用的 Qwen 配置 revision 是 `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`，Transformers revision 是 `f62dc9bf2c90353b442a56e74391fbb8c689b55e`。本次检查冻结源及两个 manifest，没有重新向远端获取它们；官方链接用于定位固定来源：[config](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/config.json)、[Qwen3_5MLP](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L822-L835)。

**初次工作树原字节 hash 核对没有全通过：config 与 modeling 文件是 CRLF，冻结的下载源是 LF。** Git 中这两个固定 blob 的原字节精确匹配冻结 hash。另两份由 Windows 产生的 JSON 记录恰好相反：历史 hash 对应 CRLF，而 Git 保存 LF；当前工作树原字节精确匹配其历史 hash。不能统一做 LF 归一化后宣称四个原字节 hash 全部相同。

脚本以固定 Git blob 为唯一内容来源；每文件显式登记历史归档行尾，重建其归档字节后核对 SHA-256 **及字节数**。另行保存 Git blob、当前工作树、重建归档的三个 hash，并检查工作树只存在可解释的 CRLF/LF 差异。任何其他内容变化或 manifest 不符都会失败。历史文件没有修改。

| R5 `sources/` 下的文件 | 历史归档行尾 | manifest SHA-256 | 当前工作树原字节匹配 | 固定内容对应历史归档匹配 |
|---|---|---|---|---|
| `qwen/config.json` | LF | `ddc63e1c717afa86c865bb5e01313d89d72bb53b97ad4a8a03ba8510c0621670` | 否；`c857db69a33400b29db19b4aa8212174253f8c76498b79c5aa9b2a6fd4013ecc` | 是；3,161 B |
| `qwen/modeling_qwen3_5.py` | LF | `458360c8072e6130580639170ad3e645b975512dbabae31eab5f92de5f0f09ef` | 否；`2582e9fd6d949cd593a9874c7173af512be5b58ccb08f146a20d3396232abde7` | 是；95,578 B |
| `qwen/representative_weight_shapes.json` | CRLF | `0cfea86881cb17b746b5b8150bf7ce35605756141c1ab365b1c4df9e962d372a` | 是 | 是；4,013 B |
| `qwen/r4_manifest.json` | CRLF | `cc49171e4ad054b04372299c06e1a441f8f5792b652a4e25789f791fdfd8a05e` | 是 | 是；5,081 B |

`representative_weight_shapes.json` 是历史 safetensors header 提取记录；本次没有重新下载 header 或检查真实权重 payload。它同时记录 layers 0 和 3 的 gate/up/down 三个矩阵；脚本逐一核对 shape、BF16 dtype 和参数数量。R5 来源 manifest 与 R4 来源 manifest 对配置/代码 hash 一致，R4 manifest 明确记录上述两个 revision。

## 完整模块与确定性逻辑账本

来源给出 `H=2560, I=9216, hidden_act=silu`。AST 检查确认 gate/up 是无 bias 的 `Linear(H,I)`，down 是无 bias 的 `Linear(I,H)`，forward 完整保持：

```text
G = gate(X)       # [M,H] x [H,I] -> [M,I]
U = up(X)         # [M,H] x [H,I] -> [M,I]
S = SiLU(G)       # [M,I]
A = S * U        # [M,I]
Y = down(A)       # [M,I] x [I,H] -> [M,H]
```

这是一个完整 dense MLP，不包含 attention、norm、残差或整个 decoder layer。PyTorch 权重存储采用 `[out,in]`，上面的矩阵乘法形状按权重转置后书写。

| 权重 | 来源 `[out,in]` | 元素数 | BF16 bytes |
|---|---|---:|---:|
| Gate | `[9216,2560]` | 23,592,960 | 47,185,920 |
| Up | `[9216,2560]` | 23,592,960 | 47,185,920 |
| Down | `[2560,9216]` | 23,592,960 | 47,185,920 |
| 合计 | 三个不同矩阵 | **70,778,880** | **141,557,760（135 MiB）** |

每个 GEMM 为 `M×H×I` MAC，三者合计 `3MHI`。以下 GEMM MAC 不含 SiLU、逐元素乘法、cast、packing、padding、跨 tile 归约或传输。

| M | Gate MAC | Up MAC | Down MAC | 完整 GEMM MAC | SiLU 元素 / 另行逐元素乘法 |
|---:|---:|---:|---:|---:|---:|
| 1 | 23,592,960 | 23,592,960 | 23,592,960 | **70,778,880** | 9,216 / 9,216 |
| 32 | 754,974,720 | 754,974,720 | 754,974,720 | **2,264,924,160** | 294,912 / 294,912 |
| 128 | 3,019,898,880 | 3,019,898,880 | 3,019,898,880 | **9,059,696,640** | 1,179,648 / 1,179,648 |

M=1 是单请求 strict decode：只准入当前调用 X，不提前提供未来 token。M=32/128 是全部输入行已在入口可用的 prefill；不能把这两项解释成 strict decode 的未来输入合批。

下表每列是**一份张量**。G、U、S、A 各有一份同形状张量；X 与 Y 各有一份同形状张量。BF16 是来源存储的名义方案，FP32 是需重新冻结数值合同的占用备选，两者不是可任意替换的等价实现。

| M | X/Y 各形状 | X/Y 各 BF16 / FP32 B | G/U/S/A 各形状 | G/U/S/A 各 BF16 / FP32 B |
|---:|---|---:|---|---:|
| 1 | `[1,2560]` | 5,120 / 10,240 | `[1,9216]` | 18,432 / 36,864 |
| 32 | `[32,2560]` | 163,840 / 327,680 | `[32,9216]` | 589,824 / 1,179,648 |
| 128 | `[128,2560]` | 655,360 / 1,310,720 | `[128,9216]` | 2,359,296 / 4,718,592 |

这些是逻辑张量大小，**不能相加当 SRAM 峰值或外存流量**。融合可消除中间物化，分片/复制/补齐会改变实际容量与移动，live-set 还取决于分片顺序与所有 reader。脚本只列 `X→gate/up, G→SiLU, U/S→multiply, A→down` 的逻辑读者；真实 NoC source-last-read 和 buffer slot 复用必须在物理计划中另行绑定。

为检查完整工作量有无漏项，脚本还给出一个有条件的外存入口/出口 payload 基数：若三份 BF16 W 与 BF16 X 各从共同 DRAM 读一次、BF16 Y 写一次，则 `W+X+Y` 分别为 **141,568,000 / 141,885,440 / 142,868,480 B**。这排除了重复加载、spill、padding、packet、descriptor、反压/重试等，既不是已执行的 DRAM bytes，也不是所有 warm/fused 合同的下界。cold/warm 的具体初始位置、controller、地址与跨调用持久性仍待统一冻结；本次不报告 warm traffic 或实际 SRAM fits。

## 原生准入缺口与下一步

| 缺口 | 进入完整模块性能试验前需要的证据 |
|---|---|
| 硬件与 SDK | 板卡/SKU、固件、tt-metal revision、SoC descriptor、harvest mask；公开全芯片坐标不等于实际板卡 |
| 数值 | BF16/FP32 math fidelity、乘法/累加/partial 导出/最终 cast 的 rounding、SiLU 近似、显式归约树；完整输出与独立 FP64 source-algebra oracle 比较并报告差异 |
| split-K | 独立确定归约重结合许可；不能以 R8 容差通过授权新归约树 |
| M=1 | 原生 kernel/tail/tiling 支持、zero-fill 来源、有效输出 mask、实际 padding MAC 与传输；不照搬 TARS 的 M 为 32 倍数规则 |
| 布局与容量 | 固定张量/权重分片、物理布局与地址、共享 controller、复制/驻留、L1 保留区、CB slot、fusion/spill 及全部 reader |
| cold/warm | 各比较组共同起终位置与权重/缓存生命周期；warm 驻留必须有容量和跨调用存活证据 |
| 完成与复用 | 每条传输的 acceptance、source-last-read、destination-visible、notification 与合法 wait scope；实际源和目标 reader 完成后才复用 |
| 完整执行 | 真正执行 gate/up/SiLU/multiply/down，所有 H 输出可见；不能将 R8 `down N=128` 的 elapsed 乘常数作为指标 |
| 性能与归因 | 经校准的完整入口→输出可见 elapsed、逐 controller/link/NIU 证据、正确移植的强 P0 与 P1；本次不存在 H1/H2 性能结果 |

来源 BF16 字段本身不定义 backend 的累加方式。R8 的抵消见证记录顺序 FP32=1、split-K FP32=0、FP64=2；本次读到冻结记录，不复跑也不从中推断 Wormhole 的数值结果。候选编译计划必须保留允许的数值语义，误差阈值不能掩盖计算形式被改变。

## 本次阅读覆盖与旧轮边界

路径均相对仓库，旧报告中的失效 Windows 链接按 `research/` 重定位。这里仅登记本工作量子任务的实际覆盖；读取 evidence ledger 的外部论文登记不等于重新读取那些论文。

| 路径 | 本次实际范围 | 证据等级与作用 |
|---|---|---|
| `SchedResearch_reassessment_evidence_20260907/proposal_contract.md` | 全文，1–76 行 | 合同阅读；H0 优先、完整 MLP、M 集合、数值与执行准入门 |
| `SchedResearch_reassessment_evidence_20260907/evidence_ledger.md` | 全文，1–112 行 | 重审登记阅读；保留原外部/历史读取范围与未完成项 |
| `research/research_progress.md` | 全文，1–61 行，包括末尾 R11 | 历史报告阅读；逐轮合同不同，不把 source slice/参考模型当设备结果 |
| `research/analysis/r1_r10_research_retrospective.md` | 全文，1–132 行，包括 §9 R11 | 历史报告阅读；15 条正式候选、未测/关闭区分；旧投入建议不限制新合同 |
| `research/r8/source_contract_audit.md` | 全文，1–115 行，尤其 §4、§6 | 历史审计阅读与本次来源复核；定位模型 revision/hash、N128 子问题与数值许可边界 |
| `research/r8/experiment_report.md` | 全文，1–100 行 | 历史报告阅读；CPU 数值、单 payload 七事件模型，未测时序 |
| `research/r8/target_contract.json` | 全文，1–93 行 | 合同检查；prepared down input、M1 准入未知、tiled 仅 live-set、completion 覆盖有限 |
| `research/r5/sources/resource_source_manifest.json` | Qwen 四项 1–34 行及 pinned JSON 解析 | 本次 manifest 检查；冻结 hash/bytes 和继承关系；其余平台 entries 未用于本工作量 |
| `research/r5/sources/qwen/r4_manifest.json` | 全文，1–72 行 | 本次代码/结果检查；model/Transformers revision、config/model 原始 URL/hash/bytes |
| `research/r5/sources/qwen/config.json` | 全文，1–104 行 | 本次来源检查；text H/I/dtype/SiLU，不使用 vision 配置充当 MLP |
| `research/r5/sources/qwen/representative_weight_shapes.json` | 全文，1–194 行 | 本次冻结 header 记录检查；layers 0/3 三个 MLP 权重均核对，未获取实际 payload |
| `research/r5/sources/qwen/modeling_qwen3_5.py` | 人读 816–840 行，MLP 822–835；全文件 AST 解析仅为定位 | 本次源码检查；三 Linear、bias 与 forward；未声称人工完整阅读整个模型实现 |
| `research/r8/results/numerical_results.json` | 18 个摘要比较及末尾 cancellation witness | 已有结果记录检查；不是重算原 NPZ，不是本次完整 MLP 数值验收 |
| `research/r12/workload_intake.py` 与 JSON | 本次实际运行；另用独立表达式核对三种 M 的 MAC/bytes | 本次计算；精确整数工作量，不含任何 timing 或设备证据 |

旧轮可继承的限制：R4/R5 通用 ready 负结果只覆盖当时来源切片和有限资源模型；R6/R7 是 Phoenix copy/固定 INT8 功能与计量入口；R8 是 down `K=9216,N=128`、M1/32 的逻辑/数值与单 payload 偏序；R9/R10 是共享 EXT staging 参考合同，R10 的 1,440 次观察并未触发改序；R11 是完整 GDN 的 cold-weight/staged ABI 驻留合同，完整 elapsed 未改善。它们既不证明本轮 Wormhole MLP 已有残差，也不证明本轮一定没有价值。

上述 R4–R7/R9–R11 信息来自本次完整阅读的两份逐轮台账，**没有在本工作量子任务中逐文件复核对应原报告/源码或重放 trace**。R8 相关合同与来源另有直接检查，如表所列。没有不可访问的必需工作量来源；缺的是原生硬件/数值/性能准入证据，不能补写成“已验收”。

## 复现与本次检查

从仓库根运行，Python 3.10+ 和 Git 足够：

```powershell
python -X utf8 -B research/r12/workload_intake.py
```

本次输出状态是 `source_and_logical_work_accepted_native_admission_pending`：4 个来源的固定内容/历史归档 hash 通过、2 个当前工作树原字节 hash 通过。每份 JSON 同时写出二者，避免全绿状态掩盖 CRLF 差异。

另行执行了独立整数表达式复算，核对三种 M 的完整 MAC、所有张量各 BF16/FP32 bytes 和有条件的 `W+X+Y` 基数；通过。还仅在内存中向返回的固定 config blob 加一个空格，验证 hash 检查确实拒绝该内容改变；通过，未修改历史文件。没有数值输出 tensor、周期数、置信区间、native kernel 或 H1/H2 性能样本。
