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
              tilt: float = 8.0, n: int = 28, k: int = 12, neck: int = 16) -> None:
    """Консольный светильник (свой, без марки): литой корпус «капля», крышка-навес, рассеиватель снизу,
    патрубок под трубу консоли сзади. p — точка крепления (конец трубы), d — направление вылета (в плане)."""
    d = np.asarray(d, float)
    d = d / np.linalg.norm(d)
    t = np.linspace(0, 1, n)
    # продольный профиль: ширина, высота крышки, глубина низа (м) по длине
    wid = width * (0.42 + 0.58 * np.sin(np.clip(t * 1.08, 0, 1) * math.pi * 0.62) ** 0.7)
    wid[-1] = wid[-2] * 0.6
    top = height * (0.55 + 0.45 * np.sin(np.clip(t, 0, 1) * math.pi * 0.75) ** 0.8) * (1 - 0.5 * t ** 6)
    bot = height * 0.35 * np.sin(np.clip(t, 0.02, 0.98) * math.pi) ** 0.5
    rings = []
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
    for i in range(max(1, n * 6 // 28), n - max(1, n * 5 // 28)):
        c = np.asarray(p, float) + fwd * (length * t[i])
        ring = []
        for j in range(k):
            a = math.pi * j / (k - 1)
            ring.append(c + side * (-math.cos(a) * wid[i] / 2 * 0.8) - upv * (math.sin(a) ** 1.2 * bot[i] * 1.12 + 0.003))
        gs.append(ring)
    Vg, Fg = C.loft([np.array(r) for r in gs], closed=False)
    glass.add(Vg, Fg, "lamp", smooth=True)
    # патрубок
    mb.extend(C.cyl_between(np.asarray(p) - fwd * 0.10, np.asarray(p) + fwd * 0.06, 0.032, neck), "paint_grey")


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
    "game_shots_by": {
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


# ================================================================ игровая версия (LOD0)
# Опор на карте сотни — LOD0 ≤ 1–1,5 тыс. треугольников. Наборы Painter: Pole04 — стойка СВ, траверса, изоляторы,
# спуск, табличка, консоль, кабель и корпус светильника (2K); Trolley — труба, фундамент, фланец, узел поперечины,
# консоль (2K). Рассеиватель — Lamp (простой полупрозрачный материал без Painter). Отверстия стойки, бандажи, гайки, хомуты, лючок — запеканием.
# Коллизия — тонкая стойка (MODELS_POLES в tools/build_prospekt.py), своих ящиков нет.
GAME = {
    "ids": {"pole04": "PC04_POLE04", "pole04_lamp": "PC04_POLE04_LAMP", "trolley": "PC04_TROLLEY"},
    "bake": ["pole04", "pole04_lamp", "trolley"],
    "skip_high": [],
    "res": {"Pole04": 11, "Trolley": 11},        # светильник — в наборе Pole04 (отдельный 512 заполнялся на 53 %)
}
SV_CH = 0.015                     # фаска углов стойки


def stand_low(mb: C.MB, pieces: int = 7) -> None:
    """Стойка СВ для игры: восьмигранник (прямоугольник с фасками), конусность по Y, от −0,08 до верха — отдельные
    куски по ~1,4 м: каждый — свой остров развёртки (10-метровая полоса легла бы по диагонали атласа, а куски по 2,5 м
    не давали уложить атлас плотнее 74 %)."""
    zs = np.linspace(-0.08, SV_TOP, pieces + 1)            # под землёй — только 8 см (неровный грунт), не 0,3 м
    for z0, z1 in zip(zs[:-1], zs[1:]):
        rings = []
        for z in (z0, z1):
            w, d, c = SV_W / 2, sv_depth(z) / 2, SV_CH
            pts = [(-w + c, -d), (w - c, -d), (w, -d + c), (w, d - c), (w - c, d), (-w + c, d), (-w, d - c), (-w, -d + c)]
            rings.append(np.array([(x, y, z) for x, y in pts]))
        V, F = C.loft(rings, closed=True, cap0=True, cap1=True)
        mb.add(V, F, "concrete")


def split_tubes(mb: C.MB, P_, r: float, n: int, max_len: float, m: str) -> None:
    """Трубка по ломаной кусками не длиннее max_len (свои острова развёртки), без торцов."""
    P_ = np.asarray(P_, float)
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P_, axis=0), axis=1))]
    cuts = np.linspace(0, seg[-1], max(1, int(np.ceil(seg[-1] / max_len))) + 1)
    for a, b in zip(cuts[:-1], cuts[1:]):
        inner = [P_[i] for i in range(len(P_)) if a < seg[i] < b]
        pa = np.array([np.interp(a, seg, P_[:, k]) for k in range(3)])
        pb = np.array([np.interp(b, seg, P_[:, k]) for k in range(3)])
        mb.extend(C.tube(np.array([pa] + inner + [pb]), r, n, caps=False), m)


