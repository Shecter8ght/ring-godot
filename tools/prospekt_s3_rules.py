# -*- coding: utf-8 -*-
"""Этап s3_props: правила расстановки (см. prospekt_s3_props.py). Каждая фаза меняет World: move / remove / add."""
from __future__ import annotations

import math

import numpy as np

import prospekt_props_audit as AU
from prospekt_s3_props import (GX0, GZ0, NX, NZ, RES, RULES, World, BENCHES, BINS, BOLLARDS, PLANTERS, ADS, LAMPS, SIGNS,
                               CABINETS, KIOSKS, STOPS, TREES, MOVABLE_FURN, VEHICLES, ci, cj, draw_poly, obb_poly, edt)


# ----------------------------------------------------------------------------------------------- помощники
def samples(W: World, it: list) -> tuple:
    o = W.fp(it)
    S = W.probe_grid(2 * o[2], 2 * o[3])
    return (o[0] + S[:, 0] * o[4][0] + S[:, 1] * o[5][0], o[1] + S[:, 0] * o[4][1] + S[:, 1] * o[5][1])


def at(arr: np.ndarray, x, z):
    return arr[np.clip(((np.asarray(z) - GZ0) / RES).astype(int), 0, NZ - 1), np.clip(((np.asarray(x) - GX0) / RES).astype(int), 0, NX - 1)]


def dist_obb(px, pz, o: tuple):
    u = (px - o[0]) * o[4][0] + (pz - o[1]) * o[4][1]
    v = (px - o[0]) * o[5][0] + (pz - o[1]) * o[5][1]
    return np.hypot(np.maximum(np.abs(u) - o[2], 0.0), np.maximum(np.abs(v) - o[3], 0.0))


def grad(field: np.ndarray, x: float, z: float) -> tuple:
    e = 0.5
    gx = float(at(field, x + e, z) - at(field, x - e, z))
    gz = float(at(field, x, z + e) - at(field, x, z - e))
    n = math.hypot(gx, gz)
    return (gx / n, gz / n) if n > 1e-6 else (0.0, 0.0)


def snap_yaw(th: float) -> float:
    q = round(th / 90.0) * 90.0
    return q if abs(th - q) < 22.0 else th


def yaw_for_front(fx: float, fz: float) -> float:
    """Поворот вещи, у которой «лицо» — локальная +Z: лицо смотрит по (fx, fz)."""
    return snap_yaw(math.degrees(math.atan2(fx, fz)))


def yaw_for_long(tx: float, tz: float, front: tuple | None = None) -> float:
    """Длинная сторона (локальная X) вдоль (tx, tz); лицом (+Z) по front, если задано."""
    if front is not None:
        return yaw_for_front(front[0], front[1])
    return snap_yaw(math.degrees(math.atan2(-tz, tx)))


def street_items(W: World, kinds: set) -> list:
    return [i for i, it in enumerate(W.items) if W.status[i] != "removed" and it[0] in kinds and not W.ug(i)]


def lamp_points(W: World) -> np.ndarray:
    pts = [(it[1], it[2]) for i, it in enumerate(W.items) if it[0] in LAMPS and W.status[i] != "removed" and not W.ug(i)]
    pts += [(l[0], l[2]) for l in W.d["lamps"]]
    return np.array(pts) if pts else np.zeros((0, 2))


def zone_name(W: World, x: float, z: float) -> str:
    return AU.zone(x, z)


