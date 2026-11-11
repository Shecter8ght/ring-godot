"""«Проспект», северная сторона западного плеча — чертежи предложения (редакция 1, 2026-11-11).

Квартал от КПП до Банковского переулка: первая линия (БЦ «Проспект, 5» с «Зерном», аптека, «Modus», пекарня,
БЦ «Проспект, 11»), банк «Капитал», автомойка «Блеск», тылы, карманы у бордюра и уличная инфраструктура.

  5. генплан квартала: что стоит и что меняется, тылы, карманы, остановка, проезды;
  6. развёртка северной стороны, поперечный профиль квартала, карманы и полосы тротуара крупно;
  7. банк «Капитал»: участок и первый этаж, −1, 2-й, 3-й этажи, крыша, пути клиентов, денег и персонала;
  8. автомойка «Блеск» и Банковский переулок, разрез банка.

Окружение — из снимка сцены data/blockouts/prospekt_snapshot.json. Сама планировка — словари ниже: это предложение,
в сцену не внесено (docs/design/prospekt_map.md §22).

    python -X utf8 tools/prospekt_north_side_plan.py          # → docs/design/prospekt_north_*.png
"""
from __future__ import annotations

import json
import math
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prospekt_vershina_plan import dim, figure_man, floors_lines, north_arrow, rect, scale_bar, site_axes  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data" / "blockouts" / "prospekt_snapshot.json"
OUT = ROOT / "docs" / "design"

# ---------------------------------------------------------------- улица: профиль северной стороны (как в сцене)
MEDIAN = (-18.65, -12.65)
LANE_EDGE = -32.65          # краевая линия: дальше к бордюру — полоса карманов 2,5 м
CURB = -35.15               # бордюр
WALK = (-46.95, CURB)       # тротуар 11,8 м
FACADE = -48.3              # линия фасадов первой линии
BACK = -59.3                # задние стены первой линии

# первая линия: (ключ, подпись, x0, x1, этажей, высота, открыто игроку)
FIRST_LINE = [
    ("bc5", "БЦ «Проспект, 5»\n«Зерно», цветы\n9 эт. · 33 м", -195.8, -162.8, 9, 33.2, True),
    ("pharm", "аптека\n2 эт.", -160.0, -146.0, 2, 8.0, True),
    ("modus", "«Modus»\n2 эт.", -143.0, -123.0, 2, 8.0, True),
    ("bakery", "пекарня\n2 эт.", -108.0, -94.0, 2, 8.0, True),
    ("bc11", "БЦ «Проспект, 11»\n10 эт. · 37 м", -92.2, -59.8, 10, 36.8, False),
]
PANORAMA = [(-190.0, -160.0, 17), (-160.0, -130.0, 17), (-104.0, -74.0, 25), (-74.0, -44.0, 25)]   # z −113,3…−87,3
PAN_Z = (-113.3, -87.3)
UNDERPASS = (-160.0, -152.0, -45.9, -35.2)        # проём лестницы перехода на тротуаре
DRIVE = (-120.0, -112.2)                          # проезжая часть въезда во двор (предложение, 7,8 м)
FENCE_N = -154.8

# карманы у бордюра: (ключ, x0, x1, мест, назначение)
POCKETS = [
    ("К1", -192.0, -166.0, 3, "БЦ 5 и «Зерно»: 3 места по 7 м"),
    ("К2", -148.0, -136.0, 1, "аптека и «Modus»: погрузка 12 м"),
    ("К3", -104.0, -71.5, 4, "пекарня и БЦ 11: 4 места по 6,9 м"),
    ("К5", -17.0, -3.5, 1, "банк: высадка и одно место 8,5 м"),
]
BUS_BAY = (-71.0, -19.0)                          # остановка: отгон 13 + площадка 26 + отгон 13
BUS_PLATFORM = (-58.0, -32.0)
BULBS = [(-166.0, -148.0, "спуск в переход"), (-136.0, -104.0, "переход и въезд во двор"), (-3.5, 6.0, "ворота инкассации")]
TREES_X = [-186.0, -172.0, -144.0, -100.0, -86.0, -72.0, -10.0]
LAMPS_X = [-198.0, -170.0, -142.0, -100.0, -75.0, -14.0]

# тылы: служебный проезд за первой линией и стоянки
SERVICE = (-66.5, BACK)                           # z: 7,2 м
LOT_ROWS = [(-71.8, -66.5), (-84.9, -79.6)]       # два ряда мест 5,3 м, между ними проезд 7,8 м
LOTS_X = [(-196.0, -123.0), (-108.0, -46.0)]
YARD_ROAD = (-152.8, -145.8)

# ---------------------------------------------------------------- банк «Капитал»
B1 = (-38.0, -4.0, -93.3, -65.3)                  # первый этаж и −1
BU = (-40.0, -2.0, -95.3, -61.3)                  # 2-й и 3-й (нависают на 2 м)
BANK_FENCE = (-43.0, 6.0, -99.3, -52.3)
BY = [0.0, 4.5, 8.4, 12.3]
BASE_Y = -3.2
ANNEX = (-4.0, 2.4, -93.3, -80.3)                 # бокс инкассации, один этаж 4,2 м

# помещения: (подпись, x0, x1, z0, z1, вид)
BANK_F1 = [
    ("операционный зал\nочередь, диваны, менеджеры", -31.0, -11.0, -78.3, -65.3, "pub"),
    ("зона 24/7\nбанкоматы", -38.0, -28.0, -70.3, -65.3, "pub"),
    ("управляющий", -38.0, -31.0, -78.3, -70.3, "staff"),
    ("тамбур", -23.5, -18.5, -68.3, -65.3, "pub"),
    ("VIP-\nпереговорная", -11.0, -4.0, -71.3, -65.3, "pub"),
    ("спуск в\nдепозитарий\nпост, Л3", -11.0, -4.0, -78.3, -71.3, "ctrl"),
    ("кабины\nкасс", -18.0, -11.0, -78.3, -75.3, "pub"),
    ("операционисты\nбэк-офис", -38.0, -24.0, -89.1, -78.3, "staff"),
    ("с/у", -24.0, -20.5, -89.1, -84.0, "staff"),
    ("коридор", -24.0, -18.0, -84.0, -78.3, "staff"),
    ("комната\nперсонала", -20.5, -11.0, -89.1, -83.3, "staff"),
    ("касса", -18.0, -11.0, -83.3, -78.3, "cash"),
    ("касса\nпересчёта", -11.0, -4.0, -89.1, -78.3, "cash"),
    ("Л1 · до крыши", -38.0, -28.0, -93.3, -89.1, "stair"),
    ("охрана · мониторы · КХО", -28.0, -16.0, -93.3, -89.1, "ctrl"),
    ("Л2 · на −1", -16.0, -4.0, -93.3, -89.1, "stair"),
    ("бокс\nинкассации\n6,4 × 13", ANNEX[0], ANNEX[1], ANNEX[2], ANNEX[3], "cash"),
]
BANK_B1 = [
    ("кладовая ценностей\n14 × 22\nсейфы, кассеты", -38.0, -24.0, -89.3, -67.3, "cash"),
    ("пред-\nкла-\nдовая", -24.0, -21.0, -89.3, -65.3, "ctrl"),
    ("коридор", -38.0, -16.0, -93.3, -89.3, "staff"),
    ("Л2", -16.0, -4.0, -93.3, -89.3, "stair"),
    ("пост охраны\nхранилища", -21.0, -14.0, -89.3, -79.3, "ctrl"),
    ("щитовая\nИБП", -14.0, -4.0, -89.3, -79.3, "staff"),
    ("депозитарий\nячейки", -21.0, -11.0, -79.3, -65.3, "pub"),
    ("Л3 · пост", -11.0, -4.0, -79.3, -71.3, "stair"),
    ("кабины\nклиентов", -11.0, -4.0, -71.3, -65.3, "pub"),
]
BANK_F2 = [
    ("Л1", -40.0, -28.0, -95.3, -89.1, "stair"),
    ("архив\nкредитных дел", -28.0, -16.0, -95.3, -83.3, "staff"),
    ("переговорная", -16.0, -2.0, -95.3, -83.3, "staff"),
    ("с/у", -40.0, -34.0, -89.1, -83.3, "staff"),
    ("клад.", -34.0, -28.0, -89.1, -83.3, "staff"),
    ("коридор 2,6", -40.0, -2.0, -83.3, -80.7, "hall"),
    ("с/у", -40.0, -34.0, -80.7, -75.3, "staff"),
    ("кухня", -34.0, -24.0, -80.7, -75.3, "staff"),
    ("ИТ", -24.0, -18.0, -80.7, -75.3, "ctrl"),
    ("копир.", -18.0, -11.0, -80.7, -75.3, "staff"),
    ("нач. отдела", -11.0, -2.0, -80.7, -75.3, "staff"),
    ("кредитный отдел\nоткрытый офис 26 × 14", -40.0, -14.0, -75.3, -61.3, "staff"),
    ("бухгалтерия\nсейф", -14.0, -2.0, -75.3, -61.3, "cash"),
]
BANK_F3 = [
    ("Л1", -40.0, -28.0, -95.3, -89.1, "stair"),
    ("серверная\nИБП", -28.0, -16.0, -95.3, -83.3, "ctrl"),
    ("служба\nбезопасности\nключ-карты", -16.0, -2.0, -95.3, -83.3, "ctrl"),
    ("с/у", -40.0, -34.0, -89.1, -83.3, "staff"),
    ("клад.", -34.0, -28.0, -89.1, -83.3, "staff"),
    ("коридор 2,6", -40.0, -2.0, -83.3, -80.7, "hall"),
    ("приёмная", -40.0, -24.0, -80.7, -75.3, "staff"),
    ("зам.", -24.0, -13.0, -80.7, -75.3, "staff"),
    ("юрист", -13.0, -2.0, -80.7, -75.3, "staff"),
    ("кабинет директора\nсейф под ключ", -40.0, -22.0, -75.3, -61.3, "cash"),
    ("зал совещаний\n20 × 14", -22.0, -2.0, -75.3, -61.3, "staff"),
]
KIND_FC = {"pub": "#e3f1fb", "staff": "#f3f3ee", "cash": "#fdf0c8", "ctrl": "#f9dcdc", "stair": "#dddddd", "hall": "#ffffff"}

