"""ИЗЛОМ-45 (wpn_smg_03): клипы рук и оружия — по образцу ВЕРАСа (tools/veras54_v13/clips/build_clips.py), на риге
tools/smg03/clips/rig.py (мастер FPS-рук v14 с исправленными кистями, ИЗЛОМ на костях SMG03_WeaponRig).

Хват — действие IZLOM45_Ready_v01 (кадр 1; правит владелец). Левая на магазине — хват магазина владельца с ВЕРАСа
(поза файла рига ВЕРАСа, _asset_src/smg03/anim/veras_ready.json), перенесённый на магазин Glock ИЗЛОМа (у пятки).
Магазин Glock не качают: защёлку жмут — он выходит вниз по своей оси; вставляют снизу по оси и досылают ладонью.
Наклон оружия — ключи Weapon_CTRL вокруг пистолетной рукоятки (цели кистей — дочерние), путь магазина и левой кисти в
хвате — в осях оружия, запечён по кадрам.

  tactical — магазин с патронами: левая к магазину, защёлка, вниз, «в подсумок», новый, вставить, дослать, к блоку.
  full     — магазин пуст, затвор на задержке: то же, затем большим пальцем левой — рычаг задержки, затвор вперёд.
  check    — проверка: магазин вынут к глазам задней стенкой (контрольные окна), держат (кадры check_hold), обратно.
  inspect  — осмотр: оружие поворачивают одним боком, другим, обратно; кисти — в хвате.
  jam      — задержка «гильза в окне»: затвор недозакрыт; левая откидывает рукоятку заряжания, отводит затвор — гильза
             вылетает, отпускает — затвор досылает патрон, рукоятку складывает.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b "<ИЗЛОМ45_Rig_v01.blend>" --python tools/smg03/clips/build_clips.py -- <клип> <выход.blend>
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
READY_JSON = ROOT / '_asset_src/smg03/anim/veras_ready.json'
ARGS = sys.argv[sys.argv.index('--') + 1:]
CLIP, OUT = ARGS[:2]
FPS = 30
TAG = CLIP.title()
sc = bpy.context.scene
sc.render.fps = FPS
for m in list(sc.timeline_markers):
    sc.timeline_markers.remove(m)
arms = bpy.data.objects['FPS_ArmsRig']
wr = bpy.data.objects['SMG03_WeaponRig']
root = bpy.data.objects['SMG03']
EYE = bpy.data.objects['FPS • Camera'].matrix_world.translation.copy()

# механика (tools/smg03/part_bolt.py, part_rig.py, part_controls.py)
BOLT_TRAVEL = 0.045
CH_TRAVEL = 0.0489
CH_SWING = 90.0
CH_TURN = 0.2
CATCH_DEG = 3.0
RELEASE_MM = 0.0013
MAG_A = math.radians(21.2)
MAG_MOUNT = Vector((-0.03546, 0.0, -0.0116))
GRIP_SRC = Vector((-0.2122, 0.0, -0.035))
JAM_OPEN = 0.3
# магазин Glock 21 на 13: от верха губок до низа донышка по оси ~134 мм
MAG_LEN = 0.134

LEFT = [b.name for b in arms.pose.bones if b.name.endswith('.L') and b.name.split('.')[0] in
        ('thumb', 'palm', 'f_index', 'f_middle', 'f_ring', 'f_pinky') and not b.name.endswith('_end')]
RIGHT = [b.name for b in arms.pose.bones if b.name.endswith('.R') and b.name.split('.')[0] in
         ('thumb', 'palm', 'f_index', 'f_middle', 'f_ring', 'f_pinky') and not b.name.endswith('_end')]
RIGHT_INDEX = ['f_index.01.R', 'f_index.02.R', 'f_index.03.R']
LEFT_THUMB = ['thumb.01.L', 'thumb.02.L', 'thumb.03.L']
ALL = [b.name for b in arms.pose.bones]
for pb in list(arms.pose.bones) + list(wr.pose.bones):
    pb.rotation_mode = 'XYZ'


def basis_of(names):
    return {n: arms.pose.bones[n].matrix_basis.copy() for n in names}


def apply(pose):
    for n, m in pose.items():
        arms.pose.bones[n].matrix_basis = m
    bpy.context.view_layer.update()


for a in (arms, wr):
    if a.animation_data:
        a.animation_data.action = None
ad = arms.animation_data or arms.animation_data_create()
ready_act = bpy.data.actions['IZLOM45_Ready_v01']
ad.action = ready_act
if ready_act.slots:
    ad.action_slot = ready_act.slots[0]
sc.frame_set(1)
bpy.context.view_layer.update()
READY = basis_of(ALL)
ad.action = None
apply(READY)
wc = arms.pose.bones['Weapon_CTRL']
ikL = arms.pose.bones['ik_hand.L']
ikR = arms.pose.bones['ik_hand.R']
IKL_READY = ikL.matrix.copy()
IKR_READY = ikR.matrix.copy()
WC_READY = wc.matrix.copy()
TW = root.matrix_world.copy()                 # оси исходника ИЗЛОМа → мир (в хвате)
RW = TW.to_3x3()
AW = arms.matrix_world.copy()
AWI = AW.inverted()


def W(p):
    return TW @ Vector(p)


GRIP = W(GRIP_SRC)                            # ось наклона оружия
MAG_TOP = W(MAG_MOUNT)
MAG_UP = (RW @ Vector((math.sin(MAG_A), 0.0, math.cos(MAG_A)))).normalized()
FWD = (RW @ Vector((1, 0, 0))).normalized()
LEFTV = (RW @ Vector((0, 1, 0))).normalized()

# ---- хват магазина левой: поза файла ВЕРАСа (пальцы) и кисть в осях магазина ВЕРАСа → магазин ИЗЛОМа
rd = json.loads(READY_JSON.read_text(encoding='utf-8'))
fp = rd['filepose']
MAGPOSE = {n: Matrix(fp['basis'][n]) for n in LEFT + ['forearm.L', 'hand.L'] if n in fp['basis']}


def frame(origin, down, fwd):
    d = down.normalized()
    f = (fwd - d * fwd.dot(d)).normalized()
    s = d.cross(f)
    m = Matrix((f, s, d)).transposed().to_4x4()
    m.translation = origin
    return m


mag_c = Matrix(fp['mag_control'])
top_v = mag_c.translation
down_v = (Vector(fp['mag_body_center']) - top_v).normalized()
F_v = frame(top_v, down_v, Vector((0, -1, 0)))
F_i = frame(MAG_TOP, -MAG_UP, FWD)
hand_v = Matrix(fp['world']['hand.L'])
k_v = Matrix(fp['world']['f_middle.01.L']).translation
rel = F_v.inverted() @ hand_v
grab = F_i @ rel
# у ВЕРАСа середина ладони ~10 см ниже верха магазина (длинный рожок); у Glock на 13 ладонь — у пятки
palm_v = hand_v.translation + (k_v - hand_v.translation) * 0.55
depth_v = (palm_v - top_v).dot(down_v)
grab.translation += -MAG_UP * (MAG_LEN + 0.012 - depth_v)
# короче ладонь — запястье подаётся к середине ладони
grab.translation += (F_i.to_3x3() @ (F_v.to_3x3().inverted() @ (k_v - hand_v.translation))) * 0.55 * 0.30
IKL_GRAB = AWI @ grab
print('CLIP хват магазина: глубина у ВЕРАСа, мм', round(depth_v * 1000, 1))

# рычаг задержки — куда ставят большой палец левой (исходник, м): задний конец рычага слева у шахты
CATCH_PT = W((-0.02275 - 0.012, 0.031, 0.01))
# рукоятка заряжания: ось откидывания и конец рукоятки в откинутом положении
CH_PIVOT = W((0.0095, 0.02365, 0.023))
CH_TIP = CH_PIVOT + LEFTV * 0.032


def about(p, rot):
    return Matrix.Translation(p) @ rot.to_4x4() @ Matrix.Translation(-p)


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def track(keys, f):
    if f <= keys[0][0]:
        return keys[0][1:]
    for a, b in zip(keys, keys[1:]):
        if a[0] <= f <= b[0]:
            k = smooth((f - a[0]) / (b[0] - a[0]))
            return tuple(x + (y - x) * k for x, y in zip(a[1:], b[1:]))
    return keys[-1][1:]


def pchip(keys, f):
    """Монотонный кубический сплайн по ключам (кадр, значения…) — как у ВЕРАСа: без перелёта на остановках."""
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


def lerp_m(a, b, t):
    la, ra, _ = a.decompose()
    lb, rb, _ = b.decompose()
    return Matrix.Translation(la.lerp(lb, t)) @ ra.slerp(rb, t).to_matrix().to_4x4()


REST = Matrix.Identity(4)

# ---------------------------------------------------------------- сценарии
# магазин: (кадр, вниз по оси м, крен°, наклон°, dx, dy, dz) — смещения в мире (x — влево, y — к камере, z — вверх)
POUCH = (0.16, 25, 35, 0.16, 0.20, -0.36)
SWAP = [(14, 0, 0, 0, 0, 0, 0), (17, 0, 0, 0, 0, 0, 0), (19, 0.012, 0, 0, 0, 0, 0), (23, 0.07, -4, 2, 0, 0, 0),
        (26, 0.16, -8, 6, 0.01, 0.0, -0.01), (31, 0.16, 12, 20, 0.08, 0.08, -0.15), (36, *POUCH), (40, *POUCH),
        (46, 0.13, -6, 8, 0.02, 0.03, -0.06), (50, 0.05, -3, 2, 0.0, 0.004, -0.008), (52, 0.03, 0, 0, 0, 0, 0),
        (55, -0.0015, 0, 0, 0, 0, 0), (56, 0.0, 0, 0, 0, 0, 0), (58, 0, 0, 0, 0, 0, 0)]
SWAP_FRAME = 38                              # «подмена» за кадром: в руке новый магазин
# оружие: (кадр, крен°, наклон°, поворот°, dx, dy, dz) вокруг пистолетной рукоятки
TILT = (-22, -6, 5, 0.04, 0.035, 0.05)
W_SWAP = [(1, 0, 0, 0, 0, 0, 0), (6, -10, -2, 1.5, 0.012, 0.01, 0.014), (12, *TILT), (22, -20, -5, 4.5, 0.036, 0.032, 0.046),
          (36, -16, -4, 3.5, 0.03, 0.028, 0.038), (48, *TILT), (54, -22.5, -6.5, 5, 0.04, 0.035, 0.054),
          (55, -23, -7, 5, 0.04, 0.035, 0.058), (58, *TILT)]
RELEASE_SWAP = [(1, 0), (15, 0), (17, 1), (21, 1), (23, 0)]
LFREE_SWAP = [(1, 'ready'), (4, ('between', 0.15, (0.0, 0.01, -0.02))), (9, ('between', 0.6, (0.02, 0.02, -0.05))),
              (13, ('near_grab', (0.0, 0.0, -0.02)))]

MAG_KEYS = [(1, 0, 0, 0, 0, 0, 0)]
CAM_W = [(1, 0)]
HOLD = None
LFINGER = [(1, 'R')]
LFREE = [(1, 'ready')]
LBACK = []
RIGHT_IDX = [(1, 0.0)]
RELEASE = [(1, 0)]
BOLT = [(1, 0.0)]
CATCH = [(1, 0.0)]
CH = [(1, 0.0)]
THUMB_L = [(1, 0.0)]
WEAPON = [(1, 0, 0, 0, 0, 0, 0)]
MARKERS = [('READY', 1)]
if CLIP in ('tactical', 'full'):
    MAG_KEYS = SWAP
    HOLD = (14, 58)
    LFINGER = [(1, 'R'), (4, 'R'), (9, 'O'), (12, 'P'), (14, 'M'), (57, 'M'), (60, 'P'), (63, 'O'), (68, 'R')]
    LFREE = LFREE_SWAP
    RELEASE = RELEASE_SWAP
    RIGHT_IDX = [(1, 0.0), (6, 0.7)]
    if CLIP == 'tactical':
        END = 72
        WEAPON = W_SWAP + [(62, -16, -4, 3, 0.03, 0.026, 0.036), (68, 1.5, 0.8, -0.4, -0.002, -0.001, -0.002),
                           (70, 0, 0, 0, 0, 0, 0), (END, 0, 0, 0, 0, 0, 0)]
        LBACK = [(60, ('near_grab', (0.0, 0.0, -0.025))), (64, ('back', 0.5, (0.02, 0.02, -0.04))), (68, 'ready')]
        RIGHT_IDX += [(64, 0.7), (69, 0.0)]
        MARKERS = [('READY', 1), ('LEFT to magazine', 4), ('release / drop', 17), ('to pouch', 26), ('new magazine', SWAP_FRAME),
                   ('insert', 50), ('seat — slap', 55), ('LEFT to front block', 59), ('READY', 70)]
    else:
        END = 86
        # затвор стоит сзади (задержка), после досылки магазина — большим пальцем левой на рычаг, затвор вперёд
        BOLT = [(1, 1.0), (66, 1.0), (67.5, 0.35), (68.5, 0.0), (END, 0.0)]
        CATCH = [(1, 1.0), (63, 1.0), (66, -1.0), (68, -1.0), (71, 0.0), (END, 0.0)]
        WEAPON = W_SWAP + [(62, -18, -5, 3.5, 0.034, 0.03, 0.04), (67, -18.5, -5.5, 3.5, 0.034, 0.03, 0.042),
                           (68, -17.5, -4.5, 3.5, 0.034, 0.03, 0.036), (76, 1.5, 0.8, -0.4, -0.002, -0.001, -0.002),
                           (80, 0, 0, 0, 0, 0, 0), (END, 0, 0, 0, 0, 0, 0)]
        LBACK = [(60, ('catch', 0.4)), (63, ('catch', 1.0)), (66, ('catch', 1.0)), (70, ('back', 0.5, (0.02, 0.02, -0.04))),
                 (76, 'ready')]
        LFINGER = [(1, 'R'), (4, 'R'), (9, 'O'), (12, 'P'), (14, 'M'), (57, 'M'), (60, 'P'), (66, 'P'), (70, 'O'), (76, 'R')]
        THUMB_L = [(1, 0.0), (60, 0.0), (63, 1.0), (66, 1.0), (69, 0.0)]
        RIGHT_IDX += [(72, 0.7), (77, 0.0)]
        MARKERS = [('READY (bolt held open)', 1), ('LEFT to magazine', 4), ('release / drop (empty)', 17),
                   ('new magazine', SWAP_FRAME), ('insert', 50), ('seat — slap', 55), ('LEFT thumb to bolt catch', 60),
                   ('press — bolt forward', 66), ('LEFT to front block', 70), ('READY', 80)]
    LFINGER.append((END, 'R'))
    LBACK.append((END, 'ready'))
    RIGHT_IDX.append((END, 0.0))
    RELEASE.append((END, 0))
elif CLIP == 'check':
    END = 100
    MAG_KEYS = [(14, 0, 0, 0, 0, 0, 0), (17, 0, 0, 0, 0, 0, 0), (19, 0.012, 0, 0, 0, 0, 0), (23, 0.07, -4, 2, 0, 0, 0),
                (27, 0.16, -6, 4, 0.0, 0.0, -0.01), (64, 0.16, -6, 4, 0.0, 0.0, -0.01), (70, 0.12, -6, 6, 0.01, 0.02, -0.04),
                (74, 0.05, -3, 2, 0.0, 0.004, -0.008), (76, 0.03, 0, 0, 0, 0, 0), (79, -0.0015, 0, 0, 0, 0, 0),
                (80, 0, 0, 0, 0, 0, 0), (82, 0, 0, 0, 0, 0, 0)]
    # вес «к глазам»: 0 — путь в осях оружия, 1 — магазин перед камерой задней стенкой (контрольные окна) к глазам
    CAM_W = [(1, 0), (24, 0), (38, 1), (56, 1), (70, 0), (END, 0)]
    HOLD = (14, 82)
    WEAPON = [(1, 0, 0, 0, 0, 0, 0), (6, -10, -2, 1.5, 0.012, 0.01, 0.014), (12, *TILT), (22, -20, -5, 4.5, 0.036, 0.032, 0.046),
              (34, -10, -2, 2, 0.01, 0.015, -0.015), (56, -9, -1.5, 2, 0.01, 0.015, -0.017), (68, -21, -6, 5, 0.04, 0.035, 0.05),
              (78, -22.5, -6.5, 5, 0.04, 0.035, 0.054), (79, -23, -7, 5, 0.04, 0.035, 0.058), (82, *TILT),
              (88, -16, -4, 3, 0.03, 0.026, 0.036), (95, 1.5, 0.8, -0.4, -0.002, -0.001, -0.002), (98, 0, 0, 0, 0, 0, 0),
              (END, 0, 0, 0, 0, 0, 0)]
    LFINGER = [(1, 'R'), (4, 'R'), (9, 'O'), (12, 'P'), (14, 'M'), (81, 'M'), (84, 'P'), (88, 'O'), (94, 'R'), (END, 'R')]
    LFREE = LFREE_SWAP
    LBACK = [(84, ('near_grab', (0.0, 0.0, -0.025))), (88, ('back', 0.5, (0.02, 0.02, -0.04))), (94, 'ready'), (END, 'ready')]
    RIGHT_IDX = [(1, 0.0), (6, 0.7), (90, 0.7), (96, 0.0), (END, 0.0)]
    RELEASE = RELEASE_SWAP + [(END, 0)]
    MARKERS = [('READY', 1), ('LEFT to magazine', 4), ('release / drop', 17), ('to eyes', 24), ('witness holes', 38),
               ('back to magwell', 57), ('insert', 74), ('seat — slap', 79), ('LEFT to front block', 83), ('READY', 98)]
elif CLIP == 'inspect':
    END = 120
    # оружие правым боком к глазам (окно выброса, клейма), потом левым (рукоятка заряжания, переводчик), обратно
    # к середине кадра (dx > 0 — влево от камеры) и ближе к глазам: в игре сцена стоит дальше и правее (hip_offset)
    WEAPON = [(1, 0, 0, 0, 0, 0, 0), (10, 8, -4, -6, 0.03, 0.02, 0.03), (24, 38, -10, -16, 0.10, 0.06, 0.08),
              (44, 40, -11, -18, 0.10, 0.065, 0.082), (58, 12, -6, 0, 0.08, 0.05, 0.06), (72, -34, -8, 18, 0.12, 0.06, 0.08),
              (92, -36, -9, 20, 0.122, 0.064, 0.082), (106, -8, -2, 4, 0.03, 0.015, 0.015), (114, 1.0, 0.5, -0.3, 0, 0, 0),
              (117, 0, 0, 0, 0, 0, 0), (END, 0, 0, 0, 0, 0, 0)]
    RIGHT_IDX = [(1, 0.0), (8, 0.7), (110, 0.7), (116, 0.0), (END, 0.0)]
    MARKERS = [('READY', 1), ('right side to eyes', 24), ('left side to eyes', 72), ('READY', 117)]
elif CLIP == 'jam':
    END = 62
    # оружие левым боком к глазам: рукоятка заряжания слева, окно с гильзой справа — видно сверху
    ROLL = (-24, -6, 10, 0.03, 0.04, 0.05)
    WEAPON = [(1, 0, 0, 0, 0, 0, 0), (6, -10, -3, 4, 0.012, 0.016, 0.02), (12, *ROLL), (26, -25, -6.5, 10, 0.03, 0.04, 0.052),
              (32, -26, -7, 10.5, 0.03, 0.045, 0.055), (34, -24, -6, 10, 0.03, 0.04, 0.05), (44, *ROLL),
              (52, -6, -1.5, 2, 0.006, 0.008, 0.01), (57, 1.0, 0.5, -0.3, 0, 0, 0), (60, 0, 0, 0, 0, 0, 0), (END, 0, 0, 0, 0, 0, 0)]
    # рукоятка: 0…CH_TURN — откинута, дальше — назад до упора (тянет затвор)
    CH = [(1, 0.0), (14, 0.0), (17, CH_TURN), (20, CH_TURN), (25, 1.0), (27, 1.0), (28.5, 0.3), (29.5, CH_TURN),
          (34, CH_TURN), (37, 0.0), (END, 0.0)]
    BOLT = [(1, JAM_OPEN), (21, JAM_OPEN)]       # дальше — от рукоятки (не меньше её хода)
    LFREE = [(1, 'ready'), (5, ('between', 0.0, (0.0, 0.0, 0.0))), (9, ('handle', 0.0, (0.0, 0.0, 0.03))),
             (13, ('handle', 0.0, (0.0, 0.0, 0.0)))]
    LBACK = [(37, ('handle', 0.0, (0.0, 0.0, 0.0))), (41, ('handle', 0.0, (0.01, 0.02, 0.04))), (48, 'ready'), (END, 'ready')]
    LFINGER = [(1, 'R'), (5, 'O'), (11, 'P'), (14, 'K'), (36, 'K'), (39, 'O'), (46, 'R'), (END, 'R')]
    RIGHT_IDX = [(1, 0.0), (5, 0.7), (52, 0.7), (58, 0.0), (END, 0.0)]
    MARKERS = [('JAM: case in port, bolt short', 1), ('LEFT to charging handle', 5), ('unfold', 14), ('pull', 20),
               ('case out', 24), ('release — bolt forward', 27), ('fold', 34), ('LEFT to front block', 38), ('READY', 57)]
else:
    raise SystemExit('клип: tactical | full | check | inspect | jam')
sc.frame_start, sc.frame_end = 1, END


def mag_weapon(f):
    drop, rl, pt, x, y, z = pchip(MAG_KEYS, f)
    base = MAG_TOP - MAG_UP * drop
    rot = Euler((math.radians(pt), math.radians(rl), 0.0), 'XYZ').to_matrix()
    return Matrix.Translation(Vector((x, y, z))) @ about(base, rot) @ Matrix.Translation(-MAG_UP * drop)


def weapon_delta(f):
    r, p, yw, x, y, z = pchip(WEAPON, f)
    rot = Euler((math.radians(p), math.radians(r), math.radians(yw)), 'XYZ').to_matrix()
    return Matrix.Translation(Vector((x, y, z))) @ about(GRIP, rot)


MAG_MID = MAG_TOP - MAG_UP * (MAG_LEN * 0.5)


def mag_camera(f):
    """Магазин перед глазами задней стенкой (контрольные окна) к камере, верх чуть от неё; лёгкое покачивание."""
    t = f / FPS
    target = EYE + Vector((0.03, -0.34, -0.07)) + Vector((0.004 * math.sin(t * 2.1), 0.0, 0.003 * math.sin(t * 1.7)))
    # ось магазина — вертикально (наклон 21° снят), задняя стенка (−X исходника = +Y мира) — к камере, чуть повернуть
    # сначала наклон оси снят (поворот на −21.2° вокруг оси «влево» мира), потом верх чуть от камеры и разворот
    rot = (Euler((math.radians(14 + 2.5 * math.sin(t * 1.3)), 0, math.radians(-12 + 5 * math.sin(t * 1.1))), 'XYZ').to_matrix()
           @ Matrix.Rotation(-MAG_A, 3, LEFTV))
    world = Matrix.Translation(target) @ rot.to_4x4() @ Matrix.Translation(-MAG_MID)
    return weapon_delta(f).inverted() @ world


def mag_delta(f):
    w = min(max(pchip(CAM_W, f)[0], 0.0), 1.0)
    a = mag_weapon(f)
    if w <= 0.0:
        return a
    return lerp_m(a, mag_camera(f), w)


# ---------------------------------------------------------------- ключи
arm_act = bpy.data.actions.new(f'IZLOM45_{TAG}_Arms_v01')
ad.action = arm_act
wad = wr.animation_data or wr.animation_data_create()
w_act = bpy.data.actions.new(f'IZLOM45_{TAG}_Weapon_v01')
wad.action = w_act
for a in (arm_act, w_act):
    a.use_fake_user = True


def key(pb, frame, loc=True, rot=True):
    if loc:
        pb.keyframe_insert('location', frame=frame)
    if rot:
        pb.keyframe_insert('rotation_euler', frame=frame)


class Keyer:
    """Ключи кости по матрице в пространстве арматуры с непрерывными углами Эйлера."""

    def __init__(self, pb):
        self.pb, self.prev = pb, None

    def at(self, frame, m_arm):
        self.pb.matrix = m_arm
        if self.prev is not None:
            self.pb.rotation_euler = self.pb.matrix_basis.to_euler('XYZ', self.prev)
        self.prev = self.pb.rotation_euler.copy()
        key(self.pb, frame)


def finger_pose(kind, n):
    if kind == 'R':
        return READY[n]
    if kind == 'M':
        return MAGPOSE.get(n, READY[n])
    if kind == 'O':
        return lerp_m(lerp_m(READY[n], MAGPOSE.get(n, READY[n]), 0.5), REST, 0.55)
    if kind == 'P':
        return lerp_m(MAGPOSE.get(n, READY[n]), REST, 0.25)
    if kind == 'K':
        # щепоть на рукоятке заряжания: пальцы полусогнуты, большой — к указательному
        return lerp_m(MAGPOSE.get(n, READY[n]), READY[n], 0.35)
    raise ValueError(kind)


# кончик большого пальца левой в хвате магазина (мир) — к нему ведут кисть на рычаг задержки
apply({**READY, **MAGPOSE})
ikL.matrix = IKL_GRAB
bpy.context.view_layer.update()
GRAB_W = (AW @ ikL.matrix).copy()
THUMB_TIP = AW @ arms.pose.bones['thumb.03.L'].tail
apply(READY)
for n in ALL:
    key(arms.pose.bones[n], 1)
    key(arms.pose.bones[n], END)

WRIST = {'R': 0.0, 'O': 0.5, 'P': 1.0, 'M': 1.0, 'K': 0.6}
for frame, kind in LFINGER:
    for n in LEFT:
        arms.pose.bones[n].matrix_basis = finger_pose(kind, n)
        key(arms.pose.bones[n], frame)
    for n in ('forearm.L', 'hand.L'):
        arms.pose.bones[n].matrix_basis = lerp_m(READY[n], MAGPOSE.get(n, READY[n]), WRIST[kind])
        key(arms.pose.bones[n], frame)
# большой палец левой — на рычаг задержки: разогнут вперёд-вверх
if CLIP == 'full':
    for frame, k in THUMB_L:
        for n in LEFT_THUMB:
            base = finger_pose('P', n)
            arms.pose.bones[n].matrix_basis = lerp_m(base, REST, k)
            key(arms.pose.bones[n], frame)
for frame, k in RIGHT_IDX:
    for n in RIGHT_INDEX:
        arms.pose.bones[n].matrix_basis = lerp_m(READY[n], REST, k)
        key(arms.pose.bones[n], frame)


def free_target(spec, grab, ready):
    if spec == 'ready':
        return ready
    kind = spec[0]
    if kind == 'between':
        m = lerp_m(ready, grab, spec[1])
        m.translation += AWI.to_3x3() @ Vector(spec[2])
        return m
    if kind == 'back':
        m = lerp_m(grab, ready, spec[1])
        m.translation += AWI.to_3x3() @ Vector(spec[2])
        return m
    if kind == 'near_grab':
        return Matrix.Translation(AWI.to_3x3() @ Vector(spec[1])) @ grab
    if kind == 'catch':
        # кисть с магазина вверх по шахте: кончик большого пальца — на задний конец рычага задержки
        m_w = GRAB_W.copy()
        m_w.translation = GRAB_W.translation.lerp(GRAB_W.translation + (CATCH_PT - THUMB_TIP), spec[1])
        return AWI @ m_w
    if kind == 'handle':
        # кисть к концу рукоятки заряжания (откинутой): ладонь слева, пальцы обхватывают конец
        m = ready.copy()
        hand_w = AW @ ready
        knuckle = hand_w.to_3x3() @ Vector((0, 0.11, 0))
        m_w = Matrix.Translation(CH_TIP - knuckle * 0.95 + LEFTV * 0.025 - Vector((0, 0, 0.01)) + Vector(spec[2])) @ hand_w.to_3x3().to_4x4()
        return AWI @ m_w
    raise ValueError(spec)


kl = Keyer(ikL)
for frame, spec in LFREE:
    kl.at(frame, free_target(spec, IKL_GRAB, IKL_READY))
for f in (range(HOLD[0], HOLD[1] + 1) if HOLD else []):
    kl.at(f, AWI @ mag_delta(f) @ AW @ IKL_GRAB)
for frame, spec in LBACK:
    kl.at(frame, free_target(spec, IKL_GRAB, IKL_READY))

# магазин: путь в осях оружия (как у ВЕРАСа: WR_W⁻¹ @ путь @ покой)
magc = wr.pose.bones['Magazine_Control']
WR_W = wr.matrix_world.copy()
MAG_REST = WR_W @ magc.matrix
km = Keyer(magc)
for f in ([1, HOLD[0] - 1] + list(range(HOLD[0], HOLD[1] + 1)) + [HOLD[1] + 1, END] if HOLD else [1, END]):
    world = mag_delta(f) @ MAG_REST if HOLD and HOLD[0] <= f <= HOLD[1] else MAG_REST
    km.at(f, WR_W.inverted() @ world)

# защёлка магазина: лопатки внутрь; рычаг задержки; затвор; рукоятка заряжания (кости — по своим осям)
for name in ('MagReleaseL', 'MagReleaseR'):
    pb = wr.pose.bones[name]
    for frame, v in RELEASE:
        pb.location = (0.0, -RELEASE_MM * v, 0.0)
        key(pb, frame, rot=False)
pb = wr.pose.bones['BoltCatch']
for frame, v in CATCH:
    pb.rotation_euler = (0.0, math.radians(CATCH_DEG) * v, 0.0)
    key(pb, frame, loc=False)
ch_pb = wr.pose.bones['ChargingHandle']
sl_pb = wr.pose.bones['ChargingSlider']
bolt_pb = wr.pose.bones['Bolt']
frames = sorted({k[0] for k in CH} | {k[0] for k in BOLT} | ({f for f in range(14, 40)} if CLIP == 'jam' else set()) | {1, END})
for f in frames:
    ch = track(CH, f)[0]
    ch_t = max(0.0, (ch - CH_TURN) / (1.0 - CH_TURN))
    slide = ch_t * CH_TRAVEL
    bolt = track(BOLT, f)[0] if f <= BOLT[-1][0] or CLIP != 'jam' else 0.0
    if CLIP == 'jam':
        # затвор: до отвода стоит недозакрытым, рукоятка выбирает зазор и тянет его; отпустил — вперёд до конца
        drawn = max(0.0, (slide - (CH_TRAVEL - BOLT_TRAVEL)) / BOLT_TRAVEL)
        bolt = max(drawn, JAM_OPEN if f < 27 else 0.0)
    sl_pb.location = (0.0, -slide, 0.0)
    key(sl_pb, f, rot=False)
    ch_pb.rotation_euler = (0.0, math.radians(CH_SWING) * min(1.0, ch / CH_TURN), 0.0)
    key(ch_pb, f, loc=False)
    bolt_pb.location = (0.0, -BOLT_TRAVEL * bolt, 0.0)
    key(bolt_pb, f, rot=False)

# гильза задержки: стоит в окне, пока затвор её не прошёл; дальше вылетает вправо-вверх и падает, кувыркаясь
if CLIP == 'jam' and 'JamCase' in wr.pose.bones:
    case_pb = wr.pose.bones['JamCase']
    kc = Keyer(case_pb)
    rest_arm = case_pb.matrix.copy()
    free = 23
    to_arm = wr.matrix_world.inverted().to_3x3()
    v0 = -LEFTV * 0.9 + Vector((0.0, 0.15, 0.7))
    kc.at(1, rest_arm)
    kc.at(free, rest_arm)
    for f in range(free + 1, min(free + 15, END) + 1):
        t = (f - free) / FPS
        off = to_arm @ (v0 * t + Vector((0.0, 0.0, -4.9 * t * t)))
        spin = Euler((t * 14.0, t * 9.0, t * 5.0), 'XYZ').to_matrix().to_4x4()
        kc.at(f, Matrix.Translation(rest_arm.translation + off) @ rest_arm.to_3x3().to_4x4() @ spin)

kw = Keyer(wc)
for k in WEAPON:
    kw.at(k[0], AWI @ weapon_delta(k[0]) @ AW @ WC_READY)

# ---------------------------------------------------------------- пальцы: суставы в пределах, ключи в осях сустава
# Палец гнётся вокруг своей оси (X кости) и разводится только у основания, без кручения; концевая — вслед за средней
# (tools/anim_from_video/hand_solver.py, опыт 2026-11-06). Ключи — в порядке Эйлера YZX (= сгиб · развод · кручение):
# между ключами палец идёт прямо по сгибу, а не через «равный поворот» в XYZ — так в переходах ломались суставы.
# Основание большого — как есть (у рига свой покой).
sys.path.insert(0, str(ROOT / 'tools/anim_from_video'))
import hand_solver as hs  # noqa: E402


def arm_fcurves():
    return [fc for layer in arm_act.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]


FINGER_BONES = {(s, f): [f'{f}.{j:02d}.{s}' for j in (1, 2, 3)] for s in ('L', 'R') for f in hs.FINGERS}
FINGER_NAMES = {n for ns in FINGER_BONES.values() for n in ns}
key_frames = {}
for fc in arm_fcurves():
    if fc.data_path.endswith('.rotation_euler'):
        key_frames.setdefault(fc.data_path.split('"')[1], set()).update(int(round(k.co.x)) for k in fc.keyframe_points)
finger_keys = {}
for (s, f), names in FINGER_BONES.items():
    for fr in sorted(set().union(*(key_frames.get(n, set()) for n in names))):
        sc.frame_set(fr)
        finger_keys[(s, f, fr)] = hs.anatomical(hs.read(arms, s, f), f)
for fc in arm_fcurves():
    if fc.data_path.endswith('.rotation_euler') and fc.data_path.split('"')[1] in FINGER_NAMES:
        fc.keyframe_points.clear()
for (s, f, fr), vals in finger_keys.items():
    hs.write(arms, s, f, vals)
    for n in FINGER_BONES[(s, f)]:
        arms.pose.bones[n].keyframe_insert('rotation_euler', frame=fr)


def fcurves(act):
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


for act in (arm_act, w_act):
    for fc in fcurves(act):
        dense = len(fc.keyframe_points) > 12
        for kp in fc.keyframe_points:
            if dense:
                kp.interpolation = 'LINEAR'
            else:
                kp.interpolation = 'BEZIER'
                kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
for name, frame in MARKERS:
    sc.timeline_markers.new(name, frame=frame)

worst = {'L': 0.0, 'R': 0.0}
for f in range(1, END + 1):
    sc.frame_set(f)
    for s in ('L', 'R'):
        d = (arms.pose.bones[f'hand.{s}'].head - arms.pose.bones[f'ik_hand.{s}'].head).length
        worst[s] = max(worst[s], d)
print('CLIP', CLIP, 'кадров', END, 'IK не дотянулась, мм: L', round(worst['L'] * 1000, 1), 'R', round(worst['R'] * 1000, 1))
txt = bpy.data.texts.get('Клипы — как править') or bpy.data.texts.new('Клипы — как править')
txt.from_string(__doc__ + f"""
Клип {CLIP}: кадры 1–{END}, {FPS} к/с. Действия: {arm_act.name} (FPS_ArmsRig), {w_act.name} (SMG03_WeaponRig). Маркеры — фазы.
Хват (кадр 1) — действие IZLOM45_Ready_v01: правите его — клипы пересобираются скриптом.""")
sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('CLIP saved', OUT)
