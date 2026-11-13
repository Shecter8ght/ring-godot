#!/usr/bin/env python
"""«Проспект», дом 7 — пробный дом вместо серой коробки: чертёж под место (в сцену не внесено).

Лист 1 — место в координатах сцены (X — восток, Z — юг), что видно с проспекта и с эстакады, куда какой фасад.
Лист 2 — фасады с сеткой пролётов, входная группа, набор частей.
Образец — концепт владельца «дом 7» (референсы/prospekt_bc5_yard/concepts/04_house_9f_brutalist_podium.webp) и схема
размеров Codex (36 × 26 м, первый этаж 4,5 м + 11 × 3,0 м, парапет 0,45 м, козырёк 14 × 2,4 м).
  python -X utf8 tools/prospekt_house7_plan.py   →  docs/design/prospekt_house7_1_site.png, prospekt_house7_2_facades.png
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle

OUT = Path(__file__).resolve().parent.parent / "docs" / "design"

# --- место (из снимка сцены prospekt_snapshot.json), прямоугольники (x0, x1, z0, z1)
HOUSE = (-206.0, -170.0, 38.0, 64.0)          # дом 7: 36 × 26
POLICE = (-208.0, -178.0, 16.0, 30.0)         # отдел полиции, 2 этажа, кровля 7,0
POLICE_YARD = (-217.0, -208.0, 16.0, 60.0)
POLICE_GARAGE = (-216.5, -209.5, 48.0, 58.0)
MINIMARKET = (-176.0, -164.0, 17.0, 27.0)
YARD = (-210.0, -166.0, 64.0, 108.0)          # двор дома 7
RING_DECK = (-246.0, -220.0, -30.0, 112.0)    # полотно Объездной, верх +9,0
AVENUE = (-248.0, -130.0, -35.15, 3.85)
WALK_S = (-218.0, -130.0, 3.85, 15.65)
PLAZA = (-210.0, -166.0, 15.65, 34.0)

# --- дом: высоты, м
H_GROUND = 4.5
H_FLOOR = 3.0
FLOORS_UP = 11
H_PARAPET = 0.45
H_TOP = H_GROUND + H_FLOOR * FLOORS_UP        # 37,5
POLICE_ROOF = 7.0
EYE = 1.7

# --- сетки пролётов, м от левого угла фасада: (от, до, вид); виды: W — окно, LP — лоджия с перфорированным
# ограждением, LG — лоджия со стеклянным, WD — деревянная вставка, P — простенок (бежевая панель)
SOUTH = [(0, 1.5, "P"), (1.5, 5.0, "W"), (5.0, 6.5, "P"), (6.5, 11.5, "LP"), (11.5, 12.0, "WD"), (12.0, 17.0, "LG"),
         (17.0, 19.0, "P"), (19.0, 24.0, "LP"), (24.0, 24.5, "WD"), (24.5, 29.5, "LG"), (29.5, 31.0, "P"),
         (31.0, 34.5, "W"), (34.5, 36.0, "P")]
NORTH = [(0, 1.4, "P"), (1.4, 4.8, "W"), (4.8, 6.3, "P"), (6.3, 10.6, "LP"), (10.6, 14.9, "LG"), (14.9, 16.3, "P"),
         (16.3, 19.7, "W"), (19.7, 21.1, "P"), (21.1, 25.4, "LP"), (25.4, 29.7, "LG"), (29.7, 31.2, "P"),
         (31.2, 34.6, "W"), (34.6, 36.0, "P")]
END = [(0, 4.4, "P"), (4.4, 6.6, "WV"), (6.6, 11.9, "P"), (11.9, 14.1, "WV"), (14.1, 19.4, "P"), (19.4, 21.6, "WV"),
       (21.6, 26.0, "P")]                    # WV — окно в тёмной вертикальной полосе
PORTAL = (11.0, 25.0)                         # козырёк 14 м по южному фасаду
PORTAL_OUT = 2.4

COL = {"beige": "#d9bfa6", "dark": "#3c3d40", "glass": "#7d8f99", "wood": "#9a5a2e", "concrete": "#8d8a84",
       "perf": "#55575b", "line": "#2a2a2a"}


def rect(ax, r, **kw):
    ax.add_patch(Rectangle((r[0], r[2]), r[1] - r[0], r[3] - r[2], **kw))


def sheet_site():
    fig, (ax, sx) = plt.subplots(1, 2, figsize=(19, 10), gridspec_kw={"width_ratios": [1.25, 1]})
    fig.suptitle("«Проспект» · дом 7 — пробный дом · лист 1: место и ориентация фасадов", fontsize=15, x=0.02, ha="left")
    rect(ax, AVENUE, fc="#c9ced3", ec="none")
    rect(ax, WALK_S, fc="#e3e0da", ec="none")
    rect(ax, PLAZA, fc="#ece9e2", ec="#b9b5ab", lw=0.6)
    rect(ax, YARD, fc="#e6ead9", ec="#a9b196", lw=0.8)
    rect(ax, RING_DECK, fc="#b8bcc2", ec="#6d7178", lw=1.0, hatch="//", alpha=0.6)
    rect(ax, POLICE_YARD, fc="#d6d6d6", ec="#888", lw=0.8)
    rect(ax, POLICE_GARAGE, fc="#a9adb3", ec="#555", lw=0.8)
    rect(ax, POLICE, fc="#9aa3ad", ec="#333", lw=1.2)
    rect(ax, MINIMARKET, fc="#b7ad9b", ec="#333", lw=1.0)
    rect(ax, HOUSE, fc=COL["beige"], ec="#000", lw=2.2)
    # козырёк и крыльцо — на юг, во двор
    x0 = HOUSE[0] + PORTAL[0]
    ax.add_patch(Rectangle((x0, HOUSE[3]), PORTAL[1] - PORTAL[0], PORTAL_OUT, fc=COL["concrete"], ec="#000", lw=1.2))
    ax.annotate("вход: портал 14 × 2,4 м\nво двор (юг)", (x0 + 7, HOUSE[3] + PORTAL_OUT), (x0 + 7, HOUSE[3] + 12),
                ha="center", fontsize=10, arrowprops=dict(arrowstyle="->"))
    t = dict(ha="center", va="center", fontsize=10)
    ax.text(-188, 51, "ДОМ 7\n36 × 26 м · 12 этажей · 37,95 м\nзакрыт, только оболочка", fontsize=11, weight="bold", **{k: v for k, v in t.items() if k != "fontsize"})
    ax.text(-193, 23, "отдел полиции\n2 эт., кровля +7,0", **t)
    ax.text(-212.5, 36, "двор\nполиции", rotation=90, **t)
    ax.text(-170, 22, "минимаркет", **t)
    ax.text(-188, 90, "двор дома 7 (ходят игроки)", **t)
    ax.text(-233, 45, "Объездная · полотно +9,0\n(играбельный верх)", rotation=90, **t)
    ax.text(-175, -16, "ПРОСПЕКТ", fontsize=12, **{k: v for k, v in t.items() if k != "fontsize"})
    ax.text(-188, 34, "проулок 8 м", fontsize=9, **{k: v for k, v in t.items() if k != "fontsize"})
    # кто что видит
    for (px, pz, lab) in ((-188, 2, "с тротуара: этажи 6–12"), (-160, -30, "через проспект: этажи 4–12")):
        ax.plot([px, -188], [pz, 38], color="#c0392b", lw=1.0, ls="--")
        ax.plot([px], [pz], "o", color="#c0392b")
        ax.text(px + 1.5, pz - 1.5, lab, color="#c0392b", fontsize=9)
    ax.plot([-221.5, -206], [45, 51], color="#8e44ad", lw=1.0, ls="--")
    ax.plot([-221.5], [45], "o", color="#8e44ad")
    ax.text(-244, 70, "с эстакады (+9): западный торец\nи северный фасад целиком,\nс 15–30 м", color="#8e44ad", fontsize=9)
    # подписи фасадов
    ax.text(-188, 36.2, "СЕВЕРНЫЙ ФАСАД — к проспекту: лоджии, без входа (концепт REAR)", ha="center", va="bottom", fontsize=9,
            color="#1f4e79", weight="bold")
    ax.text(-188, 68.6, "ЮЖНЫЙ ФАСАД — во двор: портал и лоджии (концепт FRONT)", ha="center", va="top", fontsize=9,
            color="#1f4e79", weight="bold")
    ax.text(-168.8, 51, "ВОСТОЧНЫЙ ТОРЕЦ\n(концепт RIGHT)", rotation=270, ha="left", va="center", fontsize=9, color="#1f4e79", weight="bold")
    ax.text(-207.2, 51, "ЗАПАДНЫЙ ТОРЕЦ\n(зеркально)", rotation=90, ha="right", va="center", fontsize=9, color="#1f4e79", weight="bold")
    ax.set_xlim(-250, -128)
    ax.set_ylim(112, -38)                       # север вверху
    ax.set_aspect("equal")
    ax.set_xlabel("X, м (восток →)")
    ax.set_ylabel("Z, м (юг ↓)")
    ax.grid(True, lw=0.3, color="#999", alpha=0.5)
    ax.set_title("План места, координаты сцены", loc="left", fontsize=11)

    # разрез север — юг по X = −188
    sx.set_title("Разрез север — юг (X = −188): что закрывает отдел полиции", loc="left", fontsize=11)
    sx.add_patch(Rectangle((-36, -0.4), 150, 0.4, fc="#bdbdbd", ec="none"))
    sx.add_patch(Rectangle((POLICE[2], 0), POLICE[3] - POLICE[2], POLICE_ROOF, fc="#9aa3ad", ec="#333"))
    sx.add_patch(Rectangle((HOUSE[2], 0), HOUSE[3] - HOUSE[2], H_GROUND, fc=COL["concrete"], ec="#000"))
    sx.add_patch(Rectangle((HOUSE[2], H_GROUND), HOUSE[3] - HOUSE[2], H_TOP - H_GROUND + H_PARAPET, fc=COL["beige"], ec="#000", lw=1.5))
    for i in range(FLOORS_UP + 1):
        y = H_GROUND + i * H_FLOOR
        sx.plot([HOUSE[2], HOUSE[3]], [y, y], color="#7a6a5a", lw=0.5)
        if i < FLOORS_UP:
            sx.text(HOUSE[3] + 1, y + 1.5, str(i + 2), fontsize=8, va="center")
    sx.text(HOUSE[3] + 1, 2.2, "1", fontsize=8, va="center")
    sx.add_patch(Rectangle((HOUSE[3], 3.7), PORTAL_OUT, 0.8, fc=COL["concrete"], ec="#000"))
    for (ez, lab, c) in ((2.0, "тротуар проспекта", "#c0392b"), (-33.0, "дальний тротуар", "#e67e22")):
        k = (POLICE_ROOF - EYE) / (POLICE[2] - ez)
        y38 = EYE + k * (HOUSE[2] - ez)
        sx.plot([ez, HOUSE[2]], [EYE, y38], color=c, lw=1.1, ls="--")
        sx.plot([ez], [EYE], "o", color=c)
        sx.text(ez, EYE + 2.2, lab, color=c, fontsize=9, ha="center")
        sx.text(HOUSE[2] - 1, y38, "видно выше %.1f м" % y38, color=c, fontsize=9, ha="right", va="bottom")
    sx.text(23, 8, "полиция\n+7,0", ha="center", fontsize=9)
    sx.text(51, 20, "дом 7\n4,5 + 11 × 3,0\n+ парапет 0,45\n= 37,95 м", ha="center", fontsize=10)
    sx.text(72, 6.5, "козырёк входа\n(двор)", fontsize=9)
    sx.set_xlim(-38, 100)
    sx.set_ylim(-2, 42)
    sx.set_aspect("equal")
    sx.set_xlabel("Z, м (юг →)")
    sx.set_ylabel("высота, м")
    sx.grid(True, lw=0.3, color="#999", alpha=0.5)
    fig.text(0.02, 0.02,
             "Решения чертежа: 1) вход-портал — на юг, во двор (перед северным фасадом теперь отдел полиции, проулок 8 м); "
             "2) к проспекту обращён фасад с лоджиями — его видно поверх полиции с 4–6-го этажа; "
             "3) нижние 4,5 м и портал делаются подробно (игрок рядом), этажи выше — из набора частей; "
             "4) пятно и высота совпадают с коробкой блокаута — коллизия и навигация не меняются.",
             fontsize=10, wrap=True)
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    fig.savefig(OUT / "prospekt_house7_1_site.png", dpi=110)
    plt.close(fig)


def facade(ax, bays, width, title, portal=False, door_x=None):
    ax.set_title(title, loc="left", fontsize=11)
    ax.add_patch(Rectangle((0, 0), width, H_GROUND, fc=COL["concrete"], ec="#000", lw=1.0))
    for x in [i * 1.5 for i in range(int(width / 1.5) + 1)]:            # рёбра бетонного первого этажа
        ax.plot([x, x], [0.3, H_GROUND - 0.5], color="#6d6a65", lw=0.5)
    ax.add_patch(Rectangle((0, H_GROUND), width, H_TOP - H_GROUND + H_PARAPET, fc=COL["beige"], ec="#000", lw=1.2))
    for f in range(FLOORS_UP):
        y = H_GROUND + f * H_FLOOR
        for (a, b, kind) in bays:
            if kind == "W":
                ax.add_patch(Rectangle((a + 0.5, y + 0.9), b - a - 1.0, 1.7, fc=COL["glass"], ec=COL["dark"], lw=0.8))
                ax.plot([(a + b) / 2] * 2, [y + 0.9, y + 2.6], color=COL["dark"], lw=0.6)
            elif kind == "WV":
                ax.add_patch(Rectangle((a, y), b - a, H_FLOOR, fc=COL["dark"], ec="none"))
                ax.add_patch(Rectangle((a + 0.25, y + 0.9), b - a - 0.5, 1.7, fc=COL["glass"], ec="#000", lw=0.5))
            elif kind in ("LP", "LG"):
                ax.add_patch(Rectangle((a, y), b - a, H_FLOOR, fc=COL["dark"], ec="none"))
                ax.add_patch(Rectangle((a + 0.3, y + 0.75), b - a - 0.6, 2.0, fc=COL["glass"], ec="#000", lw=0.4))
                ax.add_patch(Rectangle((a, y + 0.1), b - a, 1.1, fc=COL["perf"] if kind == "LP" else "#a9c0c9",
                                       ec="#000", lw=0.5, alpha=0.95 if kind == "LP" else 0.7,
                                       hatch="...." if kind == "LP" else None))
            elif kind == "WD":
                ax.add_patch(Rectangle((a, y), b - a, H_FLOOR, fc=COL["wood"], ec="none"))
        ax.plot([0, width], [y, y], color="#b49a83", lw=0.4)
    for x in [i * 1.5 for i in range(int(width / 1.5) + 1)]:            # швы панелей
        ax.plot([x, x], [H_GROUND, H_TOP], color="#b49a83", lw=0.25)
    ax.add_patch(Rectangle((-0.15, H_TOP), width + 0.3, H_PARAPET, fc=COL["dark"], ec="#000", lw=0.8))
    if portal:
        a, b = PORTAL
        ax.add_patch(Rectangle((a, 3.7), b - a, 0.8, fc="#a3a09a", ec="#000", lw=1.2))
        ax.add_patch(Polygon([(a + 0.2, 0), (a + 2.6, 0), (a + 1.6, 3.7), (a + 0.2, 3.7)], fc="#a3a09a", ec="#000"))
        ax.add_patch(Polygon([(b - 0.2, 0), (b - 2.6, 0), (b - 1.6, 3.7), (b - 0.2, 3.7)], fc="#a3a09a", ec="#000"))
        ax.add_patch(Rectangle((a + 3.0, 0.15), 6.0, 3.3, fc="#c9a46a", ec=COL["dark"], lw=1.5))
        for x in (a + 4.5, a + 6.0, a + 7.5):
            ax.plot([x, x], [0.15, 3.45], color=COL["dark"], lw=1.0)
        ax.add_patch(Rectangle((a + 9.4, 0), 2.4, 0.9, fc="#a3a09a", ec="#000"))
        ax.text((a + b) / 2, -1.6, "портал 14,0 м · вылет 2,4 м · витраж вестибюля 6,0 × 3,3 · двери 1,17 × 2,42 × 2",
                ha="center", fontsize=9)
    if door_x is not None:
        ax.add_patch(Rectangle((door_x, 0), 1.17, 2.42, fc=COL["dark"], ec="#000"))
        ax.text(door_x + 0.6, -1.6, "служебная дверь 1,17 × 2,42", ha="center", fontsize=9)
    ax.plot([0, width], [-0.02, -0.02], color="#000", lw=1.5)
    ax.set_xlim(-2, width + 2)
    ax.set_ylim(-3, 41)
    ax.set_aspect("equal")
    ax.set_xticks([round(a, 1) for (a, _, _) in bays] + [width])
    ax.tick_params(axis="x", labelsize=7, rotation=90)
    ax.set_yticks([0, H_GROUND] + [H_GROUND + i * H_FLOOR for i in range(1, FLOORS_UP + 1)] + [H_TOP + H_PARAPET])
    ax.tick_params(axis="y", labelsize=7)


def sheet_facades():
    fig = plt.figure(figsize=(22, 12))
    fig.suptitle("«Проспект» · дом 7 — пробный дом · лист 2: фасады, сетка пролётов, набор частей", fontsize=15, x=0.02, ha="left")
    gs = fig.add_gridspec(1, 4, width_ratios=[36, 36, 26, 22])
    facade(fig.add_subplot(gs[0]), SOUTH, 36.0, "Южный фасад — двор: портал, лоджии парами (концепт FRONT)", portal=True)
    facade(fig.add_subplot(gs[1]), NORTH, 36.0, "Северный фасад — к проспекту: лоджии, служебная дверь (REAR)", door_x=17.4)
    facade(fig.add_subplot(gs[2]), END, 26.0, "Торцы — восточный и западный (RIGHT)")
    tx = fig.add_subplot(gs[3])
    tx.axis("off")
    tx.text(0, 1.0, """НАБОР ЧАСТЕЙ (пойдёт и на другие дома)
 1. пролёт «окно» 3,4–3,5 × 3,0
 2. лоджия, перфорированное ограждение
 3. лоджия, стеклянное ограждение
 4. деревянная вставка 0,5 × 3,0
 5. простенок: бежевая панель 1,5 × 3,0, швы
 6. тёмная полоса перекрытия лоджий
 7. окно торца в тёмной вертикали
 8. панель первого этажа: бетон с рёбрами
 9. парапет, отлив, угол
