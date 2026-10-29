# AR-15 «ГРАНЬ-15»: маркировка этапа 1 текстур — только вымышленная (навык weapon-asset-texturing): название
# «ГРАНЬ-15» (владелец), вымышленный завод «ТВЕРДЬ» со своим знаком (шестигранник с гранью), вымышленный номер,
# калибр и положения переводчика. В геометрии надписей нет (lib.MARKINGS_GEOMETRY = False) — здесь они плоскими
# сетками ложатся на поверхность и запекаются маской в развёртку набора текстур; в Painter маска даёт углубление
# (лазер по анодированию / Cerakote) или выпуклость (литьё полимера) и цвет. Места — asset-state.md, «Места надписей».
# Шрифт — DejaVu Sans Mono из поставки Blender (свободная лицензия, есть кириллица; Arial для продажи модели не берём).
#   preview <папка> — крупные снимки мест с надписями поверх модели (проверка положения)
#   bake            — маски <WORK>/marks/<набор>_marks.png (белое — надпись) по развёртке
# blender --background <AR15_uv_v01.blend> --factory-startup --python-exit-code 1 --python tools/ar15/tex_marks.py -- preview|bake [...]
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
import tex_sets as T  # noqa: E402

MM = 0.001
NAME = "ГРАНЬ-15"
MAKER = "ТВЕРДЬ"                 # вымышленный завод
SERIAL = "SN 24-0731"            # вымышленный номер (как в v02)
CALIBER = "CAL 5.56 NATO"
CAP = 0.73                       # высота прописной DejaVu Sans Mono от кегля
LOGO = "@logo"

SEL_X, SEL_Z = -129.9, -26.2     # ось переводчика (lib.SELECTOR)

