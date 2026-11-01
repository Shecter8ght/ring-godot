"""Стенд нормалей: одна запечённая карта нормалей в Blender и в Godot.

Пять пар high / low, типичных для твёрдых предметов: брусок с фасками на гладкой low (все рёбра мягкие, углы 90°),
тот же брусок на low с жёсткими рёбрами, цилиндр с канавками и фасками торцов, бугристый шар и восьмигранник с
фасками на гладкой low (углы 45° — так оставляют мягкими рёбра игровых сеток оружия: жёсткие только круче 60°). Карта нормалей
запекается Cycles так же, как в конвейерах оружия (`tools/vss_m_v8/game_bake.py`: 8 бит, касательное пространство,
selected to active). Low выгружается в glTF дважды — с тангентами Blender и без них (тогда Godot считает свои), high —
отдельно. Для отсчёта — снимки Eevee «low с картой» и «high» при одном свете: насколько карта повторяет high в самом
Blender. Сравнение в Godot — `tools/normal_probe.tscn`, разбор — `tools/asset_kit/normal_probe_report.py`.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/asset_kit/normal_probe.py -- <папка>
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

OUT = Path(sys.argv[sys.argv.index('--') + 1])
OUT.mkdir(parents=True, exist_ok=True)
SIZE = 1024
EXTRUSION, RAY = 0.004, 0.01                       # м: у бруска фаска 3 мм, low дальше всего от high в углах
SHOT = 512


def log(*a) -> None:
    print('NORMAL_PROBE', *a, flush=True)


def obj(name: str, bm: bmesh.types.BMesh, at: Vector) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = at
    return ob


def shade(bm: bmesh.types.BMesh, sharp_deg: float) -> None:
    """Всё гладкое, рёбра круче порога — жёсткие (в Blender 4.1+ по ним делятся нормали)."""
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        e.smooth = e.is_manifold and e.calc_face_angle(0.0) <= math.radians(sharp_deg)


def box(dims: Vector) -> bmesh.types.BMesh:
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=dims, verts=bm.verts)
    return bm


def box_high(dims: Vector) -> bmesh.types.BMesh:
    bm = box(dims)
    bmesh.ops.bevel(bm, geom=list(bm.edges) + list(bm.verts), offset=0.003, segments=8, profile=0.5, affect='EDGES')
    shade(bm, 180.0)
    return bm


def lathe(profile: list, steps: int) -> bmesh.types.BMesh:
    """Тело вращения вокруг Z по профилю (r, z)."""
    bm = bmesh.new()
    vs = [bm.verts.new((r, 0.0, z)) for r, z in profile]
    es = [bm.edges.new((a, b)) for a, b in zip(vs, vs[1:])]
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=steps, use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def cyl_profile(r: float, h: float, detail: bool) -> list:
    if not detail:
        return [(0.0, -h), (r, -h), (r, h), (0.0, h)]
    b, g, w = 0.0015, 0.0008, 0.001
    arc = lambda zc, a0, a1: [(r - b + b * math.cos(math.radians(a)), zc + b * math.sin(math.radians(a)))
                              for a in [a0 + (a1 - a0) * i / 6 for i in range(7)]]
    pts = [(0.0, -h)] + arc(-h + b, -90, 0)
    for zc in (-0.015, 0.015):
        pts += [(r, zc - w), (r - g, zc - w), (r - g, zc + w), (r, zc + w)]
    return pts + arc(h - b, 0, 90) + [(0.0, h)]


def blob_high(radius: float) -> bmesh.types.BMesh:
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=6, radius=radius)
    for v in bm.verts:
        n = v.co.normalized()
        v.co += n * 0.0006 * noise.noise(n * 9.0)
    shade(bm, 180.0)
    return bm


def unwrap(ob: bpy.types.Object, angle: float) -> None:
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=0.03)
    bpy.ops.object.mode_set(mode='OBJECT')


def material(name: str, normal_img=None) -> bpy.types.Material:
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.21, 0.21, 0.21, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.45
    if normal_img is not None:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = normal_img
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nt.links.new(t.outputs['Color'], nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    return m


def bake(low: bpy.types.Object, high: bpy.types.Object) -> Path:
    img = bpy.data.images.new(low.name + '_normal', SIZE, SIZE, alpha=False)
    img.colorspace_settings.name = 'Non-Color'
    img.generated_color = (0.5, 0.5, 1.0, 1.0)
    m = material(low.name + '_bake')
    t = m.node_tree.nodes.new('ShaderNodeTexImage')
    t.image = img
    m.node_tree.nodes.active = t
    low.data.materials.clear()
    low.data.materials.append(m)
    sc = bpy.context.scene
    bpy.ops.object.select_all(action='DESELECT')
    high.hide_render = False
    high.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bk = sc.render.bake
    bk.use_selected_to_active = True
    bk.cage_extrusion = EXTRUSION
    bk.max_ray_distance = RAY
    bk.margin = 8
    bk.margin_type = 'EXTEND'
    bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT')
    path = OUT / f'{low.name}_normal.png'
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    log('запечено', path.name)
    return path


def export(objs: list, name: str, tangents: bool) -> None:
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(OUT / name), export_format='GLB', use_selection=True, export_apply=True,
                              export_normals=True, export_texcoords=True, export_tangents=tangents,
                              export_materials='NONE', export_animations=False, export_yup=True)
    log('выгружено', name)


def shots(pairs: list) -> None:
    """Eevee: low с картой и high одним светом — отсчёт «как запеклось» в самом Blender."""
    sc = bpy.context.scene
    for eng in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    sc.render.resolution_x = sc.render.resolution_y = SHOT
    sc.render.film_transparent = True
    sc.view_settings.view_transform = 'Standard'
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    world = bpy.data.worlds.new('probe')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.05, 0.05, 0.05, 1.0)
    sc.world = world
    sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN'))
    sun.data.energy = 3.0
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam'))
    cam.data.angle = math.radians(30)
    sc.collection.objects.link(cam)
    sc.camera = cam
    for low, high in pairs:
        nimg = bpy.data.images.load(str(OUT / f'{low.name}_normal.png'))
        nimg.colorspace_settings.name = 'Non-Color'
        low.data.materials.clear()
        low.data.materials.append(material(low.name + '_view', nimg))
        high.data.materials.clear()
        high.data.materials.append(material(high.name + '_view'))
        c = low.location
        rad = max(low.dimensions) * 0.6
        d = Vector((1.0, -1.3, 0.9)).normalized()
        cam.location = c + d * (rad / math.tan(cam.data.angle / 2) * 1.15)
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        sun.rotation_euler = Vector((0.6, -0.4, 0.7)).normalized().to_track_quat('Z', 'Y').to_euler()
        for o in bpy.data.objects:
            if o.type == 'MESH':
                o.hide_render = True
        for ob, tag in ((low, 'low'), (high, 'high')):
            ob.hide_render = False
            sc.render.filepath = str(OUT / f'blender_{low.name}_{tag}.png')
            bpy.ops.render.render(write_still=True)
            ob.hide_render = True
        log('снимки', low.name)


def main() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 16
    dims = Vector((0.10, 0.04, 0.03))
    pairs = []
    # брусок: low со всеми мягкими рёбрами (самый тяжёлый случай для тангентов) и с жёсткими
    for name, sharp, at in (('box_smooth', 180.0, Vector((0, 0, 0))), ('box_hard', 30.0, Vector((0.2, 0, 0)))):
        bm = box(dims)
        shade(bm, sharp)
        low = obj(name, bm, at)
        unwrap(low, 66.0)
        pairs.append((low, obj(name + '_high', box_high(dims), at)))
    # цилиндр 16 граней против 64 с фасками торцов и двумя канавками
    bm = lathe(cyl_profile(0.012, 0.04, False), 16)
    shade(bm, 40.0)
    low = obj('cyl', bm, Vector((0.4, 0, 0)))
    unwrap(low, 66.0)
    bm = lathe(cyl_profile(0.012, 0.04, True), 64)
    shade(bm, 40.0)
    pairs.append((low, obj('cyl_high', bm, Vector((0.4, 0, 0)))))
    # бугристый шар: кривая поверхность, где тангенты меняются плавно и везде
    bm = bmesh.new()
    bm.loops.layers.uv.new('UVMap')
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=0.03, calc_uvs=True)
    shade(bm, 180.0)
    pairs.append((obj('blob', bm, Vector((0.6, 0, 0))), obj('blob_high', blob_high(0.03), Vector((0.6, 0, 0)))))
    # восьмигранник: рёбра 45° на low мягкие, на high — скруглены фаской 1,5 мм
    bm = lathe(cyl_profile(0.012, 0.04, False), 8)
    shade(bm, 50.0)
    low = obj('oct', bm, Vector((0.8, 0, 0)))
    unwrap(low, 66.0)
    bm = lathe(cyl_profile(0.012, 0.04, False), 8)
    side = [e for e in bm.edges if abs((e.verts[0].co - e.verts[1].co).normalized().z) > 0.99]
    bmesh.ops.bevel(bm, geom=side, offset=0.0015, segments=6, profile=0.5, affect='EDGES')
    shade(bm, 40.0)
    pairs.append((low, obj('oct_high', bm, Vector((0.8, 0, 0)))))
    for low, high in pairs:
        bake(low, high)
    lows = [p[0] for p in pairs]
    export(lows, 'low_tan.glb', True)
    export(lows, 'low_notan.glb', False)
    export([p[1] for p in pairs], 'high.glb', False)
    shots(pairs)
    log('готово', OUT)


main()
