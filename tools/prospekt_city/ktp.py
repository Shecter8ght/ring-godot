"""Трансформаторная «Проспекта»: комплектная подстанция киоскового типа (набор ktp, 6 штук на карте).

Прообраз — городская КТПН 10/0,4 кВ мощностью до 250–400 кВА с кабельным вводом: корпус из оцинкованного листа
на сварной раме из швеллера, стоит на бетонном цоколе; двускатная крыша с выносом; спереди два отсека —
трансформаторный (широкие двери с жалюзи) и РУНН (щит 0,4 кВ); вентиляционные жалюзи в торцах; жёлтые знаки
«молния», табличка под диспетчерский номер; заземляющая полоса по раме, кабели — снизу в трубах.
Габарит набора 2,5 × 2,0 × 2,6 м: корпус 2,4 × 1,9, крыша с выносом 0,12 м, конёк на 2,58 м.

Оси: длина корпуса — Blender X, двери — к Blender −Y (игровое +Z). Начало координат — земля в центре.
Створки — на пустышках-шарнирах `Hinge_*` (поворот по Z открывает створку): вариант «Двери открыты».
"""
from __future__ import annotations

import math

import numpy as np

import clib as C

W, D = 2.40, 1.90                  # корпус
X0, X1 = -W / 2, W / 2
YF, YB = -D / 2, D / 2              # лицо (двери) и тыл
Z_PL = 0.15                         # верх бетонного цоколя
Z_FR = 0.28                         # верх рамы из швеллера = пол
Z_EAVE = 2.20                       # верх стен
Z_RIDGE = 2.58
OVH = 0.12                          # вынос крыши
T_WALL = 0.025                      # стена: лист 2 мм + каркас — одной толщиной
BAYS = [(-1.13, 0.06), (0.16, 1.13)]   # проёмы отсеков: трансформатор, РУНН
Z_D0, Z_D1 = Z_FR + 0.03, 2.12          # проём двери по высоте


def plinth(mb: C.MB) -> None:
    """Бетонный цоколь (лента из блоков) и рама из швеллера 160 по периметру."""
    mb.extend(C.box((0, 0, Z_PL / 2 - 0.15), (W + 0.16, D + 0.16, Z_PL + 0.30)), "concrete")


def base_frame(mb: C.MB) -> None:
    prof = C.channel_profile(Z_FR - Z_PL, 0.064, 0.006)
    zc = (Z_PL + Z_FR) / 2
    # продольные (вдоль X) — полками внутрь
    for y, sgn in ((YF, 1), (YB, -1)):
        V, F = C.prism(prof, X0, X1, origin=(0, y, zc), ex=(0, sgn, 0), ey=(0, 0, 1), ez=(1, 0, 0))
        mb.add(V, F, "steel_dark")
    for x, sgn in ((X0, 1), (X1, -1)):
        V, F = C.prism(prof, YF + 0.065, YB - 0.065, origin=(x, 0, zc), ex=(sgn, 0, 0), ey=(0, 0, 1), ez=(0, 1, 0))
        mb.add(V, F, "steel_dark")


def ground_strip(mb: C.MB) -> None:
    """Заземление: полоса 40×4 по раме снаружи, болт заземления со знаком, отвод в землю."""
    z = Z_PL + 0.05
    for y in (YF - 0.004, YB + 0.004):
        mb.extend(C.box((0, y, z), (W - 0.1, 0.004, 0.04)), "steel")
    for x in (X0 - 0.004, X1 + 0.004):
        mb.extend(C.box((x, 0, z), (0.004, D - 0.1, 0.04)), "steel")
    # отвод в землю у левого заднего угла
    mb.extend(C.box((X0 - 0.004, YB - 0.30, (z - 0.02) / 2 - 0.05), (0.004, 0.04, z + 0.06)), "steel")
    # болт заземления на раме спереди справа + табличка «земля»
    mb.extend(C.cyl((X1 - 0.18, YF - 0.012, z + 0.06), 0.012, 0.02, 6, "y"), "galv")
    mb.extend(C.box((X1 - 0.18, YF - 0.006, z + 0.13), (0.06, 0.003, 0.06)), "paint_black")


