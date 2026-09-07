# Round 2：Compiler-generated dependency contract + hardware dynamic dispatch 的批判性科研探索

日期：2026-09-03

性质：科研方向探索与可行性判定；不是法律新颖性意见，不是任何已实现能力的声明，也不授权修改活动 authority、Controller 或 RTL。

证据状态：TARS 事实取当前 typed hardware authority（`hardware_specs/tars/`）、公共编译链代码、Controller 参考模型和 round 1 的 [repo-evidence.md](../round1/repo-evidence.md)。本轮通过 Web 检索打开过原始页面的条目在 [literature-register.md](literature-register.md) 标为“已核验”。定量结论来自一个**未校准的玩具离散事件模型**（[toy-sim/r4sim.py](toy-sim/r4sim.py)），只用于给出量级和方向，不是 TARS 性能预测。

---

# 总体结论

> **“编译器给依赖合同、硬件按真实完成动态派发”在体系结构上就是 Lee–Ha 分类中的 static-assignment scheduling（1989），在微结构上是任务粒度的 CDC 6600 式 scoreboard（无重命名），在工业上已由 VTA 的依赖 token 队列、Gaudi Sync Manager、Ascend 的 set_flag/wait_flag、AIE 的 lock/ObjectFIFO 以及 2026 年基于 openNVDLA 的乱序算子调度器覆盖。作为整体方向，它属于“有工程价值但科研 novelty 较弱”。**
>
> **但在玩具模型里出现了一个可以被深入的子问题：在 TARS 这种“每核顺序发射 + 共享 DMA 动态仲裁”的基线上，运行时乱序自由度的收益在没有内存复用约束时恒为 0，只有当编译器为了 VMEM 复用而张贴了 WAR/WAW 伪依赖时才出现（玩具模型中 0.4%–4.5%），而这些伪依赖本身让最优静态调度损失 3%–8%。也就是说，“NPU 要不要动态派发”这个问题的真实内容是“编译器的静态地址复用决定应该多保守”。这个 memory reuse ↔ legal partial order ↔ dispatch freedom 的三角关系是真实的，但它首先是编译器内部的联合优化问题（Pinter 1993 在寄存器层面已经给出范式），硬件动态派发只是它的一种兜底实现。**

因此本轮的判定是：

| 判定档位 | 结论 |
|---|---|
| 已基本被现有工作覆盖 | **是**，对“给 NPU 加任务级乱序/依赖驱动派发”这一整体表述成立（见第七节 prior art）。 |
| 有工程价值但科研 novelty 较弱 | **是**，对 TARS-SC 当前形态（2 core、1 通道 DMA、单 cluster）成立；消除 descriptor 间气泡（DAE 预取）和显式化伪依赖都值得做，但不成论文。 |
| 存在值得深入的子问题 | **是**：“flexibility-certified static memory planning”——编译器在容量约束下选择哪些 buffer 复用、哪些分离，以最小化在延迟不确定性下张贴约束的期望代价，并把结果写成硬件可校验、无死锁的 partial-order contract。其新颖性中等，先例压力中等，且**必须先通过一个可快速证伪的方差测量门**。 |
| 可形成较强的 compiler–architecture co-design 方向 | **暂不成立**。只有当测量门显示任务延迟具有重尾（而非平滑抖动）、且目标配置扩展到 ≥ 4 核多通道 DMA 或数据相关图（MoE 路由、可变长 batch、）时，硬件侧动态派发才可能成为主线；后者的正确先例是 Ha & Lee 1991 的 quasi-static scheduling，而不是 out-of-order。 |

---

# 一、要解决的问题

## 1.1 目标与边界

目标：判断“compiler-generated dependency contract + hardware dynamic dispatch”是否是一个值得投入的 TARS 科研方向；如果不是整体成立，找出其中真正未解决的子问题，并给出最小证伪实验。

边界：

- 硬件锚点仍是当前绑定的 TARS-SC：1 cluster、2 core，每 core 一个 MXU/VPU/TMU 和 4 MiB VMEM，cluster 共享 1 通道、1 outstanding 的 DMA，core link 只有同步（`hardware_specs/tars/target_hardware_spec.yaml`、`modules/dma.yaml`）。Controller 每核 64 深队列、6 个 dependency slot、6 个 signal slot、`patching: static_descriptor_delivery`（`modules/controller.yaml`）。
- 编译锚点是 9 阶段公共权威链；`PhysicalMemoryPlanIR` 是唯一 placement 所有者（ADR-0110），本轮任何建议都不允许硬件重新拥有 placement。
- 不在边界内：多 cluster/NoC（typed schema 无此模块）、训练、GPU。

## 1.2 贯穿全文的例子

