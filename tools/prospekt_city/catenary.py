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
