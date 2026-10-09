"""Правая кисть на рукоятке затвора: сгиб указательного — перед рукояткой (тянуть назад), ладонь вниз,
остальные пальцы — свободный кулак у боковины (без проникновения в ствольную коробку по сетке перчатки).
Поза пишется в pose (не в action) — затем build_clips.py берёт её как HOOK.
blender --background <файл>.blend --python hook_pose.py -- <выход .blend>"""
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

OUT = sys.argv[sys.argv.index("--") + 1]
arms = bpy.data.objects["FPS_ArmsRig"]
skin = bpy.data.objects["FPS_Arms"]
sc = bpy.context.scene

# поза файла (левая — хват магазина) — сохранить; правая — из боевого хвата
ad = arms.animation_data or arms.animation_data_create()
ad.action = None
for pb in arms.pose.bones:
    pb.rotation_mode = "XYZ"
FILE = {pb.name: pb.matrix_basis.copy() for pb in arms.pose.bones}
ad.action = None
a = bpy.data.actions["VERAS54_Grip_Manual_v02"]
ad.action = a
if a.slots:
    ad.action_slot = a.slots[0]
sc.frame_set(1)
bpy.context.view_layer.update()
READY = {pb.name: pb.matrix_basis.copy() for pb in arms.pose.bones}
ad.action = None
for n, m in READY.items():
    arms.pose.bones[n].matrix_basis = m if (n.endswith(".R") or n.endswith(".R_end")) else FILE[n]
wr = bpy.data.objects["VERAS54_WeaponRig"]
if wr.animation_data:
    wr.animation_data.action = None
root = bpy.data.objects["VERAS54"]
if root.animation_data:
    root.animation_data.action = None
bpy.context.view_layer.update()

AW = arms.matrix_world
hand = arms.pose.bones["hand.R"]
ik = arms.pose.bones["ik_hand.R"]

# ось ладони в осях кисти: куда уходит кончик согнутого среднего пальца (боевой хват), без продольной оси
rot_h = (AW @ hand.matrix).to_3x3().normalized()
tip = AW @ arms.pose.bones["f_middle.03.R_end"].tail
knuckle = AW @ arms.pose.bones["f_middle.01.R"].head
curl = rot_h.inverted() @ (tip - knuckle)
curl.y = 0.0
PALM_LOCAL = curl.normalized()
print("HOOK ось ладони (локально)", tuple(round(v, 3) for v in PALM_LOCAL))

dg = bpy.context.evaluated_depsgraph_get()


def bvh_of(names):
    verts, polys = [], []
    for n in names:
        ob = bpy.data.objects[n].evaluated_get(dg)
        me = ob.to_mesh()
        b = len(verts)
        verts += [ob.matrix_world @ v.co for v in me.vertices]
        polys += [[b + i for i in p.vertices] for p in me.polygons]
        ob.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


HANDLE = "Charging handle • integral flattened shoe"
near = []
c0 = Vector((-0.165, -0.47, 1.715))
for ob in bpy.data.objects:
    if ob.type != "MESH" or ob.hide_get() or ob.name.startswith("FPS"):
        continue
    if (ob.matrix_world.translation - c0).length < 0.6:
        e = ob.evaluated_get(dg)
        pts = [e.matrix_world @ Vector(c) for c in e.bound_box]
        lo = Vector(map(min, *pts)) if False else Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        if lo.x < -0.12 and hi.y > -0.56 and lo.y < -0.38 and hi.z > 1.66 and lo.z < 1.76:
            near.append(ob.name)
WEAPON = bvh_of(near)
print("HOOK коллизия по", len(near), "деталям")
groups = {g.name: g.index for g in skin.vertex_groups}


def verts_of(bones):
    ids = {groups[b] for b in bones if b in groups}
    return [v.index for v in skin.data.vertices if sum(g.weight for g in v.groups if g.group in ids) > 0.4]


def gap(ids):
    bpy.context.view_layer.update()
    d2 = bpy.context.evaluated_depsgraph_get()
    ob = skin.evaluated_get(d2)
    me = ob.to_mesh()
    worst = 1.0
    for i in ids:
        p = ob.matrix_world @ me.vertices[i].co
        loc, _, _, d = WEAPON.find_nearest(p, 0.05)
        if loc is not None:
            worst = min(worst, d)
    ob.to_mesh_clear()
    return worst


