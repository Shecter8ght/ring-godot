"""Подсумки — игровая версия: LOD0–2 и карты 512 с принятого исходника v02 (владелец 2026-10-22: «с ретопологии всего»,
подсумок ~1 тыс. треугольников, три LOD 100/40/12 %; v02 принят 2026-10-23).

Корпус, ряды MOLLE и поле «петли» — упрощение гладкой формы (ключ «Без складок»): складки, строчки, кнопки, закрепки,
ворс — в картах. Язычок и клапан большого — лента заново по их путям из исходника (свойство «lp», pouches.py) с теми
же ключами формы («Магазин 45» / «ПМ» / «Открыт»): сетку с ключами упростить нельзя. Сечения ленты гуще на изгибах
(через донце магазина), хвост — в тех же отступах от конца во всех ключах (слой «крючка» на месте). Развёртка ленты —
по её длине и обхвату, двумя кусками; у LOD1–2 те же куски с той же раскладкой — карта одна на все LOD.
Запекание — корпус и лента отдельно (иначе луч с корпуса попадает в язычок, и под открытым язычком был бы его же
рисунок), затем общий атлас.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/game_pouches.py -- [deliver=<папка>]
→ _asset_src/npc_kit/game/pouches_game.blend, карты game/maps/pouch_{rifle,pistol,big}_{color,normal,orm}.png
"""
from __future__ import annotations

import json
import math
import sys
from collections.abc import Callable
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armor_kit as ak  # noqa: E402
import game_gear as gg  # noqa: E402
import game_lp as gl  # noqa: E402
import kit_common as kc  # noqa: E402
import pouches as pu  # noqa: E402

SRC = kc.WORK / "pouches" / "pouches_tex.blend"
OUT = gl.OUT / "pouches_game.blend"
MAPS = gl.MAPS
SIZE = 512
RAY = 0.006
# подсумок: неподвижные детали (исходник → треугольников LOD0), подвижная деталь; кнопки и нитки — только в карты
KINDS = {
    "Rifle": ({"Body": 500, "Molle": 120, "Velcro": 30}, "Tab"),
    "Pistol": ({"Body": 330, "Molle": 70, "Velcro": 24}, "Tab"),
    "Big": ({"Body": 650, "Molle": 180, "Velcro": 30}, "Flap"),
}
BAKE_ONLY = ("Snaps", "Thread")
STATIONS = (24, 12, 6)                 # сечений ленты до хвоста на LOD0/1/2 (кратны 4: два куска развёртки у всех)
STATIC_RATIO = {1: 0.30, 2: 0.10}      # доля треугольников корпуса на LOD1, LOD2 (у ленты — свои сечения)
TURN_W = 0.06                          # «вес» поворота ленты, м на радиан: на изгибах сечения гуще
LIFT = 0.0006                          # лента над путём исходника: хорды между сечениями не срезают угол донца
TAB_T, FLAP_T = 0.0028, 0.004          # толщина язычка (двойная стропа) и клапана
HOOK_DROP = -0.0013                    # слой «крючка» под концом язычка (низ ленты там ниже)
# ключ формы → магазин в подсумке (для проверки ленты против магазина)
MAG_OF = {"Rifle": {"Basis": "Mag_VERAS54_30", "Магазин 45": "Mag_VERAS54_45", "Открыт": None},
          "Pistol": {"Basis": "Mag_Glock_17", "ПМ": "Mag_PM_8", "Открыт": None},
          "Big": {"Basis": "Mag_VERAS54_Drum60", "Открыт": None}}
ISL_CAP0, ISL_CAP1, ISL_LOOP = 2, 3, 4  # куски развёртки ленты: 0, 1 — лента, далее торцы и петля


# ---------- лента низкого разрешения ----------

