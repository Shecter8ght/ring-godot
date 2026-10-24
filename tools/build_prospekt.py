# -*- coding: utf-8 -*-
"""Серый блокаут карты «Проспект» (docs/design/prospekt_map.md): городская улица за кордоном, 232 × 212 м.

    python -X utf8 tools/build_prospekt.py
      → data/blockouts/prospekt.json и scenes/levels/prospekt_study.tscn (перезаписываются целиком)
    tools/godot.cmd --windowed --resolution 1600x900 res://tools/prospekt_study.tscn   — прогулка
    tools/godot.cmd --headless res://tools/prospekt_study.tscn -- verify                 — проверка
    tools/godot.cmd --windowed --resolution 1600x900 res://tools/prospekt_study.tscn -- shots — снимки

Координаты — игровые: x — восток, z — юг (север = −z), ось проспекта z = 0, кордон на западе.
Масштаб — правило 9 AGENTS.md (владелец 2026-10-24, стенд E): предметы 1:1, ширина проходов и помещений
× 1,3 (WK), высота проёмов и потолков жилья × 1,15 (HK). Размеры карты в docs/design/prospekt_map.md —
реальные, здесь они умножены там, где это проход или помещение.

Здания с интерьерами — StudyBuilding (src/blockout/study_building.gd); уличная мелочь — наборы MallFiller
(src/blockout/mall_filler.gd); земля, проспект, кордон, подземный переход и паркинг −1 — ProspektLandscape
(src/blockout/prospekt_landscape.gd) по разделам этого плана.
"""
from __future__ import annotations

import json
import math
import random
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "data" / "blockouts" / "prospekt.json"
OUT_SCENE = ROOT / "scenes" / "levels" / "prospekt_study.tscn"

WK = 1.3    # ширина проходов и помещений
HK = 1.15   # высота проёмов и потолков жилья

# --- проспект
ROAD_HALF = 8.5                # 2+2 полосы с разделительной, м
MEDIAN_HALF = 1.5
SIDEWALK = 5.5 * WK            # 7.15
FN = -(ROAD_HALF + SIDEWALK)   # линия фасадов на севере (z)
FS = ROAD_HALF + SIDEWALK      # на юге
X_WEST = -121.0                # плиты кордона
X_EAST = 100.0                 # перекрёсток
STORY_FLAT = 2.7 * HK          # 3.105 — этаж жилья
STORY_RETAIL = 4.0             # первые этажи стрит-ритейла (и так высокие)
DOOR_H = 2.1 * HK              # 2.415
PIT_Y = -3.2                   # пол паркинга −1
TUNNEL_Y = -3.3                # пол подземного перехода

rng = random.Random(24)

plan: dict = {
    "version": 1,
    "purpose": "Карта «Проспект»: серый блокаут, 232 × 212 м — пролог и короткие рейды (docs/design/prospekt_map.md)",
    "north": "-Z",
    "scale": {"width_k": WK, "height_k": HK, "story_flat": STORY_FLAT, "door_h": DOOR_H},
    "bounds": [-126.0, -100.0, 112.0, 112.0],
    "boundary": [[-126.0, -100.0], [112.0, -100.0], [112.0, 112.0], [-126.0, 112.0]],
    "surfaces": [], "ground_holes": [], "slabs": [], "walls": [], "boxes": [], "columns": [],
    "stairs": [], "ramps": [], "lamps": [], "signs": [], "buildings": [], "spawns": [], "exits": [],
    "locations": [], "probe_routes": [],
    "filler": {"tints": ["6a6f75", "3a2a22", "b8b4a8", "2f6fa8", "9b7a2c", "5a5f66", "8a8070", "c9c3b2"],
               "items": [], "cover": [], "stories": []},
}
B = plan["buildings"]
F = plan["filler"]


def surface(sid: str, mat: str, x0: float, z0: float, x1: float, z1: float, y: float = 0.0, t: float = 0.08) -> None:
    plan["surfaces"].append({"id": sid, "mat": mat, "rect": [x0, z0, x1, z1], "y": y, "t": t})


def wall(x0: float, z0: float, x1: float, z1: float, y0: float, y1: float, mat: str = "wall") -> None:
    plan["walls"].append({"rect": [x0, z0, x1, z1], "y0": y0, "y1": y1, "mat": mat})


def box(x: float, y: float, z: float, sx: float, sy: float, sz: float, mat: str = "wall", yaw: float = 0.0, solid: bool = True) -> None:
    plan["boxes"].append({"at": [x, y, z], "size": [sx, sy, sz], "mat": mat, "yaw": yaw, "solid": solid})


def put(kit: str, x: float, z: float, yaw: float = 0.0, s: float = 1.0, dy: float = 0.0, tint: int = -1,
        roll: float = 0.0, cover: bool = False) -> None:
    item = [kit, round(x, 2), round(z, 2), round(yaw, 1)]
    if s != 1.0 or dy != 0.0 or tint >= 0 or roll != 0.0:
        item.append(s)
    if dy != 0.0 or tint >= 0 or roll != 0.0:
        item.append(round(dy, 3))
    if tint >= 0 or roll != 0.0:
        item.append(tint)
    if roll != 0.0:
        item.append(roll)
    F["items"].append(item)
    if cover:
        F["cover"].append([round(x, 1), round(z, 1)])


def building(bid: str, label: str, at: tuple, size: tuple, kind: str = "mass", floors: int = 1,
             story: float = STORY_RETAIL, yaw: float = 0.0, lift: float = 0.0, interior: str = "",
             loot_theme: str = "", loot_density: float = 0.0, region: str = "North", script: str = "build",
             extra: dict | None = None) -> None:
    B.append({"id": bid, "label": label, "at": [round(at[0], 2), round(at[1], 2)], "size": [size[0], size[1]],
              "floors": floors, "story_height": round(story, 3), "yaw": yaw, "kind": kind, "lift": lift,
              "interior": interior, "loot_theme": loot_theme, "loot_density": loot_density, "region": region,
              "script": script, "extra": extra or {}})


def flats(bid: str, label: str, at: tuple, size: tuple, floors: int, open_floors: int, story: float = STORY_FLAT,
          balconies: bool = True, glass: bool = False, lift: float = 0.0, region: str = "North", loot: float = 0.5) -> None:
    """Секция жилого дома / башня (src/blockout/flat_section.gd): квартиры, ядро, подъездная группа."""
    building(bid, label, at, size, "flats", floors, story, 0.0, lift, "", "home", loot, region, "flats",
             {"open_floors": open_floors, "balconies": balconies, "glass_bands": glass})


def sign(text: str, x: float, y: float, z: float, size: int = 56) -> None:
    plan["signs"].append({"text": text, "at": [x, y, z], "size": size})


