"""NPC: кожаная куртка-бомбер (как у мародёра на референсе) — оболочкой вокруг тела и симуляцией.

Оболочка: тело, раздутое на запас и пересобранное ровной сеткой (без пальцев, щелей и подмышечных
провалов); ниже груди висит «коробкой» с груди и лопаток (drape_torso), рукава шире. Разрезы — швы
настоящего кроя: низ (над резинкой), край рукава, горловина, бок и низ рукава — плоскостью y, центр
переда — x = 0 (застёжка), проймы — по полю (вшивной двухшовный рукав), кокетка спинки. 9 деталей,
каждая разворачивается в лекало с припуском. Пояс и манжеты — трикотажные полосы по настоящим
обхватам (бёдра, запястье), мягче кожи; стягиваются плавно и собирают кожу. Под курткой для
столкновений — «свитер» (сглаженный торс): иначе кожа ложится на пресс и лопатки.
Самостолкновений в симуляции нет (у швов детали расталкивали друг друга — ткань мялась «фольгой»).
Капюшон (HOOD) пока выключен — вернётся отдельной деталью.
Опыты по одному фактору — apply_variant (voxel=, bend=, nocuts, nobox, noease, tri, grow=),
probe frames=N — только мера смятости и габарит.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/jacket.py [-- render]
→ _asset_src/npc_kit/jacket/jacket_sim.blend (читает pants/pants_sim.blend)
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import garment as gm  # noqa: E402
import kit_common as kc  # noqa: E402
import shell as sh  # noqa: E402

OUT = kc.WORK / "jacket"
VOXEL = 0.0095
MARGIN = 0.020          # запас оболочки от тела (v03: было 0,024 — куртка выглядела толстой; 0,015 — проступала грудь)
Z_HEM = 0.925           # низ кожи; ниже — резинка
RIB_H = 0.065
CUFF_H = 0.07
SLEEVE_END = 0.075      # кожа рукава кончается за столько до запястья, дальше манжета
HOOD = False            # капюшон — пока отдельной сменной деталью на будущее; сейчас воротник-стойка
HOOD_FOLD = 150.0       # на сколько градусов откинут капюшон (0 — надет)
COLLAR_H = 0.05         # высота трикотажного воротника
LEATHER_BENDING = 80.0  # куртечная кожа жёсткая на изгиб: меньше мелкой ряби, складки крупнее
BAND_EASE = 1.02        # пояс: обхват бёдер (с брюками) + 2 % (ещё ≈4 см уходят на толщину резинки и зазор
                        # столкновений) — держится на бёдрах, кожа над ним напуском; впритык — съезжает на талию
CUFF_EASE = 1.25        # манжета: обхват руки у запястья + 25 %
GROW = 0.0              # припуск ростом ткани в симуляции вместо припуска лекал (0 — припуск в лекалах)
SPLIT_Y = -0.03         # плоскость бока и низа рукава: руки в A-позе лежат почти в ней
EASE = (1.04, 1.08)     # припуск лекал: по ширине, по длине (длина — на напуск над резинкой); v03: ширина 1,06 → 1,04
SLEEVE_EASE = (1.03, 1.07)  # рукав: длинный, собирается у манжеты (v03: уже)
CHEST_TOP = 1.40        # до этой высоты торс висит «коробкой» с груди и лопаток
SLEEVE_ROOM = 0.006     # рукав свободнее оболочки на столько (v03: было 0,012 — рукава раздувало)
Z_YOKE = 1.385          # шов кокетки на спине
# Пройма (левая; правая — зеркально): плоскость через плечевую точку, наклон 12° — низ ближе к телу;
# под рукой — горизонталь Z_PIT (на 2–3 см ниже перемычки подмышки оболочки).
ARMHOLE = (Vector((0.205, 0.0, 1.50)), Vector((0.977, 0.0, -0.215)).normalized())
Z_PIT = 1.305


def arm_points(rig: bpy.types.Object, side: str) -> tuple[Vector, Vector, Vector]:
    b = rig.data.bones
    return (b["upperarm_" + side].head_local.copy(), b["lowerarm_" + side].head_local.copy(),
            b["hand_" + side].head_local.copy())


def build_shell(body: bpy.types.Object, pants: bpy.types.Object, rig: bpy.types.Object,
                col: bpy.types.Collection, box: bool = True) -> bpy.types.Object:
    shell = sh.evaluated_copy(body, "Jacket_Shell", col)
    bm = bmesh.new()
    bm.from_mesh(shell.data)
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * MARGIN
    bm.to_mesh(shell.data)
    bm.free()
    # Пересборка ровной сеткой: раздутые пальцы, подмышки и пах сливаются — нужен только торс и руки.
    sh.voxel_remesh(shell, VOXEL)
    sh.delete_faces(shell, lambda c: c.z < Z_HEM - 0.06 or c.z > 1.72)
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        sho, elb, wr = arm_points(rig, side)
        d = (elb - wr).normalized()          # от кисти к локтю
        cut = wr + d * SLEEVE_END
        sh.clip(shell, lambda c, s=sgn, cut=cut, d=d: (c - cut).dot(-d) if c.x * s > 0.30 else -1.0)
    sh.keep_largest(shell)
    sh.smooth(shell, 28, 0.5, only=lambda c: c.z > Z_HEM - 0.05)
    if box:
        drape_torso(shell, body, pants, rig, col)
        widen_sleeves(shell, rig)
    sh.smooth(shell, 4, 0.4, only=lambda c: c.z > Z_HEM - 0.05)
    sh.offset_from(shell, body, MARGIN * 0.75)
    sh.offset_from(shell, pants, 0.010, only=lambda c: c.z < 1.12)
    sh.smooth(shell, 3, 0.4, only=lambda c: c.z < 1.15)
    # Низ над резинкой.
    sh.clip(shell, lambda c: Z_HEM - c.z)

    def above_neck(c: Vector) -> bool:
        """Горловина: сзади на основании шеи, спереди ниже на 8,5 см."""
        dx, dy = c.x, c.y + 0.055
        r = math.hypot(dx, dy)
        if r > 0.125 or c.z < 1.40:
            return False
        front = max(0.0, -dy / max(r, 1e-6))
        return c.z > 1.556 - 0.085 * front ** 1.5
    sh.delete_faces(shell, above_neck)
    sh.keep_largest(shell)
    sh.smooth_boundary(shell, 24, only=lambda c: c.z > 1.40)   # горловина ровной линией, без «пилы» по клеткам
    sh.fill_small_holes(shell, 30)
    # Бок и низ рукава; центр переда.
    sh.level_cut(shell, lambda c: c.y - SPLIT_Y)
    sh.level_cut(shell, lambda c: c.x)
    for poly in shell.data.polygons:
        poly.use_smooth = True
    return shell


def ray_radius(poly: list[tuple[float, float]], c: tuple[float, float], ang: float) -> float:
    """Расстояние от c до замкнутого контура по лучу под углом ang (радианы); наибольшее пересечение."""
    dx, dy = math.cos(ang), math.sin(ang)
    best = 0.0
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        ex, ey = q[0] - p[0], q[1] - p[1]
        den = dx * ey - dy * ex
        if abs(den) < 1e-12:
            continue
        t = ((p[0] - c[0]) * ey - (p[1] - c[1]) * ex) / den
        u = ((p[0] - c[0]) * dy - (p[1] - c[1]) * dx) / den
        if t > 0 and -1e-9 <= u <= 1 + 1e-9:
            best = max(best, t)
    return best


def drape_torso(shell: bpy.types.Object, body: bpy.types.Object, pants: bpy.types.Object,
                rig: bpy.types.Object, col: bpy.types.Collection, margin: float = MARGIN + 0.004,
                taper: float = 0.16, fade: tuple[float, float] | None = None) -> None:
    """Кожа не облегает живот и поясницу: ниже груди куртка висит с груди и лопаток прямо вниз.
    По каждому направлению из оси торса радиус оболочки — не меньше наибольшего радиуса сечений
    тела (с брюками) выше этой точки до CHEST_TOP, минус taper на метр (v03: 16 см на метр — к поясу уже,
    без «бочки»). Сечения — выпуклые, без
    рук: пресс, грудные мышцы, лопатки и позвоночник не читаются. fade (z0, z1) — ниже z0 не трогать,
    к z1 — в полную силу (так «свитер» под курткой отпускает бёдра, на которых держится пояс)."""
    union = sh.evaluated_copy(body, "Body_Pants_Union", col)
    bm = bmesh.new()
    bm.from_mesh(union.data)
    pm = sh.evaluated_copy(pants, "Pants_Tmp", col)
    bm.from_mesh(pm.data)
    bm.to_mesh(union.data)
    bm.free()
    bpy.data.objects.remove(pm)
    arms = [arm_points(rig, s) for s in ("l", "r")]

    def d_arm(p: Vector) -> float:
        return min(min(sh.seg_dist(p, a, b), sh.seg_dist(p, b, c)) for a, b, c in arms)
    z0 = Z_HEM - 0.07
    n_z = int(round((CHEST_TOP - z0) / 0.01)) + 1
    zs = [z0 + 0.01 * i for i in range(n_z)]
    na = 144
    rings = []
    for z in zs:
        pts = [(x, y) for x, y in gm.body_section_points(union, z, lambda x, y: True)
               if d_arm(Vector((x, y, z))) > 0.075 and abs(x) < 0.26]
        rings.append(gm.Ring(pts, margin, n=180))
    bpy.data.objects.remove(union)
    cy = sum(r.c[1] for r in rings) / len(rings)
    centre = (0.0, cy)
    rad = [[ray_radius(r.pts, centre, 2 * math.pi * k / na) for k in range(na)] for r in rings]
    # Сверху вниз: не уже, чем выше (почти отвесно — 4 см сужения на метр).
    drape = [row[:] for row in rad]
    for i in range(n_z - 2, -1, -1):
        for k in range(na):
            drape[i][k] = max(rad[i][k], drape[i + 1][k] - taper * 0.01)
    for _ in range(3):
        drape = [[(drape[max(i - 1, 0)][k] + 2 * drape[i][k] + drape[min(i + 1, n_z - 1)][k]) / 4 for k in range(na)]
                 for i in range(n_z)]
        drape = [[(row[(k - 1) % na] + 2 * row[k] + row[(k + 1) % na]) / 4 for k in range(na)] for row in drape]
    moved = 0
    for v in shell.data.vertices:
        p = v.co
        da = d_arm(p)
        if p.z > CHEST_TOP + 0.03 or da < 0.08:
            continue
        ang = math.atan2(p.y - cy, p.x) % (2 * math.pi)
        f = max(0.0, min(n_z - 1.001, (p.z - z0) / 0.01))
        i = int(f)
        t = f - i
        a = ang / (2 * math.pi) * na
        k = int(a) % na
        u = a - int(a)

        def at(ii: int) -> float:
            return drape[ii][k] * (1 - u) + drape[ii][(k + 1) % na] * u
        target = at(i) * (1 - t) + at(min(i + 1, n_z - 1)) * t
        r = math.hypot(p.x, p.y - cy)
        if r < target:
            w = gm.smoothstep((CHEST_TOP + 0.03 - p.z) / 0.06) * gm.smoothstep((da - 0.08) / 0.04)
            if fade:
                w *= gm.smoothstep((p.z - fade[0]) / (fade[1] - fade[0]))
            s = 1 + (target / max(r, 1e-6) - 1) * w
            v.co.x = p.x * s
            v.co.y = cy + (p.y - cy) * s
            moved += 1
    shell.data.update()
    kc.log("  коробка: сдвинуто", moved, "вершин")


def widen_sleeves(shell: bpy.types.Object, rig: bpy.types.Object) -> None:
    """Рукав бомбера просторный: дальше плеча оболочка отходит от оси руки ещё на SLEEVE_ROOM."""
    arms = [arm_points(rig, side) for side in ("l", "r")]
    for v in shell.data.vertices:
        p = v.co
        best = None
        for sho, elb, wr in arms:
            total = (elb - sho).length + (wr - elb).length
            for a, b, s0 in ((sho, elb, 0.0), (elb, wr, (elb - sho).length)):
                ab = b - a
                t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
                q = a + ab * t
                d = (p - q).length
                if best is None or d < best[0]:
                    best = (d, q, (s0 + ab.length * t) / total)
        d, q, s = best
        if d > 0.09 or s < 0.05:          # дальше — уже бок торса под рукой
            continue
        w = gm.smoothstep((s - 0.08) / 0.18)
        v.co = p + (p - q).normalized() * SLEEVE_ROOM * w
    shell.data.update()


def armhole_field(rig: bpy.types.Object, side: str):
    """Поле проймы: > 0 — рукав. У руки — расстояние до плоскости проймы; у торса (дальше 8,5–10,5 см
    от оси руки) ещё и не ниже Z_PIT — так ноль поля обходит руку замкнутой петлёй: по груди и
    лопатке вниз, под мышкой поперёк бока."""
    sgn = 1.0 if side == "l" else -1.0
    co = Vector((ARMHOLE[0].x * sgn, ARMHOLE[0].y, ARMHOLE[0].z))
    no = Vector((ARMHOLE[1].x * sgn, 0.0, ARMHOLE[1].z))
    sho, elb, wr = arm_points(rig, side)

    def g(p: Vector) -> float:
        pd = (p - co).dot(no)
        radial = min(sh.seg_dist(p, sho, elb), sh.seg_dist(p, elb, wr))
        w = gm.smoothstep((radial - 0.085) / 0.02)
        a, b, k = pd, p.z - Z_PIT, 0.018       # мягкий минимум: низ проймы скруглён, а не углом
        m = min(a, b) - k * math.log(1.0 + math.exp(-abs(a - b) / k))
        return pd * (1 - w) + m * w
    return g


def cut_seams(shell: bpy.types.Object, rig: bpy.types.Object) -> dict[str, list[float]]:
    """Швы кроя разрезом оболочки: проймы (рукав — отдельная деталь, вшивной) и кокетка спинки.
    Возвращает поля проймы по вершинам (у вершин разреза — ровно 0)."""
    fields = {side: armhole_field(rig, side) for side in ("l", "r")}
    for side in ("l", "r"):
        sh.level_cut(shell, fields[side])
    # Кокетка — только по спинке (на переде и рукавах лишняя линия вершин дала бы острые блики):
    # разрез плоскостью по граням спинки, линия кончается на швах проймы и бока.
    sh.bisect(shell, Vector((0, 0, Z_YOKE)), Vector((0, 0, 1)),
              region=lambda c: c.y > SPLIT_Y and all(f(c) < 0 for f in fields.values()))
    # Рёбра короче 1,5 мм (там, где разрезы прошли у самых вершин и пересекаются) — схлопнуть.
    bm = bmesh.new()
    bm.from_mesh(shell.data)
    bmesh.ops.dissolve_degenerate(bm, dist=0.0015, edges=bm.edges[:])
    bm.to_mesh(shell.data)
    bm.free()
    shell.data.update()
    # Поле проймы по вершинам заново: на линии разреза (|поле| < 2 мм) — ровно 0.
    vals = {}
    for side in ("l", "r"):
        out = []
        for v in shell.data.vertices:
            g = fields[side](v.co)
            out.append(0.0 if abs(g) < 0.002 else g)
        vals[side] = out
    kc.log("  швы: проймы и кокетка, вершин", len(shell.data.vertices), "рёбер короче 2 мм:", sh.short_edges(shell))
    return vals


def neckline_z(c: Vector) -> float:
    """Высота горловины над точкой: сзади на основании шеи, спереди ниже на 8,5 см."""
    dx, dy = c.x, c.y + 0.055
    r = math.hypot(dx, dy)
    front = max(0.0, -dy / max(r, 1e-6))
    return 1.556 - 0.085 * front ** 1.5


def build_hood(body: bpy.types.Object, col: bpy.types.Collection) -> bpy.types.Object:
    """Капюшон «надетым»: голова с запасом 3 см, ровная сетка, низ — по горловине, вырез для лица."""
    hood = sh.evaluated_copy(body, "Hood_Shell", col)
    sh.delete_faces(hood, lambda c: c.z < 1.44 or abs(c.x) > 0.17)
    bm = bmesh.new()
    bm.from_mesh(hood.data)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * 0.030
    bm.to_mesh(hood.data)
    bm.free()
    sh.voxel_remesh(hood, VOXEL)
    sh.keep_largest(hood)
    sh.smooth(hood, 14, 0.5)
    # Капюшону нужен объём над макушкой и сзади: чуть вытягиваем верх назад.
    for v in hood.data.vertices:
        t = gm.smoothstep((v.co.z - 1.62) / 0.2)
        v.co.y += 0.025 * t * gm.smoothstep((v.co.y + 0.02) / 0.1)
        v.co.z += 0.012 * t
    hood.data.update()

    def face_open(c: Vector) -> bool:
        return c.y < -0.02 and (c.x / 0.105) ** 2 + ((c.z - 1.645) / 0.19) ** 2 < 1.0
    sh.delete_faces(hood, lambda c: c.z < neckline_z(c) + 0.004 or face_open(c))
    sh.keep_largest(hood)
    sh.smooth_boundary(hood, 8)
    sh.bisect(hood, Vector((0, 0, 0)), Vector((1, 0, 0)))
    for poly in hood.data.polygons:
        poly.use_smooth = True
    return hood


def fold_down(verts) -> None:
    """Откинуть капюшон на спину: низ (у горловины) остаётся, верх поворачивается вокруг оси X
    через основание шеи сзади назад и вниз на HOOD_FOLD — тем сильнее, чем дальше от горловины.
    Делается после развёртки: лекало — от надетого капюшона."""
    pivot = Vector((0.0, 0.045, 1.556))
    for v in verts:
        p = v.co
        h = max(0.0, p.z - neckline_z(p))
        t = gm.smoothstep(h / 0.16)
        phi = -math.radians(HOOD_FOLD) * t
        d = p - pivot
        y = d.y * math.cos(phi) - d.z * math.sin(phi)
        z = d.y * math.sin(phi) + d.z * math.cos(phi)
        # Откинутый капюшон шире ложится по плечам и отходит от спины на пару сантиметров.
        v.co = Vector((p.x * (1.0 + 0.15 * t), pivot.y + y + 0.02 * t, pivot.z + z))


def neck_loop_ordered(me: bpy.types.Mesh, loop: list[int]) -> list[int]:
    """Горловина начиная от центра переда (там шов воротника совпадёт с застёжкой)."""
    k = min(range(len(loop)), key=lambda i: (me.vertices[loop[i]].co.x ** 2 + 4 * max(0.0, me.vertices[loop[i]].co.y + 0.2) ** 2
                                             - me.vertices[loop[i]].co.y * 0.0))
    front = min(range(len(loop)), key=lambda i: me.vertices[loop[i]].co.y)
    return loop[front:] + loop[:front]


def loop_info(shell: bpy.types.Object) -> dict[str, list[int]]:
    """Края оболочки: низ, горловина, левый и правый край рукава."""
    me = shell.data
    out = {}
    for loop in sh.boundary_loops(shell):
        pts = [me.vertices[i].co for i in loop]
        c = sum(pts, Vector()) / len(pts)
        if abs(c.z - Z_HEM) < 0.02 and abs(c.x) < 0.1:
            out["hem"] = loop
        elif c.z > 1.40 and abs(c.x) < 0.1:
            out["neck"] = loop
        elif c.x > 0.3:
            out["cuff_l"] = loop
        elif c.x < -0.3:
            out["cuff_r"] = loop
    return out


def clear_of(verts: list[Vector], objs: list[bpy.types.Object], gap: float) -> int:
    """Отодвинуть точки наружу от поверхностей objs не ближе gap (по нормали ближайшей точки)."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    trees = [BVHTree.FromObject(o, dg) for o in objs]
    moved = 0
    for v in verts:
        for t in trees:
            loc, nrm, _, dist = t.find_nearest(v)
            if loc is None or dist > 0.08:
                continue
            d = (v - loc).dot(nrm)
            if d < gap:
                v[:] = loc + nrm * gap
                moved += 1
    return moved


