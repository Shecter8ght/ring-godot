"""ПМ / КОРС-9 v11 → игровая мировая модель assets/models/weapons/pm/pm.glb (без прицела ЗОРИН).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/export_pm_v11.py
Сначала: _asset_src/pm_game/work/build_lp.py (сетка), bake_state.py (карты), tools/pm_v11_pack_maps.py.

Оси игры: +Z к дулу, +Y вверх, −X — правая сторона стрелка, начало — пистолетная рукоятка (как у v5).
Узлы деталей (WeaponRig.PART_NAMES) — пустышки без поворота в точке оси; сетки — дочерние.
Frame (с щёчкой рукояти Grip_Mesh), Barrel, Slide → Safety, Hammer, Trigger, SlideStop, MagCatch,
Magazine → Follower_Mesh, Spring_Mesh, Rounds → Round_01..08 (1 — верхний), Suppressor (глушитель 60%). Метки Muzzle,
MuzzleSuppressed, SightFront, SightRear. Ветка PM_LOD1 — то же упрощённое (~5 тыс. треугольников).
Материалы GAME • Steel • 100 / GAME • Grip • 100 (износ 60/20 — states/pm_*), GAME • Magazine • 60,
GAME • Ammo • 60. Патрон в патроннике и гильза задержки здесь не экспортируются — они во вьюмодели.
"""
from pathlib import Path
import json, math
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / '_asset_src/pm_game'
OUT = ROOT / 'assets/models/weapons/pm'
STATES = OUT / 'states'
MARK = json.loads((SRC / 'lp/markers.json').read_text(encoding='utf-8'))
# Прицельная линия горизонтальна (пристрелка): дно прорези целика — на высоте верха мушки (как у v5).
MARK['SightRear'][2] = MARK['SightFront'][2]
GRIP = Vector((0.0495, 0.0, 0.0495))                       # начало осей игры — как у v5
# Blender (дуло −X, верх +Z, правая сторона +Y) → оси игры до перевода glTF Y-up: поворот +90° вокруг Z.
MAP = Matrix.Rotation(math.radians(90), 4, 'Z') @ Matrix.Translation(-GRIP)
LOD_TRIS = 5200
log = lambda *a: print('PM_EXPORT', *a, flush=True)

bpy.context.preferences.use_preferences_save = False
bpy.ops.wm.open_mainfile(filepath=str(SRC / 'lp/PM_Game_LP_v01.blend'))
S = bpy.context.scene
for o in list(bpy.data.objects):
    if o.get('bake_only') or o.name in ('RoundChamber', 'JamCase'):
        bpy.data.objects.remove(o, do_unlink=True)
bpy.context.view_layer.update()


def tris(o):
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


# Материалы на готовых картах (100 — встраиваются; 60/20 игра ставит из states/).
def material(name, atlas, state, coat=False):
    m = bpy.data.materials[name]
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(p.outputs['BSDF'], out.inputs['Surface'])
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'GameUV'

    def tex(kind, cs):
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(str(STATES / f'pm_{atlas}_{state}_{kind}.png'), check_existing=True)
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
    # glTF: AO из R той же картинки (occlusion) — через узел glTF Material Output
    g = bpy.data.node_groups.get('glTF Material Output') or bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
    if 'Occlusion' not in [s.name for s in g.interface.items_tree if getattr(s, 'in_out', '') == 'INPUT']:
        g.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    gn = nt.nodes.new('ShaderNodeGroup')
    gn.node_tree = g
    nt.links.new(sep.outputs['Red'], gn.inputs['Occlusion'])
    if coat:
        p.inputs['Coat Weight'].default_value = 0.65
        p.inputs['Coat Roughness'].default_value = 0.06


material('GAME • Steel • 100', 'Steel', '100')
material('GAME • Grip • 100', 'Grip', '100', coat=True)
material('GAME • Magazine • 60', 'Magazine', '60')
material('GAME • Ammo • 60', 'Ammo', '60')
material('GAME • Suppressor • 60', 'Suppressor', '60')

# Пересадка в оси игры: пустышки — только перенос (без поворота), сетки — данные в осях узла.
PM = bpy.data.objects['PM']
world = {o.name: o.matrix_world.copy() for o in bpy.data.objects}
empties = [o for o in bpy.data.objects if o.type == 'EMPTY']
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
new_world = {}
for e in empties:
    new_world[e.name] = Matrix.Translation((MAP @ world[e.name]).translation) if e != PM else Matrix.Identity(4)


def depth(o):
    d = 0
    while o.parent:
        d += 1
        o = o.parent
    return d


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


def marker(name, parent, blender_pos):
    e = bpy.data.objects.new(name, None)
    S.collection.objects.link(e)
    e.empty_display_size = 0.004
    e.parent = parent
    e.matrix_parent_inverse = Matrix.Identity(4)
    w = MAP @ Vector(blender_pos)
    e.matrix_basis = parent.matrix_world.inverted() @ Matrix.Translation(w)
    return e


marker('Muzzle', PM, MARK['Muzzle'])
if 'MuzzleSuppressed' in MARK:
    marker('MuzzleSuppressed', PM, MARK['MuzzleSuppressed'])
marker('SightFront', bpy.data.objects['Slide'], MARK['SightFront'])
marker('SightRear', bpy.data.objects['Slide'], MARK['SightRear'])
bpy.context.view_layer.update()

# LOD1: копия иерархии с суффиксом _LOD1 под PM_LOD1, сетки упрощены пропорционально.
total = sum(tris(o) for o in bpy.data.objects if o.type == 'MESH')
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
            bpy.ops.object.select_all(action='DESELECT')
            c.select_set(True)
            bpy.context.view_layer.objects.active = c
            d = c.modifiers.new('lod', 'DECIMATE')
            d.ratio = budget / tris(c)
            d.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=d.name)
lod_root.hide_render = False
bpy.context.view_layer.update()
lod_total = sum(tris(o) for o in bpy.data.objects if o.type == 'MESH' and o.name.endswith('_LOD1'))
main_total = sum(tris(o) for o in bpy.data.objects if o.type == 'MESH' and not o.name.endswith('_LOD1'))
bpy.ops.object.select_all(action='DESELECT')
for o in bpy.data.objects:
    o.hide_set(False)
    o.select_set(True)
glb = OUT / 'pm.glb'
bpy.ops.export_scene.gltf(filepath=str(glb), export_format='GLB', use_selection=True, export_yup=True, export_apply=True,
                          export_extras=True, export_animations=False, export_cameras=False, export_lights=False,
                          export_image_format='AUTO')
bpy.ops.wm.save_as_mainfile(filepath=str(SRC / 'lp/PM_Game_export_v01.blend'))
gl = lambda v: [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]
report = dict(schema='pm_v11_game', source=str(SRC / 'lp/PM_Game_LP_v01.blend'), triangles=dict(first_person=main_total, lod1=lod_total),
              axes='+Z дуло, +Y верх, −X правая сторона стрелка; начало — рукоятка (как v5)',
              markers_game_m={n: gl(MAP @ Vector(MARK[n])) for n in ('Muzzle', 'MuzzleSuppressed', 'SightFront', 'SightRear') if n in MARK},
              pivots_game_m={k.split(':')[1]: gl(MAP @ Vector(v)) for k, v in MARK.items() if k.startswith('pivot:')},
              materials=['GAME • Steel • 100', 'GAME • Grip • 100', 'GAME • Magazine • 60', 'GAME • Ammo • 60', 'GAME • Suppressor • 60'])
(OUT / 'pm.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
log('SAVED', glb, 'tris', main_total, 'lod1', lod_total)
