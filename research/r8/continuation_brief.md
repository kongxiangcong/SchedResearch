# R8 continuation: 回到每 cluster 两核的多 cluster 研究主线

用户于2026-09-05明确同意范围与推进顺序，并要求更新科研进度维护文档、在新任务直接继续下一轮。本文是**已批准的范围对齐与交接**，不是R8实验结果或完整预登记。

## 科研目标与架构范围

科研问题：在编译器已做好合法mapping、地址/layout、驻留、tiling、预取与静态排程之后，多核/多cluster共享资源与跨域完成变化还留下什么端到端损失？其中是否存在强静态无法消除、因果可观测、具有有限合法动作且计入控制成本后仍有价值的硬件机会？成功是得到有证据的Accept/Refine/Reject决定，不要求产生新架构。

| 范围 | 当前定位 | 证据边界 |
| --- | --- | --- |
| 单cluster、2core | 历史TARS原始锚点；下一轮的局部控制组 | R1记录每core MXU/VPU/TMU/VMEM，cluster共享DMA/Controller；需确认当前权威target，不把历史参数自动当现状。 |
| 多cluster，每cluster 2core | **R8优先研究对象；先建立合同** | R3有2/4cluster抽象模拟；尚无目标实现、完整协议或校准。不是已经实现的最终架构。 |
| 多chip / 多chiplet | 由局部问题驱动的后续扩展 | R3的multi-chip只是抽象link/任务资源，不能认证chiplet封装、die间协议、NoP、interposer、热或PPA。当前不直接选为论文方案。 |
| 本机Phoenix | 已可执行的测量辅助平台 | R7只证明固定copy/INT8 GEMM功能与host elapsed入口；不能将它的AIE阵列等同每cluster两核TARS。 |

R6/R7的设备/SDK工作是支撑主课题的测量工作。继续Phoenix适配前，必须先写明它能回答目标合同中的哪项问题以及哪些结论可迁移；若无法对应，不继续无界地追驱动、SDK或PMU，也不把缺Phoenix观测判为目标架构没有机会。

## 继承结果，不重新解释历史

- R3：存在性已由小图反例证明，但未校准多cluster/chip结果不支持规模越大动态越有效；简化集中/分域控制没有完整层次协议或布线成本。
- R4/R5：更强基线与有来源切片主要集中单cluster双核；已测通用completion-ready未过5%净收益门。R5收费最好+0.1821%且CI跨零；不得升级为多cluster/chiplet全域否定。
- R5约33%投影差分是不同环境各自静态重训后的模型差分，非固定binary实机干扰。GDN驻留7.155%–24.027%只覆盖2head/4prepared token；resident B0=S，B2退化。完整模型跨层RF占用、自回归输入时序未验。
- R6：真实Phoenix与copy功能证据成立；Qwen3.5-4B24GDN层×32heads×128×128FP32=48MiB/B1，不能推出每token强制外存流量。
- R7：4次1GiB copy各268435456words零差异；4次INT8[1,2048]×INT8[2048,2048]全部2048输出与oracle逐byte一致。两kernel各两个进程、1+3次；只有单一现场时段、固定小值fixture，不是性能独立session。host runner可重编译，device binary为预构建。
- R7通用timestamp/trace导出机器码为桩；其他4个已装xclbin有XDP_KERNEL，已测copy/GEMM没有，限定目录缺匹配插件/metadata。实际bytes、compute-active、request/limit、运行频率、device no-op和instrumentation开销未取得。首次/后续耗时差不可归因缓存、DVFS或可恢复等待。
- 尚无真实strong-static残差、固定binary干扰pair、合法动态恢复、BF16/GDN实机、RTL/PPA或完整模型验收。继续关闭R5已测ready候选；不关闭尚未测的多cluster研究空间。

## 新任务先做的具体工作

