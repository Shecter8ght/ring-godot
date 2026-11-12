# АСТЕН-919: магазин на 17 патронов (прототип — Glock 17 Gen4): корпус с губками и окошками счёта, замковая вставка,
# пятка, подаватель, пружина, патроны 9×19 (линейка CIP) и стреляная гильза. Размеры и раскладка патронов — dims.py и
# ТЗ магазина; трубка наклонена на GRIP_DEG, верх и низ — горизонтальные плоскости (в профиль параллелограмм).
# Работаем в «косых» координатах (s, y, z): s — расстояние от передней стенки трубки по перпендикуляру к её оси
# (перед 0, зад −33), z — настоящая высота. Так вырезы по высоте остаются горизонтальными, а сечение — прямоугольным.
import math

import numpy as np

from dims import *
from sdf import *

WALL = 1.6                      # стенка трубки
BOT = MAG_BOT_Z                 # низ корпуса
TOP = -8.8                      # верх губок
TAPER_Z0 = -32.5                # с этой высоты бока сходятся к единой подаче (ниже 3-го патрона — двухрядно)
HW_TOP = 7.8                    # полуширина корпуса у губок (15,6)
FRONT_TAPER = 1.0               # передние 8 мм сечения уже на 2×1 мм (22,4 → 20,4)
SLOT_REAR, SLOT_FRONT = 4.7, 5.6        # полуширина щели губок сзади и спереди (9,4 → ~11,2)
LIP_Z = -11.4                   # нижний край внутренней кромки губки
RIM_R = 4.98                    # радиус закраины гильзы
D_STACK = 9.97                  # шаг между осями соседних патронов вдоль «ёлочки»
ROUND_X1 = 29.69                # полная длина патрона
INS_Z0, INS_Z1 = -120.2, -118.7  # вставка: низ и верх
SEAT_TOP = -118.1               # верх упорной площадки под пружину
FLANGE_H, FLANGE_OUT = 1.2, 0.9  # полки пятки по бокам низа корпуса


def bb(x0, x1, y0, y1, z0, z1):
    return ((min(x0, x1), min(y0, y1), min(z0, z1)), (max(x0, x1), max(y0, y1), max(z0, z1)))


# ---------- косые координаты ----------

def S(X, Z):
    """Расстояние от передней стенки трубки (по перпендикуляру к оси): перед 0, зад −MAG_DEPTH."""
    return COS * (X - MAG_REF[0]) - SIN * (Z - MAG_REF[1])


def wx(s: float, z: float) -> float:
    """Мировой X точки (s, z)."""
    return (s + SIN * (z - MAG_REF[1])) / COS + MAG_REF[0]


def wb(s0, s1, y0, y1, z0, z1):
    """Окно в мире для области, заданной в косых координатах."""
    xs = [wx(s, z) for s in (s0, s1) for z in (z0, z1)]
    return ((min(xs), min(y0, y1), min(z0, z1)), (max(xs), max(y0, y1), max(z0, z1)))


def sk(fn):
    """Тело, заданное в косых координатах (s, y, z), — в мировых."""
    def f(X, Y, Z):
        return fn(S(X, Z), Y, Z)
    return f


def hwz(Z):
    """Наружная полуширина корпуса на высоте Z: 11,2 внизу, к губкам сужается плавно до 7,8."""
    return MAG_HW - (MAG_HW - HW_TOP) * smoothstep((Z - TAPER_Z0) / (TOP - TAPER_Z0))


def sec(s, y, hw, s0, s1, rr, rf):
    """Скруглённый прямоугольник сечения (s, y): сзади углы rr, спереди rf, передние 8 мм сужены."""
    hwf = hw - FRONT_TAPER * smoothstep((s + 8.0) / 8.0)
    sc = (s0 + s1) / 2
    hs = (s1 - s0) / 2
    R = np.where(s > sc, rf, rr)
    qs = np.abs(s - sc) - (hs - R)
    qy = np.abs(y) - (hwf - R)
    return np.hypot(np.maximum(qs, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qs, qy), 0) - R


