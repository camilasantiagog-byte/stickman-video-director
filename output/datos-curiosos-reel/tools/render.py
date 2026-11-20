"""Render the reel frames (1080x1920) with PIL and pipe them to ffmpeg.
usage: render.py ROOT OUT.mp4 [start_s end_s]"""
import json, math, os, sys, subprocess, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps
from multiprocessing import Pool

ROOT = sys.argv[1]
OUT = sys.argv[2]
W, H = 1080, 1920
plan = json.load(open(f"{ROOT}/plan.json"))
FPS = plan["fps"]; DUR = plan["duration"]; SEGS = plan["segs"]

RED = (166, 28, 36)        # rojo mate
RED_D = (96, 14, 20)
BLACK = (10, 10, 10)
WHITE = (245, 244, 240)
F_ANTON = f"{ROOT}/fonts/Anton.ttf"
F_M900 = f"{ROOT}/fonts/Mont900.ttf"
F_M800 = f"{ROOT}/fonts/Mont800.ttf"
F_M400 = f"{ROOT}/fonts/Mont400.ttf"

# ---------------------------------------------------------------- content
HEADLINES = {
    "hook":     [("7 DATOS", "CURIOSOS"), ("QUE TE VOLARÁN", "LA CABEZA"), ("EL ÚLTIMO", "NADIE LO SABE")],
    "octopus":  [("3", "CORAZONES"), ("SANGRE", "AZUL")],
    "honey":    [("NUNCA", "CADUCA"), ("+3.000", "AÑOS")],
    "venus":    [("1 DÍA", "EN VENUS"), ("1 DÍA >", "1 AÑO")],
    "flamingo": [("NACEN", "GRISES"), ("ROSA POR", "SU COMIDA")],
    "eiffel":   [("TORRE", "EIFFEL"), ("+15 CM", "EN VERANO")],
    "cow":      [("MEJORES", "AMIGAS"), ("ESTRÉS SI", "LAS SEPARAN")],
    "brain":    [("2%", "DE TU PESO"), ("20%", "DE TU ENERGÍA")],
    "outro":    [],
}
# which word in each headline pair is painted red: index of line (0 or 1)
SPLIT_WORD = {"octopus": "y", "honey": "encontraron", "venus": "dura", "flamingo": "se", "eiffel": "crece", "cow": "y", "brain": "pero"}
ACCENT = {"hook": [0, 1, 1], "octopus": [0, 1], "honey": [1, 0], "venus": [0, 1], "flamingo": [1, 1],
          "eiffel": [1, 0], "cow": [1, 0], "brain": [0, 0]}
IMAGES = json.load(open(f"{ROOT}/images.json"))   # key -> [file, file]

# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out_expo(x): x = clamp(x); return 1 if x >= 1 else 1 - 2 ** (-10 * x)
def ease_in_out(x): x = clamp(x); return x * x * (3 - 2 * x)
def ease_out_back(x, s=1.7):
    x = clamp(x) - 1; return 1 + (s + 1) * x ** 3 + s * x ** 2

_font_cache = {}
def font(path, size):
    k = (path, size)
    if k not in _font_cache: _font_cache[k] = ImageFont.truetype(path, size)
    return _font_cache[k]

def grade(im):
    """cinematic grade: slight desat, crushed blacks, warm-red shadows, cool-neutral highs"""
    im = ImageEnhance.Color(im).enhance(0.72)
    im = ImageEnhance.Contrast(im).enhance(1.18)
    a = np.asarray(im).astype(np.float32) / 255
    lum = a.mean(axis=2, keepdims=True)
    shadow = (1 - lum) ** 2
    a = a * 0.86
    a[..., 0:1] += shadow * 0.035
    a[..., 1:3] -= shadow * 0.02
    a = np.clip(a, 0, 1) ** 1.08
    return Image.fromarray((a * 255).astype(np.uint8))

_src_cache = {}
BAND_Y, BAND_H = 360, 1200
def spec_of(spec):
    if isinstance(spec, str): return dict(f=spec)
    return spec
