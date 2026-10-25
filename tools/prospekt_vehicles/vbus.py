"""Транспорт «Проспекта»: панели и детали «коробчатых» машин — городской автобус, ПАЗ, ГАЗель-маршрутка.

Кузов собирается так же, как у легковых: поле формы (vfield.BoxField) → области на видах → панели с
зазорами и завёрнутыми кромками (coupe_ilya/domain.py). Здесь своя раскладка:
  обод — граница боковины на виде сбоку: лицо (Y = лицо(Z) + отступ), верх (Z = верх(Y) − отступ),
  корма; низ боковины — по юбке с вырезами арок и проёмами дверей;
  полосы — то, что над ободом между боковинами (лицо, капот, лобовая часть, крыша, корма): поперечные
  швы режут их, у каждой свой вид; в полосах — проёмы стёкол, фар, решётки, люка двигателя.
Двери справа (−X): створки «гармошкой», сдвижная, распашные. Детали: колёса (задние — двускатные),
бамперы, зеркала на кронштейнах, дворники, кондиционер, люки, салон (пол, сиденья, поручни, место водителя).
"""
from __future__ import annotations

import math

import numpy as np

import parts as pt
from engine_bay import rounded_block, tube
from vlib import Seam, View, domain_panel, fillet_poly, lift_poly, loop, mirror_mesh, resample
from wheel import revolve

GAP = 0.005


# =============================================================================== обод и низ боковины

def rim_path(f, s: dict, step: float = 0.008) -> tuple[np.ndarray, dict]:
    """Обод левого борта на виде сбоку: от низа лица вверх, поверху назад, вниз по корме.
    Возвращает плотную ломаную (Y, Z) и границы участков (индексы)."""
    r = s["lay"]["rim"]
    z0 = r["z_fbot"]
    front = []
    z = z0
    while True:
        y = float(f.front(z)) + r["off_f"]
        zt = float(f.top(y)) - r["off_t"]
        if z >= zt:
            break
        front.append((y, z))
        z += step * 0.5
    y_c = front[-1][0]
    # корма: сверху вниз; где начинается
    z = r["z_rbot"]
    rear = []
    while True:
        y = float(f.rear(z)) - r["off_r"]
        zt = float(f.top(y)) - r["off_t"]
        if z >= zt:
            break
        rear.append((y, z))
        z += step * 0.5
    y_d = rear[-1][0]
    ys = np.arange(y_c + step, y_d - step * 0.5, step)
    top = [(y, float(f.top(y)) - r["off_t"]) for y in ys]
    path = np.array(front + top + rear[::-1])
    marks = {"front_end": len(front) - 1, "top_end": len(front) + len(top) - 1}
    return path, marks


def cut_index(path: np.ndarray, marks: dict, seam) -> int:
    """Где поперечный шов режет обод: ("zf", z) — на лице, ("y", y) — поверху, ("zr", z) — на корме."""
    kind, v = seam
    n = len(path)
    if kind == "zf":
        rng = np.arange(0, marks["front_end"] + 1)
        return int(rng[np.argmin(np.abs(path[rng, 1] - v))])
    if kind == "zr":
        rng = np.arange(marks["top_end"] + 1, n)
        return int(rng[np.argmin(np.abs(path[rng, 1] - v))])
    rng = np.arange(marks["front_end"], marks["top_end"] + 1)
    return int(rng[np.argmin(np.abs(path[rng, 0] - v))])


def bottom_path(f, s: dict, y_from: float, z_from: float, y_to: float, z_to: float, doors: list) -> np.ndarray:
    """Низ боковины (Y, Z) от кормы к лицу: юбка (не ниже низа кузова), вырезы арок (дуги), проёмы
    дверей (П-образно вверх)."""
    lay = s["lay"]
    zs0 = lay["rim"]["z_sbot"]

    def zs(y):
        return max(zs0, float(f.bot(y)) + s["r_bot"] * 0.7)
    R = s["arch_r"] + 0.006
    wz = s["wheel_z"]
    feats = []
    for yc in s["wheel_y"]:
        feats.append(("arch", yc, yc))
    for d in doors:
        feats.append(("door", (d["y0"] + d["y1"]) / 2, d))
    feats.sort(key=lambda t: -t[1])                  # от кормы к лицу
    pts = [(y_from, z_from)]
    y_cur = y_from - 0.02

    def run_to(y_end):
        # юбка от текущего места до y_end (по низу кузова)
        nonlocal y_cur
        for y in np.arange(y_cur, y_end, -0.05):
            pts.append((y, zs(y)))
        pts.append((y_end, zs(y_end)))
        y_cur = y_end
    for kind, yc, extra in feats:
        if kind == "arch":
            z_ = zs(yc)
            dz = z_ - wz
            if abs(dz) >= R:
                continue
            a_ = math.sqrt(R * R - dz * dz)
            run_to(yc + a_)
            phi0 = math.degrees(math.atan2(dz, a_))
            for ph in np.linspace(phi0, 180.0 - phi0, 30)[1:]:
                pts.append((yc + R * math.cos(math.radians(ph)), wz + R * math.sin(math.radians(ph))))
            y_cur = yc - a_
        else:
            d = extra
            run_to(d["y1"])
            pts += [(d["y1"], d["z_top"]), (d["y0"], d["z_top"]), (d["y0"], zs(d["y0"]))]
            y_cur = d["y0"]
    if y_cur > y_to + 0.035:
        run_to(y_to + 0.02)
    pts.append((y_to, z_to))
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) + abs(p[1] - out[-1][1]) > 1e-4:
            out.append(p)
    return np.array(out)


