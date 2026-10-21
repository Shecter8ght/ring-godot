"""NPC: брюки свободного кроя (под камуфляж, как у мародёра на референсе) — лекала и сшивание.

Четыре детали (перед и зад каждой штанины), шаговый, боковой и средние швы. Пояс пока закреплён
(дальше — отдельный пояс, шлёвки, ремень и накладные карманы).

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/pants.py [-- render]
→ _asset_src/npc_kit/pants/pants_sim.blend
"""
from __future__ import annotations

import bisect
import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import garment as gm  # noqa: E402
import kit_common as kc  # noqa: E402

OUT = kc.WORK / "pants"
H = 0.012  # шаг сетки ткани

LIN = 0.720          # шаговый шов: от паха до края берцев + 6 см на напуск
Z_HEM = 0.246        # низ штанины садится на край голенища (берцы до 0,235); внутрь — продлеваем после
TUCK = 0.035         # на сколько низ уходит в голенище
BOOT_TOP = 0.235
Z_WAIST = 1.035      # линия пояса на теле
T_BLEND = 0.10       # высота перехода «штанина → таз» по лекалу


def front_segs() -> list[gm.Seg]:
    """Перед левой штанины. Низ узкий (заправляется в берцы), с 6 см — обычная ширина."""
    L = LIN
    return [
        gm.Seg("hem", [(-0.083, 0.0), (0.083, 0.0)], smooth=False),
        gm.Seg("inseam", [(0.083, 0.0), (0.100, 0.06), (0.106, 0.14), (0.120, 0.36), (0.145, L)]),
        gm.Seg("cf", [(0.145, L), (0.112, L + 0.024), (0.093, L + 0.07), (0.086, L + 0.13), (0.078, L + 0.21)]),
        gm.Seg("waist", [(0.078, L + 0.21), (-0.140, L + 0.203)], smooth=False),
        gm.Seg("side", [(-0.140, L + 0.203), (-0.162, L + 0.11), (-0.150, L), (-0.120, 0.36), (-0.106, 0.14),
                        (-0.100, 0.06), (-0.083, 0.0)]),
    ]


def back_segs() -> list[gm.Seg]:
    L = LIN
    return [
        gm.Seg("hem", [(-0.102, 0.0), (0.102, 0.0)], smooth=False),
        gm.Seg("inseam", [(0.102, 0.0), (0.120, 0.06), (0.126, 0.14), (0.140, 0.36), (0.222, L)]),
        gm.Seg("cb", [(0.222, L), (0.165, L + 0.028), (0.118, L + 0.08), (0.098, L + 0.17), (0.080, L + 0.265)]),
        gm.Seg("waist", [(0.080, L + 0.265), (-0.152, L + 0.203)], smooth=False),
        gm.Seg("side", [(-0.152, L + 0.203), (-0.182, L + 0.11), (-0.170, L), (-0.140, 0.36), (-0.126, 0.14),
                        (-0.120, 0.06), (-0.102, 0.0)]),
    ]


WB_H = 0.042   # высота пояса


def waistband_segs(front_w: float, back_w: float) -> list[gm.Seg]:
    """Пояс левой половины: полоса от центра переда до центра спинки; низ пришивается к брюкам."""
    L = front_w + back_w
    return [
        gm.Seg("bottom_f", [(0.0, 0.0), (-front_w, 0.0)], smooth=False),
        gm.Seg("bottom_b", [(-front_w, 0.0), (-L, 0.0)], smooth=False),
        gm.Seg("cb_end", [(-L, 0.0), (-L, WB_H)], smooth=False),
        gm.Seg("top", [(-L, WB_H), (0.0, WB_H)], smooth=False),
        gm.Seg("cf_end", [(0.0, WB_H), (0.0, 0.0)], smooth=False),
    ]


def waistband_place(front_w: float, back_w: float, rings: gm.RingStack):
    L = front_w + back_w

    def place(x: float, y: float) -> Vector:
        u = -x
        s = u / L          # 0 — центр переда, 1 — центр спинки
        z = Z_WAIST + y * 0.95
        px, py = rings.arc(z, -90.0, 90.0, s)
        return Vector((px + (0.002 if s < 0.02 or s > 0.98 else 0.0), py, z))
    return place


