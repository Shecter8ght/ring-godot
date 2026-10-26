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
    "game_shots": [["3/4 с ворот", [4.4, -8.4, 2.6], [0.0, -1.5, 1.3], 30], ["3/4 сзади", [-4.6, 7.8, 3.8], [0.0, 0.5, 1.2], 30],
                   ["с глаз у ворот", [-1.6, -5.2, 1.65], [-0.3, -3.0, 1.3], 30]],
    "game_shots_by": {
        "brick_open": [["3/4 с ворот", [4.4, -8.4, 2.6], [0.0, -1.8, 1.3], 30],
                       ["3/4 сзади", [-4.6, 7.8, 3.8], [0.0, 0.5, 1.2], 30],
                       ["нутро", [0.4, -5.8, 1.7], [0.0, 0.8, 1.0], 24]],
        "shell_closed": [["3/4 спереди", [3.8, -6.6, 2.4], [0.0, -0.6, 0.9], 30],
                         ["3/4 сзади", [-3.6, 6.4, 2.6], [0.0, 0.4, 0.9], 30],
                         ["с глаз у носа", [1.4, -4.4, 1.65], [0.0, -1.6, 0.7], 30]],
        "shell_open": [["3/4 спереди", [5.0, -7.6, 3.2], [0.0, -0.6, 1.6], 30],
                       ["3/4 сзади", [-4.2, 6.8, 3.2], [0.0, 0.0, 1.6], 30],
                       ["петли и подпорка", [2.9, 2.6, 3.0], [0.0, 0.3, 1.6], 30]],
    },
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


# ================================================================ игровая версия (LOD0)
# Наборы Painter: GarageBrick — кладка снаружи (2K: кирпич должен читаться вблизи); Garage — цоколь, пандус, перемычка,
# плиты, рубероид, обвязка, створки, петли, замок (2K); GarageInt — нутро открытого: стены изнутри, откосы, пол (2K);
# GarageProps — вещи в открытом (1K); Shell — ракушка целиком (2K). Кладка, швы, пустоты плит, гофр, рёбра, ручки,
# мелкие уголки — только в запекании. Створки и передняя часть ракушки — общие сетки закрытого варианта, повёрнутые
# на тех же шарнирах. Замок с ригелем — без запекания (в подробной форме его нет у открытого, а на листе остался бы
# отпечаток): простая сетка только у закрытого. Ящики коллизии — оси Blender, [центр, размер]: у закрытых —
# тело без пандуса (пандус под ногами), у открытого кирпичного — стены, простенки, перемычка и плиты (можно войти),
# у открытой ракушки — задняя часть и поднятая передняя выше 1,2 м.
GAME = {
    "ids": {"brick_closed": "PC02_GARAGE", "brick_open": "PC02_GARAGE_OPEN", "shell_closed": "PC02_SHELL",
            "shell_open": "PC02_SHELL_OPEN"},
    "bake": ["brick_closed", "brick_open", "shell_closed", "shell_open"],
    "skip_high": ["Gate_Padlock"],
    "res": {"GarageBrick": 11, "Garage": 11, "GarageInt": 11, "Shell": 11},
    "solids": {
        "brick_closed": [[[0.0, 0.0, 1.21], [3.4, 6.08, 2.42]], [[0.0, -0.13, 2.53], [3.4, 6.45, 0.30]]],
        "brick_open": [[[-1.575, 0.0, 1.21], [0.25, 6.0, 2.42]], [[1.575, 0.0, 1.21], [0.25, 6.0, 2.42]],
                       [[0.0, 2.875, 1.21], [2.9, 0.25, 2.42]], [[-1.35, -2.875, 1.21], [0.2, 0.25, 2.42]],
                       [[1.35, -2.875, 1.21], [0.2, 0.25, 2.42]], [[0.0, -2.875, 2.31], [2.5, 0.25, 0.22]],
                       [[0.0, -0.13, 2.53], [3.4, 6.45, 0.30]]],
        "shell_closed": [[[0.0, 0.0, 0.93], [2.24, 4.70, 1.86]]],
        "shell_open": [[[0.0, 1.575, 0.93], [2.24, 1.55, 1.86]], [[0.0, -0.55, 2.80], [2.30, 2.70, 3.20]]],
    },
}


def _pivot_matrix(p, R) -> np.ndarray:
    """Поворот R вокруг точки p (4×4, оси варианта)."""
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = np.asarray(p, float) - R @ np.asarray(p, float)
    return M