# ----------------------------------------------------------------------------------------------- фаза 1: входы
def phase_entrances(W: World) -> None:
    movers = []
    for i, it in enumerate(W.items):
        if W.status[i] != "keep" or not W.solid(i):
            continue
        n = it[0]
        if n in AU.NONBLOCK or n.startswith("m:U08_") or n == "track_3m" or n in KIOSKS or n in STOPS or n in TREES:
            continue
        px, pz = samples(W, it)
        if at(W.E, px, pz).any():
            movers.append(i)
    skip = set(movers)
    O = W.build_obstacles(skip)
    Og = W.blocked_grid(O)
    for i in sorted(movers, key=lambda k: -W.dims(W.items[k])[0] * W.dims(W.items[k])[1]):
        it = W.items[i]
        n = it[0]
        if W.pinned(i):
            W.log.append({"вход": "не тронуто (ящик лута у вещи)", "item": it[:4]})
            W.place(Og, it)
            continue
        zone = "any"
        pref = None
        radius = 12.0
        if n in CABINETS or n in ADS or n in BINS or n in BOLLARDS:
            zone, radius = "strip", 30.0
        elif n in SIGNS or n in PLANTERS or n in BENCHES:
            zone, radius = "walk", 8.0
            pref = lambda xs, zs: 2.5 * np.maximum(at(W.d_fac, xs, zs) - 1.2, 0.0)  # noqa: E731
        elif n in VEHICLES or n.startswith("container"):
            zone, radius = "any", 14.0
        else:
            zone, radius = "any", 8.0
            pref = lambda xs, zs: 2.5 * np.maximum(at(W.d_fac, xs, zs) - 1.2, 0.0)  # noqa: E731
        sp = W.find_spot(it, (it[1], it[2]), radius, Og, zone=zone, prefer=pref)
        if sp is None and zone != "any":
            sp = W.find_spot(it, (it[1], it[2]), radius + 10, Og, zone="any", prefer=pref)
        if sp is None:
            W.log.append({"вход": "места нет — осталось", "item": it[:4]})
            W.place(Og, it)
            continue
        W.move(i, sp[0], sp[1], sp[2], "вход: вещь из коридора двери")
        W.place(Og, W.items[i])


# ----------------------------------------------------------------------------------------------- фаза 2: остановки и ларьки
MARKET = lambda it: (it[1] < -218.0) or (it[0] == "stall" and ((-47.0 <= it[1] <= -32.0 and 100.0 <= it[2] <= 102.0) or (-25.0 <= it[1] <= -10.0 and 232.0 <= it[2] <= 236.0))) \
    or (it[1] >= 103.0 and 140.0 <= it[2] <= 250.0 and AU.zone(it[1], it[2]) == "privokz")  # noqa: E731


def kiosk_front_yaw(W: World, x: float, z: float, mode: str) -> float | None:
    g = grad(W.d_road, x, z)
    if g == (0.0, 0.0):
        return None
    f = g if mode == "strip" else (-g[0], -g[1])
    return yaw_for_front(f[0], f[1])


def audit_mid(W: World, x: float, z: float) -> bool:
    """Разбор назовёт это «посреди тротуара» (дальше 3 м от кромки, фасада и внешнего края полотна)."""
    if W.mat[cj(z), ci(x)] != 2 or at(W.wide, x, z):
        return False
    dr = float(at(W.d_road, x, z))
    if dr > 13.0 or dr <= 3.0 or float(at(W.d_fac, x, z)) <= 3.0:
        return False
    return W.A.outer_dist(x, z, dr) > 3.0


def phase_stops(W: World) -> None:
    """Остановка — в полосе у бордюра: павильон, стоящий посреди тротуара (дальше 4,5 м от кромки), прижимается к бордюру."""
    for s in list(W.stop_idx):
        it = W.items[s]
        x, z = it[1], it[2]
        if not bool(at(W.sidewalk, x, z)) or float(at(W.d_road, x, z)) <= 4.5 or W.pinned(s, 3.0):
            continue
        O = W.build_obstacles({s})
        Og = W.blocked_grid(O)
        sp = W.find_spot(it, (x, z), 10.0, Og, zone="strip", yaws=[float(it[3])])
        if sp is None:
            W.log.append({"остановка": "места у бордюра нет", "item": it[:4]})
            continue
        W.move(s, sp[0], sp[1], None, "остановка: к бордюру")


