import pandas as pd
import pytest
import numpy as np
import yaml
from harmonize import get_lineup, epoch_features, process_file, parse_filename
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]      # src/tests/ -> repo root
MANIFEST = ROOT / "docs" / "Centralized-NIDAQ-System-Pharma-1957-PRIMING.xlsx"


def recording(protocol):
    """Find a real recording by protocol, so no subject code or session time is
    written into this repository.

    Recordings are not part of the repository, so a fresh clone has none — those
    tests skip rather than fail.
    """
    matches = sorted((ROOT / "data" / "raw").glob(f"*_{protocol}_*.csv"))
    if not matches:
        pytest.skip("no real recordings present; they are not part of the repository")
    return matches[0]


@pytest.fixture(scope="session")
def man():
    if not MANIFEST.exists():
        pytest.skip("manifest workbook not present; it is not part of the repository")
    return pd.read_excel(MANIFEST, sheet_name="draft-pharma")

def test_lapb_is_column_10(man):
    meta = parse_filename(recording("TMS_120"))
    assert get_lineup(meta["_subject_token"], meta["_date_token"], man)[10] == "LAPB"

def test_bad_date_raises(man):
    meta = parse_filename(recording("TMS_120"))
    with pytest.raises(ValueError):
        get_lineup(meta["_subject_token"], "01011999", man)


def test_epoch_features_known_answer():
    # a flat signal (baseline = 0), with a known shape in the response window
    signal = np.zeros(200)
    pulse_start = 100
    signal[pulse_start+1 : pulse_start+5] = [0, 4, 4, 0]     # the "response"

    f = epoch_features(signal, pulse_start,
                       baseline_start=-4, baseline_end=-1,
                       response_start=1, response_end=5)

    assert f["baseline"] == 0.0
    assert f["pk_pk"] == 4.0
    assert f["auc"] == 8.0
    # prestim window is flat here, so both prestim metrics collapse to zero
    assert f["prestim_pk_pk"] == 0.0
    assert f["prestim_auc"] == 0.0


def test_epoch_features_prestim_is_baseline_corrected():
    # constant DC offset in the prestim window: Pk-Pk and AUC must both ignore it
    signal = np.full(200, 3.0)
    pulse_start = 100
    f = epoch_features(signal, pulse_start,
                       baseline_start=-4, baseline_end=-1,
                       response_start=1, response_end=5)

    assert f["baseline"] == 3.0
    assert f["prestim_pk_pk"] == 0.0
    assert f["prestim_auc"] == 0.0     # would be ~6.0 without the correction


def test_epoch_features_prestim_measures_real_activity():
    signal = np.zeros(200)
    pulse_start = 100
    signal[pulse_start-4 : pulse_start-1] = [0, 2, 0]      # a blip in the prestim window
    f = epoch_features(signal, pulse_start,
                       baseline_start=-4, baseline_end=-1,
                       response_start=1, response_end=5)

    baseline = 2 / 3
    assert f["baseline"] == pytest.approx(baseline)
    assert f["prestim_pk_pk"] == pytest.approx(2.0)
    assert f["prestim_auc"] == pytest.approx(np.trapezoid(np.abs(np.array([0, 2, 0]) - baseline)))


@pytest.mark.parametrize("name, expected", [
    # the everyday two-token protocol
    ("P9S99_V1T0_LAPB_PNS_Mmx_02152023-14-18-25_eventonly.csv",
     {"study": "P9", "group": "S", "subject_ID": 99, "visit": 1, "timepoint": 0,
      "target_side": "L", "target_muscle": "APB",
      "protocol_1": "PNS", "protocol_2": "Mmx"}),
    ("P9S99_V1T0_LAPB_SIC_025_02152023-14-01-03_eventonly.csv",
     {"protocol_1": "SIC", "protocol_2": "025"}),
    # three-token protocol from the Filenames sheet — the old positional parse
    # put "sec" in the date field here
    ("P9S88_V4T1_RFCR_PNS_010_sec_04102025-09-30-00_eventonly.csv",
     {"study": "P9", "group": "S", "subject_ID": 88, "visit": 4, "timepoint": 1,
      "target_side": "R", "target_muscle": "FCR",
      "protocol_1": "PNS", "protocol_2": "010_sec"}),
])
def test_parse_filename_splits(name, expected):
    meta = parse_filename(name)
    for key, value in expected.items():
        assert meta[key] == value, key


def test_parse_filename_date_is_iso():
    meta = parse_filename("P9S99_V1T0_LAPB_PNS_Mmx_02152023-14-18-25_eventonly.csv")
    assert str(meta["date"]) == "2023-02-15"
    assert meta["_date_token"] == "02152023"     # raw form get_lineup still needs


