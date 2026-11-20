"""Build the timeline: speed up VO, place segments, derive word timings. Writes plan.json + vo_full.wav"""
import json, re, subprocess, sys, os

ROOT = sys.argv[1]
TARGET = 50.0
TEMPO = 1.05
FPS = 30
script = json.load(open(f"{ROOT}/script.json"))

def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]))

def ts(s):
    h, m, rest = s.split(":"); sec, ms = rest.replace(".", ",").split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000

def vtt(p):
    cues = []
    txt = open(p, encoding="utf-8").read().strip().split("\n\n")
    for block in txt:
        lines = [l for l in block.splitlines() if l.strip()]
        for i, l in enumerate(lines):
            if "-->" in l:
                a, b = [x.strip() for x in l.split("-->")]
                cues.append((ts(a), ts(b), " ".join(lines[i + 1:])))
    return cues

os.makedirs(f"{ROOT}/vo_fast", exist_ok=True)
segs = []
for key, text in script:
    src = f"{ROOT}/vo/{key}.mp3"; dst = f"{ROOT}/vo_fast/{key}.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-af", f"atempo={TEMPO}", "-ar", "48000", "-ac", "1", dst], check=True)
    segs.append(dict(key=key, text=text, dur=dur(dst), cues=vtt(f"{ROOT}/vo/{key}.vtt")))

lead = 0.15; tail = 0.9
speech = sum(s["dur"] for s in segs)
gap = (TARGET - lead - tail - speech) / (len(segs) - 1)
gap = max(gap, 0.08)
t = lead
for s in segs:
    s["start"] = t
    s["end"] = t + s["dur"]
    words = []
    for a, b, text in s["cues"]:
        a /= TEMPO; b /= TEMPO
        toks = text.split()
        weights = [len(re.sub(r"[^\wáéíóúñ%]", "", w, flags=re.I)) + 2 for w in toks]
        tot = sum(weights); acc = 0
        for w, wt in zip(toks, weights):
            wa = a + (b - a) * acc / tot; acc += wt; wb = a + (b - a) * acc / tot
            words.append(dict(w=w, a=t + wa, b=t + wb))
    s["words"] = words
    del s["cues"]
    t = s["end"] + gap
# scene boundaries: each scene spans from its start (minus half gap) to next start
for i, s in enumerate(segs):
    s["scene_a"] = 0.0 if i == 0 else (segs[i - 1]["end"] + s["start"]) / 2
    s["scene_b"] = TARGET if i == len(segs) - 1 else (s["end"] + segs[i + 1]["start"]) / 2

# mix full VO track
inputs = []; filt = []
for i, s in enumerate(segs):
    inputs += ["-i", f"{ROOT}/vo_fast/{s['key']}.wav"]
    ms = int(s["start"] * 1000)
    filt.append(f"[{i}]adelay={ms}|{ms}[d{i}]")
filt.append("".join(f"[d{i}]" for i in range(len(segs))) + f"amix=inputs={len(segs)}:normalize=0,apad,atrim=0:{TARGET}[out]")
subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]", "-ar", "48000", "-ac", "1", f"{ROOT}/vo_full.wav"], check=True)
json.dump(dict(fps=FPS, duration=TARGET, gap=gap, segs=segs), open(f"{ROOT}/plan.json", "w"), indent=1, ensure_ascii=False)
print("gap", round(gap, 3), "speech", round(speech, 2))
for s in segs:
    print(s["key"], round(s["scene_a"], 2), round(s["scene_b"], 2))
