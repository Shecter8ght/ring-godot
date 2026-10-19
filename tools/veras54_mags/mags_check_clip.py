"""Проверка патронов в магазине 45 / барабане 60 без снятия магазина (владелец 2026-10-19): автомат поворачивается к
камере стороной с окнами остатка, держится, возвращается. Руки остаются на оружии (IK-кисти — дочерние Weapon_CTRL).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup <файл хвата .blend> --python tools/veras54_mags/mags_check_clip.py -- m45|d60 <выход .blend> [varn_v1|varn_v2]
Действия — как у клипов автомата (build_clips.py): VERAS54_Check[_<рукоятка>]_<mag45|drum60>_{Arms,Weapon,Controls,Rounds}_v01.
45: окна на передних углах обоих боков — автомат кренится вправо (правый бок к глазам) и подаётся ближе;
барабан: окно на задней крышке — дуло вниз, барабан задней крышкой к глазам.
Участок показа (кадры HOLD) — для проверки с удержанием R (config.check_hold_sets в data/weapons.json).
"""
import math
import sys
import json
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / 'veras54_v13/clips'))
import rig_common as rc  # noqa: E402

DATA = Path('E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия/Клипы v02 (Claude)')
ARGS = sys.argv[sys.argv.index('--') + 1:]
MID, OUT = ARGS[:2]
GID = ARGS[2] if len(ARGS) > 2 and ARGS[2] in rc.GRIPS else ''
SET = {'m45': 'mag45', 'd60': 'drum60'}[MID]
TAG = 'Check' + ('_' + GID if GID else '') + '_' + SET
FPS = 30
sc = bpy.context.scene
sc.render.fps = FPS
for m in list(sc.timeline_markers):
    sc.timeline_markers.remove(m)
arms = bpy.data.objects['FPS_ArmsRig']
wr = bpy.data.objects['VERAS54_WeaponRig']
root = bpy.data.objects['VERAS54']
magob = bpy.data.objects['Magazine']
rc.hide_suppressor()
for pb in list(arms.pose.bones) + list(wr.pose.bones):
    pb.rotation_mode = 'XYZ'
ALL = [b.name for b in arms.pose.bones]
for a in (arms, wr, root, magob):
    if a.animation_data:
        a.animation_data.action = None
ad = arms.animation_data or arms.animation_data_create()
ready_act = bpy.data.actions['VERAS54_Grip_Manual_v02']
ad.action = ready_act
if ready_act.slots:
    ad.action_slot = ready_act.slots[0]
sc.frame_set(1)
bpy.context.view_layer.update()
READY = {n: arms.pose.bones[n].matrix_basis.copy() for n in ALL}
ad.action = None
if GID:
    for n, v in json.loads((DATA / f'grip_{GID}_pose.json').read_text(encoding='utf-8')).items():
        READY[n] = Matrix(v)
    rc.add_grip(GID)
for n, m in READY.items():
    arms.pose.bones[n].matrix_basis = m
bpy.context.view_layer.update()
wc = arms.pose.bones['Weapon_CTRL']
WC_READY = wc.matrix.copy()
GRIP = Vector((-0.14, -0.323, 1.635))       # рукоятка — ось наклона оружия (как в build_clips.py)


def about(p, rot):
    return Matrix.Translation(p) @ rot.to_4x4() @ Matrix.Translation(-p)