def phase_kiosks(W: World) -> None:
    allk = street_items(W, KIOSKS)
    market = [i for i in allk if MARKET(W.items[i])]
    cand = [i for i in allk if i not in market]
    fixed = [i for i in cand if W.pinned(i)]
    movable = [i for i in cand if i not in fixed]
    # --- рынок в сквере, нижний ряд: выровнять в линию (дуга → прямая), остальные рынки не трогаем
    arc = [i for i in market if W.items[i][0] == "stall" and 232.0 <= W.items[i][2] <= 236.0]
    for i in sorted(arc, key=lambda k: W.items[k][1]):
        W.move(i, W.items[i][1], 233.5, 0.0, "рынок: ряд выровнен")
    skip = set(movable) | set(arc)
    O = W.build_obstacles(skip)
    for i in arc:
        draw_poly(O, obb_poly(W.fp(W.items[i])))
    Og = W.blocked_grid(O)
    doors = W.door_xz
    stops = [W.fp(W.items[s]) for s in W.stop_idx]
    stop_to_road = []
    for o in stops:
        g = grad(W.d_road, o[0], o[1])
        stop_to_road.append((-g[0], -g[1]))

    def far_ok(xs, zs):
        ok = np.ones(len(xs), bool)
        if len(doors):
            for dx, dz in doors:
                ok &= np.hypot(xs - dx, zs - dz) >= RULES["kiosk_door"]
        for o, tr in zip(stops, stop_to_road):
            ok &= dist_obb(xs, zs, o) >= RULES["kiosk_door"]
            near = np.hypot(xs - o[0], zs - o[1]) <= 13.0
            ok &= ~(near & (((xs - o[0]) * tr[0] + (zs - o[1]) * tr[1]) < -0.5))     # позади павильона — нельзя
        return ok

    placed: list = []           # итоговые позиции [i, x, z]
    # --- у остановок: один ларёк сбоку
    stop_kiosk: dict = {}
    for s in W.stop_idx:
        so = W.fp(W.items[s])
        near = [(math.hypot(W.items[k][1] - so[0], W.items[k][2] - so[1]), k) for k in movable if k not in stop_kiosk.values()
                and math.hypot(W.items[k][1] - so[0], W.items[k][2] - so[1]) <= 15.0]
        fx_near = [k for k in fixed if math.hypot(W.items[k][1] - so[0], W.items[k][2] - so[1]) <= 15.0]
        if fx_near or not near:
            continue
        near.sort()
        stop_kiosk[s] = near[0][1]
    for s, k in stop_kiosk.items():
        so = W.fp(W.items[s])
        g_s = grad(W.d_road, so[0], so[1])
        tr_s = (-g_s[0], -g_s[1])
        it = W.items[k]
        w, d, _ = W.dims(it)
        L = 2 * so[2]
        best = None
        for side in (1.0, -1.0):
            u = side * (L / 2 + RULES["gap"] + 3.0 + w / 2)
            for v in (0.0, -0.4, 0.4, -0.8, 0.8, -1.2, 1.2, -1.6, 1.6, -2.0, 2.0):
                cx = so[0] + u * so[4][0] + v * so[5][0]
                cz = so[1] + u * so[4][1] + v * so[5][1]
                # лицом по ходу стоянки: вдоль павильона, длинной стороной
                yaw = yaw_for_front(so[5][0], so[5][1])
                trial = list(it)
                trial[1], trial[2], trial[3] = cx, cz, yaw
                px, pz = samples(W, trial)
                if at(Og, px, pz).any() or at(W.road, px, pz).any() or at(W.E, px, pz).any() or at(W.P, px, pz).any():
                    continue
                if (cx - so[0]) * tr_s[0] + (cz - so[1]) * tr_s[1] < -0.9:      # позади павильона — нет
                    continue
                if audit_mid(W, cx, cz):
                    continue
                sc = math.hypot(cx - it[1], cz - it[2])
                if best is None or sc < best[0]:
                    best = (sc, cx, cz, yaw)
        if best is not None:
            W.move(k, best[1], best[2], best[3], "остановка: ларёк сбоку")
            W.place(Og, W.items[k])
            placed.append(k)
        else:
            stop_kiosk[s] = None
    # --- остальные: в полосу у бордюра или к внешнему краю, длинной стороной вдоль улицы
    rest = [k for k in movable if k not in placed]
    results = {}
    for k in sorted(rest, key=lambda k: (W.items[k][1], W.items[k][2])):
        it = W.items[k]
        x, z = it[1], it[2]
        on_street = bool(at(W.sidewalk, x, z)) or at(W.d_road, x, z) <= 13.0
        sp = None
        if on_street and bool(at(W.pave, x, z)):
            for mode in ("strip", "outer"):
                trial = list(it)
                # поворот подбирается в точке: два пробных (лицо внутрь / наружу) — берём по градиенту в самой точке
                g = grad(W.d_road, x, z)
                yaws = None
                if g != (0.0, 0.0):
                    f = g if mode == "strip" else (-g[0], -g[1])
                    yaws = [yaw_for_front(f[0], f[1])]
                s2 = W.find_spot(trial, (x, z), 14.0, Og, zone=mode, yaws=yaws,
                                 extra=lambda xs, zs: far_ok(xs, zs) & np.array([not audit_mid(W, float(a), float(b)) for a, b in zip(xs, zs)]))
                if s2 is not None:
                    # поворот пересчитываем уже по найденной точке
                    y2 = kiosk_front_yaw(W, s2[0], s2[1], mode)
                    cand_it = list(it)
                    cand_it[1], cand_it[2] = s2[0], s2[1]
                    if y2 is not None:
                        cand_it[3] = y2
                        px, pz = samples(W, cand_it)
                        if not at(Og, px, pz).any() and not at(W.road, px, pz).any():
                            s2 = (s2[0], s2[1], y2)
                    sp = (sp is None or math.hypot(s2[0] - x, s2[1] - z) < math.hypot(sp[0] - x, sp[1] - z)) and s2 or sp
        elif not on_street:
            # площадь, двор, газон: ларёк остаётся, если место чистое; повернём только если оно занято
            px, pz = samples(W, it)
            if not at(Og, px, pz).any() and far_ok(np.array([x]), np.array([z]))[0]:
                sp = (x, z, float(it[3]))
        results[k] = sp
    # --- отбор: не больше двух подряд, между группами ≥ 20 м
    kept = list(fixed) + [k for k in placed]
    pos = {k: (W.items[k][1], W.items[k][2]) for k in kept}
    for k in sorted([k for k in results if results[k] is not None],
                    key=lambda k: math.hypot(results[k][0] - W.items[k][1], results[k][1] - W.items[k][2])):
        sp = results[k]
        near = [m for m in pos if math.hypot(pos[m][0] - sp[0], pos[m][1] - sp[1]) < RULES["kiosk_group"]]
        if len(near) >= 2:
            continue
        if len(near) == 1:
            m = near[0]
            # пара: рядом (не дальше 8 м) и вторая не имеет соседей
            if math.hypot(pos[m][0] - sp[0], pos[m][1] - sp[1]) > 8.0:
                continue
            m_near = [n for n in pos if n != m and math.hypot(pos[n][0] - pos[m][0], pos[n][1] - pos[m][1]) < RULES["kiosk_group"]]
            if m_near:
                continue
        pos[k] = (sp[0], sp[1])
        kept.append(k)
        W.move(k, sp[0], sp[1], sp[2], "ларёк: на линию улицы")
        draw_poly(Og, obb_poly(W.fp(W.items[k]), RULES["gap"]))
    for k in rest:
        if k not in kept:
            W.remove(k, "ларёк: лишний (правило 6)")
    # ларёк у остановки, не нашедший места, — убираем
    for s, k in stop_kiosk.items():
        if k is not None and W.status[k] == "keep" and k not in kept:
            W.remove(k, "ларёк у остановки: места нет")
    # --- ларьки у остановок «Банк» и других: всё, что ближе 12 м к остановке и не стоит сбоку, — убрано выше (rest)
    # ларьки, оставшиеся в 12 м позади остановки, проверит разбор


