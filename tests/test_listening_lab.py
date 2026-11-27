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
            e['environment']=dict(hour='2020-01-01T01:00',position=dict(lat=1,lon=2),
                conditions={'weather':dict(valid_at='2020-01-01T01:00Z',values={'temperature_2m':[6,'°C']})})
            q=dict(ai_limit=1,ai_attempts=0)
            with patch.object(analyst,'KEY_PATH',key),patch.object(analyst,'request_note',side_effect=TimeoutError) as req:
                self.assertIn('TimeoutError',analyst.analyze(con,root,[e],q))
                self.assertEqual(analyst.ranked([e],con),[])
                self.assertEqual(con.execute('select count(*) from ai_notes').fetchone()[0],1)
                self.assertIn('allowance',analyst.analyze(con,root,[e],dict(q,ai_attempts=1)))
                req.assert_called_once()
                context=req.call_args.args[2]['recording_environment']
                self.assertEqual(context['surface_models']['weather']['values']['temperature_2m'],[6,'°C'])
                self.assertEqual(json.loads(con.execute('SELECT context FROM ai_environment').fetchone()[0]),context)
            con.close()

    def test_archive_inventory_interleaves_providers(self):
        sites=feed.stations()
        self.assertEqual(len(sites),len({s['id'] for s in sites}))
        self.assertGreaterEqual(len(sites),53)
        self.assertEqual(len({s['provider'] for s in sites[:4]}),4)

    def test_monthly_ledger_with_rollover_and_missing_receipts(self):
        import sqlite3
        con=sqlite3.connect(':memory:')
        self.addCleanup(con.close)
        analyst.schema(con)
        usage=json.dumps(dict(prompt_tokens=536,prompt_tokens_details=dict(audio_tokens=60),completion_tokens=93))
        for ident,month,state,receipt in [('a','11','complete',usage),('b','11','reserved',None),
                                          ('c','11','complete','{}'),('d','10','reserved',None)]:
            con.execute('INSERT INTO ai_notes(id,requested,state,usage) VALUES(?,?,?,?)',
                        (ident,'2026-'+month+'-10',state,receipt))
        with patch.dict('os.environ',OCEAN_AI_MONTHLY_USD='25'):
            ledger=analyst.monthly_budget(con,'2026-11-28')
            self.assertEqual(ledger['ai_committed_micro'],104040)
            self.assertEqual(analyst.monthly_budget(con,'2026-12-01')['ai_committed_micro'],0)
        with patch.dict('os.environ',OCEAN_AI_MONTHLY_USD='0'),patch.object(analyst,'request_note') as call:
            self.assertIn('budget reached',analyst.analyze(con,Path('.'),[],dict(ai_limit=3)))
            call.assert_not_called()

    def test_measured_entries_have_no_inferred_source(self):
        from research.curator import catalog_note
        entry=catalog_note(dict(frequency_hz=310,score_db=12),None)
        self.assertEqual((entry['genre'],entry['mood'],entry['basis']),('Unidentified',None,'Measured description'))
        self.assertIn('310.0 Hz',entry['explanation'])

    def test_startup_sweep_resumes_and_preserves_billing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'db').mkdir()
            con=database(root)
            self.addCleanup(con.close)
            analyst.schema(con)
            events=[dict(id=str(i),score_db=i,location='test',audio_url='/clip') for i in range(7)]
            for e in events:
                con.execute("INSERT INTO windows(event) VALUES(?)",(json.dumps(e),))
            cohort=analyst.startup(con)
            self.assertEqual(len(cohort),7)
            con.execute("INSERT INTO windows(event) VALUES(?)",(json.dumps(dict(id='future')),))
            self.assertEqual(analyst.startup(con),cohort)
            from datetime import datetime,timezone
            now=datetime.now(timezone.utc).isoformat()
            con.execute("INSERT INTO ai_notes(id,station,requested,version,state,note) VALUES('6','test',?,'old','complete',?)",
                        (now,json.dumps(dict(check='check'))))
            key=root/'key';key.write_text('placeholder')
            result=(dict(check='check'),{},'receipt','model')
            quality=dict(ai_limit=99)
            with patch.dict('os.environ',OCEAN_AI_MONTHLY_USD='25'),patch.object(analyst,'KEY_PATH',key),patch.object(analyst,'prepare_audio',return_value=(b'pcm',0)),patch.object(analyst,'request_note',return_value=result) as call:
                analyst.review_cycle(con,root,events,quality)
                self.assertEqual(quality['startup_complete'],4)
                analyst.review_cycle(con,root,events,quality)
                self.assertEqual(quality['startup_complete'],7)
                analyst.review_cycle(con,root,events,quality)
                self.assertEqual(call.call_count,7)
            self.assertEqual(analyst.attempt_count(con),8)
            self.assertEqual(analyst.monthly_budget(con,now),{})
            with patch.dict('os.environ',OCEAN_AI_MONTHLY_USD='25'):
                self.assertEqual(analyst.monthly_budget(con,now)['ai_committed_micro'],8*analyst.RESERVE_MICRO)
