"""Файл просмотра этапа 1 текстур (заводская отделка) для владельца: развёрнутые сетки с картами из Painter на местах
своих вещей, студия в файле, вьюпорт сразу Rendered. Стекло, линзы, рассеиватели и трубки — прозрачные (цвет и блеск
из карт), светодиоды и пламя светятся, нагар, табак и нутро банки — простым цветом (заводской отделки нет). Исходная форма в файле скрыта (не удаляется).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<…_uv_v01.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/finish_review.py -- <папка карт> <выход.blend> <модуль развёртки: found_lights_uv|clutter_uv>

Карты — <папка карт>/<вещь>/<вещь>_{baseColor,normal,occlusionRoughnessMetallic}.png (выгрузка sp_lib.export).
"""
import importlib
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GLASS = ("стекло", "линза", "рассеиватель", "трубка")
GLOW = ("светодиод", "пламя")
# без заводской отделки (нет слота в finish-spec): простой цвет и блеск
PLAIN = {"нагар": ((0.03, 0.028, 0.026), 0.95), "табак": ((0.16, 0.09, 0.04), 0.95), "отверстие": ((0.01, 0.01, 0.01), 0.6)}


def load(path, non_color):
    img = bpy.data.images.load(path, check_existing=True)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def material(name, maps_dir, glass=False, glow=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    if glow:
        bsdf.inputs["Emission Color"].default_value = (1.0, 0.85, 0.6, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 4.0
        return m
    base = os.path.basename(maps_dir)

    def tex(kind, non_color):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = load(os.path.join(maps_dir, f"{base}_{kind}.png"), non_color)
        return n
    bc = tex("baseColor", False)
    nt.links.new(bc.outputs["Color"], bsdf.inputs["Base Color"])
    orm = tex("occlusionRoughnessMetallic", True)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tex("normal", True).outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if glass:
        bsdf.inputs["Transmission Weight"].default_value = 1.0
        bsdf.inputs["IOR"].default_value = 1.5
        m.surface_render_method = "DITHERED"
    return m


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    maps_root, out, uv_mod = argv[0], argv[1], argv[2]
    U = importlib.import_module(uv_mod)
    top = bpy.data.collections["Развёртка_v01"]
    top.hide_viewport = False
    top.hide_render = False
    for root_name, game in U.ITEMS.items():
        root = bpy.data.objects.get(root_name)
        coll = bpy.data.collections.get(game)
        if root is None or coll is None:
            continue
        coll.hide_viewport = False
        coll.hide_render = False
        maps_dir = os.path.join(maps_root, game)
        have = os.path.exists(os.path.join(maps_dir, f"{game}_baseColor.png"))
        for ob in coll.objects:
            ob.matrix_world = root.matrix_world  # сетки развёртки — в осях своего корня
            low = ob.name.lower()
            glow = any(k in low for k in GLOW)
            glass = any(k in low for k in GLASS)
            ob.data.materials.clear()
            plain = next((v for k, v in PLAIN.items() if k in low), None)
            if plain:
                pm = bpy.data.materials.new(f"{game}_{ob.name}")
                pm.use_nodes = True
                b = next(n for n in pm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
                b.inputs["Base Color"].default_value = (*plain[0], 1.0)
                b.inputs["Roughness"].default_value = plain[1]
                ob.data.materials.append(pm)
                print("REVIEW", game, ob.name, "plain", flush=True)
                continue
            if have or glow:
                ob.data.materials.append(material(f"{game}_{'свет' if glow else 'стекло' if glass else 'карты'}",
                                                  maps_dir, glass, glow))
            print("REVIEW", game, ob.name, "glass" if glass else "glow" if glow else "maps" if have else "НЕТ КАРТ", flush=True)
        # исходная форма — скрыта
        for o in [root] + list(root.children_recursive):
            o.hide_set(True)
            o.hide_render = True
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 128
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)


if __name__ == "__main__":
    main()