def _quad(mb: C.MB, pts, mat: str, t: float = 0.02) -> None:
    """Плоская грань стены как тонкая замкнутая плита: лицо — по точкам, тыл — на t в толщу (направление — к центру
    гаража по горизонтали или вниз у пола), чтобы пересчёт нормалей не вывернул одиночную грань."""
    P = np.array(pts, float)
    ex = P[1] - P[0]
    ex /= np.linalg.norm(ex)
    k = 2
    while abs(np.dot(np.cross(ex, P[k] - P[0]), np.cross(ex, P[k] - P[0]))) < 1e-10:
        k += 1
    n = np.cross(ex, P[k] - P[0])
    n /= np.linalg.norm(n)
    c = P.mean(axis=0)
    inward = -np.array([c[0], c[1], 0.0]) if abs(n[2]) < 0.5 else np.array([0.0, 0.0, -1.0])
    if np.dot(n, inward) < 0:                     # тыл плиты — внутрь (к центру/вниз)
        n = -n
    ey = np.cross(n, ex)
    poly = [((p - P[0]) @ ex, (p - P[0]) @ ey) for p in P]
    V, F = C.prism(poly, 0.0, t, origin=P[0], ex=ex, ey=ey, ez=n)
    mb.add(V, F, mat)


def _keep_faces(ob, keep) -> None:
    """Оставить только видимые грани плиты-стены (keep(центр, нормаль) → да/нет): тыл и торцы в толще стены — вон,
    иначе они занимают половину атласа кладки. Нормали уже наружу — пересчёт после этого не нужен."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    dead = []
    for f in bm.faces:
        n = np.array(f.normal)
        P = np.array([v.co[:] for v in f.verts])
        u = np.cross(n, (0, 0, 1)) if abs(n[2]) < 0.9 else np.array([1.0, 0, 0])
        u /= np.linalg.norm(u)
        w = np.cross(n, u)
        thin = min(np.ptp(P @ u), np.ptp(P @ w)) < 0.05          # торцы плит-стен (2 см) — не лицо
        if thin or not keep(np.array(f.calc_center_median()), n, f.calc_area()):
            dead.append(f)
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()


def _outward(c, n, area) -> bool:
    return area > 0.02 and abs(n[2]) < 0.3 and n @ np.array([c[0], c[1], 0.0]) > 0


def _inward(c, n, area) -> bool:
    return area > 0.02 and abs(n[2]) < 0.3 and n @ np.array([c[0], c[1], 0.0]) < 0


SIDE_WALLS_UV = '[["x", 1, 0.9, 0.6], ["x", -1, 0.9, 0.6]]'
GATE_UV = 1.3


def _prism_uv(ob, chunks: list, piece: float = 0.0) -> None:
    """Выпрямленная развёртка выдавленных профилей (C.prism подряд, по 2 кольца из n точек): бока — полосой, U — длина
    по контуру, V — по выдавливанию; торцы (все вершины одного кольца) — плоской проекцией профиля; длинная полоса
    режется по U на куски не длиннее piece. Своя, а не game_lib.prism_strip_uv: там у профиля из 4 точек торцы —
    тоже четырёхугольники и принимаются за бока (развёртка торца вырождается в линию)."""
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    co = np.array([v.co[:] for v in me.vertices])
    info = {}                                            # вершина → (призма, кольцо, номер в кольце)
    data = []
    k = 0
    for c, nv in enumerate(chunks):
        n = nv // 2
        r0, r1 = co[k:k + n], co[k + n:k + 2 * n]
        s_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.vstack([r0, r0[:1]]), axis=0), axis=1))]
        ax = r1[0] - r0[0]
        h = float(np.linalg.norm(ax))
        ax = ax / max(h, 1e-9)
        e1 = r0[1] - r0[0]
        e1 = e1 - ax * (e1 @ ax)
        e1 /= max(np.linalg.norm(e1), 1e-9)
        e2 = np.cross(ax, e1)
        data.append((k, n, s_, h, r0[0], e1, e2))
        for i in range(n):
            info[k + i] = (c, 0, i)
            info[k + n + i] = (c, 1, i)
        k += nv
    for p in me.polygons:
        idx = [me.loops[li].vertex_index for li in p.loop_indices]
        c = info[idx[0]][0]
        k0, n, s_, h, o, e1, e2 = data[c]
        rings = {info[i][1] for i in idx}
        if len(rings) == 1:                              # торец
            for li, i in zip(p.loop_indices, idx):
                uv[li].uv = ((co[i] - o) @ e1 + 7000.0 + 10.0 * c, (co[i] - o) @ e2)
            continue
        cols = [info[i][2] for i in idx]
        wrap = max(cols) - min(cols) > n // 2
        us = [s_[q] + (s_[-1] if wrap and q < n // 2 else 0.0) for q in cols]
        kk = int((sum(us) / len(us)) // piece) if piece > 0 else 0
        for li, i, u in zip(p.loop_indices, idx, us):
            uv[li].uv = (u + 100.0 * c, h * info[i][1] + 1000.0 * kk)
    ob["uv"] = "keep"


def _drop_faces(ob, dead) -> None:
    """Убрать невидимые грани игровой детали (dead(центр, нормаль) → да): закрытое другой деталью и в земле."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    kill = [f for f in bm.faces if dead(np.array(f.calc_center_median()), np.array(f.normal))]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()


