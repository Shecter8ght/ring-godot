"""NPC и игрок: подсумки для магазинов на броне (решения владельца 2026-10-22, docs/design/gear_v2.md) — форма v01.

Одинарные, открытые сверху, по образцу владельца (винтовочный подсумок: корпус, поперечная стропа спереди, MOLLE
сзади); магазин держит не резинка со шнуром, а язычок на липучке с петлёй-тягой (при перезарядке — звук
отрываемой липучки):
- автоматный (одно место на броне) — магазины ВЕРАС-54 на 30 и на 45 (у длинного язычок длиннее — ключ формы
  «Магазин 45»), длинные пистолетные;
- пистолетный (половина места) — Глок на 17 (основа), ПМ (ключ «ПМ»);
- большой (два места) — барабан ВЕРАС-54 на 60 и другие крупные: короб с широким клапаном на липучке.
У язычков и клапана — ключ «Открыт» (магазин выдернули). Магазины — игровые модели из assets (донцем вверх, как
носят в открытом подсумке; барабан — горловиной вверх, под клапаном). Полость считается по магазину с зазором,
проверка печатает зазор каждого магазина до стенок (меньше нуля — магазин в стенке).

Оси подсумка: x — ширина (поперёк, вдоль глубины магазина), y — от брони наружу (+y — лицевая сторона), z — вверх;
низ подсумка — z = 0. Марок нет.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/pouches.py -- [render] [deliver=<папка>]
→ _asset_src/npc_kit/pouches/pouches.blend
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armor_kit as ak  # noqa: E402
import kit_common as kc  # noqa: E402

OUT = kc.WORK / "pouches"
VERSION = "v01"
WEAPONS = kc.ROOT / "assets" / "models" / "weapons"
WALL = 0.0025                   # стенка подсумка (кордура с подкладкой)
GAP = 0.003                     # зазор магазина до стенки
TAB_N = 48                      # отрезков вдоль язычка — одинаково во всех ключах формы


# ---------- магазины ----------

def import_mag(rel: str, keep: tuple[str, ...] | None, name: str) -> bpy.types.Object:
    """Магазин из игровой модели: нужные объекты одним, без LOD; трансформации применены."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(WEAPONS / rel))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH" and not o.name.endswith("LOD1")
              and (keep is None or o.name.split(".")[0] in keep)]
    for o in new:
        if o not in meshes:
            bpy.data.objects.remove(o, do_unlink=True)
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj.name = obj.data.name = name
    return obj


def align_mag(obj: bpy.types.Object, upside_down: bool, turn: bool = True) -> None:
    """Ось горловины (середины сечений в верхних 8 см) — по вертикали; upside_down — донцем вверх (открытый
    подсумок); глубина магазина — по x подсумка, толщина — по y. Горловина — у z = 0, по середине."""
    pts = [v.co.copy() for v in obj.data.vertices]
    zt = max(p.z for p in pts)
    mids = []
    for k in range(20):
        z = zt - 0.004 - k * 0.004
        sl = [p.y for p in pts if abs(p.z - z) < 0.0025]
        if len(sl) > 6 and max(sl) - min(sl) > 0.01:
            mids.append((z, (min(sl) + max(sl)) / 2))
    n = len(mids)
    mz = sum(z for z, _ in mids) / n
    my = sum(y for _, y in mids) / n
    b = sum((z - mz) * (y - my) for z, y in mids) / max(sum((z - mz) ** 2 for z, _ in mids), 1e-12)
    m = Matrix.Rotation(math.atan(b), 4, "X")                   # ось (0, b, 1) → вертикаль
    if upside_down:
        m = Matrix.Rotation(math.pi, 4, "Y") @ m                # донцем вверх
    if turn:
        m = Matrix.Rotation(math.pi / 2, 4, "Z") @ m            # глубина магазина — по x
    obj.data.transform(m)
    co = [v.co for v in obj.data.vertices]
    z0 = min(p.z for p in co)
    end = [p for p in co if p.z - z0 < 0.06] if upside_down else list(co)
    cx = (min(p.x for p in end) + max(p.x for p in end)) / 2
    cy = (min(p.y for p in end) + max(p.y for p in end)) / 2
    obj.data.transform(Matrix.Translation((-cx, -cy, -(min(p.z for p in co)))))
    obj.data.update()


def mag_bvh(obj: bpy.types.Object) -> BVHTree:
    me = obj.data
    return BVHTree.FromPolygons([obj.matrix_world @ v.co for v in me.vertices], [list(p.vertices) for p in me.polygons])


