# R6 预登记：先验证可执行测量，再决定是否存在架构问题

日期：2026-09-05。本文件写于任何 R6 kernel 实验之前；设备枚举和只读文件盘点已经完成。R5 主结果与后验驻留控制原样保留，不重跑 R1–R5。

## Research question 与 hypothesis

1. 在真实目标合法 kernel、dtype、tiling、布局、prefetch 和跨层 memory planning 后，受控共享资源行为是否仍造成稳定、有意义的端到端剩余损失？H1：此残差存在是待测命题，不能由 R5 约33%的模型环境差分推定。
2. 两个 head、四个 prepared token 的 RF 控制能否代表完整 autoregressive decode？H2：不能直接外推；应先按官方 shape/cache/generation 时序检查全层活跃状态、RF 可访问性和其他算子竞争。
3. 若残差存在，是否有因果可观测信息和有限合法动作能在相同合同内回收足够净时间？H3：只有上述条件逐门成立才值得新增机制；本轮不预选资源或 scheduler。

## 实际可用证据与限制

只读枚举发现本机 AMD Ryzen 7 7840H、AMD IPU Device，驱动10.1109.8.110；XRT2.17.0将0065:00:01.0识别为RyzenAI-Phoenix，Ready=Yes。已安装目录含vendor validate binary与runtime DLL；D:/riallto含旧driver/RadeonML发布包。尚未执行kernel，不据文件名判定BF16支持或编译工具可用。

PATH未发现Verilator/Icarus/Yosys/sbt/java；WSL枚举无已安装发行版。当前Python有numpy/onnx而无onnxruntime、torch、openvino、tvm。继续盘点其他已安装环境；本结论只覆盖已检查范围。R1–R5 trace为研究程序生成，尚无目标kernel实测trace。公开RTL/source只提供其明确配置的规则证据。

## Strong static baseline

先取得目标实际支持的kernel与数值oracle，冻结binary、输入、布局、工作量、实际频率/热状态、运行边界。静态候选至少记录真实支持的fusion、K/N/M tiling、驻留与spill、单/双缓冲、bank placement、prefetch与资源序，预算先冻结，train优化、validation选一次，test只评价。未获得compiler接口时不称strong-static已经实现；vendor自测不是本研究baseline。

## 本轮立即执行的判别实验

E0为测量能力验收，不是性能比较：保存设备/driver/runtime和binary哈希；读取XRT各可用报告；运行一次vendor verify；只有成功且耗时有界才进行其公开支持的单次data-fabric bandwidth自测（无支持则记录失败）。不使用all suite、不reset设备、不安装或升级driver、不变更全局环境。每命令保存参数、开始结束UTC、host elapsed、stdout/stderr/返回码，单命令120s超时。可对不支持的report再做一次针对性查询，不能以猜测参数无限重试。工具主机elapsed不是device kernel elapsed。

E0之后先校验counter语义：空运行/已知bytes单搬运/单compute与instrumentation开关开销。若没有可执行kernel或必要定义，保存阻塞原因，不伪造结果，不增加未校准sim。source-derived容量/时序检查可独立执行，但没有设备性能含义。

E1（条件性、尚未授权其具体实现合同）为固定强静态binary在quiet、两个事先选定非极端background等级、固定/随机相位下的配对测量。E2用新合法静态binary量化compiler收益。E3只有剩余损失及因果观测门通过后，才研究同binary/layout/input/资源合同下有限动作的收费恢复。不能把E1/E2混为E3。

## Split、统计与停止门

测量工具用10次pilot核对边界/方差，不纳入确认。目标参数、背景程序、等级、候选与样本量需要在kernel可执行后、观察确认test之前另行实例化；当前不能虚构这些值。固定split命名为pilot/train/validation/test/retest，phase seed不得跨split复用；每确认条件至少30个独立paired blocks，另一session以新相位复验，随机化pair内先后。按block/session做配对区间，request数不充当独立样本。不得跑到显著为止。

阶段筛选门沿用5%净elapsed改善、95%配对区间下界>0；至少两个预登记干扰条件及独立session成立，不只选择极端压力点；quiet平均回退容忍度预设1%。它是研究筛选阈值，未验证PPA盈亏。动态控制时间/额外流量/资源状态/频率变化均收费。

数值、容量/alias、计数器含义或overflow不合格：Refine implementation/measurement。只有host elapsed：screening；缺traffic/compute-active/具名request或limit观测：不能进机制门。无稳定残差：拒绝该已测包络中的runtime候选。有静态解：转compiler；只有未来oracle有效：先检查因果观测。缺接口是未识别，不是“静态已足够”的negative result。R5通用ready候选保持关闭。

## 历史与复现

原research_progress.md已经按字节保存为history/r5_research_progress.md，SHA256=3e9147e5c53781d9c82fc7da98306b18b689a82ef15fd392765681eaadda10c8。之后更新根表时记录parent manifest、旧快照与新表hash关系，不重新冻结R5或修改R4根README。
