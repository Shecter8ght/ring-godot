"""Купе Ильи: подкапотное пространство и внутренняя сторона капота.

Под заказ «Вернуть машину»: снимки подкапотного, места радиатора и проводки у аккумулятора.
Радиатор снят (его возвращают отдельным предметом) — видна пустая рамка, висят концы патрубков.
Аккумулятор — в двух видах: стоит на полке с клеммами / снят, клеммы висят на проводах.
Свой двигатель (рядная «шестёрка» под широкой крышкой со знаком «Клин»), без чужих эмблем.

Левый борт +X, перёд −Y. Только numpy; детали — скруглённые блоки, трубы и тела вращения.
"""
from __future__ import annotations

import math

import numpy as np

import parts as pt
from surface import resample, spline2d


def rounded_block(c, sx: float, sy: float, sz: float, r: float, n_r: int = 4):
    """Блок со скруглёнными рёбрами (радиус r): сечения по высоте, у верха и низа — сужение по дуге."""
    c = np.asarray(c, dtype=float)
    r = min(r, sx / 2 * 0.98, sy / 2 * 0.98, sz / 2 * 0.98)
    zs, insets = [], []
    for k in range(n_r + 1):                      # низ: от скругления к полному сечению
        a = math.pi / 2 * (1 - k / n_r)
        zs.append(-sz / 2 + r * (1 - math.cos(a)))
        insets.append(r * (1 - math.sin(a)) if k < n_r else 0.0)
    for k in range(n_r + 1):                      # верх
        a = math.pi / 2 * k / n_r
        zs.append(sz / 2 - r * (1 - math.cos(a)))
        insets.append(r * (1 - math.cos(math.pi / 2 - a)) if k > 0 else 0.0)
    zs, insets = np.array(zs), np.array(insets)
    path = np.c_[np.full(len(zs), c[0]), np.full(len(zs), c[1]), c[2] + zs]
    U = np.broadcast_to(np.array([1.0, 0, 0]), path.shape)
    V = np.broadcast_to(np.array([0, 1.0, 0]), path.shape)

    def sec(i):
        w, d = sx - 2 * insets[i], sy - 2 * insets[i]
        return pt.rounded_rect(max(w, 1e-4), max(d, 1e-4), max(r - insets[i], 1e-4), 4)
    return pt.loft(path, U, V, sec, cap=True)


def tube(points, radius: float, n_sec: int = 14, samples: int = 40):
    """Шланг / провод: гладкая кривая через точки и круглое сечение."""
    P = np.asarray(points, dtype=float)
    # сглаживание по проекциям на XY и XZ: Кэтмелл — Ром покоординатно
    t = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    s = np.linspace(0, t[-1], samples)
    path = np.stack([np.interp(s, t, P[:, k]) for k in range(3)], 1)
    if len(P) > 2:
        xy = spline2d(P[:, :2], samples)
        xz = spline2d(P[:, [0, 2]], samples)
        path = np.c_[xy[:, 0], xy[:, 1], xz[:, 1]]
    T, N, B = pt.frames(path, np.array([0, 0, 1.0]) if abs(np.ptp(path[:, 2])) < np.ptp(path[:, 0]) + 1e-6 else np.array([1.0, 0, 0]))
    ang = np.linspace(0, 2 * math.pi, n_sec, endpoint=False)
    circ = np.c_[np.cos(ang), np.sin(ang)] * radius
    return pt.loft(path, N, B, circ, cap=True)


def hose_clamp(center, axis, radius: float):
    """Хомут: узкое кольцо поверх шланга с «ушком» винта."""
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    P = np.linspace(np.asarray(center) - axis * 0.006, np.asarray(center) + axis * 0.006, 3)
    T, N, B = pt.frames(P, np.array([0, 0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0, 0]))
    ang = np.linspace(0, 2 * math.pi, 18, endpoint=False)
    ring = pt.loft(P, N, B, np.c_[np.cos(ang), np.sin(ang)] * (radius + 0.0025), cap=True)
    ear = rounded_block(np.asarray(center) + N[1] * (radius + 0.007), 0.012, 0.012, 0.010, 0.002)
    return pt.merge([ring, ear])


