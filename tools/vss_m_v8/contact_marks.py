# ВСС-М v8: следы рук и жизни по местам — маски владельца (E:/Models Blender/Маски_АЛЬФА) проецируются декалями туда,
# где оружие берут, нажимают, смазывают и где оно коптит, и запекаются в развёртку каждого набора текстур Painter
# отдельными картами по видам: prints (пальцы), palms (ладони), oil (масло, жирные пятна у крепежа), soot (копоть),
# wipe (протирки). В Painter (sp_stacks.contact_marks) каждый вид — свой слой со своим блеском.
# blender --background --factory-startup _asset_src/vss_m_v8/VSS_M_v8_sp.blend --python-exit-code 1 \
#   --python tools/vss_m_v8/contact_marks.py -- <папка вывода> [размер]
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
import sp_export  # noqa: E402

MASKS = "E:/Models Blender/Маски_АЛЬФА/"
P = "01_Отпечатки_пальцев/"
H = "02_Отпечатки_ладоней/"
O = "20_Масляные_плёнки_и_смазка/"
S = "21_Копоть_и_дымовой_налёт/"
W = "06_Разводы_и_следы_протирания/"
KINDS = ("prints", "palms", "oil", "soot", "wipe")

_A = math.atan2(42.0 - 11.3, 298.0 - 272.0)
SLOPE_N = (-math.sin(_A), 0.0, math.cos(_A))          # нормаль заднего скоса крышки (фиксатор)
SLOPE_C = (272.0 + (27.0 - 11.3) / math.tan(_A), 0.0, 27.0)

