"""Транспорт «Проспекта»: детали легковой поверх панелей — колёса, подкрылки, днище, начинка фар
и фонарей, решётка, номера, зеркала, ручки, дворники, уплотнители, салон, багажник, проёмы дверей.

Всё строится от той же поверхности поля, что и панели: накладки идут по кузову, а не висят
брусками; сечения скруглены. Руль слева (+X), машина с левым рулём. Только numpy; плоские фигуры
разбивает mathutils (Blender). Возвращают списки (имя, материал, вершины, грани, узел).
"""
from __future__ import annotations

import math

import numpy as np

import parts as pt
from engine_bay import rounded_block, tube
from vlib import Seam, View, loop_on_surface, mirror_mesh, resample, spline2d
from wheel import revolve

SEG = 96


# =============================================================================== колёса

def tire(R: float, W: float, rim_r: float, seg: int = SEG):
    """Шина: боковины с выпуклостью, плечи, протектор с четырьмя продольными канавками. Ось +X."""
    H = R - rim_r
    hw = W / 2
    side = [(0.80, 0.03), (0.90, 0.13), (0.97, 0.30), (1.00, 0.50), (0.985, 0.68), (0.94, 0.82), (0.87, 0.92)]
    prof = [(-k * hw, rim_r + q * H) for k, q in side]
    shoulder = [(-0.80 * hw, R - 0.012), (-0.76 * hw, R - 0.004)]
    prof += shoulder
    tread = []
    for x in np.linspace(-0.72 * hw, 0.72 * hw, 41):
        r = R
        for gc in (-0.50, -0.17, 0.17, 0.50):
            d = abs(x - gc * hw)
            if d < 0.0055:
                r = R - 0.008 * (1 - (d / 0.0055) ** 4)
        tread.append((x, r))
    prof += tread
    prof += [(-u, r) for u, r in reversed(shoulder)]
    prof += [(k * hw, rim_r + q * H) for k, q in reversed(side)]
    prof += [(0.80 * hw, rim_r + 0.004), (-0.80 * hw, rim_r + 0.004)]
    return revolve(prof, seg, closed=True)


def rim_barrel(rim_r: float, W: float, seg: int = SEG):
    """Обод: закраины, полки, ручей — тонкая стенка, видна изнутри арки."""
    hw = W / 2 * 0.86
    outer = [(-hw - 0.006, rim_r + 0.012), (-hw, rim_r + 0.003), (-hw + 0.02, rim_r), (-0.02, rim_r - 0.022),
             (0.02, rim_r - 0.022), (hw - 0.03, rim_r), (hw, rim_r + 0.003), (hw + 0.006, rim_r + 0.012)]
    inner = [(hw + 0.004, rim_r + 0.006), (hw - 0.03, rim_r - 0.006), (0.02, rim_r - 0.028),
             (-0.02, rim_r - 0.028), (-hw + 0.02, rim_r - 0.006), (-hw - 0.004, rim_r + 0.006)]
    return revolve(outer + inner, seg, closed=True)


def hubcap(rim_r: float, W: float, n: int = 8):
    """Пластиковый колпак на штампованном диске: чаша, рёбра-спицы, тёмные прорези между ними."""
    x0 = W / 2 * 0.86 + 0.004
    R = rim_r + 0.012
    dish = [(x0 - 0.004, R), (x0 + 0.006, R - 0.004), (x0 + 0.012, R - 0.020), (x0 + 0.018, R * 0.72),
            (x0 + 0.024, R * 0.45), (x0 + 0.030, R * 0.30), (x0 + 0.032, R * 0.20), (x0 + 0.036, R * 0.12),
            (x0 + 0.038, 0.0)]
    dV, dF = revolve(dish, SEG, closed=False)
    ribs, slots = [], []
    for i in range(n):
        a = i * 2 * math.pi / n
        t = np.linspace(0.30, 0.86, 10)
        r = R * t
        x = x0 + 0.030 - 0.018 * (t - 0.30) / 0.56 + 0.005
        P = np.c_[x, r * math.cos(a), r * math.sin(a)]
        rad = np.array([0.0, math.cos(a), math.sin(a)])
        tang = np.cross(np.array([1.0, 0, 0]), rad)
        ribs.append(pt.loft(P, np.broadcast_to(tang, P.shape), np.broadcast_to(np.array([1.0, 0, 0]), P.shape),
                            pt.rounded_rect(0.026, 0.008, 0.003, 2)))
        # прорезь между рёбрами: тёмная трапеция чуть глубже чаши
        b = a + math.pi / n
        poly = []
        for rr, da in ((0.40, 0.17), (0.80, 0.20), (0.80, -0.20), (0.40, -0.17)):
            poly.append((rr * R, b + da))
        quad = np.array([[x0 + 0.030 - 0.018 * (rr / R - 0.30) / 0.56 - 0.002, rr * math.cos(ang), rr * math.sin(ang)]
                         for rr, ang in poly])
        slots.append((quad, [(0, 1, 2, 3)]))
    cap = revolve([(x0 + 0.040, 0.0), (x0 + 0.040, 0.030), (x0 + 0.036, 0.040), (x0 + 0.030, 0.045)], 48)
    return (dV, dF), pt.merge(ribs), pt.merge(slots), cap


def steel_face(rim_r: float, W: float, n_holes: int = 8):
    """Штампованный диск под колпаком: чаша с выштамповкой, вентиляционные окна (тёмные), ступица, гайки."""
    x0 = W / 2 * 0.86
    prof = [(x0 - 0.002, rim_r + 0.004), (x0 - 0.010, rim_r - 0.010), (x0 - 0.020, rim_r * 0.80),
            (x0 - 0.018, rim_r * 0.62), (x0 - 0.008, rim_r * 0.50), (x0 - 0.006, rim_r * 0.40),
            (x0 - 0.012, rim_r * 0.30), (x0 - 0.012, 0.03), (x0 - 0.008, 0.0)]
    dish = revolve(prof, SEG)
    holes = []
    for i in range(n_holes):
        a = (i + 0.5) * 2 * math.pi / n_holes
        r0 = rim_r * 0.68
        k = 18
        t = np.linspace(0, 2 * math.pi, k, endpoint=False)
        ru, rt = rim_r * 0.075, rim_r * 0.10
        pts = []
        for th in t:
            rr = r0 + ru * math.cos(th)
            aa = a + (rt / r0) * math.sin(th)
            pts.append((x0 - 0.0185 + 0.001, rr * math.cos(aa), rr * math.sin(aa)))
        P = np.array(pts)
        c = P.mean(0)
        V = np.vstack([P, c[None]])
        F = [(j, (j + 1) % k, k) for j in range(k)]
        holes.append((V, F))
    nuts = []
    for i in range(4):
        a = i * 2 * math.pi / 4 + math.pi / 4
        v, f = revolve([(x0 - 0.010, 0.0), (x0 - 0.010, 0.010), (x0 + 0.004, 0.0105), (x0 + 0.008, 0.007),
                        (x0 + 0.009, 0.0)], 6, phase=math.pi / 6)
        v[:, 1] += 0.050 * math.cos(a)
        v[:, 2] += 0.050 * math.sin(a)
        nuts.append((v, f))
    return dish, pt.merge(holes), pt.merge(nuts)