def shell(mb: C.MB) -> None:
    """Стены: торцы, тыл, лицо с двумя проёмами; уголки по рёбрам; отбортовки-рёбра жёсткости."""
    t = T_WALL
    zc, h = (Z_FR + Z_EAVE) / 2, Z_EAVE - Z_FR
    mb.extend(C.box((0, YB - t / 2, zc), (W, t, h)), "galv")                    # тыл
    for x in (X0 + t / 2, X1 - t / 2):                                           # торцы с жалюзи — дыры ниже
        mb.extend(C.box((x, 0, zc), (t, D - 2 * t, h)), "galv")
    # лицо: стойки между проёмами, перемычка и порог
    edges = [X0] + [v for b in BAYS for v in b] + [X1]
    for k in range(0, len(edges), 2):
        a, b = edges[k], edges[k + 1]
        mb.extend(C.box(((a + b) / 2, YF + t / 2, zc), (b - a, t, h)), "galv")
    mb.extend(C.box((0, YF + t / 2, (Z_D1 + Z_EAVE) / 2), (W, t, Z_EAVE - Z_D1)), "galv")
    mb.extend(C.box((0, YF + t / 2, (Z_FR + Z_D0) / 2), (W, t, Z_D0 - Z_FR)), "galv")
    # уголки 50×4 по вертикальным рёбрам корпуса
    prof = C.angle_profile(0.05, 0.004)
    for (x, y, ex, ey) in ((X0, YF, (1, 0, 0), (0, 1, 0)), (X1, YF, (0, 1, 0), (-1, 0, 0)),
                           (X1, YB, (-1, 0, 0), (0, -1, 0)), (X0, YB, (0, -1, 0), (1, 0, 0))):
        o = np.array([x, y, 0]) - np.array(ex) * 0.004 - np.array(ey) * 0.004
        V, F = C.prism(prof, Z_FR, Z_EAVE + 0.02, origin=o, ex=ex, ey=ey, ez=(0, 0, 1))
        mb.add(V, F, "galv")
    # гнутые рёбра жёсткости на тылу и торцах (вертикальные «зиги»)
    for x in np.linspace(X0 + 0.4, X1 - 0.4, 4):
        mb.extend(C.box((x, YB + 0.006, zc), (0.05, 0.012, h - 0.12)), "galv")
    for x in (X0 - 0.006, X1 + 0.006):
        for y in (-0.45, 0.45):
            mb.extend(C.box((x, y, zc + 0.35), (0.012, 0.05, h - 0.9)), "galv")
    # обрамление проёмов (П-образный отгиб)
    for (a, b) in BAYS:
        for x in (a, b):
            mb.extend(C.box((x, YF - 0.006, (Z_D0 + Z_D1) / 2), (0.03, 0.012, Z_D1 - Z_D0 + 0.03)), "galv")
        mb.extend(C.box(((a + b) / 2, YF - 0.006, Z_D1 + 0.015), (b - a + 0.03, 0.012, 0.03)), "galv")
    # пол из рифлёного листа
    mb.extend(C.box((0, 0, Z_FR - 0.004), (W - 2 * t, D - 2 * t, 0.008)), "steel")


