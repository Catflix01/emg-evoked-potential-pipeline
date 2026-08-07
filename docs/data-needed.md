# Data needed to finish validating the pipeline

Most of the pipeline is checked by tests that run on every change. A few parts cannot be,
they produce measurements with nothing to compare against. This is the list of what would
settle them, in priority order.

**Nothing here needs to be sent anywhere.** `src/selfcheck.py` runs on your own machine and
prints a text report containing counts, filename patterns and millisecond values: no EMG
samples, no patient details. Sharing that report is enough.

```bash
python src/selfcheck.py --data <YOUR FOLDER> > report.txt
```

Replace `<YOUR FOLDER>` with the real location of the recordings, in Terminal, type
`--data ` and then drag the folder in from Finder to fill in the path. Running it with no
`--data` checks the sample data in `data/raw`.

---

## 1. A hand-scored MEP onset: one number, nothing to send

**What:** For **LAPB** in the `TMS_120` recording already in `data/raw/`, where does the
motor-evoked potential begin, in milliseconds?

**Why:** The pipeline currently reports **25.8 ms**. An earlier version of the detector
reported **22.2 ms** for the same trace. Both are defensible: 22.2 ms is where the signal
first departs from baseline, 25.8 ms is where it departs decisively. Which one matches how
the lab marks onset determines the setting for every onset the pipeline will ever produce.

**Cost:** One person looking at one trace they already have.

---

## 2. The earliest latency you would accept as a real response

**What:** Three numbers: the shortest time after the stimulus at which a response in a hand
muscle could possibly be real, for each kind of stimulation:

| stimulation | currently assumed | your number |
|---|---|---|
| peripheral (PNS) | 3.5 ms | ? |
| spinal (TSS) | 10 ms | ? |
| cortical (TMS, SIC, ICI) | 10 ms | ? |

**Why:** The stimulator puts a large electrical transient on the electrodes at the instant it
fires, on the PNS recordings it reaches 1.33, against a resting level of 0.0012. Nothing can
travel from the stimulator to the muscle in zero time, so anything arriving before the
shortest possible conduction latency is artifact by definition. The pipeline refuses to look
before that point, and these three numbers are that point.

The values above were taken from the measurement windows, which were chosen for computing
area-under-curve rather than for excluding artifact. They are close, but not chosen for this.

**The PNS case is tight:** the artifact decays by about 4 ms and the M-wave arrives at about
4 ms. If the accepted minimum is 3 ms the current setting stands; if it is 5 ms, PNS onset
should be reported as blank rather than as a number.

---

## 3. One session folder, with its nesting intact

**What:** any subject, any session. The folder and everything under it:

```
P1Sxx/P1Sxx_V#E#_MMDDYYYY/<protocol folder>/*.csv
```

**Why:** The `session` and `experiment` columns are read from folder names. The parsing has
only ever seen folder names invented for tests. On the sample data it produces `session =
"data"` and a blank experiment, because those files sit in a flat folder.

**It also answers a question about your existing analysis.** The legacy MATLAB walks only
folders ending in `_TMS`:

```matlab
tmsDirs = dir(fullfile(subjFolder, '**', '*_TMS'));   % A3, line 29
```

If spinal and peripheral recordings live in `_TSS` or `_PNS` folders, that pipeline never read
them. One folder listing settles it, and `selfcheck.py` reports exactly this.

---

## 4. One paired brain-and-spine recording

**What:** Any `BPC_*`, `SPC_*`, `SCAP_IMM_*` or `FAC_*` file.

**Why:** These fire both stimulators in one trial. The pipeline detects that, pairs the two
stimuli, measures from the later one, and records the gap as `isi_ms`. **That code has never
run on real data**, every recording available here fires exactly one trigger channel.

---

## 5. One contracting recording, and its hand-scored silent period

**What:** A `TMS_AMT` or `TMS_AREC` where the subject held a voluntary contraction, plus the
cortical silent period someone measured by hand, onset, offset or duration, in ms.

**Why:** A silent period is a *pause in voluntary EMG*. At rest there is nothing to pause, so
`response_offset` and `emg_resuming` currently compute on **zero rows**.

The pipeline decides a muscle was contracting when its pre-stimulus peak-to-peak exceeds
**0.15**. That number is a floor and nothing more: every recording here is at rest, and the
noisiest reaches 0.127, so anything lower produces false positives, at 0.05 it wrongly
flagged three muscle-and-protocol combinations. Whether 0.15 is *low enough* to catch a real
contraction cannot be known without an active recording.

Three to five such recordings across different subjects would be better than one, since
silent-period duration varies substantially between people.

---

## What is already validated

For contrast, so effort goes where it is needed:

- Peak-to-peak and area-under-curve are pinned to known values from a real recording and
  checked on every change.
- Filename parsing is tested against all 104 protocols documented in the *Filenames* sheet.
- MEP onset for the cortical protocols is corroborated by two independent protocols (TMS at
  25.8 ms, SIC at 26.3 ms) landing in the 15–35 ms band physiology predicts.
- The measurement windows are recorded in each row, so no number is ambiguous about how it
  was produced.
