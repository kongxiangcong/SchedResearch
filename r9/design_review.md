# R9 首跑前实验设计独立审查

日期：2026-09-05。范围：[run_experiment.py](D:/dsh-proj/SchedResarch/r9/run_experiment.py:1)、[首跑补注](D:/dsh-proj/SchedResarch/r9/prerun_clarifications.md:1)及其与当前模型的接口。只执行候选生成、phase生成、graph合法性与人工decision字典检查；未执行主性能实验、未读性能结果、未编辑runner/model。

**决定：Accept 当前有限模型实验设计进入主运行。两项首跑前缺陷已经由主代理修复并复核；未发现剩余阻断问题。** 本审查不替代逐request独立审计或结果红队。

## 已发现并修复

| 问题 | 影响 | 当前复核 |
| --- | --- | --- |
| `alternative_actions()`读取`index`，模型输出`decision_index` | 首个可替代EXT决策会KeyError，无法执行反事实 | 已统一`decision_index`。用模型格式的人工decision字典调用后正确返回替代request。[当前实现](D:/dsh-proj/SchedResarch/r9/run_experiment.py:171) |
| 首跑registration未hash `prerun_clarifications.md` | 连续时间相位、统计量、有限敏感性池及no-action解释没有被事前回执绑定 | 已加入补注、source audit、冻结Qwen config/MLP源码；在training前保存。[当前注册](D:/dsh-proj/SchedResarch/r9/run_experiment.py:199) |

## 候选池、分组与统计

- 实际池为 **204个候选，C1N/C2N/C2K各68个**，每mapping单播/广播各34。Ktile=256/512/1024/full、buffers=1/2、prefetch=1/2、resident-X、multicast、gather/row、XW/WX、forward/reverse、outstanding=1/2/4均有代表。全部204个graph能在主参考容量内构建，有用MAC均为37,748,736。这里验证“维度有覆盖”，不声称所有维度联合组合穷举。[pool](D:/dsh-proj/SchedResarch/r9/run_experiment.py:35)
- train8、validation8、test session1/2各30个phase，实际76个值互不重复。同一个phase跨policy/条件复用用于配对，不把请求或相同quiet重复当独立硬件观测。不同phase均由独立注册seed系列生成。
- 训练按mapping×输入方式×环境取top4，validation从合并shortlist按环境选一次，选择文件在test前保存；test不回流选择。main范围不含C1N，C1N仅单独控制。未发现该路径统计泄漏。[choose](D:/dsh-proj/SchedResarch/r9/run_experiment.py:113)
- 固定quiet-selected干扰损失为`T(q,interference)/T(q,quiet)-1`；更强静态消除量为`1-T(strong,interference)/T(q,interference)`，两者分开正确。所有gain先按block计算百分比再取均值，n30、df29的t区间与补注一致。[summary](D:/dsh-proj/SchedResarch/r9/run_experiment.py:143)
- 每个已选graph的`1-L/T`约束同一graph的选序动作；它不是实测恢复量，也不是跨mapping的统一最优界。t区间属于有限相位抽样的近似推断；在全部样本相同/全零时的零宽区间不能证明未见相位的总体方差为零。

## 敏感性上下文

固定敏感性子池为 **12个候选，C2N/C2K各6个**，仅双buffer、prefetch2、非resident-X、gather、XW、forward、outstanding4，交叉mapping×Ktile×multicast。它与主204池不同，报告需始终称有限子池重训，不能把相对主selected-static的差额全归因单一硬件参数。[子池](D:/dsh-proj/SchedResarch/r9/run_experiment.py:266)

结构检查：外存带宽32/128、cluster DMA32/128、MAC512/2048、latency4/36这8个变体均12个graph合法；可用VMEM256 KiB变体为 **8合法、4容量拒绝**。拒绝的是1024双buffer计划，保留的256/512计划提供有效候选。`evaluate_job()`保存非法原因，敏感性train shortlist只从合法项选择；其validation硬件上下文不变，未发现将非法候选重新选入的问题。

敏感性使用原独立test相位形成配对控制是预登记行为；它没有独立新test来确认后验机制。没有在敏感性运行新的因果机制、也没有完整静态全局最优声明。[补注](D:/dsh-proj/SchedResarch/r9/prerun_clarifications.md:10)

## 单动作、收费与no-action解释

首/末各4个有竞争的EXT决策、每处第一个非默认request、0/8 cycle收费均在结果前固定。末4个决策以及事后逐block取最优使用未来知识，**只能称sampled hindsight screen**。有限样本中最优有收益不能作为因果policy收益；无收益也只否定这些已测单动作，除非另有有效资源上界覆盖更大动作集。

模型将8 cycle付在选定EXT请求的实际开始前，期间EXT被本次选择占用；后续所有事件/服务从头重算。收费不等于机械地把最终elapsed加8，因为可与背景预留或其他引擎工作重叠。引擎检查request当时eligible，且如果指定决策从未发生则报错；没有静默把未执行动作记为收费成功。[cost语义](D:/dsh-proj/SchedResarch/r9/model.py:408)

runner以baseline初始化free/charged最优值，因此包括免费no-action，最优统计必然不负。它正确表示“可选择不干预的回看恢复”，**不能据此称quiet回退≤1%已通过，或某个固定因果策略已通过5%/CI门**。全部收费失败值另存`counterfactuals.json`，不得只报告裁剪后的最优值。[no-action初值](D:/dsh-proj/SchedResarch/r9/run_experiment.py:228)

最后，`max`恢复上界若来自两session共60个phase，它是**已测试相位的最大值**，不是整个连续相位空间的supremum。可据此关闭当前已测模型包络的具名候选；若声称所有相位均无法5%，还需全相位解析界或经证明的枚举覆盖。

## 审查时版本

| 文件 | SHA-256 |
| --- | --- |
| runner | `f8c2e4f5093346aedad5ce12d0755b889e38d3176221760707b572bbfcb61872` |
| prerun clarifications | `4afb2f4da6cc5c259f8276f7d60a19e855392e8f37f5f77002866184908acae7` |
| model | `c2bce41235fddd8fae95265cd37a4704d3504ad24ded013ec225d05760af2214` |
| reference hardware | `2a2f99d8a4ed0f4601cc288f69b49abffe2680b2fac7b7aeb45dc052e46035c3` |

这是首跑前审查快照；最终证据以主运行registration/完成回执和独立checker所绑定的版本为准，后续改动不被本文hash自动认证。
