"""Гаражи «Проспекта»: кирпичный гараж ГСК (набор garage, 56 штук на карте) и дворовый гараж-ракушка.

Кирпичный (ряды ГСК у путей и во дворах): наружная ширина 3,4 м (стены в кирпич, 250 мм — при шаге ряда 3,4 соседи
стоят стена к стене), глубина 6,0, высота у ворот 2,65, сзади 2,45 (кровля с уклоном назад). Кладка из белого
силикатного кирпича 250 × 120 × 65 со швами 10 мм, цепная перевязка (ряд ложков, ряд тычков). Цоколь — бетонная лента
на 0,1 м над землёй. Перекрытие — три пустотные плиты (1,2 + 1,2 + 1,0 м, 220 мм) с выпуском 0,3 м над воротами,
пустоты видны с торца; по плитам рубероид полосами с нахлёстом, загнут на кромки. Проём 2,5 × 2,1 в обвязке из уголка
63 × 5, бетонная перемычка. Ворота распашные наружу: две створки из листа 2,5 мм на каркасе из уголка 40 × 4 (пояса,
укосина), в правой — калитка 0,7 × 1,7, гаражные петли на штырях (по три), засов-задвижка с навесным замком, шпингалеты
изнутри, табличка под номер. Перед воротами — бетонный пандус.

Ракушка (дворовый металлический гараж 1990-х, фото «Гараж-ракушка на проспекте Вернадского», 1995, pastvu.com):
2,2 × 4,7 × 1,85 м, сечение — почти вертикальные борта со скруглением к крыше, лист с продольным гофром. Задняя часть
(1,55 м) стоит на раме из уголка; передняя (≈ 2/3 длины, со скошенным носом) откидывается вверх-назад на трёх
петлях по коньку у задней части — как капот: борта при подъёме уходят вперёд по бокам, машина заезжает между ними.
Внизу спереди — замок-«сундук» (короб с крышкой на раме, в него заходит язык носа). Открытая — поднята на 70°,
подпорки по бокам.

Оси: ширина — X, глубина — Y, ворота (нос) — к −Y (игровое +Z, как у набора garage). Начало — земля в середине.
"""
from __future__ import annotations

import math

import bpy
import numpy as np

import clib as C

# ================================================================== кирпичный гараж
W, D = 3.4, 6.0
TW = 0.25                     # стена в кирпич
Y0, Y1 = -D / 2, D / 2        # фасад с воротами, задняя стена
Z0 = 0.10                     # верх цоколя = чистый пол
ZF, ZB = 2.43, 2.23           # верх стен у ворот / сзади (низ плит)
SLOPE = (ZF - ZB) / D
SLAB = 0.22
OVER_F, OVER_B = 0.30, 0.05   # выпуск плит над воротами / сзади
GX = 1.25                     # полупроём ворот
GZ1 = 2.20                    # верх проёма
E = 0.008                     # кирпич выступает из шва
COURSE = 0.075                # ряд: 65 + шов 10
BR_MAT = "brick_white"


def z_wall(y: float) -> float:
    return ZF - (y - Y0) * SLOPE


def brick(mb: C.MB, o, u, v, n, a0: float, a1: float, b0: float, b1a: float, b1b: float, rng, mat: str) -> None:
    """Кирпич-усечённая призма: тыл в стене, лицо с фаской 3 мм; верх может быть скошен (b1a у a0, b1b у a1)."""
    ch = 0.003
    p = rng.uniform(-0.0015, 0.0015)
    back, front = -E - 0.002, p
    V = []
    for depth, inset in ((back, 0.0), (front, ch)):
        for a, b in ((a0 + inset, b0 + inset), (a1 - inset, b0 + inset), (a1 - inset, b1b - inset), (a0 + inset, b1a - inset)):
            V.append(o + u * a + v * b + n * depth)
    F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mb.add(np.array(V), F, mat)


def brick_face(mb: C.MB, o, u, v, a0: float, a1: float, b0: float, top, holes=(), seed: int = 0,
               shift: float = 0.0, mat: str = BR_MAT) -> None:
    """Кладка грани: ряды ложков и тычков (цепная перевязка), швы 10 мм; top(a) — верх кладки (под плиту)."""
    o, u, v = (np.asarray(x, float) for x in (o, u, v))
    n = np.cross(u, v)
    rng = np.random.default_rng(seed)
    k = 0
    while True:
        vb0 = b0 + k * COURSE + 0.005
        vb1 = vb0 + 0.065
        tmin = min(top(a0), top(a1))
        tmax = max(top(a0), top(a1))
        if vb0 > tmax - 0.02:
            break
        header = k % 2 == 1
        ln = 0.12 if header else 0.25
        pitch = ln + 0.010
        off = shift + (0.0625 if header else (0.0 if k % 4 == 0 else 0.13))
        # свободные отрезки ряда: грань минус проёмы, задевающие ряд
        segs = [(a0, a1)]
        for (h0, h1, hz0, hz1) in holes:
            if vb1 <= hz0 or vb0 >= hz1:
                continue
            nxt = []
            for (s0, s1) in segs:
                if h1 <= s0 or h0 >= s1:
                    nxt.append((s0, s1))
                    continue
                if h0 > s0:
                    nxt.append((s0, h0))
                if h1 < s1:
                    nxt.append((h1, s1))
            segs = nxt
        for (s0, s1) in segs:
            s = a0 - off - pitch
            while s < s1:
                c0, c1 = max(s + 0.005, s0 + 0.005), min(s + 0.005 + ln, s1 - 0.005)
                if c1 - c0 > 0.025:
                    t0, t1 = top(c0) - 0.006, top(c1) - 0.006
                    if vb0 < min(t0, t1) - 0.012:
                        brick(mb, o, u, v, n, c0, c1, vb0, min(vb1, t0), min(vb1, t1), rng, mat)
                s += pitch
        k += 1
        _ = tmin


