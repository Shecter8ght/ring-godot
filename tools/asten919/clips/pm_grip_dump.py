"""АСТЕН-919, клипы рук: хват пистолета владельца с ПМ (_asset_src/pm_game/anim/PM_FPS_Grip_v03.blend, действие
PM_Stances: кадр 1 — наискосок, 11 — от бедра, 21 — прицел) → _asset_src/asten919/anim/pm_grip.json: поза костей рук
(matrix_basis и матрицы в осях арматуры), покой костей прежних рук (до правки кистей v14) и кость рамки ПМ.
Оси ПМ (кость Frame): +X — левая сторона стрелка, −Y — дуло, +Z — вверх; начало — рукоятка.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python tools/asten919/clips/pm_grip_dump.py
"""
import json
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "_asset_src/pm_game/anim/PM_FPS_Grip_v03.blend"
OUT = ROOT / "_asset_src/asten919/anim/pm_grip.json"
bpy.ops.wm.open_mainfile(filepath=str(SRC))
S = bpy.context.scene
arms = bpy.data.objects["FPS_ArmsRig"]
M = lambda m: [[round(v, 6) for v in row] for row in m]
rec = dict(source=str(SRC), frames={}, rest={b.name: dict(m=M(b.matrix_local), len=round(b.length, 6),
                                                         parent=b.parent.name if b.parent else None)
                                             for b in arms.data.bones},
           rotation_mode={pb.name: pb.rotation_mode for pb in arms.pose.bones})
for name, f in (("carry", 1), ("ready", 11), ("ads", 21)):
    S.frame_set(f)
    bpy.context.view_layer.update()
    rec["frames"][name] = dict(basis={pb.name: M(pb.matrix_basis) for pb in arms.pose.bones},
                               pose={pb.name: M(pb.matrix) for pb in arms.pose.bones},
                               tail={pb.name: [round(v, 6) for v in pb.tail] for pb in arms.pose.bones})
rec["arm_world"] = M(arms.matrix_world)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8", newline="\n")
fr = rec["frames"]["ready"]["pose"]
print("PM_DUMP кости", len(rec["rest"]), "Frame", [round(v, 4) for v in (fr["Frame"][0][3], fr["Frame"][1][3], fr["Frame"][2][3])],
      "hand.R", [round(fr["hand.R"][i][3], 4) for i in range(3)], "hand.L", [round(fr["hand.L"][i][3], 4) for i in range(3)])
for b in ("hand.R", "palm.02.R", "f_middle.01.R", "f_middle.02.R", "f_middle.03.R", "thumb.01.R", "f_index.01.R"):
    print("PM_DUMP rest len", b, rec["rest"][b]["len"])
