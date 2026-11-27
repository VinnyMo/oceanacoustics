"""Check the public HTTPS observatory, fresh state and byte-range media delivery."""
import json
import sys
import urllib.request
from datetime import datetime, timezone

BASE = 'https://oceanacoustics.vincentmossman.com'


def read(path, **headers):
    return urllib.request.urlopen(urllib.request.Request(BASE+path, headers=headers), timeout=20)


def main():
    with read('/') as page:
        assert b'Ocean Acoustics' in page.read(65536), 'Unexpected site'
    with read('/data/observatory.json') as response:
        data = json.load(response)
    age = (datetime.now(timezone.utc)-datetime.fromisoformat(data['generated_at'])).total_seconds()
    if age < -30 or age > 900 or 'paused' in data['status'].lower():
        sys.exit('Worker snapshot stale or paused')
    for event in data['events'][:1]:
        with read(event['audio_url'],Range='bytes=0-31') as r:
            if r.status != 206 or r.read(32)[:4] != b'OggS':
                sys.exit('Public audio range probe failed')
    print(json.dumps(dict(snapshot_age_s=round(age),status=data['status'],events=data['stats']['events'],
                          audio_probe=bool(data['events']),hours=data['stats']['hours_analyzed'])))


if __name__ == '__main__':
    main()
