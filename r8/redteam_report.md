# R8 独立红队：来源、静态账本与单 payload 有限合同

日期：2026-09-05。审查范围是本轮新文件；没有修改 R1–R7 或主实验文件，没有运行设备、Phoenix 或旧轮实验。

**结论：在声明的 CPU fixture 和有限合同范围内通过，未发现账本、数值或事件扩展实现错误。接受本轮收窄后的结构结论；目标 admission、strong-static 性能残差和硬件机制收益均未通过本轮认证。**

审查读取了 `experiment_plan.md`、`prerun_clarifications.md`、`contract_experiment.py`、`target_contract.json`、`experiment_report.md`、来源/层级审计和 `results/` 全部实验产物。独立脚本 [redteam_check.py](redteam_check.py) 不导入主实验实现；[redteam_results.json](redteam_results.json) 绑定该脚本与主运行 receipt 的 SHA-256。执行命令：

```powershell
python -X utf8 -B r8/redteam_check.py
```

默认命令只读复算并打印 compact PASS，不改写已认证的 `redteam_results.json`。如需保存另一次独立回执，显式指定新路径，例如 `--output r8/redteam_recheck_new.json`。交付前修正了旧版默认覆写回执时间戳的问题：使用显式 `--output r8/redteam_results.json` 更新本次尚未冻结的回执一次，再执行默认复算，确认认证回执的前后 SHA-256 完全相同。该修正没有改变实验范围或运算。

已执行结果：6 个账本、20 个 core 记录、100 个 full-resident/tiled 分配布局、6 个完整数值 fixture / 18 个 mapping 输出、70 个事件扩展逐条通过独立核对。70 个扩展中，故障合同按预期包含 37 个错误读取；这是集合计数，不是发生概率。

## 1. 来源与数值许可

- 独立核对冻结 config/implementation 与 receipt 引用 hash；解析 `Qwen3_5MLP` AST，确认 down 是 `intermediate_size -> hidden_size` 且 `bias=False`。配置为 K=9216、完整 N=2560、BF16；已存 tensor-header 提取记录也给出 `[2560,9216]`。因此 N=[0,128) 的 full-K 输出切片有来源依据，不能称完整 down、MLP 或模型。
- R5 `full_width_specs.json` 保存的实际 projection 数值实验是 gate/up；本轮借用其中的冻结 source hash，不继承不存在的 R5 down 数值验收。down 的来源公式另见 `r5/sources/fullwidth_shape_manifest.json` 与 tensor-header 记录。
- M=1 只认证逻辑 CPU 运算和字节公式。R1 历史 MXU 的 M/N/K 需为 32 倍数，M1 不能直接提交该历史 native kernel；M32 仅满足历史 geometry，BF16/FP32、native tile/layout、多 cluster 仍未 admission。
- 从 seed 独立重新生成全部 X/W，用 `frexp + rint` 实现普通有限数的 BF16 ties-to-even rounding；所有存储 bits/hash 相同。六组随机输入/权重均非零，生成范围为 X∈[-0.25,0.25)、W∈[-0.125,0.125)。这些范围与实现已由首跑 receipt 的代码 hash 固定，未据结果修改。
- 使用 materialized BF16 精确乘积与 FP32 `cumsum` 独立重算 ascending-K 和 split-K，逐 bit 对上 18 个保存输出；另以 FP64 product sum 重算参考，和保存参考的最大差为 0。18 个诊断容差结果均为真；它们只覆盖这些 fixture，不形成 production 精度许可。
- C1N/C2N 都保持 ascending-K 次序，逐 bit 等于本轮 ordered FP32；C2K 的六组随机结果分别有 126、124、121、3874、3877、3885 个元素不同。抵消 fixture 复算为 ordered=1、split=0、FP64=2。**必须拒绝 split-K 与 ordered/官方 BF16 kernel 逐 bit 等价的推论；随机误差通过不能消除此边界。**

prepared down 输入不证明真实 gate/up 的激活分布和输入到达时序；研究 FP32 输出也不等于官方 BF16 输出。两种映射在给定实数算式上相同，不自动意味着目标 compiler 允许相同 regrouping。

## 2. 资源、地址与共同终点

独立检查矩形 K×N 分片互不重叠且面积正好 K×N，逐 core 输入/权重/partial 字节与 MAC，逐项验证所有地址区间不重叠且 fit 本轮 4 MiB 研究上限。已计 C2K cluster0 的 incoming-P 缓冲、两层 tiled buffer、独立外存 staging 槽。完整权重均为 2,359,296 B。

在本轮 private-unicast、紧凑逻辑 payload、共同外存输入与共同外存输出条件下：

| 项目 | C1N | C2N | C2K |
| --- | ---: | ---: | ---: |
| core 数 | 2 | 4 | 4 |
| 全体 X delivery | 36,864×M B | 73,728×M B | 36,864×M B |
| Y 外存写入 | 512×M B | 512×M B | 512×M B |
| remote partial payload | 0 | 0 | 512×M B |
| external staging 额外写+读 | 0 | 0 | 1,024×M B |
| 额外 FP32 reduction adds | 0 | 0 | 128×M |

独立核对最终 `.Y` transfer 完整且无重叠覆盖 N=[0,128)，每个都以外存可见事件结束；C2N 不必为了这个终点额外 gather 到 cluster0。若下一子图要求 cluster0 resident、上游已 K 分片驻留或使用 multicast，必须另立共同边界并重算，不能直接套用此表。

