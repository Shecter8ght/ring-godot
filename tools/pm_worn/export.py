"""ПМ «пошарпанный» v01 → модели игры: pm.gltf (в руках, LOD1), pm_mag.gltf (обойма отдельно), глушитель-обвес.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/pm_worn/export.py
Сначала: build_lp.py (сетка), bake.py (карты), pack.py (PNG рядом с моделью).

Оси игры: +Z к дулу, +Y вверх, −X — правая сторона стрелка, начало — пистолетная рукоятка (как у v5/v11).
Узлы деталей (WeaponRig.PART_NAMES) — пустышки без поворота в точке оси; сетки — дочерние: Frame (с щёчкой Grip_Mesh),
Barrel, Slide → Safety, Hammer, Trigger, SlideStop, MagCatch, Magazine → Follower_Mesh, Spring_Mesh, Rounds → Round_01..08
(1 — верхний), Suppressor. Метки Muzzle (хвостовик ствола), MuzzleSuppressed, SightFront, SightRear. Ветка PM_LOD1 —
то же упрощённое (~5 тыс. треугольников). Материалы GAME • <Атлас> • 100 на картах pm_<Атлас>_100_*.png (glTF отдельными
файлами: игра находит рядом с картой цвета маску плёнки _coat — шейдер следов рук).
→ assets/models/weapons/pm/pm.gltf, pm_mag.gltf (магазин с патронами — значок и предмет на полу),
  assets/models/attachments/supp_pm/supp_pm.glb (Body / Body_LOD1, начало — задний торец на оси ствола; карты кладёт pack.py).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

MARK = json.loads(C.MARKERS_FILE.read_text(encoding='utf-8'))
REC = json.loads(C.PARTS_FILE.read_text(encoding='utf-8'))
# Прицельная линия горизонтальна (пристрелка): дно прорези целика — на высоте верха мушки (как у v5).
MARK['SightRear'][2] = MARK['SightFront'][2]
GRIP = Vector((0.0495, 0.0, 0.0495))                       # начало осей игры — как у v5
# Blender (дуло −X, верх +Z, правая сторона +Y) → оси игры до перевода glTF Y-up: поворот +90° вокруг Z.
MAP = Matrix.Rotation(math.radians(90), 4, 'Z') @ Matrix.Translation(-GRIP)
# Сразу в оси игры (для GLB с export_yup=False): (x, y, z) → (−y, z, −x).
TO_GAME = Matrix(((0, -1, 0, 0), (0, 0, 1, 0), (-1, 0, 0, 0), (0, 0, 0, 1)))
LOD_TRIS = 4600
log = lambda *a: C.log('PM_EXPORT', *a)  # noqa: E731
gl = lambda v: [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]  # noqa: E731  — после MAP: оси игры


def tris(o) -> int:
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


def depth(o) -> int:
    d = 0
    while o.parent:
        d += 1
        o = o.parent
    return d


def material(name: str, atlas: str) -> None:
    """Материал на готовых картах pm_<Атлас>_100_* (glTF: карты отдельными файлами, те же имена)."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(p.outputs['BSDF'], out.inputs['Surface'])
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'GameUV'

    def tex(kind: str, cs: str):
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(str(C.ASSET / f'pm_{atlas}_100_{kind}.png'), check_existing=True)
        t.image.colorspace_settings.name = cs
        nt.links.new(uv.outputs['UV'], t.inputs['Vector'])
        return t
    nt.links.new(tex('albedo', 'sRGB').outputs['Color'], p.inputs['Base Color'])
    orm = tex('orm', 'Non-Color')
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(orm.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], p.inputs['Roughness'])
    nt.links.new(sep.outputs['Blue'], p.inputs['Metallic'])
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nm.uv_map = 'GameUV'
    nt.links.new(tex('normal', 'Non-Color').outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], p.inputs['Normal'])
    g = bpy.data.node_groups.get('glTF Material Output') or bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
    if 'Occlusion' not in [s.name for s in g.interface.items_tree if getattr(s, 'in_out', '') == 'INPUT']:
        g.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    gn = nt.nodes.new('ShaderNodeGroup')
    gn.node_tree = g
    nt.links.new(sep.outputs['Red'], gn.inputs['Occlusion'])