# (вид, деталь, точка мм в исходном положении, нормаль, поворот°, размер мм, маска)
MARKS = [
    # пальцы: органы управления и места, где перехватывают
    ("prints", "Charging_handle", (474.5, -32.0, 9.6), (0, 0, 1), 55, 16, P + "Отпечаток_смазанный_вправо_01.png"),
    ("prints", "Safety_lever", (400.5, -25.6, 0.5), (0, -1, 0), -15, 18, P + "Отпечаток_чёткий_01.png"),
    ("prints", "Trigger", (381.5, 0.0, -29.0), (1, 0, 0), 90, 14, P + "Отпечаток_грязный_02.png"),
    ("prints", "Fire_selector", (360.0, 0.25, -38.0), (0, 1, 0), 0, 10, P + "Отпечаток_смазанный_вниз_01.png"),
    ("prints", "Fire_selector", (360.0, -4.25, -38.0), (0, -1, 0), 180, 10, P + "Отпечаток_растёртый_01.png"),
    ("prints", "Magazine_catch", (406.0, 0.0, -58.0), (-1, 0, 0), 90, 14, P + "Отпечаток_смазанный_вниз_01.png"),
    ("prints", "Cover_latch_button", tuple(c + 2.0 * n for c, n in zip(SLOPE_C, SLOPE_N)), SLOPE_N, 90, 13,
     P + "Отпечаток_чёткий_01.png"),
    ("prints", "Stock_release_button", (271.0, 0.0, 16.0), (0, 0, 1), 20, 13, P + "Отпечаток_грязный_01.png"),
    ("prints", "Receiver_lower", (428.0, -18.4, -3.0), (0, -1, 0), 10, 34, P + "Отпечаток_смазанный_по_диагонали_01.png"),
    ("prints", "Receiver_lower", (330.0, -18.4, -6.0), (0, -1, 0), -30, 30, P + "Отпечаток_растёртый_01.png"),
    ("prints", "Receiver_lower", (335.0, 18.4, -8.0), (0, 1, 0), 60, 30, P + "Отпечаток_грязный_01.png"),
    ("prints", "Receiver_cover", (365.0, 19.2, 27.0), (0, 1, 0), 160, 40, P + "Отпечаток_смазанный_вправо_02.png"),
    ("prints", "Trigger_guard", (378.0, 0.0, -50.9), (0, 0, -1), 0, 24, P + "Отпечаток_смазанный_вправо_03.png"),
    ("prints", "Rail_sleeve", (628.0, 27.5, 6.0), (0, 1, 0), -100, 36, P + "Отпечаток_смазанный_по_диагонали_02.png"),
    ("prints", "Handguard", (530.0, 20.1, 14.0), (0, 1, 0), -80, 46, P + "Отпечаток_грязный_03.png"),
    ("prints", "Handguard", (512.0, 0.0, 49.2), (0, 0, 1), 10, 32, P + "Отпечаток_растёртый_01.png"),
    ("prints", "Magazine_10", (455.0, -15.4, -48.0), (0, -1, 0), 100, 34, P + "Отпечаток_смазанный_вниз_01.png"),
    ("prints", "Magazine_10", (450.0, 15.4, -44.0), (0, 1, 0), -70, 30, P + "Отпечаток_грязный_02.png"),
    ("prints", "Magazine_20", (456.0, -15.4, -60.0), (0, -1, 0), 80, 34, P + "Отпечаток_смазанный_вправо_01.png"),
    ("prints", "Magazine_20", (452.0, 15.4, -95.0), (0, 1, 0), 120, 34, P + "Отпечаток_чёткий_01.png"),
    ("prints", "Magazine_30", (454.0, -15.4, -80.0), (0, -1, 0), 60, 34, P + "Отпечаток_грязный_03.png"),
    ("prints", "Wood_stock_v8", (338.0, 17.1, -38.0), (0, 1, 0), 40, 22, P + "Отпечаток_смазанный_по_диагонали_01.png"),
    ("prints", "Suppressor_body", (800.0, 0.0, 30.4), (0, 0, 1), 30, 34, P + "Отпечаток_смазанный_по_диагонали_01.png"),
    ("prints", "Suppressor_body", (760.0, -20.4, 10.0), (0, -1, 0), 80, 30, P + "Отпечаток_грязный_01.png"),
    # ладони: рукоятка (правая рука), щека на гребне, цевьё и магазин (левая), накатка глушителя (снимают и ставят
    # глушитель — крутят рукой), бок крышки (несут за коробку)
    ("palms", "Wood_stock_v8", (330.0, -17.1, -72.0), (0, -1, 0), 100, 70, H + "Ладонь_грязная_01.png"),
    ("palms", "Wood_stock_v8", (330.0, 17.1, -70.0), (0, 1, 0), -80, 60, H + "Ладонь_частичная_01.png"),
    ("palms", "Wood_stock_v8", (205.0, 17.1, -2.0), (0, 1, 0), 0, 70, H + "Ладонь_растёртая_01.png"),
    # цевьё: вместо ладони (выглядела детской) — беспорядочные отпечатки пальцев по нижней половине (владелец 26.10)
    ("prints", "Handguard", (495.0, -19.9, 0.0), (0, -1, 0), 70, 22, P + "Отпечаток_грязный_01.png"),
    ("prints", "Handguard", (520.0, -19.9, -12.0), (0, -1, 0), 100, 20, P + "Отпечаток_смазанный_вниз_01.png"),
    ("prints", "Handguard", (548.0, -19.9, -4.0), (0, -1, 0), 60, 22, P + "Отпечаток_смазанный_по_диагонали_01.png"),
    ("prints", "Handguard", (505.0, 19.9, -10.0), (0, 1, 0), -70, 22, P + "Отпечаток_грязный_02.png"),
    ("prints", "Handguard", (540.0, 19.9, 4.0), (0, 1, 0), -110, 20, P + "Отпечаток_смазанный_вправо_02.png"),
    ("prints", "Handguard", (515.0, 0.0, -25.9), (0, 0, -1), 30, 22, P + "Отпечаток_растёртый_01.png"),
    ("prints", "Handguard", (550.0, 4.0, -25.9), (0, 0, -1), -20, 20, P + "Отпечаток_смазанный_вправо_03.png"),
    ("palms", "Rail_sleeve", (612.0, -27.5, 10.0), (0, -1, 0), 75, 50, H + "Ладонь_частичная_01.png"),
    ("palms", "Magazine_10", (462.0, -15.4, -75.0), (0, -1, 0), 0, 60, H + "Ладонь_частичная_01.png"),
    ("palms", "Suppressor_knurl", (780.0, 0.0, 30.2), (0, 0, 1), 90, 90, H + "Ладонь_смазанная_вправо_01.png"),
    ("palms", "Suppressor_knurl", (770.0, -20.2, 10.0), (0, -1, 0), 85, 80, H + "Ладонь_частичная_01.png"),
    ("palms", "Receiver_cover", (420.0, 19.2, 25.0), (0, 1, 0), 90, 90, H + "Ладонь_растёртая_01.png"),
    # масло: у окна и паза рукоятки, рама и затвор за окном, вкладыш, вокруг штифтов и винтов, муфта глушителя
    ("oil", "Receiver_lower", (440.0, -18.4, 3.0), (0, -1, 0), 0, 40, O + "Масло_08_Рваный_мазок.png"),
    ("oil", "Receiver_lower", (398.0, -18.4, 4.0), (0, -1, 0), 0, 25, O + "Масло_06_Нити_смазки.png"),
    ("oil", "Bolt_carrier", (440.0, -13.4, 10.0), (0, -1, 0), 0, 50, O + "Масло_04_Пятнистая_плёнка.png"),
    ("oil", "Bolt", (474.0, -7.0, 10.0), (0, -1, 0), 0, 25, O + "Масло_03_Густая_смазка.png"),
    ("oil", "Receiver_trunnion", (470.0, -14.4, 0.0), (0, -1, 0), 0, 20, O + "Масло_05_Капля_размазанная.png"),
    ("oil", "Suppressor_body", (575.0, 0.0, 20.4), (0, 0, 1), 0, 30, O + "Масло_10_Смешанный_перенос.png"),
    ("oil", "Wood_stock_v8", (300.0, -17.1, -36.0), (0, -1, 0), 30, 16, O + "Масло_09_Сухие_островки.png"),
    ("oil", "Wood_stock_v8", (300.0, 17.1, -36.0), (0, 1, 0), -40, 16, O + "Масло_09_Сухие_островки.png"),
] + [
    ("oil", "Receiver_lower", (x, -18.2, z), (0, -1, 0), 37 * i, 12, O + "Масло_07_Полупрозрачные_пятна.png")
    for i, (x, z) in enumerate(((300.0, -18.0), (330.0, -18.0), (440.0, -6.0), (465.0, -8.0), (409.0, -38.0)))
] + [
    # копоть: дульный срез и кольцо у него (газы), окно выброса
    ("soot", "Suppressor_body", (894.5, 0.0, 10.0), (1, 0, 0), 0, 44, S + "Копоть_04_Растёртая_копоть.png"),
    ("soot", "Suppressor_body", (884.0, 0.0, 30.6), (0, 0, 1), 0, 40, S + "Копоть_05_Дымовая_вуаль.png"),
    ("soot", "Suppressor_body", (884.0, -20.6, 10.0), (0, -1, 0), 0, 40, S + "Копоть_10_Слабый_остаток.png"),
    ("soot", "Receiver_lower", (452.0, -18.4, 10.0), (0, -1, 0), 0, 45, S + "Копоть_10_Слабый_остаток.png"),
    ("soot", "Receiver_cover", (452.0, -19.0, 10.0), (0, -1, 0), 0, 45, S + "Копоть_10_Слабый_остаток.png"),
    ("soot", "Bolt_carrier", (455.0, -13.4, 8.0), (0, -1, 0), 0, 35, S + "Копоть_02_Сухие_частицы.png"),
    # протирки: бока крышки, глушитель, верх цевья
    ("wipe", "Receiver_cover", (380.0, -19.0, 25.0), (0, -1, 0), 0, 120, W + "Протирание_по_диагонали_01.png"),
    ("wipe", "Receiver_cover", (380.0, 19.0, 25.0), (0, 1, 0), 180, 120, W + "Протирание_по_диагонали_01.png"),
    ("wipe", "Suppressor_body", (740.0, 0.0, 20.0), (0, 0, 1), 0, 120, W + "Разводы_редкие_01.png"),
    ("wipe", "Handguard", (525.0, 0.0, 49.0), (0, 0, 1), 0, 80, W + "Протирание_дугами_с_грязью_01.png"),
]


