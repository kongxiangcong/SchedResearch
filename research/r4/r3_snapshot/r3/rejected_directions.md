# R3主动拒绝与暂缓的方向

日期：2026-09-05。负结果与原始样本同等保存。

| 方向/主张 | 决策 | 具体原因/证据 | 重新进入条件 |
|---|---|---|---|
| 将CPU Tomasulo搬到NPU | Reject默认起点 | 已知DAG/binding/address无需先付rename/speculation，四任务counter即可达到exact值 | 真实load依赖/别名或恢复机制要求它，并有局部测量 |
| 一般execution contract+completion dispatch作为novelty | Reject宽表述 | SPDI、VTA、ASPEN、HwSch等高重合 | 明确硬件状态/带宽或执行语义delta |
| R2无reuse必然零收益 | Reject | 无alias、bounded CoV0.2反例150→140 | 不再作为必要条件使用 |
| R2只有heavy tail才能获益 | Reject | 同一有界反例；关键在ready inversion | 将命题改为具体目标设备的测量结论 |
| Memory contract本身新颖 | Reject | LATTICE v3直接覆盖静态memory plan作为可验证时序合同 | 尚未解决的runtime/有限状态问题，且能产生价值 |
| 更复杂age/pressure C | Reject本轮实现 | 在所测配置均值上未胜B，额外算术还未收费 | 从具体失败trace提出有因果依据的新机制 |
| 每task拆得更细总是更好 | Reject | control开销、descriptor与window增加；拆分还必须保持噪声相关性与语义 | 非人工variance averaging的iso-work Pareto优势 |
| 更大window总会更快 | Reject | 四任务W3=W4，state继续增长 | 真实ready前沿受window限制且收益回本 |
| 所有价值仅在通信层 | Reject全称 | 核内严格反例；多chip barrier图动态可能更慢 | 目标workload实际证据支持更窄主张 |
| 分布化自然解决scalability | 暂缓 | 按域加端口/queue会改变总预算；全图history/通知仍存在 | 等预算+远程credit/visibility/死锁验证 |
| 比4MiB SRAM小所以scheduler免费 | Reject | state bits不是ports/wire/comparator/Fmax/energy | 具体RTL/PPA证据与正确成本模型 |
| Jalapeño系统优势证明OoO有效 | Reject因果推断 | 系统同时改变多个因素，原始微结构及ablation未取得 | 官方微结构披露及可比较实验 |
| 直接模拟完整大模型 | 暂缓首轮 | 会把图/编译/modeling问题与scheduler纠缠 | 先通过synthetic因果检查，再导出单block真实图 |
| 继续以R1源码路径声称live验证 | Reject | 源码不在本目录；只有历史转述 | 显式提供源快照/版本与可运行导出 |
