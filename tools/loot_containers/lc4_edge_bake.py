"""Контейнеры для лута, v03 круг 4: карта кромок ИЗ 3D — запекание узла Bevel в развёртку каждого набора.
Прежняя зона (по картам положения / нормали) не видела скруглённые фаски и рёбра на границах островов. Здесь:
  R = 1 − dot(Bevel.Normal, True Normal), растянуто ×K — светится на острых и на скруглённых рёбрах (по одной детали:
      узел Bevel ищет рёбра в пределах объекта, соседние детали не «протекают»);
  G = Pointiness (0,5 — плоско; больше — выпуклое) — для отделения выпуклых рёбер от вогнутых.
  blender --background <RING_Loot_Containers_uv_v01.blend> --python tools/loot_containers/lc4_edge_bake.py [-- набор …]
→ _asset_src/loot_containers/prints/geo/<набор>_edge.npy (float32, строки сверху вниз, 3 канала: R, G, B=0)
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "dorm_modules"))
OUT = "E:/Games/RING-godot/_asset_src/loot_containers/prints/geo"
extra = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
sys.argv = sys.argv[:sys.argv.index("--")] if "--" in sys.argv else sys.argv
sys.argv += ["--", OUT, "lc_uv"] + extra
import bpy  # noqa: E402
import print_bake as PB  # noqa: E402

RADIUS = float(os.environ.get("LC4_BEVEL_R", "0.007"))
GAIN = float(os.environ.get("LC4_BEVEL_K", "10"))


def bake_item(coll, game, out_dir, res=PB.RES) -> None:
    objs = [o for o in coll.objects if o.type == "MESH"]
    coll.hide_viewport = False
    coll.hide_render = False
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for ob in objs:
        ob.hide_set(False)
        ob.hide_viewport = False
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    # у каждой детали — свой материал запекания (общий для набора материал у нескольких узлов Bevel не мешает)
    mat = objs[0].data.materials[0]
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    bev = nt.nodes.new("ShaderNodeBevel")
    bev.inputs["Radius"].default_value = RADIUS
    bev.samples = 16
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(bev.outputs["Normal"], dot.inputs[0])
    nt.links.new(geo.outputs["True Normal"], dot.inputs[1])
    sub = nt.nodes.new("ShaderNodeMath")
    sub.operation = "SUBTRACT"
    sub.inputs[0].default_value = 1.0
    nt.links.new(dot.outputs["Value"], sub.inputs[1])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.use_clamp = True
    mul.inputs[1].default_value = GAIN
    nt.links.new(sub.outputs["Value"], mul.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(mul.outputs["Value"], comb.inputs["X"])
    nt.links.new(geo.outputs["Pointiness"], comb.inputs["Y"])
    nt.links.new(comb.outputs["Vector"], emit.inputs["Color"])
    img_node = nt.nodes.new("ShaderNodeTexImage")
    nt.nodes.active = img_node
    img = bpy.data.images.new(f"{game}_edge", res, res, float_buffer=True, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    img_node.image = img
    bpy.context.scene.cycles.samples = 4
    bpy.ops.object.bake(type="EMIT", margin=8, use_clear=True)
    buf = np.empty(res * res * 4, np.float32)
    img.pixels.foreach_get(buf)
    a = np.flipud(buf.reshape(res, res, 4))[..., :3].copy()
    np.save(os.path.join(out_dir, f"{game}_edge.npy"), a)
    bpy.data.images.remove(img)
    for ob in objs:
        ob.select_set(False)
    coll.hide_viewport = True
    print("EDGE", game, "R>0.5: %.4f" % float((a[..., 0] > 0.5).mean()), flush=True)


PB.bake_item = bake_item
PB.main()