class Strip:
    """Вершины, грани, развёртка по длине и обхвату и номер куска развёртки у каждой грани."""

    def __init__(self):
        self.verts: list[Vector] = []
        self.faces: list[list[int]] = []
        self.uvs: list[list[tuple[float, float]]] = []
        self.isl: list[int] = []

    def v(self, p: Vector) -> int:
        self.verts.append(p.copy())
        return len(self.verts) - 1

    def f(self, idx: list[int], uv: list[tuple[float, float]], isl: int) -> None:
        self.faces.append(idx)
        self.uvs.append(uv)
        self.isl.append(isl)


def section(width: float, thick: float, rect: bool) -> tuple[list[tuple[float, float, float]], float]:
    """Сечение ленты по кругу: (x, y, развёртка по обхвату) и обхват. Шестиугольник — прямоугольник со скошенными
    боками; у LOD2 — прямоугольник (те же точки развёртки без середин боков)."""
    hw, t = width / 2, thick
    pts = [(hw - t / 2, t), (hw, t / 2), (hw - t / 2, 0.0), (-(hw - t / 2), 0.0), (-hw, t / 2), (-(hw - t / 2), t)]
    acc = [0.0]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        acc.append(acc[-1] + math.dist(a, b))
    out = [(x, y, s) for (x, y), s in zip(pts, acc)]
    if rect:
        out = [out[i] for i in (0, 2, 3, 5)]
    return out, acc[-1]


def weight_stations(pts: list[Vector], cum: list[float], u_end: float, n: int, scale: float = 1.0) -> list[float]:
    """n + 1 сечений на [0, u_end] равным «весом»: длина + TURN_W × поворот оси (на изгибах гуще). pts, cum — ось
    ленты и длина по ней; scale — u ленты в длину оси (у клапана u условная)."""
    w = [0.0]
    for i in range(1, len(pts)):
        turn = 0.0
        if 1 <= i < len(pts) - 1:
            a, b = (pts[i] - pts[i - 1]).normalized(), (pts[i + 1] - pts[i]).normalized()
            turn = math.acos(max(-1.0, min(1.0, a.dot(b))))
        w.append(w[-1] + (cum[i] - cum[i - 1]) + TURN_W * turn)
    end = u_end * scale
    w_end = np.interp(end, cum, w)
    out = [float(np.interp(w_end * k / n, w, cum)) / scale for k in range(n + 1)]
    out[-1] = u_end
    return out


def ribbon(m: Strip, point: Callable[[float, float, float], Vector], us: list[float], param_us: list[float],
           width_at: Callable[[float], float], bottom_at: Callable[[float], float], thick: float, rect: bool,
           split: int, nominal_w: float) -> None:
    """Лента по рамке point(u, x, y): сечения в us, развёртка — по param_us (длина у основы) и обхвату; грани до
    сечения split — кусок 0, дальше — кусок 1; торцы — свои куски."""
    sec, per = section(nominal_w, thick, rect)
    rows = []
    for u in us:
        sx = width_at(u) / nominal_w
        b = bottom_at(u)
        rows.append([m.v(point(u, x * sx, b + y / thick * (thick - b))) for x, y, _ in sec])
    seg0 = {0: param_us[0], 1: param_us[split]}
    n = len(sec)
    for i in range(len(us) - 1):
        isl = 0 if i < split else 1
        u0, u1 = param_us[i] - seg0[isl], param_us[i + 1] - seg0[isl]
        for j in range(n):
            j1 = (j + 1) % n
            a0, a1 = sec[j][2], (sec[j1][2] if j1 else per)
            m.f([rows[i][j], rows[i][j1], rows[i + 1][j1], rows[i + 1][j]], [(u0, a0), (u0, a1), (u1, a1), (u1, a0)], isl)
    for row, isl, rev in ((rows[0], ISL_CAP0, True), (rows[-1], ISL_CAP1, False)):
        idx = row[::-1] if rev else row
        uv = [(sec[k][0] + nominal_w, sec[k][1]) for k in (range(n - 1, -1, -1) if rev else range(n))]
        m.f(list(idx), uv, isl)