def insulator_low(mb: C.MB, base) -> None:
    prof = [(0.010, 0.0), (0.034, 0.0), (0.033, 0.014), (0.023, 0.034), (0.026, 0.050), (0.019, 0.058),
            (0.027, 0.070), (0.0, 0.083)]
    V, F = C.lathe(prof, 8, center=base)
    mb.add(V, F, "porcelain")


def crossarm_low(steel: C.MB, ins: C.MB) -> None:
    x_face = SV_W / 2
    prof = np.array([(0, 0), (0.006, 0), (0.006, 0.069), (0.075, 0.069), (0.075, 0.075), (0, 0.075)], float)
    V, F = C.prism(prof, -0.88, 0.88, origin=(x_face, 0, CROSS_Z - 0.075), ex=(1, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0))
    steel.add(V, F, "galv")
    steel.extend(C.box((-x_face - 0.004, 0.0, CROSS_Z - 0.04), (0.008, 0.12, 0.05)), "galv")
    for s in (-1, 1):
        a = np.array([x_face + 0.03, s * 0.72, CROSS_Z - 0.075])
        b = np.array([x_face + 0.005, s * 0.06, CROSS_Z - 0.62])
        angle_beam(steel, b, a, 0.05, 0.005, up=(1, 0, 0), flip=(1, -s))
    for y in WIRE_Y:
        p = np.array([x_face + 0.045, y, CROSS_Z])
        steel.extend(C.cyl_between(p + (0, 0, -0.03), p + (0, 0, 0.085), 0.009, 6), "galv")
        insulator_low(ins, p + (0, 0, 0.095))


def ground_lead_low(mb: C.MB, top_z: float = CROSS_Z - 0.05) -> None:
    xs = -SV_W / 2 - 0.012
    P_ = [(SV_W / 2 + 0.03, 0.05, top_z), (SV_W / 2 + 0.01, sv_depth(top_z) / 2 + 0.012, top_z - 0.08),
          (xs, sv_depth(top_z - 0.3) / 2 * 0.3, top_z - 0.35), (xs, 0.0, top_z - 1.0), (xs, 0.0, 0.25),
          (xs - 0.02, 0.0, 0.05), (xs - 0.05, 0.0, -0.25)]
    split_tubes(mb, P_, 0.004, 4, 3.0, "steel")


def plate_low(sign: C.MB, red: C.MB, z: float = 2.6) -> None:
    x = SV_W / 2 + 0.004
    V, F = C.prism(C.rect_profile(0.28, 0.21), 0.0, 0.0025, origin=(x, 0.0, z), ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0))
    sign.add(V, F, "paint_white")
    bolt = np.array([(0.012, 0.075), (-0.028, -0.004), (-0.002, -0.004), (-0.016, -0.075), (0.030, 0.012), (0.004, 0.012)])
    V, F = C.prism(bolt, 0.0025, 0.0035, origin=(x, 0.0, z), ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0))
    red.add(V, F, "paint_red")


def _bent(P_, split: int) -> np.ndarray:
    out = []
    for k in range(len(P_) - 1):
        a, b = np.array(P_[k], float), np.array(P_[k + 1], float)
        for u in np.linspace(0, 1, split, endpoint=False):
            out.append(a + (b - a) * u)
    out.append(np.array(P_[-1], float))
    return np.array(out)


