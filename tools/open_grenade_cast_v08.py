"""Открыть выданную v08 в отдельном Blender, не сохранять настройки пользователя."""
import bpy,addon_utils,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILE=Path(os.environ.get('GRENADE_V08_OPEN','E:/Models Blender/From Scenario/Grenade/Codex_Texture_v08/Grenade_MkII_Studio_v08.blend'))
bpy.context.preferences.use_preferences_save=False
addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True)
bpy.ops.wm.open_mainfile(filepath=str(FILE))
scene=bpy.context.scene;scene.frame_set(1)
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for device in prefs.devices:device.use=device.type=='OPTIX'
scene.cycles.device='GPU';scene.cycles.preview_samples=32
layer=scene.view_layers[0]
for ob in layer.objects:ob.select_set(False,view_layer=layer)
root=bpy.data.objects['CTRL_Grenade'];root.select_set(True,view_layer=layer);layer.objects.active=root
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active;sp.shading.type='MATERIAL';sp.clip_start=.001;sp.overlay.show_overlays=False
            for prop in ['use_scene_lights','use_scene_world','use_scene_lights_render','use_scene_world_render']:
                if hasattr(sp.shading,prop):setattr(sp.shading,prop,True)
            sp.region_3d.view_perspective='CAMERA'
print('V08_DELIVERY_OPENED',FILE,flush=True)