def tube(m: Strip, pts: list[Vector], r: float, sides: int) -> None:
    """Шнур петли-тяги: кольца без торцов (концы зашиты в ленту); развёртка — длина × обхват."""
    t0 = (pts[1] - pts[0]).normalized()
    nrm = t0.orthogonal().normalized()
    rows, acc = [], [0.0]
    for i, p in enumerate(pts):
        if i:
            acc.append(acc[-1] + (p - pts[i - 1]).length)
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        nrm = (nrm - t * nrm.dot(t)).normalized()
        b = t.cross(nrm)
        rows.append([m.v(p + (nrm * math.cos(2 * math.pi * k / sides) + b * math.sin(2 * math.pi * k / sides)) * r)
                     for k in range(sides)])
    per = 2 * math.pi * r
    for i in range(len(rows) - 1):
        for k in range(sides):
            k1 = (k + 1) % sides
            v0, v1 = per * k / sides, per * (k + 1) / sides
            m.f([rows[i][k], rows[i][k1], rows[i + 1][k1], rows[i + 1][k]],
                [(acc[i], v0), (acc[i], v1), (acc[i + 1], v1), (acc[i + 1], v0)], ISL_LOOP)


def tab_rib(path: list[Vector]) -> ak.RibbonFrame:
    """Ось язычка — как у исходника (pouches.tab_mesh): те же точки и сглаженные нормали."""
    pts = pu.resample(path, pu.TAB_N)
    nrm = pu.path_normals(pts)
    for _ in range(3):
        nrm = [nrm[0]] + [(nrm[i - 1] + nrm[i] * 2 + nrm[i + 1]).normalized() for i in range(1, len(nrm) - 1)] + [nrm[-1]]
    return ak.RibbonFrame(pts, nrm)


def flap_rib(path: list[Vector]) -> ak.RibbonFrame:
    """Ось клапана — как у исходника (pouches.build_big_pouch.flap)."""
    p2 = pu.resample(path, 60)
    nrm = pu.path_normals(p2)
    for _ in range(4):
        nrm = [nrm[0]] + [(nrm[i - 1] + nrm[i] * 2 + nrm[i + 1]).normalized() for i in range(1, len(nrm) - 1)] + [nrm[-1]]
    return ak.RibbonFrame(p2, nrm)


