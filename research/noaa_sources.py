"""Bounded six-second samples of the public NOAA SanctSound and NRS historical archives."""
import argparse
import base64
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import numpy as np

BUCKET = "https://storage.googleapis.com/noaa-passive-bioacoustic/"
LIST = "https://storage.googleapis.com/storage/v1/b/noaa-passive-bioacoustic/o?"
CC0 = "https://creativecommons.org/publicdomain/zero/1.0/"
RATE = 16000
SECONDS = 6
MAX_PREFIX = 4 * 1024 * 1024
HOLDOUT = "sanctsound/audio/ci01/sanctsound_ci01_02/"
REGIONS = {"ci":"Channel Islands", "fk":"Florida Keys", "gr":"Gray's Reef",
           "hi":"Hawaiian Islands", "mb":"Monterey Bay", "oc":"Olympic Coast",
           "pm":"Papahānaumokuākea", "sb":"Stellwagen Bank"}
SANCTSOUND = "ci01 ci02 ci03 ci04 ci05 fk01 fk02 fk03 fk04 gr01 gr02 gr03 hi01 hi03 hi04 hi05 hi06 mb01 mb02 mb03 oc01 oc02 oc03 oc04 pm01 pm02 pm05 sb01 sb02 sb03".split()
NRS = ["Alaskan Arctic", "Gulf of Alaska", "Olympic Coast", "Hawaiian Islands",
       "Channel Islands", "Gulf of Mexico", "Southeastern United States", "Northeastern United States",
       "Stellwagen Bank", "National Park of American Samoa", "Cordell Bank", "U.S. Virgin Islands"]


def sources():
    sites = [dict(id=f"sanctsound/audio/{s}/", provider="NOAA SanctSound",
                  location=f"{REGIONS[s[:2]]} · {s.upper()}") for s in SANCTSOUND]
    for number, name in enumerate(NRS, start=1):
        sites.append(dict(id=f"nrs/audio/{number:02d}/", provider="NOAA NRS",
                          location=f"{name} · NRS{number:02d}"))
    return sites


def read(url, cap=512000):
    with urlopen(url, timeout=12) as response:
        body = response.read(cap+1)
    if len(body) > cap:
        raise ValueError("Metadata exceeded the response bound")
    return body


def listing(prefix, **params):
    params.update(prefix=prefix, fields="prefixes,items(name,generation,size,md5Hash,updated),nextPageToken")
    return json.loads(read(LIST+urlencode(params)))


def source_url(item):
    return BUCKET + quote(item["name"], safe="/") + "?generation=" + str(int(item["generation"]))


def timestamp(name):
    # Match a delimited terminal timestamp, avoiding instrument serial numbers.
    filename = Path(name).name
    if m := re.search(r"_(\d{8}T\d{6}Z)(?:[_.]|$)", filename):
        return datetime.strptime(m[1], "%Y%m%dT%H%M%SZ"), "explicit UTC"
    if m := re.fullmatch(r"NRS\d+_(\d{8}_\d{6})\.flac", filename, re.I):
        return datetime.strptime(m[1], "%Y%m%d_%H%M%S"), "NRS clock"
    if m := re.search(r"_(\d{12})(?:\.x)?\.flac$", filename, re.I):
        return datetime.strptime(m[1], "%y%m%d%H%M%S"), "recorder clock"
    raise ValueError(f"Unresolved recording time in {filename}")


