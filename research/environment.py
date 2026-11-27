"""Join public model output to recording hours and maintain current station conditions."""
from collections import Counter
from datetime import datetime, timezone, timedelta
import json
import logging
import math
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

REGISTRY = json.loads(Path(__file__).with_name('positions.json').read_text())
GRID = json.loads(Path(__file__).with_name('model_grid.json').read_text())
WEATHER = 'temperature_2m,wind_speed_10m,wind_direction_10m,precipitation'
MARINE = 'wave_height,sea_surface_temperature,ocean_current_velocity,ocean_current_direction'
FORECAST = 'https://api.open-meteo.com/v1/forecast'
ARCHIVE = 'https://archive-api.open-meteo.com/v1/archive'
OCEAN = 'https://marine-api.open-meteo.com/v1/marine'


def position_key(event):
    if event.get('deployment'):
        return event['deployment'].strip('/').split('/')[-1].lower()
    return event.get('station') or 'mbari/mars'


def position(key):
    entry = REGISTRY['positions'].get(key)
    if entry:
        lat, lon, source, basis = entry
        return dict(lat=lat, lon=lon, source=REGISTRY['sources'][source], basis=basis)


def resolve_sanctsound(con,sites,epoch):
    # Subsequent deployments can arrive before the NOAA bulk table is refreshed.
    con.execute("CREATE TABLE IF NOT EXISTS deployment_positions(site TEXT PRIMARY KEY,retry INTEGER,data TEXT)")
    cached={k:(retry,json.loads(data) if data else None) for k,retry,data in
            con.execute('SELECT site,retry,data FROM deployment_positions')}
    attempted=False
    for key,site in sites.items():
        if site['position'] or not (match:=re.fullmatch(r'sanctsound_([a-z]{2}[0-9]{2})_([0-9]{2})',key)):
            continue
        retry,geo=cached.get(key,(0,None))
        if not geo and not attempted and retry<=epoch:
            attempted=True
            station,sequence=match.groups()
            name=f'SanctSound_{station.upper()}_{sequence}'
            url=f'https://storage.googleapis.com/noaa-passive-bioacoustic/sanctsound/audio/{station}/{key}/metadata/{name}.json'
            try:
                with urlopen(url,timeout=4) as r:
                    meta=json.loads(r.read(65536))
                lat,lon=(float(meta['LOCATION'][k]) for k in ('lat','lon'))
                if meta['DEPLOYMENT_NAME'].lower()==key and -90<=lat<=90 and -180<=lon<=180:
                    geo=dict(lat=lat,lon=lon,source=url,basis='Published deployment position')
            except (OSError,ValueError,KeyError,TypeError):
                pass
            with con:
                con.execute('INSERT OR REPLACE INTO deployment_positions VALUES(?,?,?)',
                            (key,epoch+86400,json.dumps(geo) if geo else None))
        site['position']=geo


def recording_hour(event):
    try:
        stamp = datetime.fromisoformat(event['recorded_at'])
        if stamp.tzinfo:
            return stamp.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:00')
    except (KeyError, ValueError, TypeError):
        pass


def fetch_product(sites, product, hour, today):
    current = hour == 'current'
    old = not current and hour[:10] < (today-timedelta(days=6)).isoformat()
    weather = product == 'weather'
    endpoint = (ARCHIVE if old else FORECAST) if weather else OCEAN
    fields = WEATHER if weather else MARINE
    args = dict(latitude=','.join(str(p['lat']) for p in sites),
                longitude=','.join(str(p['lon']) for p in sites), timezone='GMT')
    if weather:
        args.update(elevation=','.join(['nan']*len(sites)), cell_selection='nearest')
        if old:
            args['models'] = 'era5'
    elif not current and hour[:10] < '2022-01-01':
        args['models'] = 'era5_ocean'
        fields = 'wave_height'
    mode = 'current' if current else 'hourly'
    args[mode] = fields
    if not current:
        args.update(start_date=hour[:10], end_date=hour[:10])
    url = endpoint+'?'+urlencode(args)
    with urlopen(url, timeout=5) as response:
        raw = response.read(200001)
    if len(raw)>200000:
        raise ValueError('Oversized environmental response')
    data = json.loads(raw)
    items = data if isinstance(data,list) else [data]
    if len(items)!=len(sites):
        raise ValueError('Unexpected number of grid cells')
    out=[]
    for item in items:
        if item['utc_offset_seconds']!=0:
            raise ValueError('Expected UTC model timestamps')
        block=item[mode]
        index=None if current else block['time'].index(hour)
        stamp=block['time'] if current else hour
        datetime.strptime(stamp,'%Y-%m-%dT%H:%M')
        values={}
        for field in fields.split(','):
            v=block[field] if current else block[field][index]
            if isinstance(v,(int,float)) and math.isfinite(v):
                values[field]=[v,item[mode+'_units'][field]]
        out.append(dict(valid_at=stamp+'Z', values=values, grid=[item['latitude'],item['longitude']],
                        product=args.get('models','best match'), url=url))
    return out


