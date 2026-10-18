"""Обойма в направляющих коробки: сцена для показа и проверка посадки (затвор открыт до упора, прицела нет).

blender --background --factory-startup --python tools/mosin_pu/clip_guide_check.py -- [rifle_ver]
→ models/00_Сборка/Mosin_ClipGuide_check_<ver>.blend: винтовка, основание кронштейна (кронштейн с прицелом снят —
без него заряжают обоймой), обойма с пятью патронами в гнёздах стоек и верхний патрон магазина — его закраина перед
торцом отведённой личинки. Печатает зазоры и пересечения обоймы и патронов с винтовкой, основанием и затвором.
"""
import os
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mosin_lib as L  # noqa: E402
import build_rifle as R  # noqa: E402

A = L.ASSET_DIR
args = L.script_args()
RV = args[0] if args else "v08"
RIFLE = os.path.join(A, "models", "01_Винтовка", f"Mosin_9130PU_Rifle_{RV}.blend")
MOUNT = os.path.join(A, "models", "03_Крепление", "Mosin_PU_Mount_v01_tex20_v01.blend")
CLIP = os.path.join(A, "models", "00_Сборка", "Mosin_Clip_loaded_check_v01.blend")
CARTRIDGE = os.path.join(A, "models", "04_Патрон", "Mosin_Cartridge_762x54R_v01_tex_v01.blend")
OUT = os.path.join(A, "models", "00_Сборка", f"Mosin_ClipGuide_check_{RV}.blend")
CLIP_HALF = 35.0                      # половина длины обоймы (build_clip.HALF_LEN)
CLIP_OUT_Y = 7.9                      # наружная грань стенки обоймы у спинки
RCV_R_IN = 9.35                       # канал коробки (build_receiver): на нём стоят нижние концы стенок обоймы
RIM_X = R.CLIP_SPINE_X + 0.5          # донца патронов в обойме (внутренняя грань спинки)
MAG_TOP_Z = -12.2 + 7.24 + 0.05      # ось верхнего патрона магазина: закраина лежит на поднятом подавателе


def append(path, col_name, keep=None):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if keep is None or keep(n)]
    col = L.collection(col_name)
    obs = [o for o in dst.objects if o is not None]
    for ob in obs:
        col.objects.link(ob)
    return obs


def bvh(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world
    tree = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons],
                                all_triangles=False, epsilon=0.0)
    ev.to_mesh_clear()
    return tree


def main():
    L.reset_scene()
    rifle = append(RIFLE, "Rifle")
    # основание остаётся на коробке, кронштейн с прицелом снят
    base = append(MOUNT, "Mount_Base", keep=lambda n: n.startswith(("PU_Mount", "Mount_Base", "Mount_LockScrew")))
    clip = append(CLIP, "Clip_in_guides")
    top = append(CARTRIDGE, "Magazine_top_round")
    bpy.context.view_layer.update()

    bolt = bpy.data.objects["Bolt"]
    rotor = bpy.data.objects["Bolt_Rotor"]
    rotor.rotation_euler.x = -1.5707963
    bolt.location.x = -R.BOLT_TRAVEL * L.MM
    bolt["cocked"] = 1.0
    # обойма: спинка в гнёздах стоек, нижний конец стенок стоит на трубе коробки
    z_floor = (RCV_R_IN ** 2 - CLIP_OUT_Y ** 2) ** 0.5
    z_clip = z_floor + CLIP_HALF + 0.05
    shift = Matrix.Translation(Vector((RIM_X, 0.0, z_clip)) * L.MM)
    for ob in clip:
        if ob.parent is None:
            ob.matrix_world = shift @ ob.matrix_world
    # верхний патрон магазина
    t_root = [o for o in top if o.parent is None]
    for ob in t_root:
        ob.matrix_world = Matrix.Translation(Vector((RIM_X, 0.0, MAG_TOP_Z)) * L.MM) @ ob.matrix_world
    bpy.context.view_layer.update()

    meshes = lambda obs: [o for o in obs if o.type == "MESH"]  # noqa: E731
    clip_m, top_m = meshes(clip), meshes(top)
    fixed = [o for o in meshes(rifle) + meshes(base)]
    total = 0
    for group, label in ((clip_m, "обойма"), (top_m, "патрон магазина")):
        trees = {o.name: bvh(o) for o in group}
        for f in fixed:
            tf = bvh(f)
            for name, t in trees.items():
                n = len(t.overlap(tf))
                if n:
                    total += n
                    print(f"   {label}: {name} × {f.name}: {n}")
    face = bpy.data.objects["Bolt_Head"]
    lo, hi = L.world_bbox_mm([face])
    print(f"торец личинки x {hi[0]:.2f} мм, донца патронов x {RIM_X:.2f} мм — зазор {RIM_X - hi[0]:.2f} мм")
    lo, hi = L.world_bbox_mm(clip_m)
    print(f"обойма с патронами: x {lo[0]:.1f}…{hi[0]:.1f}, y {lo[1]:.1f}…{hi[1]:.1f}, z {lo[2]:.1f}…{hi[2]:.1f} мм")
    print(f"CLIP CHECK: {total} пересечений")
    L.save_blend(OUT)


main()
