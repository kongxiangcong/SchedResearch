# TARS 编译器—硬件协同科研：仓库实时证据审计

日期：2026-09-01

范围：当前工作树中的 llmSched 公共编译链、类型化硬件权威、Descriptor 0x8、Controller 参考模型、连接 RTL，以及最近的 compiler-owned sublayer/VMEM Wayfinder。本文只做项目事实审计和研究钩子枚举，不替主调研选择最终五个方向。

## 0. 状态标记与结论

- **[I] Implemented**：当前生产/公共链代码中已有可执行实现。
- **[A] Authority**：当前活动输入、活动 Descriptor release，或连接 RTL 的实际硬件事实。
- **[P] Proposal / accepted design**：已接受 ADR、CONTEXT 或 Wayfinder 规划，但还不是当前生产实现/活动 wire/Controller 行为。
- **[M] Missing**：仓库当前权威链没有该模型、闭环或硬件连接。

核心判断：TARS 已经不是“只有一个编译器算法”的项目；它已经具有一条真正的软硬件契约链：

`GraphClusterIR -> DataflowPlanIR -> StreamTensorPlanIR -> PhysicalMemoryPlanIR -> MovementSyncPlanIR -> CoreExecutionPlanIR -> RuntimeLaunchIR -> DescriptorEmissionIR -> DescriptorSemanticReportIR`

该顺序由当前代码常量直接冻结，而 `MappingIR`、`VMEMAllocationIR`、`DescriptorPackPlanIR` 等被明确禁止成为平行公共权威（`src/llmSched/src/llm_sched/orchestrator/authority_chain_constants.py:L16-L46`）。公共入口要求显式 `hardware_spec_root`，默认读取 `inputs/mapping/mapping_plans.json`，并允许绑定可选 cost provider（`src/llmSched/src/llm_sched/orchestrator/public_authority_chain.py:L324-L405`）。

但是，当前闭环止于“编译期静态计划 + per-core Descriptor 交付”：完整 late-binding driver、动态 patch、Controller replay 和实测性能反馈仍被定义为未来工作（`CONTEXT.md:L1610-L1612`）。更关键的是，最新“编译器拥有 sublayer/VMEM”的设计虽然已在 ADR 中接受，Controller 参考模型和连接 RTL 仍从 0x8 Descriptor 二次推导 sublayer 和 VMEM 地址。因此，目前最有价值的科研空间不是给现有流程换一个软件优化器名字，而是补上 **硬件可消费的计划、硬件可观测的反馈、以及跨层一致性/准入机制**。

为避免把愿景误写成现状，本文采用以下证据优先级：当前 `hardware_specs/tars/`、活动 release 指针和 connected RTL 记为 [A]；当前公共链可执行代码记为 [I]；`docs/hardware/tars_v0.1.md` 的 3D/NoC 章节、ADR-0110/0111/0112 和 Wayfinder 只记为 [P]。尤其 ADR-0110 自己声明该次决策不修改 Controller、legacy Descriptor 或旧调度器（`docs/adr/0110-own-sublayer-partition-and-vmem-feasibility-in-llmsched.md:L11-L16`），Wayfinder 也明确 planning evidence 不等于 active authority、Controller/RTL behavior 或 Hardware Admission（`.scratch/llmsched-compiler-owned-sublayer-vmem-wayfinding/MAP.md:L190-L204`）。

## 1. 一个具体 GEMM 的端到端实时链路

