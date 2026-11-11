# -*- coding: utf-8 -*-
"""Расширение проспекта на карте «Проспект» (владелец 2026-11-07: «на карте проспект сам проспект надо в 2 раза
расширять»). Описание — docs/design/prospekt_map.md, §20.

Генератор tools/build_prospekt.py пишет карту в прежних координатах (между фасадами 31,3 м), а этот модуль переносит
план на расширенный проспект (warp_plan в конце генератора; рейдовая сборка tools/build_prospekt_raid.py переносит
свои точки тем же warp). Правило переноса:

* внутренняя сторона поворота — «Ярус», стройка, вокзал, дом на повороте, сквер, минимаркет — стоит на месте;
* внешняя отъезжает на прибавку ширины S: север западного плеча (павильоны, ЖК «Панорама», паркинг −1, банк) —
  на север, восток южного плеча (корпус 3, «Меридиан», насыпь к востоку от тоннеля) — на восток, внешний угол
  поворота (ЖК «Вершина», площадь, пункт эвакуации) — по диагонали, целиком. Между блоками остаются два шва —
  новые полосы земли шириной S: между автомойкой банка и стилобатом «Вершины» (x = SEAM_X) и между полем эвакуации
  и парковкой корпуса 3 (z = 55); их заполняет генератор;
* поперёк проспекта полосы растягиваются по участкам — тротуар, проезжая часть, разделительная — каждая до своей
  новой ширины; вдоль — ничего не меняется. В повороте то же по радиусу вокруг центра поворота (0, 55).

Смещение d — влево от направления проспекта (запад → поворот → юг): на западном плече d = −z, в повороте — радиус
минус CR, на южном плече d = x − XS. Внутренняя сторона — d < 0, внешняя — d > 0.

Вариант — переменная окружения PROSPEKT_WIDEN (имя из VARIANTS), по умолчанию CHOSEN.
"""
from __future__ import annotations

import math
import os

# прежний поперечный профиль (tools/build_prospekt.py до расширения): тротуар 5,5 × 1,3, по две полосы 3,5 в сторону,
# разделительная 3 м
F_OLD = 8.5 + 5.5 * 1.3        # 15,65 — край тротуара от оси
RH_OLD = 8.5                   # бордюр от оси
MED_OLD = 1.5                  # половина разделительной
CX, CZ, CR = 0.0, 55.0, 55.0   # центр и радиус оси поворота
XS = CX + CR                   # ось южного плеча
LANE = 3.5
SEAM_X = 17.5                  # шов на севере: между автомойкой банка (x ≤ 17) и стилобатом «Вершины» (x ≥ 18)

# Варианты поперечного профиля (на сторону): тротуар (× 1,3 по правилу масштаба), парковочный карман у бордюра,
# полосы по 3,5 м, разделительная целиком. Внутренний край тротуара западного плеча остаётся на z = +15,65.
# Карман — асфальт за краевой линией у бордюра: при переносе он часть проезжей части (машины у прежнего бордюра
# попадают в карман, всё с прежнего тротуара — на новый тротуар).
VARIANTS: dict[str, dict] = {
    "now": {"title": "как сейчас", "walk": 7.15, "pocket": 0.0, "lanes": 2, "median": 3.0},
    "a2": {"title": "×2 «бульвар»: 3 + 3 полосы, разделительная-бульвар 13 м", "walk": 11.8, "pocket": 2.5, "lanes": 3,
           "median": 13.0},
    "b2": {"title": "×2 «магистраль»: 4 + 4 полосы, разделительная 6 м", "walk": 11.8, "pocket": 2.5, "lanes": 4,
           "median": 6.0},
    "c15": {"title": "×1,5: 3 + 3 полосы, разделительная 4 м", "walk": 8.5, "pocket": 2.5, "lanes": 3, "median": 4.0},
}
CHOSEN = "b2"                  # владелец 2026-11-07: «Б · магистраль ×2»
NAME = os.environ.get("PROSPEKT_WIDEN", CHOSEN) or CHOSEN
V = VARIANTS[NAME]

