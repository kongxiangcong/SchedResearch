# R13 服务状态机接口 v1

2026-09-08，在任何 R13 性能比较前登记。此文件细化 proposal_contract.md 的实现接口，不替代 M0/M1/M2 门。首版用整数 tick（36 tick/model cycle），无逐 flit 浮点取整。通用服务状态机同时推进网络、内存与计算；独立检查器直接按 tick 扫描同一纯数据输入，不导入主执行器。

## 纯数据输入

`spec` 是 JSON 可序列化 dict：

- `buffers`: 名称到 `{capacity: int|null, credit_delay: int}`。capacity 为 null 的输入队列仅保存已驻留内存的工作描述，不存复制出来的数据。有限 buffer 容量按 flit 计。共享池成员关系只由groups.members定义。
- `groups`: 名称到 `{members: [buffer_id], guaranteed: 1, shared: 48, per_member: 16}`。router 每 inbound port 的16个VC共享一组。`sum(max(used(q)-guaranteed,0)) <= shared`，各VC不超过16，未建队列的VC也保留其独占保底，不能借出。
- `jobs`: 每项 `{id, packet, flit, tail, release, deps: [op_id], ops: [...]}`。一个job是一个最多32B的flit或具名compute/control动作；`release` 是最早绝对tick，依赖都以指定操作完成为准。每个操作 ID 为 `job_id:op_index`。
- `ops`: 每项 `{queue, resources: {resource_id: initiation_interval}, latency, lock?: str, tag?: str}`。本操作从queue取走job；同时占用所有所列资源各自的启动间隔，latency后进入下一操作的queue或完成。无资源操作仍走相同逻辑，允许零latency。资源/latency是非负整数，非空资源的interval须为正。
- `tie_break`: `ascending` 或 `descending`，仅用于同刻的确定性仲裁顺序对照。

## 每个时间点的执行

先批量处理到期操作完成、入队、credit返回与wire-VC锁释放，再将全部依赖满足的初始job按稳定ID顺序入队。初始job只有成功取得首queue的credit才进入；release不等于已经读出payload。入队顺序为 `(arrival_time, job_id)`，同queue严格FIFO。零时间逻辑反复达固定点后才跳到下一个正时间事件。

一次操作启动必须满足：自己位于所在queue头部；全部资源都可启动；下一queue有credit可预留；wire-VC锁为空或属于本packet。调度在全部当前可行队列头中按 `(该queue上次得到服务的tick, queue_id, job_id)` 选择，初始上次服务为-1；descending仅反转字符串打平顺序。每次选择后重新收集候选。这是显式的最久未获服务优先仲裁假设，不是厂商仲裁声明。相同时间的所有已到期完成先于任何新仲裁。

启动时立即为下一queue预留容量，将当前queue从occupied变为cooling；cooling在该queue的credit_delay之后才变为可用credit。每个有限queue持续满足 `used = reserved + occupied + cooling <= capacity`，并同时检查router共享池。此处cooling是上游尚未看到的已释放容量，不能当成物理占有。下游实际空间为reserved+occupied，发送可用空间还受cooling约束。

`lock` 标识同一输出链路上的具体VC（class/dateline/buddy）。第一次启动时归本packet独占；尾flit**完成这条链路传播**后释放。锁不得跨整个路径一次占有。每条网络link的interval固定36tick，latency为router-link324tick或NIU邻接180tick。每flit先到下一router即可继续，不等待整packet。

操作完成与credit归还均记录；剩余未完成工作却没有下一事件、没有可行动作时返回deadlock并给等待队列，不冒称目标硬件死锁。成功状态为ok，quiescent包括全部credit归还；deadlock时quiescent必须为null，不给没有清空的执行编造有限清空时间，可另报stopped_at诊断。主执行器输出 `operations[{id,start,end,queue,resources,lock}]`、`job_end`、`quiescent`、`buffer_peaks`、`resource_launches`、`status`。独立tick检查器输出相同核心字段；它可使用另一个内部组织，但不得复用主执行器推进或成本计算代码。

## 边界

该接口本身不证明源/目标语义、地址与数值正确。拓扑/事务/DFG构建器必须生成真实request/response/ACK/notification、源16B读取/目标写入与复用义务；独立的轨迹数据审计再验证这些操作。尚未接通的部分不能靠通用引擎测试签成完整M0。