def sec_out(s, y, z):
    return sec(s, y, hwz(z), -MAG_DEPTH, 0.0, 3.0, 4.0)


def sec_in(s, y, z, inset=0.0):
    """Внутренняя полость трубки (со стенкой WALL), inset — дополнительный зазор внутрь."""
    w = WALL + inset
    return sec(s, y, hwz(z) - w, -MAG_DEPTH + w, -w, 3.0 - w, 4.0 - w)


def xc(z: float) -> float:
    """X оси трубки (середина сечения) на высоте z."""
    return wx(-MAG_DEPTH / 2, z)


# ---------- раскладка патронов ----------

def layout():
    """Патроны в магазине: [(X основания, Y, Z оси)] от верхнего (1) к нижнему (17)."""
    ys = [0.0, 3.2] + [(-4.3 if k % 2 == 0 else 4.3) for k in range(2, 17)]
    zs = [-14.2]
    for k in range(1, 17):
        zs.append(zs[-1] - math.sqrt(D_STACK ** 2 - (ys[k] - ys[k - 1]) ** 2))
    # патрон горизонтален, а трубка наклонена: внутри по горизонтали запас всего ~0,3 мм (верх закраины упирается в заднюю
    # стенку выше оси, нос — в переднюю ниже), поэтому основание ставим посередине запаса, а не «стенка + 0,4»
    return [(mag_rear_x(z) + WALL / COS + 2.03, y, z) for y, z in zip(ys, zs)]


ROUNDS = layout()
Z17 = ROUNDS[16][2]
FOL_TOP = Z17 - 2.7             # верх подавателя (плоская часть под последним патроном)
FOL_UNDER = FOL_TOP - 4.0       # низ плиты подавателя (внутри ножек)


# ---------- корпус ----------

