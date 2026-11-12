# АСТЕН-919: построение деталей неявными поверхностями — поле расстояний со знаком на сетке вокселей.
# Зачем: у каждого ребра свой радиус скругления (владелец: «избегай острых граней»), стыки литой рамки без швов,
# вырезы без булевых операций Blender (точное булево на таких корпусах сбоит — опыт ИЗЛОМ-45).
# Запускается обычным Python (numpy, scipy); сетку из поля строит сборщик в Blender (assemble.py, OpenVDB).
# Единицы — мм. Оси: +X к дулу, +Z вверх, −Y — правая сторона стрелка; начало — зеркало затвора на оси канала.
# Поле: меньше нуля — внутри тела.
import math
import time

import numpy as np
from scipy.spatial import cKDTree

F32 = np.float32
BIG = 1.0e3


# ---------- операции над полями ----------

def u_round(a, b, r=0.0):
    """Объединение; r — радиус галтели во вогнутом стыке (число или поле)."""
    if np.isscalar(r) and r <= 0:
        return np.minimum(a, b)
    return np.maximum(r, np.minimum(a, b)) - np.hypot(np.maximum(r - a, 0), np.maximum(r - b, 0))


def i_round(a, b, r=0.0):
    """Пересечение; r — радиус скругления выпуклого ребра (число или поле)."""
    if np.isscalar(r) and r <= 0:
        return np.maximum(a, b)
    return np.minimum(-r, np.maximum(a, b)) + np.hypot(np.maximum(a + r, 0), np.maximum(b + r, 0))


def i_chamfer(a, b, c):
    """Пересечение с фаской 45° шириной c (по каждой грани)."""
    return np.maximum(np.maximum(a, b), (a + b + c) * 0.70710678)


def cut(a, b, r=0.0):
    """Вычитание тела b из a; r — скругление кромки выреза."""
    return i_round(a, -b, r)


def cut_chamfer(a, b, c):
    return i_chamfer(a, -b, c)


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------- примитивы: функции f(X, Y, Z) → поле ----------

def slab(axis, a0, a1):
    k = "XYZ".index(axis)
    mid = (a0 + a1) / 2; half = abs(a1 - a0) / 2

    def f(X, Y, Z):
        return np.abs((X, Y, Z)[k] - mid) - half
    return f


def half(axis, a, sign=1):
    """Полупространство: тело там, где sign·(координата − a) < 0."""
    k = "XYZ".index(axis)

    def f(X, Y, Z):
        return sign * ((X, Y, Z)[k] - a)
    return f


def plane(p, n):
    """Полупространство за плоскостью: тело там, где (q − p)·n < 0."""
    n = np.array(n, float); n /= np.linalg.norm(n)

    def f(X, Y, Z):
        return (X - p[0]) * n[0] + (Y - p[1]) * n[1] + (Z - p[2]) * n[2]
    return f


def box(lo, hi, r=0.0):
    """Брус; r — скругление всех рёбер."""
    c = [(a + b) / 2 for a, b in zip(lo, hi)]
    hf = [abs(b - a) / 2 - r for a, b in zip(lo, hi)]

    def f(X, Y, Z):
        qx = np.abs(X - c[0]) - hf[0]; qy = np.abs(Y - c[1]) - hf[1]; qz = np.abs(Z - c[2]) - hf[2]
        out = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2 + np.maximum(qz, 0) ** 2)
        return out + np.minimum(np.maximum(np.maximum(qx, qy), qz), 0) - r
    return f


def box_e(lo, hi, rx=0.0, ry=0.0, rz=0.0):
    """Брус с разными скруглениями рёбер: rx — у рёбер вдоль X, ry — вдоль Y, rz — вдоль Z."""
    sx, sy, sz = slab("X", lo[0], hi[0]), slab("Y", lo[1], hi[1]), slab("Z", lo[2], hi[2])

    def f(X, Y, Z):
        a, b, c = sx(X, Y, Z), sy(X, Y, Z), sz(X, Y, Z)
        # рёбра вдоль X — стык граней Y и Z; затем грани X: их рёбра (вдоль Y и Z) — меньшим из ry, rz
        d = i_round(b, c, rx)
        return i_round(d, a, min(ry, rz) if min(ry, rz) > 0 else max(ry, rz))
    return f


