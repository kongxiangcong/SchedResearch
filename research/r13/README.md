# R13：多tile模型与有限小图探索

本轮采用硬件建模，不需要Wormhole板卡。结果入口为 [实验报告](experiment_report.md)，原 [proposal合同](proposal_contract.md) 保留首次立项状态。

- 已执行：DES、独立tick/数据审计、完整CPU数值资格、真实TETRA来源seed、576项有限小图全集、168项冻结见证回放。
- 状态：M0内部实现资格已有证据；限定NPE跨工具运行受当前WSL权限阻断；Hmodel有局部证据，M1编译器门/M2未通过。
- 下一步：[共同计划/顺序能力与强P0准入](p0_qualification_next.md)。保留负结果，不从粗估价regret直接跳到新算法。

## 文件

| 用途 | 入口 |
|---|---|
| 可读结果与图 | [报告](experiment_report.md)、[紧凑独立分析](artifacts/micro_independent_analysis.json)、[全表CSV](artifacts/micro_nominal.csv)、[参数图](figures/micro_witness_sensitivity.png) |
| 冻结输入 | [执行注册](preregistration_serial.json)、[硬件](hardware_model.json)、[服务机](machine_contract.md)、[数值](numerical_contract.json) |
| 单一主引擎/图构建 | [event_machine.py](event_machine.py)、[model_builder.py](model_builder.py) |
| 独立资格 | [independent_checker.py](independent_checker.py)、[trace_audit.py](trace_audit.py)、[检查器证据](checker_design.md) |
| 原编译器接入 | [baseline_intake.md](baseline_intake.md)、[目标适配](port_micro_tetra.py)、[lowering](lower_tetra.py)、[独立审查](tetra_lower_independent_audit.md) |
| 性能实验/分析 | [run_micro.py](run_micro.py)、[analyze_micro.py](analyze_micro.py)、[原始名义JSON](artifacts/micro_nominal.json)、[原始见证JSON](artifacts/micro_witnesses.json) |
| 来源与纠错 | [阅读覆盖](reading_coverage.md)、[修正](model_refinements.md)、[方法独立审查](micro_design_audit.md) |

## 复现

复用R12固定Windows环境 `research/r12/.venv/Scripts/python.exe`，不升级依赖。已验证Python3.13.12、NumPy2.5.3、STREAM1.14.1、OR-Tools9.15.6755及Matplotlib3.11.1；固定来源版本见 [R12 dependencies](../r12/dependencies.json)。

从仓库根运行，只读核查和独立单元测试：

```powershell
& research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/freeze_artifacts.py --check
& research/r12/.venv/Scripts/python.exe -X utf8 -B research/r12/freeze_artifacts.py --check
& research/r12/.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s research/r13 -p 'test*.py'
```

重新执行冻结的576候选或168个见证，指定**不存在的新输出路径**。使用当前注册，只串行推进，避免当前Windows IPC限制：

```powershell
& research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/run_micro.py nominal --output research/r13/local_replays/nominal.json
& research/r12/.venv/Scripts/python.exe -X utf8 -B research/r13/run_micro.py witnesses --output research/r13/local_replays/witnesses.json
```

代码/成本哈希改变会被拒绝；这时应产生另一明确版本的注册与结果，不覆盖本次冻结内容。`analyze_micro.py`专门对已保存结果作描述分析，输出若存在也拒绝覆盖。其他资格脚本的CLI及输出行为见相应文件，复跑应保留本次回执。TETRA原始pipeline缓存和临时输出可由源脚本重新生成，紧凑导出与selected证据已经保存。

原始名义/见证大 JSON、TETRA 导出和完整lowering回放超过本次提交的200KB紧凑证据上限，保留在本地复现目录；`artifact_integrity.json`登记提交范围和历史快照校验。提交中的独立分析、CSV、图和小型回执足以复核本轮数字与边界。

完整MLP只有CPU数值和工作量资格，没有资源lowering或性能实验。模型只资格化对齐unicast/read/nonposted-write动作子集；固定微图为1KiB，不能把8KiB单packet测试误用为8KiB完整微图支持。

NPE脚本 `npe_projection.py`复用现有WSL环境。本次指定发行版调用实际被拒，JSON明确未执行NPE；无需板卡，不因这个限制伪造跨工具PASS。