def _game_brick_shared(col, parent, ctx: dict) -> None:
    import game_lib as G
    hw = W / 2
    # кладка снаружи — плоскостями по лицу кирпича (швы и выступ кирпича — в запекании)
    mb = C.MB()
    for ya, yb in ((Y0, 0.0), (0.0, Y1)):                    # боковые стены — половинами (острова для квадрата)
        _quad(mb, [(-hw, ya, Z0), (-hw, yb, Z0), (-hw, yb, z_wall(yb)), (-hw, ya, z_wall(ya))][::-1], "brick")
        _quad(mb, [(hw, ya, Z0), (hw, yb, Z0), (hw, yb, z_wall(yb)), (hw, ya, z_wall(ya))], "brick")
    _quad(mb, [(-hw, Y1, Z0), (hw, Y1, Z0), (hw, Y1, z_wall(Y1)), (-hw, Y1, z_wall(Y1))][::-1], "brick")
    for s in (-1, 1):
        pts = [(s * hw, Y0, Z0), (s * GX, Y0, Z0), (s * GX, Y0, GZ1), (s * 1.5, Y0, GZ1), (s * 1.5, Y0, ZF), (s * hw, Y0, ZF)]
        _quad(mb, pts if s > 0 else pts[::-1], "brick")
    ctx["walls"] = G.part(mb, "walls", "GarageBrick", "brick", col, parent, sharp=30)
    _keep_faces(ctx["walls"], _outward)
    ctx["walls"]["uv_rules"] = SIDE_WALLS_UV                 # в ряду боковые стены закрыты соседями — реже
    G.box_unwrap(ctx["walls"])                               # боковые стены — пополам: квадратный атлас без пустот
    G.split_islands(ctx["walls"], lambda c: 1 if (abs(c[0]) > W / 2 - 0.01 and c[1] > 0) else 0)
    # цоколь: полоса 0,1 м с полкой 25 мм по периметру
    h = 0.025
    mb = C.MB()
    # полосами по сторонам (кольцо одной гранью развернулось бы островом с пустой серединой)
    xo, xi, yo0, yo1, yi0, yi1 = hw + h, hw - TW - h, Y0 - h, Y1 + h, Y0 + TW + h, Y1 - TW - h
    for x0, x1, y0, y1 in ((-xo, -xi, yo0, yo1), (xi, xo, yo0, yo1), (-xi, xi, yi1, yo1), (-xi, -GX, yo0, yi0),
                           (GX, xi, yo0, yi0)):
        V, F = C.prism([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], -0.10, Z0)
        mb.add(V, F, "concrete")
    ctx["plinth"] = G.part(mb, "plinth", "Garage", "concrete", col, parent, sharp=30)
    _prism_uv(ctx["plinth"], [len(v) for v in mb.V], piece=3.4)
    # подошва — в земле; бока внутрь — под полом; стыки полос — внутри цоколя
    _drop_faces(ctx["plinth"], lambda c, n: n[2] < -0.9 or (abs(n[2]) < 0.3 and n @ np.array([c[0], c[1], 0.0]) < 0
                                                              and abs(c[0]) < hw - 0.05 and abs(c[1]) < D / 2 - 0.05))
    # пандус, перемычка, плиты: профили — выпрямленными полосами по контуру (верх, кромка, низ — одним куском)
    mb = C.MB()
    poly = [(Y0 - 0.70, 0.0), (Y0 - 0.01, 0.0), (Y0 - 0.01, Z0 - 0.005), (Y0 - 0.66, 0.012)]
    mb.extend(C.prism(poly, -1.40, 1.40, ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0)), "concrete")
    ya, yb = Y0 - OVER_F, Y1 + OVER_B
    poly = [(ya, z_wall(ya)), (yb, z_wall(yb)), (yb, z_wall(yb) + SLAB), (ya, z_wall(ya) + SLAB)]
    mb.extend(C.prism(poly, -hw, hw, ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0)), "concrete")
    ob = G.part(mb, "ramp_slabs", "Garage", "concrete", col, parent, sharp=30)
    _prism_uv(ob, [len(v) for v in mb.V], piece=3.4)
    # невидимое: верх плит (под рубероидом), подошва пандуса
    _drop_faces(ob, lambda c, n: (n[2] > 0.9 and c[2] > ZF + 0.05) or (n[2] < -0.9 and c[2] < 0.05))
    ob["uv_rules"] = '[["x", 1, 0.9, 0.4], ["x", -1, 0.9, 0.4]]'   # торцы плит: в ряду закрыты соседними плитами
    ctx["concrete"] = ob
    mb = C.MB()
    mb.extend(C.box2((-1.5, Y0, GZ1), (1.5, Y0 + TW, ZF - 0.008)), "concrete")
    ctx["lintel"] = ob = G.part(mb, "lintel", "Garage", "concrete", col, parent, sharp=30)
    _drop_faces(ob, lambda c, n: n[2] > 0.9 or abs(n[0]) > 0.9)  # верх — под плитой, торцы — в кладке
    # рубероид: лист с загибом на передний и задний торец (полосы нахлёста — в запекании)
    mb = C.MB()
    t = 0.006

    def top(y: float) -> float:
        return z_wall(y) + SLAB
    poly = [(ya - t, top(ya) - 0.03), (ya, top(ya) - 0.03), (ya, top(ya)), (yb, top(yb)), (yb, top(yb) - 0.05),
            (yb + t, top(yb) - 0.05), (yb + t, top(yb) + t + 0.004), (ya - t, top(ya) + t + 0.004)]
    mb.extend(C.prism(poly, -hw - 0.004, hw + 0.004, ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0)), "roofing")
    ctx["roof"] = G.part(mb, "roofing", "Garage", "roofing", col, parent, sharp=30)
    _prism_uv(ctx["roof"], [len(v) for v in mb.V], piece=3.4)
    _drop_faces(ctx["roof"], lambda c, n: n[2] < -0.5)          # низ рубероида лежит на плите
    ctx["roof"]["uv_rules"] = '[["z", 1, 0.9, 0.5]]'             # верх виден только сверху
    # обвязка проёма: уголок 63 × 5
    mb = C.MB()
    w, tt = 0.063, 0.005
    prof = [(0, 0), (w, 0), (w, -tt), (-tt, -tt), (-tt, w), (0, w)]
    for s in (-1, 1):
        mb.extend(C.prism(prof, Z0 - 0.002, GZ1 + w, origin=(s * GX, Y0, 0), ex=(s, 0, 0), ey=(0, 1, 0), ez=(0, 0, 1)),
                  "paint")
    mb.extend(C.prism(prof, -GX - w, GX + w, origin=(0, Y0, GZ1), ex=(0, 0, 1), ey=(0, 1, 0), ez=(1, 0, 0)), "paint")
    ctx["frame"] = G.part(mb, "gate_frame", "Garage", "paint", col, parent, sharp=30)
    G.prism_strip_uv(ctx["frame"], [len(v) for v in mb.V])     # уголок — полосой по обводу (полки и рёбра одним куском)
    ctx["frame"]["uv_scale"] = GATE_UV                          # ворота смотрят вблизи — плотнее
    # неподвижные половины петель
    mb = C.MB()
    for s in (-1, 1):
        for z in (0.40, 1.18, 1.96):
            mb.extend(C.cyl((s * 1.30, HINGE_Y, z - 0.042), 0.0175, 0.080, 8), "steel")
    ctx["hinges_fixed"] = G.part(mb, "hinges_fixed", "Garage", "steel", col, parent, sharp=50)
    # створки: лист снаружи и объём каркаса внутри проёма (калитка в правой — заодно, её щели — в запекании),
    # подвижные половины петель — с ними
    for side in (-1, 1):
        mb = C.MB()
        xa, xb = sorted((side * LEAF_X, side * 0.005))
        mb.extend(C.box2((xa, SH_Y0, LZ0), (xb, SH_Y1, LZ1)), "paint")
        fa, fb = sorted((side * (GX - 0.012), side * 0.012))
        mb.extend(C.box2((fa, SH_Y1, Z0 + 0.055 - 0.02), (fb, SH_Y1 + 0.040, GZ1 - 0.012 + 0.02)), "paint")
        ctx[f"leaf{side}"] = G.part(mb, f"leaf_{'L' if side < 0 else 'R'}", "Garage", "paint", col, parent, sharp=30)
        # лист и каркас створки сложены вплотную: тыл листа и лицо каркаса не видны
        _drop_faces(ctx[f"leaf{side}"], lambda c, n: abs(n[1]) > 0.9 and abs(c[1] - SH_Y1) < 0.002)
        ctx[f"leaf{side}"]["uv_scale"] = GATE_UV
        mb = C.MB()
        for z in (0.40, 1.18, 1.96):
            mb.extend(C.cyl((side * 1.30, HINGE_Y, z + 0.042), 0.0175, 0.080, 8), "steel")
        ctx[f"hinge{side}"] = G.part(mb, f"hinges_{'L' if side < 0 else 'R'}", "Garage", "steel", col, parent, sharp=50)


