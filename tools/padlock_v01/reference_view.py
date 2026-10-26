"""Unsaved comparison view approximating the supplied Fab front 3/4 photograph."""
import argparse
import sys
from pathlib import Path
import bpy
from mathutils import Vector

WORK=Path(__file__).resolve().parents[2]/'_asset_src'/'padlock_v01'
p=argparse.ArgumentParser();p.add_argument('--revision',choices=['v04','v05'],default='v05')
args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
bpy.ops.wm.open_mainfile(filepath=str(WORK/'models'/('padlock_'+args.revision+'_textured.blend')))
scene=bpy.context.scene;camera=bpy.data.objects['front_34'];target=Vector((0,0,.0595))
camera.location=target+(camera.location-target)*1.25
camera.data.type='PERSP';camera.data.lens=75;camera.data.sensor_width=36;camera.data.dof.use_dof=False
camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();scene.camera=camera
floor=bpy.data.objects.get('Studio_ground')
if floor:floor.is_shadow_catcher=True
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=64;scene.cycles.use_denoising=False
scene.render.resolution_x=1280;scene.render.resolution_y=720;scene.render.resolution_percentage=100
scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
scene.render.filepath=str(WORK/'checks'/('reference_view_'+args.revision+'_raw.png'))
bpy.ops.render.render(write_still=True)
print('UNSAVED_REFERENCE_VIEW',scene.render.filepath)