**DiT-XL/2@512 的一个 block（N=1024，d=1152，16 heads），CFG 的 cond/uncond 两支不做 M 维折叠，而是作为两条独立的 13-op 链执行；注意力按 head 切分：core0 跑 heads 0–7，core1 跑 heads 8–15；O-proj 需要跨核 partial-sum；两支共享同一片 VMEM（X 2.36 MB、FFN 隐层 tile、K/V 驻留区在两支之间复用，因为 4 MiB 装不下两支）；cluster 共享单通道 DMA。**

选这个例子的原因：它同时含有动态派发理论上需要的三种结构——每核多条独立链（cond/uncond）、跨核耦合（partial-sum）、由容量导致的内存复用伪依赖——而 round 3 的 R4 方向恰恰会把 CFG 折叠成 M=2N 从而消灭第一种结构。这一张力本身是本轮的结论之一。

## 1.3 当前阻塞事实

- **同核依赖是隐式的。** `MovementSyncPlanIR` 对同核 producer/consumer 的可见性证明类型是 `same_core_queue_retirement`（`src/llmSched/src/llm_sched/orchestrator/task_synchronization.py:796-800`），即“前一个 descriptor 退休了所以数据就绪”。队列策略明确写为 `in_order_head_blocking`（同文件 `:1048`）。链上没有任何地方枚举同核的 WAR/WAW 伪依赖，因为总序使它们不需要被枚举。
- **跨核同步是计数式、按序消费的。** DEP/SIGNAL 是每对 core 一条 FIFO 序列：consumer 用 `_next_rx_seq[src_core]` 期望下一个序号，producer 完成后 `publish(sequence+1)`（`external/tars-npu-ctrl/ref_model/tars_ref/core/npu_controller.py:596-711`）。第 k 个 SIGNAL 必须被第 k 个 DEP 消费——**这个协议只在双方都按编译器给定的总序执行时才有定义**。任何一侧乱序都会让序号错配。
- **buffer 生命周期定义在总序上。** `PhysicalMemoryPlanIR` 的 lifetime 记录是 `start_order_index/end_order_index`，ordering authority 是 `DataflowPlanIR.selected_strategy_records`（`_physical_memory.py:2512-2557`）；复用判定用 `_lifetime_resident_at(lifetime, task_position)`（同文件 `:1759-1766`）。换掉总序，现有所有 alias/reuse 证明失效。
- **descriptor 之间没有重叠。** 参考模型一次只持有一个 `_pending_descriptor`，执行完 sublayer 流水、fire SIGNAL、推进 head 后才取下一个（`npu_controller.py:551-594`）。RTL 的 `prefetch_*` 状态机是 sublayer 内 ACT/WGT 下一 K chunk 的 slot 预取（`tars_npu_controller.sv:1058-1097`、`:3882-3918`），不是下一个 descriptor 的预取。`controller.yaml` 声明 `max_inflight_tasks_per_core: 64`，但没有任何实现消费它。
- **硬件派发窗口被 wire 字节数锁死。** RTL 每次 launch 要求 `words*8 <= 4096 B`（round 1 [repo-evidence.md](../round1/repo-evidence.md) §5.3），一个 0x8 descriptor 最多 39 words，因此硬件同时可见的 descriptor 数 ≤ 13。任何“ready window”设计都受此上界约束，除非先解决 H5。
- **没有任何延迟方差证据。** MXU/VPU/DMA busy 与 stall 计数器在 RTL 顶层接常量 0（repo-evidence §7）；cost provider 是 `analytical_proxy_not_cycle_exact`。本方向的全部前提——“运行时完成时刻不确定”——在 TARS 上目前是假设，不是测量。

---

# 二、当前流程：这个 block 今天会如何跑

编译期（每一步只描述行为）：

```text
 1. GraphClusterIR：26 个 op（13×2 支）进入，无 fusion，无 CFG 识别
 2. DataflowPlanIR：逐 op 在 single_map/seq_m/chn_n 中选策略与 core；SDPA 按 head 切到两核；
    产生一个跨全部 op 的总序（selected_strategy_records 的顺序）
 3. StreamTensorPlanIR：为每条 tensor edge 建立 stream/storage view
 4. PhysicalMemoryPlanIR：按总序上的 lifetime 区间做 first-fit；cond 支的 X/隐层 buffer 与 uncond 支
    同名 buffer 落在同一地址（复用）；K-step 双缓冲 slot = k mod 2
 5. MovementSyncPlanIR：同核 producer→consumer 记为 same_core_queue_retirement（不生成任何 wire 依赖）；
    跨核 partial-sum 记为 cross_core_counted_occurrence，为 (core0→core1)、(core1→core0) 两条序列
    各分配递增序号；出 availability/deadlock proof，全部基于总序
 6. CoreExecutionPlanIR：每核一个 in-order 队列，estimate_policy = static_order_only_not_final_schedule，
    cycle 上界为 None
 7. RuntimeLaunchIR / DescriptorEmissionIR：每核一个 package；每个 0x8 header 带 dep_mask/signal_mask
    （按 core 位），不带任何 buffer 或事件标识
```

