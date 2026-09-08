# R12 本次阅读与执行覆盖

2026-09-08。本轮输入包六个文件均完整阅读，原样保留；`sha256.json` 登记的五项原字节 SHA-256 全部匹配。此处的“全文”指本次读取内容，不代表其引用的所有外部论文也在本次重读。

| 输入 | 本次范围 | 本次作用/执行 |
|---|---|---|
| `SchedResearch_reassessment_evidence_20260907/proposal_contract.md` | 全文，研究问题至 Continue/Close | H0/H1/H2、四 tile 小图、完整 MLP、P0/R0 和 3%门；另在 preregistration.json 明确本轮离线边界 |
| 同目录 `evidence_ledger.md` | 全文，包括所有项目/外部登记、缺口 | 继承证据分级与历史边界；不继承“未公开”的旧结论而跳过官方源码 |
| 同目录 `evidence_manifest.json` | 全部字段/条目，分段读取 | 与 ledger 交叉核对版本、27项项目覆盖、外部来源、检索与缺口 |
| 同目录 `bound_witness.py` | 全文 | 审核 request-only、NoC0 non-wrapping、R9/R11算术；本次重新调用两组路径函数 |
| 同目录 `bound_witness_result.json` | 全文 | 两组重新计算的结构化结果精确一致；66/33仅链路服务下界 |
| 同目录 `sha256.json` | 全文并执行逐项核对 | 五项原字节 hash 完全匹配；未改写输入包 |
| “科研方向重审” `6a9e7c1f-4544-83ec-91ca-2b66c6b1445d` | 通过 read_thread 取得原用户任务和助手返回的正文；助手长答被工具截为前20,000字符，无更早页 | 不声称恢复了助手长答尾部或原附件；完整本地证据包足以确定执行合同与门槛 |

历史记录与工作量源的完整阅读、固定 Git blob/工作树/归档行尾 hash 区别，见 [workload_intake.md](workload_intake.md) 末尾阅读表。两份历史台账本次由独立工作量审计全文读取；R8合同/报告及 Qwen 冻结源另有直接核查。其他 R1–R11 结论没有在本次无选择重跑。

固定 Wormhole ISA 的全文/节选覆盖及原文行号见 [hardware_source_audit.md](hardware_source_audit.md)；固定 STREAM 的模块覆盖、已有 AIE wait 行为、单 offchip 与路径模型边界见 [baseline_source_audit.md](baseline_source_audit.md)。本次只使用这些研究材料、关联实验源码和官方依赖源码，没有读取其他方案初稿、演示或解析副本。

证据级别严格分开：

- **报告记载**：历史轮次性能、已发布文献结果和厂商文档测量表。
- **本次检查源码/结果**：固定来源、controller/channel 别名、计数器语义、STREAM 路径与目标函数、Qwen完整形状。
- **本次执行**：来源/字节复算、条件性事件偏序与数值反例、28,800路由对、96候选流量账本、真实 SCIP/TETRA 官方小例与具名full-payload费用干预；保存的最终operand maps逐元素halo枚举。tt-npe完成Linux编译、45项C++与10项Python测试及官方示例API，官方CLI失败单列；各回执另存。
- **未执行/未准入**：Wormhole板卡测量、原生完整MLP数值和elapsed、强P0与P1的设备比较、有界runtime、PPA。离线 PASS 不提升为 native G0 或 H1/H2。

新发现只在 R12 追加：部分 router buffer 参数已公开；三端点共享域内还需区分两个物理channel；原生源buffer复用必须在下一DMA发起前建立约束，不能只约束其最终完成；AIE已有生命周期相关等待优化。冻结证据包保留原文。

研究过程中的反证也保留：真实2conv的allocation footprint曾被错误推断为full all-gather需求；最终空间分片与affine访问枚举推翻了这一解释。参数化完整复制反例、原始费用干预及后续收窄结论分别保存在R12，不能合并为已证明的基线缺陷。