def test_parse_filename_separates_the_clock_time():
    meta = parse_filename("P9S99_V1T0_LAPB_PNS_Mmx_02152023-14-18-25_eventonly.csv")
    assert meta["time"] == "14:18:25"


def test_time_tells_two_runs_of_one_protocol_apart():
    # same subject, visit, protocol and day — only the clock time differs
    early = parse_filename("P9S99_V1T0_LAPB_PNS_Mmx_02152023-09-05-00_eventonly.csv")
    late  = parse_filename("P9S99_V1T0_LAPB_PNS_Mmx_02152023-14-18-25_eventonly.csv")
    assert early["date"] == late["date"]
    assert early["time"] != late["time"]


def test_parse_filename_odd_visit_token_blanks_rather_than_raises():
    # V4E1 shows up in the legacy pipeline; the EMG in such a file is still good
    meta = parse_filename("P9S88_V4E1_LAPB_TMS_120_04102025-09-30-00_eventonly.csv")
    assert meta["visit"] is None
    assert meta["timepoint"] is None
    assert meta["study"] == "P9"                 # everything else still parses


def test_parse_filename_without_datetime_token_raises():
    with pytest.raises(ValueError):
        parse_filename("P9S99_V1T0_LAPB_PNS_Mmx_eventonly.csv")


@pytest.fixture(scope="session")
def cfg():
    return yaml.safe_load(open(ROOT / "config" / "params.yaml"))

@pytest.fixture(scope="session")
def tms_results(man, cfg):
    csv = recording("TMS_120")
    return process_file(csv, man, cfg)

def test_process_file_regression(tms_results):
    # Pinned from current output — change these only if you INTEND to change results.
    assert len(tms_results) == 168
    row = tms_results[(tms_results.muscle == "LAPB") & (tms_results.pulse == 3)].iloc[0]
    assert row.pk_pk == pytest.approx(1.175, rel=1e-3)
    assert row.auc   == pytest.approx(26.95378, rel=1e-3)


def test_find_recordings_ignores_folders_that_never_hold_data(tmp_path):
    """Pointed at a project folder it must not pick up a library's own test CSVs."""
    from harmonize import find_recordings
    (tmp_path / "session").mkdir()
    (tmp_path / "session" / "real_recording.csv").write_text("1,2\n")
    for junk in [".venv/lib/site-packages/numpy/tests", "outputs", "docs", "__pycache__"]:
        folder = tmp_path / junk
        folder.mkdir(parents=True)
        (folder / "philox-testset-1.csv").write_text("1,2\n")

    found = [f.name for f in find_recordings(tmp_path)]
    assert found == ["real_recording.csv"]


def test_find_recordings_skips_the_intensity_companion_files(tmp_path):
    from harmonize import find_recordings
    (tmp_path / "P9S99_V1T0_LAPB_TMS_REC_01012024-10-00-00_eventonly.csv").write_text("1\n")
    (tmp_path / "P9S99_V1T0_LAPB_TMS_REC_01012024-10-00-00_TMS_REC_full_data.csv").write_text("1\n")
    assert len(find_recordings(tmp_path)) == 1


def test_output_matches_the_declared_schema(tms_results):
    """SCHEMA in harmonize.py is the authoritative column layout."""
    from harmonize import SCHEMA
    assert list(tms_results.columns) == SCHEMA


def test_schema_matches_spec(tms_results):
    """SCHEMA still agrees with docs/Table-layout.csv, when that file is present.

    The spec sheet holds a real subject's measurements, so it is gitignored and will
    not exist in a fresh clone — hence the skip rather than a failure.
    """
    spec_file = ROOT / "docs" / "Table-layout.csv"
    if not spec_file.exists():
        pytest.skip("docs/Table-layout.csv is gitignored; SCHEMA is the source of truth")
    spec = [c for c in pd.read_csv(spec_file, nrows=0).columns if c != "source_file"]
    assert list(tms_results.columns)[:len(spec)] == spec
    # diagnostics that trail the agreed layout rather than sitting inside it
    assert list(tms_results.columns)[len(spec):] == ["baseline", "onset_blanked_ms"]


def test_source_file_is_gone(tms_results):
    assert "source_file" not in tms_results.columns


def test_placeholder_columns_are_empty(tms_results):
    from harmonize import PLACEHOLDER_COLS
    for col in PLACEHOLDER_COLS:
        assert tms_results[col].isna().all(), col


def test_window_columns_report_the_windows_actually_used(tms_results, cfg):
    from harmonize import window_label
    row = tms_results.iloc[0]
    assert row.prestim_window == window_label(cfg["windows_ms"]["prestim"])
    assert row.response_window == window_label(cfg["windows_ms"]["response"]["default"])
    assert row.response_window == "10 to 70 ms"          # TMS uses the default