运行期（每核）：

```text
 8. Controller 取队列头 descriptor，解析、校验；GEMM 走 GemmSublayerPlanner 重新切 K chunk
 9. 若 dep_mask 非 0：等待 CSM 上来自对方核的下一个序号可消费；消费后开始执行
10. 执行 sublayer 流水：DMA 预取 slot(k+1) 与 TMU/MXU 计算 slot(k) 重叠（descriptor 内部 DAE）
11. 完成后 fire signal_mask 上的序号，推进 head，取下一个 descriptor；
    下一个 descriptor 的首个 DMA 此时才开始（descriptor 间无重叠）
12. 共享 DMA：两核各按自己的队列顺序发起请求，通道在请求级仲裁（假设；待 RTL 确认）
13. uncond 支：等 cond 支同核前序 op 全部退休（队列顺序）才能开始，即使其数据早已就绪；
    因为它的 X buffer 与 cond 支复用同一地址，这个等待也是正确性所需
```

关键性质：**每核是“自定时（self-timed）”的——顺序由编译器定死，时刻由数据到达决定；跨核同步按序计数；同核伪依赖被总序吸收，从未被显式表示。** 按 Lee–Ha 1989 的四分类，TARS 今天精确地处于 self-timed 档。

---

# 三、推荐流程：三道门，而不是“加乱序”

推荐的不是直接实现硬件动态派发，而是一条以证伪为先的路径。变化的步骤加 **[G*]** 标记，与第二节逐步对照。

## 3.1 门 A：编译器内显式化 partial-order contract（无 wire 变化）

```text
 2'.[GA] DataflowPlanIR 输出的不再只是总序，而是 task DAG + 每 task 的 core/engine 绑定 + 一个
        建议的 self-timed 线性化（保持向后兼容）
 4'.[GA] PhysicalMemoryPlanIR 对每个“复用候选对” (buffer a, buffer b) 做二选一：
        复用 → 张贴约束 reader(a) ≺ writer(b)，记录其在方差模型下的期望关键度（slack）；
        分离 → 消耗额外 VMEM，不张贴约束。目标：容量约束下最小化“张贴约束的期望代价”。
        输出 PartialOrderContract = 数据边 ∪ 张贴的内存边 ∪ 资源边（单 DMA、mirror slot）
 5'.[GA] MovementSyncPlanIR 对 contract 出三份证明：
        (i) 无环（数据边 + 内存边 + 跨核边合起来无环——玩具模型里 reuse 边与跨核耦合边直接构成了环）；
        (ii) 任意线性化下的容量可行（每个地址在任何合法顺序下不被两个存活 buffer 同时占用）；
        (iii) 归约顺序不变（所有 K 维/跨核 partial-sum 的累加顺序是 contract 中的固定边，禁止乱序）。
        同核伪依赖首次成为显式记录，而不是 same_core_queue_retirement 的副作用
 6'.[GA] CoreExecutionPlanIR 仍产出 in-order 队列，但队列顺序是从 contract 中选出的、
        在方差模型下期望 makespan 最小的线性化，而不是 DataflowPlanIR 的选择顺序
```

门 A 在今天的硬件上就有收益：玩具模型显示复用约束本身让最优静态调度损失 3%–8%，而“少复用一点”在同等噪声下优于“加动态派发”（第六节表 B-2）。它不改 wire，不改 Controller，完全在 ADR-0110 的所有权边界内。

## 3.2 门 B：方差测量与 oracle 上界（可快速证伪）

```text
 B1. 接通 RTL 顶层的 MXU/VPU/DMA busy 与 stall 计数器（H6），给 DDR 模型加入 refresh/row-miss 抖动；
     对现有 attention/GEMM/RMSNorm UAT bundle 采集 per-descriptor 时长分布
 B2. 用采到的分布驱动一个基于真实 CoreExecutionPlanIR + MovementSyncPlanIR 的离散事件回放器，比较：
     (a) 今天的 lane-self-timed（每核定序 + DMA 跨核仲裁）；
     (b) oracle static-assignment（同样的 core 绑定、同样的 contract、运行时按真实完成任意合法顺序派发）
 B3. 判据：(b) 相对 (a) 的端到端收益在 DiT block、LLM prefill、LLM decode 三类 bundle 上 < 5%（2 核）
     且在参数化 8 核/多通道配置上 < 10% → 硬件动态派发方向终止，只保留门 A 与 descriptor 间预取
```

## 3.3 门 C：仅在门 B 通过后进入的硬件

