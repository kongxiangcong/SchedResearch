# 本轮交接：开源多核 NPU 调度实验基础设施

**判决：PARTIAL。** 计划层、工作量层和 CPU 数值层是能跑、能改、能复现的真实代码并已通过；
**时序后端这一层没有跑起来**。现在能开展的实验是"计划生成与合法性研究"和"数值/工作量来源研究"，
**还不能**开展任何产生 cycles、带宽或加速比的调度实验。

---

## 1. 最重要的完成项与限制

完成的是一个后端无关的研究基础设施：有来源的 Qwen3.5-4B MLP 规格、内容寻址的候选计划 IR、
能拒绝非法计划的检查器、复用 R13 冻结实现的独立 CPU 数值参考，以及"生成计划 → 检查 → 执行 → 汇总"
的入口。全部实际运行过。

限制是一句话：**没有一个时序后端被执行过，本轮结果里没有任何 cycles 数字。**

## 2. 底座选择

选定审计对象 **ONNXim**（PSAL-POSTECH，IEEE CAL 2024），固定 commit
`a1e86296e080fa1c82f8ad3f1b6de1079c192afc`（2026-01-08），硬件配置取自其自带的
`systolic_ws_128x128_c4_simple_noc_tpuv4.json`（4 核 systolic_ws 128×128、每核 32 MiB
scratchpad、simple NoC、ramulator2 DRAM）。

**它没有被构建，也没有运行**，原因有两条且互相独立：

- **环境阻断**：主机无 cmake（全盘搜索无 cmake.exe）、无 conan；PyPI 被网络过滤替换成 HTML
  拦截页（`pip install numpy` 报 hash 不匹配，直接 curl 取回的是 `<!DOCTYPE html>`）；
  git 大文件克隆被代理截断（`curl 56` / `gzip: unexpected end of file`，8.7 MB 处停住）。
  WSL2 被主机安全策略列入黑名单，全程只能 Windows 原生。
- **能力阻断（更重要）**：源码审计显示三项与研究需求直接冲突——跨算子驻留不支持
  （`Core.cc` 每个 tile 刷新 scratchpad，输出一律写回 DRAM）、核间通信不支持
  （`Simulator.cc` 只路由 core↔DRAM）、simple 调度器有整层完成屏障（`Scheduler.cc:207-209`）。
  这属于"需要重写执行、存储所有权与通信路由"，按本轮规则应记为**选型风险**，不能藏进"未来可扩展"。

考察但未选择（**均非运行失败**）：`KULeuven-MICAS/stream`（分析型代价模型，无法提供 B1–B3
所需的执行反馈，本轮刻意不放在关键路径上；R12/R13 已跑过）、`ecolab-nus/loom-dataflow`
（输入是 tile 程序/ETG/约束模型，是规划器输入而非可执行计划）。

## 3. 实际完成

**原生复现：未通过（BLOCKED）。** 没有构建 ONNXim，没有运行其自带示例或 GoogleTest。

**B1 外部计划控制：NOT_RUN。** 计划层有真实证据：同一工作量、同一硬件下两份合法计划
`naive_layered`（id `dbe43cc256081c5a`）与 `resident_pipelined`（id `738420509c6733af`），
M=32、4 核，各 100 个 op、147 个 chunk、MAC 总数同为 2,264,924,160 = 3×32×2560×9216；
区别是**依赖边 1170 vs 292**（去掉整层屏障后约 4 倍）与**片上驻留 0 B vs 5,308,416 B**
（峰值每核 294,912–327,680 B）。但没有后端确认它会保留该映射。

**B2 跨算子流水与存储生命周期：NOT_RUN。** 检查器能拒绝：缺失依赖、容量溢出、提前复用、
复用缺顺序边、依赖成环、消费者声明不一致（6 个负例测试通过）；但没有时序后端观测真实驻留与流量。

**B3 策略替换：NOT_RUN。** ONNXim 的 `Scheduler` 是虚基类 + 工厂选择（源码级，未执行、未计时）。

**完整维度真实模块：PARTIAL（真实执行）。** CPU 上跑了完整 H=2560 / I=9216 的 MLP：
M=1 相对 FP64 的 L2 = 0.0016238196、M=32 = 0.0016506451，与 R13 冻结值 0.162382% / 0.165065%
一致；两套独立归约实现逐位相同。这只是**代数与工作量来源**的正确性，不是时序。