def load_src(spec):
    spec = spec_of(spec); key = json.dumps(spec, sort_keys=True)
    if key in _src_cache: return _src_cache[key]
    im = Image.open(f"{ROOT}/img/{spec['f']}").convert("RGB")
    z = spec.get("z", 1.0); cx, cy = spec.get("c", [0.5, 0.5])
    if z > 1:
        w, h = im.size; vw, vh = w / z, h / z
        x0 = clamp(cx * w - vw / 2, 0, w - vw); y0 = clamp(cy * h - vh / 2, 0, h - vh)
        im = im.crop((int(x0), int(y0), int(x0 + vw), int(y0 + vh)))
    portrait = im.height / im.width >= 1.3
    S = 1.3
    if portrait:
        fg = grade(ImageOps.fit(im, (int(W * S), int(H * S)), Image.LANCZOS, centering=(0.5, 0.45)))
        res = dict(portrait=True, fg=fg, size=(W, H))
    else:
        fg = grade(ImageOps.fit(im, (int(W * S), int(BAND_H * S)), Image.LANCZOS, centering=(0.5, 0.5)))
        blur = ImageOps.fit(im, (270, 480), Image.LANCZOS).filter(ImageFilter.GaussianBlur(10))
        blur = ImageEnhance.Brightness(grade(blur)).enhance(0.42).resize((W, H), Image.BICUBIC)
        res = dict(portrait=False, fg=fg, blur=blur, size=(W, BAND_H))
    _src_cache[key] = res
    return res

_mask = None
def band_mask():
    global _mask
    if _mask is None:
        y = np.arange(BAND_H)[:, None]
        m = np.clip(np.minimum(y / 160, (BAND_H - 1 - y) / 160), 0, 1) ** 1.5
        _mask = Image.fromarray((np.repeat(m, W, axis=1) * 255).astype(np.uint8), "L")
    return _mask

def kenburns(spec, p, zoom_from=1.0, zoom_to=1.16, pan=(0.0, -0.04), punch=0.0):
    r = load_src(spec)
    src = r["fg"]; tw, th = r["size"]
    sw, sh = src.size
    z = zoom_from + (zoom_to - zoom_from) * p + punch
    vw, vh = sw / 1.3 / z, sh / 1.3 / z
    cx = sw / 2 + pan[0] * sw * (p - 0.5)
    cy = sh / 2 + pan[1] * sh * (p - 0.5)
    box = (cx - vw / 2, cy - vh / 2, cx + vw / 2, cy + vh / 2)
    fg = src.resize((tw, th), Image.BILINEAR, box=box)
    if r["portrait"]: return fg
    out = r["blur"].copy()
    out.paste(fg, (0, BAND_Y), band_mask())
    return out

