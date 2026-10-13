"""Task 1 only: preserve v08 and differentiate native manufacturing microtextures.

Run in Blender 5.2.2 with UCUPaint 2.4.9. No geometry, wear, dirt, marking,
Metallic, lighting or library edits are part of the material patch.
"""
import argparse
import hashlib
import importlib
import json
import math
import shutil
import sys
from pathlib import Path

import addon_utils
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_asset_src/grenade_codex/materials_v09_stage1'
BASE = Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v08')
STUDIO = BASE / 'Grenade_MkII_Studio_v08.blend'
MASTER = BASE / 'Grenade_MkII_UCUPaint_v08.blend'
ASSETS = ['GrenadeBody', 'FuzeCasting', 'BottomPlug', 'SafetyLever',
          'PinEyelet', 'PullRing', 'SafetyPin']
FACTORY_PREFIXES = ('03 • CC0 physical machining roughness',
                    '04 • Shallow manufacturing relief and irregular raised grains',
                    '05 • Fine metal tooth')
CANDIDATE = OUT / 'Grenade_MkII_Studio_v09_Task1.blend'
UV_SHEET = 'Manufacture_Sheet_Metric'
UV_WIRE = 'Manufacture_Wire_Metric'
SHOTS = {
    'head': ((.085, -.155, .185), (.006, 0, .093), 105, 1920, 1920),
    'lever': ((.006, -.025, .22), (.003, 0, .111), 105, 1920, 1920),
    'wire': ((.085, -.16, .125), (.020, -.013, .089), 115, 1920, 1920),
    'overview': ((.19, -.33, .205), (0, 0, .049), 105, 1440, 1800),
}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')


def native():
    bpy.context.preferences.use_preferences_save = False
    if addon_utils.enable('bl_ext.blender_org.ucupaint', default_set=True) is None:
        raise RuntimeError('UCUPaint is unavailable')
    module = importlib.import_module('bl_ext.blender_org.ucupaint')
    if module.common.get_current_version_str() != '2.4.9':
        raise RuntimeError('Inspect the API before using another UCUPaint version')
    return module


def array(seq, prop, width, dtype=np.float32):
    result = np.empty(len(seq) * width, dtype=dtype)
    seq.foreach_get(prop, result)
    return result.reshape((-1, width))


def digest_array(seq, prop, width, dtype=np.float32):
    return hashlib.sha256(array(seq, prop, width, dtype).tobytes()).hexdigest()


