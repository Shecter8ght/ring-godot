"""Осмотр скачанных моделей перед интеграцией: объекты, габариты (м), кадр спереди (+Z игры = -Y Blender).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/inspect_shelter_boiler_external.py -- <папка кадров>
"""
import bpy, json, sys, math
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
out = Path(sys.argv[sys.argv.index('--') + 1]) if '--' in sys.argv else ROOT/'_asset_src/shelter/inspect'
out.mkdir(parents=True, exist_ok=True)
records = json.loads((ROOT/'_asset_src/shelter/external_boiler_sources.json').read_text(encoding='utf-8'))
report = {}
scene = bpy.context.scene
scene.render.engine = 'BLENDER_WORKBENCH'
scene.render.resolution_x = scene.render.resolution_y = 256
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'TEXTURE'
for info in records:
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes): bpy.data.meshes.remove(block)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/'_asset_src/shelter/external'/info['id']/(info['id'] + '.gltf')))
    meshes = [o for o in scene.objects if o.type == 'MESH']
    objs = []
    for o in meshes:
        pts = [o.matrix_world @ Vector(v) for v in o.bound_box]
        lo = [min(p[i] for p in pts) for i in range(3)]; hi = [max(p[i] for p in pts) for i in range(3)]
        objs.append({'name': o.name, 'size': [round(hi[i] - lo[i], 3) for i in range(3)], 'center': [round((hi[i] + lo[i]) / 2, 3) for i in range(3)], 'tris': sum(len(p.vertices) - 2 for p in o.data.polygons)})
    pts = [o.matrix_world @ Vector(v) for o in meshes for v in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    size = hi - lo
    report[info['asset']] = {'id': info['id'], 'size_blender_xyz': [round(v, 3) for v in size], 'objects': objs}
    cam_data = bpy.data.cameras.new('cam'); cam_data.type = 'ORTHO'; cam_data.ortho_scale = max(size.x, size.z) * 1.15 + .01
    cam = bpy.data.objects.new('cam', cam_data); scene.collection.objects.link(cam)
    centre = (lo + hi) / 2
    cam.location = (centre.x, lo.y - 5, centre.z); cam.rotation_euler = (math.radians(90), 0, 0)
    scene.camera = cam
    scene.render.filepath = str(out/(info['asset'] + '.png'))
    bpy.ops.render.render(write_still=True)
    # вид сбоку, с +X Blender (= +X игры): где у предмета перед — видно по профилю
    cam_data.ortho_scale = max(size.y, size.z) * 1.15 + .01
    cam.location = (hi.x + 5, centre.y, centre.z); cam.rotation_euler = (math.radians(90), 0, math.radians(90))
    scene.render.filepath = str(out/(info['asset'] + '_side.png'))
    bpy.ops.render.render(write_still=True)
print('INSPECT_JSON ' + json.dumps(report, ensure_ascii=False))
(out/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
