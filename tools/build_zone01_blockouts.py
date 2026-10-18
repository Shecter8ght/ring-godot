# -*- coding: utf-8 -*-
"""Зона 1 «Городской пояс» — блокауты по раскладке data/zone01_layout.json (решение владельца 2026-10-17:
«всю оставшуюся детализацию — блокаутами»; второй проход по кадрам картинки и «урбанизм» — 2026-10-18).

Пишет scenes/levels/zone01/zone01_layout.tscn. Каждая постройка — отдельный узел StudyBuilding
(src/blockout/study_building.gd: жилой дом с подъездом и лестницей, каркас недостроя, ангар, навес,
автобус, кран): в редакторе у узла меняются вид, размер и этажность, его можно двигать и потом заменить
моделью. Вывески — Label3D на фасадах. Мелочи — наборы примитивов UrbanProps под узлом Small (группа
urban_prop_batches: уровень склеивает их PropBatcher-ом, дальше 110 м не рисуются): рельсы, вагоны, мостки,
корт, забор стройки, остановки и ларьки, теплотрасса, хлам у домов. Крупное, что видно издалека, — эстакада,
контактная сеть, мосты, высотки за лесом — отдельно. Машины, баки, фонари, скамейки, детские площадки,
сухостой — готовые модели проекта.

Вызывается из tools/build_zone01.py (нужны его рельеф и запись сцен); отдельно не запускается.
"""
from __future__ import annotations

import math
import random

# вид раскладки → (вид StudyBuilding, высота этажа); жилые дома с подъездом и лестницей — ENTERABLE
KIND = {
    "panel": ("mass", 3.0), "house": ("mass", 3.0), "hall": ("hall", 6.0), "skeleton": ("skeleton", 3.2),
    "shop": ("hall", 3.6), "hut": ("mass", 2.7), "station": ("hall", 4.5), "ruin": ("mass", 1.6),
    "canopy": ("canopy", 3.4), "market": ("hall", 5.5), "office": ("apartments", 3.2), "cinema": ("hall", 9.0),
}
ENTERABLE = {"Panel_E2", "Panel_E6"}
TALL_HALLS = {"Bus_Depot": 8.0, "Rail_Depot": 9.0, "Sport_Hall": 8.0, "Rail_Store": 6.5}
# у этих мест фонари горят в сумерки и ночью (остальные разбиты — город брошен; и свет дорогой)
LIT_NEAR = ("Bus_Terminal", "Cinema", "Supermarket", "Admin")
LIT_MAX = 12

CONCRETE = (0.62, 0.61, 0.58)
DARK_CONCRETE = (0.45, 0.45, 0.43)
STEEL = (0.42, 0.45, 0.46)
RUST = (0.45, 0.33, 0.25)
WOOD = (0.42, 0.33, 0.24)
COURT = (0.41, 0.47, 0.43)
WAGON = (0.38, 0.29, 0.22)
GLASS = (0.55, 0.62, 0.64)
PIPE = (0.6, 0.6, 0.55)
DEBRIS = (0.36, 0.34, 0.31)
SIGN_TEXT = "Color(0.93, 0.86, 0.7, 1)"
SIGN_OUTLINE = "Color(0.14, 0.1, 0.08, 1)"
PROPS_MANIFEST = "res://assets/zone01/models/props.json"


