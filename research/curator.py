"""Public listening catalog. Measurements and interpretations have distinct provenance."""
import json

GENRES = ('Human', 'Dolphins', 'Whales', 'Other marine life', 'Machinery', 'Weather',
          'Ice & water', 'Recording artifact', 'Unidentified')
MOODS = ('Spooky', 'Rhythmic', 'Tonal', 'Percussive', 'Ambient')

# Editorial indexing of the published v1 hypotheses. Apply only when the wording matches.
LEGACY = {
    'These could be mechanical noises from nearby instrumentation or equipment in the research array.':
        ('High squeals over a quiet background', 'Machinery'),
    'The hum might originate from distant ice movement or natural oceanic background noise in the low-frequency band.':
        ('A steady low hum', 'Ice & water'),
}


def catalog_note(event, note):
    hz = event.get('frequency_hz')
    candidate = event.get('score_db') is not None
    kind = 'Anomaly candidate' if candidate else 'Archive sample'
    if note:
        legacy_title, legacy_genre = LEGACY.get(note['hypothesis'], (None,'Unidentified'))
        title = note.get('title') or legacy_title or note['observation']
        return dict(title=title, genre=note.get('genre',legacy_genre), mood=note.get('mood'),
                    basis='Listening note', kind=kind, explanation=note['observation'], note=note)
    if event.get('zero_fraction') == 1:
        return dict(title='Silent excerpt', genre='Unidentified', mood=None, basis='Measured description',
                    kind=kind, explanation='Every sample in this excerpt is zero. It contains no measurable acoustic signal.', note=None)
    band = 'Low-frequency' if hz is not None and hz < 250 else 'Mid-frequency' if hz is not None and hz < 2000 else 'High-frequency'
    title = f'{band} {"anomaly" if candidate else "excerpt"}' if hz is not None else kind
    if candidate and hz is not None:
        explanation = f'The detector found its strongest change at {hz:,.1f} Hz, {event["score_db"]:.1f} dB above the local background.'
    elif hz is not None:
        explanation = f'The strongest measured spectral peak in this archive sample is at {hz:,.1f} Hz.'
    else:
        explanation = 'This archive excerpt is available for listening and source review.'
    return dict(title=title, genre='Unidentified', mood=None, basis='Measured description', kind=kind,
                explanation=explanation, note=None)


def listening_picks(candidates):
    """Favor distinct stations among equally ranked reviews; break remaining ties by review date."""
    picks=[]
    locations=set()
    remaining=[c for c in candidates if c['animal'] or (c['character']=='distinct patterned sound'
               and c['genre'] not in ('Machinery','Recording artifact') and c['score']>=4)]
    while remaining and len(picks)<5:
        winner=max(remaining,key=lambda c:(c['animal'],c['score'],c['event']['location'] not in locations,
                                           c['created_at'],c['event']['id']))
        picks.append(winner)
        locations.add(winner['event']['location'])
        remaining.remove(winner)
    return picks


def publish_catalog(con, public, events):
    from worker import json_write
    notes = {r[0]:dict(json.loads(r[1]),model=r[2],created_at=r[3]) for r in con.execute(
        "SELECT id,note,model,requested FROM ai_notes WHERE state='complete'")}
    folder=public/'curation'
    folder.mkdir(exist_ok=True)
    entries=[]
    candidates=[]
    for e in events:
        if not e.get('audio_url') or not e.get('public_audio',True):
            continue
        if e['id'] not in notes:
            continue
        item=catalog_note(e,notes[e['id']])
        note=item['note']
        if 'character' in note and 'listening_interest' in note:
            fields=('id','location','recorded_at','audio_url','boosted_url','boost_gain_db','lowband_url',
                    'spectrogram_url','source_url','attribution','metadata_url','license','license_url')
            candidates.append(dict(title=item['title'],observation=item['explanation'],
                                   score=note['listening_interest'],genre=item['genre'],character=note['character'],
                                   animal=(note['character']=='animal-like call' and item['genre'] in ('Dolphins','Whales','Other marine life') and note['listening_interest']>=3),
                                   basis='Listening interest',
                                   created_at=note['created_at'],event={k:e.get(k) for k in fields}))
        item['environment']=e.get('environment')
        json_write(folder/(e['id']+'.json'),item)
        entries.append(dict(id=e['id'],title=item['title'],genre=item['genre'],mood=item['mood'],kind=item['kind'],
                            reviewed=item['note'] is not None,priority=(item['note'] or {}).get('priority',0),
                            recorded_at=e['recorded_at']))
    entries.sort(key=lambda i:(i['reviewed'],i['priority'],i['recorded_at'],i['id']),reverse=True)
    picks=listening_picks(candidates)
    json_write(public/'picks.json',picks)
    json_write(public/'animal-first-picks.json',picks)
    json_write(public/'showcase.json',entries)
    return len(entries)
