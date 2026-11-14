# ПКП: приклад (чёрный пластик, с окном) и его металл — затыльник с ушками на винтах, откидной плечевой упор
# на шарнире, защёлка упора. Контуры — по правому боковому рендеру владельца 13 (trace/mm2, сетка в мм модели,
# с поправкой на глубину кромок); ширины — оценка (dims.py).
import math

import numpy as np

from dims import *
from sdf import *

HW = STOCK_HW
BUTT_XT, BUTT_XB = -648.0, -646.2   # задняя плоскость пластика приклада вверху и внизу (затыльник чуть наклонён)


def _t(pts):
    """Точки контура, снятые со старой сетки снимка 13 по кромкам ближнего к камере борта (глубина 21 мм), →
    миллиметры модели: масштаб refmap.K и поправка на глубину вместе дают 0,9967 и малый сдвиг."""
    return [(0.9967 * x + 0.27, 0.9967 * z - 0.49) for x, z in pts]


# боковой контур приклада (X, Z): от шейки у ствольной коробки по верху назад
OUTLINE = _t([(-366.0, -1.0), (-432.0, -1.0), (-449.0, 10.5), (-590.0, 11.0), (-600.0, 14.0), (-651.0, 13.0),
              (-651.0, -106.0), (-622.0, -106.0), (-582.0, -82.0), (-522.0, -82.0), (-470.3, -105.0), (-437.5, -49.5),
              (-366.0, -49.5)])
OUTLINE[5] = (BUTT_XT, OUTLINE[5][1])
OUTLINE[6] = (BUTT_XB, OUTLINE[6][1])
OUTLINE_R = [0.0, 7.0, 9.0, 4.0, 3.0, 1.5, 6.0, 12.0, 12.0, 12.0, 9.0, 9.0, 0.0]
Z_TOP, Z_BOT = OUTLINE[5][1], OUTLINE[6][1]
BUTT_K = (BUTT_XB - BUTT_XT) / (Z_TOP - Z_BOT)      # наклон задней плоскости: сдвиг по X на мм высоты вниз
WINDOW = _t([(-606.0, -13.0), (-487.0, -13.0), (-472.5, -27.0), (-490.5, -54.5), (-606.0, -54.5)])
WINDOW_R = [20.5, 10.0, 7.0, 7.5, 20.5]
# выемка под большой палец на шейке (с обеих сторон)
GROOVE = _t([(-452.0, -36.8), (-425.0, -37.6), (-395.0, -40.3), (-380.0, -40.0), (-372.5, -33.0), (-372.5, -17.0),
             (-381.0, -9.5), (-420.0, -11.0), (-438.0, -17.0)])
GROOVE_R = [0.0, 30.0, 30.0, 7.0, 7.0, 7.0, 7.0, 40.0, 30.0]

# металл затыльника (мм модели: снимок 13, сетка trace/mm2/r_butt, поправка на глубину кромок)
PLATE_T = 2.6                       # толщина затыльника
FLANGE_T = 1.2                      # отбортовка затыльника на боках приклада
FLANGE_W = 2.6                      # на сколько отбортовка заходит на бока
EAR = (-626.1, -92.6, -74.6)        # ушко затыльника: передний край по X, низ и верх по Z
EAR_SCREW = (-635.0, -83.6)         # винт ушка (X, Z)
EAR_SCREW_R = 4.9
REST_AXIS = (-639.1, 17.1)          # ось шарнира плечевого упора (X, Z)
REST_EYE_R = 4.2                    # проушины упора; на снимке виден диск R 5,8 — это головка оси снаружи
REST_HEAD_R = 5.6
REST_HW = 21.0                      # полуширина упора — во всю ширину затыльника (оценка по силуэту)
# наружный контур сложенного упора (X, Z): от шарнира через верх назад и вниз по затыльнику, обратно — вдоль него
REST_OUT = [(-638.2, 23.4), (-647.7, 27.4), (-654.9, 23.6), (-657.0, 15.9), (-655.5, 0.0), (-653.3, -8.2), (-651.4, -8.2),
            (-651.4, 11.5), (-649.6, 14.6), (-643.0, 14.6), (-635.2, 14.2)]
REST_OUT_R = [3.0, 6.0, 5.0, 8.0, 10.0, 1.0, 0.8, 2.0, 1.5, 1.0, 2.0]
CATCH = (-624.7, -613.1, 21.0)      # колодка защёлки упора на верху приклада: X от и до, верх по Z (назначение — оценка)

_SIDE = None


def side_poly():
    global _SIDE
    if _SIDE is None:
        _SIDE = Poly(fillet_poly(OUTLINE, OUTLINE_R, seg=14))
    return _SIDE


def stock_body(X, Y, Z):
    """Тело приклада без окна: силуэт × ширина. Кромки скруглены крупно (приклад литой), у затыльника радиус
    плавно уменьшается — там приклад закрыт стальным затыльником с отбортовкой."""
    r = 1.5 + 3.5 * smoothstep((X + 644.0) / 16.0)
    return i_round(side_poly().sd(X, Z), np.abs(Y) - HW, r)


