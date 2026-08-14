"""Check the pipeline against real recordings, and print a report you can share.

    python src/selfcheck.py --data /path/to/study/tree

The report holds counts, filename patterns and millisecond values. It contains no EMG
samples and no patient details, so it can be pasted into an email or an issue while the
recordings stay on this machine.

It answers the questions that cannot be settled by unit tests: do the real folder names
parse, does any recording fire two triggers, does contraction detection pick out the
right files, and do the timing numbers land where physiology says they should.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))
from harmonize import (SESSION_FOLDER, PROTOCOL_TRIGGER, find_recordings, process_file,
                       parse_filename, session_from_path, data_folder)

# When a hand muscle's response should arrive, by how far the signal has to travel.
# Guides for reading the report, not pass/fail gates — a value outside them may be a
# real finding rather than a mistake.
PLAUSIBLE_ONSET_MS = {
    "peripheral": (3, 12),     # PNS: nerve at the wrist to the muscle
    "spinal": (8, 28),         # TSS: spinal cord to the muscle
    "cortical": (15, 35),      # TMS/SIC/ICI: motor cortex to the muscle
}
ONSET_BAND = {"PNS": "peripheral", "PAD": "peripheral", "HSD": "peripheral",
              "TSS": "spinal", "BSV": "spinal", "SSV": "spinal"}
PLAUSIBLE_CSP_MS = (50, 300)
BOUNDARY_MARGIN_MS = 2.0

PROVISIONAL = ["session", "experiment", "isi_ms", "is_active",
               "response_onset", "response_offset", "emg_resuming"]


def heading(text):
    return f"\n{text}\n{'-' * len(text)}"


class Names:
    """Session folder names, optionally replaced with neutral labels.

    Session folders are subject codes plus dates, so a plain report is fine inside the
    lab but not for sharing more widely. --anonymise swaps them for session-1, session-2
    and so on, kept stable within a report so the counts still line up.
    """

    def __init__(self, anonymise):
        self.anonymise = anonymise
        self.seen = {}

    def __call__(self, name):
        if not self.anonymise or name is None:
            return name
        # Both the session folder (DEMO1S01_V1E1_01012024) and the protocol folders inside
        # it (DEMO1S01_V1E1_TMS) start with the same subject and visit, so they share one
        # label. A trailing protocol name is kept — it identifies nobody; a trailing date
        # is dropped, because it does.
        parts = str(name).split("_")
        stem = "_".join(parts[:2])
        tail = parts[2] if len(parts) > 2 and not parts[2].isdigit() else ""
        if stem not in self.seen:
            self.seen[stem] = f"session-{len(self.seen) + 1}"
        return f"{self.seen[stem]}_{tail}" if tail else self.seen[stem]


def check_folders(recordings, label=None):
    label = label or (lambda name: name)
    lines = [heading("FOLDER STRUCTURE")]
    sessions, unmatched = {}, []
    for recording in recordings:
        found = session_from_path(recording)
        name = found["session"]
        if found["experiment"] is not None:
            sessions[name] = found["experiment"]
        elif name not in unmatched:
            unmatched.append(name)

    lines.append(f"  {len(sessions)} session folders parsed, "
                 f"{len(unmatched)} folder names did not match the expected pattern")
    for name, experiment in list(sessions.items())[:3]:
        lines.append(f"    parsed:     {label(name)}   -> experiment = {experiment}")
    for name in unmatched[:5]:
        lines.append(f"    unmatched:  {label(name)}")
    if not sessions:
        lines.append("    (a flat folder has no session structure — this is expected for data/raw)")
    return lines


def check_protocol_folders(recordings, has_sessions, label=None):
    """Which protocol subfolders exist. The legacy MATLAB only ever read *_TMS ones."""
    label = label or (lambda name: name)
    lines = [heading("PROTOCOL SUBFOLDERS")]
    names = sorted({r.parent.name for r in recordings})
    lines.append(f"  {len(names)} distinct folders holding recordings:")
    for name in names[:12]:
        lines.append(f"    {label(name)}")
    if not has_sessions:
        lines.append("  (flat folder — no protocol subfolders to compare against the legacy code)")
        return lines
    non_tms = [n for n in names if not n.endswith("_TMS")]
    if non_tms:
        lines.append(f"  {len(non_tms)} do NOT end in _TMS. The legacy MATLAB globbed only")
        lines.append("  '*_TMS', so recordings in these folders were never read by it:")
        for name in non_tms[:8]:
            lines.append(f"    {label(name)}")
    return lines


def check_recordings(recordings, manifest, config, lineup=None):
    """Process everything and summarise triggers, skips and timing."""
    tables, skips = [], []
    for recording in recordings:
        try:
            tables.append(process_file(recording, manifest, config, lineup=lineup))
        except Exception as e:
            skips.append({"protocol": recording.name.split("_")[3:5], "reason": str(e)})

    lines = [heading("PROCESSING")]
    lines.append(f"  {len(tables)} recordings processed, {len(skips)} skipped")

    if skips:
        lines.append(heading("SKIPPED — read this before trusting the results"))
        grouped = {}
        for skip in skips:
            key = skip["reason"].split(" in ")[0][:70]
            grouped[key] = grouped.get(key, 0) + 1
        for reason, count in sorted(grouped.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {count:>4}  {reason}")

    if not tables:
        return lines, None

    master = pd.concat(tables, ignore_index=True)

    lines.append(heading("TRIGGERS"))
    per_file = master.groupby(["protocol_1", "protocol_2"], dropna=False)
    paired = master[master.isi_ms.notna()]
    lines.append(f"  {per_file.ngroups} protocol combinations seen")
    lines.append(f"  {len(paired.groupby(['protocol_1','protocol_2'], dropna=False))} "
                 f"used two trigger channels (paired brain+spine)")
    if len(paired):
        lines.append(f"    inter-stimulus intervals: {paired.isi_ms.min():.1f} "
                     f"to {paired.isi_ms.max():.1f} ms")
    else:
        lines.append("    (no paired recording present — that branch is still untested)")
    for family, group in master.groupby("protocol_1"):
        expected = PROTOCOL_TRIGGER.get(family.upper(), "not in the table")
        lines.append(f"    {family:<6} fired channel(s) {sorted(group.stim_channel.unique())}"
                     f"   expected: {expected}")

    lines.append(heading("CONTRACTION DETECTION"))
    threshold = config.get("cusum", {}).get("active_above_pk_pk")
    active = master[master.is_active]
    lines.append(f"  threshold: median prestim_pk_pk > {threshold}")
    lines.append(f"  {master.is_active.sum()} rows active, {(~master.is_active).sum()} at rest")
    if len(active):
        lines.append("  active protocols — do these look right to you?")
        for (p1, p2), _ in active.groupby(["protocol_1", "protocol_2"], dropna=False):
            lines.append(f"    {p1}_{p2}")
    else:
        lines.append("  no recording was judged to be contracting, so the silent-period")
        lines.append("  columns (response_offset, emg_resuming) are blank everywhere.")

    lines.extend(check_timing(master))
    return lines, master


def check_timing(master):
    lines = [heading("TIMING")]
    found = master.dropna(subset=["response_onset"]).copy()
    if not len(found):
        lines.append("  no onsets detected")
        return lines

    found["margin_ms"] = found.response_onset - found.onset_blanked_ms
    target = found[found.muscle == found.target_side.fillna("") + found.target_muscle.fillna("")]

    lines.append("  target muscle, per protocol. Expected onset depends on how far the")
    lines.append("  signal travels — a peripheral M-wave arrives far sooner than a cortical MEP.")
    lines.append(f"    {'protocol':<9}{'onset':>9}{'blanked':>9}{'margin':>8}{'expected':>13}   ")
    for family, group in target.groupby("protocol_1"):
        onset = group.response_onset.median()
        blanked = group.onset_blanked_ms.median()
        margin = onset - blanked
        band_name = ONSET_BAND.get(family.upper(), "cortical")
        low, high = PLAUSIBLE_ONSET_MS[band_name]
        if margin <= BOUNDARY_MARGIN_MS:
            note = "ON ITS BLANKING BOUNDARY — not a measurement"
        elif low <= onset <= high:
            note = "[OK]"
        else:
            note = "[CHECK]"
        lines.append(f"    {family:<9}{onset:>7.1f}ms{blanked:>7.1f}ms{margin:>6.1f}ms"
                     f"{f'{low}-{high} ms':>13}   {note}")

    hugging = found[found.margin_ms <= BOUNDARY_MARGIN_MS]
    if len(hugging):
        lines.append(f"  {len(hugging)} of {len(found)} rows have an onset within "
                     f"{BOUNDARY_MARGIN_MS} ms of their blanking boundary.")
        lines.append("  Those are the edge of an exclusion window, not detected responses —")
        lines.append("  usually muscles the protocol was not targeting.")

    csp = master.dropna(subset=["emg_resuming", "response_offset"])
    if len(csp):
        duration = (csp.emg_resuming - csp.response_offset).median()
        ok = PLAUSIBLE_CSP_MS[0] <= duration <= PLAUSIBLE_CSP_MS[1]
        lines.append(f"  silent period: median {duration:.1f} ms "
                     f"{'[OK]' if ok else '[CHECK]'}")
    else:
        lines.append("  silent period: not computed (no contracting recording)")
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", help="folder of recordings; defaults to config data_root")
    parser.add_argument("--anonymise", action="store_true",
                        help="replace session folder names, which contain subject codes "
                             "and dates, with session-1, session-2 ...")
    args = parser.parse_args()
    label = Names(args.anonymise)

    config = yaml.safe_load(open(ROOT / "config" / "params.yaml"))
    source = Path(args.data).expanduser() if args.data else data_folder(config, ROOT)
    if not source.exists():
        raise SystemExit(f"No such folder: {source}")

    # A folder carrying its own manifest brings its own lineup — the demo set does, and a
    # published copy has no real manifest at all.
    local_manifest = source / "demo-manifest.xlsx"
    if local_manifest.exists():
        manifest = pd.read_excel(local_manifest)
    else:
        manifest = pd.read_excel(
            ROOT / "docs" / "Centralized-NIDAQ-System-Pharma-1957-PRIMING.xlsx",
            sheet_name=config.get("manifest_sheet", "draft-pharma"))
    recordings = find_recordings(source)

    report = [f"EMG PIPELINE SELF-CHECK", f"  {len(recordings)} recordings under {source}"]
    if not recordings:
        print("\n".join(report + ["  nothing to check"]))
        return

    has_sessions = any(session_from_path(r)["experiment"] is not None for r in recordings)
    report += check_folders(recordings, label)
    report += check_protocol_folders(recordings, has_sessions, label)
    lines, _ = check_recordings(recordings, manifest, config)
    report += lines

    report += [heading("PROVISIONAL COLUMNS"),
               "  These have never been checked against data known to be correct:",
               "    " + ", ".join(PROVISIONAL),
               "  Treat their values as unverified until this report has been reviewed."]
    report += [heading("WHAT THIS REPORT CONTAINS"),
               "  Counts, protocol names and millisecond values. No EMG samples."]
    if args.anonymise:
        report.append("  Session names replaced with neutral labels — safe to share outside the lab.")
    else:
        report.append("  Session folder names are shown, and those are subject codes plus")
        report.append("  dates. Re-run with --anonymise before sharing outside the lab.")
    print("\n".join(report))


if __name__ == "__main__":
    main()