def test_pns_gets_its_own_response_window(man, cfg):
    csv = recording("PNS_Mmx")
    pns = process_file(csv, man, cfg)
    assert pns["response_window"].unique().tolist() == ["3.5 to 25 ms"]
    # and the prestim window is shared with every other protocol
    assert pns["prestim_window"].unique().tolist() == ["-100 to -50 ms"]


def test_half_millisecond_window_rounds_rather_than_truncates():
    from harmonize import window_in_samples
    # 3.5 ms at 5000 Hz is 17.5 samples; truncating would silently shift the window
    assert window_in_samples([3.5, 25], 5000) == [18, 125]
    assert window_in_samples([10, 70], 5000) == [50, 350]


def test_unknown_family_falls_back_to_the_default_window():
    from harmonize import pick_window
    windows = {"default": [10, 70], "PNS": [3.5, 25]}
    assert pick_window(windows, "TMS") == [10, 70]
    assert pick_window(windows, "pns") == [3.5, 25]      # case-insensitive
    assert pick_window(windows, "BBV") == [10, 70]


def test_readable_csv_is_rounded_but_parquet_is_not(tms_results, tmp_path):
    from harmonize import write_results, READABLE_DECIMALS
    write_results(tms_results, tmp_path)
    full = pd.read_parquet(tmp_path / "master_results.parquet")
    readable = pd.read_csv(tmp_path / "master_results.csv")

    assert full["auc"].equals(tms_results["auc"])                      # untouched
    assert readable["auc"].equals(tms_results["auc"].round(READABLE_DECIMALS))
    # the readable view must not wipe out the small columns the way 2 dp would
    assert (readable["baseline"].abs() > 0).sum() == (tms_results["baseline"].abs() > 0).sum()


def test_stim_channel_is_the_trigger_channel(tms_results, man):
    # TMS fires on the trigger_tms channel; every row of the file shares it
    meta = parse_filename(recording("TMS_120"))
    lineup = get_lineup(meta["_subject_token"], meta["_date_token"], man)
    expected = [c for c, name in lineup.items() if name == "trigger_tms"][0]
    assert tms_results["stim_channel"].unique().tolist() == [expected]
    # it sits between the muscle's recording channel and the pulse number
    cols = list(tms_results.columns)
    assert cols[cols.index("channel") + 1] == "stim_channel"
    assert cols[cols.index("stim_channel") + 1] == "pulse"


def test_onset_is_blanked_to_the_response_window_start(tms_results, cfg, man):
    """Blanking must match the protocol's own window — PNS opens far earlier than TMS."""
    assert tms_results["onset_blanked_ms"].unique().tolist() == [10.0]

    pns = process_file(
        recording("PNS_Mmx"),
        man, cfg)
    assert pns["onset_blanked_ms"].unique().tolist() == [3.5]


def test_target_muscle_onset_clears_its_blanking_boundary(man, cfg):
    """The muscle the protocol targets should show a real response, well past the boundary.

    Muscles the protocol does not target often have no response at all, and the detector
    then returns the earliest sample it is allowed to look at. That is expected — the
    onset_blanked_ms column is what makes those cases visible.
    """
    for csv in sorted((ROOT / "data" / "raw").glob("*.csv")):
        result = process_file(csv, man, cfg)
        target = result[result.muscle == result.target_side + result.target_muscle]
        target = target.dropna(subset=["response_onset"])
        assert len(target), f"{csv.name}: target muscle produced no onset at all"
        margin = (target["response_onset"] - target["onset_blanked_ms"]).min()
        assert margin > 1.0, f"{csv.name}: target onset only {margin} ms past its boundary"


def test_boundary_hugging_onsets_stay_visible(man, cfg):
    """A reader must be able to tell a measurement from the edge of an exclusion."""
    csv = recording("TSS_200")
    result = process_file(csv, man, cfg).dropna(subset=["response_onset"])
    margin = result["response_onset"] - result["onset_blanked_ms"]
    # this recording is known to contain some — the point is they are detectable
    assert (margin <= 0.5).any()
    assert result["onset_blanked_ms"].notna().all(), "the blanking amount must always be recorded"


def test_identifiers_are_atomic(tms_results):
    row = tms_results.iloc[0]
    assert (row.study, row.group, row.subject_ID) == ("P1", "S", 1)
    assert (row.visit, row.timepoint) == (1, 0)
    assert (row.target_side, row.target_muscle) == ("L", "APB")
    assert (row.protocol_1, row.protocol_2) == ("TMS", "120")
    assert str(row.date) == "2023-02-15"