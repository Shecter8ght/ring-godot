"""ВЕРАС-54: клипы рук и оружия — тактическая перезарядка, проверка магазина, полная перезарядка.

v13 (2026-10-19): основа — риг v13 (tools/veras54_v13/game_rig.py: игровая сетка v13, ход рамы 100,6 мм); рукоятка затвора —
метка ChargingHandle (крючок v13), гильза задержки — в окне выброса v13 (rig_common.JAM_*). Позы владельца — прежние файлы
библиотеки (DATA: grip_<рукоятка>_pose.json, check_grip_pose.json). Сценарии и кадры не менялись.

Позы — из файла VERAS54_Charging_Hook_v01.blend: боевой хват (action VERAS54_Grip_Manual_v02, владелец),
хват магазина левой (обхват по касанию поверх позы владельца), правая на рукоятке затвора (крюк указательным).
Магазин в руке: путь в осях оружия (качок у переднего зацепа) или к глазам (проверка), кисть следует за
ним с тем же смещением, что в хвате. Наклон оружия — ключи Weapon_CTRL вокруг рукоятки (IK-кисти — дочерние).
Защёлка, затвор, патроны — ключи свойств рига (Magazine latch press, Bolt pull, Rounds remaining).
Путь кистей и магазина в хвате запечён по кадрам (экспорт в glTF без ограничений); остальное — редкие ключи.

v02 (2026-10-10): рукоятка под цевьём — третий аргумент varn_v1 | varn_v2: «руки на оружии» для левой —
хват рукоятки (grip_<id>_pose.json из grip_pose.py), рукоятка стоит на планке; левая сначала отпускает
рукоятку (отходит от неё с раскрытыми пальцами), а возвращаясь — подходит сбоку и смыкает пальцы.
Клипы fast / fastfull — быстрая перезарядка (двойное R): левая сразу идёт за новым магазином, новым
выбивает старый (тот падает на землю — кость SpareMag), вставляет; fastfull — то же и досылка затвором
(магазин был пуст). Основной магазин (Magazine_Control) с кадра FAST_K — новый, в руке.
Клип jam — задержка «гильза не вышла»: затвор недозакрыт, гильза зажата в окне; правая отводит затвор,
гильза выпадает, затвор досылает патрон. Имена действий: VERAS54_<Клип>[_<рукоятка>]_<что>_v01.

blender --background ".../Игровая версия/Риг v13/VERAS54_Rig_v13.blend" --python tools/veras54_v13/clips/build_clips.py -- <tactical|check|full|jam|fast|fastfull> <выход .blend> [varn_v1|varn_v2]
"""
import math
import sys

import json
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

HERE = Path(__file__).resolve().parent
# позы владельца (хват рукояток ВАРН, хват магазина для проверки) — в библиотеке, не меняются
DATA = Path("E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия/Клипы v02 (Claude)")
sys.path.insert(0, str(HERE))
import rig_common as rc  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:]
CLIP, OUT = ARGS[:2]
GID = ARGS[2] if len(ARGS) > 2 and ARGS[2] in rc.GRIPS else ""
TAG = CLIP.title() + ("_" + GID if GID else "")
FAST = CLIP in ("fast", "fastfull")
# кадр, на котором рука у подсумка берёт новый магазин (основной магазин «переезжает» в руку за кадром,
# в оружии с этого кадра виден запасной — старый)
FAST_K = 13
FPS = 30
sc = bpy.context.scene
sc.render.fps = FPS
for m in list(sc.timeline_markers):
    sc.timeline_markers.remove(m)
arms = bpy.data.objects["FPS_ArmsRig"]
wr = bpy.data.objects["VERAS54_WeaponRig"]
root = bpy.data.objects["VERAS54"]
magob = bpy.data.objects["Magazine"]

# глушитель — отдельный ассет, в этих клипах не нужен (висел в воздухе на месте хранения)
for c in bpy.data.collections:
    if "Suppressor" in c.name:
        c.hide_viewport = True
        c.hide_render = True
for ob in bpy.data.objects:
    if ob.name.startswith("chk_"):
        bpy.data.objects.remove(ob, do_unlink=True)

LEFT = [b.name for b in arms.pose.bones if b.name.endswith(".L") and b.name.split(".")[0] in
        ("thumb", "palm", "f_index", "f_middle", "f_ring", "f_pinky") and not b.name.endswith("_end")]
RIGHT = [b.name for b in arms.pose.bones if b.name.endswith(".R") and b.name.split(".")[0] in
         ("thumb", "palm", "f_index", "f_middle", "f_ring", "f_pinky") and not b.name.endswith("_end")]
RIGHT_INDEX = ["f_index.01.R", "f_index.02.R", "f_index.03.R"]
ALL = [b.name for b in arms.pose.bones]
for pb in list(arms.pose.bones) + list(wr.pose.bones):
    pb.rotation_mode = "XYZ"

# ---------------------------------------------------------------- позы

def basis_of(names):
    return {n: arms.pose.bones[n].matrix_basis.copy() for n in names}


for a in (arms, wr, root, magob):
    if a.animation_data:
        a.animation_data.action = None
FILEPOSE = basis_of(ALL)          # левая — хват магазина, правая — крюк на затворе
ad = arms.animation_data or arms.animation_data_create()
ready_act = bpy.data.actions["VERAS54_Grip_Manual_v02"]
ad.action = ready_act
if ready_act.slots:
    ad.action_slot = ready_act.slots[0]
