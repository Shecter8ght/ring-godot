"""Купе Ильи: поле формы кузова — общие параметры и расчёт (только numpy).

Работает и в системном Python (body_field.py — черновой объём, сетка marching cubes), и в Python
Blender (сборка панелей). Профили чертежа (верх, низ, пояс, ширина по длине) запекает
body_field.py в field_profiles.npz; здесь — только формулы и принятые размеры.
"""
from __future__ import annotations

import numpy as np

WHEEL_Y = 1.4355             # колёса на ±WHEEL_Y (база 2,871 по чертежу)
WHEEL_Z = 0.3430             # центр колеса над землёй

# --- Принятые размеры и решения (asset-state.md) ---------------------------------------------
HALF_FRONT_FLARE = 0.957     # полуширина по передним крыльям CLE 53 (+29 мм к обычному CLE)
HALF_REAR_FLARE = 0.9675     # по задним крыльям (габарит 1935 мм)
HALF_DOOR = 0.918            # по дверям
ARCH_R = 0.388               # радиус выреза арки: шина 0,343 + зазор
WELL_X = 0.50                # глубина колёсной ниши от оси машины
WS_BASE = (-0.855, 1.021)    # низ лобового стекла (Y, Z) — по чертежу
BL_BASE = (1.968, 1.103)     # низ заднего стекла
# Пояс (низ боковых окон, чуть ниже окантовки): Y → Z
BELT = [(-0.855, 1.015), (-0.37, 0.990), (0.87, 1.030), (1.395, 1.110), (1.968, 1.103)]
# Ширина кабины у пояса по длине (план: стойки сходятся к лобовому и сильнее к заднему стеклу)
GH_HALF = [(-0.90, 0.75), (-0.60, 0.80), (-0.20, 0.815), (0.50, 0.81), (1.10, 0.775), (1.45, 0.74), (2.00, 0.64)]
GH_TUMBLE = 0.60             # завал боковых стёкол: на метр высоты внутрь (стекло у пояса ~0,81, у крыши ~0,63)
# Сечение нижнего корпуса: доля полуширины по высоте
G_SECTION = [(0.00, 0.70), (0.10, 0.80), (0.18, 0.90), (0.25, 0.955), (0.35, 0.985), (0.55, 0.998),
             (0.70, 1.000), (0.80, 0.992), (0.90, 0.968), (0.98, 0.935), (1.06, 0.895), (1.20, 0.83)]
CROWN_HOOD = 0.045           # выпуклость капота и багажника к середине
CROWN_ROOF = 0.040           # выпуклость крыши
R_SHOULDER = 0.055           # скругление плеча (верх — борт)
R_ROOF = 0.075               # скругление края крыши
R_UNION = 0.030              # переход кабины в корпус
R_ARCH = 0.012               # кромка арки

# Свои кривые концов и низа (Y, Z), м. Перёд: нижняя часть бампера уходит назад, верх — к капоту.
NOSE_TIP = (-2.337, 0.585)
NOSE_BOT = [(-2.333, 0.47), (-2.325, 0.40), (-2.300, 0.30), (-2.255, 0.205), (-2.20, 0.195)]
NOSE_TOP = [(-2.334, 0.66), (-2.318, 0.74), (-2.280, 0.795), (-2.220, 0.828)]
TAIL_TIP = (2.517, 0.55)
TAIL_BOT = [(2.20, 0.29), (2.43, 0.34), (2.50, 0.37), (2.514, 0.45)]
TAIL_TOP = [(2.30, 1.042), (2.335, 1.034), (2.40, 0.905), (2.46, 0.80), (2.50, 0.70), (2.514, 0.62)]
BOTTOM = [(-1.90, 0.19), (-1.00, 0.185), (1.00, 0.19), (1.85, 0.22)]
# Насколько перёд и корма уходят назад/вперёд к углам (по плану): полуширина X → сдвиг, м
NOSE_SWEEP = [(0.0, 0.0), (0.30, 0.010), (0.50, 0.045), (0.65, 0.105), (0.75, 0.175), (0.85, 0.270), (0.95, 0.40)]
TAIL_SWEEP = [(0.0, 0.0), (0.37, 0.010), (0.55, 0.060), (0.68, 0.130), (0.77, 0.225), (0.90, 0.360)]
R_NOSE = 0.035               # скругление носка и кромок бампера сбоку
# Расширенные крылья CLE 53: выпуклость борта вокруг колеса (Y центра, амплитуда, м)
FLARES = [(-WHEEL_Y, HALF_FRONT_FLARE - HALF_DOOR), (WHEEL_Y, HALF_REAR_FLARE - HALF_DOOR)]
FLARE_R0, FLARE_R1 = 0.40, 0.68   # от кромки арки до слияния с бортом
# Линия плеча — острое ребро вдоль борта (Y, Z): спереди от фары, через дверь, над задним колесом
CREASE = [(-2.10, 0.785), (-1.745, 0.817), (-0.96, 0.860), (-0.40, 0.868), (0.35, 0.900), (0.84, 0.925),
          (1.50, 0.935), (2.00, 0.925)]