def extents(obj: bpy.types.Object, z0: float, z1: float) -> tuple[float, float, float, float]:
    """Габарит магазина по x и y в слое высот [z0, z1] (с учётом его положения)."""
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    sl = [p for p in pts if z0 <= p.z <= z1]
    return min(p.x for p in sl), max(p.x for p in sl), min(p.y for p in sl), max(p.y for p in sl)


# ---------- корпус ----------

def round_rect(w: float, t: float, r: float, n: int) -> list[tuple[float, float]]:
    """Скруглённый прямоугольник w × t (радиус r), n точек равномерно по длине, от середины лицевой стороны (+y)
    против часовой."""
    r = min(r, w / 2 - 1e-4, t / 2 - 1e-4)
    hx, hy = w / 2 - r, t / 2 - r
    fine = [(0.0, t / 2)]
    for cx, cy, a0 in ((-hx, hy, 90.0), (-hx, -hy, 180.0), (hx, -hy, 270.0), (hx, hy, 0.0)):
        for k in range(17):
            a = math.radians(a0 + 90.0 * k / 16)
            fine.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    per = [0.0]
    for i in range(1, len(fine) + 1):
        per.append(per[-1] + math.dist(fine[i % len(fine)], fine[i - 1]))
    out, j = [], 0
    for k in range(n):
        sv = per[-1] * k / n
        while per[j + 1] < sv:
            j += 1
        tt = (sv - per[j]) / max(per[j + 1] - per[j], 1e-12)
        a, b = fine[j], fine[(j + 1) % len(fine)]
        out.append((a[0] + (b[0] - a[0]) * tt, a[1] + (b[1] - a[1]) * tt))
    return out


def open_box(m: ak.Mesh, W: float, T: float, Hp: float, r: float, n: int = 72, rb: float = 0.008) -> None:
    """Корпус: стенка WALL снаружи и подкладка внутри, низ скруглён радиусом rb, по верху — окантовка валиком."""
    def ring(w: float, t: float, rr: float, z: float) -> list[Vector]:
        return [Vector((x, y, z)) for x, y in round_rect(w, t, rr, n)]
    rows, zs = [], []
    for k in range(7):                                   # скругление низа
        a = math.pi / 2 * k / 6
        ins = rb * (1 - math.sin(a))
        z = rb * (1 - math.cos(a))
        rows.append(ring(W - 2 * ins, T - 2 * ins, max(r - ins, 0.002), z))
        zs.append(z)
    for k in range(1, 13):
        z = rb + (Hp - rb) * k / 12
        rows.append(ring(W, T, r, z))
    br = WALL / 2 + 0.0008                               # окантовка: валик поверх стенки
    for k in range(1, 7):
        a = math.pi * k / 6
        d = WALL / 2 - math.cos(a) * WALL / 2
        rows.append(ring(W - 2 * d, T - 2 * d, max(r - d, 0.002), Hp + math.sin(a) * br))
    for k in range(0, 12):
        z = Hp - (Hp - WALL) * k / 11
        rows.append(ring(W - 2 * WALL, T - 2 * WALL, max(r - WALL, 0.002), z))
    ids, uvs = [], []
    acc = 0.0
    for j, row in enumerate(rows):
        if j:
            acc += (row[0] - rows[j - 1][0]).length
        per = [0.0]
        for i in range(1, n):
            per.append(per[-1] + (row[i] - row[i - 1]).length)
        ids.append([m.v(p) for p in row])
        uvs.append([(per[i], acc) for i in range(n)])
    m.grid(ids, uvs, closed_u=True)
    for row, flip in ((rows[0], True), (rows[-1], False)):           # дно снаружи и дно полости — веером
        c = sum(row, Vector()) / len(row)
        ci = m.v(c)
        idx = [m.v(p) for p in row]
        for i in range(n):
            f = [idx[i], idx[(i + 1) % n], ci]
            uv = [(row[i].x, row[i].y), (row[(i + 1) % n].x, row[(i + 1) % n].y), (c.x, c.y)]
            m.f(f[::-1] if flip else f, uv[::-1] if flip else uv)


class Plane:
    """Плоская сторона корпуса: лицевая (+y) или задняя (−y); u — x, v — z."""

    def __init__(self, y: float, sign: float):
        self.y, self.s = y, sign

    def normal(self, u: float, v: float) -> Vector:
        return Vector((0.0, self.s, 0.0))

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        return Vector((u, self.y + self.s * off, v))


def rect(x0: float, x1: float, z0: float, z1: float, r: float) -> list[tuple[float, float]]:
    return ak.rounded_poly([(x0, z0), (x1, z0), (x1, z1), (x0, z1)], [r] * 4)


