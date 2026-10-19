"""Пригород (зона 1) — схема левел-дизайна для прогулки владельца: маршруты, горячие точки, здания с
интерьерами, укрытия, посты мародёров, появления и выходы, места заказа «Вернуть машину», точки обзора.
Данные — data/zone01_layout.json, сгенерированные сцены зоны 1 (укрытия, посты), реестр мест заказа.

    python -X utf8 tools/zone01_ld_plan.py   →   docs/design/zone01_level_design.png
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, Polygon  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_zone01_blockouts as bo  # noqa: E402

LAYOUT = json.loads((ROOT / "data/zone01_layout.json").read_text(encoding="utf-8"))
OUT = ROOT / "docs/design/zone01_level_design.png"

# кольца риска (§1): горячие точки — лучший лут и посты; середина; остальное — край
HOT = {"Hangar_8", "Box_5", "Storeroom", "Bus_Depot", "Bus_Garage", "Rail_Store", "Rail_Depot", "Rail_Workshop",
       "Rail_Station", "N_service", "Skeleton_9", "Skeleton_2", "Site_Store"}
MID = {"Supermarket", "Pharmacy", "Admin", "School", "Kindergarten", "Cinema", "Bus_Terminal", "Bus_Office",
       "Site_Office", "Shop_N", "Sport_Hall", "Sport_Locker", "East_Brick1", "East_Brick2", "Tower_9A", "Panel_E2",
       "Panel_E6", "Pavilion_S"}
HOT_ZONES = [("Рынок", (-189, 180), 60), ("Ремонтные дворы", (122, 276), 55), ("Станция и пакгауз", (215, 120), 60),
             ("Недострой", (80, -105), 70), ("Техкорпус № 2", (56, -219), 40)]
OVERWATCH = [("крыша недостроя 9 эт.", (97, -134)), ("крыша девятиэтажки", (-78, 86)), ("эстакада", (100, 250)),
             ("переход над путями", (228, 186))]
ROUTES = [("М1 Северная улица", ["north", "mall"], "#c0392b"), ("М2 Южная улица", ["south", "evac3"], "#d35400"),
          ("М3 Проспект", ["artery"], "#8e44ad"), ("М4 Восточная улица", ["east"], "#2471a3")]
FLANKS = [("Ф1 мостки и брод", LAYOUT["boardwalk"]), ("Ф2 дворы панелек", [(-120, -60), (-87, -25), (-87, 30), (-50, 42), (-50, 75)]),
          ("Ф3 парк путей", [(250, 60), (238, 120), (226, 180), (216, 230)]),
          ("Ф4 эстакада", [tuple(q) for q in LAYOUT["overpass"]["points"]])]


def _scene_points(path: Path, pattern: str) -> list[tuple[str, float, float]]:
    """Имена и позиции узлов сцены по шаблону имени (позиция — первая строка position после заголовка)."""
    text = path.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r'\[node name="(' + pattern + r')"[^\]]*\]\n(?:[^\[]*?)position = Vector3\(([-\d.e]+), ([-\d.e]+), ([-\d.e]+)\)', text):
        out.append((m.group(1), float(m.group(2)), float(m.group(4))))
    return out


def rect(x: float, z: float, L: float, D: float, ang: float) -> list[tuple[float, float]]:
    return bo.corners(x, z, L, D, ang)


def main() -> None:
    fig = plt.figure(figsize=(21, 16), dpi=100)
    ax = fig.add_axes([0.02, 0.03, 0.70, 0.94])
    ax.set_aspect("equal")
    ax.set_xlim(-310, 310)
    ax.set_ylim(310, -310)  # север (−Z) вверху
    ax.set_facecolor("#e9e5d8")
    ax.add_patch(Polygon(LAYOUT["boundary"], closed=True, fill=False, ec="#9c7a3c", lw=1.6, ls="--"))
    ax.add_patch(Polygon(LAYOUT["swamp"], closed=True, fc="#9fb7a8", ec="none", alpha=0.8))
    ax.add_patch(Polygon(LAYOUT["bus_lot"], closed=True, fc="#cfcbc2", ec="none"))
    ax.add_patch(Polygon(LAYOUT["site"], closed=True, fc="#d9c7a3", ec="none", alpha=0.7))
    rv = LAYOUT["ravine"]
    ax.plot([q[0] for q in rv], [q[1] for q in rv], color="#6f8f6a", lw=10, alpha=0.5, solid_capstyle="round")
    for r in LAYOUT["roads"]:
        ax.plot([q[0] for q in r["points"]], [q[1] for q in r["points"]], color="#b8a98a" if r["dirt"] else "#8d8d88",
                lw=r["width"] * 0.55, solid_capstyle="round", zorder=1)
    ax.plot([q[0] for q in LAYOUT["tracks"]["axis"]], [q[1] for q in LAYOUT["tracks"]["axis"]], color="#5d4e3c", lw=3, zorder=1)
    op = LAYOUT["overpass"]["points"]
    ax.plot([q[0] for q in op], [q[1] for q in op], color="#666", lw=7, alpha=0.55, zorder=2)
    fence = LAYOUT["repair_yard"]["fence"]
    ax.plot([q[0] for q in fence], [q[1] for q in fence], color="#555", lw=1.5, zorder=3)
    for name, (x, z), r in HOT_ZONES:
        ax.add_patch(Circle((x, z), r, fc="#e74c3c", ec="#c0392b", alpha=0.10, lw=1.2, zorder=2))
        ax.text(x, z - r - 4, name, ha="center", va="bottom", fontsize=9, color="#a93226", weight="bold", zorder=9)
    # готовые куски
    for k, rd in LAYOUT["ready"].items():
        ax.add_patch(Polygon(rd["outline"], closed=True, fill=False, ec="#127a74", lw=1.4, ls="-.", zorder=3))
    open_ids = set(bo.INTERIOR) | set(bo.APARTMENTS) | bo.HOUSES
    for b in LAYOUT["buildings"]:
        x, z = b["at"]
        enter = b["id"] in open_ids or b["kind"] in ("house", "skeleton")
        if b["kind"] == "canopy":
            fc = "#c9c4b8"
        elif not enter:
            fc = "#a9a8a2"
        elif b["id"] in HOT:
            fc = "#e3725f"
        elif b["id"] in MID:
            fc = "#f0b155"
        else:
            fc = "#f3dc8a"
        ax.add_patch(Polygon(rect(x, z, b["size"][0], b["size"][1], b["angle"]), closed=True, fc=fc,
                             ec="#3d3a35" if enter else "#77756f", lw=1.1 if enter else 0.6, zorder=4))
        if enter and b["size"][0] * b["size"][1] > 150:
            ax.text(x, z, b["label"].replace("Жилой дом · 6 этажей", "дом 6 эт.").split(" · ")[0][:22], ha="center",
                    va="center", fontsize=6.2, color="#222", zorder=8)
    # укрытия, посты
    layout_scene = ROOT / "scenes/levels/zone01/zone01_layout.tscn"
    for _, x, z in _scene_points(layout_scene, r"Cover_\d+|Bags_\d+|Junk_\d+"):
        ax.add_patch(Polygon(rect(x, z, 3.0, 1.4, 0), closed=True, fc="#34495e", ec="none", zorder=5))
    ai_scene = ROOT / "scenes/levels/zone01/zone01_ai.tscn"
    for name, x, z in _scene_points(ai_scene, r"Post_\w+"):
        ax.plot(x, z, marker="X", ms=11, color="#922b21", mec="white", mew=1.2, zorder=10)
    for name, x, z in _scene_points(ai_scene, r"Nest_\w+"):
        ax.plot(x, z, marker="^", ms=10, color="#922b21", mec="white", mew=1.0, zorder=10)
    # маршруты
    roads = {r["id"]: r for r in LAYOUT["roads"]}
    for title, ids, col in ROUTES:
        for rid in ids:
            pts = roads[rid]["points"]
            ax.plot([q[0] for q in pts], [q[1] for q in pts], color=col, lw=4.5, alpha=0.55, zorder=6)
        p0 = roads[ids[0]]["points"][len(roads[ids[0]]["points"]) // 2]
        ax.text(p0[0], p0[1] - 7, title, color=col, fontsize=10, weight="bold", ha="center", zorder=11,
                bbox=dict(fc="white", ec="none", alpha=0.75, pad=1.2))
    for title, pts in FLANKS:
        ax.plot([q[0] for q in pts], [q[1] for q in pts], color="#1e8449", lw=2.6, ls=(0, (5, 3)), zorder=6)
        q = pts[len(pts) // 2]
        ax.text(q[0] + 4, q[1] + 6, title, color="#1e8449", fontsize=9, weight="bold", zorder=11,
                bbox=dict(fc="white", ec="none", alpha=0.7, pad=1.0))
    for title, (x, z) in OVERWATCH:
        ax.plot(x, z, marker="o", ms=13, mfc="none", mec="#1a5276", mew=2.2, zorder=10)
        ax.plot(x, z, marker="o", ms=4, color="#1a5276", zorder=10)
        ax.text(x + 7, z + 3, title, fontsize=8, color="#1a5276", zorder=11)
    # появления, выходы
    for x, z in LAYOUT["spawns"]:
        ax.plot(x, z, marker="o", ms=12, color="#2e86de", mec="white", mew=1.5, zorder=12)
    for e in LAYOUT["exits"]:
        x, z = e["at"]
        ax.plot(x, z, marker="^", ms=14, color="#8e44ad" if e["kind"] == "mall" else "#27ae60", mec="white", mew=1.5, zorder=12)
        ax.text(x, z + 11, e["label"].split(" (")[0], ha="center", fontsize=8, color="#145a32", zorder=12,
                bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.8))
    # заказ «Вернуть машину»
    reg = json.loads((ROOT / "data/quest_sites/car_recovery_belt.json").read_text(encoding="utf-8"))
    for s in reg["sites"]:
        x, _, z = s["position"]
        if s["id"] == "car_belt_search":
            ax.add_patch(Circle((x, z), 60, fill=False, ec="#b7950b", lw=1.8, ls=":", zorder=7))
        elif s["id"] in ("car_belt_hangar", "car_belt_parts_wheel", "car_belt_candidate"):
            ax.plot(x, z, marker="*", ms=17, color="#f1c40f", mec="#7d6608", mew=1.0, zorder=13)
    ax.text(100, 300, "заказ «Вернуть машину»: ангар № 8, кладовая, бокс № 5", ha="center", fontsize=9, color="#7d6608",
            weight="bold", zorder=13, bbox=dict(fc="white", ec="none", alpha=0.75, pad=1.2))
    for v in range(-300, 301, 100):
        ax.axvline(v, color="#000", alpha=0.05, lw=0.6)
        ax.axhline(v, color="#000", alpha=0.05, lw=0.6)
    ax.set_xticks(range(-300, 301, 100))
    ax.set_yticks(range(-300, 301, 100))
    ax.tick_params(labelsize=8)
    # легенда
    lx = fig.add_axes([0.73, 0.03, 0.26, 0.94])
    lx.axis("off")
    lines = [
        ("Пригород (зона 1) — левел-дизайн, проход 1", 15, "bold", "#222"),
        ("2026-10-19 · блокаут · север вверху · сетка 100 м", 9.5, "normal", "#555"),
        ("", 6, "normal", "#000"),
        ("Здания", 12, "bold", "#222"),
        ("■ горячая точка — интерьер, лучший лут", 10, "normal", "#e3725f"),
        ("■ середина — интерьер, средний лут", 10, "normal", "#e0a040"),
        ("■ край — дом с комнатами", 10, "normal", "#c9a93a"),
        ("■ закрыто (только фасад)", 10, "normal", "#8d8c86"),
        ("красные круги — районы горячих точек", 9.5, "normal", "#a93226"),
        ("", 6, "normal", "#000"),
        ("Маршруты", 12, "bold", "#222"),
        ("жирные — улицы М1–М4", 10, "normal", "#c0392b"),
        ("пунктир — фланги Ф1–Ф4 (тихо, медленно, прикрыто)", 10, "normal", "#1e8449"),
        ("", 6, "normal", "#000"),
        ("Бой", 12, "bold", "#222"),
        ("▪ укрытия: блоки, отбойники, машины, контейнеры,", 10, "normal", "#34495e"),
        ("   плиты и трубы стройки, мешки у постов", 10, "normal", "#34495e"),
        ("✕ посты мародёров, ▲ гнёзда стрелков", 10, "normal", "#922b21"),
        ("◎ точки обзора", 10, "normal", "#1a5276"),
        ("", 6, "normal", "#000"),
        ("Рейд", 12, "bold", "#222"),
        ("● появление (6 по краю)", 10, "normal", "#2e86de"),
        ("▲ выход, фиолетовый — к ТЦ", 10, "normal", "#27ae60"),
        ("★ заказ: ангар № 8, кладовая, бокс № 5", 10, "normal", "#b7950b"),
        ("   точки — пунктир района поиска 60 м", 10, "normal", "#b7950b"),
        ("", 6, "normal", "#000"),
        ("Что посмотреть на прогулке", 12, "bold", "#222"),
        ("1. центр: подъезды E2/E6, универсам насквозь,", 10, "normal", "#333"),
        ("   администрация (ключ серверной — верхний этаж)", 10, "normal", "#333"),
        ("2. ремонтные дворы: с запада, с востока, с эстакады", 10, "normal", "#333"),
        ("3. недострой: подъём на крышу, обзор", 10, "normal", "#333"),
        ("4. кинотеатр, школа — ближний бой", 10, "normal", "#333"),
        ("5. станция, пакгауз — бой среди вагонов", 10, "normal", "#333"),
        ("6. хватает ли укрытий на стоянке и у универсама", 10, "normal", "#333"),
        ("7. техкорпус № 2: серверная за запертой дверью", 10, "normal", "#333"),
    ]
    y = 0.99
    for text, size, weight, col in lines:
        lx.text(0.0, y, text, fontsize=size, weight=weight, color=col, va="top", transform=lx.transAxes)
        y -= 0.009 + size * 0.0017
    fig.savefig(OUT, dpi=100, facecolor="#f4f1e8")
    print(OUT)


if __name__ == "__main__":
    main()
