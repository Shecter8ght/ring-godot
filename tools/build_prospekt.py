# -*- coding: utf-8 -*-
"""Серый блокаут карты «Проспект» (docs/design/prospekt_map.md), редакция 4 — улица с поворотом.

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

Замечания владельца 2026-10-24 к блокауту 3 (редакция 4): банк — отдельное трёхэтажное здание по мотивам кинотеатра
«Родина» (Streets of Tarkov) с хранилищем на −1, подкопом из паркинга и металлическим забором; сквер — до края карты,
разнообразный (площадь с памятником, подпорные стенки, площадка, баскетбол, лиственные деревья); стройку — за «Ярус»,
каркас 9 этажей с краном; выход — тоннель на месте южного тупика, над ним железная дорога с упавшим составом (вагоны
и в сквере); пункт эвакуации у «Вершины» — до края карты с армейскими палатками; жилые дома глухие, магазины в два
этажа, у некоторых выход на крышу с лутом; обзор каждые 50–90 м чем-то перебит; места лута; грузовые контейнеры;
наполнить «Ярус» и банк; паркинг −1 — по нормам (ряды мест, проезды, лестницы и колонны не мешают движению).
Замечания 2026-10-25 (редакция 5): на повороте — высотка, первый этаж — магазины насквозь (ПВЗ, пивная, табак, кафе,
парикмахерская, аптека); сквер начинается сразу за ней и плотнее, вагоны лежат на его объектах; по периметру —
логичные преграды вместо невидимой стены; стройка «лысовата» — котлован с водой, техника, кучи; вокзал у насыпи;
паркинг — побитые машины вкривь, стекло, мусор, открытые двери и багажники, у подкопа грунт и прожекторы.
Замечания 2026-10-25 (редакция 6): железная дорога — шесть путей с опорами и проводами контактной сети; в городе —
столбы с проводами; въезд в паркинг был у самых домов — два спуска в углах двора, подальше от подъездов.

Проспект вдвое шире (владелец 2026-11-07, вариант Б «магистраль», docs/design/prospekt_map.md §20): код ниже пишет карту
в прежних координатах, а в конце tools/prospekt_widen.py переносит план на расширенный проспект; то, что зависит от
нового профиля, пишется сразу в новых координатах (mark() … raw()). PROSPEKT_WIDEN=now — прежняя карта,
PROSPEKT_OUT=<папка> — план и сцена в свою папку (варианты на схему, карта не меняется).

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

import os

import prospekt_light as LIGHT
import prospekt_widen as WIDEN

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "data" / "blockouts" / "prospekt.json"
OUT_SCENE = ROOT / "scenes" / "levels" / "prospekt_study.tscn"
# PROSPEKT_OUT — своя папка для плана и сцены (варианты расширения проспекта на схему, не трогая карту)
PREVIEW_DIR = os.environ.get("PROSPEKT_OUT", "")
# с 2026-11-08 карта правится руками (решение владельца): в проект — только по PROSPEKT_OVERWRITE=1
if not PREVIEW_DIR and os.environ.get("PROSPEKT_OVERWRITE") != "1":
    print("tools/build_prospekt.py: «Проспект» правится руками в редакторе (docs/level_editing.md): запуск перезаписал бы ручные правки сцен и наполнения. Заготовки — в свою папку: PROSPEKT_OUT=<папка>; собрать карту заново поверх правок — только если владелец решил: PROSPEKT_OVERWRITE=1.")
    raise SystemExit(1)
if PREVIEW_DIR:
    OUT_JSON = Path(PREVIEW_DIR) / "prospekt.json"
    OUT_SCENE = Path(PREVIEW_DIR) / "prospekt_study.tscn"
# id() записей плана, написанных сразу в координатах расширенного проспекта (прочее переносит WIDEN.warp_plan)
RAW_IDS: set[int] = set()

WK = 1.3
HK = 1.15
RH = 8.5                       # полупроезжая часть 2+2 с разделительной
MED = 1.5
SW = 5.5 * WK                  # тротуар 7.15
F = RH + SW                    # 15.65 — край тротуара от оси
STORY_FLAT = 2.7 * HK
STORY_RETAIL = 4.0
DOOR_H = 2.1 * HK
# паркинг −1: 6 м в свету под балками 0,9 м и плитой двора 0,4 м — выбор владельца на стенде 2026-10-29
# (tools/parking_probe.tscn, зал D: «как в Таркове»); было −3,2
PIT_Y = -7.3
PIT_BEAM = 0.9                                                  # глубина балок паркинга
TUNNEL_Y = -3.3

XW = -218.0                    # западный край карты
XC = -210.0                    # плиты кордона
CR = 55.0                      # радиус поворота
CX, CZ = 0.0, 55.0             # центр поворота
XS = CX + CR                   # ось южного плеча x = 55
ZS_END = 275.0
EMB_Z0, EMB_Z1 = 244.0, 258.0  # насыпь на юге: подошва и бровка откоса (14 м на 6 м — 23°, по нему ходят и ИИ)
RAIL_Z1 = 290.0                # южный край насыпи: шесть путей (владелец 2026-10-25: «четыре или шесть путей»)
TRACKS = [264.6 + 4.1 * k for k in range(6)]                    # оси путей, междупутье 4,1 м
YARD_Z0 = -124.0               # северный край двора: вдоль забора — хозяйственный проезд к спускам в паркинг
EMB_H = 6.0                    # высота насыпи

rng = random.Random(24)

plan: dict = {
    "version": 6,
    "purpose": "Карта «Проспект»: серый блокаут — проспект с поворотом на 90° направо, пролог и короткие рейды",
    "north": "-Z",
    "scale": {"width_k": WK, "height_k": HK, "story_flat": STORY_FLAT, "door_h": DOOR_H},
    "bounds": [-250.0, -150.0, 200.0, 318.0],
    # Г с карманом стройки и вокзала за «Ярусом» (x −152…−62, z 112…275); сквер — до насыпи на юге
    "boundary": [[XW, YARD_Z0], [160.0, YARD_Z0], [160.0, RAIL_Z1], [-152.0, RAIL_Z1], [-152.0, 112.0], [XW, 112.0]],
    "surfaces": [], "ground_holes": [], "slabs": [], "walls": [], "boxes": [], "columns": [],
    "stairs": [], "ramps": [], "lamps": [], "signs": [], "buildings": [], "spawns": [], "exits": [], "switches": [], "doors": [],
    "locations": [], "probe_routes": [], "checks": {}, "beams": [], "loot": [],
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

# Модели городской библиотеки RING_Urban_95 после ретопологии (владелец 2026-10-25: «где-то тут лежат лоуполи ассеты,
# остальное делай сам»): tools/urban95_export.py → assets/models/urban95, индекс data/urban95_models.json. Предмет u()
# с моделью в индексе ставится моделью («m:ID»), серые наборы, у которых есть модель, — тоже (KIT_MODELS: набор →
# модель и поправка курса, когда длинная ось модели — X, а набора — Z). Остальное — серые формы, пока нет своих моделей.
MODELS_INDEX = ROOT / "data" / "urban95_models.json"
MODEL_IDS = set(json.loads(MODELS_INDEX.read_text(encoding="utf-8"))["models"].keys()) if MODELS_INDEX.exists() else set()
# перед входами в здания — свободные площадки (x0, z0, x1, z1): киоски, тумбы, деревья и урны с них убираются при
# записи данных (бумажный мусор и стекло остаются); владелец 2026-10-29: «чтобы не было тесно и нелогично»
KEEP_CLEAR: list[tuple[float, float, float, float]] = []
LITTER = {"paper", "paper_ball", "glass_shards"}

KIT_MODELS = {
    "jersey": ("U01_01", 90.0), "jersey_rw": ("U01_01", 90.0), "crowd_barrier": ("U01_02", 90.0), "cone": ("U01_04", 0.0),
    "planter": ("U02_02", 0.0), "bench": ("U02_03", 0.0), "bollard": ("U02_04", 0.0), "bin": ("U02_05", 0.0),
    "sandbags": ("U03_02", 90.0), "sign_parking": ("U03_03", 0.0), "kiosk": ("U05_02", 0.0), "food_kiosk": ("R05", 0.0),
    "sign_crossing": ("U06_02", 0.0), "delineator": ("U07_03", 0.0), "billboard": ("U10_05", 0.0), "fence": ("U11_02", 90.0),
    "water_barrier": ("U11_05", 90.0), "water_barrier_w": ("U11_05", 90.0), "lamp": ("U12_03", 0.0), "tent": ("U13_01", 0.0),
    "traffic_light": ("U15_02", 0.0), "road_barrier": ("U15_04", 0.0), "dumpster": ("R02", 0.0),
    # свой транспорт (tools/prospekt_vehicles/game_export.py): группы PV_* — модели вперемешку по позиции (MallFiller);
    # «m:U14_01» — брошенные машины улиц, хэтчбек Urban 95 остаётся среди них
    "car": ("PV_car", 0.0), "car_open": ("PV_car_open", 0.0), "car_wreck": ("PV_car_wreck", 0.0),
    "suv_open": ("PV_suv_open", 0.0), "m:U14_01": ("PV_car_street", 0.0), "bus_city": ("PV_bus_city", 0.0),
    "paz": ("PV_paz_any", 0.0), "minibus": ("PV_minibus", 0.0),
    # партия 2: спецмашины своими группами вместо серых форм; перевёрнутый автобус — модель лёжа на левом борту
    "taxi": ("PV_taxi_any", 0.0), "police_car": ("PV_police_any", 0.0), "van": ("PV_van_any", 0.0),
    "ambulance": ("PV_ambulance_any", 0.0), "bus_over": ("PV_bus12_over", 0.0),
    # свои растения (tools/prospekt_plants/game.py): группы P_* — экземпляры вперемешку по позиции, у каждого LOD и ствол
    "tree_birch": ("P_birch", 0.0), "tree_round": ("P_linden", 0.0), "tree_poplar": ("P_poplar", 0.0),
    "bush_big": ("P_lilac", 0.0), "hedge": ("P_hedge", 90.0),
    # свои ограждения и город (tools/prospekt_city/game_export.py): забор района из плит ПО-2 со спиралью, без колючки — «po2»;
    # группы PC_* (tools/prospekt_city/index_groups.py) — контейнеры по цвету, опоры с фонарём через две, остановки и разбитые
    "district_fence": ("PC01_PO2", 0.0), "po2": ("PC01_PO2_BARE", 0.0),
    "garage": ("PC02_GARAGE", 0.0), "garage_open": ("PC02_GARAGE_OPEN", 0.0),
    "container20": ("PC_container20_any", 0.0), "container40": ("PC_container40_any", 0.0),
    "pole_conc": ("PC_pole04_any", 0.0), "pole_trolley": ("PC04_TROLLEY", 0.0),
    "bus_stop": ("PC_busstop_any", 0.0), "ktp": ("PC07_KTP", 0.0),
    # пролом и поваленная плита — у выхода двором ЖК; ракушки — двор дома 7; открытые — только там, где внутри лут
    "po2_breach": ("PC01_PO2_BREACH", 0.0), "po2_fallen": ("PC01_PO2_FALLEN", 0.0),
    "shell": ("PC02_SHELL", 0.0), "shell_open": ("PC02_SHELL_OPEN", 0.0),
    "container20_open": ("PC03_C20_OPEN", 0.0), "container40_open": ("PC03_C40_OPEN", 0.0),
    "ktp_open": ("PC07_KTP_OPEN", 0.0),
}
MODELS_NOSOLID = ["U19_02", "U16_04", "U15_05", "U10_01", "U19_01", "U14_04", "U10_05", "U02_01", "U14_03", "U08_03"]
MODELS_POLES = ["U15_02", "U10_02", "U12_03", "U03_03", "U06_02", "U07_02", "U10_03", "U19_05",
                "PC04_POLE04", "PC04_POLE04_LAMP", "PC04_TROLLEY"]


def u(aid: str, x: float, z: float, yaw: float = 0.0, s: float = 1.0, y: float = 0.0, cover: bool = False) -> None:
    """Предмет улицы: моделью Urban 95, если она есть в игре, иначе серой формой. yaw — куда смотрит лицевая сторона."""
    mid = aid.split("_")[0] if aid.startswith("R0") else "_".join(aid.split("_")[:2])
    if mid == "R04":
        mid = "U14_01"                                          # R04 — 161 тыс. треугольников, на сотни машин тяжело
    if mid in MODEL_IDS:
        put("m:" + mid, x, z, yaw, s, y, -1, 0.0, cover)
        return
    if aid in U_KIT:
        kit = U_KIT[aid]
        tint = rng.choice(CAR_TINTS) if kit == "car" else -1
        put(kit, x, z, yaw, s, y, tint, 0.0, cover)
    elif aid in U_BOX:
        w, h, d, mat = U_BOX[aid]
        box(x, y + h * s * 0.5, z, w * s, h * s, d * s, mat, yaw, True)
        if cover:
            FI["cover"].append([round(x, 1), round(z, 1)])


def upper_floor(title: str, cx: float, cz: float, w: float, d: float, yaw: float = 0.0, h1: float = STORY_RETAIL,
                roof: bool = False) -> None:
    """Второй этаж магазина над залом StudyBuilding (владелец 2026-10-24: «магазины сделать двухэтажными, на некоторых —
    выход на крышу с полезным лутом»): наружная стальная лестница вдоль задней стены, дверь, окна; склад или контора.
    roof — изнутри марш на крышу у фасада, на крыше парапет и место лута. Местные координаты: +z — фасад зала."""
    fr = Frame(cx, cz, yaw)
    y0 = h1 + 0.175                     # верх плиты крыши зала
    h2 = 3.6
    hx, hz = w * 0.5, d * 0.5
    door = -hx + 7.5
    sz = -hz - 0.85
    a, b = fr.p(-hx + 0.3, sz), fr.p(-hx + 6.7, sz)
    stair((a[0], 0.0, a[1]), (b[0], y0, b[1]), 1.3, "steel")
    lc = fr.p(door, sz - 0.05)
    box(lc[0], y0 - 0.12, lc[1], 1.9, 0.24, 1.6, "steel", yaw)
    seg(fr, door - 0.95, sz - 0.85, door + 0.95, sz - 0.75, y0, y0 + 1.0, "steel")
    wall_x(hz, -hx, hx, y0, h2, windows(-hx, hx, 3.0, 1.6, 0.9, 2.4), 0.25, "wall", fr)
    wall_x(-hz, -hx, hx, y0, h2, [(door, 1.17, 2.42)] + windows(-hx, hx, 4.0, 1.2, 1.0, 2.2, [(door, 1.17)]), 0.25, "wall", fr)
    for xs in (-hx, hx):
        wall_z(xs, -hz, hz, y0, h2, [(0.0, 1.4, 2.3, 0.9)], 0.25, "wall", fr)
    if w >= 14.0:
        wall_z(0.0, -hz, hz, y0, h2, [(-hz + 1.6, 1.17, 2.42)], 0.15, "wall", fr)
    holes = []
    if roof:
        holes = [fr.rect(hx - 6.8, hz - 1.65, hx - 0.8, hz - 0.15)]
        a, b = fr.p(hx - 1.0, hz - 0.9), fr.p(hx - 6.6, hz - 0.9)
        stair((a[0], y0, a[1]), (b[0], y0 + h2 + 0.25, b[1]), 1.1)
    slab("roof_" + title, fr.rect(-hx - 0.2, -hz - 0.2, hx + 0.2, hz + 0.2), y0 + h2 + 0.25, 0.25, "slab", holes)
    yr = y0 + h2 + 0.25
    for (lx0, lz0, lx1, lz1) in [(-hx - 0.2, -hz - 0.2, hx + 0.2, -hz), (-hx - 0.2, hz, hx + 0.2, hz + 0.2),
                                 (-hx - 0.2, -hz, -hx, hz), (hx, -hz, hx + 0.2, hz)]:
        seg(fr, lx0, lz0, lx1, lz1, yr, yr + 1.0, "concrete")
    # контора и склад второго этажа: шкаф, ящики, стол
    for (lx, lz, kind, tier, note) in [(-hx + 1.2, hz - 1.0, "cabinet", "common", "шкаф конторы"),
                                       (hx - 1.5, -hz + 1.2, "crate", "common", "склад магазина"),
                                       (-hx + 3.5, 0.0, "loose", "common", "на столе")]:
        x, z = fr.p(lx, lz)
        loot(x, y0, z, kind, tier, title + ": " + note)
    x, z = fr.p(-hx + 3.5, 0.0)
    box(x, y0 + 0.38, z, 1.4, 0.75, 0.8, "accent", yaw)
    x, z = fr.p(0.0, 0.0)
    plan["lamps"].append([round(x, 2), y0 + h2 - 0.4, round(z, 2), 0.6, 8.0])
    if roof:
        x, z = fr.p(-hx + 2.0, -hz + 1.5)
        put("sandbags", x, z, yaw + 90.0, 1.0, yr, -1, 0.0, True)
        x, z = fr.p(-hx + 2.0, 0.5)
        loot(x, yr, z, "crate", "good", title + ": тайник на крыше")
        x, z = fr.p(0.0, -hz + 1.2)
        loot(x, yr, z, "backpack", "med", title + ": рюкзак на крыше")
        x, z = fr.p(hx - 2.0, -hz + 1.5)
        put("ac_unit", x, z, yaw, 1.0, yr + 0.3)


def face(fx: float, fz: float) -> float:
    """Угол поворота, при котором лицевая сторона (+Z модели) смотрит в направлении (fx, fz)."""
    return math.degrees(math.atan2(fx, fz))


def revolving_entrance(cx: float, cz: float, yaw: float, doors: bool = True) -> None:
    """Входная группа в фасаде (cx, cz — середина входа на линии фасада, yaw — куда смотрит вход): карусель утоплена
    в стену на полдиаметра, по бокам — распашные стеклянные двери, над всем — козырёк на тягах. Владелец 2026-10-29:
    «круглые двери стоят как будто отдельно от здания» — прежде карусель стояла перед стеной впритык."""
    r = math.radians(yaw)
    ox, oz = math.sin(r), math.cos(r)                            # наружу
    ax, az = math.cos(r), -math.sin(r)                           # вдоль фасада

    def at(a: float, o: float) -> tuple[float, float]:
        return cx + ax * a + ox * o, cz + az * a + oz * o

    x, z = at(0.0, 0.55)
    u("U08_01_revolving_door", x, z, yaw, 1.0, 0.0, True)
    if doors:
        for a in (-2.65, 2.65):
            x, z = at(a, 0.08)
            u("U08_02_glass_doors", x, z, yaw, 1.0, 0.0, True)
    span = 8.4 if doors else 3.6
    x, z = at(0.0, 1.2)
    box(x, 3.32, z, span, 0.14, 2.4, "steel", yaw, False)        # козырёк выше карусели (2,8 м)
    for a in (-span * 0.5 + 0.3, span * 0.5 - 0.3):
        x0, z0 = at(a, 0.0)
        x1, z1 = at(a, 2.3)
        beam((x0, 4.4, z0), (x1, 3.4, z1), 0.05, 0.05, "steel")  # тяги к стене


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


class Frame:
    """Местные координаты постройки (x — вдоль фасада, z — вглубь, +z — лицо) в мировые; поворот кратен 90°."""

    def __init__(self, cx: float, cz: float, yaw: float = 0.0):
        self.cx, self.cz, self.yaw = cx, cz, yaw
        self.c, self.s = round(math.cos(math.radians(yaw))), round(math.sin(math.radians(yaw)))

    def p(self, lx: float, lz: float) -> tuple[float, float]:
        return self.cx + lx * self.c + lz * self.s, self.cz - lx * self.s + lz * self.c

    def rect(self, lx0: float, lz0: float, lx1: float, lz1: float) -> list:
        a, b = self.p(lx0, lz0), self.p(lx1, lz1)
        return [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]


WORLD = Frame(0.0, 0.0, 0.0)


def seg(fr: Frame, lx0: float, lz0: float, lx1: float, lz1: float, y0: float, y1: float, mat: str = "wall") -> None:
    r = fr.rect(lx0, lz0, lx1, lz1)
    wall(r[0], r[1], r[2], r[3], y0, y1, mat)


def wall_x(z: float, x0: float, x1: float, y0: float, h: float, gaps=(), t: float = 0.25, mat: str = "wall",
           fr: Frame = WORLD) -> None:
    """Стена вдоль x (z = const) с проёмами (x, ширина, верх[, низ]); низ > 0 — окно с подоконником."""
    x = x0
    for c in sorted(gaps, key=lambda g: g[0]):
        a, b = c[0] - c[1] * 0.5, c[0] + c[1] * 0.5
        top = min(c[2], h)
        low = c[3] if len(c) > 3 else 0.0
        if a - x > 0.01:
            seg(fr, x, z - t * 0.5, a, z + t * 0.5, y0, y0 + h, mat)
        if h - top > 0.01:
            seg(fr, a, z - t * 0.5, b, z + t * 0.5, y0 + top, y0 + h, mat)
        if low > 0.01:
            seg(fr, a, z - t * 0.5, b, z + t * 0.5, y0, y0 + low, mat)
        x = b
    if x1 - x > 0.01:
        seg(fr, x, z - t * 0.5, x1, z + t * 0.5, y0, y0 + h, mat)


def wall_z(x: float, z0: float, z1: float, y0: float, h: float, gaps=(), t: float = 0.25, mat: str = "wall",
           fr: Frame = WORLD) -> None:
    """То же вдоль z (x = const); проёмы (z, ширина, верх[, низ])."""
    z = z0
    for c in sorted(gaps, key=lambda g: g[0]):
        a, b = c[0] - c[1] * 0.5, c[0] + c[1] * 0.5
        top = min(c[2], h)
        low = c[3] if len(c) > 3 else 0.0
        if a - z > 0.01:
            seg(fr, x - t * 0.5, z, x + t * 0.5, a, y0, y0 + h, mat)
        if h - top > 0.01:
            seg(fr, x - t * 0.5, a, x + t * 0.5, b, y0 + top, y0 + h, mat)
        if low > 0.01:
            seg(fr, x - t * 0.5, a, x + t * 0.5, b, y0, y0 + low, mat)
        z = b
    if z1 - z > 0.01:
        seg(fr, x - t * 0.5, z, x + t * 0.5, z1, y0, y0 + h, mat)


def windows(a0: float, a1: float, step: float, w: float, low: float, top: float, doors=()) -> list:
    """Окна через шаг по стене от a0 до a1 мимо дверей [(центр, ширина)]."""
    out = []
    a = a0 + step * 0.5
    while a < a1 - w * 0.5:
        if all(abs(a - d[0]) > (w + d[1]) * 0.5 + 0.6 for d in doors) and a - w * 0.5 > a0 + 0.4:
            out.append((a, w, top, low))
        a += step
    return out


def slab(sid: str, rect: list, y_top: float, t: float = 0.3, mat: str = "slab", holes=()) -> None:
    plan["slabs"].append({"id": sid, "rect": [round(v, 3) for v in rect], "y_top": y_top, "t": t, "mat": mat,
                          "holes": [[round(v, 3) for v in h] for h in holes]})


def stair(a: tuple, b: tuple, width: float, mat: str = "concrete") -> None:
    """Марш от a до b (x, y, z): ступени по 17 см."""
    plan["stairs"].append({"from": [round(v, 3) for v in a], "to": [round(v, 3) for v in b], "width": width,
                           "count": max(6, int(abs(b[1] - a[1]) / 0.17 + 0.5)), "mat": mat})


def beam(a: tuple, b: tuple, w: float, d: float, mat: str = "concrete") -> None:
    plan["beams"].append([[round(v, 3) for v in a], [round(v, 3) for v in b], w, d, mat])


LOOT_KINDS = ("crate", "backpack", "suitcase", "body", "car", "register", "safe", "cabinet", "loose", "cells", "weapon", "med")


def loot(x: float, y: float, z: float, kind: str, tier: str = "common", note: str = "", yaw: float = 0.0) -> None:
    """Место лута для левел-дизайна: вид места (контейнер или свободно) и ценность — common, med, good, weapon, quest."""
    assert kind in LOOT_KINDS, kind
    plan["loot"].append({"at": [round(x, 2), round(y, 2), round(z, 2)], "kind": kind, "tier": tier, "note": note,
                         "yaw": round(yaw, 1)})


# ------------------------------------------------------------------ расширенный проспект: новые координаты
# Владелец 2026-11-07: «сам проспект надо в 2 раза расширять» — выбран вариант Б «магистраль» (tools/prospekt_widen.py):
# 4 + 4 полосы, разделительная 6 м, парковочные карманы 2,5 м, тротуары 11,8 м. Карта пишется в прежних координатах и
# в конце переносится (WIDEN.warp_plan); то, что зависит от нового профиля (разметка полос, зебры, плиты кордона, машины
# в карманах, застройка новых полос земли), пишется сразу в новых координатах — между mark() и raw().
ZA, XSN, CRN = WIDEN.ZA_NEW, WIDEN.XS_NEW, WIDEN.CR_NEW          # оси плеч и радиус оси поворота
RHN, EDGEN, MEDN, FN = WIDEN.RH_NEW, WIDEN.EDGE_NEW, WIDEN.MED_NEW, WIDEN.F_NEW
rng2 = random.Random(1107)                                      # своё зерно: прежние случайные расстановки не сдвигаются
RAW_KEEP: list = []                                             # держит записи живыми, чтобы id() не переиспользовались


def _lists() -> dict[str, list]:
    out = {k: v for k, v in plan.items() if isinstance(v, list)}
    out.update({"filler." + k: v for k, v in FI.items() if isinstance(v, list)})
    return out


def mark() -> dict[str, int]:
    return {k: len(v) for k, v in _lists().items()}


def raw(snap: dict[str, int]) -> None:
    """Записи плана после snap — уже в координатах расширенного проспекта: перенос их не трогает."""
    for k, v in _lists().items():
        for e in v[snap.get(k, 0):]:
            RAW_IDS.add(id(e))
            RAW_KEEP.append(e)


def n_curve_point(phi: float, d: float) -> tuple[float, float]:
    r = CRN + d
    return CX + r * math.sin(phi), CZ - r * math.cos(phi)


def n_along(step: float, d: float, s0: float = 0.0, skip=None, curve: bool = True):
    """Как along(), но по оси расширенного проспекта; curve=False — только прямые плечи."""
    out = []
    L1, Lc, L2 = 0.0 - XW, CRN * math.pi * 0.5, ZS_END - CZ
    s = s0
    while s < L1 + Lc + L2:
        if s < L1:
            x, z, h = XW + s, ZA - d, 90.0
        elif s < L1 + Lc:
            phi = (s - L1) / CRN
            x, z = n_curve_point(phi, d)
            h = 90.0 - math.degrees(phi)
            if not curve:
                s += step
                continue
        else:
            x, z, h = XSN + d, CZ + (s - L1 - Lc), 0.0
        if skip is None or not skip(x, z):
            out.append((x, z, h))
        s += step
    return out


def n_curve_strip(d0: float, d1: float, mat: str, t: float, y: float = 0.0, n: int = 36, solid: bool = False) -> None:
    dm, width = (d0 + d1) * 0.5, abs(d1 - d0)
    for i in range(n):
        a0, a1 = (math.pi * 0.5) * i / n, (math.pi * 0.5) * (i + 1) / n
        am = (a0 + a1) * 0.5
        x, z = n_curve_point(am, dm)
        box(x, y + t * 0.5, z, (CRN + max(d0, d1)) * (a1 - a0) * 1.04 + 0.05, t, width, mat, -math.degrees(am), solid)


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
# разметка — пунктир между полосами по всей оси (сразу по новому профилю: 4 + 4 полосы), краевая линия у карманов
_snap = mark()
for k in range(1, WIDEN.LANES):
    for side in (1.0, -1.0):
        for (x, z, h) in n_along(4.0, side * (MEDN + WIDEN.LANE * k), 8.0):
            box(x, 0.085, z, 0.15, 0.02, 2.0, "stripe", h, False)
if WIDEN.POCKET > 0.0:
    for side in (1.0, -1.0):
        box((XW + 0.0) * 0.5, 0.085, ZA - side * EDGEN, -XW, 0.02, 0.15, "stripe", 0.0, False)
        box(XSN + side * EDGEN, 0.085, (CZ + ZS_END) * 0.5, 0.15, 0.02, ZS_END - CZ, "stripe", 0.0, False)
        n_curve_strip(side * EDGEN - 0.075, side * EDGEN + 0.075, "stripe", 0.02, 0.075)
raw(_snap)

# переходы: зебра у проезда во двор (запад) и на южном плече; светофоры, знаки, тактильная плитка
CROSS_W = -126.0
CROSS_S = 150.0
# зебры — через всю ширину нового проспекта (с карманами), в разделительной под ними разрыв газона
_snap = mark()
for i in range(max(1, round(2.0 * RHN / 2.2))):
    off = -RHN + 1.1 + i * 2.2
    box(CROSS_W, 0.085, ZA + off, 5.0, 0.02, 1.1, "stripe", 0.0, False)
    box(XSN + off, 0.085, CROSS_S, 1.1, 0.02, 5.0, "stripe", 0.0, False)
raw(_snap)
for srf in plan["surfaces"]:
    if srf["id"] == "median_w":
        srf["holes"] = [[CROSS_W - 3.0, -MED, CROSS_W + 3.0, MED]]
    elif srf["id"] == "median_s":
        srf["holes"] = [[XS - MED, CROSS_S - 3.0, XS + MED, CROSS_S + 3.0]]
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
# отделка как в городском переходе (владелец 2026-11-08: «красиво и реалистично оформим подземный переход»): пол —
# гранитные плиты, стены — кафель с тёмным цоколем и полосой, потолок — подвесной; свет, витрины, указатели, поручни
# и пандус лестниц — ProspektLandscape._tunnel (по плитам tunnel_floor / tunnel_roof)
plan["slabs"].append({"id": "tunnel_floor", "rect": [TX0, TZN, TX1, TZS], "y_top": TUNNEL_Y, "t": 0.3, "mat": "tunnel_floor", "holes": []})
plan["slabs"].append({"id": "tunnel_roof", "rect": [TX0 - 0.4, -TUN, TX1 + 0.4, TUN], "y_top": -0.1, "t": 0.4, "mat": "tunnel_ceiling", "holes": []})
wall(TX0 - 0.4, TZN, TX0, TZS, TUNNEL_Y, 0.0, "tunnel_tile")
wall(TX1, TZN, TX1 + 0.4, TZS, TUNNEL_Y, 0.0, "tunnel_tile")
wall(TX0, TZN - 0.4, TX1, TZN, TUNNEL_Y, 0.0, "tunnel_tile")
wall(TX0, TZS, TX1, TZS + 0.4, TUNNEL_Y, 0.0, "tunnel_tile")
for sgn in (-1.0, 1.0):
    zc = sgn * (STAIR_Z + 2.0)
    plan["stairs"].append({"from": [TX1, 0.15, zc], "to": [TX0 + 1.5, TUNNEL_Y, zc], "width": 3.8, "count": 20, "mat": "concrete"})
    box((TX0 + 1.5 + TX1) * 0.5, -1.8, sgn * STAIR_Z, TX1 - (TX0 + 1.5), 3.6, 0.2, "tunnel_tile")
    box((TX0 + 1.5 + TX1) * 0.5, 0.5, sgn * STAIR_Z, TX1 - (TX0 + 1.5), 1.0, 0.2, "concrete")
    box((TX0 + TX1) * 0.5, 0.5, sgn * (TZS + 0.2), TX1 - TX0 + 0.8, 1.0, 0.4, "concrete")
    box((TX0 - 0.4 + TX0 + 1.5) * 0.5, 0.5, sgn * STAIR_Z, 1.9, 1.0, 0.2, "concrete")
    # парапет и по западному краю проёма лестницы: на широком тротуаре к нему подходят и с запада (от кофейни)
    box(TX0 - 0.2, 0.5, sgn * (STAIR_Z + TZS) * 0.5, 0.4, 1.0, TZS - STAIR_Z + 0.2, "concrete")
    u("U03_04_handrail_slope", (TX0 + 1.5 + TX1) * 0.5, sgn * (STAIR_Z + 0.25), 90.0 if sgn > 0 else -90.0)
    sign("подземный переход", TX1 + 1.5, 2.6, sgn * 13.0, 40)
    u("U10_03_wayfinding", TX1 + 2.0, sgn * 10.6, 90.0)
for z in (-5.0, 0.0, 5.0):
    put("kiosk", TX0 + 1.6, z, 90.0, 0.9, TUNNEL_Y, -1, 0.0, True)
# свет перехода — ряды светильников в подвесном потолке (почти все мёртвые) и дневной свет с лестниц:
# ProspektLandscape._tunnel; ламп плана и промышленных светильников здесь нет
plan["walk_holes"] = [[TX0, TZN, TX1, -STAIR_Z], [TX0, STAIR_Z, TX1, TZS]]
FI["stories"].append({"label": "тело под брезентом у ларька в переходе", "at": [TX1 - 1.5, 3.0], "height": 1.5})
# два года без людей: бумаги, бутылки и банки по полу, стекло у разбитой витрины, угол с коробками и мешками (тут
# ночевали), лужа под протечкой, пыль
rng_t = random.Random(808)
for _ in range(26):
    put(rng_t.choice(["paper", "paper", "paper_ball", "bottle", "can"]), rng_t.uniform(TX0 + 0.5, TX1 - 0.5),
        rng_t.uniform(TZN + 1.0, TZS - 1.0), rng_t.uniform(0, 360), 1.0, TUNNEL_Y)
for k in range(4):
    put("glass_shards", TX1 - 0.9 - rng_t.uniform(0.0, 0.8), -6.2 + k * 0.5, rng_t.uniform(0, 360), rng_t.uniform(0.9, 1.3), TUNNEL_Y)
put("boxes", TX1 - 0.6, -8.6, 10.0, 1.0, TUNNEL_Y)
put("bags", TX1 - 0.7, -7.9, 70.0, 1.0, TUNNEL_Y)
put("trash_pile", TX1 - 0.9, 8.8, 30.0, 0.8, TUNNEL_Y)
put("puddle", (TX0 + TX1) * 0.5 + 0.8, 2.5, 0.0, 2.4, TUNNEL_Y)
put("dust", (TX0 + TX1) * 0.5, -3.0, 0.0, 1.0, TUNNEL_Y)

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
ROAD_CARS = [(-170, 6.0, 87, 1), (-140, -6.0, 95, 0), (-12, 5.5, 88, 1)]
for (x, z, yaw, k) in ROAD_CARS:
    u("R04_car" if k else "U14_01_hatchback", x, z, yaw, 1.0, 0.0, True)
put("bus_city", -142.0, -1.0, 62.0, 1.0, 0.0, 8, 0.0, True)       # жёлтый автобус поперёк у перехода
# разбор Таркова и Ready or Not (prospekt_dressing.md § 7): машины разных классов, каждая — сценка с мелочью вокруг
put("paz", -193.0, 5.6, 92.0, 1.0, 0.0, 8, 0.0, True)                # маршрутный ПАЗ у остановки, двери открыты
# модель скорой (5,7 м с зеркалами) длиннее серой формы — на метр к востоку: маршрут пролога идёт вдоль её задка по x −193
put("ambulance", -189.0, -5.4, 97.0, 1.0, 0.0, -1, 0.0, True)       # скорая у пункта эвакуации на кордоне
put("tent", -197.0, -12.4, 90.0)
for (x, z) in [(-194.5, -11.0), (-195.2, -13.6), (-198.8, -10.6)]:
    put("suitcase", x, z, rng.uniform(0, 360))
put("water_bottles", -199.5, -13.4, 30.0)
FI["stories"].append({"label": "пункт эвакуации у кордона: скорая, палатка, чемоданы", "at": [-193.0, -9.0], "height": 4.0})
# перевёрнутый автобус на боку поперёк северной полосы: сумки, конусы, бумаги
put("bus_over", -78.0, -3.6, 96.0, 1.0, 0.0, 9, 0.0, True)
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
for (z, dx, yaw, k) in [(80, -5.5, 2, 1), (102, 6.0, 178, 0), (128, -6.0, -3, 0), (196, -5.8, 0, 0), (222, 6.0, 176, 1)]:
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
# плиты — через всю ширину нового проспекта, от забора до забора (заборы вдоль z ±17,5 переносятся вместе с кварталами)
_snap = mark()
_c0, _c1 = WIDEN.warp(XC, -17.5)[1], WIDEN.warp(XC, 17.5)[1]
_cn = math.ceil((_c1 - _c0) / 2.5 - 1e-6)
for i in range(_cn):
    put("po2", XC, _c0 + (_c1 - _c0) * (i + 0.5) / _cn, 0.0)
raw(_snap)
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
# (-262, -40) — башня 44 эт. в конце проспекта за кордоном (владелец 2026-10-29: «башни за стенами улиц»)
for (x, z, w, d, fl) in [(-262, -80, 18, 24, 17), (-264, -40, 26, 22, 44), (-262, 45, 16, 26, 12), (-258, 85, 18, 22, 25)]:
    building("Outside_W%d" % abs(z), "", (x, z), (w, d), "mass", fl, 3.0, 0.0, 0.0, "", "", 0.0, "Outside")

# ================================================================== западное плечо, север: павильоны, парковка, ЖК «Панорама»
PAV_Z0, PAV_Z1 = -28.0, -17.0                                   # павильоны стрит-ритейла у тротуара
for (bid, label, x0, x1, interior, theme) in [("Coffee", "кофейня «Зерно»", -192, -176, "shop", "register"),
                                             ("Flowers", "цветы", -173, -163, "shop", "shelf"),
                                             ("Pharmacy", "аптека", -160, -146, "pharmacy", "pharmacy"),
                                             ("Clothes", "одежда «Modus»", -143, -123, "shop", "shelf"),
                                             ("Bakery", "пекарня", -108, -94, "shop", "grocery")]:
    # кофейня «Зерно» — дверь закрыта, но не заперта (пролог, docs/design/prologue.md §4.1: подсказка «F»)
    building(bid, label, ((x0 + x1) * 0.5, (PAV_Z0 + PAV_Z1) * 0.5), (x1 - x0, PAV_Z1 - PAV_Z0), "hall", 1, STORY_RETAIL,
             0.0, 0.0, interior, theme, 0.6, extra={"entry_door": 1.2} if bid == "Coffee" else None)
    upper_floor(label, (x0 + x1) * 0.5, (PAV_Z0 + PAV_Z1) * 0.5, x1 - x0, PAV_Z1 - PAV_Z0, 0.0,
                roof=bid in ("Pharmacy", "Clothes", "Bakery"))
    u("U02_02_planter", (x0 + x1) * 0.5 - (x1 - x0) * 0.3, PAV_Z1 + 1.0, 0.0, 1.0, 0.0, True)
    u("U05_03_warning_a", (x0 + x1) * 0.5 + 2.0, PAV_Z1 + 1.2, rng.uniform(-30, 30))
building("Pavilion_Shut", "БЦ «Проспект, 11» · вестибюль и салон связи (закрыты)", (-76.0, (PAV_Z0 + PAV_Z1) * 0.5), (32.0, 11.0),
         "mass", 2, STORY_RETAIL)
# ---- стены улицы (владелец 2026-10-29: «стены улиц», образец — «Эпицентр» Таркова; «чтобы не было тесно и нелогично»):
# над павильонами без выхода на крышу — офисные этажи бизнес-центров со стеклом. Павильоны с крышей-лёжкой и тайником
# (аптека, «Modus», пекарня — просьба владельца 2026-10-24) остаются двухэтажными. Между корпусами — проезд во двор,
# проходы-арки к парковке и 22 м до банка; до жилых корпусов за парковкой — 28 м. Перед входами — свободные площадки.
# БЦ «Проспект, 5»: над кофейней и цветами (арка над проходом между ними), 2 этажа магазинов + 7 офисных;
# вестибюль — стеклянная пристройка на западном углу, вход с бокового проезда, а не из чужого магазина
BC5 = (-192.2, -162.8)
flats("BC_Prospekt5", "БЦ «Проспект, 5» — 9 этажей (закрыт)", ((BC5[0] + BC5[1]) * 0.5, (PAV_Z0 + PAV_Z1) * 0.5), 7, 0, 0.0,
      (BC5[1] - BC5[0], PAV_Z1 - PAV_Z0 + 0.4), 3.6, False, True, 8.03, "West", 0.0)
building("BC_Prospekt5_Lobby", "БЦ «Проспект, 5» · вестибюль (закрыт)", (-194.0, -22.5), (3.6, 8.8), "mass", 1, 4.6, 0.0, 0.0,
         "", "", 0.0, "West")
surface("bc5_apron", "walk", -200.0, PAV_Z0, BC5[0], PAV_Z1, 0.0, 0.05)
revolving_entrance(-195.8, -22.5, -90.0)
sign("БЦ «Проспект, 5» · вход", -196.2, 5.4, -22.5, 40)
KEEP_CLEAR.append((-202.0, -26.0, -195.8, -19.0))
# БЦ «Проспект, 11»: над закрытым павильоном салона связи, 2 + 8 этажей; вход — стеклянная секция на проспект
flats("BC_Prospekt11", "БЦ «Проспект, 11» — 10 этажей (закрыт)", (-76.0, (PAV_Z0 + PAV_Z1) * 0.5), 8, 0, 0.0,
      (32.4, PAV_Z1 - PAV_Z0 + 0.4), 3.6, False, True, 2 * STORY_RETAIL, "West", 0.0)
for dx in (-6.2, 6.2):                                           # витраж вестибюля по сторонам от входа
    u("U08_04_curtainwall", -72.0 + dx, PAV_Z1 + 0.15, 0.0)
revolving_entrance(-72.0, PAV_Z1, 0.0)
sign("БЦ «Проспект, 11» · вход", -72.0, 5.0, PAV_Z1 + 0.4, 40)
KEEP_CLEAR.append((-78.0, PAV_Z1, -66.0, PAV_Z1 + 5.0))
u("U03_01_lightbox", -184.0, PAV_Z1 + 1.3, 0.0)
# упавшее переносное ограждение поперёк тротуара до кофейни (пролог §4.1: перелезть или обойти по дороге)
for z in (-13.6, -11.1):
    put("crowd_barrier", -190.5, z, 0.0, 1.0, 0.0, -1, 90.0, True)
u("U05_02_coffee_kiosk", -168.5, PAV_Z1 + 1.6, 180.0, 1.0, 0.0, True)
FI["stories"].append({"label": "кофейня «Зерно» — закладка пролога в подсобке", "at": [-184.0, -22.0], "height": 6.0})
# парковка за павильонами (над паркингом −1): ряды машин, островки, знаки, фонари
LOT_W = [-196.0, -55.0, -121.7, -30.0]
LOT_E = [-108.2, -55.0, -46.0, -30.0]
surface("lot_w", "parking", LOT_W[0], LOT_W[1], LOT_W[2], LOT_W[3], 0.0, 0.05)
surface("lot_e", "parking", LOT_E[0], LOT_E[1], LOT_E[2], LOT_E[3], 0.0, 0.05)
for (x0, x1) in [(-194.0, -124.0), (-104.0, -48.0)]:
    x = x0
    k = 0
    while x < x1:
        for zrow, yaw in ((-33.0, 180.0), (-52.0, 0.0)):
            if rng.random() < 0.62:
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
# ЖК «Панорама»: корпус 1 (два подъезда по 17 эт.) и корпус 2 (25 эт.) — глухие (владелец 2026-10-24: жилые дома без
# планировок; вместо них — вторые этажи и крыши магазинов)
HZ0, HZ1 = -82.0, -56.0
HCZ = (HZ0 + HZ1) * 0.5
flats("Corpus1_A", "ЖК «Панорама», корпус 1 · подъезд 1 — 17 этажей (закрыт)", (-175.0, HCZ), 17, 0)
flats("Corpus1_B", "ЖК «Панорама», корпус 1 · подъезд 2 — 17 этажей (закрыт)", (-145.0, HCZ), 17, 0)
flats("Corpus2_A", "ЖК «Панорама», корпус 2 · подъезд 1 — 25 этажей (закрыт)", (-89.0, HCZ), 25, 0)
flats("Corpus2_B", "ЖК «Панорама», корпус 2 · подъезд 2 — 25 этажей (закрыт)", (-59.0, HCZ), 25, 0)
for x in (-175.0, -145.0, -89.0, -59.0):
    u("U04_05_wall_niche", x + 3.5, HZ0 - 0.2, 180.0, 1.0, 1.4)
    sign("подъезд", x, 3.6, HZ0 - 0.8, 36)
# двор за домами: площадка, парковка жильцов, мусорная площадка, гаражи, забор с воротами к насыпи
surface("yard_n", "walk", XW + 4.0, YARD_Z0 + 2.5, -40.0, -84.0, 0.0, 0.05)
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
for x in (-190.0, -140.0, -110.0, -70.0):
    put("tree_poplar", x, -88.0, rng.uniform(0, 360), 1.0)
sign("пролом в заборе района · к насыпи", -145.0, 3.6, YARD_Z0 + 1.5, 44)

# ------------------------------------------------------------------ проезд во двор, паркинг −1 и два спуска в углах двора
# Паркинг −1 по нормам (СП 113.13330; замечание владельца 2026-10-24 «должно быть место для движения автомобилей и для
# людей, несколько рядов, лестницы и столбы — не мешать движению»): места 2,5 × 5,3 (машина — предмет, 1:1), проезды
# 6,0 × 1,3 = 7,8 м между рядами, поперечные проезды у торцов той же ширины, колонны только по линиям «спина к спине»
# и через три места (шаг 8 м). Владелец 2026-10-25: «вход в паркинг очень близко к домам… всего два спуска, отнести
# в углы дворовой территории, чтобы не мешали людям ходить». Поэтому въезда с проспекта и лестниц у подъездов больше нет:
# машины заезжают во двор проездом между корпусами и идут хозяйственным проездом вдоль забора к двум рампам в северо-
# западном и северо-восточном углах двора; рампа 7,8 м, уклон 14,5 %, в продолжение торцевого проезда паркинга, под
# навесом, с тротуаром 1 м вдоль стены — пешеходам тоже по ней. Середина двора у подъездов — только для людей.
DRIVE = [-113.0, -108.2]                                        # проезд во двор (x) с проспекта между корпусами
surface("drive_e", "road", DRIVE[0], YARD_Z0 + 2.5, DRIVE[1], -F)
surface("drive_w", "walk", -121.7, -84.0, DRIVE[0], -F)
surface("yard_road", "road", -213.0, YARD_Z0 + 2.5, -42.0, YARD_Z0 + 9.5)
PIT = [-212.0, -88.0, -43.2, -33.0]                             # паркинг −1 под парковкой, двором и домами
RW = [PIT[0], PIT[0] + 7.8]                                     # западный спуск — в продолжение западного торцевого проезда
RE = [PIT[2] - 7.8, PIT[2]]                                     # восточный спуск
# верх у хозяйственного проезда; уклон 17 % — на глубину 7,3 м рампа длиннее двора, поэтому низ уходит внутрь паркинга
# по торцевому проезду (под плитой двора над рампой — 4,1…6 м)
RAMP_SLOPE = 0.17
RAMP_TOP = YARD_Z0 + 9.5
RAMP_BOT = RAMP_TOP + (-PIT_Y) / RAMP_SLOPE


def ramp_y(z: float) -> float:
    """Высота полотна рампы над уровнем двора в точке z."""
    return -min(max(z - RAMP_TOP, 0.0), RAMP_BOT - RAMP_TOP) * RAMP_SLOPE
for (x0, x1, side) in [(RW[0], RW[1], -1.0), (RE[0], RE[1], 1.0)]:
    plan["ramps"].append({"x0": x0, "x1": x1, "z0": RAMP_TOP, "z1": RAMP_BOT, "y0": 0.0, "y1": PIT_Y, "mat": "concrete",
                          "fill": True})
    walk_x = (x0, x0 + 1.0) if side < 0 else (x1 - 1.0, x1)      # тротуар вдоль наружной стены, на 15 см выше
    plan["ramps"].append({"x0": walk_x[0], "x1": walk_x[1], "z0": RAMP_TOP, "z1": RAMP_BOT, "y0": 0.15, "y1": PIT_Y + 0.15, "mat": "walk"})
    # внутри паркинга у внутренней кромки рампы — стальной отбойник на метр выше полотна
    edge = x1 if side < 0 else x0
    plan["ramps"].append({"x0": edge - 0.12, "x1": edge + 0.12, "z0": PIT[1], "z1": RAMP_BOT, "y0": ramp_y(PIT[1]) + 1.0,
                          "y1": PIT_Y + 1.0, "mat": "steel"})
    plan["ground_holes"].append([x0 - 0.3, RAMP_TOP, x1 + 0.3, PIT[1] - 0.4])
    for wx in (x0 - 0.3, x1):
        wall(wx, RAMP_TOP, wx + 0.3, PIT[1] - 0.4, PIT_Y - 0.4, 1.1, "concrete")
    # навес на стойках над всей рампой, портал с ограничителем высоты наверху, шлагбаум, знаки, свет
    box((x0 + x1) * 0.5, 3.4, (RAMP_TOP + PIT[1]) * 0.5 + 1.0, x1 - x0 + 1.4, 0.25, PIT[1] - RAMP_TOP - 2.0, "slab", 0.0, False)
    for pz in (RAMP_TOP + 1.5, (RAMP_TOP + PIT[1]) * 0.5, PIT[1] - 1.5):
        for px in (x0 - 0.5, x1 + 0.5):
            box(px, 1.7, pz, 0.3, 3.4, 0.3, "steel")
    box((x0 + x1) * 0.5, 3.0, RAMP_TOP + 0.3, x1 - x0, 0.35, 0.06, "stripe", 0.0, False)
    u("U07_02_barrier_arm", x1 - 0.4 if side < 0 else x0 + 0.4, RAMP_TOP - 0.6, 90.0 if side < 0 else -90.0)
    u("U03_03_parking_sign", x1 + 1.2 if side < 0 else x0 - 1.2, RAMP_TOP - 1.0, 180.0)
    put("speed_bump", (x0 + x1) * 0.5, RAMP_TOP - 1.4, 90.0)
    sign("паркинг −1 · въезд / выезд", (x0 + x1) * 0.5, 4.6, RAMP_TOP - 0.2, 40)
    for zz in (RAMP_TOP + 6.0, PIT[1] - 6.0):                    # под навесом во дворе
        plan["lamps"].append([(x0 + x1) * 0.5, 2.6, zz, 0.45, 8.0])
    for zz in (PIT[1] + 6.0, RAMP_BOT - 2.0):                   # внутри — под балками
        plan["lamps"].append([(x0 + x1) * 0.5, -0.4 - PIT_BEAM - 0.1, zz, 0.6, 12.0])
put("booth", RW[1] + 3.9, PIT[1] + 1.6, 0.0, 1.0, PIT_Y, -1, 0.0, True)  # пост охраны у низа западной рампы — в углу
loot(RW[1] + 3.9, PIT_Y, PIT[1] + 3.4, "cabinet", "common", "будка охраны паркинга")  # торцевого проезда у северной стены
# ряды: места 5,3 в глубину, проезды 7,8; с севера на юг — A | проезд 1 | B C | проезд 2 | D E | проезд 3 | F
STALL_D, AISLE = 5.3, 7.8
ROWS = []                                                       # (имя, z0, z1, курс машины носом к «спине» ряда)
z = PIT[1]
ROWS.append(("A", z, z + STALL_D, 180.0)); z += STALL_D
AISLES = [(z, z + AISLE)]; z += AISLE
ROWS.append(("B", z, z + STALL_D, 0.0)); z += STALL_D
COL_Z = [z]
ROWS.append(("C", z, z + STALL_D, 180.0)); z += STALL_D
AISLES.append((z, z + AISLE)); z += AISLE
ROWS.append(("D", z, z + STALL_D, 0.0)); z += STALL_D
COL_Z.append(z)
ROWS.append(("E", z, z + STALL_D, 180.0)); z += STALL_D
AISLES.append((z, z + AISLE)); z += AISLE
ROWS.append(("F", z, PIT[3], 0.0))
# у стен — полосы рамп (рампа уходит внутрь паркинга до RAMP_BOT), рядом с ними — сквозные торцевые проезды:
# все поперечные проезды соединены и у западной, и у восточной стены (иначе проезд 1 упирался в отбойники рамп)
X_ROW0, X_ROW1 = PIT[0] + AISLE * 2.0, PIT[2] - AISLE * 2.0     # места между торцевыми проездами
BAY = 8.0                                                       # колонна 0,5 + три места по 2,5
TUNNEL_Z = (-44.0, -42.0)                                       # подкоп из хранилища банка — в восточную стену у проезда 3
for srf in plan["surfaces"]:
    if srf["id"] == "yard_n":
        srf["holes"] = [[RW[0] - 0.3, RAMP_TOP, RW[1] + 0.3, PIT[1] - 0.4], [RE[0] - 0.3, RAMP_TOP, RE[1] + 0.3, PIT[1] - 0.4]]
slab("lot_slab", [PIT[0] - 0.4, PIT[1] - 0.4, PIT[2] + 0.4, PIT[3] + 0.4], 0.0, 0.4, "walk")
plan["ground_holes"].append([PIT[0] - 0.4, PIT[1] - 0.4, PIT[2] + 0.4, PIT[3] + 0.4])
slab("pit_floor", [PIT[0] - 0.4, PIT[1] - 0.4, PIT[2] + 0.4, PIT[3] + 0.4], PIT_Y, 0.4, "pit_floor")       # бетон с пропилами (StreetPaving)
wall(PIT[0] - 0.4, PIT[1] - 0.4, PIT[0], PIT[3] + 0.4, PIT_Y, -0.4, "concrete")
wall(PIT[2], PIT[1] - 0.4, PIT[2] + 0.4, TUNNEL_Z[0], PIT_Y, -0.4, "concrete")
wall(PIT[2], TUNNEL_Z[1], PIT[2] + 0.4, PIT[3] + 0.4, PIT_Y, -0.4, "concrete")
wall(PIT[2], TUNNEL_Z[0], PIT[2] + 0.4, TUNNEL_Z[1], -1.0, -0.4, "concrete")
wall(PIT[2], TUNNEL_Z[0], PIT[2] + 0.4, TUNNEL_Z[1], PIT_Y, -3.2, "concrete")      # под проломом подкопа (−3,2…−1)
wall(RW[1], PIT[1] - 0.4, RE[0], PIT[1], PIT_Y, -0.4, "concrete")             # северная стена — проёмы рамп в торцах
wall(PIT[0], PIT[3], PIT[2], PIT[3] + 0.4, PIT_Y, -0.4, "concrete")
# колонны — по линиям «спина к спине» через три места; в проездах колонн нет
for cz in COL_Z:
    plan["columns"].append({"rect": [X_ROW0, cz, X_ROW1, cz], "y0": PIT_Y, "y1": -0.4, "grid": BAY, "size": 0.9, "mat": "concrete"})
# отделка как в Таркове (владелец 2026-10-29, зал D стенда): капители под балками, полосы от бамперов на низе колонн,
# балки 0,6 × 0,9 поперёк на каждой колонне и вдоль по линиям колонн, воздуховоды у кромок проездов, трубы над рядами,
# потолок — бетон (изнанка плиты двора раньше рисовалась плиткой двора)
BEAM_Y = -0.4 - PIT_BEAM * 0.5
COL_X = [X_ROW0 + k * BAY for k in range(int((X_ROW1 - X_ROW0) / BAY) + 1)]
slab("pit_ceiling", [PIT[0], PIT[1], PIT[2], PIT[3]], -0.4, 0.04, "concrete")
for cx in COL_X:
    box(cx, BEAM_Y, (PIT[1] + PIT[3]) * 0.5, 0.6, PIT_BEAM, PIT[3] - PIT[1], "concrete", 0.0, False)
    for cz in COL_Z:
        box(cx, -0.4 - PIT_BEAM - 0.2, cz, 2.2, 0.4, 2.2, "concrete", 0.0, False)
        for k in range(6):
            box(cx, PIT_Y + 0.1 + k * 0.2, cz, 0.94, 0.2, 0.94, "hazard_yellow" if k % 2 == 0 else "dark", 0.0, False)
for cz in COL_Z:
    box((X_ROW0 + X_ROW1) * 0.5, BEAM_Y, cz, X_ROW1 - X_ROW0, PIT_BEAM, 0.6, "concrete", 0.0, False)
for (a0, a1) in AISLES:
    box((X_ROW0 + X_ROW1) * 0.5, -0.4 - PIT_BEAM - 0.3, a1 - 0.9, X_ROW1 - X_ROW0, 0.5, 1.2, "wall", 0.0, False)
for (row, z0, z1, _yaw) in ROWS:
    box((X_ROW0 + X_ROW1) * 0.5, -0.4 - PIT_BEAM - 0.12, (z0 + z1) * 0.5, X_ROW1 - X_ROW0, 0.14, 0.14, "pipe_red", 0.0, False)
# кабельные лотки вдоль продольных стен под балками (как в зале D стенда)
for tz in (PIT[1] + 0.65, PIT[3] - 0.65):
    box((PIT[0] + PIT[2]) * 0.5, -0.4 - PIT_BEAM - 0.25, tz, PIT[2] - PIT[0] - 1.0, 0.08, 0.45, "tray", 0.0, False)


def stall_free(x: float, row: str) -> bool:
    """Место не занято техпомещением в торцах ряда A."""
    return not (row == "A" and (x < X_ROW0 + 12.0 or x > X_ROW1 - 12.0))


# разметка мест, машины (половина мест), открытые багажники — места лута
for (row, z0, z1, yaw) in ROWS:
    zc = (z0 + z1) * 0.5
    k = 0
    xk = X_ROW0
    while xk + BAY <= X_ROW1 + 0.01:
        for j in range(3):
            x = xk + 0.25 + 1.25 + j * 2.5
            if not stall_free(x, row):
                continue
            box(x - 1.25, PIT_Y + 0.01, zc, 0.1, 0.02, z1 - z0 - 0.4, "stripe", 0.0, False)
            # владелец 2026-10-25: «побитые машины, стоят неровно, много стекла, открытые двери и багажники»
            if rng.random() < 0.62:
                pick = rng.random()
                xj, zj = x + rng.uniform(-0.35, 0.35), zc + rng.uniform(-0.45, 0.45)
                yj = yaw + rng.uniform(-11.0, 11.0)
                aisle = -2.9 if yaw == 0.0 else 2.9                    # сторона проезда — за кормой
                kit, tint = "car", rng.choice(CAR_TINTS)
                if pick < 0.12:
                    kit = "suv_open"
                elif pick < 0.34:
                    kit = "car_open"
                elif pick < 0.52:
                    kit = "car_wreck"
                elif pick < 0.6:
                    tint = 1                                          # сгоревшая
                put(kit, xj, zj, yj, 1.0, PIT_Y, tint, 0.0, True)
                if kit in ("suv_open", "car_open"):
                    loot(xj, PIT_Y, zj + aisle, "car", "common", "открытые двери и багажник")
                if kit != "car" or rng.random() < 0.3:
                    put("glass_shards", xj + rng.uniform(-1.0, 1.0), zj + aisle * rng.uniform(0.7, 1.1), rng.uniform(0, 360), rng.uniform(0.8, 1.4), PIT_Y)
        xk += BAY
        k += 1
# проезды: свет по оси, пешеходные дорожки вдоль торцевых проездов (продолжают тротуары рамп)
for (a0, a1) in AISLES:
    for x in range(int(X_ROW0) + 8, int(X_ROW1), 16):
        plan["lamps"].append([x, -0.4 - PIT_BEAM - 0.1, (a0 + a1) * 0.5, 0.6, 12.0])
    box((X_ROW0 + X_ROW1) * 0.5, PIT_Y + 0.01, (a0 + a1) * 0.5, X_ROW1 - X_ROW0, 0.02, 0.12, "stripe", 0.0, False)
for x in (PIT[0] + 0.5, PIT[2] - 0.5):
    box(x, PIT_Y + 0.01, (PIT[1] + PIT[3]) * 0.5, 1.0, 0.02, PIT[3] - PIT[1] - 1.0, "marker", 0.0, False)
    for z in range(int(PIT[1]) + 6, int(PIT[3]), 14):
        plan["lamps"].append([x + (3.5 if x < -100 else -3.5), -0.4 - PIT_BEAM - 0.1, z, 0.6, 12.0])
for x in (X_ROW0 - AISLE * 0.5, X_ROW1 + AISLE * 0.5):             # торцевые проезды
    box(x, PIT_Y + 0.01, (PIT[1] + PIT[3]) * 0.5, 0.12, 0.02, PIT[3] - PIT[1] - 6.0, "stripe", 0.0, False)
    for z in range(int(PIT[1]) + 13, int(PIT[3]), 14):
        plan["lamps"].append([x, -0.4 - PIT_BEAM - 0.1, z, 0.6, 12.0])
for (row, z0, z1, _yaw) in ROWS:
    sign("ряд " + row, PIT[0] + 4.0, PIT_Y + 4.0, (z0 + z1) * 0.5, 30)
    sign("ряд " + row, PIT[2] - 4.0, PIT_Y + 4.0, (z0 + z1) * 0.5, 30)
for x in ((RW[0] + RW[1]) * 0.5, (RE[0] + RE[1]) * 0.5):
    sign("выезд ↑", x, PIT_Y + 4.0, RAMP_BOT + 2.0, 34)
    box(x, PIT_Y + 4.0, RAMP_BOT + 2.15, 1.6, 0.4, 0.12, "exit_sign", 0.0, False)          # зелёный указатель выезда
# техпомещения в торцах ряда A: насосная и электрощитовая (закрыты)
for (x0, x1, title) in [(X_ROW0, X_ROW0 + 12.0, "насосная"), (X_ROW1 - 12.0, X_ROW1, "электрощитовая")]:
    wall(x0, ROWS[0][2] - 0.2, x1, ROWS[0][2], PIT_Y, -0.4, "wall")
    wall(x0, PIT[1], x0 + 0.2, ROWS[0][2], PIT_Y, -0.4, "wall")
    wall(x1 - 0.2, PIT[1], x1, ROWS[0][2], PIT_Y, -0.4, "wall")
    sign("паркинг −1 · " + title, (x0 + x1) * 0.5, PIT_Y + 3.6, ROWS[0][2] + 1.0, 30)
# брошенные посреди проездов машины, мусор и стекло по проездам, кучи мусора у стен
for (kit, x, z, yaw) in [("car_wreck", -172.0, (AISLES[0][0] + AISLES[0][1]) * 0.5, 62.0), ("car_open", -142.0, (AISLES[1][0] + AISLES[1][1]) * 0.5, 112.0),
                         ("car", -90.0, (AISLES[0][0] + AISLES[0][1]) * 0.5, 31.0), ("car_wreck", -180.0, (AISLES[2][0] + AISLES[2][1]) * 0.5, 148.0),
                         ("car_open", -100.0, (AISLES[1][0] + AISLES[1][1]) * 0.5 + 1.0, 75.0)]:
    put(kit, x, z, yaw, 1.0, PIT_Y, 1 if kit == "car" else rng.choice(CAR_TINTS), 0.0, True)
    put("glass_shards", x + 1.5, z + 1.0, rng.uniform(0, 360), 1.3, PIT_Y)
for (a0, a1) in AISLES:
    for _ in range(26):
        x = rng.uniform(X_ROW0 + 2.0, X_ROW1 - 2.0)
        z = rng.uniform(a0 + 0.5, a1 - 0.5)
        put(rng.choice(["paper", "paper", "paper_ball", "bottle", "can", "bags", "glass_shards"]), x, z, rng.uniform(0, 360),
            rng.uniform(0.7, 1.2), PIT_Y)
for (x, z) in [(PIT[0] + 2.0, -70.0), (PIT[0] + 2.0, -46.0), (-150.0, PIT[1] + 1.5), (-90.0, PIT[3] - 1.2), (-130.0, PIT[1] + 1.5)]:
    put("trash_pile", x, z, rng.uniform(0, 360), 1.0, PIT_Y)
    put("bags", x + 1.0, z + 0.6, rng.uniform(0, 360), 1.0, PIT_Y)
for (x, z) in [(-160.0, -61.0), (-118.0, -78.0), (-76.0, -60.0), (-150.0, -42.0)]:
    put("puddle", x, z, rng.uniform(0, 360), 2.2, PIT_Y)
for (x, z, kind, tier, note) in [(X_ROW0 + 3.0, AISLES[1][0] + 2.0, "body", "good", "тело ЧВК в проезде 2"),
                                 (-150.0, AISLES[0][1] - 1.0, "crate", "common", "ящики жильцов"),
                                 (X_ROW1 - 4.0, AISLES[2][0] + 2.0, "loose", "common", "инструмент у подкопа")]:
    loot(x, PIT_Y, z, kind, tier, note)

# ------------------------------------------------------------------ банк «Капитал»: три этажа, хранилище на −1
# Владелец 2026-10-24: «банк слишком плюгавый — отдельное трёхэтажное здание с логичным наполнением, хранилище на −1,
# соединить с подземным паркингом ходом (кто-то делал подкоп), обнести металлическим забором; архитектура — как у
# кинотеатра «Родина» (Streets of Tarkov)»: первый этаж утоплен за опорами, второй и третий нависают коробом с ромбической
# решёткой, наружная лестница на второй этаж. Внутри: операционный зал со стойкой, касса, охрана, кабинет управляющего;
# 2-й — офис, архив, переговорная, бухгалтерия; 3-й — кабинет директора, серверная, зал; крыша с будкой выхода;
# −1 — коридоры, пост охраны, хранилище с круглой дверью, депозитарий, пересчёт; подкоп из хранилища в паркинг −1.
BX0, BX1, BZ0, BZ1 = -38.0, -4.0, -62.0, -34.0                  # первый этаж и −1
UX0, UX1, UZ0, UZ1 = -40.0, -2.0, -64.0, -30.0                  # нависающие 2-й и 3-й
BY = [0.0, 4.5, 8.4, 12.3]                                      # полы этажей и крыша
BASE_Y = -3.2                                                   # пол −1 банка: прежний; паркинг стал глубже (6 м в свету),
                                                                # подкоп выходит в его стену на 4,1 м выше пола — к пролому насыпь
BFX0, BFX1, BFZ0, BFZ1 = -43.0, 6.0, -68.0, -21.0               # забор
building_rect_bank = [UX0, UZ0, UX1, UZ1]
plan["ground_holes"].append([BX0 - 0.4, BZ0 - 0.4, BX1 + 0.4, BZ1 + 0.4])
surface("bank_yard", "walk", BFX0, BFZ0, BFX1, BFZ1, 0.0, 0.06)
plan["surfaces"][-1]["holes"] = [[BX0, BZ0, BX1, BZ1]]                  # пол банка — свои плиты (над −1)
# марши: главный (запад, ядро x −38…−28) — 1→2 по z −59, 2→3 по z −61, 3→крыша по z −59; служебный на −1 (восток)
RUN = (-37.2, -29.2)
stair((RUN[1], BY[0], -59.0), (RUN[0], BY[1], -59.0), 1.6)
stair((RUN[0], BY[1], -61.0), (RUN[1], BY[2], -61.0), 1.6)
stair((RUN[1], BY[2], -59.0), (RUN[0], BY[3], -59.0), 1.6)
stair((-6.8, BY[0], -60.0), (-14.8, BASE_Y, -60.0), 1.6)
H1 = [RUN[0] - 0.2, -59.85, RUN[1], -58.15]
H2 = [RUN[0], -61.85, RUN[1] + 0.2, -60.15]
slab("bank_f1", [BX0, BZ0, BX1, BZ1], BY[0], 0.4, "walk", [[-14.8, -61.2, -6.6, -58.8]])
slab("bank_f2", [UX0, UZ0, UX1, UZ1], BY[1], 0.3, "slab", [H1])
slab("bank_f3", [UX0, UZ0, UX1, UZ1], BY[2], 0.3, "slab", [H2])
slab("bank_roof", [UX0, UZ0, UX1, UZ1], BY[3], 0.35, "slab", [H1])
slab("bank_base", [BX0 - 0.4, BZ0 - 0.4, BX1 + 0.4, BZ1 + 0.4], BASE_Y, 0.4, "concrete")
# ---- первый этаж: витражи к проспекту, главный вход, служебные двери; опоры под нависанием
H = BY[1] - BY[0] - 0.3
wall_x(BZ1, BX0, BX1, 0.0, H, [(-21.0, 2.4, 2.6)] + windows(BX0, BX1, 3.0, 2.4, 0.4, 3.6, [(-21.0, 2.4)]))
wall_x(BZ0, BX0, BX1, 0.0, H, [(-20.0, 1.2, 2.42)])
wall_z(BX0, BZ0, BZ1, 0.0, H, windows(BZ0, BZ1, 4.0, 1.6, 2.2, 3.6))
wall_z(BX1, BZ0, BZ1, 0.0, H, [(-40.0, 1.2, 2.42)] + windows(BZ0, BZ1, 4.0, 1.6, 2.2, 3.6, [(-40.0, 1.2)]))
for x in (UX0 + 0.6, -31.0, -21.0, -11.0, UX1 - 0.6):
    box(x, H * 0.5, UZ1 - 0.6, 0.7, H, 0.7, "concrete")
for z in (-38.0, -46.0, -54.0, -60.0):
    for x in (UX0 + 0.6, UX1 - 0.6):
        box(x, H * 0.5, z, 0.7, H, 0.7, "concrete")
# ядро лестницы, охрана, касса, кабинет управляющего, лестница на −1
wall_x(-57.8, BX0, -28.0, 0.0, H, [(-28.7, 1.17, 2.42)], 0.2)
wall_z(-28.0, BZ0, -57.8, 0.0, BY[3] - 0.3, (), 0.25)
wall_x(-57.8, -28.0, -16.0, 0.0, H, [(-22.0, 1.17, 2.42)], 0.15)
wall_z(-16.0, BZ0, -57.8, 0.0, H, (), 0.15)
wall_x(-58.6, -16.0, BX1, 0.0, H, [(-5.4, 1.17, 2.42)], 0.2)
wall_x(-52.0, -24.0, -16.0, 0.0, H, [(-20.0, 1.0, 2.2)], 0.12)                 # касса за стеклом
wall_z(-24.0, -57.8, -52.0, 0.0, H, (), 0.12)
wall_z(-16.0, -57.8, -52.0, 0.0, H, (), 0.12)
wall_x(-50.0, -10.0, BX1, 0.0, H, [(-7.0, 1.17, 2.42)], 0.12)                  # кабинет управляющего
wall_z(-10.0, -50.0, -40.0, 0.0, H, [(-45.0, 1.17, 2.42)], 0.12)
wall_x(-40.0, -10.0, BX1, 0.0, H, (), 0.12)
# стойка операционистов с калиткой, рабочие места за ней, зал ожидания, банкоматы, турникеты
for (x0, x1) in [(-36.0, -15.5), (-13.8, -10.2)]:
    box((x0 + x1) * 0.5, 0.55, -48.0, x1 - x0, 1.1, 0.8, "accent")
for x in (-33.0, -23.0, -18.0):
    box(x, 1.25, -47.7, 1.6, 0.5, 0.04, "dark", 0.0, False)                    # стёкла окон кассиров
    box(x, 0.38, -50.5, 1.4, 0.75, 0.8, "accent")
    loot(x, 0.0, -49.4, "register", "good", "окно операциониста")
for x in (-34.0, -30.0, -26.0):
    box(x, 0.23, -41.5, 2.6, 0.45, 0.6, "accent")
for x in (-37.2, -36.0):
    box(x, 0.75, -36.0 if x < -36.5 else -38.0, 0.7, 1.5, 0.7, "steel")         # банкоматы у входа
loot(-37.0, 0.0, -37.0, "safe", "good", "кассета банкомата")
for k in range(5):
    put("bollard", -27.0 + k * 1.6, -44.0, 0.0)
box(-20.0, 0.38, -55.0, 1.6, 0.75, 0.8, "accent")
loot(-18.5, 0.0, -55.5, "safe", "good", "сейф кассы")
box(-22.0, 0.38, -60.5, 3.0, 0.75, 0.8, "accent")
box(-22.0, 1.1, -61.6, 3.0, 0.7, 0.1, "dark", 0.0, False)                      # мониторы охраны
loot(-25.5, 0.0, -60.0, "weapon", "weapon", "оружейный шкаф охраны")
box(-7.0, 0.38, -45.0, 1.8, 0.75, 0.9, "accent")
loot(-5.0, 0.0, -48.5, "safe", "good", "сейф управляющего")
loot(-30.0, 0.0, -42.5, "loose", "common", "зал ожидания")
loot(-12.0, 0.0, -36.0, "body", "good", "тело мародёра у входа")
plan["lamps"] += [[-30.0, 4.0, -44.0, 0.6, 10.0], [-14.0, 4.0, -44.0, 0.6, 10.0], [-22.0, 4.0, -56.0, 0.5, 8.0]]
# ---- 2-й этаж: офис, архив, переговорная, бухгалтерия; дверь на наружную лестницу с запада
for (y0, side_door) in [(BY[1], True), (BY[2], False)]:
    h = BY[1] - BY[0] - 0.3 if y0 == BY[1] else BY[3] - BY[2] - 0.35
    wall_x(UZ1, UX0, UX1, y0, h, windows(UX0, UX1, 3.0, 2.2, 0.9, 2.7))
    wall_x(UZ0, UX0, UX1, y0, h, windows(UX0, UX1, 3.0, 2.2, 0.9, 2.7))
    wall_z(UX0, UZ0, UZ1, y0, h, ([(-44.0, 1.17, 2.42)] if side_door else []) + windows(UZ0, UZ1, 3.0, 2.0, 0.9, 2.7, [(-44.0, 1.17)]))
    wall_z(UX1, UZ0, UZ1, y0, h, windows(UZ0, UZ1, 3.0, 2.0, 0.9, 2.7))
    wall_x(-57.8, UX0, -28.0, y0, h, [(-38.6 if y0 == BY[1] else -28.7, 1.17, 2.42)], 0.2)
    wall_x(-52.0, -28.0, UX1, y0, h, [(-22.0, 1.17, 2.42), (-9.0, 1.17, 2.42)], 0.15)
    wall_x(-44.0, UX0, UX1, y0, h, [(-30.0, 1.6, 2.42), (-8.0, 1.17, 2.42)], 0.15)
    wall_z(-16.0, UZ0, -52.0, y0, h, (), 0.15)
    wall_z(-14.0, -44.0, UZ1, y0, h, (), 0.15)
    plan["lamps"] += [[-30.0, y0 + h - 0.4, -48.0, 0.5, 9.0], [-10.0, y0 + h - 0.4, -48.0, 0.5, 9.0], [-22.0, y0 + h - 0.4, -37.0, 0.5, 9.0]]
y0 = BY[1]
for x in range(-37, -16, 4):                                                   # открытый офис
    for z in (-41.0, -36.0, -32.5):
        box(x, y0 + 0.38, z, 1.6, 0.75, 0.8, "accent")
loot(-25.0, y0, -36.0, "loose", "common", "офис 2-го этажа")
for x in (-26.5, -21.5, -18.0):                                                # архив
    box(x, y0 + 1.1, -58.0, 0.6, 2.2, 8.0, "steel")
loot(-24.0, y0, -55.0, "cabinet", "common", "архив")
box(-9.0, y0 + 0.38, -58.0, 6.0, 0.75, 2.0, "accent")                         # переговорная
box(-8.0, y0 + 0.38, -37.0, 3.0, 0.75, 1.0, "accent")                          # бухгалтерия
loot(-6.0, y0, -34.0, "safe", "good", "сейф бухгалтерии")
# ---- 3-й этаж: директор, серверная, зал
y0 = BY[2]
box(-9.0, y0 + 0.38, -58.0, 2.4, 0.75, 1.1, "accent")
loot(-4.0, y0, -61.0, "safe", "good", "сейф директора (ключ)")
for z in (-62.0, -59.0, -56.0):
    box(-22.0, y0 + 1.0, z, 8.0, 2.0, 0.8, "dark")                            # стойки серверной
loot(-26.0, y0, -54.0, "crate", "good", "серверная: жёсткие диски")
box(-22.0, y0 + 0.38, -37.0, 8.0, 0.75, 2.4, "accent")
loot(-34.0, y0, -34.0, "backpack", "med", "зал 3-го этажа")
# ---- крыша: будка выхода, парапет, кондиционеры, антенна, лёжка снайпера к проспекту
yr = BY[3]
for (x0, z0, x1, z1) in [(UX0, UZ0, UX1, UZ0 + 0.25), (UX0, UZ1 - 0.25, UX1, UZ1), (UX0, UZ0, UX0 + 0.25, UZ1), (UX1 - 0.25, UZ0, UX1, UZ1)]:
    wall(x0, z0, x1, z1, yr, yr + 1.0, "concrete")
wall_x(-57.8, -38.2, -28.0, yr, 2.6, [(-36.4, 1.2, 2.3)], 0.2)
wall_x(UZ0 + 0.25, -38.2, -28.0, yr, 2.6, (), 0.2)
wall_z(-38.2, UZ0 + 0.25, -57.8, yr, 2.6, (), 0.2)
wall_z(-28.0, UZ0 + 0.25, -57.8, yr, 2.6, (), 0.2)
slab("bank_booth", [-38.4, UZ0, -27.8, -57.6], yr + 2.8, 0.2)
for x in (-22.0, -16.0, -10.0):
    put("ac_unit", x, -60.0, 0.0, 1.6, yr + 0.45)
box(-6.0, yr + 4.0, -58.0, 0.15, 8.0, 0.15, "steel")
put("sandbags", -20.0, -31.5, 90.0, 1.0, yr, -1, 0.0, True)
loot(-22.0, yr, -33.0, "weapon", "weapon", "лёжка на крыше банка")
loot(-12.0, yr, -50.0, "crate", "good", "тайник у кондиционеров")
# ---- решётка фасада: ромбы раскосами на 2-м и 3-м этажах (лицо и торцы)
def lattice(axis: str, c: float, a0: float, a1: float, y0: float, y1: float, step: float) -> None:
    a = a0
    while a < a1 - 0.1:
        b = min(a + step, a1)
        for (u0, v0, u1, v1) in [(a, y0, b, y1), (b, y0, a, y1)]:
            if axis == "x":
                beam((u0, v0, c), (u1, v1, c), 0.22, 0.3)
            else:
                beam((c, v0, u0), (c, v1, u1), 0.22, 0.3)
        a = b
lattice("x", UZ1 + 0.25, UX0, UX1, BY[1], BY[3] + 1.0, 3.8)
lattice("z", UX0 - 0.25, UZ0, UZ1, BY[1], BY[3] + 1.0, 3.4)
lattice("z", UX1 + 0.25, UZ0, UZ1, BY[1], BY[3] + 1.0, 3.4)
box((UX0 + UX1) * 0.5, BY[1] - 0.25, UZ1 + 0.25, UX1 - UX0 + 0.6, 0.5, 0.5, "concrete")
box((UX0 + UX1) * 0.5, BY[3] + 1.0, UZ1 + 0.25, UX1 - UX0 + 0.6, 0.3, 0.5, "concrete", 0.0, False)
sign("банк «Капитал»", -21.0, BY[3] + 2.4, UZ1 + 0.6, 64)
# наружная лестница на 2-й этаж с запада и площадка у двери
stair((-41.6, 0.0, -31.5), (-41.6, BY[1], -40.5), 1.6, "concrete")
box(-41.4, BY[1] - 0.12, -43.2, 2.6, 0.24, 5.6, "concrete")
wall(-42.75, -46.0, -42.6, -31.5, 0.0, 1.0, "steel")
wall(-42.75, -46.0, -40.0, -45.85, BY[1], BY[1] + 1.0, "steel")
# ---- −1: коридоры, охрана, хранилище, депозитарий, пересчёт; подкоп в паркинг
y0, hb = BASE_Y, -BASE_Y - 0.4
wall(BX0 - 0.4, BZ0 - 0.4, BX0, -44.0, y0, -0.4, "concrete")
wall(BX0 - 0.4, -42.0, BX0, BZ1 + 0.4, y0, -0.4, "concrete")
wall(BX0 - 0.4, -44.0, BX0, -42.0, -1.0, -0.4, "concrete")
wall(BX1, BZ0 - 0.4, BX1 + 0.4, BZ1 + 0.4, y0, -0.4, "concrete")
wall(BX0, BZ0 - 0.4, BX1, BZ0, y0, -0.4, "concrete")
wall(BX0, BZ1, BX1, BZ1 + 0.4, y0, -0.4, "concrete")
wall_x(-58.6, -16.0, BX1, y0, hb, (), 0.2)                                   # лестничная клетка
wall_z(-16.0, -62.0, -58.6, y0, hb, [(-60.3, 1.17, 2.42)], 0.2)
wall_x(-58.0, BX0, -24.0, y0, hb, (), 0.2)                                    # коридор вдоль z −60
wall_x(-58.0, -21.0, -16.0, y0, hb, (), 0.2)
wall_z(-24.0, -58.0, BZ1, y0, hb, [(-46.0, 2.6, 2.6)], 0.8)                   # толстая стена хранилища
wall_x(-36.0, BX0, -24.0, y0, hb, (), 0.8)
wall_z(-21.0, -58.0, BZ1, y0, hb, [(-52.0, 1.17, 2.42), (-38.0, 1.17, 2.42)], 0.2)
wall_x(-48.0, -21.0, BX1, y0, hb, (), 0.2)
wall_z(-12.0, -48.0, BZ1, y0, hb, [(-42.0, 1.17, 2.42)], 0.15)
put("vault_door", -25.5, -43.0, 90.0, 1.0, y0, -1, 0.0, True)                 # круглая дверь распахнута внутрь
for (x, z, yaw) in [(-31.0, -56.6, 0.0), (-37.0, -50.0, 90.0), (-37.0, -40.0, 90.0), (-31.0, -37.0, 180.0)]:
    put("deposit_wall", x, z, yaw, 1.0, y0, -1, 0.0, True)
for (x, z) in [(-33.0, -46.0), (-28.0, -50.0), (-28.0, -41.0)]:
    box(x, y0 + 0.6, z, 1.2, 1.2, 1.0, "steel")
    loot(x, y0, z + 0.9, "safe", "good", "хранилище: кассеты и слитки")
for (x, z, yaw) in [(-16.5, -47.4, 0.0), (-20.4, -43.0, 90.0), (-16.5, -36.6, 180.0)]:
    put("deposit_wall", x, z, yaw, 1.0, y0, -1, 0.0, True)
loot(-17.0, y0, -42.0, "cells", "good", "депозитарные ячейки")
box(-8.0, y0 + 0.38, -42.0, 4.0, 0.75, 1.4, "accent")                         # пересчёт
loot(-8.0, y0, -44.0, "loose", "good", "пересчёт: пачки денег")
box(-19.0, y0 + 0.38, -54.0, 2.0, 0.75, 0.8, "accent")                        # пост охраны −1
loot(-19.0, y0, -55.4, "weapon", "weapon", "пост охраны хранилища")
loot(-30.0, y0, -61.0, "body", "good", "тело копателя в коридоре")
plan["lamps"] += [[-30.0, -0.9, -46.0, 0.5, 8.0], [-23.0, -0.9, -50.0, 0.4, 7.0], [-12.0, -0.9, -42.0, 0.4, 7.0], [-26.0, -0.9, -60.0, 0.4, 7.0]]
# подкоп: от пролома в западной стене хранилища до стены паркинга −1 — грунт, крепь из досок, гирлянда
wall(PIT[2] + 0.4, TUNNEL_Z[0] - 0.3, BX0 - 0.4, TUNNEL_Z[0], BASE_Y, -0.6, "mud")
wall(PIT[2] + 0.4, TUNNEL_Z[1], BX0 - 0.4, TUNNEL_Z[1] + 0.3, BASE_Y, -0.6, "mud")
slab("dig_floor", [PIT[2] + 0.4, TUNNEL_Z[0] - 0.3, BX0 - 0.4, TUNNEL_Z[1] + 0.3], BASE_Y, 0.3, "mud")
slab("dig_roof", [PIT[2] + 0.4, TUNNEL_Z[0] - 0.3, BX0 - 0.4, TUNNEL_Z[1] + 0.3], -0.6, 0.3, "mud")
x = PIT[2] + 1.5
while x < BX0 - 1.0:
    for z in (TUNNEL_Z[0] + 0.1, TUNNEL_Z[1] - 0.1):
        box(x, BASE_Y + 1.1, z, 0.15, 2.2, 0.15, "wood", 0.0, False)
    box(x, -0.97, (TUNNEL_Z[0] + TUNNEL_Z[1]) * 0.5, 0.15, 0.12, 2.0, "wood", 0.0, False)
    x += 2.2
for x in (PIT[2] + 6.0, PIT[2] + 14.0):
    plan["lamps"].append([x, -1.4, (TUNNEL_Z[0] + TUNNEL_Z[1]) * 0.5, 0.3, 5.0])
# насыпь вынутого грунта к пролому (паркинг глубже подкопа на 4,1 м): пандус по торцевому проезду вдоль восточной стены,
# 27 %, и площадка перед проломом — сплошные, под ними не ходят
DIG_X = (PIT[2] - 4.4, PIT[2])
DIG_LAND = (-45.0, -40.4)
plan["ramps"].append({"x0": DIG_X[0], "x1": DIG_X[1], "z0": DIG_LAND[0] - 15.0, "z1": DIG_LAND[0], "y0": PIT_Y, "y1": BASE_Y,
                      "mat": "mud", "fill": True})
box((DIG_X[0] + DIG_X[1]) * 0.5, (PIT_Y + BASE_Y) * 0.5, (DIG_LAND[0] + DIG_LAND[1]) * 0.5, DIG_X[1] - DIG_X[0],
    BASE_Y - PIT_Y, DIG_LAND[1] - DIG_LAND[0], "mud")
put("trash_pile", PIT[2] - 2.0, -38.5, 0.0, 0.8, PIT_Y)
for k in range(3):
    put("bags", PIT[2] - 1.5 + k * 0.4, -40.9 - k * 0.5, k * 40.0, 1.0, BASE_Y)
# у подкопа (владелец 2026-10-25): куча вынутого грунта, пыль, пара прожекторов на треногах с кабелем — у подножия насыпи
for (x, z, sc) in [(DIG_X[0] - 1.5, DIG_LAND[0] - 13.0, 1.3), (DIG_X[0] - 2.5, DIG_LAND[0] - 8.0, 1.0), (PIT[2] - 3.0, -37.6, 1.1)]:
    put("pile_dirt", x, z, rng.uniform(0, 360), sc, PIT_Y)
for (x, z, y) in [(PIT[2] - 2.5, -43.0, BASE_Y), (PIT[2] - 3.5, -41.5, BASE_Y), (DIG_X[0] - 1.0, DIG_LAND[0] - 15.5, PIT_Y),
                  (PIT[2] + 3.0, -43.0, BASE_Y)]:
    put("dust", x, z, rng.uniform(0, 360), 1.0, y)
for (x, z, yaw) in [(DIG_X[0] - 2.0, DIG_LAND[0] - 4.0, 60.0), (DIG_X[0] - 2.0, -39.0, 120.0)]:
    put("floodlight", x, z, yaw, 1.0, PIT_Y)
    plan["lamps"].append([x + 1.0, PIT_Y + 1.9, z, 1.6, 14.0])
sign("подкоп в банк", PIT[2] - 1.0, -1.2, -43.0, 30)
FI["stories"].append({"label": "подкоп из паркинга в хранилище банка", "at": [PIT[2] + 6.0, -43.0], "height": -1.6})
# ---- забор из прутьев: калитка к входу, ворота для инкассаторов, пролом у подкопа (сзади)
def fence_line(axis: str, c: float, a0: float, a1: float, gaps=()) -> None:
    a = a0 + 1.25
    while a < a1:
        if all(abs(a - g[0]) > g[1] * 0.5 + 1.2 for g in gaps):
            if axis == "x":
                put("bar_fence", a, c, 90.0, 1.0, 0.0, -1, 0.0, False)
            else:
                put("bar_fence", c, a, 0.0, 1.0, 0.0, -1, 0.0, False)
        a += 2.5
fence_line("x", BFZ1, BFX0, BFX1, [(-21.0, 3.0), (1.5, 5.0)])
fence_line("x", BFZ0, BFX0, BFX1, [(-30.0, 2.5)])
fence_line("z", BFX0, BFZ0, BFZ1)
fence_line("z", BFX1, BFZ0, BFZ1, [(-45.0, 4.0)])
for x in (-35.0, -32.0, -29.0):
    put("flagpole", x, -23.5, 0.0, 1.0, 0.0, -1, 0.0, True)
for x in (-14.0, -8.0):
    put("planter", x, -24.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("booth", 3.5, -24.0, 0.0, 1.0, 0.0, -1, 0.0, True)                      # пост охраны у ворот
put("barrier_arm", 4.6, -21.6, -90.0)
put("inkassator", -17.0, -6.6, 95.0, 1.0, 0.0, 5, 0.0, True)                 # броневик у бордюра, задние двери открыты
loot(-14.0, 0.0, -6.8, "car", "good", "инкассаторский броневик: мешки с деньгами")
loot(-12.6, 0.0, -9.0, "body", "weapon", "тело инкассатора")
FI["stories"].append({"label": "инкассаторы бросили броневик у банка: кейс с деньгами", "at": [-17.0, -6.6], "height": 3.4})
# автомойка за банком (перебивает обзор от «Вершины» на парковку) и контейнеры на её задах
building("CarWash", "автомойка «Блеск» (закрыта)", (12.0, -56.0), (10.0, 20.0), "mass", 1, 4.2, 0.0, 0.0, "", "", 0.0, "West")
put("container20", 12.0, -71.0, 90.0, 1.0, 0.0, -1, 0.0, True)
put("container20", 12.2, -71.0, 92.0, 1.0, 2.62, -1, 0.0, False)
sign("автомойка «Блеск»", 12.0, 5.0, -45.6, 40)

# ================================================================== западное плечо, юг: остановка с площадкой, дом 7, «Ярус»
# остановка и ларьки на тротуаре, за ними — площадка 18 м до дома (замечание владельца)
u("U03_01_lightbox", -186.0, F - 1.0, 180.0)
put("bus_stop", -192.0, F - 3.0, 180.0, 1.0, 0.0, -1, 0.0, True)
u("R05_kiosk", -200.0, F + 2.2, 180.0, 1.0, 0.0, True)
u("U05_02_coffee_kiosk", -205.0, F + 2.0, 180.0, 1.0, 0.0, True)
surface("plaza_stop", "walk", -210.0, F, -166.0, 34.0, 0.0, 0.1)
for (x, z) in [(-196, 24), (-182, 24), (-172, 26)]:
    u("U10_04_bench_stone", x, z, 0.0, 1.0, 0.0, True)
    u("U02_02_planter", x, z + 3.5, 0.0, 1.0, 0.0, True)
for (x, z) in [(-204, 28), (-176, 30), (-188, 31)]:
    put("tree_birch", x, z, rng.uniform(0, 360), 1.2)
u("U19_04_square_light", -190.0, 27.0, 0.0)
u("U10_03_wayfinding", -168.0, 19.0, 180.0)
building("Minimarket", "минимаркет «Весна»", (-170.0, 22.0), (12.0, 10.0), "hall", 1, STORY_RETAIL, 180.0, 0.0, "shop", "grocery", 0.5, "South")
upper_floor("минимаркет «Весна»", -170.0, 22.0, 12.0, 10.0, 180.0, roof=True)
flats("House7", "дом 7 — 12 этажей (закрыт)", (-188.0, 51.0), 12, 0, 180.0, (36.0, 26.0), region="South", loot=0.0)
# гаражи-ракушки жильцов (план карты §3, участок 12): стоят вразнобой с разным шагом, носом во двор; вскрытая —
# та, где лут «гараж дома 7» (нос поднят, внутри инструмент и запчасти)
for (x, z, yaw) in [(-206.4, 74.3, 2.0), (-203.6, 74.6, -1.5), (-200.0, 74.5, 1.0), (-197.1, 74.2, -2.5),
                    (-194.3, 74.7, 1.5), (-191.2, 74.4, -1.0)]:
    put("shell_open" if x == -200.0 else "shell", x, z, yaw, 1.0, 0.0, -1, 0.0, True)
u("R02_dumpster", -176.0, 78.0, 90.0, 1.0, 0.0, True)
put("trash_pile", -172.0, 81.0, 0.0, 1.0, 0.0, -1, 0.0, True)
surface("house7_yard", "walk", -210.0, 64.0, -166.0, 108.0, 0.0, 0.05)
for i in range(6):
    u("U14_01_hatchback" if i % 2 else "R04_car", -204.0 + i * 3.4, 95.0, 0.0, 1.0, 0.0, True)
# супермаркет «Ярус»: парковка перед фасадом, зал, склад, разгрузочный двор
SM = (-102.0, 68.0, 80.0, 40.0)
# служебный коридор «Только для персонала» вдоль восточной стены — от тамбура на склад мимо зала (пролог §4.5)
building("Supermarket", "супермаркет «Ярус»", (SM[0], SM[1]), (SM[2], SM[3]), "hall", 1, 6.0, 180.0, 0.0, "supermarket", "grocery", 0.5, "South",
         extra={"staff_corridor": True})
sign("только для персонала", -64.6, 2.6, 49.4, 26)
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
# зал «Яруса» (владелец 2026-10-24: «не хватает наполненности гипермаркета»): ряды стеллажей на всю ширину, линия касс с
# номерами на подвесах, ограждения очередей, тележки, кафе, мешки и колючка у входа, высокие стеллажи склада
for x in (-137.0, -131.0, -125.0, -79.0, -73.0, -67.0):
    box(x, 0.95, 69.0, 1.0, 1.9, 18.0, "accent")
    for dz in (-5.0, 5.0):
        loot(x + 0.9, 0.0, 69.0 + dz, "loose", "common", "стеллаж «Яруса»")
for k, x in enumerate([-138.0, -134.0, -130.0, -126.0, -122.0, -82.0, -78.0, -74.0, -70.0, -66.0]):
    box(x, 0.5, 53.0, 0.7, 1.0, 2.6, "accent")
    box(x, 4.4, 53.0, 0.9, 1.1, 0.06, "paint_blue", 0.0, False)
    box(x, 5.4, 53.0, 0.04, 1.0, 0.04, "steel", 0.0, False)
    sign(str(k + 1), x, 4.4, 52.9, 30)
    if k % 3 == 0:
        loot(x + 0.6, 0.0, 53.0, "register", "common", "касса")
for x in range(-138, -120, 4):
    put("ped_fence", x + 2.0, 51.2, 90.0)
for x in (-104.0, -100.0, -98.5):
    put("cart_row", x, 50.6, 90.0)
for x in (-111.5, -92.5):
    put("sandbags", x, 50.8, 90.0, 1.0, 0.0, -1, 0.0, True)
    box(x + (-2.4 if x < -100 else 2.4), 0.3, 49.6, 3.0, 0.6, 0.6, "steel", 0.0, False)
for (x, z) in [(-136.0, 56.8), (-132.0, 57.0), (-128.0, 56.6)]:
    put("cafe_table", x, z, rng.uniform(0, 90))
sign("кафе", -132.0, 4.4, 55.5, 36)
for x in (-112.0, -92.0):
    put("rack_high", x, 83.15, 90.0, 1.0, 0.0, -1, 0.0, True)
    loot(x, 0.0, 84.0, "crate", "common", "склад «Яруса»")
loot(-140.0, 0.0, 75.0, "med", "med", "аптечный уголок «Яруса»")
loot(-90.0, 0.0, 86.0, "safe", "good", "кабинет администратора: сейф")
loot(-112.0, 0.0, 60.0, "body", "common", "тело мародёра в зале")
for i in range(32):
    x = -142.0 + 1.25 + i * 2.5
    if -104.0 < x < -96.0:                                      # ворота к стройке
        continue
    put("po2", x, 108.5, 90.0)
for i in range(22):
    z = smz1 - 40.0 + 1.25 + i * 2.5
    if z < smz1 or 95.0 < z < 100.5:
        continue
    put("po2", -61.6, z, 0.0)
sign("калитка в служебный проезд", -61.6, 3.2, 97.5, 40)
surface("service_lane", "road", -60.0, F, -50.0, 112.0)
sign("служебный проезд · к скверу", -55.0, 4.0, 104.0, 44)

# ------------------------------------------------------------------ стройка за «Ярусом»
# Владелец 2026-10-24: «стройку передвинуть за ТЦ «Ярус», по размерам как на кадре» (Streets: каркас 9–10 этажей Г-образно,
# кран, синий профнастил, бытовки). Участок x −152…−62, z 112…200: ворота из разгрузки «Яруса», ворота в сквер, пролом
# в южном заборе — выход «Пролом в заборе стройки».
SITE = [-152.0, 112.0, -62.0, 200.0]
surface("site", "mud", SITE[0], SITE[1], SITE[2], SITE[3], 0.0, 0.05)
building("Site_Skeleton", "недострой ЖК, 9 эт.", (-108.0, 150.0), (64.0, 16.0), "skeleton", 9, 3.1, 0.0, 0.0, "", "", 0.0, "South")
building("Site_Skeleton_W", "недострой ЖК, крыло 7 эт.", (-84.0, 174.0), (16.0, 28.0), "skeleton", 7, 3.1, 0.0, 0.0, "", "", 0.0, "South")
building("Site_Crane", "", (-128.0, 176.0), (6.0, 6.0), "crane", 1, 3.0, 0.0, 0.0, "", "", 0.0, "South")


def site_fence(axis: str, c: float, a0: float, a1: float, gaps=()) -> None:
    a = a0 + 1.5
    while a < a1:
        if all(abs(a - g[0]) > g[1] * 0.5 + 1.5 for g in gaps):
            put("fence", a if axis == "x" else c, c if axis == "x" else a, 90.0 if axis == "x" else 0.0, 1.0, 0.0, 3, 0.0, False)
        a += 3.0


site_fence("x", SITE[1] + 0.6, SITE[0], SITE[2], [(-100.0, 6.0)])
site_fence("x", SITE[3] - 0.6, SITE[0], SITE[2], [(-140.0, 3.0), (-100.0, 6.0)])
site_fence("z", SITE[0] + 0.6, SITE[1], SITE[3], [(186.0, 4.0)])
site_fence("z", SITE[2] - 0.6, SITE[1], SITE[3], [(150.0, 5.0), (184.0, 2.5)])
sign("стройка · ворота", -100.0, 3.5, SITE[1] + 0.6, 40)
sign("стройка · ворота в сквер", SITE[2] - 0.6, 3.5, 150.0, 40)
sign("калитка к вокзалу", -140.0, 3.0, SITE[3] - 1.0, 40)
sign("пролом в заборе района", SITE[0] + 1.0, 3.0, 186.0, 40)
# бытовки в два яруса, туалеты, контейнеры, материалы, техника, прожекторы
for i in range(3):
    put("cabin", -146.0, 120.0 + i * 6.4, 90.0, 1.0, 0.0, -1, 0.0, True)
    put("cabin", -146.0, 120.0 + i * 6.4, 90.0, 1.0, 2.64, -1, 0.0, False)
for i in range(3):
    put("outhouse", -146.5, 141.0 + i * 1.4, 90.0)
for (x, z, yaw) in [(-72.0, 120.0, 0.0), (-142.0, 194.5, 0.0), (-118.0, 195.5, 90.0)]:
    put("container20", x, z, yaw, 1.0, 0.0, -1, 0.0, True)
put("container20", -72.2, 120.3, 2.0, 1.0, 2.62, -1, 0.0, False)
for (kit, x, z, yaw) in [("rebar", -120.0, 120.0, 10.0), ("pipes", -96.0, 121.0, 90.0), ("reel", -84.0, 128.0, 0.0),
                         ("pallets", -110.0, 126.0, 30.0), ("pallets", -108.5, 126.4, -20.0), ("slab", -128.0, 130.0, 85.0),
                         ("slab", -128.2, 130.1, 82.0), ("dump_truck", -140.0, 182.0, 0.0), ("tractor", -140.0, 168.0, 20.0),
                         ("trash_pile", -68.0, 168.0, 0.0), ("bags", -70.0, 172.0, 30.0)]:
    put(kit, x, z, yaw, 1.0, 0.2 if kit == "slab" and x < -128.1 else 0.0, -1, 0.0, kit in ("pipes", "reel", "pallets", "dump_truck", "tractor", "slab"))
for (x, z) in [(-118.0, 168.0), (-66.0, 140.0)]:
    put("mast", x, z, 0.0)
# леса на южном фасаде каркаса: стойки, настилы, перила — вертикаль с ограниченным обзором
for k in range(18):
    x = -138.0 + k * 2.4
    box(x, 10.0, 158.8, 0.06, 20.0, 0.06, "steel", 0.0, False)
    box(x, 10.0, 160.0, 0.06, 20.0, 0.06, "steel", 0.0, False)
for lvl in range(1, 7):
    box(-117.6, lvl * 3.1 - 0.05, 159.4, 41.0, 0.06, 1.3, "rust", 0.0, lvl * 3.1 < 4.0)
    box(-117.6, lvl * 3.1 + 1.0, 160.05, 41.0, 0.05, 0.05, "steel", 0.0, False)
for (x, y, z, kind, tier, note) in [(-146.0, 0.0, 117.0, "cabinet", "common", "бытовка прораба"),
                                    (-146.0, 2.64, 127.0, "safe", "good", "бытовка: сейф с зарплатой"),
                                    (-100.0, 0.0, 124.0, "crate", "common", "инструмент"),
                                    (-80.0, 3.1 * 4 + 0.1, 150.0, "weapon", "weapon", "лёжка на 5-м этаже каркаса"),
                                    (-130.0, 3.1 * 8 + 0.1, 146.0, "body", "good", "тело снайпера ЧВК на 9-м этаже"),
                                    (-140.0, 0.0, 186.5, "car", "common", "кабина самосвала"),
                                    (-120.0, 0.0, 196.0, "loose", "common", "у пролома")]:
    loot(x, y, z, kind, tier, note)
FI["stories"].append({"label": "стройка за «Ярусом»: каркас, кран, бытовки", "at": [-108.0, 170.0], "height": 6.0})
# котлован под следующую секцию, залитый водой (владелец 2026-10-25: «лысовато… может пруд какой-то»): 26 × 26 м,
# глубина 4 м, вода по колено у дна, въезд для техники вдоль восточной стенки, экскаватор на бровке, арматура и опалубка
# на дне; дорога из плит от ворот, кучи песка и щебня, бетоносмеситель, поддоны кирпича, мешки цемента
SPIT = [-124.0, 164.0, -98.0, 190.0]
SPIT_Y = -4.0
plan["ground_holes"].append([SPIT[0] - 0.4, SPIT[1] - 0.4, SPIT[2] + 0.4, SPIT[3] + 0.4])
for srf in plan["surfaces"]:
    if srf["id"] == "site":
        srf["holes"] = [[SPIT[0] - 0.4, SPIT[1] - 0.4, SPIT[2] + 0.4, SPIT[3] + 0.4]]
slab("site_pit_floor", [SPIT[0] - 0.4, SPIT[1] - 0.4, SPIT[2] + 0.4, SPIT[3] + 0.4], SPIT_Y, 0.4, "mud")
wall(SPIT[0] - 0.4, SPIT[1] - 0.4, SPIT[0], SPIT[3] + 0.4, SPIT_Y, 0.0, "mud")
wall(SPIT[2], SPIT[1] - 0.4, SPIT[2] + 0.4, SPIT[3] + 0.4, SPIT_Y, 0.0, "mud")
wall(SPIT[0], SPIT[1] - 0.4, SPIT[2] - 4.4, SPIT[1], SPIT_Y, 0.0, "mud")
wall(SPIT[0], SPIT[3], SPIT[2], SPIT[3] + 0.4, SPIT_Y, 0.0, "mud")
plan["ramps"].append({"x0": SPIT[2] - 4.4, "x1": SPIT[2], "z0": SPIT[1] - 0.4, "z1": SPIT[1] + 17.0, "y0": 0.0, "y1": SPIT_Y, "mat": "mud"})
wall(SPIT[2] - 4.7, SPIT[1] + 4.0, SPIT[2] - 4.4, SPIT[1] + 17.0, SPIT_Y, -1.2, "mud")
box((SPIT[0] + SPIT[2]) * 0.5, SPIT_Y + 0.55, (SPIT[1] + SPIT[3]) * 0.5, SPIT[2] - SPIT[0], 0.04, SPIT[3] - SPIT[1], "water", 0.0, False)
for k in range(6):
    put("hazard_fence", SPIT[0] + 1.25 + k * 3.6, SPIT[1] - 1.0, 90.0, 1.0, 0.0, -1, 0.0, False)
for k in range(5):
    put("hazard_fence", SPIT[0] - 1.0, SPIT[1] + 2.0 + k * 5.0, 0.0, 1.0, 0.0, -1, 0.0, False)
for (x, z) in [(-118.0, 172.0), (-110.0, 178.0), (-116.0, 184.0), (-106.0, 170.0)]:
    for dx in (-1.2, 0.0, 1.2):
        box(x + dx, SPIT_Y + 1.0, z, 0.04, 2.0, 0.04, "rust", 0.0, False)               # выпуски арматуры
put("pallets", -120.0, 186.0, 15.0, 1.0, SPIT_Y)
put("pallets", -104.0, 186.5, 40.0, 1.0, SPIT_Y)
put("excavator", -112.0, 160.5, 0.0, 1.0, 0.0, -1, 0.0, True)
loot(-113.0, SPIT_Y, 181.0, "body", "common", "котлован: утонувший мародёр")
loot(-104.0, SPIT_Y, 186.0, "crate", "common", "котлован: ящик с инструментом")
surface("site_road", "slab", -106.0, SITE[1], -100.0, 141.5, 0.0, 0.1)
for (kit, x, z, yaw, sc) in [("pile_sand", -146.0, 152.0, 20.0, 1.2), ("pile_sand", -70.0, 144.0, 70.0, 1.0),
                             ("pile_sand", -132.0, 185.5, 0.0, 0.9), ("mixer", -86.0, 197.0, 90.0, 1.0)]:
    put(kit, x, z, yaw, sc, 0.0, -1, 0.0, True)
for (x, z) in [(-74.0, 128.0), (-72.6, 129.4), (-75.4, 129.6), (-74.0, 131.0)]:
    put("pallets", x, z, rng.uniform(-10, 10), 1.0, 0.0, 9, 0.0, True)
for k in range(5):
    put("bags", -82.0 + k * 0.7, 134.0 + (k % 2) * 0.6, rng.uniform(0, 360))
for (x, z) in [(-118.0, 128.0), (-115.0, 128.0)]:
    box(x, 0.6, z, 2.4, 1.2, 1.2, "wood")                                        # опалубка штабелем
for k in range(4):
    box(-86.0 + k * 1.0, 0.3, 128.0, 0.6, 0.6, 6.0, "rust")                     # арматурные каркасы
put("booth", -95.0, 114.5, 180.0, 1.0, 0.0, -1, 0.0, True)
sign("стройка · посторонним вход запрещён", -100.0, 4.4, SITE[1] + 0.8, 34)

# ------------------------------------------------------------------ вокзал «Проспект» у насыпи
# Владелец 2026-10-25: «можно большой железнодорожный вокзал, как предложение». Вокзал к югу от стройки у подошвы
# насыпи: площадь со стоянкой такси и остановкой; здание 60 × 30 — высокий зал в две высоты с кассами и табло,
# зал ожидания с кафе и туалетами (запад), кассы, камера хранения и полиция (восток), антресоль служебных помещений;
# в глубине зала лестница на галерею и мост к платформе на насыпи; на платформе — навес и вагоны сошедшего состава.
SX0, SX1, SZ0, SZ1 = -146.0, -86.0, 214.0, 244.0
UPL = 7.6                                                       # уровень платформы и антресоли
SROOF = 13.0
surface("station_square", "walk", -151.5, SITE[3] + 0.2, -50.0, SZ0, 0.0, 0.1)
surface("station_west", "walk", -151.5, SZ0, SX0, EMB_Z0, 0.0, 0.1)
surface("station_east", "walk", SX1, SZ0, -50.0, EMB_Z0, 0.0, 0.1)
surface("station_back", "walk", SX0, SZ1, SX1, EMB_Z0, 0.0, 0.1)
slab("stn_floor", [SX0, SZ0, SX1, SZ1], 0.12, 0.24, "walk")
slab("stn_mezz", [-106.0, SZ0, SX1, SZ1], UPL, 0.3, "slab")
slab("stn_landing", [-112.4, 238.0, -106.0, SZ1], UPL, 0.3, "slab")
slab("stn_roof", [SX0 - 0.4, SZ0 - 0.4, SX1 + 0.4, SZ1 + 0.4], SROOF, 0.4, "slab", [[-89.8, 233.4, -88.2, 243.2]])
lo, up = UPL - 0.12, SROOF - UPL
# фасад к площади: три входа в зал под козырьком, витраж в две высоты, входы крыльев
wall_x(SZ0, -126.0, -106.0, 0.12, 4.0, [(-121.0, 2.4, 3.2), (-116.0, 2.4, 3.2), (-111.0, 2.4, 3.2)], 0.4)
wall_x(SZ0, -126.0, -106.0, 4.12, SROOF - 4.12, [(-116.0, 17.0, 7.5, 0.4)], 0.4)
wall_x(SZ0, SX0, -126.0, 0.12, lo, [(-136.0, 1.8, 2.6)] + windows(SX0, -126.0, 4.0, 2.4, 1.0, 5.6, [(-136.0, 1.8)]), 0.4)
wall_x(SZ0, -106.0, SX1, 0.12, lo, [(-91.0, 1.4, 2.42)] + windows(-106.0, SX1, 4.0, 2.0, 1.0, 5.6, [(-91.0, 1.4)]), 0.4)
for (a0, a1) in [(SX0, -126.0), (-106.0, SX1)]:
    wall_x(SZ0, a0, a1, UPL, up, windows(a0, a1, 4.0, 2.0, 0.9, 3.4), 0.4)
# тыльная сторона к насыпи: служебные двери, дверь на мост с галереи
wall_x(SZ1, SX0, SX1, 0.12, lo, [(-140.0, 1.4, 2.42), (-92.0, 1.4, 2.42)] + windows(SX0, SX1, 6.0, 2.0, 2.0, 5.6, [(-140.0, 1.4), (-92.0, 1.4)]), 0.4)
wall_x(SZ1, SX0, SX1, UPL, up, [(-110.0, 1.6, 2.6)] + windows(SX0, SX1, 6.0, 2.0, 0.9, 3.4, [(-110.0, 1.6)]), 0.4)
for (xs, door) in [(SX0, 238.0), (SX1, 238.0)]:
    wall_z(xs, SZ0, SZ1, 0.12, lo, [(door, 1.4, 2.42)] + windows(SZ0, SZ1, 5.0, 2.0, 1.0, 5.6, [(door, 1.4)]), 0.4)
    wall_z(xs, SZ0, SZ1, UPL, up, windows(SZ0, SZ1, 5.0, 2.0, 0.9, 3.4), 0.4)
# внутренние стены: зал | зал ожидания, зал | кассы и полиция, кассы | камера хранения, туалеты, антресоль
wall_z(-126.0, SZ0, SZ1, 0.12, SROOF - 0.12, [(222.0, 3.0, 4.0), (231.0, 2.4, 3.2)], 0.3)
wall_z(-106.0, SZ0, SZ1, 0.12, lo, [(216.5, 1.2, 2.2, 1.0), (219.5, 1.2, 2.2, 1.0), (222.5, 1.2, 2.2, 1.0), (225.5, 1.2, 2.2, 1.0),
                                    (236.0, 1.6, 2.6)], 0.3)
wall(-106.15, SZ0, -105.85, 238.0, UPL, UPL + 1.1, "steel")                    # перила антресоли над залом
wall_z(-96.0, SZ0, 230.0, 0.12, lo, [(222.0, 1.17, 2.42)], 0.2)
wall_x(230.0, -106.0, SX1, 0.12, lo, [(-101.0, 1.17, 2.42)], 0.2)
wall_x(236.0, SX0, -126.0, 0.12, 3.0, [(-140.0, 1.0, 2.2), (-132.0, 1.0, 2.2)], 0.15)
wall_z(-136.0, 236.0, SZ1, 0.12, 3.0, (), 0.15)
wall_x(228.0, -106.0, SX1, UPL, up, [(-96.0, 1.17, 2.42)], 0.15)
# лестницы: из зала на галерею (к мосту), с антресоли на крышу
stair((-125.0, 0.12, 241.0), (-112.4, UPL, 241.0), 2.4)
stair((-89.0, UPL, 243.0), (-89.0, SROOF, 233.6), 1.4)
for (x0, z0, x1, z1) in [(SX0 - 0.4, SZ0 - 0.4, SX1 + 0.4, SZ0 - 0.2), (SX0 - 0.4, SZ1 + 0.2, SX1 + 0.4, SZ1 + 0.4),
                         (SX0 - 0.4, SZ0 - 0.4, SX0 - 0.2, SZ1 + 0.4), (SX1 + 0.2, SZ0 - 0.4, SX1 + 0.4, SZ1 + 0.4)]:
    wall(x0, z0, x1, z1, SROOF, SROOF + 1.0, "concrete")
# мост с галереи на платформу и платформа с навесом на насыпи
slab("stn_bridge", [-111.6, SZ1, -108.4, EMB_Z1 + 0.4], UPL, 0.3, "steel")
wall(-111.75, SZ1, -111.6, EMB_Z1, UPL, UPL + 1.1, "steel")
wall(-108.4, SZ1, -108.25, EMB_Z1, UPL, UPL + 1.1, "steel")
box(-110.0, UPL + 2.9, (SZ1 + EMB_Z1) * 0.5, 3.6, 0.15, EMB_Z1 - SZ1 + 0.4, "slab", 0.0, False)
wall(-150.0, EMB_Z1, -74.0, EMB_Z1 + 4.5, EMB_H, UPL, "concrete")
box(-112.0, UPL + 0.01, EMB_Z1 + 4.3, 76.0, 0.02, 0.3, "stripe", 0.0, False)
for x in range(-146, -74, 8):
    box(float(x), UPL + 1.7, EMB_Z1 + 2.2, 0.25, 3.4, 0.25, "steel")
box(-112.0, UPL + 3.5, EMB_Z1 + 2.2, 76.0, 0.2, 5.0, "slab", 0.0, False)
sign("1 платформа", -125.0, UPL + 2.8, EMB_Z1 + 0.4, 34)
# козырёк над входами, вывеска и часы
box(-116.0, 4.4, SZ0 - 2.5, 18.0, 0.25, 5.0, "slab", 0.0, False)
for x in (-124.0, -108.0):
    box(x, 2.2, SZ0 - 4.6, 0.3, 4.4, 0.3, "steel")
sign("вокзал «Проспект»", -116.0, SROOF + 2.0, SZ0 - 0.6, 80)
box(-116.0, 11.6, SZ0 - 0.25, 2.2, 2.2, 0.2, "paint_white", 0.0, False)
# обстановка: табло, справочная, лавки зала ожидания, кафе, туалеты, кассы, камера хранения, полиция, антресоль
box(-116.0, 6.4, SZ1 - 0.35, 10.0, 2.2, 0.2, "dark", 0.0, False)
box(-116.0, 0.67, 226.0, 3.0, 1.1, 1.4, "accent")
for x in (-124.0, -108.0):
    for z in (218.0, 224.0):
        put("bench", x, z, 90.0 if x < -116 else -90.0, 1.0, 0.12)
for z in (218.0, 223.0, 228.0):
    for x in (-142.0, -138.0, -134.0, -130.0):
        put("bench", x, z, 0.0, 1.0, 0.12)
box(-129.5, 0.67, 233.0, 4.0, 1.1, 0.8, "accent")
for (x, z) in [(-143.0, 233.0), (-139.0, 233.5)]:
    put("cafe_table", x, z, rng.uniform(0, 90), 1.0, 0.12)
for z in (217.0, 221.0, 225.0):
    box(-104.6, 0.5, z, 1.4, 0.75, 1.2, "accent")
for (x, z, yaw) in [(-86.6, 218.0, 90.0), (-86.6, 222.0, 90.0), (-86.6, 226.0, 90.0), (-95.4, 226.5, -90.0)]:
    put("deposit_wall", x, z, yaw, 1.0, 0.12, -1, 0.0, True)
for (x, z) in [(-102.0, 236.0), (-96.0, 240.0)]:
    box(x, 0.5, z, 1.6, 0.75, 0.8, "accent")
for k in range(3):
    put("bar_fence", -88.5, 232.5 + k * 2.5, 0.0, 1.0, 0.12)
for (x, z) in [(-102.0, 220.0), (-92.0, 220.0), (-100.0, 236.0)]:
    box(x, UPL + 0.38, z, 1.6, 0.75, 0.8, "accent")
plan["lamps"] += [[-116.0, 10.0, 222.0, 0.8, 16.0], [-116.0, 10.0, 236.0, 0.6, 14.0], [-136.0, 6.0, 224.0, 0.6, 12.0],
                  [-96.0, 6.0, 222.0, 0.5, 10.0], [-96.0, 6.0, 237.0, 0.5, 10.0], [-96.0, UPL + 4.0, 222.0, 0.5, 10.0],
                  [-96.0, UPL + 4.0, 236.0, 0.5, 10.0], [-112.0, UPL + 3.0, 260.0, 0.5, 12.0]]
# привокзальная площадь: такси, остановка с ПАЗом, ларёк, тележки и чемоданы, часы, полицейская, пост ЧВК
for (x, z, yaw) in [(-132.0, 207.0, 88.0), (-138.0, 206.5, 92.0), (-144.0, 207.2, 85.0)]:
    put("taxi", x, z, yaw, 1.0, 0.0, 8, 0.0, True)
put("paz", -78.0, 203.0, 90.0, 1.0, 0.0, 8, 0.0, True)
put("bus_stop", -70.0, 209.5, 180.0, 1.0, 0.0, -1, 0.0, True)
put("kiosk", -90.0, 203.5, 0.0, 1.0, 0.0, -1, 0.0, True)
for (x, z) in [(-128.0, 211.5), (-104.0, 211.5)]:
    put("flowerbed", x, z, 0.0)
for x in range(-146, -54, 15):
    put("lamp", float(x), 200.8, 0.0)
box(-100.0, 2.0, 210.0, 0.25, 4.0, 0.25, "black")
box(-100.0, 4.2, 210.0, 0.9, 0.9, 0.3, "paint_white", 0.0, False)
for k in range(3):
    put("cart", -105.0 + k * 1.2, 212.3, rng.uniform(-20, 20))
for (x, z) in [(-112.0, 212.0), (-113.0, 211.0), (-98.0, 208.5), (-120.0, 210.0)]:
    put("suitcase", x, z, rng.uniform(0, 360))
put("police_car", -58.0, 210.8, 2.0, 1.0, 0.0, -1, 0.0, True)
put("sandbag_post", -56.0, 214.0, 90.0, 1.0, 0.0, -1, 0.0, True)
put("body_mar", -96.0, 209.0, 40.0)
# вагоны сошедшего состава у платформы
for (kit, x, z, yaw, dy, roll) in [("wagon_pass", -130.0, 265.0, 90.0, EMB_H, 0.0), ("wagon_pass", -112.0, 265.6, 92.0, EMB_H, 11.0),
                                   ("wagon_box", -93.0, 266.2, 96.0, EMB_H - 0.2, 26.0)]:
    put(kit, x, z, yaw, 1.0, dy, -1, roll, True)
for (x, y, z, kind, tier, note) in [(-91.0, 0.12, 220.0, "cells", "good", "камера хранения: ячейки"),
                                    (-91.0, 0.12, 226.0, "cells", "good", "камера хранения: ячейки"),
                                    (-100.0, 0.12, 216.0, "safe", "good", "кассы: сейф с выручкой"),
                                    (-88.5, 0.12, 240.0, "weapon", "weapon", "полиция: оружейный шкаф"),
                                    (-102.0, 0.12, 237.2, "cabinet", "common", "полиция: стол дежурного"),
                                    (-129.5, 0.12, 234.0, "register", "common", "вокзальное кафе: касса"),
                                    (-134.0, 0.12, 223.0, "backpack", "common", "зал ожидания: рюкзак"),
                                    (-140.0, 0.12, 218.0, "suitcase", "common", "зал ожидания: чемодан"),
                                    (-116.0, 0.12, 227.6, "loose", "common", "справочная"),
                                    (-92.0, UPL, 221.0, "safe", "good", "кабинет начальника вокзала: сейф"),
                                    (-100.0, UPL, 237.0, "cabinet", "common", "антресоль: шкаф"),
                                    (-120.0, SROOF, 230.0, "crate", "good", "крыша вокзала: тайник"),
                                    (-125.0, UPL, 260.5, "body", "weapon", "платформа: тело бойца ЧВК"),
                                    (-112.0, UPL, 261.6, "suitcase", "common", "платформа: багаж из вагона"),
                                    (-93.0, EMB_H, 263.0, "crate", "common", "груз из вагона")]:
    loot(x, y, z, kind, tier, note)
FI["stories"].append({"label": "вокзал «Проспект»: последний поезд сошёл с путей", "at": [-116.0, 229.0], "height": 9.0})


# ================================================================== внутренний угол поворота: дом на повороте и сквер
# Владелец 2026-10-25: «где начинается сквер, на изгибе дороги — ещё одну высотку, первый этаж — магазины, ПВЗ,
# пивнушки, табачки, кафешка, парикмахерская, аптека; все насквозь проходимые. Сквер сдвинуть к тоннелю — начинается
# сразу за домом, уплотнить, чтобы вагоны валялись на объектах сквера, был хаос». Дом «Проспект, 1»: подиум в один
# этаж Г-образно вдоль поворота (крыло к проспекту, угол под башней, крыло к южному плечу) и башня 26 этажей на углу.
# Каждый магазин — дверь с улицы и дверь во двор на одной оси (насквозь), две арки во двор; на крыши крыльев — наружные
# лестницы со двора. Жилая башня глухая, как другие дома.
PODIUM_H = 4.5
PODIUM_TOP = 4.65


def lbox(fr: Frame, lx: float, y: float, lz: float, sx: float, sy: float, sz: float, mat: str = "accent", solid: bool = True) -> None:
    x, z = fr.p(lx, lz)
    box(x, y, z, sx, sy, sz, mat, fr.yaw, solid)


def lput(fr: Frame, kit: str, lx: float, lz: float, yaw: float = 0.0, s_: float = 1.0, dy: float = 0.0, cover: bool = False) -> None:
    x, z = fr.p(lx, lz)
    put(kit, x, z, fr.yaw + yaw, s_, dy, -1, 0.0, cover)


def lloot(fr: Frame, lx: float, lz: float, kind: str, tier: str, note: str) -> None:
    x, z = fr.p(lx, lz)
    loot(x, 0.12, z, kind, tier, note)


def furnish(fr: Frame, kind: str, title: str, a0: float, a1: float, hz: float) -> None:
    """Обстановка магазина в местных координатах (x вдоль фасада, +z — улица); посередине — сквозной проход 2 м."""
    mid = (a0 + a1) * 0.5
    left, right = a0 + 0.35, a1 - 0.35
    lw = max(0.6, mid - 1.1 - left)                       # ширина полосы слева от прохода
    lc = left + lw * 0.5
    rc = right - lw * 0.5
    y = 0.12
    if kind == "pvz":
        for c in (lc, rc):
            lbox(fr, c, y + 1.1, -hz * 0.35, lw, 2.2, hz * 1.1, "steel")
            lput(fr, "boxes", c, -hz * 0.35, 0.0, 1.0, 2.25)
        lbox(fr, lc, y + 0.55, hz - 2.6, lw, 1.1, 0.7)
        lloot(fr, lc, -1.0, "crate", "good", title + ": посылки")
        lloot(fr, rc, -3.0, "crate", "common", title + ": посылки")
    elif kind == "bar":
        lbox(fr, lc, y + 0.55, 0.0, 0.8, 1.1, hz * 1.1, "wood")
        for dz in (-hz + 1.0, -hz + 2.0):
            lput(fr, "barrel", left + 0.4, dz)
        for dz in (hz - 3.0, 0.0, -hz + 2.5):
            lput(fr, "cafe_table", rc, dz, 30.0)
        lloot(fr, lc + 0.7, 0.0, "register", "common", title + ": касса")
        lloot(fr, left + 0.5, -hz + 1.5, "crate", "common", title + ": кеги и ящики")
    elif kind == "tobacco":
        lbox(fr, lc, y + 0.55, 0.5, min(lw, 0.8), 1.1, 3.0)
        lbox(fr, left + 0.15, y + 1.2, 0.5, 0.3, 2.4, 3.6, "steel")
        lloot(fr, lc, 2.2, "register", "common", title + ": касса")
    elif kind == "cafe":
        lbox(fr, lc, y + 0.55, -hz + 2.2, lw, 1.1, 0.8)
        for dz in (hz - 2.5, 0.0, -hz + 2.6):
            lput(fr, "cafe_table", rc, dz, 15.0)
        lloot(fr, lc, -hz + 3.0, "register", "common", title + ": касса")
        lloot(fr, rc, 0.0, "loose", "common", title + ": на столе")
    elif kind == "repair":
        lbox(fr, lc, y + 0.4, 0.0, min(lw, 0.9), 0.8, 2.0)
        lbox(fr, right - 0.15, y + 1.0, -1.0, 0.3, 2.0, 3.0, "steel")
        lloot(fr, lc, 1.5, "crate", "good", title + ": телефоны и платы")
    elif kind == "pharmacy":
        for c in (lc, rc):
            for dz in (-2.5, 1.5):
                lbox(fr, c, y + 0.9, dz, lw, 1.8, 0.6)
        lbox(fr, lc, y + 0.55, hz - 2.4, lw, 1.1, 0.7)
        lloot(fr, lc, -1.6, "med", "med", title + ": полки")
        lloot(fr, rc, 2.4, "med", "med", title + ": полки")
        lloot(fr, rc, -hz + 1.2, "med", "good", title + ": склад рецептурного")
    elif kind == "lobby":
        lbox(fr, left + 0.15, y + 1.2, 0.0, 0.3, 1.6, 4.0, "steel")
        lbox(fr, rc, y + 0.55, hz - 3.0, lw, 1.1, 1.6)
        lbox(fr, rc, y + 1.2, -hz + 0.3, 1.2, 2.3, 0.1, "dark", False)
        lloot(fr, rc, hz - 4.2, "loose", "common", title + ": стойка консьержа")
    elif kind == "grocery":
        for c in (lc, rc):
            for dz in (-hz * 0.45, 0.0, hz * 0.45):
                lbox(fr, c, y + 0.9, dz, lw, 1.8, 2.0)
        lloot(fr, lc, -hz * 0.2, "loose", "common", title + ": полки")
        lloot(fr, rc, hz * 0.25, "loose", "common", title + ": полки")
        lloot(fr, rc, hz - 1.2, "register", "common", title + ": касса")
    elif kind == "barber":
        for dz in (-2.5, 0.0, 2.5):
            lbox(fr, left + 0.6, y + 0.5, dz, 0.7, 1.0, 0.7)
        lbox(fr, left + 0.05, y + 1.5, 0.0, 0.04, 1.2, 7.0, "dark", False)
        lbox(fr, rc, y + 0.55, hz - 2.0, lw, 1.1, 0.7)
        lloot(fr, rc, hz - 3.0, "loose", "common", title + ": касса и инструмент")
    elif kind == "phones":
        lbox(fr, rc, y + 0.55, hz - 2.4, lw, 1.1, 0.8)
        lbox(fr, lc, y + 0.45, 0.0, lw, 0.9, 1.6)
        lloot(fr, lc, -1.2, "crate", "good", title + ": витрина телефонов")
    elif kind == "flowers":
        for dz in (-2.0, -0.8, 0.4, 1.6):
            lput(fr, "barrel", left + 0.5, dz, 0.0, 0.6)
        lbox(fr, rc, y + 0.55, 0.5, lw, 1.1, 2.4)
        lloot(fr, rc, -1.2, "loose", "common", title + ": касса")
    elif kind == "shawarma":
        lbox(fr, lc, y + 0.55, hz - 2.2, lw, 1.1, 3.0, "steel")
        lloot(fr, lc, hz - 4.0, "register", "common", title + ": касса")
    elif kind == "pawn":
        lbox(fr, lc, y + 0.55, 0.5, lw, 1.1, 0.7)
        lput(fr, "bar_fence", lc, 0.5, 90.0, 0.7, 1.2)
        lbox(fr, left + 0.5, y + 0.6, -hz + 0.8, 0.9, 1.2, 0.8, "steel")
        lloot(fr, left + 0.5, -hz + 1.6, "safe", "good", title + ": сейф с золотом")
        lloot(fr, rc, -1.0, "weapon", "weapon", title + ": охотничье ружьё в залоге")
    elif kind == "gym":
        for c in (lc, rc):
            for dz in (-3.5, 0.0, 3.5):
                lbox(fr, c, y + 0.6, dz, min(lw, 1.4), 1.2, 1.8, "dark")
        lbox(fr, right - 0.25, y + 1.0, -hz + 2.0, 0.5, 2.0, 3.0, "steel")
        lloot(fr, right - 0.9, -hz + 2.0, "cabinet", "common", title + ": шкафчики")
    elif kind == "arch":
        lbox(fr, a0 + 0.12, 1.2, 0.0, 0.03, 1.6, 6.0, "graffiti", False)


def retail_row(rid: str, cx: float, cz: float, length: float, depth: float, yaw: float, bays: list) -> Frame:
    """Ряд магазинов подиума: плита пола, крыша, фасад с витринами и дверями, двери во двор на той же оси."""
    fr = Frame(cx, cz, yaw)
    hx, hz = length * 0.5, depth * 0.5
    slab("floor_" + rid, fr.rect(-hx, -hz, hx, hz), 0.12, 0.24, "walk")
    slab("roof_" + rid, fr.rect(-hx - 0.3, -hz - 0.3, hx + 0.3, hz + 0.3), PODIUM_TOP, 0.3, "slab")
    h = PODIUM_H - 0.12
    front, back = [], []
    a = -hx
    for (title, kind, w) in bays:
        mid = a + w * 0.5
        if kind == "arch":
            front.append((mid, w - 0.6, 3.4))
            back.append((mid, w - 0.6, 3.4))
        else:
            front.append((mid, 1.8, 2.6))
            back.append((mid, 1.17, 2.42))
            if w >= 7.0:
                for sd in (-1.0, 1.0):
                    front.append((mid + sd * (w * 0.25 + 0.45), w * 0.5 - 2.0, 3.3, 0.5))
            else:
                front.append((mid + 1.6, 1.0, 3.0, 0.8))
        if a + w < hx - 0.1:
            wall_z(a + w, -hz, hz, 0.12, h, (), 0.2, "wall", fr)
        x, z = fr.p(mid, hz + 0.5)
        sign(title, x, 3.9, z, 30)
        x, z = fr.p(mid, 0.0)
        plan["lamps"].append([round(x, 2), 3.9, round(z, 2), 0.45, 8.0])
        furnish(fr, kind, title, a, a + w, hz)
        a += w
    wall_x(hz, -hx, hx, 0.12, h, front, 0.3, "wall", fr)
    wall_x(-hz, -hx, hx, 0.12, h, back, 0.3, "wall", fr)
    for xs in (-hx, hx):
        wall_z(xs, -hz, hz, 0.12, h, (), 0.3, "wall", fr)
    return fr


TOWER_AT = (7.0, 36.0)
retail_row("podium_w", -25.0, 28.0, 42.0, 14.0, 180.0,
           [("ремонт телефонов", "repair", 5.0), ("кафе «Угол»", "cafe", 9.0), ("табак", "tobacco", 5.0),
            ("арка во двор", "arch", 5.0), ("пивная «Разливное»", "bar", 9.0), ("ПВЗ «Посылка»", "pvz", 9.0)])
retail_row("podium_c", 8.5, 36.0, 25.0, 22.0, 180.0,
           [("продукты «Угловой»", "grocery", 7.0), ("вестибюль башни", "lobby", 6.0), ("аптека «Здоровье»", "pharmacy", 12.0)])
retail_row("podium_s", 28.0, 70.0, 52.0, 14.0, 90.0,
           [("фитнес «Атлет»", "gym", 12.0), ("ломбард «Золото»", "pawn", 8.0), ("шаурма", "shawarma", 6.0), ("цветы", "flowers", 6.0),
            ("арка во двор", "arch", 5.0), ("салон связи", "phones", 7.0), ("парикмахерская «Локон»", "barber", 8.0)])
flats("Tower_Povorot", "«Проспект, 1» — башня 26 этажей (закрыта)", TOWER_AT, 26, 0, 0.0, (22.0, 22.0), STORY_FLAT, True, False,
      PODIUM_TOP, "South", 0.0)
sign("«Проспект, 1»", TOWER_AT[0], 6.4, 24.6, 48)
# крыши крыльев: парапеты, наружные лестницы со двора, лёжки и тайники
yr = PODIUM_TOP
for (x0, z0, x1, z1) in [(-46.3, 20.7, -4.0, 20.9), (-46.3, 35.1, -4.0, 35.3), (-46.3, 20.7, -46.1, 27.9), (-46.3, 29.5, -46.1, 35.3),
                         (-4.2, 20.7, -4.0, 25.0), (21.0, 43.7, 35.3, 43.9), (35.1, 43.7, 35.3, 96.3), (21.0, 96.1, 28.4, 96.3),
                         (30.0, 96.1, 35.3, 96.3), (20.7, 47.0, 20.9, 96.3), (18.0, 24.7, 21.3, 24.9), (21.1, 24.7, 21.3, 43.9)]:
    wall(x0, z0, x1, z1, yr, yr + 1.0, "concrete")
stair((-47.0, 0.0, 36.6), (-47.0, yr, 29.6), 1.4, "steel")
box(-47.0, yr - 0.12, 28.7, 1.6, 0.24, 1.6, "steel")
stair((21.6, 0.0, 97.1), (28.4, yr, 97.1), 1.4, "steel")
box(29.2, yr - 0.12, 97.0, 1.6, 0.24, 1.6, "steel")
put("sandbags", -30.0, 22.0, 90.0, 1.0, yr, -1, 0.0, True)
loot(-32.0, yr, 23.0, "crate", "good", "крыша подиума: тайник у лёжки на проспект")
put("sandbags", 33.5, 60.0, 0.0, 1.0, yr, -1, 0.0, True)
loot(32.0, yr, 62.0, "weapon", "weapon", "крыша подиума: лёжка на южное плечо")
for x in (-40.0, -12.0):
    put("ac_unit", x, 31.0, 0.0, 1.6, yr + 0.45)

# ---- сквер от дома до насыпи
surface("fore_w", "walk", -50.0, F, -4.0, 21.0, 0.0, 0.1)
surface("fore_c", "walk", -4.0, F, 21.0, 25.0, 0.0, 0.1)
surface("fore_ce", "walk", 21.0, 28.0, 37.0, 44.0, 0.0, 0.1)
surface("fore_s", "walk", 35.0, 44.0, XS - F, 96.0, 0.0, 0.1)
surface("fore_ws", "walk", -50.0, 21.0, -46.0, 35.0, 0.0, 0.1)
surface("square_a", "walk", -50.0, 35.0, 21.0, 108.0, 0.0, 0.1)
plan["surfaces"][-1]["holes"] = [[-4.0, 35.0, 21.0, 47.0]]
surface("square_b", "walk", 21.0, 96.0, XS - F, 108.0, 0.0, 0.1)
surface("square_c", "walk", -50.0, 108.0, XS - F, EMB_Z0, 0.0, 0.1)
u("U10_03_wayfinding", -48.0, 18.0, 180.0)
# двор за домом: терраса кафе, велопарковка, лавки, баки, машины жильцов, деревья
for (x, z) in [(-9.5, 39.5), (-17.0, 40.0), (-11.0, 43.5)]:
    put("cafe_table", x, z, rng.uniform(0, 90))
for x in (-30.0, -27.5):
    put("ped_fence", x, 38.5, 90.0)
for (x, z, yaw) in [(-40.0, 44.0, 0.0), (4.0, 52.0, 180.0), (-2.0, 52.0, 180.0)]:
    u("U02_03_bench_tube", x, z, yaw, 1.0, 0.0, True)
for i in range(2):
    u("R02_dumpster", -46.5, 41.0 + i * 3.0, 90.0, 1.0, 0.0, True)
put("trash_pile", -44.0, 48.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("car", -36.0, 53.0, 92.0, 1.0, 0.0, 3, 0.0, True)
put("car_open", -28.0, 54.0, 78.0, 1.0, 0.0, 6, 0.0, True)
loot(-28.0, 0.0, 51.5, "car", "common", "машина жильца во дворе")
for (x, z) in [(-20.0, 50.0), (12.0, 53.0), (-44.0, 57.0), (-8.0, 57.0)]:
    put("tree_round", x, z, rng.uniform(0, 360), rng.uniform(0.9, 1.15))
for (x, z) in [(-36.0, 40.0), (6.0, 58.0), (-24.0, 58.0)]:
    put("lamp_park", x, z, 0.0)
# площадь с памятником: канделябры кольцом, ограждения, тела под простынями, клумбы, доска почёта, ларьки, сцена
MON = (-14.0, 76.0)
put("monument", MON[0], MON[1], 0.0, 1.0, 0.0, -1, 0.0, True)
sign("сквер · памятник", MON[0], 6.0, MON[1], 44)
for k in range(8):
    a = k * math.pi / 4.0
    put("ornate_lamp", MON[0] + 11.0 * math.cos(a), MON[1] + 11.0 * math.sin(a), math.degrees(a), 1.0, 0.0, -1, 0.0, True)
for k in range(9):
    a = 0.4 + k * 0.42
    put("crowd_barrier", MON[0] + 7.0 * math.cos(a), MON[1] + 7.0 * math.sin(a), -math.degrees(a), 1.0, 0.0, -1, 0.0, True)
for (x, z, yaw) in [(-23.0, 68.0, 20.0), (-25.0, 70.5, 15.0), (-22.5, 65.0, 30.0), (-4.0, 85.0, 110.0)]:
    put("body_sheet", x, z, yaw)
loot(-22.0, 0.0, 67.0, "body", "med", "тела под простынями: санитары не успели")
for (x, z) in [(-30.0, 64.0), (2.0, 64.0), (-30.0, 88.0), (2.0, 88.0)]:
    put("flowerbed", x, z, 0.0)
for (x, z, yaw) in [(-22, 86, 90), (-6, 86, -90), (-14, 62, 0)]:
    u("U10_04_bench_stone", x, z, yaw, 1.0, 0.0, True)
wall(-38.2, 70.0, -37.8, 82.0, 0.0, 3.0, "concrete")                          # доска почёта
box(-37.7, 1.8, 76.0, 0.04, 1.6, 10.0, "graffiti", 0.0, False)
put("food_kiosk", -44.0, 90.0, 90.0, 1.0, 0.0, -1, 0.0, True)
u("U05_02_coffee_kiosk", 12.0, 62.0, -90.0, 1.0, 0.0, True)
put("tent", -34.0, 92.0, 20.0)
put("tent", -26.0, 94.0, -30.0)
loot(-30.0, 0.0, 93.0, "backpack", "common", "палатка в сквере")
put("stage", 8.0, 86.0, -90.0, 1.0, 0.0, -1, 0.0, True)
for (x0, z0, x1, z1, n) in [(-48.0, 62.0, -42.0, 80.0, 4), (14.0, 72.0, 18.0, 80.0, 2), (-4.0, 96.0, 10.0, 99.0, 4)]:
    for k in range(n):
        t = (k + 0.5) / n
        put("bush_big", x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, rng.uniform(0, 360), rng.uniform(1.0, 1.25))
# рынок, сухой фонтан


def raised_lawn(x0: float, z0: float, x1: float, z1: float, trees: int, bushes: int, graffiti_side: str = "") -> None:
    """Приподнятый газон в подпорной стенке 0,7 м: деревья и большие кусты на нём (кадр сквера Streets)."""
    for (a0, b0, a1, b1) in [(x0, z0, x1, z0 + 0.3), (x0, z1 - 0.3, x1, z1), (x0, z0, x0 + 0.3, z1), (x1 - 0.3, z0, x1, z1)]:
        wall(a0, b0, a1, b1, 0.0, 0.75, "concrete")
    box((x0 + x1) * 0.5, 0.35, (z0 + z1) * 0.5, x1 - x0 - 0.6, 0.7, z1 - z0 - 0.6, "grass")
    for (cx, cz) in [(x0, z0), (x1, z0), (x0, z1), (x1, z1), ((x0 + x1) * 0.5, z0), ((x0 + x1) * 0.5, z1)]:
        FI["cover"].append([round(cx, 1), round(cz, 1)])
    for _ in range(trees):
        put("tree_round", rng.uniform(x0 + 2, x1 - 2), rng.uniform(z0 + 2, z1 - 2), rng.uniform(0, 360), rng.uniform(0.9, 1.25), 0.7)
    for _ in range(bushes):
        put("bush_big", rng.uniform(x0 + 1.5, x1 - 1.5), rng.uniform(z0 + 1.5, z1 - 1.5), rng.uniform(0, 360), rng.uniform(0.8, 1.2), 0.7)
    if graffiti_side == "w":
        box(x0 - 0.02, 0.4, (z0 + z1) * 0.5, 0.04, 0.5, (z1 - z0) * 0.6, "graffiti", 0.0, False)
    elif graffiti_side == "s":
        box((x0 + x1) * 0.5, 0.4, z1 + 0.02, (x1 - x0) * 0.6, 0.5, 0.04, "graffiti", 0.0, False)


for k in range(5):
    put("stall", -46.0 + k * 3.3, 101.0, 180.0, 1.0, 0.0, -1, 0.0, True)
loot(-42.0, 0.0, 100.0, "register", "common", "рынок в сквере: касса палатки")
# сухой фонтан (фото владельца 05, площадь у вокзала): бортик в бежевой плитке, дно — облезлая голубая краска
for (x0, z0, x1, z1) in [(-16.5, 101.0, -7.5, 101.3), (-16.5, 106.7, -7.5, 107.0), (-16.5, 101.0, -16.2, 107.0), (-7.8, 101.0, -7.5, 107.0)]:
    wall(x0, z0, x1, z1, 0.0, 0.6, "fountain_tile")
surface("fountain_floor", "fountain_floor", -16.2, 101.3, -7.8, 106.7, 0.0, 0.12)
put("puddle", -12.0, 104.0, 0.0, 3.0)
raised_lawn(-22.0, 112.0, -4.0, 138.0, 3, 5, "w")
raised_lawn(2.0, 108.0, 22.0, 128.0, 3, 4, "s")
raised_lawn(14.0, 150.0, 34.0, 176.0, 2, 6, "w")
building("SquareCafe", "кафе «Сквер»", (-38.0, 126.0), (14.0, 9.0), "hall", 1, STORY_RETAIL, 0.0, 0.0, "shop", "kiosk", 0.6, "South")
upper_floor("кафе «Сквер»", -38.0, 126.0, 14.0, 9.0, 0.0, roof=True)
for (x, z) in [(-30.0, 134.0), (-34.0, 135.5), (-41.0, 134.5)]:
    put("cafe_table", x, z, rng.uniform(0, 90))
# детская площадка (кадр Streets: качели, деревянный комплекс с крышей, резиновое покрытие) у забора стройки
surface("playground_sq", "walk", -49.0, 150.0, -24.0, 178.0, 0.0, 0.12)
put("swing", -44.0, 156.0, 90.0)
put("swing", -44.0, 162.0, 90.0)
put("slide", -30.0, 156.0, 0.0)
put("sandbox", -36.0, 172.0, 0.0)
put("seesaw", -28.0, 170.0, 30.0)
put("climber", -40.0, 170.0, 0.0, 1.4)
for (x, z) in [(-33.0, 163.0)]:                                     # деревянный комплекс с крышей-шатром
    for dx in (-1.2, 1.2):
        for dz in (-1.2, 1.2):
            box(x + dx, 1.4, z + dz, 0.14, 2.8, 0.14, "wood")
    box(x, 1.2, z, 2.6, 0.1, 2.6, "wood")
    box(x, 3.3, z, 3.0, 1.0, 3.0, "accent", 45.0, False)
for x in (-47.0, -26.0):
    u("U02_03_bench_tube", x, 176.0, 180.0, 1.0, 0.0, True)
loot(-46.0, 0.0, 176.5, "backpack", "common", "детская площадка: брошенный рюкзак")
# баскетбол: сетка, кольца, разметка
surface("court_bb", "court", -18.0, 152.0, 8.0, 180.0, 0.0, 0.12)
for (x0, z0, x1, z1) in [(-18.0, 152.0, 8.0, 152.0), (-18.0, 180.0, 8.0, 180.0)]:
    for k in range(int((x1 - x0) / 2.5)):
        put("chainlink", x0 + 1.25 + k * 2.5, z0, 90.0)
for x in (-18.0, 8.0):
    for k in range(int(28 / 2.5)):
        if 164.0 < 152.0 + 1.25 + k * 2.5 < 168.0:
            continue
        put("chainlink", x, 152.0 + 1.25 + k * 2.5, 0.0)
put("hoop", -5.0, 154.0, 0.0)
put("hoop", -5.0, 178.0, 180.0)
box(-5.0, 0.13, 166.0, 22.0, 0.01, 0.1, "stripe", 0.0, False)
# у насыпи: гаражи, трансформаторная, туалет, роща — и хаос под упавшими вагонами: раздавленный рынок, ларёк,
# остановка, машина, поваленные фонари и деревья, груз и вещи пассажиров
surface("grove_lawn", "grass", -50.0, 184.0, XS - F, EMB_Z0, 0.0, 0.12)
for _ in range(14):
    x, z = rng.uniform(-48.0, 34.0), rng.uniform(200.0, 222.0)
    if -50.0 < x < -26.0 and 192.0 < z < 200.0 or -18.0 < x < -10.0:
        continue
    put("tree_round" if rng.random() < 0.6 else "bush_big", x, z, rng.uniform(0, 360), rng.uniform(0.85, 1.25))
for i in range(5):
    put("garage", -46.0 + i * 3.4, 196.0, 180.0, 1.0, 0.0, -1, 0.0, True)
put("ktp", 22.0, 196.0, 0.0, 1.0, 0.0, -1, 0.0, True)
for i in range(2):
    u("R02_dumpster", 26.0, 202.0 + i * 3.0, 90.0, 1.0, 0.0, True)
building("WC_Square", "туалет (закрыт)", (-14.0, 190.0), (4.0, 8.0), "mass", 1, 3.0, 0.0, 0.0, "", "", 0.0, "South")
loot(-30.0, 0.0, 194.0, "crate", "common", "открытый гараж")
for k in range(5):
    put("stall", -24.0 + k * 3.2, 233.0 + k * 0.5, 20.0 + k * 8.0, 1.0, 0.0, -1, 4.0 * (k % 2), True)
put("kiosk", 4.0, 241.0, 30.0, 1.0, 0.0, -1, 22.0, True)
put("bus_stop", -36.0, 238.5, 160.0, 1.0, 0.0, -1, 12.0, True)
put("car_wreck", 11.0, 245.0, 100.0, 1.0, 0.0, 2, -18.0, True)
for (x, z, yaw) in [(-4.0, 229.0, 0.0), (0.0, 228.0, 10.0), (4.0, 229.5, -5.0)]:
    u("U02_03_bench_tube", x, z, yaw, 1.0, 0.0, True)
for (kit, x, z, yaw, roll) in [("ornate_lamp", -6.0, 233.0, 30.0, 80.0), ("ornate_lamp", 15.0, 238.0, 120.0, 75.0),
                               ("tree_round", -27.0, 226.0, 60.0, 85.0), ("tree_round", 21.0, 235.0, 200.0, 80.0),
                               ("lamp_park", -42.0, 232.0, 90.0, 70.0)]:
    put(kit, x, z, yaw, 1.0, 0.0, -1, roll, False)
for (kit, x, z) in [("rock_a", -20.0, 240.0), ("rock_b", -8.0, 243.0), ("rock_c", 0.0, 236.0), ("rock_a", -30.0, 246.0),
                    ("suitcase", -16.0, 231.0), ("suitcase", -11.0, 230.0), ("suitcase", -19.0, 229.5), ("bags", -9.0, 232.0),
                    ("boxes", 6.0, 234.0), ("pallets", -24.0, 237.0)]:
    put(kit, x, z, rng.uniform(0, 360), rng.uniform(0.8, 1.2))
for _ in range(30):
    put(rng.choice(["paper", "paper", "paper_ball", "glass_shards", "bottle", "bags"]), rng.uniform(-40.0, 20.0), rng.uniform(224.0, 247.0),
        rng.uniform(0, 360), rng.uniform(0.7, 1.2))
put("body_mar", -8.0, 230.5, 70.0)
put("body_sheet", -18.0, 228.0, 15.0)
loot(-8.0, 0.0, 230.5, "body", "common", "тело мародёра под вагоном")
loot(-14.0, 0.0, 231.0, "suitcase", "common", "вещи пассажиров вагона")
loot(4.0, 0.0, 238.0, "register", "common", "раздавленный ларёк")
FI["stories"].append({"label": "вагоны легли на рынок, ларёк и остановку", "at": [-12.0, 236.0], "height": 6.0})

# ================================================================== внешний угол поворота: ЖК «Вершина» (Москва-Сити) и площадь
STY = [18.0, -88.0, 96.0, -28.0]                                 # стилобат
building("Vershina_Podium", "ЖК «Вершина» · стилобат: офисы, фитнес (закрыт)", ((STY[0] + STY[2]) * 0.5, (STY[1] + STY[3]) * 0.5),
         (STY[2] - STY[0], STY[3] - STY[1]), "mass", 2, 4.5, 0.0, 0.0, "", "", 0.0, "East")
# владелец 2026-10-29: «высотки разной ширины и больше, уменьшать не нужно — как в «Эпицентре» Таркова»: не четыре
# одинаковых квадрата 20–24 м, а плотная группа разной ширины — широкая пластина, толстая квадратная, вытянутая вглубь и
# низкая широкая; каждая не меньше прежней ни по ширине, ни по глубине, ни по этажам (было 22/20/24/20 м, 42/34/48/30 эт.)
flats("Vershina_T1", "ЖК «Вершина», башня 1 — пластина, 44 этажа", (40.0, -72.0), 44, 0, 0.0, (40.0, 24.0), 3.3, False, True, 9.3, "East", 0.0)
flats("Vershina_T2", "ЖК «Вершина», башня 2 — 58 этажей", (80.0, -62.0), 58, 0, 0.0, (30.0, 30.0), 3.3, False, True, 9.3, "East", 0.0)
flats("Vershina_T3", "ЖК «Вершина», башня 3 — 52 этажа", (130.0, -71.0), 52, 0, 0.0, (28.0, 32.0), 3.3, False, True, 0.0, "East", 0.0)
flats("Vershina_T4", "ЖК «Вершина», башня 4 — широкая, 36 этажей", (128.0, -30.0), 36, 0, 0.0, (42.0, 24.0), 3.3, False, True, 0.0, "East", 0.0)
# фасад стилобата к площади: стеклянная стена, вращающиеся и распашные двери, козырьки, волнистый фасад, светящийся парапет
for k in range(9):
    x = STY[0] + 4.5 + k * 8.4
    if abs(x - 40.0) > 5.0 and abs(x - 74.0) > 5.0:             # против входов — входные группы, не витраж
        u("U08_04_curtainwall", x, STY[3] + 0.15, 0.0)
    u("U12_04_lit_parapet", x, STY[3] + 0.3, 0.0, 1.0, 9.0)
revolving_entrance(40.0, STY[3], 0.0)
revolving_entrance(74.0, STY[3], 0.0)
u("U08_02_glass_doors", 57.0, STY[3] + 0.2, 0.0, 1.0, 0.0, True)
u("U08_03_canopy_bracket", 57.0, STY[3] + 0.3, 0.0, 1.0, 3.4)
u("U12_01_wave_facade", 26.0, STY[3] + 0.5, 0.0, 1.0, 5.0)
u("U12_01_wave_facade", 88.0, STY[3] + 0.5, 0.0, 1.0, 5.0)
u("U12_05_triangle_panel", STY[0] - 0.2, -60.0, -90.0, 1.0, 1.5)
u("U12_05_triangle_panel", STY[0] - 0.2, -50.0, -90.0, 1.0, 1.5)
sign("ЖК «Вершина» · четыре башни", 57.0, 11.0, STY[3] + 0.8, 64)
# площадь перед стилобатом до поворота: террасы, пилон, сиденья, светильники, стеклянные навесы, баррикада и пункт эвакуации
surface("plaza_v", "walk", 0.0, -28.0, 110.0, -6.0, 0.0, 0.1)
surface("plaza_v2", "walk", 60.0, -6.0, 110.0, 50.0, 0.0, 0.1)
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
# владелец 2026-10-24: «пункт эвакуации возле «Вершины» — до самого края карты, несколько больших крытых армейских палаток»
surface("evac_field", "walk", 110.0, -16.0, 158.0, 58.0, 0.0, 0.06)
for (x, z, yaw, sc) in [(114.0, 2.0, 0.0, 1.0), (126.0, 2.0, 0.0, 1.0), (138.0, 2.0, 0.0, 1.0), (150.0, 2.0, 0.0, 1.0),
                        (118.0, 30.0, 0.0, 1.25), (134.0, 30.0, 0.0, 1.25), (150.0, 30.0, 0.0, 1.25), (132.0, 50.0, 90.0, 1.4)]:
    put("army_tent", x, z, yaw, sc, 0.0, -1, 0.0, True)
for (x, z, kind, tier, note) in [(114.0, 0.0, "med", "med", "палатка медпункта"), (126.0, 4.0, "crate", "common", "вещи эвакуированных"),
                                 (138.0, 0.0, "suitcase", "common", "чемоданы"), (150.0, 4.0, "weapon", "weapon", "оружейка ЧВК"),
                                 (118.0, 28.0, "med", "med", "госпиталь"), (134.0, 32.0, "crate", "good", "склад гуманитарки"),
                                 (150.0, 30.0, "body", "weapon", "тело бойца ЧВК"), (132.0, 50.0, "safe", "good", "штаб: сейф с документами")]:
    loot(x, 0.0, z, kind, tier, note)
put("truck", 104.0, 47.0, 30.0, 1.0, 0.0, -1, 0.0, True)
put("truck", 155.5, 16.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("armored_truck", 113.0, 49.0, 75.0, 1.0, 0.0, -1, 0.0, True)
for (x, z) in [(144.0, 16.0), (108.0, 16.0)]:
    put("pallets", x, z, 15.0)
    put("pallets", x + 1.4, z + 0.3, -10.0)
for (x, z) in [(120.0, 16.0), (146.0, 44.0)]:
    put("mast", x, z, 0.0)
for (x, z) in [(156.0, -10.0), (102.0, -12.0)]:
    put("sandbag_post", x, z, 180.0, 1.0, 0.0, -1, 0.0, True)
for k in range(6):
    u("U09_01_hedgehog", 112.0 + k * 7.0, -14.0, rng.uniform(0, 90), 1.0, 0.0, True)
for k in range(6):
    put("barrel", 140.0 + (k % 3) * 0.7, 46.0 + (k // 3) * 0.7, 0.0)
put("flagpole", 124.0, 16.0, 0.0, 1.0, 0.0, -1, 0.0, True)
sign("пункт эвакуации · штаб ЧВК", 132.0, 6.0, 50.0, 44)
FI["stories"].append({"label": "армейские палатки: эвакуация жителей, потом штаб ЧВК", "at": [132.0, 20.0], "height": 5.0})

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
# владелец 2026-10-24: «по правой стороне карта просматривается насквозь — пусть обзору что-то мешает через 50–90 м»:
# контейнеры и ларьки в проезде парковки, гаражи между корпусом 3 и «Меридианом», гаражи вдоль двора корпуса 3
put("container40_open", 86.5, 140.0, 0.0, 1.0, 0.0, -1, 0.0, True)        # открытые — только с лутом внутри
put("container40", 86.6, 139.6, 1.5, 1.0, 2.62, -1, 0.0, False)
put("container20", 86.5, 200.0, 0.0, 1.0, 0.0, -1, 0.0, True)
put("container20", 86.4, 200.3, -2.0, 1.0, 2.62, -1, 0.0, False)
for z in (92.0, 176.0, 222.0):
    put("kiosk", 86.5, z, 90.0, 1.0, 0.0, -1, 0.0, True)
for i in range(8):
    put("garage_open" if i == 4 else "garage", 128.0 + i * 3.4, 158.0, 0.0, 1.0, 0.0, -1, 0.0, True)
for i in range(10):
    put("garage", 154.0, 78.0 + i * 3.4, -90.0, 1.0, 0.0, -1, 0.0, True)
put("ktp", 106.0, 160.0, 0.0, 1.0, 0.0, -1, 0.0, True)
loot(141.6, 0.0, 157.0, "crate", "common", "гараж открыт")
loot(86.5, 0.0, 145.5, "crate", "common", "контейнер на парковке")
u("U08_02_glass_doors", 120.0, 172.8, 180.0, 1.0, 0.0, True)
# ---- насыпь железной дороги на южном краю и тоннель под ней — выход в следующую локацию (владелец 2026-10-24:
# «выход на месте тупика на юге, там начинается тоннель в следующую локацию, сверху — железная дорога с упавшим по
# склону составом, некоторые вагоны упали даже в сквер»). Откос 10 м под 31°, верх на 6 м, путь в два направления.
TUN_X0, TUN_X1 = XS - 10.5, XS + 10.5
for (x0, x1) in [(-152.0, TUN_X0), (TUN_X1, 160.0)]:
    plan["ramps"].append({"x0": x0, "x1": x1, "z0": EMB_Z0, "z1": EMB_Z1, "y0": 0.0, "y1": EMB_H, "mat": "ground", "fill": True})
    wall(x0, EMB_Z1, x1, RAIL_Z1, 0.0, EMB_H, "ground")
plan["ramps"].append({"x0": -152.0, "x1": 160.0, "z0": RAIL_Z1, "z1": RAIL_Z1 + 10.0, "y0": EMB_H, "y1": 0.0, "mat": "ground", "fill": True})
slab("tunnel_roof", [TUN_X0, EMB_Z1, TUN_X1, RAIL_Z1], EMB_H, 1.0, "concrete")
for x in (TUN_X0 - 0.6, TUN_X1 + 0.6):
    box(x, 3.4, EMB_Z1 - 0.4, 1.2, 6.8, 0.8, "concrete")
    box(x, 3.4, RAIL_Z1 + 0.4, 1.2, 6.8, 0.8, "concrete")
box(XS, 5.6, EMB_Z1 - 0.4, TUN_X1 - TUN_X0 + 2.4, 1.6, 0.8, "concrete")
box(XS, 5.6, RAIL_Z1 + 0.4, TUN_X1 - TUN_X0 + 2.4, 1.6, 0.8, "concrete")
sign("тоннель · выезд из района", XS, 7.4, EMB_Z1 - 1.0, 56)
surface("tunnel_road", "road", XS - RH, ZS_END, XS + RH, RAIL_Z1 + 4.0)
box(XS, 3.0, RAIL_Z1 + 4.2, TUN_X1 - TUN_X0, 6.0, 0.4, "dark")
for z in range(262, int(RAIL_Z1), 7):
    plan["lamps"].append([XS, 4.6, float(z), 0.35, 9.0])
# шесть путей (владелец 2026-10-25: «четыре или шесть путей»): балластная призма, шпалы и рельсы звеньями по 3 м
for tz in TRACKS:
    box(4.0, EMB_H + 0.15, tz, 312.0, 0.3, 3.6, "rock", 0.0, True)
    x = -150.5
    while x < 158.0:
        put("track_3m", x, tz, 90.0, 1.0, EMB_H + 0.3)
        x += 3.0
# контактная сеть: жёсткие поперечины на двух мачтах через 60 м над всеми путями, над каждым путём несущий трос и
# контактный провод (6 м над рельсом), фидерные провода по верху мачт; на путях у платформы мачта — на платформе
RAIL_TOP = EMB_H + 0.62
MAST_N, MAST_S = TRACKS[0] - 2.6, TRACKS[-1] + 2.6
# поперечина — своя модель (tools/prospekt_city/catenary.py, PC05_CROSSSPAN): мачты на фундаментах, ригель, гирлянды,
# фиксирующий трос, кронштейн фидеров над южной мачтой; начало модели — середина пролёта на головке рельса, пролёт
# 25,7 м — мачты в 2,6 м от крайних путей; коллизия — мачты (solids в индексе)
for x in range(-146, 160, 60):
    put("m:PC05_CROSSSPAN", float(x), (MAST_N + MAST_S) * 0.5, 0.0, 1.0, RAIL_TOP)
for tz in TRACKS:
    box(4.0, RAIL_TOP + 6.0, tz, 312.0, 0.03, 0.03, "dark", 0.0, False)               # контактный провод
    box(4.0, RAIL_TOP + 7.3, tz, 312.0, 0.03, 0.03, "dark", 0.0, False)               # несущий трос
for dz in (-0.3, 0.3):
    box(4.0, RAIL_TOP + 9.35, MAST_S + dz, 312.0, 0.035, 0.035, "dark", 0.0, False)   # фидеры — на седлах изоляторов
# лестницы на насыпь: бетонные марши по откосу с перилами — к путям не только с платформы вокзала
for sx in (-66.0, -2.0, 100.0):                                # мимо платформы вокзала (она выше путей)
    stair((sx, 0.05, EMB_Z0), (sx, EMB_H + 0.05, EMB_Z1), 1.8)            # марш по откосу, 31°
    for wx in (sx - 1.05, sx + 0.9):
        beam((wx, 1.0, EMB_Z0), (wx, EMB_H + 1.0, EMB_Z1), 0.05, 0.05, "steel")
    sign("к путям", sx, 2.6, EMB_Z0 - 2.5, 30)
FI["stories"].append({"label": "шесть путей, контактная сеть на жёстких поперечинах", "at": [100.0, TRACKS[2]], "height": EMB_H + 9.0})
# очередь машин в тоннель по западной полосе: восточная свободна к выходу
put("bus_city", XS - 4.8, 268.0, 182.0, 1.0, 0.0, 8, 0.0, True)
put("car", XS - 5.0, 257.0, 176.0, 1.0, 0.0, 2, 0.0, True)
put("van", XS - 4.6, 250.5, 172.0, 1.0, 0.0, 9, 0.0, True)
for (x, z) in [(XS + 3.0, 246.0), (XS + 6.0, 247.0)]:
    put("water_barrier", x, z, 80.0, 1.0, 0.0, -1, 0.0, True)
loot(XS - 1.5, 0.0, 262.0, "body", "good", "тело ЧВК у въезда в тоннель")
# состав: восточная часть ещё на путях, над порталом вагон повис, западная — по откосу и в сквер
for (kit, x, z, yaw, dy, roll) in [("loco_tem", 150.0, 264.0, 88.0, EMB_H, 0.0), ("wagon_box", 132.5, 264.3, 91.0, EMB_H, 0.0),
                                   ("wagon_box", 117.5, 264.8, 93.0, EMB_H, 6.0), ("wagon_box", 102.0, 265.5, 96.0, EMB_H - 0.1, 14.0),
                                   ("wagon_box", 87.0, 266.0, 99.0, EMB_H - 0.3, 25.0), ("wagon_box", 72.0, 263.0, 70.0, EMB_H - 0.2, 18.0),
                                   ("wagon_box", XS, 260.5, 78.0, EMB_H, 32.0), ("wagon_box", 34.0, 258.5, 62.0, EMB_H - 1.2, 40.0),
                                   ("wagon_box", 20.0, 252.0, 45.0, 2.6, 65.0), ("wagon_box", 6.0, 240.0, 30.0, 0.6, 84.0),
                                   ("wagon_pass", -14.0, 236.0, 110.0, 0.9, 82.0), ("wagon_box", -34.0, 242.0, 70.0, 0.7, 97.0)]:
    put(kit, x, z, yaw, 1.0, dy, -1, roll, True)
for (kit, x, z, yaw, roll) in [("container20", -2.0, 227.0, 35.0, 90.0), ("container20", 12.0, 231.0, 70.0, 0.0), ("pallets", -24.0, 229.0, 20.0, 0.0),
                               ("pallets", -22.5, 230.0, 60.0, 0.0), ("boxes", 2.0, 233.0, 0.0, 0.0), ("log_pile", -40.0, 234.0, 30.0, 0.0)]:
    put(kit, x, z, yaw, 1.0, 0.0, -1, roll, kit in ("container20", "pallets"))
for (x, z, kind, tier, note) in [(8.0, 236.0, "crate", "good", "груз из вагона"), (-12.0, 232.0, "suitcase", "common", "пассажирский вагон"),
                                 (-30.0, 238.0, "crate", "common", "груз из вагона"), (14.0, 229.0, "crate", "good", "контейнер вскрыт"),
                                 (-6.0, 241.0, "body", "common", "тело мародёра у вагона")]:
    loot(x, 0.0, z, kind, tier, note)
FI["stories"].append({"label": "состав сошёл с насыпи: вагоны в сквере", "at": [0.0, 236.0], "height": 6.0})
# выезд к тоннелю с востока: брошенный автобус, фургон, красно-белые блоки — укрытия на подходе от южного появления
put("bus_city", 128.0, 236.0, 18.0, 1.0, 0.0, 9, 0.0, True)
put("van", 101.0, 240.0, -32.0, 1.0, 0.0, 6, 0.0, True)
for k in range(3):
    put("jersey_rw", 112.0 + k * 3.2, 228.0 - k * 0.9, 74.0, 1.0, 0.0, -1, 0.0, True)
put("ad_column", 146.0, 226.0, 0.0, 1.0, 0.0, -1, 0.0, True)
for (x, z, w, d, fl) in [(40, 300, 30, 18, 20), (90, 302, 24, 20, 26), (140, 300, 26, 18, 16)]:
    building("Outside_S%d" % x, "", (x, z + 8.0), (w, d), "mass", fl, 3.0, 0.0, 0.0, "", "", 0.0, "Outside")
for (x, z, w, d, fl) in [(196, -60, 20, 26, 22), (198, 40, 18, 24, 18), (196, 150, 22, 26, 25), (-20, -150, 24, 18, 21), (60, -152, 30, 20, 16)]:
    building("Outside_E%d_%d" % (abs(x), abs(z)), "", (x, z), (w, d), "mass", fl, 3.0, 0.0, 0.0, "", "", 0.0, "Outside")

# ================================================================== южное плечо, запад: минимаркет, стройка
building("Minimarket2", "продукты «24 часа»", (31.0, 128.0), (16.0, 10.0), "hall", 1, STORY_RETAIL, 90.0, 0.0, "shop", "grocery", 0.5, "South")
upper_floor("продукты «24 часа»", 31.0, 128.0, 16.0, 10.0, 90.0, roof=True)
u("U05_03_warning_a", 37.5, 121.0, 90.0)
u("R05_kiosk", 33.0, 112.0, 90.0, 1.0, 0.0, True)
# улица южного плеча: контейнеры поперёк западной полосы, автобус, ларьки и остановка — обзор вдоль улицы рвётся
put("container40", XS - 4.5, 168.0, 88.0, 1.0, 0.0, -1, 0.0, True)
put("container20", XS + 5.0, 178.0, 78.0, 1.0, 0.0, -1, 0.0, True)
for k in range(3):
    put("jersey_rw", XS - 1.0 + k * 0.4, 172.0 + k * 3.1, 2.0, 1.0, 0.0, -1, 0.0, True)
put("bus_city", XS + 3.5, 210.0, 162.0, 1.0, 0.0, 8, 0.0, True)
for z in (164.0, 226.0):
    put("kiosk", XS - F + 2.2, z, 90.0, 1.0, 0.0, -1, 0.0, True)
put("bus_stop", XS + F - 2.8, 186.0, -90.0, 1.0, 0.0, -1, 0.0, True)
loot(XS - 4.5, 0.0, 172.5, "body", "common", "тело у контейнера")
loot(XS + 3.5, 0.0, 214.0, "suitcase", "common", "автобус: багаж")

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
                    (-26, -12.0, 20), (82, 22, 25), (XS, 240.0, 25), (-20, 100, 20), (-176, 78, 15), (-98, -97, 20)]:
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

# ================================================================== перебивки обзора (владелец 2026-10-24, п. 7)
# Замер tools/prospekt_ld_plan.py: лучи на высоте глаз длиннее 90 м — красным на docs/design/prospekt_level_design.png.
# Каждые 50–90 м по линии взгляда — что-то выше роста: сцена, рыночные палатки, стенки кустов, ларьки, гаражи,
# трансформаторные, контейнеры, грузовики. Машины, блоки и мешки взгляд стоя не закрывают — они укрытия, не перебивки.
# сквер у поворота пересобран за домом на повороте (раздел «дом на повороте и сквер»)
# поворот: автобус поперёк внешней полосы, ларьки на внешнем тротуаре
x, z = curve_point(0.32, 5.0)
put("bus_city", x, z, 60.0, 1.0, 0.0, 9, 0.0, True)
for phi in (0.75, 1.35):
    x, z = curve_point(phi, F - 2.2)
    put("kiosk", x, z, -math.degrees(phi), 1.0, 0.0, -1, 0.0, True)
# площадь «Вершины»: второй пост ЧВК из контейнеров перед эвакуацией, ларьки у стилобата, грузовики
for (x, z, yaw, dy) in [(48.0, 26.0, 20.0, 0.0), (48.2, 26.1, 21.0, 2.62), (40.0, 40.0, 70.0, 0.0)]:
    put("container40", x, z, yaw, 1.0, dy, -1, 0.0, dy == 0.0)
put("sandbag_post", 54.0, 34.0, 200.0, 1.0, 0.0, -1, 0.0, True)
loot(55.0, 0.0, 33.0, "weapon", "weapon", "пост ЧВК у контейнеров")
for (x, z) in [(30.0, -14.0), (90.0, -13.0)]:
    put("food_kiosk", x, z, 0.0, 1.0, 0.0, -1, 0.0, True)
put("truck", 62.0, 44.0, 120.0, 1.0, 0.0, -1, 0.0, True)
put("truck", 20.0, 10.0, 35.0, 1.0, 0.0, 11, 0.0, True)
# двор ЖК на севере: гаражи, трансформаторные, контейнеры, машина — вперемешку то у забора, то у домов;
# пары гаражей — с шагом 3,4 (ширина модели PC02_GARAGE, стены соседей встык)
for (kit, x, z, yaw) in [("ktp_open", -156.0, -90.0, 0.0), ("container20", -82.0, -106.0, 0.0), ("garage", -60.0, -89.5, 0.0),
                         ("garage", -56.6, -89.5, 0.0), ("container20", -28.0, -106.0, 0.0), ("truck", 2.0, -91.0, 5.0),
                         ("garage", 32.0, -106.0, 0.0), ("garage", 35.4, -106.0, 0.0), ("ktp", 62.0, -91.0, 0.0),
                         ("container20", 100.0, -112.0, 0.0), ("garage", 140.0, -91.0, 0.0), ("garage", 143.4, -91.0, 0.0),
                         ("kiosk", -190.0, -112.0, 90.0)]:
    put(kit, x, z, yaw, 1.0, 0.0, -1, 0.0, True)
# проспект: ларьки на тротуарах, контейнер на южной полосе
for (x, z, yaw) in [(-90.0, -13.9, 180.0), (-45.0, -13.9, 180.0), (-135.0, 13.9, 0.0), (-85.0, 13.9, 0.0), (-35.0, 13.9, 0.0)]:
    put("kiosk", x, z, yaw, 1.0, 0.0, -1, 0.0, True)
# фильтр ЧВК поперёк проспекта: контейнеры через обе проезжие части, проход по тротуарам
put("container40", -106.0, -2.6, 0.0, 1.0, 0.0, -1, 0.0, True)
put("container20", -105.5, 7.5, 2.0, 1.0, 0.0, -1, 0.0, True)
put("sandbags", -108.5, -9.6, 0.0, 1.0, 0.0, -1, 0.0, True)
loot(-104.0, 0.0, 9.5, "body", "weapon", "фильтр ЧВК: тело у контейнера")
# площадь «Вершины» и поле эвакуации: грузовик, полевая кухня, генераторный контейнер — поперёк длинных линий
put("truck", 96.0, -9.0, 0.0, 1.0, 0.0, 11, 0.0, True)
building("MetroPavilion", "вход в метро «Проспект» (закрыт)", (100.0, 26.0), (12.0, 18.0), "mass", 1, 4.5, 0.0, 0.0, "", "", 0.0, "East")
put("container20", 142.0, 15.0, 0.0, 1.0, 0.0, -1, 0.0, True)
# линия z ≈ 105 (двор дома 7 → разгрузка → сквер → парковка корпуса 3) и западный край сквера вдоль служебного проезда
for (kit, x, z, yaw) in [("garage", -190.0, 103.0, 0.0), ("garage", -186.6, 103.0, 0.0), ("container20_open", -118.0, 102.0, 0.0),
                         ("kiosk", 25.0, 104.0, 0.0), ("container20", 86.5, 108.0, 0.0), ("booth", -49.0, 60.0, 0.0),
                         ("kiosk", -47.5, 145.0, 90.0), ("container20", -47.0, 214.0, 0.0), ("kiosk", -24.0, 186.0, 90.0)]:
    put(kit, x, z, yaw, 1.0, 0.0, -1, 0.0, True)
loot(-118.0, 0.0, 103.6, "crate", "common", "контейнер на разгрузке")    # двери — на юг, к забору: с севера фура
# южное плечо и середина сквера: грузовик на восточной полосе, кусты вдоль тротуара, живые изгороди у баскетбола,
# ларьки на внутреннем тротуаре поворота
put("truck", XS + 5.2, 136.0, 172.0, 1.0, 0.0, 6, 0.0, True)
put("paz", XS - 5.0, 232.0, 4.0, 1.0, 0.0, 8, 0.0, True)
for z in (112.0, 145.0, 190.0, 238.0):
    put("bush_big", XS - F - 1.4, z, rng.uniform(0, 360), 1.15)
# у западной изгороди — проход аллеи z ≈ 146 (по ней идут маршруты пролога и с юга к стройке)
for (x0, z0, x1, z1) in [(-18.0, 149.0, -8.0, 149.0), (-2.0, 183.0, 8.0, 183.0), (-22.0, 139.6, -22.0, 144.0),
                         (-22.0, 148.4, -22.0, 152.8), (10.0, 186.0, 10.0, 192.0), (-40.0, 182.0, -30.0, 182.0)]:
    n = max(1, round(math.hypot(x1 - x0, z1 - z0) / 5.0))
    for k in range(n):
        t = (k + 0.5) / n
        put("hedge", x0 + (x1 - x0) * t, z0 + (z1 - z0) * t, 90.0 if z0 == z1 else 0.0, 1.0, 0.0, -1, 0.0, True)
for _ in range(2 * 17):
    rng.random()                     # прежние 17 кустов брали по два случайных числа — дальше по карте ничего не сдвигается
for phi in (0.45, 1.1):
    x, z = curve_point(phi, -(F - 2.2))
    put("kiosk", x, z, 180.0 - math.degrees(phi), 1.0, 0.0, -1, 0.0, True)
# южное плечо: ларьки на тротуарах
for (x, z) in [(XS - F + 2.2, 100.0), (XS + F - 2.2, 130.0), (XS + F - 2.2, 202.0)]:
    put("kiosk", x, z, 90.0, 1.0, 0.0, -1, 0.0, True)

# ================================================================== периметр района (владелец 2026-10-25, п. 3)
# «По периметру карты должны стоять какие-то логичные преграды для игрока, а не просто невидимая стена». По вводной
# район «обнесли забором и поставили кордоны»: вдоль границы — бетонные плиты ПО-2 со спиралью колючки, вышки ЧВК,
# по верху насыпи — сетка полосы отвода; у стройки граница — её синий профнастил. Выходы — проломы и проходы в заборе
# (двор ЖК, стройка, пути на запад), тоннель — под насыпью. За забором — город: дома, склады, гаражи.
# Лицо плиты ПО-2 (пирамиды, +X модели) — внутрь района, к игроку: снаружи он забор не видит, а гладкая тыльная
# сторона — пустая серая стена (владелец 2026-10-29: «реши сам»). inside — с какой стороны линии район: +1 — к +X / +Z.
def fence_yaw(axis: str, inside: float) -> float:
    if axis == "x":
        return -90.0 if inside > 0 else 90.0
    return 0.0 if inside > 0 else 180.0


def fence_run(axis: str, c: float, a0: float, a1: float, kit: str = "district_fence", gaps=(), dy: float = 0.0,
              step: float = 2.5, inside: float = 0.0) -> None:
    yaw = fence_yaw(axis, inside) if inside != 0.0 else (90.0 if axis == "x" else 0.0)
    a = a0 + step * 0.5
    while a < a1:
        if all(abs(a - g[0]) > g[1] * 0.5 + step * 0.5 for g in gaps):
            if axis == "x":
                put(kit, a, c, yaw, 1.0, dy, -1, 0.0, False)
            else:
                put(kit, c, a, yaw, 1.0, dy, -1, 0.0, False)
        a += step


fence_run("x", YARD_Z0 + 0.5, XW, 160.0, gaps=[(-145.0, 5.0)], inside=1.0)
fence_run("z", 159.5, YARD_Z0, EMB_Z0, inside=-1.0)
fence_run("z", 159.5, EMB_Z1, RAIL_Z1, dy=EMB_H, inside=-1.0)
fence_run("x", RAIL_Z1 - 0.5, -152.0, 160.0, "rail_fence", dy=EMB_H, step=3.0)
fence_run("z", -151.5, SITE[3], EMB_Z0, inside=1.0)
fence_run("z", -151.5, EMB_Z1, RAIL_Z1, gaps=[(TRACKS[1], 10.0)], dy=EMB_H, inside=1.0)
fence_run("x", 111.5, XW, -152.0, inside=-1.0)
fence_run("z", XW + 0.5, YARD_Z0, -17.5, inside=1.0)
fence_run("z", XW + 0.5, 17.5, 112.0, inside=1.0)
for zz in (-17.5, 17.5):
    fence_run("x", zz, XW + 0.5, XC - 0.2, inside=-1.0 if zz < 0 else 1.0)
# выход «Дворами к насыпи» — пролом в заборе района (три места плит, 7,5 м): плиту у запада проломили тараном изнутри
# (дыра 1,3 × 1,95 м, обломки наружу), восточную повалили наружу — лежит рельефом вверх; посередине плиты нет — проход
# 2,5 м остаётся чистым для группы и чужих отрядов. Других проломов в заборе нет: пролом читается как выход.
put("po2_breach", -146.75, YARD_Z0 + 0.5, fence_yaw("x", 1.0), 1.0, 0.0, -1, 0.0, False)
put("po2_fallen", -141.75, YARD_Z0 + 0.5, fence_yaw("x", 1.0), 1.0, 0.0, -1, 0.0, False)
for (x, z, yaw) in [(-214.0, YARD_Z0 + 4.0, 45.0), (-214.0, 108.0, 135.0), (20.0, YARD_Z0 + 4.0, 0.0), (90.0, YARD_Z0 + 4.0, 0.0),
                    (156.0, YARD_Z0 + 4.0, -45.0), (156.0, 60.0, -90.0), (156.0, 196.0, -90.0), (-148.0, 205.0, 90.0)]:
    put("watchtower", x, z, yaw, 1.0, 0.0, -1, 0.0, True)
for (text, x, z) in [("ЗАПРЕТНАЯ ЗОНА · ОХРАНА ЧВК", 20.0, YARD_Z0 + 1.2), ("ЗАПРЕТНАЯ ЗОНА · ОГОНЬ БЕЗ ПРЕДУПРЕЖДЕНИЯ", 158.8, 120.0),
                     ("ЗАПРЕТНАЯ ЗОНА", -180.0, 110.8), ("ЗАПРЕТНАЯ ЗОНА · ОХРАНА ЧВК", -150.8, 225.0)]:
    sign(text, x, 3.6, z, 34)
sign("пути на запад · проход по насыпи", -150.0, EMB_H + 3.0, TRACKS[1], 34)
# город за забором: дома, склады, гаражи — чтобы за границей было «как было», а не голая земля
# N2 — башня 38 эт. за ЖК «Панорама», S4 — 50 эт. в конце южного плеча за тоннелем (силуэт города над стенами улиц)
for (bid, x, z, w, d, fl, st) in [("N1", -200.0, -138.0, 30.0, 14.0, 9, 3.0), ("N2", -140.0, -144.0, 32.0, 22.0, 38, 3.0),
                                  ("S4", 80.0, 332.0, 26.0, 26.0, 50, 3.0),
                                  ("N3", -80.0, -138.0, 24.0, 16.0, 5, 3.2), ("N4", 110.0, -140.0, 36.0, 16.0, 14, 3.0),
                                  ("E1", 186.0, -100.0, 16.0, 30.0, 6, 3.2), ("E2", 184.0, 100.0, 14.0, 40.0, 2, 4.5),
                                  ("E3", 188.0, 240.0, 20.0, 36.0, 10, 3.0), ("S1", -20.0, 306.0, 40.0, 14.0, 9, 3.0),
                                  ("S2", -100.0, 304.0, 30.0, 16.0, 3, 4.5), ("S3", -150.0, 306.0, 24.0, 16.0, 12, 3.0),
                                  ("W1", -180.0, 150.0, 30.0, 50.0, 2, 5.0), ("W2", -182.0, 236.0, 26.0, 40.0, 3, 4.5),
                                  ("W3", -238.0, 140.0, 20.0, 30.0, 14, 3.0), ("W4", -236.0, -130.0, 22.0, 16.0, 16, 3.0)]:
    building("Outside_City_" + bid, "", (x, z), (w, d), "mass", fl, st, 0.0, 0.0, "", "", 0.0, "Outside")
for i in range(5):
    put("garage", -170.0 + i * 3.4, 186.0, 0.0, 1.0, 0.0, -1, 0.0, False)
for i in range(6):
    put("garage", 174.0, -40.0 + i * 3.4, 90.0, 1.0, 0.0, -1, 0.0, False)

# ================================================================== провода в городе (владелец 2026-10-25)
# «В черте города тоже должны быть электрические столбы, как обычно в городах бывает». По проспекту — троллейбусная
# линия: стальные опоры по краю тротуаров через 32 м, поперечные растяжки, над правыми полосами по два контактных
# провода в каждую сторону. Во дворах, вдоль хозяйственных проездов, у гаражей и стройки — ЛЭП 0,4 кВ на
# железобетонных опорах через 30 м, четыре провода с провисом.
def wire(a: tuple, b: tuple, sag: float, w: float = 0.025) -> None:
    """Провод с провисом: четыре отрезка по параболе."""
    pts = []
    for k in range(5):
        t = k / 4.0
        pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t - sag * 4.0 * t * (1.0 - t), a[2] + (b[2] - a[2]) * t))
    for k in range(4):
        beam(pts[k], pts[k + 1], w, w, "dark")


TROLLEY_D = RH + 0.9                                             # опоры у бордюра
TROLLEY_H = 5.9                                                  # высота контактных проводов
trolley_pts = along(32.0, 0.0, 12.0, busy)
for (x, z, h) in trolley_pts:
    rad = math.radians(h)
    lx, lz = math.cos(rad), -math.sin(rad)                       # влево от курса
    for side in (1.0, -1.0):
        px, pz = x + lx * TROLLEY_D * side, z + lz * TROLLEY_D * side
        put("pole_trolley", px, pz, h + (90.0 if side < 0 else -90.0), 1.0, 0.0, -1, 0.0, True)
    wire((x + lx * TROLLEY_D, 7.4, z + lz * TROLLEY_D), (x - lx * TROLLEY_D, 7.4, z - lz * TROLLEY_D), 0.5, 0.02)
for k in range(len(trolley_pts) - 1):
    (x0, z0, h0), (x1, z1, h1) = trolley_pts[k], trolley_pts[k + 1]
    if math.hypot(x1 - x0, z1 - z0) > 40.0:
        continue                                                 # разрыв у перехода, кордона, тупика — провода не тянем
    r0, r1 = math.radians(h0), math.radians(h1)
    for d in (6.1, 6.7, -6.1, -6.7):
        a = (x0 + math.cos(r0) * d, TROLLEY_H, z0 - math.sin(r0) * d)
        b = (x1 + math.cos(r1) * d, TROLLEY_H, z1 - math.sin(r1) * d)
        wire(a, b, 0.25, 0.02)
POLE_LINES = [
    # (точки линии, шаг) — опоры ставятся по ломаной через шаг, провода тянутся между соседними
    ([(-205.0, YARD_Z0 + 1.6), (-48.0, YARD_Z0 + 1.6)], 30.0),           # хозяйственный проезд двора вдоль забора
    ([(-61.5, F + 4.0), (-61.5, 108.0)], 30.0),                          # служебный проезд у «Яруса»
    ([(-208.0, 66.0), (-208.0, 108.0), (-170.0, 108.0)], 28.0),          # двор дома 7, гаражи
    ([(157.0, 66.0), (157.0, 156.0), (126.0, 156.0)], 30.0),             # двор корпуса 3
    ([(-150.5, 116.0), (-150.5, 198.0)], 27.0),                          # стройка: временное питание
    ([(-48.5, 140.0), (-48.5, 222.0)], 27.0),                            # сквер у гаражей, к трансформаторной
    ([(110.0, -118.0), (155.0, -118.0), (155.0, -70.0)], 30.0),          # за «Вершиной»
]
for (line, step) in POLE_LINES:
    poles = []
    for k in range(len(line) - 1):
        (ax, az), (bx, bz) = line[k], line[k + 1]
        length = math.hypot(bx - ax, bz - az)
        n = max(1, int(round(length / step)))
        for i in range(n + (1 if k == len(line) - 2 else 0)):
            t = i / n
            poles.append((ax + (bx - ax) * t, az + (bz - az) * t, math.degrees(math.atan2(bx - ax, bz - az))))
    for (x, z, h) in poles:
        put("pole_conc", x, z, h + 90.0, 1.0, 0.0, -1, 0.0, True)
    for k in range(len(poles) - 1):
        (x0, z0, h0), (x1, z1, _h1) = poles[k], poles[k + 1]
        r = math.radians(h0 + 90.0)
        for off in (-0.7, -0.25, 0.25, 0.7):
            ox, oz = math.sin(r) * off, math.cos(r) * off
            wire((x0 + ox, 9.15, z0 + oz), (x1 + ox, 9.15, z1 + oz), 0.45)

# ================================================================== места лута на улицах и в сценках
# Владелец 2026-10-24, п. 8: «предметы — и в контейнерах (ящики, рюкзаки, чемоданы, трупы мародёров и ЧВК, машины), и
# свободно». Ценность: common — бытовое, med — медицина, good — ценное, weapon — оружие и патроны. В залах StudyBuilding
# свои места лута (полки, кассы, шкафы) — здесь улица, машины, тела, посты, крыши; маркеры видны на блокауте и на плане.
STREET_LOOT = [
    # кордон и пункт эвакуации у него
    (-197.0, -12.0, "med", "med", "палатка у кордона: аптечка"), (-196.0, -10.6, "suitcase", "common", "чемоданы эвакуации"),
    (-191.0, -7.4, "car", "med", "скорая: укладка"), (-205.5, 9.5, "weapon", "weapon", "пост ЧВК: ящик с патронами"),
    (-199.0, -12.4, "car", "weapon", "БТР ЧВК: десантный отсек"),
    # проспект: остановка, переход, перевёрнутый автобус, авария, пожарная, затор
    (-192.0, 11.0, "backpack", "common", "остановка: рюкзак"), (-155.0, 4.0, "loose", "common", "переход: ларёк"),
    (-142.0, 2.5, "suitcase", "common", "жёлтый автобус: багаж"), (-73.0, -6.8, "suitcase", "common", "перевёрнутый автобус"),
    (-80.0, -1.0, "body", "common", "тело у перевёрнутого автобуса"), (-63.5, 2.6, "car", "common", "такси: багажник"),
    (-58.8, 3.8, "car", "common", "маршрутка: сумки пассажиров"), (-91.0, -8.2, "car", "common", "пожарная: инструмент"),
    (-46.0, -3.0, "car", "common", "затор: багажник"), (-34.0, -8.0, "loose", "common", "затор: на асфальте"),
    # поворот, площадь «Вершины», оцепление, колонна
    (46.0, -16.0, "car", "weapon", "полицейская: дробовик в салоне"), (62.0, -11.0, "car", "weapon", "автозак: оружейный ящик"),
    (40.0, -6.0, "body", "weapon", "тело бойца у баррикады"), (70.0, 10.5, "crate", "weapon", "БТР колонны: ящик с патронами"),
    (56.0, -20.0, "loose", "common", "оцепление: брошенное"), (84.0, 22.0, "med", "med", "медпалатка эвакуации"),
    # сквер у памятника
    (-44.0, 92.0, "register", "common", "фудтрак: касса"), (10.4, 62.0, "loose", "common", "кофейный ларёк"),
    (-6.0, 76.0, "backpack", "med", "рюкзак у памятника"),
    # южное плечо: пост ДПС, дорожные работы, корпус 3, «Меридиан», тоннель
    (XS - 6.0, 107.4, "car", "weapon", "пост ДПС: автомат в машине"), (XS + 5.8, 121.0, "car", "common", "ПАЗ полиции"),
    (XS - 5.0, 100.0, "car", "common", "самосвал дорожников"), (80.0, 104.0, "car", "common", "парковка корпуса 3: багажник"),
    (93.0, 118.0, "car", "common", "парковка корпуса 3: салон"), (86.5, 94.6, "register", "common", "ларёк на парковке"),
    (150.0, 131.0, "loose", "common", "у мусорных баков"), (92.0, 174.0, "cabinet", "common", "будка охраны «Меридиана»"),
    (XS - 4.8, 263.0, "suitcase", "common", "автобус в тоннеле: багаж"), (XS - 5.0, 254.4, "car", "common", "машина в тоннеле"),
    (XS + 6.5, 249.0, "backpack", "med", "у барьеров перед тоннелем"),
    # двор ЖК, гаражи, дом 7, «Ярус» снаружи
    (-190.0, -101.5, "crate", "common", "гараж двора"), (-98.0, -97.0, "loose", "common", "мусорная площадка"),
    (-200.0, 76.5, "crate", "common", "гараж дома 7"), (-90.0, 44.0, "car", "common", "фургон у «Яруса»"),
    (-128.0, 24.0, "car", "common", "внедорожник: коробки"), (-103.0, 39.6, "car", "weapon", "полицейская у «Яруса»"),
    (-132.0, 100.5, "car", "common", "фура на разгрузке"), (-112.0, 95.0, "crate", "common", "ящики на разгрузке"),
]
for (x, z, kind, tier, note) in STREET_LOOT:
    loot(x, 0.0, z, kind, tier, note)


# ================================================================== приёмы EFT (владелец 2026-10-29: «делай всё»)
# docs/design/prospekt_eft_mechanics.md: условные выходы, подстанция, решётка хранилища, схроны. Механика — в рейде
# (tools/build_prospekt_raid.py → ExtractionPoint, PowerSwitch, Door, LootContainer); здесь — места и вид.
KTP_SWITCH = "prospekt_ktp"
# подстанция двора ЖК: двери КТП распахнуты, внутри — рубильник; питает ворота выезда из паркинга и электрозамок
# решётки хранилища банка
plan["switches"].append({"id": KTP_SWITCH, "label": "Рубильник подстанции (КТП)", "at": [-156.0, 0.05, -88.7], "yaw": 180.0})
sign("подстанция: питание паркинга и банка", -156.0, 3.4, -88.6, 36)
# ворота выезда из паркинга −1 в город — в западной стене, у торцевого проезда: рольставня, полосы, знак
box(PIT[0] + 0.12, PIT_Y + 1.6, -60.0, 0.12, 3.2, 6.0, "steel")
for k in range(6):
    box(PIT[0] + 0.2, PIT_Y + 0.35 + k * 0.52, -60.0, 0.03, 0.08, 6.0, "dark", 0.0, False)
for dz in (-3.15, 3.15):
    box(PIT[0] + 0.25, PIT_Y + 1.6, -60.0 + dz, 0.3, 3.2, 0.3, "stripe")
sign("выезд в город · ворота от подстанции", PIT[0] + 0.5, PIT_Y + 3.6, -60.0, 36)
# водопропускная труба под насыпью: оголовок в подошве откоса, труба Ø 1,5 м, решётка отогнута — пролезть можно
# только без рюкзака
CULVERT = (-64.0, EMB_Z0)
box(CULVERT[0], 1.1, CULVERT[1] + 0.35, 5.0, 2.2, 0.5, "concrete")
box(CULVERT[0], 0.8, CULVERT[1] + 0.08, 1.5, 1.5, 0.06, "dark", 0.0, False)
for dx in (-2.9, 2.9):
    box(CULVERT[0] + dx, 0.7, CULVERT[1] - 0.6, 0.5, 1.4, 2.4, "concrete")
box(CULVERT[0] - 0.9, 0.4, CULVERT[1] - 0.5, 0.06, 0.8, 1.4, "steel", 25.0, False)
sign("водопропускная труба · без рюкзака", CULVERT[0], 3.0, CULVERT[1] - 0.6, 36)
# решётка хранилища банка с электрозамком: в проёме толстой стены хранилища (x −24, z −46, 2,6 × 2,6) — ключ-карта
# и питание подстанции; без питания в хранилище только подкопом
plan["doors"].append({"name": "VaultGrille", "label": "решётка хранилища", "at": [-24.0, BASE_Y, -47.3], "yaw": -90.0,
                      "width": 2.6, "height": 2.6, "key": "key_bank_vault", "switch": KTP_SWITCH})
# схроны на земле (к «тайникам» на крышах): в рейде открыта случайная часть всех схронов карты
loot(-176.0, 0.0, 80.2, "backpack", "good", "схрон: в мусорном баке двора дома 7")
loot(62.0, 0.0, -89.2, "backpack", "good", "схрон: за щитом КТП у хозяйственного проезда")
loot(126.4, 0.0, 161.6, "backpack", "good", "схрон: под плитой у гаражей корпуса 3")

# ================================================================== появление, выходы, места, подходы, проверки
plan["spawns"] = [{"id": "cordon", "label": "Кордон (старт пролога)", "at": [-200.0, 0.0]},
                  {"id": "yards", "label": "Дворы ЖК", "at": [-125.0, -104.0]},
                  {"id": "vershina", "label": "За «Вершиной»", "at": [150.0, -104.0]},
                  {"id": "south", "label": "Юг, у насыпи", "at": [150.0, 236.0]},
                  {"id": "site", "label": "Стройка за «Ярусом»", "at": [-140.0, 192.0]},
                  {"id": "station", "label": "Вокзал", "at": [-100.0, 205.0]}]
plan["exits"] = [{"label": "Тоннель на юг — в следующий район", "at": [XS + 3.0, 270.0], "always": True},
                 {"label": "Дворами к насыпи", "at": [-145.0, YARD_Z0 + 1.5], "always": True},
                 {"label": "Пролом в заборе стройки", "at": [-148.5, 186.0], "always": True},
                 {"label": "По путям на запад", "at": [-147.0, TRACKS[1]], "always": False, "chance": 0.6},
                 # условные (владелец 2026-10-29): ворота паркинга — питание подстанции или брелок; труба — без рюкзака
                 {"label": "Паркинг −1, выезд в город", "at": [PIT[0] + 3.5, -60.0], "y": PIT_Y + 0.08, "always": False,
                  "switch": KTP_SWITCH, "alt_key": "key_parking_fob"},
                 {"label": "Водопропускная труба", "at": [CULVERT[0], CULVERT[1] - 1.6], "always": False, "no_backpack": True,
                  "radius": 3.0}]
plan["locations"] = [
    {"id": 1, "label": "Кордон", "at": [-200.0, 0.0], "spawn": [-200.0, 0.0], "look": [-160.0, -6.0]},
    {"id": 2, "label": "Кофейня «Зерно»", "at": [-184.0, -22.0], "spawn": [-184.0, -12.0], "look": [-184.0, -22.0]},
    {"id": 3, "label": "Паркинг −1 · западный спуск", "at": [-128.0, -60.0], "spawn": [RW[0] + 3.9, YARD_Z0 + 5.0], "look": [RW[0] + 3.9, -95.0]},
    {"id": 4, "label": "Двор ЖК", "at": [-175.0, -95.0], "spawn": [-175.0, -95.0], "look": [-175.0, -82.0]},
    {"id": 5, "label": "Подземный переход", "at": [-156.0, 0.0], "spawn": [-148.0, -10.0], "look": [-158.0, -13.0]},
    {"id": 6, "label": "Парковка «Яруса»", "at": [-102.0, 30.0], "spawn": [-112.0, 17.0], "look": [-102.0, 48.0]},
    {"id": 7, "label": "Супермаркет «Ярус»", "at": [-102.0, 68.0], "spawn": [-108.0, 44.0], "look": [-108.0, 68.0]},
    {"id": 8, "label": "Стройка за «Ярусом»", "at": [-108.0, 165.0], "spawn": [-100.0, 116.0], "look": [-108.0, 150.0]},
    {"id": 9, "label": "Площадь «Вершины»", "at": [50.0, -10.0], "spawn": [12.0, -6.0], "look": [57.0, -28.0]},
    {"id": 10, "label": "Сквер · памятник", "at": [-14.0, 76.0], "spawn": [-30.0, 46.0], "look": [-14.0, 76.0]},
    {"id": 11, "label": "Банк «Капитал»", "at": [-21.0, -48.0], "spawn": [-21.0, -18.0], "look": [-21.0, -40.0]},
    {"id": 12, "label": "Сквер · площадка и баскетбол", "at": [-20.0, 165.0], "spawn": [-8.0, 146.0], "look": [-30.0, 165.0]},
    {"id": 13, "label": "Тоннель на юге", "at": [XS, 262.0], "spawn": [XS + 4.0, 236.0], "look": [XS, 262.0]},
    {"id": 14, "label": "Корпус 3 и парковка", "at": [90.0, 110.0], "spawn": [XS + 11.0, 110.0], "look": [113.0, 110.0]},
    {"id": 15, "label": "Пункт эвакуации · палатки", "at": [132.0, 20.0], "spawn": [104.0, 18.0], "look": [132.0, 20.0]},
    {"id": 16, "label": "Упавший состав", "at": [0.0, 238.0], "spawn": [12.0, 214.0], "look": [0.0, 238.0]},
    {"id": 17, "label": "Дом на повороте · магазины", "at": [-10.0, 30.0], "spawn": [-25.5, 12.0], "look": [-25.5, 28.0]},
    {"id": 18, "label": "Вокзал «Проспект»", "at": [-116.0, 229.0], "spawn": [-116.0, 204.0], "look": [-116.0, 229.0]},
]
sm_cx = SM[0]
plan["probe_routes"] = [
    {"id": "prologue", "label": "пролог: кордон → кофейня → переход → «Ярус» → склад → разгрузка → сквер → вагоны → тоннель",
     "max_open_m": 30.0,
     "points": [[-200, 0], [-193, -4], [-193, -9.2], [-188, -9.2], [-184, -12], [-184, -16], [-184, -21], [-184, -16], [-184, -12], [-166, -12],
                [-162.5, -10], [-150, -10], [-150, -13], [-152.5, -13], [-158.6, -13], [-158.6, -9.5], [-156, -8], [-156, 0], [-156, 8], [-158.6, 9.5], [-158.6, 13],
                [-152.5, 13], [-149, 13], [-146, 17], [-130, 18], [-112, 18], [-108, 26], [-108, 46], [-108, 52], [-108, 64],
                [-108, 78], [-108, 80.6], [-122, 80.6], [-122, 84.5], [sm_cx, 84.5], [sm_cx, 90], [sm_cx, 95.5], [-66, 96.5], [-60, 97.5],
                [-55, 100], [-55, 112], [-52, 140], [-30, 146], [-10, 146], [10, 146], [11, 182], [36, 186], [37, 222],
                [41, 238], [XS + 3.0, 244], [XS + 3.0, 256], [XS + 3.0, 268]]},
    # пролог, обход мимо зала «Яруса»: тамбур (вдоль фасада — мимо мешков у входа) → дверь «Только для персонала» →
    # коридор → склад → к воротам рампы
    {"id": "prologue_staff", "label": "пролог: тамбур «Яруса» → служебный коридор → склад → ворота рампы", "max_open_m": 0.0,
     "points": [[-96, 44], [-96, 48.7], [-87.8, 48.7], [-87.8, 50.6], [-67, 50.6], [-63.2, 50.6], [-63.2, 81], [-63.2, 83.2], [-77, 83.2], [-77, 86.2],
                [-100, 86.2]]},
    {"id": "yards_to_south", "label": "дворы ЖК → проезд → зебра → служебный проезд → сквер", "max_open_m": 30.0,
     "points": [[-125, -104], [-110.6, -96], [-110.6, -60], [-110.6, -20], [-110.6, -12], [CROSS_W + 1.5, -10], [CROSS_W + 1.5, 10],
                [-112, 18], [-90, 18], [-63, 18], [-55, 20], [-55, 60], [-55, 106], [-55, 112]]},
    {"id": "vershina_to_north", "label": "за «Вершиной» → вдоль стилобата → дворы → к насыпи", "max_open_m": 30.0,
     "points": [[150, -104], [100, -100], [10, -98], [-40, -96], [-40, -85.3], [-80, -85.3], [-110.6, -96], [-140, -98], [-145, -112],
                [-145, YARD_Z0 + 2.0]]},
    {"id": "south_to_site", "label": "юг → парковка корпуса 3 → зебра → сквер → стройка → пролом", "max_open_m": 30.0,
     "points": [[150, 236], [140, 226], [110, 224], [74, 230], [72, 156], [XS + 1.5, 152], [XS - 1.5, 153.6], [37, 153.6], [37, 148], [12, 146], [-8, 146],
                [-52, 146], [-58, 150], [-68, 150], [-68, 192], [-138, 192], [-149, 186]]},
    {"id": "tower_shops", "label": "дом на повороте: арка во двор и пивная насквозь обратно на проспект", "max_open_m": 0.0,
     "points": [[-25.5, 12.0], [-25.5, 21.0], [-25.5, 30.0], [-25.5, 40.0], [-32.5, 40.0], [-32.5, 35.5], [-32.5, 28.0],
                [-32.5, 20.5], [-32.5, 13.0]]},
    {"id": "tower_arch_s", "label": "дом на повороте: арка с южного плеча в сквер", "max_open_m": 0.0,
     "points": [[42.0, 67.5], [35.5, 67.5], [28.0, 67.5], [20.5, 67.5], [14.0, 67.5]]},
    {"id": "station_platform", "label": "вокзал: площадь → зал → лестница → мост → платформа", "max_open_m": 0.0,
     "points": [[-40.0, 205.0], [-60.0, 206.5], [-110.0, 206.5], [-116.0, 206.5], [-116.0, 211.0], [-116.0, 216.0],
                [-119.5, 220.0], [-119.5, 233.0], [-124.4, 237.5], [-125.5, 239.0], [-125.5, 241.0], [-112.6, 241.0], [-110.5, 241.5], [-110.0, 243.4],
                [-110.0, 252.0], [-110.0, 260.3]], "min_y": 7.0},
    {"id": "parking_minus1", "label": "двор → проезд вдоль забора → западный спуск → паркинг −1 → восточный торец", "max_open_m": 0.0,
     "points": [[-110.6, -96], [-110.6, YARD_Z0 + 6.0], [RW[0] + 6.5, YARD_Z0 + 6.0], [RW[0] + 6.5, YARD_Z0 + 9.5], [RW[0] + 6.5, -100.0],
                [RW[0] + 6.5, -86.0], [RW[0] + 6.5, RAMP_BOT + 1.5], [X_ROW0 - 3.9, RAMP_BOT + 1.5], [X_ROW0 - 3.9, -78.8],
                [-150.0, -78.8], [-100.0, -78.8], [X_ROW1 + 3.9, -78.8]], "max_y": -2.6},
    {"id": "bank_roof", "label": "банк: калитка → зал → за стойку → ядро → три марша → крыша", "max_open_m": 0.0,
     "points": [[-21, -19], [-21, -33], [-21, -44], [-14.65, -46.5], [-14.65, -49.3], [-28.7, -49.3], [-28.7, -57.3],
                [-28.7, -58.6], [-28.6, -59.0], [-37.8, -59.0], [-38.0, -61.0], [-28.6, -61.0], [-28.6, -59.2], [-37.8, -59.2],
                [-37.6, -57.2], [-30.0, -50.0]], "min_y": BY[3] - 0.3},
    {"id": "dig_to_vault", "label": "двор → восточный спуск → паркинг −1 → подкоп → хранилище → лестница в зал банка", "max_open_m": 0.0,
     "points": [[-110.6, -96], [-110.6, YARD_Z0 + 6.0], [RE[1] - 3.9, YARD_Z0 + 6.0], [RE[1] - 3.9, YARD_Z0 + 9.5], [RE[1] - 3.9, -100.0],
                [RE[1] - 3.9, -86.0], [RE[1] - 3.9, -60.0], [RE[1] - 3.9, -43.0], [-37.0, -43.0], [-30.0, -45.5], [-22.5, -46.0], [-22.4, -60.2],
                [-16.6, -60.3], [-15.0, -60.0], [-6.4, -60.0], [-5.4, -58.0], [-5.4, -55.0]], "min_y": -0.3},
]
plan["checks"] = {"pit": [-156.0, -42.0], "pit_y": PIT_Y, "yard": [-156.0, -42.0], "tunnel": [-156.0, 0.0],
                  "cordon": {"from": [-203.0, 0.5], "to": [-226.0, 0.5], "stop_x": XC - 0.6}}

# ================================================================== расширенный проспект: карманы, разделительная, новая земля
# Всё ниже — сразу в новых координатах (raw). Укрытия на широкой дороге (правила плотности: открытый кусок ≤ 30 м,
# укрытия через 6–12 м): машины в парковочных карманах, деревья и кадки на разделительной. Новая земля между
# отъехавшими блоками (швы tools/prospekt_widen.py): на севере — переулок с бизнес-центром между банком и «Вершиной»,
# на востоке — автопарк ЧВК у лагеря эвакуации; забор района и город за ним — через швы без дыр.
KEEP_CLEAR_RAW: list[tuple[float, float, float, float]] = []
SMALL_KITS = LITTER | {"bottle", "can", "bags", "puddle", "tape", "track_3m", "ac_unit", "cone", "tires", "trash_pile"}
if WIDEN.ACTIVE:
    _snap = mark()
    # препятствия: где уже что-то стоит (прежнее — в новых координатах), клетка 4 м
    _occ: dict[tuple[int, int], list[tuple[float, float]]] = {}

    def _occupy(x: float, z: float) -> None:
        _occ.setdefault((int(math.floor(x / 4.0)), int(math.floor(z / 4.0))), []).append((x, z))

    def _free(x: float, z: float, rx: float, rz: float) -> bool:
        for i in range(int(math.floor((x - rx) / 4.0)) - 1, int(math.floor((x + rx) / 4.0)) + 2):
            for j in range(int(math.floor((z - rz) / 4.0)) - 1, int(math.floor((z + rz) / 4.0)) + 2):
                for (ox, oz) in _occ.get((i, j), []):
                    if abs(ox - x) < rx and abs(oz - z) < rz:
                        return False
        return True

    for it in FI["items"]:
        if it[0] not in SMALL_KITS:
            _occupy(*WIDEN.warp(it[1], it[2]))
    for bx in plan["boxes"]:
        if bx["mat"] != "stripe" and bx["size"][1] > 0.1 and bx["at"][1] < 3.0:
            _occupy(*WIDEN.warp(bx["at"][0], bx["at"][2]))
    for st in plan["stairs"]:
        for p in (st["from"], st["to"]):
            _occupy(*WIDEN.warp(p[0], p[2]))

    # ---- машины в карманах: прямые плечи, по обе стороны; не у зебр, перехода, въезда во двор, кордона и тоннеля
    POCKET_C = EDGEN + WIDEN.POCKET * 0.5
    CAR_KITS = [("car", 0.66), ("car_open", 0.08), ("car_wreck", 0.1), ("taxi", 0.06), ("van", 0.1)]

    def _car(x: float, z: float, yaw: float) -> None:
        r = rng2.random()
        kit = CAR_KITS[-1][0]
        for (k, w) in CAR_KITS:
            if r < w:
                kit = k
                break
            r -= w
        tint = rng2.choice(CAR_TINTS) if kit in ("car", "car_open", "car_wreck") else -1
        if kit == "car_wreck":
            tint = 1 if rng2.random() < 0.4 else tint
        put(kit, x, z, yaw, 1.0, 0.0, tint, 0.0, True)
        _occupy(x, z)
        if kit == "car_open":
            a = math.radians(yaw)
            loot(x - math.sin(a) * 2.7, 0.0, z - math.cos(a) * 2.7, "car", "common", "машина в кармане: багажник")

    for side in (1.0, -1.0):
        zc = ZA - side * POCKET_C
        x = -186.0 + (0.0 if side > 0 else 3.0)
        while x < -12.0:
            skip = abs(x - CROSS_W) < 12.0 or -165.0 < x < -147.0 or (side > 0 and -118.0 < x < -103.0)
            if not skip and rng2.random() < 0.55 and _free(x, zc, 3.4, 2.0):
                _car(x + rng2.uniform(-0.4, 0.4), zc + rng2.uniform(-0.25, 0.25), (-90.0 if side > 0 else 90.0) + rng2.uniform(-4, 4))
            x += 6.0
        xc = XSN + side * POCKET_C
        z = 66.0 + (0.0 if side > 0 else 3.0)
        while z < 236.0:
            if abs(z - CROSS_S) >= 12.0 and rng2.random() < 0.55 and _free(xc, z, 2.0, 3.4):
                _car(xc + rng2.uniform(-0.25, 0.25), z + rng2.uniform(-0.4, 0.4), (180.0 if side > 0 else 0.0) + rng2.uniform(-4, 4))
            z += 6.0

    # ---- разделительная 6 м: липы между фонарями, кадки — низкие укрытия посреди дороги
    def _median_busy(x: float, z: float) -> bool:
        return (x > CX and z > 234.0) or busy(*_unwarp_hint(x, z))   # у тоннеля разделительной нет — подъезд к порталу

    def _unwarp_hint(x: float, z: float) -> tuple[float, float]:
        """Прежняя точка оси для проверки «занятых» мест (переход, зебры, кордон, тупик) — по продольной координате."""
        if x <= CX:
            return x, 0.0
        if z >= CZ:
            return XS, z
        return x, z

    for (x, z, h) in n_along(30.0, 0.0, 37.0, _median_busy, curve=False):
        if _free(x, z, 2.5, 2.5):
            put("tree_round", x, z, rng2.uniform(0, 360), rng2.uniform(0.85, 1.1))
            _occupy(x, z)
    for (x, z, h) in n_along(45.0, 0.0, 52.0, _median_busy, curve=False):
        for dd in (-1.6, 1.6):
            a = math.radians(h)
            px, pz = x + math.cos(a) * dd, z - math.sin(a) * dd
            if _free(px, pz, 1.5, 1.5):
                u("U02_02_planter", px, pz, h, 1.0, 0.0, True)
                _occupy(px, pz)

    # ---- перебивки обзора на широкой дороге (владелец 2026-10-24, п. 7: «каждые 50–90 м»): прежние стояли под 17 м
    # проезжей части — теперь их вдвое больше поперёк, вразбежку: фильтр ЧВК через все полосы, автобусы и грузовики
    # в полосах, контейнеры, ларьки на тротуарах у бордюра
    def _view(kit: str, x: float, z: float, yaw: float, tint: int = -1, rx: float = 2.5, rz: float = 2.5) -> None:
        if _free(x, z, rx, rz):
            put(kit, x, z, yaw, 1.0, 0.0, tint, 0.0, True)
            _occupy(x, z)

    # фильтр ЧВК (прежние 40- и 20-футовый у x −106 перенеслись на северные полосы и южный край): ещё два, на 4,5 м
    # западнее — проходы между контейнерами узкие, по тротуарам свободно
    put("container40", -110.5, ZA - 15.3, 0.0, 1.0, 0.0, -1, 0.0, True)
    put("container20", -110.5, ZA + 6.6, 0.0, 1.0, 0.0, -1, 0.0, True)
    loot(-112.5, 0.0, ZA - 9.0, "body", "common", "фильтр ЧВК: тело между контейнерами")
    for (kit, x, dz, yaw, tint) in [("bus_city", -27.0, -10.5, 75.0, 8), ("truck", -52.0, 11.5, 100.0, 2), ("van", -176.0, 13.5, 80.0, 9),
                                    ("truck", -131.0, -11.0, 84.0, 6), ("minibus", -88.0, 14.0, 96.0, 9)]:
        _view(kit, x, ZA + dz, yaw, tint)
    for (x, side) in [(-170.0, 1.0), (-140.0, 1.0), (-62.0, 1.0), (-22.0, 1.0), (-182.0, -1.0), (-100.0, -1.0), (-56.0, -1.0), (-14.0, -1.0)]:
        _view("kiosk", x, ZA - side * (RHN + 3.0), 180.0 if side > 0 else 0.0)
    # поворот: автобус и грузовик на внутренних полосах, контейнеры на разделительной, фургон на внешних, ларьки
    for (kit, phi, d, dyaw, tint) in [("bus_city", 0.95, -10.0, 25.0, 9), ("truck", 0.55, -9.0, -30.0, 4), ("van", 1.35, 10.0, 40.0, 6),
                                      ("container20", 1.18, 0.0, 0.0, -1), ("kiosk", 0.8, -(RHN + 3.0), 180.0, -1),
                                      ("kiosk", 0.3, RHN + 3.0, 0.0, -1), ("truck", 0.2, 11.0, 15.0, 11)]:
        x, z = n_curve_point(phi, d)
        _view(kit, x, z, 90.0 - math.degrees(phi) + dyaw, tint)
    # южное плечо
    for (kit, d, z, yaw, tint) in [("bus_city", -9.0, 92.0, 25.0, 8), ("container40", 9.0, 192.0, 80.0, -1), ("truck", 10.0, 72.0, 170.0, 2),
                                   ("truck", -8.0, 220.0, 10.0, 11), ("van", -12.0, 140.0, 4.0, 6), ("container20", -10.0, 205.0, 95.0, -1)]:
        _view(kit, XSN + d, z, yaw, tint)
    for (d, z) in [(-(RHN + 3.0), 80.0), (-(RHN + 3.0), 175.0), (RHN + 3.0, 110.0), (RHN + 3.0, 160.0), (RHN + 3.0, 215.0)]:
        _view("kiosk", XSN + d, z, 90.0)
    # ларёчные ряды поперёк тротуаров (три ларька встык, проход 2,6–2,8 м): на одном и том же тротуаре проход то у
    # бордюра, то у фасада — взгляд вдоль тротуара упирается в ряд, а идти можно всегда
    def _kiosk_row(arm: str, along_c: float, side: float, from_curb: bool) -> None:
        for k in range(3):
            dd = RHN + 1.6 + k * 3.0 if from_curb else FN - 1.6 - k * 3.0
            if arm == "w":
                x, z, yaw = along_c, ZA - side * dd, 90.0
            elif arm == "c":                                          # в повороте along_c — угол phi
                (x, z), yaw = n_curve_point(along_c, side * dd), 90.0 - math.degrees(along_c)
            else:
                x, z, yaw = XSN + side * dd, along_c, 0.0
            put("kiosk", x, z, yaw, 1.0, 0.0, -1, 0.0, True)
            _occupy(x, z)
        if arm == "w":
            loot(along_c + 2.2, 0.0, ZA - side * (RHN + 4.6 if from_curb else FN - 4.6), "register", "common", "ларёк: касса")

    for (arm, c, side, curb) in [("s", 118.0, -1.0, False), ("s", 196.0, -1.0, True), ("s", 100.0, 1.0, True), ("s", 178.0, 1.0, False),
                                 ("w", -50.0, 1.0, False), ("w", -80.0, -1.0, False), ("w", -175.0, -1.0, True),
                                 ("s", 132.0, -1.0, True), ("s", 225.0, 1.0, True), ("c", 0.45, -1.0, True), ("c", 1.15, 1.0, False),
                                 ("c", 1.05, -1.0, False)]:
        _kiosk_row(arm, c, side, curb)
    # площадь «Вершины» стала шире на 31 м: колонна эвакуации — автобусы, грузовики, контейнеры поста — поперёк
    # длинных линий с поворота на восток и северо-восток
    for (kit, x, z, yaw, tint) in [("container40", 100.0, -2.0, 0.0, -1), ("bus_city", 112.0, 11.0, 160.0, 8), ("truck", 92.0, -21.0, 70.0, -1),
                                   ("bus_city", 78.0, -33.0, 95.0, 9), ("truck", 118.0, -24.0, 5.0, 11), ("container20", 104.0, 27.0, 90.0, -1),
                                   ("kiosk", 58.0, -40.0, 0.0, -1), ("truck", 40.0, -52.0, 85.0, -1)]:
        _view(kit, x, z, yaw, tint)
    loot(97.6, 0.0, -2.0, "crate", "common", "колонна эвакуации: вещи у контейнера")
    # фургоны и грузовики в карманах — взгляд вдоль кармана (легковые его не закрывают) рвётся через 50–80 м
    def _pocket_view(kit: str, arm: str, side: float, c: float) -> None:
        for dc in (0.0, 3.0, -3.0, 6.0, -6.0, 9.0, -9.0):
            if arm == "w":
                x, z, yaw = c + dc, ZA - side * POCKET_C, (-90.0 if side > 0 else 90.0)
            else:
                x, z, yaw = XSN + side * POCKET_C, c + dc, (180.0 if side > 0 else 0.0)
            if _free(x, z, 2.6 if arm == "w" else 1.6, 1.6 if arm == "w" else 2.6):
                put(kit, x, z, yaw + rng2.uniform(-3, 3), 1.0, 0.0, rng2.choice([2, 6, 9, 11]), 0.0, True)
                _occupy(x, z)
                return

    for (kit, arm, side, c) in [("van", "s", -1.0, 104.0), ("truck", "s", -1.0, 168.0), ("van", "s", -1.0, 222.0),
                                ("van", "s", 1.0, 84.0), ("truck", "s", 1.0, 136.0), ("van", "s", 1.0, 206.0),
                                ("van", "w", 1.0, -172.0), ("truck", "w", 1.0, -92.0), ("van", "w", 1.0, -40.0),
                                ("van", "w", -1.0, -140.0), ("truck", "w", -1.0, -66.0), ("van", "w", -1.0, -26.0)]:
        _pocket_view(kit, arm, side, c)
    # трансформаторные будки на разделительной (как прежняя у рекламного щита) — посреди дороги ещё одна перебивка
    for (x, z, yaw) in [(-45.0, ZA, 0.0), (-170.0, ZA, 0.0), (XSN, 118.0, 90.0), (XSN, 196.0, 90.0), (*n_curve_point(0.62, 0.0), 0.0)]:
        _view("ktp", x, z, yaw, -1, 1.8, 1.8)

    # ---- шов на севере: переулок между автомойкой банка и стилобатом «Вершины», бизнес-центр на углу
    SX0, SX1 = WIDEN.SEAM_X, WIDEN.SEAM_X + WIDEN.S
    ZN_FENCE = YARD_Z0 + 0.5 - WIDEN.S                               # забор района на севере
    LANE_X0, LANE_X1 = SX0 + 3.5, SX0 + 12.5                         # проезжая часть переулка 9 м (2 × 3,5 × 1,3)
    LANE_Z0, LANE_Z1 = ZN_FENCE + 5.0, -58.0
    surface("seam_lane", "road", LANE_X0, LANE_Z0, LANE_X1, LANE_Z1)
    surface("seam_walk_w", "walk", SX0, LANE_Z0, LANE_X0, LANE_Z1, 0.0, 0.15)
    surface("seam_walk_e", "walk", LANE_X1, LANE_Z0, LANE_X1 + 3.5, LANE_Z1, 0.0, 0.15)
    box(LANE_X0 + 0.1, 0.075, (LANE_Z0 + LANE_Z1) * 0.5, 0.2, 0.15, LANE_Z1 - LANE_Z0, "stripe")
    box(LANE_X1 - 0.1, 0.075, (LANE_Z0 + LANE_Z1) * 0.5, 0.2, 0.15, LANE_Z1 - LANE_Z0, "stripe")
    BC13 = (LANE_X1 + 4.0, SX1 + 0.5, -110.0, -61.0)                 # x0, x1, z0, z1 — вплотную к стилобату
    flats("BC_Prospekt13", "БЦ «Проспект, 13» — 9 этажей (закрыт)", ((BC13[0] + BC13[1]) * 0.5, (BC13[2] + BC13[3]) * 0.5), 9, 0,
          0.0, (BC13[1] - BC13[0], BC13[3] - BC13[2]), 3.6, False, True, 0.0, "East", 0.0)
    revolving_entrance((BC13[0] + BC13[1]) * 0.5, BC13[3], 0.0)
    sign("БЦ «Проспект, 13» · вход", (BC13[0] + BC13[1]) * 0.5, 5.0, BC13[3] + 0.4, 40)
    KEEP_CLEAR_RAW.append(((BC13[0] + BC13[1]) * 0.5 - 6.0, BC13[3], (BC13[0] + BC13[1]) * 0.5 + 6.0, BC13[3] + 5.0))
    sign("Банковский переулок", SX0 + 1.0, 3.2, LANE_Z1 - 1.0, 38)
    for z in range(int(LANE_Z1) - 6, int(LANE_Z0) + 4, -6):           # машины вдоль восточной обочины; у z ≈ −130 проход
        if -137.0 < z < -123.0 or rng2.random() > 0.55:
            continue
        _car(LANE_X1 - 1.6 + rng2.uniform(-0.2, 0.2), z + rng2.uniform(-0.4, 0.4), (0.0 if rng2.random() < 0.5 else 180.0) + rng2.uniform(-4, 4))
    for z in range(int(LANE_Z1) - 10, int(LANE_Z0), -24):
        u("U12_03_single_light", LANE_X1 + 2.4, z, -90.0)
    for z in range(int(LANE_Z1) - 4, int(LANE_Z0), -14):
        if not (-137.0 < z < -123.0):
            put("tree_birch", SX0 + 1.4, z, rng2.uniform(0, 360), rng2.uniform(0.8, 1.05))
    for k in range(3):
        u("R02_dumpster", SX0 + 1.6, LANE_Z0 + 3.0 + k * 3.4, 90.0, 1.0, 0.0, True)
    for k in range(4):                                               # гаражи в тупике переулка
        put("garage", LANE_X1 + 5.5 + k * 3.4, ZN_FENCE + 4.5, 180.0, 1.0, 0.0, -1, 0.0, True)
    put("kiosk", SX0 + 2.0, LANE_Z1 + 2.5, 90.0, 1.0, 0.0, -1, 0.0, True)
    put("container20", LANE_X0 + 1.6, -118.0, 0.0, 1.0, 0.0, -1, 0.0, True)     # контейнер под строительный мусор
    put("van", LANE_X0 + 2.4, -86.0, 176.0, 1.0, 0.0, 9, 0.0, True)
    for k in range(4):
        u("U02_04_bollard", LANE_X0 + 1.0 + k * 2.3, LANE_Z1 + 0.6, 0.0)
    loot(LANE_X1 + 7.0, 0.0, ZN_FENCE + 7.5, "crate", "common", "гаражи переулка")
    loot(SX0 + 2.6, 0.0, LANE_Z0 + 6.0, "loose", "common", "у баков в переулке")
    FI["stories"].append({"label": "Банковский переулок: БЦ «Проспект, 13», гаражи в тупике", "at": [LANE_X0 + 4.0, -95.0], "height": 4.0})

    # ---- шов на востоке: автопарк ЧВК у лагеря эвакуации, проезд с проспекта
    EZ0, EZ1 = CZ - WIDEN.S, CZ                                       # 23,7 … 55
    EX0 = XSN + FN                                                    # восточный край тротуара проспекта
    EX1 = 110.0 + WIDEN.S                                             # прежний край поля эвакуации (x 110 → 141,3)
    surface("seam_drive", "road", EX0, 36.0, EX1, 44.0)
    surface("seam_motorpool_n", "parking", EX0 + 2.0, EZ0 - 5.0, EX1, 36.0, 0.0, 0.05)
    surface("seam_motorpool_s", "parking", EX0 + 2.0, 44.0, EX1, 59.0, 0.0, 0.05)
    for k in range(4):                                               # грузовики рядом — перебивка обзора вдоль проезда
        put("truck", EX0 + 8.0 + k * 7.5, 51.5, 180.0 + rng2.uniform(-5, 5), 1.0, 0.0, -1, 0.0, True)
    put("armored_truck", EX0 + 12.0, 28.5, 90.0, 1.0, 0.0, -1, 0.0, True)
    for (x, z, yaw, dy) in [(EX0 + 25.0, 27.0, 0.0, 0.0), (EX0 + 25.2, 27.1, 1.5, 2.62)]:
        put("container20", x, z, yaw, 1.0, dy, -1, 0.0, dy == 0.0)
    put("trailer", EX0 + 33.0, 28.0, 90.0, 1.0, 0.0, -1, 0.0, True)
    # пост на въезде в лагерь: блоки с проездом, мешки, будка, шлагбаум
    for k in range(3):
        put("jersey_rw", EX1 - 1.5, 30.0 + k * 1.3, 0.0, 1.0, 0.0, -1, 0.0, True)
        put("jersey_rw", EX1 - 1.5, 46.5 + k * 1.3, 0.0, 1.0, 0.0, -1, 0.0, True)
    put("sandbag_post", EX1 - 4.5, 33.0, -90.0, 1.0, 0.0, -1, 0.0, True)
    put("booth", EX1 - 4.0, 46.0, 0.0, 1.0, 0.0, -1, 0.0, True)
    u("U07_02_barrier_arm", EX1 - 1.0, 36.5, 0.0)
    sign("лагерь эвакуации · въезд по пропускам", EX1 - 2.0, 3.6, 34.5, 38)
    for (x, sc) in [(EX1 + 11.0, 1.0), (EX1 + 25.0, 1.0), (EX1 + 39.0, 1.15)]:   # лагерь вырос — ещё три палатки
        put("army_tent", x, 41.0, 90.0, sc, 0.0, -1, 0.0, True)
    for k in range(4):
        put("barrel", EX1 + 4.0 + (k % 2) * 0.7, 52.0 + (k // 2) * 0.7, 0.0)
    loot(EX0 + 12.0, 0.0, 31.6, "car", "weapon", "бронемашина ЧВК в автопарке")
    loot(EX1 + 25.0, 0.0, 43.0, "crate", "common", "палатка лагеря: вещи")
    FI["stories"].append({"label": "автопарк ЧВК у въезда в лагерь", "at": [EX0 + 20.0, 40.0], "height": 4.0})

    # ---- площадь «Вершины» стала шире: покрытие между поворотом и стилобатом
    surface("plaza_v3", "walk", 65.0, -37.3, 91.3, -12.0, 0.0, 0.1)
    surface("plaza_v4", "walk", 30.0, -37.3, 65.0, -31.0, 0.0, 0.1)

    # ---- забор района через швы и город за ними
    for k in range(13):
        put("district_fence", 18.25 + k * 2.5, ZN_FENCE, fence_yaw("x", 1.0), 1.0, 0.0, -1, 0.0, False)
        put("district_fence", 159.5 + WIDEN.S, 25.95 + k * 2.5, fence_yaw("z", -1.0), 1.0, 0.0, -1, 0.0, False)
    building("Outside_City_N5", "", ((SX0 + SX1) * 0.5, ZN_FENCE - 20.0), (26.0, 16.0), "mass", 9, 3.0, 0.0, 0.0, "", "", 0.0, "Outside")
    building("Outside_City_E4", "", (190.0 + WIDEN.S + 22.0, (EZ0 + EZ1) * 0.5), (16.0, 26.0), "mass", 12, 3.0, 0.0, 0.0, "", "", 0.0,
             "Outside")
    raw(_snap)

FI["models_index"] = "res://data/urban95_models.json"
FI["kit_models"] = {k: {"model": m, "yaw": y} for k, (m, y) in KIT_MODELS.items() if m in MODEL_IDS}
FI["models_nosolid"] = MODELS_NOSOLID
FI["models_poles"] = MODELS_POLES
plan["buildings_count"] = len(B)
# расширенный проспект (владелец 2026-11-07): внешняя сторона отъезжает, полосы поперёк — до новой ширины
WIDEN.warp_plan(plan, RAW_IDS)
# свободные площадки перед входами: всё, кроме бумажного мусора и самих входов (U08_*), — прочь (и укрытия ИИ там же);
# прежние площадки — перенесённые, новые — как есть
KEEP_CLEAR = [tuple(WIDEN.warp_rect(list(r))) for r in KEEP_CLEAR] + KEEP_CLEAR_RAW


def _clear(x: float, z: float) -> bool:
    return any(r[0] <= x <= r[2] and r[1] <= z <= r[3] for r in KEEP_CLEAR)


FI["items"] = [it for it in FI["items"] if it[0] in LITTER or str(it[0]).startswith("m:U08_") or not _clear(it[1], it[2])]
FI["cover"] = [c for c in FI["cover"] if not _clear(c[0], c[1])]
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


# окружение — одно на блокаут и рейд
ENV_FILE = ROOT / "scenes" / "levels" / "prospekt" / "prospekt_environment.tres"
if not PREVIEW_DIR:
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text(LIGHT.ENV_TRES, encoding="utf-8", newline="\n")
OUT_SCENE.parent.mkdir(parents=True, exist_ok=True)
scene = [
    '[gd_scene format=3]',
    '[ext_resource type="Script" path="res://src/blockout/prospekt_landscape.gd" id="land"]',
    '[ext_resource type="Script" path="res://src/blockout/study_building.gd" id="build"]',
    '[ext_resource type="Script" path="res://src/blockout/prospekt_study_level.gd" id="launch"]',
    '[ext_resource type="Script" path="res://src/blockout/mall_filler.gd" id="fill"]',
    '[ext_resource type="Script" path="res://src/blockout/flat_section.gd" id="flats"]',
    # свет — tools/prospekt_light.py (владелец 2026-10-26: вариант стенда «всё вместе», черты освещения EFT)
    f'[ext_resource type="Environment" path="{LIGHT.ENV_PATH}" id="env"]',
    '[node name="ProspektStudy" type="Node3D"]',
    'script = ExtResource("launch")',
    'metadata/purpose = "Карта «Проспект» — серый блокаут, редакция 3: проспект с поворотом на 90° · правило масштаба E"',
    '[node name="WorldEnvironment" type="WorldEnvironment" parent="."]', 'environment = ExtResource("env")',
    '[node name="EveningSun" type="DirectionalLight3D" parent="."]', *LIGHT.SUN_PROPS,
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
                  "routes": len(plan["probe_routes"]), "json": str(OUT_JSON), "scene": str(OUT_SCENE)},
                 ensure_ascii=False))