sc.frame_set(1)
bpy.context.view_layer.update()
READY = basis_of(ALL)
ad.action = None
if GID:
    # левая — на рукоятке под цевьём; рукоятка — на планке
    for n, v in json.loads((DATA / f"grip_{GID}_pose.json").read_text(encoding="utf-8")).items():
        READY[n] = Matrix(v)
    rc.add_grip(GID)


def apply(pose):
    for n, m in pose.items():
        arms.pose.bones[n].matrix_basis = m
    bpy.context.view_layer.update()


wc = arms.pose.bones["Weapon_CTRL"]
ikL = arms.pose.bones["ik_hand.L"]
ikR = arms.pose.bones["ik_hand.R"]
apply(FILEPOSE)
IKL_GRAB = ikL.matrix.copy()
IKR_HOOK = ikR.matrix.copy()
apply(READY)
IKL_READY = ikL.matrix.copy()
IKR_READY = ikR.matrix.copy()
WC_READY = wc.matrix.copy()
MAGPOSE = {n: FILEPOSE[n] for n in LEFT + ["forearm.L", "hand.L"]}
HOOK = {n: FILEPOSE[n] for n in RIGHT + ["forearm.R", "hand.R"]}

# хват для проверки (кисть у пятки магазина, прорези открыты) — из check_grip.py
CHECKPOSE = {}
IKL_CHECK = IKL_GRAB
if CLIP == "check":
    raw = json.loads((DATA / "check_grip_pose.json").read_text(encoding="utf-8"))
    CHECKPOSE = {n: Matrix(v) for n, v in raw.items()}
    apply(READY)
    ikL.matrix_basis = CHECKPOSE["ik_hand.L"]
    bpy.context.view_layer.update()
    IKL_CHECK = ikL.matrix.copy()
    apply(READY)

magc = wr.pose.bones["Magazine_Control"]
WR_W = wr.matrix_world.copy()
MAG_REST = WR_W @ magc.matrix

# куда идёт рукоятка затвора при «Bolt pull» = 1 (в мире при боевой позе)
handle = bpy.data.objects["ChargingHandle"]          # середина рукоятки-крючка v13 (метка на кости Bolt)
h0 = handle.matrix_world.translation.copy()
root["Bolt pull"] = 1.0
root.update_tag()
bpy.context.view_layer.update()
BOLT_VEC = handle.matrix_world.translation - h0
root["Bolt pull"] = 0.0
root.update_tag()
bpy.context.view_layer.update()
print("CLIP ход рукоятки, мм", tuple(round(v * 1000, 1) for v in BOLT_VEC))

dg = bpy.context.evaluated_depsgraph_get()
mb = bpy.data.objects["Magazine_Body"].evaluated_get(dg)
MAG_C = sum((mb.matrix_world @ Vector(v) for v in mb.bound_box), Vector()) / 8

PIVOT = Vector((-0.14, -0.463, 1.675))      # передний зацеп магазина
GRIP = Vector((-0.14, -0.323, 1.635))       # рукоятка — ось наклона оружия
EYE = bpy.data.objects["FPS • Camera"].matrix_world.translation.copy()


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
    """Монотонный кубический сплайн по ключам (кадр, значения…): скорость непрерывна через ключи,
    на остановках (равные соседние значения) — без перелёта. Для траекторий магазина, оружия, весов."""
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

# общий кусок: подход левой, качок, «подсумок», новый магазин, досылка (кадры 1–60)
MAG_SWAP = [
    (16, 0, 0, 0, 0, 0), (18, 0, 0, 0, 0, 0), (22, -24, 0, 0, 0, 0), (25, -30, 0, 0, -0.012, -0.05),
    (30, -25, 15, 0.06, 0.06, -0.2), (36, -10, 35, 0.17, 0.19, -0.4), (42, -10, 35, 0.17, 0.19, -0.4),
    (48, -28, 10, 0.02, -0.01, -0.12), (52, -26, 0, 0, -0.006, -0.012), (54, -22, 0, 0, 0, 0),
    (57, 0.8, 0, 0, 0, 0), (58, 0, 0, 0, 0, 0), (60, 0, 0, 0, 0, 0),
]
TILT = (-34, -9, 6, 0.06, 0.05, 0.07)
W_SWAP = [
    (1, 0, 0, 0, 0, 0, 0), (6, -14, -3, 1.5, 0.018, 0.014, 0.02), (12, -37, -10, 6.5, 0.062, 0.052, 0.074),
    (15, *TILT), (22, -33, -9, 6, 0.06, 0.05, 0.064), (26, *TILT), (40, -29, -6, 5, 0.052, 0.045, 0.062),
    (50, -35, -10, 6, 0.06, 0.05, 0.07), (56, -34, -9.5, 6, 0.06, 0.05, 0.068),
    (57, -34.5, -10.2, 6, 0.06, 0.05, 0.078), (60, *TILT),
]
LATCH_SWAP = [(1, 0), (15, 0), (17, 1), (21, 1), (23, 0), (55.5, 0), (56.5, 0.7), (57.5, 0)]