```text
 7'.[GC] 新 wire profile（经 descriptor authority runbook，不手改活动 YAML）：header 用命名事件替代
        按 core 的 dep_mask/signal_mask：wait_event_ids[≤4]、signal_event_id；buffer 段带 slot/epoch 标识
 9'.[GC] Controller 维护一个 ≤ 13 entry 的 ready window（受 4096 B launch 上界约束，见 1.3）与一个
        每核 32–64 项、8–16 bit 的事件计数器文件；就绪判定 = 全部 wait_event 计数满足 ∧ 目标 engine 空闲
        ∧ 目标 mirror slot 空闲；同一 engine 的多个就绪 task 按编译器给的静态优先级挑选
11'.[GC] descriptor 完成 → 事件计数 +1（替代 CSM 序号 publish）；receipt 按 task 身份而非队列位置记录，
        使 Hardware Admission 在乱序下仍可比对
12'.[GC] 共享 DMA 仲裁改为 contract 优先级驱动（这是玩具模型中唯一持续有价值的动态决策，见表 B-1）
13'.[GC] uncond 支的 op 只要事件满足且 engine/slot 空闲即可派发；若门 A 决定分离其 X buffer，
        它与 cond 支之间没有任何张贴边，可完全交错
```

门 C 的硬件在面积上是微小的（计数器文件 + 窗口比较器；2026 年 openNVDLA 版全流水调度器在 28 nm 为 0.462 mm²、13 mW，且它包含了 TARS 不需要的 ROB 与取指流水），真正的代价是：CSM 协议、admission 的可重放性、以及所有基于总序的证明都要重写。

---

# 四、为什么改变

| 步骤 | 当前缺陷 | 替换 | 如何消除缺陷 |
|---|---|---|---|
| 4 → 4' | 复用决定只看容量（first-fit），从不评估它张贴的伪依赖有多关键；uncond 支被 cond 支整条链串住 | 复用/分离二选一，带方差模型下的期望代价 | 伪依赖成为有价格的一等对象；玩具模型中它的代价（3%–8%）大于动态派发能追回的部分 |
| 5 → 5' | 同核伪依赖隐藏在队列顺序里；跨核 counted occurrence 在任何乱序下无定义；deadlock proof 基于总序 | 显式 contract + 无环/容量/归约顺序三证明 | 让“合法执行空间”成为可校验对象；玩具模型中 reuse 边 + 跨核耦合边直接成环，说明这一步不是形式主义 |
| 6 → 6' | 队列顺序 = 策略选择顺序，不是任何意义下的最优线性化 | 从 contract 中选期望 makespan 最小的线性化 | 在不改硬件的前提下吃掉“静态可见”的那部分收益 |
| 8–11 → 9'–11' | descriptor 间零重叠；ready 判定绑定队列头 | 命名事件 + 窄 ready window | 只在门 B 证明收益存在后才做；否则用最简单的 descriptor 间 DAE 预取即可消除气泡（VTA 先例） |
| 12 → 12' | DMA 仲裁与编译器意图无关 | contract 优先级驱动仲裁 | 玩具模型中把全局定序 DMA 改成跨核仲裁就回收了 2%–10%，是唯一持续有价值的动态决策 |

所有变化保留 round 1–3 的所有权原则：编译器出合同和证明，硬件校验并执行，Controller 不重新拥有 placement、tile 顺序或归约顺序。

---

# 五、仍缺什么（按阻塞顺序）

1. **缺失证据：任务延迟方差的形状。** 整个方向的前提是运行时完成时刻不确定，但 RTL 计数器接 0、DDR 模型保真度未知。玩具模型给出的分界是：**平滑抖动（对数正态，CoV ≤ 0.6）下乱序收益为 0；重尾（5% 任务慢 4×）下才有 2%–10%。** 门 B1 是第一件要做的事，且不依赖任何设计决策。
2. **所有权决策：是否接受 static-assignment 作为目标执行模型。** 它会让同一份 Descriptor 流在两次运行中产生不同的 descriptor 完成顺序。当前 Hardware Admission、receipt 和 static replay 的设计（H11、ADR-0113）都假设顺序可重放。若团队认为可重放性是不可让步的（Groq 正是以此为卖点），门 C 应直接关闭，只做门 A。
3. **接口决策：命名事件替代 counted occurrence。** 6 个 dependency/signal slot 的 typed authority、CSM 序号协议、0x8 的 dep_mask/signal_mask 都要换。事件 ID 数量有限时又会引入新的串行化（Ascend Auto-Sync 与 openNVDLA 版调度器都要做 event-ID 分配），这是门 C 的隐藏成本。
4. **失败路径：contract 成环。** 内存复用边与跨核数据边组合可以形成环（玩具模型在第一次加入跨核耦合时就触发了 `cycle` 断言）。门 A 的无环证明必须 fail-closed，并在成环时回退为“分离 buffer”而不是“回退为总序”，否则又回到今天。
5. **可以等待：** 数据相关图（MoE 路由、可变长 batch、R1 的 reuse/delta 变体选择）是动态派发更强的动机，但它属于 quasi-static scheduling（Ha & Lee 1991）的范畴，应作为独立方向 P3 评估；多 cluster/NoC 与 tile 粒度任务（Tenstorrent/Cerebras 形态）超出当前 typed schema。

