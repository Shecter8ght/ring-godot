"""«Проспект», ограждения и город: общие помощники генераторов формы (Blender 5, bpy + numpy).

Сетка копится в построителе MB (вершины, грани, материал грани) и создаётся одним объектом через foreach_set —
так быстро и для сотен тысяч граней (спираль колючки, профлист). Оси — как у игры (tools/urban95_export.py):
Blender X = игровой X, Blender Z = вверх, Blender −Y = игровое +Z (лицо набора MallFiller). Начало координат —
на земле в центре набора, как у серых наборов `KITS` (src/blockout/mall_filler.gd).

Материалы REVIEW_* — только для просмотра формы (цвет, блеск); производственные UV и отделка — после принятия.
"""
from __future__ import annotations

import math
from pathlib import Path

import bmesh
import bpy
import numpy as np

# имя: (цвет, шероховатость, металл) — нейтральные, чтобы читалась форма, а не отделка
MATS: dict[str, tuple] = {
    "concrete": ((0.50, 0.49, 0.46), 0.92, 0.0),
    "concrete_old": ((0.42, 0.41, 0.38), 0.95, 0.0),
    "mortar": ((0.56, 0.55, 0.52), 0.95, 0.0),
    "rebar": ((0.33, 0.24, 0.18), 0.75, 0.9),
    "steel": ((0.32, 0.32, 0.31), 0.55, 1.0),
    "steel_dark": ((0.17, 0.17, 0.17), 0.6, 1.0),
    "galv": ((0.64, 0.65, 0.64), 0.38, 1.0),
    "wire": ((0.55, 0.56, 0.56), 0.32, 1.0),
    "razor": ((0.72, 0.73, 0.73), 0.25, 1.0),
    "rust": ((0.40, 0.22, 0.12), 0.85, 0.3),
    "paint_green": ((0.16, 0.30, 0.20), 0.55, 0.0),
    "paint_blue": ((0.16, 0.26, 0.42), 0.55, 0.0),
    "paint_brown": ((0.36, 0.20, 0.12), 0.6, 0.0),
    "paint_grey": ((0.46, 0.48, 0.47), 0.55, 0.0),
    "paint_white": ((0.80, 0.80, 0.77), 0.5, 0.0),
    "paint_red": ((0.55, 0.10, 0.08), 0.5, 0.0),
    "paint_yellow": ((0.80, 0.62, 0.10), 0.5, 0.0),
    "paint_black": ((0.05, 0.05, 0.05), 0.5, 0.0),
    "brick_white": ((0.72, 0.70, 0.64), 0.9, 0.0),
    "brick_red": ((0.50, 0.25, 0.17), 0.9, 0.0),
    "roofing": ((0.09, 0.09, 0.09), 0.8, 0.0),
    "rubber": ((0.04, 0.04, 0.04), 0.85, 0.0),
    "plywood": ((0.52, 0.40, 0.26), 0.8, 0.0),
    "wood": ((0.45, 0.32, 0.20), 0.75, 0.0),
    "glass": ((0.20, 0.27, 0.28), 0.05, 0.0),
    "porcelain": ((0.55, 0.30, 0.18), 0.15, 0.0),
    "porcelain_white": ((0.82, 0.82, 0.80), 0.15, 0.0),
    "lamp": ((0.85, 0.84, 0.78), 0.2, 0.0),
    "plastic_dark": ((0.10, 0.10, 0.10), 0.5, 0.0),
    "ground": ((0.16, 0.16, 0.155), 0.9, 0.0),
    "soil": ((0.24, 0.19, 0.14), 0.95, 0.0),
}


def mat(name: str) -> bpy.types.Material:
    key = "REVIEW_" + name
    m = bpy.data.materials.get(key)
    if m:
        return m
    col, rough, metal = MATS[name]
    m = bpy.data.materials.new(key)
    m.diffuse_color = (*col, 1.0)
    m.roughness = rough
    m.metallic = metal
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*col, 1.0)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if name == "glass":
        p.inputs["Alpha"].default_value = 0.35
        m.diffuse_color = (*col, 0.45)
        m.surface_render_method = "BLENDED"
    return m


# ---------------------------------------------------------------- матрицы и простые преобразования
def rot(axis: str, deg: float) -> np.ndarray:
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def xf(V: np.ndarray, R: np.ndarray | None = None, t=(0.0, 0.0, 0.0)) -> np.ndarray:
    V = np.asarray(V, dtype=float)
    if R is not None:
        V = V @ np.asarray(R).T
    return V + np.asarray(t, dtype=float)


