# -*- coding: utf-8 -*-
"""Зона 1 «Городской пояс», сжатая в квадрат ≈ 600 × 600 м по картинке владельца (схема, 2026-10-17).

Владелец 2026-10-17: карта одна — зона 1; сжать в квадрат ≈ 600 × 600 м, плотнее и максимально по
картинке `docs/design/concepts/urban_belt_2026-10-15/01_urban_belt_starting_concept.png`; двор хрущёвок,
рынок с ангаром и дома у оврага подвинуть под картинку; всю оставшуюся детализацию — блокаутами.

Раскладка обведена с картинки по пикселям (PX_* ниже) и переведена в метры игры: рамка карты на картинке
x 355…1210, y 25…800 растянута на квадрат 600 × 600 (по x 0,70 м/пкс, по z 0,77 м/пкс). Здания — в
настоящую величину, сокращены промежутки. Готовые куски переезжают целиком (сдвиг / поворот, см. READY).

Выход — данные раскладки (из них потом собирается уровень) и две картинки на согласование:

    python -X utf8 tools/zone01_square_plan.py
      → data/zone01_layout.json              раскладка в метрах игры (x, z; север = −Z)
      → docs/design/zone01_square_plan.png    схема с подписями и легендой
      → docs/design/zone01_square_overlay.jpg раскладка поверх картинки владельца — сверка «точь-в-точь»

Углы `angle` — от +X к +Z, то есть по часовой стрелке на плане с севером вверху; длина `size[0]` — вдоль угла.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
CONCEPT = ROOT / "docs/design/concepts/urban_belt_2026-10-15/01_urban_belt_starting_concept.png"
PLACEMENTS = ROOT / "data/zone01_nw_placements.json"
OUT_JSON = ROOT / "data/zone01_layout.json"
OUT_PLAN = ROOT / "docs/design/zone01_square_plan.png"
OUT_OVERLAY = ROOT / "docs/design/zone01_square_overlay.jpg"

# --- перевод пикселей картинки в метры игры
PX_BOX = (355.0, 25.0, 1210.0, 800.0)  # рамка игровой части на картинке
HALF = 300.0
SX = 2 * HALF / (PX_BOX[2] - PX_BOX[0])
SZ = 2 * HALF / (PX_BOX[3] - PX_BOX[1])
CX = (PX_BOX[0] + PX_BOX[2]) / 2
CY = (PX_BOX[1] + PX_BOX[3]) / 2


def m(px: float, py: float) -> tuple[float, float]:
    """Пиксель картинки → (x, z) игры."""
    return round((px - CX) * SX, 1), round((py - CY) * SZ, 1)


def p(x: float, z: float) -> tuple[float, float]:
    """(x, z) игры → пиксель картинки (для наложения)."""
    return x / SX + CX, z / SZ + CY


def mpath(pts) -> list[tuple[float, float]]:
    return [m(*q) for q in pts]


# --- граница: квадрат с неровным краем леса
BOUNDARY = [(-292, -296), (-150, -300), (0, -296), (150, -300), (294, -294), (300, -150), (297, 0), (300, 150),
            (294, 294), (150, 300), (0, 296), (-150, 300), (-294, 294), (-300, 150), (-297, 0), (-300, -150)]

# --- болото (картинка, участок 1): топь с окнами воды, тропы, мостки, постройки на берегу
PX_SWAMP = [(448, 90), (470, 66), (530, 58), (600, 58), (650, 72), (700, 92), (760, 80), (792, 100), (796, 150),
            (790, 185), (772, 225), (740, 262), (690, 275), (620, 280), (540, 282), (480, 275), (450, 250), (442, 170)]
PX_BOARDWALK = [(700, 162), (745, 155), (790, 168)]  # деревянные мостки через воду
PX_TRAILS = [
    [(452, 248), (470, 195), (520, 172), (600, 160), (650, 160), (700, 163)],  # тропа через болото к мосткам
    [(790, 170), (800, 180), (850, 182)],  # от мостков к стройке
    [(480, 86), (560, 76), (640, 72), (690, 85), (688, 130), (692, 158)],  # северная тропа по гряде
    [(690, 172), (688, 230), (665, 268)],  # южная тропа к насосной
]

# --- дороги (картинка), ширина в метрах
PX_ROADS = [
    ("forest", "Лесная дорога", 6.0, True,
     [(365, 50), (378, 100), (385, 150), (387, 200), (392, 260), (398, 330), (403, 400), (406, 450), (418, 492), (440, 520)]),
    ("north", "Северная улица", 8.0, False,
     [(390, 312), (480, 307), (560, 302), (600, 303), (650, 316), (700, 333), (750, 352), (800, 366), (850, 384),
      (900, 395), (950, 403), (1003, 410)]),
    ("artery", "Проспект", 9.0, False, [(800, 366), (785, 420), (770, 460), (757, 500), (750, 546)]),
    ("south", "Южная улица", 9.0, False,
     [(440, 528), (520, 540), (600, 546), (650, 545), (700, 545), (750, 548), (800, 560), (850, 596), (900, 616), (950, 636), (985, 648)]),
    ("east", "Восточная улица", 8.0, False,
     [(997, 135), (1003, 200), (1005, 300), (1005, 410), (1002, 470), (998, 540), (994, 600), (985, 648)]),
    ("mall", "Дорога к ТЦ", 10.0, False, [(1005, 315), (1050, 322), (1100, 335), (1210, 340)]),
    ("evac3", "Дорога к путям", 7.0, False, [(985, 648), (1000, 672), (1022, 705), (1048, 740), (1070, 772), (1088, 800)]),
    ("site", "Проезд стройки", 6.0, True, [(925, 145), (935, 180), (975, 194), (1003, 200)]),
    ("tracks_lane", "Проезд к гаражам", 5.0, False, [(1002, 470), (1040, 480), (1075, 474)]),
]
# дороги, которых нет на картинке (метры)
M_ROADS = [
    ("evac2", "Служебная дорога (промзона)", 6.0, True, [(-240.0, 88.0), (-258.0, 108.0), (-263.0, 200.0), (-262.0, 300.0)]),
    ("bridge", "К мосту через овраг", 5.0, True, [(155.0, -162.0), (170.0, -160.0)]),
]

# --- здания с картинки: (id, подпись, вид, этажей, центр в пикселях, размер [длина, глубина] м, угол °)
# виды: panel — панельная 5-этажка; house — частный / малый дом; hall — ангар, склад, зал; skeleton — недострой;
# shop — магазин, контора; hut — будка, сторожка, бытовка; canopy — навес; station — вокзал
PX_BUILDINGS = [
    # 1 — болото и север
    ("N_service", "Закрытый технический корпус", "hall", 2, (862, 130), (60, 18), 0),
    ("SwampHut_W", "Служебная постройка у болота", "hut", 1, (414, 286), (18, 14), 0),
    ("SwampLodge", "Сторожка", "hut", 1, (486, 280), (12, 10), 0),
    ("SwampPump", "Насосная на берегу", "hut", 1, (657, 245), (10, 10), 0),
    ("SwampBooth", "Будка на мостках", "hut", 1, (772, 215), (9, 8), 10),
    ("SwampRuin", "Руины опоры на островке", "ruin", 1, (465, 175), (12, 10), 20),
    # 2 — панельки (западный двор заменяет готовый двор хрущёвок, см. READY)
    ("Panel_S1", "Пятиэтажка", "panel", 5, (504, 487), (44, 12), 0),
    ("Pavilion_S", "Павильон", "shop", 1, (522, 522), (16, 10), 0),
    ("Panel_E1", "Пятиэтажка", "panel", 5, (631, 393), (44, 12), 90),
    ("Panel_E2", "Пятиэтажка", "panel", 5, (667, 430), (56, 12), 90),
    ("Panel_E3", "Пятиэтажка", "panel", 5, (640, 489), (44, 12), 0),
    ("Panel_E4", "Пятиэтажка", "panel", 5, (605, 520), (36, 12), 0),
    ("Panel_E5", "Пятиэтажка", "panel", 5, (750, 412), (44, 12), 90),
    ("Panel_E6", "Пятиэтажка вдоль проспекта", "panel", 5, (733, 491), (48, 12), 118),
    ("Shop_Res", "Магазин «Продукты»", "shop", 2, (687, 361), (24, 14), 15),
    ("Shop_N", "Магазин у северной улицы", "shop", 2, (617, 288), (24, 12), 0),
    ("House_N1", "Дом", "house", 2, (701, 306), (14, 12), 0),
    ("House_N2", "Дом", "house", 2, (731, 305), (9, 13), 0),
    ("House_N3", "Дом", "house", 1, (754, 309), (8, 10), 0),
    ("Site_Office", "Прорабская", "shop", 2, (832, 300), (24, 12), 0),
    # 3 — недострой
    ("Skeleton_9", "Недострой · 9 этажей", "skeleton", 9, (921, 239), (72, 18), 0),
    ("Skeleton_5", "Недострой · 5 этажей", "skeleton", 5, (868, 312), (60, 16), 90),
    ("Skeleton_3", "Недострой · 3 этажа", "skeleton", 3, (946, 334), (48, 22), 0),
    ("Site_Store", "Склад стройки", "hall", 1, (803, 330), (18, 16), 0),
    ("Site_Hut1", "Бытовка", "hut", 1, (812, 205), (6, 2.5), 0),
    ("Site_Hut2", "Бытовка", "hut", 1, (825, 205), (6, 2.5), 0),
    ("Site_Hut3", "Бытовка", "hut", 1, (838, 205), (6, 2.5), 0),
    ("Site_Hut4", "Бытовка", "hut", 1, (851, 205), (6, 2.5), 0),
    # 4 — спортплощадка и соседний квартал
    ("Sport_Locker", "Раздевалки", "hall", 1, (893, 478), (26, 8), 100),
    ("Sport_Kiosk", "Тренерская", "hut", 1, (884, 512), (14, 12), 10),
    ("Block_Brick", "Кирпичный корпус", "shop", 2, (922, 490), (20, 26), 10),
    ("Sport_Hall", "Спортзал (стеклянная крыша)", "hall", 1, (958, 540), (36, 36), 10),
    ("Block_Blue", "Корпус", "shop", 2, (898, 557), (32, 24), 12),
    ("Block_Yard", "Корпус с двором", "shop", 2, (956, 600), (36, 30), 10),
    ("Block_Roof", "Низкий корпус", "hall", 1, (962, 461), (32, 14), 0),
    # 5 — автостанция
    ("Bus_Terminal", "Автостанция · зал ожидания, касса", "station", 2, (654, 640), (52, 14), -54),
    ("Bus_Depot", "Ремонтный ангар автобусов", "hall", 1, (802, 667), (72, 30), 90),
    ("Bus_Garage", "Гараж-ангар", "hall", 1, (853, 665), (54, 24), 90),
    ("Bus_Office", "Контора автобазы", "shop", 2, (626, 598), (24, 18), 0),
    ("Depot_Office", "Проходная автобазы", "hut", 1, (830, 738), (26, 12), 0),
    ("House_SE1", "Дом", "house", 2, (885, 660), (12, 10), 10),
    ("House_SE2", "Дом", "house", 1, (915, 668), (10, 9), 15),
    ("House_SE3", "Дом", "house", 2, (888, 712), (12, 10), 0),
    ("House_SE4", "Дом", "house", 1, (920, 715), (10, 8), 20),
    # 6 — железная дорога и восток
    ("Rail_Station", "Ж/д станция", "station", 2, (1047, 612), (40, 16), 100),
    ("Rail_Workshop", "Мастерская у путей", "hall", 1, (1045, 672), (30, 20), 100),
    ("East_Brick1", "Кирпичный корпус", "shop", 2, (1046, 370), (36, 20), 90),
    ("East_Brick2", "Пристройка", "shop", 1, (1047, 416), (24, 12), 0),
    ("East_House", "Дом", "house", 2, (1060, 290), (24, 12), 5),
]
# гаражи у путей (модели есть — кирпичные боксы): два ряда по пять, воротами в проезд
M_BUILDINGS = [(f"Garage_{r}{i}", "Гараж у путей", "garage", 1, (186.0 + i * 4.6, zz), (4.3, 6.4), 0)
               for r, zz in (("A", 35.0), ("B", 60.0)) for i in range(5)]
M_BUILDINGS += [
    ("Rail_Store", "Пакгауз у путей", "hall", 1, (194.0, 100.0), (42.0, 26.0), 105),
    ("Rail_Depot", "Локомотивное депо", "hall", 1, (272.0, 141.0), (60.0, 30.0), 100),
    ("Rail_Canopy", "Крытая платформа", "canopy", 1, (229.0, 92.0), (84.0, 8.0), 102),
]

# навесы перронов и автобусы (картинка: ряды под углом ≈ 18°)
PX_CANOPIES = [(742, 600), (742, 618), (742, 636), (742, 654)]
PX_BUSES = [(725, 596), (755, 604), (732, 614), (760, 622), (718, 632), (748, 640), (736, 650), (712, 675), (745, 684),
            (770, 690), (700, 704)]

# площадка-спорт (поле с оградой), площадка стройки, автостанции
PX_COURT = ((841, 470), (50, 34), 12)
PX_SITE = [(797, 183), (994, 186), (1000, 372), (800, 374)]
PX_BUSLOT = [(605, 560), (790, 566), (790, 742), (640, 736), (612, 700)]

# железная дорога: ось пути с картинки; главный ход — 2 пути, станционный парк — 7 путей через 5,5 м;
# с севера пути проходят мостом над дорогой к ТЦ (кадр «TO MALL» на картинке)
TRACK_AXIS = [(312, -80), (300, -70), (280, -45), (262, -5), (251, 45), (240, 100), (228, 153), (221, 190), (214, 226),
              (205, 292), (203, 302)]
TRACK_YARD = {"from_z": 70.0, "to_z": 250.0, "count": 7, "spacing": 5.5}
RAIL_BRIDGE = ((289.0, -56.0), (24.0, 14.0), -51)
FOOTBRIDGE = ((222.0, 224.0), (64.0, 4.0), 9)
TRAIN = [(219.5 - 0.19 * 15 * i, 160 + 15 * i) for i in range(6)]  # вагоны на третьем пути парка

# --- готовые куски: старые координаты зоны 1 → новое место
READY = {
    "yard05": {"name": "Двор хрущёвок (готово)", "move": (24.0, 97.0), "rotate": 0,
               "old_outline": [(-276, -168), (-140, -168), (-140, -50), (-276, -50)]},
    "market06": {"name": "Рынок с ангаром (готово)", "move": (-21.0, 157.0), "rotate": 0,
                 "old_outline": [(-229, -47), (-107, -47), (-107, 94), (-229, 94)]},
    # дома у оврага разворачиваются на 180° вокруг (−320, 25) и встают в (230, −150): мост через овраг — выход «Старый мост»
    "houses12": {"name": "Дома у оврага, мост (готово)", "pivot_old": (-320.0, 25.0), "pivot_new": (230.0, -150.0),
                 "rotate": 180, "old_outline": [(-372, -14), (-255, -14), (-255, 66), (-372, 66)]},
}
YARD_BUILDINGS = [(-212.0, -138.0, 0.0, 57.6, 11.6), (-154.0, -108.0, -90.0, 57.6, 11.6), (-238.0, -80.0, 90.0, 54.4, 12.0)]
YARD_PLAYGROUND = (-197.0, -92.0)
YARD_GARAGES = [(-269.5, float(z)) for z in range(-160, -104, 4)]
# ось оврага в новых координатах: на участке у моста — повёрнутая старая ось (рельеф домов и моста прежний)
RAVINE = [(5, -240), (40, -262), (80, -282), (118, -283), (150, -257), (186, -237), (220, -215), (236, -191),
          (250, -163), (253, -129), (262, -110), (285, -112), (310, -118)]

# выходы и появления (метры)
EXITS = [
    ("evac1", "Лесная дорога", "always", (-292, -287)),
    ("evac2", "Служебная дорога (промзона)", "always", (-262, 294)),
    ("evac3", "Ж/д пути (окраина)", "always", (205, 296)),
    ("evac4", "Старый мост (к реке)", "always", (282, -162)),
    ("bus", "Автостанция (автобус)", "always", (-40, 214)),
    ("mall", "К ТЦ", "mall", (298, -48)),
]
SPAWNS = [(-292, -150), (-140, -292), (40, -245), (292, 30), (60, 294), (-292, 210)]
PLACES = [(1, "Болото", (-120, -205)), (2, "Панельки", (-150, -25)), (3, "Недострой", (75, -110)),
          (4, "Спортплощадка", (45, 45)), (5, "Автостанция", (-30, 175)), (6, "Ж/д станция", (205, 130)),
          (7, "Рынок", (-189, 180)), (8, "Дома у оврага", (190, -150))]

C = {
    "bg": "#ece8dc", "outside": "#cfcbbd", "ground": "#dcdcc6", "forest": "#93ad82", "swamp": "#9fb5a6",
    "water": "#86aec4", "road": "#8b8e90", "road_edge": "#6c6f71", "dirt": "#b3a27f", "rail": "#5d554b",
    "panel": "#a7a39b", "house": "#9a7d63", "hall": "#8f8a83", "skeleton": "#9b9284", "shop": "#a58f7a",
    "hut": "#8a7a66", "station": "#7f8ea0", "ruin": "#7d7469", "ready": "#127a74", "text": "#2b2824",
    "spawn": "#2d6cc0", "extract": "#1e9e4a", "mall": "#7b3fa0", "site": "#cdbb99", "court": "#9cba86",
    "ravine": "#b9b1a0", "tree": "#5f7f4e",
}


def rect_pts(cx: float, cz: float, length: float, depth: float, angle: float) -> list[tuple[float, float]]:
    """Углы прямоугольника (x, z) по центру, размеру и углу (от +X к +Z)."""
    a = math.radians(angle)
    ux, uz = math.cos(a), math.sin(a)
    vx, vz = -uz, ux
    hl, hd = length / 2, depth / 2
    return [(cx + sx * hl * ux + sy * hd * vx, cz + sx * hl * uz + sy * hd * vz)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def ready_transform(key: str, x: float, z: float) -> tuple[float, float]:
    """Старая точка готового куска → новая."""
    r = READY[key]
    if r["rotate"] == 180:
        (ox, oz), (nx, nz) = r["pivot_old"], r["pivot_new"]
        return round(nx - (x - ox), 2), round(nz - (z - oz), 2)
    dx, dz = r["move"]
    return round(x + dx, 2), round(z + dz, 2)


def ready_yaw(key: str, yaw: float) -> float:
    return yaw + READY[key]["rotate"]


def ready_items() -> dict[str, list[dict]]:
    """Постройки готовых кусков в новых координатах (для схемы и проверки пересечений)."""
    out: dict[str, list[dict]] = {"yard05": [], "market06": [], "houses12": []}
    for i, (x, z, yaw, L, D) in enumerate(YARD_BUILDINGS):
        nx, nz = ready_transform("yard05", x, z)
        out["yard05"].append({"id": f"Yard_K{i + 1}", "kind": "panel", "at": [nx, nz], "size": [L, D], "angle": -yaw})
    for i, (x, z) in enumerate(YARD_GARAGES):
        nx, nz = ready_transform("yard05", x, z)
        out["yard05"].append({"id": f"Yard_Garage{i}", "kind": "hut", "at": [nx, nz], "size": [6.0, 3.2], "angle": 0})
    pl = json.loads(PLACEMENTS.read_text(encoding="utf-8"))
    for item in pl["architecture"]:
        a = item.get("asset", "")
        x, _, z = item["position"]
        yaw = float(item.get("yaw", 0.0))
        if abs(x) < 40 and abs(z) < 40:
            continue  # мебель подъезда — в локальных координатах
        if a == "market_hangar" or a.startswith("market_stall"):
            nx, nz = ready_transform("market06", x, z)
            size = [24.0, 42.0] if a == "market_hangar" else [6.5, 13.0]
            out["market06"].append({"id": a, "kind": "hall" if a == "market_hangar" else "hut", "at": [nx, nz],
                                    "size": size, "angle": -ready_yaw("market06", yaw)})
        elif a.startswith("house") or a in ("garden_shed", "ravine_bridge"):
            nx, nz = ready_transform("houses12", x, z)
            size = {"garden_shed": [4.0, 3.0], "ravine_bridge": [34.0, 3.5]}.get(a, [11.0, 9.0])
            kind = {"garden_shed": "hut", "ravine_bridge": "bridge"}.get(a, "house")
            out["houses12"].append({"id": a, "kind": kind, "at": [nx, nz], "size": size,
                                    "angle": -ready_yaw("houses12", yaw)})
    return out


def track_offsets(tr: dict) -> list[tuple[int, float]]:
    """Пути парка: (номер, смещение от оси)."""
    n = tr["yard"]["count"]
    return [(k, (k - (n - 1) / 2) * tr["yard"]["spacing"]) for k in range(n)]


def offset_line(axis, off: float, tr: dict) -> list[tuple[float, float]]:
    """Линия пути: в парке — своё смещение, за парком пути сходятся к двум главным."""
    y0, y1 = tr["yard"]["from_z"], tr["yard"]["to_z"]
    main = tr["spacing"] / 2 * (1 if off >= 0 else -1)
    out = []
    for i, (x, z) in enumerate(axis):
        a, b = axis[max(i - 1, 0)], axis[min(i + 1, len(axis) - 1)]
        dx, dz = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dz) or 1
        t = 1.0 if y0 <= z <= y1 else max(0.0, 1.0 - min(abs(z - y0), abs(z - y1)) / 40.0)
        o = main + (off - main) * t
        out.append((x - dz / ln * o, z + dx / ln * o))
    return out


def build_layout() -> dict:
    buildings = []
    for bid, label, kind, floors, (px, py), size, angle in PX_BUILDINGS:
        x, z = m(px, py)
        buildings.append({"id": bid, "label": label, "kind": kind, "floors": floors, "at": [x, z],
                          "size": list(size), "angle": angle, "px": [px, py]})
    for bid, label, kind, floors, (x, z), size, angle in M_BUILDINGS:
        buildings.append({"id": bid, "label": label, "kind": kind, "floors": floors, "at": [x, z],
                          "size": list(size), "angle": angle})
    for i, (px, py) in enumerate(PX_CANOPIES):
        x, z = m(px, py)
        buildings.append({"id": f"Bus_Canopy{i + 1}", "label": "Навес перрона", "kind": "canopy", "floors": 1,
                          "at": [x, z], "size": [44, 4], "angle": 18, "px": [px, py]})
    roads = [{"id": rid, "label": label, "width": w, "dirt": dirt, "points": [list(q) for q in mpath(pts)]}
             for rid, label, w, dirt, pts in PX_ROADS]
    roads += [{"id": rid, "label": label, "width": w, "dirt": dirt, "points": [list(q) for q in pts]}
              for rid, label, w, dirt, pts in M_ROADS]
    ready = ready_items()
    return {
        "version": 1,
        "purpose": "Зона 1 «Городской пояс» в квадрате ≈ 600 × 600 м по картинке владельца (решение 2026-10-17)",
        "reference": str(CONCEPT.relative_to(ROOT)).replace("\\", "/"),
        "px_box": list(PX_BOX), "m_per_px": [round(SX, 4), round(SZ, 4)], "north": "-Z",
        "angle": "от +X к +Z (по часовой на плане, север вверху); size[0] — вдоль угла",
        "boundary": [list(q) for q in BOUNDARY],
        "swamp": [list(q) for q in mpath(PX_SWAMP)],
        "boardwalk": [list(q) for q in mpath(PX_BOARDWALK)],
        "trails": [[list(q) for q in mpath(t)] for t in PX_TRAILS],
        "ravine": [list(q) for q in RAVINE],
        "tracks": {"axis": [list(q) for q in TRACK_AXIS], "count": 2, "spacing": 4.5, "yard": TRACK_YARD,
                   "bridge": {"at": list(RAIL_BRIDGE[0]), "size": list(RAIL_BRIDGE[1]), "angle": RAIL_BRIDGE[2]},
                   "footbridge": {"at": list(FOOTBRIDGE[0]), "size": list(FOOTBRIDGE[1]), "angle": FOOTBRIDGE[2]},
                   "train": [list(q) for q in TRAIN]},
        "roads": roads,
        "buildings": buildings,
        "buses": [list(m(*q)) for q in PX_BUSES],
        "crane": list(m(905, 300)),
        "court": {"at": list(m(*PX_COURT[0])), "size": list(PX_COURT[1]), "angle": PX_COURT[2]},
        "site": [list(q) for q in mpath(PX_SITE)],
        "bus_lot": [list(q) for q in mpath(PX_BUSLOT)],
        "ready": {k: {"name": v["name"], "move": v.get("move"), "rotate": v["rotate"],
                      "pivot_old": v.get("pivot_old"), "pivot_new": v.get("pivot_new"),
                      "outline": [list(ready_transform(k, x, z)) for x, z in v["old_outline"]],
                      "items": ready[k]} for k, v in READY.items()},
        "exits": [{"id": e, "label": t, "kind": k, "at": list(xy)} for e, t, k, xy in EXITS],
        "spawns": [list(q) for q in SPAWNS],
        "places": [{"n": n, "label": t, "at": list(xy)} for n, t, xy in PLACES],
    }


# ---------------------------------------------------------------- проверка: пересечения построек и дорог
def _sat_overlap(a: list[tuple[float, float]], b: list[tuple[float, float]], gap: float) -> bool:
    """Пересекаются ли два выпуклых многоугольника с зазором gap (разделяющая ось)."""
    for poly in (a, b):
        for i in range(len(poly)):
            x0, z0 = poly[i]
            x1, z1 = poly[(i + 1) % len(poly)]
            nx, nz = z1 - z0, -(x1 - x0)
            ln = math.hypot(nx, nz) or 1.0
            nx, nz = nx / ln, nz / ln
            pa = [x * nx + z * nz for x, z in a]
            pb = [x * nx + z * nz for x, z in b]
            if max(pa) + gap <= min(pb) or max(pb) + gap <= min(pa):
                return False
    return True


def check(layout: dict) -> list[str]:
    boxes = []
    for b in layout["buildings"]:
        boxes.append((b["id"], rect_pts(*b["at"], *b["size"], b["angle"])))
    for k, r in layout["ready"].items():
        boxes.append((k, [tuple(q) for q in r["outline"]]))
    problems = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes[i][0][:8] == boxes[j][0][:8] == "Garage_A" or boxes[i][0][:8] == boxes[j][0][:8] == "Garage_B":
                continue  # гаражи в ряду — стена к стене
            if _sat_overlap(boxes[i][1], boxes[j][1], 3.0):
                problems.append(f"тесно: {boxes[i][0]} × {boxes[j][0]}")
    for r in layout["roads"]:
        pts = r["points"]
        for a, b in zip(pts, pts[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
            seg = rect_pts((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, L, r["width"], ang)
            for name, box in boxes:
                if r["id"] == "bridge" and name == "houses12":
                    continue  # дорога к мосту — внутрь куска
                if _sat_overlap(seg, box, 1.0):
                    problems.append(f"дорога {r['id']} задевает {name}")
    return sorted(set(problems))


# ---------------------------------------------------------------- схема
def draw_plan(layout: dict) -> None:
    fig = plt.figure(figsize=(17.0, 12.6), dpi=110)
    ax = fig.add_axes([0.01, 0.02, 0.66, 0.96])
    lim = HALF + 40
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])
    pt_per_m = 0.66 * 17.0 * 72.0 / (2 * lim)
    G = lambda x, z: (x, -z)  # noqa: E731 — север вверху

    def poly(pts, **kw):
        ax.add_patch(Polygon([G(*q) for q in pts], closed=True, **kw))

    def path(pts, width_m, color, z=3, ls="-", edge=None):
        xs, ys = zip(*[G(*q) for q in pts])
        if edge:
            ax.plot(xs, ys, color=edge, lw=(width_m + 2) * pt_per_m, solid_capstyle="round", zorder=z, ls=ls)
        ax.plot(xs, ys, color=color, lw=width_m * pt_per_m, solid_capstyle="round", zorder=z + 0.1, ls=ls)

    def box(at, size, angle, fc, z=8, ec="#4c463f", lw=0.7, hatch=None, alpha=1.0):
        poly(rect_pts(*at, *size, angle), fc=fc, ec=ec, lw=lw, zorder=z, hatch=hatch, alpha=alpha)

    ax.add_patch(Rectangle((-lim, -lim), 2 * lim, 2 * lim, fc=C["outside"], ec="none", zorder=0))
    poly(layout["boundary"], fc=C["ground"], ec="#a3762a", lw=2.0, ls=(0, (6, 3)), zorder=1)
    for t in trees_from_concept(layout):
        ax.add_patch(Circle(G(*t), 2.6, fc=C["tree"], ec="none", alpha=0.55, zorder=2.8))

    poly(layout["swamp"], fc=C["swamp"], ec="#6f8a78", lw=1.0, zorder=2)
    path(layout["ravine"], 30.0, C["ravine"], z=1.8)
    path(layout["ravine"], 4.0, C["water"], z=2.0)
    poly(layout["site"], fc=C["site"], ec="#8f7c5a", lw=1.2, ls=(0, (4, 2)), zorder=2.5)
    poly(layout["bus_lot"], fc="#cfccc4", ec="#9d998f", lw=0.8, zorder=2.5)
    ct = layout["court"]
    box(ct["at"], ct["size"], ct["angle"], C["court"], z=4, ec="white", lw=1.2)

    for t in layout["trails"]:
        path(t, 1.6, "#f4f1ea", z=3.6, ls=(0, (2, 1.5)))
    path(layout["boardwalk"], 3.5, "#8a6a43", z=4)
    for r in layout["roads"]:
        path(r["points"], r["width"], C["dirt"] if r["dirt"] else C["road"], z=3, edge=None if r["dirt"] else C["road_edge"])

    tr = layout["tracks"]
    path(tr["axis"], 16.0, "#a49786", z=2.4)
    yard_axis = [q for q in tr["axis"] if tr["yard"]["from_z"] - 30 <= q[1] <= tr["yard"]["to_z"] + 30]
    path(yard_axis, tr["yard"]["count"] * tr["yard"]["spacing"] + 8, "#a49786", z=2.41)
    for k, off in track_offsets(tr):
        path(offset_line(tr["axis"], off, tr), 0.9, C["rail"], z=3.5)
    for w in tr["train"]:
        box(w, (3.2, 14), 0, "#6d5040", z=7.5)
    box(tr["footbridge"]["at"], tr["footbridge"]["size"], tr["footbridge"]["angle"], "#7a6c58", z=9)
    box(tr["bridge"]["at"], tr["bridge"]["size"], tr["bridge"]["angle"], "#b8a98d", z=6)  # ж/д мост над дорогой к ТЦ

    for b in layout["buildings"]:
        fc = C.get(b["kind"], C["hall"])
        box(b["at"], b["size"], b["angle"], fc, hatch="xx" if b["kind"] == "skeleton" else None,
            lw=1.1 if b["kind"] in ("panel", "skeleton") else 0.6)
    for bx in layout["buses"]:
        box(bx, (12, 2.6), 18, "#d0b25a", z=9, ec="#7a6533", lw=0.4)
    crane = m(905, 300)
    ax.plot([G(*crane)[0], G(*crane)[0] - 28], [G(*crane)[1], G(*crane)[1] + 30], color="#d6a21e", lw=2.2, zorder=12)
    ax.add_patch(Circle(G(*crane), 3.0, fc="#d6a21e", ec="#7a5c10", zorder=12))

    for k, r in layout["ready"].items():
        poly(r["outline"], fc="none", ec=C["ready"], lw=2.4, ls=(0, (7, 3)), zorder=20)
        for it in r["items"]:
            fc = {"panel": C["panel"], "house": C["house"], "hall": C["hall"], "bridge": "#8a6a43"}.get(it["kind"], C["hut"])
            box(it["at"], it["size"], it["angle"], fc, z=10, lw=0.5)
    yx, yz = ready_transform("yard05", *YARD_PLAYGROUND)
    box((yx, yz), (18, 14), 0, "#d8c9a5", z=7)

    for n, label, (x, z) in [(q["n"], q["label"], q["at"]) for q in layout["places"]]:
        ax.add_patch(Circle(G(x, z), 10, fc="#2b2824" if n <= 6 else C["ready"], ec="white", lw=1.2, zorder=40))
        ax.text(*G(x, z), str(n), fontsize=8, color="white", weight="bold", ha="center", va="center", zorder=41)
    for x, z in layout["spawns"]:
        ax.add_patch(Circle(G(x, z), 7, fc=C["spawn"], ec="white", lw=1.3, zorder=45))
    for e in layout["exits"]:
        x, y = G(*e["at"])
        col = {"mall": C["mall"]}.get(e["kind"], C["extract"])
        ax.add_patch(Polygon([(x, y + 10), (x - 9, y - 6), (x + 9, y - 6)], closed=True, fc=col, ec="white", lw=1.2,
                             zorder=45))
        ty = y - 18 if y > -250 else y + 22
        ax.text(x, ty, e["label"], fontsize=6.8, weight="bold", ha="center", va="center", zorder=46,
                color="#5a2c75" if e["kind"] == "mall" else "#1d4d2c",
                bbox={"boxstyle": "round,pad=0.15", "fc": "#ffffffaa", "ec": "none"})

    # размеры и масштаб
    for (a, b, t, off) in [((-300, 318), (300, 318), "600 м", (0, 0)), ((318, -300), (318, 300), "600 м", (0, 0))]:
        ax.add_patch(FancyArrowPatch(G(*a), G(*b), arrowstyle="<|-|>", mutation_scale=10, color="#3d3a35", lw=1.0,
                                     zorder=50))
        mx, my = G((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        ax.text(mx, my, t, fontsize=9, weight="bold", ha="center", va="center", zorder=51,
                bbox={"boxstyle": "round,pad=0.2", "fc": C["bg"], "ec": "none"})
    ax.plot([-300, -200], [328, 328], color="black", lw=3, zorder=50)
    ax.plot([-200, -100], [328, 328], color="white", lw=3, zorder=50)
    for xv, t in ((-300, "0"), (-200, "100"), (-100, "200 м")):
        ax.text(xv, 336, t, fontsize=7.5, ha="center", zorder=51)
    ax.annotate("", xy=(260, 338), xytext=(260, 312), arrowprops={"arrowstyle": "-|>", "lw": 2, "color": "black"})
    ax.text(246, 326, "С", fontsize=11, weight="bold", ha="center")

    legend(fig, layout)
    OUT_PLAN.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PLAN, facecolor=fig.get_facecolor())
    plt.close(fig)


def legend(fig, layout: dict) -> None:
    lx = fig.add_axes([0.69, 0.02, 0.30, 0.96])
    lx.axis("off")
    y = [0.99]

    def put(text: str, size: float = 8.4, weight: str = "normal", color: str = C["text"]) -> None:
        lx.text(0.0, y[0], text, fontsize=size, weight=weight, color=color, va="top", transform=lx.transAxes)
        y[0] -= 0.0085 + size * 0.0017

    put("Зона 1 «Городской пояс» — квадрат 600 × 600 м", 13.5, "bold")
    put("Схема на согласование · 2026-10-17 · по картинке владельца", 8.5)
    put("Раскладка обведена с картинки; здания в настоящую величину,", 8)
    put("промежутки сжаты. Сверка — zone01_square_overlay.jpg.", 8)
    put("", 5)
    put("Участки с картинки", 10.5, "bold")
    for t in ("1  Болото: топь, окна воды, тропы, мостки, насосная, будки",
              "2  Панельки: готовый двор хрущёвок + 7 пятиэтажек, магазины",
              "3  Недострой: каркасы 9, 5 и 3 эт., кран, бытовки, склад",
              "4  Спортплощадка: поле, раздевалки, спортзал, корпуса рядом",
              "5  Автостанция: здание, 4 перрона, автобусы, ангары, контора",
              "6  Ж/д: парк 7 путей, вокзал, пакгауз, депо, переход, вагоны"):
        put(t)
    put("", 5)
    put("Готовое — переезжает целиком", 10.5, "bold", C["ready"])
    for t in ("7  Рынок с ангаром — к западу от автостанции (сдвиг)",
              "8  Дома у оврага с мостом — северо-восточный угол",
              "    (поворот на 180°): мост — выход «Старый мост»",
              "    Двор хрущёвок — западный двор панелек (сдвиг):",
              "    на картинке там такой же двор буквой П"):
        put(t, 8.2)
    put("", 5)
    put("Отличия от картинки", 10.5, "bold")
    for t in ("• Рынка на картинке нет — он вместо разъезда автобусов.",
              "• Овраг — по северному краю из болота, мимо домов на восток.",
              "• Пути заходят с северо-востока и проходят мостом над",
              "  дорогой к ТЦ (как на кадре «TO MALL»).",
              "• Выход «промзона» — в юго-западном углу за рынком.",
              "• Края карты — квадрат; углы заняты лесом, рынком, домами."):
        put(t, 8.2)
    put("", 5)
    put("Дальше — блокауты", 10.5, "bold")
    for t in ("Всё, чего нет моделями, ставится серыми формами: дома,",
              "недострой, вокзал, навесы, деревья, машины, площадки,",
              "заборы. Деревья — по зелени картинки (точки на схеме).",
              "Готовые модели остаются; блокауты потом меняются на модели.",
              "Рельеф: болото на 1,5–2 м ниже улиц, овраг −10 м,",
              "насыпь путей до +3 м, у ТЦ пути идут мостом над дорогой."):
        put(t, 8.2)
    put("", 5)
    put("Обозначения", 10.5, "bold")
    items = [(C["spawn"], "o", "появление (6, по краям)"), (C["extract"], "^", "выход"),
             (C["mall"], "^", "к карте ТЦ"), (C["ready"], "s", "готовый кусок (переезжает)"),
             (C["tree"], "o", "дерево по картинке")]
    for col, mk, text in items:
        lx.plot([0.02], [y[0] - 0.007], marker=mk, color=col, markersize=9, transform=lx.transAxes, mec="white")
        lx.text(0.07, y[0], text, fontsize=8.4, va="top", transform=lx.transAxes, color=C["text"])
        y[0] -= 0.021


# ---------------------------------------------------------------- деревья по зелени картинки
_TREES: list[tuple[float, float]] | None = None


def trees_from_concept(layout: dict) -> list[tuple[float, float]]:
    """Точки деревьев: зелёные кроны на картинке (клетка 5 пкс), без дорог, построек и воды."""
    global _TREES
    if _TREES is not None:
        return _TREES
    import numpy as np

    arr = np.asarray(Image.open(CONCEPT).convert("RGB")).astype(np.float32)
    r_, g_, b_ = arr[..., 0], arr[..., 1], arr[..., 2]
    mx = arr.max(-1)
    sat = (mx - arr.min(-1)) / (mx + 1)
    green = (g_ >= r_ - 2) & (g_ > b_ + 4) & (mx < 125) & (sat > 0.10)
    cell = 7
    blocked = [rect_pts(*b["at"], b["size"][0] + 6, b["size"][1] + 6, b["angle"]) for b in layout["buildings"]]
    for r in layout["ready"].values():
        blocked.append([tuple(q) for q in r["outline"]])
    out = []
    x0, y0, x1, y1 = (int(v) for v in PX_BOX)
    for cy in range(y0, y1, cell):
        for cx in range(x0, x1, cell):
            share = float(green[cy:cy + cell, cx:cx + cell].mean())
            if share < 0.45:
                continue
            x, z = m(cx + cell / 2, cy + cell / 2)
            if not point_in(layout["boundary"], x, z):
                continue
            if any(point_in(bx, x, z) for bx in blocked):
                continue
            jx = (math.sin(cx * 12.9898 + cy * 78.233) * 43758.5453) % 1.0 - 0.5
            jz = (math.sin(cx * 39.3468 + cy * 11.135) * 24634.6345) % 1.0 - 0.5
            x, z = round(x + jx * 4.0, 1), round(z + jz * 4.0, 1)
            if near_path(layout, x, z):
                continue
            out.append((x, z))
    _TREES = out
    return out


def point_in(poly, x: float, z: float) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % n]
        if (z0 > z) != (z1 > z) and x < (x1 - x0) * (z - z0) / ((z1 - z0) or 1e-9) + x0:
            inside = not inside
    return inside


def near_path(layout: dict, x: float, z: float) -> bool:
    for r in layout["roads"]:
        if _dist_poly(r["points"], x, z) < r["width"] / 2 + 3:
            return True
    if _dist_poly(layout["ravine"], x, z) < 12:
        return True
    if _dist_poly(layout["tracks"]["axis"], x, z) < 16:
        return True
    return False


def _dist_poly(pts, x: float, z: float) -> float:
    best = 1e9
    for (ax_, az), (bx, bz) in zip(pts, pts[1:]):
        dx, dz = bx - ax_, bz - az
        t = max(0.0, min(1.0, ((x - ax_) * dx + (z - az) * dz) / ((dx * dx + dz * dz) or 1e-9)))
        best = min(best, math.hypot(x - ax_ - t * dx, z - az - t * dz))
    return best


# ---------------------------------------------------------------- наложение на картинку
def draw_overlay(layout: dict) -> None:
    im = Image.open(CONCEPT).convert("RGB")
    k = 2
    im = im.resize((im.width * k, im.height * k), Image.LANCZOS)
    d = ImageDraw.Draw(im, "RGBA")
    P = lambda x, z: tuple(v * k for v in p(x, z))  # noqa: E731

    def outline(pts, col, w=2, fill=None):
        d.polygon([P(*q) for q in pts], outline=col, fill=fill)
        if w > 1:
            d.line([P(*q) for q in list(pts) + [pts[0]]], fill=col, width=w)

    outline(layout["boundary"], (255, 0, 255, 255), 3)
    outline(layout["swamp"], (0, 200, 255, 255), 2)
    d.line([P(*q) for q in layout["ravine"]], fill=(200, 120, 255, 200), width=int(30 / SX * k * 0.5))
    for r in layout["roads"]:
        d.line([P(*q) for q in r["points"]], fill=(255, 150, 0, 230), width=max(2, int(r["width"] / SX * k * 0.5)))
    d.line([P(*q) for q in layout["tracks"]["axis"]], fill=(255, 40, 40, 255), width=4)
    for b in layout["buildings"]:
        outline(rect_pts(*b["at"], *b["size"], b["angle"]), (0, 255, 0, 255), 2, (0, 255, 0, 40))
    for r in layout["ready"].values():
        outline([tuple(q) for q in r["outline"]], (0, 255, 230, 255), 3)
        for it in r["items"]:
            outline(rect_pts(*it["at"], *it["size"], it["angle"]), (0, 255, 230, 255), 1, (0, 255, 230, 50))
    for e in layout["exits"]:
        x, y = P(*e["at"])
        d.ellipse([x - 10, y - 10, x + 10, y + 10], outline=(0, 255, 0), width=4)
    try:
        f = ImageFont.truetype("arial.ttf", 26)
    except OSError:
        f = ImageFont.load_default()
    d.text((20, im.height - 46), "Зелёное — постройки схемы, бирюзовое — готовые куски на новом месте, оранжевое — дороги, "
           "сиреневое — овраг, красное — пути", fill=(255, 255, 255), font=f, stroke_width=3, stroke_fill=(0, 0, 0))
    im.save(OUT_OVERLAY, quality=88)


def main() -> None:
    layout = build_layout()
    problems = check(layout)
    layout["trees"] = [list(t) for t in trees_from_concept(layout)]
    OUT_JSON.write_text(json.dumps(layout, ensure_ascii=False, indent=1), encoding="utf-8")
    draw_plan(layout)
    draw_overlay(layout)
    print(f"построек {len(layout['buildings'])}, деревьев {len(layout['trees'])}, дорог {len(layout['roads'])}")
    print("\n".join(problems) if problems else "пересечений нет")
    print("saved", OUT_JSON, OUT_PLAN, OUT_OVERLAY, sep="\n")


if __name__ == "__main__":
    main()
