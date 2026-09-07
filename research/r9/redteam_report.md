# R9 独立红队：参考模型执行与判别边界

审查对象是本轮自主选择的 `shared-EXT-cluster-DMA-VMEM` 数值合同，以及该合同下的 payload 图、事件执行、有限静态搜索和相位配对实验。没有新 TARS、RTL、硅后、Phoenix 或 PPA 证据。性能结果不继承 R8 的 CPU 随机容差为官方 bitwise 许可。

## 证据状态

`independent_check.py` 不导入 `model.py` 或 `run_experiment.py`。它读取已保存 JSON/gzip 证据，独立对周期预留区间积分、重算服务 bytes 和资源下界，验证真实访问生存期，并独立重算选择和统计。`check_tests.py` 仅作为正常 fixture/故障 fixture/tiny 输入产生器调用模型，再把证据交给独立 checker。二者职责分开。

最终机器回执以 `results/audit_results.json`、`results/audit_tests.json`、`results/tiny_exact_results.json` 为准。全部主实验完成标志为 `results/completion.json`；审查不把运行期间的部分 manifest 当成最终覆盖。

**最终独立复验 PASS**：608条保存trace，477,312个请求，57,232次compute/reduce操作；204个注册候选、25个validation候选的选择重算；76个独立phase值、180个paired blocks以及36组均值/t区间重算。checker SHA256 为 `391a2431a6b8429e7a5ea05127509f098ca0b1743c4cd7ad0e06a4890ad173f2`；所审trace manifest SHA256为 `abb1e4e3f010f15b022009bf80e2874e99eac7858f328c1f441ecb1bbfcf9a87`。

## 主动攻击与安全检查

| 攻击/疑点 | 独立检查或边界 |
|---|---|
| DMA 字节漏算、重复赠予共享带宽 | 每个声明 packet 恰有一个请求；命令源/目标区域与 packet 区域逐地址覆盖一致；每个源 span 独立按32B beat取整；外存服务段总长乘速率必须等于物理 bytes；共享 EXT 不重叠。 |
| 广播免费送达第二私有 VMEM | 每个目的 VMEM 都有保留区间；cluster DMA bytes 是全部目的 span 之和；4096B广播 payload 使用8192B local服务/transport预算；完成与credit释放等到两处全部可见。 |
| split-K 绕过代价或结束边界 | 逐地址覆盖全外存 X/W；K/N矩形与每核升序K tile完全覆盖真实37,748,736 MAC；stage write与read各16384B，同共享EXT和有限scratch；最终Y恰好16384B、不重不漏，全部外存可见才结束。 |
| row/gather 偷用预打包输入或错读 tile | 对每个 compute，从直接X/W producer核对原始row-major外存行地址、K tile与N shard；核对压紧VMEM的地址/驻留X行stride；源packet与命令源区间完整对应。这里只证明模型图的操作数身份，不执行BF16乘加。 |
| 过早消费或slot在DMA最后读前复用 | 读请求的source-last-read=EXT结束，写请求=local结束；所有consumer开始≥全依赖destination-visible；通过所有实际DMA/compute访问区间检测写-读、写-写地址冲突。 |
| credit、transport或command窗口无限大 | `accept→visible` 扫描outstanding和transport占用；每slot不能重叠，单slot bytes有限；命令从admission到全packet可见独立扫描8槽限制；VMEM地址避开64KiB保留区且不越容量。 |
| 队头人为失能、干预选到尚未ready请求 | 由所有请求stage完成时刻重建每个EXT决策的完整eligible集合；核对既有EXT/local路径work-conserving；单次动作只能选该集合成员，8cycle收费实际推迟外存服务开始，并重算后续内生事件。 |
| 拷贝另一policy的延迟或改变背景 | 每条保存trace的环境必须等于预登记session/block的绝对phase与duty；共享供给的负起点前一周期也纳入积分；请求服务不能进入预留段。 |
| 测试泄漏或有利相位重复 | 独立重生成910000/920000/930000/940000四个seed的8/8/30/30个phase；76值不重用。由train重新推导每mapping/广播组/环境的top4并核对validation名单；所有最终赢家只能由validation选定。 |
| 下界方向错误 | 独立计算 `max(从t=0起累计EXT供给足够传全部必要bytes的时间, 各cluster必要local服务, 各core必要占用)`；该式放松了全部先后约束，不能高于实际结束。`(T-L)/T` 是同合同内重排恢复的上界，不是恢复量。 |