def set_fingers(name, a1, a2, a3):
    for k, ang in zip((1, 2, 3), (a1, a2, a3)):
        pb = arms.pose.bones[f"{name}.0{k}.R"]
        pb.matrix_basis = Matrix.Identity(4)
        pb.rotation_euler = (math.radians(ang), 0, 0)


# 1) ориентация: ладонью вниз справа от коробки, костяшки вперёд
# side — ладонь к коробке (без скручивания предплечья: в риге нет кости скручивания, у манжеты видна кожа);
# top — ладонью вниз сверху
MODE = os.environ.get("HOOK_MODE", "down")
SIDE = MODE == "side"
DOWN = MODE == "down"     # кулак ладонью вниз, запястье прямое (кисть по оси предплечья)
y_w = Vector((0.0, -1.0, -0.06)).normalized()
palm_w = Vector((float(os.environ.get("HOOK_TILT", "0.75")), 0.0, -1.0))
if SIDE:
    y_w = Vector((0.0, -1.0, float(os.environ.get("HOOK_YZ", "0.04")))).normalized()
    palm_w = Vector((1.0, 0.0, float(os.environ.get("HOOK_PALMZ", "-0.12"))))
if DOWN:
    y_w = Vector((0.0, -1.0, -0.05)).normalized()
    palm_w = Vector((0.0, 0.0, -1.0))
palm_w = (palm_w - y_w * palm_w.dot(y_w)).normalized()
x_local = Vector((1, 0, 0)) if abs(PALM_LOCAL.x) < 0.9 else Vector((0, 0, 1))
# базис: локальная Y → y_w, локальная PALM → palm_w
third_l = Vector((0, 1, 0)).cross(PALM_LOCAL).normalized()
M_l = Matrix((Vector((0, 1, 0)), PALM_LOCAL, third_l)).transposed()


def make_R(yw, pw):
    pw = (pw - yw * pw.dot(yw)).normalized()
    M_w = Matrix((yw, pw, yw.cross(pw).normalized())).transposed()
    return M_w @ M_l.inverted()


R = make_R(y_w, palm_w)

# 2) пальцы: указательный — крюк, остальные — свободный кулак, большой вдоль
# Пальцы правой — из боевого хвата владельца: у правой кисти рига кости повёрнуты иначе, чем у левой,
# и сгиб «вокруг X» ломал пальцы вбок. Средний/безымянный/мизинец — кулак как на рукоятке; указательный —
# его спусковая форма (это и есть крючок), чуть разогнутая к исходной позе.
IDX_OPEN = float(os.environ.get("HOOK_IDX_OPEN", "0.2"))
for f in ("f_middle", "f_ring", "f_pinky", "palm"):
    for n in [pb.name for pb in arms.pose.bones if pb.name.startswith(f) and pb.name.endswith(".R")]:
        arms.pose.bones[n].matrix_basis = READY[n]
for n in ("f_index.01.R", "f_index.02.R", "f_index.03.R"):
    loc, rq, _ = READY[n].decompose()
    arms.pose.bones[n].matrix_basis = Matrix.Translation(loc) @ rq.slerp(rq.__class__(), IDX_OPEN).to_matrix().to_4x4()
# большой — подогнут в кулак (как в боевом хвате, где он обхватывает рукоятку), не лежит над планкой
THUMB_K = float(os.environ.get("HOOK_THUMB", "1.0"))
for n in ("thumb.01.R", "thumb.02.R", "thumb.03.R"):
    loc, rq, _ = READY[n].decompose()
    arms.pose.bones[n].matrix_basis = Matrix.Translation(loc) @ rq.__class__().slerp(rq, min(max(THUMB_K, 0.0), 1.0)).to_matrix().to_4x4()

