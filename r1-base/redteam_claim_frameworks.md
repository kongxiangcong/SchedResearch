# TARS 编译器—硬件协同研究方向：技术红队与权利要求骨架

日期：2026-09-01

定位：内部科研选题与专利交底前的技术红队；不是法律意见，也不作新颖性、创造性或自由实施结论。

## 0. 先给结论

从 10 个候选中，建议保留 5 个彼此主要创新载体不同的方向：

1. **Descriptor 原子配置的 VMEM 相位/XOR 地址重映射器**：创新载体是 VMEM/TMU 地址通路；最贴近已经复现的 TARS 映射矛盾，原型成本最低，建议最先做。
2. **带代际租约检查的 VMEM ping/pong 生命周期硬件**：创新载体是 VMEM 控制器中的租约表、状态机和完成标签；解决“编译已证明、硬件未强制”的复用安全缝隙。
3. **面向 DDR-resident KV 的 3D 堆叠存储器逻辑层 attention-window engine**：创新载体是 3D memory logic die；论文空间大、代价和先例风险也最大。
4. **VMEM-bank-coupled 的可分区 32×32 MXU**：创新载体是 PE 阵列、累加器和输入网络；能针对 decode/tail 利用率，但通用“可重构 systolic array”先例极密集。
5. **代际标记的双核流式交换/归约硬件**：创新载体是 core-to-core 数据链路、FIFO 和归约单元；补上 TARS 只有同步链路、没有数据链路的架构缺口，但需避开通用 NoC/多芯粒映射先例。

若只能押一个近期专利/论文原型，选方向 1；若要一个更偏体系结构顶会、允许做较重模拟的方向，选方向 3。方向 4、5 不宜宽泛声称“可重构阵列”或“编译器映射互联”，必须把权利要求收窄到 TARS 的 VMEM bank-pair、Descriptor 原子提交和代际执行合同。方向 2 的价值取决于未来是否允许 DMA/计算乱序或多 outstanding；在当前单 outstanding DMA 下，它可能只是一项安全机制而非性能贡献。

## 1. 证据边界与统一工作流

### 1.1 本文使用的 TARS 当前事实

- 当前 target 描述两个 core；cluster 级共享一个 DMA，唯一显式 core link 是 controller synchronization，而不是数据链路（`hardware_specs/tars/target_hardware_spec.yaml:6-39`）。KV cache 的正式 target 选择是 DDR、LBHSD、BF16（同文件 `:40-66`）。
- 每核 VMEM 为 4 MiB、22-bit byte address、8 bank/4 bank-pair；ACT/WGT/OUT 为 64B IWO pair access，PARAM/DMA 为 32B PD single-bank access（`hardware_specs/tars/modules/vmem.yaml:3-97`）。
- typed hardware spec 写的是 7 offset bits、3 bank bits、12 row bits；连接的 TMU RTL 却固定执行 `physical_addr = {addr_linear[7:5], addr_linear[21:8], addr_linear[4:0]}`，并明确把连续 64B 逻辑地址轮转到四个 bank-pair（`external/tars-npu-vpu/rtl/tmu/src/data_plane/tmu_addr_remapper.sv:1-28`）。这是已复现的 authority/RTL 矛盾，不等于已经发现硅后错误。
- VMEM 每 bank 的仲裁中 IWO 是 fixed-priority slot，PARAM/DMA 位于 round-robin slots；IWO pair grant 要同时拿到相邻两 bank（`external/tars-npu-vpu/rtl/vmem/src/vmem_controller/vmem_arbitration.sv:340-385`）。因此 bank phase 会直接影响 IWO 与 PD 的阻塞机会。
- MXU 当前是固定 32×32、只列出 weight-stationary；编译约束要求 M/N/K 均为 32 的倍数（`hardware_specs/tars/modules/mxu.yaml:3-32`）。
- DMA 当前只有 1 channel、32B beat、12.8 Gbps、最多 1 outstanding；不支持 inter-core，也不支持 DDR gather（`hardware_specs/tars/modules/dma.yaml:3-27`）。
- Controller 只声明静态 Descriptor delivery，数据 route 只列 DDR↔VMEM；跨核侧只有 6 dependency/signal slots（`hardware_specs/tars/modules/controller.yaml:3-51`）。
- Controller reference model 中 `GemmSublayerPlanner` 仍自行决定 K chunk 和 VMEM layout，并在 `_binding_for_sublayer` 中覆盖 ACT/WGT/OUT/PARAM 的 VMEM base（`external/tars-npu-ctrl/ref_model/tars_ref/core/sublayer_planner.py:28-80,182-199,285-324,445-456`）。这证明当前 reference-model owner seam 尚未闭合，不证明连接 RTL 一定执行同一覆盖。
- 当前冻结的 Descriptor 0x8 v1.2 是不可静默重解释的 active release line；终点只到 `rtl_handoff_package_ready`，不是 RTL functional acceptance（`docs/descriptor/descriptor-v8-0x8-v1.2-task-sync.md:1-40,51-53`）。
- 2026-09-01 的最小 Descriptor wire 是**已接受的 planning decision**，不是 active authority：其中 `PhysicalMemoryPlanIR` 被指定为 placement/lifetime/slot/epoch/bank proof 的唯一 owner，提议用一个 `vmem_mirror_step` 推导 pong，并要求后续 codec/Controller/RTL/numerical/Hardware Admission 全部另行验证（`.scratch/llmsched-compiler-owned-sublayer-vmem-wayfinding/evidence/accepted-minimal-descriptor-wire-contract-2026-09-01.md:1-26,28-69,81-110`）。

这些状态必须分开：**planning contract ≠ active Descriptor bytes ≠ Controller agreement ≠ connected RTL agreement ≠ Hardware Admission**。本文的“缺陷”有三种：已复现的映射矛盾、当前规格明确缺少的硬件能力、尚未闭合的安全/owner seam；不会把它们一律写成已发生的芯片 bug。

### 1.2 一个贯穿五个方向的例子

统一用“一层 4096-token bound 的 autoregressive decode”作思考实验：

```text
当前：DDR 中 K/V
   -> cluster0 单共享 DMA
   -> core0/core1 各自 VMEM 窗口
   -> TMU/MXU/VPU 完成 QK、softmax、AV
   -> DDR/同步事件交换中间结果
   -> 输出投影 GEMM
```

checkout-local 部署研究记录称，最大 bound 下一个 contiguous K/V value 可达到 4,194,304B（`docs/hardware/compiler_deployment_execution_gap_plan.md:31-39`）；这恰好等于当前每核整个 4 MiB VMEM，而实际还要容纳 Q、score/window、输出和参数。因此下文不把“把完整 KV 常驻 VMEM”当可行基线，而比较 transient window、near-memory reduction 和跨核流式处理。

该 checkout-local 文档同段还沿用了 `126,976B` ACT aperture，而 live typed VMEM 已是 4 MiB；本文**不采用这个旧 aperture 数值**，只把 `4,194,304B` workload-value size 当待当前 case artifact复核的动机数据。D3 进入正式实验前必须从同一 source/case 重新计算 KV bytes，不能靠这份规划记录定量定案。

## 2. 10 个候选的漏斗

评分：5 为高；“先例重叠”越高越危险；“原型成本”越高越昂贵。

