"""Describe the development references in uncalibrated digital units."""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import welch

from research.references import RECORDS, verify


def describe(directory):
    result = {}
    for row in RECORDS:
        path = directory / (row["id"] + ".flac")
        verify(path, row)
        raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-"])
        samples = np.frombuffer(raw, "<i2").astype(float)/32768
        # Native-rate 1-second Hann segments give 1 Hz FFT bins. Uncalibrated power.
        frequency, power = welch(samples, row["rate"], window="hann", nperseg=row["rate"],
                                 noverlap=row["rate"]//2)
        metrics = {}
        for name, (lo, hi) in {"UF310": (304,320), "UF440": (417,469)}.items():
            band = (frequency >= lo) & (frequency <= hi)
            peak = int(np.argmax(power[band]))
            metrics[name] = {"peak_bin_hz": float(frequency[band][peak]),
                             "mean_psd_dbfs_per_hz": round(10*np.log10(np.mean(power[band])), 3)}
        result[row["id"]] = metrics
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    print(json.dumps(describe(p.parse_args().directory), indent=2))