# ============================================================ проспект: дорога, тротуары, бордюры
surface("road", "road", X_WEST, -ROAD_HALF, X_EAST + 9.0, ROAD_HALF)
surface("median", "grass", X_WEST + 8.0, -MEDIAN_HALF, X_EAST - 6.0, MEDIAN_HALF, 0.0, 0.2)
surface("walk_n", "walk", X_WEST, FN, X_EAST, -ROAD_HALF, 0.0, 0.15)
surface("walk_s", "walk", X_WEST, ROAD_HALF, X_EAST, FS, 0.0, 0.15)
box((X_WEST + X_EAST) * 0.5, 0.075, -ROAD_HALF + 0.1, X_EAST - X_WEST, 0.15, 0.2, "stripe")   # бордюры
box((X_WEST + X_EAST) * 0.5, 0.075, ROAD_HALF - 0.1, X_EAST - X_WEST, 0.15, 0.2, "stripe")
surface("cross_street", "road", X_EAST, -100.0, X_EAST + 9.0, 112.0)
# зебры и разметка
for xz in (-80.0, 62.0):
    for i in range(8):
        box(xz, 0.085, -ROAD_HALF + 1.1 + i * 2.2, 5.0, 0.02, 1.1, "stripe", 0.0, False)
    put("traffic_light", xz - 4.0, -ROAD_HALF - 0.6, 180.0)
    put("traffic_light", xz + 4.0, ROAD_HALF + 0.6, 0.0)
    put("sign_crossing", xz - 3.0, -ROAD_HALF - 1.2, 180.0)
    put("sign_crossing", xz + 3.0, ROAD_HALF + 1.2, 0.0)
for x in range(int(X_WEST) + 6, int(X_EAST) - 4, 4):
    for zl in (-5.0, 5.0):
        box(x + 1.0, 0.085, zl, 2.0, 0.02, 0.15, "stripe", 0.0, False)
# фонари на разделительной, деревья в решётках на тротуарах, столбики, урны
for x in range(-110, 100, 30):
    put("lamp", x, 0.0, 0.0)
for x in range(-108, 100, 14):
    put("tree_birch", x, FN + 1.6, rng.uniform(0, 360), rng.uniform(0.8, 1.1))
    put("tree_birch", x + 7, FS - 1.6, rng.uniform(0, 360), rng.uniform(0.8, 1.1))
for x in range(-100, 96, 6):
    put("bollard", x, -ROAD_HALF - 0.45, 0.0)
    put("bollard", x + 3, ROAD_HALF + 0.45, 0.0)
for x in range(-96, 96, 24):
    put("bin", x + 2.0, FN + 4.0, 0.0)
    put("bin", x - 2.0, FS - 4.0, 0.0)
put("manhole", -70.0, 6.0, 0.0)
put("manhole", 10.0, -6.5, 0.0)
put("manhole", 74.0, 6.2, 0.0)

# --- машины на проспекте (укрытия через 20–30 м) и разрывы обзора
for (x, z, yaw, tint) in [(-95, -6.5, 0, 0), (-66, 6.5, 2, 5), (-52, -6.5, -3, 0), (-30, 6.5, 8, 1), (-18, -6.5, 0, 6),
                          (2, 6.5, 0, 0), (18, -6.5, -5, 5), (48, -6.5, 0, 0), (70, 6.5, 0, 6), (84, -3, 20, 2)]:
    put("car", x, z, yaw, 1.0, 0.0, tint, 0.0, True)
put("truck_cab", 32.0, 3.5, 55.0, 1.0, 0.0, 2, 0.0, True)                       # фургон поперёк
put("bus_wreck", -56.0, -1.0, 62.0, 1.0, 0.0, 3, 0.0, True)                      # автобус поперёк у перехода
put("ktp", -9.0, 0.0, 0.0, 1.0, 0.0, -1, 0.0, True)                              # тумба на разделительной
put("billboard", -14.0, 0.0, 90.0)
for (x, z, yaw) in [(24, -5.5, 10), (28, 5.5, -15), (38, -6, 25), (40, 4, 5), (46, -1, 80)]:
    put("car", x, z, yaw, 1.0, 0.0, 5, 0.0, True)                                 # затор
put("billboard_fallen", 42.0, -9.5, 0.0, 1.0, 0.0, -1, 0.0, True)
sign("сгоревшая машина", -30.0, 2.6, 6.5, 40)

# --- перекрёсток с пробкой — граница на востоке
for z in range(-96, 108, 7):
    put("car", X_EAST + 4.5 + rng.uniform(-1.2, 1.2), z, 90 + rng.uniform(-8, 8), 1.0, 0.0, 5, 0.0, True)
put("bus_wreck", 96.0, -3.0, 35.0, 1.0, 0.0, 4, 80.0, True)                       # автобус на боку
for z in range(-96, 108, 30):
    put("lamp", X_EAST + 10.5, z, 90.0)

# ============================================================ кордон (запад)
for i in range(13):
    put("po2", X_WEST, -16.0 + 1.25 + i * 2.5, 0.0)
box(X_WEST, 1.3, 0.0, 0.3, 2.6, 8.4, "steel")                                    # закрытые ворота
for i in range(5):
    put("fbs", -112.0 + i * 4.5, -8.0 + (i % 2) * 7.0, 90.0, 1.0, 0.0, -1, 0.0, True)
for z in (-8.0, 8.0):
    put("sandbags", -117.0, z, 0.0, 1.0, 0.0, -1, 0.0, True)
put("cabin", -129.0, 18.0, 90.0)                                                  # КПП
box(-130.0, 4.0, -17.0, 4.0, 8.0, 4.0, "concrete")                               # вышка
box(-130.0, 9.2, -17.0, 5.0, 2.4, 5.0, "steel")
put("barrier_arm", -121.0, 4.6, 0.0)
sign("КПП ЧВК · назад нельзя", -118.0, 5.5, 0.0, 64)
# город за кордоном — декорация
for (x, z, w, d, fl) in [(-150, -70, 16, 22, 17), (-150, -35, 12, 18, 22), (-152, 40, 14, 24, 12), (-150, 78, 16, 20, 25)]:
    building("Outside_%d" % abs(z), "", (x, z), (w, d), "mass", fl, 3.0, 0.0, 0.0, "", "", 0.0, "Outside")
for (x, z, w, d, fl) in [(128, -60, 18, 26, 20), (128, -20, 16, 30, 24), (126, 50, 14, 28, 16), (128, 90, 20, 22, 19)]:
    building("Outside_E%d" % abs(z), "", (x, z), (w, d), "mass", fl, 3.0, 0.0, 0.0, "", "", 0.0, "Outside")

