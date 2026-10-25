# ВСС-М v8 → Substance Painter: развёртка группы деталей (общая UV-плоскость, одинаковая плотность) и FBX для Painter.
# Развёртка пишется в сами детали геометрии (файл сохраняется), в FBX уходят копии с материалом-именем группы
# (= набор текстур в Painter) и именами деталей (маски по детали в Painter).
# blender --background --factory-startup <geometry.blend> --python-exit-code 1 --python tools/vss_m_v8/sp_export.py -- <группа> <out.fbx>
import math
import sys
import bpy

GROUPS = {
    # коробка с крышкой: неподвижные стальные детали ствольной коробки
    "receiver": ["Receiver_lower", "Receiver_cover", "Cover_picatinny", "Receiver_trunnion", "Trigger_guard",
                 "Side_mount_dovetail", "Cover_latch_button", "Receiver_inner_rails", "Safety_axis_end_L", "Safety_visor"],
    "receiver_prefix": ["Receiver_pin_", "Side_mount_rivet_"],
}


def group_objects(name):
    names = list(GROUPS.get(name, []))
    objs = [bpy.data.objects[n] for n in names if n in bpy.data.objects]
    for pre in GROUPS.get(name + "_prefix", []):
        objs += [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(pre)]
    return objs


def unwrap(objs, margin=0.0025):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
        if not o.data.uv_layers:
            o.data.uv_layers.new(name="UVMap")
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(52.0), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(margin=margin, rotate=True, shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")


def export(objs, group, path):
    mat = bpy.data.materials.get(group) or bpy.data.materials.new(group)
    copies = []
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        c = o.copy()
        c.data = o.data.copy()
        c.parent = None
        c.matrix_world = o.matrix_world.copy()
        c.animation_data_clear()
        c.data.materials.clear()
        c.data.materials.append(mat)
        c.name = o.name + "__sp"
        bpy.context.scene.collection.objects.link(c)
        c.select_set(True)
        copies.append(c)
    bpy.context.view_layer.update()
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", use_mesh_modifiers=True, axis_forward="-Z", axis_up="Y",
                             object_types={"MESH"}, bake_anim=False)
    for c in copies:
        d = c.data
        bpy.data.objects.remove(c, do_unlink=True)
        bpy.data.meshes.remove(d)


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    group, out = a[0], a[1]
    # контролы — в исходное положение
    ctrl = bpy.data.objects.get("VSS_Controls")
    if ctrl:
        for k in list(ctrl.keys()):
            if not k.startswith("_"):
                ctrl[k] = 0.0
        bpy.context.view_layer.update()
    objs = group_objects(group)
    print("GROUP", group, len(objs), [o.name for o in objs][:40])
    unwrap(objs)
    export(objs, group, out)
    bpy.ops.wm.save_mainfile()
    print("EXPORTED", out)


if __name__ == "__main__":
    main()