def tab_lp(data: dict, lod: int) -> dict[str, Strip]:
    """Язычок: основа и ключи формы одной топологии. Хвост (слой «крючка») — в одних отступах от конца."""
    width, hook = data["width"], data["hook_len"]
    n = STATIONS[lod]
    out = {}
    # сечения — по изгибам основы; у ключей — в тех же долях длины (развёртка одна, рисунок не съезжает)
    base = tab_rib([Vector(p) for p in data["paths"]["Basis"]])
    uA0 = base.length - hook - 0.002
    frac = [u / uA0 for u in weight_stations(base.pts, base.cum, uA0, n)]
    for key, path in data["paths"].items():
        rib = tab_rib([Vector(p) for p in path])
        L = rib.length
        uA = L - hook - 0.002
        tail = ([L - hook + 0.001, L - hook / 2, L], [L - hook + 0.001, L], [L])[lod]
        us = [f * uA for f in frac] + tail
        m = Strip()

        def bottom(u: float, L=L) -> float:
            return HOOK_DROP * min(1.0, max(0.0, (u - (L - hook - 0.002)) / 0.003))
        ribbon(m, lambda u, x, y, rib=rib: rib.point(u, x, y + LIFT), us, us, lambda u: width, bottom, TAB_T, lod == 2,
               n // 2, width)
        if lod < 2:
            p, tan, nn = rib._at(L)
            side = nn.cross(tan).normalized()
            loop = []
            for k in range(7):
                a = math.pi * k / 6
                ext = -0.007 + 0.021 * math.sin(a)
                loop.append(p + tan * ext + nn * (0.0014 + 0.0045 * max(0.0, ext) / 0.014) + side * (0.0075 * math.cos(a)))
            tube(m, loop, 0.0015, 4)
        out[key] = m
    # развёртка у всех ключей — от основы
    first = out["Basis"]
    for m in out.values():
        m.uvs, m.isl = first.uvs, first.isl
    return out


def flap_lp(data: dict, lod: int) -> dict[str, Strip]:
    """Клапан большого подсумка: лента по профилю барабана, условная длина L0 (как у исходника), ширина сужается
    к концу; петля-тяга на конце."""
    W, L0 = data["W"], data["L0"]
    n = STATIONS[lod]
    out = {}
    base = flap_rib([Vector(p) for p in data["paths"]["Basis"]])
    us = weight_stations(base.pts, base.cum, L0, n, scale=base.length / L0)   # у ключей — те же доли L0
    for key, path in data["paths"].items():
        rib = flap_rib([Vector(p) for p in path])
        k = rib.length / L0
        m = Strip()
        ribbon(m, lambda u, x, y, rib=rib, k=k: rib.point(u * k, x, y), us, us,
               lambda u: (W - 0.008) - 0.016 * u / L0, lambda u: 0.0, FLAP_T, lod == 2, n // 2, W - 0.008)
        if lod < 2:
            p, tan, nn = rib._at(rib.length)
            side = nn.cross(tan).normalized()
            loop = []
            for j in range(7):
                a = math.pi * j / 6
                loop.append(p + tan * (-0.008 + 0.026 * math.sin(a)) + nn * (0.004 + 0.005 * math.sin(a) ** 2)
                            + side * (0.012 * math.cos(a)))
            tube(m, loop, 0.0022, 4)
        out[key] = m
    first = out["Basis"]
    for m in out.values():
        m.uvs, m.isl = first.uvs, first.isl
    return out


def strip_object(name: str, strips: dict[str, Strip], col: bpy.types.Collection, matrix) -> bpy.types.Object:
    base = strips["Basis"]
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in base.verts], [], base.faces)
    me.update()
    for layer in ("UV", "Param"):
        uvl = me.uv_layers.new(name=layer)
        for poly, uv in zip(me.polygons, base.uvs):
            for li, t in zip(poly.loop_indices, uv):
                uvl.data[li].uv = t
    me.uv_layers.active = me.uv_layers["UV"]
    att = me.attributes.new("isl", "INT", "FACE")
    att.data.foreach_set("value", base.isl)
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    o.matrix_world = matrix
    o.shape_key_add(name="Basis", from_mix=False)
    for key, m in strips.items():
        if key == "Basis":
            continue
        assert len(m.verts) == len(base.verts), f"{name}: ключ {key} — другая топология"
        kb = o.shape_key_add(name=key, from_mix=False)
        kb.value = 0.0
        for i, p in enumerate(m.verts):
            kb.data[i].co = p
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    gg.smooth(o)
    return o


# ---------- корпус ----------

def static_part(kind: str, budgets: dict[str, int], col: bpy.types.Collection) -> bpy.types.Object:
    """Корпус, MOLLE, поле «петли» — гладкая форма (без складок), упрощение до доли бюджета, одна сетка."""
    made = []
    for part, budget in budgets.items():
        src = bpy.data.objects[f"Pouch_{kind}_{part}"]
        o = gl.dup(src, f"W_{kind}_{part}", col, keep_mods=True)
        keys = o.data.shape_keys
        if keys and pu.SMOOTH_KEY in keys.key_blocks:
            smooth_co = [kb.co.copy() for kb in keys.key_blocks[pu.SMOOTH_KEY].data]
            o.shape_key_clear()
            for v, c in zip(o.data.vertices, smooth_co):
                v.co = c
        elif keys:
            o.shape_key_clear()
        gl.apply_mods(o)
        gl.decimate_to(o, budget)
        made.append(o)
    kc.make_active(made[0])
    for o in made[1:]:
        o.select_set(True)
    bpy.ops.object.join()
    s = made[0]
    s.name = s.data.name = f"S_{kind}"
    gg.smooth(s)
    att = s.data.attributes.new("isl", "INT", "FACE")
    att.data.foreach_set("value", [-1] * len(s.data.polygons))
    gl.unwrap(s, SIZE)
    if "Param" not in s.data.uv_layers:
        s.data.uv_layers.new(name="Param")
    s.data.uv_layers.active = s.data.uv_layers["UV"]
    return s