# --- Конструкция моторного отсека ----------------------------------------------------------------

def aprons():
    """Брызговики (стенки отсека), стаканы стоек, моторный щит с поддоном под коробом."""
    parts = []
    for side in (1, -1):
        # стенка брызговика: скруглённая плита вдоль машины
        parts.append(rounded_block((side * 0.635, -1.43, 0.62), 0.03, 0.96, 0.40, 0.012))
        # полка к верху крыла (не доходит до фары: нос там ниже)
        parts.append(rounded_block((side * 0.71, -1.40, 0.815), 0.15, 0.88, 0.022, 0.009))
        # стакан стойки: тело вращения (купол)
        prof = [(0.0, 0.0), (0.0, 0.115), (0.10, 0.105), (0.16, 0.085), (0.20, 0.060), (0.215, 0.0)]
        from wheel import revolve
        v, f = revolve(prof, 40, closed=False)
        v = v[:, [1, 2, 0]]                       # ось — вертикаль
        v += np.array([side * 0.560, -1.435, 0.68])
        parts.append((v, f))
    # моторный щит и поддон под коробом
    parts.append(rounded_block((0.0, -0.955, 0.66), 1.30, 0.035, 0.60, 0.012))
    parts.append(rounded_block((0.0, -0.900, 0.965), 1.36, 0.12, 0.04, 0.012))
    return pt.merge(parts)


def radiator_frame():
    """Рамка радиатора (передняя панель): верхняя поперечина, стойки, нижняя; радиатор снят."""
    parts = [
        rounded_block((0.0, -2.035, 0.770), 1.18, 0.07, 0.055, 0.012),       # верхняя поперечина
        rounded_block((0.0, -2.035, 0.300), 1.10, 0.06, 0.05, 0.012),        # нижняя
    ]
    for side in (1, -1):
        parts.append(rounded_block((side * 0.565, -2.035, 0.535), 0.06, 0.07, 0.45, 0.012))   # стойка
        # резиновые опоры радиатора (пустые гнёзда) снизу и кронштейны сверху
        parts.append(rounded_block((side * 0.42, -2.02, 0.333), 0.05, 0.05, 0.030, 0.010))
        parts.append(rounded_block((side * 0.42, -2.02, 0.738), 0.05, 0.05, 0.025, 0.008))
        # тяга от поперечины к стакану стойки
        parts.append(tube([(side * 0.50, -2.00, 0.78), (side * 0.53, -1.75, 0.80), (side * 0.56, -1.47, 0.79)], 0.016))
    return pt.merge(parts)


def engine():
    """Свой двигатель: блок, головка, широкая крышка с рёбрами и знаком, впуск слева."""
    parts = [
        rounded_block((0.0, -1.30, 0.55), 0.36, 0.66, 0.34, 0.03),            # блок
        rounded_block((0.0, -1.30, 0.75), 0.30, 0.68, 0.08, 0.02),            # головка
        rounded_block((0.0, -1.27, 0.835), 0.56, 0.72, 0.075, 0.035),         # крышка двигателя
        rounded_block((0.0, -1.20, 0.877), 0.30, 0.46, 0.014, 0.006),         # накладка на крышке
    ]
    for x in (-0.10, 0.10):
        parts.append(rounded_block((x, -1.24, 0.886), 0.022, 0.40, 0.010, 0.004))   # рёбра накладки
    # впускной патрубок от фильтра (слева спереди) к крышке
    parts.append(tube([(0.44, -1.80, 0.72), (0.38, -1.66, 0.78), (0.24, -1.58, 0.80), (0.12, -1.55, 0.80)], 0.042))
    # корпус воздушного фильтра
    parts.append(rounded_block((0.46, -1.86, 0.66), 0.20, 0.26, 0.17, 0.03))
    # корпус термостата спереди слева и патрубок насоса справа снизу — концы шлангов к радиатору
    parts.append(rounded_block((0.10, -1.66, 0.66), 0.07, 0.07, 0.06, 0.014))
    parts.append(rounded_block((-0.12, -1.64, 0.43), 0.08, 0.08, 0.07, 0.016))
    return pt.merge(parts)


