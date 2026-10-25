"""Опоры «Проспекта»: ЛЭП 0,4 кВ на железобетонной стойке (набор pole_conc, 32 на карте; вариант с фонарём)
и опора контактной сети троллейбуса (набор pole_trolley, 28 на карте).

Опора 0,4 кВ — стойка вибрированная СВ-110 (11 м, прямоугольное сечение: ширина 165 мм постоянная, глубина
280 мм у комля → 150 мм у вершины, сквозные отверстия Ø 24 под болты и хомуты), заглублена на 1,5 м — над землёй
9,5 м. Траверса — уголок 75×6 на хомуте и двух подкосах, четыре штыревых изолятора типа ТФ-20 на штырях:
шейки изоляторов (где вяжут провод) на 9,15 м, провода поперёк опоры — Blender Y = ±0,25, ±0,7 (как на карте).
Заземляющий спуск по тылу (−X), табличка «Опасно для жизни» на бандаже с лица (+X) на 2,6 м.
С фонарём — консоль из трубы Ø 48 на двух бандажах и консольный светильник (вымышленный, как ЖКУ/РКУ) на ~8 м,
кабель от траверсы по стойке.

Опора троллейбуса — стальная ступенчатая труба 325 / 273 / 219 мм на фланце с косынками, анкерами и бетонным
фундаментом, над землёй 9,0 м, лючок у основания, колпак сверху. На 7,4 м — хомут с проушиной, стержневой
изолятор, талреп и начало поперечного троса к дороге (Blender −Y; сам трос и контактные провода рисует карта).
Сверху — консоль уличного светильника 1,8 м к дороге.

Оси: Blender X = игровой X, Z — вверх, −Y = игровое +Z (к дороге у троллейбусной). Начало — земля у оси опоры.
"""
from __future__ import annotations

import math

import bpy
import numpy as np

import clib as C

# ---------------------------------------------------------------- стойка СВ-110
SV_LEN = 11.0
SV_BURY = 1.5
SV_TOP = SV_LEN - SV_BURY            # 9,5 м над землёй
SV_W = 0.165                         # по X
SV_D0, SV_D1 = 0.280, 0.150          # по Y: комель → вершина
CROSS_Z = 9.0                        # верх полки траверсы
WIRE_Z = 9.15                        # шейки изоляторов
WIRE_Y = (-0.7, -0.25, 0.25, 0.7)


def sv_depth(z: float) -> float:
    return SV_D0 + (SV_D1 - SV_D0) * (z + SV_BURY) / SV_LEN


def stand(mb: C.MB, z0: float = -0.6) -> None:
    """Стойка — прямоугольник, сужающийся по Y; угловые фаски 15 мм (форма фаской модификатора)."""
    zs = [z0, 0.0, 2.0, 4.0, 6.0, 8.0, SV_TOP]
    rings = []
    for z in zs:
        d = sv_depth(z)
        rings.append(np.array([(-SV_W / 2, -d / 2, z), (SV_W / 2, -d / 2, z), (SV_W / 2, d / 2, z), (-SV_W / 2, d / 2, z)]))
    V, F = C.loft(rings, closed=True, cap0=True, cap1=True)
    mb.add(V, F, "concrete")


SV_HOLES = [SV_TOP - h for h in (0.12, 0.36, 0.54, 0.84, 1.08, 1.32, 1.62, 1.92, 2.30)] + [0.45, 0.95, 4.2, 6.4]


def hole_cutters(mb: C.MB) -> None:
    """Сквозные отверстия Ø 24 поперёк стойки (ось X): вверху под траверсу и хомуты, у земли — под ригель/заземление."""
    for z in SV_HOLES:
        mb.extend(C.cyl((0.0, 0.0, z), 0.012, 0.4, 12, "x"))


