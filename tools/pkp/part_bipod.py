# ПКП: сошки у дульной части. Шарнир на кронштейне основания мушки (part_barrel.fsb: щека вниз с двумя отверстиями),
# вилка-обойма, две ноги из штампованного швеллера со стыком труба-в-трубе, сошники на шарнирах, пружина-разжим
# между ногами, оси со шплинтом. Положение в модели — РАЗЛОЖЕНО (стоит на земле).
# Источники формы (Wikimedia Commons, V. V. Kuzmin, CC BY-SA, снимки в refs/web, опись sources.md):
#   B08_bipod/16 (шарнир и пружина спереди), A_general/08 (вид спереди: разведение ног, сошники, рычажок-упор,
#   пружина под шарниром), A_general/01 и /16 (вид сбоку: ноги почти отвесны, длина ноги к стволу, ступни).
# Что на фото не видно, помечено «оценка»: длина и сечение ног, угол разведения, форма обоймы, упор и пружина вблизи.
# Складывание: у ПК/ПКП сошки укладываются НАЗАД вдоль ствола (по памяти из руководств, подтверждения в сети не найдено —
# «оценка»); фиксатора сложенного положения на снимках нет, не строился.
import math

import numpy as np

from dims import *
from sdf import *

U = TILE_K                       # числа кронштейна — из part_barrel.fsb (они там в единицах до поправки масштаба)
X0 = 432.5 * U                   # ось отверстий кронштейна по X
ZP = -38.5 * U                   # нижнее отверстие кронштейна — ось складывания (вторая, выше, Z = -22,5·U, свободна)
LUG_HT = 5.0 * U                 # полутолщина щеки кронштейна
LUG_HOLE = 5.0 * U               # радиус отверстий кронштейна
PIN_R = 4.7                      # ось складывания: в отверстие 5,03 с зазором 0,3

YP = 16.0                        # ось разведения ноги: расстояние от плоскости симметрии (оценка)
ZH = ZP - 26.0                   # высота осей разведения ног (оценка)
LEG_L = 345.0                    # от оси разведения до оси сошника (оценка: снимок 01, нога ≈ 0,7 длины выше-ствола-кожуха)
DEPLOY = 30.0                    # угол разведения ноги от отвеса, град (оценка: фото 08 даёт 35–38° с перспективой)
FOLD_SPLAY = 3.0                 # разведение в сложенном положении (ноги лежат по бокам газовой трубки)
FOLD_DEG = 90.0                  # вилка поворачивается вокруг +Y на этот угол: ноги — назад вдоль ствола
LEG_HW = 13.0                    # полуширина ноги по X (оценка по снимку 01: ≈ 26–30 мм)
LEG_HT = 5.5                     # полутолщина ноги по Y (оценка по снимку 08: ≈ 11–12 мм)
SHEET_T = 1.5                    # лист швеллера
FOOT_Z = -345.0                  # ось сошника в местных координатах ноги
YT = YP + LEG_L * math.sin(math.radians(DEPLOY))   # ось сошника в мировых координатах
ZT = ZH - LEG_L * math.cos(math.radians(DEPLOY))
SPRING_R, SPRING_W = 4.6, 0.65   # пружина-разжим: радиус витка, радиус проволоки (оценка по снимку 16)