if CLIP == "tactical":
    END = 79
    MAG_KEYS = MAG_SWAP
    CAM_W = [(1, 0)]
    HOLD = (16, 60)
    WEAPON = W_SWAP + [(64, -29, -7, 5, 0.05, 0.042, 0.058), (72, 2.5, 1.2, -0.6, -0.003, -0.002, -0.004),
                       (76, 0, 0, 0, 0, 0, 0), (END, 0, 0, 0, 0, 0, 0)]
    LFINGER = [(1, "R"), (5, "R"), (10, "O"), (15, "P"), (17, "M"), (59, "M"), (62, "P"), (66, "O"), (72, "R"), (END, "R")]
    LFREE = [(1, "ready"), (5, ("between", 0.12, (0.01, 0.005, -0.02))), (10, ("between", 0.62, (0.035, 0.02, -0.06))),
             (14, ("near_grab", (0.012, 0.0, -0.025)))]
    LBACK = [(63, ("near_grab", (0.015, 0.0, -0.03))), (67, ("back", 0.5, (0.03, 0.02, -0.05))), (72, "ready"), (END, "ready")]
    RIGHT_IDX = [(1, 0.0), (6, 0.7), (68, 0.7), (74, 0.0), (END, 0.0)]
    LATCH = LATCH_SWAP + [(END, 0)]
    ROUNDS = [(1, 30)]
    MARKERS = [("READY", 1), ("LEFT to magazine", 5), ("latch / rock out", 17), ("to pouch", 26), ("new magazine", 42),
               ("hook front lug", 52), ("seat — click", 57), ("LEFT to handguard", 61), ("READY", 76)]
elif CLIP == "check":
    END = 104
    MAG_KEYS = [(16, 0, 0, 0, 0, 0), (18, 0, 0, 0, 0, 0), (22, -22, 0, 0, 0, 0), (27, -30, 0, 0, -0.012, -0.05),
                (64, -30, 0, 0, -0.012, -0.05), (73, -28, 0, 0.0, -0.01, -0.1), (76.5, -26, 0, 0, -0.006, -0.012),
                (78, -22, 0, 0, 0, 0), (81, 0.8, 0, 0, 0, 0), (82, 0, 0, 0, 0, 0), (84, 0, 0, 0, 0, 0)]
    # вес «к глазам»: 0 — путь в осях оружия, 1 — магазин перед камерой боком (прорези к глазам)
    CAM_W = [(1, 0), (23, 0), (39, 1), (57, 1), (74, 0), (END, 0)]
    HOLD = (16, 84)
    WEAPON = [(1, 0, 0, 0, 0, 0, 0), (6, -14, -3, 1.5, 0.018, 0.014, 0.02), (12, -36, -9.6, 6.3, 0.061, 0.051, 0.072),
              (15, *TILT), (22, -33, -9, 6, 0.06, 0.05, 0.064), (36, -16, -2, 2, 0.01, 0.02, -0.02),
              (56, -15, -1.5, 2, 0.01, 0.02, -0.022), (70, -35, -10, 6, 0.06, 0.05, 0.07),
              (80, -34, -9.5, 6, 0.06, 0.05, 0.068), (81, -34.5, -10.2, 6, 0.06, 0.05, 0.078), (84, *TILT),
              (89, -29, -7, 5, 0.05, 0.042, 0.058), (97, 2.5, 1.2, -0.6, -0.003, -0.002, -0.004),
              (101, 0, 0, 0, 0, 0, 0), (END, 0, 0, 0, 0, 0, 0)]
    LFINGER = [(1, "R"), (5, "R"), (10, "O"), (15, "P"), (17, "M"), (28, "M"), (33, "P"), (39, "C"), (58, "C"), (63, "P"),
               (68, "M"), (83, "M"), (86, "P"), (90, "O"), (96, "R"), (END, "R")]
    # перехват: 0 — обычный хват, 1 — ниже по магазину (верхние прорези открыты)
    REGRIP = [(1, 0), (28, 0), (39, 1), (58, 1), (68, 0), (END, 0)]
    LFREE = [(1, "ready"), (5, ("between", 0.12, (0.01, 0.005, -0.02))), (10, ("between", 0.62, (0.035, 0.02, -0.06))),
             (14, ("near_grab", (0.012, 0.0, -0.025)))]
    LBACK = [(87, ("near_grab", (0.015, 0.0, -0.03))), (91, ("back", 0.5, (0.03, 0.02, -0.05))), (96, "ready"), (END, "ready")]
    RIGHT_IDX = [(1, 0.0), (6, 0.7), (93, 0.7), (99, 0.0), (END, 0.0)]
    LATCH = [(1, 0), (15, 0), (17, 1), (21, 1), (23, 0), (79.5, 0), (80.5, 0.7), (81.5, 0), (END, 0)]
    ROUNDS = [(1, 12)]
    MARKERS = [("READY", 1), ("LEFT to magazine", 5), ("latch / rock out", 17), ("to eyes + regrip", 24),
               ("inspect slots", 39), ("back to magwell", 58), ("hook front lug", 76), ("seat — click", 81),
               ("LEFT to handguard", 85), ("READY", 101)]