| # | 候选 | 硬件载体 | TARS 针对性 | 硬件实质 | 先例重叠 | 原型成本 | 红队决定 |
|---|---|---|---:|---:|---:|---:|---|
| C1 | Descriptor 原子配置的 VMEM phase/XOR remapper | 地址重映射器、shadow CSR、bank phase latch | 5 | 4 | 4 | 2 | **保留 D1**；已有 TARS 特定矛盾和仲裁证据 |
| C2 | 代际 VMEM lease/scoreboard | VMEM lease table、range comparator、completion tag | 5 | 4 | 3 | 3 | **保留 D2**； correctness 载体与 D1 不同 |
| C3 | 3D-stack logic-die KV attention window | vault-local MAC/reduction、logic-die network | 5 | 5 | 5 | 5 | **保留 D3**；论文价值高，专利范围必须很窄 |
| C4 | 可分区/多 dataflow 32×32 MXU | PE partition、crossbar、accumulator banks | 4 | 5 | 5 | 4 | **保留 D4**；仅保留 bank-coupled 窄版本 |
| C5 | 双核直接 stream/gather/reduce fabric | core link、FIFO、reducer、credit/epoch | 5 | 5 | 5 | 4 | **保留 D5**；不能只说“编译映射 NoC” |
| C6 | Descriptor template/loop expansion engine | microcode/template expander | 3 | 4 | 5 | 2 | **淘汰为主方向**；VTA、字典压缩、FEATHER/MINISA 太近，且单 Descriptor 当前并未超过 512-word buffer |
| C7 | counter-feedback 的备用 plan selector | counter、plan table、bounded selector | 3 | 3 | 5 | 3 | **淘汰**；若只剩“编译生成多方案、硬件选最好”非常通用，SAGAR/SARA 等已有自适应映射思想 |
| C8 | 3D thermal sensor + compiler placement | TSV/stack sensor、throttle/placement controls | 2 | 4 | 4 | 5 | **并入 D3 的 dependent feature**；单独方向缺少 TARS 温度证据，容易变成通用 thermal-aware scheduling |
| C9 | MBIST fault-map 驱动的坏 bank/core 降级映射 | fault map、spare/remap mux | 2 | 4 | 4 | 4 | **储备**；没有当前故障率/坏 bank blocker，先例和可靠性工程过密 |
| C10 | per-tile mixed-precision overflow detect/replay | overflow detector、replay buffer、precision mode | 2 | 4 | 5 | 4 | **淘汰**；未见 TARS 因溢出导致的 causal defect，混合精度与 replay 先例密集 |

五个保留方向之所以不重叠：D1 决定“逻辑地址映到哪个物理 bank”；D2 决定“某代数据何时可覆盖”；D3 改变“KV 在哪一级存储上被计算”；D4 改变“MAC 阵列怎样分区”；D5 改变“两个 core 怎样传数据/归约”。

## 3. D1 — Descriptor 原子配置的 VMEM 相位/XOR 地址重映射器

### 3.1 一句话判断

这是当前最值得先做的方向：它从一个已复现的 TARS typed-authority/RTL 映射矛盾出发，增加真实地址通路硬件，让编译器只在有限合法集合中选择配置；但“XOR bank hashing”本身先例很老，不能把宽泛 remapping 当创新点。

### 3.2 硬件新增/改变的实体

在每核 TMU→VMEM 地址入口增加 `ConfigurablePairRemapper`：

- 对 22-bit logical byte address 做**可逆、白名单化**的 bit permutation/XOR；bank-pair select 可以与若干 row bits XOR，32B offset 和 64B pair 原子性保持不变。
- 配置至少含 `mapping_mode`、`pair_phase`、`xor_mask_id`、`mapping_epoch`；不是任意软件可写 LUT，而是少量综合时固定的合法模式。
- 使用 active/shadow 两套寄存器；仅在 Descriptor/sublayer commit 边界原子切换，in-flight 请求继续使用旧 epoch。
- 请求和返回路径携带 `mapping_epoch`，旧 epoch 清空前不得覆盖 active configuration。
- 可选增加每 bank/pair 的 `grant_wait_cycles` 与 `collision_cycles` 计数器；计数器是验证工具，不是核心权利要求必需项。

统一例子中，编译器为 QK window 的 ACT/WGT/DMA 访问计算四个 pair phase，硬件在该 sublayer commit 时切到 mode 2；下一 AV window 可以原子切换 mode 1，物理数据布局由同一映射 epoch 解释。

### 3.3 编译侧只作为控制/生成器的部分

编译器：

1. 从绑定的 hardware spec 读取**有限模式集合**和每个模式的精确方程；
2. 根据已证明的并发访问机会，枚举有限 phase representative；
3. 以 `(collision_count, padding_bytes, logical_base_tuple)` 选一个 plan；
4. 把 mode/phase/epoch 和可选 certificate 写入新 Descriptor profile；
5. 不读取 RTL、不在 runtime 搜索、不重新解释硬件地址。

核心效果由 remapper、原子配置和 epoch 隔离硬件产生。即使没有编译器，硬件仍能接收合法配置并确定性映射；因此交底书不应把“编译算法优化 bank conflict”写成独立发明主体。

### 3.4 要解决的具体 TARS 缺陷

- typed spec 与连接 RTL 现有映射方程不一致，导致 compiler bank proof 被阻断。
- 当前连接 RTL 是一个固定 wiring permutation；编译器能做的只有改 logical base/padding，无法改变 bank phase 的映射族。
- IWO 对 PD 有 fixed priority，ACT/WGT/OUT 又要求相邻 bank-pair 同时 grant；坏 phase 会让 DMA/PARAM 受阻，或让 IWO pair 等待。
- planning 已定义 bank contention 应作为 placement cost，但没有硬件可编程映射实现去消费该选择。

### 3.5 可主张的技术骨架

以下只是交给专利代理人继续检索/扩写的工程骨架。

**方法独立项骨架**：

> 一种用于多 bank 片上存储器的访问方法，包括：接收与一个硬件任务描述符绑定的映射配置；在前一映射代的未完成访问归零时将 shadow 配置原子提交为 active 配置；对任务的逻辑地址中至少一个 row bit 与 bank-pair selection bit 执行所选白名单变换，同时保持 byte offset 及双 bank 原子访问约束；按变换后的物理 bank-pair 发起访问；并使用映射代标记把返回响应与提交时的配置关联。

**装置独立项骨架**：

> 一种加速器，包括 Descriptor commit 单元、active/shadow 映射寄存器、可配置可逆 remapper、映射代计数器、相邻 bank-pair 约束检查器以及多 bank 仲裁器；其中 commit 单元被配置为仅在前一映射代满足 drain 条件时切换映射。

**可选从属限定**：

- 配置来自综合时固定的 1/2/4/8-bank 或 XOR-mask whitelist；非法模式 fail closed。
- ACT/WGT/OUT 的 64B 请求保持相邻两 bank，PARAM/DMA 保持 32B 单 bank。
- Descriptor 同时携带 compiler-derived bank-footprint certificate，硬件只检查 mode ID/range/epoch，不执行通用搜索。
- 基于 bank wait counter 在任务结束时产生测量 receipt，但 counter 不改变本次任务配置。
- 同一 physical payload 的 producer 和 consumer 必须绑定相同 mapping epoch。