def molle_back(web: ak.Mesh, metal: ak.Mesh, T: float, Hp: float, xs: tuple[float, ...]) -> None:
    """Сзади — вертикальные стропы MOLLE с кнопкой внизу (продеваются в ряды брони)."""
    back = Plane(-T / 2, -1.0)
    for x in xs:
        ak.padded_panel(web, ak.OffsetFrame(back, 0.0011), rect(x - WEB_W / 2, x + WEB_W / 2, 0.006, Hp - 0.006, 0.002),
                        0.0022, bulge=0.0, binding=0.0, step=0.003)
        p = back.point(x, 0.016, 0.0024)
        ak.torus(metal, p, Vector((0, -1, 0)), 0.0042, 0.0015, seg=16, sides=6)


WEB_W = 0.025


# ---------- язычок на липучке ----------

def resample(path: list[Vector], n: int) -> list[Vector]:
    cum = [0.0]
    for a, b in zip(path, path[1:]):
        cum.append(cum[-1] + (b - a).length)
    out, j = [], 0
    for k in range(n + 1):
        s = cum[-1] * k / n
        while j < len(cum) - 2 and cum[j + 1] < s:
            j += 1
        t = (s - cum[j]) / max(cum[j + 1] - cum[j], 1e-12)
        out.append(path[j].lerp(path[j + 1], t))
    return out


def open_path(p0: Vector, T: float, Hp: float, length: float) -> list[Vector]:
    """«Открыт» (магазин выдернули, липучка оторвана): лента от шва у задней стенки падает вперёд через пустое горлышко
    и свисает по лицевой стороне (длина та же, что у застёгнутой; лишнее висит ниже)."""
    yb, yf = p0.y, T / 2 + 0.0035
    path = [p0, Vector((p0.x, yb, Hp + 0.004))]
    for k in range(1, 9):
        t = k / 8
        path.append(Vector((p0.x, yb + (yf - yb) * t, Hp + 0.004 + 0.008 * math.sin(math.pi * t))))
    path.append(Vector((p0.x, yf, Hp - 0.004)))
    cur = sum(((b - a).length for a, b in zip(path, path[1:])), 0.0)
    rest = max(0.01, length - cur)
    for k in range(1, 9):
        path.append(Vector((p0.x, yf + 0.0005 * k, Hp - 0.004 - rest * k / 8)))
    return path


def tab_path(mag: bpy.types.Object | None, T: float, Hp: float, x_end: float, z_end: float,
             length: float | None = None) -> list[Vector]:
    """Путь язычка: изнутри задней стенки вверх по тыльной стороне магазина, через донце, вниз по лицевой стороне
    магазина, через окантовку и по лицевой стенке подсумка вниз до липучки. Без магазина (mag=None) — «Открыт»:
    стоит вверх и заваливается назад (длина length)."""
    y_in = -T / 2 + WALL + 0.0012
    if mag is None:
        return open_path(Vector((0.0, y_in, Hp - 0.006)), T, Hp, length or 0.2)
    pts = [mag.matrix_world @ v.co for v in mag.data.vertices]
    bvh = mag_bvh(mag)
    zt = max(p.z for p in pts)
    crown = [p for p in pts if p.z > zt - 0.012]
    xf = (min(p.x for p in crown) + max(p.x for p in crown)) / 2

    def x_in(x: float, z: float) -> float:
        """x на высоте z внутри магазина (изогнутый уходит вбок): края — лучами вдоль x по середине толщины."""
        lo = bvh.ray_cast(Vector((-1.0, 0.0, z)), Vector((1, 0, 0)), 2.0)[0]
        hi = bvh.ray_cast(Vector((1.0, 0.0, z)), Vector((-1, 0, 0)), 2.0)[0]
        if lo is None or hi is None:
            return x
        return min(max(x, lo.x + 0.012), hi.x - 0.012)

    def side_y(x: float, z: float, back: bool) -> float:
        """Тыльная / лицевая сторона магазина лучом вдоль y (по сетке, а не по редким вершинам)."""
        o, d = (Vector((x, -1.0, z)), Vector((0, 1, 0))) if back else (Vector((x, 1.0, z)), Vector((0, -1, 0)))
        hit = bvh.ray_cast(o, d, 2.0)
        if hit[0] is None:
            sl = [p.y for p in pts if abs(p.z - z) < 0.006]
            return (min(sl) if back else max(sl)) + (-0.0018 if back else 0.0018)
        return hit[0].y + (-0.0018 if back else 0.0018)

    def top_z(y: float) -> float:
        """Верх донца лучом сверху (по нескольким x вокруг середины донца — берётся высший)."""
        zs = []
        for dx in (-0.006, 0.0, 0.006):
            hit = bvh.ray_cast(Vector((xf + dx, y, zt + 0.5)), Vector((0, 0, -1)), 1.0)
            if hit[0] is not None:
                zs.append(hit[0].z)
        return (max(zs) if zs else zt) + 0.0018
    path = [Vector((0.0, y_in, Hp - 0.006))]
    for k in range(1, 9):                                 # вверх по тыльной стороне магазина
        z = Hp + (zt - 0.012 - Hp) * k / 8
        x = x_in(xf * (z - Hp) / max(zt - Hp, 1e-6), z)
        path.append(Vector((x, side_y(x, z, True), z)))
    y0, y1 = path[-1].y, side_y(xf, zt - 0.012, False)
    for k in range(9):                                    # через донце
        y = y0 + (y1 - y0) * k / 8
        path.append(Vector((xf, y, top_z(y))))
    for k in range(1, 9):                                 # вниз по лицевой стороне магазина
        z = zt - 0.012 - (zt - 0.012 - (Hp + 0.004)) * k / 8
        x = x_in(xf * (z - Hp) / max(zt - Hp, 1e-6), z)
        path.append(Vector((x, side_y(x, z, False), z)))
    for _ in range(3):                                    # ход поперёк — плавно
        xs = [q.x for q in path]
        for i in range(1, len(path) - 1):
            path[i].x = (xs[i - 1] + 2 * xs[i] + xs[i + 1]) / 4
    path.append(Vector((0.0, T / 2 + 0.0015, Hp + 0.003)))   # через окантовку
    for k in range(1, 7):                                 # по лицевой стенке вниз до липучки
        z = Hp - (Hp - z_end) * k / 6
        path.append(Vector((x_end * k / 6, T / 2 + 0.0022, z)))
    return path