def hull_perimeter(pts: list[tuple[float, float]]) -> float:
    h = gm._hull(pts)
    return sum(((h[i][0] - h[i - 1][0]) ** 2 + (h[i][1] - h[i - 1][1]) ** 2) ** 0.5 for i in range(len(h)))


def rib_shrink(obj: bpy.types.Object, body: bpy.types.Object, pants: bpy.types.Object,
               rig: bpy.types.Object, grow: float = 0.0) -> float:
    """Резинки по настоящим обхватам: длина покоя полосы = её контур (развёртка), нужная — обхват
    бёдер / руки с запасом. Усадка каждой полосы — вес её вершин в группе rib (доля от наибольшей).
    Возвращает наибольшую усадку."""
    me = obj.data
    groups = {g.name: g.index for g in obj.vertex_groups}
    uv = me.uv_layers["UV_Pattern"].data

    def strip_len(name: str) -> float:
        gi = groups["piece_" + name]
        ids = {v.index for v in me.vertices if any(g.group == gi for g in v.groups)}
        xs = [uv[li].uv.x for li, loop in enumerate(me.loops) if loop.vertex_index in ids]
        return max(xs) - min(xs)
    dg = bpy.context.evaluated_depsgraph_get()
    z_band = Z_HEM - RIB_H * 0.55
    pts = []
    for o in (body, pants):
        ev = o.evaluated_get(dg)
        m = ev.to_mesh()
        for e in m.edges:
            a, b = m.vertices[e.vertices[0]].co, m.vertices[e.vertices[1]].co
            if (a.z - z_band) * (b.z - z_band) < 0 and abs(a.x) < 0.30:
                q = a.lerp(b, (z_band - a.z) / (b.z - a.z))
                pts.append((q.x, q.y))
        ev.to_mesh_clear()
    need = {"band": hull_perimeter(pts) * BAND_EASE, "collar": strip_len("collar")}
    for side in ("l", "r"):
        sho, elb, wr = arm_points(rig, side)
        d = (wr - elb).normalized()
        c = wr - d * (SLEEVE_END - CUFF_H * 0.5)
        radii = [((v.co - c) - d * (v.co - c).dot(d)).length for v in body.data.vertices
                 if abs((v.co - c).dot(d)) < 0.01 and (v.co - c).length < 0.08]
        r = sum(radii) / max(len(radii), 1)
        need["cuff_" + side] = 2 * 3.14159265 * r * CUFF_EASE
    shrink = {k: max(0.0, 1.0 - need[k] / strip_len(k)) for k in need}
    s_max = max(max(shrink.values()), 0.01)
    rib = obj.vertex_groups["rib"]
    for k, sk in shrink.items():
        gi = groups["piece_" + k]
        # Вес под формулу Blender: длина = 1 − min + (min − max)·вес, min = −grow (кожа растёт).
        w = (sk + grow) / (s_max + grow)
        rib.add([v.index for v in me.vertices if any(g.group == gi for g in v.groups)], w, "REPLACE")
    kc.log("  резинки: " + ", ".join(f"{k} {strip_len(k):.2f}→{need[k]:.2f} м (усадка {shrink[k] * 100:.0f} %)"
                                   for k in need))
    return s_max


