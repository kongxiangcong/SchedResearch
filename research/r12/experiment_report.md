# R12 第一轮：先准入真实资源与强基线

日期：2026-09-08。**本轮已开始实施，当前接受离线环境、来源与条件性功能检查；强 Wormhole P0 和 native G0 仍待准入，H1/H2 未得到性能支持。** 第一轮反证撤回了“真实2conv示例已证共享总线低估”的判断：最终映射按空间宽度分片，缓冲容量不能证明每个消费者都需要完整张量。条件性共享总线反例仍成立，真实示例的通信需求需按最终affine映射计算。

## 本轮做了什么

完整阅读冻结输入包六个文件，核对五项登记原字节hash，恢复“科研方向重审”的可访问正文，并并行检查固定 ISA、当前 TETRA 源码和完整 Qwen MLP 来源。两个历史台账包含R11追加的正文均已阅读；没有重跑R1–R11性能实验，也没有读取其他方案初稿/演示。[阅读覆盖](reading_coverage.md)

新建 `research/r12` 和工作分支 `codex/r12-wormhole-qualification`。Windows使用项目独立Python环境，取回固定ISA/STREAM/tt-npe依赖；另安装本轮独立WSL2 Ubuntu 24.04供官方Linux工具构建。预登记仍采用原合同的3%门、至少两个完整非极端配置和约1个百分点误差门，不因下面的分析结果调整门槛。[入口与复现](README.md)、[预登记](preregistration.json)

## 实际结果及允许的解释

| 检查/实验 | 本次实际结果 | 证据等级与解释 |
|---|---|---|
| 输入证据包 | 五项原字节SHA-256全部匹配；六文件完整阅读 | 输入完整性；原包未改 |
| 固定Qwen来源 | 四份Git内容按明确历史LF/CRLF表示匹配；工作树原字节仅2/4匹配，差异保留 | 代码/manifest核查；不能把行尾转换后的匹配称原字节匹配 |
| 完整MLP账本 | H=2560、I=9216，三权重总135MiB；M=1/32/128完整MAC已复算 | 逻辑工作量；没有下载权重或执行BF16 kernel |
| 原下界见证 | request-only两计划66/33 flit结果精确复现 | 没有2倍模块加速含义 |
| 完整物理torus路由 | 28,800个端点/NoC组合通过；独立raw坐标表达再次对照 | 验证两NoC方向/顺序/绕回；未检查实际板卡harvest |
| 四tile数据移动候选 | 96个预登记离散选择，每个12,288B payload；包含load、peer、output的请求/响应/ACK账本 | 最大有向链路流量范围132–202 flit；未计通知/credit包、NIU/compute/controller时间，不排序完整elapsed |
| 两链、两代、两源slot | 56事件，10条已登记HB义务全部由可达性证明；四类错误规则均被拒绝并有数值错误反例 | 条件性功能证明，未验证native CPU ordering/物理credit/网络活性 |
| 独立事件复核 | 对56个事件分别优先生成合法拓扑序，所有数值回放通过；新一代compute可早于旧ACK | 56次回放不是穷举全部拓扑序；全序义务由DAG证明支持 |
| 真正SCIP/TETRA运行 | 整数sentinel得x=3/OPTIMAL；官方2conv完整分析管线通过、导出5条真实transfer path，无scalar fallback/overlay | 准入工具，不准入Wormhole P0；分析周期12808与文档14344的差异保留 |
| 固定tt-npe构建与测试 | 独立Ubuntu 24.04、GCC12 Release build/install完成；C++ 45/45、pytest 10/10通过 | 固定上游源码保持clean；准入粗估价API，不准入设备模型精度 |
| tt-npe官方示例 | Python API完成，device 0估计437 cycles；官方CLI因Stats字段不匹配失败 | 保留整体验收`passed=false`与`ready_for_coarse_api_use=true`；示例golden=450未独立实测验证 |
| 共享总线反例与干预 | 参数化完整复制反例与独立链路正控制；full-payload费用干预重新求解得到14344，mapping/fusion与原始完全一致 | 条件性成本敏感度；最终affine映射反证了将其称为真实2conv成本修复的依据，未证明基线缺陷或H1收益 |

回执：[功能摘要](artifacts/qualification_summary.json)、[独立检查](artifacts/independent_checks.json)、[工作量](artifacts/workload_intake.json)、[原始TETRA](results/baseline_smoke/result.json)。首次smoke求解成功但本轮导出脚本误解了路径容器，出现TypeError；`attempt1.json`保留失败，修正脚本后重跑通过，上游源码未改。这不属于上游solver失败。

Linux构建的第三方来源使用上游指定tag，43份官方归档记录URL与hash，通过CPM/FetchContent公开的本地源码接口接入；未修改tt-npe。官方CLI读取`Stats.wallclock_runtime_us`，固定绑定实际将该字段放在`DeviceStats`，故不能把命令行工具记为成功。API复现入口、两次准备失败和全部测试XML见[Linux环境说明](linux_environment.md)与[最终环境回执](artifacts/npe_environment.json)。

## 比上轮更具体的硬件合同