# ============================================================ север: ЖК «Панорама», проезд, паркинг −1, двор, сквер
RETAIL_D = 9.0
retail_zc = FN - RETAIL_D * 0.5                     # −20.2
slot = 2.0 * WK                                     # служебный проход за магазинами
apt_d = 26.0                                        # 20 м × 1,3 — глубина секции с угловыми квартирами
apt_zc = FN - RETAIL_D - slot - apt_d * 0.5         # −33.9
yard_z0 = apt_zc - apt_d * 0.5                       # −40.4 — начало двора
YARD_Z1 = -84.0
FENCE_Z = -80.0

# корпус 1: стрит-ритейл (кофейня, цветы, аптека, одежда), подъезд 3 этажа, башня 17 этажей
for (bid, label, x0, x1, interior, theme) in [("Coffee", "кофейня «Зерно»", -100, -84, "shop", "register"),
                                             ("Flowers", "цветы", -84, -74, "shop", "shelf"),
                                             ("Pharmacy", "аптека", -74, -60, "pharmacy", "pharmacy"),
                                             ("Clothes", "одежда «Modus»", -60, -40, "shop", "shelf")]:
    building(bid, label, ((x0 + x1) * 0.5, retail_zc), (x1 - x0, RETAIL_D), "hall", 1, STORY_RETAIL,
             0.0, 0.0, interior, theme, 0.6)
flats("Corpus1_A", "ЖК «Панорама», корпус 1 · подъезд 1 — 17 этажей", (-85.0, apt_zc), (30.0, apt_d), 17, 3)
flats("Corpus1_B", "ЖК «Панорама», корпус 1 · подъезд 2 — 17 этажей", (-55.0, apt_zc), (30.0, apt_d), 17, 3)
building("Canopy1", "козырёк", (-76.0, FN + 2.3), (48.0, 4.4), "canopy", 1, 3.6)
# проезд во двор: асфальт, шлагбаум, пандус в паркинг
surface("drive", "road", -29.0, yard_z0, -21.0, FN)
surface("drive_lawn_w1", "grass", -40.0, yard_z0, -38.0, FN, 0.0, 0.2)
surface("drive_lawn_w2", "grass", -32.0, yard_z0, -29.0, FN, 0.0, 0.2)
surface("drive_lawn_e", "grass", -21.0, yard_z0, -10.0, FN, 0.0, 0.2)
put("barrier_arm_up", -29.5, FN - 1.0, 90.0)
put("booth", -31.5, FN - 2.5, 0.0)
sign("проезд во двор ЖК · паркинг −1", -25.0, 4.5, FN - 3.0, 44)
RAMP_X0, RAMP_X1 = -37.5, -32.5
RAMP_Z0, RAMP_Z1 = -20.0, yard_z0                   # верх у проспекта, низ у двора
plan["ramps"].append({"x0": RAMP_X0, "x1": RAMP_X1, "z0": RAMP_Z0, "z1": RAMP_Z1, "y0": 0.0, "y1": PIT_Y, "mat": "concrete"})
plan["ground_holes"].append([RAMP_X0, RAMP_Z1 - 0.5, RAMP_X1, RAMP_Z0])
wall(RAMP_X0 - 0.3, RAMP_Z1, RAMP_X0, RAMP_Z0, PIT_Y - 0.4, 1.0, "concrete")        # борта траншеи пандуса
wall(RAMP_X1, RAMP_Z1, RAMP_X1 + 0.3, RAMP_Z0, PIT_Y - 0.4, 1.0, "concrete")
sign("пандус в паркинг −1", -35.0, 2.0, RAMP_Z0 + 2.0, 40)
# корпус 2: пекарня открыта, витрины закрыты, башня 25 этажей
building("Bakery", "пекарня", (-3.0, retail_zc), (14.0, RETAIL_D), "hall", 1, STORY_RETAIL, 0.0, 0.0, "shop", "grocery", 0.5)
building("Corpus2_Retail", "салон связи · ломбард · банк (витрины)", (27.0, retail_zc), (46.0, RETAIL_D), "mass", 1, STORY_RETAIL)
flats("Corpus2_A", "ЖК «Панорама», корпус 2 · подъезд 1 — 25 этажей (закрыт)", (5.0, apt_zc), (30.0, apt_d), 25, 0)
flats("Corpus2_B", "ЖК «Панорама», корпус 2 · подъезд 2 — 25 этажей (закрыт)", (35.0, apt_zc), (30.0, apt_d), 25, 0)
# инкассаторский броневик у банка — дорогая находка на виду
put("truck_cab", 40.0, -11.0, 95.0, 1.0, 0.0, 0, 0.0, True)
sign("броневик у банка", 40.0, 3.4, -11.0, 40)

# двор ЖК на плите паркинга: плита с вырезами под лестницы и пандус
PIT_X0, PIT_X1, PIT_Z0, PIT_Z1 = -92.0, 36.0, -78.0, yard_z0
STAIR_W = 1.2 * WK                                 # 1.56
stair_a = {"x": -68.0, "z_top": -62.0, "z_bot": -56.0}   # у подъезда корпуса 1 (низ ближе к дому)
stair_b = {"x": 20.0, "z_top": -63.5, "z_bot": -69.5}    # восточная, у мусорной площадки
holes = [[stair_a["x"] - STAIR_W * 0.5 - 0.2, stair_a["z_top"] - 1.0, stair_a["x"] + STAIR_W * 0.5 + 0.2, stair_a["z_bot"] + 0.3],
         [stair_b["x"] - STAIR_W * 0.5 - 0.2, stair_b["z_bot"] - 0.3, stair_b["x"] + STAIR_W * 0.5 + 0.2, stair_b["z_top"] + 1.0],
         [RAMP_X0, PIT_Z1 - 0.5, RAMP_X1, PIT_Z1 + 0.5]]
