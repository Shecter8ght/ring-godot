#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Разбор расстановки вещей на карте «Проспект» (только чтение снимка, сцены не трогает).

Что считает (см. docs/design/prospekt_props_audit.md, если появится):
  1. деревья на тротуаре (посадочная полоса у бордюра / ходовая часть / у фасада, у двери, у остановки, у фонаря, друг к другу);
  2. входы в здания и вещи в «коридоре входа» (ширина двери + 0,6 м с боков, глубина 3 м наружу);
  3. остановки и ларьки (скопления, ларьки позади остановок, на проезжей части, посреди тротуара, у фасада с дверью);
  4. прочая уличная мелочь (линия у бордюра или разброс, пересечения, на проезжей части, в зданиях, в стенах, ряды столбиков);
  5. свободная ширина прохода на тротуарах проспекта и южного плеча (сечения через 5 м).

Запуск:  python -X utf8 tools/prospekt_props_audit.py [--snapshot путь] [--out папка]
Снимок получают командой  tools/godot.cmd --headless res://tools/prospekt_study.tscn -- snapshot  (data/blockouts/prospekt_snapshot.json).
Пишет  <out>/audit.json  и картинки props_audit_*.png (по умолчанию docs/screens/prospekt/props_audit).
Зона «Ярус» (X −142…−62, Z 44…88) в выводы не входит — её перестраивают отдельно; вещи в ней считаются отдельно.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter, defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ----------------------------------------------------------------------------------------------- наборы вещей
TREES = {"tree_birch", "tree_round", "tree_poplar"}
BUSHES = {"bush_big", "hedge"}
KIOSKS = {"kiosk", "stall", "food_kiosk", "m:U05_02", "m:R05"}
BUS_STOPS = {"bus_stop"}
BENCHES = {"bench", "m:U02_03", "m:U10_04", "m:U09_04"}
BINS = {"bin", "m:U02_05", "m:U05_04"}
BOLLARDS = {"bollard", "m:U02_04"}
PLANTERS = {"planter", "m:U02_02", "flowerbed"}
ADS = {"ad_column", "billboard", "m:U10_05", "m:U03_01"}
LAMPS = {"lamp", "ornate_lamp", "lamp_park", "m:U12_03", "m:U10_02", "pole_conc", "pole_trolley"}
SIGNS = {"m:U03_03", "m:U06_02", "m:U10_03", "m:U09_03", "m:U05_03"}
CABINETS = {"m:U03_05", "booth", "cafe_table"}
FURNITURE = BENCHES | BINS | BOLLARDS | PLANTERS | ADS | LAMPS | SIGNS | CABINETS
VEHICLES = {"car", "car_open", "car_wreck", "suv_open", "m:U14_01", "bus_city", "paz", "minibus", "taxi", "police_car",
            "van", "ambulance", "bus_over", "truck", "truck_cab", "dump_truck", "armored_truck", "btr", "avtozak",
            "flatbed", "trailer", "tractor", "excavator", "m:PV_fire_tanker", "paz_police", "inkassator", "bus_wreck",
            "loco_tem", "wagon_box", "wagon_pass"}
POLES = {"lamp", "ornate_lamp", "lamp_park", "m:U12_03", "m:U10_02", "pole_conc", "pole_trolley", "m:U03_03",
         "m:U06_02", "m:U10_03", "m:U15_02", "m:U07_02", "flagpole", "mast", "floodlight"}
# без коллизии / плоские / мусор — коридор входа не загораживают
NONBLOCK = {"paper", "paper_ball", "bottle", "can", "glass_shards", "bags", "dust", "puddle", "tape", "speed_bump",
            "slab", "track_3m", "fire_hose", "m:U05_05", "m:U06_05", "m:U06_01", "m:U15_05", "m:U09_05", "half_sphere",
            "m:U12_05", "m:U04_05", "m:U19_04", "m:PC05_CROSSSPAN", "m:U10_05", "m:U19_02", "m:U14_04", "m:U08_03",
            "billboard_fallen", "m:U01_04", "cone", "m:U14_03", "m:U03_04"}
# размеры по модели в данных нет — руками (ширина по X, глубина по Z, м)
HAND = {"stall": (3.0, 2.0), "booth": (1.2, 1.2), "ad_column": (1.3, 1.3), "cafe_table": (0.9, 0.9),
        "flowerbed": (3.0, 3.0), "cabin": (2.4, 6.0), "cart_row": (0.6, 3.2), "cart": (0.6, 0.9),
        "chainlink": (0.1, 2.0), "ped_fence": (0.1, 2.2), "hazard_fence": (0.1, 2.5), "bar_fence": (0.1, 2.5),
        "rail_fence": (0.1, 2.5), "trash_pile": (1.4, 1.2), "pallets": (1.2, 1.0), "ac_unit": (0.85, 0.3),
        "barrel": (0.6, 0.6), "lamp": (0.3, 0.3), "ornate_lamp": (0.3, 0.3), "lamp_park": (0.3, 0.3),
        "bin": (0.5, 0.5), "bollard": (0.2, 0.2), "bench": (1.8, 0.45), "planter": (2.4, 2.4), "boxes": (1.0, 1.0),
        "suitcase": (0.6, 0.4), "tires": (1.0, 1.0), "pile_sand": (3.0, 3.0), "pile_dirt": (3.0, 3.0)}
TREE_TRUNK = 0.5     # ствол с лункой, м (кроны не считаем — над головой)

ZONE_NAMES = {
    "north": "проспект, северная сторона",
    "south": "проспект, южная сторона",
    "shoulder": "южное плечо",
    "skver": "сквер у Вокзальной",
    "yards": "дворы ЖК",
    "vershina": "«Вершина» и её площадь",
    "privokz": "привокзальная площадь",
    "southwest": "юго-запад",
    "overpass": "под эстакадой",
    "other": "остальное",
    "yarus": "ЗОНА «ЯРУС» (исключена)",
}
YARUS = (-142.0, 44.0, -62.0, 88.0)


def zone(x: float, z: float) -> str:
    if YARUS[0] <= x <= YARUS[2] and YARUS[1] <= z <= YARUS[3]:
        return "yarus"
    if x < -218.0:
        return "overpass"
    if x < 40.0 and -62.0 < z < -35.0:
        return "north"
    if x < 40.0 and 3.0 < z < 50.0:
        return "south"
    if -52.0 < x < 40.0 and 100.0 < z < 250.0:
        return "skver"
    if 36.0 < x < 103.0 and 40.0 < z < 295.0:
        return "shoulder"
    if x >= 103.0 and 140.0 <= z <= 250.0:
        return "privokz"
    if 0.0 <= x < 200.0 and -150.0 < z < -29.0:
        return "vershina"
    if (x < 0.0 and -155.0 < z <= -62.0) or (x > 100.0 and 60.0 < z < 140.0):
        return "yards"
    if x < -50.0 and 50.0 < z < 250.0:
        return "southwest"
    return "other"


# ----------------------------------------------------------------------------------------------- геометрия
def obb(x: float, z: float, w: float, d: float, yaw_deg: float) -> tuple:
    """Ориентированный прямоугольник: центр, полуразмеры, ось «вперёд по X» в мире. Поворот Godot Basis(UP, yaw)."""
    th = math.radians(yaw_deg)
    ax = (math.cos(th), -math.sin(th))      # локальный X в мире
    az = (math.sin(th), math.cos(th))       # локальный Z в мире
    return (x, z, w * 0.5, d * 0.5, ax, az)