def stock(h):
    F = Field("Stock", (BUTT_XT - 1, -HW - 1, -108), (RECV_X0 + 1, HW + 1, 16), h)
    F.add(stock_body)
    # окно: сквозное, с широкой скруглённой кромкой
    win = Poly(fillet_poly(WINDOW, WINDOW_R, seg=20))
    F.sub(prism(win, "XZ", -HW - 3, HW + 3), 4.5, bbox=bb(-612, -466, -HW - 1, HW + 1, -60, -8))
    # выемки под большой палец: плавно уходят в тело к задней части
    gr = Poly(fillet_poly(GROOVE, GROOVE_R, seg=10))

    def groove(X, Y, Z):
        d2 = gr.sd(X, Z)
        depth = 2.6 * smoothstep((X + 455.0) / 60.0)
        side_k = smoothstep((np.abs(Y) - (HW - 8.0)) / 3.0)
        return -depth * smoothstep(-d2 / 5.0) * side_k
    F.displace(groove, bbox=bb(-456, -368, -HW - 1, HW + 1, -44, -6), fine=False)
    # торец шейки — плоскость стыка с коробкой
    F.apply(half("X", RECV_X0, 1), "inter", 0.0, bbox=bb(RECV_X0 - 2, RECV_X0 + 1, -HW - 1, HW + 1, -52, 2))
    return F


def buttplate(h):
    """Затыльник: стальная пластина на торце приклада с отбортовкой на бока и ушками на винтах внизу.
    Форма — оболочка вокруг тела приклада: сама повторяет его контур и наклон торца."""
    yo = HW + FLANGE_T
    F = Field("Buttplate", (BUTT_XT - PLATE_T - 1, -yo - 1, Z_BOT - FLANGE_T - 1), (EAR[0] + 1, yo + 1, Z_TOP + FLANGE_T + 1), h)

    def cap(X, Y, Z):
        a = stock_body(X, Y, Z) - FLANGE_T
        b = stock_body(X + (PLATE_T - FLANGE_T), Y, Z) - FLANGE_T
        return np.minimum(a, b)
    F.add(cap, bbox=bb(BUTT_XT - PLATE_T - 1, BUTT_XB + FLANGE_W + 2, -yo - 1, yo + 1, Z_BOT - 3, Z_TOP + 3))
    # передняя кромка отбортовки — параллельно наклонному торцу
    F.apply(plane((BUTT_XT + FLANGE_W + BUTT_K * Z_TOP, 0.0, 0.0), (1.0, 0.0, BUTT_K)), "inter", 0.3)
    # ушки на боках
    ear = rect2(BUTT_XB - 1.0, EAR[0], EAR[1], EAR[2], 7.0)
    for s in (-1, 1):
        y0, y1 = sorted((s * (HW - 0.5), s * yo))
        F.add(prism2(ear, "XZ", y0, y1, rim=0.0), 0.0, bbox=bb(BUTT_XB - 2, EAR[0] + 1, y0 - 0.5, y1 + 0.5, EAR[1] - 1, EAR[2] + 1))
    F.apply(lambda X, Y, Z: np.abs(Y) - yo, "inter", 0.35)
    # гнездо под приклад: тело приклада с малым зазором
    F.sub(lambda X, Y, Z: stock_body(X, Y, Z) - 0.05, 0.0)
    for s in (-1, 1):
        F.sub(cyl("Y", EAR_SCREW, 2.3, s * (HW - 1), s * (yo + 1)), 0.2,
              bbox=bb(EAR_SCREW[0] - 3, EAR_SCREW[0] + 3, s * yo - 3, s * yo + 3, EAR_SCREW[1] - 3, EAR_SCREW[1] + 3))
    return F


def butt_screw(side):
    def build(h):
        yo = side * (HW + FLANGE_T)
        x, z = EAR_SCREW
        ya, yb = sorted((yo - side * 2.5, yo + side * 2.0))
        F = Field("Butt_Screw", (x - 5.6, ya - 0.6, z - 5.6), (x + 5.6, yb + 0.6, z + 5.6), h)
        y0, y1 = sorted((yo, yo + side * 1.5))
        F.add(cyl("Y", (x, z), EAR_SCREW_R, y0, y1, rim=0.25, rim1=0.25))

        # головка слегка выпуклая
        def dome(X, Y, Z):
            return np.sqrt((X - x) ** 2 + (Y - (yo - side * 12.0)) ** 2 + (Z - z) ** 2) - 13.6
        F.apply(dome, "inter", 0.5)
        y2, y3 = sorted((yo - side * 2.0, yo + side * 0.4))
        F.add(cyl("Y", (x, z), 2.2, y2, y3), 0.0)
        ys0, ys1 = sorted((yo + side * 0.75, yo + side * 3.0))
        F.sub(box((x - 6, ys0, z - 0.55), (x + 6, ys1, z + 0.55), 0.0), 0.12)
        return F
    return build


