"""ИЗЛОМ-45: верх и низ корпуса по линии шва — для двух атласов (владелец 2026-11-05: «Два атласа 4K»).

Корпус исходника — одно тело; у серийного верх — металл под анодированием, низ — полимер. Граница на виде сбоку
состоит только из отрезков вдоль осей: задняя грань переднего блока X 22 (с низом нижней планки), низ коробки Z 15 от
переднего блока до заднего прилива (над шахтой — канавка шва, у проёма скобы — его верх, на X −78…−112 и позади
рукояти канавки нет), задний прилив X −240 / Z 8. Игровая сетка корпуса режется по этим отрезкам (bisect) и делится
по граням: граница цвета идёт ровно по середине канавки, а не по рёбрам упрощённых треугольников. High-poly делится
тем же правилом без разреза — её грани мелкие.

Точка грани проверяется со сдвигом внутрь детали вдоль нормали (INSET): днище коробки над проёмом скобы (Z 15, смотрит
вниз), низ переднего блока и стенки канавки попадают каждая на свою сторону.
"""
from __future__ import annotations

import json
from pathlib import Path

import bmesh

ROOT = Path(__file__).resolve().parents[2]
PROF = json.loads((ROOT / 'tools/smg03/data/profiles.json').read_text(encoding='utf-8'))
FRONT_BLOCK_REAR_X = 22.0          # lib.FRONT_BLOCK_REAR_X
TANG_X, TANG_Z = -240.0, 8.0       # задний прилив снизу коробки (tools/smg03/profiles.py)
BOTTOM_Z = -45.0                   # ниже низа нижней планки (−29.5): под передним блоком — только планка
MM = 0.001


def upper_polygon() -> list:
    """Верх корпуса на виде сбоку (мм): как «upper» в profiles.regions(), с запасом наружу (над планкой, за торцами)."""
    seam, seam_rear, step = PROF['seam_z'], PROF['seam_rear_z'], PROF['seam_step_x']
    front, rear = PROF['front_face_x'] + 20.0, PROF['rear_x'] - 30.0
    return [(front, 100.0), (front, BOTTOM_Z), (FRONT_BLOCK_REAR_X, BOTTOM_Z), (FRONT_BLOCK_REAR_X, seam), (step, seam),
            (step, seam_rear), (TANG_X, seam_rear), (TANG_X, TANG_Z), (rear, TANG_Z), (rear, 100.0)]


def cuts() -> list:
    """Отрезки границы для разреза сетки: (ось плоскости 'x'|'z', значение мм, по другой оси от, до)."""
    seam, seam_rear = PROF['seam_z'], PROF['seam_rear_z']
    rear = PROF['rear_x'] - 30.0
    out = [('x', FRONT_BLOCK_REAR_X, BOTTOM_Z, seam), ('z', seam, TANG_X, FRONT_BLOCK_REAR_X),
           ('x', TANG_X, TANG_Z, seam_rear), ('z', TANG_Z, rear, TANG_X)]
    if abs(seam_rear - seam) > 1e-6:
        out.append(('x', PROF['seam_step_x'], seam, seam_rear))
    return out


def inside(x: float, z: float, poly: list) -> bool:
    c = False
    n = len(poly)
    for i in range(n):
        x1, z1 = poly[i]
        x2, z2 = poly[(i + 1) % n]
        if (z1 > z) != (z2 > z) and x < x1 + (z - z1) * (x2 - x1) / (z2 - z1):
            c = not c
    return c


def is_upper(center, normal, inset_mm: float, poly=None) -> bool:
    """Грань по центру (м) и нормали: точка, сдвинутая внутрь детали на inset_mm, — в области верха на виде сбоку."""
    poly = poly or upper_polygon()
    x = center[0] / MM - normal[0] * inset_mm
    z = center[2] / MM - normal[2] * inset_mm
    return inside(x, z, poly)


def cut_mesh(bm, margin_mm: float = 1.0) -> int:
    """Разрез сетки корпуса (bmesh, координаты в м) по отрезкам границы: плоскостью — только грани в полосе отрезка.
    Возврат — число граней после разреза."""
    for axis, v, lo, hi in cuts():
        a = 0 if axis == 'x' else 2
        b = 2 if axis == 'x' else 0
        lo_m, hi_m = (lo - margin_mm) * MM, (hi + margin_mm) * MM
        faces = [f for f in bm.faces
                 if min(p.co[a] for p in f.verts) < v * MM < max(p.co[a] for p in f.verts)
                 and max(p.co[b] for p in f.verts) > lo_m and min(p.co[b] for p in f.verts) < hi_m]
        if not faces:
            continue
        edges = list({e for f in faces for e in f.edges})
        verts = list({p for f in faces for p in f.verts})
        co = [0.0, 0.0, 0.0]
        co[a] = v * MM
        no = [0.0, 0.0, 0.0]
        no[a] = 1.0
        bmesh.ops.bisect_plane(bm, geom=verts + edges + faces, dist=1e-7, plane_co=co, plane_no=no)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method='BEAUTY',
                          ngon_method='EAR_CLIP')
    return len(bm.faces)


def face_sides(me, inset_mm: float) -> list:
    """Верх (True) / низ (False) у каждой грани сетки me (координаты в м)."""
    poly = upper_polygon()
    return [is_upper(p.center, p.normal, inset_mm, poly) for p in me.polygons]
