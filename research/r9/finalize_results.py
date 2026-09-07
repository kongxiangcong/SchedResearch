"""Append R9 result rows once and freeze named artifacts, preserving old handoff."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "r9"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def main():
    parent = HERE / "history/aligned_research_progress.md"
    progress = ROOT / "research_progress.md"
    assert progress.read_bytes() == parent.read_bytes(), "root no longer equals R9 aligned parent; inspect before appending"
    assert not (HERE / "results_manifest.json").exists(), "R9 manifest already frozen"
    audit = json.loads((HERE / "results/audit_results.json").read_text(encoding="utf8"))
    assert audit["status"] == "PASS" and audit["audited_traces"] == 608
    for filename in ("experiment_report.md", "redteam_report.md", "static_interpretation.md", "results/loss_and_recovery.png"):
        assert (HERE / filename).is_file(), filename
    added = [
        "| R9：参考硬件与共享供给 | 自主两cluster各两核的共享EXT路径中，强静态后的干扰损失属于供给还是新增改序空间？ | mapping/广播/tiling/并发先于机制；大变慢可与小可恢复空间并存。 | 冻结单路径数值合同；Qwen down M32/fullK9216/N128；204静态候选、独立8train/8validation、两组各30paired blocks/条件；608轨迹477312requests独立审计。 | 同一C2K/K256/双buffer方案在三环境均被选；quiet47776cycle，20%背景慢24.75%/25.31%，35%慢52.81%/53.01%；重训消除0；平均免费恢复上界约1.6%–1.9%。 | **Accept条件性供给与强静态证据；不是当前TARS或实机残差。** | 理想DMA/operand端口、固定绝对预留过程、有限静态池、数值与gather/广播的真实目标准入。 | 集中硬件合同可替换；保留真实校准门，不回到Phoenix SDK，不把供给损失当scheduler收益。 |",
        "| R9：单动作筛查与失效范围 | 既有work-conserving仲裁外的一次合法DMA改序能否达到5%收费收益，能否统一关闭更广候选？ | 只有改变最终结束且收益足够的因果动作才值得新增机制；资源上界大只是未决。 | 2880次同合同单动作反事实，0/8cycle收费；tiny两序两相位exact、7故障fixture；9个事前单参数敏感性。 | 收费回看最佳均值最高0.0210%且CI跨0；35%条件为0；但35%免费恢复上界最大5.1579%，EXT128/DMA32敏感性最大19.8588%/15.8944%。 | **Reject已测动作族5%收益主张；Refine严格逐phase关闭门及带宽比例范围，不接受新机制。** | 回看选择非causal；上界松弛、有限credit串联服务与静态搜索不足尚未区分；大gap不是收益。 | 先在具名EXT/DMA比例范围加强串联资源下界与静态交互，再以新相位判别有限因果动作；不追极端参数、不外推关闭所有多cluster。 |"
    ]
    for row in added:
        assert len(row.split("|")) == 10
    lines = progress.read_bytes().decode("utf8").splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.startswith("| R8→R9：")]
    assert len(matches) == 1
    index = matches[0]
    newline = "\r\n" if lines[index].endswith("\r\n") else "\n"
    lines[index + 1:index + 1] = [row + newline for row in added]
    successor_bytes = "".join(lines).encode("utf8")
    footer = (newline + "R9实际实施与模型内判决：[完整报告](r9/experiment_report.md)、[参考硬件](r9/reference_hardware.json)、[独立红队](r9/redteam_report.md)、[结果清单](r9/results_manifest.json)、[R9 lineage](r9/history_lineage.json)。主参考已测单动作不支持新机制；35%严格关闭门与EXT/DMA比例范围保持未决。" + newline).encode("utf8")
    successor_bytes += footer
    successor = HERE / "history/successor_research_progress.md"
    assert not successor.exists()
    successor.write_bytes(successor_bytes)
    progress.write_bytes(successor_bytes)
    write(HERE / "history_lineage.json", {
        "schema": "r9.result-lineage.v1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "parent_handoff_manifest": "r9/handoff_integrity.json", "parent_handoff_sha256": sha(HERE / "handoff_integrity.json"),
        "parent_snapshot": str(parent.relative_to(ROOT)).replace("\\", "/"), "parent_sha256": sha(parent),
        "successor_snapshot": str(successor.relative_to(ROOT)).replace("\\", "/"), "successor_sha256": sha(successor),
        "added_rows": added, "rule": "Preserve parent rows and order; future root additions allowed; old manifests untouched."
    })
    named = sorted(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != "results_manifest.json")
    named.append(ROOT / "README.md")
    write(HERE / "results_manifest.json", {
        "schema": "r9.named-artifact-integrity.v1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_level": "independently audited reference model; sampled single-action rejected; wider parameter and phase scope unresolved",
        "audit_result": "r9/results/audit_results.json", "files": {str(p.relative_to(ROOT)).replace("\\", "/"): sha(p) for p in named},
        "future_rule": "Only named artifacts frozen. New R9/R10 files allowed. Evolving root is represented by successor snapshot."
    })
    print(json.dumps({"status": "FINALIZED", "named_files": len(named), "new_progress_rows": len(added)}))


if __name__ == "__main__":
    main()
