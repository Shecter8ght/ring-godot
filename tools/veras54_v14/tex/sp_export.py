# ВЕРАС-54 v14 → Substance Painter: FBX проекта (tex_sets.PROJECTS) с файла развёртки (по образцу tools/pkp/sp_export.py).
# Копия детали: материал = имя набора (набор текстур в Painter), имя сетки = понятное имя детали (tex_sets.sp_name:
# маска и отделка в Painter — по сетке). Детали разложены врозь рядами с зазором (поворот сохранён — трёхпроекционные
# узоры ложатся по осям автомата): при запекании AO и толщины одна деталь не затеняет другую — подвижные потом
# сдвигаются. Экземпляры патронов (tex_sets.INSTANCES) в проект не идут — у них та же развёртка, что у первого.
# Рядом — <проект>_meshes.json (сетка → набор, слот, деталь, заглушка формы) и <проект>_scene.json (размер сцены).
# blender -b "<ВЕРАС-54_развёртка_v14_01.blend>" --factory-startup --python-exit-code 1 --python tools/veras54_v14/tex/sp_export.py -- <проект> <out.fbx>
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
import tex_sets as T  # noqa: E402

GAP_MM = 30.0          # зазор между деталями: больше дальности лучей AO
ROW_MM = 800.0


def coords(me):
    a = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    proj, out = a[0], os.path.abspath(a[1])
    sets = T.PROJECTS[proj]
    ctl = bpy.data.objects.get(T.CONTROLS)
    if ctl:
        print("Controls:", {k: round(float(ctl[k]), 3) for k in ctl.keys() if isinstance(ctl[k], (int, float))})
    # патрон в патроннике — в полный размер (привод live_round = 0 держит пулю × 0,001)
    b = bpy.data.objects.get("Chambered_Bullet")
    if b is not None and b.animation_data:
        for d in list(b.animation_data.drivers):
            if d.data_path == "delta_scale":
                b.animation_data.drivers.remove(d)
        b.delta_scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
    order = [(s, bpy.data.objects[n]) for s in sets for n in T.SETS[s][2]]
    world = {o.name: o.matrix_world.copy() for _s, o in order}
    keep_mesh = {o.data.name for _s, o in order}
    # всё лишнее — прочь (память); файл не сохраняется
    for me in list(bpy.data.meshes):
        if me.name not in keep_mesh:
            bpy.data.meshes.remove(me)
    for _s, o in order:              # имена деталей освобождаются под копии
        o.name = o.name + "__src"
    mm = 0.001
    copies, info = [], {}
    x = z = row_h = 0.0
    for s, o in order:
        src = o.name[:-5]
        if "UVMap" not in o.data.uv_layers or len(o.data.uv_layers) != 1:
            raise RuntimeError("развёртка не одна или её нет: " + src)
        mat = bpy.data.materials.get(s)
        if mat is None:
            raise RuntimeError("нет материала набора " + s)
        me = o.data.copy()
        me.transform(world[src])
        nm = T.sp_name(src)
        me.name = nm
        c = bpy.data.objects.new(nm, me)
        if c.name != nm:
            raise RuntimeError(f"имя занято: {nm} → {c.name}")
        bpy.context.scene.collection.objects.link(c)
        me.materials.clear()
        me.materials.append(mat)
        info[nm] = dict(set=s, slot=T.slot_of(src) or "", obj=src, stub=o.get("v14_stub", ""))
        co = coords(me)
        lo, hi = Vector(co.min(0)), Vector(co.max(0))
        w, h = (hi.x - lo.x) / mm, (hi.z - lo.z) / mm
        if x > 0 and x + w > ROW_MM:
            x, z, row_h = 0.0, z + row_h + GAP_MM, 0.0
        me.transform(Matrix.Translation(Vector((x * mm - lo.x, -(lo.y + hi.y) / 2, z * mm - lo.z))))
        x += w + GAP_MM
        row_h = max(row_h, h)
        copies.append(c)
    bpy.ops.object.select_all(action="DESELECT")
    for q in copies:
        q.select_set(True)
    bpy.context.view_layer.update()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=out, use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", use_mesh_modifiers=False, axis_forward="-Z", axis_up="Y",
                             object_types={"MESH"}, bake_anim=False)
    base = os.path.splitext(out)[0]
    with open(base + "_meshes.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, ensure_ascii=False, indent=0)
    co = np.concatenate([coords(q.data) for q in copies])
    size = float((co.max(0) - co.min(0)).max()) / mm
    with open(base + "_scene.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({"size_mm": round(size, 1), "sets": sets, "res": {s: T.SETS[s][0] for s in sets}}, f)
    print("FBX", out, len(copies), "сеток", sum(len(q.data.polygons) for q in copies), "граней, сцена", round(size), "мм")


main()
