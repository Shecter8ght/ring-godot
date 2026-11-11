"""«Проспект», ЖК «Вершина» — чертежи предложения по переделке района высоток (редакция 1, 2026-11-11).

Четыре листа в координатах сцены (X — восток, Z — юг, север вверху):
  1. генплан района: башни, стилобат, двор, пути от захода, что было (пунктиром), таблица узлов;
  2. первый этаж стилобата: помещения, двери, колонны галереи, места лута;
  3. развёртка с площади (вид на север): сейчас и предложение в одном масштабе;
  4. разрез 1–1 (площадь → вестибюль → двор → башня Б → забор) и нижние 25 м фасада — слой, который видит игрок.

Окружение (забор, гаражи, посты, палатки) берётся из снимка сцены data/blockouts/prospekt_snapshot.json
(tools/prospekt_study.tscn -- snapshot). Сама расстановка — словари ниже: это предложение, в сцену не внесено.

    python -X utf8 tools/prospekt_vershina_plan.py            # → docs/design/prospekt_vershina_*.png
"""
from __future__ import annotations

import json
import math
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, Polygon, Rectangle

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data" / "blockouts" / "prospekt_snapshot.json"
OUT = ROOT / "docs" / "design"

STORY = 3.3            # этаж башни, м
EYE = 1.62             # высота глаз игрока
HALF_VFOV = math.degrees(math.atan(math.tan(math.radians(40.0)) * 9.0 / 16.0))   # поле зрения 80° по горизонтали, 16:9

# ---------------------------------------------------------------- предложение

# rect = (x0, x1, z0, z1); lift — высота, с которой начинается объём; was — где башня стоит сейчас
TOWERS = [
    {"id": "Vershina_T1", "key": "А", "name": "башня А — пластина", "rect": (54.0, 94.0, -83.3, -59.3), "floors": 44, "lift": 18.0,
     "was": (51.3, 91.3, -115.3, -91.3), "was_lift": 9.3,
     "top": {"rect": (60.0, 88.0, -83.3, -59.3), "from_floor": 39},
     "facade": "тёмное стекло, вертикальные рёбра через 1,5 м", "note": "на переднем краю стилобата, растёт от площади"},
    {"id": "Vershina_T2", "key": "Б", "name": "башня Б — самая высокая", "rect": (100.0, 130.0, -144.3, -114.3), "floors": 58, "lift": 9.3,
     "was": (96.3, 126.3, -108.3, -78.3), "was_lift": 9.3,
     "top": {"rect": (103.0, 127.0, -141.3, -117.3), "from_floor": 47},
     "facade": "сплошное стекло, пояс через 3 этажа, шпиль", "note": "второй план, на своём основании в 2 этажа"},
    {"id": "Vershina_T3", "key": "В", "name": "башня В — двойная", "rect": (147.3, 175.3, -142.3, -110.3), "floors": 52, "lift": 0.0,
     "was": (147.3, 175.3, -118.3, -86.3), "was_lift": 0.0,
     "low": {"rect": (161.3, 175.3, -142.3, -110.3), "floors": 44},
     "facade": "светлый камень, сетка окон", "note": "сдвинута на 24 м к северу"},
    {"id": "Vershina_T4", "key": "Г", "name": "башня Г — жилая с лоджиями", "rect": (138.3, 180.3, -73.3, -49.3), "floors": 36, "lift": 0.0,
     "was": (138.3, 180.3, -73.3, -49.3), "was_lift": 0.0,
     "top": {"rect": (144.3, 174.3, -73.3, -49.3), "from_floor": 31},
     "facade": "лоджии и балконы, два тона панелей", "note": "стоит на месте, меняется фасад и низ"},
]

PODIUM_H = 18.0                       # 4 этажа: первый 6,0 м, три по 4,0 м
PODIUM_FLOORS = [6.0, 10.0, 14.0, 18.0]
WING_S = (49.3, 127.3, -83.3, -59.3)  # крыло вдоль площади
WING_W = (49.3, 73.3, -119.3, -83.3)  # крыло вдоль БЦ «Проспект, 13»
PASSAGE = (100.4, 108.4, -83.3, -59.3)
ARCADE_Z = -63.3                      # линия фасада первого этажа (галерея 4 м под верхними этажами)
COLUMNS_X = [49.7, 58.0, 66.4, 74.8, 83.2, 91.6, 100.0, 108.8, 116.8, 126.9]
OLD_PODIUM = (49.3, 127.3, -119.3, -59.3)

PAVILION = (110.0, 126.0, -106.0, -96.0)      # кафе двора, 2 этажа по 3,6 м
PAVILION_H = 7.2
RAMP = (150.0, 157.8, -104.0, -76.0)          # въезд в паркинг −1: уклон 17 %, ворота закрыты
GARDEN = (77.0, 95.0, -112.0, -90.0)
BC13 = (34.0, 49.3, -110.0, -61.0)
BC13_H = 32.4

# башни города за забором — третий план (новые)
OUTSIDE_NEW = [
    {"key": "Д1", "rect": (20.0, 52.0, -218.0, -186.0), "floors": 48},
    {"key": "Д2", "rect": (190.0, 220.0, -200.0, -170.0), "floors": 54},
]

# помещения первого этажа: (подпись, x0, x1, z0, z1, вид)
ROOMS = [
    ("Офис продаж ЖК\nзал с макетом", 49.3, 62.2, -75.3, -63.3, "shop"),
    ("кабинет", 49.3, 55.8, -83.3, -75.3, "shop"),
    ("архив\nключи квартир", 55.8, 62.2, -83.3, -75.3, "key"),
    ("Вестибюль башни А\nзал в 6 м: стойка, диваны, турникеты", 62.2, 87.4, -75.3, -63.3, "lobby"),
    ("пост\nохраны", 62.2, 67.4, -83.3, -75.3, "lobby"),
    ("Л1\nна +3,0", 67.4, 72.4, -83.3, -75.3, "stair"),
    ("во\nдвор", 72.4, 75.0, -83.3, -75.3, "lobby"),
    ("лифты ×4\nне работают", 75.0, 81.4, -83.3, -75.3, "shut"),
    ("почта\nпосылки", 81.4, 87.4, -83.3, -75.3, "lobby"),
    ("Винотека\nзал", 87.4, 100.4, -76.3, -63.3, "shop"),
    ("склад", 87.4, 100.4, -83.3, -76.3, "shop"),
    ("Ювелирный салон\nзал", 108.4, 127.3, -75.3, -63.3, "shop"),
    ("мастерская", 108.4, 118.0, -83.3, -75.3, "shop"),
    ("сейфовая", 118.0, 127.3, -83.3, -75.3, "key"),
    ("Фитнес-клуб\nзал тренажёров", 49.3, 63.3, -119.3, -83.3, "shop"),
    ("раздевалка М", 63.3, 73.3, -95.3, -83.3, "shop"),
    ("ресепшен", 63.3, 73.3, -105.3, -95.3, "lobby"),
    ("раздевалка Ж", 63.3, 73.3, -119.3, -105.3, "shop"),
]

# двери: (x, z, вдоль какой оси стена — "x" или "z", ширина, подпись)
DOORS = [
    (53.8, -63.3, "x", 1.6, ""), (70.6, -63.3, "x", 5.0, "карусель и распашные"), (95.8, -63.3, "x", 1.6, ""),
    (121.0, -63.3, "x", 1.6, ""),
    (52.5, -75.3, "x", 1.17, ""), (59.0, -75.3, "x", 1.17, "ключ"),
    (64.8, -75.3, "x", 1.17, ""), (69.9, -75.3, "x", 2.4, ""), (74.2, -75.3, "x", 1.4, ""), (84.4, -75.3, "x", 1.17, ""),
    (74.2, -83.3, "x", 1.4, ""),
    (93.9, -76.3, "x", 1.17, ""), (100.4, -70.0, "z", 1.17, ""), (96.0, -83.3, "x", 1.17, "засов"),
    (108.4, -70.0, "z", 1.17, ""), (113.0, -75.3, "x", 1.17, ""), (122.6, -75.3, "x", 1.17, "ключ"),
    (73.3, -100.3, "z", 2.4, "вход со двора"), (63.3, -100.3, "z", 1.6, ""), (68.3, -95.3, "x", 1.17, ""),
    (68.3, -105.3, "x", 1.17, ""), (63.3, -89.3, "z", 1.17, ""), (63.3, -112.3, "z", 1.17, ""),
]