def enrich(con,events,acquire=True):
    now=datetime.now(timezone.utc)
    epoch=int(now.timestamp())
    con.execute("""CREATE TABLE IF NOT EXISTS environment(
        site TEXT, hour TEXT, product TEXT, retry INTEGER, payload TEXT, PRIMARY KEY(site,hour,product))""")
    rows={(s,h,p):(retry,json.loads(raw) if raw else None)
          for s,h,p,retry,raw in con.execute('SELECT * FROM environment')}
    sites={}
    pending={}
    for event in events:
        key=position_key(event)
        site=sites.setdefault(key,dict(id=key,name=event['location'],position=position(key),clips=[]))
        hour=recording_hour(event)
        if hour:
            for product in ('weather','marine'):
                pending.setdefault((key,hour,product),event.get('score_db') is not None)
        if event.get('audio_url') and event.get('public_audio',True):
            site['clips'].append(dict(id=event['id'],recorded_at=event['recorded_at'],
                                      kind='Archive sample' if event.get('station') else 'Anomaly'))

    if acquire:
        resolve_sanctsound(con,sites,epoch)
    elif con.execute("SELECT 1 FROM sqlite_master WHERE name='deployment_positions'").fetchone():
        for key,raw in con.execute('SELECT site,data FROM deployment_positions WHERE data IS NOT NULL'):
            if key in sites and not sites[key]['position']:
                sites[key]['position']=json.loads(raw)

    grid={f'grid/{lat}/{lon}':dict(position=dict(lat=lat,lon=lon),ocean=ocean) for lat,lon,ocean in GRID}
    locations={**sites,**grid}

    def retrieve(keys,hour,product,refresh_seconds=3600):
        try:
            samples=fetch_product([locations[k]['position'] for k in keys],product,hour,now.date())
        except (OSError,ValueError,TypeError,KeyError,IndexError) as exc:
            logging.warning('Environmental %s lookup: %s', product,type(exc).__name__)
            samples=[None]*len(keys)
        with con:
            for key,sample in zip(keys,samples):
                old=rows.get((key,hour,product),(0,None))[1]
                ttl=refresh_seconds if hour=='current' else (86400 if hour[:10]==now.date().isoformat() else 30*86400)
                if sample is None:
                    ttl=1800
                    sample=old
                else:
                    sample['retrieved_at']=now.isoformat()
                    if sample['values'] and hour!='current' and hour[:10]<(now.date()-timedelta(days=7)).isoformat():
                        ttl=10**10
                rows[key,hour,product]=(epoch+ttl,sample)
                con.execute('INSERT OR REPLACE INTO environment VALUES(?,?,?,?,?)',
                            (key,hour,product,epoch+ttl,json.dumps(sample) if sample else None))

    if acquire:
        for product in ('weather','marine'):
            due=sorted((rows.get((k,'current',product),(0,None))[0],k) for k,s in sites.items() if s['position'])
            keys=[k for retry,k in due if retry<=epoch][:6]
            if keys:
                retrieve(keys,'current',product)
            due=sorted((rows.get((k,'current',product),(0,None))[0],i,k) for i,(k,g) in enumerate(grid.items())
                       if product=='weather' or g['ocean'])
            keys=[k for retry,_,k in due if retry<=epoch][:6]
            if keys:
                retrieve(keys,'current',product,10800)
        # Process oldest outstanding requests first; anomaly ties take precedence.
        due=sorted((rows.get(k,(0,None))[0],not candidate,k) for k,candidate in pending.items() if sites[k[0]]['position'])
        for retry,_,(key,hour,product) in due[:6]:
            if retry<=epoch:
                retrieve([key],hour,product)

    def conditions(key,hour):
        return {p:v for p in ('weather','marine') if (v:=rows.get((key,hour,p),(0,None))[1])}
    for key,site in sites.items():
        site['current']=conditions(key,'current')
        site['clips'].sort(key=lambda c:c['recorded_at'],reverse=True)
    for event in events:
        key=position_key(event)
        event['environment']=dict(site=key,position=sites[key]['position'],
                                  hour=recording_hour(event),conditions=conditions(key,recording_hour(event)))
    for key,point in grid.items():
        point['current']=conditions(key,'current')
    return list(sites.values()),list(grid.values())


def inventory(con,events):
    result=[]
    for mode,rate,n,seconds,size,first,last in con.execute("""
        SELECT mode,coalesce(json_extract(payload,'$.sample_rate_hz'),2000),count(*),sum(seconds),sum(bytes),
        min(json_extract(payload,'$.recorded_at')),max(json_extract(payload,'$.recorded_at'))
        FROM windows GROUP BY 1,2 ORDER BY 1,2"""):
        result.append(dict(source='MBARI Pacific Sound',kind=mode,rate=rate,count=n,seconds=seconds,
                           bytes=size,first=first,last=last))
    groups={}
    for e in events:
        if not e.get('station'):
            continue
        encoding=e.get('source_encoding') or ('FLAC archive' if '.flac' in e.get('source_id','').lower() else 'PCM archive')
        key=(e['provider'],encoding,e.get('native_rate'))
        row=groups.setdefault(key,dict(source=key[0],kind=key[1],rate=key[2],count=0,seconds=0,
                                       first=e['recorded_at'],last=e['recorded_at']))
        row['count']+=1
        row['seconds']+=e['duration_seconds']
        measured=e.get('bytes_acquired',e.get('byte_length'))
        if measured is not None:
            row['bytes']=row.get('bytes',0)+measured
            row['metered']=row.get('metered',0)+1
        row['first']=min(row['first'],e['recorded_at'])
        row['last']=max(row['last'],e['recorded_at'])
    matches=Counter()
    for e in events:
        ctx=e['environment']
        matches['located']+=bool(ctx['position'])
        for product,reading in ctx['conditions'].items():
            matches[product]+=bool(reading['values'])
    return dict(rows=result+list(groups.values()),context=dict(matches),events=len(events))
