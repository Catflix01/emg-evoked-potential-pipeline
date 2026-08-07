import numpy as np
import pandas as pd
import pytest
import yaml
from pathlib import Path

from cusum import (average_epochs, cusum_curve, error_box, turning_points,
                   find_response_onset, find_silent_period, timing_values)
from harmonize import parse_filename, get_lineup, detect_pulses

ROOT = Path(__file__).resolve().parents[2]


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

SAMPLING_RATE = 5000


# --------------------------------------------------------------- the arithmetic

def test_cusum_is_flat_when_nothing_happens():
    # a constant signal never departs from its own mean, so the total never grows
    flat = np.full(500, 0.02)
    curve = cusum_curve(flat, before_samples=100)
    assert np.allclose(curve, 0.0)


def test_cusum_climbs_while_the_signal_is_raised():
    signal = np.full(500, 0.01)
    signal[200:300] = 0.05              # a burst above the resting level
    curve = cusum_curve(signal, before_samples=100)
    assert curve[199] == pytest.approx(0.0, abs=1e-9)   # flat before the burst
    assert curve[299] > curve[199]                       # climbed through it
    assert curve[350] == pytest.approx(curve[299])       # flat again after


def test_error_box_is_the_widest_quiet_wobble():
    curve = np.array([0.0, 2.0, -3.0, 1.0, 0.0, 50.0, 60.0])
    # only the first five samples are "before the stimulus"
    box = error_box(curve, before_samples=5)
    quiet = curve[:5]
    assert box == pytest.approx(np.abs(quiet - quiet.mean()).max())
    assert box < 50                     # the later spike must not inflate it


def test_turning_points_sit_where_direction_changes():
    curve = np.array([0, 1, 2, 3, 2, 1, 2, 3], dtype=float)
    points = turning_points(curve, 0, len(curve))
    assert 3 in points                  # peak
    assert 5 in points                  # trough


# --------------------------------------------------------------- known answers

def _synthetic_trace(onset_sample, offset_sample, resume_sample, n=2000, before=500):
    """A contracting muscle: background activity, a burst, a silent gap, background again.

    EMG oscillates around zero — activity shows as a larger *amplitude*, not as a
    raised DC level. So contraction is modelled by widening the noise, and the silent
    period by shrinking it almost to nothing.
    """
    rng = np.random.default_rng(0)
    signal = rng.normal(0, 0.05, n)                                    # voluntary background
    burst = slice(onset_sample, offset_sample)
    signal[burst] = rng.normal(0, 1.5, offset_sample - onset_sample)   # the evoked response
    silence = slice(offset_sample, resume_sample)
    signal[silence] = rng.normal(0, 0.002, resume_sample - offset_sample)
    return signal


def test_onset_is_found_where_the_burst_was_placed():
    before = 500
    signal = _synthetic_trace(onset_sample=before + 100,
                              offset_sample=before + 200,
                              resume_sample=before + 800)
    averaged = np.abs(signal - signal[:before].mean())
    curve = cusum_curve(averaged, before)
    onset = find_response_onset(curve, before, error_box(curve, before))
    # placed at sample 600; allow a few samples of detection lag
    assert onset == pytest.approx(before + 100, abs=15)


def test_silent_period_boundaries_land_where_they_were_placed():
    before, onset_at, offset_at, resume_at = 500, 600, 700, 1300
    signal = _synthetic_trace(onset_at, offset_at, resume_at)
    averaged = np.abs(signal - signal[:before].mean())
    curve = cusum_curve(averaged, before)

    # searched within the window the silent period is expected to fall in, as King et al.
    # do — beyond it the curve is flat and the lowest point drifts with noise
    offset, resuming = find_silent_period(curve, onset_at, resume_at + 100)
    assert offset == pytest.approx(offset_at, abs=25)      # burst ends, silence starts
    assert resuming == pytest.approx(resume_at, abs=25)    # background returns


def test_silent_period_search_window_is_load_bearing():
    """Without a bounded window the end of the silent period drifts into the flat tail."""
    before, onset_at, offset_at, resume_at = 500, 600, 700, 1300
    signal = _synthetic_trace(onset_at, offset_at, resume_at)
    averaged = np.abs(signal - signal[:before].mean())
    curve = cusum_curve(averaged, before)

    _, bounded = find_silent_period(curve, onset_at, resume_at + 100)
    _, unbounded = find_silent_period(curve, onset_at, len(curve))
    assert bounded == pytest.approx(resume_at, abs=25)
    assert unbounded > resume_at + 100          # drifts, which is why the window exists


