# АСТЕН-919: маски маркировки, наносимой краской и литьём, — в развёртку наборов (обычный Python: numpy, PIL).
#   python -X utf8 tools/asten919/tex_marks.py [папка geo] [папка масок]
# Вход — <Деталь>_geo.npz из tex_geo_dump.py. Рисунок задан в плоскости детали в мм (как на чертеже), маска в развёртке
# получается проекцией: каждый тексель знает своё положение на детали. Выход (ч/б PNG размера набора, белое — знак):
#   slide_sight_paint.png — белая обводка прорези целика и точка мушки (выбор владельца 2026-11-12, краска без рельефа);
#   magazine_numbers.png  — цифры 4…17 у окошек счёта на задней стенке магазина (литой рельеф корпуса).
# Гравировка затвора, казённика, пластины с номером и литые знаки рукояти — в самой сетке (part_slide.py и др.).
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dims import *  # noqa: E402,F403
import tex_sets as T  # noqa: E402

GEO = sys.argv[1] if len(sys.argv) > 1 else T.WORK + "/geo"
OUT = sys.argv[2] if len(sys.argv) > 2 else T.WORK + "/masks"
TOP = SLIDE_TOP           # верх затвора над осью канала
SS = 2                    # сглаживание: маска считается вдвое крупнее и уменьшается

# ---------- прицельные (плоскость YZ, взгляд стрелка: вправо — −Y) ----------
NOTCH_HW = 1.85           # полуширина прорези целика (part_slide.rear_sight)
NOTCH_Z = TOP + 1.55      # дно прорези
SIGHT_TOP = TOP + 4.3
U_GAP, U_W = 0.30, 0.75   # отступ обводки от кромки прорези и ширина полосы
DOT_R = 1.15              # точка мушки
DOT_Z = TOP + 2.35

# ---------- цифры магазина ----------
NUM_CAP = 2.1             # высота цифры, мм
NUM_Y = 7.3               # середина цифры от оси магазина (окошки на ±3,6)


def raster(geo, res, value, keep):
    """Маска res × res: тексели треугольников, для которых keep(нормаль, положение) истинно, получают
    value(положение текселя) (0…1). Положение — барицентрической интерполяцией вершин."""
    n = res * SS
    img = np.zeros((n, n), np.float32)
    uv, pos, nrm = geo["uv"], geo["pos"], geo["nrm"]
    sel = np.nonzero(keep(nrm, pos.mean(axis=1)))[0]
    for i in sel:
        t = uv[i] * n
        x0, x1 = int(np.floor(t[:, 0].min())), int(np.ceil(t[:, 0].max())) + 1
        y0, y1 = int(np.floor(t[:, 1].min())), int(np.ceil(t[:, 1].max())) + 1
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, n), min(y1, n)
        if x1 <= x0 or y1 <= y0:
            continue
        px, py = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        a, b, c = t
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        w0 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / den
        w1 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / den
        w2 = 1.0 - w0 - w1
        e = -0.02                               # тексели на границе треугольника не теряются
        ins = (w0 >= e) & (w1 >= e) & (w2 >= e)
        if not ins.any():
            continue
        p = w0[..., None] * pos[i, 0] + w1[..., None] * pos[i, 1] + w2[..., None] * pos[i, 2]
        v = value(p)
        blk = img[y0:y1, x0:x1]
        blk[ins] = np.maximum(blk[ins], v[ins])
    im = Image.fromarray(np.uint8(np.clip(img[::-1], 0, 1) * 255))       # v развёртки — снизу вверх
    return im.resize((res, res), Image.LANCZOS)


def smooth(d, w=0.06):
    """Мягкий край: расстояние до границы знака d (мм, внутри отрицательное) → 0…1."""
    return np.clip(0.5 - d / w, 0.0, 1.0)


