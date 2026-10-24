# -*- coding: utf-8 -*-
"""Серый блокаут карты «Проспект» (docs/design/prospekt_map.md), редакция 3 — улица с поворотом.

    python -X utf8 tools/build_prospekt.py
      → data/blockouts/prospekt.json и scenes/levels/prospekt_study.tscn (перезаписываются целиком)
    tools/prospekt_study.cmd                                                              — прогулка
    tools/godot.cmd --headless res://tools/prospekt_study.tscn -- verify                 — проверка
    tools/godot.cmd --windowed --resolution 1600x900 res://tools/prospekt_study.tscn -- shots — снимки

Замечания владельца 2026-10-24 к блокауту 2: дома стояли в метре от ларьков и остановок — отнести дальше, между
кофейней и домом — парковка, между остановкой и домом — территория; въезд в паркинг «как портал в ад» — сделать
настоящим въездом; карту увеличить и сделать «кишкообразной» — проспект идёт прямо и плавно поворачивает на 90°
направо; добавить окружение по Ready or Not и Escape from Tarkov («Эпицентр»); модели комплекта RING_Urban_95
владелец снял с блокаута (не текстурированы и не готовы как лоу-поли) — на их местах серые формы MallFiller и коробки.

Координаты игровые: x — восток, z — юг (север = −z). Проспект: западное плечо по z = 0 от кордона (x = −210)
до x = 0, поворот направо радиусом 55 вокруг (0, 55), южное плечо по x = 55 от z = 55 до тупика у z = 275.
Масштаб — правило 9 AGENTS.md: предметы 1:1, ширина проходов и помещений × 1,3 (WK), высоты жилья × 1,15 (HK).
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

WK = 1.3
HK = 1.15
RH = 8.5                       # полупроезжая часть 2+2 с разделительной
MED = 1.5
SW = 5.5 * WK                  # тротуар 7.15
F = RH + SW                    # 15.65 — край тротуара от оси
STORY_FLAT = 2.7 * HK
STORY_RETAIL = 4.0
DOOR_H = 2.1 * HK
PIT_Y = -3.2
TUNNEL_Y = -3.3

XW = -218.0                    # западный край карты
XC = -210.0                    # плиты кордона
CR = 55.0                      # радиус поворота
CX, CZ = 0.0, 55.0             # центр поворота
XS = CX + CR                   # ось южного плеча x = 55
ZS_END = 275.0

rng = random.Random(24)

plan: dict = {
    "version": 3,
    "purpose": "Карта «Проспект»: серый блокаут — проспект с поворотом на 90° направо, пролог и короткие рейды",
    "north": "-Z",
    "scale": {"width_k": WK, "height_k": HK, "story_flat": STORY_FLAT, "door_h": DOOR_H},
    "bounds": [-232.0, -126.0, 176.0, 290.0],
    "boundary": [[XW, -112.0], [160.0, -112.0], [160.0, ZS_END], [-55.0, ZS_END], [-55.0, 112.0], [XW, 112.0]],
    "surfaces": [], "ground_holes": [], "slabs": [], "walls": [], "boxes": [], "columns": [],
    "stairs": [], "ramps": [], "lamps": [], "signs": [], "buildings": [], "spawns": [], "exits": [],
    "locations": [], "probe_routes": [], "checks": {},
    "filler": {"tints": ["6a6f75", "3a2a22", "b8b4a8", "2f6fa8", "9b7a2c", "5a5f66", "8a8070", "c9c3b2", "d6a21e", "dcdcd6", "a5281f", "4f5a3b"],
               "items": [], "cover": [], "stories": []},
}
B = plan["buildings"]
FI = plan["filler"]

# ------------------------------------------------------------------ помощники

def surface(sid: str, mat: str, x0: float, z0: float, x1: float, z1: float, y: float = 0.0, t: float = 0.08) -> None:
    plan["surfaces"].append({"id": sid, "mat": mat, "rect": [min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1)], "y": y, "t": t})


def wall(x0: float, z0: float, x1: float, z1: float, y0: float, y1: float, mat: str = "wall") -> None:
    plan["walls"].append({"rect": [min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1)], "y0": y0, "y1": y1, "mat": mat})


def box(x: float, y: float, z: float, sx: float, sy: float, sz: float, mat: str = "wall", yaw: float = 0.0, solid: bool = True) -> None:
    plan["boxes"].append({"at": [round(x, 3), round(y, 3), round(z, 3)], "size": [round(sx, 3), round(sy, 3), round(sz, 3)],
                          "mat": mat, "yaw": round(yaw, 2), "solid": solid})


def put(kit: str, x: float, z: float, yaw: float = 0.0, s: float = 1.0, dy: float = 0.0, tint: int = -1,
        roll: float = 0.0, cover: bool = False) -> None:
    """Предмет наполнения MallFiller (серые наборы)."""
    item = [kit, round(x, 2), round(z, 2), round(yaw, 1)]
    if s != 1.0 or dy != 0.0 or tint >= 0 or roll != 0.0:
        item.append(s)
    if dy != 0.0 or tint >= 0 or roll != 0.0:
        item.append(round(dy, 3))
    if tint >= 0 or roll != 0.0:
        item.append(tint)
    if roll != 0.0:
        item.append(roll)
    FI["items"].append(item)
    if cover:
        FI["cover"].append([round(x, 1), round(z, 1)])


# Серые заменители: что стояло бы моделью Urban 95, ставится набором MallFiller (kit) или коробкой (ширина, высота,
# глубина, материал). Пусто — предмет в блокауте не нужен (мелкий декор).
U_KIT = {
    "U01_01_jersey": "jersey", "U01_06_jersey_rw": "jersey_rw", "U01_02_crowd": "crowd_barrier", "U01_03_crate": "pallets", "U01_04_cone": "cone",
    "U01_05_mesh_barrier": "crowd_barrier", "U02_02_planter": "planter", "U02_03_bench_tube": "bench", "U02_04_bollard": "bollard",
    "U02_05_bin_faceted": "bin", "U05_04_basket_bin": "bin", "U03_02_sandbags": "sandbags", "U03_03_parking_sign": "sign_parking",
    "U05_02_coffee_kiosk": "kiosk", "U06_02_crossing_sign": "sign_crossing", "U07_02_barrier_arm": "barrier_arm_up",
    "U07_03_guide_board": "delineator", "U07_04_tire_delineator": "tires", "U09_05_damaged_slab": "slab", "U10_02_twin_light": "lamp",
    "U10_05_billboard": "billboard", "U11_01_sound_fence": "fence", "U11_02_site_fence": "chainlink", "U11_03_dump_bed": "container20",
    "U11_04_privacy_screen": "fence", "U11_05_water_barrier": "water_barrier", "U12_03_single_light": "lamp", "U13_01_medical_tent": "tent",
    "U13_05_medical_cart": "cart", "U14_01_hatchback": "car", "R04_car": "car", "U15_02_traffic_light": "traffic_light",
    "U15_04_detour_board": "road_barrier", "U18_01_tank": "trailer", "U19_04_square_light": "lamp_park", "U19_05_belt_post": "bollard",
    "R02_dumpster": "dumpster", "R05_kiosk": "food_kiosk", "U14_02_plywood_case": "suitcase", "U10_03_wayfinding": "sign_bus",
}
U_BOX = {
    "U03_01_lightbox": (1.16, 2.08, 0.3, "accent"), "U03_05_street_cabinet": (0.9, 1.57, 0.46, "steel"),
    "U04_01_turnstile": (0.3, 1.08, 1.03, "steel"), "U04_04_coffee_table": (0.88, 0.42, 0.88, "accent"),
    "U05_01_guard_booth": (2.22, 2.62, 2.02, "wall"), "U06_03_guardrail": (3.4, 0.74, 0.33, "steel"),
    "U07_01_ticket_machine": (0.45, 1.26, 0.42, "steel"), "U07_05_lane_island": (4.8, 0.19, 1.0, "concrete"),
    "U08_01_revolving_door": (2.6, 2.8, 2.6, "dark"), "U08_04_curtainwall": (4.0, 3.1, 0.25, "dark"),
    "U08_05_glass_railing": (2.5, 1.04, 0.12, "dark"), "U09_01_hedgehog": (1.4, 1.4, 1.4, "rust"),
    "U09_02_concrete_cube": (1.2, 0.87, 0.85, "concrete"), "U09_03_logo_pylon": (1.0, 2.8, 0.42, "accent"),
    "U09_04_plaza_seat": (2.2, 0.55, 0.7, "concrete"), "U10_04_bench_stone": (2.0, 0.49, 0.56, "concrete"),
    "U12_01_wave_facade": (7.0, 1.4, 0.95, "wall"), "U12_02_checkpoint_cabinet": (0.73, 1.4, 0.55, "steel"),
    "U12_04_lit_parapet": (2.5, 0.75, 0.42, "concrete"), "U13_02_medical_screen": (1.76, 1.79, 0.29, "wall"),
    "U13_04_stretcher": (0.65, 0.68, 2.06, "steel"), "U15_01_checkpoint_cage": (2.13, 2.2, 2.13, "steel"),
    "U15_03_generator": (1.65, 1.27, 1.03, "steel"), "U16_01_atm": (0.73, 1.51, 0.72, "steel"), "R03_atm": (0.8, 1.41, 0.45, "steel"),
    "U16_02_bank_kiosk": (0.6, 1.65, 0.6, "steel"), "U16_03_armchair": (0.74, 0.85, 0.71, "accent"),
    "U16_05_teller_desk": (1.6, 1.25, 0.86, "accent"), "U17_04_credenza": (2.4, 0.85, 0.46, "accent"),
    "U18_02_loading_shutter": (3.9, 3.2, 0.28, "steel"), "U18_04_service_cage": (1.74, 1.74, 0.88, "steel"),
    "U19_03_relief_wall": (3.0, 3.1, 0.32, "concrete"), "U14_04_entry_steps": (4.9, 0.5, 2.7, "concrete"),
}
CAR_TINTS = [0, 2, 3, 5, 6, 7]


def u(aid: str, x: float, z: float, yaw: float = 0.0, s: float = 1.0, y: float = 0.0, cover: bool = False) -> None:
    """Предмет улицы серой формой (на месте бывшей модели Urban 95). yaw — куда смотрит лицевая сторона."""
    if aid in U_KIT:
        kit = U_KIT[aid]
        tint = rng.choice(CAR_TINTS) if kit == "car" else -1
        put(kit, x, z, yaw, s, y, tint, 0.0, cover)
    elif aid in U_BOX:
        w, h, d, mat = U_BOX[aid]
        box(x, y + h * s * 0.5, z, w * s, h * s, d * s, mat, yaw, True)
        if cover:
            FI["cover"].append([round(x, 1), round(z, 1)])


def face(fx: float, fz: float) -> float:
    """Угол поворота, при котором лицевая сторона (+Z модели) смотрит в направлении (fx, fz)."""
    return math.degrees(math.atan2(fx, fz))


def building(bid: str, label: str, at: tuple, size: tuple, kind: str = "mass", floors: int = 1,
             story: float = STORY_RETAIL, yaw: float = 0.0, lift: float = 0.0, interior: str = "",
             loot_theme: str = "", loot_density: float = 0.0, region: str = "West", script: str = "build",
             extra: dict | None = None) -> None:
    B.append({"id": bid, "label": label, "at": [round(at[0], 2), round(at[1], 2)], "size": [size[0], size[1]],
              "floors": floors, "story_height": round(story, 3), "yaw": yaw, "kind": kind, "lift": lift,
              "interior": interior, "loot_theme": loot_theme, "loot_density": loot_density, "region": region,
              "script": script, "extra": extra or {}})


def flats(bid: str, label: str, at: tuple, floors: int, open_floors: int, yaw: float = 0.0, size: tuple = (30.0, 26.0),
          story: float = STORY_FLAT, balconies: bool = True, glass: bool = False, lift: float = 0.0, region: str = "West",
          loot: float = 0.5) -> None:
    building(bid, label, at, size, "flats", floors, story, yaw, lift, "", "home", loot, region, "flats",
             {"open_floors": open_floors, "balconies": balconies, "glass_bands": glass})


def sign(text: str, x: float, y: float, z: float, size: int = 56) -> None:
    plan["signs"].append({"text": text, "at": [round(x, 2), y, round(z, 2)], "size": size})


def curve_point(phi: float, d: float) -> tuple[float, float]:
    """Точка поворота: phi — 0…π/2 от начала поворота, d — сдвиг влево от оси (наружу поворота)."""
    r = CR + d
    return CX + r * math.sin(phi), CZ - r * math.cos(phi)


def curve_strip(d0: float, d1: float, mat: str, t: float, y: float = 0.0, n: int = 28, solid: bool = True) -> None:
    """Полоса поворота от d0 до d1 (сдвиги влево от оси) — повёрнутыми коробками внахлёст."""
    dm = (d0 + d1) * 0.5
    width = abs(d1 - d0)
    for i in range(n):
        a0 = (math.pi * 0.5) * i / n
        a1 = (math.pi * 0.5) * (i + 1) / n
        am = (a0 + a1) * 0.5
        x, z = curve_point(am, dm)
        length = (CR + max(d0, d1)) * (a1 - a0) * 1.04 + 0.05
        # касательная (cos, sin) → длинная ось коробки по X; поворот вокруг Y на −am
        box(x, y + t * 0.5, z, length, t, width, mat, -math.degrees(am), solid)


def along(step: float, d: float, s0: float = 0.0, skip=None):
    """Точки вдоль всей оси (запад → поворот → юг) с шагом step, сдвиг d влево; (x, z, курс)."""
    out = []
    L1 = 0.0 - XW
    Lc = CR * math.pi * 0.5
    L2 = ZS_END - CZ
    s = s0
    while s < L1 + Lc + L2:
        if s < L1:
            x, z, h = XW + s, -d, 90.0
        elif s < L1 + Lc:
            phi = (s - L1) / CR
            x, z = curve_point(phi, d)
            h = 90.0 - math.degrees(phi)
        else:
            x, z, h = XS + d, CZ + (s - L1 - Lc), 0.0
        if skip is None or not skip(x, z):
            out.append((x, z, h))
        s += step
    return out


def in_rect(x: float, z: float, r: list) -> bool:
    return r[0] <= x <= r[2] and r[1] <= z <= r[3]


# ================================================================== проспект
# западное плечо
surface("road_w", "road", XW, -RH, 0.0, RH)
surface("median_w", "grass", XC + 12.0, -MED, -1.0, MED, 0.0, 0.2)
surface("walk_wn", "walk", XW, -F, 0.0, -RH, 0.0, 0.15)
surface("walk_ws", "walk", XW, RH, 0.0, F, 0.0, 0.15)
box((XW + 0.0) * 0.5, 0.075, -RH + 0.1, -XW, 0.15, 0.2, "stripe")
box((XW + 0.0) * 0.5, 0.075, RH - 0.1, -XW, 0.15, 0.2, "stripe")
# поворот
curve_strip(-RH, RH, "road", 0.08)
curve_strip(-MED, MED, "grass", 0.2)
curve_strip(RH, F, "walk", 0.15)
curve_strip(-F, -RH, "walk", 0.15)
curve_strip(RH - 0.2, RH, "stripe", 0.15)
curve_strip(-RH, -RH + 0.2, "stripe", 0.15)
# южное плечо
surface("road_s", "road", XS - RH, CZ, XS + RH, ZS_END)
surface("median_s", "grass", XS - MED, CZ + 1.0, XS + MED, 248.0, 0.0, 0.2)
surface("walk_se", "walk", XS + RH, CZ, XS + F, ZS_END, 0.0, 0.15)
surface("walk_sw", "walk", XS - F, CZ, XS - RH, ZS_END, 0.0, 0.15)
box(XS + RH - 0.1, 0.075, (CZ + ZS_END) * 0.5, 0.2, 0.15, ZS_END - CZ, "stripe")
box(XS - RH + 0.1, 0.075, (CZ + ZS_END) * 0.5, 0.2, 0.15, ZS_END - CZ, "stripe")
# разметка — пунктир полос по всей оси
for (x, z, h) in along(4.0, 5.0, 8.0):
    box(x, 0.085, z, 0.15, 0.02, 2.0, "stripe", h, False)
for (x, z, h) in along(4.0, -5.0, 8.0):
    box(x, 0.085, z, 0.15, 0.02, 2.0, "stripe", h, False)

# переходы: зебра у проезда во двор (запад) и на южном плече; светофоры, знаки, тактильная плитка
CROSS_W = -126.0
CROSS_S = 150.0
for i in range(8):
    box(CROSS_W, 0.085, -RH + 1.1 + i * 2.2, 5.0, 0.02, 1.1, "stripe", 0.0, False)
    box(XS - RH + 1.1 + i * 2.2, 0.085, CROSS_S, 1.1, 0.02, 5.0, "stripe", 0.0, False)
for (x, z, yaw) in [(CROSS_W - 4.0, -RH - 0.6, 180.0), (CROSS_W + 4.0, RH + 0.6, 0.0)]:
    u("U15_02_traffic_light", x, z, yaw)
    u("U06_02_crossing_sign", x + (-2.5 if yaw == 180 else 2.5), z + (-0.8 if yaw == 180 else 0.8), yaw)
    for k in (-1, 0, 1):
        u("U05_05_tactile", CROSS_W + k * 0.6, z + (-0.6 if yaw == 180 else 0.6), 0.0)
for (x, z, yaw) in [(XS - RH - 0.6, CROSS_S + 4.0, 90.0), (XS + RH + 0.6, CROSS_S - 4.0, -90.0)]:
    u("U15_02_traffic_light", x, z, yaw)
    u("U06_02_crossing_sign", x + (-0.8 if yaw == 90 else 0.8), z, yaw)
# светофоры на консоли над проезжей частью (Г-образная опора) и полусферы по краю тротуара у зебр
put("signal_arm", CROSS_W - 6.5, -RH - 1.2, 0.0, 1.0, 0.0, -1, 0.0, True)
put("signal_arm", CROSS_W + 6.5, RH + 1.2, 180.0, 1.0, 0.0, -1, 0.0, True)
put("signal_arm", XS - RH - 1.2, CROSS_S + 6.5, 90.0, 1.0, 0.0, -1, 0.0, True)
put("signal_arm", XS + RH + 1.2, CROSS_S - 6.5, -90.0, 1.0, 0.0, -1, 0.0, True)
for k in (-2, -1, 1, 2):
    for zz in (-RH - 0.5, RH + 0.5):
        put("half_sphere", CROSS_W + k * 3.2 + (0.0 if abs(k) == 1 else 1.0), zz, 0.0, 1.0, 0.0, -1, 0.0, True)
    for xx in (XS - RH - 0.5, XS + RH + 0.5):
        put("half_sphere", xx, CROSS_S + k * 3.2, 0.0, 1.0, 0.0, -1, 0.0, True)

# ------------------------------------------------------------------ подземный переход (западное плечо)
TX0, TX1 = -160.0, -152.0
TZN, TZS = -15.0, 15.0
TUN = 9.5
STAIR_Z = 11.0
plan["ground_holes"].append([TX0, TZN, TX1, TZS])
plan["slabs"].append({"id": "tunnel_floor", "rect": [TX0, TZN, TX1, TZS], "y_top": TUNNEL_Y, "t": 0.3, "mat": "concrete", "holes": []})
plan["slabs"].append({"id": "tunnel_roof", "rect": [TX0 - 0.4, -TUN, TX1 + 0.4, TUN], "y_top": -0.1, "t": 0.4, "mat": "concrete", "holes": []})
wall(TX0 - 0.4, TZN, TX0, TZS, TUNNEL_Y, 0.0, "concrete")
wall(TX1, TZN, TX1 + 0.4, TZS, TUNNEL_Y, 0.0, "concrete")
wall(TX0, TZN - 0.4, TX1, TZN, TUNNEL_Y, 0.0, "concrete")
wall(TX0, TZS, TX1, TZS + 0.4, TUNNEL_Y, 0.0, "concrete")
for sgn in (-1.0, 1.0):
    zc = sgn * (STAIR_Z + 2.0)
    plan["stairs"].append({"from": [TX1, 0.15, zc], "to": [TX0 + 1.5, TUNNEL_Y, zc], "width": 3.8, "count": 20, "mat": "concrete"})
    box((TX0 + 1.5 + TX1) * 0.5, -1.3, sgn * STAIR_Z, TX1 - (TX0 + 1.5), 4.6, 0.2, "steel")
    box((TX0 + TX1) * 0.5, 0.5, sgn * (TZS + 0.2), TX1 - TX0 + 0.8, 1.0, 0.4, "concrete")
    box((TX0 - 0.4 + TX0 + 1.5) * 0.5, 0.5, sgn * STAIR_Z, 1.9, 1.0, 0.2, "concrete")
    u("U03_04_handrail_slope", (TX0 + 1.5 + TX1) * 0.5, sgn * (STAIR_Z + 0.25), 90.0 if sgn > 0 else -90.0)
    sign("подземный переход", TX1 + 1.5, 2.6, sgn * 13.0, 40)
    u("U10_03_wayfinding", TX1 + 2.0, sgn * 10.6, 90.0)
for z in (-5.0, 0.0, 5.0):
    put("kiosk", TX0 + 1.6, z, 90.0, 0.9, TUNNEL_Y, -1, 0.0, True)
u("U18_03_industrial_light", (TX0 + TX1) * 0.5, -4.0, 0.0, 1.0, -0.6)
u("U18_03_industrial_light", (TX0 + TX1) * 0.5, 4.0, 0.0, 1.0, -0.6)
plan["lamps"].append([(TX0 + TX1) * 0.5, -0.9, 0.0, 0.5, 8.0])
plan["walk_holes"] = [[TX0, TZN, TX1, -STAIR_Z], [TX0, STAIR_Z, TX1, TZS]]
FI["stories"].append({"label": "тело под брезентом у ларька в переходе", "at": [TX1 - 1.5, 3.0], "height": 1.5})

# ------------------------------------------------------------------ уличная мебель вдоль всей оси
BUSY = [[TX0 - 2.0, -16.0, TX1 + 2.0, 16.0],                 # переход
        [CROSS_W - 4.0, -16.0, CROSS_W + 4.0, 16.0],
        [XS - 16.0, CROSS_S - 4.0, XS + 16.0, CROSS_S + 4.0],
        [XC - 10.0, -16.0, XC + 14.0, 16.0],                  # кордон
        [-122.0, -16.0, -110.0, -8.0],                        # въезд в паркинг
        [XS - 16.0, 245.0, XS + 16.0, 276.0]]                 # тупик на юге


def busy(x: float, z: float) -> bool:
    return any(in_rect(x, z, r) for r in BUSY)


for (x, z, h) in along(30.0, 0.0, 22.0, busy):
    u("U10_02_twin_light", x, z, h)
for side in (1.0, -1.0):
    for (x, z, h) in along(14.0, side * (F - 1.6), 9.0 if side > 0 else 16.0, busy):
        put("tree_birch", x, z, rng.uniform(0, 360), rng.uniform(0.8, 1.1))
    for (x, z, h) in along(5.5, side * (RH + 0.45), 3.0, busy):
        u("U02_04_bollard", x, z, h)
    for (x, z, h) in along(40.0, side * (RH + 0.5), 12.0, busy):
        u("U06_05_drain", x, z, h + 90.0)
    for (x, z, h) in along(26.0, side * (F - 3.2), 20.0, busy):
        u(rng.choice(["U05_04_basket_bin", "U02_05_bin_faceted"]), x, z, h)
    for (x, z, h) in along(60.0, side * (F - 0.8), 34.0, busy):
        u("U03_05_street_cabinet", x, z, h + (180.0 if side > 0 else 0.0))
    for (x, z, h) in along(90.0, side * (F - 2.2), 48.0 if side > 0 else 70.0, busy):
        put("ad_column", x, z, h, 1.0, 0.0, -1, 0.0, True)                # афишные тумбы
# отбойник по внешней кромке поворота и деревья в решётках на тротуаре поворота уже стоят; ограждение у бордюра поворота
for i in range(10):
    phi = (math.pi * 0.5) * (i + 0.5) / 10
    x, z = curve_point(phi, RH + 0.3)
    u("U06_03_guardrail", x, z, -math.degrees(phi), 1.0, 0.0, False)

# ------------------------------------------------------------------ машины на проезжей части и разрывы обзора
ROAD_CARS = [(-170, 6.0, 87, 1), (-140, -6.0, 95, 0), (-104, 6.0, 90, 1), (-12, 5.5, 88, 1)]
for (x, z, yaw, k) in ROAD_CARS:
    u("R04_car" if k else "U14_01_hatchback", x, z, yaw, 1.0, 0.0, True)
put("bus_city", -142.0, -1.0, 62.0, 1.0, 0.0, 8, 0.0, True)       # жёлтый автобус поперёк у перехода
# разбор Таркова и Ready or Not (prospekt_dressing.md § 7): машины разных классов, каждая — сценка с мелочью вокруг
put("paz", -193.0, 5.6, 92.0, 1.0, 0.0, 8, 0.0, True)                # маршрутный ПАЗ у остановки, двери открыты
put("ambulance", -190.0, -5.4, 97.0, 1.0, 0.0, -1, 0.0, True)       # скорая у пункта эвакуации на кордоне
put("tent", -197.0, -12.4, 90.0)
for (x, z) in [(-194.5, -11.0), (-195.2, -13.6), (-198.8, -10.6)]:
    put("suitcase", x, z, rng.uniform(0, 360))
put("water_bottles", -199.5, -13.4, 30.0)
FI["stories"].append({"label": "пункт эвакуации у кордона: скорая, палатка, чемоданы", "at": [-193.0, -9.0], "height": 4.0})
# перевёрнутый автобус на боку поперёк северной полосы: сумки, конусы, бумаги
put("bus_city", -78.0, -3.6, 96.0, 1.0, 0.0, 9, 90.0, True)
for (x, z, kit) in [(-71.0, -7.2, "suitcase"), (-73.0, -6.8, "bags"), (-85.5, -6.6, "cone"), (-84.0, -1.2, "cone"),
                    (-70.5, -1.5, "boxes"), (-82.0, -7.4, "suitcase")]:
    put(kit, x, z, rng.uniform(0, 360))
FI["stories"].append({"label": "перевёрнутый автобус: эвакуация не доехала", "at": [-78.0, -3.6], "height": 4.5})
# авария: такси врезалось в маршрутку, дверь открыта
put("taxi", -63.5, 4.8, 122.0, 1.0, 0.0, 8, 0.0, True)
put("minibus", -58.8, 6.3, 88.0, 1.0, 0.0, 9, 0.0, True)
for k in range(10):
    put("paper", -62.0 + rng.uniform(-3, 3), 3.0 + rng.uniform(-2, 2), rng.uniform(0, 360))
FI["stories"].append({"label": "авария: такси в маршрутке", "at": [-61.0, 5.5], "height": 3.0})
# пожарная у корпуса 2: район закрыли после пожара — рукава тянутся к дому
put("fire_truck", -91.0, -5.6, 92.0, 1.0, 0.0, -1, 0.0, True)
put("fire_hose", -88.0, -7.5, 180.0)
put("fire_hose", -93.0, -7.6, 200.0)
FI["stories"].append({"label": "пожарная: рукава к корпусу 2", "at": [-91.0, -5.6], "height": 4.0})
put("ktp", -96.0, 0.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("billboard", -100.0, 0.0, 90.0)
for (x, z, yaw) in [(-46, -5.5, 100), (-42, 5.5, 75), (-34, -6, 115), (-30, 4, 95)]:
    u("U14_01_hatchback", x, z, yaw, 1.0, 0.0, True)                # затор перед поворотом
put("taxi", -51.0, 2.4, 70.0, 1.0, 0.0, 8, 0.0, True)
put("truck_cab", -38.0, 0.0, 55.0, 1.0, 0.0, 2, 0.0, True)
# в повороте — сгоревшая машина и перевёрнутый фургон, щит упал на проезжую часть
x, z = curve_point(0.55, 4.0)
put("car", x, z, 30.0, 1.0, 0.0, 1, 0.0, True)
sign("сгоревшая машина", x, 2.4, z, 40)
x, z = curve_point(0.95, -4.5)
put("truck_cab", x, z, -20.0, 1.0, 0.0, 6, 85.0, True)
x, z = curve_point(1.25, 3.0)
put("billboard_fallen", x, z, 40.0, 1.0, 0.0, -1, 0.0, True)
# южное плечо: машины, пост ДПС с конусами
for (z, dx, yaw, k) in [(80, -5.5, 2, 1), (102, 6.0, 178, 0), (128, -6.0, -3, 0), (175, 5.5, 183, 1), (196, -5.8, 0, 0), (222, 6.0, 176, 1)]:
    u("R04_car" if k else "U14_01_hatchback", XS + dx, z, yaw, 1.0, 0.0, True)
put("police_car", XS - 6.0, 110.0, 8.0, 1.0, 0.0, -1, 0.0, True)
put("paz_police", XS + 5.8, 117.0, 182.0, 1.0, 0.0, -1, 0.0, True)
for (x, z, yaw, kit) in [(XS - 2.6, 103.8, 90.0, "water_barrier"), (XS - 1.3, 103.9, 85.0, "water_barrier_w"),
                         (XS + 2.4, 112.0, 95.0, "water_barrier"), (XS + 3.7, 112.2, 90.0, "water_barrier_w")]:
    put(kit, x, z, yaw, 1.0, 0.0, -1, 0.0, True)
for k in range(5):
    u("U01_04_cone", XS - 3.5 + k * 0.8, 106.0 + (k % 2) * 0.6, rng.uniform(0, 360))
u("U05_03_warning_a", XS - 2.0, 112.5, 30.0)
FI["stories"].append({"label": "пост ДПС: полицейская, ПАЗ полиции, барьеры", "at": [XS - 6.0, 110.0], "height": 4.0})
# дорожные работы на западной полосе: каток, самосвал, сетка со знаками, конусы, вскрытый асфальт
put("roller", XS - 5.2, 88.0, 4.0, 1.0, 0.0, -1, 0.0, True)
put("dump_truck", XS - 4.8, 96.5, 176.0, 1.0, 0.0, 4, 0.0, True)
for z in (84.0, 87.6, 91.2):
    put("mesh_sign", XS - 2.2, z, 0.0, 1.0, 0.0, -1, 0.0, True)
for k in range(5):
    put("cone", XS - 7.6 + k * 0.6, 82.5 - k * 0.2, rng.uniform(0, 360))
box(XS - 5.0, 0.09, 91.0, 4.5, 0.02, 7.0, "dark", 0.0, False)
FI["stories"].append({"label": "дорожные работы: каток и самосвал", "at": [XS - 5.0, 92.0], "height": 3.6})
put("flatbed", XS - 5.6, 118.0, 2.0, 1.0, 0.0, 9, 0.0, True)       # бортовая у «24 часа»

# ================================================================== кордон (запад)
for i in range(14):
    put("po2", XC, -17.5 + 1.25 + i * 2.5, 0.0)
box(XC, 1.3, 0.0, 0.3, 2.6, 8.4, "steel")
u("U07_02_barrier_arm", XC + 1.5, 5.5, -90.0)
for (x, z) in [(-204, -6.5), (-200, 4.0), (-196, -3.0)]:
    u("U01_01_jersey", x, z, 0.0, 1.0, 0.0, True)
for (x, z) in [(-206, 7.0), (-205, -2.0), (-207, 2.5)]:
    u("U09_01_hedgehog", x, z, rng.uniform(0, 90), 1.0, 0.0, True)
for (x, z) in [(-204, -12.0), (-204, 12.0)]:
    u("U03_02_sandbags", x, z, 90.0, 1.0, 0.0, True)
u("U15_01_checkpoint_cage", -206.5, -13.0, 90.0, 1.0, 0.0, True)
u("U05_01_guard_booth", -214.0, -22.0, 90.0, 1.0, 0.0, True)
u("U15_03_generator", -213.0, -27.0, 0.0, 1.0, 0.0, True)
u("U15_05_power_cable", -210.5, -25.0, 30.0)
u("U12_02_checkpoint_cabinet", -208.0, -24.5, 90.0, 1.0, 0.0, True)
for z in (-20.0, 20.0):
    u("U12_03_single_light", -208.0, z, 90.0)
for i in range(4):
    u("U01_02_crowd", -201.0 + (i % 2) * 0.8, -14.0 + i * 2.6, rng.uniform(-20, 20), 1.0, 0.0, True)
u("U15_04_detour_board", -198.0, 13.0, 90.0)
put("btr", -199.0, -9.6, 80.0, 1.0, 0.0, -1, 0.0, True)           # техника ЧВК у шлагбаума (кадры Ground Zero)
put("armored_truck", -197.0, 10.6, 100.0, 1.0, 0.0, -1, 0.0, True)
put("sandbag_post", -205.5, 9.5, -90.0, 1.0, 0.0, -1, 0.0, True)
sign("КПП ЧВК · назад нельзя", -207.0, 5.5, 0.0, 64)
box(-226.0, 4.0, -19.0, 4.0, 8.0, 4.0, "concrete")              # вышка за кордоном
box(-226.0, 9.2, -19.0, 5.0, 2.4, 5.0, "steel")
for (x, z, w, d, fl) in [(-262, -80, 18, 24, 17), (-258, -40, 14, 20, 22), (-262, 45, 16, 26, 12), (-258, 85, 18, 22, 25)]:
    building("Outside_W%d" % abs(z), "", (x, z), (w, d), "mass", fl, 3.0, 0.0, 0.0, "", "", 0.0, "Outside")

# ================================================================== западное плечо, север: павильоны, парковка, ЖК «Панорама»
PAV_Z0, PAV_Z1 = -28.0, -17.0                                   # павильоны стрит-ритейла у тротуара
for (bid, label, x0, x1, interior, theme) in [("Coffee", "кофейня «Зерно»", -192, -176, "shop", "register"),
                                             ("Flowers", "цветы", -173, -163, "shop", "shelf"),
                                             ("Pharmacy", "аптека", -160, -146, "pharmacy", "pharmacy"),
                                             ("Clothes", "одежда «Modus»", -143, -123, "shop", "shelf"),
                                             ("Bakery", "пекарня", -108, -94, "shop", "grocery")]:
    building(bid, label, ((x0 + x1) * 0.5, (PAV_Z0 + PAV_Z1) * 0.5), (x1 - x0, PAV_Z1 - PAV_Z0), "hall", 1, STORY_RETAIL,
             0.0, 0.0, interior, theme, 0.6)
    u("U02_02_planter", (x0 + x1) * 0.5 - (x1 - x0) * 0.3, PAV_Z1 + 1.0, 0.0, 1.0, 0.0, True)
    u("U05_03_warning_a", (x0 + x1) * 0.5 + 2.0, PAV_Z1 + 1.2, rng.uniform(-30, 30))
building("Pavilion_Shut", "салон связи · ломбард (закрыты)", (-76.0, (PAV_Z0 + PAV_Z1) * 0.5), (32.0, 11.0), "mass", 1, STORY_RETAIL)
u("U03_01_lightbox", -184.0, PAV_Z1 + 1.3, 0.0)
u("U05_02_coffee_kiosk", -168.5, PAV_Z1 + 1.6, 180.0, 1.0, 0.0, True)
FI["stories"].append({"label": "кофейня «Зерно» — закладка пролога в подсобке", "at": [-184.0, -22.0], "height": 6.0})
# парковка за павильонами (над паркингом −1): ряды машин, островки, знаки, фонари
LOT_W = [-196.0, -55.0, -121.0, -30.0]
LOT_E = [-106.0, -55.0, -46.0, -30.0]
surface("lot_w", "parking", LOT_W[0], LOT_W[1], LOT_W[2], LOT_W[3], 0.0, 0.05)
surface("lot_e", "parking", LOT_E[0], LOT_E[1], LOT_E[2], LOT_E[3], 0.0, 0.05)
for (x0, x1) in [(-194.0, -124.0), (-104.0, -48.0)]:
    x = x0
    k = 0
    while x < x1:
        for zrow, yaw in ((-33.0, 180.0), (-52.0, 0.0)):
            near_stair = any(abs(x - sx) < 3.0 for (sx, _zb, _zt) in [(-188.0, 0, 0), (-130.0, 0, 0)]) and zrow < -45.0
            if rng.random() < 0.62 and not near_stair:
                u("R04_car" if (k + int(zrow)) % 3 else "U14_01_hatchback", x, zrow, yaw + rng.uniform(-4, 4), 1.0, 0.0, True)
        x += 2.7 * WK
        k += 1
    u("U07_04_tire_delineator", x0 - 1.5, -42.5, 0.0, 1.0, 0.0, True)
    u("U03_03_parking_sign", x0 - 1.5, -38.0, 90.0)
for x in (-176.0, -150.0, -86.0, -62.0):
    u("U12_03_single_light", x, -42.5, 0.0)
    u("U02_02_planter", x + 2.5, -42.5, 90.0, 1.0, 0.0, True)
for x in (-182.0, -134.0, -98.0, -70.0):
    u("U06_01_speed_bump", x, -42.5, 90.0)
# ЖК «Панорама»: корпус 1 (два подъезда по 17 эт., три этажа открыты) и корпус 2 (25 эт., закрыт)
HZ0, HZ1 = -82.0, -56.0
HCZ = (HZ0 + HZ1) * 0.5
flats("Corpus1_A", "ЖК «Панорама», корпус 1 · подъезд 1 — 17 этажей", (-175.0, HCZ), 17, 3)
flats("Corpus1_B", "ЖК «Панорама», корпус 1 · подъезд 2 — 17 этажей", (-145.0, HCZ), 17, 3)
flats("Corpus2_A", "ЖК «Панорама», корпус 2 · подъезд 1 — 25 этажей (закрыт)", (-89.0, HCZ), 25, 0)
flats("Corpus2_B", "ЖК «Панорама», корпус 2 · подъезд 2 — 25 этажей (закрыт)", (-59.0, HCZ), 25, 0)
for x in (-175.0, -145.0, -89.0, -59.0):
    u("U04_05_wall_niche", x + 3.5, HZ0 - 0.2, 180.0, 1.0, 1.4)
    sign("подъезд", x, 3.6, HZ0 - 0.8, 36)
# двор за домами: площадка, парковка жильцов, мусорная площадка, гаражи, забор с воротами к насыпи
surface("yard_n", "walk", XW + 4.0, -110.0, -40.0, -84.0, 0.0, 0.05)
surface("playground", "court", -170.0, -104.0, -150.0, -90.0, 0.0, 0.1)
put("swing", -164.0, -97.0, 0.0)
put("slide", -156.0, -96.0, 90.0)
put("sandbox", -160.0, -101.0, 0.0)
for i in range(8):
    put("garage", -200.0 + i * 3.4, -104.0, 0.0, 1.0, 0.0, -1, 0.0, True)
for i in range(3):
    u("R02_dumpster", -100.0 + i * 3.6, -100.0, 0.0, 1.0, 0.0, True)
put("trash_pile", -95.0, -95.0, 30.0, 1.0, 0.0, -1, 0.0, True)
for i in range(9):
    u("R04_car" if i % 2 else "U14_01_hatchback", -88.0 + i * 3.5, -92.0, 0.0, 1.0, 0.0, True)
u("U03_05_street_cabinet", -130.0, -88.0, 0.0, 1.0, 0.0, True)
put("van", -78.0, -97.5, 80.0, 1.0, 0.0, 9, 0.0, True)
put("ktp", -120.0, -100.0, 0.0, 1.0, 0.0, -1, 0.0, True)
for i in range(70):
    x = XW + 2.5 + 1.25 + i * 2.5
    if -150.0 < x < -140.0 or x > -40.0:
        continue
    put("po2", x, -108.5, 90.0)
for x in (-190.0, -140.0, -110.0, -70.0):
    put("tree_poplar", x, -88.0, rng.uniform(0, 360), 1.0)
sign("ворота двора · к насыпи", -145.0, 3.4, -108.5, 44)

# ------------------------------------------------------------------ проезд во двор и въезд в паркинг −1 (крытый)
DRV = [-121.0, -110.0]                                          # проезд между корпусами (x)
surface("drive_e", "road", -115.2, -84.0, DRV[1], -F)            # восточная полоса вдоль траншеи пандуса
surface("drive_w", "road", DRV[0], -84.0, -115.2, -35.6)          # севернее траншеи — над плитой паркинга
RAMP_X0, RAMP_X1 = -120.5, -115.5
RAMP_TOP, RAMP_BOT = -18.0, -37.0                               # верх у проспекта, низ в паркинге
PIT = [-196.0, -55.0, -114.0, -35.0]                            # паркинг −1 под парковкой и двором
plan["ramps"].append({"x0": RAMP_X0, "x1": RAMP_X1, "z0": RAMP_TOP, "z1": RAMP_BOT, "y0": 0.0, "y1": PIT_Y, "mat": "concrete"})
plan["ground_holes"].append([RAMP_X0, PIT[3], RAMP_X1, RAMP_TOP])
# стенки траншеи от дна до парапета 1,1 м над землёй, торец у проспекта — парапет, навес над всей траншеей
for x0 in (RAMP_X0 - 0.3, RAMP_X1):
    wall(x0, PIT[3], x0 + 0.3, RAMP_TOP, PIT_Y - 0.4, 1.1, "concrete")
box((RAMP_X0 + RAMP_X1) * 0.5, 2.95, (RAMP_TOP + PIT[3]) * 0.5, RAMP_X1 - RAMP_X0 + 1.0, 0.3, RAMP_TOP - PIT[3], "slab")
for px in (RAMP_X0 - 0.5, RAMP_X1 + 0.5):                         # портал въезда: опоры и перемычка над траншеей
    box(px, 1.9, RAMP_TOP - 0.3, 0.7, 3.8, 0.8, "concrete")
box((RAMP_X0 + RAMP_X1) * 0.5, 3.55, RAMP_TOP - 0.3, RAMP_X1 - RAMP_X0 + 1.7, 0.7, 0.8, "concrete")
box((RAMP_X0 + RAMP_X1) * 0.5, 3.0, RAMP_TOP - 0.75, RAMP_X1 - RAMP_X0, 0.35, 0.06, "stripe", 0.0, False)   # ограничитель высоты
u("U07_05_lane_island", RAMP_X1 + 1.6, RAMP_TOP + 1.0, 0.0)
u("U07_01_ticket_machine", RAMP_X1 + 1.4, RAMP_TOP + 0.8, -90.0, 1.0, 0.0, True)
u("U07_02_barrier_arm", RAMP_X1 + 0.9, RAMP_TOP + 1.8, 90.0)
u("U07_03_guide_board", RAMP_X0 - 0.9, RAMP_TOP + 1.2, 0.0, 1.0, 0.0, True)
u("U07_03_guide_board", RAMP_X1 + 2.6, RAMP_TOP + 2.6, 0.0, 1.0, 0.0, True)
u("U07_04_tire_delineator", RAMP_X0 - 1.2, RAMP_TOP + 3.0, 0.0, 1.0, 0.0, True)
u("U03_03_parking_sign", RAMP_X1 + 3.4, RAMP_TOP + 1.0, 0.0)
sign("паркинг −1 · въезд", (RAMP_X0 + RAMP_X1) * 0.5, 5.4, RAMP_TOP + 0.4, 44)
put("speed_bump", (RAMP_X0 + RAMP_X1) * 0.5, RAMP_TOP + 1.6, 90.0)
for (x, z, kit) in [(RAMP_X0 - 2.0, RAMP_TOP + 2.2, "water_barrier"), (RAMP_X0 - 3.3, RAMP_TOP + 2.4, "water_barrier_w"),
                    (RAMP_X0 - 4.6, RAMP_TOP + 4.0, "half_sphere")]:
    put(kit, x, z, 90.0, 1.0, 0.0, -1, 0.0, True)
# паркинг −1: пол, стены, колонны, плита сверху с вырезами под лестницы и пандус
stairs_pit = [(-188.0, -40.0, -50.0), (-130.0, -40.0, -50.0)]   # x, низ z, верх z
SW_ = 1.2 * WK
holes = [[RAMP_X0, PIT[3] - 0.5, RAMP_X1, PIT[3] + 0.01]]
for (sx, zb, zt) in stairs_pit:
    holes.append([sx - SW_ * 0.5 - 0.2, zt - 1.0, sx + SW_ * 0.5 + 0.2, zb + 0.3])
for srf in plan["surfaces"]:
    if srf["id"] in ("lot_w", "drive_w"):
        srf["holes"] = [h for h in holes[1:]]
plan["slabs"].append({"id": "lot_slab", "rect": [PIT[0] - 0.4, PIT[1] - 0.4, PIT[2] + 0.4, PIT[3] + 0.4], "y_top": 0.0, "t": 0.4, "mat": "walk", "holes": holes})
plan["ground_holes"].append([PIT[0] - 0.4, PIT[1] - 0.4, PIT[2] + 0.4, PIT[3] + 0.4])
plan["slabs"].append({"id": "pit_floor", "rect": [PIT[0] - 0.4, PIT[1] - 0.4, PIT[2] + 0.4, PIT[3] + 0.4], "y_top": PIT_Y, "t": 0.4, "mat": "concrete", "holes": []})
wall(PIT[0] - 0.4, PIT[1] - 0.4, PIT[0], PIT[3] + 0.4, PIT_Y, -0.4, "concrete")
wall(PIT[2], PIT[1] - 0.4, PIT[2] + 0.4, PIT[3] + 0.4, PIT_Y, -0.4, "concrete")
wall(PIT[0], PIT[1] - 0.4, PIT[2], PIT[1], PIT_Y, -0.4, "concrete")
wall(PIT[0], PIT[3], RAMP_X0, PIT[3] + 0.4, PIT_Y, -0.4, "concrete")
wall(RAMP_X1, PIT[3], PIT[2], PIT[3] + 0.4, PIT_Y, -0.4, "concrete")
plan["columns"].append({"rect": [PIT[0] + 4.0, PIT[1] + 4.0, PIT[2] - 4.0, PIT[3] - 4.0], "y0": PIT_Y, "y1": -0.4, "grid": 8.0, "size": 0.5, "mat": "concrete"})
for (sx, zb, zt) in stairs_pit:
    plan["stairs"].append({"from": [sx, PIT_Y, zb], "to": [sx, 0.0, zt], "width": SW_, "count": 20, "mat": "concrete"})
    # парапеты вокруг выреза лестницы: по бокам и у нижнего края; выход — у верхнего
    x0, x1 = sx - SW_ * 0.5 - 0.2, sx + SW_ * 0.5 + 0.2
    wall(x0 - 0.15, zt - 1.0, x0, zb + 0.3, 0.0, 1.1, "concrete")
    wall(x1, zt - 1.0, x1 + 0.15, zb + 0.3, 0.0, 1.1, "concrete")
    wall(x0 - 0.15, zb + 0.3, x1 + 0.15, zb + 0.45, 0.0, 1.1, "concrete")
    box(sx, 2.5, (zb + zt) * 0.5, SW_ + 1.2, 0.2, zb - zt + 1.6, "slab", 0.0, False)   # навес над спуском
    sign("паркинг −1 · лестница", sx, 3.0, zt - 1.2, 32)
for (x, z) in [(-188.0, -38.5), (-130.0, -38.5), (RAMP_X0 - 3.0, -38.0), (-160.0, -45.0), (-140.0, -50.0)]:
    plan["lamps"].append([x, -0.9, z, 0.6, 9.0])
for x in range(-190, -118, 10):
    u("U18_03_industrial_light", x + 3.0, -45.0, 90.0, 1.0, -0.7)
for i in range(8):
    u("R04_car" if i % 3 else "U14_01_hatchback", PIT[0] + 8.0 + i * 8.0, PIT[1] + 3.2, 180.0 + rng.uniform(-3, 3), 1.0, PIT_Y, True)
for i in range(5):
    u("R04_car" if i % 2 else "U14_01_hatchback", -176.0 + i * 8.0, PIT[3] - 3.2, rng.uniform(-3, 3), 1.0, PIT_Y, True)
u("U18_04_service_cage", -192.0, -50.0, 90.0, 1.0, PIT_Y, True)
wall(-125.0, PIT[1], -114.0, PIT[1] + 6.0, PIT_Y, -0.4, "wall")    # техпомещение (закрыто)
sign("паркинг −1 · техпомещение", -119.5, -1.2, PIT[1] + 7.0, 32)

# ------------------------------------------------------------------ банк на углу перед поворотом (открытый зал)
BANK = (-26.0, -27.5, 28.0, 21.0)                               # центр x, z, длина, глубина
building("Bank", "банк «Капитал» (разграблен)", (BANK[0], BANK[1]), (BANK[2], BANK[3]), "hall", 1, 4.6, 0.0, 0.0, "", "office", 0.5)
bx, bz = BANK[0], BANK[1]
for k in (-1, 0, 1):
    u("U16_05_teller_desk", bx + k * 3.6, bz - 6.0, 0.0, 1.0, 0.0, True)
    u("U17_03_monitor", bx + k * 3.6, bz - 6.1, 0.0, 1.0, 1.25)
for k in (-1, 1):
    u("U16_01_atm", bx + k * 11.5, bz + 9.6, 180.0, 1.0, 0.0, True)
u("R03_atm", bx - 9.0, BANK[1] + BANK[3] * 0.5 + 0.35, 0.0, 1.0, 0.0, True)        # банкомат на фасаде
u("U16_02_bank_kiosk", bx + 9.0, BANK[1] + BANK[3] * 0.5 + 0.6, 0.0, 1.0, 0.0, True)
for k in range(6):
    u("U19_05_belt_post", bx - 5.0 + k * 2.0, bz + 1.0, 0.0, 1.0, 0.0, True)
for (x, z, yaw) in [(bx - 10, bz + 3, 90), (bx - 10, bz + 5, 90), (bx + 10, bz + 3, -90)]:
    u("U16_03_armchair", x, z, yaw, 1.0, 0.0, True)
u("U04_04_coffee_table", bx - 8.0, bz + 4.0, 0.0)
u("U17_02_ring_chandelier", bx, bz, 0.0, 1.0, 3.1)
u("U16_04_breached_wall", bx + 5.0, bz - 9.2, 0.0, 1.0, 0.0, True)
u("U17_04_credenza", bx - 6.0, bz - 9.8, 0.0, 1.0, 0.0, True)
u("U17_05_water_bottle", bx - 12.0, bz - 9.0, 0.0)
u("U04_01_turnstile", bx - 2.2, bz - 2.0, 0.0, 1.0, 0.0, True)
u("U04_01_turnstile", bx + 2.2, bz - 2.0, 0.0, 1.0, 0.0, True)
sign("банк «Капитал»", bx, 5.6, BANK[1] + BANK[3] * 0.5 + 0.4, 48)
put("inkassator", bx + 4.0, -6.6, 95.0, 1.0, 0.0, 5, 0.0, True)    # инкассаторский броневик у бордюра, задние двери открыты
FI["stories"].append({"label": "инкассаторы бросили броневик у банка: кейс с деньгами", "at": [bx + 4.0, -6.6], "height": 3.4})

# ================================================================== западное плечо, юг: остановка с площадкой, дом 7, «Ярус»
# остановка и ларьки на тротуаре, за ними — площадка 18 м до дома (замечание владельца)
u("U03_01_lightbox", -186.0, F - 1.0, 180.0)
put("bus_stop", -192.0, F - 3.0, 180.0, 1.0, 0.0, -1, 0.0, True)
u("R05_kiosk", -200.0, F + 2.2, 180.0, 1.0, 0.0, True)
u("U05_02_coffee_kiosk", -205.0, F + 2.0, 180.0, 1.0, 0.0, True)
surface("plaza_stop", "court", -210.0, F, -166.0, 34.0, 0.0, 0.1)
for (x, z) in [(-196, 24), (-182, 24), (-172, 26)]:
    u("U10_04_bench_stone", x, z, 0.0, 1.0, 0.0, True)
    u("U02_02_planter", x, z + 3.5, 0.0, 1.0, 0.0, True)
for (x, z) in [(-204, 28), (-176, 30), (-188, 31)]:
    put("tree_birch", x, z, rng.uniform(0, 360), 1.2)
u("U19_04_square_light", -190.0, 27.0, 0.0)
u("U10_03_wayfinding", -168.0, 19.0, 180.0)
building("Minimarket", "минимаркет «Весна»", (-170.0, 22.0), (12.0, 10.0), "hall", 1, STORY_RETAIL, 180.0, 0.0, "shop", "grocery", 0.5, "South")
flats("House7", "дом 7 — 12 этажей (закрыт)", (-188.0, 51.0), 12, 0, 180.0, (36.0, 26.0), region="South", loot=0.0)
for i in range(6):
    put("garage", -205.0 + i * 3.4, 74.0, 0.0, 1.0, 0.0, -1, 0.0, True)
u("R02_dumpster", -176.0, 78.0, 90.0, 1.0, 0.0, True)
put("trash_pile", -172.0, 81.0, 0.0, 1.0, 0.0, -1, 0.0, True)
surface("house7_yard", "walk", -210.0, 64.0, -166.0, 108.0, 0.0, 0.05)
for i in range(6):
    u("U14_01_hatchback" if i % 2 else "R04_car", -204.0 + i * 3.4, 95.0, 0.0, 1.0, 0.0, True)
# супермаркет «Ярус»: парковка перед фасадом, зал, склад, разгрузочный двор
SM = (-102.0, 68.0, 80.0, 40.0)
building("Supermarket", "супермаркет «Ярус»", (SM[0], SM[1]), (SM[2], SM[3]), "hall", 1, 6.0, 180.0, 0.0, "supermarket", "grocery", 0.5, "South")
smz0 = SM[1] - SM[3] * 0.5
smz1 = SM[1] + SM[3] * 0.5
surface("lot_sm", "parking", -146.0, F, -62.0, smz0 - 1.0, 0.0, 0.05)
sign("супермаркет «Ярус»", SM[0], 7.5, smz0 - 0.5, 72)
for r, zrow in enumerate((22.0, 32.0, 40.0)):
    for i in range(10):
        cx = -142.0 + i * 3.6 * WK
        if -112.0 < cx < -92.0 and zrow > 35.0:
            continue
        if rng.random() < 0.5:
            u("R04_car" if (i + r) % 3 else "U14_01_hatchback", cx, zrow, (0.0 if r != 1 else 180.0) + rng.uniform(-5, 5), 1.0, 0.0, True)
for z in range(20, 44, 6):
    u("U02_02_planter", -116.0, z, 90.0, 1.0, 0.0, True)
put("suv_open", -128.5, 27.0, 172.0, 1.0, 0.0, 1, 0.0, True)
put("boxes", -128.0, 23.2, 20.0)
put("police_car", -103.0, 41.5, 84.0, 1.0, 0.0, -1, 0.0, True)
building("CartShelter", "навес тележек", (-124.0, 36.0), (8.0, 6.0), "canopy", 1, 2.8, 0.0, 0.0, "", "", 0.0, "South")
for i in range(5):
    put("cart", -126.0 + i * 1.1, 36.0 + (i % 2), rng.uniform(0, 360))
put("truck", -90.0, 40.0, 0.0, 1.0, 0.0, 2, 0.0, True)
for i in range(3):
    u("U14_02_plywood_case", -88.0 + i * 0.9, 45.0, rng.uniform(0, 360))
FI["stories"].append({"label": "бросили при погрузке: фургон и ящики", "at": [-90.0, 42.0], "height": 4.0})
for x in (-134.0, -98.0, -70.0):
    u("U12_03_single_light", x, 30.0, 0.0)
u("U01_02_crowd", -104.0, smz0 - 2.0, 0.0, 1.0, 0.0, True)
u("U01_02_crowd", -100.0, smz0 - 2.0, 5.0, 1.0, 0.0, True)
u("U16_01_atm", SM[0] + 18.0, smz0 - 0.4, 180.0, 1.0, 0.0, True)
# разгрузка: ворота-роллеты в задней стене, фура, бочка-прицеп, ящики, баки, забор с калиткой в служебный проезд
for x in (-130.0, -76.0):
    u("U18_02_loading_shutter", x, smz1 + 0.2, 0.0, 1.0, 0.0, True)
u("U18_03_industrial_light", -116.0, smz1 + 0.3, 0.0, 1.0, 4.6)
u("U18_03_industrial_light", -88.0, smz1 + 0.3, 0.0, 1.0, 4.6)
surface("dock_yard", "road", -142.0, smz1, -62.0, 108.0)
put("truck", -132.0, 98.0, 90.0, 1.0, 0.0, -1, 0.0, True)
put("trailer", -121.0, 98.0, 90.0, 1.0, 0.0, -1, 0.0, True)
u("U18_01_tank", -80.0, 101.0, 90.0, 1.0, 0.0, True)
for i in range(4):
    u("U01_03_crate", -112.0 + (i % 2) * 1.4, 93.0 + (i // 2) * 1.0, rng.uniform(-10, 10), 1.0, 0.0, True)
for i in range(2):
    u("R02_dumpster", -70.0, 92.0 + i * 3.0, 90.0, 1.0, 0.0, True)
put("pallets", -96.0, 104.0, 20.0)
for i in range(32):
    put("po2", -142.0 + 1.25 + i * 2.5, 108.5, 90.0)
for i in range(22):
    z = smz1 - 40.0 + 1.25 + i * 2.5
    if z < smz1 or 95.0 < z < 100.5:
        continue
    put("po2", -61.6, z, 0.0)
sign("калитка в служебный проезд", -61.6, 3.2, 97.5, 40)
surface("service_lane", "road", -60.0, F, -50.0, 112.0)
sign("служебный проезд · к насыпи", -55.0, 4.0, 104.0, 44)

# ================================================================== внутренний угол поворота: сквер
surface("square_a", "court", -46.0, 18.0, -2.0, 108.0, 0.0, 0.1)
surface("square_b", "court", -2.0, 55.0, 37.0, 108.0, 0.0, 0.1)
curve_strip(-38.0, -16.6, "court", 0.1, 0.0, 16)
put("monument", -10.0, 70.0, 0.0, 1.0, 0.0, -1, 0.0, True)
sign("сквер · сухой фонтан", -10.0, 5.0, 70.0, 44)
for (x, z) in [(-40, 28), (-40, 60), (-40, 95), (-20, 100), (10, 100), (25, 75), (-25, 40), (5, 40)]:
    put("tree_birch", x, z, rng.uniform(0, 360), 1.2)
for (x, z, yaw) in [(-18, 66, 90), (-18, 74, 90), (-2, 66, -90), (-2, 74, -90), (-10, 58, 0), (-10, 82, 180)]:
    u("U10_04_bench_stone", x, z, yaw, 1.0, 0.0, True)
for (x, z) in [(-28, 50), (8, 52), (-28, 88), (14, 88)]:
    u("U19_04_square_light", x, z, 0.0)
    u("U09_04_plaza_seat", x + 3.0, z, 90.0, 1.0, 0.0, True)
u("U05_02_coffee_kiosk", 20.0, 95.0, -90.0, 1.0, 0.0, True)
put("food_kiosk", -38.0, 78.0, 90.0, 1.0, 0.0, -1, 0.0, True)
put("tent", -24.0, 84.0, 20.0)
put("tent", -30.0, 90.0, -30.0)
u("U10_03_wayfinding", -44.0, 20.0, 180.0)

# ================================================================== внешний угол поворота: ЖК «Вершина» (Москва-Сити) и площадь
STY = [18.0, -88.0, 96.0, -28.0]                                 # стилобат
building("Vershina_Podium", "ЖК «Вершина» · стилобат: офисы, фитнес (закрыт)", ((STY[0] + STY[2]) * 0.5, (STY[1] + STY[3]) * 0.5),
         (STY[2] - STY[0], STY[3] - STY[1]), "mass", 2, 4.5, 0.0, 0.0, "", "", 0.0, "East")
flats("Vershina_T1", "ЖК «Вершина», башня 1 — 42 этажа", (36.0, -66.0), 42, 0, 0.0, (22.0, 22.0), 3.3, False, True, 9.3, "East", 0.0)
flats("Vershina_T2", "ЖК «Вершина», башня 2 — 34 этажа", (76.0, -66.0), 34, 0, 0.0, (20.0, 20.0), 3.3, False, True, 9.3, "East", 0.0)
flats("Vershina_T3", "ЖК «Вершина», башня 3 — 48 этажей", (128.0, -78.0), 48, 0, 0.0, (24.0, 24.0), 3.3, False, True, 0.0, "East", 0.0)
flats("Vershina_T4", "ЖК «Вершина», башня 4 — 30 этажей", (130.0, -30.0), 30, 0, 0.0, (20.0, 20.0), 3.3, False, True, 0.0, "East", 0.0)
# фасад стилобата к площади: стеклянная стена, вращающиеся и распашные двери, козырьки, волнистый фасад, светящийся парапет
for k in range(9):
    x = STY[0] + 4.5 + k * 8.4
    u("U08_04_curtainwall", x, STY[3] + 0.15, 0.0)
    u("U12_04_lit_parapet", x, STY[3] + 0.3, 0.0, 1.0, 9.0)
u("U08_01_revolving_door", 40.0, STY[3] + 1.4, 0.0, 1.0, 0.0, True)
u("U08_01_revolving_door", 74.0, STY[3] + 1.4, 0.0, 1.0, 0.0, True)
u("U08_02_glass_doors", 57.0, STY[3] + 0.2, 0.0, 1.0, 0.0, True)
for x in (40.0, 57.0, 74.0):
    u("U08_03_canopy_bracket", x, STY[3] + 0.3, 0.0, 1.0, 3.4)
u("U12_01_wave_facade", 26.0, STY[3] + 0.5, 0.0, 1.0, 5.0)
u("U12_01_wave_facade", 88.0, STY[3] + 0.5, 0.0, 1.0, 5.0)
u("U12_05_triangle_panel", STY[0] - 0.2, -60.0, -90.0, 1.0, 1.5)
u("U12_05_triangle_panel", STY[0] - 0.2, -50.0, -90.0, 1.0, 1.5)
sign("ЖК «Вершина» · четыре башни", 57.0, 11.0, STY[3] + 0.8, 64)
# площадь перед стилобатом до поворота: террасы, пилон, сиденья, светильники, стеклянные навесы, баррикада и пункт эвакуации
surface("plaza_v", "court", 0.0, -28.0, 110.0, -6.0, 0.0, 0.1)
surface("plaza_v2", "court", 60.0, -6.0, 110.0, 50.0, 0.0, 0.1)
u("U19_02_terrace_stairs", 100.0, -18.0, -90.0, 1.0, 0.0, False)
u("U09_03_logo_pylon", 8.0, -24.0, face(-1.0, 1.0), 1.0, 0.0, True)
for (x, z) in [(20, -16), (34, -12), (90, -10), (96, 8)]:
    u("U09_04_plaza_seat", x, z, rng.uniform(0, 90), 1.0, 0.0, True)
for (x, z) in [(14, -10), (50, -14), (82, -4), (100, 24)]:
    u("U19_04_square_light", x, z, 0.0)
for x in (48.0, 66.0):
    u("U02_01_canopy", x, -22.0, 0.0)
u("U14_03_space_canopy", 92.0, 30.0, 90.0, 1.0, 2.8)
u("U19_03_relief_wall", 106.0, 0.0, -90.0, 1.0, 0.0, True)
u("U08_05_glass_railing", 104.0, -24.0, 0.0, 1.0, 0.0, True)
u("U08_05_glass_railing", 104.0, -12.0, 0.0, 1.0, 0.0, True)
# баррикада поперёк площади (кадры 12, 16): ежи, бетонные кубы, Джерси, мешки
for k in range(7):
    x = 22.0 + k * 6.0
    zz = -4.0 + k * 2.2
    u("U09_01_hedgehog" if k % 3 == 0 else ("U09_02_concrete_cube" if k % 3 == 1 else "U01_01_jersey"), x, zz, face(1.0, -0.4) + rng.uniform(-15, 15), 1.0, 0.0, True)
u("U03_02_sandbags", 36.0, 2.0, 30.0, 1.0, 0.0, True)
u("U09_05_damaged_slab", 30.0, -18.0, 20.0)
put("avtozak", 64.0, -14.5, 78.0, 1.0, 0.0, -1, 0.0, True)          # оцепление у входа в стилобат (Terragroup)
put("police_car", 46.0, -18.5, 24.0, 1.0, 0.0, -1, 0.0, True)
for x in (51.5, 54.5, 57.5, 60.5):
    put("tape", x, -25.0, 90.0)
for (x, z, yaw) in [(68.0, -22.5, 10.0), (70.5, -22.0, 0.0)]:
    u("U01_02_crowd", x, z, yaw, 1.0, 0.0, True)
for k in range(12):
    put("paper", 58.0 + rng.uniform(-6, 6), -20.0 + rng.uniform(-3, 3), rng.uniform(0, 360))
FI["stories"].append({"label": "оцепление: автозак и лента у входа в «Вершину»", "at": [60.0, -18.0], "height": 4.0})
put("btr", 70.0, 7.0, 35.0, 1.0, 0.0, -1, 0.0, True)                 # колонна на подходе к эвакуации
for (x, z, kit) in [(63.5, 13.5, "water_barrier"), (64.8, 13.9, "water_barrier_w"), (77.5, 2.0, "water_barrier"),
                    (78.7, 2.5, "water_barrier_w")]:
    put(kit, x, z, 120.0, 1.0, 0.0, -1, 0.0, True)
for x in (10.0, 13.5, 17.0):
    put("flagpole", x, -26.0, 0.0, 1.0, 0.0, -1, 0.0, True)
# пункт эвакуации жителей (кадр 13): палатка, ширмы, коляски, носилки, тележки, ограждения, генератор
u("U13_01_medical_tent", 82.0, 20.0, -30.0, 1.0, 0.0, True)
for (x, z, yaw) in [(76, 26, 10), (88, 12, 60)]:
    u("U13_02_medical_screen", x, z, yaw, 1.0, 0.0, True)
u("U13_03_wheelchair", 74.0, 16.0, 40.0)
u("U13_04_stretcher", 90.0, 24.0, -60.0, 1.0, 0.0, True)
u("U13_05_medical_cart", 86.0, 28.0, 0.0, 1.0, 0.0, True)
u("U15_03_generator", 96.0, 16.0, 0.0, 1.0, 0.0, True)
u("U15_05_power_cable", 92.0, 18.0, 70.0)
for k in range(5):
    u("U01_02_crowd", 70.0 + k * 2.5, 36.0, 0.0, 1.0, 0.0, True)
u("U15_04_detour_board", 68.0, 30.0, -60.0, 1.0, 0.0, True)
put("bus_wreck", 104.0, 42.0, 20.0, 1.0, 0.0, 4, 0.0, True)
FI["stories"].append({"label": "пункт эвакуации жителей: палатка, носилки, коляски", "at": [82.0, 20.0], "height": 6.0})

# ================================================================== южное плечо, восток: парковка, корпус 3, «Меридиан», тупик
surface("lot_e3", "parking", XS + F + 2.0, 60.0, 98.0, 232.0, 0.0, 0.05)
for i in range(49):
    z = 64.0 + i * 3.4
    if 146.0 < z < 154.0:
        continue
    if rng.random() < 0.55:
        u("R04_car" if i % 3 else "U14_01_hatchback", 80.0, z, 90.0 + rng.uniform(-4, 4), 1.0, 0.0, True)
    if rng.random() < 0.45:
        u("R04_car" if i % 2 else "U14_01_hatchback", 93.0, z, -90.0 + rng.uniform(-4, 4), 1.0, 0.0, True)
for z in (80.0, 120.0, 170.0):
    u("U12_03_single_light", 86.5, z, 90.0)
flats("Corpus3_A", "ЖК «Панорама», корпус 3 · подъезд 1 — 17 этажей (закрыт)", (113.0, 95.0), 17, 0, -90.0, region="East", loot=0.0)
flats("Corpus3_B", "ЖК «Панорама», корпус 3 · подъезд 2 — 17 этажей (закрыт)", (113.0, 125.0), 17, 0, -90.0, region="East", loot=0.0)
surface("yard_e", "walk", 126.0, 70.0, 158.0, 150.0, 0.0, 0.05)
put("swing", 140.0, 96.0, 90.0)
put("slide", 142.0, 104.0, 0.0)
for i in range(3):
    u("R02_dumpster", 150.0, 128.0 + i * 3.4, 90.0, 1.0, 0.0, True)
building("Meridian", "бизнес-центр «Меридиан», 8 эт. (закрыт)", (120.0, 195.0), (48.0, 44.0), "mass", 8, 3.6, 0.0, 0.0, "", "", 0.0, "East")
u("U05_01_guard_booth", 92.0, 172.0, -90.0, 1.0, 0.0, True)
u("U07_02_barrier_arm", 92.0, 177.0, 0.0)
u("U09_03_logo_pylon", 92.0, 166.0, -90.0, 1.0, 0.0, True)
for z in (160.0, 163.0):
    put("flagpole", 94.0, z, 0.0, 1.0, 0.0, -1, 0.0, True)
u("U14_04_entry_steps", 104.0, 30.0, 180.0, 1.0)                 # ступени к террасе площади «Вершины»
u("U08_02_glass_doors", 120.0, 172.8, 180.0, 1.0, 0.0, True)
# тупик: шумозащитный экран поперёк, самосвалы, блоки, объезд (кадр 11)
for k in range(10):
    u("U11_01_sound_fence", XS - 15.0 + k * 3.2, 262.0, 0.0, 1.0, 0.0, True)
put("truck", XS - 4.0, 252.0, 80.0, 1.0, 0.0, -1, 0.0, True)
put("truck", XS + 6.0, 256.0, 100.0, 1.0, 0.0, -1, 0.0, True)
u("U11_03_dump_bed", XS - 8.0, 248.0, 90.0, 1.0, 0.0, True)
for (x, z) in [(XS - 12, 244), (XS + 12, 246), (XS, 242)]:
    u("U11_05_water_barrier", x, z, 90.0 + rng.uniform(-20, 20), 1.0, 0.0, True)
for k in range(4):
    u("U07_03_guide_board", XS - 6.0 + k * 4.0, 240.0, 0.0, 1.0, 0.0, True)
u("U15_04_detour_board", XS + 2.0, 238.0, 0.0, 1.0, 0.0, True)
for k in range(6):
    u("U01_04_cone", XS - 8.0 + k * 3.0, 236.5, rng.uniform(0, 360))
# выезд к тупику с востока: брошенный автобус, фургон, красно-белые блоки — укрытия на подходе от южного появления
put("bus_city", 128.0, 259.0, 18.0, 1.0, 0.0, 9, 0.0, True)
put("van", 101.0, 243.0, -32.0, 1.0, 0.0, 6, 0.0, True)
for k in range(3):
    put("jersey_rw", 114.0 + k * 3.2, 252.5 - k * 0.9, 74.0, 1.0, 0.0, -1, 0.0, True)
put("ad_column", 140.0, 247.0, 0.0, 1.0, 0.0, -1, 0.0, True)
for (x, z, w, d, fl) in [(40, 300, 30, 18, 20), (90, 302, 24, 20, 26), (140, 300, 26, 18, 16)]:
    building("Outside_S%d" % x, "", (x, z), (w, d), "mass", fl, 3.0, 0.0, 0.0, "", "", 0.0, "Outside")
for (x, z, w, d, fl) in [(196, -60, 20, 26, 22), (198, 40, 18, 24, 18), (196, 150, 22, 26, 25), (-20, -150, 24, 18, 21), (60, -152, 30, 20, 16)]:
    building("Outside_E%d_%d" % (abs(x), abs(z)), "", (x, z), (w, d), "mass", fl, 3.0, 0.0, 0.0, "", "", 0.0, "Outside")

# ================================================================== южное плечо, запад: минимаркет, стройка
building("Minimarket2", "продукты «24 часа»", (31.0, 128.0), (16.0, 10.0), "hall", 1, STORY_RETAIL, 90.0, 0.0, "shop", "grocery", 0.5, "South")
u("U05_03_warning_a", 37.5, 121.0, 90.0)
u("R05_kiosk", 33.0, 112.0, 90.0, 1.0, 0.0, True)
SITE = [-50.0, 150.0, 30.0, 250.0]
surface("site", "walk", SITE[0], SITE[1], SITE[2], SITE[3], 0.0, 0.05)
building("Site_Skeleton", "недострой, 6 эт.", (-10.0, 195.0), (36.0, 22.0), "skeleton", 6, 3.1, 0.0, 0.0, "", "", 0.0, "South")
for k in range(int((SITE[3] - SITE[1]) / 2.5)):
    z = SITE[1] + 1.25 + k * 2.5
    if 196.0 < z < 204.0:
        continue
    u("U11_02_site_fence", SITE[2] + 0.4, z, 90.0, 1.0, 0.0, k % 3 == 0)
for k in range(int((SITE[2] - SITE[0]) / 2.5)):
    x = SITE[0] + 1.25 + k * 2.5
    u("U11_02_site_fence", x, SITE[1] - 0.4, 0.0, 1.0, 0.0, True)
for k in range(4):
    u("U11_04_privacy_screen", SITE[2] + 1.4, 160.0 + k * 9.0, 90.0, 1.0, 0.0, True)
put("cabin", -40.0, 160.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("cabin", -34.0, 160.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("rebar", -30.0, 225.0, 20.0)
put("pipes", -20.0, 232.0, 80.0, 1.0, 0.0, -1, 0.0, True)
put("reel", 5.0, 228.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("pallets", 12.0, 222.0, 30.0)
for (x, z, yaw) in [(15, 170, 10), (-38, 215, 60), (18, 240, 100)]:
    u("U09_05_damaged_slab", x, z, yaw)
for k in range(4):
    u("U01_03_crate", 22.0 + (k % 2) * 1.4, 182.0 + (k // 2) * 1.1, rng.uniform(-10, 10), 1.0, 0.0, True)
u("U11_03_dump_bed", -40.0, 240.0, 0.0, 1.0, 0.0, True)
u("U01_05_mesh_barrier", 26.0, 200.0, 90.0, 1.0, 0.0, True)
put("van", -28.0, 168.0, 30.0, 1.0, 0.0, 11, 0.0, True)
# южный край стройки вдоль пути к пролому: бытовка, контейнер, плиты штабелем
put("cabin", 2.0, 244.0, 90.0, 1.0, 0.0, -1, 0.0, True)
put("container20", -21.0, 245.0, 8.0, 1.0, 0.0, -1, 0.0, True)
put("slab", 16.0, 245.0, 85.0, 1.0, 0.0, -1, 0.0, True)
put("slab", 16.2, 245.1, 83.0, 1.0, 0.2, -1, 0.0, False)
for k in range(4):
    put("hazard_fence", 24.0, 186.0 + k * 2.5, 0.0, 1.0, 0.0, -1, 0.0, True)
sign("стройка · ворота", SITE[2] + 1.0, 3.5, 200.0, 40)
put("crane", -40.0, 190.0, 0.0) if False else None

# ================================================================== приёмы из разбора Ready or Not / Ground Zero
# решётки вентиляции паркинга −1 на парковке: сверху видно, что внизу есть ход, снизу слышно шаги
for (x, z) in [(-184.0, -42.5), (-160.0, -42.5), (-140.0, -42.5)]:
    box(x, 0.35, z, 2.4, 0.7, 1.2, "steel")
    box(x, 0.71, z, 2.2, 0.02, 1.0, "dark", 0.0, False)
# кондиционеры на фасадах жилых секций — ритм фасада, масштаб
for (cx, cz, yaw, length, floors) in [(-175.0, HCZ, 0.0, 30.0, 17), (-145.0, HCZ, 0.0, 30.0, 17), (-89.0, HCZ, 0.0, 30.0, 25),
                                      (-59.0, HCZ, 0.0, 30.0, 25), (-188.0, 51.0, 180.0, 36.0, 12)]:
    for fl in range(1, floors):
        for k in range(4):
            if rng.random() < 0.35:
                x = cx - length * 0.5 + 3.0 + k * (length - 6.0) / 3.0 + rng.uniform(-1.0, 1.0)
                y = fl * STORY_FLAT + 0.5
                zf = cz + 13.0 + 0.2 if yaw == 0.0 else cz - 13.0 - 0.2
                put("ac_unit", x, zf, yaw, 1.0, y)
# строительные леса на фасаде недостроя: стойки, ригели, настилы — вертикаль и проход с ограниченным обзором
for k in range(16):
    x = -28.0 + k * 2.4
    box(x, 9.0, 206.8, 0.06, 18.0, 0.06, "steel", 0.0, False)
    box(x, 9.0, 208.0, 0.06, 18.0, 0.06, "steel", 0.0, False)
for lvl in range(1, 7):
    box(-10.0, lvl * 3.1 - 0.05, 207.4, 38.0, 0.06, 1.3, "rust", 0.0, lvl * 3.1 < 4.0)
    box(-10.0, lvl * 3.1 + 1.0, 208.05, 38.0, 0.05, 0.05, "steel", 0.0, False)
# наружная пожарная лестница у «Меридиана»: марши по торцу до крыши — второй путь наверх (на этапе блокаута — вид)
for fl in range(8):
    y0 = fl * 3.6
    box(95.2, y0 + 1.8, 185.0 + (fl % 2) * 4.0, 1.2, 0.08, 3.4, "steel", 0.0, False)
    box(95.2, y0 + 3.55, 183.0 if fl % 2 else 191.0, 1.4, 0.06, 1.4, "steel", 0.0, False)
box(95.8, 14.4, 187.0, 0.05, 28.8, 9.0, "steel", 0.0, False)
# мусор у бордюров и куча покрышек у гаражей — сценки
put("tires", -196.0, -100.0, 0.0)
put("tires", -201.0, 71.0, 30.0)

# ================================================================== мусор: бумага, бутылки, банки, кучи
for i in range(520):
    s_pick = rng.random()
    pts = along(1.0, 0.0)
    x, z, h = pts[rng.randrange(len(pts))]
    side = rng.choice([1.0, -1.0])
    d = rng.uniform(RH + 0.4, F - 0.4) * side if s_pick < 0.7 else rng.uniform(-RH + 0.4, RH - 0.4)
    rad = math.radians(h)
    # курс h: 90 — на восток, 0 — на юг; лево от курса = (sin(h+90°)… ) — считаем от касательной
    tx, tz = math.sin(rad), math.cos(rad)
    lx, lz = tz, -tx
    px, pz = x + lx * d, z + lz * d
    if busy(px, pz):
        continue
    put("paper" if rng.random() < 0.7 else "paper_ball", px, pz, rng.uniform(0, 360), rng.uniform(0.7, 1.2))
for (cx, cz, n) in [(-200, F - 1.0, 25), (-192, F - 3.0, 20), (-156, 0.0, 18), (-124, 36.0, 30), (-102, 96.0, 30),
                    (-26, -12.0, 20), (82, 22, 25), (XS, 240.0, 25), (20, 95, 20), (-176, 78, 15), (-98, -97, 20)]:
    for i in range(n):
        put(rng.choice(["bottle", "can", "paper", "paper_ball", "bags"]), cx + rng.uniform(-6, 6), cz + rng.uniform(-4, 4),
            rng.uniform(0, 360), rng.uniform(0.6, 1.0), TUNNEL_Y if (cx, cz) == (-156, 0.0) else 0.0)
for (x, z) in [(-63.0, 50.0), (-120.0, 62.0), (-205.0, 70.0), (150.0, 140.0), (-45.0, 150.0), (-30.0, -90.0)]:
    put("trash_pile", x, z, rng.uniform(0, 360), 1.0, 0.0, -1, 0.0, True)
    put("bags", x + 1.2, z + 0.8, rng.uniform(0, 360))
# переносные ограждения и конусы — сценками у банка, у въезда, у зебр
for (x, z, n, yaw) in [(-40.0, -15.0, 3, 0.0), (-124.0, 12.0, 4, 0.0), (XS - 12.0, 146.0, 3, 90.0)]:
    for k in range(n):
        u("U01_02_crowd", x + (k * 2.5 if yaw == 0.0 else 0.0), z + (k * 2.5 if yaw == 90.0 else 0.0), yaw + rng.uniform(-12, 12), 1.0, 0.0, True)
for (x, z) in [(-112.0, 9.0), (-48.0, -11.0), (XS + 10.0, 130.0), (20.0, -12.0)]:
    for k in range(3):
        u("U01_04_cone", x + rng.uniform(-1.5, 1.5), z + rng.uniform(-1.0, 1.0), rng.uniform(0, 360))
for (x, z) in [(-60.0, -11.0), (XS - 11.0, 190.0)]:
    u("U01_05_mesh_barrier", x, z, 0.0, 1.0, 0.0, True)
for (x, z) in [(-178.0, -11.2), (-134.0, 11.2), (XS + 11.2, 96.0)]:
    u("U10_05_billboard", x, z + (-1.0 if z < 0 else 1.0), 0.0 if z < 50 else -90.0, 1.0, 0.0, True)

# ================================================================== появление, выходы, места, подходы, проверки
plan["spawns"] = [{"id": "cordon", "label": "Кордон (старт пролога)", "at": [-200.0, 0.0]},
                  {"id": "yards", "label": "Дворы ЖК", "at": [-125.0, -104.0]},
                  {"id": "vershina", "label": "За «Вершиной»", "at": [150.0, -104.0]},
                  {"id": "south", "label": "Юг, у тупика", "at": [150.0, 268.0]},
                  {"id": "site", "label": "Стройка", "at": [-45.0, 268.0]}]
plan["exits"] = [{"label": "Дворами к насыпи", "at": [-145.0, -110.0], "always": True},
                 {"label": "Служебный проезд", "at": [-55.0, 108.0], "always": True},
                 {"label": "Пролом у стройки", "at": [-52.0, 242.0], "always": True},
                 {"label": "Паркинг −1, въезд", "at": [-118.0, -15.0], "always": False}]
plan["locations"] = [
    {"id": 1, "label": "Кордон", "at": [-200.0, 0.0], "spawn": [-200.0, 0.0], "look": [-160.0, -6.0]},
    {"id": 2, "label": "Кофейня «Зерно»", "at": [-184.0, -22.0], "spawn": [-184.0, -12.0], "look": [-184.0, -22.0]},
    {"id": 3, "label": "Въезд в паркинг −1", "at": [-118.0, -20.0], "spawn": [-112.0, -11.0], "look": [-118.0, -26.0]},
    {"id": 4, "label": "Двор ЖК · подъезд 1", "at": [-175.0, -90.0], "spawn": [-175.0, -95.0], "look": [-175.0, -82.0]},
    {"id": 5, "label": "Подземный переход", "at": [-156.0, 0.0], "spawn": [-148.0, -10.0], "look": [-158.0, -13.0]},
    {"id": 6, "label": "Парковка «Яруса»", "at": [-102.0, 30.0], "spawn": [-112.0, 17.0], "look": [-102.0, 48.0]},
    {"id": 7, "label": "Супермаркет «Ярус»", "at": [-102.0, 68.0], "spawn": [-108.0, 44.0], "look": [-108.0, 68.0]},
    {"id": 8, "label": "Разгрузка «Яруса»", "at": [-102.0, 98.0], "spawn": [-96.0, 95.0], "look": [-60.0, 97.0]},
    {"id": 9, "label": "Площадь «Вершины»", "at": [50.0, -10.0], "spawn": [12.0, -6.0], "look": [57.0, -28.0]},
    {"id": 10, "label": "Сквер в повороте", "at": [-10.0, 70.0], "spawn": [-30.0, 30.0], "look": [-10.0, 70.0]},
    {"id": 11, "label": "Банк «Капитал»", "at": [-26.0, -27.5], "spawn": [-26.0, -13.0], "look": [-26.0, -27.5]},
    {"id": 12, "label": "Стройка", "at": [-10.0, 195.0], "spawn": [36.0, 200.0], "look": [-10.0, 195.0]},
    {"id": 13, "label": "Тупик на юге", "at": [XS, 250.0], "spawn": [XS + 12.0, 225.0], "look": [XS, 255.0]},
    {"id": 14, "label": "Корпус 3 и парковка", "at": [90.0, 110.0], "spawn": [XS + 11.0, 110.0], "look": [113.0, 110.0]},
]
sm_cx = SM[0]
cx1, cz1 = -175.0, HCZ
plan["probe_routes"] = [
    {"id": "prologue", "label": "пролог: кордон → кофейня → переход → парковка → «Ярус» → склад → двор → проезд", "max_open_m": 30.0,
     "points": [[-200, 0], [-193, -4], [-193, -12], [-184, -12], [-184, -16], [-184, -21], [-184, -16], [-184, -12], [-166, -12],
                [-150, -10], [-150, -13], [-152.5, -13], [-158.6, -13], [-158.6, -9.5], [-156, -8], [-156, 0], [-156, 8], [-158.6, 9.5], [-158.6, 13],
                [-152.5, 13], [-149, 13], [-146, 17], [-130, 18], [-112, 18], [-108, 26], [-108, 46], [-108, 52], [-108, 64],
                [-108, 78], [-122, 80], [-122, 84.5], [sm_cx, 84.5], [sm_cx, 90], [sm_cx, 95.5], [-66, 96.5], [-60, 97.5],
                [-55, 100], [-55, 106]]},
    {"id": "yards_to_south", "label": "дворы ЖК → проезд → зебра → служебный проезд", "max_open_m": 30.0,
     "points": [[-125, -104], [-112.5, -96], [-112.5, -60], [-112.5, -20], [-112.5, -12], [CROSS_W + 1.5, -10], [CROSS_W + 1.5, 10],
                [-112, 18], [-90, 18], [-63, 18], [-55, 20], [-55, 60], [-55, 106]]},
    {"id": "vershina_to_north", "label": "за «Вершиной» → вдоль стилобата → дворы → к насыпи", "max_open_m": 30.0,
     "points": [[150, -104], [100, -100], [10, -98], [-40, -96], [-112.5, -96], [-140, -98], [-145, -104], [-145, -109]]},
    {"id": "south_to_site", "label": "юг → парковка корпуса 3 → зебра → вдоль стройки → пролом", "max_open_m": 30.0,
     "points": [[150, 268], [110, 250], [74, 230], [72, 156], [XS + 1.5, 152], [XS - 1.5, 152], [37, 152], [36, 246], [-20, 254],
                [-50, 254], [-52, 242]]},
    {"id": "parking_minus1", "label": "въезд → пандус → паркинг −1 → лестница наверх", "max_open_m": 0.0,
     "points": [[-112, -11], [-118, -16], [-118, -24], [-118, -36], [-120, -40], [-130, -38.6], [-130, -39.6], [-130, -50.2],
                [-130, -51.5]]},
    {"id": "corpus1_floor3", "label": "подъезд 1 корпуса 1: тамбур, вестибюль, холл, лестница на 3-й этаж", "max_open_m": 0.0,
     "points": [[cx1, cz1 - 13.0 - 4.5], [cx1, cz1 - 13.0 + 1.0], [cx1, cz1 - 8.5], [cx1, cz1 - 4.0], [cx1, cz1], [cx1 - 3.75, cz1 + 0.5],
                [cx1 - 3.75, cz1 + 1.9], [cx1 - 3.75, cz1 + 3.0], [cx1 - 3, cz1 + 2.5], [cx1 + 3, cz1 + 2.5], [cx1 + 3.75, cz1 + 3.5],
                [cx1 + 3, cz1 + 4.5], [cx1 - 3, cz1 + 4.5], [cx1 - 3.75, cz1 + 3.5], [cx1 - 3, cz1 + 2.5], [cx1 + 3, cz1 + 2.5],
                [cx1 + 3.75, cz1 + 3.5], [cx1 + 3, cz1 + 4.5], [cx1 - 3, cz1 + 4.5], [cx1 - 3.75, cz1 + 3.5], [cx1 - 3.75, cz1 + 1.9],
                [cx1 - 3.75, cz1 + 0.5], [cx1, cz1]], "min_y": 2 * STORY_FLAT - 0.5},
]
plan["checks"] = {"pit": [-156.0, -39.0], "yard": [-156.0, -39.0], "tunnel": [-156.0, 0.0],
                  "cordon": {"from": [-203.0, 0.5], "to": [-226.0, 0.5], "stop_x": XC - 0.6}}

plan["buildings_count"] = len(B)
plan["items_count"] = len(FI["items"])

# ================================================================== запись
text = json.dumps(plan, ensure_ascii=False, indent=1)
text = re.sub(r"\[\s+((?:-?[\d.]+,\s+)*-?[\d.]+)\s+\]", lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]", text)
text = re.sub(r"\[\s+(\"[A-Za-z_0-9]+\",(?:\s+-?[\d.]+,?)+)\s+\]", lambda m: "[" + re.sub(r"\s+", " ", m.group(1)) + "]", text)
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
    # освещение — своё, не из других карт (владелец 2026-10-24, AGENTS.md п. 10)
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
    'ssil_enabled = true', 'ssil_radius = 4.0', 'ssil_intensity = 1.0',
    'glow_enabled = true', 'glow_intensity = 0.25', 'glow_bloom = 0.04', 'glow_hdr_threshold = 1.4',
    'fog_enabled = true', 'fog_light_color = Color(0.74, 0.72, 0.7, 1)', 'fog_light_energy = 0.7', 'fog_density = 0.00028',
    'fog_sky_affect = 0.1', 'fog_height = -2.0', 'fog_height_density = 0.0',
    'adjustment_enabled = true', 'adjustment_contrast = 1.04', 'adjustment_saturation = 0.96',
    '[node name="ProspektStudy" type="Node3D"]',
    'script = ExtResource("launch")',
    'metadata/purpose = "Карта «Проспект» — серый блокаут, редакция 3: проспект с поворотом на 90° · правило масштаба E"',
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
print(json.dumps({"buildings": len(B), "items": len(FI["items"]), "cover": len(FI["cover"]),
                  "routes": len(plan["probe_routes"]), "json": str(OUT_JSON.relative_to(ROOT)), "scene": str(OUT_SCENE.relative_to(ROOT))},
                 ensure_ascii=False))
