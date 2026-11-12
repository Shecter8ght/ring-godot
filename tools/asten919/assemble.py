# АСТЕН-919: сборка сцены Blender из деталей (build.py → *.npz + manifest.json).
#   blender --background --factory-startup --python-exit-code 1 --python tools/asten919/assemble.py -- <папка полей> <out.blend> [--raw] [--adapt 0.1]
# Поле расстояний каждой детали превращается в сетку OpenVDB: в плоских местах грани крупные, на скруглениях — по
# вокселю (--adapt — степень укрупнения, --raw — без него). Нормали вершин берутся из градиента поля: плоскости
# ровные, скругления гладкие при любой разбивке. Подвижные детали — на пустышке ASTEN919_Controls (свойства-ползунки).
import json
import math
import os
import sys
import time

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dims  # noqa: E402

MM = 0.001
# цвет в окне (diffuse_color) светлее настоящего — форму чёрных деталей иначе не разглядеть; в материале — настоящий
MATS = {
    "Steel_nitride": ((0.045, 0.045, 0.048), 0.42, 1.0, (0.36, 0.37, 0.39)),
    "Steel_black": ((0.035, 0.036, 0.038), 0.5, 1.0, (0.30, 0.31, 0.33)),
    "Steel_bare": ((0.32, 0.32, 0.33), 0.32, 1.0, (0.62, 0.62, 0.64)),
    "Spring_steel": ((0.16, 0.16, 0.17), 0.38, 1.0, (0.50, 0.50, 0.52)),
    "Polymer": ((0.03, 0.03, 0.031), 0.62, 0.0, (0.22, 0.22, 0.225)),
    "Polymer_mag": ((0.028, 0.028, 0.03), 0.55, 0.0, (0.19, 0.19, 0.20)),
    "Brass": ((0.62, 0.42, 0.16), 0.3, 1.0, (0.72, 0.55, 0.25)),
    "Bullet_jacket": ((0.55, 0.30, 0.18), 0.3, 1.0, (0.66, 0.40, 0.26)),
    "Primer": ((0.55, 0.52, 0.45), 0.3, 1.0, (0.66, 0.63, 0.55)),
}
ROOT = "АСТЕН-919"
CONTROLS = "ASTEN919_Controls"
ADAPT = 0.08


