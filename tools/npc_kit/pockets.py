"""Накладные карманы-карго брюк объёмом: карман по форме бедра с выпуклостью (в нём что-то лежит,
низ тяжелее), клапан внахлёст с толщиной и двумя кнопками. Деталь лежит на поверхности брюк из
симуляции: точки кладутся лучами к оси ноги (по кругу бедра — край не уходит вскользь и не висит
в воздухе), поверхность сглажена поверх складок брюк — пришитая деталь перекрывает впадины, а не
повторяет каждую складку. Развёртка — свои метры (UV_Pattern), рисунок камуфляжа на кармане свой —
как у настоящей нашивной детали.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

POCKET_W, POCKET_H = 0.165, 0.185     # ширина (перед–зад по бедру, по дуге), высота
POCKET_Z0 = 0.515                       # низ кармана
POCKET_FWD = 12.0                       # карман чуть вынесен вперёд от бока бедра (градусы)
FLAP_H, FLAP_OVER = 0.058, 0.006        # высота клапана, на сколько шире кармана с каждой стороны
GRID = 0.006


def smooth01(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class LegFrame:
    """Развёртка по бедру: u — дуга по кругу ноги от середины кармана (+ назад), v — высота от его середины.
    Ось ноги — середины сечений брюк по высоте; радиус r(u, v) — лучами снаружи к оси, сглажен и не ниже
    брюк (зазор lift считается от него)."""

    def __init__(self, pants_bvh: BVHTree, pants_co: list[Vector], side: float, zc: float,
                 u0: float, u1: float, v0: float, v1: float):
        self.side, self.zc = side, zc
        self.bvh = pants_bvh
        # ось: середина габарита сечения ноги через 1 см по высоте
        self.axis: dict[int, Vector] = {}
        for k in range(int((v0 - 0.03) * 100), int((v1 + 0.03) * 100) + 1):
            z = zc + k / 100
            sl = [p for p in pants_co if abs(p.z - z) < 0.008 and p.x * side > 0.015]
            xs, ys = [p.x for p in sl], [p.y for p in sl]
            self.axis[k] = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, z))
        a = math.radians(POCKET_FWD)
        self.d0 = Vector((side * math.cos(a), -math.sin(a), 0.0))   # середина кармана: бок, чуть вперёд
        self.r0 = self._hit(self.centre(0.0), self.d0)
        # сетка радиусов по (u, v) с шагом GRID, сглаженная поверх складок
        self.u0, self.v0 = u0 - GRID, v0 - GRID
        self.nu = int(round((u1 - u0) / GRID)) + 3
        self.nv = int(round((v1 - v0) / GRID)) + 3
        raw = [[self._hit(self.centre(self.v0 + j * GRID), self.dir(self.u0 + i * GRID)) for i in range(self.nu)]
               for j in range(self.nv)]
        g = [row[:] for row in raw]
        for _ in range(24):
            new = [row[:] for row in g]
            for j in range(self.nv):
                for i in range(self.nu):
                    nb = [g[j][max(0, i - 1)], g[j][min(self.nu - 1, i + 1)], g[max(0, j - 1)][i], g[min(self.nv - 1, j + 1)][i]]
                    new[j][i] = max(0.5 * g[j][i] + 0.5 * sum(nb) / 4, raw[j][i] + 0.0004)
            g = new
        self.g = g

    def centre(self, v: float) -> Vector:
        z = self.zc + v
        k = (z - self.zc) * 100
        k0 = math.floor(k)
        t = k - k0
        a = self.axis.get(k0) or self.axis[min(self.axis, key=lambda q: abs(q - k0))]
        b = self.axis.get(k0 + 1, a)
        c = a.lerp(b, t)
        return Vector((c.x, c.y, z))

    def dir(self, u: float) -> Vector:
        # +u: на левой ноге (+X) — назад, на правой — вперёд (как прежде: лицевая сторона сетки смотрит наружу)
        ang = u / max(self.r0, 0.05)
        d = self.d0
        return Vector((d.x * math.cos(ang) - d.y * math.sin(ang), d.x * math.sin(ang) + d.y * math.cos(ang), 0.0))

    def _hit(self, c: Vector, d: Vector) -> float:
        hit = self.bvh.ray_cast(c + d * 0.3, -d, 0.3)
        return (hit[0] - c).dot(d) if hit[0] is not None else 0.09

    def r(self, u: float, v: float) -> float:
        fi = max(0.0, min(self.nu - 1.0001, (u - self.u0) / GRID))
        fj = max(0.0, min(self.nv - 1.0001, (v - self.v0) / GRID))
        i, j = int(fi), int(fj)
        ti, tj = fi - i, fj - j
        g = self.g
        a = g[j][i] * (1 - ti) + g[j][i + 1] * ti
        b = g[j + 1][i] * (1 - ti) + g[j + 1][i + 1] * ti
        return a * (1 - tj) + b * tj

    def point(self, u: float, v: float, lift: float = 0.0) -> Vector:
        return self.centre(v) + self.dir(u) * (self.r(u, v) + lift)

    def normal(self, u: float, v: float) -> Vector:
        return self.dir(u)


def patch(frame: LegFrame, u0: float, u1: float, v0: float, v1: float,
          lift) -> tuple[list[Vector], list[tuple[float, float]], list[list[int]], int, int]:
    nu = max(2, int(round((u1 - u0) / GRID)))
    nv = max(2, int(round((v1 - v0) / GRID)))
    verts, uvs = [], []
    for j in range(nv + 1):
        v = v0 + (v1 - v0) * j / nv
        for i in range(nu + 1):
            u = u0 + (u1 - u0) * i / nu
            verts.append(frame.point(u, v, lift(u, v)))
            uvs.append((u - u0, v - v0))
    faces = [[j * (nu + 1) + i, j * (nu + 1) + i + 1, (j + 1) * (nu + 1) + i + 1, (j + 1) * (nu + 1) + i]
             for j in range(nv) for i in range(nu)]
    return verts, uvs, faces, nu, nv


def snap_button(bm: bmesh.types.BMesh, at: Vector, n: Vector, r: float = 0.0062, h: float = 0.0026) -> list:
    """Кнопка-«пятак»: низкий цилиндр со скруглённым верхом."""
    t = n.orthogonal().normalized()
    b = n.cross(t)
    rings = []
    for k, (rr, hh) in enumerate(((r, 0.0), (r, h * 0.6), (r * 0.82, h), (r * 0.4, h * 1.12))):
        rings.append([bm.verts.new(at + n * hh + (t * math.cos(a) + b * math.sin(a)) * rr)
                      for a in (2 * math.pi * q / 20 for q in range(20))])
    faces = []
    for r0, r1 in zip(rings, rings[1:]):
        for q in range(20):
            faces.append(bm.faces.new((r0[q], r0[(q + 1) % 20], r1[(q + 1) % 20], r1[q])))
    faces.append(bm.faces.new(rings[-1]))
    return faces


def cargo_pockets(pants: bpy.types.Object, col: bpy.types.Collection, material: bpy.types.Material,
                  metal: bpy.types.Material) -> list[bpy.types.Object]:
    dg = bpy.context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(pants, dg)
    ev = pants.evaluated_get(dg)
    me = ev.to_mesh()
    pants_co = [pants.matrix_world @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    out = []
    for side in (1.0, -1.0):
        zc = POCKET_Z0 + POCKET_H / 2
        hw, hh = POCKET_W / 2, POCKET_H / 2
        frame = LegFrame(bvh, pants_co, side, zc, -hw - FLAP_OVER, hw + FLAP_OVER, -hh, hh + 0.012)

        def pocket_lift(u: float, v: float) -> float:
            # Выпуклость: у края 1,5 мм (пристрочен), к середине до 9 мм, низ полнее (содержимое тянет вниз).
            eu = smooth01((hw - abs(u)) / 0.022)
            ev_ = smooth01((v + hh) / 0.03) * smooth01((hh - v) / 0.02)
            belly = (1 - (u / hw) ** 2) * (0.55 + 0.45 * smooth01((hh * 0.3 - v) / hh))
            wob = 0.0008 * math.sin(u * 160 + v * 40) * math.sin(v * 95)
            return 0.0015 + (0.0075 * belly + wob) * eu * ev_
        verts, uvs, faces, nu, nv = patch(frame, -hw, hw, -hh, hh, pocket_lift)

        def flap_lift(u: float, v: float) -> float:
            # Клапан над карманом: верх пришит к брюкам, низ лежит на кармане и чуть отстаёт;
            # за краями кармана (FLAP_OVER) — на брюках, с тем же нахлёстом толщины.
            under = pocket_lift(max(-hw, min(hw, u)), max(-hh, min(hh, v))) if abs(u) <= hw else 0.0015
            top = smooth01((hh + FLAP_H * 0.15 - v) / 0.012)
            return 0.0012 + (under + 0.0022) * top + 0.0012 * smooth01((hh - FLAP_H * 0.6 - v) / 0.02)
        fv, fuv, ff, fnu, fnv = patch(frame, -hw - FLAP_OVER, hw + FLAP_OVER, hh - FLAP_H + 0.012, hh + 0.012, flap_lift)
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new("UV_Pattern")
        for vs, us, fs, ox in ((verts, uvs, faces, 0.0), (fv, fuv, ff, POCKET_W + 0.05)):
            bv = [bm.verts.new(p) for p in vs]
            for f in fs:
                face = bm.faces.new([bv[i] for i in f])
                for loop, i in zip(face.loops, f):
                    loop[uvl].uv = (us[i][0] + ox + (0.0 if side > 0 else 0.5), us[i][1])
        cloth_faces = list(bm.faces)
        # Кнопки на клапане.
        for bu in (-hw * 0.55, hw * 0.55):
            bv_ = hh - FLAP_H * 0.5 + 0.012
            at = frame.point(bu, bv_, flap_lift(bu, bv_) + 0.0004)
            snap_button(bm, at, frame.normal(bu, bv_))
        bm.normal_update()
        mesh = bpy.data.meshes.new(f"Pants_Pocket_{'L' if side > 0 else 'R'}")
        bm.to_mesh(mesh)
        bm.free()
        mesh.materials.append(material)
        mesh.materials.append(metal)
        n_cloth = len(cloth_faces)
        for poly in mesh.polygons:
            poly.material_index = 0 if poly.index < n_cloth else 1
            poly.use_smooth = True
        obj = bpy.data.objects.new(mesh.name, mesh)
        col.objects.link(obj)
        mod = obj.modifiers.new("Thickness", "SOLIDIFY")
        mod.thickness = 0.0012
        mod.offset = -1.0
        mod.use_rim = True
        out.append(obj)
    return out
