"""Пожарная АЦ, этап 2: картинки наклеек износа (вне Blender, Pillow + OpenCV + scikit-image).

- листья — вырезаны из фото-атласов ambientCG LeafSet012 / 021 / 028 (CC0) по их картам прозрачности;
- помёт — пятно со снимка Wikimedia Commons «Bird poop next to turtle poop» (CC0, Hamedjavan), перекрашено в высохшее
  известковое; варианты — упругим искажением того же пятна;
- ладони — маски владельца «Маски_АЛЬФА/02_Отпечатки_ладоней» (свои, запасные: CC0 ладоней не нашлось);
- надписи пальцем по пыли и граффити баллончиком — текст вымышленный, шрифт DejaVu (свободный): рукописный наклон,
  пальцем — по скелету букв шириной подушечки; граффити — «пузырь» с обводкой и тег, края распыла, брызги, подтёки.

python -X utf8 tools/fire_truck/wear_sprites.py   → WORK/wear/sprites/*.png, sprites.json (размеры в метрах)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage.morphology import skeletonize

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
WORK = ROOT / "_asset_src" / "fire_truck" / "tex"
TEX = ROOT / "_asset_src" / "fire_truck_tex"
OUT = WORK / "wear" / "sprites"
MPL = Path("D:/ПРОГРАММЫ/python/Lib/site-packages/matplotlib/mpl-data/fonts/ttf")
FONT_BOLD = ROOT / "_asset_src" / "fonts" / "DejaVuSans-Bold.ttf"
FONT_OBL = MPL / "DejaVuSans-Oblique.ttf"
FONT_BOBL = MPL / "DejaVuSans-BoldOblique.ttf"
HANDS = Path("E:/Models Blender/Маски_АЛЬФА/02_Отпечатки_ладоней")
PX_M = 1000                                          # пикселей на метр у рисованных наклеек (1 пикс/мм)


def save_rgba(path, rgb, a):
    im = np.dstack([np.clip(rgb, 0, 1), np.clip(a, 0, 1)])
    Image.fromarray((im * 255 + 0.5).astype(np.uint8), "RGBA").save(path)


def save_gray(path, g):
    Image.fromarray((np.clip(g, 0, 1) * 255 + 0.5).astype(np.uint8), "L").save(path)


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def noise(h, w, cell, rng):
    n = rng.random((h // cell + 3, w // cell + 3)).astype(np.float32)
    return cv2.resize(n, (w + 2 * cell, h + 2 * cell), interpolation=cv2.INTER_CUBIC)[cell:cell + h, cell:cell + w]


def warp(img, amp, cell, rng):
    """Упругое искажение: рука, а не машина."""
    h, w = img.shape[:2]
    dx = (noise(h, w, cell, rng) - 0.5) * 2 * amp
    dy = (noise(h, w, cell, rng) - 0.5) * 2 * amp
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(img, gx + dx, gy + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


# ------------------------------------------------------------------------------------------------------------ листья
def leaves(meta):
    sets = [("LeafSet028", "maple"), ("LeafSet012", "oak"), ("LeafSet021", "yellow")]
    out = []
    for name, kind in sets:
        d = TEX / f"ambientcg_{name}"
        col = np.asarray(Image.open(d / f"{name}_8K-PNG_Color.png").convert("RGB"), np.float32) / 255
        op = np.asarray(Image.open(d / f"{name}_8K-PNG_Opacity.png").convert("L"), np.float32) / 255
        rough = np.asarray(Image.open(d / f"{name}_8K-PNG_Roughness.png").convert("L"), np.float32) / 255
        n, lab, stats, _ = cv2.connectedComponentsWithStats((op > 0.5).astype(np.uint8), 8)
        for k in range(1, n):
            x, y, w, h, area = stats[k]
            if area < 20000:
                continue
            pad = 8
            x0, y0 = max(0, x - pad), max(0, y - pad)
            x1, y1 = min(op.shape[1], x + w + pad), min(op.shape[0], y + h + pad)
            a = op[y0:y1, x0:x1] * (lab[y0:y1, x0:x1] == k)
            a = cv2.dilate(a, np.ones((3, 3), np.uint8))  # мягкий край оставлен картой прозрачности
            a = np.minimum(a, op[y0:y1, x0:x1])
            rgb = col[y0:y1, x0:x1]
            s = 384 / max(a.shape)                        # 10-сантиметровый лист — ~3,8 пикс/мм
            size = (max(1, int(a.shape[1] * s)), max(1, int(a.shape[0] * s)))
            a = cv2.resize(a, size, interpolation=cv2.INTER_AREA)
            rgb = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA)
            r = cv2.resize(rough[y0:y1, x0:x1], size, interpolation=cv2.INTER_AREA)
            fn = f"leaf_{len(out):02d}.png"
            save_rgba(OUT / fn, rgb, a)
            save_gray(OUT / fn.replace(".png", "_rough.png"), r)
            out.append({"file": fn, "kind": kind, "aspect": size[0] / size[1]})
    meta["leaves"] = out
    print("листьев", len(out), flush=True)


# ------------------------------------------------------------------------------------------------------------- помёт
def droppings(meta, rng):
    src = np.asarray(Image.open(TEX / "commons_photo_sources" / "Bird_poop_next_to_turtle_poop.jpg").convert("RGB"),
                     np.float32) / 255
    # пятно справа: светлое ядро (известь) и тёмный ободок (жидкая часть) на сером грунте
    y0, y1, x0, x1 = 1200, 2330, 1780, 2760
    crop = src[y0:y1, x0:x1]
    ground = np.median(src[200:900, 200:900].reshape(-1, 3), axis=0)
    blur = cv2.GaussianBlur(crop, (0, 0), 6)
    diff = np.linalg.norm(blur - ground, axis=-1)
    n, lab, stats, _ = cv2.connectedComponentsWithStats((diff > 0.14).astype(np.uint8), 8)
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    solid = (lab == k).astype(np.uint8)
    solid = cv2.morphologyEx(solid, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61)))
    ff = np.pad(solid, 1)
    cv2.floodFill(ff, None, (0, 0), 1)                  # дыры внутри пятна — тоже пятно
    solid = np.maximum(solid, 1 - ff[1:-1, 1:-1])
    solid = cv2.morphologyEx(solid, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)))
    mask = cv2.GaussianBlur(solid.astype(np.float32), (0, 0), 3)
    lum = crop.mean(-1)
    white = smooth(lum, 0.45, 0.75)                  # известь — высыхает белой; жидкость — серо-бурая плёнка
    out = []
    for v in range(4):
        mm = warp(mask, 45, 160, rng) if v else mask
        ww = warp(white, 45, 160, rng) if v else white
        if v % 2:
            mm, ww = mm[:, ::-1], ww[:, ::-1]
        dry = np.array([0.80, 0.79, 0.74]) * (0.85 + 0.15 * ww[..., None])
        film = np.array([0.42, 0.40, 0.35])
        rgb = film * (1 - ww[..., None]) + dry * ww[..., None]
        a = mm
        ys, xs = np.nonzero(a > 0.02)
        a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        rgb = rgb[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        s = 256 / max(a.shape)
        size = (int(a.shape[1] * s), int(a.shape[0] * s))
        fn = f"drop_{v}.png"
        save_rgba(OUT / fn, cv2.resize(rgb, size, interpolation=cv2.INTER_AREA),
                  cv2.resize(a, size, interpolation=cv2.INTER_AREA))
        out.append({"file": fn, "aspect": size[0] / size[1]})
    meta["drops"] = out


# ------------------------------------------------------------------------------------------------------------ ладони
def hands(meta):
    out = []
    for p in sorted(HANDS.glob("*.png")):
        g = np.asarray(Image.open(p).convert("L"), np.float32) / 255
        g = cv2.resize(g, (512, 512), interpolation=cv2.INTER_AREA)
        fn = f"hand_{len(out)}.png"
        save_gray(OUT / fn, smooth(g, 0.08, 0.75))
        out.append({"file": fn, "src": p.name, "size_m": 0.21})        # ладонь с пальцами ~19 × 21 см
    meta["hands"] = out


# ----------------------------------------------------------------------------------------------- надписи пальцем
def _text(text, font, size, pad=60):
    f = ImageFont.truetype(str(font), size)
    l, t, r, b = f.getbbox(text)
    im = Image.new("L", (r - l + 2 * pad, b - t + 2 * pad), 0)
    ImageDraw.Draw(im).text((pad - l, pad - t), text, font=f, fill=255)
    return np.asarray(im, np.float32) / 255


def finger(text, height_m, rng, width_mm=13):
    """Надпись пальцем по пыли: скелет букв рукописного начертания, ширина — подушечка пальца; край — валик сдвинутой
    пыли, внутри — стёрто не до конца (полосами вдоль движения)."""
    px = height_m * PX_M
    g = _text(text, FONT_OBL, int(px * 1.25))
    g = warp(g, px * 0.05, int(px * 0.6), rng)
    sk = skeletonize(g > 0.5).astype(np.uint8)
    d = cv2.distanceTransform(1 - sk, cv2.DIST_L2, 5)
    w = width_mm / 2 * (0.8 + 0.4 * noise(*d.shape, int(px * 0.4), rng))
    core = 1 - smooth(d, w * 0.55, w * 1.05)
    streak = 0.75 + 0.25 * noise(*d.shape, 6, rng)
    ridge = np.exp(-((d - w * 1.15) / (w * 0.25)) ** 2)        # пыль, сдвинутая пальцем, легла валиком по краю
    return np.clip(core * streak, 0, 1), ridge * (1 - core)


def drawing_smile(size_m, rng, width_mm=14):
    px = int(size_m * PX_M)
    im = Image.new("L", (px + 120, px + 120), 0)
    dr = ImageDraw.Draw(im)
    c = 60
    dr.ellipse((c, c, c + px, c + px), outline=255, width=3)
    dr.ellipse((c + px * 0.3, c + px * 0.3, c + px * 0.36, c + px * 0.36), outline=255, width=3)
    dr.ellipse((c + px * 0.62, c + px * 0.3, c + px * 0.68, c + px * 0.36), outline=255, width=3)
    dr.arc((c + px * 0.25, c + px * 0.35, c + px * 0.75, c + px * 0.75), 20, 160, fill=255, width=3)
    g = warp(np.asarray(im, np.float32) / 255, px * 0.02, int(px * 0.4), rng)
    sk = skeletonize(g > 0.3).astype(np.uint8)
    d = cv2.distanceTransform(1 - sk, cv2.DIST_L2, 5)
    w = width_mm / 2
    core = 1 - smooth(d, w * 0.55, w * 1.05)
    ridge = np.exp(-((d - w * 1.15) / (w * 0.25)) ** 2)
    return np.clip(core * (0.75 + 0.25 * noise(*d.shape, 6, rng)), 0, 1), ridge * (1 - core)


# ------------------------------------------------------------------------------------------------------- граффити
def spray_edge(shape, rng, soft_mm=3.0, dust_mm=18, dust=0.35):
    """Край распыла: мягкий спад и облачко брызг (точки, редеющие от края)."""
    m = cv2.GaussianBlur(shape, (0, 0), soft_mm)
    d = cv2.distanceTransform((shape < 0.5).astype(np.uint8), cv2.DIST_L2, 5)
    dots = (rng.random(shape.shape) < 0.08).astype(np.float32)
    dots = cv2.GaussianBlur(dots, (0, 0), 0.7) * 3
    halo = np.exp(-d / dust_mm) * dots * dust
    return np.clip(np.maximum(m, halo), 0, 1)


def drips(shape, rng, n, max_len_mm, w_mm):
    """Подтёки краски вниз от нижних кромок пятна (у толстого слоя), с каплей на конце."""
    h, w = shape.shape
    out = np.zeros_like(shape)
    edge = (shape > 0.5) & (np.roll(shape, -3, axis=0) < 0.5)
    ys, xs = np.nonzero(edge)
    if not len(xs):
        return out
    im = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(im)
    for i in rng.choice(len(xs), size=min(n, len(xs)), replace=False):
        x, y = int(xs[i]), int(ys[i])
        L = rng.uniform(0.25, 1.0) ** 2 * max_len_mm
        ww = max(2, int(w_mm * rng.uniform(0.6, 1.2)))
        y2 = min(h - 6, int(y + L))
        dr.line((x, y - 2, x + rng.normal(0, 1.5), y2), fill=255, width=ww)
        dr.ellipse((x - ww * 0.8, y2 - ww * 0.8, x + ww * 0.8, y2 + ww * 0.9), fill=255)
    return np.asarray(im, np.float32) / 255


def throwup(text, height_m, rng, fill_rgb, line_rgb, metal_fill):
    """«Пузырь»: буквы с перекрытием, скруглённые и раздутые, толстая обводка, края распыла, подтёки."""
    px = int(height_m * PX_M)
    f = ImageFont.truetype(str(FONT_BOLD), int(px * 1.15))
    pad = int(px * 0.6)
    widths = [f.getbbox(ch)[2] - f.getbbox(ch)[0] for ch in text]
    W = int(sum(widths) * 0.88) + 2 * pad
    H = px * 2 + 2 * pad
    im = Image.new("L", (W, H), 0)
    x = pad
    for ch, cw in zip(text, widths):
        lay = Image.new("L", (W, H), 0)
        l, t, r, b = f.getbbox(ch)
        ImageDraw.Draw(lay).text((x - l, pad + px * 0.3 - t + rng.normal(0, px * 0.06)), ch, font=f, fill=255)
        lay = lay.rotate(rng.normal(0, 7), center=(x + cw / 2, H / 2), resample=Image.BILINEAR)
        im = Image.fromarray(np.maximum(np.asarray(im), np.asarray(lay)))
        x += int(cw * 0.86)
    g = np.asarray(im, np.float32) / 255
    g = warp(g, px * 0.06, int(px * 0.5), rng)
    g = cv2.GaussianBlur(g, (0, 0), px * 0.05)
    fill = (g > 0.35).astype(np.float32)
    fill = cv2.dilate(fill, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(px * 0.06) | 1,) * 2))
    line = cv2.dilate(fill, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(px * 0.16) | 1,) * 2))
    line_a = spray_edge(line, rng, 2.5, 14, 0.4)
    line_a = np.maximum(line_a, drips(line, rng, 9, px * 0.35, 6))
    fill_a = spray_edge(fill, rng, 3.5, 10, 0.25) * (0.85 + 0.15 * noise(*fill.shape, 40, rng))
    fill_a = np.maximum(fill_a, drips(fill, rng, 5, px * 0.22, 5) * 0.9) * smooth(line_a, 0.5, 0.9)
    rgb = np.array(line_rgb) * (1 - fill_a[..., None]) + np.array(fill_rgb) * fill_a[..., None]
    a = np.maximum(line_a, fill_a)
    metal = fill_a * metal_fill
    return rgb, a, metal


def tag(text, height_m, rng, rgb_col, width_mm=22):
    """Тег — одним движением, наклонно: скелет букв жирного наклонного начертания, линия баллончика с распылом."""
    px = int(height_m * PX_M)
    g = _text(text, FONT_BOBL, int(px * 1.3), pad=int(px * 0.5))
    g = warp(g, px * 0.08, int(px * 0.5), rng)
    sk = skeletonize(g > 0.5).astype(np.uint8)
    d = cv2.distanceTransform(1 - sk, cv2.DIST_L2, 5)
    w = width_mm / 2 * (0.8 + 0.4 * noise(*d.shape, int(px * 0.3), rng))
    core = (d < w).astype(np.float32)
    a = spray_edge(core, rng, 2.0, 12, 0.35)
    a = np.maximum(a, drips(core, rng, 7, px * 0.4, 5))
    rgb = np.zeros(a.shape + (3,), np.float32) + np.array(rgb_col)
    return rgb, a, a * 0


GRAFFITI = [  # вымышленные слова; цвета — баллончики: серебрянка, чёрный, синий, красный
    ("graff_zhuk", "throwup", "ЖУК", 0.45, dict(fill_rgb=(0.78, 0.78, 0.78), line_rgb=(0.025, 0.025, 0.03), metal_fill=0.8)),
    ("graff_tiho", "tag", "тихо", 0.30, dict(rgb_col=(0.05, 0.12, 0.42))),
    ("graff_kot", "tag", "КОТ 23", 0.22, dict(rgb_col=(0.03, 0.03, 0.035))),
    ("graff_volna", "throwup", "ВОЛНА", 0.36, dict(fill_rgb=(0.10, 0.30, 0.62), line_rgb=(0.92, 0.92, 0.90), metal_fill=0.0)),
]
WRITING = [("write_pomoi", "ПОМОЙ МЕНЯ", 0.11), ("write_01", "01", 0.16), ("write_kira", "КИРА + ДИМА", 0.08)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(11)
    meta = {"px_m": PX_M}
    leaves(meta)
    droppings(meta, rng)
    hands(meta)
    meta["writing"] = []
    for key, text, h in WRITING:
        core, ridge = finger(text, h, rng)
        save_gray(OUT / f"{key}.png", core)
        save_gray(OUT / f"{key}_ridge.png", ridge)
        meta["writing"].append({"file": f"{key}.png", "w_m": core.shape[1] / PX_M, "h_m": core.shape[0] / PX_M})
    core, ridge = drawing_smile(0.22, rng)
    save_gray(OUT / "write_smile.png", core)
    save_gray(OUT / "write_smile_ridge.png", ridge)
    meta["writing"].append({"file": "write_smile.png", "w_m": core.shape[1] / PX_M, "h_m": core.shape[0] / PX_M})
    meta["graffiti"] = []
    for key, kind, text, h, kw in GRAFFITI:
        rgb, a, metal = throwup(text, h, rng, **kw) if kind == "throwup" else tag(text, h, rng, **kw)
        save_rgba(OUT / f"{key}.png", rgb, a)
        save_gray(OUT / f"{key}_metal.png", metal)
        meta["graffiti"].append({"file": f"{key}.png", "w_m": a.shape[1] / PX_M, "h_m": a.shape[0] / PX_M,
                                 "text": text})
    with open(OUT / "sprites.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("SPRITES", {k: len(v) for k, v in meta.items() if isinstance(v, list)}, flush=True)


if __name__ == "__main__":
    main()
