# R7：固定 copy 与单 GEMM 实机通过，研究入口收敛到 profiler/compiler 合同

日期：2026-09-05。**接受本机旧 Phoenix 栈上的可复现功能入口：项目局部 host runner 已执行 4 次固定 1 GiB copy 和 4 次 INT8 GEMM，全部完整数值比较通过。当前证据等级仍是功能验收与 host elapsed 筛查；最低设备计量合同未通过，R5 通用 ready 候选保持关闭。**

这比 R6 前进了一步：不再仅由厂商 CLI 控制输入、BO 与数值检查；现在有可重编译的 host、冻结的 device binary/指令/输入/布局、运行前 hash、实际 BO 地址回执及输出 oracle。**可重编译的是 host runner，不是 GEMM 的 AIE device binary。** 后者仍是公开预构建产物，未建立任意 shape/dtype/tiling 的设备编译路径。

## Research Question → Hypothesis → Strong Baseline

[事前计划](experiment_plan.md)在设备探测前写入，全部回执保存其同一个 SHA256。来源发现后、任何 GEMM 运行前，补充[明确计算合同](compute_addendum.md)。

| Research Question | Hypothesis | Strong Baseline / 判别实验 | Result → Verdict |
| --- | --- | --- | --- |
| 无需升级旧驱动，能否自己固定 binary、input、layout、BO 并执行 copy？ | 已安装 XRT 公共 ABI 足够，不必先安装完整 Python SDK。 | 逐导出及精确头文件核验；保持厂商 1 GiB 指令与大小；确定性全地址 input、poison output、全量比较。它是功能基线，非最优静态 copy。 | C API open/load 成功；C++ runner 两次新进程共 4 次 copy 全部通过。**Accept access。** |
| 能否得到数值可验的单 compute，避免把 BF16 文件名当能力？ | 早期 Phoenix 官方示例可提供完整 INT8 host/指令/布局合同。 | 官方 qlinear_2 单 token GEMM；原始 C++ helper 独立验证 Python fixture 后，在本机执行全部输出比较。它是预构建静态算术基线，非 strong-static 搜索结果。 | 两次新进程共 4 次 INT8 GEMM 全部精确通过。**Accept 此 shape/输入/栈的功能兼容；不外推 BF16/GDN。** |
| 能否认证 actual bytes、compute-active、request/limit 与设备时间？ | 导出接口可能是桩；真实 profiler 需要匹配插件与 kernel 合同。 | 检查实际安装 DLL 机器码；同 SHA Windows profiler 源码；16 个 xclbin 元数据。 | 通用 timestamp/trace 为 stub；两个已测 xclbin 无 XDP_KERNEL，配套 profiler 未取得。**Refine measurement；不做资源归因。** |

继承 R5 的 negative result、prepared-token 驻留范围与 R6 的模型生命周期判断均不变。约 33% 的旧投影差分仍不是固定 binary 实测；本轮也没有把新的数值测试当作 strong-static 干扰实验。

## 实现与来源合同

1. 已安装 `xrt_coreutil.dll` 的 426 个导出生成项目内 import library；25 个精确 XRT SHA 原始头文件加明确标记的生成 `version.h`，用已存在但不在 PATH 的 MSVC 14.44 BuildTools 编译。没有安装工具、改系统 PATH、替换 DLL 或升级 driver。[SDK 报告](sdk_build_report.md)
2. 一个标准库 Python ctypes 程序通过 C API 打开设备并加载 validate xclbin，未提交 kernel；真正数值实验使用公开 C++ `register_xclbin → hw_context → kernel → wait2`。[C 回执](evidence/c_api_open_load/receipt.json)
3. copy 保持系统 `validate_phx.xclbin` 与 50-word `df_bw_dpu.txt`，每次 1 GiB 输入、1 GiB 输出。输入为按 word index 的确定性 32-bit 双射混合，避免短周期数据掩盖跨块排列错误；输出置 0xa5 并 sync 后才启动。逐 268,435,456 个 uint32 比较，再核对输入/输出 SHA256。[copy 源码](copy_probe.cpp)
4. compute 使用官方 RyzenAI-SW `a3d163c81e4d0b21667c05f614c1d79be14c3fa1` 的 Phoenix `gemm_4x4.xclbin`、1663-word 指令与 qlinear_2 ABI。INT8[1,2048]×INT8[2048,2048]→INT32[1,2048]，4,194,304 **逻辑** MAC。A 含 200 B superkernel 序列，W 为 4 MiB 厂商布局。Python 生成数据/参数，原厂 C++ helper 对每个字节独立核对，并用 INT64 oracle 再验 2048 个输出；然后才执行 NPU。[来源报告](kernel_access_research.md)、[fixture 清单](sources/kernel_access/int8_fixture/fixture_manifest.json)、[compute 源码](compute_probe.cpp)

