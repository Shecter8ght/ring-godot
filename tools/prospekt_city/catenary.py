"""Контактная сеть железной дороги «Проспекта»: жёсткая поперечина над шестью путями (вокзальная горловина).

Как на станциях РЖД (схема «Жёсткая поперечина», scbist.com, рис. 2.15): две стальные решётчатые мачты на
бетонных фундаментах, по верху — ригель (пространственная ферма из уголка), под ним над каждым путём —
гирлянды подвесных изоляторов V-образно к седлу несущего троса, ниже поперёк всех путей — фиксирующий трос на
изоляторах у мачт, со «струнами» к ригелю и фиксаторами к контактному проводу. Над южной мачтой — кронштейн с
двумя фидерами на штыревых изоляторах. Надписи и номера — вымышленные (отделкой).

Привязка к карте (tools/build_prospekt.py): шесть путей с междупутьем 4,1 м, мачты в 2,6 м от крайних путей —
пролёт 25,7 м; ригель по оси на 8,6 м над головкой рельса, несущий трос 7,3, контактный провод 6,0 (сами
продольные провода рисует карта). Фидеры на карте сейчас на 8,9 м — вплотную к ригелю; в модели их седла на
9,35 м (при установке поднять линии карты). Начало координат — середина между мачтами на уровне головки рельса;
поперечина вдоль Blender Y (игровая Z), пути вдоль X; оси путей y = ±2,05, ±6,15, ±10,25; северная мачта +Y.
"""
from __future__ import annotations

import math

import numpy as np

import clib as C
import poles as P

TRACKS = [-10.25, -6.15, -2.05, 2.05, 6.15, 10.25]
MAST_Y = 12.85
RIG_Z = 8.60                     # ось ригеля
RIG_H, RIG_W = 0.50, 0.60        # высота и ширина фермы (по Z и по X)
MESS_Z = 7.30                    # несущий трос
CONT_Z = 6.00                    # контактный провод
FT_Z = 6.55                      # фиксирующий трос
FEED_Z = 9.35                    # седла фидеров
MAST_TOP = RIG_Z - RIG_H / 2     # ригель лежит на оголовках мачт
MAST_B0, MAST_B1 = 0.56, 0.32    # сечение мачты у пяты и вверху (по осям поясов)


