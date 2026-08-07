"""The comparison against the inherited MATLAB makes two claims. Both are pinned here.

  1. Pk-Pk is identical, because subtracting a constant cannot change a range.
  2. The AUC difference is the electrode offset, not muscle signal.

If either stops holding, something has changed in how responses are measured.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from compare_legacy import legacy_features, compare_recording, summarise, per_muscle

ROOT = Path(__file__).resolve().parents[2]


def recording(protocol):
    matches = sorted((ROOT / "data" / "raw").glob(f"*_{protocol}_*.csv"))
    return matches[0] if matches else None


# ------------------------------------------------------------------ the arithmetic

def test_legacy_does_not_subtract_a_baseline():
    """The whole difference between the two pipelines, in one assertion."""
    signal = np.zeros(400)
    signal[200:260] = 5.0        # a DC offset across the response window
    legacy = legacy_features(signal, 150, prestim=(-100, -50), response=(50, 110))
    # the legacy integrates the raw trace, so a flat offset produces a large area
    assert legacy["legacy_auc"] > 250
    # ... while its Pk-Pk is zero, because a flat segment has no range
    assert legacy["legacy_pk_pk"] == 0.0


def test_offset_alone_predicts_the_legacy_auc():
    """A quiet channel sitting at an offset: its legacy AUC is offset x window length."""
    offset, window = 0.05, 60
    signal = np.full(400, offset)
    legacy = legacy_features(signal, 150, prestim=(-100, -50), response=(50, 50 + window))
    assert legacy["legacy_auc"] == pytest.approx(offset * (window - 1), rel=0.02)


# ------------------------------------------------------------------ against real EMG

@pytest.fixture(scope="module")
def comparison():
    csv = recording("TMS_120")
    if csv is None:
        pytest.skip("no real recording available")
    manifest = pd.read_excel(
        ROOT / "docs" / "Centralized-NIDAQ-System-Pharma-1957-PRIMING.xlsx",
        sheet_name="draft-pharma")
    config = yaml.safe_load(open(ROOT / "config" / "params.yaml"))
    return compare_recording(csv, manifest, config)


def test_pk_pk_agrees_with_the_legacy_exactly(comparison):
    """The strongest evidence that windows, triggers and epoching match."""
    gap = (comparison.ours_pk_pk - comparison.legacy_pk_pk).abs().max()
    assert gap < 1e-9, f"Pk-Pk diverged from the legacy by {gap}"


def test_auc_differs_and_the_difference_is_the_offset(comparison):
    """Not a bug: documented, deliberate, and measurable."""
    stats = summarise(comparison)
    assert not np.isclose(stats["auc_median_percent_change"], 0), \
        "AUC should differ — this pipeline baseline-corrects and the legacy does not"
    assert stats["auc_gap_explained_by_offset"] > 0.9, \
        "the AUC gap should track each channel's resting offset almost exactly"


def test_the_gap_is_largest_where_the_offset_is_largest(comparison):
    table = per_muscle(comparison)
    worst = table.index[0]
    assert abs(table.loc[worst, "resting_offset"]) == pytest.approx(
        table.resting_offset.abs().max(), rel=1e-6), \
        "the muscle with the biggest AUC gap should be the one with the biggest offset"


def test_summary_reports_pk_pk_as_identical(comparison):
    assert summarise(comparison)["pk_pk_identical"] is True
