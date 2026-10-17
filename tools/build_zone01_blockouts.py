# -*- coding: utf-8 -*-
"""Зона 1 «Городской пояс» — блокауты по раскладке data/zone01_layout.json (решение владельца 2026-10-17:
«всю оставшуюся детализацию — блокаутами»).

Пишет scenes/levels/zone01/zone01_layout.tscn. Каждая постройка — отдельный узел StudyBuilding
(src/blockout/study_building.gd: пятиэтажка с подъездом и лестницей, каркас недостроя, ангар, навес,
автобус, кран): в редакторе у узла меняются вид, размер и этажность, его можно двигать и потом заменить
моделью. Мелочи — наборы примитивов UrbanProps (рельсы, вагоны, мостки, заборы, корт, мост путей).
Машины, баки, скамейки и детские площадки — готовые модели проекта.

Вызывается из tools/build_zone01.py (нужны его рельеф и запись сцен); отдельно не запускается.
"""
from __future__ import annotations

import math
import random

# вид раскладки → (вид StudyBuilding, высота этажа); пятиэтажки с подъездом и лестницей — ENTERABLE
KIND = {
    "panel": ("mass", 3.0), "house": ("mass", 3.0), "hall": ("hall", 6.0), "skeleton": ("skeleton", 3.2),
    "shop": ("hall", 3.6), "hut": ("mass", 2.7), "station": ("hall", 4.5), "ruin": ("mass", 1.6),
    "canopy": ("canopy", 3.4),
}
ENTERABLE = {"Panel_E2", "Panel_E6"}
TALL_HALLS = {"Bus_Depot": 8.0, "Rail_Depot": 9.0, "Sport_Hall": 8.0, "Rail_Store": 6.5}

CONCRETE = (0.62, 0.61, 0.58)
STEEL = (0.42, 0.45, 0.46)
RUST = (0.45, 0.33, 0.25)
WOOD = (0.42, 0.33, 0.24)
COURT = (0.41, 0.47, 0.43)
WAGON = (0.38, 0.29, 0.22)