# двери: (x, z, ось стены, ширина)
DOORS_F1 = [(-21.0, -65.3, "x", 2.4), (-33.0, -65.3, "x", 1.6), (-28.0, -67.8, "z", 1.17), (-21.0, -68.3, "x", 2.4),
            (-31.0, -74.0, "z", 1.17), (-11.0, -68.3, "z", 1.17), (-11.0, -74.8, "z", 1.6), (-16.2, -75.3, "x", 1.0),
            (-12.8, -75.3, "x", 1.0), (-25.5, -78.3, "x", 1.17), (-21.0, -84.0, "x", 1.17), (-22.2, -89.1, "x", 1.17),
            (-16.0, -86.0, "z", 1.17), (-18.0, -80.8, "z", 1.17), (-11.0, -81.0, "z", 1.17), (-11.0, -86.5, "z", 1.17),
            (-4.0, -85.0, "z", 1.17), (-33.0, -89.1, "x", 1.17), (-7.0, -89.1, "x", 1.17), (-20.0, -93.3, "x", 1.2),
            (-38.0, -91.2, "z", 1.17), (-0.8, -80.3, "x", 3.6)]
DOORS_B1 = [(-24.0, -77.3, "z", 2.6), (-22.5, -89.3, "x", 1.6), (-21.0, -83.3, "z", 1.17), (-21.0, -69.3, "z", 1.17),
            (-16.0, -91.6, "z", 1.17), (-14.0, -85.0, "z", 1.17), (-11.0, -75.0, "z", 1.17), (-11.0, -68.0, "z", 1.17),
            (-17.5, -89.3, "x", 1.17)]
DOORS_F2 = [(-34.0, -89.1, "x", 1.17), (-22.0, -83.3, "x", 1.17), (-9.0, -83.3, "x", 1.17), (-36.0, -83.3, "x", 1.0),
            (-37.0, -80.7, "x", 1.0), (-29.0, -80.7, "x", 1.17), (-21.0, -80.7, "x", 1.17), (-14.5, -80.7, "x", 1.17),
            (-6.5, -80.7, "x", 1.17), (-27.0, -75.3, "x", 1.6), (-8.0, -75.3, "x", 1.17), (-40.0, -82.0, "z", 1.17)]
DOORS_F3 = [(-34.0, -89.1, "x", 1.17), (-22.0, -83.3, "x", 1.17), (-9.0, -83.3, "x", 1.17), (-36.0, -83.3, "x", 1.0),
            (-32.0, -80.7, "x", 1.6), (-18.5, -80.7, "x", 1.17), (-7.5, -80.7, "x", 1.17), (-31.0, -75.3, "x", 1.17),
            (-12.0, -75.3, "x", 1.6), (-40.0, -82.0, "z", 1.17)]

# ---------------------------------------------------------------- автомойка «Блеск» и переулок
WASH = (6.8, 17.0, -92.0, -66.0)                  # здание 10,2 × 26, высота 5,0
WASH_OLD = (7.0, 17.0, -97.3, -77.3)
TUNNEL = (11.2, 17.0, -92.0, -66.0)
WASH_ROOMS = [("клиент-\nская,\nкасса", 6.8, 11.2, -74.0, -66.0, "pub"), ("бытовка", 6.8, 11.2, -79.0, -74.0, "staff"),
              ("химия", 6.8, 11.2, -83.0, -79.0, "staff"), ("техпом.:\nбойлер,\nнасосы,\nочистные", 6.8, 11.2, -92.0, -83.0, "ctrl")]
WASH_H = 5.0
LANE_ROAD = (21.0, 30.0)
LANE_WALK_W = (17.5, 21.0)
LANE_WALK_E = (30.0, 33.5)
BC13 = (34.0, 49.3, -110.0, -61.0)
VACUUM = (7.0, 13.0, -104.0, -98.0)
TIRE_SHOP = (7.0, 13.1, -112.4, -110.0)


def frame(fig, title: str, sub: str) -> None:
    fig.text(0.012, 0.972, title, fontsize=15, weight="bold", va="top")
    fig.text(0.012, 0.944, sub, fontsize=8.5, color="#444444", va="top")
    fig.text(0.988, 0.012, "«Проспект» · северная сторона проспекта · предложение, редакция 1 · 2026-11-11 · "
             "tools/prospekt_north_side_plan.py", fontsize=7, color="#666666", ha="right", va="bottom")


def callout(ax, x: float, z: float, n: int, color: str = "#b03a2e") -> None:
    ax.add_patch(Circle((x, z), 2.6, fc="white", ec=color, lw=1.1, zorder=50))
    ax.text(x, z, str(n), fontsize=7, weight="bold", color=color, ha="center", va="center", zorder=51)


def rooms(ax, items, fs: float = 6.0, lw: float = 1.3) -> None:
    for label, x0, x1, z0, z1, kind in items:
        rect(ax, (x0, x1, z0, z1), fc=KIND_FC[kind], ec="#1f1f1f", lw=lw, zorder=5)
        ax.text((x0 + x1) * 0.5, (z0 + z1) * 0.5, label, fontsize=fs if (x1 - x0) * (z1 - z0) > 45 else fs - 1.0, ha="center",
                va="center", zorder=20)


def doors(ax, items, color: str = "#1a7f5a") -> None:
    for x, z, axis, width in items:
        if axis == "x":
            ax.add_patch(Rectangle((x - width * 0.5, z - 0.3), width, 0.6, fc="white", ec=color, lw=0.9, zorder=22))
        else:
            ax.add_patch(Rectangle((x - 0.3, z - width * 0.5), 0.6, width, fc="white", ec=color, lw=0.9, zorder=22))


def path(ax, pts, color: str, lw: float = 1.4, ls=(0, (5, 3))) -> None:
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=color, lw=lw, ls=ls, zorder=30, alpha=0.95)
    ax.annotate("", xy=pts[-1], xytext=pts[-2], arrowprops={"arrowstyle": "-|>", "color": color, "lw": lw}, zorder=30)


def car(ax, x: float, z: float, along_x: bool = True, color: str = "#8d99a6", size=(4.5, 1.9)) -> None:
    w, h = size if along_x else (size[1], size[0])
    ax.add_patch(Rectangle((x - w * 0.5, z - h * 0.5), w, h, fc=color, ec="#3f4850", lw=0.4, zorder=12))


def street_base(ax, snap: dict, lim: tuple) -> None:
    """Дорога, тротуары и покрытия из снимка; вещи улицы не рисуются — на их месте предложение."""
    colors = {"road": "#d4d4d4", "walk": "#efece4", "parking": "#e2e2dd", "grass": "#dfe9d2", "court": "#e6d7c3"}
    for s in snap["surfaces"]:
        r = s["rect"]
        if r[2] < lim[0] or r[0] > lim[1] or r[3] < lim[2] or r[1] > lim[3] or s["mat"] not in colors:
            continue
        ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc=colors[s["mat"]], ec="none", zorder=1))
    for radius, color in ((101.95, "#efece4"), (90.15, "#d4d4d4")):
        ax.add_patch(Circle((0.0, 55.0), radius, fc=color, ec="#b0b0b0", lw=0.4, zorder=1.5))
    ax.add_patch(Circle((0.0, 55.0), 51.15, fc="#efece4", ec="#b0b0b0", lw=0.4, zorder=1.6))


def pockets(ax, labels: bool = True, fs: float = 6.0) -> None:
    """Полоса у бордюра: карманы (асфальт), выступы тротуара между ними, остановка."""
    ax.add_patch(Rectangle((-206.0, CURB), 212.0, CURB - LANE_EDGE if False else 2.5, fc="#efece4", ec="none", zorder=3))
    for key, x0, x1, n, note in POCKETS:
        ax.add_patch(Polygon([(x0, CURB), (x0 + 2.5, LANE_EDGE), (x1 - 2.5, LANE_EDGE), (x1, CURB)], closed=True, fc="#c4c4c4",
                             ec="#555555", lw=0.6, zorder=4))
        step = (x1 - x0 - 5.0) / n
        for i in range(1, n):
            ax.plot([x0 + 2.5 + step * i] * 2, [CURB, LANE_EDGE], color="white", lw=0.7, zorder=5)
        if labels:
            ax.text((x0 + x1) * 0.5, CURB + 1.25, key, fontsize=fs, weight="bold", ha="center", va="center", zorder=13, color="#1c1c1c",
                    clip_on=True)
    x0, x1 = BUS_BAY
    ax.add_patch(Polygon([(x0, CURB), (BUS_PLATFORM[0], CURB - 0.5), (BUS_PLATFORM[1], CURB - 0.5), (x1, CURB), (x1, LANE_EDGE),
                          (x0, LANE_EDGE)], closed=True, fc="#c9bfa3", ec="#555555", lw=0.6, zorder=4))
    if labels:
        ax.text(-45.0, -36.5, "остановка «Банк»", fontsize=fs, weight="bold", ha="center", va="center", zorder=13, clip_on=True)
    ax.add_patch(Rectangle((-48.0, -39.8), 6.0, 1.8, fc="#9db4c4", ec="#2f4050", lw=0.6, zorder=12))


# ---------------------------------------------------------------- лист 5: генплан квартала