| 步骤 | 当前 owner 与行为 | 状态 | 实时证据 | 关键缺口 |
| --- | --- | --- | --- | --- |
| 1. Frontend graph 进入 | `GraphClusterIR` 把已验证 Graph Bundle 翻译一次，保存节点、边、边界和 blocked evidence；当前不做 graph optimization、fusion 或 multi-cluster repartition。 | [I] | `src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_graph_cluster.py:L39-L79`；`CONTEXT.md:L108-L130` | 当前范围仍是一 cluster、两 core；多 cluster 是未来范围（`CONTEXT.md:L132-L145`）。 |
| 2. Mapping/Dataflow | `DataflowPlanIR` 对一个 GEMM 只构造 `single_map / seq_m / chn_n` 三类候选，先合法性裁剪、再按估计代价排序；tile 由 MXU/VMEM facts 推导，不做完整 M/N/K 或全图搜索。 | [I] | `src/llmSched/src/llm_sched/eval_pipeline/dataflow_strategy.py:L258-L357`；`src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_dataflow_plan.py:L508-L524` | 候选深度很浅，cluster composition 只做 legality，不做跨 op 全局 performance ranking（`CONTEXT.md:L1386-L1395`）。 |
| 3. Buffering intent | 当前 GEMM strategy 固定声明 ACT/WGT 按 `k_step` 双缓冲，compute 使用 MXU tile pipeline。 | [I] | `src/llmSched/src/llm_sched/eval_pipeline/dataflow_strategy.py:L503-L529` | 它是固定 intent，不是根据 DMA、bank stall 或 3D memory latency 选择 1/2/3 级缓冲。 |
| 4. Physical memory | `PhysicalMemoryPlanIR` 生成 stream/implementation buffer、lifetime、placement、double-buffer binding、capacity/alias/reuse/compute-read evidence，并成为 Descriptor BUFFER 字段来源。 | [I] | `src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_physical_memory.py:L684-L925`；owner 定义见 `CONTEXT.md:L1318-L1320` | 当前是 lifetime-aware first-fit 和 K-step modulo-2 slot；不是新规划中的 sublayer mirror frame、epoch 和 bank-cost search。 |
| 5. Movement/sync | `MovementSyncPlanIR` 从 stream + physical placement 构造 ingress、movement edge、route、sync object、availability/residency/reuse/deadlock proof；明确是 compile-time static contract。 | [I] | `src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_movement_sync.py:L63-L118`、`L141-L269`、`L274-L347` | route 词汇只有 `local_vmem/direct_core_link/shared_dma/ddr_ingress/ddr_store/ddr_materialized`，不含 NoC/SDMA/3D NUMA（`src/llmSched/src/llm_sched/hardware_modeling/query/route.py:L16-L23`）。 |
| 6. Core execution | `CoreExecutionPlanIR` 为每个 task/core 形成 compute action，绑定 stream、physical-memory、movement refs 和 resource class；cycle interval 的 upper bound 仍为 `None`，策略为 `static_order_only_not_final_schedule`。 | [I] | `src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_core_execution.py:L514-L570`、`L615-L650` | 一个 compiler task/core 仍主要对应一个静态 compute action，而非 Controller 最后执行的全部动态 sublayer/DMA/compute/drain 微序列。 |
| 7. Per-core launch/Descriptor | Runtime 产生显式 core0/core1 package；空 core 也是显式空队列，禁止 fake idle descriptor。DescriptorEmission 从 package 与全部上游 authority 打包 0x8，并记录每个 entry 的 word span、parse/verifier 状态和 field authority。 | [I][A] | 空队列契约：`src/llmSched/src/llm_sched/orchestrator/runtime_launch_planning.py:L784-L839`；打包：`src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_descriptor_emission.py:L134-L253`；活动 release：`inputs/descriptor_releases/active-release.json:L1` | wire 传的是完整 tensor/tile/BUFFER/LOOP 视图，没有传新设计所需的 sublayer identity、mirror step、slot/epoch lifecycle。 |
| 8. Controller reference execution | 对 0x8 GEMM，Controller 检查后调用自己的 `GemmSublayerPlanner`；planner 固定 M/N 一个 32 tile，按 VMEM slot budget 求 K chunk，重新排 ACT/WGT/OUT/PARAM，再执行 preload→TMU→store。 | [I] | 分支：`external/tars-npu-ctrl/ref_model/tars_ref/core/npu_controller.py:L551-L594`；规划：`external/tars-npu-ctrl/ref_model/tars_ref/core/sublayer_planner.py:L28-L80`、`L285-L324`；执行：`external/tars-npu-ctrl/ref_model/tars_ref/core/npu_controller.py:L843-L956` | Controller 是第二个 sublayer/placement 决策者；其 `_binding_for_sublayer` 会替换 VMEM base（`external/tars-npu-ctrl/ref_model/tars_ref/core/sublayer_planner.py:L445-L456`）。 |
| 9. Connected RTL execution | RTL Controller 默认 `SUBLAYER_SLOT_COUNT=1`，固定 GEMM M=1 tile、K=16 tiles，自己计算 slot base、ACT/WGT/OUT base 和 fit 条件；仅参数改为 2 slots 时才进入 pipeline mode。 | [I][A] | `external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_controller.sv:L3-L10`、`L201-L210`、`L1361-L1419`、`L1455-L1458` | 编译器计划尚未成为硬件消费的唯一执行计划；RTL 和编译器的 double-buffer 深度、地址与生命周期可能分叉。 |

这个 GEMM 流说明了当前最重要的权属断点：**编译链已经声称 PhysicalMemory 是地址 owner，但实际执行硬件仍把 0x8 当成重新规划的输入，而不是必须逐项接受的已完成硬件计划。** ADR-0110 已接受 downstream 不得 repartition/readdress 的目标，但同时明确此次交付不改 Controller 或 legacy Descriptor（`docs/adr/0110-own-sublayer-partition-and-vmem-feasibility-in-llmsched.md:L3-L16`），所以它现在应标为 [P]，不能误报为 [I]。

## 2. 当前权属边界

| 对象 | 正确 owner | owner 做什么 | 明确不做什么 | 状态/证据 |
| --- | --- | --- | --- | --- |
| Graph identity/semantics | Frontend + `GraphClusterIR` boundary | 保留 logical nodes/edges/cluster membership/blocked status | 不为 memory/descriptor 约束重写 graph | [I] `CONTEXT.md:L108-L130` |
| strategy/core/tile/loop/overlap intent | `DataflowPlanIR` | 每 op 选择 strategy、core assignment、tile、logical loop、engine 和 overlap intent | 不做 VMEM base、lifetime、final cycle schedule | [I] `src/llmSched/src/llm_sched/eval_pipeline/dataflow_strategy.py:L503-L529`；`CONTEXT.md:L1398-L1404` |
| logical stream/storage view | `StreamTensorPlanIR` | 连接 graph edge、layout、dtype、producer/consumer 与流版本 | 不做物理地址 | [I] chain position见 `src/llmSched/src/llm_sched/orchestrator/authority_chain_constants.py:L16-L26` |
| VMEM buffer/lifetime/base/bank/slot/epoch/proof | `PhysicalMemoryPlanIR` | placement、alias/capacity/reuse/compute-read、Descriptor BUFFER field authority | downstream 不得 readdress | [I] 当前 generic placement；[P] sublayer-specific invariant。`CONTEXT.md:L1308-L1320` |
| route/visibility/wait/signal | `MovementSyncPlanIR` | 有界 route selection、availability/dependency/deadlock proof | 不做全局 NoC search 或动态 DMA trace | [I] `CONTEXT.md:L1458-L1476` |
| ordered action/per-core task queue | `CoreExecutionPlanIR` | action order、queue index、sync endpoint binding、resource conflict | 不做 placement、strategy、runtime pack | [I] `CONTEXT.md:L1358-L1376` |
| runtime package/protocol | `RuntimeLaunchIR` | exact per-core queue projection、start/poll/fence/sync、action-entry binding | 不拥有 task order，不嵌 Descriptor words | [I] `CONTEXT.md:L1550-L1568` |
| wire bytes | `DescriptorEmissionIR` + active release | pack `core*.hex`、entry span、CRC、parse/verifier 和 field mapping | 不修补上游策略/地址/route | [I][A] `CONTEXT.md:L1598-L1608`；`src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_descriptor_emission.py:L179-L253` |
| runtime sublayer micro-sequence | 当前 Controller/RTL | 从 Descriptor 再推导 sublayer、DMA、TMU 程序与 slot | 当前没有消费 compiler-authored sublayer carrier | [I] `external/tars-npu-ctrl/ref_model/tars_ref/core/npu_controller.py:L843-L956`；RTL `external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_controller.sv:L1361-L1419` |
| hardware numerical admission | 独立 Controller/engine/RTL receipt | 证明 selected hardware layout 与真实执行合同一致 | compiler semantic PASS/parse PASS 不可替代 | [M] 当前主链没有闭环；定义见 `CONTEXT.md:L1065-L1071` |

