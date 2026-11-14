# ПКП: патрон 7,62×54R (тело вращения сеткой), стреляная гильза, звено нерассыпной ленты ПК (стальное, закрытое,
# звенья сцеплены витой проволочной спиралью), наконечник ленты и сама лента на пулемёте (копии патрона и звена).
# Патрон — размеры C.I.P. (dims.py). Звено и наконечник — по фото настоящей ленты (refs/web/D_belt_ammo/05_pk_belt_studio.jpg,
# 03, 04), форма и размеры звена сняты с кадра 05 (кадры в refs/web/sources.md); числа, снятые «на глаз», помечены «оценка».
# Система координат патрона: ось вдоль X, донце гильзы на X = 0, пуля к +X (так он лежит на пулемёте: донце на FEED_RIM_X).
# Система звена: та же ось X; local +Y — направление к следующему звену (к дулу патрона — нет: вдоль ленты), local −Z —
# сторона, где у звена пластина-«рубашка» (в ленте на пулемёте она снаружи изгиба).
import math

import numpy as np

import dims
from dims import *
from sdf import *

try:                                                         # коробка пишется параллельно: пока её нет — временная точка
    import part_box as _pb
    BOX_EXIT = tuple(getattr(_pb, "BOX100_BELT_EXIT"))
    BOX_DIR = tuple(getattr(_pb, "BOX100_BELT_DIR"))
except Exception:                                            # noqa: BLE001
    BOX_EXIT = None
    BOX_DIR = None

# ---------------- патрон ----------------
SEG_C = 80                       # сечений по окружности
BULLET_L_EXPOSED = CART_LEN - CASE_LEN      # пуля вне гильзы: 23,44 мм (по C.I.P.)
BULLET_L_FULL = 28.5             # оценка: полная длина пули ЛПС ≈ 28,5 мм (посадка ≈ 5 мм); донная часть не моделируется
OGIVE_X0 = 58.45                 # начало оживала (до него — цилиндрическая часть пули над дульцем), оценка по снимку 06
RIM_CH = 0.4                     # фаска передней кромки закраины
CASE_WALL = 0.36                 # стенка стреляной гильзы (оценка)
CASE_FLOOR_X = 8.0               # дно внутренней полости стреляной гильзы (оценка: толстая головка)

# ---------------- лента ----------------
# Шаг ленты. Снято с кадра 05 (ПКМ, студия, нерассыпная лента, камера почти фронтальна к дальнему ряду патронов):
# на 2× увеличении закраина (Ø14,48 мм) = 64 px → 4,4 px/мм (длина патрона 335 px = 76 мм, сходится с 77,16); расстояния
# между осями соседних патронов дальнего ряда 92, 93, 95 px → 20,9–21,6 мм; на втором кадре (х9) пары 224 и 163 px при
# 9,3 px/мм — 24 и 17,5 мм (шаг «гуляет» на спирали-шарнире), среднее 20,8. Принято 21,0 мм (закраины не касаются:
# зазор между ними 6,5 мм, как на снимке). Прикидка 16 мм не подтвердилась.
BELT_PITCH = 21.0
HINGE = BELT_PITCH / 2           # шарнир (спираль) лежит посередине между осями соседних патронов
T_LINK = 0.8                     # лист звена (оценка: тонкая штамповка 0,8 мм)
GAP = 0.2                        # зазор звена от гильзы
PL_X0, PL_X1 = 20.5, 53.2        # пластина-«рубашка»: от мышки гильзы вниз на ~33 мм (кадр 05: чёрный корпус звена 33,5 мм)
PL_ALPHA = 68.0                  # полуугол охвата пластины, градусов (оценка)
RING_X0, RING_X1 = 36.0, 46.0    # замкнутое кольцо на плечике и дульце (на внешней стороне ленты видна узкая полоса)
KN_IN, KN_T = 2.75, 0.6          # шарнирная петля (узел) вокруг спирали: внутренний радиус, лист
KN_SEG_PLUS = ((24.0, 31.5), (40.0, 47.5))     # петли на стороне +Y (две), у соседа «−» — между ними (в замок)
KN_SEG_MINUS = ((32.0, 39.5),)
SPIRAL_X0, SPIRAL_X1 = 24.0, 47.5
SPIRAL_R, SPIRAL_WIRE, SPIRAL_PITCH = 2.2, 0.4, 1.3
TIP_T = 1.0                      # лист наконечника (оценка)

