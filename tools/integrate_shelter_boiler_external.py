"""Blender: CC0 модели Poly Haven котельной → GLB убежища (метры, опора на пол, перед на +Z).

Модели Poly Haven уже в реальном масштабе и смотрят на +Z игры, как собственные ассеты убежища,
поэтому масштаб меняется только там, где предмет встаёт на место прежнего и должен совпасть по высоте.
Лишние варианты в файле (чистые сапоги, второй бак, служебная сфера тисков) отбрасываются.
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/integrate_shelter_boiler_external.py
"""
import bpy, json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'assets/shelter/models'
BUDGET = 9000
# ассет → {include/exclude: подстроки имён объектов, height: подогнать высоту (м), collide: упрощённая коллизия}
SPEC = {
    'PH_Boots': {'include': ['dirt']},
    'PH_Vice': {'exclude': ['Icosphere']},
    'PH_TrashCan': {'include': ['rust']},
    'PH_CoffeeTable': {'height': .46, 'collide': True},
    'PH_DeskLamp': {'height': .6},
    'PH_Laptop': {'height': .26},
    'PH_Chair': {'collide': True}, 'PH_Bench': {'collide': True}, 'PH_MilitaryCrate': {'collide': True},
    'PH_Carton': {'collide': True}, 'PH_ToolCart': {'collide': True}, 'PH_ToolChest': {'collide': True},
    'PH_DrillPress': {'collide': True}, 'PH_Compressor': {'collide': True}, 'PH_PropaneTank': {'collide': True},
    'PH_UtilityBox': {'collide': True}, 'PH_FoldingStool': {'collide': True},
    'PH_PlasticCrate': {'collide': True}, 'PH_MetalDesk': {'collide': True}, 'PH_Stool': {'collide': True},
    'PH_LpgTank': {'collide': True}, 'PH_JerryCan': {'collide': True},
}
records = json.loads((ROOT/'_asset_src/shelter/external_boiler_sources.json').read_text(encoding='utf-8'))
manifest = json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
for info in records:
    asset = info['asset']
    spec = SPEC.get(asset, {})
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    folder = ROOT/'_asset_src/shelter/external'/info['id']
    bpy.ops.import_scene.gltf(filepath=str(folder/(info['id'] + '.gltf')))
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if 'include' in spec:
        objects = [o for o in objects if any(s in o.name for s in spec['include'])]
    if 'exclude' in spec:
        objects = [o for o in objects if not any(s in o.name for s in spec['exclude'])]
    bounds = [o.matrix_world @ Vector(v) for o in objects for v in o.bound_box]
    lo = Vector([min(v[i] for v in bounds) for i in range(3)])
    hi = Vector([max(v[i] for v in bounds) for i in range(3)])
    size = hi - lo
    scale = float(spec['height']) / size.z if 'height' in spec else 1.0
    offset = Vector(((lo.x + hi.x) * .5, (lo.y + hi.y) * .5, lo.z))
    for o in objects:
        o.data = o.data.copy()
        matrix = o.matrix_world.copy(); o.parent = None; o.matrix_world = matrix
        for v in o.data.vertices:
            v.co = (matrix @ v.co - offset) * scale
        o.matrix_world.identity()
        bpy.context.view_layer.objects.active = o
        triangles = sum(len(p.vertices) - 2 for p in o.data.polygons)
        if triangles > BUDGET:
            mod = o.modifiers.new('Interior triangle budget', 'DECIMATE'); mod.ratio = BUDGET / triangles
            bpy.ops.object.modifier_apply(modifier=mod.name)
    for o in list(bpy.context.scene.objects):
        if o not in objects:
            bpy.data.objects.remove(o, do_unlink=True)
    size *= scale
    # мелочь (до 0.6 м) — карты 512 px: с расстояния игрока разницы нет, репозиторий легче
    if max(size.x, size.y, size.z) < .6:
        for image in bpy.data.images:
            if image.size[0] > 512:
                image.scale(512, 512)
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'integrated.blend'))
    bpy.ops.export_scene.gltf(filepath=str(OUT/(asset + '.glb')), export_format='GLB', use_selection=True,
                              export_yup=True, export_animations=False, export_image_format='JPEG', export_jpeg_quality=88)
    tris = sum(len(p.vertices) - 2 for o in objects for p in o.data.polygons)
    collisions = [{'pos': [0, size.z * .5, 0], 'size': [size.x, size.z, size.y], 'yaw': 0}] if spec.get('collide') else []
    manifest[asset] = {'external': True, 'triangles': tris,
                       'bounds_m': [round(size.x, 4), round(size.z, 4), round(size.y, 4)], 'collisions': collisions}
    print('INTEGRATED', asset, manifest[asset]['bounds_m'], tris, flush=True)
(OUT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