def tethys_anchor(deployment, first, selected):
    anchors = [first]
    receipt = json.loads((Path(__file__).resolve().parents[1] / "docs/noaa-clock-evidence.json").read_text())
    indexed_first = receipt["first_verified_filename"].get(deployment.strip("/").split("/")[-1])
    if indexed_first:
        anchors.append(timestamp(indexed_first)[0])
    items = listing(deployment+"metadata/", maxResults=24).get("items",[])
    for item in items:
        if not item["name"].lower().endswith((".xml",".xml.gz")) or int(item["size"]) > 160000:
            continue
        url = source_url(item)
        xml = read(url,160000)
        if item["name"].lower().endswith(".gz"):
            with gzip.GzipFile(fileobj=io.BytesIO(xml)) as gz:
                xml = gz.read(160001)
            if len(xml) > 160000:
                continue
        if b"tethys.sdsu.edu/schema" not in xml:
            continue
        # Several historical Tethys records contain malformed incidental party tags.
        # Use the structured document only when the actual recorder clock can be read.
        try:
            # Some NOAA XML declares UTF-8 while encoding smart quotes in Windows-1252.
            try:
                decoded = xml.decode("utf-8-sig")
            except UnicodeDecodeError:
                decoded = xml.decode("cp1252")
            root = ElementTree.fromstring(decoded)
        except ElementTree.ParseError:
            continue
        tags = {n.tag.rsplit("}",1)[-1]:n for n in root.iter()
                if n.tag.rsplit("}",1)[-1] == "Channel" and len(n)}
        if "Channel" not in tags:
            continue
        child = {n.tag.rsplit("}",1)[-1]:n.text for n in tags["Channel"]}
        try:
            begin = datetime.fromisoformat(child["Start"]).replace(tzinfo=None)
            end = datetime.fromisoformat(child["End"]).replace(tzinfo=None)
        except (KeyError,ValueError,TypeError):
            continue
        if not begin <= selected <= end:
            continue
        if indexed_first and timestamp(indexed_first)[0] == selected:
            return receipt["source"]
        for node in root.iter():
            if node.tag.rsplit("}",1)[-1] not in ("AudioTimeStamp","TimeStampAudio","Start"):
                continue
            try:
                anchor = datetime.fromisoformat((node.text or "").strip())
            except ValueError:
                continue
            if anchor.tzinfo is not None:
                anchor = anchor.astimezone(timezone.utc).replace(tzinfo=None)
            if any(abs((a-anchor).total_seconds()) <= 600 for a in anchors):
                return url
    raise ValueError("Unverified recorder clock; no UTC deployment anchor within 10 min of first file")


def eligible(deployment, horizon=96):
    if deployment == HOLDOUT or not deployment.endswith("/"):
        raise ValueError("Deployment excluded")
    rows = listing(deployment+"audio/", maxResults=horizon).get("items",[])
    return [row for row in rows if row["name"].lower().endswith(".flac")
            and int(row["size"]) >= 42]


def harp_stamp(payload):
    pos = 4
    while pos + 4 <= len(payload):
        tag, length = payload[pos], int.from_bytes(payload[pos+1:pos+4],"big")
        start = pos + 4
        end = start + length
        if end > len(payload):
            break
        if tag & 127 == 2 and payload[start:start+8] == b"riffharp":
            first = start + 68
            if first + 32 > end:
                break
            year,month,day,hour,minute,second = payload[first:first+6]
            ticks = int.from_bytes(payload[first+6:first+8],"little")
            if ticks >= 1000:
                raise ValueError("Invalid XWAV millisecond field")
            return datetime(2000+year,month,day,hour,minute,second,ticks*1000)
        if tag & 128:
            break
        pos = end
    raise ValueError("Missing XWAV recorder timestamp")


