# АСТЕН-919: органы управления — затворная задержка, защёлка затвора (для разборки), защёлка магазина, спусковой
# крючок с автоматическим предохранителем, оси. Места и размеры — снимок ref_23 (сетка 5 мм), формы — ref_11, ref_16.
# У каждой детали начало координат — её ось или опорная точка; ход записан в свойстве «motion» объекта.
import math

import numpy as np

from dims import *
from sdf import *
from part_frame import catch_rect, catch_frame, catch_shank_center, CATCH_HEAD



def bb(x0, x1, y0, y1, z0, z1):
    return ((min(x0, x1), min(y0, y1), min(z0, z1)), (max(x0, x1), max(y0, y1), max(z0, z1)))


# ---------- затворная задержка ----------

def slide_stop(h):
    """Штампованный рычаг 1,5 мм слева: проушина на оси спуска, плечо внутри стенки рамки, полка под выступ подавателя
    магазина, отогнутая наружу площадка с четырьмя рёбрами под большой палец; над площадкой — зуб, который при
    подъёме рычага входит в вырез левого борта затвора (виден снаружи, как у прототипа)."""
    px, pz = PIN_TRIGGER
    (x0, x1), (z0, z1) = STOP_PAD
    F = Field("Slide_Stop", (-25.5, 5.6, -25.2), (15.2, 16.0, -9.4), h)
    arm = union2(circle2((px, pz), 3.4), seg2((px, pz), (1.0, -14.5), 1.7), rect2(-22.8, 2.5, -15.6, -13.5, 1.0), r=1.2)
    arm = minus2(arm, circle2((px, pz), 2.05), 0.0)
    F.add(prism2(arm, "XZ", 10.05, 11.55, rim=0.3))
    # полка под выступ подавателя (отгиб внутрь, перед передней стенкой магазина, над вкладышем)
    F.add(box((2.3, 6.6, -12.3), (6.0, 10.9, -11.0), 0.4), 0.0, bbox=bb(1, 7.5, 5.6, 12.5, -13.5, -10))
    F.add(box((2.6, 10.05, -14.5), (5.7, 11.55, -11.0), 0.3), 0.3, bbox=bb(1.5, 7, 9.5, 12, -15.5, -10.5))
    # перемычка к площадке (отгиб наружу сквозь окно рамки)
    F.add(box((x0 + 0.3, 11.0, -15.3), (x1 - 0.5, 13.9, -13.1), 0.5), 0.6, bbox=bb(x0 - 1, x1 + 1, 10, 15, -16.8, -11.5))
    # зуб под вырез затвора: продолжение перемычки вверх, в плоскости левого борта затвора
    tx0, tx1 = STOP_TOOTH_X
    tooth = Poly(fillet_poly([(tx0, -14.0), (tx0, -10.35), (tx1, -10.35), (tx1 + 0.9, -14.0)], [0, 0.45, 0.7, 0]))
    F.add(prism(tooth, "XZ", 11.1, 12.95, rim=0.3), 0.6, bbox=bb(tx0 - 1.5, tx1 + 2.5, 10.5, 13.6, -15, -9.6))
    # площадка и рёбра
    F.add(prism2(rect2(x0, x1, z0, z1, 1.6), "XZ", 13.3, 14.7, rim=0.45), 0.5, bbox=bb(x0 - 1, x1 + 1, 12, 16, z0 - 1, z1 + 1))
    for k in range(4):
        zc = z0 + 1.0 + k * 1.45
        F.add(box((x0 + 0.9, 14.3, zc - 0.42), (x1 - 0.9, 15.15, zc + 0.42), 0.3), 0.2, bbox=bb(x0, x1, 13.8, 16, zc - 1.2, zc + 1.2))
    return F


# ---------- защёлка затвора ----------

def slide_lock(h):
    """Поперечная планка 2,2 × 8,6 мм сквозь рамку, наклон 15°; концы с рифлением выступают в лунки рамки."""
    lx, lz = LOCK_C
    F = Field("Slide_Lock", (lx - 4.2, -15.0, lz - 5.8), (lx + 4.2, 15.0, lz + 5.8), h)

    def bar(X, Y, Z):
        d = box((lx - 1.1, -14.3, lz - 4.3), (lx + 1.1, 14.3, lz + 4.3), 0.4)(X, Y, Z)
        # вырез посередине сверху (место прохода прилива ствола)
        d = cut(d, box_e((lx - 3, -5.3, lz - 1.6), (lx + 3, 5.3, lz + 8), rx=1.2)(X, Y, Z), 0.3)
        # рифление концов: по три канавки на передней и задней гранях
        for zc in (-2.5, 0.0, 2.5):
            for sx in (-1, 1):
                g = box((lx + sx * 0.72, 11.3, lz + zc - 0.45), (lx + sx * 3, 20, lz + zc + 0.45), 0.2)
                d = cut(d, np.minimum(g(X, Y, Z), g(X, -Y, Z)), 0.12)
        return d
    F.add(rot(bar, "Y", (lx, 0, lz), LOCK_DEG))
    return F