def material(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        col, rough, metal, view = MATS.get(name, ((0.5, 0.5, 0.5), 0.5, 0.0, (0.5, 0.5, 0.5)))
        m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF")
        b.inputs["Base Color"].default_value = (*col, 1.0)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        m.diffuse_color = (*view, 1.0); m.roughness = rough; m.metallic = 0.0
    return m


def collection(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def mesh_from(name, V, tris, quads=None):
    """Сетка из вершин (мм) и граней: треугольники и (или) четырёхугольники."""
    me = bpy.data.meshes.new(name)
    tris = np.zeros((0, 3), np.int32) if tris is None else np.asarray(tris, np.int32).reshape(-1, 3)
    quads = np.zeros((0, 4), np.int32) if quads is None else np.asarray(quads, np.int32).reshape(-1, 4)
    me.vertices.add(len(V)); me.vertices.foreach_set("co", (np.asarray(V, np.float32) * MM).ravel())
    loops = np.concatenate([tris.ravel(), quads.ravel()])
    me.loops.add(len(loops)); me.loops.foreach_set("vertex_index", loops)
    nt, nq = len(tris), len(quads)
    start = np.concatenate([np.arange(nt, dtype=np.int32) * 3, nt * 3 + np.arange(nq, dtype=np.int32) * 4])
    total = np.concatenate([np.full(nt, 3, np.int32), np.full(nq, 4, np.int32)])
    me.polygons.add(nt + nq)
    me.polygons.foreach_set("loop_start", start)
    me.polygons.foreach_set("loop_total", total)
    me.polygons.foreach_set("use_smooth", np.ones(len(me.polygons), bool))
    me.update()
    me.validate()
    return me


def trilinear(A, q):
    """Значения поля A в точках q (в индексах вокселей)."""
    n = np.array(A.shape)
    q = np.clip(q, 0.0, n - 1.001)
    i = np.floor(q).astype(np.int64); f = (q - i).astype(np.float32)
    x, y, z = i[:, 0], i[:, 1], i[:, 2]
    fx, fy, fz = f[:, 0], f[:, 1], f[:, 2]
    c00 = A[x, y, z] * (1 - fx) + A[x + 1, y, z] * fx
    c10 = A[x, y + 1, z] * (1 - fx) + A[x + 1, y + 1, z] * fx
    c01 = A[x, y, z + 1] * (1 - fx) + A[x + 1, y, z + 1] * fx
    c11 = A[x, y + 1, z + 1] * (1 - fx) + A[x + 1, y + 1, z + 1] * fx
    return (c00 * (1 - fy) + c10 * fy) * (1 - fz) + (c01 * (1 - fy) + c11 * fy) * fz


def field_mesh(name, d, adapt):
    """Поле расстояний → сетка OpenVDB и нормали вершин по градиенту поля."""
    import openvdb as vdb
    A = d["field"].astype(np.float32); h = float(d["h"]); lo = d["lo"]
    g = vdb.FloatGrid(background=4 * h)
    g.copyFromArray(A, tolerance=0.0)
    g.transform = vdb.createLinearTransform(voxelSize=h)
    g.gridClass = vdb.GridClass.LEVEL_SET
    pts, tris, quads = g.convertToPolygons(isovalue=0.0, adaptivity=adapt)
    del g
    q = (pts / h).astype(np.float32)
    N = np.zeros((len(q), 3), np.float32)
    for k in range(3):
        e = np.zeros(3, np.float32); e[k] = 0.75
        N[:, k] = trilinear(A, q + e) - trilinear(A, q - e)
    ln = np.linalg.norm(N, axis=1)
    N[ln < 1e-9] = (0, 0, 1)
    N /= np.maximum(ln, 1e-9)[:, None]
    # OpenVDB отдаёт грани нормалями внутрь — переворачиваем
    me = mesh_from(name, pts + lo[None, :], tris[:, ::-1] if len(tris) else None, quads[:, ::-1] if len(quads) else None)
    me.normals_split_custom_set_from_vertices(N.tolist())
    return me


def set_origin(o, p_mm):
    p = Vector(p_mm) * MM
    o.data.transform(Matrix.Translation(-p))
    o.location = p


def set_parent(child, parent):
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    child.matrix_world = mw


def driver(o, path, index, expr, ctrl, props):
    """Привод: выражение expr от свойств пустышки управления (простые выражения — без разрешения на скрипты)."""
    fc = o.driver_add(path, index)
    dr = fc.driver
    dr.type = "SCRIPTED"
    for p in props:
        v = dr.variables.new(); v.name = p; v.type = "SINGLE_PROP"
        v.targets[0].id = ctrl; v.targets[0].data_path = f'["{p}"]'
    dr.expression = expr


def controls(objs, top):
    """Пустышка управления: ползунки 0…1 двигают детали через приводы (delta-трансформы, исходные места не тронуты)."""
    c = bpy.data.objects.new(CONTROLS, None)
    c.empty_display_type = "PLAIN_AXES"; c.empty_display_size = 0.02
    top.objects.link(c)
    spec = [("slide", "Затвор: 0 — в переднем положении, 1 — на задержке"), ("stop", "Затворная задержка: 1 — поднята"),
            ("trigger", "Спуск: 1 — выжат до упора"), ("trigger_safety", "Предохранитель спуска: 1 — утоплен"),
            ("mag_catch", "Кнопка магазина: 1 — нажата"), ("slide_lock", "Защёлка затвора: 1 — опущена"),
            ("mag_out", "Магазин: 1 — вынут вдоль оси рукояти")]
    for k, tip in spec:
        c[k] = 0.0
        ui = c.id_properties_ui(k); ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description=tip)

    def have(n):
        return objs.get(n, (None,))[0]
    T = dims.SLIDE_TRAVEL * MM
    if have("Slide"):
        driver(have("Slide"), "delta_location", 0, f"-{T:.6f}*slide", c, ["slide"])
    # ствол отпирается на первых 6 мм хода затвора: назад и казённик вниз вокруг точки у отверстия затвора
    u = f"min(1.0, slide*{dims.SLIDE_TRAVEL / 6.0:.4f})"
    th = math.radians(dims.BARREL_TILT); px = 67.0 * MM
    for n in ("Barrel", "Barrel_Threaded"):
        b = have(n)
        if b:
            driver(b, "delta_rotation_euler", 1, f"-{th:.6f}*{u}", c, ["slide"])
            driver(b, "delta_location", 0, f"-{dims.BARREL_BACK * MM:.6f}*{u} + {px:.6f}*(1-cos({th:.6f}*{u}))", c, ["slide"])
            driver(b, "delta_location", 2, f"-{px:.6f}*sin({th:.6f}*{u})", c, ["slide"])
    if have("Slide_Stop"):
        driver(have("Slide_Stop"), "delta_rotation_euler", 1, f"{math.radians(dims.STOP_UP_DEG):.6f}*stop", c, ["stop"])
    if have("Trigger"):
        driver(have("Trigger"), "delta_rotation_euler", 1, f"{math.radians(dims.TRIGGER_DEG):.6f}*trigger", c, ["trigger"])
    if have("Trigger_Safety"):
        driver(have("Trigger_Safety"), "delta_rotation_euler", 1, f"{math.radians(dims.SAFETY_DEG):.6f}*trigger_safety", c, ["trigger_safety"])
    if have("Mag_Catch"):
        driver(have("Mag_Catch"), "delta_location", 1, f"-{dims.CATCH_IN * MM:.6f}*mag_catch", c, ["mag_catch"])
    if have("Slide_Lock"):
        a = math.radians(dims.LOCK_DEG)
        driver(have("Slide_Lock"), "delta_location", 0, f"-{math.sin(a) * dims.LOCK_DOWN * MM:.6f}*slide_lock", c, ["slide_lock"])
        driver(have("Slide_Lock"), "delta_location", 2, f"-{math.cos(a) * dims.LOCK_DOWN * MM:.6f}*slide_lock", c, ["slide_lock"])
    if have("Magazine_Body"):
        driver(have("Magazine_Body"), "delta_location", 0, f"-{dims.SIN * dims.MAG_OUT * MM:.6f}*mag_out", c, ["mag_out"])
        driver(have("Magazine_Body"), "delta_location", 2, f"-{dims.COS * dims.MAG_OUT * MM:.6f}*mag_out", c, ["mag_out"])
    return c


def main():
    global ADAPT
    argv = sys.argv[sys.argv.index("--") + 1:]
    src = os.path.abspath(argv[0]); out = os.path.abspath(argv[1])
    raw = "--raw" in argv
    rest = argv[2:]
    if "--adapt" in rest:
        ADAPT = float(rest[rest.index("--adapt") + 1]); del rest[rest.index("--adapt"):rest.index("--adapt") + 2]
    only = [a for a in rest if not a.startswith("--")]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"; sc.unit_settings.scale_length = 1.0; sc.unit_settings.length_unit = "MILLIMETERS"
    man = json.load(open(os.path.join(src, "manifest.json"), encoding="utf-8"))
    top = collection(ROOT)
    objs = {}
    total = 0
    for p in man:
        if only and p["name"] not in only:
            continue
        path = os.path.join(src, p["file"])
        if not os.path.exists(path):
            print("NO_MESH", p["name"]); continue
        t = time.time()
        d = np.load(path)
        is_field = "field" in d
        if is_field:
            me = field_mesh(p["name"], d, 0.0 if raw else p.get("adapt", ADAPT))
        else:
            me = mesh_from(p["name"], d["v"], d["f"] if d["f"].shape[1] == 3 else None, d["f"] if d["f"].shape[1] == 4 else None)
        coll = collection(p.get("coll", "Misc"), top)
        o = bpy.data.objects.new(p["name"], me)
        coll.objects.link(o)
        if not is_field:
            # готовые сетки (пружины, тела вращения): гладкие, острые рёбра по углу
            bm = bmesh.new(); bm.from_mesh(o.data)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            for e in bm.edges:
                e.smooth = len(e.link_faces) == 2 and e.calc_face_angle(0) < math.radians(p.get("sharp", 40))
            bm.to_mesh(o.data); bm.free()
        if p.get("mats"):
            # несколько материалов в одной сетке: номер материала у каждой грани — массив «m» в файле детали
            for mn in p["mats"]:
                o.data.materials.append(material(mn))
            if "m" in d and len(d["m"]) == len(o.data.polygons):
                o.data.polygons.foreach_set("material_index", np.asarray(d["m"], np.int32))
        else:
            o.data.materials.append(material(p.get("mat", "Steel_black")))
        if p.get("pivot"):
            set_origin(o, p["pivot"])
        for k in ("motion", "note"):
            if p.get(k):
                o[k] = p[k] if isinstance(p[k], str) else json.dumps(p[k], ensure_ascii=False)
        o.data.calc_loop_triangles()
        nt = len(o.data.loop_triangles); total += nt
        objs[p["name"]] = (o, p)
        print(f"OBJ {p['name']}: {nt} тр., {time.time() - t:.1f} с", flush=True)
    # копии (патроны в магазине и т. п.): общая сетка, своя матрица (16 чисел по строкам, сдвиг в мм)
    for name, (o, p) in list(objs.items()):
        for inst in p.get("instances", []):
            c = bpy.data.objects.new(inst["name"], o.data)
            collection(inst.get("coll", p.get("coll", "Misc")), top).objects.link(c)
            m = Matrix([inst["matrix"][0:4], inst["matrix"][4:8], inst["matrix"][8:12], inst["matrix"][12:16]])
            m.translation = m.translation * MM
            c.matrix_world = m
            objs[inst["name"]] = (c, {"parent": inst.get("parent"), "coll": inst.get("coll", p.get("coll"))})
            total += len(o.data.loop_triangles)
        if p.get("instances") and not p.get("keep_base"):
            for c in list(o.users_collection):
                c.objects.unlink(o)
            total -= len(o.data.loop_triangles)
            del objs[name]
            if o.users == 0:
                bpy.data.objects.remove(o)
    ctrl = controls(objs, top)
    for name, (o, p) in objs.items():
        par = p.get("parent")
        if par and par in objs:
            set_parent(o, objs[par][0])
        elif p.get("coll") != "Ammo":
            set_parent(o, ctrl)
    # варианты (ствол с резьбой и т. п.) — отдельные коллекции, выключенные по умолчанию
    vl = bpy.context.view_layer
    for p in man:
        if p.get("coll_hidden"):
            lc = vl.layer_collection.children[ROOT].children.get(p["coll"])
            if lc:
                lc.exclude = True
    print("TOTAL_TRIS", total, "OBJECTS", len(objs))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("SAVED", out)


main()
