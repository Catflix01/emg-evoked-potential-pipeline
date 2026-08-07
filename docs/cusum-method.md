# Finding response onset, offset and EMG resumption with CUSUM

This describes the method the pipeline uses to mark *when* things happen in an EMG trace: where
a response begins, where it ends, and where voluntary muscle activity comes back afterwards. It
is written for someone reading the results, not for someone editing the code.

The two papers it is based on:

- **King NKK, Kuppuswamy A, Strutton PH, Davey NJ (2006).** Estimation of cortical silent period
  following transcranial magnetic stimulation using a computerised cumulative sum method.
  *Journal of Neuroscience Methods* 150:96–104.
- **Brinkworth RSA, Türker KS (2003).** A method for quantifying reflex responses from
  intra-muscular and surface electromyogram. *Journal of Neuroscience Methods* 122:179–193.

The PDFs are not in this repository, because journal articles cannot be redistributed. The citations
above will find them. Everything needed to understand and check the method is written here.

---

## The problem: you cannot mark an onset by amplitude alone

The obvious way to find where a response starts is to wait for the EMG to cross some voltage.
This turns out not to work, and both papers say so directly. Brinkworth & Türker put it plainly:
the amplitude of the EMG at a particular point "is not sufficient for determining either the
start, nor end, of a burst of EMG activity."

Two things go wrong:

- **A noise spike crosses the threshold** and gets marked as an onset that never happened.
- **A response that builds gradually** does not cross until well after it truly began, so every
  latency comes out too late.

Researchers have patched around this with time windows, requiring the signal to stay above
threshold for some duration, but then the answer depends on a window width nobody can justify.
Too short and spikes count; too long and real brief responses are missed.

The other common approach is for an experienced person to place cursors by eye. That works, but
it is slow, and different raters place them differently. King et al. built their method precisely
because this **inter-observer variability** was the main obstacle to measuring the cortical
silent period reliably.

---

## The idea: add up how far the signal is from normal

Take the rectified EMG. Work out its average level during the quiet period *before* the stimulus. Call that **μ**. Now walk forward through the trace, keeping a running total of how far each
sample sits from μ:

```
Cusum[i] = Cusum[i-1] + (x[i] − μ)
```

That is the whole calculation, one addition and one subtraction per sample. King et al. spell out
the first three terms:

```
C₁ = (x₁ − μ)
C₂ = (x₁ − μ) + (x₂ − μ)
C₃ = (x₁ − μ) + (x₂ − μ) + (x₃ − μ)
```

Watch what the running total does:

| what the EMG is doing | what each term adds | what the curve does |
|---|---|---|
| sitting at its normal resting level | roughly zero, half above and half below | stays **flat** |
| larger than normal (a response) | positive | **climbs** |
| smaller than normal (suppressed) | negative | **falls** |

So a flat stretch of Cusum means "nothing is happening", a rising stretch means "more activity
than usual", and a falling stretch means "less activity than usual".

Crucially, the curve responds to a *sustained* change. A single noisy sample contributes one
small term and is swamped; a genuine response contributes hundreds of terms all pushing the same
way. That is why this is more robust than looking at any single sample's amplitude.

---

## Reading the events off the curve

Here is the part that makes the method work.

**A turning point of the Cusum, the moment it stops rising and starts falling, is exactly when
the EMG passed back through its pre-stimulus mean.**

Why: the curve rises only while the EMG is above μ, and falls only while it is below. The instant
it changes direction is the instant the EMG crossed μ. King et al. note this as the defining
characteristic: at the point where the gradient is zero, "the equivalent EMG is equal to the
pre-stimulus EMG mean."

So the events are read off the *shape* of the curve, and no amplitude threshold is ever chosen.
Within the silent-period window, King et al. take:

- the **maximum** turning point as the start of the silent period;
- the **minimum** turning point as its end.

---

## Deciding whether a deflection is real: the error box

A curve will wander slightly even when nothing is happening, because μ is an estimate and the
EMG is noisy. So how large must a deflection be before it counts?

Brinkworth & Türker's answer is the **error box**, and it is neat. Look at how far the Cusum
wandered during the pre-stimulus period, when by definition nothing was happening. Anything larger than
that is a real event; anything smaller is that recording's own noise.

The threshold therefore **calibrates itself to each recording**. A session with noisy electrodes
gets a stricter bar automatically; a clean session gets a more sensitive one. Nobody has to pick
a number, and no number has to be justified in a methods section beyond describing the rule.

---

## How this maps onto the output columns

The three column names describe the three events directly:

| column | what it marks | how it is found |
|---|---|---|
| `response_onset` | the response begins | first turning point after the stimulus that clears the error box |
| `response_offset` | the response ends, silence begins | the maximum turning point (King's CSP onset) |
| `emg_resuming` | voluntary EMG returns | the minimum turning point (King's CSP offset) |

All three are in **milliseconds from the stimulus**, matching the window columns.

The gap between the last two is the **cortical silent period**, the pause in voluntary muscle
activity after a TMS pulse, used as a measure of intracortical inhibition. Its duration is simply
`emg_resuming − response_offset`.

---

## The stimulus artifact, and why part of the trace is not searched

The stimulator puts a large electrical transient on the recording electrodes at the instant it
fires. On a PNS recording it looks like this, across the same five pulses:

```
            -20ms     -5ms      0ms      1ms      2ms      3ms      4ms      6ms     10ms
 pulse 1  -0.0180  -0.0150  -1.3720  -0.9050  -0.6400  -0.4350  -0.0490   0.6190  -0.7920
 pulse 3  -0.0180  -0.0190  -1.4490  -0.9610  -0.6780  -0.4910  -0.1660   0.5890  -0.7960
```

The muscle is at −0.018 with a spread of 0.0012 before the pulse. At the pulse it swings to
−1.37, roughly a thousand times the resting variation, then decays back to near zero by 4 ms.
The large biphasic waveform that follows is the M-wave.

**The transient starts at exactly 0 ms, and that is what identifies it.** A signal has to travel
from the electrode at the wrist, along the nerve, to the muscle; the shortest that can take for
a hand muscle is roughly 3 ms. Nothing physiological can appear at 0 ms. So everything before
the shortest possible conduction time is artifact by definition, and everything after is a
candidate response.

The pipeline therefore does not search the early part of the trace at all:

| stimulation | not searched until | earliest real response |
|---|---|---|
| peripheral (PNS) | 3.5 ms | M-wave, ~4 ms |
| spinal (TSS) | 10 ms | ~19 ms observed |
| cortical (TMS, SIC) | 10 ms | MEP, ~26 ms |

Two details matter:

**The cumulative sum restarts after that point.** Otherwise the artifact's contribution stays in
the running total and holds the curve outside the error box, and the detector reports the first
sample it was allowed to look at rather than a real departure. That was visible in testing: TSS
reported exactly 10.0 ms, its own boundary, until the sum was restarted, after which it
reported 19.0 ms, matching the response plainly visible in the trace at 20–25 ms.

**Every row records how much was excluded**, in `onset_blanked_ms`. An onset sitting a fraction
of a millisecond past its own boundary is the edge of the exclusion window, not a measurement.
This happens for muscles a protocol was not targeting, which often have no response at all, on
the sample data, 82 of 723 rows. Keeping the number in the table means those can be spotted
rather than mistaken for results.

**PNS is the tight case.** Its artifact decays by about 4 ms and its M-wave arrives at about
4 ms, leaving almost no margin. Cortical protocols have no such problem: their artifact is
around 0.004 and the response arrives 20 ms later: a separation of orders of magnitude in both
time and amplitude.

---

## Two things the papers force, which are easy to miss

### The values are per recording, not per pulse

Both papers work on the EMG **averaged across trials**. King averaged 20 stimuli per condition.
Single-trial EMG is exactly what the method exists to avoid having to score by eye; the turning
points on one noisy trace are unstable.

So the pipeline averages the rectified EMG across all the pulses of a recording, runs the Cusum
once per muscle, and writes the same three values to every row for that muscle. The per-pulse
`pk_pk` and `auc` columns are unaffected, only the timing columns repeat down the rows.

### They only mean anything during voluntary contraction

A cortical silent period is a *pause in ongoing voluntary EMG*. If the muscle was at rest there
is nothing to pause, and the turning points would be tracking noise.

The pipeline therefore marks each recording as active or resting: a contracting muscle has
visibly more pre-stimulus activity, which `prestim_pk_pk` already measures, and computes the
timing columns only for the active ones. A resting trial leaves them blank rather than reporting
a silent period it cannot have had.

For reference, King et al. had subjects hold 20% of their maximum contraction, with visual
feedback, throughout.

---

## What still needs checking

These columns cannot be verified the way the rest of the pipeline is. Every other number here can
be confirmed by re-running and seeing that nothing moved; these are new measurements with nothing
to compare against inside the repository.

Before they are used in any analysis they should be checked against traces the lab has already
scored by hand. As a rough guide: for a hand muscle, MEP onset should land somewhere around
20–30 ms after the stimulus, and the silent period should run out to roughly 100–200 ms. Values
far outside that mean the active/resting threshold or the search window needs adjusting, not that
the physiology is surprising.