# ----------------------------------------------------------------------------------------------- фаза 3: проезжая часть и подземное
def phase_road(W: World) -> None:
    kinds = MOVABLE_FURN | LAMPS | {"booth", "cafe_table"}
    movers = []
    for i, it in enumerate(W.items):
        if W.status[i] != "keep" or W.ug(i) or it[0] not in kinds:
            continue
        if AU.zone(it[1], it[2]) == "overpass":
            continue
        if bool(at(W.road, it[1], it[2])):
            movers.append(i)
    O = W.build_obstacles(set(movers))
    Og = W.blocked_grid(O)
    for i in movers:
        it = W.items[i]
        if W.pinned(i):
            W.log.append({"проезжая часть": "не тронуто (лут)", "item": it[:4]})
            W.place(Og, it)
            continue
        sp = W.find_spot(it, (it[1], it[2]), 3.0, Og, zone="any")
        if sp is None:
            sp = W.find_spot(it, (it[1], it[2]), 30.0, Og, zone="any")
        if sp is None:
            W.log.append({"проезжая часть": "места нет — осталось", "item": it[:4]})
            W.place(Og, it)
            continue
        W.move(i, sp[0], sp[1], sp[2], "проезжая часть: вещь убрана с дороги")
        W.place(Og, W.items[i])