def value(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    try:
        return [value(x) for x in v]
    except TypeError:
        return str(v)


def entity(ent):
    """User-editable native properties, including nested channel/mask settings."""
    result = {}
    for prop in ent.bl_rna.properties:
        name = prop.identifier
        if name in {'rna_type', 'id_data'} or prop.is_readonly and prop.type != 'COLLECTION':
            continue
        if prop.type == 'POINTER':
            continue
        if prop.type == 'COLLECTION':
            result[name] = [entity(x) for x in getattr(ent, name)]
        else:
            result[name] = value(getattr(ent, name))
    return result


def texture_node(node):
    row = {'type': node.bl_idname}
    for prop in ('projection', 'projection_blend', 'interpolation', 'extension',
                 'noise_dimensions', 'normalize'):
        if hasattr(node, prop):
            row[prop] = value(getattr(node, prop))
    if getattr(node, 'image', None):
        image = node.image
        row['image'] = {'name': image.name,
                        'sha256': hashlib.sha256(bytes(image.packed_file.data)).hexdigest()
                        if image.packed_file else sha(bpy.path.abspath(image.filepath)),
                        'color_space': image.colorspace_settings.name}
    row['inputs'] = {s.name: value(s.default_value) for s in node.inputs
                     if hasattr(s, 'default_value')}
    return row


def paint_snapshot(U):
    result = {}
    for material in bpy.data.materials:
        if not material.name.startswith('UCUPaint_v08_'):
            continue
        group = next(n for n in material.node_tree.nodes if n.type == 'GROUP'
                     and getattr(n.node_tree, 'yp', None) and n.node_tree.yp.is_ypaint_node)
        tree = group.node_tree
        bsdf = next(n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        layers = {}
        for layer in tree.yp.layers:
            props = entity(layer)
            layers[layer.name] = {'props': props,
                                 'source': texture_node(U.common.get_layer_source(layer)),
                                 'mask_sources': [texture_node(U.common.get_mask_source(m))
                                                  for m in layer.masks]}
        result[material.name] = {
            'tree': tree.name, 'root_channels': [entity(c) for c in tree.yp.channels],
            'principled': texture_node(bsdf), 'layers': layers,
            'root_links': sorted([list((l.from_node.name, l.from_socket.name,
                                       l.to_node.name, l.to_socket.name))
                                  for l in material.node_tree.links]),
        }
    return result


def geometry_snapshot():
    result = {}
    for name in ASSETS:
        obj = bpy.data.objects[name]
        mesh = obj.data
        parts = [array(mesh.vertices, 'co', 3).tobytes(),
                 array(mesh.edges, 'vertices', 2, np.int32).tobytes(),
                 array(mesh.loops, 'vertex_index', 1, np.int32).tobytes(),
                 array(mesh.polygons, 'loop_start', 1, np.int32).tobytes(),
                 array(mesh.polygons, 'loop_total', 1, np.int32).tobytes(),
                 array(mesh.polygons, 'use_smooth', 1, np.bool_).tobytes()]
        colors = {a.name: {'domain': a.domain, 'type': a.data_type,
                          'sha256': digest_array(a.data, 'color', 4)}
                  for a in mesh.color_attributes}
        result[name] = {
            'mesh_sha256': hashlib.sha256(b''.join(parts)).hexdigest(),
            'matrix': [list(row) for row in obj.matrix_world],
            'parent': obj.parent.name if obj.parent else None,
            'modifiers': [[m.name, m.type, getattr(m, 'levels', None),
                           getattr(m, 'render_levels', None)] for m in obj.modifiers],
            'shape_keys': {k.name: digest_array(k.data, 'co', 3)
                           for k in mesh.shape_keys.key_blocks} if mesh.shape_keys else {},
            'uvs': {uv.name: digest_array(uv.data, 'uv', 2) for uv in mesh.uv_layers},
            'uv_active': mesh.uv_layers.active.name,
            'uv_render': [uv.name for uv in mesh.uv_layers if uv.active_render],
            'colors': colors,
        }
    return result


def studio_snapshot():
    scene = bpy.context.scene
    return {'camera': {'matrix': [list(r) for r in scene.camera.matrix_world],
                       'lens': scene.camera.data.lens} if scene.camera else None,
            'lights': {o.name: {'matrix': [list(r) for r in o.matrix_world],
                                 'energy': o.data.energy, 'color': list(o.data.color),
                                 'size': o.data.size, 'size_y': o.data.size_y}
                       for o in scene.objects if o.type == 'LIGHT'},
            'world_nodes': [texture_node(n) for n in scene.world.node_tree.nodes],
            'view': {p: value(getattr(scene.view_settings, p)) for p in
                     ['view_transform', 'look', 'exposure', 'gamma']}}


def rig_snapshot():
    result = {}
    objects = {bpy.data.objects[name] for name in ASSETS}
    for obj in list(objects):
        parent = obj.parent
        while parent:
            objects.add(parent)
            parent = parent.parent
    for obj in sorted(objects, key=lambda o: o.name):
        row = {'parent': obj.parent.name if obj.parent else None,
               'location': list(obj.location), 'rotation': list(obj.rotation_euler),
               'scale': list(obj.scale), 'rotation_mode': obj.rotation_mode,
               'constraints': [entity(c) for c in obj.constraints],
               'properties': {k: value(obj[k]) for k in obj.keys() if k != '_RNA_UI'}}
        drivers = []
        for datablock in [obj, obj.data.shape_keys if obj.type == 'MESH' else None]:
            anim = getattr(datablock, 'animation_data', None)
            if not anim:
                continue
            for curve in anim.drivers:
                driver = curve.driver
                drivers.append({'data_path': curve.data_path, 'index': curve.array_index,
                                'expression': driver.expression, 'type': driver.type,
                                'variables': [{'name': var.name, 'type': var.type,
                                               'targets': [{'id': t.id.name if t.id else None,
                                                            'data_path': t.data_path,
                                                            'bone': t.bone_target,
                                                            'transform_type': t.transform_type,
                                                            'transform_space': t.transform_space}
                                                           for t in var.targets]}
                                              for var in driver.variables]})
            row['action_' + datablock.name] = anim.action.name if anim.action else None
        row['drivers'] = drivers
        result[obj.name] = row
    return result


def inspect(U):
    bpy.ops.wm.open_mainfile(filepath=str(STUDIO))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    baseline = {'source': str(STUDIO), 'sha256': sha(STUDIO),
                'geometry': geometry_snapshot(), 'paint': paint_snapshot(U),
                'studio': studio_snapshot()}
    write_json(OUT / 'checks/baseline_v08.json', baseline)
    arrays = {}
    for name in ASSETS:
        obj = bpy.data.objects[name]
        co = array(obj.data.vertices, 'co', 3)
        arrays[name + '_vertices'] = co
        arrays[name + '_loops'] = array(obj.data.loops, 'vertex_index', 1, np.int32)
        print('MESH', name, 'bounds', co.min(axis=0).tolist(), co.max(axis=0).tolist(),
              'matrix', [list(r) for r in obj.matrix_world], 'first', co[:12].tolist(), flush=True)
    np.savez_compressed(OUT / 'checks/input_meshes.npz', **arrays)
    for mat, row in baseline['paint'].items():
        if mat.endswith('CastBody'):
            continue
        for name, layer in row['layers'].items():
            if name in FACTORY_PREFIXES:
                print('FACTORY', mat, name, layer['source'], flush=True)
    print('BASELINE_OK', sha(STUDIO), flush=True)


def metric_uv(obj, sides, uv_name, extent, closed=False):
    """Add a separate manufacturing UV; retain every original UV and mask.

    The accepted mesh is a verified ordered sweep. U follows strip/wire length;
    V follows its actual perimeter. Seam handling is per face, without moving
    vertices, changing normals, triangulation or topology.
    """
    mesh = obj.data
    active = mesh.uv_layers.active.name
    render = [uv.name for uv in mesh.uv_layers if uv.active_render]
    co = array(mesh.vertices, 'co', 3).astype(np.float64)
    if len(co) % sides:
        raise RuntimeError(('Unexpected sweep layout', obj.name))
    sections = co.reshape(-1, sides, 3)
    centers = sections.mean(axis=1)
    length = np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(centers, axis=0), axis=1))))
    circum = np.linalg.norm(np.roll(sections, -1, axis=1) - sections, axis=2)
    around = np.concatenate((np.zeros((len(sections), 1)), np.cumsum(circum[:, :-1], axis=1)), axis=1)
    circumference = circum.sum(axis=1)
    total_length = length[-1] + np.linalg.norm(centers[-1] - centers[0])
    u_extent = total_length if closed else extent[0]
    uv = mesh.uv_layers.get(uv_name) or mesh.uv_layers.new(name=uv_name)
    values = np.empty((len(mesh.loops), 2), dtype=np.float32)
    for polygon in mesh.polygons:
        indices = np.asarray(polygon.vertices)
        section_ids = indices // sides
        side_ids = indices % sides
        u = length[section_ids].copy()
        v = around[section_ids, side_ids].copy()
        if len(set(section_ids)) == 1 and len(indices) > 4:
            # Sweep end caps: a planar metric projection avoids a zero Jacobian.
            points = co[indices] - centers[section_ids[0]]
            _, _, axes = np.linalg.svd(points, full_matrices=False)
            u = points @ axes[0] + length[section_ids[0]]
            v = points @ axes[1]
        else:
            if side_ids.max() - side_ids.min() > sides // 2:
                at_seam = side_ids == 0
                v[at_seam] = circumference[section_ids[at_seam]]
            if closed and section_ids.max() - section_ids.min() > len(sections) // 2:
                u[section_ids == 0] = total_length
        values[polygon.loop_start:polygon.loop_start + polygon.loop_total, 0] = u / u_extent
        values[polygon.loop_start:polygon.loop_start + polygon.loop_total, 1] = v / extent[1]
    uv.data.foreach_set('uv', values.ravel())
    mesh.uv_layers.active = mesh.uv_layers[active]
    for old in mesh.uv_layers:
        old.active_render = old.name in render
    mesh.update()
    return {'object': obj.name, 'uv': uv_name, 'sections': len(sections),
            'section_vertices': sides, 'length_mm': float(length[-1] * 1000),
            'u_extent_mm': float(u_extent * 1000), 'v_extent_mm': extent[1] * 1000,
            'old_active_uv_preserved': active, 'closed': closed}