# precomputed overlays
def make_overlays():
    yy = np.linspace(0, 1, H)[:, None]
    xx = np.linspace(-1, 1, W)[None, :]
    top = np.clip(1 - yy / 0.32, 0, 1) ** 1.6 * 0.85
    bot = np.clip((yy - 0.52) / 0.48, 0, 1) ** 1.3 * 0.92
    vig = np.clip((np.sqrt(xx ** 2 * 0.6 + ((yy - 0.5) * 2) ** 2 * 0.5) - 0.55) / 0.7, 0, 1) * 0.55
    alpha = np.clip(top + bot + vig, 0, 0.95)
    shade = np.zeros((H, W, 4), np.uint8)
    shade[..., :3] = 6
    shade[..., 3] = (alpha * 255).astype(np.uint8)
    grains = []
    rng = np.random.default_rng(7)
    for i in range(6):
        n = rng.normal(0, 1, (H // 2, W // 2))
        g = np.zeros((H // 2, W // 2, 4), np.uint8)
        g[..., :3] = np.clip(128 + n * 60, 0, 255)[..., None].astype(np.uint8)
        g[..., 3] = 16
        grains.append(Image.fromarray(g, "RGBA").resize((W, H), Image.NEAREST))
    return Image.fromarray(shade, "RGBA"), grains

SHADE, GRAINS = make_overlays()

def text_layer(text, path, size, fill, stroke=0, stroke_fill=BLACK, tracking=0, shadow=True):
    f = font(path, size)
    chars = list(text)
    widths = [f.getlength(c) for c in chars]
    tw = int(sum(widths) + tracking * (len(chars) - 1)) + stroke * 2 + 80
    asc, desc = f.getmetrics()
    th = asc + desc + stroke * 2 + 80
    im = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = 40 + stroke
    if shadow:
        sh = Image.new("RGBA", (tw, th), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
        xx = x
        for c, w in zip(chars, widths):
            sd.text((xx, 40 + stroke + 8), c, font=f, fill=(0, 0, 0, 230), stroke_width=max(2, size // 40), stroke_fill=(0, 0, 0, 230)); xx += w + tracking
        sh = sh.filter(ImageFilter.GaussianBlur(max(8, size // 14))); im.alpha_composite(sh); im.alpha_composite(sh)
    for c, w in zip(chars, widths):
        d.text((x, 40 + stroke), c, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        x += w + tracking
    return im.crop(im.getbbox()) if im.getbbox() else im

_layer_cache = {}
def cached_text(*args, **kw):
    k = (args, tuple(sorted(kw.items())))
    if k not in _layer_cache: _layer_cache[k] = text_layer(*args, **kw)
    return _layer_cache[k]

def paste_scaled(canvas, layer, cx, cy, scale=1.0, alpha=1.0, anchor="c"):
    if alpha <= 0.01 or scale <= 0.01: return
    if abs(scale - 1) > 0.002:
        layer = layer.resize((max(1, int(layer.width * scale)), max(1, int(layer.height * scale))), Image.BICUBIC)
    if alpha < 0.999:
        a = layer.getchannel("A").point(lambda v: int(v * alpha)); layer = layer.copy(); layer.putalpha(a)
    x = int(cx - layer.width / 2) if anchor == "c" else int(cx)
    y = int(cy - layer.height / 2)
    canvas.alpha_composite(layer, (max(x, -layer.width), y) if x > -layer.width else (0, y))

def fit_size(text, path, max_w, start):
    s = start
    while s > 40 and font(path, s).getlength(text) > max_w: s -= 4
    return s

# ---------------------------------------------------------------- scene pieces
def draw_headline(canvas, key, half, lt, cy=900):
    """two-line kinetic headline. lt = local time since this half started"""
    l1, l2 = HEADLINES[key][half]
    acc = ACCENT.get(key, [0, 0])[half]
    lines = [(l1, 0), (l2, 1)]
    y = cy
    sizes = [fit_size(l1, F_ANTON, 940, 250), fit_size(l2, F_ANTON, 940, 190 if len(l2) > 6 else 250)]
    heights = []
    for (txt, i), sz in zip(lines, sizes):
        col = RED if i == acc else WHITE
        heights.append(cached_text(txt, F_ANTON, sz, col, stroke=0).height)
    total = sum(heights) + 10
    y = cy - total / 2
    for (txt, i), sz, hgt in zip(lines, sizes, heights):
        col = RED if i == acc else WHITE
        layer = cached_text(txt, F_ANTON, sz, col, stroke=0)
        d = i * 0.09
        p = ease_out_expo((lt - d) / 0.42)
        scale = 1.0 + (1 - p) * 0.55 + 0.03 * (lt)  # slam + slow creep
        alpha = clamp((lt - d) / 0.08)
        # slight horizontal slide alternating
        dx = (1 - p) * (120 if i == 0 else -120)
        paste_scaled(canvas, layer, W / 2 + dx, y + hgt / 2, scale, alpha)
        y += hgt + 10

def draw_index(canvas, n, lt):
    """'01' badge + label + rule, top left"""
    p = ease_out_expo(lt / 0.5)
    num = cached_text(f"{n:02d}", F_ANTON, 170, RED, shadow=True)
    paste_scaled(canvas, num, 70 - (1 - p) * 80, 300, 1.0, clamp(lt / 0.12), anchor="l")
    lab = cached_text("DATO CURIOSO", F_M800, 34, WHITE, tracking=9, shadow=True)
    paste_scaled(canvas, lab, 70 + num.width + 30, 270, 1.0, clamp((lt - 0.1) / 0.2), anchor="l")
    d = ImageDraw.Draw(canvas)
    ln = int(330 * ease_out_expo((lt - 0.12) / 0.5))
    if ln > 2:
        d.rectangle([70 + num.width + 32, 312, 70 + num.width + 32 + ln, 317], fill=WHITE)
    tot = cached_text(f"/ 07", F_M400, 34, (200, 200, 196), tracking=4, shadow=True)
    paste_scaled(canvas, tot, 70 + num.width + 32, 356, 1.0, clamp((lt - 0.2) / 0.2), anchor="l")

def caption_chunks(words):
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        joined = " ".join(x["w"] for x in cur)
        if len(cur) >= 3 or len(joined) >= 16 or w["w"].endswith((".", ",", "?", "!", "…")):
            chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    return chunks

def draw_captions(canvas, seg, t, cy=1430):
    chunks = caption_chunks(seg["words"])
    active = None
    for i, c in enumerate(chunks):
        a = c[0]["a"]; b = chunks[i + 1][0]["a"] if i + 1 < len(chunks) else seg["end"] + 0.15
        if a - 0.02 <= t < b: active = (c, a)
    if not active: return
    chunk, a = active
    f = font(F_M900, 74)
    words = [w["w"].upper().strip("¡!¿?.,…") for w in chunk]
    space = 22
    widths = [f.getlength(w) for w in words]
    total = sum(widths) + space * (len(words) - 1)
    x = W / 2 - total / 2
    pop = ease_out_back((t - a) / 0.22)
    d = ImageDraw.Draw(canvas)
    for w, wd, wd_obj in zip(words, widths, chunk):
        on = wd_obj["a"] <= t
        cur = wd_obj["a"] <= t < wd_obj["b"] + 0.05
        yoff = (1 - pop) * 40
        if cur:
            pad = 14
            d.rounded_rectangle([x - pad, cy - 50 + yoff, x + wd + pad, cy + 46 + yoff], radius=10, fill=RED)
        col = WHITE if on else (190, 190, 186)
        d.text((x, cy + yoff), w, font=f, fill=col, anchor="lm", stroke_width=0 if cur else 5, stroke_fill=BLACK)
        x += wd + space

def draw_progress(canvas, t):
    d = ImageDraw.Draw(canvas)
    x0, x1, y = 70, W - 70, 150
    n = 7; gapw = 10
    segw = (x1 - x0 - gapw * (n - 1)) / n
    facts = SEGS[1:8]
    for i, s in enumerate(facts):
        a = x0 + i * (segw + gapw)
        d.rectangle([a, y, a + segw, y + 6], fill=(255, 255, 255, 70))
        p = clamp((t - s["scene_a"]) / (s["scene_b"] - s["scene_a"]))
        if p > 0: d.rectangle([a, y, a + segw * p, y + 6], fill=RED)

def draw_brand(canvas, t):
    tag = cached_text("DATOS CURIOSOS", F_M800, 26, WHITE, tracking=8, shadow=True)
    paste_scaled(canvas, tag, W - 70 - tag.width, 100, 1.0, 0.85, anchor="l")
    d = ImageDraw.Draw(canvas)
    d.rectangle([W - 70 - tag.width - 22, 92, W - 70 - tag.width - 12, 108], fill=RED)

# ---------------------------------------------------------------- transitions
def transition(canvas, t, edges):
    """red matte diagonal wipe + flash around each scene edge"""
    for e in edges:
        dt = t - e
        if -0.2 < dt < 0.2:
            p = (dt + 0.2) / 0.4  # 0..1
            band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(band)
            off = -1600 + p * 3600
            poly = [(off, -200), (off + 700, -200), (off + 700 - 900, H + 200), (off - 900, H + 200)]
            d.polygon(poly, fill=RED + (255,))
            poly2 = [(off + 720, -200), (off + 760, -200), (off + 760 - 900, H + 200), (off + 720 - 900, H + 200)]
            d.polygon(poly2, fill=WHITE + (230,))
            canvas.alpha_composite(band)
        if 0 <= dt < 0.07:
            fl = Image.new("RGBA", (W, H), (255, 255, 255, int(150 * (1 - dt / 0.07))))
            canvas.alpha_composite(fl)

def chroma(canvas, amt):
    if amt < 1: return canvas
    r, g, b, a = canvas.split()
    r = r.transform(r.size, Image.AFFINE, (1, 0, -amt, 0, 1, 0))
    b = b.transform(b.size, Image.AFFINE, (1, 0, amt, 0, 1, 0))
    return Image.merge("RGBA", (r, g, b, a))

# ---------------------------------------------------------------- scenes
def scene_fact(t, seg, idx):
    a, b = seg["scene_a"], seg["scene_b"]
    mid = (seg["start"] + seg["end"]) / 2
    # split at the word nearest mid
    ws = [w["a"] for w in seg["words"]]
    split = min(ws, key=lambda x: abs(x - mid)) - 0.05 if ws else mid
    sw = SPLIT_WORD.get(seg["key"])
    for w in seg["words"][1:]:
        if w["w"].lower().strip(".,…") == sw:
            split = w["a"] - 0.04; break
    half = 0 if t < split else 1
    imgs = IMAGES[seg["key"]]
    name = imgs[half % len(imgs)]
    h0 = a if half == 0 else split
    h1 = split if half == 0 else b
    p = (t - h0) / (h1 - h0)
    lt = t - h0
    punch = 0.25 * (1 - ease_out_expo(lt / 0.45))
    pan = (0.05, -0.03) if half == 0 else (-0.05, 0.03)
    bg = kenburns(name, p, 1.04, 1.16, pan, punch).convert("RGBA")
    bg.alpha_composite(SHADE)
    draw_headline(bg, seg["key"], half, lt, cy=930)
    draw_index(bg, idx, t - a)
    draw_captions(bg, seg, t)
    return bg, [split]

def scene_hook(t, seg):
    a, b = seg["scene_a"], seg["scene_b"]
    keys = ["octopus", "venus", "honey", "flamingo", "eiffel", "cow", "brain", "hook"]
    # rapid montage first 2.4s, then hold on hook image
    edges = []
    if t < 2.4:
        step = 0.3
        k = int(t / step)
        name = IMAGES[keys[k % len(keys)]][0]
        lt = t - k * step
        bg = kenburns(name, lt / step, 1.22, 1.06, (0.0, 0.0)).convert("RGBA")
    else:
        lt = t - 2.4
        bg = kenburns(IMAGES["hook"][-1], lt / (b - 2.4), 1.0, 1.2, (0, -0.05), 0.2 * (1 - ease_out_expo(lt / 0.5))).convert("RGBA")
    bg.alpha_composite(SHADE)
    # red flash frames on montage beats
    if t < 2.4 and (t % 0.3) < 0.034:
        bg.alpha_composite(Image.new("RGBA", (W, H), RED + (140,)))
    # "¡PARA!" slam
    if t < 1.2:
        p = ease_out_expo(t / 0.25)
        st = cached_text("¡PARA!", F_ANTON, 330, WHITE)
        shake = (random.Random(int(t * 30)).uniform(-10, 10)) * (1 - clamp(t / 0.5))
        paste_scaled(bg, st, W / 2 + shake, 930 + shake, 1 + (1 - p) * 1.2, clamp(t / 0.05) * (1 - clamp((t - 1.0) / 0.2)))
    if t >= 1.15:
        cuts = [1.15] + [w["a"] - 0.05 for w in seg["words"] if w["w"].lower() in ("que", "el")]
        half = max(i for i, c in enumerate(cuts) if t >= c)
        h0 = cuts[half]
        draw_headline(bg, "hook", half, t - h0, cy=930)
    draw_captions(bg, seg, t)
    return bg, [2.4]

def scene_outro(t, seg):
    a, b = seg["scene_a"], seg["scene_b"]
    lt = t - a
    # background: dark montage fading to black w/ red glow
    bg = kenburns(IMAGES["brain"][-1], clamp(lt / (b - a)), 1.1, 1.25, (0, 0)).convert("RGBA")
    dark = clamp(0.55 + lt * 0.25, 0, 0.88)
    bg.alpha_composite(Image.new("RGBA", (W, H), BLACK + (int(255 * dark),)))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    r = 520 + 40 * math.sin(lt * 3)
    gd.ellipse([W / 2 - r, 960 - r, W / 2 + r, 960 + r], fill=RED + (90,))
    bg.alpha_composite(glow.filter(ImageFilter.GaussianBlur(160)))
    q = cached_text("¿CUÁL TE SORPRENDIÓ MÁS?", F_M900, 56, WHITE, tracking=2)
    paste_scaled(bg, q, W / 2, 560, 1 + (1 - ease_out_expo(lt / 0.4)) * 0.3, clamp(lt / 0.1))
    # comment hint
    c = cached_text("DÉJALO EN COMENTARIOS", F_M800, 32, (210, 210, 205), tracking=8)
    paste_scaled(bg, c, W / 2, 640, 1.0, clamp((lt - 0.4) / 0.3))
    t2 = lt - 1.75
    if t2 > 0:
        s1 = cached_text("SÍGUEME", F_ANTON, 300, WHITE)
        p = ease_out_expo(t2 / 0.4)
        paste_scaled(bg, s1, W / 2, 880, 1 + (1 - p) * 0.8, clamp(t2 / 0.06))
        s2 = cached_text("PARA MÁS", F_M900, 64, WHITE, tracking=14)
        paste_scaled(bg, s2, W / 2, 1130, 1.0, clamp((t2 - 0.25) / 0.2))
        s3 = cached_text("DATOS CURIOSOS", F_ANTON, 150, RED)
        p3 = ease_out_back((t2 - 0.4) / 0.45)
        paste_scaled(bg, s3, W / 2, 1255, max(0.01, p3), clamp((t2 - 0.4) / 0.1))
    t3 = lt - 3.1
    if t3 > 0:
        d = ImageDraw.Draw(bg)
        pb = ease_out_back(t3 / 0.4)
        bw, bh = 520 * pb, 120 * pb
        tap = 1 - 0.08 * math.exp(-((t3 - 1.0) / 0.08) ** 2)
        bw *= tap; bh *= tap
        followed = t3 > 1.0
        fill = WHITE if followed else RED
        d.rounded_rectangle([W / 2 - bw / 2, 1460 - bh / 2, W / 2 + bw / 2, 1460 + bh / 2], radius=int(bh / 2), fill=fill)
        if pb > 0.6:
            lab = cached_text("✓ SIGUIENDO" if followed else "+ SEGUIR", F_M900, 52, RED if followed else WHITE, shadow=False) if not followed else cached_text("SIGUIENDO", F_M900, 52, RED, shadow=False)
            paste_scaled(bg, lab, W / 2, 1460, pb * tap, 1.0)
        # ripple at tap
        if 1.0 < t3 < 1.6:
            rp = (t3 - 1.0) / 0.6
            rr = 60 + rp * 380
            ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(ring).ellipse([W / 2 - rr, 1460 - rr, W / 2 + rr, 1460 + rr], outline=WHITE + (int(200 * (1 - rp)),), width=6)
            bg.alpha_composite(ring)
        # finger/cursor dot
        if t3 < 1.3:
            fx = W / 2 + 260 * (1 - ease_in_out((t3 - 0.3) / 0.65)); fy = 1640 - 180 * ease_in_out((t3 - 0.3) / 0.65)
            dot = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(dot).ellipse([fx - 34, fy - 34, fx + 34, fy + 34], fill=(255, 255, 255, 150), outline=WHITE, width=4)
            bg.alpha_composite(dot)
    return bg, []

def render_frame(fi):
    t = fi / FPS
    idx = 0
    for i, s in enumerate(SEGS):
        if s["scene_a"] <= t < s["scene_b"] or (i == len(SEGS) - 1 and t >= s["scene_a"]): idx = i
    seg = SEGS[idx]
    if seg["key"] == "hook":
        frame, inner = scene_hook(t, seg)
    elif seg["key"] == "outro":
        frame, inner = scene_outro(t, seg)
    else:
        frame, inner = scene_fact(t, seg, idx)
    # transitions at scene edges + inner cuts (inner cuts get flash only)
    edges = [s["scene_a"] for s in SEGS[1:]]
    transition(frame, t, edges)
    for e in inner:
        dt = t - e
        if 0 <= dt < 0.06:
            frame.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(110 * (1 - dt / 0.06)))))
    # chromatic punch near edges
    near = min([abs(t - e) for e in edges + inner] + [9])
    frame = chroma(frame, int(14 * clamp(1 - near / 0.18)))
    if seg["key"] != "outro" or t < seg["scene_a"] + 0.3:
        draw_progress(frame, t)
    draw_brand(frame, t)
    frame.alpha_composite(GRAINS[fi % len(GRAINS)])
    return frame.convert("RGB").tobytes()

if __name__ == "__main__":
    t0 = float(sys.argv[3]) if len(sys.argv) > 3 else 0
    t1 = float(sys.argv[4]) if len(sys.argv) > 4 else DUR
    frames = range(int(round(t0 * FPS)), int(round(t1 * FPS)))
    if OUT.endswith(".png"):
        for fi in frames:
            Image.frombytes("RGB", (W, H), render_frame(fi)).save(OUT.replace(".png", f"_{fi:04d}.png"))
        sys.exit()
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                           "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", OUT], stdin=subprocess.PIPE)
    with Pool(os.cpu_count()) as pool:
        for i, buf in enumerate(pool.imap(render_frame, frames, chunksize=4)):
            ff.stdin.write(buf)
            if i % 150 == 0: print("frame", i, flush=True)
    ff.stdin.close(); ff.wait()
