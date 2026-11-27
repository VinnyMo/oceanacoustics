import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from research import analyst,curator


class ListeningPicks(unittest.TestCase):
    def test_reviewed_catalog_and_animal_first_picks(self):
        con=sqlite3.connect(':memory:')
        self.addCleanup(con.close)
        analyst.schema(con)
        events=[]
        for i,(genre,character,score) in enumerate([
            ('Machinery','steady machinery',5),('Recording artifact','static or background',5),
            ('Ice & water','distinct patterned sound',5),('Other marine life','animal-like call',3),
            ('Dolphins','animal-like call',4),('Unidentified','unclear',5),
            ('Whales',None,None),('Whales','animal-like call',5),('Pending',None,None)]):
            ident=str(i)
            events.append(dict(id=ident,location='A',public_audio=i!=7,audio_url='/clip',recorded_at='2017-04-01'))
            if genre=='Pending':
                continue
            note=dict(title=ident,observation='Observation',hypothesis='Uncertain',genre=genre,priority=5)
            if character:
                note.update(listening_interest=score,character=character)
            con.execute("INSERT INTO ai_notes(id,note,requested,state) VALUES(?,?,?,'complete')",
                        (ident,json.dumps(note),f'2026-11-0{i+1}'))
        with tempfile.TemporaryDirectory() as tmp:
            pub=Path(tmp)
            curator.publish_catalog(con,pub,events)
            picks=json.loads((pub/'animal-first-picks.json').read_text())
            self.assertEqual([p['event']['id'] for p in picks],['4','3','2'])
            self.assertEqual(len(json.loads((pub/'showcase.json').read_text())),7)
            curator.publish_catalog(con,pub,events[-2:])
            self.assertEqual(json.loads((pub/'picks.json').read_text()),[])