# места лута: (x, z, вид) — b бытовое, m медицина, v ценное, w оружие (цвета — как на схеме левел-дизайна)
LOOT = [
    (51.5, -66.0, "b"), (60.0, -73.0, "b"), (51.0, -81.0, "b"), (60.5, -81.5, "v"),
    (74.0, -72.0, "b"), (64.0, -81.5, "w"), (66.0, -77.5, "b"), (83.0, -81.5, "b"), (86.0, -77.5, "b"), (79.0, -66.5, "b"),
    (89.0, -65.5, "b"), (98.5, -72.0, "v"), (89.5, -81.5, "b"), (98.0, -81.0, "b"),
    (111.0, -66.0, "v"), (124.0, -66.0, "v"), (118.0, -72.5, "b"), (110.5, -81.0, "b"), (125.0, -81.0, "v"),
    (71.0, -98.0, "b"), (65.0, -86.0, "b"), (71.5, -93.0, "b"), (65.0, -117.0, "b"), (71.5, -108.0, "m"),
    (52.0, -117.0, "b"), (61.0, -86.0, "b"),
]
LOOT_YARD = [
    (112.5, -98.5, "b"), (123.5, -104.0, "b"), (118.0, -101.0, "w"), (124.0, -98.0, "v"),
    (93.3, -120.5, "b"), (84.0, -88.0, "b"), (140.0, -92.0, "b"), (148.0, -106.0, "b"),
]
LOOT_COLOR = {"b": "#c9b27c", "m": "#3f9a55", "v": "#e0b400", "w": "#c0392b"}

# пути от захода «За Вершиной» (181.3, −135.3)
SPAWN = (181.3, -135.3)
ROUTES = [
    ("П1 · двор → пассаж → площадь", "#1a7f5a",
     [(181.3, -135.3), (183.0, -107.3), (144.0, -107.3), (130.0, -91.0), (104.4, -88.0), (104.4, -52.0)]),
    ("П2 · вдоль восточного забора → лагерь эвакуации", "#b5651d",
     [(181.3, -135.3), (185.5, -107.3), (185.5, -46.0), (176.0, -40.0)]),
    ("П3 · двор → проход у башни Г → площадь", "#2b6cb0",
     [(144.0, -107.3), (133.0, -90.0), (133.0, -52.0)]),
    ("П4 · за башнями → Банковский переулок → банк", "#7b4ab5",
     [(181.3, -135.3), (178.0, -148.5), (58.0, -148.5), (42.0, -128.0), (32.0, -112.0), (32.0, -62.0)]),
]

# перебивки длинного обзора в проходах: (x, z, ширина, глубина, подпись)
BREAKERS = [
    (183.5, -95.0, 6.0, 3.4, "гараж"), (183.5, -91.4, 6.0, 3.4, "гараж"), (170.0, -90.0, 6.1, 2.4, "контейнер"),
    (139.0, -148.0, 6.1, 2.4, "контейнер"), (86.0, -149.0, 6.1, 2.4, "контейнер"), (184.0, -66.0, 4.5, 1.9, "фургон"),
]

ITEM_SIZE = {"garage": (3.4, 6.0), "ktp": (4.0, 3.0), "container20": (6.1, 2.4), "army_tent": (10.0, 6.0), "truck": (2.5, 8.0),
             "bus_city": (2.5, 12.0), "avtozak": (2.5, 8.0), "police_car": (1.9, 4.5), "car": (1.9, 4.5), "car_open": (1.9, 4.5),
             "van": (2.0, 5.2), "kiosk": (4.0, 3.0), "food_kiosk": (4.0, 3.0), "watchtower": (3.0, 3.0)}
MOVED_ITEMS = {("garage", 171.3, -122.3), ("garage", 174.7, -122.3), ("container20", 131.3, -143.3)}


def tower_top(t: dict) -> float:
    return float(t["lift"]) + float(t["floors"]) * STORY


def center(r: tuple) -> tuple:
    return ((r[0] + r[1]) * 0.5, (r[2] + r[3]) * 0.5)


def size(r: tuple) -> tuple:
    return (r[1] - r[0], r[3] - r[2])


# ---------------------------------------------------------------- рисование

def rect(ax, r, **kw) -> Rectangle:
    p = Rectangle((r[0], r[2]), r[1] - r[0], r[3] - r[2], **kw)
    ax.add_patch(p)
    return p


def dim(ax, a, b, text=None, off=0.0, color="#333333", fs=7.0, tick=0.9) -> None:
    """Размерная линия между точками a и b (обе в координатах плана); off — сдвиг подписи поперёк."""
    ax.plot([a[0], b[0]], [a[1], b[1]], color=color, lw=0.7, zorder=30)
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    nx, ny = -dy / length, dx / length
    for p in (a, b):
        ax.plot([p[0] - nx * tick, p[0] + nx * tick], [p[1] - ny * tick, p[1] + ny * tick], color=color, lw=0.7, zorder=30)
    label = text if text is not None else ("%.1f" % length).replace(".", ",")
    ax.text((a[0] + b[0]) * 0.5 + nx * off, (a[1] + b[1]) * 0.5 + ny * off, label, fontsize=fs, color=color, ha="center", va="center",
            zorder=31, bbox={"boxstyle": "round,pad=0.12", "fc": "white", "ec": "none", "alpha": 0.9})


def frame(fig, title: str, sub: str) -> None:
    fig.text(0.012, 0.972, title, fontsize=15, weight="bold", va="top")
    fig.text(0.012, 0.944, sub, fontsize=8.5, color="#444444", va="top")
    fig.text(0.988, 0.012, "«Проспект» · ЖК «Вершина» · предложение, редакция 1 · 2026-11-11 · tools/prospekt_vershina_plan.py",
             fontsize=7, color="#666666", ha="right", va="bottom")


def north_arrow(ax, x: float, z: float, length: float = 10.0) -> None:
    ax.annotate("", xy=(x, z - length), xytext=(x, z), arrowprops={"arrowstyle": "-|>", "color": "black", "lw": 1.2}, zorder=40)
    ax.text(x, z - length - 1.5, "С", fontsize=10, weight="bold", ha="center", va="bottom", zorder=40)


def scale_bar(ax, x: float, z: float, meters: int = 50, step: int = 10, k: float = 1.0) -> None:
    for i in range(meters // step):
        ax.add_patch(Rectangle((x + i * step, z), step, 1.2 * k, fc="black" if i % 2 == 0 else "white", ec="black", lw=0.6, zorder=40))
    for i in range(meters // step + 1):
        ax.text(x + i * step, z + 3.6 * k, str(i * step), fontsize=7, ha="center", va="center", zorder=40)
    ax.text(x + meters + 3 * k, z + 0.6 * k, "м", fontsize=7, va="center", zorder=40)


def context(ax, snap: dict, lim: tuple, moved: bool) -> None:
    """Окружение из снимка сцены: покрытия, забор, вещи. moved — вещи, которые переедут, не рисовать."""
    x0, x1, z0, z1 = lim
    colors = {"road": "#d9d9d9", "walk": "#efece4", "parking": "#e4e4e0", "grass": "#dfe9d2"}
    for s in snap["surfaces"]:
        r = s["rect"]
        if r[2] < x0 or r[0] > x1 or r[3] < z0 or r[1] > z1 or s["mat"] not in colors:
            continue
        ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc=colors[s["mat"]], ec="none", zorder=1))
    # поворот проспекта: края дороги и тротуара — дуги вокруг (0, 55)
    for radius, color in ((101.95, "#efece4"), (90.15, "#d9d9d9")):
        ax.add_patch(Circle((0.0, 55.0), radius, fc=color, ec="#b0b0b0", lw=0.5, zorder=1.5))
    ax.add_patch(Circle((0.0, 55.0), 51.15, fc="#efece4", ec="#b0b0b0", lw=0.5, zorder=1.6))
    for item in snap["filler"]["items"]:
        kind, x, z = item[0], item[1], item[2]
        if not (x0 <= x <= x1 and z0 <= z <= z1):
            continue
        if moved and (kind, round(x, 1), round(z, 1)) in MOVED_ITEMS:
            continue
        if kind == "district_fence":
            ax.plot([x], [z], marker="s", ms=1.6, color="#555555", zorder=6)
        elif kind == "pole_conc":
            ax.plot([x], [z], marker="o", ms=3, mfc="white", mec="#555555", mew=0.7, zorder=6)
        elif kind in ("tree_birch",) or kind.startswith("m:P_"):
            ax.add_patch(Circle((x, z), 2.2, fc="#b9d3a0", ec="#7a9a5d", lw=0.4, zorder=5))
        elif kind in ITEM_SIZE:
            w, h = ITEM_SIZE[kind]
            yaw = float(item[3]) if len(item) > 3 else 0.0
            if abs(math.sin(math.radians(yaw))) > 0.7:
                w, h = h, w
            fc = {"garage": "#c9c2b4", "ktp": "#d6c58a", "watchtower": "#9aa3ad", "army_tent": "#c5cdb0"}.get(kind, "#bdbdbd")
            ax.add_patch(Rectangle((x - w * 0.5, z - h * 0.5), w, h, fc=fc, ec="#555555", lw=0.4, zorder=6))