def build(z1, layout: dict) -> dict:
    """Сцена блокаутов; возвращает прямоугольники построек (для площадок рельефа и проверки машин)."""
    s = z1.Scene("Layout")
    study = s.resource("res://src/blockout/study_building.gd", "Script")
    ground = z1.ground
    rng = random.Random(1017)
    footprints: list[tuple[float, float, float, float, float]] = []  # x, z, длина, глубина, угол

    def building(name: str, parent: str, kind: str, x: float, z: float, size, angle: float, floors: int,
                 story: float, label: str, sign: str = "") -> None:
        y = min(ground(x + dx, z + dz) for dx, dz in corners(0, 0, size[0], size[1], angle)) - 0.05
        study_node(s, z1, name, parent, study, kind, footprint=z1.v2(size[0], size[1]), floors=floors,
                   story_height=story, label=label, position=z1.v3(x, y, z), rotation_degrees=z1.v3(0, -angle, 0))
        footprints.append((x, z, size[0], size[1], angle))
        if sign:
            # вывеска на обоих длинных фасадах: у залов — под карнизом, у многоэтажных — над первым этажом
            h = story * floors - 1.0 if kind in ("hall", "canopy") else story + 0.5
            size_font = 56 if size[0] >= 24 else 44
            for k, (dz, yaw) in enumerate(((size[1] / 2 + 0.06, 0.0), (-size[1] / 2 - 0.06, 180.0))):
                s.node(f"Sign_{k}", f"{parent}/{name}", kind="Label3D", text=sign, font_size=size_font, pixel_size=0.02,
                       outline_size=10, modulate=z1.Raw(SIGN_TEXT), outline_modulate=z1.Raw(SIGN_OUTLINE),
                       double_sided=False, position=z1.v3(0, h, dz), rotation_degrees=z1.v3(0, yaw, 0))

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
        building(b["id"], "Buildings", kind, x, z, b["size"], b["angle"], floors, story, b["label"], b.get("sign", ""))

    # --- автобусы, кран
    s.node("Buses")
    for i, (x, z) in enumerate(layout["buses"]):
        yaw = -18 + rng.uniform(-6, 6) if z < 236 else rng.uniform(-8, 8)  # под эстакадой — вдоль неё
        study_node(s, z1, f"Bus_{i:02}", "Buses", study, "bus", label="Автобус",
                   position=z1.v3(x, ground(x, z), z), rotation_degrees=z1.v3(0, yaw, 0))
        footprints.append((x, z, 12.0, 2.6, -yaw))
    cx, cz = layout["crane"]
    study_node(s, z1, "Crane", "Buildings", study, "crane", label="Башенный кран · 38 м",
               position=z1.v3(cx, ground(cx, cz), cz), rotation_degrees=z1.v3(0, 132, 0))
    footprints.append((cx, cz, 6.0, 6.0, 0.0))

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
        footprints.append(((min(xs) + max(xs)) / 2, zc, max(xs) - min(xs) + 6, 7.0, 0.0))

    # мелочи — под узлом, который уровень склеивает PropBatcher-ом
    s.node("Small", groups=["urban_prop_batches"])
    rail(s, z1, layout)
    catenary(s, z1, layout)
    overpass(s, z1, layout, footprints, rng)
    swamp(s, z1, layout, rng)
    court(s, z1, layout)
    site_fence(s, z1, layout)
    bus_stops(s, z1, layout, footprints)
    pipes(s, z1, layout, footprints)
    lamps(s, z1, layout, footprints)
    yards(s, z1, layout, rng, footprints)
    cars(s, z1, layout, rng, footprints)
    clutter(s, z1, layout, rng, footprints)
    skyline(s, z1, study)
    s.save(z1.OUT / "zone01_layout.tscn")
    return {"footprints": footprints}


def study_node(s, z1, name: str, parent: str, script, kind: str, **attrs) -> None:
    """Узел StudyBuilding: его свойство «вид» (kind) пишется отдельно — у записи сцен kind означает тип узла."""
    s.node(name, parent, script=script, **attrs)
    s.nodes[-1] += "\nkind = " + z1.gvalue(kind)


def prop_model(s, z1, parent: str, name: str, key: str, x: float, z: float, yaw: float, y: float | None = None,
               surface: str = "metal", extra: str = "") -> None:
    """Модель из набора пропсов зоны 1 (assets/zone01/models/props.json): фонарь, скамейка, качели."""
    gy = z1.ground(x, z) if y is None else y
    s.node(name, parent, kind="StaticBody3D", script=s.resource("res://src/world/district_model.gd", "Script"),
           position=z1.v3(x, gy, z), rotation_degrees=z1.v3(0, yaw, 0), model=f"res://assets/zone01/models/{key}.glb",
           manifest=PROPS_MANIFEST, surface=surface)
    if extra:
        s.nodes[-1] += "\n" + extra


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


def point_in(poly, x: float, z: float) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        (x0, z0), (x1, z1_) = poly[i], poly[(i + 1) % n]
        if (z0 > z) != (z1_ > z) and x < (x1 - x0) * (z - z0) / ((z1_ - z0) or 1e-9) + x0:
            inside = not inside
    return inside


def dist_poly(pts, x: float, z: float) -> tuple[float, tuple[float, float], tuple[float, float]]:
    """Расстояние до ломаной, ближайшая точка и направление отрезка в ней."""
    best = (1e9, (x, z), (1.0, 0.0))
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        dx, dz = bx - ax, bz - az
        ln2 = dx * dx + dz * dz or 1e-9
        t = max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / ln2))
        cx, cz = ax + t * dx, az + t * dz
        d = math.hypot(x - cx, z - cz)
        if d < best[0]:
            ln = math.sqrt(ln2)
            best = (d, (cx, cz), (dx / ln, dz / ln))
    return best


def near_road(layout: dict, x: float, z: float, extra: float, paved_only: bool = True) -> bool:
    for r in layout["roads"]:
        if paved_only and r["dirt"]:
            continue
        if dist_poly(r["points"], x, z)[0] < r["width"] / 2 + extra:
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