# 3) положение: средний сустав указательного (голова f_index.02) — над передней кромкой рукоятки
hb = bpy.data.objects[HANDLE].evaluated_get(dg)
pts = [hb.matrix_world @ Vector(c) for c in hb.bound_box]
h_front = min(p.y for p in pts)
h_out = min(p.x for p in pts)
h_mid_z = sum(p.z for p in pts) / 8
h_top = max(p.z for p in pts)
h_cx = sum(p.x for p in pts) / 8
CROOK = Vector((h_out - 0.002, h_front - 0.0085, h_top + 0.009))
if SIDE:
    # средний сустав — снаружи конца рукоятки и перед ней; средняя фаланга заворачивает к стенке
    CROOK = Vector((h_out - 0.0065 - float(os.environ.get("HOOK_OUT", "0")), h_front - 0.0085,
                    h_mid_z + float(os.environ.get("HOOK_DZ", "0"))))
if DOWN:
    # средняя фаланга указательного — перед рукояткой, поперёк её внешней части
    CROOK = Vector((h_out + 0.004 - float(os.environ.get("HOOK_OUT", "0")), h_front - 0.0085,
                    h_mid_z + float(os.environ.get("HOOK_DZ", "0"))))
CROOK_BONE_MID = DOWN
for it in range(30 if DOWN else 6):
    if DOWN and it > 0:
        # прямое запястье: кисть по оси предплечья, ладонь вниз
        fa = arms.pose.bones["forearm.R"]
        y_w = (y_w + ((AW @ fa.tail) - (AW @ fa.head)).normalized()).normalized()
        R = make_R(y_w, Vector((0.0, 0.0, -1.0)))
    m = ik.matrix.copy()
    world = AW @ m
    world = Matrix.Translation(world.translation) @ R.to_4x4()
    ik.matrix = AW.inverted() @ world
    bpy.context.view_layer.update()
    b2 = arms.pose.bones["f_index.02.R"]
    crook = AW @ (((b2.head + b2.tail) * 0.5) if CROOK_BONE_MID else b2.head)
    err = CROOK - crook
    m = ik.matrix.copy()
    m.translation += AW.inverted().to_3x3() @ err
    ik.matrix = m
    bpy.context.view_layer.update()
    print("HOOK итерация", it, "ошибка сгиба, мм", round(err.length * 1000, 1), flush=True)
b2 = arms.pose.bones["f_index.02.R"]
fin = AW @ (((b2.head + b2.tail) * 0.5) if CROOK_BONE_MID else b2.head)
fa = arms.pose.bones["forearm.R"]
bend = math.degrees(((AW @ fa.tail) - (AW @ fa.head)).normalized().angle(y_w))
print("HOOK итог: ошибка сгиба, мм", round((CROOK - fin).length * 1000, 1), "излом запястья, °", round(bend, 1), flush=True)
reach = (AW @ arms.pose.bones["hand.R"].head - AW @ arms.pose.bones["ik_hand.R"].head).length
print("HOOK IK не дотянулась на, мм", round(reach * 1000, 1))

# 3б) большой палец — как в кулаке: прижат снаружи к средней фаланге указательного (не над коробкой).
# Сгибы 02/03 — из боевого хвата владельца; основание подбирается к цели с штрафом за отклонение
# от позы владельца (без этого палец выворачивало).
t1 = arms.pose.bones["thumb.01.R"]
tip_b = arms.pose.bones["thumb.03.R_end"] if "thumb.03.R_end" in arms.pose.bones else arms.pose.bones["thumb.03.R"]
bpy.context.view_layer.update()
i2 = arms.pose.bones["f_index.02.R"]
mid = AW @ ((i2.head + i2.tail) * 0.5)
TARGET = mid + (Vector((-0.012, -0.004, -0.006)) if DOWN else Vector((-0.011, 0.0, 0.006)))
base = t1.rotation_euler.copy()


def tcost(e):
    t1.rotation_euler = e
    bpy.context.view_layer.update()
    d = ((AW @ tip_b.tail) - TARGET).length
    dev = sum(abs(e[k] - base[k]) for k in range(3))
    return d + 0.006 * dev


cur = base.copy()
best = tcost(cur)
for step in (math.radians(8), math.radians(4), math.radians(2), math.radians(1)):
    improved = True
    while improved:
        improved = False
        for k in range(3):
            for sgn in (1, -1):
                e = cur.copy()
                e[k] += sgn * step
                c = tcost(e)
                if c < best - 1e-6:
                    best, cur, improved = c, e, True
