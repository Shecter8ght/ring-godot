# ВСС-М v8: карты приклада для Substance Painter — клеёная фанера, как у приклада ВСС (образцы владельца с Fab):
# слои ~1.55 мм уложены по ширине приклада (по Y) и чередуются — светлый медовый шпон и тёмный серо-коричневый, у каждого
# свой тон; границы слоёв слегка волнистые, клеевые швы тёмные. Цвет считается по положению во всём объёме: на
# скруглениях, гребне и в окнах — контурные полосы срезанных слоёв; строго плоские боковины — светлый лицевой шпон
# (иначе на них проступали островки соседних слоёв там, где ширина приклада меняется). Волокно —
# фото Poly Haven «Plywood» (CC0) коробочной проекцией вдоль приклада. Вторая карта — рельеф: волокна и клеевые швы
# бороздками (для высоты и грязи в порах). Запекается излучением в развёртку приклада (sp_export.py).
# blender --background --factory-startup _asset_src/vss_m_v8/VSS_M_v8_sp.blend --python-exit-code 1 \
#   --python tools/vss_m_v8/wood_laminate_bake.py -- <цвет.png> <рельеф.png> [размер]
import sys
import bpy

PLYWOOD = "E:/Games/RING-godot/assets/textures/plywood/albedo.jpg"
LAYER_MM = 1.55
# линейные цвета: светлый медовый шпон, тёмный шпон, клеевой шов
C_LIGHT = (0.6, 0.34, 0.095, 1.0)
C_FACE = (0.62, 0.4, 0.1, 1.0)              # лицевой шпон боковин (жёлто-медовый)
# яркость фото фанеры: среднее ~0.4, разброс ±0.07 — волокно растягивается от этого диапазона, а не от 0…1
LUM_LO, LUM_HI = 0.27, 0.53
C_DARK = (0.17, 0.095, 0.04, 1.0)
C_GLUE = (0.04, 0.019, 0.008, 1.0)