BELT_EXIT_FALLBACK = (FEED_RIM_X + 38.0, -60.0, -75.0)   # временная точка выхода из коробки (X, Y, Z)
BELT_Y0 = 0.0                    # ось первого патрона на лотке: Y
BELT_BEND_R = 26.0               # радиус перегиба ленты через край лотка (шарнир сгибает звенья)
BELT_EDGE_Y = -(RECV_HW + RIM_R + 8.0)    # ось ленты у борта: закраина (R 7,2) не ближе ~8 мм к листу борта (с учётом головок заклёпок)
BELT_LEAD = 25.0                 # длина прямого участка от выхода из коробки вдоль заданного направления, мм


# ======================== патрон ========================
def _ogive(x0, x_tip, r_b, step_u=None):
    """Точки оживала (x, r) от начала x0 до закруглённого носика x_tip (касательный оживал, радиус носика ~0,5 мм)."""
    Lo = x_tip - x0
    rho = (r_b * r_b + Lo * Lo) / (2 * r_b)

    def rr(u):
        return math.sqrt(max(rho * rho - (Lo - u) ** 2, 0.0)) + r_b - rho
    pts = []
    n = 26
    for k in range(1, n + 1):
        u = (Lo - 1.4) * (1 - math.cos(math.pi * (n - k) / (2 * n)))  # u — расстояние от носика; густо у носика
        pts.append((x_tip - 1.4 - u, rr(1.4 + u)))
    cap = [(x_tip - 1.0, 0.57), (x_tip - 0.6, 0.5), (x_tip - 0.3, 0.38), (x_tip - 0.1, 0.22), (x_tip, 0.0)]
    return pts + cap


def _primer_region(fired=False):
    """Капсюль: дно чуть утоплено, кромка скруглена; стреляный — с наколом."""
    if not fired:
        return [(0.35, 0.0), (0.33, 0.8), (0.28, 1.6), (0.20, 2.2), (0.14, 2.5), (0.13, 2.62), (0.18, 2.74), (0.30, 2.80), (0.6, 2.80)]
    return [(0.66, 0.0), (0.60, 0.22), (0.46, 0.42), (0.34, 0.62), (0.30, 1.0), (0.26, 1.7), (0.20, 2.2), (0.14, 2.5),
            (0.13, 2.62), (0.18, 2.74), (0.30, 2.80), (0.6, 2.80)]


def _case_outer(mouth_r, flare):
    """Наружный контур гильзы от гнезда капсюля до дульца: гнездо с фаской, кольцевая канавка на торце, закраина с фаской,
    лёгкий конус корпуса, скат, дульце. Скругления — fillet_path (у каждого излома свой радиус)."""
    P = [(0.6, 2.80), (0.6, 3.12), (0.0, 3.72), (0.0, 4.85), (0.28, 4.95), (0.28, 5.45), (0.0, 5.55), (0.0, RIM_R),
         (RIM_T - RIM_CH, RIM_R), (RIM_T, RIM_R - RIM_CH), (RIM_T, BASE_R), (SHOULDER_X, SHOULDER_R), (NECK_X, NECK_R)]
    R = [0.14, 0.14, 0.1, 0.1, 0.1, 0.1, 0.45, 0.3, 0.2, 0.5, 1.5, 1.2]
    return P, R


