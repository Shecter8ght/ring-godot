#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""«Проспект», этап s3_props: расстановка деревьев и уличных вещей по правилам docs/design/prospekt_map.md §27.2.

Читает снимок сцены (data/blockouts/prospekt_snapshot.json), строит растровую карту улиц (0,25 м): покрытия, фасады,
препятствия, коридоры входов, переходы, маршруты, подходы к ящикам лута — и расставляет вещи заново по правилам:
  входы · остановки · ларьки · проезжая часть · мебель в технической полосе · деревья и лунки · зазоры.
Пишет патч data/blockouts/prospekt_patch_s3_props.json (remove.items / add.items / add.surfaces / add.boxes) и журнал
docs/screens/prospekt/props_after/s3_log.json. Применение: tools/godot.cmd --headless res://tools/prospekt_apply_patch.tscn -- s3_props

    python -X utf8 tools/prospekt_s3_props.py [--virtual путь.json]   # --virtual: снимок «как после патча» для разбора, без патча

Правила и числа — в §27.2; здесь они в словаре RULES. Генераторы карты (build_prospekt*.py) не запускаются.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prospekt_props_audit as AU  # noqa: E402

SNAP = ROOT / "data" / "blockouts" / "prospekt_snapshot.json"
PATCH_OUT = ROOT / "data" / "blockouts" / "prospekt_patch_s3_props.json"
LOG_OUT = ROOT / "docs" / "screens" / "prospekt" / "props_after" / "s3_log.json"

RULES = {
    "tree_curb": 3.0,          # ось дерева от кромки проезжей части, м
    "tree_outer": 1.5,         # ось дерева от внешней кромки тротуара, м
    "tree_step": 8.0,          # шаг вдоль улицы, м
    "tree_min_gap": 6.0,       # между деревьями не ближе
    "tree_door": 4.0,
    "tree_stop": 6.0,
    "tree_cross": 5.0,
    "tree_lamp": 3.0,
    "pit": 1.5,                # лунка 1,5 × 1,5
    "strip": (0.6, 2.5),       # техническая полоса от кромки
    "gap": 0.3,                # зазор между вещами
    "door_depth": 4.0,         # коридор входа наружу
    "door_extra": 1.2,         # ширина двери + 1,2 м
    "route_buf": 1.5,
    "loot_buf": 1.0,
    "kiosk_group": 20.0,
    "kiosk_door": 6.0,
    "max_new_bins": 10,
}

RES = 0.25
GX0, GZ0 = -254.0, -186.0
NX = int((236.0 + 254.0) / RES)
NZ = int((322.0 + 186.0) / RES)
MAT_CODE = {"road": 1, "walk": 2, "parking": 3, "court": 4, "slab": 5, "grass": 6, "mud": 7, "fountain_floor": 8}

TREES, KIOSKS, STOPS = AU.TREES, AU.KIOSKS, AU.BUS_STOPS
BENCHES, BINS, BOLLARDS, PLANTERS, ADS, LAMPS, SIGNS, CABINETS = (AU.BENCHES, AU.BINS, AU.BOLLARDS, AU.PLANTERS,
                                                                    AU.ADS, AU.LAMPS, AU.SIGNS, AU.CABINETS)
MOVABLE_FURN = BENCHES | BINS | BOLLARDS | PLANTERS | ADS | CABINETS | SIGNS
VEHICLES = AU.VEHICLES


def ci(x: float) -> int:
    return int(math.floor((x - GX0) / RES))


def cj(z: float) -> int:
    return int(math.floor((z - GZ0) / RES))


def sl(r) -> tuple:
    return (slice(max(0, cj(r[1])), min(NZ, cj(r[3]) + 1)), slice(max(0, ci(r[0])), min(NX, ci(r[2]) + 1)))


