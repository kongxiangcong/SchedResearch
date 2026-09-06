# R6 核验与修正记录

保留 experiment_plan.md 的实验前原字节；原SHA256记录在每次probe receipt中。

1. 预登记 E1 的“尚未授权其具体实现合同”措辞不准确：用户已授权推进。本意是目标kernel、compiler候选和测量合同尚未实例化/冻结，属于技术与证据缺口，无需再次请求开始许可。继续所有可独立核验的工作。
2. 首次按 `NPU` 子串筛选Windows PnP会包含 `Input` 设备。host_inventory.json保存了原始筛选候选，唯一对应NPU的行是 `AMD IPU Device`，并由精确设备名的npu_driver及XRT枚举交叉确认；HID输入设备不计NPU。
3. vendor verify 的PASSED不等同数值验收。精确XRT源码显示只提交/等待，且catch后的failed状态可能被末尾passed覆盖；必须检查Error日志。本次原始输出无Error，但结论仍限定launch/wait smoke。
4. vendor df-bw 实际执行一个1GiB input/output搬运并比较268435456个int32。打印的 `GS/s` 由 `1 / host_elapsed_seconds` 计算，分子来自1GiB常量；不是每秒十亿sample，也不是实测AXI bytes。保留原标签，另解释其算式。该实测不能校准R5的256B请求、RF/SRAM bank、outstanding、return buffer或MAC吞吐。
5. E0到此未具备固定输入/地址、运行中频率、compute-active/request观测和strong-static kernel。停止性能归因与动态机制实验；工具合同校验、来源容量推导和独立审计继续推进。缺失数据不能作为H1被否定的证据。