def body(h):
    lo = (wx(-MAG_DEPTH, BOT) - 1.5, -MAG_HW - FLANGE_OUT - 0.6, BOT - 0.8)
    hi = (wx(0.0, TOP) + 1.5, MAG_HW + FLANGE_OUT + 0.6, TOP + 0.8)
    F = Field("Magazine_Body", lo, hi, h)
    F.add(sk(lambda s, y, z: i_round(i_round(sec_out(s, y, z), BOT - z, 0.6), z - TOP, 0.5)),
          bbox=bb(lo[0], hi[0], -13, 13, BOT - 0.5, TOP + 0.5), slab_n=24)
    # полость: открыта сверху и снизу
    F.sub(sk(lambda s, y, z: sec_in(s, y, z)), 0.3, bbox=bb(lo[0], hi[0], -13, 13, BOT - 1.0, TOP + 1.0), slab_n=24)

    # губки: щель шире спереди, внутренняя кромка вертикальная, снизу скос к стенке
    def lip(s, y, z):
        ay = np.abs(y)
        hs = SLOT_REAR + (SLOT_FRONT - SLOT_REAR) * np.clip((s + 29.4) / 27.8, 0, 1)
        d = np.maximum(sec(s, y, hwz(z) - WALL + 0.25, -MAG_DEPTH + WALL - 0.25, -WALL + 0.25, 1.6, 2.6), z - TOP)
        d = i_round(d, hs - ay, 0.6)
        return i_round(d, (LIP_Z + (ay - hs) * 0.82) - z, 0.5)
    F.add(sk(lip), 0.35, bbox=wb(-32.0, -1.0, -9, 9, -13, TOP + 0.2))

    # задняя верхняя стенка ниже: проход для упора затвора (нижний край −11,5)
    F.sub(sk(box((-40, -13, -11.5), (-29.4, 13, -5), 0.0)), 0.5, bbox=wb(-36, -28, -13, 13, -12.5, -7))
    # U-вырез в передней стенке под нос пули (до −17)
    u = Poly(fillet_poly([(-5.2, -7.0), (5.2, -7.0), (3.3, -17.0), (-3.3, -17.0)], [0.0, 0.0, 1.8, 1.8]))
    F.sub(sk(prism(u, "YZ", -3.0, 1.5)), 0.5, bbox=wb(-4, 1.5, -6, 6, -17.5, -7))

    # окошки счёта: 14 отверстий Ø2,8 с фаской 0,3, левый ряд — чётные патроны (4…16), правый — нечётные (5…17)
    for k in range(4, 18):
        x_b, _, z = ROUNDS[k - 1]
        yc = 3.6 if k % 2 == 0 else -3.6
        ac = SIN * mag_rear_x(z) + COS * z

        def hole(X, Y, Z, yc=yc, ac=ac):
            s = S(X, Z)
            a = SIN * X + COS * Z
            dr = np.hypot(Y - yc, a - ac)
            d_c = np.maximum(dr - 1.4, np.abs(s + 32.5) - 1.5)
            d_cs = np.maximum(dr - (1.4 + (-32.7 - s)), s + 32.7)
            return np.minimum(d_c, d_cs)
        F.sub(hole, 0.0, bbox=wb(-34, -30.5, yc - 2.5, yc + 2.5, z - 3.0, z + 3.0))

    # вырезы под защёлку магазина (Gen4) на обоих передних углах: мельче на прямой части, где стенка тоньше
    def notch(s, y, z):
        ay = np.abs(y)
        depth = 1.0 + 0.8 * smoothstep((ay - 6.8) / 1.4)
        d = np.maximum(np.maximum(-depth - s, np.abs(ay - 8.65) - 2.95), np.abs(z + 45.0) - 2.3)
        return d
    F.sub(sk(notch), 0.25, bbox=wb(-3, 1.5, -12.5, 12.5, -47.6, -42.4))

    # неглубокая площадка 9 × 14 под фирменный знак внизу задней грани (пустая)
    F.sub(sk(box((-33.6, -4.5, -116.5), (-32.7, 4.5, -102.5), 0.4)), 0.3, bbox=wb(-34, -32, -5, 5, -117, -102))

    # полки пятки по бокам низа: пятка надевается спереди
    flange = both(box((-29.5, MAG_HW - 0.1, BOT), (-8.5, MAG_HW + FLANGE_OUT, BOT + FLANGE_H), 0.4))
    F.add(sk(flange), 0.3, bbox=wb(-30, -8, -13, 13, BOT - 0.5, BOT + 2))
    return F


# ---------- пятка ----------

def floorplate(h):
    xr = mag_rear_x(BOT) - 2.2
    xf = mag_front_x(BOT) + 3.7
    zb, zt = -127.0, -120.7
    F = Field("Magazine_Floorplate", (xr - 1, -14, zb - 1), (xf + 1, 14, -118.0), h)
    side = Poly(fillet_poly([(xr, zb), (xf, zb), (xf, zt), (xr, zt)], [1.0, 3.0, 3.0, 1.0]))
    F.add(prism(side, "XZ", -13.0, 13.0, rim=1.0))
    # C-образные направляющие: стенки снаружи полок и губы поверх них (спереди открыты — пятка сдвигается вперёд)
    x0, x1 = mag_rear_x(BOT) - 0.3, mag_front_x(BOT) + 0.6
    for sg in (-1, 1):
        wall = box((x0, min(sg * 12.25, sg * 13.0), zt - 0.6), (x1, max(sg * 12.25, sg * 13.0), -118.4), 0.3)
        lipb = box((x0, min(sg * 11.3, sg * 13.0), -119.3), (x1, max(sg * 11.3, sg * 13.0), -118.4), 0.3)
        F.add(union(wall, lipb), 0.4, bbox=bb(x0, x1, -13.5, 13.5, zt - 0.8, -118.0))
    # сквозное отверстие Ø3,4 под штифт вставки
    xp = xc(INS_Z0)
    F.sub(cyl("Z", (xp, 0.0), 1.7, zb - 1, zt + 0.1), 0.3, bbox=bb(xp - 2.5, xp + 2.5, -2.5, 2.5, zb - 1, zt + 0.5))
    return F