def obb_corners(o: tuple) -> list:
    x, z, hw, hd, ax, az = o
    pts = []
    for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        pts.append((x + sx * hw * ax[0] + sz * hd * az[0], z + sx * hw * ax[1] + sz * hd * az[1]))
    return pts


def obb_overlap(a: tuple, b: tuple, margin: float = 0.0) -> bool:
    """Пересечение двух ориентированных прямоугольников по теореме о разделяющей оси (запас margin)."""
    for o1, o2 in ((a, b), (b, a)):
        for ax in (o1[4], o1[5]):
            c1 = o1[0] * ax[0] + o1[1] * ax[1]
            r1 = o1[2] * abs(o1[4][0] * ax[0] + o1[4][1] * ax[1]) + o1[3] * abs(o1[5][0] * ax[0] + o1[5][1] * ax[1])
            c2 = o2[0] * ax[0] + o2[1] * ax[1]
            r2 = o2[2] * abs(o2[4][0] * ax[0] + o2[4][1] * ax[1]) + o2[3] * abs(o2[5][0] * ax[0] + o2[5][1] * ax[1])
            if abs(c1 - c2) > r1 + r2 + margin:
                return False
    return True


def rect_obb(r: list) -> tuple:
    return ((r[0] + r[2]) * 0.5, (r[1] + r[3]) * 0.5, (r[2] - r[0]) * 0.5, (r[3] - r[1]) * 0.5, (1.0, 0.0), (0.0, 1.0))


def rect_dist(rects: np.ndarray, x: float, z: float) -> float:
    if len(rects) == 0:
        return 1e9
    dx = np.maximum(np.maximum(rects[:, 0] - x, 0.0), x - rects[:, 2])
    dz = np.maximum(np.maximum(rects[:, 1] - z, 0.0), z - rects[:, 3])
    return float(np.sqrt(dx * dx + dz * dz).min())


def rect_dist_arg(rects: np.ndarray, x: float, z: float) -> tuple:
    dx = np.maximum(np.maximum(rects[:, 0] - x, 0.0), x - rects[:, 2])
    dz = np.maximum(np.maximum(rects[:, 1] - z, 0.0), z - rects[:, 3])
    d = np.sqrt(dx * dx + dz * dz)
    i = int(d.argmin())
    return float(d[i]), i


# ----------------------------------------------------------------------------------------------- загрузка
class Audit:
    def __init__(self, snap_path: str) -> None:
        with open(snap_path, encoding="utf-8") as f:
            self.d = json.load(f)
        with open(os.path.join(ROOT, "data", "urban95_models.json"), encoding="utf-8") as f:
            self.models = json.load(f)["models"]
        self.kit = self.d["filler"]["kit_models"]
        self.nosolid_models = set(self.d["filler"].get("models_nosolid", []))
        self.pole_models = set(self.d["filler"].get("models_poles", []))
        self.surfaces = self.d["surfaces"]
        self.srect = np.array([s["rect"] for s in self.surfaces], dtype=float)
        self.smat = [s["mat"] for s in self.surfaces]
        self.road = np.array([s["rect"] for s in self.surfaces if s["mat"] == "road"], dtype=float)
        self.road_main = np.array([s["rect"] for s in self.surfaces if s["id"] in
                                   ("road_w", "road_s", "tunnel_road", "ur_bp_road")], dtype=float)
        # здания (кроме фоновых масс «Outside») и стены первого этажа
        self.bld = []
        for b in self.d["buildings"]:
            if b["region"] == "Outside":
                continue
            cx, cz = b["at"]
            sx, sz = b["size"]
            if abs(round(b["yaw"] / 90.0)) % 2 == 1:
                sx, sz = sz, sx
            self.bld.append({"id": b["id"], "rect": [cx - sx / 2, cz - sz / 2, cx + sx / 2, cz + sz / 2], "b": b})
        self.bld_rects = np.array([b["rect"] for b in self.bld], dtype=float)
        self.walls_ground = [w for w in self.d["walls"] if w["mat"] != "tunnel_tile" and w["y0"] < 0.8 and w["y1"] > 0.5
                             and w["y0"] > -1.0]
        self.wall_full = np.array([w["rect"] for w in self.walls_ground
                                   if w["y1"] >= 2.5 and min(w["rect"][2] - w["rect"][0], w["rect"][3] - w["rect"][1]) >= 0.2],
                                  dtype=float)
        self.facades = np.vstack([self.bld_rects, self.wall_full])
        self.items = self.d["filler"]["items"]
        self.unknown_fp: Counter = Counter()
        self.fp_cache: dict = {}
        self.entrances: list = []

    # ----- покрытие
    def mat_at(self, x: float, z: float) -> str:
        m = "none"
        for i in range(len(self.srect)):
            r = self.srect[i]
            if r[0] <= x <= r[2] and r[1] <= z <= r[3]:
                m = self.smat[i]
        return m

    # ----- размеры вещи
    def footprint(self, it: list) -> tuple:
        name = it[0]
        s = float(it[4]) if len(it) > 4 else 1.0
        yaw = float(it[3])
        kit = self.kit.get(name)
        mid = None
        yoff = 0.0
        if kit:
            mid = kit["model"]
            yoff = float(kit.get("yaw", 0.0))
        elif name.startswith("m:"):
            mid = name[2:]
        pinned = it[8] if len(it) > 8 and it[8] else None
        if name in POLES or (mid in self.pole_models):
            w, d = 0.3 * s, 0.3 * s
        elif name in TREES:
            w, d = TREE_TRUNK, TREE_TRUNK
        elif name in HAND and not (kit and name not in HAND):
            w, d = HAND[name][0] * s, HAND[name][1] * s
        else:
            m = self.models.get(pinned or mid) if (pinned or mid) else None
            if m is None and mid is not None:
                m = self.models.get(mid)
            if m is not None:
                w, d = m["aabb"]["size"][0] * s, m["aabb"]["size"][2] * s
            elif name in HAND:
                w, d = HAND[name][0] * s, HAND[name][1] * s
            else:
                self.unknown_fp[name] += 1
                w, d = 1.0 * s, 1.0 * s
        return obb(float(it[1]), float(it[2]), w, d, yaw + yoff)

    def is_solid(self, name: str) -> bool:
        if name in NONBLOCK:
            return False
        mid = self.kit.get(name, {}).get("model") if name in self.kit else (name[2:] if name.startswith("m:") else None)
        if mid and mid in self.nosolid_models:
            return False
        return True


def label(it: list) -> str:
    return f"{it[0]} ({it[1]:.1f}; {it[2]:.1f})"