def sheet_block(snap: dict) -> Path:
    fig = plt.figure(figsize=(16.54, 11.69), dpi=200)
    frame(fig, "Лист 5 · Северная сторона проспекта: квартал от КПП до Банковского переулка",
          "Серое — стоит и остаётся. Цветное и номера — предложение. Красный пунктир — что переезжает. "
          "БЦ «Проспект, 5» с «Зерном» ведёт Codex — здесь не меняется, показан как сосед.")
    lim = (-222.0, 54.0, -162.0, -6.0)
    ax = site_axes(fig, [0.035, 0.215, 0.955, 0.70], lim)
    street_base(ax, snap, lim)
    ax.add_patch(Rectangle((-218.0, -59.3), 220.0, 11.0, fc="#f6f4ee", ec="none", zorder=1.2))
    # забор района и КПП
    ax.plot([-218, 190], [FENCE_N, FENCE_N], color="#333333", lw=1.3, zorder=7)
    ax.plot([-210, -210], [-48.0, -10.0], color="#333333", lw=1.3, zorder=7)
    ax.text(-214.5, -28.0, "КПП ЧВК", fontsize=6.5, rotation=90, ha="center", va="center")
    # паркинг −1 под кварталом
    rect(ax, (-212.4, -42.8, -119.7, -63.9), fc="none", ec="#7a7a7a", lw=0.7, ls=(0, (1, 2)), zorder=6)
    ax.text(-205.5, -66.5, "контур паркинга −1", fontsize=5.5, color="#666666", ha="left", va="center")
    # «Панорама»
    for x0, x1, floors in PANORAMA:
        rect(ax, (x0, x1, PAN_Z[0], PAN_Z[1]), fc="#cfd3d8", ec="#444444", lw=0.9, zorder=8)
        ax.text((x0 + x1) * 0.5, -102.0, "ЖК «Панорама»\n%d эт." % floors, fontsize=6.5, ha="center", va="center", zorder=9)
        ax.add_patch(Rectangle((x0 + 1.0, PAN_Z[1] - 2.2), x1 - x0 - 2.0, 2.2, fc="#e9c46a", ec="#8a6d1c", lw=0.5, zorder=9))
    # первая линия
    for key, label, x0, x1, floors, h, opened in FIRST_LINE:
        rect(ax, (x0, x1, BACK, FACADE), fc="#bcc3cc" if floors > 2 else "#d9dde2", ec="#333333", lw=1.0, zorder=8)
        ax.text((x0 + x1) * 0.5, -53.8, label, fontsize=6.0, ha="center", va="center", zorder=9)
    # перемычки и проходы
    for x0, x1 in ((-163.0, -160.0), (-146.0, -143.0), (-94.0, -92.2)):
        rect(ax, (x0, x1, BACK, FACADE), fc="#bfe3d6", ec="#1a7f5a", lw=1.0, zorder=9)
    # спуск в переход
    rect(ax, UNDERPASS, fc="#9a9a9a", ec="#333333", lw=0.8, hatch="|||", zorder=9)
    ax.text(-156.0, -40.5, "переход", fontsize=5.5, ha="center", va="center", zorder=20,
            bbox={"boxstyle": "round,pad=0.1", "fc": "white", "ec": "none", "alpha": 0.85})
    # въезд во двор
    rect(ax, (DRIVE[0], DRIVE[1], YARD_ROAD[1], CURB), fc="#c4c4c4", ec="#555555", lw=0.6, zorder=3)
    ax.add_patch(Rectangle((-121.0, -62.6), 9.8, 0.5, fc="#c0392b", ec="none", zorder=12))
    ax.add_patch(Rectangle((-123.6, -64.5), 2.4, 2.4, fc="#9aa3ad", ec="#333333", lw=0.5, zorder=12))
    # тылы: служебный проезд и стоянки
    for x0, x1 in LOTS_X:
        rect(ax, (x0, x1, SERVICE[0], SERVICE[1]), fc="#cdcdc8", ec="#555555", lw=0.5, zorder=3)
        rect(ax, (x0, x1, -84.9, SERVICE[0]), fc="#e2e2dd", ec="#777777", lw=0.5, zorder=3)
        for z0, z1 in LOT_ROWS:
            x = x0 + 1.5
            while x < x1 - 2.6:
                ax.add_patch(Rectangle((x, z0), 2.5, z1 - z0, fc="none", ec="#8a8a8a", lw=0.3, zorder=4))
                x += 2.5
    for x in (-185.0, -150.0, -100.0, -66.0):      # контейнерные площадки и ТП в служебном проезде
        ax.add_patch(Rectangle((x, -66.2), 4.0, 2.4, fc="#7d8f6b", ec="#333333", lw=0.5, zorder=12))
    for x in (-134.0, -80.0):
        ax.add_patch(Rectangle((x, -66.2), 4.0, 3.0, fc="#d6c58a", ec="#333333", lw=0.5, zorder=12))
    # двор «Панорамы»: что есть
    rect(ax, (-213.0, -42.0, YARD_ROAD[0], YARD_ROAD[1]), fc="#c4c4c4", ec="#555555", lw=0.5, zorder=3)
    rect(ax, (-170.0, -150.0, -135.3, -121.3), fc="#e6d7c3", ec="#8a6d1c", lw=0.5, zorder=4)
    ax.text(-160.0, -128.3, "площадка", fontsize=5.5, ha="center", va="center")
    for hole in ((-212.3, -203.9, -145.8, -119.7), (-51.3, -42.9, -145.8, -119.7)):
        rect(ax, hole, fc="#9a9a9a", ec="#333333", lw=0.6, hatch="---", zorder=5)
    ax.text(-208.1, -116.0, "спуск −1", fontsize=5.5, ha="center")
    ax.text(-47.1, -116.0, "спуск −1", fontsize=5.5, ha="center")
    # продолжение дворового проезда к переулку и участок за банком
    rect(ax, (-42.0, 21.0, YARD_ROAD[0], YARD_ROAD[1]), fc="#bfe3d6", ec="#1a7f5a", lw=1.0, zorder=4)
    rect(ax, (-40.0, -8.0, -143.0, -103.0), fc="#e2e2dd", ec="#1a7f5a", lw=1.0, zorder=4)
    for z0, z1 in ((-143.0, -137.7), (-124.6, -119.3), (-119.3, -114.0)):
        x = -39.0
        while x < -10.6:
            ax.add_patch(Rectangle((x, z0), 2.5, z1 - z0, fc="none", ec="#8a8a8a", lw=0.3, zorder=5))
            x += 2.5
    rect(ax, (-4.0, 15.0, -136.0, -122.0), fc="#d9c9a8", ec="#6b4e16", lw=1.0, zorder=8)
    ax.text(5.5, -129.0, "ЦТП и\nкотельная", fontsize=6, ha="center", va="center", zorder=9)
    for cx in (9.0, 11.5, 14.0):
        ax.add_patch(Circle((cx, -119.5), 0.7, fc="#777777", ec="#333333", lw=0.4, zorder=9))
    # банк
    rect(ax, BU, fc="#b9c7e6", ec="#1c2f66", lw=1.4, zorder=10)
    rect(ax, B1, fc="none", ec="#1c2f66", lw=0.6, ls=(0, (2, 2)), zorder=11)
    rect(ax, ANNEX, fc="#fdf0c8", ec="#8a6d1c", lw=1.0, zorder=11)
    ax.text(-21.0, -78.0, "банк «Капитал»\n3 эт. + −1 · 13 м\n38 × 34", fontsize=7, weight="bold", ha="center", va="center", zorder=20,
            color="#0f1c40")
    ax.plot([-43, -43, 6, 6], [-61.3, -99.3, -99.3, -52.3], color="#222222", lw=1.0, ls=(0, (3, 1.5)), zorder=12)
    ax.plot([-2, 6], [-52.3, -52.3], color="#222222", lw=1.0, ls=(0, (3, 1.5)), zorder=12)
    for x in range(-40, -1, 3):
        ax.add_patch(Circle((x, -52.8), 0.35, fc="#333333", ec="none", zorder=12))
    # мойка
    rect(ax, WASH_OLD, fc="none", ec="#c0392b", lw=0.9, ls=(0, (4, 3)), zorder=13)
    rect(ax, WASH, fc="#bfe3d6", ec="#1a7f5a", lw=1.3, zorder=12)
    ax.text(11.9, -79.0, "мойка", fontsize=6, rotation=90, ha="center", va="center", zorder=20)
    # переулок и БЦ 13
    rect(ax, BC13, fc="#bcc3cc", ec="#333333", lw=1.0, zorder=8)
    ax.text(41.6, -85.0, "БЦ «Проспект, 13»", fontsize=6, rotation=90, ha="center", va="center", zorder=9)
    ax.text(25.5, -125.0, "Банковский переулок", fontsize=6, rotation=90, ha="center", va="center", color="#555555")
    # тротуар: полоса деревьев и мебели, карманы
    ax.add_patch(Rectangle((-206.0, -40.15), 212.0, 3.5, fc="#e3ead8", ec="none", zorder=2.5))
    pockets(ax)
    for x in TREES_X:
        ax.add_patch(Circle((x, -38.4), 2.2, fc="#a9c98a", ec="#5f7f3f", lw=0.4, zorder=11, alpha=0.9))
    for x in LAMPS_X:
        ax.plot([x], [-37.2], marker="o", ms=3.2, mfc="#ffd24a", mec="#333333", mew=0.5, zorder=12)
    for x in (-51.0, -47.5, -44.0):               # ларьки — в кармане-сквере у остановки
        ax.add_patch(Rectangle((x - 1.5, -46.4), 3.0, 2.4, fc="#c9a27a", ec="#333333", lw=0.4, zorder=12))
    rect(ax, (-57.0, -46.0, -61.3, -47.0), fc="#efe6cf", ec="#8a6d1c", lw=0.6, zorder=2.6)
    # номера
    marks = [(-178.0, -66.0, 1), (-161.5, -63.0, 2), (-144.5, -63.0, 2), (-116.0, -70.0, 3), (-160.0, -62.8, 0), (-150.0, -76.0, 5),
             (-118.0, -85.0, 6), (-179.0, -28.5, 7), (-142.0, -28.5, 7), (-88.0, -28.5, 7), (-10.0, -28.5, 7), (-45.0, -28.5, 8),
             (-120.0, -28.5, 9), (-90.0, -41.0, 10), (-51.5, -56.0, 11), (-21.0, -56.5, 12), (2.0, -70.0, 13), (-41.5, -86.0, 14),
             (12.0, -57.0, 15), (-10.0, -149.3, 16), (-24.0, -130.0, 17), (5.5, -139.5, 18), (-135.0, -63.0, 4)]
    for x, z, n in marks:
        if n:
            callout(ax, x, z, n)
    dim(ax, (-200.0, CURB), (-200.0, WALK[0]), off=0.0, fs=6)
    dim(ax, (-198.0, BACK), (-198.0, SERVICE[0]), off=0.0, fs=6)
    dim(ax, (-59.8, -44.0), (-43.0, -44.0), off=-2.0, fs=6)
    dim(ax, (6.0, -47.5), (17.5, -47.5), off=2.0, fs=6)
    north_arrow(ax, 46.0, -14.0, 8.0)
    scale_bar(ax, -30.0, -12.0)
    legend = [
        "1 · БЦ «Проспект, 5» с «Зерном» и цветами — ведёт Codex, не меняется.",
        "2 · Щели по 3 м между павильонами закрыты перемычками на 2-м этаже: аптека и «Modus» читаются одной торговой галереей, "
        "внизу остаются проходы к стоянке (арки). Пекарня примыкает к БЦ 11.",
        "3 · Въезд во двор: проезжая часть 7,8 м с двумя тротуарами, шлагбаум и будка в 15 м от дороги.",
        "4 · ТП первой линии — в служебном проезде (жёлтые); будки с разделительной полосы уходят.",
        "5 · Служебный проезд 7,2 м за первой линией: разгрузочные двери, контейнерные площадки (зелёные), наружные блоки, "
        "лестницы на крыши. Стоянка: два ряда по 5,3 м и проезд 7,8 м, около 100 мест.",
        "6 · Первый этаж «Панорамы» со стороны стоянки — нежилые помещения с вывесками (жёлтая полоса), закрыты.",
        "7 · Карманы у бордюра вместо сплошной полосы: К1 — 3 места, К2 — погрузка 12 м, К3 — 4 места, К5 — высадка у банка; "
        "место вдоль бордюра 6,9–7,0 × 2,5 м, скосы по 2,5 м.",
        "8 · Остановка троллейбуса «Банк»: карман 52 м (площадка 26 м, отгоны по 13 м), павильон, ларьки рядом.",
        "9 · Выступы тротуара на ширину кармана: у спуска в переход, у зебры и въезда, у ворот инкассации.",
        "10 · Полоса деревьев и мебели 3,5 м у бордюра: деревья через 14 м, фонари, скамьи, урны, велопарковки; у фасадов — "
        "свободная полоса 6,8 м. Столбики остаются только на выступах.",
        "11 · Проход к стоянке между БЦ 11 и банком: мощёная дорожка, ларьки у остановки (сейчас газон).",
        "12 · Банк: открытая площадь перед входом, противотаранные столбики; забор — вокруг служебных дворов.",
        "13 · Бокс инкассации — пристройка у восточной стены, въезд через ворота с будкой (лист 7).",
        "14 · Служебный вход, наружная пожарная лестница до 3-го этажа и крыши; ДГУ и баки — за банком.",
        "15 · Автомойка «Блеск» — на углу переулка: въезд с севера, выезд к проспекту (лист 8).",
        "16 · Дворовый проезд продлён за банком до переулка: у квартала второй выезд, у восточного спуска −1 — подъезд.",
        "17 · Служебная стоянка банка и бизнес-центров за банком (36 мест), калитка из двора банка.",
        "18 · ЦТП и котельная квартала с тремя трубами — на пустыре у переулка: ориентир и перебивка обзора.",
    ]
    lines = []
    for item in legend:
        lines += textwrap.wrap(item, 88, subsequent_indent="      ")
    third = math.ceil(len(lines) / 3)
    for i in range(3):
        fig.text(0.035 + i * 0.322, 0.185, "\n".join(lines[i * third:(i + 1) * third]), fontsize=6.8, va="top", linespacing=1.42)
    path_ = OUT / "prospekt_north_5_block.png"
    fig.savefig(path_)
    plt.close(fig)
    return path_