def frame_from(d, up=(0.0, 0.0, 1.0)) -> np.ndarray:
    """Ортонормированная тройка (ex, ey, d) с d вдоль заданного направления."""
    d = np.asarray(d, float)
    d = d / np.linalg.norm(d)
    u = np.asarray(up, float)
    if abs(u @ d) > 0.98:
        u = np.array([1.0, 0, 0]) if abs(d[0]) < 0.9 else np.array([0, 1.0, 0])
    ex = np.cross(u, d)
    ex /= np.linalg.norm(ex)
    ey = np.cross(d, ex)
    return np.stack([ex, ey, d])


# ---------------------------------------------------------------- построитель сетки
class MB:
    """Копилка сетки: части добавляются в мировых координатах объекта; weld — сварка совпадающих вершин."""

    def __init__(self) -> None:
        self.V: list[np.ndarray] = []
        self.F: list[list[int]] = []
        self.M: list[str] = []
        self.S: list[bool] = []
        self.n = 0

    def add(self, V, F, m: str = "concrete", smooth: bool = False) -> int:
        V = np.asarray(V, dtype=float).reshape(-1, 3)
        base = self.n
        self.V.append(V)
        for f in F:
            self.F.append([int(i) + base for i in f])
        self.M.extend([m] * len(F))
        self.S.extend([smooth] * len(F))
        self.n += len(V)
        return base

    def extend(self, part: tuple, m: str = "concrete", smooth: bool = False) -> int:
        return self.add(part[0], part[1], m, smooth)

    def empty(self) -> bool:
        return self.n == 0

    def build(self, name: str, col: bpy.types.Collection, parent: bpy.types.Object | None = None,
              bevel: float = 0.0, seg: int = 2, sharp: float = 32.0, weld: float = 0.0,
              bevel_angle: float = 30.0, recalc: bool = True) -> bpy.types.Object:
        V = np.vstack(self.V) if self.V else np.zeros((0, 3))
        F = self.F
        if weld > 0 and len(V):
            key = np.round(V / weld).astype(np.int64)
            _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
            inv = inv.reshape(-1)
            V = V[first]
            F2, M2, S2 = [], [], []
            for f, m, s in zip(F, self.M, self.S):
                g = [int(inv[i]) for i in f]
                h = [g[0]] + [g[k] for k in range(1, len(g)) if g[k] != g[k - 1]]
                if len(h) > 1 and h[-1] == h[0]:
                    h.pop()
                if len(h) >= 3 and len(set(h)) == len(h):
                    F2.append(h)
                    M2.append(m)
                    S2.append(s)
            F, self.M, self.S = F2, M2, S2
        me = bpy.data.meshes.new(name)
        me.vertices.add(len(V))
        me.vertices.foreach_set("co", V.astype(np.float32).ravel())
        sizes = np.array([len(f) for f in F], dtype=np.int32)
        idx = np.fromiter((i for f in F for i in f), dtype=np.int32, count=int(sizes.sum()))
        me.loops.add(len(idx))
        me.loops.foreach_set("vertex_index", idx)
        me.polygons.add(len(F))
        starts = np.r_[0, np.cumsum(sizes)[:-1]].astype(np.int32)
        me.polygons.foreach_set("loop_start", starts)
        names = list(dict.fromkeys(self.M))
        for nm in names:
            me.materials.append(mat(nm))
        mi = np.array([names.index(m) for m in self.M], dtype=np.int32)
        me.polygons.foreach_set("material_index", mi)
        me.update(calc_edges=True)
        me.validate(clean_customdata=False)
        if recalc:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(me)
            bm.free()
        sm = np.array(self.S, dtype=bool)
        if sm.any():
            me.polygons.foreach_set("use_smooth", sm)
        me.set_sharp_from_angle(angle=math.radians(sharp))
        ob = bpy.data.objects.new(name, me)
        col.objects.link(ob)
        if parent is not None:
            ob.parent = parent
        if bevel > 0:
            b = ob.modifiers.new("Фаска", "BEVEL")
            b.width = bevel
            b.segments = seg
            b.limit_method = "ANGLE"
            b.angle_limit = math.radians(bevel_angle)
            b.use_clamp_overlap = True
            b.miter_outer = "MITER_ARC"
        return ob


# ---------------------------------------------------------------- примитивы: (V, F)
def box(c, s, R=None) -> tuple:
    c = np.asarray(c, float)
    h = np.asarray(s, float) / 2
    V = np.array([[x, y, z] for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)], float) * h
    if R is not None:
        V = V @ np.asarray(R).T
    V += c
    F = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return V, F


def box2(p0, p1) -> tuple:
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    return box((p0 + p1) / 2, np.abs(p1 - p0))


