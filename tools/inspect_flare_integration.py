"""Read-only inspection of the preserved flare master and VERAS FPS arm source."""
import json
import sys
from pathlib import Path
import bpy
import addon_utils

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_asset_src" / "flare_pistol_codex" / "integration"
OUT.mkdir(parents=True, exist_ok=True)
MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "flare"
if MODE == "arms":
    source = Path("E:/Models Blender/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия/Перезарядка v01 (Claude)/VERAS54_Reload_Full_v05.blend")
else:
    bpy.context.preferences.use_preferences_save = False
    addon_utils.enable("bl_ext.blender_org.ucupaint", default_set=True)
    source = ROOT / "_asset_src" / "flare_pistol_codex" / "models" / "launcher" / "flare_pistol_codex_ucupaint_worn_v01.blend"
bpy.ops.wm.open_mainfile(filepath=str(source))
bpy.context.scene.frame_set(1)
dg = bpy.context.evaluated_depsgraph_get()
objects = []
for ob in bpy.context.scene.objects:
    item = dict(name=ob.name, type=ob.type, parent=ob.parent.name if ob.parent else None,
                parent_type=ob.parent_type, parent_bone=ob.parent_bone,
                location=list(ob.matrix_world.translation), matrix=[list(row) for row in ob.matrix_world],
                hidden=ob.hide_render, properties={k: str(ob[k]) for k in ob.keys()},
                constraints=[dict(name=c.name, type=c.type, target=getattr(getattr(c, "target", None), "name", ""),
                                  subtarget=getattr(c, "subtarget", "")) for c in ob.constraints])
    if ob.animation_data:
        item["action"] = ob.animation_data.action.name if ob.animation_data.action else None
        item["drivers"] = [dict(path=f.data_path, index=f.array_index, expression=f.driver.expression,
                                 variables=[dict(name=v.name, target=[dict(id=getattr(t.id, "name", ""), path=t.data_path) for t in v.targets]) for v in f.driver.variables]) for f in ob.animation_data.drivers]
    if ob.type == "MESH":
        ev = ob.evaluated_get(dg)
        mesh = ev.to_mesh()
        mesh.calc_loop_triangles()
        item.update(vertices=len(ob.data.vertices), triangles=len(mesh.loop_triangles),
                    bounds=[[min((ev.matrix_world @ v.co)[i] for v in mesh.vertices) for i in range(3)],
                            [max((ev.matrix_world @ v.co)[i] for v in mesh.vertices) for i in range(3)]],
                    materials=[m.name if m else None for m in ob.data.materials],
                    mods=[dict(name=m.name, type=m.type, target=getattr(getattr(m, "object", None), "name", "")) for m in ob.modifiers],
                    groups=[g.name for g in ob.vertex_groups])
        ev.to_mesh_clear()
    elif ob.type == "ARMATURE":
        item["bones"] = [dict(name=b.name, parent=b.parent.name if b.parent else None,
                              head=list(b.head_local), tail=list(b.tail_local), deform=b.use_deform,
                              matrix=[list(row) for row in ob.pose.bones[b.name].matrix],
                              constraints=[dict(type=c.type, target=getattr(getattr(c, "target", None), "name", ""),
                                                subtarget=getattr(c, "subtarget", ""), chain_count=getattr(c, "chain_count", 0)) for c in ob.pose.bones[b.name].constraints]) for b in ob.data.bones]
    objects.append(item)
report = dict(source=str(source), frame=bpy.context.scene.frame_current,
              camera=bpy.context.scene.camera.name if bpy.context.scene.camera else None,
              objects=objects, actions=[dict(name=a.name, frames=list(a.frame_range)) for a in bpy.data.actions])
path = OUT / f"inspect_{MODE}.json"
path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print("INSPECT", str(path), "objects", len(objects), flush=True)
