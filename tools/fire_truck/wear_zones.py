"""Пожарная АЦ, этап 2: места износа и наклейки в развёртке наборов — по картам геометрии wear_maps.py.

Места (ч/б, 4096, 1 — след есть): рисунок следа кладёт Painter фото-масками CC0 (sp_truck_wear.py), эти карты только
говорят, где: верх, борта, низ, пороги и арки, передок, места рук и ног, ковры листвы.
Наклейки — «проекторы» в мировых координатах (центр, нормаль, верх, ширина, высота, глубина): пиксель развёртки
получает картинку, если он рядом с плоскостью проектора и смотрит в его сторону — поэтому граффити и надписи идут
через швы развёртки и с набора на набор без разрыва.

    python -X utf8 tools/fire_truck/wear_zones.py [набор …]
    → WORK/wear/zones/<набор>_<место>.png, WORK/wear/decals/<набор>_<наклейка>[_a|_metal|_rough].png, report.json

Места: up — грани к небу (пыль, выгорание, листья), vert — борта (потёки), down — низ граней (грязь снизу),
low — дорожная грязь (высота и арки колёс, брызги назад), sill — пороги, низ дверей и панелей, кромки арок
(ржавчина), front — передок и лобовые грани низа (сколы от камней), streak — потёки сверху бортов (от кромок крыши
и проёмов), traffic — ступени, поручни, ручки и пятна вокруг ручек (10 лет службы), leafmat — ковры прелой листвы
в углах горизонталей.
Наклейки: leaves, drops (+ drops_etch — эмаль под помётом выедена), graffiti (+ _metal у серебрянки), clean (стёрто
пальцем и ладонью: надписи, рисунок, ладони), ridge (валик пыли по краю надписи), hands (жирный след ладони).
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import tex_sets as T  # noqa: E402

WEAR = Path(T.WORK) / "wear"
GEO = WEAR / "geo"
SPR = WEAR / "sprites"
ZON = WEAR / "zones"
DEC = WEAR / "decals"
RES = 4096
EXTERIOR = {"cab_panels", "cab_parts", "body_L", "body_R", "body_parts", "shutters", "roof", "trim", "pump", "chassis",
            "wheels", "glass"}
PAINT = {"paint_red", "paint_white", "signal_yellow", "chassis_black"}
# детали, за которые берутся руками и на которые встают (10 лет службы): по началу имени
TRAFFIC_PARTS = ("step", "grab", "handle", "ladder", "rung", "tread", "kick", "footboard", "running_board", "pump_step")


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def noise3(P, cell, seed):
    """Гладкий шум по положению в мире (трилинейная решётка) — неровный край мест, одинаковый через швы."""
    rng = np.random.default_rng(seed)
    g = rng.random((64, 64, 64)).astype(np.float32)
    q = P / cell
    i = np.floor(q).astype(np.int64)
    f = (q - i).astype(np.float32)
    f = f * f * (3 - 2 * f)
    out = 0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2])
                out = out + w * g[(i[:, 0] + dx) % 64, (i[:, 1] + dy) % 64, (i[:, 2] + dz) % 64]
    return out


class SetMaps:
    def __init__(self, st, info):
        d = np.load(GEO / f"{st}.npz")
        self.st = st
        part = d["part"]
        self.valid = part > 0
        self.idx = np.flatnonzero(self.valid)
        lo = np.array(info["lo"], np.float32)
        self.P = d["pos"].reshape(-1, 3)[self.idx].astype(np.float32) / 65535 * np.float32(info["span"]) + lo
        n = d["nrm"].reshape(-1, 3)[self.idx].astype(np.float32) / 127
        self.N = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
        self.part = part.reshape(-1)[self.idx]
        names = info["sets"][st]
        self.names = {int(k): v[0] for k, v in names.items()}
        self.slots = {int(k): v[1] for k, v in names.items()}
        lut = np.zeros(int(self.part.max()) + 1, object)
        for k, v in self.slots.items():
            if k < len(lut):
                lut[k] = v
        self.slot = lut[self.part]
        self._hash = None

    def image(self, vals, fill=0.0, ch=1):
        out = np.full((RES * RES, ch) if ch > 1 else RES * RES, fill, np.float32)
        out[self.idx] = vals
        return out.reshape((RES, RES, ch) if ch > 1 else (RES, RES))

    def hashed(self, cell=0.2):
        if self._hash is None:
            q = np.floor(self.P / cell).astype(np.int64) + 512
            key = (q[:, 0] * 1024 + q[:, 1]) * 1024 + q[:, 2]
            order = np.argsort(key, kind="stable")
            self._hash = (cell, key[order], order)
        return self._hash

    def near(self, lo, hi):
        """Индексы пикселей (в self.P) внутри коробки [lo, hi] мира."""
        cell, keys, order = self.hashed()
        a = np.floor(np.array(lo) / cell).astype(np.int64) + 512
        b = np.floor(np.array(hi) / cell).astype(np.int64) + 512
        res = []
        for ix in range(a[0], b[0] + 1):
            for iy in range(a[1], b[1] + 1):
                k0 = (ix * 1024 + iy) * 1024 + a[2]
                k1 = (ix * 1024 + iy) * 1024 + b[2]
                i0, i1 = np.searchsorted(keys, k0), np.searchsorted(keys, k1, side="right")
                if i1 > i0:
                    res.append(order[i0:i1])
        if not res:
            return np.zeros(0, np.int64)
        sel = np.concatenate(res)
        p = self.P[sel]
        ok = np.all((p >= np.array(lo) - 1e-4) & (p <= np.array(hi) + 1e-4), axis=1)
        return sel[ok]


# ---------------------------------------------------------------------------------------------------------- места
_IMG = {}


def streak_img(key):
    """Рисунки потёков (фото CC0) для выборки по бортам: band — полосы, свисающие с кромки (ambientCG Leaking001,
    верхние 40 % картинки), drips — подтёки сверху вниз (SurfaceImperfections010, плитка), smear — разводы (Smear006,
    повёрнуты отвесно)."""
    if key not in _IMG:
        src = ROOT / "_asset_src" / "fire_truck_tex"
        if key == "band":
            im = cv2.imread(str(src / "ambientcg_Leaking001/Leaking001_8K-PNG_Opacity.png"), cv2.IMREAD_GRAYSCALE)
            im = cv2.resize(im, (2048, 1024), interpolation=cv2.INTER_AREA)
        elif key == "drips":
            im = cv2.resize(cv2.imread(str(WEAR / "masks/spots.png"), cv2.IMREAD_GRAYSCALE), (2048, 2048),
                            interpolation=cv2.INTER_AREA)
        else:
            im = cv2.resize(cv2.imread(str(WEAR / "masks/smear.png"), cv2.IMREAD_GRAYSCALE), (2048, 2048),
                            interpolation=cv2.INTER_AREA)
            im = cv2.rotate(im, cv2.ROTATE_90_CLOCKWISE)
        _IMG[key] = im.astype(np.float32) / 255
    return _IMG[key]


def vsample(key, P, N, ztop, pw, ph, seed, tile_v=False):
    """Отвесная выборка рисунка по борту: по горизонтали — вдоль борта (у граней к ±X это Y, к ±Y — X), по
    вертикали — от верхней кромки детали вниз (потёк начинается у кромки), у плитки — с повтором."""
    img = streak_img(key)
    off = np.random.default_rng(seed).random()
    h = np.where(np.abs(N[:, 0]) > np.abs(N[:, 1]), P[:, 1], P[:, 0])
    u = (h / pw + off) % 1.0
    v = (ztop - P[:, 2]) / ph
    v = v % 1.0 if tile_v else np.clip(v, 0, 0.999)
    return sample(img, u, v)


def zones(m: SetMaps, info, scatter):
    P, N = m.P, m.N
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    nz = N[:, 2]
    out = {}
    out["up"] = smooth(nz, 0.3, 0.85)
    out["vert"] = 1 - smooth(np.abs(nz), 0.35, 0.7)
    out["down"] = smooth(-nz, 0.3, 0.8)
    nn = noise3(P, 0.35, 1)
    # дорожная грязь: снизу вверх до ~1 м, у арок — пятном вокруг колеса, брызги назад сильнее
    low = 1 - smooth(z, 0.12 + 0.25 * nn, 0.85 + 0.35 * nn)
    wheels = [w for w in info["wheels"] if w["r"] > 0.3 and "rib" not in w["name"]]
    arch = np.zeros(len(P), np.float32)
    lip = np.zeros(len(P), np.float32)
    for w in wheels:
        cx, cy, cz = w["c"]
        r = w["r"]
        side = np.abs(x - cx) < w["w"] / 2 + 0.55
        d = np.sqrt((y - cy) ** 2 + (z - cz) ** 2)
        back = 0.6 + 0.4 * smooth(y - cy, -0.4, 0.5)            # перед — −Y: колесо бросает грязь назад и вверх
        arch = np.maximum(arch, side * (1 - smooth(d, r + 0.05, r + 0.55 + 0.2 * nn)) * back)
        lip = np.maximum(lip, side * (1 - smooth(np.abs(d - (r + 0.13)), 0.04, 0.14)) * (z > cz - 0.1))
    out["low"] = np.maximum(low, 0.9 * arch)
    # пороги и низ панелей: нижняя полоса машины, низ каждой крашеной детали, кромки арок
    paint = np.isin(m.slot, list(PAINT))
    # низ и верх детали — по 1 и 99 % высот её пикселей: редкие пиксели с чужим положением на краях островов
    # (сглаживание при запекании) раздували деталь, и полоса «низа» ложилась на всю узкую накладку
    zmin = np.zeros(int(m.part.max()) + 1, np.float32)
    zmax = np.zeros(int(m.part.max()) + 1, np.float32)
    order = np.argsort(m.part, kind="stable")
    bounds = np.searchsorted(m.part[order], np.arange(len(zmin) + 1))
    for k in range(1, len(zmin)):
        zz = z[order[bounds[k]:bounds[k + 1]]]
        if len(zz):
            zmin[k], zmax[k] = np.percentile(zz, [1, 99])
    band = 1 - smooth(z, 0.2 + 0.12 * nn, 0.55 + 0.15 * nn)
    bottom = (1 - smooth(z - zmin[m.part], 0.015, 0.06 + 0.06 * nn)) * smooth(zmax[m.part] - zmin[m.part], 0.15, 0.4)
    out["sill"] = np.clip(np.maximum.reduce([0.8 * band, 0.85 * bottom * (z < 1.8), lip]), 0, 1) * paint + \
        np.clip(band * 0.6 + lip, 0, 1) * ~paint
    # сколы от камней: передок кабины низом и лобовые грани низа за передними колёсами
    fwd = smooth(-N[:, 1], 0.3, 0.8)
    out["front"] = fwd * (1 - smooth(z, 0.4 + 0.3 * nn, 1.5 + 0.3 * nn)) * (0.5 + 0.5 * (y < -2.9))
    # потёки сверху бортов: от верхней кромки детали вниз ~1 м
    out["streak"] = out["vert"] * (0.3 + 0.7 * (1 - smooth(zmax[m.part] - z, 0.05, 1.1 + 0.4 * nn)))
    zt = zmax[m.part]
    band = vsample("band", P, N, zt, 1.8, 2.6, 3)                       # полосы с верхней кромки, ~1 м
    smear = vsample("smear", P, N, zt, 1.4, 1.4, 4, tile_v=True)
    out["streak_dirt"] = out["vert"] * np.clip(np.maximum(band, 0.45 * smear * out["streak"]), 0, 1)
    drips = vsample("drips", P, N, zt, 1.1, 1.1, 5, tile_v=True)
    out["streak_runs"] = out["vert"] * drips * (0.25 + 0.75 * (1 - smooth(zt - z, 0.05, 0.7)))
    # места рук и ног: детали по имени и пятна вокруг ручек на соседних панелях
    names = np.array([m.names.get(k, "") for k in range(int(m.part.max()) + 1)], object)
    is_tr = np.array([any(s in n.lower() for s in TRAFFIC_PARTS) for n in names])
    tr = is_tr[m.part].astype(np.float32)
    handles = [b for n, b in info["boxes"].items() if "handle" in n.lower() and "rail" not in n.lower()]
    near_h = np.zeros(len(P), np.float32)
    for lo_, hi_ in handles:
        c = (np.array(lo_) + np.array(hi_)) / 2
        d = np.linalg.norm(P - c, axis=1)
        near_h = np.maximum(near_h, 1 - smooth(d, 0.04, 0.16 + 0.05 * nn))
    out["traffic"] = np.maximum(tr * (0.55 + 0.45 * out["up"]), near_h * 0.9)
    # ковры прелой листвы — у листьев из «углов» (scatter: e — доля горизонта, закрытая в 0,5 м)
    mat = np.zeros(len(P), np.float32)
    for lf in scatter["leaves"]:
        if lf["e"] < 0.4:
            continue
        c = np.array(lf["p"], np.float32)
        r = 0.10 + 0.25 * (lf["e"] - 0.4)
        sel = m.near(c - r - 0.05, c + r + 0.05)
        if not len(sel):
            continue
        d = np.linalg.norm(P[sel] - c, axis=1) / r
        mat[sel] = np.maximum(mat[sel], (1 - smooth(d * (0.8 + 0.4 * nn[sel]), 0.4, 1.0)) * smooth(N[sel, 2], 0.3, 0.7))
    out["leafmat"] = mat
    # готовые места слоёв Painter (рисунок — фото-масками там): выгорание и налёт сильнее сверху, пыль — на
    # горизонталях и немного по бортам, сколы — передок, места рук и ног, пороги и понемногу везде, царапины службы
    inside = m.st in ("cab_interior", "crew_interior", "lockers")
    big = noise3(P, 0.9, 7)
    out["fade"] = np.clip(0.4 + 0.6 * out["up"], 0, 1) * (0.7 + 0.3 * big)
    # корма: за едущей машиной завихрение — задняя стенка в пыли сильнее бортов (по ней и пишут пальцем)
    rear = smooth(N[:, 1], 0.5, 0.85) * smooth(y, 3.2, 3.7)
    dust = np.clip(np.maximum(0.9 * out["up"] + 0.22 * out["vert"] * (1 - out["low"]), rear), 0, 1)
    out["dust"] = dust * (0.75 + 0.25 * big) * (0.55 if inside else 1.0)
    out["film"] = (0.3 if inside else 1.0) * np.clip(np.maximum(0.55 + 0.45 * out["up"], rear), 0, 1) * (0.8 + 0.2 * big)
    out["chips"] = np.clip(out["front"] + 0.6 * out["traffic"] + 0.2 * out["sill"] + 0.12, 0, 1)
    out["service"] = np.clip(0.2 + 0.8 * np.maximum(out["traffic"], out["front"]), 0, 1)
    out["rust_runs"] = out["streak_runs"] * (0.3 + 0.7 * (1 - smooth(z, 0.5, 1.5)))
    return out


# ---------------------------------------------------------------------------------------------------------- наклейки
def load_rgba(fn):
    im = cv2.imread(str(SPR / fn), cv2.IMREAD_UNCHANGED).astype(np.float32) / 255
    if im.ndim == 2:
        return im
    if im.shape[2] == 4:
        return np.dstack([im[..., 2], im[..., 1], im[..., 0], im[..., 3]])
    return im[..., ::-1]


def sample(img, u, v):
    """Билинейная выборка картинки в долях (u — вправо, v — вниз)."""
    h, w = img.shape[:2]
    fx = np.clip(u * (w - 1), 0, w - 1.001)
    fy = np.clip(v * (h - 1), 0, h - 1.001)
    x0 = fx.astype(np.int64)
    y0 = fy.astype(np.int64)
    ax = (fx - x0)[..., None] if img.ndim == 3 else fx - x0
    ay = (fy - y0)[..., None] if img.ndim == 3 else fy - y0
    a = img[y0, x0] * (1 - ax) + img[y0, x0 + 1] * ax
    b = img[y0 + 1, x0] * (1 - ax) + img[y0 + 1, x0 + 1] * ax
    return a * (1 - ay) + b * ay


def frame(n, up):
    n = np.array(n, np.float64)
    n /= np.linalg.norm(n)
    up = np.array(up, np.float64)
    b = up - up.dot(n) * n
    if np.linalg.norm(b) < 1e-4:
        b = np.array([0, 1.0, 0]) - n[1] * n
    b /= np.linalg.norm(b)
    r = np.cross(b, n)
    return n, r, b


def project(m: SetMaps, c, n, up, w, h, depth, facing):
    """Пиксели набора под проектором: индексы в m.P и координаты картинки (u вправо, v вниз)."""
    n, r, b = frame(n, up)
    c = np.array(c, np.float64)
    R = 0.5 * math.hypot(w, h) + depth
    sel = m.near(c - R, c + R)
    if not len(sel):
        return sel, None, None
    d = m.P[sel] - c
    dn = d @ n
    u = d @ r / w + 0.5
    v = 0.5 - d @ b / h
    ok = (np.abs(dn) < depth) & (m.N[sel] @ n > facing) & (u >= 0) & (u < 1) & (v >= 0) & (v < 1)
    return sel[ok], u[ok], v[ok]


def over(acc_rgb, acc_a, sel, rgb, a):
    acc_rgb[sel] = rgb * a[:, None] + acc_rgb[sel] * (1 - a[:, None])
    acc_a[sel] = a + acc_a[sel] * (1 - a)


def leaf_color(rgb, k):
    """Прошлогодний лист к лету: побурел и потемнел, у части — почти чёрный, прелый."""
    rng = np.random.default_rng(k)
    decay = rng.uniform(0.7, 1.0)
    lum = rgb @ np.array([0.3, 0.55, 0.15], np.float32)
    brown = np.array([0.17, 0.115, 0.065], np.float32) * (0.55 + 0.9 * lum[:, None])
    if rng.random() < 0.35:
        brown *= 0.55
    return rgb * (1 - decay) + brown * decay


# Ручные наклейки по габаритам «Целой» (geo.json boxes): перед — −Y, левый борт (водитель) — +X, лестница — справа сзади.
# file — картинка wear_sprites.py, c — центр (снаружи поверхности), n — куда смотрит наклейка, w — ширина (None —
# естественный размер картинки), depth — сколько от центра по нормали ловит поверхность, sets — в каких наборах.
OUTSIDE = ["body_L", "body_R", "body_parts", "shutters", "cab_panels", "cab_parts", "trim"]
PLACEMENTS = [
    # граффити — вымышленные слова; на рольставнях и нижних панелях, сзади — тег
    dict(kind="graffiti", file="graff_zhuk.png", c=[1.40, 0.72, 2.00], n=[1, 0, 0], sets=OUTSIDE, facing=0.4),
    dict(kind="graffiti", file="graff_volna.png", c=[-1.40, 2.06, 1.98], n=[-1, 0, 0], sets=OUTSIDE, facing=0.4),
    dict(kind="graffiti", file="graff_tiho.png", c=[-1.40, 0.62, 0.92], n=[-1, 0, 0], sets=OUTSIDE, facing=0.4),
    dict(kind="graffiti", file="graff_kot.png", c=[0.30, 3.98, 1.45], n=[0, 1, 0], sets=OUTSIDE + ["roof"], facing=0.4,
         up=[0.12, 0, 1]),
    # пальцем по пыли: сзади на рольставне, на лобовом и стёклах дверей
    dict(kind="writing", file="write_pomoi.png", c=[-0.08, 3.98, 2.22], n=[0, 1, 0], sets=OUTSIDE, up=[-0.05, 0, 1]),
    dict(kind="writing", file="write_01.png", c=[-0.52, -3.32, 2.22], n=[0, -0.978, 0.208], sets=["glass"], facing=0.5,
         up=[0.08, 0, 1]),
    dict(kind="writing", file="write_smile.png", c=[1.36, -2.12, 2.38], n=[1, 0, 0], sets=["glass"], facing=0.5),
    dict(kind="writing", file="write_kira.png", c=[-1.36, -0.76, 2.22], n=[-1, 0, 0], sets=["glass"], facing=0.5,
         up=[0, 0.06, 1]),
    # ладони: у ручек дверей (открывали, держась), сзади у ручек рольставни, спереди — опирались
    dict(kind="hand", file="hand_4.png", c=[1.36, -2.06, 2.06], n=[1, 0, 0], w=0.21, sets=OUTSIDE, up=[0, -0.15, 1]),
    dict(kind="hand", file="hand_2.png", c=[-1.36, -2.00, 2.02], n=[-1, 0, 0], w=0.21, sets=OUTSIDE, up=[0, 0.2, 1],
         opacity=0.8),
    dict(kind="hand", file="hand_3.png", c=[1.38, -0.78, 1.90], n=[1, 0, 0], w=0.21, sets=OUTSIDE, up=[0, -0.3, 1]),
    dict(kind="hand", file="hand_0.png", c=[-0.46, 3.98, 1.32], n=[0, 1, 0], w=0.21, sets=OUTSIDE, up=[0.25, 0, 1]),
    dict(kind="hand", file="hand_1.png", c=[0.50, 3.98, 1.26], n=[0, 1, 0], w=0.21, sets=OUTSIDE, up=[-0.1, 0, 1],
         opacity=0.85),
    dict(kind="hand", file="hand_4.png", c=[0.42, -3.42, 1.66], n=[0, -1, 0], w=0.21, sets=OUTSIDE, up=[0.3, 0, 1],
         opacity=0.7),
]


def placements(meta):
    size = {d["file"]: d["w_m"] for k in ("writing", "graffiti") for d in meta.get(k, [])}
    out = []
    for pl in PLACEMENTS:
        pl = dict(pl)
        if pl.get("w") is None:
            pl["w"] = size[pl["file"]]
        out.append(pl)
    return out


def decals(m: SetMaps, info, scatter, meta):
    n = len(m.P)
    res = {}
    # листья и помёт — только наружные наборы
    if m.st in EXTERIOR and m.st != "glass":
        rgb = np.zeros((n, 3), np.float32)
        a = np.zeros(n, np.float32)
        rough = np.full(n, 0.7, np.float32)
        hit = 0
        for lf in scatter["leaves"]:
            if "shutter" in lf["part"]:          # на рейках рольставней лист не держится
                continue
            spr = meta["leaves"][lf["k"] % len(meta["leaves"])]
            img = load_rgba(spr["file"])
            rimg = load_rgba(spr["file"].replace(".png", "_rough.png"))
            s = lf["s"]
            w, h = s * min(1.0, spr["aspect"]), s / max(1.0, spr["aspect"])
            ang = lf["rot"]
            nvec = np.array(lf["n"])
            t = np.cross(nvec, [0.0, 0.0, 1.0]) if abs(nvec[2]) < 0.95 else np.array([1.0, 0, 0])
            t /= np.linalg.norm(t)
            bb = np.cross(nvec, t)
            up = math.cos(ang) * bb + math.sin(ang) * t
            sel, u, v = project(m, lf["p"], nvec, up, w, h, 0.025, 0.5)
            if not len(sel):
                continue
            px = sample(img, u, v)
            col = leaf_color(px[:, :3], lf["k"])
            over(rgb, a, sel, col, px[:, 3])
            rough[sel] = rough[sel] * (1 - px[:, 3]) + sample(rimg, u, v) * px[:, 3]
            hit += 1
        if hit:
            res["leaves"] = (rgb, a, rough)
        rgb = np.zeros((n, 3), np.float32)
        a = np.zeros(n, np.float32)
        etch = np.zeros(n, np.float32)
        hit = 0
        for dr in scatter["drops"]:
            spr = meta["drops"][dr["k"] % len(meta["drops"])]
            img = load_rgba(spr["file"])
            s = dr["s"]
            nvec = np.array(dr["n"])
            # на наклонном и отвесном — потёк вниз: картинка вытянута по падению
            stretch = 1 + 1.8 * (1 - abs(nvec[2]))
            up = np.array([0, 0, 1.0]) if abs(nvec[2]) < 0.9 else np.array([math.cos(dr["rot"]), math.sin(dr["rot"]), 0])
            w, h = s, s * stretch
            sel, u, v = project(m, dr["p"], nvec, up, w * 1.6, h * 1.6, 0.02, 0.2)
            if not len(sel):
                continue
            uu, vv = (u - 0.5) * 1.6 + 0.5, (v - 0.5) * 1.6 + 0.5
            inside = (uu >= 0) & (uu < 1) & (vv >= 0) & (vv < 1)
            px = np.zeros((len(sel), 4), np.float32)
            px[inside] = sample(img, uu[inside], vv[inside])
            over(rgb, a, sel, px[:, :3], px[:, 3])
            ring = np.clip(1 - np.hypot(u - 0.5, v - 0.5) / 0.5, 0, 1)
            etch[sel] = np.maximum(etch[sel], smooth(ring, 0.0, 0.5) * 0.8)
            hit += 1
        if hit:
            res["drops"] = (rgb, a, None)
            res["drops_etch"] = etch
    # ручные: граффити, надписи и ладони
    g_rgb = np.zeros((n, 3), np.float32)
    g_a = np.zeros(n, np.float32)
    g_m = np.zeros(n, np.float32)
    clean = np.zeros(n, np.float32)
    ridge = np.zeros(n, np.float32)
    hands = np.zeros(n, np.float32)
    got = set()
    for pl in placements(meta):
        if pl.get("sets") and m.st not in pl["sets"]:
            continue
        img = load_rgba(pl["file"])
        hh, ww = img.shape[:2]
        w = pl["w"]
        h = w * hh / ww
        sel, u, v = project(m, pl["c"], pl["n"], pl.get("up", [0, 0, 1]), w, h, pl.get("depth", 0.3),
                            pl.get("facing", 0.45))
        if not len(sel):
            continue
        kind = pl["kind"]
        if kind == "graffiti":
            px = sample(img, u, v)
            over(g_rgb, g_a, sel, px[:, :3], px[:, 3] * pl.get("opacity", 1.0))
            mm = sample(load_rgba(pl["file"].replace(".png", "_metal.png")), u, v)
            g_m[sel] = np.maximum(g_m[sel], mm)
            got.add("graffiti")
        elif kind == "writing":
            clean[sel] = np.maximum(clean[sel], sample(img, u, v))
            rimg = load_rgba(pl["file"].replace(".png", "_ridge.png"))
            ridge[sel] = np.maximum(ridge[sel], sample(rimg, u, v))
            got.add("clean")
        elif kind == "hand":
            g = sample(img, u, v) * pl.get("opacity", 1.0)
            clean[sel] = np.maximum(clean[sel], g * 0.35)
            hands[sel] = np.maximum(hands[sel], g)
            got.add("clean")
            got.add("hands")
    if "graffiti" in got:
        res["graffiti"] = (g_rgb, g_a, None)
        res["graffiti_metal"] = g_m
    if "clean" in got:
        res["clean"] = clean
        res["ridge"] = ridge
    if "hands" in got:
        res["hands"] = hands
    return res


def write(path, img):
    if img.ndim == 2:
        cv2.imwrite(str(path), (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8))
    else:
        cv2.imwrite(str(path), (np.clip(img[..., ::-1], 0, 1) * 255 + 0.5).astype(np.uint8))


def main():
    only = sys.argv[1:]
    info = json.load(open(GEO / "geo.json", encoding="utf-8"))
    sp = GEO / "scatter.json"
    scatter = json.load(open(sp, encoding="utf-8")) if sp.exists() else {"leaves": [], "drops": []}
    meta = json.load(open(SPR / "sprites.json", encoding="utf-8"))
    ZON.mkdir(parents=True, exist_ok=True)
    DEC.mkdir(parents=True, exist_ok=True)
    report = {}
    for st in T.SETS:
        if only and st not in only:
            continue
        if not (GEO / f"{st}.npz").exists():
            continue
        t0 = time.time()
        m = SetMaps(st, info)
        rep = {}
        for k, v in zones(m, info, scatter).items():
            img = m.image(v)
            if k in ("leafmat",) and img.max() == 0:
                continue
            write(ZON / f"{st}_{k}.png", img)
            rep[k] = round(float(v.mean()), 3)
        for k, v in decals(m, info, scatter, meta).items():
            if isinstance(v, tuple):
                rgb, a, rough = v
                write(DEC / f"{st}_{k}.png", m.image(rgb, ch=3))
                write(DEC / f"{st}_{k}_a.png", m.image(a))
                if rough is not None:
                    write(DEC / f"{st}_{k}_rough.png", m.image(rough, fill=0.7))
                rep[k] = round(float((a > 0.5).mean()), 4)
            else:
                write(DEC / f"{st}_{k}.png", m.image(v))
                rep[k] = round(float((v > 0.5).mean()), 4)
        report[st] = rep
        print(st, f"{time.time() - t0:.0f} с", rep, flush=True)
    rp = WEAR / "report.json"
    old = json.load(open(rp, encoding="utf-8")) if rp.exists() else {}
    old.update(report)
    with open(rp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(old, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