def member(mb: C.MB, a, b, w: float = 0.05, t: float = 0.005, up=(0, 0, 1), m: str = "galv") -> None:
    """Уголок w×w×t по линии a → b (центр уголка — на линии); up — куда смотрит одна полка."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    ln = float(np.linalg.norm(d))
    if ln < 1e-4:
        return
    Fr = C.frame_from(d, up)
    prof = C.angle_profile(w, t) - w * 0.3
    V, F = C.prism(prof, 0.0, ln, origin=a, ex=Fr[0], ey=Fr[1], ez=Fr[2])
    mb.add(V, F, m)


def gusset(mb: C.MB, c, n, size: float = 0.12, t: float = 0.006, m: str = "galv") -> None:
    """Фасонка — пластина узла фермы, нормаль n."""
    n = np.asarray(n, float)
    Fr = C.frame_from(n)
    pts = C.rect_profile(size, size * 0.8, 0.015, 2)
    V, F = C.prism(pts, -t / 2, t / 2, origin=c, ex=Fr[0], ey=Fr[1], ez=Fr[2])
    mb.add(V, F, m)


def mast_half(z: float) -> float:
    return (MAST_B0 + (MAST_B1 - MAST_B0) * z / MAST_TOP) / 2


# ---------------------------------------------------------------- мачта
def mast(mb: C.MB, conc: C.MB, y0: float, side: int) -> None:
    """Решётчатая мачта: четыре пояса из уголка 75×6, сходятся 560 → 320 мм; раскосы 50×5 зигзагом по граням,
    распорки через 4 панели; опорная плита на анкерах, бетонный фундамент; оголовок под ригель."""
    H = MAST_TOP
    def half(z: float) -> float:
        return (MAST_B0 + (MAST_B1 - MAST_B0) * z / H) / 2
    corners = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    for sx, sy in corners:
        a = np.array([sx * half(0.0), y0 + sy * half(0.0), 0.15])
        b = np.array([sx * half(H), y0 + sy * half(H), H])
        member(mb, a, b, 0.075, 0.006, up=(sx, sy, 0))
    # раскосы по четырём граням
    n_pan = 16
    zs = np.linspace(0.35, H - 0.1, n_pan + 1)
    for f in range(4):
        (ax, ay), (bx, by) = corners[f], corners[(f + 1) % 4]
        nrm = np.array([ax + bx, ay + by, 0.0]) / 2
        for k in range(n_pan):
            z0, z1 = zs[k], zs[k + 1]
            pa = np.array([ax * half(z0), y0 + ay * half(z0), z0]) if k % 2 == 0 else np.array([bx * half(z0), y0 + by * half(z0), z0])
            pb = np.array([bx * half(z1), y0 + by * half(z1), z1]) if k % 2 == 0 else np.array([ax * half(z1), y0 + ay * half(z1), z1])
            member(mb, pa, pb, 0.05, 0.005, up=nrm)
        for k in range(0, n_pan + 1, 4):
            z = zs[k]
            member(mb, (ax * half(z), y0 + ay * half(z), z), (bx * half(z), y0 + by * half(z), z), 0.05, 0.005, up=(0, 0, 1))
    # опорная плита, косынки, анкеры
    base = C.rect_profile(0.78, 0.78, 0.03, 3)
    V, F = C.prism(base, 0.12, 0.15, origin=(0, y0, 0))
    mb.add(V, F, "galv")
    for sx, sy in corners:
        p = np.array([sx * 0.33, y0 + sy * 0.33, 0.15])
        mb.extend(C.cyl_between(p - (0, 0, 0.05), p + (0, 0, 0.09), 0.015, 10), "galv")
        n6, F6 = C.lathe([(0.026, 0.0), (0.026, 0.026)], 6)
        mb.add(C.xf(n6, None, p), F6, "galv")
        for d in ((sx, 0), (0, sy)):
            dd = np.array([d[0], d[1], 0.0])
            nn = np.array([-dd[1], dd[0], 0.0])
            tri = [(0.0, 0.0), (0.12, 0.0), (0.0, 0.22)]
            c = np.array([sx * half(0.15), y0 + sy * half(0.15), 0.15])
            V, F = C.prism(tri, -0.004, 0.004, origin=c, ex=dd, ey=(0, 0, 1), ez=nn)
            mb.add(V, F, "galv")
    V, F = C.lathe([(0.50, -1.2), (0.50, 0.0)], 4, center=(0, y0, 0))
    V2, F2 = C.box((0, y0, -0.45), (1.0, 1.0, 1.0))
    conc.add(V2, F2, "concrete_old")
    V3, F3 = C.box((0, y0, 0.06), (0.95, 0.95, 0.12))
    conc.add(V3, F3, "concrete_old")
    _ = V, F
    # оголовок: горизонтальная рама из швеллера по верху поясов и столик под ригель
    h = half(H)
    for s in (-1, 1):
        V, F = C.prism(C.channel_profile(0.12, 0.05, 0.006), -h - 0.06, h + 0.06, origin=(s * (h + 0.0), y0, H - 0.06),
                       ex=(s, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0))
        mb.add(V, F, "galv")
    mb.extend(C.box((0, y0, H + 0.006), (RIG_W + 0.12, 0.42, 0.012)), "galv")
    # заземляющий спуск по поясу к пяте, номерная табличка с поля
    sx, sy = 1, side
    P_ = np.array([(sx * half(z) + 0.05, y0 + sy * half(z) + 0.02 * sy, z) for z in np.linspace(H - 0.3, 0.3, 8)])
    P_ = np.vstack([P_, [P_[-1] + (0.08, 0, -0.25), P_[-1] + (0.2, 0, -0.45)]])
    mb.extend(C.tube(P_, 0.005, 6), "steel")
    pl = C.rect_profile(0.24, 0.30, 0.012, 2)
    V, F = C.prism(pl, 0.0, 0.002, origin=(0, y0 + side * (half(2.6) + 0.04), 2.6), ex=(1, 0, 0), ey=(0, 0, 1), ez=(0, side, 0))
    mb.add(V, F, "paint_white")
    for dx in (-0.08, 0.08):
        mb.extend(C.box((dx, y0 + side * (half(2.6) + 0.02), 2.6), (0.03, 0.04, 0.03)), "galv")


# ---------------------------------------------------------------- ригель
def girder(mb: C.MB) -> None:
    """Ригель: коробчатая ферма 600 × 500 из уголка 75×6 (пояса), стойки и раскосы 50×5 на вертикальных гранях,
    зигзаг связей 50×5 по верху и низу, накладки стыков на третях пролёта, опорные столики на мачтах."""
    y0, y1 = -MAST_Y - 0.35, MAST_Y + 0.35
    hw, hh = RIG_W / 2, RIG_H / 2
    zc = RIG_Z
    chords = [(hw, zc + hh), (-hw, zc + hh), (-hw, zc - hh), (hw, zc - hh)]
    for x, z in chords:
        member(mb, (x, y0, z), (x, y1, z), 0.075, 0.006, up=(np.sign(x), 0, np.sign(z - zc)))
    n = 44
    ys = np.linspace(y0 + 0.05, y1 - 0.05, n + 1)
    for k in range(n + 1):
        y = ys[k]
        for x in (hw, -hw):                                            # стойки вертикальных граней
            member(mb, (x, y, zc - hh + 0.04), (x, y, zc + hh - 0.04), 0.05, 0.005, up=(np.sign(x), 0, 0))
        if k % 2 == 0:                                                 # поперечные распорки верха и низа
            for z in (zc + hh - 0.02, zc - hh + 0.02):
                member(mb, (-hw + 0.04, y, z), (hw - 0.04, y, z), 0.05, 0.005, up=(0, 0, np.sign(z - zc)))
    for k in range(n):
        ya, yb = ys[k], ys[k + 1]
        up_first = k % 2 == 0
        for x in (hw, -hw):                                            # раскосы вертикальных граней
            za, zb = (zc - hh + 0.04, zc + hh - 0.04) if up_first else (zc + hh - 0.04, zc - hh + 0.04)
            member(mb, (x, ya, za), (x, yb, zb), 0.05, 0.005, up=(np.sign(x), 0, 0))
        if k % 2 == 0 and k + 2 <= n:                                  # связи по верху и низу через две панели
            yc = ys[k + 2]
            for z in (zc + hh - 0.02, zc - hh + 0.02):
                member(mb, (-hw + 0.04, ya, z), (hw - 0.04, yc, z), 0.05, 0.005, up=(0, 0, np.sign(z - zc)))
    # стыки: накладки на поясах и болты
    for yj in (-MAST_Y / 3 * 1.4, MAST_Y / 3 * 1.4):
        for x, z in chords:
            mb.extend(C.box((x + np.sign(x) * 0.03, yj, z), (0.012, 0.36, 0.09)), "galv")
            for dy in (-0.12, -0.04, 0.04, 0.12):
                mb.extend(C.cyl((x + np.sign(x) * 0.045, yj + dy, z), 0.011, 0.02, 6, "x"), "galv")
    # фасонки узлов на вертикальных гранях у подвесов
    for y in TRACKS:
        for x in (hw, -hw):
            for dy in (-0.45, 0.45):
                gusset(mb, (x + np.sign(x) * 0.012, y + dy, zc - hh + 0.09), (1, 0, 0), 0.16, 0.008)


# ---------------------------------------------------------------- изоляторы и арматура
def disc_insulator(mb: C.MB, glass: C.MB, top, d) -> np.ndarray:
    """Тарельчатый изолятор ПС-70 (Ø 255, шаг 127): чугунная шапка, стеклянная тарелка с рёбрами снизу, стержень.
    top — точка шапки, d — направление вниз по гирлянде; возвращает нижнюю точку (стержень)."""
    d = np.asarray(d, float)
    d /= np.linalg.norm(d)
    R = C.frame_from(-d).T                                             # z модели — вверх по гирлянде
    cap = [(0.020, 0.0), (0.036, -0.010), (0.038, -0.045), (0.030, -0.058)]                 # торцы — крышками
    V, F = C.lathe(cap, 16)
    mb.add(C.xf(V, R, top), F, "steel", smooth=True)
    shed = [(0.034, -0.040), (0.070, -0.050), (0.110, -0.066), (0.1275, -0.078), (0.126, -0.086), (0.104, -0.083),
            (0.100, -0.094), (0.092, -0.094), (0.086, -0.082), (0.070, -0.080), (0.066, -0.092), (0.058, -0.092),
            (0.052, -0.078), (0.034, -0.072)]
    V, F = C.lathe(shed, 32)
    glass.add(C.xf(V, R, top), F, "glass", smooth=True)
    pin_ = [(0.009, -0.058), (0.009, -0.118), (0.014, -0.122), (0.014, -0.127)]
    V, F = C.lathe(pin_, 10)
    mb.add(C.xf(V, R, top), F, "galv")
    return np.asarray(top, float) + d * 0.127


def string(mb: C.MB, glass: C.MB, top, bottom, discs: int = 3) -> None:
    """Гирлянда: серьга у ригеля, discs тарелок, ушко внизу; остаток длины — тяга-серьга."""
    top, bottom = np.asarray(top, float), np.asarray(bottom, float)
    d = bottom - top
    ln = float(np.linalg.norm(d))
    u = d / ln
    p = top
    mb.extend(C.cyl_between(p, p + u * 0.08, 0.008, 8), "galv")
    p = p + u * 0.08
    for _ in range(discs):
        p = disc_insulator(mb, glass, p, u)
    mb.extend(C.cyl_between(p, bottom, 0.007, 8), "galv")


def messenger_saddle(mb: C.MB, glass: C.MB, y: float) -> None:
    """Подвес несущего троса над путём: две гирлянды V (в плоскости поперечины) от траверсок под нижним поясом
    ригеля к седлу на 7,3 м; седло с плашками вдоль пути."""
    seat = np.array([0.0, y, MESS_Z + 0.03])
    zb = RIG_Z - RIG_H / 2
    for s in (-1, 1):
        yt = y + s * 0.45
        member(mb, (-RIG_W / 2 - 0.04, yt, zb - 0.04), (RIG_W / 2 + 0.04, yt, zb - 0.04), 0.063, 0.006, up=(0, 0, -1))
        mb.extend(C.box((0.0, yt, zb - 0.075), (0.012, 0.08, 0.06)), "galv")             # проушина
        string(mb, glass, np.array([0.0, yt, zb - 0.10]), seat + (0, s * 0.04, 0.05), 4)
    # седло: коромысло вдоль пути (X) и лоток под трос
    V, F = C.prism(C.rect_profile(0.32, 0.05, 0.012, 2), -0.012, 0.012, origin=seat + (0, 0, 0.02), ex=(1, 0, 0),
                   ey=(0, 0, 1), ez=(0, 1, 0))
    mb.add(V, F, "galv")
    for dx in (-0.1, 0.1):
        mb.extend(C.box(seat + (dx, 0, -0.012), (0.05, 0.035, 0.02)), "galv")
        mb.extend(C.cyl(seat + (dx, 0, -0.03), 0.006, 0.05, 8, "y"), "galv")


def registration(mb: C.MB, glass: C.MB, dark: C.MB) -> None:
    """Фиксирующий трос поперёк путей: от мачты к мачте на 6,55 м, у мачт — гирлянды-изоляторы и талрепы;
    над каждым путём — струна к ригелю, сочленённый фиксатор (труба Ø 26) к контактному проводу 6,0 с зажимом."""
    ends = []
    for s in (-1, 1):
        anchor = np.array([0.0, s * (MAST_Y - mast_half(FT_Z) - 0.02), FT_Z + 0.02])
        mb.extend(C.box(anchor + (0, s * 0.02, 0), (0.2, 0.04, 0.12)), "galv")         # хомут на мачте
        a = anchor - np.array([0, s * 0.06, 0])
        b = a - np.array([0, s * 0.40, 0.0])
        P.rod_insulator(dark, a, b, sheds=6)
        c = b - np.array([0, s * 0.28, 0.0])
        P.turnbuckle(mb, b, c)
        ends.append(c)
    # трос с малым провисом и струны к ригелю
    y_a, y_b = ends[0][1], ends[1][1]
    ys = np.linspace(y_a, y_b, 80)
    span = y_b - y_a
    zs = FT_Z - 0.06 * (1 - ((ys - (y_a + y_b) / 2) / (span / 2)) ** 2)
    rope = np.c_[np.zeros_like(ys), ys, zs]
    dark.extend(C.tube(rope, 0.0055, 8), "steel")
    for y in TRACKS:
        z_ft = FT_Z - 0.06 * (1 - (y / (span / 2)) ** 2)
        for dy in (-0.9, 0.9):                                          # струны по бокам от пути
            zb = FT_Z - 0.06 * (1 - ((y + dy) / (span / 2)) ** 2)
            dark.extend(C.tube(np.array([(0.0, y + dy, RIG_Z - RIG_H / 2 + 0.02), (0.0, y + dy, zb + 0.01)]), 0.002, 5),
                        "steel")
            mb.extend(C.box((0.0, y + dy, zb + 0.015), (0.03, 0.03, 0.04)), "galv")
        # фиксатор: основной стержень от зажима на тросе вниз-в сторону, дополнительный — к проводу
        f0 = np.array([0.0, y - 0.55, z_ft - 0.02])
        mb.extend(C.box(f0 + (0, 0, 0.02), (0.05, 0.06, 0.06)), "galv")
        P.rod_insulator(dark, f0, f0 + (0.0, 0.18, -0.10), sheds=3)
        f1 = f0 + (0.0, 0.18, -0.10)
        f2 = np.array([0.0, y + 0.05, CONT_Z + 0.16])
        mb.extend(C.tube(np.array([f1, f1 + (f2 - f1) * 0.5 + (0, 0, 0.02), f2]), 0.013, 10), "galv")
        f3 = np.array([0.0, y + 0.45, CONT_Z + 0.03])
        mb.extend(C.tube(np.array([f2, f2 + (0, 0.2, -0.07), f3]), 0.009, 8), "galv")
        # зажим контактного провода
        mb.extend(C.box((0.0, y, CONT_Z + 0.02), (0.07, 0.03, 0.035)), "galv")
        mb.extend(C.tube(np.array([f3, (0.0, y + 0.02, CONT_Z + 0.04)]), 0.006, 6), "galv")


def feeder_bracket(mb: C.MB, glass: C.MB, y0: float, side: int) -> None:
    """Кронштейн фидеров над южной мачтой: стойка из уголка над оголовком, траверса поперёк, два штыревых изолятора
    ШФ (крупнее ТФ) — седла проводов на 9,35 м, по обе стороны от оси мачты на 0,3 м."""
    base = np.array([0.0, y0, MAST_TOP + 0.012])
    top_z = FEED_Z - 0.20
    for dx in (-0.08, 0.08):
        member(mb, base + (dx, 0, 0), (dx, y0, top_z), 0.063, 0.006, up=(np.sign(dx), 0, 0))
    member(mb, (-0.10, y0, top_z - 0.25), (0.10, y0, top_z - 0.25), 0.05, 0.005)
    V, F = C.prism(C.angle_profile(0.075, 0.006)[::-1] * (1, -1), y0 - 0.45, y0 + 0.45, origin=(-0.04, 0, top_z),
                   ex=(1, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0))
    mb.add(V, F, "galv")
    for dy in (-0.3, 0.3):
        p = np.array([0.0, y0 + dy, top_z])
        mb.extend(C.cyl_between(p - (0, 0, 0.02), p + (0, 0, 0.09), 0.011, 10), "galv")
        prof = [(0.016, 0.0), (0.055, 0.0), (0.058, 0.008), (0.052, 0.022), (0.036, 0.035), (0.034, 0.06),
                (0.050, 0.07), (0.052, 0.078), (0.040, 0.092), (0.030, 0.100), (0.034, 0.108), (0.036, 0.118),
                (0.030, 0.128), (0.012, 0.132), (0.0, 0.132)]
        V, F = C.lathe(prof, 24, center=p + (0, 0, 0.07))
        glass.add(V, F, "porcelain_white", smooth=True)
    _ = side


def crossspan(col, parent) -> None:
    st = C.MB()
    conc = C.MB()
    for side in (-1, 1):
        mast(st, conc, side * MAST_Y, side)
    st.build("Masts_Lattice", col, parent, bevel=0.001, seg=1)
    conc.build("Mast_Foundations", col, parent, bevel=0.02, seg=2)
    gd = C.MB()
    girder(gd)
    gd.build("Girder_Truss", col, parent, bevel=0.001, seg=1)
    hw = C.MB()
    gl = C.MB()
    dk = C.MB()
    for y in TRACKS:
        messenger_saddle(hw, gl, y)
    registration(hw, gl, dk)
    feeder_bracket(hw, gl, -MAST_Y, -1)
    hw.build("Suspension_Hardware", col, parent, bevel=0.0008, seg=1)
    gl.build("Insulators_Glass", col, parent, sharp=60)
    dk.build("Registration_Cable", col, parent, sharp=50)


VARIANTS = {"crossspan6": "Жёсткая поперечина · 6 путей"}
STEP = 30.0
META = {
    "folder": "Контактная_сеть", "name": "Catenary_Crossspan", "title": "Жёсткая поперечина контактной сети над 6 путями",
    "step": 30.0,
    "shots": [["общий вид", [12.0, -17.0, 7.0], [0.0, 0.0, 5.0], 22], ["мачта и ригель", [3.4, -16.6, 8.0], [0.0, -12.4, 7.6], 28],
              ["подвес над путём", [3.6, -5.2, 6.2], [0.0, -2.05, 7.0], 28]],
}


def build(keys: list[str]) -> dict:
    out = {}
    for i, k in enumerate(keys):
        name = VARIANTS[k]
        col = C.collection(name)
        r = C.root(f"Catenary | {name}", col, (i * STEP, 0.0, 0.0))
        crossspan(col, r)
        out[k] = name
    return out


# ================================================================ игровая версия (LOD0)
# Поперечин на карте шесть — LOD0 ≤ 15 тыс. треугольников. Одинаковые элементы (раскосы, стойки, распорки, связи
# фермы и мачт, фасонки, гайки, гирлянды, седла, фиксаторы) — одна сетка с одной развёрткой на все места («шаблон»:
# первый экземпляр стоит на месте подробного и запекается с него, остальные — та же сетка, повёрнутая и чуть растянутая
# по длине): плотность текстуры как у отдельного предмета. Пояса — тоже шаблоны (куски по 2,1–2,2 м). Уголки —
# выпрямленными полосами, коробки и пластины — сеткой (fold_uv), один набор Painter Cat (2K): решётка, фундаменты,
# плиты, оголовки, подвесы, изоляторы, табличка; тросы и спуски — плиточный пруток Rebar. Коллизия — только мачты
# (ригель высоко над путями).
GAME = {
    "ids": {"crossspan6": "PC05_CROSSSPAN"},
    "bake": ["crossspan6"],
    "skip_high": [],
    "res": {"Cat": 11},                                # решётка и мелочь — один атлас (порознь 22 % и 43 %)
    "ray": 0.002,                                      # сцена ≈ 28 м: 0,006 — 17 см, луч ловит соседние уголки
    "solids": {"crossspan6": [[[0.0, -12.85, 4.2], [0.7, 0.7, 8.4]], [[0.0, 12.85, 4.2], [0.7, 0.7, 8.4]]]},
}


def _m4(cols, t) -> np.ndarray:
    """4×4 из столбцов (ex, ey, ez) и сдвига."""
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2] = cols
    M[:3, 3] = t
    return M


def fold_uv(ob, angle: float = 66.0, down: bool = False) -> None:
    """Коробки и пластины детали — сеткой в один остров: большая грань, вокруг неё откинуты боковые (кайма у тонкой
    пластины, «крест» у кубика), противоположная грань — свой остров. Мелочь иначе дробится на шесть островов
    с отступом у каждого. Прочие куски (трубки, тела вращения) — умная проекция с порогом angle. down — большой
    гранью брать нижнюю (деталь высоко, видна снизу)."""
    import bmesh
    import bpy
    import game_lib as G
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    seen, comps = set(), []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, comp = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        comps.append(comp)
    fold, rest = {}, []
    for k, comp in enumerate(comps):
        amax = max(f.calc_area() for f in comp)
        cands = [f for f in comp if f.calc_area() > 0.98 * amax]
        f0 = min(cands, key=lambda f: f.normal.z) if down else max(cands, key=lambda f: f.normal.z)
        e0 = set(f0.edges)
        sides, opp, ok = [], [], True
        for g in comp:
            if g is f0:
                continue
            sh = e0 & set(g.edges)
            if len(sh) == 1:
                sides.append((g, sh.pop()))
            elif not sh and g.normal.dot(f0.normal) < -0.9:
                opp.append(g)
            else:
                ok = False
                break
        if not ok or len(opp) > 1:
            rest.extend(f.index for f in comp)
            continue
        c = f0.calc_center_median()
        n = f0.normal
        e1 = (f0.verts[1].co - f0.verts[0].co).normalized()
        e2 = n.cross(e1)

        def flat(v, c=c, e1=e1, e2=e2):
            d = v - c
            return np.array([d.dot(e1), d.dot(e2)])
        base = {v.index: flat(v.co) for v in f0.verts}
        fold[f0.index] = [base[lp.vert.index] + (1000.0 * k, 0.0) for lp in f0.loops]
        for g, e in sides:
            a_, b_ = e.verts
            ua, ub = base[a_.index], base[b_.index]
            u = (b_.co - a_.co).normalized()
            du = (ub - ua) / np.linalg.norm(ub - ua)
            out = np.array([-du[1], du[0]])
            if out.dot((ua + ub) / 2) < 0:
                out = -out
            uvs = []
            for lp in g.loops:
                v = lp.vert
                if v.index in (a_.index, b_.index):
                    q = base[v.index]
                else:
                    d = v.co - a_.co
                    t = d.dot(u)
                    q = ua + du * t + out * (d - u * t).length
                uvs.append(q + (1000.0 * k, 0.0))
            fold[g.index] = uvs
        for g in opp:
            cg, ng = g.calc_center_median(), g.normal
            f1 = (g.verts[1].co - g.verts[0].co).normalized()
            f2 = ng.cross(f1)
            fold[g.index] = [np.array([(lp.vert.co - cg).dot(f1), (lp.vert.co - cg).dot(f2)]) + (1000.0 * k, 500.0)
                             for lp in g.loops]
    bm.free()
    if rest:
        G._select([ob])
        bpy.ops.object.mode_set(mode="EDIT")
        bme = bmesh.from_edit_mesh(me)
        keep = set(rest)
        for f in bme.faces:
            f.select_set(f.index in keep)
        bmesh.update_edit_mesh(me)
        bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=0.0, area_weight=0.0,
                                 correct_aspect=True, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode="OBJECT")
    uv = me.uv_layers.active.data
    for fi, uvs in fold.items():
        for li, q in zip(me.polygons[fi].loop_indices, uvs):
            uv[li].uv = (float(q[0]), float(q[1]))
    ob["uv"] = "keep"


class Tpl:
    """Шаблоны игровых деталей: первая деталь класса строится и ставится на место, следующие — та же сетка."""

    def __init__(self, col, parent) -> None:
        import game_lib as G
        self.G, self.col, self.parent, self.lib = G, col, parent, {}

    def place(self, cls: str, build, M, ts: str, mat: str, sharp: float = 30.0, L: float = 1.0, post=None) -> None:
        """build(mb) — сетка в своих осях; M — куда поставить (4×4); L — длина (растяжение по своей оси Z);
        post(ob, mb) — развёртка шаблона (выпрямленные полосы и т. п.), копии берут её же."""
        from mathutils import Matrix
        if cls not in self.lib:
            mb = C.MB()
            build(mb)
            ob = self.G.part(mb, cls, ts, mat, self.col, self.parent, sharp=sharp)
            if post is not None:
                post(ob, mb)
            ob.matrix_basis = Matrix(np.asarray(M).tolist())
            self.lib[cls] = (ob, L)
            return
        src, L0 = self.lib[cls]
        M = np.array(M, float)
        M[:3, 2] *= L / L0
        self.G.instance(src, self.col, self.parent, M)

    def member(self, cls: str, a, b, w: float, t: float, up=(0, 0, 1), caps: bool = False, ts: str = "Cat") -> None:
        """Уголок как в member() подробной формы: тот же кадр, та же длина — шаблон класса или своя сетка."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        d = b - a
        ln = float(np.linalg.norm(d))
        if ln < 1e-4:
            return
        Fr = C.frame_from(d, up)
        prof = C.angle_profile(w, t) - w * 0.3

        def build(mb: C.MB, ln=ln) -> None:
            V, F = C.prism(prof, 0.0, ln, caps=caps)      # одна призма: полоса шаблона умещается в атлас целиком,
            mb.add(V, F, "galv")                           # а куски множили бы треугольники у всех копий

        def post(ob, mb) -> None:
            self.G.prism_strip_uv(ob, [len(v) for v in mb.V])
        self.place(cls, build, _m4((Fr[0], Fr[1], Fr[2]), a), ts, "galv", 30.0, ln, post)


