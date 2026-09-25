"""Export the owner's Persona mesh; keep the source .blend unchanged.

Run Blender headless with --python tools/export_persona_model.py, then run Godot import.
"""

import bmesh
import bpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"D:\ПРОГРАММЫ\Blender 5\Projects\Persona.blend")
OUTPUT = ROOT / "assets/models/characters/persona_animated.glb"

bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
arm = next(obj for obj in bpy.data.objects if obj.type == "ARMATURE")
skin = bpy.data.objects["Human"]
skin.data = skin.data.copy()
mesh = bmesh.new()
mesh.from_mesh(skin.data)
# У исходной сетки скрытая под брюками часть растягивается при импорте в Godot.
bmesh.ops.delete(mesh, geom=[vertex for vertex in mesh.verts if vertex.co.z < 1.03], context="VERTS")
mesh.to_mesh(skin.data)
mesh.free()

keep = {
    "Human", "Human.eyebrow002", "Human.high-poly.001", "Human.male_casualsuit05",
    "Human.rehmanpolanski_beard_viking", "Human.rehmanpolanski_moustache_viking",
    "Human.shoes03", "Human.short04", "Human.teeth_shape05", "Human.tongue01.001",
}
arm.animation_data_clear()
for obj in bpy.data.objects:
    obj.select_set(obj == arm or obj.name in keep)
bpy.context.view_layer.objects.active = arm
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(OUTPUT), export_format="GLB", use_selection=True, export_animations=False)
print("EXPORTED", OUTPUT, OUTPUT.stat().st_size)