def rect_loop(u0: float, u1: float, v0: float, v1: float, r: float) -> np.ndarray:
    return fillet_poly([(u0, v0), (u1, v0), (u1, v1), (u0, v1)], r, closed=True, n_arc=6)


def _seam_across(surf, views, pL, pR, kind, v, n=60):
    view = {"zf": "front", "zr": "rear", "y": "top"}[kind]
    xs = np.linspace(pL[0], pR[0], 9)[1:-1]
    if kind == "y":
        mids = [("top", x, v) for x in xs]
    else:
        mids = [(view, x, float(np.interp(x, [pR[0], pL[0]], [pR[2], pL[2]]))) for x in xs]
    return Seam(surf, views, [("p", *pL)] + mids + [("p", *pR)], view, n=n).P


# =============================================================================== кузов

def build(surf, f, s: dict, views: dict) -> tuple[list, dict]:
    lay = s["lay"]
    out: list = []
    S: dict = {}

    def add(name, mat, V, F, group="body"):
        out.append((name, mat, V, F, group))

    def panel(name, mat, view, loop3, holes=(), group="body", **kw):
        V = None
        h0 = kw.pop("h", 0.03)
        for k in range(4):                           # совпадение узлов сетки с контуром — другой шаг
            try:
                V, F = domain_panel(surf, views[view], loop3, holes=holes, h=h0 * (1 + 0.07 * k), **kw)
                break
            except Exception as e:
                err = e
        if V is None:                                # отладка раскладки
            print(f"!! панель {name}: {err}")
            DEBUG.append((name, view, views[view].to_uv(loop3), [views[view].to_uv(h) for h in holes]))
            return None
        add(name, mat, V, F, group)
        return V, F

    rim2, marks = rim_path(f, s)
    rimL = views["side"].lift(surf, rim2)
    rimR = rimL * np.array([-1.0, 1, 1])
    S["rim2"], S["rimL"], S["marks"] = rim2, rimL, marks
    seams = lay["seams"]
    ks = [cut_index(rim2, marks, sm) for sm in seams]
    S["seam_k"] = ks
    across = []
    for sm, k in zip(seams, ks):
        across.append(_seam_across(surf, views, rimL[k], rimR[k], sm[0], sm[1]))
    # --- полосы над ободом
    for i, band in enumerate(lay["bands"]):
        k0, k1 = ks[i], ks[i + 1]
        L = loop([across[i], rimR[k0:k1 + 1], across[i + 1][::-1], rimL[k0:k1 + 1][::-1]], tol=0.02)
        holes, extras = [], []
        for h in band.get("holes", []):
            av = views[h.get("author", band["view"])]
            u0, u1, v0, v1, r = h["rect"]
            ring = rect_loop(u0, u1, v0, v1, r)
            H = lift_poly(surf, av, np.vstack([ring, ring[:1]]), 0.004)[:-1]
            holes.append(H)
            extras.append((h, H))
        S["band_" + band["name"]] = L
        grp = band.get("group", "body")
        panel(band["name"], band.get("mat", "paint"), band["view"], L, holes=holes, group=grp, h=0.03, gap=GAP,
              hole_depth=0.035)
        for h, H in extras:
            _hole_part(surf, views, band, h, H, add, panel, S, s)
    # --- боковины
    for side, sgn, vname in (("L", 1.0, "side"), ("R", -1.0, "side_r")):
        rim3 = rimL if sgn > 0 else rimR
        doors = lay["doors_l"] if sgn > 0 else lay["doors_r"]
        k0, k1 = ks[0], ks[-1]
        y_rb, z_rb = rim2[k1]
        y_fb, z_fb = rim2[k0]
        bp = bottom_path(f, s, y_rb, z_rb, y_fb, z_fb, doors)
        bp = fillet_poly(bp, 0.025, closed=False, n_arc=4)
        B = lift_poly(surf, views[vname], bp, 0.006)
        B[0], B[-1] = rim3[k1], rim3[k0]
        L = loop([rim3[k0:k1 + 1], B], tol=0.03)
        wins = []
        for (y0, y1, z0, z1, r) in (lay["win_l"] if sgn > 0 else lay["win_r"]):
            ring = rect_loop(y0, y1, z0, z1, r)
            wins.append(lift_poly(surf, views[vname], np.vstack([ring, ring[:1]]), 0.005)[:-1])
        S["side_" + side] = L
        panel("Side_" + side, "paint", vname, L, holes=wins, h=0.035, gap=GAP, hole_depth=0.04)
        for j, W in enumerate(wins):
            panel(f"Glass_Side_{side}{j + 1}", "glass", vname, W, h=0.05, gap=0.004, flange=0.02, fit_deg=2, fit_blend=0.03)
            add(f"Seal_Side_{side}{j + 1}", "rubber", *pt.strip_on_surface(surf, np.vstack([W, W[:1]]), 0.016, 0.006, 0.0,
                                                                           r=0.0025))
        for j, d in enumerate(doors):
            _side_door(surf, views, s, d, side, sgn, vname, j, add, panel, S)
    return out, S