elif CLIP == "full":
    END = 114
    MAG_KEYS = MAG_SWAP
    CAM_W = [(1, 0)]
    HOLD = (16, 60)
    # оружие на другой бок — правая сторона (рукоятка затвора) к глазам
    ROLL_R = (24, -4, -3, 0.0, 0.03, 0.05)
    WEAPON = W_SWAP + [(64, -20, -5, 3, 0.04, 0.035, 0.05), (70, 24, -4, -3, 0.0, 0.03, 0.05),
                       (73, 26.5, -4.5, -3, 0.0, 0.03, 0.052), (76, *ROLL_R), (81, *ROLL_R),
                       (86, 23, -5, -3, 0.0, 0.036, 0.05), (87, 23, -5, -3, 0.0, 0.036, 0.05),
                       (89, 25, -2.5, -3, 0.0, 0.022, 0.052), (93, *ROLL_R), (99, 18, -3, -2, 0.0, 0.022, 0.038),
                       (106, -2, 0.8, 0.4, 0.0, -0.002, -0.003), (110, 0, 0, 0, 0, 0, 0), (END, 0, 0, 0, 0, 0, 0)]
    LFINGER = [(1, "R"), (5, "R"), (10, "O"), (15, "P"), (17, "M"), (59, "M"), (62, "P"), (66, "O"), (72, "R"), (END, "R")]
    LFREE = [(1, "ready"), (5, ("between", 0.12, (0.01, 0.005, -0.02))), (10, ("between", 0.62, (0.035, 0.02, -0.06))),
             (14, ("near_grab", (0.012, 0.0, -0.025)))]
    LBACK = [(63, ("near_grab", (0.015, 0.0, -0.03))), (67, ("back", 0.5, (0.03, 0.02, -0.05))), (72, "ready"), (END, "ready")]
    RIGHT_IDX = [(1, 0.0), (6, 0.7), (70, 0.7)]
    LATCH = LATCH_SWAP + [(END, 0)]
    ROUNDS = [(1, 0), (41, 0), (42, 30)]           # вынут пустой, вставлен полный (подмена за кадром)
    # затвор: доля хода (0 — закрыт, 1 — 100,6 мм); отвод рукой, у упора — пауза, отпустил — удар вперёд
    BOLT = [(1, 0.0), (81, 0.0), (83, 0.5), (85.5, 0.97), (86.5, 1.0), (87, 1.0), (89, 0.0), (END, 0.0)]
    MARKERS = [("READY", 1), ("LEFT to magazine", 5), ("latch / rock out", 17), ("to pouch (empty)", 26),
               ("new magazine (full)", 42), ("seat — click", 57), ("LEFT to handguard / roll right", 61),
               ("RIGHT to charging handle", 72), ("pull", 81), ("release — bolt slams", 87), ("RIGHT to grip", 90),
               ("READY", 110)]