def cartridge_profile(spent=False):
    prim = _primer_region(spent)
    P, R = _case_outer(0, 0)
    if not spent:
        P += [(52.7, NECK_R), (CASE_LEN - 0.12, NECK_R - 0.25), (CASE_LEN, BULLET_R + 0.03)]
        R += [0.8, 0.25]
        case = fillet_path(P, R, seg=6)
        bullet = [(CASE_LEN, BULLET_R + 0.03), (CASE_LEN + 0.3, BULLET_R - 0.03), (CASE_LEN + 0.7, BULLET_R)] + \
                 [(OGIVE_X0, BULLET_R)] + _ogive(OGIVE_X0, CART_LEN, BULLET_R)
        pts = prim + case[1:] + bullet[1:]
        mats = [2] * (len(prim) - 1) + [0] * len(case[1:]) + [1] * len(bullet[1:])
        # граница капсюль/гильза: первый отрезок case — от последней точки капсюля, он уже учтён
        return pts, mats
    # стреляная: дульце слегка раздуто, срез со стенкой, внутри — полость до толстого дна
    flare_r = NECK_R + 0.09
    P2 = P[:-1] + [(NECK_X, flare_r), (52.8, flare_r), (CASE_LEN, flare_r + 0.05), (CASE_LEN, flare_r + 0.05 - CASE_WALL),
                   (CASE_LEN - 0.4, flare_r - CASE_WALL - 0.05), (NECK_X + 0.6, flare_r - CASE_WALL - 0.05),
                   (SHOULDER_X + 0.3, SHOULDER_R - CASE_WALL), (RIM_T + 9.0, BASE_R - CASE_WALL - 0.05),
                   (CASE_FLOOR_X + 0.6, BASE_R - CASE_WALL - 0.1), (CASE_FLOOR_X, BASE_R - CASE_WALL - 0.9),
                   (CASE_FLOOR_X, 0.0)]
    R2 = R[:-1] + [1.2, 0.5, 0.2, 0.15, 0.2, 0.6, 1.0, 1.2, 1.2, 0.8, 0.0]
    case = fillet_path(P2, R2[:len(P2) - 2], seg=6)
    pts = prim + case[1:]
    mats = [2] * (len(prim) - 1) + [0] * len(case[1:])
    return pts, mats


def _lathe(pts, mats, shift=(0.0, 0.0, 0.0)):
    V, Q, M = lathe_mesh(pts, seg=SEG_C, axis="X", c=(0.0, 0.0), closed=False, mats=mats)
    V = V + np.array(shift, np.float32)[None, :]
    return V, Q, M


def cartridge_origin(h):
    pts, mats = cartridge_profile(False)
    return _lathe(pts, mats)


def cartridge_display(h):
    pts, mats = cartridge_profile(False)
    return _lathe(pts, mats, (-45.0 - CART_LEN / 2, -175.0, 0.0))


def case_spent(h):
    pts, mats = cartridge_profile(True)
    return _lathe(pts, mats, (40.0 - CASE_LEN / 2, -150.0, 0.0))


# ======================== звено ========================
def _case_r_table():
    """Радиус гильзы по X (по тому же контуру, что и сетка патрона): для посадки звена с зазором."""
    P, R = _case_outer(0, 0)
    P = P[10:] + [(52.7, NECK_R), (CASE_LEN, NECK_R)]
    R = [R[10], R[11], 0.0]
    pts = fillet_path(P, R[:len(P) - 2], seg=10)
    a = np.array(pts)
    o = np.argsort(a[:, 0], kind="stable")
    return a[o, 0], a[o, 1]


_RCX, _RCR = _case_r_table()


def case_r(X):
    return np.interp(X, _RCX, _RCR)


