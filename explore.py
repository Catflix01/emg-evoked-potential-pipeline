"""Scratch script: print the first few responses from one recording and plot one epoch.

Run from the repo root. Note this hardcodes channel 18 as the TMS trigger and channel 10
as LAPB — harmonize.py looks both up from the manifest instead, which is the right way.
"""
import sys
from pathlib import Path
import yaml
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import trapezoid

print("Python:", sys.executable)
config = yaml.safe_load(open("config/params.yaml"))
sampling_rate = config["sampling_rate_hz"]

# found by protocol rather than by name, so no subject code or session time is
# written into this repository
csv_file = str(sorted(Path("data/raw").glob("*_TMS_120_*.csv"))[0])
data = pd.read_csv(csv_file, header=None).values
print("shape:", data.shape, "| duration:", data.shape[0] / sampling_rate, "s")

# Find where each stimulus pulse begins on the trigger channel.
above_threshold = np.where(data[:, 18] > config["trigger_threshold"])[0]
pulse_starts = above_threshold[np.concatenate(([True], np.diff(above_threshold) > 1))]
print("pulses detected:", len(pulse_starts))

target = data[:, 10]
# This file is TMS, so it uses the default response window.
prestim_ms = config["windows_ms"]["prestim"]
response_ms = config["windows_ms"]["response"]["default"]
baseline_start, baseline_end = [round(ms / 1000 * sampling_rate) for ms in prestim_ms]
response_start, response_end = [round(ms / 1000 * sampling_rate) for ms in response_ms]

for pulse, start in enumerate(pulse_starts[:6], start=1):
    response = target[start + response_start : start + response_end]
    baseline = target[start + baseline_start : start + baseline_end].mean()
    print(f"pulse {pulse}: "
          f"P2P={np.ptp(response):.3f}  "
          f"AUC_raw={trapezoid(np.abs(response)):6.2f}  "
          f"AUC_corrected={trapezoid(np.abs(response - baseline)):6.2f}")

# Plot the third pulse, with the two measurement windows shaded.
start = pulse_starts[2]
window = target[start - 500 : start + 400]
time_ms = (np.arange(len(window)) - 500) / sampling_rate * 1000

plt.plot(time_ms, window)
plt.axvline(0, color='r', ls='--')
plt.axvspan(*prestim_ms, color='gray', alpha=.2)
plt.axvspan(*response_ms, color='green', alpha=.2)
plt.xlabel("ms from pulse")
plt.title("One MEP epoch")
plt.show()