elif FAST:
    # новый магазин: от подсумка — под старый сзади-снизу — удар вперёд (старый вылетает) — зацеп — досылка
    MAG_KEYS = [(FAST_K, -10, 35, 0.17, 0.19, -0.4), (FAST_K + 2, -12, 32, 0.16, 0.18, -0.36),
                (22, -33, 10, 0.03, 0.05, -0.085), (24, -34, 6, 0.016, 0.04, -0.07), (26.5, -31, 1, 0.004, 0.004, -0.05),
                (30, -27, 0, 0, -0.006, -0.014), (32, -22, 0, 0, 0, 0), (35, 0.8, 0, 0, 0, 0), (36, 0, 0, 0, 0, 0),
                (38, 0, 0, 0, 0, 0)]
    # старый магазин: защёлку сбивает новый, качок вперёд у зацепа, дальше падает сам
    OLD_KEYS = [(1, 0, 0, 0, 0, 0), (24, 0, 0, 0, 0, 0), (25.5, -9, 0, 0, 0, 0), (27, -25, 0, 0, -0.004, -0.012)]
    OLD_FREE = 27
    CAM_W = [(1, 0)]
    HOLD = (FAST_K, 38)
    W_FAST = [(1, 0, 0, 0, 0, 0, 0), (5, -14, -3, 1.5, 0.018, 0.014, 0.02), (11, -37, -10, 6.5, 0.062, 0.052, 0.074),
              (14, *TILT), (23, -33, -9, 6, 0.06, 0.05, 0.066), (25.5, -36, -10.5, 6.2, 0.06, 0.044, 0.078),
              (28, *TILT), (34, -34, -9.5, 6, 0.06, 0.05, 0.068), (35, -34.5, -10.2, 6, 0.06, 0.05, 0.078), (38, *TILT)]
    LFINGER = [(1, "R"), (4, "R"), (8, "O"), (FAST_K - 1, "P"), (FAST_K, "M"), (37, "M"), (40, "P"), (44, "O"), (49, "R")]
    LFREE = [(1, "ready"), (4, ("to_pouch", 0.12, (0.01, 0.005, -0.02))), (9, ("to_pouch", 0.72, (0.02, 0.01, -0.03)))]
    LBACK = [(41, ("near_grab", (0.015, 0.0, -0.03))), (45, ("back", 0.5, (0.03, 0.02, -0.05))), (50, "ready")]
    if GID:
        OFF = tuple(rc.GRIPS[GID]["release"])
        LFINGER = [(1, "R"), (2, "R"), (5, "O"), (FAST_K - 1, "P"), (FAST_K, "M"), (37, "M"), (40, "P"), (44, "O"), (48, "O"), (52, "R")]
        LFREE = [(1, "ready"), (2, "ready"), (5, ("ready_off", OFF)), (9, ("to_pouch", 0.72, (0.02, 0.01, -0.03)))]
        LBACK = [(41, ("near_grab", (0.015, 0.0, -0.03))), (44, ("back", 0.55, (0.035, 0.02, -0.04))), (48, ("ready_off", OFF)), (52, "ready")]
    LATCH = [(1, 0), (23.5, 0), (24.5, 1), (27, 1), (29, 0), (33.5, 0), (34.5, 0.7), (35.5, 0)]
    if CLIP == "fast":
        END = 58
        WEAPON = W_FAST + [(43, -29, -7, 5, 0.05, 0.042, 0.058), (51, 2.5, 1.2, -0.6, -0.003, -0.002, -0.004),
                           (55, 0, 0, 0, 0, 0, 0), (END, 0, 0, 0, 0, 0, 0)]
        RIGHT_IDX = [(1, 0.0), (6, 0.7), (48, 0.7), (54, 0.0), (END, 0.0)]
        ROUNDS = [(1, 12), (FAST_K, 30)]
        MARKERS = [("READY", 1), ("LEFT to pouch", 4), ("new magazine in hand", FAST_K), ("strike — old magazine out", 24),
                   ("old magazine falls", 27), ("hook front lug", 30), ("seat — click", 35), ("LEFT to handguard", 40), ("READY", 55)]
    else:
        END = 92
        ROLL_R = (24, -4, -3, 0.0, 0.03, 0.05)
        WEAPON = W_FAST + [(42, -20, -5, 3, 0.04, 0.035, 0.05), (48, 24, -4, -3, 0.0, 0.03, 0.05),
                           (51, 26.5, -4.5, -3, 0.0, 0.03, 0.052), (54, *ROLL_R), (59, *ROLL_R),
                           (64, 23, -5, -3, 0.0, 0.036, 0.05), (65, 23, -5, -3, 0.0, 0.036, 0.05),
                           (67, 25, -2.5, -3, 0.0, 0.022, 0.052), (71, *ROLL_R), (77, 18, -3, -2, 0.0, 0.022, 0.038),
                           (84, -2, 0.8, 0.4, 0.0, -0.002, -0.003), (88, 0, 0, 0, 0, 0, 0), (END, 0, 0, 0, 0, 0, 0)]
        RIGHT_IDX = [(1, 0.0), (6, 0.7), (48, 0.7)]
        ROUNDS = [(1, 0), (FAST_K, 30)]
        BOLT = [(1, 0.0), (59, 0.0), (61, 0.5), (63.5, 0.97), (64.5, 1.0), (65, 1.0), (67, 0.0), (END, 0.0)]
        MARKERS = [("READY", 1), ("LEFT to pouch", 4), ("new magazine in hand", FAST_K), ("strike — old magazine out", 24),
                   ("seat — click", 35), ("LEFT to handguard / roll right", 40), ("RIGHT to charging handle", 50),
                   ("pull", 59), ("release — bolt slams", 65), ("RIGHT to grip", 68), ("READY", 88)]
    LFINGER.append((END, "R"))
    LBACK.append((END, "ready"))
    LATCH.append((END, 0))
elif CLIP == "jam":
    END = 46
    MAG_KEYS = [(1, 0, 0, 0, 0, 0)]
    CAM_W = [(1, 0)]
    HOLD = None
    ROLL_R = (24, -4, -3, 0.0, 0.03, 0.05)
    # сразу на правый бок: окно с зажатой гильзой — к глазам
    WEAPON = [(1, 0, 0, 0, 0, 0, 0), (5, 9, -1.5, -1, 0.0, 0.012, 0.02), (10, 24, -4, -3, 0.0, 0.03, 0.05),
              (13, 26.5, -4.5, -3, 0.0, 0.03, 0.052), (16, *ROLL_R), (21, *ROLL_R),
              (26, 23, -5, -3, 0.0, 0.036, 0.05), (27, 23, -5, -3, 0.0, 0.036, 0.05),
              (29, 25, -2.5, -3, 0.0, 0.022, 0.052), (33, *ROLL_R), (38, 14, -2.5, -1.5, 0.0, 0.016, 0.028),
              (43, -1.5, 0.6, 0.3, 0.0, -0.002, -0.002), (END, 0, 0, 0, 0, 0, 0)]
    LFINGER = [(1, "R"), (END, "R")]
    LFREE = [(1, "ready"), (END, "ready")]
    LBACK = []
    RIGHT_IDX = [(1, 0.0), (5, 0.7), (10, 0.7)]
    LATCH = [(1, 0), (END, 0)]
    ROUNDS = [(1, 14)]
    # затвор недозакрыт (гильза зажата): JAM_OPEN; рукой — до упора, отпустил — удар вперёд
    BOLT = [(1, rc.JAM_OPEN), (21, rc.JAM_OPEN), (23, 0.66), (25.5, 0.97), (26.5, 1.0), (27, 1.0), (29, 0.0), (END, 0.0)]
    MARKERS = [("JAM: case stuck, bolt open", 1), ("roll right / RIGHT to charging handle", 5), ("pull", 21),
               ("case drops", 24), ("release — bolt slams", 27), ("RIGHT to grip", 30), ("READY", 43)]
else:
    raise SystemExit("клип: tactical | check | full | jam")
