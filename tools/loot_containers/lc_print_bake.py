"""Карты геометрии печати для контейнеров (обёртка над tools/dorm_modules/print_bake.py с модулем развёртки lc_uv).

  blender --background <RING_Loot_Containers_uv_v01.blend> --python tools/loot_containers/lc_print_bake.py [-- набор …]

Отличие от общей версии: карты пишутся .npy (float32 RGB, строки сверху вниз), а не .exr — у нынешнего OpenCV 5 нет
декодера OpenEXR (lc_prints.py читает .npy).
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
import json  # noqa: E402
import print_bake as PB  # noqa: E402


def bake_item(coll, game, out_dir, res=PB.RES) -> None:
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
        parts[k] = ob.name.split(".")[0]
    bpy.context.view_layer.objects.active = objs[0]
    mat = objs[0].data.materials[0]
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    info = nt.nodes.new("ShaderNodeObjectInfo")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(info.outputs["Object Index"], comb.inputs["X"])
    img_node = nt.nodes.new("ShaderNodeTexImage")
    nt.nodes.active = img_node
    kinds = [("pos", geo.outputs["Position"]), ("nrm", geo.outputs["Normal"]), ("part", comb.outputs["Vector"])]
    for kind, sock in kinds:
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
        np.save(os.path.join(out_dir, f"{game}_{kind}.npy"), a)
        bpy.data.images.remove(img)
    with open(os.path.join(out_dir, f"{game}_parts.json"), "w", encoding="utf-8") as fh:
        json.dump(parts, fh, ensure_ascii=False)
    for ob in objs:
        ob.select_set(False)
    coll.hide_viewport = True
    print("BAKED", game, parts, flush=True)


PB.bake_item = bake_item
PB.main()