WS = V["walk"]                                   # тротуар
WC = V["lanes"] * LANE + V["pocket"]             # асфальт одной стороны: полосы и карман
WM = V["median"]
TOTAL = 2.0 * WS + 2.0 * WC + WM                 # между фасадами
OLD_BP = [-F_OLD, -RH_OLD, -MED_OLD, MED_OLD, RH_OLD, F_OLD]
NEW_BP = [-F_OLD, -F_OLD + WS, -F_OLD + WS + WC, -F_OLD + WS + WC + WM, -F_OLD + WS + 2.0 * WC + WM, -F_OLD + TOTAL]
S = NEW_BP[-1] - F_OLD                           # насколько отъезжает внешняя сторона
AXIS = (NEW_BP[2] + NEW_BP[3]) * 0.5             # новая ось — смещение от прежней (влево, наружу)
F_NEW = TOTAL * 0.5                              # край тротуара от новой оси
RH_NEW = WC + WM * 0.5                           # бордюр от новой оси
EDGE_NEW = RH_NEW - V["pocket"]                  # краевая линия между полосами и карманом
MED_NEW = WM * 0.5
LANES = V["lanes"]
POCKET = V["pocket"]
CR_NEW = CR + AXIS                               # радиус новой оси поворота (центр тот же)
XS_NEW = XS + AXIS                               # ось южного плеча
ZA_NEW = -AXIS                                   # ось западного плеча (z)
ACTIVE = abs(S) > 1e-6


def dmap(d: float) -> float:
    """Смещение поперёк проспекта: прежнее → новое (кусочно-линейно по участкам профиля)."""
    if d <= OLD_BP[0]:
        return d
    if d >= OLD_BP[-1]:
        return d + S
    for k in range(len(OLD_BP) - 1):
        a, b = OLD_BP[k], OLD_BP[k + 1]
        if d <= b:
            t = (d - a) / (b - a)
            return NEW_BP[k] + (NEW_BP[k + 1] - NEW_BP[k]) * t
    return d + S


def offset(x: float, z: float) -> float:
    """Прежнее смещение d точки от оси проспекта (влево от направления)."""
    if x <= CX:
        return -z
    if z >= CZ:
        return x - XS
    return math.hypot(x - CX, z - CZ) - CR


def warp(x: float, z: float) -> tuple[float, float]:
    """Точка прежней карты → точка карты с расширенным проспектом."""
    if not ACTIVE:
        return x, z
    if x <= CX:                                  # западное плечо и всё к западу от поворота
        return x, -dmap(-z)
    if z >= CZ:                                  # южное плечо и всё к югу от поворота
        return XS + dmap(x - XS), z
    dx, dz = x - CX, z - CZ                      # четверть поворота
    r = math.hypot(dx, dz)
    d = r - CR
    if d <= F_OLD:
        if r < 1e-6:
            return x, z
        rn = CR + dmap(d)
        return CX + dx / r * rn, CZ + dz / r * rn
    if x < SEAM_X:                               # внешний угол: блоком к северу или по диагонали
        return x, z - S
    return x + S, z - S


def in_band(x: float, z: float) -> bool:
    return abs(offset(x, z)) < F_OLD


def _rect_samples(x0: float, z0: float, x1: float, z1: float, n: int = 6) -> list[tuple[float, float]]:
    pts = []
    for k in range(n + 1):
        t = k / n
        pts += [(x0 + (x1 - x0) * t, z0), (x0 + (x1 - x0) * t, z1), (x0, z0 + (z1 - z0) * t), (x1, z0 + (z1 - z0) * t)]
    return pts


def _small_in_band(pts: list[tuple[float, float]]) -> bool:
    """Мелкое целиком на проспекте (бордюр, полоса, шкаф): размер не растягивается — переносится только место."""
    ds = [offset(x, z) for (x, z) in pts]
    return all(abs(d) < F_OLD for d in ds) and max(ds) - min(ds) < 1.6


