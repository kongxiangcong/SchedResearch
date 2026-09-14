# 选型、实现与证据报告

证据分级贯穿全文：**【历史】** 前轮文档记载 · **【源码】** 本次读过固定版本源码 ·
**【执行】** 本次实际运行 · **【推断】** 尚未验证的判断。不把前三类混写成第四类。

## 1. 取证范围

| 材料 | 范围 | 级别 |
|---|---|---|
| `SchedResearch_R13_research_review.md`、`SchedResearch_subagent_tasks.md` | 全文 | 【历史】 |
| `research/research_progress.md` | 全文 | 【历史】 |
| `research/r13/experiment_report.md`、`p0_qualification_next.md`、`numerical_contract.json` | 全文 | 【历史】 |
| `research/analysis/r1_r10_research_retrospective.md` | **未读**（本轮未打开，不假称已读） | — |
| `research/r13/numerical_reference.py` | 全文阅读并**直接复用其函数** | 【源码】+【执行】 |
| ONNXim `a1e86296` 的 `src/`、`configs/`、`tests/`、`CMakeLists.txt`、`.gitmodules`、`conanfile.txt` | 能力审计 | 【源码】 |
| ONNXim 构建 / 示例 / 测试 | **未执行** | — |

## 2. 选型决定

按提示词要求，优先验证 ONNXim，**但它不是预定赢家**。结论是：ONNXim 作为审计对象成立，
作为本项目的执行底座**不成立**，理由分两层（详见 `docs/02_environment_blockers.md` 与
`capabilities.json`）：

**【源码】** 关键能力缺失，且不是薄适配能解决的：

- `Core.cc:36-74` —— 每个 tile 发行时 `spad_id=(spad_id+1)%2` 后立即 `flush()`，
  累加缓冲仅在同一个 fused op 内保留（`Core.cc:54-58`）；输出由 `MOVOUT` 写回 DRAM
  （`Core.cc:364-403`）。**跨算子驻留不存在。**
- `Simulator.cc:269-275` —— 每个请求都路由到 DRAM channel，每个响应都回到 core。
  **核间数据交换不存在。**
- `Scheduler.cc:207-209` —— 只有在所有核队列都空且 `count_active_layers()==0` 时才发行下一层。
  **存在整层完成屏障。**
- `OperationFactory.cc:48-49` —— Cast 映射为 `Dummy` 空操作，会让本模块的 FP32→BF16 cast 免费。
- 正面部分：`Scheduler.h:17-23` + `Scheduler.cc:4-20` 的工厂使策略可替换；
  `Simulator.cc:107-210` 按实际完成推进，无全局 barrier；`Sram.cc:6-10` 容量显式且溢出即失败。

这三点合起来意味着：研究所需的"分布式驻留 + 跨核通信"只能靠大幅改写实现。按提示词第 3 节，
这是**选型风险**，不是"未来可扩展"。

**【执行】** 环境阻断（与上面无关的另一层）：无 cmake、无 conan、PyPI 被替换为 HTML 拦截页、
大文件下载被截断、WSL2 被安全策略禁用。已尝试：pip `--trusted-host` / `pip cache purge` /
`--no-cache-dir`、直连 curl、镜像、`-C -` 断点续传 25 次、`git clone --filter=blob:none`
+ `sparse-checkout`（**成功取得源码**）。源码审计因此得以执行，构建仍不可行。

**【历史】** STREAM/TETRA 在 R12/R13 已实际运行过（`research/r12/baseline_source_audit.md`），
本轮未重新拉取——它是分析型代价模型，无法提供 B1–B3 所需的执行反馈，故刻意不放在关键路径上。
TileLoom 未尝试（其输入是规划器输入）。**两者记为"考察未选择"，不记为运行失败。**

## 3. 原生复现

**未通过。** 没有构建 ONNXim，没有运行 `build/bin/Simulator --config ... --model ...`，
没有运行 `tests/` 下的 GoogleTest（它依赖 ExternalProject 拉取 GoogleTest 1.8.1 与全部子模块）。
无官方测试通过范围可报告。

## 4. 三个能力用例

三者**均未在执行层面通过**，因为没有可用的时序后端。计划层面的真实证据如下【执行】：

- **B1** —— 两份合法计划结构不同：`dbe43cc256081c5a`（naive）与 `738420509c6733af`（resident），
  M=32、4 核，各 100 op / 147 chunk / 2,264,924,160 MAC；依赖边 1170 vs 292；
  片上驻留 0 B vs 5,308,416 B。**没有后端确认映射被保留** → NOT_RUN。
- **B2** —— 检查器拒绝 6 类非法计划（缺失依赖、容量溢出、提前复用、复用缺顺序边、
  依赖成环、消费者声明不一致），16 个测试全过。但真实驻留、流量与"消费者按需启动"
  未经任何时序后端观测 → NOT_RUN。
- **B3** —— 未建策略层（没有可插入的执行器）。ONNXim 的策略接口为【源码】级判断 → NOT_RUN。

**没有使用任何外部 Python 假执行器输出"通过"。**

## 5. 真实模块结果

有来源的 Qwen3.5-4B MLP（H=2560、I=9216，来源 `research/r13/numerical_contract.json`）：
完整 gate/up/down、SiLU、逐点乘法、down 前显式 BF16 cast、FP32 输出、M 补齐到 32。
**没有把 SiLU 换成 ReLU，没有跳过逐点算子，没有忽略 cast 或 padding。**

【执行】CPU 数值参考（复用 R13 冻结实现，两套独立归约逐位比对）：

| M | padded M | 相对 FP64 的 L2 | 与 R13 冻结值 | 主机耗时 |
|---|---|---|---|---|
| 1 | 32 | 0.0016238196248702127 | 0.162382% ✓ | 10.9 s |
| 32 | 32 | 0.0016506450773327993 | 0.165065% ✓ | 16.7 s |

工作量账本：三份 BF16 权重 141,557,760 B（135 MiB）；M=32 的 padded MAC = 2,264,924,160；
显式 cast 为 32×9216 个元素，逻辑读 4 B、写 2 B，即使被融合也不能免于计费。

【历史】这些数字是 CPU 数值与工作量资格，**不等于**后端数值正确，也不等于训练模型精度验证。
**没有任何 cycles 结果**：完整模块没有在时序后端上比较过两份计划。

## 6. 上游 / 本地变更边界

- 上游：**零修改，无补丁**。没构建就无从修改；`vendor/` 不入库。
- 本地：新增 `research/infra_open_source/`。未 commit、未 push、未建 PR。
- R1–R13 冻结代码、合同与结果：未改动。
- 基础 HEAD `2c3cda1b7e3d10f6700977abc5200df75372578b`，分支 `codex/r12-wormhole-qualification`。

## 7. 已知限制

1. **零时序证据**：本轮结果里没有任何 cycles、带宽、加速比。
2. 检查器的容量与复用判断基于计划声明的静态序，是**必要条件检查**；真实交错执行仍可能溢出。
   它不是驻留观测的替代品。
3. numpy 2.3.5 vs 合同钉的 2.5.3（本机装不上），已作为显式偏差记录在运行输出中。
4. M=128 未跑；主机峰值内存未测。
5. ONNXim 的"策略可替换""反压存在"等正面判断全部是【源码】级，未经执行验证。
6. 若将来真的用 ONNXim，必须注意 Cast 是空操作，会让本模块最关键的 cast 免费。