def site_axes(fig, pos, lim, grid=10) -> plt.Axes:
    ax = fig.add_axes(pos)
    ax.set_xlim(lim[0], lim[1])
    ax.set_ylim(lim[3], lim[2])        # север (−Z) вверху
    ax.set_aspect("equal")
    ax.set_xticks(range(int(math.ceil(lim[0] / grid) * grid), int(lim[1]) + 1, grid))
    ax.set_yticks(range(int(math.ceil(lim[2] / grid) * grid), int(lim[3]) + 1, grid))
    ax.tick_params(labelsize=6.5, length=2, top=True, right=True, labeltop=True, labelright=True)
    ax.grid(True, color="#9a9a9a", lw=0.25, alpha=0.6, zorder=2)
    ax.set_xlabel("X, м (восток →)", fontsize=7)
    ax.set_ylabel("Z, м (юг ↓)", fontsize=7)
    return ax


# ---------------------------------------------------------------- лист 1: генплан

def sheet_site(snap: dict) -> Path:
    fig = plt.figure(figsize=(16.54, 11.69), dpi=200)
    frame(fig, "Лист 1 · Генплан района высоток — ЖК «Вершина»",
          "Координаты сцены. Красный пунктир — где башни и стилобат стоят сейчас. Все четыре башни сохраняют размер в плане и этажность; "
          "меняются места, форма верха, фасад и низ.")
    lim = (10.0, 226.0, -222.0, -18.0)
    ax = site_axes(fig, [0.035, 0.05, 0.62, 0.86], lim)
    context(ax, snap, lim, moved=True)

    # забор района
    ax.plot([10, 190.8, 190.8], [-154.8, -154.8, -18], color="#333333", lw=1.4, zorder=7)
    ax.text(150.0, -157.2, "забор района (плиты ПО-2, колючка)", fontsize=6.5, color="#333333", ha="center", va="center")

    # существующее рядом
    rect(ax, BC13, fc="#cfd3d8", ec="#444444", lw=0.9, zorder=8)
    ax.text(*center(BC13), "БЦ\n«Проспект, 13»\n9 эт. · 32 м", fontsize=6.3, ha="center", va="center", zorder=9)
    rect(ax, (7.0, 17.0, -97.3, -77.3), fc="#cfd3d8", ec="#444444", lw=0.9, zorder=8)
    ax.text(13.5, -87.3, "мойка", fontsize=6, ha="center", va="center", rotation=90, zorder=9)
    ax.text(25.5, -132.0, "Банковский переулок", fontsize=6.5, rotation=90, ha="center", va="center", color="#555555", zorder=9)
    ax.text(80.0, -38.0, "площадь «Вершины»", fontsize=8, color="#555555", ha="center", zorder=9)
    ax.text(165.0, -36.5, "лагерь эвакуации", fontsize=7.5, color="#555555", ha="center", zorder=9)
    ax.text(31.0, -24.5, "проспект, поворот на юг", fontsize=7, color="#555555", rotation=-22, ha="center", va="center", zorder=9)

    # было
    rect(ax, OLD_PODIUM, fc="none", ec="#c0392b", lw=0.9, ls=(0, (4, 3)), zorder=12)
    for t in TOWERS:
        if t["was"] != t["rect"]:
            rect(ax, t["was"], fc="none", ec="#c0392b", lw=0.9, ls=(0, (4, 3)), zorder=12)
            ax.text(t["was"][1] - 0.8, t["was"][3] - 1.6, "было %s" % t["key"], fontsize=5.8, color="#c0392b", ha="right", va="center",
                    zorder=23, bbox={"boxstyle": "round,pad=0.08", "fc": "white", "ec": "none", "alpha": 0.8})

    # стилобат
    for wing in (WING_S, WING_W):
        rect(ax, wing, fc="#f4e3bf", ec="#6b4e16", lw=1.2, hatch="////", zorder=10, alpha=0.9)
    rect(ax, PASSAGE, fc="#ffffff", ec="#1a7f5a", lw=1.2, zorder=11)
    ax.text(104.4, -66.0, "пассаж\n8 × 24", fontsize=6, ha="center", va="center", color="#1a7f5a", zorder=20)
    ax.text(61.3, -101.3, "стилобат\n4 эт. · 18 м\nфитнес", fontsize=6.5, ha="center", va="center", zorder=20,
            bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.85})
    for cx in COLUMNS_X:
        ax.add_patch(Rectangle((cx - 0.4, -60.1), 0.8, 0.8, fc="#333333", ec="none", zorder=21))

    # башни
    for t in TOWERS:
        rect(ax, t["rect"], fc="#b9c7e6", ec="#1c2f66", lw=1.8, zorder=14, alpha=0.92)
        if "top" in t:
            rect(ax, t["top"]["rect"], fc="none", ec="#1c2f66", lw=0.8, ls=(0, (2, 2)), zorder=15)
        if "low" in t:
            rect(ax, t["low"]["rect"], fc="#d5def2", ec="#1c2f66", lw=0.8, zorder=15)
        cx, cz = center(t["rect"])
        w, d = size(t["rect"])
        ax.text(cx, cz, "%s\n%d эт. · %d м\n%d × %d" % (t["key"], t["floors"], round(tower_top(t)), round(w), round(d)), fontsize=8,
                weight="bold", ha="center", va="center", color="#0f1c40", zorder=22)

    # двор
    rect(ax, GARDEN, fc="#d5e6c0", ec="#5f7f3f", lw=0.7, zorder=8)
    ax.text(86.0, -101.0, "сад двора\nдеревья 12–15 м", fontsize=5.8, ha="center", va="center", color="#3f5a26", zorder=9)
    for tx, tz in ((80.5, -108.5), (91.5, -108.5), (80.5, -93.5), (91.5, -93.5)):
        ax.add_patch(Circle((tx, tz), 3.2, fc="#a9c98a", ec="#5f7f3f", lw=0.4, zorder=8.5, alpha=0.8))
    rect(ax, PAVILION, fc="#bfe3d6", ec="#1a7f5a", lw=1.3, zorder=10)
    ax.text(*center(PAVILION), "кафе двора\n2 эт. · 7 м", fontsize=6.3, ha="center", va="center", color="#0d4a33", zorder=20)
    rect(ax, RAMP, fc="#d0d0d0", ec="#444444", lw=0.9, hatch="---", zorder=9)
    ax.text(153.9, -90.0, "въезд −1\n17 %", fontsize=5.8, ha="center", va="center", zorder=20,
            bbox={"boxstyle": "round,pad=0.1", "fc": "white", "ec": "none", "alpha": 0.85})
    for bx, bz, bw, bd, _ in BREAKERS:
        ax.add_patch(Rectangle((bx - bw * 0.5, bz - bd * 0.5), bw, bd, fc="#e8c9a0", ec="#8a5a1c", lw=0.6, zorder=9))
    ax.text(93.3, -126.5, "КТП, схрон", fontsize=5.5, ha="center", color="#555555", zorder=9)

    # башни за забором
    for o in OUTSIDE_NEW:
        rect(ax, o["rect"], fc="#e6e9f2", ec="#5b6aa0", lw=1.0, ls=(0, (5, 2)), zorder=8)
        ax.text(*center(o["rect"]), "%s\n%d эт. · %d м\nза забором" % (o["key"], o["floors"], round(o["floors"] * STORY)), fontsize=6.5,
                ha="center", va="center", color="#33407a", zorder=9)
    for b in snap["buildings"]:
        if b["region"] == "Outside":
            r = (b["at"][0] - b["size"][0] * 0.5, b["at"][0] + b["size"][0] * 0.5, b["at"][1] - b["size"][1] * 0.5, b["at"][1] + b["size"][1] * 0.5)
            if r[1] > lim[0] and r[0] < lim[1] and r[3] > lim[2] and r[2] < lim[3]:
                rect(ax, r, fc="#ececec", ec="#999999", lw=0.6, zorder=3)
                ax.text(*center(r), "%d эт." % b["floors"], fontsize=5.5, color="#777777", ha="center", va="center", zorder=4)

    # пути
    for label, color, pts in ROUTES:
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, lw=1.6, ls=(0, (6, 3)), zorder=25, alpha=0.95)
        ax.annotate("", xy=pts[-1], xytext=pts[-2], arrowprops={"arrowstyle": "-|>", "color": color, "lw": 1.6}, zorder=25)
    ax.plot([SPAWN[0]], [SPAWN[1]], marker="s", ms=8, color="#2f6fd0", mec="white", mew=0.8, zorder=26)
    ax.text(SPAWN[0] + 2.4, SPAWN[1] - 6.0, "заход\n«За Вершиной»", fontsize=6, color="#2f6fd0", ha="center", va="center", zorder=26,
            bbox={"boxstyle": "round,pad=0.1", "fc": "white", "ec": "none", "alpha": 0.85})

    # размеры
    dim(ax, (97.5, -83.3), (97.5, -114.3), text="А–Б 31,0", off=0.0)
    dim(ax, (130.0, -128.0), (147.3, -128.0), off=-2.6)
    dim(ax, (166.0, -110.3), (166.0, -73.3), off=0.0)
    dim(ax, (127.3, -55.5), (138.3, -55.5), off=2.6)
    dim(ax, (175.3, -122.0), (190.8, -122.0), off=-2.6)
    dim(ax, (180.3, -60.0), (190.8, -60.0), off=2.6)
    dim(ax, (115.0, -144.3), (115.0, -154.8), off=0.0)
    dim(ax, (73.3, -116.5), (100.0, -116.5), off=2.6)
    dim(ax, (49.3, -56.5), (127.3, -56.5), off=2.4)
    dim(ax, (49.3, -122.2), (73.3, -122.2), off=-2.4)
    north_arrow(ax, 205.0, -40.0)
    scale_bar(ax, 150.0, -24.0)

    # таблицы справа
    tx = 0.672
    fig.text(tx, 0.905, "Узлы сцены (scenes/levels/prospekt_study.tscn, East)", fontsize=9.5, weight="bold", va="top")
    lines = ["узел          центр X; Z      план      эт.  низ    верх   было (центр X; Z)"]
    for t in TOWERS:
        cx, cz = center(t["rect"])
        wx, wz = center(t["was"])
        w, d = size(t["rect"])
        lines.append("%-12s %6.1f; %7.1f   %2d × %2d   %3d  %4.1f  %5.1f   %6.1f; %7.1f" % (
            t["id"], cx, cz, w, d, t["floors"], t["lift"], tower_top(t), wx, wz))
    fig.text(tx, 0.885, "\n".join(lines), fontsize=6.6, family="DejaVu Sans Mono", va="top", linespacing=1.5)
    notes = [
        "Башни (этаж 3,3 м):",
    ]
    for t in TOWERS:
        extra = ""
        if "top" in t:
            w, d = size(t["top"]["rect"])
            extra = " Верх с %d-го этажа уже: %d × %d." % (t["top"]["from_floor"], w, d)
        if "low" in t:
            extra = " Восточная половина ниже: %d эт. (%d м)." % (t["low"]["floors"], round(t["low"]["floors"] * STORY))
        line = "%s — %s: %s; %s.%s" % (t["key"], t["name"].split(" — ")[1], t["facade"], t["note"], extra)
        notes += textwrap.wrap(line, 66, initial_indent="  ", subsequent_indent="      ")
    notes += [
        "",
        "Стилобат (вместо ящика 78 × 60 высотой 9 м):",
        "  Г-образный, 4 этажа, 18 м: первый этаж 6,0 м, три по 4,0 м.",
        "  Крыло вдоль площади 78 × 24 (X 49,3…127,3; Z −83,3…−59,3),",
        "  крыло вдоль БЦ 24 × 36 (X 49,3…73,3; Z −119,3…−83,3).",
        "  Галерея на колоннах 4 м вдоль площади, шаг колонн 8,4 м",
        "  (как у нынешних козырьков). Пассаж 8 × 24, высота 6 м,",
        "  X 100,4…108,4 — сквозной проход во двор.",
        "  Первый этаж открыт игроку — лист 2.",
        "",
        "Двор (освобождается из-под ящика стилобата и башни Б):",
        "  сад 18 × 22 со взрослыми деревьями; кафе двора 16 × 10,",
        "  2 этажа, наружная лестница на крышу; въезд в паркинг −1",
        "  7,8 × 28 под навесом, ворота закрыты (задел на потом);",
        "  КТП со схроном остаётся на месте.",
        "",
        "Что переезжает из вещей: два гаража от (171; −122) к восточному",
        "  забору, контейнер от (131; −143) на (139; −148). Добавить",
        "  перебивки обзора в проходах вдоль заборов (оранжевые).",
        "",
        "За забором — две новые башни третьего плана:",
        "  Д1 32 × 32, 48 эт. (158 м) — слева от башни А, над БЦ;",
        "  Д2 30 × 30, 54 эт. (178 м) — справа, за восточным забором.",
        "",
        "Пути от захода «За Вершиной»:",
    ]
    fig.text(tx, 0.79, "\n".join(notes), fontsize=7.4, va="top", linespacing=1.42)
    y = 0.79 - 0.01255 * (len(notes) + 0.4)
    for label, color, pts in ROUTES:
        length = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
        fig.text(tx + 0.008, y, "━━", fontsize=8, color=color, va="top")
        fig.text(tx + 0.032, y, "%s — %d м" % (label, round(length)), fontsize=7.4, va="top")
        y -= 0.0165
    legend = [
        ("#b9c7e6", "#1c2f66", "башня (ключ, этажи, высота верха, план)"),
        ("#f4e3bf", "#6b4e16", "стилобат 18 м"),
        ("#bfe3d6", "#1a7f5a", "новое открытое игроку"),
        ("#e8c9a0", "#8a5a1c", "перебивка обзора (гараж, контейнер, фургон)"),
        ("#ffffff", "#c0392b", "было (пунктир) и куда переезжает"),
        ("#e6e9f2", "#5b6aa0", "новая башня за забором"),
    ]
    y -= 0.012
    for fc, ec, text in legend:
        fig.patches.append(Rectangle((tx + 0.004, y - 0.011), 0.02, 0.011, transform=fig.transFigure, fc=fc, ec=ec, lw=1.0))
        fig.text(tx + 0.032, y, text, fontsize=7.4, va="top")
        y -= 0.0165
    path = OUT / "prospekt_vershina_1_site.png"
    fig.savefig(path)
    plt.close(fig)
    return path


