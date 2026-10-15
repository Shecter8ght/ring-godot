# -*- coding: utf-8 -*-
"""Серый черновик 1-го этажа ТЦ «РИНГ» Ø200 → data/sectors/mall_1f.json.

    python -X utf8 tools/gen_mall_1f.py

Раскладка — принятый владельцем план docs/design/mall_1f_plan.md (схема — tools/mall_1f_plan.py).
Здесь всё задаётся в координатах плана: угол p — от востока против часовой стрелки (90° — север),
смещение d от оси — в сторону роста угла плана. В игре угол идёт от +X к +Z (север = -90°), поэтому
при записи: a = -p (приведено к [-180, 180)), t = -d.

Помещения — кольцевые куски [p0, p1] × [r0, r1]; проходы, аллеи, вестибюли и лестницы у них —
полосы постоянной ширины ("axis"), они главнее и обрезают кольцевые помещения (см. SectorBuilder).
Состояние витрин — пример одного рейда из плана; тасовка по рейдам — отдельная задача.
Эскалаторы, завалы, баррикада, точки появления и выхода — узлы scenes/levels/mall_1f.tscn.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "sectors" / "mall_1f.json"

R = {"atr": (0.5, 30), "gal": (30, 40), "inn": (40, 58), "st": (58, 68), "out": (68, 96), "svc": (96, 100)}
R_BACK = 86.0  # граница торгового зала и подсобок у якорей
OUTER, SITE = 100.0, 150.0
SVC_MID = 98.0  # ось служебного коридора: на ней двери
DOOR_W = 2.4

TILE, WORN, CONC = "large_floor_tiles_02", "worn_tile_floor", "concrete_floor_worn_001"
PLASTER, CWALL = "painted_plaster_wall", "concrete_wall_006"

# сектор: граница b (сектор занимает b..b+60 по плану), буква, название, цвет вывесок
SECTORS = [
    (240, "A", "Аллея", "#ff9a8a"), (180, "B", "Мода", "#ffbb66"), (120, "C", "Дом и ремонт", "#ffd84a"),
    (60, "D", "Спорт и туризм", "#86dd86"), (0, "E", "Продукты", "#74cdf0"), (300, "F", "Техника", "#c9a2f5"),
]
SIGN = {letter: col for _, letter, _, col in SECTORS}
# витрина по состоянию из плана: открыт / роллета наполовину / опущена / электророллета / сгорел
KIND = {"O": "storefront", "H": "half", "C": "locked", "P": "locked", "X": "locked"}

rooms: list[dict] = []
ops: list[dict] = []


# ---------------------------------------------------------------- координаты плана → игры

def ga(p: float) -> float:
    """Угол плана → угол игры в [-180, 180)."""
    return round((-p + 180.0) % 360.0 - 180.0, 4)


def arng(p0: float, p1: float) -> list[float]:
    """Отрезок углов плана [p0, p1] → игры [a0, a1], a1 - a0 = p1 - p0."""
    g0 = ga(p1)
    return [g0, round(g0 + (p1 - p0), 4)]


def sa(side: tuple[float, float], r: float) -> float:
    """Угол плана, где боковая граница (ось b, смещение d) пересекает дугу r."""
    b, d = side
    return b + math.degrees(math.asin(d / r))


def s_at(r: float, d: float) -> float:
    """Где прямая со смещением d пересекает дугу r — м вдоль оси от центра."""
    return math.sqrt(r * r - d * d)


# ---------------------------------------------------------------- помещения и проёмы

def ring(rid: str, name: str, typ: str, p0: float, p1: float, r0: float, r1: float, sec: str, floor: str = WORN,
         wall: str = PLASTER, **kw) -> dict:
    d = {"id": rid, "name": name, "type": typ, "a": arng(p0, p1), "r": [r0, r1], "floor": floor, "wall": wall,
         "sector": sec}
    d.update(kw)
    rooms.append(d)
    return d


def strip(rid: str, name: str, typ: str, axis: float, d0: float, d1: float, r0: float, r1: float, sec: str,
          floor: str = TILE, wall: str = PLASTER, **kw) -> dict:
    d = {"id": rid, "name": name, "type": typ, "axis": ga(axis), "t": [-d1, -d0], "r": [r0, r1], "floor": floor,
         "wall": wall, "sector": sec}
    d.update(kw)
    rooms.append(d)
    return d


def op_arc(r: float, p0: float, p1: float, kind: str, **kw) -> None:
    d = {"wall": "arc", "kind": kind, "r": r, "a": arng(p0, p1)}
    d.update(kw)
    ops.append(d)


def op_rad(p: float, r0: float, r1: float, kind: str, **kw) -> None:
    d = {"wall": "radial", "kind": kind, "a": ga(p), "r": [r0, r1]}
    d.update(kw)
    ops.append(d)


def op_along(axis: float, dd: float, s0: float, s1: float, kind: str, **kw) -> None:
    d = {"wall": "along", "kind": kind, "axis": ga(axis), "t": -dd, "s": [round(s0, 4), round(s1, 4)]}
    d.update(kw)
    ops.append(d)


def across(r: float, axis: float, d0: float, d1: float, kind: str = "open") -> None:
    """Проём на дуге r поперёк полосы (её конец открыт на улицу, галерею, вестибюль)."""
    op_arc(r, sa((axis, d0), r), sa((axis, d1), r), kind)


def door_arc(r: float, pc: float, w: float = DOOR_W, kind: str = "door") -> None:
    h = math.degrees(w / 2.0 / r)
    op_arc(r, pc - h, pc + h, kind)


def door_along(axis: float, dd: float, rc: float, w: float = DOOR_W, kind: str = "door") -> None:
    sc = s_at(rc, dd)
    op_along(axis, dd, sc - w / 2.0, sc + w / 2.0, kind)


def front_arc(r: float, p0: float, p1: float, kind: str, frac: float = 0.7, center: float = 0.5) -> None:
    m = p0 + (p1 - p0) * center
    h = (p1 - p0) * frac / 2.0
    op_arc(r, m - h, m + h, kind)


def front_along(axis: float, dd: float, r0: float, r1: float, kind: str, frac: float = 0.7) -> None:
    s0, s1 = s_at(r0, dd), s_at(r1, dd)
    m, h = (s0 + s1) / 2.0, (s1 - s0) * frac / 2.0
    op_along(axis, dd, m - h, m + h, kind)


def shop(rid: str, name: str, sec: str, right: tuple[float, float], left: tuple[float, float], r0: float, r1: float,
         fronts: list[tuple[str, str]], back: str | None = None, typ: str = "retail", theme: str | None = None,
         **kw) -> dict:
    """Магазин или служебная комната: кольцевой кусок от оси right до оси left (полосы его обрезают),
    витрины fronts [(край r0/r1/left/right, состояние O/H/C/P/X)], вторая дверь back (r0/r1)."""
    extra = dict(kw)
    if theme:
        extra["theme"] = theme
    if typ == "retail":
        extra["sign_color"] = SIGN[sec]
    if any(st == "X" for _, st in fronts):
        extra["locked"] = True  # сгорел: темно, пусто
    room = ring(rid, name, typ, right[0], left[0], r0, r1, sec, **extra)
    for edge, st in fronts:
        kind = KIND[st]
        if edge in ("r0", "r1"):
            r = r0 if edge == "r0" else r1
            front_arc(r, sa(right, r), sa(left, r), kind)
        else:
            side = right if edge == "right" else left
            front_along(side[0], side[1], r0, r1, kind)
    if back:
        r = r0 if back == "r0" else r1
        door_arc(r, (sa(right, r) + sa(left, r)) / 2.0)
    return room


def core(sec: str, b: float, pass_d: float = 2.5, r_wc: tuple[float, float] = (68.0, 80.0),
         r_stair: tuple[float, float] = (80.0, 96.0)) -> None:
    """Техядро у границы сектора: санузлы и лестничная клетка с лифтом, двери — в поперечный проход."""
    ring(f"wc_{sec.lower()}", "Санузлы", "utility", b, b + 12, *r_wc, sec, CONC, CWALL, core=True, theme="core_w",
         note="М, Ж, для маломобильных")
    ring(f"stair_{sec.lower()}", "Лестница и лифт", "utility", b, b + 12, *r_stair, sec, CONC, CWALL, core=True,
         theme="core_w", note="наверх заварено")
    door_along(b, pass_d, (r_wc[0] + r_wc[1]) / 2.0)
    door_along(b, pass_d, (r_stair[0] + r_stair[1]) / 2.0)


def stair_strip(rid: str, sec: str, axis: float, d0: float, d1: float, door_d: float | None,
                locked: bool = False) -> None:
    """Лестничная клетка полосой у вестибюля или прохода; door_d — дверь в него, None — из служебного
    коридора (вестибюль завален)."""
    extra = {"locked": True} if locked else {}
    strip(rid, "Лестница", "utility", axis, d0, d1, R_BACK, 96.0, sec, CONC, CWALL, core=True, theme="core_w",
          note="наверх заварено", **extra)
    if door_d is None:
        door_arc(96.0, sa((axis, (d0 + d1) / 2.0), 96.0))
    else:
        door_along(axis, door_d, 91.0)


# ---------------------------------------------------------------- центр: атриум, галерея, улица

rooms.append({"id": "atrium", "name": "Атриум под куполом", "type": "atrium", "a": [-180.0, 180.0], "r": list(R["atr"]),
              "floor": TILE, "wall": PLASTER, "note": "Ø60, сухой фонтан, эскалаторы на 2-й (штора наверху)"})
rooms.append({"id": "gallery", "name": "Галерея атриума", "type": "gallery", "a": [-180.0, 180.0], "r": list(R["gal"]),
              "floor": TILE, "wall": PLASTER})
ops.append({"wall": "arc", "kind": "open", "r": R["atr"][1], "a": [-180.0, 180.0], "note": "атриум открыт на галерею"})

CURTAIN = {120: "locked", 300: "half"}  # противопожарные шторы на улице: опущена / наполовину
for b, letter, title, _ in SECTORS:
    ring(f"street_{letter.lower()}", "Кольцевая улица", "gallery", b, b + 60, *R["st"], letter, TILE)
    op_rad(b, *R["st"], CURTAIN.get(b, "open"), note="противопожарная штора")

# ---------------------------------------------------------------- границы секторов: проходы, ядра
for b, letter, _, _ in SECTORS:
    strip(f"pass_in_{b}", "Поперечный проход", "corridor", b, -3, 3, *R["inn"], letter)
    across(R["inn"][0], b, -3, 3)
    across(R["inn"][1], b, -3, 3)
    if b == 0:
        continue  # восточный вход — ниже
    strip(f"pass_out_{b}", "Проход к выходу", "corridor", b, -2.5, 2.5, R["st"][1], OUTER, letter)
    across(R["st"][1], b, -2.5, 2.5)
    if b in (120, 180, 300):  # выход наружу (120 и 300 — только изнутри, 60 и 240 заварены)
        door_arc(OUTER, b, 1.8)
    for dd in (-2.5, 2.5):
        if (b, dd) == (120, 2.5):
            continue  # дверь служебного коридора у C|D заварена
        door_along(b, dd, SVC_MID)
    core(letter, b)

# восточный вход: проход 8 м, вестибюль 16 м — лагерь гарнизона за баррикадой
strip("pass_out_0", "Восточный проход", "corridor", 0, -4, 4, R["st"][1], R_BACK, "E")
across(R["st"][1], 0, -4, 4)
across(R_BACK, 0, -4, 4)
strip("vestibule_e", "Восточный вестибюль", "corridor", 0, -8, 8, R_BACK, OUTER, "E", note="лагерь гарнизона мародёров")
op_arc(OUTER, -math.degrees(3.0 / OUTER), math.degrees(3.0 / OUTER), "open", note="восточный вход, баррикада снаружи")
for dd in (-8, 8):
    door_along(0, dd, SVC_MID)
core("E", 0, pass_d=4.0, r_wc=(68.0, 77.0), r_stair=(77.0, R_BACK))

# ---------------------------------------------------------------- A — Аллея (юг, 240–300)
strip("alley_s_in", "Главная аллея", "gallery", 270, -7, 7, *R["inn"], "A")
across(R["inn"][0], 270, -7, 7)
across(R["inn"][1], 270, -7, 7)
strip("alley_s_out", "Главная аллея", "gallery", 270, -7, 7, R["st"][1], R_BACK, "A")
across(R["st"][1], 270, -7, 7)
across(R_BACK, 270, -7, 7)
strip("lobby_s", "Главный вестибюль", "corridor", 270, -10, 10, R_BACK, OUTER, "A", note="частично обрушен")
op_arc(OUTER, 270 - math.degrees(2.5 / OUTER), 270 + math.degrees(2.5 / OUTER), "open", note="пролом главного входа")
for dd in (-10, 10):
    door_along(270, dd, SVC_MID)
stair_strip("stair_s_w", "A", 270, -16, -10, -10)
stair_strip("stair_s_e", "A", 270, 10, 16, 10)
shop("pharmacy", "Аптека", "A", (252, 0), (270, -7), 68, 77, [("r0", "H"), ("left", "H")], theme="pharmacy")
shop("flowers", "Цветы", "A", (252, 0), (270, -7), 77, R_BACK, [("left", "O")], theme="department")
shop("security", "Пост охраны ТЦ", "A", (252, 0), (270, -16), R_BACK, 96, [], back="r1", typ="security", theme="cpu",
     floor=CONC, wall=CWALL)
shop("phones", "Салон связи", "A", (270, 7), (288, 0), 68, 77, [("r0", "O"), ("right", "O")], theme="phones")
shop("coffee", "Кофейня", "A", (270, 7), (288, 0), 77, R_BACK, [("right", "X")], theme="coffee", note="сгорела")
shop("admin", "Администрация ТЦ", "A", (270, 16), (288, 0), R_BACK, 96, [], back="r1", typ="office", theme="staff",
     note="сейф управляющего")
shop("kids", "Детский мир", "A", (288, 0), (300, -2.5), 68, 96, [("r0", "C")], back="r1", theme="department")
shop("optics", "Оптика", "A", (240, 3), (250, 0), *R["inn"], [("r0", "O")], back="r1", theme="optics")
shop("jewelry", "Ювелирный", "A", (250, 0), (270, -7), *R["inn"], [("r0", "H"), ("left", "H")], back="r1",
     theme="jewelry")
shop("bank", "Банк", "A", (270, 7), (287, 0), 40, 51, [("right", "O"), ("r0", "O")], theme="bank")
ring("bank_back", "Банк", "retail", 270, 281, 51, 58, "A", theme="bank")
op_arc(51, 270, 281, "open")
door_arc(58, 279)
ring("bank_vault", "Хранилище банка", "office", 281, 287, 51, 58, "A", CONC, CWALL, theme="bank")
door_arc(51, 284)
shop("pawn", "Ломбард", "A", (287, 0), (300, -3), *R["inn"], [("r0", "C")], back="r1", theme="jewelry")

# ---------------------------------------------------------------- B — Мода (юго-запад, 180–240)
strip("evac_b", "Проход к пожарному выходу", "corridor", 210, -1.5, 1.5, R["st"][1], OUTER, "B")
across(R["st"][1], 210, -1.5, 1.5)
door_arc(OUTER, 210)  # только изнутри
for dd in (-1.5, 1.5):
    door_along(210, dd, SVC_MID)
stair_strip("stair_b", "B", 210, -8, -1.5, -1.5)
ring("fashion", "«Модный дом»", "retail", 192, 210, 68, R_BACK, "B", theme="clothes", sign_color=SIGN["B"])
front_arc(68, 192, sa((210, -1.5), 68), "storefront", frac=0.32, center=0.27)
front_arc(68, 192, sa((210, -1.5), 68), "storefront", frac=0.32, center=0.73)
door_arc(R_BACK, 199)
ring("fashion_st", "Склад «Модного дома»", "storage", 192, 210, R_BACK, 96, "B", CONC, CWALL, theme="department")
door_arc(96, 197)
shop("shoes", "Обувь", "B", (210, 1.5), (222, 0), 68, 96, [("r0", "H")], back="r1", theme="clothes")
shop("jeans", "Джинсы", "B", (222, 0), (231, 0), 68, 96, [("r0", "O")], back="r1", theme="clothes")
shop("linen", "Бельё", "B", (231, 0), (240, -2.5), 68, 96, [("r0", "C")], back="r1", theme="clothes")
shop("barber", "Парикмахерская", "B", (180, 3), (190, 0), *R["inn"], [("r0", "O")], back="r1", theme="cosmetics")
shop("watches", "Часы", "B", (190, 0), (200, 0), *R["inn"], [("r0", "H")], back="r1", theme="watches")
shop("bags", "Сумки", "B", (200, 0), (210, 0), *R["inn"], [("r1", "O")], back="r0", theme="clothes")
shop("cosmetics", "Косметика", "B", (210, 0), (220, 0), *R["inn"], [("r0", "O"), ("r1", "O")], theme="cosmetics")
shop("bijou", "Бижутерия", "B", (220, 0), (230, 0), *R["inn"], [("r0", "C")], back="r1", theme="jewelry")
shop("keys", "Ключи, ремонт обуви", "B", (230, 0), (240, -3), *R["inn"], [("r1", "O")], back="r0", theme="hardware")

# ---------------------------------------------------------------- C — Дом и ремонт (северо-запад, 120–180)
strip("evac_c", "Проход к пожарному выходу", "corridor", 150, -1.5, 1.5, R["st"][1], OUTER, "C")
across(R["st"][1], 150, -1.5, 1.5)  # выход на фасаде заварен
for dd in (-1.5, 1.5):
    door_along(150, dd, SVC_MID)
stair_strip("stair_c", "C", 150, -8, -1.5, -1.5)
ring("diy", "«Дом и ремонт»", "retail", 132, 150, 68, R_BACK, "C", theme="diy", sign_color=SIGN["C"],
     note="инструмент")
front_arc(68, 132, sa((150, -1.5), 68), "locked", frac=0.6)
door_arc(R_BACK, 140)
ring("diy_st", "Склад «Дом и ремонт»", "storage", 132, 150, R_BACK, 96, "C", CONC, CWALL, theme="diy_st")
door_arc(96, 137)
shop("home", "Товары для дома", "C", (150, 1.5), (162, 0), 68, 96, [("r0", "O")], back="r1", theme="department",
     note="дом жильцов")
shop("pets", "Зоотовары", "C", (162, 0), (171, 0), 68, 96, [("r0", "O")], back="r1", theme="department")
shop("hardware", "Хозтовары", "C", (171, 0), (180, -2.5), 68, 88, [("r0", "H")], theme="hardware")
shop("stash", "Тайник", "C", (171, 0), (180, -2.5), 88, 96, [], back="r1", typ="storage", theme="hardware_st",
     floor=CONC, wall=CWALL, note="ключ К7")
shop("textile", "Текстиль", "C", (120, 3), (130, 0), *R["inn"], [("r0", "O")], back="r1", theme="department")
shop("dishes", "Посуда", "C", (130, 0), (140, 0), *R["inn"], [("r1", "O")], back="r0", theme="department")
shop("garden", "Сад", "C", (140, 0), (150, 0), *R["inn"], [("r0", "H")], back="r1", theme="hardware")
shop("photo", "Фотоателье", "C", (150, 0), (160, 0), *R["inn"], [("r0", "O"), ("r1", "O")], theme="photo")
shop("books", "Книги", "C", (160, 0), (170, 0), *R["inn"], [("r0", "X")], theme="press", note="сгорел")
shop("tobacco", "Табак", "C", (170, 0), (180, -3), *R["inn"], [("r1", "H")], back="r0", theme="press")

# ---------------------------------------------------------------- D — Спорт и туризм (север, 60–120)
strip("alley_n_in", "Северная аллея", "gallery", 90, -6, 6, *R["inn"], "D")
across(R["inn"][0], 90, -6, 6)
across(R["inn"][1], 90, -6, 6)
strip("alley_n_out", "Северная аллея", "gallery", 90, -6, 6, R["st"][1], R_BACK, "D", note="тупик у завала")
across(R["st"][1], 90, -6, 6)
across(R_BACK, 90, -6, 6)
strip("lobby_n", "Северный вестибюль", "corridor", 90, -10, 10, R_BACK, OUTER, "D", locked=True, note="завал")
stair_strip("stair_n_e", "D", 90, -16, -10, None)
stair_strip("stair_n_w", "D", 90, 10, 16, 10, locked=True)
ring("sport", "Спорттовары", "retail", 72, 90, 68, R_BACK, "D", theme="sport", sign_color=SIGN["D"])
front_arc(68, 72, sa((90, -6), 68), "storefront")
front_along(90, -6, 68, R_BACK, "storefront")
door_arc(R_BACK, 78)
ring("sport_st", "Склад спорттоваров", "storage", 72, 90, R_BACK, 96, "D", CONC, CWALL, theme="sport_st")
door_arc(96, 76)
shop("tourism", "Туризм", "D", (90, 6), (108, 0), 68, R_BACK, [("right", "O"), ("r0", "H")], theme="sport")
door_arc(R_BACK, 103)
ring("tourism_st", "Склад туризма", "storage", 90, 108, R_BACK, 96, "D", CONC, CWALL, theme="sport_st")
door_arc(96, 104)
shop("taiga", "Оружейный «Тайга»", "D", (108, 0), (120, -2.5), 68, 96, [("r0", "P")], theme="sport",
     note="электророллета: питание и ключ-карта")
shop("sportpit", "Спортпит", "D", (60, 3), (72, 0), *R["inn"], [("r0", "C")], back="r1", theme="sport")
shop("bikes", "Велосипеды", "D", (72, 0), (90, -6), *R["inn"], [("r0", "O"), ("left", "O")], back="r1", theme="sport")
shop("toys", "Игрушки", "D", (90, 6), (108, 0), *R["inn"], [("right", "O"), ("r0", "O")], back="r1",
     theme="department")
shop("medpoint", "Медпункт ТЦ", "D", (108, 0), (120, -3), *R["inn"], [], back="r1", typ="office", theme="pharmacy",
     floor=CONC)

# ---------------------------------------------------------------- E — Продукты (северо-восток, 0–60)
ring("market", "Супермаркет «Корзина»", "retail", 12, 60, 68, R_BACK, "E", theme="hyper", sign_color=SIGN["E"])
front_arc(68, 12, sa((60, -2.5), 68), "storefront", frac=0.2, center=0.25)
front_arc(68, 12, sa((60, -2.5), 68), "storefront", frac=0.2, center=0.7)
door_arc(R_BACK, 22, 3.6, "shutter")
door_arc(R_BACK, 45, 3.6, "shutter")
ring("cold", "Холодильные камеры", "storage", 0, 30, R_BACK, 96, "E", CONC, CWALL, theme="cold")
door_arc(96, 25)
ring("electrical", "Щитовая", "utility", 30, 36, R_BACK, 96, "E", CONC, CWALL, theme="electrical",
     note="рубильник этажа")
door_arc(96, 33)
ring("receiving", "Приёмка товара", "storage", 36, 54, R_BACK, OUTER, "E", CONC, CWALL, theme="hyper_st",
     note="доки, грузовой лифт на 3-й рядом")
for pc in (41, 45, 49):
    h = math.degrees(2.25 / OUTER)
    op_arc(OUTER, pc - h, pc + h, "gate", note="док")
for p in (36, 54):
    op_rad(p, SVC_MID - 0.9, SVC_MID + 0.9, "door")
ring("dock_stair", "Лестница и грузовой лифт", "utility", 54, 60, R_BACK, 96, "E", CONC, CWALL, core=True,
     theme="core_e", note="грузовой лифт на 3-й, закрыт")
op_rad(54, 90.1, 91.9, "door")
shop("bakery", "Пекарня", "E", (0, 3), (10, 0), *R["inn"], [("r1", "O")], back="r0", theme="coffee")
shop("deli", "Кулинария", "E", (10, 0), (20, 0), *R["inn"], [("r0", "O")], back="r1", theme="coffee")
shop("cafe", "Кафе «Ринг»", "E", (20, 0), (40, 0), *R["inn"], [("r0", "O")], back="r1", theme="coffee")
shop("liquor", "Алкоголь и табак", "E", (40, 0), (50, 0), *R["inn"], [("r1", "C")], back="r0", theme="press")
shop("tea", "Чай и кофе", "E", (50, 0), (60, -3), *R["inn"], [("r0", "H")], back="r1", theme="coffee")

# ---------------------------------------------------------------- F — Техника (юго-восток, 300–360)
strip("evac_f", "Проход к пожарному выходу", "corridor", 348, -1.5, 1.5, R["st"][1], OUTER, "F")
across(R["st"][1], 348, -1.5, 1.5)  # выход на фасаде заварен
for dd in (-1.5, 1.5):
    door_along(348, dd, SVC_MID)
stair_strip("stair_f", "F", 348, -8, -1.5, -1.5)
ring("electronics", "Электроника «Вольт»", "retail", 312, 348, 68, R_BACK, "F", theme="electronics",
     sign_color=SIGN["F"])
front_arc(68, 312, sa((348, -1.5), 68), "half", frac=0.7)
door_arc(R_BACK, 324)
door_arc(R_BACK, 340)
ring("electronics_st", "Склад электроники", "storage", 312, 336, R_BACK, 96, "F", CONC, CWALL,
     theme="electronics_st")
door_arc(96, 318)
shop("service", "Сервис «Вольта»", "F", (336, 0), (348, -8), R_BACK, 96, [], back="r1", typ="office", theme="service",
     floor=CONC)
shop("phone_repair", "Ремонт телефонов", "F", (348, 1.5), (360, -4), 68, R_BACK, [("r0", "O")], back="r1",
     theme="phones")
ring("camp_store", "Подсобка лагеря", "storage", 348, 360, R_BACK, 96, "F", CONC, CWALL, theme="workshop")
door_along(360, -8, 91.0)
shop("photo_video", "Фото и видео", "F", (300, 3), (310, 0), *R["inn"], [("r0", "H")], back="r1", theme="photo")
shop("consoles", "Приставки", "F", (310, 0), (320, 0), *R["inn"], [("r0", "C")], back="r1", theme="electronics")
shop("computers", "Компьютеры", "F", (320, 0), (330, 0), *R["inn"], [("r0", "O"), ("r1", "O")], theme="electronics")
shop("audio", "Аудио", "F", (330, 0), (340, 0), *R["inn"], [("r1", "O")], back="r0", theme="electronics")
shop("telecom", "Связь", "F", (340, 0), (350, 0), *R["inn"], [("r0", "X")], theme="phones", note="сгорел")
shop("tech_repair", "Ремонт техники", "F", (350, 0), (360, -3), *R["inn"], [("r1", "O")], back="r0", theme="service")

# ---------------------------------------------------------------- служебный коридор вдоль фасада
# куски между поперечными проходами и серединами секторов (там вестибюль, эвакуационный проход или
# приёмка): двери не дальше ~50 м одна от другой (норма — не реже 60 м)
SVC = [("e1", 0, 36), ("e2", 54, 60), ("d1", 60, 90), ("d2", 90, 120), ("c1", 120, 150), ("c2", 150, 180),
       ("b1", 180, 210), ("b2", 210, 240), ("a1", 240, 270), ("a2", 270, 300), ("f1", 300, 348), ("f2", 348, 360)]
for sid, p0, p1 in SVC:
    letter = sid[0].upper()
    ring(f"svc_{sid}", "Служебный коридор", "corridor", p0, p1, *R["svc"], letter, CONC, CWALL)


# ---------------------------------------------------------------- проверка раскладки

def overlaps() -> list[str]:
    """Кольцевые помещения не должны перекрываться (полосы — можно: они главнее)."""
    bad = []
    rr = [r for r in rooms if "a" in r and r["a"][1] - r["a"][0] < 359.0]
    for i, x in enumerate(rr):
        for y in rr[i + 1:]:
            if min(x["r"][1], y["r"][1]) - max(x["r"][0], y["r"][0]) <= 1e-6:
                continue
            ax0, ax1 = x["a"]
            ay0, ay1 = y["a"]
            for shift in (-360.0, 0.0, 360.0):
                if min(ax1, ay1 + shift) - max(ax0, ay0 + shift) > 1e-6:
                    bad.append(f"{x['id']} × {y['id']}")
    return bad


def main() -> None:
    bad = overlaps()
    assert not bad, "перекрываются: " + ", ".join(bad)
    for r in rooms:
        if "a" in r and r["a"][1] - r["a"][0] < 359.0:
            assert -180.0 <= r["a"][0] and r["a"][1] <= 180.0 + 1e-6, f"через шов ±180: {r['id']} {r['a']}"
    d = {
        "id": "mall_1f",
        "name": "ТЦ «РИНГ» · 1-й этаж (серый черновик)",
        "floor": 1,
        "angle": [-180.0, 180.0],
        "ring": {"outer_r": OUTER, "atrium_r": R["atr"][1], "floors": 4, "zones": R, "sectors_deg": 60, "site_r": SITE},
        "sectors": [{"id": letter.lower(), "letter": letter, "name": title, "a": arng(b, b + 60)}
                    for b, letter, title, _ in SECTORS],
        "walls": {"height": 6.0, "thickness": 0.3, "fence_height": 2.2, "barrier_height": 1.2,
                  "facade": 0.5, "fire": 0.3, "structural": 0.3, "partition": 0.15, "fence": 0.25,
                  "column": 0.6, "column_grid": 9.0, "building_height": 22.5, "site_fence_height": 3.0},
        # колонны каркаса внутри больших залов (на линиях перегородок их роль играет стена)
        "columns": [{"r": 49.0, "step": 10.0, "offset": 0.0}, {"r": 77.0, "step": 6.0, "offset": 0.0}],
        "greybox": True,
        "arch": {"storefront_h": 3.6, "door_h": 2.4, "shutter_h": 3.2, "gate_h": 4.5, "entrance_w": 3.2,
                 "broken_pane_pct": 22, "half_gap": 0.8, "open_split_columns": False,
                 "storefront_split_entrances": False},
        "camera_yaw": 0,
        "spawn": {"a": ga(270), "r": 118},
        "rooms": rooms,
        "openings": ops,
    }
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    shops = sum(1 for r in rooms if r["type"] == "retail")
    print(f"{OUT.relative_to(ROOT)}: помещений {len(rooms)} (магазинных {shops}), проёмов {len(ops)}")


if __name__ == "__main__":
    main()
