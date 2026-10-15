# -*- coding: utf-8 -*-
"""План 1-го этажа ТЦ «РИНГ» Ø200 для отдельной карты ТЦ (предложение, 2026-10-15).

Бумага для согласования с владельцем: не уровень и не данные игры. Описание и разбор —
docs/design/mall_1f_plan.md, территория вокруг — docs/design/mall_map.md.

Координаты: x — восток, y — север (север вверху), центр ТЦ в (0, 0). Угол a — в градусах от востока
против часовой стрелки (90° — север, 270° — юг), как в tools/mall_map_concept.py. В игре угол
отсчитывается от +X к +Z (север = −90°), то есть игровой угол = −a.

Помещение — кольцевой кусок между радиусами r0..r1, ограниченный по бокам либо лучом из центра
(угол b), либо линией, параллельной лучу b на расстоянии d метров (проходы и аллеи постоянной ширины).

    python -X utf8 tools/mall_1f_plan.py  →  docs/design/mall_1f_plan.png
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Rectangle, Wedge

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "design" / "mall_1f_plan.png"

# Пояса кольца, радиусы в метрах (решение владельца 2026-10-15: Ø200, атриум Ø60)
R_ATR = 30.0    # край атриума под куполом, колонны купола
R_GAL = 40.0    # галерея атриума 30–40, витрины внутренних магазинов
R_IN = 58.0     # внутренние магазины 40–58
R_ST = 68.0     # кольцевая улица 58–68
R_BACK = 86.0   # граница торгового зала и подсобок у якорей
R_SV = 96.0     # служебный коридор 96–99.5 вдоль фасада
R_FIN = 99.5
R_FAC = 100.0   # фасад 0.5 м

PASS_IN = 3.0   # полуширина поперечного прохода во внутреннем поясе
PASS_OUT = 2.5  # полуширина поперечного прохода во внешнем поясе
EVAC = 1.5      # полуширина эвакуационного коридора к пожарному выходу

C = {
    "bg": "#ece8dc", "podium": "#e2dccd", "lane": "#a7aaac", "floor": "#f3eee3", "svc": "#d7d0c2",
    "atrium": "#dbe8ef", "lobby": "#efe2c6", "text": "#2b2824", "wall": "#5b5348", "fire": "#8b2f1f",
    "col": "#4b463f", "service": "#d6d2c9", "wc": "#c4d6e4", "stair": "#bdb5a8", "hidden": "#cbbfa9",
    "rubble": "#b3a998", "gold": "#d9a514", "danger": "#c0392b", "blue": "#2d6cc0", "green": "#1e9e4a",
}

SECTORS = {
    # буква: (граница b — сектор занимает b..b+60, название, цвет)
    "A": (240.0, "Аллея", "#cf5a4c"),
    "B": (180.0, "Мода", "#e08e2e"),
    "C": (120.0, "Дом и ремонт", "#c3a21f"),
    "D": (60.0, "Спорт и туризм", "#4e9a4e"),
    "E": (0.0, "Продукты", "#2f8db0"),
    "F": (300.0, "Техника", "#8a5cb8"),
}

# Витрина / вход помещения: состояние
FRONT = {
    "O": {"color": "#2a9d4b", "lw": 2.4, "ls": "-"},                 # открыт, разграблен
    "H": {"color": "#e08a00", "lw": 2.6, "ls": (0, (2.6, 1.4))},     # роллета наполовину — ползком
    "C": {"color": "#9c3d0c", "lw": 3.4, "ls": "-"},                 # роллета закрыта — вход сзади
    "P": {"color": "#c2185b", "lw": 3.6, "ls": "-"},                 # электророллета — нужно питание
    "X": {"color": "#3f3f3f", "lw": 3.4, "ls": "-"},                 # сгорел / завален — не пройти
    "K": {"color": "#d62828", "lw": 3.8, "ls": "-"},                 # дверь на ключ
}

PT_PER_M = 1.0  # пунктов на метр, считается в main() по размеру оси


def pol(a_deg: float, r: float) -> tuple[float, float]:
    a = math.radians(a_deg)
    return r * math.cos(a), r * math.sin(a)


def tint(hex_color: str, k: float) -> str:
    """Смешать цвет с белым: k = 0 — исходный, 1 — белый."""
    h = hex_color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{int(c + (255 - c) * k):02x}" for c in rgb)


def side_angle(side: tuple[float, float], r: float) -> float:
    """Угол боковой границы на радиусе r: луч b (d = 0) или линия, параллельная лучу b, на расстоянии d."""
    b, d = side
    return b + math.degrees(math.asin(max(-1.0, min(1.0, d / r))))


def S(b: float, d: float = 0.0) -> tuple[float, float]:
    return (b, d)


def band_poly(r0: float, r1: float, right: tuple[float, float], left: tuple[float, float]) -> list[tuple[float, float]]:
    """Контур кольцевого куска: справа (по часовой) — right, слева — left."""
    pts: list[tuple[float, float]] = []
    n = 16
    for i in range(n + 1):
        r = r0 + (r1 - r0) * i / n
        pts.append(pol(side_angle(right, r), r))
    a0, a1 = side_angle(right, r1), side_angle(left, r1)
    m = max(2, int(abs(a1 - a0) / 1.0))
    pts += [pol(a0 + (a1 - a0) * i / m, r1) for i in range(1, m)]
    for i in range(n + 1):
        r = r1 - (r1 - r0) * i / n
        pts.append(pol(side_angle(left, r), r))
    a0, a1 = side_angle(left, r0), side_angle(right, r0)
    m = max(2, int(abs(a1 - a0) / 1.0))
    pts += [pol(a0 + (a1 - a0) * i / m, r0) for i in range(1, m)]
    return pts


def poly_area(pts: list[tuple[float, float]]) -> float:
    s = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        s += x0 * y1 - x1 * y0
    return abs(s) / 2.0


@dataclass
class Room:
    name: str
    r0: float
    r1: float
    right: tuple[float, float]
    left: tuple[float, float]
    sec: str
    kind: str = "shop"  # shop, anchor, back, service, wc, stair, hidden, lobby, rubble
    fronts: list[tuple] = field(default_factory=list)  # (край, состояние[, подпись]); край r0/r1/right/left, «:door» — дверь
    star: bool = False
    note: str = ""
    area: bool = True
    fs: float = 6.4
    rot: str = "auto"
    lab: tuple[float, float] | None = None  # (угол, радиус) подписи

    def poly(self) -> list[tuple[float, float]]:
        return band_poly(self.r0, self.r1, self.right, self.left)

    def m2(self) -> float:
        return poly_area(self.poly())

    def mid(self) -> tuple[float, float]:
        if self.lab:
            return self.lab
        rm = (self.r0 + self.r1) / 2.0
        return ((side_angle(self.right, rm) + side_angle(self.left, rm)) / 2.0, rm)


def build_rooms() -> list[Room]:
    """Все помещения этажа. Сектор занимает b..b+60, ядро — у его границы b по часовой."""
    R: list[Room] = []

    def core(sec: str, b: float, r1: float = R_SV, split: float = 80.0, right_d: float = PASS_OUT) -> None:
        R.append(Room("WC", R_ST, split, S(b, right_d), S(b + 12), sec, "wc", area=False, fs=6.0,
                      note="М · Ж · МГН"))
        R.append(Room("Л", split, r1, S(b, right_d), S(b + 12), sec, "stair", area=False, fs=7.5,
                      note="лифт"))

    # ---------------- A — Аллея (юг, 240–300): главный вход ----------------
    core("A", 240)
    R += [
        Room("Аптека", R_ST, 77, S(252), S(270, -7), "A", fronts=[("r0", "H"), ("left", "H")], star=True),
        Room("Цветы", 77, R_BACK, S(252), S(270, -7), "A", fronts=[("left", "O")]),
        Room("Пост охраны ТЦ", R_BACK, R_SV, S(252), S(270, -16), "A", "service",
             fronts=[("r1:door", "K", "К1")], star=True, fs=6.0),
        Room("Л", R_BACK, R_SV, S(270, -16), S(270, -10), "A", "stair", area=False, fs=7.0),
        Room("Л", R_BACK, R_SV, S(270, 10), S(270, 16), "A", "stair", area=False, fs=7.0),
        Room("Администрация", R_BACK, R_SV, S(270, 16), S(288), "A", "service",
             fronts=[("r1:door", "K", "К3")], star=True, note="сейф", fs=6.0),
        Room("Салон связи", R_ST, 77, S(270, 7), S(288), "A", fronts=[("r0", "O"), ("right", "O")]),
        Room("Кофейня", 77, R_BACK, S(270, 7), S(288), "A", fronts=[("right", "X")]),
        Room("Детский мир", R_ST, R_SV, S(288), S(300, -PASS_OUT), "A", fronts=[("r0", "C")]),
        Room("Оптика", R_GAL, R_IN, S(240, PASS_IN), S(250), "A", fronts=[("r0", "O")]),
        Room("Ювелирный", R_GAL, R_IN, S(250), S(270, -7), "A", fronts=[("r0", "H"), ("left", "H")], star=True),
        Room("Банк", R_GAL, R_IN, S(270, 7), S(287), "A", fronts=[("right", "O"), ("r0", "O")], lab=(279.0, 45.0)),
        Room("Ломбард", R_GAL, R_IN, S(287), S(300, -PASS_IN), "A", fronts=[("r0", "C")], star=True),
    ]
    # хранилище банка — комнатой в глубине банка
    R.append(Room("Хранилище", 51, R_IN, S(281), S(287), "A", "service", fronts=[("r0:door", "K", "К4")],
                  star=True, fs=5.6, area=False))

    # ---------------- B — Мода (юго-запад, 180–240) ----------------
    core("B", 180)
    R += [
        Room("«Модный дом»", R_ST, R_BACK, S(192), S(210, -EVAC), "B", "anchor", fronts=[("r0", "O")]),
        Room("склад", R_BACK, R_SV, S(192), S(210, -8), "B", "back", area=False, fs=5.8),
        Room("Л", R_BACK, R_SV, S(210, -8), S(210, -EVAC), "B", "stair", area=False, fs=7.0),
        Room("Обувь", R_ST, R_SV, S(210, EVAC), S(222), "B", fronts=[("r0", "H")]),
        Room("Джинсы", R_ST, R_SV, S(222), S(231), "B", fronts=[("r0", "O")]),
        Room("Бельё", R_ST, R_SV, S(231), S(240, -PASS_OUT), "B", fronts=[("r0", "C")]),
        Room("Парикмахерская", R_GAL, R_IN, S(180, PASS_IN), S(190), "B", fronts=[("r0", "O")], fs=5.8),
        Room("Часы", R_GAL, R_IN, S(190), S(200), "B", fronts=[("r0", "H")]),
        Room("Сумки", R_GAL, R_IN, S(200), S(210), "B", fronts=[("r1", "O")]),
        Room("Косметика", R_GAL, R_IN, S(210), S(220), "B", fronts=[("r0", "O"), ("r1", "O")], note="насквозь"),
        Room("Бижутерия", R_GAL, R_IN, S(220), S(230), "B", fronts=[("r0", "C")]),
        Room("Ключи, обувь", R_GAL, R_IN, S(230), S(240, -PASS_IN), "B", fronts=[("r1", "O")], fs=5.8),
    ]

    # ---------------- C — Дом и ремонт (северо-запад, 120–180) ----------------
    core("C", 120)
    R += [
        Room("«Дом и ремонт»", R_ST, R_BACK, S(132), S(150, -EVAC), "C", "anchor", fronts=[("r0", "C")],
             note="инструмент"),
        Room("склад", R_BACK, R_SV, S(132), S(150, -8), "C", "back", area=False, fs=5.8),
        Room("Л", R_BACK, R_SV, S(150, -8), S(150, -EVAC), "C", "stair", area=False, fs=7.0),
        Room("Товары для дома", R_ST, R_SV, S(150, EVAC), S(162), "C", fronts=[("r0", "O")], fs=6.0),
        Room("Зоотовары", R_ST, R_SV, S(162), S(171), "C", fronts=[("r0", "O")]),
        Room("Хозтовары", R_ST, 88, S(171), S(180, -PASS_OUT), "C", fronts=[("r0", "H")]),
        Room("Тайник", 88, R_SV, S(171), S(180, -PASS_OUT), "C", "hidden", fronts=[("r1:door", "K", "К7")],
             star=True, area=False, fs=5.8),
        Room("Текстиль", R_GAL, R_IN, S(120, PASS_IN), S(130), "C", fronts=[("r0", "O")]),
        Room("Посуда", R_GAL, R_IN, S(130), S(140), "C", fronts=[("r1", "O")]),
        Room("Сад", R_GAL, R_IN, S(140), S(150), "C", fronts=[("r0", "H")]),
        Room("Фотоателье", R_GAL, R_IN, S(150), S(160), "C", fronts=[("r0", "O"), ("r1", "O")], note="насквозь"),
        Room("Книги", R_GAL, R_IN, S(160), S(170), "C", fronts=[("r0", "X")], note="сгорел"),
        Room("Табак", R_GAL, R_IN, S(170), S(180, -PASS_IN), "C", fronts=[("r1", "H")]),
    ]

    # ---------------- D — Спорт и туризм (север, 60–120): северный вход завален ----------------
    core("D", 60)
    R += [
        Room("Спорттовары", R_ST, R_BACK, S(72), S(90, -6), "D", "anchor", fronts=[("r0", "O"), ("left", "O")]),
        Room("склад", R_BACK, R_SV, S(72), S(90, -16), "D", "back", area=False, fs=5.8),
        Room("Л", R_BACK, R_SV, S(90, -16), S(90, -10), "D", "stair", area=False, fs=7.0),
        Room("Л", R_BACK, R_SV, S(90, 10), S(90, 16), "D", "stair", area=False, fs=7.0, note="засыпана"),
        Room("Туризм", R_ST, R_BACK, S(90, 6), S(108), "D", fronts=[("right", "O"), ("r0", "H")]),
        Room("склад", R_BACK, R_SV, S(90, 16), S(108), "D", "back", area=False, fs=5.8),
        Room("Оружейный «Тайга»", R_ST, R_SV, S(108), S(120, -PASS_OUT), "D", fronts=[("r0", "P", "К6")],
             star=True, note="охота и рыбалка", fs=6.0),
        Room("Спортпит", R_GAL, R_IN, S(60, PASS_IN), S(72), "D", fronts=[("r0", "C")]),
        Room("Велосипеды", R_GAL, R_IN, S(72), S(90, -6), "D", fronts=[("r0", "O"), ("left", "O")]),
        Room("Игрушки", R_GAL, R_IN, S(90, 6), S(108), "D", fronts=[("right", "O"), ("r0", "O")]),
        Room("Медпункт ТЦ", R_GAL, R_IN, S(108), S(120, -PASS_IN), "D", "service",
             fronts=[("r1:door", "K", "К2")], star=True, fs=6.0),
    ]

    # ---------------- E — Продукты (северо-восток, 0–60): доки, щитовая ----------------
    R += [
        Room("WC", R_ST, 77, S(0, 4), S(12), "E", "wc", area=False, fs=6.0, note="М · Ж · МГН"),
        Room("Л", 77, R_BACK, S(0, 4), S(12), "E", "stair", area=False, fs=7.0, note="лифт"),
        Room("Супермаркет «Корзина»", R_ST, R_BACK, S(12), S(60, -PASS_OUT), "E", "anchor",
             fronts=[("r0", "O")], fs=7.4),
        Room("Холодильные камеры", R_BACK, R_SV, S(0, 8), S(30), "E", "back", fs=5.8,
             fronts=[("r1:door", "C")]),
        Room("Щитовая", R_BACK, R_SV, S(30), S(36), "E", "service", area=False, fs=5.8, lab=(33.0, 89.6)),
        Room("Приёмка товара", R_BACK, R_FIN, S(36), S(54), "E", "service", fs=6.0, note="у доков", lab=(45.0, 90.0)),
        Room("Л", R_BACK, R_SV, S(54), S(60, -PASS_OUT), "E", "stair", area=False, fs=6.5,
             note="груз. лифт\nна 3-й"),
        Room("Пекарня", R_GAL, R_IN, S(0, PASS_IN), S(10), "E", fronts=[("r1", "O")]),
        Room("Кулинария", R_GAL, R_IN, S(10), S(20), "E", fronts=[("r0", "O")]),
        Room("Кафе «Ринг»", R_GAL, R_IN, S(20), S(40), "E", fronts=[("r0", "O")]),
        Room("Алкоголь, табак", R_GAL, R_IN, S(40), S(50), "E", fronts=[("r1", "C")], fs=5.8),
        Room("Чай и кофе", R_GAL, R_IN, S(50), S(60, -PASS_IN), "E", fronts=[("r0", "H")], fs=6.0),
    ]
    # восточный вестибюль — лагерь у баррикады
    R.append(Room("вестибюль:\nлагерь", R_BACK, R_FIN, S(0, -8), S(0, 8), "E", "lobby", area=False, fs=5.6,
                  lab=(0.0, 89.6)))

    # ---------------- F — Техника (юго-восток, 300–360) ----------------
    core("F", 300)
    R += [
        Room("Электроника «Вольт»", R_ST, R_BACK, S(312), S(348, -EVAC), "F", "anchor", fronts=[("r0", "H")],
             fs=7.4),
        Room("Склад электроники", R_BACK, R_SV, S(312), S(336), "F", "service", fronts=[("r1:door", "K", "К5")],
             star=True, fs=6.0),
        Room("Сервис", R_BACK, R_SV, S(336), S(348, -8), "F", "back", area=False, fs=5.8),
        Room("Л", R_BACK, R_SV, S(348, -8), S(348, -EVAC), "F", "stair", area=False, fs=7.0),
        Room("Ремонт телефонов", R_ST, R_BACK, S(348, EVAC), S(360, -4), "F", fronts=[("r0", "O")], fs=5.8),
        Room("подсобка лагеря", R_BACK, R_SV, S(348, EVAC), S(360, -8), "F", "back", area=False, fs=5.4),
        Room("Фото и видео", R_GAL, R_IN, S(300, PASS_IN), S(310), "F", fronts=[("r0", "H")], fs=6.0),
        Room("Приставки", R_GAL, R_IN, S(310), S(320), "F", fronts=[("r0", "C")]),
        Room("Компьютеры", R_GAL, R_IN, S(320), S(330), "F", fronts=[("r0", "O"), ("r1", "O")], note="насквозь"),
        Room("Аудио", R_GAL, R_IN, S(330), S(340), "F", fronts=[("r1", "O")]),
        Room("Связь", R_GAL, R_IN, S(340), S(350), "F", fronts=[("r0", "X")], note="сгорел"),
        Room("Ремонт техники", R_GAL, R_IN, S(350), S(360, -PASS_IN), "F", fronts=[("r1", "O")], fs=5.8),
    ]

    # вестибюли и завалы главных входов
    R.append(Room("Главный вестибюль", R_BACK, R_FIN, S(270, -10), S(270, 10), "A", "lobby", area=False, fs=6.0,
                  note="частично обрушен", lab=(270.0, 89.3)))
    R.append(Room("Северный вестибюль", R_BACK, R_FIN, S(90, -10), S(90, 10), "D", "rubble", area=False, fs=6.0,
                  note="завал", lab=(90.0, 92.0)))
    return R


def draw_front(ax, room: Room, edge: str, status: str, tag: str | None) -> tuple[float, float]:
    """Витрина, роллета или дверь на краю помещения. Возвращает середину — для подписи ключа."""
    st = FRONT[status]
    door = edge.endswith(":door")
    edge = edge.split(":")[0]
    if edge in ("r0", "r1"):
        r = room.r0 if edge == "r0" else room.r1
        a0, a1 = side_angle(room.right, r), side_angle(room.left, r)
        pad = 0.9 / r * 180 / math.pi
        a0, a1 = a0 + pad, a1 - pad
        if door:
            am = (a0 + a1) / 2.0
            half = 1.4 / r * 180 / math.pi
            a0, a1 = am - half, am + half
        pts = [pol(a0 + (a1 - a0) * i / 30, r) for i in range(31)]
    else:
        side = room.right if edge == "right" else room.left
        r0, r1 = room.r0 + 0.9, room.r1 - 0.9
        if door:
            rm = (r0 + r1) / 2.0
            r0, r1 = rm - 1.4, rm + 1.4
        pts = [pol(side_angle(side, r0 + (r1 - r0) * i / 20), r0 + (r1 - r0) * i / 20) for i in range(21)]
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=st["color"], lw=st["lw"], ls=st["ls"], solid_capstyle="butt", zorder=8)
    mx, my = pts[len(pts) // 2]
    if status == "P":
        ax.text(mx, my, "⚡", fontsize=9, color="#c2185b", ha="center", va="center", zorder=13, weight="bold",
                bbox={"boxstyle": "circle,pad=0.12", "fc": "#fff3b0", "ec": "#c2185b", "lw": 0.8})
    if tag:
        # метка ключа — снаружи помещения, чтобы не закрывать подпись
        if edge in ("r0", "r1"):
            r = room.r0 - 1.9 if edge == "r0" else room.r1 + 1.9
            am = (side_angle(room.right, r) + side_angle(room.left, r)) / 2.0
            if status == "P":
                am += math.degrees(3.4 / r)
            tx, ty = pol(am, r)
        else:
            tx, ty = mx, my
        ax.text(tx, ty, tag, fontsize=6.2, color="white", ha="center", va="center", zorder=13, weight="bold",
                bbox={"boxstyle": "round,pad=0.18", "fc": FRONT["K"]["color"], "ec": "white", "lw": 0.6})
    return mx, my


def text_rot(a: float) -> float:
    rot = a % 180.0
    return rot - 180.0 if rot > 90.0 else rot


def draw_room(ax, room: Room) -> None:
    col = SECTORS[room.sec][2]
    dead = any(s == "X" for _, s, *_ in room.fronts)
    fill = {
        "shop": tint(col, 0.80), "anchor": tint(col, 0.60), "back": tint(col, 0.88), "service": C["service"],
        "wc": C["wc"], "stair": C["stair"], "hidden": C["hidden"], "lobby": C["lobby"], "rubble": C["rubble"],
    }[room.kind]
    hatch = {"stair": "----", "hidden": "....", "rubble": "xxx"}.get(room.kind)
    if dead:
        fill, hatch = "#c9c4bb", "////"
    ax.add_patch(Polygon(room.poly(), closed=True, fc=fill, ec=C["wall"], lw=0.7, zorder=4, hatch=hatch))

    a, r = room.mid()
    x, y = pol(a, r)
    lines = [room.name]
    if room.note:
        lines.append(room.note)
    if room.area and room.kind in ("shop", "anchor", "service"):
        lines.append(f"≈{round(room.m2() / 10) * 10:.0f} м²")
    bold = room.kind == "anchor"
    rot, fs = label_fit(room, a, r, lines)
    box = {"boxstyle": "round,pad=0.15", "fc": "#fbf9f3", "ec": "none", "alpha": 0.8} \
        if room.kind in ("rubble", "lobby") else None
    ax.text(x, y, "\n".join(lines), fontsize=fs, color=C["text"], ha="center", va="center", rotation=rot,
            rotation_mode="anchor", zorder=14, linespacing=1.05, weight="bold" if bold else "normal", bbox=box)
    if room.star:
        # звезда — во внешнем правом углу помещения
        rr = room.r1 - 2.4
        sa = side_angle(room.right, rr) + math.degrees(2.2 / rr)
        ax.plot(*pol(sa, rr), marker="*", ms=11, mfc=C["gold"], mec="#5a4300", mew=0.7, zorder=15)


def label_fit(room: Room, a: float, r: float, lines: list[str]) -> tuple[float, float]:
    """Поворот и кегль подписи: сначала горизонтально, потом по дуге, потом по радиусу — что влезает."""
    width = abs(math.radians(side_angle(room.left, r) - side_angle(room.right, r))) * r - 1.2
    depth = room.r1 - room.r0 - 1.2
    if room.rot == "r":
        return text_rot(a), room.fs
    ar = math.radians(a)
    fs = room.fs
    for _ in range(4):
        w = max(len(s) for s in lines) * fs * 0.56 / PT_PER_M
        h = len(lines) * fs * 1.12 / PT_PER_M
        horiz_t = w * abs(math.sin(ar)) + h * abs(math.cos(ar))
        horiz_u = w * abs(math.cos(ar)) + h * abs(math.sin(ar))
        if horiz_t <= width and horiz_u <= depth:
            return 0.0, fs
        if w <= width and h <= depth:
            return text_rot(a - 90.0), fs
        if h <= width and w <= depth:
            return text_rot(a), fs
        fs *= 0.92
    return (text_rot(a) if depth > width else text_rot(a - 90.0)), fs


def columns() -> list[tuple[float, float]]:
    """Сетка колонн: купол — через 15° по r 30; внутренний пояс — 10° по r 40/49/58; внешний — 6° по r 68–96."""
    pts: list[tuple[float, float]] = []
    pts += [pol(a, R_ATR) for a in range(0, 360, 15)]
    for r in (R_GAL, 49.0, R_IN):
        pts += [pol(a, r) for a in range(0, 360, 10)]
    for r in (R_ST, 77.0, 86.5, R_SV):
        pts += [pol(a, r) for a in range(0, 360, 6)]
    return pts


def rect_at(ax, a: float, r: float, w: float, h: float, fc: str, ec: str = "#4c463f", lw: float = 0.7,
            z: float = 9, tangential: bool = True, hatch: str | None = None) -> None:
    """Прямоугольник w (по дуге) × h (по радиусу), центр на (a, r)."""
    x, y = pol(a, r)
    rot = a - 90.0 if tangential else a
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, angle=rot, rotation_point="center", fc=fc, ec=ec,
                           lw=lw, zorder=z, hatch=hatch))


def escalator_pair(ax, a: float, r: float) -> None:
    """Пара эскалаторов по радиусу: низ у фонтана, верхняя площадка — на краю галереи 2-го этажа."""
    x, y = pol(a, r)
    ax.add_patch(Rectangle((x - 7.5, y - 1.85), 15, 3.7, angle=a, rotation_point="center", fc="#666c73",
                           ec="#3e4246", lw=0.9, zorder=9))
    ax.add_patch(Rectangle((x - 7.5, y - 0.2), 15, 0.4, angle=a, rotation_point="center", fc="#3e4246",
                           ec="none", zorder=9.2))
    ax.text(x, y, "эскалаторы ↑2-й", fontsize=5.2, color="white", ha="center", va="center",
            rotation=text_rot(a), zorder=14, linespacing=1.0)


def main() -> None:
    global PT_PER_M
    fig = plt.figure(figsize=(25.0, 17.0), dpi=105)
    fig.patch.set_facecolor(C["bg"])
    ax = fig.add_axes([0.005, 0.01, 0.655, 0.965])
    lim = 128.0
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.axis("off")
    PT_PER_M = 0.655 * 25.0 * 72.0 / (2 * lim)

    # --- снаружи: подиум с тротуаром (дальше — схема территории mall_map_concept.png)
    ax.add_patch(Circle((0, 0), 108, fc=C["podium"], ec="#a49c8b", lw=0.8, zorder=0.6))

    # --- полоса цвета сектора по фасаду и буква сектора
    for letter, (b, title, col) in SECTORS.items():
        ax.add_patch(Wedge((0, 0), 104.5, b + 0.6, b + 59.4, width=3.6, fc=col, ec="none", zorder=1))
        x, y = pol(b + 6, 114.0)
        ax.add_patch(Circle((x, y), 5.2, fc=col, ec="white", lw=1.6, zorder=20))
        ax.text(x, y, letter, fontsize=13, color="white", weight="bold", ha="center", va="center", zorder=21)
        tx, ty = x, y + (8.4 if y >= 0 else -8.4)
        ax.text(tx, ty, title, fontsize=8.6, color=tint(col, -0.0), weight="bold", ha="center", va="center",
                zorder=21)

    # --- пол общих зон, служебный коридор, атриум
    ax.add_patch(Circle((0, 0), R_FIN, fc=C["floor"], ec="none", zorder=2))
    ax.add_patch(Wedge((0, 0), R_FIN, 0, 360, width=R_FIN - R_SV, fc=C["svc"], ec="none", zorder=2.2))
    ax.add_patch(Circle((0, 0), R_ATR, fc=C["atrium"], ec="#7f9cad", lw=1.0, zorder=2.4))
    # поперечные проходы и эвакуационные коридоры доходят до фасада поверх служебного коридора
    for b in (60, 120, 180, 240, 300):
        ax.add_patch(Polygon(band_poly(R_SV, R_FIN, S(b, -PASS_OUT), S(b, PASS_OUT)), fc=C["floor"], ec="none",
                             zorder=2.3))
    for b in (150, 210, 348):
        ax.add_patch(Polygon(band_poly(R_SV, R_FIN, S(b, -EVAC), S(b, EVAC)), fc=C["floor"], ec="none", zorder=2.3))

    rooms = build_rooms()
    for room in rooms:
        draw_room(ax, room)

    # --- стены: фасад, служебный коридор, противопожарные стены по границам секторов
    ax.add_patch(Circle((0, 0), R_FAC, fc="none", ec="#2f2a24", lw=4.2, zorder=6))
    ax.add_patch(Circle((0, 0), R_SV, fc="none", ec=C["wall"], lw=1.4, zorder=5.2))
    for b in (0, 60, 120, 180, 240, 300):
        out = 4.0 if b == 0 else PASS_OUT
        for d in (-PASS_IN, PASS_IN):
            ax.plot(*zip(*[pol(side_angle(S(b, d), r), r) for r in (R_GAL, R_IN)]), color=C["fire"], lw=2.2,
                    zorder=6.5)
        for d, r_end in ((-out, R_SV if b != 0 else R_BACK), (out, R_SV if b != 0 else R_BACK)):
            ax.plot(*zip(*[pol(side_angle(S(b, d), r), r) for r in (R_ST, r_end)]), color=C["fire"], lw=2.2,
                    zorder=6.5)

    # --- колонны 0.6 × 0.6 (точки крупнее, чтобы было видно)
    cx, cy = zip(*columns())
    ax.scatter(cx, cy, s=(1.0 * PT_PER_M) ** 2, marker="s", c=C["col"], zorder=7, linewidths=0)

    # --- витрины, роллеты, двери
    for room in rooms:
        for f in room.fronts:
            draw_front(ax, room, f[0], f[1], f[2] if len(f) > 2 else None)
    # подсобки внешних магазинов: пунктир на r 89 (дверь — в служебный коридор)
    for room in rooms:
        if room.kind == "shop" and room.r0 == R_ST and room.r1 == R_SV:
            a0, a1 = side_angle(room.right, 89.0), side_angle(room.left, 89.0)
            ax.plot(*zip(*[pol(a0 + (a1 - a0) * i / 20, 89.0) for i in range(21)]), color=C["wall"], lw=0.6,
                    ls=(0, (2, 2)), zorder=5)

    # --- противопожарные шторы на кольцевой улице у границ секторов
    curtains = {0: "up", 60: "up", 120: "down", 180: "up", 240: "up", 300: "half"}
    for b, st in curtains.items():
        pts = [pol(side_angle(S(b, -PASS_IN - 1.0), r), r) for r in (R_IN, R_ST)]
        style = {"up": ("#9a8f80", 1.0, (0, (1, 1.5))), "down": ("#d62828", 4.0, "-"),
                 "half": ("#d62828", 3.6, (0, (2, 1.2)))}[st]
        ax.plot(*zip(*pts), color=style[0], lw=style[1], ls=style[2], zorder=8.5, solid_capstyle="butt")

    # --- двери служебного коридора (не длиннее 60 м между дверями — норма)
    svc_doors = []
    for b in (0, 60, 120, 180, 240, 300):
        out = 8.0 if b == 0 else PASS_OUT
        svc_doors += [(S(b, -out), "door"), (S(b, out), "door")]
    for b, d in ((150, EVAC), (210, EVAC), (348, EVAC)):
        svc_doors += [(S(b, -d), "door"), (S(b, d), "door")]
    svc_doors += [(S(36), "door"), (S(54), "door"), (S(270, -10), "door"), (S(270, 10), "door"),
                  (S(90, -10), "rubble"), (S(90, 10), "rubble")]
    locked = {(240.0, -PASS_OUT): "К2", (60.0, PASS_OUT): "К2"}
    welded = {(120.0, PASS_OUT)}
    for side, kind in svc_doors:
        pts = [pol(side_angle(side, r), r) for r in (R_SV + 0.2, R_FIN - 0.2)]
        key = locked.get((float(side[0]), float(side[1])))
        if (float(side[0]), float(side[1])) in welded:
            ax.plot(*zip(*pts), color="black", lw=3.2, zorder=8.6, solid_capstyle="butt")
            mx, my = pol(side_angle(side, 97.75), 97.75)
            ax.text(mx, my, "×", fontsize=9, color="black", ha="center", va="center", zorder=13, weight="bold")
        elif kind == "rubble":
            continue
        elif key:
            ax.plot(*zip(*pts), color=FRONT["K"]["color"], lw=3.6, zorder=8.6, solid_capstyle="butt")
            mx, my = pol(side_angle(side, 97.75) + (1.6 if side[1] > 0 else -1.6), 102.0)
            ax.text(mx, my, key, fontsize=5.8, color="white", ha="center", va="center", zorder=13, weight="bold",
                    bbox={"boxstyle": "round,pad=0.15", "fc": FRONT["K"]["color"], "ec": "white", "lw": 0.5})
        else:
            ax.plot(*zip(*pts), color="#5b5348", lw=1.6, zorder=8.6, solid_capstyle="butt")

    # --- атриум: фонтан, эскалаторы, панорамный лифт, обломки купола, островки
    ax.add_patch(Circle((0, 0), 6.0, fc="#b9cfdb", ec="#6f8fa1", lw=1.0, zorder=9))
    ax.text(0, 0, "сухой\nфонтан", fontsize=5.6, ha="center", va="center", zorder=14, color="#3b5566")
    for a in (90.0, 210.0, 330.0):
        escalator_pair(ax, a, 21.0)
    lx, ly = pol(150.0, 24.0)
    ax.add_patch(Circle((lx, ly), 1.9, fc="#9fb4c2", ec="#3e4246", lw=0.9, zorder=9))
    ax.text(lx, ly - 4.0, "панорамный\nлифт (стоит)", fontsize=5.0, ha="center", va="center", zorder=14)
    import random
    rnd = random.Random(5)
    for i in range(14):  # обломки купола: часть стекла и каркаса рухнула внутрь
        a = 35 + rnd.uniform(-14, 14)
        r = 13 + rnd.uniform(-5, 6)
        x, y = pol(a, r)
        w, h = rnd.uniform(1.0, 3.6), rnd.uniform(0.6, 2.2)
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, angle=rnd.uniform(0, 180), rotation_point="center",
                               fc="#8d8a84", ec="#4f4b45", lw=0.4, zorder=9))
    tx, ty = pol(35, 7.5)
    ax.text(tx, ty, "обломки купола", fontsize=5.4, ha="center", va="center", zorder=14, color="#4f4b45",
            style="italic")
    for a in (0, 45, 135, 180, 225, 315):  # кадки с деревьями
        ax.add_patch(Circle(pol(a + 20, 12.5), 1.6, fc="#a9c08f", ec="#6f8659", lw=0.6, zorder=9))
    for a in (15, 45, 75, 105, 135, 165, 195, 225, 255, 285, 315, 345):  # островки-киоски в галерее
        rect_at(ax, a, 35.0, 3.2, 2.0, "#cbb994")
    for b in (0, 60, 120, 180, 240, 300):  # островки и лавки на кольцевой улице
        for k in (18, 42):
            if (b + k) % 360 in (90, 270):
                continue
            rect_at(ax, b + k, 63.0, 3.6, 2.2, "#cbb994")
    rect_at(ax, 270.0, 37.5, 6.0, 2.4, "#9c8d72")  # информационная стойка у устья аллеи
    ix, iy = pol(270.0, 33.6)
    ax.text(ix, iy, "инфостойка", fontsize=5.0, ha="center", va="center", zorder=14)

    # --- главный вход: пролом в завале; северный — завал целиком
    for i in range(18):
        a = 270 + rnd.uniform(-5.5, 5.5)
        r = rnd.uniform(93, 99)
        if abs(a - 270) < 1.6:
            continue  # проход между обломками
        x, y = pol(a, r)
        w, h = rnd.uniform(1.2, 3.4), rnd.uniform(0.8, 2.4)
        ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, angle=rnd.uniform(0, 180), rotation_point="center",
                               fc="#8d8a84", ec="#4f4b45", lw=0.4, zorder=9))

    # --- баррикада и лагерь у восточного входа (кто сидит — на согласование)
    for i, (a, r) in enumerate(((-2.5, 101.5), (2.5, 101.5), (0, 104.5), (-5, 106.5), (5, 106.5))):
        rect_at(ax, a, r, 5.0, 1.6, C["danger"], z=10, ec="#5a1a12")
    for a, r in ((-3.4, 95.5), (3.4, 95.5)):
        rect_at(ax, a, r, 2.4, 1.6, "#7c8f6a", z=10, ec="#4f5c41")

    # --- шкафы и стеллажи у якорей: зал читается по рядам
    for k in range(14):
        a = 15 + k * 3.1
        ax.plot(*zip(pol(a, 72.5), pol(a, 83.0)), color=tint(SECTORS["E"][2], 0.25), lw=1.6, zorder=8.2)
    for k in range(5):  # кассы супермаркета
        rect_at(ax, 17 + k * 2.6, 70.0, 1.2, 1.6, "#6b7f8a", z=9)
    for k in range(9):
        a = 315 + k * 3.6
        rect_at(ax, a, 76.0, 3.0, 5.0, tint(SECTORS["F"][2], 0.3), z=8.2, ec="none")
    for k in range(4):
        a = 194 + k * 3.8
        ax.plot(*zip(pol(a, 72.0), pol(a, 82.0)), color=tint(SECTORS["B"][2], 0.25), lw=1.4, zorder=8.2)
    for k in range(4):
        a = 134 + k * 3.8
        ax.plot(*zip(pol(a, 72.0), pol(a, 82.0)), color=tint(SECTORS["C"][2], 0.25), lw=1.4, zorder=8.2)

    # --- входы и выходы на фасаде
    def ext_door(a: float, kind: str, text: str, r_text: float = 113.0, ha: str = "center") -> None:
        x, y = pol(a, R_FAC)
        style = {"main": ("#1e9e4a", "s"), "two": ("#2d6cc0", "s"), "barricade": (C["danger"], "s"),
                 "oneway": ("#2d6cc0", ">"), "welded": ("#222222", "X"), "rubble": ("#777777", "X"),
                 "dock": ("#2d6cc0", "s")}[kind]
        if kind == "oneway":
            ax.annotate("", xy=pol(a, 107.5), xytext=pol(a, 100.0),
                        arrowprops={"arrowstyle": "-|>", "lw": 2.2, "color": style[0]}, zorder=16)
        else:
            ax.plot([x], [y], marker=style[1], ms=9 if kind != "welded" else 8, mfc=style[0], mec="white", mew=1.0,
                    zorder=16)
        if text:
            tx, ty = pol(a, r_text)
            ax.text(tx, ty, text, fontsize=6.6, color=style[0] if kind not in ("welded", "rubble") else "#333",
                    ha=ha, va="center", zorder=21, weight="bold", linespacing=1.05,
                    bbox={"boxstyle": "round,pad=0.2", "fc": "#fbf9f3", "ec": "none", "alpha": 0.85})

    ext_door(270, "main", "ГЛАВНЫЙ ВХОД ↕\nчастично обрушен,\nпролом посередине", 115.5)
    ext_door(0, "barricade", "ВОСТОЧНЫЙ ВХОД\nбаррикада ↕\nнад ним мост\nс паркинга на 2-й", 116.0)
    for a in (41, 45, 49):
        ext_door(a, "dock", "")
    tx, ty = pol(45, 113.5)
    ax.text(tx, ty, "ДОКИ ↕ служебный вход\nиз двора разгрузки (−4 м)", fontsize=6.6, color=C["blue"], ha="center",
            va="center", weight="bold", zorder=21, rotation=0,
            bbox={"boxstyle": "round,pad=0.2", "fc": "#fbf9f3", "ec": "none", "alpha": 0.85})
    ext_door(90, "rubble", "СЕВЕРНЫЙ ВХОД ЗАВАЛЕН", 109.5)
    ext_door(180, "two", "ЗАПАДНЫЙ\nпожарный ↕", 113.5)
    ext_door(120, "oneway", "только\nизнутри", 112.0)
    ext_door(210, "oneway", "только\nизнутри", 112.0)
    ext_door(300, "oneway", "только\nизнутри", 112.0)
    for a in (60, 150, 240, 348):
        ext_door(a, "welded", "")

    # --- пути через этаж (полупрозрачные линии по осям проходов)
    def path(pts, col, lw_m, ls, z=10.5) -> None:
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=col, lw=lw_m * PT_PER_M, ls=ls, alpha=0.5, zorder=z, solid_capstyle="round",
                dash_capstyle="round")

    p1 = "#d6336c"
    path([pol(270, 98), pol(270, 40), pol(250, 14), pol(200, 11), pol(160, 11), pol(110, 14), pol(90, 40),
          pol(90, 85)], p1, 0.9, (0, (4, 2.5)))
    path([pol(180, 98), pol(180, 40), pol(170, 12), pol(10, 12), pol(0, 40), pol(0, 85)], p1, 0.9, (0, (4, 2.5)))
    path([pol(a, 63.0) for a in range(0, 361, 2)], "#2d6cc0", 0.9, (0, (4, 2.5)))
    path([pol(a, 97.75) for a in range(-80, 79, 2)], "#16884a", 0.8, (0, (4, 2.5)))
    path([pol(a, 97.75) for a in range(98, 281, 2)], "#16884a", 0.8, (0, (4, 2.5)))

    def path_tag(xy, n: str, col: str) -> None:
        ax.add_patch(Circle(xy, 3.2, fc=col, ec="white", lw=1.2, zorder=22))
        ax.text(xy[0], xy[1], n, fontsize=7.4, color="white", weight="bold", ha="center", va="center", zorder=23)

    path_tag(pol(270, 52), "I", p1)
    path_tag(pol(173, 26), "I", p1)
    path_tag(pol(228, 63), "II", "#2d6cc0")
    path_tag(pol(43, 63), "II", "#2d6cc0")
    path_tag(pol(228, 97.75), "III", "#16884a")
    path_tag(pol(318, 97.75), "III", "#16884a")

    # --- горячие точки (номер — в углу круга, куда свободнее)
    hot = [((270, 63), 9.0, "1", 45), ((0, 0), 16.0, "2", 45), ((0, 93), 9.0, "3", 140), ((46, 87), 10.0, "4", 160),
           ((112, 80), 9.0, "5", 45)]
    for (a, r), rad, n, corner in hot:
        x, y = pol(a, r)
        ax.add_patch(Circle((x, y), rad, fc=C["danger"], ec=C["danger"], lw=1.4, alpha=0.13, zorder=11))
        ax.add_patch(Circle((x, y), rad, fc="none", ec=C["danger"], lw=1.2, ls=(0, (2, 1.5)), zorder=11))
        dx, dy = pol(corner, rad)
        tx, ty = x + dx, y + dy
        ax.add_patch(Circle((tx, ty), 2.6, fc=C["danger"], ec="white", lw=1.0, zorder=22))
        ax.text(tx, ty, n, fontsize=7.4, color="white", weight="bold", ha="center", va="center", zorder=23)

    # --- где лежат ключи: ромб на месте, подпись — выноской, чтобы не закрывать комнату
    def key_mark(a: float, r: float, text: str, ta: float | None = None, tr: float | None = None) -> None:
        x, y = pol(a, r)
        ax.plot([x], [y], marker="D", ms=7.5, mfc="#f2c94c", mec="#5a4300", mew=0.9, zorder=17)
        tx, ty = pol(ta if ta is not None else a, tr if tr is not None else r)
        if ta is not None or tr is not None:
            ax.plot([x, tx], [y, ty], color="#8a6d12", lw=0.8, zorder=16.5)
        ax.text(tx, ty, text, fontsize=6.0, color="#4d3900", ha="center", va="center", zorder=21,
                weight="bold", bbox={"boxstyle": "round,pad=0.18", "fc": "#fff6cf", "ec": "#b38f1d", "lw": 0.6})

    key_mark(266.5, 95.5, "К1?", 262.5, 109.0)
    key_mark(20, 70.5, "К1?", 16.0, 65.6)
    key_mark(256, 93.5, "К2 К3 (К6)", 252.5, 109.0)
    key_mark(285, 93.5, "К4 К5 — сейф", 282.0, 109.0)
    key_mark(4.5, 96.5, "К5/К6 в общаке", -9.5, 110.5)
    # ключ от тайника — одно из трёх постоянных мест (решение владельца 2026-10-15)
    key_mark(237.0, 54.5, "К7?", 237.0, 61.5)
    key_mark(104.0, 93.8, "К7?", 104.0, 108.6)
    key_mark(340.5, 93.8, "К7?", 340.5, 108.6)

    # --- рубильник
    x, y = pol(33, 94.0)
    ax.text(x, y, "⚡", fontsize=13, color="#7a5a00", ha="center", va="center", zorder=18, weight="bold",
            bbox={"boxstyle": "circle,pad=0.2", "fc": "#ffd84d", "ec": "#7a5a00", "lw": 1.0})

    # --- места под сюжет — только пометка, решает владелец
    for name, (a, r) in (("Товары для дома", (156.5, 92.0)), ("вестибюль:\nлагерь", (-5.0, 87.6))):
        room = next(x for x in rooms if x.name == name)
        ax.add_patch(Polygon(room.poly(), closed=True, fc="none", ec="#7b3fa0", lw=1.6, ls=(0, (3, 2)), zorder=12))
        x, y = pol(a, r)
        ax.plot([x], [y], marker="o", ms=10, mfc="#7b3fa0", mec="white", mew=1.0, zorder=22)
        ax.text(x, y, "?", fontsize=7.4, color="white", weight="bold", ha="center", va="center", zorder=23)

    # --- подписи общих зон (ширина — в метрах)
    def zone(a: float, r: float, text: str, radial: bool = False, size: float = 6.2) -> None:
        x, y = pol(a, r)
        ax.text(x, y, text, fontsize=size, color="#6b6256", style="italic", ha="center", va="center", zorder=13,
                rotation=text_rot(a) if radial else text_rot(a - 90.0), linespacing=1.0)

    zone(150, 63.0, "кольцевая улица · 10 м")
    zone(330, 63.0, "кольцевая улица · 10 м")
    zone(120, 35.0, "галерея атриума · 10 м")
    zone(300, 35.0, "галерея атриума · 10 м")
    zone(160, 97.75, "служебный коридор · 3,5 м", size=5.4)
    zone(320, 97.75, "служебный коридор · 3,5 м", size=5.4)
    zone(273.4, 77.0, "главная аллея · 14 м", radial=True)
    zone(92.6, 76.0, "северная аллея — тупик у завала", radial=True, size=5.8)
    zone(186.0, 92.0, "проход к выходу", radial=True, size=5.4)
    zx, zy = pol(300, 24.5)
    ax.text(zx, zy, "АТРИУМ Ø60\nпод куполом", fontsize=7.6, color="#4d6676", weight="bold", ha="center",
            va="center", zorder=13)

    # --- стенды «вы здесь»
    stands = [(270, 88, True), (273, 61, True), (270, 42.5, True), (90, 42.5, True), (180, 92, True),
              (183, 61, True), (123, 61, False), (63, 61, True), (3, 61, True), (303, 61, False), (243, 61, True),
              (45, 97.2, True)]
    for a, r, ok in stands:
        x, y = pol(a, r)
        ax.plot([x], [y], marker="s", ms=7, mfc="#1f5fa8" if ok else "#8a8a8a", mec="white", mew=0.8, zorder=17)
        ax.text(x, y, "i", fontsize=6.2, color="white", ha="center", va="center", zorder=18, weight="bold",
                style="italic")

    # --- масштаб и север
    y0 = -lim + 6
    ax.plot([-lim + 4, -lim + 29], [y0, y0], color="black", lw=4, solid_capstyle="butt", zorder=30)
    ax.plot([-lim + 29, -lim + 54], [y0, y0], color="white", lw=4, solid_capstyle="butt", zorder=30)
    ax.plot([-lim + 4, -lim + 54], [y0, y0], color="black", lw=0.6, zorder=31)
    for xv, t in ((-lim + 4, "0"), (-lim + 29, "25"), (-lim + 54, "50 м")):
        ax.text(xv, y0 + 3.2, t, fontsize=7.5, ha="center", zorder=31)
    ax.annotate("", xy=(-lim + 8, lim - 3), xytext=(-lim + 8, lim - 17),
                arrowprops={"arrowstyle": "-|>", "lw": 2.2, "color": "black"}, zorder=31)
    ax.text(-lim + 8, lim - 21, "С", fontsize=12, weight="bold", ha="center", zorder=31)

    questions = "\n".join([
        "Решено владельцем 15.10.2026:",
        "• весь этаж проходим; какие магазины",
        "   закрыты — тасуется каждый рейд",
        "• ключ от тайника — одно из 3 мест (К7?)",
        "• рубильник у доков, генератор снаружи",
        "• раскладка — без изменений",
        "• восток — гарнизон мародёров, как рынок",
        "• «Товары для дома» — дом жильцов",
    ])
    ax.text(lim - 1.5, lim - 1.5, questions, fontsize=7.8, ha="right", va="top", color=C["text"], zorder=31,
            linespacing=1.25, multialignment="left",
            bbox={"boxstyle": "round,pad=0.5", "fc": "#fbf9f3", "ec": C["green"], "lw": 1.0})
    legend(fig, rooms)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, facecolor=fig.get_facecolor())
    print("saved", OUT)
    report(rooms)


def sector_area(rooms: list[Room], sec: str, kinds: tuple[str, ...]) -> float:
    return sum(r.m2() for r in rooms if r.sec == sec and r.kind in kinds)


def anchor_total(rooms: list[Room], names: tuple[str, ...]) -> float:
    return sum(r.m2() for r in rooms if r.name in names)


def legend(fig, rooms: list[Room]) -> None:
    lx = fig.add_axes([0.665, 0.01, 0.33, 0.975])
    lx.axis("off")
    lx.set_xlim(0, 1)
    lx.set_ylim(0, 1)
    y = 0.992

    def line(text: str, size: float = 8.4, weight: str = "normal", color: str = C["text"], x: float = 0.0,
             gap: float = 0.0) -> None:
        nonlocal y
        lx.text(x, y, text, fontsize=size, weight=weight, color=color, va="top", ha="left")
        y -= 0.0036 + size * 0.00114 + gap

    line("ТЦ «РИНГ» — план 1-го этажа", 16, "bold")
    line("Ø200 м · бумажный план · раскладка принята владельцем 15.10.2026 · в игре ничего не построено", 8.6)
    line("Север вверху. Сетка колонн 0,6×0,6: по радиусу через 9–10 м, по дуге 7–10 м.", 8.2, color="#4a463f")
    line("", 4)

    supermarket = anchor_total(rooms, ("Супермаркет «Корзина»", "Холодильные камеры", "Приёмка товара", "Щитовая"))
    electronics = anchor_total(rooms, ("Электроника «Вольт»", "Склад электроники", "Сервис"))
    line("Секторы: свой цвет, буква и тема (как у владельца в концепте)", 10.5, "bold")
    themes = {
        "A": "главный вход, аптека, банк, ювелирный, ломбард, пост охраны",
        "B": f"«Модный дом» ≈{round(anchor_total(rooms, ('«Модный дом»',)) / 10) * 10:.0f} м², обувь, часы, косметика",
        "C": "«Дом и ремонт» (инструмент), хозтовары, тайник за ключом",
        "D": "спорт и туризм, оружейный «Тайга», медпункт; северный вход завален",
        "E": f"супермаркет — якорь ≈{round(supermarket / 100) * 100:.0f} м², доки, щитовая с рубильником",
        "F": f"электроника «Вольт» — якорь ≈{round(electronics / 100) * 100:.0f} м², склад за ключом",
    }
    for letter, (b, title, col) in SECTORS.items():
        badge(lx, y, letter, col)
        lx.text(0.032, y, title, fontsize=8.4, weight="bold", va="top", color=C["text"])
        lx.text(0.175, y, themes[letter], fontsize=8.2, va="top", color=C["text"])
        y -= 0.0150
    line("", 4)

    line("Витрины и входы — пример одного рейда", 10.5, "bold")
    line("Каждый рейд тасуется заново. Постоянны: сгоревшие, «Тайга», двери на ключ, супермаркет открыт.",
         8.0, color="#4a463f")
    fr = [("O", "открыт — витрина разбита, двери настежь (разграблен)"),
          ("H", "роллета поднята наполовину — пролезть только ползком"),
          ("C", "роллета опущена — вход сзади: с улицы или из служебного коридора"),
          ("P", "электророллета — поднимается только при питании + ключ-карта"),
          ("X", "сгорел или завален — видно сквозь решётку, не пройти"),
          ("K", "дверь на ключ (К1…К7 — откуда ключи, ниже)")]
    for st, text in fr:
        s = FRONT[st]
        lx.plot([0.0, 0.05], [y - 0.006, y - 0.006], color=s["color"], lw=s["lw"], ls=s["ls"],
                solid_capstyle="butt")
        lx.text(0.062, y, text, fontsize=8.2, va="top", color=C["text"])
        y -= 0.0137
    line("", 4)

    line("Обозначения", 10.5, "bold")
    sym_y = y

    def sym(draw, text: str) -> None:
        nonlocal y
        draw(y - 0.006)
        lx.text(0.062, y, text, fontsize=8.2, va="top", color=C["text"])
        y -= 0.0137

    sym(lambda yy: lx.plot([0.025], [yy], marker="s", ms=4, color=C["col"]), "колонна")
    sym(lambda yy: lx.add_patch(Rectangle((0.005, yy - 0.005), 0.04, 0.01, fc=C["stair"], ec=C["wall"],
                                          hatch="----", lw=0.6)),
        "лестничная клетка «Л» — 14 шт.; двери наверх заварены, выход наружу — через проход")
    sym(lambda yy: lx.add_patch(Rectangle((0.005, yy - 0.005), 0.04, 0.01, fc=C["wc"], ec=C["wall"], lw=0.6)),
        "санузлы в 6 техядрах: М, Ж, для маломобильных; рядом лифт")
    sym(lambda yy: lx.plot([0.0, 0.05], [yy, yy], color=C["fire"], lw=2.2),
        "противопожарная стена на границе секторов")
    sym(lambda yy: (lx.plot([0.0, 0.022], [yy, yy], color="#d62828", lw=4.0),
                    lx.plot([0.028, 0.05], [yy, yy], color="#d62828", lw=3.6, ls=(0, (2, 1.2)))),
        "противопожарная штора на улице: опущена / наполовину (ползком)")
    sym(lambda yy: lx.plot([0.0, 0.05], [yy, yy], color="#5b5348", lw=1.6),
        "двери служебного коридора — через каждые ≤ 60 м (норма)")
    sym(lambda yy: lx.plot([0.025], [yy], marker="*", ms=11, mfc=C["gold"], mec="#5a4300", mew=0.7),
        "дорогая комната (лучшая добыча, обычно за ключом или роллетой)")
    sym(lambda yy: lx.plot([0.025], [yy], marker="D", ms=7, mfc="#f2c94c", mec="#5a4300", mew=0.9),
        "где лежит ключ: К1? — одно из двух мест, К7? — одно из трёх")
    sym(lambda yy: lx.text(0.025, yy, "⚡", fontsize=10, ha="center", va="center", color="#7a5a00",
                           bbox={"boxstyle": "circle,pad=0.15", "fc": "#ffd84d", "ec": "#7a5a00", "lw": 0.8}),
        "рубильник этажа (щитовая у доков)")
    sym(lambda yy: (lx.plot([0.018], [yy], marker="s", ms=7, mfc="#1f5fa8", mec="white"),
                    lx.plot([0.038], [yy], marker="s", ms=7, mfc="#8a8a8a", mec="white")),
        "стенд-схема «вы здесь» / разбит")
    sym(lambda yy: (lx.plot([0.0, 0.05], [yy, yy], color="#7b3fa0", lw=1.6, ls=(0, (3, 2))),
                    lx.plot([0.025], [yy], marker="o", ms=9, mfc="#7b3fa0", mec="white")),
        "«?» — кто здесь живёт: восток — мародёры, C — жильцы")
    sym(lambda yy: (lx.plot([0.012], [yy], marker="s", ms=8, mfc="#1e9e4a", mec="white"),
                    lx.plot([0.03], [yy], marker=">", ms=8, mfc="#2d6cc0", mec="white"),
                    lx.plot([0.046], [yy], marker="X", ms=8, mfc="#222", mec="white")),
        "вход ↕ / выход только изнутри / заварен или завален")
    line("", 4)

    line("Три пути через этаж", 10.5, "bold")
    for col, n, text in (("#d6336c", "I", "Через атриум — быстро и открыто: прострел 60–80 м, укрытия — эскалаторы,\n"
                                          "фонтан, кадки, обломки купола. Юг ↔ север, запад ↔ восток."),
                         ("#2d6cc0", "II", "Кольцевая улица — между витринами: прямой обзор по дуге не дальше ~70 м,\n"
                                           "киоски — укрытия. Штора C|D опущена — обход галереей или служебкой."),
                         ("#16884a", "III", "Служебный коридор вдоль фасада — тесно, темно, двери, ключи; видно ≤ 50 м.\n"
                                            "Петли нет: на севере завал. Из него — двери в подсобки магазинов.")):
        badge(lx, y, n, col, 7.0)
        lx.text(0.032, y, text, fontsize=8.2, va="top", color=C["text"], linespacing=1.15)
        y -= 0.0262
    line("", 3)

    line("Горячие точки", 10.5, "bold")
    for n, text in (("1", "главный перекрёсток — аллея × улица: через него идут все с юга"),
                    ("2", "атриум — центр, видно со всех сторон галереи"),
                    ("3", "восточный вестибюль — гарнизон мародёров за баррикадой, занят каждый рейд"),
                    ("4", "супермаркет и приёмка у доков — много добычи, два входа снаружи"),
                    ("5", "«Тайга» после включения света — роллета гремит, слышно на пол-этажа")):
        badge(lx, y, n, C["danger"])
        lx.text(0.032, y, text, fontsize=8.2, va="top", color=C["text"])
        y -= 0.0137
    line("", 3)

    line("Ключи и рубильник (цепочка)", 10.5, "bold")
    for text in ("К1 «Пост охраны» — на теле охранника в главном вестибюле или у касс супермаркета",
                 "Пост охраны → К2 «Служебный» (двери коридора, медпункт) и К3 «Администрация»;",
                 "    иногда — К6 ключ-карта «Тайги»",
                 "Администрация → сейф управляющего: К4 «Хранилище банка», К5 «Склад электроники»",
                 "Общак лагеря на востоке (ящик под охраной) — может быть К5 или К6",
                 "К7 «Тайник» — одно из трёх мест: «Ключи, обувь» (B), склад туризма (D),",
                 "    сервис «Вольта» (F); место выбирается в начале рейда",
                 "Питание: генератор в техкомплексе снаружи → рубильник в щитовой у доков →",
                 "    свет на этаже, электророллета «Тайги», ворота доков (выход «грузовик»)"):
        line(text, 8.2)
    line("", 3)

    line("Нормы (опора — СП 1.13130.2020, docs/building_standards.md)", 10.5, "bold")
    for text in ("до выхода из торгового зала ≤ 50 м (зал до 5 тыс. м³), ≤ 80 м (больше 10 тыс. м³) — табл. 11;",
                 "    у нас самые глубокие магазины — 28 м, якоря — по 2–3 выхода",
                 "этаж больше чем на 1000 человек — не меньше 4 выходов; у нас 12 наружу + 14 лестниц",
                 "коридор длиннее 60 м — делить дверями: служебный коридор разбит дверями",
                 "двери из зала ≥ 1,2 м; главные проходы в залах ≥ 2,5 м (больше 400 м²)",
                 "стены: фасад 0,5 · противопожарная 0,3 · несущая 0,3 · перегородка 0,15"):
        line(text, 8.0, color="#3d3a35")
    line("", 3)

    # разрез-полоса по радиусу
    line("Разрез по радиусу (от центра к фасаду), м", 10.5, "bold")
    bands = [(0, 30, C["atrium"], "атриум"), (30, 40, "#efe9dc", "галерея"), (40, 58, tint("#c3a21f", 0.75), "внутр. магазины"),
             (58, 68, "#efe9dc", "улица"), (68, 96, tint("#c3a21f", 0.6), "внешние магазины и якоря"),
             (96, 99.5, C["svc"], ""), (99.5, 100, "#2f2a24", "")]
    x0, w = 0.0, 0.95
    for r0, r1, col, text in bands:
        lx.add_patch(Rectangle((x0 + w * r0 / 100, y - 0.022), w * (r1 - r0) / 100, 0.016, fc=col, ec=C["wall"],
                               lw=0.5))
        if text:
            lx.text(x0 + w * (r0 + r1) / 200, y - 0.014, text, fontsize=7.2, ha="center", va="center")
    for rv in (0, 30, 40, 58, 68, 96, 100):
        lx.text(x0 + w * rv / 100, y - 0.026, str(rv), fontsize=7, ha="center", va="top")
    lx.text(x0 + w * 0.978, y - 0.002, "служебный\nкоридор", fontsize=6.4, ha="center", va="bottom")


def badge(lx, y: float, text: str, col: str, size: float = 7.6) -> None:
    """Цветной кружок с буквой или номером в легенде (маркером — не растягивается по высокой оси)."""
    lx.plot([0.012], [y - 0.0058], marker="o", ms=13, mfc=col, mec="white", mew=1.0)
    lx.text(0.012, y - 0.0058, text, fontsize=size, color="white", weight="bold", ha="center", va="center")


def report(rooms: list[Room]) -> None:
    """Цифры для описания: площади по секторам и по видам помещений."""
    trade = sum(r.m2() for r in rooms if r.kind in ("shop", "anchor"))
    print(f"торговые залы: {trade:.0f} м², магазинов {sum(1 for r in rooms if r.kind in ('shop', 'anchor'))}")
    for letter in SECTORS:
        print(letter, f"залы {sector_area(rooms, letter, ('shop', 'anchor')):.0f}",
              f"подсобки/служебные {sector_area(rooms, letter, ('back', 'service', 'hidden')):.0f}")
    for r in rooms:
        if r.kind in ("shop", "anchor", "service", "back", "hidden"):
            print(f"  {r.sec} {r.name:24s} {r.m2():7.0f}")
    total = math.pi * R_FAC ** 2
    print(f"этаж всего {total:.0f} м², атриум {math.pi * R_ATR ** 2:.0f}")


if __name__ == "__main__":
    main()
