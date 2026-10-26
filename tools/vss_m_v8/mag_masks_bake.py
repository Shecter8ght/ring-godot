# ВСС-М v8: маска губок и переднего упора магазинов (набор «magazine» в Painter) — где затвор трёт пластик до блеска
# (фото владельца 26.10: губки затёрты). Считается по расстоянию вдоль оси магазина от оси верхнего патрона (все три
# магазина в одной плоскости XZ, сдвинуты только по Y): выше заплечика — 1, ниже на 4 мм — 0. Запекается излучением
# в общую развёртку набора (sp_export.py), детали, кроме корпусов, — чёрные.
# blender --background --factory-startup _asset_src/vss_m_v8/VSS_M_v8_sp.blend --python-exit-code 1 \
#   --python tools/vss_m_v8/mag_masks_bake.py -- <mag_lips.png> [размер] [набор: magazine|magazine_30]
import math
import os
import sys
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sp_export  # noqa: E402

P0 = (446.4, -2.6)                 # ось верхнего патрона (x, z), part_magazine.P0
TH = math.radians(5.0)             # наклон оси магазина у верха, part_magazine.THETA0
D = (math.sin(TH), -math.cos(TH))  # вниз по оси
BODIES = ("Magazine_10", "Magazine_20", "Magazine_30")


def build_material(body):
    m = bpy.data.materials.new("_mag_lips")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(emit.outputs[0], out.inputs["Surface"])
    if not body:
        emit.inputs["Color"].default_value = (0, 0, 0, 1)
        return m
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])

    def op(o, a, b):
        x = nt.nodes.new("ShaderNodeMath")
        x.operation = o
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                x.inputs[i].default_value = v
            else:
                nt.links.new(v, x.inputs[i])
        return x.outputs[0]
    # u = (p - P0) · D в мм
    u = op("ADD", op("MULTIPLY", op("SUBTRACT", op("MULTIPLY", sep.outputs["X"], 1000.0), P0[0]), D[0]),
           op("MULTIPLY", op("SUBTRACT", op("MULTIPLY", sep.outputs["Z"], 1000.0), P0[1]), D[1]))
    r = nt.nodes.new("ShaderNodeMapRange")
    r.interpolation_type = "SMOOTHSTEP"
    nt.links.new(u, r.inputs["Value"])
    r.inputs["From Min"].default_value, r.inputs["From Max"].default_value = 1.0, 5.0
    r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = 1.0, 0.0
    c = nt.nodes.new("ShaderNodeCombineColor")
    for i in range(3):
        nt.links.new(r.outputs[0], c.inputs[i])
    nt.links.new(c.outputs[0], emit.inputs["Color"])
    return m


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    path = a[0]
    size = int(a[1]) if len(a) > 1 else 4096
    group = a[2] if len(a) > 2 else "magazine"
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    sc.render.bake.margin = 8
    img = bpy.data.images.new("mag_lips", size, size, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    img.generated_color = (0, 0, 0, 1)
    bpy.ops.object.select_all(action="DESELECT")
    objs = [bpy.data.objects[n] for n in sp_export.GROUPS[group] if n in bpy.data.objects]
    for o in objs:
        mat = build_material(o.name in BODIES)
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = img
        mat.node_tree.nodes.active = tex
        o.data.materials.clear()
        o.data.materials.append(mat)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.bake(type="EMIT")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    print("BAKED", path)


main()
