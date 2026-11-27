"""Record a local human decision with an append-only audit trail; publish only its label."""
import argparse
import fcntl
import json
from pathlib import Path

from worker import database, now, publish

LABELS = ('Known sound','Probable match','Unidentified recurring pattern','Isolated anomaly','Recording artifact','Uncertain')


def review(root, ident, label, reviewer, rationale):
    if label not in LABELS or not reviewer.strip() or not rationale.strip():
        raise ValueError('A classification, reviewer and rationale are required')
    with (root/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        con = database(root)
        with con:
            row = con.execute("SELECT rowid,event FROM windows WHERE json_extract(event,'$.id')=?",(ident,)).fetchone()
            if row is None:
                raise ValueError('Unknown event')
            event = json.loads(row['event'])
            event.update(classification=label,review_status='Reviewed')
            con.execute('INSERT INTO reviews VALUES(?,?,?,?,?)',(ident,now(),label,reviewer,rationale))
            con.execute('UPDATE windows SET event=? WHERE rowid=?',(json.dumps(event),row['rowid']))
        publish(con,root,'Review published')
        con.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('state',type=Path)
    p.add_argument('event_id')
    p.add_argument('classification',choices=LABELS)
    p.add_argument('reviewer')
    p.add_argument('rationale')
    a = p.parse_args()
    review(a.state,a.event_id,a.classification,a.reviewer,a.rationale)
