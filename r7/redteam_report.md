# R7 独立红队：执行合同与计量资格

日期：2026-09-05。独立范围：主任务编写的 copy/compute harness、公开 ABI 与 fixture、采集器及执行回执。此 reviewer 不提交设备 kernel，也不启用 profiling。已完成执行前审查和全部四份真实执行进程回执复核。

**结论：接受这两个具体 kernel 的真实功能执行与 host elapsed screening 能力；不接受设备计量资格、strong-static、残差归因或动态收益主张。** Copy 与 INT8 GEMM 各 4 次，共 8 次设备提交均保存 COMPLETED、全量数值通过，外层进程无 Error/FAILED、无 timeout、退出码为 0，前后冻结 artifact 未变。以下说明证据与限制。

## 执行前发现与修正

1. **GEMM kernel 名不一致，运行前拦截。** 初版 `compute_probe.cpp` 和 compute addendum 使用 `DPU_PDI_0`；下载 `gemm_4x4.xclbin` 的安装 DLL metadata 解析及 fixture manifest 都是 `DPU`。已将此列为执行 blocker，主任务在设备提交前改为 `DPU`。不能把宿主名字选错造成的异常归类为 Phoenix 不支持 compute。
2. **计时标签混淆，运行前修正。** 初版 `launch_to_output_sync_s` 由 launch/wait 与 output sync 两段相加，遗漏 state-check 与 timer 间隔。主任务改为从独立 `launch_start` 到 output sync 完成的连续窗口。两段分项仍独立保留；不得用旧标签解释已修改代码以外的历史数据。
3. **来源版本不等同于兼容性验收。** RyzenAI-SW 1.0 fixture 配套历史 XRT 2.14 头文件，而本机是 XRT 2.17/driver .110。主任务使用精确 2.17 host headers，保留原 compute xclbin/指令和 source helper；能编译只证明宿主链接，兼容性必须由有界真实运行、状态和数值检查判断。

核对文件：[experiment_plan.md](experiment_plan.md)、[compute_addendum.md](compute_addendum.md)、[copy_probe.cpp](copy_probe.cpp)、[compute_probe.cpp](compute_probe.cpp)、[capture.py](capture.py)、[metadata receipt](sdk/metadata_receipt.json)、[GEMM metadata](sdk/metadata/15_gemm_4x4.txt)。

## 合同与错误路径审查

| 项 | 独立结论 |
| --- | --- |
| Copy ABI | 1 GiB 输入/输出、opcode 1、`DPU_PDI_0`、input group(1)/output group(3)/cacheable instruction group(5)、其余空参数，遵循冻结的 `TestDF_bandwidth.cpp`；未把它缩成未经支持的新 shape。 |
| Copy 数值验收 | 32-bit 位置相关固定模式，不是短周期全零；每轮输出先 poison 并 sync；检查全部 268,435,456 words、input/output hashes 及 input host mapping hash。`input_unchanged` 是主机映射的检查，没有额外从设备同步 input 后再验的证据。 |
| GEMM ABI | 一个 prepared INT8 row×2048×2048、INT32 2048 输出；metadata 的 opcode uint64、各 BO 指针及 instruction count uint32 和宿主参数相符；instruction BO group(5) 指向 SRAM，其他数据 BO group 指向 HOST。tag/size metadata 不认证物理 SRAM 可驻留分配量。 |
| GEMM fixture | 激活与原始权重为 varied signed [-3,3]，INT64 oracle 再验 INT32 结果；packing 是 WgtMatrix 地址映射，super sequence 为 200 B。独立 CPU 编译使用原始 AMD helper 逐 byte 核对 4,194,304 B 权重 packing 和 200 B sequence，全部 2048 oracle 输出复验 PASS。见 [fixture verifier source](sources/kernel_access/verify_fixture.cpp)、[CPU verifier output](sdk/fixture_verification_output.txt)。CPU verifier 不是设备算术验收。 |
| 输出反证强度 | 两个 harness 都先 poison；compute oracle 仅供比较，不复制到设备输出，因此完整匹配能排除 host 直接填 golden 的路径。compute 保存所有原始输出 bytes；copy 保留全量比较计数与 SHA，不保存 1 GiB 输出副本。 |
| 等待与失败 | `wait2(30s)` 后还检查 `ERT_CMD_STATE_COMPLETED`；超时返回不是默认通过。异常进 stderr、退出码 1，外层独立 subprocess timeout 保存部分 stdout/stderr。不存在 vendor verify 的 catch 后重写 PASSED。 |
| 冻结与分界 | 输入/fixture 内部 hash 与外层运行前后 artifact hash可交叉核对；同进程重复复用 BO，跨进程不能声称相同地址。输入/指令 sync、poison、hash、比较、落盘不在 launch→wait 窗口内；完整 subprocess elapsed 是另一观测。 |
| 误用风险 | 任意输出错误/timeout/runtime error 要保留并停止；不能根据 elapsed 筛掉失败或重跑到通过。成功的少数重复是功能/host elapsed calibration，不能当 train/test、paired blocks 或收益 CI。 |

