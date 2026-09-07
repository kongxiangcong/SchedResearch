# SchedResearch：NPU 静态调度与动态执行研究

面向多核、多 cluster NPU，研究强静态编译之后仍值得由运行时硬件处理的问题。项目按 R1–R11 保留实验合同、源码、结果、审计及研究决定。

## 阅读入口

- [研究进度与证据链](research/research_progress.md)
- [R11 实验报告](research/r11/experiment_report.md)与[独立红队](research/r11/independent_audit.md)
- [R1–R10 回顾](research/analysis/r1_r10_research_retrospective.md)
- [目录迁移与复现说明](docs/reproduction.md)

R11 报告关闭的是完整 GDN 单层静态驻留的已测候选；各轮结论只在各自实验边界内成立。历史 R3/R4 首页保存在 [research/README.md](research/README.md)，不代表项目最新进度。

## 目录

| 路径 | 用途 |
| --- | --- |
| `research/r1-base/`、`research/r2-ooo-npu/`、`research/r3/` 至 `research/r11/` | 各轮研究材料、实现、合同、结果与审计 |
| `research/sim/` | 共用的 R3 模拟器与编译契约原型 |
| `research/experiments/`、`research/tests/` | 共用实验入口、结果与基础测试 |
| `research/analysis/`、`research/literature/` | 跨轮分析、文献登记与来源证据 |
| `references/` | 外部阅读材料原始导出 |
| `docs/` | 当前项目使用与目录维护说明 |
| `run.py` | 从仓库根运行历史实验的统一入口 |

`research/` 是完整的实验工作区。保持轮次内部路径、冻结源码与清单不变，使相对路径引用和源码哈希审计继续成立。结果保留在原实验所属目录，仍只跟踪已审核的紧凑产物。

## 快速运行

需要 Python 3；本环境已验证 Python 3.12。基础仿真使用标准库；数值检查及绘图还需 NumPy、Matplotlib。

```bash
python run.py -m unittest discover -s tests -v
python run.py -m r4.run --limit 1 --seeds 2 --search-budget 16
python run.py r11/numerical.py
python run.py -m r11.run_experiments
python run.py r11/independent_audit.py
```

也可以先 `cd research`，再执行历史文档中的命令。历史文档所称“仓库根目录”现对应 `research/`；直接运行脚本时，若需要导入同级包，优先使用根目录的 `run.py`。

原始 trace、大结果及部分设备环境不随 Git 分发。新 clone 的完整审计应先生成相应产物；R7 Phoenix 实验仍需要对应设备与 SDK。详见[复现说明](docs/reproduction.md)。