def alloy_face(rim_r: float, W: float, n_spokes: int = 5, split: bool = False):
    """Литой диск: спицы (по одной или сдвоенные), ступица, колпачок; спицы вогнуты к центру."""
    x0 = W / 2 * 0.86
    out = []
    pairs = [(-1, 1)] if split else [(0,)]
    for p in range(n_spokes):
        base = p * 2 * math.pi / n_spokes
        for side in pairs[0]:
            t = np.linspace(0, 1, 18)
            r = 0.060 + (rim_r + 0.004 - 0.060) * t
            x = x0 - 0.006 - 0.030 * (1 - t) ** 1.5 + 0.004
            spread = (math.radians(4.5) * side * (0.4 + t)) if split else 0.0
            ang = base + spread
            P = np.c_[x, r * np.cos(ang), r * np.sin(ang)]
            radial = np.c_[np.zeros_like(r), np.cos(ang) * np.ones_like(r), np.sin(ang) * np.ones_like(r)]
            tang = np.cross(np.array([1.0, 0, 0]), radial)
            w0, w1 = (0.030, 0.020) if split else (0.052, 0.034)

            def sec(i, t=t, w0=w0, w1=w1):
                w = w0 + (w1 - w0) * t[i]
                return pt.rounded_rect(w, 0.026, 0.008, 3)
            out.append(pt.loft(P, tang, np.broadcast_to(np.array([1.0, 0, 0]), P.shape), sec, cap=True))
    hub = revolve([(x0 - 0.035, 0.0), (x0 - 0.035, 0.075), (x0 - 0.010, 0.078), (x0 - 0.002, 0.070),
                   (x0 + 0.004, 0.052), (x0 + 0.008, 0.032), (x0 + 0.009, 0.0)], 64)
    lip = revolve([(x0 - 0.010, rim_r + 0.002), (x0 + 0.004, rim_r + 0.004), (x0 + 0.008, rim_r + 0.014),
                   (x0 + 0.004, rim_r + 0.018), (x0 - 0.012, rim_r + 0.012)], SEG, closed=True)
    nuts = []
    for i in range(4 if n_spokes == 4 else 5):
        a = i * 2 * math.pi / (4 if n_spokes == 4 else 5) + math.pi / n_spokes
        v, f = revolve([(x0 + 0.002, 0.0), (x0 + 0.002, 0.009), (x0 + 0.012, 0.0095), (x0 + 0.016, 0.006),
                        (x0 + 0.017, 0.0)], 6, phase=math.pi / 6)
        v[:, 1] += 0.052 * math.cos(a)
        v[:, 2] += 0.052 * math.sin(a)
        nuts.append((v, f))
    return pt.merge(out), pt.merge([hub, lip]), pt.merge(nuts)


def brake(rim_r: float):
    """Тормозной диск с колоколом и суппорт — видны сквозь спицы."""
    rd = rim_r * 0.70
    disc = revolve([(-0.044, rd * 0.45), (-0.044, rd), (-0.022, rd), (-0.022, rd * 0.45)], 64, closed=True)
    hat = revolve([(-0.022, rd * 0.48), (0.0, rd * 0.45), (0.010, rd * 0.42), (0.010, 0.04), (0.004, 0.04),
                   (0.004, rd * 0.40), (-0.018, rd * 0.44)], 48, closed=True)
    t = np.linspace(-0.45, 0.45, 12)
    ang = math.radians(150.0) + t
    P = np.c_[np.full_like(t, -0.033), rd * 0.86 * np.cos(ang), rd * 0.86 * np.sin(ang)]
    radial = np.c_[np.zeros_like(t), np.cos(ang), np.sin(ang)]
    cal = pt.loft(P, np.broadcast_to(np.array([1.0, 0, 0]), P.shape), radial, pt.rounded_rect(0.06, 0.045, 0.012, 3))
    return pt.merge([disc, hat]), cal


def wheel_parts(spec: dict) -> list[tuple[str, str, np.ndarray, list]]:
    R, W = spec["tire_r"], spec["tire_w"]
    rim_r = spec["rim_d_in"] * 0.0127
    style = spec.get("wheel_style", "steel_cap")
    out = [("Tire", "rubber", *tire(R, W, rim_r)), ("Rim_Barrel", "rim_steel" if style == "steel_cap" else "rim_alloy",
                                                    *rim_barrel(rim_r, W))]
    disc, cal = brake(rim_r)
    out += [("Brake_Disc", "brake", *disc), ("Caliper", "steel_dark", *cal)]
    if style == "steel_cap":
        face, holes, nuts = steel_face(rim_r, W)
        out += [("Rim_Face", "rim_steel", *face), ("Rim_Holes", "mesh_black", *holes), ("Lug_Nuts", "steel_dark", *nuts)]
        dish, ribs, slots, cap = hubcap(rim_r, W, spec.get("cap_spokes", 8))
        out += [("Hubcap", "hubcap", *dish), ("Hubcap_Ribs", "hubcap", *ribs), ("Hubcap_Slots", "mesh_black", *slots),
                ("Hubcap_Center", "hubcap", *cap)]
    else:
        spokes, hub, nuts = alloy_face(rim_r, W, spec.get("spokes", 5), spec.get("split_spokes", False))
        out += [("Rim_Spokes", "rim_alloy", *spokes), ("Rim_Hub", "rim_alloy", *hub), ("Lug_Nuts", "steel_dark", *nuts)]
    return out


# =============================================================================== низ

def wheel_liner(yc: float, zc: float, r: float, x_in: float, x_out: float):
    return pt.wheel_liner(yc, zc, r=r, x_in=x_in, x_out=x_out, phi0=-20.0, phi1=200.0)


def under_tray(f, spec: dict):
    """Днище: плита по плану кузова с вырезами под колёса и тоннель выхлопа."""
    yf, yr = spec["wheel_y"]
    y0, y1 = yf - spec["arch_r"] - 0.10, yr + spec["arch_r"] + 0.10
    ys = np.linspace(y0, y1, 160)
    half = np.minimum(f.plan(ys) * 0.86, spec["width"] / 2 - 0.12)
    for c in spec["wheel_y"]:
        m = np.abs(ys - c) < spec["arch_r"] + 0.06
        half[m] = np.minimum(half[m], spec["well_x"] - 0.03)
    left = np.c_[half, ys]
    poly = np.vstack([left, np.c_[-half[::-1], ys[::-1]]])
    if pt.poly_area(poly) < 0:
        poly = poly[::-1]
    pv, pf = pt.poly_mesh(poly)
    z = spec["lay"]["sill_bot_z"] - 0.012
    return np.c_[pv[:, 0], pv[:, 1], np.full(len(pv), z)], [f_[::-1] for f_ in pf]