---

# 六、定量推理：玩具模型说了什么、没说什么

模型（[toy-sim/r4sim.py](toy-sim/r4sim.py)）：每条 stream 是 12 个 op 的串行链（长/短交替，类比一个 block 的 GEMM/VPU op）；每个 op = LOAD（占 DMA 资源）→ COMP（占本核 compute 资源）；stream 轮转绑定到 core；可选跨核耦合（每 4 个 op 需要兄弟 stream 上一 op 的输出，类比 partial-sum）；可选内存复用边（同核下一条 stream 的同名 buffer 复用地址：`COMP(s,j+1) ≺ LOAD(s+cores,j)`，按概率 reuse ∈ {0, 0.5, 1.0} 张贴）。三种执行策略：

- **ST**：全局 list schedule（按均值、关键路径优先）得到每个资源的固定顺序，运行时自定时；
- **lane-ST（TARS 基线）**：每核 compute 与 DMA 发射顺序固定，共享 DMA 在两核队头之间按优先级动态仲裁；
- **SA**：static-assignment，每个资源在就绪集合中按同一静态优先级动态挑选。

噪声：对数正态（CoV 0.1/0.3/0.6）；“tail”模式再叠加 5% 任务慢 4×。200 次采样取均值。

**表 B-1：SA 相对 lane-ST 的 makespan 收益（%）。** 行 = 例子对应配置（4 streams/2 cores/shared DMA ≈ 本文例子；8/2/shared ≈ batch 2；32/8/per-core ≈ 8 核扩展）。

| 配置 | 噪声 | reuse=0 | reuse=0.5 | reuse=1.0 |
|---|---|---:|---:|---:|
| 4/2/shared | 对数正态 CoV 0.6 | 0.0 | 0.0 | 0.0 |
| 4/2/shared | + 重尾 | 0.0 | 0.0 | 0.0 |
| 4/2/shared | + 跨核耦合 | 0.0 | 1.2 | 1.1 |
| 4/2/shared | + 重尾 + 耦合 | 0.0 | 1.1 | 1.4 |
| 8/2/shared | + 重尾 + 耦合 | 0.0 | **4.5** | 2.7 |
| 32/8/per-core | 对数正态 CoV 0.6 | 0.0 | 0.1 | 0.0 |
| 32/8/per-core | + 重尾 + 耦合 | 0.0 | 3.6 | 3.9 |

三个可复现的观察：

1. **reuse=0 的列全部为 0。** 只有数据依赖时，编译器按均值算出的每核顺序在任何噪声下都不比运行时乱序差。这与 Bambha & Bhattacharyya 2005 的结论一致（低到中等变异性下 OT/ST 不逊于动态），也与 2026 年 openNVDLA 调度器作者自己的注释一致（“算子级任务基本串行，32 项 ROB 已足够”）。
2. **乱序收益只在张贴了内存复用边之后出现**，且最高 4.5%。它的物理含义是：伪依赖把两条本可交错的链焊在一起，运行时抖动让这个焊点时而在关键路径上时而不在，动态派发只是在焊点不关键时把它绕开。
3. **表 B-2（同一模型）：** reuse 边本身的代价 > 动态派发的回收。以 8/2/shared + 重尾 + 耦合、CoV 0.6 为例：reuse=0 时 lane-ST 4772；reuse=0.5 时 lane-ST 5142、SA 4909。即“多花 VMEM 不复用”（4772）优于“复用 + 硬件乱序”（4909）。用户提出的三角 trade-off 是真实的，但它的主导项是静态复用决定，不是动态自由度。

**表 B-3：全局定序 DMA（ST）相对 lane-ST 的损失（%）**：4/2/shared 重尾下 3.3%–7.6%，8/2/shared 重尾下 5.4%–10.2%。这说明在单通道共享 DMA 的机器上，唯一持续有价值的运行时决策是 **DMA 请求的跨核仲裁**——TARS 若已如此（待 RTL 确认），这部分收益已被拿走。

模型**没有**覆盖的东西（也是它可能低估或高估的地方）：tile 粒度任务与 bank 冲突；descriptor 取指/解码开销；数据相关图；异构 stream；不同 op 的方差差异；单 outstanding DMA 的延迟绑定带宽（这会让 decode 场景完全 DMA 受限，任何计算侧乱序都无意义）。它是给门 B 定判据用的，不是结论。