def synchronize(U, ent, prop, val):
    setattr(ent, prop, val)
    U.common.set_entity_prop_value(ent, prop, getattr(ent, prop))
    actual = U.common.get_entity_prop_value(ent, prop)
    if isinstance(val, (int, float)) and abs(actual - val) > 1e-8:
        raise RuntimeError(('Native socket mismatch', prop, val, actual))


def reconnect(U, tree):
    U.input_outputs.check_all_channel_ios(tree.yp, reconnect=True)
    U.input_outputs.check_start_end_root_ch_nodes(tree)
    for layer in tree.yp.layers:
        U.node_connections.reconnect_layer_nodes(layer)
    U.node_connections.reconnect_yp_nodes(tree)


def patch(U, family):
    bpy.ops.wm.open_mainfile(filepath=str(CANDIDATE if CANDIDATE.exists() else STUDIO))
    scene = bpy.context.scene
    scene.frame_set(1)
    bpy.context.view_layer.update()
    baseline = json.loads((OUT / 'checks/baseline_v08.json').read_text(encoding='utf8'))
    assert sha(STUDIO) == baseline['sha256'], 'The saved acceptance source changed; inspect before editing'
    manifest = json.loads((OUT / 'textures/manufacturing/manifest.json').read_text(encoding='utf8'))
    row = next(r for r in manifest['maps'] if r['family'] == family)
    members = {'head': ['FuzeCasting', 'BottomPlug'], 'lever': ['SafetyLever'],
               'wire': ['PullRing', 'PinEyelet', 'SafetyPin']}[family]
    uv_rows = []
    if family == 'lever':
        uv_rows.append(metric_uv(bpy.data.objects['SafetyLever'], 16, UV_SHEET, (.0512, .0512)))
    elif family == 'wire':
        for name, sides in [('PullRing', 24), ('PinEyelet', 24), ('SafetyPin', 20)]:
            uv_rows.append(metric_uv(bpy.data.objects[name], sides, UV_WIRE, (.064, .0064), name == 'PinEyelet'))
    obj = bpy.data.objects[members[0]]
    bpy.context.view_layer.objects.active = obj
    material = obj.active_material
    group = next(n for n in material.node_tree.nodes if n.type == 'GROUP' and n.node_tree.yp.is_ypaint_node)
    tree = group.node_tree
    layers = {l.name: l for l in tree.yp.layers}
    for layer_name, role in [(FACTORY_PREFIXES[0], 'roughness'), (FACTORY_PREFIXES[1], 'height')]:
        layer = layers[layer_name]
        source = U.common.get_layer_source(layer)
        image_path = OUT / 'textures/manufacturing' / row[role]['file']
        if sha(image_path) != row[role]['sha256']:
            raise RuntimeError(('Map changed after authoring', image_path))
        image = bpy.data.images.load(str(image_path), check_existing=True)
        image.colorspace_settings.name = 'Non-Color'
        image.pack()
        source.image = image
        source.interpolation = 'Cubic' if role == 'height' else 'Linear'
        source.extension = 'REPEAT'
        if family == 'head':
            layer.texcoord_type = 'Object'
            layer.scale = (1 / .0512,) * 3
            source.projection = 'BOX'
            source.projection_blend = .12
        else:
            layer.uv_name = UV_SHEET if family == 'lever' else UV_WIRE
            layer.texcoord_type = 'UV'
            layer.scale = (1, 1, 1)
            layer.translation = (0, 0, 0)
            layer.rotation = (0, 0, 0)
            source.projection = 'FLAT'
        if role == 'height':
            normal_index = next(i for i, c in enumerate(tree.yp.channels) if c.type == 'NORMAL')
            synchronize(U, layer.channels[normal_index], 'bump_distance', row['bump_distance_m'])
        # Native layer names/order, all masks, intensities and other channels remain.
        source.label = f'v09 task 1: {family} {role}; retained native manufacturing layer'
    fine = layers[FACTORY_PREFIXES[2]]
    source = U.common.get_layer_source(fine)
    source.inputs['Scale'].default_value = {'head': 24000, 'lever': 35000, 'wire': 40000}[family]
    source.inputs['Detail'].default_value = {'head': 2.1, 'lever': 1.6, 'wire': 1.4}[family]
    if family != 'head':
        fine.uv_name = UV_SHEET if family == 'lever' else UV_WIRE
        fine.texcoord_type = 'UV'
        fine.scale = (.0512, .0512, 1) if family == 'lever' else (.064, .0064, 1)
        fine.translation = (0, 0, 0)
    normal_index = next(i for i, c in enumerate(tree.yp.channels) if c.type == 'NORMAL')
    synchronize(U, fine.channels[normal_index], 'bump_distance',
                {'head': 6e-6, 'lever': 1.6e-6, 'wire': .8e-6}[family])
    reconnect(U, tree)
    # Store the layer's provenance without removing the original packed maps.
    tree['task1_manufacturing'] = json.dumps(row, ensure_ascii=False)
    tree['task1_geometry_frozen'] = True
    material['task1_manufacturing_family'] = family
    # Retain v08 dependencies by absolute path during authoring. Delivery remaps
    # these to self-contained relative copies only after the visual comparisons.
    for image in bpy.data.images:
        if image.filepath and image.type not in {'RENDER_RESULT', 'COMPOSITING'}:
            image.filepath = bpy.path.abspath(image.filepath)
            for packed in image.packed_files:
                packed.filepath = image.filepath
    # Retain replaced image datablocks for reversible editing, including a map
    # whose final native layer stopped using it in a previous family patch.
    for path in sorted((BASE / 'textures').rglob('*.png')):
        matches = [im for im in bpy.data.images
                   if im.type not in {'RENDER_RESULT', 'COMPOSITING'}
                   and Path(bpy.path.abspath(im.filepath)).resolve() == path.resolve()]
        if matches:
            for image in matches:
                if image.users == 0:
                    image.use_fake_user = True
        elif path.name in {'Metal049C_8K-PNG_Roughness.png', 'Metal009_8K-PNG_Roughness.png'}:
            image = bpy.data.images.load(str(path), check_existing=True)
            image.colorspace_settings.name = 'Non-Color'
            image.use_fake_user = True
            image.pack()
    bpy.context.preferences.filepaths.save_version = 0
    assert len(tree.yp.layers) == {'head': 13, 'lever': 15, 'wire': 9}[family]
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(CANDIDATE), relative_remap=False, compress=True)
    patch_record = OUT / 'checks/patch_task1.json'
    records = json.loads(patch_record.read_text(encoding='utf8')) if patch_record.exists() else {}
    records[family] = {'maps': row, 'metric_uv': uv_rows, 'material': material.name,
                       'layer_names': list(FACTORY_PREFIXES), 'only_task': 1}
    write_json(patch_record, records)
    print('PATCH_OK', family, CANDIDATE, flush=True)