# место: набор, деталь, точка (мм, оси винтовки), нормаль наружу, «вверх» текста, строки (текст, высота мм, сдвиг
# вдоль / поперёк строки мм), вид («laser» — врезано, «mold» — выпукло литьём)
MARKS = [
    # нижний слева, панель шахты: верх панели закрыт рычагом двусторонней защёлки (v06) — строки ниже него
    dict(set="lower", target="Lower_receiver", at=(-22.3, 20.0, -36.0), n=(0, 1, 0), up=(0, 0, 1), kind="laser",
         lines=[(NAME, 3.4, 0.0, 0.0), (CALIBER, 1.9, 0.0, -4.6), (SERIAL, 1.9, 0.0, -8.4)]),
    # нижний справа, панель шахты: знак завода
    dict(set="lower", target="Lower_receiver", at=(-22.3, -20.0, -36.0), n=(0, -1, 0), up=(0, 0, 1), kind="laser",
         lines=[(LOGO, 9.0, 0.0, 3.0), (MAKER, 2.6, 0.0, -5.0)]),
    # положения переводчика: флажок вперёд — предохранитель, вверх — одиночный, назад — автоматический; SAFE и AUTO
    # за концом флажка (слева флажок 14.5 мм от оси, справа 9.5), SEMI спереди сверху: над флажком — край верхнего
    # ресивера (слева) и головка оси автоспуска (справа)
    dict(set="lower", target="Lower_receiver", at=(SEL_X, 20.0, SEL_Z), n=(0, 1, 0), up=(0, 0, 1), kind="laser",
         lines=[("SAFE", 2.0, -18.5, 0.0), ("SEMI", 1.8, -8.5, 12.5), ("AUTO", 2.0, 18.5, 0.0)]),
    dict(set="lower", target="Lower_receiver", at=(SEL_X, -20.0, SEL_Z), n=(0, -1, 0), up=(0, 0, 1), kind="laser",
         lines=[("SAFE", 2.0, 15.0, 0.0), ("SEMI", 1.8, 7.5, 13.0), ("AUTO", 2.0, -15.0, 0.0)]),
    # верхний слева, между приливами (x −71…−31), ниже изгиба «трубы»
    dict(set="upper", target="Upper_receiver", at=(-50.0, 20.0, 4.0), n=(0, 1, 0), up=(0, 0, 1), kind="laser",
         lines=[(NAME, 4.6, 0.0, 0.0)]),
    # цевьё, задние боковые грани с обеих сторон — знак и марка
    dict(set="handguard", target="Handguard", at=(36.0, 25.0, 0.5), n=(0, 1, 0), up=(0, 0, 1), kind="laser",
         lines=[(LOGO, 7.0, -9.0, 0.0), ("ГРАНЬ", 3.2, 6.0, 0.0)]),
    dict(set="handguard", target="Handguard", at=(36.0, -25.0, 0.5), n=(0, -1, 0), up=(0, 0, 1), kind="laser",
         lines=[(LOGO, 7.0, 9.0, 0.0), ("ГРАНЬ", 3.2, -6.0, 0.0)]),
    # приклад: ровный бок верхней балки у задней стойки (на стойке — гнездо QD и прорези) — знак литьём
    dict(set="stock", target="Stock_body", at=(-333.0, 25.0, 2.5), n=(0, 1, 0), up=(0, 0, 1), kind="mold",
         lines=[(LOGO, 12.0, 0.0, 0.0)]),
    dict(set="stock", target="Stock_body", at=(-333.0, -25.0, 2.5), n=(0, -1, 0), up=(0, 0, 1), kind="mold",
         lines=[(LOGO, 12.0, 0.0, 0.0)]),
    # магазин: левый бок под шахтой, между ребром и рифлением (верх магазина в шахте) — калибр и ёмкость; донце —
    # знак и завод; литьём
    dict(set="magazine", target="Magazine_body", at=(-9.0, 20.0, -84.8), n=(0, 1, 0), up=(0, 0, 1), kind="mold",
         lines=[("5,56×45  30", 2.2, 0.0, 0.0)]),
    dict(set="magazine", target="Magazine_floorplate", at=(4.6, 0.0, -205.0), n=(0, 0, -1), up=(0, -1, 0),
         kind="mold", lines=[(LOGO, 7.0, -8.0, 0.0), (MAKER, 3.0, 5.0, 0.0)]),
    # глушитель (лежит в стороне, ось x 180…352, z −112): вдоль трубы слева, лазер по Cerakote
    dict(set="suppressor", target="Suppressor_body", at=(266.0, 25.0, -112.0), n=(0, 1, 0), up=(0, 0, 1),
         kind="laser", lines=[(LOGO, 6.0, -26.0, 0.0), ("ГРАНЬ · " + MAKER, 2.8, 2.0, 2.0),
                              ("5.56×45  " + SERIAL, 2.0, 2.0, -2.2)]),
]


def font():
    f = bpy.data.fonts.get("MarkFont")
    if f is None:
        path = os.path.join(bpy.utils.system_resource("DATAFILES"), "fonts", "DejaVuSansMono.woff2")
        f = bpy.data.fonts.load(path)
        f.name = "MarkFont"
    return f


def text_mesh(text, h_mm):
    cu = bpy.data.curves.new("_mark", "FONT")
    cu.body = text
    cu.font = font()
    cu.size = h_mm / CAP * MM
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.fill_mode = "BOTH"
    cu.resolution_u = 6
    o = bpy.data.objects.new("_mark", cu)
    bpy.context.scene.collection.objects.link(o)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.curves.remove(cu)
    return me


def logo_mesh(h_mm):
    """Знак завода: шестигранник-контур (вершиной вверх) с гранью — правая нижняя половина залита (как срез камня)."""
    r = h_mm / 2 * MM
    w = 0.12 * h_mm * MM
    bm = bmesh.new()
    outer = [Vector((r * math.sin(math.radians(60 * i)), r * math.cos(math.radians(60 * i)), 0)) for i in range(6)]
    inner = [p * ((r - w) / r) for p in outer]
    vo = [bm.verts.new(p) for p in outer]
    vi = [bm.verts.new(p) for p in inner]
    for i in range(6):
        j = (i + 1) % 6
        bm.faces.new((vo[i], vo[j], vi[j], vi[i]))
    # грань: от верхней правой вершины к нижней левой — залита правая нижняя часть с зазором от контура
    g = 0.22 * h_mm * MM
    k = (r - w - g) / (r - w)
    tri = [inner[1] * k, inner[2] * k, inner[3] * k, inner[4] * k]
    vt = [bm.verts.new(p) for p in tri]
    bm.faces.new(vt)
    me = bpy.data.meshes.new("_logo")
    bm.to_mesh(me)
    bm.free()
    return me


