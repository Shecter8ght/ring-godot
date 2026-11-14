"""Дом 7 «Проспекта», игровые карты (system Python: numpy + PIL) → assets/textures/prospekt_houses.
  python -X utf8 tools/prospekt_houses/game_textures.py

Общие фото-наборы Poly Haven уже лежат в assets/textures/<id> (concrete_wall_007, painted_plaster_wall, plywood, tarred_gravel,
mud_forest) — шейдер дома берёт их как есть, тон и контраст задаются параметрами материала (как tint_lum в materials.py).
Здесь — только то, чего в проекте ещё нет:
  metal_dark_*  — Metal063 (ambientCG, CC0): albedo, normal (GL), orm (R — AO 1, G — шероховатость, B — металл);
  metal_light_* — Metal052A (ambientCG, CC0): то же;
  conc_height   — высота бетона concrete_wall_007 для parallax occlusion (из карты нормалей — Пуассон по БПФ, как prep_textures.py);
  perf_alpha    — перфорация (шахматный шаг 24 мм, плитка 0,96 м; белое — металл), копия карты материалов v01;
  notice        — лист «ПОДЪЕЗД ЗАКРЫТ» (gen_notice.py), уменьшенный;
  m_marble, m_plaque, m_grain, m_streak, m_crack — фото-маски владельца (Маски_АЛЬФА) для крупной неоднородности и рисунка грязи;
  curtains      — атлас штор 4 × 1 (2048 × 1024): задёрнуты две, собраны по краям, тюль, вертикальные жалюзи; RGB — ткань с
                  тенью складок (тон шейдер красит по номеру окна), A — плотность (тюль ~0,55, щели жалюзи — 0).
Складки — та же функция, что fold_panel() в house7_finish.py (сумма неравных синусов), освещена сбоку; ткань — Fabric034.
"""
import math
import os
import shutil

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "_asset_src", "textures")
LIB = "E:/Models Blender/ENVIRONMENT/RING_Prospekt_Houses/textures"
OUT = os.path.join(ROOT, "assets", "textures", "prospekt_houses")


def rgb(path, size):
    return np.asarray(Image.open(path).convert("RGB").resize((size, size), Image.LANCZOS)).astype(np.float32) / 255.0


def gray(path, size):
    return np.asarray(Image.open(path).convert("L").resize((size, size), Image.LANCZOS)).astype(np.float32) / 255.0


def save_rgb(a, name, q=92):
    im = Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))
    p = os.path.join(OUT, name)
    if name.endswith(".webp"):
        im.save(p, quality=q, method=6)
    else:
        im.save(p)
    return p


def metal_set(key, folder):
    d = os.path.join(SRC, folder)
    s = 2048
    alb = rgb(os.path.join(d, "color_2k.jpg"), s)
    nrm = rgb(os.path.join(d, "normal_2k.jpg"), s)           # ambientCG: в папке NormalGL (OpenGL, как у Godot)
    rough = gray(os.path.join(d, "roughness_2k.jpg"), s)
    metal = gray(os.path.join(d, "metalness_2k.jpg"), s)
    save_rgb(alb, key + "_albedo.webp", 92)
    save_rgb(nrm, key + "_normal.png")
    orm = np.stack([np.ones_like(rough), rough, metal], -1)
    save_rgb(orm, key + "_orm.webp", 95)


def height_from_normal(nrm):
    n = nrm * 2.0 - 1.0
    nz = np.maximum(n[..., 2], 0.2)
    gx = -n[..., 0] / nz
    gy = n[..., 1] / nz
    h, w = gx.shape
    kx = np.fft.fftfreq(w)[None, :] * 2 * np.pi
    ky = np.fft.fftfreq(h)[:, None] * 2 * np.pi
    den = kx ** 2 + ky ** 2
    den[0, 0] = 1.0
    H = (1j * kx * np.fft.fft2(gx) + 1j * ky * np.fft.fft2(gy)) / (-den)
    H[0, 0] = 0
    r = np.real(np.fft.ifft2(H))
    lo, hi = np.percentile(r, 1), np.percentile(r, 99)
    return np.clip((r - lo) / (hi - lo + 1e-9), 0, 1)


def fold_profile(x, folds, amp, seed):
    """Смещение шторы поперёк окна, как fold_panel(): сумма трёх неравных синусов, x — 0…1 по ширине полотна."""
    rnd = np.random.default_rng(seed)
    ph = rnd.uniform(0, math.tau, 3)
    k = folds * math.tau
    return amp * (np.sin(x * k + ph[0]) * 0.6 + np.sin(x * k * 1.73 + ph[1]) * 0.28 + np.sin(x * k * 0.47 + ph[2]) * 0.22)


