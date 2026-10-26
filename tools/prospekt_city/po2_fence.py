"""Забор района «Проспекта»: секция из плиты ПО-2 с колючкой поверх (набор district_fence, 447 штук на карте).

Плита ПО-2 (серия ИЖ 31-77): 2500 × 3000 × 150 мм, ≈ 1,43 т; с лицевой стороны — поле 5 × 4 пирамид по 450 мм
в рамке 125 мм, ниже — гладкая утопленная полоса 310 мм, по краям снизу две «ноги» 470 мм, уходящие в стакан
фундамента (по чертежу завода, железобетон43.рф). Плиты ставят встык, без столбов. Над землёй — тело 2,5 м.
Поверх — Y-кронштейн из уголка 40×4 у стыка, две нити колючей проволоки по концам кронштейна и спираль АКЛ
Ø 600 мм (лента 22 мм с шипами на сердечнике 2,5 мм), 10 витков на секцию — витки соседних секций сходятся.

Оси: длина плиты — Blender Y (игровая Z), толщина — X; рельеф на +X. Стык со стаканом — у Y = −1,25
(игровое +1,25, как столбик серого набора). Начало координат — земля в середине секции.
"""
from __future__ import annotations

import math

import numpy as np

import clib as C

L = 2.5            # шаг секций на карте
LP = 2.49          # плита: 2490 мм по факту (ПО-2* 2490 × 3000 × 158) — между плитами щель 10 мм
T = 0.15           # толщина рамки
XF, XB = T / 2, -T / 2                 # лицевая и тыльная плоскости
X_WEB = XB + 0.050                    # поле пирамид: стенка 50 мм, пирамида +50 — вершины на 50 мм ниже рамки
X_TIP = XB + 0.100                     # (так сходится объём из паспорта: 0,566 м³)
X_PANEL = XB + 0.100                   # утопленная полоса: 100 мм
ZB = 0.10          # низ тела плиты над землёй (ноги — в стакане, верх стакана +0,05)
CH = 0.030         # откос рамки к полю и полосе
SIDE = 0.125       # рамка сбоку (вместе с откосом)
CELL = 0.45
ROWS, COLS = 4, 5


def zl() -> dict:
    """Высотные отметки тела плиты снизу вверх (сумма 2,5 м по чертежу)."""
    z = ZB
    out = {"bot": z}
    z += 0.110
    out["pan_ch0"] = z
    z += CH
    out["pan0"] = z
    z += 0.310
    out["pan1"] = z
    z += CH
    out["pan_ch1"] = z
    z += 0.080
    out["fld_ch0"] = z
    z += CH
    out["fld0"] = z
    z += CELL * ROWS
    out["fld1"] = z
    z += CH
    out["fld_ch1"] = z
    z += 0.080
    out["top"] = z
    return out


Z = zl()
Y_IN = LP / 2 - SIDE           # граница поля/полосы
Y_CH = Y_IN + CH               # начало откоса