输入数值为 [-3,3]，oracle 范围 [-575,691]、694 个不同输出，含正负与抵消。只覆盖这一确定性 fixture，不是全 INT8 数值范围、量化精度或模型质量验收。设备执行程序没有 CPU fallback；CPU oracle 只用于最终检查。

## Result：实际运行与计时边界

两种 kernel 都先在一个新进程执行 1 次，通过后另起新进程执行 3 次。repeat 进程内部保持同一 BO、input、layout、binary；每次都重新 poison 输出，copy 还重新 sync 输入/指令。没有新增背景、静态变体、动态策略或 test seeds。

| Kernel / process | 调用次序 | host launch→wait2 (ms) | 连续 launch→output sync (ms) | 完整数值比较 |
| --- | --- | ---: | ---: | --- |
| copy / initial | 0 | 363.9387 | 383.9602 | 268,435,456 words，0 差异 |
| copy / repeat | 0 | 346.2202 | 364.3393 | 同上 |
| copy / repeat | 1 | 265.8747 | 285.9118 | 同上 |
| copy / repeat | 2 | 266.4585 | 288.0976 | 同上 |
| GEMM / initial | 0 | 2.8619 | 2.8752 | 2048 INT32，0 差异 |
| GEMM / repeat | 0 | 2.2650 | 2.2892 | 同上 |
| GEMM / repeat | 1 | 0.5888 | 0.6127 | 同上 |
| GEMM / repeat | 2 | 0.4801 | 0.4929 | 同上 |

copy 四次输出 hash 均为 `f670740d…c49ad8`，GEMM 四次完整输出文件均与 golden `2da121a2…fd2158` 逐 byte 一致。四个进程退出码均 0、stderr 均为空、无 timeout，执行前后所列 artifact hash 不变。原始日志、完整回执和 GEMM 输出保存在 [evidence](evidence/)；[summary](measurement_summary.json)由[只读结果审计程序](summarize_results.py)重算。

launch→wait2 包含 host run 对象创建、参数设置、提交与等待；连续 launch→output sync 还包含 host 状态检查和输出同步。初始化、输入同步、poison、hash、比较、输出文件写入及 teardown 不在前一个区间。完整进程 elapsed 分别为 copy 5.245344/9.272288 s，GEMM 0.289257/0.186364 s。不能由这些时间换算设备 MAC 利用率、TOPS、实际 AXI 带宽或 request latency。

repeat 中后续调用比首调用短，**这里只观察到调用次序相关的 elapsed 变化**；没有控制频率、热态、缓存、CPU 抖动和后台 master，不能归因具体 warming、静态驻留、拥塞或可恢复等待。两次进程启动是功能重启检查，未满足第二独立 session、新随机相位与 paired-block 性能门；不报告 CI、p99、性能收益或残差。

BO 地址在启动前保存，同一进程重复时不重新分配。本次两个进程恰好返回相同 address 数值，copy 的 group_id 高位却随 context 改变；地址由 XRT 返回，不是对 DRAM 物理位置、跨 context 同映射或缓存驻留的证明。已保存相关 DLL 文件 hash 与子进程 PATH/ini；metadata 工具另行认证了实际加载 coreutil 路径，数值探针自身未枚举完整 loaded-module 集合，不能称完整运行时模块 attestation。

## Measurement：校验了什么，仍缺什么

