"""Остановочный павильон «Проспекта» (набор bus_stop, 4 штуки на карте).

Прообраз — современный городской павильон 6,0 × 1,9 м (своя форма, без марок): каркас из профтрубы 80×80 на
анкерных пластинах, задняя стенка — три панели закалённого стекла 10 мм в ригелях, левое крыло — стекло,
правое — двусторонний световой короб «сити-формат» (поле 1,2 × 1,8 м), консольный козырёк 6,4 × 2,4 м с уклоном
назад к водостоку и водосточной трубе, фасонная кромка с полем под название остановки, скамья на трёх опорах с
деревянными брусками, стенд с расписанием и номерами маршрутов.
Габарит серого набора: стенки 2,3 м, козырёк на 2,55 м; задняя стенка — на игровом z = −1,0 (Blender y = +1,0),
открыто к дороге — Blender −Y. Начало координат — земля в середине павильона.

«Разбит»: закалённое стекло не колется на кинжалы — панель осыпается крошкой (кубики 8–15 мм) кучкой под рамой,
у ригелей остаются полоски крошки; короб без лицевого стекла, плакат порван; одна опора скамьи погнута.
"""
from __future__ import annotations

import math

import numpy as np

import clib as C

LX = 6.0                         # по осям крайних стоек
YB = 1.00                        # ось задней стенки
YW = -0.62                       # передняя стойка крыльев
POST = 0.08                      # профтруба 80×80×4
Z_ROOF0 = 2.45                   # низ балок козырька у задней стенки
ROOF_X, ROOF_Y0, ROOF_Y1 = 3.2, -1.10, 1.30   # козырёк: X ± 3,2, Y от −1,1 до +1,3
SLOPE = 0.045                    # уклон козырька назад (на 2,4 м)
GZ0, GZ1 = 0.20, 2.27            # стекло по высоте
XS = [-3.0, -1.0, 1.0, 3.0]      # задние стойки


def roof_z(y: float) -> float:
    """Низ кровельной панели в точке y (выше спереди, ниже сзади)."""
    return Z_ROOF0 + 0.14 + SLOPE * (ROOF_Y1 - y) / (ROOF_Y1 - ROOF_Y0) * 2.4 / 2.4


def post(mb: C.MB, an: C.MB, x: float, y: float, h: float) -> None:
    """Стойка 80×80 с фаской, анкерная пластина 250×250×12 с рёбрами и 4 гайками (an — тонкие детали)."""
    mb.extend(C.box((x, y, h / 2), (POST, POST, h)), "paint_grey")
    mb = an
    mb.extend(C.box((x, y, 0.006), (0.25, 0.25, 0.012)), "paint_grey")
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        tri = np.array([(0.0, 0.0), (0.075, 0.0), (0.0, 0.12)])
        e = np.array([dx, dy, 0.0])
        V, F = C.prism(tri, -0.004, 0.004, origin=(x + dx * POST / 2, y + dy * POST / 2, 0.012), ex=e, ey=(0, 0, 1),
                       ez=np.cross(e, (0, 0, 1)))
        mb.add(V, F, "paint_grey")
    for dx in (-0.095, 0.095):
        for dy in (-0.095, 0.095):
            mb.extend(C.cyl((x + dx, y + dy, 0.020), 0.013, 0.016, 6), "galv")
            mb.extend(C.cyl((x + dx, y + dy, 0.034), 0.007, 0.024, 10), "galv")


