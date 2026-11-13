"""Сумка-укладка: игровая версия рядом с high-poly в одной студии (после medbag_game.py -- export).

  blender --background "<RING_Loot_MedBag_finish_v03.blend>" --python tools/loot_containers/medbag_game_compare.py -- [имя_кадра …]

Файл — отделка принята (high-poly с материалами); игровые объекты дописываются из RING_Loot_MedBag_game_v01.blend.

Кадры — Просмотр/medbag_v02/game_vs_high_*.png: слева high-poly (закрыта / раскрыта), справа игровая модель с игровыми
картами (базовый цвет, ORM, нормаль), та же студия и свет (lc3_bag_view.studio).
"""
import math
import os
import sys

import bpy
from mathutils import Vector as V

sys.path.insert(0, "E:/Games/RING-godot/tools/loot_containers")
import lc3_bag_view as VW  # noqa: E402

SHOTS = VW.SHOTS
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def tree(root):
    return [root] + list(root.children_recursive)


GAME = "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/models/RING_Loot_MedBag_game_v01.blend"


def main() -> None:
    sc = bpy.context.scene
    with bpy.data.libraries.load(GAME, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("готово:")]
    for o in dst.objects:
        sc.collection.objects.link(o)
    VW.studio()
    hi_c, hi_o = bpy.data.objects["МС_сумка_укладка"], bpy.data.objects["МС_сумка_укладка_раскрыта"]
    g_c, g_o = bpy.data.objects["готово:lc_medbag"], bpy.data.objects["готово:lc_medbag_open"]
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in sum((tree(r) for r in (hi_c, hi_o, g_c, g_o)), []):
            o.hide_render = True
    for o in tree(g_c) + tree(g_o):
        if o.name.endswith("_lod1"):
            o.hide_render = True
    # раскладка: ряд закрытых, ряд раскрытых; слева high-poly, справа игровая
    pos = {hi_c: (-0.45, 0.0), g_c: (0.45, 0.0), hi_o: (-0.45 - 0.95, 0.0), g_o: (0.45, 0.0)}
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 64
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1800, 900
    cam = sc.camera
    bpy.data.materials["lc_medbag"].use_backface_culling = True   # как в движке: грани смотрят наружу или не видны
    views = {"closed": ((hi_c, g_c), (0.0, 0.0, 0.16), 1.35, 28, 22, 45),
             "open": ((hi_o, g_o), (0.0, 0.0, 0.2), 1.55, 25, 32, 42),
             "top": ((hi_o, g_o), (0.0, 0.0, 0.1), 1.2, 0, 80, 50),
             "close_zip": ((hi_c, g_c), (-0.1, -0.1, 0.28), 0.5, 28, 30, 55)}
    os.makedirs(SHOTS, exist_ok=True)
    for name, ((h, g), tgt, dist, az, el, lens) in views.items():
        if argv and name not in argv:
            continue
        for r in (hi_c, hi_o, g_c, g_o):
            for o in tree(r):
                o.hide_render = r not in (h, g) or (o.type == "MESH" and o.name.endswith("_lod1"))
        h.location = V((-0.4, 0.0, 0.0))
        g.location = V((0.4, 0.0, 0.0))
        bpy.context.view_layer.update()
        c = V((0.0, 0.0, 0.0)) + V(tgt)
        a, e = math.radians(az), math.radians(el)
        cam.location = c + V((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        cam.data.clip_start = 0.01
        sc.render.filepath = f"{SHOTS}/game_vs_high_{name}.png"
        bpy.ops.render.render(write_still=True)
        print("кадр", name, flush=True)


main()