DEBUG: list = []


def _hole_part(surf, views, band, h, H, add, panel, S, s):
    """Что стоит в проёме полосы: стекло, табло, фара, фонарь, решётка, люк двигателя, задние двери."""
    view = band["view"]
    nm = h["name"]
    if h.get("glass") is True:
        panel("Glass_" + nm, "glass", view, H, h=0.05, gap=0.004, flange=0.02, fit_deg=3, fit_blend=0.04)
        add("Seal_" + nm, "rubber", *pt.strip_on_surface(surf, np.vstack([H, H[:1]]), 0.018, 0.007, 0.0, r=0.003))
    elif h.get("glass") == "display":
        panel("Display_" + nm, "display", view, H, h=0.03, gap=0.003, flange=0.03)
        add("Display_Back_" + nm, "mesh_black", *pt.backing(surf, views[view], H, 0.05))
    elif h.get("lamp"):
        mat = "lamp_red" if h["lamp"] == "tail" else "lamp_glass"
        panel("Lamp_" + nm, mat, view, H, h=0.012, gap=0.003, flange=0.035)
        add("Lamp_Back_" + nm, "lamp_red_inner" if h["lamp"] == "tail" else "lamp_inner", *pt.backing(surf, views[view], H, 0.05))
        if h["lamp"] in ("head", "head2"):
            c = H.mean(0)
            nn = surf.normal(c[None])[0]
            u0, u1, v0, v1, r = h["rect"]
            n_l = 2 if h["lamp"] == "head2" else 1
            for k in range(n_l):
                xc = u0 + (u1 - u0) * ((k + 0.5) / n_l if n_l > 1 else 0.62)
                p = views[view].lift(surf, np.array([[xc, (v0 + v1) / 2]]))[0] - nn * 0.03
                P = np.linspace(p - nn * 0.03, p, 4)
                T, N, B = pt.frames(P, np.array([0, 0, 1.0]))
                rr = min(u1 - u0, v1 - v0) * 0.36
                circ = np.c_[np.cos(np.linspace(0, 2 * math.pi, 24, endpoint=False)),
                             np.sin(np.linspace(0, 2 * math.pi, 24, endpoint=False))] * rr
                add(f"Lamp_Lens_{nm}{k}", "chrome", *pt.loft(P, N, B, circ, cap=True))
    elif h.get("grille"):
        add("Grille_Back_" + nm, "mesh_black", *pt.backing(surf, views[view], H, 0.06))
        u0, u1, v0, v1, r = h["rect"]
        zs = list(np.linspace(v0 + 0.03, v1 - 0.03, h["grille"]))
        add("Grille_Bars_" + nm, "trim_black", *pt.fins_in_loop(surf, views[view], H, zs, t=0.014, depth=0.04,
                                                                 recess=0.012, margin=0.01))
    elif h.get("hatch"):
        # люк двигателя: крышка в проёме с жалюзи
        from vlib import loop_on_surface
        inner = loop_on_surface(surf, views[view], H, 0.02, 0.006, False)
        panel("Engine_Hatch", "paint", view, inner, group="hatch", h=0.03, gap=GAP, flange=0.03)
        u0, u1, v0, v1, r = h["rect"]
        lv = rect_loop(u0 + 0.12, u1 - 0.12, v0 + 0.55, v1 - 0.10, 0.03)
        LV = lift_poly(surf, views[view], np.vstack([lv, lv[:1]]), 0.004)[:-1]
        zs = list(np.arange(v0 + 0.60, v1 - 0.12, 0.045))
        add("Engine_Louvers", "trim_black", *pt.fins_in_loop(surf, views[view], LV, zs, t=0.010, depth=0.03, recess=-0.004,
                                                            margin=0.004), "hatch")
        add("Engine_Louver_Back", "mesh_black", *pt.backing(surf, views[view], LV, 0.03), "hatch")
    elif h.get("doors") == "swing2":
        # задние распашные двери: две створки с окнами
        u0, u1, v0, v1, r = h["rect"]
        mid = (u0 + u1) / 2
        for k, (a, b) in enumerate(((mid + 0.004, u1 - 0.006), (u0 + 0.006, mid - 0.004))):
            ring = rect_loop(a, b, v0 + 0.006, v1 - 0.006, 0.03)
            D = lift_poly(surf, views[view], np.vstack([ring, ring[:1]]), 0.004)[:-1]
            wr = rect_loop(a + 0.07, b - 0.07, v0 + 0.62, v1 - 0.10, 0.04)
            WW = lift_poly(surf, views[view], np.vstack([wr, wr[:1]]), 0.004)[:-1]
            grp = "rdoor_l" if k == 0 else "rdoor_r"
            panel(f"Rear_Door_{'L' if k == 0 else 'R'}", "paint", view, D, holes=[WW], group=grp, h=0.03, gap=GAP,
                  flange=0.05, hole_depth=0.03)
            panel(f"Glass_Rear_Door_{'L' if k == 0 else 'R'}", "glass", view, WW, group=grp, h=0.04, gap=0.004, flange=0.02,
                  fit_deg=2, fit_blend=0.03)
            hz = (v0 + v1) / 2 - 0.05
            hp = views[view].lift(surf, np.array([[a + 0.10 if k == 0 else b - 0.10, hz]]))[0]
            add(f"Rear_Door_Handle_{'L' if k == 0 else 'R'}", "trim_black",
                *rounded_block(hp + surf.normal(hp[None])[0] * 0.012, 0.03, 0.03, 0.14, 0.012), grp)
        S["rear_doors"] = h["rect"]


