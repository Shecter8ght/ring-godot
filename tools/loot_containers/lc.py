"""Общие построители контейнеров для лута, партия 1 (Blender 5, bmesh). Соглашения — как у вещей общежития партии 3
(tools/dorm_modules/build_items3.py): метры, Z вверх, лицо к −Y, корень-пустышка на опоре (у настенных — на плоскости
лица), у каждого состояния своя коллекция и свой корень, подвижные детали — объекты с началом в оси шарнира / у лица
ящика (геометрия построена в осях предмета, потом сдвинута на -pivot), вещи на подвижной детали — её дочерние узлы.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "dorm_modules"))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import build_furniture as B  # noqa: E402
import mlib as L  # noqa: E402
from build_found_lights import lathe  # noqa: E402

V = Vector
TAU = 2 * math.pi
obj = B.obj


def mats() -> dict:
    return {
        "steel_a": L.material("Сталь_окраска_светлая", (0.55, 0.56, 0.54), 0.45, 0.3),
        "steel_b": L.material("Сталь_окраска_тёмная", (0.16, 0.2, 0.17), 0.45, 0.3),
        "steel_c": L.material("Сталь_окраска_серая", (0.35, 0.36, 0.37), 0.45, 0.3),
        "chrome": L.material("Хром_нержавейка", (0.75, 0.75, 0.74), 0.2, 1.0),
        "steel_raw": L.material("Сталь_голая", (0.5, 0.5, 0.49), 0.4, 1.0),
        "brass": L.material("Латунь", (0.7, 0.55, 0.25), 0.3, 1.0),
        "plastic_black": L.material("Пластик_чёрный", (0.03, 0.03, 0.03), 0.45),
        "plastic_grey": L.material("Пластик_серый", (0.3, 0.3, 0.3), 0.45),
        "plastic_beige": L.material("Пластик_бежевый", (0.65, 0.62, 0.52), 0.45),
        "plastic_white": L.material("Пластик_белый", (0.8, 0.8, 0.78), 0.4),
        "rubber": L.material("Резина", (0.02, 0.02, 0.02), 0.85),
        "glass_dark": L.material("Стекло_тёмное", (0.05, 0.06, 0.07), 0.05, 0.0, 0.5),
        "screen": L.material("Экран", (0.01, 0.015, 0.02), 0.08),
        "paper": L.material("Бумага", (0.85, 0.84, 0.8), 0.8),
        "folder": L.material("Папка_картон", (0.55, 0.62, 0.45), 0.7),
        "felt": L.material("Войлок", (0.12, 0.1, 0.08), 0.95),
        "fabric": L.material("Ткань_сумка", (0.32, 0.03, 0.03), 0.75),
        "fabric_dark": L.material("Ткань_подкладка", (0.1, 0.1, 0.11), 0.85),
        "webbing": L.material("Стропа", (0.04, 0.04, 0.04), 0.85),
        "reflect": L.material("Лента_светоотражающая", (0.75, 0.78, 0.7), 0.35),
        "zip": L.material("Молния", (0.02, 0.02, 0.02), 0.6),
        "elastic": L.material("Резинка", (0.04, 0.04, 0.04), 0.9),
        "foam": L.material("Пенопласт_вкладыш", (0.18, 0.18, 0.2), 0.9),
    }


def mat_faces(faces, idx: int) -> None:
    for f in faces:
        f.material_index = idx


# ---------------------------------------------------------------- скруглённые коробки и листовые оболочки

def _axis_nodes(h: float, r: float, seg: int, flat: int) -> list:
    """Узлы по оси от -h до h: на скруглении — по равным углам (0…45°) проекции куба, на плоском — flat делений."""
    t = [r * math.tan(math.radians(45.0 * k / seg)) for k in range(seg + 1)]
    lo = [-(h - r) - tk for tk in reversed(t)]
    hi = [(h - r) + tk for tk in t]
    mid = []
    span = 2 * (h - r)
    if flat > 0 and span > 1e-6:
        mid = [-(h - r) + span * k / (flat + 1) for k in range(1, flat + 1)]
    return lo + mid + hi


def rbox(bm, size, r: float, center=(0, 0, 0), seg: int = 3, flat=(0, 0, 0), open_: str | None = None) -> list:
    """Коробка со скруглением r по всем рёбрам (узлы — на равных углах скругления), без внутренних вершин.
    open_ — «-y», «+z» …: грань с этой стороны не строится (оболочка для Solidify)."""
    hs = [s / 2 for s in size]
    r = min(r, min(hs) - 1e-5)
    ns = [_axis_nodes(hs[i], r, seg, flat[i]) for i in range(3)]
    cache = {}

    def vert(i, j, k):
        key = (i, j, k)
        if key not in cache:
            p = V((ns[0][i], ns[1][j], ns[2][k]))
            inner = V([max(-hs[a] + r, min(hs[a] - r, p[a])) for a in range(3)])
            d = p - inner
            if d.length > 1e-9:
                p = inner + d.normalized() * r
            cache[key] = bm.verts.new(p + V(center))
        return cache[key]

    n = [len(a) for a in ns]
    faces = []
    skip = None
    if open_:
        skip = ("xyz".index(open_[1]), open_[0])
    for ax in range(3):
        for sgn in (-1, 1):
            if skip and skip[0] == ax and (skip[1] == "-") == (sgn < 0):
                continue
            a1, a2 = [i for i in range(3) if i != ax]
            idx = [0, 0, 0]
            idx[ax] = 0 if sgn < 0 else n[ax] - 1
            for p in range(n[a1] - 1):
                for q in range(n[a2] - 1):
                    cs = []
                    for dp, dq in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        ii = list(idx)
                        ii[a1], ii[a2] = p + dp, q + dq
                        cs.append(vert(*ii))
                    # ориентация: нормаль наружу — потом recalc в finish_bm
                    faces.append(bm.faces.new(cs))
    return faces


def shell(bm, size, r: float, center, open_: str | None, seg: int = 3, flat=(0, 0, 0)) -> list:
    return rbox(bm, size, r, center, seg, flat, open_)


def sheet_mod(ob, t: float, bevel: float = 0.0005, segs: int = 2) -> None:
    """Листовая оболочка: Solidify внутрь (наружный габарит не меняется) + узкая фаска кромки листа."""
    md = ob.modifiers.new("Лист", "SOLIDIFY")
    md.thickness = t
    md.offset = -1
    md.use_even_offset = True
    if bevel > 0:
        bv = ob.modifiers.new("Фаска", "BEVEL")
        bv.width = bevel
        bv.segments = segs
        bv.limit_method = "ANGLE"
        bv.angle_limit = math.radians(40)
        bv.harden_normals = False
        bv.use_clamp_overlap = True


MOVERS: dict = {}


def part(bm, name, coll, mlist, parent, ppiv=(0, 0, 0), piv=None, bevel=0.0, segs=2, angle=40.0, smooth=40.0, mover=False):
    """Объект в осях предмета (геометрия bm задана от корня); начало узла — в piv (ось шарнира), родитель — parent
    с началом в ppiv (корень — (0,0,0))."""
    piv = V(piv if piv is not None else ppiv)
    ppiv = V(ppiv)
    ob = obj(bm, name, coll, mlist, parent, bevel=bevel, segs=segs, angle=angle, smooth=smooth)
    ob.data.transform(Matrix.Translation(-piv))
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.location = piv - ppiv
    if mover:
        MOVERS.setdefault(coll.name, []).append(ob)
    return ob


def shell_part(name, coll, mat_list, parent, size, r, center, open_, t, ppiv=(0, 0, 0), piv=None, seg=3, flat=(0, 0, 0),
               bevel=0.0005, mover=False):
    """Листовая оболочка как объект: скруглённая коробка без грани open_, толщина t внутрь."""
    bm = bmesh.new()
    rbox(bm, size, r, center, seg, flat, open_)
    ob = part(bm, name, coll, mat_list, parent, ppiv, piv, smooth=50, mover=mover)
    sheet_mod(ob, t, bevel)
    return ob


# ---------------------------------------------------------------- мелкие детали

def cyl(bm, p0, p1, r, segs=16, r1=None):
    return L.bm_cyl(bm, p0, p1, r, segs=segs, r1=r1)


def plug(bm, c, depth: float = 0.004, r: float = 0.0065, gap: float = 0.0012, axis: str = "-y") -> None:
    """Личинка замка: два полудиска с щелью-пазом (паз виден как углубление). c — центр на плоскости, axis — наружу."""
    sgn = -1 if axis[0] == "-" else 1
    pts = [(math.cos(a) * r, math.sin(a) * r) for a in [math.radians(-85 + 170 * i / 10) for i in range(11)]]
    half = [(max(x, gap / 2), y) for x, y in pts]
    for s in (1, -1):
        poly = [(s * x, y) for x, y in half]
        if s < 0:
            poly = poly[::-1]
        if axis[1] == "y":
            L.bm_prism(bm, poly, V(c), (1, 0, 0), (0, 0, 1), (0, sgn * depth, 0))
        else:
            L.bm_prism(bm, poly, V(c), (1, 0, 0), (0, 1, 0), (0, 0, sgn * depth))


def hole_plate(bm, x0, x1, z0, z1, y0, y1, win, ax: str = "y") -> None:
    """Плита x0…x1 × z0…z1 толщиной y0…y1 с прямоугольным окном win=(wx0, wx1, wz0, wz1): единая замкнутая оболочка
    (кольцо квадов вокруг окна на обеих сторонах), без швов между кусками."""
    wx0, wx1, wz0, wz1 = win
    outer = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    inner = [(wx0, wz0), (wx1, wz0), (wx1, wz1), (wx0, wz1)]
    vo = [[bm.verts.new((x, y, z)) for x, z in outer] for y in (y0, y1)]
    vi = [[bm.verts.new((x, y, z)) for x, z in inner] for y in (y0, y1)]
    for k in range(4):
        j = (k + 1) % 4
        bm.faces.new((vo[0][k], vo[0][j], vi[0][j], vi[0][k]))
        bm.faces.new((vo[1][j], vo[1][k], vi[1][k], vi[1][j]))
        bm.faces.new((vo[0][j], vo[0][k], vo[1][k], vo[1][j]))
        bm.faces.new((vi[0][k], vi[0][j], vi[1][j], vi[1][k]))


def bounds(colls, evaluated: bool = True):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for c in colls:
        for ob in c.all_objects:
            if ob.type == "MESH" and not ob.hide_render:
                ev = ob.evaluated_get(dg)
                pts += [ev.matrix_world @ V(b) for b in ev.bound_box]
    if not pts:
        return V(), V()
    mn = V((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = V((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def tri_count(colls) -> int:
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0
    for c in colls:
        for ob in c.all_objects:
            if ob.type == "MESH":
                me = ob.evaluated_get(dg).to_mesh()
                n += sum(len(p.vertices) - 2 for p in me.polygons)
                ob.evaluated_get(dg).to_mesh_clear()
    return n


def smooth_path(points, n: int = 6):
    pts = [V(p) for p in points]
    out = []
    for i in range(len(pts) - 1):
        p0, p1, p2 = pts[max(i - 1, 0)], pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return out


def rot_box(bm, mn, mx, center, rot: Matrix) -> None:
    """Брус mn…mx (в своих осях), повёрнутый на rot вокруг center."""
    fs = L.bm_box(bm, mn, mx)
    vs = {v for f in fs for v in f.verts}
    c = V(center)
    bmesh.ops.transform(bm, matrix=Matrix.Translation(c) @ rot.to_4x4() @ Matrix.Translation(-c), verts=list(vs))


def tray_door(bm, x0, x1, z0, z1, yf, depth, t, win=None, sgn: int = 1) -> None:
    """Дверь-лоток из кусков листа: лицо толщиной t на y=yf (внутрь к +Y), отбортовка по периметру глубиной depth,
    win=(wx0,wx1,wz0,wz1) — окно в лице."""
    if win is None:
        L.bm_box(bm, (x0, yf, z0), (x1, yf + t, z1))
    else:
        hole_plate(bm, x0, x1, z0, z1, yf, yf + t, win)
    y1 = yf + depth
    L.bm_box(bm, (x0, yf + t, z0), (x0 + t, y1, z1))
    L.bm_box(bm, (x1 - t, yf + t, z0), (x1, y1, z1))
    L.bm_box(bm, (x0 + t, yf + t, z0), (x1 - t, y1, z0 + t))
    L.bm_box(bm, (x0 + t, yf + t, z1 - t), (x1 - t, y1, z1))