## 3. `TargetHardwareSpec` 已有的可配置旋钮

### 3.1 当前可被编译器查询的事实

1. **拓扑与实例**：[A] 当前 target 明确为 1 cluster、2 cores，每 core 各有 MXU/VPU/TMU/VMEM，cluster 共享一个 DMA 和 Controller，core link 只有 synchronization（`hardware_specs/tars/target_hardware_spec.yaml:L6-L39`）。schema 本身能容纳多个 cluster/core/instance/shared-resource/core-link（`src/llmSched/src/llm_sched/hardware_modeling/schema/root.py:L12-L47`），normalized IR 也保留 `cluster_count / cores_per_cluster / core_count`（`src/llmSched/src/llm_sched/hardware_modeling/ir/topology.py:L41-L49`）。
2. **MXU**：[A] rows/columns、dtype、accumulator depth、dataflow、接口宽度、M/N/K multiple、preload alignment/K step multiple（`hardware_specs/tars/modules/mxu.yaml:L3-L32`）。当前实例是 32×32、acc depth 64、weight-stationary。
3. **VPU/TMU**：[A] VPU lane/sublane/local buffer/op capability/tail；TMU port width、7-D AGU、stride/loop 位宽、BSE、backpressure、transform capability 和 64B granularity（`hardware_specs/tars/modules/vpu.yaml:L3-L23`、`L61-L90`；`hardware_specs/tars/modules/tmu.yaml:L3-L44`）。
4. **VMEM**：[A] capacity/address width、bank geometry、interleave/remap、ACT/WGT/OUT/PARAM/DMA path、role-path capability、reserved range、declared region 和 alignment（`hardware_specs/tars/modules/vmem.yaml:L3-L52`、`L53-L135`）。
5. **DMA/Controller**：[A] DMA channel/beat/bandwidth/outstanding/dimension/gather/alignment；Controller queue/inflight、CSR/addressability、patch mode、programmable module、route CSR、sync slots/cost（`hardware_specs/tars/modules/dma.yaml:L3-L27`；`hardware_specs/tars/modules/controller.yaml:L3-L51`）。
6. **Compiler profile**：[A] opcode、quantization、WDQ group size、KV cache layout/storage/dtype（`hardware_specs/tars/target_hardware_spec.yaml:L40-L73`）。

这些 facts 已经通过 immutable `TargetHardwareSpec -> NormalizedHardwareModelIR -> BoundHardwareModel -> Typed Hardware Query -> CostModelProvider` 进入公共编译 seam；hardware query 只回答 capability/fact，不替 compiler 做 workload decision（`docs/adr/0096-freeze-unified-hardware-modeling-owners-and-parity.md:L9-L28`）。因此“面向可配置硬件结构的软硬件协同”有现成 ABI 基座，而不必新造一个平行硬件描述系统。

### 3.2 还不是旋钮的架构愿景

当前 closed root schema 只引用 `mxu/vpu/tmu/dma/vmem/controller` 六类模块，没有 NoC、router、SDMA、3D memory macro、chiplet/die、TSV、NUMA、thermal 或 DVFS 字段（`src/llmSched/src/llm_sched/hardware_modeling/schema/root.py:L57-L99`）。公共链还显式把 `multi_cluster_scheduling` 放入 deferred scope（`src/llmSched/src/llm_sched/orchestrator/authority_chain_constants.py:L161-L165`）。所以：

- “多 cluster、Folded Torus、3D DRAM/Flash”目前只能标为 [P/M]，不能作为已经实现的 TARS 能力。
- target schema 的 topology 容器具备扩展起点，但 route class、memory hierarchy、placement IR 和 runtime protocol 还没有对应语义。

## 4. VMEM：当前事实、实现与冲突

### 4.1 当前活动硬件事实

- [A] 每 core 4 MiB、22-bit byte address、8 banks、4 bank pairs、每 bank 32B；ACT/WGT/OUT 以 64B、2-bank interleave 访问，PARAM/DMA 是 32B、single-bank linear physical（`hardware_specs/tars/modules/vmem.yaml:L3-L24`、`L25-L97`）。连接 RTL 一致地定义 4 MiB、22-bit、8×32B bank，并给出 read latency/return FIFO 等额外物理事实（`external/tars-npu-vpu/rtl/vmem/src/vmem_defines.vh:L8-L29`）。固定 remapper 让连续 32B logical beat 轮转 Bank0..Bank7（`external/tars-npu-ctrl/rtl/vmem/src/vmem_controller/vmem_addr_remapper.sv:L1-L18`）。
- [A] RTL VMEM AXI bridge只接受 32B 对齐、INCR、且完全落在 4 MiB aperture 内的 burst（`external/tars-npu-vpu/rtl/vmem/src/vmem_controller/vmem_axi_bridge.sv:L177-L197`）。