def _game_brick_interior(col, parent) -> None:
    import game_lib as G
    xi = W / 2 - TW
    yi0, yi1 = Y0 + TW, Y1 - TW
    mb = C.MB()
    _quad(mb, [(-xi, yi0, Z0), (-xi, yi1, Z0), (-xi, yi1, z_wall(yi1)), (-xi, yi0, z_wall(yi0))], "brick")
    _quad(mb, [(xi, yi0, Z0), (xi, yi1, Z0), (xi, yi1, z_wall(yi1)), (xi, yi0, z_wall(yi0))][::-1], "brick")
    _quad(mb, [(-xi, yi1, Z0), (xi, yi1, Z0), (xi, yi1, z_wall(yi1)), (-xi, yi1, z_wall(yi1))], "brick")
    for s in (-1, 1):
        # простенок изнутри и откос проёма
        pts = [(s * xi, yi0, Z0), (s * GX, yi0, Z0), (s * GX, yi0, GZ1), (s * xi, yi0, GZ1)]
        _quad(mb, pts[::-1] if s > 0 else pts, "brick")
        pts = [(s * GX, Y0, Z0), (s * GX, yi0, Z0), (s * GX, yi0, GZ1), (s * GX, Y0, GZ1)]
        _quad(mb, pts[::-1] if s < 0 else pts, "brick")
    ob = G.part(mb, "walls_inner", "GarageInt", "brick", col, parent, sharp=30)
    # стены изнутри — к центру; откосы проёма (x = ±GX) смотрят в проём, их центр по x — снаружи середины: оставить
    _keep_faces(ob, lambda c, n, a: a > 0.02 and abs(n[2]) < 0.3 and (n @ np.array([c[0], c[1], 0.0]) < 0
                                                                     or (abs(abs(c[0]) - GX) < 0.01 and abs(n[0]) > 0.9)))
    mb = C.MB()
    _quad(mb, [(-xi, Y0 - 0.01, Z0), (xi, Y0 - 0.01, Z0), (xi, yi1, Z0), (-xi, yi1, Z0)], "floor")
    ob = G.part(mb, "floor", "GarageInt", "floor", col, parent, sharp=30)
    _keep_faces(ob, lambda c, n, a: n[2] > 0.5)