### 3.6 最小原型

1. RTL：把 `tmu_addr_remapper.sv` 改成 4–8 个白名单模式，加 active/shadow CSR 和 epoch drain；不先修改整个 VMEM datapath。
2. 模型：在 `TargetHardwareSpec` 中显式编码每个模式，修正当前 typed/RTL contradiction；扩展 logical-bank cost model。
3. workload：构造 ACT+WGT+DMA 三种并发 pattern，再选 20–50 个真实 GEMM/SDPA sublayer trace。
4. 验证：形式检查 bijection、地址范围、64B pair preservation、旧 epoch response 不被新 epoch接收；RTL 与 Python address oracle 逐地址相等。
5. 综合：比较 fixed remapper 与 configurable remapper 的 area、Fmax、动态功耗。

### 3.7 关键指标与反证实验

主要指标：IWO pair wait cycles、PD starvation cycles、bank/pair collision cycles、有效带宽、sublayer cycles；次要指标：mux/CSR 面积、critical path、切换 bubble、编译搜索时间。

预注册的 go/no-go 例子：在真实 conflict-bearing corpus 上，至少一个稳定模式使总 stall 降低 ≥15%，端到端周期降低 ≥5%，而中性 workload 回退 <1%；remapper 不进入 VMEM critical path或 Fmax 下降 <2%。这些是研究阈值，不是当前已测结果。

必须做的反证：

- 固定 remap + 仅移动 base/padding 是否已经达到同样结果？若是，硬件无必要。
- 随机/轮转/XOR 三类模式是否在真实 trace 上只有 synthetic benchmark 获益？
- 把 DMA/PARAM 关掉后收益是否消失？若消失，主张应缩到 IWO/PD 共存，不可声称普适 bank 优化。
- 多模式 mux 是否导致 Fmax/energy 损失大于 stall 收益？
- 若硬件 owner 最终判定 typed spec 只是文档错误、固定 RTL 正好满足所有 workload，则“修复矛盾”不能单独构成研究贡献。

### 3.8 主要先例与重叠风险