def decode(item, workdir):
    size = int(item["size"])
    # Inspect the FLAC streaminfo. Copy only the prefix needed for six seconds of
    # even uncompressed samples plus room for metadata and decoder read-ahead.
    url = source_url(item)

    def byte_range(first,last):
        req = Request(url, headers={"Range":f"bytes={first}-{last}", "Accept-Encoding":"identity"})
        with urlopen(req,timeout=18) as response:
            if response.status != 206 or response.headers.get("Content-Range") != f"bytes {first}-{last}/{size}":
                raise ValueError("Unexpected object generation, size, or range")
            data = response.read(last-first+2)
        if len(data) != last-first+1:
            raise ValueError("Truncated archive range")
        return data

    head = byte_range(0,41)
    if head[:4] != b"fLaC" or head[4]&127 or int.from_bytes(head[5:8],"big") != 34:
        raise ValueError("Unsupported FLAC streaminfo")
    info = int.from_bytes(head[18:26],"big")
    rate, channels, bits, frames = info>>44, ((info>>41)&7)+1, ((info>>36)&31)+1, info&((1<<36)-1)
    if not 1000 <= rate <= 384000 or not 1 <= channels <= 8 or frames < rate*SECONDS:
        raise ValueError("Insufficient duration or unsupported audio format")
    count = min(size, 131072 + (SECONDS+1)*rate*channels*((bits+7)//8))
    if count > MAX_PREFIX:
        raise ValueError("Required FLAC prefix exceeds sample budget")
    payload = head + byte_range(42,count-1)
    xwav_stamp = harp_stamp(payload) if item["name"].lower().endswith(".x.flac") else None
    if count == size and item.get("md5Hash"):
        expected = base64.b64decode(item["md5Hash"],validate=True)
        if hashlib.md5(payload,usedforsecurity=False).digest() != expected:
            raise ValueError("Full object MD5 mismatch")
    with tempfile.TemporaryDirectory(dir=workdir) as tmp:
        path = Path(tmp)/"sample.flac"
        path.write_bytes(payload)
        result = subprocess.run(["ffmpeg","-nostdin","-v","error","-xerror","-threads","1",
                                 "-err_detect","crccheck+explode","-i",str(path),"-map","0:a:0",
                                 "-t",str(SECONDS),"-ac","1","-ar",str(RATE),"-f","s16le","-"],
                                capture_output=True,timeout=15)
    if result.returncode or len(result.stdout) != SECONDS*RATE*2:
        raise ValueError("Invalid frames or insufficient contiguous decoded audio")
    return dict(native_rate=rate,native_channels=channels,native_bits=bits,bytes_acquired=count,
                prefix_sha256=hashlib.sha256(payload).hexdigest(),pcm_sha256=hashlib.sha256(result.stdout).hexdigest(),
                object_size=size,xwav_timestamp=xwav_stamp.isoformat() if xwav_stamp else None,object_md5_base64=item.get("md5Hash")), np.frombuffer(result.stdout,"<i2")


def sample(station, sequence, workdir):
    known = {s["id"]:s for s in sources()}
    station = known[station["id"]]
    if not isinstance(sequence,int) or sequence < 0:
        raise ValueError("Expected a nonnegative per-station sequence")
    prefix = station["id"]
    deployments = [p for p in sorted(listing(prefix,delimiter="/",maxResults=96).get("prefixes",[]))
                   if p != HOLDOUT and re.fullmatch(re.escape(prefix)+r"[A-Za-z0-9_-]+/",p)]
    if not deployments:
        raise LookupError("No publicly listed deployments")
    file_number, dep_number = divmod(sequence,len(deployments))
    deployment = deployments[dep_number]
    items = eligible(deployment)
    usable = [i for i in items if not re.search(r"(?:pre|post)[-_ ]?deployment", i["name"], re.I)]
    if deployment == "sanctsound/audio/mb03/01/":
        # The deployment record gives the usable frequency/time interval.
        usable = [i for i in usable if datetime(2018,11,15,20,0,9) <= timestamp(i["name"])[0]
                  <= datetime(2019,6,10,17,0,3)]
    if file_number >= len(usable):
        raise LookupError("Bounded historical sample exhausted for deployment")
    item = usable[file_number]
    stamp, clock = timestamp(item["name"])
    anchor = None
    if clock != "explicit UTC" and not item["name"].lower().endswith(".x.flac"):
        first_stamp = timestamp(items[0]["name"])[0]
        try:
            anchor = tethys_anchor(deployment,first_stamp,stamp)
        except ValueError:
            # A SanctSound SoundTrap filename contains the instrument's UTC clock.
            # HARP (.x) and NRS objects require their own deployment evidence.
            if not (clock == "recorder clock" and ".x.flac" not in item["name"].lower()
                    and re.search(r"_\d{3,10}_\d{12}\.flac$",item["name"])):
                raise
            anchor = "https://doi.org/10.5061/dryad.x0k6djj2d"
    workdir = Path(workdir)
    workdir.mkdir(parents=True,exist_ok=True)
    m,pcm = decode(item,workdir)
    if m["xwav_timestamp"]:
        native_stamp = datetime.fromisoformat(m["xwav_timestamp"])
        if native_stamp.replace(microsecond=0) != stamp:
            raise ValueError("XWAV internal UTC and archive name disagree")
        stamp = native_stamp
        anchor = "Embedded HARP XWAV recording block timestamp"
    sanct = prefix.startswith("sanctsound/")
    doi = "10.25921/saca-sp25" if sanct else "10.7289/V5M32T0D"
    credit = ("NOAA Office of National Marine Sanctuaries and U.S. Navy" if sanct else
              "NOAA OAR PMEL, National Marine Fisheries Service, NOS ONMS and DOI National Park Service")
    m.update(recorded_at=stamp.replace(tzinfo=timezone.utc).isoformat(),source_url=source_url(item),
             source_id=f"{item['name']}#{item['generation']}",provider=station["provider"],location=station["location"],
             attribution=f"{credit}. NOAA NCEI. https://doi.org/{doi}",
             license_url=CC0, public_audio=True,clock_evidence=anchor or "explicit UTC in object name",
             object_modified_at=item["updated"],deployment=deployment,mode="historical",
             duration_s=SECONDS,playback_rate=RATE)
    return m,pcm


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workdir",type=Path)
    parser.add_argument("--sequence",default=0,type=int)
    parser.add_argument("--station",action="append")
    args=parser.parse_args()
    for s in sources():
        if args.station and s["id"] not in args.station:
            continue
        try:
            metadata,_=sample(s,args.sequence,args.workdir)
            print(json.dumps(dict(station=s["id"],status="verified",**metadata)),flush=True)
        except (OSError,ValueError,LookupError,subprocess.SubprocessError) as exc:
            print(json.dumps(dict(station=s["id"],status="skipped",error=str(exc))),flush=True)
