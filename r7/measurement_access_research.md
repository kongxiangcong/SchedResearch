# R7：旧 Phoenix Windows 栈的计量入口核验

日期：2026-09-05。范围：只读本地 DLL/发布包、冻结源码、接口及计量合同分析；**此子任务没有加载 DLL、打开设备、提交 kernel、设置 profiling 环境变量、启动 ETW 或修改驱动**。设备执行以 R7 主实验报告为准。本报告不产生性能数字。

**结论：当前安装的通用 XRT 设备时间戳/trace 导出是空实现，不能通过调用这些名字获得设备观测。冻结 XRT 源码确有 Windows AIE counter 和 timer 路径，但它依赖成套 XDP 插件、`XDP_KERNEL`、匹配元数据及固件操作合同；这些补件尚未在限定本地目录找到。当前可立即使用的是明确定义的 host elapsed 和主机仪表开销校验。** 这不足以建立 R6 的机制资格，也不说明硬件没有计数器、真实残差为零或静态优化已经足够。

## 1. 研究问题与判别门

| Research Question | Hypothesis | Strong Baseline | Discriminative Experiment | Stop / Next Decision |
| --- | --- | --- | --- | --- |
| 安装 DLL 的时间戳、trace 导出是否有真实实现？ | 导出名可能只是兼容接口，不能凭存在即认定可测 | 以实际后端二进制哈希、导出 RVA 和完整最短函数机器码为准；公开源码辅助解释 | 静态读取 PE 导出地址并检查函数开头；有可执行读路径才做带 sentinel 的只读能力测试 | 若直接 return 或返回常量，关闭这条计量入口，不消耗 kernel 运行 |
| 同版本 Windows AIE profiler 是否提供下一步补件路线？ | 有事件硬件能力，但宿主插件、固件操作、元数据和计量定义缺一不可 | 同版本实现、明确模块/端口/事件与 reset/read 边界 | 先核对插件、`XDP_KERNEL` 与 metadata，再在已验 copy/compute 上开关配对、已知工作校准 | 缺必需件即保持未测试；不得靠 `aie_profile=true` 替代计量验收 |
| 最小可用 instrumentation 能达到什么等级？ | 自有 host 时间戳可筛查 elapsed；不能填设备 cycles、actual bytes 或 request metrics | 固定 BO/input/binary，主机 timer 只包住提交到完成 fence，输出同步/验收分开 | 相邻 timer、固定 copy、单 compute、最小/完整记录开关配对；日志延后落盘 | 只取得 host 时间则停在 device screening；不打开调度机制门 |

以上为来源/接口问题，未重跑 R1–R6。R6 的 5% 净 elapsed、95% 配对 CI 下界、每条件/session 至少 30 paired blocks、新 session、新相位、至少两个非极端干扰及 quiet ≤1% 回退仍由主实验合同负责。仪表可用性不等于这些性能门已经执行。

## 2. 安装二进制：可直接排除的空入口

[`inspect_pe_exports.py`](sources/metering/inspect_pe_exports.py)用 Python 标准库解析文件的 PE export table，保存整文件 SHA256、RVA、文件偏移、forwarder 标记及函数前 32 字节；不调用 `LoadLibrary`。两个 DLL 的记录见 [`local_pe_exports.json`](sources/metering/local_pe_exports.json)。实际函数都是非 forwarder，以下指令已经终止函数；随后 `CC` padding 不属于函数执行路径。

| API | 两个安装后端的最短机器码 | 已核验含义 |
| --- | --- | --- |
| `xclGetDeviceTimestamp` | `33 C0 C3` | `xor eax,eax; ret`，返回零，不读设备 |
| `xclGetDeviceClockFreqMHz` | `0F 57 C0 C3` | `xorps xmm0,xmm0; ret`，返回浮点零，不读设备 |
| `xclGetTraceBufferInfo` | `33 C0 C3` | 返回零、不写输出参数；“成功”值不能解释为已获得 buffer 信息 |
| `xclReadTraceData` | `33 C0 C3` | 返回零、不读设备、不写 trace 数据 |
| `xclGetDebugIpLayout` | `C2 00 00` | 直接 return，不写输出 buffer/长度 |
| `xclGetDebugIPlayoutPath` | `B8 01 00 00 00 C3` | 返回 1、不写路径 |

对象是 `C:\Windows\System32\AMD\xrt_core.dll` 和 `amd_xrt_core.dll`。此结论针对冻结的两份安装文件；未扫描所有其他后端，也未声称后来安装的驱动仍如此。直接返回的函数无须设备 probe 再次确认零；若未来换二进制，应重新读导出/hash。