def decal_empty(i, parent, pos, nrm, rot, size):
    par = bpy.data.objects[parent]
    e = bpy.data.objects.new(f"_mark_{i:02d}", None)
    bpy.context.scene.collection.objects.link(e)
    n = Vector(nrm).normalized()
    q = Vector((0, 0, 1)).rotation_difference(n)
    m = q.to_matrix().to_4x4() @ Matrix.Rotation(math.radians(rot), 4, "Z")
    h = size * 0.0005
    depth = max(2.5, size * 0.3) * 0.001
    local = Matrix.Translation(Vector(pos) * 0.001) @ m @ Matrix.Diagonal((h, h, depth, 1.0))
    bpy.context.view_layer.update()
    # точка задана в координатах детали в исходном положении (как в tex_v8.make_decals)
    e.matrix_world = par.matrix_world @ local
    world_n = (par.matrix_world.to_3x3() @ n).normalized()
    return e, world_n


def build_material(name, decals):
    """Маска вида: максимум по декалям; у каждой — картинка в своём квадрате, затухание по глубине и по углу
    к нормали декали (чтобы не проступала на обороте и боковинах)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    L = nt.links
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    L.new(emit.outputs[0], out.inputs["Surface"])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    acc = None
    for e, wn, img in decals:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        tc.object = e
        uv = nt.nodes.new("ShaderNodeVectorMath")
        uv.operation = "MULTIPLY_ADD"
        L.new(tc.outputs["Object"], uv.inputs[0])
        uv.inputs[1].default_value = (0.5, 0.5, 0.0)
        uv.inputs[2].default_value = (0.5, 0.5, 0.0)
        tx = nt.nodes.new("ShaderNodeTexImage")
        tx.image = img
        tx.extension = "CLIP"
        L.new(uv.outputs[0], tx.inputs["Vector"])
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        L.new(tx.outputs["Color"], bw.inputs[0])
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        L.new(tc.outputs["Object"], sep.inputs[0])
        az = nt.nodes.new("ShaderNodeMath"); az.operation = "ABSOLUTE"
        L.new(sep.outputs["Z"], az.inputs[0])
        fz = nt.nodes.new("ShaderNodeMapRange")
        L.new(az.outputs[0], fz.inputs["Value"])
        fz.inputs["From Min"].default_value = 0.6
        fz.inputs["From Max"].default_value = 1.0
        fz.inputs["To Min"].default_value = 1.0
        fz.inputs["To Max"].default_value = 0.0
        dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = "DOT_PRODUCT"
        L.new(geo.outputs["Normal"], dot.inputs[0])
        dot.inputs[1].default_value = tuple(wn)
        fn = nt.nodes.new("ShaderNodeMapRange")
        L.new(dot.outputs["Value"], fn.inputs["Value"])
        fn.inputs["From Min"].default_value = 0.15
        fn.inputs["From Max"].default_value = 0.45
        m1 = nt.nodes.new("ShaderNodeMath"); m1.operation = "MULTIPLY"
        L.new(bw.outputs[0], m1.inputs[0]); L.new(fz.outputs["Result"], m1.inputs[1])
        m2 = nt.nodes.new("ShaderNodeMath"); m2.operation = "MULTIPLY"
        L.new(m1.outputs[0], m2.inputs[0]); L.new(fn.outputs["Result"], m2.inputs[1])
        if acc is None:
            acc = m2.outputs[0]
        else:
            mx = nt.nodes.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
            L.new(acc, mx.inputs[0]); L.new(m2.outputs[0], mx.inputs[1])
            acc = mx.outputs[0]
    L.new(acc, emit.inputs["Color"])
    return m


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out_dir = a[0]
    size = int(a[1]) if len(a) > 1 else 2048
    os.makedirs(out_dir, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 1
    sc.render.bake.margin = 8
    ctrl = bpy.data.objects.get("VSS_Controls")
    if ctrl:
        for k in list(ctrl.keys()):
            if not k.startswith("_"):
                ctrl[k] = 0.0
    bpy.context.view_layer.update()
    sets = ["receiver"] + list(sp_export.PARTS)
    owner = {}
    for g in sets:
        for o in sp_export.group_objects(g):
            owner[o.name] = g
    images = {}
    marks = {}
    for i, (kind, parent, pos, nrm, rot, size_mm, path) in enumerate(MARKS):
        if parent not in bpy.data.objects or parent not in owner:
            print("NO MARK TARGET", parent)
            continue
        e, wn = decal_empty(i, parent, pos, nrm, rot, size_mm)
        if path not in images:
            images[path] = bpy.data.images.load(MASKS + path, check_existing=True)
            images[path].colorspace_settings.name = "Non-Color"
        marks.setdefault((owner[parent], kind), []).append((e, wn, images[path]))
    bpy.context.view_layer.update()
    for (g, kind), decals in sorted(marks.items()):
        objs = sp_export.group_objects(g)
        img = bpy.data.images.new(f"{g}_{kind}", size, size, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        img.generated_color = (0, 0, 0, 1)
        mat = build_material(f"_marks_{g}_{kind}", decals)
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = img
        mat.node_tree.nodes.active = tex
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.data.materials.clear()
            o.data.materials.append(mat)
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.bake(type="EMIT")
        path = os.path.join(out_dir, f"{g}_{kind}.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        print("MARKS", g, kind, len(decals), path)


main()