# ---------- вставка ----------

def insert(h):
    xp = xc(INS_Z0)
    lo = (wx(-MAG_DEPTH, INS_Z0) - 1, -11, INS_Z0 - 2.8)
    hi = (wx(0.0, INS_Z1) + 1, 11, SEAT_TOP + 0.5)
    F = Field("Magazine_Insert", lo, hi, h)
    plate = sk(lambda s, y, z: i_round(i_round(sec_in(s, y, z, 0.12), z - INS_Z1, 0.4), INS_Z0 - z, 0.4))
    F.add(plate, bbox=bb(lo[0], hi[0], -11, 11, INS_Z0 - 0.5, INS_Z1 + 0.5))
    # упорная площадка под пружину
    xs = xc(INS_Z1)
    seat = Poly(fillet_poly([(xs - 14.0, -8.0), (xs + 14.0, -8.0), (xs + 14.0, 8.0), (xs - 14.0, 8.0)], 4.5))
    F.add(prism(seat, "XY", INS_Z1 - 0.3, SEAT_TOP, rim=0.2), 0.25, bbox=bb(xs - 15, xs + 15, -9, 9, INS_Z1 - 0.5, SEAT_TOP + 0.3))
    # штифт Ø3,0 длиной 2,2 вниз, в отверстие пятки
    F.add(cyl("Z", (xp, 0.0), 1.5, INS_Z0 - 2.2, INS_Z0 + 0.3, rim=0.4), 0.3,
          bbox=bb(xp - 2, xp + 2, -2, 2, INS_Z0 - 2.5, INS_Z0 + 0.6))
    return F


# ---------- подаватель ----------

def follower(h):
    y16, z16 = ROUNDS[15][1], ROUNDS[15][2]
    y17 = ROUNDS[16][1]
    pad_top = z16 - 2.7
    lo = (wx(-MAG_DEPTH + 1, FOL_TOP - 12.5) - 1, -10, FOL_TOP - 12.5)
    hi = (wx(-1, pad_top + 3.0) + 1, 10, pad_top + 3.0)
    F = Field("Magazine_Follower", lo, hi, h)
    cav = lambda s, y, z: sec_in(s, y, z, 0.3)
    block = sk(lambda s, y, z: i_round(i_round(cav(s, y, z), z - FOL_TOP, 0.6), (FOL_TOP - 12.0) - z, 0.4))
    F.add(block, bbox=bb(lo[0], hi[0], -10, 10, FOL_TOP - 12.5, FOL_TOP + 0.5))
    # ножки спереди и сзади (по 1,5 мм), между ними гнездо под пружину
    F.sub(sk(box((-29.6, -12, FOL_TOP - 13), (-3.3, 12, FOL_UNDER), 0.5)), 0.4,
          bbox=wb(-31, -2, -11, 11, FOL_TOP - 13, FOL_UNDER + 0.5))
    # слева приподнятая часть под 16-й патрон и язычок упора затворной задержки в переднем левом углу
    pad = sk(lambda s, y, z: i_round(i_round(cav(s, y, z), z - pad_top, 0.5), 1.1 - y, 0.5))
    F.add(pad, 0.5, bbox=wb(-31, -1.5, 0, 10, FOL_TOP - 1.0, pad_top + 0.5))
    tab = sk(lambda s, y, z: i_round(cav(s, y, z), np.maximum(np.maximum(np.abs(s + 3.4) - 1.5, np.abs(y - 7.3) - 2.0),
                                                              np.maximum(pad_top - 0.3 - z, z - (pad_top + 2.5))), 0.4))
    F.add(tab, 0.3, bbox=wb(-5.2, -1.5, 4.5, 10, pad_top - 0.5, pad_top + 3))
    # седло R5,1 вдоль X под каждый из двух нижних патронов
    F.sub(cyl("X", (y17, Z17), 5.1, lo[0] - 1, hi[0] + 1), 0.3, bbox=bb(lo[0], hi[0], y17 - 6, y17 + 6, Z17 - 6, FOL_TOP + 1))
    F.sub(cyl("X", (y16, z16), 5.1, lo[0] - 1, hi[0] + 1), 0.3, bbox=bb(lo[0], hi[0], y16 - 6, y16 + 6, z16 - 6, pad_top + 3))
    return F


