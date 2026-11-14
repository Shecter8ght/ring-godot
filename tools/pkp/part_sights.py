# ПКП: прицельные приспособления — секторный прицел на крышке ствольной коробки и мушка.
# Устройство (как у ПК / ПКМ / ПКП, подтверждено фото refs/web/B03_right_side/14_receiver_sights_closeup.jpg и
# рендерами владельца 13 / 14): колодка из штампованного листа с двумя стенками приклёпана к верху крышки; прицельная
# планка шарнирно сидит на оси у ЗАДНЕЙ стенки колодки (в задней стенке — овальное отверстие), вперёд идёт чуть вверх;
# на переднем конце планки — рамка целика с поперечным винтом боковых поправок и маховичком; по планке ходит хомутик
# с рифлёной кнопкой-защёлкой, зубья защёлки — гребёнка под планкой; деления 1–15 выбиты двумя рядами (чётные дальше
# от стрелка, нечётные ближе), «1» у переднего конца, «15» у заднего. Пластинчатая пружина под планкой упирается в её
# нижнюю плоскость. Мушка — стержень с буртиком в пазу между «ушами» основания мушки (см. part_barrel.fsb).
# Ось отсчёта: X = 0 — передний торец коробки, Z = 0 — ось канала, −Y — правая сторона стрелка (dims.py).
# Размеры, которых нет на снимках, помечены «оценка»: по снимкам прицела мерены общая компоновка и высоты
# (ref13: колодка X −283…−205, верх до Z ≈ 47 сзади; ось планки по вертикали ~44,5; высота рамки ~54–55 от оси канала).
# Высота линии прицеливания и её проход над ручкой для переноски проверены расчётом (см. check_line в конце модуля).
import math

import numpy as np

from dims import *
from sdf import *

U = TILE_K
FONT = "C:/Windows/Fonts/ARIALN.TTF"       # узкий шрифт только для технических цифр шкалы (не марка)

# ---- общая геометрия ----
PX, PZ = -278.0, 44.5                      # ось планки (оценка по рендеру 13; сзади у стенки)
BASE_X0, BASE_X1 = -283.0, -205.5          # колодка (ref13)
Z_REAR = 47.2                              # верх заднего борта колодки (ref13: ≈ 47)
WALL_I, WALL_O = 9.4, 11.4                 # внутренняя и внешняя грани стенок колодки по Y (оценка по ширине верха крышки)
FLOOR_T = 1.5
LEAF_LEN = 68.0                            # длина планки от оси до носика (оценка по ref13: до X ≈ −210)
LEAF_T = 3.0
LEAF_HW = 7.4
TH = math.atan2(5.1, 67.0)                 # подъём планки вперёд (ref13: от Z 45 сзади до ≈ 50 у рамки)
C, S = math.cos(TH), math.sin(TH)
SC_PITCH = 2.8                             # шаг делений вдоль планки (оценка)
SC_U1 = 53.0                               # положение «1» вдоль планки (от оси), «15» = SC_U1 − 14·шаг
SLIDER_N = 3                               # хомутик построен у «3»
FR_U = 62.7                                # поперечный винт: положение вдоль планки
FR_W = 4.2                                 # и высота над серединой планки
NOTCH_BOTTOM_W = 5.0                       # дно прорези целика над серединой планки
POST_X, POST_TOP = 440.0, 59.0             # мушка (единицы part_barrel: умножаются на U)


def zt(x):
    """Верх крышки по X (копия _ramp part_cover: 34,5 → 44,5 на ступени −229 … −206)."""
    t = min(1.0, max(0.0, (x + 229.0) / 23.0))
    return 34.5 + 10.0 * t


def tilted(fn):
    """Тело fn, заданное в системе планки (u вдоль неё от оси, y, w над серединой), → мировая система."""
    def f(X, Y, Z):
        dx = X - PX; dz = Z - PZ
        return fn(dx * C + dz * S, Y, -dx * S + dz * C)
    return f


def W(u, w):
    """Точка планки (u, w) → мировые (X, Z)."""
    return PX + u * C - w * S, PZ + u * S + w * C


