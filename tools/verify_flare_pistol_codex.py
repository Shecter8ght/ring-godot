"""Fresh-open verification of the editable source, not the baked export copy."""
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/"_asset_src/flare_pistol_codex/integration"
spec=importlib.util.spec_from_file_location("flare_animation",ROOT/"tools/animate_flare_pistol_codex.py")
anim=importlib.util.module_from_spec(spec)
spec.loader.exec_module(anim)
vx=anim.load_module("veras_helpers",ROOT/"tools/export_veras54.py")
if "--" in sys.argv and len(sys.argv)>sys.argv.index("--")+1:
    anim.MASTER=Path(sys.argv[sys.argv.index("--")+1])
bpy.ops.wm.open_mainfile(filepath=str(anim.MASTER))
rig=bpy.data.objects["FPS_ArmsRig"]
scene=bpy.context.scene
arms=[bpy.data.objects[name] for name in ["FPS_Arms_Right","FPS_Arms_Left"]]
for ob in arms: ob.data.calc_loop_triangles()
hands_triangles=sum(len(ob.data.loop_triangles) for ob in arms)
assert hands_triangles==4760
audit_path=WORK/"animation_audit.json"
audit=json.loads(audit_path.read_text(encoding="utf-8"))
audit["hands_triangles"]=hands_triangles
audit_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")
assert all(bpy.data.actions.get("Flare_Codex_"+clip) for clip in anim.CLIPS)
assert rig.pose.bones["hand.R"].constraints and rig.pose.bones["hand.L"].constraints
vx.assign(rig,bpy.data.actions["Flare_Codex_idle"])
scene.frame_set(1)
right_rest=rig.pose.bones["ik_hand.R"].matrix.copy()
frame_rest=rig.pose.bones["Frame"].matrix.copy()
vx.assign(rig,bpy.data.actions["Flare_Codex_reload_empty"])
samples={}
for f in [14,30,42,48,50,56,58,65,70,91,110,117,123,128,140,144,156]:
    scene.frame_set(f)
    bpy.context.view_layer.update()
    barrel=rig.pose.bones["Barrel"].matrix @ rig.data.bones["Barrel"].matrix_local.inverted()
    forward=(barrel.to_3x3() @ (anim.GUN.to_3x3() @ Vector((1,0,0)))).normalized()
    chamber=barrel @ (anim.GUN @ anim.PIVOTS["OldRound"])
    case=rig.pose.bones["OldRound"].matrix.translation
    frame_delta=rig.pose.bones["Frame"].matrix @ frame_rest.inverted()
    right_error=(rig.pose.bones["ik_hand.R"].matrix.translation-(frame_delta @ right_rest).translation).length
    assert right_error < .001, (f,"right grip drift",right_error)
    for pb in rig.pose.bones:
        assert all(math.isfinite(value) for row in pb.matrix for value in row)
    if f==42: assert (-forward).z < -.995, "Open chamber must point down"
    if f==58: assert (case-chamber).z < -.07, "Case must leave downward on second shake"
    if f in [48,56,123,140]: assert rig["left_hand_active"]==0., "Left hand must not shake or close the gun"
    if f in [30,91,110]: assert rig["left_hand_active"]==1.
    if rig["preview_new_green"]>.5 and f in [110,123,128,144,156]:
        assert not bpy.data.objects["LoadRoundGreen"].hide_viewport, "Inserted cartridge must remain in the chamber"
    if f>=70: assert bpy.data.objects["OldRoundRed"].hide_viewport, "Dropped case must leave the scene"
    samples[f]={"muzzle_direction":list(forward),"case_base":list(case),"chamber":list(chamber),
                "left_hand_active":rig["left_hand_active"],"right_grip_error_m":right_error}
report={"result":"PASS","source":str(anim.MASTER),"clips":list(anim.CLIPS),"samples":samples,
        "hand_controls":[pb.name for pb in rig.pose.bones if pb.name.startswith(("ik_","f_","thumb"))]}
(WORK/"editable_animation_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print("EDITABLE_ANIMATION_PASS",len(anim.CLIPS),"clips",len(samples),"fresh-open poses")