def _tools(F, side):
    """Помощники ноги: местные координаты (X — ширина, Y — наружу, Z — вниз по ноге, начало на оси разведения)
    переносятся в мировые: зеркало для правой ноги, сдвиг на ось и поворот на угол разведения."""
    sy = float(side)
    ang = side * DEPLOY
    th = math.radians(ang)
    c, s = math.cos(th), math.sin(th)
    piv = (X0, sy * YP, ZH)

    def place(fn):
        def m(X, Y, Z):
            return fn(X, sy * Y, Z)
        return rot(move(m, piv), "X", piv, ang)

    def wbb(lo, hi, pad=0.6):
        P = []
        for x in (lo[0], hi[0]):
            for y in (lo[1], hi[1]):
                for z in (lo[2], hi[2]):
                    u = sy * y; v = z
                    P.append((piv[0] + x, piv[1] + u * c - v * s, piv[2] + u * s + v * c))
        P = np.array(P)
        return (tuple(P.min(axis=0) - pad), tuple(P.max(axis=0) + pad))

    def add(fn, lo, hi, r=0.0):
        F.add(place(fn), r, bbox=wbb(lo, hi))

    def sub(fn, lo, hi, r=0.0):
        F.sub(place(fn), r, bbox=wbb(lo, hi))

    return place, wbb, add, sub


def _leg_bounds(side):
    class _F:  # только чтобы взять wbb
        pass
    _, wbb, _, _ = _tools(_F, side)
    return wbb((-20, -33, -362), (20, 10, 9), pad=1.0)


def leg(side):
    def build(h):
        lo, hi = _leg_bounds(side)
        F = Field("Bipod_Leg_%s" % ("L" if side > 0 else "R"), lo, hi, h)
        place, wbb, add, sub = _tools(F, side)
        HW, HT = LEG_HW, LEG_HT
        # шарнирный барабан на оси разведения и сплошная верхушка ноги (под рёбра ушек вилки)
        add(cyl("X", (0, 0), 6.0, -HW, HW, rim=0.6), (-HW, -6, -6), (HW, 6, 6), 0.0)
        add(box((-HW, -HT, -30), (HW, HT, -3), 1.2), (-HW, -HT, -30), (HW, HT, -3), 0.8)
        # верхняя часть: штампованный швеллер, спинка снаружи, полки внутрь, открыт внутрь
        add(box((-HW, -HT, -186), (HW, HT, -20), 1.2), (-HW, -HT, -186), (HW, HT, -20), 0.6)
        sub(box((-HW + SHEET_T, -HT - 1.5, -187.5), (HW - SHEET_T, HT - SHEET_T, -30), 0.5),
            (-HW, -HT - 2, -188), (HW, HT, -29), 0.0)
        # поперечная муфта стыка «труба в трубе»
        add(box((-HW - 1.6, -HT - 1.8, -194), (HW + 1.6, HT + 1.8, -176), 1.6), (-HW - 2, -HT - 2, -195), (HW + 2, HT + 2, -175), 0.6)
        # нижнее колено: плоская полоса, входит в верхнее
        add(box((-10.0, -4.5, -322), (10.0, 4.5, -184), 1.4), (-10, -5, -323), (10, 5, -183), 0.8)
        # штампованные рёбра жёсткости на спинках (выпуклые)
        add(box((-2.4, HT - 0.4, -172), (2.4, HT + 0.9, -34), 0.9), (-3, HT - 1, -173), (3, HT + 1.5, -33), 0.4)
        add(box((-2.0, 3.6, -312), (2.0, 5.0, -202), 0.7), (-3, 3, -313), (3, 5.5, -201), 0.3)
        # заклёпки на спинке: вверху и по длине швеллера
        for x, z in ((-8.5, -18), (8.5, -18), (-9.0, -110), (9.0, -110), (-9.0, -160), (9.0, -160)):
            add(cyl("Y", (x, z), 2.1, HT - 0.4, HT + 1.0, rim=0.6), (x - 3, HT - 1, z - 3), (x + 3, HT + 1.5, z + 3), 0.3)
        # ушки хомута под ось сошника: две пластинки с круглым концом
        ear = seg2((0.0, -312.0), (0.0, FOOT_Z), 6.0)
        for x0, x1 in ((-7.4, -5.0), (5.0, 7.4)):
            add(prism2(ear, "YZ", x0, x1, rim=0.6), (x0, -6.5, -352), (x1, 6.5, -310), 0.6)
        # ось сошника с головками (заклёпка с натёками) — ось 2,5, отверстие в сошнике 2,9
        add(cyl("X", (0, FOOT_Z), 2.5, -8.6, 8.6), (-9, -3, FOOT_Z - 3), (9, 3, FOOT_Z + 3), 0.0)
        for x0, x1 in ((7.2, 8.6), (-8.6, -7.2)):
            add(cyl("X", (0, FOOT_Z), 3.6, x0, x1, rim=0.5), (x0 - 1, -4, FOOT_Z - 4), (x1 + 1, 4, FOOT_Z + 4), 0.3)
        # рычажок-упор на внутренней стороне (фото 08, 16: гнутый пруток), приваривается к спинке швеллера
        pts = [(0.0, HT - SHEET_T, -140.0), (0.0, -27.0, -140.0), (0.0, -27.0, -157.0)]
        add(wire(pts, 2.0), (-3, -30, -160), (3, HT, -137), 0.5)
        # шпенёк под пружину-разжим на внутренней стороне верхушки
        add(cyl("Y", (0, -16), 1.4, -11.0, -4.5, rim=0.4), (-2, -12, -18), (2, -4, -14), 0.5)
        # отверстие шарнира разведения
        sub(cyl("X", (0, 0), 2.85, -HW - 2, HW + 2), (-HW - 3, -4, -4), (HW + 3, 4, 4), 0.0)
        return F
    return build


