# ВЕРАС-54 v14: проба цвета корпуса без пересборки в Painter — на файле просмотра цвет наборов корпуса (receiver, cover —
# целиком слот corpus) умножается в линейном так, чтобы средний тон 0,044 sRGB стал заданным; кадры tex_review.shots.
# Файл не сохраняется. Для сравнения вариантов, числа в спецификацию вносит владелец работы.
#   blender -b <файл просмотра> --factory-startup --python-exit-code 1 --python tools/veras54_v14/tex/tex_variant.py -- <папка> <цвет sRGB> [шероховатость] [вид,вид]
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
import tex_review as R  # noqa: E402


def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


a = sys.argv[sys.argv.index("--") + 1:]
out, col = a[0], float(a[1])
rough = float(a[2]) if len(a) > 2 and a[2] != "-" else None
views = a[3].split(",") if len(a) > 3 else None
gain = lin(col) / lin(0.044)
for s in ("receiver", "cover"):
    m = bpy.data.materials.get(f"ВЕРАС-54 • {s}")
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    src = b.inputs["Base Color"].links[0].from_socket
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(src, mul.inputs["A"])
    mul.inputs["B"].default_value = (gain, gain, gain, 1.0)
    nt.links.new(mul.outputs["Result"], b.inputs["Base Color"])
    if rough is not None:
        rsrc = b.inputs["Roughness"].links[0].from_socket
        add = nt.nodes.new("ShaderNodeMath")
        add.operation = "ADD"
        nt.links.new(rsrc, add.inputs[0])
        add.inputs[1].default_value = rough - 0.16
        add.use_clamp = True
        nt.links.new(add.outputs[0], b.inputs["Roughness"])
print("ВАРИАНТ цвет", col, "усиление", round(gain, 2), "шероховатость", rough)
R.shots(out, 64, views)