plan["slabs"].append({"id": "yard_slab", "rect": [-100.0, YARD_Z1, 50.0, yard_z0], "y_top": 0.0, "t": 0.4, "mat": "walk", "holes": holes})
plan["ground_holes"].append([PIT_X0 - 0.4, PIT_Z0 - 0.4, PIT_X1 + 0.4, PIT_Z1 + 0.4])
# паркинг −1: пол, стены, колонны, лестницы, аварийный свет
plan["slabs"].append({"id": "pit_floor", "rect": [PIT_X0 - 0.4, PIT_Z0 - 0.4, PIT_X1 + 0.4, PIT_Z1 + 0.4], "y_top": PIT_Y, "t": 0.4, "mat": "concrete", "holes": []})
wall(PIT_X0 - 0.4, PIT_Z0 - 0.4, PIT_X0, PIT_Z1 + 0.4, PIT_Y, -0.4, "concrete")
wall(PIT_X1, PIT_Z0 - 0.4, PIT_X1 + 0.4, PIT_Z1 + 0.4, PIT_Y, -0.4, "concrete")
wall(PIT_X0, PIT_Z0 - 0.4, PIT_X1, PIT_Z0, PIT_Y, -0.4, "concrete")
wall(PIT_X0, PIT_Z1, RAMP_X0, PIT_Z1 + 0.4, PIT_Y, -0.4, "concrete")                 # южная стена с проёмом пандуса
wall(RAMP_X1, PIT_Z1, PIT_X1, PIT_Z1 + 0.4, PIT_Y, -0.4, "concrete")
plan["columns"].append({"rect": [PIT_X0 + 4.0, PIT_Z0 + 4.0, PIT_X1 - 4.0, PIT_Z1 - 4.0], "y0": PIT_Y, "y1": -0.4, "grid": 8.0, "size": 0.5, "mat": "concrete"})
plan["stairs"].append({"from": [stair_a["x"], PIT_Y, stair_a["z_bot"]], "to": [stair_a["x"], 0.0, stair_a["z_top"]], "width": STAIR_W, "count": 20, "mat": "concrete"})
plan["stairs"].append({"from": [stair_b["x"], PIT_Y, stair_b["z_bot"]], "to": [stair_b["x"], 0.0, stair_b["z_top"]], "width": STAIR_W, "count": 20, "mat": "concrete"})
for (x, z) in [(stair_a["x"], stair_a["z_bot"] - 1.0), (stair_b["x"], stair_b["z_bot"] + 1.0), (-35.0, PIT_Z1 - 3.0), (-30.0, -60.0), (10.0, -58.0)]:
    plan["lamps"].append([x, -0.9, z, 0.6, 9.0])
sign("вход в подъезд 1", -85.0, 3.4, yard_z0 - 0.6, 40)
sign("вход в подъезд 2", -55.0, 3.4, yard_z0 - 0.6, 40)
# машины в паркинге и техпомещение
for i in range(9):
    put("car", PIT_X0 + 8.0 + i * 8.0, PIT_Z0 + 4.0, 0.0, 1.0, PIT_Y, (i * 3) % 8, 0.0, True)
for i in range(6):
    put("car", -60.0 + i * 8.0, PIT_Z1 - 9.0, 0.0, 1.0, PIT_Y, (i * 5) % 8, 0.0, True)
wall(24.0, PIT_Z0, 36.0, PIT_Z0 + 6.0, PIT_Y, -0.4, "wall")                         # техпомещение (закрыто)
sign("паркинг −1 · техпомещение", 30.0, -1.2, PIT_Z0 + 8.0, 36)
# двор: площадка, парковка жильцов, КТП, мусорка, забор с воротами, деревья
surface("playground", "court", -62.0, -66.0, -38.0, -50.0, 0.0, 0.1)
put("swing", -56.0, -58.0, 0.0)
put("slide", -46.0, -56.0, 90.0)
put("sandbox", -50.0, -62.0, 0.0)
for i in range(10):
    put("car", -90.0 + i * 7.2, -72.0, 90.0, 1.0, 0.0, (i * 2) % 8, 0.0, True)
for i in range(6):
    put("car", -10.0 + i * 7.2, -72.0, 90.0, 1.0, 0.0, (i * 4) % 8, 0.0, True)
put("ktp", 23.0, -46.5, 0.0, 1.0, 0.0, -1, 0.0, True)
for i in range(3):
    put("dumpster", 32.0 + i * 1.6, -66.0, 0.0, 1.0, 0.0, -1, 0.0, True)
for x in (-90, -70, -50, -30):
    put("tree_birch", x, -42.5, rng.uniform(0, 360), 1.0)
put("tree_poplar", 0.0, -60.0, 0.0, 1.1)
put("tree_poplar", 12.0, -70.0, 0.0, 0.9)
for i in range(60):
    x = -100.0 + 1.25 + i * 2.5
    if -24.0 < x < -16.0:
        continue
    put("po2", x, FENCE_Z, 90.0)
box(-20.0, 1.2, FENCE_Z, 0.3, 2.4, 0.3, "steel")                                   # створка ворот распахнута
sign("ворота двора · к насыпи", -20.0, 3.4, FENCE_Z, 44)
surface("north_lane", "road", -26.0, -100.0, -14.0, FENCE_Z)
# сквер
surface("square", "court", 56.0, -64.0, X_EAST, FN, 0.0, 0.12)
put("monument", 78.0, -40.0, 0.0, 1.0, 0.0, -1, 0.0, True)
sign("сквер · сухой фонтан", 78.0, 4.5, -40.0, 44)
for (x, z) in [(62, -22), (94, -22), (62, -58), (94, -58), (78, -20), (78, -60)]:
    put("tree_birch", x, z, rng.uniform(0, 360), 1.2)
for (x, z, yaw) in [(70, -32, 0), (86, -32, 0), (70, -48, 180), (86, -48, 180)]:
    put("bench", x, z, yaw)
    put("bin", x + 1.5, z, 0.0)
for x in range(58, 100, 7):
    put("flowerbed", x, -17.5, 0.0, 0.5)
