# ВСС-М v8: прицелы комплекта (ПСО 4×24 и 4×32 на планку) → Substance Painter. Детали делятся по материалам на наборы
# текстур (корпус — анодированный алюминий, ободки — точёный алюминий, гравировка — заливка краской, внутренняя чернь,
# резина); стёкла остаются процедурными. У каждого набора своя развёртка. Результат — файл с прицелами (иерархия
# сохранена, сцена берёт их отсюда) и FBX для Painter (два прицела рядом, без перекрытия).
# blender --background --factory-startup --python-exit-code 1 --python tools/vss_m_v8/sights_sp.py -- <sights_sp.blend> <sights.fbx>
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
import sp_export  # noqa: E402

KIT = "E:/Models Blender/WEAPONS/ВСС Винторез — полный комплект/01_Blender/02_Оптика"
SOURCES = ((f"{KIT}/01_ПСО_4x24/ПСО_4x24_Исходник_геометрии.blend", "PSO_VSS_4x24"),
           (f"{KIT}/02_Прицел_4x32/Прицел_4x32_Исходник_геометрии.blend", "Rail_4x32"))
SETS = {"Coated aluminium": "optic_body", "Machined rim": "optic_rim", "Engraving": "optic_engraving",
        "Inner black": "optic_inner", "Rubber": "optic_rubber"}
SET_NAMES = ("optic_body", "optic_body_432", "optic_rim", "optic_engraving", "optic_inner", "optic_rubber")
FBX_SHIFT = Vector((0.0, 0.25, 0.0))     # 4×32 в FBX сдвинут вбок от ПСО — запекание не путает прицелы


def append_root(path, root_name):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    root = None
    for o in dst.objects:
        if o is not None and o.parent is None and o.name.split(".")[0] == root_name:
            root = o
    keep = []
    for o in dst.objects:
        if o is None:
            continue
        r = o
        while r.parent is not None:
            r = r.parent
        if r is root:
            bpy.context.scene.collection.objects.link(o)
            keep.append(o)
        else:
            bpy.data.objects.remove(o, do_unlink=True)
    return root, keep


def set_of(mat):
    if mat is None:
        return None
    nm = mat.name.split(".")[0]
    return SETS.get(nm)


def split(o):
    """Деталь с несколькими материалами → по объекту на набор (тот же родитель и положение); стекло — своим."""
    import bmesh
    slots = [s.material for s in o.material_slots]
    groups = {}
    for i, m in enumerate(slots):
        groups.setdefault(set_of(m) or ("glass" if m is not None else None), []).append(i)
    if len(groups) <= 1:
        k = next(iter(groups)) if groups else None
        if k in SET_NAMES:
            mat = bpy.data.materials.get(k) or bpy.data.materials.new(k)
            o.data.materials.clear()
            o.data.materials.append(mat)
        return [o]
    out = []
    for k, idx in groups.items():
        c = o.copy()
        c.data = o.data.copy()
        c.name = f"{o.name}_{k}"
        bpy.context.scene.collection.objects.link(c)
        c.parent = o.parent
        c.matrix_world = o.matrix_world.copy()
        bm = bmesh.new()
        bm.from_mesh(c.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index not in idx], context="FACES")
        bm.to_mesh(c.data)
        bm.free()
        if k in SET_NAMES:
            mat = bpy.data.materials.get(k) or bpy.data.materials.new(k)
            c.data.materials.clear()
            c.data.materials.append(mat)
        out.append(c)
    for ch in list(o.children):
        mw = ch.matrix_world.copy()
        ch.parent = out[0]
        ch.matrix_world = mw
    d = o.data
    bpy.data.objects.remove(o, do_unlink=True)
    if d.users == 0:
        bpy.data.meshes.remove(d)
    return out


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out_blend, out_fbx = a[0], a[1]
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    by_set = {k: [] for k in SET_NAMES}
    roots = []
    for path, rn in SOURCES:
        root, objs = append_root(path, rn)
        roots.append(root)
        for o in objs:
            if o.type != "MESH":
                continue
            if o.data.users > 1:
                o.data = o.data.copy()
            for p in split(o):
                k = p.data.materials[0].name.split(".")[0] if p.data.materials else None
                if k == "optic_body" and rn == "Rail_4x32":   # у каждого корпуса своя карта 4K (на двоих 2K — 3,3 пикс/мм, «мыло»)
                    k = "optic_body_432"
                    p.data.materials[0] = bpy.data.materials.get(k) or bpy.data.materials.new(k)
                if k in by_set:
                    by_set[k].append((rn, p))
    for k, items in by_set.items():
        objs = [p for _, p in items]
        if objs:
            sp_export.unwrap(objs, margin=0.004)
        print("SET", k, len(objs))
    bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=True)
    print("SAVED", out_blend)
    # FBX: копии в мировых координатах, 4×32 сдвинут вбок
    copies = []
    bpy.ops.object.select_all(action="DESELECT")
    for k, items in by_set.items():
        for rn, o in items:
            c = o.copy()
            c.data = o.data.copy()
            c.parent = None
            c.matrix_world = o.matrix_world.copy()
            bpy.context.scene.collection.objects.link(c)
            c.data.transform(c.matrix_world)
            c.matrix_world = Matrix.Identity(4)
            if rn == "Rail_4x32":
                c.data.transform(Matrix.Translation(FBX_SHIFT))
            c.name = o.name + "__sp"
            sp_export.triangulate_ngons(c)
            c.select_set(True)
            copies.append(c)
    bpy.context.view_layer.update()
    bpy.ops.export_scene.fbx(filepath=out_fbx, use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", use_mesh_modifiers=True, axis_forward="-Z", axis_up="Y",
                             object_types={"MESH"}, bake_anim=False)
    print("EXPORTED", out_fbx, len(copies))


main()