# ---------- пружина ----------

def rrect_path(L=26.0, W=14.0, R=4.0, n_arc=24):
    """Замкнутый скруглённый прямоугольник (x, y) от середины передней стороны против часовой; возвращает (длины, точки)."""
    a, b = L / 2 - R, W / 2 - R
    pts = [(L / 2, 0.0)]
    corners = [(a, b, 0), (-a, b, 90), (-a, -b, 180), (a, -b, 270)]
    for cx, cy, a0 in corners:
        for k in range(n_arc + 1):
            t = math.radians(a0 + 90.0 * k / n_arc)
            pts.append((cx + R * math.cos(t), cy + R * math.sin(t)))
    pts.append((L / 2, 0.0))
    p = np.array(pts)
    seg = np.hypot(*np.diff(p, axis=0).T)
    return np.concatenate([[0.0], np.cumsum(seg)]), p


def spring():
    """Пружина прямоугольного витка (проволока Ø1,2, 9 витков): горизонтальные витки со сдвигом по оси трубки."""
    wr = 0.6
    z_lo, z_hi = SEAT_TOP + wr + 0.03, FOL_UNDER - wr - 0.03
    turns, per, m = 9.0, 36, 12
    cum, path = rrect_path()
    n = int(turns * per) + 1
    u = np.linspace(0.0, turns, n)
    # подъём по виткам: концы почти сомкнуты (шаг 1,2), середина — равномерно
    knots_u = np.array([0.0, 0.2, 1.2, 7.8, 8.8, 9.0])
    mid = (z_hi - z_lo - 2.4) / 6.6
    knots_z = z_lo + np.array([0.0, 0.0, 1.2, 1.2 + 6.6 * mid, 2.4 + 6.6 * mid, 2.4 + 6.6 * mid])
    z = np.interp(u, knots_u, knots_z)
    f = (u % 1.0)
    f[-1] = 1.0
    px = np.interp(f * cum[-1], cum, path[:, 0])
    py = np.interp(f * cum[-1], cum, path[:, 1])
    cx = np.array([xc(v) for v in z])
    P = np.stack([cx + px, py, z], axis=1)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    N = np.array([0.0, 0.0, 1.0])[None, :] - T[:, 2:3] * T
    N /= np.linalg.norm(N, axis=1)[:, None]
    B = np.cross(T, N)
    ph = np.arange(m) * 2 * math.pi / m
    ring = np.cos(ph)[None, :, None] * N[:, None, :] + np.sin(ph)[None, :, None] * B[:, None, :]
    V = (P[:, None, :] + wr * ring).reshape(-1, 3)
    faces = []
    for i in range(n - 1):
        for k in range(m):
            a, b = i * m + k, i * m + (k + 1) % m
            faces.append((a, b, b + m, a + m))
    cap0 = len(V)
    cap1 = cap0 + 1
    V = np.vstack([V, P[0], P[-1]])
    for k in range(0, m, 2):
        a, b, c = k, (k + 1) % m, (k + 2) % m
        faces.append((cap0, c, b, a))
        o = (n - 1) * m
        faces.append((cap1, o + a, o + b, o + c))
    return V.astype(np.float32), np.array(faces, np.int32)


# ---------- патрон 9×19 ----------

