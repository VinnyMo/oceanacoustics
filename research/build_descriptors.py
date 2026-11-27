"""Reproduce the two small numerical spectra shipped with the detector."""
import argparse
import json
from math import gcd
from pathlib import Path
import subprocess

import numpy as np
from scipy.signal import resample_poly

from classification.references import RATE, VERSION, profile
from research.references import RECORDS, verify


def descriptors(directory):
    result = []
    for row in RECORDS:
        path = directory / (row["id"] + ".flac")
        verify(path, row)
        pcm = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-"])
        native = np.frombuffer(pcm, "<i2").astype(np.float64)/32768
        factor = gcd(row["rate"], RATE)
        x = resample_poly(native, RATE//factor, row["rate"]//factor)
        result.append(dict(target=row["target"], deployment=row["deployment"],
                           utc=row["utc"], pcm_sha256=row["pcm_s16le_sha256"],
                           band_mean_dbfs_per_hz=profile(x).round(5).tolist()))
    return dict(version=VERSION, source="NOAA Office of National Marine Sanctuaries and U.S. Navy (2020), doi:10.25921/saca-sp25",
                labels="Kim et al. (2025), doi:10.3354/meps14910, Figure 2B/C",
                references=result)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("reference_directory", type=Path)
    print(json.dumps(descriptors(p.parse_args().reference_directory), indent=2))