def _side_door(surf, views, s, d, side, sgn, vname, j, add, panel, S):
    """Дверь в проёме борта: «гармошка» из двух створок, сдвижная или распашная (как у легковой)."""
    lay = s["lay"]
    zs = lay["rim"]["z_sbot"]
    view = views[vname]
    y0, y1, zt = d["y0"], d["y1"], d["z_top"]
    grp = f"door_{side.lower()}{j + 1}"
    if d["kind"] == "fold2":
        # створки — алюминиевая рамка трубой и стекло, утоплены на 3 см от борта, по две на проём
        mid = (y0 + y1) / 2
        z_b = max(zs, lay.get("floor_z", zs)) - 0.02 if s["kind"] != "bus" else zs + 0.01
        for k, (a, b) in enumerate(((y0 + 0.012, mid - 0.006), (mid + 0.006, y1 - 0.012))):
            ys = np.array([a, b])
            P = view.lift(surf, np.array([[(a + b) / 2, (z_b + zt) / 2]]))[0]
            x = P[0] - sgn * 0.035
            outline = rect_loop(a, b, z_b + 0.01, zt - 0.012, 0.025)
            path = np.c_[np.full(len(outline), x), outline[:, 0], outline[:, 1]]
            path = np.vstack([path, path[:1]])
            T, N, Bv = pt.frames(path, np.array([1.0, 0, 0]))
            frame = pt.loft(path, N, Bv, pt.rounded_rect(0.055, 0.035, 0.008, 2), cap=False)
            rail = rounded_block((x, (a + b) / 2, z_b + 0.42), 0.035, b - a - 0.04, 0.06, 0.01)
            glass_poly = rect_loop(a + 0.03, b - 0.03, z_b + 0.05, zt - 0.05, 0.02)
            pv, pf = pt.poly_mesh(glass_poly)
            gV = np.c_[np.full(len(pv), x), pv[:, 0], pv[:, 1]]
            gF = [f[::-1] for f in pf] if sgn < 0 else pf
            leaf = f"{grp}{'ab'[k]}"
            add(f"Door_{side}{j + 1}{'AB'[k]}_Frame", "steel_dark", *pt.merge([frame, rail]), leaf)
            add(f"Door_{side}{j + 1}{'AB'[k]}_Glass", "glass", gV, gF, leaf)
        # ступени входа и рамка проёма
        z_floor = lay.get("floor_z", 0.36)
        if z_floor - zs > 0.2:
            for st in range(int((z_floor - zs) / 0.2)):
                zz = zs + 0.18 * (st + 1)
                xb = view.lift(surf, np.array([[(y0 + y1) / 2, zz]]))[0][0]
                add(f"Step_{side}{j + 1}_{st}", "rubber", *rounded_block((xb - sgn * (0.18 + 0.25 * st), (y0 + y1) / 2, zz),
                                                                       0.30, y1 - y0 - 0.04, 0.03, 0.01))
        return
    # дверь кузова панелью: «car» — на петлях спереди, «slide» — сдвижная назад
    z_b = zs + 0.004
    ring = fillet_poly([(y0 + 0.003, z_b), (y1 - 0.003, z_b), (y1 - 0.003, zt - 0.003), (y0 + 0.003, zt - 0.003)],
                       [0.02, 0.02, 0.06, 0.06], closed=True, n_arc=6)
    D = lift_poly(surf, view, np.vstack([ring, ring[:1]]), 0.005)[:-1]
    wz0, wz1 = d["win"]
    wr = rect_loop(y0 + 0.07, y1 - 0.07, wz0, wz1, 0.04)
    W = lift_poly(surf, view, np.vstack([wr, wr[:1]]), 0.005)[:-1]
    panel(f"Door_{side}{j + 1}", "paint", vname, D, holes=[W], group=grp, h=0.03, gap=GAP, flange=0.08, hole_depth=0.03)
    panel(f"Glass_Door_{side}{j + 1}", "glass", vname, W, group=grp, h=0.04, gap=0.004, flange=0.02, fit_deg=2, fit_blend=0.03)
    add(f"Door_Card_{side}{j + 1}", "interior", *pt.backing(surf, view, D, 0.08), grp)
    hy = y1 - 0.16 if d["kind"] == "car" else y0 + 0.14
    line = view.lift(surf, np.c_[np.linspace(hy - 0.07, hy + 0.07, 12), np.full(12, wz0 - 0.16)])
    add(f"Door_Handle_{side}{j + 1}", "trim_black", *pt.strip_on_surface(surf, line, 0.03, 0.014, 0.003, r=0.006), grp)
    S.setdefault("panel_doors", []).append((grp, d, side))
    if d["kind"] == "slide":
        # направляющая сдвижной двери по борту
        rail = view.lift(surf, np.c_[np.linspace(y0 + 0.2, y1 + 0.75, 20), np.full(20, wz1 + 0.06)])
        add(f"Slide_Rail_{side}", "trim_black", *pt.strip_on_surface(surf, rail, 0.025, 0.012, 0.0, r=0.004))