def _mast_low(T: Tpl, y0: float, side: int) -> None:
    H = MAST_TOP

    def half(z: float) -> float:
        return (MAST_B0 + (MAST_B1 - MAST_B0) * z / H) / 2
    corners = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    for k, (sx, sy) in enumerate(corners):                         # пояса — четырьмя одинаковыми кусками (шаблон)
        a = np.array([sx * half(0.0), y0 + sy * half(0.0), 0.15])
        b = np.array([sx * half(H), y0 + sy * half(H), H])
        for u0, u1 in ((0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.0)):
            T.member("mchord", a + (b - a) * u0, a + (b - a) * u1, 0.075, 0.006, up=(sx, sy, 0))
    n_pan = 16
    zs = np.linspace(0.35, H - 0.1, n_pan + 1)
    for f in range(4):
        (ax, ay), (bx, by) = corners[f], corners[(f + 1) % 4]
        nrm = np.array([ax + bx, ay + by, 0.0]) / 2
        for k in range(n_pan):
            z0, z1 = zs[k], zs[k + 1]
            pa = np.array([ax * half(z0), y0 + ay * half(z0), z0]) if k % 2 == 0 else np.array([bx * half(z0), y0 + by * half(z0), z0])
            pb = np.array([bx * half(z1), y0 + by * half(z1), z1]) if k % 2 == 0 else np.array([ax * half(z1), y0 + ay * half(z1), z1])
            T.member("mdiag", pa, pb, 0.05, 0.005, up=nrm)
        for k in range(0, n_pan + 1, 4):
            z = zs[k]
            T.member("mstrut", (ax * half(z), y0 + ay * half(z), z), (bx * half(z), y0 + by * half(z), z), 0.05, 0.005,
                     up=(0, 0, 1))
    I3 = np.eye(3)

    def plate(mb: C.MB) -> None:                        # низ плиты и гаек лежит на бетоне и плите — без граней
        V, F = C.prism(C.rect_profile(0.78, 0.78), 0.12, 0.15)
        mb.add(V, F[:-2] + F[-1:], "galv")
        for sx_, sy_ in corners:
            V, F = C.lathe([(0.026, 0.15), (0.026, 0.176)], 6, center=(sx_ * 0.33, sy_ * 0.33, 0.0), cap_bottom=False)
            mb.add(V, F, "galv")
    T.place("mplate", plate, _m4((I3[0], I3[1], I3[2]), (0, y0, 0)), "Cat", "galv")
    for sx, sy in corners:
        for dd in ((sx, 0), (0, sy)):
            dd3 = np.array([dd[0], dd[1], 0.0])
            nn = np.array([-dd3[1], dd3[0], 0.0])
            c = np.array([sx * half(0.15), y0 + sy * half(0.15), 0.15])

            def gus(mb: C.MB) -> None:
                V, F = C.prism([(0.0, 0.0), (0.12, 0.0), (0.0, 0.22)], -0.004, 0.004)
                mb.add(V, F, "galv")
            T.place("mgusset", gus, _m4((dd3, np.array([0.0, 0.0, 1.0]), nn), c), "Cat", "galv")

    def found(mb: C.MB) -> None:                        # над землёй — один блок; глубина — 10 см под грунт, дна нет
        V, F = C.box((0, 0, 0.01), (1.0, 1.0, 0.22))
        mb.add(V, F[1:], "concrete_old")

    def found_uv(ob, mb) -> None:                       # верх почти весь под опорной плитой мачты — реже
        ob["uv_rules"] = '[["z", 1, 0.9, 0.4]]'
    T.place("mfound", found, _m4((I3[0], I3[1], I3[2]), (0, y0, 0)), "Cat", "concrete", sharp=30, post=found_uv)
    h = half(H)

    def head(mb: C.MB) -> None:                         # оголовок: два швеллера — выпрямленными полосами
        for s_ in (-1, 1):
            V, F = C.prism(C.channel_profile(0.12, 0.05, 0.006), -h - 0.06, h + 0.06, origin=(s_ * h, 0.0, H - 0.06),
                           ex=(s_, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0))
            mb.add(V, F, "galv")

    def head_plate(mb: C.MB) -> None:
        mb.extend(C.box((0, 0, H + 0.006), (RIG_W + 0.12, 0.42, 0.012)), "galv")
    def head_plate_uv(ob, mb) -> None:                 # плита на 8,4 м: видна снизу, верх — нет
        fold_uv(ob, 45.0, down=True)
        ob["uv_rules"] = '[["z", -1, 0.7, 1.0], ["z", 1, 0.7, 0.3]]'
    T.place("mhead", head, _m4((I3[0], I3[1], I3[2]), (0, y0, 0)), "Cat", "galv",
            post=lambda ob, mb: T.G.prism_strip_uv(ob, [len(v) for v in mb.V]))
    T.place("mheadplate", head_plate, _m4((I3[0], I3[1], I3[2]), (0, y0, 0)), "Cat", "galv", post=head_plate_uv)
    # заземляющий спуск и табличка — у каждой мачты свои (сторона)
    sx, sy = 1, side
    P_ = np.array([(sx * half(z) + 0.05, y0 + sy * half(z) + 0.02 * sy, z) for z in np.linspace(H - 0.3, 0.3, 4)])
    P_ = np.vstack([P_, [P_[-1] + (0.08, 0, -0.25), P_[-1] + (0.2, 0, -0.45)]])
    mb = C.MB()
    P.split_tubes(mb, P_, 0.005, 4, 3.0, "steel")
    ob = T.G.part(mb, f"mlead_{side}", "Rebar", "rebar", T.col, T.parent, sharp=80)     # ржавый пруток, не атлас
    T.G.tubes_uv(ob, [len(v) for v in mb.V], 4, 0.08)
    def sign(mb: C.MB) -> None:                         # табличка лицом к +Y; у мачты −Y — та же, повёрнутая
        V, F = C.prism(C.rect_profile(0.24, 0.30), 0.0, 0.002, ex=(1, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0))
        mb.add(V, F, "paint_white")
    R = np.eye(3) if side > 0 else C.rot("z", 180.0)
    T.place("msign", sign, _m4((R[:, 0], R[:, 1], R[:, 2]), (0, y0 + side * (half(2.6) + 0.04), 2.6)), "Cat", "sign")


