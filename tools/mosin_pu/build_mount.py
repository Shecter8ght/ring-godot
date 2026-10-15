"""Крепление прицела ПУ (обр. 1942): основание на левом боку коробки + съёмный кронштейн с кольцами.

Решение владельца 2026-10-15: основание входит в модель крепления, винтовка без пластины.
Форма: кронштейн — снимок eBay (refs/web/mount/web_00.jpg), основание — web_01.jpg, посадка на винтовке —
fotoace.ru (refs/web/pu_views2/web_03.jpg) и RIA 5039/265 (обе стороны). Размеры по подложке правой стороны:
стойка x −78,6…−29,7, окно Ø18,2 с центром (−53,6; 22,5), заднее кольцо x −89,7…−67,7, переднее −47,5…−29,4,
кольца Ø29,7 под трубу Ø26,4, ось прицела z = 51,2. Боковой вынос оси прицела влево y = +8 — оценка по фото.
Основание: x −122…−6 (по левому снимку, оценка), внутренняя грань — по кольцу коробки Ø31,3.

Оси — как у винтовки (начало = начало винтовки: на винтовке ставится без сдвига). Пустышка Mount_ScopeSocket —
точка заднего торца окуляра прицела на его оси (начало модели прицела).
Запуск: blender --background --factory-startup --python tools/mosin_pu/build_mount.py
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mosin_lib as L  # noqa: E402

OUT = os.path.join(L.ASSET_DIR, "models", "03_Крепление", "Mosin_PU_Mount_v01.blend")
R_RCV = 15.65
YS, ZS = 8.0, 51.2                 # ось прицела
R_TUBE, R_RING = 13.2, 14.85
SCOPE_REAR_X = -187.5
RINGS = (("Rear", -89.7, -67.7, 2), ("Front", -47.5, -29.4, 1))
WEB_X = (-78.6, -29.7)
WEB_Y = (13.5, 26.5)
BASE_X = (-122.0, -6.0)
BASE_Z = (-3.0, 11.5)
BASE_OUT = 22.5


def _box(name, xr, yr, zr, mat=None, col=None):
    v = [(x, y, z) for x in xr for y in yr for z in zr]
    v = [tuple(c * L.MM for c in p) for p in v]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    ob = L.mesh_object(name, v, faces, mat, col, None if mat is None else 30)
    L.fix_normals(ob)
    return ob


def base_profile(out_y=BASE_OUT, z0=BASE_Z[0], z1=BASE_Z[1], bev=1.4):
    """Сечение основания (y, z): внутренняя грань по цилиндру коробки, наружная плоская, кромки — ласточкин хвост."""
    pts = []
    n = 16
    for i in range(n + 1):
        z = z1 - (z1 - z0) * i / n
        pts.append((math.sqrt(max(R_RCV ** 2 - z * z, 0.0)) - 0.05, z))
    pts += [(out_y - bev, z0), (out_y, z0 + bev), (out_y, z1 - bev), (out_y - bev, z1)]
    return pts


def build_base(col):
    parts = []
    prof = base_profile()
    base = L.extrude_profile("Mount_Base", prof, BASE_X[0], BASE_X[1], "Steel_Blued", col, plane="YZ")
    L.bevel_mod(base, 0.4, 2)
    parts.append(base)
    # передний упор: утолщение со скруглённым торцом
    stop_prof = base_profile(out_y=BASE_OUT + 3.6, bev=1.8)
    stop = L.extrude_profile("Mount_Base_FrontStop", L.fillet(stop_prof, 0.0, 2, closed=True), -14.0, -4.0,
                             "Steel_Blued", col, plane="YZ")
    L.bevel_mod(stop, 2.2, 4)
    parts.append(stop)
    # задняя колодка стопорного винта
    blk_prof = base_profile(out_y=BASE_OUT + 6.0, z0=-4.0, z1=12.5, bev=1.5)
    blk = L.extrude_profile("Mount_Base_RearBlock", blk_prof, BASE_X[0] - 2.0, BASE_X[0] + 11.0, "Steel_Blued",
                            col, plane="YZ")
    L.bevel_mod(blk, 1.0, 3)
    parts.append(blk)
    # стопорный винт: накатанная головка сзади, ось вдоль X
    screw_c = Vector((0, BASE_OUT + 2.4, 4.2))
    head = L.lathe("Mount_LockScrew", L.fillet([(BASE_X[0] - 12.0, 0), (BASE_X[0] - 12.0, 6.4),
                                                (BASE_X[0] - 2.4, 6.4), (BASE_X[0] - 2.4, 3.0),
                                                (BASE_X[0] - 1.9, 3.0), (BASE_X[0] - 1.9, 0)],
                                               [0, 1.0, 0.8, 0.3, 0, 0], 4), 72, "Steel_Blued", col,
                   origin=(0, screw_c.y, screw_c.z))
    # шлиц на торце и накатка — пропилы
    L.boolean(head, _box("cut_slot", (BASE_X[0] - 13.0, BASE_X[0] - 10.6), (screw_c.y - 7, screw_c.y + 7),
                         (screw_c.z - 0.7, screw_c.z + 0.7)))
    for k in range(36):
        a = 2 * math.pi * k / 36
        c = _box("cut_knurl", (BASE_X[0] - 10.4, BASE_X[0] - 3.4), (-0.25, 0.25), (6.1, 7.5))
        c.matrix_world = Matrix.Translation(Vector((0, screw_c.y, screw_c.z)) * L.MM) @ Matrix.Rotation(a, 4, "X")
        L.boolean(head, c)
    parts.append(head)
    # винты основания на открытом переднем участке (шлицевые, заподлицо)
    for x in (-18.5,):
        s = L.lathe("Mount_Base_Screw", L.fillet([(0, 0), (0, 3.2), (0.5, 3.2), (0.9, 0)], [0, 0, 0.4, 0], 3), 32,
                    "Steel_Blued", col, axis="Y", origin=(x, BASE_OUT - 0.2, 4.2))
        L.boolean(s, _box("cut_slot", (x - 3.6, x + 3.6), (BASE_OUT + 0.4, BASE_OUT + 2.0), (3.85, 4.55)))
        parts.append(s)
    return parts


def build_bracket(col):
    parts = []
    # лапа: накладка на ласточкин хвост основания, концы скошены
    foot_out = [(-108.0, -4.4), (-104.0, 13.2), (-26.0, 13.2), (-22.0, -4.4)]
    foot = L.extrude_profile("Mount_Bracket", L.fillet(foot_out, 0.8, 3, closed=True), BASE_OUT - 0.6,
                             BASE_OUT + 4.6, "Steel_Blued", col)
    # губки лапы, охватывающие скосы основания
    for z0, z1 in ((-4.4, -2.6), (11.7, 13.2)):
        lip = _box("lip", (-106.0, -24.0), (BASE_OUT - 2.0, BASE_OUT), (z0, z1))
        L.boolean(foot, lip, "UNION")
    # стойка с верхней полкой под кольца
    web = L.fillet([(WEB_X[0], 10.0), (WEB_X[1], 10.0), (WEB_X[1], 39.0), (-89.7, 39.0), (-89.7, 32.0),
                    (WEB_X[0], 30.0)], [0, 1.0, 1.0, 1.0, 4.0, 2.0], 5, closed=True)
    web_ob = L.extrude_profile("web", web, WEB_Y[0], WEB_Y[1], None, None, None)
    L.boolean(foot, web_ob, "UNION")
    # полка смещается к оси прицела: мост от стойки к кольцам
    bridge = _box("bridge", (-89.7, WEB_X[1]), (YS - 6.0, WEB_Y[1]), (32.0, ZS - R_RING + 2.5))
    L.boolean(foot, bridge, "UNION")
    # окно и карманы на наружной грани
    circle = [(-53.6 + 9.1 * math.cos(2 * math.pi * k / 64), 22.5 + 9.1 * math.sin(2 * math.pi * k / 64))
              for k in range(64)]
    L.boolean(foot, L.extrude_profile("cut_window", circle, WEB_Y[0] - 5.0, WEB_Y[1] + 5.0, None, None, None))
    for x0, x1 in ((-76.0, -65.0), (-42.2, -31.2)):
        outline = L.fillet([(x0, 13.8), (x1, 13.8), (x1, 31.2), (x0, 31.2)], [2.2] * 4, 6, closed=True)
        L.boolean(foot, L.extrude_profile("cut_pocket", outline, WEB_Y[1] - 5.0, WEB_Y[1] + 5.0, None, None, None))
    # кольца: обойма по трубе прицела + стяжное ушко сверху-слева с прорезью и винтами
    for name, x0, x1, n_screws in RINGS:
        ring = L.lathe("ring", [(x0, R_TUBE), (x0, R_RING), (x1, R_RING), (x1, R_TUBE)], 96, None, None,
                       closed=True, origin=(0, YS, ZS))
        L.boolean(foot, ring, "UNION")
        lug_y0, lug_y1 = YS + 7.5, YS + 17.5
        lug_z0, lug_z1 = ZS + 5.0, ZS + 11.5
        lug = _box("lug", (x0, x1), (lug_y0, lug_y1), (lug_z0, lug_z1))
        L.boolean(foot, lug, "UNION")
        # прорезь кольца по ушку
        L.boolean(foot, _box("cut_split", (x0 - 1, x1 + 1), (YS + 10.0, YS + 10.6), (ZS + 3.0, ZS + 9.0)))
        for i in range(n_screws):
            sx = x0 + (x1 - x0) * (i + 1) / (n_screws + 1)
            s = L.lathe("Mount_RingScrew", L.fillet([(0, 0), (0, 2.6), (0.6, 2.6), (1.1, 0)], [0, 0, 0.5, 0], 3),
                        32, "Steel_Blued", col, axis="Z", origin=(sx, YS + 13.4, lug_z1 - 0.05))
            L.boolean(s, _box("cut_slot", (sx - 3.0, sx + 3.0), (YS + 13.05, YS + 13.75), (lug_z1 + 0.6, lug_z1 + 2.0)))
            parts.append(s)
    # очистить внутренность колец (полость под трубу)
    L.boolean(foot, L.lathe("cut_bore", [(-100, 0), (-100, R_TUBE), (-20, R_TUBE), (-20, 0)], 96,
                            origin=(0, YS, ZS)))
    foot.data.shade_smooth()
    foot.data.set_sharp_from_angle(angle=math.radians(35))
    L.bevel_mod(foot, 0.6, 3, 35)
    parts.insert(0, foot)
    return parts


def build():
    L.reset_scene()
    col = L.collection("PU_Mount")
    root = L.empty("PU_Mount", col=col, size=0.03)
    cb = L.collection("PU_Mount_Base", col)
    ck = L.collection("PU_Mount_Bracket", col)
    base_parts = build_base(cb)
    br_parts = build_bracket(ck)
    base_root = L.empty("Mount_Base_Root", (BASE_X[1], BASE_OUT, 4.2), cb, 0.01)
    br_root = L.empty("Mount_Bracket_Root", (-26.0, BASE_OUT, 4.2), ck, 0.01)   # кронштейн снимается вдоль X
    socket = L.empty("Mount_ScopeSocket", (SCOPE_REAR_X, YS, ZS), ck, 0.02)
    for p in base_parts:
        L.parent_keep(p, base_root)
    for p in br_parts:
        L.parent_keep(p, br_root)
    L.parent_keep(socket, br_root)
    L.parent_keep(base_root, root)
    L.parent_keep(br_root, root)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    lo, hi = L.world_bbox_mm(meshes)
    print("MOUNT bbox mm", tuple(round(v, 2) for v in lo), tuple(round(v, 2) for v in hi),
          "size", tuple(round(h - l, 2) for l, h in zip(lo, hi)))
    L.save_blend(OUT)


if __name__ == "__main__":
    build()
