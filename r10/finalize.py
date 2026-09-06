"""One-time R10 successor and named-artifact freeze, never edits prior rounds."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[1];P=ROOT/'r10'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert not (P/'results_manifest.json').exists(),'already frozen'
    for f in ('results/audit_results.json','causal_results/audit_results.json','results/bound_tests.json','replay_receipt.json'):
        assert json.loads((P/f).read_text())['status']=='PASS'
    lineage=json.loads((P/'history_lineage.json').read_text(encoding='utf-8-sig'))
    parent=ROOT/lineage['parent_snapshot'];root=ROOT/'research_progress.md'
    assert sha(parent)==lineage['parent_sha256'] and root.read_bytes().startswith(parent.read_bytes())
    rows=[
        '| R10：更紧下界与联合静态 | EXT128/DMA32的大恢复上界中能证明多少只是资源下界松弛，静态交互还能消除多少elapsed？ | 有限credit在EXT停供期限制local供给，联合驻留/布局/预取/顺序可能消除其余损失。 | 两hardware各960合法候选、8/8新train/validation、各29 shortlist、360独立配对块；证明并独立实现credit/停供/依赖下界。 | EXT128旧静态上界均值约18%收紧至9.62%–11.49%；新静态仍约9.79%–11.47%。DMA32/20%仅约0.106%静态改善，35%为0；新上界仍约11.33%–13.15%。 | Accept部分松下界解释；Refine残余，不支持静态已消除大gap或全部不可避免供给。 | 有限静态池、串联下界仍松，所有干扰条件仍未过逐block小于5%关闭门；非真实TARS证据。 | 以完整外存Y终点的小图credit/两资源顺序证书收紧未决空间，不把upper当收益。 |',
        '| R10：新相位收费观察规则 | 可观测busy/idle状态的一次有限EXT改序规则能否在强静态后达到机制门？ | 四个固定观察点可能找到idle接收cluster，收费改序后仍有净elapsed收益。 | 独立预登记新8/8/30/30相位；360 baseline/causal测试配对，2cycle每观察与8cycle动作；720详细trace独立复核，A/B共1440次elapsed重放。 | 1440观察全部另一侧busy，0次实际改序，全部只收8cycle；最高干扰均值0.002796%且CI跨0；quiet回退最高0.027226%。A/B合计1104 trace、860736 requests通过。 | Reject该观察规则的5%收益主张；未有效测试实际触发改序价值，不接受最小硬件机制。 | 平均约10%–13%剩余upper仍可能是松界、静态遗漏或动态空间；模拟session不等于实机，无PPA。 | 保留负结果与未决，不用同批test调阈值；新动作须先证明可触发与端到端作用，再新登记新相位。 |'
    ]
    with root.open('ab') as f:f.write(('\n\n'+'\n'.join(rows)+'\n\nR10实际结果：[完整报告](r10/experiment_report.md)、[下界证明](r10/bound_proof.md)、[独立复核与红队](r10/redteam_report.md)、[R10 lineage](r10/history_lineage.json)、[结果清单](r10/results_manifest.json)。部分松下界已确认，剩余动态空间未判明；本轮不接受新机制。\n').encode('utf8'))
    successor=P/'history/r10_research_progress.md';successor.write_bytes(root.read_bytes())
    lineage.update(successor_snapshot=str(successor.relative_to(ROOT)).replace('\\','/'),successor_sha256=sha(successor),phase='completed-reference-experiment',added_rows=[s for s in root.read_text(encoding='utf8').splitlines() if s.startswith('| R10：')])
    (P/'history_lineage.json').write_text(json.dumps(lineage,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    files={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(P.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='results_manifest.json'}
    manifest=dict(schema='r10.named-artifacts.v1',files=files,scope='frozen R10 reference-model evidence; future additions allowed',audit_results=['r10/results/audit_results.json','r10/causal_results/audit_results.json'])
    (P/'results_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(frozen=len(files),root_rows_added=len(rows))))
if __name__=='__main__':main()
