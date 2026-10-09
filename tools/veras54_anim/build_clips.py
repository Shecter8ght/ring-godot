"""ВЕРАС-54: клипы рук и оружия — тактическая перезарядка, проверка магазина, полная перезарядка.

Позы — из файла VERAS54_Charging_Hook_v01.blend: боевой хват (action VERAS54_Grip_Manual_v02, владелец),
хват магазина левой (обхват по касанию поверх позы владельца), правая на рукоятке затвора (крюк указательным).
Магазин в руке: путь в осях оружия (качок у переднего зацепа) или к глазам (проверка), кисть следует за
ним с тем же смещением, что в хвате. Наклон оружия — ключи Weapon_CTRL вокруг рукоятки (IK-кисти — дочерние).
Защёлка, затвор, патроны — ключи свойств рига (Magazine latch press, Bolt pull, Rounds remaining).
Путь кистей и магазина в хвате запечён по кадрам (экспорт в glTF без ограничений); остальное — редкие ключи.

blender --background VERAS54_Charging_Hook_v01.blend --python build_clips.py -- <tactical|check|full> <выход .blend>
"""
import math
import sys

import bpy
from mathutils import Euler, Matrix, Vector

CLIP, OUT = sys.argv[sys.argv.index("--") + 1:][:2]
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
    import json
    from pathlib import Path as _P
    raw = json.loads((_P(bpy.data.filepath).parent / "check_grip_pose.json").read_text(encoding="utf-8"))
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
handle = bpy.data.objects["Charging handle • integral flattened shoe"]
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
    # затвор: доля хода (0 — закрыт, 1 — 74 мм); отвод рукой, у упора — пауза, отпустил — удар вперёд
    BOLT = [(1, 0.0), (81, 0.0), (83, 0.5), (85.5, 0.97), (86.5, 1.0), (87, 1.0), (89, 0.0), (END, 0.0)]
    MARKERS = [("READY", 1), ("LEFT to magazine", 5), ("latch / rock out", 17), ("to pouch (empty)", 26),
               ("new magazine (full)", 42), ("seat — click", 57), ("LEFT to handguard / roll right", 61),
               ("RIGHT to charging handle", 72), ("pull", 81), ("release — bolt slams", 87), ("RIGHT to grip", 90),
               ("READY", 110)]
else:
    raise SystemExit("клип: tactical | check | full")
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

arm_act = bpy.data.actions.new(f"VERAS54_{CLIP.title()}_Arms_v01")
ad.action = arm_act
wad = wr.animation_data or wr.animation_data_create()
w_act = bpy.data.actions.new(f"VERAS54_{CLIP.title()}_Weapon_v01")
wad.action = w_act
rad = root.animation_data or root.animation_data_create()
c_act = bpy.data.actions.new(f"VERAS54_{CLIP.title()}_Controls_v01")
rad.action = c_act
mad = magob.animation_data or magob.animation_data_create()
m_act = bpy.data.actions.new(f"VERAS54_{CLIP.title()}_Rounds_v01")
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
    raise ValueError(spec)


kl = Keyer(ikL, arms.matrix_world)
for frame, spec in LFREE:
    kl.at(frame, free_target(spec, IKL_GRAB, IKL_READY))
for f in range(HOLD[0], HOLD[1] + 1):
    g = min(max(pchip(REGRIP, f)[0], 0.0), 1.0) if CLIP == "check" else 0.0
    kl.at(f, mag_delta(f) @ (lerp_m(IKL_GRAB, IKL_CHECK, g) if g > 0 else IKL_GRAB))
for frame, spec in LBACK:
    kl.at(frame, free_target(spec, IKL_GRAB, IKL_READY))

km = Keyer(magc, WR_W)
for f in [1, HOLD[0] - 1] + list(range(HOLD[0], HOLD[1] + 1)) + [HOLD[1] + 1, END]:
    world = mag_delta(f) @ MAG_REST if HOLD[0] <= f <= HOLD[1] else MAG_REST
    km.at(f, WR_W.inverted() @ world)

# правая на затворе (полная перезарядка)
if CLIP == "full":
    def pull(f):
        return track(BOLT, f)[0] if not (87 <= f <= 89) else 1.0 - (f - 87) / 2.0

    kr = Keyer(ikR, arms.matrix_world)
    up = Vector((0.0, 0.0, 0.03))
    # туда и обратно — в обход ствольной коробки снаружи справа (−X в осях оружия), не сквозь крышку
    out = Vector((-0.065, 0.0, 0.0))
    kr.at(70, IKR_READY)
    kr.at(73, Matrix.Translation(out + Vector((0.0, 0.0, 0.015))) @ IKR_READY)
    kr.at(76, Matrix.Translation(out + Vector((0.0, -0.01, 0.035))) @ IKR_HOOK)
    kr.at(79, Matrix.Translation(Vector((-0.012, -0.022, 0.016))) @ IKR_HOOK)
    for f in range(81, 88):
        kr.at(f, Matrix.Translation(BOLT_VEC * track(BOLT, f)[0]) @ IKR_HOOK)
    # отпустил у заднего упора: кисть уходит наружу-вверх, затвор бьёт вперёд
    kr.at(89, Matrix.Translation(BOLT_VEC * 1.05 + Vector((-0.03, 0.0, 0.02))) @ IKR_HOOK)
    kr.at(92, Matrix.Translation(BOLT_VEC * 0.8 + out + Vector((0.0, 0.0, 0.02))) @ IKR_HOOK)
    kr.at(96, Matrix.Translation(out + Vector((0.0, 0.0, 0.01))) @ IKR_READY)
    kr.at(99, IKR_READY)
    kr.at(END, IKR_READY)
    open_r = {n: lerp_m(READY[n], REST, 0.6) for n in RIGHT}
    pre = {n: lerp_m(HOOK[n], REST, 0.35) for n in RIGHT}
    for frame, pose in ((70, {n: lerp_m(READY[n], REST, 0.7) if n in RIGHT_INDEX else READY[n] for n in RIGHT}),
                        (74, open_r), (79, pre), (81, HOOK), (87, HOOK), (89, pre), (93, open_r), (99, READY), (END, READY)):
        for n in RIGHT + ["forearm.R", "hand.R"]:
            src = pose.get(n)
            if src is None:
                src = HOOK[n] if pose is HOOK else READY[n]
            arms.pose.bones[n].matrix_basis = src
            key(arms.pose.bones[n], frame)
    for f in range(80, 92):
        root["Bolt pull"] = pull(f)
        root.keyframe_insert('["Bolt pull"]', frame=f)
    root["Bolt pull"] = 0.0
    root.keyframe_insert('["Bolt pull"]', frame=1)
    root.keyframe_insert('["Bolt pull"]', frame=END)

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