def draw_poly(mask: np.ndarray, pts, val=True) -> None:
    xs = [(p[0] - GX0) / RES for p in pts]
    zs = [(p[1] - GZ0) / RES for p in pts]
    ix0, ix1 = max(0, int(min(xs)) - 1), min(NX, int(max(xs)) + 2)
    iz0, iz1 = max(0, int(min(zs)) - 1), min(NZ, int(max(zs)) + 2)
    if ix1 <= ix0 or iz1 <= iz0:
        return
    im = Image.new("L", (ix1 - ix0, iz1 - iz0), 0)
    ImageDraw.Draw(im).polygon([(x - ix0, z - iz0) for x, z in zip(xs, zs)], fill=1)
    a = np.asarray(im, dtype=bool)
    if val:
        mask[iz0:iz1, ix0:ix1] |= a
    else:
        mask[iz0:iz1, ix0:ix1] &= ~a


def draw_line(mask: np.ndarray, pts, width_m: float) -> None:
    im = Image.fromarray(np.zeros((NZ, NX), np.uint8))
    d = ImageDraw.Draw(im)
    d.line([((p[0] - GX0) / RES, (p[1] - GZ0) / RES) for p in pts], fill=1, width=max(1, int(width_m / RES)))
    mask |= np.asarray(im, dtype=bool)