def path_normals(pts: list[Vector]) -> list[Vector]:
    """Нормаль ленты, лежащей в плоскости y–z: X × касательная (вверх по тыльной стороне — от брони, через донце — вверх,
    вниз по лицевой — наружу); ширина ленты тогда всегда вдоль x."""
    nrm = []
    for i in range(len(pts)):
        tan = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        n = Vector((1.0, 0.0, 0.0)).cross(tan)
        nrm.append(n.normalized() if n.length > 1e-9 else Vector((0, 0, 1)))
    return nrm


def tab_mesh(path: list[Vector], width: float, mag_center: Vector) -> ak.Mesh:
    """Язычок (стропа двойная, 2,8 мм) с липучкой-«крючком» снизу на конце и петлёй-тягой."""
    pts = resample(path, TAB_N)
    nrm = path_normals(pts)
    for _ in range(3):
        nrm = [nrm[0]] + [(nrm[i - 1] + nrm[i] * 2 + nrm[i + 1]).normalized() for i in range(1, len(nrm) - 1)] + [nrm[-1]]
    rib = ak.RibbonFrame(pts, nrm)
    m = ak.Mesh()
    ak.strap(m, rib, width, 0.0028, step=rib.length / TAB_N, taper=0.0)
    # липучка-«крючок» снизу конца: своя лента по последним 4 см
    u0 = rib.length - 0.042
    end = [rib.point(u0 + 0.04 * k / 12, 0.0, 0.0) for k in range(13)]
    rib2 = ak.RibbonFrame(end, [rib.normal(u0 + 0.04 * k / 12, 0.0) for k in range(13)])
    ak.strap(m, rib2, width - 0.004, 0.0012, base_off=-0.0013, step=rib2.length / 12, mat=1)
    # петля-тяга на конце
    p, tan, nn = rib._at(rib.length)
    side = nn.cross(tan).normalized()
    loop = [p + tan * (0.004 + 0.012 * math.sin(math.pi * k / 12)) + nn * (0.002 + 0.006 * math.sin(math.pi * k / 12))
            + side * (0.008 * math.cos(math.pi * k / 12)) for k in range(13)]
    ak.tube(m, loop, 0.0022, sides=6)
    return m


# ---------- подсумки ----------

def materials() -> dict:
    return {
        "cordura": kc.clay("Pouch_Cordura", (0.20, 0.20, 0.17), 0.85),
        "webbing": kc.clay("Pouch_Webbing", (0.12, 0.12, 0.10), 0.8),
        "velcro": kc.clay("Pouch_Velcro", (0.06, 0.06, 0.05), 0.95),
        "metal": kc.clay("Pouch_Metal", (0.30, 0.30, 0.30), 0.35),
    }


