"""«Проспект», вторая очередь, этап 5б: новые места лута (ящики Loot_N) по зонам второй очереди.

Только существующие таблицы data/loot.json и виды ящиков (look). Два режима:
  python -X utf8 tools/prospekt_s2_5b_loot.py cands <кандидаты.json>
      — список точек (x, z, пол) для подгонки по физике (tools/prospekt_loot_snap.tscn);
  python -X utf8 tools/prospekt_s2_5b_loot.py apply <подогнанные.json>
      — дописывает узлы Loot_N в scenes/levels/prospekt.tscn и записи loot плана data/blockouts/prospekt.json
        (и места прогулки locations); повторный запуск отказывается (метка этапа).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCENE = ROOT / "scenes" / "levels" / "prospekt.tscn"
PLAN = ROOT / "data" / "blockouts" / "prospekt.json"

# вид: (kind плана, tier, таблица, look, search_s)
P = {
    "reg": ("register", "common", "register", 0, 2),
    "reg_good": ("register", "good", "register", 0, 2),
    "cab": ("cabinet", "common", "office", 0, 2.5),
    "crate": ("crate", "common", "storage", 5, 3),
    "crate_food": ("crate", "common", "grocery", 5, 3),
    "crate_tools": ("crate", "common", "tools", 5, 3),
    "crate_work": ("crate", "common", "workshop", 5, 3),
    "shelf": ("loose", "common", "shelf", 0, 1.5),
    "shelf_food": ("loose", "common", "grocery", 0, 1.5),
    "kiosk": ("loose", "common", "kiosk", 0, 1.5),
    "elec": ("crate", "good", "electronics", 5, 3),
    "server": ("crate", "good", "server_rack", 5, 3),
    "car": ("car", "common", "home", 0, 3.5),
    "case": ("suitcase", "common", "home", 4, 2.5),
    "pack": ("backpack", "common", "home", 4, 2.5),
    "med": ("med", "med", "pharmacy", 4, 2),
    "sec": ("weapon", "weapon", "security", 2, 3),
    "pmc_box": ("weapon", "weapon", "pmc", 2, 3),
    "pmc_car": ("car", "weapon", "pmc", 0, 3.5),
}


def ring_h(z: float) -> float:
    return min(15.5, 9.0 + max(0.0, z - 150.0) * (15.5 - 9.0) / 100.0)


# (зона, x, z, пол, вид, подпись)
C: list[tuple] = []


def add(zone: str, floor: float, items: list[tuple]) -> None:
    for x, z, kind, name in items:
        C.append((zone, x, z, floor, kind, name))


# ---- «Ярус»
add("«Ярус», зал", 0.0, [
    (-123, 52, "reg", "Касса"), (-81, 52, "reg", "Касса"), (-116, 52, "reg", "Касса экспресс"),
    (-134, 66, "shelf_food", "Стеллаж: бакалея"), (-128, 74, "shelf", "Стеллаж: бытовая химия"),
    (-82, 64, "shelf_food", "Стеллаж: консервы"), (-76, 72, "shelf", "Стеллаж: товары"),
    (-133, 84, "crate_food", "Мясной цех: ящик"), (-116, 84, "crate_food", "Холодильная камера"),
    (-100, 84, "crate", "Приёмка: ящики"), (-86, 84, "pack", "Комната персонала: рюкзак"),
])
add("«Ярус», второй этаж", 6.0, [
    (-120, 53, "shelf_food", "Фуд-корт: стойка"), (-95, 53, "shelf_food", "Фуд-корт: стойка"),
    (-66, 53, "crate_food", "Кухня: ящик"),
    (-138, 64, "elec", "«Техно»: коробки"), (-130, 72, "elec", "«Техно»: коробки"), (-121, 77, "elec", "«Техно»: витрина"),
    (-80, 64, "shelf", "Одежда: стеллаж"), (-70, 74, "shelf", "Детский мир: корзина"),
    (-122, 84, "cab", "Бухгалтерия: шкаф"), (-111, 84, "server", "Серверная: стойка"),
    (-100, 84, "sec", "Охрана: сейф-шкаф"), (-84, 84, "reg_good", "Счётная: касса"),
])
add("«Ярус», склад", 0.0, [
    (-124, 94, "crate", "Склад: паллета"), (-116, 108, "crate", "Склад: паллета"), (-108, 94, "crate", "Склад: стеллаж"),
    (-100, 110, "crate_work", "Склад: стеллаж"), (-92, 98, "crate_tools", "Склад: стеллаж"),
])
add("«Ярус», диспетчерская склада", 3.2, [(-75, 113, "cab", "Диспетчерская: стол")])
add("«Ярус», крыша камер", 3.6, [(-136, 94, "crate", "Площадка на камерах: ящик")])
add("«Ярус», крыша склада", 10.9, [(-112, 94, "case", "Крыша склада: сумка")])
# ---- вокзал
add("вокзал, первый этаж", 0.0, [
    (112, 234.5, "reg", "Окно кассы"), (122, 234.5, "reg", "Окно кассы"), (116, 226, "case", "Забытый чемодан"),
    (111, 244, "cab", "Касса: сейф-шкаф"),
    (123, 245, "sec", "Линейный пункт: сейф-шкаф"), (126, 240, "cab", "Линейный пункт: стол"),
    (180, 224, "shelf_food", "Буфет: стойка"), (170, 232, "case", "Зал ожидания: багаж"), (184, 234, "pack", "Зал ожидания: рюкзак"),
    (167, 241, "case", "Камера хранения: чемодан"), (172, 245, "case", "Камера хранения: чемодан"), (167, 246, "pack", "Камера хранения: рюкзак"),
    (180, 243, "crate", "Багажное: тюки"), (184, 246, "case", "Багажное: чемодан"),
])
add("вокзал, второй этаж", 3.8, [
    (110, 225, "cab", "Кабинет начальника вокзала"), (123, 225, "cab", "Радиоузел: стол"), (112, 242, "cab", "Бухгалтерия: шкаф"),
    (170, 225, "pack", "Комната отдыха: рюкзак"), (169, 243, "med", "Медпункт: аптечка"),
])
add("вокзал, конкорс", 7.6, [(155, 244, "case", "Конкорс: забытая сумка")])
add("вокзал, платформа", 7.6, [(120, 260, "case", "Платформа: сумка на скамье")])
add("вокзал, башня", 24.0, [(144.2, 221.2, "crate", "Площадка башни: ящик")])
# ---- площадь и автостанция
add("площадь", 0.0, [
    (112.5, 146.4, "kiosk", "Ларёк: витрина"), (123, 146.4, "kiosk", "Ларёк: витрина"),
    (162.6, 153, "car", "Автобус: багажный отсек"), (162.6, 189, "car", "Автобус: багажный отсек"),
    (182, 150, "cab", "Автостанция: диспетчерская"), (133, 208.4, "car", "Такси: багажник"),
])
# ---- отдел полиции
add("полиция, первый этаж", 0.0, [
    (-194, 28, "sec", "Дежурная часть: оружейный шкаф"), (-190, 25, "cab", "Дежурная часть: стол"),
    (-181, 18, "cab", "Приём граждан: шкаф"),
])
add("полиция, второй этаж", 3.5, [
    (-204, 18, "cab", "Кабинет начальника: шкаф"), (-193, 18, "cab", "Следователи: шкаф"), (-204, 27, "cab", "Архив: стеллаж"),
])
add("полиция, двор", 0.0, [(-212.5, 53, "car", "Гараж отдела: машина")])
# ---- под эстакадой
add("под эстакадой, ракушки", 0.0, [(-238, -131, "crate_work", "Ракушка: инструмент"), (-236, -112, "crate_tools", "Ракушка: покрышки")])
add("под эстакадой, рынок", 0.0, [
    (-236, 68, "kiosk", "Рынок «Под мостом»: прилавок"), (-228, 84, "kiosk", "Рынок «Под мостом»: прилавок"),
    (-240, 80, "crate", "Рынок: контейнер"), (-232, 98, "crate_food", "Рынок: ящики"), (-226, 106, "crate", "Рынок: поддоны"),
])
add("под эстакадой, дорожники", 0.0, [(-232, 150, "crate_tools", "Техника дорожников: ящик"), (-238, 186, "crate_work", "Бытовка дорожников")])
add("под эстакадой, почтовые фургоны", 0.0, [(-232, 222, "car", "Почтовый фургон"), (-236, 238, "car", "Почтовый фургон")])
add("под эстакадой, штрафстоянка", 0.0, [(-232, 38, "car", "Штрафстоянка: машина")])
add("под эстакадой, блокпост ЧВК", 0.0, [(-236, -30, "pmc_box", "Блокпост ЧВК: оружейный ящик"), (-228, 2, "pmc_car", "Блокпост ЧВК: машина")])
# ---- полотно эстакады
for x, z, kind, name in [(-233, 165, "car", "Багажник машины"), (-228, 190, "car", "Багажник машины"), (-240, 225, "car", "Багажник машины"),
                         (-224, 207, "car", "Автобус на остановке: салон"), (-238, 248, "crate", "Фура: кузов")]:
    C.append(("полотно эстакады", x, z, round(ring_h(z), 3), kind, name))
# ---- юго-запад
add("юго-запад, гаражи", 0.0, [
    (-199.4, 118.8, "crate_work", "Гараж: верстак"), (-170.0, 118.8, "crate_tools", "Гараж: полки"), (-191.0, 131.2, "crate_work", "Гараж: ящик"),
])
add("юго-запад, стройка", 0.0, [(-198.7, 153.5, "crate_tools", "Городок строителей: бытовка"), (-199, 172.5, "crate_tools", "Склад материалов: поддоны")])
add("юго-запад, почтовый двор", 0.0, [
    (-188, 216.6, "car", "Фургон почты: кузов"), (-180, 234, "case", "Мешки почты"), (-160, 239.5, "crate", "Контейнер почты"),
])
add("сквер, туалет", -3.2, [(-25, 111, "shelf", "Туалет: подсобка")])

LOCATIONS = [
    {"id": 22, "label": "Объездная · остановка наверху", "at": [-221.3, 207.0], "spawn": [-225.0, 197.0], "look": [-221.3, 207.0]},
    {"id": 23, "label": "Под эстакадой · рынок", "at": [-234.0, 86.0], "spawn": [-232.0, 72.0], "look": [-234.0, 86.0]},
    {"id": 24, "label": "Гаражный кооператив", "at": [-190.0, 125.0], "spawn": [-170.0, 125.0], "look": [-199.4, 118.0]},
    {"id": 25, "label": "Автостанция", "at": [172.0, 170.0], "spawn": [150.0, 166.0], "look": [165.0, 171.0]},
    {"id": 26, "label": "Лагерь · вертолётная площадка", "at": [176.0, 30.0], "spawn": [168.0, 18.0], "look": [176.5, 30.0]},
]


def fmt(v: float) -> str:
    s = ("%.3f" % v).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def main() -> None:
    mode = sys.argv[1]
    if mode == "cands":
        out = [{"id": i, "x": c[1], "z": c[2], "y": c[3]} for i, c in enumerate(C)]
        Path(sys.argv[2]).write_text(json.dumps(out), encoding="utf-8")
        print(len(out), "кандидатов")
        return
    snapped = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    scene = open(SCENE, encoding="utf-8", newline="").read()
    first = len(re.findall(r'\[node name="Loot_\d+"', scene))
    nodes: list[str] = []
    entries: list[str] = []
    skipped: list[str] = []
    zones: dict[str, int] = {}
    tables: dict[str, int] = {}
    if first != 331:
        sys.exit("ящиков в сцене не 331: этап 5б уже внесён?")
    n = first
    for c, s in zip(C, snapped):
        if not s["ok"]:
            skipped.append("%s %s (%s, %s): %s" % (c[0], c[5], c[1], c[2], s["why"]))
            continue
        kind, tier, table, look, search = P[c[4]]
        x, y, z = float(s["x"]), float(s["y"]), float(s["z"])
        nodes.append('[node name="Loot_%d" parent="Gameplay/Loot" instance=ExtResource("12")]\nposition = Vector3(%s, %s, %s)\n'
                     'display_name = "%s"\ntable = "%s"\nsearch_s = %s\nlook = %d\n' % (n, fmt(x), fmt(y + 0.6), fmt(z), c[5], table, fmt(search), look))
        entries.append('  {\n   "at": [%s, %s, %s],\n   "kind": "%s",\n   "tier": "%s",\n   "note": "%s: %s",\n   "yaw": 0.0\n  }'
                       % (fmt(x), fmt(y), fmt(z), kind, tier, c[0], c[5]))
        zones[c[0]] = zones.get(c[0], 0) + 1
        tables[table] = tables.get(table, 0) + 1
        n += 1
    # сцена: после последнего Loot_N
    m = list(re.finditer(r'\[node name="Loot_\d+"[^\n]*\n(?:[^\[\n][^\n]*\n)*', scene))[-1]
    scene = scene[:m.end()] + "\n" + "\n".join(nodes) + scene[m.end():]
    open(SCENE, "w", encoding="utf-8", newline="").write(scene)
    # план: дописать в конец списка loot
    text = open(PLAN, encoding="utf-8", newline="").read()
    head, tail = text.split(' "filler"', 1)
    k = head.rindex("]")
    head = head[:k].rstrip("\n") + ",\n" + ",\n".join(entries) + "\n " + head[k:]
    text = head + ' "filler"' + tail
    # места прогулки
    d = json.loads(text)
    ids = {l["id"] for l in d["locations"]}
    add_locs = [l for l in LOCATIONS if l["id"] not in ids]
    if add_locs:
        def loc_text(l: dict) -> str:
            v = [("%.1f" % q) for q in l["at"] + l["spawn"] + l["look"]]
            return ('  {\n   "id": %d,\n   "label": "%s",\n   "at": [%s, %s],\n   "spawn": [%s, %s],\n   "look": [%s, %s]\n  }'
                    % (l["id"], l["label"], *v))
        loc_txt = ",\n".join(loc_text(l) for l in add_locs)
        i = text.index(' "locations": [')
        j = text.index("\n ]", i)
        text = text[:j] + ",\n" + loc_txt + text[j:]
    open(PLAN, "w", encoding="utf-8", newline="").write(text)
    print("добавлено ящиков", len(nodes), "из", len(C), "Loot_%d…Loot_%d" % (first, n - 1))
    print("по зонам", zones)
    print("по таблицам", tables)
    print("пропущено", skipped)


if __name__ == "__main__":
    main()