这些字段没有兑换成同价的“总带宽成本”：peer 链路、source read、destination write、local reduction 和外存访问各占不同资源；actual beats、padding、descriptor、协议开销和频率仍未知。C1N 与四核方案不是 equal-compute 性能比较；C2N/C2K 的四核/容量/路径预算应相同，但有效工作量之外的 reduction 与 X 副本量本就不同。

**分配的有限性必须保留：**4 MiB 是历史研究上限，不是当前可用 VMEM 认证；bank/保留区/packing/strided DMA 均 pending。主 transfer 账本采用 full-resident 的 X/W 名称，tiled 记录是另外的空间分配备选，尚未展开成各 tile 的实际 transfer/descriptor/live-interval 执行。100 个布局通过只认证这些不相交 payload span 的空间算术，不认证 native lowering、prefetch 时序或最优驻留。

## 3. 全部事件扩展与错误 witness

独立枚举使用不同事件枚举顺序和 symbolic generation 状态，再将读到的 generation 映射回 sentinel 数值；逐条核对保存 JSONL 的完整顺序集合、无重复、每次读数、correct 标志与每个保存的错误 witness。

| 合同 | 全部扩展 | 错误扩展 | 独立错误 witness / 读数 |
| --- | ---: | ---: | --- |
| safe | 5 | 0 | 无 |
| early_event | 40 | 26 | A,E,C,D,R,S,V → -7，目标尚未写入 |
| early_source_reuse | 6 | 1 | A,S,R,V,E,C,D → 97，捕获了复用后的源 |
| early_destination_reuse | 15 | 10 | A,R,S,V,D,E,C → 53，目的被提前复用 |
| conservative_source_release | 4 | 0 | 无 |

原始 payload 值为 11。safe 的 5 个扩展全部读到 11；conservative 的 4 个扩展也全部正确。较少允许的顺序不是更长 elapsed 的证据，没有时间单位或运行分布可供此推断。

证明的前提是单次 transfer、source 已 produce-visible、R 原子捕获一个 sentinel 到 transport、V 发布到目的、单个 consumer 数值读取与各一次覆盖。它没有逐 beat、多 reader、并发两个 partial、credits/backpressure、event-ID 复用、retry/error、producer→DMA 可见性或最后 Y store 可见性。因此：

1. 接受“该有限操作模型中，所给安全偏序足够；三个削弱版本允许错误读取”。
2. 不能把具体 V<E / R<S 等显式 signal 形式称为所有目标的唯一必要 ISA；blocking copy、静态 fence、现有队列语义或其他等价 happens-before 都可满足安全条件。
3. 不能声称 TARS 存在这些 bug、整个 C2K 端到端 completion 合同已经认证，或错误扩展数量是实际风险/性能分布。

## 4. Strong-static 与下一决定

本轮没有实测残差，也没有穷举 target-admitted strong-static 的时序最优。接下来的基线必须允许其实际支持的 output/K mapping、producer/consumer placement、fusion/residency、tiling/layout/padding、input multicast、buffer/prefetch/outstanding、已有 work-conserving 仲裁和精确静态 wait/release。若 mapping 或现有语义消除问题，应归入静态/compiler 合同，不把这次有限证书包装成 ready scheduler 的价值。

`target_contract.json` 已把当前 checkout、路线能力、数值 admission、实际容量/端口/带宽和观测保持为 unknown，并明确 E2 的范围与多种合法实现形式。下一步只读当前权威 TARS 入口，确定是否真的需要通过共享外存/DMA staging 这些 partial，才能选择具名可测残差。Phoenix copy host elapsed 没有填补该问题的缺口。

**Accept** 来源约束的逻辑账本与单 payload 安全证书；**Refine** native mapping、路线、completion binding 与 strong-static 合同；**Reject** 从本轮直接推出目标 bug、新调度机制或真实收益。设备运行、确认用 paired blocks、收费恢复测量均为 0；既定 5% / 配对 CI / 双 session 性能门没有被本轮结构验收替代。

## 5. 最终报告表述核对

最后通读 `experiment_report.md` 和补充了 `tiled_execution_status` 的 `target_contract.json`：数值、bytes、布局范围、witness 和证据等级与所审结果一致，没有把有限结构反例表述成目标故障、真实残差或收益。接受对象明确为研究合同；当前最优 mapping 与真实服务变化仍未决。未发现阻断发布的过度推论。

绑定本次实际读过的两个最终文档版本，以及完成默认只读修正后的 checker/认证回执；不认证随后维护的根进度或 lineage：

| 文件 | SHA-256 |
| --- | --- |
| `r8/experiment_report.md` | `1746343a4f7f02a426e3ec9ac34103b488a0e7b95eda1ec2bd2e0abd234a26b7` |
| `r8/target_contract.json` | `384b554f5e129b90d42290d92cd54af5bf7e1831dc4ecbdfd4c61143a64e768f` |
| `r8/redteam_check.py` | `efc809cc30d1453841126751fefe99b27b5a98598b21a66dffcb492f1d6b86bb` |
| `r8/redteam_results.json` | `312b1202f37749efc3465fbd33d7d407fb7f58483fa6560e41b5d192010d321f` |
