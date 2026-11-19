"""ВЕРАС-54: что владелец поменял сам — позы и клипы его файла против генератора и против «до пересборки».

Только чтение: открывается КОПИЯ его файла, ничего не сохраняется.

blender -b <копия ВЕРАС-54_руки_клипы_v01.blend> --factory-startup --python tools/veras54_v14/clips_port/analyze_owner.py --
        <генератор.blend> <до_пересборки (копия).blend> <выход.json>

Позы: по каждой позе и кости — сдвиг (мм, в осях родителя кости) и поворот (°) от генератора и от «до пересборки»;
в мире — где кисти, подушечки пальцев и автомат (мм / °).
Клипы: разница с генератором по ключам; затем перенос поз панели (clip_tools.remap) на копии клипа генератора —
генератор → «до пересборки» → текущие позы и напрямую генератор → текущие; что после этого осталось — ручные правки.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "clips"))
import clip_tools as CT  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
GEN, PRE, OUT = args[0], args[1], args[2]
log = lambda *a: print("OWN", *a, flush=True)  # noqa: E731
S = bpy.context.scene
arms, wr = CT.rigs()
glove = bpy.data.objects["FPS_Arms"]
cam = bpy.data.objects["FPS • Camera"]


def append_actions(path, names, suffix):
    before = set(bpy.data.actions)
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.actions = [n for n in src.actions if n in names]
    out = {}
    for a in set(bpy.data.actions) - before:
        base = a.name.rsplit(".", 1)[0] if a.name[-4:-3] == "." and a.name[-3:].isdigit() else a.name
        a.name = base + suffix
        a.use_fake_user = False
        out[base] = a
    return out


base_clips = [a.name for a in CT.clip_actions()]
gen = append_actions(GEN, set(base_clips) | {CT.POSES}, "@gen")
pre = append_actions(PRE, {CT.POSES}, "@pre")
log("добавлено из генератора", len(gen), "из до_пересборки", len(pre))

poses_v01 = bpy.data.actions[CT.POSES]
T = {"gen": CT.pose_table(gen[CT.POSES], arms), "pre_raw": CT.pose_table(pre[CT.POSES], arms),
     "v01": CT.pose_table(poses_v01, arms)}
# позы «до пересборки» так, как их увидел бы перенос (кадры поз приведены к хвату кадра 1) — на копии действия
pre_tidy = pre[CT.POSES].copy()
pre_tidy.name = "VERAS54_Poses@pre_tidy"
T["pre"] = CT.tidy_poses(bpy.context, arms, wr, pre_tidy, log)
T["v01_tidy"] = CT.tidy_poses(bpy.context, arms, wr, poses_v01.copy(), log)


def dm(a, b):
    ang, dist = CT.apart(a, b)
    return round(ang, 2), round(dist * 1000, 2)


# ---------------------------------------------------------------- позы, в осях костей
own, fing, left, right = CT.bone_sets(arms)
pose_diff = {}
for name, f in CT.POSE_FRAMES.items():
    rec = {}
    for pb in arms.pose.bones:
        n = pb.name
        e = {}
        for k in ("pre", "v01"):
            ang, mm = dm(T["gen"][name][n], T[k][name][n])
            if ang > 0.05 or mm > 0.05:
                e[k] = [ang, mm]
        ang, mm = dm(T["pre"][name][n], T["v01"][name][n])
        if ang > 0.05 or mm > 0.05:
            e["v01_vs_pre"] = [ang, mm]
        ang, mm = dm(T["v01"][name][n], T["v01_tidy"][name][n])
        if ang > 0.05 or mm > 0.05:
            e["v01_untidy"] = [ang, mm]
        if e:
            rec[n] = e
    pose_diff[name] = rec

# ---------------------------------------------------------------- позы в мире: кисти, подушечки, автомат
TIPS = [f"{f}.03.{s}" for s in ("L", "R") for f in ("thumb", "f_index", "f_middle", "f_ring", "f_pinky")]
gi = {g.index: g.name for g in glove.vertex_groups}
owner_of = {}
for v in glove.data.vertices:
    if v.groups:
        g = max(v.groups, key=lambda g: g.weight)
        owner_of[v.index] = gi[g.group]
tip_verts = {t: [i for i, o in owner_of.items() if o == t] for t in TIPS}


def world_state(table, name):
    for ob in (arms, wr):
        if ob.animation_data:
            ob.animation_data.action = None
    for pb in arms.pose.bones:
        pb.matrix_basis = table[name][pb.name]
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    eo = glove.evaluated_get(dg)
    me = eo.to_mesh()
    W = eo.matrix_world
    tips = {t: list(sum((W @ me.vertices[i].co for i in idx), Vector()) / max(len(idx), 1)) for t, idx in tip_verts.items()}
    eo.to_mesh_clear()
    AW = arms.matrix_world
    out = dict(tips=tips,
               hand={s: list(AW @ arms.pose.bones[f"hand.{s}"].head) for s in ("L", "R")},
               hand_rot={s: [list(r) for r in (AW @ arms.pose.bones[f"hand.{s}"].matrix).to_3x3()] for s in ("L", "R")},
               gap={s: (arms.pose.bones[f"hand.{s}"].head - arms.pose.bones[f"ik_hand.{s}"].head).length * 1000 for s in ("L", "R")},
               gun=[list(r) for r in (AW @ arms.pose.bones["Weapon_CTRL"].matrix)])
    return out


world = {}
for k in ("gen", "pre", "v01"):
    world[k] = {name: world_state(T[k], name) for name in CT.POSE_FRAMES}


def w_diff(a, b):
    """Разница мировых состояний: кисти, подушечки (мм), автомат (мм, °) — в мире и в осях автомата."""
    out = {}
    for s in ("L", "R"):
        d = (Vector(a["hand"][s]) - Vector(b["hand"][s])).length * 1000
        ra, rb = Matrix(a["hand_rot"][s]), Matrix(b["hand_rot"][s])
        ang = math.degrees(ra.to_quaternion().rotation_difference(rb.to_quaternion()).angle)
        if d > 0.1 or ang > 0.1:
            out[f"hand.{s}"] = [round(d, 1), round(ang, 1)]
    for t in TIPS:
        d = (Vector(a["tips"][t]) - Vector(b["tips"][t])).length * 1000
        if d > 0.2:
            out[t] = round(d, 1)
    ga, gb = Matrix(a["gun"]), Matrix(b["gun"])
    d = (ga.translation - gb.translation).length * 1000
    ang = math.degrees(ga.to_quaternion().rotation_difference(gb.to_quaternion()).angle)
    if d > 0.1 or ang > 0.1:
        out["gun"] = [round(d, 1), round(ang, 1)]
    # кисти относительно автомата (что важно для переноса: место хвата на автомате)
    for s in ("L", "R"):
        la = ga.inverted() @ Vector(a["hand"][s])
        lb = gb.inverted() @ Vector(b["hand"][s])
        d = (la - lb).length * 1000
        if d > 0.1:
            out[f"hand.{s}@gun"] = [round(d, 1)] + [round(v * 1000, 1) for v in (la - lb)]
    return out


world_diff = {name: {"pre_vs_gen": w_diff(world["pre"][name], world["gen"][name]),
                     "v01_vs_gen": w_diff(world["v01"][name], world["gen"][name]),
                     "v01_vs_pre": w_diff(world["v01"][name], world["pre"][name])} for name in CT.POSE_FRAMES}
gaps = {k: {name: {s: round(world[k][name]["gap"][s], 1) for s in ("L", "R")} for name in CT.POSE_FRAMES} for k in world}

# ---------------------------------------------------------------- клипы
def curves(act):
    out = {}
    for layer in act.layers:
        for st in layer.strips:
            for slot in act.slots:
                bag = st.channelbag(slot)
                if bag is None:
                    continue
                for fc in bag.fcurves:
                    out[(slot.name_display, fc.data_path, fc.array_index)] = fc
    return out


def bone_key_diff(a, b, ob_name, ob):
    """По костям: на каких кадрах ключи различаются, наибольший сдвиг (мм) и поворот (°) матрицы basis."""
    ca = CT.bone_curves(CT.bag_of(a, ob))
    cb = CT.bone_curves(CT.bag_of(b, ob))
    out = {}
    for n, cva in ca.items():
        cvb = cb.get(n, {})
        pb = ob.pose.bones.get(n)
        if pb is None:
            continue
        frames = sorted({round(kp.co[0], 3) for fc in cva.values() for kp in fc.keyframe_points})
        worst = [0.0, 0.0]
        fr = []
        for f in frames:
            ang, d = CT.apart(CT.read(cva, pb, f), CT.read(cvb, pb, f))
            if ang > 0.05 or d * 1000 > 0.05:
                fr.append(f)
                worst = [max(worst[0], ang), max(worst[1], d * 1000)]
        if fr:
            out[n] = dict(frames=fr, max_deg=round(worst[0], 2), max_mm=round(worst[1], 2))
    return out


def other_diff(a, b):
    """Ключи свойств и прочих кривых (не кости рук): разные значения."""
    ca, cb = curves(a), curves(b)
    out = {}
    for k, fc in ca.items():
        if k[0] == arms.name and k[1].startswith("pose.bones"):
            continue
        g = cb.get(k)
        va = [(round(p.co[0], 3), round(p.co[1], 5)) for p in fc.keyframe_points]
        vb = [(round(p.co[0], 3), round(p.co[1], 5)) for p in g.keyframe_points] if g else None
        if va != vb:
            out["|".join(map(str, k))] = dict(v01=va[:40], other=vb[:40] if vb else None)
    return out


clips = {}
for name in base_clips:
    a = bpy.data.actions[name]
    g = gen[name]
    sim1 = g.copy()
    n1 = CT.remap(sim1, arms, T["gen"], T["pre"])
    n2 = CT.remap(sim1, arms, T["pre"], T["v01"])
    sim2 = g.copy()
    n3 = CT.remap(sim2, arms, T["gen"], T["v01"])
    rec = dict(length=max(kp.co[0] for fc in curves(a).values() for kp in fc.keyframe_points),
               length_gen=max(kp.co[0] for fc in curves(g).values() for kp in fc.keyframe_points),
               marks=a.get("marks"), marks_gen=g.get("marks"), synced_keys=[n1, n2, n3],
               vs_gen=bone_key_diff(a, g, arms.name, arms),
               resid_2step=bone_key_diff(a, sim1, arms.name, arms),
               resid_direct=bone_key_diff(a, sim2, arms.name, arms),
               weapon_vs_gen=bone_key_diff(a, g, wr.name, wr),
               other_vs_gen=other_diff(a, g))
    clips[name] = rec
    log(name, "отличий от генератора (костей)", len(rec["vs_gen"]), "после переноса поз осталось", len(rec["resid_2step"]),
        "/", len(rec["resid_direct"]))
    bpy.data.actions.remove(sim1)
    bpy.data.actions.remove(sim2)

Path(OUT).write_text(json.dumps(dict(pose_diff=pose_diff, world_diff=world_diff, gaps=gaps, clips=clips,
                                     world={k: {n: dict(hand=v["hand"], gun=v["gun"]) for n, v in w.items()} for k, w in world.items()}),
                                ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
log("готово", OUT)
