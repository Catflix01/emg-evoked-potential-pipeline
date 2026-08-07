# Review before publishing

This tool reads EMG recordings and produces one table: peak-to-peak and area-under-curve per
muscle per stimulus pulse, plus response timing. It does the job the MATLAB code in
`docs/legacy/` currently does.

The proposal is to put the code on GitHub, and a demo version of the app that carries only
made-up recordings. Real recordings stay on lab machines.

Five things need your decision. They are at the bottom. About ten minutes.

## Where the data lives

A published app can only read files that are in the repository. Recordings, the manifest, the
outputs and the reference PDFs are all kept out of it, so a published copy has no patient data
to reach. It falls back to the made-up set and says so on screen.

So the risk was never really the app. It is the repository, and that is what the checks below
are about.

## What the audit found

The code makes no network calls. It has no `eval`, no `exec`, no `pickle`, no shell execution,
and no credentials. Dependencies are pinned to exact versions so results do not drift when
someone reinstalls.

Four problems, three now fixed.

**A participant code and session time were already in the git history.** The first commit
included a spreadsheet quoting a real filename: a participant code with the exact minute of
their session. Adding it to `.gitignore` does nothing, because it was already inside the
commit.

I rebuilt the history from scratch, which was possible only because nothing had been pushed
yet, then scanned every object in the repository. No real participant code remains anywhere in
it. Had this been found after publishing, it would have been permanent.

**The safety check itself had a hole.** It scanned for participant codes with a pattern that
required a word boundary after the code. In a filename the code is followed by an underscore,
which counts as a word character, so the pattern never matched the form that actually appears.
The check said "safe" while a subject-plus-timestamp filename was still sitting in `explore.py`.

Pattern fixed, a second pattern added for a code next to a session date, MATLAB files added to
the scan, and the allowlist deleted so there is nothing left to widen.

**`group` is a diagnosis.** The lab's own documentation gives the code: S is SCI, A is
able-bodied, L is ALS, M is myelopathy. So every row of the output carries the participant's
diagnosis. That is not the same kind of information as an EMG amplitude, and with 19
participants, a diagnosis plus a session date narrows things down a long way. This one is
decision 2 below.

**Publishing happens automatically.** Streamlit rebuilds the app on every push, and the safety
check was a local git hook, so it would not run on anyone else's machine. It now also runs in
GitHub Actions, so it travels with the repository.

There is also no licence file, which means other labs cannot legally reuse the code. That is
decision 3.

## The comparison with the old pipeline

I ran both versions over the same recordings, same windows, same rows. The legacy formula comes
straight from `EMG_Pipeline_A3_ProcessingData.m`, lines 171 to 178.

Peak-to-peak agrees exactly. The largest difference across 728 rows is 1.1e-16, which is
floating-point noise. That is worth something on its own: it means the windows, the trigger
detection and the epoching in the new code all match the old code.

Area under curve does not agree. It differs by a median of 59%. The reason is known and
deliberate, since the old code integrates the raw trace while this one subtracts the
pre-stimulus baseline first. What the comparison adds is how large that turns out to be:

| muscle | resting offset | old AUC | new AUC | share of the old value that is offset |
|---|---|---|---|---|
| LTB | +0.053 | 15.84 | 0.18 | 98.9% |
| RTB | -0.028 | 8.35 | 0.13 | 98.5% |
| LBB | +0.014 | 4.24 | 0.28 | 93.3% |
| LAPB (target) | -0.018 | 10.04 | 7.21 | 28.2% |
| LADM | -0.001 | 2.18 | 2.17 | 0.3% |

The correlation between a channel's resting electrode offset and the size of the gap is 0.935.
Where a channel sits at an offset, most of its old AUC is that offset rather than muscle
activity. Where the offset is near zero, the two versions agree.

I want to be careful about how far that goes. It is evidence, not a conclusion. It suggests
that AUC values computed previously may be measuring electrode offset on affected channels, but
whether that matters for any given analysis is your call. Peak-to-peak is unaffected either
way, and it agrees exactly.

You can check this on your own data:

```bash
python src/compare_legacy.py --data <your folder>
```

It measures each recording both ways from the same file. No MATLAB, nothing uploaded.

## What is not yet verified

Checked against known-correct data: `pk_pk`, `auc`, `prestim_pk_pk`, `prestim_auc`, `baseline`,
every identifier parsed from a filename, and filename parsing across all 104 documented
protocols. MEP onset for the cortical protocols is corroborated by two protocols agreeing
independently.

Not yet checked: `session` and `experiment` (never seen a real session folder), `isi_ms` (no
paired recording available), `is_active` (no contracting recording), and `response_offset` and
`emg_resuming` (a silent period only exists during contraction, so these currently compute on
no rows at all).

`docs/data-needed.md` says what would settle each one. The cheapest is a hand-scored MEP onset
for a recording already sitting in the repository.

## What I need from you

1. I rebuilt the git history, because waiting would have made it permanent. Please confirm you
   are happy with that.
2. May `group`, which is a diagnosis, appear in outputs that leave the lab? If not it should be
   dropped or recoded before anything is shared.
3. Which licence?
4. Is a public demo carrying only made-up recordings acceptable?
5. What should happen about the AUC finding for analyses already run with the old values?

## Checking any of it yourself

```bash
python src/check_before_publish.py                     # what would be committed, and is it safe
python src/compare_legacy.py --data <folder>           # both versions side by side
python src/selfcheck.py --data <folder> --anonymise    # a shareable report with no identifiers
python -m pytest                                       # the test suite
```

All of it runs locally. Nothing leaves the machine.
