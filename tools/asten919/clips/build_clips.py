"""АСТЕН-919 (wpn_hg_02): клипы рук от первого лица — ключевые кадры движения. Хваты — отдельно, в действии ASTEN919_Poses.

Вход — файл с позами (tools/asten919/clips/poses.py или тот же файл клипов после правки поз владельцем); выход — один
.blend со всеми клипами: каждое действие ASTEN919_<Клип> (два слота: FPS_ArmsRig и ASTEN919_WeaponRig) и дорожки NLA
«Клипы» — клипы подряд на общей шкале, маркеры — начала клипов и фазы.

Что чем двигается (ключи редкие, только на опорных позах; между ними — кривые Bezier):
  движение  — Weapon_CTRL (пистолет с правой кистью: наклоны вокруг рукояти и сдвиги), ik_hand.L (левая кисть; дочерняя
              Weapon_CTRL — «на пистолете» едет с ним), кости ASTEN919_WeaponRig: Slide, Trigger, SlideStop, MagCatch,
              Magazine_Control (ход магазина в шахте), SpareMag_Control (старый магазин быстрой перезарядки), Case,
              JamCase (гильзы; «выключены» масштабом 0,001); у Magazine_Control ограничение «В левой кисти» (влияние
              0 / 1): магазин держится за кость mag.L левой кисти;
  хват      — пальцы (thumb.*, f_*.*, palm.*) и место кисти на пистолете (ik_hand.R / ik_hand.L в позах): в клипы
              переносятся из действия ASTEN919_Poses (кадр-поза → набор костей, словарь OWN; остальное в позе — с кадра 1).
              Поправить хват во всех клипах сразу — поправить позу в ASTEN919_Poses и пересобрать клипы
              (tools/asten919/clips/rebuild.cmd). Действие поз — рабочее у обоих ригов (Extrapolation: Nothing, кадры
              1–61), клипы — дорожкой NLA с кадра 101; ключи владельца, попавшие в постороннее действие, сборщик
              переносит в позы сам, ключи не на кадрах поз — отбрасывает.
Каждый клип начинается и кончается позой «ХВАТ» (кадр 1 поз); Fire — с пальцем на спуске.

КАК МЕНЯТЬ ДВИЖЕНИЕ (клипы руками не править — пересборка их стирает; всё движение — в этом скрипте)
  1. Положение пистолета — на кадрах поз, без кода: Weapon_CTRL на кадре 41 (магазин вынимают), 46 (новый вставляют
     и досылают), 51 (левая тянет затвор). Поставил, ключ, rebuild.cmd — клипы возьмут это положение (G_MAG, G_SEAT,
     G_RACK). Остальные положения — числа в функциях клипов: FLICK (взмах быстрой перезарядки), LSIDE / RSIDE (осмотр),
     LOW (проверка магазина): (крен по часовой°, дуло вверх°, дуло влево°, влево м, к глазам м, вверх м) от хвата.
  2. Когда что происходит — таблицы ключей в функциях клипов (reload_tactical, reload_fast, mag_check, inspect, rack,
     fire; общий кусок смены магазина — swap). Номера кадров — внутри клипа, длина клипа — Clip(имя, кадров):
       c.gun([k(кадр, поза, roll=…, pitch=…, yaw=…, dx=…, dy=…, dz=…), …])  пистолет: поза и поправки к ней
       c.left([(кадр, "grip" | ("mag", вышел_м) | ("seat", вышел_м) | ("pinch", ход 0…1) | ("world", точка, поворот)), …])
       c.fingers(кости, [(кадр, имя позы), …])                             пальцы из кадров поз
       c.part("slide" | "trigger" | "stop" | "catch" | "mag", [(кадр, ход), …])   детали пистолета
       c.hold([(кадр, 0 | 1)])  магазин в левой кисти;  c.mark(имя=кадр)  маркеры фаз
     Хочешь медленнее — раздвинь кадры ключей (и увеличь длину клипа), сильнее — увеличь поправку.
  3. Рывки передёргивания — таблица RACK_TUG (подал вперёд, ушёл за рукой, бросок после отпускания, отбой).
  4. Новая поза с кадра поз в клип — три шага, как сделаны G_MAG / G_SEAT / G_RACK: (а) матрица из позы:
     G_X = pose_shift(B["имя позы"]["Weapon_CTRL"]); (б) умолчание в GUN_DEFAULT, пока на кадре стоит хват;
     (в) в таблице клипа k(кадр, G_X) вместо чисел.
  Проба на копии файла, чтобы не трогать рабочий: rebuild.cmd "<полный путь к копии.blend>".

blender -b "<позы или клипы.blend>" --python-exit-code 1 --python tools/asten919/clips/build_clips.py -- <выход.blend>
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Euler, Matrix, Quaternion, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = Path(sys.argv[sys.argv.index("--") + 1])
sys.path.insert(0, str(HERE))
from sdf_grid import Grid  # noqa: E402

FPS = 30
POSES = "ASTEN919_Poses"
PREFIX = "ASTEN919_"
POSE_FRAMES = dict(grip=1, trigger=11, pressed=16, catch=21, stop=26, up=31, mag=41, seat=46, pinch=51, free=61)
MAG_DROP = 0.055
SLIDE, TRIGGER, STOP, CATCH = 0.043, 18.0, 6.0, 0.002
JAM_OPEN = 0.3
TAIL = 100                                           # технический ключ поз перед первым клипом (копия хвата)
GAP = 24                                             # кадров между клипами на общей шкале
log = lambda *a: print("ASTEN_CLIPS", *a, flush=True)  # noqa: E731

S = bpy.context.scene
S.render.fps = FPS
arms = bpy.data.objects["FPS_ArmsRig"]
wr = bpy.data.objects["ASTEN919_WeaponRig"]
root = bpy.data.objects["ASTEN919"]
cam = bpy.data.objects["FPS • Camera"]
QUAT = ("Weapon_CTRL", "ik_hand.R", "ik_hand.L", "mag.L")
A_BONES = [pb.name for pb in arms.pose.bones]
FINGER = lambda n: n.split(".")[0] in ("thumb", "palm", "f_index", "f_middle", "f_ring", "f_pinky")  # noqa: E731
R_THUMB = [n for n in A_BONES if n.startswith("thumb") and n.endswith(".R")]
R_INDEX = [n for n in A_BONES if n.startswith("f_index") and n.endswith(".R")]
L_FING = [n for n in A_BONES if FINGER(n) and n.endswith(".L")]
L_ARM = [n for n in A_BONES if n.endswith(".L") and n not in L_FING]     # вся левая рука, кроме пальцев (кисть, цель IK, локоть…)
L_BODY = [n for n in L_ARM if n not in ("ik_hand.L", "mag.L")]


def update():
    bpy.context.view_layer.update()


def slot_of(act, ob):
    return next((s for s in act.slots if s.name_display == ob.name), None) or act.slots.new(id_type="OBJECT", name=ob.name)


def assign(act):
    for ob in (arms, wr):
        ad = ob.animation_data or ob.animation_data_create()
        ad.action = act
        if act is not None:
            ad.action_slot = slot_of(act, ob)


# ================================================================ позы владельца
for ob in (arms, wr):                                # прежние дорожки и клипы — прочь (пересборка)
    ad = ob.animation_data
    if ad:
        for t in list(ad.nla_tracks):
            ad.nla_tracks.remove(t)
for a in list(bpy.data.actions):
    if a.name.startswith(PREFIX) and a.name != POSES:
        bpy.data.actions.remove(a)
poses_act = bpy.data.actions[POSES]
POSE_AT = {f: name for name, f in POSE_FRAMES.items()}


def bag_of(act, ob):
    layer = act.layers[0] if act.layers else act.layers.new("Layer")
    strip = layer.strips[0] if layer.strips else layer.strips.new(type="KEYFRAME")
    return strip.channelbag(slot_of(act, ob), ensure=True)


def absorb(ob):
    """Ключи владельца, попавшие мимо поз (K без режима правки дорожки заводит действие «…Action» поверх NLA),
    переносятся в ASTEN919_Poses на свои кадры; само постороннее действие убирается."""
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
    if src is not None:
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


def drop_off_pose_keys():
    """В действии поз ключи живут только на кадрах поз: случайные (K на кадре клипа) убираются."""
    lost = set()
    for layer in poses_act.layers:
        for st in layer.strips:
            for bag in st.channelbags:
                for fc in bag.fcurves:
                    for kp in reversed(list(fc.keyframe_points)):
                        if round(kp.co[0]) not in POSE_AT or abs(kp.co[0] - round(kp.co[0])) > 1e-4:
                            if round(kp.co[0]) != TAIL:
                                lost.add(round(kp.co[0], 2))
                            fc.keyframe_points.remove(kp)
                    fc.update()
    if lost:
        log(f"в позах были ключи не на кадрах поз {sorted(lost)} — убраны (движение правится в таблицах build_clips.py)")


for ob in (arms, wr):
    absorb(ob)
drop_off_pose_keys()
assign(poses_act)
for ob in (arms, wr):
    ob.animation_data.action_extrapolation = "HOLD"
con = wr.pose.bones["Magazine_Control"].constraints["В левой кисти"]


def con_enable(on):
    if hasattr(con, "enabled"):
        con.enabled = on
    else:
        con.mute = not on


# На кадрах поз магазин стоит на своём месте в пистолете (кадр 41 — вышел из шахты на MAG_DROP) и за кистью не едет:
# владелец ставит кисть вокруг него. Как магазин лежит в кисти (кость mag.L), сборщик снимает сам с кадра 41.
for fc in bag_of(poses_act, wr).fcurves:
    if fc.data_path.endswith('constraints["В левой кисти"].influence'):
        for kp in fc.keyframe_points:
            kp.co[1] = 0.0
            kp.handle_left[1] = kp.handle_right[1] = 0.0
        fc.update()
con_enable(False)
B = {}
SHORT = {}                                           # позы левой руки, где рука не дотягивается до цели (мм)
for name, f in POSE_FRAMES.items():
    S.frame_set(f)
    update()
    B[name] = {n: arms.pose.bones[n].matrix_basis.copy() for n in A_BONES}
    hand, ikt = arms.pose.bones["hand.L"], arms.pose.bones["ik_hand.L"]
    if name in ("mag", "seat", "pinch"):
        res = (hand.head - ikt.head).length * 1000
        if res > 1.0:
            SHORT[name] = res
    if name == "mag" and "mag.L" in A_BONES:
        # кисть берётся на цели IK (в клипах она до неё дотягивается), а не там, где её остановила вытянутая рука
        reached = hand.matrix.copy()
        reached.translation = ikt.matrix.translation
        rel = arms.data.bones["hand.L"].matrix_local.inverted() @ arms.data.bones["mag.L"].matrix_local
        basis = (reached @ rel).inverted() @ arms.matrix_world.inverted() @ wr.matrix_world @ wr.pose.bones["Magazine_Control"].matrix
        d = (basis.translation - B[name]["mag.L"].translation).length * 1000
        B[name]["mag.L"] = basis
        if d > 0.05:
            log(f"поза «mag» (кадр {f}): магазин в левой кисти лежит по-новому (сдвиг {d:.1f} мм) — снято с позы кисти")
con_enable(True)

# Что в какой позе «своё» (остальное в ней — как в хвате, кадр 1): так поправленный хват виден на всех кадрах поз.
OWN = dict(trigger=set(R_INDEX), pressed=set(R_INDEX), catch=set(R_THUMB), stop=set(R_THUMB), up=set(R_THUMB),
           mag=set(L_FING) | set(L_ARM) | {"mag.L", "Weapon_CTRL"}, seat=set(L_FING) | set(L_ARM) | {"Weapon_CTRL"},
           pinch=set(L_FING) | set(L_ARM) | {"Weapon_CTRL"}, free=set(L_FING) | set(L_ARM) | {"Weapon_CTRL"})
# Weapon_CTRL на кадрах левой руки — только для показа (как удобно ставить кисть): левая кисть — дочерняя пистолета,
# её место на пистолете от этого не зависит; в клипах пистолет двигают таблицы движения.
if "mag.L" in A_BONES:                               # как магазин лежит в левой кисти — одна поза на все кадры (кадр 41)
    for name in B:
        B[name]["mag.L"] = B["mag"]["mag.L"].copy()


def key_pose(pb, frame):
    pb.keyframe_insert("rotation_quaternion" if pb.rotation_mode == "QUATERNION" else "rotation_euler", frame=frame)
    pb.keyframe_insert("location", frame=frame)
    pb.keyframe_insert("scale", frame=frame)


changed = {}
for name, f in POSE_FRAMES.items():
    for n in A_BONES:
        want = B[name][n] if (name == "grip" or n in OWN[name]) else B["grip"][n]
        if name != "grip" and n not in OWN[name]:
            d = max(abs(a - b) for ra, rb in zip(B[name][n], want) for a, b in zip(ra, rb))
            if d > 1e-5:
                changed.setdefault(name, []).append(n)
            B[name][n] = want.copy()
        pb = arms.pose.bones[n]
        pb.matrix_basis = want
        key_pose(pb, f)
for name, bones in changed.items():
    log(f"поза «{name}» (кадр {POSE_FRAMES[name]}): {len(bones)} костей приведены к хвату кадра 1")
assign(None)
con.influence = 0.0
for pb in wr.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
for b in ("SpareMag_Control", "Case", "JamCase"):
    wr.pose.bones[b].scale = (0.001,) * 3
for n in A_BONES:
    arms.pose.bones[n].matrix_basis = B["grip"][n]
update()
AW = arms.matrix_world.copy()
AWI = AW.inverted()
TW = root.matrix_world.copy()                        # исходник пистолета (м) → мир, в покое
RW = TW.to_3x3()
wc = arms.pose.bones["Weapon_CTRL"]
ikL = arms.pose.bones["ik_hand.L"]
WC_REST = wc.matrix.copy()
GRIP_W = TW @ Vector((-0.044, 0.0, -0.065))          # вокруг чего наклоняется пистолет: середина рукояти
U = Vector((math.sin(math.radians(22.0)), 0.0, math.cos(math.radians(22.0))))     # ось магазина вверх (исходник)
EYE = cam.matrix_world.translation.copy()


def ik_variant(pose, shift_src):
    """Место левой кисти из позы, сдвинутое в осях пистолета (м) → matrix_basis цели ik_hand.L (пистолет в покое)."""
    ikL.matrix_basis = B[pose]["ik_hand.L"]
    update()
    m = AW @ ikL.matrix
    m = Matrix.Translation(RW @ Vector(shift_src)) @ m
    ikL.matrix = AWI @ m
    update()
    out = ikL.matrix_basis.copy()
    ikL.matrix_basis = B["grip"]["ik_hand.L"]
    update()
    return out


def left_rest_world(pose):
    ikL.matrix_basis = B[pose]["ik_hand.L"]
    update()
    m = (AW @ ikL.matrix).copy()
    ikL.matrix_basis = B["grip"]["ik_hand.L"]
    update()
    return m


MAG_HAND_W = left_rest_world("mag")                  # левая с магазином (вышел на MAG_DROP), пистолет в покое
MAG_C0 = TW @ (Vector((-0.045, 0.0, -0.075)) - U * MAG_DROP)      # середина магазина при этом


def gun_basis(roll, pitch, yaw, dx, dy, dz, base=None):
    """Поза пистолета (крен по часовой°, дуло вверх°, дуло влево°, влево м, к глазам м, вверх м) → matrix_basis.
    base = None — от покоя; base = матрица позы владельца (pose_shift) — поправки от неё: повороты в осях уже
    наклонённого пистолета вокруг середины рукояти, сдвиги — в мире."""
    R = (Matrix.Rotation(math.radians(yaw), 4, Vector((0, 0, 1))) @ Matrix.Rotation(math.radians(pitch), 4, Vector((-1, 0, 0)))
         @ Matrix.Rotation(math.radians(roll), 4, Vector((0, -1, 0))))
    D = (Matrix.Translation(Vector((dx, dy, dz))) @ (base if base is not None else Matrix.Identity(4))
         @ Matrix.Translation(GRIP_W) @ R @ Matrix.Translation(-GRIP_W))
    wc.matrix = AWI @ D @ AW @ WC_REST
    update()
    return wc.matrix_basis.copy()


def pose_shift(basis):
    """matrix_basis кости Weapon_CTRL из позы владельца → сдвиг пистолета в мире относительно покоя (хвата)."""
    wc.matrix_basis = basis
    update()
    D = AW @ wc.matrix @ WC_REST.inverted() @ AWI
    wc.matrix_basis = B["grip"]["Weapon_CTRL"]
    update()
    return D


# ================================================================ ключи
class Clip:
    def __init__(self, name, end, state=None):
        self.name, self.end = name, end
        self.act = bpy.data.actions.new(PREFIX + name)
        self.act.use_fake_user = True
        assign(self.act)
        self.prev = {}
        self.marks = {}
        self.left_keys = []
        st = dict(slide=0.0, stop=0.0, trigger=0.0, catch=0.0, mag=0.0, held=0.0)
        st.update(state or {})
        self.state0 = st
        con.influence = 0.0
        for pb in wr.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        for b in ("SpareMag_Control", "Case", "JamCase"):
            wr.pose.bones[b].scale = (0.001,) * 3
        for n in A_BONES:                             # опорная поза в начале и в конце — у всех костей
            self.bone(n, 1, B["grip"][n])
            self.bone(n, end, B["grip"][n])
        for part in ("slide", "stop", "trigger", "catch", "mag"):
            self.part(part, [(1, st[part])])
        self.hold([(1, st["held"])])
        for b in ("SpareMag_Control", "Case", "JamCase"):
            self.scale(b, [(1, 0)])

    # ---- руки
    def bone(self, n, frame, basis, loc=True):
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
        if loc:
            pb.keyframe_insert("location", frame=frame)

    def fingers(self, names, keys):
        """keys: (кадр, имя позы) — пальцы из позы владельца."""
        for frame, pose in keys:
            for n in names:
                self.bone(n, frame, B[pose][n])

    def gun(self, keys):
        """Пистолет с правой кистью: (кадр, крен по часовой°, дуло вверх°, дуло влево°, влево м, к глазам м, вверх м)."""
        for frame, base, pose in keys:
            self.bone("Weapon_CTRL", frame, gun_basis(*pose, base=base))
        return self

    def left(self, keys):
        """Левая кисть: (кадр, место): 'grip' | ('mag', вышел_м) | ('seat', вышел_м) | ('pinch', ход 0…1[, сдвиг исходник м])
        — на пистолете (едет с ним); ('world', точка мира, (rx, ry, rz)°) — в мире, поворот от позы «магазин в кисти»."""
        self.left_keys += [(frame, "grip" if spec == "grip" else spec[0]) for frame, spec in keys]
        for frame, spec in keys:
            if spec == "grip":
                basis, arm = B["grip"]["ik_hand.L"], "grip"
            elif spec[0] == "mag":
                basis, arm = ik_variant("mag", -U * (spec[1] - MAG_DROP)), "mag"
            elif spec[0] == "seat":
                basis, arm = ik_variant("seat", -U * spec[1]), "seat"
            elif spec[0] == "pinch":
                sh = Vector((-SLIDE * spec[1], 0.0, 0.0)) + (Vector(spec[2]) if len(spec) > 2 else Vector())
                basis, arm = ik_variant("pinch", sh), "pinch"
            else:
                S.frame_set(frame)                    # где сейчас пистолет
                update()
                m = Euler([math.radians(v) for v in spec[2]], "XYZ").to_matrix().to_4x4() @ MAG_HAND_W.to_3x3().to_4x4()
                m.translation = Vector(spec[1])
                ikL.matrix = AWI @ m
                update()
                basis, arm = ikL.matrix_basis.copy(), "mag"
            self.bone("ik_hand.L", frame, basis)
            for n in L_BODY:                          # hand.L, upper_arm.L, локоть — как в той же позе владельца
                self.bone(n, frame, B[arm][n])
        return self

    # ---- пистолет
    def part(self, what, keys):
        b = wr.pose.bones
        for frame, v in keys:
            if what == "slide":
                b["Slide"].location = (0.0, -SLIDE * v, 0.0)
                b["Slide"].keyframe_insert("location", frame=frame)
            elif what == "trigger":
                b["Trigger"].rotation_euler = (-math.radians(TRIGGER) * v, 0.0, 0.0)
                b["Trigger"].keyframe_insert("rotation_euler", frame=frame)
            elif what == "stop":
                b["SlideStop"].rotation_euler = (-math.radians(STOP) * v, 0.0, 0.0)
                b["SlideStop"].keyframe_insert("rotation_euler", frame=frame)
            elif what == "catch":
                b["MagCatch"].location = (CATCH * v, 0.0, 0.0)
                b["MagCatch"].keyframe_insert("location", frame=frame)
            elif what == "mag":                       # вышел из шахты на v метров (в осях пистолета)
                b["Magazine_Control"].location = (0.0, -U.x * v, -U.z * v)
                b["Magazine_Control"].keyframe_insert("location", frame=frame)

    def hold(self, keys):
        for frame, v in keys:
            con.influence = v
            con.keyframe_insert("influence", frame=frame)

    def scale(self, bone, keys):
        pb = wr.pose.bones[bone]
        for frame, on in keys:
            pb.scale = (1.0, 1.0, 1.0) if on else (0.001, 0.001, 0.001)
            pb.keyframe_insert("scale", frame=frame)

    def fly(self, bone, keys):
        """Свободный полёт детали: (кадр, 'rest' | (смещение в осях пистолета м) | ('w', смещение в мире м от прошлого
        ключа), (поворот°)). Мировые ключи считаются по положению пистолета на своём кадре."""
        pb = wr.pose.bones[bone]
        rest = wr.matrix_world @ wr.data.bones[bone].matrix_local
        last = None
        for frame, pos, rot in keys:
            S.frame_set(frame)
            update()
            gun_now = wr.matrix_world @ wr.pose.bones["WeaponRoot"].matrix @ wr.data.bones["WeaponRoot"].matrix_local.inverted()
            R = Euler([math.radians(v) for v in rot], "XYZ").to_matrix().to_4x4()
            if pos == "rest":
                m = gun_now @ wr.matrix_world.inverted() @ rest
            elif pos[0] == "w":
                m = last.copy()
                m.translation = last.translation + Vector(pos[1])
                m = Matrix.Translation(m.translation) @ R @ last.to_3x3().to_4x4()
            else:
                m = gun_now @ wr.matrix_world.inverted() @ Matrix.Translation(RW @ Vector(pos)) @ rest @ R
            last = m.copy()
            pb.matrix = wr.matrix_world.inverted() @ m
            update()
            q = pb.matrix_basis.to_euler("XYZ", self.prev[bone]) if bone in self.prev else pb.matrix_basis.to_euler("XYZ")
            pb.rotation_euler = q
            self.prev[bone] = q.copy()
            pb.keyframe_insert("location", frame=frame)
            pb.keyframe_insert("rotation_euler", frame=frame)

    def straight_left(self):
        """Между соседними ключами левой кисти одного вида (магазин в шахте, досылание ладонью, щепоть на затворе)
        кисть идёт вдоль оси детали: у всех каналов одна и та же форма кривой по времени (ручки Free, одна доля хода),
        иначе авто-ручки Bezier у каждого канала свои и магазин гуляет в шахте поперёк. У ключа, за которым кисть
        уходит в свободный полёт ('world'), скорость сохраняется (доля 1/3), у остальных — плавный старт / остановка."""
        lk = sorted(set(self.left_keys))
        pairs = []
        for i in range(len(lk) - 1):
            (fa, ka), (fb, kb) = lk[i], lk[i + 1]
            if ka == kb and ka in ("mag", "seat", "pinch"):
                pairs.append((fa, fb, 1 / 3 if i > 0 and lk[i - 1][1] == "world" else 0.0,
                              1 / 3 if i + 2 < len(lk) and lk[i + 2][1] == "world" else 0.0))
        if not pairs:
            return
        bones = set(L_BODY) | {"ik_hand.L"}
        for fc in [fc for layer in self.act.layers for st in layer.strips for bag in st.channelbags for fc in bag.fcurves]:
            if not fc.data_path.startswith('pose.bones["') or fc.data_path.split('"')[1] not in bones:
                continue
            at = {round(kp.co[0]): kp for kp in fc.keyframe_points}
            for fa, fb, sa, sb in pairs:
                a, b = at.get(fa), at.get(fb)
                if a is None or b is None:
                    continue
                dv, dt = b.co[1] - a.co[1], (fb - fa) / 3
                a.handle_right_type = b.handle_left_type = "FREE"
                a.handle_right = (fa + dt, a.co[1] + dv * sa)
                b.handle_left = (fb - dt, b.co[1] - dv * sb)
            fc.update()

    def mark(self, **kw):
        self.marks.update(kw)

    def finish(self):
        for fc in [fc for layer in self.act.layers for st in layer.strips for bag in st.channelbags for fc in bag.fcurves]:
            step = "influence" in fc.data_path or fc.data_path.endswith("scale")
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT" if step else "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()
        self.straight_left()
        self.act.frame_range = (1, self.end)
        self.act.use_frame_range = True
        # проверка: дотянулись ли руки до целей, не уходит ли левая в рамку
        worst = {"L": (0.0, 0), "R": (0.0, 0)}
        for f in range(1, self.end + 1):
            S.frame_set(f)
            for s in ("L", "R"):
                d = (arms.pose.bones[f"hand.{s}"].head - arms.pose.bones[f"ik_hand.{s}"].head).length * 1000
                if d > worst[s][0]:
                    worst[s] = (round(d, 1), f)
        log(f"{self.name}: кадров {self.end} ({self.end / FPS:.2f} с), фазы {self.marks}, рука не дотянулась, мм (кадр): L {worst['L']} R {worst['R']}")
        return dict(frames=self.end, seconds=round(self.end / FPS, 2), marks=self.marks, state=self.state0, reach_mm=worst)


# ================================================================ общие куски
REST = (0, 0, 0, 0.0, 0.0, 0.0)
CANT = (32, 10, 8, 0.030, 0.050, 0.050)              # «немного к лицу», шахтой к левой руке
PRESENT = (56, 17, 10, 0.036, 0.056, 0.062)          # шахта навстречу новому магазину
POUCH = ((0.17, -0.10, 1.34), (25, 10, -30))         # «подсумок»: слева внизу, за кадром
POUCH2 = ((0.165, -0.105, 1.345), (27, 12, -28))

# Передёргивание затвора: пистолет ближе к середине кадра, завален влево (окно выбрасывателя к глазам), дуло вверх.
# Это положение владелец ставит сам — Weapon_CTRL на кадре позы 51 («щепоть на затворе»); пока там пистолет стоит
# как в хвате, сборщик пишет туда это умолчание. Рывки при оттягивании и отпускании — RACK_TUG (от этой позы).
RACK = (-42, 18, 6, 0.065, 0.030, 0.050)
RACK_TUG = dict(brace=dict(dy=-0.006, pitch=-1.0),                       # перед рывком правая подаёт пистолет вперёд
                pulled=dict(dy=0.022, pitch=4.0, roll=-3.0, dz=0.004),   # затвор оттянут: пистолет уходит за левой рукой
                slam=dict(dy=-0.018, pitch=-5.0, dz=-0.004),             # отпущен: пружина бросает пистолет вперёд, дуло клюёт
                rebound=dict(dy=0.005, pitch=1.6))                       # отбой назад, потом покой


def same_as_grip(name, bone="Weapon_CTRL"):
    return max(abs(a - b) for ra, rb in zip(B[name][bone], B["grip"][bone]) for a, b in zip(ra, rb)) < 1e-5


# Положение пистолета в клипах берётся с кадров поз левой руки (Weapon_CTRL на кадре): 41 — магазин вынимают,
# 46 — новый вставляют и досылают, 51 — левая тянет затвор. Пока на кадре пистолет стоит как в хвате, сборщик пишет
# туда умолчание (CANT / PRESENT / RACK) — дальше владелец правит его на кадре сам.
GUN_DEFAULT = dict(mag=(CANT, "когда вынимают магазин"), seat=(PRESENT, "когда вставляют и досылают магазин"),
                   pinch=(RACK, "когда левая тянет затвор"))
defaults = {}
for name, (pose, when) in GUN_DEFAULT.items():
    if same_as_grip(name):
        defaults[name] = (gun_basis(*pose), f"положение по умолчанию ({when}) — правьте Weapon_CTRL на этом кадре")
    elif name in SHORT:
        log(f"поза «{name}» (кадр {POSE_FRAMES[name]}): левая рука не дотягивается на {SHORT[name]:.0f} мм — придвиньте "
            f"пистолет или кисть")
if defaults:                                         # позы посчитаны до назначения действия: оно пересчитало бы их при update()
    assign(poses_act)
    for name, (basis, why) in defaults.items():
        wc.matrix_basis = basis
        key_pose(wc, POSE_FRAMES[name])
        B[name]["Weapon_CTRL"] = basis.copy()
        log(f"поза «{name}» (кадр {POSE_FRAMES[name]}): пистолет — {why}")
    assign(None)
wc.matrix_basis = B["grip"]["Weapon_CTRL"]
update()
G_MAG = pose_shift(B["mag"]["Weapon_CTRL"])          # пистолет, когда вынимают магазин, — как на кадре позы 41
G_SEAT = pose_shift(B["seat"]["Weapon_CTRL"])        # когда вставляют и досылают — как на кадре позы 46
G_RACK = pose_shift(B["pinch"]["Weapon_CTRL"])       # при передёргивании — как на кадре позы 51


def k(frame, pose, **d):
    """Ключ пистолета: поза (крен, вверх, влево, dx, dy, dz) или поза владельца (матрица pose_shift) с поправками."""
    base = pose if isinstance(pose, Matrix) else None
    v = [0.0] * 6 if base is not None else list(pose)
    for key, add in d.items():
        v[("roll", "pitch", "yaw", "dx", "dy", "dz").index(key)] += add
    return (frame, base, tuple(v))


def rack_gun(base, hold, pull, back, release):
    """Ключи пистолета на передёргивание: встал в позу base (hold) → подал вперёд (pull, начало рывка) → затвор сзади,
    пистолет ушёл за левой рукой (back … release) → бросок вперёд после отпускания → отбой → покой в позе."""
    return [k(hold, base), k(pull, base, **RACK_TUG["brace"]), k(back, base, **RACK_TUG["pulled"]),
            k(release, base, **RACK_TUG["pulled"]), k(release + 3, base, **RACK_TUG["slam"]),
            k(release + 6, base, **RACK_TUG["rebound"]), k(release + 10, base)]


def swap(c, t, cant_from=None):
    """Смена магазина от кадра t (кнопка уже нажата на t): магазин выпал в ладонь → подсумок → новый → вставлен → дослан
    ладонью. → кадр, на котором магазин дослан."""
    c.part("mag", [(t, 0.0), (t + 4, MAG_DROP), (t + 54, MAG_DROP), (t + 58, 0.048), (t + 61, 0.0)])
    c.part("catch", [(t - 2, 0), (t, 1), (t + 4, 1), (t + 7, 0)])
    c.hold([(t + 6, 1), (t + 54, 0)])
    c.fingers(L_FING, [(t - 6, "free"), (t + 2, "free"), (t + 6, "mag"), (t + 54, "mag"), (t + 57, "seat"), (t + 64, "seat"), (t + 74, "grip")])
    c.left([(t - 1, ("mag", MAG_DROP + 0.008)), (t + 5, ("mag", MAG_DROP)), (t + 12, ("mag", 0.128)), (t + 23, ("world", *POUCH)),
            (t + 31, ("world", *POUCH2)), (t + 41, ("mag", 0.140)), (t + 47, ("mag", 0.122)), (t + 54, ("mag", MAG_DROP)),
            (t + 58, ("seat", 0.048)), (t + 61, ("seat", 0.0)), (t + 64, ("seat", 0.007))])
    c.mark(catch=t, mag_out=t + 12, mag_hidden=t + 23, mag_new=t + 27, insert=t + 47, mag_in=t + 54, seat=t + 61)
    return t + 61


# ================================================================ клипы
def reload_tactical(name="Reload_Tactical", full=None):
    """Неполная (п. 2) и полная (п. 1): full = None | 'stop' — затвор на задержке, большой правой опускает рычаг |
    'rack' — затвор закрыт, левая передёргивает щепотью."""
    t = 13
    end = {None: 104, "stop": 118, "rack": 138}[full]
    c = Clip(name, end, dict(slide=1.0, stop=1.0) if full == "stop" else None)
    c.fingers(R_THUMB, [(5, "grip"), (11, "catch"), (t + 5, "catch"), (t + 11, "grip")])
    seat = swap(c, t)
    g = [k(1, REST), k(11, G_MAG), k(26, G_MAG, roll=-2, pitch=1, dz=0.002), k(46, G_MAG, roll=6, pitch=3, dx=0.002, dz=0.002),
         k(58, G_SEAT), k(seat - 3, G_SEAT, roll=1), k(seat + 1, G_SEAT, pitch=1.6, dz=0.006), k(seat + 5, G_SEAT)]
    if full is None:
        g += [k(92, REST, roll=3, pitch=1, dx=0.002, dy=0.003, dz=0.003), k(96, REST, roll=-1.2, pitch=-0.4), k(100, REST)]
        c.left([(seat + 16, "grip")])
        c.fingers(L_FING, [(seat + 16, "grip")])
    elif full == "stop":
        p = seat + 13                                 # большой давит рычаг
        c.fingers(R_THUMB, [(seat + 4, "grip"), (p - 2, "stop"), (p + 3, "stop"), (p + 10, "grip")])
        c.part("stop", [(p - 1, 1), (p + 1, 0)])
        c.part("slide", [(p, 1), (p + 2, 0)])
        g += [k(p, G_SEAT, roll=-8, pitch=-3), k(p + 3, G_SEAT, roll=-9, pitch=-5.5, dy=-0.006), k(p + 7, G_SEAT, roll=-10, pitch=-3),
              k(106, REST, roll=3, pitch=1, dx=0.002, dy=0.003, dz=0.003), k(110, REST, roll=-1.2, pitch=-0.4), k(114, REST)]
        c.left([(seat + 22, "grip")])
        c.fingers(L_FING, [(seat + 22, "grip")])
        c.mark(slide_release=p + 1)
    else:
        p = seat + 16                                 # левая взяла затвор щепотью
        c.left([(p, ("pinch", 0.0)), (p + 4, ("pinch", 0.0)), (p + 10, ("pinch", 1.0)), (p + 12, ("pinch", 1.0, (-0.012, 0.012, 0.014))),
                (p + 32, "grip")])
        c.fingers(L_FING, [(p - 6, "free"), (p, "pinch"), (p + 10, "pinch"), (p + 13, "free"), (p + 32, "grip")])
        c.part("slide", [(p + 4, 0), (p + 10, 1), (p + 11, 1), (p + 13, 0)])
        g += rack_gun(G_RACK, p, p + 4, p + 10, p + 11)
        g += [k(end - 12, REST, roll=-3, pitch=1, dx=0.002, dy=0.003, dz=0.003), k(end - 8, REST, roll=1.2, pitch=-0.4), k(end - 4, REST)]
        c.mark(rack_pull=p + 4, rack_release=p + 11)
    c.gun(g)
    return c.finish()


def reload_fast(name="Reload_Fast_Tactical", full=False):
    """Быстрая (п. 3, 4): взмах пистолетом против часовой — старый магазин вылетает вправо и остаётся на земле."""
    end = 76 if full else 62
    c = Clip(name, end, dict(slide=1.0, stop=1.0) if full else None)
    FLICK = (-74, 7, -6, -0.020, 0.022, 0.034)
    c.fingers(R_THUMB, [(1, "grip"), (4, "catch"), (9, "catch"), (14, "grip")])
    c.part("catch", [(3, 0), (5, 1), (9, 1), (12, 0)])
    # левая сразу к подсумку; с кадра 7 в ней новый магазин, на его месте в шахте — старый (SpareMag), он вылетает
    c.hold([(7, 1), (33, 0)])
    c.scale("SpareMag_Control", [(7, 1), (21, 0)])
    c.fingers(L_FING, [(3, "free"), (7, "mag"), (33, "mag"), (36, "seat"), (42, "seat"), (52, "grip")])
    c.left([(7, ("world", *POUCH)), (13, ("world", *POUCH2)), (23, ("mag", 0.140)), (27, ("mag", 0.122)), (33, ("mag", MAG_DROP)),
            (36, ("seat", 0.048)), (38, ("seat", 0.0)), (41, ("seat", 0.007))])
    c.part("mag", [(33, MAG_DROP), (36, 0.048), (38, 0.0)])
    g = [k(1, REST), k(4, REST, roll=10, dz=0.008), k(8, FLICK), k(10, FLICK, roll=5, pitch=-1), k(22, G_SEAT), k(35, G_SEAT, roll=1),
         k(39, G_SEAT, pitch=1.6, dz=0.006), k(42, G_SEAT)]
    if full:
        p = 49
        c.fingers(R_THUMB, [(41, "grip"), (p - 2, "stop"), (p + 3, "stop"), (p + 9, "grip")])
        c.part("stop", [(p - 1, 1), (p + 1, 0)])
        c.part("slide", [(p, 1), (p + 2, 0)])
        g += [k(p, G_SEAT, roll=-8, pitch=-3), k(p + 3, G_SEAT, roll=-9, pitch=-5.5, dy=-0.006), k(66, REST, roll=3, pitch=1, dz=0.003),
              k(70, REST, roll=-1.2, pitch=-0.4), k(73, REST)]
        c.left([(60, "grip")])
        c.fingers(L_FING, [(60, "grip")])
        c.mark(slide_release=p + 1)
    else:
        g += [k(52, REST, roll=3, pitch=1, dz=0.003), k(56, REST, roll=-1.2, pitch=-0.4), k(59, REST)]
        c.left([(52, "grip")])
    c.gun(g)
    c.fly("SpareMag_Control", [(7, "rest", (0, 0, 0)), (9, tuple(-U * 0.085), (0, 0, 0)), (13, ("w", (-0.16, 0.02, -0.06)), (0, 40, 25)),
                               (20, ("w", (-0.22, 0.03, -0.42)), (30, 110, 60))])
    c.mark(catch=5, flick=8, mag_out=9, mag_new=13, insert=27, mag_in=33, seat=38)
    return c.finish()


def mag_check():
    """Проверка магазина (п. 5): вынуть, к глазам задней стенкой (окошки), вернуть."""
    t = 13
    c = Clip("Mag_Check", 114)
    c.fingers(R_THUMB, [(5, "grip"), (11, "catch"), (t + 5, "catch"), (t + 11, "grip")])
    c.part("catch", [(t - 2, 0), (t, 1), (t + 4, 1), (t + 7, 0)])
    c.part("mag", [(t, 0.0), (t + 4, MAG_DROP), (80, MAG_DROP), (84, 0.048), (87, 0.0)])
    c.hold([(t + 6, 1), (80, 0)])
    c.fingers(L_FING, [(t - 6, "free"), (t + 2, "free"), (t + 6, "mag"), (80, "mag"), (83, "seat"), (90, "seat"), (100, "grip")])
    eyes = MAG_HAND_W.translation + (EYE + Vector((0.02, -0.33, -0.125)) - MAG_C0)     # выше — предплечье закрывает кадр
    eyes2 = eyes + Vector((-0.004, 0.006, 0.004))
    c.left([(t - 1, ("mag", MAG_DROP + 0.008)), (t + 5, ("mag", MAG_DROP)), (t + 12, ("mag", 0.128)), (38, ("world", tuple(eyes), (10, -6, 14))),
            (60, ("world", tuple(eyes2), (12, -3, 9))), (68, ("mag", 0.140)), (73, ("mag", 0.122)), (80, ("mag", MAG_DROP)),
            (84, ("seat", 0.048)), (87, ("seat", 0.0)), (90, ("seat", 0.007)), (103, "grip")])
    LOW = (18, 4, 6, 0.012, 0.022, 0.006)
    c.gun([k(1, REST), k(11, G_MAG), k(26, G_MAG, roll=-2, pitch=1), k(38, LOW), k(60, LOW, roll=2, pitch=1), k(69, G_SEAT), k(83, G_SEAT, roll=1),
           k(88, G_SEAT, pitch=1.6, dz=0.006), k(92, G_SEAT), k(104, REST, roll=3, pitch=1, dz=0.003), k(108, REST, roll=-1.2, pitch=-0.4), k(111, REST)])
    c.mark(catch=t, mag_out=t + 12, hold_start=38, hold_end=60, insert=73, mag_in=80, seat=87)
    return c.finish()


def inspect():
    """Осмотр (п. 6): правая поворачивает пистолет к лицу левой стороной, большой вверх; второе нажатие — правой стороной."""
    c = Clip("Inspect", 122)
    LSIDE = (78, 12, 26, 0.075, 0.005, 0.075)       # ближе к глазам нельзя: манжета закрывает кадр
    RSIDE = (-104, 15, 16, 0.065, 0.010, 0.085)
    away = ((0.25, -0.30, 1.30), (10, 0, -15))      # левая опущена: вытянута вниз-влево, локоть не лезет в кадр
    c.left([(4, "grip"), (16, ("world", *away)), (98, ("world", away[0], (12, 2, -12))), (116, "grip")])
    c.fingers(L_FING, [(4, "grip"), (12, "free"), (102, "free"), (116, "grip")])
    c.fingers(R_THUMB, [(6, "grip"), (16, "up"), (52, "up"), (62, "grip"), (96, "grip")])
    c.gun([k(1, REST), k(8, REST, roll=8, dz=0.01, dx=0.01), k(20, LSIDE), k(50, LSIDE, roll=3, yaw=-3, pitch=1, dz=0.003),
           k(57, LSIDE, roll=-60, yaw=-6, dx=-0.004), k(66, RSIDE), k(94, RSIDE, roll=-4, yaw=3, pitch=1, dz=0.003),
           k(110, REST, roll=-5, pitch=1.5, dx=0.004, dz=0.004), k(114, REST, roll=1.5, pitch=-0.5), k(118, REST)])
    c.mark(left_side_start=20, left_side_end=50, right_side_start=66, right_side_end=94)
    return c.finish()


def rack(name="Slide_Rack", jam=False):
    """Передёрнуть затвор щепотью (досыл при закрытом затворе); jam — заклинивший затвор (п. 7): гильза в окне,
    затвор недозакрыт — отвести назад, гильза выпадает, отпустить."""
    c = Clip(name, 58, dict(slide=JAM_OPEN) if jam else None)
    s0 = JAM_OPEN if jam else 0.0
    c.left([(4, "grip"), (14, ("pinch", s0)), (17, ("pinch", s0)), (23, ("pinch", 1.0)), (25, ("pinch", 1.0, (-0.012, 0.012, 0.014))), (46, "grip")])
    c.fingers(L_FING, [(4, "grip"), (9, "free"), (14, "pinch"), (23, "pinch"), (26, "free"), (46, "grip")])
    c.part("slide", [(17, s0), (23, 1), (24, 1), (26, 0)])
    c.gun([k(1, REST)] + rack_gun(G_RACK, 13, 17, 23, 24)
          + [k(47, REST, roll=3, pitch=1, dz=0.003), k(51, REST, roll=-1.2, pitch=-0.4), k(54, REST)])
    if jam:
        c.scale("JamCase", [(1, 1), (36, 0)])
        c.fly("JamCase", [(1, "rest", (0, 0, 0)), (20, "rest", (0, 0, 0)), (23, ("w", (-0.03, 0.01, -0.02)), (40, 20, 60)),
                          (28, ("w", (-0.06, 0.02, -0.14)), (120, 60, 150)), (35, ("w", (-0.05, 0.02, -0.34)), (220, 110, 260))])
    c.mark(pinch=14, pull=17, case_out=20 if jam else 0, release=24)
    return c.finish()


def fire():
    """Выстрел (п. 8, 9): палец выжимает спуск, затвор отходит, гильза вылетает из окна вправо-вверх, спуск отпущен."""
    c = Clip("Fire", 24)
    for n in R_INDEX:                                 # выстрел — с пальцем на спуске в начале и в конце
        c.bone(n, 1, B["trigger"][n])
        c.bone(n, 24, B["trigger"][n])
    c.fingers(R_INDEX, [(3, "pressed"), (9, "pressed"), (13, "trigger")])
    c.part("trigger", [(1, 0), (3, 1), (9, 1), (13, 0)])
    c.part("slide", [(3, 0), (5, 1), (6, 1), (8, 0)])
    c.gun([k(1, REST), k(3, REST), k(6, REST, pitch=7, roll=-1.5, dy=0.013, dz=0.008), k(12, REST, pitch=-0.9, dy=-0.002), k(18, REST)])
    c.scale("Case", [(4, 1)])
    c.fly("Case", [(4, (0.004, -0.004, 0.004), (0, 0, 0)), (6, ("w", (-0.05, 0.03, 0.05)), (40, 30, 80)), (10, ("w", (-0.11, 0.05, 0.07)), (150, 80, 200)),
                   (16, ("w", (-0.13, 0.05, -0.04)), (300, 150, 380)), (24, ("w", (-0.14, 0.05, -0.30)), (480, 230, 560))])
    c.mark(press=3, slide_back=5, case_out=5, reset=13)
    return c.finish()


def finger_to_trigger():
    c = Clip("Finger_To_Trigger", 10)
    for n in R_INDEX:
        c.bone(n, 8, B["trigger"][n])
        c.bone(n, 10, B["trigger"][n])
    c.mark(on_trigger=8)
    return c.finish()


REC = {}
REC["Reload_Full"] = reload_tactical("Reload_Full", "stop")
REC["Reload_Full_Rack"] = reload_tactical("Reload_Full_Rack", "rack")
REC["Reload_Tactical"] = reload_tactical()
REC["Reload_Fast_Full"] = reload_fast("Reload_Fast_Full", True)
REC["Reload_Fast_Tactical"] = reload_fast()
REC["Mag_Check"] = mag_check()
REC["Inspect"] = inspect()
REC["Jam_Clear"] = rack("Jam_Clear", True)
REC["Slide_Rack"] = rack()
REC["Fire"] = fire()
REC["Finger_To_Trigger"] = finger_to_trigger()

# ================================================================ общая шкала NLA
assign(None)
for m in list(S.timeline_markers):
    S.timeline_markers.remove(m)
tracks = {}
for ob in (arms, wr):
    t = ob.animation_data.nla_tracks.new()
    t.name = "Клипы"
    tracks[ob.name] = t
for name, f in POSE_FRAMES.items():
    S.timeline_markers.new(f"ПОЗА {name}", frame=f)
at = 101
for name, rec in REC.items():
    act = bpy.data.actions[PREFIX + name]
    for ob in (arms, wr):
        st = tracks[ob.name].strips.new(name, at, act)
        st.action_slot = slot_of(act, ob)
        st.action_frame_start, st.action_frame_end = 1, rec["frames"]
        st.frame_end = at + rec["frames"] - 1
        st.extrapolation = "HOLD_FORWARD"
        st.blend_type = "REPLACE"
    rec["timeline_start"] = at
    S.timeline_markers.new(f"▶ {name}", frame=at)
    for mk, fr in rec["marks"].items():
        if fr:
            S.timeline_markers.new(f"{mk}", frame=at + fr - 1)
    at += rec["frames"] + GAP
S.frame_start, S.frame_end = 1, at - GAP
# Позы — рабочее действие обоих ригов (не дорожка NLA): ключ на кадре позы (I / K в Pose Mode) пишется прямо в него.
# Оно действует только на своих кадрах 1–100 (Extrapolation: Nothing), дальше играют клипы дорожки «Клипы».
poses_act.use_frame_range = False
for fc in [fc for layer in poses_act.layers for st in layer.strips for bag in st.channelbags for fc in bag.fcurves]:
    fc.keyframe_points.insert(TAIL, fc.evaluate(1))   # кадры 62–100: рука возвращается в хват, с него начинается первый клип
    fc.update()
assign(poses_act)
for ob in (arms, wr):
    ob.animation_data.action_extrapolation = "NOTHING"
    ob.animation_data.action_blend_type = "REPLACE"
    ob.animation_data.action_influence = 1.0
S.frame_set(1)
(ROOT / "_asset_src/asten919/anim/clips.json").write_text(json.dumps(REC, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
txt = bpy.data.texts.get("АСТЕН-919 — позы и клипы (читать)") or bpy.data.texts.new("АСТЕН-919 — позы и клипы (читать)")
lines = [__doc__, "", "Клипы (кадр начала на общей шкале, длина, фазы — кадры внутри клипа):"]
for name, rec in REC.items():
    lines.append(f"  {rec['timeline_start']:5d}  {name:22s} {rec['frames']:4d} к ({rec['seconds']:.2f} с)  {rec['marks']}")
lines += ["", "Позы (действие ASTEN919_Poses, кадры): " + ", ".join(f"{k_} {v}" for k_, v in POSE_FRAMES.items()),
          "",
          "КАК ПРАВИТЬ ХВАТ",
          "  Кадры 1–61 — позы (действие ASTEN919_Poses, оно рабочее: ключ пишется прямо в него). Кадры 101 и дальше —",
          "  клипы, они собраны скриптом из этих поз; руками их не править — пересборка сотрёт.",
          "  1. Встать на кадр позы (маркеры «ПОЗА …»), Pose Mode, поставить кости, выделить их (или все), I или K.",
          "  2. Сохранить файл, запустить tools\\asten919\\clips\\rebuild.cmd (в папке игры), в Blender — File → Revert.",
          "  Что в какой позе читается:",
          "     1  ХВАТ — всё: обе руки на пистолете, пальцы, место пистолета в кадре (Weapon_CTRL). С него начинается",
          "        и им кончается каждый клип.",
          "    11, 16 — только указательный правой (на спуске; спуск выжат).",
          "    21, 26, 31 — только большой правой (кнопка магазина; рычаг задержки; вверх для осмотра).",
          "    41 — левая рука с магазином: пальцы и место кисти. Магазин на этом кадре стоит на месте (вышел из шахты",
          "         на 55 мм) и за кистью не едет — кисть ставится вокруг него; в клипах он лежит в кисти так же.",
          "    ПИСТОЛЕТ (Weapon_CTRL) на кадрах 41, 46, 51 идёт в клипы: 41 — как он стоит, когда магазин вынимают,",
          "         46 — когда новый вставляют и досылают, 51 — пока левая тянет затвор. Кисть едет вместе с пистолетом.",
          "    46, 51 — левая: ладонь досылает магазин; щепоть на затворе (пальцы и ik_hand.L).",
          "         Рывки при оттягивании и отпускании затвора — числа RACK_TUG в build_clips.py.",
          "    На кадре 61 пистолет можно наклонять как удобно — в клипы это не идёт.",
          "    61 — левая свободна: только пальцы (куда рука идёт — в таблицах движения).",
          "  Остальные кости на кадрах 11–61 при пересборке копируются с кадра 1 — хват правится один раз."]
txt.from_string("\n".join(lines))
OUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True)
log("сохранено", OUT, "клипов", len(REC), "кадров на шкале", S.frame_end)
