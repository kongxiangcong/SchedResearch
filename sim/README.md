# R3 task scheduling research harness

这是依据 R1 的 compiler-owned placement/contract 思路新建的**未校准、无数值执行的研究模型**。不导入 llmSched，不复用活动 Descriptor wire，不声明兼容 TARS RTL。R1/R2 文件未修改。根问题是固定映射下的完成顺序变化是否值得硬件增加有限状态；不是复刻 CPU Tomasulo。

## 运行与产物

只需 Python 3.10+ 标准库；本次实际运行 Python 3.14。

```powershell
python -B -m unittest discover -s tests -v
python -B -m experiments.run --seeds 20 --training-seeds 8
python -B -m experiments.oracle_probe
python -B -m experiments.check_results
```

运行位置为仓库根目录。`experiments/configs/r3.json` 保存实际配置与训练/测试 seed；`experiments/results/r3/` 保存逐样本 CSV、全部指标 JSONL、统计摘要、seed0 trace、compiler contract 和源码 SHA256 manifest。`counterexample.json` 是四任务的可手算反例。`clairvoyant_probe.json` 只给**非精确、有未来信息的启发式可行解**；不能作为理论上下界。只有 `sim/scheduler/oracle.py:exact_orders` 对最多 8 个任务、固定映射、一元资源、非抢占、零开销模型枚举全部拓扑顺序并投影资源顺序，才称 exact oracle。

## 模块与契约

- `workload/`：逻辑任务、typed dependencies、synthetic 图和 LLM/DiT 结构 motif。
- `compiler/`：无环检查、静态资源映射、64B 对齐 buffer、命名 completion event、priority、admission 和 resource order。
- `memory/`：唯一地址 owner。默认不复用；手动复用必须证明 old writer 与所有 readers 先于 next writer。测试覆盖 WAR/WAW、错误别名、容量/对齐。
- `hardware_model/`：window entry/byte 双限额、有限 issue/wakeup service ports、实体执行/事件可见延迟；latency 子模块只产生 synthetic memory/communication service variation。
- `noc/`：以一元 resource 表示 chip NoC / interchip link / ingress/egress，**没有** packet/router/credit/flit 模型。
- `execution.py`：heapq 事件循环、原子 resource bundle、事件可见性、trace safety replay。
- `scheduler/`：A 固定资源顺序、B completion-ready/static priority、C age+pressure heuristic；oracle 独立。
- `metrics/`：等待类别、utilization、调度次数、状态/descriptor 的部分抽象预算。

Task 的 resources 已由 compiler 决定；hardware 不重选 mapping/address、也不发现 RAW。data/completion/WAR/WAW/reduction 边保持类型，执行时一律等 producer completion 可见。归约边禁止重排。一个 task 持有全部 resource bundle 直至完成：例如 DMA+shared SRAM 必须原子得到二者；竞争通过排队产生，**不**额外叠加随机 contention penalty。此粒度把 SRAM 占用近似为整个 task，可能高估实际 bank 竞争；不能代替 beat-level bank 或带宽共享模型。

执行器直接消费 Python Contract/Workload 对象；JSON descriptor 是合同导出投影，尚无 binary encoder/decoder roundtrip 或 decoder 硬件验证。Buffer 的 size 必须覆盖 task 输出声明。Admission 除 data DAG 的拓扑顺序外，还必须兼容附带的静态 resource order，避免有限窗口把静态资源队首永远藏在窗口后面；此版本选择拒绝这类合同，不引入绕过窗口取指机制。

Completion 的含义是本模型声明的 output-visible 实体完成；notification 可再延迟。所有同 timestamp 完成与立即可见事件先批量处理，然后仲裁。通知端口按 destination scheduler domain 序列化；第一条可在端口空闲时立即接受，后续受 service interval 限制。不会在 DMA issue 时唤醒 consumer。此版本只模拟单次有限 DAG，event ID 在单次运行不复用；没有 epoch wrap、fault recovery、外部 payload materialization 或数值 receipt。

Admission 使用 compiler 产生的拓扑 descriptor 流，同时限制每 domain entry 数与 wire bytes。任一 descriptor 大于 byte window 直接拒绝。不同 scheduler 使用同一 admission contract 和容量。已退休 completion/edge history 保留到本次 DAG 结束以支持晚 admission，**所以总状态不是 O(window)**。Completion 待处理项受 in-flight/window 间接限制；wakeup 待处理项最多是全图 edge 数，未实现额外有限 completion FIFO/credit backpressure。成本中显式记入它，而不是隐藏成免费网络。按 cluster 分 domain 仅是 issue/wakeup 分片，仍有全图 metadata；不是已验证的无中心分布式协议，更不是 hierarchical scheduler。

## Baseline 的准确含义

A 是强于顺序执行的 self-timed 静态基线。Compiler 用 longest-path/shortest/longest/fanout/四个固定随机 priority 的 8 种 list schedule 生成候选，选择预测 latency 最低者。固定**每个 resource**的顺序，运行时只等实际依赖和资源释放，可以提前于预测时间发射；没有 absolute-time padding。它不是全局最优 compiler，也不搜索 mapping/tiling/融合/缓存布局。所有候选都会显式重叠不同 engine、DMA 与独立任务。

A2 在同一个候选池用 8 个独立训练 seed 选择期望 latency 最小的**固定**资源顺序。测试 seed 为 0..19，训练 seed 为 10000..10007，不使用测试完成时刻。有限训练可能过拟合，A 一并报告供核对。主比较 B/C vs A2 使用 A2 的同一 mapping、地址、DAG、priority、admission 顺序、延时样本和硬件开销。

