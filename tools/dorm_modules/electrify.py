"""Электрика общежития в стенд: светильники, выключатели, розетки, коробки и провода по плану (data/blockouts/dorm.json)
→ data/blockouts/dorm_electrics.json.

  python -X utf8 tools/dorm_modules/electrify.py

Интервью 2026-11-01: светильники вперемешку (открытые на две трубки и с рассеивателем), проводка вперемешку (в основном
плоский на гвоздиках с распаечными коробками, кое-где старый витой на роликах и обрывки), выключатели и розетки
вперемешку. Расстановка (владелец: провода «как в жизни», мигающих «1–2 на этаж»):
  помещение — светильник по середине потолка; выключатель у двери изнутри, со стороны ручки (дверь открывается
  к ближней стене), 1,5 м; от него провод вверх до коробки под потолком, с неё — на потолок и к светильнику;
  в жилой комнате ещё розетка: от коробки по стене под потолком к ближнему углу, по боковой стене и вниз;
  коридор — светильники вдоль оси между балками, у каждого провод по потолку к стене и вниз до коробки; у лестницы —
  выключатель; на стенах коридора кое-где старый витой провод на роликах с обрывком;
  закраска при ремонте (варианты износа) — по помещению: ниже линии зелёной панели — краской, выше — побелкой;
  мигающие — 1–2 светильника с трубками в коридорах каждого этажа (стенд даёт им тусклый свет и мерцание трубок).
Случай — по id помещения и этажу, повторяемый. Оси — Godot (y вверх); у модели: стенное лицом в +Z, потолочное
висит вниз от y = 0 вдоль X, модуль провода — от начала вдоль +X по поверхности z = 0 (провод на +Z).
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "data/blockouts/dorm.json"
INDEX = ROOT / "assets/models/dorm/electrics/electrics.json"
OUT = ROOT / "data/blockouts/dorm_electrics.json"
MODELS = json.loads(INDEX.read_text(encoding="utf-8"))
UP = np.array([0.0, 1.0, 0.0])
SWITCH_H = 1.5          # выключатель от пола, м
SOCKET_H = 0.9          # розетка
BOX_DROP = 0.42         # середина коробки ниже потолка
BOX_R = 0.046
CEIL_RISE = 0.35        # модуль «стена — потолок»: 0,35 по стене и 0,35 по потолку
FOLD_IN = MODELS["el_wire_fold"]["ports"]["end"][0]     # залом: от начала до оси второго колена
FOLD_OUT = -MODELS["el_wire_fold"]["ports"]["end"][1]   # и колено вниз
FAR = {"ceiling": 40.0, "wall": 18.0, "wire": 20.0}
# что висит на потолке по виду помещения (модель: вес)
CEILING = {
    "corridor": {"el_lsp_2": 3, "el_lsp_1": 2, "el_lsp_0": 1.5, "el_lpo_closed": 1.5, "el_lpo_hanging": 1, "el_lpo_torn": 1},
    "room": {"el_pendant_bulb": 2, "el_pendant_broken": 1.5, "el_pendant_empty": 1.5, "el_plafond_glass": 2.5,
             "el_plafond_open": 1.5, "el_lsp_1": 0.5, "el_lsp_0": 0.5},
    "wet": {"el_plafond_glass": 3, "el_plafond_open": 2},
    "service": {"el_lpo_closed": 2, "el_lpo_hanging": 1, "el_lsp_2": 1, "el_lsp_1": 1, "el_lsp_0": 1},
    "storage": {"el_pendant_bulb": 1, "el_pendant_broken": 1, "el_pendant_empty": 1},
}
KIND = {"room": "room", "toilets": "wet", "showers": "wet", "wash": "wet", "kitchen": "service", "laundry": "service",
        "lounge": "service", "hall": "service", "vestibule": "service", "commandant": "service", "watch": "service",
        "turn": "service", "storage": "storage", "tech": "service"}
TUBES = {"el_lsp_2", "el_lsp_1", "el_lpo_closed", "el_lpo_hanging", "el_lpo_torn"}


def unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def r4(v) -> list[float]:
    return [round(float(x), 4) for x in v]


class Wiring:
    def __init__(self, plan: dict):
        self.plan = plan
        self.items: list[dict] = []
        self.lights: list[dict] = []
        self.fin = plan["finish"]

    # ------------------------------------------------------------------ установка модели
    def put(self, model: str, at, x, y, z, section: str, tag: str, variant: dict | None = None, **extra) -> dict:
        if isinstance(variant, str):      # закраска провода — код варианта его набора
            variant = {MODELS[model]["sets"][0]: variant}
        item = {"id": f"{tag}_{len(self.items)}", "section": section, "model": model, "origin": r4(at),
                "basis": r4(list(x) + list(y) + list(z)), "far": FAR[MODELS[model]["kind"]]}
        if variant:
            item["variant"] = variant
        item.update(extra)
        self.items.append(item)
        return item

    def wall_item(self, model, at, n, section, tag, variant=None, **extra):
        n = unit(n)
        return self.put(model, at, np.cross(UP, n), UP, n, section, tag, variant, **extra)

    def ceiling_item(self, model, at, axis, section, tag, variant=None, **extra):
        axis = unit(axis)
        return self.put(model, at, axis, UP, np.cross(axis, UP), section, tag, variant, **extra)

    # ------------------------------------------------------------------ провод
    def run(self, start, d, n, length, section, tag, variant=None) -> np.ndarray:
        """Прямой провод от start вдоль d по поверхности с нормалью n: модули по 1 м, хвост — 0,5 м или 1 м, растянутый
        по длине (0,75…1,5); короче 6 см — не кладётся."""
        start, d, n = np.asarray(start, float), unit(d), unit(n)
        pos, left = start.copy(), float(length)
        while left > 1e-3:
            if left >= 1.5:
                model, k = "el_wire_1m", 1.0
            elif left >= 0.75:
                model, k = "el_wire_1m", left
            elif left >= 0.06:
                model, k = "el_wire_05m", left / 0.5
            else:
                break
            self.put(model, pos, d * k, np.cross(n, d), n, section, tag, variant)
            step = k * MODELS[model]["length"]
            pos, left = pos + d * step, left - step
        return start + d * float(length)

    def fold(self, corner, d_in, d_out, n, section, tag, variant=None) -> tuple[np.ndarray, np.ndarray]:
        """Залом провода на 90° в плоскости поверхности: угол — пересечение осей колен. Возвращает начало и конец модуля."""
        d_in, d_out, n = unit(d_in), unit(d_out), unit(n)
        y = np.cross(n, d_in)
        if np.dot(d_out, y) > 0:      # поворот в другую сторону — зеркально
            y = -y
        at = np.asarray(corner, float) - d_in * FOLD_IN
        self.put("el_wire_fold", at, d_in, y, n, section, tag, variant)
        return at, np.asarray(corner, float) + d_out * FOLD_OUT

    def to_ceiling(self, wall_pt, n, section, tag, variant=None) -> np.ndarray:
        """С коробки на потолок: wall_pt — на стене на 0,35 ниже потолка; конец — на потолке в 0,35 от стены."""
        n = unit(n)
        self.put("el_wire_ceiling", wall_pt, np.cross(UP, n), UP, n, section, tag, variant)
        return np.asarray(wall_pt, float) + UP * CEIL_RISE + n * CEIL_RISE

    def paint(self, rng: random.Random, repainted: bool, floor_y: float, h: float, clear: float, ceiling: bool = False):
        """Вариант закраски по высоте: ниже линии зелёной панели — краска, выше и потолок — побелка."""
        if not repainted or rng.random() < 0.2:
            return None
        return "whitewash" if ceiling or h - floor_y > clear * self.fin["paint_lower_fraction"] else "paint"


def variant_for(model: str, rng: random.Random, paint: str | None = None) -> dict:
    """Отделка вперемешку (варианты наборов модели) и закраска у настенного."""
    out = {}
    for s, codes in MODELS[model].get("variants", {}).items():
        finishes = [c for c in codes if c not in ("paint", "whitewash")]
        if paint and paint in codes:
            out[s] = paint
        elif finishes and rng.random() < 0.5:
            out[s] = rng.choice(finishes)
    return out


def pick(rng: random.Random, table: dict) -> str:
    keys = list(table)
    return rng.choices(keys, weights=[table[k] for k in keys])[0]


# ---------------------------------------------------------------------- помещения

def door_of(space: dict, doors: list[dict]):
    """Дверь помещения: (стена «x0/x1/z0/z1», положение вдоль стены, ширина)."""
    x0, z0, x1, z1 = space["rect"]
    best = None
    for d in doors:
        ax, ay, az = d["at"]
        if abs(ay - space["y"]) > 0.2:
            continue
        if d["axis"] == "z" and x0 - 0.1 <= ax <= x1 + 0.1:
            for wall, zw in (("z0", z0), ("z1", z1)):
                gap = abs(az - zw)
                if gap < 0.6 and (best is None or gap < best[3]):
                    best = (wall, ax, float(d["width"]), gap)
        elif d["axis"] == "x" and z0 - 0.1 <= az <= z1 + 0.1:
            for wall, xw in (("x0", x0), ("x1", x1)):
                gap = abs(ax - xw)
                if gap < 0.6 and (best is None or gap < best[3]):
                    best = (wall, az, float(d["width"]), gap)
    return best


class Space:
    """Прямоугольное помещение: стены — плоскости по краям rect, нормаль внутрь, касательная вдоль стены."""

    def __init__(self, s: dict, clear: float):
        self.s = s
        self.x0, self.z0, self.x1, self.z1 = s["rect"]
        self.y = float(s["y"])
        self.H = self.y + clear
        self.clear = clear
        self.c = np.array([(self.x0 + self.x1) / 2, self.H, (self.z0 + self.z1) / 2])

    def wall(self, w: str):
        """(точка на линии стены у пола, нормаль внутрь, касательная по +оси, ось касательной, пределы вдоль)."""
        if w == "z0":
            return np.array([0, self.y, self.z0]), np.array([0, 0, 1.0]), np.array([1.0, 0, 0]), 0, (self.x0, self.x1)
        if w == "z1":
            return np.array([0, self.y, self.z1]), np.array([0, 0, -1.0]), np.array([1.0, 0, 0]), 0, (self.x0, self.x1)
        if w == "x0":
            return np.array([self.x0, self.y, 0]), np.array([1.0, 0, 0]), np.array([0, 0, 1.0]), 2, (self.z0, self.z1)
        return np.array([self.x1, self.y, 0]), np.array([-1.0, 0, 0]), np.array([0, 0, 1.0]), 2, (self.z0, self.z1)

    def point(self, w: str, along: float, h: float) -> np.ndarray:
        base, _, t, ax, _ = self.wall(w)
        p = base.copy()
        p[ax] = along
        p[1] = self.y + h
        return p


def corner_walls(w: str) -> tuple[str, str]:
    """Боковые стены у стены w: (у меньшего края, у большего)."""
    return ("x0", "x1") if w in ("z0", "z1") else ("z0", "z1")


def room_wiring(W: Wiring, s: dict, doors: list[dict], clear: float, section: str, kind: str) -> None:
    sp = Space(s, clear)
    rng = random.Random(s["id"])
    tag = s["id"]
    repainted = rng.random() < 0.55
    door = door_of(s, doors)
    # светильник по середине; длинные — вдоль длинной стороны
    model = pick(rng, CEILING[kind])
    wide = (sp.x1 - sp.x0) >= (sp.z1 - sp.z0)
    axis = np.array([1.0, 0, 0]) if wide else np.array([0, 0, 1.0])
    fixtures = [sp.c]
    if s["kind"] == "lounge":
        off = axis * (max(sp.x1 - sp.x0, sp.z1 - sp.z0) / 4)
        fixtures = [sp.c - off, sp.c + off]
    for k, at in enumerate(fixtures):
        W.ceiling_item(model, at, axis, section, f"{tag}_lamp{k}", variant_for(model, rng))
    if door is None:
        return
    wname, dpos, dwidth, _ = door
    base, n, t, ax, (lo, hi) = sp.wall(wname)
    mid = (lo + hi) / 2
    side = 1.0 if mid > dpos else -1.0          # ручка — к середине стены, петли — у ближнего угла
    u_s = dpos + side * (dwidth / 2 + 0.2)
    if not (lo + 0.1 < u_s < hi - 0.1):
        return
    sw_model = rng.choice(["el_switch_round", "el_switch_white"])
    p_s = sp.point(wname, u_s, SWITCH_H)
    pv = W.paint(rng, repainted, sp.y, p_s[1], clear)
    W.wall_item(sw_model, p_s, n, section, f"{tag}_sw", variant_for(sw_model, rng, pv),
                switch_on=rng.random() < 0.5)
    # вверх до коробки
    p_box = sp.point(wname, u_s, clear - BOX_DROP)
    bottom = p_s + UP * 0.035
    W.run(bottom, UP, n, (p_box[1] - BOX_R) - bottom[1], section, tag, W.paint(rng, repainted, sp.y, p_s[1] + 0.5, clear))
    W.wall_item("el_box", p_box, n, section, f"{tag}_box", variant_for("el_box", rng, W.paint(rng, repainted, sp.y, p_box[1], clear)))
    wv = W.paint(rng, repainted, sp.y, p_box[1], clear, ceiling=True)
    on_ceiling = W.to_ceiling(sp.point(wname, u_s, clear - CEIL_RISE), n, section, tag, wv)
    # по потолку внутрь до оси светильника, залом к нему, до края светильника
    target = fixtures[0]
    reach = float(np.dot(target - on_ceiling, n))
    across = float(np.dot(target - on_ceiling, t))
    half = MODELS[model]["aabb"]["size"]
    edge_n = (half[0] if abs(np.dot(axis, n)) > 0.5 else half[2]) / 2
    edge_t = (half[0] if abs(np.dot(axis, t)) > 0.5 else half[2]) / 2
    down = np.array([0, -1.0, 0])
    if abs(across) < 0.25:
        W.run(on_ceiling, n, down, reach - edge_n, section, tag, wv)
    else:
        d_t = t * math.copysign(1.0, across)
        corner = on_ceiling + n * reach
        W.run(on_ceiling, n, down, reach - FOLD_IN, section, tag, wv)
        _, end = W.fold(corner, n, d_t, down, section, tag, wv)
        W.run(end, d_t, down, abs(across) - FOLD_OUT - edge_t, section, tag, wv)
    # розетка в жилой: от коробки по стене под потолком к ближнему углу, по боковой стене и вниз
    if s["kind"] != "room":
        return
    walls = corner_walls(wname)
    to_hi = (hi - u_s) < (u_s - lo)
    d_wall = t if to_hi else -t
    side_wall = walls[1] if to_hi else walls[0]
    start = p_box + d_wall * BOX_R
    length = (hi - u_s if to_hi else u_s - lo) - BOX_R - 0.004
    W.run(start, d_wall, n, length, section, tag, wv)
    sb, sn, st, sax, (slo, shi) = sp.wall(side_wall)
    # по боковой стене — от угла внутрь помещения (по нормали стены двери)
    along0 = p_box[2] if sax == 2 else p_box[0]
    corner_pt = sp.point(side_wall, along0, clear - BOX_DROP)
    socket_at = 1.35
    d_side = n
    W.run(corner_pt + d_side * 0.004, d_side, sn, socket_at - FOLD_IN, section, tag, wv)
    _, end = W.fold(corner_pt + d_side * socket_at, d_side, -UP, sn, section, tag, wv)
    p_sock = corner_pt + d_side * socket_at
    p_sock[1] = sp.y + SOCKET_H
    sv = W.paint(rng, repainted, sp.y, p_sock[1], clear)
    W.run(end, -UP, sn, end[1] - (p_sock[1] + 0.035), section, tag, W.paint(rng, repainted, sp.y, sp.y + 1.2, clear))
    so_model = rng.choice(["el_socket_round", "el_socket_white"])
    W.wall_item(so_model, p_sock, sn, section, f"{tag}_so", variant_for(so_model, rng, sv))


# ---------------------------------------------------------------------- коридоры

def corridor_wiring(W: Wiring, plan: dict, floor: int, clear: float, y: float, section: str) -> None:
    rng = random.Random(f"corridor{floor}")
    H = y + clear
    portals = [p for p in plan["portals"] if p["floor"] == floor]
    beams_x = sorted(p["at"][0] for p in portals if p["kind"] == "transverse" and abs(p["at"][2]) < 0.1)
    beams_z = sorted(p["at"][2] for p in portals if p["kind"] == "transverse" and abs(p["at"][2]) > 0.1)
    openings = [p for p in portals if p["kind"] == "side_opening"]
    doors = [d for d in plan["doors"] if abs(d["at"][1] - y) < 0.2]
    fixtures = []   # (точка, ось, полоса)

    def spans(lo, hi, n_per):
        mids = []
        for k in range(n_per):
            mids.append(lo + (hi - lo) * (k + 0.5) / n_per)
        return mids
    # главный коридор: x 0…43,41, z ±1,7; между балками, длинные куски — по две
    bounds = [0.0] + beams_x + [43.41]
    for a, b in zip(bounds[:-1], bounds[1:]):
        lo, hi = a + (0.2 if a > 0 else 0.0), b - (0.2 if b < 43.41 else 0.0)
        n_per = 2 if hi - lo > 7.0 else 1
        for x in spans(lo, hi, n_per):
            if abs(x - 36.7) < 0.8:        # двойная дверь в хозкрыло поперёк коридора
                x += 1.0
            fixtures.append((np.array([x, H, 0.0]), np.array([1.0, 0, 0]), "main"))
    # коридор хозкрыла: x 41,71, z −8,88…−39
    zb = [-8.88] + sorted(beams_z, reverse=True) + [-39.0]
    for a, b in zip(zb[:-1], zb[1:]):
        lo, hi = b + 0.2, a - (0.2 if a > -8.88 else 0.0)
        n_per = max(1, int((hi - lo) / 5.0))
        for z in spans(lo, hi, n_per):
            fixtures.append((np.array([41.71, H, z]), np.array([0, 0, 1.0]), "annex"))

    def wall_free(axis_pos: float, wall_z: float) -> bool:
        """Есть ли стена главного коридора z = wall_z в месте axis_pos (нет проёма и двери ±0,35)."""
        for p in openings:
            if math.copysign(1, p["at"][2]) == math.copysign(1, wall_z) and abs(axis_pos - p["at"][0]) < p["clear_width"] / 2 + 0.3:
                return False
        for d in doors:
            if d["axis"] == "z" and math.copysign(1, d["at"][2]) == math.copysign(1, wall_z) and \
                    abs(axis_pos - d["at"][0]) < d["width"] / 2 + 0.35:
                return False
        return True

    tube_fixtures = []
    for k, (at, axis, band) in enumerate(fixtures):
        model = pick(rng, CEILING["corridor"])
        tag = f"f{floor}_corr{k}"
        item = W.ceiling_item(model, at, axis, section, tag, variant_for(model, rng))
        if model in TUBES and band == "main":
            tube_fixtures.append(item)
        repainted = rng.random() < 0.5
        half = MODELS[model]["aabb"]["size"][2] / 2
        if band == "main":
            for wz in (1.7, -1.7):
                if wall_free(at[0], wz):
                    break
            else:
                continue
            n = np.array([0, 0, -math.copysign(1.0, wz)])
            wall_pt = np.array([at[0], H - CEIL_RISE, wz])
        else:
            wz = 43.41
            n = np.array([-1.0, 0, 0])
            wall_pt = np.array([wz, H - CEIL_RISE, at[2]])
        wv = W.paint(rng, repainted, y, H, clear, ceiling=True)
        on_ceiling = W.to_ceiling(wall_pt, n, section, tag, wv)
        reach = float(np.dot(at - on_ceiling, n))
        W.run(on_ceiling, n, np.array([0, -1.0, 0]), reach - half, section, tag, wv)
        box = wall_pt.copy()
        box[1] = H - BOX_DROP
        W.wall_item("el_box", box, n, section, f"{tag}_box", variant_for("el_box", rng, W.paint(rng, repainted, y, box[1], clear)))
    # мигающие: 1–2 светильника с трубками на этаж
    rng.shuffle(tube_fixtures)
    for item in tube_fixtures[: rng.choice([1, 2])]:
        W.lights.append({"id": item["id"] + "_flicker", "section": section, "fixture": item["id"], "model": item["model"],
                         "seed": rng.randrange(1 << 30)})
    # выключатель коридора у лестницы
    p_s = np.array([18.3, y + SWITCH_H, -1.7])
    n = np.array([0, 0, 1.0])
    sw = rng.choice(["el_switch_round", "el_switch_white"])
    W.wall_item(sw, p_s, n, section, f"f{floor}_corr_sw", variant_for(sw, rng), switch_on=True)
    p_box = np.array([18.3, H - BOX_DROP, -1.7])
    W.run(p_s + UP * 0.035, UP, n, (p_box[1] - BOX_R) - (p_s[1] + 0.035), section, f"f{floor}_corr_sw")
    W.wall_item("el_box", p_box, n, section, f"f{floor}_corr_swbox", variant_for("el_box", rng))
    # старый витой на роликах — по два куска на этаж в простенках без дверей
    spots = []
    for x in np.arange(1.0, 42.0, 0.5):
        for wz in (1.7, -1.7):
            if all(wall_free(float(xx), wz) for xx in (x, x + 0.8, x + 1.6)) and \
                    all(abs(x + dx - b) > 0.45 for b in beams_x for dx in (0.0, 0.8, 1.6)):
                spots.append((float(x), wz))
    rng.shuffle(spots)
    taken = []
    for x, wz in spots:
        if len(taken) == 2:
            break
        if any(abs(x - tx) < 4.0 for tx, _ in taken):
            continue
        taken.append((x, wz))
        n = np.array([0, 0, -math.copysign(1.0, wz)])
        d = np.array([1.0, 0, 0]) if n[2] > 0 else np.array([-1.0, 0, 0])
        start = np.array([x if n[2] > 0 else x + 1.6, H - 0.55, wz])
        W.put("el_wire_twisted", start, d, UP, n, section, f"f{floor}_twisted", variant_for("el_wire_twisted", random.Random(x)))


def main() -> None:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    W = Wiring(plan)
    clears = plan["scale"]["ceiling_clear"]
    floors_y = plan["scale"]["floor_y"]
    doors = plan["doors"]
    # потолок с проломом над комнатой — проводка оборвана вместе с перекрытием
    broken = {b["room_below"] for b in plan.get("breaches", [])}
    for s in plan["spaces"]:
        kind = KIND.get(s["kind"])
        if kind is None or s["id"] in broken or s["kind"] == "tech":
            continue
        f = int(s["floor"])
        room_wiring(W, s, doors, clears[f - 1], f"Floor{f}", kind)
    for f, y in enumerate(floors_y, start=1):
        if f == 5:
            continue  # техэтаж — открытый зал без коридора (свет — своими светильниками потом)
        corridor_wiring(W, plan, f, clears[f - 1], y, f"Floor{f}")
    OUT.write_text(json.dumps({"version": 1, "source": "tools/dorm_modules/electrify.py", "items": W.items,
                               "lights": W.lights}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    from collections import Counter
    c = Counter(i["model"] for i in W.items)
    tris = sum(MODELS[i["model"]]["triangles"] for i in W.items)
    print("ELECTRIFY", len(W.items), "моделей,", len(W.lights), "мигающих;", tris, "треугольников всего;", dict(c))


if __name__ == "__main__":
    main()