def foot(side):
    def build(h):
        sy = float(side)
        F = Field("Bipod_Foot_%s" % ("L" if side > 0 else "R"), (X0 - 36, sy * YT - 21, ZT - 18), (X0 + 36, sy * YT + 21, ZT + 8), h)

        def mir(fn):
            return move(lambda X, Y, Z: fn(X, sy * Y, Z), (X0, sy * YT, ZT))

        def wb(lo, hi):
            return bb(X0 + lo[0], X0 + hi[0], sy * YT + lo[1], sy * YT + hi[1], ZT + lo[2], ZT + hi[2])

        # шарнирная втулка между ушками ноги и шейка вниз к подошве
        F.add(mir(cyl("X", (0, 0), 5.2, -4.6, 4.6, rim=0.5)), 0.0, bbox=wb((-6, -7, -7), (6, 7, 7)))
        F.add(mir(box((-4.6, -6.5, -11.0), (4.6, 6.5, -2.0), 1.0)), 0.6, bbox=wb((-6, -8, -12), (6, 8, -1)))
        # подошва: плита с отогнутым вверх носком (в сторону дула), шипы снизу
        sole = Poly(fillet_poly([(-30.0, -14.0), (24.0, -14.0), (31.5, -8.0), (29.2, -5.9), (22.5, -10.5), (-30.0, -10.5)],
                                [1.2, 1.4, 0.8, 0.8, 1.2, 1.2]))
        F.add(mir(prism(sole, "XZ", -17.0, 17.0, rim=0.8)), 0.5, bbox=wb((-32, -18, -15), (33, 18, -5)))
        for x in (-20.0, -3.0, 14.0):
            F.add(mir(box((x - 1.6, -14.0, -15.6), (x + 1.6, 14.0, -13.0), 0.5)), 0.3, bbox=wb((x - 3, -15, -16), (x + 3, 15, -12)))
        # отверстие под ось сошника
        F.sub(mir(cyl("X", (0, 0), 2.9, -7, 7)), 0.0, bbox=wb((-8, -4, -4), (8, 4, 4)))
        return F
    return build


