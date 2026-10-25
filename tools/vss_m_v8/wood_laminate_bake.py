# ВСС-М v8: основа цвета приклада для Substance Painter — клеёная берёзовая фанера, как у приклада ВСС (образец
# владельца с Fab): на плоских боковинах — лицевой шпон (фото Poly Haven «Plywood», CC0), на скруглениях, торцах
# и в вырезах окон — полосы слоёв (слой ~1.55 мм по ширине приклада, клеевые прослойки темнее, тон слоёв разный,
# кромки слоёв слегка волнистые). Запекается излучением в развёртку приклада (sp_export.py), 4K.
# blender --background --factory-startup _asset_src/vss_m_v8/VSS_M_v8_sp.blend --python-exit-code 1 \
#   --python tools/vss_m_v8/wood_laminate_bake.py -- <out.png> [размер]
import sys
import bpy

PLYWOOD = "E:/Games/RING-godot/assets/textures/plywood/albedo.jpg"
LAYER_MM = 1.55
# цвета в линейном пространстве: светлый шпон, середина, клеевая прослойка; оттенок фото лицевого шпона
C_LIGHT = (0.55, 0.32, 0.11, 1.0)
C_MID = (0.42, 0.2, 0.06, 1.0)
C_GLUE = (0.16, 0.045, 0.012, 1.0)
FACE_TINT = (1.25, 0.92, 0.5, 1.0)


def node(nt, kind, **kw):
    n = nt.nodes.new(kind)
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def math_node(nt, op, a, b=None, value=None):
    n = node(nt, "ShaderNodeMath", operation=op)
    L = nt.links
    if isinstance(a, (int, float)):
        n.inputs[0].default_value = a
    else:
        L.new(a, n.inputs[0])
    if b is not None:
        if isinstance(b, (int, float)):
            n.inputs[1].default_value = b
        else:
            L.new(b, n.inputs[1])
    return n.outputs[0]


def build_material():
    m = bpy.data.materials.new("_wood_laminate_bake")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    L = nt.links
    out = node(nt, "ShaderNodeOutputMaterial")
    emit = node(nt, "ShaderNodeEmission")
    L.new(emit.outputs[0], out.inputs["Surface"])
    geo = node(nt, "ShaderNodeNewGeometry")
    sep = node(nt, "ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    # волнистость кромок слоёв: шум по (x, z) сдвигает номер слоя на доли периода
    pos_mm = node(nt, "ShaderNodeVectorMath", operation="SCALE")
    L.new(geo.outputs["Position"], pos_mm.inputs[0])
    pos_mm.inputs["Scale"].default_value = 1000.0
    wav = node(nt, "ShaderNodeTexNoise")
    wav.inputs["Scale"].default_value = 0.035
    wav.inputs["Detail"].default_value = 3.0
    L.new(pos_mm.outputs[0], wav.inputs["Vector"])
    t = math_node(nt, "MULTIPLY", sep.outputs["Y"], 1000.0 / LAYER_MM)
    t = math_node(nt, "ADD", t, math_node(nt, "MULTIPLY", math_node(nt, "SUBTRACT", wav.outputs["Fac"], 0.5), 1.4))
    fr = math_node(nt, "FRACT", t)
    idx = math_node(nt, "FLOOR", t)
    # полоса слоя: светлый шпон → клеевая прослойка
    ramp = node(nt, "ShaderNodeValToRGB")
    cr = ramp.color_ramp
    cr.elements[0].position = 0.0; cr.elements[0].color = C_LIGHT
    cr.elements[1].position = 0.6; cr.elements[1].color = C_LIGHT
    for p, c in ((0.7, C_MID), (0.76, C_GLUE), (0.9, C_GLUE), (0.97, C_MID)):
        e = cr.elements.new(p); e.color = c
    L.new(fr, ramp.inputs[0])
    # тон слоя: у каждого шпона свой (белый шум по номеру слоя)
    wn = node(nt, "ShaderNodeTexWhiteNoise", noise_dimensions="1D")
    L.new(idx, wn.inputs["W"])
    tone = node(nt, "ShaderNodeMapRange")
    L.new(wn.outputs["Value"], tone.inputs["Value"])
    tone.inputs["To Min"].default_value = 0.8
    tone.inputs["To Max"].default_value = 1.12
    stripes = node(nt, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    stripes.inputs["Factor"].default_value = 1.0
    L.new(ramp.outputs["Color"], stripes.inputs[6])
    tone_rgb = node(nt, "ShaderNodeCombineColor")
    for i in range(3):
        L.new(tone.outputs["Result"], tone_rgb.inputs[i])
    L.new(tone_rgb.outputs[0], stripes.inputs[7])
    # лицевой шпон: фото фанеры коробочной проекцией, волокна вдоль приклада
    tc = node(nt, "ShaderNodeTexCoord")
    mp = node(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.7, 3.6, 3.6)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    img = node(nt, "ShaderNodeTexImage", projection="BOX", projection_blend=0.3)
    img.image = bpy.data.images.load(PLYWOOD, check_existing=True)
    L.new(mp.outputs[0], img.inputs["Vector"])
    face_col = node(nt, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    face_col.inputs["Factor"].default_value = 1.0
    L.new(img.outputs["Color"], face_col.inputs[6])
    face_col.inputs[7].default_value = FACE_TINT
    # где поверхность смотрит вбок (±Y) — лицевой шпон, иначе — срез слоёв
    ny = node(nt, "ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Normal"], ny.inputs[0])
    face = node(nt, "ShaderNodeMapRange")
    L.new(math_node(nt, "ABSOLUTE", ny.outputs["Y"]), face.inputs["Value"])
    face.inputs["From Min"].default_value = 0.82
    face.inputs["From Max"].default_value = 0.96
    face.interpolation_type = "SMOOTHSTEP"
    mix = node(nt, "ShaderNodeMix", data_type="RGBA")
    L.new(face.outputs["Result"], mix.inputs["Factor"])
    L.new(stripes.outputs[2], mix.inputs[6])
    L.new(face_col.outputs[2], mix.inputs[7])
    L.new(mix.outputs[2], emit.inputs["Color"])
    return m


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[0]
    size = int(a[1]) if len(a) > 1 else 4096
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
    o = bpy.data.objects["Wood_stock_v8"]
    img = bpy.data.images.new("wood_laminate", size, size, alpha=False)
    img.colorspace_settings.name = "sRGB"
    mat = build_material()
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    mat.node_tree.nodes.active = tex
    o.data.materials.clear()
    o.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    sc.render.bake.margin = 16
    bpy.ops.object.bake(type="EMIT")
    img.filepath_raw = out
    img.file_format = "PNG"
    img.save()
    print("BAKED", out)


main()