# =============================================================================== колёса грузового типа

def truck_wheel(spec: dict, inner: bool = False):
    """Колесо: шина, штампованный диск с вентиляционными окнами, ступица, гайки по окружности; inner —
    внутреннее колесо пары (лицом внутрь)."""
    from carparts import tire, rim_barrel
    R, W = spec["tire_r"], spec["tire_w"]
    rim_r = spec["rim_d_in"] * 0.0127
    x0 = W / 2 * 0.86
    face = revolve([(x0 - 0.004, rim_r + 0.004), (x0 - 0.02, rim_r - 0.02), (x0 - 0.05, rim_r * 0.72),
                    (x0 - 0.05, rim_r * 0.55), (x0 - 0.02, rim_r * 0.45), (x0 - 0.02, 0.0)], 72)
    holes = []
    for i in range(6 if rim_r > 0.25 else 5):
        n = 6 if rim_r > 0.25 else 5
        a = (i + 0.5) * 2 * math.pi / n
        k = 16
        t = np.linspace(0, 2 * math.pi, k, endpoint=False)
        r0 = rim_r * 0.635
        pts = [(x0 - 0.048, (r0 + rim_r * 0.07 * math.cos(th)) * math.cos(a + 0.16 * math.sin(th)),
                (r0 + rim_r * 0.07 * math.cos(th)) * math.sin(a + 0.16 * math.sin(th))) for th in t]
        P = np.array(pts)
        V = np.vstack([P, P.mean(0)[None]])
        holes.append((V, [(q, (q + 1) % k, k) for q in range(k)]))
    hub = revolve([(x0 - 0.02, 0.0), (x0 - 0.02, 0.11), (x0 + 0.03, 0.10), (x0 + 0.06, 0.07), (x0 + 0.07, 0.0)], 48)
    nuts = []
    ns = spec.get("studs", 10)
    for i in range(ns):
        a = i * 2 * math.pi / ns
        v, f = revolve([(x0 - 0.02, 0.0), (x0 - 0.02, 0.014), (x0 + 0.012, 0.014), (x0 + 0.016, 0.009),
                        (x0 + 0.017, 0.0)], 6, phase=math.pi / 6)
        rr = 0.142 if rim_r > 0.25 else 0.09
        v[:, 1] += rr * math.cos(a)
        v[:, 2] += rr * math.sin(a)
        nuts.append((v, f))
    parts = [("Tire", "rubber", *tire(R, W, rim_r, 96)), ("Rim_Barrel", "rim_steel", *rim_barrel(rim_r, W, 96)),
             ("Rim_Face", "rim_steel", *face), ("Rim_Holes", "mesh_black", *pt.merge(holes)), ("Hub", "steel_dark", *hub),
             ("Lug_Nuts", "steel_dark", *pt.merge(nuts))]
    if inner:
        parts = [(n, m, V * np.array([-1.0, 1, 1]), [f[::-1] for f in F]) for n, m, V, F in parts if n != "Hub" and n != "Lug_Nuts"]
    return parts


# =============================================================================== детали

def _arm(p0, p1, p2, r: float):
    """Кронштейн зеркала: труба по квадратичной кривой Безье p0 → p2 с контрольной точкой p1."""
    t = np.linspace(0, 1, 24)[:, None]
    P = (1 - t) ** 2 * np.asarray(p0) + 2 * (1 - t) * t * np.asarray(p1) + t ** 2 * np.asarray(p2)
    T, N, B = pt.frames(P, np.array([0, 0, 1.0]) if abs(P[-1, 2] - P[0, 2]) < 0.5 else np.array([1.0, 0, 0]))
    ang = np.linspace(0, 2 * math.pi, 10, endpoint=False)
    return pt.loft(P, N, B, np.c_[np.cos(ang), np.sin(ang)] * r, cap=True)


