# SchedResearch 开源多核 NPU 调度实验基础设施

以 Qwen / FLUX.2 场景下的多核 NPU 调度为长期目标。本轮交付的是**科研实验基础设施**：
有来源的模型模块 → 可替换的候选执行计划 → 合法性检查 →（时序后端）→ 可解释结果。

> **当前状态：PARTIAL。** 计划层、工作量层和 CPU 数值层已经真实跑通；
> **时序后端这一层本轮没有跑起来**，原因是环境阻断 + 所选后端能力不匹配，
> 详见 [`docs/02_environment_blockers.md`](docs/02_environment_blockers.md)。
> 本目录**没有**用假执行器输出任何"通过"。

## 目录结构

| 路径 | 内容 |
|---|---|
| `configs/pinned_versions.json` | 所有上游固定版本、主机环境、网络状态 |
| `configs/hardware/` | 有来源的硬件配置（含上游 commit 与归一化说明） |
| `configs/workloads/` | 工作量配置 |
| `src/schedinfra/workload/` | 有来源的 Qwen3.5-4B MLP 规格与工作量账本 |
| `src/schedinfra/plan/` | 计划 IR（`schema.py`）、合法性检查（`checker.py`）、参考计划生成器（`generators.py`） |
| `src/schedinfra/analysis/` | 独立 CPU 数值参考（复用 R13 冻结实现） |
| `src/schedinfra/backend/` | 后端适配层；`onnxim.py` 记录能力审计并**拒绝伪造结果** |
| `src/schedinfra/runner.py` / `cli.py` | "生成计划 → 检查 → 执行 → 汇总"入口 |
| `experiments/` | 各能力用例脚本 |
| `tests/` | 单元测试与负例 |
| `runs/` | 每次运行的证据（命令、清单、指标、计划与检查产物） |
| `vendor/` | 上游源码（**不入库**），ONNXim 固定 commit `a1e86296` |
| `docs/` | 环境与阻断说明 |

分层原则：研究层 / 后端扩展 / 硬件配置 / 实验结果边界清晰；第三方代码与构建产物
隔离存放；巨型依赖、权重、虚拟环境和原始 trace 不进 Git。

## 环境与安装

在 **Windows PowerShell 7**（或 Git Bash）中执行。WSL2 在本机被安全策略禁用，
因此全部为 Windows 原生。

本轮**不需要 pip**：主机 Python 3.14 的用户级 site-packages 已含所需包，
用 `PYTHONPATH` 启用即可（`scripts/env.ps1` / `scripts/env.sh` 已封装）。

```powershell
# PowerShell 7
cd D:\dsh-proj\SchedResarch\research\infra_open_source
. .\scripts\env.ps1
python -m pytest tests -q
```

```bash
# Git Bash
cd /d/dsh-proj/SchedResarch/research/infra_open_source
source scripts/env.sh
python -m pytest tests -q
```

已验证版本：Python 3.14.0、numpy 2.3.5、onnx 1.20.0、pyyaml 6.0.3、pytest 9.0.2。

> 若要在新环境复现：`scripts/setup_env.ps1` 会创建独立 venv 并 `pip install -r requirements.txt`。
> **本机该脚本会失败**（PyPI 被网络过滤替换成 HTML 拦截页），这是已知阻断，不是脚本缺陷。

## 运行命令

```bash
# 1) 工作量账本（M=32）
python -m schedinfra.cli inventory --m 32

# 2) 生成两份计划、做合法性检查、尝试后端执行（M=32）
python -m schedinfra.cli plan-check --m 32

# 3) 独立 CPU 数值参考（完整 H/I）
python -m schedinfra.cli cpu-reference --m 1 32

# 4) 记录 ONNXim 源码能力审计
python -m schedinfra.cli backend-audit
```

### 两种模式

- `native`：固定上游，不打补丁，不启用任何研究扩展。
- `research`：启用具名本地扩展，扩展身份写入运行清单。

两种模式共用同一套公共能力；模式切换不会悄悄给某个方法更好的存储或通信语义。
`plan-check --mode native|research` 可切换。

### 输入 / 输出位置

- 输入：工作量取自冻结的 `research/r13/numerical_contract.json`（H=2560、I=9216）；
  硬件取 `configs/hardware/onnxim_tpuv4_c4.json`。
- 输出：每次运行写入 `runs/<UTC时间戳>_<用途>/`，包含 `manifest.json`、
  `plans/<plan>.json`、`checks/<plan>.json`。运行目录**不会被覆盖**。

## 最小示例

```python
from schedinfra.plan.schema import HardwareProfile
from schedinfra.plan.generators import naive_layered_plan, resident_pipelined_plan
from schedinfra.plan.checker import check_plan
from schedinfra.workload.qwen_mlp import MLPModule

hw = HardwareProfile.from_file("configs/hardware/onnxim_tpuv4_c4.json")
module = MLPModule(32)

for plan in (naive_layered_plan(module, hw), resident_pipelined_plan(module, hw)):
    result = check_plan(plan)
    print(plan.name, plan.plan_id, "ok" if result.ok else result.errors,
          result.stats.get("peak_residency_bytes"))
```

实测输出（M=32，4 核）：

| 计划 | plan_id | 合法 | ops | 依赖边数 | 片上驻留 | 每核峰值驻留 |
|---|---|---|---|---|---|---|
| `naive_layered` | `dbe43cc256081c5a` | 是 | 100 | 1170 | 0 B（全部落 DRAM） | — |
| `resident_pipelined` | `738420509c6733af` | 是 | 100 | **292** | 5,308,416 B | 294,912–327,680 B |

两者 MAC 总数相同（2,264,924,160 = 3×32×2560×9216），差别在**驻留位置与顺序约束**：
去掉整层屏障后依赖边数减少约 4 倍。这是可解释的结构差异，**不是性能结论**——
没有任何 cycles 数字。

## 常见阻断

| 现象 | 原因 | 处理 |
|---|---|---|
| `pip install` 报 hash 不匹配 | PyPI 被替换成 HTML 拦截页 | 改用 `scripts/env.ps1`（PYTHONPATH 指向已有 site-packages） |
| `git clone` 报 `early EOF` / `curl 56` | 代理截断大文件 | 用 `--filter=blob:none` + `sparse-checkout` |
| `BackendUnavailable` | ONNXim 无法构建（无 cmake/conan） | 预期行为；见 `docs/02_environment_blockers.md` |
| `wsl.exe` 被拒绝 | 主机安全策略黑名单 | 全程使用 Windows 原生 |

## 不做什么

本轮不建设描述符 ISA 模拟器、完整生产编译器、通用九段 IR、自研 DRAM/NoC、
全模型 benchmark 集、跨芯片/3D memory 或新调度硬件。冻结的 R1–R13 代码、合同
与结果未被修改。