### 4.2 当前编译实现

- [I] placement 会把 compiler logical address 送入 typed memory query，保留 alignment、remap mode、bank/bank-pair refs、post-remap ranges 和 hardware provenance（`src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_vmem_placement.py:L44-L93`）。
- [I] stream buffer 依据 lifetime 复用 slot，超 capacity fail closed；implementation workspace 也是 lifetime-aware first-fit（`src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_physical_memory.py:L1091-L1176`、`L1302-L1369`）。
- [I] 只有 strategy 明确写出 `double_buffer_by_k_step` 才创建 alternate slot；alternate 用最小地址 first-fit，最后按地址大小命名 ping/pong，bank-pair separation 仅标为 `advisory`（`src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_vmem_placement.py:L128-L167`、`L188-L282`）。每个 K step 只按 `k_step_index % 2` 绑定 slot（同文件 `L285-L371`）。
- [M] 当前公共 PhysicalMemory builder 中没有 collision count、arbitration opportunity、phase-candidate ranking 或 mirror-step search；实际分配核心仍是 alignment/lifetime first-fit（`src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_vmem_placement.py:L400-L423`）。

### 4.3 三套地址区间同时存在

| 来源 | data/runtime | protected/PARAM | 状态 |
| --- | --- | --- | --- |
| 当前 typed hardware authority | data `[0, 0x3FF000)`，PARAM `[0x3FF000, 0x400000)`，即 4092 KiB + 4 KiB | `hardware_specs/tars/modules/vmem.yaml:L98-L135` | [A] |
| 当前连接 RTL Controller | GEMM sublayer 可用上界 `0x3F0000`；固定 VPU PARAM/LUT base 也是 `0x3F0000`，即最后 64 KiB 不进入 sublayer arena | `external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_controller.sv:L192-L208` | [I][A] |
| 最新 compiler-owned Wayfinder | runtime `[0,0x3F0000)`；Controller LUT `[0x3F0000,0x3F1000)`；dynamic PARAM `[0x3F1000,0x400000)`，即 4032/4/60 KiB | `.scratch/llmsched-compiler-owned-sublayer-vmem-wayfinding/MAP.md:L32-L47` | [P]，该 MAP 明确不授权 active YAML/RTL 修改 |
| reachable legacy input | 128 KiB/core；data 124 KiB，PARAM 4 KiB @ `0x1F000` | `inputs/hardware/hardware_model_template.yaml:L1-L30` | legacy/stale，但仍是权威漂移风险 |

这不是纯文档差异：当前 compiler 可以合法分配 `0x3F0000..0x3FF000`，但 RTL GEMM sublayer allocator 把这 60 KiB 排除；另一方面 RTL 固定参数会占用 `0x3F0000`，而 typed authority 仍把它视为 data。ADR-0096 曾记录 PARAM 从 `0x1F000` 迁到 `0x3FF000` 的历史 parity（`docs/adr/0096-freeze-unified-hardware-modeling-owners-and-parity.md:L151-L183`），说明这一表面已发生过迁移，不能用旧 golden 掩盖当前 connected-RTL drift。

### 4.4 新 sublayer/VMEM 决策的真实状态

- [P] ADR-0111 接受 ACT/WGT 两个 isomorphic mirror frame、一个 `mirror_step`、OUT singleton、`slot=s mod 2`、`epoch=floor(s/2)`，并要求 downstream 不 readdress（`docs/adr/0111-derive-sublayer-pong-from-one-mirror-step.md:L3-L21`）。
- [P] ADR-0112 接受把 bank collision 作为可仲裁的 placement cost，由 connected RTL 提供 physical baseline，但只能经 hardware owner 推入 typed authority（`docs/adr/0112-treat-vmem-bank-contention-as-placement-cost.md:L3-L17`）。
- [P] Wayfinder 仍是 `needs-triage`，明确是 planning-only；当前 frontier 还是 implementation slice order，accepted wire evidence 也明确“不等于 active authority、Controller/RTL behavior 或 Hardware Admission”（`.scratch/llmsched-compiler-owned-sublayer-vmem-wayfinding/MAP.md:L1-L33`、`L167-L204`）。

所以当前最准确的说法是：**generic VMEM placement/lifetime/double-buffer 已 implemented；compiler-owned family sublayer、mirror step、epoch-safe lifecycle 和 bank-cost search 已 accepted/planned，但尚未接入生产 chain、活动 Descriptor 和 Controller/RTL。**

## 5. Descriptor 0x8、per-core queue、TMU/MXU 与 Controller

### 5.1 活动 wire

- [A] 活动 release 是 `descriptor-v8-0x8-rmsnorm-fp16-expanded-scalar-20260825-r1`（`inputs/descriptor_releases/active-release.json:L1`），其 accepted authority 明确 `descriptor_version=0x8`（`inputs/descriptor_releases/accepted/descriptor-v8-0x8-rmsnorm-fp16-expanded-scalar-20260825-r1/authority/descriptor_v8_authority.json:L1-L33`）。
- [A/I] 0x8 是 variable-length profile wire：最多 39 个 64-bit words、5 个 BUFFER slot，body 为 HEADER→FAMILY→present BUFFER→LOOP；header 内有 dep/signal mask 和 CRC（`inputs/descriptor_releases/accepted/descriptor-v8-0x8-rmsnorm-fp16-expanded-scalar-20260825-r1/authority/wire_schema.yaml:L74-L90`、`L127-L165`）。
- [I] compiler packer把 `vmem_base_addr` 编成 32 bits，把每维 extent/stride 各编成 16 bits（`src/llmSched/src/llm_sched/descriptor/v8/codec.py:L39-L85`）；Controller parser 对同一布局独立解码（`external/tars-npu-ctrl/ref_model/tars_ref/descriptor/v8/parser.py:L25-L68`、`L97-L174`）。
- [I] compiler/Controller wire verifier目前直接检查 32B base alignment；实际 22-bit VMEM aperture 的合法性主要依赖 compiler-side PhysicalMemory/semantic join，而不是 wire parser 自身（`src/llmSched/src/llm_sched/descriptor/v8/verifier.py:L81-L102`；`external/tars-npu-ctrl/ref_model/tars_ref/descriptor/v8/verifier.py:L66-L88`）。