def cavity(mags: list[bpy.types.Object], Hp: float) -> tuple[float, float]:
    """Полость по магазинам: ширина (x) и толщина (y) в высоте подсумка + зазор (магазины — по середине)."""
    w = t = 0.0
    for mg in mags:
        x0, x1, y0, y1 = extents(mg, 0.0, Hp)
        w = max(w, 2 * max(abs(x0), abs(x1)))
        t = max(t, 2 * max(abs(y0), abs(y1)))
    return w + 2 * GAP, t + 2 * GAP


def check(mag: bpy.types.Object, Win: float, Tin: float, r_in: float, floor: float, Hp: float) -> float:
    """Наименьший зазор вершин магазина ниже края до стенок полости (меньше нуля — в стенке)."""
    worst = 1.0
    for v in mag.data.vertices:
        p = mag.matrix_world @ v.co
        if p.z > Hp:
            continue
        qx, qy = abs(p.x) - (Win / 2 - r_in), abs(p.y) - (Tin / 2 - r_in)
        outside = math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r_in
        worst = min(worst, -outside, p.z - floor)
    return worst


def build_open_pouch(col, mats, prefix: str, mags: dict, Hp: float, keys: dict) -> dict:
    """Открытый подсумок под магазины mags (имя → объект, первый — основа язычка); keys — имя ключа формы → магазин
    (или None — «Открыт»). Возвращает размеры."""
    first = next(iter(mags.values()))
    Win, Tin = cavity(list(mags.values()), Hp)
    W, T = Win + 2 * WALL, Tin + 2 * WALL
    r = min(0.012, T / 2 - 0.002)
    for mg in mags.values():
        mg.location.z = WALL + 0.0015
        bpy.context.view_layer.update()
    body, web, vel, metal = ak.Mesh(), ak.Mesh(), ak.Mesh(), ak.Mesh()
    open_box(body, W, T, Hp, r)
    front = Plane(T / 2, 1.0)
    # спереди: поперечная стропа внизу и поле липучки-«петли» вверху (на него ложится язычок)
    ak.padded_panel(web, ak.OffsetFrame(front, 0.0011), rect(-W / 2 + r * 0.7, W / 2 - r * 0.7, Hp * 0.12, Hp * 0.12 + WEB_W,
                                                             0.002), 0.0022, bulge=0.0, binding=0.0, step=0.003)
    vz0, vz1 = Hp * 0.12 + WEB_W + 0.008, Hp - 0.010
    vw = min(0.030, W / 2 - r * 0.7)
    ak.padded_panel(vel, ak.OffsetFrame(front, 0.0009), rect(-vw, vw, vz0, vz1, 0.003), 0.0016, bulge=0.0, binding=0.0,
                    step=0.003)
    molle_back(web, metal, T, Hp, (-W / 4, W / 4) if W > 0.06 else (0.0,))
    body.build(f"{prefix}_Body", col, [mats["cordura"]])
    web.build(f"{prefix}_Webbing", col, [mats["webbing"]])
    vel.build(f"{prefix}_Velcro", col, [mats["velcro"]])
    metal.build(f"{prefix}_Snaps", col, [mats["metal"]])
    # язычок: основа — по первому магазину, ключи — по остальным и «Открыт»
    tab_w = min(0.030, W - 0.012)
    z_end = (vz0 + vz1) / 2 - 0.004
    base_path = tab_path(first, T, Hp, 0.0, z_end)
    center = Vector((0.0, 0.0, Hp))
    base = tab_mesh(base_path, tab_w, center)
    length = sum((b - a).length for a, b in zip(base_path, base_path[1:]))
    shapes = {}
    for key, mg in keys.items():
        shapes[key] = tab_mesh(tab_path(mg, T, Hp, 0.0, z_end + (0.012 if mg is not None else 0.0), length), tab_w, center)
    base.build(f"{prefix}_Tab", col, [mats["webbing"], mats["velcro"]], shape_keys=shapes)
    rep = {"W": W, "T": T, "H": Hp}
    for name, mg in mags.items():
        rep[f"зазор {name}"] = check(mg, Win, Tin, max(r - WALL, 0.002), WALL, Hp)
    return rep


