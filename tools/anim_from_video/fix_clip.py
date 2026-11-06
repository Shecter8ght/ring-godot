"""Клип рук на проверку и починку пальцев (внутри Blender): анатомия суставов и смыкание по касанию кожи
(tools/anim_from_video/hand_solver.py). Опыт «анимация рук по видео», владелец 2026-11-06.

  audit — по каждому кадру: насколько пальцы входят в оружие и магазин (мм) и насколько сустав «изломан»
          (градусы от анатомической позы); печать по пальцам — наихудшее и сколько кадров с вхождением > 1 мм.
  fix   — то же, затем каждые STEP кадров пальцы обеих кистей: анатомическая поза → смыкание на предмете,
          ключи пальцев заново; после — снова audit. Кисти, предплечья и оружие не трогаются.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <ИЗЛОМ45_Clip_<клип>_v01.blend> --python-exit-code 1 --python tools/anim_from_video/fix_clip.py -- audit|fix [<выход.blend>] [шаг] [palms] [verbose]
(verbose — в какую деталь и на сколько входит ладонь, каждые 6 кадров)
"""
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hand_solver as hs  # noqa: E402

ARGS = sys.argv[sys.argv.index('--') + 1:]
MODE = ARGS[0]
OUT = ARGS[1] if len(ARGS) > 1 else None
STEP = int(ARGS[2]) if len(ARGS) > 2 and ARGS[2].isdigit() else 2
sc = bpy.context.scene
rig = bpy.data.objects['FPS_ArmsRig']
mesh = bpy.data.objects['FPS_Arms']
wr = bpy.data.objects['SMG03_WeaponRig']
# снаружи видимые детали: внутренние (патрон в магазине, подаватель, затвор, гильза задержки) касанию не мешают
INNER = ('Round_', 'Mag13_follower', 'JamCase', 'Bolt_Steel', 'ChargingSlider')
WEAPON = [o for o in bpy.data.objects if o.type == 'MESH' and o.parent == wr and o.visible_get()
          and not o.name.startswith(INNER)]
SIDES = ('L', 'R')
missing = [f'{f}.{j:02d}.{s}' for s in SIDES for f in hs.FINGERS for j in (1, 2, 3)
           if f'{f}.{j:02d}.{s}' not in mesh.vertex_groups]
if missing:
    print('FIX нет групп вершин:', missing[:6])
skins = {s: hs.Skin(rig, mesh, s) for s in SIDES}
for pb in rig.pose.bones:
    pb.rotation_mode = 'XYZ'


def audit(tag):
    dg = bpy.context.evaluated_depsgraph_get()
    stat = {(s, f): [0.0, 0, 0.0] for s in SIDES for f in hs.FINGERS}   # глубина мм, кадров > 1 мм, излом °
    palm = {s: 0.0 for s in SIDES}
    for fr in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(fr)
        bvh = hs.surface(WEAPON, dg)
        for s in SIDES:
            palm[s] = max(palm[s], hs.depth(bvh, skins[s].points(f'hand.{s}')) * 1000)
            for f in hs.FINGERS:
                d = hs.finger_depth(skins[s], bvh, s, f) * 1000
                v = hs.violations(hs.read(rig, s, f), f)
                st = stat[(s, f)]
                st[0] = max(st[0], d)
                st[1] += d > 1.0
                st[2] = max(st[2], v)
        if 'verbose' in ARGS and fr % 6 == 1:
            for s in SIDES:
                for p in hs.palm_points(skins[s], s):
                    i = bvh.inside_part(p)
                    if i >= 0:
                        loc, _, _, dist = bvh.bvh.find_nearest(p, 0.05)
                        if dist and dist > 0.003:
                            print(f'AUDIT ладонь {tag} {s} кадр {fr} внутри {WEAPON[i].name} на {dist * 1000:.1f} мм')
                            break
    n = sc.frame_end - sc.frame_start + 1
    for s in SIDES:
        row = ', '.join(f'{f}: {stat[(s, f)][0]:.1f} мм / {stat[(s, f)][1]} к / {stat[(s, f)][2]:.0f}°' for f in hs.FINGERS)
        print(f'AUDIT {tag} {s} (кадров {n}; ладонь {palm[s]:.1f} мм) {row}')
    return stat


