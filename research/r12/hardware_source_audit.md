# R12 Wormhole B0 硬件来源与事件语义审计

日期：2026-09-08。证据等级：固定官方原文、官方图生成源码核查，以及据此提出的离线反例；没有设备运行、周期仿真或性能测量。本文件不改变任何冻结历史报告。对主图的可执行验证状态以本轮实际结果文件为准，不能从本审计推导 G0 已完成。

ISA 来源固定为 `tenstorrent/tt-isa-documentation@5287a62727350bcef35f7b411d1b8a706172ec4c`。本次已对 `research/r12/deps/tt-isa-documentation` 执行 `git rev-parse HEAD`，结果与合同一致；先用公开 GitHub/raw 页面核验，再使用本地固定源码补全阅读与核对行号。下列行号均为 Git blob 的真实行号，不使用网页转换后的行号。

## 阅读覆盖和适用范围

| 材料 | 本次阅读范围 | 用途与边界 |
|---|---|---|
| `SchedResearch_reassessment_evidence_20260907/proposal_contract.md` | 全文 | H0/H1/H2、三类见证、小图与资格门；不把任意硬件差异算为 H1 |
| 同目录 `bound_witness.py` | 全文 | 仅 NoC0 非绕回 request-link 字节下界；没有 ACK/read-response/NIU/controller/consumer |
| 同目录 `evidence_ledger.md` | 全文 | 追溯上轮来源与明确缺口；历史阅读/复算不冒充本次实验 |
| [NoC/README.md][noc] | 全文 1–68 | packet/flit、双 NoC、VC、公开吞吐上限；非完整运行时间模型 |
| [NoC/RoutingPaths.md][routing] | 全文 1–63 | request/response/ACK 单播路径、共享链路、cut-through |
| [NoC/Coordinates.md][coordinates] | 全文 1–73 | raw/translated 分离；harvest 表只有示例意义 |
| [NoC/Ordering.md][ordering] | 全文 1–48 | 数据、请求及响应顺序、跨 NoC 等待义务 |
| [NoC/Counters.md][counters] | 全文 1–173 | 源读取、目标可见、ACK、ID 计数器与自动拆包 |
| [NoC/MemoryMap.md][memorymap] | 全文 1–268 | 发起器、地址角色、通知、端点识别、翻译开关 |
| [NoC/Alignment.md][alignment] | 全文 1–65 | 本轮限定对齐单包普通读写的合法性 |
| [DRAMTile/README.md][dram] | 1–70、100–157；71–99 表格部分读取 | endpoint/channel 别名、缓冲规格、DRAM 排序；厂商性能表不作为本轮校准 |
| [BabyRISCV/MemoryOrdering.md][riscv-ordering] | 全文 1–148 | 原生发起、轮询、发布/消费的本地顺序义务 |
| [Diagrams/Src/NoC.lua][diagram-source] | 1–190；后部按坐标公式检索 | 官方 tile map 与单播路径算法；未执行 Lua 图生成 |
| [TT-Metal memory guide][metal-memory] | DRAM tiles、memory access 与 placement 相关正文 | `latest` 在线旁证，2026-09-08 核验；不充当固定 tt-metal kernel 实现 |

## 可直接冻结的结构事实

以 NoC0 raw 坐标作为**记录物理位置的规范坐标** `p=(x,y)`：`0≤x<10`，`0≤y<12`。这不是把 NoC1 的寄存器地址也写成 NoC0 坐标。同一 tile 的 NoC1 raw 地址为 `(9-x,11-y)`。在规范物理坐标中，NoC0 按 `x+1 mod 10` 后 `y+1 mod 12`；NoC1 按 `y-1 mod 12` 后 `x-1 mod 10`。在 NoC1 自己的 raw 坐标中，则是先递增 y、再递增 x。两者均保留 torus 绕回，不能把四个活动 tile 缩成 2×2 网络。[Coordinates 7–25][coordinates]、[MemoryMap 183–192][memorymap]、[RoutingPaths 11–41][routing]、[官方路径代码 82–115][diagram-source]。

上述转换由坐标定义和 10×12 尺寸推得。固件 translated 坐标另有映射表；文档的 Y 表假定特定 harvested rows，不能用来宣布某张卡的可用 tile。文档允许 0–15 通过 identity 表继续作为 raw 坐标，但真实运行必须核验已启用的翻译方案及 descriptor。[Coordinates 19–65][coordinates]