---

# 七、Prior art：已经覆盖到哪里

| 层面 | 最近的先例 | 覆盖了什么 | 留给 TARS 的空隙 |
|---|---|---|---|
| 执行模型分类 | Lee & Ha 1989【审】四分类；Ha & Lee 1991 quasi-static【审】 | fully static / self-timed / static-assignment / fully dynamic 的定义与取舍；数据相关构造的准静态处理 | 无：本方向 = static-assignment |
| 静态放置 + 动态发射 | TRIPS/EDGE SPDI（Nagarajan et al. PACT'04【审】；Burger et al. Computer'04【审】） | 编译器放置、硬件按操作数到达发射；调度器要同时管 locality/contention | 粒度从指令到 task，但范式相同 |
| 任务级乱序硬件 | Task Superscalar（Etsion et al. MICRO'10【审】）、Picos、Carbon（Kumar et al. ISCA'07【审】）、TaskStream（Dadu & Nowatzki ASPLOS'22【审】） | 硬件依赖检测、任务队列、任务级 dataflow 执行 | 它们在硬件里做依赖分析；本方向让编译器做——这正是 Gaudi/Ascend/VTA 的做法 |
| 部分序调度 | Policella, Cesta, Oddi, Smith（ICAPS'04、AI Comm. 2007【审】）Partial Order Schedules | “张贴最少前序约束使任意时间可行解都资源可行”，两种生成算法，鲁棒性度量 | 资源是累积型，不含地址复用；无硬件 |
| 有序事务 vs 自定时 | Sriram & Lee 1997【审】；Bambha & Bhattacharyya 2005【审】 | OT 在低变异性下不逊于 ST 与 FD；变异性升高后 ST、FD 依次胜出；给出 crossover 实验 | 直接预言了表 B-1；NPU 版本需要重做但结论可能不变 |
| 分配 ↔ 调度自由度 | Goodman & Hsu 1988【审】；Pinter 1993【审】parallel interference graph；Bradlee et al. 1991 | 寄存器复用引入伪依赖限制调度；构造不引入伪依赖的分配 | 对象从等长寄存器换成变长、分 bank 的 SRAM 区间，且允许硬件延迟解析——这是门 A 的科研内核 |
| 并行下的安全复用 | Safe Optimized Static Memory Allocation for Parallel DL（MLSys'23【审】）；COSMA（2023【预】） | 给定并行流，求可证明安全的最小复用约束集；调度/分配/替换联合 ILP | 只做“给定并行求安全”，不做“为并行度选择复用”；无运行时乱序 |
| SDF buffer–吞吐 Pareto | Stuijk, Geilen, Basten DAC'06（记忆/未核验） | 自定时 SDF 中 buffer 大小与吞吐的 Pareto 前沿 | 稳态周期图，非 DAG；FIFO 深度，非地址 |
| 工业 NPU 依赖驱动 | VTA（Moreau et al. 2018【预】/IEEE Micro'19）RAW/WAR token 队列；Gaudi 3 Sync Manager【技】；Ascend Auto-Sync set_flag/wait_flag【技】；AMD AIE locks/ObjectFIFO【技】；Tenstorrent circular buffer + semaphore【技】；M100（2026【预】）“orchestrated dataflow”：每 PE 顺序、跨 PE 乱序完成 | 编译器生成同步合同、硬件按计数事件触发；buffer depth 作为可调的“静态重命名”深度 | 全部是 self-timed 或每 PE 顺序；无一给出复用/自由度的联合优化或证书 |
| NPU 算子级乱序调度器 | A fully hardware-managed scheduling architecture for AI accelerators（2026，J. King Saud Univ. CIS【审】） | openNVDLA 上 OCSR + 32 项 ROB 的乱序算子派发；30% 收益全部来自消除 CPU/驱动调度开销 | TARS 已有硬件队列，这 30% 不存在；作者自认算子级并行有限 |
| 确定性反例 | Groq TSP（Abts et al. ISCA'20【审】） | 移除所有 reactive 元件（arbiter、cache），编译器精确知道完成时刻 | 证明“编译器不知道完成时刻”是设计选择而非必然；TARS 的不确定性来自 DDR 与共享 DMA |

结论：**“编译器合同 + 硬件按事件派发”是 2018–2026 工业 NPU 的通行做法；“允许顺序自由”是 TRIPS/Task Superscalar/openNVDLA-2026 已做的事；“分配决定调度自由度”是 1988–1993 编译器文献的核心结果。** 未被同时覆盖的只有第六节暴露的那一个组合：变长分 bank SRAM 上的复用决定 × 方差模型 × 硬件可校验的部分序合同 × 无死锁证明。

