# ВЕРАС-54 v14: сборка сцены Blender из деталей (build.py → куски полей *.npz + manifest.json).
#   blender --background --factory-startup --python-exit-code 1 --python tools/veras54_v14/geo/assemble.py -- <папка полей> <out.blend>
#       [деталь …] [--raw] [--adapt 0.1] [--adapt-scale 0.4]
# Поле расстояний детали (куски вдоль X) складывается в одну разрежённую сетку OpenVDB и превращается в сетку:
# в плоских местах грани крупные, на скруглениях — по вокселю (--adapt — степень укрупнения, --raw — без него;
# --adapt-scale — множитель укрупнения всех деталей: меньше — чище тонкие рёбра и выштамповки, больше треугольников).
# Нормали вершин берутся из градиента поля: плоскости ровные, скругления гладкие при любой разбивке.
# Подвижные детали — на пустышке VERAS54_Controls (свойства-ползунки, part_rig.py).
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

MM = 0.001
# цвет в окне (diffuse_color) светлее настоящего — форму чёрных деталей иначе не разглядеть; в материале — настоящий
MATS = {
    "Steel_blued": ((0.040, 0.041, 0.044), 0.42, 1.0, (0.36, 0.37, 0.39)),      # воронёная сталь: коробка, крышка, ствол
    "Steel_phosphate": ((0.055, 0.056, 0.058), 0.6, 1.0, (0.33, 0.34, 0.35)),   # фосфатированные мелкие детали
    "Steel_bare": ((0.32, 0.32, 0.33), 0.32, 1.0, (0.62, 0.62, 0.64)),          # белая сталь: затворная рама, затвор
    "Spring_steel": ((0.16, 0.16, 0.17), 0.38, 1.0, (0.50, 0.50, 0.52)),
    "Alu_anodized": ((0.030, 0.030, 0.033), 0.5, 1.0, (0.27, 0.28, 0.30)),      # съёмные кронштейны с планками
    "Polymer": ((0.022, 0.022, 0.023), 0.5, 0.0, (0.20, 0.20, 0.205)),          # приклад, рукоятка
    "Mag_polymer": ((0.030, 0.030, 0.031), 0.55, 0.0, (0.24, 0.24, 0.245)),     # магазин
    "Rubber": ((0.018, 0.018, 0.018), 0.8, 0.0, (0.15, 0.15, 0.15)),            # затыльник
    "Case_lacquer": ((0.33, 0.30, 0.12), 0.38, 1.0, (0.55, 0.50, 0.28)),        # гильза: биметалл под лаком
    "Bullet_jacket": ((0.55, 0.30, 0.18), 0.3, 1.0, (0.66, 0.40, 0.26)),
    "Primer": ((0.60, 0.42, 0.20), 0.3, 1.0, (0.70, 0.52, 0.30)),
}
ROOT = "ВЕРАС-54"
CONTROLS = "VERAS54_Controls"
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
    """Сетка из вершин (мм) и граней: треугольники и (или) четырёхугольники. Четырёхугольник с повтором последней
    вершины (токарные сетки у оси) становится треугольником."""
    me = bpy.data.meshes.new(name)
    tris = np.zeros((0, 3), np.int32) if tris is None else np.asarray(tris, np.int32).reshape(-1, 3)
    quads = np.zeros((0, 4), np.int32) if quads is None else np.asarray(quads, np.int32).reshape(-1, 4)
    order = None
    if len(quads):
        deg = quads[:, 2] == quads[:, 3]
        if deg.any():
            # порядок граней меняется: сначала треугольники — вернуть перестановку для номеров материалов
            order = np.concatenate([np.where(deg)[0], np.where(~deg)[0]])
            tris = np.vstack([tris, quads[deg][:, :3]]); quads = quads[~deg]
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
    return me, order


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


