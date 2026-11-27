"""Write a deterministic, public scientific closeout from the project ledger."""
import gzip
import json
from pathlib import Path
import sqlite3

DB = Path('/srv/oceanacoustics/state/db/results.sqlite')
OUT = Path(__file__).resolve().parents[1] / 'results/observations.jsonl.gz'
FIELDS = """id station provider location recorded_at processed_at source_id source_url metadata_url attribution license license_url public_audio native_rate sample_rate_hz duration_seconds frequency_hz score_db classification group_id sha256 source_sha256 native_pcm_sha256 pcm_sha256 header_sha256 etag byte_start byte_length algorithm mode zero_fraction rail_fraction rms_dbfs reference_comparison clock_evidence quality source_encoding""".split()


def export():
    immutable = '&immutable=1' if not Path(str(DB)+'-wal').exists() else ''
    con = sqlite3.connect(DB.as_uri()+'?mode=ro'+immutable, uri=True)
    con.row_factory = sqlite3.Row
    con.execute('BEGIN')
    records = []
    for row in con.execute('SELECT payload,event FROM windows ORDER BY key,etag,offset'):
        for kind, key in [('window','payload'),('candidate','event')]:
            if row[key]:
                obj = json.loads(row[key])
                records.append(dict(type=kind, **{k:obj[k] for k in FIELDS if k in obj}))
    for row in con.execute('SELECT event FROM source_samples ORDER BY id'):
        obj = json.loads(row[0])
        records.append(dict(type='source_sample', **{k:obj[k] for k in FIELDS if k in obj}))
    for table in ['ai_notes','pip_previous']:
        for row in con.execute(f"SELECT id,requested,version,model,note FROM {table} WHERE state='complete' ORDER BY id,requested"):
            records.append(dict(type='listening_review',id=row['id'],reviewed_at=row['requested'],
                                version=row['version'],model=row['model'],note=json.loads(row['note'])))
    for row in con.execute('SELECT id,context FROM ai_environment ORDER BY id'):
        records.append(dict(type='review_environment',id=row['id'],context=json.loads(row['context'])))
    for row in con.execute('SELECT id,hz,source,recurring FROM families ORDER BY id'):
        records.append(dict(type='provisional_group',**dict(row)))
    for row in con.execute('SELECT event_id,family,window_id FROM members ORDER BY event_id,family'):
        records.append(dict(type='group_membership',**dict(row)))
    for row in con.execute("SELECT site,hour,product,payload FROM environment WHERE payload IS NOT NULL ORDER BY site,hour,product"):
        records.append(dict(type='surface_model',site=row['site'],hour=row['hour'],product=row['product'],
                            reading=json.loads(row['payload'])))
    for row in con.execute("SELECT site,data FROM deployment_positions WHERE data IS NOT NULL ORDER BY site"):
        records.append(dict(type='deployment_position',site=row['site'],position=json.loads(row['data'])))
    con.close()
    content=''.join(json.dumps(r,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n' for r in records).encode()
    temporary=OUT.with_suffix('.tmp')
    temporary.write_bytes(gzip.compress(content,mtime=0))
    temporary.replace(OUT)


if __name__=='__main__':
    export()