首跑前检查覆盖27个静态构型、50,404个请求，包括三种mapping、单播/广播、row/gather、X驻留/非驻留以及full-K。故障副本包括漏packet、过早consumer、免费广播、少服务一cycle、DMA源最后读期间alias覆盖、credit超限和transport slot重用，7例均被检测。故障只修改内存副本；正常结果未被覆盖。

## Tiny exact 的精确范围

两条read请求链同时在t=0接受，共用一个EXT和一个cluster DMA。A从EXT读64B并送两处VMEM，B读128B送一处；两种EXT顺序AB/BA穷尽合法首选择，随后本地FIFO顺序唯一。使用32cycle周期、25%预留，phase=0/13；独立按整cycle枚举供给，得到AB/BA最终可见时间分别21/22和29/30，与模型每个node的完成时刻完全一致，4条trace也经独立审计。

该tiny的终点明确是两处输入在VMEM可见，用于检查read-stage顺序、共享服务与有限选择；它没有compute或最终外存Y，不能被称为主工作量exact最优证明。主实验的最终外存Y由完整trace检查覆盖。

## 判别结论与不能越过的门

204个事前静态候选，train后25个进入validation。主条件均选到同一个C2K/Ktile256/双buffer/广播/gather/X先/逆核序/outstanding4静态。quiet为47,776 reference cycles；同一quiet-selected static在20%预留下，两组独立模拟phase的平均损失为24.7543%/25.3070%，35%为52.8112%/53.0114%。重新训练静态的额外消除量为0，因为选中的静态相同；不能把不同静态之间或2核/4核之间的差分叫动态调度收益。

| 独立模拟phase组 | 20%剩余零成本上界最大值 | 35%剩余零成本上界最大值 | 20%收费单动作回看最佳均值及95%t CI |
|---|---:|---:|---|
| session 1 | 4.240450% | 5.157867% | 0.021036% [-0.003008%, 0.045080%] |
| session 2 | 4.051386% | 5.157867% | 0.008010% [-0.003702%, 0.019722%] |

35%条件下已测单动作的最好净恢复为0。总计2,880次单动作重新执行，原始记录保留1,420次更慢结果；展示的best含no-action，不能用它证明quiet回退≤1%的可部署策略门。最晚4个eligible epoch与事后择优包含未来知识，未实现causal policy。收费后的最好结果偶尔优于零收费同一动作集合并非免费收益：8cycle确实计入外存开始时刻，延迟改变绝对phase上的后续顺序；不能从末时刻直接减8模拟收费。

**Accept** 该参考合同下的执行账本、完整trace可见性/容量证据，以及固定静态干扰损失主要接近共同供给减少的条件性解释。平均资源下界余量小并不证明它在所有phase下都小。

**Reject** 这批预登记单动作筛查能支撑新机制：最高平均收费恢复远低于5%，20%的CI跨零，35%没有恢复，也没有满足可部署策略的因果观测和quiet回退门。

**Refine，不作全部关闭**：预登记要求两个非极端背景、两session的最大零成本恢复上界均不足5%才关闭具名额外选序候选；35%的5.157867%明确未通过这条停止门。20%已测相位块中的上界不足5%只能约束这些块及该固定合同，未穷尽连续phase。更宽敏感性还有EXT128B/cycle最大19.858830%、local DMA32B/cycle最大15.894406%的松弛空间；它们是9个事前单参数变体内的受限静态重选结果，不证明存在同等可恢复收益，也不允许用来事后挑正例。其他吞吐、延迟、VMEM变体也不能被本轮一并关闭。

## 覆盖限制

主实验每条件每session30个paired blocks；这些是独立模拟相位组，不是实机session。t区间针对预定相位采样下的成对均值；quiet重复是确定性的，零宽CI没有提供设备稳定性证据。静态池不是全部联合维度的穷举；敏感性只用事前受限子池重新训练。

保存并逐请求审计的是180条主静态trace、360条额外mapping控制trace、14条改善结果的单动作trace和54条敏感性首block trace，共608条。未保存全部2,880次反事实或全部1,620次敏感性执行的逐请求trace；其完整数值结果保存，但独立payload检查只覆盖明确列出的trace。tiny全枚举也不扩大这一范围。

未来若继续，应先加强35%下的下界或在同一参考规格内检查一个事前限定的更有判别力动作集合；若替换真实TARS参数，须重新审查split-K FP32许可、2D gather/广播、local端口、预留/不可抢占仲裁和completion合同。任何上述模型结论都不构成真实目标的最终机制接受。

复验：`python -X utf8 -B r9/check_tests.py --results r9/results`，再运行 `python -X utf8 -B r9/independent_check.py --results r9/results`。冻结工件身份和历史由根任务的 `r9/check_results.py` 与既有R8 checks另行核验。