---

# 八、对十个问题的直接回答

1. **问题是否真实存在，何时最明显。** 存在但被高估。它需要三件事同时成立：每核有 ≥ 2 条独立链、任务延迟重尾、编译器因容量张贴了伪依赖。LLM decode 不满足（单通道 DMA 是唯一瓶颈，计算侧顺序无意义）；单 block DiT/prefill 在 op 粒度是一条链，不满足第一条；round 3 的 R2/R4 融合与 CFG 折叠进一步消灭独立链。最明显的场景是 batch ≥ 2 的图像生成、MoE 专家、多请求 decode 共存——即多流共享 VMEM 的场景。
2. **为何纯静态不够、动态能解决什么。** 纯静态（self-timed）在只有数据依赖时不逊于动态（表 B-1 reuse=0 列）。动态派发能解决的只有一件事：让被伪依赖焊接的两条链在焊点不关键时绕开。它不能解决 DMA 带宽、bank 冲突或归约顺序。
3. **最合理的职责边界。** 编译器：DAG、core/engine 绑定、地址、复用/分离决定、张贴约束、归约顺序、静态优先级、无环/容量证明、一个兼容的线性化。硬件：命名事件计数、就绪判定、engine/slot 占用、按静态优先级挑选、DMA 仲裁、按 task 身份出 receipt。硬件不做：图分析、地址分配、重命名、优先级计算。
4. **新的 correctness 问题。** (i) 同核 WAR/WAW 从隐式变显式，必须枚举；(ii) counted occurrence 协议在乱序下无定义，必须换命名事件；(iii) 复用边 + 跨核边可成环 → 死锁，必须 fail-closed；(iv) 事件 ID 有限 → 新的串行化；(v) 浮点归约顺序必须是合同中的固定边；(vi) 可重放性与 admission receipt 需要按 task 身份而非队列位置；(vii) 双缓冲 slot=k mod 2（ADR-0111）在 descriptor 内仍成立，跨 descriptor 的 slot 占用要进入 scoreboard。
5. **是否存在值得研究的联合优化。** 存在，且它是本轮唯一保留的科研内核：`min E[makespan(contract, noise)] s.t. capacity`，决策变量是每对复用候选的复用/分离与线性化，输出带证明的 contract。任务粒度进入方式：更细的 task 增加自由度但被 4096 B/13 descriptor 的窗口和 39 words/descriptor 的 wire 成本抵消——粒度选择与 H5/H10 耦合。
6. **硬件结构与代价。** 每核 32–64 × 8–16 bit 事件计数器、≤ 13 项 ready window（每项 ≤ 4 个 wait 引用）、engine/slot 占用位、优先级比较器；面积与功耗在 4 MiB VMEM 面前可忽略（参考 2026 年 openNVDLA 版 0.462 mm²/13 mW 含 ROB 与取指流水）。真实代价是验证复杂度、CSM 协议重写、可重放性丢失、以及 descriptor 取指带宽（窗口内每项都要先解码）。
7. **是否已被覆盖。** 见第七节：整体表述已被覆盖；子问题（第 5 条）未被同时覆盖。
8. **反例。** (a) 它就是一个硬件任务调度器（Gaudi SM / Ascend TS / VTA）；(b) 玩具模型中相对 TARS 基线的收益 ≤ 4.5%，且只在复用约束下出现；(c) 同一模型中“少复用”优于“复用 + 乱序”；(d) Groq 证明可以靠确定性硬件消灭前提；(e) round 3 的融合方向系统性地减少独立链；(f) 2026 年 openNVDLA 调度器的 30% 来自 TARS 不存在的软件开销。
9. **真正的 novelty 核心（如果有）。** 不是“NPU 乱序”，而是：**“在静态地址分配的 NPU 上，运行时调度自由度完全由编译器张贴的内存伪依赖决定；因此分配器应当以‘方差模型下张贴约束的期望关键度’为目标，并输出一份任意合法线性化都容量可行、无死锁、归约顺序不变的硬件可校验合同。”** 这把问题从体系结构搬回编译器，硬件动态派发退为可选的兜底。
10. **论文方向比较。** 见第九节。

---

# 九、可能的论文方向