- [Configurable XOR Hash Functions for Banked Scratchpad Memories in GPUs](https://doi.org/10.1109/TC.2015.2479595)：直接覆盖 configurable XOR bank hashing，重叠**高**。
- [An adaptive address mapping function for a bank-based multi-ported memory](https://doi.org/10.1587/elex.14.20170373)：自适应地址映射，重叠**中高**。
- [Optimizing operation and data mapping for CGRA with multi-bank memory](https://doi.org/10.1145/1755951.1755892)：编译/映射与 multi-bank memory 协同，重叠**中高**。

可能保住的窄核心不是 XOR 本身，而是：**Descriptor-bound atomic mapping epoch + TARS 64B adjacent-pair preservation + compiler 的有限并发证明 + producer/consumer 同代硬件检查**。

### 3.9 为什么可能不成立

- 地址 mode 只能改变冲突位置，不能增加端口或带宽；真实瓶颈可能是单 DMA 或 MXU。
- bank mapping 配置切换要求数据 producer/consumer 一致，可能需要搬迁或双重解释，收益被切换 bubble 抵消。
- XOR/remap 和编译 bank placement 均有密集先例，若权利要求没有 TARS 特定原子提交/代际约束，很可能过宽。
- 当前 mapping contradiction 也许最终只是 authority 文档修复，不需要新硬件。

## 4. D2 — 带代际租约检查的 VMEM ping/pong 生命周期硬件

### 4.1 一句话判断

把 planning 中的 `(partition_revision, core, layer, slot, epoch)` 从“编译证明”升级为硬件执行合同，能形成清楚的装置型成果；但当前 DMA 只有一个 outstanding、Controller 可能严格顺序执行，因此必须先证明真的存在异步复用窗口或未来性能需求。

### 4.2 硬件新增/改变的实体

每核 VMEM controller 增加小型 `Generation Lease Table`（GLT）：

- 每项记录 `role, base, span, slot, epoch, producer_state, reader_count, mapping_epoch`。
- 状态机至少包含 `FREE → FILLING → READY → READING → RELEASE_PENDING → FREE`；OUT 可使用 `DRAINING → STORING` 分支。
- DMA load/store、TMU/MXU/VPU 请求与 completion 均携带短 generation tag。
- range comparator 在新 lease commit 时检查与所有 live span 的 overlap；同一 slot 只有在上一 epoch 的最终读者和晚到 completion 清空后可再次进入 FILLING。
- stale completion 不得更新 READY/FREE；它触发 poison/error receipt，而不是静默归属新 epoch。
- GLT 只缓存/执行编译给出的 span 和顺序，不自行重新分配地址。

统一例子中，K-window `s` 的 ACT/WGT 用 ping/epoch `e` 计算时，DMA 可以往 pong 填 `s+1`；GLT 在收到 `s` 的最后 compute-read completion 前禁止 `s+2` 覆盖 ping。

### 4.3 编译侧只作为控制/生成器的部分

- `PhysicalMemoryPlanIR` 决定 base/span/mirror_step/slot/epoch 和合法生命周期。
- Descriptor/launch package 只投影 `LEASE_ACQUIRE/READY/RELEASE` 所需的最小字段或事件 ID。
- 编译器生成静态 schedule 和 proof digest，不实现 runtime scoreboard，不修复 late completion。
- 硬件是最终执行者：检查范围、转换状态、拒绝错误 generation、发布 completion receipt。

### 4.4 要解决的具体 TARS 缺陷

- planning contract 已明确 ACT/WGT ping/pong、OUT singleton 及 `slot=s mod 2, epoch=floor(s/2)`，并要求 late old-epoch completion fail closed（`.scratch/llmsched-compiler-owned-sublayer-vmem-wayfinding/evidence/ping-pong-mirror-slot-lifecycle-2026-08-27.md:15-30,32-76,78-111`），但它仍是 planning evidence。
- 当前 active Descriptor 不能静默加入这些语义；2026-09-01 wire 提议也尚未通过 Controller/RTL/Hardware Admission。
- Controller reference model 仍根据 ordinal 自行创建 slot/base 并覆盖 binding，存在 compiler owner 与 consumer behavior 分叉。
- 当前设备 completion/queue 生命周期尚未形成 fresh submission receipt；checkout-local gap audit 还记录 fresh epoch/receipt 未实现（`docs/hardware/compiler_deployment_execution_gap_plan.md:149-166`）。

这不是“已观察到数据损坏”的断言，而是：**未来一旦为了性能引入 preload/compute/store overlap，现有证据不足以证明复用安全**。

### 4.5 可主张的技术骨架

**方法独立项骨架**：

> 一种片上存储区复用方法，包括：从任务描述符装载包含地址区间、槽号和代号的租约；在硬件租约表中将区间从空闲态转换为填充态；仅在匹配代号的填充完成后允许计算读；累计匹配代号的读完成；在全部读完成后释放该代；以及当旧代完成在新代 acquire 后到达时阻止该完成改变新代状态并生成错误状态。

**装置独立项骨架**：

> 一种加速器存储控制器，包括租约表、地址区间重叠比较器、代际标签传播网络、读者计数器、完成过滤器及错误/poison receipt 单元，其中租约表不选择地址而执行由外部任务描述符声明的物理区间生命周期。

**可选从属限定**：

- ACT/WGT 共享一个 mirror step、分别具有 ping/pong lease；OUT 为独立 singleton lease。
- generation 是 partition revision、core、layer、slot、epoch 的压缩或哈希表示，并有 wrap-around drain 规则。
- DMA fill 可与另一 slot 的 compute 重叠，但同 slot overwrite 必须等待 `compute_read_end`。
- OUT store completion 必须早于下一 output drain；否则硬件暂停或 poison。
- lease 与 D1 的 `mapping_epoch` 联合绑定，防止同一数据在 producer/consumer 间采用不同 remap。

### 4.6 最小原型

1. 在 Controller/VMEM RTL 边界实现 4–8-entry GLT；先只覆盖 ACT、WGT、OUT 三种 role 和两 slot。
2. 在 reference model 中替换 `_vmem_layout` 的自主选择：它只能装载/检查 compiler plan，不再重新寻址。
3. 生成 4 类 adversarial trace：正常 overlap、同 slot 过早 overwrite、旧 epoch late completion、tag wrap-around。
4. SVA 证明：live overlap 禁止、旧 completion 不改变新状态、无错误 trace 最终释放、无 tag 泄漏。
5. 在单 outstanding DMA 基线和模拟 2/4 outstanding 的 future mode 下分别量化价值。

### 4.7 关键指标与反证实验

指标：错误 trace 检出率、false stall、额外 tag bits、GLT area/Fmax、可删除的软件 barrier 数、DMA/compute overlap ratio、端到端 cycles。

反证：

- 对当前严格 in-order + 1 outstanding 执行穷举状态空间；若 late completion 在合法硬件模型中不可达，GLT 只是未来保险，不能声称修复当前 bug。
- 用静态 dependency slot/barrier 实现同等安全；若性能和面积更好，专用 GLT 不成立。
- 注入 tag wrap 和 reset；若安全必须依赖无限 epoch，方案不可实现。
- 关闭异步 preload/store，观察 GLT 是否只增加延迟。
- 检查 Descriptor 字段开销是否迫使拆 descriptor 或超过 queue word gate。

### 4.8 主要先例与重叠风险

- [NVDLA Hardware Architecture](https://nvdla.org/hw/v1/hwarch.html)：官方架构已有大量 double-buffered configuration/register groups；“ping/pong”本身绝非新颖核心。
- [Compiler-directed scratchpad-memory prefetching for real-time systems](https://doi.org/10.4230/LIPIcs.ECRTS.2017.24)：编译指示 scratchpad prefetch/时序，重叠**中**。
- [Scratchpad Sharing Techniques for Multicore Embedded Systems](https://arxiv.org/abs/1607.03238)：scratchpad 生命周期/共享管理，重叠**中**。

窄核心应是：**由编译器决定地址但由硬件对 role-span generation 执行 stale-completion rejection，并将可审计错误 receipt 绑定到同一 Descriptor task**，而不是“使用双缓冲”。

### 4.9 为什么可能不成立

- 当前 1 outstanding DMA 和顺序队列可能天然避免 hazard，scoreboard 没有性能或 correctness 增量。
- range comparator 和 tag plumbing 可能贯穿 DMA、TMU、MXU、VPU，改动面大于表本身。
- CPU/GPU scoreboard、DMA tags、double buffering 都是成熟概念；如果不能证明 TARS 的 role-cohort/mirror/receipt 组合带来不同技术效果，重叠风险高。
- 编译计划错误若仍能提交到 GLT，硬件检查范围有限；若加入完整 proof checker，面积又可能不可接受。

## 5. D3 — 3D 堆叠存储器逻辑层的 KV attention-window engine

### 5.1 一句话判断

这是最“像硬件论文”的方向：让 K/V 不再经单共享 DMA 全量往返 VMEM，而在 3D memory logic die 内完成 window-local QK/AV 与可合并 reduction；不过 attention PIM/NMP 已非常拥挤，专利必须落到 TARS 的 transient-window/Descriptor/归约协议，不能声称泛化“在 HBM 中做 attention”。

### 5.2 硬件新增/改变的实体

增加一个与 TARS cluster 相连的 `Stacked-KV Attention Engine`：

- K/V 按 LBHSD 分片放入 3D DRAM/HBM vault；logic die 每 vault 配置 BF16/FP16 dot-product lanes。
- core 向 logic die 广播当前 Q tile 和 `(layer, head-group, token-range)`；K/V 不搬入 VMEM。
- 第一遍每 vault 产生局部 `max` 和 `sum(exp(score-max))`；跨 vault reduction 得全局 softmax 统计。
- 第二遍或 online-softmax 数据通路产生局部 `weighted-V`，logic-die reducer 合并后只向 core 返回 head output/window partial。
- 命令队列含 task/generation ID、mask、causal bound、window base/stride、dtype 和 partial-reduction policy；不支持任意程序。
- 可选 thermal counter/sensor 只用于 throttling 和调度 receipt，作为从属研究点，不另立宽泛方向。

统一例子中，原本每 token 由共享 DMA 读 K/V window；现在 core 发送一个 Q tile，stack 内读取 K/V 并只返回 softmax/AV 的小结果。VMEM 保留 Q、output 和后续投影 tile。

### 5.3 编译侧只作为控制/生成器的部分

- 编译器把逻辑 attention 分成可结合的 vault/window partial，证明 token/head coverage、causal mask、地址范围和归约顺序。
- 编译器生成硬件命令、vault shard map 和 final reducer tree；不在 host 计算 attention，不动态迁移 KV。
- hardware engine 执行 dot-product、指数近似/softmax statistic、AV accumulate、跨 vault reduction 和错误检测。
- Descriptor Semantic Report 只验证“完整 coverage 与归约等价性”，不成为物理计算主体。

### 5.4 要解决的具体 TARS 缺陷

- KV cache 正式位于 DDR；每 cluster 只有一个 12.8 Gbps、单 outstanding DMA，且两个 core 共享。
- 最大 contiguous KV value 与 4 MiB per-core VMEM 同量级，无法与 Q/score/output/workspace 同时常驻。
- DMA 不支持 DDR gather，attention window/头分片容易退化成多次 1D/2D 搬运。
- decode 的算术强度随 context 变长而下降，外存流量会支配延迟；D3 改变的是数据移动物理位置，而不是只换编译 schedule。

### 5.5 可主张的技术骨架

**方法独立项骨架**：

> 一种在包括堆叠存储阵列和逻辑层的存储器中执行注意力的方法，包括：在存储阵列中按层、KV 类型、头组和 token 维存放 K/V；由逻辑层接收查询 tile 及描述其合法 token window 的硬件任务；在多个 vault 内对本地 K 分片计算 score partial 和 softmax 统计；合并各 vault 统计以得到归一化参数；利用该参数在逻辑层对本地 V 分片累加输出 partial；以及向外部加速 core 返回归并后的输出而不输出对应完整 K/V window。

**装置独立项骨架**：

> 一种三维堆叠存储器，包括含多个 KV vault 的存储层、含 query ingress、vault-local dot-product 单元、softmax statistic 单元、weighted-V 单元和跨 vault reducer 的逻辑层，以及与 TARS task descriptor 对应的命令/代际检查器。

**可选从属限定**：

- 使用在线 softmax 的 `(m,l,o)` associative state，在 vault/window 间确定性合并。
- 命令显式绑定 LBHSD stride、causal upper bound、head-group 和 KV generation。
- core 只接收 AV output 或 bounded partial，不接收完整 K/V。
- 由 compiler certificate 证明 shard coverage 无缺失/重叠；硬件检查 window bounds 与 generation。
- logic-die thermal counter 超阈值时只在命令边界降频/重分片，并返回实际执行配置 receipt。

### 5.6 最小原型

1. 不造 3D 芯片：先用 cycle-level HBM/vault model + 一个 synthesizable vault compute RTL。
2. 实现两种 engine：QK-only partial 返回 core；QK+online-softmax+AV 全逻辑层。前者是可行性下限，后者是目标。
3. 把现有 LBHSD DDR address/stride 和 Descriptor window plan接到模型，保证不是理想化 contiguous trace。
4. 跑 context 128/512/2048/4096、不同 head-group/window、两个 core 同时 decode。
5. 加带宽、command queue、vault conflict、TSV/logic power 和简化 thermal throttling；与“tiled DMA→VMEM”强基线比较。

### 5.7 关键指标与反证实验

指标：每 token 跨 stack/cluster 字节、共享 DMA occupancy、tokens/s、p50/p99 decode latency、vault bandwidth utilization、logic-die TOPS/W、stack power/temperature proxy、数值误差。

反证：

- 与 flash/online attention 的最佳 transient-window DMA baseline 比，而不是与“完整 KV 搬入 VMEM”的稻草人比较。
- 只做 QK、只做 AV、全 attention 三档 ablation；若 exp/reduction/二遍读让带宽更差，应缩到有收益的 primitive。
- 在短 context 和 sliding-window attention 上验证 command/Q broadcast 是否压过节省流量。
- 注入 vault imbalance、bank conflict、热降频；若理想均匀分片才有收益，论文结论不稳。
- 与增加普通 HBM 带宽或多 DMA channel 的等面积方案比较。
- 若数值等价需要高精度全局 reduction，logic die area/通信可能吞噬优势。

### 5.8 主要先例与重叠风险

- [TETRIS: Scalable and Efficient Neural Network Acceleration with 3D Memory](https://doi.org/10.1145/3037697.3037702)：3D memory 中的 DNN 加速，重叠**高**。
- [AttAcc! Unleashing the Power of PIM for Batched Transformer-based Generative Model Inference](https://doi.org/10.1145/3620665.3640422)：PIM transformer inference，重叠**很高**。
- [NeuPIMs: NPU-PIM Heterogeneous Acceleration for Batched LLM Inferencing](https://arxiv.org/abs/2403.00579)：NPU+PIM 异构 LLM 推理，重叠**很高**。
- [PIM-GPT](https://www.nature.com/articles/s44335-024-00004-2)：processing-in-memory GPT inference，重叠**很高**。
- [NicePIM](https://arxiv.org/abs/2305.19041)：NPU/PIM 协同映射 LLM inference，重叠**很高**。
- [Samsung HBM-PIM official announcement](https://semiconductor.samsung.com/news-events/news/samsung-develops-industrys-first-high-bandwidth-memory-with-ai-processing-power/)：产业硬件路线证明“HBM 内置 AI processing”也不是空白。
- [Demystifying the characteristics of 3D-stacked memories: A case study for Hybrid Memory Cube](https://doi.org/10.1109/IISWC.2017.8167757)：提醒 logic-layer power/temperature/bandwidth并非免费。

可尝试收窄的核心：**TARS LBHSD generation-bound window descriptor + vault-local associative online-softmax/AV partial + compiler coverage certificate + 只回传 bounded result 的接口**。仍需正式 claim chart 检索，不能据此认定可专利。

### 5.9 为什么可能不成立

- AttAcc、NeuPIMs、PIM-GPT、NicePIM 已覆盖大量 LLM/PIM 组合，专利空间可能极窄。
- 3D stack 热密度、logic die area、DRAM 时序和 vault 冲突可能使理想带宽收益不可兑现。
- TARS 规模只有两 core；若 workload 吞吐不足以摊销专用 stack，产品价值弱。
- 两遍 softmax 会二次读 V/K，单遍 online softmax又增加状态和数值复杂度。
- 原型只能是模型/FPGA，缺少真实 stack 时容易被质疑能耗和热结论。

## 6. D4 — VMEM-bank-coupled 的可分区 32×32 MXU

### 6.1 一句话判断

固定 32×32、M/N/K 32 倍数和 weight-stationary 对 decode 的 M=1/小 head/tail 很不友好；但可重构 systolic array 是高度拥挤方向，只有把 partition 与 TARS 四个 VMEM bank-pair、Descriptor 原子模式和 accumulator lifetime 联合起来才值得继续。

### 6.2 硬件新增/改变的实体

将 32×32 PE array 物理划为 4 个 16×16 quadrant：

- mode 0：四象限耦合为原 32×32；mode 1：两个 16×32；mode 2：两个 32×16；mode 3：四个 16×16。
- ACT/WGT 输入网络增加 bank-pair-to-quadrant crossbar/broadcast；每个 partition 可绑定一个或两个 VMEM pair。
- accumulator buffer 分 bank，支持 partition-local drain；只有明示 reduction mode 才跨 partition 合并。
- weight-stationary 保留为首版；若加入 output-stationary，应另作从属方案，避免原型同时变成完全通用 dataflow fabric。
- Descriptor commit 原子锁存 `partition_mode, pair_binding, accumulator_partition, tail_mask`，任务中途不可变化。

统一例子中，decode projection 的 M 很小：四个 16×16 partition 可以并行处理不同 head-group/N block，而不是把 M=1 padding 到 32 后让大部分 PE 空闲。

### 6.3 编译侧只作为控制/生成器的部分

- 编译器按 shape、tail、bank placement 在有限 partition mode 中选择，不描述任意 PE 路由。
- 它生成 quadrant operand assignment、pair binding、tail mask 和 accumulator drain plan。
- hardware crossbar、PE gating、partition-local accumulator 和合并网络产生并行效果。
- 任何 unsupported shape/mode 由 hardware admission 拒绝；Controller 不重新选择 mode。

### 6.4 要解决的具体 TARS 缺陷

- 当前 MXU 物理规格只给出固定 32×32 和 weight-stationary。
- 当前 compiler constraint 把 M/N/K 都限制为 32 倍数；decode、小 batch、head/tail 会产生 padding 或低 PE utilization。
- reference planner 明确把 nominal M/N 固定为 32，并禁止因 VMEM 容量把它“提升”到 M64；当前路径没有细粒度阵列形态。
- 四个 VMEM bank-pair 已经存在，但固定大阵列无法用多个独立小 tile 同时消费这些 pair。

### 6.5 可主张的技术骨架

**方法独立项骨架**：

> 一种矩阵计算方法，包括：从任务描述符接收预定义阵列分区模式和多个片上存储 bank-pair 到分区的绑定；在任务提交边界将 PE 阵列配置为一个耦合阵列或多个独立子阵列；从相应 bank-pair 向各子阵列供给不同 tile；在分区化累加器中独立累计；以及按描述符指定的 drain/merge 模式输出结果。

**装置独立项骨架**：

> 一种矩阵加速器，包括可耦合 PE 象限、bank-pair 输入选择网络、可分区 accumulator、tail-mask 门控单元和 Descriptor mode latch，其中 mode latch 只接受保持存储端双 bank 原子访问的有限模式。

**可选从属限定**：

- 四个 16×16 象限组成 32×32/16×32/32×16/16×16 模式。
- 每个 subarray 的输入绑定到 D1 映射后的一个或两个 bank-pair。
- compiler certificate 证明同周期 partition 的 pair footprint 不重叠；硬件检查 pair ID 和 mode legality。
- accumulator generation 与 D2 lease tag 一致，防止 partition 切换时误 drain。
- 对 tail 元素执行 PE gating，不在 VMEM 中物化 zero padding。

### 6.6 最小原型

1. 在现有 32×32 RTL 周围先加入 quadrant clock/enable、输入 mux 和 accumulator partition；首版不做任意路由。
2. 写 cycle model 对 32×32 baseline 与 4-mode array 做相同 VMEM bandwidth 限制下比较。
3. workload 分三组：M=1 decode、16/32 边界 tail、规则 M/N/K=32 control group。
4. 做真实 bank-pair trace，不给每个 partition 假定无限输入带宽。
5. 综合比较 area/Fmax/clock-gating power，并验证 fused mode 与原 32×32 bit-exact。

### 6.7 关键指标与反证实验

指标：active PE ratio、useful MAC/cycle、padding MAC、VMEM pair utilization、array cycles、end-to-end cycles、crossbar/accumulator area、Fmax、energy/useful MAC。

反证：

- 同等面积增加一个小专用 vector/GEMV engine 是否比改 MXU 更好？
- 将所有 partition 置于真实 4-pair 带宽下；若供数不足，理论 PE utilization 无意义。
- 对规则 32×32 workload 测回退；若 mux 让主 workload Fmax下降，整体可能得不偿失。
- compiler 仅通过更好 batching/packing 是否就能填满原阵列？
- partition-local accumulator 的容量和 drain 是否成为新瓶颈？

### 6.8 主要先例与重叠风险

- [FlexSA: Flexible Systolic Array Architecture for Efficient Pruned DNN Model Training](https://arxiv.org/abs/2004.13027)：可组合 subarray，重叠**很高**。
- [SARA: Scaling a Reconfigurable Dataflow Accelerator](https://arxiv.org/abs/2101.04799)（论文也讨论 SAGAR）：reconfigurable systolic/dataflow，重叠**很高**。
- [MAERI: Enabling Flexible Dataflow Mapping over DNN Accelerators via Reconfigurable Interconnects](https://doi.org/10.1145/3173162.3173176)：灵活 dataflow/interconnect，重叠**很高**。
- [Planaria: Dynamic Architecture Fission for Spatial Multi-Tenant Acceleration of DNNs](https://doi.org/10.1109/MICRO50266.2020.00062)：阵列动态裂分，重叠**很高**。

可能的窄核心：**把有限 quadrant mode 与 TARS 四个 64B VMEM bank-pair 的无冲突绑定、同一 Descriptor 原子提交和 accumulator generation 联合为一项装置合同**。不能宽泛主张“把 systolic array 分块提高利用率”。

### 6.9 为什么可能不成立

- 关键概念已被 FlexSA/MAERI/Planaria 等覆盖，技术差异可能只剩工程参数。
- decode 可能更适合 VPU/GEMV engine，不值得污染主 MXU critical path。
- VMEM 和单 DMA 可能先饱和，阵列利用率提高不改善端到端。
- 16×16 粒度仍不能高效处理 M=1；若继续细分，crossbar/控制成本快速增加。

## 7. D5 — 代际标记的双核流式交换/归约硬件

### 7.1 一句话判断

TARS 目前两个 core 之间只有同步 link、没有 data route；增加一个小而确定的 point-to-point stream/reduce fabric 可以减少共享 DMA/DDR round trip。通用 NoC 和编译通信调度先例很多，因此需要坚持“两核、有限 primitive、VMEM bank-pair endpoint、代际 completion”的窄装置。

### 7.2 硬件新增/改变的实体

增加 `Core Exchange Fabric`（CEF）：

- 每方向一个 credit-based FIFO 和 64B payload lane，与 source OUT / destination ACT 或专用 remote-write port 相连。
- 命令 primitive 限定为 `SEND_CONTIG`, `SEND_STRIDED`, `REDUCE_ADD`, `REDUCE_MAX`；不做通用 packet NoC。
- packet header 含 `task_id, generation, role, dst_base, length, reduction_op, last`。
- destination 有 4 个 bank-pair ingress queue，按目标 pair backpressure；可直接写 remote VMEM，或在小 reducer 中与本地 partial 合并。
- endpoint 只有在完整 packet count、generation 和 CRC/poison 检查通过后发布 signal；同步与数据可见性成为同一个 hardware receipt。

统一例子中，core0/core1 分别计算 attention head partial。当前需写 DDR/共享 DMA再读；CEF 可把 core0 partial 直接流到 core1 的 reducer，完成 `max/sum` 或 output add，再由 core1继续计算。

### 7.3 编译侧只作为控制/生成器的部分

- 编译器选择合法 producer/consumer、tile order、destination range、reduction op 和 generation。
- `MovementSyncPlanIR` 生成 send/receive occurrence 和保序约束；不模拟路由器，不在 runtime 重新分配 buffer。
- hardware FIFO/credit/reducer 实际搬运、backpressure、匹配 generation、完成归约和发布 receipt。
- 对 unsupported non-associative op 或不匹配 packet count fail closed。

### 7.4 要解决的具体 TARS 缺陷

- target topology 唯一 core link 是 synchronization，没有 payload path。
- shared DMA 只有一个 channel/one outstanding，`supports_inter_core: false`；两个 core 的中间结果若经 DDR，会竞争同一资源。
- Controller route table 只列 DDR↔VMEM；所谓 `cross_core_transfer_cost_cycles: 50` 没有对应可执行数据 route。
- attention 的 softmax statistics、head/output partial 与 tensor-parallel reduction 都是小而频繁的 cross-core data，纯同步事件不能替代 payload transfer。

### 7.5 可主张的技术骨架

**方法独立项骨架**：

> 一种双核加速器的数据交换方法，包括：根据任务描述符在源核建立包含目标 VMEM 区间、归约操作和代际标识的发送事务；通过不经过共享外存 DMA 的信用流控链路发送 payload；在目标核按 bank-pair 接收队列写入或与本地 partial 执行限定归约；验证全部 packet 的代际和计数；以及仅在数据可见后产生与该代际绑定的完成信号。

**装置独立项骨架**：

> 一种包括第一 core、第二 core、cluster 共享 DMA 和独立 core-exchange fabric 的加速器，其中 exchange fabric 包含双向 FIFO、credit controller、bank-pair ingress、有限归约单元及数据/同步联合 receipt 发生器。

**可选从属限定**：

- payload width 与 TARS IWO 64B pair access 相同。
- destination pair 由 D1 remapper 的 mapping epoch 确定。
- receive range 先由 D2 lease table acquire，packet generation 必须匹配 lease generation。
- `REDUCE_MAX`/`REDUCE_ADD` 用于 online-softmax statistic；非法顺序或计数直接 poison whole task。
- 共享 DMA 与 CEF 有独立 arbitration domain，CEF 不占用 cluster DMA outstanding slot。

### 7.6 最小原型

1. 先做两核定长 64B duplex FIFO，不做 mesh；endpoint 用现有 VMEM bridge的额外 master port或受控 remote-write adapter。
2. 加 `SEND_CONTIG` 和 `REDUCE_ADD` 两个 primitive，随后再考虑 strided/max。
3. 在 BFM 中跑 producer→consumer、双向同时发送、destination bank backpressure、错误 generation、packet loss/duplicate。
4. 从真实双核 execution plan 抽取三类 trace：普通 tensor handoff、attention statistic reduce、output partial add。
5. 与 DDR round trip 强基线在相同 VMEM arbitration 和 DMA bandwidth下比较。

### 7.7 关键指标与反证实验

指标：cross-core bytes/s、payload latency、共享 DMA bytes/occupancy、VMEM ingress stall、dual-core speedup、FIFO/reducer area和power、deadlock/poison coverage。

反证：

- 增加第二个普通 DMA channel是否用更小面积取得同样收益？
- 如果 destination VMEM bank conflict 主导，直连只把瓶颈前移，应与 D1/D2 解耦测量。
- 对 payload size 扫描；若只有极大 tensor 才获益，DDR/HBM burst 可能更有效。
- 对 packet backpressure 做形式死锁检查，尤其双向 send + 等待 receive 的循环。
- 取消 in-network reduce，只做 direct copy；若性能不变，不应声称 reducer 是必要特征。
- 验证 compiler batching 是否已能把跨核通信隐藏在计算后面。

### 7.8 主要先例与重叠风险

- [METRO: Bridging the Gap between Computation and Communication in Multi-chip Accelerators for Recommendation Systems](https://arxiv.org/abs/2108.10570)：编译/映射通信协同，重叠**高**。
- [T10: A Reconfigurable System with Compiler-Driven Interchiplet Communication](https://doi.org/10.1145/3694715.3695955)：compiler-driven interchiplet communication，重叠**很高**。
- [Simba: Scaling Deep-Learning Inference with Multi-Chip-Module-Based Architecture](https://research.nvidia.com/publication/2021-05_simba-scaling-deep-learning-inference-chiplet-based-architecture)：多芯粒推理通信/层次，重叠**高**。

可尝试收窄的核心：**与 TARS 共享 DMA 并列的两核专用 64B bank-pair endpoint，数据 completion 与 generation-bound sync occurrence 合一，并可执行 attention partial 的有限归约**。不能宽泛主张“编译器决定跨核通信”。

### 7.9 为什么可能不成立

- 两 core 规模太小，第二 DMA channel 或更好静态分区可能更简单。
- VMEM 增加写端口、arbiter master 或 remote-write adapter 的面积/时序很重。
- METRO/T10/Simba 等使通用通信协同非常拥挤。
- 当前 workload 的 per-core partition也许几乎无 payload dependency；若只有同步而没有真实 data handoff，CEF 无用。
- reducer 数值顺序可能破坏现有 golden，带来额外 numerical-agreement负担。

## 8. 淘汰方向的红队说明

### 8.1 C6 Descriptor template/loop expansion engine

设想是在硬件中缓存模板、由短 Descriptor 展开 buffer/loop/micro-op。它确实是硬件，不只是编译器；但不建议作为五大主方向：

- 当前单 Descriptor 上限 28 words，Controller buffer 512 words，“单条太长”并不是已证瓶颈（`docs/descriptor/02-descriptor-format.md:29-58`）。
- [VTA: A Hardware-Software Blueprint for Flexible Deep Learning Specialization](https://arxiv.org/abs/1807.04188) 已使用可编程指令/微操作架构。
- [Energy-efficient instruction compression with programmable dictionaries](https://doi.org/10.1007/s10617-024-09290-2) 直接覆盖 programmable dictionary instruction compression。
- [FEATHER/MINISA official repository](https://github.com/maeri-project/FEATHER) 明确把参数化 ISA/configuration-stream expansion 作为核心；与“硬件展开短配置”过近。

除非先测得整队列 fetch/parse energy 是主瓶颈，并形成 TARS 特有的“family reversibility checker + generation lease expansion”，否则它更像工程压缩。

### 8.2 C7 counter-feedback 备用 plan selector

“编译器预生成 K 个合法 plan，硬件读 counter 选择一个”很容易落入普遍的 adaptive mapping/reconfigurable accelerator 范畴；SARA/SAGAR、可配置 bank mapping 和 runtime autotuning 均有接近思想。它还会动摇 `PhysicalMemoryPlanIR` 的单一 placement authority。除非 selector 只在一个被证明等价的 bounded remap mode 内切换并产出可审计 receipt，否则不独立立项。

### 8.3 C8 thermal-aware 3D placement

热感知是 D3 必做的反证/从属机制，不足以单独成为 TARS-specific 主方向：当前仓库没有真实 stack thermal map 或 throttling failure。若独立立项，容易退化为“根据温度编译调度”的常见方案。

### 8.4 C9 fault-aware degraded mode

坏 bank/core remap、冗余和 MBIST 是成熟可靠性路线。当前没有 TARS defect-rate、fault map 或 yield 数据，无法建立 causal problem。先留作 D1 remapper 的从属功能，不要先以“编译避开坏 bank”立项。

### 8.5 C10 mixed-precision overflow detect/replay

当前虽有 BF16/FP16/INT8/FP32 accumulator，但没有证据把 numerical FAIL 因果归因到 overflow。没有这个根因，增加 detector/replay 既可能无用，也会与成熟 mixed-precision/error recovery工作高度重叠。应先做 numerical failure taxonomy。

## 9. 五方向比较与停止条件

| 方向 | TARS 特异性 | 论文潜力 | 近期专利交底可写性 | 先例风险 | 最小可证伪周期 | 首个停止条件 |
|---|---:|---:|---:|---:|---:|---|
| D1 VMEM remapper | 5 | 4 | 4 | 4 | 4–8 周 | base/padding baseline 已同样消除冲突，或 Fmax 损失吞掉收益 |
| D2 generation lease | 5 | 3 | 4 | 3 | 6–10 周 | 在全部合法当前执行中 stale completion不可达，且未来 overlap 也无计划 |
| D3 3D KV NMP | 4 | 5 | 2 | 5 | 3–6 月 | 相对最佳 transient-window baseline，真实 stack model 下 bytes/energy/latency无净收益 |
| D4 partitioned MXU | 4 | 4 | 2 | 5 | 2–4 月 | 真实 VMEM 带宽下 PE 利用率提升不转化为 end-to-end speedup |
| D5 core exchange | 5 | 4 | 3 | 5 | 2–4 月 | workload trace 几乎无 cross-core payload，或第二 DMA 更优 |

### 9.1 拥挤度、宽权项失败原因和最小创新核

这里的“可主张”只表示值得做逐要素检索的工程组合，不表示法律上新颖或具有创造性。

| 总优先级 | 方向 | 专利/论文拥挤度 | broad claim 为什么站不住 | 最小可主张创新核 | 推荐定位 |
|---:|---|---|---|---|---|
| 1 | D1 VMEM remapper | **高** | XOR hash、adaptive bank mapping、compiler bank placement 都已有直接先例；“按冲突选择映射”过于通用 | Descriptor 边界 active/shadow 原子提交；保持 TARS 64B adjacent-pair；mapping epoch 随请求/响应传播；compiler 只从有限 mode 中给出并发证明 | 近期原型、交底和论文的共同首选 |
| 2（有条件） | D2 generation lease | **中高** | double buffering、scoreboard、DMA tag、scratchpad prefetch 都是成熟机制；“防止 ping/pong 覆盖”太宽 | compiler 仍唯一选择 role-span 地址；硬件 GLT 执行 `(slot,epoch)` 租约；旧代 completion 不得改变新代状态并生成 task-bound poison receipt | 先做可达性形式证明；hazard 可达才立项 |
| 3（论文）/5（专利） | D3 3D KV NMP | **极高** | PIM/HBM 内 attention、NPU-PIM LLM inference、3D-memory DNN 均已有近邻；“KV 留在 HBM 计算”基本站不住 | LBHSD generation-bound window command；vault-local associative online-softmax/AV partial；compiler coverage certificate；外部仅返回 bounded result | 体系结构论文旗舰；不适合先押宽专利 |
| 4 | D5 core exchange | **极高** | compiler-driven NoC/interchiplet communication、direct link、in-network reduce 都有密集先例 | 与共享 DMA 并列的 TARS 两核 64B bank-pair endpoint；receive lease generation；payload completion 与同代 sync occurrence 合为一个硬件 receipt | 先做 cross-core trace，再决定论文/交底 |
| 5 | D4 partitioned MXU | **极高** | FlexSA/MAERI/Planaria/SAGAR 已覆盖阵列裂分、可重构 dataflow 和 flexible interconnect | 有限 quadrant mode 与四个 VMEM pair 无冲突绑定；同一 Descriptor 原子锁存；partition-local accumulator generation；tail 不物化 zero padding | 只有 trace 证明 MXU 利用率是主因时继续 |

因此优先级不是“想象空间”排序，而是“已有 TARS 证据 × 最小硬件改动 × 能否快速证伪”排序。D3 的论文想象空间最大，但它在专利拥挤度和实验成本上都是最危险的；D1 的题目看似较小，却最可能形成一套可测、可综合、能明确失败的完整技术闭环。

建议的实际门序：

1. **先冻结事实**：硬件 owner 选定唯一 VMEM mapping equation；没有这一步，D1 bank proof 仍不可比较。
2. **做两个低成本 trace study**：当前 workload 的 bank/pair arbitration trace，以及跨核 payload/DDR round-trip trace。
3. **D1 RTL MVP**：它既能修正 authority/RTL seam，也为 D4/D5 提供真实 bank endpoint。
4. **D2 先做形式反证**：证明当前/未来 execution 中代际 hazard 是否可达，再决定要不要 RTL。
5. **D3 先做 roofline/bytes lower bound**：如果理论上也赢不了 tiled DMA baseline，就不进入 stack simulator。
6. D4/D5 只有在 trace 分别证明 PE underutilization 或 cross-core payload 是主要 stall 后才进入 RTL。

## 10. 专利交底时的写法边界

### 10.1 应把什么放在独立项

- 物理装置：remapper、shadow/active latch、lease table、logic-die compute、PE partition、direct link/reducer。
- 明确硬件状态转换：何时 commit、何时阻塞、怎样标记 generation、怎样处理 stale/error。
- 明确地址/数据效果：逻辑地址如何生成物理 bank、哪些字节不再跨 DDR/VMEM、哪些 PE 同时工作、何时数据对 consumer 可见。
- 编译输出只作为装置输入：有限 mode、地址区间、coverage、generation、reduction policy。

### 10.2 不宜把什么作为核心

- “编译器选择最优配置”“根据代价优化”“生成 Descriptor”这类纯算法句子。
- 只说“提高带宽、降低功耗”，而没有硬件路径与可测状态。
- 把 planning acceptance 写成 current hardware support。
- 把固定的参数（32×32、4 bank-pair、两 core）当唯一创新；它们可以是从属限定，但通常不是技术原理。
- 用宽泛词覆盖 PIM、可重构阵列、NoC、双缓冲；主要先例已经非常接近。

### 10.3 每个方向都应补的交底附件

1. current-vs-proposed block diagram；
2. 一个完整 Descriptor task 的时序图；
3. 状态机和 fail-closed/error path；
4. 至少一个正例、一个反例地址/周期 trace；
5. 综合结果和端到端 workload 结果；
6. 与最近三篇先例逐要素 claim chart；
7. 清楚标记哪些是已实现、模拟、规划和假设。

## 11. 文献检索覆盖与局限

### 11.1 用户指定 academic-search 工具的运行状态

2026-09-01 依照 `nature-academic-search` 工作流，尝试以 Crossref、arXiv、OpenAlex、Semantic Scholar 做多源 `search_papers`。该搜索入口在本次环境中于结果集生成前报错：

```text
Search failed: asyncio.run() cannot be called from a running event loop
```

因此本次**没有可报告的 `search_run_id`，也不能声称完成了可复现的多源查全检索**。后续使用精确 DOI/arXiv ID 的 `get_paper_by_id` 校验了标题/年份；Crossref 与 arXiv identifier lookup 成功，OpenAlex/Semantic Scholar 本轮没有形成可用 search run。作者字段在若干 identifier 返回中不可完整核对，故本文刻意不依赖作者名作判断。

### 11.2 回退检索

为不中断技术红队，回退到公开 Web，但只保留：

- DOI/Crossref 对应的原始论文入口；
- arXiv 原文页；
- Nature 原论文页；
- NVIDIA/Samsung/NVDLA 等官方项目或厂商页面；
- 研究团队官方 GitHub。

没有把二手博客、聚合摘要或营销转载作为重叠判断依据。检索主题覆盖：bank XOR/remapping、multi-bank CGRA mapping、scratchpad prefetch/lifecycle、3D memory/PIM attention、reconfigurable systolic/dataflow、compiler-driven interconnect、descriptor/microcode compression。未完成专利数据库、非英文专利、被引/施引图和逐 claim 法律检索。

### 11.3 精确标识符核验摘要

| 标识符 | 结果 |
|---|---|
| `10.1109/TC.2015.2479595` | Crossref 标题/年份匹配；作者完整性需人工复核 |
| `2004.13027` | arXiv 标题/年份匹配；作者完整性需人工复核 |
| `2101.04799` | arXiv 标题/年份匹配；作者完整性需人工复核 |
| `10.1145/3620665.3640422` | Crossref 标题/年份匹配；作者完整性需人工复核 |
| `2403.00579` | arXiv 标题/年份匹配；作者完整性需人工复核 |
| `2108.10570` | arXiv 标题/年份匹配；作者完整性需人工复核 |
| `10.1007/s10617-024-09290-2` | Crossref 标题/年份匹配 |
| `10.1109/IISWC.2017.8167757` | Crossref 标题/年份匹配 |
| `1807.04188` | arXiv 标题/年份匹配；作者完整性需人工复核 |
| `10.1145/3694715.3695955` | Crossref 标题/年份匹配 |
| `10.1145/3037697.3037702` | Crossref 只返回短题名 `TETRIS`，年份匹配；完整题名需人工复核，不能算全字段验证通过 |