### 5.2 per-core queue 与同步

- [A] ADR-0077 接受“每个 target core 必须有显式 queue，包括空 queue”的交付合同（`docs/adr/0077-use-per-core-descriptor-queues-as-delivery-contract.md:L1-L15`）。[I] 当前 runtime 对空 core 写显式空 package，不允许 fake idle descriptor（`src/llmSched/src/llm_sched/orchestrator/runtime_launch_planning.py:L784-L839`）。
- [I] task synchronization builder 仍硬编码遍历 `(0,1)`，生成 in-order queue、queue index 和 dep/signal occurrence refs（`src/llmSched/src/llm_sched/orchestrator/task_synchronization.py:L1055-L1133`）。Controller 对 queue head descriptor 先等待/消费 DEP，执行完成后 fire SIGNAL 并推进 descriptor head（`external/tars-npu-ctrl/ref_model/tars_ref/core/npu_controller.py:L551-L594`、`L596-L705`）。
- [I/RTL] 顶层有每 core descriptor base/depth/head 接口（`external/tars-npu-ctrl/rtl/top/tars_npu_core_top.sv:L29-L33`），RTL Controller暴露 16-bit head 并在每个 descriptor complete 后按其 64-bit word 数推进（`external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_controller.sv:L1125-L1136`、`L3855-L3866`）。

### 5.3 队列 admission 的单位裂缝

当前 typed Controller authority 声明 `queue_depth_per_core=64`（`hardware_specs/tars/modules/controller.yaml:L3-L7`），其 query 将输入视为 per-core queue **entry count** 并与 64 比较（`src/llmSched/src/llm_sched/hardware_modeling/query/controller.py:L86-L116`）。Runtime 传入的也确实是 `len(descriptor_entries)`，而且显式关闭 queue-capacity 和 launch-descriptor-limit enforcement（`src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_runtime_launch.py:L411-L440`）。

但 RTL 接受的是 `start_stream_len_words`，并要求 `words * 8 <= 4096B`（`external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_controller.sv:L210-L210`、`L4167-L4179`）。由于一个 0x8 descriptor 最多 39 words，`64 entries` 与 `4096 bytes/512 words` 不是等价约束。这是一个已落到真实硬件接口的 admission 缺口，而不是命名问题。

### 5.4 TMU/MXU 边界

- [A] MXU 当前是 32×32 WS array、64-row accumulator，M/N/K 必须 32 倍数；TMU 有 3 个 64B 端口、7-D AGU、32-bit signed stride、16-bit loop count、backpressure（`hardware_specs/tars/modules/mxu.yaml:L3-L32`；`hardware_specs/tars/modules/tmu.yaml:L3-L39`）。
- [A] 架构边界要求 VPU 是 MXU 唯一直接控制者，Controller 不介入周期级执行（`docs/hardware/tars_v0.1.md:L88-L103`）。这为科研设计限定了一个重要原则：compiler/descriptor 可以选择 tile、buffer、DMA/sync 合同，但不能把论文贡献写成 Controller 逐周期控制 MXU。
- [I] RTL sublayer planner只接受 nominal M/N/K=32 的 0x8 GEMM profile，并在硬件中固定 M step=1 tile、K step≤16 tiles（`external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_controller.sv:L1361-L1377`）。它是现有硬件化优化的最直接落点。

## 6. 3D 堆叠、Chiplet 与多 Cluster：有架构草图，无编译/硬件权威闭环

架构文档给出了很丰富的 [P] 愿景：

- MXU_DIM、cores/cluster、clusters、VMEM、frequency、memory type、3D macro 数和 NoC width 都被写成参数，带 capacity/bandwidth/NoC/area 方程（`docs/hardware/tars_v0.1.md:L927-L953`）。
- Folded 2D Torus、DOR/virtual channel、parallel modes 和 hop/bandwidth 估算已有描述（`docs/hardware/tars_v0.1.md:L967-L1004`）。
- 3D DRAM 用 TSV 形成 local/remote NUMA，三层 memory hierarchy 明确区分 local 3D DRAM 和经 NoC 的 remote 3D DRAM（`docs/hardware/tars_v0.1.md:L1006-L1026`）。
- 文档预设 compiler 静态分区 Weight/KV/Activation/System reserve，提出双/三级 buffering，并新增每 core 两 channel 的 SDMA；compiler 应做 parallel strategy、weight mapping、buffer depth、SDMA instruction 和 topology-aware placement（`docs/hardware/tars_v0.1.md:L1038-L1079`）。

但这些都还没有进入当前 [A]/[I]：