# ---------- защёлка магазина ----------

def mag_catch(h):
    """Кнопка 12,9 × 10,6 мм с продольным рифлением слева (переставляется на правую сторону), перекладина перед
    магазином, зацеп входит в правый вырез магазина; нажатие сдвигает деталь вправо на 2,5 мм."""
    cx, cz = CATCH_C
    sx, sz = catch_shank_center()
    ax, pr = catch_frame()
    F = Field("Mag_Catch", (cx - 9.5, -14.4, cz - 9.0), (sx + 4.5, 18.0, cz + 9.0), h)
    head = catch_rect(cx, cz, CATCH_HEAD[1], CATCH_HEAD[0], 1.4)
    shank = catch_rect(sx, sz, 2.6, 2.0, 0.5)
    # перекладина слева кончается под наружной стенкой рамки; к кнопке от её заднего края идёт короткая перемычка
    # в закрытом канале стенки (при нажатии перемычка уходит в левый вырез магазина)
    bridge = catch_rect(sx - 2.75, sz, 2.0, 1.75, 0.4)
    F.add(prism2(shank, "XZ", -13.6, 11.3, rim=0.4))
    F.add(prism2(bridge, "XZ", 11.0, 13.2, rim=0.3), 0.0)
    # стойка под передним краем кнопки: соединяет перемычку с кнопкой
    post = lambda U, V: np.maximum(bridge(U, V), catch_rect(cx, cz, CATCH_HEAD[1] - 0.6, CATCH_HEAD[0] - 0.3, 0.8)(U, V))
    F.add(prism2(post, "XZ", 11.0, 14.8, rim=0.25), 0.0)
    F.add(prism2(head, "XZ", 14.4, 16.9, rim=0.75), 0.4)
    # рифление кнопки: канавки вдоль рукояти
    for k in range(8):
        w = -5.1 + k * 1.46
        gx, gz = cx + pr[0] * w, cz + pr[1] * w
        g = catch_rect(gx, gz, CATCH_HEAD[1] - 0.9, 0.33, 0.3)
        F.sub(lambda X, Y, Z, g=g: np.maximum(g(X, Z), 16.45 - Y), 0.15,
              bbox=bb(gx - 6, gx + 6, 16.3, 18, gz - 6, gz + 6))
    # зацеп на задней грани перекладины — под правый вырез магазина
    lx_, lz_ = sx + pr[0] * 2.7, sz + pr[1] * 2.7
    ledge = catch_rect(lx_, lz_, 2.1, 0.85, 0.3)
    F.add(prism2(ledge, "XZ", -11.3, -9.4, rim=0.3), 0.3, bbox=bb(lx_ - 4, lx_ + 4, -12.5, -8, lz_ - 4, lz_ + 4))
    # паз под проволочную пружину снизу перекладины
    F.sub(box((sx - 0.5, -1.2, sz - 6), (sx + 0.5, 1.2, sz - 1.2), 0.2), 0.15, bbox=bb(sx - 2, sx + 2, -2.5, 2.5, sz - 5, sz))
    return F


# ---------- спусковой крючок ----------
# Контуры — во взведённом положении (палец не давит), снимок ref_11: широкий верх с «плавником» сзади, перо загнуто
# вперёд; координаты сняты по проёму скобы (его передняя и задняя стенки — общие с ref_23).

TRIGGER_READY = [(12.6, -27.5), (12.2, -30.5), (11.7, -34.0), (12.0, -38.0), (13.4, -41.5), (15.6, -45.0), (17.6, -48.0),
                 (18.6, -50.0), (17.6, -50.7), (15.2, -49.6), (12.2, -48.0), (8.9, -45.6), (5.9, -42.2), (3.6, -39.0),
                 (1.6, -36.6), (0.3, -34.9), (0.5, -33.2), (1.6, -31.2), (2.6, -29.0), (3.6, -25.8), (6.6, -22.0),
                 (7.2, -19.6), (9.0, -18.0), (12.0, -17.9), (13.6, -19.4), (14.4, -22.0), (13.4, -25.5)]
SAFETY_READY = [(13.0, -40.6), (15.9, -43.3), (19.0, -46.2), (20.5, -47.6), (19.7, -48.7), (17.6, -48.4), (14.5, -46.2),
                (11.5, -43.2), (9.6, -41.2), (6.0, -40.9), (3.4, -41.3), (1.5, -40.7), (1.1, -39.6), (2.6, -38.9),
                (6.5, -38.3), (10.2, -38.4)]
SAFETY_PIVOT = (8.8, -39.2)


