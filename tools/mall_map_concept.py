# -*- coding: utf-8 -*-
"""Схема отдельной карты ТЦ с прилегающей территорией (предложение, 2026-10-15).

Это не уровень и не данные игры — картинка для согласования с владельцем.
Координаты в метрах: x — восток, y — север (север вверху), центр ТЦ в (0, 0).
Образец раскладки — первая картинка концепта владельца «ТЦ РИНГ — прилегающая территория»
(docs/design/concepts/mall_2026-10-15). Описание — docs/design/mall_map.md.

    python -X utf8 tools/mall_map_concept.py  →  docs/design/mall_map_concept.png
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, Polygon, Rectangle, Wedge

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "design" / "mall_map_concept"

# Здание — решение владельца 2026-10-15: Ø200; атриум Ø60 под куполом, подиум с тротуаром, пожарный проезд
MALL_R = 100.0
ATRIUM_R = 30.0
PODIUM_R = 108.0
FIRE_LANE = (112.0, 122.0)
LOOP_R = 255.0  # объездная дорога вокруг всей территории ТЦ (как на образце)

C = {
    "bg": "#ece8dc", "outside": "#d9d4c6", "field": "#dfe0c8", "forest": "#9db58a",
    "green": "#bccfa6", "road": "#8b8e90", "road_edge": "#6c6f71", "parking": "#cfccc4",
    "plaza": "#e3d6bd", "mall": "#d9cbb0", "mall_edge": "#5e5446", "atrium": "#cfe0ea",
    "bld": "#8a8279", "bld_edge": "#4c463f", "water": "#8fb6cc", "danger": "#c0392b",
    "pit": "#b9b3a6", "text": "#2b2824", "spawn": "#2d6cc0", "extract": "#1e9e4a",
    "cond": "#d68a00",
}


def pol(a_deg: float, r: float) -> tuple[float, float]:
    """Точка по углу (0° — восток, 90° — север) и радиусу."""
    a = math.radians(a_deg)
    return r * math.cos(a), r * math.sin(a)


def label(ax, xy, text: str, size: float = 8.5, color: str | None = None, weight: str = "normal",
          ha: str = "center", box: bool = False, rot: float = 0.0) -> None:
    kw = {}
    if box:
        kw["bbox"] = {"boxstyle": "round,pad=0.25", "fc": "#fbf9f3", "ec": "#9a9283", "lw": 0.6, "alpha": 0.92}
    ax.text(xy[0], xy[1], text, fontsize=size, color=color or C["text"], weight=weight,
            ha=ha, va="center", rotation=rot, zorder=30, linespacing=1.15, **kw)


def num(ax, xy, n: int) -> None:
    """Номер объекта в кружке — расшифровка в легенде справа."""
    ax.add_patch(Circle(xy, 9.5, fc="#2b2824", ec="white", lw=1.2, zorder=40))
    ax.text(xy[0], xy[1], str(n), fontsize=7.5, color="white", weight="bold", ha="center", va="center", zorder=41)


def rect(ax, cx, cy, w, h, fc, ec=None, lw=0.8, z=5, angle=0.0, hatch=None, alpha=1.0):
    r = Rectangle((cx - w / 2, cy - h / 2), w, h, angle=angle, rotation_point="center", fc=fc,
                  ec=ec or C["bld_edge"], lw=lw, zorder=z, hatch=hatch, alpha=alpha)
    ax.add_patch(r)
    return r


def road(ax, pts, width_m: float, z: int = 3) -> None:
    xs, ys = zip(*pts)
    # ширина линии в пунктах подбирается под масштаб фигуры (см. PT_PER_M)
    ax.plot(xs, ys, color=C["road_edge"], lw=(width_m + 2.0) * PT_PER_M, solid_capstyle="butt", zorder=z)
    ax.plot(xs, ys, color=C["road"], lw=width_m * PT_PER_M, solid_capstyle="butt", zorder=z + 0.1)


def arc_pts(a0: float, a1: float, r: float, n: int = 90):
    return [pol(a0 + (a1 - a0) * i / n, r) for i in range(n + 1)]


def car_rows(ax, a0: float, a1: float, r0: float, r1: float, step_r: float = 16.0, density: float = 0.55,
             seed: int = 1) -> None:
    """Ряды брошенных машин на парковке — точками, с пропусками, как после бегства."""
    import random
    rnd = random.Random(seed)
    r = r0 + 6.0
    while r < r1 - 4.0:
        n = int(abs(a1 - a0) * math.pi / 180.0 * r / 3.0)
        for i in range(n):
            if rnd.random() > density:
                continue
            a = a0 + (a1 - a0) * (i + 0.5) / n
            x, y = pol(a, r)
            ax.add_patch(Rectangle((x - 1.1, y - 2.3), 2.2, 4.6, angle=a - 90.0 + rnd.uniform(-8, 8),
                                   rotation_point="center", fc=rnd.choice(["#7d8790", "#9a9a92", "#6f6a66", "#a08c74", "#5f6e7a"]),
                                   ec="none", zorder=6))
        r += step_r


def main() -> None:
    global PT_PER_M
    fig = plt.figure(figsize=(17.0, 12.6), dpi=110)
    ax = fig.add_axes([0.01, 0.04, 0.70, 0.92])
    x0, x1, y0, y1 = -470.0, 460.0, -400.0, 400.0
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])
    # пунктов на метр: ширина оси в дюймах * 72 / ширина в метрах
    PT_PER_M = 0.70 * 17.0 * 72.0 / (x1 - x0)

    # --- за границей: город, промзона, новостройки (декорация без входа)
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=C["outside"], ec="none", zorder=0))
    boundary = [(-400, -350), (380, -350), (425, -150), (412, 205), (335, 345), (-150, 368), (-385, 305), (-438, 60)]
    ax.add_patch(Polygon(boundary, closed=True, fc=C["field"], ec="#a3762a", lw=2.0, ls=(0, (6, 3)), zorder=1))
    label(ax, (0, -385), "за шоссе — новостройки ЖК 17 эт. (видны, без входа)", 8, "#6b655c")
    label(ax, (440, 60), "промзона,\nсклады\n(декорация)", 8, "#6b655c")
    label(ax, (-455, 200), "поле,\nЛЭП", 8, "#6b655c")

    # --- лесополосы по краю (север и северо-восток), скрытые подходы
    ax.add_patch(Polygon([(-385, 305), (-150, 368), (335, 345), (300, 300), (60, 318), (-160, 322), (-330, 270)],
                         closed=True, fc=C["forest"], ec="none", zorder=1.5, alpha=0.95))
    ax.add_patch(Polygon([(335, 345), (412, 205), (425, 60), (380, 70), (372, 200), (300, 300)],
                         closed=True, fc=C["forest"], ec="none", zorder=1.5, alpha=0.95))
    label(ax, (-40, 343), "лесополоса — тихие подходы с севера", 8, "#3e5531")

    # --- шоссе на юге с пробкой и пешеходным мостом
    road(ax, [(-470, -318), (460, -318)], 24.0, z=2)
    import random
    rnd = random.Random(7)
    for i in range(70):
        x = -440 + i * 12.5 + rnd.uniform(-3, 3)
        lane = rnd.choice([-326, -321, -315, -310])
        if rnd.random() < 0.72:
            ax.add_patch(Rectangle((x - 2.3, lane - 1.1), 4.6, 2.2, fc=rnd.choice(["#7d8790", "#6f6a66", "#a08c74", "#4f5a63"]),
                                   ec="none", zorder=4))
    rect(ax, -40, -318, 6, 34, "#b8a98d", z=4.5)  # пешеходный мост через шоссе
    label(ax, (-250, -318), "федеральная трасса: пробка брошенных машин", 8, "#f4f1ea")
    label(ax, (-40, -296), "пешеходный мост", 7, "#3d3a35")

    # --- объездная дорога вокруг территории ТЦ, съезды
    road(ax, arc_pts(0, 360, LOOP_R, 240), 9.0)
    road(ax, [(205, -318), (215, -280), (205, -245), pol(-50, LOOP_R)], 8.0)  # съезд с трассы
    road(ax, [(-150, -318), (-150, -292), pol(-122, LOOP_R)], 8.0)  # к автостанции
    road(ax, [(-470, 30), (-300, 22), pol(175, LOOP_R)], 9.0)  # западная дорога через КПП
    road(ax, [(400, 268), (300, 205), pol(38, LOOP_R)], 7.0)  # служебная к техкомплексу
    # въезды с объездной к зданию
    for a in (-90, 180, 0, 45):
        road(ax, [pol(a, LOOP_R), pol(a, FIRE_LANE[1])], 8.0)

    # --- парковки: юг (главная, террасами), запад, восток
    ax.add_patch(Wedge((0, 0), 240, -160, -20, width=240 - 130, fc=C["parking"], ec="#9d998f", lw=0.6, zorder=2))
    ax.add_patch(Wedge((0, 0), 238, 150, 210, width=238 - 130, fc=C["parking"], ec="#9d998f", lw=0.6, zorder=2))
    ax.add_patch(Wedge((0, 0), 238, -20, 18, width=238 - 130, fc=C["parking"], ec="#9d998f", lw=0.6, zorder=2))
    for rr in (172, 206):  # подпорные стенки террас южной парковки
        ax.plot(*zip(*arc_pts(-158, -22, rr, 80)), color="#5c574f", lw=1.6, zorder=7)
    car_rows(ax, -158, -118, 130, 240, seed=2, density=0.45)
    car_rows(ax, -62, -22, 130, 240, seed=3, density=0.5)
    car_rows(ax, 152, 208, 130, 238, seed=4, density=0.8)
    car_rows(ax, -18, 16, 130, 238, seed=5, density=0.35)
    # навесы для тележек и островки зелени на главной парковке
    for a, r in ((-140, 190), (-128, 222), (-50, 190), (-38, 222), (-150, 150), (-30, 150)):
        x, y = pol(a, r)
        rect(ax, x, y, 12, 3.5, "#9c8f7a", angle=a - 90, z=7)
    for a, r in ((-145, 172), (-35, 172), (-140, 206), (-40, 206)):
        ax.add_patch(Circle(pol(a, r), 5.5, fc=C["green"], ec="#7f966b", lw=0.6, zorder=7.5))

    # --- главная площадь (юг)
    ax.add_patch(Wedge((0, 0), 168, -116, -64, width=168 - PODIUM_R, fc=C["plaza"], ec="#a89a80", lw=0.8, zorder=3))
    ax.add_patch(Circle(pol(-90, 140), 8, fc=C["water"], ec="#6f8fa1", zorder=8))  # сухой фонтан
    for a in (-104, -76):
        ax.add_patch(Circle(pol(a, 152), 6, fc=C["green"], ec="#7f966b", zorder=8))
    rect(ax, *pol(-90, 162), 4, 14, "#5b5046", z=9)  # рекламная стела «РИНГ»
    # крытая галерея от автостанции к площади
    gal = [(-150, -272), (-118, -222), (-70, -175), pol(-100, 168)]
    ax.plot(*zip(*gal), color="#a9926f", lw=5.0 * PT_PER_M, zorder=8, solid_capstyle="round")
    ax.plot(*zip(*gal), color="#e9dcc2", lw=2.2 * PT_PER_M, zorder=8.1, solid_capstyle="round", ls=(0, (2, 1)))

    # --- пожарный проезд и само здание
    ax.add_patch(Wedge((0, 0), FIRE_LANE[1], 0, 360, width=FIRE_LANE[1] - FIRE_LANE[0], fc=C["road"], ec=C["road_edge"], lw=0.8, zorder=4))
    ax.add_patch(Circle((0, 0), PODIUM_R, fc="#e2dccd", ec="#a49c8b", lw=0.8, zorder=4.5))
    ax.add_patch(Circle((0, 0), MALL_R, fc=C["mall"], ec=C["mall_edge"], lw=2.2, zorder=5))
    for a in range(0, 360, 60):  # границы секторов по 60°
        ax.plot(*zip(pol(a, ATRIUM_R + 12), pol(a, MALL_R)), color="#a4977f", lw=0.8, ls=(0, (3, 2)), zorder=5.5)
    ax.add_patch(Circle((0, 0), ATRIUM_R, fc=C["atrium"], ec="#7f9cad", lw=1.0, zorder=6))
    label(ax, (0, 8), "ТЦ «РИНГ»", 12, weight="bold")
    label(ax, (0, -14), "Ø200 м, 4 этажа\nатриум Ø60 под куполом", 8)

    # входы в здание
    def door(a: float, color: str, text: str, dr: float = 30.0, ha: str = "center") -> None:
        x, y = pol(a, MALL_R)
        ax.add_patch(Rectangle((x - 5, y - 5), 10, 10, angle=a, rotation_point="center", fc=color, ec="white", lw=1.0, zorder=12))
        label(ax, pol(a, MALL_R - dr), text, 7.2, color, "bold", ha=ha)

    door(-90, "#1e9e4a", "ГЛАВНЫЙ ВХОД\n(частично обрушен)", 26)
    door(0, C["danger"], "", 30)
    door(90, "#555555", "", 22)
    door(180, "#2d6cc0", "", 27)
    door(135, "#2d6cc0", "", 27)
    door(205, "#2d6cc0", "", 27)
    door(45, "#2d6cc0", "", 30)

    # --- разгрузочный двор (северо-восток), в выемке −4 м
    ax.add_patch(Wedge((0, 0), 210, 22, 70, width=210 - 124, fc=C["pit"], ec="#6f6a60", lw=1.4, zorder=3, hatch="..."))
    for a in (30, 38, 46, 54, 62):
        x, y = pol(a, 158)
        rect(ax, x, y, 3.0, 16, "#e8e4da", angle=a - 90, z=7, ec="#5d574e")  # фуры у доков
    rect(ax, *pol(48, 202), 7, 7, C["danger"], z=9)  # пост ЧВК у ворот двора
    label(ax, pol(46, 186), "пост ЧВК", 7, C["danger"], "bold")

    # --- многоуровневый паркинг (восток) с мостом на 2-й этаж
    rect(ax, 185, -42, 64, 100, "#a19a90", lw=1.4, z=8)
    for k in range(1, 4):
        ax.plot([153, 217], [-92 + k * 25, -92 + k * 25], color="#7c756c", lw=0.7, zorder=8.5)
    bx = pol(-3, MALL_R)[0]
    ax.add_patch(Polygon([(153, -6), (153, 2), (bx, 2), (bx, -6)], closed=True, fc="#c9b893", ec="#6a5d47", lw=1.0, zorder=9))
    label(ax, (122, 9), "мост на 2-й этаж", 7, "#6a5d47", "bold")

    # --- восточная баррикада перед входом
    for i, (a, r) in enumerate(((-8, 130), (0, 136), (8, 130), (-4, 150), (5, 151))):
        rect(ax, *pol(a, r), 3.2, 12, C["danger"], angle=a + (20 if i % 2 else -15), z=9, alpha=0.85)

    # --- сквер с летней верандой на севере (между зданием и объездной)
    ax.add_patch(Wedge((0, 0), 236, 74, 146, width=236 - 128, fc=C["green"], ec="#8aa276", lw=0.6, zorder=2))
    rnd = random.Random(11)
    for i in range(60):
        a = rnd.uniform(76, 144)
        r = rnd.uniform(134, 232)
        ax.add_patch(Circle(pol(a, r), rnd.uniform(3.5, 6.0), fc="#86a873", ec="none", zorder=3, alpha=0.9))
    rect(ax, *pol(100, 144), 26, 12, "#b9a888", angle=10, z=7)  # летняя веранда
    rect(ax, *pol(128, 186), 18, 18, "#d8c9a5", z=7)  # детская площадка

    # --- противопожарный водоём (север), ливнёвка
    ax.add_patch(Ellipse((-110, 288), 120, 56, angle=-8, fc=C["water"], ec="#5f8296", lw=1.2, zorder=4))
    ax.plot([-60, -40, -12], [276, 262, 254], color="#5f8296", lw=2.2, ls=(0, (2, 1.5)), zorder=4.5)

    # --- технический комплекс (восток за объездной): котельная с трубой, ТП, генераторы, башня
    rect(ax, 300, 150, 44, 30, C["bld"], z=8)
    ax.add_patch(Circle((322, 172), 5, fc="#6b625a", ec="#3e3832", lw=1.2, zorder=9))  # труба 45 м — ориентир
    rect(ax, 262, 112, 16, 12, C["bld"], z=8)
    rect(ax, 338, 120, 20, 14, C["bld"], z=8)
    ax.add_patch(Circle((350, 178), 6.5, fc="#9b9389", ec="#4c463f", lw=1.0, zorder=9))  # водонапорная башня
    rect(ax, 283, 192, 26, 14, "#bdb4a8", z=8)

    # --- АЗС (северо-запад), КПП ЧВК (запад), западная парковка с лагерем
    rect(ax, -250, 182, 36, 18, "#c9b9a0", z=8, hatch="////")  # навес колонок
    rect(ax, -274, 210, 18, 11, C["bld"], z=8)
    rect(ax, -228, 206, 14, 12, C["bld"], z=8)
    for i in range(6):
        rect(ax, -352 + i * 7, 18 + (i % 2) * 12, 5.5, 2.6, "#9a9a92", z=9)  # блоки
    rect(ax, -330, 44, 6, 6, C["danger"], z=9)  # вышка
    rect(ax, -372, 4, 16, 6, "#5f7a5a", z=9)
    rect(ax, -372, 44, 16, 6, "#5f7a5a", z=9)
    for i in range(7):  # палатки эвакуационного пункта на западной парковке (предложение)
        x, y = pol(170 + i * 4.5, 190 + (i % 3) * 13)
        rect(ax, x, y, 8, 5, "#7c8f6a", z=8, ec="#4f5c41")

    # --- автостанция (юго-запад), кафе и мойка (юго-восток)
    rect(ax, -158, -284, 70, 16, "#b9ab95", z=8)
    for i in range(4):
        rect(ax, -186 + i * 18, -268, 12, 3, "#8b7b62", z=8.5)
    rect(ax, 262, -262, 30, 20, C["bld"], z=8)
    rect(ax, 300, -240, 18, 26, "#a99f93", z=8)
    ax.plot([240, 248, 285, 292], [-282, -290, -290, -275], color="#6c6f71", lw=3.5 * PT_PER_M, zorder=7)

    # --- подписи участков (номера → легенда)
    nums = [
        (1, (0, -38)), (2, pol(-90, 180)), (3, (-140, -200)), (4, (-158, -300)),
        (5, (185, -100)), (6, (262, -280)), (7, pol(0, 178)), (8, pol(46, 132)), (9, (300, 128)),
        (10, (-110, 315)), (11, pol(110, 200)), (12, (-250, 160)), (13, (-340, 62)), (14, pol(180, 220)),
        (15, (-40, -340)),
    ]
    for n, xy in nums:
        num(ax, xy, n)

    # --- точки появления игроков, выходы, маршруты подхода
    spawns = {"S": (-20, -360), "З": (-415, -110), "СЗ": (-330, 278), "С": (130, 336), "В": (408, 30), "ЮВ": (392, -282)}
    for name, (x, y) in spawns.items():
        ax.add_patch(Circle((x, y), 8, fc=C["spawn"], ec="white", lw=1.4, zorder=45))
    extracts = [((-182, -296), C["extract"], "Автостанция"), ((-60, 256), C["extract"], "Ливнёвка"),
                ((-430, 34), C["cond"], "Дорога за КПП\n(плата)"), (pol(46, 168), C["cond"], "Грузовик\n(питание ворот)"),
                ((405, 120), C["extract"], "Пролом в заборе"), ((-38, 50), C["cond"], "Крыша — вертолёт\n(позже, 4-й этаж)")]
    for (x, y), col, text in extracts:
        ax.add_patch(Polygon([(x, y + 10), (x - 9, y - 6), (x + 9, y - 6)], closed=True, fc=col, ec="white", lw=1.2, zorder=45))
        label(ax, (x, y - 17), text, 6.8, "#1d4d2c" if col == C["extract"] else "#7a4f00", "bold")

    routes = [
        ("A", "#7b3fa0", [(-20, -350), (-60, -300), (-110, -230), (-70, -170), pol(-92, 100)]),
        ("B", "#b5651d", [(-405, -100), (-360, -40), (-300, 60), (-250, 140), (-200, 110), pol(178, 100)]),
        ("C", "#2a7f8f", [(385, -275), (300, -220), (230, -120), (215, -60), (160, -4)]),
        ("D", "#3a6b2a", [(130, 326), (210, 260), (300, 210), (250, 150), pol(46, 108)]),
    ]
    for key, col, pts in routes:
        for i in range(len(pts) - 1):
            last = i == len(pts) - 2
            ax.add_patch(FancyArrowPatch(pts[i], pts[i + 1], arrowstyle="-|>" if last else "-", mutation_scale=14,
                                         color=col, lw=2.2, ls=(0, (5, 3)), zorder=35, shrinkA=0, shrinkB=0))
        mx, my = pts[1]
        ax.add_patch(Circle((mx, my), 9, fc=col, ec="white", lw=1.2, zorder=36))
        ax.text(mx, my, key, fontsize=8, color="white", weight="bold", ha="center", va="center", zorder=37)

    # --- масштаб и север
    ax.plot([200, 300], [-375, -375], color="black", lw=3, zorder=50)
    ax.plot([300, 400], [-375, -375], color="white", lw=3, zorder=50)
    ax.plot([200, 400], [-375, -375], color="black", lw=0.6, zorder=51)
    for xv, t in ((200, "0"), (300, "100"), (400, "200 м")):
        ax.text(xv, -388, t, fontsize=7.5, ha="center", zorder=51)
    ax.annotate("", xy=(420, 385), xytext=(420, 345), arrowprops={"arrowstyle": "-|>", "lw": 2, "color": "black"}, zorder=51)
    ax.text(420, 330, "С", fontsize=11, weight="bold", ha="center", zorder=51)

    # --- легенда справа
    lx = fig.add_axes([0.715, 0.04, 0.28, 0.92])
    lx.axis("off")
    lines = [
        ("ТЦ «РИНГ» — отдельная карта", 14, "bold"),
        ("Схема прилегающей территории · предложение 2026-10-15", 8.5, "normal"),
        ("Образец — первая картинка концепта владельца. Не уровень,", 8, "normal"),
        ("а раскладка для согласования; размеры — ориентиры.", 8, "normal"),
        ("", 6, "normal"),
        ("Участки", 10.5, "bold"),
        ("1  ТЦ: Ø200, 4 этажа, 6 секторов по 60°", 8.5, "normal"),
        ("2  Главная площадь: фонтан, стела, ступени, навес", 8.5, "normal"),
        ("3  Главная парковка: 2 террасы (−2 и −4 м), ряды машин", 8.5, "normal"),
        ("4  Автостанция и крытая галерея к площади", 8.5, "normal"),
        ("5  Многоуровневый паркинг, 4 яруса, мост на 2-й этаж", 8.5, "normal"),
        ("6  Придорожное кафе с окном выдачи, автомойка", 8.5, "normal"),
        ("7  Восточный вход: баррикада рейдеров (горячая точка)", 8.5, "normal"),
        ("8  Разгрузочный двор в выемке −4 м: доки, фуры, лифт на 3-й", 8.5, "normal"),
        ("9  Техкомплекс: котельная с трубой, ТП, генераторы, башня", 8.5, "normal"),
        ("10 Противопожарный водоём и ливнёвка", 8.5, "normal"),
        ("11 Сквер: летняя веранда, детская площадка, деревья", 8.5, "normal"),
        ("12 АЗС (частично разрушена): магазин, навес, мойка", 8.5, "normal"),
        ("13 КПП ЧВК на западной дороге: блоки, вышка, вагончики", 8.5, "normal"),
        ("14 Западная парковка: пробка, пункт эвакуации (палатки)", 8.5, "normal"),
        ("15 Трасса с пробкой и пешеходный мост", 8.5, "normal"),
        ("", 6, "normal"),
        ("Подходы (от появления до здания 260–380 м, 1,5–3 мин)", 10.5, "bold"),
        ("A  юг, быстрый и открытый: автостанция → парковка → площадь", 8.5, "normal"),
        ("B  запад: поле → мимо КПП → АЗС → лагерь → пожарный выход", 8.5, "normal"),
        ("C  восток, вертикальный: кафе → паркинг → мост / вост. вход", 8.5, "normal"),
        ("D  север, тихий: лес → техкомплекс → разгрузочный двор", 8.5, "normal"),
        ("", 6, "normal"),
        ("Обозначения", 10.5, "bold"),
    ]
    y = 0.985
    for text, size, w in lines:
        lx.text(0.0, y, text, fontsize=size, weight=w, color=C["text"], va="top", transform=lx.transAxes)
        y -= 0.0085 + size * 0.0017
    items = [
        (C["spawn"], "o", "появление игроков (края карты)"),
        (C["extract"], "^", "выход всегда"),
        (C["cond"], "^", "выход по условию"),
        (C["danger"], "s", "враждебный пост / баррикада"),
        ("#1e9e4a", "s", "главный вход в ТЦ"),
        ("#555555", "s", "северный вход завален"),
        ("#2d6cc0", "s", "служебный и пожарные выходы"),
    ]
    for col, mk, text in items:
        lx.plot([0.02], [y - 0.007], marker=mk, color=col, markersize=9, transform=lx.transAxes, mec="white")
        lx.text(0.07, y, text, fontsize=8.5, va="top", transform=lx.transAxes, color=C["text"])
        y -= 0.021
    y -= 0.008
    notes = [
        "Рельеф: участок понижается к трассе. Север выше на 2–4 м,",
        "южная парковка спускается двумя террасами с подпорными",
        "стенками — укрытия и разрывы прострелов на открытом.",
        "Двор разгрузки в выемке: сверху видно не всё.",
        "",
        "Риск растёт к центру: снаружи — средняя добыча",
        "(АЗС, кафе, фуры, пост ЧВК), лучшая — внутри ТЦ.",
    ]
    for t in notes:
        lx.text(0.0, y, t, fontsize=8.3, va="top", transform=lx.transAxes, color="#4a463f")
        y -= 0.017

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT.with_suffix(".png"), facecolor=fig.get_facecolor())
    print("saved", OUT.with_suffix(".png"))


PT_PER_M = 1.0

if __name__ == "__main__":
    main()