def yoke(h):
    """Вилка: две щёки охватывают щеку кронштейна на оси складывания, поперечина и ушки несут оси разведения ног."""
    F = Field("Bipod_Yoke", (X0 - 20, -27, ZH - 12), (X0 + 20, 27, ZP + 13), h)
    cheek = prism2(seg2((X0, ZP), (X0, ZH + 17.0), 8.0), "XZ", LUG_HT + 0.6, LUG_HT + 4.0, rim=0.7)
    F.add(both(cheek), 0.0, bbox=bb(X0 - 9, X0 + 9, -10, 10, ZH + 6, ZP + 9))
    bridge = box((X0 - 17.0, -25.0, ZH + 7.6), (X0 + 17.0, 25.0, ZH + 13.0), 1.5)
    F.add(bridge, 0.8, bbox=bb(X0 - 18, X0 + 18, -26, 26, ZH + 6, ZH + 14))
    ear2 = union2(rect2(8.0, 24.0, ZH, ZH + 14.0), circle2((16.0, ZH), 8.0))
    for x0, x1 in ((X0 - 16.2, X0 - 13.6), (X0 + 13.6, X0 + 16.2)):
        F.add(both(prism2(ear2, "YZ", x0, x1, rim=0.8)), 0.8, bbox=bb(x0 - 1, x1 + 1, -25, 25, ZH - 9, ZH + 15))
    F.sub(cyl("Y", (X0, ZP), 4.9, -12, 12), 0.4, bbox=bb(X0 - 6, X0 + 6, -10, 10, ZP - 6, ZP + 6))
    F.sub(both(cyl("X", (YP, ZH), 2.85, X0 - 20, X0 + 20)), 0.0, bbox=bb(X0 - 20, X0 + 20, -20, 20, ZH - 4, ZH + 4))
    return F


def pin_fold(h):
    """Ось складывания (по Y через щеку кронштейна) с головкой, шайбой и шплинтом."""
    prof = [(-12.2, 0.0), (-12.2, 4.2), (-11.7, 4.7), (-10.2, 4.7), (-10.2, 6.4), (-9.2, 6.4), (-9.2, 4.7), (9.2, 4.7),
            (9.2, 6.8), (10.7, 6.8), (11.2, 6.2), (11.2, 0.0)]
    body = lathe_mesh(prof, seg=48, axis="Y", c=(X0, ZP), closed=False)
    # шплинт: шпилька из проволоки, проходит по Z через конец оси, ушко сверху
    r = 1.7
    pts = [(X0 - 0.55, -11.0, ZP - 6.5), (X0 - 0.55, -11.0, ZP + 6.0)]
    for k in range(1, 12):
        a = math.pi - math.pi * k / 11.0
        pts.append((X0 + r * math.cos(a) - r, -11.0, ZP + 6.0 + r * math.sin(a)))
    pts += [(X0 + 0.55, -11.0, ZP + 6.0), (X0 + 0.55, -11.0, ZP - 6.5)]
    cot = tube_mesh(np.array(pts), 0.5, seg=8)
    return join_meshes(body, cot)


def pin_hinge(side):
    def build(h):
        prof = [(-18.4, 0.0), (-18.4, 2.2), (-18.0, 2.6), (-17.0, 2.6), (-17.0, 4.2), (-16.4, 4.2), (-16.4, 2.6),
                (16.4, 2.6), (16.4, 4.4), (17.9, 4.4), (17.9, 0.0)]
        prof = [(X0 + a, r) for a, r in prof]      # ось X — координата абсолютная
        return lathe_mesh(prof, seg=36, axis="X", c=(side * YP, ZH), closed=False)
    return build


def _leg_world(side, y, z):
    """Мировая точка по местным (y наружу, z вниз по ноге) координатам ноги."""
    th = math.radians(side * DEPLOY)
    u = side * y
    return (X0, side * YP + u * math.cos(th) - z * math.sin(th), ZH + u * math.sin(th) + z * math.cos(th))


