"""The demo recordings are built with known properties, so the pipeline can be checked
end to end: it should recover what each file was made with.

These also cover three things no recording in data/raw can reach — a nested session
folder, a paired recording firing two triggers, and a contracting muscle.
"""
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from harmonize import find_recordings, process_file

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "data" / "demo"

pytestmark = pytest.mark.skipif(
    not (DEMO / "expected.json").exists(),
    reason="demo data not generated — run python src/make_demo_data.py")


@pytest.fixture(scope="module")
def demo():
    config = yaml.safe_load(open(ROOT / "config" / "params.yaml"))
    manifest = pd.read_excel(DEMO / "demo-manifest.xlsx")
    tables = {f.name: process_file(f, manifest, config) for f in find_recordings(DEMO)}
    expected = {row["file"]: row for row in json.loads((DEMO / "expected.json").read_text())}
    return tables, expected


def target_rows(table):
    return table[table.muscle == "LAPB"]


def test_every_demo_recording_processes(demo):
    tables, expected = demo
    assert set(tables) == set(expected), "a demo recording failed to process"


def test_onset_matches_what_each_file_was_built_with(demo):
    """The response was drawn at a known latency; the pipeline should find it there."""
    tables, expected = demo
    for name, table in tables.items():
        built = expected[name]["built_with_onset_ms"]
        found = target_rows(table).response_onset.iloc[0]
        # a few ms of tolerance: the response ramps in rather than starting abruptly,
        # and the paired protocols are measured from the later of their two stimuli
        assert abs(found - built) < 6, f"{name}: built at {built} ms, found {found} ms"


def test_session_folder_is_parsed(demo):
    """Neither column can be exercised by data/raw, which is a flat folder."""
    tables, _ = demo
    for name, table in tables.items():
        assert table.session.iloc[0] == "DEMO1S01_V1E1_01012024", name
        assert table.experiment.iloc[0] == 1, name


def test_paired_recording_recovers_its_interval(demo):
    """The two-trigger branch has never run on a real recording."""
    tables, expected = demo
    paired = [n for n, row in expected.items() if row["paired_isi_ms"]]
    assert paired, "no paired recording in the demo set"
    for name in paired:
        built = expected[name]["paired_isi_ms"]
        found = tables[name].isi_ms.dropna().unique()
        assert list(found) == [built], f"{name}: built with ISI {built}, found {found}"


def test_unpaired_recordings_have_no_interval(demo):
    tables, expected = demo
    for name, table in tables.items():
        if not expected[name]["paired_isi_ms"]:
            assert table.isi_ms.isna().all(), f"{name} reported an ISI but is not paired"


def test_contracting_recording_is_detected_as_active(demo):
    """is_active has never seen a contracting muscle in the real sample."""
    tables, expected = demo
    active = [n for n, row in expected.items() if row["contracting"]]
    assert active, "no contracting recording in the demo set"
    for name in active:
        assert target_rows(tables[name]).is_active.all(), \
            f"{name} was built contracting but was read as resting"


def test_resting_demo_recordings_are_not_flagged_active(demo):
    tables, expected = demo
    for name, table in tables.items():
        if not expected[name]["contracting"]:
            assert not target_rows(table).is_active.any(), \
                f"{name} was built at rest but was read as contracting"


def test_silent_period_only_appears_on_the_contracting_recording(demo):
    tables, expected = demo
    for name, table in tables.items():
        rows = target_rows(table)
        has_csp = rows.emg_resuming.notna().any()
        assert has_csp == bool(expected[name]["contracting"]), \
            f"{name}: silent period {'found' if has_csp else 'missing'} unexpectedly"


def test_demo_data_contains_no_real_subject_codes():
    """A guard on the thing that makes this data safe to publish."""
    import re
    for path in DEMO.rglob("*"):
        if path.is_file():
            assert not re.search(r"P\d+S\d+", path.name), f"{path} looks like a real subject"
