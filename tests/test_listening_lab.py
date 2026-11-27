import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np
from processing.listening import add_listening
from research import analyst,feed
from worker import database


class Lab(unittest.TestCase):
    def test_low_band_and_credit_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'db').mkdir()
            folder=root/'public/data/events/example'
            folder.mkdir(parents=True)
            rate=16000
            x=np.rint(5*np.sin(2*np.pi*40*np.arange(rate*6)/rate)).astype('<i2')
            path=folder/'original.wav'
            with wave.open(str(path),'wb') as w:
                w.setparams((1,2,rate,0,'NONE','')); w.writeframes(x.tobytes())
            original=path.read_bytes()
            e=dict(id='example',audio_url='/data/events/example/listen.ogg',frequency_hz=40,location='test')
            add_listening(e,folder)
            self.assertGreater(e['boost_gain_db'],45)
            self.assertGreater((folder/'lowband.ogg').stat().st_size,100)
            self.assertEqual(original,path.read_bytes())
            con=database(root)
            analyst.schema(con)
            key=root/'test-key'
            key.write_text('placeholder')
            q=dict(ai_limit=1,ai_attempts=0)
            with patch.object(analyst,'KEY_PATH',key),patch.object(analyst,'request_note',side_effect=TimeoutError) as req:
                self.assertIn('TimeoutError',analyst.analyze(con,root,[e],q))
                self.assertEqual(analyst.ranked([e],con),[])
                self.assertEqual(con.execute('select count(*) from ai_notes').fetchone()[0],1)
                self.assertIn('allowance',analyst.analyze(con,root,[e],dict(q,ai_attempts=1)))
                req.assert_called_once()
            con.close()

    def test_archive_inventory_interleaves_providers(self):
        sites=feed.stations()
        self.assertEqual(len(sites),len({s['id'] for s in sites}))
        self.assertGreaterEqual(len(sites),53)
        self.assertEqual(len({s['provider'] for s in sites[:4]}),4)
