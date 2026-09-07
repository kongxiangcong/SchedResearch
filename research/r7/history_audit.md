# R7 历史证据保存与继承审计

2026-09-05进行只读 hash 审计，没有重跑 R1–R6 性能实验。**R6的89项、R5的262项、R4的612项全部通过；原进度表的10条历史实验行及八字段表头完整保留。**

在根 `research_progress.md` 仍为 R6 版本时，使用二进制读取和独占创建写入 [R6进度表快照](history/r6_research_progress.md)，共10206 B，SHA256为 `49b32d42362359d975e797b8d9eb8901950c42f548caddf8a73a3498232ad2c5`。该值同时等于原 `r6/artifact_integrity.json` 的逻辑根进度表 hash 与 `r6/history_lineage.json` 的 successor hash。快照完成时间为2026-09-05 07:45:40 UTC；当时再次执行原 `r6/check_integrity.py`，得到89/262/612项PASS。[原始快照与检查回执](history/snapshot_receipt.json)

新的 [history_lineage.json](history_lineage.json) 保存 R4、R5、R6三个原 manifest 的 hash，并将 R6逻辑根进度表明确映射到新快照。R5仍沿用原R6 lineage的 `r6/history/r5_research_progress.md`；其他所有历史路径保持原处。没有覆盖或重新冻结任何旧manifest，也未修改旧verifier。R4所覆盖的根README继续按原hash核验。

[check_integrity.py](check_integrity.py) 验证上述映射、全部历史文件、R6完整文件范围，以及历史进度行的字节内容、重复次数和相对顺序；同时要求原八字段表头仍在。它将R7 successor登记与R7最终冻结分开，允许主流程先完成报告和根进度表，再记录最终hash。

| 操作 | 用途与约束 |
| --- | --- |
| `python -X utf8 r7/check_integrity.py --verify-history` | 开发期核验89/262/612项与历史行；successor尚未登记时明确输出pending，不将此状态当R7最终验收。 |
| `python -X utf8 r7/check_integrity.py --record-successor` | 根表完成R7追加后运行一次；拒绝没有R7行、与R6相同、历史行变更、已经登记或已经冻结。它只修改R7 lineage，记录最终根表hash及R6 parent hash。 |
| `python -X utf8 r7/check_integrity.py --freeze-r7` | successor登记且所有报告/回执完成后运行一次；原子独占创建R7 manifest，已有manifest时拒绝覆盖。 |
| `python -X utf8 r7/check_integrity.py` | 冻结后校验所有R7范围内文件和当前根表，拒绝缺失、新增和内容变化，同时重验所有父轮证据。 |

R7范围排除三个来源检索缓存 `sources/kernel_access/{riallto_repo,ryzenai_repo,dynamicdispatch_repo}` 及其 `.git`，并排除 `.git`、`__pycache__` 目录和 `.pyc`。权威来源与设备/CPU回执都位于缓存之外，计入冻结。`artifact_integrity.json` 自身不加入其hash映射，避免自引用。冻结后若需要保存新的回执，应建立显式后继关系，不能向冻结轮任意新增文件。

实际验证了两个入口：`--verify-history`通过且输出10条历史实验行；在successor未登记时调用`--freeze-r7`返回非零并提示先登记，确认没有创建manifest。[真实开发期检查与提前冻结拒绝回执](history/checker_initial_receipt.json)。没有通过实际冻结来测试覆盖拒绝，以免抢先冻结仍在工作的R7。

根表追加R7后，原R6 verifier会因其逻辑根路径指向当前新表而报告变化，这是已显式记录的后继关系；R7 checker用字节快照验证原R6期望。该检查只证明历史与工件完整性，不评价性能门、样本独立性、因果识别或硬件创新。
