"""Принятая граната v08: отдельная игровая копия, bake high → low и glTF.

Blender --background --factory-startup --python-exit-code 1 --python tools/prepare_grenade_game.py -- build|bake|export|inspect|compare|audit
Исходник библиотеки только читается; вся выдача — внутри проекта.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys

import addon_utils
import bpy
from mathutils import Matrix, Vector, kdtree

ROOT = Path(__file__).resolve().parents[1]
SRC = Path('E:/Models Blender/WEAPONS/Grenade/Codex_Texture_v08/Grenade_MkII_UCUPaint_v08.blend')
WORK = ROOT / '_asset_src/grenade_game'
OUT = ROOT / 'assets/models/weapons/grenade'
PARTS = {'GrenadeBody': 8000, 'FuzeCasting': 2400, 'SafetyLever': 1200,
         'SafetyPin': 640, 'PullRing': 800, 'PinEyelet': 192, 'BottomPlug': 128}
GROUP = {name: ('body' if name == 'GrenadeBody' else 'mechanism') for name in PARTS}
SIZE = {'body': 2048, 'mechanism': 2048}
CENTER = Vector((0, 0, .045))
LP = WORK / 'Grenade_Game_LP.blend'
log = lambda *args: print('GRENADE_GAME', *args, flush=True)


def save_json(name, value):
    (WORK / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')


def source():
    bpy.context.preferences.use_preferences_save = False
    addon_utils.enable('bl_ext.blender_org.ucupaint', default_set=True)
    bpy.ops.wm.open_mainfile(filepath=str(SRC))
    bpy.context.scene.frame_set(1)
    ctrl = bpy.data.objects['CTRL_Grenade']
    ctrl.animation_data_clear()
    ctrl['pin_pull'] = ctrl['lever_open'] = 0.0
    ctrl.update_tag()
    bpy.context.view_layer.update()


def tris(mesh):
    mesh.calc_loop_triangles()
    return len(mesh.loop_triangles)


def select(objs):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objs:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def clean_game_data(keep_maps=False):
    # В производную копию не попадают осиротевшие high-poly, нативные стеки и 8K-маски.
    for material in list(bpy.data.materials):
        if material.name not in ['GAME_body', 'GAME_mechanism']:
            bpy.data.materials.remove(material)
    for group in list(bpy.data.node_groups):
        bpy.data.node_groups.remove(group, do_unlink=True)
    for image in list(bpy.data.images):
        if keep_maps and Path(bpy.path.abspath(image.filepath)).parent.resolve() == OUT.resolve():
            image.pack()
        else:
            bpy.data.images.remove(image)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)


def build():
    source()
    scene = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    report = {'source': str(SRC), 'sha256': hashlib.file_digest(SRC.open('rb'), 'sha256').hexdigest(),
              'accepted_version': 'v08', 'sizes': SIZE, 'parts': {}, 'center_blender': list(CENTER)}
    coll = bpy.data.collections.new('GRENADE_GAME')
    scene.collection.children.link(coll)
    root = bpy.data.objects.new('Grenade', None)
    coll.objects.link(root)
    nodes = {'root': root}
    for name, original in [('Pin', 'CTRL_PinAssembly'), ('Lever', 'CTRL_LeverPose')]:
        node = bpy.data.objects.new(name, None)
        node.parent = root
        node.location = bpy.data.objects[original].matrix_world.translation - CENTER
        coll.objects.link(node)
        nodes[name] = node
    report['pin_drivers'] = []
    for ob in [bpy.data.objects['CTRL_PinAssembly'], bpy.data.objects['CTRL_LeverPose']]:
        if ob.animation_data:
            for fc in ob.animation_data.drivers:
                report['pin_drivers'].append({'object': ob.name, 'path': fc.data_path,
                                             'index': fc.array_index, 'expression': fc.driver.expression})
    low = []
    for name, budget in PARTS.items():
        hi = bpy.data.objects[name]
        evaluated = hi.evaluated_get(dg)
        mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=dg)
        mesh.transform(evaluated.matrix_world)
        obj = bpy.data.objects.new('LP_' + name, mesh)
        coll.objects.link(obj)
        before = tris(mesh)
        select([obj])
        dec = obj.modifiers.new('Сохранить силуэт и отверстия', 'DECIMATE')
        dec.ratio = min(1.0, budget / before)
        bpy.ops.object.modifier_apply(modifier=dec.name)
        # Чека сохраняет сжатие раздвоенных концов: перенос дельты high-poly на игровую сетку.
        if name == 'SafetyPin' and hi.data.shape_keys:
            keys = hi.data.shape_keys.key_blocks
            compressed = keys.get('SplitTips_Compress')
            if compressed:
                tree = kdtree.KDTree(len(hi.data.vertices))
                for i, vertex in enumerate(keys[0].data):
                    tree.insert(hi.matrix_world @ vertex.co, i)
                tree.balance()
                obj.shape_key_add(name='Basis')
                key = obj.shape_key_add(name='SplitTips_Compress')
                for i, vertex in enumerate(obj.data.vertices):
                    _, nearest, _ = tree.find(vertex.co)
                    delta = hi.matrix_world.to_3x3() @ (compressed.data[nearest].co - keys[0].data[nearest].co)
                    key.data[i].co = vertex.co + delta
        parent = nodes['Pin'] if name in ('SafetyPin', 'PullRing', 'PinEyelet') else nodes['Lever'] if name == 'SafetyLever' else root
        origin = CENTER + parent.location if parent != root else CENTER
        obj.data.transform(Matrix.Translation(-origin), shape_keys=True)
        obj.parent = parent
        obj.data.materials.clear()
        atlas = GROUP[name]
        material = bpy.data.materials.get('GAME_' + atlas) or bpy.data.materials.new('GAME_' + atlas)
        material.use_nodes = True
        obj.data.materials.append(material)
        obj['source_part'] = name
        for poly in obj.data.polygons:
            poly.use_smooth = True
        report['parts'][name] = {'high_triangles': before, 'low_triangles': tris(obj.data), 'atlas': atlas}
        low.append(obj)
        log(name, before, '→', tris(obj.data))
    for atlas in SIZE:
        objects = [ob for ob in low if GROUP[ob['source_part']] == atlas]
        select(objects)
        for obj in objects:
            for uv in list(obj.data.uv_layers):
                obj.data.uv_layers.remove(uv)
            obj.data.uv_layers.new(name='GameUV')
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.008,
                                 correct_aspect=True, scale_to_bounds=True)
        bpy.ops.object.mode_set(mode='OBJECT')
    # Сохраняем только производную игровую сцену, не перезаписывая нативный мастер.
    for obj in list(bpy.data.objects):
        if obj not in coll.objects.values():
            bpy.data.objects.remove(obj, do_unlink=True)
    report['triangles'] = sum(row['low_triangles'] for row in report['parts'].values())
    save_json('mesh_report.json', report)
    scene.world = None
    clean_game_data()
    bpy.ops.wm.save_as_mainfile(filepath=str(LP), compress=True)


def bake():
    source()
    scene = bpy.context.scene
    with bpy.data.libraries.load(str(LP), link=False) as (src, dst):
        dst.collections = ['GRENADE_GAME']
    coll = dst.collections[0]
    scene.collection.children.link(coll)
    # Возвращаем координаты high-poly для лучей; локальная сетка/UV остаются экспортными.
    coll.objects['Grenade'].location = CENTER
    bpy.context.view_layer.update()
    scene.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = device.type == 'OPTIX'
    scene.cycles.device = 'GPU'
    scene.cycles.samples = 8
    scene.cycles.use_denoising = False
    bk = scene.render.bake
    bk.use_selected_to_active = True
    bk.use_cage = False
    bk.cage_extrusion = .002
    bk.max_ray_distance = .005
    bk.margin = 12
    bk.margin_type = 'EXTEND'
    bk.normal_space = 'TANGENT'
    manifest = []
    for atlas, size in SIZE.items():
        names = [name for name in PARTS if GROUP[name] == atlas]
        for channel in ['color', 'rough', 'metal', 'normal', 'ao']:
            path = WORK / 'maps' / f'{atlas}_{channel}.png'
            if path.exists():
                log('RESUME', path.name)
                continue
            image = bpy.data.images.new(f'Bake_{atlas}_{channel}', size, size, alpha=False, float_buffer=True,
                                         is_data=channel != 'color')
            image.colorspace_settings.name = 'sRGB' if channel == 'color' else 'Non-Color'
            image.generated_color = (.5, .5, 1, 1) if channel == 'normal' else (1, 1, 1, 1)
            for i, name in enumerate(names):
                high = bpy.data.objects[name]
                low = coll.objects['LP_' + name]
                for obj in scene.objects:
                    if obj.type == 'MESH':
                        obj.hide_render = obj not in [high, low]
                mat = low.data.materials[0]
                nt = mat.node_tree
                node = nt.nodes.get('BAKE_TARGET') or nt.nodes.new('ShaderNodeTexImage')
                node.name = 'BAKE_TARGET'
                node.image = image
                nt.nodes.active = node
                select([low, high])
                bpy.context.view_layer.objects.active = low
                bk.use_clear = i == 0
                links = []
                if channel in ['color', 'rough', 'metal']:
                    for material in high.data.materials:
                        tree = material.node_tree
                        output = next(n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
                        socket = output.inputs['Surface'].links[0].from_socket
                        yp = next(n for n in tree.nodes if n.type == 'GROUP' and getattr(n.node_tree, 'yp', None) and n.node_tree.yp.is_ypaint_node)
                        emit = tree.nodes.new('ShaderNodeEmission')
                        tree.links.new(yp.outputs[{'color': 'Color', 'rough': 'Roughness', 'metal': 'Metallic'}[channel]], emit.inputs['Color'])
                        tree.links.new(emit.outputs[0], output.inputs['Surface'])
                        links.append((tree, output, socket, emit))
                log('BAKE', atlas, channel, name)
                bpy.ops.object.bake(type='NORMAL' if channel == 'normal' else 'AO' if channel == 'ao' else 'EMIT')
                for tree, output, socket, emit in links:
                    tree.links.new(socket, output.inputs['Surface'])
                    tree.nodes.remove(emit)
            image.file_format = 'PNG'
            image.filepath_raw = str(path)
            image.save()
            manifest.append({'file': path.name, 'color_space': image.colorspace_settings.name,
                             'sha256': hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()})
            bpy.data.images.remove(image)
            save_json('bake_manifest.json', manifest)
            log('SAVED', path)


def export():
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    # Те же треугольники, которые использовал bake: экспортёр получает готовые tangents,
    # включая крышки кольца и раздвоенную чеку, и не выбирает другую диагональ n-gon.
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        old = obj.data
        old.calc_loop_triangles()
        faces = [tuple(tri.vertices) for tri in old.loop_triangles]
        uv_faces = [[tuple(old.uv_layers.active.data[loop].uv) for loop in tri.loops] for tri in old.loop_triangles]
        shapes = {key.name: [tuple(v.co) for v in key.data] for key in old.shape_keys.key_blocks} if old.shape_keys else {}
        mesh = bpy.data.meshes.new(obj.name + '_Triangulated')
        mesh.from_pydata([tuple(v.co) for v in old.vertices], [], faces)
        for material in old.materials:
            mesh.materials.append(material)
        uv = mesh.uv_layers.new(name='GameUV')
        for polygon, coordinates in zip(mesh.polygons, uv_faces):
            polygon.use_smooth = True
            for loop, coord in zip(polygon.loop_indices, coordinates):
                uv.data[loop].uv = coord
        obj.data = mesh
        for name, vertices in shapes.items():
            key = obj.shape_key_add(name=name)
            for vertex, co in zip(key.data, vertices):
                vertex.co = co
        mesh.calc_tangents(uvmap='GameUV')
    for atlas in SIZE:
        mat = bpy.data.materials['GAME_' + atlas]
        nt = mat.node_tree
        nt.nodes.clear()
        bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
        output = nt.nodes.new('ShaderNodeOutputMaterial')
        nt.links.new(bsdf.outputs[0], output.inputs[0])
        def tex(suffix, data=True):
            path = OUT / f'grenade_{atlas}_{suffix}.png'
            im = bpy.data.images.load(str(path), check_existing=True)
            im.colorspace_settings.name = 'Non-Color' if data else 'sRGB'
            node = nt.nodes.new('ShaderNodeTexImage')
            node.image = im
            return node
        color = tex('albedo', False)
        nt.links.new(color.outputs['Color'], bsdf.inputs['Base Color'])
        orm = tex('orm')
        sep = nt.nodes.new('ShaderNodeSeparateColor')
        nt.links.new(orm.outputs[0], sep.inputs[0])
        nt.links.new(sep.outputs['Green'], bsdf.inputs['Roughness'])
        nt.links.new(sep.outputs['Blue'], bsdf.inputs['Metallic'])
        normal = tex('normal')
        normalmap = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(normal.outputs[0], normalmap.inputs['Color'])
        nt.links.new(normalmap.outputs[0], bsdf.inputs['Normal'])
    clean_game_data(keep_maps=True)
    select([o for o in bpy.context.scene.objects])
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'Grenade_Game.blend'), compress=True)
    bpy.ops.export_scene.gltf(filepath=str(OUT / 'grenade.glb'), export_format='GLB', use_selection=True,
                              export_animations=False, export_yup=True, export_apply=False,
                              export_texcoords=True, export_normals=True, export_tangents=True,
                              export_materials='EXPORT', export_image_format='NONE',
                              export_morph=True, export_extras=True)
    log('EXPORTED', OUT / 'grenade.glb')


def compare():
    source()
    scene = bpy.context.scene
    with bpy.data.libraries.load(str(WORK / 'Grenade_Game.blend'), link=False) as (src, dst):
        dst.collections = ['GRENADE_GAME']
    coll = dst.collections[0]
    scene.collection.children.link(coll)
    coll.objects['Grenade'].location = CENTER
    scene.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = device.type == 'OPTIX'
    scene.cycles.device = 'GPU'
    scene.cycles.samples = 48
    scene.cycles.use_denoising = False
    scene.render.resolution_x = scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    camera = scene.camera
    camera.location = (.14, -.24, .14)
    camera.rotation_euler = (Vector((0, 0, .055)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera.data.lens = 70
    camera.data.clip_start = .001
    camera.data.dof.use_dof = False
    for kind in ['native', 'game']:
        for obj in scene.objects:
            if obj.type == 'MESH':
                obj.hide_render = (obj.name not in PARTS) if kind == 'native' else obj not in coll.objects.values()
        scene.render.filepath = str(WORK / f'compare_{kind}.png')
        bpy.ops.render.render(write_still=True)
        log('COMPARE', kind)


def audit():
    bpy.ops.wm.open_mainfile(filepath=str(WORK / 'Grenade_Game.blend'))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    assert len(meshes) == 7
    assert sum(tris(o.data) for o in meshes) == 13359
    assert bpy.data.objects['LP_SafetyPin'].data.shape_keys.key_blocks.get('SplitTips_Compress')
    dependencies = []
    uv_report = []
    for image in bpy.data.images:
        if image.source != 'FILE' or image.name == 'Render Result':
            continue
        path = Path(bpy.path.abspath(image.filepath))
        assert path.is_file(), path
        dependencies.append({'file': str(path), 'size': list(image.size), 'space': image.colorspace_settings.name})
    for obj in meshes:
        assert all(len(poly.vertices) == 3 for poly in obj.data.polygons)
        obj.data.calc_tangents(uvmap='GameUV')
        uv = obj.data.uv_layers.active
        areas = []
        for poly in obj.data.polygons:
            a, b, c = [uv.data[i].uv for i in poly.loop_indices]
            areas.append(abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x)) * .5)
        assert min(areas) > 1e-13, obj.name
        uv_report.append({'part': obj.name, 'triangles': tris(obj.data), 'uv_area': sum(areas), 'min_uv_area': min(areas)})
    assert len(dependencies) == 6, dependencies
    bounds = [o.matrix_world @ Vector(v) for o in meshes for v in o.bound_box]
    dimensions = [max(v[i] for v in bounds) - min(v[i] for v in bounds) for i in range(3)]
    assert .06 < dimensions[0] < .07 and .11 < dimensions[2] < .12
    save_json('reopen_audit.json', {'triangles': 13359, 'meshes': 7, 'dimensions_blender': dimensions,
                                   'maps': dependencies, 'uv': uv_report,
                                   'source_unchanged': hashlib.file_digest(SRC.open('rb'), 'sha256').hexdigest() == json.loads((WORK / 'mesh_report.json').read_text(encoding='utf8'))['sha256']})
    log('AUDIT_OK', dimensions)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['build', 'bake', 'export', 'inspect', 'compare', 'audit'])
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / 'maps').mkdir(exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if args.stage == 'inspect':
        source()
        log([(o.name, len(o.data.vertices), tris(o.data)) for o in bpy.context.scene.objects if o.type == 'MESH'])
    else:
        globals()[args.stage]()