class Span:
    """Ширина детали на высоте y: крайние x контура (для обёртки)."""

    def __init__(self, segs: list[gm.Seg]):
        poly = []
        for s in segs:
            poly.extend(s.dense()[:-1])
        self.poly = poly
        ys = [p[1] for p in poly]
        self.y0, self.y1 = min(ys), max(ys)
        self.table = []
        n = 400
        for k in range(n + 1):
            y = self.y0 + (self.y1 - self.y0) * k / n
            xs = []
            for i in range(len(poly)):
                a, b = poly[i], poly[(i + 1) % len(poly)]
                if (a[1] - y) * (b[1] - y) <= 0 and a[1] != b[1]:
                    t = (y - a[1]) / (b[1] - a[1])
                    xs.append(a[0] + (b[0] - a[0]) * t)
            self.table.append((y, min(xs) if xs else 0.0, max(xs) if xs else 0.0))
        self.keys = [t[0] for t in self.table]
        self.waist = next(sg for sg in segs if sg.name == "waist").dense()

    def at(self, y: float) -> tuple[float, float]:
        i = min(max(bisect.bisect_left(self.keys, y), 0), len(self.table) - 1)
        return self.table[i][1], self.table[i][2]

    def top(self, x: float) -> float:
        """Высота линии пояса над точкой; за краем пояса (клин шага) — высота ближайшего конца."""
        w = sorted(self.waist)
        if x <= w[0][0]:
            return w[0][1]
        if x >= w[-1][0]:
            return w[-1][1]
        for a, b in zip(w, w[1:]):
            if a[0] <= x <= b[0]:
                return a[1] + (b[1] - a[1]) * (x - a[0]) / max(b[0] - a[0], 1e-9)
        return w[-1][1]


def lerp_table(table: list[tuple[float, tuple]], z: float) -> tuple:
    if z <= table[0][0]:
        return table[0][1]
    for (za, va), (zb, vb) in zip(table, table[1:]):
        if za <= z <= zb:
            t = (z - za) / (zb - za)
            return tuple(a + (b - a) * t for a, b in zip(va, vb))
    return table[-1][1]


def smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def make_place(span: Span, back: bool, legs: list, rings: gm.RingStack, z_cr: float):
    """Обёртка левой детали: ниже промежности — эллипс вокруг ноги, выше — обхват таза по сечению тела."""
    sgn = 1.0 if back else -1.0

    def place(x: float, y: float) -> Vector:
        xs, xi = span.at(y)
        s = 0.0 if xi - xs < 1e-6 else (x - xs) / (xi - xs)
        s = max(0.0, min(1.0, s))
        if y <= LIN:
            z = Z_HEM + (y / LIN) * (z_cr - Z_HEM)
        else:
            top = span.top(x)
            z = z_cr + (y - LIN) / max(top - LIN, 1e-3) * (Z_WAIST - z_cr)
        cx, cy, hx, hy = lerp_table(legs, z)
        # Внутри голенища штанина прилегает (0,8 см), выше — свободная (3 см).
        m = 0.006 + 0.024 * smooth((z - (BOOT_TOP - 0.02)) / 0.12)
        a = min(hx + m, cx - 0.008)
        b = hy + m + 0.002
        phi = math.pi * s
        leg = Vector((cx + a * math.cos(phi), cy + sgn * b * math.sin(phi), z))
        w = smooth((y - LIN) / T_BLEND)
        if w <= 0:
            return leg
        px, py = rings.arc(z, 0.0, sgn * 90.0, s)
        pel = Vector((px + 0.002, py, z))
        return leg.lerp(pel, w)
    return place


def sections(report: dict) -> tuple[list, list]:
    m = report["measure"]
    legs = []
    for k in ["ankle", "calf", "knee", "thigh_mid", "thigh_top"]:
        s = m["left_leg"][k]
        legs.append((s["z"], (s["center"][0], s["center"][1], (s["x"][1] - s["x"][0]) / 2, (s["y"][1] - s["y"][0]) / 2)))
    legs.append((1.2, legs[-1][1]))
    pelvis = []
    for k in ["seat", "hip", "belly", "waist"]:
        s = m["torso"][k]
        pelvis.append((s["z"], (0.0, s["center"][1], (s["x"][1] - s["x"][0]) / 2, (s["y"][1] - s["y"][0]) / 2)))
    pelvis.sort()
    pelvis.insert(0, (0.6, pelvis[0][1]))
    return legs, pelvis


def crotch_z(body: bpy.types.Object) -> float:
    zs = [(body.matrix_world @ v.co).z for v in body.data.vertices if abs(v.co.x) < 0.012 and 0.7 < v.co.z < 1.0]
    return min(zs)


