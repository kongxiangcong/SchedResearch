"""Render the R3 evidence report and standalone scientific plots from saved results."""
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "experiments" / "results" / "r3"


def main():
    summaries = json.loads((DATA / "summary.json").read_text(encoding="utf-8"))
    index = {row["config"]: row for row in summaries}
    minimum = json.loads((ROOT / "experiments/results/minimum_window/results.json").read_text(encoding="utf-8"))
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    metrics = [json.loads(line) for line in (DATA / "metrics.jsonl").read_text(encoding="utf-8").splitlines()]
    figdir = ROOT / "r3" / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "savefig.dpi": 170, "font.family": "DejaVu Sans"})
    names = [("critical_background_memory_cov06", "Critical + background"),
             ("llm_prefill_memory_cov06", "LLM prefill motif"),
             ("llm_decode_memory_cov06", "LLM decode motif"),
             ("dit_cfg_memory_cov06", "DiT CFG motif"),
             ("cores_8", "8 cores"),
             ("chips_2_communication", "2 chips: comm variation"),
             ("grain_4_cost_2", "4 tiles: control cost 2")]
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.8), gridspec_kw={"width_ratios": [1.3, 1, 1]})
    ax = axes[0]
    y = np.arange(len(names))
    for offset, policy, color in [(-.15, "B", "#137c82"), (.15, "C", "#be6138")]:
        values = [index[name][policy + "_paired_reduction_pct"] for name, _ in names]
        lo = [v - index[name][policy + "_normal95_low"] for v, (name, _) in zip(values, names)]
        hi = [index[name][policy + "_normal95_high"] - v for v, (name, _) in zip(values, names)]
        ax.errorbar(values, y + offset, xerr=[lo, hi], fmt="o", markersize=4,
                    capsize=2, color=color, label=policy)
    ax.axvline(0, color="#555555", linewidth=.8)
    ax.set_yticks(y, [label for _, label in names])
    ax.invert_yaxis()
    ax.set_xlabel("Paired latency reduction vs A2 (%)")
    ax.set_title("A  Dynamic dispatch often does not help", loc="left", fontweight="bold")
    ax.legend(loc="lower left", frameon=False)
    ax.grid(axis="x", alpha=.18)
    ax = axes[1]
    for window, color in [(2, "#8a8d91"), (3, "#137c82"), (4, "#9268a1")]:
        rows = [r for r in minimum["results"] if r["window"] == window and r["common_cost"] == 0]
        ax.plot([r["extra_dynamic_dispatch"] for r in rows], [r["reduction_pct"] for r in rows],
                marker="o", markersize=4, color=color, linestyle="--" if window == 4 else "-",
                label=f"Window {window}")
    ax.axhline(0, color="#555555", linewidth=.8)
    ax.set_xlabel("Extra dynamic dispatch cost per task (cycles)")
    ax.set_ylabel("Expected latency reduction (%)")
    ax.set_title("B  Small window, narrow cost margin", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    ax.grid(alpha=.18)
    ax = axes[2]
    for cost, linestyle in [(0, "--"), (2, "-")]:
        for policy, color in [("A2", "#686d75"), ("B", "#137c82")]:
            values = [index[f"grain_{p}_cost_{cost}"][policy + "_mean"] for p in (1, 2, 4)]
            ax.plot([1, 2, 4], values, marker="o", color=color, linestyle=linestyle,
                    markersize=4, label=f"{policy}, control cost {cost}")
    ax.set_xticks([1, 2, 4])
    ax.set_xlabel("Tiles per task (fixed total service work)")
    ax.set_ylabel("Mean latency (synthetic cycles)")
    ax.set_title("C  Finer grain must pay for control", loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=.18)
    fig.suptitle("R3: compiler-known graph, runtime completion uncertainty", fontsize=16, x=.53, y=.98)
    fig.text(.5, .018, "Uncalibrated synthetic models. A: 20 seeds, approximate 95% intervals; B: exact two-world distribution. No silicon or full-model claims.",
             ha="center", fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, .07, 1, .93), w_pad=2)
    for suffix in ("png", "pdf"):
        fig.savefig(figdir / ("r3_evidence." + suffix))
    plt.close(fig)

    positive = sum(r["B_paired_reduction_pct"] > 1e-8 for r in summaries)
    negative = sum(r["B_paired_reduction_pct"] < -1e-8 for r in summaries)
    zero = len(summaries) - positive - negative
    c_wins = sum(r["C_mean"] < r["B_mean"] - 1e-8 for r in summaries)
    a2_losses = sum(r["A2_mean"] > r["A_mean"] + 1e-8 for r in summaries)
    lines = ["# R3实验报告：存在调度机会，但尚未证明大规模动态硬件值得",
             "", "日期：2026-09-05。由 `python -X utf8 -B -m experiments.make_report` 从当前完整结果生成。",
             "", "## 1. 结果与证据级别",
             "", f"完成 **{manifest['configs']}配置 × 20 test seeds × A/A2/B/C = {manifest['test_samples']}次执行**。另有四任务exact反例与72个minimum-window/开销点（每点两个确定场景，穷举6种静态admission/order合同）。14项自动测试通过；保存196条seed0 traces，全部通过资源互斥/最小依赖可见性检查；13个源文件hash与实验manifest一致。trace检查的排队时序覆盖限制见第6节。",
             "", f"B相对同合同A2：{positive}个配置均值为正、{negative}负、{zero}零；C有{c_wins}个配置mean优于B。A2在{a2_losses}个配置中mean反而输给A，有限训练静态不是普遍更强。正/负数量未按统计显著性筛选，也不是独立真实workload的胜率。",
             "", "**结论：** R2的必要条件已被严格反例否定；本轮更大motif大多数没有值得增加硬件的优势。更复杂C没有继续理由。Hybrid仍是值得研究的边界，但本轮不确认独立论文贡献或真实设备性能。",
             "", "![R3 evidence](figures/r3_evidence.png)",
             "", "可导出图：[PDF](figures/r3_evidence.pdf)。图中B/C对A2的配对区间只反映synthetic分布采样误差，不覆盖模型误差；展示case为解释机制选择，不代替下方全表。",
             "", "## 2. 四任务：精确存在性、最小窗口与增量成本",
             "", "两独立DMA分别唤醒共享VPU上的20cycle任务，DMA时长等概率(80,120)/(120,80)。固定地址，无复用，CoV0.2且有界。两个VPU固定顺序的期望均150；B每场景140，达到每场景下界120+20。latency reduction=6.667%，speedup=1.07143。不存在把naive sequential当baseline的问题。",
             "", "有限window包括运行中和等待中的resident task。W2会让等待较晚producer的descriptor挡住尚未admit的替代任务；W3暴露它，W4不再增加收益。以下common cost为0，额外派发成本只向B收费：",
             "", "| Window | B额外dispatch/task | 最优静态期望 | B期望 | 延迟降低 | B部分state bits |",
             "|---:|---:|---:|---:|---:|---:|"]
    for row in minimum["results"]:
        if row["common_cost"] == 0 and row["extra_dynamic_dispatch"] in (0, 4, 8):
            lines.append(f"| {row['window']} | {row['extra_dynamic_dispatch']} | {row['static_expected']:.1f} | {row['dynamic_expected']:.1f} | {row['reduction_pct']:.3f}% | {row['dynamic_state_bits']} |")
    lines += ["", "所有点总descriptor估计234B；351/412等state数只是本图的部分逻辑位预算，不是PPA或量产规格。W3在额外8cycle时变成156，比最优静态150慢4%。因此最小窗口并不保证划算，也不能从本例推导所有NPU用3项就够。",
              "", "## 3. 大图主比较与强静态核对",
              "", "A采用8种离线list-schedule候选择预测最优；A2用8个独立训练seed选择固定顺序。B/C使用A2的同DAG、mapping、地址、priority、admission与hardware。A2/B配对隔离选序自由；A列则用于发现B是否只是胜一个较差的静态选择。A/A2都还不是生产级全局最优。",
              "", "| 配置 | task数 | A均值 | A2均值 | B均值 | C均值 | B对A2配对降低 | 近似95%区间 |",
              "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in summaries:
        lines.append(f"| {row['config']} | {row['tasks']} | {row['A_mean']:.2f} | {row['A2_mean']:.2f} | {row['B_mean']:.2f} | {row['C_mean']:.2f} | {row['B_paired_reduction_pct']:.3f}% | [{row['B_normal95_low']:.3f}, {row['B_normal95_high']:.3f}] |")
    prefill = index["llm_prefill_memory_cov06"]
    dit = index["dit_cfg_memory_cov06"]
    comm = index["chips_2_communication"]
    lines += ["", "需要特别解释的观察：",
              "", f"- Prefill motif的B对A2为+{prefill['B_paired_reduction_pct']:.3f}%，但A={prefill['A_mean']:.2f}已优于B={prefill['B_mean']:.2f}，不能据此宣称strong compiler无法解决。",
              f"- DiT motif为+{dit['B_paired_reduction_pct']:.3f}%，统计上虽有一致小改善，但远小于5%研究筛选阈值；它是手写CFG/AdaLN结构，不是真实DiT测量。",
              f"- 两chip communication-only为{comm['B_paired_reduction_pct']:.3f}%，动态更慢。阶段barrier和非抢占resource order让“通信越随机、动态越值钱”不成立。",
              "- 确定性链/多个规则pipeline为零；随机链也可以为零。后者是缺乏可利用自由度，不是延迟确定。",
              "- 粒度扫描保持粗task的同一噪声因子和总服务工作量。细粒度带来的pipeline重叠也能被静态compiler利用，不能把它全部归给dynamic。",
              "", "## 4. 集中与分域：相同预算仍未见优势",
              "", "原clusters_*_local每域复制端口/窗口，所以只作扩硬件的对照。equal_budget_*固定总entry/bytes/issue/wakeup预算：local每域16项/4096B/1 issue/1 wakeup，central按实际域数乘总量。两者保持同样物理任务资源，端口服务和窗口分配方式不同；没有建布线距离或真正层次协议。",
              "", "| 域数 | Central B latency | Local B latency | Local相对central延迟降低 |",
              "|---:|---:|---:|---:|"]
    for count in (2, 4):
        a = index[f"equal_budget_clusters_{count}_central"]["B_mean"]
        b = index[f"equal_budget_clusters_{count}_local"]["B_mean"]
        lines.append(f"| {count} | {a:.3f} | {b:.3f} | {100*(a-b)/a:.3f}% |")
    lines += ["", "该比较没有证明分布式更好；它也不能证明central实际布线可扩展。当前所谓local只分片issue/wakeup与admission，全图metadata仍存在；hierarchical scheduler未实现。",
              "", "## 5. 利用率与控制成本（B，跨20 seeds平均）",
              "", "| 配置 | MXU busy | VPU busy | DMA busy | Ready均值 | issue利用率 | wakeup数 | descriptor B | 部分state bits |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name in ["chain_memory_cov06", "llm_prefill_memory_cov06", "dit_cfg_memory_cov06", "chips_2_communication", "grain_4_cost_2", "wakeup_1"]:
        rows = [r["metrics"] for r in metrics if r["config"] == name and r["policy"] == "B"]
        def mean(key):
            return statistics.mean(r[key] for r in rows)
        def util(kind):
            vals = [v for row in rows for r, v in row["resource_utilization"].items() if kind in r]
            return f"{100*statistics.mean(vals):.1f}%" if vals else "—"
        issue = mean("scheduler_issue_utilization")
        issue_text = f"{100*issue:.1f}%" if issue else "未收费"
        lines.append(f"| {name} | {util('mxu')} | {util('vpu')} | {util('dma')} | {mean('ready_queue_mean'):.2f} | {issue_text} | {mean('wakeup_messages'):.0f} | {mean('descriptor_bytes_estimate'):.0f} | {mean('abstract_state_bits'):.0f} |")
    lines += ["", "busy是task服务时间/总延迟，多个同类resource等权平均；reserved利用率另含dispatch设置，原始JSONL也保留。issue利用率是建模端口服务占用率；0开销下不能将其解释成真实scheduler空闲。task throughput为Ntasks/latency，不能换成tokens/s。",
              "", "各样本还保存admission/dependency/memory-resource/communication-resource/engine/static-order/issue等待、各resource idle、critical-path ratio、candidate checks和state breakdown。task等待类别排他，但跨task相加**不等于**端到端stall。cache miss、DRAM refresh和NoC flit stall未实现，不能从聚合资源字段推导。",
              "", "## 6. 正确性、模型局限与可复现性",
              "", "独立审计修复了buffer span不足、有限窗口admission/静态顺序不兼容、barrier被错误当tile data edge三个输入/扩展缺口。当前结果按修复后源码重跑。trace checker独立查每task唯一、基础可见性和resource不重叠，但未独立重建全部wakeup/issue排队；这些由专门单元测试覆盖。详见 [simulator redteam](../analysis/simulator_redteam.md)。",
              "", "模型仍有重要局限：整task原子独占SRAM/DMA/NoC bundle；服务分布人工且缺相关拥塞；无真实model export/数值；地址默认不复用，capacity联合优化未测；finite window之外还有O(N+E)history/通知状态；无有限credit回压/epoch回绕/分布式死锁验证；C额外算术延迟未收费。descriptor只是可检查JSON表示和假想bytes，**没有binary decoder roundtrip**。",
              "", "这些局限使本轮足以反驳R2必要条件、证明特定图的信息价值并筛选策略，但不足以证明真实端侧NPU收益或最小硬件总状态。未通过实际workload+强静态+详细时序+PPA证据门，所以最终架构暂不锁定。",
              "", "复现（目录根，Python标准库运行仿真；画图另需matplotlib/numpy）：",
              "", "```powershell", "python -X utf8 -B -m unittest discover -s tests -v",
              "python -X utf8 -B -m experiments.run --seeds 20 --training-seeds 8",
              "python -X utf8 -B -m experiments.oracle_probe",
              "python -X utf8 -B -m experiments.check_results",
              "python -X utf8 -B -m experiments.minimum_window",
              "python -X utf8 -B -m experiments.make_report", "```",
              "", "[完整CSV](../experiments/results/r3/summary.csv) · [逐seed样本](../experiments/results/r3/samples.csv) · [全部metrics](../experiments/results/r3/metrics.jsonl) · [源码manifest](../experiments/results/r3/manifest.json) · [产物检查](../experiments/results/r3/artifact_check.json) · [minimum-window原始结果](../experiments/results/minimum_window/results.json)"]
    (ROOT / "r3/experiment_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report and PNG/PDF plots generated from {len(summaries)} configurations.")
    for name, _ in names:
        row = index[name]
        print(f"{name}: B {row['B_paired_reduction_pct']:.3f}%, C {row['C_paired_reduction_pct']:.3f}%")


if __name__ == "__main__":
    main()