def lamp_bracket_low(mb: C.MB) -> None:
    z_low, z_up = 7.45, 7.95
    x0 = SV_W / 2 + 0.03
    P_ = [(x0, 0.0, z_low - 0.1), (x0, 0.0, z_up), (x0 + 0.05, 0.0, z_up + 0.12), (x0 + 0.25, 0.0, z_up + 0.24),
          (x0 + 0.7, 0.0, z_up + 0.30), (x0 + 1.25, 0.0, z_up + 0.30)]
    mb.extend(C.tube(_bent(P_, 2), 0.024, 8), "galv")
    mb.extend(C.cyl_between((x0, 0.0, z_low + 0.05), (x0 + 0.55, 0.0, z_up + 0.27), 0.012, 6), "galv")


def cable_low(mb: C.MB) -> None:
    y = sv_depth(8.5) / 2 + 0.012
    P_ = [(SV_W / 2 + 0.07, 0.25, CROSS_Z + 0.02), (SV_W / 2 + 0.02, y + 0.02, CROSS_Z - 0.1), (0.03, y, CROSS_Z - 0.35),
          (0.03, sv_depth(8.2) / 2 + 0.012, 8.2), (0.04, sv_depth(8.0) / 2 + 0.014, 8.0), (SV_W / 2 + 0.03, 0.05, 7.98)]
    mb.extend(C.tube(np.array(P_), 0.007, 4), "plastic_dark")


def _mat4(R=None, t=(0.0, 0.0, 0.0)) -> np.ndarray:
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    M[:3, 3] = t
    return M


def trolley_tube_low(mb: C.MB) -> None:
    """Труба по секциям (3 м) — отдельные куски: свои острова развёртки; переход-конус — в начале верхней секции."""
    r_top = TR_SEC[-1][2]
    for k, (z0, z1, r) in enumerate(TR_SEC):
        prof = [(r, 0.025)] if k == 0 else [(TR_SEC[k - 1][2], z0 - 0.08)]
        prof.append((r, z0 + 0.08) if k else (r, 0.08))
        if k < len(TR_SEC) - 1:
            prof.append((r, z1 - 0.08))
        else:
            prof += [(r, z1), (r_top + 0.006, TR_TOP), (r_top + 0.006, TR_TOP + 0.02), (r_top * 0.5, TR_TOP + 0.08),
                     (0.0, TR_TOP + 0.09)]
        V, F = C.lathe(prof, 12)
        mb.add(V, F, "paint_grey")


def trolley_base_low(conc: C.MB, paint: C.MB, galv: C.MB) -> None:
    V, F = C.lathe([(0.30, -0.40), (0.325, -0.05), (0.325, 0.07), (0.31, 0.10), (0.0, 0.10)], 12)
    conc.add(V, F, "concrete_old")
    V, F = C.prism(C.rect_profile(0.45, 0.45), 0.10, 0.125)
    paint.add(V, F, "paint_grey")
    for sx in (-1, 1):
        for sy in (-1, 1):
            p = np.array([sx * 0.17, sy * 0.17, 0.125])
            V, F = C.lathe([(0.021, 0.0), (0.021, 0.048)], 6, center=p)        # гайки; шпилька — запеканием
            galv.add(V, F, "galv")
    r0 = TR_SEC[0][2]
    for k in range(4):
        a = math.radians(45 + 90 * k)
        d = np.array([math.cos(a), math.sin(a), 0.0])
        n = np.array([-d[1], d[0], 0.0])
        V, F = C.prism([(0.0, 0.0), (0.12, 0.0), (0.0, 0.26)], -0.006, 0.006, origin=d * r0 + (0, 0, 0.125), ex=d,
                       ey=(0, 0, 1), ez=n)
        paint.add(V, F, "paint_grey")


