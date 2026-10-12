"""Author and inspect the saved Mk II art asset in Blender; no game import."""
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_asset_src/grenade_codex'
SOURCE = Path('E:/Models Blender/From Scenario/Grenade/Grenade.blend')
MODE = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else 'source-preview'


def aim(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat('-Z', 'Y').to_euler()


def setup_studio(center):
    scene = bpy.context.scene
    for ob in list(scene.objects):
        if ob.type in {'CAMERA', 'LIGHT'}:
            bpy.data.objects.remove(ob, do_unlink=True)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    pref = bpy.context.preferences.addons['cycles'].preferences
    pref.compute_device_type = 'OPTIX'
    pref.get_devices()
    for dev in pref.devices:
        dev.use = dev.type == 'OPTIX'
    scene.cycles.device = 'GPU'
    print('DEVICES', [(d.name, d.type, d.use) for d in pref.devices], flush=True)
    scene.world = bpy.data.worlds.new('Studio - neutral ambient')
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (.15, .18, .22, 1)
    bg.inputs['Strength'].default_value = .35
    for name, pos, energy, size, color in [
        ('Key softbox', (-.17, -.22, .24), 1.15, .15, (1,.92,.82)),
        ('Fill softbox', (.17, -.08, .15), .55, .12, (.82,.89,1)),
        ('Rim strip', (.04, .19, .20), 1.65, .08, (1,1,1)),
    ]:
        data = bpy.data.lights.new(name, 'AREA')
        data.energy, data.size, data.color = energy, size, color
        ob = bpy.data.objects.new(name, data)
        scene.collection.objects.link(ob)
        ob.location = Vector(center) + Vector(pos)
        aim(ob, Vector(center) + Vector((0,0,.055)))
    camera = bpy.data.objects.new('Camera - inspection', bpy.data.cameras.new('Camera - inspection'))
    scene.collection.objects.link(camera)
    camera.data.type = 'ORTHO'
    camera.data.clip_start = .001
    camera.data.clip_end = 100
    scene.camera = camera
    scene.render.resolution_x, scene.render.resolution_y = 1050, 1300
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.view_settings.exposure = .10
    return camera


def shot(name, center, offset=(.17,-.28,.18), target=(0,0,.057), scale=.167):
    scene = bpy.context.scene
    scene.camera.location = Vector(center) + Vector(offset)
    aim(scene.camera, Vector(center)+Vector(target))
    scene.camera.data.ortho_scale = scale
    folder = OUT / 'previews'
    folder.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(folder / (name+'.png'))
    print('RENDER_BEGIN', name, flush=True)
    bpy.ops.render.render(write_still=True)
    print('RENDER_OK', name, flush=True)


def source_preview():
    bpy.context.preferences.use_preferences_save = False
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    center = bpy.data.objects['MK2_Grenade'].location.copy()
    setup_studio(center)
    shot('source_original', center)
    neutral = bpy.data.materials.new('Neutral geometry inspection')
    neutral.diffuse_color = (.23,.25,.28,1)
    neutral.use_nodes = True
    p = neutral.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (.23,.25,.28,1)
    p.inputs['Metallic'].default_value = .2
    p.inputs['Roughness'].default_value = .32
    bpy.context.view_layer.material_override = neutral
    shot('source_geometry', center)
    shot('source_geometry_head', center, (.09,-.14,.21), (0,0,.097), .077)
    print('SOURCE_PREVIEW_OK', flush=True)


if __name__ == '__main__':
    source_preview()
