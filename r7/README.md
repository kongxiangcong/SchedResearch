# R7 executable Phoenix access

[实验报告](experiment_report.md) · [测量摘要](measurement_summary.json) · [独立红队](redteam_report.md) · [科研进度](../research_progress.md)

4 次固定 1 GiB copy、4 次 INT8 单 GEMM 在真实 Phoenix 上全部数值通过。已获得可重编译 host runner；device binary 是冻结的预构建资产。当前限于 host elapsed 功能/能力筛查，尚未通过设备计量或机制门。

## 不运行设备的复核

在 `D:\dsh-proj\SchedResarch`：

```powershell
python -X utf8 -B r7/check_integrity.py
python -X utf8 -B r7/summarize_results.py
```

前者按快照验证 R4/R5/R6/R7；后者核验真实回执/文件并确定性重写同内容 summary。不要运行旧 R6 verifier 后改 manifest 消除根表演进；旧 verifier 只理解旧 live-root 关系。

## 复用入口

`sdk/build_copy.cmd` 与 `sdk/build_compute.cmd` 使用已安装 MSVC、局部 headers/import library 构建。构建/源码/EXE hash 见 `sdk/build_receipt.json`；重新构建需保存新 receipt，不覆盖已冻结的本轮证据。

`run_calibration.py` 是此次已执行的封装：拒绝陈旧 source/EXE pair，要求 phase=repeat 的 initial 已数值通过；运行器每次最多 10 次，wait2 上限 30s，子进程 90s。已有 `copy_initial`/`copy_repeat`/`compute_initial`/`compute_repeat` evidence 路径拒绝覆盖，**直接重用这些命令会报已有目录**。下一轮应新建目录/回执名并冻结自己的合同，不删除已有 evidence。

新执行只能在明确的 xclbin/指令/input/layout 合同下进行。现有 GEMM 仅 `M=1,K=N=2048,INT8×INT8→INT32`；不要给它任意缩 BO 或替换 BF16 文件。

来源检索 `sources/kernel_access/*_repo` 是明确排除的 git 下载缓存；权威来源/fixture 在其旁的独立文件与 source_manifest 中。其余 artifact 边界由 R7 manifest 记录；不修改 R1–R6。