def obb_poly(o: tuple, grow: float = 0.0) -> list:
    x, z, hw, hd, ax, az = o
    hw += grow
    hd += grow
    return [(x + sx * hw * ax[0] + sz * hd * az[0], z + sx * hw * ax[1] + sz * hd * az[1])
            for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def edt(mask_free: np.ndarray) -> np.ndarray:
    """Расстояние (м) от каждой клетки до ближайшей клетки, где mask_free == False."""
    return ndi.distance_transform_edt(mask_free) * RES


class World:
    def __init__(self, snap_path: Path) -> None:
        self.A = AU.Audit(str(snap_path))
        d = self.A.d
        self.d = d
        self.items: list = [list(it) for it in d["filler"]["items"]]
        self.orig: list = [list(it) for it in self.items]
        self.status: list = ["keep"] * len(self.items)       # keep / moved / removed
        self.note: list = [""] * len(self.items)
        self.added: list = []                                  # новые вещи (запись)
        self.pits: list = []                                   # [x, z] лунки
        self.log: list = []
        self.ents, _ = AU.collect_entrances(self.A)
        self._static()

    # ------------------------------------------------------------------ растр
    def _static(self) -> None:
        d, A = self.d, self.A
        mat = np.zeros((NZ, NX), np.uint8)
        wide = np.zeros((NZ, NX), bool)
        self.surf_top = np.zeros((NZ, NX), np.float32)
        for s in d["surfaces"]:
            r = s["rect"]
            mat[sl(r)] = MAT_CODE.get(s["mat"], 9)
            wide[sl(r)] = min(r[2] - r[0], r[3] - r[1]) > 12.5
            self.surf_top[sl(r)] = float(s.get("y", 0.0)) + float(s.get("t", 0.08))
        self.mat = mat
        self.wide = wide
        self.road = mat == 1
        self.pave = np.isin(mat, (2, 4, 5))
        self.parking = mat == 3
        self.sidewalk = self.pave & ~wide
        self.d_road = edt(~self.road)
        # внешний край — граница полосы тротуара (соседняя широкая площадь или газон — «за краем»), а не слитого мощения
        street = self.road | self.sidewalk | self.parking
        self.d_out = edt(street | (mat == 8))
        # фасады и препятствия
        fac = np.zeros((NZ, NX), bool)
        for b in A.bld:
            fac[sl(b["rect"])] = True
        for w in A.walls_ground:
            r = w["rect"]
            if w["y1"] >= 2.5 and min(r[2] - r[0], r[3] - r[1]) >= 0.2:
                fac[sl(r)] = True
        self.fac = fac
        self.d_fac = edt(~fac)
        self.d_ns = edt(self.sidewalk)          # от клетки тротуара до ближайшей клетки не тротуара
        core = self.d_ns >= 2.9
        self.narrow = self.sidewalk & ~(edt(~core) <= 3.1)      # полосы уже ~6 м (между проезжими частями)
        O = fac.copy()
        for w in A.walls_ground:
            if w["y1"] >= 1.0:
                O[sl(w["rect"])] = True
        for b in d["boxes"]:
            top = b["at"][1] + b["size"][1] * 0.5
            bot = b["at"][1] - b["size"][1] * 0.5
            if not b.get("solid", True) or b["size"][1] < 0.3 or top < 0.3 or bot > 1.5:
                continue
            draw_poly(O, obb_poly(AU.obb(b["at"][0], b["at"][2], b["size"][0], b["size"][2], b.get("yaw", 0.0))))
        for st in d["stairs"]:
            a, b2 = st["from"], st["to"]
            if min(a[1], b2[1]) < -0.3:
                draw_line(O, [(a[0], a[2]), (b2[0], b2[2])], float(st["width"]) + 0.4)
        for rp in d["ramps"]:
            if min(rp["y0"], rp["y1"]) < -0.3:
                O[sl([rp["x0"], rp["z0"], rp["x1"], rp["z1"]])] = True
        for l in d["lamps"]:
            draw_poly(O, obb_poly(AU.obb(l[0], l[2], 0.5, 0.5, 0.0)))
        self.O_static = O
        # переходы (зебры): тонкие полосы 4…5 м длиной
        Z = np.zeros((NZ, NX), bool)
        for b in d["boxes"]:
            if b["size"][1] <= 0.03 and b["mat"] in ("stripe", "paint_white"):
                lo, hi = min(b["size"][0], b["size"][2]), max(b["size"][0], b["size"][2])
                if 3.9 <= hi <= 5.1 and lo <= 1.2:
                    draw_poly(Z, obb_poly(AU.obb(b["at"][0], b["at"][2], b["size"][0], b["size"][2], b.get("yaw", 0.0))))
        # одиночные полосы не переход: оставляем клетки, у которых в радиусе 2 м не меньше трёх других полос
        lab, n = ndi.label(ndi.binary_dilation(Z, iterations=int(1.2 / RES)))
        sizes = ndi.sum(Z, lab, range(1, n + 1))
        keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s * RES * RES > 4.0])
        self.Z = Z & keep
        self.d_cross = edt(~self.Z)
        # маршруты проверки и подходы к ящикам лута
        P = np.zeros((NZ, NX), bool)
        for r in d["probe_routes"]:
            draw_line(P, [tuple(p) for p in r["points"]], RULES["route_buf"] * 2.0)
        self.P = P
        L = np.zeros((NZ, NX), bool)
        for l in d["loot"]:
            draw_poly(L, obb_poly(AU.obb(l["at"][0], l["at"][2], RULES["loot_buf"] * 2.4, RULES["loot_buf"] * 2.4, 0.0)))
        self.L = L
        self.loot_xz = np.array([[l["at"][0], l["at"][2]] for l in d["loot"]])
        # коридоры входов: ширина двери + 1,2 м, 4 м наружу
        E = np.zeros((NZ, NX), bool)
        for e in self.ents:
            n = (e["nx"], e["nz"])
            th = math.atan2(n[0], n[1])
            cor = (e["x"] + n[0] * RULES["door_depth"] * 0.5, e["z"] + n[1] * RULES["door_depth"] * 0.5,
                   (e["w"] + RULES["door_extra"]) * 0.5, RULES["door_depth"] * 0.5,
                   (math.cos(th), -math.sin(th)), (math.sin(th), math.cos(th)))
            draw_poly(E, obb_poly(cor))
        self.E = E
        self.door_xz = np.array([[e["x"], e["z"]] for e in self.ents])
        self.stop_idx = [i for i, it in enumerate(self.items) if it[0] in STOPS and not self.ug(i)]

    # ------------------------------------------------------------------ вещи
    def ug(self, i: int) -> bool:
        it = self.items[i]
        return len(it) > 5 and float(it[5]) <= -1.0

    def fp(self, it: list) -> tuple:
        return self.A.footprint(it)

    def dims(self, it: list) -> tuple:
        o = self.fp(it)
        yaw_eff = math.degrees(math.atan2(-o[4][1], o[4][0]))
        return 2 * o[2], 2 * o[3], (yaw_eff - float(it[3])) % 360.0

    def solid(self, i: int) -> bool:
        return self.A.is_solid(self.items[i][0]) and not self.ug(i)

    def pinned(self, i: int, r: float = 1.9) -> bool:
        it = self.items[i]
        if len(self.loot_xz) == 0:
            return False
        dd = np.hypot(self.loot_xz[:, 0] - it[1], self.loot_xz[:, 1] - it[2])
        return bool(dd.min() < r)

    def build_obstacles(self, skip: set) -> np.ndarray:
        """Растр занятого: статика + все твёрдые вещи, кроме перечисленных в skip (их ставят заново)."""
        O = self.O_static.copy()
        for i, it in enumerate(self.items):
            if i in skip or self.status[i] == "removed" or not self.solid(i):
                continue
            if it[0] in AU.NONBLOCK or it[0] in ("track_3m",):
                continue
            draw_poly(O, obb_poly(self.fp(it)))
        for it in self.added:
            draw_poly(O, obb_poly(self.fp(it)))
        return O

    # ------------------------------------------------------------------ поиск места
    def probe_grid(self, w: float, d: float) -> np.ndarray:
        nx = max(2, int(math.ceil(w / 0.25)) + 1)
        nz = max(2, int(math.ceil(d / 0.25)) + 1)
        xs = np.linspace(-w / 2, w / 2, nx)
        zs = np.linspace(-d / 2, d / 2, nz)
        return np.array([(a, b) for a in xs for b in zs])

    def find_spot(self, it: list, around: tuple, radius: float, Og: np.ndarray, *, yaws=None, zone: str = "strip",
                  extra=None, prefer=None, step: float = 0.5, min_d: float = 0.0) -> tuple | None:
        """Ближайшее к around (x, z) место для вещи it: [x, z, yaw] или None.
        zone: strip — полоса 0,6…2,5 м от кромки; outer — у внешнего края; walk — любое мощение; any — вне проезжей части.
        extra(xs, zs) -> bool-массив допусков (необязательно); prefer(xs, zs) -> штраф к расстоянию."""
        w, dd, yoff = self.dims(it)
        yaw0 = float(it[3])
        yaws = [yaw0] if yaws is None else yaws
        best = None
        gx = np.arange(around[0] - radius, around[0] + radius + 1e-6, step)
        gz = np.arange(around[1] - radius, around[1] + radius + 1e-6, step)
        XX, ZZ = np.meshgrid(gx, gz)
        xs, zs = XX.ravel(), ZZ.ravel()
        dist = np.hypot(xs - around[0], zs - around[1])
        ok = dist <= radius
        xs, zs, dist = xs[ok], zs[ok], dist[ok]
        ix = np.clip(((xs - GX0) / RES).astype(int), 0, NX - 1)
        iz = np.clip(((zs - GZ0) / RES).astype(int), 0, NZ - 1)
        if zone == "strip":
            lo, hi = RULES["strip"]
            c = self.pave[iz, ix] & (self.d_road[iz, ix] >= lo + 0.0) & (self.d_road[iz, ix] <= max(hi, lo + min(w, dd)))
        elif zone == "outer":
            c = self.pave[iz, ix] & (self.d_out[iz, ix] <= 2.6) & (self.d_fac[iz, ix] >= 3.0)
        elif zone == "walk":
            c = self.pave[iz, ix]
        else:
            c = ~self.road[iz, ix]
        c &= ~self.E[iz, ix]
        c &= ~self.P[iz, ix]
        c &= ~self.L[iz, ix]
        xs, zs, dist, ix, iz = xs[c], zs[c], dist[c], ix[c], iz[c]
        if len(xs) == 0:
            return None
        if extra is not None:
            m = extra(xs, zs)
            xs, zs, dist = xs[m], zs[m], dist[m]
        if len(xs) == 0:
            return None
        score = dist.copy()
        if prefer is not None:
            score = score + prefer(xs, zs)
        order = np.argsort(score)
        S = self.probe_grid(w, dd)
        for yw in yaws:
            th = math.radians(yw + yoff)
            ax, az = (math.cos(th), -math.sin(th)), (math.sin(th), math.cos(th))
            # проверка по лучшим кандидатам (до 400 штук на поворот)
            for k in order[:600]:
                px = xs[k] + S[:, 0] * ax[0] + S[:, 1] * az[0]
                pz = zs[k] + S[:, 0] * ax[1] + S[:, 1] * az[1]
                jx = np.clip(((px - GX0) / RES).astype(int), 0, NX - 1)
                jz = np.clip(((pz - GZ0) / RES).astype(int), 0, NZ - 1)
                if Og[jz, jx].any():
                    continue
                if zone in ("strip", "outer", "walk") and not self.pave[jz, jx].all():
                    continue
                if zone == "strip" and (self.d_road[jz, jx] < RULES["strip"][0] - 0.05).any():
                    continue
                if zone == "any" and self.road[jz, jx].any():
                    continue
                if (self.E[jz, jx] | self.L[jz, jx]).any():
                    continue
                sc = score[k] + (0.0 if yw == yaws[0] else 0.2)
                if best is None or sc < best[0]:
                    best = (sc, float(xs[k]), float(zs[k]), yw)
                break
        return None if best is None else (best[1], best[2], best[3])

    def place(self, Og: np.ndarray, it: list) -> None:
        """Занять место новой вещи в растре Og (с зазором)."""
        draw_poly(Og, obb_poly(self.fp(it), RULES["gap"]))

    def blocked_grid(self, O: np.ndarray) -> np.ndarray:
        return edt(~O) < RULES["gap"]

    # ------------------------------------------------------------------ учёт изменений
    def frozen(self, i: int) -> bool:
        """Эстакада и всё западнее X −217 (рынок под эстакадой, сходы, блокпост ЧВК) — не трогаем (бот у сходов чувствителен к вещам)."""
        return self.orig[i][1] < -217.0

    def move(self, i: int, x: float, z: float, yaw: float | None, why: str) -> None:
        if self.frozen(i):
            return
        it = self.items[i]
        it[1], it[2] = round(x, 3), round(z, 3)
        if yaw is not None:
            it[3] = round(yaw, 1)
        self.status[i] = "moved" if self.status[i] != "removed" else "removed"
        self.note[i] = why

    def remove(self, i: int, why: str) -> None:
        if self.frozen(i):
            return
        self.status[i] = "removed"
        self.note[i] = why

    def add(self, rec: list, why: str) -> None:
        self.added.append(rec)
        self.log.append({"добавлено": rec, "why": why})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=str(SNAP))
    ap.add_argument("--virtual", default="", help="записать снимок «как после патча» для разбора (без применения к сцене)")
    a = ap.parse_args()
    from prospekt_s3_finish import run_all
    W = run_all(Path(a.snapshot), Path(a.virtual) if a.virtual else None)
    c = Counter(W.status)
    print("вещей: оставлено", c["keep"], "перенесено", c["moved"], "убрано", c["removed"], "добавлено", len(W.added), "лунок", len(W.pits))
    print("патч:", PATCH_OUT)


if __name__ == "__main__":
    main()
