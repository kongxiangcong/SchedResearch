# R3暂定架构提案：先保留测量边界

日期：2026-09-05。**尚未收敛为最终架构，也没有足够证据建议设计大而全OoO NPU。** 当前保留一个可替换、可收费的latency-tolerant task-dispatch边界作为研究工具。

## 1. 当前候选最小通路

```text
Compiler: graph + binding + storage safety + static schedule candidates
                             ↓
                  typed execution contract
                             ↓
         bounded descriptor admission (entries AND bytes)
                             ↓
             dependency count + legal-ready selection
                             ↓
        static priority + resource availability arbitration
                             ↓
          independent MXU / VPU / DMA / transfer engines
                             ↓
              output-visible completion / notification
```

必需结构只有被当前语义要求的resident状态、依赖就绪、资源占用和完成通知。固定binding/address并保留显式alias顺序，因此当前不需要register rename；无故障单次DAG未要求完整CPU式退休/恢复ROB，且依赖由compiler给出，无需硬件全图analysis。这些是本轮语义边界的结果，不能从“不推测”单独推出“不需要重命名”。资源需求用明确bundle编码；发布给远端的event必须晚于数据可读，而非DMA issue。

这一通路已有大量先例。它是实验基准，并非待宣称的新机制。[先例红队](../analysis/novelty_redteam.md)

## 2. 实验支持了什么

四任务反例证明仅completion信息可以让一个合法局部dispatcher优于所有固定顺序；W3达到140，W4无额外收益。但同例新增每task 8cycle派发成本便倒退4%。因此“state不多”不是充分论据，调度时延与task粒度必须成对设计。

更大motif里B的收益小且经常为负，C额外age/pressure没有稳定价值。暂不保留C，不加CAM、ROB或全局迁移来追逐未解释的分数。多chip通信-only的负例还表明，通信不确定性本身也不保证机会。

## 3. 本轮还不是minimum-total-state硬件

当前resident entry/bytes和issue/wakeup吞吐有限，但为了晚admission，整个有限DAG的completed/delivered history与待发通知保留到结束。其规模与N/E相关，成本模型显式计入。分域scheduler只是服务端口和窗口分片，仍共享全图元数据；无端到端credit、epoch回绕或分布式死锁证明。

下一步真正可能有价值的硬件问题是：**compiler能否给出有限前沿/事件生命周期信息，使已完成记录安全回收，同时在受限通知带宽下保持主要调度机会？** 这是待研究候选，不是“本轮已实现bounded-state”的包装。

需对比：全图event-history基线；compiler定义区域边界后局部窗口；仅固定FIFO+self-timed同步；允许跨区域少量命名事件。每种都计descriptor静态字节、最大active events、回收证明、lost-wakeup防护和队列反压，不能只报resident task table。

## 4. 架构主线如何保持

编译器负责提供硬件可消费的合法执行空间和事件生命周期，不接管runtime完成判断。研究指标是这个接口能使硬件少维护多少状态、少发送多少唤醒、减少多少等待。编译器memory allocation只是约束条件之一，而非把论文自动改成allocator工作。

研究切入点的排序：先真实task完成方差/ready inversion与资源利用率；再识别strong-static残余bubble；然后最小dynamic-state/事件带宽设计；最后才确定core/cluster/chip层次。在前两步没有显著可恢复空间时，应停止新增硬件。

## 5. 收敛闸门

1. 真实LLM/DiT导出图中存在独立分支和可绕过等待，fusion/batching强基线后仍存在。
2. 用真实或详细DRAM/NoC闭环时序，B在独立test集合仍明显胜更强静态。
3. 限制task/event/history/queue总state后，收益仍可支付新增dispatch/wakeup成本。
4. 相对TaskStream/ASPEN/HwSch/LATTICE有清楚且可测的delta；不是仅把对象换成NPU。
5. 用RTL合成或可信微结构模型给出面积、Fmax、能量/控制成本，才讨论论文主张或具体专利机制。

当前只完成部分第1步的合成存在性。后续是否进入硬件提案取决于证据，而非原先“乱序执行”的名称。