1. **重建目标合同的证据来源。** 先读当前进度及下列原始文件，区分历史实现、公开来源规则与研究假设。以每cluster2core、单cluster控制组→最小多cluster扩展为范围；cluster数、共享DMA/SRAM、跨cluster数据路径、completion可见性、资源/存储归属与容量均显式化。2cluster可作为待评估的最小扩展候选，不自动冻结全部数值。
2. **确认每个可调静态维度与公平资源预算。** 合法mapping/layout、fusion/residency、tiling/reuse、buffering/capacity、bank布局、prefetch、resource order/outstanding等的支持依据；新增通道/带宽/存储与仅改变控制组织分开比较。不要把R3按域复制的窗口/端口当免费层次化收益。
3. **选择一个最有判别力的共享资源问题。** 用具名依赖/数据移动、总bytes与资源/关键路径下界，区分静态可消除、不可回避供给不足、同步/可见性合同缺口和可能的运行时次序价值。候选如共享DMA供给或跨cluster payload/completion边界，但不要预设答案；不做全平台重写。
4. **选择能回答该问题的验证路径。** Phoenix仅在合同可映射时复用；R1当前checkout/设备/RTL入口未知则只问最少缺失信息，并继续文档、来源、合同审计等独立工作。`D:/workspace/llmSched`是旧离线architecture compiler，非R1所述TARS根；其中用户untracked/.runs保留。`D:/workspace/riscv_npu_alias`仅文档，非可执行RTL。禁止扩大扫描或重跑旧实验代替进展。
5. **新实验前给出1–3个未解决问题、假设、证据限制、strong-static baseline、判别实验与停止门。** 对能执行的最小实验实际推进，保留失败和不支持路径；若只能做合同/结构性反例，明确未校准，不能把它当真实瓶颈或收益。已有R7入口不因换会话自动重跑。
6. **完成科研闭环并维护八字段表。** Research Question → Hypothesis → Strong Baseline → Discriminative Experiment → Result → Red-team → Accept/Refine/Reject。新增R8代码/报告/数据放r8，独立分派来源、合同/实验与红队，主agent持续推进。

后续性能门不变：独立train/validation/test，selected strong-static同合同固定binary残差与动态恢复分开；每条件每session至少30独立paired blocks，第二session新相位、至少两个非极端干扰；净elapsed≥5%、95%配对CI下界>0、quiet平均回退≤1%。仅有host elapsed时标screening，最低设备观测不足不启动机制收益归因。采样/仪表开销、频率影响、额外traffic和控制代价必须收费。

## 首读文件与精确复用入口

1. `research_progress.md`（最新主线）及本文件。
2. `analysis/problem_definition.md`、`analysis/compiler_contract_requirements.md`、`analysis/design_space.md`，特别是domain/resource/visibility合同。
3. `r1-base/live_evidence_audit.md`、`r1-base/five_directions.md`，以及`analysis/r1_r2_audit.md`；R1的方向排序是历史，不继承为当前优先级。
4. `experiments/run.py`、`sim/workload/motifs.py`、`sim/noc/__init__.py`、`r3/experiment_report.md`，只核对已存在层级语义，不无理由重跑。
5. `r5/experiment_report.md`、`r5/measurement_gate.md`与`r7/experiment_report.md`、`r7/redteam_report.md`、`r7/measurement_summary.json`。
6. 仅需要Phoenix接口时再读`r7/sdk_build_report.md`、`r7/kernel_access_research.md`、`r7/measurement_access_research.md`。安装runtime：driver10.1109.8.110、XRT2.17.0@42cba83aee86b253c49eccd484646e91d062468d。旧headers/publicbinary的兼容性仅由R7限定运行证明，不能盲升。

## 历史保护与进度维护

目录不是Git仓库。原R1–R7所有文件、结果、否定结论不改；根README仍由R4冻结。R7原进度表在根修改前保存为`r8/history/r7_research_progress.md`，hash与R7 manifest/lineage一致。旧R7 verifier不理解新的live-root；用`python -X utf8 -B r8/check_history.py`按显式快照认证R7 686、R6 89、R5 262、R4 612项。

本次对齐后的根表另有`r8/history/aligned_research_progress.md`快照与`r8/handoff_integrity.json`，只冻结**交接文档**，没有冻结未来整个R8。`--require-handoff`额外要求当前根表仍等于交接版本；R8后续追加结果后不用该选项，需保存新父子关系，保留旧表各行。对齐行是用户决策/计划，不是新实验结果；R8结果另加行，不将“待测”改写成已通过。