def field_mesh(name, src, nchunks, adapt):
    """Куски поля расстояний → одна сетка OpenVDB и нормали вершин по градиенту поля."""
    import openvdb as vdb
    files = [os.path.join(src, f"{name}__{i:02d}.npz") for i in range(nchunks)]
    g = None; h = None; lo = None; spans = []
    for f in files:
        d = np.load(f)
        h = float(d["h"]); lo = d["lo"]; s0, c0, c1 = int(d["s0"]), int(d["c0"]), int(d["c1"])
        if g is None:
            g = vdb.FloatGrid(background=4 * h)
            g.transform = vdb.createLinearTransform(voxelSize=h)
            g.gridClass = vdb.GridClass.LEVEL_SET
        core = d["field"][c0 - s0:c1 - s0].astype(np.float32)
        # нутро глубже полосы — в «фон»: воксели не хранятся, знак вернёт заливка
        core[core <= -4 * h * 0.999] = 4 * h
        g.copyFromArray(np.ascontiguousarray(core), ijk=(c0, 0, 0), tolerance=0.0)
        spans.append((s0, c0, c1))
        del core, d
    g.signedFloodFill()
    pts, tris, quads = g.convertToPolygons(isovalue=0.0, adaptivity=adapt)
    del g
    q = (pts / h).astype(np.float32)
    N = np.zeros((len(q), 3), np.float32)
    last = len(spans) - 1
    for ci, (f, (s0, c0, c1)) in enumerate(zip(files, spans)):
        sel = np.ones(len(q), bool)
        if ci > 0:
            sel &= q[:, 0] >= c0
        if ci < last:
            sel &= q[:, 0] < c1
        if not sel.any():
            continue
        A = np.load(f)["field"].astype(np.float32)
        qq = q[sel].copy(); qq[:, 0] -= s0
        for k in range(3):
            e = np.zeros(3, np.float32); e[k] = 0.75
            N[sel, k] = trilinear(A, qq + e) - trilinear(A, qq - e)
        del A
    ln = np.linalg.norm(N, axis=1)
    sharp = ln / (1.5 * h)      # 1 — гладкое место, меньше — вершина на кромке (градиент двух граней гасит себя)
    N[ln < 1e-9] = (0, 0, 1)
    N /= np.maximum(ln, 1e-9)[:, None]
    # OpenVDB отдаёт грани нормалями внутрь — переворачиваем
    me, _ = mesh_from(name, pts + lo[None, :], tris[:, ::-1] if len(tris) else None, quads[:, ::-1] if len(quads) else None)
    me.normals_split_custom_set(crease_normals(me, N, h, sharp).tolist())
    return me


def crease_normals(me, N, h, sharp):
    """Нормали по углам граней. Обычно — градиент поля в вершине (гладко на любых скруглениях). Но у вершины на
    кромке градиент — среднее двух граней, и крупный треугольник упрощённой сетки тянет этот наклон через всю
    плоскость: на кромках ступенек выходили «волоски». Поэтому у вершины на кромке (длина градиента заметно меньше
    единицы) угол крупной грани, чья нормаль расходится с градиентом, берёт нормаль самой грани. Купола и плавные
    бока (градиент полной длины) остаются гладкими."""
    nl, npoly = len(me.loops), len(me.polygons)
    lv = np.empty(nl, np.int32); me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(npoly, np.int32); me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(npoly, np.int32); me.polygons.foreach_get("loop_total", lt)
    pn = np.empty(npoly * 3, np.float32); me.polygons.foreach_get("normal", pn); pn = pn.reshape(-1, 3)
    co = np.empty(len(me.vertices) * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3) / MM
    if len(N) != len(co):       # проверка сетки убрала вершины — оставляем градиент как есть
        return N[np.clip(lv, 0, len(N) - 1)]
    nxt = np.arange(nl, dtype=np.int64) + 1
    nxt[ls + lt - 1] = ls
    elen = np.linalg.norm(co[lv[nxt]] - co[lv], axis=1)
    emax = np.maximum.reduceat(elen, ls)
    pol = np.repeat(np.arange(npoly), lt)
    G = N[lv]; Fn = pn[pol]
    dev = np.degrees(np.arccos(np.clip((G * Fn).sum(axis=1), -1.0, 1.0)))
    big = np.clip((emax[pol] / h - 1.5) / 1.5, 0.0, 1.0)
    t = np.clip((dev - 3.0) / 5.0, 0.0, 1.0)
    c = np.clip((0.985 - sharp[lv]) / 0.035, 0.0, 1.0)
    w = (big * c * t * t * (3 - 2 * t))[:, None].astype(np.float32)
    out = G * (1 - w) + Fn * w
    out /= np.maximum(np.linalg.norm(out, axis=1), 1e-9)[:, None]
    return out


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
    """Пустышка управления: ползунки двигают детали через приводы (delta-трансформы, исходные места не тронуты).
    Описание ползунков и приводов — part_rig.py (им же пользуется проверка пересечений)."""
    c = bpy.data.objects.new(CONTROLS, None)
    c.empty_display_type = "PLAIN_AXES"; c.empty_display_size = 0.03
    top.objects.link(c)
    try:
        import part_rig
    except ImportError:
        return c
    for k, tip, default in part_rig.SLIDERS:
        c[k] = float(default)
        ui = c.id_properties_ui(k); ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description=tip)
    for name, path, index, expr, props in part_rig.drivers():
        o = objs.get(name, (None,))[0]
        if o is not None:
            driver(o, path, index, expr, c, props)
    return c