put("food_kiosk", 90.0, -52.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("tent", 72.0, -44.0, 20.0)
put("tent", 84.0, -45.0, -30.0)
put("lamp_park", 66.0, -40.0, 0.0)
put("lamp_park", 90.0, -40.0, 0.0)

# ============================================================ юг: бизнес-центр, супермаркет, дом 7
building("Vershina_Podium", "ЖК «Вершина» · стилобат: банк, офисы, фитнес (закрыт)", (-94.0, FS + 18.0), (44.0, 36.0), "mass", 2, 4.0, 0.0, 0.0, "", "", 0.0, "South")
flats("Vershina_T1", "ЖК «Вершина», башня 1 — 40 этажей", (-106.0, FS + 10.5), (20.0, 20.0), 40, 0, 3.2, False, True, 8.3, "South", 0.0)
flats("Vershina_T2", "ЖК «Вершина», башня 2 — 34 этажа", (-82.0, FS + 10.5), (20.0, 20.0), 34, 0, 3.2, False, True, 8.3, "South", 0.0)
flats("Vershina_T3", "ЖК «Вершина», башня 3 — 46 этажей", (-105.0, 63.0), (22.0, 22.0), 46, 0, 3.2, False, True, 0.0, "South", 0.0)
flats("Vershina_T4", "ЖК «Вершина», башня 4 — 30 этажей", (-84.0, 92.0), (20.0, 20.0), 30, 0, 3.2, False, True, 0.0, "South", 0.0)
sign("ЖК «Вершина» · четыре башни на стилобате", -94.0, 10.0, FS + 1.0, 64)
put("bus_stop", -99.0, FS - 3.0, 180.0, 1.0, 0.0, -1, 0.0, True)
put("kiosk", -114.0, FS - 3.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("kiosk", -110.0, FS - 2.6, 0.0, 1.0, 0.0, -1, 0.0, True)
sign("ларьки · остановка", -112.0, 3.6, FS - 3.0, 36)
put("hedge", -116.0, FS + 0.6, 90.0)
put("hedge", -72.5, FS + 0.6, 90.0)
# задний двор бизнес-центра — заход «За бизнес-центром»
surface("bc_yard", "road", -116.0, FS + 36.0, -72.0, 100.0)
for i in range(3):
    put("dumpster", -100.0 + i * 1.6, 58.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("container40", -92.0, 72.0, 90.0, 1.0, 0.0, -1, 0.0, True)
put("truck", -110.0, 90.0, 0.0, 1.0, 0.0, -1, 0.0, True)
for i in range(19):
    z = 53.0 + 1.25 + i * 2.5
    if 76.0 < z < 82.0:
        continue
    put("po2", -72.0, z, 0.0)
# супермаркет «Ярус»: зал (фасад на север, вход с парковки), склад и рампа на юг
SM_X0, SM_X1, SM_Z0, SM_Z1 = -60.0, 20.0, 56.0, 96.0
building("Supermarket", "супермаркет «Ярус»", ((SM_X0 + SM_X1) * 0.5, (SM_Z0 + SM_Z1) * 0.5), (SM_X1 - SM_X0, SM_Z1 - SM_Z0),
         "hall", 1, 6.0, 180.0, 0.0, "supermarket", "grocery", 0.5, "South")
surface("parking", "parking", -70.0, FS, 30.0, SM_Z0)
sign("супермаркет «Ярус»", -20.0, 7.5, SM_Z0 - 0.5, 72)
for r in range(3):
    for i in range(9):
        cx = -62.0 + i * 8.0 + r * 2.0
        if rng.random() < 0.55 and not (-31.0 < cx < -21.0):
            put("car", cx, 24.0 + r * 11.0, 0.0, 1.0, 0.0, (i + r) % 8, 0.0, True)
for z in range(20, 52, 7):
    put("planter", -27.0, z, 0.0, 1.0, 0.0, -1, 0.0, True)
building("CartShelter", "навес тележек", (-32.0, 40.0), (8.0, 10.0), "canopy", 1, 2.8, 0.0, 0.0, "", "", 0.0, "South")
for i in range(4):
    put("cart", -33.0 + i * 1.2, 40.0 + (i % 2), rng.uniform(0, 360))
put("truck", -12.0, 42.0, 0.0, 1.0, 0.0, 2, 0.0, True)                            # фургон с открытым багажником
for i in range(3):
    put("suitcase", -10.0 + i * 0.8, 46.5, rng.uniform(0, 360))
for x in range(-66, 30, 24):
    put("lamp", x + 2.0, 36.0, 0.0)
put("tree_birch", -66.0, 50.0, 0.0, 1.0)
put("tree_birch", 26.0, 50.0, 0.0, 1.0)
# разгрузочный двор
surface("dock_yard", "road", SM_X0, SM_Z1, SM_X1, 106.0)
put("truck", -45.0, 100.0, 90.0, 1.0, 0.0, -1, 0.0, True)
put("trailer", -34.0, 100.0, 90.0, 1.0, 0.0, -1, 0.0, True)
for i in range(3):
    put("dumpster", 5.0 + i * 1.6, 103.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("pallets", -8.0, 99.0, 20.0)
put("pallets", -4.0, 102.0, 70.0)
for i in range(32):
    put("po2", SM_X0 + 1.25 + i * 2.5, 106.0, 90.0)
for i in range(20):
    z = SM_Z0 + 1.25 + i * 2.5
    if 96.0 < z < 100.5:
        continue
    put("po2", 20.0, z, 0.0)
sign("калитка в проезд", 20.0, 3.2, 98.0, 40)
surface("service_lane", "road", 22.0, FS, 32.0, 112.0)
sign("служебный проезд · к насыпи", 27.0, 4.0, 104.0, 44)
# дом 7: 9 этажей закрыт, минимаркет открыт
building("House7", "дом 7 — 9 эт. (закрыт)", (65.0, 61.0), (62.0, 18.0), "mass", 9, 3.0, 0.0, 0.0, "", "", 0.0, "South")
building("Minimarket", "минимаркет", (47.0, FS + RETAIL_D * 0.5), (26.0, RETAIL_D), "hall", 1, STORY_RETAIL, 180.0, 0.0, "shop", "grocery", 0.5, "South")
building("House7_Retail", "«Студия ногтей» · бар (витрины)", (78.0, FS + RETAIL_D * 0.5), (36.0, RETAIL_D), "mass", 1, STORY_RETAIL, 0.0, 0.0, "", "", 0.0, "South")
surface("house7_yard", "court", 34.0, FS + RETAIL_D, 96.0, 52.0, 0.0, 0.1)
for i in range(7):
    put("garage", 40.0 + i * 7.5, 49.0, 180.0, 1.0, 0.0, -1, 0.0, True)
put("dumpster", 90.0, 30.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("dumpster", 91.6, 30.0, 0.0)
put("bus_stop", 40.0, FS - 3.0, 180.0, 1.0, 0.0, -1, 0.0, True)
put("kiosk", 50.0, FS - 3.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("food_kiosk", 55.0, FS - 3.0, 0.0, 1.0, 0.0, -1, 0.0, True)
for x in (40, 60, 80):
    put("tree_birch", x, 30.0, rng.uniform(0, 360), 1.0)

# ============================================================ подземный переход под проспектом
TX0, TX1 = -48.0, -40.0                             # 6 м × 1,3 ≈ 8 — ширина тоннеля
TZ_N, TZ_S = -15.0, 15.0                            # траншея с площадками лестниц под тротуарами
TUN_N, TUN_S = -9.5, 9.5                            # тоннель под проезжей частью (крыша)
STAIR_Z = 11.0                                      # лестницы вдоль улицы: площадка z ±11…±15, ширина 4 (3 × 1,3)
plan["ground_holes"].append([TX0, TZ_N, TX1, TZ_S])
plan["slabs"].append({"id": "tunnel_floor", "rect": [TX0, TZ_N, TX1, TZ_S], "y_top": TUNNEL_Y, "t": 0.3, "mat": "concrete", "holes": []})
plan["slabs"].append({"id": "tunnel_roof", "rect": [TX0 - 0.4, TUN_N, TX1 + 0.4, TUN_S], "y_top": -0.1, "t": 0.4, "mat": "concrete", "holes": []})
wall(TX0 - 0.4, TZ_N, TX0, TZ_S, TUNNEL_Y, 0.0, "concrete")
wall(TX1, TZ_N, TX1 + 0.4, TZ_S, TUNNEL_Y, 0.0, "concrete")
wall(TX0, TZ_N - 0.4, TX1, TZ_N, TUNNEL_Y, 0.0, "concrete")
wall(TX0, TZ_S, TX1, TZ_S + 0.4, TUNNEL_Y, 0.0, "concrete")
for sgn in (-1.0, 1.0):
    zc = sgn * (STAIR_Z + 2.0)                       # ось лестницы z = ±13
    plan["stairs"].append({"from": [TX1, 0.15, zc], "to": [TX0 + 1.5, TUNNEL_Y, zc], "width": 3.8, "count": 20, "mat": "concrete"})   # верх вровень с тротуаром
    box((TX0 + 1.5 + TX1) * 0.5, -1.3, sgn * STAIR_Z, TX1 - (TX0 + 1.5), 4.6, 0.2, "steel")   # перила вдоль марша
    box((TX0 + TX1) * 0.5, 0.5, sgn * (TZ_S + 0.2), TX1 - TX0 + 0.8, 1.0, 0.4, "concrete")   # парапет у фасада
    box((TX0 - 0.4 + TX0 + 1.5) * 0.5, 0.5, sgn * STAIR_Z, 1.9, 1.0, 0.2, "concrete")          # парапет у площадки
    put("sign_crossing", TX1 + 0.8, sgn * 12.0, 0.0)
for z in (-5.0, 0.0, 5.0):
    put("kiosk", TX0 + 1.6, z, 90.0, 0.9, TUNNEL_Y, -1, 0.0, True)
put("suitcase", TX1 - 1.5, 3.0, 40.0, 1.0, TUNNEL_Y)
sign("подземный переход", TX1 + 1.5, 2.6, -13.0, 40)
sign("подземный переход", TX1 + 1.5, 2.6, 13.0, 40)
# дыры в тротуарах под лестницы (вдоль улицы, у фасада; у бордюра остаётся 2,5 м тротуара)
plan["walk_holes"] = [[TX0, TZ_N, TX1, -STAIR_Z], [TX0, STAIR_Z, TX1, TZ_S]]

# ============================================================ появление, выходы, места, подходы
plan["spawns"] = [{"id": "cordon", "label": "Кордон (старт пролога)", "at": [-104.0, 0.0]},
                  {"id": "yards", "label": "Дворы ЖК", "at": [-60.0, -92.0]},
                  {"id": "bc", "label": "За бизнес-центром", "at": [-100.0, 78.0]},
                  {"id": "square", "label": "Сквер", "at": [78.0, -68.0]}]
plan["exits"] = [{"label": "Дворами к насыпи", "at": [-20.0, -86.0], "always": True},
                 {"label": "Служебный проезд", "at": [27.0, 100.0], "always": True},
                 {"label": "Паркинг −1, пандус", "at": [-35.0, -24.0], "always": False}]
plan["locations"] = [
    {"id": 1, "label": "Кордон", "at": [-104.0, 0.0], "spawn": [-104.0, 0.0], "look": [-80.0, -10.0]},
    {"id": 2, "label": "Кофейня «Зерно»", "at": [-92.0, -20.0], "spawn": [-92.0, -10.0], "look": [-92.0, -20.0]},
    {"id": 3, "label": "Проезд и пандус", "at": [-25.0, -20.0], "spawn": [-25.0, -12.0], "look": [-33.0, -35.0]},
    {"id": 4, "label": "Двор ЖК · подъезд 1", "at": [-85.0, -62.0], "spawn": [-20.0, -62.0], "look": [-85.0, -56.0]},
    {"id": 5, "label": "Подземный переход", "at": [-44.0, 0.0], "spawn": [-36.0, -10.0], "look": [-47.0, -13.0]},
    {"id": 6, "label": "Парковка супермаркета", "at": [-20.0, 35.0], "spawn": [-44.0, 18.0], "look": [-20.0, 56.0]},
    {"id": 7, "label": "Супермаркет «Ярус»", "at": [-20.0, 76.0], "spawn": [-20.0, 52.0], "look": [-20.0, 76.0]},
    {"id": 8, "label": "Разгрузочный двор", "at": [-20.0, 100.0], "spawn": [-55.0, 101.0], "look": [20.0, 98.0]},
    {"id": 9, "label": "Сквер", "at": [78.0, -40.0], "spawn": [70.0, -12.0], "look": [78.0, -40.0]},
    {"id": 10, "label": "Дом 7", "at": [65.0, 40.0], "spawn": [47.0, 12.0], "look": [60.0, 45.0]},
]
sm_cx = (SM_X0 + SM_X1) * 0.5
plan["probe_routes"] = [
    {"id": "prologue", "label": "пролог: кордон → кофейня → переход → парковка → «Ярус» → склад → двор → проезд", "max_open_m": 30.0,
     "points": [[-104, 0], [-98, -6], [-98, -11], [-92, -12], [-92, -15], [-91, -18], [-91, -22], [-92, -15], [-92, -12], [-60, -12],
                [-52, -10], [-39.5, -10], [-39.5, -13], [-41.5, -13], [-47.3, -13], [-47.3, -9.5], [-44, 0], [-44, 8], [-47.3, 10], [-47.3, 13], [-41.5, 13], [-39.5, 13], [-34, 18], [-24, 30], [-24, 50],
                [sm_cx - 6, 54], [sm_cx - 6, 60], [sm_cx - 6, 72], [sm_cx - 6, 86], [sm_cx - 20, 88], [sm_cx - 20, 92.5],
                [sm_cx, 92.5], [sm_cx, 97.2], [10, 97.2], [18, 98], [27, 100]]},
    {"id": "yards_to_south", "label": "дворы ЖК → проезд → парковка → служебный проезд", "max_open_m": 30.0,
     "points": [[-60, -92], [-22, -86], [-20, -70], [-25, -44], [-25, -20], [-25, -12], [-25, 0], [-25, 14], [-24, 30],
                [-24, 52], [-64, 52], [-64, 80], [-64, 104.5], [0, 104.5], [12, 102], [18, 98], [27, 100]]},
    {"id": "square_to_north", "label": "сквер → проспект → двор ЖК → к насыпи", "max_open_m": 30.0,
     "points": [[78, -68], [66, -50], [66, -30], [66, -13], [0, -12], [-25, -12], [-25, -30], [-25, -44], [-20, -70], [-20, -82], [-20, -86]]},
    {"id": "bc_to_north", "label": "за бизнес-центром → вдоль «Яруса» → зебра → проезд → к насыпи", "max_open_m": 30.0,
     "points": [[-100, 78], [-80, 79], [-74, 79], [-69, 79], [-66, 70], [-66, 30], [-66, 14], [-77, 0], [-77, -10], [-40, -10], [-25, -12],
                [-25, -44], [-20, -70], [-20, -86]]},
    {"id": "parking_minus1", "label": "пандус → паркинг −1 → лестница во двор", "max_open_m": 0.0,
     "points": [[-25, -14], [-35, -18], [-35, -30], [-35, -45], [-35, -56], [-60, -58], [stair_a["x"], stair_a["z_bot"] + 0.8],
                [stair_a["x"], stair_a["z_top"] - 1.0], [stair_a["x"], -66]]},
    {"id": "corpus1_floor3", "label": "подъезд 1 корпуса 1: тамбур, вестибюль, холл, лестница на 3-й этаж", "max_open_m": 0.0,
     "points": [[-85, yard_z0 - 3.5], [-85, yard_z0 + 1.0], [-85, apt_zc - 8.5], [-85, apt_zc - 4.0], [-85, apt_zc], [-88.75, apt_zc + 0.5], [-88.75, apt_zc + 1.9],
                [-88.75, apt_zc + 3.0], [-88, apt_zc + 2.5], [-82, apt_zc + 2.5], [-81.25, apt_zc + 3.5], [-82, apt_zc + 4.5], [-88, apt_zc + 4.5],
                [-88.75, apt_zc + 3.5], [-88, apt_zc + 2.5], [-82, apt_zc + 2.5], [-81.25, apt_zc + 3.5], [-82, apt_zc + 4.5], [-88, apt_zc + 4.5],
                [-88.75, apt_zc + 3.5], [-88.75, apt_zc + 1.9], [-88.75, apt_zc + 0.5], [-85, apt_zc]], "min_y": 2 * STORY_FLAT - 0.5},
]
F["stories"] = [{"label": "пост ДПС: машина, конусы, щит «Внимание»", "at": [-66.0, 6.5], "height": 4.0},
                {"label": "бросили при погрузке: багажник и коробки", "at": [-12.0, 46.0], "height": 4.0},
                {"label": "тело под брезентом у ларька", "at": [-43.0, 3.0], "height": 1.5}]
for i in range(3):
    put("cone", -69.0 + i * 1.2, 4.0 + (i % 2) * 0.6, rng.uniform(0, 360))
put("road_barrier", -63.0, 8.0, 0.0)
put("cone", -45.0, 18.5, 0.0)
put("cone", 5.0, 14.0, 30.0)
put("tires", 60.0, 7.0, 0.0)
put("tires", -20.0, -7.0, 20.0)
# бумаги и мусор — мелочью (декали дороги у MallFiller нет, кладём коробки, сумки, пакеты)
for i in range(40):
    x = rng.uniform(X_WEST + 4, X_EAST - 2)
    z = rng.choice([rng.uniform(FN + 0.5, -ROAD_HALF - 0.6), rng.uniform(ROAD_HALF + 0.6, FS - 0.5)])
    put(rng.choice(["suitcase", "bags", "cart"]) if i % 5 == 0 else "bags", x, z, rng.uniform(0, 360), rng.uniform(0.6, 1.0))

# --- мусор: бумага, бутылки, банки, кучи у баков и ларьков (владелец: «нет мусора, клочков бумаги»)
for i in range(320):
    x = rng.uniform(X_WEST + 3, X_EAST + 6)
    r = rng.random()
    if r < 0.35:
        z = rng.uniform(FN + 0.3, -ROAD_HALF - 0.3)
    elif r < 0.7:
        z = rng.uniform(ROAD_HALF + 0.3, FS - 0.3)
    else:
        z = rng.uniform(-ROAD_HALF + 0.3, ROAD_HALF - 0.3)
    put("paper" if rng.random() < 0.7 else "paper_ball", x, z, rng.uniform(0, 360), rng.uniform(0.7, 1.2))
for (cx, cz, n) in [(-112, FS - 3, 25), (-99, FS - 3, 20), (40, FS - 3, 20), (52, FS - 3, 25), (-46.4, 0, 18), (90, -52, 20), (-20, 40, 40), (23, -46, 15)]:
    for i in range(n):
        put(rng.choice(["bottle", "can", "paper", "paper_ball", "bags"]), cx + rng.uniform(-6, 6), cz + rng.uniform(-4, 4), rng.uniform(0, 360), rng.uniform(0.6, 1.0),
            TUNNEL_Y if (cx, cz) == (-46.4, 0) else 0.0)
for (x, z) in [(34.0, -64.0), (-96.0, 60.0), (92.0, 33.0), (6.0, 101.5), (-62.0, 54.0), (58.0, 12.0)]:
    put("trash_pile", x, z, rng.uniform(0, 360), 1.0, 0.0, -1, 0.0, True)
    put("bags", x + 1.2, z + 0.8, rng.uniform(0, 360))
# ограждения: металлические вдоль бордюра у зебр и разделительной, переносные у кордона и въездов, бетон у тумбы
for xz in (-80.0, 62.0):
    for k in range(-5, 6):
        if k in (-1, 0, 1):
            continue
        put("ped_fence", xz + k * 2.1, -ROAD_HALF - 0.25, 90.0, 1.0, 0.0, -1, 0.0, k % 3 == 0)
        put("ped_fence", xz + k * 2.1, ROAD_HALF + 0.25, 90.0, 1.0, 0.0, -1, 0.0, k % 3 == 0)
for x in range(-60, -32, 2):                                   # до проезда во двор — там разрыв для пешеходов
    put("ped_fence", x + 1.0, -MEDIAN_HALF - 0.1, 90.0)
    put("ped_fence", x + 1.0, MEDIAN_HALF + 0.1, 90.0)
for i in range(7):
    put("crowd_barrier", -117.5 + (i % 2) * 0.8, -9.0 + i * 3.0, 0.0 + rng.uniform(-20, 20), 1.0, 0.0, -1, 0.0, True)
for i in range(4):
    put("crowd_barrier", -66.0 + i * 2.6, 17.0, 0.0 + rng.uniform(-10, 10), 1.0, 0.0, -1, 0.0, True)
for i in range(3):
    put("crowd_barrier", -38.5 + i * 2.6, FN - 0.6, 90.0, 1.0, 0.0, -1, 0.0, True)
    put("crowd_barrier", -18.5 + i * 2.6, FN - 0.6, 90.0, 1.0, 0.0, -1, 0.0, True)
for (x, z) in [(-15.0, -2.4), (-15.0, 2.4), (-3.0, -2.4), (-3.0, 2.4)]:
    put("jersey", x, z, 90.0, 1.0, 0.0, -1, 0.0, True)
for i in range(6):
    put("fbs", 80.0 + i * 3.0, -8.9 + (i % 2) * 0.8, 90.0, 1.0, 0.0, -1, 0.0, True)
for i in range(5):
    put("road_barrier", 60.0 + i * 2.4, 9.3, 90.0)
put("cone", -82.0, 9.5, 0.0)
put("cone", -78.5, 9.8, 0.0)
put("cone", 64.0, -9.6, 0.0)

plan["buildings_count"] = len(B)
plan["items_count"] = len(F["items"])

# ============================================================ запись
text = json.dumps(plan, ensure_ascii=False, indent=1)
text = re.sub(r"\[\s+((?:-?[\d.]+,\s+)*-?[\d.]+)\s+\]", lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]", text)
text = re.sub(r"\[\s+(\"[a-z_0-9]+\",(?:\s+-?[\d.]+,?)+)\s+\]", lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]", text)
OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
OUT_JSON.write_text(text + "\n", encoding="utf-8", newline="\n")


def tf(b: dict) -> str:
    yaw = math.radians(b["yaw"])
    c, s = math.cos(yaw), math.sin(yaw)
    return (f"transform = Transform3D({c:.5f}, 0, {-s:.5f}, 0, 1, 0, {s:.5f}, 0, {c:.5f}, "
            f"{b['at'][0]}, {b['lift']}, {b['at'][1]})")


scene = [
    '[gd_scene format=3]',
    '[ext_resource type="Script" path="res://src/blockout/prospekt_landscape.gd" id="land"]',
    '[ext_resource type="Script" path="res://src/blockout/study_building.gd" id="build"]',
    '[ext_resource type="Script" path="res://src/blockout/prospekt_study_level.gd" id="launch"]',
    '[ext_resource type="Script" path="res://src/blockout/mall_filler.gd" id="fill"]',
    '[ext_resource type="Script" path="res://src/blockout/flat_section.gd" id="flats"]',
    # освещение — своё, не из других карт (владелец 2026-10-24): физическое небо, низкое вечернее солнце с
    # запада-юго-запада, ACES, рассеянный свет неба с ровной подсветкой, SSIL, лёгкий туман
    '[sub_resource type="PhysicalSkyMaterial" id="SkyMat"]',
    'rayleigh_coefficient = 2.2', 'rayleigh_color = Color(0.26, 0.41, 0.58, 1)', 'mie_coefficient = 0.006',
    'mie_eccentricity = 0.82', 'mie_color = Color(0.69, 0.68, 0.62, 1)', 'turbidity = 8.0', 'sun_disk_scale = 2.0',
    'ground_color = Color(0.3, 0.28, 0.25, 1)', 'energy_multiplier = 1.6',
    '[sub_resource type="Sky" id="Sky"]', 'sky_material = SubResource("SkyMat")',
    '[sub_resource type="Environment" id="Environment"]',
    'background_mode = 2', 'sky = SubResource("Sky")',
    'ambient_light_source = 3', 'ambient_light_color = Color(0.62, 0.66, 0.74, 1)', 'ambient_light_sky_contribution = 0.5', 'ambient_light_energy = 0.9',
    'reflected_light_source = 2',
    'tonemap_mode = 3', 'tonemap_exposure = 1.05', 'tonemap_white = 6.0',
    'ssao_enabled = true', 'ssao_radius = 1.2', 'ssao_intensity = 1.6',
    # SDFGI в блокауте выключен: на сером материале он не успевал набрать свет и гасил рассеянный — тени чёрные;
    # для чистовой карты глобальное освещение подбирать отдельно (AGENTS.md, п. 10)
    'ssil_enabled = true', 'ssil_radius = 4.0', 'ssil_intensity = 1.0',
    'glow_enabled = true', 'glow_intensity = 0.25', 'glow_bloom = 0.04', 'glow_hdr_threshold = 1.4',
    'fog_enabled = true', 'fog_light_color = Color(0.74, 0.72, 0.7, 1)', 'fog_light_energy = 0.7', 'fog_density = 0.00028',
    'fog_sky_affect = 0.1', 'fog_height = -2.0', 'fog_height_density = 0.0',
    'adjustment_enabled = true', 'adjustment_contrast = 1.04', 'adjustment_saturation = 0.96',
    '[node name="ProspektStudy" type="Node3D"]',
    'script = ExtResource("launch")',
    'metadata/purpose = "Карта «Проспект» — серый блокаут 232 × 212 м · правило масштаба E (проходы × 1,3, высоты × 1,15, предметы 1:1)"',
    '[node name="WorldEnvironment" type="WorldEnvironment" parent="."]', 'environment = SubResource("Environment")',
    '[node name="EveningSun" type="DirectionalLight3D" parent="."]',
    'rotation_degrees = Vector3(-17, -118, 0)', 'light_color = Color(1, 0.8, 0.62, 1)', 'light_energy = 1.7',
    'light_angular_distance = 0.6', 'shadow_enabled = true', 'shadow_blur = 1.2', 'directional_shadow_max_distance = 260.0',
    'directional_shadow_split_1 = 0.08', 'directional_shadow_split_2 = 0.25', 'directional_shadow_split_3 = 0.55',
    '[node name="Landscape" type="Node3D" parent="."]', 'script = ExtResource("land")',
    '[node name="Filler" type="Node3D" parent="."]', 'script = ExtResource("fill")',
]
regions: list[str] = []
for b in B:
    if b["region"] not in regions:
        regions.append(b["region"])
for region in regions:
    scene.append(f'[node name="{region}" type="Node3D" parent="."]')
    for b in B:
        if b["region"] != region:
            continue
        lines = [f'[node name="{b["id"]}" type="Node3D" parent="{region}" groups=["mall_study_snap"]]', tf(b),
                 f'script = ExtResource("{b["script"]}")', f'kind = "{b["kind"] if b["script"] == "build" else "mass"}"',
                 f'footprint = Vector2({b["size"][0]}, {b["size"][1]})', f'floors = {b["floors"]}',
                 f'story_height = {b["story_height"]}', f'label = "{b["label"]}"']
        for key, val in b["extra"].items():
            lines.append(f'{key} = {str(val).lower() if isinstance(val, bool) else val}')
        if b["interior"]:
            lines += [f'interior = "{b["interior"]}"', f'loot_theme = "{b["loot_theme"]}"', f'loot_density = {b["loot_density"]}']
        if b["lift"]:
            lines.append(f'metadata/lift = {b["lift"]}')
        scene.extend(lines)
OUT_SCENE.write_text("\n\n".join(scene) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"buildings": len(B), "items": len(F["items"]), "cover": len(F["cover"]), "routes": len(plan["probe_routes"]),
                  "json": str(OUT_JSON.relative_to(ROOT)), "scene": str(OUT_SCENE.relative_to(ROOT))}, ensure_ascii=False))
