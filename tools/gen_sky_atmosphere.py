"""Расчётное небо (режим «расчёт» DayCycle): таблицы рассеяния в атмосфере и подгонка яркости.

python -X utf8 tools/gen_sky_atmosphere.py            → data/sky_atmosphere.json
python -X utf8 tools/gen_sky_atmosphere.py --preview <папка>   — ещё панорамы обоих режимов по высотам солнца

Атмосфера — модель Hillaire (2020, «A Scalable and Production Ready Sky and Atmosphere»): Рэлей, Ми,
озон; таблица пропускания (256×64, параметризация Брюнетона) и таблица многократного рассеяния
(32×32). Шейдер src/world/atmosphere_sky.gdshader по ним маршит луч взгляда (в четверть разрешения).
Подгонка: яркость расчётного неба по высоте солнца сводится к освещённости от нынешнего неба из
панорам (тот же расчёт, что в day_cycle_sky.gdshader, по данным sky_hdri зоны 1) — свет на земле,
который берёт оттенок из неба, остаётся прежним. Числа модели — здесь; шейдер получает их из JSON.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/sky_atmosphere.json"
SECTOR = ROOT / "data/sectors/zone01_mall.json"
BALANCE = ROOT / "src/core/balance.gd"

# ---------------------------------------------------------------- атмосфера Земли (км)
RG = 6360.0
RT = 6460.0
RAY_S = np.array([5.802, 13.558, 33.1]) * 1e-3   # рассеяние Рэлея, 1/км (без поглощения)
RAY_H = 8.0
MIE_S = 3.996e-3                                  # рассеяние Ми, 1/км
MIE_E = 4.40e-3                                   # ослабление Ми
MIE_H = 1.2
MIE_G = 0.8
OZ_A = np.array([0.650, 1.881, 0.085]) * 1e-3     # поглощение озоном
OZ_C = 25.0                                       # слой озона: пик на 25 км, «шатёр» ±15 км
OZ_W = 15.0
ALBEDO = 0.3                                      # земля для многократного рассеяния
VIEW_H = 0.2                                      # высота глаза над «землёй» атмосферы, км

T_W, T_H = 256, 64
M_N = 32
H_TOP = math.sqrt(RT * RT - RG * RG)


def densities(h: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    h = np.maximum(h, 0.0)
    return np.exp(-h / RAY_H), np.exp(-h / MIE_H), np.maximum(0.0, 1.0 - np.abs(h - OZ_C) / OZ_W)


def extinction(h: np.ndarray) -> np.ndarray:
    r, m, o = densities(h)
    return r[..., None] * RAY_S + m[..., None] * MIE_E + o[..., None] * OZ_A


def scattering(h: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    r, m, _ = densities(h)
    return r[..., None] * RAY_S, m[..., None] * MIE_S


def ray_sphere(r: np.ndarray, mu: np.ndarray, radius: float) -> tuple[np.ndarray, np.ndarray]:
    """Расстояния до сферы radius из точки на высоте r (центр Земли — 0) под косинусом mu к зениту."""
    disc = r * r * (mu * mu - 1.0) + radius * radius
    s = np.sqrt(np.maximum(disc, 0.0))
    return -r * mu - s, np.where(disc >= 0.0, -r * mu + s, -1.0)


# ---------------------------------------------------------------- пропускание
def transmittance_lut() -> np.ndarray:
    xm = np.arange(T_W) / (T_W - 1)
    xr = np.arange(T_H) / (T_H - 1)
    XM, XR = np.meshgrid(xm, xr)
    rho = H_TOP * XR
    r = np.sqrt(rho * rho + RG * RG)
    dmin = RT - r
    dmax = rho + H_TOP
    d = dmin + XM * (dmax - dmin)
    mu = np.where(d == 0.0, 1.0, (H_TOP * H_TOP - rho * rho - d * d) / np.maximum(2.0 * r * d, 1e-9))
    mu = np.clip(mu, -1.0, 1.0)
    n = 200
    tau = np.zeros(r.shape + (3,))
    for i in range(n):
        t = d * (i + 0.5) / n
        h = np.sqrt(r * r + t * t + 2.0 * r * mu * t) - RG
        tau += extinction(h) * (d / n)[..., None]
    return np.exp(-tau)  # [T_H, T_W, 3]


def t_uv(r: np.ndarray, mu: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rho = np.sqrt(np.maximum(r * r - RG * RG, 0.0))
    d = np.maximum(-r * mu + np.sqrt(np.maximum(r * r * (mu * mu - 1.0) + RT * RT, 0.0)), 0.0)
    dmin = RT - r
    dmax = rho + H_TOP
    return (d - dmin) / np.maximum(dmax - dmin, 1e-9), rho / H_TOP


def bilinear(lut: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """x, y — доли 0..1 от центра первой клетки до центра последней (как в шейдере с поправкой на полклетки)."""
    hgt, wid = lut.shape[:2]
    fx = np.clip(x, 0.0, 1.0) * (wid - 1)
    fy = np.clip(y, 0.0, 1.0) * (hgt - 1)
    x0 = np.minimum(np.floor(fx).astype(int), wid - 2)
    y0 = np.minimum(np.floor(fy).astype(int), hgt - 2)
    ax = (fx - x0)[..., None]
    ay = (fy - y0)[..., None]
    a = lut[y0, x0] * (1 - ax) + lut[y0, x0 + 1] * ax
    b = lut[y0 + 1, x0] * (1 - ax) + lut[y0 + 1, x0 + 1] * ax
    return a * (1 - ay) + b * ay


def sample_t(lut: np.ndarray, r: np.ndarray, mu: np.ndarray) -> np.ndarray:
    u, v = t_uv(r, mu)
    return bilinear(lut, u, v)


def sun_visible(r: np.ndarray, mu_s: np.ndarray) -> np.ndarray:
    """Солнце не за Землёй: луч к нему не упирается в землю."""
    near, _ = ray_sphere(r, mu_s, RG)
    disc = r * r * (mu_s * mu_s - 1.0) + RG * RG
    return np.where((disc >= 0.0) & (near > 0.0), 0.0, 1.0)


# ---------------------------------------------------------------- многократное рассеяние
def multiscatter_lut(tl: np.ndarray) -> np.ndarray:
    k = 16
    u = (np.arange(k) + 0.5) / k
    U, V = np.meshgrid(u, u)
    th = np.arccos(1.0 - 2.0 * V.ravel())
    ph = 2.0 * math.pi * U.ravel()
    dirs = np.stack([np.sin(th) * np.cos(ph), np.cos(th), np.sin(th) * np.sin(ph)], -1)  # y — вверх
    steps = 40
    out = np.zeros((M_N, M_N, 3))
    for j in range(M_N):
        h0 = (j / (M_N - 1)) * (RT - RG - 0.01) + 0.005
        r0 = RG + h0
        for i in range(M_N):
            mu_s = -1.0 + 2.0 * i / (M_N - 1)
            sun = np.array([0.0, mu_s, -math.sqrt(max(0.0, 1.0 - mu_s * mu_s))])
            mu = dirs[:, 1]
            gn, _ = ray_sphere(np.full_like(mu, r0), mu, RG)
            disc_g = r0 * r0 * (mu * mu - 1.0) + RG * RG
            hit_g = (disc_g >= 0.0) & (gn > 0.0)
            _, tt = ray_sphere(np.full_like(mu, r0), mu, RT)
            tmax = np.where(hit_g, gn, tt)
            L = np.zeros((len(mu), 3))
            F = np.zeros((len(mu), 3))
            thr = np.ones((len(mu), 3))
            dt = tmax / steps
            for s in range(steps):
                t = dt * (s + 0.5)
                p = dirs * t[:, None] + np.array([0.0, r0, 0.0])
                rr = np.linalg.norm(p, axis=1)
                h = rr - RG
                up = p / rr[:, None]
                mus = up @ sun
                sr, sm = scattering(h)
                ss = sr + sm
                se = extinction(h)
                tsun = sample_t(tl, rr, mus) * sun_visible(rr, mus)[:, None]
                step_t = np.exp(-se * dt[:, None])
                S = tsun * ss / (4.0 * math.pi)
                L += thr * (S - S * step_t) / np.maximum(se, 1e-12)
                F += thr * (ss - ss * step_t) / np.maximum(se, 1e-12)
                thr *= step_t
            pg = dirs * tmax[:, None] + np.array([0.0, r0, 0.0])
            rg = np.linalg.norm(pg, axis=1)
            ng = pg / rg[:, None]
            mug = ng @ sun
            tg = sample_t(tl, rg, mug)
            L += np.where(hit_g[:, None], thr * tg * np.maximum(mug, 0.0)[:, None] * ALBEDO / math.pi, 0.0)
            l2 = L.mean(0)
            fms = F.mean(0)
            out[j, i] = l2 / (1.0 - fms)
    return out


# ---------------------------------------------------------------- небо по лучам (как в шейдере)
def phase_r(c: np.ndarray) -> np.ndarray:
    return 3.0 / (16.0 * math.pi) * (1.0 + c * c)


def phase_m(c: np.ndarray, g: float = MIE_G) -> np.ndarray:
    k = 3.0 / (8.0 * math.pi) * (1.0 - g * g) / (2.0 + g * g)
    return k * (1.0 + c * c) / np.power(np.maximum(1.0 + g * g - 2.0 * g * c, 1e-6), 1.5)


def sky_radiance(dirs: np.ndarray, sun: np.ndarray, tl: np.ndarray, ml: np.ndarray, steps: int = 32,
                 mie_k: float = 1.0) -> np.ndarray:
    """Яркость неба по направлениям dirs [N,3] (y — вверх) при солнце sun (освещённость 1). Ниже горизонта —
    луч до земли с её отражением (для сравнения освещённости; шейдер под горизонтом делает по-своему)."""
    r0 = RG + VIEW_H
    mu = dirs[:, 1]
    gn, _ = ray_sphere(np.full_like(mu, r0), mu, RG)
    disc_g = r0 * r0 * (mu * mu - 1.0) + RG * RG
    hit_g = (disc_g >= 0.0) & (gn > 0.0)
    _, tt = ray_sphere(np.full_like(mu, r0), mu, RT)
    tmax = np.where(hit_g, gn, tt)
    cos_v = dirs @ sun
    pr = phase_r(cos_v)[:, None]
    pm = phase_m(cos_v)[:, None]
    L = np.zeros((len(mu), 3))
    thr = np.ones((len(mu), 3))
    t_prev = np.zeros_like(mu)
    for s in range(steps):
        # шаги гуще у глаза: горизонт и дымка
        f = (s + 1.0) / steps
        t_new = tmax * f * f
        dt = t_new - t_prev
        t = 0.5 * (t_new + t_prev)
        t_prev = t_new
        p = dirs * t[:, None] + np.array([0.0, r0, 0.0])
        rr = np.linalg.norm(p, axis=1)
        h = rr - RG
        up = p / rr[:, None]
        mus = up @ sun
        sr, sm = scattering(h)
        sm = sm * mie_k
        r_, m_, o_ = densities(h)
        se = r_[:, None] * RAY_S + m_[:, None] * MIE_E * mie_k + o_[:, None] * OZ_A
        tsun = sample_t(tl, rr, mus) * sun_visible(rr, mus)[:, None]
        ms = bilinear(ml, (mus + 1.0) * 0.5, h / (RT - RG))
        S = tsun * (sr * pr + sm * pm) + ms * (sr + sm)
        step_t = np.exp(-se * dt[:, None])
        L += thr * (S - S * step_t) / np.maximum(se, 1e-12)
        thr *= step_t
    pg = dirs * tmax[:, None] + np.array([0.0, r0, 0.0])
    rg = np.linalg.norm(pg, axis=1)
    mug = (pg / rg[:, None]) @ sun
    tg = sample_t(tl, rg, mug)
    L += np.where(hit_g[:, None], thr * tg * np.maximum(mug, 0.0)[:, None] * ALBEDO / math.pi, 0.0)
    return L


def pano_dirs(w: int, h: int) -> np.ndarray:
    """Направления панорамы как в шейдере: u = atan(x, −z)/2π + 0.5, v = acos(y)/π."""
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    U, V = np.meshgrid(u, v)
    phi = (U - 0.5) * 2.0 * math.pi
    th = V * math.pi
    return np.stack([np.sin(th) * np.sin(phi), np.cos(th), -np.sin(th) * np.cos(phi)], -1)


def sun_dir(elev: float, az: float = 0.0) -> np.ndarray:
    e = math.radians(elev)
    a = math.radians(az)
    return np.array([math.sin(a) * math.cos(e), math.sin(e), -math.cos(a) * math.cos(e)])


# ---------------------------------------------------------------- нынешнее небо из панорам (для подгонки)
def gd_const(name: str) -> dict:
    """Словарь-константа из balance.gd (Color(…) → [r, g, b])."""
    import re
    src = BALANCE.read_text(encoding="utf-8")
    i = src.index("const %s := {" % name) + len("const %s := " % name)
    depth = 0
    for j in range(i, len(src)):
        depth += {"{": 1, "}": -1}.get(src[j], 0)
        if depth == 0:
            break
    body = src[i:j + 1]
    body = re.sub(r"##[^\n]*", "", body)
    body = re.sub(r"Color\(([^)]*)\)", r"[\1]", body)
    body = re.sub(r",(\s*[}\]])", r"\1", body)
    return json.loads(body)


def srgb_lin(c: list) -> np.ndarray:
    c = np.array(c[:3], float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def smoothstep(a: float, b: float, x: float) -> float:
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def day_weights(e: float, dc: dict) -> dict:
    day = smoothstep(dc["dusk_to"], dc["day_from"], e)
    night = 1.0 - smoothstep(dc["night_to"], dc["dusk_from"], e)
    return {"day": day, "dusk": max(0.0, 1.0 - day - night), "night": night}


LUM = np.array([0.2126, 0.7152, 0.0722])
PW, PH = 256, 128


def hdri_pano(path: Path, cache: Path) -> np.ndarray:
    f = cache / (path.stem + "_%d.npy" % PW)
    if f.exists():
        return np.load(f)
    sys.path.insert(0, str(ROOT / "tools"))
    from sky_info import read_hdr
    rgb = read_hdr(path).astype(np.float32)
    h, w = rgb.shape[:2]
    small = rgb.reshape(PH, h // PH, PW, w // PW, 3).mean((1, 3))
    np.save(f, small)
    return small


def hdri_mode(e: float, weather: str, cache: Path, ctx: dict) -> np.ndarray:
    """Небо из панорам при высоте солнца e (солнце панорам — к азимуту 0), как day_cycle_sky.gdshader
    без ночной части и до обрезки для карты отражений. [PH, PW, 3]."""
    dc, hw, sky = ctx["dc"], ctx["hw"], ctx["sky_hdri"]
    w = day_weights(e, dc)
    ww = hw.get(weather, hw["clear"])
    prof = {}
    for k in ("day", "dusk", "night"):
        conf = sky.get(k + "_" + weather, sky.get(k, {})) if k != "night" else {}
        veil = conf.get("veil", 1.0)
        prof[k] = {"exp": conf.get("exposure", 1.0) * (1.0 + (ww["exposure"] - 1.0) * veil),
                   "oc": ww["overcast"] * veil, "haze": conf.get("haze", 0.0), "a": conf.get("a", "")}
    dd = max(w["day"] + w["dusk"], 1e-3)
    wd = {"day": w["day"] / dd, "dusk": w["dusk"] / dd}
    dim = dc["twilight_dim"] + (1.0 - dc["twilight_dim"]) * smoothstep(dc["twilight_end"], dc["sun_on"], e)
    exposure = sum(wd[k] * prof[k]["exp"] for k in wd) * dim
    overcast = sum(w[k] * prof[k]["oc"] for k in w)
    haze = sum(wd[k] * prof[k]["haze"] for k in wd)
    hdri_k = smoothstep(dc["sky_off"], dc["sky_on"], e)
    info = ctx["sky_info"]
    cols = []
    for k in ("day", "dusk"):
        p = ROOT / prof[k]["a"].replace("res://", "")
        img = hdri_pano(p, cache)
        shift = int(round((info[p.stem]["sun_u"] - 0.5) * PW))
        cols.append(np.roll(img, -shift, axis=1))
    c = np.minimum(cols[0] * (1 - wd["dusk"]) + cols[1] * wd["dusk"], 40.0)
    d = ctx["dirs"]
    elev = np.degrees(np.arcsin(np.clip(d[..., 1], -1, 1)))
    oc_col = srgb_lin([0.62, 0.65, 0.68])
    if haze > 0:
        hl = c @ LUM
        hk = (1.0 - np.vectorize(lambda x: smoothstep(-1.0, 10.0, x))(elev)) * haze
        c = c + (oc_col * (hl * 1.25)[..., None] - c) * hk[..., None]
    lum = c @ LUM
    flat = lum + ((1.0 - np.exp(-lum * 1.4)) - lum) * overcast
    c = c + (oc_col * (flat * 1.6)[..., None] - c) * overcast * 0.85
    return c * srgb_lin(ww["tint"]) * exposure * hdri_k


def irradiance(L: np.ndarray, d: np.ndarray, up: bool = True) -> np.ndarray:
    """Освещённость площадки, смотрящей вверх (или вниз), от панорамы L [PH, PW, 3]."""
    th = np.arccos(np.clip(d[..., 1], -1, 1))
    dw = (2 * math.pi / PW) * (math.pi / PH) * np.sin(th)
    cos = d[..., 1] if up else -d[..., 1]
    k = np.maximum(cos, 0.0) * dw
    return (L * k[..., None]).sum((0, 1))


def calc_sky(e: float, tl: np.ndarray, ml: np.ndarray, ctx: dict, mie: float) -> np.ndarray:
    d = ctx["dirs"]
    up = d[..., 1] >= 0.0
    out = np.zeros(d.shape)
    out[up] = sky_radiance(d[up], sun_dir(e), tl, ml, mie_k=mie)
    return out


def pack_half(img: np.ndarray) -> str:
    rgba = np.concatenate([img, np.ones(img.shape[:2] + (1,))], -1).astype("<f2")
    return base64.b64encode(rgba.tobytes()).decode("ascii")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", default="")
    args = ap.parse_args()
    cache = Path(tempfile.gettempdir()) / "ring_sky_atmosphere"
    cache.mkdir(exist_ok=True)
    tl = transmittance_lut()
    print("пропускание:", tl.shape, "к зениту с земли", tl[0, 0], "к горизонту", tl[0, -1])
    ml = multiscatter_lut(tl)
    print("многократное:", ml.shape, "полдень у земли", ml[0, -1], "закат", ml[0, M_N // 2])
    np.save(cache / "tl.npy", tl)
    np.save(cache / "ml.npy", ml)
    sc = gd_const("SKY_CALC")
    ctx = {"dc": gd_const("DAY_CYCLE"), "hw": gd_const("HDRI_WEATHER"),
           "sky_hdri": json.loads(SECTOR.read_text(encoding="utf-8"))["sky_hdri"],
           "sky_info": json.loads((ROOT / "assets/sky/sky_info.json").read_text(encoding="utf-8")),
           "dirs": pano_dirs(PW, PH)}
    cal = calibrate(tl, ml, ctx, cache, sc)
    data = {
        "comment": "tools/gen_sky_atmosphere.py — таблицы рассеяния и подгонка яркости расчётного неба",
        "atmosphere": {"rg": RG, "rt": RT, "ray_s": list(RAY_S), "ray_h": RAY_H, "mie_s": MIE_S, "mie_e": MIE_E,
                       "mie_h": MIE_H, "mie_g": MIE_G, "oz_a": list(OZ_A), "oz_c": OZ_C, "oz_w": OZ_W,
                       "view_h": VIEW_H},
        "transmittance": {"w": T_W, "h": T_H, "rgbah": pack_half(tl)},
        "multiscatter": {"w": M_N, "h": M_N, "rgbah": pack_half(ml)},
        "calib": cal,
    }
    OUT.write_bytes((json.dumps(data, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    print("записано", OUT.relative_to(ROOT), "%.0f КБ" % (OUT.stat().st_size / 1024))
    if args.preview:
        preview(Path(args.preview), tl, ml, ctx, cache, cal, sc)


def r5(v) -> float | list:
    if isinstance(v, (list, tuple, np.ndarray)):
        return [r5(x) for x in v]
    return float("%.5g" % float(v))


## Подгонка по высоте солнца для каждой погоды: gain — множитель атмосферы (освещённость от неба —
## как от панорам), oc — яркость зенита пасмурного неба (модель CIE: к горизонту втрое темнее), amb —
## поправка оттенка для карты отражений и рассеянного света, ground — яркость нижней полусферы.
## Ниже match_floor панорам уже почти нет: усиление растёт на twilight_adapt порядка за градус
## (глаз привыкает к сумеркам), а небо гаснет по физике.
def calibrate(tl: np.ndarray, ml: np.ndarray, ctx: dict, cache: Path, sc: dict) -> dict:
    d = ctx["dirs"]
    floor = float(sc["match_floor"])
    adapt = float(sc["twilight_adapt"])
    clamp = 2.5
    oc_unit = 7.0 * math.pi / 9.0
    elev = list(range(int(sc["cal_from"]), int(sc["cal_to"]) + 1))
    out: dict = {"elev": elev, "weather": {}}
    for wthr, ws in sc["weather"].items():
        mie = float(ws["mie"])
        o = float(ws["overcast"])
        rows: dict = {"gain": [], "oc": [], "amb": [], "ground": []}
        base = None
        for e in sorted(elev, reverse=True):
            C = calc_sky(float(e), tl, ml, ctx, mie)
            ec = irradiance(C, d)
            if e >= floor:
                H = np.minimum(hdri_mode(float(e), wthr, cache, ctx), clamp)
                et = irradiance(H, d)
                edn = irradiance(H, d, False)
                g = (et @ LUM) / max(ec @ LUM, 1e-12)
                ecc = irradiance(np.minimum(C * g, clamp), d)
                g *= (et @ LUM) / max(ecc @ LUM, 1e-12)
                ecc = irradiance(np.minimum(C * g, clamp), d)
                total = (1.0 - o) * ecc + o * et
                amb = et / np.maximum(total, 1e-12)
                row = {"gain": g, "oc": et / oc_unit, "amb": amb, "ground": edn / math.pi / amb, "lum": ec @ LUM}
                base = row
            else:
                g = base["gain"] * 10.0 ** (adapt * (floor - e))
                s = (ec @ LUM) * g / max(base["lum"] * base["gain"], 1e-20)
                row = {"gain": g, "oc": base["oc"] * s, "amb": base["amb"], "ground": base["ground"] * s, "lum": ec @ LUM}
            for k in rows:
                rows[k].insert(0, r5(row[k]))
            print("%s %+3d° ×%-9.4g зенит туч %s оттенок %s низ %s" % (wthr, e, row["gain"], np.round(row["oc"], 4),
                  np.round(row["amb"], 2), np.round(row["ground"], 4)))
        out["weather"][wthr] = rows
    return out


def preview(out: Path, tl: np.ndarray, ml: np.ndarray, ctx: dict, cache: Path, cal: dict, sc: dict) -> None:
    """Панорамы верхней полусферы: слева — из фото (как сейчас), справа — расчёт; одна выдержка."""
    from PIL import Image
    out.mkdir(parents=True, exist_ok=True)
    d = ctx["dirs"]
    tiles = []
    for e in [44.0, 15.0, 5.0, 1.0, -2.0, -6.0, -10.0, -13.0]:
        i = cal["elev"].index(int(e))
        g = cal["weather"]["clear"]["gain"][i]
        H = np.minimum(hdri_mode(max(e, -10.0), "clear", cache, ctx), 40.0)
        C = calc_sky(e, tl, ml, ctx, 1.0) * g
        row = []
        for L in (H, C):
            x = L[: PH // 2] * 0.9
            x = x / (1.0 + x)
            row.append((np.clip(x, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8))
        tiles.append(np.concatenate(row, 1))
    Image.fromarray(np.concatenate(tiles, 0)).save(out / "sky_compare.png")
    print("превью:", out / "sky_compare.png")

if __name__ == "__main__":
    main()