def rails(mb: C.MB, a, b) -> None:
    """Ригели под стекло: верхний и нижний П-профиль 50×40 между стойками, с пазом под стекло."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    ln = float(np.linalg.norm(d))
    e = d / ln
    n = np.cross((0, 0, 1), e)
    c = (a + b) / 2
    for z, sgn in ((GZ0 - 0.025, 1), (GZ1 + 0.025, -1)):
        prof = np.array([(-0.025, -0.02), (0.025, -0.02), (0.025, 0.02), (0.008, 0.02), (0.008, -0.005),
                         (-0.008, -0.005), (-0.008, 0.02), (-0.025, 0.02)])
        prof[:, 1] *= sgn
        V, F = C.prism(prof, -ln / 2 + POST / 2, ln / 2 - POST / 2, origin=(c[0], c[1], z), ex=n, ey=(0, 0, 1), ez=e)
        mb.add(V, F, "paint_grey")


def glass_panel(mb: C.MB, a, b, inset: float = 0.0) -> None:
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    ln = float(np.linalg.norm(d))
    e = d / ln
    n = np.cross((0, 0, 1), e)
    c = (a + b) / 2
    R = np.stack([e, n, np.array([0, 0, 1.0])], axis=1)
    V, F = C.box((0, 0, 0), (ln - POST - 0.02 - inset, 0.010, GZ1 - GZ0 + 0.02))
    mb.add(C.xf(V, R, (c[0], c[1], (GZ0 + GZ1) / 2)), F, "glass")


def clamps(mb: C.MB, a, b) -> None:
    """Прижимы стекла к стойкам: по два с каждой стороны, «шайба» 50 мм."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    e = (b - a) / np.linalg.norm(b - a)
    n = np.cross((0, 0, 1), e)
    for p, s in ((a, 1), (b, -1)):
        for z in (0.75, 1.75):
            for side in (-1, 1):
                c = p + e * s * (POST / 2 + 0.03) + n * side * 0.012
                V, F = C.lathe([(0.025, 0.0), (0.025, 0.006), (0.02, 0.012)], 16)
                R = np.stack([e, np.cross(n * side, e), n * side], axis=1)
                mb.add(C.xf(V, R, (c[0], c[1], z)), F, "galv")


def roof(mb: C.MB, det: C.MB) -> None:
    """Козырёк: балки-консоли над стойками, кассетная кромка 160 мм с полем под название, водосток и труба."""
    # балки вдоль Y над задними стойками (переменного сечения: тоньше к переднему краю)
    for x in XS:
        y0, y1 = ROOF_Y0 + 0.08, ROOF_Y1 - 0.06
        P = np.array([(x, y1, Z_ROOF0 + 0.07), (x, YB, Z_ROOF0 + 0.07), (x, y0, Z_ROOF0 + 0.11)])
        V, F = C.sweep(C.rect_profile(0.06, 0.14), P, up=(0, 0, 1), scale=[1.0, 1.0, 0.55])
        mb.add(V, F, "paint_grey")
    # продольные прогоны
    for y in (YB, 0.0, -0.75):
        z = roof_z(y) - 0.03
        mb.extend(C.box((0, y, z), (2 * ROOF_X - 0.12, 0.05, 0.05)), "paint_grey")
    # кровельная панель (сотовый поликарбонат на каркасе — сплошной лист 32 мм) с уклоном
    yf, yb = ROOF_Y0 + 0.02, ROOF_Y1 - 0.02
    P = np.array([(-ROOF_X + 0.02, yf, roof_z(yf)), (ROOF_X - 0.02, yf, roof_z(yf)), (ROOF_X - 0.02, yb, roof_z(yb)),
                  (-ROOF_X + 0.02, yb, roof_z(yb))])
    V = np.vstack([P, P + np.array([0, 0, 0.032])])
    F = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    mb.add(V, F, "glass")
    # кассетная кромка по периметру (алюминиевая композитная панель): высота 160 мм, спереди поле под название
    h = 0.16
    for y in (ROOF_Y0, ROOF_Y1):
        z = roof_z(y) + 0.02
        mb.extend(C.box((0, y, z), (2 * ROOF_X, 0.03, h)), "paint_grey")
    for x in (-ROOF_X, ROOF_X):
        P = np.array([(x, ROOF_Y0 + 0.015, roof_z(ROOF_Y0) + 0.02), (x, ROOF_Y1 - 0.015, roof_z(ROOF_Y1) + 0.02)])
        V, F = C.sweep(C.rect_profile(0.03, h), P, up=(0, 0, 1))
        mb.add(V, F, "paint_grey")
    # поле под название остановки (белое, надпись — отделкой) и световая полоса под кромкой
    mb = det
    mb.extend(C.box((0, ROOF_Y0 - 0.017, roof_z(ROOF_Y0) + 0.02), (2.6, 0.004, 0.11)), "paint_white")
    mb.extend(C.box((0, ROOF_Y0 + 0.03, roof_z(ROOF_Y0) - 0.055), (2 * ROOF_X - 0.2, 0.03, 0.012)), "lamp")
    # водосток сзади (полукруглый жёлоб) и труба на левой задней стойке
    prof = np.array([(0.06 * math.cos(a), 0.06 * math.sin(a)) for a in np.linspace(math.pi, 2 * math.pi, 9)])
    prof = np.vstack([prof, prof[::-1] * 0.92])
    gz = roof_z(ROOF_Y1) - 0.02
    V, F = C.sweep(prof, np.array([(-ROOF_X - 0.02, ROOF_Y1 + 0.075, gz), (ROOF_X + 0.02, ROOF_Y1 + 0.075, gz)]),
                   up=(0, 0, 1))
    mb.add(V, F, "galv")
    P = np.array([(-ROOF_X + 0.25, ROOF_Y1 + 0.075, gz - 0.04), (-ROOF_X + 0.25, ROOF_Y1 + 0.04, gz - 0.25),
                  (XS[0] + 0.12, YB + 0.10, gz - 0.45), (XS[0] + 0.12, YB + 0.10, 0.25), (XS[0] + 0.12, YB + 0.25, 0.08)])
    mb.extend(C.tube(P, 0.04, 12), "galv")
    for z in (0.6, 1.4, 2.0):                                                # хомуты трубы
        mb.extend(C.box((XS[0] + 0.08, YB + 0.10, z), (0.06, 0.012, 0.03)), "galv")