**可重复入口：PASS。** `python -m schedinfra.cli {inventory,plan-check,cpu-reference,backend-audit}`
均能运行并写入带时间戳的证据目录。计划检查主机耗时 0.773 s，CPU 参考 M=1/32 共 16.7 s。

## 4. 改动范围

新增 `research/infra_open_source/`（未提交、未 push）。核心文件：`src/schedinfra/workload/qwen_mlp.py`、
`plan/schema.py`、`plan/checker.py`、`plan/generators.py`、`analysis/cpu_reference.py`、
`backend/onnxim.py`、`runner.py`、`cli.py`，以及 `configs/`、`tests/`、`docs/`。
**没有修改任何上游代码，没有打补丁**（没构建就无从修改）。R1–R13 冻结代码、合同、结果未被改动。
仓库基础 HEAD `2c3cda1b`（分支 `codex/r12-wormhole-qualification`），工作区除新增目录外无改动。

## 5. 能力与缺口

原生可用：分块/循环序、buffer 容量、依赖与资源顺序、策略接口、反压（仅在 booksim2/ramulator2
后端）、self-timed 推进、SiLU（仅 fused `swish`）。
需extension：逐 tile 核映射、显式 slot 复用、独立逐元素乘法。
**锁死**：跨算子驻留、核间通信、整层屏障、精度 cast（Cast 是 Dummy 空操作，会让目标模块的 cast 免费）。
未验证：以上所有"原生"判断都是 `source_only`，**没有任何一项经过执行验证**。

三个最重要的阻断：
1. **无时序后端**（环境 + 能力双重）——已尝试 pip/镜像/trusted-host、curl、断点续传、
   blobless 稀疏克隆（成功拿到源码，但构建仍缺 cmake/conan/子模块）。
2. **ONNXim 不能表达研究所需语义**——不是环境问题是设计问题，不能靠适配层绕过。
3. **自建执行核心需要授权**——本轮规则禁止未经新范围授权扩成长期模拟器项目。

## 6. 复现方法

```bash
cd research/infra_open_source
. ./scripts/env.ps1            # PowerShell 7；Git Bash 用 source scripts/env.sh
python -m pytest tests -q      # 16 passed
python -m schedinfra.cli plan-check --m 32
python -m schedinfra.cli cpu-reference --m 1 32
python -m schedinfra.cli backend-audit
```

主机：Windows 10/11、Python 3.14.0、numpy 2.3.5（**注意：R13 合同钉的是 2.5.3，本机装不上，
已作为显式偏差记录**）。代表用例：计划检查 0.773 s；CPU 参考 M=1 约 10.9 s、M=32 约 16.7 s；
峰值内存未实测（**未测**）。M=128 未跑（**未测**）。cycles、带宽、加速比全部**未测**。

## 7. 下一轮建议（只推荐一个目标）

**先解决"能执行"这一个问题**：请授权二选一——

- **(a)** 建一个**有界的最小 tile 级执行核心**（约 1–2 kLOC，直接复用本轮的计划 IR 与检查器，
  只做 B1–B3 所需的最小语义：多核、容量受限的分布式 scratchpad、显式 slot 复用、
  DRAM 中转并显式计费、self-timed 完成事件、可替换发行策略），使 B1–B3 能真正执行；或
- **(b)** 提供带 cmake ≥ 3.22 与 conan 1.57 的 Linux / WSL2 主机（或解除 `wsl.exe` 策略封锁），
  重新准入 ONNXim，并把研究范围收窄到**不要求跨算子驻留**的问题。

起始文件：`src/schedinfra/plan/schema.py`、`plan/checker.py`、`plan/generators.py`、
`backend/onnxim.py`、`runner.py`、`capabilities.json`。
验收条件见 `handoff.json` 的 `next_round.acceptance`（B1/B2/B3 各一条 + 完整 MLP 两份计划对比
+ 固定 seed 可复现）。
真正需要外部决定的：(a)/(b) 选哪个；若选 (b) 则能否提供主机；以及研究问题是否可以在
不含跨算子驻留的前提下重新表述。
本轮证据**不支持**开展：任何加速比或 gate 阈值实验、跨后端性能对比、把 292 vs 1170 边数说成性能收益。