def lb(u0, u1, y0, y1, w0, w1):
    """Мировой bbox местного бруса планки."""
    pts = [W(u, w) for u in (u0, u1) for w in (w0, w1)]
    xs = [p[0] for p in pts]; zs = [p[1] for p in pts]
    return bb(min(xs), max(xs), y0, y1, min(zs), max(zs))


def lfield(name, u0, u1, y0, y1, w0, w1, h):
    b = lb(u0, u1, y0, y1, w0, w1)
    return Field(name, (b[0][0] - 1, b[0][1] - 1, b[0][2] - 1), (b[1][0] + 1, b[1][1] + 1, b[1][2] + 1), h)


class _T:
    """Подставка для engrave: рельеф, заданный в системе планки."""
    def __init__(self, F):
        self.F = F

    def displace(self, fn, bbox=None, fine=True):
        self.F.displace(tilted(fn), bbox=bbox, fine=fine)


def scale_u(n):
    return SC_U1 - (n - 1) * SC_PITCH


# ---------- основание (колодка) ----------

def base(h):
    F = Field("Rear_Sight_Base", (BASE_X0 - 2, -WALL_O - 2.5, 33.0), (BASE_X1 + 2, WALL_O + 2.5, 49.0), h)
    wall_poly = Poly(fillet_poly(
        [(BASE_X0, 34.4), (-229.0, 34.4), (-206.0, 44.5), (BASE_X1, 44.5), (BASE_X1, 46.0), (-207.0, 46.0),
         (-222.0, 44.0), (-238.0, 42.5), (-270.0, 42.5), (-274.0, Z_REAR), (BASE_X0, Z_REAR)],
        [0.8, 0, 0.8, 0.5, 0.5, 1.5, 2.0, 2.0, 2.5, 2.0, 1.2]))
    for s in (-1, 1):
        y0, y1 = sorted((s * WALL_I, s * WALL_O))
        F.add(prism(wall_poly, "XZ", y0, y1, rim=0.45), 0.0, bbox=bb(BASE_X0, BASE_X1, y0, y1, 34, 48))
    # дно между стенками: повторяет верх крышки (на ступени идёт под уклон)
    floor = Path2(fillet_path([(BASE_X0 + 1.0, 35.45), (-229.0, 35.45), (-206.0, 45.45)], [5.0]))
    F.add(strip(floor, "XZ", FLOOR_T, -WALL_I - 0.2, WALL_I + 0.2, rim=0.4), 0.5, bbox=bb(BASE_X0, BASE_X1, -WALL_I - 1, WALL_I + 1, 34, 47))
    # задняя стенка с овальным отверстием (ref: отверстие у нижнего края)
    F.add(box((BASE_X0, -WALL_O, 34.4), (BASE_X0 + 2.0, WALL_O, Z_REAR), 0.5), 0.6, bbox=bb(BASE_X0 - 1, BASE_X0 + 3, -WALL_O - 1, WALL_O + 1, 34, 48))
    F.sub(box_e((BASE_X0 - 1.5, -1.6, 37.2), (BASE_X0 + 3.5, 1.6, 41.4), rx=1.4), 0.3, bbox=bb(BASE_X0 - 2, BASE_X0 + 4, -2.5, 2.5, 36, 43))
    # отверстия оси планки (посадка: на 0,3 больше оси r 1,15)
    F.sub(cyl("Y", (PX, PZ), 1.45, -WALL_O - 3, WALL_O + 3), 0.25, bbox=bb(PX - 3, PX + 3, -WALL_O - 2, WALL_O + 2, PZ - 3, PZ + 3))
    # клёпаные соединения со стенками крышки: головки на внешних сторонах
    for x, z in ((-277.0, 40.0), (-259.0, 38.6), (-242.0, 38.6), (-224.0, 40.8)):
        for s in (-1, 1):
            F.add(cyl("Y", (x, z), 1.5, s * (WALL_O - 0.2), s * (WALL_O + 0.85), rim=0.6), 0.2,
                  bbox=bb(x - 2, x + 2, s * WALL_O - 1.5, s * WALL_O + 1.5, z - 2, z + 2))
    return F


# ---------- прицельная планка ----------

