"""Turn raw EMG recordings into one tidy table: a row per muscle per stimulus pulse.

The reasoning behind the less obvious choices lives in docs/pipeline-notes.md.
"""
from pathlib import Path
import re
import pandas as pd
import numpy as np
import yaml
from datetime import datetime

from cusum import timing_values

# Which trigger channel each protocol family is expected to fire on. The pipeline finds
# the trigger by seeing which channel actually fired; this is kept as a cross-check, so a
# mislabelled file shows up as a disagreement rather than passing silently.
PROTOCOL_TRIGGER = {
    "TMS": "trigger_tms",      # brain Magventure/Magstim
    "SIC": "trigger_tms",      # brain (SIC and ICI are interchangeable)
    "ICI": "trigger_tms",
    "BBV": "trigger_tms",      # brain control data, SCAP studies
    "SBV": "trigger_tms",
    "INT": "trigger_tms",      # control collection during an intervention
    "TSS": "trigger_tscs",     # spinal
    "PNS": "trigger_tscs",     # peripheral
    "PAD": "trigger_tscs",
    "HSD": "trigger_tscs",
    "BSV": "trigger_tscs",     # spinal control data, SCAP studies
    "SSV": "trigger_tscs",
}
# Companion files holding stimulus intensities rather than EMG. They parse like ordinary
# recordings, so they have to be excluded by name or they produce confident nonsense.
NOT_A_RECORDING = "_full_data"
# Reserved for a second response; nothing fills these in yet — see docs/pipeline-notes.md.
PLACEHOLDER_TEXT_COLS = ["2nd_response_window"]
PLACEHOLDER_NUM_COLS = [
    "2nd_pk_pk", "2nd_auc",
    "2nd_response_onset", "2nd_response_offset", "2nd_emg_resuming",
]
PLACEHOLDER_COLS = PLACEHOLDER_TEXT_COLS + PLACEHOLDER_NUM_COLS
# The column order of docs/Table-layout.csv, with baseline added at the end.
SCHEMA = [
    "study", "group", "subject_ID", "visit", "timepoint", "experiment",
    "target_side", "target_muscle", "protocol_1", "protocol_2",
    "date", "time", "session",
    "muscle", "channel", "stim_channel", "pulse", "isi_ms", "is_active",
    "prestim_window", "prestim_pk_pk", "prestim_auc",
    "response_window", "pk_pk", "auc",
    "2nd_response_window", "2nd_pk_pk", "2nd_auc",
    "response_onset", "response_offset", "emg_resuming",
    "2nd_response_onset", "2nd_response_offset", "2nd_emg_resuming",
    "n_pulses_dropped",
    "baseline", "onset_blanked_ms",
]
# The shape of each piece of a recording's filename, and the column each part becomes.
# Read the (?P<name> ...) bits as "call this piece <name>"; the rest describes its shape:
#   \d = a digit    [A-Z] = a capital letter    + = one or more    ? = optional

SUBJECT_TOKEN = re.compile(r"""
    ^ (?P<study>      [A-Z]+\d+ )     
      (?P<group>      [A-Z]     )     
      (?P<subject_ID> \d+       ) $   
""", re.VERBOSE)

VISIT_TOKEN = re.compile(r"""
    ^ V (?P<visit>     \d+ )          
      T (?P<timepoint> \d+ ) $        
""", re.VERBOSE)

TARGET_TOKEN = re.compile(r"""
    ^ (?P<target_side>   [LR] )?      
      (?P<target_muscle> .+   ) $     
""", re.VERBOSE)

DATETIME_TOKEN = re.compile(r"""
    ^ (?P<date>   \d{8} ) -           
      (?P<hour>   \d{2} ) -           
      (?P<minute> \d{2} ) -           
      (?P<second> \d{2} ) $           
""", re.VERBOSE)

# A session folder, e.g. DEMO1S01_V1E1_01012024. The experiment number lives only here —
# the filenames inside carry V1T0 and never mention E1.
SESSION_FOLDER = re.compile(r"""
    ^ [A-Z]+\d+[A-Z]\d+ _             # DEMO1S01
      V\d+ E (?P<experiment> \d+ )    # V1E1
      _ \d{8}                         # 01012024
""", re.VERBOSE)


def _as_number(value):
    # Filename pieces arrive as text; turn the ones that are purely digits into numbers.
    if value is not None and value.isdigit():
        return int(value)
    return value


