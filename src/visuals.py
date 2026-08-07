# src/visuals.py — figures from the pipeline output
import sys
import yaml
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import seaborn as sns
from matplotlib.ticker import ScalarFormatter, NullFormatter, NullLocator


def plain_log(axis):
    """Show plain numbers (1, 10, 100) on a log axis instead of 10^x."""
    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    axis.set_major_formatter(formatter)
    axis.set_minor_formatter(NullFormatter())   # hide the little in-between ticks


def tidy_colorbar(ax):
    """Give a colorbar plain-number ticks and no minor-tick clutter."""
    colorbar = ax.collections[0].colorbar
    plain_log(colorbar.ax.yaxis)
    colorbar.ax.yaxis.set_minor_locator(NullLocator())


ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from harmonize import (process_file, parse_filename, get_lineup, pick_trigger,
                       detect_pulses, pick_window)

sns.set_theme(style="whitegrid", context="talk")   # clean, readable defaults

MANIFEST_FILE = ROOT / "docs" / "Centralized-NIDAQ-System-Pharma-1957-PRIMING.xlsx"
CONFIG_FILE = ROOT / "config" / "params.yaml"
FIGDIR = ROOT / "outputs" / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)


def save_boxplot(df, muscle_order, value_col, title, filename):
    """One box per muscle, on a log axis because response sizes span orders of magnitude."""
    fig, ax = plt.subplots(figsize=(9, 8))
    ax.set_xscale("log")
    sns.boxplot(data=df, y="muscle", x=value_col, order=muscle_order, ax=ax, showfliers=False)
    ax.set_title(title)
    plain_log(ax.xaxis)
    fig.tight_layout()
    fig.savefig(FIGDIR / filename, dpi=150)


def save_heatmap(df, muscle_order, value_col, title, filename, cmap, fmt, cbar_label):
    """Median value for every muscle-by-protocol combination."""
    pivot = df.pivot_table(index="muscle", columns="protocol", values=value_col,
                           aggfunc="median").reindex(muscle_order)
    pivot = pivot.mask(pivot <= 0)       # a log color scale can't show 0 or negative
    fig, ax = plt.subplots(figsize=(9, 8))
    sns.heatmap(pivot, annot=True, fmt=fmt, cmap=cmap, norm=LogNorm(), ax=ax,
                linewidths=0.5, linecolor="white", cbar_kws={"label": cbar_label})
    tidy_colorbar(ax)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(FIGDIR / filename, dpi=150)
    return pivot


def build_master():
    """Run every raw recording through the pipeline and stack the results into one table."""
    manifest = pd.read_excel(MANIFEST_FILE, sheet_name="draft-pharma")
    config = yaml.safe_load(open(CONFIG_FILE))
    frames = []
    for csv_file in sorted((ROOT / "data" / "raw").glob("*.csv")):
        try:
            frames.append(process_file(csv_file, manifest, config))
        except ValueError as e:
            print(f"SKIP {csv_file.name}: {e}")
    df = pd.concat(frames, ignore_index=True)
    # The table splits protocol into family and variant; rejoin them for figure labels.
    df["protocol"] = (df["protocol_1"] + "_" + df["protocol_2"].fillna("")).str.rstrip("_")
    print(f"{len(df)} rows across {len(frames)} files")
    return df


