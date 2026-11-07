# -*- coding: utf-8 -*-
"""Левел-дизайн карты «Проспект»: схема и замер обзора по плану data/blockouts/prospekt.json.

    python -X utf8 tools/prospekt_ld_plan.py            → docs/design/prospekt_level_design.png + docs/screens/prospekt/sightlines.json

Замер обзора (владелец 2026-10-24: «чтобы обзору постоянно что-то мешало через каждые 50–70–90 метров»): из точек
сетки 6 м по улице (вне зданий) лучи по 24 направлениям на высоте глаз 1,7 м до первой преграды. Преграда — то, что
закрывает взгляд стоя: здания, стены, коробки и наборы наполнения выше 1,7 м (автобусы, грузовики, контейнеры, вагоны,
ларьки, палатки, гаражи, большие кусты); машины, блоки, мешки, ограждения и сетка — нет. Граница карты — преграда
(за ней игроков нет). Итог: доля лучей длиннее 90 м и самые длинные — красным на схеме.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "data" / "blockouts" / "prospekt.json"
OUT_PNG = ROOT / "docs" / "design" / "prospekt_level_design.png"
OUT_JSON = ROOT / "docs" / "screens" / "prospekt" / "sightlines.json"

EYE = 1.7
CELL = 0.5            # растр преград, м
LONG = 90.0           # «обзор должен прерываться через 50–90 м»
STEP = 6.0            # шаг точек замера
RAYS = 24
MAX_RAY = 320.0

# наборы MallFiller, которые закрывают взгляд стоя: ширина × длина в плане (по локальным x и z)
VIEW_KITS = {
    "bus_city": (2.55, 12.0), "paz": (2.4, 7.8), "paz_police": (2.4, 7.8), "avtozak": (2.5, 7.9), "minibus": (2.05, 5.9),
    "ambulance": (2.05, 5.9), "inkassator": (2.1, 5.6), "armored_truck": (2.55, 7.0), "btr": (2.9, 7.6),
    "fire_truck": (2.5, 8.6), "dump_truck": (2.5, 7.6), "truck": (2.5, 7.2), "truck_cab": (2.5, 6.0), "trailer": (2.5, 13.0),
    "bus_wreck": (2.55, 12.0), "van": (1.94, 4.4), "flatbed": (2.0, 2.0), "container40": (2.44, 12.2), "container20": (2.44, 6.1),
    "garage": (3.2, 6.0), "garage_open": (3.2, 6.0), "cabin": (2.4, 6.0), "booth": (1.2, 1.2), "fence": (0.1, 3.0),
    "po2": (0.15, 2.5), "kiosk": (3.0, 2.4), "food_kiosk": (2.5, 2.0), "army_tent": (4.8, 10.0), "stage": (11.0, 6.5),
    "stall": (3.0, 2.0), "bus_stop": (6.0, 0.3),
    "district_fence": (0.25, 2.5), "watchtower": (2.6, 2.6), "excavator": (3.2, 4.6), "mixer": (2.5, 7.6),
    "ad_column": (1.3, 1.3), "loco_tem": (3.0, 16.5), "wagon_box": (3.0, 14.0), "wagon_pass": (3.1, 16.0),
    "bush_big": (2.2, 2.0), "roller": (1.7, 3.6), "ktp": (2.5, 2.0), "outhouse": (1.1, 1.2), "monument": (2.2, 2.2),
    "shed": (3.0, 4.0), "ruin_l": (0.45, 7.0), "ruin_i": (0.45, 5.0), "rack_high": (1.1, 8.0), "deposit_wall": (3.0, 0.5),
    "tractor": (1.5, 3.0), "reel": (1.2, 2.0), "cart_row": (0.0, 0.0), "billboard_fallen": (0.0, 0.0),
    "bus_over": (3.0, 12.0),
}
TIER_COLORS = {"common": (200, 180, 138), "med": (79, 174, 99), "good": (227, 178, 60), "weapon": (196, 73, 59), "quest": (61, 111, 181)}
ROUTE_COLORS = [(64, 140, 220), (230, 140, 40), (150, 90, 200), (40, 170, 160), (120, 120, 120), (210, 80, 140), (100, 160, 60)]


class Grid:
    def __init__(self, bounds: list):
        self.x0, self.z0, self.x1, self.z1 = bounds
        self.nx = int((self.x1 - self.x0) / CELL) + 1
        self.nz = int((self.z1 - self.z0) / CELL) + 1
        self.cells = bytearray(self.nx * self.nz)

    def mark_poly(self, pts: list) -> None:
        xs = [p[0] for p in pts]
        zs = [p[1] for p in pts]
        i0, i1 = max(0, int((min(xs) - self.x0) / CELL)), min(self.nx - 1, int((max(xs) - self.x0) / CELL) + 1)
        j0, j1 = max(0, int((min(zs) - self.z0) / CELL)), min(self.nz - 1, int((max(zs) - self.z0) / CELL) + 1)
        for j in range(j0, j1 + 1):
            z = self.z0 + (j + 0.5) * CELL
            for i in range(i0, i1 + 1):
                x = self.x0 + (i + 0.5) * CELL
                if inside(pts, x, z) or near_poly(pts, x, z, CELL * 0.75):
                    self.cells[j * self.nx + i] = 1

    def blocked(self, x: float, z: float) -> bool:
        i = int((x - self.x0) / CELL)
        j = int((z - self.z0) / CELL)
        if i < 0 or j < 0 or i >= self.nx or j >= self.nz:
            return True
        return self.cells[j * self.nx + i] == 1


def inside(poly: list, x: float, z: float) -> bool:
    c = False
    n = len(poly)
    for k in range(n):
        ax, az = poly[k]
        bx, bz = poly[(k + 1) % n]
        if (az > z) != (bz > z) and x < (bx - ax) * (z - az) / (bz - az + 1e-12) + ax:
            c = not c
    return c


def near_poly(poly: list, x: float, z: float, r: float) -> bool:
    n = len(poly)
    for k in range(n):
        ax, az = poly[k]
        bx, bz = poly[(k + 1) % n]
        dx, dz = bx - ax, bz - az
        t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz + 1e-12)))
        if math.hypot(ax + dx * t - x, az + dz * t - z) < r:
            return True
    return False


def rect_poly(cx: float, cz: float, w: float, d: float, yaw_deg: float) -> list:
    """Прямоугольник w (локальная x) × d (локальная z), поворот как у Godot (Basis(UP, yaw))."""
    a = math.radians(yaw_deg)
    c, s = math.cos(a), math.sin(a)
    out = []
    for (lx, lz) in [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)]:
        out.append((cx + lx * c + lz * s, cz - lx * s + lz * c))
    return out


def build(plan: dict) -> tuple[Grid, list]:
    g = Grid(plan["bounds"])
    footprints = []
    for b in plan["buildings"]:
        if b["kind"] in ("canopy",):
            continue
        w, d = b["size"]
        if b["kind"] == "crane":
            w, d = 2.0, 2.0
        p = rect_poly(b["at"][0], b["at"][1], w, d, b["yaw"])
        g.mark_poly(p)
        footprints.append(p)
    for wl in plan["walls"]:
        if wl["y0"] <= EYE <= wl["y1"]:
            r = wl["rect"]
            g.mark_poly([(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])])
    for bx in plan["boxes"]:
        y, sy = bx["at"][1], bx["size"][1]
        if y - sy / 2 <= EYE <= y + sy / 2 and max(bx["size"][0], bx["size"][2]) > 0.25:
            g.mark_poly(rect_poly(bx["at"][0], bx["at"][2], bx["size"][0], bx["size"][2], bx["yaw"]))
    for r in plan["ramps"]:
        # откос насыпи закрывает взгляд там, где выше глаз
        z_eye = r["z0"] + (r["z1"] - r["z0"]) * (EYE / max(0.01, r["y1"] - r["y0"]))
        if r["y1"] > EYE:
            g.mark_poly([(r["x0"], z_eye), (r["x1"], z_eye), (r["x1"], r["z1"]), (r["x0"], r["z1"])])
    for it in plan["filler"]["items"]:
        kit = it[0]
        if kit not in VIEW_KITS or VIEW_KITS[kit][0] <= 0.0:
            continue
        s = float(it[4]) if len(it) > 4 else 1.0
        dy = float(it[5]) if len(it) > 5 else 0.0
        if dy > EYE:
            continue
        w, d = VIEW_KITS[kit]
        g.mark_poly(rect_poly(it[1], it[2], w * s, d * s, it[3]))
    # за границей — преграда: игроков там нет
    boundary = [tuple(p) for p in plan["boundary"]]
    for j in range(g.nz):
        z = g.z0 + (j + 0.5) * CELL
        for i in range(g.nx):
            if not inside(boundary, g.x0 + (i + 0.5) * CELL, z):
                g.cells[j * g.nx + i] = 1
    return g, footprints


def sightlines(plan: dict, g: Grid, footprints: list) -> dict:
    boundary = [tuple(p) for p in plan["boundary"]]
    pts = []
    x = plan["bounds"][0] + STEP * 0.5
    while x < plan["bounds"][2]:
        z = plan["bounds"][1] + STEP * 0.5
        while z < plan["bounds"][3]:
            # полоса 4 м у границы — не место для боя (за забором никого), вдоль неё лучи не меряем
            if inside(boundary, x, z) and not near_poly(boundary, x, z, 4.0) and not g.blocked(x, z) and z < 248.0:
                pts.append((x, z))
            z += STEP
        x += STEP
    long_rays = []
    total = 0
    worst_by_point = []
    for (px, pz) in pts:
        best = 0.0
        for k in range(RAYS):
            a = 2 * math.pi * k / RAYS
            dx, dz = math.cos(a), math.sin(a)
            t = 0.0
            while t < MAX_RAY:
                t += 0.4
                qx, qz = px + dx * t, pz + dz * t
                if g.blocked(qx, qz):
                    break
            total += 1
            best = max(best, t)
            if t > LONG:
                long_rays.append((px, pz, px + dx * t, pz + dz * t, t))
        worst_by_point.append(best)
    long_rays.sort(key=lambda r: -r[4])
    share = len(long_rays) / max(1, total)
    return {"points": len(pts), "rays": total, "long_rays": len(long_rays), "long_share": round(share, 4),
            "max_m": round(long_rays[0][4], 1) if long_rays else 0.0,
            "points_with_long_view": sum(1 for w in worst_by_point if w > LONG),
            "longest": [[round(v, 1) for v in r] for r in long_rays[:60]], "all_long": long_rays}


def draw(plan: dict, footprints: list, sl: dict) -> None:
    b = plan["bounds"]
    k = 3.0
    W, H = int((b[2] - b[0]) * k), int((b[3] - b[1]) * k) + 120
    img = Image.new("RGB", (W, H), (236, 233, 224))
    d = ImageDraw.Draw(img, "RGBA")

    def P(x: float, z: float) -> tuple:
        return ((x - b[0]) * k, (z - b[1]) * k)

    d.polygon([P(*p) for p in plan["boundary"]], fill=(222, 218, 205), outline=(90, 90, 90))
    for s in plan["surfaces"]:
        r = s["rect"]
        col = {"road": (150, 150, 150), "walk": (205, 200, 188), "parking": (175, 175, 170), "court": (214, 206, 186),
               "grass": (170, 190, 140), "mud": (180, 160, 130)}.get(s["mat"], (210, 205, 195))
        d.rectangle([P(r[0], r[1]), P(r[2], r[3])], fill=col)
    for (x0, z0, x1, z1, _t) in sl["all_long"]:
        d.line([P(x0, z0), P(x1, z1)], fill=(220, 40, 30, 22), width=1)
    for wl in plan["walls"]:
        r = wl["rect"]
        d.rectangle([P(r[0], r[1]), P(r[2], r[3])], fill=(80, 80, 80))
    for p in footprints:
        d.polygon([P(*q) for q in p], fill=(120, 116, 108), outline=(50, 50, 50))
    for it in plan["filler"]["items"]:
        if it[0] in VIEW_KITS and VIEW_KITS[it[0]][0] > 0:
            s = float(it[4]) if len(it) > 4 else 1.0
            w, dd = VIEW_KITS[it[0]]
            d.polygon([P(*q) for q in rect_poly(it[1], it[2], w * s, dd * s, it[3])], fill=(70, 80, 95))
        elif it[0] in ("car", "taxi", "police_car", "suv_open"):
            d.polygon([P(*q) for q in rect_poly(it[1], it[2], 1.9, 4.6, it[3])], fill=(140, 150, 165))
    for i, r in enumerate(plan["probe_routes"]):
        pts = [P(p[0], p[1]) for p in r["points"]]
        d.line(pts, fill=ROUTE_COLORS[i % len(ROUTE_COLORS)] + (220,), width=3)
    for l in plan["loot"]:
        x, z = P(l["at"][0], l["at"][2])
        c = TIER_COLORS.get(l["tier"], (200, 200, 200))
        d.ellipse([x - 4, z - 4, x + 4, z + 4], fill=c, outline=(30, 30, 30))
    try:
        font = ImageFont.truetype("arial.ttf", 22)
        small = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = small = ImageFont.load_default()
    for s in plan["spawns"]:
        x, z = P(*s["at"])
        d.rectangle([x - 8, z - 8, x + 8, z + 8], fill=(61, 111, 181))
        d.text((x + 10, z - 10), "▶ " + s["label"], fill=(30, 60, 120), font=small)
    for e in plan["exits"]:
        x, z = P(*e["at"])
        d.ellipse([x - 9, z - 9, x + 9, z + 9], fill=(60, 155, 90) if e["always"] else (196, 138, 44))
        d.text((x + 11, z - 10), "выход: " + e["label"], fill=(20, 90, 40), font=small)
    for loc in plan["locations"]:
        x, z = P(*loc["at"])
        d.text((x - 20, z - 8), "%d · %s" % (loc["id"], loc["label"]), fill=(20, 20, 20), font=small)
    d.text((16, H - 112), "«Проспект» · левел-дизайн (редакция 5): маршруты проверки — цветные линии, лут — точки (бежевый бытовое, "
           "зелёный медицина, жёлтый ценное, красный оружие), появления — синие квадраты, выходы — зелёные круги", fill=(20, 20, 20), font=font)
    d.text((16, H - 78), "Обзор на высоте глаз 1,7 м: красные лучи — длиннее %d м. Точек %d, лучей %d, длинных %d (%.1f %%), "
           "самый длинный %.0f м; точек, откуда есть обзор > %d м: %d" % (LONG, sl["points"], sl["rays"], sl["long_rays"],
           sl["long_share"] * 100, sl["max_m"], LONG, sl["points_with_long_view"]), fill=(150, 30, 20), font=font)
    d.text((16, H - 44), "мест лута %d · укрытий наполнения %d · построек %d" % (len(plan["loot"]), len(plan["filler"]["cover"]),
           len(plan["buildings"])), fill=(20, 20, 20), font=font)
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT_PNG)


def main() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    g, footprints = build(plan)
    sl = sightlines(plan, g, footprints)
    draw(plan, footprints, sl)
    report = {k: v for k, v in sl.items() if k != "all_long"}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in report.items() if k != "longest"}, ensure_ascii=False))
    for r in report["longest"][:12]:
        print("  %.0f м: (%.0f, %.0f) → (%.0f, %.0f)" % (r[4], r[0], r[1], r[2], r[3]))


if __name__ == "__main__":
    main()