B 对合法 ready 集合使用同一 compiler priority 进行动态 dispatch。C 再增加 ready age 与当前 resource ready pressure，**同样固定 mapping**；不读取未来 service time、不扫描图求 critical path。C 只是一个成本更高的启发式，不是 Fully Dynamic，也不代表所有复杂 OoO 方案。C 与 B 的 issue/visibility 参数相同，这使 C 的性能比较偏乐观；额外 arithmetic/state 只做预算，没有 RTL critical-path 延迟。Fully Dynamic 的动态依赖发现、placement 和迁移都未实现，不能从本模型推断其收益。

所有运行使用 task-ID+seed 的稳定 hash 产生相同 service sample；compute 不随机。跨粒度 sweep 中同一粗任务的所有 tile 共享同一噪声因子，避免独立采样偷偷降低方差，总 service work 保持不变。tile overlap 假设对应 tile 可独立消费；不是从真实 attention/DiT 中已证明的 lowering。非 data 的同步/归约边仍为全 barrier。

## Workload 与统计限制

`clusters_*_central/local` 给予每个 scheduler domain 相同预算，local 因复制端口/window 而增加总预算；这是资源增配实验。`equal_budget_clusters_*` 则固定总 entry/byte/issue/wakeup 预算：local 每域 16 entries、4096B、1 issue lane、1 wakeup lane；central 乘 domain 数形成统一池。后者用于单独考察分片、queue fragmentation 和全局仲裁。同步 barrier 归真实 chip0.cluster0 域，没有额外 scheduler 域。两者均没有模型化控制网络物理距离，不能证明分布式时钟或布线收益。

Chain、fork-join、diamond、heterogeneous pipeline、critical-path+background 是可解释 synthetic DAG。LLM prefill/decode motif 使用 norm、projection、KV memory、softmax、FFN；DiT motif 独立包含 conditioning、AdaLN、cond/uncond 两支、attention/FFN/gate、跨核 gather、CFG combine 和 repeated-step 依赖。没有实际 model export、attention数值、GQA shape、SwiGLU 两路数值语义、MoE 路由或动态 batch；名字不能当作真实 LLM/DiT 性能结论。

多 cluster/chip motif 特意含阶段 barrier，以测试“规模增加一定增益”是否成立；它也限制了可利用并行度。没有 burst、cache、DRAM refresh/row-hit、链路拥塞相关性或 CPU/OS 多租户校准。默认 lognormal 噪声仅作用 memory/communication；heavy-tail 单列为 5%×4 合成假设，绝非 NPU measured fact。链路 contention 来自 resource 排队，服务噪声与排队等待分开。

摘要的 `B_paired_reduction_pct` 是逐样本 `(A2-B)/A2` 的平均，不是 `mean(A2)/mean(B)-1`。normal95 interval 是 20 样本的近似均值区间，仅反映人工分布采样不确定性；不覆盖模型误差，不应称硬件置信区间。p95 是小样本 empirical quantile。所有 seed0 trace 可独立验证依赖可见性、资源无重叠、每 task 恰好执行一次。没有性能 improvement 门槛筛除负结果。

上述 trace replay 的 visibility 验证范围仅为 `producer.finish + minimum completion latency`；它不独立重建 wakeup 服务队列或 issue ports 的全部时序。因此不能把它称为完整 wakeup/issue bandwidth 验证。端口串行化由专门的小例 unit test 覆盖，完整独立微架构 reference checker 尚未实现。

## 指标、成本与证据边界

Latency 是有限 DAG end-to-end completion time。`tasks_per_cycle` 是 task throughput，不能当 tokens/s 或 frames/s。resource utilization 的 busy 是 service time；reserved utilization 另含 dispatch setup。每个 resource 有 idle cycles，MXU/VPU/DMA/NoC 可从名字独立聚合。

所有 `*_wait_task_cycles` 是任务等待时间之和，分类依次为 admission、dependency、communication resource、memory resource、engine resource、static order、scheduler issue，彼此排他。它们**不是相加等于 latency 的全局 stall cycles**；例如两任务同时等待贡献两倍 wall time。Dependency wait 混合尚未完成与 wakeup 可见性等待，当前未逐原因细分。`critical_path_dilation` 是实际 latency / 忽略资源冲突的 sampled-DAG 最长路径；并非某条真实 path 的沿途 dilation。

Descriptor wire 是统一假想大小 `48 + 5*fanin + 8*resource_count` bytes，admission 与报告调用同一 helper；不是 R1 的 0x8，也不是 JSON 字节数。`abstract_state_bits` 给出 logical breakdown：active IDs/counters/status、priority、ready IDs、resource owner、completion queue、wakeup queue、持久 history、ports/cursors、C age。队列按本图/window 最坏条目预算，时间戳假设32bit；它是**部分抽象预算**，不是精确总门数或 silicon 上界。Decoder、routing、metadata cache/SRAM ports、布线、ECC、packet credits 和实际 comparator timing 未知。`priority_comparators_upper` 仅理想选择网络的比较器数量估计，不能等价面积。结果不能声明能耗改善、scheduler面积可忽略或production acceptance。

## 已知边界与下一步接口

下一轮优先导入真实 task trace / service distribution，增加 correlated memory/communication 模型和 compiler candidate 搜索强度。只有在 robust static 仍明显落后时，再扩 finite notification credits、event generations、distributed/hierarchical ownership 协议与更精确银行/NoC 模型。此版本可证明契约和排队语义下的反例与有限实验结果，不能证明一个 NPU architecture 值得立项。