def _girder_low(T: Tpl) -> None:
    y0, y1 = -MAST_Y - 0.35, MAST_Y + 0.35
    hw, hh = RIG_W / 2, RIG_H / 2
    zc = RIG_Z
    chords = [(hw, zc + hh), (-hw, zc + hh), (-hw, zc - hh), (hw, zc - hh)]
    for k, (x, z) in enumerate(chords):     # пояса — 12 одинаковыми кусками по 2,2 м: полоса шаблона короче, атлас плотнее
        cuts = np.linspace(y0, y1, 13)
        for ya, yb in zip(cuts[:-1], cuts[1:]):
            T.member("gchord", (x, ya, z), (x, yb, z), 0.075, 0.006, up=(np.sign(x), 0, np.sign(z - zc)))
    n = 44
    ys = np.linspace(y0 + 0.05, y1 - 0.05, n + 1)
    for k in range(n + 1):
        y = ys[k]
        for x in (hw, -hw):
            T.member("gpost", (x, y, zc - hh + 0.04), (x, y, zc + hh - 0.04), 0.05, 0.005, up=(np.sign(x), 0, 0))
        if k % 2 == 0:
            for z in (zc + hh - 0.02, zc - hh + 0.02):
                T.member("gstrut", (-hw + 0.04, y, z), (hw - 0.04, y, z), 0.05, 0.005, up=(0, 0, np.sign(z - zc)))
    for k in range(n):
        ya, yb = ys[k], ys[k + 1]
        up_first = k % 2 == 0
        for x in (hw, -hw):
            za, zb = (zc - hh + 0.04, zc + hh - 0.04) if up_first else (zc + hh - 0.04, zc - hh + 0.04)
            T.member("gdiag", (x, ya, za), (x, yb, zb), 0.05, 0.005, up=(np.sign(x), 0, 0))
        if k % 2 == 0 and k + 2 <= n:
            yc = ys[k + 2]
            for z in (zc + hh - 0.02, zc - hh + 0.02):
                T.member("gbrace", (-hw + 0.04, ya, z), (hw - 0.04, yc, z), 0.05, 0.005, up=(0, 0, np.sign(z - zc)))
    I3 = np.eye(3)
    for yj in (-MAST_Y / 3 * 1.4, MAST_Y / 3 * 1.4):
        for x, z in chords:
            def splice(mb: C.MB) -> None:
                mb.extend(C.box((0, 0, 0), (0.012, 0.36, 0.09)), "galv")
            T.place("gsplice", splice, _m4((I3[0], I3[1], I3[2]), (x + np.sign(x) * 0.03, yj, z)), "Cat", "galv")
    for y in TRACKS:
        for x in (hw, -hw):
            for dy in (-0.45, 0.45):
                def gus(mb: C.MB) -> None:
                    Fr = C.frame_from(np.array([1.0, 0.0, 0.0]))
                    V, F = C.prism(C.rect_profile(0.16, 0.128), -0.004, 0.004, ex=Fr[0], ey=Fr[1], ez=Fr[2])
                    mb.add(V, F, "galv")
                T.place("ggusset", gus, _m4((I3[0], I3[1], I3[2]), (x + np.sign(x) * 0.012, y + dy, zc - hh + 0.09)),
                        "Cat", "galv")