def lightbox(mb: C.MB, det: C.MB, glass: bool = True, torn: bool = False) -> None:
    """Сити-формат в правом крыле: корпус 1,40 × 2,05 × 0,16, поле 1,2 × 1,8 с обеих сторон, лицевые стёкла."""
    x = XS[-1]
    yc = (YB - POST / 2 + YW + POST / 2) / 2
    ln = (YB - POST / 2) - (YW + POST / 2) - 0.02
    zc = 0.25 + 2.05 / 2
    # рама-корпус: 4 бруска 110 мм
    fr = 0.10
    mb.extend(C.box((x, yc, zc + 2.05 / 2 - fr / 2), (0.16, ln, fr)), "paint_grey")
    mb.extend(C.box((x, yc, zc - 2.05 / 2 + fr / 2), (0.16, ln, fr)), "paint_grey")
    for s in (-1, 1):
        mb.extend(C.box((x, yc + s * (ln / 2 - fr / 2), zc), (0.16, fr, 2.05 - 2 * fr)), "paint_grey")
    # ножки короба (между ним и землёй)
    for s in (-1, 1):
        mb.extend(C.box((x, yc + s * (ln / 2 - 0.12), 0.125), (0.10, 0.06, 0.25)), "paint_grey")
    # плакаты (внутри) и стёкла
    mb = det
    pw, ph = ln - 2 * fr, 2.05 - 2 * fr
    for s in (-1, 1):
        if torn and s > 0:
            # порванный плакат: верхняя часть отвисла вперёд
            mb.extend(C.box((x + s * 0.03, yc, zc - ph * 0.15), (0.004, pw, ph * 0.7)), "paint_white")
            V, F = C.box((0, 0, 0), (0.004, pw * 0.8, ph * 0.3))
            mb.add(C.xf(V, C.rot("y", 25.0), (x + s * 0.09, yc + 0.05, zc + ph * 0.28)), F, "paint_white")
        else:
            mb.extend(C.box((x + s * 0.03, yc, zc), (0.004, pw, ph)), "paint_white")
        if glass or s < 0:
            mb.extend(C.box((x + s * 0.072, yc, zc), (0.006, pw + 0.02, ph + 0.02)), "glass")


def bench(mb: C.MB, bent: bool = False) -> None:
    """Скамья 3,6 м: три опоры из полосы 60×10 (П-образные), пять брусков 70×35, база на анкерах."""
    x0, x1 = -2.2, 1.4
    yc, zs = 0.62, 0.46
    for k, x in enumerate((x0 + 0.15, (x0 + x1) / 2, x1 - 0.15)):
        tilt = 9.0 if (bent and k == 2) else 0.0
        prof = np.array([(-0.005, -0.03), (0.005, -0.03), (0.005, 0.03), (-0.005, 0.03)])   # 10 мм в плоскости гиба, 60 — по X
        pts = np.array([(x, yc - 0.20, 0.0), (x, yc - 0.17, zs - 0.06), (x, yc + 0.20, zs - 0.06), (x, yc + 0.22, 0.0)])
        if tilt:
            pts = C.xf(pts - (x, yc, 0), C.rot("y", tilt), (x, yc, 0)) - np.array([0, 0, 0.0])
        V, F = C.sweep(prof, pts, up=(1, 0, 0))
        mb.add(V, F, "paint_grey")
        for y in (yc - 0.20, yc + 0.22):
            mb.extend(C.box((x, y, 0.005), (0.10, 0.12, 0.01)), "paint_grey")
    # бруски: при погнутой опоре правый конец осел
    for j in range(5):
        y = yc - 0.18 + j * 0.09
        a = np.array([x0, y, zs - 0.02])
        b = np.array([x1, y, zs - 0.02])
        if bent:
            b = b + np.array([0.0, 0.0, -0.08])
        if bent and j in (1, 2):
            # два бруска сломаны у правой опоры: обломок свисает
            m = a + (b - a) * 0.8
            V, F = C.sweep(C.rect_profile(0.07, 0.035, 0.008), np.array([a, m]), up=(0, 0, 1))
            mb.add(V, F, "wood")
            tip = m + np.array([0.35, 0.02, -0.30 if j == 1 else -0.20])
            V, F = C.sweep(C.rect_profile(0.07, 0.035, 0.008), np.array([m + np.array([0.02, 0, -0.01]), tip]), up=(0, 0, 1))
            mb.add(V, F, "wood")
            continue
        V, F = C.sweep(C.rect_profile(0.07, 0.035, 0.008), np.array([a, b]), up=(0, 0, 1))
        mb.add(V, F, "wood")


