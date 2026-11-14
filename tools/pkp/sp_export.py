# «Частокол» → Substance Painter: FBX проекта (tex_sets.PROJECTS) с файла развёртки (по образцу
# tools/asten919/sp_export.py). Копия детали: материал = имя набора (набор текстур в Painter), имя = «<деталь>__sp»
# (маски по детали). Детали разложены врозь рядами с зазором (поворот сохранён — трёхпроекционные узоры ложатся по осям
# пулемёта): при запекании AO и толщины одна деталь не затеняет другую — подвижные потом сдвигаются. У копий ленты одна
# сетка — в проект идёт одна копия. Патрон и гильза — кусками по материалам формы (гильза, пуля, капсюль).
# Многоугольники больше четырёх вершин режутся на треугольники (Painter режет их сам — с мусором в AO).
# blender -b "<Частокол_развёртка_v01.blend>" --factory-startup --python-exit-code 1 --python tools/pkp/sp_export.py -- <проект> <out.fbx>
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
ROW_MM = 1200.0
PIECE = {"Case_lacquer": "case", "Bullet_jacket": "bullet", "Primer": "primer"}


def coords(me):
    import numpy as np
    a = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


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
        if len(o.data.polygons) == 0:
            d = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.meshes.remove(d)
            continue
        out.append((o, mn))
    d = c.data
    bpy.data.objects.remove(c, do_unlink=True)
    bpy.data.meshes.remove(d)
    return out


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    proj, out = a[0], a[1]
    sets = T.PROJECTS[proj]
    ctl = bpy.data.objects.get("PKP_Controls")
    if ctl:
        print("PKP_Controls:", {k: round(float(ctl[k]), 3) for k in ctl.keys() if isinstance(ctl[k], (int, float))})
    keep_names = set()
    order = []
    for s in sets:
        seen = set()
        for n in T.SETS[s][2]:
            o = bpy.data.objects[n]
            if o.data.name in seen:
                continue
            seen.add(o.data.name)
            order.append((s, o))
            keep_names.add(o.name)
    # всё лишнее — прочь (память): объекты других проектов и их сетки; файл не сохраняется
    mats_of = {o.name: [sl.material.name if sl.material else "" for sl in o.material_slots] for _s, o in order}
    world = {o.name: o.matrix_world.copy() for _s, o in order}
    keep_mesh = {o.data.name for _s, o in order}
    for me in list(bpy.data.meshes):
        if me.name not in keep_mesh:
            bpy.data.meshes.remove(me)
    mm = 0.001
    copies, info = [], {}
    x = z = row_h = 0.0
    for s, o in order:
        if "UVMap" not in o.data.uv_layers:
            raise RuntimeError("нет развёртки: " + o.name)
        mat = bpy.data.materials.get(s) or bpy.data.materials.new(s)
        me = o.data.copy()
        me.transform(world[o.name])
        c = bpy.data.objects.new(o.name + "__sp", me)
        bpy.context.scene.collection.objects.link(c)
        names = mats_of[o.name]
        if len(names) > 1 and all(n in PIECE for n in names):
            pieces = split_by_material(c, o.name, names)
        else:
            pieces = [(c, names[0] if names else "")]
        for q, mn in pieces:
            info[q.name] = dict(set=s, mat=mn, obj=o.name, mesh=o.data.name)
            q.data.materials.clear()
            q.data.materials.append(mat)
            beauty(q.data)
        import numpy as np
        co = np.concatenate([coords(q.data) for q, _ in pieces])
        lo, hi = Vector(co.min(0)), Vector(co.max(0))
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
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=out, use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", use_mesh_modifiers=False, axis_forward="-Z", axis_up="Y",
                             object_types={"MESH"}, bake_anim=False)
    with open(os.path.splitext(out)[0] + "_meshes.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, ensure_ascii=False, indent=0)
    import numpy as np
    co = np.concatenate([coords(q.data) for q in copies])
    size = float((co.max(0) - co.min(0)).max()) / mm
    with open(os.path.splitext(out)[0] + "_scene.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({"size_mm": round(size, 1)}, f)
    print("FBX", out, len(copies), "сеток", sum(len(q.data.polygons) for q in copies), "граней, сцена", round(size), "мм")


main()