def _string_parts(discs: int = 4) -> tuple:
    """Гирлянда в своих осях: z вниз по гирлянде от точки подвеса. Металл (серьга, шапки, стержни) и тарелки."""
    metal = [(0.008, 0.0), (0.008, 0.08)]
    sheds = []
    z = 0.08
    for _ in range(discs):
        metal += [(0.036, z + 0.005), (0.036, z + 0.055), (0.009, z + 0.062)]        # шапка и стержень до следующей
        sheds.append([(0.034, z + 0.040), (0.1275, z + 0.075), (0.122, z + 0.086), (0.034, z + 0.080)])
        z += 0.127
    return metal, sheds, z


def _saddle_low(T: Tpl, y: float) -> None:
    seat = np.array([0.0, y, MESS_Z + 0.03])
    zb = RIG_Z - RIG_H / 2
    I3 = np.eye(3)
    for s in (-1, 1):
        yt = y + s * 0.45
        T.member("sbeam", (-RIG_W / 2 - 0.04, yt, zb - 0.04), (RIG_W / 2 + 0.04, yt, zb - 0.04), 0.063, 0.006,
                 up=(0, 0, -1), ts="Cat")

        def lug(mb: C.MB) -> None:
            mb.extend(C.box((0, 0, 0), (0.012, 0.08, 0.06)), "galv")
        T.place("slug", lug, _m4((I3[0], I3[1], I3[2]), (0.0, yt, zb - 0.075)), "Cat", "galv")
        top = np.array([0.0, yt, zb - 0.10])
        bot = seat + (0, s * 0.04, 0.05)
        u = (bot - top) / np.linalg.norm(bot - top)
        Fr = C.frame_from(u)
        metal, sheds, ln_ = _string_parts(4)

        def s_metal(mb: C.MB) -> None:
            V, F = C.lathe(metal + [(0.007, float(np.linalg.norm(bot - top)))], 6)
            mb.add(V, F, "galv")

        def s_glass(mb: C.MB) -> None:
            for sh in sheds:                           # верхний срез тарелки — внутри шапки, не нужен
                V, F = C.lathe(sh, 8, cap_bottom=False)
                mb.add(V, F, "glass")
        M = _m4((Fr[0], Fr[1], Fr[2]), top)
        T.place("string_metal", s_metal, M, "Cat", "galv", sharp=60)
        T.place("string_glass", s_glass, M, "Cat", "glass", sharp=60)

    def seat_b(mb: C.MB) -> None:
        V, F = C.prism(C.rect_profile(0.32, 0.05), -0.012, 0.012, origin=(0, 0, 0.02), ex=(1, 0, 0), ey=(0, 0, 1),
                       ez=(0, 1, 0))
        mb.add(V, F, "galv")
        for dx in (-0.1, 0.1):
            mb.extend(C.box((dx, 0, -0.012), (0.05, 0.035, 0.02)), "galv")
    T.place("seat", seat_b, _m4((I3[0], I3[1], I3[2]), seat), "Cat", "galv")


