# Research harness基础设施选型

日期：2026-09-05。下列是本轮打开的项目README/官方文档级调查，未声称全部安装、构建或跑通。运行中的R3采用小型Python heapq事件核；后续仅在某个未建模因素改变结论时接入详细后端。

## 1. 开源候选比较

| 项目/一手来源 | 适合复用的能力 | 本问题缺口/接入代价 | 决定 |
|---|---|---|---|
| [gem5](https://github.com/gem5/gem5) | CPU OoO、系统、cache/memory、事件式微结构 | 需要自建NPU contract/task engine，系统级依赖多，首轮迭代偏重 | 后续若核内cache/OoO成主因再用 |
| [Gemmini](https://github.com/ucb-bar/gemmini) | 开源加速器RTL/ISA、scratchpad、跨controller依赖和ROB | 与目标task合同不同；构建需Chipyard生态 | 微结构与公平baseline参考；不是当前运行底座 |
| [NVDLA](https://github.com/nvdla/hw) / [官方文档](https://nvdla.org/hw/v1/ias/unit_description.html) | 实际accelerator模块、DMA/engine配置 | 模型/算子与LLM/DiT、可选scheduler自由度不匹配 | 对照实现，勿为适配它改变问题 |
| [SCALE-Sim v3](https://github.com/scalesim-project/SCALE-Sim) | systolic compute、memory trace、layout、多核、Ramulator/Accelergy集成 | 主要GEMM/conv模型；异构task合同和wakeup需自建 | 优先候选：以后校准MXU与memory服务 |
| [Timeloop](https://github.com/Accelergy-Project/timeloop) | mapping/search与分析成本 | 不是现成的completion/wakeup微结构模拟器 | 静态cost/mapping候选，不替代事件核 |
| [Stream](https://github.com/KULeuven-MICAS/stream) | 异构多核layer-fused mapping；ZigZag cost；TETRA MILP tensor placement/transfer | 未直接提供本研究有界依赖表/事件网络机制 | 最优先强静态外部对手/输入来源 |
| [ASTRA-sim](https://github.com/astra-sim/astra-sim) | distributed AI workload、collective、compute/memory/network APIs、Chakra输入 | 主焦点分布系统；core级task wakeup仍需自定义 | 多chip通信若成主要收益源再接 |
| [Chakra](https://github.com/mlcommons/chakra) | 执行图schema及trace工具 | trace不自动包含alias/可见性契约、也不代表新的mapping合法性 | 后续graph exchange/replay格式 |
| [BookSim2](https://github.com/booksim/booksim2) | cycle-accurate NoC、router/VC/流控 | 高频跨语言调用与时间推进需明确；不含NPU任务语义 | 当聚合NoC反压改变方向时接 |
| [Ramulator2](https://github.com/CMU-SAFARI/ramulator2/blob/main/README.md) | DRAM controller与bank/refresh时序；当前README为2.1，含LPDDR等模型与library接口 | 要生成真实地址transaction，服务时间随顺序变化 | memory主导时优先；端侧优先LPDDR配置，不默认HBM |
| [Accel-Sim](https://github.com/accel-sim/accel-sim-framework) | GPU trace与warp/SM微结构、校准流程 | 引入GPU ISA假设；不自然等价NPU descriptor | GPU机制参考；首轮不采用 |
| [SimGrid](https://github.com/simgrid/simgrid) | 分布应用/任务、通信仿真 | 提供系统抽象而非NPU SRAM bank/有限scoreboard | 大规模task图后端候选 |
| [SimPy](https://simpy.readthedocs.io/en/latest/) | Python离散事件、process与shared resources | 需精确定义同刻completion、原子多资源占用/arbiter | 可用，但这次heapq更容易审计全部事件语义 |
| [MLIR async](https://mlir.llvm.org/docs/Dialects/AsyncDialect/) | token/value/await可做contract前端 | 全编译基础设施不是首轮所需；不自动做地址安全 | 后续llmSched导出/适配时再接 |

README是活动分支，功能可能漂移；以上是读取当日状态。尚未vendoring，所以不虚构commit SHA或说“已复用某框架”。真正接入时固定revision、许可证、build命令、微测试和校准trace。

## 2. 为什么本轮用小事件核

先要回答的是：在相同DAG、mapping、静态地址、资源下，仅真实完成信息能否改变更好的合法顺序。R2已经有heapq toy，保留其可解释性并重新建立同时事件处理、有限admission、typed边和强静态实验，比先把新scheduler塞进完整GPU或SoC更直接。

复用成熟框架不是目标本身。R3内核不假装细粒度DRAM/NoC仿真；它暴露 memory、noc、workload、compiler、scheduler、hardware、metrics模块作为独立替换边界。其强项是因果隔离，弱项是物理校准和真实访问序列。

## 3. 升级接口（设计，未实现适配器）

```text
issue(request_id, resource, address, bytes, earliest_time)
    -> accepted / backpressure
tick(next_event_time)
    -> event(request_id, kind, time, scope, generation)

kind = accepted | source_reusable | destination_visible | credit_return | failed
```

DRAM/NoC后端必须闭环返回完成/credit，不能只离线注入一份旧策略duration。source_reusable与destination_visible可以是不同时刻；前者允许复用发送buffer，后者才能唤醒远端consumer，accepted只表示请求接收。全局事件核推进到最近的后端事件，保证同时completion先收齐再仲裁。后端精度升级时保留相同contract和scheduler，先用零拥塞/单请求解析例校验，再跑多请求。

Compiler升级路径：手写motif → 实际LLM/DiT block导出DAG与tensor bytes → Stream/自有静态搜索产生placement → R1语义兼容的contract → 相同仿真与trace检验。图前端可以更换，硬件不因此重新分析完整模型。

## 4. 接入触发门

- 若收益主要出现在memory服务方差：先Ramulator/真实请求trace；不要先加更复杂task scheduler。
- 若收益随跨域edge/注入拥塞变化：先BookSim/ASTRA-sim；聚合link模型无法区分路由/VC/HOL。
- 若收益只剩核内load-use：转gem5或具体RTL模型，task-level DES不能验证instruction OoO。
- 若动态仅胜弱静态heuristic：先接Stream/更强mapping-memory planner，不要升级硬件复杂度。
- 若全套收费实验无稳定收益：保留harness和负结果，收窄或拒绝架构方向。
