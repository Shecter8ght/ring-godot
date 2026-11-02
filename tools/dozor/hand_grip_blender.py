"""Editable Blender starter from the tested Godot pose, preserving imported bone rest axes."""
from pathlib import Path
import json
import math
import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/dozor/grip'
OUTPUT = Path('E:/Models Blender/новые руки/DOZOR_Pistol_Grip_starter_v01.blend')
C = Matrix.Rotation(math.pi / 2, 4, 'X')


def import_objects(path):
    # Blender's installed importer does not implement Godot's node-visibility extension.
    if path.name.endswith('_items.gltf'):
        doc = json.loads(path.read_text('utf-8'))
        assert not doc.get('skins') and not doc.get('animations')
        nodes = doc['nodes']
        drop = set()
        def discard(index):
            if index in drop: return
            drop.add(index)
            for child in nodes[index].get('children', []): discard(child)
        for i, node in enumerate(nodes):
            if node.get('extensions', {}).get('KHR_node_visibility', {}).get('visible') is False:
                discard(i)
        remap = {old: new for new, old in enumerate(i for i in range(len(nodes)) if i not in drop)}
        doc['nodes'] = [n for i, n in enumerate(nodes) if i not in drop]
        for node in doc['nodes']:
            if 'children' in node: node['children'] = [remap[i] for i in node['children'] if i in remap]
            node.get('extensions', {}).pop('KHR_node_visibility', None)
        for scene in doc['scenes']: scene['nodes'] = [remap[i] for i in scene['nodes'] if i in remap]
        for field in ['extensionsRequired', 'extensionsUsed']:
            if field in doc: doc[field] = [x for x in doc[field] if x != 'KHR_node_visibility']
        path = path.with_name(path.stem + '_blender.gltf')
        path.write_text(json.dumps(doc, ensure_ascii=False), 'utf-8')
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    return set(bpy.data.objects) - before


def alignment(arm, bones):
    pairs = [(b, arm.matrix_world @ arm.data.bones[b['name']].matrix_local)
             for b in bones if b['name'] in arm.data.bones]
    g = np.array([[b['rest'][i][3] for i in range(3)] for b, _ in pairs])
    n = np.array([list(m.translation) for _, m in pairs])
    gc, nc = g.mean(0), n.mean(0)
    u, _, vt = np.linalg.svd((g - gc).T @ (n - nc))
    r = vt.T @ u.T
    if np.linalg.det(r) < 0:
        vt[-1] *= -1
        r = vt.T @ u.T
    t = nc - r @ gc
    out = Matrix.Identity(4)
    for i in range(3):
        for j in range(3): out[i][j] = float(r[i, j])
        out[i][3] = float(t[i])
    error = max((out @ Vector([b['rest'][i][3] for i in range(3)]) - m.translation).length for b, m in pairs)
    assert error < 0.00005, ('rest correspondence', error)
    return out, error


def parent_bone(obj, arm, bone):
    world = obj.matrix_world.copy()
    obj.parent = arm
    obj.parent_type = 'BONE'
    obj.parent_bone = bone
    bpy.context.view_layer.update()
    obj.matrix_world = world
    bpy.context.view_layer.update()
    assert (obj.matrix_world.translation - world.translation).length < 0.00001


def camera(scene, transform, name):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    position, target = transform
    obj.location = C @ Vector(position)
    obj.rotation_euler = ((C @ Vector(target)) - obj.location).to_track_quat('-Z', 'Y').to_euler()
    data.angle = math.radians(65)
    data.clip_start = 0.005
    return obj