def cyl(axis, c, r, a0, a1, rim=0.0, rim1=None):
    """Цилиндр вдоль оси axis через точку c (две другие координаты по порядку XYZ), от a0 до a1; rim — скругление
    торцевых кромок (rim1 — у торца a1, если другое)."""
    k = "XYZ".index(axis)
    o = [i for i in range(3) if i != k]
    mid = (a0 + a1) / 2; hf = abs(a1 - a0) / 2

    def f(X, Y, Z):
        P = (X, Y, Z)
        dr = np.hypot(P[o[0]] - c[0], P[o[1]] - c[1]) - r
        if rim1 is None:
            return i_round(dr, np.abs(P[k] - mid) - hf, rim)
        d = i_round(dr, min(a0, a1) - P[k], rim)
        return i_round(d, P[k] - max(a0, a1), rim1)
    return f


def cone(axis, c, a0, r0, a1, r1):
    """Усечённый конус вдоль оси (без торцов — для пересечения со slab): радиус r0 при a0, r1 при a1."""
    k = "XYZ".index(axis)
    o = [i for i in range(3) if i != k]
    s = (r1 - r0) / (a1 - a0)
    nrm = math.hypot(1.0, s)

    def f(X, Y, Z):
        P = (X, Y, Z)
        rr = r0 + (P[k] - a0) * s
        return (np.hypot(P[o[0]] - c[0], P[o[1]] - c[1]) - rr) / nrm
    return f


def sphere(c, r):
    def f(X, Y, Z):
        return np.sqrt((X - c[0]) ** 2 + (Y - c[1]) ** 2 + (Z - c[2]) ** 2) - r
    return f


def capsule(p0, p1, r):
    p0 = np.array(p0, float); p1 = np.array(p1, float)
    d = p1 - p0; L2 = float(d @ d)

    def f(X, Y, Z):
        t = np.clip(((X - p0[0]) * d[0] + (Y - p0[1]) * d[1] + (Z - p0[2]) * d[2]) / L2, 0, 1)
        return np.sqrt((X - p0[0] - t * d[0]) ** 2 + (Y - p0[1] - t * d[1]) ** 2 + (Z - p0[2] - t * d[2]) ** 2) - r
    return f


# ---------- плоские контуры ----------

def fillet_poly(points, radii, seg=8):
    """Скругляет углы замкнутого многоугольника. radii — число или список на каждый угол (0 — острый)."""
    n = len(points)
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * n
    out = []
    for i in range(n):
        p0 = np.array(points[i - 1], float); p1 = np.array(points[i], float); p2 = np.array(points[(i + 1) % n], float)
        r = radii[i]
        a = p0 - p1; b = p2 - p1
        la, lb = np.linalg.norm(a), np.linalg.norm(b)
        if r <= 0 or la < 1e-9 or lb < 1e-9:
            out.append((p1[0], p1[1])); continue
        a /= la; b /= lb
        ang = math.acos(max(-1.0, min(1.0, float(a @ b))))
        if ang < 1e-3 or abs(ang - math.pi) < 1e-3:
            out.append((p1[0], p1[1])); continue
        t = min(r / math.tan(ang / 2), la * 0.49, lb * 0.49)
        re = t * math.tan(ang / 2)
        s = p1 + a * t; e = p1 + b * t
        bis = (a + b); bis /= np.linalg.norm(bis)
        c = p1 + bis * (re / math.sin(ang / 2))
        a0 = math.atan2(s[1] - c[1], s[0] - c[0]); a1 = math.atan2(e[1] - c[1], e[0] - c[0])
        da = a1 - a0
        while da > math.pi: da -= 2 * math.pi
        while da < -math.pi: da += 2 * math.pi
        for k in range(seg + 1):
            aa = a0 + da * k / seg
            out.append((c[0] + math.cos(aa) * re, c[1] + math.sin(aa) * re))
    return out