def pchip(keys, f):
    xs = [k[0] for k in keys]
    if f <= xs[0]:
        return keys[0][1:]
    if f >= xs[-1]:
        return keys[-1][1:]
    i = max(j for j in range(len(xs) - 1) if xs[j] <= f)
    h = xs[i + 1] - xs[i]
    t = (f - xs[i]) / h
    out = []
    for c in range(1, len(keys[0])):
        ys = [k[c] for k in keys]

        def slope(j):
            if j == 0 or j == len(xs) - 1:
                return 0.0
            d0 = (ys[j] - ys[j - 1]) / (xs[j] - xs[j - 1])
            d1 = (ys[j + 1] - ys[j]) / (xs[j + 1] - xs[j])
            if d0 * d1 <= 0:
                return 0.0
            w0 = 2 * (xs[j + 1] - xs[j]) + (xs[j] - xs[j - 1])
            w1 = (xs[j + 1] - xs[j]) + 2 * (xs[j] - xs[j - 1])
            return (w0 + w1) / (w0 / d0 + w1 / d1)
        m0, m1 = slope(i), slope(i + 1)
        t2, t3 = t * t, t * t * t
        out.append((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h * m0 + (-2 * t3 + 3 * t2) * ys[i + 1]
                   + (t3 - t2) * h * m1)
    return tuple(out)


# Поза показа — расчётом: окно остатка (точка и нормаль в осях магазина = осях автомата, м) встаёт перед глазами
# (на расстоянии d по взгляду, со смещением вправо / вверх на экране) и смотрит прямо в камеру; оставшийся поворот —
# по второму направлению автомата (у 45 — дуло влево-вперёд, поперёк тела, как держат стрелки-правши: к глазам левый
# бок, окна и цифры есть на обоих; у барабана — верх автомата вверх с лёгким завалом вправо, крышку видно наискось
# на 40°: строго по оси за ней рукоятка и правая кисть).
TARGET = {
    # точка окна: левый бок 45-го у окон, ряд «25» (дуга магазина, ближе к передней стенке)
    'mag45': dict(point=(0.0515, 0.0155, -0.1114), normal=(0.0, 1.0, 0.0), d=0.40, right=0.03, up=-0.06,
                  axis=(1.0, 0.0, 0.0), axis_to=(-0.80, 0.50, 0.20)),
    # точка окна: задняя крышка барабана, низ дуги цифр (36 мм ниже оси барабана)
    'drum60': dict(point=(0.0089, 0.0, -0.1468), normal=(-0.9455, 0.0, -0.3256), d=0.40, right=0.02, up=-0.06,
                   axis=(0.0, 0.0, 1.0), axis_to=(0.30, 0.0, 0.95), oblique=40.0),
}[SET]


def solve_show():
    """Поворот (кватернион, вокруг рукоятки GRIP) и сдвиг оружия, при которых окно магазина — перед глазами и смотрит в камеру."""
    cam = bpy.data.objects['FPS • Camera'].matrix_world
    eye = cam.translation.copy()
    fwd = -(cam.to_3x3() @ Vector((0, 0, 1))).normalized()
    up = (cam.to_3x3() @ Vector((0, 1, 0))).normalized()
    right = fwd.cross(up).normalized()
    m = magob.matrix_world
    pw = m @ Vector(TARGET['point'])
    n0 = (m.to_3x3() @ Vector(TARGET['normal'])).normalized()
    a0 = (m.to_3x3() @ Vector(TARGET['axis'])).normalized()
    target = eye + fwd * TARGET['d'] + right * TARGET['right'] + up * TARGET['up']
    n1 = (eye - target).normalized()
    # смотреть на окно наискось (у барабана: за задней крышкой по оси — рукоятка и правая кисть)
    n1 = Matrix.Rotation(math.radians(TARGET.get('oblique', 0.0)), 3, up) @ n1
    ax, ay, az = TARGET['axis_to']                      # в осях камеры: вправо, вперёд, вверх
    a1 = (right * ax + fwd * ay + up * az).normalized()

    def frame(n, a):
        a = (a - n * a.dot(n)).normalized()
        return Matrix((n, a, n.cross(a))).transposed()

    rot = frame(n1, a1) @ frame(n0, a0).transposed()
    return rot.to_quaternion(), target - GRIP - rot @ (pw - GRIP)


SHOW_Q, SHOW_T = solve_show()
print('MAGS_CHECK_CLIP show deg', round(math.degrees(SHOW_Q.angle), 1), 'axis', tuple(round(v, 3) for v in SHOW_Q.axis),
      'move m', tuple(round(v, 3) for v in SHOW_T), flush=True)
HOLD = (20, 40)
END = 60


# доля пути к показу по кадрам: подъём, показ (HOLD), возврат с лёгким перелётом
FRAC = [(1, 0.0), (6, 0.22), (14, 0.9), (HOLD[0], 1.0), (HOLD[1], 1.0), (47, 0.62), (54, 0.0), (57, 0.0), (END, 0.0)]
sc.frame_start, sc.frame_end = 1, END


def weapon_delta(f):
    k = min(max(pchip(FRAC, f)[0], 0.0), 1.0)
    q = Quaternion().slerp(SHOW_Q, k)
    # покачивание руки на показе (затухает к краям участка)
    w = min(max(min(f - HOLD[0] + 4, HOLD[1] + 4 - f) / 6.0, 0.0), 1.0)
    t = f / FPS
    sway = Euler((math.radians(0.8 * w * math.sin(t * 1.7)), math.radians(1.1 * w * math.sin(t * 1.3 + 1.0)),
                  math.radians(0.7 * w * math.sin(t * 1.1 + 2.0))), 'XYZ').to_quaternion()
    off = SHOW_T * k + Vector((0.002 * math.sin(t * 1.9), 0.002 * math.sin(t * 1.5 + 0.5), 0.002 * math.sin(t * 2.1))) * w
    return Matrix.Translation(off) @ about(GRIP, (sway @ q).to_matrix())


def key(pb, frame):
    pb.keyframe_insert('location', frame=frame)
    pb.keyframe_insert('rotation_euler', frame=frame)


arm_act = bpy.data.actions.new(f'VERAS54_{TAG}_Arms_v01')
ad.action = arm_act
w_act = bpy.data.actions.new(f'VERAS54_{TAG}_Weapon_v01')
(wr.animation_data or wr.animation_data_create()).action = w_act
c_act = bpy.data.actions.new(f'VERAS54_{TAG}_Controls_v01')
(root.animation_data or root.animation_data_create()).action = c_act
m_act = bpy.data.actions.new(f'VERAS54_{TAG}_Rounds_v01')
(magob.animation_data or magob.animation_data_create()).action = m_act
for a in (arm_act, w_act, c_act, m_act):
    a.use_fake_user = True
for n in ALL:
    key(arms.pose.bones[n], 1)
    key(arms.pose.bones[n], END)
magc = wr.pose.bones['Magazine_Control']
key(magc, 1)
key(magc, END)
prev = None
for f in range(1, END + 1):                         # по кадрам: большой поворот без перескоков углов Эйлера
    wc.matrix = weapon_delta(f) @ WC_READY
    if prev is not None:
        wc.rotation_euler = wc.matrix_basis.to_euler('XYZ', prev)
    prev = wc.rotation_euler.copy()
    key(wc, f)
for frame in (1, END):
    root['Magazine latch press'] = 0.0
    root.keyframe_insert('["Magazine latch press"]', frame=frame)
    magob['Rounds remaining'] = 30
    magob.keyframe_insert('["Rounds remaining"]', frame=frame)
for name, frame in (('READY', 1), ('turn — count windows to eyes', 6), ('inspect', HOLD[0]), ('back', HOLD[1]), ('READY', 57)):
    sc.timeline_markers.new(name, frame=frame)
txt = bpy.data.texts.get('Клипы — как править') or bpy.data.texts.new('Клипы — как править')
txt.from_string(__doc__ + f'\nКлип: кадры 1–{END}, {FPS} к/с; участок показа {HOLD[0]}–{HOLD[1]}. Ключи — только Weapon_CTRL (крен, тангаж, '
                f'рыскание, подача к глазам); правка — ключи этой кости.')
sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('MAGS_CHECK_CLIP saved', OUT, 'hold', HOLD, flush=True)