def build_big_pouch(col, mats, prefix: str, drum: bpy.types.Object) -> dict:
    """Большой подсумок (два места): короб по барабану и широкий клапан через горловину вниз на липучку спереди."""
    pts = [drum.matrix_world @ v.co for v in drum.data.vertices]
    zt = max(p.z for p in pts)
    neck = [p for p in pts if p.z > zt - 0.035]
    body_top = max(p.z for p in pts if not (abs(p.x) < 0.03 and p.z > zt - 0.035)) if neck else zt
    Hp = body_top * 0.80
    Win, Tin = cavity([drum], Hp)
    W, T = Win + 2 * WALL, Tin + 2 * WALL
    r = 0.018
    drum.location.z = WALL + 0.0015
    bpy.context.view_layer.update()
    pts = [drum.matrix_world @ v.co for v in drum.data.vertices]
    zt = max(p.z for p in pts)
    body, web, vel, metal = ak.Mesh(), ak.Mesh(), ak.Mesh(), ak.Mesh()
    open_box(body, W, T, Hp, r, n=96)
    front = Plane(T / 2, 1.0)
    ak.padded_panel(web, ak.OffsetFrame(front, 0.0011), rect(-W / 2 + r * 0.7, W / 2 - r * 0.7, 0.020, 0.020 + WEB_W, 0.002),
                    0.0022, bulge=0.0, binding=0.0, step=0.003)
    vz0, vz1 = 0.060, Hp - 0.012
    ak.padded_panel(vel, ak.OffsetFrame(front, 0.0009), rect(-0.045, 0.045, vz0, vz1, 0.003), 0.0016, bulge=0.0,
                    binding=0.0, step=0.003)
    molle_back(web, metal, T, Hp, (-W / 3, 0.0, W / 3))
    body.build(f"{prefix}_Body", col, [mats["cordura"]])
    web.build(f"{prefix}_Webbing", col, [mats["webbing"]])
    vel.build(f"{prefix}_Velcro", col, [mats["velcro"]])
    metal.build(f"{prefix}_Snaps", col, [mats["metal"]])

    # клапан: полоса шириной корпуса по профилю барабана в плоскости x = 0 (через горловину)
    dbvh = mag_bvh(drum)

    def prof_z(y: float) -> float:
        zs = []
        for k in range(13):
            x = -W / 2 + 0.01 + (W - 0.02) * k / 12
            hit = dbvh.ray_cast(Vector((x, y, 2.0)), Vector((0, 0, -1)), 3.0)
            if hit[0] is not None:
                zs.append(hit[0].z)
        return max(zs) if zs else Hp
    y_back, y_front = -T / 2 + 0.002, T / 2
    path = [Vector((0.0, y_back, Hp - 0.008)), Vector((0.0, y_back, Hp + 0.01))]
    for k in range(25):
        y = -Tin / 2 + Tin * k / 24
        path.append(Vector((0.0, y, max(prof_z(y), Hp) + 0.006)))
    path.append(Vector((0.0, y_front + 0.002, Hp + 0.01)))
    for k in range(1, 7):
        path.append(Vector((0.0, y_front + 0.0035, Hp - (Hp - (vz0 + vz1) / 2) * k / 6)))

    L0 = 0.30                                              # условная длина развёртки клапана

    class NormRib:
        """Лента клапана с длиной развёртки L0 при любой настоящей длине пути (ключи формы — одна топология)."""

        def __init__(self, rib: ak.RibbonFrame):
            self.rib, self.k = rib, rib.length / L0

        def normal(self, u: float, v: float) -> Vector:
            return self.rib.normal(u * self.k, v)

        def point(self, u: float, v: float, off: float = 0.0) -> Vector:
            return self.rib.point(u * self.k, v, off)

    def flap(path_pts: list[Vector]) -> ak.Mesh:
        p2 = resample(path_pts, 60)
        nrm = path_normals(p2)
        for _ in range(4):
            nrm = [nrm[0]] + [(nrm[i - 1] + nrm[i] * 2 + nrm[i + 1]).normalized() for i in range(1, len(nrm) - 1)] + [nrm[-1]]
        rib = ak.RibbonFrame(p2, nrm)
        m = ak.Mesh()
        ak.padded_panel(m, ak.OffsetFrame(NormRib(rib), 0.002),
                        ak.rounded_poly([(0.0, -W / 2 + 0.004), (L0, -W / 2 + 0.012), (L0, W / 2 - 0.012), (0.0, W / 2 - 0.004)],
                                        [0.002, 0.012, 0.012, 0.002]), 0.004, bulge=0.0, binding=0.006, step=0.006)
        L = rib.length
        p, tan, nn = rib._at(L)
        side = nn.cross(tan).normalized()
        loop = [p + tan * (0.004 + 0.014 * math.sin(math.pi * k / 12)) + nn * (0.004 + 0.006 * math.sin(math.pi * k / 12))
                + side * (0.012 * math.cos(math.pi * k / 12)) for k in range(13)]
        ak.tube(m, loop, 0.0025, sides=6)
        return m
    base = flap(path)
    L = sum((b - a).length for a, b in zip(path, path[1:]))
    base.build(f"{prefix}_Flap", col, [mats["cordura"]], shape_keys={"Открыт": flap(open_path(path[0], T, Hp, L))})
    return {"W": W, "T": T, "H": Hp, "зазор барабан": check(drum, Win, Tin, r - WALL, WALL, Hp)}


