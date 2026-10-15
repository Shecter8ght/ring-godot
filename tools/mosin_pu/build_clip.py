"""Пластинчатая обойма на 5 патронов 7,62×54R — high-poly для просмотра формы.

Форма по фото: Commons Mosin_ammo_clip.JPG (PD), Stripper_clip_of_Hungarian_7.62x54R.JPG (CC0),
фото владельца 2 и 3, обойма в направляющих (refs/web/clip/web/web_07.jpg).
U-образный профиль из листа 0,5 мм: спинка за донцами, две стенки со ступенькой — у спинки стенки
раздвинуты под закраины Ø14,48, дальше сходятся к корпусам гильз и держат закраины. На обоих концах
каждой стенки — язычок между двумя прорезями, отогнут внутрь (упор крайних патронов).

Размеры: шаг патронов 13,45 мм (по фото 1,09 диаметра гильзы; меньше 13,43 закраина верхнего
патрона пересекла бы корпус нижнего), длина обоймы 70,0 мм (фото: 5,29 шага; продавец — 2,75″),
вылет стенок 15,5 мм (фото), лист 0,5 мм (оценка). Язычки на обеих стенках — допущение (видна одна).

Оси обоймы как в направляющих винтовки: патроны вдоль +X, обойма вдоль Z, стенки по ±Y.
Начало — середина внутренней плоскости спинки. Запуск:
blender --background --factory-startup --python tools/mosin_pu/build_clip.py
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mosin_lib as L  # noqa: E402

OUT = os.path.join(L.ASSET_DIR, "models", "05_Обойма", "Mosin_StripperClip_v01.blend")
OUT_LOADED = os.path.join(L.ASSET_DIR, "models", "00_Сборка", "Mosin_Clip_loaded_check_v01.blend")
CARTRIDGE = os.path.join(L.ASSET_DIR, "models", "04_Патрон", "Mosin_Cartridge_762x54R_v01.blend")

T = 0.5             # толщина листа
HALF_LEN = 35.0     # половина длины обоймы
PITCH = 13.45       # шаг патронов
U_FREE = 15.5       # вылет стенок от спинки (наружная грань спинки на −T)
V_RIM = 7.65        # средняя линия стенки у закраин (внутр. 7,40 > 7,24)
V_BODY = 6.50       # средняя линия стенки у корпусов (внутр. 6,25 > 6,185)
U_STEP0, U_STEP1 = 3.8, 4.5   # ступенька стенки
STAGGER = 1.65      # через один патрон донце смещено вперёд (закраины не в одной плоскости)

# язычок: прорези от торца обоймы к корню (u — от спинки, z — от торца внутрь)
TONGUE_ROOT = 6.2
SLIT_W = 0.35
SLIT_A = [(7.55, 0.0), (8.45, 4.6), (8.75, 5.6), (9.3, 6.2), (9.9, 6.6)]   # (u, расстояние от корня)
BEND_LEN, BEND_ANG = 1.4, math.radians(28)


def centerline():
    pts = [(U_FREE, V_BODY), (U_STEP1, V_BODY), (U_STEP0, V_RIM), (-T / 2, V_RIM),
           (-T / 2, -V_RIM), (U_STEP0, -V_RIM), (U_STEP1, -V_BODY), (U_FREE, -V_BODY)]
    radii = [0, 0.5, 0.5, 0.65, 0.65, 0.5, 0.5, 0]
    path = L.fillet(pts, radii, seg=6)
    # густые точки по плоским участкам — для прорезей и отгиба язычков
    dense = []
    for a, b in zip(path[:-1], path[1:]):
        a, b = Vector(a), Vector(b)
        n = max(1, int((b - a).length / 0.4))
        dense += [a.lerp(b, i / n) for i in range(n)]
    dense.append(Vector(path[-1]))
    return dense


def z_slices():
    zs = set()
    z = -HALF_LEN
    while z < HALF_LEN - 1e-6:
        zs.add(round(z, 4))
        edge = HALF_LEN - abs(z)
        z += 0.3 if edge < TONGUE_ROOT + 1.5 else 1.5
    zs.add(HALF_LEN)
    return sorted(zs)


def build_sheet(col):
    path = centerline()
    n = len(path)
    normals = []
    for i in range(n):
        a = path[max(0, i - 1)]
        b = path[min(n - 1, i + 1)]
        tng = (b - a).normalized()
        normals.append(Vector((-tng.y, tng.x)))
    outer = [p + nm * T / 2 for p, nm in zip(path, normals)]
    inner = [p - nm * T / 2 for p, nm in zip(path, normals)]
    zs = z_slices()
    verts, faces = [], []
    idx = {}
    for k, z in enumerate(zs):
        for i in range(n):
            for s, src in ((0, outer), (1, inner)):
                idx[(k, i, s)] = len(verts)
                verts.append((src[i].x, src[i].y, z))
    for k in range(len(zs) - 1):
        for i in range(n - 1):
            faces.append((idx[(k, i, 0)], idx[(k, i + 1, 0)], idx[(k + 1, i + 1, 0)], idx[(k + 1, i, 0)]))
            faces.append((idx[(k, i, 1)], idx[(k + 1, i, 1)], idx[(k + 1, i + 1, 1)], idx[(k, i + 1, 1)]))
        for i in (0, n - 1):   # свободные кромки стенок
            faces.append((idx[(k, i, 0)], idx[(k + 1, i, 0)], idx[(k + 1, i, 1)], idx[(k, i, 1)]))
    last = len(zs) - 1
    for i in range(n - 1):     # торцы обоймы
        faces.append((idx[(0, i, 0)], idx[(0, i, 1)], idx[(0, i + 1, 1)], idx[(0, i + 1, 0)]))
        faces.append((idx[(last, i, 0)], idx[(last, i + 1, 0)], idx[(last, i + 1, 1)], idx[(last, i, 1)]))
    verts = [(x * L.MM, y * L.MM, z * L.MM) for x, y, z in verts]
    ob = L.mesh_object("Clip_Body", verts, faces, "Clip_Steel", col, smooth_angle=None)
    L.fix_normals(ob)
    return ob


def slit_paths():
    """Средние линии прорезей в координатах (u, z) для всех четырёх язычков стенки."""
    c = 10.5                                   # середина язычка по u
    a = SLIT_A
    b = [(2 * c - u, d) for u, d in a]
    out = []
    for zsign in (1, -1):
        for path in (a, b):
            z_root = zsign * (HALF_LEN - TONGUE_ROOT)
            out.append([(u, z_root + zsign * d) for u, d in path] + [(path[-1][0] + (0.6 if path is b else -0.6) * -1,
                                                                       zsign * (HALF_LEN + 0.8))])
    return out


def slit_cutter(path_uz, vsign, col):
    """Тонкая призма вдоль прорези, насквозь через стенку по v."""
    pts = [Vector(p) for p in path_uz]
    left, right = [], []
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        tng = (b - a).normalized()
        nm = Vector((-tng.y, tng.x))
        # у корня прорезь заканчивается полукругом — не острый надрез
        left.append(p + nm * SLIT_W / 2)
        right.append(p - nm * SLIT_W / 2)
    root = pts[0]
    tng0 = (pts[1] - pts[0]).normalized()
    cap = [root + (Vector((-tng0.y, tng0.x)) * math.cos(t) - tng0 * math.sin(t)) * SLIT_W / 2
           for t in [math.pi * i / 6 for i in range(1, 6)]]
    outline = left + list(reversed(right)) + list(reversed(cap))
    v0, v1 = (V_BODY - 0.6, V_BODY + 0.6)
    if vsign < 0:
        v0, v1 = -v1, -v0
    verts = [(u * L.MM, v * L.MM, z * L.MM) for v in (v0, v1) for (u, z) in outline]
    m = len(outline)
    faces = [(k, (k + 1) % m, m + (k + 1) % m, m + k) for k in range(m)]
    faces += [tuple(reversed(range(m))), tuple(range(m, 2 * m))]
    ob = L.mesh_object("slit_cutter", verts, faces, None, col, smooth_angle=None)
    L.fix_normals(ob)
    return ob


def bend_tongues(ob):
    """Отгибает язычки внутрь: корень — дуга BEND_LEN, дальше прямо под углом BEND_ANG."""
    me = ob.data
    paths = slit_paths()
    r_b = BEND_LEN / BEND_ANG
    moved = 0
    for v in me.vertices:
        u, vv, z = (c / L.MM for c in v.co)
        if u < 6.0 or abs(abs(vv) - V_BODY) > T:
            continue
        zsign = 1 if z > 0 else -1
        d = abs(z) - (HALF_LEN - TONGUE_ROOT)
        if d <= 0:
            continue
        pa, pb = (paths[0], paths[1]) if zsign > 0 else (paths[2], paths[3])
        ua, ub = _u_at(pa, z), _u_at(pb, z)
        if ua is None or ub is None or not (min(ua, ub) < u < max(ua, ub)):
            continue
        vsign = 1 if vv > 0 else -1
        s = (abs(vv) - V_BODY)            # смещение от средней поверхности (+ наружу)
        if d <= BEND_LEN:
            phi = d / r_b
            dz = (r_b + s) * math.sin(phi)
            dv = (r_b + s) * math.cos(phi) - r_b
        else:
            dz = (r_b + s) * math.sin(BEND_ANG) + (d - BEND_LEN) * math.cos(BEND_ANG)
            dv = (r_b + s) * math.cos(BEND_ANG) - r_b - (d - BEND_LEN) * math.sin(BEND_ANG)
        z_new = zsign * (HALF_LEN - TONGUE_ROOT + dz)
        v_new = vsign * (V_BODY + dv)
        v.co = (u * L.MM, v_new * L.MM, z_new * L.MM)
        moved += 1
    me.update()
    print("TONGUE verts moved", moved)


def _u_at(path, z):
    for (u0, z0), (u1, z1) in zip(path[:-1], path[1:]):
        if min(z0, z1) <= z <= max(z0, z1) and abs(z1 - z0) > 1e-9:
            t = (z - z0) / (z1 - z0)
            return u0 + (u1 - u0) * t
    return None


def build():
    L.reset_scene()
    col = L.collection("StripperClip")
    root = L.empty("StripperClip", col=col, size=0.03)
    body = build_sheet(col)
    for vsign in (1, -1):
        for path in slit_paths():
            L.boolean(body, slit_cutter(path, vsign, col), "DIFFERENCE", "EXACT")
    # прорези режут сетку листа рядом с её вершинами — остаются осколки в сотые доли мм
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.04 * L.MM)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=0.04 * L.MM)
    bm.to_mesh(body.data)
    bm.free()
    bend_tongues(body)
    body.data.shade_smooth()
    body.data.set_sharp_from_angle(angle=math.radians(30))
    body.parent = root
    lo, hi = L.world_bbox_mm([body])
    print("CLIP bbox mm", tuple(round(v, 3) for v in lo), tuple(round(v, 3) for v in hi),
          "size", tuple(round(h - l, 3) for l, h in zip(lo, hi)))
    L.save_blend(OUT)

    # проверочная сборка: 5 патронов в обойме (связанные копии)
    with bpy.data.libraries.load(CARTRIDGE, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("Cartridge")]
    cart_col = L.collection("Cartridges_in_clip")
    base = {o.name: o for o in dst.objects}
    for i in range(5):
        r = bpy.data.objects.new(f"Round_{i + 1}", None)
        cart_col.objects.link(r)
        r.location = (STAGGER * L.MM if i % 2 else 0.0, 0, (i - 2) * PITCH * L.MM)
        for name in ("Cartridge_Case", "Cartridge_Bullet", "Cartridge_Primer"):
            c = bpy.data.objects.new(f"{name}_{i + 1}", base[name].data)
            cart_col.objects.link(c)
            c.parent = r
    L.save_blend(OUT_LOADED)


if __name__ == "__main__":
    build()
