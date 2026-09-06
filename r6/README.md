# R6 evidence and next decision

阅读 [实验报告](experiment_report.md)、[独立红队](redteam_report.md)、[一手来源](source_evidence.md)与[测量合同](measurement_schema.md)。原始probe回执在evidence，历史进度表字节快照在history。

已实际执行Phoenix厂商launch/wait与1GiB copy自测；尚无strong-static的固定binary干扰、compiler对照或动态恢复结果。当前决定Refine measurement/kernel access；R5通用ready候选继续关闭。

在工作区根目录复核（不再次运行设备）：

```powershell
python -X utf8 -B r6\check_integrity.py
python -X utf8 -B r6\test_measurements.py -v
```

来源推导与设备报告解释可分别用 `python -X utf8 -B r6\residency_audit.py`、`python -X utf8 -B r6\summarize_probes.py` 重算；它们只重写对应R6 JSON，不调用旧simulator或硬件。测量模板用 `python -X utf8 -B r6\validate_measurements.py r6\measurement_template.json` 检查，缺观测导致机制资格为false是正确结果。

历史版本关系在history_lineage.json。根research_progress.md是R6的新版本；r5原清单及所有旧文件未改。原r5/check_integrity.py会发现根表变化，R6 checker通过明确的快照映射认证R5旧版本，不能运行R5 --freeze掩盖演进。
