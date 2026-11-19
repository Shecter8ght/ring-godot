"""ВЕРАС-54: путь магазина в клипах генератора (кадр за кадром, оси рига оружия) → JSON для port.py.

В файле владельца после правки позы 41 (19.11) ключи кисти у шахты (повёрнутые) остались прежними, а место магазина в кисти
сменилось — магазин в его v01 уходит от пути на 35–40 мм. Путь берётся с клипов генератора: ключи клипов владелец не правил,
клипы генератора с ними совпадают кадр в кадр (разведка 19.11).

blender -b <VERAS54_generator_clips.blend> --factory-startup --python tools/veras54_v14/clips_port/record_gen.py -- <выход.json>
"""
import json
import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clip_tools_v14 as CT  # noqa: E402

OUT = sys.argv[sys.argv.index("--") + 1]
arms, wr = CT.rigs()
S = bpy.context.scene
glove = bpy.data.objects["FPS_Arms"]
for m in glove.modifiers:
    m.show_viewport = False
objs = (arms, wr, bpy.data.objects["VERAS54"], bpy.data.objects["Magazine"])
rest = wr.data.bones["Magazine_Control"].matrix_local
out = {}
for act in CT.clip_actions():
    bag = CT.bag_of(act, wr)
    holds = any("Magazine_Control" in fc.data_path and "influence" in fc.data_path and any(k.co[1] > 0.5 for k in fc.keyframe_points)
                for fc in (bag.fcurves if bag else ()))
    if not holds:
        continue
    for ob in objs:
        ad = ob.animation_data or ob.animation_data_create()
        sl = CT.slot_of(act, ob)
        ad.action = act if sl else None
        if sl:
            ad.action_slot = sl
    end = int(math.ceil(CT.last_key(act, arms)))
    # «не той стороной»: место магазина в кисти в этих клипах крутится (ключи mag.L 1 → 41 и знак кватерниона после
    # разворота) — путь кисти считается для магазина, лежащего в кисти как в позе 41
    muted = []
    if "Wrong" in act.name:
        for fc in CT.bag_of(act, arms).fcurves:
            if 'pose.bones["mag.L"]' in fc.data_path:
                fc.mute = True
                muted.append(fc)
        arms.pose.bones["mag.L"].matrix_basis = CT.pose_table(bpy.data.actions[CT.POSES], arms)["mag"]["mag.L"]
    rec = {"end": end, "E": {}, "infl": {}}
    for f in range(1, end + 1):
        S.frame_set(f)
        pb = wr.pose.bones["Magazine_Control"]
        rec["E"][f] = [list(r) for r in (pb.matrix @ rest.inverted())]
        rec["infl"][f] = pb.constraints["В левой кисти"].influence
    for fc in muted:
        fc.mute = False
    out[act.name[len(CT.PREFIX):]] = rec
    print("REC", act.name, end, flush=True)
Path(OUT).write_text(json.dumps(out), encoding="utf-8", newline="\n")