# ---------------------------------------------------------------- лист 2: первый этаж стилобата

def sheet_ground(snap: dict) -> Path:
    fig = plt.figure(figsize=(16.54, 11.69), dpi=200)
    frame(fig, "Лист 2 · Стилобат «Вершины», первый этаж (отметка 0,0; высота этажа 6,0 м)",
          "Правило масштаба E: двери 1,17 × 2,42, проходы × 1,3. Зелёный контур — открыто игроку, серое — закрыто. "
          "Точки — места лута (предложение): бежевый бытовое, зелёный медицина, жёлтый ценное, красный оружие.")
    lim = (42.0, 134.0, -126.0, -48.0)
    ax = site_axes(fig, [0.035, 0.05, 0.70, 0.86], lim, grid=5)
    ax.add_patch(Rectangle((lim[0], -59.3), lim[1] - lim[0], 11.3, fc="#efece4", ec="none", zorder=1))
    ax.add_patch(Rectangle((73.3, -126.0), 60.7, 42.7, fc="#e9efe1", ec="none", zorder=1))
    ax.text(88.0, -52.5, "площадь «Вершины»", fontsize=10, color="#666666", ha="center", va="center")
    ax.text(118.0, -110.0, "двор", fontsize=10, color="#666666", ha="center", va="center")
    rect(ax, (42.0, 49.3, -110.0, -61.0), fc="#cfd3d8", ec="#444444", lw=0.9, zorder=3)
    ax.text(45.6, -85.0, "БЦ «Проспект, 13»", fontsize=7, rotation=90, ha="center", va="center", zorder=4)

    # галерея и башня над ней
    rect(ax, (49.3, 127.3, ARCADE_Z, -59.3), fc="#f7f1e1", ec="#6b4e16", lw=0.6, ls=(0, (4, 2)), zorder=3)
    ax.text(114.5, -61.3, "галерея 4 м под верхними этажами, потолок 6 м", fontsize=6.5, color="#6b4e16", ha="center", va="center", zorder=20)
    for cx in COLUMNS_X:
        ax.add_patch(Rectangle((cx - 0.4, -60.1), 0.8, 0.8, fc="#222222", ec="none", zorder=21))
    kind_fc = {"shop": "#eef7f1", "lobby": "#e3f1fb", "key": "#fdf0c8", "stair": "#e9e9e9", "shut": "#d4d4d4"}
    for label, x0, x1, z0, z1, kind in ROOMS:
        rect(ax, (x0, x1, z0, z1), fc=kind_fc[kind], ec="#1f1f1f", lw=1.6, zorder=5)
        small = (x1 - x0) * (z1 - z0) < 60.0
        ax.text((x0 + x1) * 0.5, (z0 + z1) * 0.5 + (0.0 if small else -1.0), label, fontsize=5.6 if small else 7.2, ha="center", va="center",
                zorder=20, weight="normal" if small else "bold")
        if not small:
            ax.text((x0 + x1) * 0.5, (z0 + z1) * 0.5 + 2.4, "%s × %s" % (("%.1f" % (x1 - x0)).replace(".", ","),
                    ("%.1f" % (z1 - z0)).replace(".", ",")), fontsize=6, color="#555555", ha="center", va="center", zorder=20)
    # пассаж
    rect(ax, PASSAGE, fc="#ffffff", ec="#1a7f5a", lw=2.0, zorder=5)
    ax.text(104.4, -72.0, "ПАССАЖ\nсквозной\n8,0 × 24,0\nвысота 6,0\nрешётки\nподняты", fontsize=7, weight="bold", color="#1a7f5a",
            ha="center", va="center", zorder=20)
    # лестница
    for i in range(8):
        ax.plot([67.9 + i * 0.55, 67.9 + i * 0.55], [-82.8, -78.8], color="#555555", lw=0.5, zorder=6)
    # двери
    for x, z, axis, width, label in DOORS:
        if axis == "x":
            ax.add_patch(Rectangle((x - width * 0.5, z - 0.35), width, 0.7, fc="white", ec="#1a7f5a", lw=0.9, zorder=22))
            if label:
                ax.text(x, z + (1.5 if z > -70 or z < -80 else -1.3), label, fontsize=5.2, color="#1a7f5a", ha="center", va="center", zorder=23)
        else:
            ax.add_patch(Rectangle((x - 0.35, z - width * 0.5), 0.7, width, fc="white", ec="#1a7f5a", lw=0.9, zorder=22))
            if label:
                ax.text(x + 1.0, z - 2.2, label, fontsize=5.2, color="#1a7f5a", ha="left", va="center", zorder=23)
    # контур башни А над этажом
    rect(ax, TOWERS[0]["rect"], fc="none", ec="#1c2f66", lw=1.0, ls=(0, (7, 3)), zorder=24)
    ax.text(92.6, -84.6, "контур башни А над стилобатом", fontsize=6, color="#1c2f66", ha="right", va="center", zorder=24)
    # лут
    for x, z, kind in LOOT + [p for p in LOOT_YARD if lim[0] < p[0] < lim[1] and lim[2] < p[1] < lim[3]]:
        ax.plot([x], [z], marker="o", ms=5.5, mfc=LOOT_COLOR[kind], mec="#222222", mew=0.6, zorder=26)
    # двор: павильон, сад
    rect(ax, GARDEN, fc="#d5e6c0", ec="#5f7f3f", lw=0.7, zorder=3)
    ax.text(88.0, -104.0, "сад двора", fontsize=7, color="#3f5a26", ha="center", zorder=4)
    rect(ax, PAVILION, fc="#bfe3d6", ec="#1a7f5a", lw=1.6, zorder=5)
    rect(ax, (110.0, 120.0, -106.0, -96.0), fc="none", ec="#1f1f1f", lw=1.0, zorder=6)
    ax.text(115.0, -102.5, "кафе двора\nзал 10 × 10", fontsize=6.5, ha="center", va="center", zorder=20)
    ax.text(123.0, -101.0, "кухня", fontsize=6, ha="center", va="center", zorder=20)
    ax.add_patch(Rectangle((110.0, -107.6), 9.0, 1.6, fc="#e9e9e9", ec="#555555", lw=0.6, zorder=6))
    ax.text(114.5, -109.0, "лестница на 2-й этаж (диспетчерская ЖК) и крышу", fontsize=5.5, ha="center", va="center", zorder=20)
    ax.add_patch(Rectangle((91.3, -123.8), 4.0, 3.0, fc="#d6c58a", ec="#555555", lw=0.6, zorder=6))
    ax.text(93.3, -125.0, "КТП", fontsize=5.5, ha="center", va="center", zorder=20)
    rect(ax, (100.0, 130.0, -126.0, -114.3), fc="#b9c7e6", ec="#1c2f66", lw=1.6, zorder=5)
    ax.text(115.0, -119.5, "башня Б · основание 2 эт. (закрыто, стеклянный вестибюль)", fontsize=6.5, ha="center", va="center", zorder=20)
    # размеры
    dim(ax, (49.3, -57.4), (62.2, -57.4), off=1.4)
    dim(ax, (62.2, -57.4), (87.4, -57.4), off=1.4)
    dim(ax, (87.4, -57.4), (100.4, -57.4), off=1.4)
    dim(ax, (100.4, -57.4), (108.4, -57.4), off=1.4)
    dim(ax, (108.4, -57.4), (127.3, -57.4), off=1.4)
    dim(ax, (129.6, -83.3), (129.6, -63.3), off=0.0)
    dim(ax, (129.6, -63.3), (129.6, -59.3), off=0.0)
    dim(ax, (49.3, -121.6), (73.3, -121.6), off=-1.4)
    dim(ax, (75.6, -119.3), (75.6, -83.3), off=0.0)
    dim(ax, (112.0, -83.3), (112.0, -96.0), off=0.0)
    north_arrow(ax, 130.0, -51.0, 5.0)
    scale_bar(ax, 44.0, -52.6, meters=20, step=5, k=0.45)

    tx = 0.752
    fig.text(tx, 0.905, "Помещения", fontsize=9.5, weight="bold", va="top")
    text = [
        "Офис продаж ЖК — зал с макетом комплекса, кабинет,",
        "  архив с ключами квартир (дверь под ключ).",
        "Вестибюль башни А — двусветный зал: стойка, диваны,",
        "  турникеты; за ним пост охраны (оружейный шкаф,",
        "  мониторы), лестница Л1, лифтовой холл (лифты",
        "  стоят), почта с посылками. Вход с площади — карусель",
        "  и распашные двери под козырьком, выход во двор.",
        "Винотека — зал и склад; дверь в пассаж, дверь склада",
        "  во двор закрыта на засов изнутри.",
        "Ювелирный салон — зал с витринами, мастерская,",
        "  сейфовая под ключ; служебная дверь в пассаж.",
        "Фитнес-клуб — вход со двора: ресепшен, две",
        "  раздевалки со шкафчиками, зал тренажёров 14 × 36.",
        "Кафе двора — зал и кухня; наверху диспетчерская ЖК",
        "  (ключи, шкаф охраны), крыша — точка над двором.",
        "",
        "Антресоль вестибюля, отметка +3,0 (по лестнице Л1):",
        "  балкон 3 м над залом, офис управляющей компании",
        "  12 × 8, переговорная 7 × 8. Через витраж с неё",
        "  видна площадь — позиция с обзором; её видно",
        "  с крыши банка и с площади.",
        "",
        "Закрыто: этажи 2–4 стилобата, лифты, башни выше",
        "  антресоли (лестница Л1 выше завалена).",
        "",
        "Счёт: 18 помещений на этаже, 2 в кафе, 2 на антресоли;",
        "  мест лута — %d в стилобате и %d во дворе." % (len(LOOT), len(LOOT_YARD)),
        "",
        "Входы и что рядом:",
        "  с площади — 4 двери и пассаж, все под галереей;",
        "  со двора — вестибюль, фитнес, пассаж;",
        "  между магазинами и пассажем — 2 служебные двери.",
        "  Из каждого помещения, кроме сейфовых, два выхода",
        "  или выход в зал с двумя выходами.",
    ]
    fig.text(tx, 0.885, "\n".join(text), fontsize=7.4, va="top", linespacing=1.45)
    path = OUT / "prospekt_vershina_2_ground.png"
    fig.savefig(path)
    plt.close(fig)
    return path