def details(surf, f, s: dict, views: dict, S: dict) -> list:
    out = []
    lay = s["lay"]
    kind = s["kind"]
    hw = s["width"] / 2
    yn = float(f.front(0.8))
    yt = float(f.rear(1.0))
    zs = lay["rim"]["z_sbot"]

    def add(name, mat, mesh, group="body"):
        out.append((name, mat, mesh[0], mesh[1], group))

    # бамперы: брус по лицу и корме, с заходом на углы
    for nm, view, z0, z1, ylim in (("Bumper_F", "front", zs - 0.02, zs + (0.20 if kind != "paz" else 0.16), None),
                                   ("Bumper_R", "rear", lay["rim"]["z_rbot"] - 0.02, lay["rim"]["z_rbot"] + 0.16, None)):
        zc = (z0 + z1) / 2
        xs = np.linspace(-hw + 0.06, hw - 0.06, 60)
        line = views[view].lift(surf, np.c_[xs, np.full(len(xs), zc)])
        nrm = surf.normal(line)
        nrm[:, 2] = 0
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
        path = line + nrm * 0.035
        sec = pt.rounded_rect(0.10, z1 - z0, 0.03, 3)
        add(nm, "bumper_plastic", pt.loft(path, nrm, np.broadcast_to(np.array([0, 0, 1.0]), path.shape), sec, cap=True))
    # номера
    from carparts import plate
    pf = views["front"].lift(surf, np.array([[0.0, zs + 0.09]]))[0]
    add("Plate_Front", "plate", plate(pf + np.array([0, -0.10, 0]), np.array([0, -1.0, 0])))
    pr = views["rear"].lift(surf, np.array([[0.0 if kind != "gazel" else 0.0, lay["rim"]["z_rbot"] + 0.07]]))[0]
    add("Plate_Rear", "plate", plate(pr + np.array([0, 0.10, 0]), np.array([0, 1.0, 0])))
    # зеркала: на автобусе и ПАЗе — на изогнутых кронштейнах вперёд, у ГАЗели — на дверях
    for sgn, sd in ((1.0, "L"), (-1.0, "R")):
        if kind in ("bus", "paz"):
            z_a = 2.28 if kind == "bus" else 2.30
            base = np.array([sgn * (hw - 0.03), yn + 0.30, z_a])
            p1 = np.array([sgn * (hw + 0.10), yn - 0.10, z_a + 0.02])
            p2 = np.array([sgn * (hw + 0.16), yn - 0.32, z_a - 0.18])
            arm = _arm(base, p1, p2, 0.018)
            head = rounded_block(p2 + np.array([0, 0, -0.22]), 0.08, 0.20, 0.38, 0.04)
            glass = rounded_block(p2 + np.array([0, 0.105, -0.22]), 0.07, 0.006, 0.34, 0.002)
        else:
            base = views["side" if sgn > 0 else "side_r"].lift(surf, np.array([[-0.93, 1.30]]))[0]
            p2 = base + np.array([sgn * 0.20, -0.04, 0.05])
            arm = _arm(base, base + np.array([sgn * 0.10, -0.02, 0.08]), p2, 0.012)
            head = rounded_block(p2 + np.array([sgn * 0.06, 0, 0.0]), 0.12, 0.07, 0.24, 0.03)
            glass = rounded_block(p2 + np.array([sgn * 0.06, 0.037, 0.0]), 0.10, 0.004, 0.21, 0.002)
        add(f"Mirror_Arm_{sd}", "trim_black", arm, "body" if kind != "gazel" else f"door_{sd.lower()}1")
        add(f"Mirror_Head_{sd}", "trim_black", head, "body" if kind != "gazel" else f"door_{sd.lower()}1")
        add(f"Mirror_Glass_{sd}", "chrome", glass, "body" if kind != "gazel" else f"door_{sd.lower()}1")
    # дворники
    ws_band = [b for b in lay["bands"] if any(h.get("glass") is True and h["name"].startswith(("ws", "windshield"))
                                             for h in b["holes"])]
    if ws_band:
        b = ws_band[0]
        hs = [h for h in b["holes"] if h.get("glass") is True and h["name"].startswith(("ws", "windshield"))]
        av = views[hs[0].get("author", b["view"])] if hs[0].get("author") else views["front"]
        v0 = min(h["rect"][2] for h in hs)
        u_l = max(h["rect"][1] for h in hs)
        for k, (xa, xb) in enumerate(((0.06, u_l * 0.86), (-u_l * 0.86, -0.06))):
            line = av.lift(surf, np.c_[np.linspace(xa, xb, 30), np.full(30, v0 + 0.06)])
            add(f"Wiper_{k}", "trim_black", pt.strip_on_surface(surf, line, 0.02, 0.012, 0.004, r=0.004))
    # крыша: кондиционер, люки, антенна (автобус, ПАЗ)
    if kind == "bus":
        zr = float(f.top(0.0))
        add("Roof_AC", "paint", rounded_block((0.0, 0.2, zr + 0.10), 1.90, 2.6, 0.20, 0.08))
        for y in (-0.3, 0.7):
            add(f"AC_Fan_{y}", "mesh_black", rounded_block((0.45 if y < 0 else -0.45, y + 0.2, zr + 0.205), 0.52, 0.52, 0.01, 0.2))
        for y in (-3.6, 3.8):
            add(f"Roof_Hatch_{y}", "trim_black", rounded_block((0.0, y, zr + 0.03), 0.80, 0.80, 0.07, 0.03))
    elif kind == "paz":
        zr = float(f.top(0.0))
        for y in (-1.2, 1.4):
            add(f"Roof_Hatch_{y}", "trim_black", rounded_block((0.0, y, zr + 0.025), 0.70, 0.70, 0.06, 0.03))
    # габаритные огни по борту (автобус, ПАЗ): оранжевые на юбке
    if kind in ("bus", "paz"):
        for sgn, vn in ((1.0, "side"), (-1.0, "side_r")):
            for y in np.linspace(yn + 1.2, yt - 1.2, 4):
                p = views[vn].lift(surf, np.array([[y, zs + 0.12]]))[0]
                add(f"Marker_{'LR'[sgn < 0]}_{y:.1f}", "lamp_amber", rounded_block(p + np.array([sgn * 0.008, 0, 0]), 0.02, 0.10, 0.04, 0.008))
    # брызговики за колёсами
    for y in s["wheel_y"]:
        for sgn in (1.0, -1.0):
            x = sgn * (hw - 0.18)
            add(f"Mudflap_{y:.1f}_{'LR'[sgn < 0]}", "rubber",
                rounded_block((x, y + s["arch_r"] + 0.02, s["wheel_z"] - 0.10), 0.30 if kind != "gazel" else 0.22, 0.012, 0.42, 0.004))
    # подкрылки
    for y in s["wheel_y"]:
        for sgn, sd in ((1.0, "L"), (-1.0, "R")):
            V, F = pt.wheel_liner(y, s["wheel_z"], s["arch_r"] + 0.01, s["well_x"], hw - 0.02, phi0=-10.0, phi1=190.0)
            if sgn < 0:
                V, F = mirror_mesh(V, F)
            out.append((f"Liner_{y:.1f}_{sd}", "liner", V, F, "body"))
    # днище: плита и выхлоп
    y0, y1 = yn + 0.3, yt - 0.3
    z_u = zs - 0.03 if kind == "bus" else zs - 0.05
    add("Under_Tray", "liner", rounded_block((0.0, (y0 + y1) / 2, z_u), 2 * hw - 0.30, y1 - y0, 0.02, 0.01))
    if kind != "bus":
        add("Frame", "steel_dark", pt.merge([rounded_block((sx * 0.45, (y0 + y1) / 2, z_u - 0.10), 0.07, y1 - y0, 0.14, 0.01)
                                             for sx in (1, -1)]))
        ex = tube([(-0.35, 0.0, z_u - 0.08), (-0.40, yt - 0.6, z_u - 0.08), (-0.42, yt - 0.05, z_u - 0.06)], 0.03, 10, 20)
        add("Exhaust", "steel_dark", ex)
    else:
        add("Exhaust", "steel_dark", tube([(-0.85, yt - 0.9, z_u + 0.05), (-0.95, yt - 0.25, z_u + 0.0)], 0.05, 12, 6))
    # мосты: задний (балка с редуктором)
    yr = s["wheel_y"][1]
    add("Rear_Axle", "steel_dark", pt.merge([tube([(-s["track_r"] / 2 + 0.1, yr, s["wheel_z"]), (s["track_r"] / 2 - 0.1, yr, s["wheel_z"])],
                                                  0.07 if kind != "gazel" else 0.045, 12, 4),
                                             rounded_block((0.12, yr, s["wheel_z"]), 0.36, 0.36, 0.34, 0.12)]))
    return out


