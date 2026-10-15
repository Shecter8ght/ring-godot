# -*- coding: utf-8 -*-
"""Схема новой зоны 1 «Южная окраина» без ТЦ (предложение, 2026-10-15).

Не уровень и не данные игры — картинка для согласования с владельцем. Образец — его концепт
«Southern Outskirts» (болото, панельки, недострой, спортплощадка, автостанция, ж/д станция,
на востоке переход к карте ТЦ). Готовые куски — двор хрущёвок, рынок, дома у оврага с оврагом —
остаются на своих нынешних координатах: карта строится вокруг них. Их положение читается из
data/zone01_nw_placements.json и констант tools/build_zone01_yard.py / build_zone01.py.

Координаты схемы: X — восток (= x игры), Y — север (= −z игры); центр бывшего ТЦ в (0, 0).
Описание — docs/design/zone01_outskirts.md.

    python -X utf8 tools/zone01_outskirts_concept.py  →  docs/design/zone01_outskirts_concept.png
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "design" / "zone01_outskirts_concept.png"
PLACEMENTS = ROOT / "data" / "zone01_nw_placements.json"

# готовое: корпуса двора (tools/build_zone01_yard.py BUILDINGS: имя, x, z игры, поворот, длина, глубина)
YARD_BUILDINGS = [(-212.0, -138.0, 0.0, 57.6, 11.6), (-154.0, -108.0, -90.0, 57.6, 11.6), (-238.0, -80.0, 90.0, 54.4, 12.0)]
# ось оврага (tools/build_zone01.py RAVINE), x, z игры
RAVINE = [(-305, -176), (-312, -140), (-318, -108), (-334, -70), (-345, -36), (-343, 4), (-340, 38), (-326, 66),
          (-310, 90), (-276, 112), (-240, 132), (-208, 158), (-190, 182), (-196, 214), (-214, 250), (-232, 280)]

C = {
    "bg": "#ece8dc", "outside": "#d6d2c3", "ground": "#dcdcc6", "forest": "#93ad82", "green": "#bccfa6",
    "swamp": "#9fb5a6", "water": "#86aec4", "road": "#8b8e90", "road_edge": "#6c6f71", "rail": "#5d554b",
    "bld": "#8a8279", "bld_edge": "#4c463f", "panel": "#a7a39b", "ready": "#127a74", "text": "#2b2824",
    "spawn": "#2d6cc0", "extract": "#1e9e4a", "cond": "#d68a00", "danger": "#c0392b", "sport": "#c98d6b",
    "site": "#cdbb99",
}
PT_PER_M = 1.0


def g(x: float, z: float) -> tuple[float, float]:
    """Координаты игры (x, z) → схема (X, Y), север вверху."""
    return x, -z


def label(ax, xy, text: str, size: float = 8.0, color: str | None = None, weight: str = "normal",
          ha: str = "center", rot: float = 0.0, z: float = 30) -> None:
    ax.text(xy[0], xy[1], text, fontsize=size, color=color or C["text"], weight=weight, ha=ha, va="center",
            rotation=rot, zorder=z, linespacing=1.15)


def num(ax, xy, n: int) -> None:
    ax.add_patch(Circle(xy, 10, fc="#2b2824", ec="white", lw=1.2, zorder=40))
    ax.text(xy[0], xy[1], str(n), fontsize=8, color="white", weight="bold", ha="center", va="center", zorder=41)


def rect(ax, cx, cy, w, h, fc, ec=None, lw=0.8, z=5, angle=0.0, hatch=None, alpha=1.0, ls="-"):
    ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h, angle=angle, rotation_point="center", fc=fc,
                           ec=ec or C["bld_edge"], lw=lw, zorder=z, hatch=hatch, alpha=alpha, ls=ls))


def line(ax, pts, width_m: float, color: str, edge: str | None = None, z: float = 3, ls="-") -> None:
    xs, ys = zip(*pts)
    if edge:
        ax.plot(xs, ys, color=edge, lw=(width_m + 2.0) * PT_PER_M, solid_capstyle="butt", zorder=z, ls=ls)
    ax.plot(xs, ys, color=color, lw=width_m * PT_PER_M, solid_capstyle="butt", zorder=z + 0.1, ls=ls)


def road(ax, pts, width_m: float = 8.0, z: float = 3) -> None:
    line(ax, pts, width_m, C["road"], C["road_edge"], z)


def dim(ax, p0, p1, text: str, off: tuple[float, float] = (0, 0)) -> None:
    """Размерная линия с подписью."""
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="<|-|>", mutation_scale=10, color="#3d3a35", lw=1.0, zorder=50))
    mx, my = (p0[0] + p1[0]) / 2 + off[0], (p0[1] + p1[1]) / 2 + off[1]
    ax.text(mx, my, text, fontsize=8.5, weight="bold", ha="center", va="center", zorder=51, color="#3d3a35",
            bbox={"boxstyle": "round,pad=0.2", "fc": C["bg"], "ec": "none"})


def ready_outline(ax, pts, text: str, at, ha: str = "center") -> None:
    """Контур готового куска (остаётся на месте) и подпись."""
    ax.add_patch(Polygon(pts, closed=True, fc="none", ec=C["ready"], lw=2.6, ls=(0, (7, 3)), zorder=20))
    label(ax, at, text, 8.2, C["ready"], "bold", ha=ha, z=31)


def main() -> None:
    global PT_PER_M
    fig = plt.figure(figsize=(17.0, 12.6), dpi=110)
    ax = fig.add_axes([0.01, 0.03, 0.68, 0.94])
    x0, x1, y0, y1 = -440.0, 335.0, -345.0, 380.0
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])
    # пунктов на метр: окно по ширине или высоте — что теснее
    PT_PER_M = min(0.68 * 17.0 * 72.0 / (x1 - x0), 0.94 * 12.6 * 72.0 / (y1 - y0))
    rnd = random.Random(5)

    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=C["outside"], ec="none", zorder=0))
    boundary = [(-395, -300), (-170, -312), (140, -305), (262, -300), (272, -120), (276, 130), (258, 325),
                (40, 342), (-210, 338), (-370, 330), (-405, 160), (-410, -80)]
    ax.add_patch(Polygon(boundary, closed=True, fc=C["ground"], ec="#a3762a", lw=2.0, ls=(0, (6, 3)), zorder=1))

    # --- лес по краям (запад за оврагом, север за болотом, северо-восток)
    forest = [
        [(-410, -80), (-405, 160), (-370, 330), (-330, 300), (-360, 150), (-372, -40), (-380, -300), (-395, -300)],
        [(-370, 330), (-210, 338), (40, 342), (60, 316), (-120, 314), (-300, 304)],
        [(258, 325), (40, 342), (60, 316), (180, 312), (245, 296)],
        [(-170, -312), (140, -305), (120, -280), (-60, -268), (-160, -282)],
    ]
    for poly in forest:
        ax.add_patch(Polygon(poly, closed=True, fc=C["forest"], ec="none", zorder=1.5))
    label(ax, (-425, 240), "лес", 8, "#3e5531")
    label(ax, (300, 230), "за насыпью —\nполе, вдали\nкупол ТЦ", 7.5, "#6b655c")
    label(ax, (-430, -200), "лес,\nпромзона", 7.5, "#6b655c")

    # --- 1. болото на севере: топь, сваи, мостки, насосная, затопленные гаражи
    swamp = [(-300, 178), (-250, 200), (-180, 186), (-120, 205), (-60, 196), (0, 214), (20, 250), (5, 290),
             (-60, 304), (-150, 296), (-240, 300), (-300, 282), (-325, 240)]
    ax.add_patch(Polygon(swamp, closed=True, fc=C["swamp"], ec="#6f8a78", lw=1.0, zorder=2))
    for _ in range(26):  # окна открытой воды
        cx, cy = rnd.uniform(-290, 0), rnd.uniform(205, 290)
        ax.add_patch(Circle((cx, cy), rnd.uniform(5, 13), fc=C["water"], ec="none", zorder=2.5, alpha=0.9))
    for _ in range(70):  # кочки и сухостой
        ax.add_patch(Circle((rnd.uniform(-295, 5), rnd.uniform(195, 295)), rnd.uniform(1.5, 3.5), fc="#6f8b62",
                            ec="none", zorder=2.6))
    boardwalk = [(-200, 190), (-190, 225), (-150, 248), (-110, 246), (-80, 270), (-40, 286)]
    ax.plot(*zip(*boardwalk), color="#8a6a43", lw=2.6 * PT_PER_M, zorder=4, ls=(0, (1.2, 0.6)))
    rect(ax, -150, 258, 14, 10, C["bld"], z=5)  # насосная на острове
    for i in range(4):
        rect(ax, -258 + i * 5, 222, 4, 7, "#7d7469", z=5, alpha=0.8)  # затопленные гаражи
    # речка из болота на восток, под насыпью — к старому мосту
    river = [(5, 290), (60, 300), (130, 306), (200, 300), (250, 312), (300, 320)]
    line(ax, river, 9.0, C["water"], "#5f8296", z=2.2)
    # исток оврага у болота
    rav = [g(x, z) for x, z in RAVINE]
    line(ax, rav, 30.0, "#b9b1a0", None, z=1.8)
    line(ax, rav, 4.0, C["water"], None, z=2.0)
    ax.plot(*zip(*rav), color="#7d7566", lw=0.6, zorder=2.1, ls=(0, (3, 2)))

    # --- бывший ТЦ: только тень для ориентира
    ax.add_patch(Circle((0, 0), 87.5, fc="none", ec="#9b9384", lw=1.0, ls=(0, (2, 3)), zorder=1.6))
    label(ax, (-62, 25), "здесь был ТЦ Ø175", 7, "#9b9384", rot=0)

    # --- дороги
    road(ax, [(-272, 164), (-174, 164), (-10, 164)], 9.0)  # северная улица вдоль болота
    road(ax, [(-10, 164), (25, 178), (25, 262), (60, 300), (60, 352)], 7.0)  # по краю болота → к старому мосту
    road(ax, [(110, 60), (110, 92)], 6.0)  # въезд на стройку
    rect(ax, 52, 296, 9, 24, "#8a6a43", angle=-40, z=6)  # старый мост через речку
    road(ax, [(-10, 164), (-10, 60), (-10, -95)], 9.0)  # проспект с севера к автостанции
    road(ax, [(-110, 60), (-10, 60), (190, 60), (300, 60)], 9.0)  # улица к ТЦ, под ж/д мостом на восток
    road(ax, [(-300, 175), (-330, 260), (-352, 340)], 6.0)  # лесная дорога на северо-запад по дамбе
    road(ax, [(-95, -150), (40, -150), (110, -125), (150, -125)], 7.0)  # привокзальная
    road(ax, [(-10, -95), (-60, -95), (-110, -60)], 6.0)  # к рынку
    road(ax, [(-174, 164), (-174, 123)], 6.0)  # въезд во двор (как сейчас)
    road(ax, [(-300, -35), (-343, -37), (-400, -40)], 5.0)  # мост через овраг → в промзону
    label(ax, (100, 66), "улица к ТЦ", 7.5, "#f4f1ea")
    label(ax, (-4, 120), "проспект", 7.5, "#f4f1ea", rot=90)

    # --- железная дорога на невысокой насыпи вдоль востока, станция на юго-востоке
    line(ax, [(217, 350), (217, 120), (213, -60), (195, -200), (185, -320)], 16.0, "#a49786", None, z=2.4)
    for dx in (-3.0, 3.0):
        ax.plot([217 + dx, 217 + dx, 213 + dx, 195 + dx, 185 + dx], [350, 120, -60, -200, -320], color=C["rail"],
                lw=1.1, zorder=3.5)
    for k, (xa, xb) in enumerate(((201, 183), (189, 171))):  # станционные пути и тупики
        ax.plot([211, xa, xb], [-70, -150, -230], color=C["rail"], lw=1.0, zorder=3.5)
    rect(ax, 217, 60, 22, 14, "#b8a98d", z=6)  # ж/д мост над улицей к ТЦ
    rect(ax, 150, -128, 40, 14, C["bld"], z=6)  # вокзальчик
    rect(ax, 177, -132, 6, 60, "#c4b8a4", z=5.5)  # платформа
    ax.plot([150, 207], [-100, -100], color="#7a6c58", lw=2.2 * PT_PER_M, zorder=6)  # пешеходный мост через пути
    rect(ax, 213, -190, 18, 50, "#9d958a", z=6)  # депо
    for yy in (-150, -165, -180, -205, -220):
        rect(ax, 191 if yy > -190 else 181, yy, 3.4, 13, "#6d5040", z=6.5)  # вагоны
    rect(ax, 172, -38, 26, 18, C["bld"], z=6)  # тяговая подстанция
    label(ax, (172, -52), "тяговая ТП", 6.8)

    # --- 2. панельки: готовый двор + второй двор (новый, пока снаружи)
    for x, z, yaw, L, D in YARD_BUILDINGS:
        X, Y = g(x, z)
        rect(ax, X, Y, L, D, C["panel"], angle=-yaw, z=8, lw=1.0)
    for i, gz in enumerate(range(-160, -104, 4)):
        rect(ax, -269.5, -gz, 6, 3.2, "#8e8478", z=7, lw=0.4)
    rect(ax, -197, 92, 18, 14, "#d8c9a5", z=6)  # площадка
    for X, Y, ang in ((-80, 145, 0), (-35, 100, 90), (-115, 95, 90)):  # второй двор
        rect(ax, X, Y, 57.6, 11.6, C["panel"], angle=ang, z=8, lw=0.8, alpha=0.75)
    rect(ax, -70, 78, 26, 14, "#c8b693", z=7)  # детский сад / магазин «Продукты» в первом этаже

    # --- рынок (готовый), дома у оврага (готовые) — из данных расстановки
    pl = json.loads(PLACEMENTS.read_text(encoding="utf-8"))
    for item in pl["architecture"]:
        a = item.get("asset", "")
        x, _, z = item["position"]
        if abs(x) < 40 and abs(z) < 40:
            continue  # мебель задаётся в локальных координатах подъезда
        X, Y = g(x, z)
        yaw = float(item.get("yaw", 0.0))
        if a == "market_hangar":
            rect(ax, X, Y, 24, 42, C["bld"], angle=-yaw, z=8, lw=1.0)
        elif a.startswith("market_stall"):
            rect(ax, X, Y, 6.5, 13, "#b49c7c" if a.endswith("open") else "#a69886", angle=-yaw, z=8, lw=0.5)
        elif a.startswith("house"):
            rect(ax, X, Y, 11, 9, "#9a7d63", angle=-yaw, z=8, lw=0.8)
        elif a == "garden_shed":
            rect(ax, X, Y, 4, 3, "#8a7a66", angle=-yaw, z=8, lw=0.4)
        elif a == "ravine_bridge":
            rect(ax, X, Y, 34, 3.5, "#8a6a43", angle=-yaw, z=8, lw=0.6)
        elif a == "garden_fence":
            ax.add_patch(Circle((X, Y), 0.9, fc="#8a7a66", ec="none", zorder=7))

    ready_outline(ax, [(-276, 168), (-140, 168), (-140, 50), (-276, 50)], "ГОТОВО: двор хрущёвок\n(подъезд, 6 квартир, подвал)", (-208, 182))
    ready_outline(ax, [(-240, 56), (-108, 56), (-108, -108), (-240, -108)], "ГОТОВО:\nрынок\nи ангар", (-80, -40))
    ready_outline(ax, [(-372, 14), (-255, 14), (-255, -66), (-372, -66)], "ГОТОВО: дома\nу оврага, мост", (-318, -86))

    # --- 3. недострой: два каркаса, кран, бытовки, склад материалов
    ax.add_patch(Polygon([(30, 92), (190, 92), (196, 232), (40, 236)], closed=True, fc=C["site"], ec="#8f7c5a",
                         lw=1.2, zorder=3, ls=(0, (4, 2))))
    rect(ax, 95, 180, 62, 22, "#9b9284", z=8, lw=1.2, hatch="xx")  # каркас 9 эт.
    rect(ax, 150, 130, 36, 22, "#9b9284", z=8, lw=1.2, hatch="xx", angle=90)  # каркас 5 эт. (нынешний недострой)
    ax.plot([60, 140], [130, 150], color="#d6a21e", lw=2.0, zorder=9)  # стрела крана
    ax.add_patch(Circle((60, 130), 3.5, fc="#d6a21e", ec="#7a5c10", zorder=9))
    for i in range(4):
        rect(ax, 50 + i * 9, 104, 7, 3, "#c4c0b5", z=8)  # бытовки
    rect(ax, 175, 205, 26, 18, "#bfb39c", z=7, hatch="..")  # склад материалов

    # --- 4. спортплощадка: стадион школы, баскетбол, зал ДЮСШ
    ax.add_patch(Rectangle((40, -45), 112, 80, fc="#c9a58b", ec="#7b5d48", lw=1.0, zorder=4))
    ax.add_patch(Rectangle((58, -32), 76, 54, fc="#9cba86", ec="white", lw=1.0, zorder=4.5))
    rect(ax, 30, 0, 18, 26, "#c98d6b", z=5, ec="#7b5d48")  # баскетбол
    rect(ax, 100, -78, 60, 26, "#7f8ea0", z=7)  # зал ДЮСШ
    rect(ax, 96, 42, 50, 5, "#9e958a", z=5)  # трибуна

    # --- 5. автостанция: навес-ангар, платформы, касса, ремзона, автобусы
    ax.add_patch(Rectangle((-100, -215), 160, 118, fc="#cfccc4", ec="#9d998f", lw=0.8, zorder=3))
    rect(ax, -60, -118, 50, 16, C["bld"], z=7)  # здание автостанции
    for i in range(4):
        rect(ax, -82 + i * 22, -146, 16, 4, "#a08a68", z=7)  # навесы платформ
    rect(ax, 20, -180, 60, 34, "#9d958a", z=6, alpha=0.9)  # гараж-ангар автобусов
    for i in range(9):
        rect(ax, -88 + i * 12 + rnd.uniform(-1, 1), -190 + rnd.uniform(-4, 4), 3.0, 12, "#d0b25a", angle=rnd.uniform(-8, 8), z=8,
             ec="#7a6533", lw=0.5)  # автобусы
    rect(ax, -10, -205, 30, 10, "#b5a68c", z=6)  # ремонтные боксы

    # --- АЗС у выезда к ТЦ
    rect(ax, 178, 30, 26, 14, "#c9b9a0", z=6, hatch="////")
    rect(ax, 194, 14, 12, 9, C["bld"], z=6)


    # --- номера участков
    for n, xy in [(1, (-120, 222)), (2, (-60, 128)), (3, (110, 214)), (4, (96, -10)), (5, (-30, -170)), (6, (140, -158)),
                  (7, (-174, -78)), (8, (-232, -40)), (9, (178, 48))]:
        num(ax, xy, n)

    # --- появление, выходы
    for xy in [(-395, 215), (150, 322), (258, -30), (110, -290), (-250, -292), (-398, -150)]:
        ax.add_patch(Circle(xy, 8, fc=C["spawn"], ec="white", lw=1.4, zorder=45))
    exits = [((-352, 330), C["extract"], "Лесная дорога\n(северная зона)"),
             ((60, 338), C["extract"], "Старый мост\n(к реке)"),
             ((-396, -40), C["extract"], "Мост через овраг\n(в промзону)"),
             ((187, -305), C["extract"], "Ж/д пути\n(окраина)"),
             ((8, -126), C["cond"], "Автостанция\n(автобус)"),
             ((290, 60), "#7b3fa0", "К ТЦ"),
             ]
    for (x, y), col, text in exits:
        ax.add_patch(Polygon([(x, y + 10), (x - 9, y - 6), (x + 9, y - 6)], closed=True, fc=col, ec="white", lw=1.2, zorder=45))
        label(ax, (x, y - 18), text, 6.8, "#1d4d2c" if col == C["extract"] else ("#5a2c75" if col == "#7b3fa0" else "#7a4f00"),
              "bold", z=46)
    ax.add_patch(FancyArrowPatch((250, 74), (330, 74), arrowstyle="-|>", mutation_scale=18, color="#7b3fa0", lw=3, zorder=44))

    # --- размеры
    dim(ax, (-410, -326), (276, -326), "≈ 690 м")
    dim(ax, (312, -312), (312, 342), "≈ 650 м", off=(0, 0))
    dim(ax, (-300, 312), (20, 312), "болото ≈ 330 м", off=(0, 9))
    dim(ax, (-100, -224), (60, -224), "160 м")
    dim(ax, (40, -54), (152, -54), "112 м")
    dim(ax, (30, 242), (196, 242), "≈ 165 м", off=(0, 7))

    # масштаб и север
    ax.plot([-400, -300], [365, 365], color="black", lw=3, zorder=50)
    ax.plot([-300, -200], [365, 365], color="white", lw=3, zorder=50)
    ax.plot([-400, -200], [365, 365], color="black", lw=0.6, zorder=51)
    for xv, t in ((-400, "0"), (-300, "100"), (-200, "200 м")):
        ax.text(xv, 377, t, fontsize=7.5, ha="center", zorder=51)
    ax.annotate("", xy=(300, 375), xytext=(300, 342), arrowprops={"arrowstyle": "-|>", "lw": 2, "color": "black"})
    ax.text(282, 358, "С", fontsize=11, weight="bold", ha="center")

    # --- легенда
    lx = fig.add_axes([0.70, 0.03, 0.295, 0.94])
    lx.axis("off")
    y = 0.99

    def put(text: str, size: float = 8.4, weight: str = "normal", color: str = C["text"], step: float | None = None) -> None:
        nonlocal y
        lx.text(0.0, y, text, fontsize=size, weight=weight, color=color, va="top", transform=lx.transAxes)
        y -= step if step is not None else 0.0085 + size * 0.0017

    put("Зона 1 «Южная окраина» — без ТЦ", 14, "bold")
    put("Схема · предложение 2026-10-15 · по концепту владельца", 8.5)
    put("Готовые куски остаются на своих местах, карта — вокруг них.", 8)
    put("", 5)
    put("Участки", 10.5, "bold")
    for t in ("1  Болото: топь, окна воды, мостки, насосная, затопленные гаражи",
              "2  Панельки: готовый двор + второй двор (3 дома, пока снаружи)",
              "3  Недострой: каркасы 9 и 5 эт., кран, бытовки, склад",
              "4  Спортплощадка: школьный стадион, баскетбол, зал ДЮСШ",
              "5  Автостанция: здание, платформы, ангар, автобусы, боксы",
              "6  Ж/д станция: пути, платформа, вокзальчик, депо, вагоны",
              "7  Рынок и ангар (готово) — рынок у автостанции",
              "8  Частные дома у оврага, мост (готово)",
              "9  АЗС на выезде к ТЦ"):
        put(t)
    put("", 5)
    put("Готовое и что уходит", 10.5, "bold")
    for t in ("Остаются как есть: двор, рынок, дома, овраг с ручьём.",
              "Уходят: ТЦ с площадью, паркинг, погрузка, кольцевая дорога,",
              "насыпь на севере, холм с мачтой, отстойники, блокпост.",
              "Переносятся: недострой (каркас 5 эт.), подстанция — к путям.",
              "Гаражи — по желанию, место найдём (в концепте их нет)."):
        put(t, 8.2)
    put("", 5)
    put("Стык с картой ТЦ", 10.5, "bold")
    for t in ("«Улица к ТЦ» уходит на восток под ж/д мостом. На карте ТЦ",
              "игрок приходит с запада — по дороге мимо КПП ЧВК.",
              "Сейчас «К ТЦ» — обычный выход; позже — переход: следующий",
              "рейд начинается у КПП на карте ТЦ с тем же снаряжением.",
              "С востока зоны 1 над насыпью виден купол ТЦ."):
        put(t, 8.2)
    put("", 5)
    put("Обозначения", 10.5, "bold")
    items = [(C["spawn"], "o", "появление (6, по краям)"), (C["extract"], "^", "выход всегда"),
             (C["cond"], "^", "выход по условию"), ("#7b3fa0", "^", "к карте ТЦ"),
             (C["ready"], "s", "готовый кусок — остаётся на месте")]
    for col, mk, text in items:
        lx.plot([0.02], [y - 0.007], marker=mk, color=col, markersize=9, transform=lx.transAxes, mec="white")
        lx.text(0.07, y, text, fontsize=8.4, va="top", transform=lx.transAxes, color=C["text"])
        y -= 0.021
    y -= 0.006
    for t in ("Рельеф: болото на 1,5–2 м ниже улиц, овраг −10 м (как есть),",
              "насыпь ж/д +3 м вдоль востока — одна граница и «горлышко»",
              "под мостом. Дистанции: 3–20 м в домах, 20–70 м во дворах,",
              "на рынке и станции, до 150 м вдоль путей и через болото."):
        put(t, 8.0, color="#4a463f", step=0.017)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, facecolor=fig.get_facecolor())
    print("saved", OUT)


if __name__ == "__main__":
    main()
