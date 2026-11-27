"""Six-second range samples from public daily polar TAR archives, with native-clock provenance."""
import hashlib
import io
import re
import struct
import tarfile
from datetime import datetime,timezone
from math import gcd
from urllib.request import Request,urlopen

import numpy as np
from scipy.signal import resample_poly
from processing.dsp import decode
from ingestion.mbari import layout

DEPLOYMENTS = {
    '962533':'PALAOA, Ekström Ice Shelf',
    '981192':'Weddell Sea, AWI229-13',
    '986812':'Weddell Sea, AWI231-13',
    '973171':'Weddell Sea, AWI229-10',
    '982321':'Weddell Sea, AWI251-3',
}


def sources():
    return [dict(id='pangaea/'+n,provider='AWI / PANGAEA',location=name) for n,name in DEPLOYMENTS.items()]


def ranged(url,start,length,etag=None):
    headers={'Range':f'bytes={start}-{start+length-1}'}
    if etag:
        headers['If-Match']=etag
    with urlopen(Request(url,headers=headers),timeout=12) as r:
        cr = r.headers.get('Content-Range','')
        if r.status!=206 or not re.fullmatch(fr'bytes {start}-{start+length-1}/\d+',cr):
            raise ValueError('Polar archive did not honor the range')
        data=r.read(length+1)
        if len(data)!=length:
            raise ValueError('Incomplete polar range')
        return data,r.headers.get('ETag')


def sample(station,sequence,workdir):
    n=station['id'].split('/')[1]
    doi='https://doi.pangaea.de/10.1594/PANGAEA.'+n
    with urlopen(doi+'?format=html',timeout=12) as r:
        manifest=r.read(1_100_000).decode()
    license_url='https://creativecommons.org/licenses/by/4.0/'
    if license_url not in manifest:
        raise ValueError('License needs review')
    links=sorted(set(re.findall(fr'href="(https://download\.pangaea\.de/dataset/{n}/files/[^"<>]+\.tar)"',manifest)))
    if not links:
        raise ValueError('Daily archives unavailable')
    url=links[sequence%len(links)]
    header,etag=ranged(url,0,16384)
    with tarfile.open(fileobj=io.BytesIO(header),mode='r:') as t:
        m=t.next()
        if m is None or not m.isfile() or not m.name.lower().endswith('.wav'):
            raise ValueError('First member is not PCM audio')
    wav=header[m.offset_data:]
    if wav[12:16]!=b'fmt ':
        raise ValueError('Unsupported WAV layout')
    rate=struct.unpack_from('<I',wav,24)[0]
    if not 2000<=rate<=384000:
        raise ValueError('Unsupported native rate')
    offset,width,frames=layout(wav,m.size,rate)
    match=re.search(r'(20\d{6})[-_T](\d{6})',m.name)
    if not match or frames<rate*6:
        raise ValueError('Missing timestamp or incomplete clip')
    stamp=datetime.strptime(''.join(match.groups()),'%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
    left=m.offset_data+offset
    raw,_=ranged(url,left,6*rate*width,etag)
    common=gcd(16000,rate)
    x=resample_poly(decode(raw,width),16000//common,rate//common)
    info=dict(recorded_at=stamp.isoformat(),source_url=url,source_id=m.name,
              native_rate=rate,attribution='Alfred Wegener Institute and dataset authors, PANGAEA '+n,
              license_url=license_url,metadata_url=doi,public_audio=True,byte_start=left,byte_length=len(raw),
              native_pcm_sha256=hashlib.sha256(raw).hexdigest(),etag=etag)
    return info,np.clip(np.rint(x*32768),-32768,32767).astype('<i2')