def world_bvh(o):
    dg = bpy.context.evaluated_depsgraph_get()
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    mw = o.matrix_world
    verts = [mw @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    oe.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def place(m, bvh):
    """Сетки строк места m на поверхности детали: луч снаружи по нормали — точка, плоскость надписи на 0.05 мм выше."""
    n = Vector(m["n"]).normalized()
    up = Vector(m["up"]).normalized()
    right = up.cross(n)
    out = []
    for text, h, du, dv in m["lines"]:
        c = Vector(m["at"]) * MM + right * (du * MM) + up * (dv * MM)
        hit = bvh.ray_cast(c + n * 0.03, -n, 0.06)
        if hit[0] is None:
            print("MISS", m["target"], text)
            continue
        # плоскость строки — касательная к поверхности в точке попадания (на «трубе» ресивера и глушителе)
        sn = hit[1].normalized()
        if sn.dot(n) < 0:
            sn = -sn
        su = (up - sn * sn.dot(up)).normalized()
        sr = su.cross(sn)
        me = logo_mesh(h) if text == LOGO else text_mesh(text, h)
        mat = Matrix((sr, su, sn)).transposed().to_4x4()
        mat.translation = hit[0] + sn * 0.00005
        me.transform(mat)
        o = bpy.data.objects.new("MARK_" + text, me)
        bpy.context.scene.collection.objects.link(o)
        o["mark_set"] = m["set"]
        o["mark_target"] = m["target"]
        out.append((o, hit[0], n))
    return out


def build():
    bvhs = {}
    marks = []
    for m in MARKS:
        if m["target"] not in bvhs:
            bvhs[m["target"]] = world_bvh(bpy.data.objects[m["target"]])
        marks += [(m, *x) for x in place(m, bvhs[m["target"]])]
    return marks


def preview(folder):
    """Снимки Workbench: деталь серым, надписи красным, камера по нормали места."""
    os.makedirs(folder, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "OBJECT"
    sc.display.shading.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = 1200, 800
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.color = (0.55, 0.55, 0.57, 1)
    marks = build()
    for o, *_ in [(x[1], ) for x in marks]:
        o.color = (0.9, 0.1, 0.05, 1)
    cd = bpy.data.cameras.new("PrevCam")
    cam = bpy.data.objects.new("PrevCam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cd.type = "ORTHO"
    done = set()
    for i, m in enumerate(MARKS):
        n = Vector(m["n"]).normalized()
        c = Vector(m["at"]) * MM
        cam.location = c + n * 0.25
        cam.rotation_euler = (-n).to_track_quat("-Z", "Y").to_euler()
        cd.ortho_scale = 0.07
        cd.clip_start = 0.01
        sc.render.filepath = os.path.join(folder, f"mark_{i:02d}_{m['set']}.png")
        bpy.ops.render.render(write_still=True)
        done.add(sc.render.filepath)
    print("PREVIEW", len(done))


def bake():
    """Маска надписей в развёртку набора: Cycles, излучение надписей «выбранное → активное», луч из поверхности
    детали наружу; изображение набора общее для всех деталей набора (без очистки между деталями)."""
    out_dir = T.WORK + "/marks"
    os.makedirs(out_dir, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 16
    marks = build()
    emit = bpy.data.materials.new("MarkEmit")
    emit.use_nodes = True
    nt = emit.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs[0])
    for o, *_ in [(x[1],) for x in marks]:
        o.data.materials.clear()
        o.data.materials.append(emit)
    sets = sorted({m["set"] for m in MARKS})
    for s in sets:
        res = T.SETS[s][0]
        img = bpy.data.images.new(f"marks_{s}", res, res, alpha=False, float_buffer=False)
        img.colorspace_settings.name = "Non-Color"
        img.generated_color = (0, 0, 0, 1)
        tmat = bpy.data.materials.new(f"BakeTarget_{s}")
        tmat.use_nodes = True
        tn = tmat.node_tree.nodes.new("ShaderNodeTexImage")
        tn.image = img
        tmat.node_tree.nodes.active = tn
        targets = sorted({m["target"] for m in MARKS if m["set"] == s})
        for tname in targets:
            tgt = bpy.data.objects[tname]
            keep = list(tgt.data.materials)
            tgt.data.materials.clear()
            tgt.data.materials.append(tmat)
            bpy.ops.object.select_all(action="DESELECT")
            for x in marks:
                if x[0]["target"] == tname:
                    x[1].select_set(True)
            tgt.select_set(True)
            bpy.context.view_layer.objects.active = tgt
            bpy.ops.object.bake(type="EMIT", use_selected_to_active=True, cage_extrusion=0.0006,
                                max_ray_distance=0.0015, margin=3, margin_type="EXTEND", use_clear=False)
            tgt.data.materials.clear()
            for mm in keep:
                tgt.data.materials.append(mm)
            print("BAKED", s, tname)
        img.filepath_raw = f"{out_dir}/{s}_marks.png"
        img.file_format = "PNG"
        img.save()
        print("SAVED", img.filepath_raw)


# швы литья: линия разъёма формы — плоскость симметрии детали (y = 0 в осях детали); набор → детали
SEAMS = {"grip": ["Pistol_grip"], "stock": ["Stock_body"], "magazine": ["Magazine_body", "Magazine_floorplate"]}
SEAM_HALF_MM = 0.12          # полуширина линии: ~0.25 мм, как на образце (3DG Modeling, «Курс текстурирование рукоятки», ч. 2)


def seams():
    """Маска швов литья <WORK>/marks/<набор>_seams.png: запекание излучения 1 там, где |y| детали меньше полуширины
    линии (координаты объекта: детали симметричны относительно плоскости y = 0), в развёртку набора."""
    out_dir = T.WORK + "/marks"
    os.makedirs(out_dir, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 16
    for s, names in SEAMS.items():
        res = T.SETS[s][0]
        img = bpy.data.images.new(f"seams_{s}", res, res, alpha=False, float_buffer=False)
        img.colorspace_settings.name = "Non-Color"
        img.generated_color = (0, 0, 0, 1)
        m = bpy.data.materials.new(f"SeamBake_{s}")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(tc.outputs["Object"], sep.inputs[0])
        ab = nt.nodes.new("ShaderNodeMath")
        ab.operation = "ABSOLUTE"
        nt.links.new(sep.outputs["Y"], ab.inputs[0])
        lt = nt.nodes.new("ShaderNodeMath")
        lt.operation = "LESS_THAN"
        lt.inputs[1].default_value = SEAM_HALF_MM * MM
        nt.links.new(ab.outputs[0], lt.inputs[0])
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(lt.outputs[0], em.inputs["Strength"])
        o_ = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(em.outputs[0], o_.inputs[0])
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = img
        nt.nodes.active = tn
        for name in names:
            tgt = bpy.data.objects[name]
            keep = list(tgt.data.materials)
            tgt.data.materials.clear()
            tgt.data.materials.append(m)
            bpy.ops.object.select_all(action="DESELECT")
            tgt.select_set(True)
            bpy.context.view_layer.objects.active = tgt
            bpy.ops.object.bake(type="EMIT", margin=3, margin_type="EXTEND", use_clear=False)
            tgt.data.materials.clear()
            for mm in keep:
                tgt.data.materials.append(mm)
            print("SEAM", s, name)
        img.filepath_raw = f"{out_dir}/{s}_seams.png"
        img.file_format = "PNG"
        img.save()
        print("SAVED", img.filepath_raw)


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:]
    if a[0] == "preview":
        preview(a[1])
    elif a[0] == "bake":
        bake()
    elif a[0] == "seams":
        seams()
