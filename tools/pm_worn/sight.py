"""Коллиматор ЗОРИН К-1 и крепление к затвору ПМ → два обвеса игры (владелец 2026-10-23: прицел — самостоятельный ассет
на любую планку Пикатинни, крепление — отдельный переходник к пистолету).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/pm_worn/sight.py -- geometry|bake|export [zorin_k1|mount_pm_k1]
Источник — 03_Коллиматор/PM_ReflexSight_on_mount_Worn_v01.blend (крепление + прицел, два корня; читается).
  zorin_k1    — прицел: Body (~7 тыс. треугольников), Lens, Reticle; начало — середина башмака на плоскости верха планки
                (на крепление ПМ и на планку любого оружия он встаёт этой плоскостью); карты 2048 с плёнкой →
                assets/models/attachments/zorin_k1/zorin_k1.glb, zorin_k1_100_{base_color,roughness,metallic,normal,coat}.png,
                manifest.json (sight_h — центр линзы над началом).
  mount_pm_k1 — крепление: Body с картами 1024 в самом GLB (переходник ставит WeaponMods._adapter как есть); начало — сокет
                optic_primary ПМ (корень крепления смещён на k1_mount_game_m − сокет), в manifest — планка, которую оно даёт
                (верх и длина в осях игры) → assets/models/attachments/mount_pm_k1/.
Оси игры: X влево, Y вверх, Z к дулу.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

LENS = 'Reflex | K1 curved aspheric lens'
RAIL = 'Mount | continuous relieved rail spine'
# сокет optic_primary основы «pistol» (data/weapons.json models.pistol.sockets) и корень крепления на ПМ (pm.json k1_mount_game_m)
PM_SOCKET = Vector((0.0, 0.076, 0.004))
# Сцена ПМ (дуло −X, верх +Z, правая сторона +Y) → оси игры (X влево, Y вверх, Z к дулу).
TO_GAME = Matrix(((0, -1, 0, 0), (0, 0, 1, 0), (-1, 0, 0, 0), (0, 0, 0, 1)))
ASSETS = {
    'zorin_k1': dict(prefix='Reflex |', res=2048, out=C.ATT_SIGHT, lod=0.25,
                     # в руках ПМ + крепление + К-1 + глушитель с патронами ≤ 40 тыс.: прицел ~5 тыс.
                     limits=(('lower casting', 1350), ('protective hood', 800), ('side cheek', 250), ('cross-slot shoe', 230),
                             ('clamp jaw', 120), ('six-lobe fastener', 70), ('cheek fastener', 56), ('adjustment recessed bezel', 70),
                             ('adjustment', 130), ('battery cover seal', 70), ('battery cover', 250), ('brightness button', 90),
                             ('upper anchor', 56), ('windage stop', 40), ('battery hinge', 56), ('release latch', 40),
                             ('inspection plate', 56), ('emitter seat', 40), ('lens seat', 200), ('base seam', 70), ('', 90))),
    'mount_pm_k1': dict(prefix='Mount |', res=1024, out=C.ROOT / 'assets/models/attachments/mount_pm_k1', lod=0.0,
                        limits=(('rail spine', 800), ('wraparound saddle', 260), ('clamp plate', 150), ('support pad', 70),
                                ('cross-slot fastener', 90), ('', 110))),
}
log = lambda *a: C.log('K1', *a)  # noqa: E731


def sources(prefix: str):
    return [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render and o.name.startswith(prefix)]


def frame_of(aid: str) -> Matrix:
    """Начало модели в координатах файла: прицел — середина башмака на плоскости верха планки, крепление — корень."""
    if aid == 'mount_pm_k1':
        return Matrix.Identity(4)
    dg = bpy.context.evaluated_depsgraph_get()
    rail = bpy.data.objects[RAIL].evaluated_get(dg)
    top = max((rail.matrix_world @ Vector(c)).z for c in rail.bound_box)
    x = bpy.data.objects['PM_ReflexSight • asset root'].matrix_world.translation.x
    return Matrix.Translation((x, 0.0, top))


def geometry(aid: str) -> None:
    spec = ASSETS[aid]
    bpy.ops.wm.open_mainfile(filepath=str(C.SRC_SIGHT))
    dg = bpy.context.evaluated_depsgraph_get()
    origin = frame_of(aid)
    body, lens = [], None
    for src in sources(spec['prefix']):
        low = C.evaluated_copy(src, dg, 'LP_' + src.name)
        bpy.context.collection.objects.link(low)
        limit = next(n for key, n in spec['limits'] if key in src.name)
        before = C.obj_tris(low)
        after = C.simplify(low, limit)
        log(src.name[:50], before, '->', after)
        if src.name == LENS:
            lens = low
        else:
            body.append(low)
    C.activate(body)
    bpy.context.view_layer.objects.active = body[0]
    bpy.ops.object.join()
    body = bpy.context.object
    body.name = body.data.name = 'Body'
    objs = [body]
    if lens is not None:
        lens.name = lens.data.name = 'Lens'
        objs.append(lens)
    for o in objs:
        o.data.transform(origin.inverted())
        for layer in list(o.data.uv_layers):
            o.data.uv_layers.remove(layer)
        o.data.uv_layers.new(name='GameUV')
    C.unwrap([body], 0.004)
    mat = bpy.data.materials.new(f'GAME • {aid} • 100')
    mat.use_nodes = True
    body.data.materials.append(mat)
    for obj in list(bpy.data.objects):
        if obj not in objs:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    work = C.WORK / 'sight'
    work.mkdir(parents=True, exist_ok=True)
    body['origin_file'] = [round(v, 6) for v in origin.translation]
    bpy.ops.wm.save_as_mainfile(filepath=str(work / f'{aid}_low.blend'))
    log('GEOMETRY_OK', aid, 'Body', C.obj_tris(body), 'Lens', C.obj_tris(lens) if lens else 0, 'px/mm', C.texel_report([body], spec['res']))


INPUT = {'base_color': 'Base Color', 'metallic': 'Metallic', 'roughness': 'Roughness', 'coat': 'Coat Weight'}


def bake(aid: str) -> None:
    spec = ASSETS[aid]
    res = spec['res']
    out = spec['out']
    C.enable_ucupaint()
    bpy.ops.wm.open_mainfile(filepath=str(C.SRC_SIGHT))
    for o in bpy.data.objects:
        if o.type == 'LIGHT':
            o.hide_render = True
    high = [o for o in sources(spec['prefix']) if o.name != LENS]
    with bpy.data.libraries.load(str(C.WORK / f'sight/{aid}_low.blend'), link=False) as (_, target):
        target.objects = ['Body']
    body = target.objects[0]
    bpy.context.collection.objects.link(body)
    body.name = 'BakeTarget'
    # сетка хранится от своего начала — вернуть в координаты файла
    body.matrix_world = Matrix.Translation(Vector(body['origin_file']))
    body.visible_camera = body.visible_diffuse = body.visible_glossy = body.visible_shadow = False
    mat = bpy.data.materials.new('BakeTargetMaterial')
    mat.use_nodes = True
    body.data.materials.clear()
    body.data.materials.append(mat)
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    mat.node_tree.nodes.active = node
    S = bpy.context.scene
    C.gpu_cycles(S, 24)
    bk = S.render.bake
    bk.use_selected_to_active = True
    bk.use_cage = False
    bk.cage_extrusion = 0.0008
    bk.max_ray_distance = 0.0016
    bk.margin = 6
    bk.normal_space = 'TANGENT'
    original = {}
    for obj in high:
        for material in obj.data.materials:
            if not material or material in original or material.node_tree is None:
                continue
            bsdf = next((n for n in material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            output = next((n for n in material.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
            if bsdf and output:
                original[material] = (bsdf, output)
    out.mkdir(parents=True, exist_ok=True)
    channels = ('base_color', 'roughness', 'metallic', 'coat', 'normal') if aid == 'zorin_k1' else ('base_color', 'roughness', 'metallic', 'normal')
    for channel in channels:
        for material, (bsdf, output) in original.items():
            tree = material.node_tree
            if channel == 'normal':
                tree.links.new(bsdf.outputs[0], output.inputs['Surface'])
                continue
            emission = tree.nodes.get('GameBakeEmission') or tree.nodes.new('ShaderNodeEmission')
            emission.name = 'GameBakeEmission'
            source = bsdf.inputs[INPUT[channel]]
            for link in list(emission.inputs['Color'].links):
                tree.links.remove(link)
            if source.is_linked:
                tree.links.new(source.links[0].from_socket, emission.inputs['Color'])
            else:
                value = source.default_value
                emission.inputs['Color'].default_value = value if hasattr(value, '__len__') else (value, value, value, 1)
            tree.links.new(emission.outputs[0], output.inputs['Surface'])
        image = bpy.data.images.new(f'{aid}_100_{channel}', width=res, height=res, alpha=False, float_buffer=(channel == 'normal'))
        image.colorspace_settings.name = 'sRGB' if channel == 'base_color' else 'Non-Color'
        image.generated_color = (0.5, 0.5, 1.0, 1.0) if channel == 'normal' else (0, 0, 0, 1)
        node.image = image
        C.activate(high + [body])
        S.cycles.samples = 16 if channel == 'normal' else 24
        bpy.ops.object.bake(type='NORMAL' if channel == 'normal' else 'EMIT', use_clear=True, use_selected_to_active=True,
                            cage_extrusion=bk.cage_extrusion, max_ray_distance=bk.max_ray_distance, margin=bk.margin)
        image.filepath_raw = str(out / f'{aid}_100_{channel}.png')
        image.file_format = 'PNG'
        if channel == 'normal':
            image.use_half_precision = False
        image.save()
        log('baked', aid, channel)
    log('BAKE_OK', aid)


def textured_material(aid: str, out: Path):
    mat = bpy.data.materials.new(aid)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    for channel, socket in (('base_color', 'Base Color'), ('roughness', 'Roughness'), ('metallic', 'Metallic'), ('normal', 'Normal')):
        path = out / f'{aid}_100_{channel}.png'
        if not path.exists():
            continue
        image = bpy.data.images.load(str(path))
        image.colorspace_settings.name = 'sRGB' if channel == 'base_color' else 'Non-Color'
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = image
        if channel == 'normal':
            nm = mat.node_tree.nodes.new('ShaderNodeNormalMap')
            mat.node_tree.links.new(tex.outputs['Color'], nm.inputs['Color'])
            mat.node_tree.links.new(nm.outputs['Normal'], bsdf.inputs[socket])
        else:
            mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs[socket])
    return mat


def export(aid: str) -> None:
    spec = ASSETS[aid]
    out = spec['out']
    bpy.ops.wm.open_mainfile(filepath=str(C.WORK / f'sight/{aid}_low.blend'))
    body = bpy.data.objects['Body']
    lens = bpy.data.objects.get('Lens')
    objs = [o for o in (body, lens) if o is not None]
    # корень крепления на ПМ стоит не в сокете: сдвиг геометрии, чтобы начало модели легло в сокет optic_primary
    shift = Vector((0.0, 0.0, 0.0))
    rail = None
    if aid == 'mount_pm_k1':
        pm = json.loads((C.ASSET / 'pm.json').read_text(encoding='utf-8'))
        mount_game = Vector(pm['k1_mount_game_m'])
        shift = mount_game - PM_SOCKET
        bb = [TO_GAME @ v.co for v in body.data.vertices]      # вершины крепления в осях игры до сдвига
        rail_top = max(v.y for v in bb)
        rail_z = [round(min(v.z for v in bb) + shift.z, 4), round(max(v.z for v in bb) + shift.z, 4)]
        rail = dict(pos=[0.0, round(rail_top + shift.y, 5), round(shift.z, 5)], rail_z=[round(rail_z[0] - shift.z, 4), round(rail_z[1] - shift.z, 4)])
    for o in objs:
        o.data.transform(Matrix.Translation(shift) @ TO_GAME @ o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
        o.data.update()
    root = bpy.data.objects.new(aid, None)
    bpy.context.collection.objects.link(root)
    body.data.materials.clear()
    body.data.materials.append(textured_material(aid, out))
    extra = []
    center = Vector((0, 0, 0))
    if lens is not None:
        glass = bpy.data.materials.new(aid + '_lens')
        glass.use_nodes = True
        gb = glass.node_tree.nodes.get('Principled BSDF')
        gb.inputs['Base Color'].default_value = (0.05, 0.08, 0.1, 1.0)
        gb.inputs['Roughness'].default_value = 0.05
        gb.inputs['Metallic'].default_value = 0.0
        gb.inputs['Alpha'].default_value = 0.35
        glass.surface_render_method = 'BLENDED'
        lens.data.materials.clear()
        lens.data.materials.append(glass)
        pts = [v.co for v in lens.data.vertices]
        center = Vector([(min(p[i] for p in pts) + max(p[i] for p in pts)) / 2 for i in range(3)])
        # светящаяся метка в центре линзы — игра красит её ПНВ и ведёт люфтом (meta reticle_dot по свечению)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.0005, location=center)
        reticle = bpy.context.object
        reticle.name = reticle.data.name = 'Reticle'
        rm = bpy.data.materials.new(aid + '_reticle')
        rm.use_nodes = True
        rb = rm.node_tree.nodes.get('Principled BSDF')
        rb.inputs['Base Color'].default_value = (1.0, 0.1, 0.05, 1.0)
        rb.inputs['Emission Color'].default_value = (1.0, 0.15, 0.08, 1.0)
        rb.inputs['Emission Strength'].default_value = 4.0
        reticle.data.materials.append(rm)
        extra = [lens, reticle]
    lod_objs = []
    if spec['lod'] > 0.0:
        world = body.copy()
        world.data = body.data.copy()
        world.name = 'Body_LOD1'
        bpy.context.collection.objects.link(world)
        C.activate([world])
        mod = world.modifiers.new('lod', 'DECIMATE')
        mod.ratio = spec['lod']
        mod.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier=mod.name)
        lod_objs = [world]
    for o in [body] + lod_objs + extra:
        o.parent = root
        C.activate([o])
        mod = o.modifiers.new('tri', 'TRIANGULATE')
        bpy.ops.object.modifier_apply(modifier=mod.name)
    C.activate([root, body] + lod_objs + extra)
    out.mkdir(parents=True, exist_ok=True)
    # прицел: карты подставит игра (WeaponMods._model_part) — GLB без картинок; крепление — с картами внутри (_adapter)
    bpy.ops.export_scene.gltf(filepath=str(out / f'{aid}.glb'), export_format='GLB', use_selection=True, export_yup=False,
                              export_animations=False, export_texcoords=True, export_normals=True, export_tangents=True,
                              export_extras=True, export_image_format='NONE' if aid == 'zorin_k1' else 'AUTO')
    bb = [v.co for v in body.data.vertices]
    report = dict(source=str(C.SRC_SIGHT), triangles={o.name: C.obj_tris(o) for o in [body] + lod_objs + extra},
                  axis='X left, Y up, Z forward',
                  bounds_m={'min': [round(min(c[i] for c in bb), 4) for i in range(3)], 'max': [round(max(c[i] for c in bb), 4) for i in range(3)]},
                  states=[100], texture_size=spec['res'])
    if aid == 'zorin_k1':
        report.update(origin='середина башмака на плоскости верха планки (ставится на любую планку Пикатинни)',
                      lens_center_m=[round(v, 5) for v in center], sight_h=round(center.y, 5),
                      clamp_m=round(report['bounds_m']['max'][2] - report['bounds_m']['min'][2], 4))
    else:
        report.update(origin='сокет optic_primary ПМ (корень крепления сдвинут на k1_mount_game_m − сокет)',
                      shift_m=[round(v, 5) for v in shift], provides_rail=rail)
    (out / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(C.WORK / f'sight/{aid}_export.blend'))
    log('EXPORT_OK', aid, report['triangles'], 'sight_h', report.get('sight_h'), 'rail', rail)


bpy.context.preferences.use_preferences_save = False
argv = sys.argv[sys.argv.index('--') + 1:]
step = argv[0]
ids = argv[1:] or list(ASSETS)
for aid in ids:
    {'geometry': geometry, 'bake': bake, 'export': export}[step](aid)