# ----------------------------------------------------------------------------------------------- фаза 4: мебель в ходовой части
def furn_loc(W: World, x: float, z: float) -> str:
    if W.mat[min(NZ - 1, max(0, cj(z))), min(NX - 1, max(0, ci(x)))] == 2 and at(W.d_road, x, z) <= 13.0 and not at(W.wide, x, z):
        if at(W.d_road, x, z) <= 5.0:
            return "strip"
        if at(W.d_fac, x, z) <= 2.0:
            return "facade"
        return "walkway"
    return "other"


def phase_furniture(W: World) -> None:
    kinds = MOVABLE_FURN | LAMPS | {"booth", "cafe_table"}
    movers = [i for i, it in enumerate(W.items) if W.status[i] == "keep" and not W.ug(i) and it[0] in kinds
              and furn_loc(W, it[1], it[2]) == "walkway"]
    O = W.build_obstacles(set(movers))
    Og = W.blocked_grid(O)
    # скамьи сначала: у них спинка к газону / фасаду — у внешнего края, если там есть чем занять; иначе полоса
    movers.sort(key=lambda i: (0 if W.items[i][0] in BENCHES else 1))
    for i in movers:
        it = W.items[i]
        if W.pinned(i):
            W.place(Og, it)
            continue
        zones = ("outer", "strip") if it[0] in BENCHES else ("strip",)
        sp = None
        for z in zones:
            for rad in (12.0, 30.0):
                sp = W.find_spot(it, (it[1], it[2]), rad, Og, zone=z)
                if sp is not None:
                    break
            if sp is not None:
                break
        if sp is None:
            sp = W.find_spot(it, (it[1], it[2]), 20.0, Og, zone="walk")
        if sp is None:
            W.log.append({"мебель": "места нет — осталось", "item": it[:4]})
            W.place(Og, it)
            continue
        # ориентация: вдоль улицы (скамья — спинкой к внешнему краю)
        yaw = sp[2]
        if it[0] in BENCHES:
            g = grad(W.d_road, sp[0], sp[1])
            if g != (0.0, 0.0):
                yaw = yaw_for_front(-g[0], -g[1]) if at(W.d_road, sp[0], sp[1]) > 3.0 else yaw_for_front(g[0], g[1])
        W.move(i, sp[0], sp[1], yaw, "мебель: из ходовой части")
        W.place(Og, W.items[i])


# ----------------------------------------------------------------------------------------------- фаза 5: деревья и лунки
def audit_walkway(W: World, x: float, z: float) -> bool:
    """Точка, которую разбор назовёт «ходовой частью» тротуара (дальше 5 м от кромки, 3 м от фасада и внешнего края)."""
    if W.mat[cj(z), ci(x)] not in (2, 3, 4, 5) or at(W.wide, x, z):
        return False
    dr = float(at(W.d_road, x, z))
    if dr > 13.0 or dr <= 5.0 or float(at(W.d_fac, x, z)) <= 3.0:
        return False
    return W.A.outer_dist(x, z, dr) > 3.0


def tree_constraints(W: World, placed_trees: np.ndarray):
    lamps = lamp_points(W)
    doors = W.door_xz
    stops = [W.fp(W.items[s]) for s in W.stop_idx]

    def ok(xs, zs):
        m = np.ones(len(xs), bool)
        for dx, dz in doors:
            m &= np.hypot(xs - dx, zs - dz) >= RULES["tree_door"]
        for o in stops:
            m &= dist_obb(xs, zs, o) >= RULES["tree_stop"]
        m &= at(W.d_cross, xs, zs) >= RULES["tree_cross"]
        if len(lamps):
            for lx, lz in lamps:
                m &= np.hypot(xs - lx, zs - lz) >= RULES["tree_lamp"]
        if len(placed_trees):
            for tx, tz in placed_trees:
                m &= np.hypot(xs - tx, zs - tz) >= RULES["tree_min_gap"]
        return m
    return ok