def boolean_cut(ob: bpy.types.Object, cutter_mb: C.MB, col, parent) -> None:
    """Вычесть резаки из объекта до фаски (модификатор наверх стека и применить)."""
    cutter = cutter_mb.build("_cutter", col, parent)
    m = ob.modifiers.new("Отверстия", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.solver = "EXACT"
    m.object = cutter
    bpy.context.view_layer.objects.active = ob
    with bpy.context.temp_override(object=ob):
        bpy.ops.object.modifier_move_to_index(modifier="Отверстия", index=0)
        bpy.ops.object.modifier_apply(modifier="Отверстия")
    bpy.data.objects.remove(cutter, do_unlink=True)


def nut_bolt(mb: C.MB, p, axis: str, length: float, r: float = 0.008) -> None:
    """Шпилька с шайбой и шестигранной гайкой на конце p; axis — направление наружу ('+x', '-x', '+y' …)."""
    s = 1.0 if axis[0] == "+" else -1.0
    ax = axis[1]
    d = np.array({"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}[ax], float) * s
    p = np.asarray(p, float)
    mb.extend(C.cyl_between(p - d * length, p + d * 0.022, r, 10), "galv")
    R = {"x": C.rot("y", 90), "y": C.rot("x", -90), "z": None}[ax]
    w, F = C.lathe([(r * 2.6, 0.0), (r * 2.6, 0.003)], 16)
    mb.add(C.xf(w, R, p + d * 0.0), F, "galv")
    n6, F6 = C.lathe([(r * 1.9, 0.003), (r * 1.9, 0.003 + r * 1.6)], 6)
    mb.add(C.xf(n6, R if s > 0 else (R @ C.rot("x", 180) if R is not None else C.rot("x", 180)), p), F6, "galv")


def angle_beam(mb: C.MB, p0, p1, w: float, t: float, up=(0, 0, 1), flip: tuple = (1, 1), m: str = "galv") -> None:
    """Уголок w×w×t от p0 до p1: полки вдоль 'вверх' и 'вбок' (flip — знаки полок)."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    ln = float(np.linalg.norm(d))
    Fr = C.frame_from(d, up)
    prof = C.angle_profile(w, t) * np.array(flip, float)
    if flip[0] * flip[1] < 0:
        prof = prof[::-1]
    V, F = C.prism(prof, 0.0, ln, origin=p0, ex=Fr[0], ey=Fr[1], ez=Fr[2])
    mb.add(V, F, m)


def strap(mb: C.MB, z: float, h: float = 0.04, t: float = 0.004, ears: str = "+x", m: str = "galv") -> None:
    """Бандаж-хомут из полосы вокруг стойки СВ (по контуру сечения) с ушками и болтом с указанной стороны."""
    d = sv_depth(z)
    hw, hd = SV_W / 2 + t, d / 2 + t
    ring = C.rect_profile(2 * hw, 2 * hd, 0.012, 3)
    inner = C.rect_profile(2 * (hw - t), 2 * (hd - t), 0.008, 3)
    Vo = [(x, y, z - h / 2) for x, y in ring] + [(x, y, z + h / 2) for x, y in ring]
    Vi = [(x, y, z - h / 2) for x, y in inner] + [(x, y, z + h / 2) for x, y in inner]
    n = len(ring)
    V = Vo + Vi
    F = []
    for i in range(n):
        j = (i + 1) % n
        F.append((i, j, n + j, n + i))                                     # наружная
        F.append((2 * n + i, 3 * n + i, 3 * n + j, 2 * n + j))             # внутренняя
        F.append((i, 2 * n + i, 2 * n + j, j))                             # низ
        F.append((n + i, n + j, 3 * n + j, 3 * n + i))                     # верх
    mb.add(np.array(V), F, m)
    s = 1.0 if ears[0] == "+" else -1.0
    if ears[1] == "x":
        x = s * (hw + 0.018)
        for dy in (-0.022, 0.022):
            mb.extend(C.box((x, dy, z), (0.036, 0.005, h)), m)
        mb.extend(C.cyl_between((x, -0.045, z), (x, 0.045, z), 0.006, 8), "galv")
    else:
        y = s * (hd + 0.018)
        for dx in (-0.022, 0.022):
            mb.extend(C.box((dx, y, z), (0.005, 0.036, h)), m)
        mb.extend(C.cyl_between((-0.045, y, z), (0.045, y, z), 0.006, 8), "galv")


def insulator_tf(mb: C.MB, base) -> None:
    """Штыревой фарфоровый изолятор типа ТФ-20: юбка, талия, шейка под вязку провода, головка с желобом сверху."""
    prof = [(0.010, 0.000), (0.033, 0.000), (0.035, 0.004), (0.034, 0.012), (0.029, 0.018), (0.024, 0.028),
            (0.023, 0.040), (0.026, 0.046), (0.026, 0.050), (0.020, 0.054), (0.019, 0.060), (0.025, 0.064),
            (0.027, 0.070), (0.024, 0.078), (0.016, 0.083), (0.008, 0.083)]
    V, F = C.lathe(prof, 24, center=base)
    mb.add(V, F, "porcelain", smooth=True)


def pin(mb: C.MB, p, h: float = 0.095) -> None:
    """Штырь: шпилька Ø 18 с гайкой под полкой, колпачок-втулка изолятора."""
    p = np.asarray(p, float)
    mb.extend(C.cyl_between(p + (0, 0, -0.03), p + (0, 0, h - 0.01), 0.009, 10), "galv")
    w, F = C.lathe([(0.020, 0.0), (0.020, 0.006)], 12)
    mb.add(C.xf(w, None, p), F, "galv")
    n6, F6 = C.lathe([(0.016, -0.018), (0.016, -0.006)], 6)
    mb.add(C.xf(n6, None, p), F6, "galv")
    cap, Fc = C.lathe([(0.013, h - 0.04), (0.015, h - 0.004), (0.012, h)], 10)
    mb.add(C.xf(cap, None, p), Fc, "plastic_dark")


def crossarm(mb: C.MB, steel: C.MB) -> None:
    """Траверса на лицевой (+X) грани: уголок 75×6 (горизонтальная полка сверху), хомут, подкосы 50×5, штыри."""
    x_face = SV_W / 2
    L2 = 0.88
    # уголок: вертикальная полка прижата к стойке (x от грани), горизонтальная — наружу, верх на CROSS_Z
    prof = np.array([(0, 0), (0.006, 0), (0.006, 0.069), (0.075, 0.069), (0.075, 0.075), (0, 0.075)], float)
    V, F = C.prism(prof, -L2, L2, origin=(x_face, 0, CROSS_Z - 0.075), ex=(1, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0))
    steel.add(V, F, "galv")
    # хомут: шпильки сквозь стойку (отверстия на 8,95 и 8,7 ниже) — U-болт поперёк траверсы
    for z in (CROSS_Z - 0.04,):
        steel.extend(C.cyl_between((x_face + 0.006, -0.0, z), (-x_face - 0.03, 0.0, z), 0.008, 10), "galv")
    # прижимная планка с тыла и гайки
    steel.extend(C.box((-x_face - 0.004, 0.0, CROSS_Z - 0.04), (0.008, 0.12, 0.05)), "galv")
    for z in (CROSS_Z - 0.04,):
        nut_bolt(steel, (-x_face - 0.008, 0.0, z), "-x", 0.0)
        nut_bolt(steel, (x_face + 0.006, 0.0, z), "+x", 0.0)
    # подкосы: от концов траверсы вниз к стойке, уголок 50×5
    for s in (-1, 1):
        a = np.array([x_face + 0.03, s * 0.72, CROSS_Z - 0.075])
        b = np.array([x_face + 0.005, s * 0.06, CROSS_Z - 0.62])
        angle_beam(steel, b, a, 0.05, 0.005, up=(1, 0, 0), flip=(1, -s))
        nut_bolt(steel, a + (0.0, 0.0, 0.0), "+x", 0.02, 0.007)
    # нижний хомут подкосов вокруг стойки
    strap(steel, CROSS_Z - 0.62, ears="+x")
    # штыри и изоляторы
    for y in WIRE_Y:
        p = np.array([x_face + 0.045, y, CROSS_Z])
        pin(steel, p)
        insulator_tf(mb, p + (0, 0, 0.095))


def ground_lead(mb: C.MB, top_z: float = CROSS_Z - 0.05) -> None:
    """Заземляющий спуск: круг Ø 8 по тыльной грани (−X) от траверсы в землю, скобы через 1,5 м."""
    xs = -SV_W / 2 - 0.012
    P = [(SV_W / 2 + 0.03, 0.05, top_z), (SV_W / 2 + 0.01, sv_depth(top_z) / 2 + 0.012, top_z - 0.08),
         (xs, sv_depth(top_z - 0.3) / 2 * 0.3, top_z - 0.35)]
    z = top_z - 1.0
    while z > 0.2:
        P.append((xs, 0.0, z))
        z -= 1.5
    P += [(xs, 0.0, 0.25), (xs - 0.02, 0.0, 0.05), (xs - 0.05, 0.0, -0.25)]
    mb.extend(C.tube(np.array(P), 0.004, 6), "steel")
    z = top_z - 1.2
    while z > 0.4:
        mb.extend(C.box((xs, 0.0, z), (0.02, 0.05, 0.03)), "galv")
        z -= 1.5


def danger_plate(mb: C.MB, z: float = 2.6) -> None:
    """Табличка «Опасно для жизни» 280 × 210 на бандаже с лица (+X); номер опоры — трафаретом выше (отделка)."""
    strap(mb, z, h=0.025, t=0.002, ears="-x", m="galv")
    x = SV_W / 2 + 0.004
    pl = C.rect_profile(0.28, 0.21, 0.012, 3)
    V, F = C.prism(pl, 0.0, 0.0025, origin=(x, 0.0, z), ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0))
    mb.add(V, F, "paint_white")
    # молния — рельефной накладкой (цвет — отделкой)
    bolt = np.array([(0.012, 0.075), (-0.028, -0.004), (-0.002, -0.004), (-0.016, -0.075), (0.030, 0.012), (0.004, 0.012)])
    V, F = C.prism(bolt, 0.0025, 0.0035, origin=(x, 0.0, z), ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0))
    mb.add(V, F, "paint_red")


# ---------------------------------------------------------------- светильник
def luminaire(mb: C.MB, glass: C.MB, p, d, length: float = 0.68, width: float = 0.30, height: float = 0.17,
              tilt: float = 8.0) -> None:
    """Консольный светильник (свой, без марки): литой корпус «капля», крышка-навес, рассеиватель снизу,
    патрубок под трубу консоли сзади. p — точка крепления (конец трубы), d — направление вылета (в плане)."""
    d = np.asarray(d, float)
    d = d / np.linalg.norm(d)
    n = 28
    t = np.linspace(0, 1, n)
    # продольный профиль: ширина, высота крышки, глубина низа (м) по длине
    wid = width * (0.42 + 0.58 * np.sin(np.clip(t * 1.08, 0, 1) * math.pi * 0.62) ** 0.7)
    wid[-1] = wid[-2] * 0.6
    top = height * (0.55 + 0.45 * np.sin(np.clip(t, 0, 1) * math.pi * 0.75) ** 0.8) * (1 - 0.5 * t ** 6)
    bot = height * 0.35 * np.sin(np.clip(t, 0.02, 0.98) * math.pi) ** 0.5
    rings = []
    k = 12
    for i in range(n):
        ring = []
        for j in range(k):
            a = math.pi * j / (k - 1)                                       # верхняя полуарка
            ring.append((math.cos(a) * wid[i] / 2, math.sin(a) ** 0.6 * top[i]))
        for j in range(1, k - 1):
            a = math.pi * j / (k - 1)
            ring.append((-math.cos(a) * wid[i] / 2 * 0.96, -math.sin(a) ** 1.2 * bot[i]))
        rings.append(ring)
    m = len(rings[0])
    side = np.cross(d, (0, 0, 1))
    side /= np.linalg.norm(side)
    up = np.cross(side, d)
    R = C.rot("y", 0)
    # наклон корпуса вверх по вылету
    ta = math.radians(tilt)
    fwd = d * math.cos(ta) + np.array([0, 0, 1.0]) * math.sin(ta)
    upv = np.cross(side, fwd)
    _ = R, up
    V = []
    for i in range(n):
        c = np.asarray(p, float) + fwd * (length * t[i])
        for a_, b_ in rings[i]:
            V.append(c + side * a_ + upv * b_)
    F = []
    for i in range(n - 1):
        for j in range(m):
            jj = (j + 1) % m
            F.append((i * m + j, i * m + jj, (i + 1) * m + jj, (i + 1) * m + j))
    F.append(tuple(range(m - 1, -1, -1)))
    F.append(tuple(range((n - 1) * m, n * m)))
    mb.add(np.array(V), F, "paint_grey", smooth=True)
    # рассеиватель: вдавленная чаша по низу средней части
    gs = []
    for i in range(6, n - 5):
        c = np.asarray(p, float) + fwd * (length * t[i])
        ring = []
        for j in range(k):
            a = math.pi * j / (k - 1)
            ring.append(c + side * (-math.cos(a) * wid[i] / 2 * 0.8) - upv * (math.sin(a) ** 1.2 * bot[i] * 1.12 + 0.003))
        gs.append(ring)
    Vg, Fg = C.loft([np.array(r) for r in gs], closed=False)
    glass.add(Vg, Fg, "lamp", smooth=True)
    # патрубок
    mb.extend(C.cyl_between(np.asarray(p) - fwd * 0.10, np.asarray(p) + fwd * 0.06, 0.032, 16), "paint_grey")


def lamp_bracket_sv(mb: C.MB, glass: C.MB) -> None:
    """Консоль Ø 48 на двух бандажах с лица (+X): трубный изгиб вверх, вылет 1,4 м, светильник на ~8 м."""
    z_low, z_up = 7.45, 7.95
    strap(mb, z_low, ears="-x")
    strap(mb, z_up, ears="-x")
    x0 = SV_W / 2 + 0.03
    # стойка консоли по грани — между бандажами, затем изгиб наружу и вверх
    P = [(x0, 0.0, z_low - 0.1), (x0, 0.0, z_up), (x0 + 0.05, 0.0, z_up + 0.12), (x0 + 0.25, 0.0, z_up + 0.24),
         (x0 + 0.7, 0.0, z_up + 0.30), (x0 + 1.25, 0.0, z_up + 0.30)]
    Pd = []
    for k in range(len(P) - 1):                                         # сгладить ломаную
        a, b = np.array(P[k]), np.array(P[k + 1])
        for u in np.linspace(0, 1, 6, endpoint=False):
            Pd.append(a + (b - a) * u)
    Pd.append(np.array(P[-1]))
    mb.extend(C.tube(np.array(Pd), 0.024, 14), "galv")
    # подкос консоли
    mb.extend(C.cyl_between((x0, 0.0, z_low + 0.05), (x0 + 0.55, 0.0, z_up + 0.27), 0.012, 10), "galv")
    luminaire(mb, glass, (x0 + 1.22, 0.0, z_up + 0.30), (1, 0, 0))


def cable_sv(mb: C.MB) -> None:
    """Кабель питания светильника: от траверсы вниз по грани +Y, вдоль консоли (СИП-2, Ø 14) на скобах."""
    y = sv_depth(8.5) / 2 + 0.012
    P = [(SV_W / 2 + 0.07, 0.25, CROSS_Z + 0.02), (SV_W / 2 + 0.02, y + 0.02, CROSS_Z - 0.1), (0.03, y, CROSS_Z - 0.35),
         (0.03, sv_depth(8.2) / 2 + 0.012, 8.2), (0.04, sv_depth(8.0) / 2 + 0.014, 8.0),
         (SV_W / 2 + 0.03, 0.05, 7.98)]
    mb.extend(C.tube(np.array(P), 0.007, 8), "plastic_dark")
    for z in (8.75, 8.35):
        mb.extend(C.box((0.03, sv_depth(z) / 2 + 0.012, z), (0.03, 0.02, 0.02)), "plastic_dark")


def pole04(col, parent, lamp: bool = False) -> None:
    body = C.MB()
    stand(body)
    ob = body.build("SV110_Stand", col, parent, bevel=0.012, seg=2, weld=1e-6)
    holes = C.MB()
    hole_cutters(holes)
    boolean_cut(ob, holes, col, parent)
    ins = C.MB()
    steel = C.MB()
    crossarm(ins, steel)
    ins.build("Insulators_TF20", col, parent, sharp=60, weld=1e-6)
    ground_lead(steel)
    steel.build("Crossarm_Hardware", col, parent, bevel=0.0008, seg=1)
    sign = C.MB()
    danger_plate(sign)
    sign.build("Danger_Plate", col, parent, weld=1e-6)
    if lamp:
        lm = C.MB()
        gl = C.MB()
        lamp_bracket_sv(lm, gl)
        cable_sv(lm)
        lm.build("Lamp_Bracket", col, parent, bevel=0.0008, seg=1, sharp=50, weld=1e-6)
        gl.build("Lamp_Diffuser", col, parent, sharp=70, weld=1e-6)


# ---------------------------------------------------------------- троллейбусная опора
TR_TOP = 9.0
TR_SEC = [(0.0, 3.0, 0.1625), (3.0, 6.0, 0.1365), (6.0, TR_TOP, 0.1095)]   # (от, до, радиус)
SPAN_Z = 7.4


def trolley_tube(mb: C.MB) -> None:
    """Ступенчатая труба 325 / 273 / 219 с коническими переходами 150 мм и колпаком."""
    prof = [(TR_SEC[0][2], 0.025)]
    for k, (z0, z1, r) in enumerate(TR_SEC):
        prof.append((r, z0 + (0.08 if k else 0.025)))
        prof.append((r, z1 - 0.08 if k < len(TR_SEC) - 1 else z1))
        if k < len(TR_SEC) - 1:
            r2 = TR_SEC[k + 1][2]
            prof.append(((r + r2) / 2 + 0.004, z1))                     # сварной шов перехода
    # колпак
    r_top = TR_SEC[-1][2]
    prof += [(r_top + 0.006, TR_TOP), (r_top + 0.006, TR_TOP + 0.02), (r_top * 0.75, TR_TOP + 0.06),
             (r_top * 0.35, TR_TOP + 0.085), (0.0, TR_TOP + 0.09)]
    V, F = C.lathe(prof, 32)
    mb.add(V, F, "paint_grey", smooth=True)


def trolley_base(conc: C.MB, steel: C.MB) -> None:
    """Фундамент Ø 650 (+0,1 над землёй), фланец 450 × 450 × 25, четыре анкера с двумя гайками, косынки, лючок."""
    V, F = C.lathe([(0.30, -0.40), (0.325, -0.05), (0.325, 0.07), (0.31, 0.10), (0.0, 0.10)], 32)
    conc.add(V, F, "concrete_old")
    pl = C.rect_profile(0.45, 0.45, 0.03, 3)
    V, F = C.prism(pl, 0.10, 0.125)
    steel.add(V, F, "paint_grey")
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = np.array([sx * 0.17, sy * 0.17, 0.125])
            steel.extend(C.cyl_between(p - (0, 0, 0.06), p + (0, 0, 0.075), 0.012, 10), "galv")
            n6, F6 = C.lathe([(0.021, 0.0), (0.021, 0.022)], 6)
            steel.add(C.xf(n6, None, p), F6, "galv")
            steel.add(C.xf(n6, None, p + (0, 0, 0.026)), F6, "galv")
            w, Fw = C.lathe([(0.028, 0.0), (0.028, 0.004)], 14)
            steel.add(C.xf(w, None, p - (0, 0, 0.0)), Fw, "galv")
    r0 = TR_SEC[0][2]
    for k in range(4):
        a = math.radians(45 + 90 * k)
        d = np.array([math.cos(a), math.sin(a), 0.0])
        n = np.array([-d[1], d[0], 0.0])
        tri = [(0.0, 0.0), (0.12, 0.0), (0.0, 0.26)]
        V, F = C.prism(tri, -0.006, 0.006, origin=d * r0 + (0, 0, 0.125), ex=d, ey=(0, 0, 1), ez=n)
        steel.add(V, F, "paint_grey")
    # лючок на +X: рамка и крышка с замком
    hx = r0 + 0.003
    hatch = C.rect_profile(0.12, 0.30, 0.02, 3)
    V, F = C.prism(hatch, 0.0, 0.006, origin=(hx - 0.004, 0.0, 0.75), ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0))
    steel.add(V, F, "paint_grey")
    steel.extend(C.cyl((hx + 0.005, 0.0, 0.65), 0.008, 0.008, 10, "x"), "steel_dark")


def collar_clamp(mb: C.MB, z: float, r: float, ear_dir, h: float = 0.06) -> np.ndarray:
    """Хомут из двух полуколец с ушками на болтах и проушиной в сторону ear_dir; возвращает центр отверстия проушины."""
    ear = np.asarray(ear_dir, float)
    ear /= np.linalg.norm(ear)
    side = np.array([-ear[1], ear[0], 0.0])
    rr = r + 0.008
    V, F = C.lathe([(rr, z - h / 2), (rr, z + h / 2)], 32)
    mb.add(V, F, "galv")
    V, F = C.lathe([(r + 0.001, z - h / 2), (r + 0.001, z + h / 2)], 32)
    # ушки стяжки по бокам
    for s in (-1, 1):
        c = side * s * (rr + 0.025)
        mb.extend(C.box(c + (0, 0, z), (0.05 if abs(side[0]) > 0.5 else 0.012, 0.05 if abs(side[1]) > 0.5 else 0.012, h)),
                  "galv")
        a = c + ear * 0.03 + (0, 0, z)
        b = c - ear * 0.03 + (0, 0, z)
        mb.extend(C.cyl_between(a, b, 0.007, 8), "galv")
    # проушина — две щеки, палец
    for s in (-1, 1):
        c = ear * (rr + 0.05) + side * s * 0.014 + (0, 0, z)
        V, F = C.prism(C.rect_profile(0.10, 0.07, 0.03, 3), -0.004, 0.004, origin=c, ex=ear, ey=(0, 0, 1), ez=side)
        mb.add(V, F, "galv")
    hole = ear * (rr + 0.075) + (0, 0, z)
    mb.extend(C.cyl_between(hole - side * 0.024, hole + side * 0.024, 0.008, 10), "galv")
    return hole


def rod_insulator(mb: C.MB, a, b, sheds: int = 7) -> None:
    """Полимерный стержневой изолятор: стержень Ø 24 в оболочке, тарелки-рёбра, оконцеватели с проушинами."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    ln = float(np.linalg.norm(d))
    u = d / ln
    R = C.frame_from(u).T                                               # z модели → u
    prof = [(0.017, 0.0), (0.017, 0.06), (0.014, 0.065)]                       # торцы — крышками
    z = 0.075
    span = ln - 0.15
    pitch = span / sheds
    for k in range(sheds):
        z0 = 0.075 + k * pitch
        prof += [(0.014, z0), (0.045, z0 + pitch * 0.25), (0.046, z0 + pitch * 0.32), (0.014, z0 + pitch * 0.42)]
    prof += [(0.014, ln - 0.075), (0.017, ln - 0.065), (0.017, ln)]
    _ = z
    V, F = C.lathe(prof, 18)
    mb.add(C.xf(V, R, a), F, "plastic_dark", smooth=True)


def turnbuckle(mb: C.MB, a, b) -> None:
    """Талреп: два винта с проушинами и корпус-рамка посередине."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    ln = float(np.linalg.norm(d))
    u = d / ln
    mb.extend(C.cyl_between(a, b, 0.008, 10), "galv")
    c0, c1 = a + u * ln * 0.3, a + u * ln * 0.7
    Fr = C.frame_from(u)
    for s in (-1, 1):
        V, F = C.prism(C.rect_profile(0.008, 0.006), 0.0, float(np.linalg.norm(c1 - c0)),
                       origin=c0 + Fr[0] * s * 0.016, ex=Fr[0], ey=Fr[1], ez=Fr[2])
        mb.add(V, F, "galv")
    for c in (c0, c1):
        mb.extend(C.cyl_between(c - u * 0.006, c + u * 0.006, 0.02, 12), "galv")


def span_fitting(mb: C.MB, dark: C.MB) -> None:
    """Узел поперечины на 7,4 м: хомут с проушиной к дороге (−Y), серьга, изолятор, талреп, конец троса с зажимом."""
    r = TR_SEC[1][2] if SPAN_Z < TR_SEC[1][1] else TR_SEC[2][2]
    hole = collar_clamp(mb, SPAN_Z, r, (0, -1, 0))
    # серьга
    s0 = hole + (0, -0.06, 0)
    mb.extend(C.tube(np.array([hole + (0, 0.0, 0.012), s0 + (0, 0, 0.012), s0 + (0, -0.01, 0), s0 + (0, 0, -0.012),
                               hole + (0, 0, -0.012)]), 0.006, 8), "galv")
    i0 = s0 + (0, -0.01, 0)
    i1 = i0 + (0, -0.42, 0)
    rod_insulator(dark, i0, i1)
    t1 = i1 + (0, -0.30, 0)
    turnbuckle(mb, i1, t1)
    # коуш и трос Ø 10 к дороге (дальше — провод карты), зажим с тремя болтами
    th = [t1, t1 + (0, -0.04, 0.015), t1 + (0, -0.09, 0.0), t1 + (0, -0.04, -0.015), t1]
    mb.extend(C.tube(np.array(th), 0.006, 8), "galv")
    rope = np.array([t1 + (0, -0.09, 0.0), t1 + (0, -0.6, -0.01)])
    dark.extend(C.tube(rope, 0.005, 8), "steel")
    dark.extend(C.tube(rope + (0, 0, 0.012), 0.005, 8), "steel")
    for k in range(2):
        c = t1 + (0, -0.16 - 0.1 * k, 0.006)
        mb.extend(C.box(c, (0.03, 0.04, 0.035)), "galv")


def lamp_console_trolley(mb: C.MB, glass: C.MB) -> None:
    """Консоль светильника сверху: труба Ø 60 из колпака-переходника, изгиб к дороге, вылет 1,8 м."""
    zc = TR_TOP + 0.02
    P = [(0, 0, zc - 0.25), (0, 0, zc + 0.15), (0, -0.06, zc + 0.32), (0, -0.25, zc + 0.48), (0, -0.7, zc + 0.6),
         (0, -1.3, zc + 0.64), (0, -1.75, zc + 0.64)]
    Pd = []
    for k in range(len(P) - 1):
        a, b = np.array(P[k], float), np.array(P[k + 1], float)
        for u in np.linspace(0, 1, 6, endpoint=False):
            Pd.append(a + (b - a) * u)
    Pd.append(np.array(P[-1], float))
    # сгладить скользящим средним
    Pd = np.array(Pd)
    for _ in range(3):
        Pd[1:-1] = (Pd[:-2] + 2 * Pd[1:-1] + Pd[2:]) / 4
    mb.extend(C.tube(Pd, 0.030, 16), "paint_grey")
    # переходник-стакан на оголовке
    V, F = C.lathe([(TR_SEC[-1][2] + 0.012, TR_TOP - 0.18), (TR_SEC[-1][2] + 0.012, TR_TOP + 0.05),
                    (0.045, TR_TOP + 0.09), (0.034, TR_TOP + 0.12)], 24)
    mb.add(V, F, "paint_grey", smooth=True)
    for k in range(3):
        a = math.radians(30 + 120 * k)
        mb.extend(C.cyl_between((math.cos(a) * 0.11, math.sin(a) * 0.11, TR_TOP - 0.1),
                                (math.cos(a) * 0.145, math.sin(a) * 0.145, TR_TOP - 0.1), 0.007, 8), "galv")
    luminaire(mb, glass, (0, -1.72, zc + 0.64), (0, -1, 0), tilt=5.0)


def trolley(col, parent) -> None:
    tb = C.MB()
    trolley_tube(tb)
    tb.build("Trolley_Pole", col, parent, sharp=40, weld=1e-6)
    conc = C.MB()
    steel = C.MB()
    trolley_base(conc, steel)
    conc.build("Trolley_Foundation", col, parent, bevel=0.015, seg=2, weld=1e-6)
    steel.build("Trolley_Base", col, parent, bevel=0.0008, seg=1, weld=1e-6)
    hw = C.MB()
    dk = C.MB()
    span_fitting(hw, dk)
    hw.build("Span_Fitting", col, parent, bevel=0.0008, seg=1)
    dk.build("Span_Insulator", col, parent, sharp=50, weld=1e-6)
    lc = C.MB()
    gl = C.MB()
    lamp_console_trolley(lc, gl)
    lc.build("Lamp_Console", col, parent, sharp=45, bevel=0.0008, seg=1, weld=1e-6)
    gl.build("Lamp_Diffuser", col, parent, sharp=70, weld=1e-6)
    # номерная табличка опоры на хомуте
    pl = C.MB()
    r = TR_SEC[0][2]
    V, F = C.lathe([(r + 0.003, 2.45), (r + 0.003, 2.47)], 32)
    pl.add(V, F, "galv")
    V, F = C.prism(C.rect_profile(0.16, 0.10, 0.01, 2), 0.0, 0.002, origin=(r + 0.004, 0.0, 2.40), ex=(0, 1, 0),
                   ey=(0, 0, 1), ez=(1, 0, 0))
    pl.add(V, F, "paint_white")
    pl.build("Number_Plate", col, parent, weld=1e-6)


VARIANTS = {"pole04": "Опора 0,4 кВ", "pole04_lamp": "Опора 0,4 кВ с фонарём", "trolley": "Опора троллейбусной сети"}
STEP = 3.0
META = {
    "folder": "Опоры", "name": "Poles_City", "title": "Опоры: ЛЭП 0,4 кВ (СВ-110) и контактной сети троллейбуса",
    "step": 3.0,
    "shots": [["во весь рост", [10.0, -12.0, 5.0], [0.0, 0.0, 4.9], 30], ["верх крупно", [1.6, -2.2, 9.6], [0.0, 0.0, 9.0], 32],
              ["низ и табличка", [2.4, -1.7, 2.3], [0.1, 0.0, 1.9], 28]],
    "shots_by": {
        "pole04_lamp": [["во весь рост", [10.0, -12.0, 5.0], [0.6, 0.0, 4.9], 30],
                        ["верх и светильник", [3.2, -3.0, 9.6], [0.7, 0.0, 8.5], 32],
                        ["низ и табличка", [2.4, -1.7, 2.3], [0.1, 0.0, 1.9], 28]],
        "trolley": [["во весь рост", [10.0, -11.0, 5.2], [0.0, -0.8, 5.0], 30],
                    ["поперечина и светильник", [3.6, -4.0, 9.2], [0.0, -1.0, 8.4], 30],
                    ["основание крупно", [1.3, -1.5, 1.1], [0.0, 0.0, 0.4], 30]],
    },
}


def build(keys: list[str]) -> dict:
    out = {}
    for i, k in enumerate(keys):
        name = VARIANTS[k]
        col = C.collection(name)
        r = C.root(f"Pole | {name}", col, (i * STEP, 0.0, 0.0))
        if k == "trolley":
            trolley(col, r)
        else:
            pole04(col, r, lamp=(k == "pole04_lamp"))
        out[k] = name
    return out
