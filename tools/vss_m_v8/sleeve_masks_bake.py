# ВСС-М v8: маски муфты с планками (набор «sleeve» в Painter) под покрытие Cerakote (владелец 26.10): где планки и
# продольные полосы вдоль оси (обвесы ездят по планкам вперёд-назад — сколы вытянуты по X). Считается по положению
# в системе винтовки: корпус муфты |y| ≤ 23, z −13…33 мм, планки выступают на 9–10 мм — по бокам, снизу и сверху.
# Запекается излучением в развёртку набора (sp_export.py): sleeve_rail.png — планки 1, корпус 0;
# sleeve_streaks.png — шум, растянутый вдоль X (порог задаёт стек). rear_sight_ids.png — в развёртке мелкой стали
# острова заднего прицела белым вместе с полями (маска группы Cerakote: по сеткам она не закрывала края островов, и
# износ стали с полей давал светлую кайму вдоль рёбер прицела).
# blender --background --factory-startup _asset_src/vss_m_v8/VSS_M_v8_sp.blend --python-exit-code 1 \
#   --python tools/vss_m_v8/sleeve_masks_bake.py -- <папка> [размер]
import os
import sys
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sp_export  # noqa: E402

BODY_Y, BODY_ZLO, BODY_ZHI = 24.5, -14.5, 34.5     # граница корпуса и основания планок, мм (грани корпуса — 23, −13, 33)
REAR_SIGHT = ("Rear_sight_base", "Rear_sight_leaf", "Rear_sight_slider", "Rear_sight_weld")   # = sp_stacks.REAR_SIGHT


def build_material(kind):
    if kind in ("on", "off"):
        m = bpy.data.materials.new("_ids_" + kind)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        emit = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(emit.outputs[0], out.inputs["Surface"])
        v = 1.0 if kind == "on" else 0.0
        emit.inputs["Color"].default_value = (v, v, v, 1)
        return m
    m = bpy.data.materials.new("_sleeve_" + kind)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(emit.outputs[0], out.inputs["Surface"])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    mm = nt.nodes.new("ShaderNodeVectorMath")
    mm.operation = "SCALE"
    nt.links.new(geo.outputs["Position"], mm.inputs[0])
    mm.inputs["Scale"].default_value = 1000.0

    def op(o, a, b=None):
        x = nt.nodes.new("ShaderNodeMath")
        x.operation = o
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                x.inputs[i].default_value = v
            else:
                nt.links.new(v, x.inputs[i])
        return x.outputs[0]

    if kind == "rail":
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(mm.outputs[0], sep.inputs[0])
        # насколько точка вышла за корпус: бока, низ, верх
        d = op("MAXIMUM", op("SUBTRACT", op("ABSOLUTE", sep.outputs["Y"]), BODY_Y),
               op("MAXIMUM", op("SUBTRACT", BODY_ZLO, sep.outputs["Z"]), op("SUBTRACT", sep.outputs["Z"], BODY_ZHI)))
        v = nt.nodes.new("ShaderNodeMapRange")
        v.interpolation_type = "SMOOTHSTEP"
        nt.links.new(d, v.inputs["Value"])
        v.inputs["From Min"].default_value, v.inputs["From Max"].default_value = -0.6, 0.6
        val = v.outputs[0]
    else:
        # полосы вдоль X: шум, сжатый поперёк в 40 раз — длина полос десятки мм, ширина около миллиметра
        def streak(sx, syz, scale, seed):
            st = nt.nodes.new("ShaderNodeVectorMath")
            st.operation = "MULTIPLY"
            nt.links.new(mm.outputs[0], st.inputs[0])
            st.inputs[1].default_value = (sx, syz, syz)
            sh = nt.nodes.new("ShaderNodeVectorMath")
            sh.operation = "ADD"
            nt.links.new(st.outputs[0], sh.inputs[0])
            sh.inputs[1].default_value = (seed, seed * 1.7, seed * 0.3)
            nz = nt.nodes.new("ShaderNodeTexNoise")
            nz.noise_dimensions = "3D"
            nt.links.new(sh.outputs[0], nz.inputs["Vector"])
            nz.inputs["Scale"].default_value = scale
            nz.inputs["Detail"].default_value = 3.0
            nz.inputs["Roughness"].default_value = 0.55
            return nz.outputs["Fac"]
        val = op("ADD", op("MULTIPLY", streak(0.025, 1.0, 1.0, 3.1), 0.6), op("MULTIPLY", streak(0.05, 2.4, 1.0, 11.7), 0.4))
    c = nt.nodes.new("ShaderNodeCombineColor")
    for i in range(3):
        nt.links.new(val, c.inputs[i])
    nt.links.new(c.outputs[0], emit.inputs["Color"])
    return m


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    folder = a[0]
    size = int(a[1]) if len(a) > 1 else 4096
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    sc.render.bake.margin = 8
    objs = [bpy.data.objects[n] for n in sp_export.GROUPS["sleeve"] if n in bpy.data.objects]
    for kind in ("rail", "streaks"):
        img = bpy.data.images.new("sleeve_" + kind, size, size, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        img.generated_color = (0, 0, 0, 1)
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            mat = build_material(kind)
            tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
            tex.image = img
            mat.node_tree.nodes.active = tex
            o.data.materials.clear()
            o.data.materials.append(mat)
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        bpy.ops.object.bake(type="EMIT")
        path = os.path.join(folder, f"sleeve_{kind}.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        print("BAKED", path)
    # острова заднего прицела в наборе мелкой стали
    img = bpy.data.images.new("rear_sight_ids", size, size, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    img.generated_color = (0, 0, 0, 1)
    sc.render.bake.margin = 6
    bpy.ops.object.select_all(action="DESELECT")
    objs = [bpy.data.objects[n] for n in sp_export.GROUPS["steel_parts"] if n in bpy.data.objects]
    for o in objs:
        mat = build_material("on" if o.name in REAR_SIGHT else "off")
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = img
        mat.node_tree.nodes.active = tex
        o.data.materials.clear()
        o.data.materials.append(mat)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.bake(type="EMIT")
    path = os.path.join(folder, "rear_sight_ids.png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    print("BAKED", path)


main()
