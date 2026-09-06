# Strong static与动态策略的公平实验合同

日期：2026-09-05。这里预先固定解释规则，防止看完结果再挑baseline。

## 1. 基线层次

1. **A：强预测静态**。critical-path/list scheduling、多priority候选，选预测makespan最好的固定资源顺序；执行时依赖和资源允许即可开始，不等待过期的绝对时间戳。
2. **A2：分布感知静态**。在独立training环境上选择期望表现好的静态顺序，test环境只执行冻结计划；不能在test每个seed重选后再称静态。
3. **A-exact：小图最优静态**。枚举合法资源顺序与有限场景，求min E[T]；这是检验“收益只是静态heuristic很差”的关键。
4. **B：固定mapping+completion-ready**。沿用编译priority和同样资源，跳过尚不ready的任务；无未来duration访问。
5. **C：更复杂的causal策略**。同mapping，仅多使用age/resource pressure等实际可见状态。C优于B是待测命题。
6. **O：小图clairvoyant exact**。每个环境知道未来duration后求最优，估算信息价值上限。大图clairvoyant启发式单列，不能称严格上限。

“Fully Dynamic”还包含runtime mapping/dependency discovery，与上述C不同。本轮不做全动态分析引擎；其额外成本/收益需要另一个受控实验。

## 2. 强静态还欠什么

A/A2很重要但仍不是生产级compiler最优：它们未必有完整fusion、bank/layout co-optimization、非贪心资源预约、全部有效序搜索、tensor partition优化、通信collective选择。小图exact消除一部分疑虑；真实motif上若只对候选静态获胜，称“相对所实现强静态”，不能称“compiler不可能解决”。

强静态应有DMA双缓冲/异步加载机会。若原设备共享DMA本来允许跨核队头仲裁，需要加入lane-static基线，否则把已有arbiter的收益重复记账。R2虽做了lane-static，但它的compute/load图结构太窄，不能据此关闭更广研究空间。

## 3. 必须控制的变量

同DAG、task work、数据量、placement、地址、alias constraints、数值语义、engine数量、SRAM容量、DMA/channel/outstanding、NoC/link capacity、descriptor window与控制开销。所有策略使用task-id/seed绑定的相同**外生**服务样本。

排队是策略内生结果，必须由resource争用产生，不能给某策略一份预先去掉contention的trace。cache/DRAM timing若受访问顺序影响，不能靠固定每task duration公平建模，需transaction-level模型或显式标注近似边界。

比较“更多buffer”与“新增动态硬件”时必须同时报SRAM增量。R2的少复用更快只是速度比较，若没有容量成本，不构成等预算胜出。

## 4. 统计与指标解释

主要报告配对test seed上的latency reduction = 1−T_X/T_A；speedup=T_A/T_X，两者不能混写。平均比值与均值之比可能不同，文件必须声明。报告均值、分布范围或配对95%CI，给正/负/零结果和seed数；多场景筛选后的最佳值不能作为总体结论。

latency、每engine/resource busy fraction、task-time分解、scheduler busy、ready occupancy、wakeup updates/bytes、决策频率、metadata bytes和estimated state bits一起输出。task-time stall可重叠于其他task执行，不能将它的和写成makespan分解。

有限DAG的Ntasks/makespan只是任务完成率；只有稳定任务规模和重复请求注入、warmup之后的统计，才是模型requests/s或tokens/s。critical-path dilation用真实duration下纯DAG最长路径作分母，不能把预测误差混进去。

## 5. 证伪闸门

先检查oracle头寸：若同资源小图的clairvoyant exact也只有很小收益，不设计大调度器。再检查强静态差距是否主要来自可修复的offline优化。然后收费：issue/wakeup/window/communication成本逐步加入，画收益与成本的Pareto边界。

继续条件采用预注册的工程阈值作研究筛选而非定理：代表motif上收费后的latency improvement至少5%且配对区间不跨0；更复杂C相对B至少额外3%才有继续理由；机制应在非挑选的case上没有不可接受的回退。5%/3%均可由目标设备成本预算修改，但修改必须记录且重新跑全套。

缺少真实trace、真实workload graph、RTL PPA时，不确认“适合论文/专利”。当前可得的是存在性证明、负结果、机制筛选，以及下一轮需要采集什么证据。
