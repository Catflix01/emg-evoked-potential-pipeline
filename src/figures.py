"""Build the figures, and hand them back rather than saving them.

Both front ends draw from here: visuals.py saves what it gets, the web app displays it.
Keeping the drawing in one place means a figure cannot mean one thing on screen and
something else in a file.

Nothing here imports pyarrow or joblib, so it runs in a browser as well as a terminal.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.ticker import ScalarFormatter, NullFormatter, NullLocator

# The three figures the browser version shows are drawn with matplotlib alone, because
# seaborn has no build in Pyodide and requiring it stops the whole app from starting.
# The richer extras below still use it, and import it only when called.
plt.rcParams.update({
    "axes.grid": True, "grid.color": "white", "grid.linewidth": 1.2,
    "axes.facecolor": "#eaeaf2", "axes.edgecolor": "none",
    "axes.titlesize": 15, "axes.labelsize": 12, "figure.facecolor": "white",
})


def _seaborn():
    """Import seaborn only where it is genuinely needed, with a useful message."""
    try:
        import seaborn as sns
    except ImportError as e:
        raise ImportError(
            "This figure needs seaborn, which has no browser build. It is available "
            "in the command-line version: python main.py figures"
        ) from e
    sns.set_theme(style="whitegrid", context="talk")
    return sns


def plain_log(axis):
    """Show plain numbers (1, 10, 100) on a log axis instead of 10^x."""
    formatter = ScalarFormatter()
    formatter.set_scientific(False)
    axis.set_major_formatter(formatter)
    axis.set_minor_formatter(NullFormatter())


def tidy_colorbar(ax):
    """Give a colorbar plain-number ticks and no minor-tick clutter."""
    colorbar = ax.collections[0].colorbar
    plain_log(colorbar.ax.yaxis)
    colorbar.ax.yaxis.set_minor_locator(NullLocator())


def muscle_order(df, value_col="auc"):
    """Muscles sorted by how large their response was, biggest first."""
    return df.groupby("muscle")[value_col].median().sort_values(ascending=False).index


def response_by_muscle(df, value_col="auc", title=None):
    """Which muscles responded at all.

    A log axis because response sizes run from noise to several volts, and a linear
    axis would flatten every small muscle against zero.
    """
    order = list(muscle_order(df, value_col))
    values = [df.loc[df.muscle == m, value_col].dropna().to_numpy() for m in order]
    fig, ax = plt.subplots(figsize=(9, 8))
    ax.set_xscale("log")
    box = ax.boxplot(values, vert=False, showfliers=False, patch_artist=True,
                     tick_labels=order, widths=0.6)
    for patch in box["boxes"]:
        patch.set_facecolor("#4c72b0")
        patch.set_alpha(.85)
    for part in ("medians", "whiskers", "caps"):
        for line in box[part]:
            line.set_color("#2a2a2a")
    ax.invert_yaxis()                      # largest response at the top
    ax.set_xlabel(value_col)
    ax.set_title(title or f"Response size ({value_col}) by muscle")
    plain_log(ax.xaxis)
    fig.tight_layout()
    return fig


def muscle_by_protocol(df, value_col="auc", cmap="viridis", fmt=".0f", title=None):
    """Did each protocol do what it was supposed to.

    The target muscle should stand out under its own protocol; if it does not, either
    the stimulation missed or the channel lineup is wrong.
    """
    order = muscle_order(df, value_col)
    pivot = (df.pivot_table(index="muscle", columns="protocol", values=value_col,
                            aggfunc="median").reindex(order))
    pivot = pivot.mask(pivot <= 0)          # a log colour scale cannot show 0
    fig, ax = plt.subplots(figsize=(9, 8))
    values = np.ma.masked_invalid(pivot.to_numpy(dtype=float))
    image = ax.imshow(values, cmap=cmap, aspect="auto",
                      norm=LogNorm(vmin=np.nanmin(pivot.to_numpy()),
                                   vmax=np.nanmax(pivot.to_numpy())))
    ax.set_xticks(range(len(pivot.columns)), pivot.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)), pivot.index)
    ax.grid(False)
    # the number in each cell, so the figure can be read without the colour bar
    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            if not np.ma.is_masked(values[row, col]):
                ax.text(col, row, format(values[row, col], fmt),
                        ha="center", va="center", fontsize=9,
                        color="white" if values[row, col] < np.nanmedian(pivot) else "black")
    bar = fig.colorbar(image, ax=ax, label=f"median {value_col}")
    plain_log(bar.ax.yaxis)
    bar.ax.yaxis.set_minor_locator(NullLocator())
    ax.set_title(title or f"Median {value_col}: muscle by protocol")
    fig.tight_layout()
    return fig, pivot


def pk_pk_against_auc(df, title=None):
    """Do the two measurements agree with each other.

    They measure different things, so they should rise together without lying on a
    line. A cloud with no trend would mean one of them is not measuring the response.
    """
    positive = df[(df["pk_pk"] > 0) & (df["auc"] > 0)]
    fig, ax = plt.subplots(figsize=(8, 7))
    for colour, (protocol, group) in zip(
            plt.rcParams["axes.prop_cycle"].by_key()["color"] * 4,
            positive.groupby("protocol")):
        ax.scatter(group["pk_pk"], group["auc"], label=protocol, alpha=0.6, s=22, color=colour)
    ax.legend(title="protocol", fontsize=9)
    ax.set_xlabel("pk_pk")
    ax.set_ylabel("auc")
    ax.set_xscale("log")
    ax.set_yscale("log")
    plain_log(ax.xaxis)
    plain_log(ax.yaxis)
    ax.set_title(title or "Peak-to-peak against AUC, by protocol")
    fig.tight_layout()
    return fig


def one_epoch(signal, pulse_start, sampling_rate, prestim_ms, response_ms,
              before=500, after=400, title=None):
    """One raw trace with the measurement windows drawn on it.

    The check nothing else makes: if the shaded response window does not sit over the
    response, every number in the table is measuring the wrong stretch of signal.
    """
    window = signal[pulse_start - before : pulse_start + after]
    time_ms = (np.arange(len(window)) - before) / sampling_rate * 1000
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(time_ms, window)
    ax.axvspan(*prestim_ms, color="gray", alpha=.2, label="baseline window")
    ax.axvspan(*response_ms, color="green", alpha=.2, label="response window")
    ax.axvline(0, color="r", ls="--", label="stimulus")
    ax.set_xlabel("milliseconds from the stimulus")
    ax.set_ylabel("EMG")
    ax.legend()
    ax.set_title(title or "One recorded response")
    fig.tight_layout()
    return fig


def spread_by_muscle(df, value_col="auc", title=None):
    """The spread per muscle, with every individual pulse drawn on top."""
    sns = _seaborn()
    order = muscle_order(df, value_col)
    fig, ax = plt.subplots(figsize=(9, 8))
    sns.violinplot(data=df, y="muscle", x=value_col, order=order, inner=None,
                   log_scale=True, color="lightsteelblue", ax=ax)
    sns.stripplot(data=df, y="muscle", x=value_col, order=order, color="k",
                  size=3, alpha=.4, ax=ax)
    plain_log(ax.xaxis)
    ax.set_title(title or f"{value_col} per muscle, with individual pulses")
    fig.tight_layout()
    return fig


def mean_by_muscle(df, value_col="auc", title=None):
    """Mean per muscle with confidence intervals, on a linear axis.

    Bars need a true zero, so this one is not logged.
    """
    sns = _seaborn()
    order = muscle_order(df, value_col)
    fig, ax = plt.subplots(figsize=(9, 8))
    sns.barplot(data=df, y="muscle", x=value_col, order=order, ax=ax)
    ax.set_title(title or f"Mean {value_col} by muscle (95% CI)")
    fig.tight_layout()
    return fig


def muscles_clustered(pivot, title=None):
    """Muscles grouped by the shape of their response across protocols."""
    sns = _seaborn()
    data = pivot.dropna(how="all").fillna(0)     # clustering cannot take blanks
    grid = sns.clustermap(data, standard_scale=0, cmap="viridis", figsize=(8, 9),
                          linewidths=0.5, cbar_kws={"label": "per-muscle, 0-1"})
    grid.ax_col_dendrogram.set_title(title or "Muscles clustered by response pattern")
    return grid


def feature_pairs(df, title=None):
    """How the measurements relate to each other, logged because they are skewed."""
    sns = _seaborn()
    data = df.loc[(df["pk_pk"] > 0) & (df["auc"] > 0),
                  ["pk_pk", "auc", "baseline", "protocol"]].copy()
    data["pk_pk"] = np.log10(data["pk_pk"])
    data["auc"] = np.log10(data["auc"])
    data = data.rename(columns={"pk_pk": "log10(pk_pk)", "auc": "log10(auc)"})
    grid = sns.pairplot(data, hue="protocol", plot_kws={"alpha": 0.5, "s": 15})
    grid.figure.suptitle(title or "Pairwise relationships by protocol", y=1.02)
    return grid