def badge_on_engine():
    return pt.badge(np.array([0.0, -1.42, 0.886]), (0, 0, 1), (0, -1, 0), 0.07, depth=0.004)


def hanging_hoses():
    """Патрубки снятого радиатора: верхний от термостата, нижний от насоса — концы висят, на них хомуты."""
    upper_pts = [(0.10, -1.70, 0.66), (0.14, -1.82, 0.67), (0.22, -1.92, 0.62), (0.27, -1.97, 0.55)]
    lower_pts = [(-0.12, -1.68, 0.43), (-0.20, -1.84, 0.40), (-0.30, -1.95, 0.34), (-0.34, -1.99, 0.28)]
    up = tube(upper_pts, 0.021)
    lo = tube(lower_pts, 0.023)
    c_up = hose_clamp(upper_pts[-1], np.subtract(upper_pts[-1], upper_pts[-2]), 0.021)
    c_lo = hose_clamp(lower_pts[-1], np.subtract(lower_pts[-1], lower_pts[-2]), 0.023)
    return pt.merge([up, lo]), pt.merge([c_up, c_lo])


def coolant_tank():
    return rounded_block((-0.50, -1.80, 0.72), 0.13, 0.16, 0.14, 0.03)


def fuse_box():
    return pt.merge([rounded_block((0.44, -1.04, 0.76), 0.20, 0.13, 0.09, 0.015),
                     rounded_block((0.44, -1.04, 0.807), 0.19, 0.12, 0.010, 0.004)])


def brake_reservoir():
    from wheel import revolve
    v, f = revolve([(0.0, 0.0), (0.0, 0.040), (0.07, 0.040), (0.075, 0.030), (0.085, 0.022), (0.095, 0.0)], 24)
    v = v[:, [1, 2, 0]] + np.array([0.56, -1.02, 0.80])
    return v, f


def strut_brace():
    bar = tube([(0.56, -1.435, 0.905), (0.0, -1.435, 0.915), (-0.56, -1.435, 0.905)], 0.019)
    feet = pt.merge([rounded_block((s * 0.56, -1.435, 0.898), 0.12, 0.10, 0.014, 0.005) for s in (1, -1)])
    return pt.merge([bar, feet])


# --- Аккумулятор: полка, сам аккумулятор с клеммами, провода -------------------------------------
BATT_C = np.array([-0.505, -1.11, 0.0])       # центр полки в плане
BATT_SIZE = (0.175, 0.315, 0.190)             # 80 А·ч: 315×175×190 мм
TRAY_Z = 0.515


def battery_tray():
    sx, sy, _ = BATT_SIZE
    return pt.merge([rounded_block((BATT_C[0], BATT_C[1], TRAY_Z - 0.010), sx + 0.03, sy + 0.03, 0.02, 0.006),
                     rounded_block((BATT_C[0], BATT_C[1] - sy / 2 - 0.012, TRAY_Z + 0.02), sx + 0.03, 0.01, 0.05, 0.004),
                     rounded_block((BATT_C[0], BATT_C[1] + sy / 2 + 0.012, TRAY_Z + 0.02), sx + 0.03, 0.01, 0.05, 0.004)])


def battery():
    """Аккумулятор в корпусе с крышкой, ручкой и двумя выводами; прижимная планка."""
    from wheel import revolve
    sx, sy, sz = BATT_SIZE
    zc = TRAY_Z + sz / 2
    body = rounded_block((BATT_C[0], BATT_C[1], zc - 0.008), sx, sy, sz - 0.016, 0.008)
    lid = rounded_block((BATT_C[0], BATT_C[1], TRAY_Z + sz - 0.009), sx + 0.004, sy + 0.004, 0.018, 0.006)
    posts = []
    for dy, name in ((-sy / 2 + 0.045, "+"), (sy / 2 - 0.045, "-")):
        v, f = revolve([(0.0, 0.0), (0.0, 0.0105), (0.020, 0.0095), (0.022, 0.0)], 18)
        v = v[:, [1, 2, 0]] + np.array([BATT_C[0] + 0.045, BATT_C[1] + dy, TRAY_Z + sz])
        posts.append((v, f))
    clamp_bar = rounded_block((BATT_C[0], BATT_C[1], TRAY_Z + sz + 0.004), sx + 0.02, 0.025, 0.008, 0.003)
    return pt.merge([body, lid]), pt.merge(posts), clamp_bar


