# «Осока»: источник питания (по образцу наземного источника питания «Иглы» — баллон с газом для охлаждения ГСН и
# батарея; одноразовый, приводится в действие наколом рычагом «ИСХОДНОЕ — НАКОЛ»). Чёрный резиновый шар — гнездо на
# пусковом механизме; оливковый цилиндр Ø65 — сам источник, вставляется в шар по оси (вниз к переду на 8°).
# Снимок КБМ: шар 182…341 × 503…646 пикс, цилиндр 66…200 × 545…644 пикс (dims.py).
import math
import bpy
from mathutils import Matrix, Vector
from lib import MM, v, lathe, px_x, px_z, cyl, finish_small
import dims as D


def frame():
    """Ось источника: начало в центре шара, +X вдоль оси к переду (вниз на 8°)."""
    bx, by, bd = D.POWER_BALL_PX
    c = Vector((px_x(bx), 0.0, px_z(bx, by)))
    a = math.radians(D.POWER_AXIS_DEG)
    ax = Vector((math.cos(a), 0.0, -math.sin(a)))
    # поворот вокруг +Y на +a опускает перёд оси (x' = x·cos a, z' = −x·sin a)
    m = Matrix.Translation(c * MM) @ Matrix.Rotation(a, 4, "Y")
    return c, ax, m


def build(ctx):
    C = ctx["coll"]["Power"]
    c, ax, m = frame()
    R = D.POWER_BALL_PX[2] / 2
    # шар-гнездо: сзади горловина к литью (R 15), выпуклость R 47.5, спереди воротник R 35 обжимает цилиндр
    neck_x = (px_x(D.POWER_NECK_PX[0]) - c.x) / math.cos(math.radians(D.POWER_AXIS_DEG))
    prof = [(neck_x - 2.0, 0.0), (neck_x - 2.0, 13.0), (neck_x + 2.0, 15.0), (-R * 0.86, 19.0)]
    t0, t1 = math.radians(144.0), math.radians(48.0)
    for k in range(18):
        t = t0 + (t1 - t0) * k / 17                    # дуга шара от задней горловины к переднему воротнику
        prof.append((R * math.cos(t), R * math.sin(t)))
    xc = R * math.cos(t1)
    prof += [(xc + 1.2, 35.6), (xc + 11.0, 35.2), (xc + 12.0, 33.6), (xc + 12.0, 0.0)]
    ball = lathe("Power_socket", prof, C, "Rubber_black", seg=96)
    ball.data.transform(m)
    # штуцер литья под горловину
    stub = lathe("Power_socket_stub", [(neck_x - 9.0, 0.0), (neck_x - 9.0, 11.0), (neck_x - 8.0, 12.0), (neck_x + 1.0, 12.0),
                                        (neck_x + 1.0, 0.0)], C, "Paint_olive_cast", seg=48)
    stub.data.transform(m)
    # сам источник: цилиндр Ø65, торец с фаской; задний конец уходит в воротник шара
    r = D.POWER_CYL[2] / 2
    x_front = (px_x(D.POWER_CYL[0]) - c.x) / math.cos(math.radians(D.POWER_AXIS_DEG))
    x_back = R * math.cos(math.radians(48.0)) - 8.0
    cylp = [(x_back, 0.0), (x_back, r - 1.5), (x_back + 1.5, r), (x_front - 4.0, r), (x_front - 1.2, r - 0.8),
            (x_front, r - 4.0), (x_front + 0.6, 6.0), (x_front + 0.8, 0.0)]
    pw = lathe("Power_source", cylp, C, "Paint_olive", seg=96)
    # торцевая заглушка и поясок у воротника
    band = lathe("Power_source_band", [(x_back + 18.0, r - 0.2), (x_back + 18.0, r + 0.8), (x_back + 24.0, r + 0.8),
                                       (x_back + 24.0, r - 0.2)], C, "Paint_olive", seg=96)
    from lib import join
    pw = join([pw, band], "Power_source")
    pw.data.transform(m)
    from lib import set_origin
    set_origin(pw, tuple(c))
    return {"source": pw, "axis": ax, "center": c}