def walls(col, parent, interior: bool) -> None:
    core = C.MB()
    # ядро стен (шов): утоплено на E под лицо кирпича со всех сторон
    for x0, x1 in ((-W / 2 + E, -W / 2 + TW - E), (W / 2 - TW + E, W / 2 - E)):
        poly = [(Y0 + E, Z0), (Y1 - E, Z0), (Y1 - E, z_wall(Y1 - E)), (Y0 + E, z_wall(Y0 + E))]
        core.extend(C.prism(poly, x0, x1, ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0)), "mortar")
    poly = [(Y1 - TW + E, Z0), (Y1 - E, Z0), (Y1 - E, z_wall(Y1 - E)), (Y1 - TW + E, z_wall(Y1 - TW + E))]
    core.extend(C.prism(poly, -W / 2 + TW - E - 0.01, W / 2 - TW + E + 0.01, ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0)),
                "mortar")
    for s in (-1, 1):                                            # простенки у ворот
        xa, xb = sorted((s * (W / 2 - TW + E + 0.01), s * GX))
        core.extend(C.box2((xa, Y0 + E, Z0), (xb, Y0 + TW - E, GZ1)), "mortar")
    core.build("Brick_WallCore", col, parent)
    # кладка снаружи
    br = C.MB()
    holes_front = [(-GX, GX, 0.0, GZ1 + 0.002), (-1.5, 1.5, GZ1, ZF + 0.1)]
    brick_face(br, (0, Y0, 0), (1, 0, 0), (0, 0, 1), -W / 2, W / 2, Z0, lambda a: z_wall(Y0), holes_front, 1)
    vent = [(-0.07, 0.07, 1.86, 2.02)]
    brick_face(br, (0, Y1, 0), (-1, 0, 0), (0, 0, 1), -W / 2, W / 2, Z0, lambda a: z_wall(Y1), vent, 2)
    brick_face(br, (-W / 2, 0, 0), (0, -1, 0), (0, 0, 1), -D / 2, D / 2, Z0, lambda a: z_wall(-a), (), 3, 0.06)
    brick_face(br, (W / 2, 0, 0), (0, 1, 0), (0, 0, 1), -D / 2, D / 2, Z0, lambda a: z_wall(a), (), 4, 0.06)
    if interior:
        yi0, yi1 = Y0 + TW, Y1 - TW
        xi = W / 2 - TW
        brick_face(br, (-xi, 0, 0), (0, 1, 0), (0, 0, 1), yi0, yi1, Z0, lambda a: z_wall(a), (), 5)
        brick_face(br, (xi, 0, 0), (0, -1, 0), (0, 0, 1), -yi1, -yi0, Z0, lambda a: z_wall(-a), (), 6)
        brick_face(br, (0, yi1, 0), (1, 0, 0), (0, 0, 1), -xi, xi, Z0, lambda a: z_wall(yi1), vent, 7)
        brick_face(br, (0, yi0, 0), (-1, 0, 0), (0, 0, 1), -xi, xi, Z0, lambda a: z_wall(yi0),
                   [(-GX, GX, 0.0, GZ1 + 0.002), (-xi, xi, GZ1, ZF + 0.1)], 8)
    br.build("Brick_Masonry", col, parent)
    # продух в задней стене: решётка из прутка
    gr = C.MB()
    for x in np.linspace(-0.05, 0.05, 4):
        gr.extend(C.cyl_between((x, Y1 - 0.02, 1.865), (x, Y1 - 0.02, 2.015), 0.004, 6), "steel_dark")
    gr.build("Brick_VentGrille", col, parent)


def foundation(col, parent, interior: bool) -> None:
    fd = C.MB()
    h = 0.025
    fd.extend(C.box2((-W / 2 - h, Y0 - h, -0.35), (-W / 2 + TW + h, Y1 + h, Z0)), "concrete_old")
    fd.extend(C.box2((W / 2 - TW - h, Y0 - h, -0.35), (W / 2 + h, Y1 + h, Z0)), "concrete_old")
    fd.extend(C.box2((-W / 2 + TW - h, Y1 - TW - h, -0.35), (W / 2 - TW + h, Y1 + h, Z0)), "concrete_old")
    for s in (-1, 1):
        xa, xb = sorted((s * (W / 2 - TW + h), s * GX))
        fd.extend(C.box2((xa, Y0 - h, -0.35), (xb, Y0 + TW + h, Z0)), "concrete_old")
    fd.build("Brick_Foundation", col, parent, bevel=0.01, seg=1)
    fl = C.MB()
    fl.extend(C.box2((-W / 2 + TW, Y0 + TW - 0.01, -0.05), (W / 2 - TW, Y1 - TW, Z0)), "concrete")       # пол
    fl.extend(C.box2((-GX, Y0 - 0.01, -0.05), (GX, Y0 + TW, Z0 - 0.005)), "concrete")                   # под порогом
    # пандус: клин от порога к земле
    poly = [(Y0 - 0.70, 0.0), (Y0 - 0.01, 0.0), (Y0 - 0.01, Z0 - 0.005), (Y0 - 0.66, 0.012)]
    fl.extend(C.prism(poly, -1.40, 1.40, ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0)), "concrete_old")
    fl.build("Brick_FloorRamp", col, parent, bevel=0.008, seg=1)
    # порог из уголка
    th = C.MB()
    th.extend(C.prism(C.angle_profile(0.05, 0.005), -GX, GX, origin=(0, Y0 - 0.002, Z0 - 0.005), ex=(0, 1, 0),
                      ey=(0, 0, 1), ez=(1, 0, 0)), "steel_dark")
    th.build("Brick_Threshold", col, parent)


def lintel_and_slabs(col, parent) -> None:
    li = C.MB()
    li.extend(C.box2((-1.5, Y0, GZ1), (1.5, Y0 + TW, ZF - 0.008)), "concrete")
    li.build("Brick_Lintel", col, parent, bevel=0.012, seg=2)
    widths = [1.19, 1.19, 0.99]
    x = -W / 2
    ya, yb = Y0 - OVER_F, Y1 + OVER_B
    for i, w in enumerate(widths):
        sl = C.MB()
        poly = [(ya, z_wall(ya)), (yb, z_wall(yb)), (yb, z_wall(yb) + SLAB), (ya, z_wall(ya) + SLAB)]
        sl.extend(C.prism(poly, x + 0.005, x + w - 0.005, ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0)), "concrete")
        ob = sl.build(f"Brick_Slab_{i + 1}", col, parent, bevel=0.012, seg=2)
        # пустоты Ø159 с шагом 185 — видны с торца над воротами
        n = int((w - 0.10) / 0.185)
        cut = C.MB()
        x0 = x + w / 2 - (n - 1) * 0.185 / 2
        zc = z_wall(ya) + SLAB / 2
        for k in range(n):
            V, F = C.lathe([(0.0795, -0.15), (0.0795, 0.15)], 20)
            cut.add(C.xf(V, C.rot("x", 90 + math.degrees(SLOPE)), (x0 + k * 0.185, ya, zc)), F)
        cutter = cut.build("_cut", col, parent)
        m = ob.modifiers.new("Пустоты", "BOOLEAN")
        m.operation, m.solver, m.object = "DIFFERENCE", "EXACT", cutter
        with bpy.context.temp_override(object=ob):
            bpy.ops.object.modifier_move_to_index(modifier="Пустоты", index=0)
            bpy.ops.object.modifier_apply(modifier="Пустоты")
        bpy.data.objects.remove(cutter, do_unlink=True)
        x += w + 0.01 if i < 2 else w
    # рубероид: лист по плитам с загибом на передний и задний торец, полосы рулонов с нахлёстом
    rf = C.MB()

    def top(y: float) -> float:
        return z_wall(y) + SLAB

    t = 0.006
    poly = [(ya - t, top(ya) - 0.03), (ya, top(ya) - 0.03), (ya, top(ya)), (yb, top(yb)), (yb, top(yb) - 0.05),
            (yb + t, top(yb) - 0.05), (yb + t, top(yb) + t), (ya - t, top(ya) + t)]
    rf.extend(C.prism(poly, -W / 2, W / 2, ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0)), "roofing")
    for xs in (-0.80, 0.15, 1.10):                               # нахлёст рулонов 1 м
        poly = [(ya - t - 0.004, top(ya) - 0.028), (ya - t, top(ya) - 0.028), (ya - t, top(ya) + t),
                (yb + t, top(yb) + t), (yb + t, top(yb) - 0.045), (yb + t + 0.004, top(yb) - 0.045),
                (yb + t + 0.004, top(yb) + t + 0.004), (ya - t - 0.004, top(ya) + t + 0.004)]
        rf.extend(C.prism(poly, xs, xs + 0.10, ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0)), "roofing")
    rf.build("Brick_Roofing", col, parent)
    # капельник из оцинковки под загибом над воротами
    dr = C.MB()
    poly = [(ya - t - 0.0025, top(ya) - 0.034), (ya - t - 0.0005, top(ya) - 0.034), (ya - t - 0.0005, top(ya) + t + 0.002),
            (ya - t + 0.03, top(ya) + t + 0.002), (ya - t + 0.03, top(ya) + t + 0.004), (ya - t - 0.0025, top(ya) + t + 0.004)]
    dr.extend(C.prism(poly, -W / 2, W / 2, ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0)), "galv")
    dr.build("Brick_Drip", col, parent)


