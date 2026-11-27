"""Round-robin source sampling, quality metrics and a static public research notebook."""
import hashlib
from itertools import zip_longest
import json
import logging
import os
from pathlib import Path
import tempfile
import time

import numpy as np
from scipy.signal import welch

from processing import dsp
from processing.listening import add_listening
from research import analyst,curator,environment,noaa_sources,orcasound,polar


def stations():
    # Interleave archives so the initial samples already span recording environments.
    noaa=noaa_sources.sources()
    lists=[polar.sources(),orcasound.sources()]
    lists.extend([s for s in noaa if s['provider']==p] for p in sorted({s['provider'] for s in noaa}))
    return [s for batch in zip_longest(*lists) for s in batch if s]


def schema(con):
    analyst.schema(con)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS source_visits(id TEXT PRIMARY KEY, attempts INTEGER,status TEXT,last_visit TEXT);
        CREATE TABLE IF NOT EXISTS source_samples(id TEXT PRIMARY KEY,station TEXT,event TEXT);
    """)


def sample_one(con,root,all_sites):
    from worker import guard,json_write,now
    guard(root)
    visits={r[0]:r[1] for r in con.execute('SELECT id,attempts FROM source_visits')}
    site=min(all_sites,key=lambda s:visits.get(s['id'],0))
    sequence=visits.get(site['id'],0)
    sid=site['id']
    with con:
        con.execute('INSERT OR REPLACE INTO source_visits VALUES(?,?,?,?)',(sid,sequence+1,'Sampling',now()))
    adapter=polar if sid.startswith('pangaea/') else orcasound if sid.startswith('orcasound/') else noaa_sources
    try:
        with tempfile.TemporaryDirectory(dir=root/'tmp') as tmp:
            stage=Path(tmp)
            meta,x=adapter.sample(site,sequence,stage)
            if x.shape!=(96000,) or x.dtype!=np.dtype('<i2'):
                raise ValueError('Expected six seconds of mono PCM16')
            ident='src-'+hashlib.sha256((sid+meta['source_url']+meta['recorded_at']).encode()).hexdigest()[:32]
            prefix='/data/events/'+ident
            pcm=x.tobytes()
            y=dsp.decode(pcm,2)
            f,p=welch(y,16000,nperseg=2048)
            usable=(f>=15)&(f<=min(8000,meta['native_rate']/2))
            hz=float(f[usable][np.argmax(p[usable])])
            event=dict(meta,id=ident,station=sid,provider=site['provider'],location=site['location'],
                       classification='Archive sample',duration_seconds=6,sample_rate_hz=16000,frequency_hz=hz,
                       sha256=hashlib.sha256(pcm).hexdigest(),processed_at=now(),
                       rms_dbfs=round(float(10*np.log10(max(1e-20,np.mean(y*y)))),2),
                       zero_fraction=float(np.mean(x==0)),rail_fraction=float(np.mean((x==32767)|(x==-32768))))
            if event['public_audio']:
                folder=root/'public/data/events'/ident
                event.update(audio_url=prefix+'/listen.ogg',lossless_url=prefix+'/original.wav',
                             waveform_url=prefix+'/wave.png',spectrogram_url=prefix+'/spectrum.png')
                clips=stage/'evidence'
                clips.mkdir()
                dsp.evidence(pcm,2,y,clips,16000)
                add_listening(event,clips)
                if not folder.exists():
                    clips.rename(folder)
                event['artifact_bytes']=sum(p.stat().st_size for p in folder.iterdir())+8192
                json_write(folder.with_suffix('.json'),event)
            with con:
                con.execute('INSERT OR IGNORE INTO source_samples VALUES(?,?,?)',(ident,sid,json.dumps(event)))
            status='Sample verified'
    except Exception as exc:
        status='Temporarily unavailable'
        logging.warning('Source %s: %s',sid,type(exc).__name__)
    with con:
        con.execute('UPDATE source_visits SET status=? WHERE id=?',(status,sid))


def update(con,root,acquire=True,enable_ai=True):
    from worker import guard,json_write,now
    guard(root)
    schema(con)
    sites=stations()
    footprint=con.execute("SELECT coalesce(sum(json_extract(event,'$.artifact_bytes')),0) FROM source_samples").fetchone()[0]
    if acquire and footprint < 400_000_000:
        remaining=len(sites)-con.execute('SELECT count(*) FROM source_visits').fetchone()[0]
        deadline=time.monotonic()+35
        for _ in range(min(3,max(1,remaining))):
            sample_one(con,root,sites)
            if time.monotonic()>=deadline:
                break
    public=root/'public/data'
    snapshot=json.loads((public/'observatory.json').read_text())
    st=snapshot['stats']
    visits={r[0]:r[1] for r in con.execute('SELECT id,status FROM source_visits')}
    counts=dict(con.execute('SELECT station,count(*) FROM source_samples GROUP BY station'))
    for s in sites:
        s.update(status=visits.get(s['id'],'Queued'),clips=counts.get(s['id'],0))
    mbari=dict(id='mbari/mars',provider='MBARI Pacific Sound',location='Monterey Bay, MARS',
               status='Monitoring',clips=st['events'])
    times=con.execute("""SELECT min(json_extract(payload,'$.processed_at')),max(json_extract(payload,'$.processed_at')),
                        count(*) FROM windows""").fetchone()
    events=[json.loads(r[0]) for r in con.execute('SELECT event FROM windows WHERE event IS NOT NULL UNION ALL SELECT event FROM source_samples')]
    quality=dict(distinct_seconds=st['coverage_seconds'],processed_hours=st['hours_analyzed'],
                 recurring_groups=st['recurring_groups'],candidates=st['events'],reviewed=st['reviewed'],
                 silent_windows=st['silent_windows'],windows=times[2],first_processed_at=times[0],
                 latest_processed_at=times[1],sites_sampled=len(counts)+int(times[2]>0),
                 source_samples=sum(counts.values()),source_seconds=6*sum(counts.values()),
                 ai_attempts=con.execute('SELECT count(*) FROM ai_notes').fetchone()[0],
                 ai_limit=max(0,int(os.getenv('OCEAN_AI_LIMIT','3'))))
    sq=con.execute("""SELECT count(json_extract(event,'$.rail_fraction')),
                    coalesce(sum(json_extract(event,'$.rail_fraction')>0),0),
                    coalesce(sum(json_extract(event,'$.zero_fraction')=1),0) FROM source_samples""").fetchone()
    quality.update(source_quality_n=sq[0],rail_samples=sq[1],zero_source_samples=sq[2])
    mapped,grid=environment.enrich(con,events,acquire)
    inventory=environment.inventory(con,events)
    status=analyst.review_cycle(con,root,events,quality,enable_ai)
    quality['ai_attempts']=analyst.attempt_count(con)
    reviewed={r[0] for r in con.execute("SELECT id FROM ai_notes WHERE state='complete'")}
    quality['ai_completed']=len(reviewed)
    for site in mapped:
        site['clips']=[c for c in site['clips'] if c['id'] in reviewed]
    json_write(public/'globe.json',dict(generated_at=now(),sites=mapped,grid=grid))
    notes=[]
    for r in con.execute("""SELECT id,model,requested,note FROM ai_notes WHERE state='complete'
                             ORDER BY json_extract(note,'$.priority') DESC,requested DESC LIMIT 50"""):
        event=json.loads((public/'events'/(r[0]+'.json')).read_text())
        note=json.loads(r[3])
        notes.append(dict(note,event=event,model=r[1],created_at=r[2],
                          title=curator.catalog_note(event,note)['title']))
    quality.update(analyst.monthly_budget(con,now()))
    quality['cataloged']=curator.publish_catalog(con,public,events)
    picks=json.loads((public/'animal-first-picks.json').read_text())
    json_write(public/'research.json',dict(featured_id=picks[0]['event']['id'] if picks else None,generated_at=now(),status=status,quality=quality,inventory=inventory,
               notes=notes,queue=[],sources=[mbari,*sites],source_clips=[]))