# ---------------------------------------------------------------- лист 6: развёртка, профиль, карманы

def sheet_street(snap: dict) -> Path:
    fig = plt.figure(figsize=(16.54, 11.69), dpi=200)
    frame(fig, "Лист 6 · Развёртка северной стороны, поперечный профиль квартала, карманы и тротуар",
          "Развёртка — вид с проспекта на север. Профиль — разрез по X = −153 (через аптеку), юг слева. "
          "Высоты первой линии прежние; меняется то, что между домами и за ними.")
    # --- развёртка
    ax = fig.add_axes([0.035, 0.615, 0.955, 0.29])
    ax.set_xlim(-222, 54)
    ax.set_ylim(-3, 58)
    ax.set_aspect("equal")
    ax.set_ylabel("высота, м", fontsize=7)
    ax.tick_params(labelsize=6.5)
    ax.set_yticks(range(0, 56, 10))
    ax.grid(True, axis="y", color="#aaaaaa", lw=0.25, zorder=0)
    ax.add_patch(Rectangle((-222, -3), 276, 3, fc="#d9d9d9", ec="none", zorder=1))
    for x0, x1, floors in PANORAMA:                # второй план
        ax.add_patch(Rectangle((x0, 0), x1 - x0, 58.0, fc="#e6e8ea", ec="#b5b9be", lw=0.6, zorder=2))
        floors_lines(ax, x0, x1, 0, 58.0, 3.105, "#c5c9ce", 0.2)
        ax.text((x0 + x1) * 0.5, 52.0, "«Панорама» %d эт. · %d м" % (floors, round(floors * 3.105)), fontsize=6, color="#777777", ha="center",
                bbox={"boxstyle": "round,pad=0.1", "fc": "white", "ec": "none", "alpha": 0.8})
    for key, label, x0, x1, floors, h, opened in FIRST_LINE:
        ax.add_patch(Rectangle((x0, 0), x1 - x0, 8.0, fc="#d9dde2", ec="#333333", lw=0.9, zorder=6))
        ax.plot([x0, x1], [4.0, 4.0], color="#555555", lw=0.4, zorder=7)
        if floors > 2:
            ax.add_patch(Rectangle((x0 + (3.6 if key == "bc5" else 0.0), 8.0), x1 - x0 - (3.6 if key == "bc5" else 0.0), h - 8.0,
                                   fc="#aebbd0", ec="#1c2f66", lw=0.9, zorder=6))
            floors_lines(ax, x0 + (3.6 if key == "bc5" else 0.0), x1, 8.0, h, 3.6, "#5a6b8c", 0.3)
        ax.text((x0 + x1) * 0.5, h + 1.6 if floors > 2 else 14.6, label.split("\n")[0], fontsize=6.3, ha="center", zorder=20)
    for x0, x1 in ((-163.0, -160.0), (-146.0, -143.0)):                    # перемычки с арками
        ax.add_patch(Rectangle((x0, 4.0), x1 - x0, 4.0, fc="#bfe3d6", ec="#1a7f5a", lw=0.9, zorder=7))
    ax.add_patch(Rectangle((-94.0, 0), 1.8, 8.0, fc="#bfe3d6", ec="#1a7f5a", lw=0.9, zorder=7))
    ax.add_patch(Rectangle((-123.0, 4.6), 15.0, 1.2, fc="#bfe3d6", ec="#1a7f5a", lw=0.9, zorder=7))
    ax.text(-115.5, 9.5, "въезд во двор\nворота 4,6 м", fontsize=5.5, ha="center", va="center", color="#0d4a33")
    # банк
    ax.add_patch(Rectangle((-38.0, 0), 34.0, 4.5, fc="#8f9aa8", ec="#333333", lw=0.8, zorder=6))
    ax.add_patch(Rectangle((-40.0, 4.2), 38.0, 9.1, fc="#e9e6dc", ec="#1c2f66", lw=1.0, zorder=7))
    x = -40.0
    while x < -2.1:
        ax.plot([x, x + 3.8], [4.2, 13.3], color="#8a8f99", lw=0.5, zorder=8)
        ax.plot([x + 3.8, x], [4.2, 13.3], color="#8a8f99", lw=0.5, zorder=8)
        x += 3.8
    ax.add_patch(Rectangle((-23.5, 0), 5.0, 3.4, fc="#bfe3d6", ec="#1a7f5a", lw=0.8, zorder=9))
    ax.add_patch(Rectangle((-4.0, 0), 6.4, 4.2, fc="#fdf0c8", ec="#8a6d1c", lw=0.8, zorder=6))
    ax.text(-21.0, 15.0, "банк «Капитал» · 13 м", fontsize=6.3, ha="center", zorder=20)
    ax.add_patch(Rectangle((6.8, 0), 10.2, WASH_H, fc="#bfe3d6", ec="#1a7f5a", lw=0.9, zorder=6))
    ax.add_patch(Rectangle((12.1, 0), 4.0, 3.6, fc="#5c7186", ec="none", zorder=7))
    ax.plot([16.6, 16.6], [0, 9.0], color="#333333", lw=1.0, zorder=7)
    ax.add_patch(Rectangle((15.4, 6.2), 2.4, 2.8, fc="#2b6cb0", ec="none", zorder=8))
    ax.text(11.9, 10.6, "мойка 5 м", fontsize=6, ha="center")
    ax.add_patch(Rectangle((34.0, 0), 15.3, 32.4, fc="#aebbd0", ec="#1c2f66", lw=0.9, zorder=6))
    floors_lines(ax, 34.0, 49.3, 0, 32.4, 3.6, "#5a6b8c", 0.3)
    ax.text(41.6, 34.0, "БЦ 13 · 32 м", fontsize=6.3, ha="center")
    for x in TREES_X:
        ax.plot([x, x], [0, 6.5], color="#6b4a2a", lw=0.8, zorder=10)
        ax.add_patch(Circle((x, 9.5), 3.6, fc="#a9c98a", ec="#5f7f3f", lw=0.4, zorder=10, alpha=0.75))
    ax.add_patch(Rectangle((-48.0, 0), 6.0, 2.8, fc="#9db4c4", ec="#2f4050", lw=0.6, zorder=11))
    for x in (-180.0, -150.0, -100.0, -60.0, -30.0, 0.0):
        figure_man(ax, x)
    # --- поперечный профиль квартала по X = −153
    axp = fig.add_axes([0.035, 0.08, 0.53, 0.44])
    axp.set_xlim(-8, -160)
    axp.set_ylim(-9, 58)
    axp.set_aspect("equal")
    axp.set_title("поперечный профиль квартала: от разделительной до забора района", fontsize=9.5, loc="left")
    axp.set_xlabel("Z, м (проспект слева, забор справа)", fontsize=7)
    axp.tick_params(labelsize=6.5)
    axp.set_xticks(range(-10, -161, -10))
    axp.set_yticks([-7, 0, 8, 20, 40, 53])
    axp.grid(True, axis="y", color="#aaaaaa", lw=0.25, zorder=0)
    axp.add_patch(Rectangle((-160, -9), 152, 9, fc="#d9d9d9", ec="none", zorder=1))
    axp.add_patch(Rectangle((-119.7, -7.3), 55.8, 6.9, fc="#f2f2f2", ec="#666666", lw=0.6, zorder=2))
    axp.text(-92.0, -4.0, "паркинг −1 · 6 м в свету", fontsize=6, ha="center", va="center")
    axp.add_patch(Rectangle((-59.3, 0), 11.0, 8.0, fc="#d9dde2", ec="#333333", lw=0.9, zorder=5))
    axp.plot([-59.3, -48.3], [4.0, 4.0], color="#555555", lw=0.4, zorder=6)
    axp.text(-53.8, 9.6, "аптека\n8 м", fontsize=6, ha="center")
    axp.add_patch(Rectangle((-113.3, 0), 26.0, 52.8, fc="#cfd3d8", ec="#444444", lw=0.9, zorder=5))
    floors_lines(axp, -113.3, -87.3, 0, 52.8, 3.105, "#9aa0a8", 0.25)
    axp.add_patch(Rectangle((-89.5, 0), 2.2, 3.1, fc="#e9c46a", ec="#8a6d1c", lw=0.5, zorder=6))
    axp.text(-100.3, 54.5, "«Панорама» 17 эт. · 53 м", fontsize=6.3, ha="center")
    axp.plot([FENCE_N, FENCE_N], [0, 3.2], color="#333333", lw=1.6, zorder=6)
    axp.plot([-38.4, -38.4], [0, 6.5], color="#6b4a2a", lw=0.9, zorder=6)
    axp.add_patch(Circle((-38.4, 9.5), 3.6, fc="#a9c98a", ec="#5f7f3f", lw=0.4, zorder=6, alpha=0.8))
    axp.add_patch(Rectangle((-34.8, 0), 1.9, 1.5, fc="#8d99a6", ec="#3f4850", lw=0.4, zorder=6))
    for z0, z1 in LOT_ROWS:
        axp.add_patch(Rectangle((z0 + 0.4, 0), 4.5, 1.5, fc="#8d99a6", ec="#3f4850", lw=0.4, zorder=6))
    figure_man(axp, -43.0)
    figure_man(axp, -63.0)
    figure_man(axp, -130.0)
    bands = [(-12.65, -18.65, "раздели-\nтельная\n6,0"), (-18.65, -32.65, "4 полосы\n14,0"), (-32.65, -35.15, "кар-\nман\n2,5"),
             (-35.15, -46.95, "тротуар\n11,8"), (-48.3, -59.3, "первая\nлиния\n11,0"), (-59.3, -66.5, "служеб-\nный\n7,2"),
             (-66.5, -84.9, "стоянка\n2 ряда\n18,4"), (-87.3, -113.3, "жилой дом\n26,0"), (-113.3, -145.8, "двор: площадка,\nгаражи, ТП\n32,5"),
             (-145.8, -152.8, "проезд\n7,0")]
    for z0, z1, label in bands:
        axp.plot([z0, z0], [0, 30.0], color="#c0392b", lw=0.4, ls=(0, (3, 3)), zorder=3)
        axp.plot([z1, z1], [0, 30.0], color="#c0392b", lw=0.4, ls=(0, (3, 3)), zorder=3)
        axp.text((z0 + z1) * 0.5, 24.0 if abs(z1 - z0) < 8 else 19.0, label, fontsize=5.6, ha="center", va="center", zorder=20,
                 bbox={"boxstyle": "round,pad=0.1", "fc": "white", "ec": "none", "alpha": 0.9})
    # --- карманы: план полосы у бордюра
    axk = fig.add_axes([0.60, 0.335, 0.39, 0.185])
    axk.set_xlim(-112, -12)
    axk.set_ylim(-28.5, -49.5)
    axk.set_aspect("equal")
    axk.set_title("полоса у бордюра: карман К3, остановка «Банк», карман К5 (план)", fontsize=9.5, loc="left")
    axk.tick_params(labelsize=6)
    axk.set_xticks(range(-110, -11, 10))
    axk.set_yticks([-46.95, -40.15, -35.15, -32.65])
    axk.add_patch(Rectangle((-112, -32.65), 100, 4.2, fc="#d4d4d4", ec="none", zorder=1))
    axk.add_patch(Rectangle((-112, -46.95), 100, 11.8, fc="#efece4", ec="none", zorder=1))
    axk.add_patch(Rectangle((-112, -49.5), 100, 2.55, fc="#d9dde2", ec="none", zorder=1))
    axk.add_patch(Rectangle((-112, -40.15), 100, 3.5, fc="#e3ead8", ec="none", zorder=2))
    pockets(axk, labels=True, fs=6.5)
    for x in (-98.0, -91.5, -85.0, -78.5):
        car(axk, x, -33.9)
    car(axk, -12.0 - 2.0, -33.9)
    axk.add_patch(Rectangle((-51.0, -34.3), 12.0, 2.6, fc="#e0b030", ec="#7a5a00", lw=0.5, zorder=12))
    for x in TREES_X:
        if -112 < x < -12:
            axk.add_patch(Circle((x, -38.4), 2.0, fc="#a9c98a", ec="#5f7f3f", lw=0.4, zorder=11, alpha=0.9))
    for x in LAMPS_X:
        if -112 < x < -12:
            axk.plot([x], [-37.2], marker="o", ms=3.5, mfc="#ffd24a", mec="#333333", mew=0.5, zorder=12)
    dim(axk, (-104.0, -30.6), (-71.5, -30.6), off=-1.1, fs=6)
    dim(axk, (-71.0, -30.6), (-58.0, -30.6), off=-1.1, fs=6)
    dim(axk, (-58.0, -30.6), (-32.0, -30.6), off=-1.1, fs=6)
    dim(axk, (-32.0, -30.6), (-19.0, -30.6), off=-1.1, fs=6)
    axk.text(-88.0, -44.0, "свободная полоса у фасадов 6,8 м", fontsize=6, ha="center", va="center")
    axk.text(-88.0, -48.2, "фасады первой линии", fontsize=6, ha="center", va="center")
    # --- тротуар крупно: разрез
    axs = fig.add_axes([0.60, 0.08, 0.39, 0.19])
    axs.set_xlim(-17, -50.5)
    axs.set_ylim(-1.2, 10.2)
    axs.set_aspect("equal")
    axs.set_title("тротуар и карман крупно (разрез, проспект слева)", fontsize=9.5, loc="left")
    axs.tick_params(labelsize=6)
    axs.set_xticks([-18.65, -32.65, -35.15, -36.65, -40.15, -46.95, -48.3])
    axs.set_xticklabels(["−18,7", "−32,7", "−35,2", "−36,7", "−40,2", "−47,0", "−48,3"])
    axs.set_yticks([0, 4, 8])
    axs.add_patch(Rectangle((-50.5, -1.2), 33.5, 1.2, fc="#d9d9d9", ec="none", zorder=1))
    axs.add_patch(Rectangle((-35.15, -0.15), 17.65, 0.15, fc="#777777", ec="none", zorder=2))
    axs.add_patch(Rectangle((-50.5, 0), 2.2, 8.0, fc="#d9dde2", ec="#333333", lw=0.9, zorder=5))
    axs.add_patch(Rectangle((-48.3, 2.9), 1.3, 0.2, fc="#555555", ec="none", zorder=6))
    axs.add_patch(Rectangle((-34.85, 0.05), 1.9, 1.45, fc="#8d99a6", ec="#3f4850", lw=0.5, zorder=6))
    axs.add_patch(Rectangle((-31.9, 0.05), 2.5, 3.1, fc="#e0b030", ec="#7a5a00", lw=0.5, zorder=6))
    axs.plot([-38.4, -38.4], [0, 5.2], color="#6b4a2a", lw=1.4, zorder=6)
    axs.add_patch(Circle((-38.4, 7.4), 2.2, fc="#a9c98a", ec="#5f7f3f", lw=0.5, zorder=6, alpha=0.85))
    axs.plot([-37.2, -37.2], [0, 5.6], color="#444444", lw=1.1, zorder=7)
    axs.plot([-37.2, -36.2], [5.6, 5.6], color="#444444", lw=1.1, zorder=7)
    axs.plot([-36.0, -36.0], [0, 9.0], color="#444444", lw=1.4, zorder=7)
    axs.plot([-36.0, -30.9], [8.6, 8.6], color="#444444", lw=0.6, zorder=7)
    axs.add_patch(Rectangle((-39.9, 0), 1.6, 0.45, fc="#8a6d1c", ec="none", zorder=7))
    figure_man(axs, -43.5)
    figure_man(axs, -45.0)
    for x0, x1, label in ((-48.3, -46.95, "у фасада\n1,35"), (-46.95, -40.15, "свободная полоса\n6,8"), (-40.15, -36.65, "деревья, мебель\n3,5"),
                          (-36.65, -35.15, "край\n1,5"), (-35.15, -32.65, "карман\n2,5"), (-32.65, -18.65, "4 полосы · 14,0")):
        axs.plot([x0, x0], [0, 4.4], color="#c0392b", lw=0.4, ls=(0, (3, 3)), zorder=3)
        axs.text((x0 + x1) * 0.5, 4.1 if x1 - x0 > 2 else 5.4, label, fontsize=5.6, ha="center", va="center", zorder=20,
                 bbox={"boxstyle": "round,pad=0.08", "fc": "white", "ec": "none", "alpha": 0.9})
    path_ = OUT / "prospekt_north_6_street.png"
    fig.savefig(path_)
    plt.close(fig)
    return path_