def info_board(mb: C.MB) -> None:
    """Стенд: расписание и номера маршрутов на задней стойке слева изнутри, табличка с номерами сверху."""
    x, y = XS[1] - 0.55, YB - 0.04
    mb.extend(C.box((x, y, 1.35), (0.80, 0.03, 1.05)), "paint_grey")
    mb.extend(C.box((x, y - 0.016, 1.35), (0.72, 0.002, 0.97)), "paint_white")
    mb.extend(C.box((x, y - 0.019, 1.35), (0.74, 0.004, 0.99)), "glass")
    # указатель-«флажок» с номерами маршрутов на левой передней стойке
    mb.extend(C.box((-3.0, YW - 0.05, 2.12), (0.03, 0.42, 0.22)), "paint_white")
    mb.extend(C.box((-3.0, YW - 0.05, 2.12), (0.034, 0.44, 0.012)), "paint_blue")


def granules(mb: C.MB, rng: np.random.Generator, center, spread, n: int, z0: float = 0.0) -> None:
    """Крошка закалённого стекла: кубики 8–15 мм горкой (больше у середины)."""
    c = np.asarray(center, float)
    for _ in range(n):
        r = rng.normal(0, 1, 2) * np.asarray(spread)
        s = rng.uniform(0.008, 0.016)
        V, F = C.box((0, 0, 0), (s, s * rng.uniform(0.7, 1.2), 0.008))
        h = max(0.0, 0.03 * math.exp(-float((r / np.asarray(spread)) @ (r / np.asarray(spread))) / 2) * rng.uniform(0, 1))
        V = C.xf(V, C.rot("z", rng.uniform(0, 90)) @ C.rot("x", rng.uniform(-30, 30)), (c[0] + r[0], c[1] + r[1], z0 + 0.004 + h))
        mb.add(V, F, "glass")