| 方向 | 主张 | 创新性 | 实现难度 | prior-art 压力 | 可验证性 | 判定 |
|---|---|---|---|---|---|---|
| P1 Flexibility-certified static memory planning（门 A） | 复用/分离决定以方差模型下的期望代价为目标；输出无环/容量/归约三证明的 contract；在自定时硬件上直接见效 | 中 | 中（纯编译器；需要方差模型） | 中（Pinter 1993、MLSys'23、Policella 2007、Stuijk 2006） | 高（DES + 现有 bundle；无需 RTL） | **推荐先做**；收益上限由门 B 决定 |
| P2 Static-assignment NPU with certified partial-order contract（门 C，即用户原始想法） | 命名事件 scoreboard + ready window + contract 优先级 DMA 仲裁 | 低–中 | 高（新 wire、CSM、Controller、RTL、admission） | 高（VTA、Gaudi、Ascend、TRIPS、Task Superscalar、openNVDLA-2026、Lee–Ha） | 中（RTL 仿真；需先有方差） | 仅在门 B 通过（≥ 10% @ 8 核）后立项 |
| P3 Quasi-static contract for data-dependent loops | 编译器生成变体空间（MoE 专家子集、可变 batch、R1 的 reuse/delta 变体），硬件按运行时标量在预验证变体间选择 | 中–高（NPU 语境下） | 中 | 中（Ha & Lee 1991、Cambricon-D/Ditto、TeaCache） | 中 | 比 P2 更强的动态派发动机；与 round 3 R1 合并评估 |
| P4 Latency-variance characterization of a descriptor-driven NPU（门 B 本身） | 测量并建模 DDR/共享 DMA/bank 引起的 per-descriptor 方差；给出 ST/SA crossover | 低–中 | 低 | 低（Bambha 2005 是 DSP 版） | 高 | 基础设施；可作 workshop 或论文 §Motivation |
| P5 Inter-descriptor decoupled access/execute | 下一个 descriptor 的首个 DMA 与当前 descriptor 计算重叠 | 低 | 低–中 | 极高（VTA、DAE 1984） | 高 | 工程项；任何 P1/P2 实验的必备基线，否则收益会被误归因 |

建议顺序：P4（门 B1，2–3 周，不依赖任何设计决策）→ P1（门 A，6–8 周，可独立成文）→ 按门 B3 判据决定 P2 是否立项；P3 作为 round 3 R1 的延伸单独评估；P5 作为基线先实现。

---

# 十、如果继续：problem statement、最危险的先例、最值得验证的假设、最小证伪实验

**Problem statement。** 给定 task DAG G、core/engine 绑定、VMEM 容量 C、任务时长分布 D，选择地址分配 A 与张贴约束集 P(A)，使得 (G ∪ P(A) ∪ 资源边) 无环、任意线性化容量可行、归约顺序不变，并最小化 E_D[makespan] ——分别在 self-timed 执行（P1）与 static-assignment 执行（P2）下求解，并量化两者差距。

**最危险的先例。** 对 P1：Pinter 1993（parallel interference graph——“先删除所有伪依赖再按需加回”正是门 A 的算法骨架）与 MLSys'23 安全复用约束集；对 P2：VTA 的 RAW/WAR token 队列 + Bambha 2005 的 crossover 结论 + 2026 年 openNVDLA 版乱序调度器；对整体表述：Lee & Ha 1989 已经命名了这个执行模型。

**最值得验证的假设。** H₁：在真实 TARS 方差下，oracle static-assignment 相对 lane-self-timed 的收益 < 5%（2 核）。若 H₁ 成立，P2 终止、P1 保留；若 H₁ 被推翻且收益集中在张贴约束处，P1+P2 联合成文；若被推翻且收益出现在 reuse=0 的配置（与玩具模型矛盾），说明存在模型未捕捉的方差源（bank 冲突、descriptor 取指），需要先重做 P4。

**最小证伪实验。** (1) 接通 RTL 计数器，对 3 个现有 UAT bundle 采 per-descriptor 时长；(2) 用 [toy-sim/r4sim.py](toy-sim/r4sim.py) 的框架替换为真实 CoreExecutionPlanIR/MovementSyncPlanIR 回放，接入采到的分布；(3) 输出 lane-ST 与 oracle-SA 的 makespan 及“收益中来自张贴约束的份额”。若两周内做不出 (1)，先用 DDR 模型的 refresh/row-miss 抖动作为替代分布并明确标注。

---

# 十一、与 round 1 产物的关系

- round 1 [academic-search.md](../r1-base/academic-search.md) 方向四（自描述 Descriptor、DAE、硬件 scoreboard）是本轮 P2/P5 的前身；round 1 [idea-redteam.md](../r1-base/idea-redteam.md) 对 D2 的判断（“单 outstanding DMA 下 scoreboard 只是安全机制而非性能贡献”）被本轮玩具模型在更一般的设置下重新确认。
- round 1 H5（4096 B 队列窗口）、H6（计数器接 0）、H7（共享 DMA 仲裁）、H11（receipt）在本轮分别成为派发窗口上界、门 B 的前置、唯一持续有价值的动态决策、以及乱序下 admission 的必要改造。

文献登记见 [literature-register.md](literature-register.md)。