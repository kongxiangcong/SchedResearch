# 下一轮 proposal 合同：真实 NoC 执行语义下的联合编译资格验证

状态：2026-09-07 提案，尚无新模块性能结果。不是新模拟器或新硬件实现。

## 研究问题

在固定的 Wormhole B0 原生异步执行架构上，正确表达共享 memory-controller/NIU 资源、源缓冲可复用时刻与目标数据可见时刻后，是否会改变强 tensor-placement/transfer-routing 编译计划的优劣，并产生可重复的完整模块收益？剩余收益是否需要新的有界运行时动作？

主线是编译器；备用是固定 mapping/address 的有界执行自由度。TETRIS 作为独立的 3D 论文合同，不与 Wormhole 混成免费扩带宽模型。

## 反证优先

H0：正常配置/移植当前 STREAM/TETRA，加原生 circular-buffer、async NoC、优化 wait scope，就足以消除具名损失；无需新编译算法或乱序硬件。
H1：完成语义与共享资源的组合会造成已有优化计划的可测排序错误或不必要的 buffer 占有；通过联合选择 placement、合法 NoC 路径、发送窗口和等待范围，可在原生 runtime 上降低完整模块 elapsed。
H2（条件备选）：固定 H1 计划及全部地址/工作后，真实运行时信息仍允许有限候选窗口在收费后超越最强静态/依赖驱动软件对照。

不能以 H1 成立推出 H2；不能以共享 EXT 模型与真实架构差异本身作为新方法贡献。

## 固定来源

项目 a947b563356610cf4dbb05995debf18fc3054e66。
Wormhole ISA 5287a62727350bcef35f7b411d1b8a706172ec4c。
STREAM 75748cc17e7c43add5a7d0d8f080841eb26531c4（1.14.1）。
tt-npe 341da058f0b65e51d3643fb36f011a0784abedff。
硬件板卡/固件/tt-metal/SoC descriptor/harvest mask 尚需在执行前固定，不允许假定文档全芯片配置等于任意 SKU。

## 最小图与预登记见证

四个活动 Tensix tile，保留物理 torus；两条 load→compute→peer-write→consumer 链，最终输出写至共同指定位置；两个可复用 buffer slot。见证族事先固定为：

1. 相同数据量与总 byte-hops、共享链路与分离链路。
2. 多个 DRAM endpoint 属于同一 controller，与真正不同 controller。
3. 相同地址下区分 source-last-read、destination-visible 和 notification，并比较允许的最小 wait scope。

先做静态候选小图枚举与事件正确性，不添加计算噪声。不启用需要额外活性证明的 VC_LINKED、非零仲裁优先级等特殊网络模式。

已有 bound_witness.py 仅实现第1类的 request-link 字节下界核对，不是上面完整图的时间模拟。

## 完整工作负载

优先 Qwen3.5-4B 完整 MLP：H=2560，I=9216，down(SiLU(gate(X))*up(X))。来源为项目 R8 登记的官方模型配置和 Transformers revision；执行前读取冻结源并重验 hash。
M∈{1,32,128}。M=1 为单请求 strict-decode 对照，不能预给后续 token；prefill 的输入批明确已经存在。权重、激活、输出位置信息和全部 cold/warm 政策固定。不能仅复用 R8 的 down N=128 切片作为完整指标。
数值方式及归约树先准入。BF16/FP32 原生实现与项目 FP64 oracle 的差异要报告；不以误差容忍掩盖改变计算语义。

## 变量、约束和候选算法

变量：算子/张量分片、compute placement、memory-domain placement、复制/驻留、地址和合法生命期、NoC0/NoC1 等原生路由选择、发送 release/window、等待范围、可选资源排序边。
约束：真实依赖、RAW/WAR/WAW、归约顺序、source last-reader、目标可见、buffer 容量/复用、NIU 资源、协议顺序、credit 守恒和无死锁。
算法候选：以强 TETRA 结果为起点，执行语义核查产生最小冲突；正确性冲突加入合法性约束，拥塞反例仅形成有依据的成本项或下界，不能直接把一次慢执行当作非法组合删除。反复求解 placement/发送窗口/等待范围，导出带正确性证据的原生执行计划。

这不是已证明的新算法。若现有求解器接入正确硬件资源后就能得到同样结果，应收敛为后端建模/编译工程或负结果。

## 比较与归因

P0：正确重定向的强 STREAM/TETRA + 合法 fusion、tiling、prefetch、双缓冲、通信感知 mapping、原生 wait scope 优化。
P1：候选执行语义联合计划。
R0：原生 self-timed/CB/NoC pipeline，固定选择的资源次序。
Rd：同硬件上的依赖驱动软件参考，使用已有算法并计入真实执行代价；不是声称厂商提供通用 DFG 任务调度器。
Rh：新增有界动作，只有 H1 后仍有残差才实现；不改变 mapping/address/routes。窗口之外的历史和元数据必须计入。
报告 P0/P1 × R0/Rd/Rh。控制 offload 与同计划改变次序分开测。

## 指标、正确性、校准

完整模块入口至输出/状态可见的 elapsed；必要时另报 host 提交到完成，控制 offload 不得切掉被消除的 host 时间。另报 throughput、适用时 p95/p99、逐层 bytes、逐 link/controller/NIU 利用与排队、峰值 SRAM、compute-active、critical-path waits、实际动作数与单动作效果。
同策略独立演化内生队列，不重用 baseline 的结束时间。相同外生流量在绝对时间上配对。固定 shape 无噪声重复不是独立样本。
校准先覆盖单请求、共享/分离链路、共享/分离 controller、source-read 与 destination-visible。ttsim 只作功能工具；tt-npe 只作粗筛，不当完整 DFG 周期真值。

## Continue / Close

G0：完整小图数值、所有事件顺序、复用、credit 和终止检查全通过；每类候选动作实际触发。零动作不进入大实验。
G1：预登记 witness 家族中存在强 P0 后残差，且不是硬件资源增加、错误端点建模、弱原生 kernel 或非法排序造成。
G2：建议 P1 在至少两个预登记非极端完整模块配置达到3%净 elapsed 改善，校准对相对收益的误差界不超过约1个百分点；否则先 Refine 仪器，不降低门槛。随机实验另要求配对区间下界大于0。确定性实验逐配置报告，不伪造 timing CI。
G3：Rh 需在最强 P1/R0 或 P1/Rd 之上达到3%净改善，gross recovery 至少覆盖2倍暴露控制开销，quiet 回退不超过1%；没有 PPA 估计不进入硬件立项。旧5%另作历史对照。
Close：现有编译/原生 runtime 吸收全部残差；改进只出现在削弱 baseline 或改变数值/资源后；零成本 runtime 上界已小于完整费用；或只剩普通后端移植且没有可区分贡献。

上述收益门是本轮预登记建议，不是物理常数；在任何性能 test 之前冻结。未知硬件费用必须保留未知，不使用跨平台加速比或把局部同步延迟当完整调度费用。
