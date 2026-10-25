"""Транспорт «Проспекта»: поле формы кузова легковой машины по ключевым точкам (только numpy).

Принцип — как у принятого купе Ильи (tools/coupe_ilya/fieldcore.py): кузов = гладкое объединение
нижнего корпуса и кабины минус колёсные арки, минус — внутри. Отличие — всё задаётся параметрами
класса (specs.py): профили сбоку, перёд и корма, план, сечение по высоте, кабина — точками; между
точками естественный кубический сплайн (ломаная даёт излом поверхности на каждом узле — видно
в отражениях как ребро вдоль кузова).

Оси: X — вбок (левый борт +X), Y — вдоль (перёд к −Y), Z — вверх от земли; Y = 0 — середина базы.
Работает и в системном Python (черновой объём, marching cubes), и в Python Blender (панели).
"""
from __future__ import annotations

import numpy as np


def smin(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(k - np.abs(a - b), 0.0, None) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    return -smin(-a, -b, k)


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def cspline(xk, yk, x):
    """Естественный кубический сплайн через узлы; за краями — продолжение по касательной."""
    xk = np.asarray(xk, dtype=float)
    yk = np.asarray(yk, dtype=float)
    n = len(xk)
    if n == 2:
        return yk[0] + (yk[1] - yk[0]) / (xk[1] - xk[0]) * (np.asarray(x, float) - xk[0])
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


def pchip(xk, yk, x):
    """Монотонная кубическая интерполяция (без выбросов между узлами); за краями — по крайним наклонам."""
    xk = np.asarray(xk, dtype=float)
    yk = np.asarray(yk, dtype=float)
    if len(xk) == 2:
        return cspline(xk, yk, x)
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
    t = np.clip((x - xk[i]) / h[i], 0.0, 1.0)
    h00, h10 = 2 * t ** 3 - 3 * t ** 2 + 1, t ** 3 - 2 * t ** 2 + t
    h01, h11 = -2 * t ** 3 + 3 * t ** 2, t ** 3 - t ** 2
    y = h00 * yk[i] + h10 * h[i] * m[i] + h01 * yk[i + 1] + h11 * h[i] * m[i + 1]
    y = np.where(x < xk[0], yk[0] + m[0] * (x - xk[0]), y)
    return np.where(x > xk[-1], yk[-1] + m[-1] * (x - xk[-1]), y)


class Curve:
    """v(t) по узлам: сплайн, сведённый в плотную таблицу (быстро в лучах), и поправка расстояния
    k = 1/√(1 + v'²) — превращает разность «точка − кривая» в расстояние по нормали."""

    def __init__(self, pts, step: float = 0.002, ext: float = 1.5, kind: str = "cspline") -> None:
        p = np.asarray(sorted(pts), dtype=float)
        self.knots = p
        self.t = np.arange(p[0, 0] - ext, p[-1, 0] + ext + step / 2, step)
        self.v = pchip(p[:, 0], p[:, 1], self.t) if kind == "pchip" else cspline(p[:, 0], p[:, 1], self.t)
        g = np.gradient(self.v, self.t)
        self.k = 1.0 / np.sqrt(1.0 + g * g)

    def __call__(self, t):
        return np.interp(t, self.t, self.v)

    def at(self, t):
        return np.interp(t, self.t, self.v), np.interp(t, self.t, self.k)


class CarField:
    """Поле кузова по параметрам класса (словарь spec из specs.py): eval(X, Y, Z), минус — внутри."""

    def __init__(self, spec: dict) -> None:
        s = self.s = spec
        self.top = Curve(s["top"])            # верх нижнего корпуса сбоку: бампер, капот, пояс, крышка
        self.bot = Curve(s["bottom"])         # низ: губа бампера, порог, задний бампер
        self.front = Curve(s["front"])        # лицо носа: Y от высоты Z (по оси машины)
        self.rear = Curve(s["rear"])          # торец кормы: Y от Z
        self.plan = Curve(s["plan"])          # полуширина по длине (на высоте наибольшего сечения)
        self.sec = Curve(s["section"])        # доля полуширины по высоте
        self.sw_f = Curve(s["nose_sweep"], ext=0.6)   # насколько лицо носа уходит назад к углам (по доле ширины)
        self.sw_r = Curve(s["tail_sweep"], ext=0.6)
        self.belt = Curve(s["belt"])          # пояс — низ боковых окон
        self.gh = Curve(s["gh_half"])         # полуширина кабины у пояса
        self.gh_top = Curve(s["gh_top"])      # полуширина кабины у крыши (план крыши — выпуклый)
        self.roof = Curve(s["roof"])          # крыша сбоку
        self.ws = Curve(s["ws"])              # лобовое: Y от Z по оси
        self.bl = Curve(s["bl"])              # заднее стекло / дверь багажника: Y от Z
        self.ws_sw = Curve(s["ws_sweep"], ext=0.6)
        self.bl_sw = Curve(s["bl_sweep"], ext=0.6)
        self.crease = Curve(s["crease"]) if s.get("crease") else None
        self.wheels = [(y, s["wheel_z"]) for y in s["wheel_y"]]

    # --- нижний корпус ----------------------------------------------------------------------
    def lower(self, X: np.ndarray, Y: np.ndarray, Z: np.ndarray) -> np.ndarray:
        s = self.s
        ax = np.abs(X)
        hw, hk = self.plan.at(Y)
        hw = np.maximum(hw, 0.05)
        u = np.clip(ax / hw, 0.0, 1.4)
        tv, tk = self.top.at(Y)
        bv, bk = self.bot.at(Y)
        crown = s["crown_hood"] * np.minimum(u, 1.0) ** 2
        d_top = (Z + crown - tv) * tk
        d_bot = (bv - Z) * bk
        fv, fk = self.front.at(Z)
        d_front = (fv + self.sw_f(u) - Y) * fk
        rv, rk = self.rear.at(Z)
        d_rear = (Y - rv + self.sw_r(u)) * rk
        d = smax(d_top, d_bot, s["r_tb"])
        d = smax(d, d_front, s["r_nose"])
        d = smax(d, d_rear, s["r_tail"])
        g = np.maximum(self.sec(Z), 0.2)
        d_plan = (ax / g - hw) * hk * g
        # Крылья вокруг колёс (у внедорожника — расширители) и линия плеча
        for yc, zc in self.wheels:
            amp = s.get("flare", 0.0)
            if amp:
                r = np.sqrt((Y - yc) ** 2 + (Z - zc) ** 2)
                d_plan = d_plan - amp * (1.0 - smoothstep(s["flare_r0"], s["flare_r1"], r)) * smoothstep(0.15, 0.30, Z)
        if self.crease is not None:
            y0, y1 = self.crease.knots[0, 0], self.crease.knots[-1, 0]
            on = smoothstep(y0, y0 + 0.2, Y) * (1 - smoothstep(y1 - 0.2, y1, Y))
            dz = np.abs(Z - self.crease(Y))
            d_plan = d_plan - s["crease_amp"] * (1 - smoothstep(0.0, s["crease_w"], dz)) * on
        return smax(d, d_plan, s["r_shoulder"])

    # --- кабина -----------------------------------------------------------------------------
    def cabin(self, X: np.ndarray, Y: np.ndarray, Z: np.ndarray) -> np.ndarray:
        s = self.s
        ax = np.abs(X)
        belt = self.belt(Y)
        rv, rk = self.roof.at(Y)
        # Боковое стекло завалено внутрь: полуширина от пояса до крыши — по прямой между двумя планами
        g0, g1 = self.gh(Y), self.gh_top(Y)
        rise = np.maximum(rv - belt, 0.15)
        tumble = (g0 - g1) / rise
        half = np.maximum(g0 - tumble * np.clip(Z - belt, 0, None), 0.05)
        u = np.clip(ax / half, 0.0, 1.4)
        d_roof = (Z + s["crown_roof"] * np.minimum(u, 1.0) ** 2 - rv) * rk
        d_side = (ax - half) / np.sqrt(1.0 + tumble * tumble)
        wv, wk = self.ws.at(Z)
        d_ws = (wv + self.ws_sw(u) - Y) * wk
        bv, bk = self.bl.at(Z)
        d_bl = (Y - bv + self.bl_sw(u)) * bk
        d = smax(d_ws, d_side, s["r_apillar"])
        d = smax(d, d_bl, s["r_cpillar"])
        d = smax(d, d_roof, s["r_roof"])
        return smax(d, belt - 0.22 - Z, 0.02)

    def eval(self, X: np.ndarray, Y: np.ndarray, Z: np.ndarray, arches: bool = True) -> np.ndarray:
        s = self.s
        body = smin(self.lower(X, Y, Z), self.cabin(X, Y, Z), s["r_union"])
        if arches:
            for yc, zc in self.wheels:
                d_c = np.sqrt((Y - yc) ** 2 + (Z - zc) ** 2) - s["arch_r"]
                arch = smax(d_c, s["well_x"] - np.abs(X), 0.02)
                body = smax(body, -arch, s["r_arch"])
        return body


class BoxField:
    """Кузов «коробкой» (городской автобус, ПАЗ, ГАЗель): профиль сбоку — крыша/капот top(Y), низ bottom(Y),
    лицо front(Z), корма rear(Z); план — полуширина plan(Y) с долей по высоте section(Z); свои радиусы
    вертикальных углов (r_corner), кромки крыши (r_roof) и низа (r_bot). Минус — внутри."""

    def __init__(self, spec: dict) -> None:
        s = self.s = spec
        k = s.get("curve_kind", "pchip")
        self.top = Curve(s["top"], kind=k)
        self.bot = Curve(s["bottom"], kind=k)
        self.front = Curve(s["front"], kind=k)
        self.rear = Curve(s["rear"], kind=k)
        self.plan = Curve(s["plan"], kind=k)
        self.sec = Curve(s["section"], kind=k) if s.get("section") else None
        self.sw_f = Curve(s.get("nose_sweep", [(0.0, 0.0), (1.0, 0.0)]), ext=0.6)
        self.sw_r = Curve(s.get("tail_sweep", [(0.0, 0.0), (1.0, 0.0)]), ext=0.6)
        self.wheels = [(y, s["wheel_z"]) for y in s["wheel_y"]]

    def half(self, Y, Z):
        hw = np.maximum(self.plan(Y), 0.05)
        return hw * (self.sec(Z) if self.sec is not None else 1.0)

    def eval(self, X: np.ndarray, Y: np.ndarray, Z: np.ndarray, arches: bool = True) -> np.ndarray:
        s = self.s
        ax = np.abs(X)
        hw = self.half(Y, Z)
        u = np.clip(ax / hw, 0.0, 1.4)
        d_x = ax - hw
        tv, tk = self.top.at(Y)
        bv, bk = self.bot.at(Y)
        fv, fk = self.front.at(Z)
        rv, rk = self.rear.at(Z)
        d_top = (Z - tv) * tk
        d_bot = (bv - Z) * bk
        d_f = (fv + self.sw_f(u) - Y) * fk
        d_r = (Y - rv + self.sw_r(u)) * rk
        d_plan = smax(smax(d_x, d_f, s["r_corner"]), d_r, s.get("r_corner_rear", s["r_corner"]))
        d = smax(d_plan, d_top, s["r_roof"])
        d = smax(d, d_bot, s["r_bot"])
        if arches:
            for yc, zc in self.wheels:
                d_c = np.sqrt((Y - yc) ** 2 + (Z - zc) ** 2) - s["arch_r"]
                arch = smax(d_c, s["well_x"] - ax, 0.02)
                d = smax(d, -arch, s.get("r_arch", 0.012))
        return d