def _registration_low(T: Tpl) -> None:
    import poles as P_
    I3 = np.eye(3)
    ends = []
    galv, poly = C.MB(), C.MB()
    for s in (-1, 1):
        anchor = np.array([0.0, s * (MAST_Y - mast_half(FT_Z) - 0.02), FT_Z + 0.02])
        galv.extend(C.box(anchor + (0, s * 0.02, 0), (0.2, 0.04, 0.12)), "galv")
        a = anchor - np.array([0, s * 0.06, 0])
        b = a - np.array([0, s * 0.40, 0.0])
        P_.rod_insulator_low(poly, a, b, 3, sides=6)
        c = b - np.array([0, s * 0.28, 0.0])
        galv.extend(C.cyl_between(b, c, 0.008, 6), "galv")
        galv.extend(C.box((b + c) / 2, (0.04, 0.12, 0.012)), "galv")
        ends.append(c)
    y_a, y_b = ends[0][1], ends[1][1]
    span = y_b - y_a
    ys = np.linspace(y_a, y_b, 24)
    zs = FT_Z - 0.06 * (1 - ((ys - (y_a + y_b) / 2) / (span / 2)) ** 2)
    rope, drop = C.MB(), C.MB()
    P_.split_tubes(rope, np.c_[np.zeros_like(ys), ys, zs], 0.0055, 4, 3.5, "steel")
    for y in TRACKS:
        z_ft = FT_Z - 0.06 * (1 - (y / (span / 2)) ** 2)
        for dy in (-0.9, 0.9):
            zb_ = FT_Z - 0.06 * (1 - ((y + dy) / (span / 2)) ** 2)
            drop.extend(C.tube(np.array([(0.0, y + dy, RIG_Z - RIG_H / 2 + 0.02), (0.0, y + dy, zb_ + 0.01)]), 0.003, 3,
                               caps=False), "steel")

            def clamp(mb: C.MB) -> None:
                mb.extend(C.box((0, 0, 0), (0.03, 0.03, 0.04)), "galv")
            T.place("dclamp", clamp, _m4((I3[0], I3[1], I3[2]), (0.0, y + dy, zb_ + 0.015)), "Cat", "galv")
        f0 = np.array([0.0, y - 0.55, z_ft - 0.02])

        def fix(mb: C.MB) -> None:
            mb.extend(C.box((0, 0, 0.02), (0.05, 0.06, 0.06)), "galv")
        T.place("fbox", fix, _m4((I3[0], I3[1], I3[2]), f0), "Cat", "galv")

        def fins(mb: C.MB) -> None:
            P_.rod_insulator_low(mb, (0, 0, 0), (0.0, 0.18, -0.10), 2, sides=6)
        T.place("fins", fins, _m4((I3[0], I3[1], I3[2]), f0), "Cat", "polymer", sharp=60)
        f1 = f0 + (0.0, 0.18, -0.10)
        f2 = np.array([0.0, y + 0.05, CONT_Z + 0.16])
        galv.extend(C.tube(np.array([f1, f1 + (f2 - f1) * 0.5 + (0, 0, 0.02), f2]), 0.013, 6), "galv")
        f3 = np.array([0.0, y + 0.45, CONT_Z + 0.03])
        galv.extend(C.tube(np.array([f2, f2 + (0, 0.2, -0.07), f3]), 0.009, 6), "galv")

        def cclamp(mb: C.MB) -> None:
            mb.extend(C.box((0, 0, 0), (0.07, 0.03, 0.035)), "galv")
        T.place("cclamp", cclamp, _m4((I3[0], I3[1], I3[2]), (0.0, y, CONT_Z + 0.02)), "Cat", "galv")
        galv.extend(C.tube(np.array([f3, (0.0, y + 0.02, CONT_Z + 0.04)]), 0.006, 4), "galv")
    T.G.part(galv, "reg_hardware", "Cat", "galv", T.col, T.parent, sharp=35)
    T.G.part(poly, "reg_insulators", "Cat", "polymer", T.col, T.parent, sharp=60)
    ob = T.G.part(rope, "reg_rope", "Rebar", "rebar", T.col, T.parent, sharp=80)
    T.G.tubes_uv(ob, [len(v) for v in rope.V], 4, 0.08)
    ob = T.G.part(drop, "reg_droppers", "Rebar", "rebar", T.col, T.parent, sharp=80)
    T.G.tubes_uv(ob, [len(v) for v in drop.V], 3, 0.08)


