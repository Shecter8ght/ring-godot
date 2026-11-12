"""Сто ценных находок: готовые PBR-ассеты и детали проверенных моделей.

Blender --background --factory-startup --python tools/build_valuable_loot.py.
Источники и выбор деталей — data/valuable_loot_assets.json. Результат в метрах;
никаких процедурных заменителей вещей в игре. Закрытая упаковка получает этикетку.
"""
import json
import sys
from pathlib import Path
from mathutils import Vector
import bpy

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'assets/items/models/valuable'
RAW = ROOT / '_asset_src/loot_value'
SPECS = json.loads((ROOT / 'data/valuable_loot_assets.json').read_text(encoding='utf8'))
OUT.mkdir(parents=True, exist_ok=True)
manifest = json.loads((OUT / 'manifest.json').read_text(encoding='utf8')) if (OUT / 'manifest.json').exists() else {}
only = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []


def import_source(source):
    if source.startswith('weapon:'):
        path = ROOT / source[7:]
        bpy.ops.import_scene.gltf(filepath=str(path))
        return str(path.relative_to(ROOT)), 'RING: existing approved geometry'
    if source == 'phone':
        folder = RAW / source
        with bpy.data.libraries.load(str(folder / 'samsung-sgh-i677.blend'), link=False) as (a, b):
            b.objects = a.objects
        for obj in b.objects:
            if obj and obj.type == 'MESH':
                bpy.context.collection.objects.link(obj)
        # Исходник Blender 2.7 использовал старый материал: сохранить UV и фототекстуру.
        image = bpy.data.images.load(str(folder / 'samsung-sgh-i677-redacted.png'))
        mat = bpy.data.materials.new('Phone photo PBR')
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Roughness'].default_value = .36
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = image
        mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        for o in bpy.context.scene.objects:
            if o.type == 'MESH':
                o.data.materials.clear(); o.data.materials.append(mat)
        return 'https://opengameart.org/content/smartphone-1', 'CC0 1.0 — Brian MacIntosh'
    if source == 'flare_gun':
        folder = RAW / source / 'Guns&Explosives/Flare_Gun'
        bpy.ops.import_scene.fbx(filepath=str(folder / 'FlareGun.fbx'))
        mat = bpy.data.materials.new('FlareGun PBR'); mat.use_nodes = True
        nodes = mat.node_tree.nodes; links = mat.node_tree.links
        bsdf = nodes.get('Principled BSDF')
        for suffix, channel in [('Base_Color', 'Base Color'), ('Roughness', 'Roughness'), ('Metallic', 'Metallic')]:
            tex = nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(str(folder / ('FlareGun_' + suffix + '.png')))
            if suffix != 'Base_Color': tex.image.colorspace_settings.name = 'Non-Color'
            links.new(tex.outputs['Color'], bsdf.inputs[channel])
        # DirectX normal: переворачиваем зелёный канал для OpenGL Godot.
        tex = nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(str(folder / 'FlareGun_Normal_DirectX.png')); tex.image.colorspace_settings.name = 'Non-Color'
        split = nodes.new('ShaderNodeSeparateColor'); combine = nodes.new('ShaderNodeCombineColor')
        invert = nodes.new('ShaderNodeMath'); invert.operation = 'SUBTRACT'; invert.inputs[0].default_value = 1
        normal = nodes.new('ShaderNodeNormalMap')
        links.new(tex.outputs['Color'], split.inputs['Color']); links.new(split.outputs['Red'], combine.inputs['Red'])
        links.new(split.outputs['Green'], invert.inputs[1]); links.new(invert.outputs[0], combine.inputs['Green'])
        links.new(split.outputs['Blue'], combine.inputs['Blue']); links.new(combine.outputs['Color'], normal.inputs['Color']); links.new(normal.outputs['Normal'], bsdf.inputs['Normal'])
        for o in bpy.context.scene.objects:
            if o.type == 'MESH': o.data.materials.clear(); o.data.materials.append(mat)
        return 'https://3dmodelscc0.itch.io/free-cc0-guns-explosives-pack', 'CC0 1.0 — 3dmodelscc0'
    folder = next(p for p in [RAW / source, ROOT / '_asset_src/loot' / source, ROOT / '_asset_src/shelter/external' / source] if p.exists())
    assert 'CC0' in (folder / 'license.txt').read_text(encoding='utf8')
    bpy.ops.import_scene.gltf(filepath=str(folder / (source + '.gltf')))
    return 'https://polyhaven.com/a/' + source, 'CC0 1.0 — Poly Haven'