def drape(w, h, x0, x1, folds, amp, seed, fabric, tulle=False):
    """Полотно шторы между долями ширины x0…x1: тень складок (производная смещения — сбоку свет), ткань, низ чуть неровный."""
    col = np.zeros((h, w, 3), np.float32)
    alpha = np.zeros((h, w), np.float32)
    xa, xb = int(x0 * w), int(x1 * w)
    if xb - xa < 4:
        return col, alpha
    xs = np.linspace(0, 1, xb - xa)
    d = fold_profile(xs, folds, amp, seed)
    slope = np.gradient(d, xs) / max(1e-6, amp * folds * math.tau)
    shade = np.clip(0.80 + 0.32 * slope, 0.45, 1.12)
    hem = (np.sin(xs * folds * math.tau * 1.3 + seed) * 0.006 + 0.985)            # подол неровный
    fab = fabric[:h, xa:xb]
    lum = fab.mean(-1, keepdims=True)
    lum = 1.0 + (lum / max(1e-6, lum.mean()) - 1.0) * 0.5
    col[:, xa:xb] = (shade[None, :, None] * lum)
    vv = np.linspace(0, 1, h)[:, None]
    a = (vv < hem[None, :]).astype(np.float32)
    if tulle:
        a *= 0.42 + 0.25 * fabric[:h, xa:xb, 0] / max(1e-6, fabric[..., 0].mean()) * 0.5
        col[:, xa:xb] = np.clip(col[:, xa:xb] * 1.05, 0, 1.2)
    alpha[:, xa:xb] = a
    return col, alpha


def curtains():
    tw, th = 512, 1024
    fab = gray(os.path.join(SRC, "Fabric034", "color_2k.jpg"), 2048)
    fab = np.repeat(np.tile(fab, (1, 1))[:th, :, None], 3, -1)
    atlas = np.zeros((th, tw * 4, 4), np.float32)
    # 0 — задёрнуты две половины (вариант «a»)
    c1, a1 = drape(tw, th, 0.0, 0.495, 4, 0.03, 11, fab)
    c2, a2 = drape(tw, th, 0.505, 1.0, 4, 0.03, 12, fab)
    t0 = (c1 + c2, np.maximum(a1, a2))
    # 1 — собраны по краям (окна «c», лоджии «b», «c»)
    c1, a1 = drape(tw, th, 0.0, 0.2, 2, 0.05, 21, fab)
    c2, a2 = drape(tw, th, 0.8, 1.0, 2, 0.05, 22, fab)
    t1 = (c1 + c2, np.maximum(a1, a2))
    # 2 — тюль на всё окно («d»)
    t2 = drape(tw, th, 0.0, 1.0, 9, 0.012, 31, fab, tulle=True)
    # 3 — вертикальные жалюзи (окна «b»): ламели 89 мм с просветами, чуть повёрнуты — полосы светлее / темнее
    xs = np.linspace(0, 1, tw)
    lam = (xs * 26.0) % 1.0
    shade = 0.78 + 0.22 * np.cos(lam * math.pi)
    a3 = (lam < 0.9).astype(np.float32)
    col3 = np.repeat(np.repeat(shade[None, :, None], th, 0), 3, -1) * 0.95
    a3 = np.repeat(a3[None, :], th, 0)
    a3[int(th * 0.985):] = 0.0
    t3 = (col3, a3)
    for i, (c, a) in enumerate((t0, t1, t2, t3)):
        atlas[:, i * tw:(i + 1) * tw, :3] = np.clip(c, 0, 1)
        atlas[:, i * tw:(i + 1) * tw, 3] = a
    im = Image.fromarray((np.clip(atlas, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
    im.save(os.path.join(OUT, "curtains.png"))


def main():
    os.makedirs(OUT, exist_ok=True)
    metal_set("metal_dark", "Metal063")
    metal_set("metal_light", "Metal052A")
    print("metal ok")
    n = rgb(os.path.join(ROOT, "assets", "textures", "concrete_wall_007", "normal.jpg"), 2048)
    h = height_from_normal(n)
    Image.fromarray((h * 255 + 0.5).astype(np.uint8), "L").save(os.path.join(OUT, "conc_height.png"))
    print("height ok")
    Image.open(os.path.join(LIB, "perf_alpha.png")).convert("L").resize((1024, 1024), Image.LANCZOS).save(os.path.join(OUT, "perf_alpha.png"))
    Image.open(os.path.join(LIB, "notice.png")).convert("RGB").resize((512, 724), Image.LANCZOS).save(os.path.join(OUT, "notice.png"))
    for m in ("m_marble", "m_plaque", "m_grain", "m_streak", "m_crack"):
        Image.open(os.path.join(LIB, "masks", m + ".png")).convert("L").resize((1024, 1024), Image.LANCZOS).save(os.path.join(OUT, m + ".png"))
    curtains()
    print("done", OUT)


if __name__ == "__main__":
    main()