def _game_brick_props(col, parent) -> None:
    """Нутро открытого: те же места и размеры, что у подробной формы, простыми объёмами."""
    import game_lib as G
    parts: dict = {}

    def mbk(k):
        if k not in parts:
            parts[k] = C.MB()
        return parts[k]
    rng = np.random.default_rng(5)
    x0, x1, y0, y1 = -1.15, 1.15, Y1 - TW - 0.48, Y1 - TW - 0.03
    for x in (x0, x1):
        for y in (y0, y1):
            mbk("steel").extend(C.box((x + (0.02 if x < 0 else -0.02), y + (0.02 if y < y1 - 0.1 else -0.02), Z0 + 1.0),
                                      (0.04, 0.04, 2.0)), "steel")
    for z in (0.25, 0.75, 1.25, 1.75):
        mbk("plywood").extend(C.box2((x0, y0, Z0 + z - 0.03), (x1, y1, Z0 + z + 0.018)), "plywood")
    for z, items in ((0.268, [(-0.8, 0.45, 0.35, 0.30), (-0.25, 0.4, 0.35, 0.22), (0.55, 0.5, 0.36, 0.28)]),
                     (0.768, [(-0.6, 0.35, 0.3, 0.25), (0.2, 0.42, 0.36, 0.32)]),
                     (1.268, [(-0.9, 0.3, 0.3, 0.2), (0.75, 0.45, 0.32, 0.3)]),
                     (1.768, [(0.0, 0.55, 0.38, 0.25)])):
        for (x, w, d, h) in items:
            V, F = C.box((x, (y0 + y1) / 2, Z0 + z + h / 2), (w, d, h), C.rot("z", rng.uniform(-6, 6)))
            mbk("cardboard").add(V, F, "cardboard")
    for (x, z) in ((0.05, 0.268), (0.15, 0.268), (-0.3, 0.768), (-0.18, 0.768), (0.45, 1.268), (-0.45, 1.268)):
        mbk("paint_grey").extend(C.cyl((x, y0 + 0.15, Z0 + z + 0.095), 0.085, 0.19, 8), "paint_grey")
    # верстак
    xa, xb, ya, yb = -W / 2 + TW + 0.02, -W / 2 + TW + 0.62, 0.0, 1.70
    for x in (xa + 0.02, xb - 0.02):
        for y in (ya + 0.02, yb - 0.02):
            mbk("steel").extend(C.box((x, y, Z0 + 0.43), (0.05, 0.05, 0.86)), "steel")
    mbk("plywood").extend(C.box2((xa, ya, Z0 + 0.18), (xb, yb, Z0 + 0.20)), "plywood")
    mbk("wood").extend(C.box2((xa - 0.01, ya - 0.02, Z0 + 0.86), (xb + 0.03, yb + 0.02, Z0 + 0.90)), "wood")
    vx, vy = xb - 0.07, yb - 0.25
    mbk("paint_blue").extend(C.box((vx + 0.03, vy, Z0 + 0.96), (0.18, 0.10, 0.12)), "paint_blue")
    # шины: тор 12 × 6
    for k in range(4):
        c = (0.92, 1.45, Z0 + 0.0975 + k * 0.196)
        mbk("rubber").extend(_tire_low(c), "rubber")
    mbk("rubber").extend(_tire_low((0.80, -0.10, Z0 + 0.0975)), "rubber")
    # канистры
    for (c, yaw) in (((-1.02, -0.45, Z0), 8.0), ((-0.82, -0.62, Z0), -14.0)):
        V, F = C.box((0, 0, 0.235), (0.165, 0.345, 0.47))
        mbk("paint_green").add(C.xf(V, C.rot("z", yaw), c), F, "paint_green")
    # щиток и лампа
    mbk("paint_grey").extend(C.box2((W / 2 - TW - 0.10, Y0 + TW + 0.25, 1.45), (W / 2 - TW, Y0 + TW + 0.45, 1.75)),
                             "paint_grey")
    zc = z_wall(0.4)
    mbk("plastic").extend(C.box((0.0, 0.4, zc - 0.20), (0.006, 0.006, 0.40)), "plastic")
    mbk("plastic").extend(C.lathe([(0.0, -0.11), (0.03, -0.10), (0.03, -0.06), (0.012, -0.03), (0.012, 0.0)], 6,
                                  center=(0.0, 0.4, zc - 0.43)), "plastic")
    # поддон у правой стены (на ребре), метла, ведро
    R = C.rot("y", -82)
    base = np.array([W / 2 - TW - 0.18, -1.40, Z0])
    V, F = C.box((0.6, 0.0, 0.07), (1.2, 0.80, 0.14))
    mbk("wood").add(C.xf(V, R, base), F, "wood")
    mbk("wood").extend(C.cyl_between((-W / 2 + TW + 0.06, Y1 - TW - 0.60, Z0 + 0.25), (-W / 2 + TW + 0.03, Y1 - TW - 0.75,
                                                                                      Z0 + 1.45), 0.012, 4), "wood")
    mbk("galv").extend(C.lathe([(0.13, 0.0), (0.15, 0.30), (0.145, 0.30), (0.125, 0.006)], 8, center=(0.55, 1.95, Z0)),
                       "galv")
    for k, mb in parts.items():
        ob = G.part(mb, "props_" + k, "GarageInt", k, col, parent, sharp=40, weld=1e-5)   # вещи — в наборе нутра
        if k == "rubber":
            _tires_uv(ob)