# ---------------------------------------------------------------- лист 7: банк

def bank_shell(ax, upper: bool) -> None:
    if upper:
        rect(ax, BU, fc="#ffffff", ec="#111111", lw=2.0, zorder=4)
    else:
        rect(ax, B1, fc="#ffffff", ec="#111111", lw=2.0, zorder=4)
        rect(ax, BU, fc="none", ec="#1c2f66", lw=0.7, ls=(0, (6, 3)), zorder=24)


def small_axes(fig, pos, title: str) -> plt.Axes:
    ax = fig.add_axes(pos)
    ax.set_xlim(-45.5, 4.5)
    ax.set_ylim(-58.5, -99.5)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=9, loc="left", pad=3)
    ax.set_xticks(range(-40, 1, 10))
    ax.set_yticks(range(-95, -59, 10))
    ax.tick_params(labelsize=5.5, length=2)
    ax.grid(True, color="#bbbbbb", lw=0.2, zorder=0)
    return ax


def sheet_bank(snap: dict) -> Path:
    fig = plt.figure(figsize=(16.54, 11.69), dpi=200)
    frame(fig, "Лист 7 · Банк «Капитал»: участок и этажи",
          "Габариты, место, ядро Л1, лестница Л2, кладовая у западной стены и подкоп — как в сцене. Меняется планировка: "
          "зоны клиентов (голубое), персонала (светлое), денег (жёлтое), контроля (розовое). Пунктир — контур нависающих этажей.")
    # --- участок и первый этаж
    lim = (-48.0, 10.0, -104.0, -46.0)
    ax = site_axes(fig, [0.035, 0.215, 0.475, 0.665], lim, grid=5)
    ax.set_title("участок и 1-й этаж · отметка 0,0 · высота этажа 4,5 м", fontsize=9.5, loc="left", pad=20)
    ax.add_patch(Rectangle((lim[0], WALK[0]), lim[1] - lim[0], 0.95, fc="#efece4", ec="none", zorder=1))
    ax.add_patch(Rectangle((-43.0, -99.3), 49.0, 47.0, fc="#f1eee6", ec="none", zorder=1))
    ax.add_patch(Rectangle((-48.0, -104.0), 58.0, 4.7, fc="#e9efe1", ec="none", zorder=1))
    ax.text(-36.0, -47.3, "тротуар проспекта", fontsize=7, color="#666666", ha="center", va="center")
    ax.text(-21.0, -57.0, "площадь перед банком\n38 × 9, открыта к улице", fontsize=7, color="#555555", ha="center", va="center")
    bank_shell(ax, False)
    rooms(ax, BANK_F1, fs=6.4)
    doors(ax, DOORS_F1)
    # стойка операционистов
    ax.add_patch(Rectangle((-31.0, -78.8), 13.0, 1.0, fc="#c9a27a", ec="#333333", lw=0.6, zorder=21))
    ax.text(-24.5, -76.6, "стойка · 4 окна", fontsize=5.4, ha="center", va="center", zorder=23)
    for x in (-36.8, -34.4, -32.0):
        ax.add_patch(Rectangle((x - 0.45, -70.0), 0.9, 0.9, fc="#5c7186", ec="none", zorder=21))
    # опоры под нависанием
    for x in (-39.4, -31.0, -21.0, -11.0, -2.6):
        ax.add_patch(Rectangle((x - 0.35, -62.25), 0.7, 0.7, fc="#222222", ec="none", zorder=21))
    for z in (-69.3, -77.3, -85.3, -91.3):
        for x in (-39.4, -2.6):
            ax.add_patch(Rectangle((x - 0.35, z - 0.35), 0.7, 0.7, fc="#222222", ec="none", zorder=21))
    # забор служебных дворов
    ax.plot([-43, -43, 6, 6, -2], [-61.3, -99.3, -99.3, -52.3, -52.3], color="#222222", lw=1.4, ls=(0, (3, 1.5)), zorder=12)
    ax.plot([-43, -40], [-61.3, -61.3], color="#222222", lw=1.4, ls=(0, (3, 1.5)), zorder=12)
    ax.plot([-2, -2], [-61.3, -52.3], color="#222222", lw=1.4, ls=(0, (3, 1.5)), zorder=12)
    for x in [v * 1.6 - 40.0 for v in range(0, 24)]:
        ax.add_patch(Circle((x, -52.8), 0.22, fc="#333333", ec="none", zorder=12))
    ax.text(-30.0, -51.2, "противотаранные столбики через 1,6 м", fontsize=5.6, ha="center", va="center")
    for x in (-35.0, -32.0, -29.0):
        ax.plot([x], [-54.8], marker="o", ms=3, mfc="white", mec="#333333", zorder=12)
    ax.add_patch(Rectangle((-9.0, -51.6), 1.2, 0.5, fc="#2b6cb0", ec="none", zorder=12))
    ax.text(-8.4, -50.4, "стела", fontsize=5.4, ha="center")
    # наружная лестница, служебный вход, ДГУ, баки
    ax.add_patch(Rectangle((-42.75, -77.3), 1.95, 14.5, fc="#dddddd", ec="#333333", lw=0.7, zorder=10))
    for i in range(12):
        ax.plot([-42.75, -40.8], [-63.4 - i * 0.75] * 2, color="#666666", lw=0.4, zorder=11)
    ax.text(-44.6, -70.0, "наружная лестница: 2-й, 3-й этаж, крыша", fontsize=5.6, rotation=90, ha="center", va="center")
    ax.add_patch(Rectangle((-12.0, -98.4), 6.1, 2.4, fc="#8c9a7b", ec="#333333", lw=0.6, zorder=10))
    ax.text(-9.0, -97.2, "ДГУ", fontsize=5.6, ha="center", va="center", zorder=20)
    for x in (-36.0, -33.6):
        ax.add_patch(Rectangle((x, -98.4), 2.0, 1.4, fc="#7d8f6b", ec="#333333", lw=0.5, zorder=10))
    ax.text(-34.0, -100.6, "баки, калитка к служебной стоянке", fontsize=5.6, ha="center", va="center")
    ax.add_patch(Rectangle((2.6, -56.4), 2.2, 2.2, fc="#9aa3ad", ec="#333333", lw=0.5, zorder=12))
    ax.add_patch(Rectangle((-1.6, -52.6), 5.6, 0.5, fc="#c0392b", ec="none", zorder=12))
    ax.text(4.0, -58.0, "будка", fontsize=5.4, ha="center")
    ax.text(2.2, -63.5, "двор\nинкассации", fontsize=6, ha="center", va="center", color="#555555")
    car(ax, 2.0, -72.5, along_x=False, color="#b8a34a", size=(6.0, 2.4))
    rect(ax, (6.8, 10.0, -92.0, -66.0), fc="#bfe3d6", ec="#1a7f5a", lw=1.0, zorder=5)
    ax.text(8.4, -79.0, "мойка", fontsize=6, rotation=90, ha="center", va="center")
    # пути
    path(ax, [(-21.0, -49.0), (-21.0, -66.8), (-21.0, -72.0), (-24.5, -76.4)], "#2b6cb0")
    path(ax, [(-21.0, -72.0), (-12.5, -73.5), (-8.5, -74.8)], "#2b6cb0")
    path(ax, [(2.0, -49.5), (2.0, -76.0), (-0.8, -82.0), (-0.8, -85.0), (-7.5, -85.0), (-7.5, -90.6), (-12.0, -91.3)], "#b5651d")
    path(ax, [(-46.0, -91.2), (-39.5, -91.2), (-36.0, -91.2)], "#555555")
    dim(ax, (-38.0, -102.0), (-4.0, -102.0), off=-1.2, fs=6)
    dim(ax, (8.0, -93.3), (8.0, -65.3), off=0.0, fs=6)
    dim(ax, (-21.0, -65.3), (-21.0, -52.3), text="13,0", off=3.4, fs=6)
    dim(ax, (-4.0, -95.6), (2.4, -95.6), off=-1.2, fs=6)
    north_arrow(ax, -45.0, -49.0, 3.0)
    scale_bar(ax, -14.0, -48.4, meters=20, step=5, k=0.4)
    # --- малые планы
    a1 = small_axes(fig, [0.545, 0.59, 0.215, 0.31], "−1 · отметка −3,2 · высота 2,8 м")
    bank_shell(a1, False)
    rooms(a1, BANK_B1, fs=5.6, lw=1.0)
    doors(a1, DOORS_B1)
    for z0, z1 in ((-89.3, -77.9), (-76.7, -67.3)):               # толстая стена кладовой
        a1.add_patch(Rectangle((-24.4, z0), 0.8, z1 - z0, fc="#333333", ec="none", zorder=21))
    a1.add_patch(Rectangle((-38.4, -89.3), 0.8, 14.0, fc="#333333", ec="none", zorder=21))
    a1.add_patch(Rectangle((-38.4, -73.3), 0.8, 6.0, fc="#333333", ec="none", zorder=21))
    a1.add_patch(Rectangle((-45.5, -75.3), 7.1, 2.0, fc="#b9906a", ec="#6b4a2a", lw=0.6, zorder=6))
    a1.text(-42.0, -77.0, "подкоп\nиз паркинга", fontsize=5.2, ha="center", va="center", color="#6b4a2a")
    a1.text(-21.0, -62.4, "решётка кладовой (X −24; Z −77,3): ключ-карта и питание", fontsize=5.2, ha="center", va="center",
            color="#b03a2e", zorder=25)
    path(a1, [(-45.0, -74.3), (-36.0, -74.3)], "#b03a2e", lw=1.1)
    path(a1, [(-10.0, -91.6), (-18.0, -91.6), (-22.5, -91.0), (-22.5, -78.5), (-26.0, -77.3)], "#b5651d", lw=1.1)
    path(a1, [(-7.5, -76.5), (-9.0, -75.0), (-14.0, -73.0)], "#2b6cb0", lw=1.1)
    a2 = small_axes(fig, [0.775, 0.59, 0.215, 0.31], "2-й этаж · +4,5 · кредитный отдел и бэк-офис")
    bank_shell(a2, True)
    rooms(a2, BANK_F2, fs=5.6, lw=1.0)
    doors(a2, DOORS_F2)
    a2.add_patch(Rectangle((-42.75, -82.6), 2.75, 5.3, fc="#dddddd", ec="#333333", lw=0.6, zorder=6))
    a3 = small_axes(fig, [0.545, 0.245, 0.215, 0.31], "3-й этаж · +8,4 · дирекция")
    bank_shell(a3, True)
    rooms(a3, BANK_F3, fs=5.6, lw=1.0)
    doors(a3, DOORS_F3)
    a3.add_patch(Rectangle((-42.75, -82.6), 2.75, 5.3, fc="#dddddd", ec="#333333", lw=0.6, zorder=6))
    a4 = small_axes(fig, [0.775, 0.245, 0.215, 0.31], "крыша · +12,3 · парапет 1,0 м")
    rect(a4, BU, fc="#ecebe6", ec="#111111", lw=2.0, zorder=4)
    rect(a4, (-38.2, -28.0, -95.0, -89.1), fc="#dddddd", ec="#111111", lw=1.0, zorder=5)
    a4.text(-33.1, -92.0, "будка Л1", fontsize=5.6, ha="center", va="center", zorder=20)
    rect(a4, (-24.0, -8.0, -93.5, -89.5), fc="#c9d3ea", ec="#333333", lw=0.7, zorder=5)
    a4.text(-16.0, -91.5, "венткамера, чиллеры", fontsize=5.6, ha="center", va="center", zorder=20)
    a4.add_patch(Rectangle((-42.75, -82.6), 2.75, 5.3, fc="#dddddd", ec="#333333", lw=0.6, zorder=6))
    a4.text(-36.0, -79.9, "выход наружной\nлестницы", fontsize=5.2, ha="left", va="center", zorder=20)
    a4.add_patch(Rectangle((-26.0, -63.8), 12.0, 1.6, fc="#b8a98a", ec="#333333", lw=0.6, zorder=6))
    a4.text(-20.0, -66.3, "лёжка к проспекту (мешки)", fontsize=5.6, ha="center", va="center", zorder=20)
    a4.plot([-6.0], [-89.3], marker="x", ms=5, color="#333333")
    a4.text(-6.0, -86.8, "антенна", fontsize=5.2, ha="center", zorder=20)
    a4.add_patch(Rectangle((-13.0, -82.0), 2.0, 2.0, fc="#fdf0c8", ec="#8a6d1c", lw=0.6, zorder=6))
    a4.text(-12.0, -78.8, "тайник", fontsize=5.2, ha="center", zorder=20)
    # --- подписи
    notes_l = [
        "Что стоит на месте: габарит 34 × 28 (верх 38 × 34), три этажа и −1, высоты этажей, ядро Л1 в северо-западном углу,",
        "лестница Л2 на −1, кладовая у западной стены, подкоп, решётка в толстой стене, крыша с будкой.",
        "",
        "Что меняется на 1-м этаже и почему:",
        " • тамбур и зона 24/7 с отдельной дверью — банкоматы работают, когда банк закрыт;",
        " • зал стал 20 × 13: очередь, менеджеры у окон, стойка на 4 окна, две кабины касс за дверями;",
        " • клиент спускается к ячейкам по своей лестнице Л3 мимо поста — не через служебную зону;",
        " • деньги идут отдельно: ворота → двор → бокс инкассации (ворота закрываются) → касса пересчёта → Л2 → кладовая;",
        " • восточная дверь из зала убрана: сейчас мешки несут через зал с клиентами;",
        " • служебный вход с запада сразу к Л1 и охране; у охраны мониторы и комната хранения оружия.",
    ]
    notes_r = [
        "Пути: синий — клиент, оранжевый — деньги, серый — персонал, красный — подкоп.",
        "",
        "Входы для игрока — восемь: главный вход, дверь зоны 24/7, служебная западная, задняя дверь охраны,",
        "ворота бокса инкассации, наружная лестница (двери 2-го и 3-го этажа, крыша), подкоп из паркинга −1.",
        "",
        "На −1 три независимых спуска: Л2 (служебная), Л3 (клиентская), подкоп. Решётка кладовой — по ключ-карте",
        "из службы безопасности на 3-м этаже и при питании от подстанции; без них — только подкопом.",
        "",
        "Размер: 34 × 28 по правилу × 1,3 — это настоящие 26 × 21,5 м, обычное отделение-офис в три этажа.",
        "Кладовая 14 × 22 втрое больше настоящей — оставлена как зал финала.",
        "Вопрос владельцу: забор перед входом. Решение от 24.10 — «обнести забором»; на чертеже забор только",
        "вокруг служебных дворов, перед входом — открытая площадь со столбиками. Вернуть забор по фасаду — одна линия.",
    ]
    fig.text(0.035, 0.175, "\n".join(notes_l), fontsize=6.9, va="top", linespacing=1.42)
    fig.text(0.545, 0.215, "\n".join(notes_r), fontsize=6.9, va="top", linespacing=1.42)
    path_ = OUT / "prospekt_north_7_bank.png"
    fig.savefig(path_)
    plt.close(fig)
    return path_


