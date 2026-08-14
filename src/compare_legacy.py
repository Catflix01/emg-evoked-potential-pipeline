"""Compare this pipeline against the inherited MATLAB, on the same recordings.

    python src/compare_legacy.py --data <YOUR FOLDER>

No MATLAB needed. Each recording is measured twice — once the way
docs/legacy/EMG_Pipeline_A3_ProcessingData.m does it, once the way this pipeline does —
so the two can be compared row for row.

The expected result, and the reason this exists:

  Pk-Pk   identical, to floating-point. The legacy takes peak2peak(resp); this pipeline
          takes it after subtracting the baseline, and subtracting a constant cannot
          change a range. Agreement here means the windows, trigger detection and
          epoching all match.

  AUC     differs. The legacy integrates the raw trace; this pipeline subtracts the
          pre-stimulus baseline first. On a channel with a resting offset, most of the
          legacy value is that offset rather than muscle activity.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from harmonize import (parse_filename, get_lineup, triggers_that_fired, pick_window,
                       window_in_samples, find_recordings, data_folder)


def legacy_features(signal, pulse_start, prestim, response):
    """Exactly what EMG_Pipeline_A3_ProcessingData.m lines 171-178 compute.

        pre  = x( idx - 0.100*Fs : idx - 0.050*Fs );
        resp = x( idx + 0.010*Fs : idx + 0.070*Fs );
        P2P_matrix(i,m) = peak2peak(resp);
        AUC_matrix(i,m) = trapz(abs(resp));

    Note there is no baseline subtraction — that is the whole difference.
    """
    before_start, before_end = prestim
    after_start, after_end = response
    raw_response = signal[pulse_start + after_start : pulse_start + after_end]
    raw_prestim = signal[pulse_start + before_start : pulse_start + before_end]
    return {
        "legacy_pk_pk": float(np.ptp(raw_response)),
        "legacy_auc": float(np.trapezoid(np.abs(raw_response))),
        "legacy_prestim_pk_pk": float(np.ptp(raw_prestim)),
        "legacy_prestim_auc": float(np.trapezoid(np.abs(raw_prestim))),
    }


def compare_recording(csv_path, manifest, config, lineup=None):
    """Measure one recording both ways, one row per muscle per pulse.

    `lineup` behaves as it does in process_file: given one it is used, otherwise the
    manifest is consulted.
    """
    meta = parse_filename(csv_path)
    data = pd.read_csv(csv_path, header=None).to_numpy()
    if lineup is None:
        lineup = get_lineup(meta["_subject_token"], meta["_date_token"], manifest)
    muscles = {c: n for c, n in lineup.items() if not n.startswith("trigger")}
    triggers = {c: n for c, n in lineup.items() if n.startswith("trigger")}

    sampling_rate = config["sampling_rate_hz"]
    fired = triggers_that_fired(data, triggers, config["trigger_threshold"])
    if not fired:
        raise ValueError("no trigger fired")
    pulse_starts = sorted(fired.values(), key=len)[-1]

    prestim = window_in_samples(config["windows_ms"]["prestim"], sampling_rate)
    response = window_in_samples(
        pick_window(config["windows_ms"]["response"], meta["protocol_1"]), sampling_rate)

    rows = []
    for channel, muscle in muscles.items():
        signal = data[:, channel]
        for pulse, start in enumerate(pulse_starts, start=1):
            if start + prestim[0] < 0 or start + response[1] > len(data):
                continue
            baseline = signal[start + prestim[0] : start + prestim[1]].mean()
            corrected = signal[start + response[0] : start + response[1]] - baseline
            rows.append({
                "protocol": meta["protocol_1"], "muscle": muscle, "pulse": pulse,
                "baseline": float(baseline),
                "ours_pk_pk": float(np.ptp(corrected)),
                "ours_auc": float(np.trapezoid(np.abs(corrected))),
                **legacy_features(signal, start, prestim, response),
            })
    return pd.DataFrame(rows)


def summarise(comparison):
    """How closely the two agree, and whether the difference is explained."""
    pk_pk_gap = (comparison.ours_pk_pk - comparison.legacy_pk_pk).abs()
    auc_gap = comparison.legacy_auc - comparison.ours_auc

    # if the difference is electrode offset, it should equal |offset| x window length
    window_samples = comparison.legacy_auc.notna().sum() and 300
    predicted = comparison.baseline.abs() * window_samples
    explained = np.corrcoef(predicted, auc_gap)[0, 1] if len(comparison) > 2 else float("nan")

    return {
        "rows": len(comparison),
        "pk_pk_max_difference": float(pk_pk_gap.max()),
        "pk_pk_identical": bool(pk_pk_gap.max() < 1e-9),
        "auc_median_percent_change": float(
            ((comparison.ours_auc - comparison.legacy_auc) / comparison.legacy_auc * 100).median()),
        "auc_correlation": float(np.corrcoef(comparison.legacy_auc, comparison.ours_auc)[0, 1]),
        "auc_gap_explained_by_offset": float(explained),
    }


def per_muscle(comparison):
    """A table a reader can scan: offset, both AUCs, and what the offset alone predicts."""
    table = comparison.groupby("muscle").agg(
        resting_offset=("baseline", "mean"),
        legacy_auc=("legacy_auc", "median"),
        our_auc=("ours_auc", "median"),
    )
    table["gap"] = table.legacy_auc - table.our_auc
    table["gap_predicted_by_offset"] = table.resting_offset.abs() * 300
    table["legacy_that_is_offset_%"] = (table.gap / table.legacy_auc * 100).clip(0, 100)
    return table.sort_values("gap", ascending=False).round(3)


def report(comparison):
    s = summarise(comparison)
    lines = ["COMPARISON WITH THE INHERITED MATLAB PIPELINE", ""]
    lines.append(f"  {s['rows']} muscle-and-pulse rows, measured both ways from the same files")
    lines.append("")
    lines.append("  Pk-Pk")
    verdict = "IDENTICAL" if s["pk_pk_identical"] else "DIFFERS"
    lines.append(f"    {verdict} — largest difference {s['pk_pk_max_difference']:.2e}")
    if s["pk_pk_identical"]:
        lines.append("    The windows, trigger detection and epoching match the legacy exactly.")
    lines.append("")
    lines.append("  AUC")
    lines.append(f"    differs by a median of {s['auc_median_percent_change']:+.1f}%")
    lines.append(f"    correlation between the two: {s['auc_correlation']:.3f}")
    lines.append(f"    correlation between the gap and each channel's resting offset: "
                 f"{s['auc_gap_explained_by_offset']:.3f}")
    lines.append("")
    lines.append("    The legacy integrates the raw trace; this pipeline subtracts the")
    lines.append("    pre-stimulus baseline first. A correlation near 1.0 above means the")
    lines.append("    difference IS the electrode offset, not muscle signal.")
    lines.append("")
    lines.append("  Per muscle:")
    for line in per_muscle(comparison).to_string().splitlines():
        lines.append(f"    {line}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", help="folder of recordings; defaults to config data_root")
    args = parser.parse_args()

    config = yaml.safe_load(open(ROOT / "config" / "params.yaml"))
    source = Path(args.data).expanduser() if args.data else data_folder(config, ROOT)
    local_manifest = source / "demo-manifest.xlsx"
    manifest = pd.read_excel(local_manifest) if local_manifest.exists() else pd.read_excel(
        ROOT / "docs" / "Centralized-NIDAQ-System-Pharma-1957-PRIMING.xlsx",
        sheet_name=config.get("manifest_sheet", "draft-pharma"))

    frames = []
    for recording in find_recordings(source):
        try:
            frames.append(compare_recording(recording, manifest, config))
        except Exception as e:
            print(f"  skipped {recording.name}: {e}")
    if not frames:
        raise SystemExit(f"Nothing to compare under {source}")
    print(report(pd.concat(frames, ignore_index=True)))


if __name__ == "__main__":
    main()