# ---------- сцена ----------

def stage(col: bpy.types.Collection, x: float) -> None:
    for o in col.all_objects:
        o.location.x += x


def main() -> None:
    args = kc.args_after_dashes()
    kc.wipe_scene()
    mats = materials()
    mag30 = import_mag("veras54/veras54.gltf", ("Magazine",), "Mag_VERAS54_30")
    mag45 = import_mag("veras54_mags/veras54_mag45_world.gltf", None, "Mag_VERAS54_45")
    drum = import_mag("veras54_mags/veras54_drum60_world.gltf", None, "Mag_VERAS54_Drum60")
    pm = import_mag("pm/pm_mag.gltf", None, "Mag_PM_8")
    glock = import_mag("glock17/glock17.glb", ("MagBody", "MagFloorplate", "MagFollower", "MagSpring"), "Mag_Glock_17")
    for mg, up in ((mag30, True), (mag45, True), (pm, True), (glock, True)):
        align_mag(mg, up)
    align_mag(drum, False, turn=False)                       # двойной барабан — поперёк подсумка
    report = {}
    # автоматный: основа — ВЕРАС на 30
    rc = kc.collection("08_Pouch_Rifle")
    report["автоматный"] = build_open_pouch(rc, mats, "Pouch_Rifle", {"30": mag30, "45": mag45}, 0.120,
                                            {"Магазин 45": mag45, "Открыт": None})
    # пистолетный: основа — Глок на 17
    pc = kc.collection("08_Pouch_Pistol")
    report["пистолетный"] = build_open_pouch(pc, mats, "Pouch_Pistol", {"Глок 17": glock, "ПМ": pm}, 0.068,
                                             {"ПМ": pm, "Открыт": None})
    bc = kc.collection("08_Pouch_Big")
    report["большой"] = build_big_pouch(bc, mats, "Pouch_Big", drum)
    for name, rep in report.items():
        kc.log(f"  подсумок {name}: " + ", ".join(f"{k} {v * 1000:.1f} мм" for k, v in rep.items()))
    # магазины — в свои коллекции у подсумков
    for mg, col in ((mag30, rc), (mag45, rc), (glock, pc), (pm, pc), (drum, bc)):
        for c in list(mg.users_collection):
            c.objects.unlink(mg)
        kc.collection(f"{col.name} · {mg.name}", col).objects.link(mg)
    for o in bpy.data.objects:                              # ключи формы — выключены (новые создаются со значением 1)
        if o.type == "MESH" and o.data.shape_keys:
            for kb in o.data.shape_keys.key_blocks[1:]:
                kb.value = 0.0
    stage(pc, 0.20)
    stage(bc, 0.42)
    OUT.mkdir(parents=True, exist_ok=True)
    kc.save(OUT / "pouches.blend")
    if "render" in args:
        render()
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        deliver(Path(dest))


README = (
    "Подсумки для магазинов — ФОРМА {ver} на согласование (нейтральный материал). Одинарные, открытые сверху, магазин\n"
    "держит язычок на липучке с петлёй-тягой (не резинка): автоматный (одно место на броне), пистолетный (половина\n"
    "места), большой (два места, клапан на липучке). Магазины — игровые модели: ВЕРАС-54 на 30 и на 45, барабан на 60,\n"
    "Глок на 17, ПМ. Вместимость проверена расчётом: зазор до стенок не меньше 3 мм, до дна 1,5 мм.\n"
    "Длинный магазин и ПМ — в своих коллекциях внутри 08_Pouch_* (включить глаз). Язычок под них — ключ формы:\n"
    "выделить *_Tab → Object Data → Shape Keys: «Магазин 45» / «ПМ» = 1; «Открыт» = 1 — магазин выдернули, язычок\n"
    "оторван и свисает (так же клапан большого — *_Flap). Смотреть в Rendered (Cycles).\n"
    "Скрипт: tools/npc_kit/pouches.py.\n")


