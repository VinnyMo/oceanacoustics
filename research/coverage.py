"""Export observed effort and explicit unprocessed intervals for each inventoried version."""
import argparse
import json
from pathlib import Path
import sqlite3


def intervals(rows):
    ranges = []
    for start, length in rows:
        if ranges and start == ranges[-1][1]:
            ranges[-1][1] += length
        else:
            ranges.append([start,start+length])
    return ranges


def report(root):
    with sqlite3.connect((root/'db/results.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as con:
        for key,etag in con.execute('SELECT key,etag FROM sightings ORDER BY key,etag'):
            rows = con.execute('SELECT offset,frames,payload FROM windows WHERE key=? AND etag=? ORDER BY offset',(key,etag)).fetchall()
            covered = intervals((r[0],r[1]) for r in rows)
            frames = next((json.loads(r[2])['audio_frames'] for r in rows if 'audio_frames' in json.loads(r[2])),None)
            gaps = []
            previous = 0
            for left,right in covered:
                if previous<left:
                    gaps.append([previous,left])
                previous=right
            if frames is None or previous<frames:
                gaps.append([previous,frames])
            yield dict(source_id=key,etag=etag,rate_hz=16000 if key.endswith("-16kHz.wav") else 2000,analyzed_sample_ranges=covered,
                       unprocessed_sample_ranges=gaps,all_zero_windows=sum(json.loads(r[2])['zero_fraction']==1 for r in rows))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('state',type=Path)
    for item in report(p.parse_args().state):
        print(json.dumps(item))