官方图源码给出的 DRAM endpoint 分组如下。每行列出三个物理 tile，每个 tile 在两条 NoC 各有一个 NIU；总计六个 NIU 别名访问同一组 GDDR6 地址空间。[图源码 12–25][diagram-source]、[NoC README 15][noc]

| group | NoC0 raw 物理坐标 |
|---|---|
| D0 | `(0,0)`, `(0,1)`, `(0,11)` |
| D1 | `(0,5)`, `(0,6)`, `(0,7)` |
| D2 | `(5,0)`, `(5,1)`, `(5,11)` |
| D3 | `(5,2)`, `(5,9)`, `(5,10)` |
| D4 | `(5,3)`, `(5,4)`, `(5,8)` |
| D5 | `(5,5)`, `(5,6)`, `(5,7)` |

**共享 group 不能再被简化成任意的一个串行 server。** 固定 ISA 每组三 tile 对应两个 1 GiB channel，地址 `[0,0x40000000)` 与 `[0x40000000,0x80000000)` 分别选择 channel 0/1；固定 ISA 使用每 channel 的 Controller/PHY 表述，而 TT-Metal 教程把整组称为一个 DRAM controller。账本应同时记录 `group` 和 `channel`。同 group、同 channel、同地址的不同 endpoint 是别名，绝不能复制容量或当作独立带宽；同 group、不同 channel 则不得无依据强行完全串行。[DRAM 3–41][dram]、[TT-Metal DRAM tiles][metal-memory]

因此，第二类见证应至少区分：(a) 同 group/同 channel 的两个 endpoint；(b) 不同 group/相同 channel index；(c) 同 group/不同 channel 的对照。仅 (a) 与 (b) 是原始“共享/分离 controller”见证的清楚比较，且各比较需固定真实数据位置和字节量。

## Packet 账本与顺序模型

普通 read：发起 NIU → remote source 的请求为一个 header flit；remote source → return destination 的响应承载数据。普通 non-inline write：发起 NIU 从自己的 `NOC_TARG_ADDR` 取数据，向 `NOC_RET_ADDR` 发含数据的请求；nonposted ACK 回到 `NOC_TARG_ADDR` 中的坐标。inline write 则直接写 `NOC_TARG_ADDR`，ACK 回发起 NIU。这种地址角色差异必须由 lowering 显式处理。[MemoryMap 73–91][memorymap]

单包最多 8192 B，flit 为 32 B。对本轮 32 B 对齐且 payload 为 32 B 整数倍的普通读写，含数据 packet 的 flit 数为 `1+payload/32`；read request 和 write ACK 各一个 flit。普通 write、ACK 与 read response 都必须独立产生路径和 NIU 注入/接收占用记录。响应仍走该 NoC 自身的单向路径，**不沿请求边倒走**；换 NoC 不能在事务中把 ACK 免费切换到另一条网络。[NoC README 3、68][noc]、[RoutingPaths 17、41][routing]

链路相交应按 `(NoC, directed port/link)` 统计；同 router 的不同出口并不自动互斥。路由器采用 cut-through，逐包每跳完全收完再发的模型会引入无依据限制。字节服务下界只能用于成本粗筛，不能把拥塞组合当作正确性非法组合删除。[RoutingPaths 59–63][routing]

单个 packet 的 L1 读写以 16 B 原子单元作用，整体 packet 不原子；两个接收写 stream 各自有序不意味着整个范围已更新。默认 VC 可以带来重排；固定 request VC 只建立有条件的请求顺序，响应/ACK 仍可能重排。L1 数据写之后的 MMIO 通知即使走同一 VC，也可能先于数据实际写完。[Ordering 5–28][ordering]

DRAM 的不同 endpoint NIU 之间没有请求排序保证；相同 NIU 且相同到达 VC 才有文档列出的部分排序。即便该条件下 write→read 被目的 NIU 正确排序，也不能把它扩展成不同 endpoint/NoC 间的全局顺序。[DRAM 145–157][dram]

## 三种完成与可观测事件

以下表以对齐、单包、non-inline、nonposted 的 L1→L1 write 为主要准入子集。`id` 是发起 NIU 上的 counter scope，不是无限多的单请求 token。

