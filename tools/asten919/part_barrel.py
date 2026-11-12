# АСТЕН-919: ствол (штатный и удлинённый с резьбой M13,5×1 LH и защитной гайкой) и возвратный механизм с двумя
# пружинами (как у четвёртого поколения прототипа). Канал сквозной; патронник, скос
# подачи, нижний прилив с наклонным пазом — по снимкам разборки (ref_21, ref_27).
import math

import numpy as np

from dims import *
from sdf import *

LUG_HW = 4.3
ROD_X0, ROD_X1 = 24.2, 112.6          # направляющая: от прилива ствола до переднего торца «носа» затвора
SLEEVE_X0 = 66.0


def bb(x0, x1, y0, y1, z0, z1):
    return ((min(x0, x1), min(y0, y1), min(z0, z1)), (max(x0, x1), max(y0, y1), max(z0, z1)))


def bore(x0, x1):
    """Канал ствола — гладкий цилиндр по полям; нарезка мельче вокселя и остаётся текстурному этапу."""
    def f(X, Y, Z):
        d = np.hypot(Y, Z) - (BORE_R + 0.04)
        return np.maximum(d, np.maximum(x0 - X, X - x1))
    return f


def thread(x0, x1, r_major, pitch=1.0, depth=0.54, left=True, internal=False):
    """Резьба вдоль X: наружная (тело — внутри радиуса) или внутренняя (тело — снаружи)."""
    s = 1.0 if left else -1.0

    def f(X, Y, Z):
        rr = np.hypot(Y, Z)
        ph = X / pitch + s * np.arctan2(Z, Y) / (2 * math.pi)
        ph = ph - np.floor(ph)
        prof = depth * (1 - np.abs(2 * ph - 1))          # 0 у вершины витка, depth во впадине
        if internal:
            d = (r_major - depth + prof - rr) * 0.75
        else:
            d = (rr - (r_major - prof)) * 0.75
        return np.maximum(d, np.maximum(x0 - X, X - x1))
    return f


def lug_poly():
    return Poly(fillet_poly([(3.0, -6.5), (3.0, -12.5), (4.5, -15.6), (9.3, -15.6), (11.0, -12.6), (14.0, -11.2),
                             (16.0, -13.6), (17.6, -16.2), (23.8, -16.2), (26.5, -12.0), (26.5, -6.5)],
                            [0, 1.0, 1.0, 0.9, 1.0, 1.4, 1.0, 0.9, 1.0, 1.0, 0], seg=8))


def barrel_common(F, muzzle_x, tube_end=None):
    tube_end = muzzle_x if tube_end is None else tube_end
    # казённик: брус с небольшими фасками, верх — вровень с крышей затвора
    F.add(box_e((0.0, -BLOCK_HW, -8.0), (BLOCK_X1, BLOCK_HW, BLOCK_TOP), rx=0.7, ry=0.5, rz=0.7))
    F.apply(plane((0, BLOCK_HW, BLOCK_TOP - 1.3), (0, 1, 1)), "inter", 0.4, bbox=bb(-1, BLOCK_X1 + 1, 6, 10, 8, 11.5))
    F.apply(plane((0, -BLOCK_HW, BLOCK_TOP - 1.3), (0, -1, 1)), "inter", 0.4, bbox=bb(-1, BLOCK_X1 + 1, -10, -6, 8, 11.5))
    # труба
    F.add(cyl("X", (0, 0), BARREL_R, BLOCK_X1 - 4.0, tube_end), 1.2, bbox=bb(BLOCK_X1 - 5, BLOCK_X1 + 4, -9.5, 9.5, -9.5, 9.5))
    F.add(cyl("X", (0, 0), BARREL_R, BLOCK_X1 + 2, tube_end), 0.0, bbox=bb(BLOCK_X1 + 1, tube_end + 1, -8, 8, -8, 8))
    # нижний прилив с наклонным пазом
    F.add(prism(lug_poly(), "XZ", -LUG_HW, LUG_HW, rim=0.5), 0.8, bbox=bb(2, 28, -6, 6, -19, -5))
    # гнездо под пятку направляющей на передней грани прилива
    F.sub(cyl("X", (0, GUIDE_Z), 3.6, 24.2, 30.0, rim=0.6), 0.3, bbox=bb(23, 28, -5, 5, GUIDE_Z - 5, GUIDE_Z + 5))
    # задний торец ниже козырька отступает; скос подачи
    F.sub(box((-2.0, -20, -30), (1.9, 20, 4.4), 0.0), 0.3, bbox=bb(-1, 3, -10, 10, -19, 5.5))
    F.sub(capsule((3.6, 0, -1.4), (-5.5, 0, -10.5), 4.7), 0.3, bbox=bb(-1, 9, -6, 6, -12, 4))
    # низ казённика сзади подрезан: при отпирании он проходит над губками магазина
    F.sub(box_e((-3.0, -20, -30), (5.0, 20, -5.8), ry=2.0), 0.4, bbox=bb(-1, 8, -10, 10, -9.5, -4.5))
    # вырез под зацеп выбрасывателя справа
    F.sub(box((0.5, -BLOCK_HW - 2, -2.2), (3.6, -4.7, 2.2), 0.3), 0.25, bbox=bb(0, 4.5, -10, -4, -3, 3))
    # патронник, переходной конус, канал
    F.sub(cyl("X", (0, 0), CHAMBER_R, 1.0, 20.9), 0.25, bbox=bb(0, 22, -6, 6, -6, 6))
    F.sub(inter(cone("X", (0, 0), 20.5, CHAMBER_R, 23.0, BORE_R - 0.05), slab("X", 20.5, 23.2)), 0.0, bbox=bb(20, 24, -6, 6, -6, 6))
    F.sub(bore(20.0, muzzle_x + 2), 0.0, bbox=bb(19.5, muzzle_x + 1, -5, 5, -5, 5))


