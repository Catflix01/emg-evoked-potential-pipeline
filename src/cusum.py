"""Find when a response starts, when it ends, and when EMG comes back.

The method is the cumulative sum (Cusum). docs/cusum-method.md explains it in plain
terms; in short, it adds up how far the EMG sits from its pre-stimulus average, so a
turning point in that running total marks the EMG crossing back through that average.

  King NKK, Kuppuswamy A, Strutton PH, Davey NJ (2006). J Neurosci Methods 150:96-104.
  Brinkworth RSA, Turker KS (2003). J Neurosci Methods 122:179-193.
"""
import numpy as np


def average_epochs(signal, pulse_starts, before_samples, after_samples):
    """Cut one window around each pulse, rectify, and average them together.

    Both papers work on the trial-averaged rectified EMG rather than single traces —
    a single trace is exactly what is too noisy to score reliably.
    """
    epochs = [signal[start - before_samples : start + after_samples]
              for start in pulse_starts
              if start - before_samples >= 0 and start + after_samples <= len(signal)]
    if not epochs:
        return None
    epochs = np.asarray(epochs, dtype=float)
    resting_level = epochs[:, :before_samples].mean(axis=1, keepdims=True)
    return np.abs(epochs - resting_level).mean(axis=0)


def cusum_curve(averaged, before_samples):
    """The running total of how far the EMG is from its pre-stimulus average."""
    prestim_mean = averaged[:before_samples].mean()
    return np.cumsum(averaged - prestim_mean)


def error_box(cusum, before_samples):
    """How far the curve wanders while nothing is happening.

    Brinkworth & Turker's significance test: a deflection only counts if it exceeds
    the largest deviation seen before the stimulus. Each recording's own noise
    therefore sets its own threshold, rather than someone picking a number.
    """
    quiet = cusum[:before_samples]
    return float(np.abs(quiet - quiet.mean()).max())


def turning_points(cusum, start, end):
    """Where the curve changes direction between two samples.

    A turning point is where the EMG crossed back through its pre-stimulus average,
    which is what makes it meaningful rather than just a bend in a line.
    """
    section = cusum[start:end]
    if len(section) < 3:
        return []
    rising = np.diff(section) > 0
    changes = np.where(np.diff(rising.astype(int)) != 0)[0] + 1
    return [start + int(c) for c in changes]


def find_response_onset(cusum, before_samples, box, blank_samples=0):
    """First sample after the blanking period where the curve clears the error box.

    Blanking exists because the stimulator puts an electrical transient on the
    electrodes at the moment it fires. Nothing can travel from the stimulator to the
    muscle in zero time, so anything before the shortest possible conduction latency
    is artifact by definition and is not searched.

    The comparison restarts from the curve's value at the end of the blanking period,
    so artifact accumulated during it does not carry into the measurement.
    """
    start = before_samples + max(0, blank_samples)
    if start >= len(cusum):
        return None
    after = np.arange(start, len(cusum))
    departed = after[np.abs(cusum[after] - cusum[start]) > box]
    return int(departed[0]) if len(departed) else None


def find_silent_period(cusum, search_start, search_end):
    """The pause in voluntary EMG: the curve's highest point, then its lowest after that.

    King et al. take the maximum turning point as the start of the silent period and the
    minimum as its end, searched "within the likely time window of the silent period".
    That window matters: once EMG resumes the curve goes flat rather than turning back
    up, so over an unbounded stretch the lowest point drifts wherever noise puts it.
    """
    search_end = min(search_end, len(cusum))
    if search_end - search_start < 3:
        return None, None
    section = cusum[search_start:search_end]
    highest = search_start + int(np.argmax(section))
    if highest >= search_end - 1:
        return highest, None
    lowest = highest + 1 + int(np.argmin(cusum[highest + 1:search_end]))
    return highest, lowest


def samples_to_ms(sample, before_samples, sampling_rate):
    """Sample index within the epoch -> milliseconds from the stimulus."""
    if sample is None:
        return None
    return round((sample - before_samples) / sampling_rate * 1000, 2)


def timing_values(signal, pulse_starts, sampling_rate, before_ms, after_ms, is_active,
                  silent_period_end_ms=300, blank_until_ms=0):
    """Onset, offset and EMG resumption for one muscle in one recording, in ms.

    `blank_until_ms` is the earliest latency at which a response could physically
    arrive; everything before it is stimulus artifact and is not searched. It is
    reported back as `onset_blanked_ms` so any onset can be judged against how close
    it sits to its own exclusion boundary.

    The silent-period pair is only computed when the muscle was contracting; at rest
    there is no voluntary activity to pause, so those two are left blank instead.
    """
    blank = {"response_onset": None, "response_offset": None, "emg_resuming": None,
             "onset_blanked_ms": blank_until_ms}

    before_samples = round(before_ms / 1000 * sampling_rate)
    after_samples = round(after_ms / 1000 * sampling_rate)
    averaged = average_epochs(signal, pulse_starts, before_samples, after_samples)
    if averaged is None:
        return blank

    cusum = cusum_curve(averaged, before_samples)
    box = error_box(cusum, before_samples)
    blank_samples = round(blank_until_ms / 1000 * sampling_rate)

    onset = find_response_onset(cusum, before_samples, box, blank_samples)
    result = {"response_onset": samples_to_ms(onset, before_samples, sampling_rate),
              "response_offset": None, "emg_resuming": None,
              "onset_blanked_ms": blank_until_ms}

    if is_active and onset is not None:
        search_end = before_samples + round(silent_period_end_ms / 1000 * sampling_rate)
        offset, resuming = find_silent_period(cusum, onset, search_end)
        result["response_offset"] = samples_to_ms(offset, before_samples, sampling_rate)
        result["emg_resuming"] = samples_to_ms(resuming, before_samples, sampling_rate)

    return result