def louvre(mb: C.MB, c, w: float, h: float, axis: str = "y", n: int | None = None, m: str = "galv") -> None:
    """Жалюзийная решётка: рамка 30 мм и наклонные ламели (45°) за ней. axis — куда смотрит решётка."""
    c = np.asarray(c, float)
    n = n or max(3, int(h / 0.045))
    if axis == "y":
        sgn = 1 if c[1] > 0 else -1
        e_w, e_n = np.array([1.0, 0, 0]), np.array([0, sgn, 0.0])
    else:
        sgn = 1 if c[0] > 0 else -1
        e_w, e_n = np.array([0, 1.0, 0]), np.array([sgn, 0, 0.0])
    up = np.array([0, 0, 1.0])
    fr = 0.03
    for s in (-1, 1):
        mb.extend(C.box(c + e_w * s * (w / 2 - fr / 2) + e_n * 0.008, np.abs(e_w * fr + e_n * 0.016 + up * h)), m)
        mb.extend(C.box(c + up * s * (h / 2 - fr / 2) + e_n * 0.008, np.abs(e_w * w + e_n * 0.016 + up * fr)), m)
    pitch = (h - 2 * fr) / n
    for k in range(n):
        zc = -h / 2 + fr + pitch * (k + 0.5)
        V, F = C.box((0, 0, 0), (w - 2 * fr, 0.045, 0.0015))
        R = np.stack([e_w, e_n, up], axis=1) @ C.rot("x", -40.0 if True else 40.0)
        mb.add(C.xf(V, R, c + up * zc + e_n * 0.004), F, m)
    # тёмная сетка за ламелями (противомышиная)
    mb.extend(C.box(c + e_n * 0.0015, np.abs(e_w * (w - 2 * fr) + e_n * 0.002 + up * (h - 2 * fr))), "steel_dark")


def roof(mb: C.MB) -> None:
    """Двускатная крыша: два ската из листа 50 мм с выносом, конёк, капельники; щипцы-треугольники в торцах."""
    ye = D / 2 + OVH
    zs = Z_EAVE - 0.02
    for s in (-1, 1):
        # скат: четырёхугольник от карниза до конька, толщина 0,05
        p = [(X0 - OVH, s * ye, zs), (X1 + OVH, s * ye, zs), (X1 + OVH, 0.0, Z_RIDGE), (X0 - OVH, 0.0, Z_RIDGE)]
        P = np.array(p)
        V = np.vstack([P, P + np.array([0, 0, 0.05])])
        F = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
        mb.add(V, F, "galv")
        # капельник по карнизу
        mb.extend(C.box((0, s * (ye + 0.005), zs - 0.02), (W + 2 * OVH, 0.01, 0.06)), "galv")
        # фальцы по скату (стоячие)
        for x in np.linspace(X0 - OVH + 0.25, X1 + OVH - 0.25, 6):
            a = np.array([x, s * (ye - 0.02), zs + 0.06])
            b = np.array([x, 0.0, Z_RIDGE + 0.06])
            V, F = C.sweep(C.rect_profile(0.012, 0.025), np.array([a, b]), up=(0, 0, 1))
            mb.add(V, F, "galv")
    # конёк
    V, F = C.sweep(np.array([(-0.09, -0.02), (0.0, 0.035), (0.09, -0.02), (0.07, -0.025), (0.0, 0.02), (-0.07, -0.025)]),
                   np.array([(X0 - OVH - 0.01, 0, Z_RIDGE + 0.055), (X1 + OVH + 0.01, 0, Z_RIDGE + 0.055)]), up=(0, 0, 1))
    mb.add(V, F, "galv")
    # щипцы (фронтоны) — закрыты листом, в них жалюзи ниже
    for x in (X0 + 0.01, X1 - 0.01):
        tri = [(YF, Z_EAVE), (YB, Z_EAVE), (0.0, Z_RIDGE - 0.02)]
        V, F = C.prism(tri, x - 0.01, x + 0.01, ex=(0, 1, 0), ey=(0, 0, 1), ez=(1, 0, 0))
        mb.add(V, F, "galv")


