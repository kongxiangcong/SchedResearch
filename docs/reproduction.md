# 目录迁移与复现

## 路径映射

本次在 `a9c885f` 的文档归档基础上完成实验工作区迁移；下表以原始 `e71cc04` 布局为参照。前一次归档说明保存在 [历史布局说明](previous-archive-layout.md)，其中的根目录兼容链接已由本次统一入口取代。

| 旧路径 | 新路径 |
| --- | --- |
| `r1-base/`、`r2-ooo-npu/`、`r3/` … `r11/` | `research/` 下同名目录 |
| `sim/`、`experiments/`、`tests/` | `research/` 下同名目录 |
| `analysis/`、`literature/`、`research_progress.md` | `research/` 下同名路径 |
| `README.md` | `research/README.md`，历史正文原样保留 |
| `.gitignore` | `research/.gitignore`，实验忽略规则与白名单原样保留 |
| `zhihu_da-zhi-ruo-yu-64-38/` | `references/zhihu_da-zhi-ruo-yu-64-38/` |

R3–R11、共用实验代码及第三方来源文件按原始内容迁移，没有重算历史 manifest 或改写实验结论。R2 审计脚本恢复 `e71cc04` 的工作区定位方式，适应整体迁移；保留 `a9c885f` 已有的 R2 来源哈希修正。旧脚本中的工作区相对路径、源码 hash 及内部 Markdown 链接继续使用原语义。外部指向旧 GitHub `main` 文件路径的书签需按上表更新；固定历史提交链接不受影响。

## 运行约定

从项目根使用 `python run.py`，后面接原 Python 命令的参数。启动器使用当前 Python 解释器，设置 UTF-8、禁写字节码、工作目录及工作区导入路径，并传回子进程退出码。

```bash
# 基础与冻结快照测试
python run.py -m unittest discover -s tests -v
python run.py -m unittest discover -s r4/r3_snapshot/tests -v

# R4 最小实验；会写入 research/experiments/results/r4/
python run.py -m r4.run --limit 1 --seeds 2 --search-budget 16

# R11 完整复现顺序
python run.py r11/numerical.py
python run.py -m r11.run_experiments
python run.py r11/independent_audit.py
```

传入的相对输入、输出路径都以 `research/` 为基准。启动器不隔离结果目录：重跑可能覆盖该轮本地结果和已跟踪的紧凑汇总，运行前应保存需要保留的结果，运行后检查 `git status`。

如需手动运行，先进入 `research/`，以 `python -B -X utf8 -m 包.模块` 执行模块。不要在项目根直接使用旧的 `python -m r4.run`；根目录不创建旧路径别名或符号链接。

## 环境与证据边界

此前本环境的复现版本为 Python 3.12.13、NumPy 2.3.5、Matplotlib 3.10.8；这是已测环境记录，不是对其他版本的兼容性承诺。基础模拟器仅需标准库，数值/绘图命令按需安装 NumPy、Matplotlib。R6/R7 的设备工具有独立要求，遵循该轮说明。

Git 只分发源码、合同、文档和审核过的紧凑结果。缺少被忽略的 trace/samples 时，审计报错不等于性能结论被推翻，也不能跳过审计宣称复现通过。应先运行对应生成入口，再运行独立审计。

后续轮次放入 `research/r12/` 等目录；跨轮分析放入 `research/analysis/`，外部阅读导出放入 `references/`。冻结快照与第三方源码继续原样保存。若以后拆分共用 Python 包，需要独立迁移方案和实验重新登记，避免破坏历史证据链。

## 本次迁移验证

- 共用测试 14/14、R3 冻结快照测试 14/14 通过。
- R2 的 21 个表格点复现；R4 最小配置 12 次执行，B2 为 −7.913%。
- R11：76 组 prefill、4 组 decode 数值检查及 122 条 trace 独立审计通过；quiet −0.0157%，background A/B −0.5992%/−0.6060%。
- 本机生成过程出现 3 个截断 gzip trace，按相同图、seed 和条件重新生成，核对 elapsed 与汇总一致后通过审计；没有修改被冻结的生成器。
- 新导航链接、工作区外调用、失败退出码传递、结果忽略规则与紧凑结果白名单均已检查。

重跑产生的已跟踪结果差异未纳入本次目录变更。