def _split_token(pattern, token):
    # Pull the named pieces out of one filename token, or blanks if it doesn't fit the shape.
    match = pattern.match(token)
    if not match:
        return {name: None for name in pattern.groupindex}
    return {name: _as_number(value) for name, value in match.groupdict().items()}


def parse_filename(csv_path):
    # Read the study, subject, visit, target and protocol out of a recording's filename.
    name = Path(csv_path).name
    tokens = Path(csv_path).stem.split("_")

    # Find the date-time piece rather than counting underscores, because the protocol
    # can be one, two or three pieces wide (PNS_Mmx, SIC_025, PNS_010_sec).
    date_index = next((i for i, t in enumerate(tokens) if DATETIME_TOKEN.match(t)), None)
    if date_index is None or date_index < 4:
        raise ValueError(f"{name}: no MMDDYYYY-HH-MM-SS token after subject/visit/target/protocol")

    stamp = DATETIME_TOKEN.match(tokens[date_index])
    date_token = stamp["date"]
    protocol_tokens = tokens[3:date_index]

    return {
        # Keys starting with _ are for internal use and get dropped from the output table.
        "_subject_token": tokens[0],
        "_date_token": date_token,
        **_split_token(SUBJECT_TOKEN, tokens[0]),
        **_split_token(VISIT_TOKEN, tokens[1]),
        **_split_token(TARGET_TOKEN, tokens[2]),
        "protocol_1": protocol_tokens[0],
        "protocol_2": "_".join(protocol_tokens[1:]) or None,
        "date": datetime.strptime(date_token, "%m%d%Y").date(),
        # The clock time separates two runs of the same protocol on the same day.
        "time": f"{stamp['hour']}:{stamp['minute']}:{stamp['second']}",
    }


def session_from_path(csv_path):
    """Read the session folder name and its experiment number from a recording's path.

    Recordings sit at <subject>/<session>/<protocol folder>/file.csv, so the session is
    two levels up. A flat folder has no session, and both fields come back blank.
    """
    parents = Path(csv_path).resolve().parents
    for folder in list(parents)[:3]:
        match = SESSION_FOLDER.match(folder.name)
        if match:
            return {"session": folder.name, "experiment": int(match["experiment"])}
    # No folder matched the expected shape. Keep the likeliest one so the row is still
    # traceable, rather than discarding what we do know.
    grandparent = parents[1].name if len(parents) > 1 else None
    return {"session": grandparent, "experiment": None}


def triggers_that_fired(data, triggers, threshold):
    """Which trigger channels actually carry pulses, and where.

    The protocol name is not consulted. Every protocol lights exactly one trigger and
    leaves the others silent, except the paired brain+spine protocols which light two —
    so asking the data is both simpler and able to handle protocols nothing knows about.
    """
    fired = {}
    for channel in triggers:
        if channel >= data.shape[1]:
            continue
        starts = detect_pulses(data[:, channel], threshold)
        if len(starts):
            fired[channel] = starts
    return fired


def pair_stimuli(first_starts, second_starts, sampling_rate, max_gap_ms=1000):
    """Match each stimulus on one channel with the nearest one on the other.

    Paired brain+spine protocols fire both stimulators per trial. The response is
    measured from the later of the two — the test stimulus — and the gap between them
    is recorded as the inter-stimulus interval.
    """
    max_gap = max_gap_ms / 1000 * sampling_rate
    anchors, intervals = [], []
    for first in first_starts:
        nearest = min(second_starts, key=lambda s: abs(s - first))
        gap = abs(int(nearest) - int(first))
        if gap <= max_gap:
            anchors.append(max(int(first), int(nearest)))
            intervals.append(round(gap / sampling_rate * 1000, 2))
    return anchors, intervals


def get_lineup(participant, date, manifest):
    # Look up which muscle was recorded on which channel for one session.
    channel_labels = [c for c in manifest.columns if isinstance(c, int) and c <= 18]
    date = datetime.strptime(date, '%m%d%Y')
    is_participant = manifest["Participant"] == participant
    is_date = manifest["Date"] == date
    matching_rows = manifest[is_participant & is_date]
    if len(matching_rows) == 0:
        raise ValueError(f"No lineup found for {participant} on {date.date()}")
    if len(matching_rows) > 1:
        raise ValueError(f"Multiple rows matched for {participant} on {date.date()} — expected exactly 1")

    row = matching_rows.iloc[0]
    channel_names = {}

    for channel in channel_labels:
        value = row[channel]
        if pd.isna(value):
            continue
        channel_names[channel] = str(value).strip().strip("*")

    return channel_names