def door_leaf(mb: C.MB, det: C.MB, w: float, h: float, side: int, louvres: bool, lock: bool) -> None:
    """Створка в координатах шарнира: от петли по +X·side, толщина 40 мм, лицо к −Y; петли, рёбра, ручка."""
    t = 0.04
    x0, x1 = (0.008, w) if side > 0 else (-w, -0.008)
    xc = (x0 + x1) / 2
    # полотно: лист с отбортовкой — коробка с фаской + утопленная филёнка изнутри не нужна
    mb.extend(C.box((xc, 0.0, (Z_D0 + Z_D0 + h) / 2), (x1 - x0, t, h)), "galv")
    zt = Z_D0 + h
    # рёбра жёсткости (отбортовка) по наружной стороне
    for z in (Z_D0 + h * 0.36, Z_D0 + h * 0.66):
        mb.extend(C.box((xc, -t / 2 - 0.006, z), (x1 - x0 - 0.12, 0.012, 0.04)), "galv")
    if louvres:
        louvre(det, (xc, -t / 2 - 0.001, Z_D0 + 0.30), x1 - x0 - 0.16, 0.36, "y", 8)
        louvre(det, (xc, -t / 2 - 0.001, zt - 0.28), x1 - x0 - 0.16, 0.28, "y", 6)
    # петли: три накладные с осью (у кромки на шарнире)
    for z in (Z_D0 + 0.18, Z_D0 + h / 2, zt - 0.18):
        mb.extend(C.cyl((0.0, -t / 2 - 0.010, z), 0.010, 0.09, 12, "z"), "steel")
        mb.extend(C.box((side * 0.04, -t / 2 - 0.004, z), (0.07, 0.008, 0.05)), "steel")
    # уплотнитель по контуру (видно при открытой створке)
    for s in (-1, 1):
        det.extend(C.box((xc, t / 2 + 0.004, (Z_D0 + zt) / 2 + s * (h / 2 - 0.02)), (x1 - x0 - 0.04, 0.008, 0.02)), "rubber")
    if lock:
        # поворотная ручка-замок под ключ на свободной кромке, засов вверх/вниз
        xl = x1 - 0.07 if side > 0 else x0 + 0.07
        zl = Z_D0 + h * 0.5
        mb.extend(C.box((xl, -t / 2 - 0.006, zl), (0.05, 0.012, 0.16)), "steel_dark")
        mb.extend(C.box((xl, -t / 2 - 0.022, zl + 0.03), (0.022, 0.03, 0.10)), "steel_dark")
        mb.extend(C.cyl((xl, -t / 2 - 0.014, zl - 0.055), 0.011, 0.012, 10, "y"), "steel")
        for zz in (zl + 0.20, zl - 0.20):                                      # проушины под навесной замок
            det.extend(C.box((xl, -t / 2 - 0.02, zz), (0.006, 0.04, 0.05)), "steel")
    # знак «молния» на верхней части створки
    if lock or louvres:
        zs = Z_D0 + h * (0.47 if louvres else 0.80)          # на створках с жалюзи — между рёбрами
        tri = np.array([(-0.14, 0.0), (0.14, 0.0), (0.0, 0.24)])
        V, F = C.prism(tri, 0.0, 0.0015, origin=(xc, -t / 2 - 0.0005, zs), ex=(1, 0, 0), ey=(0, 0, 1), ez=(0, -1, 0))
        det.add(V, F, "paint_yellow")
        bolt = np.array([(-0.006, 0.17), (0.03, 0.10), (0.005, 0.10), (0.02, 0.03), (-0.03, 0.12), (-0.005, 0.12),
                         (-0.02, 0.19)])
        V, F = C.prism(bolt, 0.0015, 0.0025, origin=(xc, -t / 2 - 0.0005, zs), ex=(1, 0, 0), ey=(0, 0, 1), ez=(0, -1, 0))
        det.add(V, F, "paint_black")


def doors(col, parent, open_: bool) -> None:
    h = Z_D1 - Z_D0 - 0.01
    yh = YF - 0.026
    for bi, (a, b) in enumerate(BAYS):
        w = (b - a) / 2 - 0.004
        for side, xh, ang in ((1, a, -100.0 if bi == 0 else -96.0), (-1, b, 104.0 if bi == 0 else 92.0)):
            name = f"Hinge_{'T' if bi == 0 else 'N'}{'L' if side > 0 else 'R'}"
            pv = C.pivot(name, col, parent, (xh, yh, 0.0), (0, 0, math.radians(ang) if open_ else 0.0))
            mb, det = C.MB(), C.MB()
            door_leaf(mb, det, w, h, side, louvres=(bi == 0), lock=(side < 0))
            mb.build(f"KTP_Door_{name[6:]}", col, pv, bevel=0.003, seg=1)
            det.build(f"KTP_DoorDetails_{name[6:]}", col, pv)


