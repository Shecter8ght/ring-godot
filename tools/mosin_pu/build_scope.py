"""Оптический прицел ПУ 3,5×21 (труба типа 1891/30, без сужения) — high-poly для просмотра формы.

Размеры: длина 169 мм (Википедия, PU scope) — по снимку 169,7; окуляр Ø29,2 (25 мм), труба Ø27,8 за кольцом
и Ø26,4 спереди, объектив Ø21 (паспорт 3,5×21). Барабаны: вертикальный сверху, боковой слева, оба на одной
линии (центр 87 мм от окуляра). Снято с подложки RIA 5039/265; детали барабанов — снимок fotoace.ru (pikabu).

Отдельные объекты: корпус (полый), барабаны, линзы окуляра и объектива (стекло с толщиной), сетка.
Оси: оптическая ось +X (к объективу), верх +Z, правая сторона стрелка −Y (боковой барабан — слева, +Y).
Начало — центр заднего торца окуляра на оптической оси.
Запуск: blender --background --factory-startup --python tools/mosin_pu/build_scope.py
"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mosin_lib as L  # noqa: E402

OUT = os.path.join(L.ASSET_DIR, "models", "02_Прицел", "Mosin_PU_Scope_v01.blend")
LEN = 169.7
R_EYE, R_BODY, R_FRONT, R_IN = 14.6, 13.9, 13.2, 10.6
TURRET_X = 87.0


def body_profile():
    # замкнутый профиль (осевая, радиус): снаружи от окуляра к объективу, внутри обратно
    outer = [(0.0, 11.9), (0.0, R_EYE), (25.0, R_EYE), (25.6, R_BODY), (99.0, R_BODY), (99.6, R_FRONT),
             (165.6, R_FRONT), (165.9, R_FRONT - 0.35), (166.3, R_FRONT), (LEN, R_FRONT), (LEN, 11.2)]
    inner = [(165.2, 11.2), (165.2, R_IN), (4.2, R_IN), (4.2, 11.9)]
    pts = outer + inner
    radii = [0.3, 1.2, 0.4, 0.3, 0.3, 0.3, 0.1, 0.1, 0.1, 1.0, 0.3, 0.3, 0.3, 0.3, 0.3]
    return L.fillet(pts, radii, seg=6, closed=True)


def knurl_disc(name, r, h, z0, teeth=60, depth=0.28, seg_per=3, mat="Scope_Body", col=None):
    """Накатанный диск: ось Z, рифление по образующей."""
    n = teeth * seg_per
    verts, faces = [], []
    for zi, z in enumerate((z0, z0 + h)):
        for k in range(n):
            a = 2 * math.pi * k / n
            rr = r - (depth if (k % seg_per) == 0 else 0.0)
            verts.append((rr * math.cos(a) * L.MM, rr * math.sin(a) * L.MM, z * L.MM))
    faces += [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    faces.append(tuple(reversed(range(n))))
    faces.append(tuple(range(n, 2 * n)))
    ob = L.mesh_object(name, verts, faces, mat, col, smooth_angle=30)
    L.fix_normals(ob)
    L.bevel_mod(ob, 0.35, 2, 50)
    return ob


def turret(prefix, col, r_boss, r_drum, r_cap, h_boss, h_drum, h_cap, screws):
    """Барабан поправок по оси +Z от поверхности трубы; затем ставится матрицей."""
    parts = []
    base = R_BODY - 1.5
    boss = L.lathe(prefix + "_Boss", L.fillet([(base, 0), (base, r_boss), (base + h_boss, r_boss),
                                              (base + h_boss, 0)], [0, 0, 0.5, 0], 3), 64, "Scope_Body", col,
                   axis="Z")
    drum = L.lathe(prefix + "_Scale", L.fillet([(base + h_boss, 0), (base + h_boss, r_drum),
                                               (base + h_boss + h_drum, r_drum), (base + h_boss + h_drum, 0)],
                                              [0, 0.4, 0.4, 0], 3), 72, "Steel_Bright", col, axis="Z")
    z_cap = base + h_boss + h_drum
    cap = knurl_disc(prefix + "_Cap", r_cap, h_cap, z_cap, col=col)
    parts += [boss, drum, cap]
    for (sx, sy) in screws:   # винты на торце крышки
        s = L.lathe(prefix + "_CapScrew", L.fillet([(0, 0), (0, 1.6), (0.35, 1.6), (0.6, 0)], [0, 0, 0.3, 0], 3),
                    24, "Scope_Body", col, axis="Z", origin=(sx, sy, z_cap + h_cap - 0.05))
        L.boolean(s, _slot_cut(sx, sy, z_cap + h_cap + 0.3, 1.8, 0.35))
        parts.append(s)
    return parts


def _slot_cut(x, y, z, length, width):
    v = [(x + dx * length, y + dy * width / 2, z + dz * 0.6) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
    v = [tuple(c * L.MM for c in p) for p in v]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    ob = L.mesh_object("cut_slot", v, faces, None, None, None)
    L.fix_normals(ob)
    return ob


def lens(name, x0, thick, r, curve, col):
    """Линза: стекло с выпуклыми гранями (стрелка curve), кромка скруглена."""
    n = 12
    front = [(x0 - curve * (1 - (i / n) ** 2), r * i / n) for i in range(n + 1)]
    back = [(x0 + thick + curve * (1 - (i / n) ** 2), r * i / n) for i in range(n, -1, -1)]
    prof = front + back
    return L.lathe(name, prof, 72, "Glass_Lens", col, smooth_angle=80)


def reticle(col, x):
    """Сетка ПУ: заострённый пенёк снизу и горизонтальные нити по бокам (тонкая пластина в плоскости YZ)."""
    t = 0.05
    shapes = [
        [(-0.9, -R_IN + 0.1), (0.9, -R_IN + 0.1), (0.35, -1.2), (0.0, 0.0), (-0.35, -1.2)],      # пенёк
        [(-R_IN + 0.1, -0.06), (-2.2, -0.06), (-2.2, 0.06), (-R_IN + 0.1, 0.06)],                # левая нить
        [(2.2, -0.06), (R_IN - 0.1, -0.06), (R_IN - 0.1, 0.06), (2.2, 0.06)],                    # правая нить
    ]
    obs = []
    for sh in shapes:
        obs.append(L.extrude_profile("Scope_Reticle", sh, x - t / 2, x + t / 2, "Reticle_Black", col, None,
                                     plane="YZ"))
    ret = L.join(obs, "Scope_Reticle")
    return ret


def build():
    L.reset_scene()
    col = L.collection("PU_Scope")
    root = L.empty("PU_Scope", col=col, size=0.03)
    body = L.lathe("Scope_Body", body_profile(), 128, "Scope_Body", col, closed=True)
    parts = [body]
    # вертикальный барабан сверху
    top = turret("Scope_TurretElev", col, 8.6, 9.25, 11.0, 3.8, 5.0, 3.7, [(0.0, 0.0)])
    for p in top:
        p.matrix_world = Matrix.Translation(Vector((TURRET_X, 0, 0)) * L.MM) @ p.matrix_world
    # боковой барабан слева (+Y): поворот оси Z → +Y
    side = turret("Scope_TurretWind", col, 8.2, 8.8, 10.2, 3.2, 4.2, 3.4,
                  [(0.0, 4.6), (4.0, -2.3), (-4.0, -2.3)])
    rot = Matrix.Rotation(-math.pi / 2, 4, "X")
    for p in side:
        p.matrix_world = Matrix.Translation(Vector((TURRET_X, 0, 0)) * L.MM) @ rot @ p.matrix_world
    parts += top + side
    # крышки барабанов вращаются вокруг своих осей — начало на оси
    for p in top + side:
        if p.name.endswith("_Cap") or "_Cap." in p.name:
            bpy.context.view_layer.update()
            c = p.matrix_world.translation
            axis_pt = Vector((TURRET_X, 0, 0)) * L.MM
            L.set_origin_mm(p, tuple(v / L.MM for v in axis_pt))
    lens_r = lens("Scope_Lens_Eyepiece", 1.4, 2.4, 11.8, 0.35, col)
    lens_f = lens("Scope_Lens_Objective", 166.2, 2.2, 11.1, 0.4, col)
    ret = reticle(col, 120.0)
    parts += [lens_r, lens_f, ret]
    for p in parts:
        L.parent_keep(p, root)
    lo, hi = L.world_bbox_mm([p for p in parts])
    print("SCOPE bbox mm", tuple(round(v, 2) for v in lo), tuple(round(v, 2) for v in hi),
          "size", tuple(round(h - l, 2) for l, h in zip(lo, hi)))
    L.save_blend(OUT)


if __name__ == "__main__":
    build()