def refine_line(W: World, x: float, z: float, line: str, Og: np.ndarray) -> tuple:
    for _ in range(3):
        if line == "curb":
            d = float(at(W.d_road, x, z))
            g = grad(W.d_road, x, z)
            t = RULES["tree_curb"]
        else:
            d = float(at(W.d_out, x, z))
            g = grad(W.d_out, x, z)
            t = RULES["tree_outer"]
        if g == (0.0, 0.0) or abs(d - t) < 0.02:
            break
        nx_, nz_ = x + (t - d) * g[0], z + (t - d) * g[1]
        if bool(at(Og, nx_, nz_)):
            break
        x, z = nx_, nz_
    return x, z


def phase_trees(W: World) -> None:
    trees = [i for i, it in enumerate(W.items) if it[0] in TREES and W.status[i] != "removed" and not W.ug(i)]
    streets, plaza, soft = [], [], []
    for i in trees:
        x, z = W.items[i][1], W.items[i][2]
        m = W.mat[cj(z), ci(x)]
        if m == 1 or bool(at(W.sidewalk, x, z)) or (m in (3,) and at(W.d_road, x, z) <= 13.0):
            streets.append(i)
        elif m in (2, 4, 5):
            plaza.append(i)
        else:
            soft.append(i)
    O = W.build_obstacles(set(streets) | set(plaza))
    Og = W.blocked_grid(O)
    fixed_trees = np.array([(W.items[i][1], W.items[i][2]) for i in soft]) if soft else np.zeros((0, 2))
    placed = [tuple(p) for p in fixed_trees]
    final: list = []                      # индексы деревьев, оставшихся на мощении (для лунок)
    TRUNK = AU.TREE_TRUNK

    def try_line(i: int, around, radius, narrow: bool = False):
        it = W.items[i]
        ok = tree_constraints(W, np.array(placed) if placed else np.zeros((0, 2)))
        # линия «у бордюра» и «у внешнего края»
        def extra(xs, zs):
            dr = at(W.d_road, xs, zs)
            do = at(W.d_out, xs, zs)
            lines = (np.abs(dr - RULES["tree_curb"]) <= 0.25) | ((np.abs(do - RULES["tree_outer"]) <= 0.25) & (at(W.d_fac, xs, zs) >= 3.0)
                                                                  & (dr >= 2.5))
            if narrow:
                # узкая полоса между проезжими частями (< 6 м): ось полосы
                lines = (at(W.d_ns, xs, zs) >= 1.2) & (dr >= 1.2) & (at(W.d_fac, xs, zs) >= 1.5) & at(W.narrow, xs, zs)
            m = lines & at(W.sidewalk, xs, zs) & ok(xs, zs)
            if len(xs):
                m &= np.array([not audit_walkway(W, float(a), float(b)) for a, b in zip(xs, zs)])
            return m
        sp = W.find_spot(it, around, radius, Og, zone="walk", extra=extra, step=0.5)
        return sp

    for i in sorted(streets, key=lambda k: (W.items[k][1], W.items[k][2])):
        it = W.items[i]
        x0, z0 = it[1], it[2]
        sp = try_line(i, (x0, z0), 5.0)
        narrow = False
        if sp is None:
            sp = try_line(i, (x0, z0), 4.0, narrow=True)
            narrow = sp is not None
        if sp is None:
            sp = try_line(i, (x0, z0), 12.0)
        if sp is not None:
            line = "curb" if abs(float(at(W.d_road, sp[0], sp[1])) - RULES["tree_curb"]) <= 0.3 else "outer"
            nx_, nz_ = (sp[0], sp[1]) if narrow else refine_line(W, sp[0], sp[1], line, Og)
            # проверка после уточнения
            okf = tree_constraints(W, np.array(placed) if placed else np.zeros((0, 2)))
            if not bool(okf(np.array([nx_]), np.array([nz_]))[0]):
                nx_, nz_ = sp[0], sp[1]
            if (nx_, nz_) != (x0, z0):
                W.move(i, nx_, nz_, None, "дерево: на линию улицы")
            placed.append((nx_, nz_))
            draw_poly(Og, obb_poly(W.fp(W.items[i]), RULES["gap"]))
            final.append(i)
            continue
        # ближайший газон
        ok = tree_constraints(W, np.array(placed) if placed else np.zeros((0, 2)))
        sp = W.find_spot(it, (x0, z0), 25.0, Og, zone="any",
                         extra=lambda xs, zs: np.isin(at(W.mat, xs, zs), (6, 7)) & ok(xs, zs) & (at(W.d_road, xs, zs) > 1.5))
        if sp is not None:
            W.move(i, sp[0], sp[1], None, "дерево: на газон")
            placed.append((sp[0], sp[1]))
            draw_poly(Og, obb_poly(W.fp(W.items[i]), RULES["gap"]))
            continue
        W.remove(i, "дерево: места на линии и на газоне нет")
    # --- деревья на газоне и грунте: пары ближе 3 м — второе дерево на 3,5 м дальше
    for a_i in soft:
        for b_i in soft:
            if a_i < b_i and W.status[b_i] != "removed" and math.hypot(W.items[a_i][1] - W.items[b_i][1], W.items[a_i][2] - W.items[b_i][2]) < 3.0:
                others = np.array([(W.items[k][1], W.items[k][2]) for k in soft if k != b_i and W.status[k] != "removed"])
                itb = W.items[b_i]
                sp = W.find_spot(itb, (itb[1], itb[2]), 8.0, Og, zone="any",
                                 extra=lambda xs, zs: np.isin(at(W.mat, xs, zs), (6, 7)) & np.array(
                                     [bool((np.hypot(others[:, 0] - a, others[:, 1] - b) >= 3.5).all()) for a, b in zip(xs, zs)]))
                if sp is not None:
                    W.move(b_i, sp[0], sp[1], None, "дерево: ближе 3 м к соседнему")
    # --- площади: ряды остаются, одиночные — на сетку 8 м
    pl = np.array([(W.items[i][1], W.items[i][2]) for i in plaza]) if plaza else np.zeros((0, 2))

    def in_row(i: int) -> bool:
        x, z = W.items[i][1], W.items[i][2]
        n = 0
        for j in plaza:
            if j == i:
                continue
            xj, zj = W.items[j][1], W.items[j][2]
            if (abs(xj - x) < 0.06 and abs(zj - z) <= 8.6) or (abs(zj - z) < 0.06 and abs(xj - x) <= 8.6):
                n += 1
        return n >= 1

    for i in sorted(plaza, key=lambda k: (W.items[k][1], W.items[k][2])):
        it = W.items[i]
        x0, z0 = it[1], it[2]
        ok = tree_constraints(W, np.array(placed) if placed else np.zeros((0, 2)))
        stay = in_row(i) and bool(ok(np.array([x0]), np.array([z0]))[0])
        if not stay:
            # сетка 8 м от начала координат: ближайшая свободная точка
            step = RULES["tree_step"]
            def extra(xs, zs):
                lat = (np.abs(((xs / step) - np.round(xs / step)) * step) < 0.26) & (np.abs(((zs / step) - np.round(zs / step)) * step) < 0.26)
                return lat & ok(xs, zs)
            sp = W.find_spot(it, (x0, z0), 12.0, Og, zone="walk", extra=extra, step=0.5)
            if sp is not None:
                gx, gz = round(sp[0] / step) * step, round(sp[1] / step) * step
                if not bool(at(Og, gx, gz)) and bool(ok(np.array([gx]), np.array([gz]))[0]):
                    sp = (gx, gz, sp[2])
                W.move(i, sp[0], sp[1], None, "дерево: площадь, сетка 8 м")
                x0, z0 = sp[0], sp[1]
            elif not bool(ok(np.array([x0]), np.array([z0]))[0]):
                W.remove(i, "дерево: площадь, места нет")
                continue
        placed.append((x0, z0))
        draw_poly(Og, obb_poly(W.fp(W.items[i]), RULES["gap"]))
        final.append(i)
    # --- лунки под каждым деревом на мощении
    for i in final:
        x, z = W.items[i][1], W.items[i][2]
        if W.mat[cj(z), ci(x)] in (2, 4, 5):
            W.pits.append((round(x, 3), round(z, 3), round(float(at(W.surf_top, x, z)), 3)))
    W.log.append({"деревья": {"на мощении": len(final), "лунок": len(W.pits)}})