def shoulder_rest(h):
    """Откидной плечевой упор (в сложенном положении): штампованная чашка, облегающая верхний задний угол приклада."""
    F = Field("Shoulder_Rest", (-658.5, -REST_HW - 1, -9.6), (-632, REST_HW + 1, 29), h)
    out = Poly(fillet_poly(REST_OUT, REST_OUT_R, seg=10))
    F.add(prism(out, "XZ", -REST_HW, REST_HW, rim=1.1))
    # изнутри чашка пустая: остаются наружная стенка и боковины; сторона к прикладу открыта
    F.sub(prism(out, "XZ", -REST_HW + 1.8, REST_HW - 1.8, off=-2.2), 0.6)
    opening = Poly([(-652.6, -9.5), (-630.0, -9.5), (-630.0, 15.8), (-648.8, 15.8), (-652.6, 11.5)])
    F.sub(prism(opening, "XZ", -REST_HW + 1.8, REST_HW - 1.8), 0.4)
    # проушины шарнира по краям
    for s in (-1, 1):
        y0, y1 = sorted((s * (REST_HW - 3.6), s * REST_HW))
        F.add(cyl("Y", REST_AXIS, REST_EYE_R, y0, y1, rim=0.8), 0.8, bbox=bb(-647, -632, y0 - 1, y1 + 1, 11.5, 24.5))
    F.sub(cyl("Y", REST_AXIS, 2.05, -REST_HW - 2, REST_HW + 2), 0.2, bbox=bb(-643, -635, -REST_HW - 1, REST_HW + 1, 14, 21))
    return F


def rest_hinge(h):
    """Основание шарнира упора на верху приклада: планка, стойки, ось; впереди — колодка защёлки с рычажком."""
    zt = Z_TOP
    F = Field("Rest_Hinge", (-646.5, -HW - 2.6, zt - 0.6), (CATCH[1] + 1.5, HW + 2.6, 24.2), h)
    # планка лежит на верху приклада и повторяет его уклон: слой над телом приклада
    def base(X, Y, Z):
        lim = np.maximum(np.maximum(-645.4 - X, X - (CATCH[1] + 0.8)), np.abs(Y) - 9.5)
        return i_round(i_round(stock_body(X, Y, Z) - 1.5, lim, 0.5), 6.0 - Z, 0.0)
    F.add(base)
    # стойки оси между проушинами упора
    lug = union2(rect2(REST_AXIS[0] - 3.4, REST_AXIS[0] + 3.4, zt + 0.5, REST_AXIS[1], 0.6), circle2(REST_AXIS, 3.4))
    for s in (-1, 1):
        y0, y1 = sorted((s * 5.6, s * 9.5))
        F.add(prism2(lug, "XZ", y0, y1, rim=0.5), 0.8, bbox=bb(-644, -634, y0 - 1, y1 + 1, zt, 21.5))
    # ось с головками
    F.add(cyl("Y", REST_AXIS, 2.0, -HW - 1.7, HW + 1.7, rim=0.4), 0.0)
    for s in (-1, 1):
        y0, y1 = sorted((s * (HW + 0.25), s * (HW + 1.9)))
        F.add(cyl("Y", REST_AXIS, REST_HEAD_R, y0, y1, rim=0.6), 0.0, bbox=bb(-646, -632, y0 - 0.5, y1 + 0.5, 10.5, 23.6))
    # колодка защёлки и её рычажок, удерживающий упор сложенным
    F.add(box_e((CATCH[0], -7.0, zt + 1.0), (CATCH[1], 7.0, CATCH[2]), rx=1.6, ry=1.2, rz=1.2), 0.8,
          bbox=bb(CATCH[0] - 2, CATCH[1] + 2, -9, 9, zt, CATCH[2] + 1))
    lever = Path2(fillet_path([(CATCH[0] - 0.6, 19.2), (-630.4, 18.4), (-633.4, 20.6)], [3.0]))
    F.add(strip(lever, "XZ", 2.0, -4.0, 4.0, rim=0.6), 0.5, bbox=bb(-635.5, CATCH[0] + 1, -5, 5, 16, 23))
    # снизу всё подрезано по телу приклада
    F.sub(lambda X, Y, Z: stock_body(X, Y, Z) - 0.05, 0.0)
    return F


def parts():
    return [
        dict(name="Stock", build=stock, h=0.2, coll="Приклад", mat="Polymer", adapt=0.04),
        dict(name="Buttplate", build=buttplate, h=0.15, coll="Приклад", mat="Steel_blued", parent="Stock", adapt=0.1),
        dict(name="Butt_Screw_R", build=butt_screw(-1), h=0.06, coll="Приклад", mat="Steel_phosphate", parent="Stock"),
        dict(name="Butt_Screw_L", build=butt_screw(1), h=0.06, coll="Приклад", mat="Steel_phosphate", parent="Stock"),
        dict(name="Rest_Hinge", build=rest_hinge, h=0.1, coll="Приклад", mat="Steel_blued", parent="Stock"),
        dict(name="Shoulder_Rest", build=shoulder_rest, h=0.1, coll="Приклад", mat="Steel_blued", parent="Stock",
             pivot=[REST_AXIS[0], 0.0, REST_AXIS[1]]),
    ]