def pick_trigger(protocol, triggers):
    # Find which channel carries the stimulus trigger for this protocol.
    family = protocol.split("_")[0].upper()
    if family not in PROTOCOL_TRIGGER:
        raise ValueError(
            f"No trigger mapping for protocol family {family!r} (from {protocol!r}); "
            f"known families: {sorted(PROTOCOL_TRIGGER)}"
        )
    label = PROTOCOL_TRIGGER[family]

    matching_columns = [c for c, name in triggers.items() if name == label]
    if not matching_columns:
        raise ValueError(
            f"Protocol {protocol!r} needs {label!r}, but this session's lineup only "
            f"has {sorted(triggers.values())}"
        )
    if len(matching_columns) > 1:
        raise ValueError(f"Lineup has {label!r} on multiple columns: {matching_columns}")
    return matching_columns[0]


def detect_pulses(trigger_channel, threshold):
    # Find the sample where each stimulus pulse begins.
    above_threshold = np.where(trigger_channel > threshold)[0]
    if len(above_threshold) == 0:
        return above_threshold
    # A pulse stays above threshold for many samples; keep only the first of each run.
    is_first_sample = np.concatenate(([True], np.diff(above_threshold) > 1))
    return above_threshold[is_first_sample]


def pick_window(windows, protocol_family):
    # Use the family's own window if it has one, otherwise the default.
    if not isinstance(windows, dict):
        return windows
    return windows.get(protocol_family.upper(), windows.get("default"))


def window_label(window_ms):
    # How the window is written in the output, e.g. "-100 to -50 ms".
    if window_ms is None:
        return None
    start, end = window_ms
    return f"{start:g} to {end:g} ms"


def window_in_samples(window_ms, sampling_rate):
    # Milliseconds from the stimulus -> sample offsets. Rounded, not truncated, because
    # a window can start on a half-millisecond (PNS begins at 3.5 ms).
    return [round(ms / 1000 * sampling_rate) for ms in window_ms]


def epoch_features(signal, pulse_start,
                   baseline_start, baseline_end, response_start, response_end):
    # Measure the baseline and response windows of one pulse, returning a dict of metrics.
    prestim = signal[pulse_start + baseline_start : pulse_start + baseline_end]
    baseline = prestim.mean()
    # Both windows are baseline-corrected so a channel's resting offset can't inflate its AUC.
    prestim_corrected = prestim - baseline
    response = signal[pulse_start + response_start : pulse_start + response_end] - baseline
    return {
        "prestim_pk_pk": float(np.ptp(prestim_corrected)),
        "prestim_auc": float(np.trapezoid(np.abs(prestim_corrected))),
        "pk_pk": float(np.ptp(response)),
        "auc": float(np.trapezoid(np.abs(response))),
        "baseline": float(baseline),
    }