| 事件 | 硬件观测 | 能证明什么 | 不能证明什么 |
|---|---|---|---|
| command 提交/首跳 VC 分配 | `NOC_CMD_CTRL` 写 1 / 后归 0 | command 已进入协议 / 发起器可复用 | 源缓冲已读完、目标可见 |
| “sent”计数增量 | `*_WR_REQ_SENT`, `*_WR_DATA_WORD_SENT` | 文档定义的发送阶段已达 | 源 L1 读取完成；该增量发生在其之前 |
| 全部源读取完成 | `WRITE_REQS_OUTGOING_ID(id)` 相应减量 | 满足全部 source last-reader 后可复用源范围 | 目标已经可消费 |
| 最后数据 flit 到达目标 NIU | `*_WR_REQ_RECEIVED` | 网络包已到 NIU | 目标 L1 全部写完 |
| 目标写完/生成 ACK | `SLV_WR_ACK_SENT` | 目标写入已完成 | 发起方已收到完成信息 |
| ACK 抵达回源 NIU | `MST_WR_ACK_RECEIVED`；`REQS_OUTSTANDING_ID(id)` 减量 | 对该正确 scope，远端写完已获确认 | 某个任意子集一定完成、消费者已读完 |

表中计数时点逐一来自 [Counters 119–150][counters]；`CMD_CTRL` 含义来自 [MemoryMap 148–156][memorymap]。Read 在 return NIU 写完 L1 后才更新 `MST_RD_RESP_RECEIVED` 与 outstanding；不能把 read request sent 当作 load 完成。[Counters 71–95][counters]

同 `id` 的多个事务共享 8 bit 计数器。等待 outstanding 清零可覆盖该 scope 所有返回，不能凭一个总 ACK 增量认定“先发的那一个”已完成。若另一个 kernel/NoC overlay 也改同计数器，需要隔离或扩展合同；不能忽略它。posted write 没有期待 ACK 的 outstanding 增量，观察该计数器为零不证明目标可见。自动拆包会一次加入多个计数，且约束整个 NIU 的后续发起器操作；本轮最小见证先手工限定单包，不悄悄依赖自动拆包。[Counters 23–24、121–173][counters]、[Ordering 18][ordering]

“notification”还应分类：`MEM_RD_DROP_ACK` 涉及发送侧 overlay 通知；`DeliverToReceiverOverlay` 涉及接收侧 overlay packet 投递；另发 L1/MMIO/semaphore 通知则是独立事务。这三个不是同一完成事件。本次所读接口不足以把接收 overlay 投递自动当作整个 payload 对消费核的 acquire，最小核验应关闭该功能并使用可证明的 ACK→显式通知关系。[MemoryMap 63、130–141][memorymap]

## 两链、两个复用 slot 的安全等待建议

这是据上述硬件规则提出的**后端实现义务**，不是已执行的 tt-metal kernel。原生 API 的名称、编译器 barriers 与指令序列需在固定 tt-metal revision 后逐项核对。

1. 明确两个可复用 slot 各自的 `(tile, address, bytes)`，并另列所有固定 staging/output/consumer buffer。若使用“每个 source 两个 + 每个 destination 两个”，必须按真实总数记账，不能继续称为总计两个 slot。每条链至少运行两个 epoch，让复用真正触发。
2. `load→compute`：load 的 return destination 完成获得后才向 compute 发布输入；compute 的全部源写入已发布后才允许 NIU 读取。每个 compute→peer transfer 取得目标 slot credit 后再发起。
3. peer write 使用 nonposted 单播，响应地址留在原发起 NIU。不同可独立等待的流占用不同 transaction ID；同 id 同时只容纳合同登记的请求集合。两链在各自 NIU 上独立推进，不加入无因果关系的全局 wait。
4. 发起 peer write 后，等待其 `OUTGOING_ID` 归零允许释放源 slot。可以在 ACK 返回前覆盖该源范围，但不得破坏尚存的其他 source reader，也不得过早把该 id 分配给下一 epoch 后声称是在等待旧 epoch。下一 epoch 的 load 必须在该 guard 后才 **issue**；只限制下一 load 的最终 visible 会允许其提前部分写入旧源 slot。
5. 在相应 `OUTSTANDING_ID` 归零、确认该 peer payload 目标可见之后，才另发带 epoch 标识的消费者通知。notification 到达前，消费者不得读目标；通知观察到后，本地数据访问必须具备正确的 RISC-V 顺序。
6. consumer 全部读取结束后才返还目标 slot credit。ACK 是写完成，不是 consumer last-reader；源 slot 和目标 slot 的 release 不能合并。最终输出及通知在模块退出前要各自按合同完成。

第 5 步是保守但可解释的 P0 原生实现，不应作为 P1 的独占能力。将其 wait 从“所有请求”缩为“本 payload 的独立 ID scope”同样应先给 P0。后续可尝试依赖硬件明示有序路径减少等待，但需先给出适用内存类型、NIU、VC 和重排证明，不能只凭软件 issue 顺序。