# ----------------------------------------------------------------------------------------------- входы
def collect_entrances(A: Audit) -> tuple:
    """Входы в здания из всех доступных источников. Возвращает (список, описание источников)."""
    ents: list = []
    notes: dict = {}

    def add(x, z, nx, nz, w, src, name):
        ents.append({"x": x, "z": z, "nx": nx, "nz": nz, "w": w, "src": src, "name": name})

    # А. залы (StudyBuilding._hall_gaps): дверь на локальной +Z стороне и чёрный ход на −Z
    n_hall = 0
    for b in A.d["buildings"]:
        if b["kind"] != "hall" or b["region"] == "Outside":
            continue
        th = math.radians(b["yaw"])
        ax = (math.cos(th), -math.sin(th))
        az = (math.sin(th), math.cos(th))
        cx, cz = b["at"]
        hx, hz = b["size"][0] * 0.5, b["size"][1] * 0.5
        ent = float(b["extra"].get("entry_door", 0) or 0)
        interior = b["interior"]
        if interior == "shop":
            front = (0.0, ent if ent > 0 else 2.0)
            back = (hx - 2.0, 1.2)
        elif interior == "pharmacy":
            front = (0.0, 2.0)
            back = (-hx + 2.0, 1.2)
        else:
            continue
        for (lx, w), side, tag in ((front, 1.0, "парадный"), (back, -1.0, "чёрный")):
            x = cx + lx * ax[0] + side * hz * az[0]
            z = cz + lx * ax[1] + side * hz * az[1]
            add(x, z, side * az[0], side * az[1], w, "зал (study_building._hall_gaps)", f"{b['id']} · {tag}")
            n_hall += 1
    notes["залы (магазины/кафе)"] = n_hall
    # Б. секции «flats» с open_floors > 0: двойная дверь 2,4 м на локальной −Z стороне (flat_section._lobby)
    n_flat = 0
    for b in A.d["buildings"]:
        if b["kind"] != "flats" or int(b["extra"].get("open_floors", 0) or 0) <= 0:
            continue
        th = math.radians(b["yaw"])
        az = (math.sin(th), math.cos(th))
        cx, cz = b["at"]
        hz = b["size"][1] * 0.5
        add(cx - hz * az[0], cz - hz * az[1], -az[0], -az[1], 2.4, "секция flats (flat_section._lobby)", b["id"] + " · подъезд")
        n_flat += 1
    notes["подъезды секций flats"] = n_flat
    # В. модели дверей в наполнении: карусель U08_01, двустворчатая U08_02
    n_mod = 0
    for it in A.items:
        if it[0] in ("m:U08_01", "m:U08_02"):
            th = math.radians(float(it[3]))
            add(it[1], it[2], math.sin(th), math.cos(th), 2.6, "модель двери в наполнении (U08_01/02)", it[0])
            n_mod += 1
    notes["модели дверей U08_01/02"] = n_mod
    # Г. проёмы в стенах первого этажа (план, собранный патчами: банк, мойка, «Вершина» и т. д.)
    n_gap = 0
    lines: dict = defaultdict(list)
    for w in A.walls_ground:
        r = w["rect"]
        t = min(r[2] - r[0], r[3] - r[1])
        if t < 0.2 or t > 0.45:
            continue
        if r[2] - r[0] >= r[3] - r[1]:
            lines[("x", round((r[1] + r[3]) * 0.5, 2))].append((r[0], r[2]))
        else:
            lines[("z", round((r[0] + r[2]) * 0.5, 2))].append((r[1], r[3]))
    for (axis, c), segs in lines.items():
        segs.sort()
        merged = []
        for a, b in segs:
            if merged and a <= merged[-1][1] + 0.05:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        for i in range(len(merged) - 1):
            g0, g1 = merged[i][1], merged[i + 1][0]
            w = g1 - g0
            if w < 0.9 or w > 6.0:
                continue
            mid = (g0 + g1) * 0.5
            px, pz = (mid, c) if axis == "x" else (c, mid)
            n = (0.0, 1.0) if axis == "x" else (1.0, 0.0)
            # наружу — та сторона, где луч 25 м свободен от толстых стен, а с другой стороны стена близко
            def ray_free(sign):
                for k in range(1, 26):
                    qx, qz = px + sign * n[0] * k, pz + sign * n[1] * k
                    if rect_dist(A.wall_full, qx, qz) < 0.15 or rect_dist(A.bld_rects, qx, qz) < 0.0 + 1e-9:
                        return k
                return 99
            kp, km = ray_free(1.0), ray_free(-1.0)
            if kp >= 25 and km < 25:
                sgn = 1.0
            elif km >= 25 and kp < 25:
                sgn = -1.0
            else:
                continue   # оба луча свободны (проход насквозь) или оба заперты (внутренняя дверь)
            add(px, pz, sgn * n[0], sgn * n[1], w, "проём в стене 1-го этажа (снимок)", f"стена {axis}={c}")
            n_gap += 1
    notes["проёмы в наружных стенах первого этажа плана"] = n_gap
    # дедуп: входы ближе 1,6 м — один (берём источник с большим приоритетом: модель двери, зал, секция, проём)
    prio = {"зал": 0, "секция": 1, "модель": 2, "проём": 3}
    ents.sort(key=lambda e: [v for k, v in prio.items() if e["src"].startswith(k)][0])
    out: list = []
    for e in ents:
        if any(math.hypot(e["x"] - o["x"], e["z"] - o["z"]) < 1.6 for o in out):
            continue
        out.append(e)
    return out, notes


