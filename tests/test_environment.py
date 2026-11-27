import sqlite3
import unittest
from unittest.mock import patch

from research import environment as env


class EnvironmentalContext(unittest.TestCase):
    def setUp(self):
        self.con=sqlite3.connect(':memory:')
        self.addCleanup(self.con.close)
        self.events=[dict(id=str(i),location='MARS',recorded_at=t,audio_url='/clip',score_db=8)
                     for i,t in enumerate(['2015-07-29T05:23:00-07:00','2015-07-29T12:59:59Z'])]
        self.events.append(dict(id='u',station='unknown',location='Unverified site',
                                recorded_at='2015-07-29T12:01:00Z',audio_url='/clip'))

    def test_hour_join_backfill_deduplication_and_outage(self):
        def product(sites,kind,hour,today):
            if kind=='marine' and hour!='current':
                raise OSError
            return [dict(values={'test':[0,'m']},valid_at=hour) for _ in sites]
        with patch.object(env,'fetch_product',side_effect=product) as fetch:
            sites,grid=env.enrich(self.con,self.events)
            self.assertEqual(fetch.call_count,6)
            env.enrich(self.con,self.events)
            self.assertEqual(fetch.call_count,8)
        for e in self.events[:2]:
            ctx=e['environment']
            self.assertEqual(ctx['hour'],'2015-07-29T12:00')
            self.assertEqual(ctx['conditions']['weather']['valid_at'],ctx['hour'])
            self.assertNotIn('marine',ctx['conditions'])
        self.assertIn('marine',sites[0]['current'])
        self.assertEqual(self.events[-1]['environment']['conditions'],{})
        self.assertIsNone(sites[-1]['position'])

    def test_offline_publication_and_coordinate_provenance(self):
        with patch.object(env,'fetch_product') as fetch:
            sites,grid=env.enrich(self.con,self.events,acquire=False)
            fetch.assert_not_called()
        self.assertEqual(len(sites[0]['clips']),2)
        self.assertEqual(env.recording_hour(dict(recorded_at='2010-01-01T00:00')),None)
        self.assertEqual(env.position_key({'deployment':'sanctsound/audio/ci01/sanctsound_ci01_01/'}),'sanctsound_ci01_01')
        for key in env.REGISTRY['positions']:
            pos=env.position(key)
            self.assertTrue(-90<=pos['lat']<=90 and -180<=pos['lon']<=180)
            self.assertTrue(pos['source'].startswith('https://'))
