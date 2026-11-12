"""«Проспект», вторая очередь, этап 2 — данные плана и рейдовой сцены «Яруса» (вызывается из tools/prospekt_patch.py).

Правит текстом (повтор не дублирует): data/blockouts/prospekt.json (места лута, маршруты проверки, места прогулки) и
scenes/levels/prospekt.tscn (ворота рампы, служебная дверь, посты, метки пролога, ящики лута «Яруса» и двора).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# маршруты проверки: пролог и служебная ветка переписаны под новый путь, три новых — вертикальные связи и крыша
Y_TAIL = [[-100.0, 79.0], [-100.0, 84.0], [-100.0, 90.0], [-100.0, 96.0], [-100.0, 113.0], [-98.0, 114.0], [-98.0, 123.0], [-96.0, 127.5],
          [-62.0, 128.5], [-58.5, 128.0], [-55.0, 131.0]]
ROUTE_STAFF = [[-96.0, 44.0], [-96.0, 46.0], [-96.0, 50.3], [-66.0, 50.3], [-66.0, 50.6], [-63.2, 50.6], [-63.2, 81.0], [-63.2, 83.0], [-68.0, 84.0],
               [-68.0, 90.0], [-68.6, 92.0], [-68.6, 100.8], [-72.0, 100.8], [-75.0, 94.8], [-100.0, 94.8], [-100.0, 113.0], [-98.0, 115.0]]
ROUTE_VERT = [[-108.0, 40.0], [-108.0, 46.0], [-108.0, 52.0], [-108.0, 78.0], [-110.5, 78.0], [-110.5, 61.5], [-110.5, 59.5], [-100.0, 59.5], [-90.0, 59.5],
              [-90.0, 78.0], [-91.0, 79.5], [-91.0, 86.0], [-91.0, 90.0], [-106.5, 90.0], [-106.5, 116.5], [-140.8, 116.5], [-140.8, 102.0],
              [-136.0, 102.0], [-136.0, 114.0], [-98.0, 114.0], [-98.0, 123.0], [-96.0, 127.0]]
ROUTE_ROOF = [[-150.0, 146.0], [-150.0, 142.0], [-148.3, 138.4], [-145.8, 133.0], [-143.5, 128.0], [-141.2, 123.0], [-139.0, 118.2], [-139.0, 115.0],
              [-139.0, 97.5], [-143.7, 97.5], [-143.7, 100.0], [-143.7, 113.5], [-143.7, 114.5]]
ROUTE_FIRE = [[-143.7, 114.5], [-143.7, 113.5], [-143.7, 100.0], [-143.7, 97.5], [-139.0, 97.5], [-139.0, 112.0]]
ROUTE_LABELS = {
    "prologue": "пролог: кордон → кофейня → переход → «Ярус» (тамбур, зал, приёмка) → склад → док → двор разгрузки → калитка → сквер → вагоны → тоннель",
    "prologue_staff": "пролог: тамбур «Яруса» → служебный коридор → Л1 → служебный двор → склад → к доку",
    "yarus_vertical": "«Ярус»: тамбур → эскалатор → галерея → «к мосткам» → мостки → лестница на пол склада → док → двор",
    "yarus_roof": "«Ярус»: стройка → упавшая стрела → крыша склада → пожарная лестница вниз",
    "yarus_roof_fire": "«Ярус»: двор → пожарная лестница вверх → крыша склада"}
LOOT_MOVES = [
    ([-137.4, 0.0, 53.0], "касса", [-130.0, 0.0, 56.0]),
    ([-66.1, 0.0, 64.0], "стеллаж «Яруса»", [-84.1, 0.0, 64.0]),
    ([-66.1, 0.0, 74.0], "стеллаж «Яруса»", [-84.1, 0.0, 74.0]),
    ([-112.0, 0.0, 84.0], "склад «Яруса»", [-116.0, 0.0, 84.6]),
    ([-92.0, 0.0, 84.0], "склад «Яруса»", [-96.0, 0.0, 84.5]),
    ([-90.0, 0.0, 86.0], "кабинет администратора: сейф", [-139.6, 6.0, 85.0]),
    ([-118.0, 0.0, 103.6], "контейнер на разгрузке", [-116.0, 0.0, 104.0]),
    ([-132.0, 0.0, 100.5], "фура на разгрузке", [-127.8, 0.0, 126.0]),
    ([-112.0, 0.0, 95.0], "ящики на разгрузке", [-110.0, 0.0, 94.0]),
]
# узлы рейдовой сцены: имя → новая позиция; метки пролога, посты, ящики лута «Яруса» и его двора
NODE_MOVES = [
    ("Yarus_Dock", "Vector3(-100, 0.02, 106)"), ("AI_Yarus_Dock", "Vector3(-100, 0.02, 106)"),
    ("Site", "Vector3(-108, 0.05, 148)"), ("AI_Site", "Vector3(-108, 0.05, 148)"),
    ("LateBags", "Vector3(-92, 0.1, 114.5)"), ("Hall_Cart", "Vector3(-122, 0.05, 66)"), ("Hall_Till", "Vector3(-126.5, 0.05, 53.6)"), ("Dock", "Vector3(-101, 0.05, 114)"),
    ("Loot_140", "Vector3(-130, 0.6, 56)"), ("Loot_138", "Vector3(-84.1, 0.6, 64)"), ("Loot_139", "Vector3(-84.1, 0.6, 74)"),
    ("Loot_144", "Vector3(-116, 0.6, 84.6)"), ("Loot_145", "Vector3(-96, 0.6, 84.5)"), ("Loot_147", "Vector3(-139.6, 6.6, 85)"),
    ("Loot_236", "Vector3(-116, 0.6, 104)"), ("Loot_278", "Vector3(-127.8, 0.6, 126)"), ("Loot_279", "Vector3(-110, 0.6, 94)"),
]


def _num(v: float) -> str:
    return repr(float(v))


def _route_text(rid: str, label: str, pts: list, extra: str = "") -> str:
    body = ",\n".join(f"    [{x}, {z}]" for x, z in pts)
    return ('  {\n   "id": "%s",\n   "label": "%s",\n   "max_open_m": 0.0,\n   "points": [\n%s\n   ]%s\n  }' % (rid, label, body, extra))


def plan_data() -> None:
    path = ROOT / "data" / "blockouts" / "prospekt.json"
    text = open(path, encoding="utf-8", newline="").read()
    for old, note, new in LOOT_MOVES:
        rx = re.compile(r'"at": \[%s, %s, %s\],(\n   "kind": "[a-z]+",\n   "tier": "[a-z]+",\n   "note": "%s")' %
                        (re.escape(_num(old[0])), re.escape(_num(old[1])), re.escape(_num(old[2])), re.escape(note)))
        text, n = rx.subn(lambda m: '"at": [%s, %s, %s],%s' % (_num(new[0]), _num(new[1]), _num(new[2]), m.group(1)), text, count=1)
        if n == 0 and ('"at": [%s, %s, %s]' % (_num(new[0]), _num(new[1]), _num(new[2]))) not in text:
            raise SystemExit(f"лут «{note}» не найден ни на старом, ни на новом месте")
    # пролог: хвост маршрута от тамбура до (−55; 131); дальше как был — (−52; 140) …
    m = None if "[-55.0, 131.0]" in text else re.search(r'\[-108\.0, 46\.0\],\n    \[-108\.0, 52\.0\],.*?\[-55\.0, 112\.0\]', text, re.S)
    if m:
        pts = [[-108.0, 46.0], [-108.0, 52.0], [-108.0, 64.0], [-108.0, 78.0]] + Y_TAIL
        body = ",\n".join("    [%s, %s]" % (_num(a), _num(b)) for a, b in pts)
        text = text[:m.start()] + body.lstrip() + text[m.end():]
    elif "[-55.0, 131.0]" not in text:
        raise SystemExit("маршрут prologue: нет ни старого, ни нового хвоста")
    text = re.sub(r'("id": "prologue",\n   "label": )"[^"]*"', lambda mm: mm.group(1) + '"%s"' % ROUTE_LABELS["prologue"], text, count=1)
    if '"id": "yarus_vertical"' not in text:
        tail = '\n   ]\n  }\n ],\n "checks"'
        if tail not in text:
            raise SystemExit("prospekt.json: нет конца probe_routes")
        extra = ""
        for rid, pts, ex in (("yarus_vertical", ROUTE_VERT, ""), ("yarus_roof", ROUTE_ROOF, ""), ("yarus_roof_fire", ROUTE_FIRE, ',\n   "min_y": 10.5')):
            extra += ",\n" + _route_text(rid, ROUTE_LABELS[rid], pts, ex)
        text = text.replace(tail, '\n   ]\n  }' + extra + '\n ],\n "checks"', 1)
    for rid, pts in (("prologue_staff", ROUTE_STAFF), ("yarus_vertical", ROUTE_VERT), ("yarus_roof", ROUTE_ROOF), ("yarus_roof_fire", ROUTE_FIRE)):
        rx = re.compile(r'(\{\n   "id": "%s",\n   "label": )"[^"]*"(,\n   "max_open_m": [0-9.]+,\n   "points": \[\n).*?(\n   \])' % rid, re.S)
        body = ",\n".join("    [%s, %s]" % (_num(a), _num(b)) for a, b in pts)
        text, n = rx.subn(lambda mm: mm.group(1) + '"%s"' % ROUTE_LABELS[rid] + mm.group(2) + body + mm.group(3), text, count=1)
        if n != 1:
            raise SystemExit(f"маршрут {rid} не найден")
    # места прогулки: 8 — спавн на стройку, 19 — склад «Яруса»
    text = text.replace('"label": "Стройка за «Ярусом»",\n   "at": [-108.0, 165.0],\n   "spawn": [-100.0, 116.0]',
                        '"label": "Стройка за «Ярусом»",\n   "at": [-108.0, 165.0],\n   "spawn": [-100.0, 142.0]')
    if '"label": "Склад «Яруса»"' not in text:
        tail = '   "label": "Вокзал «Проспект»",\n   "at": [-116.0, 229.0],\n   "spawn": [-116.0, 204.0],\n   "look": [-116.0, 229.0]\n  }\n ],'
        if tail not in text:
            raise SystemExit("prospekt.json: нет конца списка мест")
        text = text.replace(tail, tail[:-4] + ',\n  {\n   "id": 19,\n   "label": "Склад «Яруса»",\n   "at": [-106.0, 104.0],\n   "spawn": [-100.0, 94.8],\n   "look": [-100.0, 112.0]\n  }\n ],', 1)
    open(path, "w", encoding="utf-8", newline="").write(text)
    # рейдовая сцена
    path = ROOT / "scenes" / "levels" / "prospekt.tscn"
    text = open(path, encoding="utf-8", newline="").read()
    for name, pos in NODE_MOVES:
        rx = re.compile(r'(\[node name="%s" [^\n]*\]\n(?:transform = [^\n]*\n)?position = )Vector3\([^)]*\)' % re.escape(name))
        text, n = rx.subn(lambda mm: mm.group(1) + pos, text, count=1)
        if n != 1:
            raise SystemExit(f"prospekt.tscn: нет узла {name}")
    gate_old = 'position = Vector3(-102, 0, 88)\nwidth = 4.2\nheight = 3.8\n'
    gate_new = ('position = Vector3(-98, 0, 118)\nwidth = 3.6\nheight = 4.0\n\n[node name="StaffDoor" parent="Gameplay" instance=ExtResource("14")]\n'
                'transform = Transform3D(0, 0, 1, 0, 1, 0, -1, 0, 0, -64.3, 0, 51.2)\nwidth = 1.2\nheight = 2.415\n')
    if gate_old in text:
        text = text.replace(gate_old, gate_new, 1)
    elif 'name="StaffDoor"' not in text:
        raise SystemExit("prospekt.tscn: нет ворот рампы")
    open(path, "w", encoding="utf-8", newline="").write(text)
    print("  данные: ящики лута, маршруты, места прогулки, ворота рампы, служебная дверь, посты и метки пролога")
