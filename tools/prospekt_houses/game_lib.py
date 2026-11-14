"""Общие помощники игровых версий домов «Проспекта» (Blender, bpy). Дом 7 — первый; следующие дома серии берут то же.

Принцип: игровая сетка собирается тем же набором частей kit.py, что и форма, но в «игровом» режиме — без фасок, швы плит и
опалубка картами, шторы и комнаты за окнами — шейдером; затем:
  * cull_module()  — у модуля убираются невидимые грани: на границах пролёта (их закрывают соседи и ядро) и грани, целиком
                     спрятанные в соседних коробках того же модуля (по запомненным коробкам, а не лучами — коробки касаются);
  * realize()      — экземпляры коллекций → копии сеток в мировых координатах, с цветом вершин на экземпляр (номер окна,
                     вариант шторы, размер проёма — для шейдера окна), затем одна сетка на уровень детализации, поверхность
                     на материал;
  * box_uv()       — UV1 в метрах кубической проекцией в осях дома (как трипланарная проекция материалов v01 по миру);
  * atlas_uv()     — UV2: уникальная развёртка под атлас грязи;
  * bake_emission()— запекание узлов излучения в развёртку UV2 (маски грязи, AO).
Оси Blender: метры, Z вверх, фасад пролёта смотрит в −Y (как kit.py).
"""
import math
import zlib

import bpy
import bmesh
from mathutils import Vector, Matrix

EPS = 1e-3


# ---------------------------------------------------------------- отсечение невидимых граней
def _inside_any(p, boxes, tol=1e-4):
    for (x0, x1, y0, y1, z0, z1) in boxes:
        if x0 + tol < p.x < x1 - tol and y0 + tol < p.y < y1 - tol and z0 + tol < p.z < z1 - tol:
            return True
    return False


def _face_hidden(f, boxes, step=0.04):
    """Грань закрыта целиком: точки сетки по грани (шаг ≤ step, до 24 × 24) на 3 мм наружу все внутри коробок модуля.
    Пяти точек мало: лицо поля за каннелюрами с шагом 0,28 «закрыто» в центре и у углов, а между рёбрами видно."""
    vs = [v.co for v in f.verts]
    if len(vs) < 3:
        return False
    off = f.normal * 0.003
    a, b, d = vs[0], vs[1], vs[-1]
    e1, e2 = b - a, d - a
    n1 = max(2, min(24, int(math.ceil(e1.length / step)) + 1))
    n2 = max(2, min(24, int(math.ceil(e2.length / step)) + 1))
    quad = len(vs) == 4
    for i in range(n1):
        for j in range(n2):
            u, v = (i + 0.5) / n1, (j + 0.5) / n2
            if not quad and u + v > 1.0:
                continue
            p = a + e1 * u + e2 * v
            if not _inside_any(p + off, boxes):
                return False
    return True


def cull_module(ob, boxes, open_mats=(), bounds=None, cull_x=(True, True), cull_z=(True, True), cull_back=True):
    """Убирает невидимые грани модуля.
    boxes — коробки модуля (x0, x1, y0, y1, z0, z1): грань, у которой центр и четыре точки у углов (на 3 мм наружу) лежат внутри
    коробок, закрыта целиком. bounds = (w, depth, h): грани на плоскостях x = 0 / x = w, z = 0 / z = h и y = depth, смотрящие наружу,
    закрывают соседние пролёты и ядро дома. open_mats — материалы незамкнутых листов (стекло, перфорация): их не трогаем."""
    me = ob.data
    names = [m.name.split(".")[0] if m else "" for m in me.materials]
    bm = bmesh.new()
    bm.from_mesh(me)
    kill = []
    for f in bm.faces:
        if names[f.material_index] in open_mats:
            continue
        n = f.normal
        vs = [v.co for v in f.verts]
        if bounds:
            w, dep, h = bounds
            if cull_back and n.y > 0.9 and all(abs(v.y - dep) < EPS for v in vs):
                kill.append(f); continue
            if cull_x[0] and n.x < -0.9 and all(abs(v.x) < EPS for v in vs):
                kill.append(f); continue
            if cull_x[1] and n.x > 0.9 and all(abs(v.x - w) < EPS for v in vs):
                kill.append(f); continue
            if cull_z[0] and n.z < -0.9 and all(abs(v.z) < EPS for v in vs):
                kill.append(f); continue
            if cull_z[1] and n.z > 0.9 and all(abs(v.z - h) < EPS for v in vs):
                kill.append(f); continue
        if _face_hidden(f, boxes):
            kill.append(f)
    if kill:
        bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(me)
    bm.free()
    return len(kill)