def build_scene(wid, title):
    scene = bpy.data.scenes.new(title)
    bpy.context.window.scene = scene
    imported = import_objects(ROOT / 'assets/models/characters/veras_arms.gltf')
    arm = next(o for o in imported if o.type == 'ARMATURE')
    arm.name = title + ' • редактируемые руки'
    arm.animation_data_clear()
    arm.show_in_front = True
    arm.data.display_type = 'STICK'
    bones = json.loads((WORK / (wid + '_pose.json')).read_text('utf-8'))['bones']
    convert, rest_error = alignment(arm, bones)
    rest = {b.name: arm.matrix_world @ b.matrix_local for b in arm.data.bones}
    desired = {}
    for b in bones:
        name = b['name']
        if name not in rest: continue
        deform = convert @ Matrix(b['pose']) @ Matrix(b['rest']).inverted() @ convert.inverted()
        desired[name] = arm.matrix_world.inverted() @ deform @ rest[name]
    # Imported glTF bone orientations differ from Godot; apply deformation in world space.
    for bone in arm.data.bones:
        if bone.name in desired:
            arm.pose.bones[bone.name].matrix = desired[bone.name]
            bpy.context.view_layer.update()
    error = max((arm.pose.bones[n].matrix.translation - m.translation).length for n, m in desired.items())
    assert error < 0.0001, ('pose transfer', error)
    arm.animation_data_create()
    arm.animation_data.action = bpy.data.actions.new(title + ' • стартовая поза — кадр 1')
    for bone in arm.pose.bones:
        bone.rotation_mode = 'QUATERNION'
        for prop in ['location', 'rotation_quaternion', 'scale']:
            bone.keyframe_insert(data_path=prop, frame=1, group=bone.name)
    items = import_objects(WORK / (wid + '_items.gltf'))
    roots = [o for o in items if o.parent not in items]
    correction = convert @ C.inverted()
    for obj in roots: obj.matrix_world = correction @ obj.matrix_world
    bpy.context.view_layer.update()
    holder = next(o for o in items if o.name.startswith('DozorHandHolder'))
    parent_bone(holder, arm, 'mixamorig_LeftHand')
    holder.name = title + ' • фонарь следует левой кисти'
    for obj in roots:
        if obj != holder:
            parent_bone(obj, arm, 'mixamorig_RightHand')
            obj.name = title + ' • пистолет следует правой кисти'
    for obj in items:
        if obj.type != 'MESH' or not obj.name.startswith('Lens'): continue
        mat = bpy.data.materials.new(title + ' • стекло фонаря')
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (0.5, 0.6, 0.7, 1)
        bsdf.inputs['Roughness'].default_value = 0.04
        bsdf.inputs['Transmission Weight'].default_value = 0.95
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    scene.world = bpy.data.worlds.new(title + ' • студия')
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0.16, 0.19, 0.24, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = 0.7
    for index, position in enumerate([(-0.6, 0.1, 0.7), (0.4, 0.3, 0.5)]):
        data = bpy.data.lights.new(title + ' • софтбокс ' + str(index), 'AREA')
        light = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(light)
        light.location = position
        light.rotation_euler = (-light.location).to_track_quat('-Z', 'Y').to_euler()
        data.energy = 55
        data.shape = 'DISK'
        data.size = 0.5
    scene.camera = camera(scene, [(0.38, 0.05, 0.32), (0, -0.09, -0.04)], title + ' • осмотр')
    camera(scene, [(0, 0.04, -0.46), (0, -0.06, 0.35)], title + ' • вид из глаз')
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 24
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.frame_start = scene.frame_end = 1
    scene.frame_set(1)
    scene['Источник'] = 'Стартовый хват ДОЗОР, проверенный в Godot. Поза на правку владельцу.'
    arm['Правка'] = 'Pose Mode. Пистолет привязан к RightHand, фонарь к LeftHand. Исходный rest не изменён.'
    return scene, {'weapon': wid, 'rest_error_m': rest_error, 'pose_error_m': error, 'bones': len(desired)}


bpy.ops.wm.read_factory_settings(use_empty=True)
initial = bpy.context.scene
scenes, report = [], []
for wid, title in [('wpn_hg_01', 'ДОЗОР — ПМ'), ('wpn_hg_02', 'ДОЗОР — Glock')]:
    scene, result = build_scene(wid, title)
    scenes.append(scene)
    report.append(result)
bpy.data.scenes.remove(initial)
bpy.context.window.scene = scenes[0]
text = bpy.data.texts.new('00 — КАК ПРАВИТЬ')
text.write('Две сцены: ПМ и Glock. Руки и пальцы — Pose Mode, кадр 1.\n'
           'Пистолет следует правой кисти; фонарь следует левой. Rest pose не применялась.\n'
           'Это стартовая поза для правки, не принятая финальная анимация.\n'
           'В Godot: Оружие и хват рук → ПМ / Glock · ДОЗОР в левой руке → Хват рук.\n'
           'Изменения Blender и ползунки Godot независимы; готовую Blender-позу нужно переносить отдельно.\n')
for image in bpy.data.images:
    if image.source == 'FILE' and not image.packed_file:
        try: image.pack()
        except RuntimeError: pass
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        area.spaces.active.region_3d.view_perspective = 'CAMERA'
        area.spaces.active.shading.type = 'MATERIAL'
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
bpy.ops.wm.open_mainfile(filepath=str(OUTPUT))
assert all(bpy.data.scenes.get(scene_name) for scene_name in ['ДОЗОР — ПМ', 'ДОЗОР — Glock'])
assert len([o for o in bpy.data.objects if o.type == 'ARMATURE']) == 2
assert len([o for o in bpy.data.objects if o.parent_type == 'BONE' and o.parent_bone == 'mixamorig_LeftHand']) == 2
(WORK / 'blender_report.json').write_text(json.dumps({'output': str(OUTPUT), 'scenes': report}, ensure_ascii=False, indent=2), 'utf-8')
print('DOZOR editable starter saved and reopened:', OUTPUT, report)