def join_into(active: bpy.types.Object, others: list[bpy.types.Object], name: str) -> bpy.types.Object:
    kc.make_active(active)
    for o in others:
        o.select_set(True)
    bpy.ops.object.join()
    active.name = active.data.name = name
    return active


def repack(o: bpy.types.Object) -> None:
    kc.make_active(o)
    o.data.uv_layers.active = o.data.uv_layers["UV"]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=6.0 / SIZE)
    bpy.ops.object.mode_set(mode="OBJECT")


def island_maps(o: bpy.types.Object) -> dict[int, np.ndarray]:
    """Для каждого куска ленты — преобразование развёртки «по длине и обхвату» → раскладка атласа (МНК, 3×2)."""
    me = o.data
    isl = np.empty(len(me.polygons), np.int64)
    me.attributes["isl"].data.foreach_get("value", isl)
    par, uv = me.uv_layers["Param"].data, me.uv_layers["UV"].data
    rows: dict[int, tuple[list, list]] = {}
    for poly in me.polygons:
        k = int(isl[poly.index])
        if k < 0:
            continue
        a, b = rows.setdefault(k, ([], []))
        for li in poly.loop_indices:
            a.append((par[li].uv.x, par[li].uv.y, 1.0))
            b.append((uv[li].uv.x, uv[li].uv.y))
    return {k: np.linalg.lstsq(np.array(a), np.array(b), rcond=None)[0] for k, (a, b) in rows.items()}


def apply_island_maps(o: bpy.types.Object, maps: dict[int, np.ndarray]) -> None:
    me = o.data
    isl = np.empty(len(me.polygons), np.int64)
    me.attributes["isl"].data.foreach_get("value", isl)
    par, uv = me.uv_layers["Param"].data, me.uv_layers["UV"].data
    for poly in me.polygons:
        A = maps[int(isl[poly.index])]
        for li in poly.loop_indices:
            q = np.array((par[li].uv.x, par[li].uv.y, 1.0)) @ A
            uv[li].uv = (float(q[0]), float(q[1]))


def copy_faces(o: bpy.types.Object, name: str, keep: Callable[[int], bool], col: bpy.types.Collection) -> bpy.types.Object:
    """Копия сетки только с гранями keep(isl), без ключей формы."""
    c = gl.dup(o, name, col)
    if c.data.shape_keys:
        c.shape_key_clear()
    bm = bmesh.new()
    bm.from_mesh(c.data)
    lay = bm.faces.layers.int.get("isl")
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep(f[lay])], context="FACES")
    bm.to_mesh(c.data)
    bm.free()
    return c


# ---------- запекание и атлас ----------

def raster(o: bpy.types.Object, size: int, grow: int = 0) -> np.ndarray:
    """Где в атласе лежат грани объекта (маска size × size, строки снизу вверх — как пиксели Blender)."""
    me = o.data
    me.calc_loop_triangles()
    uv = me.uv_layers["UV"].data
    mask = np.zeros((size, size), bool)
    for tri in me.loop_triangles:
        p = np.array([uv[li].uv[:] for li in tri.loops]) * size - 0.5
        x0, y0 = np.floor(p.min(0)).astype(int) - 1
        x1, y1 = np.ceil(p.max(0)).astype(int) + 1
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        (ax, ay), (bx, by), (cx, cy) = p
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12:
            continue
        l1 = ((by - cy) * (xx - cx) + (cx - bx) * (yy - cy)) / d
        l2 = ((cy - ay) * (xx - cx) + (ax - cx) * (yy - cy)) / d
        l3 = 1 - l1 - l2
        e = -0.6 / max(abs(d) ** 0.5, 1.0)
        mask[y0:y1 + 1, x0:x1 + 1] |= (l1 >= e) & (l2 >= e) & (l3 >= e)
    for _ in range(grow):
        g = mask.copy()
        g[1:] |= mask[:-1]
        g[:-1] |= mask[1:]
        g[:, 1:] |= mask[:, :-1]
        g[:, :-1] |= mask[:, 1:]
        mask = g
    return mask


