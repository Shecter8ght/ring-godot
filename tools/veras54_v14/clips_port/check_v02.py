"""ВЕРАС-54 v02 (автомат v14): проверки после переноса и кадры для своей проверки. Только чтение (файл не сохраняется).

blender -b <ВЕРАС-54_руки_клипы_v02.blend> --factory-startup --python tools/veras54_v14/clips_port/check_v02.py -- <отчёт.json> <папка кадров>
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clip_tools_v14 as CT  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
OUT, SHOTS = args[0], Path(args[1])
SHOTS.mkdir(parents=True, exist_ok=True)
log = lambda *a: print("CHK", *a, flush=True)  # noqa: E731
S = bpy.context.scene
C = bpy.context
arms, wr = CT.rigs()
root = bpy.data.objects["VERAS54"]
magob = bpy.data.objects["Magazine"]
glove = bpy.data.objects["FPS_Arms"]
REP = {}
I4 = Matrix.Identity(4)


def update():
    C.view_layer.update()


def assign(act):
    for ob in (arms, wr, root, magob):
        ad = ob.animation_data or ob.animation_data_create()
        sl = CT.slot_of(act, ob) if act else None
        ad.action = act if sl else None
        if sl:
            ad.action_slot = sl
            ad.action_extrapolation = "HOLD"


poses = bpy.data.actions[CT.POSES]
T = CT.pose_table(poses, arms)

# ---------------------------------------------------------------- 1. длины, начало и конец — хват
EXEMPT = ("Draw", "Holster", "Finger_On", "Finger_Off", "Mag_Eject", "Mag_Insert")  # извлечь / вставить: кончается / начинается с магазином в руке
clips = {}
for act in CT.clip_actions():
    nm = act.name[len(CT.PREFIX):]
    if act.get(CT.NOT_PORTED):
        clips[nm] = dict(not_ported=True)
        continue
    cv = CT.bone_curves(CT.bag_of(act, arms))
    end = int(math.ceil(CT.last_key(act, arms)))
    worst = {}
    for f in (1, end):
        w = (0.0, 0.0, "")
        for pb in arms.pose.bones:
            if pb.name in ("mag.L", "supp.L", "f_ring.01.L"):     # f_ring.01.L: сдвиг 22,6 мм поза ≠ клипы — так и в v01 и у генератора
                continue
            ang, d = CT.apart(CT.read(cv.get(pb.name, {}), pb, f), T["grip"][pb.name])
            ang = min(ang, 360 - ang)
            if ang + d * 1000 > w[0] + w[1]:
                w = (round(ang, 2), round(d * 1000, 2), pb.name)
        worst["start" if f == 1 else "end"] = w
    clips[nm] = dict(frames=end, marks=json.loads(act.get("marks", "{}")), grip_dev=worst,
                     grip_ok=nm in EXEMPT or max(worst["start"][0], worst["end"][0]) < 0.5 and max(worst["start"][1], worst["end"][1]) < 2.0)
REP["clips"] = clips
REP["versions"] = sum(1 for a in bpy.data.actions if CT.is_version(a))

# ---------------------------------------------------------------- 2. детали двигаются своими костями
assign(None)
for pb in wr.pose.bones:
    pb.matrix_basis = I4.copy()


def setp(**kw):
    base = {"Bolt pull": 0.0, "Magazine latch press": 0.0, "Trigger pull": 0.0, "Fire mode": 1.0, "Selector from mode": 1.0,
            "Selector blend": 1.0, "Cover button press": 0.0}
    base.update(kw)
    for k, v in base.items():
        root[k] = v
    root.update_tag()
    update()


def where(n):
    return wr.matrix_world.inverted() @ bpy.data.objects[n].matrix_world


parts = {}
setp()
c0, h0, s0, l0, b0 = (where(n) for n in ("Bolt_Carrier__Body", "Bolt__Body", "Selector_Lever__Body", "Mag_Catch__Body", "Cover_Button__Body"))
setp(**{"Bolt pull": 1.0})
c1, h1 = where("Bolt_Carrier__Body"), where("Bolt__Body")
parts["рама, ход мм"] = round((c1.translation - c0.translation).length * 1000, 2)
parts["затвор: поворот °, отставание мм"] = [round(math.degrees((h0.to_quaternion().rotation_difference(h1.to_quaternion())).angle), 2),
                                              round(((h1.translation - h0.translation) - (c1.translation - c0.translation)).length * 1000, 2)]
for mode, label in ((0.0, "предохранитель"), (3.0, "«2»"), (2.0, "ОД")):
    setp(**{"Fire mode": mode, "Selector from mode": mode})
    s1 = where("Selector_Lever__Body")
    q = s0.to_quaternion().rotation_difference(s1.to_quaternion())
    parts[f"переводчик {label}, ° от АВ"] = round(math.degrees(q.angle) * (1 if q.axis.y > 0 else -1), 2)
setp(**{"Magazine latch press": 1.0})
parts["защёлка нажата, °"] = round(math.degrees(l0.to_quaternion().rotation_difference(where("Mag_Catch__Body").to_quaternion()).angle), 2)
setp(**{"Cover button press": 1.0})
parts["кнопка крышки, мм"] = round((where("Cover_Button__Body").translation - b0.translation).length * 1000, 2)
setp()
for n_ in (30, 15, 0):
    magob["Rounds remaining"] = n_
    magob.update_tag()
    S.frame_set(1)
    update()
    vis = sum(1 for k in range(1, 31) if not bpy.data.objects[f"Round_{k:02d}"].hide_viewport)
    parts[f"патронов {n_}: видно"] = vis
magob["Rounds remaining"] = 30
update()
REP["parts"] = parts
log("детали", parts)

# ---------------------------------------------------------------- 3. руки на новой сетке по позам
gi = {g.index: g.name for g in glove.vertex_groups}
MAIN = {}
for v in glove.data.vertices:
    if v.groups:
        MAIN[v.index] = gi[max(v.groups, key=lambda g: g.weight).group]
REG = {}
for i, b in MAIN.items():
    side = b.rsplit(".", 1)[-1]
    head = b.split(".")[0]
    reg = {"thumb": "большой", "f_index": "указательный", "f_middle": "средний", "f_ring": "безымянный", "f_pinky": "мизинец",
           "palm": "ладонь", "hand": "ладонь"}.get(head)
    if reg and side in ("L", "R"):
        REG.setdefault(f"{side} {reg}", []).append(i)
TIPS = {f"{s} {r}": f"{b}.03.{s}" for s in ("L", "R") for r, b in (("большой", "thumb"), ("указательный", "f_index"),
                                                                    ("средний", "f_middle"), ("безымянный", "f_ring"),
                                                                    ("мизинец", "f_pinky"))}
TIPIDX = {k: [i for i, b in MAIN.items() if b == bn] for k, bn in TIPS.items()}
GUN = [o for o in bpy.data.collections["VERAS54 v14 • игровая сетка"].objects if o.type == "MESH"]
MAG = [o for o in bpy.data.collections["Магазин 30 (штатный)"].objects if o.type == "MESH" and not o.name.startswith("Round_")]


def tris(objs):
    dg = C.evaluated_depsgraph_get()
    W = wr.matrix_world.inverted()
    vs, fs, off = [], [], 0
    for o in objs:
        e = o.evaluated_get(dg)
        me = e.to_mesh()
        me.calc_loop_triangles()
        M = W @ e.matrix_world
        vs += [tuple(M @ v.co * 1000) for v in me.vertices]
        fs += [tuple(off + i for i in lt.vertices) for lt in me.loop_triangles]
        off += len(me.vertices)
        e.to_mesh_clear()
    return BVHTree.FromPolygons(vs, fs)


def signed(b, p):
    co, n, _i, d = b.find_nearest(Vector(p))
    if co is None:
        return 99.0
    return d if (Vector(p) - co).dot(n) >= 0 else -d


pose_rep = {}
for pose in ("grip", "frame", "pressed", "sel_down", "sel_up", "hook_pre", "hook", "mag", "check", "varn_v1", "varn_v2", "mag_latch"):
    f = CT.POSE_FRAMES[pose]
    assign(poses)
    v = CT.POSE_VARIANT.get(pose, {})
    CT.show_variant(v.get("grip", ""), v.get("mag", "30"), bool(v.get("light")))
    S.frame_set(f)
    update()
    extra = [bpy.data.objects[n] for n in ("Foregrip • varn_v1", "Foregrip • varn_v2") if v.get("grip") and n.endswith(v["grip"])]
    b = tris([o for o in GUN + MAG if not o.hide_viewport] + extra)
    dg = C.evaluated_depsgraph_get()
    e = glove.evaluated_get(dg)
    me = e.to_mesh()
    W = wr.matrix_world.inverted() @ e.matrix_world
    G = np.array([tuple(W @ vv.co * 1000) for vv in me.vertices])
    e.to_mesh_clear()
    rec = {}
    for r, idx in REG.items():
        d = np.array([signed(b, G[i]) for i in idx])
        near = d[np.abs(d) < 25]
        if not len(near):
            continue
        rec[r] = dict(touch=int((np.abs(near) <= 3).sum()), inside_2mm=int((near < -2).sum()), inside_5mm=int((near < -5).sum()),
                      min=round(float(near.min()), 1))
    tips = {}
    for k, idx in TIPIDX.items():
        p = G[idx].mean(0)
        tips[k] = round(signed(b, p), 1)
    gap = {s: round((arms.pose.bones[f"hand.{s}"].head - arms.pose.bones[f"ik_hand.{s}"].head).length * 1000, 1) for s in ("L", "R")}
    pose_rep[f"{f} {CT.POSE_RU[pose]}"] = dict(regions=rec, fingertips_mm=tips, reach_gap_mm=gap)
    log("поза", f, "подушечки", tips, "недотяг кисти", gap)
CT.show_variant()
REP["poses"] = pose_rep

# ---------------------------------------------------------------- 4. недотяг кисти в клипах
reach = {}
glove_mod = next(m for m in glove.modifiers if m.type == "ARMATURE")
glove_mod.show_viewport = False
for act in CT.clip_actions():
    if act.get(CT.NOT_PORTED):
        continue
    assign(act)
    end = int(math.ceil(CT.last_key(act, arms)))
    w = {"L": (0.0, 0), "R": (0.0, 0)}
    for f in range(1, end + 1):
        S.frame_set(f)
        for s in ("L", "R"):
            d = (arms.pose.bones[f"hand.{s}"].head - arms.pose.bones[f"ik_hand.{s}"].head).length * 1000
            if d > w[s][0]:
                w[s] = (round(d, 1), f)
    reach[act.name[len(CT.PREFIX):]] = w
glove_mod.show_viewport = True
REP["reach_mm"] = reach

# ---------------------------------------------------------------- 5. кадры (Workbench, камера игры и сбоку)
S.render.engine = "BLENDER_WORKBENCH"
S.render.resolution_x, S.render.resolution_y = 1280, 720
S.render.resolution_percentage = 100
S.render.image_settings.file_format = "PNG"
S.render.image_settings.color_mode = "RGB"
sh = S.display.shading
sh.light, sh.color_type, sh.show_cavity = "STUDIO", "TEXTURE", True
sh.show_shadows = False
S.view_settings.view_transform = "Standard"
fps_cam = bpy.data.objects["FPS • Camera"]
side = bpy.data.objects.new("_side", bpy.data.cameras.new("_side"))
S.collection.objects.link(side)
side.data.type = "ORTHO"
side.data.clip_start, side.data.clip_end = 0.01, 5


def look(cam, eye, tgt, up):
    f_ = (tgt - eye).normalized()
    r = f_.cross(up).normalized()
    u = r.cross(f_)
    cam.matrix_world = Matrix(((r.x, u.x, -f_.x, eye.x), (r.y, u.y, -f_.y, eye.y), (r.z, u.z, -f_.z, eye.z), (0, 0, 0, 1)))


def shot(name, act_name, frame, cam="fps", target_mm=(200, 0, -60), eye_dir=(0.2, 1.0, -0.3), scale=0.32):
    act = bpy.data.actions[act_name]
    assign(act)
    v = CT.variant_of(act) if act_name != CT.POSES else {}
    CT.show_variant(v.get("grip", ""), v.get("mag", "30"), bool(v.get("light")))
    S.frame_set(frame)
    update()
    if cam == "fps":
        S.camera = fps_cam
    else:
        W = wr.matrix_world
        t = W @ (Vector(target_mm) / 1000)
        d = (W.to_3x3() @ Vector(eye_dir)).normalized()
        side.data.ortho_scale = scale
        look(side, t + d * 0.7, t, W.to_3x3() @ Vector((0, 0, 1)))
        S.camera = side
    S.render.filepath = str(SHOTS / f"{name}.png")
    bpy.ops.render.render(write_still=True)
    log("кадр", name)


tac = clips["Reload_Tactical"]["marks"]
fast = clips["Reload_Fast"]["marks"]
full = clips["Reload_Full"]["marks"]
shot("v02_01_hvat_kadr1", CT.POSES, 1)
shot("v02_02_hvat_kadr1_sboku", CT.POSES, 1, cam="side", target_mm=(60, 0, -80), eye_dir=(0, -1, 0), scale=0.26)
shot("v02_03_prislonenie", "VERAS54_Reload_Tactical", tac["lean"], cam="side", target_mm=(200, 0, -70), eye_dir=(0, 1, 0), scale=0.34)
shot("v02_04_primykanie", "VERAS54_Reload_Tactical", tac["join"] + 2, cam="side", target_mm=(200, 0, -70), eye_dir=(0, 1, 0), scale=0.34)
shot("v02_05_bolshoy_na_zashchelke", "VERAS54_Reload_Tactical", tac["latch_press"] + 1, cam="side", target_mm=(170, 0, -80),
     eye_dir=(-0.3, 1, -0.4), scale=0.26)
shot("v02_06_bystraya_vylet_1", "VERAS54_Reload_Fast", fast["mag_toss"] + 3)
shot("v02_07_bystraya_vylet_2", "VERAS54_Reload_Fast", fast["mag_toss"] + 7)
shot("v02_08_peredyorgivanie", "VERAS54_Reload_Full", full["rack_pull"] + 4)
shot("v02_09_perevodchik", "VERAS54_Fire_Mode_Auto_Burst", 9, cam="side", target_mm=(120, 0, -20), eye_dir=(0.2, -1, 0.3), scale=0.22)
shot("v02_10_izvlechenie_kachok", "VERAS54_Reload_Tactical", 22)

# вылет в быстрой: магазин в кадре камеры игры?
act = bpy.data.actions["VERAS54_Reload_Fast"]
assign(act)
toss = []
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
for f in range(fast["mag_toss"], fast["mag_toss"] + 20):
    S.frame_set(f)
    p = wr.matrix_world @ wr.pose.bones["SpareMag"].matrix.translation
    co = world_to_camera_view(S, fps_cam, p)
    toss.append([f, round(co.x, 2), round(co.y, 2), round(wr.pose.bones["SpareMag"].scale.x, 3)])
REP["toss_in_camera"] = toss
Path(OUT).write_text(json.dumps(REP, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
log("готово", OUT)