1. typed root 没有 NoC/3D/SDMA 模块类型（`src/llmSched/src/llm_sched/hardware_modeling/schema/root.py:L57-L99`）；route vocabulary 没有 NoC/SDMA/NUMA（`src/llmSched/src/llm_sched/hardware_modeling/query/route.py:L16-L23`）。
2. 当前 target 只有一个 cluster 和 synchronization-only core link（`hardware_specs/tars/target_hardware_spec.yaml:L6-L39`）；公共 compiler 明确 defer multi-cluster（`src/llmSched/src/llm_sched/orchestrator/authority_chain_constants.py:L161-L165`）。
3. 架构文档本身还是概念基线：它在开头写 128×128 MXU、2×128KB VMEM、8-channel DMA（`docs/hardware/tars_v0.1.md:L38-L49`），而当前活动 target 是 32×32 MXU、每 core 4 MiB、1-channel DMA（`hardware_specs/tars/modules/mxu.yaml:L3-L15`；`hardware_specs/tars/modules/vmem.yaml:L3-L24`；`hardware_specs/tars/modules/dma.yaml:L3-L10`）。因此第 14 章可作为研究假设来源，不能直接当 silicon fact。

仓库里没有独立 chiplet/package/interposer/coherence/thermal model。若主调研选择 3D/chiplet 方向，首个科研贡献必须包括 **把 memory tier、TSV locality、NoC route、SDMA stream 和温度/带宽约束提升为 typed hardware facts 与 compiler-owned placement/schedule contract**，而不是声称现有 TARS 已支持这些能力。

## 7. 分析模型与真实硬件反馈之间的缺口

| 层面 | 当前分析能力 | 真实硬件侧事实 | 缺口 |
| --- | --- | --- | --- |
| strategy cost | fallback rank 只用 tile work、imbalance、tail waste；代码明确丢弃 `hardware_model, mxu_compute`，compute/memory/movement/sync/makespan/bandwidth 多项是 `None`，状态是 `not_a_latency_model`（`src/llmSched/src/llm_sched/eval_pipeline/dataflow_strategy.py:L815-L871`）。 | MXU、DMA、sync 有明确 geometry/bandwidth/outstanding/cost facts。 | [M] 选择没有消费真实 bandwidth、bank stall、DMA arbitration 或 measured cycles。 |
| optional cost provider | 只有 GEMM analytical proxy；contention unavailable，fidelity=`analytical_proxy_not_cycle_exact`、confidence=`low_uncalibrated`（`src/llmSched/src/llm_sched/hardware_modeling/analytical_cost.py:L14-L18`、`L36-L94`）。provider 未绑定时返回明确 unavailable（`src/llmSched/src/llm_sched/hardware_modeling/cost.py:L151-L174`）。 | RTL 有具体流水/回压/共享 DMA 行为。 | [M] 没有校准数据集、误差界、online/offline feedback 更新协议。 |
| movement/core timing | Movement 声明是 compile-time static proof，CoreExecution upper-bound cycle 为 `None`（`src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_movement_sync.py:L254-L269`；`src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_core_execution.py:L540-L545`）。 | RTL 真实存在 DMA wait、TMU/MXU backpressure、queue wait。 | [M] 静态 legality 无法回答 overlap、head-of-line blocking、bank serialization 的真实性能。 |
| VMEM bank | compiler可得到 bank/bank-pair footprint，但当前只做 first-fit，bank-pair separation 是 advisory。 | RTL 有固定 8-bank remap 和 bank arbitration。 | [M] 没有 compiler placement cost ↔ RTL bank-stall counter 的验证闭环。 |
| performance counters | Controller regbank定义 cycle/MXU busy/VPU busy/DMA busy/descriptor/DMA bytes/stall counters（`external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_regbank.sv:L101-L150`、`L181-L195`）；DMA 也有 active/wait/bytes/transaction/error counters（`external/tars-npu-ctrl/rtl/dma/src/dma_perf_counter.sv:L1-L39`）。 | Controller 顶层目前把 MXU/VPU/DMA busy、DMA bytes/done 和 stall 全部接常量 0，只接了 descriptor done（`external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_controller.sv:L2515-L2539`）。 | [M] “有 counter 寄存器”不等于“有可用 telemetry”；当前无法校准编译器 cost。 |
| runtime observation | domain 允许 external runtime/profiling artifact，但不进入编译 authority（`CONTEXT.md:L1821-L1823`）；Performance Report 是独立 downstream owner（`CONTEXT.md:L2499-L2501`）。 | 当前交付没有 run-specific observation（`CONTEXT.md:L1610-L1612`）。 | [M] 缺少 descriptor/task/plan identity 与 counter sample 的可追溯 join。 |
| external payload materialization | RoPE 的 compiler 侧只建立 packed-PARAM projection、placement 和 view；PhysicalMemory builder 按几何创建 implementation buffer，并直接把 `buffer_status` 记为 `ready`，没有 payload bytes/readiness 字段（`src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_rope_packed_param_physical.py:L95-L132`）。 | packed COS/SIN bytes 必须由人工显式调用的独立 preprocessor 生成；model_frontend/llmSched 不请求、不调用、不验证、也不等待它（`CONTEXT.md:L700-L705`）。非 FP16 RMSNorm gamma 同样要求 Descriptor 后独立工具转换，且 payload readiness 与编译/发布/激活分离（`docs/adr/0109-use-fp16-storage-views-for-admitted-rmsnorm.md:L41-L53`）。 | [M] 当前可以证明“Descriptor 要读哪里”，却不能证明“外部 bytes 已被正确生成并在 launch 前到位”；缺少 materialization receipt → launch/admission 的硬件可核验 join。 |
| correctness admission | compiler有 final-hex parse/verifier/semantic/static replay。 | Hardware Admission 要独立连接 selected layout 与 Controller/engine/RTL contract。 | [M] compiler PASS 不能替代 RTL numerical execution（`CONTEXT.md:L1065-L1071`；`CONTEXT.md:L1618-L1642`）。 |

