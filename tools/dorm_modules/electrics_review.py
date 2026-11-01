"""Электрика общежития: файл просмотра текстур — наборы развёртки с картами Painter в студии (светильники и лампы —
под потолком, выключатели, розетки, коробка и провода — на стене), варианты отделки — копиями рядом с подписью кода.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Electrics_uv_v01.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/electrics_review.py -- <папка карт> <выход .blend>

Стекло колбы — прозрачное, молочное стекло плафона и рассеиватель — полупрозрачные (призматический вариант —
прозрачнее); остальное — карты как есть.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector as V

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_electrics as B  # noqa: E402
import finish_review as R  # noqa: E402
import mlib as L  # noqa: E402

CATALOG = "E:/Games/RING-godot/tools/asset_kit/finish/finishes.json"
CEIL = B.CEIL
# набор: (где — «потолок» / «стена», высота на стене, ширина места по X)
PLACE = {"el_lsp": ("ceil", 0, 1.45), "el_lpo": ("ceil", 0, 1.5), "el_tube": ("ceil", 0, 1.4), "el_plafond": ("ceil", 0, 0.5),
         "el_pendant": ("ceil", 0, 0.4), "el_bulb": ("ceil", 0, 0.45),
         "el_switch_round": ("wall", 1.4, 0.2), "el_socket_round": ("wall", 1.4, 0.2), "el_switch_white": ("wall", 1.4, 0.2),
         "el_socket_white": ("wall", 1.4, 0.2), "el_box": ("wall", 1.4, 0.25), "el_wire_flat": ("wall", CEIL, 2.2),
         "el_wire_twisted": ("wall", 1.0, 1.9)}
# полупрозрачность по слоту (имя сетки до «__»): (пропускание, прозрачное стекло)
SEE = {"Лампа_стекло": (1.0, True), "Плафон_стекло": (0.55, False), "Рассеиватель_опал": (0.5, False)}
# варианты износа без карточки каталога: настенное, закрашенное при ремонте (electrics_sp.py wear)
PAINTED = {"краска": "закрашено краской стены", "побелка": "забелено побелкой"}


def seethrough(mat, transmission, clear):
    b = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["IOR"].default_value = 1.5
    if clear:
        b.inputs["Roughness"].default_value = 0.02
        for lnk in list(b.inputs["Roughness"].links):
            mat.node_tree.links.remove(lnk)
    mat.surface_render_method = "DITHERED"


def apply_maps(objs, game, maps_dir, prefix=None, variant_code=None):
    cache = {}
    for ob in objs:
        if ob.type != "MESH":
            continue
        base = ob.name.split(".")[0].split("__")[0]
        key = base if base in SEE else ""
        if key not in cache:
            m = R.material(f"{game}{'__' + variant_code if variant_code else ''}{'_' + key if key else ''}", maps_dir,
                           prefix=prefix)
            if key:
                tr, clear = SEE[key]
                if variant_code == "PL-PRZ" and key == "Рассеиватель_опал":
                    tr, clear = 0.9, False
                seethrough(m, tr, clear)
            cache[key] = m
        ob.data.materials.clear()
        ob.data.materials.append(cache[key])
        for p in ob.data.polygons:
            p.use_smooth = True
        # рёбра круче 40° — острые: у вырезов (гнёзда, прорезь) их не пометил булев — сглаживание тянуло лицо в полосы
        ob.data.set_sharp_from_angle(angle=math.radians(40))


def label(coll, text, at, rot):
    cu = bpy.data.curves.new(f"подпись {text}", "FONT")
    cu.body = text
    cu.size = 0.05
    cu.align_x = "CENTER"
    t = bpy.data.objects.new(f"подпись {text}", cu)
    coll.objects.link(t)
    t.location = at
    t.rotation_euler = rot
    t.data.materials.append(bpy.data.materials.get("Подпись") or L.material("Подпись", (0.9, 0.9, 0.85), 0.6))


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    maps_root, out = argv[0], argv[1]
    titles = {f["code"]: f["title"] for f in json.load(open(CATALOG, encoding="utf-8"))["finishes"]}
    titles.update(PAINTED)
    for o in list(bpy.data.objects):
        if not any(c.name in PLACE or c.name == "Развёртка_v01" for c in o.users_collection):
            bpy.data.objects.remove(o)
    top = bpy.data.collections["Развёртка_v01"]
    top.hide_viewport = False
    top.hide_render = False
    var_top = bpy.data.collections.new("Варианты отделки")
    bpy.context.scene.collection.children.link(var_top)
    xc, xw = 0.0, 0.4
    for game, (where, z, width) in PLACE.items():
        coll = bpy.data.collections.get(game)
        if coll is None:
            continue
        coll.hide_viewport = False
        coll.hide_render = False
        objs = [o for o in coll.objects if o.type == "MESH"]
        if where == "ceil":
            at = V((xc + width / 2, -0.7, CEIL))
            xc += width + 0.25
        else:
            at = V((xw + width / 2 - (0.0 if game.startswith("el_wire") else 0.0), 0.0, z))
            xw += width + 0.2
        shift = Matrix.Translation(at - (V((0.5 * 0, 0, 0))))
        if game.startswith("el_wire"):
            shift = Matrix.Translation(at - V((width / 2, 0, 0)))
        for ob in objs:
            ob.matrix_world = shift
        apply_maps(objs, game, os.path.join(maps_root, game))
        variants = sorted(d.split("__", 1)[1] for d in os.listdir(maps_root) if d.startswith(game + "__"))
        for k, code in enumerate(variants):
            vc = bpy.data.collections.new(f"{game} · {code} · {titles.get(code, '')}")
            var_top.children.link(vc)
            off = Matrix.Translation(V((0, -0.55 * (k + 1), 0))) if where == "ceil" else Matrix.Translation(V((0, 0, -0.22 * (k + 1))))
            copies = []
            for ob in objs:
                new = ob.copy()
                new.data = ob.data.copy()
                vc.objects.link(new)
                new.matrix_world = off @ shift
                copies.append(new)
            apply_maps(copies, game, os.path.join(maps_root, f"{game}__{code}"), prefix=game, variant_code=code)
            p = (off @ shift).translation
            if where == "ceil":
                label(vc, code, (p.x, p.y, 0.002), (0, 0, 0))
            else:
                label(vc, code, (p.x, -0.002, p.z - 0.07), (math.radians(90), 0, 0))
        print("REVIEW", game, len(objs), "деталей, варианты", variants, flush=True)
    span = max(xc, xw) + 0.5
    B.studio(span, L.collection("Студия"))
    floor = bpy.data.objects.get("студия_пол")
    ceil = bpy.data.objects.get("студия_потолок")
    for ob, y0 in ((floor, -3.5), (ceil, -3.0)):
        if ob is not None:
            for v in ob.data.vertices:
                if v.co.y < -1.0:
                    v.co.y = y0
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