def build(z1, layout: dict) -> dict:
    """Сцена блокаутов; возвращает прямоугольники построек (для площадок рельефа и проверки машин)."""
    s = z1.Scene("Layout")
    study = s.resource("res://src/blockout/study_building.gd", "Script")
    ground = z1.ground
    rng = random.Random(1017)
    footprints: list[tuple[float, float, float, float, float]] = []  # x, z, длина, глубина, угол

    def building(name: str, parent: str, kind: str, x: float, z: float, size, angle: float, floors: int,
                 story: float, label: str) -> None:
        y = min(ground(x + dx, z + dz) for dx, dz in corners(0, 0, size[0], size[1], angle)) - 0.05
        study_node(s, z1, name, parent, study, kind, footprint=z1.v2(size[0], size[1]), floors=floors,
                   story_height=story, label=label, position=z1.v3(x, y, z), rotation_degrees=z1.v3(0, -angle, 0))
        footprints.append((x, z, size[0], size[1], angle))

    # готовые куски — тоже занятое место (машины и площадки их обходят)
    for r in layout["ready"].values():
        xs = [q[0] for q in r["outline"]]
        zs = [q[1] for q in r["outline"]]
        footprints.append(((min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2, max(xs) - min(xs), max(zs) - min(zs), 0.0))

    # --- постройки
    s.node("Buildings")
    for b in layout["buildings"]:
        if b["kind"] == "garage":
            continue  # гаражи у путей — модели кирпичных боксов (ниже)
        kind, story = KIND.get(b["kind"], ("mass", 3.0))
        if b["id"] in ENTERABLE:
            kind = "apartments"
        floors = int(b["floors"])
        if b["id"] in TALL_HALLS:
            story, floors = TALL_HALLS[b["id"]], 1
        elif kind == "hall" and floors > 1:
            story, floors = story * floors, 1  # контора / вокзал — высокий зал с проёмами
        x, z = b["at"]
        building(b["id"], "Buildings", kind, x, z, b["size"], b["angle"], floors, story, b["label"])

    # --- автобусы, кран
    s.node("Buses")
    for i, (x, z) in enumerate(layout["buses"]):
        study_node(s, z1, f"Bus_{i:02}", "Buses", study, "bus", label="Автобус",
               position=z1.v3(x, ground(x, z), z), rotation_degrees=z1.v3(0, -18 + rng.uniform(-6, 6), 0))
    cx, cz = layout["crane"]
    study_node(s, z1, "Crane", "Buildings", study, "crane", label="Башенный кран · 38 м",
           position=z1.v3(cx, ground(cx, cz), cz), rotation_degrees=z1.v3(0, 132, 0))

    # --- гаражи у путей: ряды кирпичных боксов (Sketchfab, ворота на −X модели) воротами в проезд
    s.node("Garages")
    rows: dict[str, list] = {}
    for b in layout["buildings"]:
        if b["kind"] == "garage":
            rows.setdefault(b["id"][:8], []).append(b["at"])
    for r, (key, pts) in enumerate(sorted(rows.items())):
        xs = [p[0] for p in pts]
        zc = pts[0][1]
        yaw = 90.0 if key.endswith("A") else -90.0  # северный ряд воротами на юг, южный — на север
        for k, gx in enumerate((min(xs) + 2.0, max(xs) - 2.0) if max(xs) - min(xs) > 20 else ((min(xs) + max(xs)) / 2,)):
            z1.sf_model(s, f"Row{r}_Block{k}", "sf_garage_row", gx, zc, yaw, "Garages", y=ground(gx, zc) - .05,
                        surface="concrete")

    rail(s, z1, layout)
    swamp(s, z1, layout)
    court(s, z1, layout)
    site_fence(s, z1, layout)
    yards(s, z1, layout, rng, footprints)
    cars(s, z1, layout, rng, footprints)
    s.save(z1.OUT / "zone01_layout.tscn")
    return {"footprints": footprints}


def study_node(s, z1, name: str, parent: str, script, kind: str, **attrs) -> None:
    """Узел StudyBuilding: его свойство «вид» (kind) пишется отдельно — у записи сцен kind означает тип узла."""
    s.node(name, parent, script=script, **attrs)
    s.nodes[-1] += "\nkind = " + z1.gvalue(kind)


def corners(x: float, z: float, length: float, depth: float, angle: float) -> list[tuple[float, float]]:
    a = math.radians(angle)
    ux, uz = math.cos(a), math.sin(a)
    vx, vz = -uz, ux
    return [(x + sx * length / 2 * ux + sy * depth / 2 * vx, z + sx * length / 2 * uz + sy * depth / 2 * vz)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def inside_any(x: float, z: float, footprints, pad: float) -> bool:
    for bx, bz, L, D, ang in footprints:
        a = math.radians(ang)
        dx, dz = x - bx, z - bz
        u = dx * math.cos(a) + dz * math.sin(a)
        v = -dx * math.sin(a) + dz * math.cos(a)
        if abs(u) < L / 2 + pad and abs(v) < D / 2 + pad:
            return True
    return False


def segment_piece(a, b, y0: float, y1: float, width: float, height: float, color, collision=True, lift=0.0) -> dict:
    """Брус от a до b (x, z) с высотой низа y0/y1 — в мировых координатах, для узла UrbanProps в (0, 0, 0)."""
    (ax, az), (bx, bz) = a, b
    length = math.dist(a, b)
    yaw = -math.degrees(math.atan2(bz - az, bx - ax))
    pitch = math.degrees(math.atan2(y1 - y0, length)) if length > 0 else 0.0
    return dict(at=[round((ax + bx) / 2, 3), round((y0 + y1) / 2 + height / 2 + lift, 3), round((az + bz) / 2, 3)],
                size=[round(length + 0.05, 3), round(height, 3), round(width, 3)], color=list(color),
                collision=collision, rotation=[0.0, round(yaw, 2), round(pitch, 2)])


def offset_line(axis, off: float) -> list[tuple[float, float]]:
    out = []
    for i, (x, z) in enumerate(axis):
        a, b = axis[max(i - 1, 0)], axis[min(i + 1, len(axis) - 1)]
        dx, dz = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dz) or 1.0
        out.append((x - dz / ln * off, z + dx / ln * off))
    return out


def densify(points, step: float) -> list[tuple[float, float]]:
    out = []
    for (ax, az), (bx, bz) in zip(points, points[1:]):
        n = max(1, int(math.dist((ax, az), (bx, bz)) / step))
        for i in range(n):
            out.append((ax + (bx - ax) * i / n, az + (bz - az) * i / n))
    out.append(tuple(points[-1]))
    return out


def track_lines(layout: dict) -> list[list[tuple[float, float]]]:
    """Пути: два главных во всю длину; в парке ещё пять, на въездах в парк сходятся к главным."""
    tr = layout["tracks"]
    axis = densify(tr["axis"], 20.0)
    y0, y1 = tr["yard"]["from_z"], tr["yard"]["to_z"]
    n, sp = tr["yard"]["count"], tr["yard"]["spacing"]
    lines = [offset_line(axis, -tr["spacing"] / 2), offset_line(axis, tr["spacing"] / 2)]
    for k in range(n):
        off = (k - (n - 1) / 2) * sp
        if abs(off) < sp * 0.5:
            continue  # средний путь парка совпадает с главными
        main = tr["spacing"] / 2 * (1 if off >= 0 else -1)
        pts = []
        for i, (x, z) in enumerate(axis):
            if not (y0 - 40.0 <= z <= y1 + 40.0):
                continue
            a, b = axis[max(i - 1, 0)], axis[min(i + 1, len(axis) - 1)]
            dx, dz = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(dx, dz) or 1.0
            t = 1.0 if y0 <= z <= y1 else max(0.0, 1.0 - min(abs(z - y0), abs(z - y1)) / 40.0)
            o = main + (off - main) * t
            pts.append((x - dz / ln * o, z + dx / ln * o))
        if len(pts) > 1:
            lines.append(pts)
    return lines


def rail(s, z1, layout: dict) -> None:
    """Рельсы (по паре брусьев на путь), вагоны, пешеходный переход над путями, мост над дорогой к ТЦ."""
    s.node("Rail")
    ground = z1.ground
    pieces = []
    for pts in track_lines(layout):
        for side in (-0.76, 0.76):
            line = offset_line(pts, side)
            for a, b in zip(line, line[1:]):
                pieces.append(segment_piece(a, b, ground(*a), ground(*b), 0.08, 0.16, STEEL, collision=False))
    z1.props(s, "Rails", 0, 0, pieces, "Rail", y=0.0, surface="metal")
    # вагоны на путях парка — укрытия вдоль путей
    tr = layout["tracks"]
    wagons = []
    line = densify(track_lines(layout)[2], 2.0)  # первый путь парка западнее главных
    for (wx, wz) in tr["train"]:
        best = min(line, key=lambda q: math.dist(q, (wx, wz)))
        i = line.index(best)
        a, b = line[max(i - 1, 0)], line[min(i + 1, len(line) - 1)]
        yaw = -math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        y = ground(*best)
        wagons.append(dict(at=[round(best[0], 2), round(y + 2.45, 2), round(best[1], 2)], size=[14.0, 3.6, 3.2],
                           color=list(WAGON), collision=True, rotation=[0, round(yaw, 1), 0]))
        wagons.append(dict(at=[round(best[0], 2), round(y + 0.45, 2), round(best[1], 2)], size=[12.0, 0.9, 2.2],
                           color=[0.2, 0.2, 0.2], collision=True, rotation=[0, round(yaw, 1), 0]))
    z1.props(s, "Wagons", 0, 0, wagons, "Rail", y=0.0, surface="metal")
    # пешеходный переход над путями: настил на 6,5 м, лестницы с обеих сторон
    fb = tr["footbridge"]
    (fx, fz), (L, W), ang = fb["at"], fb["size"], fb["angle"]
    a = math.radians(ang)
    ux, uz = math.cos(a), math.sin(a)
    deck = 6.5
    end_a = (fx - ux * L / 2, fz - uz * L / 2)
    end_b = (fx + ux * L / 2, fz + uz * L / 2)
    ga, gb = ground(*end_a), ground(*end_b)
    stair = 14.0
    in_a = (end_a[0] + ux * stair, end_a[1] + uz * stair)
    in_b = (end_b[0] - ux * stair, end_b[1] - uz * stair)
    top = max(ga, gb) + deck
    fbp = [segment_piece(in_a, in_b, top, top, W, 0.35, CONCRETE),
           segment_piece(end_a, in_a, ga, top, W - 0.6, 0.3, CONCRETE),
           segment_piece(in_b, end_b, top, gb, W - 0.6, 0.3, CONCRETE)]
    for side in (-1, 1):
        rail_a = (in_a[0] - uz * side * W / 2, in_a[1] + ux * side * W / 2)
        rail_b = (in_b[0] - uz * side * W / 2, in_b[1] + ux * side * W / 2)
        fbp.append(segment_piece(rail_a, rail_b, top + 0.35, top + 0.35, 0.08, 1.1, STEEL))
    for p in (in_a, in_b):
        fbp.append(dict(at=[round(p[0], 2), round((ground(*p) + top) / 2, 2), round(p[1], 2)],
                        size=[1.0, round(top - ground(*p), 2), 1.0], color=list(CONCRETE), collision=True))
    z1.props(s, "Footbridge", 0, 0, fbp, "Rail", y=0.0)
    # мост путей над дорогой к ТЦ: пролёт на опорах, дорога проходит под ним
    br = tr["bridge"]
    (bx, bz), (bl, bw), bang = br["at"], br["size"], br["angle"]
    top = z1.RAIL_BRIDGE_TOP
    a = math.radians(bang)
    ux, uz = math.cos(a), math.sin(a)
    pa = (bx - ux * bl / 2, bz - uz * bl / 2)
    pb = (bx + ux * bl / 2, bz + uz * bl / 2)
    bp = [segment_piece(pa, pb, top - 1.2, top - 1.2, bw, 1.2, CONCRETE)]
    for p in (pa, pb):
        g = ground(*p)
        bp.append(dict(at=[round(p[0], 2), round((g + top - 1.2) / 2, 2), round(p[1], 2)],
                       size=[2.0, round(top - 1.2 - g, 2), bw], color=list(CONCRETE), collision=True,
                       rotation=[0, round(-bang, 1), 0]))
    z1.props(s, "RailBridge", 0, 0, bp, "Rail", y=0.0)


def swamp(s, z1, layout: dict) -> None:
    """Мостки через воду болота: настил на сваях чуть выше глади."""
    s.node("Swamp")
    water = z1.SWAMP_WATER
    pieces = []
    pts = densify(layout["boardwalk"], 4.0)
    for a, b in zip(pts, pts[1:]):
        y = max(water + 0.45, min(z1.ground(*a), z1.ground(*b)) + 0.25)
        pieces.append(segment_piece(a, b, y, y, 1.8, 0.12, WOOD))
        pieces.append(dict(at=[round(a[0], 2), round(water - 0.4, 2), round(a[1], 2)], size=[0.22, round(y - water + 1.2, 2), 0.22],
                           shape="cylinder", color=list(WOOD), collision=False))
    z1.props(s, "Boardwalk", 0, 0, pieces, "Swamp", y=0.0, surface="wood")


def court(s, z1, layout: dict) -> None:
    """Спортплощадка: покрытие, сетчатая ограда на столбах, ворота и щиты."""
    s.node("Court")
    c = layout["court"]
    (x, z), (L, D), ang = c["at"], c["size"], c["angle"]
    y = z1.ground(x, z)
    pieces = [dict(at=[0, 0.04, 0], size=[L, 0.08, D], color=list(COURT), collision=False)]
    for sx in (-1, 1):
        pieces.append(dict(at=[sx * (L / 2 - 1.2), 1.0, 0], size=[0.12, 2.0, 3.0], color=[0.85, 0.85, 0.82], collision=True))
    # стороны ограды: (центр, длина, вдоль X) — на длинных сторонах проходы по 6 м посередине
    sides = [((sx * L / 2, 0.0), D, False) for sx in (-1, 1)]
    sides += [((half * (L / 4 + 1.5), sz * D / 2), L / 2 - 3, True) for sz in (-1, 1) for half in (-1, 1)]
    for (cx, cz), length, along_x in sides:
        size_wall = [length, 3.2, 0.06] if along_x else [0.06, 3.2, length]
        pieces.append(dict(at=[cx, 1.6, cz], size=size_wall, collision=True, render=False))
        rail = [length, 0.06, 0.06] if along_x else [0.06, 0.06, length]
        for h in (0.25, 1.6, 3.15):
            pieces.append(dict(at=[cx, h, cz], size=rail, color=list(STEEL), collision=False, shadow=False))
        n = max(2, int(length / 3.5))
        for k in range(n + 1):
            t = -length / 2 + length * k / n
            px, pz = (cx + t, cz) if along_x else (cx, cz + t)
            pieces.append(dict(at=[px, 1.6, pz], size=[0.07, 3.2, 0.07], color=list(STEEL), collision=False))
    z1.props(s, "Field", x, z, pieces, "Court", yaw=-ang, y=y)


def site_fence(s, z1, layout: dict) -> None:
    """Забор стройки из бетонных плит по контуру площадки, с двумя проходами."""
    s.node("SiteFence")
    poly = layout["site"] + layout["site"][:1]
    pieces = []
    for i, (a, b) in enumerate(zip(poly, poly[1:])):
        length = math.dist(a, b)
        gap_at = 0.5 if i in (1, 3) else None  # проходы на востоке и западе
        cuts = [(0.0, 1.0)] if gap_at is None else [(0.0, gap_at - 6 / length), (gap_at + 6 / length, 1.0)]
        for t0, t1 in cuts:
            pa = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
            pb = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
            for seg_a, seg_b in zip(densify([pa, pb], 8.0), densify([pa, pb], 8.0)[1:]):
                pieces.append(segment_piece(seg_a, seg_b, z1.ground(*seg_a) - 0.1, z1.ground(*seg_b) - 0.1, 0.18, 2.3, CONCRETE))
    z1.props(s, "Fence", 0, 0, pieces, "SiteFence", y=0.0)


def yards(s, z1, layout: dict, rng: random.Random, footprints) -> None:
    """Дворы панелек и частного сектора: детские площадки, скамейки, баки (модели проекта)."""
    s.node("Yards")
    spots = [((-52.0, 2.0), 0.0), ((-98.0, 30.0), 0.0), ((-58.0, 30.0), 15.0), ((-140.0, 72.0), 0.0),
             ((-48.0, -55.0), 0.0)]
    placed = 0
    for i, ((x, z), yaw) in enumerate(spots):
        if inside_any(x, z, footprints, 7.0) or placed >= 3:
            continue
        placed += 1
        y = z1.ground(x, z)
        s.node(f"Play_{i}", "Yards", kind="Node3D", position=z1.v3(x, y, z), rotation_degrees=z1.v3(0, yaw, 0))
        model(s, z1, f"Play_{i}", "Swing", "play_swing", -3.0, 0.0, 0.0)
        model(s, z1, f"Play_{i}", "Carousel", "play_carousel", 3.0, 1.0, 0.0)
        for k, (bx, bz) in enumerate(((-4.0, 5.0), (4.0, 5.0), (0.0, -5.0))):
            model(s, z1, f"Play_{i}", f"Bench_{k}", "bench_back", bx, bz, 180.0 if bz > 0 else 0.0)
    # мусорные баки у торцов пятиэтажек
    n = 0
    for b in layout["buildings"]:
        if b["kind"] != "panel":
            continue
        (x, z), (L, D), ang = b["at"], b["size"], b["angle"]
        a = math.radians(ang)
        px = x + math.cos(a) * (L / 2 + 4.0)
        pz = z + math.sin(a) * (L / 2 + 4.0)
        if inside_any(px, pz, footprints, 1.0):
            continue
        z1.sf_model(s, f"Bins_{n}", rng.choice(["sf_dumpster_a", "sf_dumpster_b", "sf_dumpster_tipped"]), px, pz,
                    -ang + 90, "Yards")
        n += 1


def model(s, z1, parent: str, name: str, key: str, x: float, z: float, yaw: float) -> None:
    s.node(name, f"Yards/{parent}", kind="StaticBody3D", script=s.resource("res://src/world/district_model.gd", "Script"),
           position=z1.v3(x, 0, z), rotation_degrees=z1.v3(0, yaw, 0), model=f"res://assets/zone01/models/{key}.glb",
           manifest="res://assets/zone01/models/props.json", surface="metal", materials_dir="")


def cars(s, z1, layout: dict, rng: random.Random, footprints) -> None:
    """Брошенные машины: у обочин улиц (как на картинке) и на стоянке автобазы."""
    s.node("Cars")
    n = 0
    taken: list[tuple[float, float]] = []
    junctions = [tuple(r["points"][0]) for r in layout["roads"]] + [tuple(r["points"][-1]) for r in layout["roads"]]
    for r in layout["roads"]:
        if r["dirt"] or r["id"] in ("mall",):
            continue
        pts = densify(r["points"], 2.0)
        i = 8
        while i < len(pts) - 8:
            if rng.random() < 0.22:
                a, b = pts[i - 1], pts[i + 1]
                dx, dz = b[0] - a[0], b[1] - a[1]
                ln = math.hypot(dx, dz) or 1.0
                side = rng.choice((-1, 1))
                off = r["width"] / 2 - 1.1
                x, z = pts[i][0] - dz / ln * off * side, pts[i][1] + dx / ln * off * side
                yaw = -math.degrees(math.atan2(dz, dx)) + (180 if side < 0 else 0) + rng.uniform(-6, 6)
                if (not inside_any(x, z, footprints, 2.0) and all(math.dist((x, z), t) > 7.0 for t in taken)
                        and all(math.dist((x, z), j) > 14.0 for j in junctions)):
                    z1.car(s, f"Car_{n:02}", x, z, yaw, parent="Cars")
                    taken.append((x, z))
                    n += 1
                i += 6
            else:
                i += 3
    # стоянка у автобазы: ряд легковых вдоль южного края площадки автостанции
    for k in range(9):
        x, z = -70.0 + k * 3.2, 241.0
        if rng.random() < 0.7 and not inside_any(x, z, footprints, 1.5):
            z1.car(s, f"Lot_{k}", x, z, 90.0 + rng.uniform(-8, 8), parent="Cars")
