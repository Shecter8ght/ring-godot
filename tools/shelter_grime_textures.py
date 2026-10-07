"""Текстуры старения котельной: подтёки (CC0 ambientCG, декали), макро-пятна и полосы для шейдера
стен (свои, шум), копоть, пыль у стен, надписи маркером и мелом (шрифт Neucha, OFL).

python tools/shelter_grime_textures.py
Пишет assets/shelter/textures/grime/*.png; исходники — в _asset_src/shelter/grime/ (вне git).
"""
import io
import math
import os
import random
import urllib.request
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'assets', 'shelter', 'textures', 'grime')
SRC = os.path.join(ROOT, '_asset_src', 'shelter', 'grime')
LEAKS = ['Leaking001', 'Leaking003', 'Leaking004', 'Leaking005', 'Leaking008']
FONT_URL = 'https://github.com/google/fonts/raw/main/ofl/neucha/Neucha.ttf'
UA = {'User-Agent': 'RING-asset-fetch/1.0'}


def fetch(url, path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req) as r, open(path, 'wb') as f:
            f.write(r.read())
    return path


def save(img, name):
    os.makedirs(OUT, exist_ok=True)
    img.save(os.path.join(OUT, name), optimize=True)
    print('  ', name, img.size)


# ---------------------------------------------------------------- шум

def periodic_noise(size, cells, rng):
    """Тайлящийся value-noise: решётка cells×cells, косинусная интерполяция."""
    g = rng.random((cells, cells))
    xs = np.arange(size) * cells / size
    i0 = np.floor(xs).astype(int) % cells
    i1 = (i0 + 1) % cells
    t = xs - np.floor(xs)
    t = (1 - np.cos(t * math.pi)) * 0.5
    a = g[i0][:, i0] * (1 - t)[None, :] + g[i0][:, i1] * t[None, :]
    b = g[i1][:, i0] * (1 - t)[None, :] + g[i1][:, i1] * t[None, :]
    return a * (1 - t)[:, None] + b * t[:, None]


def fbm(size, base, octaves, rng, gain=0.5):
    out = np.zeros((size, size))
    amp, total = 1.0, 0.0
    for o in range(octaves):
        out += periodic_noise(size, base * 2 ** o, rng) * amp
        total += amp
        amp *= gain
    return out / total


def norm(a):
    return (a - a.min()) / max(1e-6, a.max() - a.min())


def gray(a):
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), 'L')


# ---------------------------------------------------------------- шейдерные маски

def macro_mask():
    """Крупные пятна (метры) — ломают повтор плитки текстур: R — пятна, G — мелкие разводы."""
    rng = np.random.default_rng(5)
    big = norm(fbm(512, 3, 5, rng))
    small = norm(fbm(512, 12, 4, rng))
    big = np.clip((big - 0.5) * 1.6 + 0.5, 0, 1)
    img = np.stack([big, small, np.zeros_like(big)], -1)
    save(Image.fromarray((img * 255).astype(np.uint8), 'RGB'), 'macro.png')


def streak_mask():
    """Вертикальные подтёки, тайлятся по обеим осям: колонки разной ширины и длины, капли внизу."""
    rng = np.random.default_rng(11)
    w = h = 512
    a = np.zeros((h, w))
    for _ in range(140):
        x = rng.integers(0, w)
        width = rng.uniform(1.5, 9.0)
        y0 = rng.integers(0, h)
        length = rng.integers(40, 380)
        strength = rng.uniform(0.25, 1.0)
        ys = (y0 + np.arange(length)) % h
        fade = np.linspace(1.0, 0.0, length) ** rng.uniform(0.6, 1.8)
        wobble = np.cumsum(rng.normal(0, 0.25, length))
        for k, y in enumerate(ys):
            cx = x + wobble[k]
            xs = np.arange(int(cx - width * 2), int(cx + width * 2) + 1)
            d = np.abs(xs - cx) / width
            v = np.clip(1 - d, 0, 1) ** 1.5 * strength * fade[k]
            a[y, xs % w] = np.maximum(a[y, xs % w], v)
    a = np.asarray(gray(a).filter(ImageFilter.GaussianBlur(1.2))) / 255.0
    noise = norm(fbm(512, 8, 4, rng))
    save(gray(np.clip(a * (0.55 + 0.6 * noise), 0, 1)), 'streaks.png')


# ---------------------------------------------------------------- декали

