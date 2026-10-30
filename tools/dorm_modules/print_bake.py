"""Карты геометрии в развёртку вещей — для наложения печати (print_apply.py): положение и нормаль каждого пикселя
(в осях корня вещи, метры) и номер детали.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<…_uv_v01.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/print_bake.py -- <папка выхода> <модуль развёртки: found_lights_uv|clutter_uv> [вещь …]

Выход: <папка>/<вещь>_pos.exr, _nrm.exr, _part.exr (R = номер детали) и <вещь>_parts.json (номер → имя сетки).
Запекание Cycles на процессоре, эмиссия, 2048, поле 8 пикселей.
"""
import importlib
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
RES = 2048


def bake_item(coll, game, out_dir) -> None:
    sc = bpy.context.scene
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
    for kind, sock in (("pos", geo.outputs["Position"]), ("nrm", geo.outputs["Normal"]), ("part", comb.outputs["Vector"])):
        img = bpy.data.images.new(f"{game}_{kind}", RES, RES, float_buffer=True, alpha=False)
        img.colorspace_settings.name = "Non-Color"
        img_node.image = img
        for l in list(emit.inputs["Color"].links):
            nt.links.remove(l)
        nt.links.new(sock, emit.inputs["Color"])
        bpy.ops.object.bake(type="EMIT", margin=8, use_clear=True)
        img.filepath_raw = os.path.join(out_dir, f"{game}_{kind}.exr")
        img.file_format = "OPEN_EXR"
        img.save()
    with open(os.path.join(out_dir, f"{game}_parts.json"), "w", encoding="utf-8") as fh:
        json.dump(parts, fh, ensure_ascii=False)
    for ob in objs:
        ob.select_set(False)
    coll.hide_viewport = True
    print("BAKED", game, parts, flush=True)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    out_dir, uv_mod, only = argv[0], argv[1], argv[2:]
    os.makedirs(out_dir, exist_ok=True)
    U = importlib.import_module(uv_mod)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 1
    sc.render.bake.margin = 8
    top = bpy.data.collections["Развёртка_v01"]
    top.hide_viewport = False
    for game in U.ITEMS.values():
        if only and game not in only:
            continue
        coll = bpy.data.collections.get(game)
        if coll is not None:
            bake_item(coll, game, out_dir)


if __name__ == "__main__":
    main()