def finish(U):
    """Make the candidate's packed images and external copies self-contained."""
    bpy.ops.wm.open_mainfile(filepath=str(CANDIDATE))
    copies = []
    for image in bpy.data.images:
        if image.type in {'RENDER_RESULT', 'COMPOSITING'}:
            continue
        source = Path(bpy.path.abspath(image.filepath)).resolve()
        if not source.is_file() or not image.packed_file:
            raise RuntimeError(('Missing preserved image', image.name, str(source)))
        if source.is_relative_to(BASE.resolve()):
            relative = source.relative_to(BASE.resolve())
            destination = OUT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and sha(destination) != sha(source):
                raise RuntimeError(('Refuse to replace different retained map', destination))
            if not destination.exists():
                shutil.copy2(source, destination)
        elif source.is_relative_to(OUT.resolve()):
            destination = source
        else:
            raise RuntimeError(('Unexpected dependency root', source))
        digest = hashlib.sha256(bytes(image.packed_file.data)).hexdigest()
        if digest != sha(destination):
            raise RuntimeError(('Packed image bytes differ from external file', image.name))
        relative_path = '//'+destination.relative_to(OUT).as_posix()
        image.filepath = relative_path
        for packed in image.packed_files:
            packed.filepath = relative_path
        copies.append({'name': image.name, 'file': relative_path, 'sha256': digest,
                       'color_space': image.colorspace_settings.name})
    # Retain licence evidence from the accepted source, no new commercial assets.
    resource_dst = OUT / 'resources'
    if not resource_dst.exists():
        shutil.copytree(BASE / 'resources', resource_dst)
    source_dst = OUT / 'source'
    source_dst.mkdir(parents=True, exist_ok=True)
    for name in ['grenade_surface_v09.py', 'grenade_manufacturing_maps_v09.py']:
        shutil.copy2(ROOT / 'tools' / name, source_dst / name)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(CANDIDATE), relative_remap=False, compress=True)
    write_json(OUT / 'checks/self_contained_images.json', {'images': copies, 'count': len(copies)})
    print('SELF_CONTAINED_OK', len(copies), CANDIDATE, flush=True)