def leaf(h):
    F = lfield("Rear_Sight_Leaf", -3.2, LEAF_LEN + 1, -LEAF_HW - 1.5, LEAF_HW + 1.5, -6.0, 9.5, h)
    plan = Poly(fillet_poly([(0.5, -4.0), (40.0, -LEAF_HW), (LEAF_LEN, -LEAF_HW), (LEAF_LEN, LEAF_HW), (40.0, LEAF_HW), (0.5, 4.0)],
                            [2.0, 0.8, 1.5, 1.5, 0.8, 2.0]))
    F.add(tilted(prism(plan, "XY", -LEAF_T / 2, LEAF_T / 2, rim=0.5)), 0.0, bbox=lb(0, LEAF_LEN, -LEAF_HW - 1, LEAF_HW + 1, -2, 2))
    # ушко оси
    F.add(tilted(cyl("Y", (0.0, 0.0), 2.6, -4.4, 4.4, rim=0.45)), 0.5, bbox=lb(-3, 4, -5, 5, -3, 3))
    F.sub(tilted(cyl("Y", (0.0, 0.0), 1.3, -7, 7)), 0.2, bbox=lb(-2, 2, -6, 6, -2, 2))
    # гребёнка защёлки под правой кромкой и прорези под зуб защёлки: по шагу делений
    F.add(tilted(box((scale_u(15) - 2.8, -4.0, -3.8), (SC_U1 + 2.4, -2.8, -1.0), 0.35)), 0.3,
          bbox=lb(scale_u(15) - 3, SC_U1 + 3, -5, -2, -4.2, -1))
    for n in range(1, 16):
        u = scale_u(n)
        F.sub(tilted(box((u - 0.65, -5.0, -4.4), (u + 0.65, -2.0, -2.4), 0.25)), 0.15,
              bbox=lb(u - 1, u + 1, -5.2, -1.8, -4.6, -2.2))
    # рамка целика: две стойки по краям, в них — отверстия под винт боковых поправок
    for s in (-1, 1):
        y0, y1 = sorted((s * 5.6, s * 7.2))
        F.add(tilted(box((59.0, y0, 0.0), (66.6, y1, 7.4), 0.65)), 0.5, bbox=lb(58, 67.5, y0 - 1, y1 + 1, -1, 8.4))
    F.sub(tilted(cyl("Y", (FR_U, FR_W), 1.2, -9, 9)), 0.25, bbox=lb(FR_U - 3, FR_U + 3, -8.5, 8.5, FR_W - 3, FR_W + 3))
    # шкала боковых поправок: поперечные риски перед рамкой (деление 1 мм, каждое пятое длиннее)
    ticks = []
    for k in range(-5, 6):
        ln = 2.0 if k % 5 == 0 else 1.2
        ticks.append(rect2(0.0, ln, k * 1.0 - 0.14, k * 1.0 + 0.14, 0.05))
    T = _T(F)
    engrave(T, union2(*ticks), "XY", (56.0, 0.0), 1, LEAF_T / 2, 1, depth=0.18, wall=0.1,
            bbox=lb(55.5, 58.5, -6, 6, 0.8, 2.0))
    # деления 1–15: чётные — дальний ряд (+Y), нечётные — ближний (−Y); читаются со стороны стрелка справа
    for n in range(1, 16):
        f2, wd = text2(str(n), FONT, 2.0, ppm=40)
        yb = 1.9 if n % 2 == 0 else -4.1
        u = scale_u(n) - wd / 2
        engrave(T, f2, "XY", (u, yb), 1, LEAF_T / 2, 1, depth=0.18, wall=0.1,
                bbox=lb(u - 0.5, u + wd + 0.5, yb - 0.5, yb + 2.7, 0.8, 2.0))
    return F


# ---------- хомутик и защёлка ----------

U0 = scale_u(SLIDER_N)
WB = 1.0                                   # высота оси кнопки над серединой планки