def link_shape():
    """Поле звена (чистая функция f(X, Y, Z) — её же берёт проверка зазоров). Рубашка: лист вокруг гильзы
    от X=20,5 до 53,2, охват ±PL_ALPHA от −Z; замкнутое кольцо на плечике; по бокам — шарнирные петли вокруг спирали
    (с одной стороны две, с другой одна, чтобы соседи входили «в замок») на отогнутых полках."""
    al = math.radians(PL_ALPHA)
    hx = (PL_X1 - PL_X0) / 2
    xc = (PL_X0 + PL_X1) / 2

    def sheet(X, Y, Z):
        r = np.hypot(Y, Z)
        rin = case_r(X) + GAP
        return np.abs(r - rin - T_LINK / 2) - T_LINK / 2, r

    def knuckle(X, Y, Z, sy, segs):
        q = np.abs(np.hypot(Y - sy * HINGE, Z) - (KN_IN + KN_T / 2)) - KN_T / 2
        d = None
        for a, b in segs:
            s = i_round(q, np.abs(X - (a + b) / 2) - (b - a) / 2, 0.2)
            d = s if d is None else np.minimum(d, s)
        return d

    def web(X, Y, Z, sy, segs):
        d = None
        for a, b in segs:
            qx = np.abs(X - (a + b) / 2) - (b - a) / 2
            qy = np.abs(Y - sy * 7.6) - 1.7
            qz = np.abs(Z + 2.7) - 0.4
            s = i_round(i_round(qx, qy, 0.25), qz, 0.25)
            d = s if d is None else np.minimum(d, s)
        return d

    def f(X, Y, Z):
        sh, r = sheet(X, Y, Z)
        phi = np.arctan2(np.abs(Y), -Z)
        plate = i_round(sh, r * (phi - al), 0.3)
        plate = i_round(plate, np.abs(X - xc) - hx, 0.3)
        ring = i_round(sh, np.abs(X - (RING_X0 + RING_X1) / 2) - (RING_X1 - RING_X0) / 2, 0.3)
        body = np.minimum(plate, ring)
        out = body
        for sy, segs in ((1.0, KN_SEG_PLUS), (-1.0, KN_SEG_MINUS)):
            grp = u_round(web(X, Y, Z, sy, segs), knuckle(X, Y, Z, sy, segs), 0.2)
            out = u_round(out, grp, 0.15)
        return out
    return f


LINK_BB = bb(PL_X0 - 1, PL_X1 + 1, -HINGE - 3.6, HINGE + 3.6, -8.2, 8.2)


def link(h):
    F = Field("Belt_Link", (PL_X0 - 1.0, -HINGE - 3.6, -8.2), (PL_X1 + 1.0, HINGE + 3.6, 8.2), h)
    F.add(link_shape())
    return F


def spiral(h):
    return helix_mesh((0.0, 0.0), SPIRAL_R, SPIRAL_WIRE, SPIRAL_X0, SPIRAL_X1, SPIRAL_PITCH, seg_turn=24, seg_wire=8, dead=0.0)


# ======================== наконечник ========================
def tip_shape():
    """Наконечник (язычок) ленты: плоская пластина с овальной прорезью под протяжку, сужающаяся к закруглённому концу,
    с язычками к шарнирным петлям (в одной плоскости с осями патронов). Размеры — оценка по кадру 05 (язычок 50–60 мм × 20–25)."""
    pts = fillet_poly([(23.5, 5.5), (48.5, 5.5), (48.5, -18.0), (44.5, -40.0), (40.0, -48.0), (32.0, -48.0), (27.5, -40.0),
                       (23.5, -18.0)], [0.8, 0.8, 4.0, 10.0, 10.0, 10.0, 4.0, 4.0], seg=10)
    plate = Poly(pts)
    slot = Poly(fillet_poly([(30.5, -29.0), (41.5, -29.0), (41.5, -37.0), (30.5, -37.0)], [3.0, 3.0, 3.0, 3.0], seg=10))
    body = prism(plate, "XY", -TIP_T / 2, TIP_T / 2, rim=0.3)
    hole = prism(slot, "XY", -TIP_T, TIP_T)

    def kn(X, Y, Z):
        d = None
        for a, b in KN_SEG_PLUS:
            q = np.abs(np.hypot(Y - HINGE, Z) - (KN_IN + KN_T / 2)) - KN_T / 2
            s = i_round(q, np.abs(X - (a + b) / 2) - (b - a) / 2, 0.2)
            qx = np.abs(X - (a + b) / 2) - (b - a) / 2
            tg = i_round(i_round(qx, np.abs(Y - 5.9) - 1.8, 0.25), np.abs(Z) - TIP_T / 2, 0.25)
            s = u_round(s, tg, 0.2)
            d = s if d is None else np.minimum(d, s)
        return d

    def f(X, Y, Z):
        d = cut(body(X, Y, Z), hole(X, Y, Z), 0.3)
        # продольные рёбра жёсткости по краям (выдавка): валик вдоль Y
        for xr in (27.5, 44.5):
            rid = np.hypot(X - xr, Z - 0.5) - 0.55
            rid = i_round(rid, np.abs(Y + 22.0) - 18.0, 0.3)
            d = u_round(d, rid, 0.25)
        return u_round(d, kn(X, Y, Z), 0.15)
    return f


