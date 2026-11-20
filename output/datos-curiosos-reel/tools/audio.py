"""Synthesize an original dark cinematic trap bed + SFX, duck under VO, write mix.wav"""
import json, sys, wave
import numpy as np

ROOT = sys.argv[1]
SR = 48000
plan = json.load(open(f"{ROOT}/plan.json"))
DUR = plan["duration"]; SEGS = plan["segs"]
N = int(DUR * SR)
rng = np.random.default_rng(3)
BPM = 128
beat = 60 / BPM

def env_exp(n, tau): return np.exp(-np.arange(n) / (tau * SR))
def add(buf, sig, t, g=1.0):
    i = int(t * SR)
    if i >= len(buf): return
    sig = sig[: len(buf) - i]; buf[i:i + len(sig)] += sig * g

def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.zeros_like(x); acc = 0.0
    # vectorized one-pole via lfilter-like cumulative approach
    from scipy.signal import lfilter
    return lfilter([1 - a], [1, -a], x)

def highpass(x, cutoff): return x - lowpass(x, cutoff)

def kick():
    n = int(0.45 * SR); tt = np.arange(n) / SR
    f = 45 + 110 * np.exp(-tt * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * env_exp(n, 0.16) * 0.9 + rng.normal(0, 1, n) * env_exp(n, 0.004) * 0.15

def hat(open_=False):
    n = int((0.18 if open_ else 0.05) * SR)
    return highpass(rng.normal(0, 1, n), 7000) * env_exp(n, 0.05 if open_ else 0.012) * 0.25

def clap():
    n = int(0.3 * SR); x = highpass(rng.normal(0, 1, n), 1200)
    e = env_exp(n, 0.06)
    for d in (0.0, 0.011, 0.022): e += np.roll(env_exp(n, 0.006), int(d * SR)) * 0.6
    return x * e * 0.35

def boom():
    n = int(1.6 * SR); tt = np.arange(n) / SR
    f = 30 + 70 * np.exp(-tt * 6)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 0.5)
    s += lowpass(rng.normal(0, 1, n), 900) * env_exp(n, 0.12) * 0.8
    return np.tanh(s * 1.6) * 0.8

def whoosh(length=0.45, rev=False):
    n = int(length * SR); x = rng.normal(0, 1, n)
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    if rev: env = np.linspace(0, 1, n) ** 3
    # sweeping band: crossfade lowpassed & highpassed
    lo = lowpass(x, 600); hi = highpass(x, 3000)
    k = np.linspace(0, 1, n)
    return (lo * (1 - k) + hi * k) * env * 0.5

def tick():
    n = int(0.06 * SR); tt = np.arange(n) / SR
    return np.sin(2 * np.pi * 2400 * tt) * env_exp(n, 0.01) * 0.25

def pad_note(freq, dur):
    n = int(dur * SR); tt = np.arange(n) / SR
    s = np.zeros(n)
    for det in (-0.12, 0, 0.11):
        f = freq * 2 ** (det / 12)
        s += 2 * ((tt * f) % 1) - 1  # saw
    s = lowpass(s / 3, 900)
    a = np.minimum(1, tt / 0.4) * np.minimum(1, (dur - tt) / 0.5)
    return s * a

music = np.zeros(N); sfx = np.zeros(N)
# chord progression in A minor: Am - F - C - G (as low pads), 2 bars each
chords = [[110, 130.81, 164.81], [87.31, 110, 130.81], [65.41*2, 164.81, 196], [98, 123.47, 146.83]]
bar = beat * 4
t = 0; ci = 0
while t < DUR:
    for f in chords[ci % 4]:
        add(music, pad_note(f, bar * 2 + 0.5), t, 0.10)
    add(music, pad_note(chords[ci % 4][0] / 2, bar * 2 + 0.5), t, 0.16)  # sub-bass pad
    t += bar * 2; ci += 1

# drums: start full groove after hook slam (t≈0.15), drop-out for outro tail
start = SEGS[1]["scene_a"] - bar  # groove enters one bar before fact 1
i = 0; t = 0.0
while t < DUR - 1.0:
    b = i % 16  # 16th notes per bar? -> use 8th grid
    step = i % 8
    if t >= 0.0:
        if step in (0,) or (step == 5 and t > start): add(music, kick(), t, 1.0 if t > start else 0.7)
        if t > start:
            if step in (2, 6): add(music, clap(), t, 0.9)
            add(music, hat(open_=(step == 7)), t, 0.6)
            if step % 2 == 1: add(music, hat(), t + beat / 4, 0.35)
    t += beat / 2; i += 1

# sfx at transitions and slams
edges = [s["scene_a"] for s in SEGS[1:]]
add(sfx, boom(), 0.12, 0.9)                         # PARA slam
for k in range(8): add(sfx, tick(), k * 0.3, 0.7)   # montage ticks
add(sfx, whoosh(0.9, rev=True), 2.4 - 0.9, 0.5)
add(sfx, boom(), 2.4, 0.45)
for e in edges:
    add(sfx, whoosh(0.42), e - 0.22, 0.7)
    add(sfx, boom(), e + 0.02, 0.5)
add(sfx, boom(), SEGS[-1]["scene_a"] + 1.75, 0.8)  # SIGUEME slam
add(sfx, tick(), SEGS[-1]["scene_a"] + 4.1, 1.2)    # button tap

# VO + ducking
def read_wav(p):
    with wave.open(p) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32768
    return a
vo = read_wav(f"{ROOT}/vo_full.wav")[:N]
vo = np.pad(vo, (0, N - len(vo)))
env = np.abs(vo)
from scipy.ndimage import maximum_filter1d
env = maximum_filter1d(env, int(0.08 * SR))
env = lowpass(env, 6)
duck = 1 - 0.55 * np.clip(env / 0.08, 0, 1)
music *= duck
# fade music at end
fade = np.ones(N); fl = int(1.2 * SR); fade[-fl:] = np.linspace(1, 0, fl)
music *= fade
mix = vo * 1.0 + music * 0.33 + sfx * 0.45
mix = np.tanh(mix * 1.1) * 0.95
out = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
with wave.open(f"{ROOT}/mix_raw.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
print("ok")