def warp_rect(r: list, keep_small: bool = False) -> list:
    x0, z0, x1, z1 = float(r[0]), float(r[1]), float(r[2]), float(r[3])
    pts = _rect_samples(x0, z0, x1, z1)
    if keep_small and _small_in_band(pts):
        cx, cz = warp((x0 + x1) * 0.5, (z0 + z1) * 0.5)
        hx, hz = (x1 - x0) * 0.5, (z1 - z0) * 0.5
        return [round(cx - hx, 3), round(cz - hz, 3), round(cx + hx, 3), round(cz + hz, 3)]
    w = [warp(x, z) for (x, z) in pts]
    return [round(min(p[0] for p in w), 3), round(min(p[1] for p in w), 3), round(max(p[0] for p in w), 3),
            round(max(p[1] for p in w), 3)]


def cross_dir(x: float, z: float) -> tuple[float, float]:
    """Направление поперёк проспекта в точке (единичное)."""
    if x <= CX:
        return 0.0, 1.0
    if z >= CZ:
        return 1.0, 0.0
    r = max(1e-6, math.hypot(x - CX, z - CZ))
    return (x - CX) / r, (z - CZ) / r


def warp_box(at: list, size: list, yaw: float) -> tuple[list, list, float]:
    """Коробка (центр x, y, z; размер; поворот как у Godot) — по её локальным осям. Мелкое поперёк проспекта
    (бордюр, полоса, ограждение) толщину поперёк не меняет, вдоль — тянется вместе с поворотом."""
    x, y, z = float(at[0]), float(at[1]), float(at[2])
    sx, sy, sz = float(size[0]), float(size[1]), float(size[2])
    a = math.radians(yaw)
    ux, uz = (math.cos(a), -math.sin(a)), (math.sin(a), math.cos(a))
    corners = [(x + ux[0] * sx * i * 0.5 + uz[0] * sz * j * 0.5, z + ux[1] * sx * i * 0.5 + uz[1] * sz * j * 0.5)
               for i in (-1, 0, 1) for j in (-1, 0, 1)]
    pa = warp(x + ux[0] * sx * 0.5, z + ux[1] * sx * 0.5)
    pb = warp(x - ux[0] * sx * 0.5, z - ux[1] * sx * 0.5)
    qa = warp(x + uz[0] * sz * 0.5, z + uz[1] * sz * 0.5)
    qb = warp(x - uz[0] * sz * 0.5, z - uz[1] * sz * 0.5)
    nsx = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
    nsz = math.hypot(qa[0] - qb[0], qa[1] - qb[1])
    if all(abs(offset(px, pz)) < F_OLD for (px, pz) in corners):
        cd = cross_dir(x, z)
        if sx < 1.6 and abs(ux[0] * cd[0] + ux[1] * cd[1]) > 0.7:
            nsx = sx
        if sz < 1.6 and abs(uz[0] * cd[0] + uz[1] * cd[1]) > 0.7:
            nsz = sz
    ncx, ncz = (pa[0] + pb[0] + qa[0] + qb[0]) * 0.25, (pa[1] + pb[1] + qa[1] + qb[1]) * 0.25
    if sx > 1e-3 and nsx > 1e-3:
        yaw = round(math.degrees(math.atan2(-(pa[1] - pb[1]), pa[0] - pb[0])), 2)
    return [round(ncx, 3), y, round(ncz, 3)], [round(nsx, 3), sy, round(nsz, 3)], yaw


def stair_scale(a: list, b: list) -> float:
    """Марш вдоль проспекта на тротуаре (лестницы перехода) шире во столько же, во сколько шире тротуар; поперёк — как был."""
    mx, mz = (float(a[0]) + float(b[0])) * 0.5, (float(a[2]) + float(b[2])) * 0.5
    d = offset(mx, mz)
    if abs(d) >= F_OLD:
        return 1.0
    dx, dz = float(b[0]) - float(a[0]), float(b[2]) - float(a[2])
    n = math.hypot(dx, dz)
    if n < 1e-6:
        return 1.0
    p0, p1 = warp(mx, mz), warp(mx + 0.01 * (-dz / n), mz + 0.01 * (dx / n))
    return math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / 0.01


def _p2(p: list) -> list:
    x, z = warp(float(p[0]), float(p[1]))
    return [round(x, 2), round(z, 2)] + list(p[2:])


def _p3(p: list) -> list:
    x, z = warp(float(p[0]), float(p[2]))
    return [round(x, 2), p[1], round(z, 2)] + list(p[3:])