def _feeder_low(T: Tpl, y0: float) -> None:
    base = np.array([0.0, y0, MAST_TOP + 0.012])
    top_z = FEED_Z - 0.20
    for dx in (-0.08, 0.08):
        T.member(f"fpost_{dx > 0}", base + (dx, 0, 0), (dx, y0, top_z), 0.063, 0.006, up=(np.sign(dx), 0, 0),
                 caps=True, ts="Cat")
    T.member("fstrut", (-0.10, y0, top_z - 0.25), (0.10, y0, top_z - 0.25), 0.05, 0.005, ts="Cat")
    mb, ins = C.MB(), C.MB()
    V, F = C.prism(C.angle_profile(0.075, 0.006)[::-1] * (1, -1), y0 - 0.45, y0 + 0.45, origin=(-0.04, 0, top_z),
                   ex=(1, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0))
    mb.add(V, F, "galv")
    for dy in (-0.3, 0.3):
        p = np.array([0.0, y0 + dy, top_z])
        mb.extend(C.cyl_between(p - (0, 0, 0.02), p + (0, 0, 0.09), 0.011, 6), "galv")
        prof = [(0.016, 0.0), (0.058, 0.006), (0.036, 0.035), (0.052, 0.074), (0.030, 0.100), (0.036, 0.115),
                (0.012, 0.132), (0.0, 0.132)]
        V, F = C.lathe(prof, 8, center=p + (0, 0, 0.07))
        ins.add(V, F, "porcelain_white")
    T.G.part(mb, "feeder_bracket", "Cat", "galv", T.col, T.parent, sharp=35)
    T.G.part(ins, "feeder_insulators", "Cat", "porcelain", T.col, T.parent, sharp=60)