# ---------------------------------------------------------------- лист 3: развёртка с площади

def floors_lines(ax, x0, x1, y0, y1, step, color, lw=0.25) -> None:
    y = y0 + step
    while y < y1 - 0.01:
        ax.plot([x0, x1], [y, y], color=color, lw=lw, zorder=6)
        y += step


def figure_man(ax, x: float, h: float = 1.75, color: str = "#c0392b") -> None:
    ax.plot([x, x], [0.0, h * 0.86], color=color, lw=1.0, zorder=40)
    ax.add_patch(Circle((x, h * 0.93), h * 0.07, fc=color, ec="none", zorder=40))


def elevation(ax, new: bool, snap: dict) -> None:
    ax.set_xlim(14, 226)
    ax.set_ylim(-6, 222)
    ax.set_aspect("equal")
    ax.set_xlabel("X, м — вид на север с площади", fontsize=7)
    ax.set_ylabel("высота, м", fontsize=7)
    ax.tick_params(labelsize=6.5)
    ax.set_yticks(range(0, 221, 20))
    ax.grid(True, axis="y", color="#aaaaaa", lw=0.25, zorder=0)
    ax.add_patch(Rectangle((14, -6), 212, 6, fc="#d9d9d9", ec="none", zorder=1))
    # город за забором (то, что есть)
    for b in snap["buildings"]:
        if b["region"] == "Outside" and b["at"][1] < -150.0:
            x0 = b["at"][0] - b["size"][0] * 0.5
            ax.add_patch(Rectangle((x0, 0), b["size"][0], b["floors"] * b["story_height"], fc="#eeeeee", ec="#bbbbbb", lw=0.5, zorder=2))
    if new:
        for o in OUTSIDE_NEW:
            r = o["rect"]
            ax.add_patch(Rectangle((r[0], 0), r[1] - r[0], o["floors"] * STORY, fc="#e4e8f3", ec="#8f9ac4", lw=0.8, ls=(0, (5, 2)), zorder=3))
            ax.text((r[0] + r[1]) * 0.5, o["floors"] * STORY + 3, "%s · %d м" % (o["key"], round(o["floors"] * STORY)), fontsize=6.5,
                    color="#5b6aa0", ha="center")
        order = [TOWERS[1], TOWERS[2], TOWERS[0], TOWERS[3]]      # дальние раньше
        shades = {"Б": "#c9d3ea", "В": "#d9d2c0", "А": "#8fa3cf", "Г": "#c3b49a"}
        for t in order:
            r, top = t["rect"], tower_top(t)
            far = t["key"] in ("Б", "В")
            if "top" in t:
                split = t["lift"] + (t["top"]["from_floor"] - 1) * STORY
                ax.add_patch(Rectangle((r[0], 0), r[1] - r[0], split, fc=shades[t["key"]], ec="#1c2f66", lw=1.0, zorder=4 if far else 8))
                tr = t["top"]["rect"]
                ax.add_patch(Rectangle((tr[0], split), tr[1] - tr[0], top - split, fc=shades[t["key"]], ec="#1c2f66", lw=1.0, zorder=4 if far else 8))
            elif "low" in t:
                lr = t["low"]["rect"]
                ax.add_patch(Rectangle((r[0], 0), lr[0] - r[0], top, fc=shades[t["key"]], ec="#1c2f66", lw=1.0, zorder=4))
                ax.add_patch(Rectangle((lr[0], 0), lr[1] - lr[0], t["low"]["floors"] * STORY, fc=shades[t["key"]], ec="#1c2f66", lw=1.0, zorder=4))
            z = 5 if far else 9
            if t["key"] == "А":      # вертикальные рёбра
                x = r[0] + 1.5
                while x < r[1] - 0.1:
                    ax.plot([x, x], [PODIUM_H, top if 60.0 <= x <= 88.0 else t["lift"] + 38 * STORY], color="#3c4f8a", lw=0.25, zorder=z)
                    x += 1.5
                ty = t["lift"] + 21 * STORY
                ax.add_patch(Rectangle((r[0], ty), r[1] - r[0], STORY, fc="#3c4f8a", ec="none", zorder=z))
            elif t["key"] == "Б":
                floors_lines(ax, r[0], r[1], t["lift"], t["lift"] + 46 * STORY, STORY * 3, "#6f7fb0", 0.4)
                floors_lines(ax, 103.0, 127.0, t["lift"] + 46 * STORY, top, STORY * 3, "#6f7fb0", 0.4)
                ax.plot([115.0, 115.0], [top, top + 15.0], color="#1c2f66", lw=1.0, zorder=z)
            elif t["key"] == "В":
                floors_lines(ax, r[0], 161.3, 0, top, STORY, "#8a7f66", 0.25)
                floors_lines(ax, 161.3, r[1], 0, t["low"]["floors"] * STORY, STORY, "#8a7f66", 0.25)
                for x in (150.8, 154.3, 157.8, 164.8, 168.3, 171.8):
                    ax.plot([x, x], [0, top if x < 161.3 else t["low"]["floors"] * STORY], color="#8a7f66", lw=0.25, zorder=z)
            else:
                floors_lines(ax, r[0], r[1], 9.0, t["lift"] + 30 * STORY, STORY, "#6b5d45", 0.3)
                floors_lines(ax, 144.3, 174.3, t["lift"] + 30 * STORY, top, STORY, "#6b5d45", 0.3)
                for x in (145.3, 152.3, 166.3, 173.3):       # столбцы лоджий
                    ax.add_patch(Rectangle((x - 1.6, 9.0), 3.2, 30 * STORY - 9.0, fc="#8d7a5b", ec="none", alpha=0.55, zorder=z))
            ax.text((r[0] + r[1]) * 0.5, top + (18 if t["key"] == "Б" else 3), "%s · %d эт. · %d м" % (t["key"], t["floors"], round(top)),
                    fontsize=7.5, weight="bold", color="#0f1c40", ha="center", zorder=30)
        # стилобат и галерея
        ax.add_patch(Rectangle((WING_S[0], 0), WING_S[1] - WING_S[0], PODIUM_H, fc="#f1dfb6", ec="#6b4e16", lw=1.0, zorder=10))
        for y in PODIUM_FLOORS[:-1]:
            ax.plot([WING_S[0], WING_S[1]], [y, y], color="#6b4e16", lw=0.4, zorder=11)
        ax.add_patch(Rectangle((PASSAGE[0], 0), PASSAGE[1] - PASSAGE[0], 6.0, fc="#ffffff", ec="#1a7f5a", lw=1.0, zorder=12))
        for cx in COLUMNS_X:
            ax.add_patch(Rectangle((cx - 0.4, 0), 0.8, 6.0, fc="#6b4e16", ec="none", zorder=12))
        ax.text(88.0, 21.0, "стилобат 18 м", fontsize=6.5, color="#6b4e16", ha="center", zorder=30,
                bbox={"boxstyle": "round,pad=0.1", "fc": "white", "ec": "none", "alpha": 0.8})
    else:
        old = [("52 эт.", (147.3, 175.3), 0.0, 52), ("58 эт.", (96.3, 126.3), 9.3, 58), ("44 эт.", (51.3, 91.3), 9.3, 44),
               ("36 эт.", (138.3, 180.3), 0.0, 36)]
        for label, (x0, x1), lift, floors in old:
            top = lift + floors * STORY
            ax.add_patch(Rectangle((x0, 0), x1 - x0, top, fc="#aeb9c9", ec="#39424f", lw=1.0, zorder=5))
            floors_lines(ax, x0, x1, lift, top, STORY, "#39424f", 0.25)
            ax.text((x0 + x1) * 0.5, top + 3, "%s · %d м" % (label, round(top)), fontsize=7.5, weight="bold", ha="center", zorder=30)
        ax.add_patch(Rectangle((49.3, 0), 78.0, 9.0, fc="#dcd7cb", ec="#555555", lw=1.0, zorder=10))
        ax.text(88.0, 12.0, "стилобат 9 м, глухой", fontsize=6.5, ha="center", zorder=30,
                bbox={"boxstyle": "round,pad=0.1", "fc": "white", "ec": "none", "alpha": 0.8})
    ax.add_patch(Rectangle((BC13[0], 0), BC13[1] - BC13[0], BC13_H, fc="#cfd3d8", ec="#444444", lw=0.9, zorder=10))
    ax.text(41.6, BC13_H + 3, "БЦ 32 м", fontsize=6.5, ha="center", zorder=30)
    ax.plot([190.8, 190.8], [0, 3.0], color="#333333", lw=1.5, zorder=12)
    for x in (60.0, 88.0, 120.0, 150.0):
        figure_man(ax, x)


