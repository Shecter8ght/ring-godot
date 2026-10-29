# AR-15 «ГРАНЬ-15»: глушитель отдельным файлом (в игре — покупной предмет). Берёт собранный .blend винтовки,
# оставляет только Suppressor_body с его деталями, ставит центр посадочного торца в начало координат (ось канала — X).
# blender -b <AR15_geometry.blend> --python tools/ar15/delivery_suppressor.py -- <out.blend>
import sys
import bpy
from mathutils import Matrix, Vector


def tree(o):
    out = [o]
    for c in o.children:
        out += tree(c)
    return out


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    ctrl = bpy.data.objects.get("AR15_Controls")
    if ctrl is not None:
        ctrl["suppressor_on"] = 1.0          # на тормозе: посадочный торец на оси канала
        ctrl.update_tag()
    bpy.context.view_layer.update()
    root = bpy.data.objects["Suppressor_body"]
    keep = tree(root)
    world = {o.name: o.matrix_world.copy() for o in keep}
    for o in keep:
        o.animation_data_clear()
    mount = world[root.name].translation.copy()
    shift = Matrix.Translation(-mount)
    # корень — без родителя, дети остаются его детьми
    root.parent = None
    root.matrix_world = shift @ world[root.name]
    bpy.context.view_layer.update()
    for o in keep[1:]:
        o.matrix_world = shift @ world[o.name]
    for o in list(bpy.data.objects):
        if o not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    sup_c = bpy.data.collections.get("Suppressor")
    for c in list(bpy.data.collections):
        if c is not sup_c and c.name != "AR15":
            bpy.data.collections.remove(c)
    for o in keep:
        if sup_c is not None and sup_c not in o.users_collection:
            sup_c.objects.link(o)
    try:
        bpy.ops.outliner.orphans_purge(do_recursive=True)
    except Exception:
        pass
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "SOLID"
                        sp.shading.color_type = "MATERIAL"
                        sp.shading.show_cavity = True
                        sp.region_3d.view_location = Vector((0.08, 0.0, 0.0))
                        sp.region_3d.view_distance = 0.45
                        sp.clip_start = 0.002
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("SAVED", out, "objects", len(keep), "mount_was", [round(c * 1000, 2) for c in mount])


main()