def prism(poly, h0: float, h1: float, origin=(0, 0, 0), ex=(1, 0, 0), ey=(0, 1, 0), ez=(0, 0, 1),
          caps: bool = True) -> tuple:
    """Многоугольник (a, b) плоскости ex/ey, выдавленный по ez от h0 до h1. Обход — против часовой."""
    P = np.asarray(poly, float)
    n = len(P)
    o, ex, ey, ez = (np.asarray(v, float) for v in (origin, ex, ey, ez))
    V = []
    for h in (h0, h1):
        for a, b in P:
            V.append(o + ex * a + ey * b + ez * h)
    F = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    if caps:
        F.append(tuple(range(n - 1, -1, -1)))
        F.append(tuple(range(n, 2 * n)))
    return np.array(V), F


def loft(rings: list, closed: bool = True, cap0: bool = False, cap1: bool = False) -> tuple:
    """Кольца с одинаковым числом точек → поверхность (каждое кольцо — (m,3))."""
    R = [np.asarray(r, float) for r in rings]
    m = len(R[0])
    V = np.vstack(R)
    F = []
    for k in range(len(R) - 1):
        a, b = k * m, (k + 1) * m
        rng = range(m) if closed else range(m - 1)
        for i in rng:
            j = (i + 1) % m
            F.append((a + i, a + j, b + j, b + i))
    if cap0:
        F.append(tuple(range(m - 1, -1, -1)))
    if cap1:
        F.append(tuple(range((len(R) - 1) * m, len(R) * m)))
    return V, F


def path_frames(P: np.ndarray, up=(0.0, 0.0, 1.0), closed: bool = False) -> tuple:
    """Касательные и перенос рамки вдоль ломаной (без закрутки)."""
    P = np.asarray(P, float)
    n = len(P)
    T = np.zeros_like(P)
    if closed:
        T = np.roll(P, -1, 0) - np.roll(P, 1, 0)
    else:
        T[1:-1] = P[2:] - P[:-2]
        T[0] = P[1] - P[0]
        T[-1] = P[-1] - P[-2]
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    N = np.zeros_like(P)
    f = frame_from(T[0], up)
    N[0] = f[1]
    for i in range(1, n):
        v = N[i - 1] - T[i] * (N[i - 1] @ T[i])
        ln = np.linalg.norm(v)
        N[i] = v / ln if ln > 1e-9 else frame_from(T[i], up)[1]
    B = np.cross(T, N)
    return T, N, B


def sweep(profile, path, closed_profile: bool = True, closed_path: bool = False, up=(0.0, 0.0, 1.0),
          scale=None, caps: bool = True, N_override=None) -> tuple:
    """Профиль (a, b) по ломаной: a — вдоль бинормали, b — вдоль нормали рамки (N ≈ «вверх» при up)."""
    pr = np.asarray(profile, float)
    P = np.asarray(path, float)
    T, N, B = path_frames(P, up, closed_path)
    if N_override is not None:
        N = np.asarray(N_override, float)
        B = np.cross(T, N)
    sc = np.ones(len(P)) if scale is None else np.asarray(scale, float)
    rings = [P[i] + sc[i] * (np.outer(pr[:, 0], B[i]) + np.outer(pr[:, 1], N[i])) for i in range(len(P))]
    if closed_path:
        rings.append(rings[0])
    V, F = loft(rings, closed_profile, caps and closed_profile and not closed_path,
                caps and closed_profile and not closed_path)
    return V, F


def circle(r: float, n: int = 8, start: float = 0.0) -> np.ndarray:
    a = start + np.arange(n) * 2 * np.pi / n
    return np.c_[np.cos(a) * r, np.sin(a) * r]


def tube(path, r: float, n: int = 8, closed_path: bool = False, up=(0.0, 0.0, 1.0), caps: bool = True) -> tuple:
    return sweep(circle(r, n), path, True, closed_path, up, caps=caps)


def lathe(rz, n: int = 24, center=(0, 0, 0), R=None, a0: float = 0.0, a1: float = 2 * np.pi,
          cap_bottom: bool = True, cap_top: bool = True) -> tuple:
    """Тело вращения вокруг Z: профиль (r, z) снизу вверх. r = 0 на конце — точка (полюс)."""
    rz = np.asarray(rz, float)
    full = abs(a1 - a0 - 2 * np.pi) < 1e-6
    k = n if full else n + 1
    ang = a0 + np.arange(k) * (a1 - a0) / n
    rings = [np.c_[np.cos(ang) * r, np.sin(ang) * r, np.full(k, z)] for r, z in rz]
    V, F = loft(rings, full)
    m = k
    if cap_bottom and rz[0][0] > 1e-9 and full:
        F.append(tuple(range(m - 1, -1, -1)))
    if cap_top and rz[-1][0] > 1e-9 and full:
        F.append(tuple(range((len(rz) - 1) * m, len(rz) * m)))
    if R is not None:
        V = V @ np.asarray(R).T
    return V + np.asarray(center, float), F


