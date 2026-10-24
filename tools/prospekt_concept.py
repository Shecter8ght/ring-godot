# -*- coding: utf-8 -*-
"""Схема новой маленькой карты «Проспект» — городская улица за кордоном (предложение, 2026-10-24).

Не уровень и не данные игры — картинка для согласования с владельцем. Описание —
docs/design/prospekt_map.md. Координаты: X — восток (= x игры), Y — север (= −z игры), ось проспекта y = 0,
кордон слева (запад).

    python -X utf8 tools/prospekt_concept.py  →  docs/design/prospekt_concept.png
"""
from __future__ import annotations

import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "design" / "prospekt_concept.png"

C = {
    "bg": "#ebe7db", "outside": "#d3cfc1", "ground": "#d9d6c7", "asphalt": "#8d9093", "asphalt_edge": "#5f6264",
    "walk": "#c9c3b2", "lawn": "#b9c9a0", "tower": "#7d7a8a", "tower_edge": "#3f3d49", "open": "#c67b5a",
    "open_edge": "#5a3523", "closed": "#a39f96", "closed_edge": "#55524c", "under": "#5b7fa6", "fence": "#4a4640",
    "text": "#2b2824", "spawn": "#2d6cc0", "extract": "#1e9e4a", "cond": "#d68a00", "danger": "#c0392b",
    "car": "#4f5358", "tree": "#6f9a5a", "route": "#b0239a", "cordon": "#8c2b2b",
}


def label(ax, xy, text: str, size: float = 7.5, color: str | None = None, weight: str = "normal",
          ha: str = "center", rot: float = 0.0, z: float = 30) -> None:
    ax.text(xy[0], xy[1], text, fontsize=size, color=color or C["text"], weight=weight, ha=ha, va="center",
            rotation=rot, zorder=z, linespacing=1.15)


def num(ax, xy, n: int) -> None:
    ax.add_patch(Circle(xy, 4.2, fc="#2b2824", ec="white", lw=1.0, zorder=40))
    ax.text(xy[0], xy[1], str(n), fontsize=7, color="white", weight="bold", ha="center", va="center", zorder=41)


def rect(ax, x0: float, y0: float, w: float, h: float, fc: str, ec: str, z: float = 10, lw: float = 0.9,
         hatch: str | None = None, alpha: float = 1.0, ls: str = "-") -> None:
    ax.add_patch(Rectangle((x0, y0), w, h, fc=fc, ec=ec, lw=lw, zorder=z, hatch=hatch, alpha=alpha, ls=ls))


def car(ax, x: float, y: float, rot: float = 0.0, color: str | None = None, w: float = 4.4, h: float = 1.9) -> None:
    import matplotlib.transforms as T
    r = Rectangle((-w / 2, -h / 2), w, h, fc=color or C["car"], ec="#23262a", lw=0.5, zorder=22)
    r.set_transform(T.Affine2D().rotate_deg(rot).translate(x, y) + ax.transData)
    ax.add_patch(r)


def tree(ax, x: float, y: float, r: float = 2.6) -> None:
    ax.add_patch(Circle((x, y), r, fc=C["tree"], ec="#44633a", lw=0.5, zorder=21, alpha=0.9))


