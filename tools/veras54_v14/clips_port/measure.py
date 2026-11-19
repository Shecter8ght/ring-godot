"""ВЕРАС-54: старая игровая сетка (v13) в файле клипов против новой (v14) — места хвата и касания перчатки.

Только чтение: открывается КОПИЯ файла клипов, новая сетка добавляется в память, файл не сохраняется.

blender -b <копия ВЕРАС-54_руки_клипы_v01.blend> --factory-startup --python tools/veras54_v14/clips_port/measure.py --
        <VERAS54_Game_LP.blend> <выход.json>

Оси — VERAS54_WeaponRig (+X к дулу, +Y влево стрелка, +Z вверх; у обеих сеток X = 0 — задний торец коробки, Z = 0 — ось
ствола), мм. Новая сетка ставится тождественно в эти оси; подвижные узлы — на кости старого рига с тем же назначением
(рама → Bolt, переводчик → Selector, спуск → Trigger, защёлка → MagazineLatch, магазин → Magazine, приклад → StockFold,
дульное → MuzzleAttachment): так новая сетка едет в позах и клипах владельца так же, как старая.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "clips"))
import clip_tools as CT  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
LP, OUT = args[0], args[1]
log = lambda *a: print("MEAS", *a, flush=True)  # noqa: E731
S = bpy.context.scene
arms, wr = CT.rigs()
root = bpy.data.objects["VERAS54"]
glove = bpy.data.objects["FPS_Arms"]
NEW_PARENT = {"Receiver": "WeaponRoot", "Bolt_Carrier": "Bolt", "Selector_Lever": "Selector", "Trigger": "Trigger",
              "Mag_Catch": "MagazineLatch", "Magazine": "Magazine", "Stock_Knuckle": "StockFold",
              "MuzzleDevice": "MuzzleAttachment", "Cover_Button": "CoverButton"}
OLD_PARTS = dict(body=["Body_Polymer", "Body_Steel", "DustCover_Steel", "CoverButton_Steel"], bolt=["Bolt_Steel"],
                 selector=["Selector_Steel"], trigger=["Trigger_Steel"], latch=["MagazineLatch_Steel"],
                 stock=["StockFold_Polymer", "StockFold_Steel"], muzzle=["MuzzleDevice_Steel"],
                 mag=["Magazine_Body", "Magazine_Steel"])
NEW_PARTS = dict(body=["Receiver__Body", "Receiver__Front", "Dust_Cover__Body", "Cover_Button__Body", "Rear_Sight_Leaf__Body",
                       "Rear_Sight_Slider__Body", "Rear_Sight_Drum__Body", "Rear_Sight_Knob__Body", "Rear_Sight_Button_L__Body",
                       "Rear_Sight_Button_R__Body", "Handguard_Latch__Front", "Hinge_Latch__Body"],
                 bolt=["Bolt_Carrier__Body"], selector=["Selector_Lever__Body"], trigger=["Trigger__Body"],
                 latch=["Mag_Catch__Body"], stock=["Stock_Knuckle__Front", "Stock_Body__Front", "Stock_Latch__Front"],
                 muzzle=["MuzzleDevice__Front"], mag=["Magazine__Mag"])


def update():
    bpy.context.view_layer.update()


def rest():
    for ob in (arms, wr, root, bpy.data.objects["Magazine"]):
        if ob.animation_data:
            ob.animation_data.action = None
    for pb in wr.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    for n in ("SpareMag", "JamCase", "Suppressor_Control"):
        wr.pose.bones[n].scale = (0.001,) * 3
    for c in (pb.constraints.get("В левой кисти") for pb in wr.pose.bones):
        if c:
            c.influence = 0.0
    for k, v in {"Bolt pull": 0.0, "Magazine latch press": 0.0, "Trigger pull": 0.0, "Fire mode": 1.0, "Selector from mode": 1.0,
                 "Selector blend": 1.0, "Muzzle attachment": 0.0, "Magazine removed": 0.0, "Stock fold": 0.0,
                 "Cover button press": 0.0, "Cover lift": 0.0}.items():
        root[k] = v
    root.update_tag()
    bpy.data.objects["Magazine"]["Rounds remaining"] = 30.0
    update()


# ---------------------------------------------------------------- новая сетка
rest()
with bpy.data.libraries.load(LP, link=False) as (src, dst):
    names_src = [n for n in src.objects if not n.endswith("_LOD1")]
    dst.objects = list(names_src)
coll = bpy.data.collections.new("NEW v14 (разведка)")
S.collection.children.link(coll)
NEW = {}
for n, o in zip(names_src, dst.objects):
    if o is None:
        continue
    coll.objects.link(o)
    NEW[n] = o                                     # имя в файле сетки (в файле клипов у одноимённых — «.001»)
keep = list(NEW.values())
for o in keep:
    o.animation_data_clear()                       # приводы новой сетки — прочь; «покой» = переводчик на АВ (0,55215)
    o.delta_location = (0, 0, 0)
    o.delta_rotation_euler = (0, 0, 0)
    o.delta_scale = (1, 1, 1)
NAME_OF = {o: n for n, o in NEW.items()}
update()
local = {}                                         # где узел стоит в осях рига оружия (покой)
for o in keep:
    m = Matrix.Identity(4)
    q = o
    while q is not None:                           # мировая матрица по цепочке родителей (у только что добавленного не посчитана)
        m = q.matrix_basis @ m if q.parent is None else (q.matrix_parent_inverse @ q.matrix_basis) @ m
        q = q.parent
    local[NAME_OF[o]] = m
WRW = wr.matrix_world.copy()
for name, bone in NEW_PARENT.items():
    o = NEW[name]
    o.parent = wr
    o.parent_type = "BONE"
    o.parent_bone = bone
    o.matrix_parent_inverse = Matrix.Identity(4)
update()
for name in NEW_PARENT:
    NEW[name].matrix_world = WRW @ local[name]
update()
for o in keep:                                      # проверка: в покое каждый узел там, где в файле сетки
    err = max(abs(a - b) for ra, rb in zip(WRW.inverted() @ o.matrix_world, local[NAME_OF[o]]) for a, b in zip(ra, rb))
    if err > 1e-5:
        log("узел не на месте", NAME_OF[o], err)
log("новая сетка добавлена: объектов", len(keep))


# ---------------------------------------------------------------- геометрия в осях рига, мм
def tris_of(names):
    """Треугольники объектов (вычисленные) в осях рига оружия, мм → (N, 3, 3)."""
    dg = bpy.context.evaluated_depsgraph_get()
    W = wr.matrix_world.inverted()
    out = []
    for n in names:
        o = bpy.data.objects.get(n)
        if o is None or o.type != "MESH":
            continue
        e = o.evaluated_get(dg)
        me = e.to_mesh()
        me.calc_loop_triangles()
        M = W @ e.matrix_world
        co = np.array([tuple(M @ v.co) for v in me.vertices]) * 1000.0
        tri = np.array([lt.vertices[:] for lt in me.loop_triangles], dtype=np.int64)
        e.to_mesh_clear()
        if len(tri):
            out.append(co[tri])
    return np.concatenate(out) if out else np.zeros((0, 3, 3))


def section(T, axis, value):
    """Сечение треугольников плоскостью coord[axis] = value → точки (M, 3)."""
    if not len(T):
        return np.zeros((0, 3))
    d = T[:, :, axis] - value
    pts = []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        a, b = d[:, i], d[:, j]
        m = (a * b) < 0
        t = a[m] / (a[m] - b[m])
        pts.append(T[m, i] + (T[m, j] - T[m, i]) * t[:, None])
    return np.concatenate(pts) if pts else np.zeros((0, 3))


def r1(v):
    return None if v is None else round(float(v), 1)


def stat(P, sel=None):
    if sel is not None:
        P = P[sel]
    if not len(P):
        return None
    return dict(x=[r1(P[:, 0].min()), r1(P[:, 0].max())], y=[r1(P[:, 1].min()), r1(P[:, 1].max())], z=[r1(P[:, 2].min()), r1(P[:, 2].max())])


rest()
OT = {k: tris_of(v) for k, v in OLD_PARTS.items()}
NT = {k: tris_of(v) for k, v in NEW_PARTS.items()}
F = {}


def both(name, fn):
    F[name] = dict(old=fn(OT), new=fn(NT))


# пистолетная рукоятка: сечения по высоте — спинка (min x), перед (max x), ширина (|y|)
def grip(T):
    out = {}
    for z in (-45, -60, -75, -90, -105, -120, -135, -150):
        P = section(T["body"], 2, z)
        P = P[(P[:, 0] > -40) & (P[:, 0] < (78 if z < -62 else 70)) & (np.abs(P[:, 1]) < 30)]
        if len(P):
            out[str(z)] = dict(back=r1(P[:, 0].min()), front=r1(P[:, 0].max()), half_w=r1(np.abs(P[:, 1]).max()))
    B = T["body"].reshape(-1, 3)
    g = B[(B[:, 0] > -40) & (B[:, 0] < 80) & (np.abs(B[:, 1]) < 30)]
    i = g[:, 2].argmin()
    out["bottom"] = [r1(g[i, 0]), r1(g[i, 2])]
    pts = [(v["back"], int(k)) for k, v in out.items() if k.lstrip("-").isdigit() and int(k) <= -60]
    if len(pts) >= 2:
        xs, zs = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
        k = np.polyfit(zs, xs, 1)[0]
        out["back_angle_deg"] = r1(math.degrees(math.atan(k)))
    return out


both("grip", grip)


def trigger(T):
    out = {}
    for z in (-35, -45, -55, -62):
        P = section(T["trigger"], 2, z)
        if len(P):
            out[str(z)] = dict(front=r1(P[:, 0].max()), back=r1(P[:, 0].min()))
    A = T["trigger"].reshape(-1, 3)
    out["tip_z"] = r1(A[:, 2].min())
    out["bbox"] = stat(A)
    return out


both("trigger", trigger)


def guard(T):
    out = {}
    for x in (75, 90, 105, 120, 130):
        P = section(T["body"], 0, x)
        P = P[(P[:, 2] < -30) & (P[:, 2] > -100) & (np.abs(P[:, 1]) < 15)]
        if len(P):
            out[str(x)] = dict(bottom=r1(P[:, 2].min()))
    return out


both("guard", guard)


def handguard(T):
    out = {}
    for x in (270, 300, 330, 360, 390, 420):
        P = section(T["body"], 0, x)
        if not len(P):
            continue
        mid = P[np.abs(P[:, 2]) < 4]
        low = P[(P[:, 2] < -10) & (P[:, 2] > -22)]
        out[str(x)] = dict(bottom=r1(P[:, 2].min()), top=r1(P[:, 2].max()),
                           half_w_z0=r1(np.abs(mid[:, 1]).max()) if len(mid) else None,
                           half_w_z15=r1(np.abs(low[:, 1]).max()) if len(low) else None,
                           left=r1(P[:, 1].max()), right=r1(P[:, 1].min()),
                           left_z=[r1(P[P[:, 1] > P[:, 1].max() - 1.5][:, 2].min()), r1(P[P[:, 1] > P[:, 1].max() - 1.5][:, 2].max())])
    return out


both("handguard", handguard)


def mag(T):
    out = {}
    M = T["mag"]
    for z in (-15, -30, -60, -90, -120, -150, -180):
        P = section(M, 2, z)
        if len(P):
            out[str(z)] = dict(rear=r1(P[:, 0].min()), front=r1(P[:, 0].max()), half_w=r1(np.abs(P[:, 1]).max()))
    A = M.reshape(-1, 3)
    out["bbox"] = stat(A)
    i = A[:, 2].argmin()
    out["lowest"] = [r1(A[i, 0]), r1(A[i, 2])]
    top = A[A[:, 2] > A[:, 2].max() - 12]
    j = top[:, 0].argmax()
    out["front_top"] = [r1(top[j, 0]), r1(top[j, 2])]
    k = top[:, 0].argmin()
    out["rear_top"] = [r1(top[k, 0]), r1(top[k, 2])]
    return out


both("magazine", mag)


def latch(T):
    A = T["latch"].reshape(-1, 3)
    i = A[:, 2].argmin()
    return dict(bbox=stat(A), lowest=[r1(A[i, 0]), r1(A[i, 2])])


both("mag_catch", latch)


def handle(T):
    A = T["bolt"].reshape(-1, 3)
    h = A[A[:, 1] < -24]
    if not len(h):
        return None
    i = h[:, 1].argmin()
    return dict(bbox=stat(h), tip=[r1(h[i, 0]), r1(h[i, 1]), r1(h[i, 2])], centre=[r1(v) for v in h.mean(0)])


both("charging_handle", handle)


def selector(T):
    A = T["selector"].reshape(-1, 3)
    i = A[:, 0].argmax()
    return dict(bbox=stat(A), end=[r1(A[i, 0]), r1(A[i, 1]), r1(A[i, 2])])


both("selector", selector)


def stock(T):
    A = T["stock"].reshape(-1, 3)
    i = A[:, 0].argmin()
    butt = A[A[:, 0] < A[:, 0].min() + 6]
    return dict(bbox=stat(A), butt_z=[r1(butt[:, 2].min()), r1(butt[:, 2].max())], butt_x=r1(A[i, 0]))


both("stock", stock)


def muzzle(T):
    A = T["muzzle"].reshape(-1, 3)
    return dict(bbox=stat(A), radius=r1(np.sqrt(A[:, 1] ** 2 + A[:, 2] ** 2).max()))


both("muzzle", muzzle)


def top(T):
    out = {}
    for x in (20, 60, 100, 150, 200, 240):
        P = section(T["body"], 0, x)
        P = P[np.abs(P[:, 1]) < 40]
        if len(P):
            out[str(x)] = dict(top=r1(P[:, 2].max()), right=r1(P[:, 1].min()), left=r1(P[:, 1].max()))
    return out


both("receiver", top)
# кнопка крышки
F["cover_button"] = dict(old=stat(tris_of(["CoverButton_Steel"]).reshape(-1, 3)), new=stat(tris_of(["Cover_Button__Body"]).reshape(-1, 3)))
# оси, кости старого рига против узлов новой
F["pivots"] = dict(old={b.name: [r1(v * 1000) for v in b.head_local] for b in wr.data.bones},
                   new={n: [r1(v * 1000) for v in local[n].translation] for n in NEW if not n.endswith(("__Body", "__Front", "__Mag"))})
# рукоятки ВАРН и фонарь (старые объекты)
for n in ("Foregrip • varn_v1", "Foregrip • varn_v2", "Глушитель • supp_veras", "DOZOR_P"):
    o = bpy.data.objects.get(n)
    if o is None:
        continue
    if o.type == "MESH":
        F["acc " + n] = stat(tris_of([n]).reshape(-1, 3))
    else:
        F["acc " + n] = [r1(v * 1000) for v in (wr.matrix_world.inverted() @ o.matrix_world).translation]
# планки снизу: где низ планки цевья
F["clip_points_old"] = {k: [r1(v * 1000) for v in p] for k, p in json.loads(root["clip_points"]).items()}

# магазины старые (30 / 45 / 60) против новой коробки: насколько верх магазина входит в новую коробку
NB = NT["body"].reshape(-1, 3)
bvh_new_body = BVHTree.FromPolygons([tuple(p) for p in NB], [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(NT["body"]))])
OB = OT["body"].reshape(-1, 3)
bvh_old_body = BVHTree.FromPolygons([tuple(p) for p in OB], [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(OT["body"]))])


def signed(bvh, p):
    co, nrm, _i, dist = bvh.find_nearest(Vector(p))
    if co is None:
        return None
    return dist if (Vector(p) - co).dot(nrm) >= 0 else -dist


def mag_vs(names, bvh):
    T = tris_of(names)
    A = T.reshape(-1, 3)
    A = A[A[:, 2] > -60]
    ds = [signed(bvh, p) for p in A[::max(1, len(A) // 4000)]]
    ds = np.array([d for d in ds if d is not None])
    return dict(n=int(len(ds)), min=r1(ds.min()) if len(ds) else None, inside_1mm=int((ds < -1).sum()), inside_3mm=int((ds < -3).sum()))


for key, coll_name in (("30", "Магазин 30 (штатный)"), ("45", "Магазин 45"), ("60", "Барабан 60")):
    CT.show_variant("", key)
    update()
    names = [o.name for o in bpy.data.collections[coll_name].objects if o.type == "MESH" and "loaded" not in o.name]
    F[f"old_mag{key}_in_new_receiver"] = mag_vs(names, bvh_new_body)
    F[f"old_mag{key}_in_old_receiver"] = mag_vs(names, bvh_old_body)
CT.show_variant()
update()
F["new_mag_in_new_receiver"] = mag_vs(["Magazine__Mag"], bvh_new_body)
F["new_mag_in_old_receiver"] = mag_vs(["Magazine__Mag"], bvh_old_body)
log("места сняты")

# ---------------------------------------------------------------- касания перчатки в позах
gi = {g.index: g.name for g in glove.vertex_groups}
REGION = {}
for v in glove.data.vertices:
    if not v.groups:
        continue
    g = gi[max(v.groups, key=lambda g: g.weight).group]
    side = g.rsplit(".", 1)[-1]
    head = g.split(".")[0]
    reg = {"thumb": "большой", "f_index": "указательный", "f_middle": "средний", "f_ring": "безымянный", "f_pinky": "мизинец",
           "palm": "ладонь", "hand": "ладонь"}.get(head)
    if reg and side in ("L", "R"):
        REGION[v.index] = f"{side} {reg}"
reg_names = sorted(set(REGION.values()))
reg_idx = {r: np.array([i for i, x in REGION.items() if x == r]) for r in reg_names}

LIGHT = [o.name for o in bpy.data.collections["Фонарь ДОЗОР (левая планка)"].objects if o.type == "MESH"]
POSE_SHOW = dict(varn_v1=["Foregrip • varn_v1"], varn_v2=["Foregrip • varn_v2"], light=LIGHT, supp=["Глушитель • supp_veras"])
OLD_ALL = sum(OLD_PARTS.values(), [])
NEW_ALL = sum(NEW_PARTS.values(), [])
poses_act = bpy.data.actions[CT.POSES]


def bvh_of(T):
    A = T.reshape(-1, 3)
    return BVHTree.FromPolygons([tuple(p) for p in A], [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(T))])


def glove_local():
    dg = bpy.context.evaluated_depsgraph_get()
    e = glove.evaluated_get(dg)
    me = e.to_mesh()
    M = wr.matrix_world.inverted() @ e.matrix_world
    co = np.array([tuple(M @ v.co) for v in me.vertices]) * 1000.0
    e.to_mesh_clear()
    return co


contacts = {}
for pose, f in CT.POSE_FRAMES.items():
    rest()
    for ob in (arms, wr):
        ad = ob.animation_data or ob.animation_data_create()
        ad.action = poses_act
        ad.action_slot = CT.slot_of(poses_act, ob)
    v = CT.POSE_VARIANT.get(pose, {})
    CT.show_variant(v.get("grip", ""), v.get("mag", "30"), bool(v.get("light")))
    S.frame_set(f)
    update()
    extra = POSE_SHOW.get(pose, [])
    mag_old = OLD_PARTS["mag"]
    if pose == "mag45":
        mag_old = [o.name for o in bpy.data.collections["Магазин 45"].objects if o.type == "MESH" and "loaded" not in o.name]
    if pose == "drum60":
        mag_old = [o.name for o in bpy.data.collections["Барабан 60"].objects if o.type == "MESH" and "loaded" not in o.name]
    old_names = [n for n in OLD_ALL if n not in OLD_PARTS["mag"]] + mag_old + extra
    new_names = [n for n in NEW_ALL if not (pose in ("mag45", "drum60") and n == "Magazine__Mag")]
    if pose == "supp":                              # глушитель старый на обеих: меряется рука на автомате, не глушитель
        new_names = [n for n in new_names if n != "MuzzleDevice__Front"] + ["Глушитель • supp_veras"]
        old_names = [n for n in old_names if n != "MuzzleDevice_Steel"]
    if pose in ("mag45", "drum60"):                 # новых 45 / 60 нет — старые и на новой
        new_names += mag_old
    bo = bvh_of(tris_of(old_names))
    bn = bvh_of(tris_of(new_names))
    G = glove_local()
    rec = {}
    for r in reg_names:
        idx = reg_idx[r]
        P = G[idx]
        # только вершины у автомата (ближе 25 мм к старой или новой сетке)
        do, dn = [], []
        for p in P:
            a, b = signed(bo, p), signed(bn, p)
            if a is None or b is None:
                continue
            if min(abs(a), abs(b)) < 25:
                do.append(a)
                dn.append(b)
        do, dn = np.array(do), np.array(dn)
        if not len(do):
            continue
        touch = np.abs(do) <= 3.0
        e = dict(near=int(len(do)), touch_old=int(touch.sum()), old_min=r1(do.min()),
                 old_inside_2mm=int((do < -2).sum()), old_inside_5mm=int((do < -5).sum()),
                 new_min=r1(dn.min()), new_inside_2mm=int((dn < -2).sum()), new_inside_5mm=int((dn < -5).sum()),
                 touch_new=int((np.abs(dn) <= 3).sum()))
        if touch.sum():
            t = dn[touch]
            e.update(at_touch_new_median=r1(np.median(t)), at_touch_new_min=r1(t.min()), at_touch_new_max=r1(t.max()),
                     at_touch_inside=int((t < -1).sum()), at_touch_gap=int((t > 3).sum()))
        rec[r] = e
    contacts[pose] = rec
    log("касания", pose, {r: (e["touch_old"], e.get("at_touch_new_median"), e["new_min"]) for r, e in rec.items()})

Path(OUT).write_text(json.dumps(dict(features=F, contacts=contacts), ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
log("готово", OUT)
