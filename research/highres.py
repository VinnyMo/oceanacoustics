"""Retrieve a 1–60 second native 16 kHz follow-up at a UTC timestamp."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
from urllib.request import Request, urlopen
import wave

from ingestion import mbari
from worker import guard, usage

BASE = "https://pacific-sound-16khz.s3.us-west-2.amazonaws.com/"
RATE = 16000


def retrieve(root, stamp, seconds):
    if not 1 <= seconds <= 60 or stamp.tzinfo is None or stamp.microsecond:
        raise ValueError("Supply an offset-aware timestamp in whole seconds and duration 1–60")
    stamp = stamp.astimezone(timezone.utc)
    key = stamp.strftime("%Y/%m/MARS-%Y%m%dT000000Z-16kHz.wav")
    midnight = stamp.replace(hour=0, minute=0, second=0)
    frames_from_start = int((stamp-midnight).total_seconds()) * RATE
    with (root / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        guard(root)
        folder = root / "research"
        folder.mkdir(exist_ok=True)
        if usage(folder) + 10_000_000 > 1_000_000_000:
            raise ValueError("Manual research storage budget reached")
        with urlopen(Request(BASE + key, method="HEAD"), timeout=30) as response:
            record = mbari.Recording(key, int(response.headers["Content-Length"]),
                                     response.headers["ETag"], response.headers["Last-Modified"])
        asset = stamp.strftime("%Y%m%dT%H%M%SZ") + f"-{seconds}s-16k-" + hashlib.sha256(record.etag.encode()).hexdigest()[:12]
        dest = folder / asset
        if dest.exists():
            manifest = json.loads((dest / "source.json").read_text())
            if hashlib.sha256((dest / "original.wav").read_bytes()).hexdigest() != manifest["wav_sha256"]:
                raise ValueError("Retained follow-up checksum mismatch")
            return dest
        with tempfile.TemporaryDirectory(dir=folder) as tmp:
            tmp = Path(tmp)
            mbari.fetch(record, 0, min(8191,record.size-1), tmp/"header", base=BASE)
            offset, width, frames = mbari.layout((tmp/"header").read_bytes(), record.size, RATE)
            if frames_from_start + RATE * seconds > frames:
                raise ValueError("Interval exceeds the available object")
            left = offset + frames_from_start * width
            right = left + seconds * RATE * width - 1
            mbari.fetch(record, left, right, tmp/"payload", base=BASE)
            release = tmp/"release"
            release.mkdir()
            wav = release/"original.wav"
            with wave.open(str(wav), "wb") as writer:
                writer.setparams((1,width,RATE,0,"NONE",""))
                writer.writeframes((tmp/"payload").read_bytes())
            info = dict(url=BASE+key,etag=record.etag,modified=record.modified,utc=stamp.isoformat(),
                        duration_seconds=seconds,rate=RATE,byte_range=[left,right],source_size=record.size,
                        pcm_sha256=hashlib.sha256((tmp/"payload").read_bytes()).hexdigest(),
                        wav_sha256=hashlib.sha256(wav.read_bytes()).hexdigest(),
                        attribution="MBARI Pacific Sound, CC BY 4.0; doi:10.1109/OCEANS.2016.7761363")
            (release/"source.json").write_text(json.dumps(info,indent=2)+"\n")
            os.rename(release, dest)
        return dest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("state", type=Path)
    p.add_argument("utc", type=datetime.fromisoformat)
    p.add_argument("seconds", type=int)
    args = p.parse_args()
    print(retrieve(args.state, args.utc, args.seconds))