| 项目 | R7 状态 | 实际限制 |
| --- | --- | --- |
| 已知逻辑 bytes copy | **功能通过** | 1 GiB input/output；指令与sync另列。未读 accepted/completed bytes，不能称 traffic counter 校准。 |
| 单 compute | **功能通过** | 仅固定 INT8 GEMM；逻辑 MAC 数不是 compute-active。 |
| 主机空计时窗口 | 2×1000 相邻 steady_clock 读，均值约 23 ns、min 0 | 0 表示分辨率内读数相同；不是零耗时 device no-op，也不从每次 kernel 时间扣除它。 |
| 真实 device 空运行 | **未建立** | 没有来源明确的 zero-work 指令合同。R6 verify、任意零长度/删指令和 XCL_EMULATION_MODE=noop 都不能替代。 |
| device elapsed / traffic / compute-active / request | **未建立** | 安装的通用函数是桩；专用 profiler 缺配套、事件定义和校准。 |
| instrumentation 开关开销 | **未建立** | 没有可用 device profiler；也未将 host logger 与最小记录版本作配对。不将 23 ns 当完整仪表开销。 |
| 时钟/热/背景 | **未控制、未采集运行轨迹** | 仅固定软件及数据；R6 事后 clock/power 字段不升级证据等级。 |

实际 DLL 静态机器码显示 timestamp、traceBufferInfo、readTraceData 是直接返回整数 0，clockFreq 返回浮点 0，debugIpLayout 直接返回且不写输出。该证据关闭这些安装接口，不推导所有 Phoenix PMU 均不可用。[计量报告](measurement_access_research.md)

同 SHA 的 Windows AIE profiler 确有 `XDP_KERNEL` 配置/读取流程；16 个元数据检查中四个其他已装 xclbin 有此名字，但本轮 copy/GEMM 没有。三个限定目录尚未找到匹配的 XDP 插件、xaiengine 与 aie_control_config.json。另一 context 有同名 kernel 不能证明能安全读取当前 workload。ML timeline 还硬编码 1000 MHz，需要实际 timer 域/溢出校准。未为得到一个日志而开启必然缺件的 profiler。

## Red-team → Accept / Refine / Reject

[独立红队](redteam_report.md)在执行前发现并修正了两个具体问题：GEMM 应打开元数据中的 `DPU`，以及连续结果可见时间不能把两个不相连窗口简单相加。修正后重新编译并绑定源码/EXE hash，再执行；没有发生以错误 kernel 名称提交或以旧 binary 重试的设备实验。运行后审计原始 receipts 与全部 GEMM 输出。

- **Accept**：不升级系统，已得到可复用固定 copy 和 INT8 单 compute 的真实设备入口；旧 Phoenix 预构建 GEMM 在本机当前栈、这一输入/shape 下功能兼容。
- **Refine**：优先取得匹配 Phoenix firmware 的 profiler 开发包/示例工程，使同 workload context 的 XDP、metadata、counter/reset/read/timer 合同可执行；同时需可生成合法静态 kernel 变体的 device compiler 接口。
- **Reject 本轮过度主张**：完整测量校准、strong-static 已建立、真实残差为零或非零、BF16/GDN/完整 decode 验收、动态机制收益和 PPA 均无依据。R5 已测 ready 候选维持关闭。

下一问题自然缩小为：**能否把这个已通过数值的 Phoenix kernel 与有定义的设备 profiler、可调静态编译合同接到同一 context？** 最小补件有明确名称和接口，已不再是泛泛的“找一台 NPU”或“安装任意 Python SDK”。若补件不可得，此入口仍可用于 host elapsed 与 compiler/API 功能筛查；不能用增加未校准 simulator 来替代最低观测。

补件齐备后先完成真实 no-op、已知工作 counter 与 instrumentation 配对校准；再冻结 static candidate、背景等级及独立 train/validation/test。沿用 ≥5% 净 elapsed、95% 配对 CI 下界 >0、每条件每 session ≥30 独立 blocks、第二 session 新相位、至少两个非极端干扰及 quiet 平均回退 ≤1% 的门。R7 全部数据是 access/calibration，确认集与干扰/静态/动态比较数均为 0。

历史关系：根进度表更新前，R6 原版已经 byte-exact 保存到 [r7/history/r6_research_progress.md](history/r6_research_progress.md)，R5 snapshot 仍在 r6。由 [lineage](history_lineage.json)与 [checker](check_integrity.py)显式认证，旧 R4/R5/R6 manifest 和根 README 均不改写。