def append_base(path, top, objs):
    """Детали, которые переходят из v13 без изменений (transfer.py): ствол, газовый узел, дульное устройство,
    затвор, целик, патроны. Сетки и модификаторы — как есть, материалы — простые здешние (карты v13 не тянутся)."""
    import transfer
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        names = [n for n in src.objects if transfer.group_of(n)]
        dst.objects = names
    tris = 0

    def world(o):
        # у только что добавленного объекта matrix_world не посчитана (он ещё не в сцене): собираем её сами
        # по цепочке родителей, иначе детали со своим смещением (штифты, болты, пружина) слетают в начало координат
        m = o.matrix_basis.copy()
        return world(o.parent) @ o.matrix_parent_inverse @ m if o.parent else m

    worlds = {o.name: world(o) for o in dst.objects if o is not None}
    for o in dst.objects:
        if o is None or o.type != "MESH":
            continue
        coll, mat, new_name = transfer.group_of(o.name)
        mw = worlds[o.name]
        o.parent = None
        for pref, dx in transfer.SHIFT_X.items():
            if o.name.startswith(pref):
                mw.translation.x += dx * MM
        for pref, org in transfer.ORIGIN.items():
            if o.name.startswith(pref):
                lp = mw.inverted() @ (Vector(org) * MM)
                o.data.transform(Matrix.Translation(-lp))
                mw = mw @ Matrix.Translation(lp)
        o.matrix_world = mw
        collection(coll, top).objects.link(o)
        o.data.materials.clear()
        o.data.materials.append(material(mat))
        o["from_v13"] = o.name
        objs[o.name] = (o, {"parent": transfer.PARENTS.get(new_name or o.name), "coll": coll})
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    # материалы и карты v13 в файл не сохраняются
    for m in list(bpy.data.materials):
        if m.users == 0:
            bpy.data.materials.remove(m)
    for im in list(bpy.data.images):
        if im.users == 0:
            bpy.data.images.remove(im)
    print("BASE", len([o for o in dst.objects if o is not None]), "объектов из v13,", tris, "тр.")
    return tris


def main():
    global ADAPT
    argv = sys.argv[sys.argv.index("--") + 1:]
    src = os.path.abspath(argv[0]); out = os.path.abspath(argv[1])
    raw = "--raw" in argv
    rest = argv[2:]
    scale = 1.0
    if "--adapt" in rest:
        ADAPT = float(rest[rest.index("--adapt") + 1]); del rest[rest.index("--adapt"):rest.index("--adapt") + 2]
    if "--adapt-scale" in rest:
        scale = float(rest[rest.index("--adapt-scale") + 1]); del rest[rest.index("--adapt-scale"):rest.index("--adapt-scale") + 2]
    base = None
    if "--base" in rest:
        base = rest[rest.index("--base") + 1]; del rest[rest.index("--base"):rest.index("--base") + 2]
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
        t = time.time()
        mats_idx = None
        if p.get("chunks"):
            if not os.path.exists(os.path.join(src, f"{p['name']}__00.npz")):
                print("NO_FIELD", p["name"]); continue
            me = field_mesh(p["name"], src, p["chunks"], 0.0 if raw else p.get("adapt", ADAPT) * scale)
            is_field = True
        else:
            path = os.path.join(src, p["name"] + ".npz")
            if not os.path.exists(path):
                print("NO_MESH", p["name"]); continue
            d = np.load(path)
            f = d["f"]
            me, order = mesh_from(p["name"], d["v"], f if f.shape[1] == 3 else None, f if f.shape[1] == 4 else None)
            if "m" in d:
                mats_idx = np.asarray(d["m"], np.int32)
                if order is not None:
                    mats_idx = mats_idx[order]
            is_field = False
        coll = collection(p.get("coll", "Прочее"), top)
        o = bpy.data.objects.new(p["name"], me)
        coll.objects.link(o)
        if not is_field:
            # готовые сетки (тела вращения, пружины): гладкие, острые рёбра по углу
            bm = bmesh.new(); bm.from_mesh(o.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            lim = math.radians(p.get("sharp", 35))
            for e in bm.edges:
                e.smooth = len(e.link_faces) == 2 and e.calc_face_angle(0) < lim
            bm.to_mesh(o.data); bm.free()
        if p.get("mats"):
            for mn in p["mats"]:
                o.data.materials.append(material(mn))
            if mats_idx is not None and len(mats_idx) == len(o.data.polygons):
                o.data.polygons.foreach_set("material_index", mats_idx)
        else:
            o.data.materials.append(material(p.get("mat", "Steel_blued")))
        if p.get("pivot"):
            set_origin(o, p["pivot"])
        for k in ("motion", "note"):
            if p.get(k):
                o[k] = p[k] if isinstance(p[k], str) else json.dumps(p[k], ensure_ascii=False)
        o.data.calc_loop_triangles()
        nt = len(o.data.loop_triangles); total += nt
        objs[p["name"]] = (o, p)
        print(f"OBJ {p['name']}: {nt} тр., {time.time() - t:.1f} с", flush=True)
    # копии (патроны в ленте и т. п.): общая сетка, своя матрица (16 чисел по строкам, сдвиг в мм)
    for name, (o, p) in list(objs.items()):
        for inst in p.get("instances", []):
            c = bpy.data.objects.new(inst["name"], o.data)
            collection(inst.get("coll", p.get("coll", "Прочее")), top).objects.link(c)
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
    if base:
        total += append_base(base, top, objs)
    ctrl = controls(objs, top)
    for name, (o, p) in objs.items():
        par = p.get("parent")
        if par and par in objs:
            set_parent(o, objs[par][0])
        else:
            set_parent(o, ctrl)
    # варианты (коробка на 200 и т. п.) — отдельные коллекции, выключенные по умолчанию
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
