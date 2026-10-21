"""NPC: берцы на шнуровке (по образцу владельца со Sketchfab), брюки заправляются внутрь.

Колодка — стопа и голень тела с запасом: у стопы 6 мм, к верху голенища 2,2 см (место для
заправленных брюк); носок объёмный. Поверх — накладки: носок, задник, резиновый рант по низу
(соты — картой нормалей). Верх голенища — мягкий кант. Горловина шнуровки — от подъёма стопы
вверх по переду голенища, под ней сплошной язык (сетка — текстурой). Внизу пять пар D-колец
на язычках, выше — четыре пары крючков; шнурок крест-накрест, две обмотки вокруг верха и бант.
Подошва толстая: каблук ступенью, носок приподнят, поперечные грунтозацепы — геометрией.
Подошва ниже голой стопы (каблук на HEEL): в игре весь набор поднять на HEEL.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/boots.py [-- render]
→ _asset_src/npc_kit/boots/boots.blend (читает body/body_M.blend)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
import mathutils.geometry as mgeo
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import garment as gm  # noqa: E402
import kit_common as kc  # noqa: E402
import shell as sh  # noqa: E402

OUT = kc.WORK / "boots"
BOOT_TOP = 0.235      # верх голенища над полом стопы
FOOT_GAP = 0.006      # верх от стопы
SHAFT_GAP = 0.020     # голенище от голени (брюки внутри)
FOREFOOT = 0.028      # подошва под носком
HEEL = 0.038          # под пяткой
LACE_R = 0.0019


class FootFrame:
    """Доля длины стопы t: 0 — носок, 1 — пятка."""

    def __init__(self, obj: bpy.types.Object, axis_x: float):
        ys = [v.co.y for v in obj.data.vertices]
        self.y_toe, self.y_heel = min(ys), max(ys)
        self.axis_x = axis_x

    def t(self, p: Vector) -> float:
        return (p.y - self.y_toe) / (self.y_heel - self.y_toe)


def boot_last(body: bpy.types.Object, col: bpy.types.Collection, axis_x: float) -> bpy.types.Object:
    last = sh.evaluated_copy(body, "Boot_Last_L", col)
    last.data.materials.clear()
    sh.delete_faces(last, lambda c: c.z > BOOT_TOP + 0.05 or c.x < 0.06)
    bm = bmesh.new()
    bm.from_mesh(last.data)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.normal_update()
    for v in bm.verts:
        off = FOOT_GAP + (SHAFT_GAP - FOOT_GAP) * gm.smoothstep((v.co.z - 0.085) / 0.13)
        v.co += v.normal * off
    bm.to_mesh(last.data)
    bm.free()
    sh.voxel_remesh(last, 0.004)
    sh.keep_largest(last)
    sh.smooth(last, 30, 0.6)
    fr = FootFrame(last, axis_x)
    # Носок: объёмный «стакан» — выше, шире, округлый, на 1 см длиннее стопы.
    for v in last.data.vertices:
        p = v.co
        t = fr.t(p)
        fore = gm.smoothstep((0.45 - t) / 0.30)
        p.x = axis_x + (p.x - axis_x) * (1.0 + 0.06 * fore)
        if p.z > 0.02:
            p.z += 0.009 * fore * gm.smoothstep((p.z - 0.02) / 0.03)
        p.y -= 0.010 * gm.smoothstep((0.22 - t) / 0.22)
        p.z = max(p.z, 0.004)
    last.data.update()
    sh.smooth(last, 10, 0.5)
    sh.bisect(last, Vector((0, 0, 0.010)), Vector((0, 0, -1)), clear_outer=True)
    sh.bisect(last, Vector((0, 0, BOOT_TOP)), Vector((0, 0, 1)), clear_outer=True)
    return last


def build_sole(last: bpy.types.Object, col: bpy.types.Collection) -> bpy.types.Object:
    """Подошва: профиль борта по контуру низа колодки; каблук ступенью, носок приподнят;
    низ — сетка с поперечными грунтозацепами (кроме выемки подъёма)."""
    pts = gm.body_section_points(last, 0.013, lambda x, y: True)
    ring = gm.Ring(pts, 0.0, n=200)
    cx, cy = ring.c
    base = [Vector((x, y, 0.0)) for x, y in ring.pts]
    ys = [p.y for p in base]
    y_toe, y_heel = min(ys), max(ys)
    L = y_heel - y_toe

    def bottom_z(x: float, y: float) -> float:
        t = (y - y_toe) / L
        heel_w = gm.smoothstep((t - 0.70) / 0.025)
        arch = gm.smoothstep((t - 0.50) / 0.08) * (1 - heel_w)
        toe = gm.smoothstep((0.18 - t) / 0.18)
        return -(FOREFOOT + (HEEL - FOREFOOT) * heel_w) + 0.009 * arch + 0.013 * toe

    def lugs(x: float, y: float) -> float:
        """Поперечные зацепы: канавки глубиной 4 мм через 13 мм, в выемке подъёма — гладко."""
        t = (y - y_toe) / L
        if 0.52 < t < 0.70:
            return 0.0
        ph = ((y - y_toe) / 0.013) % 1.0
        groove = gm.smoothstep((0.32 - abs(ph - 0.5)) / 0.08)
        return 0.004 * (1.0 - groove)

    profile = [(0.00, -0.001), (0.10, 0.004), (0.25, 0.0062), (0.45, 0.0070), (0.62, 0.0068),
               (0.66, 0.0058), (0.70, 0.0068), (0.86, 0.0066), (0.95, 0.0050), (1.00, 0.0034)]
    top_z = 0.021
    rings = []
    for f, off in profile:
        r = []
        for p in base:
            d = Vector((p.x - cx, p.y - cy, 0))
            n = d.normalized() if d.length > 1e-6 else Vector((0, -1, 0))
            q = Vector((p.x, p.y, 0)) + n * off
            bz = bottom_z(p.x, p.y) + (lugs(p.x, p.y) - 0.004) * (f > 0.99)
            r.append(Vector((q.x, q.y, top_z + (bz - top_z) * f)))
        rings.append(r)
    n = len(base)
    verts = [v for r in rings for v in r]
    faces = []
    for k in range(len(rings) - 1):
        for i in range(n):
            a, b = k * n + i, k * n + (i + 1) % n
            faces.append([a, b, b + n, a + n])
    # Низ — треугольная сетка 4 мм внутри контура, зацепы смещением по z.
    outline = [(v.x, v.y) for v in rings[-1]]
    interior = []
    xs, ys2 = [p[0] for p in outline], [p[1] for p in outline]
    hstep = 0.004
    yy = min(ys2) + hstep
    row = 0
    while yy < max(ys2):
        xx = min(xs) + (hstep / 2 if row % 2 else 0)
        while xx < max(xs):
            if gm._inside((xx, yy), outline) and gm._dist_to_poly((xx, yy), outline) > 0.003:
                interior.append((xx, yy))
            xx += hstep
        yy += hstep * 0.87
        row += 1
    pts2 = [Vector(p) for p in outline + interior]
    out = mgeo.delaunay_2d_cdt(pts2, [], [list(range(n))], 1, 1e-7, True)
    _, _, ofaces, orig, _, _ = out
    remap = {k: o[0] for k, o in enumerate(orig) if o}
    base_i = len(verts)
    last_ring = (len(rings) - 1) * n
    for (x, y) in interior:
        verts.append(Vector((x, y, bottom_z(x, y) + lugs(x, y) - 0.004)))
    for f in ofaces:
        idx = []
        for k in f:
            o = remap[k]
            idx.append(last_ring + o if o < n else base_i + (o - n))
        faces.append(idx[::-1])
    # Верх подошвы закрыт (под колодкой не виден).
    c_top = sum(rings[0], Vector()) / n
    verts.append(c_top)
    ti = len(verts) - 1
    for i in range(n):
        faces.append([i, (i + 1) % n, ti])
    mesh = bpy.data.meshes.new("Boot_Sole_L")
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    mesh.update()
    obj = bpy.data.objects.new("Boot_Sole_L", mesh)
    col.objects.link(obj)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj


class Throat:
    """Линия шнуровки: от подъёма стопы по верху стопы к переду щиколотки и вверх по голенищу."""

    def __init__(self, last: bpy.types.Object, fr: FootFrame):
        dg = bpy.context.evaluated_depsgraph_get()
        self.bvh = BVHTree.FromObject(last, dg)
        L = fr.y_heel - fr.y_toe
        pts = []
        for t in [0.40, 0.46, 0.52, 0.58]:
            y = fr.y_toe + L * t
            pts.append(self.bvh.ray_cast(Vector((fr.axis_x, y, 0.5)), Vector((0, 0, -1)))[0])
        for z in [0.10, 0.13, 0.16, 0.19, BOOT_TOP - 0.004]:
            pts.append(self.bvh.ray_cast(Vector((fr.axis_x - 0.012 * (z - 0.10) / 0.13, -0.5, z)), Vector((0, 1, 0)))[0])
        self.pts = pts
        cum = [0.0]
        for i in range(len(pts) - 1):
            cum.append(cum[-1] + (pts[i + 1] - pts[i]).length)
        self.cum = cum
        self.samples = [self.at(k / 200)[0] for k in range(201)]

    def at(self, s: float) -> tuple[Vector, Vector]:
        d = max(0.0, min(1.0, s)) * self.cum[-1]
        for i in range(len(self.pts) - 1):
            if self.cum[i + 1] >= d:
                t = (d - self.cum[i]) / max(self.cum[i + 1] - self.cum[i], 1e-9)
                a, b = self.pts[i], self.pts[i + 1]
                return a.lerp(b, t), (b - a).normalized()
        return self.pts[-1], (self.pts[-1] - self.pts[-2]).normalized()

    def width(self, s: float) -> float:
        return 0.007 + 0.013 * gm.smoothstep(s / 0.5)

    def nearest_s(self, p: Vector) -> tuple[float, float]:
        best, bk = 1e9, 0
        for k, q in enumerate(self.samples):
            d = (p - q).length_squared
            if d < best:
                best, bk = d, k
        return bk / 200, math.sqrt(best)


def tube(points: list[Vector], radius: float, name: str, col: bpy.types.Collection, closed: bool = False,
         flat: float = 1.0) -> bpy.types.Object:
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 2
    cu.resolution_u = 6
    sp = cu.splines.new("NURBS")
    sp.points.add(len(points) - 1)
    for p, q in zip(sp.points, points):
        p.co = (q.x, q.y, q.z, 1.0)
    sp.order_u = min(3, len(points))
    sp.use_endpoint_u = not closed
    sp.use_cyclic_u = closed
    obj = bpy.data.objects.new(name, cu)
    col.objects.link(obj)
    if flat != 1.0:
        obj.scale = (1, 1, 1)
    return obj


def thicken(obj: bpy.types.Object, thickness: float, offset: float = -1.0) -> None:
    mod = obj.modifiers.new("Thickness", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = offset
    mod.use_rim = True
    mod.use_even_offset = True
    with bpy.context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_apply(modifier=mod.name)


def overlay(src: bpy.types.Object, name: str, keep, lift: float, thickness: float,
            col: bpy.types.Collection, smooth_edge: int = 12) -> bpy.types.Object:
    """Накладка поверх верха: участок колодки по условию keep, приподнятый и с толщиной."""
    o = sh.evaluated_copy(src, name, col)
    o.data.materials.clear()
    sh.delete_faces(o, lambda c: not keep(c))
    sh.keep_largest(o)
    sh.smooth_boundary(o, smooth_edge)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * lift
    bm.to_mesh(o.data)
    bm.free()
    thicken(o, thickness, offset=1.0)
    return o


def ring_on_surface(bvh: BVHTree, z: float, center: Vector, lift: float, n: int = 48, tilt: float = 0.0) -> list[Vector]:
    """Кольцо вокруг голенища на высоте z (лучи от оси наружу и обратно на поверхность)."""
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        d = Vector((math.cos(a), math.sin(a), 0))
        zz = z + tilt * math.sin(a)
        origin = Vector((center.x, center.y, zz)) + d * 0.3
        hit = bvh.ray_cast(origin, -d)
        if hit[0] is not None:
            pts.append(hit[0] + hit[1] * lift)
    return pts


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / "body" / "body_M.blend"))
    body = bpy.data.objects["NPC_Body"]
    rig = bpy.data.objects["NPC_Skeleton"]
    col = kc.collection("04_Boots")
    work = kc.collection("96_Boot_Work")
    axis_x = rig.data.bones["foot_l"].head_local.x
    last = boot_last(body, work, axis_x)
    fr = FootFrame(last, axis_x)
    # Мягкий кант: верхние 2,5 см голенища чуть пухлее.
    bm = bmesh.new()
    bm.from_mesh(last.data)
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * 0.0032 * gm.smoothstep((v.co.z - (BOOT_TOP - 0.028)) / 0.012)
    bm.to_mesh(last.data)
    bm.free()
    full = sh.evaluated_copy(last, "Boot_Full_L", work)
    sole = build_sole(last, col)
    throat = Throat(full, fr)
    surf = throat.bvh

    def in_throat(c: Vector) -> bool:
        s, d = throat.nearest_s(c)
        return 0.0 < s < 1.0 and d < throat.width(s) and c.z > 0.03
    sh.delete_faces(last, in_throat)
    sh.keep_largest(last)
    sh.smooth_boundary(last, 4, only=lambda c: c.z < BOOT_TOP - 0.003)

    def tongue_keep(c: Vector) -> bool:
        s, d = throat.nearest_s(c)
        return -0.02 < s < 1.02 and d < throat.width(min(max(s, 0), 1)) + 0.012 and c.z > 0.03
    tongue = sh.evaluated_copy(full, "Boot_Tongue_L", col)
    sh.delete_faces(tongue, lambda c: not tongue_keep(c))
    sh.keep_largest(tongue)
    bm = bmesh.new()
    bm.from_mesh(tongue.data)
    bm.normal_update()
    for v in bm.verts:
        v.co -= v.normal * 0.0035
        v.co.z += 0.007 * gm.smoothstep((v.co.z - (BOOT_TOP - 0.03)) / 0.03)
    bm.to_mesh(tongue.data)
    bm.free()
    thicken(tongue, 0.003)
    upper = last
    upper.name = "Boot_Upper_L"
    kc.move_to(upper, col)
    thicken(upper, 0.0028)

    # Накладки: носок, задник, резиновый рант.
    def toe_cap(c: Vector) -> bool:
        t = fr.t(c)
        edge = 0.20 + 0.05 * (abs(c.x - axis_x) / 0.05) ** 2
        return t < edge and c.z < 0.075
    def heel_counter(c: Vector) -> bool:
        t = fr.t(c)
        top = 0.095 - 0.045 * gm.smoothstep((0.88 - t) / 0.12)
        return t > 0.70 and c.z < top
    def rand(c: Vector) -> bool:
        t = fr.t(c)
        h = 0.021 + 0.007 * gm.smoothstep((0.25 - t) / 0.25)
        return c.z < h
    caps = [overlay(full, "Boot_ToeCap_L", toe_cap, 0.0008, 0.0014, col),
            overlay(full, "Boot_Heel_L", heel_counter, 0.0008, 0.0014, col),
            overlay(full, "Boot_Rand_L", rand, 0.0024, 0.0018, col)]

    # Фурнитура: внизу D-кольца на язычках, выше крючки.
    hardware, holes = [], []
    stops = [0.05, 0.14, 0.23, 0.32, 0.41, 0.55, 0.68, 0.81, 0.94]
    for k, s in enumerate(stops):
        p, tan = throat.at(s)
        hit = surf.find_nearest(p)
        nrm = hit[1] if hit[0] is not None else Vector((0, -1, 0))
        side = tan.cross(nrm).normalized()
        w = throat.width(s) + 0.007
        for sgn in (-1, 1):
            c = p + side * sgn * w
            hit = surf.find_nearest(c)
            c, nrm_c = (hit[0], hit[1]) if hit[0] is not None else (c, nrm)
            out_dir = -side * sgn                       # к горловине
            if k < 5:
                # Язычок-держатель и D-кольцо, торчащее к горловине.
                tab = [c - out_dir * 0.006 + nrm_c * 0.0012, c + nrm_c * 0.0016, c + out_dir * 0.004 + nrm_c * 0.0018]
                hardware.append(("tab", tube(tab, 0.0028, "Boot_Tab", col)))
                ring_c = c + out_dir * 0.006 + nrm_c * 0.003
                t1, t2 = tan, (out_dir * 0.6 + nrm_c * 0.8).normalized()
                ring_pts = [ring_c + t1 * math.cos(a) * 0.0045 + t2 * math.sin(a) * 0.0032 for a in
                            [2 * math.pi * j / 14 for j in range(14)]]
                hardware.append(("metal", tube(ring_pts, 0.0010, "Boot_DRing", col, closed=True)))
                holes.append((ring_c + t2 * 0.0025, nrm_c, sgn, k))
            else:
                hook = [c, c + nrm_c * 0.0045, c + nrm_c * 0.0065 + tan * 0.004,
                        c + nrm_c * 0.0045 + tan * 0.0075 + out_dir * 0.002]
                hardware.append(("metal", tube(hook, 0.0013, "Boot_Hook", col)))
                rivet = [c - tan * 0.0025 + nrm_c * 0.0008, c + nrm_c * 0.0012, c + tan * 0.0025 + nrm_c * 0.0008]
                hardware.append(("metal", tube(rivet, 0.0022, "Boot_Rivet", col)))
                holes.append((c + nrm_c * 0.005 + tan * 0.0045, nrm_c, sgn, k))

    def hole(k: int, sgn: int):
        return next(h for h in holes if h[3] == k and h[2] == sgn)

    def span(a, b, lift: float = 0.0045) -> list[Vector]:
        mid = (a[0] + b[0]) / 2 + (a[1] + b[1]).normalized() * lift
        return [a[0], mid, b[0]]
    laces = []
    # Низ — поперечина, дальше две нити крест-накрест.
    laces.append(tube(span(hole(0, -1), hole(0, 1)), LACE_R, "Boot_Lace", col))
    for start in (-1, 1):
        path = []
        sgn = start
        for k in range(len(stops) - 1):
            seg = span(hole(k, sgn), hole(k + 1, -sgn))
            path += seg if not path else seg[1:]
            sgn = -sgn
        laces.append(tube(path, LACE_R, "Boot_Lace", col))
    # Две обмотки вокруг верха голенища и бант спереди.
    axis_top = Vector((axis_x - 0.012, -0.03, BOOT_TOP))
    for z, tilt in ((BOOT_TOP - 0.020, 0.003), (BOOT_TOP - 0.031, -0.002)):
        pts = ring_on_surface(surf, z, axis_top, 0.0022, tilt=tilt)
        if len(pts) > 8:
            laces.append(tube(pts, LACE_R, "Boot_Lace_Wrap", col, closed=True))
    a, b = hole(len(stops) - 1, -1), hole(len(stops) - 1, 1)
    knot = (a[0] + b[0]) / 2 + (a[1] + b[1]).normalized() * 0.007
    side = (b[0] - a[0]).normalized()
    out = (a[1] + b[1]).normalized()
    down = Vector((0, 0, -1))
    for sgn in (-1, 1):
        laces.append(tube([knot, knot + side * sgn * 0.013 + out * 0.006 + down * 0.003,
                           knot + side * sgn * 0.024 + out * 0.004 + down * 0.014,
                           knot + side * sgn * 0.009 + out * 0.006 + down * 0.011, knot], LACE_R, "Boot_Lace_Bow", col))
        laces.append(tube([knot, knot + side * sgn * 0.005 + out * 0.008 + down * 0.012,
                           knot + side * sgn * 0.010 + out * 0.006 + down * 0.045,
                           knot + side * sgn * 0.012 + out * 0.005 + down * 0.070], LACE_R, "Boot_Lace_End", col))
    laces.append(tube([knot - side * 0.0045, knot, knot + side * 0.0045], LACE_R * 1.7, "Boot_Lace_Knot", col))

    mats = {}
    for mat_name, color, rough in [("Boot_Leather", (0.09, 0.055, 0.035), 0.55), ("Boot_Sole", (0.025, 0.025, 0.025), 0.8),
                                   ("Boot_Rubber", (0.03, 0.03, 0.03), 0.7), ("Boot_Lace", (0.07, 0.05, 0.035), 0.9),
                                   ("Boot_Metal", (0.10, 0.10, 0.105), 0.35), ("Boot_Mesh", (0.06, 0.045, 0.035), 0.85)]:
        mats[mat_name] = kc.clay(mat_name, color, rough)

    def assign(o: bpy.types.Object, m: str) -> None:
        o.data.materials.clear()
        o.data.materials.append(mats[m])
    assign(upper, "Boot_Leather")
    assign(sole, "Boot_Sole")
    assign(tongue, "Boot_Mesh")
    assign(caps[0], "Boot_Leather")
    assign(caps[1], "Boot_Leather")
    assign(caps[2], "Boot_Rubber")
    curves = []
    for kind, o in hardware:
        assign(o, "Boot_Leather" if kind == "tab" else "Boot_Metal")
        curves.append(o)
    for o in laces:
        assign(o, "Boot_Lace")
        curves.append(o)
    for o in curves:
        kc.make_active(o)
        bpy.ops.object.convert(target="MESH")
    parts = [upper, sole, tongue, *caps, *curves]
    for p in parts:
        for poly in p.data.polygons:
            poly.use_smooth = True
    kc.make_active(upper)
    for o in parts:
        o.select_set(True)
    bpy.ops.object.join()
    boot_l = bpy.context.view_layer.objects.active
    boot_l.name = "Boots_L"
    boot_r = boot_l.copy()
    boot_r.data = boot_l.data.copy()
    col.objects.link(boot_r)
    boot_r.name = "Boots_R"
    boot_r.data.transform(Matrix.Scale(-1, 4, Vector((1, 0, 0))))
    bm = bmesh.new()
    bm.from_mesh(boot_r.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(boot_r.data)
    bm.free()
    # Препятствие для ткани: только наружная поверхность берца (без внутренней стенки голенища) —
    # заправленная штанина внутри его не чувствует, а над краем ложится напуском.
    shape_col = kc.collection("04_Boots_Collider")
    outer_l = sh.evaluated_copy(full, "Boots_L_Outer", shape_col)
    outer_r = sh.evaluated_copy(full, "Boots_R_Outer", shape_col)
    outer_r.data.transform(Matrix.Scale(-1, 4, Vector((1, 0, 0))))
    bm = bmesh.new()
    bm.from_mesh(outer_r.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(outer_r.data)
    bm.free()
    shape_col.hide_render = True
    for o in list(work.objects):
        bpy.data.objects.remove(o)
    kc.log("BOOTS", len(boot_l.data.vertices), "verts per boot")
    OUT.mkdir(parents=True, exist_ok=True)
    kc.save(OUT / "boots.blend")
    if "render" in args:
        kc.studio()
        body.hide_render = "nobody" in args
        cams = {
            "boot_34": kc.camera("Cam_Boot34", (0.75, -0.65, 0.40), (0.19, -0.06, 0.10), 70),
            "boot_side": kc.camera("Cam_BootSide", (0.95, -0.06, 0.12), (0.19, -0.06, 0.10), 70),
            "boot_front": kc.camera("Cam_BootFront", (0.25, -0.95, 0.22), (0.19, -0.06, 0.10), 70),
            "boot_sole": kc.camera("Cam_BootSole", (0.55, -0.35, -0.45), (0.19, -0.06, 0.0), 70),
        }
        floor = bpy.data.objects.get("Studio_Floor")
        for k, cam in cams.items():
            if floor:
                floor.hide_render = k == "boot_sole"
            kc.render(cam, OUT / f"{k}.png", (900, 700), 48)


if __name__ == "__main__":
    main()