def tip(h):
    F = Field("Belt_Tip", (22.5, -49.5, -4.5), (49.5, HINGE + 3.6, 4.5), h)
    F.add(tip_shape())
    return F


# ======================== раскладка ленты ========================
def _path_points(exit_yz, dir_yz):
    """Ось ленты в плоскости YZ: с лотка (Y0, FEED_Z) вправо, плавный перегиб вниз и вдоль борта к точке выхода из коробки."""
    A = (BELT_Y0, FEED_Z)
    E = exit_yz
    B = (min(E[0], BELT_EDGE_Y), FEED_Z)
    pts = [A, B]
    rad = [BELT_BEND_R]
    if dir_yz is not None:
        d = np.array(dir_yz, float)
        d /= np.linalg.norm(d)
        pre = (E[0] + d[0] * BELT_LEAD, E[1] + d[1] * BELT_LEAD)
        pts += [pre, E]
        rad += [60.0]
    else:
        pts += [E]
    return fillet_path(pts, rad, seg=28)


def belt_poses(n=None, exit_yz=None, dir_yz=None, start=(BELT_Y0, FEED_Z)):
    """Позы звеньев: список (p, t) — ось патрона (y, z) и единичная касательная вдоль ленты. Звенья — жёсткие, соседние
    сцеплены в общем шарнире (спираль): шарнир звена i (p + HINGE·t) совпадает с шарниром звена i+1 (p − HINGE·t)."""
    if exit_yz is None:
        if BOX_EXIT is not None:
            e = BOX_EXIT
            exit_yz = (e[-2], e[-1])
        else:
            exit_yz = BELT_EXIT_FALLBACK[1:]
    if dir_yz is None and BOX_DIR is not None:
        d = BOX_DIR
        dir_yz = (d[-2], d[-1])
    raw = np.array(_path_points(exit_yz, dir_yz))
    sl = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(raw, axis=0), axis=1))])
    ss = np.arange(0.0, sl[-1], 0.5)                   # частая выборка: поиск ближайшей точки идёт по вершинам
    poly = np.stack([np.interp(ss, sl, raw[:, 0]), np.interp(ss, sl, raw[:, 1])], axis=1)
    tan = np.gradient(poly, axis=0)
    tan /= np.linalg.norm(tan, axis=1)[:, None]

    def near(p):
        i = int(np.argmin(np.linalg.norm(poly - p, axis=1)))
        return i, tan[i]
    p = poly[0].copy()
    t = tan[0].copy()
    out = [(p.copy(), t.copy())]
    while True:
        if n is not None and len(out) >= n:
            break
        Hh = p + HINGE * t
        tn = t.copy()
        for _ in range(8):
            pn = Hh + HINGE * tn
            i, tn = near(pn)
        if (i >= len(poly) - 2 and np.linalg.norm(pn - poly[-1]) > 12.0) or np.linalg.norm(pn - out[-1][0]) < 1.0 or len(out) > 60:
            break
        p, t = pn, tn.copy()
        out.append((p.copy(), t.copy()))
    return out


def _mat(ty, tz, py, pz, x=FEED_RIM_X):
    """Матрица звена: local Y → касательная t, local Z → (−tz, ty); сдвиг в мм."""
    return [1, 0, 0, x, 0, ty, -tz, py, 0, tz, ty, pz, 0, 0, 0, 1]


def _mat_t(py, pz, x=FEED_RIM_X):
    return [1, 0, 0, x, 0, 1, 0, py, 0, 0, 1, pz, 0, 0, 0, 1]


