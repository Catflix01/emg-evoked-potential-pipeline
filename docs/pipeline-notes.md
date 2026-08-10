# Pipeline notes: why the code does what it does

The code in `src/harmonize.py` is kept deliberately plain, with comments no longer than a
sentence. This file holds the reasoning behind the decisions that aren't obvious from reading
it, so that nobody has to reverse-engineer them later.

---

## Which columns are verified, and which are not

Not every column carries the same weight of evidence. This distinction matters more than any
other note in this file.

**Verified**, meaning pinned to known values from a real recording and re-checked on every change:
`pk_pk`, `auc`, `prestim_pk_pk`, `prestim_auc`, `baseline`, and every identifier parsed from a
filename (tested against all 104 protocols in the *Filenames* sheet).

**Provisional**: the code is tested, but it has never run against data known to be correct:

| column | what is missing |
|---|---|
| `session`, `experiment` | never seen a real session folder; the sample data is a flat directory |
| `isi_ms` | no paired brain+spine recording available, so the pairing code has never run |
| `is_active` | the threshold is a floor calibrated on resting data; no contracting recording to confirm it is low enough |
| `response_offset`, `emg_resuming` | a silent period only exists during contraction, so these compute on zero rows |
| `response_onset` | corroborated for the cortical protocols (TMS 25.8 ms, SIC 26.3 ms, both inside the 15–35 ms band), but no hand-scored value has confirmed the convention |

`python main.py check` prints this same warning alongside any results it produces, so the
distinction travels with the numbers rather than living only here.

---

## What the `baseline` column is

The **mean voltage of the pre-stimulus window** (−100 to −50 ms), where that muscle's channel
was resting just before the pulse arrived.

It is not a measurement of the response. It is the zero point, and every Pk-Pk and AUC in the row is
computed after subtracting it, so that a channel sitting at +0.053 V and one sitting at 0 V can
be compared. It is kept in the output for two reasons:

- it is the only way to reconstruct raw amplitudes from the baseline-corrected ones;
- it is a **quality flag**: a channel with an unusually large or drifting baseline usually had a
  bad electrode, and that is worth seeing before trusting its numbers.

It sits after the columns of `docs/Table-layout.csv` rather than inside them, because it is
diagnostic rather than part of the agreed layout.

---

## Which measurement window each protocol uses

Windows are not the same for every protocol, because the physiology is not. A cortical MEP
travels brain → spinal cord → muscle and arrives around 20–30 ms after the pulse; a peripheral
M-wave has a far shorter path and arrives within a few milliseconds. Measuring a PNS response in
a 10–70 ms window would miss its start entirely.

All windows live in one block in `config/params.yaml`:

```yaml
windows_ms:
  prestim: [-100, -50]        # every protocol
  response:
    default: [10, 70]
    PNS: [3.5, 25]            # M-wave arrives much sooner than a cortical MEP
  second_response: {}
```

**The `prestim_window` / `response_window` / `2nd_response_window` columns are filled from these
same values.** They are never typed in separately, so a row cannot claim a window that the
arithmetic did not use. If the config changes, the columns change with it. Reading a row tells
you exactly how its numbers were produced.

Adding a family is one line. Anything not listed uses `default`.

A note on precision: window edges are converted to samples with `round`, not truncation. At
5000 Hz, 3.5 ms is 17.5 samples, and truncating would silently start the window 0.1 ms early.

---

## Why prestim AUC is baseline-corrected

The legacy MATLAB measured the pre-stimulus window raw:

```matlab
P2P_matrix_preStim(i,m) = peak2peak(pre);
AUC_matrix_preStim(i,m) = trapz(abs(pre));   % <- raw, not corrected
```

We subtract the baseline first. The reason is that every EMG channel sits at its own resting
voltage, and `trapz(abs(...))` on an uncorrected segment measures that offset far more than it
measures muscle activity. Channel LTB rests at about +0.053, so across a 250-sample prestim
window its raw AUC comes out near 13 no matter how quiet the muscle actually was. A channel
resting near 0 looks quiet by comparison purely because of where its electrode sat.

Baseline-correcting makes prestim AUC comparable across channels, and makes it consistent with
the response AUC, which was already corrected.

**Pk-Pk is unaffected by this choice.** Subtracting a constant from a segment cannot change its
peak-to-peak range, so `prestim_pk_pk` matches the legacy value exactly.

---

## Why the response-timing columns are empty

`response_onset`, `response_offset`, `emg_resuming` and the four `2nd_*` columns exist in the
table but nothing fills them in yet. Two separate problems have to be solved first.

**Onset detection.** The lab's own process notes still list this as an open question:
*"Can we add response onset latency? Most people use cusum."* Picking a detector and validating
it against traces the lab trusts is a piece of work in its own right, and a wrong threshold
produces confident-looking numbers that are silently wrong.

**Locating the second response.** There is no single rule, because "second response" means
different things per protocol family:

| family | first response | second response |
|---|---|---|
| `PNS` | M-wave (direct motor) | H-reflex (spinal) |
| `SIC`, `ICI`, `PAD` | response to the conditioning pulse | response to the test pulse |

The columns are emitted empty rather than omitted so the table shape stays stable. Anything already reading
the output keeps working when the values start appearing.

---

## Why dates are stored as `YYYY-MM-DD` and not `MMDDYYYY`

The recording filenames carry dates as `MMDDYYYY`, for example `08152023`. Written to a CSV and opened
in Excel, or read back with pandas, that becomes the number `8152023`. The leading zero is
gone, because a field of digits gets treated as a number.

For most dates this is survivable. For January it is not:

```
2024-01-17  ->  01172024  ->  1172024  ->  reads back as 2024-11-07
```

`%m` takes two digits (`11`) before `%d` gets a look, so a January session silently becomes a
November one. No error is raised. Ten days a year land in this trap, and real sessions have
fallen inside it.

ISO format is immune twice over: the hyphens stop anything treating it as a number, and the
field order is fixed-width so it cannot be re-read a second way.

Note the pipeline itself was never at risk: it reads the date from the filename on disk, which
never passes through Excel. This protects the *output*.

---

## Why the filename parse looks for the date instead of counting underscores

The obvious approach is to split on `_` and take fixed positions. That breaks, because the
protocol is not always two pieces wide:

| filename protocol | pieces |
|---|---|
| `PNS_Mmx` | 2 |
| `SIC_025` | 2 |
| `PNS_010_sec` | 3 |
| `TSS_410_Ct1` | 3 |

With a fixed-position parse, the three-piece names push everything along by one, and the date
field ends up holding `sec`. The parse instead finds the `MMDDYYYY-HH-MM-SS` piece and works
backwards from it, so the protocol can be any width.

---

## Why an unrecognised visit token blanks instead of erroring

Visits are normally `V1T0` (visit 1, timepoint 0), but the legacy pipeline shows `V4E1` shaped
tokens exist too. A recording with an odd visit token still contains perfectly good EMG, so the
`visit` and `timepoint` columns are left blank and the measurements are kept, rather than
throwing the file away over its name.

---

## Why `source_file` is not in the output

It was removed by request. Worth knowing what that costs: the filename was the only place the
recording's *timestamp* appeared. The remaining identifiers only resolve down to the date, so
two runs of the same protocol on the same subject on the same day are no longer distinguishable
from the table alone. If that becomes a problem, adding a `time` column from the same filename
token restores uniqueness at much lower width than the full filename.

---

## Why `stim_channel` sits next to `channel`

They are easy to confuse:

- **`channel`**: the channel the *muscle* was recorded on (e.g. 10 for LAPB).
- **`stim_channel`**: the channel the *stimulus trigger* fired on (e.g. 18 for TMS, 17 for
  spinal/peripheral).

`stim_channel` is there to make finding a specific response again in NewQuant easier. It is
constant for a whole recording, since one protocol uses one trigger.

---

## Why the output is a parquet file

Parquet stores each column's type alongside the data; CSV stores only text and leaves the
reader to guess. On this table the guessing loses two things:

| column | written as | back from CSV | back from parquet |
|---|---|---|---|
| `date` | a real date | text, needs re-parsing | a real date |
| `prestim_window` | empty text column | becomes a number column | still text |

The second row is the awkward one: the placeholder columns are empty, so a CSV reader has
nothing to infer from and defaults them to numeric, which then conflicts with the text they
are meant to hold.

The real cost of parquet is that it cannot be opened in Excel. So the pipeline writes both.

---

## Why there are two output files, and why the CSV is rounded to 4 places

Every run writes the same table twice:

| file | precision | for |
|---|---|---|
| `outputs/master_results.parquet` | full | the code, and any analysis: the source of truth |
| `outputs/master_results.csv` | 4 decimal places | opening in Excel and reading by eye |

The CSV is a **view**. Nothing reads it back into an analysis, so rounding it cannot affect any
result. That separation is what allows it to be readable without being lossy where it matters.

**Four decimals rather than two**, because two destroys three of the columns. Measured on a real
run of 728 rows:

| column | median | at 2 dp | rows flattened to 0.00 |
|---|---|---|---|
| `auc` | 0.399 | 0.40 | 0 |
| `prestim_auc` | 0.241 | 0.24 | 0 |
| `pk_pk` | 0.016 | 0.02 | 24 (3%) |
| `prestim_pk_pk` | 0.008 | 0.01 | 49 (7%) |
| `baseline` | −0.00037 | −0.00 | **238 (33%)** |

Two decimals is fine for the AUC columns, whose values run from about 0.05 to 70. It is not fine
for the amplitude columns, whose values are an order of magnitude smaller: a median Pk-Pk of
0.016 becomes 0.02, a 25% error, and a third of the baseline column disappears entirely.

Four decimals is still plainly readable, `0.016`, `0.3991`, `72.6487`, and loses nothing that
matters at these magnitudes.