def configure_render(scene, samples):
    scene.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = device.type == 'OPTIX'
    scene.cycles.device = 'GPU'
    scene.cycles.samples = samples
    scene.cycles.seed = 90131
    scene.cycles.use_animated_seed = False
    scene.cycles.use_denoising = False
    scene.cycles.adaptive_threshold = .006
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '16'
    scene.camera.data.dof.use_dof = False


def render(U, version, shot, samples, pilot):
    path = STUDIO if version == 'before' else CANDIDATE
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene = bpy.context.scene
    scene.frame_set(1)
    configure_render(scene, samples)
    position, target, lens, width, height = SHOTS[shot]
    scene.camera.location = position
    scene.camera.rotation_euler = (Vector(target) - scene.camera.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera.data.lens = lens
    scene.render.resolution_x = width // 2 if pilot else width
    scene.render.resolution_y = height // 2 if pilot else height
    image_path = OUT / ('pilot' if pilot else 'comparisons') / f'{shot}_{version}.png'
    image_path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(image_path)
    spec = studio_snapshot()
    spec['render'] = {p: value(getattr(scene.render, p)) for p in
                      ['resolution_x', 'resolution_y', 'resolution_percentage', 'filter_size']}
    spec['cycles'] = {p: value(getattr(scene.cycles, p)) for p in
                      ['samples', 'seed', 'use_denoising', 'adaptive_threshold', 'max_bounces',
                       'diffuse_bounces', 'glossy_bounces']}
    spec['dof'] = scene.camera.data.dof.use_dof
    write_json(image_path.with_suffix('.json'), {'source_file': str(path), 'source_sha256': sha(path),
                                               'comparison_spec': spec})
    print('RENDER_BEGIN', shot, version, samples, flush=True)
    bpy.ops.render.render(write_still=True)
    print('RENDER_OK', image_path, sha(image_path), flush=True)


def differences(before, after, prefix=''):
    if isinstance(before, dict) and isinstance(after, dict):
        out = []
        for key in sorted(set(before) | set(after)):
            path = prefix + '/' + key
            if key not in before or key not in after:
                out.append([path, before.get(key), after.get(key)])
            else:
                out.extend(differences(before[key], after[key], path))
        return out
    if before != after:
        return [[prefix, before, after]]
    return []


def verify(U, path=CANDIDATE):
    bpy.ops.wm.open_mainfile(filepath=str(path))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    baseline = json.loads((OUT / 'checks/baseline_v08.json').read_text(encoding='utf8'))
    geometry = geometry_snapshot()
    added = {}
    for name, old in baseline['geometry'].items():
        extra = {key: val for key, val in geometry[name]['uvs'].items() if key not in old['uvs']}
        expected = {UV_SHEET} if name == 'SafetyLever' else (
            {UV_WIRE} if name in {'PullRing', 'PinEyelet', 'SafetyPin'} else set())
        if set(extra) != expected:
            raise RuntimeError(('Unexpected additional UV data', name, sorted(extra)))
        added[name] = extra
        for key in extra:
            del geometry[name]['uvs'][key]
    geom_diff = differences(baseline['geometry'], geometry)
    paint = paint_snapshot(U)
    factory_changes, protected_changes = [], []
    for mat, old in baseline['paint'].items():
        current = paint[mat]
        for field in ('tree', 'root_channels', 'principled', 'root_links'):
            protected_changes.extend(differences(old[field], current[field], mat + '/' + field))
        if set(old['layers']) != set(current['layers']):
            raise RuntimeError(('Changed native layer identities', mat))
        for name, original in old['layers'].items():
            modified = current['layers'][name]
            if name in FACTORY_PREFIXES and not mat.endswith('CastBody'):
                # Existing masks on a manufacturing layer are protected as well.
                for key in ('mask_sources',):
                    protected_changes.extend(differences(original[key], modified[key], mat + '/' + name + '/' + key))
                protected_changes.extend(differences(original['props']['masks'], modified['props']['masks'], mat + '/' + name + '/masks'))
                for i, (old_channel, new_channel) in enumerate(zip(
                        original['props']['channels'], modified['props']['channels'])):
                    old_values, new_values = dict(old_channel), dict(new_channel)
                    if old['root_channels'][i]['type'] == 'NORMAL':
                        old_values.pop('bump_distance', None)
                        new_values.pop('bump_distance', None)
                    protected_changes.extend(differences(old_values, new_values,
                                              mat + '/' + name + '/protected_channel_' + str(i)))
                for prop in ['enable', 'intensity_value', 'enable_masks', 'modifiers', 'blend_type']:
                    if prop in original['props']:
                        protected_changes.extend(differences(original['props'][prop], modified['props'][prop],
                                                  mat + '/' + name + '/' + prop))
                factory_changes.extend(differences(original, modified, mat + '/' + name))
            else:
                protected_changes.extend(differences(original, modified, mat + '/' + name))
    studio_diff = differences(baseline['studio'], studio_snapshot())
    candidate_rig = rig_snapshot()
    images = []
    for image in bpy.data.images:
        if image.type in {'RENDER_RESULT', 'COMPOSITING'}:
            continue
        images.append({'name': image.name, 'file': image.filepath,
                       'resolved': bpy.path.abspath(image.filepath),
                       'packed_paths': [p.filepath for p in image.packed_files],
                       'packed': bool(image.packed_file), 'color_space': image.colorspace_settings.name,
                       'size': list(image.size)})
        resolved = Path(bpy.path.abspath(image.filepath))
        if not image.packed_file or not resolved.is_file():
            raise RuntimeError(('Incomplete image dependency', image.name))
        if hashlib.sha256(bytes(image.packed_file.data)).hexdigest() != sha(resolved):
            raise RuntimeError(('Packed/external mismatch', image.name))
        if image.name.endswith('_16.png') and image.colorspace_settings.name != 'Non-Color':
            raise RuntimeError(('Wrong data-map color space', image.name))
    bpy.ops.wm.open_mainfile(filepath=str(STUDIO))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    rig_diff = differences(rig_snapshot(), candidate_rig)
    result = {'file': str(path), 'sha256': sha(path), 'geometry_differences': geom_diff,
              'protected_material_differences': protected_changes, 'studio_differences': studio_diff,
              'factory_changes': factory_changes, 'additional_uvs': added, 'images': images,
              'rig_differences': rig_diff,
              'native_stacks': len(paint), 'native_layers': sum(len(s['layers']) for s in paint.values()),
              'pass': not geom_diff and not protected_changes and not studio_diff and not rig_diff}
    write_json(OUT / 'checks/verify_task1.json', result)
    print('VERIFY', result['pass'], 'geometry', len(geom_diff), 'protected', len(protected_changes),
          'studio', len(studio_diff), 'factory', len(factory_changes), flush=True)
    for row in (geom_diff + protected_changes + studio_diff + rig_diff)[:18]:
        print('UNEXPECTED_DIFF', row, flush=True)
    for im in images:
        if not Path(im['resolved']).is_file():
            print('PATH_DIAG', im['name'], im['resolved'], im['packed_paths'], flush=True)
    if not result['pass']:
        raise RuntimeError('Protected state differs; repair the copy before proceeding')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['inspect', 'patch', 'render', 'compare', 'verify', 'finish'])
    parser.add_argument('--family', choices=['head', 'lever', 'wire'])
    parser.add_argument('--version', choices=['before', 'after'], default='after')
    parser.add_argument('--shot', choices=list(SHOTS), default='head')
    parser.add_argument('--samples', type=int, default=192)
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    OUT.mkdir(parents=True, exist_ok=True)
    U = native()
    if args.mode == 'inspect':
        inspect(U)
    elif args.mode == 'patch':
        if not args.family:
            parser.error('--family is required for patch')
        patch(U, args.family)
    elif args.mode == 'render':
        render(U, args.version, args.shot, args.samples, args.pilot)
    elif args.mode == 'verify':
        verify(U)
    elif args.mode == 'finish':
        finish(U)
    elif args.mode == 'compare':
        for shot in ['head', 'lever', 'wire']:
            for version in ['before', 'after']:
                render(U, version, shot, args.samples, args.pilot)


if __name__ == '__main__':
    main()
