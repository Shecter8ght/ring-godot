"""ВЕРАС-54 v13: клипы переключения режима огня большим пальцем правой руки (решение владельца 2026-10-19:
X — по кругу АВ → 2 → ОД → АВ, предохранителя нет; «переключение большим пальцем правой руки»).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup ".../Риг v13/VERAS54_Rig_v13.blend" --python-exit-code 1
    --python tools/veras54_v13/clips/fire_mode_clip.py -- <откуда> <куда> <выход .blend> [varn_v1|varn_v2] [preview=<префикс>]
откуда / куда — auto | burst | semi (положения рычага: АВ, «2» на 3,92° ниже, ОД на 7,85° ниже — метки и ямки фиксатора,
_asset_src/veras54_v13/tex/gen_selector_track.py). Вниз — палец ложится на полочку лепестка сверху и давит; вверх (ОД → АВ) —
подводится под полочку и толкает.

Большой палец в боевом хвате лежит слева от рукоятки, полочка — справа, в 114 мм от него: кисть отпускает рукоятку, ладонь
ложится вдоль правой стенки коробки (пальцы приоткрыты, над магазином), большой палец по IK трёх фаланг встаёт подушечкой на
полочку, переводит рычаг и кисть возвращается в хват. Кадры (30 к/с): 1 хват — 6 кисть у коробки, палец у полочки — 8 касание —
11 рычаг щёлкнул — 13 палец отошёл — 18 хват. Пальцы и большой палец запечены по кадрам, IK-цель кисти — редкими ключами.
В игре рычаг ставит сама игра по режиму (служебный клип selector_by_mode); участок 8→11 — config.fire_mode_push в data/weapons.json.
Действия: VERAS54_Firemode_<откуда>_<куда>[_<рукоятка>]_<Arms|Weapon>_v01.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
DATA = Path("E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия/Клипы v02 (Claude)")
sys.path.insert(0, str(HERE))
import rig_common as rc  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:]
SRC_MODE, DST_MODE, OUT = ARGS[:3]
GID = next((a for a in ARGS[3:] if a in rc.GRIPS), "")
PREVIEW = next((a.split("=", 1)[1] for a in ARGS[3:] if a.startswith("preview=")), "")
TAG = f"Firemode_{SRC_MODE}_{DST_MODE}" + (f"_{GID}" if GID else "")
FPS = 30
END = 18
ANGLE = {"auto": 0.0, "burst": math.radians(3.92), "semi": 0.1370083}   # вниз — плюс (как драйвер рига: ОД 0,137)
DOWN = ANGLE[DST_MODE] > ANGLE[SRC_MODE]
# кисть у коробки: сдвиг IK-цели правой кисти в осях VERAS54 (м) — вперёд, вправо, вверх; палец — над / под полочкой
_shift = next((a.split('=', 1)[1] for a in ARGS[3:] if a.startswith('shift=')), '')
HAND_SHIFT = Vector([float(v) for v in _shift.split(':')]) if _shift else Vector((0.075, -0.022, 0.035 if DOWN else 0.025))
HOVER = 0.012            # палец над полочкой до касания и после
# подушечка — ближе к наружному краю полочки (−Y): иначе бок пальца заходит в окно выброса к затворной раме
OUTWARD = float(next((a.split('=', 1)[1] for a in ARGS[3:] if a.startswith('out=')), 0.006))
PAD = 0.007              # центр подушечки — над поверхностью полочки
FINGERS_OPEN = float(next((a.split('=', 1)[1] for a in ARGS[3:] if a.startswith('open=')), 0.15))   # пальцы правой кисти
# приоткрыты, пока кисть не на рукоятке (0 — хват, 1 — покой рига)

sc = bpy.context.scene
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, END
for m in list(sc.timeline_markers):
    sc.timeline_markers.remove(m)
arms = bpy.data.objects["FPS_ArmsRig"]
wr = bpy.data.objects["VERAS54_WeaponRig"]
root = bpy.data.objects["VERAS54"]
magob = bpy.data.objects["Magazine"]
for c in bpy.data.collections:
    if "Suppressor" in c.name:
        c.hide_viewport = True
        c.hide_render = True
for ob in (arms, wr, root, magob):
    if ob.animation_data:
        ob.animation_data.action = None
for pb in list(arms.pose.bones) + list(wr.pose.bones):
    pb.rotation_mode = "XYZ"

READY = rc.ready_pose(arms)
if GID:
    for n, v in json.loads((DATA / f"grip_{GID}_pose.json").read_text(encoding="utf-8")).items():
        READY[n] = Matrix(v)
    rc.add_grip(GID)
ALL = [pb.name for pb in arms.pose.bones]
THUMB = ["thumb.01.R", "thumb.02.R", "thumb.03.R"]
FINGERS = [b.name for b in arms.pose.bones if b.name.endswith(".R") and b.name.split(".")[0] in
           ("palm", "f_index", "f_middle", "f_ring", "f_pinky") and not b.name.endswith("_end")]


def apply(pose):
    for n, m in pose.items():
        arms.pose.bones[n].matrix_basis = m
    bpy.context.view_layer.update()


def lerp_m(a, b, t):
    la, ra, _ = a.decompose()
    lb, rb, _ = b.decompose()
    return Matrix.Translation(la.lerp(lb, t)) @ ra.slerp(rb, t).to_matrix().to_4x4()


def smooth(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


def track(keys, f):
    """Значение по ключам (кадр, значение) с плавным входом и выходом на каждом участке."""
    if f <= keys[0][0]:
        return keys[0][1]
    for a, b in zip(keys, keys[1:]):
        if a[0] <= f <= b[0]:
            return a[1] + (b[1] - a[1]) * smooth((f - a[0]) / (b[0] - a[0]))
    return keys[-1][1]


# ---------------------------------------------------------------- рычаг переводчика: без драйвера, ключами
wr.driver_remove('pose.bones["Selector"].rotation_euler', 1)
sel = wr.pose.bones["Selector"]
to_veras = root.matrix_world.inverted()


def shelf_contact(angle):
    """Точка касания на полочке лепестка (мир): середина верха (вниз) или низа (вверх) при угле рычага angle."""
    sel.rotation_euler[1] = angle
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ob = bpy.data.objects["Selector_Steel"].evaluated_get(dg)
    me = ob.to_mesh()
    pts = [ob.matrix_world @ v.co for v in me.vertices]
    ob.to_mesh_clear()
    shelf = [p for p in pts if 0.134 <= (to_veras @ p).x <= 0.152]
    c = sum(shelf, Vector()) / len(shelf)
    zs = [(to_veras @ p).z for p in shelf]
    z = max(zs) if DOWN else min(zs)
    local = to_veras @ c
    local.z = z
    local.y -= OUTWARD
    return root.matrix_world @ local


UP_W = (root.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
SIDE = 1.0 if DOWN else -1.0
C_FROM = shelf_contact(ANGLE[SRC_MODE])
C_TO = shelf_contact(ANGLE[DST_MODE])
print("FIREMODE shelf mm", [round(v * 1000, 1) for v in to_veras @ C_FROM], "→", [round(v * 1000, 1) for v in to_veras @ C_TO])

# ---------------------------------------------------------------- кисть: IK-цель правой
apply(READY)
ikR = arms.pose.bones["ik_hand.R"]
IKR_READY = ikR.matrix.copy()
A = arms.matrix_world.inverted() @ root.matrix_world            # оси VERAS54 → пространство арматуры
SHIFT_ARM = A.to_3x3() @ HAND_SHIFT
HAND_KEYS = [(1, 0.0), (6, 1.0), (13, 1.0), (END, 0.0)]


def hand_at(f):
    w = track(HAND_KEYS, f)
    return Matrix.Translation(SHIFT_ARM * w) @ IKR_READY


def fingers_at(f):
    return track(HAND_KEYS, f) * FINGERS_OPEN


# путь подушечки большого пальца (мир): над полочкой → касание → с рычагом → над новым положением
def pad_at(f):
    if f <= 8:
        k = smooth((f - 6) / 2.0) if f > 6 else 0.0
        return C_FROM + UP_W * SIDE * (PAD + HOVER * (1.0 - k))
    if f <= 11:
        return C_FROM.lerp(C_TO, smooth((f - 8) / 3.0)) + UP_W * SIDE * PAD
    k = smooth((f - 11) / 2.0)
    return C_TO + UP_W * SIDE * (PAD + HOVER * k)


THUMB_KEYS = [(1, 0.0), (3, 0.0), (6, 1.0), (13, 1.0), (16, 0.0), (END, 0.0)]


def thumb_pad_world():
    """Центр подушечки большого пальца: вершины перчатки, где главная кость — thumb.03.R."""
    dg = bpy.context.evaluated_depsgraph_get()
    glove = bpy.data.objects["FPS_Arms"]
    eo = glove.evaluated_get(dg)
    me = eo.to_mesh()
    gi = glove.vertex_groups["thumb.03.R"].index
    pts = []
    for v in glove.data.vertices:
        w = {g.group: g.weight for g in v.groups}
        if w.get(gi, 0.0) > 0.5 and max(w.values()) == w[gi]:
            pts.append(eo.matrix_world @ me.vertices[v.index].co)
    eo.to_mesh_clear()
    return sum(pts, Vector()) / len(pts)


# IK трёх фаланг большого пальца к пустышке; цель поправляется так, чтобы на точку встала подушечка, а не конец кости
tgt = bpy.data.objects.new("chk_thumb_target", None)
sc.collection.objects.link(tgt)
ik = arms.pose.bones["thumb.03.R"].constraints.new("IK")
ik.target = tgt
ik.chain_count = 3
ik.use_tail = True
ik.use_rotation = False


# ---------------------------------------------------------------- позы по кадрам
baked = {}
reach = 0.0
for f in range(1, END + 1):
    apply(READY)
    ikR.matrix = hand_at(f)
    open_k = fingers_at(f)
    for n in FINGERS:
        arms.pose.bones[n].matrix_basis = lerp_m(READY[n], Matrix.Identity(4), open_k)
    bpy.context.view_layer.update()
    w = track(THUMB_KEYS, f)
    ik.influence = w
    want = pad_at(f)
    tgt.location = want
    for _ in range(4):
        bpy.context.view_layer.update()
        if w <= 0.0:
            break
        miss = want - thumb_pad_world()
        tgt.location = tgt.location + miss
    bpy.context.view_layer.update()
    if w >= 1.0:
        reach = max(reach, (want - thumb_pad_world()).length)
    pose = {}
    for n in ALL:
        pb = arms.pose.bones[n]
        if n in THUMB:
            pose[n] = arms.convert_space(pose_bone=pb, matrix=pb.matrix, from_space="POSE", to_space="LOCAL").copy()
        else:
            pose[n] = pb.matrix_basis.copy()
    pose["ik_hand.R"] = ikR.matrix_basis.copy()
    baked[f] = pose
arms.pose.bones["thumb.03.R"].constraints.remove(ik)
bpy.data.objects.remove(tgt, do_unlink=True)
print("FIREMODE thumb pad miss mm", round(reach * 1000, 1))

# ---------------------------------------------------------------- ключи
ad = arms.animation_data or arms.animation_data_create()
arm_act = bpy.data.actions.new(f"VERAS54_{TAG}_Arms_v01")
ad.action = arm_act
wad = wr.animation_data or wr.animation_data_create()
w_act = bpy.data.actions.new(f"VERAS54_{TAG}_Weapon_v01")
wad.action = w_act
for a in (arm_act, w_act):
    a.use_fake_user = True


def key(pb, frame):
    pb.keyframe_insert("location", frame=frame)
    pb.keyframe_insert("rotation_euler", frame=frame)


prev = {}
for f in range(1, END + 1):
    sparse = f in (1, 6, 13, END)
    for n in ALL:
        dense = n in THUMB or n in FINGERS
        if not (dense or sparse):
            continue
        pb = arms.pose.bones[n]
        pb.matrix_basis = baked[f][n] if n in baked[f] else READY[n]
        if n in prev:
            pb.rotation_euler = pb.matrix_basis.to_euler("XYZ", prev[n])
        prev[n] = pb.rotation_euler.copy()
        key(pb, f)
SEL_KEYS = [(1, ANGLE[SRC_MODE]), (8, ANGLE[SRC_MODE]), (11, ANGLE[DST_MODE]), (END, ANGLE[DST_MODE])]
for f in range(1, END + 1):
    sel.rotation_euler[1] = track(SEL_KEYS, f)
    sel.keyframe_insert("rotation_euler", index=1, frame=f)


def fcurves(act):
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                out.extend(bag.fcurves)
    return out


for act in (arm_act, w_act):
    for fc in fcurves(act):
        dense = len(fc.keyframe_points) > 6
        for kp in fc.keyframe_points:
            if dense:
                kp.interpolation = "LINEAR"
            else:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
for name, frame in (("Хват", 1), ("Кисть у коробки", 6), ("Палец на полочке", 8), ("Рычаг щёлкнул", 11),
                    ("Палец отошёл", 13), ("Хват ", END)):
    sc.timeline_markers.new(name, frame=frame)

# правая перчатка не входит в оружие? (вершины перчатки правой кисти внутри деталей оружия, кроме подушечки большого пальца
# на полочке — там касание)
from mathutils.bvhtree import BVHTree  # noqa: E402
glove = bpy.data.objects["FPS_Arms"]
right_groups = {glove.vertex_groups[n].index for n in FINGERS + THUMB + ["hand.R"] if n in glove.vertex_groups}
right_verts = []
for v in glove.data.vertices:
    if v.groups:
        g = max(v.groups, key=lambda g: g.weight)
        if g.group in right_groups:
            right_verts.append(v.index)
gun = [o for o in bpy.data.objects if o.type == "MESH" and o.visible_get() and not o.name.startswith(("FPS_Arms", "chk_"))
       and any(o.name.startswith(k) for k in ("Receiver", "Dust cover", "Magazine", "Magwell", "Trigger", "Pistol grip", "Selector",
                                               "Bolt", "Handguard", "Rear sight", "Gas", "Stock"))]
worst_pen = {}
for f in (1, 6, 8, 10, 11, 13):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    eo = glove.evaluated_get(dg)
    me = eo.to_mesh()
    pts = [(i, eo.matrix_world @ me.vertices[i].co) for i in right_verts]
    eo.to_mesh_clear()
    per = {}
    for part in gun:
        tree = rc.bvh_of([part], dg)
        inside, deep = 0, 0.0
        for i, co in pts:
            loc, nrm, _, dist = tree.find_nearest(co)
            # внутри: ближайшая точка «спереди» по нормали и луч наружу пересекает деталь нечётное число раз — грубо: по нормали
            if loc is not None and dist < 0.02 and (co - loc).dot(nrm) < -0.0005:
                inside += 1
                deep = max(deep, dist)
        if inside:
            per[part.name[:28]] = (inside, round(deep * 1000, 1))
    worst_pen[f] = per
for f, per in worst_pen.items():
    print("FIREMODE перчатка в оружии, кадр", f, per)

# IK кисти дотягивается?
worst = 0.0
for f in range(1, END + 1):
    sc.frame_set(f)
    worst = max(worst, (arms.pose.bones["hand.R"].head - arms.pose.bones["ik_hand.R"].head).length)
print("FIREMODE", TAG, "кадров", END, "IK кисти не дотянулась, мм", round(worst * 1000, 1))

txt = bpy.data.texts.get("Клипы — как править") or bpy.data.texts.new("Клипы — как править")
txt.from_string(__doc__ + f"""
Клип {TAG}: кадры 1–{END}, {FPS} к/с. Действия: {arm_act.name} (FPS_ArmsRig), {w_act.name} (VERAS54_WeaponRig: рычаг Selector).
Драйвер рычага в этом файле снят — угол рычага ключами (Y-поворот кости Selector). Маркеры — фазы.""")
sc.frame_set(1)
if PREVIEW:
    rc.hide_suppressor()
    rc.preview(Path(PREVIEW), (C_FROM + C_TO) * 0.5, ["fps", "right", "close"], [1, 6, 8, 11, 13])
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("FIREMODE saved", OUT)
