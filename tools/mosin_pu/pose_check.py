"""Проверка поз затвора в сборке: закрыт / поворот рукояти вверх / отвод назад и промежуточные положения.

blender --background --factory-startup <assembly.blend> --python tools/mosin_pu/pose_check.py -- <out_dir> [render]
Печатает пары объектов, чьи треугольники пересекаются (BVH overlap) в каждой позе: подвижный затвор против
остальной винтовки (с креплением и прицелом, если они в файле) и внутри затвора — поворотные детали (стебель,
личинка, выбрасыватель) против неповоротных (планка, курок, ударник). Печатает и значения драйверов: ход курка
(кулачок взведения) и положение отсечки-отражателя. С аргументом render — кадры трёх основных поз.
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
# (имя, поворот стебля, ход затвора, курок на взводе)
POSES = [
    ("closed", 0.0, 0.0, 0.0),
    ("closed_cocked", 0.0, 0.0, 1.0),
    ("rot15", -15.0, 0.0, 0.0),
    ("rot30", -30.0, 0.0, 0.0),
    ("rot45", -45.0, 0.0, 0.0),
    ("rot60", -60.0, 0.0, 0.0),
    ("rot75", -75.0, 0.0, 0.0),
    ("rotated", OPEN_ANGLE, 0.0, 0.0),
    ("back10", OPEN_ANGLE, -10.0, 0.0),
    ("back20", OPEN_ANGLE, -20.0, 0.0),
    ("back35", OPEN_ANGLE, -35.0, 0.0),
    ("back50", OPEN_ANGLE, -50.0, 0.0),
    ("back55", OPEN_ANGLE, -55.0, 0.0),
    ("back57", OPEN_ANGLE, -57.0, 0.0),
    ("back60", OPEN_ANGLE, -60.0, 0.0),
    ("back75", OPEN_ANGLE, -75.0, 0.0),
    ("back87", OPEN_ANGLE, -87.2, 0.0),
    ("open", OPEN_ANGLE, TRAVEL, 0.0),
    ("open_cocked", OPEN_ANGLE, TRAVEL, 1.0),
]
RENDER_POSES = ("closed", "rotated", "open")


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


def check(label, group_a, group_b):
    trees_a = {o.name: bvh(o) for o in group_a if o.type == "MESH"}
    trees_b = {o.name: bvh(o) for o in group_b if o.type == "MESH"}
    hits = []
    for a, ta in trees_a.items():
        for b, tb in trees_b.items():
            n = len(ta.overlap(tb))
            if n:
                hits.append((a, b, n))
    for a, b, n in hits:
        print(f"   {label}: {a} × {b}: {n}")
    return hits


def main():
    bolt = bpy.data.objects["Bolt"]
    rotor = bpy.data.objects["Bolt_Rotor"]
    cocking = bpy.data.objects.get("Bolt_Cocking")
    slide = bpy.data.objects.get("Interrupter_Slide")
    moving = descendants(bolt)
    names = {o.name for o in moving}
    others = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name not in names
              and not o.name.startswith(("Bolt",))]
    turning = [o for o in descendants(rotor) if o.type == "MESH"]
    still = [o for o in moving if o.type == "MESH" and o not in turning]
    for ob in (cocking, slide):
        if ob and ob.animation_data:
            for fc in ob.animation_data.drivers:
                d = fc.driver
                print(f"DRIVER {ob.name}.{fc.data_path}[{fc.array_index}] = {d.expression}  "
                      f"simple={d.is_simple_expression} valid={d.is_valid}")
    base_bolt = bolt.matrix_basis.copy()
    base_rot = rotor.matrix_basis.copy()
    base_cocked = bolt.get("cocked", 0.0)
    total = 0
    for label, ang, travel, cocked in POSES:
        rotor.matrix_basis = base_rot @ Matrix.Rotation(math.radians(ang), 4, "X")
        bolt.matrix_basis = Matrix.Translation((travel * L.MM, 0, 0)) @ base_bolt
        if "cocked" in bolt:
            bolt["cocked"] = cocked
        bolt.update_tag()
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        info = ""
        if cocking:
            info += f" курок {cocking.evaluated_get(dg).matrix_world.translation.x / L.MM - travel:+.2f} мм"
        if slide:
            info += f" отражатель {slide.evaluated_get(dg).matrix_world.translation.y / L.MM:+.2f} мм"
        hits = check(label, moving, others) + check(label, turning, still)
        total += len(hits)
        print(f"POSE {label}: поворот {ang:.0f}°, ход {travel:.1f} мм,{info} — {len(hits)} пересечений")
        if RENDER and label in RENDER_POSES:
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
    if "cocked" in bolt:
        bolt["cocked"] = base_cocked
    print(f"POSES TOTAL: {total} пересечений в {len(POSES)} позах")


main()