def game(col, parent, key: str, ctx: dict) -> None:
    """Игровые детали поперечины (game.py): мачты, ригель, подвесы, фиксирующий трос, кронштейн фидеров."""
    T = Tpl(col, parent)
    for side in (-1, 1):
        _mast_low(T, side * MAST_Y, side)
    _girder_low(T)
    for y in TRACKS:
        _saddle_low(T, y)
    _registration_low(T)
    _feeder_low(T, -MAST_Y)
    SMALL = ("reg_hardware", "reg_insulators", "string_glass", "string_metal", "fins", "feeder_insulators", "seat",
             "dclamp", "cclamp", "fbox", "slug", "gsplice", "ggusset", "mgusset", "feeder_bracket")
    FOLD = ("reg_hardware", "seat", "dclamp", "cclamp", "fbox", "slug", "gsplice", "ggusset", "mgusset",
            "feeder_bracket", "mplate", "msign")                   # коробки и пластины — сеткой, не шестью островами
    done = set()
    for o in col.objects:
        if o.type != "MESH" or o.data.name in done:
            continue
        done.add(o.data.name)
        small = o.get("part") in SMALL
        if o.get("part") in FOLD:
            fold_uv(o, 66.0 if small else 45.0)
        elif small and o.get("uv") != "keep":
            o["uv"] = 66.0
        if small:
            o["uv_scale"] = 0.4
        if o.get("tex_set") == "Cat" and o.get("part") not in ("mfound", "msign"):
            o["uv_half"] = True                                   # одна сталь (стекло, полимер) — отступ вполовину