**端点、共享域、物理channel需分别表示。** 三个DRAM tile、两NoC合计六个NIU共享2GiB地址空间；其中地址低1GiB和高1GiB分别指向两个物理channel。相同group的两个endpoint不提供独立带宽，也不能把整个group一律简化成单串行channel。三类见证现在同时保留“同channel别名”“同group另一channel”“不同group”，输入地址保持不重叠。[固定DRAM合同](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/DRAMTile/README.md#L3-L41)

**完成事件需要具名。** 非inline写的sent计数可以早于源数据读完；目标NIU收到最后flit也可以早于目标L1全部写完。源slot复用绑定source-last-read，通知消费者绑定完成ACK及其原生发布顺序，接收slot复用绑定consumer最后读取。删除其中任一对应义务均能构造错误输出。下一DMA必须在源释放后才发起，不能只约束最终`load_visible`。[固定Counters](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/Counters.md#L119-L150)

**部分缓冲参数已经公开。** 每router inbound port为2KiB，各VC保底32B、共享池1.5KiB、单VC最多再取480B。上轮“buffer未知”的说法需缩紧到仍未公开/未校准的NIU排队、credit时序等部分。原始包不改，在R12追加修正；这些数字没有被拼接成未经校准的周期模型。[固定DRAM性能段](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/DRAMTile/README.md#L64-L70)

**离线偏序边仍需原生实现。** Baby RISCV 的`fence`是no-op，不能在伪代码中插一句通用fence就宣布CPU↔NIU发布/轮询顺序成立。`CMD_CTRL`读回、counter作用域/溢出、真实notification和L1消费者顺序，必须检查固定tt-metal原语及实际指令。此处是native G0的具体缺口。[固定MemoryOrdering](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/TensixTile/BabyRISCV/MemoryOrdering.md#L45-L68)

## 对研究主张的第一次反证

当前STREAM已经用真实共享`CommunicationLink`对象表达路径排斥，AIE lowering也已有根据descriptor回收/输出到达而安排等待的实现。因此“联合placement/routing”“区分完成并缩小wait scope”本身都不能直接作为新颖贡献。默认generic入口的单offchip、通用路径候选与AIE资源策略，还没有正确落到Wormhole多channel/双NoC/NIU合同。[基线审计](baseline_source_audit.md)

共享资源探针最初提出一个可检查的怀疑：多源传输使用按源/目标数量分摊的`chains`假设，是否把共享总线当成多条独立链路？在**每个消费者都必须得到全部独立源分片**的参数化合同下，单共享128 bit/cycle总线承载262,144个必需bits，即使理想广播也需2048 cycles；helper给出512。四条真正独立链路的正控制仍允许512。这个有明确前提的守恒反例成立。[共享资源探针](shared_resource_probe.md)

但将前提迁移到真实官方2conv示例的尝试被本轮独立审计推翻：最终Conv1的z6与Conv2的z13均对应ox空间宽分片，不能从每core分配了完整缓冲区推出full all-gather需求。真实消费者需要哪些源元素，应从最终operand affine关系与halo计算。**目前没有证明真实2conv的512违法，也没有证明其通信成本已正确。** 独立审计保留了从容量推断、提出反解释到检查最终映射的证据过程。[独立研究审计](independent_research_audit.md)

从保存的实际operand maps逐元素枚举，在两算子按相同core顺序连续四等分的所有权见证中，四个consumer分别需要512/1024/1024/512个远端16bit元素，合计49152bits，对应384个共享bus payload服务cycles。512高于此必要下界；但这不证明原生地址安排、实际搬运策略或完整512-cycle传输可实现。该见证足以否定“计算本身强制传完整262144bits”的推断。[最终affine与需求回执](artifacts/shared_resource_affine_audit.json)

收窄结论前已执行的[分析干预合同](shared_resource_counterfactual_contract.json)及[原始回执](results/shared_resource_counterfactual/result.json)原样保留：固定源码不改，只在指定的单bus transfer上将512改为full-payload合同的2048，然后重跑真实TETRA。分析总量从12808变为14344 cycles，mapping与fusion完全相同；40次helper调用中8次匹配，其中5次来自allocator。它现在只回答“若对该transfer收费2048，当前优化器如何响应”，**不再解释为真实示例成本修复、真实性能或P1收益**。原始合同/回执中更强的措辞被本报告及后续需求审计明确取代。

这个小闭环的结果是条件性成本改变没有改变所选计划，而我们对真实工作量的初始解释未通过反证。下一步先建立逐source-slice、consumer实际需求和逐共享资源之间的可核算关系，再准入强P0。若正确接入资源及执行语义后，现有求解器已吸收所有收益，应接受H0或记录后端工程结果。

## Continue / Refine / Close

| 门 | 当前判定 | 尚缺什么 |
|---|---|---|
| 离线来源、工具与逻辑小图 | Accept当前明确覆盖的子项 | 不扩大成设备正确性 |
| G0 | Refine，尚未通过 | 固定原生后端/SoC/harvest；部分写入、counter/credit/notification、完整输出及终止 |
| G1 | 未测试 | 正确重定向且强化后的P0；三个见证家族真正执行，排除基线错误 |
| G2 | 未测试 | 完整MLP的原生数值/布局、校准elapsed；至少两个非极端配置3%净改善 |
| G3 | 未打开 | 最强P1之后的残差、固定mapping/address/routes、有界动作、完整控制费与PPA |

本轮继续编译器主线，暂不实现Rh。设备或远程主机入口尚未提供，但可继续进行后端源码与功能仿真准备。板卡性能资格不能被离线重复、ttsim功能成功或tt-npe粗估价替代；没有生成新的性能置信区间、模块加速比或硬件立项结论。