def lathe(prof, mats, n=64):
    """Тело вращения вокруг +X: prof — точки (x, r) от оси до оси, mats[i] — материал отрезка prof[i] → prof[i+1].
    На оси торцы — веером четырёхугольников от центральной вершины."""
    V = []
    idx = []
    ang = np.arange(n) * 2 * math.pi / n
    for x, r in prof:
        if r < 1e-9:
            idx.append(len(V))
            V.append((x, 0.0, 0.0))
        else:
            idx.append(np.arange(len(V), len(V) + n))
            V.extend((x, r * math.cos(a), r * math.sin(a)) for a in ang)
    faces, fm = [], []
    for i in range(len(prof) - 1):
        a, b = idx[i], idx[i + 1]
        ai, bi = isinstance(a, (int, np.integer)), isinstance(b, (int, np.integer))
        if ai and bi:
            continue
        if ai:
            for k in range(0, n, 2):
                faces.append((a, b[k], b[(k + 1) % n], b[(k + 2) % n])); fm.append(mats[i])
        elif bi:
            for k in range(0, n, 2):
                faces.append((a[(k + 2) % n], a[(k + 1) % n], a[k], b)); fm.append(mats[i])
        else:
            for k in range(n):
                faces.append((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k])); fm.append(mats[i])
    return np.array(V, np.float32), np.array(faces, np.int32), np.array(fm, np.int32)


class Profile:
    """Контур (x, r): точки и материал отрезка, ведущего в каждую следующую точку."""

    def __init__(self, x, r):
        self.p = [(x, r)]
        self.m = []

    def to(self, x, r, mat):
        self.p.append((x, r)); self.m.append(mat)

    def arc(self, cx, cy, rad, a0, a1, mat, steps=5):
        for k in range(1, steps + 1):
            t = math.radians(a0 + (a1 - a0) * k / steps)
            self.to(cx + rad * math.cos(t), cy + rad * math.sin(t), mat)


def case_outside(pr, mat_brass, mat_primer, dimple):
    """Донце и наружная поверхность гильзы до среза; возвращает радиус среза."""
    if dimple:
        # ударник оставил лунку Ø1,4 глубиной 0,5 на капсюле
        pr.p[0] = (0.6, 0.0)
        for k in range(1, 8):
            r = 0.7 * k / 7
            pr.to(0.1 + 0.5 * (1 + math.cos(math.pi * r / 0.7)) / 2, r, mat_primer)
    else:
        pr.p[0] = (0.1, 0.0)
    pr.to(0.1, 1.95, mat_primer)
    pr.arc(0.3, 2.025, 0.2, 180, 90, mat_primer, 4)          # скруглённая кромка капсюля, он утоплен на 0,1
    pr.to(0.8, 2.225, mat_primer)
    pr.to(0.8, 2.375, mat_brass)                             # кольцевой зазор 0,15 вокруг капсюля
    pr.to(0.2, 2.375, mat_brass)
    pr.to(0.0, 2.575, mat_brass)                             # фаска гнезда
    pr.to(0.0, 4.68, mat_brass)
    pr.to(0.3, RIM_R, mat_brass)                             # фаска закраины 0,3
    pr.to(0.97, RIM_R, mat_brass)
    pr.to(1.27, 4.68, mat_brass)
    pr.to(1.27, 4.395, mat_brass)                            # проточка под зацеп выбрасывателя Ø8,79
    pr.to(2.385, 4.395, mat_brass)
    pr.to(3.2, 4.965, mat_brass)                             # передний конус 35° к корпусу Ø9,93
    pr.to(19.15, 4.825, mat_brass)                           # корпус сужается к дульцу Ø9,65