def apply_variant(args: list[str]) -> None:
    """Опыты: voxel=, bend=, nocuts, nobox, noease, tri, grow=, nogrow — по одному фактору против обычной сборки."""
    global VOXEL, LEATHER_BENDING, EASE, SLEEVE_EASE, GROW
    for a in args:
        if a.startswith("grow="):
            GROW = float(a[5:])
        elif a == "nogrow":
            GROW = 0.0
        if a.startswith("voxel="):
            VOXEL = float(a[6:])
        elif a.startswith("bend="):
            LEATHER_BENDING = float(a[5:])
        elif a == "noease":
            EASE = SLEEVE_EASE = (1.0, 1.0)


def crumple_probe(obj: bpy.types.Object, sew: list[tuple[int, int]]) -> None:
    """Насколько вещь смята и укорочена после короткой симуляции (до сварки швов)."""
    import wear
    dg = bpy.context.evaluated_depsgraph_get()
    m = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), depsgraph=dg)
    adj = wear.adjacency(m)
    f = wear.fold(m, adj, iterations=4, scale=1.0)
    rough = sum(abs(x) for x in f) / len(f) * 1000
    zs = [v.co.z for v in m.vertices]
    xs = [v.co.x for v in m.vertices]
    kc.log(f"PROBE смятость {rough:.2f} мм, z {min(zs):.3f}..{max(zs):.3f}, x {min(xs):.3f}..{max(xs):.3f}")


