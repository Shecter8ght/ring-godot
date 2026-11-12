"""«Проспект», вторая очередь, этап 4 — данные плана и рейдовой сцены малых зон (вызывается из tools/prospekt_patch.py).

Правит текстом (повтор не дублирует): data/blockouts/prospekt.json (маршруты проверки, места прогулки, места лута лагеря) и
scenes/levels/prospekt.tscn (ящики лута и пост лагеря переехали по зонам).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

POLICE_F1 = [[-192.0, 10.0], [-192.0, 14.0], [-192.0, 18.5], [-192.0, 21.0], [-193.0, 21.6], [-193.0, 24.6], [-193.0, 21.6], [-196.0, 19.5],
             [-199.5, 19.5], [-205.0, 19.5], [-209.5, 19.5], [-213.0, 19.5], [-213.0, 22.0]]
POLICE_F2 = [[-192.0, 10.0], [-192.0, 18.5], [-189.0, 21.5], [-187.05, 21.8], [-187.05, 24.0], [-187.05, 26.0], [-187.05, 27.2], [-186.6, 28.6],
             [-185.25, 28.6], [-185.25, 27.2], [-185.25, 25.5], [-185.25, 23.9], [-185.5, 22.8], [-185.5, 22.0], [-195.0, 22.0], [-203.0, 22.0],
             [-203.0, 19.5]]
CAMP_WALK = [[137.5, -2.0], [140.0, -1.5], [142.5, -0.6], [144.5, -0.5], [146.2, -2.0], [147.6, -3.5], [149.5, -3.5], [152.0, -2.0], [164.0, -2.0],
             [164.0, -20.0], [164.0, -30.0], [161.5, -33.5], [164.0, -30.0], [165.8, -26.0], [168.0, -22.5], [174.0, -22.5], [166.0, -22.5],
             [166.0, 10.0], [168.0, 20.0], [176.5, 28.0], [166.0, 44.5], [166.0, 52.0], [166.0, 55.4], [154.5, 55.4], [154.5, 59.5]]
CAMP_TOWER = [[159.0, -40.0], [159.0, -45.8], [157.5, -45.8], [150.0, -45.8], [146.5, -45.8], [143.5, -45.0]]
WC_UNDER = [[-41.0, 111.0], [-36.0, 111.0], [-33.0, 111.0], [-30.0, 111.0], [-27.5, 109.2], [-26.0, 108.0], [-25.2, 108.0], [-25.2, 111.0],
            [-25.2, 114.0], [-24.0, 114.0], [-22.5, 114.0], [-20.0, 112.5], [-19.0, 111.0], [-16.0, 111.0], [-12.0, 111.0], [-8.0, 111.0]]
WC_UNDER_IN = WC_UNDER[:11] + [[-21.0, 112.5]]
LABELS = {
    "police_f1": "отдел полиции, этаж 1: тротуар → вход → холл → дежурная часть; холл → камеры → дверь во двор → двор",
    "police_f2": "отдел полиции, этаж 2: тротуар → холл → лестница (два марша) → коридор → кабинет начальника",
    "camp_walk": "лагерь эвакуации: западные ворота → фильтр → медсанбат → вертолётная площадка → южные ворота",
    "camp_tower": "лагерь эвакуации: вышка у северо-западного угла по ступенчатому маршу",
    "wc_under": "подземный туалет: западный спуск → М → кладовая → Ж → восточный спуск",
    "wc_under_in": "подземный туалет: западный спуск → М → кладовая → Ж (конец — внизу)",
}
# новая раскладка лута лагеря: (прежнее положение) → (новое); y плана 0,0, у рейдовой сцены 0,6
LOOT_MOVES = [((145.3, -31.3), (169.3, -31.3)), ((169.3, -31.3), (162.0, -36.5)), ((181.3, -27.3), (160.5, 8.0)),
              ((149.3, -3.3), (181.3, -31.3)), ((165.3, 0.7), (175.0, 13.2)), ((181.3, -1.3), (160.0, 51.0)),
              ((163.3, 18.7), (153.0, 8.5)), ((166.3, 43.0), (172.0, 51.0))]


def _num(v: float) -> str:
    return repr(float(v))


def _g(v: float) -> str:
    return ("%g" % v)


def _route_text(rid: str, label: str, pts: list, extra: str = "") -> str:
    body = ",\n".join(f"    [{x}, {z}]" for x, z in pts)
    return ('  {\n   "id": "%s",\n   "label": "%s",\n   "max_open_m": 0.0,\n   "points": [\n%s\n   ]%s\n  }' % (rid, label, body, extra))


def plan_data(p=None) -> None:
    path = ROOT / "data" / "blockouts" / "prospekt.json"
    text = open(path, encoding="utf-8", newline="").read()
    # ---- маршруты: перед south_to_site (он стоит последним — порядок важен для ring_deck)
    if '"id": "police_f1"' not in text:
        anchor = '  {\n   "id": "south_to_site",'
        if anchor not in text:
            raise SystemExit("prospekt.json: нет маршрута south_to_site")
        new = (_route_text("police_f1", LABELS["police_f1"], POLICE_F1) + ",\n"
               + _route_text("police_f2", LABELS["police_f2"], POLICE_F2, ',\n   "min_y": 3.0') + ",\n"
               + _route_text("camp_walk", LABELS["camp_walk"], CAMP_WALK) + ",\n"
               + _route_text("camp_tower", LABELS["camp_tower"], CAMP_TOWER, ',\n   "min_y": 5.0') + ",\n"
               + _route_text("wc_under", LABELS["wc_under"], WC_UNDER) + ",\n"
               + _route_text("wc_under_in", LABELS["wc_under_in"], WC_UNDER_IN, ',\n   "max_y": -2.5') + ",\n")
        text = text.replace(anchor, new + anchor, 1)
    # ---- место прогулки 15 и новое 21
    old15 = '"label": "Пункт эвакуации · палатки",\n   "at": [163.3, -11.3],\n   "spawn": [135.3, -13.3],'
    new15 = '"label": "Пункт эвакуации · палатки",\n   "at": [163.3, -11.3],\n   "spawn": [151.0, -2.0],'
    if old15 in text:
        text = text.replace(old15, new15, 1)
    elif new15 not in text:
        raise SystemExit("prospekt.json: нет места прогулки 15")
    if '"label": "Отдел полиции"' not in text:
        tail = '   "look": [146.0, 220.0]\n  }\n ],'
        if tail not in text:
            raise SystemExit("prospekt.json: нет конца списка мест")
        text = text.replace(tail, tail[:-4] + ',\n  {\n   "id": 21,\n   "label": "Отдел полиции",\n   "at": [-192.0, 16.0],\n'
                            '   "spawn": [-192.0, 9.0],\n   "look": [-192.0, 20.0]\n  }\n ],', 1)
    # ---- лут лагеря: одновременная замена (через метки, чтобы пары не наложились)
    marks = []
    for i, ((ox, oz), (nx, nz)) in enumerate(LOOT_MOVES):
        old = '"at": [%s, 0.0, %s]' % (_num(ox), _num(oz))
        new = '"at": [%s, 0.0, %s]' % (_num(nx), _num(nz))
        if old in text:
            text = text.replace(old, "@@%d@@" % i, 1)
            marks.append((i, new))
        elif new not in text:
            raise SystemExit("prospekt.json: нет лута " + old)
    for i, new in marks:
        text = text.replace("@@%d@@" % i, new, 1)
    open(path, "w", encoding="utf-8", newline="").write(text)
    # ---- рейдовая сцена: ящики и пост
    path = ROOT / "scenes" / "levels" / "prospekt.tscn"
    text = open(path, encoding="utf-8", newline="").read()
    marks = []
    for i, ((ox, oz), (nx, nz)) in enumerate(LOOT_MOVES):
        old = "position = Vector3(%s, 0.6, %s)" % (_g(ox), _g(oz))
        new = "position = Vector3(%s, 0.6, %s)" % (_g(nx), _g(nz))
        if old in text:
            text = text.replace(old, "@@%d@@" % i, 1)
            marks.append((i, new))
        elif new not in text:
            raise SystemExit("prospekt.tscn: нет ящика " + old)
    for i, new in marks:
        text = text.replace("@@%d@@" % i, new, 1)
    old = "position = Vector3(159.3, 0.06, -5.3)\nradius = 16"
    new = "position = Vector3(157.5, 0.06, -0.5)\nradius = 16"
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise SystemExit("prospekt.tscn: нет поста Camp_PMC")
    open(path, "w", encoding="utf-8", newline="").write(text)
    if p is not None:
        print("  данные: маршруты police_f1/f2, camp_walk, camp_tower, wc_under, wc_under_in; места 15 (правка) и 21; лут лагеря по зонам, пост Camp_PMC")
