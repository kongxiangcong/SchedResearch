"""One-time append-only R11 handoff; no prior round artifacts changed."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1];HERE=ROOT/'r11'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
    assert not (HERE/'handoff_integrity.json').exists()
    history=HERE/'history';history.mkdir(exist_ok=True)
    progress=ROOT/'research_progress.md';original=progress.read_bytes()
    parent=history/'r10_research_progress.md';parent.write_bytes(original)
    row='| R10→R11：完整单层驻留验证（计划） | R5小切片静态驻留收益在完整GDN单层和真实输入顺序下还能否成立？ | 合法保留state可能减少重复本地搬运；完整容量和token生命周期也可能消除原收益。 | 用户确认只验证驻留；暂停动态选序；保存R10父快照，建立R11交接；新任务先预登记再实施数值、容量、traffic、elapsed和独立复核。 | 已明确窄范围与成立/关闭判决；尚无R11实验结果。 | Accept实验范围；不预判收益，不并行启动分片、新存储硬件或scheduler。 | 完整32heads容量、真实prepared输入可得性、prefill与decode适用差异及共同成本。 | 新任务完成实验，给出成立可继续或未获支持关闭的具名结论，不能只交计划。 |'
    assert len(row.split('|'))==10
    progress.write_bytes(original+('\n\n'+row+'\n\nR11用户确认的窄范围与直接实施交接：[continuation brief](r11/continuation_brief.md)、[handoff integrity](r11/handoff_integrity.json)。\n').encode('utf8'))
    aligned=history/'aligned_research_progress.md';aligned.write_bytes(progress.read_bytes())
    save(HERE/'history_lineage.json',dict(parent_round='R10',successor_round='R11',parent_snapshot='r11/history/r10_research_progress.md',parent_sha256=sha(parent),aligned_snapshot='r11/history/aligned_research_progress.md',aligned_sha256=sha(aligned),phase='user-authorized-handoff',added_plan_row=row))
    files=[HERE/'continuation_brief.md',HERE/'prepare_handoff.py',parent,aligned]
    save(HERE/'handoff_integrity.json',dict(status='ready-for-implementation',files={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in files},frozen_r10_manifest_sha256=sha(ROOT/'r10/results_manifest.json'),note='Only these handoff files frozen; R11 implementation/results may be added; new final lineage must preserve parent and aligned snapshots'))
    assert progress.read_bytes().startswith(original)
    print(json.dumps(dict(status='PASS',handoff_files=len(files),added_rows=1)))
if __name__=='__main__':main()