# =============================================================================== салон

def seat_bus(x: float, y: float, z_floor: float, width: float = 0.44, facing: float = -1.0):
    """Сиденье автобуса: пластиковая чаша (подушка и спинка), рамка на стойке, поручень на спинке."""
    from interior import rot
    zc = z_floor + 0.45
    cush = rounded_block((x, y, zc), width, 0.42, 0.07, 0.025)
    yb = y + 0.21 * -facing
    back = rounded_block((x, yb, zc + 0.36), width, 0.06, 0.66, 0.025)
    back = (rot(back[0], rx=0.10 * facing, about=(x, yb, zc)), back[1])
    leg = tube([(x, y, z_floor), (x, y, zc - 0.04)], 0.02, 8, 3)
    grip = tube([(x - width / 2 + 0.05, yb, zc + 0.70), (x + width / 2 - 0.05, yb, zc + 0.70)], 0.012, 8, 3)
    return pt.merge([cush, back]), pt.merge([leg, grip])


def interior(f, s: dict, S: dict) -> list:
    lay = s["lay"]
    kind = s["kind"]
    out = []
    hw = s["width"] / 2 - 0.09
    zf = lay.get("floor_z", 0.4)
    yn = float(f.front(1.0)) + 0.20
    yt = float(f.rear(1.0)) - 0.15
    zr = float(f.top(0.0)) - max(0.10, s["r_roof"] * 0.85)
    # где начинается салон: у ГАЗели — за моторным щитом (основание лобового), у автобусов — от лица
    y_cab = lay.get("cab_y", yn)
    ys_t = np.linspace(yn, yt, 400)
    y_ceil = float(ys_t[np.argmax(f.top(ys_t) > zr + 0.05)])

    def add(name, mat, mesh):
        out.append((name, mat, mesh[0], mesh[1], "body"))

    # пол (у автобуса — ступенька к заднему площадке), потолок
    if kind == "bus":
        ys = lay["floor_step_y"]
        add("Floor_Front", "floor_rubber", rounded_block((0.0, (yn + ys) / 2, zf - 0.015), 2 * hw, ys - yn, 0.03, 0.01))
        add("Floor_Rear", "floor_rubber", rounded_block((0.0, (ys + yt) / 2, lay["floor_rear_z"] - 0.015), 2 * hw, yt - ys,
                                                        0.03, 0.01))
        add("Floor_Step", "floor_rubber", rounded_block((0.0, ys, (zf + lay["floor_rear_z"]) / 2), 2 * hw, 0.04,
                                                        lay["floor_rear_z"] - zf, 0.01))
    else:
        add("Floor", "floor_rubber", rounded_block((0.0, (y_cab + yt) / 2, zf - 0.015), 2 * hw, yt - y_cab, 0.03, 0.01))
    hc = hw - s["r_roof"] * 0.5
    yc0 = max(y_ceil, y_cab) + 0.15 + s["r_roof"] * 0.5
    add("Ceiling", "headliner", rounded_block((0.0, (yc0 + yt - 0.1) / 2, zr), 2 * hc, yt - 0.1 - yc0, 0.02, 0.01))
    # место водителя: кресло, панель, руль, перегородка
    y_drv = y_cab + (0.85 if kind == "bus" else (0.60 if kind == "paz" else 0.80))
    x_drv = hw - 0.40
    from interior import seat
    z_dash = zf + (0.62 if kind != "gazel" else 0.36)
    add("Driver_Seat", "seat", seat(x_drv, y_drv, zf + (0.30 if kind != "gazel" else 0.12), width=0.50, back_h=0.62,
                                     tilt=0.25))
    add("Dash", "interior", rounded_block((0.0 if kind == "gazel" else x_drv - 0.2, y_cab + 0.18, z_dash),
                                          2 * hw - 0.1 if kind == "gazel" else 1.2, 0.36, 0.30, 0.06))
    sw = revolve([(0.016 * math.cos(a), 0.22 + 0.016 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 10, endpoint=False)],
                 48, closed=True)
    from interior import rot
    Vw = rot(sw[0][:, [1, 0, 2]], rx=math.radians(55 if kind != "gazel" else 30)) + np.array([x_drv, y_cab + 0.45,
                                                                                               z_dash + 0.20])
    add("Steering_Wheel", "interior", (Vw, sw[1]))
    if kind != "gazel":
        add("Driver_Partition", "interior", rounded_block((x_drv - 0.10, y_drv + 0.45, zf + 0.75), 0.9, 0.04, 1.45, 0.02))
    # пассажирские сиденья рядами вдоль окон (у дверей — проход)
    doors_r = lay["doors_r"]

    def near_door(y, sgn):
        if sgn > 0:
            return False
        return any(d["y0"] - 0.25 < y < d["y1"] + 0.35 for d in doors_r)

    pitch = 0.78 if kind == "bus" else 0.74
    y_start = y_drv + (1.10 if kind == "bus" else 0.85)
    seats, frames = [], []
    for sgn in (1.0, -1.0):
        y = y_start
        while y < yt - 0.45:
            if not near_door(y, sgn):
                zfl = zf if kind != "bus" or y < lay["floor_step_y"] else lay["floor_rear_z"]
                for k in range(2 if kind != "gazel" or sgn > 0 else 1):
                    x = sgn * (hw - 0.26 - k * 0.46)
                    a, b = seat_bus(x, y, zfl)
                    seats.append(a)
                    frames.append(b)
            y += pitch
    add("Passenger_Seats", "seat_plastic", pt.merge(seats))
    add("Seat_Frames", "steel_dark", pt.merge(frames))
    # поручни: вертикальные стойки у прохода и две продольные под потолком
    if kind in ("bus", "paz"):
        poles = []
        for y in np.arange(y_start - 0.3, yt - 0.6, 1.5 if kind == "bus" else 1.2):
            for sgn in (1.0, -1.0):
                zfl = zf if kind != "bus" or y < lay["floor_step_y"] else lay["floor_rear_z"]
                poles.append(tube([(sgn * 0.32, y, zfl), (sgn * 0.32, y, zr - 0.01)], 0.017, 10, 3))
        for sgn in (1.0, -1.0):
            poles.append(tube([(sgn * 0.32, yn + 0.9, zr - 0.12), (sgn * 0.32, yt - 0.5, zr - 0.12)], 0.016, 10, 3))
        add("Handrails", "rail_yellow", pt.merge(poles))
    return out