def tube_piece(a, b, y0: float, y1: float, diameter: float, color, collision=False) -> dict:
    """Труба (цилиндр) от a на высоте y0 до b на высоте y1 — ось цилиндра Y кладётся вдоль отрезка."""
    (ax, az), (bx, bz) = a, b
    flat = math.dist(a, b)
    length = math.hypot(flat, y1 - y0)
    yaw = -math.degrees(math.atan2(bz - az, bx - ax))
    pitch = math.degrees(math.atan2(y1 - y0, flat)) if flat > 0 else 90.0
    return dict(at=[round((ax + bx) / 2, 3), round((y0 + y1) / 2, 3), round((az + bz) / 2, 3)],
                size=[round(diameter, 3), round(length + 0.04, 3), round(diameter, 3)], shape="cylinder",
                color=list(color), collision=collision, rotation=[0.0, round(yaw, 2), round(pitch - 90.0, 2)])


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
    """Рельсы (по паре брусьев на путь), вагоны и тепловоз, переход над путями, мост над дорогой к ТЦ."""
    s.node("Rail")
    ground = z1.ground
    pieces = []
    for pts in track_lines(layout):
        for side in (-0.76, 0.76):
            line = offset_line(pts, side)
            for a, b in zip(line, line[1:]):
                pieces.append(segment_piece(a, b, ground(*a), ground(*b), 0.08, 0.16, STEEL, collision=False))
    z1.props(s, "Rails", 0, 0, pieces, "Small", y=0.0, surface="metal")
    # состав на пути парка: тепловоз (с кабиной и капотом) и вагоны — укрытия вдоль путей
    tr = layout["tracks"]
    wagons = []
    line = densify(track_lines(layout)[2], 2.0)  # первый путь парка западнее главных
    for k, (wx, wz) in enumerate(tr["train"]):
        best = min(line, key=lambda q: math.dist(q, (wx, wz)))
        i = line.index(best)
        a, b = line[max(i - 1, 0)], line[min(i + 1, len(line) - 1)]
        yaw = -math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        y = ground(*best)
        body = (0.62, 0.42, 0.16) if k == 0 else WAGON
        wagons.append(dict(at=[round(best[0], 2), round(y + 2.45, 2), round(best[1], 2)],
                           size=[14.0, 3.6 if k else 2.6, 3.2 if k else 2.9], color=list(body), collision=True,
                           rotation=[0, round(yaw, 1), 0]))
        if k == 0:  # кабина тепловоза
            wagons.append(dict(at=[round(best[0], 2), round(y + 3.6, 2), round(best[1], 2)], size=[3.0, 1.6, 3.1],
                               color=[0.55, 0.38, 0.15], collision=True, rotation=[0, round(yaw, 1), 0]))
        wagons.append(dict(at=[round(best[0], 2), round(y + 0.45, 2), round(best[1], 2)], size=[12.0, 0.9, 2.2],
                           color=[0.2, 0.2, 0.2], collision=True, rotation=[0, round(yaw, 1), 0]))
    z1.props(s, "Wagons", 0, 0, wagons, "Small", y=0.0, surface="metal")
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


def catenary(s, z1, layout: dict) -> None:
    """Контактная сеть: опоры по обе стороны полотна через 45 м, ригели поперёк, провод над каждым путём."""
    ground = z1.ground
    tr = layout["tracks"]
    axis = densify(tr["axis"], 45.0)
    y0, y1 = tr["yard"]["from_z"], tr["yard"]["to_z"]
    yard_half = (tr["yard"]["count"] - 1) / 2 * tr["yard"]["spacing"]
    (bx, bz) = tr["bridge"]["at"]
    pieces = []
    for i, (x, z) in enumerate(axis):
        if math.dist((x, z), (bx, bz)) < 14.0 or abs(x) > 296 or abs(z) > 296:
            continue  # у моста над дорогой и за краем карты опор нет
        a, b = axis[max(i - 1, 0)], axis[min(i + 1, len(axis) - 1)]
        dx, dz = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dz) or 1.0
        nx, nz = -dz / ln, dx / ln
        t = 1.0 if y0 <= z <= y1 else max(0.0, 1.0 - min(abs(z - y0), abs(z - y1)) / 40.0)
        half = tr["spacing"] / 2 + (yard_half - tr["spacing"] / 2) * t + 3.2
        g = ground(x, z)
        top = g + 8.2
        masts = [(x + nx * half, z + nz * half), (x - nx * half, z - nz * half)]
        for mx, mz in masts:
            mg = ground(mx, mz)
            pieces.append(dict(at=[round(mx, 2), round((mg + top) / 2, 2), round(mz, 2)], size=[0.35, round(top - mg, 2), 0.35],
                               color=list(DARK_CONCRETE), collision=True))
        pieces.append(segment_piece(masts[0], masts[1], top - 0.4, top - 0.4, 0.25, 0.35, STEEL, collision=False))
    for line in track_lines(layout):
        pts = densify(line, 45.0)
        for a, b in zip(pts, pts[1:]):
            if math.dist(a, (bx, bz)) < 14.0 or math.dist(b, (bx, bz)) < 14.0:
                continue
            pieces.append(segment_piece(a, b, ground(*a) + 6.3, ground(*b) + 6.3, 0.05, 0.05, STEEL, collision=False))
    z1.props(s, "Catenary", 0, 0, pieces, "Rail", y=0.0, surface="metal")


