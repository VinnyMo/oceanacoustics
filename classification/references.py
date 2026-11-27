"""Descriptive spectral correlation against two figure-labelled coastal excerpts."""
from functools import lru_cache
import json
from pathlib import Path

import numpy as np
from scipy.signal import welch

RATE = 2000
VERSION = "reference-logband-pearson-v1"
CONFIG = Path(__file__).with_name("reference_bands.json")


def profile(samples):
    x = np.asarray(samples, dtype=np.float64)
    if x.ndim != 1 or x.size < RATE or not np.isfinite(x).all():
        raise ValueError("Expected at least one second of finite mono 2 kHz audio")
    f, p = welch(x, RATE, window="hann", nperseg=RATE, noverlap=RATE//2)
    # Disjoint 50 Hz bands, 100 Hz inclusive through 900 Hz exclusive.
    selected = p[(100 <= f) & (f < 900)].reshape(16, 50)
    return 10*np.log10(np.maximum(selected.mean(axis=1), 1e-24))


@lru_cache(maxsize=1)
def exemplars():
    data = json.loads(CONFIG.read_text())
    if data["version"] != VERSION:
        raise ValueError("Reference descriptor version mismatch")
    return data["references"]


def compare(samples):
    measured = profile(samples)
    measured -= measured.mean()
    magnitude = np.linalg.norm(measured)
    scores = {}
    for reference in exemplars():
        curve = np.asarray(reference["band_mean_dbfs_per_hz"])
        curve = curve - curve.mean()
        denom = magnitude * np.linalg.norm(curve)
        scores[reference["target"]] = (
            round(float(np.clip(measured @ curve / denom, -1, 1)), 4)
            if denom > 1e-10 else None
        )
    return {"algorithm": VERSION, "measure": "Pearson correlation of 16 log-power bands",
            "scores": scores, "interpretation": "Coastal exemplar similarity only"}
