"""Серый черновик территории ТЦ «РИНГ» в настоящем масштабе — для прогулки и замера (mall_map.md §5,
шаг 2). Раскладка принята владельцем 2026-10-17 без изменений; координаты — из согласованной схемы
tools/mall_map_concept.py (там x — восток, y — север; здесь X — восток, Z = −y, юг).

Это исследование, а не рейдовая карта: добычи, ИИ, эвакуации и сети здесь нет. В центре — настоящий
серый 1-й этаж ТЦ (data/sectors/mall_1f.json, SectorBuilder без своего асфальта и забора), его завалы
входов и эскалаторы переносятся из scenes/levels/mall_1f.tscn как есть.

    python -X utf8 tools/build_mall_study.py
Пишет:
    data/blockouts/mall_study.json        план: граница, дороги, парковки, террасы, двор, места, маршруты
    scenes/levels/mall_study.tscn         сцена: рельеф (MallLandscape), здание (MallRing), постройки участков
Повторный запуск перезаписывает обе (ручные правки сцены пропадут — править план здесь).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def g(x: float, y: float) -> list[float]:
    """Точка схемы (x восток, y север) → игра [X, Z]."""
    return [round(x, 2), round(-y, 2)]


def gs(points) -> list[list[float]]:
    return [g(x, y) for x, y in points]


def pol(a_deg: float, r: float) -> tuple[float, float]:
    """Точка схемы по углу (0° — восток, 90° — север) и радиусу."""
    a = math.radians(a_deg)
    return r * math.cos(a), r * math.sin(a)


def arc(a0: float, a1: float, r: float, n: int) -> list[list[float]]:
    return [g(*pol(a0 + (a1 - a0) * i / n, r)) for i in range(n + 1)]


def ga(a_deg: float) -> float:
    """Угол схемы → угол игры (SectorBuilder.polar: от +X к +Z)."""
    return -a_deg


MALL_R = 100.0
PODIUM_R = 108.0
FIRE_LANE = [112.0, 122.0]
LOOP_R = 255.0

# ------------------------------------------------------------------ постройки участков
buildings: list[dict] = []


def building(key, label, xy, size, region, kind="mass", floors=1, height=3.0, yaw=0.0, lift=0.0):
    """Постройка в точке схемы; yaw — угол прямоугольника на схеме (против часовой, как в игре)."""
    buildings.append({"id": key, "label": label, "at": g(*xy), "size": [round(size[0], 2), round(size[1], 2)],
                      "floors": floors, "story_height": height, "yaw": round(yaw, 2), "kind": kind,
                      "region": region, "lift": lift})


# 2 — главная площадь: стела и навес над главным входом
building("Stela", "Рекламная стела «РИНГ»", pol(-90, 162), (4, 14), "Plaza", height=12)
building("Entrance_Canopy", "Навес над главным входом", pol(-90, 113), (30, 9), "Plaza", kind="canopy", height=5.2)
# 4 — автостанция: павильон, перроны, автобусы, крытая галерея к площади
building("Bus_Pavilion", "Автостанция · касса и зал", (-158, -284), (70, 16), "BusStation", kind="hall", height=5.0)
for i in range(4):
    building(f"Bus_Platform_{i + 1}", "Перрон под навесом", (-186 + i * 18, -268), (12, 3), "BusStation", kind="canopy", height=4.0)
for i, x in enumerate((-180, -144)):
    building(f"Bus_{i + 1}", "Автобус · 12 м", (x, -258), (12, 2.6), "BusStation", kind="bus")
gallery = [(-150, -272), (-118, -222), (-70, -175), pol(-100, 168)]
for i in range(len(gallery) - 1):
    (x0, y0), (x1, y1) = gallery[i], gallery[i + 1]
    length = math.hypot(x1 - x0, y1 - y0)
    building(f"Gallery_{i + 1}", "Крытая галерея к площади", ((x0 + x1) / 2, (y0 + y1) / 2), (length, 5), "BusStation",
             kind="canopy", height=3.4, yaw=math.degrees(math.atan2(y1 - y0, x1 - x0)))
# 5 — многоуровневый паркинг: 4 яруса по 3 м — второй ярус вровень со 2-м этажом ТЦ (6 м), мост
building("Parking_Garage", "Многоуровневый паркинг · 4 яруса", (185, -42), (64, 100), "Garage", kind="skeleton", floors=4, height=3.0)
# 6 — придорожное кафе и мойка
building("Cafe", "Придорожное кафе · окно выдачи", (262, -262), (30, 20), "Cafe", kind="hall", height=4.0)
building("Car_Wash", "Автомойка", (300, -240), (18, 26), "Cafe", kind="canopy", height=4.5)
# 7 — восточный вход: баррикада рейдеров (контейнеры, автобусы) перед лагерем в вестибюле
for i, (a, r) in enumerate(((-8, 130), (0, 136), (8, 130), (-4, 150), (5, 151))):
    building(f"Barricade_{i + 1}", "Баррикада рейдеров · контейнер", pol(a, r), (3.2, 12), "Barricade",
             height=2.6, yaw=a + (20 if i % 2 else -15))
# 8 — разгрузочный двор в выемке −4 м: фуры у доков, пост ЧВК у ворот
for i, a in enumerate((30, 38, 46, 54, 62)):
    building(f"Truck_{i + 1}", "Фура у дока", pol(a, 153), (2.6, 16), "Yard", height=4.0, yaw=a - 90)
building("PMC_Post", "Пост ЧВК у ворот двора", pol(48, 202), (7, 7), "Yard", kind="hall", height=3.0)
# 9 — техкомплекс: котельная с трубой 45 м (ориентир), ТП, генераторы, водонапорная башня
building("Boiler_House", "Котельная", (300, 150), (44, 30), "Tech", kind="hall", height=7.0)
building("Chimney", "Труба котельной · 45 м", (322, 172), (8, 8), "Tech", height=45.0)
building("Substation", "Трансформаторная подстанция", (262, 112), (16, 12), "Tech", height=4.0)
building("Generators", "Генераторная", (338, 120), (20, 14), "Tech", height=3.6)
building("Water_Tower", "Водонапорная башня", (350, 178), (12, 12), "Tech", height=24.0)
building("Service_Warehouse", "Склад обслуживания техники", (283, 192), (26, 14), "Tech", kind="hall", height=4.5)
# 11 — сквер: летняя веранда
building("Veranda", "Летняя веранда кафе", pol(100, 144), (26, 12), "Square", kind="canopy", height=3.2, yaw=10)
# 12 — АЗС: навес колонок, магазин, мойка и сервисный бокс
building("Fuel_Canopy", "АЗС · навес колонок", (-250, 182), (36, 18), "Gas", kind="canopy", height=5.0)
building("Gas_Shop", "АЗС · магазин", (-274, 210), (18, 11), "Gas", kind="hall", height=3.5)
building("Gas_Service_Box", "АЗС · мойка и сервисный бокс", (-228, 206), (14, 12), "Gas", kind="hall", height=4.5)
# 13 — КПП ЧВК на западной дороге: блоки, вышка, вагончики
for i in range(6):
    building(f"Block_{i + 1}", "Бетонный блок", (-352 + i * 7, 18 + (i % 2) * 12), (5.5, 2.6), "Checkpoint", height=1.2)
building("Watchtower", "Вышка КПП", (-330, 44), (6, 6), "Checkpoint", height=8.0)
building("Wagon_South", "Вагончик охраны", (-372, 4), (16, 6), "Checkpoint", height=2.8)
building("Wagon_North", "Вагончик охраны", (-372, 44), (16, 6), "Checkpoint", height=2.8)
# 14 — западная парковка: палатки пункта эвакуации (след мира, владелец 2026-10-17)
for i in range(7):
    a = 170 + i * 4.5
    # по оси западного въезда (180°) — проход между палатками
    if abs(a - 180) < 3:
        a += 3.5 if a >= 180 else -3.5
    building(f"Tent_{i + 1}", "Палатка эвакуационного пункта", pol(a, 190 + (i % 3) * 13), (8, 5), "WestParking",
             height=2.6, yaw=a - 90)
# за границей — новостройки за трассой и склады промзоны (декорация без входа)
for i, x in enumerate((-300, -170, 40, 190, 320)):
    building(f"Tower_{i + 1}", "Новостройка ЖК · 17 этажей", (x, -430), (54, 18), "Outside", floors=17, height=3.0)
for i, y in enumerate((-60, 60, 180)):
    building(f"Warehouse_{i + 1}", "Склад промзоны", (470, y), (40, 70), "Outside", height=9.0)

# ------------------------------------------------------------------ дороги (в метрах игры)
roads = [
    {"id": "loop", "width": 9, "points": arc(0, 360, LOOP_R, 240)},
    {"id": "highway_exit", "width": 8, "points": gs([(205, -318), (215, -280), (205, -245), pol(-50, LOOP_R)])},
    {"id": "to_bus_station", "width": 8, "points": gs([(-150, -318), (-150, -292), pol(-122, LOOP_R)])},
    {"id": "west_road", "width": 9, "points": gs([(-470, 30), (-300, 22), pol(175, LOOP_R)])},
    {"id": "service_road", "width": 7, "points": gs([(400, 268), (300, 205), pol(38, LOOP_R)])},
]
for a in (-90, 180, 0, 45):
    roads.append({"id": f"entry_{int(a) % 360}", "width": 8, "points": gs([pol(a, LOOP_R), pol(a, FIRE_LANE[1])])})
roads.append({"id": "car_wash_drive", "width": 4, "points": gs([(240, -282), (248, -290), (285, -290), (292, -275)])})

# ------------------------------------------------------------------ план
plan = {
    "version": 1,
    "purpose": "Серый черновик территории ТЦ в настоящем масштабе: прогулка и замер, не рейдовая карта",
    "reference": "docs/design/mall_map_concept.png (принята 2026-10-17), docs/design/concepts/mall_2026-10-15/01_ring_territory.png",
    "north": "-Z",
    "bounds": [-470, -400, 460, 400],
    "boundary": gs([(-400, -350), (380, -350), (425, -150), (412, 205), (335, 345), (-150, 368), (-385, 305), (-438, 60)]),
    "forest": [gs([(-385, 305), (-150, 368), (335, 345), (300, 300), (60, 318), (-160, 322), (-330, 270)]),
               gs([(335, 345), (412, 205), (425, 60), (380, 70), (372, 200), (300, 300)])],
    "mall": {"r": MALL_R, "podium_r": PODIUM_R, "fire_lane": FIRE_LANE, "loop_r": LOOP_R, "flat_r": 150.0,
             "sector": "res://data/sectors/mall_1f.json"},
    "roads": roads,
    "highway": {"z": 318.0, "width": 24.0, "x": [-470.0, 460.0], "y": -5.0, "crossing_x": [-34.0, -26.0]},
    # уровни рельефа (м): север выше, южная парковка террасами, трасса ниже всего
    "levels": {"north": 3.5, "north_from": 130.0, "north_to": 330.0, "south": -5.0, "south_from": 150.0, "south_to": 306.0},
    "terraces": {"a": [ga(-22), ga(-158)], "walls": [172.0, 206.0], "steps": [-2.0, -4.0], "ramps": [55.0, 90.0, 125.0],
                 "ramp_half_deg": 4.0, "ramp_len": 14.0},
    "parkings": [{"a": [ga(-20), ga(-160)], "r": [130.0, 240.0], "rows": {"a": [ga(-22), ga(-62)], "density": 0.5, "seed": 3}},
                 {"a": [ga(-118), ga(-158)], "r": [130.0, 240.0], "rows": {"a": [ga(-118), ga(-158)], "density": 0.45, "seed": 2}},
                 {"a": [ga(210), ga(150)], "r": [130.0, 238.0], "rows": {"a": [ga(208), ga(152)], "density": 0.8, "seed": 4}},
                 {"a": [ga(18), ga(-20)], "r": [130.0, 238.0], "rows": {"a": [ga(16), ga(-18)], "density": 0.35, "seed": 5}}],
    "plaza": {"a": [ga(-64), ga(-116)], "r": [PODIUM_R, 168.0], "fountain": g(*pol(-90, 140)), "fountain_r": 8.0,
              "planters": [g(*pol(-104, 152)), g(*pol(-76, 152))]},
    "yard": {"a": [ga(70), ga(22)], "r": [136.0, 205.0], "floor": -4.0, "dock": [136.0, 144.0], "dock_top": -2.8,
             "ramp_a": ga(46), "ramp_half_deg": 5.0, "ramp_r": [205.0, 236.0]},
    "square": {"a": [ga(146), ga(74)], "r": [128.0, 236.0], "trees": 60, "seed": 11, "playground": g(*pol(128, 186))},
    "pond": {"at": g(-110, 288), "size": [120.0, 56.0], "yaw": 8.0, "depth": 1.8, "drain": gs([(-60, 276), (-40, 262), (-12, 254)])},
    "garage_bridge": {"from": g(153, -2), "to": g(MALL_R - 0.5, -2), "width": 8.0, "y": 6.0},
    "foot_bridge": {"x": -40.0, "z": [298.0, 338.0], "width": 4.0, "y": 1.2},
    "buildings": buildings,
    "spawns": [{"id": k, "at": g(*xy)} for k, xy in
               {"Ю": (-20, -360), "З": (-415, -110), "СЗ": (-330, 278), "С": (130, 336), "В": (408, 30), "ЮВ": (392, -282)}.items()],
    "exits": [{"label": "Автостанция", "at": g(-182, -296), "always": True},
              {"label": "Ливнёвка", "at": g(-60, 256), "always": True},
              {"label": "Дорога на окраину (за КПП, плата)", "at": g(-430, 34), "always": False},
              {"label": "Грузовик (питание ворот)", "at": g(*pol(46, 168)), "always": False},
              {"label": "Пролом в заборе", "at": g(405, 120), "always": True},
              {"label": "Крыша — вертолёт (позже, 4-й этаж)", "at": g(-38, 50), "always": False}],
    # 15 участков схемы; spawn — куда переносит клавиша, look — куда смотреть
    "locations": [
        {"id": 1, "label": "ТЦ · главный вход", "at": [0.0, 60.0], "spawn": [0.0, 128.0], "look": [0.0, 95.0]},
        {"id": 2, "label": "ГЛАВНАЯ ПЛОЩАДЬ", "at": g(*pol(-90, 150)), "spawn": [18.0, 160.0], "look": [0.0, 120.0]},
        {"id": 3, "label": "ГЛАВНАЯ ПАРКОВКА", "at": [-90.0, 200.0], "spawn": [0.0, 214.0], "look": [-90.0, 190.0]},
        {"id": 4, "label": "АВТОСТАНЦИЯ", "at": g(-158, -284), "spawn": [-130.0, 255.0], "look": [-158.0, 284.0]},
        {"id": 5, "label": "МНОГОУРОВНЕВЫЙ ПАРКИНГ", "at": g(185, -42), "spawn": [240.0, 30.0], "look": [185.0, 42.0]},
        {"id": 6, "label": "ПРИДОРОЖНОЕ КАФЕ", "at": g(262, -262), "spawn": [235.0, 235.0], "look": [262.0, 262.0]},
        {"id": 7, "label": "ВОСТОЧНЫЙ ВХОД · БАРРИКАДА", "at": g(*pol(0, 140)), "spawn": [165.0, -30.0], "look": [115.0, 0.0]},
        {"id": 8, "label": "РАЗГРУЗОЧНЫЙ ДВОР", "at": g(*pol(46, 165)), "spawn": g(*pol(46, 232)), "look": g(*pol(46, 150))},
        {"id": 9, "label": "ТЕХКОМПЛЕКС", "at": g(300, 150), "spawn": [245.0, -130.0], "look": [300.0, -150.0]},
        {"id": 10, "label": "ПРОТИВОПОЖАРНЫЙ ВОДОЁМ", "at": g(-110, 288), "spawn": [-40.0, -262.0], "look": [-110.0, -288.0]},
        {"id": 11, "label": "СКВЕР", "at": g(*pol(110, 180)), "spawn": [-30.0, -128.0], "look": [-60.0, -180.0]},
        {"id": 12, "label": "АЗС", "at": g(-250, 182), "spawn": [-205.0, -160.0], "look": [-250.0, -182.0]},
        {"id": 13, "label": "КПП ЧВК", "at": g(-340, 30), "spawn": [-300.0, -25.0], "look": [-345.0, -25.0]},
        {"id": 14, "label": "ЗАПАДНАЯ ПАРКОВКА · ПАЛАТКИ", "at": g(*pol(180, 200)), "spawn": [-140.0, 10.0], "look": [-200.0, 0.0]},
        {"id": 15, "label": "ТРАССА И ПЕШЕХОДНЫЙ МОСТ", "at": g(-40, -318), "spawn": [-58.0, 292.0], "look": [-40.0, 318.0]},
    ],
    # подходы схемы A–D — проверка капсулой «от появления до здания»
    "probe_routes": [
        {"id": "A_юг_через_трассу", "points": [[-30.0, 345.0], [-30.0, 296.0], [0.0, 262.0], [0.0, 180.0], [0.0, 174.0], [10.0, 164.0], [14.0, 124.0]]},
        {"id": "B_запад_мимо_КПП", "points": [[-405.0, 100.0], [-395.0, 40.0], [-300.0, -60.0], [-250.0, -140.0], [-252.0, 0.0], [-124.0, 0.0]]},
        {"id": "C_восток_к_баррикаде", "points": [[385.0, 275.0], [300.0, 220.0], [240.0, 130.0], [240.0, 0.0], [155.0, 0.0]]},
        {"id": "D_север_во_двор", "points": [[130.0, -336.0], [200.0, -265.0], g(*pol(46, 240)), g(*pol(44, 190)), g(*pol(42, 150))]},
    ],
}


def area(poly):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2


plan["boundary_area_m2"] = round(area(plan["boundary"]), 1)
(ROOT / "data/blockouts").mkdir(parents=True, exist_ok=True)
(ROOT / "data/blockouts/mall_study.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

# ------------------------------------------------------------------ сцена
mall_1f = (ROOT / "scenes/levels/mall_1f.tscn").read_text(encoding="utf-8")


def copied_nodes(group: str) -> list[str]:
    """Узлы группы (Escalators / Rubble) из серого 1-го этажа — те же завалы и эскалаторы."""
    out = []
    for block in re.split(r"\n(?=\[node )", mall_1f):
        m = re.match(r'\[node name="([^"]+)" parent="%s" instance=ExtResource\("([^"]+)"\)\]' % group, block)
        if not m:
            continue
        res = {"3_esc": "esc", "4_rub": "rub"}[m.group(2)]
        body = block.split("\n", 1)[1].strip()
        out.append(f'[node name="{m.group(1)}" parent="Mall/{group}" instance=ExtResource("{res}")]\n{body}')
    return out


scene = [
    '[gd_scene format=3]',
    '[ext_resource type="Script" path="res://src/blockout/mall_landscape.gd" id="land"]',
    '[ext_resource type="Script" path="res://src/blockout/study_building.gd" id="build"]',
    '[ext_resource type="Script" path="res://src/blockout/mall_ring.gd" id="ring"]',
    '[ext_resource type="Script" path="res://src/blockout/mall_study_level.gd" id="launch"]',
    '[ext_resource type="PackedScene" path="res://scenes/world/escalator.tscn" id="esc"]',
    '[ext_resource type="PackedScene" path="res://scenes/world/rubble_pile.tscn" id="rub"]',
    '[sub_resource type="ProceduralSkyMaterial" id="SkyMat"]',
    'sky_top_color = Color(0.36, 0.44, 0.52, 1)',
    'sky_horizon_color = Color(0.72, 0.66, 0.58, 1)',
    'ground_bottom_color = Color(0.3, 0.3, 0.27, 1)',
    'ground_horizon_color = Color(0.72, 0.66, 0.58, 1)',
    '[sub_resource type="Sky" id="Sky"]', 'sky_material = SubResource("SkyMat")',
    '[sub_resource type="Environment" id="Environment"]',
    'background_mode = 2', 'sky = SubResource("Sky")',
    'ambient_light_source = 3', 'ambient_light_color = Color(0.68, 0.71, 0.75, 1)',
    'ambient_light_energy = 0.55', 'reflected_light_source = 2',
    'tonemap_mode = 2', 'tonemap_exposure = 1.0',
    'fog_enabled = true', 'fog_light_color = Color(0.7, 0.66, 0.6, 1)',
    'fog_light_energy = 0.6', 'fog_density = 0.00035',
    'ssao_enabled = true', 'ssao_radius = 1.5', 'ssao_intensity = 1.3',
    '[node name="MallStudy" type="Node3D"]',
    'script = ExtResource("launch")',
    'metadata/purpose = "Серый черновик территории ТЦ в настоящем масштабе · раскладка принята 2026-10-17"',
    '[node name="WorldEnvironment" type="WorldEnvironment" parent="."]',
    'environment = SubResource("Environment")',
    # базовая атмосфера игры — летний вечер, низкое тёплое солнце с запада-юго-запада
    '[node name="EveningSun" type="DirectionalLight3D" parent="."]',
    'rotation_degrees = Vector3(-24, -112, 0)',
    'light_color = Color(1, 0.86, 0.7, 1)', 'light_energy = 1.1',
    'light_angular_distance = 2.0', 'shadow_enabled = true',
    'directional_shadow_max_distance = 220.0',
    '[node name="Landscape" type="Node3D" parent="."]', 'script = ExtResource("land")',
    '[node name="Mall" type="Node3D" parent="."]', 'script = ExtResource("ring")',
    '[node name="Escalators" type="Node3D" parent="Mall"]',
    *copied_nodes("Escalators"),
    '[node name="Rubble" type="Node3D" parent="Mall"]',
    *copied_nodes("Rubble"),
]
regions = []
for b in buildings:
    if b["region"] not in regions:
        regions.append(b["region"])
for region in regions:
    scene.append(f'[node name="{region}" type="Node3D" parent="."]')
    for b in buildings:
        if b["region"] != region:
            continue
        scene.extend([f'[node name="{b["id"]}" type="Node3D" parent="{region}" groups=["mall_study_snap"]]',
                      f'transform = Transform3D({math.cos(math.radians(b["yaw"])):.5f}, 0, {-math.sin(math.radians(b["yaw"])):.5f}, '
                      f'0, 1, 0, {math.sin(math.radians(b["yaw"])):.5f}, 0, {math.cos(math.radians(b["yaw"])):.5f}, '
                      f'{b["at"][0]}, 0, {b["at"][1]})',
                      'script = ExtResource("build")',
                      f'kind = "{b["kind"]}"', f'footprint = Vector2({b["size"][0]}, {b["size"][1]})',
                      f'floors = {b["floors"]}', f'story_height = {b["story_height"]}',
                      f'label = "{b["label"]}"'])
dest = ROOT / "scenes/levels/mall_study.tscn"
dest.write_text("\n\n".join(scene) + "\n", encoding="utf-8")
print(json.dumps({"boundary_area_m2": plan["boundary_area_m2"], "buildings": len(buildings), "roads": len(roads),
                  "locations": len(plan["locations"]), "routes": len(plan["probe_routes"])}, ensure_ascii=False))