def plate_mesh(mb: C.MB, back_ngon: bool = False, apex: bool = False) -> None:
    """Тело плиты одной замкнутой сеткой: лицевая сетка линий, тыльная плоскость, торцы.
    back_ngon — тыл одной гранью по контуру (игровая сетка: внутренние линии тыла не нужны)."""
    ys = [-LP / 2, -Y_CH, -Y_IN] + [(-Y_IN + CELL * k) for k in range(1, COLS)] + [Y_IN, Y_CH, LP / 2]
    zs = [Z["bot"], Z["pan_ch0"], Z["pan0"], Z["pan1"], Z["pan_ch1"], Z["fld_ch0"], Z["fld0"]]
    zs += [Z["fld0"] + CELL * k for k in range(1, ROWS)] + [Z["fld1"], Z["fld_ch1"], Z["top"]]
    ny, nz = len(ys), len(zs)
    eps = 1e-6

    def depth(y: float, z: float) -> float:
        if -Y_IN - eps <= y <= Y_IN + eps:
            if Z["fld0"] - eps <= z <= Z["fld1"] + eps:
                return X_WEB
            if Z["pan0"] - eps <= z <= Z["pan1"] + eps:
                return X_PANEL
        return XF

    V = []
    for z in zs:
        for y in ys:
            V.append((depth(y, z), y, z))
    fid = lambda i, j: j * ny + i  # noqa: E731
    F = []
    for j in range(nz - 1):
        for i in range(ny - 1):
            a, b, c, d = fid(i, j), fid(i + 1, j), fid(i + 1, j + 1), fid(i, j + 1)
            yc, zc = (ys[i] + ys[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
            in_field = -Y_IN < yc < Y_IN and Z["fld0"] < zc < Z["fld1"]
            if in_field:
                continue                                   # ячейки поля — пирамидами ниже
            dd = [V[k][0] for k in (a, b, c, d)]
            vals = sorted(set(round(x, 6) for x in dd))
            if len(vals) == 2:
                cnt = [sum(1 for x in dd if abs(x - v) < 1e-6) for v in vals]
                if 1 in cnt:                               # угол откоса: делим по диагонали через «чужую» вершину
                    odd_v = vals[cnt.index(1)]
                    k = [abs(x - odd_v) < 1e-6 for x in dd].index(True)
                    q = [a, b, c, d]
                    o = q[k]
                    opp = q[(k + 2) % 4]
                    n1, n2 = q[(k + 1) % 4], q[(k + 3) % 4]
                    F.append((o, n1, opp))
                    F.append((o, opp, n2))
                    continue
            F.append((a, b, c, d))
    # пирамиды поля: основание — узлы сетки, площадка 80 × 50 мм на 0,64 высоты ячейки (откос сверху короче)
    base = len(V)
    for r in range(ROWS):
        for c in range(COLS):
            i0, j0 = 3 + c - 1 + 1, 7 + r - 1  # индексы узлов: ys[2] = −Y_IN, zs[6] = fld0
            i0 = 2 + c
            j0 = 6 + r
            y0, y1 = ys[i0], ys[i0 + 1]
            z0, z1 = zs[j0], zs[j0 + 1]
            yc = (y0 + y1) / 2
            zc = z0 + (z1 - z0) * 0.64
            k = len(V)
            b00, b10, b11, b01 = fid(i0, j0), fid(i0 + 1, j0), fid(i0 + 1, j0 + 1), fid(i0, j0 + 1)
            if apex:                                   # игровая сетка: вершина-точка, площадка — в запекании
                V.append((X_TIP, yc, zc))
                F += [(b00, b10, k), (b10, b11, k), (b11, b01, k), (b01, b00, k)]
                continue
            V += [(X_TIP, yc - 0.04, zc - 0.025), (X_TIP, yc + 0.04, zc - 0.025), (X_TIP, yc + 0.04, zc + 0.025),
                  (X_TIP, yc - 0.04, zc + 0.025)]
            F += [(b00, b10, k + 1, k), (b10, b11, k + 2, k + 1), (b11, b01, k + 3, k + 2), (b01, b00, k, k + 3),
                  (k, k + 1, k + 2, k + 3)]
    # тыльная плоскость теми же линиями (без Т-стыков на торцах)
    bb = len(V)
    if back_ngon:
        ring = [(i, 0) for i in range(ny)] + [(ny - 1, j) for j in range(1, nz)] +                [(i, nz - 1) for i in range(ny - 2, -1, -1)] + [(0, j) for j in range(nz - 2, 0, -1)]
        bmap = {}
        for (i, j) in ring:
            bmap[(i, j)] = len(V)
            V.append((XB, ys[i], zs[j]))
        bid = lambda i, j: bmap[(i, j)]  # noqa: E731
        F.append(tuple(bmap[q] for q in ring[::-1]))
    else:
        for z in zs:
            for y in ys:
                V.append((XB, y, z))
        bid = lambda i, j: bb + j * ny + i  # noqa: E731
        for j in range(nz - 1):
            for i in range(ny - 1):
                F.append((bid(i, j), bid(i, j + 1), bid(i + 1, j + 1), bid(i + 1, j)))
    # торцы: низ, верх, бока
    for i in range(ny - 1):
        F.append((fid(i, 0), bid(i, 0), bid(i + 1, 0), fid(i + 1, 0)))
        F.append((fid(i, nz - 1), fid(i + 1, nz - 1), bid(i + 1, nz - 1), bid(i, nz - 1)))
    for j in range(nz - 1):
        F.append((fid(0, j), fid(0, j + 1), bid(0, j + 1), bid(0, j)))
        F.append((fid(ny - 1, j), bid(ny - 1, j), bid(ny - 1, j + 1), fid(ny - 1, j + 1)))
    mb.add(V, F, "concrete")
    _ = base


def legs(mb: C.MB) -> None:
    """Ноги: 185 мм вверху, 135 внизу (скос внутрь), 470 мм вниз от тела — в стакан."""
    for s in (-1, 1):
        yo = s * (LP / 2 - 0.020)
        poly = [(yo, ZB + 0.01), (yo, ZB - 0.47), (yo - s * 0.135, ZB - 0.47), (yo - s * 0.185, ZB - 0.36),
                (yo - s * 0.185, ZB + 0.01)]
        if s < 0:
            poly = poly[::-1]
        V, F = C.prism(poly, XB + 0.005, XF - 0.005, ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0))
        mb.add(V, F, "concrete")


def embeds(mb: C.MB) -> None:
    """Закладные П2 у ног (лицо и тыл) и монтажные петли сверху."""
    for s in (-1, 1):
        y = s * (LP / 2 - 0.11)
        for x in (XF + 0.002, XB - 0.002):
            mb.extend(C.box((x, y, ZB + 0.05), (0.006, 0.10, 0.08)), "rust")


def lifting_loops(mb: C.MB, bend: tuple = (0.0, 0.0), n: int = 10, sides: int = 6) -> None:
    """Петли из арматуры Ø12 у торцов сверху (60 мм от края), торчат на 70 мм; bend — завал петли, °."""
    for k, s in enumerate((-1, 1)):
        y = s * (LP / 2 - 0.06)
        pts = []
        for i in range(n + 1):
            a = math.pi * i / n
            pts.append((0.035 * math.cos(a), y, Z["top"] + 0.045 + 0.035 * math.sin(a)))
        pts = [(0.035, y, Z["top"] - 0.06)] + pts + [(-0.035, y, Z["top"] - 0.06)]
        P = np.array(pts)
        if bend[k]:
            P = C.xf(P - (0, y, Z["top"]), C.rot("y", bend[k]), (0, y, Z["top"]))
        mb.extend(C.tube(P, 0.006, sides), "rebar")


def foundation(mb: C.MB, y: float, tilt=None, depth: float = 0.70) -> None:
    """Стакан фундамента под ноги двух плит у стыка: блок 600 × 450, над землёй 50 мм, раствор в стакане.
    depth — высота блока (в игре — только верх: остальное под землёй и в развёртке не нужно)."""
    V, F = C.box((0, y, 0.05 - depth / 2), (0.45, 0.60, depth))
    if tilt is not None:
        V = C.xf(V, *tilt)
    mb.add(V, F, "concrete_old")


def grout(mb: C.MB, y: float, tilt=None) -> None:
    """Раствор в стакане вокруг ног — чуть выше блока."""
    V, F = C.box((0, y, 0.050), (0.22, 0.38, 0.016))
    if tilt is not None:
        V = C.xf(V, *tilt)
    mb.add(V, F, "mortar")


# ---------------------------------------------------------------- колючка
H_TOP = Z["top"]
BR_Y = -L / 2 + 0.25            # кронштейн у стыка, на тыльной стороне; здесь виток спирали вверху — плечи между витками
SP_R = 0.30                      # спираль Ø 600
SP_Z = H_TOP + 0.20 + SP_R       # ось спирали
ARM = 30.0                       # развал плеч Y, ° от вертикали


def bracket(mb: C.MB, y: float = BR_Y, anchors: bool = True, clamps: bool = True) -> None:
    """Y-кронштейн: стойка из уголка 40×4 на двух анкерах по тылу плиты, два плеча под 30°, хомуты нитей."""
    prof = C.angle_profile(0.04, 0.004)
    stem0, stem1 = H_TOP - 0.42, H_TOP + 0.18
    # стойка: полка к тылу плиты (X−), вторая — поперёк
    P = np.array([(XB - 0.004, y, stem0), (XB - 0.004, y, stem1)])
    V, F = C.prism(prof, stem0, stem1, origin=(XB, y - 0.02, 0), ex=(-1, 0, 0), ey=(0, 1, 0), ez=(0, 0, 1))
    mb.add(V, F, "steel")
    _ = P
    for z in ((H_TOP - 0.33, H_TOP - 0.12) if anchors else ()):  # анкеры: шайба и гайка
        mb.extend(C.cyl((XB - 0.010, y + 0.002, z), 0.014, 0.004, 12, "x"), "galv")
        mb.extend(C.cyl((XB - 0.016, y + 0.002, z), 0.009, 0.010, 6, "x"), "galv")
        mb.extend(C.cyl((XB - 0.024, y + 0.002, z), 0.005, 0.016, 8, "x"), "galv")
    # плечи: из точки над стойкой, к лицу и к тылу; концы — на нитях
    top = np.array([XB - 0.02, y, stem1])
    for s in (-1, 1):
        a = math.radians(ARM)
        d = np.array([s * math.sin(a), 0.0, math.cos(a)])
        ln = 0.62
        end = top + d * ln
        Fr = C.frame_from(d, (0, 1, 0))
        V, F = C.prism(prof - 0.02, 0.0, ln, origin=top, ex=Fr[0], ey=Fr[1], ez=Fr[2])
        mb.add(V, F, "steel")
        # хомут нити на конце плеча
        if clamps:
            mb.extend(C.cyl(end + d * 0.01, 0.012, 0.03, 8, "y"), "galv")
    # косынка между плечами
    tri = [(0.0, 0.0), (0.10, 0.17), (-0.10, 0.17)]
    V, F = C.prism(tri, -0.003, 0.003, origin=top, ex=(1, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0))
    mb.add(V, F, "steel")


def arm_ends(y: float = BR_Y) -> list:
    top = np.array([XB - 0.02, y, H_TOP + 0.18])
    out = []
    for s in (-1, 1):
        a = math.radians(ARM)
        out.append(top + np.array([s * math.sin(a), 0.0, math.cos(a)]) * 0.62)
    return out


def barbed_strand(mb: C.MB, a, b, sag: float = 0.015, seed: int = 0) -> None:
    """Колючая проволока: две проволоки Ø 2 мм в скрутку (шаг 70 мм), четырёхточечные колючки через 120 мм."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    ln = float(np.linalg.norm(b - a))
    n = max(8, int(ln / 0.006))
    t = np.linspace(0, 1, n)
    C0 = a + np.outer(t, b - a)
    C0[:, 2] -= sag * 4 * t * (1 - t)
    Tn, N, B = C.path_frames(C0, (0, 0, 1))
    s = t * ln
    for ph in (0.0, math.pi):
        ang = s / 0.07 * 2 * math.pi + ph
        P = C0 + 0.0013 * (np.outer(np.cos(ang), N[0]) + np.outer(np.sin(ang), B[0]))
        mb.extend(C.tube(P, 0.001, 4), "wire")
    rng = np.random.default_rng(seed)
    k = 0.06
    while k < ln - 0.03:
        i = int(k / ln * (n - 1))
        p = C0[i]
        tdir = Tn[i]
        for q in range(4):
            ang = q * math.pi / 2 + rng.uniform(-0.3, 0.3)
            d = N[i] * math.cos(ang) + B[i] * math.sin(ang) + tdir * rng.uniform(-0.25, 0.25)
            d /= np.linalg.norm(d)
            mb.extend(C.tube(np.array([p, p + d * 0.014]), 0.001, 3, caps=True), "wire")
        mb.extend(C.tube(np.array([p - tdir * 0.006, p + tdir * 0.006]), 0.0022, 6), "wire")   # обмотка колючки
        k += 0.12


def razor_coil(mb: C.MB, y0: float, y1: float, turns: int, r: float = SP_R, z: float = SP_Z, x: float = XB - 0.02,
               squash=None, seed: int = 1) -> None:
    """Спираль АКЛ: сердечник Ø 2,5 мм и лента 22 × 0,5 мм на нём, шипы-лезвия парами по обе кромки через 37 мм."""
    n = turns * 120 + 1
    t = np.linspace(0, 1, n)
    ang = t * turns * 2 * math.pi
    rr = np.full(n, r) if squash is None else squash(t, ang) * r
    P = np.c_[x + rr * np.sin(ang), y0 + (y1 - y0) * t, z + rr * np.cos(ang)]
    mb.extend(C.tube(P, 0.00125, 5), "wire")
    # лента: ширина вдоль оси спирали (на поверхности витка), обжата на сердечнике
    Tn, N, B = C.path_frames(P, (0, 1, 0))
    axis = np.array([0.0, 1.0, 0.0])
    W = np.cross(Tn, np.c_[np.sin(ang), np.zeros(n), np.cos(ang)])   # касательная × радиус ≈ ось
    W /= np.linalg.norm(W, axis=1, keepdims=True)
    _ = axis
    half = 0.011
    rings = [np.vstack([P[i] - W[i] * half, P[i] + W[i] * half]) for i in range(n)]
    V, F = C.loft(rings, closed=False)
    mb.add(V, F, "razor")
    # шипы: на каждой кромке пара лезвий — вперёд-наружу и назад-наружу
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    s = 0.02
    Vb, Fb = [], []
    while s < seg[-1] - 0.02:
        i = int(np.searchsorted(seg, s))
        i = min(i, n - 1)
        p, tg, w = P[i], Tn[i], W[i]
        for side in (-1, 1):
            e = p + w * half * side
            for dirn in (-1, 1):
                k = len(Vb)
                Vb += [e - tg * 0.004 * dirn, e + tg * 0.009 * dirn, e + w * side * 0.012 + tg * 0.016 * dirn]
                Fb.append((k, k + 1, k + 2))
        s += 0.037
    mb.add(np.array(Vb), Fb, "razor")


def wire_ties(mb: C.MB, pts: list) -> None:
    for p in pts:
        mb.extend(C.tube(np.array([p, p + np.array([0, 0.002, -0.03])]), 0.0012, 4), "wire")


# ---------------------------------------------------------------- пролом
def breach_cutter(rng: np.random.Generator) -> tuple:
    """Пролом от тарана: рваный контур от земли до ~1,95 м, шире на тыльной стороне (выкол бетона)."""
    yc, w, h = 0.10, 1.30, 1.95
    m = 64
    ph = rng.uniform(0, 2 * math.pi, 4)

    def contour(grow: float, jit: float) -> list:
        pts = []
        for k in range(m):
            a = math.pi * k / (m - 1)
            low = 0.10 * math.sin(3 * a + ph[0]) + 0.06 * math.sin(7 * a + ph[1]) + 0.04 * math.sin(13 * a + ph[2])
            r = 1.0 + low + rng.uniform(-jit, jit)
            y = yc - math.cos(a) * w / 2 * r * grow
            z = max(0.0, math.sin(a) ** 0.6 * h * (1 + 0.6 * (r - 1)) * (1 + (grow - 1) * 0.5))
            pts.append((y, z))
        return [(pts[0][0], -0.6)] + pts + [(pts[-1][0], -0.6)]
    rings = []
    for x, grow, jit in ((XF + 0.25, 1.00, 0.0), (XF, 1.00, 0.035), (XF - 0.05, 1.03, 0.05), (XB + 0.05, 1.07, 0.05),
                         (XB, 1.14, 0.04), (XB - 0.25, 1.14, 0.0)):
        rings.append(np.array([(x, y, z) for y, z in contour(grow, jit)]))
    return C.loft(rings, closed=True, cap0=True, cap1=True)


RB_X = XB + 0.025                 # сетка — в середине стенки поля (50 мм)


def rebar_mesh(mb: C.MB, rng: np.random.Generator, hole_fn, sides: int = 6) -> None:
    """Арматурная сетка Ø 8 / 200 мм в теле плиты: стержни через пролом оборваны и загнуты по ходу тарана (−X)."""
    ys = np.arange(-1.10, 1.11, 0.20)
    zs = np.arange(ZB + 0.08, Z["top"] - 0.05, 0.20)
    for y in ys:                                     # вертикальные
        inside = [z for z in np.linspace(ZB, Z["top"], 200) if hole_fn(y, z)]
        if not inside:
            continue
        z_lo, z_hi = min(inside), max(inside)
        for z_edge, sgn in ((z_hi, -1), (z_lo, 1)):
            if z_edge <= ZB + 0.02 and sgn > 0:
                continue
            ln = rng.uniform(0.12, 0.45)
            bend = rng.uniform(0.6, 1.2)
            dy = rng.uniform(-0.05, 0.05)
            pts = []
            for k in range(9):
                u = k / 8 * ln
                pts.append((-math.sin(u / ln * bend) * u * 0.8, y + dy * u / ln,
                            z_edge + sgn * (0.02 + u * math.cos(u / ln * bend))))
            mb.extend(C.tube(np.array([(RB_X, y, z_edge - sgn * 0.08)] + [(p[0] + RB_X, p[1], p[2]) for p in pts]),
                             0.004, sides), "rebar")
    for z in zs:                                     # горизонтальные
        inside = [y for y in np.linspace(-1.2, 1.2, 240) if hole_fn(y, z)]
        if not inside:
            continue
        y_lo, y_hi = min(inside), max(inside)
        for y_edge, sgn in ((y_lo, 1), (y_hi, -1)):
            ln = rng.uniform(0.10, 0.38)
            bend = rng.uniform(0.5, 1.3)
            droop = rng.uniform(0.05, 0.25)
            pts = []
            for k in range(9):
                u = k / 8 * ln
                pts.append((-math.sin(u / ln * bend) * u * 0.8, y_edge + sgn * (0.02 + u * math.cos(u / ln * bend)),
                            z - u * droop))
            mb.extend(C.tube(np.array([(RB_X, y_edge - sgn * 0.08, z)] + [(p[0] + RB_X, p[1], p[2]) for p in pts]),
                             0.004, sides), "rebar")


def debris(mb: C.MB, rng: np.random.Generator, n: int = 26, small: bool = True) -> None:
    """Обломки по ходу тарана (тыльная сторона, −X): куски с пирамидами, крошка."""
    for k in range(n):
        big = k < 10
        s = np.r_[rng.uniform(0.16, 0.48, 2), rng.uniform(0.05, 0.10)] if big else             np.r_[rng.uniform(0.03, 0.10, 2), rng.uniform(0.02, 0.05)]
        x = -rng.uniform(0.15, 1.5 if big else 2.0)
        y = 0.10 + rng.normal(0, 0.5)
        V, F = C.irregular_chunk((0, 0, 0), s, rng, 0.22)
        tilt = rng.uniform(-18, 18) if big else rng.uniform(-40, 40)
        V = C.xf(V, C.rot("z", rng.uniform(0, 360)) @ C.rot("x", tilt), (x, y, s[2] * 0.4 + abs(tilt) / 400 * s[0]))
        if big or small:
            mb.add(V, F, "concrete")


# ---------------------------------------------------------------- варианты
def section(col, parent, variant: str = "intact", seed: int = 7) -> None:
    rng = np.random.default_rng(seed)
    body = C.MB()
    plate_mesh(body)
    ob = body.build("PO2_Plate", col, parent, bevel=0.010, seg=2, weld=1e-5)
    lg = C.MB()
    legs(lg)
    lg.build("PO2_Legs", col, parent, bevel=0.010, seg=2)
    if variant == "breach":
        cv, cf = breach_cutter(rng)
        cut = C.MB()
        cut.add(cv, cf, "concrete")
        cutter = cut.build("_cutter", col, parent)            # в тех же координатах, что и плита
        import bpy
        m = ob.modifiers.new("Пролом", "BOOLEAN")
        m.operation = "DIFFERENCE"
        m.solver = "EXACT"
        m.object = cutter
        bpy.context.view_layer.objects.active = ob
        # пролом — до фаски: модификатор наверх стека и применить
        with bpy.context.temp_override(object=ob):
            bpy.ops.object.modifier_move_to_index(modifier="Пролом", index=0)
            bpy.ops.object.modifier_apply(modifier="Пролом")
        bpy.data.objects.remove(cutter, do_unlink=True)
        poly = np.array(cv[:66, 1:])                     # передний контур (y, z) — для проверки «в проёме»

        def hole_fn(y: float, z: float) -> bool:
            return C.inside_poly(poly, y, z)
        rb = C.MB()
        rebar_mesh(rb, rng, hole_fn)
        rb.build("PO2_Rebar", col, parent)
        db = C.MB()
        debris(db, rng)
        db.build("PO2_Debris", col, parent, bevel=0.004, seg=1, sharp=20)
    det = C.MB()
    embeds(det)
    grout(det, -L / 2)
    lifting_loops(det, (0.0, 25.0 if variant != "intact" else 0.0))
    det.build("PO2_Embeds", col, parent)
    fnd = C.MB()
    foundation(fnd, -L / 2)
    fnd.build("PO2_Foundation", col, parent, bevel=0.012, seg=2)
    # колючка
    br = C.MB()
    bracket(br)
    br.build("PO2_Bracket", col, parent, bevel=0.0015, seg=1)
    wr = C.MB()
    ends = arm_ends()
    for k, e in enumerate(ends):
        barbed_strand(wr, (e[0], -L / 2, e[2]), (e[0], L / 2, e[2]), 0.012, seed + k)
    wr.build("PO2_BarbedWire", col, parent)
    rz = C.MB()
    if variant == "breach":
        # спираль над проломом просела: витки над проёмом опущены и смяты
        def squash(t, ang):
            yy = -L / 2 + L * t
            w = np.exp(-((yy - 0.1) / 0.55) ** 2)
            return 1.0 - 0.28 * w * (0.5 + 0.5 * np.cos(ang * 0.5))
        razor_coil(rz, -L / 2, L / 2, 10, squash=squash, seed=seed)
    else:
        razor_coil(rz, -L / 2, L / 2, 10, seed=seed)
    rz.build("PO2_RazorCoil", col, parent)


def fallen(col, parent, seed: int = 11) -> None:
    """Плита повалена наружу: лежит на земле рельефом вверх, стакан вывернут, спираль сползла рядом."""
    rng = np.random.default_rng(seed)
    body = C.MB()
    plate_mesh(body)
    legs(body)
    embeds(body)
    lifting_loops(body, (10.0, 40.0))
    V = np.vstack(body.V)
    # повернуть вокруг тыльной кромки низа ног (ось Y) на −91,5°: плита легла на −X рельефом вверх, тыльная
    # плоскость — снизу; ноги вырваны из стаканов и лежат на них, верх плиты — на земле
    R = C.rot("y", -91.5)
    piv = np.array([XB, 0.0, ZB - 0.47])
    body.V = [C.xf(V - piv, R, np.array([0.22, 0.0, 0.085]))]
    body.build("PO2_Plate", col, parent, bevel=0.010, seg=2, weld=1e-5)
    fnd = C.MB()
    foundation(fnd, -L / 2, (C.rot("y", -7.0), (0.0, 0.0, 0.02)))          # стаканы остались в земле, их повело
    foundation(fnd, L / 2, (C.rot("y", -5.0) @ C.rot("x", -3.0), (0.0, 0.0, 0.015)))
    # вывороченный грунт у стаканов
    for y in (-L / 2, L / 2):
        for k in range(7):
            V, F = C.irregular_chunk((0, 0, 0), rng.uniform(0.08, 0.22, 3) * (1, 1, 0.5), rng, 0.35)
            V = C.xf(V, C.rot("z", rng.uniform(0, 360)), (rng.uniform(-0.35, 0.25), y + rng.uniform(-0.35, 0.35), 0.02))
            fnd.add(V, F, "soil")
    fnd.build("PO2_Foundation", col, parent, bevel=0.012, seg=2)
    rz = C.MB()

    def squash(t, ang):
        return 0.75 + 0.1 * np.sin(ang * 0.37)
    razor_coil(rz, -L / 2 + 0.2, L / 2 - 0.1, 9, z=0.22, x=-3.20, squash=squash, seed=seed)
    rz.build("PO2_RazorCoil", col, parent)


VARIANTS = {"intact": "Секция", "breach": "Пролом", "fallen": "Повалена"}
STEP = 3.6
# выдача и проверочные виды (previews.py читает это без импорта): камера и цель — от начала варианта
META = {
    "folder": "Забор_ПО-2", "name": "PO2_Fence", "title": "Секция забора из плиты ПО-2 с колючкой",
    "step": 3.6,
    "shots": [["3/4 с лица", [3.6, -3.4, 2.2], [0.0, 0.0, 1.5], 30], ["3/4 с тыла", [-3.4, 3.2, 2.4], [0.0, 0.0, 1.5], 30],
              ["колючка крупно", [1.1, -1.5, 3.3], [-0.1, -0.7, 3.0], 35]],
    "game_shots": [["3/4 с лица", [3.4, -3.2, 1.9], [0.0, 0.0, 1.5], 30], ["3/4 с тыла", [-3.2, 3.0, 2.2], [0.0, 0.0, 1.5], 30],
                   ["с глаз, вблизи", [1.6, -1.1, 1.65], [0.0, -0.4, 1.3], 30]],
    "game_shots_by": {
        "fallen": [["3/4 с лица", [1.8, -4.2, 2.6], [-1.6, 0.0, 0.2], 30], ["3/4 с тыла", [-5.6, 3.4, 2.4], [-1.4, 0.0, 0.2], 30],
                   ["с глаз", [0.9, -2.2, 1.65], [-1.2, 0.0, 0.2], 30]],
    },
    "shots_by": {
        "breach": [["3/4 с лица", [3.4, -2.6, 1.8], [0.0, 0.1, 1.1], 30], ["3/4 с тыла", [-3.4, 2.6, 1.8], [-0.3, 0.1, 0.9], 30],
                   ["скол и арматура", [-1.3, -0.9, 1.4], [0.0, -0.2, 1.1], 35]],
        "fallen": [["3/4 с лица", [1.8, -4.2, 2.6], [-1.6, 0.0, 0.2], 30], ["3/4 с тыла", [-5.6, 3.4, 2.4], [-1.4, 0.0, 0.2], 30],
                   ["стаканы и ноги", [1.6, -2.0, 1.0], [0.0, -0.9, 0.2], 35]],
    },
}


def build(keys: list[str]) -> dict:
    out = {}
    for i, k in enumerate(keys):
        name = VARIANTS[k]
        col = C.collection(name)
        r = C.root(f"PO2 | {name}", col, (i * STEP, 0.0, 0.0))
        if k == "fallen":
            fallen(col, r)
        else:
            section(col, r, k)
        out[k] = name
    return out


# ================================================================ игровая версия (LOD0)
# Наборы Painter: PO2 — целая плита, ноги, стакан, раствор, петли, кронштейн (на 447 секциях и у повал. / голой);
# PO2Breach — плита с проломом, арматура, обломки. Спираль и нити — ленты с плиточной текстурой (Razor, Barbed).
# Закладные, анкеры, хомуты, фаски — только в запекании. Коллизия «Пролома» — по бокам и над проёмом, «Повалена» —
# низкий ящик по плите (по ней можно пройти), спираль без коллизии. Ящики коллизии — в осях Blender: [центр, размер].
GAME = {
    "ids": {"intact": "PC01_PO2", "breach": "PC01_PO2_BREACH", "fallen": "PC01_PO2_FALLEN", "bare": "PC01_PO2_BARE"},
    "extra": {"bare": "Без колючки"},
    "bake": ["intact", "breach"],
    "skip_high": ["PO2_RazorCoil", "PO2_BarbedWire"],
    # дальше 150 м спираль — меньше 4 пикселей и мелкий шум отсечения альфы: там секция без колючки (447 секций на карте)
    "lods": {"intact": [["intact", 150.0], ["bare", 520.0]]},
    "cells": {"intact": 32.0},                     # переход считается от центра клетки — клетка мелкая, ошибка ≤ 23 м
    "res": {"PO2": "11x10", "PO2Breach": "11x10"},     # 2048 × 1024: лицо и тыл плиты рядом
    "solids": {
        "breach": [[[-0.10, -0.93, 1.30], [0.65, 0.63, 2.60]], [[-0.10, 1.03, 1.30], [0.65, 0.43, 2.60]],
                   [[-0.10, 0.10, 2.70], [0.65, 1.50, 1.40]]],
        "fallen": [[[-1.30, 0.0, 0.17], [3.10, 2.50, 0.34]]],
    },
}
RAZOR_PERIOD = 0.074            # плитка ленты: две пары лезвий (шаг 37 мм)
REBAR_PERIOD = 0.080            # плитка прутка: 10 поперечных рёбер по 8 мм
RAZOR_W = 0.048                 # лента 22 мм + лезвия по кромкам
# плотность по видимости: торцы плиты закрыты соседними плитами (×0,15), верхний торец виден сверху (×0,5)
PLATE_UV_RULES = '[["y", 1, 0.9, 0.15], ["y", -1, 0.9, 0.15], ["z", 1, 0.9, 0.5]]'
BARB_PERIOD = 0.140             # плитка нити: два шага скрутки (70 мм) и одна колючка
BARB_W = 0.040


def coil_ribbon(mb: C.MB, y0: float, y1: float, turns: int, r: float = SP_R, z: float = SP_Z, x: float = XB - 0.02,
                squash=None, seg: int = 12) -> None:
    """Спираль для игры: лента по винтовой линии (вершины парами поперёк), лезвия и сердечник — в текстуре."""
    n = turns * seg + 1
    t = np.linspace(0, 1, n)
    ang = t * turns * 2 * math.pi
    rr = np.full(n, r) if squash is None else squash(t, ang) * r
    P = np.c_[x + rr * np.sin(ang), y0 + (y1 - y0) * t, z + rr * np.cos(ang)]
    Tn, _N, _B = C.path_frames(P, (0, 1, 0))
    W = np.cross(Tn, np.c_[np.sin(ang), np.zeros(n), np.cos(ang)])
    W /= np.linalg.norm(W, axis=1, keepdims=True)
    V = np.empty((2 * n, 3))
    V[0::2] = P - W * RAZOR_W / 2
    V[1::2] = P + W * RAZOR_W / 2
    F = [(2 * k, 2 * k + 2, 2 * k + 3, 2 * k + 1) for k in range(n - 1)]
    mb.add(V, F, "razor")


def barbed_cards(mb: C.MB, a, b, sag: float = 0.012, seg: int = 4) -> list:
    """Нить колючки для игры: две крестом поставленные полосы с провисом; возвращает число пар вершин полос."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    t = np.linspace(0, 1, seg + 1)
    P = a + np.outer(t, b - a)
    P[:, 2] -= sag * 4 * t * (1 - t)
    for d in (np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0])):
        V = np.empty((2 * len(P), 3))
        V[0::2] = P - d * BARB_W / 2
        V[1::2] = P + d * BARB_W / 2
        F = [(2 * k, 2 * k + 2, 2 * k + 3, 2 * k + 1) for k in range(len(P) - 1)]
        mb.add(V, F, "wire")
    return [len(P), len(P)]


