"""Exploratory single-exemplar matching. A group needs two different source days."""
import json
import wave

import numpy as np
from processing.dsp import decode, spectrum

VERSION = 'spectral-shape-v1'


def fingerprint(path):
    with wave.open(str(path), 'rb') as w:
        rate = w.getframerate()
        x = decode(w.readframes(w.getnframes()), w.getsampwidth())
    # Take the 80th percentile magnitude in each frequency bin, then pool adjacent bins.
    profile = np.percentile(spectrum(x, rate)[1:], 80, axis=1).reshape(-1, 4).mean(axis=1)
    profile = np.sqrt(profile)
    return profile / max(1e-12, np.linalg.norm(profile))


def assign(con, public):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS families(id TEXT PRIMARY KEY, hz REAL, vector TEXT, source TEXT, recurring INTEGER);
    CREATE INDEX IF NOT EXISTS family_frequency ON families(hz);
    CREATE TABLE IF NOT EXISTS members(event_id TEXT PRIMARY KEY, family TEXT, window_id INTEGER UNIQUE);
    CREATE INDEX IF NOT EXISTS family_members ON members(family);
    """)
    pending = con.execute("""SELECT rowid,event FROM windows WHERE event IS NOT NULL
        AND rowid NOT IN (SELECT window_id FROM members) ORDER BY rowid""").fetchall()
    for rowid, encoded in pending:
        e = json.loads(encoded)
        hz = e['frequency_hz']
        vec = fingerprint(public/'events'/e['id']/'original.wav')
        best, similarity = None, 0.97
        for family in con.execute('SELECT * FROM families WHERE hz BETWEEN ? AND ? ORDER BY id',
                                  (hz-8,hz+8)):
            exemplar = json.loads(family['vector'])
            if len(exemplar) != len(vec):
                continue
            score = float(vec @ exemplar)
            if score >= similarity:
                best, similarity = family, score
        with con:
            if best is None:
                family_id = e['id']
                con.execute('INSERT INTO families VALUES(?,?,?,?,0)',(family_id,hz,json.dumps(vec.tolist()),e['source_id']))
            else:
                family_id = best['id']
            con.execute('INSERT INTO members VALUES(?,?,?)',(e['id'],family_id,rowid))
            if best and (best['recurring'] or best['source'] != e['source_id']):
                con.execute('UPDATE families SET recurring=1 WHERE id=?',(family_id,))
                rows = con.execute("""SELECT w.rowid,w.event FROM windows w JOIN members m ON w.rowid=m.window_id
                    WHERE m.family=? AND json_extract(w.event,'$.group_id') IS NULL""",(family_id,)).fetchall()
                for i, data in rows:
                    event = json.loads(data)
                    event.update(group_id=family_id,group_algorithm=VERSION)
                    con.execute('UPDATE windows SET event=? WHERE rowid=?',(json.dumps(event),i))