def tuck(obj: bpy.types.Object, body_col: bpy.types.Object) -> None:
    """Продлить низ штанин внутрь голенища: от края вниз до BOOT_TOP − TUCK, прижимая к ноге
    (7 мм от кожи — внутри берца с запасом)."""
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromObject(body_col, bpy.context.evaluated_depsgraph_get())
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    edges = [e for e in bm.edges if e.is_boundary and all(v.co.z < 0.5 for v in e.verts)]
    steps = 3
    for k in range(steps):
        res = bmesh.ops.extrude_edge_only(bm, edges=edges)
        new_v = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
        edges = [g for g in res["geom"] if isinstance(g, bmesh.types.BMEdge) and g.is_boundary]
        for v in new_v:
            t = (k + 1) / steps
            z = v.co.z + (BOOT_TOP - TUCK - v.co.z) * t
            p = Vector((v.co.x, v.co.y, z))
            hit = bvh.find_nearest(p)
            if hit[0] is not None:
                target = hit[0] + hit[1] * 0.007
                p = p.lerp(Vector((target.x, target.y, z)), t)
            v.co = p
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def main() -> None:
    args = kc.args_after_dashes()
    if "stack" in args:
        import faulthandler
        faulthandler.dump_traceback_later(40, repeat=True)
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / "body" / "body_M.blend"))
    report = json.loads((kc.WORK / "body" / "body_report.json").read_text(encoding="utf-8"))
    body = bpy.data.objects["NPC_Body"]
    z_cr = crotch_z(body) - 0.05
    legs, _ = sections(report)
    # Обхват таза по сечению тела: у пояса ткань почти прилегает, ниже, на ягодицах, — свободнее.
    rings = gm.RingStack(body, z_cr - 0.06, Z_WAIST + 0.03,
                         lambda z: 0.026 + (0.014 - 0.026) * smooth((z - 0.92) / 0.08),
                         lambda x, y: abs(x) < 0.30)
    fs, bs = front_segs(), back_segs()
    span_f, span_b = Span(fs), Span(bs)

    def waist_band(segs):
        """Пояс держится, как настоящий: обхват (≈0,92 м) меньше обхвата бёдер — ниже не сползти,
        но с учётом зазора столкновений (≈7 мм) не туже живота — иначе выдавит вверх к талии."""
        waist = next(s for s in segs if s.name == "waist").dense()
        return lambda x, y: max(0.0, 1.0 - gm._dist_to_poly((x, y), waist) / 0.03)

    def hem_band(x: float, y: float) -> float:
        """Низ штанины на резинке (заправлен в берцы): стягивается по голени."""
        return max(0.0, 1.0 - y / 0.035)
    front_l = gm.Piece("front_l", fs, make_place(span_f, False, legs, rings, z_cr), material="Pants_Fabric",
                       groups={"hem_band": hem_band}, uv_offset=(0.20, 0.0))
    back_l = gm.Piece("back_l", bs, make_place(span_b, True, legs, rings, z_cr), material="Pants_Fabric",
                      groups={"hem_band": hem_band}, uv_offset=(0.62, 0.0))
    fw = gm.poly_length(next(sg for sg in fs if sg.name == "waist").dense())
    bw = gm.poly_length(next(sg for sg in bs if sg.name == "waist").dense())
    band_l = gm.Piece("band_l", waistband_segs(fw, bw), waistband_place(fw, bw, rings), material="Pants_Fabric",
                      groups={"waistband": lambda x, y: 1.0}, uv_offset=(0.20, 1.20), h=0.010)
    front_r = gm.mirror_piece(front_l, "front_r", (1.04, 0.0))
    back_r = gm.mirror_piece(back_l, "back_r", (1.48, 0.0))
    band_r = gm.mirror_piece(band_l, "band_r", (0.20, 1.28))
    pieces = [front_l, back_l, front_r, back_r, band_l, band_r]
    seams = []
    for side in ("l", "r"):
        seams.append(gm.Seam(f"front_{side}.side", f"back_{side}.side", reverse=False))
        seams.append(gm.Seam(f"front_{side}.inseam", f"back_{side}.inseam", reverse=False))
        seams.append(gm.Seam(f"band_{side}.bottom_f", f"front_{side}.waist", reverse=False))
        seams.append(gm.Seam(f"band_{side}.bottom_b", f"back_{side}.waist", reverse=True))
    seams.append(gm.Seam("band_l.cb_end", "band_r.cb_end", reverse=False))
    seams.append(gm.Seam("band_l.cf_end", "band_r.cf_end", reverse=False))
    seams.append(gm.Seam("front_l.cf", "front_r.cf", reverse=False))
    seams.append(gm.Seam("back_l.cb", "back_r.cb", reverse=False))

    col = kc.collection("02_Pants")
    kc.clay("Pants_Fabric", (0.36, 0.38, 0.30), 0.8)
    obj, sew = gm.build_garment("Pants", pieces, seams, H, col)
    kc.log("PANTS_MESH", len(obj.data.vertices), "verts", len(obj.data.polygons), "tris", len(sew), "sew")
    OUT.mkdir(parents=True, exist_ok=True)
    if "place_only" in args:
        kc.save(OUT / "pants_placed.blend")
        cams = kc.view_cameras(1.8)
        for view in ["front", "side", "three_quarter"]:
            kc.render(cams[view], OUT / f"placed_{view}.png", (700, 900), 16)
        return

    sim_col = kc.collection("98_Sim_Colliders")
    # Внутренняя сторона бёдер у паха: бёдра почти касаются, ткань зажимало бы между ними — эту часть
    # препятствия убираем, шов у паха провиснет свободно.
    def crotch_gap(c: Vector) -> float:
        w = gm.smoothstep(1.0 - abs(c.x) / 0.07) * gm.smoothstep((c.z - 0.70) / 0.08) * gm.smoothstep((0.95 - c.z) / 0.05)
        # Край голенища берца — гладкий выступ на ноге: штанина садится на него и собирается напуском.
        rim = gm.smoothstep((c.z - (BOOT_TOP - 0.06)) / 0.03) * gm.smoothstep((BOOT_TOP + 0.004 - c.z) / 0.022)
        return 0.0015 - 0.012 * w + 0.021 * rim       # край голенища: boots.SHAFT_GAP + 1 мм
    body_col = gm.make_collider(body, "Body_Collider", sim_col, thickness=0.003, friction=30.0, offset_fn=crotch_gap)
    # Берцы: из boots.blend в сцену; препятствие — их копии (ткань над голенищем ложится напуском).
    boots_col = kc.collection("04_Boots")
    with bpy.data.libraries.load(str(kc.WORK / "boots" / "boots.blend")) as (src, dst):
        dst.objects = [n for n in src.objects if n in ("Boots_L", "Boots_R", "Boots_L_Outer", "Boots_R_Outer")]
    boot_cols = []
    for o in dst.objects:
        if o.name.endswith("_Outer") and "boot_collide" in args:
            sim_col.objects.link(o)
            # Стенка 5 мм внутрь со скруглённым краем: у открытой трубы на кромке нормали скачут.
            sol = o.modifiers.new("Wall", "SOLIDIFY")
            sol.thickness = 0.005
            sol.offset = -1.0
            sol.use_rim = True
            o.modifiers.new("Collision", "COLLISION")
            o.collision.thickness_outer = 0.003
            o.collision.thickness_inner = 0.004
            o.collision.cloth_friction = 20.0
            o.hide_render = True
            boot_cols.append(o)
        elif not o.name.endswith("_Outer"):
            boots_col.objects.link(o)
    for c in (body_col, *boot_cols):
        bad = gm.penetrations(obj, c, 0.004)
        zs = sorted(round((obj.matrix_world @ obj.data.vertices[i].co).z, 2) for i in bad)
        kc.log("PANTS_PENETRATION", c.name, len(bad), zs[:5], zs[-5:])
    if "nobody" in args:
        bpy.data.objects.remove(body_col)
    elif "nopush" not in args:
        # Обёртка грубая: у паха ткань уходит в тело — выводим перед вперёд, спинку назад до старта,
        # иначе симуляция взрывается.
        back_ids = set()
        for name in ("piece_back_l", "piece_back_r"):
            gi = obj.vertex_groups[name].index
            back_ids |= {v.index for v in obj.data.vertices if any(g.group == gi for g in v.groups)}
        n = gm.push_along(obj, body_col, lambda i: Vector((0, 1, 0)) if i in back_ids else Vector((0, -1, 0)), 0.012)
        bad = gm.penetrations(obj, body_col, 0.004)
        kc.log("PANTS_PUSHED", n, "left", len(bad), sorted({tuple(round(c, 2) for c in obj.data.vertices[i].co) for i in bad})[:12])
    t0 = time.time()
    gm.simulate(obj, gm.FABRICS["twill"], frames=int(next((a.split("=")[1] for a in args if a.startswith("frames=")), 80)), sew_frames=35, stiff_group="waistband", stiff_bending=60.0, 
                collide_collection=sim_col, self_collision="noself" not in args, debug=tuple(args), log=kc.log)
    gm.freeze(obj, sew, kc.log)
    gm.smooth_noise(obj, 2, 0.4)
    tuck(obj, bpy.data.objects["Body_Collider"])
    moved = gm.push_out(obj, bpy.data.objects["Body_Collider"], 0.002)
    kc.log("PANTS_SIM", round(time.time() - t0, 1), "s; pushed", moved)
    sim_col.hide_viewport = True
    sim_col.hide_render = True
    kc.save(OUT / "pants_sim.blend")
    if "render" in args:
        cams = kc.view_cameras(1.8)
        cams["legs"] = kc.camera("Cam_Legs", (1.4, -2.6, 0.55), (0, 0, 0.5), 70)
        for view in ["front", "back", "side", "legs"]:
            kc.render(cams[view], OUT / f"pants_{view}.png", (900, 1200), 48)


if __name__ == "__main__":
    main()
