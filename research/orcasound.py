"""Bounded HLS samples from publicly listed Orcasound hydrophones with program timestamps."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
import re
import subprocess
from urllib.request import urlopen

import numpy as np

STATIONS={'rpi_port_townsend':'Port Townsend','rpi_sunset_bay':'Sunset Bay',
          'rpi_andrews_bay':'Andrews Bay','rpi_orcasound_lab':'Orcasound Lab',
          'rpi_bush_point':'Bush Point','rpi_north_sjc':'North San Juan Channel'}
BASE='https://audio-orcasound-net.s3.us-west-2.amazonaws.com/'


def sources():
    return [dict(id='orcasound/'+k,location=v,provider='Orcasound') for k,v in STATIONS.items()]


def bounded(url,limit):
    with urlopen(url,timeout=12) as response:
        data=response.read(limit+1)
    if len(data)>limit:
        raise ValueError('Orcasound object exceeds sampling budget')
    return data


def sample(station,sequence,workdir):
    node=station['id'].split('/')[1]
    prefix=BASE+node+'/'
    epoch=bounded(prefix+'latest.txt',32).decode().strip()
    if not re.fullmatch(r'\d{10}',epoch):
        raise ValueError('Invalid playlist epoch')
    playlist=prefix+'hls/'+epoch+'/'
    text=bounded(playlist+'live.m3u8',2_000_000).decode()
    pairs=re.findall(r'#EXT-X-PROGRAM-DATE-TIME:([^\s]+)\s+(live\d+\.ts)',text)
    quality='HLS program timestamp supplied by recorder'
    if pairs:
        when,segment=pairs[-1-(sequence%min(32,len(pairs)))]
        stamp=datetime.fromisoformat(when)
    else:
        # Older encoders anchor the entire playlist by its UTC session epoch.
        entries=re.findall(r'#EXTINF:([0-9.]+),[^\n]*\n(live\d+\.ts)',text)
        if not entries or '#EXT-X-MEDIA-SEQUENCE:0\n' not in text or '#EXT-X-DISCONTINUITY' in text:
            raise ValueError('Unanchored Orcasound playlist')
        index=len(entries)-1-sequence%min(32,len(entries))
        if any(int(name[4:-3])!=i for i,(_,name) in enumerate(entries[:index+1])):
            raise ValueError('Missing Orcasound segments')
        stamp=datetime.fromtimestamp(int(epoch),timezone.utc)+timedelta(seconds=sum(float(x[0]) for x in entries[:index]))
        segment=entries[index][1]
        quality='Approximate UTC from stream session epoch plus segment durations'
    if stamp.tzinfo is None:
        raise ValueError('Ambiguous segment timezone')
    url=playlist+segment
    raw=bounded(url,2_000_000)
    probe=subprocess.run(['ffprobe','-v','error','-f','mpegts','-select_streams','a:0','-show_entries',
                          'stream=sample_rate','-of','json','pipe:0'],input=raw,capture_output=True,timeout=8,check=True)
    rate=int(json.loads(probe.stdout)['streams'][0]['sample_rate'])
    pcm=subprocess.run(['ffmpeg','-v','error','-f','mpegts','-i','pipe:0','-map','0:a:0','-t','6.1',
                        '-ac','1','-ar','16000','-f','s16le','pipe:1'],input=raw,capture_output=True,timeout=8,check=True)
    samples=np.frombuffer(pcm.stdout,'<i2')[:96000]
    if samples.size!=96000:
        raise ValueError('Short HLS segment')
    return dict(recorded_at=stamp.astimezone(timezone.utc).isoformat(),source_url=url,source_id=node+'/'+epoch+'/'+segment,
                native_rate=rate,attribution='Orcasound • '+STATIONS[node],public_audio=True,
                license_url='https://creativecommons.org/licenses/by-nc-sa/4.0/',source_encoding='HLS AAC',quality=quality,
                source_sha256=hashlib.sha256(raw).hexdigest()),samples