# с какого кадра правая уходит к рукоятке затвора (в полной — после смены магазина)
R0 = {"full": 70, "jam": 10, "fastfull": 48}.get(CLIP, 0)
if GID and CLIP != "jam" and not FAST:
    # отпустить рукоятку: кисть отходит от неё вбок с раскрытыми пальцами, затем — к магазину;
    # обратно — подойти сбоку, сомкнуть пальцы
    OFF = tuple(rc.GRIPS[GID]["release"])
    back0 = LBACK[0][0]
    LFREE = [(1, "ready"), (3, "ready"), (7, ("ready_off", OFF)), (11, ("between", 0.66, (0.03, 0.02, -0.05))),
             (14, ("near_grab", (0.012, 0.0, -0.025)))]
    LBACK = [(back0, ("near_grab", (0.015, 0.0, -0.03))), (back0 + 4, ("back", 0.55, (0.035, 0.02, -0.04))),
             (back0 + 8, ("ready_off", OFF)), (back0 + 12, "ready"), (END, "ready")]
    LFINGER = ([(1, "R"), (3, "R"), (7, "O")] + [k for k in LFINGER if 10 <= k[0] < back0 + 3 and k[1] != "R"]
               + [(back0 + 8, "O"), (back0 + 12, "R"), (END, "R")])
    LFINGER.sort(key=lambda k: k[0])
sc.frame_start, sc.frame_end = 1, END


def mag_weapon(f):
    a, r, x, y, z = pchip(MAG_KEYS, f)
    rot = Euler((math.radians(a), math.radians(r), 0), "XYZ").to_matrix()
    return Matrix.Translation(Vector((x, y, z))) @ about(PIVOT, rot)


def weapon_delta(f):
    r, p, yw, x, y, z = pchip(WEAPON, f)
    rot = Euler((math.radians(p), math.radians(r), math.radians(yw)), "XYZ").to_matrix()
    return Matrix.Translation(Vector((x, y, z))) @ about(GRIP, rot)


def mag_camera(f):
    """Магазин перед глазами правым боком (прорези) к камере, верх чуть к ней; лёгкое покачивание."""
    t = f / FPS
    target = EYE + Vector((0.035, -0.36, -0.065)) + Vector((0.004 * math.sin(t * 2.1), 0.0, 0.003 * math.sin(t * 1.7)))
    rot = (Euler((math.radians(10 + 2.5 * math.sin(t * 1.3)), 0, 0), "XYZ").to_matrix()
           @ Euler((0, 0, math.radians(-90 + 6 * math.sin(t * 1.1))), "XYZ").to_matrix())
    world = Matrix.Translation(target) @ rot.to_4x4() @ Matrix.Translation(-MAG_C)
    return weapon_delta(f).inverted() @ world


def mag_delta(f):
    w = min(max(pchip(CAM_W, f)[0], 0.0), 1.0)
    a = mag_weapon(f)
    if w <= 0.0:
        return a
    return lerp_m(a, mag_camera(f), w)


# ---------------------------------------------------------------- ключи

arm_act = bpy.data.actions.new(f"VERAS54_{TAG}_Arms_v01")
ad.action = arm_act
wad = wr.animation_data or wr.animation_data_create()
w_act = bpy.data.actions.new(f"VERAS54_{TAG}_Weapon_v01")
wad.action = w_act
rad = root.animation_data or root.animation_data_create()
c_act = bpy.data.actions.new(f"VERAS54_{TAG}_Controls_v01")
rad.action = c_act
mad = magob.animation_data or magob.animation_data_create()
m_act = bpy.data.actions.new(f"VERAS54_{TAG}_Rounds_v01")
mad.action = m_act
for a in (arm_act, w_act, c_act, m_act):
    a.use_fake_user = True


def key(pb, frame):
    pb.keyframe_insert("location", frame=frame)
    pb.keyframe_insert("rotation_euler", frame=frame)


class Keyer:
    """Ключи кости по матрице в пространстве арматуры с непрерывными углами Эйлера."""

    def __init__(self, pb, arm_w):
        self.pb, self.arm_w, self.prev = pb, arm_w, None

    def at(self, frame, m_arm):
        self.pb.matrix = m_arm
        if self.prev is not None:
            self.pb.rotation_euler = self.pb.matrix_basis.to_euler("XYZ", self.prev)
        self.prev = self.pb.rotation_euler.copy()
        key(self.pb, frame)


def finger_pose(kind, n):
    if kind == "R":
        return READY[n]
    if kind == "M":
        return MAGPOSE[n]
    if kind == "O":
        return lerp_m(lerp_m(READY[n], MAGPOSE[n], 0.5), REST, 0.55)
    if kind == "P":
        return lerp_m(MAGPOSE[n], REST, 0.25)
    if kind == "C":
        return CHECKPOSE[n]
    raise ValueError(kind)


apply(READY)
for n in ALL:
    key(arms.pose.bones[n], 1)
    key(arms.pose.bones[n], END)

WRIST = {"R": 0.0, "O": 0.5, "P": 1.0, "M": 1.0, "C": 1.0}
for frame, kind in LFINGER:
    for n in LEFT:
        arms.pose.bones[n].matrix_basis = finger_pose(kind, n)
        key(arms.pose.bones[n], frame)
    for n in ("forearm.L", "hand.L"):
        arms.pose.bones[n].matrix_basis = CHECKPOSE[n] if kind == "C" else lerp_m(READY[n], MAGPOSE[n], WRIST[kind])
        key(arms.pose.bones[n], frame)