def sticker(item, objects, lo, hi):
    path = RAW / 'labels' / (item + '.png')
    if not path.exists(): return
    # Наклейка на верхнюю грань настоящей транспортной коробки/футляра.
    z = hi.z + .00035
    cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
    w, h = (hi.x - lo.x) * .7, (hi.y - lo.y) * .55
    mesh = bpy.data.meshes.new('Printed label UV')
    mesh.from_pydata([(cx-w/2,cy-h/2,z),(cx+w/2,cy-h/2,z),(cx+w/2,cy+h/2,z),(cx-w/2,cy+h/2,z)], [], [(0,1,2,3)])
    uv = mesh.uv_layers.new()
    for i, xy in enumerate([(0,0),(1,0),(1,1),(0,1)]): uv.data[i].uv = xy
    o = bpy.data.objects.new('Factory_label', mesh); bpy.context.collection.objects.link(o)
    mat = bpy.data.materials.new('Printed paper'); mat.use_nodes = True
    node = mat.node_tree.nodes.new('ShaderNodeTexImage'); node.image = bpy.data.images.load(str(path))
    bsdf = mat.node_tree.nodes.get('Principled BSDF'); bsdf.inputs['Roughness'].default_value = .85
    mat.node_tree.links.new(node.outputs['Color'], bsdf.inputs['Base Color']); o.data.materials.append(mat)
    objects.append(o)


for item, spec in SPECS.items():
    if only and item not in only: continue
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    source, license_name = import_source(spec['source'])
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if 'selector' in spec:
        objects = [o for o in objects if o.name in spec['selector']]
        assert objects, (item, spec['selector'])
    if spec['source'] == 'metal_toolbox': objects = [o for o in objects if 'handle_latch' not in o.name]
    if spec.get('keep_island') == 'largest':
        # сетка из нескольких деталей (вкладыши рамки АСТЕН-919): остаётся самая подробная — блок запирания
        import bmesh
        for o in objects:
            o.data = o.data.copy()
            bm = bmesh.new(); bm.from_mesh(o.data)
            # связность — по совпадающим вершинам: после импорта glTF сетка разрезана по швам развёртки
            root = {}
            def find(k):
                while root[k] != k:
                    root[k] = root[root[k]]; k = root[k]
                return k
            first = {}
            for f in bm.faces:
                root[f.index] = f.index
            for f in bm.faces:
                for v in f.verts:
                    key = (round(v.co.x, 5), round(v.co.y, 5), round(v.co.z, 5))
                    if key in first:
                        root[find(f.index)] = find(first[key])
                    else:
                        first[key] = f.index
            groups = {}
            for f in bm.faces:
                groups.setdefault(find(f.index), []).append(f)
            keep = max(groups.values(), key=len)
            bmesh.ops.delete(bm, geom=[f for g in groups.values() if g is not keep for f in g], context='FACES')
            bm.to_mesh(o.data); bm.free()
    points = [o.matrix_world @ Vector(v) for o in objects for v in o.bound_box]
    lo = Vector([min(v[i] for v in points) for i in range(3)]); hi = Vector([max(v[i] for v in points) for i in range(3)])
    size = hi - lo
    factor = float(spec.get('max_dimension', .16 if spec['source']=='phone' else (.29 if spec['source']=='flare_gun' else max(size)))) / max(size)
    # Разные штатные размеры упаковки: плоские платы, длинные модули, объёмные наборы.
    axes = Vector([v / size[i] for i,v in enumerate(spec['dimensions'])]) if 'dimensions' in spec else Vector((factor,factor,factor))
    offset = Vector(((lo.x+hi.x)/2, (lo.y+hi.y)/2, lo.z))
    total = sum(len(p.vertices)-2 for o in objects for p in o.data.polygons)
    for o in objects:
        matrix = o.matrix_world.copy(); o.data = o.data.copy(); o.parent = None
        for v in o.data.vertices:
            point = matrix @ v.co - offset
            v.co = Vector((point.x*axes.x,point.y*axes.y,point.z*axes.z))
        o.matrix_world.identity()
        if o.data.shape_keys:
            o.shape_key_clear()
        if total > 6200:
            bpy.context.view_layer.objects.active = o
            mod = o.modifiers.new('World loot budget', 'DECIMATE'); mod.ratio = 6200 / total
            bpy.ops.object.modifier_apply(modifier=mod.name)
    for o in list(bpy.context.scene.objects):
        if o not in objects: bpy.data.objects.remove(o, do_unlink=True)
    size = Vector((size.x*axes.x,size.y*axes.y,size.z*axes.z))
    if spec.get('label'): sticker(item, objects, Vector((-size.x/2,-size.y/2,0)), Vector((size.x/2,size.y/2,size.z)))
    for image in bpy.data.images:
        if image.size[0] > 1024: image.scale(1024,1024)
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.ops.wm.save_as_mainfile(filepath=str(RAW / (item+'.blend')))
    bpy.ops.export_scene.gltf(filepath=str(OUT / (item+'.glb')), export_format='GLB', use_selection=True,
        export_yup=True, export_animations=False, export_image_format='JPEG', export_jpeg_quality=90)
    manifest[item] = {'source':source,'license':license_name,'triangles':sum(len(p.vertices)-2 for o in objects for p in o.data.polygons),
        'size':[round(size.x,4),round(size.z,4),round(size.y,4)], 'packaged':bool(spec.get('label'))}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('VALUABLE',item,manifest[item]['triangles'],flush=True)
