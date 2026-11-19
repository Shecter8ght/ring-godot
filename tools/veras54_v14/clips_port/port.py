"""ВЕРАС-54: перенос клипов рук владельца со старой игровой сетки (v13) на новую (v14) — файл ВЕРАС-54_руки_клипы_v02.blend.

Вход — КОПИЯ его ВЕРАС-54_руки_клипы_v01.blend (сам v01 не трогается); выход — v02.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <копия v01.blend> --factory-startup --python-exit-code 1
    --python tools/veras54_v14/clips_port/port.py -- <VERAS54_Game_LP.blend> <ВЕРАС-54_игровая_v14_02.blend> <выход v02.blend> <отчёт.json>

Что делает (по заданию briefs/clips_port.md, решения владельца 19.11):
 1. путь магазина в его клипах снимается ДО любых правок (как магазин шёл у шахты в каждом кадре);
 2. сетка v13 убирается, игровая v14 с картами «Игровая версия/Карты v14» садится на те же кости VERAS54_WeaponRig; кости
    переводчика, защёлки, кнопки крышки, шарнира приклада, дульного, гнезда глушителя, пружины и подавателя — под оси v14,
    добавлена кость затвора BoltHead (поворот −35°); приводы — под новые углы и ходы; имена костей и свойств прежние;
 3. позы: жёсткий сдвиг кистей (пальцы не трогаются) — правая на рукоятке и левая на цевье подгонкой ладони к новой сетке,
    большой на переводчике — по новой полочке, крюк — по новой рукоятке взведения, левая с магазином — подгонкой к
    корпусу нового магазина, ВАРН — вместе с нижней планкой; новый кадр 91 «большой на защёлке» (черновой);
 4. позы в клипы — тем же переносом, что кнопка панели (clip_tools_v14.remap);
 5. клипы: магазин качается вокруг переднего зацепа нового магазина; при вставке — «прислонение» (остановка 3 кадра,
    клип длиннее на 3 кадра) и «примыкание» до щелчка защёлки; при извлечении большой левой на лапке защёлки; в быстрой
    старый магазин улетает вперёд-вниз;
 6. версии (ВАРН, 45 / 60) собираются заново; клипы обвесов (глушитель, фонарь) не переносятся и помечены.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "clips"))
import clip_tools_v14 as CT  # noqa: E402
from vcommon import finger_to  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
LP, MAPS_BLEND, OUT, REPORT, GEN_PATH = args[0], args[1], args[2], args[3], args[4]
MAPS_DIR = Path(MAPS_BLEND).parent.parent / "Карты v14"
log = lambda *a: print("PORT", *a, flush=True)  # noqa: E731
S = bpy.context.scene
C = bpy.context
arms, wr = CT.rigs()
root = bpy.data.objects["VERAS54"]
magob = bpy.data.objects["Magazine"]
glove = bpy.data.objects["FPS_Arms"]
glove_mod = next(m for m in glove.modifiers if m.type == "ARMATURE")
REP = {}
I4 = Matrix.Identity(4)
NOT_PORTED = ("Suppressor_On", "Suppressor_Off", "Light_Button")
HOLD = 3                                               # «прислонение»: остановка, кадров при 30 к/с
OLD_PIVOT_MM = Vector(json.loads(root["clip_points"])["pivot"]) * 1000
PROPS0 = {"Bolt pull": 0.0, "Magazine latch press": 0.0, "Trigger pull": 0.0, "Fire mode": 1.0, "Selector from mode": 1.0,
          "Selector blend": 1.0, "Muzzle attachment": 0.0, "Magazine removed": 0.0, "Stock fold": 0.0,
          "Cover button press": 0.0, "Cover lift": 0.0}


def update():
    C.view_layer.update()


def unassign():
    for ob in (arms, wr, root, magob):
        if ob.animation_data:
            ob.animation_data.action = None


def assign(act):
    for ob in (arms, wr, root, magob):
        ad = ob.animation_data or ob.animation_data_create()
        slot = CT.slot_of(act, ob)
        if slot is None:
            ad.action = None
            continue
        ad.action = act
        ad.action_slot = slot
        ad.action_extrapolation = "HOLD"


def rest():
    unassign()
    for pb in wr.pose.bones:
        pb.matrix_basis = I4.copy()
    for c in (pb.constraints.get("В левой кисти") for pb in wr.pose.bones):
        if c:
            c.influence = 0.0
    for k, v in PROPS0.items():
        root[k] = v
    root.update_tag()
    magob["Rounds remaining"] = 30
    update()


def mm(v):
    return [round(float(x), 2) for x in v]


def wr_mm(world_pts):
    W = wr.matrix_world.inverted()
    return np.array([tuple(W @ p) for p in world_pts]) * 1000.0


def tris_wr(objs):
    """Треугольники объектов в осях рига оружия (мм) → (N,3,3)."""
    dg = C.evaluated_depsgraph_get()
    W = wr.matrix_world.inverted()
    out = []
    for o in objs:
        e = o.evaluated_get(dg)
        me = e.to_mesh()
        me.calc_loop_triangles()
        M = W @ e.matrix_world
        co = np.array([tuple(M @ v.co) for v in me.vertices]) * 1000.0
        tri = np.array([lt.vertices[:] for lt in me.loop_triangles], dtype=np.int64)
        e.to_mesh_clear()
        if len(tri):
            out.append(co[tri])
    return np.concatenate(out)


def bvh(T):
    A = T.reshape(-1, 3)
    return BVHTree.FromPolygons([tuple(p) for p in A], [(3 * i, 3 * i + 1, 3 * i + 2) for i in range(len(T))])


def signed(b, p):
    co, n, _i, d = b.find_nearest(Vector(p))
    if co is None:
        return 99.0
    return d if (Vector(p) - co).dot(n) >= 0 else -d


# ================================================================ 1. путь магазина в клипах владельца (до правок)
glove_mod.show_viewport = False
REST_MAG = wr.data.bones["Magazine_Control"].matrix_local.copy()
REST_SPARE = wr.data.bones["SpareMag"].matrix_local.copy()
base_clips = [a for a in CT.clip_actions() if not CT.is_version(a)]
# путь — с клипов генератора (record_gen.py): в v01 повёрнутые ключи кисти у шахты после правки позы 41 не сдвинулись
ORIG = {}
for nm, r in json.loads(Path(GEN_PATH).read_text(encoding="utf-8")).items():
    if nm in NOT_PORTED:
        continue
    ORIG[nm] = dict(end=r["end"], E={int(f): Matrix(m) for f, m in r["E"].items()},
                    infl={int(f): v for f, v in r["infl"].items()})
log("путь магазина снят с клипов:", sorted(ORIG))
unassign()

# ================================================================ 2. старая сетка: что нужно для подгонки (до замены)
rest()
OLD_BODY_T = tris_wr([bpy.data.objects[n] for n in ("Body_Polymer", "Body_Steel", "DustCover_Steel")])
OLD_MAG_T = tris_wr([bpy.data.objects[n] for n in ("Magazine_Body", "Magazine_Steel")])
dg = C.evaluated_depsgraph_get()


def obj_pts(o):
    e = o.evaluated_get(dg)
    me = e.to_mesh()
    P = wr_mm([e.matrix_world @ v.co for v in me.vertices])
    e.to_mesh_clear()
    return P


OLD_SEL = obj_pts(bpy.data.objects["Selector_Steel"])
OLD_HANDLE = obj_pts(bpy.data.objects["Bolt_Steel"])
OLD_HANDLE = OLD_HANDLE[OLD_HANDLE[:, 1] < -24]
OLD_MAGP = OLD_MAG_T.reshape(-1, 3)
ol = OLD_MAGP[OLD_MAGP[:, 2] > -40]
OLD_LUG = ol[ol[:, 0].argmax()]
old_bvh_body, old_bvh_mag = bvh(OLD_BODY_T), bvh(OLD_MAG_T)

# ================================================================ 3. кости рига под оси v14, новая сетка
BONE_HEADS = {"Selector": (60.0, -17.7, -8.5), "MagazineLatch": (136.5, 0.0, -57.5), "CoverButton": (34.5, 0.0, 38.2),
              "StockFold": (5.8, 18.8, -18.5), "MuzzleAttachment": (587.4, 0.0, 0.0), "Socket_Muzzle": (587.4, 0.0, 0.0),
              "RecoilSpring": (17.3, 0.0, 15.5), "MagazineFollower": (212.156, 0.105, -153.165)}
old_heads = {n: mm(Vector(wr.data.bones[n].head_local) * 1000) for n in BONE_HEADS}
# старые сетки автомата и магазина 30 — прочь (обвесы, магазины 45 / 60, гильза задержки остаются)
gone = []
for cname in ("VERAS54 v13 • игровая сетка", "Магазин 30 (штатный)", "Старый магазин 30"):
    for o in list(bpy.data.collections[cname].objects):
        if o.type == "MESH":
            gone.append(o.name)
            bpy.data.objects.remove(o, do_unlink=True)
log("старых сеток убрано", len(gone))
for o in (wr, arms):
    o.hide_set(False)
    o.hide_viewport = False
C.view_layer.objects.active = wr
for o in C.view_layer.objects:
    o.select_set(o == wr)
bpy.ops.object.mode_set(mode="EDIT")
eb = wr.data.edit_bones
for n, h in BONE_HEADS.items():
    b = eb[n]
    d = (b.tail - b.head)
    b.head = Vector(h) / 1000.0
    b.tail = b.head + d
bh = eb.new("BoltHead")
bh.head = Vector((0.22135, 0.0, 0.0))
bh.tail = bh.head + Vector((0.0, 0.025, 0.0))
bh.roll = 0.0
bh.parent = eb["Bolt"]
bh.use_deform = False
bpy.ops.object.mode_set(mode="OBJECT")
wr.pose.bones["BoltHead"].rotation_mode = "XYZ"
rest()

# новая сетка: LOD0 (с патронами) из файла игровой сетки
with bpy.data.libraries.load(LP, link=False) as (src, dst):
    lp_names = [n for n in src.objects if not n.endswith("_LOD1")]
    dst.objects = list(lp_names)
NEW = {n: o for n, o in zip(lp_names, dst.objects) if o is not None}
coll_gun = bpy.data.collections.get("VERAS54 v13 • игровая сетка")
coll_gun.name = "VERAS54 v14 • игровая сетка"
coll_mag = bpy.data.collections["Магазин 30 (штатный)"]
for n, o in NEW.items():
    o.animation_data_clear()
    o.delta_location = (0, 0, 0)
    o.delta_rotation_euler = (0, 0, 0)
    o.delta_scale = (1, 1, 1)
    ((coll_mag if n.startswith(("Magazine", "Round_")) else coll_gun)).objects.link(o)
name_of = {o: n for n, o in NEW.items()}
local = {}
for o in NEW.values():
    m = I4.copy()
    q = o
    while q is not None:
        m = q.matrix_basis @ m if q.parent is None else (q.matrix_parent_inverse @ q.matrix_basis) @ m
        q = q.parent
    local[name_of[o]] = m
PARENT = {"Receiver": ("BONE", "WeaponRoot"), "Bolt_Carrier": ("BONE", "Bolt"), "Bolt": ("BONE", "BoltHead"),
          "Selector_Lever": ("BONE", "Selector"), "Trigger": ("BONE", "Trigger"), "Mag_Catch": ("BONE", "MagazineLatch"),
          "Cover_Button": ("BONE", "CoverButton"), "Stock_Knuckle": ("BONE", "StockFold"),
          "MuzzleDevice": ("BONE", "MuzzleAttachment"), "Recoil_Spring": ("BONE", "RecoilSpring"),
          "Magazine": ("OBJECT", "Magazine"), "Magazine_Follower": ("BONE", "MagazineFollower"),
          "Chamber_Round": ("BONE", "WeaponRoot")}
WRW = wr.matrix_world.copy()
for n, (kind, tgt) in PARENT.items():
    o = NEW[n]
    if kind == "BONE":
        o.parent, o.parent_type, o.parent_bone = wr, "BONE", tgt
    else:
        o.parent, o.parent_type = bpy.data.objects[tgt], "OBJECT"
    o.matrix_parent_inverse = I4.copy()
update()
for n in PARENT:
    NEW[n].matrix_world = WRW @ local[n]
update()
err = max(max(abs(a - b) for ra, rb in zip(WRW.inverted() @ o.matrix_world, local[name_of[o]]) for a, b in zip(ra, rb))
          for o in NEW.values())
log("новая сетка на костях: объектов", len(NEW), "расхождение с файлом сетки", f"{err:.1e}")
REP["mesh_place_err"] = err
# материалы с принятыми картами (файл игровой версии v14_02), пути — абсолютные к «Карты v14»
with bpy.data.libraries.load(MAPS_BLEND, link=False) as (src, dst):
    want = [n for n in src.materials if n.startswith("ВЕРАС-54 v14 • игра")]
    dst.materials = list(want)
newmat = {n: m for n, m in zip(want, dst.materials)}
for o in NEW.values():
    for s in getattr(o, "material_slots", ()):
        if s.material is not None:
            base = s.material.name.rsplit(".", 1)[0] if s.material.name[-4:-3] == "." else s.material.name
            if base in newmat:
                old = s.material
                s.material = newmat[base]
for m in list(bpy.data.materials):
    if m.users == 0:
        bpy.data.materials.remove(m)
for n, m in newmat.items():
    m.name = n
    for nd in m.node_tree.nodes:
        if nd.type == "TEX_IMAGE" and nd.image:
            nd.image.filepath = str(MAPS_DIR / Path(nd.image.filepath.replace("\\", "/")).name)
            nd.image.reload()
REP["maps"] = sorted({nd.image.filepath for m in newmat.values() for nd in m.node_tree.nodes if nd.type == "TEX_IMAGE" and nd.image})
# пустышка рукоятки затвора (по ней генератор брал ход) — к центру новой рукоятки
NEW_HANDLE = None
rest()
dg = C.evaluated_depsgraph_get()
nh = obj_pts(NEW["Bolt_Carrier__Body"])
NEW_HANDLE = nh[nh[:, 1] < -24]
ch = bpy.data.objects.get("ChargingHandle")
if ch is not None:
    ch.matrix_world = WRW @ Matrix.Translation(Vector(NEW_HANDLE.mean(0)) / 1000.0)
    for c in list(ch.users_collection):
        if c != coll_gun:
            pass
# патроны: видимость по счётчику (как было), подаватель по счётчику по укладке v14
for k in range(1, 31):
    o = NEW.get(f"Round_{k:02d}")
    for path in ("hide_viewport", "hide_render"):
        fc = o.driver_add(path)
        d = fc.driver
        d.type = "SCRIPTED"
        v = d.variables.new()
        v.name, v.type = "n", "SINGLE_PROP"
        v.targets[0].id_type = "OBJECT"
        v.targets[0].id = magob
        v.targets[0].data_path = '["Rounds remaining"]'
        d.expression = f"n<{k}"
slots = []
for k in range(1, 31):
    m = local[f"Round_{k:02d}"]
    slots.append((m.translation.x, m.translation.z, math.atan2(m[0][2], m[0][0])))
slots = np.array(slots)
ns = np.arange(0, 31)
tgt = []
for n_ in ns:
    if n_ == 0:
        s = slots[0] + (slots[0] - slots[1])
    else:
        s = slots[n_ - 1]
    tgt.append(s - slots[29])
tgt = np.array(tgt)
polys = [np.polyfit(ns, tgt[:, i], 3) for i in range(3)]


def poly_expr(c):
    a, b, c2, d0 = (float(x) for x in c)
    return f"({a:.6e})*m*m*m+({b:.6e})*m*m+({c2:.6e})*m+({d0:.6e})"


m_expr = "min(max(n,0),30)"
for dp, idx, pi in (('pose.bones["MagazineFollower"].location', 0, 0), ('pose.bones["MagazineFollower"].location', 2, 1),
                    ('pose.bones["MagazineFollower"].rotation_euler', 1, 2)):
    fc = next(f for f in wr.animation_data.drivers if f.data_path == dp and f.array_index == idx)
    e = poly_expr(polys[pi]).replace("m", f"({m_expr})")
    fc.driver.expression = e
REP["follower_fit_mm"] = round(float(max(abs(np.polyval(polys[i], ns) - tgt[:, i]).max() for i in (0, 1)) * 1000), 2)


# приводы под v14
def drv(dp, idx):
    return next((f for f in wr.animation_data.drivers if f.data_path == dp and f.array_index == idx), None)


ANG = dict(safe=-0.157081, auto=0.0, semi=0.127408, burst=0.061975)      # предохранитель / АВ / ОД / «2», рад (рычаг v14)
sel = drv('pose.bones["Selector"].rotation_euler', 1)
ang = lambda v: (f"({ANG['safe']} if {v}<.5 else ({ANG['auto']} if {v}<1.5 else "      # noqa: E731
                 f"({ANG['semi']} if {v}<2.5 else {ANG['burst']})))")
sel.driver.expression = f"{ang('previous')}*(1-(min(max(blend,0),1)))+{ang('mode')}*(min(max(blend,0),1))"
drv('pose.bones["MagazineLatch"].rotation_euler', 1).driver.expression = "-.226893*min(max(v,0),1)"
TRAVEL = "min(min(max(pull,0),1)*0.100600,0.072900 if mode<0.5 else 0.100600)"
drv('pose.bones["RecoilSpring"].scale', 0).driver.expression = f"max(0.25,1-0.60822*{TRAVEL}/0.1006)"
old_cb = drv('pose.bones["CoverButton"].location', 0)
if old_cb is not None:
    wr.driver_remove('pose.bones["CoverButton"].location', 0)


def add_driver(dp, idx, expr, varmap):
    fc = wr.driver_add(dp, idx)
    d = fc.driver
    d.type = "SCRIPTED"
    for vn, prop in varmap.items():
        v = d.variables.new()
        v.name, v.type = vn, "SINGLE_PROP"
        v.targets[0].id_type = "OBJECT"
        v.targets[0].id = root
        v.targets[0].data_path = f'["{prop}"]'
    d.expression = expr


add_driver('pose.bones["CoverButton"].location', 2, "-.0012*min(max(v,0),1)", {"v": "Cover button press"})
add_driver('pose.bones["BoltHead"].location', 0, f"min({TRAVEL},0.008)", {"pull": "Bolt pull", "mode": "Fire mode"})
add_driver('pose.bones["BoltHead"].rotation_euler', 0, f"-0.610865*min(max(({TRAVEL}*1000-2.5)/5.5,0),1)",
           {"pull": "Bolt pull", "mode": "Fire mode"})
root["Geometry version"] = "v14 игровая (VERAS54_Game_LP, карты «Игровая версия/Карты v14»), риг v13 с осями v14"
root["fire_modes"] = "Fire mode: 0 — предохранитель (−9°), 1 — АВ (0°), 2 — ОД (+7,3°), 3 — «2» (+3,55°); рычаг v14"
rest()
update()

# старый магазин быстрой перезарядки — копии нового (корпус, подаватель, два верхних патрона)
spare_coll = bpy.data.collections["Старый магазин 30"]
wr.pose.bones["SpareMag"].scale = (1, 1, 1)
update()
for n, bone in (("Magazine__Mag", "SpareMag"), ("Magazine_Follower__Mag", "SpareMag"), ("Round_01", "SpareMag_Rounds"),
                ("Round_02", "SpareMag_Rounds")):
    src = NEW[n]
    w = src.matrix_world.copy()
    cp = src.copy()
    cp.animation_data_clear()
    cp.name = "Старый 30 • " + n
    cp["variant"] = "mag:30"
    spare_coll.objects.link(cp)
    cp.parent, cp.parent_type, cp.parent_bone = wr, "BONE", bone
    cp.matrix_parent_inverse = I4.copy()
    update()
    cp.matrix_world = w
rest()

# ================================================================ 4. подгонка кистей к новой сетке (жёстко, пальцы не трогаются)
dg = C.evaluated_depsgraph_get()
NEW_BODY_T = tris_wr([NEW[n] for n in ("Receiver__Body", "Receiver__Front", "Dust_Cover__Body")])
NEW_MAG_T = tris_wr([NEW["Magazine__Mag"]])
new_bvh_body, new_bvh_mag = bvh(NEW_BODY_T), bvh(NEW_MAG_T)
NEW_SEL = obj_pts(NEW["Selector_Lever__Body"])
NM = NEW_MAG_T.reshape(-1, 3)
nl = NM[(NM[:, 2] > -40) & (NM[:, 2] < -15)]
NEW_LUG = nl[nl[:, 0].argmax()]
NEW_PIVOT_MM = Vector((NEW_LUG[0], 0.0, NEW_LUG[2])) + (OLD_PIVOT_MM - Vector((OLD_LUG[0], 0.0, OLD_LUG[2])))
NEW_PIVOT_MM.y = 0.0
REP["pivot_mm"] = dict(old=mm(OLD_PIVOT_MM), old_lug=mm(OLD_LUG), new_lug=mm(NEW_LUG), new=mm(NEW_PIVOT_MM))
root["clip_points_v14"] = json.dumps({"pivot": list(NEW_PIVOT_MM / 1000.0)})
log("ось качка магазина, мм: старая", mm(OLD_PIVOT_MM), "новая", mm(NEW_PIVOT_MM))

gi = {g.index: g.name for g in glove.vertex_groups}
MAIN = {}
for v in glove.data.vertices:
    if v.groups:
        MAIN[v.index] = gi[max(v.groups, key=lambda g: g.weight).group]
poses_act = bpy.data.actions[CT.POSES]


def pose_glove(frame):
    """Перчатка (мм, оси рига оружия) на кадре позы."""
    glove_mod.show_viewport = True
    assign(poses_act)
    S.frame_set(frame)
    update()
    d = C.evaluated_depsgraph_get()
    e = glove.evaluated_get(d)
    me = e.to_mesh()
    P = wr_mm([e.matrix_world @ v.co for v in me.vertices])
    e.to_mesh_clear()
    glove_mod.show_viewport = False
    return P


def pick(P, bones_pred, bvh_old):
    idx = [i for i, b in MAIN.items() if bones_pred(b)]
    out = []
    for i in idx:
        if abs(signed(bvh_old, P[i])) <= 3.0:
            out.append(P[i])
    return np.array(out)


def fit(P, b_new, axes=(0, 1, 2), lim=14.0):
    """Сдвиг (мм) точек касания, при котором они ложатся на новую поверхность: d² (внутрь — ×4), спуск по осям."""
    def cost(t):
        d = np.array([signed(b_new, p + t) for p in P])
        return float(np.mean(np.where(d < 0, 4 * d * d, d * d)))
    t = np.zeros(3)
    c0 = cost(t)
    best = c0
    for step in (2.0, 1.0, 0.5, 0.25):
        moved = True
        while moved:
            moved = False
            for ax in axes:
                for sg in (1, -1):
                    tt = t.copy()
                    tt[ax] += sg * step
                    if abs(tt[ax]) > lim:
                        continue
                    c = cost(tt)
                    if c < best - 1e-6:
                        best, t, moved = c, tt, True
    return t, math.sqrt(c0), math.sqrt(best)


R_PALM = lambda b: b.endswith(".R") and (b.startswith(("palm", "hand")) or b == "thumb.01.R")  # noqa: E731
L_ALL = lambda b: b.endswith(".L") and b.split(".")[0] in ("palm", "hand", "thumb", "f_index", "f_middle", "f_ring", "f_pinky")  # noqa: E731
SHIFT = {}
P1 = pose_glove(1)
pts = pick(P1, R_PALM, old_bvh_body)
t, c0, c1 = fit(pts, new_bvh_body)
SHIFT[("grip", "R")] = t
REP.setdefault("fits", {})["правая на рукоятке (кадр 1)"] = dict(points=len(pts), shift_mm=mm(t), rms_before=round(c0, 2), rms_after=round(c1, 2))
pts = pick(P1, L_ALL, old_bvh_body)
t, c0, c1 = fit(pts, new_bvh_body, axes=(1, 2))        # вдоль цевья не сдвигать: подгонка там скользит по призме
SHIFT[("grip", "L")] = t
REP["fits"]["левая на цевье (кадр 1)"] = dict(points=len(pts), shift_mm=mm(t), rms_before=round(c0, 2), rms_after=round(c1, 2))
for pose in ("mag", "check"):
    P = pose_glove(CT.POSE_FRAMES[pose])
    pts = pick(P, L_ALL, old_bvh_mag)
    t, c0, c1 = fit(pts, new_bvh_mag)
    SHIFT[(pose, "L")] = t
    REP["fits"][f"левая с магазином (кадр {CT.POSE_FRAMES[pose]})"] = dict(points=len(pts), shift_mm=mm(t),
                                                                          rms_before=round(c0, 2), rms_after=round(c1, 2))
SHIFT[("pre", "L")] = SHIFT[("mag", "L")]


def rot_y(P, piv, deg):
    a = math.radians(deg)
    x, z = P[:, 0] - piv[0], P[:, 2] - piv[1]
    Q = P.copy()
    Q[:, 0] = piv[0] + x * math.cos(a) + z * math.sin(a)
    Q[:, 2] = piv[1] - x * math.sin(a) + z * math.cos(a)
    return Q


def shelf(P, lo, hi, down):
    sh = P[(P[:, 0] >= lo) & (P[:, 0] <= hi)]
    c = sh.mean(0)
    c[2] = sh[:, 2].max() + 7 if down else sh[:, 2].min() - 7
    c[1] -= 6
    return c


old_end, new_end = OLD_SEL[:, 0].max(), NEW_SEL[:, 0].max()
for pose, deg_old, deg_new, down in (("sel_down", 0.0, 0.0, True), ("sel_up", 7.85, 7.30, False)):
    co = shelf(rot_y(OLD_SEL, (60.0, -8.0), deg_old), 134, 152, down)
    cn = shelf(rot_y(NEW_SEL, (60.0, -8.5), deg_new), 134 + new_end - old_end, 152 + new_end - old_end, down)
    SHIFT[(pose, "R")] = cn - co
    REP["fits"][f"большой на переводчике ({pose})"] = dict(shift_mm=mm(cn - co), shelf_old=mm(co), shelf_new=mm(cn))
hd = NEW_HANDLE.mean(0) - OLD_HANDLE.mean(0)
SHIFT[("hook", "R")] = hd
SHIFT[("hook_pre", "R")] = hd
REP["fits"]["крюк на рукоятке взведения (31, 36)"] = dict(shift_mm=mm(hd))
RAIL_DZ = 5.2                                          # нижняя планка цевья v14 выше на 5,2 мм (разведка)
for pose in ("varn_v1", "varn_v2"):
    SHIFT[(pose, "L")] = np.array((0.0, 0.0, RAIL_DZ))
for n in ("Foregrip • varn_v1", "Foregrip • varn_v2"):
    o = bpy.data.objects[n]
    # в осях кости WeaponRoot (= оси рига оружия): matrix_world у скрытой коллекции не посчитана
    PI = o.matrix_parent_inverse
    o.matrix_basis = PI.inverted() @ Matrix.Translation((0, 0, RAIL_DZ / 1000.0)) @ PI @ o.matrix_basis
log("сдвиги кистей, мм:", {f"{k[0]}.{k[1]}": mm(v) for k, v in SHIFT.items()})

# ================================================================ 5. позы: сдвиги и новый кадр 91
bag_p = CT.bag_of(poses_act, arms)
cv_p = CT.bone_curves(bag_p)
assign(poses_act)
for (pose, side), t in SHIFT.items():
    f = CT.POSE_FRAMES[pose]
    S.frame_set(f)
    update()
    pb = arms.pose.bones[f"ik_hand.{side}"]
    M = pb.matrix.copy()
    M.translation += wr.matrix_world.to_3x3() @ (Vector(t) / 1000.0)
    pb.matrix = M
    basis = pb.matrix_basis.copy()
    CT.write(cv_p.setdefault(pb.name, {}), pb, f, basis, bag_p, insert=True)
REP["pose_shifts_mm"] = {f"{CT.POSE_FRAMES[p]} {CT.POSE_RU[p]} — {'правая' if s == 'R' else 'левая'}": mm(t)
                         for (p, s), t in SHIFT.items()}
# кадр 91: копия «на магазине» (все кривые поз), большой — на лапку защёлки
F91, F41 = CT.POSE_FRAMES["mag_latch"], CT.POSE_FRAMES["mag"]
for ob in (arms, wr):
    bag = CT.bag_of(poses_act, ob)
    for fc in bag.fcurves:
        v = fc.evaluate(F41)
        kp = fc.keyframe_points.insert(F91, v)
        kp.interpolation = "CONSTANT"
        fc.update()
cv_p = CT.bone_curves(bag_p)
T41 = CT.pose_table(poses_act, arms)["mag_latch"]
unassign()
for pb in wr.pose.bones:
    pb.matrix_basis = I4.copy()
for n_ in ("SpareMag", "JamCase", "Suppressor_Control"):
    wr.pose.bones[n_].scale = (0.001,) * 3
for pb in arms.pose.bones:
    pb.matrix_basis = T41[pb.name]
update()
dg = C.evaluated_depsgraph_get()
catch = obj_pts(NEW["Mag_Catch__Body"])
lowp = catch[catch[:, 2] < catch[:, 2].min() + 12]
press_pt = Vector((lowp[:, 0].min() - 2.0, 0.0, lowp[:, 2].mean())) / 1000.0
glove_mod.show_viewport = True
miss = finger_to(arms, glove, "L", "thumb", wr.matrix_world @ press_pt)
glove_mod.show_viewport = False
for n in [b.name for b in arms.pose.bones if b.name.startswith("thumb") and b.name.endswith(".L")]:
    CT.write(cv_p.setdefault(n, {}), arms.pose.bones[n], F91, arms.pose.bones[n].matrix_basis.copy(), bag_p, insert=True)
REP["latch_thumb"] = dict(target_mm=mm(press_pt * 1000), miss_mm=round(miss, 1))
log("большой левой на защёлке: промах, мм", round(miss, 1))
S.timeline_markers.new(f"ПОЗА {CT.POSE_RU['mag_latch']}", frame=F91)

# ================================================================ 6. позы → клипы (как кнопка панели)
applied = bpy.data.actions[CT.APPLIED]
OLD = CT.pose_table(applied, arms)
NEWT = CT.tidy_poses(C, arms, wr, poses_act, log)
OLD["mag_latch"] = {n: m.copy() for n, m in NEWT["mag_latch"].items()}
for act in base_clips:
    nm = act.name[len(CT.PREFIX):]
    if nm in NOT_PORTED:
        act[CT.NOT_PORTED] = True
        act["group"] = "Не перенесено на v14 (обвесы)"
        continue
    n = CT.remap(act, arms, OLD, NEWT)
    REP.setdefault("remap_keys", {})[nm] = n
bpy.data.actions.remove(applied)
snap = poses_act.copy()
snap.name = CT.APPLIED
snap.use_fake_user = True
log("позы перенесены в клипы", REP["remap_keys"])

# ================================================================ 7. клипы: путь магазина, прислонение, защёлка, вылет
P_OLD = OLD_PIVOT_MM / 1000.0
P_NEW = NEW_PIVOT_MM / 1000.0


def decompose(E, P):
    """E (оси рига) → (поворот 3×3, сдвиг t): E = T(t) · поворот вокруг P."""
    R = E.to_3x3()
    t = E @ P - P
    return R, t


def about_p(R, P, t):
    return Matrix.Translation(t) @ Matrix.Translation(P) @ R.to_4x4() @ Matrix.Translation(-P)


def remap_E(E):
    R, t = decompose(E, P_OLD)
    return about_p(R, P_NEW, t)


def ang_of(E):
    return math.degrees(E.to_quaternion().angle) if E.to_quaternion().angle < math.pi else 360 - math.degrees(E.to_quaternion().angle)


def at_well(E):
    R, t = decompose(E, P_OLD)
    return t.length < 0.060 and ang_of(E) <= 40


def all_curves(act):
    out = []
    for layer in act.layers:
        for st in layer.strips:
            for bag in st.channelbags:
                out.extend(bag.fcurves)
    return out


def insert_hold(act, fc_frame, H):
    for fc in all_curves(act):
        kps = fc.keyframe_points
        if not len(kps):
            continue
        v = fc.evaluate(fc_frame)
        interp = None
        for kp in sorted(kps, key=lambda k: -k.co[0]):
            if kp.co[0] > fc_frame + 1e-3:
                kp.co[0] += H
                kp.handle_left[0] += H
                kp.handle_right[0] += H
        prev = [k for k in kps if k.co[0] <= fc_frame + 1e-3]
        interp = prev[-1].interpolation if prev else kps[0].interpolation
        if not any(abs(k.co[0] - fc_frame) < 1e-3 for k in kps):
            kps.insert(fc_frame, v).interpolation = interp
        kps.insert(fc_frame + H, v).interpolation = interp
        fc.update()
    marks = json.loads(act.get("marks", "{}"))
    act["marks"] = json.dumps({k: (v + H if v > fc_frame else v) for k, v in marks.items()}, ensure_ascii=False)


def key_frames(act, ob, path_part):
    out = set()
    bag = CT.bag_of(act, ob)
    for fc in (bag.fcurves if bag else ()):
        if path_part in fc.data_path:
            out |= {round(k.co[0], 3) for k in fc.keyframe_points}
    return sorted(out)


def prop_curve(act, prop):
    bag = CT.bag_of(act, root)
    return next((fc for fc in (bag.fcurves if bag else ()) if fc.data_path == f'["{prop}"]'), None)


L_THUMB = [b.name for b in arms.pose.bones if b.name.startswith("thumb") and b.name.endswith(".L")]


def reach_left(act, end, tol=2.0):
    """Левая не дотягивается до цели (кисть с магазином встала по новому пути) — плечо подаётся ключами, как у генератора."""
    ua = arms.pose.bones["upper_arm.L"]
    moved = 0
    for _ in range(3):
        gaps = {}
        for f in range(1, end + 1):
            S.frame_set(f)
            gaps[f] = (arms.pose.bones["ik_hand.L"].head - arms.pose.bones["hand.L"].head).length * 1000
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
            for edge in (r[0] - 2, r[-1] + 2):
                if 1 <= edge <= end and edge not in bad:
                    S.frame_set(edge)
                    plan.append((edge, ua.matrix_basis.copy()))
            for f in sorted(set(r[::3]) | {r[-1], max(r, key=lambda x: gaps[x])}):
                S.frame_set(f)
                for _i in range(8):
                    d = arms.pose.bones["ik_hand.L"].head - arms.pose.bones["hand.L"].head
                    if d.length < 0.0004:
                        break
                    ua.matrix = Matrix.Translation(d * 1.05) @ ua.matrix
                    update()
                plan.append((f, ua.matrix_basis.copy()))
        cv = CT.bone_curves(CT.bag_of(act, arms))
        for f, mb in plan:
            CT.write(cv.setdefault("upper_arm.L", {}), ua, f, mb, CT.bag_of(act, arms), insert=True)
        moved += len(plan)
    worst = 0.0
    for f in range(1, end + 1):
        S.frame_set(f)
        worst = max(worst, (arms.pose.bones["ik_hand.L"].head - arms.pose.bones["hand.L"].head).length * 1000)
    return moved, round(worst, 1)
CLIPS_REP = {}
for act in base_clips:
    nm = act.name[len(CT.PREFIX):]
    if nm not in ORIG:
        continue
    o = ORIG[nm]
    E0, infl0 = o["E"], o["infl"]
    rec = dict(length_before=o["end"], holds=[], latch_press=[], dev_mm=0.0, pivot_dev_mm=0.0)
    wrong = "Wrong" in nm
    if wrong:
        cvm = CT.bone_curves(CT.bag_of(act, arms)).get("mag.L", {})
        hid = int(json.loads(act.get("marks", "{}")).get("mag_hidden", 26)) - 1
        CT.write(cvm, arms.pose.bones["mag.L"], hid, NEWT["mag"]["mag.L"], CT.bag_of(act, arms), insert=True)
        qs = [cvm[("rotation_quaternion", i)] for i in range(4)]
        frames_q = sorted({round(k.co[0], 3) for fc in qs for k in fc.keyframe_points})
        prevq = None
        for fq in frames_q:
            kps = [next(k for k in fc.keyframe_points if abs(k.co[0] - fq) < 1e-3) for fc in qs]
            q = [k.co[1] for k in kps]
            if prevq is not None and sum(a * b for a, b in zip(q, prevq)) < 0:
                for k in kps:
                    d = -2 * k.co[1]
                    k.co[1] += d
                    k.handle_left[1] += d
                    k.handle_right[1] += d
                q = [-v for v in q]
            prevq = q
        for fc in qs:
            fc.update()
        rec["mag_in_hand_fixed"] = dict(key_normal_at=hid, quat_keys=len(frames_q))
    # --- вставки: кадр «прислонения» — зацеп у шахты (сдвиг < 0,7 мм), магазин ещё наклонён и дальше качается к 0
    contacts = []
    for f in range(2, o["end"] - 4):
        if infl0[f] < 0.5:
            continue
        R, t = decompose(E0[f], P_OLD)
        Rp, tp = decompose(E0[f - 1], P_OLD)
        if t.length < 0.0007 and ang_of(E0[f]) > 10 and (tp.length >= 0.0007 or ang_of(E0[f - 1]) <= 10) \
                and ang_of(E0[min(f + 4, o["end"])]) < ang_of(E0[f]) - 5:
            contacts.append(f)
    timeline = {}                                      # новый кадр → старый
    shift = 0
    for f in contacts:
        insert_hold(act, f + shift, HOLD)
        rec["holds"].append(f + shift)
        shift += HOLD
    end_new = o["end"] + shift
    s_ = 0
    holds_set = [(h, h + HOLD) for h in rec["holds"]]
    for g in range(1, end_new + 1):
        back = sum(HOLD for h, h2 in holds_set if g > h2) + sum(g - h for h, h2 in holds_set if h < g <= h2)
        timeline[g] = g - back
    # --- извлечение: большой левой на лапке защёлки, пока она нажата (магазин в шахте, в кисти)
    lc = prop_curve(act, "Magazine latch press")
    if lc is not None:
        pts = sorted((k.co[0], k.co[1]) for k in lc.keyframe_points)
        runs, cur = [], None
        for f, v in pts:
            if v > 0.95 and cur is None:
                cur = [f, f]
            elif v > 0.95:
                cur[1] = f
            elif cur is not None:
                runs.append(cur)
                cur = None
        cv_c = CT.bone_curves(CT.bag_of(act, arms))
        for a, b in runs:
            fo = timeline.get(int(round(a)), int(round(a)))
            if fo in E0 and infl0[fo] > 0.5 and ang_of(E0[fo]) < 1.0 and decompose(E0[fo], P_OLD)[1].length < 0.001:
                for fr, pose in ((a, "mag_latch"), (b, "mag_latch"), (b + 2, "mag")):
                    for n in L_THUMB:
                        CT.write(cv_c.setdefault(n, {}), arms.pose.bones[n], fr, NEWT[pose][n], CT.bag_of(act, arms), insert=True)
                rec["latch_press"].append([a, b])
    # --- магазин в кисти у шахты: качок вокруг нового зацепа; ключ кисти на каждом кадре
    assign(act)
    muted = []
    if wrong:
        for fc in CT.bag_of(act, arms).fcurves:
            if 'pose.bones["mag.L"]' in fc.data_path:
                fc.mute = True
                muted.append(fc)
        arms.pose.bones["mag.L"].matrix_basis = NEWT["mag"]["mag.L"]
    plan = []
    want = {}
    well = set()
    hand_keys = set(int(round(k)) for k in key_frames(act, arms, 'pose.bones["ik_hand.L"]'))
    for g in range(1, end_new + 1):
        fo = timeline[g]
        if infl0.get(fo, 0) < 0.5:
            continue
        if not at_well(E0[fo]) and g not in hand_keys:
            continue
        S.frame_set(g)
        Ed = remap_E(E0[fo])
        want[g] = Ed
        if at_well(E0[fo]):
            well.add(g)
        pbm = wr.pose.bones["Magazine_Control"]
        if pbm.constraints["В левой кисти"].influence < 0.5:
            continue
        Mc = pbm.matrix.copy()
        ik = arms.pose.bones["ik_hand.L"]
        W = wr.matrix_world
        Kn = W @ (Ed @ REST_MAG) @ Mc.inverted() @ W.inverted() @ ik.matrix
        ik.matrix = Kn
        plan.append((g, ik.matrix_basis.copy()))
    cv_c = CT.bone_curves(CT.bag_of(act, arms))
    for g, basis in plan:
        CT.write(cv_c["ik_hand.L"], arms.pose.bones["ik_hand.L"], g, basis, CT.bag_of(act, arms), insert=True)
    for fc in cv_c["ik_hand.L"].values():
        fc.update()
    # проверка пути: магазин против желаемого (мм), зацеп у оси качка на полукадрах
    dev, pdev = 0.0, 0.0
    for g in sorted(want):
        for sub in (0.0, 0.5):
            if sub and (g + 1 not in well or g not in well):
                continue
            S.frame_set(g, subframe=sub)
            E = wr.pose.bones["Magazine_Control"].matrix @ REST_MAG.inverted()
            if sub == 0.0:
                corners = [Vector(c) for c in ((0.15, 0, -0.03), (0.23, 0, -0.03), (0.2, 0, -0.2))]
                dd = max((E @ c - want[g] @ c).length for c in corners) * 1000
                dev = max(dev, dd) if g in well else dev
                rec["dev_all_mm"] = max(rec.get("dev_all_mm", 0.0), round(dd, 2))
            Rw, tw = decompose(want[g], P_NEW)
            if tw.length < 0.0005 and (sub == 0.0 or decompose(want[g + 1], P_NEW)[1].length < 0.0005):
                pdev = max(pdev, (E @ P_NEW - P_NEW).length * 1000)
    for fc in muted:                                    # «не той стороной»: замер — для магазина как в позе 41, потом ключи назад
        fc.mute = False
    rec["dev_mm"], rec["pivot_dev_mm"] = round(dev, 2), round(pdev, 2)
    rec["hand_frames"] = len(want)
    rec["shoulder_keys"], rec["reach_left_mm"] = reach_left(act, end_new)
    # --- быстрая: старый магазин (SpareMag) — качок у нового зацепа, потом вперёд-вниз из кадра
    marks = json.loads(act.get("marks", "{}"))
    if "old_falls" in marks:
        free = int(marks["old_falls"])
        bag_w = CT.bag_of(act, wr)
        cv_w = CT.bone_curves(bag_w)
        pbs = wr.pose.bones["SpareMag"]
        # ключи до вылета — на новый зацеп
        frames_sp = [f for f in key_frames(act, wr, 'pose.bones["SpareMag"].location') if f <= free]
        sp_plan = []
        for f in frames_sp:
            S.frame_set(int(f), subframe=f - int(f))
            Ed = remap_E(pbs.matrix @ REST_SPARE.inverted())      # ключи старого магазина ещё прежние
            pbs.matrix = Ed @ REST_SPARE
            sp_plan.append((f, pbs.matrix_basis.copy()))
        for f, basis in sp_plan:
            CT.write(cv_w["SpareMag"], pbs, f, basis, bag_w, insert=True)
        # падение: прежние ключи после вылета — прочь
        for fc in bag_w.fcurves:
            if fc.data_path.startswith('pose.bones["SpareMag"]') and not fc.data_path.startswith('pose.bones["SpareMag_'):
                for i in reversed(range(len(fc.keyframe_points))):
                    if fc.keyframe_points[i].co[0] > free + 1e-3:
                        fc.keyframe_points.remove(fc.keyframe_points[i], fast=True)
                fc.update()
        S.frame_set(free)
        M0 = wr.matrix_world @ pbs.matrix
        G0 = wr.matrix_world.to_3x3()
        v0 = G0 @ Vector((1.3, 0.0, -0.45))            # оси автомата: вперёд и вниз, м/с
        ax_spin = G0 @ Vector((0.0, 1.0, 0.0))         # вокруг поперечной оси — носом вниз
        ax_roll = G0 @ Vector((1.0, 0.0, 0.0))
        n_fall = 18
        fplan = []
        for f in range(free + 1, min(free + n_fall, end_new) + 1, 2):
            t = (f - free) / 30.0
            off = v0 * t + Vector((0, 0, -4.9 * t * t))
            Rm = (Matrix.Rotation(7.0 * t, 3, ax_spin) @ Matrix.Rotation(1.5 * t, 3, ax_roll)).to_4x4()
            M = Matrix.Translation(M0.translation + off) @ Rm @ M0.to_3x3().to_4x4()
            S.frame_set(f)
            pbs.matrix = (wr.matrix_world).inverted() @ M
            fplan.append((f, pbs.matrix_basis.copy()))
        for f, basis in fplan:
            CT.write(cv_w["SpareMag"], pbs, f, basis, bag_w, insert=True)
        for fc in bag_w.fcurves:
            if fc.data_path == 'pose.bones["SpareMag"].location' or fc.data_path == 'pose.bones["SpareMag"].rotation_euler':
                for kp in fc.keyframe_points:
                    if kp.co[0] > free:
                        kp.interpolation = "LINEAR"
                fc.update()
        hide_at = min(free + n_fall + 1, end_new)
        for i in range(3):
            fc = bag_w.fcurves.find('pose.bones["SpareMag"].scale', index=i)
            if fc is not None:
                fc.keyframe_points.insert(hide_at, 0.001).interpolation = "CONSTANT"
                fc.update()
        marks["mag_toss"] = free
        rec["mag_toss"] = dict(frame=free, hidden=hide_at, v0_mps=[1.3, 0.0, -0.45])
    # --- фазы: прислонение / примыкание / защёлка (старые имена не трогаются)
    for i, h in enumerate(rec["holds"]):
        sfx = "" if i == 0 else f"_{i + 1}"
        marks["lean" + sfx] = h
        marks["join" + sfx] = h + HOLD
    if lc is not None:
        clicks = sorted(k.co[0] for k in lc.keyframe_points if 0.5 < k.co[1] < 0.95)
        for i, c in enumerate(clicks):
            marks["latch_click" + ("" if i == 0 else f"_{i + 1}")] = int(round(c))
    for i, (a, b) in enumerate(rec["latch_press"]):
        marks["latch_press" + ("" if i == 0 else f"_{i + 1}")] = int(round(a))
    act["marks"] = json.dumps(marks, ensure_ascii=False)
    rec["length_after"] = int(math.ceil(CT.last_key(act, arms)))
    rec["marks"] = marks
    CLIPS_REP[nm] = rec
    log(nm, rec["length_before"], "→", rec["length_after"], "прислонение", rec["holds"], "защёлка", rec["latch_press"],
        "путь, мм", rec["dev_mm"], "зацеп, мм", rec["pivot_dev_mm"])
REP["clips"] = CLIPS_REP
unassign()

# ================================================================ 8. версии, панель, сохранение
nv = CT.build_versions(C, log)
REP["versions"] = nv
panel = bpy.data.texts.get(CT.PANEL_TEXT) or bpy.data.texts.new(CT.PANEL_TEXT)
panel.from_string((HERE / "clip_tools_v14.py").read_text(encoding="utf-8"))
panel.use_module = True
txt = bpy.data.texts.get("ВЕРАС-54 — позы и клипы (читать)")
if txt is not None:
    txt.from_string(
        "v02 — АВТОМАТ v14 (перенос 19.11). Сетка v13 заменена игровой v14, кисти сдвинуты жёстко (пальцы не подгонялись),\n"
        "магазин качается вокруг переднего зацепа нового магазина: «прислонение» (lean) — остановка 3 кадра, «примыкание»\n"
        "(join) — до щелчка защёлки (latch_click); при извлечении большой левой на защёлке (latch_press, поза 91 — черновая);\n"
        "в быстрой старый магазин улетает вперёд-вниз (mag_toss). Клипы обвесов (глушитель, фонарь) не перенесены.\n"
        "Сборки клипов заново из таблиц для v02 нет (regenerate.cmd не применять).\n\n" + txt.as_string())
S["veras_v14_port"] = "v02: автомат v14, перенос 19.11; клипы обвесов не перенесены"
glove_mod.show_viewport = True
rest()
CT.open_action(C, CT.POSES)
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=True)
Path(REPORT).write_text(json.dumps(REP, ensure_ascii=False, indent=1, default=str), encoding="utf-8", newline="\n")
log("сохранено", OUT)
