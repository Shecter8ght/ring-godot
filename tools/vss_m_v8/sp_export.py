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
    # проект «parts»: наборы текстур по материалу, детали при запекании разложены врозь
    "steel_parts": ["Bolt_carrier", "Bolt_carrier_plate", "Bolt_carrier_web", "Charging_handle", "Gas_piston_rod",
                    "Fire_selector", "Magazine_catch", "Safety_lever", "Trigger", "Front_sling_bracket", "Front_sling_swivel",
                    "Rail_sleeve_screws", "Stock_screw_L", "Stock_screw_R", "Stock_sling_plate", "Stock_sling_rivet_0",
                    "Stock_sling_rivet_1", "Stock_sling_swivel", "Rear_sight_base", "Rear_sight_hinge_pin", "Rear_sight_leaf",
                    "Rear_sight_slider", "Rear_sight_weld", "Front_sight_base", "Front_sight_post"],
    "suppressor": ["Suppressor_body", "Suppressor_baffles", "Barrel"],
    "bare_steel": ["Bolt", "Bolt_extractor", "Bolt_firing_pin_tip", "Ejector_blade", "Recoil_spring_guide", "Recoil_spring",
                   "Magazine_10_spring", "Magazine_20_spring", "Magazine_30_spring"],
    "handguard": ["Handguard"],
    "sleeve": ["Rail_sleeve"],
    "magazine": ["Magazine_10", "Magazine_10_floorplate", "Magazine_10_follower", "Magazine_10_plate_button",
                 "Magazine_20", "Magazine_20_floorplate", "Magazine_20_follower", "Magazine_20_plate_button",
                 "Magazine_30", "Magazine_30_floorplate", "Magazine_30_follower", "Magazine_30_plate_button"],
    "wood": ["Wood_stock_v8"],
    "rubber": ["Rubber_butt_pad"],
    # все 60 патронов — одна сетка: в Painter один патрон, гильза и пуля — отдельными сетками (маски по имени)
    "rounds": ["Magazine_30_round_01"],
}
PARTS = ["steel_parts", "suppressor", "bare_steel", "handguard", "sleeve", "magazine", "wood", "rubber", "rounds"]


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


def split_by_material(c, names):
    """Копия с несколькими материалами → отдельные объекты по слоту (имена из names)."""
    import bmesh
    out = []
    for i, nm in enumerate(names):
        o = c.copy(); o.data = c.data.copy(); o.name = nm
        bpy.context.scene.collection.objects.link(o)
        bm = bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != i], context="FACES")
        bm.to_mesh(o.data); bm.free()
        out.append(o)
    d = c.data
    bpy.data.objects.remove(c, do_unlink=True)
    bpy.data.meshes.remove(d)
    return out


def export_parts(path, sets=PARTS, gap=12.0, row_w=520.0):
    """Наборы PARTS в один FBX: материал копии = имя набора; детали разложены рядами без перекрытий,
    чтобы при запекании AO одна деталь не затеняла другую (патроны в магазине, рама в коробке)."""
    from mathutils import Matrix, Vector
    MMs = 0.001
    copies = []
    x = z = row_h = 0.0
    for g in sets:
        objs = group_objects(g)
        unwrap(objs)
        mat = bpy.data.materials.get(g) or bpy.data.materials.new(g)
        for o in objs:
            c = o.copy(); c.data = o.data.copy(); c.parent = None
            c.matrix_world = o.matrix_world.copy(); c.animation_data_clear()
            bpy.context.scene.collection.objects.link(c)
            c.data.transform(c.matrix_world); c.matrix_world = Matrix.Identity(4)
            nslots = len(c.data.materials)
            c.name = o.name + "__sp"
            parts = [c]
            if g == "rounds" and nslots > 1:
                parts = split_by_material(c, ["Round_case__sp", "Round_bullet__sp"])
            for q in parts:
                q.data.materials.clear(); q.data.materials.append(mat)
            vs = [v.co for q in parts for v in q.data.vertices]
            lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
            hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
            w, h = (hi.x - lo.x) / MMs, (hi.z - lo.z) / MMs
            if x > 0 and x + w > row_w:
                x, z, row_h = 0.0, z + row_h + gap, 0.0
            sh = Vector((x * MMs - lo.x, -(lo.y + hi.y) / 2, z * MMs - lo.z))
            for q in parts:
                q.data.transform(Matrix.Translation(sh))
            x += w + gap
            row_h = max(row_h, h)
            copies += parts
    bpy.ops.object.select_all(action="DESELECT")
    for q in copies:
        q.select_set(True)
    bpy.context.view_layer.update()
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", use_mesh_modifiers=True, axis_forward="-Z", axis_up="Y",
                             object_types={"MESH"}, bake_anim=False)
    for q in copies:
        d = q.data
        bpy.data.objects.remove(q, do_unlink=True)
        bpy.data.meshes.remove(d)
    print("PARTS", len(copies), "objects")


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
    if group == "parts":
        export_parts(out)
    else:
        objs = group_objects(group)
        print("GROUP", group, len(objs), [o.name for o in objs][:40])
        unwrap(objs)
        export(objs, group, out)
    bpy.ops.wm.save_mainfile()
    print("EXPORTED", out)


if __name__ == "__main__":
    main()
