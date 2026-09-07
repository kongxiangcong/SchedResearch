"""Record the R8 successor once, preserving the frozen scope-alignment parent."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R8 = ROOT / "r8"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    live = ROOT / "research_progress.md"
    parent = R8 / "history/aligned_research_progress.md"
    successor = R8 / "history/completed_research_progress.md"
    lineage = R8 / "history_lineage.json"
    assert not successor.exists() and not lineage.exists(), "one-time successor; do not overwrite"
    assert sha(live) == sha(parent), "root must still be the recorded parent"
    assert json.loads((R8 / "results/receipt.json").read_text(encoding="utf8"))["status"] == "PASS"
    assert json.loads((R8 / "redteam_results.json").read_text(encoding="utf8"))["status"] == "PASS"
    before = live.read_text(encoding="utf8")
    old = "R8目前为方向对齐/待执行，不是新实验结论。"
    new = "R8已完成来源/静态分片账本、CPU数值与单payload偏序闭环；当前决定为Refine目标准入与传输路径，尚无真实残差或性能结论。"
    assert before.count(old) == 1
    rows = [
        "| R8：静态分片与资源账本 | 两cluster各两核的跨域partial是否为工作量必需，还是静态mapping/路径取舍？ | Output-shard可免partial；split-K的价值依赖输入复制、route及数值许可，不能直接推出动态残差。 | 事前登记；Qwen down fullK9216/N128、M1/32，3种mapping×2M的6账本；20core/100分配；3seeds×2M×3mapping的18 CPU数值比较，独立复算。 | 同4核权重2359296B；M32单播输入N分片2359296B、K分片1179648B，后者增16384B partial；全部诊断容差通过，但6个split-K结果均非bitwise，抵消反例顺序1/split0/FP64为2。 | **Accept来源约束账本；Refine目标静态准入，不作性能排名。** | 当前TARS根、multicast/staging/peer路线、VMEM保留区和静态搜索；M1非历史native geometry，split-K数值许可未证。 | 先确认当前target及实际共享DMA/外存路径，允许target支持的mapping/layout/驻留/预取与既有仲裁；选择strong-static后才测真实残差。 |",
        "| R8：payload可见性与复用 | DMA接受/最后读/目标可见能否未经证明合并为consumer和slot复用的完成信号？ | 精确静态wait/release或等价阻塞合同足以使有限单payload抽象安全；过早放行可构造错误。 | 五种七事件偏序全部70线性扩展，逐条执行sentinel读取；独立checker复算全部记录及witness，没有时序或设备实验。 | safe5/0错、保守release4/0错；early-event40/26错、early-source6/1错、early-destination15/10错；37是结构错误数非概率。 | **Accept有限安全证书与反例；Reject由此推出target bug、新scheduler或真实收益。** | 仅单次已produce-visible payload；未验两个partial并发、完整reduction/最终store、credit/反压、重试和RTL；真实残差未测。 | 获取目标completion语义并绑定具名span/last-reader；当前停止扩sim/Phoenix SDK，R5通用ready保持关闭，保留未测多cluster空间。 |"
    ]
    text = before.replace(old, new)
    anchor = next(line for line in text.splitlines() if line.startswith("| R7→R8："))
    text = text.replace(anchor, anchor + "\n" + "\n".join(rows), 1)
    text += "\nR8实际结果与新父子关系：[完整报告](r8/experiment_report.md)、[目标合同](r8/target_contract.json)、[独立红队](r8/redteam_report.md)、[R8 lineage](r8/history_lineage.json)。当前入口需求收敛为权威TARS顶层checkout路径；历史与R8分别用 `r8/check_history.py`、`r8/check_results.py` 只读复核。\n"
    historical = [line for line in before.splitlines() if line.startswith("| R")]
    current = [line for line in text.splitlines() if line.startswith("| R")]
    assert all(Counter(current)[r] == count for r, count in Counter(historical).items())
    assert [r for r in current if r in historical] == historical
    assert all(len(r.split("|")) == 10 for r in rows)
    live.write_text(text, encoding="utf8", newline="\n")
    successor.write_bytes(live.read_bytes())
    data = {"schema": "r8.progress-lineage.v1", "created_utc": datetime.now(timezone.utc).isoformat(),
            "parent_handoff_sha256": sha(R8 / "handoff_integrity.json"),
            "parent_progress": {"snapshot": parent.relative_to(ROOT).as_posix(), "sha256": sha(parent)},
            "successor_progress": {"logical_path": "research_progress.md", "snapshot": successor.relative_to(ROOT).as_posix(), "sha256": sha(successor)},
            "added_rows": rows, "evidence_level": "R8 source/CPU/finite-order results, no target performance",
            "future_rule": "preserve this successor snapshot and rows; new results need a new parent-child record; never rewrite old manifests"}
    lineage.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print(json.dumps({"status": "PASS", "new_rows": len(rows), "parent_sha256": sha(parent), "successor_sha256": sha(successor)}))


if __name__ == "__main__":
    main()
