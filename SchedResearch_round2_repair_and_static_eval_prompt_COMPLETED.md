# 下一轮实施提示词：修复计划准入，接通开源静态评估

请在 SchedResearch 本地工作区实际完成下面这轮有限范围的基础设施更新，不只返回计划。目标是修复当前计划层的正确性缺口，并建立第一条可复现的开源静态评估路径。本轮不是新调度算法研究，也不授权自建通用计时模拟器。

## 1. 当前决策与必读材料

长期研究方向不变：Qwen / FLUX.2 场景下的多核静态数据流规划，以及编译器约束下的动态执行。现有 dataflow 编译器与九段 IR 的工程实现暂不改动；不接描述符。

上一轮交接给出的“自建 1–2 kLOC 执行器，或者提供 Linux 并缩窄问题以适配 ONNXim”不是本轮决策。当前选择是：

**先修复计划与检查器；优先恢复 STREAM 原生 generic 静态评估。运行时资源执行作为独立准入阶段保留，不把它改称已经完成。**

请完整阅读本提示词和 `infra_review_4db062ed.md`（若根目录没有，按本地实际存放路径定位），随后检查：

- `research/infra_open_source/handoff_to_chatgpt.md`、`handoff.json`；
- `src/schedinfra/plan/{schema,checker,generators}.py`；
- `src/schedinfra/{runner,cli}.py`、`src/schedinfra/backend/onnxim.py`；
- `tests/test_plan.py`、硬件配置和已有运行回执；
- 根据接入需要读取 R12 的固定 STREAM 依赖/入口与 R13 数值合同，不重跑全部历史实验。

本次审查固定在远端 `4db062ed255951c843d1c63e592ad62e1c2fdfcf`。先读取真实 HEAD、分支和 git status；本地有更新则增量工作，不 reset，不覆盖用户修改。交接中 `2c3cda1b` 和“未提交”是旧运行状态，不应当作现在工作区的事实。保存原证据，另加新归档身份。

所有修改默认限制在 `research/infra_open_source/`，可增加一个指向新结果的状态入口。不要改写旧 runs、R1–R13 冻结内容或用户的两份背景文档；不自动 commit、push、PR 或合并。

## 2. P0：使检查器与执行入口真正形成准入门

随附 `plan_checker_counterexamples.py` 和 `checker_counterexample_results.json` 是已验证的定向反例线索，不替代你的复跑。前者默认是诊断脚本，不因某项被接受就返回非零；请将必要反例转成具有正确断言的回归测试。

### 2.1 偏序与复用安全

修复 `any(reader in predecessors)`：覆盖某物理 slot 前必须有所有旧读者的完成/最后读取证据，或者证明某个事件传递支配全部读者。第一版可用保守 op-completion，无需立即引入全部 R13 分作用域事件。

不能只把 any 改成 all。即使删去 `reuse_of`，也必须从实际 level/core/slot/address 范围推导别名和覆盖关系。定义清楚 slot 的容量、偏移和重叠规则；不得由可选注解决定是否检查安全。

明确区分“仅指定序列安全”和“任意满足偏序的执行都安全”。依赖图外的 `static_order` 不能偷偷成为实际顺序限制；后端若必须保留它，必须显式导出并审计这些约束。

至少加入 P 写 A、R1/R2 读 A、Q 覆盖 slot 的反例：Q 只依赖 R1 时必须拒绝；Q 已正确等待全部读者时接受；删除 reuse_of 后仍能识别同物理 slot 的风险。

### 2.2 结构与值来源

检查内部 chunk 的声明 producer 与实际 writes 双向一致且唯一；检查每个 read 的来源、consumer 列表、op.core 与 placement.core 范围、合法存储层级、正数大小、非负偏移以及初始驻留占用。检查 static_order 是真正的拓扑序，不只是 op 集合的排列。

存在未知 ID、重复 ID 或结构错误时，返回结构化拒绝并停止依赖这些字段的后续分析，避免 KeyError/递归异常掩盖原错误。

