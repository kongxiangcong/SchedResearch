# R4 prior-art delta: strong static first

核验日期：2026-09-05。这是独立的机制与基线审查；不是专利权利要求检索，也不是外部框架复现实验。R3 的 SPDI、VTA、TaskStream、ASPEN 和 HwSch 审计仍保留；本轮只更新最直接约束 R4 的三个参照。

## 冻结证据

| 来源 | 本轮实际核验 | 对 R4 的约束 |
| --- | --- | --- |
| [LATTICE v3, 2026-08-04](https://arxiv.org/html/2607.17422v3) | §III-B/C 的固定地址、生命周期/溢出事件、reuse 边合同；§IV-D 的关键链附近同 pipeline 相邻交换；§IV-E 独立 memory/timing replay；§V 的单核 command trace 范围。 | “静态 memory plan 是可验证 scheduling contract”已经被明确覆盖。顺序搜索必须固定地址、reuse orientation、traffic 与容量；冻结全部资源顺序只能是起始基线。其结果是建模时延，不能当作真实端侧完成方差的证据。 |
| [PipeThreader, OSDI 2025](https://www.usenix.org/system/files/osdi25-cheng.pdf) | §3.1/3.2 用 tile sTask、异构 sEU 和二维 sProgram 表示 placement/order，barrier 等待完成；§4 搜索 tile 与 pipeline；§5 包含布局约束和双缓冲。§2/3 明确讨论软件 tile pipeline，而非替代 GPU thread/warp dispatch。 | 强静态应获准做异构流水、可行 fusion、tiling 与缓冲配置。把这些优化遗漏留下的 deterministic bubble 归为 completion-order 信息价值会夸大动态机会。不能把本地几次交换命名为“复现 PipeThreader”。 |
| [Stream v2, 2025-10-07](https://arxiv.org/html/2212.10612v2) | §III 细粒度层融合与依赖，§IV COALA 内存/通信建模，§V WACO 约束优化。它跨越 mapping、allocation、scheduling，范围大于同固定 mapping 的 ready dispatch。 | 端侧多核实验不能仅复制若干 engine 而忽略通信与容量。若 R4 固定 mapping，应写成有意隔离 dispatch 的条件实验，不能声称战胜 Stream 的整体优化。 |
| [Stream 源码冻结版本](https://github.com/KULeuven-MICAS/stream/tree/75748cc17e7c43add5a7d0d8f080841eb26531c4) | 当前 README 与 pyproject 已保存，当前实现文档使用 TETRA/MILP allocation；论文使用 WACO/COALA。 | 不能把论文算法名、当前仓库架构与本地实现混写为同一个已复现 baseline。本轮没有安装或执行 Stream。 |

本轮下载的 HTML、固定 revision 的源码说明及 SHA-256 见 [source manifest](evidence/prior_art/manifest.json)。GitHub API 返回 403 rate-limit 后，使用只读 `git ls-remote` 冻结 Stream main 为 `75748cc17e7c43add5a7d0d8f080841eb26531c4`。USENIX PDF 的 Python 下载返回 403，但 web 工具读到会议完整 PDF；本目录已有 R3 PDF/文本保留在 `literature/sources/papers/pipethreader.*`。这些不同获取路径不应伪装成同一次成功下载。

## 能否 claim novelty

**不能把“compiler contract + completion-ready dispatch”本身作为 R4 新颖性。** R3 已有的 TaskStream/ASPEN/HwSch 对照，加上本轮核验的 LATTICE 合同，都使这个主张过宽。LATTICE 是静态 plan-preserving timing，PipeThreader 是显式异构 tile pipeline，Stream 是层融合/多核 placement 与通信分析；这些差别只说明各自研究范围，不能自动构成 R4 的贡献。

R4 可以提出的条件问题是：官方来源的代表性子图，在同一经过顺序优化、融合、固定 mapping/address/reuse 合同之下，固定资源队列留下的等待中，多少由部署时未知的完成顺序导致，多少可由收费的 completion dispatch 缩短最终 makespan。该问题必须由本轮实际结果回答。

先例并不证明任意动态机制都无效。反过来，某个 B 比某个静态 A 快也不证明新机制有效：必须给出静态搜索范围、确定性 gap、holdout 选择、配对环境、可执行替代任务及端到端缩短证据。如果主要优势消失于更强静态、共享 DMA arbitration 或合法 fusion，研究结论应保留负结果。

## 本轮最小反证门

1. 强静态可采用名义预测、独立 training/validation 的固定资源顺序搜索；test 环境不得反向挑静态计划。tiny 图用穷举给出所声明搜索空间的 exact gap。
2. 对照共享任务服务需求、mapping、precision、tile、buffer plan 与容量。固定任务服务样本和固定绝对时间背景带宽日历是两类不同的共同随机环境，不能混成一个“相同时长”公平性要求。
3. 同时报告确定性、外生服务差异、时间相关背景争用；compute 默认确定性。对调度诱发排队保持单独归因。
4. “可恢复等待”必须在资源空闲时确有依赖、地址与 admission 合法替代任务；报告时间并集并通过反事实或配对 trace 解释是否缩短最终关键路径。
5. 每项动态优势付 issue/wakeup/decision/metadata 成本。descriptor window 有限不代表总事件历史有限，零选择时延也不代表可综合。

若上述门通过，下一轮才比较有界生命周期/epoch 与当前 full-history reference；没有正收益时不扩张 OoO，也不从论文覆盖差异推断专利新颖性。