def cyl(c, r: float, h: float, n: int = 16, axis: str = "z") -> tuple:
    V, F = lathe([(r, -h / 2), (r, h / 2)], n)
    R = None if axis == "z" else (rot("y", 90) if axis == "x" else rot("x", -90))
    return xf(V, R, c), F


def cyl_between(a, b, r: float, n: int = 12, caps: bool = True) -> tuple:
    return tube(np.array([a, b], float), r, n, caps=caps)


def angle_profile(w: float, t: float) -> np.ndarray:
    """Уголок w×w×t (по часовой оси внутрь): полка по a и по b от угла (0, 0)."""
    return np.array([(0, 0), (w, 0), (w, t), (t, t), (t, w), (0, w)], float)


def channel_profile(h: float, b: float, t: float) -> np.ndarray:
    """Швеллер: стенка h по оси b, полки b по оси a, центр стенки у a = 0."""
    return np.array([(0, -h / 2), (b, -h / 2), (b, -h / 2 + t), (t, -h / 2 + t), (t, h / 2 - t), (b, h / 2 - t),
                     (b, h / 2), (0, h / 2)], float)


def rect_profile(w: float, h: float, r: float = 0.0, n_arc: int = 3) -> np.ndarray:
    if r <= 0:
        return np.array([(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)], float)
    pts = []
    for cx, cy, a0 in ((w / 2 - r, -h / 2 + r, -90), (w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                       (-w / 2 + r, -h / 2 + r, 180)):
        for k in range(n_arc + 1):
            a = math.radians(a0 + 90 * k / n_arc)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return np.array(pts)


def irregular_chunk(c, s, rng: np.random.Generator, jitter: float = 0.25) -> tuple:
    """Обломок: коробка 3×3×3 с раздёрнутыми вершинами (неровные грани скола)."""
    g = np.linspace(-1, 1, 3)
    pts = {}
    V = []
    idx = {}
    for i, x in enumerate(g):
        for j, y in enumerate(g):
            for k, z in enumerate(g):
                if 0 < i < 2 and 0 < j < 2 and 0 < k < 2:
                    continue
                idx[(i, j, k)] = len(V)
                V.append([x, y, z])
    V = np.array(V) * np.asarray(s, float) / 2
    V += rng.uniform(-jitter, jitter, V.shape) * np.asarray(s, float) / 2
    F = []

    def q(a, b, c_, d):
        F.append((idx[a], idx[b], idx[c_], idx[d]))
    for i in range(2):
        for j in range(2):
            q((i, j, 0), (i, j + 1, 0), (i + 1, j + 1, 0), (i + 1, j, 0))
            q((i, j, 2), (i + 1, j, 2), (i + 1, j + 1, 2), (i, j + 1, 2))
            q((i, 0, j), (i + 1, 0, j), (i + 1, 0, j + 1), (i, 0, j + 1))
            q((i, 2, j), (i, 2, j + 1), (i + 1, 2, j + 1), (i + 1, 2, j))
            q((0, i, j), (0, i, j + 1), (0, i + 1, j + 1), (0, i + 1, j))
            q((2, i, j), (2, i + 1, j), (2, i + 1, j + 1), (2, i, j + 1))
    return V + np.asarray(c, float), F


def inside_poly(poly, x: float, y: float) -> bool:
    """Точка внутри многоугольника (чётность пересечений луча)."""
    P = np.asarray(poly, float)
    inside = False
    n = len(P)
    for i in range(n):
        (x0, y0), (x1, y1) = P[i], P[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            if x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
                inside = not inside
    return inside


# ---------------------------------------------------------------- сцена
def reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"


def collection(name: str) -> bpy.types.Collection:
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def root(name: str, col: bpy.types.Collection, loc=(0, 0, 0)) -> bpy.types.Object:
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "PLAIN_AXES"
    e.empty_display_size = 0.5
    e.location = loc
    col.objects.link(e)
    return e


def pivot(name: str, col: bpy.types.Collection, parent, loc, rot_euler=(0, 0, 0)) -> bpy.types.Object:
    """Пустышка-шарнир: деталь — её дочерний объект, поворот пустышки открывает деталь."""
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "ARROWS"
    e.empty_display_size = 0.3
    col.objects.link(e)
    e.parent = parent
    e.location = loc
    e.rotation_euler = rot_euler
    return e


def parent_keep(ob: bpy.types.Object, parent: bpy.types.Object) -> None:
    """Сделать дочерним, сохранив мировое положение (сетка задана в мировых координатах)."""
    bpy.context.view_layer.update()
    mw = ob.matrix_world.copy()
    ob.parent = parent
    ob.matrix_parent_inverse = parent.matrix_world.inverted()
    ob.matrix_world = mw


def save(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.view_layer.update()
    bpy.context.preferences.filepaths.save_version = 0      # без .blend1 — файл пересобирается генератором
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