# ---------------------------------------------------------------- лист 8: мойка, переулок, разрез банка

def sheet_wash(snap: dict) -> Path:
    fig = plt.figure(figsize=(16.54, 11.69), dpi=200)
    frame(fig, "Лист 8 · Автомойка «Блеск» и Банковский переулок; разрез банка",
          "Мойка переезжает на 8,5 м к проспекту и становится проездной: въезд с севера, выезд к углу. "
          "Красный пунктир — где она стоит сейчас (глухая коробка 10 × 20 без ворот).")
    lim = (-8.0, 40.0, -124.0, -46.0)
    ax = site_axes(fig, [0.035, 0.05, 0.37, 0.86], lim, grid=5)
    ax.add_patch(Rectangle((lim[0], -59.3), lim[1] - lim[0], 13.3, fc="#efece4", ec="none", zorder=1))
    ax.add_patch(Rectangle((6.0, -124.0), 11.5, 64.7, fc="#d4d4d4", ec="none", zorder=1))
    ax.add_patch(Rectangle((LANE_ROAD[0], -124.0), 9.0, 66.0, fc="#c4c4c4", ec="none", zorder=1))
    for w in (LANE_WALK_W, LANE_WALK_E):
        ax.add_patch(Rectangle((w[0], -124.0), w[1] - w[0], 66.0, fc="#efece4", ec="#999999", lw=0.4, zorder=2))
    for z0, z1 in ((-104.0, -96.0), (-66.0, -60.0)):              # съезды через тротуар
        ax.add_patch(Rectangle((17.5, z0), 3.5, z1 - z0, fc="#d4d4d4", ec="#555555", lw=0.5, zorder=3))
    ax.text(8.0, -54.0, "площадь у проспекта", fontsize=7, color="#666666", ha="center")
    ax.text(25.2, -84.0, "Банковский переулок · 9 м", fontsize=7, color="#555555", ha="center", va="center", rotation=90)
    ax.plot([6, 6], [-99.3, -52.3], color="#222222", lw=1.4, ls=(0, (3, 1.5)), zorder=12)
    ax.text(4.8, -76.0, "забор двора инкассации", fontsize=5.8, rotation=90, ha="center", va="center")
    rect(ax, ANNEX, fc="#fdf0c8", ec="#8a6d1c", lw=1.0, zorder=5)
    ax.text(-0.8, -87.0, "бокс\nинкассации", fontsize=5.8, ha="center", va="center")
    rect(ax, (-8.0, -4.0, -93.3, -65.3), fc="#b9c7e6", ec="#1c2f66", lw=1.0, zorder=5)
    ax.text(-6.0, -79.0, "банк", fontsize=6.5, rotation=90, ha="center", va="center")
    rect(ax, BC13, fc="#bcc3cc", ec="#333333", lw=1.0, zorder=5)
    ax.text(37.0, -85.0, "БЦ «Проспект, 13»", fontsize=6.5, rotation=90, ha="center", va="center")
    rect(ax, WASH_OLD, fc="none", ec="#c0392b", lw=1.0, ls=(0, (4, 3)), zorder=25)
    ax.text(3.6, -96.4, "было", fontsize=5.8, color="#c0392b", ha="center", va="center", zorder=26,
            bbox={"boxstyle": "round,pad=0.08", "fc": "white", "ec": "none", "alpha": 0.85})
    # здание мойки
    rect(ax, TUNNEL, fc="#e3f1fb", ec="#111111", lw=1.2, zorder=5)
    ax.text(14.1, -79.0, "МОЕЧНЫЙ\nТОННЕЛЬ\n5,8 × 26\n\nпост 1 —\nмойка\n\nпост 2 —\nсушка", fontsize=6.3, weight="bold", ha="center", va="center", zorder=20)
    rooms(ax, WASH_ROOMS, fs=5.2, lw=1.0)
    rect(ax, WASH, fc="none", ec="#111111", lw=2.0, zorder=21)
    for z in (-92.0, -66.0):
        ax.add_patch(Rectangle((12.1, z - 0.35), 4.0, 0.7, fc="white", ec="#1a7f5a", lw=1.2, zorder=22))
    doors(ax, [(9.0, -66.0, "x", 1.6), (11.2, -70.0, "z", 1.17), (11.2, -76.5, "z", 1.17), (11.2, -87.5, "z", 1.17), (9.0, -92.0, "x", 1.17),
               (6.8, -81.0, "z", 0.0001)])
    ax.plot([17.0, 17.0], [-90.0, -68.0], color="#4a90c2", lw=2.4, zorder=23)
    ax.text(18.2, -79.0, "стена тоннеля к переулку — стекло", fontsize=5.6, rotation=90, ha="center", va="center", color="#2b6cb0")
    # площадки
    rect(ax, VACUUM, fc="#dfe6f5", ec="#33407a", lw=0.9, ls=(0, (4, 2)), zorder=6)
    ax.text(10.0, -101.0, "навес:\nпылесосы, воздух", fontsize=5.8, ha="center", va="center", zorder=20)
    rect(ax, TIRE_SHOP, fc="#c9a27a", ec="#333333", lw=0.8, zorder=6)
    ax.text(10.0, -113.8, "шиномонтаж (контейнер)", fontsize=5.8, ha="center", va="center")
    ax.text(1.0, -100.5, "площадка въезда 12 м,\nочередь 2 машины", fontsize=5.8, ha="center", va="center", zorder=20)
    ax.text(0.5, -62.6, "площадка выезда 6,7 м", fontsize=5.8, ha="center", va="center", zorder=20)
    for x in [v * 1.6 + 6.8 for v in range(0, 7)]:
        ax.add_patch(Circle((x, -59.3), 0.22, fc="#333333", ec="none", zorder=12))
    ax.plot([16.4], [-60.4], marker="s", ms=6, color="#2b6cb0", zorder=12)
    ax.text(14.0, -57.6, "стела «Автомойка 24»", fontsize=5.8, ha="center", va="center")
    car(ax, 14.1, -86.0, along_x=False, color="#7c93a8")
    car(ax, 14.1, -72.0, along_x=False, color="#7c93a8")
    car(ax, 14.1, -97.0, along_x=False)
    car(ax, 22.6, -110.0, along_x=False)
    car(ax, 22.6, -116.0, along_x=False)
    path(ax, [(27.5, -50.0), (27.5, -108.0), (23.0, -106.0), (19.0, -100.0), (14.1, -97.5), (14.1, -66.5), (15.5, -62.6), (20.0, -62.6),
              (23.5, -58.0), (23.5, -50.0)], "#1a7f5a", lw=1.5)
    dim(ax, (6.8, -64.2), (17.0, -64.2), off=1.0, fs=6)
    dim(ax, (2.4, -92.0), (2.4, -66.0), off=0.0, fs=6)
    dim(ax, (21.0, -121.0), (30.0, -121.0), off=-1.0, fs=6)
    north_arrow(ax, 36.0, -49.5, 2.5)
    scale_bar(ax, -6.0, -48.6, meters=20, step=5, k=0.4)
    # --- разрез мойки
    axw = fig.add_axes([0.44, 0.615, 0.55, 0.14])
    axw.set_xlim(-56, -110)
    axw.set_ylim(-1.0, 9.5)
    axw.set_aspect("equal")
    axw.set_title("мойка: продольный разрез по тоннелю (проспект слева)", fontsize=9.5, loc="left")
    axw.tick_params(labelsize=6)
    axw.set_xticks([-59.3, -66.0, -92.0, -104.0])
    axw.set_yticks([0, 3.6, 5.0])
    axw.add_patch(Rectangle((-110, -1.0), 54, 1.0, fc="#d9d9d9", ec="none", zorder=1))
    axw.add_patch(Rectangle((-92.0, 0), 26.0, WASH_H, fc="#e3f1fb", ec="#111111", lw=1.4, zorder=3))
    axw.add_patch(Rectangle((-92.0, 3.6), 26.0, 1.4, fc="#cfd8e3", ec="#111111", lw=0.8, zorder=4))
    for z in (-92.0, -66.0):
        axw.add_patch(Rectangle((z - 0.2, 0), 0.4, 3.6, fc="#ffffff", ec="#1a7f5a", lw=1.0, zorder=5))
    axw.add_patch(Rectangle((-88.2, 0.05), 4.5, 1.5, fc="#7c93a8", ec="#3f4850", lw=0.5, zorder=6))
    axw.add_patch(Rectangle((-74.2, 0.05), 4.5, 1.5, fc="#7c93a8", ec="#3f4850", lw=0.5, zorder=6))
    for z in (-89.0, -83.0):
        axw.plot([z, z], [0, 3.3], color="#2b6cb0", lw=1.2, zorder=6)
    axw.plot([-89.0, -83.0], [3.3, 3.3], color="#2b6cb0", lw=1.2, zorder=6)
    axw.text(-86.0, 4.3, "портал мойки", fontsize=5.6, ha="center", va="center", zorder=8)
    axw.text(-72.0, 4.3, "сушка, протирка", fontsize=5.6, ha="center", va="center", zorder=8)
    axw.add_patch(Rectangle((-104.0, 3.4), 6.0, 0.3, fc="#33407a", ec="none", zorder=5))
    axw.plot([-103.6, -103.6], [0, 3.4], color="#33407a", lw=1.0)
    axw.plot([-98.4, -98.4], [0, 3.4], color="#33407a", lw=1.0)
    axw.text(-101.0, 4.4, "навес", fontsize=5.6, ha="center")
    axw.plot([-60.4, -60.4], [0, 9.0], color="#333333", lw=1.2)
    axw.add_patch(Rectangle((-61.6, 6.2), 2.4, 2.8, fc="#2b6cb0", ec="none", zorder=5))
    figure_man(axw, -63.0)
    figure_man(axw, -95.0)
    axw.text(-58.0, 6.5, "стела\n9 м", fontsize=5.6, ha="center", va="center")
    # --- разрез банка
    axb = fig.add_axes([0.44, 0.19, 0.55, 0.33])
    axb.set_xlim(-46, -104)
    axb.set_ylim(-5.0, 18.5)
    axb.set_aspect("equal")
    axb.set_title("банк: разрез С–Ю по X = −21 (вход, зал, охрана; проспект слева)", fontsize=9.5, loc="left")
    axb.tick_params(labelsize=6)
    axb.set_xticks([-46.95, -52.3, -61.3, -65.3, -78.3, -89.1, -93.3, -95.3, -99.3])
    axb.set_xticklabels(["−47,0", "−52,3", "−61,3", "−65,3", "−78,3", "−89,1", "−93,3", "−95,3", "−99,3"], rotation=40)
    axb.set_yticks([-3.2, 0, 4.5, 8.4, 12.3, 13.3])
    axb.grid(True, axis="y", color="#aaaaaa", lw=0.25, zorder=0)
    axb.add_patch(Rectangle((-104, -5.0), 58, 5.0, fc="#d9d9d9", ec="none", zorder=1))
    axb.add_patch(Rectangle((-93.7, -3.6), 28.8, 3.6, fc="#f5f5f5", ec="#333333", lw=1.2, zorder=2))
    axb.add_patch(Rectangle((-93.3, 0), 28.0, 4.2, fc="#e3f1fb", ec="#111111", lw=1.4, zorder=3))
    for y0, y1 in ((4.5, 8.1), (8.4, 11.95)):
        axb.add_patch(Rectangle((-95.3, y0), 34.0, y1 - y0, fc="#f3f3ee", ec="#111111", lw=1.4, zorder=3))
    for y in (4.2, 8.1, 11.95):
        axb.add_patch(Rectangle((-95.3, y), 34.0, 0.3, fc="#555555", ec="none", zorder=4))
    for z in (-95.3, -61.55):
        axb.add_patch(Rectangle((z, 12.3), 0.25, 1.0, fc="#555555", ec="none", zorder=4))
    axb.add_patch(Rectangle((-95.0, 12.3), 5.9, 2.6, fc="#dddddd", ec="#111111", lw=1.0, zorder=3))
    axb.add_patch(Rectangle((-62.25, 0), 0.7, 4.2, fc="#222222", ec="none", zorder=5))
    for z in (-89.1, -78.3):
        axb.plot([z, z], [0, 4.2], color="#111111", lw=1.0, zorder=5)
    axb.plot([-68.3, -68.3], [0, 4.2], color="#4a90c2", lw=1.4, zorder=5)
    axb.plot([-65.3, -65.3], [0, 4.2], color="#4a90c2", lw=1.8, zorder=5)
    for z in (-89.1, -83.3, -80.7, -75.3):
        axb.plot([z, z], [4.5, 8.1], color="#111111", lw=0.8, zorder=5)
        axb.plot([z, z], [8.4, 11.95], color="#111111", lw=0.8, zorder=5)
    for z in (-89.3, -79.3):
        axb.plot([z, z], [-3.2, -0.4], color="#111111", lw=0.8, zorder=5)
    axb.add_patch(Rectangle((-78.8, 0), 1.0, 1.1, fc="#c9a27a", ec="#333333", lw=0.5, zorder=6))
    labels = [(-66.8, 2.1, "тамбур"), (-73.3, 2.6, "операционный зал\n13 м"), (-83.7, 2.6, "коридор,\nперсонал"), (-91.2, 2.1, "охрана"),
              (-68.3, 6.3, "кредитный отдел"), (-78.0, 6.3, "ИТ"), (-82.0, 6.3, "кор."), (-89.3, 6.3, "архив"),
              (-68.3, 10.2, "зал совещаний"), (-78.0, 10.2, "зам."), (-82.0, 10.2, "кор."), (-89.3, 10.2, "серверная"),
              (-72.3, -1.8, "депозитарий"), (-84.3, -1.8, "пост охраны"), (-91.3, -1.8, "коридор"), (-92.0, 13.6, "будка Л1"),
              (-56.8, 2.6, "площадь 9 м"), (-63.3, 2.6, "навес")]
    for z, y, text in labels:
        axb.text(z, y, text, fontsize=5.6, ha="center", va="center", zorder=20)
    axb.plot([-99.3, -99.3], [0, 2.4], color="#222222", lw=1.4, ls=(0, (3, 1.5)))
    for z in (-53.0,):
        axb.add_patch(Rectangle((z - 0.1, 0), 0.2, 0.9, fc="#333333", ec="none", zorder=6))
    figure_man(axb, -50.0)
    figure_man(axb, -58.0)
    figure_man(axb, -72.0)
    figure_man(axb, -97.5)
    axb.add_patch(Rectangle((-63.9, 12.3), 1.6, 0.8, fc="#b8a98a", ec="#333333", lw=0.5, zorder=6))
    axb.text(-70.0, 13.4, "лёжка", fontsize=5.6, ha="center")
    notes = [
        "Мойка: одна проездная линия (портал и сушка) и боковой блок вдоль забора банка — клиентская с кассой, бытовка, склад химии, техпомещение.",
        "Въезд с переулка на северную площадку (очередь на две машины, пылесосы под навесом), выезд — на южную и налево в переулок к проспекту.",
        "С проспекта видны южные ворота и стела на углу: здание закрывает разрыв 11,5 м между банком и переулком.",
        "Для игрока: тоннель насквозь (27 м под крышей с двумя воротами), четыре комнаты бокового блока, стеклянная стена к переулку.",
        "Почему не между БЦ 11 и банком: там проход к стоянке, который владелец просил не перекрывать (29.10), и въезд пришлось бы вести через тротуар проспекта.",
        "Переулок: 9 м (две полосы и стоянка вдоль), два съезда через тротуар, столбики в устье убираются — это проезд, а не пешеходная зона.",
    ]
    fig.text(0.44, 0.135, "\n".join(notes), fontsize=6.9, va="top", linespacing=1.5)
    path_ = OUT / "prospekt_north_8_wash.png"
    fig.savefig(path_)
    plt.close(fig)
    return path_


def main() -> None:
    plt.rcParams["font.family"] = "DejaVu Sans"
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    for build in (sheet_block, sheet_street, sheet_bank, sheet_wash):
        print("prospekt_north_side_plan:", build(snap))


if __name__ == "__main__":
    main()