容量结果只能覆盖明确建模的部分。单序列 live bytes 不能标成任意交错下的硬件峰值；kernel workspace、权重 staging、接收副本没有建模时必须显示缺项。不要为获得通用证明而无限扩展本轮算法。

### 2.3 Fail-closed 执行入口

`runner.run_plans()` 当前没有在 check.ok 为 false 时阻断 backend.execute。必须修复，并使用 spy backend 验证：非法计划的调用次数为零，拒绝原因与 CLI/manifest 总状态一致。

不要把 source-audit 或固定 blocker 字符串包装成已实现的 adapter。`backend/onnxim.py` 目前 execute 无条件拒绝，保留其历史能力审计，同时明确标为“未实现执行适配”。环境探测与历史诊断分开，不能换到可用环境后仍永远返回旧机器的固定错误。

新增运行使用唯一目录并拒绝覆盖。硬件完整配置、数值合同、后端 commit/patch、策略和输入要有单独内容身份；plan_id 可以保持计划身份，不用强迫它兼任整次实验身份。

## 3. P0/P1：修复计划表达，但不强迫开源工具接受自定义 IR

当前 v1 是逻辑候选，不是已完成的物理执行计划。请在 schema/结果中明确分层：逻辑语义校验、后端可表达性、物理 lowering 准入是三件事。

重点处理：

1. `resident_pipelined` 将 A16 放在各核 SPAD，而 down 读取全部分片。远端读取必须有明确的 movement/remote-access 合同；尚无合同则 physical_lowering_status=NOT_READY，不允许默认为免费读取。可以先用明确的同核生产消费 fixture 验证局部驻留，再由原生后端规划完整模块的合法数据移动。
2. 两个生成器当前默认 core assignment 相同。需要测试核映射控制时，另外构造一个合法核置换用例，不把 placement/依赖差异描述成核映射差异。
3. naive 的 mul/cast 在遍历过程中读取逐渐增长的 stage ID 列表，实际是部分前缀依赖。若声称每层全屏障，应先构造完整 stage ID 再建依赖；否则改名并报告实际偏序。保留旧结果的历史身份。
4. `resident_bytes_by_level` 是所有逻辑值大小的累加，应重命名/解释为 resident_value_bytes_sum，不称峰值、物理流量或节省的 DRAM 字节。
5. 为计划数值回放补最小 shape、slice、layout、操作及数值许可信息。不要重新建设完整编译器层级。

新增一个小尺寸、真正消费计划和 chunk 访问的小型功能回放测试，与独立代数 oracle 对照。它只用于数值、读写与覆盖验证，不提供虚构的周期或带宽。故意变更分片来源、写入范围、cast 或复用依赖时，应能检测错误或报告不具备所需保证。现有完整 CPU reference 不读取 Plan，不能替代这一检查。

## 4. P1：接通一条真实开源静态评估路径

### 4.1 环境与版本

优先检查 R12 已有 STREAM checkout、venv、Python 和 solver 是否仍可用；记录真实路径、import 来源和版本。不要因为新的 pip 失败就推断旧环境全部不可用，也不要用旧报告代替当前试运行。

选择一个具名、可复现的 STREAM commit；优先能复用的已固定版本，不默认追最新。基座安装与 AMD AIE 全工具链分开，generic 流程不要求先构建全套 MLIR/AIE 后端。

只使用允许的网络源、已有缓存或带 hash 清单的离线包。遇到证书、HTML 拦截、下载截断，做有界诊断并保存证据；不关闭安全策略、TLS 校验或 hash 校验，不尝试规避主机政策。没有可用环境时应诚实交付部分结果，不写替代模拟器掩盖阻断。

### 4.2 原生运行优先

先用上游原生硬件、原生 fixture 和原生入口复现。记录实际命令、exit code、选中结构、分析指标与运行耗时。禁止拿 README 预期值当本机结果。

再将有来源的 Qwen MLP 接入原生格式。优先完整 H=2560/I=9216 的 M=32；M=1/128、attention、FLUX2 或整模型不作为本轮前置。保留 SiLU、逐点乘法和必要 cast；支持缺失时明示 PARTIAL，不用 identity/no-op 代替。原生 SwiGLU 示例成功不等于完整 Qwen 合同已承载。