def keyrow(fr):
    for s in SIDES:
        for f in hs.FINGERS:
            for pb in hs.bones(rig, s, f):
                pb.keyframe_insert('rotation_euler', frame=fr)


def fcurves():
    return [fc for layer in rig.animation_data.action.layers for strip in layer.strips for bag in strip.channelbags
            for fc in bag.fcurves]


def settle_palms():
    """Ладонь внутри рукоятки или магазина — цель IK кисти отодвигается наружу (по ключам её положения): на каждом
    ключе — шагами по 0.5 мм вдоль средней нормали, пока ладонь не выйдет (не дальше 25 мм)."""
    dg = bpy.context.evaluated_depsgraph_get()
    for s in SIDES:
        ik = rig.pose.bones[f'ik_hand.{s}']
        loc_fc = [fc for fc in fcurves() if fc.data_path == f'pose.bones["ik_hand.{s}"].location']
        frames = sorted({int(round(k.co.x)) for fc in loc_fc for k in fc.keyframe_points})
        moved = []
        for fr in frames:
            sc.frame_set(fr)
            surf = hs.surface(WEAPON, dg)
            total = 0.0
            base_loc = ik.location.copy()
            for _ in range(50):
                d, depth = hs.palm_push(skins[s], surf, s)
                if d is None or depth < 0.0005:
                    break
                # сдвиг в мире → в осях кости (location задаётся до её поворота, в осях родителя с покоем)
                p3 = (rig.matrix_world @ (ik.matrix @ ik.matrix_basis.inverted())).to_3x3()
                ik.location = ik.location + p3.inverted() @ (d * 0.0005)
                bpy.context.view_layer.update()
                total += 0.5
                if total >= 25:
                    break
            if total:
                delta = ik.location - base_loc
                for fc in loc_fc:
                    for k in fc.keyframe_points:
                        if int(round(k.co.x)) == fr:
                            k.co.y += delta[fc.array_index]
                            k.handle_left.y += delta[fc.array_index]
                            k.handle_right.y += delta[fc.array_index]
                moved.append((fr, total))
        print('FIX ладонь', s, 'ключей', len(frames), 'сдвинуто', len(moved), 'наибольший сдвиг мм', max((m[1] for m in moved), default=0))


audit('было')
if MODE == 'fix':
    if 'palms' in ARGS:
        settle_palms()      # опыт: сдвиг кисти наружу по нормали портил хват (правая съезжала с рукоятки) — по просьбе
    dg = bpy.context.evaluated_depsgraph_get()
    frames = list(range(sc.frame_start, sc.frame_end + 1, STEP))
    if frames[-1] != sc.frame_end:
        frames.append(sc.frame_end)
    poses = {}
    for fr in frames:
        sc.frame_set(fr)
        bvh = hs.surface(WEAPON, dg)
        res = {}
        for s in SIDES:
            for f in hs.FINGERS:
                target = hs.anatomical(hs.read(rig, s, f), f)
                res[(s, f)] = hs.close(rig, s, f, target, skins[s], bvh)
        poses[fr] = {(s, f): hs.read(rig, s, f) for s in SIDES for f in hs.FINGERS}
        worst = max(res.items(), key=lambda kv: kv[1][1])
        print('FIX кадр', fr, 'хуже всех', worst[0], 'было/стало мм', worst[1])
    # ключи после всех расчётов: иначе новые ключи меняют позу следующих кадров до их расчёта; прежние ключи пальцев —
    # долой (иначе их позы остаются в кадрах между новыми)
    names = {pb.name for s in SIDES for f in hs.FINGERS for pb in hs.bones(rig, s, f)}
    for fc in [fc for layer in rig.animation_data.action.layers for strip in layer.strips for bag in strip.channelbags
               for fc in bag.fcurves]:
        if fc.data_path.startswith('pose.bones["') and fc.data_path.split('"')[1] in names and 'rotation' in fc.data_path:
            fc.keyframe_points.clear()
    for pb in (rig.pose.bones[n] for n in names):
        pb.rotation_mode = 'YZX'
    for fr in frames:
        for (s, f), vals in poses[fr].items():
            hs.write(rig, s, f, vals)
        keyrow(fr)
    audit('стало')
    if OUT:
        sc.frame_set(1)
        bpy.ops.wm.save_as_mainfile(filepath=OUT)
        print('FIX saved', OUT)