还有一项会直接影响上述所有步骤：Baby RISCV 的 `fence` 为 no-op。发布 L1、写 CMD、读 counter、发通知和消费通知后的访存不能用泛型 fence 糊成一个顺序边。文档提供同地址读回及消费 load 结果等办法；发起 CMD 后首次读 counter 需先读回 CMD。最终应审查已有 tt-metal 原语的生成代码，而非在研究 checker 中假定 C++ 语句天然序列化。[BabyRISCV 45–68、124–148][riscv-ordering]、[Counters 43][counters]

## 用于否定错误 checker 的最小反例

下列是文档允许的事件前缀或资源别名推论，**不是实际采集的 hardware trace**。状态空间 checker 必须接受允许的重排，同时拒绝依赖它的非法消费/复用。

| ID | 错误假定 | 最小反例或断言 |
|---|---|---|
| CE1 | `CMD_CTRL=0` 即可覆盖源 | command accepted → 覆写 source → NIU 后读；可读到新 epoch |
| CE2 | write sent counter 等于 source last-read | sent 增量 → 源覆写 → remaining source read；sent 与读取结束之间必须允许空隙 |
| CE3 | outgoing 清零等于目标可见 | source read done → consumer read → destination writes done；早读非法 |
| CE4 | 最后 flit 到 NIU 等于内存完成 | destination packet received → consumer read → remaining L1 writes；早读非法 |
| CE5 | 非 posted 后通知按 issue 次序可见 | payload write → MMIO notify；notify 先处理，数据仍未完成；同 static VC 也不能消除此反例 |
| CE6 | 先发 A，首个 ACK 就完成 A | issue A,B → ACK B → consumer A；不同 scope 或全 scope wait 才能区分 |
| CE7 | posted 的 outstanding=0证明远端写完 | issue posted；该计数未增加即为零，payload 仍在途 |
| CE8 | 两个 DRAM endpoint 即两份资源 | D0 `(0,0)` 与 `(0,1)` 同地址写读指向同一 channel 字节；不许复制容量/值 |
| CE9 | 同 group 等于单串行 channel | D0 address 0 与 `0x40000000` 落不同 channel；资源账本应保留区别，不添加未经证实的全串行边 |
| CE10 | ACK 使用反向边 | NoC0 `(1,1)→(2,1)` 请求一 hop，返回 `(2,1)→(1,1)` 必須沿 +x 绕回九 hop；不是一 hop 左行 |
| CE11 | NoC1 raw 仍按物理方向减坐标 | p `(3,2)→(1,1)` 在 NoC1 raw 是 `(6,9)→(8,10)`，先 y+1 后 x+2；方向、空间不可混合 |
| CE12 | 源释放与目标 credit 相同 | write ACK 返回后 consumer 尚未完成；复写目标 slot 会破坏 consumer，不能凭 ACK返credit |
| CE13 | RISC-V fence强制完成 | store L1 → fence → CMD/通知；fence无语义效力，checker应要求独立后端证据 |

CE1–7 来自上文事件与排序规则；CE8–11 是结构/路由规则的直接推论；CE12 是应用 buffer 生命周期约束；CE13 对应固定 RISCV ISA 的明示行为。没有一个反例证明 P1 比强 P0 更快，也没有一个构成新增 runtime 的必要性证明。

## 已知参数、仍未知参数和准入清单

不能继续笼统写“router buffer 未知”：固定文档明确每 inbound port 2 KiB，其中各 VC 保底 32 B，剩余 1.5 KiB 为共享池，每 VC 最多再取 480 B。文档也给出链路 1 flit/cycle、router hop 9 cycles、NIU 两端约 5 cycles，以及最多 12 request/4 response 同时由接收 NIU 处理。[DRAM 70][dram]、[NoC README 60–66][noc]、[Ordering 20][ordering]。这些参数可以登记，**本轮不据此拼成未经校准的周期模型**。

