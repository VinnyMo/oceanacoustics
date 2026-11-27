import hashlib
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from research import noaa_sources as archive


class NOAAArchiveTests(unittest.TestCase):
    def test_station_inventory_and_holdout(self):
        rows = archive.sources()
        self.assertEqual(len({s["id"] for s in rows}),42)
        with self.assertRaises(ValueError):
            archive.eligible(archive.HOLDOUT)
        with self.assertRaises(ValueError):
            archive.timestamp("deployment_123456789.flac")
        self.assertEqual(archive.timestamp("NRS01_20141015_034021.flac")[0].isoformat(),
                         "2014-10-15T03:40:21")
        with self.assertRaises(KeyError):
            archive.sample({"id":"other/archive/"},0,".")

    def test_decoder_checks_range_and_preserves_duration(self):
        pcm = np.arange(35000,dtype="<i2")
        flac = subprocess.check_output(["ffmpeg","-loglevel","error","-f","s16le","-ar","5000",
                    "-ac","1","-i","pipe:0","-c:a","flac","-f","flac","pipe:1"],input=pcm.tobytes())
        # FFmpeg streaming FLAC specifies an unknown frame count; a seekable archive object
        # includes the frame count. Set the STREAMINFO count for this test fixture.
        info = int.from_bytes(flac[18:26],"big")
        data = flac[:18] + ((info & ~((1<<36)-1)) | len(pcm)).to_bytes(8,"big") + flac[26:]
        obj = dict(name="nrs/audio/01/test.flac",size=len(data),generation="123",
                   md5Hash=archive.base64.b64encode(hashlib.md5(data,usedforsecurity=False).digest()).decode())

        def response(request,timeout):
            start,end=map(int,request.headers["Range"][6:].split("-"))
            payload=io.BytesIO(data[start:end+1])
            payload.status=206
            payload.headers={"Content-Range":f"bytes {start}-{end}/{len(data)}"}
            return payload

        with tempfile.TemporaryDirectory() as folder, patch.object(archive,"urlopen",response):
            m,x=archive.decode(obj,Path(folder))
            self.assertEqual((x.dtype,x.shape,m["native_rate"]), (np.dtype("<i2"),(96000,),5000))
            self.assertEqual(m["prefix_sha256"],hashlib.sha256(data).hexdigest())
            self.assertEqual(list(Path(folder).iterdir()),[])
            obj["md5Hash"]="AAAAAAAAAAAAAAAAAAAAAA=="
            with self.assertRaisesRegex(ValueError,"MD5"):
                archive.decode(obj,Path(folder))
