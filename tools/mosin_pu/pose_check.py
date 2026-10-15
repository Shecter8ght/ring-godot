"""Проверка поз затвора в сборке: закрыт / повёрнут (рукоять вверх) / отведён назад.

blender --background --factory-startup <assembly.blend> --python tools/mosin_pu/pose_check.py -- <out_dir> [render]
Печатает пары объектов, чьи треугольники пересекаются (BVH overlap) в каждой позе; с аргументом render — кадры.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mosin_lib as L  # noqa: E402

args = L.script_args()
OUT = args[0]
RENDER = "render" in args
OPEN_ANGLE = -90.0          # стебель поворачивается рукоятью вверх (правая сторона −Y)
TRAVEL = -88.0              # ход затвора назад, мм


def bvh(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)


def descendants(root):
    out = []
    for ch in root.children:
        out.append(ch)
        out += descendants(ch)
    return out


def check(label, moving, others):
    trees_m = {o.name: bvh(o) for o in moving if o.type == "MESH"}
    trees_o = {o.name: bvh(o) for o in others if o.type == "MESH"}
    hits = []
    for a, ta in trees_m.items():
        for b, tb in trees_o.items():
            n = len(ta.overlap(tb))
            if n:
                hits.append((a, b, n))
    print(f"POSE {label}: {len(hits)} пересечений")
    for a, b, n in hits:
        print(f"   {a} × {b}: {n}")
    return hits


def main():
    bolt = bpy.data.objects["Bolt"]
    rotor = bpy.data.objects["Bolt_Rotor"]
    moving = descendants(bolt)
    names = {o.name for o in moving}
    others = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name not in names
              and not o.name.startswith(("Bolt",))]
    base_bolt = bolt.matrix_basis.copy()
    base_rot = rotor.matrix_basis.copy()
    poses = {
        "closed": (0.0, 0.0),
        "rotated": (OPEN_ANGLE, 0.0),
        "open": (OPEN_ANGLE, TRAVEL),
    }
    for label, (ang, travel) in poses.items():
        rotor.matrix_basis = base_rot @ Matrix.Rotation(math.radians(ang), 4, "X")
        bolt.matrix_basis = Matrix.Translation((travel * L.MM, 0, 0)) @ base_bolt
        bpy.context.view_layer.update()
        check(label, moving, others)
        if RENDER:
            sys.argv = [sys.argv[0], "--", "--out", OUT, "--prefix", f"pose_{label}", "--name", "rcv",
                        "--dir=-0.35,0.8,-0.5", "--focus=-90,0,15", "--dist", "430", "--res", "1400x900",
                        "--samples", "24"]
            # отрисовка тем же сценарием видов
            g = {"__name__": "__render__"}
            exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_views.py"),
                      encoding="utf-8").read(), g)
            for o in list(bpy.data.objects):
                if o.type in ("LIGHT", "CAMERA"):
                    bpy.data.objects.remove(o, do_unlink=True)
    rotor.matrix_basis = base_rot
    bolt.matrix_basis = base_bolt


main()