def test_resting_muscle_gets_no_silent_period():
    # is_active False => the silent-period pair stays blank even if a response exists
    before = 500
    signal = _synthetic_trace(600, 700, 1300)
    values = timing_values(signal, [before + 500], SAMPLING_RATE,
                           before_ms=100, after_ms=150, is_active=False)
    assert values["response_offset"] is None
    assert values["emg_resuming"] is None


# --------------------------------------------------------------- against real EMG

@pytest.fixture(scope="module")
def lapb_mep():
    """The LAPB channel and TMS pulses from the real TMS_120 recording."""
    csv = recording("TMS_120")
    manifest_file = ROOT / "docs" / "Centralized-NIDAQ-System-Pharma-1957-PRIMING.xlsx"
    if not manifest_file.exists():
        pytest.skip("manifest workbook not present; it is not part of the repository")
    manifest = pd.read_excel(
        ROOT / "docs" / "Centralized-NIDAQ-System-Pharma-1957-PRIMING.xlsx",
        sheet_name="draft-pharma")
    config = yaml.safe_load(open(ROOT / "config" / "params.yaml"))
    meta = parse_filename(csv)
    data = pd.read_csv(csv, header=None).to_numpy()
    lineup = get_lineup(meta["_subject_token"], meta["_date_token"], manifest)
    muscle_channel = [c for c, name in lineup.items() if name == "LAPB"][0]
    trigger_channel = [c for c, name in lineup.items() if name == "trigger_tms"][0]
    pulses = detect_pulses(data[:, trigger_channel], config["trigger_threshold"])
    return data[:, muscle_channel], pulses


def test_real_mep_onset_is_physiologically_plausible(lapb_mep):
    """An APB response to motor-cortex TMS arrives about 20-25 ms after the pulse."""
    signal, pulses = lapb_mep
    values = timing_values(signal, pulses, SAMPLING_RATE,
                           before_ms=100, after_ms=150, is_active=False)
    onset = values["response_onset"]
    assert onset is not None, "no MEP onset found in a recording that clearly has one"
    assert 15 <= onset <= 35, f"onset {onset} ms is outside the plausible range for APB"


def test_real_mep_onset_regression(lapb_mep):
    # Pinned from the current implementation — change only if you INTEND to change
    # how onset is detected. See docs/cusum-method.md.
    signal, pulses = lapb_mep
    values = timing_values(signal, pulses, SAMPLING_RATE,
                           before_ms=100, after_ms=150, is_active=False,
                           blank_until_ms=10)          # as the pipeline runs it
    assert values["response_onset"] == pytest.approx(25.8, abs=0.1)
    assert values["onset_blanked_ms"] == 10


def test_blanking_excludes_a_stimulus_artifact():
    """A transient at t=0 must not be reported as a response."""
    rng = np.random.default_rng(1)
    before, stimulus, n = 500, 1000, 2000
    signal = rng.normal(0, 0.002, n)
    # the stimulator's discharge: large, starts exactly at the pulse, decays within 4 ms
    signal[stimulus:stimulus + 20] += np.exp(-np.arange(20) / 5) * 1.5
    # the real response, 25 ms (125 samples) later
    signal[stimulus + 125:stimulus + 175] += rng.normal(0, 0.4, 50)

    unblanked = timing_values(signal, [stimulus], SAMPLING_RATE,
                              before_ms=100, after_ms=150, is_active=False,
                              blank_until_ms=0)
    blanked = timing_values(signal, [stimulus], SAMPLING_RATE,
                            before_ms=100, after_ms=150, is_active=False,
                            blank_until_ms=10)

    assert unblanked["response_onset"] < 2, "without blanking the artifact is reported"
    assert blanked["response_onset"] >= 10, "blanking must exclude the artifact window"
    assert blanked["response_onset"] == pytest.approx(25, abs=6)


def test_blanking_amount_is_reported_back():
    # so an onset can be judged against how close it sits to its own exclusion boundary
    signal = np.random.default_rng(2).normal(0, 0.01, 2000)
    values = timing_values(signal, [1000], SAMPLING_RATE,
                           before_ms=100, after_ms=150, is_active=False,
                           blank_until_ms=3.5)
    assert values["onset_blanked_ms"] == 3.5


def test_real_recording_is_recognised_as_resting(lapb_mep):
    # this is a resting protocol, so no silent period should be reported
    signal, pulses = lapb_mep
    values = timing_values(signal, pulses, SAMPLING_RATE,
                           before_ms=100, after_ms=150, is_active=False)
    assert values["response_offset"] is None
    assert values["emg_resuming"] is None