def main() -> None:
    args = kc.args_after_dashes()
    apply_variant(args)
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / "pants" / "pants_sim.blend"))
    body = bpy.data.objects["NPC_Body"]
    rig = bpy.data.objects["NPC_Skeleton"]
    pants = bpy.data.objects["Pants"]
    work = kc.collection("96_Jacket_Work")
    t0 = time.time()
    shell = build_shell(body, pants, rig, work, box="nobox" not in args)
    if "nocuts" in args:
        seam_vals = {side: [0.0] * len(shell.data.vertices) for side in ("l", "r")}
    else:
        seam_vals = cut_seams(shell, rig)
    if "tri" in args:
        bm = bmesh.new()
        bm.from_mesh(shell.data)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.to_mesh(shell.data)
        bm.free()
    loops = loop_info(shell)
    for loop in sh.boundary_loops(shell):
        pts = [shell.data.vertices[i].co for i in loop]
        kc.log("  контур", len(loop), "x", round(min(p.x for p in pts), 2), round(max(p.x for p in pts), 2),
               "z", round(min(p.z for p in pts), 2), round(max(p.z for p in pts), 2),
               "скачок", round(max((pts[i] - pts[i - 1]).length for i in range(len(pts))), 3))
    kc.log("JACKET_SHELL", len(shell.data.vertices), "verts", {k: len(v) for k, v in loops.items()},
           f"{time.time() - t0:.0f} с")

    # Капюшон — отдельный кусок в той же оболочке (свои вершины), низ пришьём к горловине.
    n_shell_v = len(shell.data.vertices)
    n_shell_f = len(shell.data.polygons)
    if HOOD:
        hood = build_hood(body, work)
        bm = bmesh.new()
        bm.from_mesh(shell.data)
        bm.from_mesh(hood.data)
        bm.to_mesh(shell.data)
        bm.free()
        shell.data.update()
    me = shell.data
    neck = loops["neck"]
    hood_sew = []
    hood_bottom = []
    for loop in sh.boundary_loops(shell):
        if loop[0] < n_shell_v:
            continue
        for i in loop:
            c = me.vertices[i].co
            if abs(c.z - neckline_z(c)) < 0.02:
                hood_bottom.append(i)
    # Пары по углу вокруг шеи (не по расстоянию): по порядку, без повторов — иначе несколько точек
    # капюшона садятся на одну точку горловины и низ стягивается в ком.
    def neck_angle(i: int) -> float:
        c = me.vertices[i].co
        return math.atan2(c.x, c.y + 0.055)           # 0 — сзади, ±π — спереди
    neck_sorted = sorted(neck, key=neck_angle)
    neck_ang = [neck_angle(k) for k in neck_sorted]
    used: set[int] = set()
    for i in sorted(hood_bottom, key=neck_angle):
        a = neck_angle(i)
        j = min(range(len(neck_sorted)), key=lambda k: abs(neck_ang[k] - a) + (1.0 if neck_sorted[k] in used else 0.0))
        used.add(neck_sorted[j])
        hood_sew.append((i, neck_sorted[j]))
    kc.log("JACKET_HOOD", len(me.vertices) - n_shell_v, "verts", len(hood_bottom), "на горловине")

    pieces: dict[str, sh.ShellPiece] = {}
    for poly in me.polygons:
        c = Vector(poly.center)
        fb = "b" if c.y > SPLIT_Y else "f"
        sleeve = next((side for side in ("l", "r") if poly.index < n_shell_f
                       and sum(seam_vals[side][i] for i in poly.vertices) > 0), None)
        if poly.index >= n_shell_f:
            name = "hood_l" if c.x > 0 else "hood_r"
        elif sleeve:
            name = f"sleeve_{sleeve}_{fb}"           # рукав двухшовный: верх и низ — по плоскости y
        elif fb == "b" and c.z > Z_YOKE and "nocuts" not in args:
            name = "yoke"
        elif fb == "b":
            name = "back_l" if c.x > 0 else "back_r"
        else:
            name = "front_l" if c.x > 0 else "front_r"
        pieces.setdefault(name, sh.ShellPiece(name, "Jacket_Leather")).faces.append(list(poly.vertices))
    for pc in pieces.values():
        pc.material = "Jacket_Leather"
        ease = (1.03, 1.03) if pc.name.startswith("hood") else SLEEVE_EASE if pc.name.startswith("sleeve") else EASE
        if GROW:
            ease = (1.0, 1.0)                    # припуск даст рост ткани в симуляции
        sh.flatten(shell, pc, ease, work)
        xs = [p[0] for p in pc.flat.values()]
        ys = [p[1] for p in pc.flat.values()]
        kc.log("JACKET_FLAT", pc.name, len(pc.faces), "граней", f"{max(xs) - min(xs):.2f} x {max(ys) - min(ys):.2f} м")

    fold_down([v for v in me.vertices if v.index >= n_shell_v])
    me.update()
    extras = []
    if not HOOD:
        # Воротник-стойка: трикотажная полоса вверх от горловины, чуть к шее.
        loop = neck_loop_ordered(me, neck)
        pts = [me.vertices[i].co.copy() for i in loop]
        strip = sh.strip_along(pts, loop, lambda i, p: Vector((0, -0.25, 1)).normalized() if p.y < -0.08 else Vector((0, 0, 1)),
                               COLLAR_H, 5, outward=lambda p: -Vector((p.x, p.y + 0.055, 0)).normalized() * 0.6)
        strip.update(name="collar", material="Jacket_Rib", groups=["rib"])
        extras.append(strip)
    # Пояс-резинка: вниз от края, чуть наружу.
    # Пояс начинается и кончается у застёжки (как у настоящей куртки), а не где попало.
    hem = neck_loop_ordered(me, loops["hem"])
    pts = [me.vertices[i].co.copy() for i in hem]
    strip = sh.strip_along(pts, hem, lambda i, p: Vector((0, 0, -1)), RIB_H, 6,
                           outward=lambda p: Vector((p.x, p.y + 0.03, 0)).normalized())
    strip.update(name="band", material="Jacket_Rib", groups=["rib"])
    # Пояс свисает отвесно, а бёдра ниже края кожи шире: без этого резинка с первого кадра стоит
    # внутри брюк, столкновение выталкивает её рывком — низ подскакивает, куртка мнётся и садится.
    clear_of(strip["verts"], [pants, body], 0.006)
    extras.append(strip)
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        loop = loops["cuff_" + side]
        sho, elb, wr = arm_points(rig, side)
        d = (wr - elb).normalized()
        pts = [me.vertices[i].co.copy() for i in loop]
        axis_c = wr - d * SLEEVE_END
        strip = sh.strip_along(pts, loop, lambda i, p, d=d: d, CUFF_H, 6,
                               outward=lambda p, c=axis_c, d=d: ((p - c) - d * (p - c).dot(d)).normalized())
        strip.update(name="cuff_" + side, material="Jacket_Rib", groups=["rib"])
        extras.append(strip)
    col = kc.collection("03_Jacket")
    kc.clay("Jacket_Leather", (0.075, 0.045, 0.03), 0.42)
    kc.clay("Jacket_Rib", (0.035, 0.032, 0.03), 0.9)
    obj, sew = sh.assemble("Jacket", shell, list(pieces.values()), extras, col, VOXEL, extra_sew=hood_sew)
    kc.log("JACKET_MESH", len(obj.data.vertices), "verts", len(obj.data.polygons), "faces", len(sew), "sew")
    OUT.mkdir(parents=True, exist_ok=True)

    sim_col = bpy.data.collections.get("98_Sim_Colliders") or kc.collection("98_Sim_Colliders")
    sim_col.hide_viewport = False
    for o in list(sim_col.objects):
        bpy.data.objects.remove(o)
    # Под курткой — «свитер»: торс для столкновений теми же выпуклыми сечениями, что и коробка куртки,
    # на 8 мм от тела и почти отвесно с груди. Иначе кожа под тяжестью ложится на пресс, лопатки и
    # позвоночник, а у настоящей куртки их не видно. К бёдрам «свитер» сходит на нет — там держится пояс.
    bc = gm.make_collider(body, "Body_Collider", sim_col, offset=0.0015, thickness=0.003, friction=15.0)
    drape_torso(bc, body, pants, rig, work, margin=0.008, taper=0.25, fade=(0.98, 1.08))
    gm.make_collider(pants, "Pants_Collider", sim_col, offset=0.001, thickness=0.003, friction=15.0)
    work.hide_viewport = True
    work.hide_render = True
    if "place_only" in args:
        # Проверка кроя: каждая деталь своим цветом.
        palette = [(0.55, 0.2, 0.15), (0.2, 0.45, 0.2), (0.2, 0.3, 0.6), (0.6, 0.5, 0.15), (0.45, 0.2, 0.5),
                   (0.15, 0.5, 0.5), (0.6, 0.35, 0.2), (0.3, 0.3, 0.3), (0.5, 0.5, 0.5), (0.25, 0.15, 0.1)]
        me = obj.data
        piece_of = {}
        for k, vg in enumerate(g for g in obj.vertex_groups if g.name.startswith("piece_")):
            mat = kc.clay("Check_" + vg.name, palette[k % len(palette)], 0.6)
            me.materials.append(mat)
            for v in me.vertices:
                if any(gg.group == vg.index for gg in v.groups):
                    piece_of[v.index] = len(me.materials) - 1
        for poly in me.polygons:
            poly.material_index = piece_of.get(poly.vertices[0], poly.material_index)
        kc.save(OUT / "jacket_placed.blend")
        cams = kc.view_cameras(1.8)
        for view in ["front", "side", "three_quarter", "back"]:
            kc.render(cams[view], OUT / f"placed_{view}.png", (700, 900), 16)
        return
    frames = int(next((a.split("=")[1] for a in args if a.startswith("frames=")), 90))
    # Капюшон мягче (тонкая кожа на подкладке): общая жёсткость на изгиб — его, у остальной
    # кожи — по группе "stiff" (наибольшая).
    leather = gm.FABRICS["leather"]
    stiff = obj.vertex_groups.new(name="stiff")
    hood_ids = set()
    for nm in ("piece_hood_l", "piece_hood_r"):
        if nm not in obj.vertex_groups:
            continue
        gi = obj.vertex_groups[nm].index
        hood_ids |= {v.index for v in obj.data.vertices if any(g.group == gi for g in v.groups)}
    stiff.add([v.index for v in obj.data.vertices if v.index not in hood_ids], 1.0, "REPLACE")
    # Трикотаж мягче кожи на растяжение: основная ткань — рубчик, кожа — по группе "leather".
    knit = gm.FABRICS["knit_rib"]
    soft = gm.Fabric(leather.mass, knit.tension, knit.compression, knit.shear, 4.0, quality=leather.quality)
    rib_gi = obj.vertex_groups["rib"].index
    obj.vertex_groups.new(name="leather").add(
        [v.index for v in obj.data.vertices if not any(g.group == rib_gi for g in v.groups)], 1.0, "REPLACE")
    s_max = 0.0 if "noshrink" in args else rib_shrink(obj, body, pants, rig, GROW)
    gm.simulate(obj, soft, frames=frames, sew_frames=20, shrink_group="rib", shrink=s_max, shrink_frames=30, grow=GROW,
                struct_group="leather", struct_fabric=leather,
                # Без самостолкновений: у швов две детали лежат вплотную, отталкиваются, а сшивание тянет
                # их назад — ткань дрожит, мнётся «фольгой» и садится (низ и рукава поднимались). Складки,
                # проткнувшие друг друга, расправляет досадка после сварки (там самостолкновения есть).
                self_collision="selfcol" in args,
                stiff_group="stiff", stiff_bending=LEATHER_BENDING,
                collide_collection=sim_col, debug=tuple(args), log=kc.log)
    if "probe" in args:
        crumple_probe(obj, sew)
        return
    gm.freeze(obj, sew, kc.log)
    # Швы сварены — досадка со столкновениями по всей вещи: складки, проткнувшие друг друга у швов
    # (там самостолкновения были выключены), расправляются.
    gm.relax(obj, gm.Fabric(leather.mass, leather.tension, leather.compression, leather.shear, 15.0,
                            quality=leather.quality), 14, collide_collection=sim_col, log=kc.log)
    gm.taubin(obj, 20)
    kc.log("JACKET_SIM", round(time.time() - t0, 1), "s")
    sim_col.hide_viewport = True
    sim_col.hide_render = True
    kc.save(OUT / "jacket_sim.blend")
    if "render" in args:
        cams = kc.view_cameras(1.8)
        for view in ["front", "back", "side", "three_quarter"]:
            kc.render(cams[view], OUT / f"jacket_{view}.png", (900, 1200), 48)
    snap_col = bpy.data.collections.get("97_Snapshots")
    if snap_col:
        obj.hide_render = True
        cam = kc.camera("Cam_Snap", (0.0, -3.2, 1.25), (0.0, 0.0, 1.2), 60)
        for snap in sorted(snap_col.objects, key=lambda o: o.name):
            snap.hide_render = False
            kc.render(cam, OUT / "snaps" / f"{snap.name}.png", (600, 400), 12)
            snap.hide_render = True


if __name__ == "__main__":
    main()
