# ВСС-М v8: карта высот ромбовидной накатки рифлёной части глушителя (сетка Suppressor_knurl) в развёртку набора
# «suppressor» — для слоя высоты в Substance Painter. Узор считается по углу вокруг оси канала и по длине: два
# семейства канавок под ±45°, по окружности целое число ромбов (без шва), шаг ~1.3 мм, вершины чуть притуплены.
# Остальные детали набора в карте чёрные (высота 0).
# blender --background --factory-startup _asset_src/vss_m_v8/VSS_M_v8_sp.blend --python-exit-code 1 \
#   --python tools/vss_m_v8/knurl_bake.py -- <out.png> [размер]
import math
import sys
import bpy

BORE_Z = 10.0
RADIUS = 20.2
PITCH = 1.3


def build_area_material():
    """Белая заливка — где сетка накатки лежит в развёртке (маска области для слоёв канавок)."""
    m = bpy.data.materials.new("_knurl_area")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (1, 1, 1, 1)
    nt.links.new(emit.outputs[0], out.inputs["Surface"])
    return m


def build_material():
    m = bpy.data.materials.new("_knurl_bake")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    L = nt.links

    def n(kind, **kw):
        x = nt.nodes.new(kind)
        for k, v in kw.items():
            setattr(x, k, v)
        return x

    def op(o, a, b=None):
        x = n("ShaderNodeMath", operation=o)
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                x.inputs[i].default_value = v
            else:
                L.new(v, x.inputs[i])
        return x.outputs[0]

    out = n("ShaderNodeOutputMaterial")
    emit = n("ShaderNodeEmission")
    L.new(emit.outputs[0], out.inputs["Surface"])
    geo = n("ShaderNodeNewGeometry")
    sep = n("ShaderNodeSeparateXYZ")
    L.new(geo.outputs["Position"], sep.inputs[0])
    y = op("MULTIPLY", sep.outputs["Y"], 1000.0)
    z = op("SUBTRACT", op("MULTIPLY", sep.outputs["Z"], 1000.0), BORE_Z)
    x = op("MULTIPLY", sep.outputs["X"], 1000.0)
    turns = round(2 * math.pi * RADIUS / PITCH)
    a = op("MULTIPLY", op("ARCTAN2", z, y), turns / (2 * math.pi))
    b = op("DIVIDE", x, PITCH)

    def tri(t):
        return op("SUBTRACT", 1.0, op("MULTIPLY", op("ABSOLUTE", op("SUBTRACT", op("FRACT", t), 0.5)), 2.0))
    h = op("MINIMUM", tri(op("ADD", a, b)), tri(op("SUBTRACT", a, b)))
    h = op("MINIMUM", op("MULTIPLY", h, 1.18), 1.0)
    rgb = n("ShaderNodeCombineColor")
    for i in range(3):
        L.new(h, rgb.inputs[i])
    L.new(rgb.outputs[0], emit.inputs["Color"])
    return m


def bake_one(o, mat, path, size):
    img = bpy.data.images.new("knurl_" + mat.name, size, size, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    img.generated_color = (0, 0, 0, 1)
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    mat.node_tree.nodes.active = tex
    o.data.materials.clear()
    o.data.materials.append(mat)
    bpy.ops.object.bake(type="EMIT")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    print("BAKED", path)


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[0]
    size = int(a[1]) if len(a) > 1 else 4096
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    sc.render.bake.margin = 8
    o = bpy.data.objects["Suppressor_knurl"]
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bake_one(o, build_material(), out, size)
    bake_one(o, build_area_material(), out.replace("_height", "_area"), size)


main()