def overpass(s, z1, layout: dict, footprints, rng: random.Random) -> None:
    """Эстакада: бетонная дорога на опорах (кадры «автостанция» и «к ТЦ»). С запада — съезд на площадку
    автостанции, дальше настил на постоянной высоте над автобусами, улицей и путями; по ней можно пройти."""
    ground = z1.ground
    s.node("Overpass")
    ov = layout["overpass"]
    pts = densify(ov["points"], 10.0)
    dist = [0.0]
    for a, b in zip(pts, pts[1:]):
        dist.append(dist[-1] + math.dist(a, b))
    ramp_pt = tuple(ov["points"][ov["ramp_end"]])
    ramp_len = dist[min(range(len(pts)), key=lambda i: math.dist(pts[i], ramp_pt))]
    level = max(ground(*p) for p, d in zip(pts, dist) if d >= ramp_len) + ov["height"]
    g0 = ground(*pts[0]) + 0.05
    ys = [g0 + (level - g0) * (3 * (d / ramp_len) ** 2 - 2 * (d / ramp_len) ** 3) if d < ramp_len else level for d in dist]
    w = ov["width"]
    pieces = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        pieces.append(segment_piece(a, b, ys[i] - 0.9, ys[i + 1] - 0.9, w, 0.9, CONCRETE))
        for side in (-1, 1):
            pa, pb = offset_line([a, b], side * (w / 2 - 0.15))
            pieces.append(segment_piece(pa, pb, ys[i], ys[i + 1], 0.3, 1.0, DARK_CONCRETE))
    tracks = track_lines(layout)
    d = ov["span"] / 2
    while d < dist[-1]:
        i = max(k for k in range(len(dist)) if dist[k] <= d)
        i = min(i, len(pts) - 2)
        t = (d - dist[i]) / max(dist[i + 1] - dist[i], 1e-6)
        x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t
        z = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t
        y = ys[i] + (ys[i + 1] - ys[i]) * t
        dx, dz = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
        ln = math.hypot(dx, dz) or 1.0
        nx, nz = -dz / ln, dx / ln
        if y - ground(x, z) > 3.0 and abs(x) < 300:
            ok = True
            cols = [(x + nx * side * 3.4, z + nz * side * 3.4) for side in (-1, 1)]
            for cx, cz in cols:
                if (inside_any(cx, cz, footprints, 1.2) or near_road(layout, cx, cz, 1.0)
                        or any(dist_poly(tl, cx, cz)[0] < 3.2 for tl in tracks)):
                    ok = False
            if ok:
                for cx, cz in cols:
                    g = ground(cx, cz)
                    pieces.append(dict(at=[round(cx, 2), round((g + y - 0.9) / 2, 2), round(cz, 2)],
                                       size=[1.3, round(y - 0.9 - g, 2), 1.3], color=list(DARK_CONCRETE), collision=True))
                    footprints.append((cx, cz, 1.3, 1.3, 0.0))
                pieces.append(segment_piece(cols[0], cols[1], y - 1.9, y - 1.9, 1.6, 1.0, DARK_CONCRETE))
                d += ov["span"]
                continue
        d += 4.0  # опора не встала (дом, дорога, путь) — пробуем чуть дальше
    z1.props(s, "Deck", 0, 0, pieces, "Overpass", y=0.0)
    # брошенные машины на настиле
    for k, frac in enumerate((0.42, 0.58, 0.77)):
        dd = dist[-1] * frac
        i = max(j for j in range(len(dist)) if dist[j] <= dd)
        x, z = pts[i]
        yaw = -math.degrees(math.atan2(pts[min(i + 1, len(pts) - 1)][1] - z, pts[min(i + 1, len(pts) - 1)][0] - x))
        z1.sf_model(s, f"DeckCar_{k}", "sf_car_burned" if k == 1 else "sf_vaz2104", x + rng.uniform(-3, 3), z,
                    yaw + 90 + rng.uniform(-15, 15), "Overpass", y=ys[i])


