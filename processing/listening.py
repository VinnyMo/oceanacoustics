"""Listening derivatives only. The original PCM and detector inputs stay at source level."""
import os
import subprocess
import wave

import numpy as np
from scipy.signal import butter, hilbert, sosfiltfilt
from processing.dsp import decode


def encode(samples, rate, target):
    rms = float(np.sqrt(np.mean(samples**2)))
    peak = float(np.max(np.abs(samples)))
    gain = min(10**(72/20), 0.70/max(peak,1e-12), 0.09/max(rms,1e-12))
    temp = target.with_suffix('.part')
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','f32le','-ar',str(rate),
                    '-ac','1','-i','pipe:0','-ar','48000','-c:a','libopus','-application','audio',
                    '-threads','1','-b:a','64k','-f','ogg',str(temp)],
                   input=(samples*gain).astype('<f4').tobytes(),check=True,timeout=15)
    os.replace(temp,target)
    return round(20*np.log10(gain),1)


def add_listening(event, folder):
    with wave.open(str(folder/'original.wav'),'rb') as w:
        rate = w.getframerate()
        x = decode(w.readframes(w.getnframes()),w.getsampwidth()).astype(float)
    audible = sosfiltfilt(butter(3,12,fs=rate,btype='highpass',output='sos'),x)
    if np.max(np.abs(audible)) < 1e-10:
        event['listening_version'] = 1
        return
    base = event['audio_url'].rsplit('/',1)[0]
    event['boost_gain_db'] = encode(audible,rate,folder/'boost.ogg')
    event['boosted_url'] = base+'/boost.ogg'
    if event.get('frequency_hz',0) < 250:
        low = sosfiltfilt(butter(4,250,fs=rate,btype='lowpass',output='sos'),audible)
        phase = np.arange(len(x))*(2*np.pi*220/rate)
        shifted = np.real(hilbert(low)*np.exp(1j*phase))
        encode(shifted,rate,folder/'lowband.ogg')
        event['lowband_url'] = base+'/lowband.ogg'
    event['listening_version'] = 1


def upgrade(con, root):
    rows = con.execute("""SELECT rowid,event FROM windows WHERE event IS NOT NULL
        AND json_extract(event,'$.listening_version') IS NULL ORDER BY rowid DESC LIMIT 8""").fetchall()
    import json
    from worker import json_write
    for rowid,data in rows:
        event = json.loads(data)
        folder = root/'public/data/events'/event['id']
        add_listening(event,folder)
        with con:
            con.execute('UPDATE windows SET event=? WHERE rowid=?',(json.dumps(event),rowid))
            con.execute("DELETE FROM settings WHERE name='catalog'")
        json_write(folder.with_suffix('.json'),event)
