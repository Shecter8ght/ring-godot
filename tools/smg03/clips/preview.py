"""ИЗЛОМ-45, клипы рук: быстрые снимки (Workbench, текстуры) — из камеры FPS и сбоку справа / слева / снизу; для клипа —
кадры по списку. Самопроверка агента, владельцу — файл .blend.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <файл.blend> --python tools/smg03/clips/preview.py -- <папка> [кадр,кадр…] [виды: fps,right,left,below,top]
"""
import sys
from pathlib import Path

import bpy
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
out = Path(a[0])
frames = [int(x) for x in a[1].split(',')] if len(a) > 1 and a[1] else [bpy.context.scene.frame_current]
views = a[2].split(',') if len(a) > 2 else ['fps', 'right', 'left', 'below']
out.mkdir(parents=True, exist_ok=True)
S = bpy.context.scene
S.render.engine = 'BLENDER_WORKBENCH'
S.display.shading.light = 'STUDIO'
S.display.shading.color_type = 'RANDOM' if '--clay' in sys.argv else 'TEXTURE'
S.display.shading.show_cavity = True
S.display.shading.show_shadows = False
S.render.resolution_x, S.render.resolution_y = 1280, 720
S.render.film_transparent = False
fps = bpy.data.objects.get('FPS • Camera')
cam = bpy.data.objects.new('cam_preview', bpy.data.cameras.new('cam_preview'))
S.collection.objects.link(cam)
cam.data.lens = 50
cam.data.clip_start = 0.005
root = bpy.data.objects.get('SMG03')
for f in frames:
    S.frame_set(f)
    bpy.context.view_layer.update()
    c = root.matrix_world.translation.copy() if root else Vector((0, -0.4, 1.6))
    c = c + Vector((0.0, -0.08, 0.0))
    for v in views:
        if v == 'fps' and fps:
            S.camera = fps
        else:
            d = {'right': Vector((-1.0, 0.15, 0.25)), 'left': Vector((1.0, 0.15, 0.25)), 'below': Vector((-0.3, 0.2, -1.0)),
                 'top': Vector((0.0, 0.3, 1.0)), 'rhand': Vector((-1.0, 0.5, 0.1)), 'lhand': Vector((-0.6, -0.4, -0.6)),
                 'mag': Vector((0.8, -0.5, -0.35)), 'magr': Vector((-0.8, -0.3, -0.3))}[v]
            if v in ('mag', 'magr'):
                wrig = bpy.data.objects['SMG03_WeaponRig']
                cc = wrig.matrix_world @ wrig.pose.bones['Magazine_Control'].head
                cam.location = cc + d.normalized() * 0.42
                cam.rotation_euler = (cc - cam.location).to_track_quat('-Z', 'Y').to_euler()
                S.camera = cam
                S.render.filepath = str(out / f'f{f:03d}_{v}.png')
                bpy.ops.render.render(write_still=True)
                continue
            near = {'rhand': (bpy.data.objects['FPS_ArmsRig'], 'hand.R', 0.36), 'lhand': (bpy.data.objects['FPS_ArmsRig'], 'hand.L', 0.36)}
            cc, dist = c, 0.75
            if v in near:
                rig, bone, dist = near[v]
                cc = rig.matrix_world @ rig.pose.bones[bone].tail
            cam.location = cc + d.normalized() * dist
            cam.rotation_euler = (cc - cam.location).to_track_quat('-Z', 'Y').to_euler()
            S.camera = cam
            S.render.filepath = str(out / f'f{f:03d}_{v}.png')
            bpy.ops.render.render(write_still=True)
            continue
            cam.rotation_euler = (c - cam.location).to_track_quat('-Z', 'Y').to_euler()
            S.camera = cam
        S.render.filepath = str(out / f'f{f:03d}_{v}.png')
        bpy.ops.render.render(write_still=True)
print('PREVIEW', out, frames, views)