def side_louvres(mb: C.MB) -> None:
    for x in (X0, X1):
        sgn = -1 if x < 0 else 1
        louvre(mb, (x + sgn * 0.001, -0.35, Z_FR + 0.45), 0.55, 0.40, "x", 9)
        louvre(mb, (x + sgn * 0.001, -0.35, Z_EAVE - 0.35), 0.55, 0.36, "x", 8)
        louvre(mb, (x + sgn * 0.006, 0.0, (Z_EAVE + Z_RIDGE) / 2 - 0.04), 0.50, 0.18, "x", 4)   # в щипце
    # табличка под диспетчерский номер на правом торце и на лице над РУНН
    mb.extend(C.box((X1 + 0.004, 0.35, 1.65), (0.003, 0.42, 0.22)), "paint_white")
    mb.extend(C.box(((BAYS[1][0] + BAYS[1][1]) / 2, YF - 0.004, Z_D1 + 0.035), (0.36, 0.003, 0.05)), "paint_white")
    # знак «молния» на правом торце
    tri = np.array([(-0.16, 0.0), (0.16, 0.0), (0.0, 0.28)])
    V, F = C.prism(tri, 0.0, 0.0015, origin=(X1 + 0.002, 0.35, 1.18), ex=(0, -1, 0), ey=(0, 0, 1), ez=(1, 0, 0))
    mb.add(V, F, "paint_yellow")


def cables(mb: C.MB) -> None:
    """Кабельные вводы: три трубы снизу у тыла уходят в землю под цоколь, на трубах — заделка."""
    for k, x in enumerate((-0.55, -0.25, 0.45)):
        r = 0.055 if k < 2 else 0.065
        mb.extend(C.cyl((x, YB - 0.25, Z_PL - 0.06), r, 0.36, 16), "plastic_dark")
        mb.extend(C.cyl((x, YB - 0.25, Z_PL + 0.13), r * 0.7, 0.04, 12), "rubber")


# ---------------------------------------------------------------- нутро (вариант «Двери открыты»)
def transformer(mb: C.MB) -> None:
    """Масляный трансформатор в гофробаке (≈ ТМГ 250 кВА): бак 1,05 × 0,72 × 0,95, гофры по длинным сторонам,
    крышка с тремя вводами ВН и четырьмя НН, катки на швеллерах, пробки и бирка."""
    xc, yc = (BAYS[0][0] + BAYS[0][1]) / 2, 0.10
    z0 = Z_FR + 0.12
    bw, bd, bh = 0.82, 0.48, 0.92
    mb.extend(C.box((xc, yc, z0 + bh / 2), (bw, bd, bh)), "paint_grey")
    # гофры: тонкие рёбра 3 мм, глубина 0,13, шаг 45 мм — по длинным сторонам
    for s in (-1, 1):
        for x in np.arange(xc - bw / 2 + 0.04, xc + bw / 2 - 0.03, 0.045):
            mb.extend(C.box((x, yc + s * (bd / 2 + 0.065), z0 + bh / 2 - 0.02), (0.004, 0.13, bh - 0.12)), "paint_grey")
    for s in (-1, 1):
        for y in np.arange(yc - bd / 2 + 0.05, yc + bd / 2 - 0.04, 0.045):
            mb.extend(C.box((xc + s * (bw / 2 + 0.05), y, z0 + bh / 2 - 0.02), (0.10, 0.004, bh - 0.12)), "paint_grey")
    # крышка с бортом
    mb.extend(C.box((xc, yc, z0 + bh + 0.02), (bw + 0.24, bd + 0.30, 0.04)), "paint_grey")
    # основание-салазки и катки
    for y in (yc - 0.22, yc + 0.22):
        mb.extend(C.box((xc, y, z0 - 0.06), (bw + 0.1, 0.08, 0.10)), "steel_dark")
        for x in (xc - 0.38, xc + 0.38):
            mb.extend(C.cyl((x, y, Z_FR + 0.055), 0.055, 0.05, 16, "y"), "steel_dark")
    # вводы ВН (фарфор, рёбра) — сзади, НН — спереди
    zt = z0 + bh + 0.04
    prof_hv = [(0.05, 0.0), (0.05, 0.03), (0.07, 0.04), (0.04, 0.07), (0.065, 0.10), (0.035, 0.13), (0.06, 0.16),
               (0.03, 0.19), (0.05, 0.22), (0.025, 0.25), (0.025, 0.30), (0.008, 0.30), (0.008, 0.36)]
    for k in (-1, 0, 1):
        V, F = C.lathe(prof_hv, 20, center=(xc + k * 0.22, yc + 0.14, zt))
        mb.add(V, F, "porcelain")
    prof_lv = [(0.035, 0.0), (0.035, 0.03), (0.05, 0.04), (0.03, 0.07), (0.045, 0.09), (0.025, 0.12),
               (0.025, 0.14), (0.012, 0.14), (0.012, 0.22)]
    for k in range(4):
        V, F = C.lathe(prof_lv, 16, center=(xc - 0.27 + k * 0.18, yc - 0.17, zt))
        mb.add(V, F, "porcelain")
    # шины НН от вводов вниз к щиту — медные полосы
    for k in range(4):
        x = xc - 0.27 + k * 0.18
        P = np.array([(x, yc - 0.17, zt + 0.21), (x, yc - 0.17, zt + 0.33), (BAYS[0][1] - 0.05, yc - 0.17 + k * 0.03,
                                                                              zt + 0.33)])
        V, F = C.sweep(C.rect_profile(0.04, 0.005), P, up=(0, 0, 1))
        mb.add(V, F, "rust")
    # пробка заливки, бирка, болт заземления бака
    mb.extend(C.cyl((xc + 0.30, yc - 0.05, zt + 0.03), 0.03, 0.06, 12), "steel")
    mb.extend(C.box((xc, yc - bd / 2 - 0.004, z0 + bh - 0.2), (0.16, 0.004, 0.10)), "galv")