def node(nt, kind, **kw):
    n = nt.nodes.new(kind)
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def math_node(nt, op, a, b=None):
    n = node(nt, "ShaderNodeMath", operation=op)
    for i, x in enumerate((a, b)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            nt.links.new(x, n.inputs[i])
    return n.outputs[0]


def map_range(nt, x, a0, a1, b0, b1, smooth=False):
    n = node(nt, "ShaderNodeMapRange")
    if smooth:
        n.interpolation_type = "SMOOTHSTEP"
    nt.links.new(x, n.inputs["Value"])
    n.inputs["From Min"].default_value = a0
    n.inputs["From Max"].default_value = a1
    n.inputs["To Min"].default_value = b0
    n.inputs["To Max"].default_value = b1
    return n.outputs["Result"]


def build_material(mode):
    m = bpy.data.materials.new("_wood_bake_" + mode)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    L = nt.links
    out = node(nt, "ShaderNodeOutputMaterial")
    emit = node(nt, "ShaderNodeEmission")
    L.new(emit.outputs[0], out.inputs["Surface"])
    geo = node(nt, "ShaderNodeNewGeometry")
    pos_mm = node(nt, "ShaderNodeVectorMath", operation="SCALE")
    L.new(geo.outputs["Position"], pos_mm.inputs[0])
    pos_mm.inputs["Scale"].default_value = 1000.0
    sep = node(nt, "ShaderNodeSeparateXYZ")
    L.new(pos_mm.outputs[0], sep.inputs[0])
    # волнистость слоёв: мелкая (кромки шпона) и плавный изгиб по длине
    wav = node(nt, "ShaderNodeTexNoise")
    wav.inputs["Scale"].default_value = 0.035
    wav.inputs["Detail"].default_value = 3.0
    L.new(pos_mm.outputs[0], wav.inputs["Vector"])
    bend = node(nt, "ShaderNodeTexNoise")
    bend.inputs["Scale"].default_value = 0.006
    bend.inputs["Detail"].default_value = 1.0
    L.new(pos_mm.outputs[0], bend.inputs["Vector"])
    t = math_node(nt, "MULTIPLY", sep.outputs["Y"], 1.0 / LAYER_MM)
    t = math_node(nt, "ADD", t, math_node(nt, "MULTIPLY", math_node(nt, "SUBTRACT", wav.outputs["Fac"], 0.5), 0.8))
    t = math_node(nt, "ADD", t, math_node(nt, "MULTIPLY", math_node(nt, "SUBTRACT", bend.outputs["Fac"], 0.5), 1.5))
    fr = math_node(nt, "FRACT", t)
    idx = math_node(nt, "FLOOR", t)
    parity = math_node(nt, "FLOORED_MODULO", idx, 2.0)
    glue = map_range(nt, fr, 0.9, 0.95, 0.0, 1.0, smooth=True)
    # волокно: фото фанеры, яркость → «волокно» вокруг единицы
    tc = node(nt, "ShaderNodeTexCoord")
    mp = node(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (3.2, 3.2, 3.2)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    img = node(nt, "ShaderNodeTexImage", projection="BOX", projection_blend=0.3)
    img.image = bpy.data.images.load(PLYWOOD, check_existing=True)
    img.image.colorspace_settings.name = "Non-Color"     # нужна только яркость волокна в значениях файла (sRGB 0…1)
    L.new(mp.outputs[0], img.inputs["Vector"])
    bw = node(nt, "ShaderNodeRGBToBW")
    L.new(img.outputs["Color"], bw.inputs[0])
    lum = bw.outputs[0]
    # лицевой шпон — где поверхность смотрит строго вбок
    nsep = node(nt, "ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Normal"], nsep.inputs[0])
    face = map_range(nt, math_node(nt, "ABSOLUTE", nsep.outputs["Y"]), 0.94, 0.985, 0.0, 1.0, smooth=True)
    if mode == "height":
        # рельеф: на шпоне боковин — волокно (светлое выше, тёмное — бороздки); на срезе слоёв волокно слабое,
        # бороздками идут клеевые швы (иначе на гребне рельеф волокна поперёк слоёв читался как кора)
        h_face = map_range(nt, lum, LUM_LO, LUM_HI, 0.15, 0.85)
        h_cut = math_node(nt, "SUBTRACT", map_range(nt, lum, LUM_LO, LUM_HI, 0.42, 0.58), math_node(nt, "MULTIPLY", glue, 0.3))
        hm = node(nt, "ShaderNodeMix", data_type="FLOAT")
        L.new(face, hm.inputs["Factor"])
        L.new(h_cut, hm.inputs[2])
        L.new(h_face, hm.inputs[3])
        L.new(hm.outputs[0], emit.inputs["Color"])
        return m
    wn = node(nt, "ShaderNodeTexWhiteNoise", noise_dimensions="1D")
    L.new(idx, wn.inputs["W"])
    lay = node(nt, "ShaderNodeMix", data_type="RGBA")
    L.new(parity, lay.inputs["Factor"])
    lay.inputs[6].default_value = C_LIGHT
    lay.inputs[7].default_value = C_DARK
    tone = map_range(nt, wn.outputs["Value"], 0.0, 1.0, 0.75, 1.15)
    grain = map_range(nt, lum, LUM_LO, LUM_HI, 0.5, 1.45)
    grain_cut = map_range(nt, lum, LUM_LO, LUM_HI, 0.82, 1.18)      # на срезе слоёв полосы важнее волокна
    k = math_node(nt, "MULTIPLY", tone, grain_cut)
    kk = node(nt, "ShaderNodeCombineColor")
    for i in range(3):
        L.new(k, kk.inputs[i])
    col = node(nt, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    col.inputs["Factor"].default_value = 1.0
    L.new(lay.outputs[2], col.inputs[6])
    L.new(kk.outputs[0], col.inputs[7])
    fin = node(nt, "ShaderNodeMix", data_type="RGBA")
    L.new(math_node(nt, "MULTIPLY", glue, 0.85), fin.inputs["Factor"])
    L.new(col.outputs[2], fin.inputs[6])
    fin.inputs[7].default_value = C_GLUE
    # лицевой шпон: светлый тон × волокно, крупные пятна тона по длине
    vt = map_range(nt, bend.outputs["Fac"], 0.3, 0.7, 0.88, 1.08)
    vk = node(nt, "ShaderNodeCombineColor")
    vg = math_node(nt, "MULTIPLY", grain, vt)
    for i in range(3):
        L.new(vg, vk.inputs[i])
    veneer = node(nt, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    veneer.inputs["Factor"].default_value = 1.0
    veneer.inputs[6].default_value = C_FACE
    L.new(vk.outputs[0], veneer.inputs[7])
    res = node(nt, "ShaderNodeMix", data_type="RGBA")
    L.new(face, res.inputs["Factor"])
    L.new(fin.outputs[2], res.inputs[6])
    L.new(veneer.outputs[2], res.inputs[7])
    L.new(res.outputs[2], emit.inputs["Color"])
    return m


def bake(o, mode, path, size):
    img = bpy.data.images.new("wood_" + mode, size, size, alpha=False)
    img.colorspace_settings.name = "sRGB" if mode == "color" else "Non-Color"
    mat = build_material(mode)
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    mat.node_tree.nodes.active = tex
    o.data.materials.clear()
    o.data.materials.append(mat)
    bpy.ops.object.bake(type="EMIT")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    print("BAKED", mode, path)


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    color_path, height_path = a[0], a[1]
    size = int(a[2]) if len(a) > 2 else 4096
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            if any(d.type == dev for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == dev
                sc.cycles.device = "GPU"
                break
        except Exception:
            continue
    sc.cycles.samples = 4
    sc.render.bake.margin = 16
    o = bpy.data.objects["Wood_stock_v8"]
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bake(o, "color", color_path, size)
    bake(o, "height", height_path, size)


main()
