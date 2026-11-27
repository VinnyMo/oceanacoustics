import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from research import analyst,curator


class ListeningPicks(unittest.TestCase):
    def test_rank_playable_reviews_and_keep_legacy_score_provenance(self):
        con=sqlite3.connect(':memory:')
        self.addCleanup(con.close)
        analyst.schema(con)
        events=[]
        for i,place in enumerate(('A','A','B','A','C','D','E')):
            ident=str(i)
            events.append(dict(id=ident,location=place,public_audio=i!=5,audio_url='/clip',recorded_at='2017-04-01'))
            if i==6:
                continue
            note=dict(title=ident,observation='Measured whistle',hypothesis='Uncertain',priority=5)
            if i!=2:
                note['listening_interest']=[4,5,0,5,1,5][i]
            con.execute("INSERT INTO ai_notes(id,note,requested,state) VALUES(?,?,?,'complete')",
                        (ident,json.dumps(note),f'2026-11-0{i+1}'))
        with tempfile.TemporaryDirectory() as tmp:
            pub=Path(tmp)
            curator.publish_catalog(con,pub,events)
            picks=json.loads((pub/'picks.json').read_text())
            self.assertEqual([p['event']['id'] for p in picks],['3','2','1','0','4'])
            self.assertEqual([p['basis'] for p in picks[:2]],['Listening interest','Review priority'])
            curator.publish_catalog(con,pub,events[-2:])
            self.assertEqual(json.loads((pub/'picks.json').read_text()),[])
