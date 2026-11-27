"""DSP baseline v1. Report signal levels relative to digital full scale."""
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw
from scipy.signal import stft

RATE = 2000
VERSION = 'spectral-excess-v1'
WINDOW = 60
CLIP = 6


def decode(raw, width):
    if width == 3:
        triplets = np.frombuffer(raw, 'u1').reshape(-1, 3).astype('i4')
        value = triplets[:, 0] | triplets[:, 1] << 8 | triplets[:, 2] << 16
        value = (value ^ 8388608) - 8388608
    else:
        value = np.frombuffer(raw, '<i' + str(width))
    return value.astype('f4') / (2 ** (width * 8 - 1))


def spectrum(x):
    return np.abs(stft(x, RATE, nperseg=256, noverlap=192, boundary=None, padded=False)[2])


def detect(x):
    power = spectrum(x)
    db = 20 * np.log10(np.maximum(power, 1e-9))
    excess = db - np.median(db, axis=1, keepdims=True)
    # Require sustained excess across roughly 0.35 s to suppress single-frame impulses.
    score = np.apply_along_axis(lambda row: np.convolve(row, np.ones(11)/11, mode='valid'), 1, excess[3:-1])
    band, frame = np.unravel_index(np.argmax(score), score.shape)
    peak = float(score[band, frame])
    center = ((frame + 5)*64 + 128)/RATE
    start = int(np.clip(center - CLIP/2, 0, len(x)/RATE - CLIP)*RATE)
    result = (start, float((band+3)*RATE/256), peak) if peak >= 12 and np.max(power[band+3]) > 1e-7 else None
    return power, result


def spectrogram(power, dest):
    db = 20*np.log10(np.maximum(power, 1e-9))
    low, high = np.percentile(db, [3, 99.5])
    v = np.clip((db-low)/max(1,high-low), 0, 1)
    colors = np.array([[5,16,35],[16,47,84],[15,110,135],[79,207,185],[255,218,124]])
    rgb = np.stack([np.interp(v, np.linspace(0,1,5), channel) for channel in colors.T], axis=-1)
    Image.fromarray(rgb[::-1].astype('uint8')).resize((800,240)).save(dest, format='PNG')


def evidence(raw, width, x, folder):
    with wave.open(str(folder/'original.wav'), 'wb') as w:
        w.setparams((1,width,RATE,0,'NONE',''))
        w.writeframes(raw)
    subprocess.run(['ffmpeg','-nostdin','-loglevel','error','-threads','1','-filter_threads','1','-y','-i',str(folder/'original.wav'),
                    '-ar','48000','-c:a','libopus','-b:a','48k','-threads','1',str(folder/'listen.ogg')],check=True)
    spectrogram(spectrum(x), folder/'spectrum.png')
    img = Image.new('RGB',(600,96),'#091e34')
    pen = ImageDraw.Draw(img)
    scale = 44 / max(1e-10,np.max(np.abs(x)))
    for i, section in enumerate(np.array_split(x,600)):
        pen.line((i,48-scale*section.max(),i,48-scale*section.min()),fill='#67ded2')
    img.save(folder/'wave.png')
