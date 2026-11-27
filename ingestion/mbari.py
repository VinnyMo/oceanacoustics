"""Anonymous, validator-bound S3 range reads. All offsets are bytes in the original WAV."""
import os
import re
import struct
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone

BASE = 'https://pacific-sound-2khz.s3.us-west-2.amazonaws.com/'
NS = {'s': 'http://s3.amazonaws.com/doc/2006-03-01/'}
KEY = re.compile(r'\d{4}/\d{2}/MARS-(\d{8}T\d{6}Z)-(?:2|16)kHz\.wav')


def listing(prefix, delimiter=None, base=BASE):
    params = {'list-type': '2', 'prefix': prefix}
    if delimiter:
        params['delimiter'] = delimiter
    while True:
        with urllib.request.urlopen(base + '?' + urllib.parse.urlencode(params), timeout=30) as r:
            root = ET.fromstring(r.read(2_000_000))
        yield root
        token = root.findtext('s:NextContinuationToken', namespaces=NS)
        if not token:
            return
        params['continuation-token'] = token


def prefixes(prefix, base=BASE):
    return sorted(e.text for root in listing(prefix, '/', base) for e in root.findall('s:CommonPrefixes/s:Prefix', NS))


@dataclass(frozen=True)
class Recording:
    key: str
    size: int
    etag: str
    modified: str

    @property
    def start(self):
        return datetime.strptime(KEY.fullmatch(self.key)[1], '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)


def records(prefix, base=BASE):
    for root in listing(prefix, base=base):
        for element in root.findall('s:Contents', NS):
            key = element.findtext('s:Key', namespaces=NS)
            if KEY.fullmatch(key):
                yield Recording(key, int(element.findtext('s:Size', namespaces=NS)),
                                element.findtext('s:ETag', namespaces=NS), element.findtext('s:LastModified', namespaces=NS))


def fetch(rec, start, end, dest, base=BASE):
    part = dest.with_suffix('.part')
    size = end - start + 1
    if dest.exists() and dest.stat().st_size == size:
        return
    offset = part.stat().st_size if part.exists() else 0
    if offset > size:
        part.unlink()
        offset = 0
    if offset < size:
        left = start + offset
        req = urllib.request.Request(base + rec.key, headers={'Range': f'bytes={left}-{end}', 'If-Match': rec.etag})
        with urllib.request.urlopen(req, timeout=45) as r:
            if r.status != 206 or r.headers['Content-Range'] != f'bytes {left}-{end}/{rec.size}' or r.headers['ETag'] != rec.etag:
                raise ValueError('Archive range or version mismatch')
            with part.open('ab') as out:
                remaining = size - offset
                while remaining:
                    data = r.read(min(65536, remaining))
                    if not data:
                        raise IOError('Incomplete archive range')
                    out.write(data)
                    remaining -= len(data)
    os.replace(part, dest)


def layout(header, size, expected_rate=2000):
    if header[:4] != b'RIFF' or header[8:12] != b'WAVE':
        raise ValueError('Expected RIFF WAVE')
    pos, width = 12, None
    while pos + 8 <= len(header):
        kind, length = struct.unpack_from('<4sI', header, pos)
        pos += 8
        if kind == b'fmt ':
            codec, channels, rate, _, width, bits = struct.unpack_from('<HHIIHH', header, pos)
            if (codec, channels, rate) != (1, 1, expected_rate) or (width, bits) not in ((2, 16), (3, 24), (4, 32)):
                raise ValueError('Unsupported encoding')
        if kind == b'data' and width and pos + length <= size and length % width == 0:
            return pos, width, length // width
        pos += length + length % 2
    raise ValueError('Unsupported or truncated WAV header')


class PacificSound:
    location = 'Monterey Accelerated Research System, offshore California'
    first_month = '2015/07/'

    def __init__(self, rate=16000):
        if rate not in (2000,16000):
            raise ValueError('Supported archive rates are 2000 and 16000 Hz')
        self.rate = rate
        self.base = f'https://pacific-sound-{rate//1000}khz.s3.us-west-2.amazonaws.com/'

    def latest_month(self):
        return prefixes(prefixes('', self.base)[-1], self.base)[-1]

    def records(self, month):
        return records(month, self.base)

    def source_url(self, recording):
        return self.base + recording.key

    def fetch(self, recording, first, last, target):
        fetch(recording,first,last,target,base=self.base)

    def layout(self, header, size):
        return layout(header,size,self.rate)