def battery_cables(installed: bool):
    """Провода: плюс (красный) к блоку предохранителей, минус (чёрный) на кузов. Без аккумулятора клеммы висят."""
    sx, sy, sz = BATT_SIZE
    top = TRAY_Z + sz
    pos_term = np.array([BATT_C[0] + 0.045, BATT_C[1] - sy / 2 + 0.045, top + 0.012])
    neg_term = np.array([BATT_C[0] + 0.045, BATT_C[1] + sy / 2 - 0.045, top + 0.012])
    if not installed:
        pos_term = pos_term + np.array([0.06, -0.02, -0.11])     # клемма свисает с полки
        neg_term = neg_term + np.array([0.07, 0.03, -0.14])
    pos = tube([pos_term, pos_term + np.array([0.06, -0.02, 0.04]), (-0.20, -1.06, 0.80), (0.10, -1.00, 0.84),
                (0.38, -1.04, 0.80)], 0.0095)
    neg = tube([neg_term, neg_term + np.array([0.05, 0.03, 0.03]), (-0.56, -0.98, 0.72), (-0.60, -0.97, 0.66)], 0.0085)
    from wheel import revolve
    clamps = []
    for c in (pos_term, neg_term):
        v, f = revolve([(0.0, 0.0), (0.0, 0.016), (0.024, 0.016), (0.024, 0.0)], 12)
        v = v[:, [1, 2, 0]] + c - np.array([0, 0, 0.012])
        clamps.append((v, f))
    return pos, neg, pt.merge(clamps)



def brick(c, rot_z: float, seed: int):
    """Кирпич 250×120×65 с фасками и мелкими сколами (неровная поверхность, не ровный брусок)."""
    v, f = rounded_block((0, 0, 0), 0.250, 0.120, 0.065, 0.005, n_r=3)
    rng = np.random.default_rng(seed)
    # сколы: случайное вдавливание у рёбер, сильнее на углах
    edge = (np.abs(v[:, 0]) > 0.115).astype(float) + (np.abs(v[:, 1]) > 0.050) + (np.abs(v[:, 2]) > 0.027)
    v = v - np.sign(v) * (rng.random(v.shape) * 0.0025) * (edge[:, None] >= 2)
    ca, sa = math.cos(rot_z), math.sin(rot_z)
    v = v @ np.array([[ca, sa, 0], [-sa, ca, 0], [0, 0, 1]])
    return v + np.asarray(c, float), f


def bricks_under_hub(x: float, y: float):
    """Стопка из трёх рядов (2 + 2 поперёк + 1) под поворотным кулаком снятого колеса."""
    out = []
    h = 0.065
    out.append(brick((x - 0.000, y - 0.065, h / 2), 0.0, 1))
    out.append(brick((x + 0.005, y + 0.062, h / 2), 0.02, 2))
    out.append(brick((x - 0.060, y, h * 1.5), math.pi / 2 + 0.03, 3))
    out.append(brick((x + 0.062, y + 0.004, h * 1.5), math.pi / 2 - 0.02, 4))
    out.append(brick((x, y - 0.006, h * 2.5), 0.05, 5))
    return pt.merge(out)


def knuckle(side: float, y: float):
    """Поворотный кулак и нижний рычаг (видны, когда колесо снято): от ступицы вниз к опоре."""
    hubc = np.array([side * 0.775, y, 0.343])
    parts = [rounded_block(hubc + np.array([-side * 0.045, 0, -0.045]), 0.06, 0.09, 0.17, 0.02),
             rounded_block(hubc + np.array([-side * 0.075, 0, -0.130]), 0.10, 0.07, 0.035, 0.012),
             tube([hubc + np.array([-side * 0.09, 0.0, -0.14]), np.array([side * 0.50, y + 0.10, 0.24]),
                   np.array([side * 0.36, y + 0.16, 0.24])], 0.022)]
    return pt.merge(parts)
