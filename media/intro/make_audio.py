"""Synthesised sound design for the 10 s intro (no samples, no licences). Usage: python make_audio.py hit.json out.wav

Declarative table (shotcraft rule S2): every sound is pinned to a picture event. Vocabulary is whoosh / impact / riser /
tick / ping (no game-style bloops). Levels leave headroom; a quiet drone gives the piece a floor and fades at both ends.
"""
import json, sys, wave
import numpy as np

SR = 48000
N = SR * 10
rng = np.random.default_rng(7)
mix = np.zeros(N)

def add(sig, t0, gain=1.0):
    i = int(t0 * SR); j = min(N, i + len(sig))
    if i < N: mix[i:j] += gain * sig[: j - i]

def env(n, a, d):                       # attack, exponential decay (seconds)
    t = np.arange(n) / SR
    return np.minimum(t / max(a, 1e-4), 1) * np.exp(-t / d)

def lowpass(x, fc):
    a = np.exp(-2 * np.pi * fc / SR); y = np.zeros_like(x); s = 0.0
    for k, v in enumerate(x): s = (1 - a) * v + a * s; y[k] = s
    return y

def bandnoise(dur, f0, f1):             # swept band of noise: rising (f0<f1) or falling
    n = int(dur * SR); x = rng.standard_normal(n)
    out = np.zeros(n); fc = np.geomspace(f0, f1, n)
    s1 = s2 = 0.0
    for k in range(n):
        a = np.exp(-2 * np.pi * fc[k] / SR); s1 = (1 - a) * x[k] + a * s1; s2 = (1 - a) * s1 + a * s2; out[k] = s2
    out -= lowpass(out, 40)             # remove rumble offset
    return out / (np.max(np.abs(out)) + 1e-9)

def whoosh(dur, rising=True):
    n = int(dur * SR); x = bandnoise(dur, 400, 5000) if rising else bandnoise(dur, 5000, 400)
    t = np.linspace(0, 1, n); return x * np.sin(np.pi * t) ** 1.6
def riser(dur):
    n = int(dur * SR); x = bandnoise(dur, 200, 6000); return x * np.linspace(0, 1, n) ** 2.2
def impact(dur=0.9, f=58):
    n = int(dur * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * (f + 40 * np.exp(-t * 18)) * t) * env(n, .002, .22) + 0.25 * lowpass(rng.standard_normal(n), 400) * env(n, .001, .05)
def tick(f=3200):
    n = int(.035 * SR); x = rng.standard_normal(n); x -= lowpass(x, f * .5); return x * env(n, .0005, .006)
def ping(f, dur=.5):
    n = int(dur * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t) + .35 * np.sin(2 * np.pi * 2 * f * t)) * env(n, .003, .11)
def click():
    n = int(.04 * SR); x = rng.standard_normal(n); x -= lowpass(x, 1500); return x * env(n, .0003, .008)

hit = json.load(open(sys.argv[1]))
# drone floor: two low sines, faded in over 1.2 s and out over 1.0 s
t = np.arange(N) / SR
drone = (np.sin(2*np.pi*55*t) + .6*np.sin(2*np.pi*82.4*t + .3) + .15*np.sin(2*np.pi*110*t)) * np.clip(t/1.2, 0, 1) * np.clip((10 - t)/1.0, 0, 1)
mix += 0.045 * drone

# --- picture-pinned events ---------------------------------------------------------------------------
add(riser(1.05), 0.05, 0.28)                       # orbit ellipse draws and speeds toward the O
add(impact(), 1.08, 0.55)                          # ring locks into the O of ORBIT
for i in range(4): add(tick(), 1.0 + i * 0.11, 0.22)      # R B I T unfold
add(whoosh(.55), 1.2, 0.20)                        # satellite O deploys its panels
for i in range(8): add(tick(2600), 1.5 + i * 0.07, 0.18)  # B S E R V E R S unfold
add(whoosh(.62, rising=False), 3.05, 0.30)         # lockup shrinks to the corner
add(whoosh(.45), 3.55, 0.12)                       # orbit arc and servicer enter
for k, tt in enumerate(hit): add(ping([587, 659, 740, 880, 988][k], .5), tt, 0.20)   # servicer passes each station; card opens
add(whoosh(.9), 7.5, 0.30)                         # lockup returns, servicer departs for the satellite
add(click(), 8.62, 0.55); add(impact(1.2, 52), 8.68, 0.70)  # dock: latch click then low impact
for f in (293.7, 440, 587.3): add(ping(f, 1.4), 8.75, 0.07)     # one quiet open fifth to close
# ---------------------------------------------------------------------------------------------------
mix = np.tanh(mix * 1.15) * 0.88
pcm = (mix * 32767).astype(np.int16)
with wave.open(sys.argv[2], "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print("peak", float(np.max(np.abs(mix))), "rms", float(np.sqrt(np.mean(mix**2))))