def leaks():
    """Подтёки ambientCG (CC0): цвет + непрозрачность в альфу, ORM из шероховатости, нормаль GL."""
    for i, asset in enumerate(LEAKS):
        z = fetch('https://ambientcg.com/get?file=%s_1K-PNG.zip' % asset, os.path.join(SRC, asset + '_1K-PNG.zip'))
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()

            def part(suffix):
                for n in names:
                    if n.endswith(suffix):
                        return Image.open(io.BytesIO(zf.read(n)))
                return None
            color = part('_Color.png').convert('RGB')
            opacity = part('_Opacity.png').convert('L')
            rough = part('_Roughness.png')
            normal = part('_NormalGL.png')
        # подтёк на побелке и кирпиче — ржаво-бурый, а не «чистая вода»: тон к грязи, альфа мягче
        c = np.asarray(color).astype(float) / 255.0
        lum = c.mean(-1, keepdims=True)
        tint = np.array([0.42, 0.34, 0.24])
        c = np.clip(lum * 0.6 + tint * 0.5, 0, 1) * 0.6
        al = np.asarray(opacity).astype(float) / 255.0
        rgba = np.concatenate([c, np.clip(al * 1.1, 0, 1)[..., None]], -1)
        size = (512, 1024) if color.size[1] > color.size[0] else (512, 512)
        save(Image.fromarray((rgba * 255).astype(np.uint8), 'RGBA').resize(size, Image.LANCZOS), 'leak_%d.png' % i)
        # высолы: белёсые соляные потёки на кирпиче и тёмной краске
        salt = np.clip(0.62 + (lum - lum.mean()) * 0.5, 0, 1) * np.array([1.0, 0.98, 0.93])
        rgba = np.concatenate([salt, np.clip(al * 0.9, 0, 1)[..., None]], -1)
        save(Image.fromarray((rgba * 255).astype(np.uint8), 'RGBA').resize(size, Image.LANCZOS), 'salt_%d.png' % i)
        if rough is not None:
            r = np.asarray(rough.convert('L')).astype(float) / 255.0
            orm = np.stack([np.ones_like(r), r * 0.8, np.zeros_like(r)], -1)
            save(Image.fromarray((orm * 255).astype(np.uint8), 'RGB').resize((256, 512) if color.size[1] > color.size[0] else (256, 256), Image.LANCZOS), 'leak_%d_orm.png' % i)
        if normal is not None:
            save(normal.convert('RGB').resize((256, 512) if color.size[1] > color.size[0] else (256, 256), Image.LANCZOS), 'leak_%d_normal.png' % i)


def soot_plume():
    """Копоть над топкой, лампой, трубой: язык вверх, плотный у основания, рваный край."""
    rng = np.random.default_rng(21)
    w, h = 256, 512
    y, x = np.mgrid[0:h, 0:w]
    u = (x - w / 2) / (w / 2)
    v = 1.0 - y / h  # 0 — низ, 1 — верх
    spread = 0.18 + 0.82 * v ** 0.6
    core = np.clip(1 - (np.abs(u) / spread) ** 2, 0, 1)
    noise = norm(fbm(512, 6, 5, rng))[:h, :w]
    a = core * (1 - v ** 1.5) * (0.4 + 0.8 * noise) * np.clip(v * 10, 0, 1)
    a = np.clip(a * 1.1, 0, 0.95)
    rgb = np.ones((h, w, 3)) * np.array([0.06, 0.055, 0.05])
    save(Image.fromarray((np.concatenate([rgb, a[..., None]], -1) * 255).astype(np.uint8), 'RGBA'), 'soot.png')


def dust_strip():
    """Пыль и грязь на полу вдоль стены: тайлится по длине (X), у стены (верх, v=0) плотнее."""
    rng = np.random.default_rng(31)
    w, h = 1024, 256
    n = norm(fbm(1024, 10, 5, rng))[:h, :w]
    fine = norm(fbm(1024, 48, 3, rng))[:h, :w]
    v = np.arange(h)[:, None] / h
    a = (1 - v) ** 1.4 * (0.45 + 0.7 * n) * (0.7 + 0.3 * fine)
    a = np.clip(a, 0, 0.9)
    rgb = np.ones((h, w, 3)) * np.array([0.47, 0.44, 0.38])
    save(Image.fromarray((np.concatenate([rgb, a[..., None]], -1) * 255).astype(np.uint8), 'RGBA'), 'dust_strip.png')