def slider(h):
    F = lfield("Rear_Sight_Slider", U0 - 5.0, U0 + 5.0, -9.5, 12.0, -3.4, 4.6, h)
    F.add(tilted(box((U0 - 4.4, -8.9, 1.65), (U0 + 4.4, 8.9, 3.4), 0.5)), 0.0, bbox=lb(U0 - 5, U0 + 5, -9.5, 9.5, 1, 4))
    for s in (-1, 1):
        y0, y1 = sorted((s * 7.7, s * 8.9))
        F.add(tilted(box((U0 - 4.4, y0, -2.6), (U0 + 4.4, y1, 3.4), 0.5)), 0.4, bbox=lb(U0 - 5, U0 + 5, y0 - 1, y1 + 1, -3, 4))
    # окно над шкалой: хомутик показывает деление по передней кромке
    F.sub(tilted(box((U0 - 2.4, -3.6, 1.0), (U0 + 2.4, 3.6, 4.0), 0.4)), 0.3, bbox=lb(U0 - 3, U0 + 3, -4.5, 4.5, 0.5, 4.5))
    # круглая головка оси с дальней (левой) стороны
    F.add(tilted(cyl("Y", (U0, WB), 3.0, 8.5, 11.7, rim=0.55)), 0.4, bbox=lb(U0 - 4, U0 + 4, 8, 12, WB - 4, WB + 4))
    # отверстие под стержень кнопки: на 0,1 больше
    F.sub(tilted(cyl("Y", (U0, WB), 1.6, -10.0, -6.0)), 0.2, bbox=lb(U0 - 3, U0 + 3, -10, -6, WB - 3, WB + 3))
    return F


def button(h):
    """Кнопка защёлки хомутика: стержень в стенке хомутика и рифлёная головка (шашечная насечка геометрией)."""
    F = lfield("Rear_Sight_Button", U0 - 4.5, U0 + 4.5, -16.0, -6.5, WB - 4.2, WB + 4.2, h)
    F.add(tilted(cyl("Y", (U0, WB), 1.5, -11.9, -7.7, rim=0.3)), 0.0)
    F.add(tilted(cyl("Y", (U0, WB), 3.3, -15.0, -11.8, rim=0.65, rim1=0.65)), 0.4)

    def knurl(u, y, w):
        a = (u - U0) + (w - WB); b = (u - U0) - (w - WB)
        face = smoothstep((-y - 14.55) / 0.35) * smoothstep((3.05 - np.hypot(u - U0, w - WB)) / 0.4)
        return 0.22 * (0.5 + 0.5 * np.cos(2 * math.pi * a / 1.1)) * (0.5 + 0.5 * np.cos(2 * math.pi * b / 1.1)) * face

    F.displace(tilted(knurl), bbox=lb(U0 - 3.5, U0 + 3.5, -15.5, -14, WB - 3.5, WB + 3.5), fine=False)
    return F


# ---------- целик: прорезь, винт боковых поправок, маховичок ----------

def notch(h):
    """Целик: пластина с прорезью U-образной формы; скользит вдоль Y по винту (ход ±1,9 мм)."""
    F = lfield("Rear_Sight_Notch", FR_U - 3, FR_U + 3, -4.5, 4.5, 1.0, 9.0, h)
    u0, u1 = FR_U - 2.1, FR_U + 2.1
    F.add(tilted(box((u0, -3.4, 1.65), (u1, 3.4, 8.0), 0.55)), 0.0, bbox=lb(u0 - 1, u1 + 1, -4, 4, 1, 9))
    F.sub(tilted(union(box((u0 - 1, -1.05, NOTCH_BOTTOM_W + 1.05), (u1 + 1, 1.05, 10.0)), cyl("X", (0.0, NOTCH_BOTTOM_W + 1.05), 1.05, u0 - 1, u1 + 1))),
          0.3, bbox=lb(u0 - 2, u1 + 2, -2, 2, NOTCH_BOTTOM_W - 1.5, 9))
    F.sub(tilted(cyl("Y", (FR_U, FR_W), 1.2, -4.5, 4.5)), 0.2, bbox=lb(FR_U - 3, FR_U + 3, -4.5, 4.5, FR_W - 3, FR_W + 3))
    return F