def lv_panel(mb: C.MB) -> None:
    """РУНН: щит на всю высоту отсека — панели с рубильниками, автоматами, счётчиком, шинами наверху."""
    a, b = BAYS[1]
    xc = (a + b) / 2
    y_face = YF + 0.30
    w = b - a - 0.06
    z0, z1 = Z_FR + 0.05, Z_EAVE - 0.12
    mb.extend(C.box((xc, y_face + 0.20, (z0 + z1) / 2), (w, 0.40, z1 - z0)), "paint_grey")
    # перегородка между отсеками
    mb.extend(C.box((BAYS[0][1] + 0.05, 0.0, (Z_FR + Z_EAVE) / 2), (0.02, D - 0.06, Z_EAVE - Z_FR)), "galv")
    # рубильники (рукоятки) — ряд сверху
    for k in range(3):
        x = a + 0.18 + k * 0.30
        mb.extend(C.box((x, y_face - 0.015, 1.72), (0.18, 0.03, 0.24)), "plastic_dark")
        P = np.array([(x, y_face - 0.03, 1.66), (x, y_face - 0.20, 1.78)])
        mb.extend(C.tube(P, 0.012, 8), "steel")
        mb.extend(C.cyl((x, y_face - 0.22, 1.795), 0.022, 0.07, 10, "x"), "paint_red")
    # автоматы на DIN-рейках, два ряда
    for zr in (1.30, 1.05):
        mb.extend(C.box((xc, y_face - 0.006, zr), (w - 0.1, 0.012, 0.035)), "galv")
        for k in range(8):
            mb.extend(C.box((a + 0.12 + k * 0.095, y_face - 0.04, zr), (0.075, 0.07, 0.17)), "porcelain_white")
            mb.extend(C.box((a + 0.12 + k * 0.095, y_face - 0.08, zr + 0.02), (0.02, 0.02, 0.03)), "plastic_dark")
    # счётчик и трансформаторы тока
    mb.extend(C.box((xc + 0.22, y_face - 0.05, 0.72), (0.18, 0.10, 0.28)), "porcelain_white")
    mb.extend(C.box((xc + 0.22, y_face - 0.101, 0.76), (0.12, 0.002, 0.06)), "glass")
    for k in range(3):
        mb.extend(C.cyl((a + 0.18 + k * 0.16, y_face - 0.06, 0.70), 0.06, 0.06, 16, "y"), "plastic_dark")
    # шины наверху щита
    for k in range(4):
        mb.extend(C.box((xc, y_face + 0.02 + k * 0.05, z1 - 0.07), (w - 0.04, 0.006, 0.05)), "rust")
    # кабели вниз в пол
    for k in range(3):
        P = np.array([(a + 0.2 + k * 0.25, y_face - 0.05, 0.55), (a + 0.2 + k * 0.25, y_face - 0.05, Z_FR + 0.10),
                      (a + 0.2 + k * 0.25, y_face + 0.15, Z_FR - 0.02)])
        mb.extend(C.tube(P, 0.025, 10), "rubber")