def export_gltf(path: Path, objs, separate: bool, yup: bool) -> None:
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    path.parent.mkdir(parents=True, exist_ok=True)
    kw = dict(filepath=str(path), use_selection=True, export_yup=yup, export_apply=True, export_extras=True,
              export_animations=False, export_cameras=False, export_lights=False, export_texcoords=True, export_normals=True,
              export_tangents=True)
    if separate:
        bpy.ops.export_scene.gltf(export_format='GLTF_SEPARATE', export_texture_dir='', export_materials='EXPORT',
                                  export_image_format='AUTO', **kw)
    else:
        bpy.ops.export_scene.gltf(export_format='GLB', export_materials='EXPORT', export_image_format='NONE', **kw)


bpy.context.preferences.use_preferences_save = False
bpy.ops.wm.open_mainfile(filepath=str(C.LP_FILE))
S = bpy.context.scene
for o in list(bpy.data.objects):
    if o.get('bake_only') or o.name in ('RoundChamber', 'JamCase'):
        bpy.data.objects.remove(o, do_unlink=True)
bpy.context.view_layer.update()
for atlas, name in C.MATNAME.items():
    material(name, atlas)

# Пересадка в оси игры: пустышки — только перенос (без поворота), сетки — данные в осях узла.
PM = bpy.data.objects['PM']
world = {o.name: o.matrix_world.copy() for o in bpy.data.objects}
empties = [o for o in bpy.data.objects if o.type == 'EMPTY']
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
new_world = {e.name: (Matrix.Translation((MAP @ world[e.name]).translation) if e != PM else Matrix.Identity(4)) for e in empties}
for e in sorted(empties, key=depth):
    e.matrix_parent_inverse = Matrix.Identity(4)
    e.matrix_basis = (new_world[e.parent.name].inverted() if e.parent else Matrix.Identity(4)) @ new_world[e.name]
for o in meshes:
    o.data.transform(new_world[o.parent.name].inverted() @ MAP @ world[o.name])
    o.matrix_parent_inverse = Matrix.Identity(4)
    o.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
# Щёчка рукояти неподвижна вместе с рамкой: Grip_Mesh — под Frame (игра знает Frame, не Grip).
grip_node = bpy.data.objects['Grip']
gmesh = bpy.data.objects['Grip_Mesh']
gw = gmesh.matrix_world.copy()
gmesh.parent = bpy.data.objects['Frame']
gmesh.matrix_parent_inverse = Matrix.Identity(4)
gmesh.data.transform(bpy.data.objects['Frame'].matrix_world.inverted() @ gw)
gmesh.matrix_basis = Matrix.Identity(4)
bpy.data.objects.remove(grip_node, do_unlink=True)


def marker(name: str, parent, blender_pos) -> None:
    e = bpy.data.objects.new(name, None)
    S.collection.objects.link(e)
    e.empty_display_size = 0.004
    e.parent = parent
    e.matrix_parent_inverse = Matrix.Identity(4)
    e.matrix_basis = parent.matrix_world.inverted() @ Matrix.Translation(MAP @ Vector(blender_pos))


marker('Muzzle', PM, MARK['Muzzle'])
if 'MuzzleSuppressed' in MARK:
    marker('MuzzleSuppressed', PM, MARK['MuzzleSuppressed'])
marker('SightFront', bpy.data.objects['Slide'], MARK['SightFront'])
marker('SightRear', bpy.data.objects['Slide'], MARK['SightRear'])
bpy.context.view_layer.update()

# Глушитель-обвес отдельно (до LOD): копия сетки в осях игры, начало — задний торец на оси ствола.
supp_src = bpy.data.objects['Suppressor_Mesh']
supp_body = supp_src.copy()
supp_body.data = supp_src.data.copy()
supp_body.name = 'Body'
supp_body.data.name = 'Body'
S.collection.objects.link(supp_body)
supp_body.parent = None
seat_game = MAP @ Vector((-0.07922, 0.0, 0.11253))
supp_body.data.transform(Matrix.Translation(-seat_game) @ supp_src.matrix_world)
supp_body.matrix_basis = Matrix.Identity(4)

# LOD1: копия иерархии с суффиксом _LOD1 под PM_LOD1, сетки упрощены пропорционально.
main_meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o != supp_body]
total = sum(tris(o) for o in main_meshes)
lod_root = bpy.data.objects.new('PM_LOD1', None)
S.collection.objects.link(lod_root)
lod_root.parent = PM
copies = {PM.name: lod_root}
for o in sorted([o for o in bpy.data.objects if o.parent is not None and o != lod_root], key=depth):
    if o.name.startswith(('Muzzle', 'SightFront', 'SightRear')):
        continue
    c = o.copy()
    if o.type == 'MESH':
        c.data = o.data.copy()
    S.collection.objects.link(c)
    c.name = o.name + '_LOD1'
    c.parent = copies[o.parent.name]
    c.matrix_parent_inverse = Matrix.Identity(4)
    c.matrix_basis = o.matrix_basis.copy()
    copies[o.name] = c
    if o.type == 'MESH':
        budget = max(12, int(tris(o) * LOD_TRIS / total))
        if tris(c) > budget:
            C.activate([c])
            d = c.modifiers.new('lod', 'DECIMATE')
            d.ratio = budget / tris(c)
            d.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=d.name)