def swamp(s, z1, layout: dict, rng: random.Random) -> None:
    """Болото: мостки на сваях над водой, сухостой в воде (модель сухого дерева)."""
    s.node("Swamp")
    water = z1.SWAMP_WATER
    pieces = []
    pts = densify(layout["boardwalk"], 4.0)
    for a, b in zip(pts, pts[1:]):
        y = max(water + 0.45, min(z1.ground(*a), z1.ground(*b)) + 0.25)
        pieces.append(segment_piece(a, b, y, y, 1.8, 0.12, WOOD))
        pieces.append(dict(at=[round(a[0], 2), round(water - 0.4, 2), round(a[1], 2)], size=[0.22, round(y - water + 1.2, 2), 0.22],
                           shape="cylinder", color=list(WOOD), collision=False))
    z1.props(s, "Boardwalk", 0, 0, pieces, "Small", y=0.0, surface="wood")
    poly = layout["swamp"]
    xs = [p[0] for p in poly]
    zs = [p[1] for p in poly]
    n = 0
    z = min(zs)
    while z < max(zs) and n < 55:
        x = min(xs)
        while x < max(xs) and n < 55:
            px, pz = x + rng.uniform(-3, 3), z + rng.uniform(-3, 3)
            g = z1.ground(px, pz)
            if point_in(poly, px, pz) and g < water - 0.15 and rng.random() < 0.35:
                z1.sf_model(s, f"DeadTree_{n:02}", "sf_dead_tree", px, pz, rng.uniform(0, 360), "Swamp", y=g - 0.3,
                            surface="wood")
                n += 1
            x += 11.0
        z += 11.0


def court(s, z1, layout: dict) -> None:
    """Спортплощадка: покрытие, сетчатая ограда на столбах, ворота и щиты."""
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
            pieces.append(dict(at=[cx, h, cz], size=rail, color=list(RUST), collision=False, shadow=False))
        n = max(2, int(length / 3.5))
        for k in range(n + 1):
            t = -length / 2 + length * k / n
            px, pz = (cx + t, cz) if along_x else (cx, cz + t)
            pieces.append(dict(at=[px, 1.6, pz], size=[0.07, 3.2, 0.07], color=list(RUST), collision=False))
    # баскетбольные щиты на стойках
    for sx in (-1, 1):
        pieces.append(dict(at=[sx * (L / 2 - 4), 1.6, 0], size=[0.12, 3.2, 0.12], color=list(STEEL), collision=True))
        pieces.append(dict(at=[sx * (L / 2 - 4.6), 3.2, 0], size=[0.05, 1.05, 1.8], color=[0.8, 0.8, 0.78], collision=False))
    z1.props(s, "Field", x, z, pieces, "Small", yaw=-ang, y=y)


def site_fence(s, z1, layout: dict) -> None:
    """Забор стройки из бетонных плит по контуру площадки, с двумя проходами."""
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
    z1.props(s, "SiteFence", 0, 0, pieces, "Small", y=0.0)


def _road_side(layout: dict, x: float, z: float):
    """Ближайшая асфальтовая улица: (дорога, ближайшая точка, направление)."""
    best = None
    for r in layout["roads"]:
        if r["dirt"]:
            continue
        d, c, u = dist_poly(r["points"], x, z)
        if best is None or d < best[0]:
            best = (d, r, c, u)
    return best[1], best[2], best[3]