## 计量否定与未识别项

[独立计量报告](measurement_access_research.md)以安装 DLL 完整 hash、导出 RVA/机器码证明通用 timestamp/clock/trace API 是空函数。接口调用返回 0 不可以填 `device_elapsed=0`、`traffic=0` 或 `dropped_records=0`。Windows AIE profile 源码提供补件路线，但所选 copy/GEMM xclbin 没有 `XDP_KERNEL`，有界查找缺插件和元数据；其他四份已装 xclbin 有该名字，也尚未建立 profiling ABI/事件/固件/窗口合同。

因此本轮 **没有**：真实 empty-device calibration、可校准 device elapsed、actual requested/accepted/completed port bytes、compute-active/elapsed cycles 分母、request trace/limit/latency buckets、running frequency、instrumentation on/off、counter wrap/overflow/丢失认证。CPU no-launch timer 仅是主机时钟调用成本。单 GEMM 正确不等于计数器的 single-compute calibration；copy 已知 logical bytes 不等于 actual bus counter 校准。

## 执行回执审核

独立脚本 [`audit_execution_receipts.py`](audit_execution_receipts.py)仅读取保存的数据，结果 [`execution_receipt_audit.json`](execution_receipt_audit.json)为 `consistency_pass=true`、`copy=4`、`compute=4`、`errors=[]`、`performance_gate_evaluated=false`。它检查每份 before/after/current artifact SHA、capture/plan SHA、raw stdout/stderr SHA、编译源/二进制绑定、各 stage 条数、state=4、数值通过、全量覆盖及连续计时关系，并将全部四份 GEMM 输出的 **8192 B 原文件**逐 byte 与冻结 oracle 比较。没有再次执行设备或 fixture generation。

| 保存进程 | launches | host launch→wait2，ms（原顺序） | host launch→output sync，ms | 整个 subprocess elapsed，s |
| --- | ---: | --- | --- | ---: |
| [copy_initial](evidence/copy_initial/receipt.json) | 1 | 363.9387 | 383.9602 | 5.2453441 |
| [copy_repeat](evidence/copy_repeat/receipt.json) | 3 | 346.2202, 265.8747, 266.4585 | 364.3393, 285.9118, 288.0976 | 9.2722878 |
| [compute_initial](evidence/compute_initial/receipt.json) | 1 | 2.8619 | 2.8752 | 0.2892571 |
| [compute_repeat](evidence/compute_repeat/receipt.json) | 3 | 2.2650, 0.5888, 0.4801 | 2.2892, 0.6127, 0.4929 | 0.1863639 |

每次 copy 都检查 268,435,456 个 words，输出 hash 都为 `f670740db6f236b884078533b82427530dfa8c5f1c57b269843be95c87c49ad8`，等于 prelaunch 固定输入；每次 compute 都检查 2048 个 INT32，输出 hash 为 `2da121a2e7db4df976d9266d5d0af0d0fa460ca0e58d0a6034ef4e8197fd2158`。这些数值是**数据完整性**事实，不能当 AXI traffic。copy 未保存 1 GiB 原始输出，独立复核的物证是已审阅比较代码、全量比较日志与摘要；GEMM 有完整输出文件。原始失败数为零，没有被排除的失败样本。

首次与 repeat 是两个进程，仅有一个现场时段、同一固定输入，无配对背景、随机顺序或新相位。repeat 进程内部长期复用同一组 BO，这由分配在 loop 外的代码及一份 prelaunch 地址记录支持。两进程报告的 address 数值恰好相同也不能认证物理 page/context 映射相同：copy 的输入/输出 group ID 从 `131072` 变为 `262144`，指令 group 从 `131073` 变为 `262145`。不将它们描述为跨 session 完整布局冻结或 R6 独立 test session。