def spring(h):
    """Пружина-разжим: витая, на шпеньках внутренних сторон ног, ось вдоль Y; по краям поджатые витки."""
    zc = _leg_world(1, -8.0, -16.0)[2]
    y_end = _leg_world(1, -5.5, -16.0)[1] - 0.6
    wr = SPRING_W
    turns_dead = 1.4
    pitch = 2.3
    L = 2 * y_end
    ld = turns_dead * 2 * wr * 1.02
    live = max(1.0, (L - 2 * ld) / pitch)
    total = 2 * turns_dead + live
    n = int(total * 28) + 1
    P = []
    for i in range(n):
        t = i / (n - 1) * total
        if t < turns_dead:
            s = t / turns_dead * ld
        elif t > total - turns_dead:
            s = L - (total - t) / turns_dead * ld
        else:
            s = ld + (t - turns_dead) / live * (L - 2 * ld)
        a = 2 * math.pi * t
        P.append((X0 + SPRING_R * math.cos(a), -y_end + s, zc + SPRING_R * math.sin(a)))
    return tube_mesh(np.array(P), wr, seg=10)


def parts():
    zs = _leg_world(1, -8.0, -16.0)[2]
    motion_leg = ("шарнир: ось X через (%.2f, ±%.1f, %.2f); складывание у ноги относительно вилки — от DEPLOY к FOLD_SPLAY: "
                  "поворот вокруг этой оси на %.0f° внутрь (L: −%.0f°, R: +%.0f° от положения «разложено»)"
                  % (X0, YP, ZH, DEPLOY - FOLD_SPLAY, DEPLOY - FOLD_SPLAY, DEPLOY - FOLD_SPLAY))
    return [
        dict(name="Bipod_Pin", build=pin_fold, coll="Сошки", mat="Steel_phosphate", sharp=40, parent="Front_Sight_Base",
             pivot=[X0, 0.0, ZP], note="ось складывания, неподвижна на кронштейне основания мушки"),
        dict(name="Bipod_Yoke", build=yoke, h=0.12, coll="Сошки", mat="Steel_blued", parent="Front_Sight_Base",
             pivot=[X0, 0.0, ZP], adapt=0.1,
             motion="шарнир: ось Y через (%.2f, 0, %.2f); складывание сошек вокруг +Y на +%.0f° (ноги назад вдоль ствола)"
                    % (X0, ZP, FOLD_DEG)),
        dict(name="Bipod_Hinge_Pin_L", build=pin_hinge(1), coll="Сошки", mat="Steel_phosphate", sharp=40, parent="Bipod_Yoke",
             pivot=[X0, YP, ZH]),
        dict(name="Bipod_Hinge_Pin_R", build=pin_hinge(-1), coll="Сошки", mat="Steel_phosphate", sharp=40, parent="Bipod_Yoke",
             pivot=[X0, -YP, ZH]),
        dict(name="Bipod_Leg_L", build=leg(1), h=0.15, coll="Сошки", mat="Steel_blued", parent="Bipod_Yoke", adapt=0.1,
             pivot=[X0, YP, ZH], motion=motion_leg),
        dict(name="Bipod_Leg_R", build=leg(-1), h=0.15, coll="Сошки", mat="Steel_blued", parent="Bipod_Yoke", adapt=0.1,
             pivot=[X0, -YP, ZH], motion=motion_leg),
        dict(name="Bipod_Foot_L", build=foot(1), h=0.1, coll="Сошки", mat="Steel_blued", parent="Bipod_Leg_L",
             pivot=[X0, YT, ZT], motion="шарнир: ось X (параллельна оси ноги-вилки в разложенном виде); в разложенном виде подошва ровная, "
                                        "при складывании — вернуть подошву вдоль ноги (поворот на DEPLOY−FOLD_SPLAY наружу)"),
        dict(name="Bipod_Foot_R", build=foot(-1), h=0.1, coll="Сошки", mat="Steel_blued", parent="Bipod_Leg_R",
             pivot=[X0, -YT, ZT]),
        dict(name="Bipod_Spring", build=spring, coll="Сошки", mat="Spring_steel", sharp=60, parent="Bipod_Yoke",
             pivot=[X0, 0.0, zs], note="масштаб по Y — по расстоянию между шпеньками ног"),
    ]
