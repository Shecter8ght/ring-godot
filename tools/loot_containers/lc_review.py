"""Контейнеры для лута, партия 1: файл просмотра текстур этапа 1 — все семь предметов, закрытое и открытое состояния рядом, в
студии (студийная HDRI в отражениях, свет, камера, вьюпорт сразу Rendered).

  blender --background <RING_Loot_Containers_uv_v01.blend> --python tools/loot_containers/lc_review.py -- <папка карт> <выход.blend> [shots <папка>]

Карты — <папка карт>/<набор>/<набор>_{baseColor,normal,occlusionRoughnessMetallic}.png (выгрузка sp_lib.export). Окно принтера кассы
— прозрачное (цвет и блеск из карт), ткань сумки — с блеском ворса (Sheen). С «shots» дополнительно рендерятся проверочные
кадры (Cycles, малое число выборок, шумодав) — для самопроверки, не для владельца.
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector as V

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "dorm_modules"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "asset_kit", "finish"))
import build_furniture as B  # noqa: E402
import finish_review as R  # noqa: E402
import mlib as L  # noqa: E402
import render_cards as RC  # noqa: E402

WALL = 1.4
# набор: (корень: пол или стена, ширина места закрытого, ширина места открытого)
PLACE = {"lc_safe": ("floor", 0.7, 1.3), "lc_cell": ("wall", 0.6, 1.0), "lc_gun": ("floor", 1.0, 1.9),
         "lc_file": ("floor", 0.7, 0.7), "lc_cash": ("floor", 0.6, 0.6), "lc_bag": ("floor", 0.8, 0.9),
         "lc_aid": ("wall", 0.6, 1.0)}
SHEEN = {"lc_bag": (0.2, 0.5)}
GLASS = ("окно",)
TITLES = {"lc_safe": "Сейф напольный", "lc_cell": "Сейф-ячейка", "lc_gun": "Оружейный шкаф", "lc_file": "Картотечный шкаф",
          "lc_cash": "Кассовое место", "lc_bag": "Медицинская сумка", "lc_aid": "Аптечка настенная"}


def label(coll, text, at):
    cu = bpy.data.curves.new(f"подпись {text}", "FONT")
    cu.body = text
    cu.size = 0.05
    cu.align_x = "CENTER"
    t = bpy.data.objects.new(f"подпись {text}", cu)
    coll.objects.link(t)
    t.location = at
    t.data.materials.append(bpy.data.materials.get("Подпись") or L.material("Подпись", (0.9, 0.9, 0.85), 0.6))


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    maps_root, out = argv[0], argv[1]
    shots = argv[3] if len(argv) > 3 and argv[2] == "shots" else None
    for o in list(bpy.data.objects):
        if o.name.startswith("_src_"):
            bpy.data.objects.remove(o)
    top = bpy.data.collections["Развёртка_v01"]
    top.hide_viewport = False
    top.hide_render = False
    x = 0.0
    spots = {}
    for game, (how, wc, wo) in PLACE.items():
        maps_dir = os.path.join(maps_root, game)
        have = os.path.exists(os.path.join(maps_dir, f"{game}_baseColor.png"))
        mats = {}
        for suffix, width, tag in (("__closed", wc, "закрыто"), ("", wo, "открыто")):
            coll = bpy.data.collections[game + suffix]
            coll.hide_viewport = False
            coll.hide_render = False
            cx = x + width / 2
            m = Matrix.Translation((cx, WALL if how == "wall" else 0.0, 1.3 if how == "wall" else 0.0))
            for ob in coll.objects:
                ob.hide_viewport = False
                ob.hide_render = False
                ob.matrix_world = m
                ob.data.materials.clear()
                if not have:
                    continue
                key = "glass" if any(k in ob.name for k in GLASS) else ""
                if key not in mats:
                    mm = R.material(f"{game}{'_стекло' if key else ''}", maps_dir, glass=bool(key), sheen=SHEEN.get(game))
                    mats[key] = mm
                ob.data.materials.append(mats[key])
                for p in ob.data.polygons:
                    p.use_smooth = True
                ob.data.set_sharp_from_angle(angle=math.radians(40))
            label(coll, f"{TITLES[game]} — {tag}", (cx, -0.9 if how == "floor" else WALL - 0.9, 0.002))
            spots[(game, tag)] = m.translation.copy()
            x += width + 0.12
        x += 0.35
    span = x
    st = L.collection("Студия")
    B.studio(st, span)
    # студийная HDRI в отражениях (камера видит ровный фон), мягкий свет от неё плюс три софтбокса студии
    bpy.context.scene.world = RC.world_studio(strength=1.0)
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.samples = 128
    bpy.context.scene.cycles.use_denoising = True
    bpy.context.scene.view_settings.view_transform = "AgX"
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
    if shots:
        render_shots(shots, spots)
    bpy.ops.file.make_paths_relative()   # карты лежат рядом: textures/finish_v01 в папке библиотеки
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)


# (имя, набор, состояние, смещение цели от корня, расстояние, азимут°, возвышение°, фокусное мм)
SHOTS = [
    ("safe_closed", "lc_safe", "закрыто", (0, 0, 0.36), 1.9, -25, 12, 50),
    ("safe_dial", "lc_safe", "закрыто", (0.0, -0.22, 0.50), 0.32, -10, 6, 50),
    ("safe_open", "lc_safe", "открыто", (0.0, 0.0, 0.36), 2.2, -40, 14, 50),
    ("gun_closed", "lc_gun", "закрыто", (0, 0, 0.9), 3.4, -22, 8, 50),
    ("gun_open", "lc_gun", "открыто", (0, 0, 0.9), 3.6, -20, 8, 50),
    ("file_open", "lc_file", "открыто", (0, -0.1, 0.7), 2.6, -30, 12, 50),
    ("cash_closed", "lc_cash", "закрыто", (0, 0, 0.15), 1.0, -20, 38, 50),
    ("cash_keys", "lc_cash", "закрыто", (-0.05, -0.1, 0.16), 0.5, 0, 55, 50),
    ("bag_open", "lc_bag", "открыто", (0, 0, 0.15), 1.4, -25, 28, 50),
    ("bag_close", "lc_bag", "закрыто", (0, -0.1, 0.25), 0.55, -15, 38, 50),
    ("aid_closed", "lc_aid", "закрыто", (0, -0.05, 0.0), 1.1, -12, 6, 50),
    ("cell_open", "lc_cell", "открыто", (0, -0.1, 0.0), 0.9, -25, 10, 50),
]


def render_shots(folder, spots) -> None:
    os.makedirs(folder, exist_ok=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 1000, 750
    sc.cycles.samples = 40
    cam = bpy.data.cameras.new("проверка")
    co = bpy.data.objects.new("проверка", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    for name, game, state, off, dist, az, el, lens in SHOTS:
        base = spots[(game, state)]
        tgt = base + V(off)
        a, e = math.radians(az - 90), math.radians(el)
        co.location = tgt + V((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * dist
        co.rotation_euler = (tgt - co.location).to_track_quat("-Z", "Y").to_euler()
        cam.lens = lens
        sc.render.filepath = os.path.join(folder, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("SHOT", name, flush=True)


if __name__ == "__main__":
    main()