def atlas(kind: str, s: bpy.types.Object, t: bpy.types.Object) -> dict[str, bpy.types.Image]:
    """Карты корпуса и ленты в одну: лента — по своим граням (с полями), остальное — корпус."""
    ms = raster(s, SIZE)
    mt = raster(t, SIZE, grow=3) & ~ms
    out = {}
    name = f"pouch_{kind.lower()}"
    for ch in ("color", "normal", "orm"):
        a, b = bpy.data.images[f"{s.name}_{ch}"], bpy.data.images[f"{t.name}_{ch}"]
        pa = np.empty(SIZE * SIZE * 4, np.float32)
        pb = np.empty(SIZE * SIZE * 4, np.float32)
        a.pixels.foreach_get(pa)
        b.pixels.foreach_get(pb)
        pa, pb = pa.reshape(SIZE, SIZE, 4), pb.reshape(SIZE, SIZE, 4)
        pa[mt] = pb[mt]
        im = bpy.data.images.get(f"{name}_{ch}") or bpy.data.images.new(f"{name}_{ch}", SIZE, SIZE, alpha=False)
        im.colorspace_settings.name = "sRGB" if ch == "color" else "Non-Color"
        im.pixels.foreach_set(pa.ravel())
        im.filepath_raw = str(MAPS / f"{name}_{ch}.png")
        im.file_format = "PNG"
        im.save()
        out[ch] = im
        for tmp in (s.name, t.name):
            f = MAPS / f"{tmp.lower()}_{ch}.png"
            if f.exists():
                f.unlink()
    kc.log(f"  атлас {name}: корпус {ms.mean() * 100:.0f} %, лента {mt.mean() * 100:.0f} % площади карты")
    return out


def game_material(kind: str, maps: dict[str, bpy.types.Image]) -> bpy.types.Material:
    m = bpy.data.materials.get(f"GAME_Pouch_{kind}") or bpy.data.materials.new(f"GAME_Pouch_{kind}")
    m.use_nodes = True
    gl.bake_target(m, maps["color"])
    gl.preview_material(m, maps)
    return m


# ---------- проверка ----------

def tris(o: bpy.types.Object) -> int:
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def check_mags(kind: str, g: bpy.types.Object) -> list[str]:
    """Лента против магазина в каждом ключе формы (пересечения граней)."""
    msg = []
    keys = g.data.shape_keys.key_blocks
    for key, mag in MAG_OF[kind].items():
        for kb in keys[1:]:
            kb.value = 1.0 if kb.name == key else 0.0
        bpy.context.view_layer.update()
        if mag is None:
            continue
        dg = bpy.context.evaluated_depsgraph_get()
        a = BVHTree.FromObject(g, dg)
        b = BVHTree.FromObject(bpy.data.objects[mag], dg)
        msg.append(f"{key}: {len(a.overlap(b))} пар граней с {mag}")
    for kb in keys[1:]:
        kb.value = 0.0
    return msg


# ---------- сборка ----------

