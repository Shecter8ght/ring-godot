"""Подгонка хвата правой кисти на пистолетной рукоятке целиком (внутри Blender) — кисть и пальцы вместе по касанию.

Опыт «анимация рук по видео» (владелец 2026-11-06: «да, начни с правой»). Хват ИЗЛОМа перенесён с ВЕРАСа, где кисть была в
1,4 раза крупнее: углы пальцев остались, кулак у новой кисти теснее, рукоятка проходит сквозь основные фаланги (до 14 мм).
Пальцами по одному это не исправить — нужно двигать кисть и разгибать пальцы вместе.

Подбор (Нелдер — Мид, 12 чисел): сдвиг кисти поперёк рукоятки (2, мм) и вдоль неё (1, мм — почти не меняется:
высота хвата верная), поворот вокруг середины ладони (3, °); у среднего, безымянного и
мизинца — доля сгиба у основания и доля сгиба средней и концевой фаланг. Цена:
  вхождение кожи в оружие глубже 3 мм (мякоть и перчатка проминаются — сетка рук не мнётся) — квадрат;
  ладонь и подушечки (средняя и концевая фаланги) этих трёх пальцев дальше 2 мм от самой рукоятки (грани нижней
  ствольной коробки позади скобы) — квадрат зазора;
  отход от исходного хвата — квадрат (поперёк 3 мм, вдоль 2 мм, 3°, доля 0,2) — исходный хват на глаз верный.
Затем указательный (на спуске) и большой (вторая и концевая фаланги) — по фалангам, как hand_solver.close.
Суставы — в пределах (hand_solver.anatomical), основание большого не трогается.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <ИЗЛОМ45_Rig_v01.blend> --python-exit-code 1 --python tools/anim_from_video/grip_fit.py -- <выход.blend>
В выходном файле действие IZLOM45_Ready_v01 (кадр 1) заменено подогнанным хватом: клипы из него —
tools/smg03/clips/build_clips.py с этим файлом вместо рига. Исходный риг не меняется.
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hand_solver as hs  # noqa: E402

OUT = sys.argv[sys.argv.index('--') + 1]
S = 'R'
WRAP = ('f_middle', 'f_ring', 'f_pinky')
sc = bpy.context.scene
rig = bpy.data.objects['FPS_ArmsRig']
mesh = bpy.data.objects['FPS_Arms']
wr = bpy.data.objects['SMG03_WeaponRig']
INNER = ('Round_', 'Mag13_follower', 'JamCase', 'Bolt_Steel', 'ChargingSlider')
WEAPON = [o for o in bpy.data.objects if o.type == 'MESH' and o.parent == wr and o.visible_get()
          and not o.name.startswith(INNER)]
ad = rig.animation_data or rig.animation_data_create()
act = bpy.data.actions['IZLOM45_Ready_v01']
ad.action = act
if act.slots:
    ad.action_slot = act.slots[0]
sc.frame_set(1)
basis = {pb.name: pb.matrix_basis.copy() for pb in rig.pose.bones}
ad.action = None
for pb in rig.pose.bones:
    pb.rotation_mode = 'XYZ'
    pb.matrix_basis = basis[pb.name]
bpy.context.view_layer.update()

dg = bpy.context.evaluated_depsgraph_get()
surf = hs.surface(WEAPON, dg)
skin = hs.Skin(rig, mesh, S, step=2)
ik = rig.pose.bones[f'ik_hand.{S}']
AW = rig.matrix_world
IK0 = (AW @ ik.matrix).copy()
hand = rig.pose.bones[f'hand.{S}']
PC = AW @ (hand.head + (rig.pose.bones[f'f_middle.01.{S}'].head - hand.head) * 0.55)   # середина ладони
TARGET = {f: hs.anatomical(hs.read(rig, S, f), f) for f in hs.FINGERS}


# пистолетная рукоятка — по сетке: грани нижней коробки позади спусковой скобы и ниже корпуса (в осях исходника x < −0.19,
# z < −0.035); ось — через центры сечений по высоте. (В rig.py ось наклонена не в ту сторону — +0.27 по x, — поэтому
# касание считалось и со скобой.)
root = bpy.data.objects['SMG03']
RW = root.matrix_world
RINV = RW.inverted()


def grip_region():
    from mathutils.bvhtree import BVHTree
    ob = next(o for o in WEAPON if o.name == 'Receiver_Lower')
    eo = ob.evaluated_get(dg)
    me = eo.to_mesh()
    mw = eo.matrix_world
    vs = [mw @ v.co for v in me.vertices]
    verts, polys, src = [], [], []
    side = {'left': ([], []), 'palm': ([], [])}
    r3 = RINV.to_3x3()
    for poly in me.polygons:
        c = RINV @ (mw @ poly.center)
        if c.x < -0.19 and c.z < -0.035:
            base = len(verts)
            verts.extend(vs[i] for i in poly.vertices)
            polys.append(list(range(base, base + len(poly.vertices))))
            src.append(c)
            n = (r3 @ (mw.to_3x3() @ poly.normal)).normalized()
            key = 'left' if n.y > 0.5 else ('palm' if (n.y < -0.5 or n.x < -0.5) else None)
            if key:
                vv, pp = side[key]
                b2 = len(vv)
                vv.extend(vs[i] for i in poly.vertices)
                pp.append(list(range(b2, b2 + len(poly.vertices))))
    eo.to_mesh_clear()
    # ось: центры сечений (по высоте z исходника)
    cents = []
    for z0 in [x * 0.005 for x in range(-18, -7)]:
        sl = [c for c in src if abs(c.z - z0) < 0.004]
        if len(sl) > 8:
            cents.append(sum(sl, Vector()) / len(sl))
    top, bot = cents[-1], cents[0]
    axis_src = (bot - top).normalized()
    print('FIT граней рукоятки', len(polys), 'ось в осях исходника', [round(v, 2) for v in axis_src],
          'от', [round(v, 3) for v in top], 'до', [round(v, 3) for v in bot])
    global SIDE_BVH
    SIDE_BVH = {k: BVHTree.FromPolygons(v, p, all_triangles=False) for k, (v, p) in side.items()}
    print('FIT граней: левая сторона', len(side['left'][1]), 'под ладонь', len(side['palm'][1]))
    return BVHTree.FromPolygons(verts, polys, all_triangles=False), RW @ top, (RW.to_3x3() @ axis_src).normalized()


SIDE_BVH = {}
GRIP_BVH, GRIP, AXIS = grip_region()
U = AXIS.orthogonal().normalized()
V = AXIS.cross(U).normalized()


def grip_gap(pts, bvh=None):
    """Наименьшее расстояние точек кожи до поверхности рукоятки (снаружи) — касание с ней."""
    best = 1.0
    for p in pts:
        loc, _, _, d = (bvh or GRIP_BVH).find_nearest(p, 0.05)
        if loc is not None and not surf.inside(p):
            best = min(best, d)
    return best


def signed(p, near=0.03):
    loc, _, _, d = surf.bvh.find_nearest(p, near)
    if loc is None:
        return near
    return -d if surf.inside(p) else d


def set_state(x):
    ta, tb, th, rx, ry, rz = x[:6]
    rot = Euler((math.radians(rx), math.radians(ry), math.radians(rz)), 'XYZ').to_matrix().to_4x4()
    move = (U * ta + V * tb + AXIS * th) * 0.001
    m = Matrix.Translation(PC + move) @ rot @ Matrix.Translation(-PC) @ IK0
    ik.matrix = AW.inverted() @ m
    for i, f in enumerate(WRAP):
        c1, c2 = x[6 + 2 * i], x[7 + 2 * i]
        t = TARGET[f]
        vals = [(t[0][0] * c1, t[0][1], 0.0), (t[1][0] * c2, 0.0, 0.0), (t[2][0] * c2, 0.0, 0.0)]
        hs.write(rig, S, f, hs.anatomical(vals, f))
    bpy.context.view_layer.update()


SOFT = 0.003        # мякоть и перчатка под нажимом проминаются: вход до 3 мм не штрафуется (сетка рук не мнётся)


def cost(x, report=False):
    set_state(x)
    pen = 0.0
    worst = 0.0
    groups = [f'hand.{S}', f'thumb.01.{S}'] + [f'{f}.{j:02d}.{S}' for f in WRAP for j in (1, 2, 3)]
    gap = {}
    for g in groups:
        dmin = 1.0
        for p in skin.points(g):
            d = signed(p)
            dmin = min(dmin, d)
            if d < -SOFT:
                pen += ((-d - SOFT) * 1000) ** 2
                worst = max(worst, -d)
        gap[g] = dmin
    touch = 0.0
    want = [f'hand.{S}'] + [f'{f}.03.{S}' for f in WRAP]
    for g in want:
        gap[g] = grip_gap(skin.points(g), SIDE_BVH['palm'] if g.startswith('hand') else SIDE_BVH['left'])
        touch += (max(0.0, gap[g] - 0.002) * 1000) ** 2
    # отход: поперёк рукоятки — 5 мм, вдоль неё — 2 мм (высота хвата верная), поворот — 5°, доли сгиба — 0.3
    reg = ((x[0] / 4.0) ** 2 + (x[1] / 4.0) ** 2 + (x[2] / 1.5) ** 2 + np.sum((np.asarray(x[3:6]) / 1.0) ** 2)
           + np.sum(((np.asarray(x[6:]) - 1.0) / 0.2) ** 2))
    c = 3.0 * pen + 2.0 * touch + 6.0 * reg
    if report:
        print('FIT вход мм', round(worst * 1000, 1), 'вход Σ', round(pen, 1), 'зазоры мм',
              {g.split('.')[0] + g.split('.')[1] if '.' in g else g: round(gap[g] * 1000, 1) for g in want},
              'отход', round(float(reg), 2), 'цена', round(c, 1))
    return c


def nelder_mead(f, x0, steps, iters=500, tol=1e-3):
    n = len(x0)
    pts = [np.array(x0, float)]
    for i in range(n):
        p = np.array(x0, float)
        p[i] += steps[i]
        pts.append(p)
    vals = [f(p) for p in pts]
    for it in range(iters):
        order = np.argsort(vals)
        pts = [pts[i] for i in order]
        vals = [vals[i] for i in order]
        if abs(vals[-1] - vals[0]) < tol * (abs(vals[0]) + 1e-9) and it > 50:
            break
        c = np.mean(pts[:-1], axis=0)
        xr = c + (c - pts[-1])
        fr = f(xr)
        if fr < vals[0]:
            xe = c + 2.0 * (c - pts[-1])
            fe = f(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = c + 0.5 * (pts[-1] - c)
            fc = f(xc)
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                for i in range(1, len(pts)):
                    pts[i] = pts[0] + 0.5 * (pts[i] - pts[0])
                    vals[i] = f(pts[i])
        if it % 50 == 0:
            print('FIT шаг', it, 'цена', round(vals[0], 1))
    i = int(np.argmin(vals))
    return pts[i], vals[i]


x0 = [0, 0, 0, 0, 0, 0] + [1.0] * 6
print('FIT было:')
cost(x0, report=True)
best, val = x0, cost(x0)
for rnd, steps in enumerate(([4, 4, 1.0, 0.5, 0.5, 0.5] + [0.2] * 6, [2, 2, 0.5, 0.3, 0.3, 0.3] + [0.1] * 6)):
    best, val = nelder_mead(cost, best, steps, iters=400)
    print('FIT круг', rnd + 1, 'цена', round(val, 1), 'кисть мм/°', [round(float(v), 1) for v in best[:6]],
          'сгибы', [round(float(v), 2) for v in best[6:]])
print('FIT стало:')
cost(best, report=True)
set_state(best)
# указательный и большой — по фалангам у поверхности
for f in ('f_index', 'thumb'):
    print('FIT', f, 'было/стало мм', hs.close(rig, S, f, hs.anatomical(hs.read(rig, S, f), f), skin, surf))

# ключи хвата: действие IZLOM45_Ready_v01 в этом файле — все кости на кадре 1 (как в rig.py); клипы читают его в XYZ
fitted = {pb.name: pb.matrix_basis.copy() for pb in rig.pose.bones}
ad.action = act
if act.slots:
    ad.action_slot = act.slots[0]
for pb in rig.pose.bones:
    pb.rotation_mode = 'XYZ'
    pb.matrix_basis = fitted[pb.name]
for pb in rig.pose.bones:
    pb.keyframe_insert('location', frame=1)
    pb.keyframe_insert('rotation_euler', frame=1)
txt = bpy.data.texts.get('Подгонка хвата') or bpy.data.texts.new('Подгонка хвата')
txt.from_string(__doc__ + f'\nКисть: сдвиг мм {[round(v, 1) for v in best[:3]]}, поворот ° {[round(v, 1) for v in best[3:6]]}; '
                f'доли сгиба (основание, средняя+концевая) {dict(zip(WRAP, [tuple(round(v, 2) for v in best[6 + 2 * i:8 + 2 * i]) for i in range(3)]))}\n')
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print('FIT saved', OUT)