def exhaust(spec: dict):
    """Выхлоп: труба по днищу к задней части слева, глушитель, насадка под бампером."""
    lay = spec["lay"]
    z = lay["sill_bot_z"] - 0.06
    yt = float(spec["rear"][len(spec["rear"]) // 2][1])
    x = -0.42
    pipe = tube([(0.10, -0.6, z + 0.01), (0.15, 0.4, z + 0.01), (x + 0.10, yt - 0.85, z + 0.03), (x, yt - 0.55, z + 0.04),
                 (x, yt - 0.06, lay["bump_r_bottom_z"] - 0.04)], 0.024, 12, 40)
    muffler = rounded_block((x + 0.02, yt - 0.62, z + 0.06), 0.30, 0.42, 0.18, 0.06)
    tip = tube([(x, yt - 0.20, lay["bump_r_bottom_z"] - 0.04), (x, yt - 0.02, lay["bump_r_bottom_z"] - 0.035)],
               0.030, 16, 6)
    return pt.merge([pipe, muffler]), tip


# =============================================================================== фары, фонари, решётка

def backing(surf, view, loop3, depth, h=0.012):
    return pt.backing(surf, view, loop3, depth, h)


def headlamp_inner(surf, views, lamp_loop: np.ndarray):
    """Отражатель (задник), линза проектора, полоса поворотника по низу фары."""
    view = views["rf"]
    back = pt.backing(surf, view, lamp_loop, 0.055)
    L = lamp_loop
    c = L.mean(0)
    nn = surf.normal(c[None])[0]
    # проектор — в наружной половине фары, ближе к середине по высоте
    far = L[np.argmax(L[:, 0])]
    pc = c + 0.35 * (far - c)
    pc = surf.project(pc[None])[0] - surf.normal(pc[None])[0] * 0.030
    axis = surf.normal(pc[None])[0]
    P = np.linspace(pc - axis * 0.045, pc, 6)
    T, N, B = pt.frames(P, np.array([0, 0, 1.0]))
    circ = np.c_[np.cos(np.linspace(0, 2 * math.pi, 28, endpoint=False)),
                 np.sin(np.linspace(0, 2 * math.pi, 28, endpoint=False))] * 0.034
    lens = pt.loft(P, N, B, circ, cap=True)
    ring = pt.loft(np.linspace(pc - axis * 0.012, pc - axis * 0.002, 3), N[:3], B[:3], circ * 1.32, cap=False)
    # второй рефлектор-чаша (дальний свет) — ближе к середине машины
    near = L[np.argmin(L[:, 0])]
    qc = c + 0.30 * (near - c)
    qc = surf.project(qc[None])[0] - surf.normal(qc[None])[0] * 0.045
    bowl = revolve([(0.0, 0.0), (0.004, 0.012), (0.012, 0.024), (0.024, 0.032), (0.036, 0.035)], 32)
    bv = bowl[0][:, [1, 0, 2]] * np.array([1, -1, 1])
    bv = bv + qc
    # полоса поворотника — вдоль нижней кромки, под стеклом
    low = L[L[:, 2] < np.quantile(L[:, 2], 0.30)]
    low = low[np.argsort(low[:, 0])]
    if len(low) > 6:
        strip = resample(low, 40)[4:-4]
        strip = surf.project(strip + 0.25 * (c - strip)) - surf.normal(strip) * 0.012
        T2, N2, B2 = pt.frames(strip, np.array([0, 0, 1.0]))
        amber = pt.loft(strip, N2, B2, pt.rounded_rect(0.010, 0.016, 0.004, 3))
    else:
        amber = (np.zeros((0, 3)), [])
    return back, pt.merge([lens]), pt.merge([ring, (bv, bowl[1])]), amber


def taillamp_inner(surf, views, tl_loop: np.ndarray):
    """Задник фонаря и внутренние секции: красная, белая (задний ход), рамка-разделитель."""
    view = views["rr"]
    back = pt.backing(surf, view, tl_loop, 0.04)
    inner = loop_on_surface(surf, view, tl_loop, 0.01, 0.022, False)
    ring = resample(np.vstack([inner, inner[:1]]), 160)
    ring = ring - surf.normal(ring) * 0.010
    T, N, B = pt.frames(ring, np.array([0, 0, 1.0]))
    divider = pt.loft(ring, N, B, pt.rounded_rect(0.006, 0.014, 0.002, 2), cap=False)
    return back, divider


def grille_parts(surf, views, S: dict, lay: dict):
    """Решётка: горизонтальные планки и сетка за ними; нижний воздухозаборник; противотуманки."""
    out = []
    holes = S["_front_holes"]
    rf = views["rf"]
    if "grille" in holes:
        g = holes["grille"]
        out.append(("Grille_Back", "mesh_black", *pt.backing(surf, rf, g, 0.07), "body"))
        zs = np.linspace(lay["grille"][-1][1] + 0.018, lay["grille"][0][1] - 0.018, lay.get("grille_bars", 4))
        out.append(("Grille_Bars", "trim_gloss_black", *pt.fins_in_loop(surf, rf, g, list(zs), t=0.010, depth=0.045,
                                                                         recess=0.012, margin=0.010), "body"))
        surround = resample(np.vstack([g, g[:1]]), 300)
        out.append(("Grille_Surround", "chrome", *pt.loft(surround, *pt.frames(surround, np.array([0, -1.0, 0]))[1:],
                                                          pt.rounded_rect(0.009, 0.007, 0.003, 2), cap=False), "body"))
    if "intake" in holes:
        g = holes["intake"]
        out.append(("Intake_Back", "mesh_black", *pt.backing(surf, rf, g, 0.06), "body"))
        zc = (lay["intake"][0][1] + lay["intake"][-1][1]) / 2
        out.append(("Intake_Bar", "trim_black", *pt.fins_in_loop(surf, rf, g, [zc], t=0.014, depth=0.05, recess=0.008,
                                                                  margin=0.004), "body"))
    for key in ("fog_l", "fog_r"):
        if key not in holes:
            continue
        g = holes[key]
        out.append((f"Fog_Back_{key[-1].upper()}", "trim_black", *pt.backing(surf, rf, g, 0.05), "body"))
        c = g.mean(0)
        nn = surf.normal(c[None])[0]
        pc = surf.project(c[None])[0] - nn * 0.028
        P = np.linspace(pc - nn * 0.02, pc, 4)
        T, N, B = pt.frames(P, np.array([0, 0, 1.0]))
        w = np.ptp(g[:, 0]) * 0.36
        h = np.ptp(g[:, 2]) * 0.40
        circ = np.c_[np.cos(np.linspace(0, 2 * math.pi, 24, endpoint=False)) * w,
                     np.sin(np.linspace(0, 2 * math.pi, 24, endpoint=False)) * h]
        out.append((f"Fog_Lens_{key[-1].upper()}", "lamp_glass", *pt.loft(P, B, N, circ, cap=True), "body"))
    return out


def plate(center, normal, up=(0, 0, 1.0), w: float = 0.520, h: float = 0.112, t: float = 0.004):
    """Номерной знак: скруглённая пластина (подложка текста — отделкой)."""
    n = np.asarray(normal, float)
    n /= np.linalg.norm(n)
    u = np.cross(np.asarray(up, float), n)
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    P = np.array([center - n * t / 2, center + n * t / 2])
    P = np.linspace(P[0], P[1], 3)
    return pt.loft(P, np.broadcast_to(u, P.shape), np.broadcast_to(v, P.shape), pt.rounded_rect(w, h, 0.008, 3))


# =============================================================================== мелочь кузова

def mirror(surf, views, base_yz: tuple, spec: dict):
    """Зеркало на «парусе» двери: корпус обтекаемого сечения, стекло, ножка; левое (+X)."""
    side = views["side"]
    base = side.lift(surf, np.array([base_yz]))[0]
    L, Hh, D = spec.get("mirror_size", (0.20, 0.125, 0.095))
    x0 = base[0] + 0.035
    xs = np.linspace(x0, x0 + L, 24)
    t = (xs - x0) / L
    yc = base[1] + 0.02 + 0.015 * t
    zc = base[2] + 0.055 + 0.02 * t
    path = np.c_[xs, yc, zc]
    U = np.broadcast_to(np.array([0, 1.0, 0]), path.shape)
    Vv = np.broadcast_to(np.array([0, 0, 1.0]), path.shape)

    def sec(i):
        k = 1.0 - 0.25 * t[i] ** 3
        return pt.d_section(D * (0.85 + 0.15 * k), Hh * k, min(D, Hh) * 0.45, 0.012)
    housing = pt.loft(path, U, Vv, sec, cap=True)
    # стекло на заднем плоском торце: тонкая пластина чуть позади
    gx = np.linspace(xs[2], xs[-3], 10)
    gz = np.interp(gx, xs, zc)
    gy = np.interp(gx, xs, yc) + D / 2 + 0.001
    hh = np.interp(gx, xs, Hh * (1.0 - 0.25 * t ** 3)) * 0.40
    top = np.c_[gx, gy, gz + hh]
    bot = np.c_[gx, gy, gz - hh][::-1]
    poly = np.vstack([top, bot])
    pv, pf = pt.poly_mesh(np.c_[poly[:, 0], poly[:, 2]])
    glass = (np.c_[pv[:, 0], np.interp(pv[:, 0], gx, gy), pv[:, 1]], [f[::-1] for f in pf])
    # ножка: от паруса двери под корпус
    P = np.array([base + np.array([-0.004, 0.0, 0.02]), np.array([x0 + 0.02, yc[0] + 0.005, zc[0] - 0.035])])
    P = np.linspace(P[0], P[1], 6)
    T, N, B = pt.frames(P, np.array([0, 1.0, 0]))
    arm = pt.loft(P, N, B, pt.rounded_rect(0.07, 0.03, 0.012, 3), cap=True)
    return housing, glass, arm


def handle(surf, views, y0: float, y1: float, z: float):
    """Ручка двери: скоба на тёмной выемке."""
    side = views["side"]
    yy = np.linspace(y0, y1, 30)
    line = side.lift(surf, np.c_[yy, np.full(len(yy), z)])
    bar = pt.strip_on_surface(surf, line[2:-2], 0.030, 0.014, 0.003, r=0.007)
    cup = pt.strip_on_surface(surf, line, 0.046, 0.002, -0.0015, r=0.0009)
    return bar, cup


def wiper(surf, views, p0_top, p1_top, pivot_top):
    top = views["top"]
    blade_line = top.lift(surf, np.linspace(np.array(p0_top), np.array(p1_top), 40))
    blade = pt.strip_on_surface(surf, blade_line, 0.018, 0.011, 0.002, r=0.004)
    mid = blade_line[len(blade_line) // 2]
    piv = top.lift(surf, np.array([pivot_top]))[0]
    arm_line = surf.project(np.linspace(piv, mid, 20))
    arm = pt.strip_on_surface(surf, arm_line, 0.016, 0.008, 0.014, r=0.003)
    return pt.merge([blade, arm])


def seal_along(surf, P: np.ndarray, width: float, thick: float, lift: float = 0.0, r: float | None = None):
    return pt.strip_on_surface(surf, P, width, thick, lift, r=r)


def offset_along_surface(surf, P: np.ndarray, d: np.ndarray) -> np.ndarray:
    return surf.project(P + d)


def antenna(surf, views, y: float):
    top = views["top"]
    p = top.lift(surf, np.array([[0.0, y]]))[0]
    base = rounded_block(p + np.array([0, 0.0, 0.012]), 0.045, 0.09, 0.03, 0.012)
    P = np.array([p + np.array([0, 0.02, 0.025]), p + np.array([0, 0.16, 0.20])])
    rod = tube(P, 0.003, 8, 4)
    return pt.merge([base, rod])


# =============================================================================== салон

def interior(f, spec: dict, S: dict):
    """Салон: торпедо со щитком и центральной консолью, руль, кресла, задний диван, тоннель, пол,
    полка за задним сиденьем (седан); всё по размерам кузова."""
    lay = spec["lay"]
    cab = spec.get("cabin", {})
    out = []
    z_floor = lay["sill_top_z"] - 0.06
    y_ws = float(f.ws(lay["ws_base_z"] + 0.03))
    half_in = min(float(f.gh(0.0)), spec["width"] / 2) - 0.07
    # торпедо: профиль от основания стекла к коленям, по всей ширине
    belt0 = float(f.belt(y_ws + 0.3))
    prof = np.array([(y_ws + 0.02, belt0 + 0.02), (y_ws + 0.16, belt0 + 0.05), (y_ws + 0.30, belt0 + 0.055),
                     (y_ws + 0.40, belt0 + 0.035), (y_ws + 0.44, belt0 - 0.02), (y_ws + 0.43, belt0 - 0.12),
                     (y_ws + 0.38, belt0 - 0.25), (y_ws + 0.34, belt0 - 0.32), (y_ws + 0.20, belt0 - 0.34),
                     (y_ws + 0.05, belt0 - 0.30)])
    prof = spline2d(prof, 40)
    xs = np.linspace(-half_in, half_in, 44)
    V, F = [], []
    n = len(prof)
    for i, x in enumerate(xs):
        V.append(np.c_[np.full(n, x), prof[:, 0], prof[:, 1]])
    V = np.vstack(V)
    F = [(i * n + j, i * n + j + 1, (i + 1) * n + j + 1, (i + 1) * n + j) for i in range(len(xs) - 1) for j in range(n - 1)]
    out.append(("Dashboard", "interior", V, F, "body"))
    face_y = y_ws + 0.43
    drv_x = cab.get("driver_x", 0.36)
    out.append(("Instrument_Hood", "interior", *rounded_block((drv_x, face_y - 0.10, belt0 + 0.07), 0.36, 0.20, 0.08, 0.035),
                "body"))
    out.append(("Center_Stack", "interior", *rounded_block((0.0, face_y - 0.02, belt0 - 0.12), 0.26, 0.10, 0.28, 0.02),
                "body"))
    out.append(("Center_Screen", "trim_gloss_black", *rounded_block((0.0, face_y + 0.034, belt0 - 0.06), 0.20, 0.006, 0.11,
                                                                     0.003), "body"))
    # руль: обод, спицы, ступица, кожух колонки
    sw_c = np.array([drv_x, face_y + 0.20, belt0 - 0.02])
    tilt = math.radians(cab.get("wheel_tilt_deg", 24))
    Rw, rw = 0.185, 0.016
    ang = np.linspace(0, 2 * math.pi, 14, endpoint=False)
    rim = revolve([(rw * math.cos(a), Rw + rw * math.sin(a)) for a in ang], 56, closed=True)
    hub = rounded_block((0, 0, -0.02), 0.06, 0.12, 0.10, 0.03)
    spokes = [rounded_block((0, 0, -0.10), 0.03, 0.05, 0.15, 0.012), rounded_block((0, -0.10, -0.01), 0.03, 0.17, 0.04, 0.012),
              rounded_block((0, 0.10, -0.01), 0.03, 0.17, 0.04, 0.012)]
    sw = pt.merge([rim, hub] + spokes)
    Vw = sw[0][:, [1, 0, 2]]                         # ось руля — вдоль Y
    from interior import rot
    Vw = rot(Vw, rx=tilt) + sw_c
    out.append(("Steering_Wheel", "interior", Vw, sw[1], "body"))
    col = rounded_block((0, -0.12, 0), 0.08, 0.20, 0.08, 0.03)
    out.append(("Steering_Column", "interior", rot(col[0], rx=tilt) + sw_c, col[1], "body"))
    # кресла
    from interior import seat
    y_fs = lay["b_y"] - cab.get("front_seat_back", 0.20)
    z_seat = z_floor + cab.get("seat_h", 0.25)
    for x in (drv_x, -drv_x):
        out.append(("Seat_Front_" + ("L" if x > 0 else "R"), "seat", *seat(x, y_fs, z_seat, width=0.50, back_h=0.60,
                                                                          tilt=0.30), "body"))
    y_rs = cab.get("rear_seat_y", lay["c_belt_y"] - 0.30)
    bench = pt.merge([seat(0.33, y_rs, z_seat - 0.03, width=0.46, back_h=0.52, tilt=0.30, rear=True),
                      seat(-0.33, y_rs, z_seat - 0.03, width=0.46, back_h=0.52, tilt=0.30, rear=True),
                      rounded_block((0.0, y_rs, z_seat - 0.03), 0.22, 0.50, 0.12, 0.04)])
    out.append(("Seat_Rear", "seat", *bench, "body"))
    for x in (0.30, -0.30, 0.0):
        out.append((f"Headrest_Rear_{'LRC'[[0.30, -0.30, 0.0].index(x)]}", "seat",
                    *rounded_block((x, y_rs + 0.30, z_seat + 0.57), 0.24, 0.08, 0.15, 0.04), "body"))
    # тоннель с рычагом КПП и ручником, пол
    out.append(("Console", "interior", *pt.merge([
        rounded_block((0.0, (face_y + y_fs) / 2 + 0.05, z_floor + 0.14), 0.22, max(y_fs - face_y + 0.25, 0.3), 0.20, 0.05),
        rounded_block((0.0, y_fs + 0.05, z_floor + 0.26), 0.16, 0.30, 0.06, 0.025),
        tube([(0.0, face_y + 0.30, z_floor + 0.24), (0.0, face_y + 0.33, z_floor + 0.36)], 0.012, 10, 4),
        rounded_block((0.0, face_y + 0.335, z_floor + 0.38), 0.045, 0.045, 0.06, 0.02)]), "body"))
    y_front = y_ws + 0.15
    y_back = y_rs + 0.45
    out.append(("Floor", "carpet", *rounded_block((0.0, (y_front + y_back) / 2, z_floor), 2 * half_in + 0.04,
                                                  y_back - y_front, 0.03, 0.01), "body"))
    if spec["rear_style"] == "sedan" and "bl_base_z" in lay:
        # полка за задним сиденьем — до основания заднего стекла
        y_bl = float(f.bl(lay["bl_base_z"])) + 0.02
        z_sh = lay["bl_base_z"] - 0.02
        y0 = y_rs + 0.36
        out.append(("Parcel_Shelf", "interior", *rounded_block((0.0, (y0 + y_bl) / 2, z_sh), 2 * half_in - 0.06,
                                                               max(y_bl - y0, 0.1), 0.02, 0.008), "body"))
    # зеркало заднего вида и козырьки — за лобовым стеклом под потолком
    zv = float(f.roof(lay["a_top_y"] + 0.10)) - 0.075
    yv = float(f.ws(zv)) + 0.13
    out.append(("Mirror_Inner", "interior", *rounded_block((0.0, yv - 0.02, zv - 0.08), 0.24, 0.03, 0.065, 0.02), "body"))
    for x in (0.36, -0.36):
        out.append((f"Visor_{'L' if x > 0 else 'R'}", "headliner",
                    *rounded_block((x, yv + 0.02, zv), 0.36, 0.16, 0.02, 0.008), "body"))
    return out


def door_cards(surf, views, S: dict, spec: dict, f):
    """Обивка двери изнутри: плита по контуру обшивки на глубине двери, подлокотник, ручка, карман."""
    lay = spec["lay"]
    out = []
    side = views["side"]
    for key, grp in (("_skin_f", "door_f"), ("_skin_r", "door_r")):
        loopP = S[key]
        inner = loop_on_surface(surf, side, loopP, 0.014, 0.012, False)
        V, F = pt.backing(surf, side, inner, lay["door_depth"])
        out.append(("Door_Card_" + grp[-1].upper(), "interior", V, F, grp))
        ys = loopP[:, 1]
        y0, y1 = ys.min() + 0.10, ys.max() - 0.12
        zb = float(np.median(loopP[:, 2][loopP[:, 2] > np.quantile(loopP[:, 2], 0.7)]))
        xin = float(np.median(V[:, 0])) - 0.03
        arm = rounded_block((xin, (y0 + y1) / 2 + 0.05, zb - 0.20), 0.06, (y1 - y0) * 0.55, 0.05, 0.02)
        pocket = rounded_block((xin + 0.005, (y0 + y1) / 2, zb - 0.45), 0.04, (y1 - y0) * 0.7, 0.10, 0.015)
        out.append(("Door_Card_Trim_" + grp[-1].upper(), "interior", *pt.merge([arm, pocket]), grp))
    return out


def door_jambs(surf, views, S: dict, spec: dict):
    """Проёмы дверей: стенки проёма вглубь кузова, порог-ступень, средняя стойка B между дверями."""
    lay = spec["lay"]
    out = []
    # стенки проёма по контуру двух дверей (наружный обход проёма): низ, задняя кромка, верх, передняя
    edge = np.vstack([S["door_bot_f"].reversed(), S["door_bot_r"].reversed()[1:], S["door_rear"].reversed()[1:],
                      S["frame_c"].reversed()[1:], S["door_top_r"].reversed()[1:], S["door_top_f"].reversed()[1:],
                      S["frame_a"].reversed()[1:], S["door_belt_f"].reversed()[1:], S["door_front"].reversed()[1:]])
    edge = resample(edge, 500)
    nrm = surf.normal(edge)
    depth = lay["door_depth"] + 0.02
    rings = [edge - nrm * 0.006, edge - nrm * depth]
    V = np.vstack(rings)
    n = len(edge)
    F = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n - 1)]
    out.append(("Door_Jamb", "paint_inner", V, F, "body"))
    # стойка B: от порога до рейлинга крыши, за стыком дверей
    b = S["b_line"].P
    b = resample(b, 30)
    bn = surf.normal(b)
    post_line = b - bn * 0.045
    T, N, B = pt.frames(post_line, np.array([1.0, 0, 0]))
    out.append(("B_Pillar", "paint_inner", *pt.loft(post_line, N, B, pt.rounded_rect(0.05, 0.11, 0.012, 3), cap=True), "body"))
    # порог изнутри: ступень от кромки двери к полу
    sill = np.vstack([S["door_bot_f"].reversed(), S["door_bot_r"].reversed()[1:]])
    sill = resample(sill, 60)
    inner = sill.copy()
    inner[:, 0] -= 0.16
    inner[:, 2] -= 0.04
    V = np.vstack([sill - surf.normal(sill) * depth, inner])
    m = len(sill)
    F = [(i, m + i, m + i + 1, i + 1) for i in range(m - 1)]
    out.append(("Sill_Tread", "interior", V, F, "body"))
    return out


def trunk_parts(surf, views, S: dict, spec: dict, f):
    """Багажник: внутренняя панель крышки (пятой двери), ванна багажника (пол и стенки), у хэтчбека — шторка."""
    lay = spec["lay"]
    out = []
    lid = S["_lid_loop"]
    inner = loop_on_surface(surf, views["rx_rear"], lid, 0.016, 0.03, False)
    if "_tg_glass" in S:
        hole = loop_on_surface(surf, views["rx_rear"], S["_tg_glass"], 0.016, 0.02, True)
        uv = views["rx_rear"].to_uv(inner)
        huv = views["rx_rear"].to_uv(hole)
        pv, pf = pt.poly_mesh(uv, [huv])
        P = views["rx_rear"].lift(surf, pv)
        out.append(("Tailgate_Inner", "paint_inner", P - surf.normal(P) * 0.045, [f_[::-1] for f_ in pf], "lid"))
        y_rs = spec.get("cabin", {}).get("rear_seat_y", lay["c_belt_y"] - 0.30)
        y0, z_c = y_rs + 0.36, lay["bl_base_z"] - 0.035
        y1 = float(f.bl(z_c + 0.05)) - 0.10
        hw = min(float(f.gh(y1)), spec["width"] / 2) - 0.10
        out.append(("Cargo_Cover", "interior", *rounded_block((0.0, (y0 + y1) / 2, z_c), 2 * hw, max(y1 - y0, 0.1), 0.015,
                                                              0.006), "body"))
    else:
        out.append(("Trunk_Lid_Inner", "paint_inner", *pt.backing(surf, views["rx_rear"], inner, 0.035), "lid"))
    yt = float(spec["rear"][len(spec["rear"]) // 2][1])
    y0 = lay["c_belt_y"] + 0.15
    y1 = yt - 0.24                                  # корма к углам уходит вперёд — стенки не доходят до неё
    z0 = lay["bump_r_bottom_z"] + 0.12
    hw = min(float(f.plan(y1)), spec["width"] / 2) * 0.86 - 0.10
    out.append(("Trunk_Tub", "carpet", *rounded_block((0.0, (y0 + y1) / 2, z0 + 0.02), 2 * hw, y1 - y0, 0.03, 0.01),
                "body"))
    for sgn in (1, -1):
        out.append((f"Trunk_Wall_{'L' if sgn > 0 else 'R'}", "carpet",
                    *rounded_block((sgn * (hw + 0.01), (y0 + y1) / 2, z0 + 0.22), 0.02, y1 - y0, 0.42, 0.008), "body"))
    out.append(("Trunk_Wall_Back", "carpet", *rounded_block((0.0, y1 + 0.01, z0 + 0.15), 2 * hw, 0.02, 0.28, 0.008), "body"))
    return out


# =============================================================================== после пожара

def _zigzag(p0, p1, side_dir, amp: float, n: int) -> list:
    """Змейка пружины от p0 к p1 с размахом amp поперёк (side_dir)."""
    p0, p1, sd = np.asarray(p0, float), np.asarray(p1, float), np.asarray(side_dir, float)
    pts = []
    for k in range(n + 1):
        t = k / n
        pts.append(p0 + (p1 - p0) * t + sd * (amp if k % 2 else -amp) * (0 < k < n))
    return pts


def _poly_tube(pts, r: float, closed: bool = False):
    """Проволока по ломаной (без сглаживания углов): отрезки трубками."""
    P = [np.asarray(p, float) for p in pts]
    if closed:
        P = P + [P[0]]
    parts = []
    ang = np.linspace(0, 2 * math.pi, 8, endpoint=False)
    circ = np.c_[np.cos(ang), np.sin(ang)] * r
    for a, b in zip(P[:-1], P[1:]):
        seg = np.linspace(a, b, 2)
        T = b - a
        T /= max(np.linalg.norm(T), 1e-9)
        up = np.array([0, 0, 1.0]) if abs(T[2]) < 0.9 else np.array([1.0, 0, 0])
        Bv = np.cross(T, up)
        Bv /= np.linalg.norm(Bv)
        Nv = np.cross(Bv, T)
        parts.append(pt.loft(seg, np.broadcast_to(Nv, seg.shape), np.broadcast_to(Bv, seg.shape), circ, cap=True))
    return pt.merge(parts)


def seat_frame(x: float, y: float, z: float, width: float = 0.48, back_h: float = 0.58, tilt: float = 0.30,
               rear: bool = False):
    """Сгоревшее кресло: рамка подушки и спинки трубой, пружины-змейки, стойки подголовника."""
    from interior import rot
    hw, d = width / 2, 0.48
    parts = []
    cush = [(x - hw, y - d / 2, z), (x + hw, y - d / 2, z), (x + hw, y + d / 2, z), (x - hw, y + d / 2, z)]
    parts.append(_poly_tube(cush, 0.011, closed=True))
    for k in range(4):
        xx = x - hw + width * (k + 0.5) / 4
        parts.append(_poly_tube(_zigzag((xx, y - d / 2, z - 0.01), (xx, y + d / 2, z - 0.01), (1, 0, 0), 0.025, 8), 0.004))
    if not rear:
        for sx in (-1, 1):
            parts.append(_poly_tube([(x + sx * hw * 0.8, y - d / 2 + 0.05, z), (x + sx * hw * 0.8, y - d / 2 + 0.05, z - 0.16),
                                     (x + sx * hw * 0.8, y + d / 2 - 0.05, z - 0.16), (x + sx * hw * 0.8, y + d / 2 - 0.05, z)],
                                    0.012))
    yb, zb = y + d / 2, z + 0.02
    back = [(x - hw, yb, zb), (x + hw, yb, zb), (x + hw, yb, zb + back_h), (x - hw, yb, zb + back_h)]
    bt = _poly_tube(back, 0.011, closed=True)
    springs = []
    for k in range(3):
        xx = x - hw + width * (k + 0.5) / 3
        springs.append(_poly_tube(_zigzag((xx, yb, zb + 0.04), (xx, yb, zb + back_h - 0.04), (1, 0, 0), 0.03, 9), 0.004))
    bk = pt.merge([bt] + springs)
    if not rear:
        posts = pt.merge([_poly_tube([(x + sx * 0.08, yb, zb + back_h), (x + sx * 0.08, yb, zb + back_h + 0.12)], 0.006)
                          for sx in (-1, 1)])
        bk = pt.merge([bk, posts])
    bk = (rot(bk[0], rx=-tilt, about=(x, yb, zb)), bk[1])
    parts.append(bk)
    return pt.merge(parts)


def burnt_interior(f, spec: dict, S: dict):
    """Салон после пожара: каркасы кресел и дивана, поперечина торпедо, кольцо руля с колонкой, голый пол."""
    from interior import rot
    lay = spec["lay"]
    cab = spec.get("cabin", {})
    z_floor = lay["sill_top_z"] - 0.06
    y_ws = float(f.ws(lay["ws_base_z"] + 0.03))
    half_in = min(float(f.gh(0.0)), spec["width"] / 2) - 0.07
    belt0 = float(f.belt(y_ws + 0.3))
    drv_x = cab.get("driver_x", 0.36)
    face_y = y_ws + 0.43
    out = []
    y_fs = lay["b_y"] - cab.get("front_seat_back", 0.20)
    z_seat = z_floor + cab.get("seat_h", 0.25)
    for x in (drv_x, -drv_x):
        out.append(("Seat_Frame_Front_" + ("L" if x > 0 else "R"), "burnt", *seat_frame(x, y_fs, z_seat - 0.03), "body"))
    y_rs = cab.get("rear_seat_y", lay["c_belt_y"] - 0.30)
    out.append(("Seat_Frame_Rear", "burnt", *pt.merge([seat_frame(0.33, y_rs, z_seat - 0.06, 0.44, 0.50, 0.30, True),
                                                       seat_frame(-0.33, y_rs, z_seat - 0.06, 0.44, 0.50, 0.30, True)]),
                "body"))
    beam = tube([(-half_in, y_ws + 0.38, belt0 - 0.08), (half_in, y_ws + 0.38, belt0 - 0.08)], 0.028, 12, 4)
    brackets = pt.merge([_poly_tube([(sx, y_ws + 0.38, belt0 - 0.08), (sx, y_ws + 0.40, z_floor)], 0.015) for sx in (0.12, -0.12)])
    out.append(("Dash_Beam", "burnt", *pt.merge([beam, brackets]), "body"))
    tilt = math.radians(cab.get("wheel_tilt_deg", 24))
    sw_c = np.array([drv_x, face_y + 0.20, belt0 - 0.02])
    ang = np.linspace(0, 2 * math.pi, 8, endpoint=False)
    ring = revolve([(0.007 * math.cos(a), 0.18 + 0.007 * math.sin(a)) for a in ang], 48, closed=True)
    spokes = pt.merge([_poly_tube([(0, 0, 0), (0, 0.17 * math.cos(a), 0.17 * math.sin(a))], 0.006) for a in (0, math.pi, -math.pi / 2)])
    sw = pt.merge([ring, spokes])
    Vw = rot(sw[0][:, [1, 0, 2]], rx=tilt) + sw_c
    out.append(("Steering_Ring", "burnt", Vw, sw[1], "body"))
    col = tube([sw_c + np.array([0, -0.02, -0.01]), sw_c + np.array([0, -0.40, -0.17])], 0.022, 10, 4)
    out.append(("Steering_Column", "burnt", *col, "body"))
    y_front, y_back = y_ws + 0.15, y_rs + 0.45
    out.append(("Floor_Bare", "burnt", *pt.merge([
        rounded_block((0.0, (y_front + y_back) / 2, z_floor - 0.01), 2 * half_in + 0.04, y_back - y_front, 0.012, 0.004),
        rounded_block((0.0, (y_front + y_back) / 2, z_floor + 0.07), 0.24, y_back - y_front, 0.16, 0.04)]), "body"))
    return out


def crash_beam(spec: dict, f):
    """Без переднего бампера видно силовое: поперечный брус, рамка радиатора, кронштейны."""
    y_n = float(spec["front"][len(spec["front"]) // 2][1])
    lay = spec["lay"]
    hw = float(f.plan(y_n + 0.3)) - 0.16
    zc = (lay["intake"][0][1] + lay["grille"][-1][1]) / 2 if "intake" in lay else 0.48
    beam = rounded_block((0.0, y_n + 0.14, zc), 2 * hw, 0.07, 0.11, 0.02)
    arms = pt.merge([rounded_block((sx * (hw - 0.08), y_n + 0.32, zc), 0.08, 0.30, 0.09, 0.02) for sx in (1, -1)])
    zt = lay["grille"][0][1] + 0.0 if "grille" in lay else 0.72
    frame = pt.merge([
        rounded_block((0.0, y_n + 0.40, zt), 2 * hw - 0.2, 0.05, 0.05, 0.012),
        rounded_block((0.0, y_n + 0.40, zc - 0.05), 2 * hw - 0.2, 0.05, 0.05, 0.012),
        rounded_block((hw - 0.15, y_n + 0.40, (zt + zc) / 2), 0.05, 0.05, zt - zc + 0.1, 0.012),
        rounded_block((-hw + 0.15, y_n + 0.40, (zt + zc) / 2), 0.05, 0.05, zt - zc + 0.1, 0.012)])
    radiator = rounded_block((0.0, y_n + 0.44, (zt + zc) / 2 - 0.02), 2 * hw - 0.36, 0.04, zt - zc, 0.006)
    return pt.merge([beam, arms]), frame, radiator


def spoiler(surf, views, S: dict):
    """Козырёк над стеклом пятой двери: крыло по верхней кромке двери, сечение капля."""
    top = S["bl_top"].P
    edge = np.vstack([top[::-1], (top * [-1, 1, 1])[1:]])
    edge = resample(edge, 120)[4:-4]
    nrm = surf.normal(edge)
    path = edge + nrm * 0.012 + np.array([0, 0.035, 0])
    T, N, B = pt.frames(path, np.array([0, 0, 1.0]))
    sec = pt.d_section(0.11, 0.022, 0.010, 0.004)
    return pt.loft(path, np.broadcast_to(np.array([0, 1.0, 0]), path.shape), np.broadcast_to(np.array([0, 0, 1.0]), path.shape),
                   sec, cap=True)


def rear_wiper(surf, views, S: dict, spec: dict):
    """Задний дворник: ось над низом стекла по центру, щётка лежит влево-вверх."""
    rear = views["rear"]
    G = S["_tg_glass"]
    zb = float(G[:, 2].min())
    piv = rear.lift(surf, np.array([[0.0, zb + 0.015]]))[0]
    tip = rear.lift(surf, np.array([[0.48, zb + 0.10]]))[0]
    line = surf.project(np.linspace(piv, tip, 30))
    blade = pt.strip_on_surface(surf, line[4:], 0.016, 0.010, 0.002, r=0.004)
    arm = pt.strip_on_surface(surf, line, 0.014, 0.007, 0.013, r=0.003)
    hub = rounded_block(piv + surf.normal(piv[None])[0] * 0.02, 0.05, 0.04, 0.05, 0.015)
    return pt.merge([blade, arm, hub])


def roof_rail(surf, views, S: dict, spec: dict):
    """Рейлинг на крыше (левый): труба-дуга над краем крыши на трёх опорах."""
    edge = S["roof_side"].P
    edge = resample(edge, 60)
    inward = np.array([-0.035, 0, 0])
    base = surf.project(edge + inward)
    nrm = surf.normal(base)
    y0, y1 = base[:, 1].min() + 0.12, base[:, 1].max() - 0.06
    keep = (base[:, 1] > y0) & (base[:, 1] < y1)
    base, nrm = base[keep], nrm[keep]
    t = np.linspace(0, 1, len(base))
    lift = 0.045 + 0.012 * np.sin(np.pi * t)
    path = base + nrm * lift[:, None]
    T, N, B = pt.frames(path, np.array([0, 0, 1.0]))
    bar = pt.loft(path, N, B, pt.rounded_rect(0.028, 0.030, 0.010, 3), cap=True)
    feet = []
    for k in (0, len(base) // 2, len(base) - 1):
        c = base[k] + nrm[k] * 0.025
        feet.append(rounded_block(c, 0.045, 0.11 if k in (0, len(base) - 1) else 0.07, 0.05, 0.015))
    return pt.merge([bar] + feet)


def side_step(spec: dict, f):
    """Подножка вдоль порога между арками (левая): плита с рифлёной накладкой и три кронштейна."""
    yf, yr = spec["wheel_y"]
    ar = spec["arch_r"]
    y0, y1 = yf + ar + 0.06, yr - ar - 0.06
    z = spec["lay"]["sill_bot_z"] - 0.05
    xb = float(f.plan(0.0)) * float(f.sec(spec["lay"]["sill_bot_z"]))
    plate = rounded_block((xb + 0.04, (y0 + y1) / 2, z), 0.17, y1 - y0, 0.045, 0.015)
    tread = rounded_block((xb + 0.04, (y0 + y1) / 2, z + 0.025), 0.13, y1 - y0 - 0.06, 0.008, 0.003)
    brackets = [rounded_block((xb - 0.04, y, z + 0.02), 0.12, 0.05, 0.03, 0.008) for y in np.linspace(y0 + 0.12, y1 - 0.12, 3)]
    return pt.merge([plate, tread] + brackets)


def arch_flares(surf, views, S: dict, spec: dict):
    """Расширители арок (левые): пластиковая накладка по кромке арки, выступает наружу."""
    out = []
    for nm, keys in (("Flare_F", ("arch_f_front", "arch_f_top")), ("Flare_R", ("arch_r_low", "arch_r_top"))):
        a, b = S[keys[0]].P, S[keys[1]].P
        curve = np.vstack([a[::-1], b[1:]])
        curve = curve[curve[:, 2] > spec["lay"]["sill_bot_z"] + 0.02]
        curve = resample(curve, 120)
        nrm = surf.normal(curve)
        out.append((nm, pt.strip_on_surface(surf, curve, 0.075, 0.022, 0.0, r=0.008)))
    return out


def chassis(spec: dict, f):
    """Рама и задний мост рамного внедорожника — видны под высоким кузовом."""
    yf, yr = spec["wheel_y"]
    z = spec["lay"]["sill_bot_z"] - 0.06
    y0 = float(spec["front"][0][1]) + 0.20
    y1 = float(spec["rear"][0][1]) - 0.10
    rails = pt.merge([rounded_block((sx * 0.50, (y0 + y1) / 2, z), 0.07, y1 - y0, 0.16, 0.012) for sx in (1, -1)])
    xs = pt.merge([rounded_block((0.0, y, z), 1.0, 0.07, 0.10, 0.01) for y in (yf + 0.35, -0.2, 0.9, y1 - 0.15)])
    wz = spec["wheel_z"]
    axle = tube([(-spec["track"] / 2 + 0.12, yr, wz), (spec["track"] / 2 - 0.12, yr, wz)], 0.045, 14, 4)
    diff = rounded_block((0.10, yr, wz), 0.26, 0.30, 0.26, 0.10)
    tank = rounded_block((-0.20, yr + 0.55, z + 0.02), 0.70, 0.45, 0.20, 0.05)
    springs = []
    for sx in (1, -1):
        for k in range(5):
            zz = z + 0.10 + k * 0.05
            springs.append(tube([(sx * 0.48 + 0.07 * np.cos(a), yr + 0.07 * np.sin(a), zz + a * 0.008) for a in np.linspace(0, 2 * np.pi, 9)],
                                0.011, 8, 18))
    return [("Frame", "steel_dark", pt.merge([rails, xs])), ("Rear_Axle", "steel_dark", pt.merge([axle, diff])),
            ("Fuel_Tank", "steel_dark", tank), ("Rear_Springs", "steel_dark", pt.merge(springs))]


def spare_wheel(spec: dict, S: dict, surf):
    """Запасное колесо на задней двери: шина, диск, мягкий чехол поверх."""
    R, W = spec["tire_r"], spec["tire_w"]
    rim_r = spec["rim_d_in"] * 0.0127
    G = S["_tg_glass"]
    zc = float(G[:, 2].min()) - R * 0.55 - 0.03
    pc = surf.ray(np.array([[0.0, float(spec["rear"][-1][1]) + 1.0, zc]]), np.array([0.0, -1.0, 0.0]))[0]
    yc = pc[1] + W / 2 + 0.05
    tv, tf = tire(R, W, rim_r, 72)
    cover = revolve([(-W / 2 - 0.004, R * 0.98), (0.0, R + 0.006), (W / 2 + 0.006, R * 0.97), (W / 2 + 0.018, R * 0.80),
                     (W / 2 + 0.024, R * 0.4), (W / 2 + 0.026, 0.0)], 72)
    mount = rounded_block((0.0, 0.0, 0.0), 0.12, 0.18, 0.12, 0.02)

    def place(V):
        V = V[:, [1, 0, 2]].copy()            # ось колеса — вдоль Y (наружу назад)
        return V + np.array([0.0, yc, zc])
    mv = mount[0].copy()
    mv[:, 0] = mv[:, 0] * 0.5 - W / 2 - 0.02
    bv, bf = rim_barrel(rim_r, W, 72)
    fv, ff = steel_face(rim_r, W)[0]
    return [("Spare_Tire", "rubber", (place(tv), tf)), ("Spare_Cover", "seat", (place(cover[0]), cover[1])),
            ("Spare_Rim", "rim_steel", (place(np.vstack([bv, fv])), list(bf) + [tuple(i + len(bv) for i in q) for q in ff])),
            ("Spare_Mount", "steel_dark", (place(mv), mount[1]))]