def _fallen_matrix() -> np.ndarray:
    R = C.rot("y", -91.5)
    piv = np.array([XB, 0.0, ZB - 0.47])
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = np.array([0.22, 0.0, 0.085]) - R @ piv
    return M


def _tilt_matrix(R, t, dy: float = 0.0) -> np.ndarray:
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = np.asarray(t) + R @ np.array([0.0, dy, 0.0])
    return M


def game(col, parent, key: str, ctx: dict) -> None:
    """Игровые детали варианта key (game.py): первая — «Секция», остальные берут её сетки (общая развёртка)."""
    import bpy

    import game_lib as G
    if "plate" not in ctx:
        mb = C.MB()
        plate_mesh(mb, back_ngon=True, apex=True)
        ctx["plate"] = G.part(mb, "plate", "PO2", "concrete", col, parent, weld=1e-5, sharp=8)   # грани пирамид — резко
        # лицо целиком (рамка, откосы, поле пирамид, полоса) — один остров, тыл — второй, торцы — полосы; крутые
        # внутренние откосы рамки (100 мм вглубь на 30 мм) в проекции лица сжаты по уклону — узкие стенки,
        # видны только вскользь; иначе поле отрывается от рамки и атлас пустеет (заполнение 57 % вместо 80+)
        G.box_unwrap(ctx["plate"], (4.0, 1.0, 1.0))
        ctx["plate"]["uv_rules"] = PLATE_UV_RULES
        mb = C.MB()
        legs(mb)
        ctx["legs"] = G.part(mb, "legs", "PO2", "concrete", col, parent)
        mb = C.MB()
        foundation(mb, -L / 2, depth=0.15)
        ctx["fnd"] = G.part(mb, "foundation", "PO2", "concrete", col, parent, sharp=30)
        mb = C.MB()
        grout(mb, -L / 2)
        ctx["grout"] = G.part(mb, "grout", "PO2", "mortar", col, parent, sharp=30)
        mb = C.MB()
        lifting_loops(mb, n=4, sides=3)
        ctx["loops"] = ob = G.part(mb, "loops", "Rebar", "rebar", col, parent, sharp=70)
        G.tubes_uv(ob, [len(v) for v in mb.V], 3, REBAR_PERIOD)              # плиточный пруток, не атлас
        mb = C.MB()
        bracket(mb, anchors=False, clamps=False)
        ctx["bracket"] = G.part(mb, "bracket", "PO2", "steel", col, parent, sharp=30)
        mb = C.MB()
        lens = []
        for e in arm_ends():
            lens += barbed_cards(mb, (e[0], -L / 2, e[2]), (e[0], L / 2, e[2]))
        ctx["barbed"] = ob = G.part(mb, "strands", "Barbed", "wire", col, parent, sharp=180)
        G.strip_uv(ob, BARB_PERIOD, strips=lens)
        mb = C.MB()
        coil_ribbon(mb, -L / 2, L / 2, 10)
        ctx["coil"] = ob = G.part(mb, "coil", "Razor", "razor", col, parent, sharp=180)
        G.strip_uv(ob, RAZOR_PERIOD)
    if key == "intact":
        return
    if key == "bare":
        for k in ("plate", "legs", "fnd", "grout", "loops"):
            G.instance(ctx[k], col, parent)
        return
    if key == "breach":
        rng = np.random.default_rng(7)               # тот же ряд, что у подробной формы: тот же пролом
        mb = C.MB()
        plate_mesh(mb, back_ngon=True, apex=True)
        ob = G.part(mb, "plate", "PO2Breach", "concrete", col, parent, weld=1e-5, sharp=8)
        cut = C.MB()
        cv, cf = breach_cutter(rng)
        cut.add(cv, cf, "concrete")
        cutter = cut.build("_cutter", col, parent)
        m = ob.modifiers.new("Пролом", "BOOLEAN")
        m.operation, m.solver, m.object = "DIFFERENCE", "EXACT", cutter
        with bpy.context.temp_override(object=ob):
            bpy.ops.object.modifier_apply(modifier="Пролом")
        bpy.data.objects.remove(cutter, do_unlink=True)
        # развёртка — после выреза (кромки скола — свои грани): лицо и тыл по острову, кромки — по осям; лицо и тыл
        # режутся на куски слева, справа и над проёмом — укладка по рамкам не теряет площадь дыры
        G.box_unwrap(ob, (4.0, 1.0, 1.0))
        ob["uv_rules"] = PLATE_UV_RULES
        ys_hole = np.array(cv[:66, 1])
        y_lo, y_hi = float(ys_hole.min()) - 0.02, float(ys_hole.max()) + 0.02
        G.split_islands(ob, lambda c: 0 if c[1] < y_lo else (1 if c[1] > y_hi else 2))
        poly = np.array(cv[:66, 1:])
        rb = C.MB()
        rebar_mesh(rb, rng, lambda y, z: C.inside_poly(poly, y, z), sides=3)
        G.tubes_uv(G.part(rb, "rebar", "Rebar", "rebar", col, parent, sharp=70), [len(v) for v in rb.V], 3, REBAR_PERIOD)
        db = C.MB()
        debris(db, rng, small=False)
        dob = G.part(db, "debris", "PO2Breach", "concrete", col, parent, sharp=25)
        dob["uv"], dob["uv_scale"] = 66.0, 0.5           # куски — крупными островами, на земле — вдвое реже
        for k in ("legs", "fnd", "grout", "loops", "bracket", "barbed"):
            G.instance(ctx[k], col, parent)

        def squash(t, ang):
            yy = -L / 2 + L * t
            w = np.exp(-((yy - 0.1) / 0.55) ** 2)
            return 1.0 - 0.28 * w * (0.5 + 0.5 * np.cos(ang * 0.5))
        mb = C.MB()
        coil_ribbon(mb, -L / 2, L / 2, 10, squash=squash)
        G.strip_uv(G.part(mb, "coil", "Razor", "razor", col, parent, sharp=180), RAZOR_PERIOD)
        return
    if key == "fallen":
        M = _fallen_matrix()
        for k in ("plate", "legs", "loops"):
            G.instance(ctx[k], col, parent, M)
        G.instance(ctx["fnd"], col, parent, _tilt_matrix(C.rot("y", -7.0), (0.0, 0.0, 0.02)))
        G.instance(ctx["fnd"], col, parent, _tilt_matrix(C.rot("y", -5.0) @ C.rot("x", -3.0), (0.0, 0.0, 0.015), L))

        def squash(t, ang):
            return 0.75 + 0.1 * np.sin(ang * 0.37)
        mb = C.MB()
        coil_ribbon(mb, -L / 2 + 0.2, L / 2 - 0.1, 9, z=0.22, x=-3.20, squash=squash)
        G.strip_uv(G.part(mb, "coil", "Razor", "razor", col, parent, sharp=180), RAZOR_PERIOD)
