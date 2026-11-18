"""ВЕРАС-54, клипы рук: замеры для собственной проверки (печать в лог).

  — магазин в шахте: на участках, где магазин у шахты (качок, зацеп, досылание), его отклонение от пути клипов v13
    (поворот вокруг переднего зацепа), мм — у зацепа и у середины магазина;
  — руки: недотяг кисти до цели по всем кадрам каждого клипа, мм;
  — начало и конец клипа — хват (кроме «убрать автомат» и «палец со спуска»).

blender -b <файл клипов.blend> --python tools/veras54_v14/clips/check_clips.py
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clip_tools as CT  # noqa: E402

S = bpy.context.scene
arms, wr = CT.rigs()
root = bpy.data.objects["VERAS54"]
PTS = json.loads(root["clip_points"])
log = lambda *a: print("VERAS_CHECK", *a, flush=True)  # noqa: E731


def pchip_lin(keys, f):
    """Путь магазина — тем же монотонным сплайном, что у сборщика (build_clips.pchip)."""
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


# участки «у шахты» неполной перезарядки и путь магазина v13 (качок°, крен°, x, y, z) в осях автомата при покое
PATH = {"Reload_Tactical": [(16, 0, 0, 0, 0, 0), (18, 0, 0, 0, 0, 0), (22, -24, 0, 0, 0, 0), (25, -30, 0, 0, -0.012, -0.05),
                            (30, -25, 15, 0.06, 0.06, -0.2), (36, -10, 35, 0.17, 0.19, -0.4), (42, -10, 35, 0.17, 0.19, -0.4),
                            (48, -28, 10, 0.02, -0.01, -0.12), (52, -26, 0, 0, -0.006, -0.012), (54, -22, 0, 0, 0, 0),
                            (57, 0.8, 0, 0, 0, 0), (58, 0, 0, 0, 0, 0), (60, 0, 0, 0, 0, 0)],
        "Reload_Fast": [(13, -10, 35, 0.17, 0.19, -0.4), (15, -12, 32, 0.16, 0.18, -0.36), (22, -33, 12, 0.035, 0.055, -0.095),
                        (25, -34, 7, 0.018, 0.042, -0.074), (27, -34, 6, 0.016, 0.040, -0.071), (29, -31, 1, 0.004, 0.004, -0.050),
                        (32, -29, 0, 0.0, -0.004, -0.03), (35, -27, 0, 0, -0.006, -0.014), (37, -22, 0, 0, 0, 0),
                        (40, 0.8, 0, 0, 0, 0), (41, 0, 0, 0, 0, 0), (43, 0, 0, 0, 0, 0)]}
WELL = {"Reload_Tactical": ([(16, 0, 0, 0, 0, 0), (18, 0, 0, 0, 0, 0), (22, -24, 0, 0, 0, 0), (25, -30, 0, 0, -0.012, -0.05)],
                            [(52, -26, 0, 0, -0.006, -0.012), (54, -22, 0, 0, 0, 0), (57, 0.8, 0, 0, 0, 0), (58, 0, 0, 0, 0, 0),
                             (60, 0, 0, 0, 0, 0)]),
        "Reload_Fast": ([(29, -31, 1, 0.004, 0.004, -0.050), (32, -29, 0, 0.0, -0.004, -0.03), (35, -27, 0, 0, -0.006, -0.014),
                         (37, -22, 0, 0, 0, 0), (40, 0.8, 0, 0, 0, 0), (41, 0, 0, 0, 0, 0), (43, 0, 0, 0, 0, 0)],)}


def gun_world():
    return wr.matrix_world.copy()


bad = []
for act in CT.clip_actions():
    CT.open_action(bpy.context, act.name)
    end = S.frame_end
    worst = {"L": 0.0, "R": 0.0}
    for f in range(1, end + 1):
        S.frame_set(f)
        for s in ("L", "R"):
            worst[s] = max(worst[s], (arms.pose.bones[f"hand.{s}"].head - arms.pose.bones[f"ik_hand.{s}"].head).length * 1000)
    name = act.name[len(CT.PREFIX):]
    line = f"{name}: {end} к, недотяг L {worst['L']:.1f} R {worst['R']:.1f} мм"
    if name in WELL:
        S.frame_set(1)
        bpy.context.view_layer.update()
        WR0 = gun_world()
        rest = wr.data.bones["Magazine_Control"].matrix_local
        piv = Vector(PTS["pivot"])
        mc = Vector((0.20, 0.0, -0.10))                # середина магазина (оси рига оружия), примерно
        dev = 0.0
        for seg in WELL[name]:
            for f10 in range(seg[0][0] * 10, seg[-1][0] * 10 + 1, 5):
                f = f10 / 10
                S.frame_set(int(f), subframe=f - int(f))
                bpy.context.view_layer.update()
                a, r, x, y, z = pchip_lin(PATH[name], f)
                PW = WR0 @ piv
                D = Matrix.Translation(Vector((x, y, z))) @ Matrix.Translation(PW) @ \
                    Euler((math.radians(a), math.radians(r), 0), "XYZ").to_matrix().to_4x4() @ Matrix.Translation(-PW)
                want = WR0.inverted() @ D @ WR0 @ rest      # где кость магазина должна быть (оси рига оружия)
                have = wr.pose.bones["Magazine_Control"].matrix
                for p in (piv, mc):
                    q_want = want @ (rest.inverted() @ p)
                    q_have = have @ (rest.inverted() @ p)
                    dev = max(dev, (q_want - q_have).length * 1000)
        line += f"; магазин у шахты: отклонение от пути до {dev:.1f} мм"
    # начало и конец — хват
    if name not in ("Holster", "Finger_Off", "Finger_On", "Draw"):
        P = CT.pose_table(bpy.data.actions[CT.POSES], arms)["grip"]
        cv = CT.bone_curves(CT.bag_of(act, arms))
        off = []
        for f in (1, end):
            for n in ("Weapon_CTRL", "ik_hand.L", "ik_hand.R", "f_index.02.R", "f_middle.02.L"):
                if n in cv and not CT.close(CT.read(cv[n], arms.pose.bones[n], f), P[n], 1e-4):
                    off.append((f, n))
        if off:
            line += f"; НЕ хват на краях: {off[:4]}"
            bad.append(name)
    log(line)
log("клипов", len(CT.clip_actions()), "версий", len(CT.clip_actions(True)) - len(CT.clip_actions()), "не начинаются / не кончаются хватом:", bad)
