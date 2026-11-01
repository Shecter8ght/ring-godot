"""Цевьё Dolinskyi: маски вместо мазков кистью автора ролика (Python API Painter мазки не рисует). Каждому пикселю
развёртки 2K — его точка на модели и нормаль (растр треугольников low-poly из mesh_dump.py); по ним — места и рисунки:

    decal_mask      надписи и номера планок (у автора — PSD с автообновлением): «VARN-DEFENSE  QR-7» на боку
                    верхней планки со стороны −Y, номера L/R/U/B в каждом втором пазу, повёрнуты на 90°
    milling_lines   следы фрезы вдоль планок и площадок («milling» / «lines» в папке Height/Normal)
    milling_arcs    дуги торцевой фрезы на площадках гнёзд QD и торцах
    contact_clean   где трутся и пыли нет: верх зубьев, верхние кромки, наружные грани площадок, торцы
    rail_wear       следы креплений обвесов на планках (у автора — фото износа, Levels, контраст)
    rail_zones      планки целиком (для царапин только на них)
    circles         кольцевые следы в гнёздах QD и вокруг них
    chips           точки сколов на выступах, где цевьё бьётся (основа «edge damage»)
    spots_matte     контрастные матовые пятна (у автора — альфы кистью)
    spots_gloss     контрастные глянцевые пятна
    oil             засохшее масло у корней планок и концов окон

Рисунки пятен — CC0 ambientCG и маски владельца «Маски_АЛЬФА». Белое — эффект.
    python -X utf8 tools/handguard_dolinskyi/masks.py [имя …]
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from dims import *  # noqa: E402,F401,F403

ROOT = HERE.parents[1]
OUT = ROOT / "_asset_src" / "handguard_dolinskyi" / "masks"
LIB = Path("E:/Models Blender/Маски_АЛЬФА")
CC0 = LIB / "50_Скачанные_CC0_ambientCG_ShareTextures" / "ambientCG"
FONT = Path("D:/ПРОГРАММЫ/python/Lib/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf")
RES = 2048
PAD_PX = 10
RNG = np.random.default_rng(1101)
TEXT = ("VARN-DEFENSE", "QR-7")       # вымышленная маркировка вместо «FAB-DEFENSE  NFR-RS»


# ---------- растр развёртки ----------

def rasterize():
    d = np.load(OUT / "mesh.npz")
    uv, pos, nrm = d["uv"], d["pos"], d["nrm"]
    P = np.zeros((RES, RES, 3), np.float32)
    N = np.zeros((RES, RES, 3), np.float32)
    cov = np.zeros((RES, RES), bool)
    px = uv[..., 0] * RES - 0.5
    py = (1.0 - uv[..., 1]) * RES - 0.5
    for t in range(len(uv)):
        x, y = px[t], py[t]
        x0, x1 = max(0, int(math.floor(x.min()))), min(RES - 1, int(math.ceil(x.max())))
        y0, y1 = max(0, int(math.floor(y.min()))), min(RES - 1, int(math.ceil(y.max())))
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1, dtype=np.float32), np.arange(y0, y1 + 1, dtype=np.float32))
        det = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
        if abs(det) < 1e-12:
            continue
        w0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / det
        w1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / det
        w2 = 1.0 - w0 - w1
        ins = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not ins.any():
            continue
        iy, ix = gy[ins].astype(int), gx[ins].astype(int)
        w = np.stack([w0[ins], w1[ins], w2[ins]], 1)
        P[iy, ix] = w @ pos[t]
        N[iy, ix] = w @ nrm[t]
        cov[iy, ix] = True
    N /= np.maximum(np.linalg.norm(N, axis=2, keepdims=True), 1e-9)
    # отступ: пустые пиксели у островов — значения ближайшего острова (как dilation при запекании)
    dist, (iy, ix) = ndimage.distance_transform_edt(~cov, return_indices=True)
    near = (~cov) & (dist <= PAD_PX)
    P[near] = P[iy[near], ix[near]]
    N[near] = N[iy[near], ix[near]]
    return P, N, cov | near


# ---------- помощники ----------

def save(name, a, blur=0.0):
    a = np.clip(a, 0.0, 1.0)
    if blur:
        a = ndimage.gaussian_filter(a, blur)
    Image.fromarray((a * 255 + 0.5).astype(np.uint8), "L").save(OUT / f"{name}.png")
    print("MASK", name, f"покрытие {float((a > 0.5).mean()) * 100:.1f} %, среднее {float(a.mean()):.3f}")


def noise(P, cell_mm, seed, octaves=3):
    """Объёмный шум по точкам модели (значение в 0..1): не зависит от швов развёртки."""
    rng = np.random.default_rng(seed)
    out = np.zeros(P.shape[:2], np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        c = cell_mm / (2 ** o)
        k = rng.normal(size=(3, 3)) * 2 * math.pi / c
        ph = rng.uniform(0, 2 * math.pi, 3)
        v = sum(np.sin(P @ k[i] + ph[i]) for i in range(3)) / 3
        out += amp * v
        tot += amp
        amp *= 0.55
    return 0.5 + 0.5 * out / tot


def polar(P):
    y, z = P[..., 1], P[..., 2]
    return np.sqrt(y * y + z * z), np.degrees(np.arctan2(z, y))


def rail_local(P, side):
    """Локальные координаты планки: u — поперёк (мм от середины), h — глубина от верха зуба (0 — верх)."""
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    if side == "top":
        return y, TOP_CREST - z, (x >= TOP_X[0] - 0.1) & (x <= TOP_X[1] + 0.1)
    if side == "bot":
        return y, BOT_CREST + z, (x >= BOT_X[0] - 0.1) & (x <= BOT_X[1] + 0.1)
    if side == "L":           # сторона −Y
        return z, SIDE_CREST + y, (x >= SIDE_X[0] - 0.1) & (x <= SIDE_X[1] + 0.1)
    return z, SIDE_CREST - y, (x >= SIDE_X[0] - 0.1) & (x <= SIDE_X[1] + 0.1)


RAIL_X = {"top": TOP_X, "bot": BOT_X, "L": SIDE_X, "R": SIDE_X}
RAIL_N = {"top": (0, 0, 1), "bot": (0, 0, -1), "L": (0, -1, 0), "R": (0, 1, 0)}


def in_rail(P, side, depth=8.5):
    u, h, xin = rail_local(P, side)
    return xin & (np.abs(u) <= RAIL_V_HW + 0.2) & (h >= -0.2) & (h <= depth)


def groove_dx(x, side):
    """Расстояние вдоль X до ближайшей стенки паза (мм) и признак «в пазу»."""
    xs = np.array(slot_starts(*RAIL_X[side]))
    edges = np.concatenate([xs, xs + SLOT_W])
    dx = np.min(np.abs(x[..., None] - edges[None, None, :]), axis=-1)
    ing = np.zeros(x.shape, bool)
    for a in xs:
        ing |= (x >= a) & (x <= a + SLOT_W)
    return dx, ing


# ---------- надписи ----------

def text_image(text, cap_mm, ppm=60):
    font = ImageFont.truetype(str(FONT), size=int(cap_mm * ppm / 0.73))
    l, t, r, b = font.getbbox(text)
    img = Image.new("L", (r - l + 8, b - t + 8), 0)
    ImageDraw.Draw(img).text((4 - l, 4 - t), text, fill=255, font=font)
    return np.asarray(img, np.float32) / 255.0, ppm


def decal(mask, P, N, cov, text, cap_mm, origin, U, V, Nd, spacing=1.0):
    U, V, Nd = (np.array(a, np.float32) for a in (U, V, Nd))
    assert np.allclose(np.cross(U, V), Nd), (text, U, V, Nd)
    img, ppm = text_image(text, cap_mm)
    if spacing != 1.0:
        img = np.asarray(Image.fromarray((img * 255).astype(np.uint8)).resize(
            (int(img.shape[1] * spacing), img.shape[0]), Image.LANCZOS), np.float32) / 255.0
    h, w = img.shape
    d = P - np.array(origin, np.float32)
    on = cov & (N @ Nd > 0.8) & (np.abs(d @ Nd) < 0.5)
    u = d @ U
    v = d @ V
    ix = (w / 2 + u * ppm)
    iy = (h / 2 - v * ppm)
    ok = on & (ix >= 0) & (ix < w - 1) & (iy >= 0) & (iy < h - 1)
    vals = ndimage.map_coordinates(img, [iy[ok], ix[ok]], order=1)
    mask[ok] = np.maximum(mask[ok], vals)


def make_decals(P, N, cov):
    m = np.zeros((RES, RES), np.float32)
    # маркировка — на боку верхней планки (плоская грань между трубой и подрезом «ласточкина хвоста», фото 3:16)
    zc = 0.5 * (math.sqrt(R_OUT ** 2 - RAIL_TOP_HW ** 2) + TOP_CREST - 2 * RAIL_V_D)
    decal(m, P, N, cov, TEXT[0], 2.4, (82.0, -RAIL_TOP_HW, zc), (1, 0, 0), (0, 0, 1), (0, -1, 0), spacing=1.15)
    decal(m, P, N, cov, TEXT[1], 2.4, (117.0, -RAIL_TOP_HW, zc), (1, 0, 0), (0, 0, 1), (0, -1, 0), spacing=1.15)
    # номера в каждом втором пазу (у реального NFR — на дне паза, повёрнуты на 90°, читаются снизу вверх)
    spec = {"L": ("L", (0, -(SIDE_CREST - SLOT_D), 0), (0, 0, 1), (-1, 0, 0), (0, -1, 0)),
            "R": ("R", (0, SIDE_CREST - SLOT_D, 0), (0, 0, 1), (1, 0, 0), (0, 1, 0)),
            "top": ("U", (0, 0, TOP_CREST - SLOT_D), (0, 1, 0), (-1, 0, 0), (0, 0, 1)),
            "bot": ("B", (0, 0, -(BOT_CREST - SLOT_D)), (0, 1, 0), (1, 0, 0), (0, 0, -1))}
    for side, (letter, o, U, V, Nd) in spec.items():
        for k, xs in enumerate(slot_starts(*RAIL_X[side])):
            if k % 2:
                continue
            org = np.array(o, np.float32)
            org[0] = xs + SLOT_W / 2
            decal(m, P, N, cov, f"{letter} {k + 1}", 3.1, org, U, V, Nd, spacing=1.05)
    save("decal_mask", m)


# ---------- следы обработки ----------

def make_milling(P, N, cov):
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    nx = np.abs(N[..., 0])
    rails = np.zeros(x.shape, bool)
    for s in ("top", "bot", "L", "R"):
        rails |= in_rail(P, s)
    pads = np.zeros(x.shape, bool)
    for a, b in PADS:
        pads |= (x >= a - 0.1) & (x <= b + 0.1) & (np.abs(z) <= PAD_HZ + 0.2) & (np.abs(y) >= 18.0)
    # риски вдоль X на гранях, параллельных оси (бока и верх зубьев, бока площадок): прямые, шаг 0.8 мм (шаг фрезы),
    # мягкий синус; сила меняется полосами — фреза шла несколькими проходами. Раньше фаза шла «волной» по шуму и риски
    # выходили острыми (cos³): волнистые горизонтали, «слоистость», как у 3D-печати (владелец 01.11)
    cross = np.where(np.abs(N[..., 1]) > np.abs(N[..., 2]), z, y)
    pitch = 0.8
    lines = 0.5 + 0.5 * np.cos(2 * math.pi * cross / pitch)
    band = np.clip((noise(P, 18.0, 4, 2) - 0.3) * 2.0, 0, 1)
    holes = np.zeros(x.shape, bool)       # стенки гнёзд QD — сверлёные: прямые риски легли бы на цилиндр кольцами
    for a, b in PADS:
        holes |= np.sqrt((x - (a + b) / 2) ** 2 + z ** 2) < HOLE_R + 0.3
    sel = (rails | pads) & (nx < 0.3) & ~holes
    save("milling_lines", np.where(sel, lines * band * 0.6, 0.0))
    # дуги торцевой фрезы: на наружных гранях площадок (центр фрезы сбоку) и на торцах
    face = pads & (np.abs(np.abs(y) - PAD_FACE) < 0.3) & (np.abs(N[..., 1]) > 0.8)
    arcs = np.zeros(x.shape, np.float32)
    for a, b in PADS:
        c = np.array([(a + b) / 2 - 22.0, 6.0])
        rr = np.sqrt((x - c[0]) ** 2 + (z - c[1]) ** 2)
        m = face & (x >= a - 0.1) & (x <= b + 0.1)
        arcs[m] = (0.5 + 0.5 * np.cos(2 * math.pi * rr[m] / 0.8)) ** 3
    ends = cov & (nx > 0.8) & ((x < LIP_X[1] + 0.6) | (x > BODY_X[1] - 0.6))
    r, _ = polar(P)
    arcs[ends] = (0.5 + 0.5 * np.cos(2 * math.pi * r[ends] / 0.7)) ** 3 * 0.8
    save("milling_arcs", arcs * (0.6 + 0.4 * noise(P, 6.0, 5, 2)))


# ---------- места касаний и износа ----------

def make_contact(P, N, cov):
    """Где трутся (руки, кобура, стол, обвес) — пыль и грязь вычищены, кромки светлее."""
    x = P[..., 0]
    out = np.zeros(x.shape, np.float32)
    for s in ("top", "bot", "L", "R"):
        u, h, xin = rail_local(P, s)
        r = in_rail(P, s, 3.5)
        top = r & (h < 0.25)
        upper = r & (h < RAIL_V_D + 0.3)
        out = np.maximum(out, np.where(top, 1.0, 0.0))
        out = np.maximum(out, np.where(upper, 0.6, 0.0))
    y = np.abs(P[..., 1])
    out = np.maximum(out, np.where(cov & (np.abs(y - PAD_FACE) < 0.25) & (np.abs(N[..., 1]) > 0.8), 0.85, 0.0))
    out = np.maximum(out, np.where(cov & ((x < 0.6) | (x > 176.4)), 0.7, 0.0))
    save("contact_clean", out * (0.75 + 0.25 * noise(P, 5.0, 7)), blur=1.2)


MOUNTS = (("top", 16.0, 72.0), ("top", 146.0, 177.0), ("L", 108.0, 142.0), ("bot", 52.0, 104.0), ("R", 24.0, 48.0))


def make_rail_wear(P, N, cov):
    x = P[..., 0]
    out = np.zeros(x.shape, np.float32)
    zones = np.zeros(x.shape, np.float32)
    for s in ("top", "bot", "L", "R"):
        zones = np.maximum(zones, np.where(in_rail(P, s, 6.0), 1.0, 0.0))
    for k, (s, a, b) in enumerate(MOUNTS):
        u, h, xin = rail_local(P, s)
        r = in_rail(P, s, 3.4) & (x >= a) & (x <= b)
        dx, ing = groove_dx(x, s)
        crest = r & (h < 0.25)
        edge = np.exp(-dx / 0.5) * (h < SLOT_D + 0.2)            # кромки пазов — там упирается поперечина крепления
        apex = np.exp(-np.abs(np.abs(u) - RAIL_V_HW) / 0.45)      # вершины «ласточкина хвоста» — там зажимает
        fade = np.clip(np.minimum(x - a, b - x) / 3.0, 0, 1)      # у концов крепления — резкий край пятна
        mot = noise(P, 2.5, 20 + k, 3)
        v = np.where(r, np.clip(0.25 * crest + 0.8 * edge + 0.9 * apex, 0, 1) * (0.45 + 0.75 * mot) * fade, 0.0)
        out = np.maximum(out, v)
    save("rail_wear", out, blur=0.6)
    save("rail_zones", zones, blur=0.8)


def make_circles(P, N, cov):
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    out = np.zeros(x.shape, np.float32)
    for a, b in PADS:
        xc = (a + b) / 2
        rho = np.sqrt((x - xc) ** 2 + z ** 2)
        wall = cov & (rho < HOLE_R + 0.25) & (np.abs(y) > 17.5) & (np.abs(N[..., 1]) < 0.4)
        # кольца от защёлки антабки QD: несколько неровных колец там, где шарики ходят по стенке, а не частая
        # «резьба» (шаг 0,6 мм на полную силу читался слоями, владелец 01.11)
        depth = np.abs(y[wall])
        v = np.zeros(depth.shape, np.float32)
        for _ in range(4):
            d0, w, k = RNG.uniform(20.5, 25.5), RNG.uniform(0.15, 0.35), RNG.uniform(0.35, 1.0)
            v = np.maximum(v, k * np.exp(-((depth - d0) / w) ** 2))
        out[wall] = v
        # у входа — притёртый поясок шириной ~1,5 мм, без полос
        ring = cov & (np.abs(np.abs(y) - PAD_FACE) < 0.3) & (rho >= HOLE_R) & (rho < HOLE_R + 1.6)
        fade = np.clip(1.0 - (rho - HOLE_R) / 1.6, 0, 1)
        out[ring] = np.maximum(out[ring], 0.5 * fade[ring])
    save("circles", out * (0.6 + 0.4 * noise(P, 3.0, 31)))


def make_chips(P, N, cov):
    """Точки сколов: только на выступах, куда приходится удар (концы, нижняя планка, наружные кромки зубьев)."""
    x = P[..., 0]
    cand = np.zeros(x.shape, np.float32)
    for s, wgt in (("bot", 1.0), ("L", 0.6), ("R", 0.6), ("top", 0.45)):
        u, h, xin = rail_local(P, s)
        dx, ing = groove_dx(x, s)
        r = in_rail(P, s, 1.2) & ~ing
        cand = np.maximum(cand, np.where(r & ((dx < 0.6) | (np.abs(np.abs(u) - RAIL_TOP_HW) < 0.5)), wgt, 0.0))
    ends = cov & ((x < 1.0) | (x > 175.8) | ((x > BODY_X[1] - 0.8) & (x < BODY_X[1] + 0.2)))
    cand = np.maximum(cand, np.where(ends, 1.0, 0.0))
    pads = cov & (np.abs(np.abs(P[..., 1]) - PAD_FACE) < 0.6) & (np.abs(np.abs(P[..., 2]) - PAD_HZ) < 0.8)
    cand = np.maximum(cand, np.where(pads, 0.8, 0.0))
    iy, ix = np.nonzero(cand > 0)
    w = cand[iy, ix]
    pick = RNG.choice(len(iy), size=260, replace=False, p=w / w.sum())
    out = np.zeros(x.shape, np.float32)
    for i in pick:
        c = P[iy[i], ix[i]]
        rad = RNG.uniform(0.15, 0.55) if RNG.random() < 0.85 else RNG.uniform(0.6, 1.1)
        d = np.linalg.norm(P - c, axis=2)
        blob = np.clip(1.0 - d / rad, 0, 1)
        out = np.maximum(out, (blob > 0) * np.clip(blob * 3.0 * (0.6 + 0.6 * noise(P, rad * 2, int(i))), 0, 1))
    save("chips", out)


# ---------- пятна альфами ----------

def load_alpha(path, size=512, invert=False):
    im = Image.open(path).convert("L")
    a = np.asarray(im, np.float32) / 255.0
    if invert:
        a = 1.0 - a
    lo, hi = np.percentile(a, 2), np.percentile(a, 99.5)
    a = np.clip((a - lo) / max(hi - lo, 1e-3), 0, 1)
    return a


def crop(a, frac):
    h, w = a.shape
    s = int(min(h, w) * frac)
    y0 = RNG.integers(0, h - s)
    x0 = RNG.integers(0, w - s)
    c = a[y0:y0 + s, x0:x0 + s]
    yy, xx = np.mgrid[0:s, 0:s] / max(s - 1, 1) - 0.5
    return c * np.clip(1.0 - (np.sqrt(xx * xx + yy * yy) / 0.5) ** 4, 0, 1)   # края штампа — в ноль


def stamp(out, P, N, cov, img, center, normal, size_mm, rot):
    n = normal / np.linalg.norm(normal)
    t1 = np.cross(n, [1.0, 0.0, 0.0])
    if np.linalg.norm(t1) < 0.3:
        t1 = np.cross(n, [0.0, 0.0, 1.0])
    t1 /= np.linalg.norm(t1)
    t2 = np.cross(n, t1)
    c, s = math.cos(rot), math.sin(rot)
    t1, t2 = c * t1 + s * t2, -s * t1 + c * t2
    d = P - center
    near = cov & (np.abs(d).max(axis=2) < size_mm * 0.75) & (N @ n > 0.35)
    if not near.any():
        return
    u = d[near] @ t1 / size_mm + 0.5
    v = d[near] @ t2 / size_mm + 0.5
    h, w = img.shape
    ok = (u >= 0) & (u < 1) & (v >= 0) & (v < 1)
    vals = np.zeros(u.shape, np.float32)
    vals[ok] = ndimage.map_coordinates(img, [v[ok] * (h - 1), u[ok] * (w - 1)], order=1)
    out[near] = np.maximum(out[near], vals)


def outer_points(P, N, cov, step=3):
    r, _ = polar(P)
    nr = (P[..., 1] * N[..., 1] + P[..., 2] * N[..., 2]) / np.maximum(r, 1e-6)
    ok = cov & (r > R_IN + 1.0) & ((nr > 0.5) | (np.abs(N[..., 0]) > 0.8))
    iy, ix = np.nonzero(ok[::step, ::step])
    return iy * step, ix * step


def scatter(name, P, N, cov, sources, count, size_range, where=None, frac=(0.35, 0.7)):
    iy, ix = outer_points(P, N, cov)
    if where is not None:
        keep = where[iy, ix]
        iy, ix = iy[keep], ix[keep]
    alphas = [load_alpha(p, invert=inv) for p, inv in sources]
    out = np.zeros(P.shape[:2], np.float32)
    for k in range(count):
        i = RNG.integers(len(iy))
        img = crop(alphas[k % len(alphas)], RNG.uniform(*frac))
        stamp(out, P, N, cov, img, P[iy[i], ix[i]], N[iy[i], ix[i]], RNG.uniform(*size_range),
              RNG.uniform(0, 2 * math.pi))
    save(name, out)


def make_spots(P, N, cov):
    x = P[..., 0]
    gloss = [(CC0 / "Fingerprints001" / "Fingerprints001_2K-PNG_Opacity.png", False),
             (CC0 / "Fingerprints004" / "Fingerprints004_2K-PNG_Opacity.png", False),
             (LIB / "06_Разводы_и_следы_протирания" / "Разводы_редкие_01.png", False),
             (CC0 / "Smear002" / "Smear002_2K-JPG_Roughness.jpg", True)]
    matte = [(LIB / "05_Брызги_и_высохшие_капли" / "Капли_тонкие_контуры_01.png", False),
             (LIB / "05_Брызги_и_высохшие_капли" / "Брызги_средние_01.png", False),
             (LIB / "03_Пыль_и_частицы" / "Пыль_пятнами_01.png", False)]
    oil = [(LIB / "20_Масляные_плёнки_и_смазка" / f, False)
           for f in ("Масло_05_Капля_размазанная.png", "Масло_08_Рваный_мазок.png", "Масло_02_Разбитые_островки.png")]
    scatter("spots_gloss", P, N, cov, gloss, 26, (4.0, 11.0))
    scatter("spots_matte", P, N, cov, matte, 22, (2.5, 7.0), frac=(0.25, 0.5))
    # масло — у корней планок, у концов окон и в нижней половине (стекает)
    r, th = polar(P)
    roots = np.zeros(x.shape, bool)
    for s in ("top", "bot", "L", "R"):
        u, h, xin = rail_local(P, s)
        roots |= xin & (np.abs(u) < RAIL_V_HW + 3.5) & (h > 4.5) & (h < 10.5)
    scatter("oil", P, N, cov, oil, 12, (5.0, 13.0), where=roots | (P[..., 2] < -12.0))


EXT = {"ext_smear004": ("Smear004/Smear004_2K-JPG_Roughness.jpg", True),
       "ext_smear007": ("Smear007/Smear007_2K-PNG_Opacity.png", False),
       "ext_scratches001": ("Scratches001/Scratches001_2K-PNG_Opacity.png", False),
       "ext_scratches003": ("Scratches003/Scratches003_2K-PNG_Opacity.png", False)}


def make_ext(P=None, N=None, cov=None):
    """Карты CC0 (ambientCG) в проект: ч/б, растянутые уровни (у ambientCG маски тусклые, среднее 0.2–0.3)."""
    for name, (rel, inv) in EXT.items():
        a = load_alpha(CC0 / rel, invert=inv)
        Image.fromarray((a * 255 + 0.5).astype(np.uint8), "L").save(OUT / f"{name}.png")
        print("EXT", name, rel)
    (OUT / "license.txt").write_text(
        "ext_*.png — CC0 1.0, ambientCG (https://ambientcg.com, https://docs.ambientcg.com/license/): "
        + ", ".join(r.split("/")[0] for r, _ in EXT.values()) + ".\n"
        "Через «Маски_АЛЬФА/50_Скачанные_CC0_ambientCG_ShareTextures» владельца (скачаны 2026-10-30).\n"
        "Остальные маски и dirt_albedo.png — свои (tools/handguard_dolinskyi/masks.py), рисунки пятен — из тех же CC0\n"
        "и масок владельца «Маски_АЛЬФА» (06_Разводы, 05_Брызги, 03_Пыль, 20_Масляные плёнки).\n", encoding="utf-8")


def make_dirt_albedo(P=None, N=None, cov=None):
    """Фото грязи для засохшего масла (у автора — dirt_albedo: «любая контрастная текстура с цветовыми вариациями,
    хоть фото стены с желтоватыми пятнами»). Пока нет фото по промпту 5 — своя: охра, бурый, серый, тёмные крапины."""
    rng = np.random.default_rng(77)
    h = w = 1024

    def octave(cells):
        g = rng.random((cells, cells)).astype(np.float32)
        g = np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
        return g
    n = sum(octave(c) * a for c, a in ((6, 0.5), (18, 0.25), (60, 0.15), (220, 0.1)))
    n = (n - n.min()) / (n.max() - n.min())
    pal = np.array([[0.16, 0.14, 0.11], [0.30, 0.24, 0.14], [0.45, 0.36, 0.20], [0.36, 0.34, 0.30]], np.float32)
    t = np.clip(n * 3.0, 0, 2.999)
    i = t.astype(int)
    f = (t - i)[..., None]
    col = pal[i] * (1 - f) + pal[np.minimum(i + 1, 3)] * f
    specks = (octave(400) > 0.86)[..., None]
    col = np.where(specks, col * 0.45, col)
    Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8), "RGB").save(OUT / "dirt_albedo.png")
    print("DIRT dirt_albedo.png")


def make_spots2(P, N, cov):
    """Второй набор контрастных пятен — для верхних «glossy» / «matte» (у автора отдельные слои поверх всего)."""
    global RNG
    RNG = np.random.default_rng(2202)
    gloss = [(CC0 / "Fingerprints004" / "Fingerprints004_2K-PNG_Opacity.png", False),
             (LIB / "06_Разводы_и_следы_протирания" / "Протирание_по_диагонали_01.png", False)]
    matte = [(LIB / "05_Брызги_и_высохшие_капли" / "Брызги_средние_01.png", False),
             (LIB / "03_Пыль_и_частицы" / "Пыль_редкая_01.png", False)]
    scatter("spots_gloss2", P, N, cov, gloss, 12, (3.0, 7.0))
    scatter("spots_matte2", P, N, cov, matte, 12, (2.0, 5.0), frac=(0.25, 0.45))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])
    cache = OUT / "maps.npz"
    if only and cache.exists():
        d = np.load(cache)
        P, N, cov = d["P"].astype(np.float32), d["N"].astype(np.float32), d["cov"]
    else:
        P, N, cov = rasterize()
        np.savez_compressed(cache, P=P, N=N.astype(np.float16), cov=cov)
    jobs = {"decals": make_decals, "milling": make_milling, "contact": make_contact, "rail_wear": make_rail_wear,
            "circles": make_circles, "chips": make_chips, "spots": make_spots, "ext": make_ext,
            "dirt_albedo": make_dirt_albedo, "spots2": make_spots2}
    for k, fn in jobs.items():
        if not only or k in only:
            fn(P, N, cov)


if __name__ == "__main__":
    main()
