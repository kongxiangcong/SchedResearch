# R8 下一次取证入口

只缺用户提供的**当前权威 TARS 顶层 checkout 路径**。已发一次简短询问；不再扩扫磁盘，不用 `D:/workspace/llmSched` 或 `riscv_npu_alias` 代替它。拿到路径后先只读，保护 dirty/untracked/.runs。

入口必须能追到 `hardware_specs/tars/`、`src/llmSched/`、`external/tars-npu-ctrl/`；精确历史源码定位见 [来源审计](source_contract_audit.md)。首先读取该根的适用 AGENTS、Git状态与revision，再顺当前 target YAML / active-release / connected RTL 指针核对下列合同。不能只看目录名字认证。

| 核对项 | 要解决的具体分歧 | 可接受的决定 |
| --- | --- | --- |
| C2 与 BF16/FP32 native lowering | 两 cluster 是否存在；M=32,N32/64,K4608/9216 可否导出；允许 split-K regrouping 吗 | 不支持则缩为单cluster控制或明确 target 设计合同；不伪装设备已实现 |
| X 共享及 partial 路径 | 每core单播、DMA multicast、shared SRAM、peer load/store或外存staging究竟是哪一种 | 实际路线选择对应账本；新增link作为资源变更另立baseline |
| VMEM/queue保留区、bank布局、tile/prefetch | 当前4MiB可用范围及合法buffer/静态排程空间 | 重新生成合法地址与候选，不把本轮packed研究分配直接发设备 |
| partial destination-visible与slot release绑定 | DMA done到底表示接受、最后读、目标可读还是退休；blocking API有何保证 | 将已有fence/队列语义绑定到账本，无需默认新增事件网络 |
| counter/trace与同binary控制 | 能否辨认实际bytes、compute-active、request-limit/latency及关键依赖 | 未达最低观测只做screening，不启动硬件收益归因 |

下一最小判别实验是：**若实际路线要求 partial 经过与 X/W 共用的外存/DMA，先让 target-admitted 的两种 mapping、tiling、buffer/prefetch 和现有仲裁进入同资源 strong-static 候选；若 N 分片或已支持的广播/驻留消掉问题，则归 compiler/静态路径。** 只有 selected-static 固定二进制仍在受控共享服务下出现残差，才采具名 transfer 的因果 trace 并寻找有限合法干预。

目前不能选最优 mapping、设定带宽/干扰负载或冻结设备确认集，因为这些取决于上表的入口事实。仅用 Phoenix copy host elapsed 无法解答该问题；继续旧 SDK 适配不会补齐目标合同，所以本轮停止该支线。

目标入口取得前，合同与结构闭环已经完成；不通过添加未校准时序复杂度来继续制造“结果”。R5 通用ready候选保持关闭，尚未测的多cluster空间保留。性能门沿用 [事前计划](experiment_plan.md) 与 [R5 measurement gate](../r5/measurement_gate.md)。
