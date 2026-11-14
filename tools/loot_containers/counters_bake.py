"""Опоры касс v01, отделка: карты геометрии в развёртку — положение, нормаль, номер детали (как lc_print_bake.py) и карта кромок
из 3D (как lc4_edge_bake.py: узел Bevel, по одной детали). Cycles на процессоре, эмиссия, поле 8 пикселей.

  blender --background <RING_Loot_Counters_uv_v01.blend> --python tools/loot_containers/counters_bake.py [-- набор …]
→ _asset_src/loot_containers/prints/geo_counters/<набор>_{pos,nrm,part,edge}.npy (float32, строки сверху вниз) и <набор>_parts.json
"""
import json
import os
import sys

import bpy
import numpy as np

OUT = "E:/Games/RING-godot/_asset_src/loot_containers/prints/geo_counters"
RES = {"cn_counter": 2048, "cn_checkout": 2048}
RADIUS = float(os.environ.get("CN_BEVEL_R", "0.006"))
GAIN = float(os.environ.get("CN_BEVEL_K", "10"))


def _nodes(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    img_node = nt.nodes.new("ShaderNodeTexImage")
    nt.nodes.active = img_node
    return nt, emit, img_node


def _bake(game, kind, res, nt, emit, img_node, sock) -> np.ndarray:
    img = bpy.data.images.new(f"{game}_{kind}", res, res, float_buffer=True, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    img_node.image = img
    for l in list(emit.inputs["Color"].links):
        nt.links.remove(l)
    nt.links.new(sock, emit.inputs["Color"])
    bpy.ops.object.bake(type="EMIT", margin=8, use_clear=True)
    buf = np.empty(res * res * 4, np.float32)
    img.pixels.foreach_get(buf)
    a = np.flipud(buf.reshape(res, res, 4))[..., :3].copy()
    bpy.data.images.remove(img)
    return a


def bake_item(coll, game, res) -> None:
    objs = [o for o in coll.objects if o.type == "MESH"]
    coll.hide_viewport = False
    coll.hide_render = False
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    parts = {}
    for k, ob in enumerate(objs, 1):
        ob.hide_set(False)
        ob.hide_viewport = False
        ob.select_set(True)
        ob.pass_index = k
        parts[k] = ob.name.split(".")[0] if ob.name.count(".") and ob.name.rsplit(".", 1)[-1].isdigit() else ob.name
    bpy.context.view_layer.objects.active = objs[0]
    mat = objs[0].data.materials[0]
    nt, emit, img_node = _nodes(mat)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    info = nt.nodes.new("ShaderNodeObjectInfo")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(info.outputs["Object Index"], comb.inputs["X"])
    for kind, sock in (("pos", geo.outputs["Position"]), ("nrm", geo.outputs["Normal"]), ("part", comb.outputs["Vector"])):
        np.save(os.path.join(OUT, f"{game}_{kind}.npy"), _bake(game, kind, res, nt, emit, img_node, sock))
    with open(os.path.join(OUT, f"{game}_parts.json"), "w", encoding="utf-8") as fh:
        json.dump(parts, fh, ensure_ascii=False)
    # кромки из 3D
    nt, emit, img_node = _nodes(mat)
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
    cb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(mul.outputs["Value"], cb.inputs["X"])
    nt.links.new(geo.outputs["Pointiness"], cb.inputs["Y"])
    bpy.context.scene.cycles.samples = 4
    a = _bake(game, "edge", res, nt, emit, img_node, cb.outputs["Vector"])
    np.save(os.path.join(OUT, f"{game}_edge.npy"), a)
    print("BAKED", game, len(parts), "частей; кромка R>0.5: %.4f" % float((a[..., 0] > 0.5).mean()), flush=True)
    for ob in objs:
        ob.select_set(False)
    coll.hide_viewport = True


def main() -> None:
    only = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    os.makedirs(OUT, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 1
    sc.render.bake.margin = 8
    top = bpy.data.collections["Развёртка_v01"]
    top.hide_viewport = False
    for game, res in RES.items():
        if only and game not in only:
            continue
        bake_item(bpy.data.collections[game], game, res)


if __name__ == "__main__":
    main()