def hv_side(mb: C.MB) -> None:
    """В трансформаторном отсеке у стены — выключатель нагрузки ВН с приводом и кабельные муфты."""
    x = BAYS[0][0] + 0.12
    mb.extend(C.box((x, 0.55, 1.40), (0.16, 0.50, 0.90)), "paint_grey")
    mb.extend(C.box((x + 0.085, 0.45, 1.25), (0.01, 0.10, 0.18)), "steel_dark")
    P = np.array([(x + 0.09, 0.45, 1.22), (x + 0.30, 0.45, 1.10)])
    mb.extend(C.tube(P, 0.012, 8), "steel")
    for k in range(3):
        mb.extend(C.cyl((x, 0.38 + k * 0.17, 0.80), 0.04, 0.40, 12), "rubber")


# ---------------------------------------------------------------- сборка
def kiosk(col, parent, open_: bool) -> None:
    pl = C.MB()
    plinth(pl)
    pl.build("KTP_Plinth", col, parent, bevel=0.012, seg=2)
    fr = C.MB()
    base_frame(fr)
    ground_strip(fr)
    cables(fr)
    fr.build("KTP_Frame", col, parent, bevel=0.0012, seg=1)
    sh = C.MB()
    shell(sh)
    sh.build("KTP_Shell", col, parent, bevel=0.0015, seg=1)
    lv = C.MB()
    side_louvres(lv)
    lv.build("KTP_Louvres", col, parent)
    rf = C.MB()
    roof(rf)
    rf.build("KTP_Roof", col, parent, bevel=0.004, seg=1)
    doors(col, parent, open_)
    inner = C.MB()
    transformer(inner)
    lv_panel(inner)
    hv_side(inner)
    inner.build("KTP_Inside", col, parent, bevel=0.003, seg=1)


VARIANTS = {"closed": "Закрыта", "open": "Двери открыты"}
STEP = 4.5
META = {
    "folder": "КТП", "name": "KTP_Kiosk", "title": "Трансформаторная подстанция киоскового типа",
    "step": 4.5,
    "shots": [["3/4 спереди", [3.4, -4.4, 2.4], [0.0, 0.0, 1.2], 32], ["3/4 сзади", [-3.6, 4.2, 2.6], [0.0, 0.0, 1.2], 32],
              ["двери и знаки крупно", [1.6, -2.2, 1.6], [0.2, -0.9, 1.3], 35]],
    "shots_by": {
        "open": [["3/4 спереди", [3.2, -4.6, 2.3], [0.0, 0.0, 1.2], 32], ["нутро: трансформатор", [-0.9, -2.6, 2.0], [-0.55, 0.1, 1.1], 30],
                 ["нутро: щит РУНН", [1.1, -2.3, 1.6], [0.65, -0.3, 1.2], 30]],
    },
}


def build(keys: list[str]) -> dict:
    out = {}
    for i, k in enumerate(keys):
        name = VARIANTS[k]
        col = C.collection(name)
        r = C.root(f"KTP | {name}", col, (i * STEP, 0.0, 0.0))
        kiosk(col, r, k == "open")
        out[k] = name
    return out