CREASE_AMP, CREASE_W = 0.006, 0.050
# Нижняя линия двери — мягкая впадина
DOOR_LINE = [(-1.00, 0.410), (0.12, 0.449), (0.90, 0.480)]
DOOR_AMP, DOOR_W = -0.004, 0.07
# Выпуклости капота: центр по X, полуширина, высота; вдоль Y — от лобового к передней кромке
HOOD_DOMES = [(0.145, 0.120, 0.014)]
HOOD_DOME_Y = (-1.98, -0.98)



def smin(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    h = np.clip(k - np.abs(a - b), 0.0, None) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    return -smin(-a, -b, k)


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


class Profile1D:
    """Кривая v(Y) на мелкой сетке; расстояние до неё по нормали в первом приближении."""

    def __init__(self, ys: np.ndarray, v: np.ndarray) -> None:
        self.ys, self.v = ys, v
        self.k = 1.0 / np.sqrt(1.0 + np.gradient(v, ys) ** 2)

    def at(self, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return np.interp(y, self.ys, self.v), np.interp(y, self.ys, self.k)


def extend(ys: np.ndarray, v: np.ndarray, valid: np.ndarray, slope: float) -> np.ndarray:
    """За носком и хвостом кривая круто уходит (slope на метр) — тело кончается."""
    r = v.copy()
    i0, i1 = np.where(valid)[0][[0, -1]]
    r[:i0] = v[i0] + slope * (ys[i0] - ys[:i0])
    r[i1 + 1:] = v[i1] + slope * (ys[i1 + 1:] - ys[i1])
    return r


class BodyField:
    """Поле формы кузова: eval(X, Y, Z) для массивов одной формы (минус — внутри).

    Тот же расчёт, что даёт сетку чернового объёма, — для проекции панелей на поверхность.
    """

    def __init__(self, pr: dict) -> None:
        ys, top, bot, zlt, half = pr["ys"], pr["top"], pr["bot"], pr["z_low_top"], pr["half"]
        valid = ~np.isnan(top)
        self.t_low = Profile1D(ys, extend(ys, zlt, valid, -30.0))
        self.b_low = Profile1D(ys, extend(ys, bot, valid, 30.0))
        t_gh_raw = np.where(pr["in_gh"], top, zlt - 0.15)
        self.t_gh = Profile1D(ys, extend(ys, t_gh_raw, valid, -30.0))
        self.ys = ys
        self.zlt_e = extend(ys, zlt, valid, 0.0)
        self.plan = Profile1D(ys, extend(ys, half, valid & (half > 0), -30.0))
        self.sw_f = [p[0] for p in NOSE_SWEEP], [p[1] for p in NOSE_SWEEP]
        self.sw_r = [p[0] for p in TAIL_SWEEP], [p[1] for p in TAIL_SWEEP]
        self.kt = 1.0 / np.sqrt(1.0 + GH_TUMBLE ** 2)
        self.crease_x = np.array([p[0] for p in CREASE])
        self.crease_y = np.array([p[1] for p in CREASE])

    def lower(self, X: np.ndarray, Y: np.ndarray, Z: np.ndarray) -> np.ndarray:
        ax = np.abs(X)
        # Профиль носа и кормы к углам уходит назад (по плану), а не обрезается планом
        w_f = smoothstep(-1.55, -2.05, Y)
        w_r = smoothstep(1.75, 2.20, Y)
        axf = np.minimum(ax, self.sw_f[0][-1])
        axr = np.minimum(ax, self.sw_r[0][-1])
        yq = Y - cspline(*self.sw_f, axf) * w_f + cspline(*self.sw_r, axr) * w_r
        pv, pk = self.plan.at(Y)
        crown = CROWN_HOOD * np.clip(ax / np.maximum(pv, 0.05), 0, 1.2) ** 2
        tv, tk = self.t_low.at(yq)
        bv, bk = self.b_low.at(yq)
        # Выпуклости капота: гладкий горб поперёк, нарастает и спадает по длине
        y0, y1 = HOOD_DOME_Y
        along = smoothstep(y0, y0 + 0.30, Y) * (1 - smoothstep(y1 - 0.25, y1, Y))
        for xc, hw, amp in HOOD_DOMES:
            q = np.clip(1 - ((ax - xc) / hw) ** 2, 0, None)
            tv = tv + amp * q * q * along
        d_side = smax((Z + crown - tv) * tk, (bv - Z) * bk, R_NOSE)
        g = cspline([p[0] for p in G_SECTION], [p[1] for p in G_SECTION], Z)
        d_plan = (ax / g - pv) * pk * g
        # Крылья: выпуклость борта кольцом вокруг оси колеса, ниже порога — нет
        for yc, amp in FLARES:
            r = np.sqrt((Y - yc) ** 2 + (Z - WHEEL_Z) ** 2)
            d_plan = d_plan - amp * (1.0 - smoothstep(FLARE_R0, FLARE_R1, r)) * smoothstep(0.16, 0.30, Z)
        # Линия плеча (острое ребро) и нижняя линия двери (впадина)
        on = smoothstep(CREASE[0][0], CREASE[0][0] + 0.15, Y) * (1 - smoothstep(CREASE[-1][0] - 0.15, CREASE[-1][0], Y))
        # Гребень со скруглённой вершиной (smoothstep), а не «домиком»: острый излом на сетке читается как ребро
        dz = np.abs(Z - cspline(self.crease_x, self.crease_y, Y))
        d_plan = d_plan - CREASE_AMP * (1 - smoothstep(0.0, CREASE_W, dz)) * on
        door_z = cspline([p[0] for p in DOOR_LINE], [p[1] for p in DOOR_LINE], Y)
        on_d = smoothstep(-1.05, -0.85, Y) * (1 - smoothstep(0.80, 0.98, Y))
        d_plan = d_plan - DOOR_AMP * (1 - smoothstep(0.0, DOOR_W, np.abs(Z - door_z))) * on_d
        return smax(d_side, d_plan, R_SHOULDER)

    def cabin(self, X: np.ndarray, Y: np.ndarray, Z: np.ndarray) -> np.ndarray:
        ax = np.abs(X)
        zlt = np.interp(Y, self.ys, self.zlt_e)
        gh_half = cspline([p[0] for p in GH_HALF], [p[1] for p in GH_HALF], Y)
        gv, gk = self.t_gh.at(Y)
        d_gtop = (Z + CROWN_ROOF * (ax / 0.60) ** 2 - gv) * gk
        d_gside = (ax - (gh_half - GH_TUMBLE * np.clip(Z - zlt, 0, None))) * self.kt
        d_gbot = (zlt - 0.25) - Z
        # Кабина только над поясом между лобовым и задним стёклами (иначе тянется под капот
        # в нос вровень с корпусом и плавное объединение даёт тонкую «скорлупу» перед бампером)
        d_gy = np.maximum(WS_BASE[0] - 0.12 - Y, Y - (BL_BASE[0] + 0.12))
        return smax(smax(smax(d_gtop, d_gside, R_ROOF), d_gbot, 0.02), d_gy, 0.02)

    def eval(self, X: np.ndarray, Y: np.ndarray, Z: np.ndarray, arches: bool = True) -> np.ndarray:
        body = smin(self.lower(X, Y, Z), self.cabin(X, Y, Z), R_UNION)
        if arches:
            # Колёсные арки: цилиндры поперёк, только снаружи от ниши
            for c in (-WHEEL_Y, WHEEL_Y):
                d_c = np.sqrt((Y - c) ** 2 + (Z - WHEEL_Z) ** 2) - ARCH_R
                arch = smax(d_c, WELL_X - np.abs(X), 0.02)
                body = smax(body, -arch, R_ARCH)
        return body


def cspline(xk, yk, x):
    """Естественный кубический сплайн через узлы (непрерывна вторая производная).

    Ломаная (np.interp) даёт излом поверхности на каждом узле — вдоль кузова это видно как ребро.
    За краями — продолжение по касательной.
    """
    xk = np.asarray(xk, dtype=float)
    yk = np.asarray(yk, dtype=float)
    n = len(xk)
    h = np.diff(xk)
    A = np.zeros((n, n))
    r = np.zeros(n)
    A[0, 0] = A[-1, -1] = 1.0
    for i in range(1, n - 1):
        A[i, i - 1] = h[i - 1]
        A[i, i] = 2 * (h[i - 1] + h[i])
        A[i, i + 1] = h[i]
        r[i] = 3 * ((yk[i + 1] - yk[i]) / h[i] - (yk[i] - yk[i - 1]) / h[i - 1])
    c = np.linalg.solve(A, r)
    b = (yk[1:] - yk[:-1]) / h - h * (2 * c[:-1] + c[1:]) / 3
    d = (c[1:] - c[:-1]) / (3 * h)
    x = np.asarray(x, dtype=float)
    i = np.clip(np.searchsorted(xk, x) - 1, 0, n - 2)
    t = np.clip(x - xk[i], 0.0, h[i])
    y = yk[i] + b[i] * t + c[i] * t ** 2 + d[i] * t ** 3
    slope0 = b[0]
    slope1 = b[-1] + 2 * c[-2] * h[-1] + 3 * d[-1] * h[-1] ** 2
    y = np.where(x < xk[0], yk[0] + slope0 * (x - xk[0]), y)
    return np.where(x > xk[-1], yk[-1] + slope1 * (x - xk[-1]), y)


def pchip(xk: np.ndarray, yk: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Монотонная кубическая интерполяция (Фрича — Карлсона), за краями — по крайним наклонам."""
    xk = np.asarray(xk, dtype=float)
    yk = np.asarray(yk, dtype=float)
    h = np.diff(xk)
    d = np.diff(yk) / h
    m = np.zeros_like(yk)
    for i in range(1, len(xk) - 1):
        if d[i - 1] * d[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    m[0], m[-1] = d[0], d[-1]
    x = np.asarray(x, dtype=float)
    i = np.clip(np.searchsorted(xk, x) - 1, 0, len(xk) - 2)
    t = (x - xk[i]) / h[i]
    tc = np.clip(t, 0.0, 1.0)
    h00, h10 = 2 * tc ** 3 - 3 * tc ** 2 + 1, tc ** 3 - 2 * tc ** 2 + tc
    h01, h11 = -2 * tc ** 3 + 3 * tc ** 2, tc ** 3 - tc ** 2
    y = h00 * yk[i] + h10 * h[i] * m[i] + h01 * yk[i + 1] + h11 * h[i] * m[i + 1]
    # Вне узлов — продолжение по наклону крайнего отрезка
    y = np.where(x < xk[0], yk[0] + m[0] * (x - xk[0]), y)
    return np.where(x > xk[-1], yk[-1] + m[-1] * (x - xk[-1]), y)


def load_profiles(path) -> dict:
    """Профили из field_profiles.npz (запекает body_field.py)."""
    z = np.load(path)
    return {k: z[k] for k in z.files}
