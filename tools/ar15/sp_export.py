# AR-15 «ГРАНЬ-15» → Substance Painter: FBX всех наборов текстур одним файлом (по образцу tools/vss_m_v8/sp_export.py).
# Копия детали: материал = имя набора (набор текстур в Painter), имя = «<деталь>__sp» (маски по детали), многоугольники
# больше четырёх вершин — треугольниками BEAUTY (Painter режет их сам, на вогнутых — мусор в AO и кривизне).
# Детали разложены врозь рядами с зазором (поворот сохранён — трёхпроекционные маски ложатся по осям винтовки):
# при запекании AO и толщины одна деталь не затеняет другую — подвижные потом сдвигаются, затвор выходит из коробки.
# Патрон (общая сетка 31 копии) — один, гильза и пуля отдельными сетками.
# blender --background <AR15_uv_v01.blend> --factory-startup --python-exit-code 1 --python tools/ar15/sp_export.py -- <out.fbx>
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
import tex_sets as T  # noqa: E402

GAP_MM = 40.0          # зазор между деталями: больше дальности лучей AO
ROW_MM = 700.0


def parts():
    """[(набор, объект)] в порядке наборов; у общей сетки патрона — один объект Cartridge_556."""
    out = []
    for s in T.SETS:
        for o in bpy.data.objects:
            if o.type == "MESH" and o.get("ar15_set") == s and T.set_of(o.name) == s:
                out.append((s, o))
    return out


def beauty(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    big = [f for f in bm.faces if len(f.verts) > 4]
    if big:
        bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="BEAUTY")
        bm.to_mesh(me)
    bm.free()


def split_by_material(c, names):
    out = []
    for i, nm in enumerate(names):
        o = c.copy()
        o.data = c.data.copy()
        o.name = nm
        bpy.context.scene.collection.objects.link(o)
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != i], context="FACES")
        bm.to_mesh(o.data)
        bm.free()
        out.append(o)
    d = c.data
    bpy.data.objects.remove(c, do_unlink=True)
    bpy.data.meshes.remove(d)
    return out


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    MMs = 0.001
    copies = []
    info = {}          # сетка в Painter → набор, материал геометрии, деталь (маски по материалу внутри набора)
    x = z = row_h = 0.0
    for s, o in parts():
        mat = bpy.data.materials.get(s) or bpy.data.materials.new(s)
        c = o.copy()
        c.data = o.data.copy()
        c.parent = None
        c.animation_data_clear()
        bpy.context.scene.collection.objects.link(c)
        c.data.transform(o.matrix_world)
        c.matrix_world = Matrix.Identity(4)
        c.name = o.name + "__sp"
        pieces = [c]
        if o.name == "Cartridge_556":
            pieces = split_by_material(c, ["Round_case__sp", "Round_bullet__sp"])
            info["Round_case__sp"] = dict(set=s, mat="Brass", obj=o.name)
            info["Round_bullet__sp"] = dict(set=s, mat="Bullet_jacket", obj=o.name)
        else:
            info[c.name] = dict(set=s, mat=o.get("ar15_mat", ""), obj=o.name)
        for q in pieces:
            q.data.materials.clear()
            q.data.materials.append(mat)
            beauty(q.data)
        vs = [v.co for q in pieces for v in q.data.vertices]
        lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
        hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
        w, h = (hi.x - lo.x) / MMs, (hi.z - lo.z) / MMs
        if x > 0 and x + w > ROW_MM:
            x, z, row_h = 0.0, z + row_h + GAP_MM, 0.0
        sh = Vector((x * MMs - lo.x, -(lo.y + hi.y) / 2, z * MMs - lo.z))
        for q in pieces:
            q.data.transform(Matrix.Translation(sh))
        x += w + GAP_MM
        row_h = max(row_h, h)
        copies += pieces
    bpy.ops.object.select_all(action="DESELECT")
    for q in copies:
        q.select_set(True)
    bpy.context.view_layer.update()
    bpy.ops.export_scene.fbx(filepath=out, use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", use_mesh_modifiers=False, axis_forward="-Z", axis_up="Y",
                             object_types={"MESH"}, bake_anim=False)
    import json
    with open(os.path.splitext(out)[0] + "_meshes.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, ensure_ascii=False, indent=0)
    print("FBX", out, len(copies), "сеток")


main()
