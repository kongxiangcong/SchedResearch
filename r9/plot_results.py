"""Plot the frozen R9 main-reference summary without modifying research evidence.

Run: python -X utf8 -B r9/plot_results.py
The exact two owned output paths may be regenerated with --overwrite-own.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
SOURCE = RESULTS / "summary.json"
EXPECTED_SOURCE_SHA256 = "194d945430293825888b1289720f5d0464be390676543bb12a1770d883fa7685"
OWNER = "R9 plot_results.py"
OUTPUTS = {"png": RESULTS / "loss_and_recovery.png", "pdf": RESULTS / "loss_and_recovery.pdf"}


def validate_output(path: Path, overwrite: bool) -> None:
    if path.resolve().parent != RESULTS.resolve() or path not in OUTPUTS.values():
        raise ValueError("output must be one of the two exact owned figure paths")
    if not path.exists():
        return
    if not overwrite:
        raise FileExistsError(f"Refusing overwrite: {path}; use --overwrite-own for this figure only")
    if path.suffix == ".png":
        with Image.open(path) as old:
            owned = old.info.get("Software") == OWNER
    else:
        owned = f"/Creator ({OWNER})".encode("ascii") in path.read_bytes()
    if not owned:
        raise ValueError(f"existing file lacks this plotter's ownership marker: {path}")


def series(summary, keys, name):
    rows = [summary[key][name] for key in keys]
    if any(row["n"] != 30 for row in rows):
        raise ValueError("figure requires the registered 30 paired blocks per condition/session")
    mean = np.array([row["mean"] for row in rows])
    ci = np.array([row["ci95_t"] for row in rows])
    error = np.stack([mean - ci[:, 0], ci[:, 1] - mean])
    if np.any(error < 0):
        raise ValueError("confidence interval does not contain its mean")
    return mean, error, np.array([row["max"] for row in rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite-own", action="store_true")
    args = parser.parse_args()
    for path in OUTPUTS.values():
        validate_output(path, args.overwrite_own)
    source_bytes = SOURCE.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise ValueError("summary differs from the frozen R9 figure source")
    summary = json.loads(source_bytes)
    keys = ["s1.reserved20", "s2.reserved20", "s1.reserved35", "s2.reserved35"]
    loss, loss_error, _ = series(summary, keys, "fixed_static_loss_pct")
    upper, upper_error, upper_max = series(summary, keys, "remaining_zero_cost_upper_pct")
    charged, charged_error, _ = series(summary, keys, "best_sampled_single_action_charged_pct")

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.labelcolor": "#252c35", "text.color": "#202833",
        "axes.edgecolor": "#6e7782", "xtick.color": "#3a4654", "ytick.color": "#3a4654",
        "pdf.fonttype": 42, "ps.fonttype": 42,
        "savefig.facecolor": "white", "figure.facecolor": "white",
    })
    blue, orange, gray = "#23618d", "#bc5819", "#6b727a"
    fig, (left, right) = plt.subplots(1, 2, figsize=(12.0, 6.5), gridspec_kw={"width_ratios": [0.94, 1.15]})
    fig.subplots_adjust(left=0.073, right=0.975, bottom=0.29, top=0.77, wspace=0.27)
    fig.suptitle("R9: interference slowdown and remaining recovery space", x=0.073, y=0.97,
                 ha="left", fontsize=17, weight="semibold")
    fig.text(0.073, 0.915, "Qwen down M32 / K9216 / N128  |  two clusters, two cores each  |  shared external service", fontsize=10.5)
    x = np.array([0, 1, 2.6, 3.6])
    ticklabels = ["20%\nS1", "20%\nS2", "35%\nS1", "35%\nS2"]
    for ax in (left, right):
        ax.set_xticks(x, ticklabels)
        ax.set_xlim(-0.6, 4.2)
        ax.set_xlabel("External-service reservation / simulated phase session", labelpad=10)
        ax.grid(axis="y", color="#e5e9ed", linewidth=0.7)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", length=0, pad=7)
    left.set_title("A   Fixed selected-static slowdown", loc="left", fontsize=12, pad=17)
    left.errorbar(x, loss, yerr=loss_error, fmt="o", color=blue, markersize=7,
                  capsize=4, elinewidth=1.4, zorder=3)
    for xx, value in zip(x, loss):
        left.annotate(f"{value:.2f}%", (xx, value), xytext=(0, 12), textcoords="offset points",
                      ha="center", fontsize=10, weight="medium")
    left.set_ylim(0, 62)
    left.set_yticks([0, 10, 20, 30, 40, 50, 60])
    left.set_ylabel("Slowdown vs. the same plan in quiet (%)", labelpad=9)

    right.set_title("B   Recovery on the selected graph", loc="left", fontsize=12, pad=17)
    right.errorbar(x - 0.12, upper, yerr=upper_error, fmt="o", color=blue,
                   markersize=6.5, capsize=4, elinewidth=1.4, zorder=4)
    right.plot(x, upper_max, linestyle="none", marker="D", markersize=6,
               markerfacecolor="white", markeredgewidth=1.3, color=blue, zorder=4)
    right.errorbar(x + 0.12, charged, yerr=charged_error, fmt="s", color=orange,
                   markersize=5.5, capsize=3, elinewidth=1.25, zorder=4)
    right.axhline(5, color=gray, linestyle=(0, (4, 3)), linewidth=1.0, zorder=2)
    right.text(-0.49, 5.55, "5% gain screen", fontsize=9.5, color=gray)
    right.set_ylim(-0.22, 6.05)
    right.set_yticks([0, 1, 2, 3, 4, 5, 6])
    right.set_ylabel("Bound / sampled gain vs. interfered elapsed (%)", labelpad=9)
    for xx, value in zip(x, charged):
        right.annotate(f"{value:.3f}%", (xx + 0.12, value), xytext=(0, 12), textcoords="offset points",
                       ha="center", color=orange, fontsize=8.5)
    for xx, value in zip(x[2:], upper_max[2:]):
        right.annotate(f"{value:.3f}%", (xx, value), xytext=(0, 9), textcoords="offset points",
                       ha="center", color=blue, fontsize=9)
    handles = [
        Line2D([0], [0], marker="o", linestyle="none", color=blue, markersize=6, label="Mean + 95% CI"),
        Line2D([0], [0], marker="D", linestyle="none", color=blue, markerfacecolor="white", markersize=5.5, label="Max. sampled-phase bound"),
        Line2D([0], [0], marker="s", linestyle="none", color=orange, markersize=5.5, label="Charged hindsight gain + 95% CI"),
    ]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.069, 0.88),
               ncol=3, frameon=False, handletextpad=0.6, columnspacing=2.0, fontsize=9.3)
    fig.text(0.073, 0.11, "Whiskers: paired-block t 95% CI; n=30 per condition/session. Main reference model only; sessions are not device runs.", fontsize=9)
    fig.text(0.073, 0.07, "Right: per-graph zero-cost recovery upper bound; sampled action costs 8 cycles, uses hindsight, and includes no-action.", fontsize=9)
    fig.text(0.073, 0.03, "Sampled maximum 5.158% exceeds the 5% screen: no uniform closure or mechanism acceptance. Source: r9/results/summary.json", fontsize=9)

    png, pdf = io.BytesIO(), io.BytesIO()
    fig.savefig(png, format="png", dpi=200,
                metadata={"Software": OWNER, "Description": "Frozen R9 reference-model results; summary SHA256=" + source_sha})
    fig.savefig(pdf, format="pdf", metadata={"Creator": OWNER, "Title": "R9 interference slowdown and recovery space",
                                             "Subject": "Reference model; no mechanism acceptance. Summary SHA256=" + source_sha,
                                             "CreationDate": datetime(2026, 9, 5, tzinfo=timezone.utc),
                                             "ModDate": datetime(2026, 9, 5, tzinfo=timezone.utc)})
    plt.close(fig)
    # Both destinations were validated before rendering; no other path is writable.
    for kind, payload in (("png", png.getvalue()), ("pdf", pdf.getvalue())):
        path = OUTPUTS[kind]
        mode = "wb" if args.overwrite_own else "xb"
        with path.open(mode) as stream:
            stream.write(payload)
        print(json.dumps({"path": str(path), "sha256": hashlib.sha256(payload).hexdigest(),
                          "source_sha256": source_sha, "bytes": len(payload)}))


if __name__ == "__main__":
    main()