def face_glass_outward(ob, mats, uv_rect=None, uv_mats=()):
    """Листы стекла смотрят наружу (−Y модуля); uv_rect = (x0, x1, z0, z1) — UV1 стекла 0…1 по всему проёму (шейдер окна:
    шторы по атласу и «комната» за стеклом), а не в метрах."""
    me = ob.data
    names = [m.name.split(".")[0] if m else "" for m in me.materials]
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")   # то же имя, что у box_uv (UV1 glTF)
    for f in bm.faces:
        if names[f.material_index] not in mats:
            continue
        if f.normal.y > 0:
            f.normal_flip()
        if uv_rect and names[f.material_index] in uv_mats:
            x0, x1, z0, z1 = uv_rect
            for l in f.loops:
                l[uvl].uv = ((l.vert.co.x - x0) / (x1 - x0), (l.vert.co.z - z0) / (z1 - z0))
    bm.to_mesh(me)
    bm.free()


# ---------------------------------------------------------------- экземпляры → одна сетка
def inst_seed(name):
    return (zlib.crc32(name.encode()) & 0xFFFFFF) / float(0xFFFFFF)


def realize(asm_col, out_name, color_of=None, extra=()):
    """Все экземпляры коллекции asm_col (и объекты extra) — в одну сетку out_name в мировых координатах.
    color_of(empty) → (r, g, b, a) — цвет вершин экземпляра (FLOAT_COLOR по углам граней)."""
    tmp = []
    bpy.context.view_layer.update()              # matrix_world экземпляров, созданных скриптом, иначе ещё единичные
    for e in list(asm_col.objects):
        if e.type != "EMPTY" or not e.instance_collection:
            continue
        for src in e.instance_collection.objects:
            if src.type != "MESH" or len(src.data.polygons) == 0:
                continue
            me = src.data.copy()
            me.transform(e.matrix_world @ src.matrix_world)
            if color_of:
                col = color_of(e)
                attr = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
                for d in attr.data:
                    d.color = col
            ob = bpy.data.objects.new(e.name + "_r", me)
            bpy.context.scene.collection.objects.link(ob)
            tmp.append(ob)
    for ob in extra:
        if ob.name not in bpy.context.scene.collection.objects:
            bpy.context.scene.collection.objects.link(ob)
        if color_of and not ob.data.color_attributes.get("Col"):
            attr = ob.data.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
            for d in attr.data:
                d.color = (0.0, 0.5, 0.0, 0.0)
        tmp.append(ob)
    bpy.ops.object.select_all(action="DESELECT")
    for ob in tmp:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = tmp[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = out_name
    ob.data.name = out_name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # одинаковые материалы с суффиксами .001 — в один слот
    merge_slots(ob)
    return ob


def merge_slots(ob):
    me = ob.data
    names = [m.name.split(".")[0] if m else "" for m in me.materials]
    uniq = []
    for n in names:
        if n not in uniq:
            uniq.append(n)
    remap = [uniq.index(n) for n in names]
    idx = [0] * len(me.polygons)
    me.polygons.foreach_get("material_index", idx)
    idx = [remap[i] for i in idx]
    mats = {}
    for m in me.materials:
        if m:
            mats.setdefault(m.name.split(".")[0], m)
    me.materials.clear()
    for n in uniq:
        me.materials.append(mats.get(n) or bpy.data.materials.get(n))
    me.polygons.foreach_set("material_index", idx)
    me.update()


def drop_faces(ob, pred):
    """Удалить грани по условию pred(центр, нормаль, имя материала)."""
    me = ob.data
    names = [m.name.split(".")[0] if m else "" for m in me.materials]
    bm = bmesh.new()
    bm.from_mesh(me)
    kill = [f for f in bm.faces if pred(f.calc_center_median(), f.normal, names[f.material_index])]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(me)
    bm.free()
    return len(kill)


def drop_material(ob, name):
    n = drop_faces(ob, lambda c, nrm, m: m == name)
    merge_slots_drop_unused(ob)
    return n


def merge_slots_drop_unused(ob):
    me = ob.data
    used = set(p.material_index for p in me.polygons)
    keep = [i for i in range(len(me.materials)) if i in used]
    remap = {i: k for k, i in enumerate(keep)}
    idx = [0] * len(me.polygons)
    me.polygons.foreach_get("material_index", idx)
    mats = [me.materials[i] for i in keep]
    me.materials.clear()
    for m in mats:
        me.materials.append(m)
    me.polygons.foreach_set("material_index", [remap[i] for i in idx])
    me.update()


def rename_material(ob, old, new):
    import kit
    me = ob.data
    for i, m in enumerate(me.materials):
        if m and m.name.split(".")[0] == old:
            me.materials[i] = kit.get_mat(new)


# ---------------------------------------------------------------- развёртки
def box_uv(ob, skip_mats=(), rotate_mats=(), layer="UVMap"):
    """UV1 в метрах: кубическая проекция по преобладающей оси нормали, без зеркал (u вдоль фасада слева направо, v вверх).
    rotate_mats — материалы с рисунком вдоль вертикали (рейки: волокна дерева вдоль рейки) — u и v меняются местами."""
    me = ob.data
    names = [m.name.split(".")[0] if m else "" for m in me.materials]
    if layer not in me.uv_layers:
        me.uv_layers.new(name=layer)
    me.uv_layers.active = me.uv_layers[layer]
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv[layer]
    for f in bm.faces:
        mn = names[f.material_index]
        if mn in skip_mats:
            continue
        n = f.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for l in f.loops:
            p = l.vert.co
            if az >= ax and az >= ay:
                u, v = p.x, (p.y if n.z > 0 else -p.y)
            elif ax >= ay:
                u, v = (p.y if n.x > 0 else -p.y), p.z
            else:
                u, v = (-p.x if n.y > 0 else p.x), p.z
            if mn in rotate_mats and az < 0.7:
                u, v = v, -u
            l[uvl].uv = (u, v)
    bm.to_mesh(me)
    bm.free()


NEUTRAL_UV = (0.9985, 0.9985)        # клетка атласа под мелочь без своей грязи (рамы, сталь, цепь, стекло)


def atlas_uv(ob, layer="UV2", margin=0.0008, angle=66.0, only_mats=None, min_edge=0.12):
    """UV2: уникальная развёртка дома (Smart UV по осям, острова в масштабе) — под атлас грязи.
    only_mats — материалы со своей грязью (стены, бетон, панели); остальным грани UV2 сводятся в угловую клетку NEUTRAL_UV
    (после запекания её заливают средними значениями) — иначе тысячи островков рам съедают атлас отступами."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0003)   # стыки коробок одного фасада — общие вершины
    bm.to_mesh(me)
    bm.free()
    if layer not in me.uv_layers:
        me.uv_layers.new(name=layer)
    keep = me.uv_layers.active.name
    me.uv_layers.active = me.uv_layers[layer]
    names = [m.name.split(".")[0] if m else "" for m in me.materials]
    # узкие грани (бока каннелюр, торцы стенок уже ~2 текселей атласа) — тоже в угловую клетку: свой остров у них
    # меньше текселя, и запечённое AO по нему — чёрная полоса
    def wide(p):
        vs = [me.vertices[i].co for i in p.vertices]
        ed = [(vs[k] - vs[k - 1]).length for k in range(len(vs))]
        return min(ed) >= min_edge
    sel = [(only_mats is None or names[p.material_index] in only_mats) and wide(p) for p in me.polygons]
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    me.polygons.foreach_set("select", sel)
    me.update()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    uv = me.uv_layers[layer].data
    for p, s in zip(me.polygons, sel):
        for i in p.loop_indices:
            if s:
                uv[i].uv = uv[i].uv * 0.994          # полоса у верхнего и правого края — под угловую клетку
            else:
                uv[i].uv = NEUTRAL_UV
    me.uv_layers.active = me.uv_layers[keep]


def uv_fill(ob, layer):
    """Доля площади UV-квадрата, занятая островами (оценка по сумме площадей треугольников UV)."""
    me = ob.data
    uv = me.uv_layers[layer].data
    s = 0.0
    for p in me.polygons:
        pts = [uv[i].uv for i in p.loop_indices]
        for k in range(1, len(pts) - 1):
            a, b, c = pts[0], pts[k], pts[k + 1]
            s += abs((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)) * 0.5
    return s


def tris(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def tris_by_material(ob):
    me = ob.data
    names = [m.name.split(".")[0] if m else "" for m in me.materials]
    out = {}
    for p in me.polygons:
        k = names[p.material_index]
        out[k] = out.get(k, 0) + len(p.vertices) - 2
    return out


# ---------------------------------------------------------------- запекание в UV2
def bake_emission(ob, image, uv_layer, build_tree, samples=16, margin=6):
    """Запекает излучение узлов build_tree(NT) → цвет в развёртку uv_layer объекта ob (все слоты временно — один материал)."""
    import materials as MT
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    mat = bpy.data.materials.new("bake_tmp")
    N = MT.NT(mat)
    col = build_tree(N)
    em = N.node("ShaderNodeEmission")
    N.put(em.inputs[0], col)
    N.l.new(em.outputs[0], N.out.inputs[0])
    tex = N.node("ShaderNodeTexImage", image=image)
    N.n.active = tex
    me = ob.data
    saved = [s.material for s in ob.material_slots]
    for s in ob.material_slots:
        s.material = mat
    keep = me.uv_layers.active.name
    me.uv_layers.active = me.uv_layers[uv_layer]
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.bake(type="EMIT", margin=margin, use_clear=True)
    for s, m in zip(ob.material_slots, saved):
        s.material = m
    me.uv_layers.active = me.uv_layers[keep]
    bpy.data.materials.remove(mat)


def new_image(name, size, alpha=False, non_color=True):
    im = bpy.data.images.new(name, size, size, alpha=alpha, float_buffer=False)
    if non_color:
        im.colorspace_settings.name = "Non-Color"
    return im
