# -*- coding: utf-8 -*-
"""Этап s3_props: урны у лавок и остановок, зазоры, вещи в зданиях и стенах, сборка патча."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

import prospekt_props_audit as AU
from prospekt_s3_props import (GX0, GZ0, NX, NZ, RES, RULES, World, BENCHES, BINS, BOLLARDS, PLANTERS, ADS, LAMPS, SIGNS,
                               CABINETS, KIOSKS, STOPS, TREES, ci, cj, draw_poly, obb_poly, PATCH_OUT, LOG_OUT)
from prospekt_s3_rules import at, samples, furn_loc, yaw_for_front, grad


# ----------------------------------------------------------------------------------------------- урны
def phase_bins(W: World) -> None:
    bins = [i for i, it in enumerate(W.items) if it[0] in BINS and W.status[i] != "removed" and not W.ug(i)]
    needy = []      # (kind, i, x, z)
    for s in W.stop_idx:
        if W.status[s] != "removed":
            needy.append(("stop", s, W.items[s][1], W.items[s][2]))
    for i, it in enumerate(W.items):
        if it[0] in BENCHES and W.status[i] != "removed" and not W.ug(i):
            x, z = it[1], it[2]
            if W.mat[cj(z), ci(x)] in (2, 4, 5, 3) and at(W.d_road, x, z) <= 13.0 and not at(W.wide, x, z):
                needy.append(("bench", i, x, z))
    def has_bin(x, z, r=6.0):
        return any(math.hypot(W.items[b][1] - x, W.items[b][2] - z) <= r for b in bins if W.status[b] != "removed")
    needs = [n for n in needy if not has_bin(n[2], n[3])]
    spare = [b for b in bins if not any(math.hypot(W.items[b][1] - n[2], W.items[b][2] - n[3]) <= 6.0 for n in needy)
             and not W.pinned(b)]
    O = W.build_obstacles(set(spare))
    Og = W.blocked_grid(O)
    new_bins = 0
    moved = 0
    done = 0

    def put_near(rec: list, n: tuple):
        _, i, x, z = n
        for zone in ("walk", "any"):
            sp = W.find_spot(rec, (x, z), 4.5, Og, zone=zone)
            if sp is not None:
                return sp
        return None

    for n in sorted(needs, key=lambda t: 0 if t[0] == "stop" else 1):
        if has_bin(n[2], n[3]):
            continue
        cand = sorted([b for b in spare if W.status[b] != "removed" and math.hypot(W.items[b][1] - n[2], W.items[b][2] - n[3]) <= 45.0],
                      key=lambda b: math.hypot(W.items[b][1] - n[2], W.items[b][2] - n[3]))
        if cand:
            b = cand[0]
            sp = put_near(W.items[b], n)
            if sp is not None:
                spare.remove(b)
                W.move(b, sp[0], sp[1], None, "урна: к лавке / остановке")
                W.place(Og, W.items[b])
                moved += 1
                continue
        if new_bins >= RULES["max_new_bins"]:
            continue
        rec = ["bin", n[2], n[3], 0.0]
        sp = put_near(rec, n)
        if sp is None:
            continue
        rec = ["bin", round(sp[0], 3), round(sp[1], 3), 0.0]
        W.add(rec, "урна у лавки / остановки (нет рядом)")
        W.place(Og, rec)
        new_bins += 1
    # оставшиеся лишние урны, которые стояли в ходовой части, уже перенесены фазой мебели
    W.log.append({"урны": {"перенесено к лавкам и остановкам": moved, "новых": new_bins,
                           "лавок и остановок без урны осталось": sum(1 for n in needy if not has_bin(n[2], n[3]))}})


# ----------------------------------------------------------------------------------------------- зазоры, здания, стены
CLS = BENCHES | BINS | BOLLARDS | PLANTERS | ADS | LAMPS | SIGNS | CABINETS


def pairs_overlap(W: World) -> list:
    cand = [i for i, it in enumerate(W.items) if W.status[i] != "removed" and not W.ug(i) and W.solid(i)
            and (it[0] in CLS or it[0] in TREES or it[0] in KIOSKS or it[0] in STOPS)]
    cand.sort(key=lambda i: W.items[i][1])
    fps = {i: W.fp(W.items[i]) for i in cand}
    out = []
    for ai in range(len(cand)):
        a = cand[ai]
        for bi in range(ai + 1, len(cand)):
            b = cand[bi]
            if W.items[b][1] - W.items[a][1] > 6.0:
                break
            if abs(W.items[b][2] - W.items[a][2]) > 6.0:
                continue
            if AU.obb_overlap(fps[a], fps[b], -0.05):
                out.append((a, b))
    return out


def inside_bad(W: World) -> list:
    A = W.A
    bad = []
    wall_obbs = [AU.rect_obb(w["rect"]) for w in A.walls_ground if min(w["rect"][2] - w["rect"][0], w["rect"][3] - w["rect"][1]) >= 0.1
                 and w["y1"] >= 1.5]
    for i, it in enumerate(W.items):
        if W.status[i] == "removed" or W.ug(i) or not (it[0] in CLS or it[0] in TREES or it[0] in KIOSKS):
            continue
        x, z = it[1], it[2]
        hit = False
        for b in A.bld:
            r = b["rect"]
            if r[0] + 0.3 < x < r[2] - 0.3 and r[1] + 0.3 < z < r[3] - 0.3:
                hit = True
                break
        if not hit:
            o = W.fp(it)
            for wo in wall_obbs:
                if abs(wo[0] - x) > 8 or abs(wo[1] - z) > 8:
                    continue
                if AU.obb_overlap(o, wo, -0.05):
                    hit = True
                    break
        if hit:
            bad.append(i)
    return bad


def phase_clearances(W: World) -> None:
    for rnd in range(4):
        bad = set(inside_bad(W))
        ov = pairs_overlap(W)
        movers = set(bad)
        for a, b in ov:
            pick = None
            # двигаем то, что легче: кадка / ларёк / лавка / урна / щит / шкаф / фонарь; дерево и остановка стоят
            order = [PLANTERS, KIOSKS, BENCHES, BINS, ADS, CABINETS, SIGNS, BOLLARDS, LAMPS, TREES]
            for grp in order:
                for k in (a, b):
                    if W.items[k][0] in grp and not W.pinned(k) and W.items[k][0] not in STOPS:
                        pick = k
                        break
                if pick is not None:
                    break
            if pick is not None:
                movers.add(pick)
        if not movers:
            break
        O = W.build_obstacles(movers)
        Og = W.blocked_grid(O)
        for i in sorted(movers):
            it = W.items[i]
            if W.pinned(i):
                W.place(Og, it)
                continue
            sp = None
            zone_pref = ("strip", "walk", "any") if it[0] in (BINS | BOLLARDS | CABINETS | ADS | SIGNS | KIOSKS) else ("any",)
            for zn in zone_pref:
                for rad in (3.0, 7.0, 14.0):
                    sp = W.find_spot(it, (it[1], it[2]), rad, Og, zone=zn)
                    if sp is not None:
                        break
                if sp is not None:
                    break
            if sp is None:
                W.log.append({"зазоры": "места нет", "item": it[:4]})
                W.place(Og, it)
                continue
            W.move(i, sp[0], sp[1], sp[2], "зазор / здание / стена")
            W.place(Og, W.items[i])


# ----------------------------------------------------------------------------------------------- патч
def pit_pieces(W: World) -> tuple:
    s = RULES["pit"]
    surfaces, boxes = [], []
    for n, (x, z, top) in enumerate(W.pits):
        surfaces.append({"id": f"s3_pit_{n:03d}", "mat": "mud", "rect": [round(x - s / 2, 3), round(z - s / 2, 3), round(x + s / 2, 3), round(z + s / 2, 3)],
                         "y": top, "t": 0.03})
        bw, bh = 0.08, 0.08
        yc = top + bh / 2.0
        e = s / 2 + bw / 2
        for sx, sz, sw, sd in ((0.0, -e, s + 2 * bw, bw), (0.0, e, s + 2 * bw, bw), (-e, 0.0, bw, s), (e, 0.0, bw, s)):
            boxes.append({"at": [round(x + sx, 3), round(yc, 3), round(z + sz, 3)], "size": [round(sw, 3), bh, round(sd, 3)],
                          "mat": "concrete", "yaw": 0.0, "solid": False})
    return surfaces, boxes


def build_patch(W: World) -> dict:
    remove, add_items = [], []
    for i, st in enumerate(W.status):
        if st == "moved" and W.items[i] == W.orig[i]:
            W.status[i] = "keep"
        if st == "keep" or W.status[i] == "keep":
            continue
        o = W.orig[i]
        remove.append({"kits": [o[0]], "rect": [round(o[1] - 0.06, 3), round(o[2] - 0.06, 3), round(o[1] + 0.06, 3), round(o[2] + 0.06, 3)]})
        if st == "moved":
            add_items.append(W.items[i])
    add_items += W.added
    # повторы: вещь рядом с убранной в том же месте (дубликат записи) — вернуть
    rem_keys = {}
    for r in remove:
        rem_keys.setdefault((r["kits"][0], r["rect"][0], r["rect"][1]), r)
    for i, st in enumerate(W.status):
        if st != "keep":
            continue
        o = W.orig[i]
        for r in remove:
            if r["kits"][0] == o[0] and r["rect"][0] <= o[1] <= r["rect"][2] and r["rect"][1] <= o[2] <= r["rect"][3]:
                add_items.append(o)       # осталась «не тронутая» вещь, попавшая под чужое правило, — вернуть
                break
    surfaces, boxes = pit_pieces(W)
    return {"remove": {"items": remove, "pieces": [], "nodes": []},
            "add": {"items": add_items, "surfaces": surfaces, "boxes": boxes}}


def virtual_snapshot(W: World, patch: dict, out: Path) -> None:
    """Снимок «как после патча» для разбора: вещи и покрытия."""
    d = json.loads(json.dumps(W.d))
    items = [list(o) for o in W.orig]
    rem = patch["remove"]["items"]
    kept = []
    for it in items:
        if any(it[0] in r["kits"] and r["rect"][0] <= it[1] <= r["rect"][2] and r["rect"][1] <= it[2] <= r["rect"][3] for r in rem):
            continue
        kept.append(it)
    kept += patch["add"]["items"]
    d["filler"]["items"] = kept
    d["surfaces"] += patch["add"]["surfaces"]
    d["boxes"] += patch["add"]["boxes"]
    out.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def run_all(snap: Path, virtual: Path | None) -> World:
    from prospekt_s3_rules import phase_entrances, phase_stops, phase_kiosks, phase_road, phase_furniture, phase_trees
    W = World(snap)
    for name, fn in (("входы", phase_entrances), ("остановки", phase_stops), ("ларьки и остановки", phase_kiosks), ("проезжая часть", phase_road),
                     ("мебель", phase_furniture), ("деревья и лунки", phase_trees), ("урны", phase_bins),
                     ("зазоры", phase_clearances)):
        before = sum(1 for s in W.status if s != "keep")
        fn(W)
        print(f"фаза «{name}»: изменено вещей {sum(1 for s in W.status if s != 'keep') - before}")
    patch = build_patch(W)
    patch["meta"] = {"stage": "s3_props", "purpose": "расстановка деревьев и уличных вещей по правилам docs/design/prospekt_map.md §27.2"}
    PATCH_OUT.write_text(json.dumps(patch, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    stat = Counter()
    for i, st in enumerate(W.status):
        if st != "keep":
            stat[(W.orig[i][0], st, W.note[i])] += 1
    LOG_OUT.parent.mkdir(parents=True, exist_ok=True)
    LOG_OUT.write_text(json.dumps({"итоги": [[list(k), v] for k, v in sorted(stat.items())], "журнал": W.log, "лунок": len(W.pits),
                                   "новых вещей": len(W.added)}, ensure_ascii=False, indent=1), encoding="utf-8")
    if virtual is not None:
        virtual_snapshot(W, patch, virtual)
    return W