10. кровля: две надстройки, вентшахты

СВОИ УЗЛЫ ДОМА 7
 • портал: козырёк с рёбрами снизу,
   два косых пилона, крыльцо со ступенями,
   витраж вестибюля (тёмный, свет за стеклом)
 • служебная дверь в проулке

ВЫСОТЫ
 первый этаж 4,5 м (бетон)
 11 жилых × 3,0 м
 парапет 0,45 м → 37,95 м

ИГРОВАЯ ВЕРСИЯ (замысел)
 • коллизия — прежняя коробка 36 × 26
 • окна: стекло с отражением, за ним
   тёмная «комната» картой, шторы — 4 вида
 • LOD0 до ~60 м: части геометрией
   LOD1: плоские пролёты с нормалью
   LOD2 (с эстакады, издали): коробка
   с запечённым фасадом
 • материалы: фото-основы CC0 (панель
   фиброцемент, бетон в опалубке, металл),
   износ «два года простоя» — потёки под
   швами и отливами, грязь у земли,
   маски владельца; декали поверх
""", va="top", fontsize=10, family="DejaVu Sans")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT / "prospekt_house7_2_facades.png", dpi=110)
    plt.close(fig)


if __name__ == "__main__":
    sheet_site()
    sheet_facades()
    print("ok:", OUT / "prospekt_house7_1_site.png", OUT / "prospekt_house7_2_facades.png")
