"""One bounded observation per mode. A singleton lock also protects atomic publication."""
import argparse
import fcntl
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
from datetime import datetime, timezone, timedelta

from scipy.signal import resample_poly

from classification.families import assign
from classification.references import compare
from ingestion import mbari
from ingestion.provider import Archive
from processing import dsp

PRIMARY = mbari.PacificSound()
GB = 10**9


def now():
    return datetime.now(timezone.utc).isoformat()


def json_write(path, data):
    temp = path.with_suffix('.tmp')
    content = json.dumps(data, allow_nan=False)
    if path.exists() and path.read_text() == content:
        return
    temp.write_text(content)
    temp.replace(path)


def usage(directory):
    return sum(p.stat().st_blocks * 512 for p in directory.rglob('*') if p.is_file() and not p.is_symlink())


def storage(root):
    # Deployment keeps all persistent project data and release files on a fixed-size filesystem.
    if root.parent.is_mount():
        fs = os.statvfs(root)
        return (fs.f_blocks-fs.f_bfree)*fs.f_frsize
    return usage(root) + usage(Path(__file__).resolve().parent)


def guard(root):
    used = storage(root)
    if used >= 40*GB:
        logging.warning('Storage above 40 GB')
    host_low = root.parent.is_mount() and shutil.disk_usage(root.parent.parent).free < 10*GB
    if used >= 45*GB or shutil.disk_usage(root).free < GB or host_low:
        raise RuntimeError('Downloads suspended for storage headroom')
    for folder, limit in [('cache',20),('db',4),('public/data/events',3),('public/data/catalog',1)]:
        if usage(root/folder) + 5_000_000 > limit*GB:
            raise RuntimeError(f'{folder} budget reached')


