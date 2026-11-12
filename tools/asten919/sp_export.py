# АСТЕН-919 → Substance Painter: FBX всех наборов текстур одним файлом (по образцу tools/ar15/sp_export.py).
# Копия детали: материал = имя набора (набор текстур в Painter), имя = «<деталь>__sp» (маски по детали). Детали
# разложены врозь рядами с зазором (поворот сохранён — трёхпроекционные маски ложатся по осям пистолета): при
# запекании AO и толщины одна деталь не затеняет другую — подвижные потом сдвигаются. Патрон (общая сетка 18 копий) —
# один, гильза, пуля и капсюль — отдельными сетками (у них разные отделки). Нормали из поля расстояний уходят в файл.
# blender --background <АСТЕН-919_развёртка_v01.blend> --factory-startup --python-exit-code 1 --python tools/asten919/sp_export.py -- <out.fbx>
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
import tex_sets as T  # noqa: E402

GAP_MM = 40.0          # зазор между деталями: больше дальности лучей AO
ROW_MM = 600.0
SPLIT = {"Round_9x19_loose": "Round", "Case_9x19": "Case"}     # деталь → начало имён кусков по материалам
PIECE = {"Brass": "case", "Bullet_jacket": "bullet", "Primer": "primer"}


def parts():
    """[(набор, объект)] в порядке наборов."""
    out = []
    for s, (_res, names) in T.SETS.items():
        for n in names:
            out.append((s, bpy.data.objects[n]))
    return out


def beauty(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    big = [f for f in bm.faces if len(f.verts) > 4]
    if big:
        bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="BEAUTY")
        bm.to_mesh(me)
    bm.free()


def split_by_material(c, prefix, mats):
    out = []
    for i, mn in enumerate(mats):
        o = c.copy()
        o.data = c.data.copy()
        o.name = f"{prefix}_{PIECE[mn]}__sp"
        bpy.context.scene.collection.objects.link(o)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != i], context="FACES")
        bm.to_mesh(o.data)
        bm.free()
        out.append((o, mn))
    d = c.data
    bpy.data.objects.remove(c, do_unlink=True)
    bpy.data.meshes.remove(d)
    return out


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    ctl = bpy.data.objects.get("ASTEN919_Controls")
    if ctl:                                     # всё в исходном положении
        for k in ("slide", "stop", "trigger", "trigger_safety", "mag_catch", "slide_lock", "mag_out"):
            if k in ctl:
                ctl[k] = 0.0
        ctl.update_tag()
        bpy.context.view_layer.update()
    mm = 0.001
    copies = []
    info = {}          # сетка в Painter → набор, материал геометрии, деталь
    x = z = row_h = 0.0
    for s, o in parts():
        if "UVMap" not in o.data.uv_layers:
            raise RuntimeError("нет развёртки: " + o.name)
        mat = bpy.data.materials.get(s) or bpy.data.materials.new(s)
        c = o.copy()
        c.data = o.data.copy()
        c.parent = None
        c.animation_data_clear()
        bpy.context.scene.collection.objects.link(c)
        c.data.transform(o.matrix_world)
        c.matrix_world = Matrix.Identity(4)
        c.delta_location = (0, 0, 0)
        c.delta_rotation_euler = (0, 0, 0)
        names = [sl.material.name for sl in o.material_slots]
        if o.name in SPLIT:
            pieces = split_by_material(c, SPLIT[o.name], names)
        else:
            c.name = o.name + "__sp"
            pieces = [(c, names[0] if names else "")]
        for q, mn in pieces:
            info[q.name] = dict(set=s, mat=mn, obj=o.name)
            q.data.materials.clear()
            q.data.materials.append(mat)
            beauty(q.data)
        vs = [v.co for q, _ in pieces for v in q.data.vertices]
        lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
        hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
        w, h = (hi.x - lo.x) / mm, (hi.z - lo.z) / mm
        if x > 0 and x + w > ROW_MM:
            x, z, row_h = 0.0, z + row_h + GAP_MM, 0.0
        sh = Vector((x * mm - lo.x, -(lo.y + hi.y) / 2, z * mm - lo.z))
        for q, _ in pieces:
            q.data.transform(Matrix.Translation(sh))
        x += w + GAP_MM
        row_h = max(row_h, h)
        copies += [q for q, _ in pieces]
    bpy.ops.object.select_all(action="DESELECT")
    for q in copies:
        q.select_set(True)
    bpy.context.view_layer.update()
    bpy.ops.export_scene.fbx(filepath=out, use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", use_mesh_modifiers=False, axis_forward="-Z", axis_up="Y",
                             object_types={"MESH"}, bake_anim=False)
    with open(os.path.splitext(out)[0] + "_meshes.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, ensure_ascii=False, indent=0)
    # наибольший размер сцены, мм: трёхпроекционные узоры Painter считают плитки на него
    vs = [v.co for q in copies for v in q.data.vertices]
    size = max(max(getattr(v, a) for v in vs) - min(getattr(v, a) for v in vs) for a in "xyz") / mm
    with open(os.path.splitext(out)[0] + "_scene.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({"size_mm": round(size, 1)}, f)
    print("FBX", out, len(copies), "сеток", sum(len(q.data.polygons) for q in copies), "граней")


main()