## 8. 具体缺陷 / 研究钩子（供主任务组合，不是最终五个方向）

### H1. 消除 compiler 与 Controller 的双重 sublayer/VMEM authority

- **缺陷**：[I] compiler 已输出 PhysicalMemory placement；[I] Controller/RTL 仍重新切 GEMM K chunk 并重新计算 ACT/WGT/OUT base；[P] ADR 又要求 downstream 不 readdress。
- **可硬件化抓手**：新增 hardware-consumable `Sublayer Plan` profile/descriptor carrier，Controller只验证 capacity/alignment/lifecycle 后执行；硬件输出 rejection code/receipt，而不自行改计划。
- **可量化实验**：compiler plan 与 Controller trace 的 sublayer tuple/address exact agreement；减少重复 planner 门数/firmware 分支；对大 K、tail、双缓冲 case 的 cycle 与错误率。
- **证据**：`docs/adr/0110-own-sublayer-partition-and-vmem-feasibility-in-llmsched.md:L3-L16`；`external/tars-npu-ctrl/ref_model/tars_ref/core/sublayer_planner.py:L240-L324`、`L445-L456`；RTL `external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_controller.sv:L1361-L1419`。

### H2. VMEM aperture/protected-range 的硬件自描述与原子 admission

- **缺陷**：[A] typed authority 是 4092/4 KiB；[I/A] RTL 是 4032/64 KiB；legacy 仍有 124/4 KiB。编译合法地址可能落入 RTL 保护区。
- **可硬件化抓手**：启动时由 Controller/ROM 暴露 VMEM capability table（aperture、reserved range、bank map、generation）；compiler artifact 带 digest，launch hardware做 digest/range admission。
- **可量化实验**：跨 RTL configuration 的 zero-stale-config launch；非法 overlap 检出覆盖率；配置切换成本。
- **证据**：`hardware_specs/tars/modules/vmem.yaml:L125-L135`；`external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_controller.sv:L192-L208`；`inputs/hardware/hardware_model_template.yaml:L17-L30`。

### H3. Bank-phase-aware placement + 可观测 arbitration hardware

- **缺陷**：[I] compiler只保留 footprint，alternate slot first-fit，bank separation advisory；[P] bank collision cost 已接受但未实现。
- **可硬件化抓手**：compiler枚举有限 alignment phase/mirror residue，硬件提供 per-domain collision/stall counter 或 bank grant trace摘要；以真实 contention 校准选择。
- **可量化实验**：相同 tensor bytes 下 bank conflict、stall cycles、TMU/MXU utilization、energy；证明不改变 numerical semantics。
- **证据**：`src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_vmem_placement.py:L228-L280`；`docs/adr/0112-treat-vmem-bank-contention-as-placement-cost.md:L3-L17`；固定 remap `external/tars-npu-ctrl/rtl/vmem/src/vmem_controller/vmem_addr_remapper.sv:L1-L18`。

### H4. 自适应 1/2/3 级 buffering 与 credit-based TMU/DMA 接口

- **缺陷**：compiler固定 double buffer intent；RTL默认 one slot，只在 parameter=2 时 pipeline；3D 文档甚至指出某些点需要 triple buffering。
- **可硬件化抓手**：把 buffer depth、slot credit、prefetch distance 做成 TargetHardwareSpec + descriptor/runtime contract；TMU 暴露 slot-ready/consume credit，Controller不必为每 tile stop/restart。
- **可量化实验**：不同 DDR/3D bandwidth、K depth、tail 下的 throughput/latency/VMEM overhead/energy Pareto。
- **证据**：`src/llmSched/src/llm_sched/eval_pipeline/dataflow_strategy.py:L517-L526`；`external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_controller.sv:L3-L10`、`L1455-L1458`；`docs/hardware/tars_v0.1.md:L1049-L1058`。

### H5. Variable-length Descriptor 的 byte-credit queue hardware

- **缺陷**：compiler/controller capability按 descriptor entry 数判断，RTL按总 word/4096B 判断；runtime还关闭 capacity enforcement。
- **可硬件化抓手**：queue descriptor增加 byte/word credits、entry-offset table 或 streaming fetch window；compiler在 emission 后按真实 variable-length words admission，并把 proof 交给硬件。
- **可量化实验**：不同 operator mix 的 queue occupancy、fetch bubbles、buffer utilization、head-of-line blocking；与固定 64-entry 模型比较。
- **证据**：wire max 39 words `inputs/descriptor_releases/accepted/descriptor-v8-0x8-rmsnorm-fp16-expanded-scalar-20260825-r1/authority/wire_schema.yaml:L74-L90`；compiler query `src/llmSched/src/llm_sched/orchestrator/authority_chain_builders/_runtime_launch.py:L411-L440`；RTL byte limit `external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_controller.sv:L4167-L4179`。

### H6. Plan-aware hardware telemetry 与校准 cost provider

- **缺陷**：当前 ranking 不是 latency model，optional analytical provider低置信且不含 contention；RTL counter寄存器存在但关键输入接 0。
- **可硬件化抓手**：按 `(release_digest, task_id, entry_id, sublayer_id, slot_epoch)` 标记 counter sample；接通 MXU/VPU/DMA/bank/sync stall，形成独立 Performance Report，再训练/校准 cost provider。
- **可量化实验**：predicted-vs-measured error、strategy regret、跨 shape/硬件配置泛化、计数器面积/功耗。
- **证据**：`src/llmSched/src/llm_sched/eval_pipeline/dataflow_strategy.py:L815-L871`；`src/llmSched/src/llm_sched/hardware_modeling/analytical_cost.py:L36-L94`；`external/tars-npu-ctrl/rtl/npu_ctrl/tars_npu_controller.sv:L2515-L2539`。