def sight_paint(res):
    def u_shape(p):
        y, z = np.abs(p[..., 1]), p[..., 2]
        outer = np.maximum(y - (NOTCH_HW + U_GAP + U_W), (NOTCH_Z - U_GAP - U_W) - z)
        inner = np.maximum(y - (NOTCH_HW + U_GAP), (NOTCH_Z - U_GAP) - z)
        d = np.maximum(outer, -inner)
        d = np.maximum(d, z - (SIGHT_TOP - 0.45))       # до скругления верхней кромки
        return smooth(d)

    def dot(p):
        return smooth(np.hypot(p[..., 1], p[..., 2] - DOT_Z) - DOT_R)

    back = lambda nrm, c: nrm[:, 0] < -0.6              # грань, обращённая к стрелку
    rear = raster(np.load(f"{GEO}/Rear_Sight_geo.npz"), res, u_shape,
                  lambda nrm, c: back(nrm, c) & (c[:, 2] > TOP + 0.3) & (np.abs(c[:, 1]) < NOTCH_HW + U_GAP + U_W + 1))
    front = raster(np.load(f"{GEO}/Front_Sight_geo.npz"), res, dot, lambda nrm, c: back(nrm, c) & (c[:, 2] > TOP + 0.3))
    return Image.fromarray(np.maximum(np.asarray(rear), np.asarray(front)))


def numbers_sheet(px_mm=40.0):
    """Лист задней стенки магазина: по горизонтали — «вправо для смотрящего сзади» (−Y), по вертикали — вдоль оси
    магазина вверх. Возвращает картинку и функцию (y, a) → значение."""
    font = ImageFont.truetype(font_path(), int(round(NUM_CAP * px_mm / 0.729)))      # высота прописной DejaVu — 0,729 кегля
    # окошки: чётные патроны слева для стрелка (+Y), нечётные справа; координата вдоль оси — как в part_magazine
    import part_magazine as M
    rows = []
    for k in range(4, 18):
        _x, _y, z = M.ROUNDS[k - 1]
        yc = 3.6 if k % 2 == 0 else -3.6
        ac = SIN * mag_rear_x(z) + COS * z
        rows.append((k, yc, ac))
    a0 = min(r[2] for r in rows) - 4.0
    a1 = max(r[2] for r in rows) + 4.0
    w, h = int(2 * MAG_HW * px_mm), int((a1 - a0) * px_mm)
    im = Image.new("L", (w, h), 0)
    dr = ImageDraw.Draw(im)
    for k, yc, ac in rows:
        ny = NUM_Y if yc > 0 else -NUM_Y
        cx = (MAG_HW - ny) * px_mm                 # вправо на листе — −Y
        cy = (a1 - ac) * px_mm
        dr.text((cx, cy), str(k), font=font, fill=255, anchor="mm")
    im = im.filter(ImageFilter.GaussianBlur(0.6))
    arr = np.asarray(im, np.float32) / 255.0

    def value(p):
        y = p[..., 1]
        a = SIN * p[..., 0] + COS * p[..., 2]
        u = np.clip(((MAG_HW - y) * px_mm).astype(int), 0, w - 1)
        v = np.clip(((a1 - a) * px_mm).astype(int), 0, h - 1)
        ok = (np.abs(y) < MAG_HW) & (a > a0) & (a < a1)
        return np.where(ok, arr[v, u], 0.0)
    return im, value, (a0, a1)


def magazine_numbers(res):
    sheet, value, (a0, a1) = numbers_sheet()
    sheet.save(f"{OUT}/magazine_numbers_sheet.png")
    rear = np.array([-COS, 0.0, SIN])               # наружная нормаль задней стенки

    def keep(nrm, c):
        a = SIN * c[:, 0] + COS * c[:, 2]
        s = COS * (c[:, 0] - MAG_REF[0]) - SIN * (c[:, 2] - MAG_REF[1])
        return (nrm @ rear > 0.75) & (a > a0) & (a < a1) & (s < -MAG_DEPTH + 1.5)
    return raster(np.load(f"{GEO}/Magazine_Body_geo.npz"), res, value, keep)


def main():
    os.makedirs(OUT, exist_ok=True)
    m = sight_paint(T.SETS["slide"][0])
    m.save(f"{OUT}/slide_sight_paint.png")
    print("slide_sight_paint", np.asarray(m).mean() / 255 * 100, "% атласа")
    m = magazine_numbers(T.SETS["magazine"][0])
    m.save(f"{OUT}/magazine_numbers.png")
    print("magazine_numbers", np.asarray(m).mean() / 255 * 100, "% атласа")


main()
