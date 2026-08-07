"""Generate synthetic recordings so the published app has something to show.

    python src/make_demo_data.py

Nothing here comes from a person. The EMG is random noise with a response drawn at a
chosen latency, so the demo doubles as an end-to-end check: the pipeline should recover
the latency each file was built with.

It also covers three things no recording in data/raw can reach — a nested session folder,
a paired brain-and-spine recording that fires two triggers, and a contracting muscle with
a silent period.
"""
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "data" / "demo"

SAMPLING_RATE = 5000
N_CHANNELS = 19
# Shaped like a real subject code (letters, digits, letter, digits) so the demo
# exercises the actual filename parsing, but unmistakably not a real participant.
SUBJECT = "DEMO1S01"
SESSION = "DEMO1S01_V1E1_01012024"
DATE = "01012024"

# channel -> muscle, matching the shape of a real session's lineup
MUSCLES = {2: "LBB", 3: "RBB", 4: "LTB", 5: "RTB", 8: "LECR", 9: "RECR",
           10: "LAPB", 11: "RAPB", 12: "LFDI", 13: "RFDI"}
TRIGGER_TSCS, TRIGGER_TMS = 16, 18

# Each demo recording, and the response latency it is built with. The pipeline should
# find these back — see test_demo_data.py.
RECORDINGS = [
    # (protocol, folder, onset_ms, second_trigger_ms, contracting)
    ("TMS_120", "DEMO1S01_V1E1_TMS", 24.0, None, False),
    ("TMS_AMT", "DEMO1S01_V1E1_TMS", 24.0, None, True),    # contracting: has a silent period
    ("SIC_025", "DEMO1S01_V1E1_TMS", 25.0, None, False),
    ("TSS_200", "DEMO1S01_V1E1_TSS", 18.0, None, False),
    ("PNS_Mmx", "DEMO1S01_V1E1_PNS", 5.0, None, False),
    ("BPC_120", "DEMO1S01_V1E1_SCAP", 24.0, 12.0, False),  # paired: two triggers, 12 ms apart
]


def make_recording(rng, onset_ms, second_trigger_ms, contracting,
                   n_pulses=10, gap_ms=500):
    """One recording: quiet channels, trigger pulses, and a response on the target."""
    gap = int(gap_ms / 1000 * SAMPLING_RATE)
    n_samples = gap * (n_pulses + 1)
    data = rng.normal(0, 0.002, (n_samples, N_CHANNELS))

    # a contracting muscle shows wider background, not a raised level
    if contracting:
        data[:, 10] = rng.normal(0, 0.12, n_samples)

    onset = int(onset_ms / 1000 * SAMPLING_RATE)
    for pulse in range(1, n_pulses + 1):
        at = pulse * gap
        # the trigger: a few samples above threshold
        trigger = TRIGGER_TMS if second_trigger_ms is None else TRIGGER_TMS
        data[at:at + 5, trigger] = 10.0
        if second_trigger_ms is not None:
            first = at - int(second_trigger_ms / 1000 * SAMPLING_RATE)
            data[first:first + 5, TRIGGER_TSCS] = 10.0

        # the stimulus artifact: large, starts exactly at the pulse, gone within 4 ms
        artifact = np.exp(-np.arange(20) / 5) * 0.8
        data[at:at + 20, 10] += artifact

        # the evoked response on the target muscle, at the chosen latency
        response = rng.normal(0, 0.5, 50) * np.hanning(50)
        data[at + onset:at + onset + 50, 10] += response

        # a contracting muscle falls silent after the response, then resumes
        if contracting:
            silence = at + onset + 50
            data[silence:silence + 500, 10] = rng.normal(0, 0.002, 500)

    return data


def make_manifest():
    """A channel lineup for the demo subject, in the shape harmonize.py expects."""
    row = {"Date": pd.Timestamp("2024-01-01"), "Participant": SUBJECT}
    for channel, muscle in MUSCLES.items():
        row[channel] = muscle
    row[TRIGGER_TSCS] = "trigger_tscs"
    row[TRIGGER_TMS] = "trigger_tms"
    return pd.DataFrame([row])


def main():
    rng = np.random.default_rng(20240101)
    if DEMO.exists():
        for old in DEMO.rglob("*"):
            if old.is_file():
                old.unlink()

    expected = []
    for protocol, folder, onset_ms, second_ms, contracting in RECORDINGS:
        target = DEMO / SUBJECT / SESSION / folder
        target.mkdir(parents=True, exist_ok=True)
        name = f"{SUBJECT}_V1T0_LAPB_{protocol}_{DATE}-10-00-00_demo.csv"
        data = make_recording(rng, onset_ms, second_ms, contracting)
        pd.DataFrame(data).to_csv(target / name, header=False, index=False)
        expected.append({"file": name, "protocol": protocol,
                         "built_with_onset_ms": onset_ms,
                         "paired_isi_ms": second_ms, "contracting": contracting})
        print(f"  {name}  ({data.shape[0]} samples, response at {onset_ms} ms)")

    make_manifest().to_excel(DEMO / "demo-manifest.xlsx", index=False)
    # written as JSON, not CSV, so the pipeline does not mistake it for a recording
    pd.DataFrame(expected).to_json(DEMO / "expected.json", orient="records", indent=2)
    print(f"\nWrote {len(expected)} recordings, a manifest and expected.json to {DEMO}")
    print("None of it is real. The pipeline should recover the latencies in expected.json.")


if __name__ == "__main__":
    main()