### H7. 共享 DMA contention-aware scheduling / DMA 微架构协同

- **缺陷**：[A] 当前只有 1 channel、1 outstanding、12.8 Gbps（`hardware_specs/tars/modules/dma.yaml:L3-L10`），但 strategy fallback 的 movement/sync/bandwidth cost 全为 `None`；旧 analytical lane 的 shared-DMA penalty 只是 task-level 15% heuristic（`src/llmSched/src/llm_sched/eval_pipeline/resource_cost_builder.py:L650-L703`）。
- **可硬件化抓手**：compiler选择 DMA channel/priority/burst aggregation 与 per-core issue window；硬件提供 weighted arbitration、outstanding queues 和 wait attribution。
- **可量化实验**：双 core同时 preload/store 下的 fairness、tail latency、DMA utilization、MXU starvation；1-channel 与轻量多-channel/virtual-channel 比较。

### H8. 可配置 core/cluster/direct-link 的一致 topology-route contract

- **缺陷**：schema允许 core link 只取 `synchronization/data_transfer`，但 route query 判断 direct link 时检查的是 `data_movement/direct_core_link`，可表示值与可识别值不一致（`src/llmSched/src/llm_sched/hardware_modeling/schema/root.py:L35-L39`；`src/llmSched/src/llm_sched/hardware_modeling/query/route.py:L208-L224`）。task sync 又硬编码 core0/core1（`src/llmSched/src/llm_sched/orchestrator/task_synchronization.py:L1066-L1096`）。
- **可硬件化抓手**：统一 typed link protocol，支持 topology-discovered N-core queue/sync endpoint、direct data link bandwidth/credit，并扩展 compiler partition/routing。
- **可量化实验**：2/4 cores、link on/off、shared-DMA fallback 下的 scalability、sync pressure、route regret。

### H9. 3D-DRAM/Chiplet NUMA placement + SDMA streaming prefetch

- **缺陷**：[P] 文档已有 TSV-local macro、remote-via-NoC、SDMA 和 compiler placement设想；[M] typed schema、IR、route、descriptor 和 RTL admission 都没有对应对象。
- **可硬件化抓手**：新增 memory-tier/macro affinity/bandwidth/thermal facts；PhysicalMemoryPlanIR扩展 3D placement，MovementSync扩展 SDMA/NoC route；SDMA按 compiler address sequence执行并回传 credit/stall。
- **可量化实验**：weight/KV/activation partition、local-hit ratio、NoC hops、TSV bandwidth、prefetch hidden ratio、thermal hotspot；DDR vs 3D、static vs topology-aware。
- **证据**：`docs/hardware/tars_v0.1.md:L1006-L1026`、`L1038-L1079`；当前缺失边界 `src/llmSched/src/llm_sched/hardware_modeling/schema/root.py:L57-L99`。

### H10. 为 compiler-owned sublayer 设计最小新 wire + 轻量硬件 decoder

- **缺陷**：活动 wire仍是 0x8；最新 Wayfinder提出 0x9-only production、mirror step 与 family-specific sublayer fields，但明确仍是 planning evidence。
- **可硬件化抓手**：比较“显式每 slot 地址”与“ping base + mirror_step + role offsets + lifecycle”两种编码；实现小型 decoder/validator，保证无 replan、可 fail closed，并测 descriptor bytes、decoder area、launch bandwidth。
- **可量化实验**：8 family、tail/rank/profile coverage；wire reduction、decoder critical path/area、Controller state reduction、compiler↔RTL exact replay。
- **证据**：活动 0x8 `inputs/descriptor_releases/active-release.json:L1`；规划边界 `.scratch/llmsched-compiler-owned-sublayer-vmem-wayfinding/MAP.md:L52-L70`、`L190-L204`；ADR 保留 wire 独立决策 `docs/adr/0111-derive-sublayer-pong-from-one-mirror-step.md:L15-L21`。

### H11. Hardware Admission Engine / numerical receipt

- **缺陷**：Descriptor release publish 明确不要求 Controller/RTL receipt 或 Hardware Admission（`docs/adr/0113-publish-descriptor-releases-in-one-snapshot-transaction.md:L23-L26`）；compiler validation pass 也不声明 Controller/RTL numerical closure（`CONTEXT.md:L1618-L1642`）。
- **可硬件化抓手**：在 FPGA/RTL simulation/硅后建立同一 receipt schema，绑定 hardware digest、descriptor release、per-core queue、plan identity、input/output hash、counter snapshot；硬件/仿真器生成不可由 compiler伪造的 execution receipt。
- **可量化实验**：错误注入覆盖（地址、mask、tail、dtype、bank overlap、Controller replan drift）、诊断定位时间、回归吞吐；把“软件闭环”和“硬件已执行”严格分开。

## 9. 给主调研的组合建议

上述 11 个钩子可按三条主轴组合，但此处不替主任务选择最终五个方向：

1. **计划可执行性轴**：H1/H4/H5/H10/H11，目标是让 compiler-authored plan 成为硬件唯一可验证执行合同。
2. **反馈可优化性轴**：H3/H6/H7，目标是让 bank/DMA/TMU/MXU 的真实 stall 能反向校准策略与 placement。
3. **架构可扩展性轴**：H2/H8/H9，目标是让同一 typed hardware ABI覆盖不同 VMEM、core/cluster、3D/NoC/SDMA 配置。

任何论文/专利方向都应至少同时包含：一个新的硬件结构或可观测机制、一个 compiler/IR/descriptor 协同协议、一个 fail-closed correctness/admission 条件，以及 RTL/FPGA/仿真/硅后可测的性能或面积功耗指标。这样贡献才不会退化成“编译器软件优化”。