def build() -> None:
    import ucup  # noqa: F401  (стеки UCUPaint исходника)
    bpy.ops.wm.open_mainfile(filepath=str(SRC))
    cols = {lvl: kc.collection(f"GAME_LOD{lvl}") for lvl in range(3)}
    work = kc.collection("GAME_Work")
    items, pairs, game = [], {}, {}
    for kind, (budgets, moving) in KINDS.items():
        src_moving = bpy.data.objects[f"Pouch_{kind}_{moving}"]
        data = json.loads(src_moving[pu.LP_PROP])
        lp = tab_lp if moving == "Tab" else flap_lp
        s = static_part(kind, budgets, work)
        t0 = strip_object(f"T_{kind}_0", lp(data, 0), work, src_moving.matrix_world.copy())
        g0 = join_into(t0, [s], f"G_Pouch_{kind}")
        repack(g0)
        maps = island_maps(g0)
        # для запекания — корпус и лента порознь, без ключей
        sb = copy_faces(g0, f"B_Pouch_{kind}_S", lambda k: k < 0, work)
        tb = copy_faces(g0, f"B_Pouch_{kind}_T", lambda k: k >= 0, work)
        srcs = tuple(f"Pouch_{kind}_{p}" for p in (*budgets, *BAKE_ONLY))
        items += [(sb, srcs, SIZE, RAY, sb.name.lower()), (tb, (src_moving.name,), SIZE, RAY, tb.name.lower())]
        pairs[kind] = (sb, tb)
        # LOD1–2: корпус — упрощение корпуса LOD0 (та же развёртка), лента — заново, развёртка — по кускам LOD0
        lods = {0: g0}
        for lvl in (1, 2):
            sc = copy_faces(g0, f"S_{kind}_{lvl}", lambda k: k < 0, work)
            gl.decimate_to(sc, max(12, int(tris(sc) * STATIC_RATIO[lvl])))
            tl = strip_object(f"T_{kind}_{lvl}", lp(data, lvl), work, src_moving.matrix_world.copy())
            apply_island_maps(tl, maps)
            lods[lvl] = join_into(tl, [sc], f"G_Pouch_{kind}_LOD{lvl}")
        for lvl, o in lods.items():
            for c in list(o.users_collection):
                c.objects.unlink(o)
            cols[lvl].objects.link(o)
        game[kind] = lods
    gl.bake_set(items, MAPS, ao_distance=0.03)
    for kind, (sb, tb) in pairs.items():
        mat = game_material(kind, atlas(kind, sb, tb))
        for o in game[kind].values():
            o.data.materials.clear()
            o.data.materials.append(mat)
            if "Param" in o.data.uv_layers:
                o.data.uv_layers.remove(o.data.uv_layers["Param"])
    for o in list(work.objects):
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(work)
    for kind, lods in game.items():
        kc.log(f"  {kind}: LOD0 {tris(lods[0])}, LOD1 {tris(lods[1])}, LOD2 {tris(lods[2])} треугольников; ключи "
               + ", ".join(kb.name for kb in lods[0].data.shape_keys.key_blocks[1:]))
        kc.log("    лента и магазин: " + "; ".join(check_mags(kind, lods[0])))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    kc.save(OUT)


README = (
    "Подсумки — ИГРОВАЯ ВЕРСИЯ (ретопология), на просмотр. Решения владельца 2026-10-22: подсумок ~1 тыс. треугольников,\n"
    "карта 512, три LOD (100 / 40 / 12 %). Исходник — принятые Подсумки_v02_текстуры.blend.\n"
    "GAME_LOD0 — вверху, LOD1 и LOD2 — ниже; слева направо: автоматный, пистолетный, большой. Магазины — игровые модели\n"
    "(в игре отдельные), в коллекции «Магазины».\n"
    "Складки, строчки, кнопки, закрепки MOLLE, ворс липучки и слой «крючка» — в картах (цвет, нормали, ORM: R — AO,\n"
    "G — шероховатость, B — металл). Язычок и клапан — с ключами формы, как у исходника: выделить G_Pouch_* →\n"
    "Object Data → Shape Keys («Магазин 45» / «ПМ» / «Открыт»). Смотреть в Rendered (Cycles); сетку — Overlays → Wireframe.\n"
    "Скрипт: tools/npc_kit/game_pouches.py.\n")