公开 SHA `42cba83aee86b253c49eccd484646e91d062468d` 的 [Windows `perf.cpp`](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/pcie/windows/alveo/perf.cpp#L14)同样将 timestamp/clock 写为零，并包含带宽常量。**但公开 Alveo `shim.cpp` 的 trace 函数有逻辑，和本机 Phoenix DLL 的空函数不同。** 因此工具报告的 XRT SHA 允许定位公共部分，不能证明 vendor 后端每个实现都与公开 Alveo 文件一致。[公开 trace 函数](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/pcie/windows/alveo/shim.cpp#L2132)

`xrt_coreutil.dll` 的 `get_aim_counter_result`、`get_am_counter_result` 等 C++ 导出也不能绕过缺口。源码依赖具体 debug IP base address、类型/版本与 `device->xread(XCL_ADDR_SPACE_DEVICE_PERFMON, ...)`，并非任意 Phoenix 端口的通用 PMU 接口；本轮未取得该映射和后端读取合同。[debug_ip.cpp](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/common/debug_ip.cpp#L36)

## 3. 可定位的 Windows AIE profiler：补件与语义

冻结源码在 `XDP_MINIMAL_BUILD=yes` 且 Windows 时构建 AIE profile/debug/ML timeline；完整构建分支里的 AIE trace 则在 `NOT WIN32` 下。不能说整个 XRT 没有 Windows AIE profiling，也不能借 Linux AIE trace 教程推定安装能力。[plugin/CMakeLists.txt](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/xdp/profile/plugin/CMakeLists.txt#L5)

Windows [AIE profile 实现](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/xdp/profile/plugin/aie_profile/win/aie_profile.cpp)给出了具体入口：

- core `heat_map` 配置 `ACTIVE_CORE`、group stall、vector instruction 和 program flow；`stalls` 配置 memory/stream/lock/cascade stall。事件名字不证明逐 lane MAC active；完整事件定义及选择 mask、计数触发语义仍需匹配 AIE driver/硬件文档校准。
- shim、memory tile 有 stream running/stalled、TLAST、finished-BD、memory backpressure/starvation 等事件。这些不是已定义的 AXI requested/accepted/completed bytes、request ID、credit 上限或延迟 histogram。将 BD 次数乘 nominal 长度或 running cycles 乘总线宽度仍属推导，除非先证明事件范围、边界、有效字节、padding 和并发路径。
- 配置通过 `XAie_PerfCounterReset`、`XAie_PerfCounterControlSet` 和 event/group/port selection 生成 serialized transaction，然后以 `CONFIGURE_OPCODE=2` 提交 `xrt::kernel(context, "XDP_KERNEL")`。它会写设备配置，**不是零开销只读仪表**。
- 读计数也是一次 `XDP_KERNEL` transaction、BO write/sync、提交/wait，随后分配 4 KiB cacheable BO，sync 后读取偏移 `0xC00` 的 `uint32_t` 结果。寄存器地址使用 `(col << 25) + (row << 20)`，并非由应用任意填地址即可认证可用。
- Windows 实现的 `finishedPoll` 在第一次读取后置 true；`XDP_MINIMAL_BUILD` 分支在结束/flush 时调用 poll，不开普通持续 polling thread。`interval_us=1000` 的公共默认值不代表 Windows 每毫秒采样。该路径最多提供已配置窗口结束时的一次读数；多次微 kernel 的逐次归因需要另立配置/reset/read 合同。[plugin 生命周期](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/xdp/profile/plugin/aie_profile/aie_profile_plugin.cpp#L226)
- 结果只有读出的 32-bit count；源码没有在此完成 wrap 扩展、overflow 认证、复用损失检测或设备/host 时间同步。记录中的 host timestamp 在 polling transaction **之前**采集；不能把它当实际 counter latch 时刻。程序也没有提供所需的同引擎 elapsed cycles 分母。

必需件包括 `xdp_aie_profile_plugin`、`xdp_core`、`xaiengine` 及匹配头文件、带 `XDP_KERNEL` 的硬件 context、`aie_control_config.json` 和相符的 firmware custom profiling op。CMake 明确链接 xaiengine；metadata 构造实际执行相对路径 `read_json("aie_control_config.json", ...)`，虽错误消息写“host executable directory”，工作目录也须显式控制。[AIE profile 构建](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/xdp/profile/plugin/aie_profile/CMakeLists.txt#L27)、[metadata](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/xdp/profile/plugin/aie_profile/aie_profile_metadata.cpp#L39)

限定目录 `C:\Windows\System32\AMD`、`D:\riallto\ipu_stack_rel_silicon_prod`、`D:\riallto\ipu_stack_rel_silicon_1.0` 未找到 `xdp*.dll`、`*xaiengine*` 或 `aie_control_config.json`。这是 [`local_plugin_scope.json`](sources/metering/local_plugin_scope.json)保存的有界文件查找，不是全机器不存在。

R7 SDK 子任务使用安装 DLL 解析全部 15 个已装 xclbin 加下载的 GEMM，共 16/16 成功且未打开设备。四个已装文件确有 `XDP_KERNEL`：`1x4_3.5.0.0-1505`、`1x4_3.5.0.0-1562`、`4x4_3.5.0.0-1506`、`4x4_3.5.0.0-1561`；`validate_phx` 和所选下载 GEMM 均没有。证据见 [`metadata_receipt.json`](sdk/metadata_receipt.json)及 [`metadata/`](sdk/metadata/)。因此是**当前实验 kernel 没有同 context 的 XDP 入口、配套插件仍缺失**，不是整台机器不存在该名字。另一 xclbin 的命名 kernel 不能证明其 profile custom op、安全 buffer 合同或跨 context 读取当前 workload 的能力，暂不执行。

## 4. ML timeline、ERT 时间戳与 ETW 的边界

Windows ML timeline 从 `XDP_KERNEL` 连接的 4 KiB SRAM BO 读取 record timer。记录前 3 KiB 格式是 entry count 加 32-bit ID/32-bit AIE timer low 成对数据；源码 max count 为 383。它假定固件 stub 已写入有效数据，超过上限时不会正常输出记录。JSON 头将 `clock_freq_MHz` **硬编码为 1000**；没有 runtime DVFS 采集或跨 wrap 还原。故即使文件能生成，也要先证明 timer 域、起止 marker 位置、wrap/溢出及固件记录开销，不能直接换算 Phoenix device ns。[ml_timeline.cpp](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/xdp/profile/plugin/ml_timeline/clientDev/ml_timeline.cpp#L45)

公共 `ert.h` 有 `stat_enabled` 和 `cu_cmd_state_timestamps`，注释单位为 ns。但它说的是 driver 记录 command states；相关 timestamp size/helper 在 `__linux__` 下，支持 opcode 列表未包含当前 DPU `ERT_START_DPU`。不能给 Phoenix DPU packet 强开这个 bit 并将内存中的值称设备运行时间；还缺实际 Windows driver 填写合同。[ert.h](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/include/ert.h#L991)

RML 包中有 [`tracelogging.WPRP`](sources/metering/installed_RML_tracelogging.WPRP)，定义 `RMLTraceLoggingProvider` 的 GUID `2369df2f-8be2-4f72-b258-187ef2ade4fe`、128 KiB buffer/64 buffers。文件没有定义 AXI bytes、MAC active 或 request 生命周期字段。安装的 trace DLL 导出也主要是 Vitis/RML host tracing 类；本轮没有 provider schema 或设备事件合同证据。此路线可在将来研究软件阶段时间，但不作为当前 ctypes kernel runner 的硬件计量补件；未启动 WPR。

## 5. 最小局部配置与 instrumentation 校验

可直接推进的版本是主实验自己持有 timestamp 和 raw receipt。建议每个新进程由 `XRT_INI_PATH` 指向项目内明确的关闭配置：[`host_screening_off.ini`](sources/metering/configs/host_screening_off.ini)。不得修改全局或系统目录 `xrt.ini`。公共读取逻辑优先查 `XRT_INI_PATH` 完整文件路径，再查 executable/cwd；配置项读取后可能缓存，进程中切换未必生效，`xrtIniStringSet` 在已使用 key 上会拒绝改变。[config_reader.cpp](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/common/config_reader.cpp#L115)

环境里存在同名布尔 key，例如 `Debug.native_xrt_trace`，其优先级高于 ini，因此采集器应将**相关 profiling 环境项**纳入 software/config receipt；不要打印无关环境变量。当前本子任务仅读取三个具名环境项，全部 unset。

[`native_trace_candidate.ini`](sources/metering/configs/native_trace_candidate.ini)只用于未来补齐 **同版本** `xdp_native_plugin.dll` 和依赖后的候选。`native_xrt_trace` 从 `XILINX_XRT`/默认 runtime 目录动态加载插件，C ABI 的 `xrtRunOpen/Start/Wait` 都在 profiling wrapper 内；缺插件可使加载异常进入 C API error 路径，不能把“开 trace 后调用失败”算 kernel 变慢或后台 profiling 自动成功。[native_profile.cpp](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/common/api/native_profile.cpp#L16)、[module_loader.cpp](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/common/module_loader.cpp#L197)、[C ABI wrapper](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/common/api/xrt_kernel.cpp#L3860)

即使补齐插件，native trace 的 timestamp 是 `xrt_core::time_ns()` 的 host 时钟，sync bytes 来源是调用的 buffer size 参数，不是 AXI 实际完成流量。[native sync logger](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/common/api/native_profile.cpp#L116)

最有判别力的最小校验顺序：

1. **主机空窗口**：连续两个 `perf_counter_ns`，冻结 Python/时钟信息，保存原始差值分布。这仅认证 timer/语言调用地板，不是空设备运行。
2. **真实空设备运行**：只接受编译器/固件已定义且数值/状态可验的 no-op 程序；零长度 BO、未 start 就 wait、verify、任意删减 firmware words 都不能默认等价。`XCL_EMULATION_MODE=noop` 会选择 `xrt_noop` 后端，明确不是物理 NPU 校准。[shim 选择](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/common/module_loader.cpp#L72)
3. **已知逻辑 bytes copy**：固定 BO 与输入，host 提交→已完成 fence 单独计时；之后 output sync 与数值检查分别记录。BO 数据长度可填 logical payload；R6 `traffic` 六类 actual-byte 字段保持 null，直到有实际端口计数。copy 验收不能完成 single-compute 校准。
4. **仪表开销**：同 binary/BO/input 比较只保留两个 host timestamp 与增加阶段 timestamp/缓冲记录的版本，预先随机化配对顺序；不在计时窗口打印/写 JSON。两臂都保留数值验收与错误。计量新增的前后台工作、flush、设备 XDP 命令若有则全部另存并收费。不能以空 timer 中位数机械减掉每次 kernel elapsed。
5. 补齐 AIE counter/timer 后先用已知 copy 和单 compute 逐项核验事件定义、reset/read 边界、counter 宽度、溢出、同一窗口分母、域同步和 instrumentation on/off 影响；通过后再冻结强静态工作量与背景条件。无需为了收集失效通用 trace 再运行设备。

## 6. R6 观测合同映射与决定

| R6 项 | 当前来源支持/本轮状态 | R7 应记录 |
| --- | --- | --- |
| `elapsed_host_ns` | 可由主采集器立即做提交→完成 fence；本报告未执行 | 真实值及 host timer boundary，sync/validation 单列 |
| `elapsed_device_ns` | 已安装通用 timestamp 为 stub；ML timer 缺配套及校准 | null，给出以上具体原因 |
| `traffic` | native sync size/BD count/逻辑 bytes 均不是现成的 requested/accepted/completed 端口计数 | null；logical bytes 放独立字段 |
| `compute_active` | Windows 源码提供 core 活动/向量/停顿事件候选，尚未取得可运行 profiler 与已定义分母 | null；不把 ACTIVE_CORE 直接叫 MAC utilization |
| `request_observation` | 核对的接口没有可用 request trace、限额或延迟 buckets；stall/BD 事件不满足合同 | null；不从 host kernel latency 推 request latency |
| frequency | 通用 clock API 空实现；ML header 1000 MHz 为常量 | runtime frequency 未验证；保留 R6 事后快照级别 |
| calibration | 主机 timer/记录开销可做；真 no-op、单 compute、设备 counter/timer 仍需分别完成 | 按实际完成项填写，不以来源阅读代替 verified |

**Verdict：Refine measurement access；保持动态机制门关闭。** 下一步最小、具体的外部补件是适配当前 Phoenix driver/firmware 的 XDP/AI Engine profiling 开发包或一个含可运行 `XDP_KERNEL`、`aie_control_config.json`、counter/timer 示例及事件说明的项目。如果该补件不可得，R7 固定 copy/compute runner 的合理产物仍是 host elapsed screening 和 kernel/compiler 接口验证，不是“硬件没有机会”的 negative result。

冻结的来源清单见 [`sources/metering/source_manifest.json`](sources/metering/source_manifest.json)。公开完整 archive 及选读文件来自精确 SHA；GitHub tree API 403 和两个初次 raw 路径 404 保留在 receipt，未改写为成功。PE 解析是独立的静态本地证据，不受公开 vendor 后端源码缺失所替代。
