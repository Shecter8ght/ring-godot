"""Optional read-only Blender probe for the target character and representative FBX."""
import bpy
import json
from pathlib import Path

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[1]
persona = Path(r"D:\ПРОГРАММЫ\Blender 5\Projects\Persona.blend")
files = json.loads((AUDIT / "all_animations.json").read_text(encoding="utf-8"))["files"]
representatives = {}
for file in files:
    representatives.setdefault(file["sourcePack"], ROOT / file["path"])
SOURCES = [persona, *representatives.values()]
RESULT = []
for source in SOURCES:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    try:
        if source.suffix == ".blend":
            bpy.ops.wm.open_mainfile(filepath=str(source))
        else:
            bpy.ops.import_scene.fbx(filepath=str(source), use_anim=True)
        arms = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
        meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
        RESULT.append({
            "path": str(source), "armatures": [{
                "name": arm.name,
                "objectScale": list(arm.scale),
                "boneCount": len(arm.data.bones),
                "rootBones": [bone.name for bone in arm.data.bones if bone.parent is None],
                "boneNames": [bone.name for bone in arm.data.bones],
            } for arm in arms],
            "meshCount": len(meshes),
            "actions": [{"name": action.name, "frameRange": list(action.frame_range)} for action in bpy.data.actions],
        })
    except Exception as error:
        RESULT.append({"path": str(source), "error": str(error)})

(AUDIT / "rig_probe.json").write_text(json.dumps(RESULT, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("RIG_PROBE_WRITTEN", AUDIT / "rig_probe.json")
