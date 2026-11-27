"""Reconstruct native-rate figure-labelled SanctSound development excerpts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

RECORDS = json.loads(Path(__file__).with_name("references.json").read_text())


def verify(path, row):
    pcm = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path),
                                   "-f", "s16le", "-c:a", "pcm_s16le", "-"])
    if len(pcm) != row["rate"] * row["duration_seconds"] * 2 or (
        hashlib.sha256(pcm).hexdigest() != row["pcm_s16le_sha256"]
    ):
        raise ValueError(f"Unexpected decoded samples for {row['id']}")


def acquire(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for row in RECORDS:
        dest = directory / (row["id"] + ".flac")
        if dest.exists():
            verify(dest, row)
            continue
        size = row["prefix_bytes"]
        request = urllib.request.Request(row["source"], headers={"Range": f"bytes=0-{size - 1}"})
        with urllib.request.urlopen(request, timeout=45) as response:
            if response.status != 206 or response.headers["Content-Range"] != (
                f"bytes 0-{size - 1}/{row['source_bytes']}"
            ):
                raise ValueError("Archive range changed")
            prefix = response.read(size + 1)
        if hashlib.sha256(prefix).hexdigest() != row["prefix_sha256"]:
            raise ValueError("Archive bytes changed")
        with tempfile.TemporaryDirectory(dir=directory) as tmp:
            src, clip = Path(tmp) / "prefix.flac", Path(tmp) / "clip.flac"
            src.write_bytes(prefix)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(src),
                            "-t", str(row["duration_seconds"]), "-map", "0:a:0", "-c:a", "flac",
                            "-map_metadata", "-1", "-fflags", "+bitexact", str(clip)], check=True)
            verify(clip, row)
            os.replace(clip, dest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    acquire(parser.parse_args().directory)