def edge_crumbs(mb: C.MB, rng: np.random.Generator, a, b, z: float, depth: float) -> None:
    """Полоска крошки, оставшаяся в пазу ригеля: рваная кромка шириной до depth."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    e = (b - a) / np.linalg.norm(b - a)
    n = np.cross((0, 0, 1), e)
    ln = float(np.linalg.norm(b - a)) - POST - 0.04
    c0 = (a + b) / 2 - e * ln / 2
    t = 0.0
    while t < ln:
        w = rng.uniform(0.03, 0.09)
        h = rng.uniform(0.01, depth)
        V, F = C.box((0, 0, 0), (w, 0.010, h))
        p = c0 + e * (t + w / 2)
        zz = z + (h / 2 if z < 1 else -h / 2)
        V = C.xf(V, np.stack([e, n, np.array([0, 0, 1.0])], axis=1), (p[0], p[1], zz))
        mb.add(V, F, "glass")
        t += w + rng.uniform(0.0, 0.02)


def pavilion(col, parent, broken: bool, seed: int = 5) -> None:
    rng = np.random.default_rng(seed)
    fr = C.MB()
    an = C.MB()
    for x in XS:
        post(fr, an, x, YB, Z_ROOF0)
    for x in (XS[0], XS[-1]):
        post(fr, an, x, YW, Z_ROOF0 + 0.03)
    an.build("BusStop_Anchors", col, parent, bevel=0.0015, seg=1)
    # ригели: задняя стенка (три пролёта) и левое крыло
    for k in range(3):
        rails(fr, (XS[k], YB, 0), (XS[k + 1], YB, 0))
    rails(fr, (XS[0], YB, 0), (XS[0], YW, 0))
    # верхняя обвязка крыльев (связь передней стойки с балкой)
    for x in (XS[0], XS[-1]):
        fr.extend(C.box((x, (YB + YW) / 2, Z_ROOF0 + 0.02), (POST, YB - YW, POST)), "paint_grey")
    fr.build("BusStop_Frame", col, parent, bevel=0.006, seg=2)
    hw = C.MB()
    for k in range(3):
        clamps(hw, (XS[k], YB, 0), (XS[k + 1], YB, 0))
    clamps(hw, (XS[0], YB, 0), (XS[0], YW, 0))
    hw.build("BusStop_Clamps", col, parent)
    rf, rd = C.MB(), C.MB()
    roof(rf, rd)
    rf.build("BusStop_Roof", col, parent, bevel=0.004, seg=1)
    rd.build("BusStop_RoofDetails", col, parent)
    gl = C.MB()
    spans = [((XS[k], YB, 0), (XS[k + 1], YB, 0)) for k in range(3)] + [((XS[0], YB, 0), (XS[0], YW, 0))]
    gone = {1, 3} if broken else set()
    for k, (a, b) in enumerate(spans):
        if k in gone:
            continue
        glass_panel(gl, a, b)
    if not gl.empty():
        gl.build("BusStop_Glass", col, parent)
    lb, ld = C.MB(), C.MB()
    lightbox(lb, ld, glass=not broken, torn=broken)
    lb.build("BusStop_Lightbox", col, parent, bevel=0.004, seg=1)
    ld.build("BusStop_LightboxFaces", col, parent)
    bn = C.MB()
    bench(bn, bent=broken)
    bn.build("BusStop_Bench", col, parent, bevel=0.004, seg=1)
    ib = C.MB()
    info_board(ib)
    ib.build("BusStop_Info", col, parent)
    if broken:
        cr = C.MB()
        for k in gone:
            a, b = spans[k]
            edge_crumbs(cr, rng, a, b, GZ0 + 0.005, 0.06)
            edge_crumbs(cr, rng, a, b, GZ1 - 0.005, 0.10)
            a, b = np.asarray(a, float), np.asarray(b, float)
            mid = (a + b) / 2
            n = np.cross((0, 0, 1), (b - a) / np.linalg.norm(b - a))
            along = np.abs((b - a) / np.linalg.norm(b - a))
            spread_in = mid - n * 0.15
            granules(cr, rng, spread_in, along[:2] * 0.55 + np.abs(n[:2]) * 0.25 + 0.05, 700)
            granules(cr, rng, mid + n * 0.25, along[:2] * 0.45 + np.abs(n[:2]) * 0.20 + 0.04, 350)
        # из короба: стекло лицевой стороны — крошкой у ножек
        granules(cr, rng, (XS[-1] - 0.35, (YB + YW) / 2, 0), (0.25, 0.55), 400)
        cr.build("BusStop_GlassCrumbs", col, parent)


VARIANTS = {"intact": "Целый", "broken": "Разбит"}
STEP = 8.0
META = {
    "folder": "Остановка", "name": "BusStop_Pavilion", "title": "Остановочный павильон",
    "step": 8.0,
    "shots": [["3/4 спереди", [5.6, -6.6, 2.6], [0.0, 0.1, 1.2], 30], ["3/4 сзади", [-5.4, 6.4, 2.8], [0.0, 0.2, 1.2], 30],
              ["скамья и узел стойки", [-1.6, -1.2, 1.1], [-2.6, 0.7, 0.45], 30]],
    "shots_by": {
        "broken": [["3/4 спереди", [5.6, -6.6, 2.6], [0.0, 0.1, 1.2], 30], ["короб и крошка стекла", [5.2, -2.6, 1.6], [2.4, 0.4, 0.4], 30],
                   ["скамья и пролёт без стекла", [0.6, -2.4, 1.5], [-0.4, 0.8, 0.6], 30]],
    },
}


def build(keys: list[str]) -> dict:
    out = {}
    for i, k in enumerate(keys):
        name = VARIANTS[k]
        col = C.collection(name)
        r = C.root(f"BusStop | {name}", col, (i * STEP, 0.0, 0.0))
        pavilion(col, r, k == "broken")
        out[k] = name
    return out