def trigger(h):
    """Спусковой крючок: гладкая выпуклая передняя грань, прорезь под предохранитель, ось предохранителя."""
    pts = smooth_closed(TRIGGER_READY, 0.2, 0.7)
    xs = [p[0] for p in pts]; zs = [p[1] for p in pts]
    F = Field("Trigger", (min(xs) - 0.8, -4.4, min(zs) - 0.8), (max(xs) + 0.8, 4.4, max(zs) + 0.8), h)
    F.add(prism(Poly(pts), "XZ", -3.6, 3.6, rim=1.5))
    F.sub(cyl("Y", PIN_TRIGGER, 2.05, -10, 10), 0.25)
    saf = Poly(smooth_closed(SAFETY_READY, 0.2, 0.4))
    F.sub(prism(saf, "XZ", -1.25, 1.25, off=0.3), 0.3)
    sp = SAFETY_PIVOT
    F.sub(cyl("Y", sp, 0.8, -10, 10), 0.15, bbox=bb(sp[0] - 2, sp[0] + 2, -4.4, 4.4, sp[1] - 2, sp[1] + 2))
    return F


def trigger_safety(h):
    """Автоматический предохранитель спуска: рычажок в прорези, спереди выступает из пера, сзади хвост-упор."""
    pts = smooth_closed(SAFETY_READY, 0.2, 0.4)
    xs = [p[0] for p in pts]; zs = [p[1] for p in pts]
    F = Field("Trigger_Safety", (min(xs) - 0.6, -1.7, min(zs) - 0.6), (max(xs) + 0.6, 1.7, max(zs) + 0.6), h)
    F.add(prism(Poly(pts), "XZ", -1.0, 1.0, rim=0.45))
    F.sub(cyl("Y", SAFETY_PIVOT, 0.8, -3, 3), 0.1)
    return F


def safety_pin(h):
    sp = SAFETY_PIVOT
    F = Field("Trigger_Safety_Pin", (sp[0] - 1.3, -4.0, sp[1] - 1.3), (sp[0] + 1.3, 4.0, sp[1] + 1.3), h)
    F.add(cyl("Y", sp, 0.76, -3.4, 3.4, rim=0.25))
    return F


# ---------- оси ----------

def pin(center, r, half_len):
    def build(h):
        F = Field("Pin", (center[0] - r - 0.6, -half_len - 0.6, center[1] - r - 0.6), (center[0] + r + 0.6, half_len + 0.6, center[1] + r + 0.6), h)
        F.add(cyl("Y", center, r, -half_len, half_len, rim=0.45))
        return F
    return build


def parts():
    px, pz = PIN_TRIGGER
    lx, lz = LOCK_C
    sp = SAFETY_PIVOT
    return [
        dict(name="Slide_Stop", build=slide_stop, h=0.05, coll="Controls", mat="Steel_black", pivot=(px, 0, pz), weight=4,
             motion=f"поворот вокруг своей оси Y на +{STOP_UP_DEG:g}° — зуб входит в вырез затвора (задержка); ось — ось спуска"),
        dict(name="Slide_Lock", build=slide_lock, h=0.05, coll="Controls", mat="Steel_black", pivot=(lx, 0, lz), weight=3,
             motion=f"сдвиг вдоль своей планки вниз на {LOCK_DOWN:g} мм: (−{math.sin(math.radians(LOCK_DEG)) * LOCK_DOWN:.2f}, 0, −{math.cos(math.radians(LOCK_DEG)) * LOCK_DOWN:.2f}) мм — разборка"),
        dict(name="Mag_Catch", build=mag_catch, h=0.05, coll="Controls", mat="Polymer", pivot=(CATCH_C[0], 0, CATCH_C[1]), weight=4,
             motion=f"сдвиг по Y на −{CATCH_IN:g} мм — кнопка нажата, зацеп выходит из выреза магазина"),
        dict(name="Trigger", build=trigger, h=0.05, coll="Controls", mat="Polymer", pivot=(px, 0, pz), weight=4,
             motion=f"поворот вокруг своей оси Y на +{TRIGGER_DEG:g}° — спуск выжат до упора"),
        dict(name="Trigger_Safety", build=trigger_safety, h=0.04, coll="Controls", mat="Polymer", parent="Trigger", pivot=(sp[0], 0, sp[1]),
             motion=f"поворот вокруг своей оси Y на +{SAFETY_DEG:g}° — предохранитель утоплен в крючок"),
        dict(name="Trigger_Safety_Pin", build=safety_pin, h=0.04, coll="Controls", mat="Steel_black", parent="Trigger"),
        dict(name="Pin_Trigger", build=pin(PIN_TRIGGER, 1.98, 12.9), h=0.04, coll="Pins", mat="Steel_black", parent="Frame"),
        dict(name="Pin_Locking_Block", build=pin(PIN_BLOCK, 1.48, 12.9), h=0.04, coll="Pins", mat="Steel_black", parent="Frame"),
        dict(name="Pin_Trigger_Housing", build=pin(PIN_HOUSING, 1.98, 12.9), h=0.04, coll="Pins", mat="Polymer", parent="Frame"),
    ]
