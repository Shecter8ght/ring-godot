"""Облегчённый готовый самолёт CC0 для дальнего пролёта, без новой геометрии."""
from pathlib import Path
import bpy

root = Path(__file__).resolve().parent.parent
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(root/'_asset_src/loot_value/plane/plane.glb'))
objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
total = sum(len(f.vertices)-2 for o in objects for f in o.data.polygons)
for obj in objects:
    if obj.data.shape_keys: obj.shape_key_clear()
    if total > 20000:
        bpy.context.view_layer.objects.active = obj
        mod = obj.modifiers.new('Distant aircraft', 'DECIMATE'); mod.ratio = 20000 / total
        bpy.ops.object.modifier_apply(modifier=mod.name)
for obj in list(bpy.context.scene.objects):
    if obj.type in ['CAMERA','LIGHT']: bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=str(root/'assets/items/models/valuable/supply_aircraft.glb'),
    export_format='GLB', export_animations=False, export_image_format='JPEG', export_jpeg_quality=90)