def warp_plan(plan: dict, raw: set[int] | None = None) -> None:
    """Переносит весь план на расширенный проспект на месте. raw — id() записей, уже написанных в новых координатах."""
    if not ACTIVE:
        return
    raw = raw or set()

    def old(e: object) -> bool:
        return id(e) not in raw

    plan["bounds"] = warp_rect(plan["bounds"])
    plan["boundary"] = [_p2(p) for p in plan["boundary"]]
    for s in plan["surfaces"]:
        if old(s):
            s["rect"] = warp_rect(s["rect"])
            if "holes" in s:
                s["holes"] = [warp_rect(h) for h in s["holes"]]
    plan["ground_holes"] = [warp_rect(h) if old(h) else h for h in plan["ground_holes"]]
    plan["walk_holes"] = [warp_rect(h) if old(h) else h for h in plan.get("walk_holes", [])]
    for s in plan["slabs"]:
        if old(s):
            s["rect"] = warp_rect(s["rect"])
            s["holes"] = [warp_rect(h) for h in s.get("holes", [])]
    for w in plan["walls"]:
        if old(w):
            w["rect"] = warp_rect(w["rect"])
    for b in plan["boxes"]:
        if old(b):
            b["at"], b["size"], b["yaw"] = warp_box(b["at"], b["size"], b["yaw"])
    for c in plan["columns"]:
        if old(c):
            c["rect"] = warp_rect(c["rect"])
    for s in plan["stairs"]:
        if old(s):
            s["width"] = round(s["width"] * stair_scale(s["from"], s["to"]), 3)
            s["from"], s["to"] = _p3(s["from"]), _p3(s["to"])
    for r in plan["ramps"]:
        if old(r):
            x0, z0, x1, z1 = warp_rect([r["x0"], min(r["z0"], r["z1"]), r["x1"], max(r["z0"], r["z1"])])
            flip = r["z0"] > r["z1"]
            r["x0"], r["x1"] = x0, x1
            r["z0"], r["z1"] = (z1, z0) if flip else (z0, z1)
    plan["lamps"] = [_p3(l) if old(l) else l for l in plan["lamps"]]
    for s in plan["signs"]:
        if old(s):
            s["at"] = _p3(s["at"])
    for b in plan["buildings"]:
        if old(b):
            b["at"] = _p2(b["at"])
    for key in ("spawns", "exits"):
        for e in plan[key]:
            if old(e):
                e["at"] = _p2(e["at"])
    for e in plan["switches"] + plan["doors"]:
        if old(e):
            e["at"] = _p3(e["at"])
    for loc in plan["locations"]:
        if old(loc):
            for key in ("at", "spawn", "look"):
                loc[key] = _p2(loc[key])
    for r in plan["probe_routes"]:
        if old(r):
            r["points"] = [_p2(p) for p in r["points"]]
    ch = plan["checks"]
    for key in ("pit", "yard", "tunnel"):
        if key in ch:
            ch[key] = _p2(ch[key])
    if "cordon" in ch:
        ch["cordon"]["from"] = _p2(ch["cordon"]["from"])
        ch["cordon"]["to"] = _p2(ch["cordon"]["to"])
    plan["beams"] = [[_p3(b[0]), _p3(b[1])] + b[2:] if old(b) else b for b in plan["beams"]]
    for l in plan["loot"]:
        if old(l):
            l["at"] = _p3(l["at"])
    fi = plan["filler"]
    fi["items"] = [[it[0]] + _p2(it[1:3]) + it[3:] if old(it) else it for it in fi["items"]]
    fi["cover"] = [_p2(c) if old(c) else c for c in fi["cover"]]
    for s in fi["stories"]:
        if old(s):
            s["at"] = _p2(s["at"])
    plan["widen"] = {"variant": NAME, "title": V["title"], "total_m": round(TOTAL, 2), "shift_m": round(S, 2),
                     "walk": V["walk"], "pocket": V["pocket"], "lanes": V["lanes"], "median": WM,
                     "axis_west_z": round(ZA_NEW, 3), "axis_south_x": round(XS_NEW, 3), "curve_r": round(CR_NEW, 3)}