def evict(root):
    files = sorted((root/'cache').iterdir(),key=lambda p:p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    for p in files:
        if total > 19*GB or time.time()-p.stat().st_mtime > 86400:
            total -= p.stat().st_size
            p.unlink()


def database(root):
    con = sqlite3.connect(root/'db/results.sqlite')
    con.row_factory = sqlite3.Row
    con.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS windows(
      key TEXT, etag TEXT, offset INTEGER, frames INTEGER, mode TEXT, bytes INTEGER,
      seconds REAL, payload TEXT, event TEXT, PRIMARY KEY(key,etag,offset));
    CREATE TABLE IF NOT EXISTS inventory(key TEXT PRIMARY KEY, size INTEGER, modified TEXT);
    CREATE TABLE IF NOT EXISTS reviews(id TEXT, utc TEXT, classification TEXT, reviewer TEXT, rationale TEXT);
    CREATE TABLE IF NOT EXISTS sightings(key TEXT, etag TEXT, seen TEXT, PRIMARY KEY(key,etag));
    CREATE TABLE IF NOT EXISTS settings(name TEXT PRIMARY KEY, value TEXT);
    """)
    return con


def choose(con, month, mode, archive):
    records = sorted(archive.records(month),key=lambda r:r.key,reverse=mode=='monitor')
    with con:
        con.executemany('INSERT OR REPLACE INTO inventory VALUES(?,?,?)',
                        [(r.key,r.size,r.modified) for r in records])
        con.executemany('INSERT OR IGNORE INTO sightings VALUES(?,?,?)',[(r.key,r.etag,now()) for r in records])
    if mode == 'monitor':
        return records[:1]
    counts = dict(con.execute('SELECT key,count(*) FROM windows WHERE key LIKE ? GROUP BY key',(month+'%',)))
    return sorted(records,key=lambda rec: (counts.get(rec.key,0),rec.key))


def next_month(month):
    year, m = map(int,month.strip('/').split('/'))
    return f'{year+(m==12):04}/{m%12+1:02}/'


def work(con, root, mode, archive: Archive = PRIMARY):
    rate = archive.rate
    cursor_name = "month" if rate == 2000 else f"month-{rate}"
    evict(root)
    guard(root)
    if mode == 'monitor':
        month = archive.latest_month()
    else:
        row = con.execute("SELECT value FROM settings WHERE name=?",(cursor_name,)).fetchone()
        month = row[0] if row else archive.first_month
    for rec in choose(con,month,mode,archive):
        identity = hashlib.sha256((rec.key+rec.etag).encode()).hexdigest()[:24]
        header = root/'cache'/f'{identity}-header.bin'
        archive.fetch(rec,0,min(8191, rec.size-1),header)
        base,width,frames = archive.layout(header.read_bytes(),rec.size)
        stride = rate*dsp.WINDOW
        # Index offsets by timestamp, so monitoring and backfill cannot double-count.
        done = {r[0] for r in con.execute('SELECT offset FROM windows WHERE key=? AND etag=?',(rec.key,rec.etag))}
        offsets = range(0, frames-stride+1, stride)
        if mode=='monitor':
            offsets = reversed(offsets)
        elif len(offsets) > 720:
            # Sample each day at midday first, then fill contiguous intervals.
            from itertools import chain
            offsets = chain(offsets[720:],offsets[:720])
        offset = next((i for i in offsets if i not in done),None)
        if offset is None:
            continue
        path = root/'cache'/f'{identity}-{offset}.bin'
        left = base+offset*width
        t0 = time.monotonic()
        archive.fetch(rec,left,left+stride*width-1,path)
        acquired = now()
        raw = path.read_bytes()
        x = dsp.decode(raw,width)
        power, candidate = dsp.detect(x,rate)
        stamp = rec.start + timedelta(seconds=offset/rate)
        public = root/'public/data'
        ident = f'{identity}-{offset}'
        payload = dict(source_id=rec.key, source_url=archive.source_url(rec),etag=rec.etag,
                       source_sha256=hashlib.sha256(raw).hexdigest(),byte_start=left, byte_length=len(raw),
                       recorded_at=stamp.isoformat(),mode=mode,location=archive.location,
                       archive_modified_at=rec.modified,publication_delay_seconds=None,
                       acquired_at=acquired,duration_seconds=dsp.WINDOW,algorithm=dsp.VERSION if rate==2000 else "spectral-excess-16k-v1",
                       sample_rate_hz=rate, pcm_bits=width*8, object_size=rec.size, audio_frames=frames,
                       header_sha256=hashlib.sha256(header.read_bytes()[:base]).hexdigest(),
                       zero_fraction=float((x==0).mean()),spectrogram_url=f'/data/{ident}.png')
        first_seen = con.execute('SELECT seen FROM sightings WHERE key=? AND etag=?',(rec.key,rec.etag)).fetchone()[0]
        payload['first_seen_lag_seconds'] = (datetime.fromisoformat(first_seen)-stamp).total_seconds()
        event = None
        if candidate:
            sample,hz,score = candidate
            clipraw = raw[sample*width:(sample+rate*dsp.CLIP)*width]
            folder = public/'events'/ident
            if not folder.exists():
                with tempfile.TemporaryDirectory(dir=root/'tmp') as tmp:
                    stage = Path(tmp)/ident
                    stage.mkdir()
                    dsp.evidence(clipraw,width,x[sample:sample+dsp.CLIP*rate],stage,rate)
                    stage.rename(folder)
            prefix = f'/data/events/{ident}'
            event = dict(id=ident, recorded_at=(stamp+timedelta(seconds=sample/rate)).isoformat(),
                         sample_rate_hz=rate,duration_seconds=dsp.CLIP,frequency_hz=hz,score_db=score,source_id=rec.key,
                         source_url=archive.source_url(rec),group_id=None,classification='Unreviewed anomaly',
                         location=archive.location,audio_url=prefix+'/listen.ogg',lossless_url=prefix+'/original.wav',
                         waveform_url=prefix+'/wave.png',spectrogram_url=prefix+'/spectrum.png',
                         byte_start=left+sample*width,byte_length=len(clipraw),etag=rec.etag,
                         sha256=hashlib.sha256(clipraw).hexdigest(),algorithm=dsp.VERSION if rate==2000 else "spectral-excess-16k-v1",
                         reference_comparison=compare(resample_poly(x[sample:sample+rate*dsp.CLIP],1,rate//2000)))
            json_write(public/'events'/f'{ident}.json',event)
        image = public/f'{ident}.png'
        dsp.spectrogram(power,image.with_suffix('.tmp'))
        image.with_suffix('.tmp').replace(image)
        payload['processed_at'] = now()
        elapsed = time.monotonic()-t0
        with con:
            con.execute('INSERT INTO windows VALUES(?,?,?,?,?,?,?,?,?)',(rec.key,rec.etag,offset,stride,
                        mode,len(raw),elapsed,json.dumps(payload),json.dumps(event) if event else None))
        logging.info('%s %s offset=%d seconds=%.3f candidate=%s',mode,rec.key,offset,elapsed,bool(event))
        return
    if mode=='backfill' and month < datetime.now(timezone.utc).strftime('%Y/%m/'):
        with con:
            con.execute("INSERT OR REPLACE INTO settings VALUES(?,?)",(cursor_name,next_month(month)))


def publish(con,root,status):
    public = root/'public/data'
    assign(con,public)
    agg = con.execute("""SELECT count(*), coalesce(sum(json_extract(payload,'$.duration_seconds')),0), coalesce(sum(bytes),0),
      sum(seconds), count(event), coalesce(sum(CASE WHEN mode='backfill' THEN json_extract(payload,'$.duration_seconds') ELSE 0 END),0)/3600.
      FROM windows""").fetchone()
    latest = con.execute("SELECT payload FROM windows ORDER BY (mode='monitor') DESC, rowid DESC LIMIT 1").fetchone()
    last = con.execute('SELECT payload FROM windows ORDER BY rowid DESC LIMIT 1').fetchone()
    latest = json.loads(latest[0]) if latest else None
    events = [json.loads(r[0]) for r in con.execute('SELECT event FROM windows WHERE event IS NOT NULL ORDER BY rowid DESC LIMIT 100')]
    unique_seconds = con.execute("""SELECT coalesce(sum(duration),0) FROM (
        SELECT max(json_extract(payload,'$.duration_seconds')) AS duration FROM windows
        GROUP BY json_extract(payload,'$.location'),json_extract(payload,'$.recorded_at'))""").fetchone()[0]
    stats = dict(hours_analyzed=agg[1]/3600,coverage_seconds=unique_seconds,bytes_processed=agg[2],
                 processing_speed=agg[1]/agg[3] if agg[3] else None,events=agg[4],backfill_hours=agg[5],
                 recurring_groups=con.execute('SELECT count(*) FROM families WHERE recurring=1').fetchone()[0],reviewed=con.execute('SELECT count(DISTINCT id) FROM reviews').fetchone()[0],storage_bytes=storage(root),uptime_seconds=None,
                 last_acquisition=json.loads(last[0])['acquired_at'] if last else None,
                 silent_windows=con.execute("SELECT count(*) FROM windows WHERE json_extract(payload,'$.zero_fraction')=1").fetchone()[0],
                 inventoried_files=con.execute('SELECT count(*) FROM inventory').fetchone()[0])
    # Rebuild the public catalog after committed changes. A failed publication is retryable.
    generation = (agg[4],stats['recurring_groups'],con.execute('SELECT count(*) FROM reviews').fetchone()[0])
    cache = con.execute("SELECT value FROM settings WHERE name='catalog'").fetchone()
    if not cache or cache[0] != str(generation):
        catalog = public/'catalog'
        catalog.mkdir(exist_ok=True)
        cursor = con.execute('SELECT event FROM windows WHERE event IS NOT NULL ORDER BY rowid DESC')
        page = 1
        while batch := cursor.fetchmany(100):
            items = [json.loads(r[0]) for r in batch]
            for item in items:
                json_write(public/'events'/(item['id']+'.json'),item)
            json_write(catalog/f'{page}.json',items)
            page += 1
        with con:
            con.execute("INSERT OR REPLACE INTO settings VALUES('catalog',?)",(str(generation),))
    if os.environ.get('OCEAN_TIMER') == '1':
        tick = time.time()
        beat = con.execute("SELECT value FROM settings WHERE name='heartbeat'").fetchone()
        started, previous = json.loads(beat[0]) if beat else [tick,tick]
        if tick-previous > 900 or tick < previous:
            started = tick
        with con:
            con.execute("INSERT OR REPLACE INTO settings VALUES('heartbeat',?)",(json.dumps([started,tick]),))
        stats['uptime_seconds'] = tick-started
    if stats['storage_bytes'] >= 40*GB:
        status += ' • storage above 40 GB'
    json_write(public/'observatory.json',dict(generated_at=now(),status=status,latest=latest,stats=stats,events=events))
    if latest:
        for p in public.glob('*.png'):
            if p.name != latest['spectrogram_url'].split('/')[-1] and time.time()-p.stat().st_mtime>600:
                p.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode',choices=['monitor','backfill','both'])
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--rate',type=int,choices=(2000,16000),default=16000)
    args = parser.parse_args()
    root = args.state.resolve()
    for name in ['db','cache','tmp','logs','public/data/events']:
        (root/name).mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,handlers=[logging.StreamHandler(),
                        RotatingFileHandler(root/'logs/worker.log',maxBytes=1_000_000,backupCount=3)])
    with (root/'worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return
        con = database(root)
        try:
            for mode in (['monitor','backfill'] if args.mode=='both' else [args.mode]):
                if mode == 'backfill' and os.getloadavg()[0] > float(os.environ.get('BACKFILL_LOAD_LIMIT','4')):
                    logging.info('Backfill deferred for host load')
                    continue
                if os.environ.get('ENABLE_'+mode.upper(),'1')=='1':
                    publish(con,root,'Analyzing '+mode+' window')
                    work(con,root,mode,mbari.PacificSound(args.rate))
                    publish(con,root,'Waiting for next acquisition')
        except Exception:
            logging.exception('Worker run failed')
            publish(con,root,'Acquisition paused • retry scheduled')
            raise
        finally:
            con.close()


if __name__ == '__main__':
    main()