def knob(h):
    """Винт боковых поправок с маховичком справа: стержень с резьбой, головка слева, рифлёный маховичок."""
    F = lfield("Rear_Sight_Knob", FR_U - 4.5, FR_U + 4.5, -13.5, 9.5, FR_W - 4.5, FR_W + 4.5, h)
    c = (FR_U, FR_W)
    F.add(tilted(cyl("Y", c, 1.0, -7.6, 7.8, rim=0.25)), 0.0)
    F.add(tilted(cyl("Y", c, 1.8, 7.5, 8.6, rim=0.35)), 0.3, bbox=lb(FR_U - 3, FR_U + 3, 7, 9, FR_W - 3, FR_W + 3))
    F.add(tilted(cyl("Y", c, 3.4, -12.6, -7.7, rim=0.6, rim1=0.6)), 0.4, bbox=lb(FR_U - 5, FR_U + 5, -13.5, -7, FR_W - 5, FR_W + 5))

    def serr(u, y, w):
        ang = np.arctan2(w - FR_W, u - FR_U)
        side = smoothstep((3.5 - np.hypot(u - FR_U, w - FR_W)) / 0.2) * smoothstep((3.4 - np.hypot(u - FR_U, w - FR_W)) / 0.2 + 0.0)
        near = smoothstep((np.hypot(u - FR_U, w - FR_W) - 2.8) / 0.4)
        k = 0.5 + 0.5 * np.cos(ang * 28.0)
        ring = smoothstep((-y - 8.2) / 0.5) * smoothstep((12.1 + y) / 0.5)
        return 0.32 * k * near * ring

    F.displace(tilted(serr), bbox=lb(FR_U - 4.5, FR_U + 4.5, -13, -7, FR_W - 4.5, FR_W + 4.5), fine=False)

    def thread(u, y, w):
        r = np.hypot(u - FR_U, w - FR_W)
        return 0.1 * np.cos(2 * math.pi * y / 0.75) * smoothstep((1.3 - r) / 0.2) * smoothstep((7.0 - np.abs(y - 0.0)) / 0.3) * smoothstep((np.abs(y) - 0.0) / 1.0)

    F.displace(tilted(thread), bbox=lb(FR_U - 1.6, FR_U + 1.6, -7.4, 7.4, FR_W - 1.6, FR_W + 1.6), fine=False)
    return F


# ---------- ось и пружина ----------

def pin(h):
    F = Field("Rear_Sight_Pin", (PX - 3, -WALL_O - 2.2, PZ - 3), (PX + 3, WALL_O + 2.2, PZ + 3), h)
    F.add(cyl("Y", (PX, PZ), 1.15, -WALL_O - 0.2, WALL_O + 0.2, rim=0.25))
    for s in (-1, 1):
        F.add(cyl("Y", (PX, PZ), 1.9, s * (WALL_O + 0.0), s * (WALL_O + 1.1), rim=0.45), 0.25,
              bbox=bb(PX - 3, PX + 3, s * (WALL_O - 0.3), s * (WALL_O + 1.5), PZ - 3, PZ + 3))
    return F


def spring(h):
    """Пластинчатая пружина планки: приклёпана к дну колодки сзади, свободным концом упирается в планку снизу."""
    F = Field("Rear_Sight_Spring", (-278, -1.0, 35), (-232, 4.6, 47.5), h)
    path = Path2(fillet_path([(-277.0, 36.55 + 0.0), (-268.0, 36.55), (-251.0, 41.2), (-238.0, 45.6)], [4.0, 6.0]))
    F.add(strip(path, "XZ", 0.7, 0.0, 3.6, rim=0.25))
    # заклёпки на дне
    for x in (-274.5, -270.5):
        F.add(cyl("Z", (x, 1.8), 1.1, 36.0, 37.55, rim=0.35), 0.2, bbox=bb(x - 2, x + 2, 0, 3.6, 35.5, 38.2))
    return F


# ---------- мушка (единицы part_barrel: умножаются на U) ----------