def process_file(csv_path, manifest, config):
    # Measure every muscle's response to every pulse in one recording.
    meta = parse_filename(csv_path)
    data = pd.read_csv(csv_path, header=None).to_numpy()
    lineup = get_lineup(meta["_subject_token"], meta["_date_token"], manifest)
    muscles  = {c: name for c, name in lineup.items() if not name.startswith("trigger")}
    triggers = {c: name for c, name in lineup.items() if name.startswith("trigger")}

    # Ask which trigger channels fired, rather than looking the protocol up.
    sampling_rate = config["sampling_rate_hz"]
    fired = triggers_that_fired(data, triggers, config["trigger_threshold"])
    intervals = None
    if not fired:
        raise ValueError(f"No trigger over {config['trigger_threshold']} on any of "
                         f"{sorted(triggers.values())} in {Path(csv_path).name}")
    if len(fired) == 1:
        trigger_column, pulse_starts = next(iter(fired.items()))
    elif len(fired) == 2:
        # A paired brain+spine protocol: measure from the later stimulus of each pair.
        (first_col, first_starts), (second_col, second_starts) = sorted(fired.items())
        pulse_starts, intervals = pair_stimuli(first_starts, second_starts, sampling_rate)
        if not pulse_starts:
            raise ValueError(f"Two triggers fired in {Path(csv_path).name} but no pair "
                             f"fell close enough together to be one trial")
        trigger_column = second_col
    else:
        raise ValueError(f"{len(fired)} trigger channels fired in {Path(csv_path).name} "
                         f"(columns {sorted(fired)}); expected one, or two if paired")

    # Cross-check against what this protocol family is expected to use.
    expected = PROTOCOL_TRIGGER.get(meta["protocol_1"].upper())
    trigger_mismatch = bool(expected) and triggers.get(trigger_column) != expected

    # Choose this protocol's windows, then convert them to sample counts.
    windows = config["windows_ms"]
    prestim_ms = windows["prestim"]
    response_ms = pick_window(windows["response"], meta["protocol_1"])
    baseline_start, baseline_end = window_in_samples(prestim_ms, sampling_rate)
    response_start, response_end = window_in_samples(response_ms, sampling_rate)

    # Drop pulses sitting too close to either end of the recording to measure.
    n_samples = len(data)
    pulses = [(number, start) for number, start in enumerate(pulse_starts, start=1)
              if start + baseline_start >= 0 and start + response_end <= n_samples]
    dropped = len(pulse_starts) - len(pulses)
    if not pulses:
        raise ValueError(f"All {len(pulse_starts)} pulses in {Path(csv_path).name} fall too "
                         f"close to the recording edges to measure")

    # The inter-stimulus interval, for paired protocols only.
    interval_by_pulse = {}
    if intervals is not None:
        kept = [number for number, _ in pulses]
        interval_by_pulse = dict(zip(kept, intervals))

    # One row per muscle per pulse, plus the response timing per muscle.
    settings = config.get("cusum", {})
    active_above = settings.get("active_above_pk_pk", 0.05)
    rows = []
    for channel, muscle in muscles.items():
        signal = data[:, channel]
        measured = [epoch_features(signal, start, baseline_start, baseline_end,
                                   response_start, response_end) for _, start in pulses]
        # Contracting muscles carry visibly more pre-stimulus activity than resting ones.
        is_active = bool(np.median([m["prestim_pk_pk"] for m in measured]) > active_above)
        timing = timing_values(
            signal, [start for _, start in pulses], sampling_rate,
            before_ms=settings.get("epoch_before_ms", 100),
            after_ms=settings.get("epoch_after_ms", 150),
            is_active=is_active,
            silent_period_end_ms=settings.get("silent_period_end_ms", 300),
            # Nothing can arrive before the response window opens, so anything
            # earlier is the stimulator's own artifact rather than muscle.
            blank_until_ms=response_ms[0],
        )
        for (pulse, _), features in zip(pulses, measured):
            rows.append({"muscle": muscle, "channel": channel, "pulse": pulse,
                         "isi_ms": interval_by_pulse.get(pulse), "is_active": is_active,
                         **features, **timing})

    results = pd.DataFrame(rows)

    # Attach the identifiers that apply to the whole recording.
    for key, value in meta.items():
        if not key.startswith("_"):
            results[key] = value
    for key, value in session_from_path(csv_path).items():
        results[key] = value
    # Which channel carried the stimulus, for finding this response again in NewQuant.
    results["stim_channel"] = trigger_column
    results["n_pulses_dropped"] = dropped
    # Record the windows these numbers actually came from.
    results["prestim_window"] = window_label(prestim_ms)
    results["response_window"] = window_label(response_ms)
    for column in PLACEHOLDER_NUM_COLS:
        results[column] = np.nan
    for column in PLACEHOLDER_TEXT_COLS:
        results[column] = pd.Series(pd.NA, index=results.index, dtype="string")

    results = results.reindex(columns=SCHEMA)
    results.attrs["trigger_mismatch"] = trigger_mismatch
    results.attrs["trigger_label"] = triggers.get(trigger_column)
    return results


READABLE_DECIMALS = 4


def write_results(master, outputs_dir):
    """Write the full-precision table for the code, and a rounded one for people.

    The CSV is a view for reading in Excel — rounding it cannot affect any analysis,
    which reads the parquet. Four decimals rather than two because two would flatten a
    third of the baseline column to 0.00; see docs/pipeline-notes.md.
    """
    outputs_dir.mkdir(exist_ok=True)
    master.to_parquet(outputs_dir/"master_results.parquet", index=False)
    master.round(READABLE_DECIMALS).to_csv(outputs_dir/"master_results.csv", index=False)


