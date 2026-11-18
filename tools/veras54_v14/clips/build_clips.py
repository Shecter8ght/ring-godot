"""ВЕРАС-54 (wpn_ar_01): клипы рук от первого лица — ключевые кадры движения. Хваты — отдельно, в действии VERAS54_Poses.

Вход — файл с позами (poses.py или тот же файл клипов после правки поз владельцем); выход — один .blend со всеми клипами:
каждое действие VERAS54_<Клип> (слоты: FPS_ArmsRig, VERAS54_WeaponRig, VERAS54 — свойства деталей, Magazine — число
патронов) и версии под рукоятки ВАРН V1 / V2 и магазины 45 / 60 (VERAS54_<Клип>__<рукоятка>_<магазин>, собирает панель).

Что чем двигается (ключи редкие, только на опорных позах; между ними — кривые Bezier):
  автомат   — Weapon_CTRL (с ним едут цели обеих кистей): (крен, тангаж, рыскание, x, y, z) от хвата, как в клипах v13;
  кисти     — ik_hand.L / ik_hand.R (на автомате — едут с ним), плечи upper_arm.* — из позы того же ключа;
  пальцы    — из поз (кадр-поза → набор костей), ключ «как в позе» панель потом обновляет из поз;
  магазин   — в руке: ограничение «В левой кисти» у Magazine_Control (и у SpareMag) к кости mag.L (влияние 0 / 1); в шахте —
              своими ключами; старый магазин быстрой перезарядки и уроненный — кость SpareMag, гильза задержки — JamCase,
              глушитель — Suppressor_Control (к кости supp.L); «выключены» масштабом 0,001;
  детали    — свойства VERAS54 (затвор Bolt pull, защёлка, спуск, переводчик) и Magazine (Rounds remaining).
Каждый клип начинается и кончается позой «ХВАТ» (кроме «убрать автомат» и «палец со спуска»).

ВАЖНО: этот скрипт — генератор черновых клипов. После него клипы правит владелец прямо в Blender (панель «ВЕРАС»,
clip_tools.py). Повторный запуск стирает ручные правки клипов (позы остаются) — только через regenerate.cmd с подтверждением;
rebuild.cmd на файле с клипами делает лишь то же, что кнопка панели.

blender -b "<позы или клипы.blend>" --python-exit-code 1 --python tools/veras54_v14/clips/build_clips.py -- <выход.blend>
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

HERE = Path(__file__).resolve().parent
ROOT_DIR = HERE.parents[2]
OUT = Path(sys.argv[sys.argv.index("--") + 1])
sys.path.insert(0, str(HERE))
import clip_tools as CT  # noqa: E402
from vcommon import Gun, about, finger_to, gun_delta, lerp_m  # noqa: E402

FPS = 30
PREFIX = CT.PREFIX
log = lambda *a: print("VERAS_CLIPS", *a, flush=True)  # noqa: E731
S = bpy.context.scene
S.render.fps = FPS
arms = bpy.data.objects["FPS_ArmsRig"]
glove = bpy.data.objects["FPS_Arms"]
wr = bpy.data.objects["VERAS54_WeaponRig"]
root = bpy.data.objects["VERAS54"]
magob = bpy.data.objects["Magazine"]
cam = bpy.data.objects["FPS • Camera"]
PTS = json.loads(root["clip_points"])
A_BONES = [pb.name for pb in arms.pose.bones]
FING = lambda n: n.split(".")[0] in CT.FINGER  # noqa: E731
L_FING = [n for n in A_BONES if FING(n) and n.endswith(".L")]
R_FING = [n for n in A_BONES if FING(n) and n.endswith(".R")]
R_INDEX = [n for n in A_BONES if n.startswith("f_index") and n.endswith(".R")]
R_THUMB = [n for n in A_BONES if n.startswith("thumb") and n.endswith(".R")]
L_THUMB = [n for n in A_BONES if n.startswith("thumb") and n.endswith(".L")]
I4 = Matrix.Identity(4)
CONS = {b: wr.pose.bones[b].constraints["В левой кисти"] for b in ("Magazine_Control", "SpareMag", "Suppressor_Control")}
PROPS0 = {"Bolt pull": 0.0, "Magazine latch press": 0.0, "Trigger pull": 0.0, "Fire mode": 1.0, "Selector from mode": 1.0,
          "Selector blend": 1.0, "Muzzle attachment": 0.0}
MODE = dict(auto=1.0, semi=2.0, burst=3.0)
JAM_OPEN = 0.30


def update():
    bpy.context.view_layer.update()


def slot_of(act, ob):
    return next((s for s in act.slots if s.name_display == ob.name), None) or act.slots.new(id_type="OBJECT", name=ob.name)


def assign(act, objs=(arms, wr, root, magob)):
    for ob in objs:
        ad = ob.animation_data or ob.animation_data_create()
        ad.action = act
        if act is not None:
            ad.action_slot = slot_of(act, ob)


# ================================================================ позы владельца
for ob in (arms, wr, root, magob):                   # прежние дорожки — прочь (пересборка)
    ad = ob.animation_data
    if ad:
        for t in list(ad.nla_tracks):
            ad.nla_tracks.remove(t)
for a in list(bpy.data.actions):
    if a.name.startswith(PREFIX) and a.name not in (CT.POSES,):
        bpy.data.actions.remove(a)
poses_act = bpy.data.actions[CT.POSES]
POSE_AT = {f: n for n, f in CT.POSE_FRAMES.items()}


def bag_of(act, ob):
    layer = act.layers[0] if act.layers else act.layers.new("Layer")
    strip = layer.strips[0] if layer.strips else layer.strips.new(type="KEYFRAME")
    return strip.channelbag(slot_of(act, ob), ensure=True)


def absorb(ob):
    """Ключи владельца, попавшие мимо поз (K без открытого действия заводит «…Action»), переносятся в позы на свои
    кадры; само постороннее действие убирается."""
    ad = ob.animation_data
    if ad is None:
        return
    if ad.use_tweak_mode:
        ad.use_tweak_mode = False
    stray = ad.action
    if stray is None or stray == poses_act or stray.name.startswith(PREFIX):
        return
    src = next((b for layer in stray.layers for st in layer.strips for b in [st.channelbag(ad.action_slot)] if b), None) \
        if ad.action_slot else None
    moved, lost = set(), set()
    if src is not None and ob in (arms, wr):
        dst = bag_of(poses_act, ob)
        for fc in src.fcurves:
            tgt = dst.fcurves.find(fc.data_path, index=fc.array_index)
            for kp in fc.keyframe_points:
                f = round(kp.co[0])
                if f not in POSE_AT:
                    lost.add(f)
                    continue
                if tgt is None:
                    tgt = dst.fcurves.new(fc.data_path, index=fc.array_index, group_name=fc.group.name if fc.group else "")
                tgt.keyframe_points.insert(f, kp.co[1], options={"REPLACE"})
                moved.add(f)
            if tgt is not None:
                tgt.update()
    log(f"{ob.name}: ключи из постороннего действия «{stray.name}» перенесены в позы, кадры {sorted(moved)}"
        + (f"; ключи на кадрах {sorted(lost)} — не кадры поз, отброшены" if lost else ""))
    ad.action = None
    if stray.users == 0 or not stray.use_fake_user:
        bpy.data.actions.remove(stray)


for ob in (arms, wr, root, magob):
    absorb(ob)
assign(None)
assign(poses_act, (arms, wr))
for c in CONS.values():
    c.enabled = False
B, SHORT = {}, {}
for name, f in CT.POSE_FRAMES.items():
    S.frame_set(f)
    update()
    B[name] = {n: arms.pose.bones[n].matrix_basis.copy() for n in A_BONES}
    for s in ("L", "R"):
        gap = (arms.pose.bones[f"hand.{s}"].head - arms.pose.bones[f"ik_hand.{s}"].head).length * 1000
        if gap > 1.0:
            SHORT[(name, s)] = gap
for c in CONS.values():
    c.enabled = True
for (name, s), gap in SHORT.items():
    log(f"поза «{name}» (кадр {CT.POSE_FRAMES[name]}): {'левая' if s == 'L' else 'правая'} рука не дотягивается на {gap:.0f} мм")
assign(None)

# ================================================================ покой: хват, автомат на месте
for pb in wr.pose.bones:
    pb.matrix_basis = I4.copy()
for c in CONS.values():
    c.influence = 0.0
for n, v in PROPS0.items():
    root[n] = v
for n in A_BONES:
    arms.pose.bones[n].matrix_basis = B["grip"][n]
update()
G = Gun(arms, B["grip"]["Weapon_CTRL"], PTS["grip"], wr)
AW, AWI = G.AW, G.AWI
WR_REST = G.WR_REST
wc = arms.pose.bones["Weapon_CTRL"]
IK_REL = {s: arms.data.bones["Weapon_CTRL"].matrix_local.inverted() @ arms.data.bones[f"ik_hand.{s}"].matrix_local for s in ("L", "R")}
IK_AT_REST = {s: G.WC_REST @ IK_REL[s] for s in ("L", "R")}
for s in ("L", "R"):
    chk = IK_AT_REST[s] @ B["grip"][f"ik_hand.{s}"] - arms.pose.bones[f"ik_hand.{s}"].matrix
    assert max(abs(v) for row in chk for v in row) < 1e-5, "цель кисти не дочерняя Weapon_CTRL"
HAND_W = {s: {p: AW @ IK_AT_REST[s] @ B[p][f"ik_hand.{s}"] for p in B} for s in ("L", "R")}   # кисть в мире, автомат в покое
PIVOT_W = WR_REST @ Vector(PTS["pivot"])
MAG_REST_W = WR_REST @ wr.data.bones["Magazine_Control"].matrix_local
dg = bpy.context.evaluated_depsgraph_get()
_mb = bpy.data.objects["Magazine_Body"].evaluated_get(dg)
MAG_C_W = sum((_mb.matrix_world @ Vector(v) for v in _mb.bound_box), Vector()) / 8
EYE = cam.matrix_world.translation.copy()
CAM_FWD = -(cam.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
CAM_UP = (cam.matrix_world.to_3x3() @ Vector((0, 1, 0))).normalized()
CAM_RT = CAM_FWD.cross(CAM_UP).normalized()
# ход рукоятки затвора при «Bolt pull» = 1 (мир, автомат в покое)
_h = bpy.data.objects["ChargingHandle"]
_h0 = _h.matrix_world.translation.copy()
root["Bolt pull"] = 1.0
root.update_tag()
update()
BOLT_VEC = _h.matrix_world.translation - _h0
root["Bolt pull"] = 0.0
root.update_tag()
update()
log("ход рукоятки затвора, мм", [round(v * 1000, 1) for v in BOLT_VEC])

# положения автомата по умолчанию (как в poses.py) и поправки владельца с кадров поз
TILT = (-34, -9, 6, 0.06, 0.05, 0.07)
ROLL_R = (24, -4, -3, 0.0, 0.03, 0.05)
LOW = (-16, -2, 2, 0.01, 0.02, -0.02)
DEF = dict(mag=TILT, hook=ROLL_R, check=LOW)
CORR = {}
for ref, d in DEF.items():
    own_shift = G.shift_of(B[ref]["Weapon_CTRL"])
    CORR[ref] = own_shift @ gun_delta(d, G.GRIP_W).inverted()
    ang = math.degrees(CORR[ref].to_quaternion().angle)
    if ang > 0.05 or CORR[ref].translation.length > 0.0005:
        log(f"поза «{ref}»: автомат стоит иначе, чем по умолчанию ({ang:.1f}°, {CORR[ref].translation.length * 1000:.0f} мм) — "
            "ключи автомата возле неё сдвинуты так же")
SUPP_W = G.shift_of(B["supp"]["Weapon_CTRL"])


def near_ref(pose):
    """К какой позе с положением автомата близок ключ (крен…z) — или None."""
    D = gun_delta(pose, G.GRIP_W)
    best = None
    for ref, d in DEF.items():
        Dr = gun_delta(d, G.GRIP_W)
        ang = math.degrees(D.to_quaternion().rotation_difference(Dr.to_quaternion()).angle)
        dist = (D.translation - Dr.translation).length
        if ang < CT.GUN_NEAR_DEG and dist < CT.GUN_NEAR_M and (best is None or ang + dist * 300 < best[0]):
            best = (ang + dist * 300, ref)
    return best[1] if best else None


# ================================================================ сплайны (как в клипах v13)
def pchip(keys, f):
    """Монотонный кубический сплайн по ключам (кадр, значения…): на остановках — без перелёта."""
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
        out.append((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h * m0 + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h * m1)
    return tuple(out)


def mag_delta(k):
    """Магазин в осях автомата (мир при покое): (качок°, крен°, x, y, z) вокруг переднего зацепа."""
    a, r, x, y, z = k
    return Matrix.Translation(Vector((x, y, z))) @ about(PIVOT_W, Euler((math.radians(a), math.radians(r), 0), "XYZ").to_matrix())


def track(keys, f):
    return pchip(keys, f)[0]


# ================================================================ клип
class Clip:
    def __init__(self, name, end, title, versions="grip+mag", variant=None, state=None, mark_order=()):
        self.name, self.end, self.title = name, end, title
        self.act = bpy.data.actions.new(PREFIX + name)
        self.act.use_fake_user = True
        self.act["title"] = title
        self.act["versions"] = versions
        self.act["variant"] = json.dumps(dict(dict(grip="", mag="30"), **(variant or {})))
        assign(self.act)
        self.prev = {}
        self.marks = {}
        st = dict(PROPS0, **{"Rounds remaining": 30})
        st.update(state or {})
        self.state0 = st
        for pb in wr.pose.bones:
            pb.matrix_basis = I4.copy()
        for n in A_BONES:                             # опорная поза в начале и в конце — у всех костей
            self.bone(n, 1, B["grip"][n])
            self.bone(n, end, B["grip"][n])
        for n, v in st.items():
            self.prop(n, [(1, v)])
        for b in ("Magazine_Control", "SpareMag", "JamCase", "Suppressor_Control"):
            self.wmat(b, [(1, "rest")])
        for b in ("SpareMag", "JamCase", "Suppressor_Control"):
            self.scale(b, [(1, 0)])
        for b in ("MuzzleAttachment", "SpareMag_Rounds"):
            self.scale(b, [(1, 1)])
        for b in CONS:
            self.hold(b, [(1, 0)])

    # ---- руки
    def bone(self, n, frame, basis):
        pb = arms.pose.bones[n]
        pb.matrix_basis = basis
        if pb.rotation_mode == "QUATERNION":
            q = pb.rotation_quaternion.copy()
            if n in self.prev and self.prev[n].dot(q) < 0:
                q.negate()
            pb.rotation_quaternion = q
            self.prev[n] = q.copy()
            pb.keyframe_insert("rotation_quaternion", frame=frame)
        else:
            if n in self.prev:
                pb.rotation_euler = basis.to_euler("XYZ", self.prev[n])
            self.prev[n] = pb.rotation_euler.copy()
            pb.keyframe_insert("rotation_euler", frame=frame)
        pb.keyframe_insert("location", frame=frame)
        if n in ("mag.L",):
            pb.keyframe_insert("scale", frame=frame)

    def fingers(self, names, keys):
        """keys: (кадр, имя позы | {кость: матрица})."""
        for frame, pose in keys:
            for n in names:
                self.bone(n, frame, pose[n] if isinstance(pose, dict) else B[pose][n])
        return self

    def gun(self, keys):
        """Автомат: (кадр, поза) — поза: (крен, тангаж, рыскание, x, y, z) от хвата (возле позы с положением автомата —
        с поправкой владельца с кадра позы) | ('pose', имя, поправка6) | матрица сдвига в мире."""
        for frame, spec in keys:
            if isinstance(spec, Matrix):
                D = spec
            elif spec and spec[0] == "pose":
                base = SUPP_W if spec[1] == "supp" else G.shift_of(B[spec[1]]["Weapon_CTRL"])
                d = spec[2] if len(spec) > 2 else (0, 0, 0, 0, 0, 0)
                D = Matrix.Translation(Vector(d[3:])) @ base @ gun_delta((d[0], d[1], d[2], 0, 0, 0), G.GRIP_W)
            else:
                ref = near_ref(spec)
                D = gun_delta(spec, G.GRIP_W)
                if ref is not None:
                    D = CORR[ref] @ D
            self.bone("Weapon_CTRL", frame, G.WC_PARENT.inverted() @ AWI @ D @ AW @ G.WC_REST)
        return self

    def gun_at(self, frame):
        """Сдвиг автомата в мире на кадре (по уже поставленным ключам)."""
        S.frame_set(int(frame), subframe=frame - int(frame))
        update()
        return (AW @ wc.matrix) @ (AW @ G.WC_REST).inverted()

    def hand(self, side, keys, shoulder=True):
        """Кисть: (кадр, место) — место: имя позы | ('off', поза, (dx, dy, dz)) — сдвиг в мире при покое автомата |
        ('lerp', поза_а, поза_б, t, сдвиг) | ('mag', поза, D) — D @ кисть позы (D — сдвиг магазина в осях автомата) |
        ('w', H) — кисть в мире при покое автомата | ('world', H) — кисть в мире сейчас (автомат — где он на кадре)."""
        bn = f"ik_hand.{side}"
        for frame, spec in keys:
            arm_pose = "grip"
            if isinstance(spec, str):
                arm_pose = spec
                basis = B[spec][bn]
            else:
                kind = spec[0]
                if kind == "off":
                    arm_pose = spec[1]
                    H = Matrix.Translation(Vector(spec[2])) @ HAND_W[side][spec[1]]
                elif kind == "lerp":
                    arm_pose = spec[1] if spec[3] < 0.5 else spec[2]
                    H = lerp_m(HAND_W[side][spec[1]], HAND_W[side][spec[2]], spec[3])
                    H.translation += Vector(spec[4])
                elif kind == "mag":
                    arm_pose = spec[1]
                    H = spec[2] @ HAND_W[side][spec[1]]
                elif kind == "w":
                    H = spec[1]
                elif kind == "world":
                    G_f = self.gun_at(frame)
                    H = G_f.inverted() @ spec[1]
                else:
                    raise ValueError(spec)
                basis = IK_AT_REST[side].inverted() @ AWI @ H
            self.bone(bn, frame, basis)
            if shoulder:
                for n in (f"upper_arm.{side}", f"pole.{side}"):
                    self.bone(n, frame, B[arm_pose][n])
        return self

    # ---- автомат: детали
    def prop(self, name, keys, ob=None):
        ob = ob or (magob if name == "Rounds remaining" else root)
        for frame, v in keys:
            ob[name] = int(v) if name == "Rounds remaining" else float(v)
            ob.keyframe_insert(f'["{name}"]', frame=frame)
        return self

    def hold(self, bone, keys):
        c = CONS[bone]
        for frame, v in keys:
            c.influence = float(v)
            c.keyframe_insert("influence", frame=frame)
        return self

    def scale(self, bone, keys):
        pb = wr.pose.bones[bone]
        for frame, on in keys:
            pb.scale = (1.0, 1.0, 1.0) if on else (0.001, 0.001, 0.001)
            pb.keyframe_insert("scale", frame=frame)
        return self

    def wmat(self, bone, keys, gun_now=False):
        """Кость рига оружия: (кадр, 'rest' | D — сдвиг в осях автомата (мир при покое) | ('world', M) — где кость в мире
        сейчас (автомат — где он на кадре))."""
        pb = wr.pose.bones[bone]
        rest = wr.data.bones[bone].matrix_local
        for frame, spec in keys:
            if isinstance(spec, str):
                arm_m = rest.copy()
            elif isinstance(spec, tuple) and spec[0] == "world":
                G_f = self.gun_at(frame)
                arm_m = (G_f @ WR_REST).inverted() @ spec[1]
            else:
                arm_m = WR_REST.inverted() @ spec @ WR_REST @ rest
            pb.matrix = arm_m
            mb = pb.matrix_basis.copy()               # сразу: пересчёт анимации затёр бы позу
            pb.location = mb.translation
            pb.rotation_euler = mb.to_euler("XYZ", self.prev.get("w:" + bone, Euler()))
            self.prev["w:" + bone] = pb.rotation_euler.copy()
            pb.keyframe_insert("location", frame=frame)
            pb.keyframe_insert("rotation_euler", frame=frame)
        return self

    def bone_world(self, bone, frame):
        """Где кость рига оружия в мире на кадре (по ключам)."""
        S.frame_set(int(frame))
        update()
        return wr.matrix_world @ wr.pose.bones[bone].matrix

    def fall(self, bone, f0, n=14, v0=(0.05, -0.55, -0.5), spin=(-7.0, 2.0, 1.5), hide_after=True):
        """Свободное падение детали с кадра f0: с того места, где она на f0 (мир), скорость v0 — в осях автомата."""
        M0 = self.bone_world(bone, f0)
        G0 = self.gun_at(f0)
        v = G0.to_3x3() @ Vector(v0)
        keys = []
        for f in range(f0 + 1, min(f0 + n, self.end) + 1, 2):
            t = (f - f0) / FPS
            off = v * t + Vector((0, 0, -4.9 * t * t))
            R = Euler((t * spin[0], t * spin[1], t * spin[2]), "XYZ").to_matrix().to_4x4()
            M = Matrix.Translation(M0.translation + off) @ R @ M0.to_3x3().to_4x4()
            keys.append((f, ("world", M)))
        self.wmat(bone, keys)
        if hide_after:
            self.scale(bone, [(min(f0 + n + 1, self.end), 0)])
        return self

    def reach(self, tol=2.0, passes=3):
        """Где рука не дотягивается до цели (автомат далеко), плечо подаётся к кисти ровно настолько — ключи плеча
        на кадрах с недотягом (раз в 3 кадра) и опоры по краям участка."""
        for side in ("L", "R"):
            ua = arms.pose.bones[f"upper_arm.{side}"]
            for _ in range(passes):
                gaps = {}
                for f in range(1, self.end + 1):
                    S.frame_set(f)
                    gaps[f] = (arms.pose.bones[f"ik_hand.{side}"].head - arms.pose.bones[f"hand.{side}"].head).length * 1000
                bad = [f for f, g in gaps.items() if g > tol]
                if not bad:
                    break
                runs, cur = [], [bad[0]]
                for f in bad[1:]:
                    if f - cur[-1] <= 2:
                        cur.append(f)
                    else:
                        runs.append(cur)
                        cur = [f]
                runs.append(cur)
                plan = []
                for r in runs:
                    frames = sorted(set(r[::3]) | {r[-1], max(r, key=lambda f: gaps[f])})
                    for edge in (r[0] - 2, r[-1] + 2):
                        if 1 <= edge <= self.end:
                            S.frame_set(edge)
                            plan.append((edge, ua.matrix_basis.copy()))
                    for f in frames:
                        S.frame_set(f)
                        update()
                        m = ua.matrix.copy()
                        for _i in range(6):
                            d = arms.pose.bones[f"ik_hand.{side}"].head - arms.pose.bones[f"hand.{side}"].head
                            if d.length < 0.0005:
                                break
                            ua.matrix = Matrix.Translation(d * 1.05) @ ua.matrix
                            update()
                        plan.append((f, ua.matrix_basis.copy()))
                for f, mb in plan:
                    self.bone(ua.name, f, mb)
                for fc in [fc for layer in self.act.layers for st in layer.strips for bag in st.channelbags for fc in bag.fcurves
                           if ua.name in fc.data_path]:
                    for kp in fc.keyframe_points:
                        kp.interpolation = "BEZIER"
                        kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
                    fc.update()

    def mark(self, **kw):
        self.marks.update(kw)
        return self

    def finish(self):
        for fc in [fc for layer in self.act.layers for st in layer.strips for bag in st.channelbags for fc in bag.fcurves]:
            step = ("influence" in fc.data_path or fc.data_path.endswith("scale") or "Rounds" in fc.data_path
                    or "Fire mode" in fc.data_path or "Selector from" in fc.data_path)
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT" if step else "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()
        self.reach()
        worst = {"L": (0.0, 0), "R": (0.0, 0)}
        for f in range(1, self.end + 1):
            S.frame_set(f)
            for s in ("L", "R"):
                d = (arms.pose.bones[f"hand.{s}"].head - arms.pose.bones[f"ik_hand.{s}"].head).length * 1000
                if d > worst[s][0]:
                    worst[s] = (round(d, 1), f)
        self.act["marks"] = json.dumps({k: v for k, v in self.marks.items() if v}, ensure_ascii=False)
        log(f"{self.name}: {self.end} к ({self.end / FPS:.2f} с), фазы {self.marks}; рука не дотянулась, мм (кадр): "
            f"L {worst['L']} R {worst['R']}")
        return dict(title=self.title, frames=self.end, seconds=round(self.end / FPS, 2), marks=self.marks, reach_mm=worst)


# ================================================================ куски, общие для клипов
OUT_R = (-0.065, 0.0, 0.0)                            # мимо коробки снаружи справа (−X мира — правый бок автомата)
MAG_SWAP = [
    (16, 0, 0, 0, 0, 0), (18, 0, 0, 0, 0, 0), (22, -24, 0, 0, 0, 0), (25, -30, 0, 0, -0.012, -0.05),
    (30, -25, 15, 0.06, 0.06, -0.2), (36, -10, 35, 0.17, 0.19, -0.4), (42, -10, 35, 0.17, 0.19, -0.4),
    (48, -28, 10, 0.02, -0.01, -0.12), (52, -26, 0, 0, -0.006, -0.012), (54, -22, 0, 0, 0, 0),
    (57, 0.8, 0, 0, 0, 0), (58, 0, 0, 0, 0, 0), (60, 0, 0, 0, 0, 0),
]
W_SWAP = [(1, 0, 0, 0, 0, 0, 0), (6, -14, -3, 1.5, 0.018, 0.014, 0.02), (12, -37, -10, 6.5, 0.062, 0.052, 0.074),
          (15, *TILT), (22, -33, -9, 6, 0.06, 0.05, 0.064), (26, *TILT), (40, -29, -6, 5, 0.052, 0.045, 0.062),
          (50, -35, -10, 6, 0.06, 0.05, 0.07), (56, -34, -9.5, 6, 0.06, 0.05, 0.068),
          (57, -34.5, -10.2, 6, 0.06, 0.05, 0.078), (60, *TILT)]
LATCH_SWAP = [(1, 0), (15, 0), (17, 1), (21, 1), (23, 0), (55.5, 0), (56.5, 0.7), (57.5, 0)]
POUCH_D = mag_delta((-10, 35, 0.17, 0.19, -0.4))     # магазин в подсумке (осями автомата)


def shift(keys, d, lo=None, hi=None):
    """Сдвинуть кадры ключей на d (только в промежутке [lo, hi], если задан)."""
    out = []
    for k in keys:
        f = k[0]
        if (lo is None or f >= lo) and (hi is None or f <= hi):
            out.append((f + d, *k[1:]))
        else:
            out.append(k)
    return out


def seg(keys, lo, hi):
    return [k for k in keys if lo <= k[0] <= hi]


def gun_keys(table):
    return [(k[0], tuple(k[1:])) for k in table]


def at_well(k):
    """Магазин у шахты (качок, зацеп, досылание, удар по защёлке): сдвиг меньше 6 см, качок не больше 35°."""
    return max(abs(v) for v in k[3:]) < 0.06 and abs(k[1]) <= 35 and abs(k[2]) < 8


def well_frames(keys):
    """Кадры, где магазин у шахты поворачивается: там ключ кисти — на каждом кадре (иначе кривые Bezier уводят магазин
    в сторону от оси качка — было до 8,5 мм)."""
    out = set()
    for a, b in zip(keys, keys[1:]):
        if at_well(a) and at_well(b) and (abs(a[1] - b[1]) >= 2 or abs(a[2] - b[2]) >= 2):
            out |= set(range(int(math.ceil(a[0])), int(b[0]) + 1))
    return out


def mag_hand(c, keys, pose="mag"):
    """Левая с магазином по пути (кадр, качок, крен, x, y, z) — кисть «как в позе», сдвинутая вместе с магазином;
    у шахты — на каждом кадре по сплайну пути."""
    frames = sorted({k[0] for k in keys} | well_frames(keys))
    c.hand("L", [(f, ("mag", pose, mag_delta(pchip(keys, f)))) for f in frames])


def left_out_to_mag(c, t=0, varn_off=None):
    """Левая с цевья к магазину (кадры 1–14 неполной)."""
    c.hand("L", [(1 + t, "grip"), (5 + t, ("lerp", "grip", "mag", 0.12, (0.01, 0.005, -0.02))),
                 (10 + t, ("lerp", "grip", "mag", 0.62, (0.035, 0.02, -0.06))), (14 + t, ("off", "mag", (0.012, 0.0, -0.025)))])


def left_back_to_grip(c, t):
    """Левая от магазина обратно на цевьё: t — кадр «у магазина»."""
    c.hand("L", [(t, ("off", "mag", (0.015, 0.0, -0.03))), (t + 4, ("lerp", "mag", "grip", 0.5, (0.03, 0.02, -0.05))),
                 (t + 9, "grip")])


def right_index_off(c, keys):
    """Указательный правой: (кадр, 'grip' | 'frame') — на спуске / вдоль корпуса."""
    c.fingers(R_INDEX, keys)


def rack(c, r0, bolt, slam, b0=0.0):
    """Правая крюком тянет рукоятку затвора (кадр r0 — правая уходит с рукоятки): ключи кисти, пальцев, затвора."""
    at0 = BOLT_VEC * b0
    out = Vector(OUT_R)
    c.hand("R", [(r0, "grip"), (r0 + 3, ("off", "grip", out + Vector((0, 0, 0.015)))),
                 (r0 + 6, ("off", "hook", at0 + out + Vector((0.0, -0.01, 0.035)))),
                 (r0 + 9, ("off", "hook", at0 + Vector((-0.012, -0.010, 0.016))))])
    pulls = sorted({r0 + 11} | {int(k[0]) for k in bolt if r0 + 11 <= k[0] <= slam})
    c.hand("R", [(f, ("off", "hook", BOLT_VEC * track(bolt, f))) for f in pulls])
    c.hand("R", [(slam + 2, ("off", "hook", BOLT_VEC * 1.05 + Vector((-0.03, 0.0, 0.02)))),
                 (slam + 5, ("off", "hook", BOLT_VEC * 0.8 + out + Vector((0.0, 0.0, 0.02)))),
                 (slam + 9, ("off", "grip", out + Vector((0.0, 0.0, 0.01)))), (slam + 12, "grip")])
    c.fingers(R_FING, [(r0, "frame"), (r0 + 4, "r_open"), (r0 + 9, "hook_pre"), (r0 + 11, "hook"), (slam, "hook"),
                       (slam + 2, "hook_pre"), (slam + 6, "r_open"), (slam + 12, "grip")])
    c.prop("Bolt pull", bolt)


def bolt_keys(start, b0, pull, slam):
    """Ход затвора: стоит b0 до pull, отвод до упора к slam−1, удар вперёд за 2 кадра."""
    return [(1, b0), (pull, b0), (pull + 2, b0 + (1 - b0) * 0.5), (slam - 1.5, 0.97), (slam - 0.5, 1.0), (slam, 1.0), (slam + 2, 0.0)]


def rack_gun(r0, slam):
    """Автомат на правый бок (рукоятка затвора к глазам) и обратно — как в клипах v13."""
    return [(r0 - 6, (-20, -5, 3, 0.04, 0.035, 0.05)), (r0, (24, -4, -3, 0.0, 0.03, 0.05)),
            (r0 + 3, (26.5, -4.5, -3, 0.0, 0.03, 0.052)), (r0 + 6, ROLL_R), (slam - 6, ROLL_R),
            (slam - 1, (23, -5, -3, 0.0, 0.036, 0.05)), (slam, (23, -5, -3, 0.0, 0.036, 0.05)),
            (slam + 2, (25, -2.5, -3, 0.0, 0.022, 0.052)), (slam + 6, ROLL_R), (slam + 12, (18, -3, -2, 0.0, 0.022, 0.038)),
            (slam + 19, (-2, 0.8, 0.4, 0.0, -0.002, -0.003)), (slam + 23, (0, 0, 0, 0, 0, 0))]


def swap_clip(c, t_ins=0, mag_in=None, left_fingers=None, back=None):
    """Смена магазина (неполная v13, кадры 1–79): левая к магазину, качок, «в подсумок», новый, зацеп, качок до
    щелчка, левая на цевьё. t_ins — сколько кадров вставлено после «нового магазина» (кадр 42) — для «живых»; mag_in —
    свой путь магазина с кадра 42 (без сдвига)."""
    left_out_to_mag(c)
    keys = seg(MAG_SWAP, 16, 42) + (mag_in if mag_in is not None else shift(seg(MAG_SWAP, 48, 60), t_ins))
    mag_hand(c, keys)
    end_hold = keys[-1][0]
    c.hold("Magazine_Control", [(16, 1), (end_hold, 0)])
    left_back_to_grip(c, end_hold + 3)
    lf = [(1, "grip"), (5, "grip"), (10, "free"), (15, "pre"), (17, "mag"), (end_hold - 1, "mag"), (end_hold + 2, "pre"),
          (end_hold + 6, "free"), (end_hold + 12, "grip")]
    c.fingers(L_FING, left_fingers or lf)
    c.prop("Magazine latch press", shift(LATCH_SWAP, t_ins, 50))
    return end_hold


# ================================================================ клипы
REC = {}


def reload_tactical():
    c = Clip("Reload_Tactical", 79, "Неполная перезарядка")
    c.gun(gun_keys(W_SWAP + [(64, -29, -7, 5, 0.05, 0.042, 0.058), (72, 2.5, 1.2, -0.6, -0.003, -0.002, -0.004),
                             (76, 0, 0, 0, 0, 0, 0)]))
    swap_clip(c)
    right_index_off(c, [(1, "grip"), (6, "frame"), (68, "frame"), (74, "grip")])
    c.prop("Rounds remaining", [(1, 30)])
    c.mark(left_to_mag=5, catch=17, mag_hidden=26, mag_new=42, insert=52, seat=57, left_to_grip=61, ready=76)
    return c.finish()


def reload_full(name="Reload_Full", title="Полная перезарядка (затвор правой)", slip=False):
    d = 12 if slip else 0
    end = 114 + d
    c = Clip(name, end, title, state={"Rounds remaining": 0})
    r0 = 70
    slam = r0 + 17 + d
    g = gun_keys(W_SWAP) + [(64, (-20, -5, 3, 0.04, 0.035, 0.05))] + rack_gun(r0, slam)[1:]
    c.gun(g)
    swap_clip(c)
    right_index_off(c, [(1, "grip"), (6, "frame")])
    if slip:
        bolt = [(1, 0), (81, 0), (83, 0.25), (84.5, 0.45), (85.5, 0.45), (87, 0.0), (93, 0.0), (95, 0.5), (slam - 1.5, 0.97),
                (slam - 0.5, 1.0), (slam, 1.0), (slam + 2, 0.0), (end, 0.0)]
        out = Vector(OUT_R)
        c.hand("R", [(r0, "grip"), (r0 + 3, ("off", "grip", out + Vector((0, 0, 0.015)))),
                     (r0 + 6, ("off", "hook", out + Vector((0.0, -0.01, 0.035)))), (r0 + 9, ("off", "hook", Vector((-0.012, -0.010, 0.016)))),
                     (81, ("off", "hook", BOLT_VEC * 0.0)), (84, ("off", "hook", BOLT_VEC * 0.45)),
                     (86, ("off", "hook", BOLT_VEC * 0.62 + Vector((-0.025, 0.0, 0.018)))),     # пальцы сорвались — кисть дальше
                     (89, ("off", "hook", BOLT_VEC * 0.3 + Vector((-0.02, 0.0, 0.025)))),
                     (92, ("off", "hook", Vector((-0.008, -0.012, 0.01)))), (93, ("off", "hook", BOLT_VEC * 0.0))])
        pulls = [f for f in (95, slam - 2, slam - 1, slam)]
        c.hand("R", [(f, ("off", "hook", BOLT_VEC * track(bolt, f))) for f in pulls])
        c.hand("R", [(slam + 2, ("off", "hook", BOLT_VEC * 1.05 + Vector((-0.03, 0.0, 0.02)))),
                     (slam + 5, ("off", "hook", BOLT_VEC * 0.8 + out + Vector((0.0, 0.0, 0.02)))),
                     (slam + 9, ("off", "grip", out + Vector((0.0, 0.0, 0.01)))), (slam + 12, "grip")])
        c.fingers(R_FING, [(r0, "frame"), (r0 + 4, "r_open"), (r0 + 9, "hook_pre"), (r0 + 11, "hook"), (85, "hook"),
                           (87, "hook_pre"), (90, "r_open"), (92, "hook_pre"), (93, "hook"), (slam, "hook"),
                           (slam + 2, "hook_pre"), (slam + 6, "r_open"), (slam + 12, "grip")])
        c.prop("Bolt pull", bolt)
        c.mark(rack_pull=81, slip=85, regrip=92, rack_pull_2=93)
    else:
        rack(c, r0, [(1, 0.0), (81, 0.0), (83, 0.5), (85.5, 0.97), (86.5, 1.0), (87, 1.0), (89, 0.0), (end, 0.0)], slam)
        c.mark(rack_pull=81)
    c.prop("Rounds remaining", [(1, 0), (41, 0), (42, 30)])
    c.mark(left_to_mag=5, catch=17, mag_hidden=26, mag_new=42, insert=52, seat=57, left_to_grip=61, roll_right=61,
           rack_reach=72, rack_release=slam, right_to_grip=slam + 3, ready=slam + 23)
    return c.finish()


def reload_fast(name="Reload_Fast", title="Быстрая перезарядка (старый на землю)", full=False, stuck=False):
    """Быстрая: левая сразу к подсумку, новым магазином — чётко — бьёт по защёлке, старый вываливается; stuck — старый
    застрял, второй удар."""
    s = 9 if stuck else 0
    K = 13                                            # новый магазин в руке (у подсумка)
    strike = 29
    mag = [(K, -10, 35, 0.17, 0.19, -0.4), (K + 2, -12, 32, 0.16, 0.18, -0.36), (22, -33, 12, 0.035, 0.055, -0.095),
           (25, -34, 7, 0.018, 0.042, -0.074), (27, -34, 6, 0.016, 0.040, -0.071),
           (strike, -31, 1, 0.004, 0.004, -0.050)]
    if stuck:                                         # отвёл, пауза — заметил; второй удар по застрявшему
        mag += [(31, -32, 3, 0.010, 0.020, -0.062), (35, -32, 3, 0.010, 0.020, -0.062), (36, -32.5, 4, 0.012, 0.024, -0.066),
                (38, -30, 0, 0.002, 0.0, -0.046)]
    mag += [(32 + s, -29, 0, 0.0, -0.004, -0.03), (35 + s, -27, 0, 0, -0.006, -0.014), (37 + s, -22, 0, 0, 0, 0),
            (40 + s, 0.8, 0, 0, 0, 0), (41 + s, 0, 0, 0, 0, 0), (43 + s, 0, 0, 0, 0, 0)]
    seat = 40 + s
    W = [(1, 0, 0, 0, 0, 0, 0), (5, -14, -3, 1.5, 0.018, 0.014, 0.02), (11, -37, -10, 6.5, 0.062, 0.052, 0.074), (14, *TILT),
         (26, -33, -9, 6, 0.06, 0.05, 0.066), (strike, -36, -10.5, 6.2, 0.06, 0.044, 0.078), (strike + 3, *TILT)]
    if stuck:
        W += [(38, -35.5, -10.3, 6.1, 0.06, 0.045, 0.076), (41, *TILT)]
    W += [(seat - 1, -34, -9.5, 6, 0.06, 0.05, 0.068), (seat, -34.5, -10.2, 6, 0.06, 0.05, 0.078), (seat + 3, *TILT)]
    if full:
        r0 = seat + 13
        slam = r0 + 17
        end = slam + 27
        g = gun_keys(W) + [(seat + 8, (-20, -5, 3, 0.04, 0.035, 0.05))] + rack_gun(r0, slam)[1:]
    else:
        end = seat + 26
        g = gun_keys(W + [(seat + 8, -29, -7, 5, 0.05, 0.042, 0.058), (seat + 16, 2.5, 1.2, -0.6, -0.003, -0.002, -0.004),
                          (seat + 20, 0, 0, 0, 0, 0, 0)])
    c = Clip(name, end, title, state={"Rounds remaining": 0 if full else 12})
    c.gun(g)
    pouch_hand = POUCH_D @ HAND_W["L"]["mag"]
    c.hand("L", [(1, "grip"), (4, ("w", lerp_m(HAND_W["L"]["grip"], pouch_hand, 0.12))),
                 (9, ("w", lerp_m(HAND_W["L"]["grip"], pouch_hand, 0.72)))])
    mag_hand(c, mag)
    c.hold("Magazine_Control", [(K, 1), (mag[-1][0], 0)])
    left_back_to_grip(c, mag[-1][0] + 3)
    c.fingers(L_FING, [(1, "grip"), (4, "grip"), (8, "free"), (K - 1, "pre"), (K, "mag"), (mag[-1][0] - 1, "mag"),
                       (mag[-1][0] + 2, "pre"), (mag[-1][0] + 6, "free"), (mag[-1][0] + 12, "grip")])
    # старый магазин: в шахте с кадра K, новый бьёт по защёлке — качок вперёд у зацепа, дальше падает сам
    c.scale("SpareMag", [(K, 1)])
    old = [(1, (0, 0, 0, 0, 0)), (strike - 1, (0, 0, 0, 0, 0)), (strike + 0.5, (-9, 0, 0, 0, 0))]
    if stuck:
        old += [(strike + 2, (-18, 0, 0, -0.004, -0.008)), (37, (-18, 0, 0, -0.004, -0.008)), (39, (-25, 0, 0, -0.004, -0.012))]
        free = 39
    else:
        old += [(strike + 2, (-25, 0, 0, -0.004, -0.012))]
        free = strike + 2
    c.wmat("SpareMag", [(f, mag_delta(k)) for f, k in old])
    c.fall("SpareMag", free)
    c.prop("Magazine latch press", [(1, 0), (strike - 1.5, 0), (strike - 0.5, 1), (strike + 2, 1), (strike + 4, 0),
                                    (seat - 1.5, 0), (seat - 0.5, 0.7), (seat + 0.5, 0)])
    c.prop("Rounds remaining", [(1, 0 if full else 12), (K, 30)])
    if full:
        rack(c, r0, [(1, 0.0), (r0 + 11, 0.0), (r0 + 13, 0.5), (slam - 1.5, 0.97), (slam - 0.5, 1.0), (slam, 1.0),
                     (slam + 2, 0.0), (end, 0.0)], slam)
        right_index_off(c, [(1, "grip"), (6, "frame")])
        c.mark(roll_right=seat + 5, rack_reach=r0 + 2, rack_pull=r0 + 11, rack_release=slam, right_to_grip=slam + 3,
               ready=slam + 23)
    else:
        right_index_off(c, [(1, "grip"), (6, "frame"), (seat + 12, "frame"), (seat + 18, "grip")])
        c.mark(ready=seat + 20)
    c.mark(left_to_pouch=4, mag_new=K, strike=strike, old_falls=free, insert=35 + s, seat=seat, left_to_grip=seat + 6)
    if stuck:
        c.mark(stuck=strike + 2, strike_2=38)
    return c.finish()


def reload_living(name, title, kind):
    """Неполная с «живой» вставкой после нового магазина (кадр 42): drop — старый выскользнул (раньше, после качка);
    miss_a / miss_b — не попал в шахту; wrong_a / wrong_b — не той стороной."""
    if kind == "drop":
        d = 10
        c = Clip(name, 79 + d, title)
        # кисть с магазином: качок, потом магазин выскальзывает (27) — пустая кисть замирает и идёт к подсумку
        left_out_to_mag(c)
        k1 = seg(MAG_SWAP, 16, 25)
        mag_hand(c, k1)
        c.hold("Magazine_Control", [(16, 1)])
        hand27 = mag_delta((-28, 4, 0.012, 0.012, -0.08))
        c.hand("L", [(27, ("mag", "mag", hand27)), (31, ("mag", "mag", mag_delta((-27, 6, 0.016, 0.016, -0.09))))])
        rest = shift(seg(MAG_SWAP, 30, 60), d)
        mag_hand(c, rest)
        c.hold("Magazine_Control", [(rest[-1][0], 0)])
        # магазин в кисти прячется на время (уронили — его место занимает SpareMag), новый появляется у подсумка
        c.bone("mag.L", 27, B["mag"]["mag.L"])
        sc = B["mag"]["mag.L"].copy()
        hidden = Matrix.LocRotScale(sc.translation, sc.to_quaternion(), Vector((0.001,) * 3))
        c.bone("mag.L", 28, hidden)
        c.bone("mag.L", 46 + d - 2, hidden)
        c.bone("mag.L", 46 + d, B["mag"]["mag.L"])
        G27 = c.gun_at(27)
        c.scale("SpareMag", [(28, 1)])
        S.frame_set(27)
        update()
        c.wmat("SpareMag", [(28, ("world", G27 @ WR_REST @ wr.data.bones["SpareMag"].matrix_local.copy()))])
        held = c.bone_world("Magazine_Control", 27)
        c.wmat("SpareMag", [(28, ("world", held))])
        c.fall("SpareMag", 28, v0=(0.0, -0.1, -0.3))
        end_hold = rest[-1][0]
        left_back_to_grip(c, end_hold + 3)
        c.fingers(L_FING, [(1, "grip"), (5, "grip"), (10, "free"), (15, "pre"), (17, "mag"), (26, "mag"), (28, "pre"),
                           (31, "free"), (44 + d, "pre"), (46 + d, "mag"), (end_hold - 1, "mag"), (end_hold + 2, "pre"),
                           (end_hold + 6, "free"), (end_hold + 12, "grip")])
        c.prop("Magazine latch press", shift(LATCH_SWAP, d, 50))
        W = gun_keys(seg(W_SWAP, 1, 26)) + [(30, (-35, -10, 6, 0.06, 0.05, 0.072)), (33, TILT)] + \
            [(k[0] + d, k[1]) for k in gun_keys(seg(W_SWAP, 40, 60))] + \
            [(64 + d, (-29, -7, 5, 0.05, 0.042, 0.058)), (72 + d, (2.5, 1.2, -0.6, -0.003, -0.002, -0.004)), (76 + d, (0, 0, 0, 0, 0, 0))]
        c.gun(W)
        right_index_off(c, [(1, "grip"), (6, "frame"), (68 + d, "frame"), (74 + d, "grip")])
        c.mark(left_to_mag=5, catch=17, slip=27, mag_hidden=36 + d, mag_new=42 + d, insert=52 + d, seat=57 + d,
               left_to_grip=61 + d, ready=76 + d)
        return c.finish()
    # ---- после нового магазина (42): своя вставка
    if kind == "miss_a":                              # передом о край шахты, отвёл, вторая попытка
        ins = [(48, -28, 10, 0.02, -0.01, -0.12), (51, -27, 2, 0.0, -0.014, -0.032), (53, -27, 4, 0.0, -0.010, -0.044),
               (57, -27, 4, 0.0, -0.010, -0.046), (60, -28, 6, 0.005, -0.004, -0.07), (63, -26, 0, 0, -0.006, -0.012),
               (65, -22, 0, 0, 0, 0), (68, 0.8, 0, 0, 0, 0), (69, 0, 0, 0, 0, 0), (71, 0, 0, 0, 0, 0)]
        marks = dict(miss=51, retry=60, insert=63, seat=68)
    elif kind == "miss_b":                            # мимо шахты вбок, вернул, вставил
        ins = [(48, -28, 10, 0.03, -0.01, -0.11), (51, -27, 5, 0.032, -0.008, -0.03), (53, -27, 5, 0.034, -0.008, -0.026),
               (57, -27, 5, 0.034, -0.008, -0.028), (60, -27, 3, 0.012, -0.006, -0.045), (63, -26, 0, 0, -0.006, -0.012),
               (65, -22, 0, 0, 0, 0), (68, 0.8, 0, 0, 0, 0), (69, 0, 0, 0, 0, 0), (71, 0, 0, 0, 0, 0)]
        marks = dict(miss=51, retry=60, insert=63, seat=68)
    elif kind in ("wrong_a", "wrong_b"):              # не той стороной: упёрся / заметил, развернул в кисти
        if kind == "wrong_a":
            ins = [(48, -28, 10, 0.02, -0.01, -0.12), (52, -27, 2, 0.0, -0.008, -0.045), (55, -27, 2, 0.0, -0.008, -0.048),
                   (60, -27, 3, 0.0, -0.008, -0.05), (64, -28, 10, 0.03, 0.02, -0.14), (72, -28, 10, 0.03, 0.02, -0.14)]
            flip_from, flip_to, marks = 64, 72, dict(try_=52, notice=55, flip=64)
        else:
            ins = [(48, -28, 10, 0.02, -0.01, -0.12), (51, -28, 10, 0.02, -0.01, -0.12), (55, -28, 10, 0.03, 0.01, -0.14),
                   (63, -28, 10, 0.03, 0.01, -0.14)]
            flip_from, flip_to, marks = 55, 63, dict(try_=48, notice=51, flip=55)
        t = flip_to + 4
        ins += [(t, -28, 10, 0.02, -0.01, -0.12), (t + 4, -26, 0, 0, -0.006, -0.012), (t + 6, -22, 0, 0, 0, 0),
                (t + 9, 0.8, 0, 0, 0, 0), (t + 10, 0, 0, 0, 0, 0), (t + 12, 0, 0, 0, 0, 0)]
        marks.update(insert=t + 4, seat=t + 9)
    d = ins[-1][0] - 60
    c = Clip(name, 79 + d, title)
    swap_clip(c, t_ins=d, mag_in=ins)
    seat = marks["seat"]
    W = gun_keys(seg(W_SWAP, 1, 40)) + [(48, (-35, -10, 6, 0.06, 0.05, 0.07)), (seat - 1, (-34, -9.5, 6, 0.06, 0.05, 0.068)),
                                        (seat, (-34.5, -10.2, 6, 0.06, 0.05, 0.078)), (seat + 3, TILT),
                                        (64 + d, (-29, -7, 5, 0.05, 0.042, 0.058)), (72 + d, (2.5, 1.2, -0.6, -0.003, -0.002, -0.004)),
                                        (76 + d, (0, 0, 0, 0, 0, 0))]
    if kind == "miss_a":
        W += [(52, (-36, -10.5, 6.2, 0.06, 0.044, 0.076))]                    # толчок о край
    W.sort(key=lambda k: k[0])
    c.gun(W)
    c.prop("Magazine latch press", [(1, 0), (15, 0), (17, 1), (21, 1), (23, 0), (seat - 1.5, 0), (seat - 0.5, 0.7), (seat + 0.5, 0)])
    if kind.startswith("wrong"):                      # магазин в кисти развёрнут, потом поворачивается
        axis = Vector((0, 0, 1)) if kind == "wrong_a" else Vector((1, 0, 0))
        rest = wr.data.bones["Magazine_Control"].matrix_local
        mc = WR_REST.inverted() @ MAG_C_W                  # середина магазина в осях рига оружия
        Rr = about(mc, Matrix.Rotation(math.pi, 3, axis))
        local = rest.inverted() @ Rr @ rest
        wrong = B["mag"]["mag.L"] @ local
        c.bone("mag.L", 1, B["mag"]["mag.L"])
        c.bone("mag.L", 41, wrong)
        c.bone("mag.L", flip_from, wrong)
        half = B["mag"]["mag.L"] @ (rest.inverted() @ about(mc, Matrix.Rotation(math.pi / 2, 3, axis)) @ rest)
        c.bone("mag.L", (flip_from + flip_to) // 2, half)
        c.bone("mag.L", flip_to, B["mag"]["mag.L"])
        c.fingers(L_FING, [(flip_from, "mag"), (flip_from + 2, "pre"), (flip_to - 2, "pre"), (flip_to, "mag")])
    right_index_off(c, [(1, "grip"), (6, "frame"), (68 + d, "frame"), (74 + d, "grip")])
    c.mark(left_to_mag=5, catch=17, mag_hidden=26, mag_new=42, left_to_grip=seat + 4, ready=76 + d, **{k.rstrip("_"): v for k, v in marks.items()})
    return c.finish()


def mag_check():
    """Проверка магазина (v13): вынуть, к глазам правым боком (прорези), перехват ниже; держать R — дольше; вернуть."""
    END = 104
    MK = [(16, 0, 0, 0, 0, 0), (18, 0, 0, 0, 0, 0), (22, -22, 0, 0, 0, 0), (27, -30, 0, 0, -0.012, -0.05),
          (64, -30, 0, 0, -0.012, -0.05), (73, -28, 0, 0.0, -0.01, -0.1), (76.5, -26, 0, 0, -0.006, -0.012),
          (78, -22, 0, 0, 0, 0), (81, 0.8, 0, 0, 0, 0), (82, 0, 0, 0, 0, 0), (84, 0, 0, 0, 0, 0)]
    CAM_W = [(1, 0), (23, 0), (39, 1), (57, 1), (74, 0), (END, 0)]
    W = [(1, 0, 0, 0, 0, 0, 0), (6, -14, -3, 1.5, 0.018, 0.014, 0.02), (12, -36, -9.6, 6.3, 0.061, 0.051, 0.072),
         (15, *TILT), (22, -33, -9, 6, 0.06, 0.05, 0.064), (36, *LOW), (56, -15, -1.5, 2, 0.01, 0.02, -0.022),
         (70, -35, -10, 6, 0.06, 0.05, 0.07), (80, -34, -9.5, 6, 0.06, 0.05, 0.068), (81, -34.5, -10.2, 6, 0.06, 0.05, 0.078),
         (84, *TILT), (89, -29, -7, 5, 0.05, 0.042, 0.058), (97, 2.5, 1.2, -0.6, -0.003, -0.002, -0.004), (101, 0, 0, 0, 0, 0, 0)]
    c = Clip("Mag_Check", END, "Проверка магазина", versions="grip", state={"Rounds remaining": 12})
    c.gun(gun_keys(W))
    left_out_to_mag(c)
    # место магазина в кисти: до перехвата — «на магазине», у глаз — «хват ниже» (поза 56)
    c.bone("mag.L", 28, B["mag"]["mag.L"])
    c.bone("mag.L", 39, B["check"]["mag.L"])
    c.bone("mag.L", 58, B["check"]["mag.L"])
    c.bone("mag.L", 68, B["mag"]["mag.L"])
    rel = arms.data.bones["hand.L"].matrix_local.inverted() @ arms.data.bones["mag.L"].matrix_local
    cv = CT.bone_curves(bag_of(c.act, arms)).get("mag.L", {})

    def cam_world(f):
        t = f / FPS
        target = EYE + Vector((0.035, -0.36, -0.065)) + Vector((0.004 * math.sin(t * 2.1), 0.0, 0.003 * math.sin(t * 1.7)))
        rot = (Euler((math.radians(10 + 2.5 * math.sin(t * 1.3)), 0, 0), "XYZ").to_matrix()
               @ Euler((0, 0, math.radians(-90 + 6 * math.sin(t * 1.1))), "XYZ").to_matrix())
        return Matrix.Translation(target) @ rot.to_4x4() @ Matrix.Translation(-MAG_C_W)

    frames = sorted({int(k[0]) for k in MK if 16 <= k[0] <= 84} | {28, 33, 39, 45, 51, 57, 62, 68} | well_frames(MK))
    keys = []
    for f in frames:
        Gf = c.gun_at(f)
        w = min(max(track(CAM_W, f), 0.0), 1.0)
        Dw = mag_delta(pchip(MK, f))
        if w > 0:
            Dw = lerp_m(Dw, Gf.inverted() @ cam_world(f), w)
        MC = Gf @ Dw @ MAG_REST_W                     # кость магазина в мире
        mb = CT.read(cv, arms.pose.bones["mag.L"], f) if cv else B["mag"]["mag.L"]
        Hw = MC @ mb.inverted() @ rel.inverted()      # кисть (голова hand.L) в мире
        keys.append((f, ("world", AW @ (AWI @ Hw))))
    c.hand("L", keys)
    c.hold("Magazine_Control", [(16, 1), (84, 0)])
    left_back_to_grip(c, 87)
    c.fingers(L_FING, [(1, "grip"), (5, "grip"), (10, "free"), (15, "pre"), (17, "mag"), (28, "mag"), (33, "pre"), (39, "check"),
                       (58, "check"), (63, "pre"), (68, "mag"), (83, "mag"), (86, "pre"), (90, "free"), (96, "grip")])
    right_index_off(c, [(1, "grip"), (6, "frame"), (93, "frame"), (99, "grip")])
    c.prop("Magazine latch press", [(1, 0), (15, 0), (17, 1), (21, 1), (23, 0), (79.5, 0), (80.5, 0.7), (81.5, 0)])
    c.mark(left_to_mag=5, catch=17, to_eyes=24, hold_start=40, hold_end=57, insert=76, seat=81, left_to_grip=85, ready=101)
    return c.finish()


def mag_check_big(which):
    """Проверка магазина 45 / барабана 60 без снятия: автомат поворачивается к глазам стороной с окнами остатка."""
    TARGET = {
        "45": dict(point=(0.0515, 0.0155, -0.1114), normal=(0.0, 1.0, 0.0), d=0.34, right=0.03, up=-0.06,
                   axis=(1.0, 0.0, 0.0), axis_to=(-0.80, 0.50, 0.20)),
        "60": dict(point=(0.0089, 0.0, -0.1468), normal=(-0.9455, 0.0, -0.3256), d=0.34, right=0.02, up=-0.06,
                   axis=(0.0, 0.0, 1.0), axis_to=(0.30, 0.0, 0.95), oblique=40.0)}[which]
    m = magob.matrix_world
    pw = m @ Vector(TARGET["point"])
    n0 = (m.to_3x3() @ Vector(TARGET["normal"])).normalized()
    a0 = (m.to_3x3() @ Vector(TARGET["axis"])).normalized()
    target = EYE + CAM_FWD * TARGET["d"] + CAM_RT * TARGET["right"] + CAM_UP * TARGET["up"]
    n1 = Matrix.Rotation(math.radians(TARGET.get("oblique", 0.0)), 3, CAM_UP) @ (EYE - target).normalized()
    ax, ay, az = TARGET["axis_to"]
    a1 = (CAM_RT * ax + CAM_FWD * ay + CAM_UP * az).normalized()

    def frame(n, a):
        a = (a - n * a.dot(n)).normalized()
        return Matrix((n, a, n.cross(a))).transposed()
    rot = frame(n1, a1) @ frame(n0, a0).transposed()
    show = Matrix.Translation(target - G.GRIP_W - rot @ (pw - G.GRIP_W)) @ about(G.GRIP_W, rot)
    q = show.to_quaternion()

    def part(k):
        R = Quaternion().slerp(q, k).to_matrix()
        return Matrix.Translation(show.translation * k) @ about(G.GRIP_W, R) if False else \
            Matrix.Translation((target - G.GRIP_W - rot @ (pw - G.GRIP_W)) * k) @ about(G.GRIP_W, R)
    END = 60
    c = Clip(f"Mag_Check_{which}", END, f"Проверка {'магазина 45' if which == '45' else 'барабана 60'} (без снятия)",
             versions="grip", variant=dict(mag=which), state={"Rounds remaining": 30})
    sway = Matrix.Translation(Vector((0.002, 0.0, 0.002)))
    c.gun([(1, (0, 0, 0, 0, 0, 0)), (6, part(0.22)), (14, part(0.9)), (20, part(1.0)), (30, sway @ part(1.0)), (40, part(1.0)),
           (47, part(0.62)), (54, (0, 0, 0, 0, 0, 0)), (57, (0, 0, 0, 0, 0, 0))])
    right_index_off(c, [(1, "grip"), (5, "frame"), (52, "frame"), (57, "grip")])
    c.mark(turn=6, hold_start=20, hold_end=40, ready=57)
    return c.finish()


def jam_clear(name="Jam_Clear", title="Устранение задержки", slip=False):
    """Задержка (v13): гильза зажата в окне, затвор приоткрыт; автомат на правый бок, правая отводит затвор, гильза
    выпадает, затвор досылает. slip — пальцы сорвались с рукоятки, второй рывок."""
    d = 12 if slip else 0
    END = 46 + d
    r0 = 10
    slam = r0 + 17 + d
    c = Clip(name, END, title, versions="grip", state={"Bolt pull": JAM_OPEN, "Rounds remaining": 14})
    c.gun([(1, (0, 0, 0, 0, 0, 0)), (5, (9, -1.5, -1, 0.0, 0.012, 0.02)), (10, (24, -4, -3, 0.0, 0.03, 0.05)),
           (13, (26.5, -4.5, -3, 0.0, 0.03, 0.052)), (16, ROLL_R), (slam - 6, ROLL_R), (slam - 1, (23, -5, -3, 0.0, 0.036, 0.05)),
           (slam, (23, -5, -3, 0.0, 0.036, 0.05)), (slam + 2, (25, -2.5, -3, 0.0, 0.022, 0.052)), (slam + 6, ROLL_R),
           (slam + 11, (14, -2.5, -1.5, 0.0, 0.016, 0.028)), (slam + 16, (-1.5, 0.6, 0.3, 0.0, -0.002, -0.002)),
           (END, (0, 0, 0, 0, 0, 0))])
    right_index_off(c, [(1, "grip"), (5, "frame")])
    if slip:
        bolt = [(1, JAM_OPEN), (21, JAM_OPEN), (23, 0.5), (24, 0.55), (25.5, JAM_OPEN), (33, JAM_OPEN), (35, 0.66),
                (slam - 1.5, 0.97), (slam - 0.5, 1.0), (slam, 1.0), (slam + 2, 0.0), (END, 0.0)]
        out = Vector(OUT_R)
        at0 = BOLT_VEC * JAM_OPEN
        c.hand("R", [(r0, "grip"), (r0 + 3, ("off", "grip", out + Vector((0, 0, 0.015)))),
                     (r0 + 6, ("off", "hook", at0 + out + Vector((0.0, -0.01, 0.035)))),
                     (r0 + 9, ("off", "hook", at0 + Vector((-0.012, -0.010, 0.016)))), (21, ("off", "hook", at0)),
                     (24, ("off", "hook", BOLT_VEC * 0.55)), (26, ("off", "hook", BOLT_VEC * 0.7 + Vector((-0.025, 0.0, 0.018)))),
                     (29, ("off", "hook", BOLT_VEC * 0.5 + Vector((-0.02, 0.0, 0.025)))), (32, ("off", "hook", at0 + Vector((-0.008, -0.012, 0.01)))),
                     (33, ("off", "hook", at0)), (35, ("off", "hook", BOLT_VEC * 0.66)), (slam - 1, ("off", "hook", BOLT_VEC * 0.99)),
                     (slam, ("off", "hook", BOLT_VEC)), (slam + 2, ("off", "hook", BOLT_VEC * 1.05 + Vector((-0.03, 0.0, 0.02)))),
                     (slam + 5, ("off", "hook", BOLT_VEC * 0.8 + out + Vector((0.0, 0.0, 0.02)))),
                     (slam + 9, ("off", "grip", out + Vector((0.0, 0.0, 0.01)))), (slam + 12, "grip")])
        c.fingers(R_FING, [(r0, "frame"), (r0 + 4, "r_open"), (r0 + 9, "hook_pre"), (r0 + 11, "hook"), (24, "hook"),
                           (26, "hook_pre"), (29, "r_open"), (32, "hook_pre"), (33, "hook"), (slam, "hook"),
                           (slam + 2, "hook_pre"), (slam + 6, "r_open"), (slam + 12, "grip")])
        c.prop("Bolt pull", bolt)
        free = 37
        c.mark(slip=25, regrip=32, rack_pull_2=33)
    else:
        rack(c, r0, [(1, JAM_OPEN), (21, JAM_OPEN), (23, 0.66), (25.5, 0.97), (26.5, 1.0), (27, 1.0), (29, 0.0), (END, 0.0)],
             slam, b0=JAM_OPEN)
        free = r0 + 13
    # зажатая гильза: стоит в окне, пока затвор её держит, потом вылетает вправо-вверх и падает
    c.scale("JamCase", [(1, 1)])
    c.wmat("JamCase", [(free, "rest")])
    c.fall("JamCase", free, v0=(-0.75, 0.2, 0.55), spin=(14.0, 9.0, 5.0))
    c.mark(jam=1, roll_right=5, rack_pull=21, case_out=free + 1, rack_release=slam, right_to_grip=slam + 3, ready=slam + 16)
    return c.finish()


def fire_mode(src, dst):
    """Переводчик огня большим пальцем правой (v13): кисть к правой стенке коробки, подушечка на полочку рычага, щелчок,
    кисть обратно. Вниз (АВ → 2 → ОД) — палец сверху полочки, вверх (ОД → АВ) — снизу."""
    down = MODE[dst] != 1.0
    pose = "sel_down" if down else "sel_up"
    END = 18
    name = f"Fire_Mode_{src.title()}_{dst.title()}"
    ru = dict(auto="АВ", burst="«2»", semi="ОД")
    c = Clip(name, END, f"Переводчик огня: {ru[src]} → {ru[dst]}", versions="grip",
             state={"Fire mode": MODE[dst], "Selector from mode": MODE[src], "Selector blend": 0.0})
    c.hand("R", [(1, "grip"), (6, pose), (13, pose), (END, "grip")])
    c.fingers([n for n in R_FING if n not in R_THUMB], [(1, "grip"), (6, pose), (13, pose), (END, "grip")])
    # большой: подушечка на полочке до и после щелчка — расчётом по рычагу в этих положениях
    S.frame_set(8)
    update()
    pads = {}
    for f, blend in ((8, 0.0), (11, 1.0)):
        for n in A_BONES:
            arms.pose.bones[n].matrix_basis = B[pose][n]
        root["Fire mode"], root["Selector from mode"], root["Selector blend"] = MODE[dst], MODE[src], blend
        root.update_tag()
        update()
        to_v = root.matrix_world.inverted()
        dgr = bpy.context.evaluated_depsgraph_get()
        ob = bpy.data.objects["Selector_Steel"].evaluated_get(dgr)
        me = ob.to_mesh()
        pts = [ob.matrix_world @ v.co for v in me.vertices]
        ob.to_mesh_clear()
        sh = [p for p in pts if 0.134 <= (to_v @ p).x <= 0.152]
        cc = to_v @ (sum(sh, Vector()) / len(sh))
        zs = [(to_v @ p).z for p in sh]
        cc.z = (max(zs) + 0.007) if down else (min(zs) - 0.007)
        cc.y -= 0.006
        finger_to(arms, glove, "R", "thumb", root.matrix_world @ cc)
        pads[f] = {n: arms.pose.bones[n].matrix_basis.copy() for n in R_THUMB}
    c.fingers(R_THUMB, [(1, "grip"), (3, "grip"), (6, pose), (8, pads[8]), (11, pads[11]), (13, pose), (16, "grip")])
    c.prop("Fire mode", [(1, MODE[dst])])
    c.prop("Selector from mode", [(1, MODE[src])])
    c.prop("Selector blend", [(1, 0.0), (8, 0.0), (11, 1.0), (END, 1.0)])
    c.mark(hand_to_lever=6, push=8, click=11, back=13, ready=END)
    return c.finish()


def fire():
    c = Clip("Fire", 10, "Выстрел: указательный жмёт спуск", versions="grip")
    c.fingers(R_INDEX, [(3, "pressed"), (5, "pressed"), (8, "grip")])
    c.prop("Trigger pull", [(1, 0), (3, 1), (5, 1), (8, 0)])
    c.mark(press=3, reset=8)
    return c.finish()


def dry_fire():
    c = Clip("Dry_Fire", 16, "Щелчок вхолостую", versions="grip", state={"Rounds remaining": 0})
    c.fingers(R_INDEX, [(5, "pressed"), (9, "pressed"), (13, "grip")])
    c.prop("Trigger pull", [(1, 0), (5, 1), (9, 1), (13, 0)])
    c.gun([(5, (0, 0, 0, 0, 0, 0)), (6, (0.4, 0.3, 0, 0, -0.001, 0)), (8, (0, 0, 0, 0, 0, 0))])
    c.mark(press=5, release=13)
    return c.finish()


def finger(on):
    name = "Finger_On" if on else "Finger_Off"
    c = Clip(name, 8, "Палец на спуск" if on else "Палец со спуска", versions="grip")
    c.fingers(R_INDEX, [(1, "frame" if on else "grip"), (6, "grip" if on else "frame"), (8, "grip" if on else "frame")])
    c.mark(**({"finger_on": 6} if on else {"finger_off": 6}))
    return c.finish()


AWAY_L = Matrix.Translation(EYE + CAM_FWD * 0.22 - CAM_RT * 0.10 - CAM_UP * 0.50) @ HAND_W["L"]["free"].to_3x3().to_4x4()
LOW_OUT = (35, 40, -25, -0.10, 0.05, -0.32)           # автомат опущен вправо-вниз, за кадром


def draw():
    c = Clip("Draw", 26, "Достать автомат", versions="grip")
    c.gun([(1, LOW_OUT), (10, (14, 14, -8, -0.04, 0.02, -0.12)), (18, (-2, -2, 1, 0.003, -0.004, 0.006)),
           (22, (0.6, 0.4, 0, 0, 0.001, -0.001)), (26, (0, 0, 0, 0, 0, 0))])
    c.hand("L", [(1, ("world", AWAY_L)), (10, ("world", AWAY_L)), (16, ("off", "grip", (0.02, 0.03, -0.04))), (20, "grip")])
    c.fingers(L_FING, [(1, "free"), (14, "free"), (20, "grip")])
    right_index_off(c, [(1, "frame"), (18, "frame"), (24, "grip")])
    c.mark(raise_=1, left_on=18, ready=24)
    c.marks["raise"] = c.marks.pop("raise_")
    return c.finish()


def holster():
    END = 22
    c = Clip("Holster", END, "Убрать автомат", versions="grip")
    c.gun([(1, (0, 0, 0, 0, 0, 0)), (6, (-1.5, -1.0, 0.5, 0.004, 0.004, 0.008)), (14, (14, 14, -8, -0.04, 0.02, -0.12)), (END, LOW_OUT)])
    c.hand("L", [(1, "grip"), (4, ("off", "grip", (0.02, 0.03, -0.04))), (10, ("world", AWAY_L)), (END, ("world", AWAY_L))])
    c.fingers(L_FING, [(1, "grip"), (6, "free"), (END, "free")])
    right_index_off(c, [(1, "grip"), (5, "frame"), (END, "frame")])
    c.mark(left_off=4, lower=8)
    return c.finish()


def aim(point_local, ahead, right, up, axis_cam, up_cam):
    """Сдвиг автомата в мире: точка автомата — перед глазами, ствол и верх — по осям камеры."""
    def in_cam(v):
        return (CAM_RT * v[0] + CAM_FWD * v[1] + CAM_UP * v[2]).normalized()

    def frame(a, u):
        u = (u - a * a.dot(u)).normalized()
        return Matrix((a, u, a.cross(u))).transposed()
    p0 = WR_REST @ Vector(point_local)
    a0 = (WR_REST.to_3x3() @ Vector((1, 0, 0))).normalized()
    u0 = (WR_REST.to_3x3() @ Vector((0, 0, 1))).normalized()
    R = frame(in_cam(axis_cam), in_cam(up_cam)) @ frame(a0, u0).transposed()
    target = EYE + CAM_FWD * ahead + CAM_RT * right + CAM_UP * up
    return Matrix.Translation(target - R @ p0) @ R.to_4x4()


def inspect():
    """Осмотр (три нажатия I): левым боком к глазам, дулом вверх, прикладом вниз ~45° — руки замирают (места обвесов);
    правым боком — видно затвор и переводчик; обратно в хват."""
    END = 150
    LEFT = aim((0.22, 0, 0.0), 0.50, 0.04, -0.02, (-0.707, 0.0, 0.707), (0.707, 0.0, 0.707))
    RIGHT = aim((0.15, 0, 0.0), 0.42, 0.06, -0.10, (0.15, 0.95, 0.10), (-0.95, 0.15, 0.0))
    sway = Matrix.Translation(Vector((0.0, 0.0, 0.003))) @ Matrix.Rotation(math.radians(1.2), 4, "Z")
    c = Clip("Inspect", END, "Осмотр (три нажатия I)", versions="grip")
    c.gun([(1, (0, 0, 0, 0, 0, 0)), (8, (8, -2, 0, -0.01, 0.0, 0.01)), (22, LEFT), (41, sway @ LEFT), (60, LEFT),
           (82, RIGHT), (101, sway @ RIGHT), (120, RIGHT),
           (134, (-5, 1.5, 0, 0.004, 0, 0.004)), (140, (1.5, -0.5, 0, 0, 0, 0)), (146, (0, 0, 0, 0, 0, 0))])
    c.hand("L", [(4, "grip"), (14, ("world", AWAY_L)), (126, ("world", AWAY_L)), (138, ("off", "grip", (0.02, 0.03, -0.04))),
                 (142, "grip")])
    c.fingers(L_FING, [(4, "grip"), (10, "free"), (130, "free"), (142, "grip")])
    right_index_off(c, [(1, "grip"), (6, "frame"), (138, "frame"), (146, "grip")])
    c.mark(side_left=22, side_left_end=60, side_right=82, side_right_end=120, ready=146)
    return c.finish()


def light_button():
    c = Clip("Light_Button", 18, "Кнопка фонаря (большой левой)", versions="", variant=dict(light=True))
    c.hand("L", [(1, "grip"), (6, "light"), (11, "light"), (16, "grip")])
    c.fingers(L_THUMB, [(1, "grip"), (6, "light"), (8, "light"), (11, "light"), (16, "grip")])
    c.mark(reach=6, press=8, back=11)
    return c.finish()


def suppressor(on):
    """Накрутить / снять глушитель: автомат дулом к середине кадра (поза 66), левая приносит глушитель снизу,
    наживляет, крутит перехватами (глушитель круглый — поворот кисти вместе с ним не виден), дотягивает."""
    END = 100 if on else 96
    c = Clip("Suppressor_On" if on else "Suppressor_Off", END, "Накрутить глушитель" if on else "Снять глушитель",
             versions="grip")
    axis_w = (SUPP_W.to_3x3() @ (WR_REST.to_3x3() @ Vector((1, 0, 0)))).normalized()
    muzzle = WR_REST @ wr.data.bones["Socket_Muzzle"].head_local
    sw = {}

    def turn(deg, fwd):
        """Кисть на глушителе, повёрнута вокруг оси ствола на deg и сдвинута вдоль неё на fwd (м) — в мире при покое."""
        H = HAND_W["L"]["supp"]
        p = muzzle
        R = about(p, Matrix.Rotation(math.radians(deg), 3, (WR_REST.to_3x3() @ Vector((1, 0, 0))).normalized()))
        return Matrix.Translation((WR_REST.to_3x3() @ Vector((1, 0, 0))) * fwd) @ R @ H
    del axis_w, sw
    on_muzzle = WR_REST.inverted() @ (Matrix.Translation(wr.data.bones["Socket_Muzzle"].head_local
                                                        - wr.data.bones["Suppressor_Control"].head_local))
    on_muzzle = Matrix.Translation(wr.data.bones["Socket_Muzzle"].head_local - wr.data.bones["Suppressor_Control"].head_local)
    at_muzzle = WR_REST @ on_muzzle @ WR_REST.inverted()             # сдвиг кости глушителя на дуло (мир при покое)
    if on:
        c.gun([(1, (0, 0, 0, 0, 0, 0)), (14, (2, 3, 6, 0.01, 0.01, 0.0)), (26, ("pose", "supp")), (60, ("pose", "supp")),
               (64, ("pose", "supp", (0, 1.5, 0, 0, 0.004, -0.004))), (68, ("pose", "supp")),
               (82, (-3, 1, 0, 0.004, 0, 0.004)), (88, (1, -0.4, 0, 0, 0, 0)), (94, (0, 0, 0, 0, 0, 0))])
        c.hand("L", [(1, "grip"), (6, ("off", "grip", (0.02, 0.03, -0.05))), (14, ("world", AWAY_L)),
                     (28, ("w", turn(0, 0.035))), (34, ("w", turn(0, 0.02))),
                     (38, ("w", turn(70, 0.018))), (42, ("w", turn(0, 0.015))), (46, ("w", turn(70, 0.012))),
                     (50, ("w", turn(0, 0.008))), (54, ("w", turn(70, 0.005))), (58, ("w", turn(0, 0.002))),
                     (62, "supp"), (66, "supp"), (72, ("off", "supp", (0.02, 0.03, -0.04))), (80, "grip")])
        c.fingers(L_FING, [(1, "grip"), (6, "free"), (14, "free"), (18, "supp"), (66, "supp"), (70, "free"), (80, "grip")])
        c.hold("Suppressor_Control", [(16, 1), (64, 0)])
        c.wmat("Suppressor_Control", [(63, at_muzzle), (END, at_muzzle)])
        c.scale("Suppressor_Control", [(16, 1)])
        c.scale("MuzzleAttachment", [(34, 0)])
        c.mark(bring=16, thread=34, turns=38, seated=62, left_to_grip=70, ready=94)
    else:
        c.wmat("Suppressor_Control", [(1, at_muzzle), (END, at_muzzle)])
        c.scale("Suppressor_Control", [(1, 1), (72, 0)])
        c.scale("MuzzleAttachment", [(1, 0), (56, 1)])
        c.gun([(1, (0, 0, 0, 0, 0, 0)), (14, ("pose", "supp")), (58, ("pose", "supp")), (62, ("pose", "supp", (0, 1.5, 0, 0, 0.004, -0.004))),
               (72, (2, 3, 6, 0.01, 0.01, 0.0)), (82, (-3, 1, 0, 0.004, 0, 0.004)), (88, (1, -0.4, 0, 0, 0, 0)), (92, (0, 0, 0, 0, 0, 0))])
        c.hand("L", [(1, "grip"), (6, ("off", "grip", (0.02, 0.03, -0.05))), (16, ("off", "supp", (0.01, 0.02, -0.02))), (20, "supp"),
                     (24, ("w", turn(-70, 0.002))), (28, ("w", turn(0, 0.005))), (32, ("w", turn(-70, 0.008))),
                     (36, ("w", turn(0, 0.012))), (40, ("w", turn(-70, 0.015))), (44, ("w", turn(0, 0.018))),
                     (48, ("w", turn(-70, 0.02))), (52, ("w", turn(0, 0.025))), (56, ("w", turn(0, 0.06))),
                     (68, ("world", AWAY_L)), (76, ("off", "grip", (0.02, 0.03, -0.05))), (84, "grip")])
        c.fingers(L_FING, [(1, "grip"), (6, "free"), (16, "pre"), (20, "supp"), (66, "supp"), (72, "free"), (84, "grip")])
        c.hold("Suppressor_Control", [(20, 1), (72, 0)])
        c.mark(grab=20, turns=24, off=56, left_to_grip=76, ready=92)
    right_index_off(c, [(1, "grip"), (6, "frame"), (END - 8, "frame"), (END - 3, "grip")])
    return c.finish()


def mag_out_in(out):
    """Вынуть / вставить магазин из окна рюкзака: свои клипы (не кусок неполной)."""
    if out:
        END = 54
        c = Clip("Mag_Eject", END, "Вынуть магазин (окно рюкзака)")
        c.gun(gun_keys(seg(W_SWAP, 1, 26)) + [(34, TILT), (44, (-29, -7, 5, 0.05, 0.042, 0.058)),
                                               (50, (2.5, 1.2, -0.6, -0.003, -0.002, -0.004)), (54, (0, 0, 0, 0, 0, 0))])
        left_out_to_mag(c)
        mag_hand(c, seg(MAG_SWAP, 16, 36))
        c.hold("Magazine_Control", [(16, 1)])
        hidden = B["mag"]["mag.L"].copy()
        hidden = Matrix.LocRotScale(hidden.translation, hidden.to_quaternion(), Vector((0.001,) * 3))
        c.bone("mag.L", 35, B["mag"]["mag.L"])
        c.bone("mag.L", 36, hidden)
        c.bone("mag.L", END, hidden)
        c.hand("L", [(44, ("w", lerp_m(POUCH_D @ HAND_W["L"]["mag"], HAND_W["L"]["grip"], 0.6))), (50, "grip")])
        c.fingers(L_FING, [(1, "grip"), (5, "grip"), (10, "free"), (15, "pre"), (17, "mag"), (36, "mag"), (40, "free"), (50, "grip")])
        c.prop("Magazine latch press", [(1, 0), (15, 0), (17, 1), (21, 1), (23, 0)])
        right_index_off(c, [(1, "grip"), (6, "frame"), (46, "frame"), (52, "grip")])
        c.mark(left_to_mag=5, catch=17, mag_out=25, mag_hidden=36, ready=50)
    else:
        END = 56
        d = -30                                       # кадры неполной с 42 — на 30 раньше
        c = Clip("Mag_Insert", END, "Вставить магазин (окно рюкзака)")
        hidden = B["mag"]["mag.L"].copy()
        hidden = Matrix.LocRotScale(hidden.translation, hidden.to_quaternion(), Vector((0.001,) * 3))
        c.bone("mag.L", 1, hidden)
        c.bone("mag.L", 11, hidden)
        c.bone("mag.L", 12, B["mag"]["mag.L"])
        c.hold("Magazine_Control", [(1, 1), (60 + d, 0)])
        c.gun([(1, (0, 0, 0, 0, 0, 0)), (6, (-14, -3, 1.5, 0.018, 0.014, 0.02)), (12, TILT)]
              + [(k[0] + d, tuple(k[1:])) for k in seg(W_SWAP, 50, 60)]
              + [(34, (-29, -7, 5, 0.05, 0.042, 0.058)), (44, (2.5, 1.2, -0.6, -0.003, -0.002, -0.004)), (48, (0, 0, 0, 0, 0, 0))])
        c.hand("L", [(1, "grip"), (6, ("w", lerp_m(HAND_W["L"]["grip"], POUCH_D @ HAND_W["L"]["mag"], 0.5)))])
        mag_hand(c, [(12, -10, 35, 0.17, 0.19, -0.4)] + shift(seg(MAG_SWAP, 48, 60), d))
        left_back_to_grip(c, 60 + d + 3)
        c.fingers(L_FING, [(1, "grip"), (4, "free"), (11, "pre"), (12, "mag"), (60 + d - 1, "mag"), (60 + d + 2, "pre"),
                           (60 + d + 6, "free"), (60 + d + 12, "grip")])
        c.prop("Magazine latch press", [(1, 0), (55.5 + d, 0), (56.5 + d, 0.7), (57.5 + d, 0)])
        right_index_off(c, [(1, "grip"), (6, "frame"), (42, "frame"), (48, "grip")])
        c.mark(mag_new=12, insert=52 + d, seat=57 + d, left_to_grip=61 + d, ready=48)
    return c.finish()


def empty_mag():
    """Патроны кончились: левая достаёт магазин из подсумка, подносит — он пустой, убирает (голос — в игре)."""
    END = 76
    c = Clip("Empty_Mag", END, "Патроны кончились: пустой магазин", state={"Rounds remaining": 0})
    pouch = POUCH_D @ HAND_W["L"]["mag"]
    look = Matrix.Translation(EYE + CAM_FWD * 0.36 - CAM_UP * 0.10 + CAM_RT * 0.02 - MAG_C_W) @ MAG_REST_W
    rel = arms.data.bones["hand.L"].matrix_local.inverted() @ arms.data.bones["mag.L"].matrix_local
    R = Matrix.Rotation(math.radians(-55), 4, CAM_RT) @ Matrix.Rotation(math.radians(-90), 4, CAM_UP)  # горловиной к глазам
    lookM = Matrix.Translation(look.translation) @ R @ MAG_REST_W.to_3x3().to_4x4()
    Hlook = lookM @ B["mag"]["mag.L"].inverted() @ rel.inverted()
    c.gun([(1, (0, 0, 0, 0, 0, 0)), (12, (-8, -2, 2, 0.015, 0.012, 0.015)), (40, (-9, -2.5, 2, 0.016, 0.013, 0.016)),
           (60, (-2, -0.5, 0.5, 0.003, 0.003, 0.004)), (68, (0, 0, 0, 0, 0, 0))])
    c.hand("L", [(1, "grip"), (5, ("w", lerp_m(HAND_W["L"]["grip"], pouch, 0.3))), (12, ("w", pouch)), (24, ("world", Hlook)),
                 (40, ("world", Matrix.Translation(Vector((0.0, 0.0, 0.004))) @ Hlook)), (52, ("w", pouch)),
                 (62, ("off", "grip", (0.02, 0.03, -0.05))), (68, "grip")])
    c.scale("SpareMag", [(12, 1), (56, 0)])
    c.scale("SpareMag_Rounds", [(1, 0)])
    c.hold("SpareMag", [(12, 1), (56, 0)])
    c.fingers(L_FING, [(1, "grip"), (6, "free"), (11, "pre"), (12, "mag"), (52, "mag"), (56, "free"), (68, "grip")])
    right_index_off(c, [(1, "grip"), (6, "frame"), (62, "frame"), (68, "grip")])
    c.mark(to_pouch=5, look=24, away=46, left_to_grip=62, ready=70)
    return c.finish()


REC["Reload_Tactical"] = reload_tactical()
REC["Reload_Full"] = reload_full()
REC["Reload_Fast"] = reload_fast()
REC["Reload_Fast_Full"] = reload_fast("Reload_Fast_Full", "Быстрая с пустым (старый на землю, затвор)", full=True)
REC["Mag_Check"] = mag_check()
REC["Mag_Check_45"] = mag_check_big("45")
REC["Mag_Check_60"] = mag_check_big("60")
REC["Jam_Clear"] = jam_clear()
for s_, d_ in (("auto", "burst"), ("burst", "semi"), ("semi", "auto")):
    REC[f"Fire_Mode_{s_.title()}_{d_.title()}"] = fire_mode(s_, d_)
REC["Fire"] = fire()
REC["Dry_Fire"] = dry_fire()
REC["Finger_On"] = finger(True)
REC["Finger_Off"] = finger(False)
REC["Draw"] = draw()
REC["Holster"] = holster()
REC["Inspect"] = inspect()
REC["Light_Button"] = light_button()
REC["Mag_Eject"] = mag_out_in(True)
REC["Mag_Insert"] = mag_out_in(False)
REC["Suppressor_On"] = suppressor(True)
REC["Suppressor_Off"] = suppressor(False)
REC["Reload_Tactical_Drop"] = reload_living("Reload_Tactical_Drop", "Живая: уронил магазин (стресс)", "drop")
REC["Reload_Miss_A"] = reload_living("Reload_Miss_A", "Живая: не попал в шахту — о край", "miss_a")
REC["Reload_Miss_B"] = reload_living("Reload_Miss_B", "Живая: не попал в шахту — мимо вбок", "miss_b")
REC["Reload_Wrong_A"] = reload_living("Reload_Wrong_A", "Живая: магазин задом наперёд", "wrong_a")
REC["Reload_Wrong_B"] = reload_living("Reload_Wrong_B", "Живая: магазин вверх ногами", "wrong_b")
REC["Reload_Fast_Stuck"] = reload_fast("Reload_Fast_Stuck", "Живая: быстрая, старый застрял — второй удар", stuck=True)
REC["Reload_Fast_Full_Stuck"] = reload_fast("Reload_Fast_Full_Stuck", "Живая: быстрая с пустым, старый застрял", full=True, stuck=True)
REC["Reload_Full_Slip"] = reload_full("Reload_Full_Slip", "Живая: полная, пальцы сорвались с затвора", slip=True)
REC["Jam_Clear_Slip"] = jam_clear("Jam_Clear_Slip", "Живая: задержка, пальцы сорвались с затвора", slip=True)
REC["Empty_Mag"] = empty_mag()

# ================================================================ файл: позы и клипы — действия, версии, панель
GROUPS = (("Стрельба, достать / убрать", ("Fire", "Dry_Fire", "Finger_On", "Finger_Off", "Draw", "Holster")),
          ("Перезарядка", ("Reload_Tactical", "Reload_Full", "Reload_Fast", "Reload_Fast_Full", "Mag_Eject", "Mag_Insert")),
          ("Обслуживание", ("Mag_Check", "Mag_Check_45", "Mag_Check_60", "Inspect", "Jam_Clear", "Fire_Mode_Auto_Burst",
                            "Fire_Mode_Burst_Semi", "Fire_Mode_Semi_Auto", "Light_Button", "Suppressor_On", "Suppressor_Off")),
          ("Живые (стресс)", ("Reload_Tactical_Drop", "Reload_Miss_A", "Reload_Miss_B", "Reload_Wrong_A", "Reload_Wrong_B",
                              "Reload_Fast_Stuck", "Reload_Fast_Full_Stuck", "Reload_Full_Slip", "Jam_Clear_Slip", "Empty_Mag")))
assert sorted(n for _g, ns in GROUPS for n in ns) == sorted(REC), set(REC) ^ {n for _g, ns in GROUPS for n in ns}
REC = {n: dict(REC[n], group=g) for g, ns in GROUPS for n in ns}
assign(None)
for i, (name, rec) in enumerate(REC.items()):
    act = bpy.data.actions[PREFIX + name]
    act["order"] = i
    act["group"] = rec["group"]
    act.use_frame_range = False                       # длина клипа — по последнему ключу: владелец может её менять
poses_act.use_frame_range = False
snap = poses_act.copy()
snap.name = CT.APPLIED
snap.use_fake_user = True
nv = CT.build_versions(bpy.context, log)
log("версий собрано", nv)
panel = bpy.data.texts.get(CT.PANEL_TEXT) or bpy.data.texts.new(CT.PANEL_TEXT)
panel.from_string((HERE / "clip_tools.py").read_text(encoding="utf-8"))
panel.use_module = True                               # панель регистрируется при открытии файла
for ob in (arms, wr):
    ob.select_set(False)
CT.open_action(bpy.context, CT.POSES)
js = ROOT_DIR / "_asset_src/veras54_v14/anim/clips.json"
js.parent.mkdir(parents=True, exist_ok=True)
js.write_text(json.dumps(REC, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
txt = bpy.data.texts.get("ВЕРАС-54 — позы и клипы (читать)") or bpy.data.texts.new("ВЕРАС-54 — позы и клипы (читать)")
lines = [CT.__doc__, "", "ЧТО В КАКОЙ ПОЗЕ (кадры «Позы (хваты)»)"]
own, _f, _l, _r = CT.bone_sets(arms)
for name, f in CT.POSE_FRAMES.items():
    lines.append(f"  {f:>3}  {CT.POSE_RU[name]}" + ("   ← и где стоит автомат в этой фазе" if name in CT.GUN_REF else ""))
lines += ["", "  Кадр 1 — всё. На остальных кадрах «своё» только у одной руки; прочее кнопка панели сама копирует с кадра 1.",
          "", "КЛИПЫ (длина, фазы — кадры внутри клипа)"]
for name, rec in REC.items():
    lines.append(f"  {rec['title'][:44]:44s} {rec['frames']:4d} к ({rec['seconds']:.2f} с)  {rec['marks']}")
lines += ["", "Собрать все клипы заново из таблиц build_clips.py (сотрёт ручные правки клипов; позы останутся):",
          "  tools\\veras54_v14\\clips\\regenerate.cmd в папке игры."]
txt.from_string("\n".join(lines))
OUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True)
log("сохранено", OUT, "клипов", len(REC))