def belt_layout(n=None, exit_yz=None, dir_yz=None):
    """Раскладка ленты: список матриц звеньев (16 чисел по строкам, сдвиг в мм) — от патрона на лотке. Для пересчёта
    с другой точкой выхода (коробка на 200) — передать exit_yz (y, z) и dir_yz."""
    return [_mat(t[0], t[1], p[0], p[1]) for p, t in belt_poses(n, exit_yz, dir_yz)]


def belt_instances(n=None, exit_yz=None, dir_yz=None):
    """Копии для сборки: патроны, звенья, спирали (шарнир k — между звеньями k−1 и k; нулевой — между наконечником и звеном 0)."""
    poses = belt_poses(n, exit_yz, dir_yz)
    rounds, links, spirals = [], [], []
    for k, (p, t) in enumerate(poses):
        rounds.append(dict(name=f"Belt_Round_{k:02d}", matrix=_mat_t(p[0], p[1]), coll="Лента"))
        links.append(dict(name=f"Belt_Link_{k:02d}", matrix=_mat(t[0], t[1], p[0], p[1]), coll="Лента"))
    for k, (p, t) in enumerate(poses):
        hp = p - HINGE * t
        spirals.append(dict(name=f"Belt_Spiral_{k:02d}", matrix=_mat_t(hp[0], hp[1]), coll="Лента"))
    p0, t0 = poses[0]
    ptip = p0 - BELT_PITCH * t0
    tipi = dict(name="Belt_Tip", matrix=_mat(t0[0], t0[1], ptip[0], ptip[1]), coll="Лента")
    return rounds, links, spirals, tipi


# --- отдельный отрезок на 6 патронов, лежит прямо (для показа звеньев) ---
STRIP_N = 6
STRIP_POS = (FEED_RIM_X, -190.0, 0.0)


def strip_instances():
    rounds, links, spirals = [], [], []
    for k in range(STRIP_N):
        y = STRIP_POS[1] - BELT_PITCH * k
        rounds.append(dict(name=f"Strip_Round_{k:02d}", matrix=_mat_t(y, STRIP_POS[2], STRIP_POS[0]), coll="Лента — отрезок"))
        links.append(dict(name=f"Strip_Link_{k:02d}", matrix=_mat(-1.0, 0.0, y, STRIP_POS[2], STRIP_POS[0]), coll="Лента — отрезок"))
        spirals.append(dict(name=f"Strip_Spiral_{k:02d}", matrix=_mat_t(y + HINGE, STRIP_POS[2], STRIP_POS[0]), coll="Лента — отрезок"))
    ytip = STRIP_POS[1] + BELT_PITCH
    tipi = dict(name="Strip_Tip", matrix=_mat(-1.0, 0.0, ytip, STRIP_POS[2], STRIP_POS[0]), coll="Лента — отрезок")
    return rounds, links, spirals, tipi


# ======================== каталог ========================
def parts():
    rounds, links, spirals, tipi = belt_instances()
    srounds, slinks, sspirals, stip = strip_instances()
    return [
        dict(name="Cartridge", build=cartridge_display, coll="Патроны", mats=["Case_lacquer", "Bullet_jacket", "Primer"], sharp=50, coll_hidden=True),
        dict(name="Case_Spent", build=case_spent, coll="Патроны", mats=["Case_lacquer", "Bullet_jacket", "Primer"], sharp=50, coll_hidden=True),
        dict(name="Belt_Round_src", build=cartridge_origin, coll="Лента", mats=["Case_lacquer", "Bullet_jacket", "Primer"], sharp=50,
             instances=rounds + srounds),
        dict(name="Belt_Link_src", build=link, h=0.07, coll="Лента", mat="Belt_steel", instances=links + slinks),
        dict(name="Belt_Spiral_src", build=spiral, coll="Лента", mat="Belt_steel", sharp=60, instances=spirals + sspirals),
        dict(name="Belt_Tip_src", build=tip, h=0.08, coll="Лента", mat="Belt_steel", instances=[tipi]),
        dict(name="Strip_Tip_src", build=tip, h=0.08, coll="Лента — отрезок", mat="Belt_steel", coll_hidden=True, instances=[stip]),
    ]
