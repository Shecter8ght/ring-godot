"""Open the delivered studio in a separate Blender window, with native layers."""
import importlib.util
from pathlib import Path

import bpy

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('grenade_texture',HERE/'texture_grenade_codex.py')
T=importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
T.P.native()  # Enable only in this instance; saving user preferences is disabled.
FILE=Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v06/Grenade_MkII_Studio_v06.blend')
if not FILE.is_file():
    FILE=Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v06_Progress/Grenade_MkII_UCUPaint_Codex_v06.blend')
assert FILE.is_file(),FILE
bpy.ops.wm.open_mainfile(filepath=str(FILE))
scene=bpy.context.scene
scene.frame_set(1)
layer=scene.view_layers[0]
for ob in layer.objects:
    ob.select_set(False,view_layer=layer)
body=bpy.data.objects['GrenadeBody']
body.select_set(True,view_layer=layer)
layer.objects.active=body
scene.cycles.device='GPU'
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX'
prefs.get_devices()
for device in prefs.devices:
    device.use=device.type=='OPTIX'
print('DELIVERED_GRENADE_OPENED',FILE,flush=True)