def sheet_elevation(snap: dict) -> Path:
    fig = plt.figure(figsize=(16.54, 11.69), dpi=200)
    frame(fig, "Лист 3 · Развёртка с площади (вид на север): сейчас и предложение — один масштаб",
          "Красные фигурки — человек 1,75 м. Бледное — город за забором. Ближние башни темнее, дальние светлее: "
          "сейчас все четыре на одном расстоянии и с одним фасадом, в предложении — два плана на участке и третий за забором.")
    ax1 = fig.add_axes([0.035, 0.09, 0.455, 0.80])
    elevation(ax1, False, snap)
    ax1.set_title("сейчас", fontsize=11, loc="left")
    ax2 = fig.add_axes([0.53, 0.09, 0.455, 0.80])
    elevation(ax2, True, snap)
    ax2.set_title("предложение", fontsize=11, loc="left")
    fig.text(0.035, 0.052, "Сейчас: стена из четырёх одинаковых полосатых объёмов, щели 5 и 13 м, от стилобата 9 м сразу 120–200 м.\n"
             "Предложение: ступени 6 (галерея) → 18 (стилобат) → 32 (БЦ) → 119 → 163 → 172 → 201 м; у каждой башни свой верх и свой "
             "рисунок фасада; Б и В стоят на 31–55 м глубже А и Г.", fontsize=8.5, va="top", linespacing=1.6)
    path = OUT / "prospekt_vershina_3_elevation.png"
    fig.savefig(path)
    plt.close(fig)
    return path


# ---------------------------------------------------------------- лист 4: разрез и нижние 25 м