def deliver(folder: Path) -> None:
    from mathutils import Quaternion
    bpy.ops.wm.open_mainfile(filepath=str(OUT))
    keep = {"GAME_LOD0", "GAME_LOD1", "GAME_LOD2", "99_Studio"}
    mags = kc.collection("Магазины")
    for kind, per in MAG_OF.items():
        for key, name in per.items():
            if name:
                o = bpy.data.objects[name]
                for c in list(o.users_collection):
                    c.objects.unlink(o)
                mags.objects.link(o)
                o.hide_render = o.hide_viewport = key != "Basis"
    keep.add(mags.name)
    for o in list(bpy.data.objects):
        if o.type in ("MESH", "ARMATURE", "EMPTY") and not any(c.name in keep for c in o.users_collection):
            bpy.data.objects.remove(o)
    for c in list(bpy.data.collections):
        if c.name not in keep and not c.objects and not c.children:
            bpy.data.collections.remove(c)
    for lvl in (1, 2):
        for o in bpy.data.collections[f"GAME_LOD{lvl}"].objects:
            o.location.z -= 0.25 * lvl
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    kc.studio()
    kc.gpu_cycles(64)
    scene = bpy.context.scene
    scene.cycles.preview_samples = 24
    scene.cycles.use_preview_denoising = True
    scene.camera = kc.camera("Camera_Front", (0.55, 1.25, 0.05), (0.21, 0.0, -0.16), 50)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                sp = area.spaces.active
                sp.shading.type = "RENDERED"
                sp.overlay.show_floor = False
                r3 = sp.region_3d
                r3.view_location = (0.21, 0.0, -0.16)
                r3.view_distance = 1.1
                r3.view_rotation = Quaternion((0.17, 0.12, 0.56, 0.80))
    text = bpy.data.texts.new("00_ПРОЧТИ")
    text.use_fake_user = True
    text.write(README)
    bpy.ops.file.pack_all()
    folder.mkdir(parents=True, exist_ok=True)
    kc.save(folder / "Подсумки_игровые.blend")
    kc.log("DELIVERED", folder / "Подсумки_игровые.blend")


def shots() -> None:
    """Свои проверочные кадры: каждый подсумок LOD0 закрытым (с магазином) и открытым; исходник скрыт."""
    bpy.ops.wm.open_mainfile(filepath=str(OUT))
    kc.studio()
    prev = kc.WORK / "previews"
    lod0 = set(bpy.data.collections["GAME_LOD0"].objects)
    mags = {m for per in MAG_OF.values() for m in per.values() if m}
    for o in bpy.data.objects:
        if o.type == "MESH" and o not in lod0 and o.name not in mags:
            o.hide_render = True
    paths = []
    for kind, x0 in (("Rifle", 0.0), ("Pistol", 0.20), ("Big", 0.42)):
        g = bpy.data.objects[f"G_Pouch_{kind}"]
        for state in ("Basis", "Открыт"):
            for kb in g.data.shape_keys.key_blocks[1:]:
                kb.value = 1.0 if kb.name == state else 0.0
            for name in mags:
                bpy.data.objects[name].hide_render = not (state == "Basis" and name == MAG_OF[kind]["Basis"])
            z = 0.10 if kind != "Pistol" else 0.07
            cam = kc.camera("Cam_game", (x0 + 0.20, 0.32, z + 0.12), (x0, 0.0, z), 60)
            path = prev / f"pouch_game_{kind.lower()}_{'closed' if state == 'Basis' else 'open'}.png"
            kc.render(cam, path, (700, 700), 64)
            paths.append(path)
        for kb in g.data.shape_keys.key_blocks[1:]:
            kb.value = 0.0


def main() -> None:
    args = kc.args_after_dashes()
    if "deliver_only" not in args and "shots_only" not in args:
        build()
    if "shots" in args or "shots_only" in args:
        shots()
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        deliver(Path(dest))


if __name__ == "__main__":
    main()