数值合同不必绑定原 R13 CPU 归约树为所有硬件的唯一语义。若需不同合法 kernel、padding 或归约方式，应事前独立声明并验证，不能把它仍称为原冻结合同的逐位实现，也不能事后为改善结果改变许可。

**不要先要求 STREAM 必须直接读取 Plan v1。** 优先使用它已有的 workload/mapping/hardware 输入，保留作者实现与真实 selected 结果，再增加最小的标准化导出用于审计。输入约束、候选、selected 结果和公共投影的身份必须分开。

### 4.3 两种静态选择与指标

在同一具名硬件和数值能力下，给出至少两种不同的合法静态配置或 mapping；验证它们确实改变 selected 结构，报告效果，无需出现加速。

输出包括作者模型原生指标、可支持的流量/容量账本、分析费用、计划结构与来源。必要时区分 solver 目标、steady-state 周期和完整模块 latency，不自行把不同指标统一命名为 makespan。

标注 `evaluation_kind=analytical_static`。这条路径不是 B1–B3 的动态执行回放，不能签 RUNTIME_READY，不能用它分析未建模的 credit、bank 或运行时重排序收益。

## 5. 备选与明确停止条件

ONNXim 的 generic 跨算子驻留/peer 路由不足，是当前选型依据，不推导“所有融合与持久性都不可能”。本轮暂停其全栈改造，不为了迁就它缩窄长期研究问题，也不因有可用 Linux 就自动重新开工。

若 STREAM 确有依赖或关键输入能力阻断，可做一次限定的 `ecolab-nus/loom-mlar` evaluator 替代核查：先查看固定版本的 installation、Schedule/evaluate 接口和许可状态。其 Rust 评估组件不必先构建全套 MLIR 验证器，但依赖、模型语义和实际运行仍须验证。只尝试最小原生评估样例，不并行建设 Loom 全栈。其符号评估也不自动通过动态执行门。

本轮不实现 SimGrid NPU 模型或新事件内核。SimGrid 等成熟活动/DAG 引擎作为后续动态执行选型线索保留；正式接入前仍需要实际 NPU 计算、存储寿命、有限资源与完成语义合同，不能拿通用 DAG 时间冒充目标 NPU 周期。

所有可用开源后端均被真实环境/输入问题阻断时，交付修复与明确接缝。不要再次要求“自建或牺牲研究方向”二选一；给出最小外部依赖与可验证的恢复步骤。

## 6. 验收状态与反馈

旧 B1/B2/B3 的历史 NOT_RUN 原样保留。新结果分别报告：

- **PLAN_SAFE**：具名能力范围内反例与原回归通过；真正与计划绑定的功能回放通过；非法计划无法进入后端。若只保证一个固定次序，应在状态字段写明，不冒领所有偏序执行安全。
- **STATIC_EVAL_READY**：真实开源原生路径已运行；完整 Qwen 模块在明确合同内承载；两种静态选择的 selected 结构与分析结果可复现。缺任一项则逐项 PARTIAL。
- **RUNTIME_READY**：仅在 B1–B3 的资源反馈、生命周期和策略替换获得真实执行证据后成立。本轮可以保持 NOT_RUN；静态分析不能代替它。

结束时生成新的 `handoff_to_chatgpt.md` 与 `handoff.json`，不要覆盖旧 runs 中的证据。至少包含：实际起始/归档 commit 和工作区差异、逐文件更新、原测试及新增测试数量、反例修复前后结果、计划/硬件/数值/后端身份、真实执行命令与日志、逻辑/物理/分析/动态各层状态、完整模块覆盖与缺失算子、关键数字的确切含义、剩余三个最重要的缺口。

最终回复给出 READY/PARTIAL/BLOCKED 的分层结论和文件路径。下一轮只提出一个建议目标，并解释其为什么由本轮证据产生。本轮成功不要求任何加速、新颖性主张、RTL、板卡或生产编译器修改。