def sheet_section(snap: dict) -> Path:
    fig = plt.figure(figsize=(16.54, 11.69), dpi=200)
    frame(fig, "Лист 4 · Разрез 1–1 (ломаный: X = 80 до двора, дальше X = 115) и нижние 25 м фасада",
          "Лучи — верхний край кадра при взгляде прямо (поле зрения 80° по горизонтали, 16:9, ± %s° по вертикали). "
          "Всё, что выше луча, игрок видит, только задрав голову, поэтому главная работа — нижние 18–25 м." % ("%.1f" % HALF_VFOV).replace(".", ","))
    # --- разрез: юг слева, север справа (Z убывает вправо)
    tan = math.tan(math.radians(HALF_VFOV))
    a, b = TOWERS[0], TOWERS[1]
    eyes = [(-40.0, "с площади", "#c0392b"), (-8.0, "с тротуара у дороги", "#b5651d"), (16.0, "с проезжей части", "#7b4ab5")]

    def front(axis, detail: bool) -> None:
        """Стилобат с галереей и вестибюлем, башня А над ним."""
        split = a["lift"] + 38 * STORY
        axis.add_patch(Rectangle((-83.3, 0), 24.0, PODIUM_H, fc="#f1dfb6", ec="#6b4e16", lw=1.0, zorder=5))
        axis.add_patch(Rectangle((-63.3, 0), 4.0, 6.0, fc="#ffffff", ec="#6b4e16", lw=0.8, zorder=6))
        axis.add_patch(Rectangle((-60.1, 0), 0.8, 6.0, fc="#6b4e16", ec="none", zorder=7))
        axis.add_patch(Rectangle((-83.3, PODIUM_H), 24.0, tower_top(a) - PODIUM_H, fc="#8fa3cf", ec="#1c2f66", lw=1.0, zorder=5))
        floors_lines(axis, -83.3, -59.3, PODIUM_H, tower_top(a), STORY, "#3c4f8a", 0.25)
        axis.plot([-83.3, -59.3], [split, split], color="#1c2f66", lw=0.8, zorder=7)
        axis.plot([-83.3, -75.3], [3.0, 3.0], color="#6b4e16", lw=1.0, zorder=7)
        if not detail:
            return
        for y in PODIUM_FLOORS[:-1]:
            axis.plot([-83.3, -59.3 if y > 6.0 else -63.3], [y, y], color="#6b4e16", lw=0.6, zorder=7)
        axis.plot([-75.3, -75.3], [0, 6.0], color="#6b4e16", lw=0.8, zorder=7)
        axis.plot([-63.3, -63.3], [0, 6.0], color="#4a90c2", lw=1.8, zorder=8)
        axis.text(-69.3, 3.0, "зал\nвестибюля\n6 м", fontsize=5.6, ha="center", va="center", zorder=9)
        axis.text(-79.3, 4.5, "антресоль\n+3,0", fontsize=5.2, ha="center", va="center", zorder=9)
        axis.text(-79.3, 1.4, "лифты, пост", fontsize=5.2, ha="center", va="center", zorder=9)
        axis.text(-71.3, 12.0, "этажи 2–4 стилобата — закрыты", fontsize=6, ha="center", va="center", zorder=9)
        axis.text(-71.3, 31.0, "башня А\nдо 163 м", fontsize=7, weight="bold", ha="center", va="center", color="#0f1c40", zorder=9,
                  bbox={"boxstyle": "round,pad=0.15", "fc": "white", "ec": "none", "alpha": 0.8})
        axis.text(-61.3, -3.6, "галерея\n4 м", fontsize=5.6, ha="center", va="center", color="#6b4e16", zorder=9)

    ax = fig.add_axes([0.035, 0.40, 0.40, 0.50])
    ax.set_xlim(20, -226)
    ax.set_ylim(-9, 218)
    ax.set_aspect("equal")
    ax.set_title("разрез целиком", fontsize=10, loc="left")
    ax.set_xlabel("Z, м (юг слева, север справа)", fontsize=7)
    ax.set_ylabel("высота, м", fontsize=7)
    ax.tick_params(labelsize=6.5)
    ax.set_xticks(range(20, -227, -20))
    ax.set_yticks(range(0, 211, 20))
    ax.grid(True, color="#aaaaaa", lw=0.25, zorder=0)
    ax.add_patch(Rectangle((-226, -9), 246, 9, fc="#d9d9d9", ec="none", zorder=1))
    ax.text(-22.0, -4.5, "площадь, 72 м", fontsize=6.5, ha="center", va="center")
    ax.text(-99.0, -4.5, "двор, 31 м", fontsize=6.5, ha="center", va="center")
    front(ax, False)
    ax.text(-71.3, tower_top(a) + 3, "А · %d м" % round(tower_top(a)), fontsize=8, weight="bold", ha="center", color="#0f1c40")
    for z in (-93.5, -108.5):
        ax.plot([z, z], [0, 7.0], color="#6b4a2a", lw=0.9, zorder=4)
        ax.add_patch(Circle((z, 10.5), 4.6, fc="#a9c98a", ec="#5f7f3f", lw=0.4, zorder=4))
    ax.add_patch(Rectangle((-106.0, 0), 10.0, PAVILION_H, fc="#bfe3d6", ec="#1a7f5a", lw=1.0, zorder=6))
    ax.text(-101.0, 19.0, "кафе\n7 м", fontsize=6, ha="center", color="#0d4a33", zorder=8)
    bsplit = b["lift"] + 46 * STORY
    ax.add_patch(Rectangle((-144.3, 0), 30.0, b["lift"], fc="#dfe6f5", ec="#1c2f66", lw=1.0, zorder=5))
    ax.add_patch(Rectangle((-144.3, b["lift"]), 30.0, bsplit - b["lift"], fc="#c9d3ea", ec="#1c2f66", lw=1.0, zorder=5))
    ax.add_patch(Rectangle((-141.3, bsplit), 24.0, tower_top(b) - bsplit, fc="#c9d3ea", ec="#1c2f66", lw=1.0, zorder=5))
    floors_lines(ax, -144.3, -114.3, b["lift"], bsplit, STORY * 3, "#6f7fb0", 0.4)
    floors_lines(ax, -141.3, -117.3, bsplit, tower_top(b), STORY * 3, "#6f7fb0", 0.4)
    ax.plot([-129.3, -129.3], [tower_top(b), tower_top(b) + 12.0], color="#1c2f66", lw=1.0)
    ax.text(-129.3, tower_top(b) - 8, "Б · %d м" % round(tower_top(b)), fontsize=8, weight="bold", ha="center", color="#0f1c40", zorder=8)
    ax.plot([-154.8, -154.8], [0, 3.2], color="#333333", lw=1.8, zorder=6)
    ax.text(-158.0, 7.0, "забор", fontsize=6, ha="center")
    ax.add_patch(Rectangle((-193.3, 0), 20.0, 48.0, fc="#eeeeee", ec="#bbbbbb", lw=0.6, zorder=3))
    ax.text(-183.3, 50.5, "город, 48 м", fontsize=6, ha="center", color="#888888")
    ax.add_patch(Rectangle((-218.0, 0), 32.0, 48 * STORY, fc="#e4e8f3", ec="#8f9ac4", lw=0.8, ls=(0, (5, 2)), zorder=2))
    ax.text(-202.0, 48 * STORY + 3, "Д1 · 158 м\n(в стороне, X 20…52)", fontsize=6, ha="center", color="#5b6aa0")
    for z, label, color in eyes:
        hit = EYE + (z + 59.3) * tan
        ax.plot([z, -59.3], [EYE, hit], color=color, lw=0.8, ls=(0, (5, 3)), zorder=20)
        ax.plot([z], [EYE], marker="o", ms=3, color=color, zorder=21)

    # крупно: площадь, галерея, вестибюль, лучи взгляда
    axz = fig.add_axes([0.47, 0.40, 0.515, 0.50])
    axz.set_xlim(26, -96)
    axz.set_ylim(-7, 47)
    axz.set_aspect("equal")
    axz.set_title("крупно: что попадает в кадр при взгляде прямо", fontsize=10, loc="left")
    axz.set_xlabel("Z, м", fontsize=7)
    axz.tick_params(labelsize=6.5)
    axz.set_xticks(range(20, -97, -10))
    axz.set_yticks([0, 6, 10, 14, 18, 25, 30, 40])
    axz.grid(True, color="#aaaaaa", lw=0.25, zorder=0)
    axz.add_patch(Rectangle((-96, -7), 122, 7, fc="#d9d9d9", ec="none", zorder=1))
    axz.add_patch(Rectangle((13.4, -0.5), 12.6, 0.5, fc="#777777", ec="none", zorder=2))
    front(axz, True)
    axz.plot([-93.5, -93.5], [0, 7.0], color="#6b4a2a", lw=1.0, zorder=4)
    axz.add_patch(Circle((-93.5, 10.5), 4.6, fc="#a9c98a", ec="#5f7f3f", lw=0.4, zorder=4))
    axz.text(-89.5, -3.6, "двор", fontsize=6, ha="center", va="center")
    for z, label, color in eyes:
        hit = EYE + (z + 59.3) * tan
        figure_man(axz, z, color=color)
        axz.plot([z, -59.3], [EYE, hit], color=color, lw=1.0, ls=(0, (5, 3)), zorder=20)
        axz.plot([-59.3], [hit], marker="o", ms=4.5, color=color, zorder=21)
        axz.text(-57.6, hit + 1.6, ("%.1f м" % hit).replace(".", ","), fontsize=7.5, weight="bold", color=color, va="center", ha="right",
                 zorder=22, bbox={"boxstyle": "round,pad=0.12", "fc": "white", "ec": "none", "alpha": 0.9})
        axz.text(z, -3.6, "%s\n%d м до фасада" % (label, round(z + 59.3)), fontsize=5.8, color=color, ha="center", va="center", zorder=22)
    fig.text(0.47, 0.455, "С площади при взгляде прямо в кадре нижние 10,7 м — галерея и второй этаж стилобата; с тротуара у дороги — 25,8 м;\n"
             "с проезжей части — 37 м. Чтобы увидеть верх башни А (163 м) целиком, не поднимая взгляда, надо отойти на %d м;\n"
             "с площади взгляд приходится поднимать на %d°, с тротуара у дороги — на %d°." % (
                 round((tower_top(a) - EYE) / tan), round(math.degrees(math.atan((tower_top(a) - EYE) / 19.3))),
                 round(math.degrees(math.atan((tower_top(a) - EYE) / 51.3)))), fontsize=8, va="top", linespacing=1.55)

    # --- нижние 25 м фасада с площади
    ax2 = fig.add_axes([0.035, 0.045, 0.95, 0.27])
    ax2.set_xlim(30, 194)
    ax2.set_ylim(-1.5, 27)
    ax2.set_aspect("equal")
    ax2.set_xlabel("X, м — нижние 25 м фасада с площади: то, что всегда в кадре", fontsize=7)
    ax2.tick_params(labelsize=6.5)
    ax2.set_yticks([0, 3, 6, 10, 14, 18, 25])
    ax2.grid(True, axis="y", color="#aaaaaa", lw=0.25, zorder=0)
    ax2.add_patch(Rectangle((30, -1.5), 164, 1.5, fc="#d9d9d9", ec="none", zorder=1))
    # БЦ
    ax2.add_patch(Rectangle((34.0, 0), 15.3, 27.0, fc="#cfd3d8", ec="#444444", lw=0.9, zorder=3))
    floors_lines(ax2, 34.0, 49.3, 0, 27.0, 3.6, "#555555", 0.4)
    ax2.text(41.6, 13.0, "БЦ\n«Проспект, 13»", fontsize=6, ha="center", va="center", zorder=8)
    # башня А над стилобатом
    ax2.add_patch(Rectangle((54.0, PODIUM_H), 40.0, 9.0, fc="#8fa3cf", ec="#1c2f66", lw=1.0, zorder=3))
    x = 55.5
    while x < 93.9:
        ax2.plot([x, x], [PODIUM_H, 27.0], color="#3c4f8a", lw=0.35, zorder=4)
        x += 1.5
    floors_lines(ax2, 54.0, 94.0, PODIUM_H, 27.0, STORY, "#3c4f8a", 0.3)
    ax2.text(74.0, 23.5, "башня А: рёбра через 1,5 м, этаж 3,3 м", fontsize=6.5, ha="center", zorder=8,
             bbox={"boxstyle": "round,pad=0.1", "fc": "white", "ec": "none", "alpha": 0.85})
    # стилобат: верхние этажи
    ax2.add_patch(Rectangle((49.3, 6.0), 78.0, 12.0, fc="#f1dfb6", ec="#6b4e16", lw=1.0, zorder=3))
    for y in (10.0, 14.0):
        ax2.plot([49.3, 127.3], [y, y], color="#6b4e16", lw=0.5, zorder=4)
    x = 50.7
    while x < 125.0:
        for y in (6.9, 10.9, 14.9):
            ax2.add_patch(Rectangle((x, y), 1.9, 2.4, fc="#5c7186", ec="none", zorder=4))
        x += 2.8
    ax2.add_patch(Rectangle((49.3, 5.6), 78.0, 0.5, fc="#6b4e16", ec="none", zorder=6))
    # первый этаж за колоннами: витрины и двери
    ax2.add_patch(Rectangle((49.3, 0), 78.0, 5.6, fc="#2f3d4c", ec="none", zorder=2))
    ax2.add_patch(Rectangle((PASSAGE[0], 0), 8.0, 5.6, fc="#e9efe1", ec="#1a7f5a", lw=1.0, zorder=4))
    ax2.text(104.4, 3.0, "пассаж\nво двор", fontsize=5.5, ha="center", va="center", color="#1a7f5a", zorder=8)
    for x0, x1, label in ((49.3, 62.2, "ОФИС ПРОДАЖ"), (62.2, 87.4, "ВЕРШИНА · вестибюль"), (87.4, 100.4, "ВИНОТЕКА"), (108.4, 127.3, "ЮВЕЛИРНЫЙ")):
        ax2.add_patch(Rectangle((x0 + 0.6, 4.3), x1 - x0 - 1.2, 0.9, fc="#f3f3f3", ec="none", zorder=5))
        ax2.text((x0 + x1) * 0.5, 4.75, label, fontsize=4.6, ha="center", va="center", zorder=8)
    for x, width in ((53.8, 1.6), (95.8, 1.6), (121.0, 1.6)):
        ax2.add_patch(Rectangle((x - width * 0.5, 0), width, 2.42, fc="#9fb7c9", ec="white", lw=0.5, zorder=5))
    ax2.add_patch(Rectangle((68.1, 0), 5.0, 2.6, fc="#9fb7c9", ec="white", lw=0.5, zorder=5))
    ax2.add_patch(Rectangle((66.4, 3.2), 8.4, 0.25, fc="#c9c9c9", ec="#555555", lw=0.4, zorder=7))
    ax2.text(70.6, 3.75, "козырёк", fontsize=4.5, ha="center", va="center", color="white", zorder=8)
    for cx in COLUMNS_X:
        ax2.add_patch(Rectangle((cx - 0.4, 0), 0.8, 5.6, fc="#c8b78f", ec="#6b4e16", lw=0.4, zorder=7))
    # башня Г: основание и лоджии
    ax2.add_patch(Rectangle((138.3, 0), 42.0, 27.0, fc="#c3b49a", ec="#3d3324", lw=1.0, zorder=3))
    ax2.add_patch(Rectangle((138.3, 0), 42.0, 9.0, fc="#7c8794", ec="#3d3324", lw=0.8, zorder=4))
    ax2.text(159.3, 4.5, "башня Г: основание 2 этажа, стекло и вход", fontsize=6, ha="center", va="center", color="white", zorder=8)
    floors_lines(ax2, 138.3, 180.3, 9.0, 27.0, STORY, "#6b5d45", 0.35)
    for x in (145.3, 152.3, 166.3, 173.3):
        ax2.add_patch(Rectangle((x - 1.6, 9.0), 3.2, 18.0, fc="#8d7a5b", ec="none", alpha=0.7, zorder=5))
    ax2.text(159.3, 20.0, "лоджии столбцами, этаж 3,3 м", fontsize=6, ha="center", zorder=8,
             bbox={"boxstyle": "round,pad=0.1", "fc": "white", "ec": "none", "alpha": 0.85})
    ax2.text(132.8, 12.0, "проход\nво двор\n11 м", fontsize=6.5, ha="center", va="center", color="#2b6cb0", zorder=12)
    # вещи известного размера
    for x in (58.5, 72.0, 97.0, 104.0, 118.0, 134.0, 150.0):
        figure_man(ax2, x)
    ax2.add_patch(Rectangle((142.0, 0), 12.0, 3.1, fc="#e0b030", ec="#7a5a00", lw=0.6, zorder=9, alpha=0.95))
    ax2.text(148.0, 1.5, "автобус 12 × 3,1", fontsize=5, ha="center", va="center", zorder=10)
    for x in (64.0, 82.0, 112.5, 130.5):
        ax2.plot([x, x], [0, 8.0], color="#444444", lw=0.9, zorder=9)
        ax2.plot([x, x + 1.5], [8.0, 8.0], color="#444444", lw=0.9, zorder=9)
    for x in (79.0, 113.0):
        ax2.plot([x, x], [0, 7.0], color="#6b4a2a", lw=1.1, zorder=9)
        ax2.add_patch(Circle((x, 10.5), 4.2, fc="#a9c98a", ec="#5f7f3f", lw=0.4, zorder=9, alpha=0.6))
    ax2.text(187.0, 6.0, "6,0 — потолок\nгалереи", fontsize=6, ha="center", va="center")
    ax2.text(187.0, 18.0, "18,0 — верх\nстилобата", fontsize=6, ha="center", va="center")
    path = OUT / "prospekt_vershina_4_section.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> None:
    plt.rcParams["font.family"] = "DejaVu Sans"
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for build in (sheet_site, sheet_ground, sheet_elevation, sheet_section):
        print("prospekt_vershina_plan:", build(snap))


if __name__ == "__main__":
    main()