# Folders that hold CSVs but never raw recordings.
#
# Two kinds. Development folders, because pointing the pipeline at a project directory
# would otherwise pick up the virtual environment's own test data: numpy alone ships
# dozens of .csv files.
#
# And the study's own output folders. DATA_FOR_PROCESSING keeps raw recordings in
# ALL-DATA, with siblings holding results. Without these, pointing at a study root would
# walk into 2.PROCESSED-DATA and 7.CLEAN-DATA and measure previous results as though they
# were recordings, which is worse than failing: it is measuring a measurement.
NOT_DATA_FOLDERS = {
    ".venv", "venv", "outputs", "docs", "notebooks", "__pycache__",
    "site-packages", "node_modules",
    "ARCHIVE", "CODE",
    "1.CROSS-CHECK", "2.PROCESSED-DATA", "3.REORDER-DATA", "4.DEMOGRAPHICS",
    "5.OTHER-DATA", "6.CONCATENATED", "7.CLEAN-DATA", "8.PRETTY-FIGURES",
}


def find_recordings(folder):
    """Every recording under a folder, including subfolders.

    Skips folders that never hold recordings, and the recruitment-curve companion files,
    which carry stimulus intensities rather than EMG but are named closely enough to
    parse as ordinary recordings.
    """
    def is_recording(path):
        if NOT_A_RECORDING in path.name:
            return False
        return not any(part in NOT_DATA_FOLDERS or part.startswith(".")
                       for part in path.relative_to(folder).parts[:-1])

    root = Path(folder)
    return sorted(f for f in root.rglob("*.csv") if is_recording(f))


def _process_safe(csv_path, manifest, config):
    """Process one recording. Returns (table, skip-reason); exactly one is None."""
    try:
        return process_file(csv_path, manifest, config), None
    except ValueError as e:
        return None, str(e)


def skip_row(csv_path, reason, data_root):
    """One line of the skip report, with as much identity as parsing managed to recover."""
    try:
        meta = parse_filename(csv_path)
    except ValueError:
        meta = {}
    try:
        where = str(Path(csv_path).resolve().relative_to(Path(data_root).resolve()))
    except ValueError:
        where = Path(csv_path).name
    return {"file": where,
            "session": session_from_path(csv_path)["session"],
            "protocol_1": meta.get("protocol_1"),
            "protocol_2": meta.get("protocol_2"),
            "reason": reason}


def data_folder(config, root):
    """Where to look for recordings: data_root if set, otherwise the local sample."""
    configured = config.get("data_root")
    return Path(configured).expanduser() if configured else root / "data" / "raw"


def main(data=None):
    """Measure every recording and write the results to outputs/."""
    from joblib import Parallel, delayed  # pyright: ignore[reportMissingImports]
    root = Path(__file__).resolve().parent.parent
    config = yaml.safe_load(open(root/"config"/"params.yaml"))
    manifest = pd.read_excel(root/"docs"/"Centralized-NIDAQ-System-Pharma-1957-PRIMING.xlsx",
                             sheet_name=config.get("manifest_sheet", "draft-pharma"))
    (root/"outputs").mkdir(exist_ok=True)

    source = Path(data).expanduser() if data else data_folder(config, root)
    csv_files = find_recordings(source)
    print(f"{len(csv_files)} recordings under {source}")

    outcomes = Parallel(n_jobs=-1)(
        delayed(_process_safe)(f, manifest, config) for f in csv_files)

    results = [table for table, _ in outcomes if table is not None]
    skipped = [skip_row(f, reason, source)
               for f, (_, reason) in zip(csv_files, outcomes) if reason is not None]

    if not results:
        raise SystemExit(f"Nothing could be processed. {len(skipped)} recordings skipped.")

    master = pd.concat(results, ignore_index=True)
    write_results(master, root/"outputs")

    if skipped:
        pd.DataFrame(skipped).to_csv(root/"outputs"/"skipped_files.csv", index=False)
    print(f"{len(master)} rows from {len(results)} recordings, {len(skipped)} skipped"
          + (", see outputs/skipped_files.csv" if skipped else ""))
    return master


if __name__ == "__main__":
    main()