for frame, k in RIGHT_IDX:
    for n in RIGHT_INDEX:
        arms.pose.bones[n].matrix_basis = lerp_m(READY[n], REST, k)
        key(arms.pose.bones[n], frame)


def free_target(spec, grab, ready):
    if spec == "ready":
        return ready
    kind = spec[0]
    if kind == "between":
        m = lerp_m(ready, grab, spec[1])
        m.translation += Vector(spec[2])
        return m
    if kind == "back":
        m = lerp_m(grab, ready, spec[1])
        m.translation += Vector(spec[2])
        return m
    if kind == "near_grab":
        return Matrix.Translation(Vector(spec[1])) @ grab
    if kind == "ready_off":
        return Matrix.Translation(Vector(spec[1])) @ ready
    if kind == "to_pouch":
        # к подсумку: туда, где рука возьмёт новый магазин (быстрая перезарядка)
        m = lerp_m(ready, mag_delta(FAST_K) @ grab, spec[1])
        m.translation += Vector(spec[2])
        return m
    raise ValueError(spec)


kl = Keyer(ikL, arms.matrix_world)
for frame, spec in LFREE:
    kl.at(frame, free_target(spec, IKL_GRAB, IKL_READY))
for f in (range(HOLD[0], HOLD[1] + 1) if HOLD else []):
    g = min(max(pchip(REGRIP, f)[0], 0.0), 1.0) if CLIP == "check" else 0.0
    kl.at(f, mag_delta(f) @ (lerp_m(IKL_GRAB, IKL_CHECK, g) if g > 0 else IKL_GRAB))
for frame, spec in LBACK:
    kl.at(frame, free_target(spec, IKL_GRAB, IKL_READY))

km = Keyer(magc, WR_W)
for f in ([1, HOLD[0] - 1] + list(range(HOLD[0], HOLD[1] + 1)) + [HOLD[1] + 1, END] if HOLD else [1, END]):
    world = mag_delta(f) @ MAG_REST if HOLD and HOLD[0] <= f <= HOLD[1] else MAG_REST
    km.at(f, WR_W.inverted() @ world)

# быстрая перезарядка: старый магазин — запасная кость; стоит в оружии, новый его выбивает, он падает
if FAST:
    spare = rc.add_spare_mag(wr)
    spare.rotation_mode = "XYZ"
    bpy.context.view_layer.update()
    SPARE_REST = WR_W @ spare.matrix
    kspare = Keyer(spare, WR_W)

    def old_delta(f):
        a, r, x, y, z = pchip(OLD_KEYS, f)
        rot = Euler((math.radians(a), math.radians(r), 0), "XYZ").to_matrix()
        return Matrix.Translation(Vector((x, y, z))) @ about(PIVOT, rot)

    for f in [1, 23] + list(range(24, OLD_FREE + 1)):
        kspare.at(f, WR_W.inverted() @ old_delta(f) @ SPARE_REST)
    free_m = old_delta(OLD_FREE) @ SPARE_REST
    # падает: вперёд-вниз, кувыркаясь (оружие наклонено — «низ» в его осях чуть в сторону)
    v0 = Vector((0.05, -0.55, -0.5))
    down = Vector((-0.25, 0.0, -0.97)).normalized()
    for f in range(OLD_FREE + 1, min(OLD_FREE + 14, END) + 1):
        t = (f - OLD_FREE) / FPS
        off = v0 * t + down * (4.9 * t * t)
        spin = about(free_m.translation, Euler((-t * 7.0, t * 2.0, t * 1.5), "XYZ").to_matrix())
        kspare.at(f, WR_W.inverted() @ Matrix.Translation(off) @ spin @ free_m)