def main():
    df = build_master()
    muscle_order = df.groupby("muscle")["auc"].median().sort_values(ascending=False).index

    # Figures 1-2 — value by muscle (horizontal so the labels have room).
    save_boxplot(df, muscle_order, "auc", "Evoked response size (AUC) by muscle", "auc_by_muscle.png")
    save_boxplot(df, muscle_order, "pk_pk", "Peak-to-peak by muscle", "pkpk_by_muscle.png")

    # Figures 3-4 — median value per muscle per protocol.
    pivot_auc = save_heatmap(df, muscle_order, "auc", "Median AUC — muscle x protocol",
                             "heatmap_auc.png", cmap="viridis", fmt=".0f", cbar_label="median AUC")
    save_heatmap(df, muscle_order, "pk_pk", "Median peak-to-peak — muscle x protocol",
                 "heatmap_pkpk.png", cmap="magma", fmt=".2f", cbar_label="median Pk-Pk")

    # Figure 5 — muscles grouped by the shape of their response across protocols.
    pattern_data = pivot_auc.dropna(how="all").fillna(0)      # clustering can't take blanks
    clustermap = sns.clustermap(
        pattern_data,
        standard_scale=0,          # rescale each muscle 0-1 so shape matters, not size
        cmap="viridis",
        figsize=(8, 9),
        linewidths=0.5,
        cbar_kws={"label": "AUC (per-muscle, 0–1)"},
    )
    clustermap.ax_col_dendrogram.set_title("Muscles clustered by response pattern")
    clustermap.savefig(FIGDIR / "clustermap_auc.png", dpi=150, bbox_inches="tight")

    # Figure 6 — one raw LAPB response with the two measurement windows shaded.
    # found by protocol rather than by name, so no subject code or session time is
    # written into this repository
    csv_file = sorted((ROOT / "data" / "raw").glob("*_TMS_120_*.csv"))[0]
    manifest = pd.read_excel(MANIFEST_FILE, sheet_name="draft-pharma")
    config = yaml.safe_load(open(CONFIG_FILE))
    sampling_rate = config["sampling_rate_hz"]

    meta = parse_filename(csv_file)
    # the windows this protocol was actually measured with
    prestim_ms = config["windows_ms"]["prestim"]
    response_ms = pick_window(config["windows_ms"]["response"], meta["protocol_1"])

    data = pd.read_csv(csv_file, header=None).to_numpy()
    lineup = get_lineup(meta["_subject_token"], meta["_date_token"], manifest)
    muscle_channel = [c for c, name in lineup.items() if name == "LAPB"][0]
    trigger_channel = pick_trigger(
        meta["protocol_1"],
        {c: name for c, name in lineup.items() if name.startswith("trigger")},
    )
    pulse_start = detect_pulses(data[:, trigger_channel], config["trigger_threshold"])[2]

    window = data[pulse_start - 500 : pulse_start + 400, muscle_channel]
    time_ms = (np.arange(len(window)) - 500) / sampling_rate * 1000
    plt.figure(figsize=(9, 4))
    plt.plot(time_ms, window)
    plt.axvspan(*prestim_ms, color="gray", alpha=.2, label="baseline")
    plt.axvspan(*response_ms, color="green", alpha=.2, label="response")
    plt.axvline(0, color="r", ls="--", label="pulse")
    plt.xlabel("ms from pulse")
    plt.ylabel("EMG")
    plt.legend()
    plt.title("LAPB MEP — one epoch")
    plt.tight_layout()
    plt.savefig(FIGDIR / "epoch_lapb.png", dpi=150, bbox_inches="tight")

    # Figure 7 — peak-to-peak against AUC, log-log since both span orders of magnitude.
    scatter_fig, scatter_ax = plt.subplots(figsize=(8, 7))
    positive_only = df[(df["pk_pk"] > 0) & (df["auc"] > 0)]   # log axes can't show 0 or negative
    sns.scatterplot(data=positive_only, x="pk_pk", y="auc", hue="protocol",
                    alpha=0.6, ax=scatter_ax)
    scatter_ax.set_xscale("log")
    scatter_ax.set_yscale("log")
    plain_log(scatter_ax.xaxis)
    plain_log(scatter_ax.yaxis)
    scatter_ax.set_title("Peak-to-peak vs AUC by protocol")
    scatter_fig.tight_layout()
    scatter_fig.savefig(FIGDIR / "scatter_pkpk_vs_auc.png", dpi=150)

    # Figure 8 — the spread of AUC per muscle, with every individual pulse drawn on top.
    violin_fig, violin_ax = plt.subplots(figsize=(9, 8))
    sns.violinplot(data=df, y="muscle", x="auc", order=muscle_order, inner=None,
                   log_scale=True, color="lightsteelblue", ax=violin_ax)
    sns.stripplot(data=df, y="muscle", x="auc", order=muscle_order, color="k",
                  size=3, alpha=.4, ax=violin_ax)
    plain_log(violin_ax.xaxis)
    violin_ax.set_title("AUC distribution by muscle (violin + individual pulses)")
    violin_fig.tight_layout()
    violin_fig.savefig(FIGDIR / "violin_auc_by_muscle.png", dpi=150)

    # Figure 9 — how the measurements relate to each other, logged because they are skewed.
    pair_data = df.loc[(df["pk_pk"] > 0) & (df["auc"] > 0),
                       ["pk_pk", "auc", "baseline", "protocol"]].copy()
    pair_data["pk_pk"] = np.log10(pair_data["pk_pk"])
    pair_data["auc"] = np.log10(pair_data["auc"])
    pair_data = pair_data.rename(columns={"pk_pk": "log10(pk_pk)", "auc": "log10(auc)"})
    pairgrid = sns.pairplot(pair_data, hue="protocol", plot_kws={"alpha": 0.5, "s": 15})
    pairgrid.figure.suptitle("Pairwise feature relationships by protocol", y=1.02)
    pairgrid.savefig(FIGDIR / "pairplot_features.png", dpi=150, bbox_inches="tight")

    # Figure 10 — mean AUC per muscle on a linear axis, since bars need a true zero.
    bar_fig, bar_ax = plt.subplots(figsize=(9, 8))
    sns.barplot(data=df, y="muscle", x="auc", order=muscle_order, ax=bar_ax)
    bar_ax.set_title("Mean AUC by muscle (95% CI)")
    bar_fig.tight_layout()
    bar_fig.savefig(FIGDIR / "barplot_auc_by_muscle.png", dpi=150)

    print(f"Saved figures to {FIGDIR}")
    plt.show()


if __name__ == "__main__":
    main()