def main() -> None:
    rng = random.Random(7)
    fig, ax = plt.subplots(figsize=(15.5, 11.5), dpi=150)
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["outside"])
    ax.set_aspect("equal")
    ax.set_xlim(-222, 140)
    ax.set_ylim(-125, 112)

    # --- игровая область (внутри — земля, снаружи — город-декорация)
    bx0, bx1, by0, by1 = -120, 112, -112, 100
    rect(ax, bx0, by0, bx1 - bx0, by1 - by0, C["ground"], "#7a7466", z=1, lw=1.4, ls="--")

    # --- проспект: проезжая часть 2+2, разделительная клумба, тротуары
    rect(ax, -120, -8.5, 232, 17, C["asphalt"], C["asphalt_edge"], z=4)
    rect(ax, -120, -1.5, 232, 3, C["lawn"], "#7d8f66", z=5)                     # разделительная полоса
    rect(ax, -120, 8.5, 232, 5.5, C["walk"], "#9a9484", z=4)                   # тротуар север
    rect(ax, -120, -14, 232, 5.5, C["walk"], "#9a9484", z=4)                   # тротуар юг
    for x in range(-110, 100, 30):                                              # фонари на разделительной
        ax.add_patch(Circle((x, 0), 0.9, fc="#f0d070", ec="#6a5a20", lw=0.5, zorder=26))
    for x in range(-114, 100, 4):                                               # разметка
        ax.plot([x, x + 2], [5, 5], color="#e6e3d8", lw=0.7, zorder=6)
        ax.plot([x, x + 2], [-5, -5], color="#e6e3d8", lw=0.7, zorder=6)
    for x in (-80, 62):                                                         # зебры и светофоры
        for i in range(8):
            rect(ax, x - 2.5, -8.5 + i * 2.2, 5, 1.1, "#e6e3d8", "#e6e3d8", z=7)
        ax.add_patch(Circle((x - 4, 9.5), 0.8, fc="#c0392b", ec="#222", lw=0.4, zorder=27))
        ax.add_patch(Circle((x + 4, -9.5), 0.8, fc="#c0392b", ec="#222", lw=0.4, zorder=27))
    # перекрёсток на востоке с пробкой — граница карты
    rect(ax, 100, -112, 9, 212, C["asphalt"], C["asphalt_edge"], z=4)
    for y in range(-100, 96, 7):
        car(ax, 104.5 + rng.uniform(-1.2, 1.2), y, rot=90 + rng.uniform(-8, 8), color="#5a5f66")
    car(ax, 96, 3, rot=35, color="#9b7a2c", w=12, h=2.6)                       # автобус на боку на перекрёстке
    label(ax, (104.5, -108), "пробка\nграница", 6.5, rot=90)

    # --- кордон на западе: забор из плит через проспект, блоки, КПП, вышка
    rect(ax, -121, -16, 2.2, 32, C["cordon"], C["cordon"], z=15)
    for i in range(5):
        rect(ax, -112 + i * 4.5, -8 + (i % 2) * 7, 2.4, 2.4, "#a8a49a", "#3a3835", z=16)
    rect(ax, -134, -22, 10, 8, "#b8a46a", "#4a4020", z=15)
    label(ax, (-129, -18), "КПП ЧВК", 6.5)
    rect(ax, -133, 14, 5, 5, "#b8a46a", "#4a4020", z=15)
    label(ax, (-130.5, 21), "вышка", 6)
    label(ax, (-165, -38), "город\nза кордоном\n(декорация,\nживой)", 7, color="#5a5650")
    ax.add_patch(Polygon([(-150, 40), (-124, 40), (-124, 100), (-150, 100)], fc="#c4c0b2", ec="none", zorder=2))
    ax.add_patch(Polygon([(-150, -112), (-124, -112), (-124, -40), (-150, -40)], fc="#c4c0b2", ec="none", zorder=2))
    for (x, y, w, h) in [(-148, 50, 14, 20), (-148, 76, 12, 18), (-147, -95, 13, 22), (-148, -66, 11, 16),
                         (120, 20, 16, 30), (118, 60, 18, 24), (122, -60, 14, 28), (118, -100, 20, 22)]:
        rect(ax, x, y, w, h, C["tower"], C["tower_edge"], z=3, hatch="///", alpha=0.6)
    label(ax, (128, 108), "высотки за границей — декорация", 6.5, color="#5a5650")

    # --- север: ЖК «Панорама» корпус 1 (17 эт.), первые этажи — стрит-ритейл
    rect(ax, -100, 14, 60, 22, C["tower"], C["tower_edge"], z=12, lw=1.2)
    label(ax, (-70, 31), "ЖК «Панорама», корпус 1 — 17 этажей (вход со двора, 2–3 этажи открыты)", 6.3, color="white")
    for (x0, w, name, opn) in [(-100, 16, "кофейня\n«Зерно»", True), (-84, 10, "цветы", True),
                               (-74, 14, "аптека", True), (-60, 20, "одежда\n«Modus»", True)]:
        rect(ax, x0, 14, w, 9, C["open"] if opn else C["closed"], C["open_edge"], z=13)
        label(ax, (x0 + w / 2, 18.5), name, 6.3, color="white")
    # проезд во двор между корпусами, шлагбаум, пандус в паркинг
    rect(ax, -40, 14, 30, 26, C["asphalt"], C["asphalt_edge"], z=11)
    ax.plot([-40, -10], [14.5, 14.5], color="#d9c23a", lw=2.2, zorder=14)
    label(ax, (-25, 11.5), "шлагбаум", 6)
    rect(ax, -37, 20, 7, 18, "#6d7378", "#2b2f33", z=12)
    label(ax, (-33.5, 29), "пандус\nв паркинг −1", 6, color="white", rot=90)
    # корпус 2 — закрыт, первые этажи: пекарня открыта, остальное витрины
    rect(ax, -10, 14, 60, 22, C["tower"], C["tower_edge"], z=12, lw=1.2, hatch="///", alpha=0.85)
    label(ax, (20, 31), "ЖК «Панорама», корпус 2 — 25 этажей, закрыт (только фасад)", 6.3, color="white")
    for (x0, w, name, opn) in [(-10, 14, "пекарня", True), (4, 12, "салон\nсвязи", False), (16, 14, "ломбард", False),
                               (30, 20, "банк\n(банкомат)", False)]:
        rect(ax, x0, 14, w, 9, C["open"] if opn else C["closed"], C["open_edge"] if opn else C["closed_edge"], z=13)
        label(ax, (x0 + w / 2, 18.5), name, 6.3, color="white" if opn else C["text"])
    # двор ЖК на плите паркинга
    rect(ax, -100, 36, 150, 44, C["walk"], "#8f8a7a", z=10)
    rect(ax, -100, 80, 150, 1.2, C["fence"], C["fence"], z=14)
    rect(ax, -24, 79.5, 8, 2.2, "#d9c23a", "#4a4020", z=15)
    label(ax, (-20, 84.5), "ворота", 6)
    rect(ax, -62, 50, 24, 16, C["lawn"], "#7d8f66", z=11)
    label(ax, (-50, 58), "детская\nплощадка", 6.3)
    rect(ax, 20, 44, 6, 5, "#b7b2a4", "#4a4640", z=13)
    label(ax, (23, 52), "КТП", 6)
    rect(ax, 32, 62, 10, 8, "#b7b2a4", "#4a4640", z=13)
    label(ax, (37, 73), "мусорная\nплощадка", 6)
    for i in range(10):
        car(ax, -90 + i * 7.2, 72, rot=90, color="#6a6f75")
    for i in range(6):
        car(ax, -10 + i * 7.2, 72, rot=90, color="#6a6f75")
    label(ax, (-70, 77), "парковка жильцов", 6.3)
    for i in range(4):
        tree(ax, -90 + i * 20, 42, 3)
    tree(ax, 0, 60, 3.2)
    tree(ax, 12, 70, 2.8)
    # вход в корпус 1 со двора
    rect(ax, -74, 36, 8, 2.5, "#f0d070", "#6a5a20", z=15)
    label(ax, (-70, 40.5), "вход в корпус 1 (холл, лестница)", 6)
    # подземный паркинг −1 (пунктир под двором)
    rect(ax, -92, 38, 128, 38, "none", C["under"], z=18, lw=1.3, ls="--")
    label(ax, (-6, 48), "подземный паркинг −1 (под двором): темно, колонны, машины;\nвыходы — пандус, лестница в холл корпуса 1, лестница во двор", 6.3,
          color=C["under"])
    # сквер на востоке
    rect(ax, 56, 14, 44, 50, C["lawn"], "#7d8f66", z=10)
    ax.add_patch(Circle((78, 40), 7, fc="#9fbbd1", ec="#5b7fa6", lw=0.8, zorder=12))
    label(ax, (78, 40), "фонтан\n(сухой)", 6)
    for (x, y) in [(62, 22), (94, 22), (62, 58), (94, 58), (78, 20), (78, 60)]:
        tree(ax, x, y, 3.4)
    rect(ax, 86, 50, 9, 5, "#c79f5a", "#5a3a10", z=13)
    label(ax, (90.5, 58), "фудтрак", 6)
    label(ax, (78, 27), "сквер: лавки, клумбы, урны", 6.3)

    # --- юг: бизнес-центр (закрыт), остановка и ларьки, супермаркет с парковкой и разгрузкой, дом 7
    rect(ax, -116, -58, 44, 44, C["closed"], C["closed_edge"], z=12, hatch="///", alpha=0.9)
    label(ax, (-94, -36), "бизнес-центр\n«Меридиан», 6 эт.\nзакрыт", 6.5)
    rect(ax, -116, -23, 44, 9, C["closed"], C["closed_edge"], z=13)
    label(ax, (-94, -18.5), "банк · страховая · «Бургерная» — витрины", 6)
    rect(ax, -104, -13.5, 9, 2.5, "#7fb0d8", "#2f5f86", z=15)
    label(ax, (-99.5, -10.5), "остановка", 6)
    for (x, name) in [(-116, "шаурма"), (-111, "пресса")]:
        rect(ax, x, -13.5, 4, 3, "#c79f5a", "#5a3a10", z=15)
    label(ax, (-113, -16.5), "ларьки", 6)
    # супермаркет
    rect(ax, -70, -56, 100, 42, C["walk"], "#9a9484", z=10)
    label(ax, (-20, -18), "парковка супермаркета: тележки, машины, клумбы, фонари", 6.3)
    for r in range(3):
        for i in range(9):
            if rng.random() < 0.55:
                car(ax, -62 + i * 8 + r * 2, -24 - r * 11, rot=0, color="#6a6f75")
    rect(ax, -60, -96, 80, 40, C["open"], C["open_edge"], z=12, lw=1.2)
    label(ax, (-20, -70), "супермаркет «Ярус» — торговый зал: ряды стеллажей, кассы,\nхолодильники; за залом — склад с высокими стеллажами (темно)", 6.5, color="white")
    rect(ax, -26, -58, 12, 2.5, "#f0d070", "#6a5a20", z=15)
    label(ax, (-20, -53), "вход", 6)
    rect(ax, -60, -96, 80, 9, "#8a4d33", "#3d1f12", z=13)
    label(ax, (-20, -91.5), "склад", 6.3, color="white")
    rect(ax, -60, -106, 80, 10, C["asphalt"], C["asphalt_edge"], z=11)
    label(ax, (-20, -101), "разгрузочный двор: рампа, фура, баки, забор", 6.3)
    car(ax, -45, -100, rot=0, color="#b8b4a8", w=14, h=2.6)
    rect(ax, -60, -108, 80, 1.2, C["fence"], C["fence"], z=14)
    rect(ax, 20, -106, 1.2, 50, C["fence"], C["fence"], z=14)
    rect(ax, 19.5, -100, 2.2, 6, "#d9c23a", "#4a4020", z=15)
    label(ax, (26, -97), "калитка", 6)
    # проезд между супермаркетом и домом 7
    rect(ax, 22, -112, 10, 98, C["asphalt"], C["asphalt_edge"], z=4)
    label(ax, (27, -60), "служебный проезд", 6, rot=90)
    # дом 7
    rect(ax, 34, -70, 62, 18, C["closed"], C["closed_edge"], z=12, hatch="///", alpha=0.9)
    label(ax, (65, -61), "дом 7 — 9 эт., панельный, закрыт", 6.5)
    rect(ax, 34, -23, 62, 9, C["closed"], C["closed_edge"], z=13)
    rect(ax, 34, -23, 26, 9, C["open"], C["open_edge"], z=13)
    label(ax, (47, -18.5), "минимаркет\n(открыт)", 6.3, color="white")
    label(ax, (78, -18.5), "«Студия ногтей» · бар — витрины", 6)
    rect(ax, 34, -52, 62, 29, C["walk"], "#8f8a7a", z=10)
    label(ax, (65, -40), "двор дома 7: гаражи-ракушки, клумбы, сушилки", 6.3)
    for i in range(7):
        rect(ax, 40 + i * 7.5, -50, 5.5, 3.2, "#9c9a8f", "#4a4640", z=13)
    rect(ax, 36, -13.5, 9, 2.5, "#7fb0d8", "#2f5f86", z=15)
    label(ax, (40.5, -10.5), "остановка", 6)
    rect(ax, 50, -13.5, 4, 3, "#c79f5a", "#5a3a10", z=15)
    rect(ax, 55, -13.5, 4, 3, "#c79f5a", "#5a3a10", z=15)
    label(ax, (54, -16.5), "цветы · кофе", 6)

    # --- подземный переход под проспектом
    rect(ax, -48, -11, 6, 22, "none", C["under"], z=18, lw=1.3, ls="--")
    rect(ax, -60, -3.5, 30, 7, "none", C["under"], z=18, lw=1.0, ls=":")
    label(ax, (-45, 0), "подземный\nпереход", 5.8, color=C["under"])
    rect(ax, -48, 11, 6, 2.5, "#7fb0d8", "#2f5f86", z=15)
    rect(ax, -48, -13.5, 6, 2.5, "#7fb0d8", "#2f5f86", z=15)

    # --- проспект: машины, деревья, повреждения
    for (x, y, rot, col) in [(-95, 6.5, 0, "#6a6f75"), (-66, -6.5, 0, "#6a6f75"), (-52, 6.5, 0, "#6a6f75"),
                             (-30, -6.5, 8, "#3a2a22"), (-18, 6.5, 0, "#6a6f75"), (2, -6.5, 0, "#6a6f75"),
                             (18, 6.5, -5, "#6a6f75"), (48, 6.5, 0, "#6a6f75"), (70, -6.5, 0, "#6a6f75"),
                             (84, 3, 20, "#8a8070")]:
        car(ax, x, y, rot, col)
    car(ax, 32, -3.5, rot=55, color="#b8b4a8", w=6, h=2.3)                 # фургон доставки, поперёк
    label(ax, (-30, -4), "сгоревшая", 5.5, color="#eee")
    label(ax, (32, -3.5), "фургон", 5.5)
    for x in range(-108, 100, 14):
        tree(ax, x, 12, 2.2)
        tree(ax, x + 7, -12, 2.2)
    for (x, y, t) in [(6, 10, "разбитые витрины"), (-6, -10, "упавшая вывеска"), (60, 10, "обрушенный козырёк"),
                      (-68, -10, "бордюр, мусор, бурьян")]:
        label(ax, (x, y + (2.5 if y > 0 else -2.5)), t, 5.5, color=C["danger"])
    # провода над проспектом
    for x in range(-100, 100, 40):
        ax.plot([x, x], [-13, 13], color="#3a3835", lw=0.6, ls=(0, (1, 2)), zorder=8)

    # --- появление и выходы
    def mark(xy, kind: str, text: str, at, ha: str = "center") -> None:
        if kind == "spawn":
            ax.add_patch(Circle(xy, 3.2, fc=C["spawn"], ec="white", lw=1.0, zorder=45))
        else:
            ax.add_patch(Polygon([(xy[0], xy[1] + 4), (xy[0] - 3.5, xy[1] - 2.5), (xy[0] + 3.5, xy[1] - 2.5)],
                                 fc=C["extract"] if kind == "extract" else C["cond"], ec="white", lw=1.0, zorder=45))
        label(ax, at, text, 6.3, color=C["spawn"] if kind == "spawn" else
              (C["extract"] if kind == "extract" else C["cond"]), weight="bold", ha=ha)

    mark((-104, 0), "spawn", "старт пролога\n(без оружия)", (-107, 6.5))
    mark((-60, 92), "spawn", "появление «Дворы ЖК»", (-60, 97.5))
    mark((27, -108), "spawn", "появление «Проезд»", (33, -108), "left")
    mark((78, 68), "spawn", "появление «Сквер»", (78, 73.5))
    mark((-20, 86), "extract", "выход «Дворами к насыпи»", (-20, 93))
    mark((27, -100), "extract", "выход «Служебный проезд»", (33, -100), "left")
    mark((-33.5, 42), "cond", "выход «Паркинг −1, пандус» — условный", (-33.5, 37))

    # --- маршрут пролога
    chains = [[(-104, 0), (-100, 9), (-92, 12), (-92, 17)],
              [(-88, 17), (-88, 10), (-60, 10), (-45, 9), (-45, -11), (-30, -16), (-20, -50),
               (-20, -75), (-50, -88), (-50, -100), (5, -100), (20, -97), (27, -100)]]
    for pts in chains:
        for a, b in zip(pts[:-1], pts[1:]):
            ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=9, color=C["route"], lw=1.6,
                                         zorder=50, ls="--"))
    label(ax, (-45, -32), "маршрут\nпролога", 6.5, color=C["route"], weight="bold")
    for (xy, n) in [((-94, -4), 1), ((-38, 4), 2), ((-13, -62), 3), ((-55, -92), 4), ((5, -104), 5)]:
        ax.add_patch(Circle(xy, 3.6, fc=C["route"], ec="white", lw=1.0, zorder=52))
        ax.text(xy[0], xy[1], str(n), fontsize=6.5, color="white", weight="bold", ha="center", va="center", zorder=53)

    # --- номера мест
    places = [((-118, 11), 1), ((-96, 26), 2), ((-66, 26), 3), ((-14, 22), 4), ((-30, 76), 5), ((-52, 14), 6),
              ((-94, -60), 7), ((-62, -22), 8), ((-20, -84), 9), ((-20, -110), 10), ((47, -25), 11), ((65, -54), 12),
              ((66, 32), 13), ((100, -108), 14)]
    for (xy, n) in places:
        num(ax, xy, n)

    # --- легенда и заголовок
    ax.set_xticks(range(-120, 121, 20))
    ax.set_yticks(range(-120, 101, 20))
    ax.tick_params(labelsize=6, colors="#5a5650")
    ax.grid(color="#bdb8a8", lw=0.3, alpha=0.6, zorder=0)
    ax.set_title("Карта «Проспект» — городская улица за кордоном (предложение 2026-10-24, север вверху, метры)",
                 fontsize=11, color=C["text"], pad=8)
    legend = [
        ("1 кордон: плиты, блоки, КПП ЧВК, вышка — назад нельзя", C["cordon"]),
        ("2 кофейня «Зерно» — закладка пролога (подсобка)", C["open"]),
        ("3 первые этажи корпуса 1: цветы, аптека, одежда — открыты", C["open"]),
        ("4 проезд во двор ЖК: шлагбаум, пандус в паркинг −1", C["asphalt"]),
        ("5 двор ЖК на плите: площадка, парковка, КТП; холл и 2–3 этажи корпуса 1", C["walk"]),
        ("6 подземный переход с ларьками — темно", C["under"]),
        ("7 бизнес-центр — закрыт, витрины, остановка, ларьки", C["closed"]),
        ("8 парковка супермаркета — открытое место с укрытиями", C["walk"]),
        ("9 супермаркет «Ярус»: зал, кассы, склад — главный CQB", C["open"]),
        ("10 разгрузочный двор: рампа, фура, калитка в проезд", C["asphalt"]),
        ("11 минимаркет дома 7 — открыт; дом закрыт", C["open"]),
        ("12 двор дома 7: ракушки, мусорка, сушилки", C["walk"]),
        ("13 сквер: сухой фонтан, лавки, фудтрак", C["lawn"]),
        ("14 перекрёсток с пробкой — граница; автобус на боку", C["asphalt_edge"]),
    ]
    for i, (t, col) in enumerate(legend):
        y = 104 - i * 6.2
        rect(ax, -220, y - 2, 4, 4, col, "#3a3835", z=60)
        ax.text(-214, y, t, fontsize=6.2, color=C["text"], va="center", zorder=60)
    ax.text(-220, 8, "штриховка — закрытые здания (только фасад)\nпунктир синий — под землёй\n"
                     "● синий — появление, ▲ зелёный — выход,\n▲ оранжевый — условный\n"
                     "пунктир лиловый — маршрут пролога,\n1–5 — его сцены\n\n"
                     "игровая область ≈ 232 × 212 м (4,9 га);\nпроспект 2+2 с разделительной клумбой,\n"
                     "тротуары 5,5 м, деревья в решётках, фонари,\nпровода между опорами, парковочные карманы",
            fontsize=6.2, color=C["text"], va="top", zorder=60)

    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, facecolor=fig.get_facecolor())
    print(OUT)


if __name__ == "__main__":
    main()