TIRE_N, TIRE_RINGS = 12, 7


def _tires_uv(ob) -> None:
    """Шины (_tire_low подряд, по TIRE_RINGS колец из TIRE_N точек): прямой полосой — U по окружности (средний радиус),
    V — по профилю; вместо «бубликов» умной проекции. Дальше — только упаковка."""
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    co = np.array([v.co[:] for v in me.vertices])
    per = TIRE_N * TIRE_RINGS
    step = 2 * math.pi * 0.27 / TIRE_N
    v_of = np.zeros(len(co))
    for t in range(len(co) // per):
        g = co[t * per:(t + 1) * per].reshape(TIRE_RINGS, TIRE_N, 3)
        sv = np.r_[0, np.cumsum(np.linalg.norm(np.diff(g[:, 0, :], axis=0), axis=1))]
        v_of[t * per:(t + 1) * per] = np.repeat(sv, TIRE_N) + 5.0 * t
    for p in me.polygons:
        idx = [me.loops[li].vertex_index for li in p.loop_indices]
        cols = [i % per % TIRE_N for i in idx]
        wrap = max(cols) - min(cols) > TIRE_N // 2
        for li, i, c in zip(p.loop_indices, idx, cols):
            uv[li].uv = ((c + (TIRE_N if wrap and c < TIRE_N // 2 else 0)) * step, v_of[i])
    ob["uv"] = "keep"


def _tire_low(c) -> tuple:
    ro, w, rr = 0.317, 0.195, 0.195
    prof = [(rr + 0.02, -w / 2 + 0.02), (ro - 0.04, -w / 2), (ro, -w / 2 + 0.04), (ro, w / 2 - 0.04), (ro - 0.04, w / 2),
            (rr + 0.02, w / 2 - 0.02)]
    n = TIRE_N
    rings = []
    for r, z in prof:
        a = np.arange(n) * 2 * np.pi / n
        rings.append(np.c_[np.cos(a) * r, np.sin(a) * r, np.full(n, z)])
    rings.append(rings[0])
    V, F = C.loft(rings, closed=True)
    return V + np.asarray(c, float), F


def _shell_low_profile() -> tuple:
    """Гладкое сечение ракушки для игры: середина гофра (гребни и впадины — в нормалях), по точке на шаг гофра."""
    P, N, env = shell_profile(0.0)
    mid = env - N * 0.009
    idx = list(range(0, len(mid), 4))
    if idx[-1] != len(mid) - 1:
        idx.append(len(mid) - 1)
    return mid[idx], N[idx]


def _shell_thin(mb: C.MB, y_front, y_back: float, grow: float) -> np.ndarray:
    P, N = _shell_low_profile()
    P = P + N * grow
    Pi = P - N * 0.004
    loop = np.vstack([P, Pi[::-1]])
    rings = []
    for y_of in (y_front, y_back):
        ys = np.array([y_of(z) if callable(y_of) else y_of for z in loop[:, 1]])
        rings.append(np.c_[loop[:, 0], ys, loop[:, 1]])
    V, F = C.loft(rings, closed=True, cap0=True, cap1=True)
    mb.add(V, F, "paint")
    return Pi


def _shell_strip_uv(ob, n_loop: int, piece: float = 2.4, inner_k: float = 0.6) -> None:
    """Выпрямленная развёртка оболочки ракушки (C.loft двух колец по контуру «наружная дуга + изнанка обратно»):
    U — длина по контуру в сечении XZ, V — по Y (у носа кольцо косое — V по месту вершины). Наружная сторона и изнанка —
    отдельными полосами (изнанка видна только у открытой — реже, × inner_k), торцевые кромки — своими, длинные полосы
    режутся на куски не длиннее piece; торцы-сечения — плоской проекцией. Дальше — только упаковка."""
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    co = np.array([v.co[:] for v in me.vertices])
    n_out = n_loop // 2
    xz = co[n_loop:2 * n_loop][:, [0, 2]]
    s_ = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.vstack([xz, xz[:1]]), axis=0), axis=1))]
    perim = s_[-1]
    for p in me.polygons:
        idx = [me.loops[li].vertex_index for li in p.loop_indices]
        if len(idx) > 4:                                     # торцы-сечения (если остались) — плоской проекцией
            for li, i in zip(p.loop_indices, idx):
                uv[li].uv = (co[i][0] + 5000.0, co[i][2])
            continue
        cols = [i % n_loop for i in idx]
        wrap = max(cols) - min(cols) > n_loop // 2
        c0 = max(cols) if wrap else min(cols)
        if c0 < n_out - 1:
            kind, base = 0, 0.0
        elif c0 >= n_out and not wrap:
            kind, base = 1, s_[n_out]
        else:
            kind, base = 2, 0.0                              # нижние кромки толщины листа
        us = [s_[c] + (perim if wrap and c < n_loop // 2 else 0.0) for c in cols]
        mid = sum(us) / len(us) - base
        k = int(mid // piece) if kind < 2 else 0
        sc = inner_k if kind == 1 else 1.0
        for li, i, u in zip(p.loop_indices, idx, us):
            uv[li].uv = ((u - base) * sc, co[i][1] * sc + 1000.0 * (1 + k + 40 * kind))
    ob["uv"] = "keep"


def _game_shell_shared(col, parent, ctx: dict) -> None:
    import game_lib as G
    # задняя часть: оболочка (полосой) и торцевой лист отдельно
    mb = C.MB()
    Pi = _shell_thin(mb, SJ + 0.012, SY1, 0.0)
    ctx["shell_rear"] = ob = G.part(mb, "rear", "Shell", "paint", col, parent, sharp=35)
    _drop_faces(ob, lambda c, n: abs(n[1]) > 0.8)          # срезы листа 4 мм: под торцевым листом и под передней частью
    _shell_strip_uv(ob, len(mb.V[0]) // 2)
    mb = C.MB()
    poly = [(x, z) for x, z in Pi]
    mb.extend(C.prism(poly, SY1 - 0.004, SY1, ex=(1, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0)), "paint")
    ctx["shell_rear_plate"] = G.part(mb, "rear_plate", "Shell", "paint", col, parent, sharp=35)
    # рама из уголка (профили — выпрямленными полосами) и короб замка
    mb = C.MB()
    hw = SW / 2
    for s in (-1, 1):
        mb.extend(C.prism(C.angle_profile(0.05, 0.005), SY0 - 0.05, SY1 + 0.02, origin=(s * (hw + 0.004), 0, 0),
                          ex=(-s, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0)), "steel")
    for y, sy in ((SY0 - 0.05, 1), (SY1 + 0.02, -1), (SJ, 1)):
        mb.extend(C.prism(C.angle_profile(0.05, 0.005), -hw - 0.004, hw + 0.004, origin=(0, y, 0), ex=(0, sy, 0),
                          ey=(0, 0, 1), ez=(1, 0, 0)), "steel")
    ctx["shell_frame"] = ob = G.part(mb, "base_frame", "Shell", "steel", col, parent, sharp=30)
    G.prism_strip_uv(ob, [len(v) for v in mb.V])
    mb = C.MB()
    lb = (-0.16, SY0 - 0.21, 0.0, 0.16, SY0 - 0.05, 0.19)
    mb.extend(C.box2((lb[0] - 0.008, lb[1] - 0.008, 0.0), (lb[3] + 0.008, lb[4] + 0.004, lb[5])), "paint")
    ctx["shell_lock"] = G.part(mb, "lock_box", "Shell", "paint", col, parent, sharp=30)
    # передняя часть: оболочка (полосой) и нос, нижние уголки, планка — отдельно; петли (подвижные карты) — с ней
    mb = C.MB()
    Pi = _shell_thin(mb, nose_y, SJ, 0.012)
    ctx["shell_front"] = ob = G.part(mb, "front", "Shell", "paint", col, parent, sharp=35)
    _drop_faces(ob, lambda c, n: abs(n[1]) > 0.8)          # срезы листа 4 мм у носа и стыка — кромки не видны
    _shell_strip_uv(ob, len(mb.V[0]) // 2, piece=1.2)        # у косого носа полоса не прямоугольна — куски короче
    mb = C.MB()
    n_dir = np.array([0.0, -math.cos(NOSE), math.sin(NOSE)])
    ev = np.array([0.0, math.sin(NOSE), math.cos(NOSE)])
    poly = [(x, z / math.cos(NOSE)) for x, z in Pi]
    mb.extend(C.prism(poly, 0.0, 0.004, origin=(0, SY0, 0), ex=(1, 0, 0), ey=ev, ez=-n_dir), "paint")
    for s in (-1, 1):
        x = s * (SW / 2 + 0.012)
        mb.extend(C.box2((x - 0.03 * (s > 0), nose_y(0.06), 0.06), (x + 0.03 * (s < 0), SJ - 0.01, 0.10)), "paint")
    a = np.array([0.0, nose_y(0.10) - 0.004, 0.10])
    b = np.array([0.0, SY0 - 0.125, 0.215])
    d = (b - a) / np.linalg.norm(b - a)
    mb.extend(C.prism(C.rect_profile(0.05, 0.008), 0.0, float(np.linalg.norm(b - a)), origin=a, ex=(1, 0, 0),
                      ey=np.cross(d, (1, 0, 0)), ez=d), "paint")
    ctx["shell_front_parts"] = G.part(mb, "front_parts", "Shell", "paint", col, parent, sharp=35)
    mb = C.MB()
    for x in (-0.45, 0.0, 0.45):
        mb.extend(C.cyl((x, SJ, HINGE_Z), 0.014, 0.09, 8, "x"), "steel")
    ctx["shell_hinges_fixed"] = G.part(mb, "hinges_fixed", "Shell", "steel", col, parent, sharp=50)
    mb = C.MB()
    for x in (-0.45, 0.0, 0.45):
        mb.extend(C.box2((x - 0.05, SJ - 0.17, SH + 0.0), (x + 0.05, SJ - 0.01, SH + 0.009)), "steel")
        for dx in (0.085, -0.085):
            mb.extend(C.cyl((x + dx, SJ, HINGE_Z), 0.014, 0.07, 8, "x"), "steel")
    ctx["shell_hinges_moving"] = G.part(mb, "hinges_moving", "Shell", "steel", col, parent, sharp=50)


def _half_margin(col) -> None:
    """Наборы снаружи гаража и «ракушки» — куски одних деталей (полосы цоколя, плит, рубероида, обвязки, листы створок,
    стены, полосы кожуха): между ними половинный отступ (норма навыка), иначе поля съедают атлас."""
    for o in col.objects:
        if o.type == "MESH" and o.get("tex_set") in ("Garage", "GarageBrick", "Shell"):
            o["uv_half"] = True


def game(col, parent, key: str, ctx: dict) -> None:
    """Игровые детали варианта (game.py): закрытые варианты задают общие сетки, открытые берут их повёрнутыми."""
    import game_lib as G
    if key == "brick_closed":
        _game_brick_shared(col, parent, ctx)
        mb = C.MB()
        mb.extend(C.box2((-0.40, SH_Y0 - 0.024, 1.08), (0.09, SH_Y0 - 0.012, 1.12)), "steel")       # ригель задвинут
        V, F = C.box((0.075, SH_Y0 - 0.05, 0.93), (0.07, 0.03, 0.06))
        mb.add(V, F, "steel")                                                                         # навесной замок
        mb.extend(C.box2((0.04, SH_Y0 - 0.032, 1.00), (0.11, SH_Y0 - 0.010, 1.075)), "steel")
        G.part(mb, "padlock", "Garage", "steel", col, parent, sharp=40)
        _half_margin(col)
        return
    if key == "brick_open":
        for k in ("walls", "plinth", "concrete", "lintel", "roof", "frame", "hinges_fixed"):
            G.instance(ctx[k], col, parent)
        for side in (-1, 1):
            M = _pivot_matrix((side * 1.30, HINGE_Y, 0.0), C.rot("z", 100.0 if side > 0 else -100.0))
            G.instance(ctx[f"leaf{side}"], col, parent, M)
            G.instance(ctx[f"hinge{side}"], col, parent, M)
        _game_brick_interior(col, parent)
        _game_brick_props(col, parent)
        return
    if key == "shell_closed":
        _game_shell_shared(col, parent, ctx)
        _half_margin(col)
        return
    if key == "shell_open":
        for k in ("shell_rear", "shell_rear_plate", "shell_frame", "shell_lock", "shell_hinges_fixed"):
            G.instance(ctx[k], col, parent)
        M = _pivot_matrix((0.0, SJ, HINGE_Z), C.rot("x", -70.0))
        G.instance(ctx["shell_front"], col, parent, M)
        G.instance(ctx["shell_front_parts"], col, parent, M)
        G.instance(ctx["shell_hinges_moving"], col, parent, M)
        mb = C.MB()
        ang = math.radians(-70.0)
        for s in (-1, 1):
            x = s * (SW / 2 + 0.03)
            yl, zl = -0.6, -1.6
            yw = SJ + yl * math.cos(ang) - zl * math.sin(ang)
            zw = HINGE_Z + yl * math.sin(ang) + zl * math.cos(ang)
            yf = SJ - 1.5
            mb.extend(C.cyl_between((x, yf, 0.05), (x, yw, zw), 0.016, 6), "steel")
            mb.extend(C.cyl_between((x, yf + (yw - yf) * 0.45, 0.05 + (zw - 0.05) * 0.45), (x, yw, zw), 0.020, 6), "steel")
            mb.extend(C.box2((x - 0.02, yf - 0.05, 0.0), (x + 0.02, yf + 0.05, 0.05)), "steel")
        G.part(mb, "props", "Shell", "steel", col, parent, sharp=40)