def bus_stops(s, z1, layout: dict, footprints) -> None:
    """Остановки: павильон с лавкой и знаком у обочины, рядом через одну — ларёк с вывеской."""
    s.node("BusStops")
    kiosks = ["ПЕЧАТЬ", "ЦВЕТЫ", "ПРОДУКТЫ 24", "ШАУРМА"]
    for i, (x, z, side) in enumerate(layout["bus_stops"]):
        road, (cx, cz), (ux, uz) = _road_side(layout, x, z)
        nx, nz = -uz, ux
        off = road["width"] / 2 + 4.2
        px, pz = cx + nx * side * off, cz + nz * side * off
        tx, tz = -nx * side, -nz * side  # к дороге
        yaw = math.degrees(math.atan2(-tx, -tz))  # открытой стороной (−Z узла) к дороге
        pieces = [dict(at=[0, 2.6, 0], size=[4.6, 0.12, 2.0], color=list(STEEL), collision=True),
                  dict(at=[0, 1.3, 0.95], size=[4.6, 2.5, 0.06], color=list(GLASS), collision=True),
                  dict(at=[-2.27, 1.3, 0.2], size=[0.06, 2.5, 1.5], color=list(GLASS), collision=True),
                  dict(at=[2.27, 1.3, 0.2], size=[0.06, 2.5, 1.5], color=list(GLASS), collision=True),
                  dict(at=[3.4, 1.5, -0.6], size=[0.08, 3.0, 0.08], shape="cylinder", color=list(STEEL), collision=True),
                  dict(at=[3.4, 2.75, -0.6], size=[0.55, 0.55, 0.05], color=[0.85, 0.82, 0.3], collision=False)]
        if i % 2 == 0:  # ларёк
            pieces += [dict(at=[-5.2, 1.3, 0.2], size=[3.0, 2.6, 2.4], color=[0.55, 0.6, 0.62], collision=True),
                       dict(at=[-5.2, 2.75, 0.2], size=[3.4, 0.2, 2.8], color=list(STEEL), collision=False)]
        node = z1.props(s, f"Stop_{i}", px, pz, pieces, "Small", yaw=yaw)
        prop_model(s, z1, f"Small/Stop_{i}", "Bench", "bench_plain", 0.0, 0.35, 180.0, y=0.0, surface="wood")
        s.node("Sign", node, kind="Label3D", text="ОСТАНОВКА", font_size=32, pixel_size=0.02, outline_size=8,
               modulate=z1.Raw(SIGN_TEXT), outline_modulate=z1.Raw(SIGN_OUTLINE), double_sided=False,
               position=z1.v3(0, 2.85, -1.02), rotation_degrees=z1.v3(0, 180, 0))
        if i % 2 == 0:
            s.node("KioskSign", node, kind="Label3D", text=kiosks[(i // 2) % len(kiosks)], font_size=30, pixel_size=0.02,
                   outline_size=8, modulate=z1.Raw(SIGN_TEXT), outline_modulate=z1.Raw(SIGN_OUTLINE), double_sided=False,
                   position=z1.v3(-5.2, 2.3, -1.02), rotation_degrees=z1.v3(0, 180, 0))
        footprints.append((px, pz, 11.0, 3.0, -yaw))


def pipes(s, z1, layout: dict, footprints) -> None:
    """Теплотрасса: две утеплённые трубы на опорах (2,4 м — под ними проходят), над улицами — П-образные
    переходы на 5,8 м; в конце — тепловой пункт (постройка раскладки)."""
    ground = z1.ground
    pieces = []
    for li, line in enumerate(layout["pipes"]):
        pts = densify(line, 5.0)
        hs = []
        for x, z in pts:
            over = near_road(layout, x, z, 3.0)
            hs.append((max(ground(x, z), max((ground(x + ox, z + oz) for ox, oz in ((4, 0), (-4, 0), (0, 4), (0, -4))))) + (5.8 if over else 2.4), over))
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            ya, yb = hs[i][0], hs[i + 1][0]
            for side in (-0.32, 0.32):
                pa, pb = offset_line([a, b], side)
                pieces.append(tube_piece(pa, pb, ya, yb, 0.42, PIPE, collision=True))
        for i, (x, z) in enumerate(pts):
            y, over = hs[i]
            if over and near_road(layout, x, z, 0.8):
                continue  # опора не на проезжей части
            g = ground(x, z)
            pieces.append(dict(at=[round(x, 2), round((g + y - 0.25) / 2, 2), round(z, 2)], size=[0.25, round(y - 0.25 - g, 2), 0.25],
                               color=list(DARK_CONCRETE), collision=True))
            footprints.append((x, z, 1.5, 1.5, 0.0))
    z1.props(s, "Pipes", 0, 0, pieces, "Small", y=0.0, surface="metal")


def lamps(s, z1, layout: dict, footprints) -> None:
    """Фонари вдоль городских улиц через ~34 м, через сторону. Горят только у автостанции, кинотеатра,
    универсама и администрации (до LIT_MAX) — светильник с тенью дорогой, а город брошен."""
    s.node("Lamps")
    lit_spots = [tuple(b["at"]) for b in layout["buildings"] if b["id"] in LIT_NEAR]
    lit_spots.append(tuple(layout["overpass"]["points"][0]))
    placed: list[tuple[float, float]] = []
    lit = 0
    n = 0
    for r in layout["roads"]:
        if r["dirt"] or r["id"] not in ("north", "south", "artery", "east", "mall", "evac3", "tracks_lane"):
            continue
        pts = densify(r["points"], 2.0)
        side = 1
        acc = 10.0
        for i in range(1, len(pts) - 1):
            acc += math.dist(pts[i - 1], pts[i])
            if acc < 34.0:
                continue
            acc = 0.0
            side = -side
            a, b = pts[i - 1], pts[i + 1]
            ux, uz = b[0] - a[0], b[1] - a[1]
            ln = math.hypot(ux, uz) or 1.0
            nx, nz = -uz / ln, ux / ln
            off = r["width"] / 2 + 1.4
            x, z = pts[i][0] + nx * side * off, pts[i][1] + nz * side * off
            if inside_any(x, z, footprints, 0.8) or any(math.dist((x, z), p) < 14.0 for p in placed) or abs(x) > 296 or abs(z) > 296:
                continue
            tx, tz = -nx * side, -nz * side  # вынос светильника (+Z модели) — к дороге
            yaw = math.degrees(math.atan2(tx, tz))
            on = lit < LIT_MAX and any(math.dist((x, z), q) < 45.0 for q in lit_spots)
            prop_model(s, z1, "Lamps", f"Lamp_{n:02}", "lamp_post", x, z, yaw, surface="concrete",
                       extra="lamp_head = Vector3(0, 8.99, 2.05)" if on else "")
            lit += 1 if on else 0
            placed.append((x, z))
            footprints.append((x, z, 0.8, 0.8, 0.0))
            n += 1


def yards(s, z1, layout: dict, rng: random.Random, footprints) -> None:
    """Дворы панелек: детские площадки (качели, горка, песочница, карусель), скамейки, баки (модели проекта)."""
    s.node("Yards")
    spots = [((-87.0, 14.0), 90.0), ((-50.0, 5.0), 90.0), ((-50.0, 42.0), 0.0), ((-140.0, 70.0), 0.0),
             ((-104.0, 34.0), 0.0), ((-87.0, -22.0), 90.0)]
    placed = 0
    for i, ((x, z), yaw) in enumerate(spots):
        if inside_any(x, z, footprints, 6.0) or near_road(layout, x, z, 6.0) or placed >= 4:
            continue
        placed += 1
        y = z1.ground(x, z)
        s.node(f"Play_{i}", "Yards", kind="Node3D", position=z1.v3(x, y, z), rotation_degrees=z1.v3(0, yaw, 0))
        for name, key, dx, dz, ry in (("Swing", "play_swing", -3.0, 0.0, 0.0), ("Carousel", "play_carousel", 3.0, 1.0, 0.0),
                                      ("Slide", "play_slide", 0.0, -3.5, 90.0), ("Sandbox", "play_sandbox", 4.0, -3.0, 0.0)):
            prop_model(s, z1, f"Yards/Play_{i}", name, key, dx, dz, ry, y=0.0)
        for k, (bx, bz) in enumerate(((-4.0, 5.0), (4.0, 5.0), (0.0, -6.5))):
            prop_model(s, z1, f"Yards/Play_{i}", f"Bench_{k}", "bench_back", bx, bz, 180.0 if bz > 0 else 0.0, y=0.0,
                       surface="wood")
        footprints.append((x, z, 14.0, 14.0, -yaw))
    # мусорные баки у торцов жилых домов
    n = 0
    for b in layout["buildings"]:
        if b["kind"] != "panel":
            continue
        (x, z), (L, D), ang = b["at"], b["size"], b["angle"]
        a = math.radians(ang)
        px = x + math.cos(a) * (L / 2 + 4.0)
        pz = z + math.sin(a) * (L / 2 + 4.0)
        if inside_any(px, pz, footprints, 1.0) or near_road(layout, px, pz, 1.5):
            continue
        z1.sf_model(s, f"Bins_{n}", rng.choice(["sf_dumpster_a", "sf_dumpster_b", "sf_dumpster_tipped"]), px, pz,
                    -ang + 90, "Yards")
        footprints.append((px, pz, 3.0, 3.0, 0.0))
        n += 1


def cars(s, z1, layout: dict, rng: random.Random, footprints) -> None:
    """Брошенные машины: у обочин улиц (как на картинке) и на стоянке у универсама."""
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
                if (not inside_any(x, z, footprints, 1.0) and all(math.dist((x, z), t) > 7.0 for t in taken)
                        and all(math.dist((x, z), j) > 14.0 for j in junctions)):
                    z1.car(s, f"Car_{n:02}", x, z, yaw, parent="Cars")
                    taken.append((x, z))
                    footprints.append((x, z, 4.5, 2.0, -yaw))
                    n += 1
                i += 6
            else:
                i += 3
    # стоянка у универсама: ряд легковых перед входом
    sm = next(b for b in layout["buildings"] if b["id"] == "Supermarket")
    sx, sz = sm["at"]
    for k in range(10):
        x, z = sx - 16.0 + k * 3.4, sz + sm["size"][1] / 2 + 4.5
        if rng.random() < 0.6 and not inside_any(x, z, footprints, 0.5):
            z1.car(s, f"Lot_{k}", x, z, 90.0 + rng.uniform(-8, 8), parent="Cars")
            footprints.append((x, z, 2.0, 4.5, 0.0))


def clutter(s, z1, layout: dict, rng: random.Random, footprints) -> None:
    """Хлам у домов — по «карте пустоты»: в клетках 11 м рядом с постройками, где пусто, — куча мусора,
    штабель плит ФБС, сарай, покрышки, ржавый контейнер, опрокинутый бак или сгоревшая машина."""
    s.node("Clutter", "Small")
    built = [f for f in footprints if f[2] * f[3] > 60.0]
    tracks = track_lines(layout)
    n = 0
    z = -285.0
    while z < 285.0:
        x = -285.0
        while x < 285.0:
            px, pz = x + rng.uniform(-3.5, 3.5), z + rng.uniform(-3.5, 3.5)
            x += 11.0
            if rng.random() > 0.3:
                continue
            if (inside_any(px, pz, footprints, 3.0) or near_road(layout, px, pz, 3.5, paved_only=False)
                    or point_in(layout["swamp"], px, pz) or dist_poly(layout["ravine"], px, pz)[0] < 18.0
                    or any(dist_poly(tl, px, pz)[0] < 10.0 for tl in tracks)):
                continue
            if not inside_any(px, pz, built, 30.0):
                continue  # пустыри и лес не трогаем — только у построек
            roll = rng.random()
            yaw = rng.uniform(0, 360)
            name = f"Junk_{n:03}"
            g = z1.ground(px, pz)
            if roll < 0.12:
                z1.sf_model(s, name, "sf_car_burned" if rng.random() < 0.5 else "sf_vaz2104", px, pz, yaw, "Small/Clutter")
            elif roll < 0.22:
                z1.sf_model(s, name, rng.choice(["sf_dumpster_tipped", "sf_dumpster_b"]), px, pz, yaw, "Small/Clutter")
            elif roll < 0.3:
                z1.sf_model(s, name, "sf_wood_block", px, pz, yaw, "Small/Clutter", surface="wood")
            else:
                if roll < 0.52:  # куча мусора
                    pieces = [dict(at=[rng.uniform(-1, 1), 0.3, rng.uniform(-1, 1)], size=[rng.uniform(1, 2.2), 0.7, rng.uniform(1, 2)],
                                   color=list(DEBRIS), collision=True, rotation=[rng.uniform(-8, 8), rng.uniform(0, 90), rng.uniform(-8, 8)])
                              for _ in range(3)]
                elif roll < 0.66:  # штабель бетонных блоков
                    pieces = [dict(at=[0, 0.3 + 0.6 * k, 0], size=[2.4, 0.6, 0.6 if k else 1.2], color=list(CONCRETE),
                                   collision=True, rotation=[0, rng.uniform(-6, 6), 0]) for k in range(rng.randint(1, 3))]
                elif roll < 0.8:  # сарай
                    pieces = [dict(at=[0, 1.2, 0], size=[3.0, 2.4, 2.4], color=[0.4, 0.33, 0.27], collision=True),
                              dict(at=[0, 2.5, 0], size=[3.4, 0.12, 2.8], color=list(RUST), collision=True, rotation=[6, 0, 0])]
                elif roll < 0.9:  # покрышки
                    pieces = [dict(at=[rng.uniform(-0.6, 0.6), 0.15 + 0.3 * k, rng.uniform(-0.6, 0.6)], size=[0.75, 0.28, 0.75],
                                   shape="cylinder", color=[0.12, 0.12, 0.12], collision=True) for k in range(rng.randint(1, 4))]
                else:  # ржавый морской контейнер
                    pieces = [dict(at=[0, 1.3, 0], size=[6.0, 2.6, 2.4], color=list(RUST), collision=True)]
                z1.props(s, name, px, pz, pieces, "Small/Clutter", yaw=yaw, y=g)
            footprints.append((px, pz, 4.0, 4.0, 0.0))
            n += 1
        z += 11.0
    print(f"zone01: хлама у домов {n}")


def skyline(s, z1, study) -> None:
    """Высотки за лесом — город вокруг (почти на каждом кадре картинки): блокауты 9–16 этажей."""
    s.node("Skyline")
    for i, (x, z, L, D, floors, yaw) in enumerate(z1.SKYLINE):
        y = min(z1.ground(x + dx, z + dz) for dx, dz in corners(0, 0, L, D, yaw)) - 0.3
        study_node(s, z1, f"Tower_{i:02}", "Skyline", study, "mass", footprint=z1.v2(L, D), floors=floors,
                   story_height=2.9, label="Высотка за лесом", position=z1.v3(x, y, z), rotation_degrees=z1.v3(0, -yaw, 0))
