# R13 数值与实际数据需求资格

2026-09-08。**本次实际通过完整 H=2560、I=9216、M=1/32/128 的 CPU 数值资格，以及独立需求/资源守恒回归。** 此处没有 DES 周期或硬件结果，不宣称训练模型任务精度。当前研究的统一上层合同仍是 [proposal_contract.md](proposal_contract.md)。

## 先冻结，再执行

[numerical_contract.json](numerical_contract.json) 在首次数值执行前写入，结果保存其原字节 SHA-256。输入采用固定 PCG64 seed；三个独立确定性权重各为完整矩阵，无权重下载。X 和 W 先转为 BF16，FP64 源代数和量化执行都使用相同的已量化初始数据。源代数只保留 `down(SiLU(gate(X))*up(X))`，不额外插入 down 输入 cast，用于显示命名模型相对源代数的偏差。

三个 GEMM 的 BF16 乘数精确表示为 FP32。每32个 K 乘积先按相邻项二叉树做 FP32 加法，再按 K block 递增顺序累加 FP32 block sum；不使用 FMA，也不许可候选随意重结合或改变 split-K 归约顺序。主实现物化32项乘积后分层相加；独立实现逐 K 流式推进二进制 carry 栈，且采用不同输出列分块。**普通 FP32 BLAS 没有被误称为这个归约树。** BLAS 只计算 FP64 源代数对照。

SiLU 在 FP32 的每个乘/加/除步骤舍入，exp 由 host double libm 计算后舍入 FP32，使用正负分支避免溢出；独立路径使用标量 `math.exp` 和标量舍入。随后执行 FP32 逐元素乘法，以及显式 BF16 round-to-nearest-even cast，再进入 down。BF16 主路径采用位级舍入，独立路径采用指数/网格与 ties-to-even 整数舍入。整个中间张量和完整输出都做逐位一致检查，不能借宽松误差容差掩盖合同不一致。

## 实际结果

可复现代码为 [numerical_reference.py](numerical_reference.py)，完整结果为 [numerical_qualification.json](artifacts/numerical_qualification.json)。环境为现有 R12 本地 venv，Python 3.13.12 / NumPy 2.5.3。耗时字段明确是 **CPU 验证墙钟时间，不是模型延迟**。

| M | 完整输出元素 | 实际执行的 padded M | 量化合同独立检查 | 相对 FP64 源代数 L2 误差 | 最大绝对误差 / 源代数最大绝对值 |
|---:|---:|---:|---|---:|---:|
| 1 | 2,560 | 32 | 全部中间与输出逐位一致 | 0.162382% | 0.159173% |
| 32 | 81,920 | 32 | 全部中间与输出逐位一致 | 0.165065% | 0.152029% |
| 128 | 327,680 | 128 | 全部中间与输出逐位一致 | 0.165844% | 0.140576% |

预登记的两个源代数误差阈值均为2%，三项通过。接近零的输出导致最大逐点相对误差可达数百倍，此指标已完整保留在 JSON，但没有被当作稳定的验收分母。本次结果只验证固定生成样本；2%不是模型对任意输入的形式误差界，也不是 Qwen 的任务准确率声明。

另实际通过：10个 BF16 正负 ties/subnormal/signed-zero 案例、100,000个有限 FP32 位模式的独立 BF16 转换、8个 SiLU 极值/零值案例、FP32 归约重结合反例，以及漏掉 down 输入 cast 的负向变体。固定树的抵消案例得1，非法先抵消大项的变体得2；漏 cast 变体也产生不同输出。M=1 的31条 padding 行实际执行并检查保持零。

## 必须交给资源与性能模型的账本

- 三份 BF16 权重共141,557,760 B（135 MiB），每次 cold invocation 必须支付实际需要的读取。
- X 为 BF16，Y 为 **FP32**，逻辑入口/出口分别为 `2*M*2560` 和 `4*M*2560` B；R12 的 BF16 Y 候选基数不能沿用。
- G/U/S/A32 各为 `4*M*9216` B，A16 为 `2*M*9216` B；这些是单份逻辑大小，不是相加后的物理峰值。
- A32→A16 为 `M*9216` 次 cast，逻辑读取 `4*M*9216` B、产出 `2*M*9216` B。融合可消除中间物化，不能删除转换工作。
- M=1 的逻辑 GEMM MAC 为70,778,880，但32行 tiling 下实际 padded MAC 为 **2,264,924,160**；M=32也是2,264,924,160，M=128为9,059,696,640。零填充的来源、物理存储、搬运和服务由实际计划显式计量。
- 这些数值资格不自动证明某个物理分片、bank布局、队列控制或完成事件实现正确；后者由 DES 与独立 checker 验收。

## 独立重新推导真实需求

[demand_checks.py](demand_checks.py) 从原始 ONNX 的 Conv 属性推导 `(out_y+dy-pad_y, out_x+dx-pad_x)` 访问，利用最终 IR/SVG 定位分片维度，并对保存的输出 affine map 做 basis-vector probe 验证该维度确实改变 x。它不调用 R12 halo 枚举器、不读取 R12 halo 结果作为答案，也不由 buffer footprint 推定访问需求。[demand_checks.json](artifacts/demand_checks.json) 保存实际输入 hash 与逐 core 枚举结果。

| 合同 | 本次独立推导 | 范围 |
|---|---:|---|
| 真实2conv，四个连续对齐 ox owner/consumer 区间 | 3,072个远端16-bit word，即49,152 bit；共享128-bit/cycle bus必要服务界384 | 该所有权见证；不证明384或512周期完整协议可实现 |
| 四分片源，四目标都要求完整复制，允许理想共享 bus 广播 | 所有16,384 word至少经过一次，262,144 bit / 128 = 2,048 | 显式 full-copy 合同；512周期共享 bus 声明被拒绝 |
| 四份独立 quarter 分别送到四个不同目标，各有独立128-bit/cycle link | 每 link 65,536 bit，四条各512 cycle，可并行 | 四条独立传输正控制，不是完整 all-gather |

真实2conv远端列仍为 `{7,8,15,16,23,24}`。因此 full-copy 的2,048界不能挪作真实2conv必需界；本次没有把历史条件性14,344分析升级为已确认成本修复或P1收益。

## 复现

从仓库根使用既有依赖环境运行：

```powershell
& research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/demand_checks.py
& research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/numerical_reference.py
```

只输出两个紧凑 JSON，张量留在内存；R12冻结文件未修改。数值脚本固定读入现有数值合同，执行过程中若合同字节变化则失败。此资格是后续 M0 的数值/需求子证据，**不单独代表完整 M0 已通过**。
