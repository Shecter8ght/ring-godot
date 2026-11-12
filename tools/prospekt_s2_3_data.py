"""«Проспект», вторая очередь, этап 3 — данные плана и рейдовой сцены вокзала (вызывается из tools/prospekt_patch.py).

Правит текстом (повтор не дублирует): data/blockouts/prospekt.json (заход, места лута, маршруты проверки, места прогулки) и
scenes/levels/prospekt.tscn (заход «Вокзал, платформа», ящики лута, переехавшие с площадки).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ENTRY = (184.0, 260.0)
ENTRY_Y = 7.68

# платформа → восточный мост → конкорс → марш → зал → главный вход → площадь → переход южного плеча → сквер → … → Вокзальная → «Пролом»
SQUARE_PATH = [[155.0, 213.0], [155.0, 206.0], [155.0, 196.0], [155.0, 150.0], [148.0, 147.0], [130.0, 147.0], [104.0, 148.0], [103.3, 156.0]]
PARK_PATH = [[73.65, 152.0], [67.65, 153.6], [53.0, 158.5], [47.0, 158.5], [44.0, 156.0], [37.0, 153.6], [37.0, 148.0], [12.0, 146.0],
             [-8.0, 146.0], [-52.0, 146.0], [-55.0, 150.0]]
LANE_PATH = [[-55.0, 198.0], [-55.0, 202.0], [-60.0, 202.0]]
STREET_PATH = [[-140.0, 202.0], [-215.0, 202.0], [-222.5, 202.0], [-222.5, 190.0], [-222.5, 176.0], [-232.0, 176.0], [-245.6, 176.0], [-245.6, 170.0], [-245.6, 176.0], [-232.0, 176.0], [-222.5, 176.0], [-222.5, 190.0], [-222.5, 202.0], [-200.0, 202.0]]
UP = [[155.0, 206.0], [155.0, 212.0], [153.0, 218.0], [153.0, 221.3], [159.5, 221.3], [159.5, 222.0], [159.5, 230.6], [159.5, 231.2], [159.5, 231.8],
      [159.5, 237.0], [159.5, 240.0], [159.5, 244.0], [159.0, 247.0], [159.0, 252.0], [159.0, 259.2], [184.0, 259.2], [184.0, 260.0]]
ROUTE_S2S = (UP + UP[-3::-1][1:] + [[153.0, 221.3], [153.0, 218.0]] + SQUARE_PATH + PARK_PATH + LANE_PATH + STREET_PATH)
ROUTE_NEW = [[155.0, 200.0], [155.0, 212.0], [153.0, 218.0], [153.0, 222.0], [153.0, 229.0], [135.0, 229.0], [135.0, 221.3], [132.5, 221.3],
             [132.5, 222.0], [132.5, 230.6], [132.5, 231.2], [132.5, 231.8], [132.5, 237.0], [132.5, 240.0], [132.5, 244.0], [133.0, 247.0],
             [133.0, 252.0], [133.0, 258.0], [133.0, 260.5]]
ROUTE_WINGS = [[117.0, 216.0], [117.0, 223.0], [107.05, 226.0], [107.05, 228.5], [107.05, 233.5], [107.05, 234.6], [108.95, 234.6], [108.95, 233.5],
               [108.95, 228.6], [108.95, 226.0], [124.0, 226.0], [124.0, 244.0], [128.0, 244.0], [131.0, 244.0]]
ROUTE_LABELS = {
    "south_to_site": "вокзал: платформа → восточный мост → конкорс → марш → зал → главный вход → площадь → переход южного плеча → сквер → служебный проезд → Вокзальная → «Пролом»",
    "station_new": "новый вокзал: площадь → главный вход → зал → марш на +7,6 → конкорс → западный мост → платформа",
    "station_wings": "новый вокзал: кассовый зал → лестница западного крыла → второй этаж → терраса → дверь на конкорс"}


def _num(v: float) -> str:
    return repr(float(v))


def _route_text(rid: str, label: str, pts: list, extra: str = "") -> str:
    body = ",\n".join(f"    [{x}, {z}]" for x, z in pts)
    return ('  {\n   "id": "%s",\n   "label": "%s",\n   "max_open_m": 0.0,\n   "points": [\n%s\n   ]%s\n  }' % (rid, label, body, extra))


def plan_data() -> None:
    path = ROOT / "data" / "blockouts" / "prospekt.json"
    text = open(path, encoding="utf-8", newline="").read()
    # заход
    text = text.replace('"id": "south",\n   "label": "Юг, у насыпи",\n   "at": [181.3, 236.0]',
                        '"id": "south",\n   "label": "Вокзал, платформа",\n   "at": [%s, %s]' % (_num(ENTRY[0]), _num(ENTRY[1])))
    if '"label": "Вокзал, платформа"' not in text:
        raise SystemExit("prospekt.json: нет захода «Юг, у насыпи»")
    # лут, переехавший вместе с гаражами
    for old, new in (("[172.9, 0.0, 157.0]", "[172.9, 0.0, 121.0]"), ("[157.7, 0.0, 161.6]", "[143.0, 0.0, 198.4]")):
        if old in text:
            text = text.replace('"at": ' + old, '"at": ' + new, 1)
        elif ('"at": ' + new) not in text:
            raise SystemExit("prospekt.json: нет лута " + old)
    text = text.replace("схрон: под плитой у гаражей корпуса 3", "схрон: под скамьёй на привокзальной площади")
    # маршрут south_to_site переписан, новые — station_new, station_wings
    # south_to_site стоит в конце списка: перед ring_deck длинный маршрут делает его провал в полном прогоне (зависит от времени, см. STATUS)
    rx = re.compile(r'  \{\n   "id": "south_to_site",.*?\n   \]\n  \},\n', re.S)
    text, n = rx.subn("", text, count=1)
    if n != 1:
        raise SystemExit("маршрут south_to_site не найден")
    if '"id": "station_new"' not in text:
        tail = '\n   ],\n   "min_y": 10.5\n  }\n ],\n "checks"'
        if tail not in text:
            raise SystemExit("prospekt.json: нет конца probe_routes")
        extra = ",\n" + _route_text("station_new", ROUTE_LABELS["station_new"], ROUTE_NEW, ',\n   "min_y": 7.0')
        extra += ",\n" + _route_text("station_wings", ROUTE_LABELS["station_wings"], ROUTE_WINGS)
        extra += ",\n" + _route_text("south_to_site", ROUTE_LABELS["south_to_site"], ROUTE_S2S)
        text = text.replace(tail, '\n   ],\n   "min_y": 10.5\n  }' + extra + '\n ],\n "checks"', 1)
    # места прогулки: 18 — почтово-багажный терминал, 20 — новый вокзал
    text = text.replace('"id": 18,\n   "label": "Вокзал «Проспект»"', '"id": 18,\n   "label": "Почтово-багажный терминал"')
    if '"label": "Вокзал «Проспект»",\n   "at": [130.0' not in text:
        tail = '   "look": [-100.0, 112.0]\n  }\n ],'
        if tail not in text:
            raise SystemExit("prospekt.json: нет конца списка мест")
        text = text.replace(tail, tail[:-4] + ',\n  {\n   "id": 20,\n   "label": "Вокзал «Проспект»",\n   "at": [130.0, 175.0],\n'
                            '   "spawn": [146.0, 205.0],\n   "look": [146.0, 220.0]\n  }\n ],', 1)
    open(path, "w", encoding="utf-8", newline="").write(text)
    # рейдовая сцена
    path = ROOT / "scenes" / "levels" / "prospekt.tscn"
    text = open(path, encoding="utf-8", newline="").read()
    reps = [('position = Vector3(181.3, 0.08, 236)\ndisplay_name = "Юг, у насыпи"',
             'position = Vector3(%g, %g, %g)\ndisplay_name = "Вокзал, платформа"' % (ENTRY[0], ENTRY_Y, ENTRY[1])),
            ('position = Vector3(172.9, 0.6, 157)', 'position = Vector3(172.9, 0.6, 121)'),
            ('position = Vector3(157.7, 0.6, 161.6)', 'position = Vector3(143, 0.6, 198.4)'),
            ('display_name = "Под плитой у гаражей корпуса 3"', 'display_name = "Под скамьёй на привокзальной площади"')]
    for a, b in reps:
        if a in text:
            text = text.replace(a, b, 1)
        elif b not in text:
            raise SystemExit("prospekt.tscn: нет места для замены: " + a)
    open(path, "w", encoding="utf-8", newline="").write(text)
    print("  данные: заход «Вокзал, платформа», лут гаражей, маршруты south_to_site / station_new / station_wings, места прогулки 18 и 20")
