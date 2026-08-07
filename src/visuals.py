# src/visuals.py — write the figures to outputs/figures/
#
# The drawing itself lives in figures.py, so the web app shows exactly what this saves.
import sys
from pathlib import Path

import pandas as pd
import yaml
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from harmonize import (process_file, parse_filename, get_lineup, pick_trigger,
                       detect_pulses, pick_window, find_recordings)
import figures

MANIFEST_FILE = ROOT / "docs" / "Centralized-NIDAQ-System-Pharma-1957-PRIMING.xlsx"
CONFIG_FILE = ROOT / "config" / "params.yaml"
FIGDIR = ROOT / "outputs" / "figures"


def build_master(manifest=None, config=None, folder=None):
    """Run every recording through the pipeline and stack the results into one table."""
    manifest = pd.read_excel(MANIFEST_FILE, sheet_name="draft-pharma") if manifest is None else manifest
    config = yaml.safe_load(open(CONFIG_FILE)) if config is None else config
    folder = folder or ROOT / "data" / "raw"

    frames = []
    for csv_file in find_recordings(folder):
        try:
            frames.append(process_file(csv_file, manifest, config))
        except ValueError as e:
            print(f"SKIP {csv_file.name}: {e}")
    df = pd.concat(frames, ignore_index=True)
    print(f"{len(df)} rows across {len(frames)} files")
    return add_protocol_label(df)


def add_protocol_label(df):
    """The table splits protocol into family and variant; rejoin them for figure labels."""
    df = df.copy()
    df["protocol"] = (df["protocol_1"] + "_" + df["protocol_2"].fillna("")).str.rstrip("_")
    return df


def one_epoch_from_recording(csv_file, manifest, config, muscle="LAPB", pulse_index=2):
    """Pull one raw trace out of a recording, ready to plot with its windows shaded."""
    meta = parse_filename(csv_file)
    data = pd.read_csv(csv_file, header=None).to_numpy()
    lineup = get_lineup(meta["_subject_token"], meta["_date_token"], manifest)
    muscle_channel = [c for c, name in lineup.items() if name == muscle][0]
    trigger_channel = pick_trigger(
        meta["protocol_1"], {c: n for c, n in lineup.items() if n.startswith("trigger")})
    pulse_start = detect_pulses(data[:, trigger_channel], config["trigger_threshold"])[pulse_index]
    return {
        "signal": data[:, muscle_channel],
        "pulse_start": int(pulse_start),
        "sampling_rate": config["sampling_rate_hz"],
        "prestim_ms": config["windows_ms"]["prestim"],
        "response_ms": pick_window(config["windows_ms"]["response"], meta["protocol_1"]),
    }


def main():
    FIGDIR.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_excel(MANIFEST_FILE, sheet_name="draft-pharma")
    config = yaml.safe_load(open(CONFIG_FILE))
    df = build_master(manifest, config)

    figures.response_by_muscle(df, "auc").savefig(FIGDIR / "auc_by_muscle.png", dpi=150)
    figures.response_by_muscle(df, "pk_pk").savefig(FIGDIR / "pkpk_by_muscle.png", dpi=150)

    auc_fig, auc_pivot = figures.muscle_by_protocol(df, "auc", cmap="viridis", fmt=".0f")
    auc_fig.savefig(FIGDIR / "heatmap_auc.png", dpi=150)
    pkpk_fig, _ = figures.muscle_by_protocol(df, "pk_pk", cmap="magma", fmt=".2f")
    pkpk_fig.savefig(FIGDIR / "heatmap_pkpk.png", dpi=150)

    figures.muscles_clustered(auc_pivot).savefig(
        FIGDIR / "clustermap_auc.png", dpi=150, bbox_inches="tight")
    figures.pk_pk_against_auc(df).savefig(FIGDIR / "scatter_pkpk_vs_auc.png", dpi=150)
    figures.spread_by_muscle(df, "auc").savefig(FIGDIR / "violin_auc_by_muscle.png", dpi=150)
    figures.mean_by_muscle(df, "auc").savefig(FIGDIR / "barplot_auc_by_muscle.png", dpi=150)
    figures.feature_pairs(df).savefig(
        FIGDIR / "pairplot_features.png", dpi=150, bbox_inches="tight")

    # one raw trace, so the measurement windows can be seen sitting over the response
    csv_file = sorted((ROOT / "data" / "raw").glob("*_TMS_120_*.csv"))[0]
    epoch = one_epoch_from_recording(csv_file, manifest, config)
    figures.one_epoch(**epoch, title="LAPB response, one epoch").savefig(
        FIGDIR / "epoch_lapb.png", dpi=150, bbox_inches="tight")

    print(f"Saved figures to {FIGDIR}")
    plt.show()


if __name__ == "__main__":
    main()
