# -*- coding: utf-8 -*-
"""Рейдовая карта «Проспект»: сцена уровня поверх серого блокаута (как scenes/levels/mall_map.tscn поверх черновика ТЦ).

    python -X utf8 tools/build_prospekt.py          — сначала блокаут (data/blockouts/prospekt.json, prospekt_study.tscn)
    python -X utf8 tools/build_prospekt_raid.py     — затем рейд: data/sectors/prospekt.json, scenes/levels/prospekt.tscn,
                                                       scenes/levels/prospekt/prospekt_environment.tres
    tools/godot.cmd --headless res://tools/bake_prospekt_nav.tscn   — кэш навигации data/navigation/prospekt
    tools/godot.cmd --headless res://tools/prospekt_raid_check.tscn — проверка рейда

Заходы и выходы — из плана блокаута (spawns, exits; кордон — только старт пролога, в обычный рейд не заходят).
Население слоями (docs/design/enemy_population.md): посты у мест добычи, кордон и штаб у палаток держат ЧВК
«Периметр» (AIPost.arch = "pmc"), патрули по улицам, снайперы на крышах и каркасе, подход с краёв карты.
Свет — свой (AGENTS.md п. 10): физическое небо и низкое солнце блокаута, время суток и погода — RaidAtmosphere.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "data" / "blockouts" / "prospekt.json"
SECTOR = ROOT / "data" / "sectors" / "prospekt.json"
SCENE = ROOT / "scenes" / "levels" / "prospekt.tscn"
ENV = ROOT / "scenes" / "levels" / "prospekt" / "prospekt_environment.tres"

plan = json.loads(PLAN.read_text(encoding="utf-8"))
EMB_TOP = 6.3                                                   # верх балласта на насыпи

# ---------------------------------------------------------------- заходы и выходы
ENTRY_Y = {"station": 0.12}
entries = [(s["label"], s["at"][0], ENTRY_Y.get(s["id"], 0.08), s["at"][1]) for s in plan["spawns"] if s["id"] != "cordon"]
EXIT_Y = {"По путям на запад": EMB_TOP}
exits = [(e["label"], e["at"][0], EXIT_Y.get(e["label"], 0.08), e["at"][1], 6.0 if "Тоннель" in e["label"] else 4.5) for e in plan["exits"]]

# ---------------------------------------------------------------- население
# (имя, x, y, z, радиус, группа (от, до), тип, обязателен с N игроков, вес, метка взаимоисключения)
POSTS = [
    ("Cordon_PMC", -203.0, 0.08, 0.0, 10.0, (3, 4), "pmc", 1, 1.0, ""),
    ("Camp_PMC", 128.0, 0.06, 26.0, 16.0, (3, 4), "pmc", 0, 3.0, ""),
    ("Bank_Hall", -21.0, 0.12, -44.0, 12.0, (2, 3), "", 0, 3.0, "bank"),
    ("Bank_Vault", -30.0, -3.2, -46.0, 8.0, (1, 2), "", 0, 2.0, "bank"),
    ("Yarus_Hall", -102.0, 0.05, 66.0, 18.0, (2, 4), "", 0, 3.0, ""),
    ("Yarus_Dock", -100.0, 0.02, 96.0, 12.0, (2, 3), "", 0, 1.5, ""),
    ("Station_Hall", -116.0, 0.12, 226.0, 14.0, (2, 3), "", 0, 2.0, ""),
    ("Tower_Court", -14.0, 0.1, 45.0, 14.0, (2, 3), "", 0, 1.5, ""),
    ("Square", -14.0, 0.1, 82.0, 16.0, (2, 3), "", 0, 1.5, ""),
    ("Train_Wreck", -6.0, 0.12, 222.0, 14.0, (2, 3), "", 0, 2.0, ""),
    ("Parking", -128.0, -3.2, -60.0, 20.0, (2, 3), "", 0, 2.0, ""),
    ("Site", -108.0, 0.05, 132.0, 16.0, (2, 3), "", 0, 1.5, ""),
    ("Corpus3_Lot", 86.0, 0.05, 150.0, 16.0, (2, 3), "", 0, 1.0, ""),
    ("Vershina_Plaza", 50.0, 0.1, -12.0, 16.0, (2, 3), "", 0, 1.5, ""),
    ("Yard_ZhK", -150.0, 0.05, -100.0, 16.0, (2, 3), "", 0, 1.0, ""),
    ("House7_Yard", -190.0, 0.05, 85.0, 14.0, (2, 3), "", 0, 1.0, ""),
]
ROUTES = [
    ("Route_Avenue", "Проспект: тротуары от перехода до поворота", False,
     [(-140.0, 0.15, 13.0), (-100.0, 0.15, 13.0), (-60.0, 0.15, 13.5), (-30.0, 0.15, -13.0), (10.0, 0.15, -14.0)]),
    ("Route_South", "Южное плечо: вдоль парковки корпуса 3 к тоннелю", False,
     [(66.0, 0.15, 80.0), (66.0, 0.15, 140.0), (66.0, 0.15, 200.0), (44.0, 0.15, 230.0), (44.0, 0.15, 160.0), (44.0, 0.15, 100.0)]),
    ("Route_Yard", "Хозяйственный проезд двора вдоль забора", False,
     [(-200.0, 0.08, -117.0), (-150.0, 0.08, -117.0), (-110.0, 0.08, -117.0), (-55.0, 0.08, -117.0)]),
    ("Route_Square", "Сквер: от дома на повороте к вагонам", False,
     [(-40.0, 0.1, 60.0), (10.0, 0.1, 62.0), (12.0, 0.1, 140.0), (-40.0, 0.1, 146.0), (-30.0, 0.1, 186.0), (10.0, 0.1, 206.0)]),
    ("Route_Station", "Привокзальная площадь", False,
     [(-60.0, 0.12, 206.0), (-100.0, 0.12, 207.0), (-140.0, 0.12, 206.0)]),
]
# (имя, x, y, z, курс взгляда в градусах (0 — на север, −Z), сектор)
NESTS = [
    ("Nest_BankRoof", -20.0, 12.3, -32.5, 180.0, 90.0),
    ("Nest_SiteTop", -130.0, 25.0, 146.0, 0.0, 80.0),
    ("Nest_StationRoof", -120.0, 13.0, 232.0, 0.0, 80.0),
    ("Nest_PodiumRoof", -30.0, 4.65, 22.5, 0.0, 90.0),
]
ARRIVALS = [
    ("Arrive_YardGap", -145.0, 0.08, -119.0),
    ("Arrive_StationWest", -146.0, 0.12, 205.0),
    ("Arrive_East", 154.0, 0.08, 100.0),
    ("Arrive_NorthEast", 150.0, 0.08, -118.0),
    ("Arrive_RailsWest", -146.0, EMB_TOP, 272.8),
]

# ---------------------------------------------------------------- данные сектора
sector = {
    "id": "prospekt",
    "name": "Проспект",
    "_comment": ("Рейдовая карта «Проспект» (docs/design/prospekt_map.md): геометрия — серый блокаут scenes/levels/prospekt_study.tscn "
                 "(tools/build_prospekt.py) внутри scenes/levels/prospekt.tscn (tools/build_prospekt_raid.py); заходы, выходы, посты, "
                 "патрули, гнёзда и подход — узлы сцены уровня. Свет свой (AGENTS.md п. 10). Навигация — кэш data/navigation/prospekt "
                 "(tools/bake_prospekt_nav.tscn после правки блокаута)."),
    "layout": "cartesian_scene",
    "greybox": True,
    "bounds": plan["bounds"],
    "boundary": plan["boundary"],
    "units": "metres",
    "north": "-Z",
    "spawn": [entries[0][1], entries[0][2], entries[0][3]],
    "camera_yaw": 0,
    "nav_cache": "res://data/navigation/prospekt",
    "events": {"off": ["power"], "at": {"drop": [-14.0, 0.1, 100.0], "pmc": [-60.0, 0.1, 205.0]},
               "drop_text": "Вертолёт над сквером — что-то сбросили",
               "pmc_text": "У вокзала заглушили мотор. Хлопнули двери."},
    "rooms": [],
}
SECTOR.write_text(json.dumps(sector, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

# ---------------------------------------------------------------- окружение: умолчания Godot (владелец 2026-10-26 —
# «вернуть к самым дефолтным значениям, от которых дальше будем танцевать»); время суток и погода рейда — поверх
# (RaidAtmosphere, общие для всех карт), своих множителей света ("light" сектора) у карты нет
ENV.parent.mkdir(parents=True, exist_ok=True)
ENV.write_text("\n".join([
    '[gd_resource type="Environment" load_steps=3 format=3]',
    '',
    '[sub_resource type="ProceduralSkyMaterial" id="SkyMat"]',
    '',
    '[sub_resource type="Sky" id="Sky"]', 'sky_material = SubResource("SkyMat")',
    '',
    '[resource]',
    'background_mode = 2', 'sky = SubResource("Sky")', 'tonemap_mode = 2', 'glow_enabled = true',
    '']), encoding="utf-8", newline="\n")

# ---------------------------------------------------------------- сцена уровня
def v3(x: float, y: float, z: float) -> str:
    return "Vector3(%g, %g, %g)" % (x, y, z)


lines = [
    '[gd_scene format=3]',
    '',
    '[ext_resource type="Script" path="res://src/world/sector_level.gd" id="1"]',
    '[ext_resource type="PackedScene" path="res://scenes/levels/prospekt_study.tscn" id="2"]',
    '[ext_resource type="PackedScene" path="res://scenes/world/spawn_point.tscn" id="4"]',
    '[ext_resource type="PackedScene" path="res://scenes/world/extraction_point.tscn" id="5"]',
    '[ext_resource type="Environment" path="res://scenes/levels/prospekt/prospekt_environment.tres" id="6"]',
    '[ext_resource type="PackedScene" path="res://scenes/player/camera_rig.tscn" id="7"]',
    '[ext_resource type="PackedScene" path="res://scenes/world/ai_post.tscn" id="8"]',
    '[ext_resource type="PackedScene" path="res://scenes/world/ai_route.tscn" id="9"]',
    '[ext_resource type="PackedScene" path="res://scenes/world/ai_nest.tscn" id="10"]',
    '[ext_resource type="PackedScene" path="res://scenes/world/ai_arrival.tscn" id="11"]',
    '[ext_resource type="PackedScene" path="res://scenes/world/loot_container.tscn" id="12"]',
    '',
    '[node name="Prospekt" type="Node3D"]',
    'script = ExtResource("1")',
    'sector_path = "res://data/sectors/prospekt.json"',
    'metadata/purpose = "Рейдовая карта «Проспект»: серый блокаут, заходы, выходы, население — tools/build_prospekt_raid.py"',
    '',
    '[node name="World" parent="." groups=["nav_source"] instance=ExtResource("2")]',
    '',
    '[node name="WorldEnvironment" parent="World" index="0"]',
    'environment = ExtResource("6")',
    '',
    '[node name="EveningSun" parent="World" index="1"]',
    'visible = false',
    '',
    '[node name="Gameplay" type="Node3D" parent="."]',
]
for i, (label, x, y, z) in enumerate(entries):
    lines += ['', '[node name="Entry_%d" parent="Gameplay" instance=ExtResource("4")]' % i, 'position = ' + v3(x, y, z),
              'display_name = "%s"' % label, 'entry = true']
for i, (label, x, y, z, r) in enumerate(exits):
    lines += ['', '[node name="Extraction_%d" parent="Gameplay" instance=ExtResource("5")]' % i, 'position = ' + v3(x, y, z),
              'display_name = "%s"' % label, 'radius = %g' % r]
lines += ['', '[node name="Population" type="Node3D" parent="Gameplay"]', '', '[node name="Posts" type="Node3D" parent="Gameplay/Population"]']
for (name, x, y, z, r, size, arch, always, weight, excl) in POSTS:
    lines += ['', '[node name="%s" parent="Gameplay/Population/Posts" instance=ExtResource("8")]' % name, 'position = ' + v3(x, y, z),
              'radius = %g' % r, 'group_size = Vector2i(%d, %d)' % size, 'weight = %g' % weight]
    if arch:
        lines.append('arch = "%s"' % arch)
    if always:
        lines.append('always_from = %d' % always)
    if excl:
        lines.append('exclusive = "%s"' % excl)
lines += ['', '[node name="Routes" type="Node3D" parent="Gameplay/Population"]']
for (name, title, loop, pts) in ROUTES:
    lines += ['', '[node name="%s" parent="Gameplay/Population/Routes" instance=ExtResource("9")]' % name, 'title = "%s"' % title]
    if loop:
        lines.append('loop = true')
    for k, (x, y, z) in enumerate(pts):
        lines += ['', '[node name="P%02d" type="Marker3D" parent="Gameplay/Population/Routes/%s"]' % (k + 1, name), 'position = ' + v3(x, y, z)]
lines += ['', '[node name="Nests" type="Node3D" parent="Gameplay/Population"]']
for (name, x, y, z, yaw, sector_deg) in NESTS:
    # курс взгляда: гнездо смотрит вдоль −Z маркера; поворот вокруг Y на −курс (0 — север, 180 — юг)
    c, s = round(math.cos(math.radians(-yaw)), 6), round(math.sin(math.radians(-yaw)), 6)
    lines += ['', '[node name="%s" parent="Gameplay/Population/Nests" instance=ExtResource("10")]' % name,
              'transform = Transform3D(%g, 0, %g, 0, 1, 0, %g, 0, %g, %g, %g, %g)' % (c, -s, s, c, x, y, z),
              'sector_deg = %g' % sector_deg]
lines += ['', '[node name="Arrivals" type="Node3D" parent="Gameplay/Population"]']
for (name, x, y, z) in ARRIVALS:
    lines += ['', '[node name="%s" parent="Gameplay/Population/Arrivals" instance=ExtResource("11")]' % name, 'position = ' + v3(x, y, z)]
# места лута плана (владелец 2026-10-24, п. 8) — настоящие контейнеры рейда: вид места → облик и время обыска,
# ценность и пометка → таблица data/loot.json; в залах StudyBuilding свои места лута, их здесь нет
LOOK = {"crate": 5, "backpack": 4, "suitcase": 4, "body": 3, "car": 0, "register": 0, "safe": 1, "cabinet": 0, "loose": 0,
        "cells": 2, "weapon": 2, "med": 4}
SEARCH = {"crate": 3.0, "backpack": 2.5, "suitcase": 2.5, "body": 4.0, "car": 3.5, "register": 2.0, "safe": 6.0, "cabinet": 2.5,
          "loose": 1.5, "cells": 5.0, "weapon": 3.0, "med": 2.0}


def loot_table(kind: str, tier: str, note: str) -> str:
    n = note.lower()
    if tier == "med" or kind == "med":
        return "pharmacy"
    if kind == "safe" or kind == "cells":
        if "ломбард" in n or "золот" in n:
            return "jewelry_safe"
        if any(w in n for w in ("банк", "хранилищ", "касс", "выручк", "инкассатор", "денег", "деньг", "ячейк")):
            return "bank"
        return "office"
    if tier == "weapon":
        return "pmc" if ("чвк" in n or "бойц" in n) else "security"
    if kind == "body":
        return "pmc" if "чвк" in n else "marauder"
    if kind == "register":
        return "register"
    if tier == "good":
        if "инкассатор" in n or "банк" in n:
            return "bank"
        if "сервер" in n or "диск" in n:
            return "server_rack"
        return "electronics" if kind in ("crate", "loose", "backpack") else "components"
    if kind == "cabinet":
        return "office"
    if kind in ("crate",):
        return "storage"
    if kind == "car":
        return "home"
    return "home" if kind in ("backpack", "suitcase") else "shelf"


lines += ['', '[node name="Loot" type="Node3D" parent="Gameplay"]']
for i, l in enumerate(plan.get("loot", [])):
    x, y, z = l["at"]
    title = l["note"].split(":")[-1].strip() if l["note"] else "Тайник"
    title = (title[:1].upper() + title[1:]).replace('"', "'")
    lines += ['', '[node name="Loot_%d" parent="Gameplay/Loot" instance=ExtResource("12")]' % i,
              'position = ' + v3(x, y + 0.6, z), 'display_name = "%s"' % title,
              'table = "%s"' % loot_table(l["kind"], l["tier"], l["note"]), 'search_s = %g' % SEARCH[l["kind"]],
              'look = %d' % LOOK[l["kind"]]]
lines += ['', '[node name="AI_Spawns" type="Node3D" parent="Gameplay"]']
for (name, x, y, z, *_rest) in POSTS:
    if _rest[2] == "pmc":
        continue
    lines += ['', '[node name="AI_%s" type="Marker3D" parent="Gameplay/AI_Spawns" groups=["ai_spawn_points"]]' % name, 'position = ' + v3(x, y, z)]
lines += [
    '', '[node name="Navigation" type="Node3D" parent="."]',
    '', '[node name="Audio" type="Node3D" parent="."]',
    '', '[node name="Lighting" type="Node3D" parent="."]',
    '', '[node name="WorldEnvironment" type="WorldEnvironment" parent="."]', 'environment = ExtResource("6")',
    '', '[node name="Sun" type="DirectionalLight3D" parent="."]',
    'transform = Transform3D(-0.866023, -0.433016, 0.250001, 0, 0.499998, 0.866027, -0.500003, 0.75, -0.43301, 0, 0, 0)', 'shadow_enabled = true',
    '', '[node name="CameraRig" parent="." instance=ExtResource("7")]',
    '', '[node name="HUD" type="CanvasLayer" parent="."]',
    '', '[node name="Root" type="Control" parent="HUD"]',
    'layout_mode = 3', 'anchors_preset = 15', 'anchor_right = 1.0', 'anchor_bottom = 1.0', 'grow_horizontal = 2', 'grow_vertical = 2',
    'mouse_filter = 2',
    '', '[node name="Status" type="Label" parent="HUD/Root"]',
    'offset_left = 24.0', 'offset_top = 20.0', 'offset_right = 700.0', 'offset_bottom = 48.0', 'text = "HP 100"',
    '', '[node name="Dead" type="Label" parent="HUD/Root"]', 'visible = false',
    '',
]
SCENE.write_text("\n".join(lines), encoding="utf-8", newline="\n")
print(json.dumps({"entries": len(entries), "exits": len(exits), "posts": len(POSTS), "routes": len(ROUTES), "nests": len(NESTS),
                  "arrivals": len(ARRIVALS), "scene": str(SCENE.relative_to(ROOT))}, ensure_ascii=False))