bpy.context.view_layer.update()
lod_total = sum(tris(o) for o in bpy.data.objects if o.type == 'MESH' and o.name.endswith('_LOD1'))
main_total = sum(tris(o) for o in main_meshes)
pm_objs = [o for o in bpy.data.objects if o != supp_body]
export_gltf(C.ASSET / 'pm.gltf', pm_objs, separate=True, yup=True)

# Обойма отдельно: магазин с патронами как есть (ось — как в оружии), для значка и предмета на полу.
mag_root = bpy.data.objects['Magazine']
mag_objs = [mag_root] + [o for o in bpy.data.objects if o.name != mag_root.name and any(p.name == mag_root.name for p in [o.parent, getattr(o.parent, 'parent', None)] if p is not None)]
mag_objs = [o for o in mag_objs if not o.name.endswith('_LOD1')]
export_gltf(C.ASSET / 'pm_mag.gltf', mag_objs, separate=True, yup=True)

# Глушитель-обвес: Body / Body_LOD1 в осях игры без глушителя в сборке (export_yup=False → данные уже в осях игры).
# Данные уже после MAP (поворот Z), остаётся перевод glTF Y-up вручную: (x, y, z) → (x, z, −y).
YUP = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0), (0, 0, 0, 1)))
supp_body.data.transform(YUP)
supp_root = bpy.data.objects.new('supp_pm', None)
S.collection.objects.link(supp_root)
supp_body.parent = supp_root
supp_lod = supp_body.copy()
supp_lod.data = supp_body.data.copy()
supp_lod.name = 'Body_LOD1'
S.collection.objects.link(supp_lod)
supp_lod.parent = supp_root
C.activate([supp_lod])
d = supp_lod.modifiers.new('lod', 'DECIMATE')
d.ratio = 0.3
d.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier=d.name)
for o in (supp_body, supp_lod):
    o.data.materials.clear()
    mat = bpy.data.materials.get('supp_pm') or bpy.data.materials.new('supp_pm')
    o.data.materials.append(mat)
export_gltf(C.ATT_SUPP / 'supp_pm.glb', [supp_root, supp_body, supp_lod], separate=False, yup=False)
bb = [v.co for v in supp_body.data.vertices]
supp_report = dict(source=str(C.SRC_SUPP), triangles=dict(Body=tris(supp_body), Body_LOD1=tris(supp_lod)),
                   axis='X left, Y up, Z forward; начало — задний торец переходника на оси ствола',
                   bounds_m={'min': [round(min(c[i] for c in bb), 4) for i in range(3)], 'max': [round(max(c[i] for c in bb), 4) for i in range(3)]},
                   states=[100], texture_size=C.SIZE['Suppressor'])
(C.ATT_SUPP / 'manifest.json').write_text(json.dumps(supp_report, ensure_ascii=False, indent=2), encoding='utf-8', newline='\n')

bpy.ops.wm.save_as_mainfile(filepath=str(C.WORK / 'lp/PM_Worn_export.blend'))
report = dict(schema='pm_worn_game', source=str(C.LP_FILE), triangles=dict(first_person=main_total, lod1=lod_total, pistol=REC['triangles']['pistol']),
              axes='+Z дуло, +Y верх, −X правая сторона стрелка; начало — рукоятка (как v5)',
              markers_game_m={n: gl(MAP @ Vector(MARK[n])) for n in ('Muzzle', 'MuzzleSuppressed', 'SightFront', 'SightRear') if n in MARK},
              pivots_game_m={k.split(':')[1]: gl(MAP @ Vector(v)) for k, v in MARK.items() if k.startswith('pivot:')},
              k1_mount_game_m=gl(MAP @ Vector(MARK['K1Mount'])) if 'K1Mount' in MARK else None,
              k1_lens_game_m=gl(MAP @ Vector(MARK['K1Lens'])) if 'K1Lens' in MARK else None,
              materials=list(C.MATNAME.values()))
(C.ASSET / 'pm.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
log('SAVED', C.ASSET / 'pm.gltf', 'tris', main_total, 'lod1', lod_total, 'supp', supp_report['triangles'])
