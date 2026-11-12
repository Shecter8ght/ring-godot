"""Готовые CC0-модели переносимого лута → GLB в метрах с PBR, опора на Y=0.

Новая геометрия не создаётся: импорт Poly Haven, удаление вариантов, бюджет сетки.
Исходники: _asset_src/shelter/external и python tools/fetch_polyhaven_models.py loot
circuit_board pliers screwdriver measuring_tape_01 cross_pein_hammer cassette_player
vintage_video_camera --res 1k. Запуск Blender --background --factory-startup --python.
"""
import json
from pathlib import Path
import bpy
from mathutils import Vector
from math import pi

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'assets/items/models/loot'
OUT.mkdir(parents=True, exist_ok=True)
SOURCES = {
    'circuit_board': 'circuit_board', 'pliers': 'pliers', 'screwdriver': 'screwdriver',
    'hammer': 'cross_pein_hammer',
    'pipe_wrench': 'pipe_wrench', 'multimeter': 'retro_multimeter', 'oil_tin': 'oil_tin',
    'thermos': 'modified_thermos', 'kettle': 'vintage_electric_kettle',
    'radio_transceiver': 'vintage_radio_transceiver', 'cassette_player': 'cassette_player',
    'video_camera': 'vintage_video_camera', 'binoculars': 'binoculars',
    'clipboard': 'clipboard',
    'empty_jerrycan': 'metal_jerrycan_green', 'medical_case': 'medical_box',
    'metal_toolbox': 'metal_toolbox', 'bench_vice': 'bench_vice_01',
    'desk_lamp': 'desk_lamp_arm_01', 'junction_box': 'utility_box_01', 'power_unit': 'power_box_01',
}
manifest = {}
for item, source in SOURCES.items():
    folder = ROOT / '_asset_src/shelter/external' / source
    if not folder.exists():
        folder = ROOT / '_asset_src/loot' / source
    license_text = (folder / 'license.txt').read_text(encoding='utf-8')
    assert 'CC0' in license_text, source
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.ops.import_scene.gltf(filepath=str(folder / (source + '.gltf')))
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    # Служебная сфера в исходнике тисков не является частью предмета.
    objects = [o for o in objects if 'Icosphere' not in o.name]
    if item == 'radio_transceiver':
        # В исходнике рядом разложены отдельные кабели, ключ Морзе и микрофон.
        objects = [o for o in objects if o.name in ['vintage_radio_transceiver', 'vintage_radio_transceiver_dial']]
    if item == 'metal_toolbox':
        objects = [o for o in objects if 'handle_latch' not in o.name]
    # Ручной инструмент и настенные часы лежат на опоре, а не балансируют на ребре.
    if item in ['pliers', 'screwdriver', 'hammer', 'pipe_wrench', 'wall_clock', 'cassette_player']:
        from mathutils import Matrix
        turn = Matrix.Rotation(-pi * .5 if item == 'wall_clock' else pi * .5, 4, 'X')
        for o in objects:
            o.matrix_world = turn @ o.matrix_world
    points = [o.matrix_world @ Vector(v) for o in objects for v in o.bound_box]
    lo = Vector([min(v[i] for v in points) for i in range(3)])
    hi = Vector([max(v[i] for v in points) for i in range(3)])
    offset = Vector(((lo.x + hi.x) * .5, (lo.y + hi.y) * .5, lo.z))
    total = sum(len(p.vertices) - 2 for o in objects for p in o.data.polygons)
    for o in objects:
        matrix = o.matrix_world.copy()
        o.data = o.data.copy()
        o.parent = None
        for v in o.data.vertices:
            v.co = matrix @ v.co - offset
        o.matrix_world.identity()
        if total > 6500:
            bpy.context.view_layer.objects.active = o
            mod = o.modifiers.new('Loot budget', 'DECIMATE')
            mod.ratio = 6500 / total
            bpy.ops.object.modifier_apply(modifier=mod.name)
    for o in list(bpy.context.scene.objects):
        if o not in objects:
            bpy.data.objects.remove(o, do_unlink=True)
    size = hi - lo
    # Компактная распределительная коробка: та же готовая сетка с масштабом 32 см.
    if item == 'junction_box':
        factor = .32 / size.z
        for o in objects:
            for v in o.data.vertices:
                v.co *= factor
        size *= factor
    for image in bpy.data.images:
        limit = 512 if max(size) < .22 else 1024
        if image.size[0] > limit:
            image.scale(limit, limit)
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.ops.wm.save_as_mainfile(filepath=str(folder / 'loot_game.blend'))
    bpy.ops.export_scene.gltf(filepath=str(OUT / (item + '.glb')), export_format='GLB',
        use_selection=True, export_yup=True, export_animations=False,
        export_image_format='JPEG', export_jpeg_quality=90)
    tris = sum(len(p.vertices) - 2 for o in objects for p in o.data.polygons)
    manifest[item] = {'source': 'https://polyhaven.com/a/' + source, 'license': 'CC0 1.0',
        'triangles': tris, 'size': [round(size.x, 4), round(size.z, 4), round(size.y, 4)]}
    print('LOOT', item, manifest[item]['size'], tris, flush=True)
(OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
