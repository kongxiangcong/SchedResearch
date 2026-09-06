# R6 一手来源核验：从可枚举 Phoenix 到可解释测量

核验日期：2026-09-05。**本机已运行 Phoenix NPU 的厂商搬运自测；这把证据推进到设备功能检查，但尚未建立可校准 GDN、projection 或新调度机制的测量合同。** 本文只解释来源、计量与适用范围；独立设备执行回执见 [evidence/](evidence/)，不将来源阅读算作设备或 RTL 执行。

模型继承 R4/R5 固定 revision；本机 XRT 的源码核验使用工具报告的精确 SHA，而非当前最新版文档。新增下载、失败、SHA256 与 8 项历史来源 hash 复核见 [source_manifest.json](sources/source_manifest.json)，复现程序为 [freeze_source_evidence.py](sources/freeze_source_evidence.py)。历史来源未改动。

## 1. 当前真实可执行对象：XRT 2.17.0 的 verify 和 df-bw

[本机完整报告](evidence/report_all/stdout.txt)识别 `RyzenAI-Phoenix`、XRT `2.17.0@42cba83aee86b253c49eccd484646e91d062468d`。该 SHA 对应公开 [XRT commit](https://github.com/Xilinx/XRT/commit/42cba83aee86b253c49eccd484646e91d062468d)，因此可逐句检查实际版本测试，而不借用新版本 `xrt-smi` 的说明。

### verify：提交和等待检查，不是算术正确性检查

`TestVerify` 对名字含 Ryzen 的设备委托 `TestIPU`。后者使用 `validate_phx.xclbin`，创建 6 个 128 B BO，提交一次 DPU kernel 并 `run.wait()`；没有读取输出并比较数值。因此 [verify PASSED 回执](evidence/vendor_verify/stdout.txt)最多支持这条提交/等待路径未报告错误，不能验收 BF16 GEMM、FP32 recurrence 或模型质量。[精确 TestVerify](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/tools/common/tests/TestVerify.cpp#L18)、[精确 TestIPU](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/tools/common/tests/TestIPU.cpp#L77)

额外发现：`TestIPU` 捕获提交异常时先写 `failed`，随后函数末尾无条件写 `passed`，会覆盖前者。因此验收程序必须同时检查原始 Error、退出状态与执行结果，不能只解析 PASSED。当前保存的 verify 输出未见 Error；此源码缺陷仍降低该测试的证明力。[TestIPU 异常与最终状态](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/tools/common/tests/TestIPU.cpp#L96)

### df-bw：有全量 copy 比较，但 elapsed 和单位必须重新解释

| 源码/本地序列事实 | 测量含义 |
| --- | --- |
| `buffer_size=1024^3`；输入和输出各 1 GiB；`word_count=buffer_size/4` | 是 268,435,456 个 32-bit words 的单次搬运合同，不是 BF16 算术 |
| CPU 对全部输入 words 赋 `rand()%4096`；计时前完成指令和输入 BO sync | 输入填充/上传成本不在打印的 elapsed 内；本轮没有保存输入 BO hash |
| host `high_resolution_clock` 从一次 `kernel(...)` 调用前到 `run.wait2()` 返回后 | 含 host launch/wait 与设备工作；不是独立设备周期计数，也不含后续 output sync/check |
| output sync 后逐 word 比较全部输入/输出，失败时记录 mismatch | PASSED 支持该 copy payload 一致性；不能证明 compute engine 被使用 |
| `bandwidth=buffer_size_gb/elapsedSecs`，其中 `buffer_size_gb=1`，却打印 `GS/s` | 数值是 `1/elapsed`；按源码的 1 GiB payload 可解释为单向逻辑 GiB/s，不能直接当作 decimal GB/s 或 Gsample/s |
| 已安装 `df_bw_dpu.txt` 注释为 shim DMA loopback，只有 COL0/ROW0，一条 IFM BD2 与一条 OFM BD5 | 不能当作整个 4×4 compute array 或所有 shim 的带宽。BD length 字段 `0x10000000` 与 32-bit words×4 的 1 GiB 一致；未解码固件全部 opcode，不声称已观测 AXI 实际 bytes |

来源：[TestDF_bandwidth.cpp 的 buffer 定义](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/tools/common/tests/TestDF_bandwidth.cpp#L20)、[填充/计时/验证/计算 L152–202](https://github.com/Xilinx/XRT/blob/42cba83aee86b253c49eccd484646e91d062468d/src/runtime_src/core/tools/common/tests/TestDF_bandwidth.cpp#L152)、[冻结安装序列](sources/xrt/installed_df_bw_dpu.txt)。这里按源码推导逻辑流量，不用文件注释替代实际计数器。

[首轮 df-bw 回执](evidence/vendor_df_bw/stdout.txt)记录 elapsed `0.359610 s`，原样指标 `2.780787 GS/s`。两者满足上述倒数公式（输出有舍入）；没有据此拟合 R5 的 bandwidth、RTT、outstanding 或计算吞吐。单次 source-loopback 的已知工作可说输入读取 1 GiB、输出写出 1 GiB 的逻辑 payload，但协议 beats、缓存、page behavior、额外指令流量与真正 shared fabric bytes 均未测。不能把两方向相加后称单端口有效带宽。

`TestDF_bandwidth.cpp` 和 `SubCmdValidate.cpp` 未见 `srand`；这不足以认证每次输入相同：未检查整个进程调用链的 `rand` 状态，测试也不导出 seed/input hash。BO 每次重新分配，地址未固定。故它可用于初始可运行性/方差筛查，不能通过 [R5 固定 binary/layout/input 合同](../r5/measurement_gate.md)。

### E0 能力到 R5 测量门的映射

| R5 必要项 | 当前 E0 能力 | 缺口与最小补件 |
| --- | --- | --- |
| 固定 binary/kernel/dtype | 可保存已安装 xclbin 与序列 hash，已执行 loopback | 缺具有明确算术/精度/shape 的可调用 kernel、生成源/编译参数、正确性 oracle；目录里有 BF16 文件名不等于该路径已执行 |
| 固定 layout/input/state | 厂商自测已知 1 GiB shape、全量比较 | 需要同一进程长期复用 BO、输入/state seed+hash、device地址/可追溯映射、warm/cold/reset 合同 |
| elapsed | host launch→wait2 时间 | 设备 start/finish 或有明确误差的计时 API；output-visible 边界与 host-fence 分开 |
| actual bytes | 只能由逻辑 buffer 推导 | 需要定义明确的 requested/accepted/completed bytes 或 bus beats，含背景流量；不要补成固定数值 |
| outstanding/request latency | 厂商测试不输出 | 需要至少一个定义清楚的 request/limit/latency 接口，记录计数器作用域、释放边界、wrap/overflow |
| compute-active | loopback不验证计算 | 需要真正算术 kernel 与其 active/data-starved 等观测；若只有 elapsed，则仅做瓶颈筛查 |
| 频率/热状态 | `examine`打印 H=800、MP-IPU=400 MHz；无温度传感器 | 不是运行期锁频/采样证据。需要可读取实际运行频率与状态的接口；不能假定固定 |
| 功耗 | 报告同时出现 Power=123 W 和 No electrical sensors found | 未认证，排除功耗/能耗分析；本轮未追到足够源码证明它是常量，不以猜测定性为真实或伪值 |
| 背景与强静态对照 | 可进一步执行同自测的粗筛查 | 尚缺可冻结的背景 bytes/phase 及可修改合法 tiling/layout/prefetch 的编译接口；粗筛查不能打开动态机制门 |

设备报告事实见 [report_all/stdout.txt](evidence/report_all/stdout.txt)。这些“未具备”指本轮已验证接口，不是声称 Phoenix 硬件绝无相应功能。

**当前最小需要的是现有 Phoenix 栈可用的配套 host headers/libraries 或 Python binding、与驱动匹配的 kernel 编译/载入方法、可验证输入/输出的示例，以及相关计量接口定义。** 先实例化固定 copy 和单 compute 合同，再决定是否能承载 GDN。无需先装完整模型，也不建议为了得到更多计数器盲升驱动/SDK。

## 2. 真实 GDN 的跨层、跨 token 状态边界

冻结模型为 `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`，实现为 Transformers `f62dc9bf2c90353b442a56e74391fbb8c689b55e`。官方 config 的 32 文本层明确列出 24 个 GDN 和 8 个 full attention；每个 GDN 是 32 value heads、16 q/k heads、128×128 recurrent state，并声明 `mamba_ssm_dtype=float32`。[固定 config](https://huggingface.co/Qwen/Qwen3.5-4B/blob/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a/config.json)

下表是 B=1、普通 cached decode、未量化状态的**来源公式**，不是实测分配量或内存交通：

| 常驻逻辑状态 | 公式 | 容量 |
| --- | --- | --- |
| 一个 GDN head | 128×128×4 B | 65,536 B = 64 KiB |
| 一层 GDN 的32 heads | 32×65,536 B | 2,097,152 B = 2 MiB |
| 24层全部 recurrent state | 24×2 MiB | 50,331,648 B = 48 MiB |
| 一层 conv state，假定 projection输出BF16 | (2×16×128+32×128)×4历史槽×2 B | 65,536 B = 64 KiB |
| 24层 conv state，同上精度条件 | 24×64 KiB | 1.5 MiB |
| 8层 GQA KV，context=L，假定BF16 | 8×2(K,V)×4 KVheads×256×L×2 B | 32 KiB×L；L=4096时128 MiB |

batch、beam、并发 sequence 按独立 cache 数扩大；权重、norm/FFN临时量、live activation、allocator padding、speculative rollback 与视觉路径均不在上述数值内。conv 缓存沿输入实际 dtype 创建，recurrent 沿传入 recurrent tensor 创建；不能将全模型 BF16 dtype强加给 FP32 recurrent state。[cache 创建与更新源码](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/cache_utils.py#L1017)、[FP32 recurrence与state shape](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L450)、[GQA cache更新](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L797)

在该普通生成路径中，下一 token 先依赖当前完整前向的 logits 和采样/argmax；前向内部按层依次更新 hidden states，各层 cache 以 layer_idx 区分。于是同层 state 的两个相邻 token 更新之间，通常还有余下层、最后 norm/head/token选择和下一 token 的前置层。**四个真实 decode token 的所有层输入不能像 R5 那样同时预先备好。**[层执行循环](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/models/qwen3_5/modeling_qwen3_5.py#L1289)、[标准 generation循环](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/generation/utils.py#L3017)、[token选择/拼接](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/generation/utils.py#L3060)

R5 的每core 73,760 B resident控制由一个64KiB head加4token prepared输入/输出组成；两个core仅处理2/32 heads，而且没有其他层共享RF。[R5实验报告](../r5/experiment_report.md)。因此其7%–24%静态收益说明该切片原lowering有可删除交通，不能证明完整decode能做同样连续4步驻留。

同时，48 MiB总state**不证明每token必须从DRAM读写48MiB**，也不证明partial resident毫无价值。合法strong static可以保留部分head、使用SRAM层次、layer/sequence partition或其他真实支持的缓存计划；它必须支付其他工作占用、保存/恢复和可访问性成本。框架 `mark_static_address`/in-place cache仅承诺软件张量地址与语义，不承诺物理RF驻留。实际需要编译器allocation/spill报告、kernel间持久性合同、跨层存活区间和设备traffic，才能区分被迫spill与可改进的memory planning。[cache源码](https://github.com/huggingface/transformers/blob/f62dc9bf2c90353b442a56e74391fbb8c689b55e/src/transformers/cache_utils.py#L1033)

prefill、teacher-forced已知token、speculative draft/verify与普通逐token采样的可用输入不同，若选择它们应另立合同。不能用prepared-token片段替换上述跨token依赖以获得驻留收益。

## 3. Riallto 与现有旧 Phoenix 栈的关系

冻结 `AMDResearch/Riallto v1.1@74a26aade2c2762e2854d5ab78f01d180eaeaead` 的README区分 Lite（预构建示例运行）和 Full（自定义构建），其Windows快速入门列的是driver `10.1109.8.128`。这与本机报告的旧driver `10.1109.8.110`不同，不能把v1.1教程环境默认当作当前已安装环境。[固定Riallto README](https://github.com/AMDResearch/Riallto/blob/74a26aade2c2762e2854d5ab78f01d180eaeaead/README.md)

`AppRunner`需要成套 xclbin、firmware sequence和可选handoff metadata，用匹配的 `pyxrt` 建context，`call()`等待并检查完成状态，buffer同步单独暴露。这可作为固定BO/输入/launch边界的参考，但所读API没有直接提供R5要求的request latency/outstanding/compute-active集合。现有 `D:/riallto` 是driver/RadeonML发布包目录，不能仅凭目录名认证已安装该Python框架。[固定 AppRunner](https://github.com/AMDResearch/Riallto/blob/74a26aade2c2762e2854d5ab78f01d180eaeaead/npu/runtime/apprunner.py#L79)、[调用与同步](https://github.com/AMDResearch/Riallto/blob/74a26aade2c2762e2854d5ab78f01d180eaeaead/npu/runtime/apprunner.py#L512)

官方FAQ将Riallto定位为探索/教学，说明有closed-source elements；研究编译器时指向MLIR-AIE/MLIR-AIR，部署模型时指向Ryzen AI Software。[AMD Riallto FAQ](https://riallto.ai/faq.html)。这是后续工具选择的边界，尚不是迁移建议；本轮未安装或升级任何上述完整栈，也未把现代XDNA2教程能力推定给Phoenix。

## 4. Arm公开文档与Gemmini公开RTL能证明什么

Arm U85 TRM与CMSIS资料提供请求stall、outstanding-limit stall、AXI latency buckets及MAC active等分类。CMSIS driver调用需要具体target提供register base、IRQ、compiled command stream和region base pointers；其Vela编译输入/region规划可以定义静态合同，但阅读/编译driver不等于执行U85。U85所述TOSA integer profiles也不等于BF16/FP32 Qwen图已合法lowering。本机没有因为存在这些资料就得到Arm设备或Arm RTL。来源为 [冻结 U85 TRM](https://documentation-service.arm.com/static/67b5ba01ce2747241fce860f)、[CMSIS target/command stream说明](https://github.com/ARM-software/CMSIS-Ethos-U/blob/79d0fccfe59cab7fd0cab97c65050d2824c5269f/source/README.md#L49)。TRM本轮web读取失败，已核对R5本地PDF hash，未篡改为在线成功。

Gemmini `8c3f9923a44a2fe2c7930587be297d6d4f8c09ca` 是可构建的公开Chisel设计，以下是**明确配置的来源事实，而不是本轮RTL执行结果**：

| 来源配置/接口 | 已确认与限制 |
| --- | --- |
| `Configs.scala::defaultConfig` | INT8输入/权重、INT32 accumulator，16×16 array，256 KiB scratchpad，4 single-port banks，64 KiB accumulator，16 memory in-flight，64B最大DMA，128bit bus；不能把这些代入Phoenix或R5 BF16参数 |
| `ConfigsFP.scala` | 同revision确有FP32、FP16和BF16配置；BF16为Float(8,8)输入/权重、Float(8,24)accumulator。其基础FP array是4×4，另有BF16 8×8变体；应各自生成硬件和software header并验算，不能复用INT8吞吐 |
| `CounterFile` | 可配置event/external counters、snapshot、reset；external宽32bit。RDMA/WDMA active/TL-wait、EXE_ACTIVE等名字必须追到接线条件 |
| `ExecuteController` | EXE_ACTIVE接`control_state==compute`；这是控制器状态计数，不自动等于逐lane实际MAC active |
| `XactTracker`与`DMA` | RDMA_TOTAL_LATENCY累加valid entries，WDMA_TOTAL_LATENCY累加busy transactions，是outstanding占用积分；不是latency histogram，更不是互斥关键路径stall |
| `DMA` bytes | RDMA_BYTES_REC每个D-channel fire累加`1<<size`。size来自transaction，源码另有`edge.last(tl.d)`。多beat必须用waveform核验计量：例如64B transaction/16B beat时，直接按每beat累加64可能是4倍。此为源码风险推导，未宣称已跑RTL确认bug |

来源：[defaultConfig](https://github.com/ucb-bar/gemmini/blob/8c3f9923a44a2fe2c7930587be297d6d4f8c09ca/src/main/scala/gemmini/Configs.scala#L21)、[BF16/FP配置](https://github.com/ucb-bar/gemmini/blob/8c3f9923a44a2fe2c7930587be297d6d4f8c09ca/src/main/scala/gemmini/ConfigsFP.scala#L87)、[CounterFile](https://github.com/ucb-bar/gemmini/blob/8c3f9923a44a2fe2c7930587be297d6d4f8c09ca/src/main/scala/gemmini/CounterFile.scala#L75)、[EXE_ACTIVE](https://github.com/ucb-bar/gemmini/blob/8c3f9923a44a2fe2c7930587be297d6d4f8c09ca/src/main/scala/gemmini/ExecuteController.scala#L1003)、[RDMA latency](https://github.com/ucb-bar/gemmini/blob/8c3f9923a44a2fe2c7930587be297d6d4f8c09ca/src/main/scala/gemmini/XactTracker.scala#L94)、[DMA回传与计数](https://github.com/ucb-bar/gemmini/blob/8c3f9923a44a2fe2c7930587be297d6d4f8c09ca/src/main/scala/gemmini/DMA.scala#L289)。

若执行公开RTL最小机制微测试，仍需冻结完整Chipyard及其Rocket Chip/Chisel/HardFloat等submodules、Java/Scala构建链、Verilator+C++工具链、RISC-V编译工具链、Gemmini软件与生成参数header，以及SoC内存模型。官方流程为Chipyard `build-setup.sh`，生成 `GemminiRocketConfig` 的Verilator模拟器与baremetal测试binary；debug目标可导出waveforms。当前保存的若干Scala文件不构成该完整环境。Spike可做功能检查，官方明确它不能给准确性能/剖析指标。[Gemmini构建与Spike边界](https://github.com/ucb-bar/gemmini/blob/8c3f9923a44a2fe2c7930587be297d6d4f8c09ca/README.md#L16)

最小有价值的RTL实验是固定明确配置，用单beat/多beat已知长度DMA、请求上限与返回backpressure、同bank/异bank合法地址对照，检查A/D handshake、source ID、credit释放、bytes以及consumer可见时间；先验证counter，再使用counter。它可证伪某个计量或握手规则，不能据此声称校准真实Phoenix的DRAM/NoC/热态、完整Qwen、或面积功耗。发现本机真设备后，本轮没有为了增加证据等级而安装庞大Chipyard栈。

## 5. 来源侧下一决定

**Refine measurement，保持R5动态候选关闭。** 当前可以确认设备copy路径能够执行，且源码已经揭示自测标签和计量的具体限制；不能由此判断强静态之后真实残差为零或非零。下一步先让本机合同可复现、可观测，并用目标实际支持且数值通过的kernel做隔离/受控干扰与合法静态对照。只有测量门通过，才讨论剩余损失是否可被有限因果干预恢复。

来源访问限制均保留：3个GitHub API tree请求403 rate-limit；Arm header和XRT设备query的初次路径请求404；随后用网页目录定位了所需模型、Riallto runtime、Gemmini配置和精确XRT测试文件。失败的Arm header/设备query未用于主张PMU或功耗实现；没有扫描外部私库、获取真实权重、执行官方模型或运行RTL。