# ----------------------------------------------------------------------------------------------- анализ
def run(snap: str, outdir: str) -> dict:
    A = Audit(snap)
    items = A.items
    res: dict = {"snapshot": os.path.relpath(snap, ROOT) if snap.startswith(ROOT) else snap,
                 "items_total": len(items), "yarus_excluded": list(YARUS)}
    zones = {k: Counter() for k in ZONE_NAMES}

    def zc(cat: str, x: float, z: float) -> None:
        zones[zone(x, z)][cat] += 1

    # ---------- справочник по наборам
    counts = Counter(i[0] for i in items)
    res["inventory"] = {
        "деревья": {k: counts[k] for k in TREES if counts[k]},
        "кусты/живая изгородь": {k: counts[k] for k in BUSHES if counts[k]},
        "ларьки/киоски": {k: counts[k] for k in sorted(KIOSKS) if counts[k]},
        "остановки": {k: counts[k] for k in BUS_STOPS if counts[k]},
        "прочая мебель улицы": {k: counts[k] for k in sorted(FURNITURE) if counts[k]},
        "транспорт (всего)": sum(counts[k] for k in VEHICLES),
    }
    res["models_for_trees"] = {k: A.kit.get(k, {}).get("model") for k in TREES | BUSHES}
    res["models_for_kiosks"] = {k: A.kit.get(k, {}).get("model", "серая форма набора (3,0 × 2,4 м)") for k in sorted(KIOSKS)}
    res["models_for_bus_stop"] = A.models["PC_busstop_any"]["aabb"]["size"]

    # ---------- входы
    ents, ent_notes = collect_entrances(A)
    for e in ents:
        e["zone"] = zone(e["x"], e["z"])
    res["entrances_sources"] = ent_notes
    res["entrances_total"] = len(ents)

    # заранее: footprints и покрытия
    fps = [A.footprint(it) for it in items]
    solid = [A.is_solid(it[0]) for it in items]
    zone_of = [zone(it[1], it[2]) for it in items]

    def dr(x, z):
        return rect_dist(A.road, x, z)

    # ================================================================ 1. деревья
    trees = [(i, it) for i, it in enumerate(items) if it[0] in TREES]
    tree_rows = []
    hist_road, hist_fac = [], []
    lamp_pts = [(it[1], it[2]) for it in items if it[0] in LAMPS]
    stop_obbs = [(i, fps[i]) for i, it in enumerate(items) if it[0] in BUS_STOPS]
    cat1 = defaultdict(list)
    for i, it in trees:
        x, z = it[1], it[2]
        zn = zone_of[i]
        mat = A.mat_at(x, z)
        d_road = dr(x, z)
        d_fac = rect_dist(A.facades, x, z)
        row = {"i": i, "name": it[0], "x": x, "z": z, "zone": zn, "mat": mat,
               "d_road": round(d_road, 2), "d_facade": round(d_fac, 2)}
        sidewalk = mat in ("walk", "parking", "slab", "court") and d_road <= 13.0
        paved_plaza = mat in ("walk", "slab", "court") and d_road > 13.0
        d_door = min([math.hypot(x - e["x"], z - e["z"]) for e in ents] or [99])
        d_stop = min([math.hypot(x - o[1][0], z - o[1][1]) for o in stop_obbs] or [99])
        d_lamp = min([math.hypot(x - lx, z - lz) for lx, lz in lamp_pts] or [99])
        d_tree = min([math.hypot(x - o[1][1], z - o[1][2]) for o in trees if o[0] != i] or [99])
        row.update(d_door=round(d_door, 2), d_stop=round(d_stop, 2), d_lamp=round(d_lamp, 2), d_tree=round(d_tree, 2))
        if mat == "road":
            row["cls"] = "на проезжей части"
        elif mat == "parking":
            row["cls"] = "на стоянке"
        elif sidewalk:
            if d_fac <= 3.0:
                row["cls"] = "тротуар: у фасада (≤ 3 м)"
            elif d_road < 1.0:
                row["cls"] = "тротуар: на кромке (< 1 м от бордюра)"
            elif d_road <= 5.0:
                row["cls"] = "тротуар: посадочная полоса (1…5 м от бордюра)"
            else:
                # ширина полотна тротуара по покрытию walk, внутри которого стоит дерево
                wmin = [min(r[2] - r[0], r[3] - r[1]) for k, r in enumerate(A.srect) if A.smat[k] == "walk"
                        and r[0] <= x <= r[2] and r[1] <= z <= r[3] and min(r[2] - r[0], r[3] - r[1]) <= 12.5]
                d_out = (wmin[0] - d_road) if wmin else 99.0
                row["d_outer_edge"] = round(d_out, 2)
                if d_out <= 3.0:
                    row["cls"] = "тротуар: у внешнего края полотна (≤ 3 м), второй ряд"
                else:
                    row["cls"] = "тротуар: ХОДОВАЯ ЧАСТЬ (> 5 м от бордюра, > 3 м от фасада)"
        elif paved_plaza:
            row["cls"] = "мощёная площадь/двор (не у проезжей части)"
        else:
            row["cls"] = "газон/грунт/вне покрытий"
        row["score"] = (min(d_road - 5.0, d_fac - 3.0) if row["cls"].startswith("тротуар: ХОД") else 0.0)
        tree_rows.append(row)
        if sidewalk or mat in ("road", "parking"):
            hist_road.append(d_road)
            hist_fac.append(min(d_fac, 30.0))
    for r in tree_rows:
        r["flags"] = []
        if r["d_door"] < 2.0:
            r["flags"].append("у двери < 2 м")
        if r["d_stop"] < 3.0:
            r["flags"].append("у остановки < 3 м")
        if r["d_lamp"] < 2.0:
            r["flags"].append("у фонаря < 2 м")
        if r["d_tree"] < 3.0:
            r["flags"].append("ближе 3 м к другому дереву")
    # деревья в местах машин (пересечение со стоянкой машины)
    veh_idx = [i for i, it in enumerate(items) if it[0] in VEHICLES]
    for r in tree_rows:
        o = obb(r["x"], r["z"], TREE_TRUNK, TREE_TRUNK, 0)
        for j in veh_idx:
            if abs(items[j][1] - r["x"]) < 6 and abs(items[j][2] - r["z"]) < 6 and obb_overlap(o, fps[j]):
                r["flags"].append("в габарите машины")
                break
    by_cls = Counter(r["cls"] for r in tree_rows)
    tz = defaultdict(Counter)
    for r in tree_rows:
        tz[r["zone"]][r["cls"]] += 1
    flags_c = Counter(f for r in tree_rows if r["zone"] != "yarus" for f in r["flags"])

    def hist(vals, edges):
        h = np.histogram(vals, bins=edges)[0]
        return {f"{edges[k]:g}–{edges[k+1]:g}": int(h[k]) for k in range(len(h))}

    ex_y = [r for r in tree_rows if r["zone"] != "yarus"]
    res["cat1_trees"] = {
        "total": len(tree_rows), "yarus_total": len(tree_rows) - len(ex_y),
        "by_class": dict(Counter(r["cls"] for r in ex_y)),
        "by_zone_class": {ZONE_NAMES[z]: dict(c) for z, c in tz.items() if z != "yarus"},
        "flags": dict(flags_c),
        "hist_d_road_street": hist([r["d_road"] for r in ex_y if r["cls"].startswith(("тротуар", "на стоянке", "на проезжей"))],
                                   [0, 0.5, 1, 1.5, 2, 3, 4, 5, 6, 8, 10, 13, 20]),
        "hist_d_facade_street": hist([r["d_facade"] for r in ex_y if r["cls"].startswith("тротуар")],
                                     [0, 1, 2, 3, 4, 5, 6, 8, 10, 15, 30]),
        "worst15_walkway": sorted([r for r in ex_y if r["cls"].startswith("тротуар: ХОД")], key=lambda r: -r["score"])[:15],
        "worst15_flagged": sorted([r for r in ex_y if r["flags"] or r["cls"].startswith(("на проезжей", "на стоянке"))],
                                  key=lambda r: -len(r["flags"]))[:15],
        "rows": ex_y,
    }

    # ================================================================ 2. входы
    blockers_i = [i for i, it in enumerate(items) if solid[i] and it[0] not in ("track_3m",) and not it[0].startswith("m:U08_") and zone_of[i] != "yarus"
                  or (solid[i] and zone_of[i] == "yarus" and False)]
    # (в зоне «Ярус» вещи не учитываем; входы там тоже помечены)
    blocked = []
    for e in ents:
        ez = e["zone"]
        # прямоугольник коридора: ширина двери + 0,6 с боков, глубина 3 м наружу (центр — на 1,5 м от двери)
        n = (e["nx"], e["nz"])
        yaw = math.degrees(math.atan2(-n[1] * 0 + n[0], n[1]))   # нормаль = (sin, cos)
        th = math.radians(yaw)
        cor = (e["x"] + n[0] * 1.5, e["z"] + n[1] * 1.5, (e["w"] + 1.2) * 0.5, 1.5, (math.cos(th), -math.sin(th)), (math.sin(th), math.cos(th)))
        hits = []
        for i in blockers_i:
            it = items[i]
            if abs(it[1] - e["x"]) > 12 or abs(it[2] - e["z"]) > 12:
                continue
            if obb_overlap(cor, fps[i]):
                hits.append(i)
        # стена/здание на пути коридора не считаем: проверяем только вещи
        e["hits"] = [{"name": items[i][0], "x": items[i][1], "z": items[i][2]} for i in hits]
        e["blocked"] = bool(hits)
        # вход «в никуда»: перед дверью не покрытие улицы (проверка геометрии)
        e["mat_out"] = A.mat_at(e["x"] + n[0] * 1.5, e["z"] + n[1] * 1.5)
        if hits:
            blocked.append(e)
    ent_zone = defaultdict(lambda: [0, 0])
    for e in ents:
        ent_zone[e["zone"]][0] += 1
        ent_zone[e["zone"]][1] += 1 if e["blocked"] else 0
    ex_e = [e for e in ents if e["zone"] != "yarus"]
    res["cat2_entrances"] = {
        "total": len(ents), "yarus_total": len(ents) - len(ex_e),
        "blocked": sum(1 for e in ex_e if e["blocked"]),
        "by_zone": {ZONE_NAMES[z]: {"входов": v[0], "перегорожено": v[1]} for z, v in ent_zone.items() if z != "yarus"},
        "blocked_by_name": dict(Counter(h["name"] for e in ex_e for h in e["hits"])),
        "worst15": sorted([e for e in ex_e if e["blocked"]], key=lambda e: -len(e["hits"]))[:15],
        "all": ents,
    }

    # ================================================================ 3. ларьки и остановки
    kiosks = [i for i, it in enumerate(items) if it[0] in KIOSKS]
    stops = [i for i, it in enumerate(items) if it[0] in BUS_STOPS]
    # скопления: ≥ 2 ларьков ближе 6 м (по центрам)
    par = {i: i for i in kiosks}

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for a in kiosks:
        for b in kiosks:
            if a < b and math.hypot(items[a][1] - items[b][1], items[a][2] - items[b][2]) < 6.0:
                par[find(a)] = find(b)
    groups = defaultdict(list)
    for i in kiosks:
        groups[find(i)].append(i)
    clusters = []
    for g in groups.values():
        if len(g) >= 2:
            cx = sum(items[i][1] for i in g) / len(g)
            cz = sum(items[i][2] for i in g) / len(g)
            clusters.append({"n": len(g), "zone": zone(cx, cz), "cx": round(cx, 1), "cz": round(cz, 1),
                             "members": [[items[i][0], round(items[i][1], 1), round(items[i][2], 1), items[i][3]] for i in g],
                             "mat": A.mat_at(cx, cz)})
    # ларьки у остановок и «позади»
    stop_rows = []
    behind_total = 0
    for s in stops:
        sx, sz = items[s][1], items[s][2]
        d, ri = rect_dist_arg(A.road_main if len(A.road_main) else A.road, sx, sz)
        rr = (A.road_main if len(A.road_main) else A.road)[ri]
        qx = min(max(sx, rr[0]), rr[2])
        qz = min(max(sz, rr[1]), rr[3])
        tvx, tvz = qx - sx, qz - sz
        ln = math.hypot(tvx, tvz) or 1.0
        tvx, tvz = tvx / ln, tvz / ln
        near = []
        for k in kiosks:
            dd = math.hypot(items[k][1] - sx, items[k][2] - sz)
            if dd <= 12.0:
                dot = (items[k][1] - sx) * tvx + (items[k][2] - sz) * tvz
                near.append({"name": items[k][0], "x": items[k][1], "z": items[k][2], "dist": round(dd, 1),
                             "behind": dot < -1.0, "side": round(dot, 1)})
        behind = sum(1 for n in near if n["behind"])
        behind_total += behind
        stop_rows.append({"x": sx, "z": sz, "zone": zone(sx, sz), "d_road": round(d, 1), "mat": A.mat_at(sx, sz),
                          "kiosks_12m": len(near), "behind": behind, "kiosks": near})
    # ларьки по местам
    kiosk_rows = []
    for k in kiosks:
        it = items[k]
        x, z = it[1], it[2]
        mat = A.mat_at(x, z)
        d_road = dr(x, z)
        d_fac = rect_dist(A.facades, x, z)
        # расстояние до двери (габарит ларька к двери)
        d_door = min([math.hypot(x - e["x"], z - e["z"]) for e in ents] or [99])
        fl = []
        if mat == "road":
            fl.append("на проезжей части")
        sidewalk = mat == "walk" and d_road <= 13.0
        if sidewalk and d_road > 3.0 and d_fac > 3.0:
            fl.append("посреди тротуара (>3 м от бордюра и фасада)")
        if d_fac <= 1.0:
            fl.append("вплотную к стене/фасаду")
        if d_door <= 4.0:
            fl.append("у двери ≤ 4 м")
        kiosk_rows.append({"i": k, "name": it[0], "x": x, "z": z, "yaw": it[3], "zone": zone_of[k], "mat": mat,
                           "d_road": round(d_road, 1), "d_facade": round(d_fac, 1), "d_door": round(d_door, 1), "flags": fl})
    ex_k = [r for r in kiosk_rows if r["zone"] != "yarus"]
    ex_clusters = [c for c in clusters if c["zone"] != "yarus"]
    res["cat3_kiosks"] = {
        "kiosks_total": len(kiosk_rows), "yarus_total": len(kiosk_rows) - len(ex_k),
        "bus_stops_total": len(stops),
        "by_zone": {ZONE_NAMES[z]: sum(1 for r in ex_k if r["zone"] == z) for z in ZONE_NAMES if z != "yarus"},
        "flags": dict(Counter(f for r in ex_k for f in r["flags"])),
        "clusters_ge2_within_6m": len(ex_clusters),
        "clusters_ge3": sum(1 for c in ex_clusters if c["n"] >= 3),
        "clusters_by_zone": dict(Counter(ZONE_NAMES[c["zone"]] for c in ex_clusters)),
        "clusters": sorted(ex_clusters, key=lambda c: -c["n"]),
        "bus_stops": stop_rows,
        "kiosks_behind_stops_total": behind_total,
        "worst15_flagged": sorted([r for r in ex_k if r["flags"]], key=lambda r: -len(r["flags"]))[:15],
    }

    # ================================================================ 4. прочая мелочь
    street_classes = {"скамьи": BENCHES, "урны": BINS, "столбики": BOLLARDS, "кадки/клумбы": PLANTERS, "рекл. щиты/колонны": ADS,
                      "фонари/опоры": LAMPS, "знаки": SIGNS, "шкафы/будки/столы": CABINETS}
    cls_of = {}
    for cn, st in street_classes.items():
        for n in st:
            cls_of[n] = cn
    cat4 = {"по классам": {}}
    furn_rows = []
    for i, it in enumerate(items):
        if it[0] not in cls_of or zone_of[i] == "yarus":
            continue
        x, z = it[1], it[2]
        mat = A.mat_at(x, z)
        d_road = dr(x, z)
        d_fac = rect_dist(A.facades, x, z)
        loc = "прочее"
        if mat == "walk" and d_road <= 13.0:
            loc = "полоса у бордюра (≤ 5 м)" if d_road <= 5.0 else ("у фасада (≤ 2 м)" if d_fac <= 2.0 else "ХОДОВАЯ ЧАСТЬ")
        elif mat == "road":
            loc = "на проезжей части"
        elif mat == "parking":
            loc = "на стоянке"
        elif mat in ("grass", "mud", "none"):
            loc = "газон/грунт"
        elif mat in ("walk", "slab", "court"):
            loc = "мощёная площадь/двор"
        furn_rows.append({"i": i, "name": it[0], "cls": cls_of[it[0]], "x": x, "z": z, "mat": mat, "loc": loc,
                          "d_road": round(d_road, 2), "d_facade": round(d_fac, 2), "zone": zone_of[i]})
    for cn in street_classes:
        rows = [r for r in furn_rows if r["cls"] == cn]
        cat4["по классам"][cn] = {"всего": len(rows), **dict(Counter(r["loc"] for r in rows))}
    # пересечения габаритов между «мебелью», деревьями и ларьками
    cand = [i for i, it in enumerate(items) if (it[0] in cls_of or it[0] in TREES or it[0] in KIOSKS or it[0] in BUS_STOPS)
            and solid[i] and zone_of[i] != "yarus"]
    cand.sort(key=lambda i: items[i][1])
    overlaps = []
    for ai in range(len(cand)):
        a = cand[ai]
        for bi in range(ai + 1, len(cand)):
            b = cand[bi]
            if items[b][1] - items[a][1] > 6.0:
                break
            if abs(items[b][2] - items[a][2]) > 6.0:
                continue
            # лампа/столбик на лавке, фонарь у дерева не считаем за ошибку «малого»: порог — вложение > 0,05 м
            if obb_overlap(fps[a], fps[b], -0.05):
                overlaps.append((a, b))
    ov_rows = [{"a": label(items[a]), "b": label(items[b]), "x": items[a][1], "z": items[a][2], "zone": zone_of[a]} for a, b in overlaps]
    cat4["overlaps_total"] = len(ov_rows)
    cat4["overlaps_by_pair"] = dict(Counter(" × ".join(sorted([items[a][0], items[b][0]])) for a, b in overlaps).most_common(25))
    cat4["overlaps_worst15"] = ov_rows[:15]
    # на проезжей части (мебель, ларьки, деревья)
    on_road = [r for r in furn_rows if r["loc"] == "на проезжей части"]
    on_road += [{"name": r["name"], "cls": "ларёк", "x": r["x"], "z": r["z"], "zone": r["zone"], "loc": "на проезжей части"}
                for r in ex_k if "на проезжей части" in r["flags"]]
    on_road += [{"name": r["name"], "cls": "дерево", "x": r["x"], "z": r["z"], "zone": r["zone"], "loc": "на проезжей части"}
                for r in ex_y if r["cls"] == "на проезжей части"]
    cat4["on_road_total"] = len(on_road)
    cat4["on_road_by_class"] = dict(Counter(r["cls"] for r in on_road))
    cat4["on_road_by_zone"] = dict(Counter(ZONE_NAMES[r["zone"]] for r in on_road))
    cat4["on_road_list"] = on_road[:60]
    # внутри зданий-объёмов и в стенах
    inside, in_wall = [], []
    wall_obbs = [(rect_obb(w["rect"]), w) for w in A.walls_ground if min(w["rect"][2] - w["rect"][0], w["rect"][3] - w["rect"][1]) >= 0.1
                 and w["y1"] >= 1.5]
    check_idx = [i for i, it in enumerate(items) if (it[0] in cls_of or it[0] in TREES or it[0] in KIOSKS) and zone_of[i] != "yarus"]
    for i in check_idx:
        x, z = items[i][1], items[i][2]
        for b in A.bld:
            r = b["rect"]
            if r[0] + 0.3 < x < r[2] - 0.3 and r[1] + 0.3 < z < r[3] - 0.3:
                inside.append({"name": items[i][0], "x": x, "z": z, "in": b["id"], "zone": zone_of[i]})
                break
        for wo, w in wall_obbs:
            if abs(wo[0] - x) > 8 or abs(wo[1] - z) > 8:
                continue
            if obb_overlap(fps[i], wo, -0.05):
                in_wall.append({"name": items[i][0], "x": x, "z": z, "wall": [round(v, 1) for v in w["rect"]], "zone": zone_of[i]})
                break
    cat4["inside_building_total"] = len(inside)
    cat4["inside_building_by_class"] = dict(Counter(r["name"] for r in inside))
    cat4["inside_building_list"] = inside[:40]
    cat4["in_wall_total"] = len(in_wall)
    cat4["in_wall_by_class"] = dict(Counter(r["name"] for r in in_wall))
    cat4["in_wall_list"] = in_wall[:40]
    # столбики: цепочки с шагом < 1,2 м
    bol = [i for i, it in enumerate(items) if it[0] in BOLLARDS and zone_of[i] != "yarus"]
    bpar = {i: i for i in bol}

    def bfind(a):
        while bpar[a] != a:
            bpar[a] = bpar[bpar[a]]
            a = bpar[a]
        return a

    steps = []
    for a in bol:
        near = sorted((math.hypot(items[a][1] - items[b][1], items[a][2] - items[b][2]), b) for b in bol if b != a)[:1]
        if near:
            steps.append(near[0][0])
        for b in bol:
            if a < b and math.hypot(items[a][1] - items[b][1], items[a][2] - items[b][2]) < 2.0:
                bpar[bfind(a)] = bfind(b)
    chains = defaultdict(list)
    for i in bol:
        chains[bfind(i)].append(i)
    chain_rows = []
    for g in chains.values():
        if len(g) < 3:
            continue
        xs = np.array([items[i][1] for i in g])
        zs = np.array([items[i][2] for i in g])
        pts = np.c_[xs, zs]
        # направление цепочки и шаг
        c = pts.mean(axis=0)
        u, s, vt = np.linalg.svd(pts - c)
        dirv = vt[0]
        proj = np.sort((pts - c) @ dirv)
        step = float(np.diff(proj).mean()) if len(proj) > 1 else 0.0
        extent = float(proj[-1] - proj[0])
        # поперёк тротуара? кромка ближайшей дороги — вдоль оси X или Z
        d, ri = rect_dist_arg(A.road, float(c[0]), float(c[1]))
        rr = A.road[ri]
        qx = min(max(c[0], rr[0]), rr[2])
        qz = min(max(c[1], rr[1]), rr[3])
        tvx, tvz = qx - c[0], qz - c[1]
        ln = math.hypot(tvx, tvz) or 1.0
        across = abs(dirv[0] * tvx / ln + dirv[1] * tvz / ln)    # 1 — цепочка идёт на дорогу (поперёк тротуара)
        chain_rows.append({"n": len(g), "step": round(step, 2), "length": round(extent, 1), "cx": round(float(c[0]), 1), "cz": round(float(c[1]), 1),
                           "zone": zone(float(c[0]), float(c[1])), "d_road": round(d, 1), "across": round(across, 2),
                           "mat": A.mat_at(float(c[0]), float(c[1]))})
    cat4["bollards"] = {"total": len(bol), "median_nearest_gap": round(float(np.median(steps)), 2) if steps else None,
                        "chains_ge3": len(chain_rows),
                        "chains_tight_lt_1_2": sum(1 for r in chain_rows if r["step"] < 1.2),
                        "chains_across_walk": sum(1 for r in chain_rows if r["across"] > 0.7 and r["mat"] == "walk" and r["step"] < 1.2),
                        "chains": sorted(chain_rows, key=lambda r: r["step"])[:30]}
    res["cat4_misc"] = cat4
    res["cat4_misc"]["furniture_rows_count"] = len(furn_rows)

    # ================================================================ 5. ширина прохода
    sect_res = {}

    def sections(name, axis, lo, hi, rng, step=5.0):
        """axis='x': сечение поперёк улицы идёт вдоль Z на разных X (улица вдоль X); 'z' — наоборот."""
        gaps, totals, who = [], [], []
        s = rng[0]
        while s <= rng[1] + 1e-6:
            occ = []
            ocl = []
            for i, it in enumerate(items):
                if not solid[i] or zone_of[i] == "yarus" or it[0] in VEHICLES:
                    continue
                if it[0] in ("track_3m",):
                    continue
                pts = obb_corners(fps[i])
                a_along = [p[0] if axis == "x" else p[1] for p in pts]
                if max(a_along) < s - 0.5 or min(a_along) > s + 0.5:
                    continue
                a_cross = [p[1] if axis == "x" else p[0] for p in pts]
                c0, c1 = min(a_cross), max(a_cross)
                if c1 < lo or c0 > hi:
                    continue
                occ.append((max(c0, lo), min(c1, hi)))
                ocl.append(it[0])
            for w in A.walls_ground:
                if w["y1"] < 1.0:
                    continue
                r = w["rect"]
                if axis == "x":
                    if r[2] < s - 0.5 or r[0] > s + 0.5 or r[3] < lo or r[1] > hi:
                        continue
                    occ.append((max(r[1], lo), min(r[3], hi)))
                else:
                    if r[3] < s - 0.5 or r[1] > s + 0.5 or r[2] < lo or r[0] > hi:
                        continue
                    occ.append((max(r[0], lo), min(r[2], hi)))
                ocl.append("стена")
            occ.sort()
            free, cur, best = 0.0, lo, 0.0
            for a, b in occ:
                if a > cur:
                    best = max(best, a - cur)
                    free += a - cur
                cur = max(cur, b)
            if hi > cur:
                best = max(best, hi - cur)
                free += hi - cur
            gaps.append(best)
            totals.append(free)
            who.append(Counter(ocl).most_common(1)[0][0] if ocl else "")
            s += step
        g = np.array(gaps)
        return {"сечений": len(g), "ширина_тротуара": round(hi - lo, 2), "min_просвет": round(float(g.min()), 2),
                "median_просвет": round(float(np.median(g)), 2),
                "доля_<2м": round(float((g < 2.0).mean()), 3), "доля_<1.2м": round(float((g < 1.2).mean()), 3),
                "доля_<3м": round(float((g < 3.0).mean()), 3),
                "худшие": [{axis: round(rng[0] + 5.0 * k, 1), "просвет": round(float(g[k]), 2), "что": who[k]}
                           for k in np.argsort(g)[:8]]}

    sect_res["север, западное плечо (z −48,3…−35,15), x −218…−1"] = sections("n", "x", -48.3, -35.15, (-218.0, -1.0))
    sect_res["юг, западное плечо (z 3,85…15,65), x −218…−1"] = sections("s", "x", 3.85, 15.65, (-218.0, -1.0))
    sect_res["южное плечо, западный тротуар (x 39,35…51,15), z 56…258"] = sections("sw", "z", 39.35, 51.15, (56.0, 258.0))
    sect_res["южное плечо, восточный тротуар (x 90,15…101,95), z 56…258"] = sections("se", "z", 90.15, 101.95, (56.0, 258.0))
    res["cat5_passage"] = sect_res

    # ================================================================ сводка по зонам
    zsum = {}
    for zk, name in ZONE_NAMES.items():
        zsum[name] = {
            "деревья_всего": sum(1 for r in tree_rows if r["zone"] == zk),
            "деревья_на_тротуаре_ходовая": sum(1 for r in tree_rows if r["zone"] == zk and r["cls"].startswith("тротуар: ХОД")),
            "деревья_на_проезжей/стоянке": sum(1 for r in tree_rows if r["zone"] == zk and r["cls"] in ("на проезжей части", "на стоянке")),
            "входов": sum(1 for e in ents if e["zone"] == zk),
            "входов_перегорожено": sum(1 for e in ents if e["zone"] == zk and e["blocked"]),
            "ларьков": sum(1 for r in kiosk_rows if r["zone"] == zk),
            "ларьков_в_скоплениях": sum(c["n"] for c in clusters if c["zone"] == zk),
            "мебели_на_ходовой": sum(1 for r in furn_rows if r["zone"] == zk and r["loc"] == "ХОДОВАЯ ЧАСТЬ"),
        }
    res["zones_summary"] = zsum
    res["unknown_footprints"] = dict(A.unknown_fp)
    # покрытия/ширины данных
    res["street_data"] = {
        "walk_wn": "z −46,95…−35,15 (11,8 м), кромка проезжей части z = −35,15 (карман 2,5 м — часть проезжей части road_w)",
        "walk_ws": "z 3,85…15,65 (11,8 м), кромка z = 3,85",
        "walk_sw/se": "x 39,35…51,15 и 90,15…101,95 (11,8 м), кромка x = 51,15 / 90,15",
        "отдельного покрытия под посадочную полосу": False,
        "поверхности по mat": dict(Counter(A.smat)),
    }
    res["_internal"] = {"A": A, "fps": fps, "tree_rows": tree_rows, "kiosk_rows": kiosk_rows, "furn_rows": furn_rows, "ents": ents,
                        "clusters": clusters, "stop_rows": stop_rows, "overlaps": overlaps, "in_wall": in_wall, "inside": inside,
                        "on_road": on_road, "chain_rows": chain_rows, "zone_of": zone_of, "solid": solid}
    return res