def deliver(folder: Path, filename: str | None = None) -> None:
    """Файл на просмотр: основные магазины видны, длинный и ПМ скрыты, студия, камера спереди, всё упаковано."""
    from mathutils import Quaternion
    set_state("", None, None)
    for name in MAGS:
        bpy.data.objects[name].hide_render = False
    vl = bpy.context.view_layer.layer_collection
    for parent in ("08_Pouch_Rifle", "08_Pouch_Pistol", "08_Pouch_Big"):
        for lc in vl.children[parent].children:
            lc.hide_viewport = lc.name.endswith(("Mag_VERAS54_45", "Mag_PM_8"))
            lc.collection.hide_render = lc.hide_viewport
    kc.studio()
    kc.gpu_cycles(64)
    scene = bpy.context.scene
    scene.cycles.preview_samples = 24
    scene.cycles.use_preview_denoising = True
    scene.camera = kc.camera("Camera_Front", (0.30, 0.95, 0.30), (0.21, 0.0, 0.08), 50)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                sp = area.spaces.active
                sp.shading.type = "RENDERED"
                sp.overlay.show_floor = False
                r3 = sp.region_3d
                r3.view_location = (0.21, 0.0, 0.08)
                r3.view_distance = 0.75
                r3.view_rotation = Quaternion((0.17, 0.12, 0.56, 0.80))
    text = bpy.data.texts.new("00_ПРОЧТИ")
    text.use_fake_user = True
    text.write(README.format(ver=VERSION))
    bpy.ops.file.pack_all()
    folder.mkdir(parents=True, exist_ok=True)
    name = filename or f"Подсумки_{VERSION}_форма.blend"
    kc.save(folder / name)
    kc.log("DELIVERED", folder / name)


SHOTS = (  # (подсумок, x на сцене, видимый магазин, ключ формы, подпись)
    ("Pouch_Rifle", 0.0, "Mag_VERAS54_30", None, "rifle_30"),
    ("Pouch_Rifle", 0.0, "Mag_VERAS54_45", "Магазин 45", "rifle_45"),
    ("Pouch_Rifle", 0.0, None, "Открыт", "rifle_open"),
    ("Pouch_Pistol", 0.20, "Mag_Glock_17", None, "pistol_glock"),
    ("Pouch_Pistol", 0.20, "Mag_PM_8", "ПМ", "pistol_pm"),
    ("Pouch_Big", 0.42, "Mag_VERAS54_Drum60", None, "big_drum"),
    ("Pouch_Big", 0.42, None, "Открыт", "big_open"),
)
MAGS = ("Mag_VERAS54_30", "Mag_VERAS54_45", "Mag_Glock_17", "Mag_PM_8", "Mag_VERAS54_Drum60")


def set_state(prefix: str, mag: str | None, key: str | None) -> None:
    for name in MAGS:
        bpy.data.objects[name].hide_render = name != mag
    for o in bpy.data.objects:
        if o.data is not None and getattr(o.data, "shape_keys", None) and o.name.startswith(prefix):
            for kb in o.data.shape_keys.key_blocks[1:]:
                kb.value = 1.0 if kb.name == key else 0.0


def render() -> None:
    import numpy as np
    kc.studio()
    kc.gpu_cycles(96)
    out = kc.WORK / "previews"
    paths = []
    for prefix, x0, mag, key, tag in SHOTS:
        set_state(prefix, mag, key)
        tgt = (x0, 0.0, 0.10 if prefix != "Pouch_Pistol" else 0.07)
        cam = kc.camera("C_p_" + tag, (x0 + 0.26, 0.42, tgt[2] + 0.17), tgt, 60)
        p = out / f"pouch_{tag}.png"
        kc.render(cam, p, (560, 560), 96)
        paths.append(p)
    set_state("", None, None)
    imgs = [bpy.data.images.load(str(p)) for p in paths]
    w, h = imgs[0].size
    cols, rows = 4, 2
    grid = np.ones((h * rows, w * cols, 4), np.float32)
    for k, im in enumerate(imgs):
        r, c = divmod(k, cols)
        px = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(px)
        grid[(rows - 1 - r) * h:(rows - r) * h, c * w:(c + 1) * w] = px.reshape(h, w, 4)
    res = bpy.data.images.new("pouches_grid", w * cols, h * rows, alpha=False)
    res.pixels.foreach_set(grid.ravel())
    sset = bpy.context.scene.render.image_settings
    sset.file_format = "JPEG"
    sset.quality = 90
    sset.color_mode = "RGB"
    res.save_render(str(out / f"pouches_{VERSION}.jpg"))


if __name__ == "__main__":
    main()
