"""Отладка: магазин в клипе по кадрам (только чтение)."""
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clip_tools_v14 as CT  # noqa: E402

arms, wr = CT.rigs()
act = bpy.data.actions["VERAS54_Reload_Tactical"]
for ob in (arms, wr, bpy.data.objects["VERAS54"], bpy.data.objects["Magazine"]):
    ad = ob.animation_data or ob.animation_data_create()
    sl = CT.slot_of(act, ob)
    ad.action = act if sl else None
    if sl:
        ad.action_slot = sl
rest = wr.data.bones["Magazine_Control"].matrix_local
S = bpy.context.scene
for f in (1, 16, 18, 20, 22, 25, 30, 50, 52, 53, 54, 55, 57, 58, 60):
    S.frame_set(f)
    pb = wr.pose.bones["Magazine_Control"]
    E = pb.matrix @ rest.inverted()
    print("DBG", f, round(pb.constraints["В левой кисти"].influence, 2), [round(v * 1000, 1) for v in E.translation],
          round(E.to_quaternion().angle * 57.3, 1), [round(v * 1000, 1) for v in pb.matrix.translation], flush=True)
