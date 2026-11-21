"""ВЕРАС-54, файл клипов v02: путь магазина у шахты — заново, по таблицам генератора клипов, с осью качка v14.

Почему: при переносе на v14 (port.py) путь магазина взяли из файла v01 таким, каким он стал после правки позы 41 и
кнопки «Хваты из поз → во все клипы»: та кнопка ставила кисть по новой позе, а место магазина в кисти — тоже по новой,
и на кадрах качка магазин уезжал с пути на 35–40 мм (в v02 — вверх в коробку до 81 мм и вбок на 16 мм). Здесь путь
магазина относительно автомата берётся из таблиц tools/veras54_v14/clips/build_clips.py (MAG_SWAP, быстрая, «живые»,
проверка, вынуть / вставить) — качок вокруг переднего зацепа, только ось — зацеп v14; кадры — с остановками
«прислонение», которые добавил перенос. Кисть ставится вокруг магазина так, как в позе 41 «на магазине». Старый
магазин быстрой перезарядки до удара стоит в шахте (раньше съезжал между ключами 1 и 28), вылет — заново от нового
места; уроненный в «выскользнул» падает с того места, где выскользнул. Потом — плечо, где рука не дотягивается, и
версии (ВАРН, магазины 45 / 60).

blender -b <ВЕРАС-54_руки_клипы_v02.blend> --factory-startup --python-exit-code 1 --python tools/veras54_v14/clips_port/mag_path_fix.py -- <выход.blend> [клип …]
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import clip_tools_v14 as CT  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
OUT = args[0]
ONLY = set(args[1:])
S, C = bpy.context.scene, bpy.context
log = lambda *a: print("FIX", *a, flush=True)  # noqa: E731
arms, wr = CT.rigs()
root = bpy.data.objects[CT.ROOT]
magob = bpy.data.objects[CT.MAG]
FPS = S.render.fps / S.render.fps_base
PIVOT = Vector((0.23241, 0.0, -0.02342))               # передний зацеп магазина v14, оси рига оружия (port_report: pivot_mm.new)
HOLD = 3                                               # «прислонение» — остановка, добавленная переносом
REST_MAG = wr.data.bones["Magazine_Control"].matrix_local.copy()
REST_SPARE = wr.data.bones["SpareMag"].matrix_local.copy()
B_MAG = CT.hold_link(arms, "mag.L")
REP = {}


def update():
    C.view_layer.update()


def assign(act):
    for ob in (arms, wr, root, magob):
        ad = ob.animation_data or ob.animation_data_create()
        sl = CT.slot_of(act, ob) if act else None
        ad.action = act if sl else None
        if sl:
            ad.action_slot = sl


# ---------------------------------------------------------------- «мир при покое» генератора: риг оружия при хвате
POSES = bpy.data.actions[CT.POSES]
T = CT.pose_table(POSES, arms)
assign(None)
for pb in list(arms.pose.bones) + list(wr.pose.bones):
    pb.matrix_basis = Matrix.Identity(4)
arms.pose.bones["Weapon_CTRL"].matrix_basis = T["grip"]["Weapon_CTRL"]
update()
WR_REST = wr.matrix_world.copy()
M41 = T["mag"]["mag.L"]


def about(p, rot3):
    return Matrix.Translation(p) @ rot3.to_4x4() @ Matrix.Translation(-p)


def conv(k):
    """(качок°, крен°, x, y, z) генератора — сдвиг в осях автомата (мир при покое) вокруг зацепа → оси рига оружия."""
    a, r, x, y, z = k
    Dw = Matrix.Translation(Vector((x, y, z))) @ about(WR_REST @ PIVOT, Euler((math.radians(a), math.radians(r), 0), "XYZ").to_matrix())
    return WR_REST.inverted() @ Dw @ WR_REST


def pchip(keys, f):
    """Монотонный кубический сплайн по ключам (кадр, значения…) — как в генераторе клипов."""
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


def seg(keys, lo, hi):
    return [k for k in keys if lo <= k[0] <= hi]


def shift(keys, d):
    return [(k[0] + d, *k[1:]) for k in keys]


# ---------------------------------------------------------------- пути магазина из генератора (кадры генератора)
MAG_SWAP = [
    (16, 0, 0, 0, 0, 0), (18, 0, 0, 0, 0, 0), (22, -24, 0, 0, 0, 0), (25, -30, 0, 0, -0.012, -0.05),
    (30, -25, 15, 0.06, 0.06, -0.2), (36, -10, 35, 0.17, 0.19, -0.4), (42, -10, 35, 0.17, 0.19, -0.4),
    (48, -28, 10, 0.02, -0.01, -0.12), (52, -26, 0, 0, -0.006, -0.012), (54, -22, 0, 0, 0, 0),
    (57, 0.8, 0, 0, 0, 0), (58, 0, 0, 0, 0, 0), (60, 0, 0, 0, 0, 0),
]
SWAP = seg(MAG_SWAP, 16, 42) + seg(MAG_SWAP, 48, 60)


def fast_keys(stuck):
    s = 9 if stuck else 0
    K, strike = 13, 29
    mag = [(K, -10, 35, 0.17, 0.19, -0.4), (K + 2, -12, 32, 0.16, 0.18, -0.36), (22, -33, 12, 0.035, 0.055, -0.095),
           (25, -34, 7, 0.018, 0.042, -0.074), (27, -34, 6, 0.016, 0.040, -0.071), (strike, -31, 1, 0.004, 0.004, -0.050)]
    if stuck:
        mag += [(31, -32, 3, 0.010, 0.020, -0.062), (35, -32, 3, 0.010, 0.020, -0.062), (36, -32.5, 4, 0.012, 0.024, -0.066),
                (38, -30, 0, 0.002, 0.0, -0.046)]
    mag += [(32 + s, -29, 0, 0.0, -0.004, -0.03), (35 + s, -27, 0, 0, -0.006, -0.014), (37 + s, -22, 0, 0, 0, 0),
            (40 + s, 0.8, 0, 0, 0, 0), (41 + s, 0, 0, 0, 0, 0), (43 + s, 0, 0, 0, 0, 0)]
    old = [(1, 0, 0, 0, 0, 0), (strike - 1, 0, 0, 0, 0, 0), (strike + 0.5, -9, 0, 0, 0, 0)]
    if stuck:
        old += [(strike + 2, -18, 0, 0, -0.004, -0.008), (37, -18, 0, 0, -0.004, -0.008), (39, -25, 0, 0, -0.004, -0.012)]
        free = 39
    else:
        old += [(strike + 2, -25, 0, 0, -0.004, -0.012)]
        free = strike + 2
    return mag, old, free


def living(kind):
    if kind == "miss_a":
        ins = [(48, -28, 10, 0.02, -0.01, -0.12), (51, -27, 2, 0.0, -0.014, -0.032), (53, -27, 4, 0.0, -0.010, -0.044),
               (57, -27, 4, 0.0, -0.010, -0.046), (60, -28, 6, 0.005, -0.004, -0.07), (63, -26, 0, 0, -0.006, -0.012),
               (65, -22, 0, 0, 0, 0), (68, 0.8, 0, 0, 0, 0), (69, 0, 0, 0, 0, 0), (71, 0, 0, 0, 0, 0)]
    elif kind == "miss_b":
        ins = [(48, -28, 10, 0.03, -0.01, -0.11), (51, -27, 5, 0.032, -0.008, -0.03), (53, -27, 5, 0.034, -0.008, -0.026),
               (57, -27, 5, 0.034, -0.008, -0.028), (60, -27, 3, 0.012, -0.006, -0.045), (63, -26, 0, 0, -0.006, -0.012),
               (65, -22, 0, 0, 0, 0), (68, 0.8, 0, 0, 0, 0), (69, 0, 0, 0, 0, 0), (71, 0, 0, 0, 0, 0)]
    else:
        if kind == "wrong_a":
            ins = [(48, -28, 10, 0.02, -0.01, -0.12), (52, -27, 2, 0.0, -0.008, -0.045), (55, -27, 2, 0.0, -0.008, -0.048),
                   (60, -27, 3, 0.0, -0.008, -0.05), (64, -28, 10, 0.03, 0.02, -0.14), (72, -28, 10, 0.03, 0.02, -0.14)]
            flip_to = 72
        else:
            ins = [(48, -28, 10, 0.02, -0.01, -0.12), (51, -28, 10, 0.02, -0.01, -0.12), (55, -28, 10, 0.03, 0.01, -0.14),
                   (63, -28, 10, 0.03, 0.01, -0.14)]
            flip_to = 63
        t = flip_to + 4
        ins += [(t, -28, 10, 0.02, -0.01, -0.12), (t + 4, -26, 0, 0, -0.006, -0.012), (t + 6, -22, 0, 0, 0, 0),
                (t + 9, 0.8, 0, 0, 0, 0), (t + 10, 0, 0, 0, 0, 0), (t + 12, 0, 0, 0, 0, 0)]
    return seg(MAG_SWAP, 16, 42) + ins


MK = [(16, 0, 0, 0, 0, 0), (18, 0, 0, 0, 0, 0), (22, -22, 0, 0, 0, 0), (27, -30, 0, 0, -0.012, -0.05),
      (64, -30, 0, 0, -0.012, -0.05), (73, -28, 0, 0.0, -0.01, -0.1), (76.5, -26, 0, 0, -0.006, -0.012),
      (78, -22, 0, 0, 0, 0), (81, 0.8, 0, 0, 0, 0), (82, 0, 0, 0, 0, 0), (84, 0, 0, 0, 0, 0)]
CAM_W = [(1, 0), (23, 0), (39, 1), (57, 1), (74, 0), (104, 0)]          # проверка: доля пути «к глазам» (не у шахты)
DROP = seg(MAG_SWAP, 16, 25) + [(27, -28, 4, 0.012, 0.012, -0.08), (31, -27, 6, 0.016, 0.016, -0.09)] + shift(seg(MAG_SWAP, 30, 60), 10)

PLANS = {
    "Reload_Tactical": SWAP, "Reload_Full": SWAP, "Reload_Full_Slip": SWAP,
    "Mag_Eject": seg(MAG_SWAP, 16, 36), "Mag_Insert": [(12, -10, 35, 0.17, 0.19, -0.4)] + shift(seg(MAG_SWAP, 48, 60), -30),
    "Reload_Tactical_Drop": DROP, "Mag_Check": MK,
    "Reload_Miss_A": living("miss_a"), "Reload_Miss_B": living("miss_b"),
    "Reload_Wrong_A": living("wrong_a"), "Reload_Wrong_B": living("wrong_b"),
    "Reload_Fast": fast_keys(False)[0], "Reload_Fast_Full": fast_keys(False)[0],
    "Reload_Fast_Stuck": fast_keys(True)[0], "Reload_Fast_Full_Stuck": fast_keys(True)[0],
}


def holds_of(act):
    marks = json.loads(act.get("marks", "{}"))
    return sorted(int(v) for k, v in marks.items() if k == "lean" or k.startswith("lean_"))


def to_gen(g, holds):
    """Кадр файла v02 → кадр генератора: остановки «прислонение» (HOLD кадров после кадра h) — назад."""
    back = 0.0
    for h in holds:
        if g > h + HOLD:
            back += HOLD
        elif g > h:
            back += g - h
    return g - back


def mag_world(g):
    return wr.matrix_world @ wr.pose.bones["Magazine_Control"].matrix


def solve_hand(g, E):
    """Ключ левой кисти на кадре g: магазин (кость Magazine_Control) = E в осях рига оружия, хват — поза 41."""
    S.frame_set(int(g), subframe=g - int(g))
    update()
    want_w = wr.matrix_world @ E @ REST_MAG
    ik = arms.pose.bones["ik_hand.L"]
    ik.matrix = arms.matrix_world.inverted() @ want_w @ (B_MAG @ M41).inverted()
    return ik.matrix_basis.copy()


def reach_left(act, frames_all, tol=2.0):
    """Где левая не дотягивается (магазин далеко) — плечо подаётся к кисти ключами (как у генератора)."""
    ua = arms.pose.bones["upper_arm.L"]
    worst = 0.0
    for _ in range(3):
        gaps = {}
        for f in frames_all:
            S.frame_set(f)
            gaps[f] = (arms.pose.bones["ik_hand.L"].head - arms.pose.bones["hand.L"].head).length * 1000
        bad = [f for f, gp in gaps.items() if gp > tol]
        worst = max(gaps.values()) if gaps else 0.0
        if not bad:
            break
        plan = []
        for f in bad:
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
    return round(worst, 1)


def drop_keys(fc_list, lo, hi):
    for fc in fc_list:
        for i in reversed(range(len(fc.keyframe_points))):
            if lo - 1e-3 <= fc.keyframe_points[i].co[0] <= hi + 1e-3:
                fc.keyframe_points.remove(fc.keyframe_points[i], fast=True)
        fc.update()


def spare_curves(act):
    bag = CT.bag_of(act, wr)
    return bag, [fc for fc in bag.fcurves if fc.data_path in ('pose.bones["SpareMag"].location', 'pose.bones["SpareMag"].rotation_euler',
                                                              'pose.bones["SpareMag"].rotation_quaternion')]


def write_spare(act, keys):
    """(кадр, матрица кости SpareMag в осях рига оружия) → ключи."""
    bag, _fcs = spare_curves(act)
    pbs = wr.pose.bones["SpareMag"]
    plan = []
    for f, M in keys:
        S.frame_set(int(f), subframe=f - int(f))
        update()
        pbs.matrix = M
        plan.append((f, pbs.matrix_basis.copy()))
    cv = CT.bone_curves(bag)
    for f, basis in plan:
        CT.write(cv.setdefault("SpareMag", {}), pbs, f, basis, bag, insert=True)


def fall_keys(M0w, g0, end, v0_gun, spin, n, step):
    """Падение детали из мирового M0w с кадра g0: скорость v0 — в осях автомата (мир при покое), повернуть как автомат на g0."""
    S.frame_set(g0)
    update()
    Grot = (wr.matrix_world @ WR_REST.inverted()).to_3x3()
    v = Grot @ Vector(v0_gun)
    out = []
    for f in range(g0 + 1, min(g0 + n, end) + 1, step):
        t = (f - g0) / FPS
        off = v * t + Vector((0, 0, -4.9 * t * t))
        R = spin(t)
        M = Matrix.Translation(M0w.translation + off) @ R.to_4x4() @ M0w.to_3x3().to_4x4()
        S.frame_set(f)
        update()
        out.append((f, wr.matrix_world.inverted() @ M))
    return out


# ---------------------------------------------------------------- клипы
for act in CT.clip_actions():
    nm = act.name[len(CT.PREFIX):]
    if nm not in PLANS or (ONLY and nm not in ONLY) or act.get(CT.NOT_PORTED):
        continue
    keys = PLANS[nm]
    holds = holds_of(act)
    assign(act)
    end = int(math.ceil(CT.last_key(act, arms)))
    cv = CT.bone_curves(CT.bag_of(act, arms))
    ik = arms.pose.bones["ik_hand.L"]
    infl = CT.bag_of(act, wr).fcurves.find('pose.bones["Magazine_Control"].constraints["В левой кисти"].influence')
    lo, hi = keys[0][0], keys[-1][0]
    rec = dict(holds=holds, frames=[], blended=[], skipped_cam=[])
    # магазин сейчас (для проверки «к глазам» — смесь)
    plan = []
    for g in sorted({round(k.co[0], 3) for fc in cv["ik_hand.L"].values() for k in fc.keyframe_points}):
        gg = to_gen(g, holds)
        if not (lo <= gg <= hi) or infl.evaluate(g) < 0.5:
            continue
        E = conv(pchip(keys, gg))
        if nm == "Mag_Check":
            w = min(max(pchip(CAM_W, gg)[0], 0.0), 1.0)
            if w >= 0.5:
                rec["skipped_cam"].append(g)
                continue
            if w >= 0.02:
                S.frame_set(int(g), subframe=g - int(g))
                update()
                Ecur = wr.pose.bones["Magazine_Control"].matrix @ REST_MAG.inverted()
                lc, rc, _ = E.decompose()
                lb, rb, _ = Ecur.decompose()
                E = Matrix.Translation(lc.lerp(lb, w)) @ rc.slerp(rb, w).to_matrix().to_4x4()
                rec["blended"].append([g, round(w, 3)])
        plan.append((g, solve_hand(g, E)))
    for g, basis in plan:
        CT.write(cv["ik_hand.L"], ik, g, basis, CT.bag_of(act, arms), insert=True)
    rec["frames"] = [g for g, _ in plan]
    # плечо: прежние подачи плеча на этих кадрах (не позы) — прочь, потом заново там, где рука не дотягивается
    span = [g for g, _ in plan]
    if span:
        ua_cv = CT.bone_curves(CT.bag_of(act, arms)).get("upper_arm.L", {})
        a, b = min(span), max(span)
        ua_frames = sorted({round(k.co[0], 3) for fc in ua_cv.values() for k in fc.keyframe_points if a < k.co[0] < b})
        gone = [f for f in ua_frames
                if not any(CT.close(CT.read(ua_cv, arms.pose.bones["upper_arm.L"], f), T[p]["upper_arm.L"], 2e-4) for p in T)]
        for f in gone:
            drop_keys(ua_cv.values(), f, f)
        rec["shoulder_keys_removed"] = gone
        rec["reach_mm"] = reach_left(act, list(range(max(1, int(a) - 3), min(end, int(b) + 3) + 1)))
    # старый магазин быстрой: в шахте до удара, качок от удара, вылет вперёд-вниз заново от нового места
    if nm.startswith("Reload_Fast"):
        _mag, old, free = fast_keys("Stuck" in nm)
        bag, fcs = spare_curves(act)
        drop_keys(fcs, 2, end)
        write_spare(act, [(k[0], conv(k[1:]) @ REST_SPARE) for k in old])
        S.frame_set(free)
        update()
        M0 = wr.matrix_world @ wr.pose.bones["SpareMag"].matrix
        ax_spin = (wr.matrix_world.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
        ax_roll = (wr.matrix_world.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
        v_arm = Vector((1.3, 0.0, -0.45))                # как у переноса: вперёд-вниз, м/с, в осях автомата
        Grot = wr.matrix_world.to_3x3()
        toss = []
        for f in range(free + 1, min(free + 18, end) + 1, 2):
            t = (f - free) / FPS
            off = Grot @ v_arm * t + Vector((0, 0, -4.9 * t * t))
            Rm = (Matrix.Rotation(7.0 * t, 3, ax_spin) @ Matrix.Rotation(1.5 * t, 3, ax_roll)).to_4x4()
            M = Matrix.Translation(M0.translation + off) @ Rm @ M0.to_3x3().to_4x4()
            S.frame_set(f)
            update()
            toss.append((f, wr.matrix_world.inverted() @ M))
        write_spare(act, toss)
        for fc in fcs:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR" if kp.co[0] > free else "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()
        rec["spare"] = dict(old_keys=[k[0] for k in old], free=free, toss=[f for f, _ in toss])
    # уроненный («выскользнул»): с места магазина в кисти на кадре 27, падает как у генератора
    if nm == "Reload_Tactical_Drop":
        bag, fcs = spare_curves(act)
        drop_keys(fcs, 28, end)
        S.frame_set(27)
        update()
        M0 = mag_world(27)
        sp = (-7.0, 2.0, 1.5)
        keys_f = [(28, wr.matrix_world.inverted() @ M0)]
        keys_f += fall_keys(M0, 28, end, (0.0, -0.1, -0.3), lambda t: Euler((t * sp[0], t * sp[1], t * sp[2]), "XYZ").to_matrix(), 14, 2)
        write_spare(act, keys_f)
        rec["drop"] = [f for f, _ in keys_f]
    REP[nm] = rec
    log(nm, "кадров кисти", len(rec["frames"]), "остановки", holds, "недотяг мм", rec.get("reach_mm"),
        "смесь", rec["blended"], rec.get("spare", ""))

# ---------------------------------------------------------------- поза 91: большой на защёлке — сгибы в пределах суставов
import latch_thumb as LT  # noqa: E402

glove = bpy.data.objects["FPS_Arms"]
mods = [m for m in glove.modifiers if m.type == "ARMATURE"]
was = [m.show_viewport for m in mods]
for m in mods:
    m.show_viewport = True
assign(None)
for pb in wr.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
for n in ("SpareMag", "JamCase", "Suppressor_Control"):
    wr.pose.bones[n].scale = (0.001,) * 3
for pb in arms.pose.bones:
    pb.matrix_basis = T["mag"][pb.name].copy()
root["Magazine latch press"] = 1.0
update()
thumb, miss, ang = LT.place(arms, glove, T["mag"], LT.press_point(wr))
root["Magazine latch press"] = 0.0
for m, v in zip(mods, was):
    m.show_viewport = v
bag_p = CT.bag_of(POSES, arms)
cvp = CT.bone_curves(bag_p)
for n, M in thumb.items():
    CT.write(cvp.setdefault(n, {}), arms.pose.bones[n], CT.POSE_FRAMES["mag_latch"], M, bag_p, insert=True)
REP["latch_thumb"] = dict(miss_mm=miss, angles_deg=ang)
log("большой на защёлке: промах мм", miss, "углы", ang)

# ---------------------------------------------------------------- позы → клипы (как кнопка панели), версии, панель, сохранить
res = CT.sync(C, lambda *a: log(*a))
log("позы → клипы", res)
panel = bpy.data.texts.get(CT.PANEL_TEXT) or bpy.data.texts.new(CT.PANEL_TEXT)
panel.from_string((HERE / "clip_tools_v14.py").read_text(encoding="utf-8"))
panel.use_module = True
REP["_sync"] = res
rep_path = HERE.parents[2] / "_asset_src" / "veras54_v14" / "anim_port" / (Path(OUT).stem + ".mag_fix.json")
rep_path.parent.mkdir(parents=True, exist_ok=True)
rep_path.write_text(json.dumps(REP, ensure_ascii=False, indent=1), encoding="utf-8")
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
log("сохранено", OUT)