def span_fitting_low(galv: C.MB, poly: C.MB, rope: C.MB) -> None:
    r = TR_SEC[1][2] if SPAN_Z < TR_SEC[1][1] else TR_SEC[2][2]
    rr, z, h = r + 0.008, SPAN_Z, 0.06
    V, F = C.lathe([(r + 0.001, z - h / 2), (rr, z - h / 2), (rr, z + h / 2), (r + 0.001, z + h / 2)], 10)
    galv.add(V, F, "galv")
    ear, side = np.array([0.0, -1.0, 0.0]), np.array([1.0, 0.0, 0.0])
    for s in (-1, 1):
        c = side * s * (rr + 0.025)
        galv.extend(C.box(c + (0, 0, z), (0.05, 0.012, h)), "galv")
        c = ear * (rr + 0.05) + side * s * 0.014 + (0, 0, z)
        V, F = C.prism(C.rect_profile(0.10, 0.07), -0.004, 0.004, origin=c, ex=ear, ey=(0, 0, 1), ez=side)
        galv.add(V, F, "galv")
    hole = ear * (rr + 0.075) + (0, 0, z)
    galv.extend(C.cyl_between(hole - side * 0.024, hole + side * 0.024, 0.008, 6), "galv")
    s0 = hole + (0, -0.06, 0)
    galv.extend(C.tube(np.array([hole + (0, 0.0, 0.012), s0 + (0, 0, 0.012), s0 + (0, -0.01, 0), s0 + (0, 0, -0.012),
                                 hole + (0, 0, -0.012)]), 0.006, 4), "galv")
    i0 = s0 + (0, -0.01, 0)
    i1 = i0 + (0, -0.42, 0)
    rod_insulator_low(poly, i0, i1, 3, sides=6)
    t1 = i1 + (0, -0.30, 0)
    galv.extend(C.cyl_between(i1, t1, 0.008, 6), "galv")
    galv.extend(C.box((i1 + t1) / 2, (0.04, 0.12, 0.012)), "galv")
    th = [t1, t1 + (0, -0.04, 0.015), t1 + (0, -0.09, 0.0), t1 + (0, -0.04, -0.015), t1]
    galv.extend(C.tube(np.array(th), 0.006, 4), "galv")
    rope.extend(C.tube(np.array([t1 + (0, -0.09, 0.0), t1 + (0, -0.6, -0.01)]), 0.007, 4), "steel")
    galv.extend(C.box(t1 + (0, -0.21, 0.006), (0.03, 0.14, 0.035)), "galv")