def front_post(h):
    F = Field("Front_Sight_Post", (POST_X - 4, -4, 45), (POST_X + 4, 4, POST_TOP + 1.5), h, unit=U)
    c = (POST_X, 0.0)
    # буртик с насечкой, стержень, закруглённая вершина
    F.add(cyl("Z", c, 2.95, 45.65, 49.3, rim=0.4))

    def knurl(X, Y, Z):
        ang = np.arctan2(Y, X - POST_X)
        return 0.14 * (0.5 + 0.5 * np.cos(ang * 24.0)) * smoothstep((Z - 45.9) / 0.3) * smoothstep((49.0 - Z) / 0.3)

    F.displace(knurl, bbox=bb(POST_X - 4, POST_X + 4, -4, 4, 45.5, 49.5), fine=False)
    F.add(cyl("Z", c, 1.7, 49.0, POST_TOP, rim=0.8), 0.5, bbox=bb(POST_X - 3, POST_X + 3, -3, 3, 48.5, POST_TOP + 1))
    # шлиц под отвёртку в торце буртика не нужен (виден сверху у ушей): тонкая прорезь вдоль Y по буртику
    F.sub(box((POST_X - 3.2, -0.3, 48.6), (POST_X + 3.2, 0.3, 49.6), 0.1), 0.12, bbox=bb(POST_X - 4, POST_X + 4, -1, 1, 48, 50))
    return F


def parts():
    ax = [C, 0.0, S]
    wx, wz = W(U0, WB)
    fx, fz = W(FR_U, FR_W)
    return [
        dict(name="Rear_Sight_Base", build=base, h=0.12, coll="Прицел", mat="Steel_blued", parent="Top_Cover", adapt=0.1),
        dict(name="Rear_Sight_Pin", build=pin, h=0.08, coll="Прицел", mat="Steel_phosphate", parent="Rear_Sight_Base",
             pivot=[PX, 0.0, PZ]),
        dict(name="Rear_Sight_Spring", build=spring, h=0.08, coll="Прицел", mat="Spring_steel", parent="Rear_Sight_Base"),
        dict(name="Rear_Sight_Leaf", build=leaf, h=0.1, coll="Прицел", mat="Steel_blued", parent="Rear_Sight_Base",
             pivot=[PX, 0.0, PZ]),            # ось Y; угол подъёма планки +TH уже в форме (вокруг оси вверх — до ~15°, оценка)
        dict(name="Rear_Sight_Slider", build=slider, h=0.08, coll="Прицел", mat="Steel_blued", parent="Rear_Sight_Leaf",
             pivot=[wx, 0.0, wz]),            # ход вдоль планки: вектор (%.4f, 0, %.4f), от «1» (+0) к «15» минус %.1f мм
        dict(name="Rear_Sight_Button", build=button, h=0.08, coll="Прицел", mat="Steel_phosphate", parent="Rear_Sight_Slider",
             pivot=[wx, -13.0, wz]),          # утапливается вдоль +Y на 1,5 мм (ось кнопки параллельна Y)
        dict(name="Rear_Sight_Notch", build=notch, h=0.08, coll="Прицел", mat="Steel_blued", parent="Rear_Sight_Leaf",
             pivot=[fx, 0.0, fz]),            # скользит вдоль Y, ход ±1,9 мм
        dict(name="Rear_Sight_Knob", build=knob, h=0.07, coll="Прицел", mat="Steel_phosphate", parent="Rear_Sight_Leaf",
             pivot=[fx, 0.0, fz]),            # вращается вокруг оси Y через точку
        dict(name="Front_Sight_Post", build=front_post, h=0.07, coll="Прицел", mat="Steel_phosphate",
             parent="Front_Sight_Base", pivot=[POST_X * U, 0.0, 45.65 * U], unit=U),   # ввёртывается вдоль Z
    ]


def check_line():
    """Расчёт линии прицеливания: дно прорези → вершина мушки; зазор над ручкой для переноски (верх Z = 53·U на X от −15 до 118)."""
    nx, nz = W(FR_U, NOTCH_BOTTOM_W)
    px, pz = POST_X * U, POST_TOP * U
    out = [f"прорезь: X {nx:.1f} Z {nz:.2f}; вершина мушки: X {px:.1f} Z {pz:.2f}"]
    for x in (-15.0, 40.0, 118.0):
        z = nz + (pz - nz) * (x - nx) / (px - nx)
        out.append(f"X {x:6.1f}: линия Z {z:.2f}, верх ручки {53.0 * U:.2f}, запас {z - 53.0 * U:.2f}")
    return out


if __name__ == "__main__":
    print(*check_line(), sep="\n")
