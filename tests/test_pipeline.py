import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

from ingestion import mbari
from processing import dsp
from research.review import review
import worker


class Baseline(unittest.TestCase):
    def test_silence_and_burst(self):
        x = np.zeros(120000,dtype='f4')
        self.assertIsNone(dsp.detect(x)[1])
        x[60000:62000] = 0.5*np.sin(2*np.pi*250*np.arange(2000)/2000)
        start, hz, score = dsp.detect(x)[1]
        self.assertLessEqual(abs(hz-250),8)
        self.assertLessEqual(start,60000)
        self.assertGreater(score,12)

    def test_native_high_band_clip(self):
        rate = 16000
        x = np.zeros(60*rate,dtype='<i2')
        x[30*rate:31*rate] = 16000*np.sin(2*np.pi*5000*np.arange(rate)/rate)
        data = dsp.decode(x.tobytes(),2)
        _, (start,hz,_) = dsp.detect(data,rate)
        self.assertAlmostEqual(hz,5000,delta=8)
        self.assertLessEqual(start,30*rate)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            clip = x[start:start+6*rate]
            dsp.evidence(clip.tobytes(),2,dsp.decode(clip.tobytes(),2),folder,rate)
            with wave.open(str(folder/'original.wav'),'rb') as w:
                self.assertEqual((w.getframerate(),w.getnframes()),(16000,96000))

    def test_guard(self):
        with tempfile.TemporaryDirectory() as tmp, patch('worker.storage',return_value=45*10**9):
            with self.assertRaises(RuntimeError):
                worker.guard(Path(tmp))

    def test_range_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'id.bin'
            out.with_suffix('.part').write_bytes(b'abc')
            res = io.BytesIO(b'de')
            res.status = 206
            res.headers = {'Content-Range':'bytes 13-14/100','ETag':'"abc"'}
            rec = mbari.Recording('example.wav',100,'"abc"','')
            with patch('urllib.request.urlopen',return_value=res) as get:
                mbari.fetch(rec,10,14,out)
                self.assertEqual(get.call_args.args[0].get_header('Range'),'bytes=13-14')
                self.assertEqual(out.read_bytes(),b'abcde')
                mbari.fetch(rec,10,14,out)
                self.assertEqual(get.call_count,1)

    def test_worker_and_review(self):
        for rate in (2000,16000):
            with self.subTest(rate=rate):
                self.check_worker(rate)

    def check_worker(self,rate):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ('cache','db','public/data/events','tmp'):
                (root/folder).mkdir(parents=True)
            x = np.zeros(60*rate,dtype='<i2')
            x[30*rate:31*rate] = 16000*np.sin(2*np.pi*250*np.arange(rate)/rate)
            buf = io.BytesIO()
            with wave.open(buf,'wb') as w:
                w.setparams((1,2,rate,0,'NONE',''))
                w.writeframes(x.tobytes())
            data = buf.getvalue()
            rec = mbari.Recording(f'2015/07/MARS-20150728T000000Z-{rate//1000}kHz.wav',len(data),'"a"','2015-07-30T00:00:00Z')
            con = worker.database(root)
            with patch.object(mbari,'records',return_value=[rec]), patch.object(mbari,'fetch',side_effect=lambda r,l,h,p,**kwargs:p.write_bytes(data[l:h+1])):
                worker.work(con,root,'backfill',mbari.PacificSound(rate))
                worker.work(con,root,'backfill',mbari.PacificSound(rate))
                worker.publish(con,root,'Test')
            con.close()
            snap = root/'public/data/observatory.json'
            obj = json.loads(snap.read_text())
            self.assertEqual(obj['stats']['coverage_seconds'],60)
            event = obj['events'][0]
            self.assertTrue((root/'public'/event['audio_url'][1:]).is_file())
            with wave.open(str(root/'public'/event['lossless_url'][1:]),'rb') as clip:
                self.assertEqual((clip.getframerate(),clip.getnframes()),(rate,rate*6))
            review(root,event['id'],'Recording artifact','reviewer','Synthetic unit-test burst')
            self.assertEqual(json.loads(snap.read_text())['stats']['reviewed'],1)
            item = json.loads((root/'public/data/catalog/1.json').read_text())[0]
            self.assertEqual(item['classification'],'Recording artifact')