| 未知/未固定项 | 性能或 native 准入前需要的证据 |
|---|---|
| 板卡 SKU、ASIC 数、B0 revision、harvest mask | 设备枚举与实际 SoC descriptor；四个活动 tile 与选定 DRAM endpoint 可用 |
| 固件、driver、tt-metal/compiler/SoC descriptor 版本 | 固定 commit/version/hash；实际 boot/配置记录 |
| AI/AXI/GDDR clocks、功耗模式、温度/降频 | 实机配置与重复测量条件；不能把典型 12 GT/s 当作实测 |
| 每 NIU 内部数据队列/AXI 排队、VC credit 返回时序及共享池仲裁细节 | 官方补充合同或实测校准；四个 command initiator 不等于四请求在途上限 |
| DRAM bank/address mapping、refresh、read/write turnaround 和控制器调度 | 固定通道内微基准与公开依据；不能凭 group alias 发明调度器 |
| 原生 scoped wait、ID 所有权与 counter wrap/overflow | 审核固定 tt-metal primitive；禁止其他使用者污染 scope |
| L1/CB publication、local last-reader、通知 acquire | 固定后端原语与实际指令；尤其核验 Baby RISCV 读回/依赖消费 |
| peer/DRAM/最终输出完整可见与时间戳边界 | read/write/notification 三者分开验证；最终 elapsed 覆盖输出可见 |
| 完整 MLP 数值方式、归约树、内存地址及 buffer 容量 | 按 proposal_contract 数值准入；小整数/FP64离线见证不能替代 BF16/FP32 native 准入 |

当前可以开展完整拓扑、packet/NIU/link/channel 账本、合法事件部分序、buffer epoch/credit 守恒及反例测试。实际硬件、原生 kernel 与时序校准未完成前，状态最多是 G0 的离线子项进展；不能宣称 G0/G1/G2、最优性排序反转、3%收益或新增硬件必要性已成立。

相对上轮证据包，本次补充读到的 `DRAMTile/README.md:70` 缩小了“队列/缓冲未知”的范围：router inbound buffer 的大小与共享分配上限已有公开参数。保持原证据包冻结，在 R12 登记这一补充；NIU/AXI 排队细节、credit 时序与实际控制器校准仍未完成。

## 本次独立审查执行结果

独立审查 `qualification.py` 时发现两项会影响后续硬件迁移的错误，并由主实现代理修正：

- 源 slot 复用最初只约束下一 load 的 `load_visible`，现提前到 `load_issue`，避免正在执行的下一 DMA 在最终完成前已部分覆盖旧源。
- 同 channel 的两个别名 endpoint 最初对两条数值不同的链使用同地址；现加链级地址偏移，保证候选改变 endpoint/group/channel 时仍是相同逻辑输入及独立字节范围。

修正后实际运行 `python -X utf8 -B research/r12/independent_checks.py`：PASS。结果保存至 `artifacts/independent_checks.json`。检查使用与主实现不同的坐标表达（各 NoC raw 空间中正向构造，再回到规范物理坐标）比较 28,800 条全端点路径；独立核对 read response 与 write ACK 的绕回流量；检查 96 个候选的输入地址别名；对安全 DAG 的 56 个事件分别优先生成合法拓扑序并复放标量数值。专门构造了下一 epoch compute 早于上一 epoch ACK 的合法执行，数值仍正确，确认修正没有把源复用过度约束成等待远端 ACK。

56 次数值复放不是穷举全部拓扑序；全部拓扑序上的已登记 happens-before 义务由 DAG 可达性检查支持，仍以图内边的后端可实现性为前提。当前未见上述离线范围内剩余的路径方向、read/ACK 角色或标量 span 复用错误。并未验证 NIU counter 寄存器状态机、16 B 部分读写、credit 实际容量与活性；这几项仍是 native G0 的资格缺口。

关键原文可直接定位：[源读取/目标可见/ACK 时点](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/Counters.md#L119-L150)、[请求地址角色](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/MemoryMap.md#L73-L91)、[L1→MMIO 与跨 NoC 顺序](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/Ordering.md#L18-L32)、[公开 router buffer 参数](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/DRAMTile/README.md#L64-L70)、[Baby RISCV fence 与替代顺序方法](https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/TensixTile/BabyRISCV/MemoryOrdering.md#L45-L68)。

[noc]: https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/README.md
[routing]: https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/RoutingPaths.md
[coordinates]: https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/Coordinates.md
[ordering]: https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/Ordering.md
[counters]: https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/Counters.md
[memorymap]: https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/MemoryMap.md
[alignment]: https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/NoC/Alignment.md
[dram]: https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/DRAMTile/README.md
[riscv-ordering]: https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/WormholeB0/TensixTile/BabyRISCV/MemoryOrdering.md
[diagram-source]: https://github.com/tenstorrent/tt-isa-documentation/blob/5287a62727350bcef35f7b411d1b8a706172ec4c/Diagrams/Src/NoC.lua
[metal-memory]: https://docs.tenstorrent.com/tt-metal/latest/tt-metalium/tt_metal/advanced_topics/memory_for_kernel_developers.html