def hood_marks(F):
    """Номер и калибр на правой грани казённика (видны в окне выброса)."""
    ser, ws = text2(MARK_SERIAL, font_path(True), 1.9, track=0.12)
    engrave(F, ser, "XZ", (5.5, 4.6), 1, -BLOCK_HW, -1, depth=0.15, bbox=bb(5, 7 + ws, -BLOCK_HW - 1, -BLOCK_HW + 1, 3.5, 7.5))
    cal, wc = text2(MARK_CAL, font_path(True), 1.9, track=0.12)
    engrave(F, cal, "XZ", (5.5, 1.2), 1, -BLOCK_HW, -1, depth=0.15, bbox=bb(5, 7 + wc, -BLOCK_HW - 1, -BLOCK_HW + 1, 0.3, 4))


def barrel(h):
    F = Field("Barrel", (-0.8, -BLOCK_HW - 0.8, -18.8), (BARREL_LEN + 0.8, BLOCK_HW + 0.8, BLOCK_TOP + 0.8), h)
    # труба строится длиннее и обрезается плоскостью: совпадающие торцы со скруглением дают усадку
    barrel_common(F, BARREL_LEN, BARREL_LEN + 0.7)
    # дульный срез: скруглённая кромка и утопленная коронка
    F.apply(half("X", BARREL_LEN, 1), "inter", 0.7, bbox=bb(BARREL_LEN - 2, BARREL_LEN + 1, -8, 8, -8, 8))
    F.sub(cyl("X", (0, 0), 5.5, BARREL_LEN - 0.7, BARREL_LEN + 2), 0.3, bbox=bb(BARREL_LEN - 2, BARREL_LEN + 1, -7, 7, -7, 7))
    hood_marks(F)
    return F


def barrel_threaded(h):
    F = Field("Barrel_Threaded", (-0.8, -BLOCK_HW - 0.8, -18.8), (THREAD_LEN + 0.8, BLOCK_HW + 0.8, BLOCK_TOP + 0.8), h)
    barrel_common(F, THREAD_X0)
    # проточка у уступа и резьбовая часть
    F.add(cyl("X", (0, 0), THREAD_R - 0.6, THREAD_X0 - 1, THREAD_X0 + 1.2), 0.0, bbox=bb(THREAD_X0 - 1, THREAD_X0 + 2, -8, 8, -8, 8))
    F.add(inter(thread(THREAD_X0 + 1.0, THREAD_LEN, THREAD_R), cyl("X", (0, 0), THREAD_R + 0.1, THREAD_X0 + 1.0, THREAD_LEN, rim=0.6)),
          0.0, bbox=bb(THREAD_X0, THREAD_LEN + 1, -8, 8, -8, 8))
    F.sub(cyl("X", (0, 0), CHAMBER_R + 0.05, THREAD_LEN - 0.6, THREAD_LEN + 2), 0.25, bbox=bb(THREAD_LEN - 2, THREAD_LEN + 1, -7, 7, -7, 7))
    F.sub(bore(THREAD_X0 - 2, THREAD_LEN + 2), 0.0, bbox=bb(THREAD_X0 - 2, THREAD_LEN + 1, -5, 5, -5, 5))
    hood_marks(F)
    return F