日志显示重复时 elapsed 改变，尤其 compute；没有运行期频率、热态、背景、设备起止和实际流量，因此无法辨别 host/runtime warming、设备状态、DVFS、缓存或其他原因。禁止将初次/后续比值写成机制收益、静态收益或可恢复等待。也没有据此计算 CI/TOPS/AXI bandwidth。

软件 provenance 边界：实际运行回执保存所选安装 DLL 的前后 hash、PATH 前缀、关闭 profiling 的局部 ini 与 `XCL_EMULATION_MODE=null`；SDK metadata 进程另行打印了实际加载的安装 `xrt_coreutil.dll` 路径。copy/compute 进程本身没有逐模块 `GetModuleFileName` 记录，所以这些回执不是每个已加载 DLL 的独立模块路径认证。上述功能接受来自物理 XRT 路径、已枚举 Phoenix、明确 BO 与 kernel 提交/完成和输出验证的组合证据，不能提升为受控 production workload 验收。

## 最终决定

执行前的 ABI 名称和计时标签问题在任何设备提交前修正并重新编译；审核后的源/二进制与实际进程前后摘要一致。**Accept executable access / Refine measurement**：现有栈已经能够运行可复核 copy 和单 INT8 GEMM，R6 的“缺单 compute 可执行合同”已取得实证进展。下一门是与该 workload 同 context 的可定义 counter/timer/请求接口或适配开发包，以及分别完成真实 empty、counter known-bytes、single-compute 和 instrumentation 开销校准。

当前证据不满足 R6 mechanism gate。强静态、真实剩余损失、固定 binary 干扰、合法动态动作与收费净收益均未测；不得把缺观测写成 negative result，也不得以 8 次功能执行解除 R5 已测通用 ready 候选的关闭决定。

## 最终文档审计

在 lineage freeze 前，只读复核了最终 [experiment_report.md](experiment_report.md)、[measurement_summary.json](measurement_summary.json)、[README.md](README.md)与[根进度表](../research_progress.md)。本次只更新本红队报告，未修改这些文件，也未运行设备。

- 摘要全部 4 个进程的 receipt SHA、prelaunch contract、8 条 result 及 process elapsed 与原始回执/日志逐字段相同。GEMM repeat 的完整进程值为 **0.1863638999639079 s**，报告中的 0.186364 s 是正确舍入；8 条两种 elapsed 表格、fixture 范围 [-575,691]/694 distinct outputs、2×1000 host timer（23.1/22.9 ns mean、min 0）均相符。
- 36 个文档本地链接/目录目标全部存在。README 的复核入口不启动设备；重用执行路径拒绝覆盖及预构建 device binary 限制表述清楚。此处未重新运行会重写 summary 的命令，而是直接比较其保存内容与 raw receipts。
- 最终文档清楚区分 host/device 编译、logical/actual bytes、主机空窗口/设备 no-op、功能重启/独立统计 session，并保留未控制背景/频率/热态、未认证完整 loaded modules、无 instrumentation 对照与无收益门的边界。未发现新的 R7 性能过度主张。
- 根表历史 R5 行仍保留原约33%措辞；现已在表前添加明确补注：它是**不同环境各自静态重训后的投影模型差分，不是固定 binary 实机干扰测量**。这使根表可独立理解，同时保留旧行。与 R6 byte snapshot 对照，全部 10 条 R1–R6 数据行均逐行原样保留。

本次审阅摘要：experiment report `4809b388d5b8a49036f6ce410f936cf72f843e914a24908ed026f0ced14a3c45`；measurement summary `85305ce1ad43f1242a56977ab594a703fbf66f750a74f9a5771ae54bdfc03125`；R7 README `e805721c7d2b9c4b534348288a9dd73684ecc324abaa94ddb1662bf4dc9960af`；根进度表 `d2696951b8613e2fa90be5b730b0be7328d5fa199e035155cad4e7745843f30e`。这些仅绑定此次文档审阅对象；历史 manifest/lineage 的最终一致性由主任务的 checker 单独认证。

**Final document verdict：PASS，未留下阻止记录 successor 的文档 blocker。** 该 PASS 不改变前述设备计量和机制门的关闭状态。