# правая на затворе (полная перезарядка, задержка): кадры — от R0, затвор в начале — на BOLT[0] хода
if CLIP in ("full", "jam", "fastfull"):
    B0 = BOLT[0][1]
    slam = R0 + 17

    def pull(f):
        return track(BOLT, f)[0] if not (slam <= f <= slam + 2) else 1.0 - (f - slam) / 2.0

    kr = Keyer(ikR, arms.matrix_world)
    # туда и обратно — в обход ствольной коробки снаружи справа (−X в осях оружия), не сквозь крышку
    out = Vector((-0.065, 0.0, 0.0))
    at0 = BOLT_VEC * B0                     # где рукоятка затвора ждёт руку
    if R0 > 1:
        kr.at(1, IKR_READY)
    kr.at(R0, IKR_READY)
    kr.at(R0 + 3, Matrix.Translation(out + Vector((0.0, 0.0, 0.015))) @ IKR_READY)
    kr.at(R0 + 6, Matrix.Translation(at0 + out + Vector((0.0, -0.01, 0.035))) @ IKR_HOOK)
    kr.at(R0 + 9, Matrix.Translation(at0 + Vector((-0.012, -0.022, 0.016))) @ IKR_HOOK)
    for f in range(R0 + 11, R0 + 18):
        kr.at(f, Matrix.Translation(BOLT_VEC * track(BOLT, f)[0]) @ IKR_HOOK)
    # отпустил у заднего упора: кисть уходит наружу-вверх, затвор бьёт вперёд
    kr.at(R0 + 19, Matrix.Translation(BOLT_VEC * 1.05 + Vector((-0.03, 0.0, 0.02))) @ IKR_HOOK)
    kr.at(R0 + 22, Matrix.Translation(BOLT_VEC * 0.8 + out + Vector((0.0, 0.0, 0.02))) @ IKR_HOOK)
    kr.at(R0 + 26, Matrix.Translation(out + Vector((0.0, 0.0, 0.01))) @ IKR_READY)
    kr.at(R0 + 29, IKR_READY)
    kr.at(END, IKR_READY)
    open_r = {n: lerp_m(READY[n], REST, 0.6) for n in RIGHT}
    pre = {n: lerp_m(HOOK[n], REST, 0.35) for n in RIGHT}
    for frame, pose in ((R0, {n: lerp_m(READY[n], REST, 0.7) if n in RIGHT_INDEX else READY[n] for n in RIGHT}),
                        (R0 + 4, open_r), (R0 + 9, pre), (R0 + 11, HOOK), (R0 + 17, HOOK), (R0 + 19, pre),
                        (R0 + 23, open_r), (R0 + 29, READY), (END, READY)):
        for n in RIGHT + ["forearm.R", "hand.R"]:
            src = pose.get(n)
            if src is None:
                src = HOOK[n] if pose is HOOK else READY[n]
            arms.pose.bones[n].matrix_basis = src
            key(arms.pose.bones[n], frame)
    for f in range(R0 + 10, R0 + 22):
        root["Bolt pull"] = pull(f)
        root.keyframe_insert('["Bolt pull"]', frame=f)
    root["Bolt pull"] = B0
    root.keyframe_insert('["Bolt pull"]', frame=1)
    root["Bolt pull"] = 0.0
    root.keyframe_insert('["Bolt pull"]', frame=END)

# зажатая гильза: до отвода затвора стоит в окне, освободилась — вылетает вправо-вверх и падает
if CLIP == "jam":
    case_pb = rc.add_jam_case(wr)
    case_pb.rotation_mode = "XYZ"
    bpy.context.view_layer.update()
    kc = Keyer(case_pb, WR_W)
    rest_arm = case_pb.matrix.copy()
    free = R0 + 13                           # затвор прошёл гильзу
    to_arm = WR_W.inverted().to_3x3()
    roll = math.radians(ROLL_R[0])
    v0 = Vector((-0.75, 0.2, 0.55))
    down = Vector((math.sin(roll), 0.0, -math.cos(roll)))    # настоящий «низ» в осях накренённого оружия
    kc.at(1, rest_arm)
    for f in range(free, min(free + 14, END) + 1):
        t = (f - free) / FPS
        off = to_arm @ (v0 * t + down * (4.9 * t * t))
        spin = Euler((t * 14.0, t * 9.0, t * 5.0), "XYZ").to_matrix().to_4x4()
        here = Matrix.Translation(rest_arm.translation + off) @ rest_arm.to_3x3().to_4x4() @ spin
        kc.at(f, here)

kw = Keyer(wc, arms.matrix_world)
for k in WEAPON:
    kw.at(k[0], weapon_delta(k[0]) @ WC_READY)

for frame, v in LATCH:
    root["Magazine latch press"] = float(v)
    root.keyframe_insert('["Magazine latch press"]', frame=frame)
for frame, v in ROUNDS:
    magob["Rounds remaining"] = int(v)
    magob.keyframe_insert('["Rounds remaining"]', frame=frame)


def fcurves(act):
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


for act in (arm_act, w_act, c_act, m_act):
    for fc in fcurves(act):
        dense = len(fc.keyframe_points) > 12
        for kp in fc.keyframe_points:
            if act is m_act:
                kp.interpolation = "CONSTANT"
            elif dense:
                kp.interpolation = "LINEAR"
            else:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"

for name, frame in MARKERS:
    sc.timeline_markers.new(name, frame=frame)

# проверка: дотягиваются ли IK-кисти (запястье у цели) на каждом кадре
worst = {"L": 0.0, "R": 0.0}
for f in range(1, END + 1):
    sc.frame_set(f)
    for s in ("L", "R"):
        d = (arms.pose.bones[f"hand.{s}"].head - arms.pose.bones[f"ik_hand.{s}"].head).length
        worst[s] = max(worst[s], d)
print("CLIP", CLIP, "кадров", END, "IK не дотянулась, мм: L", round(worst["L"] * 1000, 1), "R", round(worst["R"] * 1000, 1))

txt = bpy.data.texts.get("Клипы — как править") or bpy.data.texts.new("Клипы — как править")
txt.from_string(__doc__ + f"""
Клип {CLIP}: кадры 1–{END}, {FPS} к/с. Действия: {arm_act.name} (FPS_ArmsRig), {w_act.name} (VERAS54_WeaponRig),
{c_act.name} (VERAS54: защёлка, затвор), {m_act.name} (Magazine: Rounds remaining). Маркеры — фазы.
Редкие ключи: Weapon_CTRL, пальцы, свойства. Запечены по кадрам: ik_hand.L и Magazine_Control в хвате{', ik_hand.R при отводе затвора' if CLIP == 'full' else ''}.
Глушитель скрыт (коллекция 09 | Suppressor) — отдельный ассет.""")
sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("CLIP saved", OUT)