def thread_protector(h):
    """Защитная гайка резьбы: кольцо Ø15,6 длиной 12 мм с прямой накаткой, внутри — резьба."""
    x0, x1 = THREAD_X0 + 0.15, THREAD_LEN + 0.6
    R = 7.8
    F = Field("Thread_Protector", (x0 - 0.6, -R - 0.6, -R - 0.6), (x1 + 0.6, R + 0.6, R + 0.6), h)
    F.add(cyl("X", (0, 0), R, x0, x1, rim=0.7))
    mid = slab("X", x0 + 1.8, x1 - 1.8)

    def knurl(X, Y, Z):
        # канавки накатки (36 по окружности, до 0,28 мм) в средней части кольца
        depth = np.clip(0.28 * (np.cos(36 * np.arctan2(Z, Y)) - 0.35) / 0.65, 0, 0.28)
        return np.maximum((R - depth) - np.hypot(Y, Z), mid(X, Y, Z))
    F.sub(knurl, 0.12)
    # внутренняя резьба: вычитаем «болт» чуть больше резьбы ствола
    F.sub(thread(x0 - 1, x1 + 1, THREAD_R + 0.08), 0.0)
    return F


def guide_rod(h):
    """Направляющая: стержень с пяткой, передняя втулка с головкой (головка видна в «носу» затвора)."""
    c = (0, GUIDE_Z)
    F = Field("Guide_Rod", (ROD_X0 - 0.6, -5.6, GUIDE_Z - 5.6), (ROD_X1 + 0.6, 5.6, GUIDE_Z + 5.6), h)
    F.add(cyl("X", c, 3.4, ROD_X0, 27.0, rim=0.8))
    F.add(cyl("X", c, 4.9, 26.6, 28.3, rim=0.4), 0.3)
    F.add(cyl("X", c, 2.1, 28.0, SLEEVE_X0 + 2), 0.4)
    F.add(cyl("X", c, 4.7, SLEEVE_X0, SLEEVE_X0 + 1.6, rim=0.4), 0.3)
    F.add(cyl("X", c, 3.6, SLEEVE_X0 + 1.2, 109.8), 0.4)
    F.add(cyl("X", c, 4.42, 109.4, ROD_X1, rim=0.3, rim1=0.9), 0.4)
    # углубление в торце головки
    F.sub(sphere((ROD_X1 + 5.2, c[0], c[1]), 5.6), 0.3, bbox=bb(ROD_X1 - 1.5, ROD_X1 + 1, -4, 4, GUIDE_Z - 4, GUIDE_Z + 4))
    return F


def spring_outer(h):
    return helix_mesh((0, GUIDE_Z), 4.75, 0.5, SLEEVE_X0 + 1.7, 109.3, 3.1, seg_turn=40, seg_wire=12)


def spring_inner(h):
    return helix_mesh((0, GUIDE_Z), 3.05, 0.45, 28.4, SLEEVE_X0 - 0.1, 2.5, seg_turn=36, seg_wire=12)


def parts():
    return [
        dict(name="Barrel", build=barrel, h=0.08, coll="Barrel", mat="Steel_nitride", weight=12, pivot=(0, 0, 0), adapt=0.05,
             motion=f"при отпирании: назад на {BARREL_BACK:g} мм и поворот вокруг оси Y на −{BARREL_TILT:g}° (казённик вниз) вокруг точки у отверстия затвора (X 67 мм)"),
        dict(name="Barrel_Threaded", build=barrel_threaded, h=0.08, coll="Barrel_Threaded", mat="Steel_nitride", weight=12, pivot=(0, 0, 0), adapt=0.05,
             coll_hidden=True, note="вариант: ствол с резьбой M13,5×1 LH; включается вместо Barrel"),
        dict(name="Thread_Protector", build=thread_protector, h=0.06, coll="Barrel_Threaded", mat="Steel_black", parent="Barrel_Threaded",
             coll_hidden=True, weight=3, pivot=(THREAD_X0, 0, 0)),
        dict(name="Guide_Rod", build=guide_rod, h=0.06, coll="Recoil_Spring", mat="Steel_black", weight=3),
        dict(name="Recoil_Spring_Outer", build=spring_outer, h=0.1, coll="Recoil_Spring", mat="Spring_steel", parent="Guide_Rod"),
        dict(name="Recoil_Spring_Inner", build=spring_inner, h=0.1, coll="Recoil_Spring", mat="Spring_steel", parent="Guide_Rod"),
    ]