t1.rotation_euler = cur
bpy.context.view_layer.update()
print("HOOK большой палец: до цели, мм", round(((AW @ tip_b.tail) - TARGET).length * 1000, 1),
      "поворот основания от позы владельца, °", [round(math.degrees(cur[k] - base[k]), 1) for k in range(3)], flush=True)

# 4) проверка: вершины перчатки внутри деталей (чётность пересечений лучами по трём осям)
def inside(p):
    votes = 0
    for d in (Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, 1, 0))):
        hits, o = 0, p.copy()
        for _ in range(40):
            loc, _, _, _ = WEAPON.ray_cast(o, d, 1.0)
            if loc is None:
                break
            hits += 1
            o = loc + d * 1e-5
        votes += hits % 2
    return votes >= 2


def count_in(parts):
    bpy.context.view_layer.update()
    d3 = bpy.context.evaluated_depsgraph_get()
    o = skin.evaluated_get(d3)
    mm = o.to_mesh()
    ids = verts_of([b.name for b in arms.pose.bones if b.name.endswith(".R") and b.name.startswith(parts)])
    n = sum(1 for i in ids if inside(o.matrix_world @ mm.vertices[i].co))
    o.to_mesh_clear()
    return n


lift = 0
while False:
    m = ik.matrix.copy()
    m.translation += AW.inverted().to_3x3() @ Vector((0, 0, 0.001))
    ik.matrix = m
    lift += 1
print("HOOK кисть поднята на, мм", lift)
bpy.context.view_layer.update()
d2 = bpy.context.evaluated_depsgraph_get()
ob = skin.evaluated_get(d2)
me = ob.to_mesh()
for part in ("hand", "palm", "f_index", "f_middle", "f_ring", "f_pinky", "thumb"):
    ids = verts_of([b.name for b in arms.pose.bones if b.name.endswith(".R") and b.name.startswith(part)])
    n_in = sum(1 for i in ids if inside(ob.matrix_world @ me.vertices[i].co))
    print("HOOK внутри деталей:", part, n_in, "из", len(ids), flush=True)
# зона прицела: над ствольной коробкой (правее x −0.166 и выше z 1.725) — перчатки там быть не должно
over = [i for i in range(len(me.vertices)) if (lambda p: p.x > -0.166 and p.z > 1.725)(ob.matrix_world @ me.vertices[i].co)]
rv = set(verts_of([b.name for b in arms.pose.bones if b.name.endswith(".R")]))
over_r = [i for i in over if i in rv]
top = max(((ob.matrix_world @ me.vertices[i].co).z for i in rv), default=0)
print("HOOK над коробкой вершин правой:", len(over_r), "верх кисти z", round(top, 4), flush=True)
from collections import Counter
gi = {g.index: g.name for g in skin.vertex_groups}
cnt = Counter()
for i in over_r:
    v = skin.data.vertices[i]
    if v.groups:
        cnt[gi[max(v.groups, key=lambda g: g.weight).group]] += 1
print("HOOK над коробкой по костям:", dict(cnt.most_common(8)), flush=True)
# по деталям: какая деталь ближе всего к «внутренним» вершинам ладони и большого пальца
per = {n: bvh_of([n]) for n in near}
ids = verts_of([b.name for b in arms.pose.bones if b.name.endswith(".R") and b.name.startswith(("palm", "thumb", "f_index", "f_middle", "f_ring", "f_pinky", "hand"))])
hit = {}
for i in ids:
    p = ob.matrix_world @ me.vertices[i].co
    if inside(p):
        best = min(near, key=lambda n: per[n].find_nearest(p, 0.2)[3] if per[n].find_nearest(p, 0.2)[0] is not None else 9)
        d = per[best].find_nearest(p, 0.2)[3]
        hit.setdefault(best, []).append(round(d * 1000, 1))
for n, ds in hit.items():
    print("HOOK деталь", n, "вершин", len(ds), "глубже всего, мм", max(ds), flush=True)
ob.to_mesh_clear()
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("HOOK saved", OUT)