def floor_grime():
    """Пятна на полу: размазанная грязь, следы колёс тележек — круглые и вытянутые пятна."""
    rng = np.random.default_rng(41)
    for i in range(3):
        s = 512
        y, x = np.mgrid[0:s, 0:s]
        cx, cy = s / 2, s / 2
        ax, ay = rng.uniform(0.6, 1.0), rng.uniform(0.35, 1.0)
        d = np.sqrt(((x - cx) / (s / 2 * ax)) ** 2 + ((y - cy) / (s / 2 * ay)) ** 2)
        n = norm(fbm(512, 5 + i * 2, 5, rng))
        a = np.clip(1 - d + (n - 0.5) * 0.9, 0, 1) ** 0.8 * (0.35 + 0.55 * n)
        a = np.clip(a, 0, 0.92)
        rgb = np.ones((s, s, 3)) * np.array([0.07, 0.06, 0.05])
        save(Image.fromarray((np.concatenate([rgb, a[..., None]], -1) * 255).astype(np.uint8), 'RGBA'), 'floor_grime_%d.png' % i)


# ---------------------------------------------------------------- надписи

NOTES = [
    ('ДАВЛЕНИЕ НЕ ВЫШЕ 3', 'marker'), ('ПРОВЕРЕНО', 'marker'), ('ВОДА ТЕХНИЧЕСКАЯ\nНЕ ПИТЬ', 'marker'),
    ('КАНИСТРЫ СЮДА', 'chalk', 'right'), ('ЗАКРЫВАТЬ!', 'marker'), ('№ 2', 'chalk'),
    ('|||| |||| |||', 'chalk'), ('НЕ КУРИТЬ', 'marker'), ('ВЕНТИЛЬ', 'chalk', 'down'),
]


def notes():
    """Атлас 3×3 надписей: маркер (тёмно-синий, плотный) и мел (белёсый, рваный)."""
    font_path = fetch(FONT_URL, os.path.join(SRC, 'Neucha.ttf'))
    cell_w, cell_h = 512, 256
    atlas = Image.new('RGBA', (cell_w * 3, cell_h * 3), (0, 0, 0, 0))
    rng = random.Random(7)
    for k, note in enumerate(NOTES):
        text, kind = note[0], note[1]
        arrow = note[2] if len(note) > 2 else ''
        cell = Image.new('L', (cell_w, cell_h), 0)
        d = ImageDraw.Draw(cell)
        size = 64 if '\n' not in text else 52
        room = cell_w * (0.62 if arrow == 'right' else 0.88)
        while True:
            font = ImageFont.truetype(font_path, size)
            bbox = d.multiline_textbbox((0, 0), text, font=font, align='center')
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if tw <= room or size <= 24:
                break
            size -= 4
        x0 = (cell_w - tw - (120 if arrow == 'right' else 0)) / 2 - bbox[0]
        y0 = (cell_h - th - (70 if arrow == 'down' else 0)) / 2 - bbox[1]
        d.multiline_text((x0, y0), text, font=font, fill=255, align='center')
        # стрелка от руки: древко и два «уса» (в шрифте стрелок нет)
        if arrow == 'right':
            ax, ay = x0 + bbox[0] + tw + 20, cell_h / 2
            d.line([(ax, ay), (ax + 95, ay + 3)], fill=255, width=7)
            d.line([(ax + 95, ay + 3), (ax + 70, ay - 18)], fill=255, width=7)
            d.line([(ax + 95, ay + 3), (ax + 72, ay + 24)], fill=255, width=7)
        elif arrow == 'down':
            ax, ay = cell_w / 2, y0 + bbox[1] + th + 12
            d.line([(ax, ay), (ax + 2, ay + 60)], fill=255, width=7)
            d.line([(ax + 2, ay + 60), (ax - 18, ay + 38)], fill=255, width=7)
            d.line([(ax + 2, ay + 60), (ax + 22, ay + 40)], fill=255, width=7)
        cell = cell.rotate(rng.uniform(-6, 6), resample=Image.BICUBIC)
        a = np.asarray(cell).astype(float) / 255.0
        nrng = np.random.default_rng(k)
        grain = nrng.random(a.shape)
        if kind == 'chalk':
            a = a * np.clip(grain * 1.6 - 0.25, 0, 1) * 0.85
            rgb = np.array([0.82, 0.82, 0.78])
        else:
            a = a * (0.75 + 0.25 * grain)
            rgb = np.array([0.08, 0.09, 0.16])
        tile = np.concatenate([np.ones(a.shape + (3,)) * rgb, a[..., None]], -1)
        note_img = Image.fromarray((tile * 255).astype(np.uint8), 'RGBA')
        atlas.paste(note_img, ((k % 3) * cell_w, (k // 3) * cell_h))
        # декаль берёт текстуру целиком — каждая надпись ещё и отдельным файлом
        save(note_img, 'note_%d.png' % k)
    save(atlas, 'notes.png')


if __name__ == '__main__':
    macro_mask()
    streak_mask()
    leaks()
    soot_plume()
    dust_strip()
    floor_grime()
    notes()
