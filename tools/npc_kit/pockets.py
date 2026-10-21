"""Накладные карманы-карго брюк объёмом: карман по форме бедра с выпуклостью (в нём что-то лежит,
низ тяжелее), клапан внахлёст с толщиной и двумя кнопками. Деталь лежит на поверхности брюк из
симуляции (лучами к оси ноги), край пристрочен вплотную. Развёртка — свои метры (UV_Pattern), рисунок
камуфляжа на кармане свой — как у настоящей нашивной детали.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

POCKET_W, POCKET_H = 0.165, 0.185     # ширина (перед–зад по бедру), высота
POCKET_Z0 = 0.515                       # низ кармана
FLAP_H, FLAP_OVER = 0.058, 0.006        # высота клапана, на сколько шире кармана с каждой стороны
GRID = 0.006


def smooth01(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def surface_frame(bvh: BVHTree, side: float, z: float) -> tuple[Vector, Vector, Vector, Vector]:
    """Точка на внешней стороне бедра и её базис: нормаль, «вверх» по поверхности, «поперёк»."""
    hit = bvh.ray_cast(Vector((side * 0.6, -0.01, z)), Vector((-side, 0, 0)))
    c, n = hit[0], hit[1].normalized()
    if n.x * side < 0:
        n = -n
    up = (Vector((0, 0, 1)) - n * n.z).normalized()
    across = up.cross(n).normalized()          # перед ↔ зад
    return c, n, up, across


def project(bvh: BVHTree, p: Vector, n: Vector) -> tuple[Vector, Vector]:
    hit = bvh.ray_cast(p + n * 0.05, -n, 0.12)
    if hit[0] is None:
        return p, n
    hn = hit[1] if hit[1].dot(n) > 0 else -hit[1]
    return hit[0], hn


def patch(bvh: BVHTree, c: Vector, n: Vector, up: Vector, across: Vector, u0: float, u1: float,
          v0: float, v1: float, lift) -> tuple[list[Vector], list[tuple[float, float]], list[list[int]], int, int]:
    nu = max(2, int(round((u1 - u0) / GRID)))
    nv = max(2, int(round((v1 - v0) / GRID)))
    verts, uvs = [], []
    for j in range(nv + 1):
        v = v0 + (v1 - v0) * j / nv
        for i in range(nu + 1):
            u = u0 + (u1 - u0) * i / nu
            s, sn = project(bvh, c + across * u + up * v, n)
            verts.append(s + sn * lift(u, v))
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
    out = []
    for side in (1.0, -1.0):
        zc = POCKET_Z0 + POCKET_H / 2
        c, n, up, across = surface_frame(bvh, side, zc)
        hw, hh = POCKET_W / 2, POCKET_H / 2

        def pocket_lift(u: float, v: float) -> float:
            # Выпуклость: у края 1,5 мм (пристрочен), к середине до 9 мм, низ полнее (содержимое тянет вниз).
            eu = smooth01((hw - abs(u)) / 0.022)
            ev = smooth01((v + hh) / 0.03) * smooth01((hh - v) / 0.02)
            belly = (1 - (u / hw) ** 2) * (0.55 + 0.45 * smooth01((hh * 0.3 - v) / hh))
            wob = 0.0008 * math.sin(u * 160 + v * 40) * math.sin(v * 95)
            return 0.0015 + (0.0075 * belly + wob) * eu * ev
        verts, uvs, faces, nu, nv = patch(bvh, c, n, up, across, -hw, hw, -hh, hh, pocket_lift)

        def flap_lift(u: float, v: float) -> float:
            # Клапан над карманом: верх пришит к брюкам, низ лежит на кармане и чуть отстаёт.
            under = pocket_lift(max(-hw, min(hw, u)), max(-hh, min(hh, v))) if abs(u) <= hw else 0.0015
            top = smooth01((hh + FLAP_H * 0.15 - v) / 0.012)
            return 0.0012 + (under + 0.0022) * top + 0.0012 * smooth01((hh - FLAP_H * 0.6 - v) / 0.02)
        fv, fuv, ff, fnu, fnv = patch(bvh, c, n, up, across, -hw - FLAP_OVER, hw + FLAP_OVER,
                                      hh - FLAP_H + 0.012, hh + 0.012, flap_lift)
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
        buttons = []
        for bu in (-hw * 0.55, hw * 0.55):
            s, sn = project(bvh, c + across * bu + up * (hh - FLAP_H * 0.5 + 0.012), n)
            at = s + sn * (flap_lift(bu, hh - FLAP_H * 0.5 + 0.012) + 0.0004)
            buttons += snap_button(bm, at, sn)
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