# ----------------------------------------------------------------------------------------------- картинки
def draw(res: dict, outdir: str) -> list:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle

    I = res["_internal"]
    A: Audit = I["A"]
    fps = I["fps"]
    items = A.items
    col = {"road": "#9a9a9a", "walk": "#eadcb0", "parking": "#b4b4c4", "grass": "#a8d0a0", "mud": "#b89878", "court": "#9cc4e0",
           "slab": "#d0d0d0", "fountain_floor": "#7ab0f0"}

    def base(ax, x0, x1, z0, z1, labels=True):
        for s in A.surfaces:
            r = s["rect"]
            if r[2] < x0 or r[0] > x1 or r[3] < z0 or r[1] > z1:
                continue
            ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc=col.get(s["mat"], "#fff"), ec="none"))
        for w in A.walls_ground:
            r = w["rect"]
            if w["y1"] >= 1.8 and w["mat"] != "tunnel_tile":
                ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc="#222", ec="#222", lw=0.3))
        for b in A.bld:
            r = b["rect"]
            ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc="#555555", ec="#222", alpha=0.35, lw=0.6))
            if labels and x0 < (r[0] + r[2]) / 2 < x1 and z0 < (r[1] + r[3]) / 2 < z1:
                ax.text((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, b["id"], fontsize=5, ha="center")
        ax.set_xlim(x0, x1)
        ax.set_ylim(z1, z0)
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.25)

    def other_items(ax, x0, x1, z0, z1):
        for i, it in enumerate(items):
            if not (x0 <= it[1] <= x1 and z0 <= it[2] <= z1):
                continue
            n = it[0]
            if n in ("paper", "paper_ball", "bottle", "can", "glass_shards", "bags", "dust", "puddle", "track_3m"):
                continue
            if n in TREES:
                c, ec = "#2e8b2e", "#0a4a0a"
            elif n in KIOSKS:
                c, ec = "#d06bd0", "#702070"
            elif n in BUS_STOPS:
                c, ec = "#3a6ad0", "#102070"
            elif n in FURNITURE:
                c, ec = "#f0a030", "#704010"
            elif n in VEHICLES:
                c, ec = "#c8c8d8", "#707080"
            else:
                c, ec = "#d8d8d8", "#808080"
            if n in TREES:
                ax.add_patch(plt.Circle((it[1], it[2]), 0.45, fc=c, ec=ec, lw=0.4, zorder=5))
            else:
                ax.add_patch(Polygon(obb_corners(fps[i]), closed=True, fc=c, ec=ec, lw=0.4, alpha=0.9, zorder=4))

    def mark(ax, pts, color, marker, size, lab=None, zorder=9):
        if not pts:
            return
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], c=color, marker=marker, s=size, zorder=zorder, label=lab,
                   edgecolors="k", linewidths=0.4)

    tr_bad = [(r["x"], r["z"]) for r in I["tree_rows"] if r["zone"] != "yarus" and r["cls"].startswith("тротуар: ХОД")]
    tr_road = [(r["x"], r["z"]) for r in I["tree_rows"] if r["zone"] != "yarus" and r["cls"] in ("на проезжей части", "на стоянке")]
    tr_flag = [(r["x"], r["z"]) for r in I["tree_rows"] if r["zone"] != "yarus" and r["flags"] and not r["cls"].startswith("тротуар: ХОД")]
    door_blk = [(e["x"], e["z"]) for e in I["ents"] if e["blocked"] and e["zone"] != "yarus"]
    door_ok = [(e["x"], e["z"]) for e in I["ents"] if not e["blocked"] and e["zone"] != "yarus"]
    clus = [(c["cx"], c["cz"]) for c in I["clusters"] if c["zone"] != "yarus"]
    kk = [(r["x"], r["z"]) for r in I["kiosk_rows"] if r["zone"] != "yarus" and r["flags"]]
    ov = [(items[a][1], items[a][2]) for a, b in I["overlaps"]]
    onr = [(r["x"], r["z"]) for r in I["on_road"]]
    inw = [(r["x"], r["z"]) for r in I["in_wall"] + I["inside"]]
    fm = [(r["x"], r["z"]) for r in I["furn_rows"] if r["loc"] == "ХОДОВАЯ ЧАСТЬ" and r["zone"] != "yarus"]

    def legend_marks(ax):
        mark(ax, door_ok, "#40e040", "^", 28, "вход свободен")
        mark(ax, door_blk, "#ff2020", "^", 60, "вход перегорожен")
        mark(ax, tr_bad, "#00e0ff", "o", 40, "дерево в ходовой части")
        mark(ax, tr_road, "#ff00ff", "o", 60, "дерево на дороге/стоянке")
        mark(ax, tr_flag, "#ffff00", "o", 18, "дерево у двери/остановки/фонаря/дерева")
        mark(ax, clus, "#ff8000", "s", 90, "скопление ларьков (≥ 2 < 6 м)")
        mark(ax, kk, "#ff0080", "D", 22, "ларёк: дорога/ходовая/у стены/у двери")
        mark(ax, fm, "#8040ff", "P", 28, "мебель улицы в ходовой части")
        mark(ax, ov, "#000000", "x", 25, "пересечение габаритов")
        mark(ax, onr, "#ff0000", "X", 40, "на проезжей части")
        mark(ax, inw, "#800000", "*", 40, "в здании / в стене")

    files = []
    # общая карта
    fig, ax = plt.subplots(figsize=(24, 26))
    base(ax, -250, 235, -185, 320, labels=False)
    other_items(ax, -250, 235, -185, 320)
    legend_marks(ax)
    ax.legend(loc="lower right", fontsize=9)
    zx = [(-142, 44, -62, 88)]
    ax.add_patch(Rectangle((YARUS[0], YARUS[1]), YARUS[2] - YARUS[0], YARUS[3] - YARUS[1], fc="none", ec="red", ls="--", lw=1.5))
    ax.text(-102, 66, "«Ярус»\nисключён", color="red", ha="center", fontsize=9)
    ax.set_title("Проспект: проблемы расстановки по карте (снимок сцены)")
    p = os.path.join(outdir, "props_audit_map.png")
    fig.savefig(p, dpi=55, bbox_inches="tight")
    plt.close(fig)
    files.append(p)
    crops = [("north_bank_stop", "северная сторона у остановки «Банк»", -110, 10, -62, -30, 130),
             ("south_yarus", "южная сторона у «Яруса»", -150, -50, 0, 50, 130),
             ("shoulder_south", "южное плечо (юг)", 30, 112, 90, 240, 110),
             ("skver_vokzalnaya", "сквер у Вокзальной", -58, 45, 95, 250, 110),
             ("vershina_square", "площадь «Вершины»", 0, 145, -62, -28, 130),
             ("avenue_west", "проспект, западное плечо (кафе «Зерно» … БЦ-11)", -215, -105, -50, 20, 130)]
    for key, title, x0, x1, z0, z1, dpi in crops:
        w = x1 - x0
        h = z1 - z0
        fig, ax = plt.subplots(figsize=(max(9, min(22, w / 6)), max(6, min(22, h / 6))))
        base(ax, x0, x1, z0, z1)
        other_items(ax, x0, x1, z0, z1)
        legend_marks(ax)
        ax.legend(loc="upper right", fontsize=7)
        ax.set_title(title)
        p = os.path.join(outdir, f"props_audit_{key}.png")
        fig.savefig(p, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        files.append(p)
    # гистограмма деревьев
    ex = [r for r in I["tree_rows"] if r["zone"] != "yarus" and r["cls"].startswith(("тротуар", "на проезжей", "на стоянке"))]
    fig, axs = plt.subplots(1, 2, figsize=(14, 5))
    axs[0].hist([r["d_road"] for r in ex], bins=[0, 0.5, 1, 1.5, 2, 3, 4, 5, 6, 8, 10, 13], color="#3a8a3a", edgecolor="k")
    axs[0].axvspan(1.0, 5.0, color="#80ff80", alpha=0.25, label="посадочная полоса 1…5 м")
    axs[0].set_xlabel("расстояние дерева до кромки проезжей части, м")
    axs[0].legend()
    axs[1].hist([min(r["d_facade"], 30) for r in ex], bins=[0, 1, 2, 3, 4, 5, 6, 8, 10, 15, 30], color="#8a6a3a", edgecolor="k")
    axs[1].set_xlabel("расстояние дерева до фасада, м")
    fig.suptitle("Деревья на улицах/стоянках (без «Яруса»)")
    p = os.path.join(outdir, "props_audit_tree_hist.png")
    fig.savefig(p, dpi=90, bbox_inches="tight")
    plt.close(fig)
    files.append(p)
    return files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=os.path.join(ROOT, "data", "blockouts", "prospekt_snapshot.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "screens", "prospekt", "props_audit"))
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    res = run(a.snapshot, a.out)
    files = [] if a.no_images else draw(res, a.out)
    res.pop("_internal")
    res["images"] = files
    with open(os.path.join(a.out, "audit.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print("готово:", os.path.join(a.out, "audit.json"))


if __name__ == "__main__":
    main()