def rod_insulator_low(mb: C.MB, a, b, sheds: int = 3, sides: int = 8) -> None:
    """Стержневой изолятор для игры: стержень и sheds рёбер (тела вращения без лишних колец)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    ln = float(np.linalg.norm(d))
    R = C.frame_from(d / ln).T
    prof = [(0.017, 0.0), (0.017, 0.065)]
    pitch = (ln - 0.15) / sheds
    for k in range(sheds):
        z0 = 0.075 + k * pitch
        prof += [(0.014, z0), (0.046, z0 + pitch * 0.28), (0.014, z0 + pitch * 0.45)]
    prof += [(0.017, ln - 0.065), (0.017, ln)]
    V, F = C.lathe(prof, sides)
    mb.add(C.xf(V, R, a), F, "plastic_dark")


def lamp_console_low(mb: C.MB) -> None:
    zc = TR_TOP + 0.02
    P_ = [(0, 0, zc - 0.25), (0, 0, zc + 0.15), (0, -0.06, zc + 0.32), (0, -0.25, zc + 0.48), (0, -0.7, zc + 0.6),
          (0, -1.3, zc + 0.64), (0, -1.75, zc + 0.64)]
    Pd = _bent(P_, 2)
    for _ in range(3):
        Pd[1:-1] = (Pd[:-2] + 2 * Pd[1:-1] + Pd[2:]) / 4
    mb.extend(C.tube(Pd, 0.030, 6), "paint_grey")
    V, F = C.lathe([(TR_SEC[-1][2] + 0.012, TR_TOP - 0.18), (TR_SEC[-1][2] + 0.012, TR_TOP + 0.05),
                    (0.045, TR_TOP + 0.09), (0.034, TR_TOP + 0.12)], 12)
    mb.add(V, F, "paint_grey")


# ---------------------------------------------------------------- развёртка игровых деталей (нормы навыка)
def cyl_unwrap(ob, cut: float = 0.0) -> None:
    """Цилиндрическая развёртка тела вращения вокруг вертикали (труба опоры, фундамент, хомут): U — дуга (угол ×
    радиус вершины), V — высота; шов — сзади (−X, от дороги и таблички). Горизонтальные грани (|n_z| > 0,7) — плоской
    проекцией своими островами. cut > 0 — полоса режется по высоте на куски (длинный остров иначе упирается в край)."""
    import game_lib as G
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    for p in me.polygons:
        cos = [me.vertices[me.loops[li].vertex_index].co for li in p.loop_indices]
        if abs(p.normal.z) > 0.7:
            off = 50.0 if p.normal.z > 0 else 60.0
            for li, co in zip(p.loop_indices, cos):
                uv[li].uv = (co.x + off, co.y)
            continue
        angs = [math.atan2(co.y, co.x) for co in cos]
        if max(angs) - min(angs) > math.pi:
            angs = [a_ + 2 * math.pi if a_ < 0 else a_ for a_ in angs]
        for li, co, a_ in zip(p.loop_indices, cos, angs):
            uv[li].uv = (a_ * math.hypot(co.x, co.y), co.z)
    ob["uv"] = "keep"
    if cut > 0:
        G.split_islands(ob, lambda c: int(c[2] // cut))


def tube_uv(ob, chunks: list, sides: list, radii: list) -> None:
    """Выпрямленная развёртка трубок C.tube подряд (вершины кольцами по sides): U — по окружности (2πr, шов — по
    первой образующей), V — длина по оси; торцы — кружками своими островами. Без сварки вершин (порядок колец)."""
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    co = np.array([v.co[:] for v in me.vertices])
    u_of, v_of, circ, ang = (np.zeros(len(co)) for _ in range(4))
    k = 0
    for n, sd, r in zip(chunks, sides, radii):
        rings = n // sd
        cen = co[k:k + n].reshape(rings, sd, 3).mean(axis=1)
        sl = np.r_[0, np.cumsum(np.linalg.norm(np.diff(cen, axis=0), axis=1))]
        v_of[k:k + n] = np.repeat(sl, sd)
        u_of[k:k + n] = np.tile(np.arange(sd) / sd * 2 * math.pi * r, rings)
        ang[k:k + n] = np.tile(np.arange(sd) / sd * 2 * math.pi, rings)
        circ[k:k + n] = 2 * math.pi * r
        k += n
    for p in me.polygons:
        idx = [me.loops[li].vertex_index for li in p.loop_indices]
        if len(idx) > 4 or len({round(v_of[i], 6) for i in idx}) == 1:      # торец (все вершины одного кольца) — кружок
            for li, i in zip(p.loop_indices, idx):
                rr = circ[i] / (2 * math.pi)
                uv[li].uv = (100.0 + math.cos(ang[i]) * rr, math.sin(ang[i]) * rr + 5.0 * v_of[i])
            continue
        us = [u_of[i] for i in idx]
        wrap = max(us) - min(us) > circ[idx[0]] * 0.5
        for li, i in zip(p.loop_indices, idx):
            uv[li].uv = (u_of[i] + (circ[i] if wrap and u_of[i] < circ[i] * 0.5 else 0.0), v_of[i])
    ob["uv"] = "keep"


def _chunks(mb: C.MB) -> list:
    return [len(v) for v in mb.V]


def split_v(ob, piece: float) -> None:
    """Длинная выпрямленная полоса (V — длина) режется на куски не длиннее piece: грани с серединой развёртки в куске k
    сдвигаются по U на k·1000 — свои острова, укладка не упирается в край атласа."""
    me = ob.data
    uv = me.uv_layers.active.data
    for p in me.polygons:
        vs = [uv[li].uv[1] for li in p.loop_indices]
        k = int((sum(vs) / len(vs)) // piece)
        if k:
            for li in p.loop_indices:
                uv[li].uv = (uv[li].uv[0] + 1000.0 * k, uv[li].uv[1])


def crossarm_low2(arm: C.MB, small: C.MB, pin: C.MB, ins: C.MB) -> None:
    """Траверса (как crossarm_low): уголок и подкосы — призмами (выпрямленные полосы), накладка и штыри — мелочью."""
    x_face = SV_W / 2
    prof = np.array([(0, 0), (0.006, 0), (0.006, 0.069), (0.075, 0.069), (0.075, 0.075), (0, 0.075)], float)
    for y0, y1 in ((-0.88, -0.29), (-0.29, 0.29), (0.29, 0.88)):          # тремя кусками — короче полосы
        V, F = C.prism(prof, y0, y1, origin=(x_face, 0, CROSS_Z - 0.075), ex=(1, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0))
        arm.add(V, F, "galv")
    for s_ in (-1, 1):
        a_ = np.array([x_face + 0.03, s_ * 0.72, CROSS_Z - 0.075])
        b_ = np.array([x_face + 0.005, s_ * 0.06, CROSS_Z - 0.62])
        angle_beam(arm, b_, a_, 0.05, 0.005, up=(1, 0, 0), flip=(1, -s_))
    small.extend(C.box((-x_face - 0.004, 0.0, CROSS_Z - 0.04), (0.008, 0.12, 0.05)), "galv")
    # штырь и изолятор — один раз (у первого провода); остальные три — копии той же сетки внахлёст (game)
    p_ = np.array([x_face + 0.045, WIRE_Y[0], CROSS_Z])
    pin.extend(C.cyl_between(p_ + (0, 0, -0.03), p_ + (0, 0, 0.085), 0.009, 6), "galv")
    insulator_low(ins, p_ + (0, 0, 0.095))


def lamp_bracket_low2(mb: C.MB) -> tuple:
    """Консоль фонаря 0,4 кВ (как lamp_bracket_low) — с раскладкой трубок для развёртки."""
    lamp_bracket_low(mb)
    return [8, 6], [0.024, 0.012]


def trolley_console_low(tube: C.MB, collar: C.MB) -> None:
    """Консоль светильника троллейбусной опоры (как lamp_console_low): изогнутая труба и хомут-оголовок отдельно —
    у трубы выпрямленная полоса, у хомута — цилиндрическая развёртка."""
    zc = TR_TOP + 0.02
    P_ = [(0, 0, zc - 0.25), (0, 0, zc + 0.15), (0, -0.06, zc + 0.32), (0, -0.25, zc + 0.48), (0, -0.7, zc + 0.6),
          (0, -1.3, zc + 0.64), (0, -1.75, zc + 0.64)]
    Pd = _bent(P_, 2)
    for _ in range(3):
        Pd[1:-1] = (Pd[:-2] + 2 * Pd[1:-1] + Pd[2:]) / 4
    tube.extend(C.tube(Pd, 0.030, 6), "paint_grey")
    V, F = C.lathe([(TR_SEC[-1][2] + 0.012, TR_TOP - 0.18), (TR_SEC[-1][2] + 0.012, TR_TOP + 0.05),
                    (0.045, TR_TOP + 0.09), (0.034, TR_TOP + 0.12)], 12)
    collar.add(V, F, "paint_grey")


def trolley_base_low2(conc: C.MB, paint: C.MB, galv: C.MB) -> None:
    """Основание троллейбусной (как trolley_base_low), фундамент — только верх над землёй (под землёй не виден и
    в развёртке не нужен)."""
    V, F = C.lathe([(0.32, -0.06), (0.325, -0.05), (0.325, 0.07), (0.31, 0.10), (0.0, 0.10)], 12)
    conc.add(V, F, "concrete_old")
    V, F = C.prism(C.rect_profile(0.45, 0.45), 0.10, 0.125)
    paint.add(V, F, "paint_grey")
    for sx in (-1, 1):
        for sy in (-1, 1):
            p_ = np.array([sx * 0.17, sy * 0.17, 0.125])
            V, F = C.lathe([(0.021, 0.0), (0.021, 0.048)], 6, center=p_)
            galv.add(V, F, "galv")
    r0 = TR_SEC[0][2]
    for k in range(4):
        a_ = math.radians(45 + 90 * k)
        d = np.array([math.cos(a_), math.sin(a_), 0.0])
        nn = np.array([-d[1], d[0], 0.0])
        V, F = C.prism([(0.0, 0.0), (0.12, 0.0), (0.0, 0.26)], -0.006, 0.006, origin=d * r0 + (0, 0, 0.125), ex=d,
                       ey=(0, 0, 1), ez=nn)
        paint.add(V, F, "paint_grey")


def game(col, parent, key: str, ctx: dict) -> None:
    """Игровые детали варианта (game.py): опора 0,4 кВ — первая; с фонарём берёт её сетки; светильник — одна сетка."""
    import game_lib as G
    if key in ("pole04", "pole04_lamp") and "stand" not in ctx:
        mb = C.MB()
        stand_low(mb)
        # стойка: четыре куска по 2,5 м — выпрямленные полосы (обвод сечения × высота), без сварки (порядок колец)
        ctx["stand"] = G.part(mb, "stand", "Pole04", "concrete", col, parent, sharp=30)
        G.prism_strip_uv(ctx["stand"], _chunks(mb))
        split_v(ctx["stand"], 1.3)                         # куски по 1,3 м — ровнее укладываются рядом с мелочью
        ctx["stand"]["uv_half"] = True                     # куски одной стойки — отступ вполовину
        arm, small, pin, ins = C.MB(), C.MB(), C.MB(), C.MB()
        crossarm_low2(arm, small, pin, ins)
        ctx["crossarm"] = G.part(arm, "crossarm", "Pole04", "galv", col, parent, sharp=35)
        G.prism_strip_uv(ctx["crossarm"], _chunks(arm))   # уголки — выпрямленными полосами, по 0,6 м
        split_v(ctx["crossarm"], 0.6)
        ctx["crossarm"]["uv_half"] = True
        ctx["crossarm"]["uv_scale"] = 0.7                  # на 9 м — видна снизу, издали
        ctx["arm_small"] = G.part(small, "crossarm_small", "Pole04", "galv", col, parent, sharp=35)
        ctx["arm_small"]["uv_scale"] = 0.6
        ctx["pin"] = G.part(pin, "pin", "Pole04", "galv", col, parent, sharp=35)
        ctx["pin"]["uv_scale"] = 0.6
        ctx["insulators"] = G.part(ins, "insulators", "Pole04", "porcelain", col, parent, sharp=60)
        ctx["insulators"]["uv_scale"] = 0.5                # на 9 м, мелкие — видны снизу издали
        ctx["copies"] = []
        for y in WIRE_Y[1:]:                               # три других штыря с изоляторами — та же развёртка
            M = _mat4(None, (0.0, y - WIRE_Y[0], 0.0))
            ctx["copies"].append(G.instance(ctx["insulators"], col, parent, M))
            ctx["copies"].append(G.instance(ctx["pin"], col, parent, M))
        mb = C.MB()
        ground_lead_low(mb)
        # спуск — ржавый пруток: плиточный Rebar (wire_textures.py), не атлас
        ctx["lead"] = G.part(mb, "ground_lead", "Rebar", "rebar", col, parent, sharp=80)
        G.tubes_uv(ctx["lead"], _chunks(mb), 4, 0.08)
        sign, red = C.MB(), C.MB()
        plate_low(sign, red)
        ctx["plate"] = G.part(sign, "plate", "Pole04", "sign", col, parent, sharp=30)
        ctx["plate_red"] = G.part(red, "plate_bolt", "Pole04", "signred", col, parent, sharp=30)
        if key == "pole04":
            return
    if key == "pole04_lamp":
        for k in ("stand", "crossarm", "arm_small", "pin", "insulators", "lead", "plate", "plate_red"):
            G.instance(ctx[k], col, parent)
        for c in ctx["copies"]:
            G.instance(c, col, parent)
        mb = C.MB()
        sides, radii = lamp_bracket_low2(mb)
        ob = G.part(mb, "lamp_bracket", "Pole04", "galv", col, parent, sharp=45)
        tube_uv(ob, _chunks(mb), sides, radii)
        split_v(ob, 0.5)
        ob["uv_half"] = True
        mb = C.MB()
        cable_low(mb)
        ob = G.part(mb, "cable", "Pole04", "cable", col, parent, sharp=80)
        tube_uv(ob, _chunks(mb), [4], [0.007])
        split_v(ob, 0.5)
        ob["uv_scale"], ob["uv_half"] = 0.6, True
        from mathutils import Matrix
        body, glass = C.MB(), C.MB()
        luminaire(body, glass, (0.0, 0.0, 0.0), (1, 0, 0), tilt=0.0, n=10, k=6, neck=8)
        ctx["lamp"] = G.part(body, "luminaire", "Pole04", "lumpaint", col, parent, sharp=50)
        ctx["lamp"]["uv_scale"] = 0.6                      # на 8 м, виден снизу и издали
        ctx["diffuser"] = G.part(glass, "diffuser", "Lamp", "lamp", col, parent, sharp=70)   # без Painter
        M = _mat4(C.rot("y", -8.0), (SV_W / 2 + 0.03 + 1.22, 0.0, 7.95 + 0.30))
        for k in ("lamp", "diffuser"):
            ctx[k].matrix_basis = Matrix(M.tolist())
        return
    if key == "trolley":
        mb = C.MB()
        trolley_tube_low(mb)
        ob = G.part(mb, "tube", "Trolley", "paint", col, parent, sharp=35, weld=1e-6)
        cyl_unwrap(ob, cut=3.05)                           # труба — цилиндром, шов сзади; секции по 3 м — свои острова
        ob["uv_half"] = True
        conc, paint, galv = C.MB(), C.MB(), C.MB()
        trolley_base_low2(conc, paint, galv)
        ob = G.part(conc, "foundation", "Trolley", "concrete", col, parent, sharp=35, weld=1e-6)
        cyl_unwrap(ob)
        G.part(paint, "base", "Trolley", "paint", col, parent, sharp=35)
        tube, collar = C.MB(), C.MB()
        trolley_console_low(tube, collar)
        ob = G.part(tube, "console", "Trolley", "paint", col, parent, sharp=50)
        tube_uv(ob, _chunks(tube), [6], [0.030])
        split_v(ob, 0.7)
        ob["uv_half"] = True
        ob = G.part(collar, "collar", "Trolley", "paint", col, parent, sharp=35)
        cyl_unwrap(ob)
        poly, rope = C.MB(), C.MB()
        span_fitting_low(galv, poly, rope)
        G.part(galv, "hardware", "Trolley", "galv", col, parent, sharp=35)["uv_scale"] = 0.7
        G.part(poly, "rod_insulator", "Trolley", "polymer", col, parent, sharp=60)["uv_scale"] = 0.6
        ob = G.part(rope, "rope", "Trolley", "rope", col, parent, sharp=80)
        tube_uv(ob, _chunks(rope), [4], [0.007])
        ob["uv_scale"] = 0.6
        sign = C.MB()
        r = TR_SEC[0][2]
        V, F = C.prism(C.rect_profile(0.16, 0.10), 0.0, 0.002, origin=(r + 0.004, 0.0, 2.40), ex=(0, 1, 0), ey=(0, 0, 1),
                       ez=(1, 0, 0))
        sign.add(V, F, "paint_white")
        G.part(sign, "number_plate", "Trolley", "sign", col, parent, sharp=30)
        zc = TR_TOP + 0.02
        M = _mat4(C.rot("z", -90.0) @ C.rot("y", -5.0), (0.0, -1.72, zc + 0.64))
        G.instance(ctx["lamp"], col, parent, M)
        G.instance(ctx["diffuser"], col, parent, M)
