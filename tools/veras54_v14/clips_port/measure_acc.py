"""ВЕРАС-54: обвесы на старой сетке (рукоятки ВАРН, фонарь, глушитель) и планки старой / новой сетки, мм в осях рига оружия.

Только чтение (копия файла клипов, ничего не сохраняется).
blender -b <копия файла клипов.blend> --factory-startup --python tools/veras54_v14/clips_port/measure_acc.py -- <VERAS54_Game_LP.blend> <выход.json>
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "clips"))
import clip_tools as CT  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
LP, OUT = args[0], args[1]
arms, wr = CT.rigs()
for ob in bpy.data.objects:
    if ob.animation_data and ob.type == "ARMATURE":
        ob.animation_data.action = None
for pb in wr.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
CT.show_variant("varn_v1", "30", True)
for c in ("Рукоятка ВАРН V2", "Глушитель"):
    bpy.data.collections[c].hide_viewport = False
wr.pose.bones["Suppressor_Control"].scale = (1, 1, 1)
bpy.context.view_layer.update()
W = wr.matrix_world.inverted()


def pts(o, M=None):
    dg = bpy.context.evaluated_depsgraph_get()
    e = o.evaluated_get(dg)
    me = e.to_mesh()
    M = M if M is not None else W @ e.matrix_world
    P = np.array([tuple(M @ v.co) for v in me.vertices]) * 1000
    e.to_mesh_clear()
    return P


def box(P):
    return dict(x=[round(P[:, 0].min(), 1), round(P[:, 0].max(), 1)], y=[round(P[:, 1].min(), 1), round(P[:, 1].max(), 1)],
                z=[round(P[:, 2].min(), 1), round(P[:, 2].max(), 1)])


out = {}
for n in ("Foregrip • varn_v1", "Foregrip • varn_v2", "Глушитель • supp_veras"):
    out[n] = box(pts(bpy.data.objects[n]))
light = np.concatenate([pts(o) for o in bpy.data.collections["Фонарь ДОЗОР (левая планка)"].objects if o.type == "MESH"])
out["Фонарь ДОЗОР (все детали)"] = box(light)
body = np.concatenate([pts(bpy.data.objects[n]) for n in ("Body_Polymer", "Body_Steel")])


def rails(P, lo=255, hi=440):
    """Низ цевья по X (шаг 5 мм) и левый борт: где они ровные — там планка."""
    rec = {}
    for x in range(lo, hi, 10):
        s = P[(P[:, 0] > x - 2.5) & (P[:, 0] < x + 2.5)]
        if not len(s):
            continue
        low = s[s[:, 2] < s[:, 2].min() + 1.0]
        lft = s[(s[:, 1] > s[:, 1].max() - 1.0)]
        rec[x] = dict(bottom=round(s[:, 2].min(), 1), bottom_half_w=round(np.abs(low[:, 1]).max(), 1),
                      left=round(s[:, 1].max(), 1), left_z=[round(lft[:, 2].min(), 1), round(lft[:, 2].max(), 1)])
    return rec


out["old_rails"] = rails(body)
with bpy.data.libraries.load(LP, link=False) as (src, dst):
    dst.objects = ["Receiver__Front", "Receiver__Body"]
new = np.concatenate([np.array([tuple(v.co) for v in o.data.vertices]) * 1000 for o in dst.objects])
out["new_rails"] = rails(new)
Path(OUT).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
print("ACC готово", flush=True)