def cartridge():
    """Патрон 9×19 (CIP): гильза, пуля FMJ с касательной оживальной головкой, капсюль; ось +X, донце в X=0."""
    pr = Profile(0.1, 0.0)
    case_outside(pr, 0, 2, False)
    pr.to(19.15, 4.605, 0)                                   # срез дульца
    pr.to(19.15, 4.505, 0)                                   # ступенька 0,1 к пуле Ø9,01
    x_t, rb, r_e, x_e = 22.7, 4.505, 1.5, ROUND_X1 - 0.45
    rho = ((x_e - x_t) ** 2 + (r_e - rb) ** 2) / (2 * (rb - r_e))
    th_e = math.asin((x_e - x_t) / rho)
    pr.to(x_t, rb, 1)
    for k in range(1, 15):
        th = th_e * k / 14
        pr.to(x_t + rho * math.sin(th), rb - rho + rho * math.cos(th), 1)
    # головка: скругление R~0,8 к плоской площадке (квадратичная кривая по касательной)
    d = np.array([math.cos(th_e), -math.sin(th_e)])
    t = (ROUND_X1 - x_e) / d[0]
    c = (ROUND_X1, r_e + t * d[1])
    f_r = 0.6
    for k in range(1, 7):
        q = k / 6
        pr.to((1 - q) ** 2 * x_e + 2 * q * (1 - q) * c[0] + q * q * ROUND_X1,
              (1 - q) ** 2 * r_e + 2 * q * (1 - q) * c[1] + q * q * f_r, 1)
    pr.to(ROUND_X1, 0.0, 1)
    return lathe(pr.p, pr.m)


def empty_case():
    """Стреляная гильза: открытый срез, стенка 0,3 у среза утолщается к дну, на капсюле лунка от ударника."""
    pr = Profile(0.6, 0.0)
    case_outside(pr, 0, 1, True)
    pr.to(19.15, 4.525, 0)
    out = lambda x: 4.965 - 0.14 * (x - 3.2) / 15.95
    for x in np.linspace(17.6, 5.4, 9):
        wall = 0.3 + 0.7 * float(smoothstep((14.0 - x) / 8.6))
        pr.to(float(x), out(float(x)) - wall, 0)
    for x, r in [(4.6, 3.9), (4.25, 3.75), (4.08, 3.45), (4.0, 3.0), (4.0, 0.0)]:
        pr.to(x, r, 0)
    V, Fc, M = lathe(pr.p, pr.m)
    a = math.radians(-20.0)
    R = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    return (V @ R.T + np.array([95.0, -118.0, -122.0])).astype(np.float32), Fc, M


def round_instances():
    out = []
    for k, (xb, y, z) in enumerate(ROUNDS, 1):
        out.append({"name": f"Round_{k:02d}", "matrix": [1, 0, 0, xb, 0, 1, 0, y, 0, 0, 1, z, 0, 0, 0, 1],
                    "parent": "Magazine_Body", "coll": "Magazine"})
    out.append({"name": "Round_9x19_loose", "coll": "Ammo", "matrix": [1, 0, 0, 45.0, 0, 1, 0, -105.0, 0, 0, 1, -122.0, 0, 0, 0, 1]})
    return out


def parts():
    ft = (xc(FOL_TOP), 0.0, FOL_TOP)
    return [
        dict(name="Magazine_Body", build=body, h=0.1, coll="Magazine", mat="Polymer_mag", weight=4),
        dict(name="Magazine_Floorplate", build=floorplate, h=0.08, coll="Magazine", mat="Polymer_mag", parent="Magazine_Body"),
        dict(name="Magazine_Insert", build=insert, h=0.08, coll="Magazine", mat="Polymer_mag", parent="Magazine_Body"),
        dict(name="Magazine_Follower", build=follower, h=0.08, coll="Magazine", mat="Polymer_mag", parent="Magazine_Body", pivot=ft,
             motion="ход вдоль оси трубы (−sin22°, 0, −cos22°); положение дано для 17 патронов; пустой магазин: +85.5 мм вверх по оси"),
        dict(name="Magazine_Spring", build=lambda h: spring(), h=0.1, coll="Magazine", mat="Spring_steel", parent="Magazine_Body"),
        dict(name="Round_9x19", build=lambda h: cartridge(), h=0.1, coll="Magazine", mats=["Brass", "Bullet_jacket", "Primer"],
             instances=round_instances()),
        dict(name="Case_9x19", build=lambda h: empty_case(), h=0.1, coll="Ammo", mats=["Brass", "Primer"]),
    ]