def arc(cx, cy, r, a0, a1, seg=16):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / seg)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / seg)))
            for k in range(seg + 1)]


def smooth_closed(pts, step=0.25, sigma=1.0):
    """Перевыборка замкнутого контура через step мм и сглаживание по Гауссу (sigma — мм вдоль контура)."""
    from scipy.ndimage import gaussian_filter1d
    p = np.array(pts, float)
    q = np.vstack([p, p[:1]])
    seg = np.linalg.norm(np.diff(q, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    m = max(16, int(s[-1] / step))
    t = np.linspace(0, s[-1], m, endpoint=False)
    out = np.stack([np.interp(t, s, q[:, 0]), np.interp(t, s, q[:, 1])], axis=1)
    if sigma > 0:
        out = gaussian_filter1d(out, sigma / step, axis=0, mode="wrap")
    return [tuple(v) for v in out]


class Poly:
    """Замкнутый контур на плоскости с точным расстоянием со знаком (минус — внутри)."""

    def __init__(self, pts, step=0.05):
        p = np.array(pts, np.float64)
        if np.allclose(p[0], p[-1]):
            p = p[:-1]
        self.p = p
        self.a = p
        self.b = np.roll(p, -1, axis=0)
        d = self.b - self.a
        L = np.linalg.norm(d, axis=1)
        keep = L > 1e-9
        self.a, self.b, d, L = self.a[keep], self.b[keep], d[keep], L[keep]
        self.d = d; self.L2 = L * L
        # точки-пробы вдоль контура и номер их отрезка — для поиска ближайшего отрезка
        sp, si = [], []
        for i, (a, dd, l) in enumerate(zip(self.a, d, L)):
            n = max(1, int(math.ceil(l / step)))
            t = (np.arange(n) + 0.5) / n
            sp.append(a[None, :] + t[:, None] * dd[None, :]); si.append(np.full(n, i))
        self.tree = cKDTree(np.vstack(sp)); self.seg_of = np.concatenate(si)
        self.lo = p.min(axis=0); self.hi = p.max(axis=0)
        self.n = len(self.a)

    def _dist_seg(self, q, i):
        a = self.a[i]; d = self.d[i]
        t = np.clip(((q - a) * d).sum(axis=1) / self.L2[i], 0, 1)
        return np.linalg.norm(q - a - t[:, None] * d, axis=1)

    def _inside(self, q):
        """Чётность пересечений луча +x с рёбрами (по частям, чтобы не раздувать память)."""
        out = np.zeros(len(q), bool)
        ay = self.a[:, 1][None, :]; by = self.b[:, 1][None, :]
        ax = self.a[:, 0][None, :]; bx = self.b[:, 0][None, :]
        for s in range(0, len(q), 20000):
            x = q[s:s + 20000, 0][:, None]; y = q[s:s + 20000, 1][:, None]
            cond = (ay > y) != (by > y)
            with np.errstate(divide="ignore", invalid="ignore"):
                xi = ax + (y - ay) * (bx - ax) / (by - ay)
            out[s:s + 20000] = (np.count_nonzero(cond & (x < xi), axis=1) % 2) == 1
        return out

    def sd(self, U, V):
        shape = np.broadcast(U, V).shape
        Ub, Vb = np.broadcast_arrays(U, V)
        q = np.stack([Ub.ravel(), Vb.ravel()], axis=1).astype(np.float64)
        _, idx = self.tree.query(q, workers=-1)
        i = self.seg_of[idx]
        d = self._dist_seg(q, i)
        for sh in (-1, 1):
            d = np.minimum(d, self._dist_seg(q, (i + sh) % self.n))
        ins = self._inside(q)
        return np.where(ins, -d, d).astype(F32).reshape(shape)


def prism(poly, plane_, w0, w1, rim=0.0, rim1=None, off=0.0):
    """Контур в плоскости plane_ («XZ», «XY» или «YZ»: первая буква — ось u, вторая — v), выдавленный по третьей оси
    от w0 до w1. rim — скругление кромок торцов (rim1 — у торца w1, если другое); off — сдвиг контура наружу (мм)."""
    ku = "XYZ".index(plane_[0]); kv = "XYZ".index(plane_[1])
    kw = 3 - ku - kv
    lo, hi = min(w0, w1), max(w0, w1)

    def f(X, Y, Z):
        P = (X, Y, Z)
        d2 = poly.sd(P[ku], P[kv]) - off
        if rim1 is None:
            return i_round(d2, np.abs(P[kw] - (lo + hi) / 2) - (hi - lo) / 2, rim)
        d = i_round(d2, lo - P[kw], rim)
        return i_round(d, P[kw] - hi, rim1)
    return f


# ---------- преобразования ----------

def rot(fn, axis, origin, deg):
    """Тело fn, повёрнутое на deg градусов вокруг оси axis через точку origin (x, y, z) (правый винт)."""
    k = "XYZ".index(axis)
    a = math.radians(deg); ca, sa = math.cos(a), math.sin(a)
    i, j = [(1, 2), (2, 0), (0, 1)][k]

    def f(X, Y, Z):
        P = [X, Y, Z]
        u = P[i] - origin[i]; v = P[j] - origin[j]
        # обратный поворот точки запроса
        Q = list(P)
        Q[i] = origin[i] + u * ca + v * sa
        Q[j] = origin[j] - u * sa + v * ca
        return fn(*Q)
    return f


def move(fn, d):
    def f(X, Y, Z):
        return fn(X - d[0], Y - d[1], Z - d[2])
    return f


def both(fn, r=0.0):
    """fn и его зеркало по Y."""
    def f(X, Y, Z):
        return u_round(fn(X, Y, Z), fn(X, -Y, Z), r)
    return f


def union(*fns, r=0.0):
    def f(X, Y, Z):
        d = fns[0](X, Y, Z)
        for g in fns[1:]:
            d = u_round(d, g(X, Y, Z), r)
        return d
    return f


def inter(*fns, r=0.0):
    def f(X, Y, Z):
        d = fns[0](X, Y, Z)
        for g in fns[1:]:
            d = i_round(d, g(X, Y, Z), r)
        return d
    return f


def minus(fa, fb, r=0.0):
    def f(X, Y, Z):
        return cut(fa(X, Y, Z), fb(X, Y, Z), r)
    return f


# ---------- сетка вокселей ----------

class Field:
    def __init__(self, name, lo, hi, h):
        self.name = name
        self.h = float(h)
        self.lo = np.array(lo, float)
        self.n = np.ceil((np.array(hi, float) - self.lo) / h).astype(int) + 1
        self.F = np.full(tuple(self.n), BIG, F32)
        self.t0 = time.time()

    def _win(self, bbox, pad):
        sl = []
        for k in range(3):
            if bbox is None:
                i0, i1 = 0, self.n[k]
            else:
                i0 = max(0, int(math.floor((bbox[0][k] - pad - self.lo[k]) / self.h)))
                i1 = min(self.n[k], int(math.ceil((bbox[1][k] + pad - self.lo[k]) / self.h)) + 1)
            sl.append((i0, max(i0, i1)))
        return sl

    def _axes(self, sl):
        ax = [(self.lo[k] + self.h * np.arange(sl[k][0], sl[k][1])).astype(F32) for k in range(3)]
        return ax[0][:, None, None], ax[1][None, :, None], ax[2][None, None, :]

    def apply(self, fn, op="union", r=0.0, bbox=None, pad=None, slab_n=40):
        """Применяет тело fn к полю в окне bbox (((x0,y0,z0),(x1,y1,z1)) или None — всё поле). op: union, cut,
        inter, cut_chamfer; r — радиус (у union — галтель, у cut/inter — скругление кромки)."""
        if pad is None:
            pad = r + 2 * self.h
        sl = self._win(bbox, pad)
        if any(b <= a for a, b in sl):
            return
        for i0 in range(sl[0][0], sl[0][1], slab_n):
            i1 = min(sl[0][1], i0 + slab_n)
            s = ((i0, i1), sl[1], sl[2])
            X, Y, Z = self._axes(s)
            d = fn(X, Y, Z)
            view = self.F[i0:i1, sl[1][0]:sl[1][1], sl[2][0]:sl[2][1]]
            if op == "union":
                view[...] = u_round(view, d, r)
            elif op == "cut":
                view[...] = cut(view, d, r)
            elif op == "inter":
                view[...] = i_round(view, d, r)
            elif op == "cut_chamfer":
                view[...] = cut_chamfer(view, d, r)
            else:
                raise ValueError(op)

    def displace(self, fn, bbox=None, slab_n=40):
        """Смещение поверхности: поле уменьшается на fn (плюс — наружу). Для мелкого рельефа (пупырышки, канавки)."""
        sl = self._win(bbox, 2 * self.h)
        if any(b <= a for a, b in sl):
            return
        for i0 in range(sl[0][0], sl[0][1], slab_n):
            i1 = min(sl[0][1], i0 + slab_n)
            X, Y, Z = self._axes(((i0, i1), sl[1], sl[2]))
            view = self.F[i0:i1, sl[1][0]:sl[1][1], sl[2][0]:sl[2][1]]
            view[...] = view - fn(X, Y, Z)

    def add(self, fn, r=0.0, bbox=None, **kw):
        self.apply(fn, "union", r, bbox, **kw)

    def sub(self, fn, r=0.0, bbox=None, **kw):
        self.apply(fn, "cut", r, bbox, **kw)


    def save(self, path, **meta):
        """Поле (узкая полоса у поверхности, float16) — сетку из него строит сборщик в Blender (OpenVDB, адаптивно)."""
        band = 4 * self.h
        A = np.clip(self.F, -band, band).astype(np.float16)
        np.savez(path, field=A, h=self.h, lo=self.lo, **meta)
        ins = int((self.F < 0).sum())
        print(f"FIELD {self.name}: {tuple(int(v) for v in self.n)} вокселей по {self.h} мм, объём {ins * self.h ** 3 / 1000:.2f} см3, "
              f"{time.time() - self.t0:.1f} с", flush=True)


# ---------- плоские фигуры: функции f2(U, V) → поле; объединяются на плоскости и выдавливаются prism2 ----------
# (объединение выдавленных тел с общей плоской гранью и галтелью вспучивает эту грань — стыки делаем на плоскости)

def rect2(u0, u1, v0, v1, r=0.0):
    cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
    hu, hv = abs(u1 - u0) / 2 - r, abs(v1 - v0) / 2 - r

    def f(U, V):
        q1 = np.abs(U - cu) - hu; q2 = np.abs(V - cv) - hv
        return np.hypot(np.maximum(q1, 0), np.maximum(q2, 0)) + np.minimum(np.maximum(q1, q2), 0) - r
    return f


def circle2(c, r):
    def f(U, V):
        return np.hypot(U - c[0], V - c[1]) - r
    return f


def seg2(p0, p1, r):
    """Отрезок со скруглёнными концами (полоса шириной 2r)."""
    du, dv = p1[0] - p0[0], p1[1] - p0[1]
    L2 = du * du + dv * dv

    def f(U, V):
        t = np.clip(((U - p0[0]) * du + (V - p0[1]) * dv) / L2, 0, 1)
        return np.hypot(U - p0[0] - t * du, V - p0[1] - t * dv) - r
    return f


def union2(*fns, r=0.0):
    def f(U, V):
        d = fns[0](U, V)
        for g in fns[1:]:
            d = u_round(d, g(U, V), r)
        return d
    return f


def minus2(fa, fb, r=0.0):
    def f(U, V):
        return cut(fa(U, V), fb(U, V), r)
    return f


def prism2(fn2, plane_, w0, w1, rim=0.0, rim1=None):
    """Плоская фигура fn2 в плоскости plane_ («XZ», «XY», «YZ»), выдавленная по третьей оси от w0 до w1."""
    ku = "XYZ".index(plane_[0]); kv = "XYZ".index(plane_[1])
    kw = 3 - ku - kv
    lo, hi = min(w0, w1), max(w0, w1)

    def f(X, Y, Z):
        P = (X, Y, Z)
        d2 = fn2(P[ku], P[kv])
        if rim1 is None:
            return i_round(d2, np.abs(P[kw] - (lo + hi) / 2) - (hi - lo) / 2, rim)
        d = i_round(d2, lo - P[kw], rim)
        return i_round(d, P[kw] - hi, rim1)
    return f


def helix_mesh(c, R, wire_r, x0, x1, pitch, seg_turn=32, seg_wire=12, dead=1.25):
    """Витая пружина вдоль оси X через точку c (y, z): сетка трубки. dead — поджатые витки на концах."""
    L = abs(x1 - x0)
    d = 2 * wire_r
    turns_dead = dead
    Ld = turns_dead * d * 1.02
    turns_live = max(1.0, (L - 2 * Ld - d) / pitch)
    total = 2 * turns_dead + turns_live
    n = int(total * seg_turn) + 1
    pts = []
    for i in range(n):
        t = i / (n - 1) * total
        if t < turns_dead:
            x = t / turns_dead * Ld
        elif t > total - turns_dead:
            x = (L - d) - (total - t) / turns_dead * Ld
        else:
            x = Ld + (t - turns_dead) / turns_live * (L - d - 2 * Ld)
        a = 2 * math.pi * t
        pts.append((min(x0, x1) + wire_r + x, c[0] + R * math.cos(a), c[1] + R * math.sin(a)))
    return tube_mesh(np.array(pts), wire_r, seg_wire)


def tube_mesh(P, r, seg=12):
    """Трубка радиуса r вдоль ломаной P (N×3) с закрытыми торцами: вершины и четырёхугольники."""
    P = np.asarray(P, float)
    n = len(P)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1)[:, None]
    # опорный вектор без кручения: переносим нормаль вдоль ломаной
    N = np.zeros_like(P)
    up = np.array([1.0, 0.0, 0.0]) if abs(T[0, 0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    v = up - T[0] * (up @ T[0]); N[0] = v / np.linalg.norm(v)
    for i in range(1, n):
        v = N[i - 1] - T[i] * (N[i - 1] @ T[i])
        N[i] = v / np.linalg.norm(v)
    B = np.cross(T, N)
    ang = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    V = (P[:, None, :] + r * (np.cos(ang)[None, :, None] * N[:, None, :] + np.sin(ang)[None, :, None] * B[:, None, :])).reshape(-1, 3)
    idx = np.arange(n * seg).reshape(n, seg)
    a = idx[:-1]; b = idx[1:]
    Q = np.stack([a, np.roll(a, -1, axis=1), np.roll(b, -1, axis=1), b], axis=-1).reshape(-1, 4)
    # торцы: веером к центральной вершине (вырожденными четырёхугольниками не пользуемся — два треугольника в квад)
    c0 = len(V); c1 = len(V) + 1
    V = np.vstack([V, P[0] - T[0] * r * 0.6, P[-1] + T[-1] * r * 0.6])
    caps = []
    for k in range(0, seg, 2):
        caps.append([c0, idx[0, (k + 2) % seg], idx[0, (k + 1) % seg], idx[0, k]])
        caps.append([c1, idx[-1, k], idx[-1, (k + 1) % seg], idx[-1, (k + 2) % seg]])
    Q = np.vstack([Q, np.array(caps)])
    return V.astype(F32), Q.astype(np.int32)


# ---------- надписи и знаки: плоское поле из растра шрифта ----------

def text2(text, font_path, cap_h, ppm=48, track=0.0):
    """Надпись как плоская фигура: возвращает (f2, ширина мм). Начало — левый край на базовой линии, U вправо,
    V вверх; cap_h — высота прописной буквы, мм; track — добавка к межбуквенному расстоянию, мм."""
    from PIL import Image, ImageDraw, ImageFont
    from scipy.ndimage import distance_transform_edt, map_coordinates, gaussian_filter
    size = 200
    font = ImageFont.truetype(font_path, size)
    cap = font.getbbox("Н")
    k = cap_h * ppm / (cap[3] - cap[1])
    font = ImageFont.truetype(font_path, max(8, int(round(size * k))))
    asc, desc = font.getmetrics()
    pad = int(ppm * 1.5)
    xs = [0.0]
    for ch in text:
        xs.append(xs[-1] + font.getlength(ch) + track * ppm)
    wpx = int(xs[-1]) + 2 * pad; hpx = asc + desc + 2 * pad
    im = Image.new("L", (wpx, hpx), 0)
    dr = ImageDraw.Draw(im)
    for ch, x in zip(text, xs):
        dr.text((pad + x, pad), ch, fill=255, font=font)
    a = gaussian_filter(np.asarray(im, np.float32) / 255.0, 0.6) > 0.5
    sd = (distance_transform_edt(~a) - distance_transform_edt(a)).astype(np.float32) / ppm
    sd = gaussian_filter(sd, 0.8)
    base_row = pad + asc

    def f(U, V):
        Ub, Vb = np.broadcast_arrays(U, V)
        col = Ub * ppm + pad; row = base_row - Vb * ppm
        out = map_coordinates(sd, [row.ravel(), col.ravel()], order=1, mode="nearest").reshape(Ub.shape)
        far = (col < 0) | (col > wpx - 1) | (row < 0) | (row > hpx - 1)
        return np.where(far, 1.0, out).astype(F32)
    return f, (xs[-1] - track * ppm) / ppm


def sign2(size=8.4, t=0.5):
    """Знак марки (вымышленный): четырёхлучевая звезда в скруглённом квадрате; центр в начале координат."""
    hs = size / 2

    def f(U, V):
        frame = np.abs(rect2(-hs, hs, -hs, hs, 1.6)(U, V) + t / 2) - t / 2
        k = (hs - 1.5) ** (2.0 / 3.0)
        star = (np.abs(U) ** (2.0 / 3.0) + np.abs(V) ** (2.0 / 3.0) - k) * 1.2
        return np.minimum(frame, star)
    return f


def engrave(F, f2, plane_, origin, u_dir, w_face, side, depth=0.2, wall=0.12, bbox=None):
    """Гравировка плоской фигуры f2 в грань, перпендикулярную третьей оси. plane_ — оси фигуры («XZ»: U вдоль X,
    V вдоль Z), origin — место начала фигуры (u, v), u_dir = ±1 — направление чтения вдоль первой оси, w_face —
    координата грани, side = ±1 — с какой стороны тело (грань смотрит в сторону side). depth < 0 — выпуклый рельеф."""
    ku = "XYZ".index(plane_[0]); kv = "XYZ".index(plane_[1])
    kw = 3 - ku - kv

    def fn(X, Y, Z):
        P = (X, Y, Z)
        d = f2((P[ku] - origin[0]) * u_dir, P[kv] - origin[1])
        prof = depth * np.clip(-d / wall, 0, 1)
        near = smoothstep((1.2 - np.abs(P[kw] - w_face)) / 0.3)
        return -prof * near
    F.displace(fn, bbox=bbox)
