"""Open the delivered art master in a separate Blender window, with native layers."""
import importlib.util
from pathlib import Path

import bpy

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('grenade_texture',HERE/'texture_grenade_codex.py')
T=importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
T.P.native()  # Enable only in this instance; saving user preferences is disabled.
FILE=Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v06/Grenade_MkII_UCUPaint_Codex_v06.blend')
if not FILE.is_file():
    FILE=Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v06_Progress/Grenade_MkII_UCUPaint_Codex_v06.blend')
assert FILE.is_file(),FILE
bpy.ops.wm.open_mainfile(filepath=str(FILE))
bpy.context.scene.frame_set(1)
for ob in bpy.context.selected_objects:
    ob.select_set(False)
body=bpy.data.objects['GrenadeBody']
body.select_set(True)
bpy.context.view_layer.objects.active=body
print('DELIVERED_GRENADE_OPENED',FILE,flush=True)