def angle_member(mb: C.MB, p0, p1, d_in, d_back, w: float = 0.04, t: float = 0.004, mat: str = "paint_brown") -> None:
    """Уголок вдоль p0 → p1 пяткой по линии: одна полка по d_in, другая по d_back."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    ln = float(np.linalg.norm(p1 - p0))
    mb.extend(C.prism(C.angle_profile(w, t), 0.0, ln, origin=p0, ex=d_in, ey=d_back, ez=(p1 - p0) / ln), mat)


def gate_frame(col, parent) -> None:
    """Обвязка проёма: уголок 63 × 5, полка по лицу стены и полка по откосу."""
    fr = C.MB()
    w, t = 0.063, 0.005
    for s in (-1, 1):
        # пятка на ребре проёма у лица стены; полки — наружу по лицу (±X) и вглубь по откосу (+Y)
        fr.extend(C.prism([(0, 0), (w, 0), (w, -t), (-t, -t), (-t, w), (0, w)], Z0 - 0.002, GZ1 + w,
                          origin=(s * GX, Y0, 0), ex=(s, 0, 0), ey=(0, 1, 0), ez=(0, 0, 1)), "paint_brown")
    fr.extend(C.prism([(0, 0), (w, 0), (w, -t), (-t, -t), (-t, w), (0, w)], -GX - w, GX + w,
                      origin=(0, Y0, GZ1), ex=(0, 0, 1), ey=(0, 1, 0), ez=(1, 0, 0)), "paint_brown")
    fr.build("Brick_GateFrame", col, parent)


HINGE_Y = Y0 - 0.025
LEAF_X = 1.28                 # створки перекрывают обвязку на 30 мм
LZ0, LZ1 = Z0 + 0.03, GZ1 + 0.035
SH_Y0, SH_Y1 = Y0 - 0.0115, Y0 - 0.009          # лист створки
WK = (0.20, 0.90, 0.33, 2.03)                    # проём калитки в правой створке


def hinge(mb: C.MB, x: float, z: float, side: int, leaf_y: float, strap_dir: int, fixed: bool) -> None:
    """Гаражная петля: две трубки Ø35 по 80 мм на штыре; подвижная — с полосой на листе."""
    r = 0.0175
    if fixed:
        mb.extend(C.cyl((x, HINGE_Y, z - 0.042), r, 0.080, 16), "steel")
        mb.extend(C.box2((x + side * 0.002, HINGE_Y + 0.008, z - 0.08), (x - side * 0.035, Y0 - 0.002, z - 0.005)), "steel")
    else:
        mb.extend(C.cyl((x, HINGE_Y, z + 0.042), r, 0.080, 16), "steel")
        mb.extend(C.cyl((x, HINGE_Y, z + 0.086), 0.010, 0.008, 12), "steel")          # шляпка штыря
        x2 = x + strap_dir * 0.22
        mb.extend(C.box2((min(x, x2), leaf_y - 0.006, z + 0.012), (max(x, x2), leaf_y, z + 0.072)), "steel")


def leaf(col, parent, side: int) -> list:
    """Створка: лист 2,5 мм снаружи, каркас из уголка 40 × 4 внутри; side = −1 левая, +1 правая (с калиткой)."""
    xh = side * LEAF_X
    xm = side * 0.005
    xa, xb = sorted((xh, xm))
    sh = C.MB()
    if side < 0:
        sh.extend(C.box2((xa, SH_Y0, LZ0), (xb, SH_Y1, LZ1)), "paint_brown")
    else:
        w0, w1, z0, z1 = WK
        sh.extend(C.box2((xa, SH_Y0, LZ0), (w0, SH_Y1, LZ1)), "paint_brown")
        sh.extend(C.box2((w1, SH_Y0, LZ0), (xb, SH_Y1, LZ1)), "paint_brown")
        sh.extend(C.box2((w0, SH_Y0, LZ0), (w1, SH_Y1, z0)), "paint_brown")
        sh.extend(C.box2((w0, SH_Y0, z1), (w1, SH_Y1, LZ1)), "paint_brown")
    obs = [sh.build("Gate_Leaf_" + ("L" if side < 0 else "R"), col, parent, bevel=0.0008, seg=1)]
    fr = C.MB()
    din_x = -side                       # от петлевой кромки внутрь створки
    yb = SH_Y1
    xi_h = side * (GX - 0.012)          # каркас входит в проём, мимо обвязки и упора порога
    xi_m = side * 0.012
    zb, zt = Z0 + 0.055, GZ1 - 0.012
    # пояса и стойки
    angle_member(fr, (xi_h, yb, zb), (xi_m, yb, zb), (0, 0, 1), (0, 1, 0))
    angle_member(fr, (xi_m, yb, zt), (xi_h, yb, zt), (0, 0, -1), (0, 1, 0))
    angle_member(fr, (xi_h, yb, zb), (xi_h, yb, zt), (din_x, 0, 0), (0, 1, 0))
    angle_member(fr, (xi_m, yb, zt), (xi_m, yb, zb), (-din_x, 0, 0), (0, 1, 0))
    if side < 0:
        angle_member(fr, (xi_h, yb, 1.18), (xi_m, yb, 1.18), (0, 0, 1), (0, 1, 0))
        # укосина: от низа у петель к верху у притвора
        p0 = np.array([xi_h + din_x * 0.04, yb, zb + 0.05])
        p1 = np.array([xi_m - din_x * 0.04, yb, 1.14])
        d = (p1 - p0) / np.linalg.norm(p1 - p0)
        n_in = np.cross((0, 1, 0), d)
        angle_member(fr, p0, p1, n_in if n_in[2] > 0 else -n_in, (0, 1, 0))
        p0 = np.array([xi_h + din_x * 0.04, yb, 1.22])
        p1 = np.array([xi_m - din_x * 0.04, yb, zt - 0.05])
        d = (p1 - p0) / np.linalg.norm(p1 - p0)
        n_in = np.cross((0, 1, 0), d)
        angle_member(fr, p0, p1, n_in if n_in[2] > 0 else -n_in, (0, 1, 0))
    else:
        w0, w1, z0, z1 = WK
        for x, dx in ((w0 - 0.005, -1), (w1 + 0.005, 1)):
            angle_member(fr, (x, yb, zb + 0.04), (x, yb, zt - 0.04), (dx, 0, 0), (0, 1, 0))
        angle_member(fr, (w0, yb, z1 + 0.005), (w1, yb, z1 + 0.005), (0, 0, 1), (0, 1, 0))
        angle_member(fr, (w0, yb, 1.18), (xi_m, yb, 1.18), (0, 0, 1), (0, 1, 0))
        angle_member(fr, (w1, yb, 1.18), (xi_h, yb, 1.18), (0, 0, 1), (0, 1, 0))
    obs.append(fr.build("Gate_LeafFrame_" + ("L" if side < 0 else "R"), col, parent))
    # петли (подвижные половины) и мелочь на листе
    hw = C.MB()
    hx = side * 1.30
    for z in (0.40, 1.18, 1.96):
        hinge(hw, hx, z, side, SH_Y0, -side, fixed=False)
    if side < 0:
        # засов: две скобы-направляющие, ригель с ручкой, проушина замка
        for x in (-0.36, -0.14):
            hw.extend(C.box2((x - 0.02, SH_Y0 - 0.028, 1.07), (x + 0.02, SH_Y0, 1.075)), "steel")
            hw.extend(C.box2((x - 0.02, SH_Y0 - 0.028, 1.125), (x + 0.02, SH_Y0, 1.13)), "steel")
            hw.extend(C.box2((x - 0.02, SH_Y0 - 0.028, 1.07), (x + 0.02, SH_Y0 - 0.024, 1.13)), "steel")
        # табличка под номер
        hw.extend(C.box2((-0.80, SH_Y0 - 0.003, 1.78), (-0.50, SH_Y0, 1.96)), "paint_white")
        # шпингалеты изнутри у притвора: низ и верх
        for (z0, z1) in ((LZ0 - 0.06, 0.55), (1.80, LZ1 + 0.10)):
            hw.extend(C.cyl_between((-0.045, SH_Y1 + 0.03, z0), (-0.045, SH_Y1 + 0.03, z1), 0.008, 10), "steel")
            for z in (z0 + 0.12 if z0 < 1 else z1 - 0.30, z0 + 0.30 if z0 < 1 else z1 - 0.12):
                hw.extend(C.box2((-0.065, SH_Y1, z - 0.015), (-0.025, SH_Y1 + 0.045, z + 0.015)), "steel")
    else:
        # ответная скоба засова и проушина замка
        hw.extend(C.box2((0.02, SH_Y0 - 0.028, 1.07), (0.10, SH_Y0, 1.075)), "steel")
        hw.extend(C.box2((0.02, SH_Y0 - 0.028, 1.125), (0.10, SH_Y0, 1.13)), "steel")
        hw.extend(C.box2((0.06, SH_Y0 - 0.028, 1.07), (0.10, SH_Y0 - 0.024, 1.13)), "steel")
    obs.append(hw.build("Gate_LeafHardware_" + ("L" if side < 0 else "R"), col, parent))
    return obs


def wicket(col, parent) -> list:
    w0, w1, z0, z1 = WK
    sh = C.MB()
    sh.extend(C.box2((w0 + 0.004, SH_Y0, z0 + 0.004), (w1 - 0.004, SH_Y1, z1 - 0.004)), "paint_brown")
    fr = C.MB()
    angle_member(fr, (w0 + 0.02, SH_Y1, z0 + 0.02), (w1 - 0.02, SH_Y1, z0 + 0.02), (0, 0, 1), (0, 1, 0), 0.032, 0.003)
    angle_member(fr, (w1 - 0.02, SH_Y1, z1 - 0.02), (w0 + 0.02, SH_Y1, z1 - 0.02), (0, 0, -1), (0, 1, 0), 0.032, 0.003)
    angle_member(fr, (w0 + 0.02, SH_Y1, z1 - 0.02), (w0 + 0.02, SH_Y1, z0 + 0.02), (1, 0, 0), (0, 1, 0), 0.032, 0.003)
    angle_member(fr, (w1 - 0.02, SH_Y1, z0 + 0.02), (w1 - 0.02, SH_Y1, z1 - 0.02), (-1, 0, 0), (0, 1, 0), 0.032, 0.003)
    angle_member(fr, (w0 + 0.02, SH_Y1, 1.18), (w1 - 0.02, SH_Y1, 1.18), (0, 0, 1), (0, 1, 0), 0.032, 0.003)
    for z in (0.62, 1.74):                                     # петли калитки (на кромке к петлям створки)
        fr.extend(C.cyl((w1 + 0.012, SH_Y0 - 0.014, z + 0.035), 0.012, 0.065, 14), "steel")
        fr.extend(C.box2((w1 - 0.16, SH_Y0 - 0.005, z + 0.01), (w1 + 0.004, SH_Y0, z + 0.06)), "steel")
    # ручка-скоба, накладка цилиндра, проушина
    P = np.array([(w0 + 0.07, SH_Y0, 1.02), (w0 + 0.07, SH_Y0 - 0.05, 1.03), (w0 + 0.07, SH_Y0 - 0.05, 1.17),
                  (w0 + 0.07, SH_Y0, 1.18)])
    fr.extend(C.tube(P, 0.009, 10), "steel")
    fr.extend(C.box2((w0 + 0.04, SH_Y0 - 0.006, 1.24), (w0 + 0.10, SH_Y0, 1.36)), "steel")
    fr.extend(C.cyl((w0 + 0.07, SH_Y0 - 0.009, 1.32), 0.012, 0.008, 16, "y"), "galv")
    fr.extend(C.cyl((w1 + 0.012, SH_Y0 - 0.014, 0.62 - 0.035), 0.012, 0.065, 14), "steel")   # ответные трубки на створке
    fr.extend(C.cyl((w1 + 0.012, SH_Y0 - 0.014, 1.74 - 0.035), 0.012, 0.065, 14), "steel")
    return [sh.build("Gate_Wicket", col, parent, bevel=0.0008, seg=1), fr.build("Gate_WicketFrame", col, parent)]


def fixed_hinges_and_lock(col, parent, locked: bool) -> None:
    hw = C.MB()
    for side in (-1, 1):
        for z in (0.40, 1.18, 1.96):
            hinge(hw, side * 1.30, z, side, SH_Y0, -side, fixed=True)
    hw.build("Gate_FrameHinges", col, parent)
    if not locked:
        return
    lk = C.MB()
    # ригель задвинут в ответную скобу; навесной замок через ушки ригеля и скобы
    lk.extend(C.box2((-0.40, SH_Y0 - 0.024, 1.08), (0.09, SH_Y0 - 0.012, 1.12)), "steel")
    P = np.array([(-0.30, SH_Y0 - 0.018, 1.12), (-0.30, SH_Y0 - 0.018, 1.19), (-0.30, SH_Y0 - 0.06, 1.21)])
    lk.extend(C.tube(P, 0.008, 10), "steel")                                                  # ручка ригеля
    lk.extend(C.box2((0.04, SH_Y0 - 0.032, 1.00), (0.05, SH_Y0 - 0.010, 1.075)), "steel")      # ушки
    lk.extend(C.box2((0.10, SH_Y0 - 0.032, 1.00), (0.11, SH_Y0 - 0.010, 1.075)), "steel")
    V, F = C.box((0.075, SH_Y0 - 0.05, 0.93), (0.07, 0.03, 0.06))
    lk.add(V, F, "galv")                                                                       # корпус замка
    V, F = C.tube(np.array([(0.052 + 0.045 * (1 - math.cos(a)) / 2, SH_Y0 - 0.05, 0.96 + 0.05 * math.sin(a))
                            for a in np.linspace(0, math.pi, 10)]), 0.005, 8)
    lk.add(V, F, "steel")
    lk.build("Gate_Padlock", col, parent, bevel=0.004, seg=1)


# ---------------------------------------------------------------- нутро открытого гаража
def tire(mb: C.MB, c, rng) -> None:
    """Шина 195/65 R15, лёжа: профиль с протектором (канавки), борт до обода."""
    ro, w, rr = 0.317, 0.195, 0.195
    prof = []
    for k in range(13):
        a = math.pi * (k / 12) - math.pi / 2
        prof.append((ro - 0.035 + 0.035 * math.cos(a), w / 2 * math.sin(a) * 1.0))
    tread = []
    for z in np.linspace(-0.08, 0.08, 9):
        tread.append((ro - (0.008 if int(round((z + 0.08) / 0.02)) % 2 else 0.0), z))
    inner = [(rr + 0.02, w / 2 - 0.02), (rr, w / 2 - 0.03), (rr, -w / 2 + 0.03), (rr + 0.02, -w / 2 + 0.02)]
    loop = [(ro - 0.03, -w / 2)] + tread + [(ro - 0.03, w / 2), (ro - 0.09, w / 2 + 0.004), (rr + 0.03, w / 2 - 0.004)] + \
        inner + [(rr + 0.03, -w / 2 + 0.004), (ro - 0.09, -w / 2 - 0.004)]
    n = 40
    rings = []
    for r, z in loop:
        a = np.arange(n) * 2 * np.pi / n
        rings.append(np.c_[np.cos(a) * r, np.sin(a) * r, np.full(n, z)])
    rings.append(rings[0])
    V = np.vstack(rings)
    F = []
    for k in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            F.append((k * n + i, k * n + j, (k + 1) * n + j, (k + 1) * n + i))
    # последнее кольцо совпадает с первым — сварится при сборке
    mb.add(C.xf(V, C.rot("z", rng.uniform(0, 360)), c), F, "rubber", smooth=True)
    _ = prof


def jerrycan(mb: C.MB, c, yaw: float) -> None:
    """Канистра 20 л: 345 × 165 × 470, три ручки, горловина с крышкой."""
    R = C.rot("z", yaw)
    V, F = C.box((0, 0, 0.215), (0.165, 0.345, 0.43))
    mb.add(C.xf(V, R, c), F, "paint_green")


def jerrycan_handles(mb: C.MB, c, yaw: float) -> None:
    R = C.rot("z", yaw)
    for y in (-0.10, 0.0, 0.10):
        P = np.array([(0, y - 0.02, 0.43), (0, y - 0.02, 0.47), (0, y + 0.02, 0.47), (0, y + 0.02, 0.43)])
        V, F = C.tube(P, 0.008, 8)
        mb.add(C.xf(V, R, c), F, "paint_green")
    V, F = C.cyl((0, 0.15, 0.45), 0.025, 0.05, 14)
    mb.add(C.xf(V, R, c), F, "paint_green")


def interior(col, parent) -> None:
    rng = np.random.default_rng(5)
    st = C.MB()
    # стеллаж у задней стены: стойки из перфоуголка, четыре полки из фанеры
    x0, x1, y0, y1 = -1.15, 1.15, Y1 - TW - 0.48, Y1 - TW - 0.03
    for x, sx in ((x0, 1), (x1, -1)):
        for y, sy in ((y0, 1), (y1, -1)):
            st.extend(C.prism(C.angle_profile(0.04, 0.003), Z0, Z0 + 2.0, origin=(x, y, 0), ex=(sx, 0, 0), ey=(0, sy, 0),
                              ez=(0, 0, 1)), "steel")
    for z in (0.25, 0.75, 1.25, 1.75):
        st.extend(C.box2((x0, y0, Z0 + z), (x1, y1, Z0 + z + 0.018)), "plywood")
        for y in (y0, y1):
            st.extend(C.box2((x0, y - 0.015, Z0 + z - 0.03), (x1, y + 0.015, Z0 + z)), "steel")
    st.build("Garage_Shelf", col, parent)
    # на полках: коробки, банки краски, банки
    sb = C.MB()
    for z, items in ((0.268, [(-0.8, 0.45, 0.35, 0.30), (-0.25, 0.4, 0.35, 0.22), (0.55, 0.5, 0.36, 0.28)]),
                     (0.768, [(-0.6, 0.35, 0.3, 0.25), (0.2, 0.42, 0.36, 0.32)]),
                     (1.268, [(-0.9, 0.3, 0.3, 0.2), (0.75, 0.45, 0.32, 0.3)]),
                     (1.768, [(0.0, 0.55, 0.38, 0.25)])):
        for (x, w, d, h) in items:
            V, F = C.box((x, (y0 + y1) / 2, Z0 + z + h / 2), (w, d, h), C.rot("z", rng.uniform(-6, 6)))
            sb.add(V, F, "plywood")
    for (x, z) in ((0.05, 0.268), (0.15, 0.268), (-0.3, 0.768), (-0.18, 0.768), (0.45, 1.268), (-0.45, 1.268)):
        V, F = C.cyl((x, y0 + 0.15, Z0 + z + 0.095), 0.085, 0.19, 18)
        sb.add(V, F, "paint_grey")
    sb.build("Garage_ShelfItems", col, parent, bevel=0.006, seg=1)
    # верстак у левой стены: каркас из уголка, столешница из доски, тиски
    wb = C.MB()
    xa, xb, ya, yb = -W / 2 + TW + 0.02, -W / 2 + TW + 0.62, 0.0, 1.70
    for x in (xa + 0.02, xb - 0.02):
        for y in (ya + 0.02, yb - 0.02):
            wb.extend(C.box((x, y, Z0 + 0.43), (0.05, 0.05, 0.86)), "steel_dark")
    for y in (ya + 0.02, yb - 0.02):
        wb.extend(C.box(((xa + xb) / 2, y, Z0 + 0.20), (xb - xa, 0.04, 0.04)), "steel_dark")
    wb.extend(C.box2((xa, ya, Z0 + 0.18), (xb, yb, Z0 + 0.20)), "plywood")
    wt = C.MB()
    wt.extend(C.box2((xa - 0.01, ya - 0.02, Z0 + 0.86), (xb + 0.03, yb + 0.02, Z0 + 0.90)), "wood")
    wt.build("Garage_WorkbenchTop", col, parent, bevel=0.004, seg=1)
    # тиски на углу
    vx, vy = xb - 0.07, yb - 0.25
    wb.extend(C.box((vx, vy, Z0 + 0.95), (0.12, 0.10, 0.10)), "paint_blue")
    wb.extend(C.box((vx + 0.06, vy, Z0 + 0.97), (0.06, 0.10, 0.06)), "paint_blue")
    wb.extend(C.cyl_between((vx + 0.09, vy, Z0 + 0.96), (vx + 0.25, vy, Z0 + 0.96), 0.008, 10), "steel")
    wb.extend(C.cyl_between((vx + 0.25, vy - 0.08, Z0 + 0.96), (vx + 0.25, vy + 0.08, Z0 + 0.96), 0.006, 8), "steel")
    wb.build("Garage_Workbench", col, parent)
    # шины стопкой в правом заднем углу, канистры, ведро
    tr = C.MB()
    for k in range(4):
        tire(tr, (0.92, 1.45, Z0 + 0.0975 + k * 0.196), rng)
    tire(tr, (0.80, -0.10, Z0 + 0.0975), rng)
    tr.build("Garage_Tires", col, parent, weld=1e-6, sharp=50)
    jc = C.MB()
    jerrycan(jc, (-1.02, -0.45, Z0), 8.0)
    jerrycan(jc, (-0.82, -0.62, Z0), -14.0)
    jh = C.MB()
    jerrycan_handles(jh, (-1.02, -0.45, Z0), 8.0)
    jerrycan_handles(jh, (-0.82, -0.62, Z0), -14.0)
    jh.build("Garage_CanHandles", col, parent)
    jc.build("Garage_Cans", col, parent, bevel=0.012, seg=2)
    # лампа на проводе, щиток с трубой проводки
    el = C.MB()
    zc = z_wall(0.4)
    el.extend(C.cyl_between((0.0, 0.4, zc), (0.0, 0.4, zc - 0.40), 0.003, 6), "plastic_dark")
    el.extend(C.cyl((0.0, 0.4, zc - 0.43), 0.02, 0.06, 14), "plastic_dark")
    el.extend(C.lathe([(0.0, -0.11), (0.03, -0.10), (0.03, -0.06), (0.012, -0.03), (0.012, 0.0)], 18,
                      center=(0.0, 0.4, zc - 0.46)), "lamp")
    el.extend(C.box2((W / 2 - TW - 0.10, Y0 + TW + 0.25, 1.45), (W / 2 - TW, Y0 + TW + 0.45, 1.75)), "paint_grey")
    el.extend(C.cyl_between((W / 2 - TW - 0.03, Y0 + TW + 0.35, 1.75), (W / 2 - TW - 0.03, Y0 + TW + 0.35, z_wall(-2.4)),
                            0.01, 8), "plastic_dark")
    el.build("Garage_Electrics", col, parent, bevel=0.003, seg=1, weld=1e-6)
    # поддон у правой стены, метла в углу
    pl = C.MB()
    R = C.rot("y", -82)
    base = np.array([W / 2 - TW - 0.18, -1.40, Z0])
    for x in (0.0, 0.55, 1.10):
        V, F = C.box((x + 0.05, 0.0, 0.05), (0.10, 0.80, 0.10))
        pl.add(C.xf(V, R, base), F, "wood")
    for y in np.linspace(-0.35, 0.35, 5):
        V, F = C.box((0.6, y, 0.11), (1.2, 0.10, 0.022))
        pl.add(C.xf(V, R, base), F, "wood")
    pl.extend(C.cyl_between((-W / 2 + TW + 0.06, Y1 - TW - 0.60, Z0 + 0.25), (-W / 2 + TW + 0.03, Y1 - TW - 0.75, Z0 + 1.45),
                            0.012, 8), "wood")
    pl.extend(C.lathe([(0.0, 0.0), (0.13, 0.0), (0.15, 0.30), (0.145, 0.30), (0.125, 0.006), (0.0, 0.006)], 24,
                      center=(0.55, 1.95, Z0)), "galv")                                   # ведро
    pl.build("Garage_Junk", col, parent, bevel=0.002, seg=1, weld=1e-6)


def brick_garage(col, root, open_: bool) -> None:
    walls(col, root, open_)
    foundation(col, root, open_)
    lintel_and_slabs(col, root)
    gate_frame(col, root)
    fixed_hinges_and_lock(col, root, not open_)
    for side in (-1, 1):
        pv = C.pivot("Hinge_Leaf_" + ("L" if side < 0 else "R"), col, root, (side * 1.30, HINGE_Y, 0.0))
        obs = leaf(col, root, side)
        if side > 0:
            wp = C.pivot("Hinge_Wicket", col, root, (WK[1] + 0.012, SH_Y0 - 0.014, 0.0))
            for ob in wicket(col, root):
                C.parent_keep(ob, wp)
            C.parent_keep(wp, pv)
        for ob in obs:
            C.parent_keep(ob, pv)
        if open_:
            pv.rotation_euler = (0.0, 0.0, math.radians(100.0 if side > 0 else -100.0))
    if open_:
        interior(col, root)
        # ригель отодвинут, замок висит на ушке ригеля открытым — не ставим
    bpy.context.view_layer.update()


# ================================================================== ракушка
SW, SL, SH = 2.20, 4.70, 1.85
SY0, SY1 = -SL / 2, SL / 2
SJ = 0.80                       # стык передней и задней части (по Y)
NOSE = math.radians(32.0)       # скос носа от вертикали
HINGE_Z = SH + 0.012            # ось петель — по коньку
T_SHEET = 0.0015


def shell_profile(grow: float = 0.0) -> np.ndarray:
    """Сечение (x, z) по наружной стороне с продольным гофром: борта почти вертикальны, скругление к крыше.

    Обход слева снизу через крышу направо вниз; grow — раздутие (передняя часть чуть шире задней)."""
    hw = SW / 2 + grow
    zr = SH + grow
    rc = 0.46
    base = []
    for z in np.linspace(0.06, 1.33, 14):                       # левый борт снизу вверх, лёгкий завал внутрь
        base.append((-hw + (z - 0.06) * 0.012, z))
    xc, zc = -hw + 0.016 + rc, 1.33
    for a in np.linspace(math.pi, math.pi / 2, 12)[1:]:
        base.append((xc + rc * math.cos(a), zc + (zr - 0.03 - zc) * math.sin(a)))
    for x in np.linspace(xc, 0, 8)[1:]:
        base.append((x, zr - 0.03 + 0.03 * (1 - (x / xc) ** 2)))
    half = np.array(base)
    full = np.vstack([half, (half[-2::-1] * [-1, 1])])
    # равномерно по длине дуги и гофр: трапеция шаг 0,20, гребень 0,06, глубина 0,018 (наружу)
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(full, axis=0), axis=1))]
    total = seg[-1]
    pitch = total / round(total / 0.20)
    marks = []
    s = 0.0
    while s < total - 1e-6:
        for d in (0.0, 0.035, 0.095, 0.13):
            if s + d < total:
                marks.append(s + d)
        s += pitch
    marks.append(total)
    marks = np.array(marks)
    P = np.c_[np.interp(marks, seg, full[:, 0]), np.interp(marks, seg, full[:, 1])]
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    N = np.c_[-T[:, 1], T[:, 0]]                                 # наружу (обход по часовой сверху)
    if N[len(N) // 2, 1] < 0:
        N = -N
    ph = (marks % pitch)
    up = np.where((ph > 0.034) & (ph < 0.096), 1.0, 0.0)
    P = P + N * (up * 0.018)[:, None]
    P[0, 1] = P[-1, 1] = 0.06
    env = np.c_[np.interp(marks, seg, full[:, 0]), np.interp(marks, seg, full[:, 1])] + N * 0.018
    env[0, 1] = env[-1, 1] = 0.06
    return P, N, env


def shell_part(mb: C.MB, y_front, y_back: float, grow: float, slant: bool) -> tuple:
    """Тонкая оболочка части: наружный и внутренний (−1,5 мм) профили, торцы замкнуты кромкой."""
    P, N, env = shell_profile(grow)
    Pi = P - N * T_SHEET
    loop = np.vstack([P, Pi[::-1]])                              # замкнутый тонкий профиль
    rings = []
    for y_of in (y_front, y_back):
        ys = np.array([y_of(z) if callable(y_of) else y_of for z in loop[:, 1]])
        rings.append(np.c_[loop[:, 0], ys, loop[:, 1]])
    V, F = C.loft(rings, closed=True, cap0=True, cap1=True)
    mb.add(V, F, "paint_green")
    _ = slant
    return P, N, env


def frames(mb: C.MB, Pi: np.ndarray, N: np.ndarray, ys) -> None:
    """Внутренние дуги каркаса из трубы 40 × 20 по сечению."""
    path2 = Pi - N * 0.012
    for y in ys:
        path = np.c_[path2[:, 0], np.full(len(path2), y), path2[:, 1]]
        mb.extend(C.sweep(C.rect_profile(0.02, 0.04), path, True, False, (0, 1, 0)), "paint_green")


def nose_y(z: float) -> float:
    return SY0 + z * math.tan(NOSE)


def shell(col, root, open_: bool) -> None:
    rear = C.MB()
    P, N, env = shell_part(rear, SJ + 0.012, SY1, 0.0, False)
    frames(rear, P - N * T_SHEET, N, (SJ + 0.06, SY1 - 0.06))
    # задняя стенка: лист по внутреннему контуру с вертикальными рёбрами
    Pi = P - N * T_SHEET
    poly = [(x, z) for x, z in Pi]
    rear.extend(C.prism(poly, SY1 - 0.002, SY1, ex=(1, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0)), "paint_green")
    for x in (-0.6, 0.0, 0.6):
        rear.extend(C.box2((x - 0.02, SY1 - 0.002, 0.08), (x + 0.02, SY1 + 0.012, SH - 0.08)), "paint_green")
    # окантовка стыка: П-профиль по контуру переднего торца задней части
    tr = np.c_[env[:, 0], np.full(len(env), SJ + 0.035), env[:, 1]]
    rear.extend(C.sweep(C.rect_profile(0.004, 0.05), tr, True, False, (0, 1, 0)), "paint_green")
    rear.build("Shell_Rear", col, root, bevel=0.0006, seg=1)
    # рама из уголка 50 × 5 по земле, замок-«сундук» спереди
    fr = C.MB()
    hw = SW / 2
    for s in (-1, 1):
        fr.extend(C.prism(C.angle_profile(0.05, 0.005), SY0 - 0.05, SY1 + 0.02, origin=(s * (hw + 0.004), 0, 0),
                          ex=(-s, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0)), "steel_dark")
    for y, sy in ((SY0 - 0.05, 1), (SY1 + 0.02, -1), (SJ, 1)):
        fr.extend(C.prism(C.angle_profile(0.05, 0.005), -hw - 0.004, hw + 0.004, origin=(0, y, 0), ex=(0, sy, 0),
                          ey=(0, 0, 1), ez=(1, 0, 0)), "steel_dark")
    lb = (-0.16, SY0 - 0.21, 0.0, 0.16, SY0 - 0.05, 0.19)       # короб замка
    fr.extend(C.box2(lb[:3], (lb[3], lb[4], lb[5] - 0.012)), "paint_green")
    fr.extend(C.box2((lb[0] - 0.008, lb[1] - 0.008, lb[5] - 0.012), (lb[3] + 0.008, lb[4] + 0.004, lb[5])), "paint_green")
    fr.extend(C.cyl_between((lb[0], lb[4] - 0.006, lb[5] + 0.006), (lb[3], lb[4] - 0.006, lb[5] + 0.006), 0.008, 10),
              "steel")                                         # петля крышки
    fr.extend(C.box2((-0.03, lb[1] - 0.012, 0.09), (0.03, lb[1] - 0.004, 0.17)), "steel")   # язычок крышки с ушком
    fr.build("Shell_BaseFrame", col, root, bevel=0.0015, seg=1)
    # передняя часть — на пустышке петель по коньку
    pv = C.pivot("Hinge_Shell", col, root, (0.0, SJ, HINGE_Z))
    fp = C.MB()
    P, N, env = shell_part(fp, nose_y, SJ, 0.012, True)
    Pi = P - N * T_SHEET
    frames(fp, Pi, N, (SY0 + 1.30, SY0 + 2.30, SJ - 0.05))
    # нос: лист по внутреннему контуру на скошенной плоскости, три выдавленных ребра
    n_dir = np.array([0.0, -math.cos(NOSE), math.sin(NOSE)])     # наружу-вверх
    ev = np.array([0.0, math.sin(NOSE), math.cos(NOSE)])          # вверх по носу
    poly = [(x, z / math.cos(NOSE)) for x, z in Pi]
    fp.extend(C.prism(poly, 0.0, 0.002, origin=(0, SY0, 0), ex=(1, 0, 0), ey=ev, ez=-n_dir), "paint_green")
    for x in (-0.55, 0.0, 0.55):
        top = np.interp(abs(x), np.abs(Pi[: len(Pi) // 2, 0])[::-1], Pi[: len(Pi) // 2, 1][::-1]) - 0.12
        a0, a1 = 0.10 / math.cos(NOSE), top / math.cos(NOSE)
        fp.extend(C.prism([(x - 0.025, a0), (x + 0.025, a0), (x + 0.018, a1), (x - 0.018, a1)], -0.002, 0.012,
                          origin=(0, SY0, 0), ex=(1, 0, 0), ey=ev, ez=n_dir), "paint_green")
    # ручка-скоба на носу
    hz = 0.55
    hp = np.array([0.0, nose_y(hz), hz]) - n_dir * 0.002
    P_h = np.array([hp + np.array([x, 0, 0]) + n_dir * d + ev * e for x, d, e in
                    ((-0.13, 0.0, 0.0), (-0.12, 0.05, 0.0), (0.12, 0.05, 0.0), (0.13, 0.0, 0.0))])
    fp.extend(C.tube(P_h, 0.010, 10), "steel")
    for x in (-0.13, 0.13):
        fp.extend(C.prism(C.rect_profile(0.04, 0.06), -0.004, 0.0, origin=hp + np.array([x, 0, 0]), ex=(1, 0, 0), ey=ev,
                          ez=-n_dir), "steel")
    # окантовка носа уголком по контуру
    edge = np.c_[env[:, 0], [nose_y(z) + 0.012 for z in env[:, 1]], env[:, 1]]
    fp.extend(C.sweep(C.rect_profile(0.012, 0.03), edge, True, False, (0, 1, 0)), "paint_green")
    # нижние уголки бортов и пояс у стыка
    for s in (-1, 1):
        x = s * (SW / 2 + 0.012)
        fp.extend(C.box2((x - 0.03 * (s > 0), nose_y(0.06), 0.06), (x + 0.03 * (s < 0), SJ - 0.01, 0.10)), "paint_green")
    tr = np.c_[env[:, 0], np.full(len(env), SJ - 0.035), env[:, 1]]
    fp.extend(C.sweep(C.rect_profile(0.004, 0.05), tr, True, False, (0, 1, 0)), "paint_green")
    # поперечные швы листов (нахлёст) — два пояса
    for yb in (SY0 + 1.55, SY0 + 2.45):
        band = np.c_[env[:, 0], np.full(len(env), yb), env[:, 1]]
        fp.extend(C.sweep(C.rect_profile(0.003, 0.06), band, True, False, (0, 1, 0)), "paint_green")
    # язык замка: полоса от низа носа вперёд-вверх над крышкой короба и вниз в прорезь
    a = np.array([0.0, nose_y(0.10) - 0.004, 0.10])
    b = np.array([0.0, SY0 - 0.125, 0.215])
    d = (b - a) / np.linalg.norm(b - a)
    fp.extend(C.prism(C.rect_profile(0.05, 0.008), 0.0, float(np.linalg.norm(b - a)), origin=a, ex=(1, 0, 0),
                      ey=np.cross(d, (1, 0, 0)), ez=d), "steel")
    fp.extend(C.box2((-0.025, SY0 - 0.133, 0.12), (0.025, SY0 - 0.117, 0.219)), "steel")
    ob = fp.build("Shell_Front", col, root, bevel=0.0006, seg=1)
    C.parent_keep(ob, pv)
    # петли по коньку: три карты, штырь
    hg = C.MB()
    for x in (-0.45, 0.0, 0.45):
        hg.extend(C.cyl((x, SJ, HINGE_Z), 0.014, 0.09, 16, "x"), "steel")
        hg.extend(C.box2((x - 0.05, SJ + 0.01, SH - 0.006), (x + 0.05, SJ + 0.17, SH + 0.003)), "steel")
    hg.build("Shell_HingesFixed", col, root)
    hm = C.MB()
    for x in (-0.45, 0.0, 0.45):
        hm.extend(C.box2((x - 0.05, SJ - 0.17, SH + 0.0), (x + 0.05, SJ - 0.01, SH + 0.009)), "steel")
        hm.extend(C.cyl((x + 0.085, SJ, HINGE_Z), 0.014, 0.07, 16, "x"), "steel")
        hm.extend(C.cyl((x - 0.085, SJ, HINGE_Z), 0.014, 0.07, 16, "x"), "steel")
    ob = hm.build("Shell_HingesMoving", col, root)
    C.parent_keep(ob, pv)
    if open_:
        ang = 70.0
        pv.rotation_euler = (math.radians(-ang), 0.0, 0.0)
        bpy.context.view_layer.update()
        # подпорки: от рамы у стыка к нижнему поясу борта поднятой части
        pr = C.MB()
        a = math.radians(-ang)
        for s in (-1, 1):
            x = s * (SW / 2 + 0.03)
            yl, zl = -0.6, -1.6                                  # точка на борту в осях петли (у низа, близ стыка)
            yw = SJ + yl * math.cos(a) - zl * math.sin(a)
            zw = HINGE_Z + yl * math.sin(a) + zl * math.cos(a)
            yf = SJ - 1.5
            pr.extend(C.cyl_between((x, yf, 0.05), (x, yw, zw), 0.016, 12), "steel")          # телескопическая стойка
            pr.extend(C.cyl_between((x, yf + (yw - yf) * 0.45, 0.05 + (zw - 0.05) * 0.45), (x, yw, zw), 0.020, 12),
                      "steel")
            pr.extend(C.box2((x - 0.02, yf - 0.05, 0.0), (x + 0.02, yf + 0.05, 0.05)), "steel")
        pr.build("Shell_Props", col, root, bevel=0.002, seg=1)


# ================================================================== варианты
VARIANTS = {"brick_closed": "Кирпичный · закрыт", "brick_open": "Кирпичный · открыт",
            "shell_closed": "Ракушка · закрыта", "shell_open": "Ракушка · открыта"}
STEP = 5.0
META = {
    "folder": "Гаражи", "name": "Garages", "title": "Гаражи: кирпичный ГСК и ракушка", "step": 5.0,
    "shots": [["3/4 с ворот", [4.4, -8.4, 2.6], [0.0, -1.5, 1.3], 30], ["3/4 сзади", [-4.6, 7.8, 3.8], [0.0, 0.5, 1.2], 30],
              ["ворота крупно", [-1.3, -5.6, 1.7], [-0.25, -3.0, 1.2], 35]],
    "shots_by": {
        "brick_open": [["3/4 с ворот", [4.4, -8.4, 2.6], [0.0, -1.8, 1.3], 30],
                       ["3/4 сзади", [-4.6, 7.8, 3.8], [0.0, 0.5, 1.2], 30],
                       ["нутро", [0.4, -5.8, 1.7], [0.0, 0.8, 1.0], 24]],
        "shell_closed": [["3/4 спереди", [3.8, -6.6, 2.4], [0.0, -0.6, 0.9], 30],
                         ["3/4 сзади", [-3.6, 6.4, 2.6], [0.0, 0.4, 0.9], 30],
                         ["замок и нос", [1.3, -4.4, 1.0], [0.0, -2.2, 0.45], 35]],
        "shell_open": [["3/4 спереди", [5.0, -7.6, 3.2], [0.0, -0.6, 1.6], 30],
                       ["3/4 сзади", [-4.2, 6.8, 3.2], [0.0, 0.0, 1.6], 30],
                       ["петли и подпорка", [2.9, 2.6, 3.0], [0.0, 0.3, 1.6], 30]],
    },
}


def build(keys: list[str]) -> dict:
    out = {}
    for i, k in enumerate(keys):
        name = VARIANTS[k]
        col = C.collection(name)
        r = C.root(("GarageBrick" if k.startswith("brick") else "GarageShell") + f" | {name}", col, (i * STEP, 0.0, 0.0))
        if k.startswith("brick"):
            brick_garage(col, r, k.endswith("open"))
        else:
            shell(col, r, k.endswith("open"))
        out[k] = name
    return out
