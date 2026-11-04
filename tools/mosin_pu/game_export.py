"""Мосин 1891/30 ПУ → игровые файлы assets/models/weapons/mosin_pu/ (после game_lp.py, game_bake.py, game_pack.py).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/mosin_pu/game_export.py -- [fp|detail]
  fp:
  mosin_pu.glb           — винтовка с основанием кронштейна, ~20 000 треугольников (в руках) + ветка Mosin_PU_LOD1 (мировая);
  attachments/pu_mosin/pu_mosin.gltf — прицел ПУ на кронштейне, съёмный обвес optic_pu_01 (решение владельца 2026-11-04):
                           начало — ось узла Mount_Bracket (на винтовке — сокет optic_primary); сетки Body_Bracket,
                           Body_Scope, Body_Lens и их _LOD1 (WeaponMods._model_part); карты — общие с винтовкой
                           (атлас Optic: ссылки на mosin_pu_Optic_20_*.png, копий нет); pu_mosin.json — окуляр и треугольники;
  mosin_pu_round.glb     — патрон 7,62×54R (Round) и стреляная гильза (SpentCase);
  mosin_pu_collision.glb — упрощённая физика: выпуклые оболочки «-convcolonly» (Godot делает из них StaticBody3D;
                           отдельным файлом — чтобы у модели в руках не было физики);
  mosin_pu.json          — оси, метки, оси вращения, треугольники, карты, как двигать затвор (проверки).
  detail:
  mosin_pu_detail.glb    — подробная (~109 тыс.) — разглядывать вблизи, тот же порядок узлов и меток; mosin_pu_detail.json.
Оси игры: +Z к дулу, +Y вверх, −X — правая сторона стрелка; начало — середина шейки ложи, где держит правая рука.
Узлы — пустышки без поворота в точке оси, сетки — дочерние: Frame (Frame_Wood, Frame_Steel), Bolt → Bolt_Bar_Mesh,
Bolt_Rotor (поворот вокруг оси канала — ось Z узла), Bolt_Cocking; Interrupter; Trigger; Follower;
RearSight_Leaf → RearSight_Slider; Mount_Base; Mount_Bracket → Scope (Scope_Body_Mesh, Scope_Lens_Mesh).
Метки: Muzzle, SightFront, SightRear (на планке целика), ScopeEye (центр заднего торца окуляра), ScopeFront.
Сетки «Magazine*» и «Stock*» не называются нарочно: так игра помечает съёмные магазин и приклад, у Мосина их нет.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_rifle as R  # noqa: E402  (ход затвора — одно место)

ROOT = Path(__file__).resolve().parents[2]
VARIANT = (sys.argv[sys.argv.index('--') + 1:] + ['fp'])[0] if '--' in sys.argv else 'fp'
WORK = ROOT / '_asset_src/mosin_pu_game' / VARIANT
MAPS = WORK / 'maps/game'
NAME = 'mosin_pu' if VARIANT == 'fp' else 'mosin_pu_detail'
# fp — в игру; detail — в библиотеку модели (игровые версии и комплект на продажу), в репозиторий игры не идёт
LIB_GAME = Path('E:/Models Blender/WEAPONS/Мосин — винтовка и узлы/models/06_Игровая')
OUT = ROOT / 'assets/models/weapons/mosin_pu' if VARIANT == 'fp' else LIB_GAME / 'detail'
OUT.mkdir(parents=True, exist_ok=True)
REC = json.loads((WORK / 'lp/parts.json').read_text(encoding='utf-8'))
GRIP_X = -0.240                 # середина хвата шейки (спуск — x −152 мм, хвост скобы — −206)
LOD_TRIS = 5000                 # мировая модель fp (чужие руки, на земле); у detail ветки LOD нет
COLLISION = {                   # оболочка → (детали, x от, x до), м
    'Col_Butt': (('Frame_Wood_Stock', 'Frame_Steel'), -0.60, -0.30),
    'Col_Wrist': (('Frame_Wood_Stock', 'Frame_Steel', 'Bolt_Rotor_Mesh', 'Bolt_Cocking_Mesh', 'Trigger_Mesh'), -0.30, 0.03),
    'Col_Fore': (('Frame_Wood_Stock', 'Frame_Wood_Handguard', 'Frame_Steel'), 0.03, 0.62),
    'Col_Muzzle': (('Frame_Steel',), 0.62, 0.80),
    # прицел съёмный (обвес optic_pu_01): у винтовки — только основание кронштейна на ствольной коробке
    'Col_Optic': (('Mount_Base_Mesh',), -1.0, 1.0),
}
PU_OUT = ROOT / 'assets/models/attachments/pu_mosin'
PU_NAMES = {'Mount_Bracket_Mesh': 'Body_Bracket', 'Scope_Body_Mesh': 'Body_Scope', 'Scope_Lens_Mesh': 'Body_Lens'}
HULL_VERTS = 48
log = lambda *a: print('MOSIN_EXPORT', *a, flush=True)

bpy.context.preferences.use_preferences_save = False
bpy.ops.wm.open_mainfile(filepath=str(WORK / 'lp/Mosin_Game_LP.blend'))
S = bpy.context.scene
# пустышки узлов создавались, пока исходник держал те же имена (Bolt, Trigger…) — у них «.001»; игре нужны точные
for o in list(bpy.data.objects):
    base = o.name.split('.')[0]
    if o.type == 'EMPTY' and base != o.name and base not in bpy.data.objects:
        o.name = base


def tris(o) -> int:
    o.data.calc_loop_triangles()
    return len(o.data.loop_triangles)


def select_only(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


# ---------------------------------------------------------------- материалы на готовых картах
def material(name: str, tag: str, lens: bool = False) -> None:
    m = bpy.data.materials[name]
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(p.outputs['BSDF'], out.inputs['Surface'])
    uv = nt.nodes.new('ShaderNodeUVMap')
    uv.uv_map = 'GameUV'

    def tex(kind, cs):
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(str(MAPS / f'{tag}_{kind}.png'), check_existing=True)
        t.image.colorspace_settings.name = cs
        nt.links.new(uv.outputs['UV'], t.inputs['Vector'])
        return t
    if lens:
        # стекло: тёмное просветлённое (лёгкий синий налёт), отражает окружение; пыль — шероховатостью из атласа прицела.
        # Непрозрачное: при прицеливании окуляр закрывает картинка оптики (CameraRig — отдельная камера кругом поверх
        # экрана по метке ScopeEye и радиусу окуляра), снаружи настоящая оптика тоже тёмная, а прозрачность во вьюмодели
        # даёт ошибки сортировки. Белый цвет стекла исходника рассчитан на пропускание Cycles — в игре был молочный диск.
        p.inputs['Base Color'].default_value = (0.010, 0.013, 0.020, 1.0)
    else:
        nt.links.new(tex('albedo', 'sRGB').outputs['Color'], p.inputs['Base Color'])
    orm = tex('orm', 'Non-Color')
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(orm.outputs['Color'], sep.inputs['Color'])
    nt.links.new(sep.outputs['Green'], p.inputs['Roughness'])
    nt.links.new(sep.outputs['Blue'], p.inputs['Metallic'])
    if not lens:
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
    if lens:
        p.inputs['Coat Weight'].default_value = 0.0


material('GAME • Wood • 20', 'Wood_20')
material('GAME • Steel • 20', 'Steel_20')
material('GAME • Optic • 20', 'Optic_20')
material('GAME • Lens • 20', 'Optic_20', lens=True)
material('GAME • Ammo', 'Ammo')

# ---------------------------------------------------------------- неподвижное дерево — одной сеткой
O = bpy.data.objects
bpy.ops.object.select_all(action='DESELECT')
O['Frame_Wood_Handguard'].select_set(True)
O['Frame_Wood_Stock'].select_set(True)
bpy.context.view_layer.objects.active = O['Frame_Wood_Stock']
bpy.ops.object.join()
wood = bpy.context.view_layer.objects.active
wood.name = wood.data.name = 'Frame_Wood'
bpy.context.view_layer.update()

# середина шейки на x = GRIP_X: центр сечения ложи
sec = [wood.matrix_world @ v.co for v in wood.data.vertices if abs((wood.matrix_world @ v.co).x - GRIP_X) < 0.004]
GRIP = Vector((GRIP_X, 0.0, (min(p.z for p in sec) + max(p.z for p in sec)) / 2))
log('grip origin mm', [round(c * 1000, 1) for c in GRIP])
# оси винтовки (дуло +X, верх +Z, правая сторона −Y) → оси игры до перевода glTF в Y-up: поворот −90° вокруг Z
MAP = Matrix.Rotation(math.radians(-90), 4, 'Z') @ Matrix.Translation(-GRIP)

def hull(bm) -> None:
    """Выпуклая оболочка на месте: внутренние и лишние вершины удаляются (convex_hull их оставляет)."""
    res = bmesh.ops.convex_hull(bm, input=bm.verts[:])
    drop = list({g for g in res['geom_interior'] + res['geom_unused'] if isinstance(g, bmesh.types.BMVert)})
    bmesh.ops.delete(bm, geom=drop, context='VERTS')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')


# ---------------------------------------------------------------- коллизия — по игровой сетке в покое
col_objs = []
for name, (parts, x0, x1) in COLLISION.items():
    pts = []
    for part in parts:
        o = O['Frame_Wood'] if part.startswith('Frame_Wood') else O[part]
        pts += [o.matrix_world @ v.co for v in o.data.vertices if x0 <= (o.matrix_world @ v.co).x < x1]
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(MAP @ p)
    hull(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    co = bpy.data.objects.new(name + '-convcolonly', me)
    S.collection.objects.link(co)
    if len(me.vertices) > HULL_VERTS:
        select_only(co)
        d = co.modifiers.new('d', 'DECIMATE')
        d.ratio = HULL_VERTS / len(me.vertices)
        bpy.ops.object.modifier_apply(modifier=d.name)
        bm = bmesh.new()
        bm.from_mesh(co.data)
        hull(bm)
        bm.to_mesh(co.data)
        bm.free()
    col_objs.append(co)
    log('collision', name, len(co.data.vertices), 'verts')

# ---------------------------------------------------------------- пересадка в оси игры
rifle = [o for o in O if o.type in ('MESH', 'EMPTY') and not o.name.startswith(('Round', 'Col_'))]
ammo = [o for o in O if o.name.startswith('Round')]
world = {o.name: o.matrix_world.copy() for o in rifle + ammo}


def depth(o) -> int:
    d = 0
    while o.parent:
        d += 1
        o = o.parent
    return d


def regraft(objs, mapping):
    new_world = {}
    for e in objs:
        if e.type == 'EMPTY':
            new_world[e.name] = Matrix.Translation((mapping @ world[e.name]).translation) if e.parent else Matrix.Identity(4)
    for e in sorted([o for o in objs if o.type == 'EMPTY'], key=depth):
        e.matrix_parent_inverse = Matrix.Identity(4)
        e.matrix_basis = (new_world[e.parent.name].inverted() if e.parent else Matrix.Identity(4)) @ new_world[e.name]
    for o in objs:
        if o.type == 'MESH':
            o.data.transform(new_world[o.parent.name].inverted() @ mapping @ world[o.name])
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


regraft(rifle, MAP)
# патрон: донце в начале, ось +X → +Z игры
AMMO_MAP = Matrix.Rotation(math.radians(-90), 4, 'Z')
regraft(ammo, AMMO_MAP)
root = O['Mosin_PU']


def marker(name: str, parent, rifle_mm) -> None:
    e = bpy.data.objects.new(name, None)
    S.collection.objects.link(e)
    e.empty_display_size = 0.006
    e.parent = parent
    e.matrix_parent_inverse = Matrix.Identity(4)
    e.matrix_basis = parent.matrix_world.inverted() @ Matrix.Translation(MAP @ (Vector(rifle_mm) * 0.001))


MK = REC['markers_mm']
marker('Muzzle', root, MK['Muzzle'])
marker('SightFront', O['Frame'], MK['SightFront'])
marker('SightRear', O['RearSight_Leaf'], MK['SightRear'])
marker('ScopeEye', O['Scope'], MK['ScopeEye'])
marker('ScopeFront', O['Scope'], MK['ScopeFront'])
bpy.context.view_layer.update()

# ---------------------------------------------------------------- патрон и гильза — по сетке на каждый
merged = {}
for name, parts in (('Round', ('Round_Case', 'Round_Bullet', 'Round_Primer')), ('SpentCase', ('Round_Case', 'Round_Primer'))):
    me = bpy.data.meshes.new(name + '_Mesh')
    bm = bmesh.new()
    for part in parts:
        src = O[part].data.copy()
        src.transform(O[part].matrix_world)
        bm.from_mesh(src)                                # одна развёртка GameUV и один материал у всех частей
        bpy.data.meshes.remove(src)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(O['Round_Case'].data.materials[0])
    merged[name] = me
for part in ('Round_Case', 'Round_Bullet', 'Round_Primer', 'Round'):
    bpy.data.objects.remove(O[part], do_unlink=True)
for name, me in merged.items():
    e = bpy.data.objects.new(name, None)
    S.collection.objects.link(e)
    j = bpy.data.objects.new(name + '_Mesh', me)
    S.collection.objects.link(j)
    j.parent = e
bpy.context.view_layer.update()

# ---------------------------------------------------------------- LOD1: копия иерархии, сетки упрощены (только fp)
rifle_meshes = [o for o in O if o.type == 'MESH' and o.name not in ('Round_Mesh', 'SpentCase_Mesh') and not o.name.startswith('Col_')]
main_total = sum(tris(o) for o in rifle_meshes)
lod_root = bpy.data.objects.new('Mosin_PU_LOD1', None)
S.collection.objects.link(lod_root)
lod_root.parent = root
copies = {root.name: lod_root} if VARIANT == 'fp' else {}
MARKERS = ('Muzzle', 'SightFront', 'SightRear', 'ScopeEye', 'ScopeFront')
for o in sorted([o for o in O if o.parent is not None and o != lod_root and not o.name.startswith(('Round', 'SpentCase', 'Col_'))], key=depth):
    if o.name.startswith(MARKERS) or o.parent.name not in copies:
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
        budget = max(12, int(tris(o) * LOD_TRIS / main_total))
        if tris(c) > budget:
            select_only(c)
            d = c.modifiers.new('lod', 'DECIMATE')
            d.ratio = budget / tris(c)
            d.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=d.name)
bpy.context.view_layer.update()

# ---------------------------------------------------------------- прицел ПУ на кронштейне — отдельный обвес (только fp)
# кронштейн с трубой (и их ветка LOD1) уходят из винтовки под свой корень; начало — ось узла Mount_Bracket, то есть
# на винтовке он встаёт ровно туда, где стоял (сокет optic_primary = положение узла). Основание — у винтовки.
pu_root = None
pu_at = Vector((0.0, 0.0, 0.0))
if VARIANT == 'fp':
    pu_root = bpy.data.objects.new('PU_Mosin', None)
    S.collection.objects.link(pu_root)
    pu_at = O['Mount_Bracket'].matrix_world.translation.copy()
    for name in ('Mount_Bracket', 'Mount_Bracket_LOD1'):
        n = O[name]
        mw = n.matrix_world.copy()
        n.parent = pu_root
        n.matrix_parent_inverse = Matrix.Identity(4)
        n.matrix_basis = Matrix.Translation(-pu_at) @ mw
    for src, dst in PU_NAMES.items():
        O[src + '_LOD1'].name = dst + '_LOD1'
        O[src].name = dst
    bpy.context.view_layer.update()
pu_meshes = [o for o in pu_root.children_recursive if o.type == 'MESH'] if pu_root is not None else []
rifle_meshes = [o for o in rifle_meshes if o not in pu_meshes]
lod_total = sum(tris(o) for o in bpy.data.objects if o.type == 'MESH' and o.name.endswith('_LOD1') and o not in pu_meshes)


def subtree(o):
    out = [o]
    for c in o.children:
        out += subtree(c)
    return out


def gltf_out(path: Path, fmt: str) -> None:
    # запись файла на E: изредка срывается OSError Errno 22 (2026-11-04, дважды, каждый раз другой файл; повтор
    # проходит) — несколько попыток с паузой
    for attempt in range(4):
        try:
            bpy.ops.export_scene.gltf(filepath=str(path), export_format=fmt, use_selection=True, export_yup=True,
                                      export_apply=True, export_extras=True, export_animations=False,
                                      export_cameras=False, export_lights=False, export_image_format='AUTO')
            return
        except RuntimeError as e:
            if 'Errno 22' not in str(e) or attempt == 3:
                raise
            log('retry', path.name, attempt + 1)
            time.sleep(3.0)


def export(path: Path, objs) -> None:
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.hide_set(False)
        o.select_set(True)
    gltf_out(path, 'GLB')
    log('exported', path.name)


def export_pu() -> None:
    """Прицел ПУ — .gltf с отдельными картами; Blender кладёт рядом копии атласа Optic, они заменяются ссылками на карты
    винтовки (Godot берёт уже импортированные mosin_pu_Optic_20_*.png — один атлас в памяти на винтовку и прицел)."""
    PU_OUT.mkdir(parents=True, exist_ok=True)
    path = PU_OUT / 'pu_mosin.gltf'
    bpy.ops.object.select_all(action='DESELECT')
    for o in subtree(pu_root):
        o.hide_set(False)
        o.select_set(True)
    gltf_out(path, 'GLTF_SEPARATE')
    g = json.loads(path.read_text(encoding='utf-8'))
    for im in g.get('images', []):
        local = PU_OUT / im['uri']
        shared = f'{NAME}_{Path(im["uri"]).stem}.png'
        if not (OUT / shared).exists():
            raise SystemExit(f'нет карты винтовки {shared} — сначала импорт mosin_pu.glb в Godot')
        im['uri'] = '../../weapons/mosin_pu/' + shared
        im.pop('mimeType', None)
        local.unlink(missing_ok=True)
    path.write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    log('exported', path.name, [im['uri'] for im in g.get('images', [])])


if VARIANT == 'detail':
    bpy.data.objects.remove(lod_root, do_unlink=True)
export(OUT / f'{NAME}.glb', subtree(root))
if VARIANT == 'fp':
    export(OUT / 'mosin_pu_round.glb', subtree(O['Round']) + subtree(O['SpentCase']))
    export(OUT / 'mosin_pu_collision.glb', col_objs)
    export_pu()
bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'lp/Mosin_Game_export.blend'))

gl = lambda v: [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]          # Blender (Z-up) → glTF (Y-up)
game = lambda mm: gl(MAP @ (Vector(mm) * 0.001))
if VARIANT == 'fp':
    pu_rel = lambda name: gl(O[name].matrix_world.translation)   # в осях прицела-обвеса: его корень — в начале сцены
    (PU_OUT / 'pu_mosin.json').write_text(json.dumps(dict(
        schema='mosin_pu_scope_v01', source=str(WORK / 'lp/Mosin_Game_LP.blend'), rifle=f'{NAME}.glb',
        axes='+Z к дулу, +Y верх, −X правая сторона стрелка; начало — ось кронштейна (узел Mount_Bracket); метры',
        socket_on_rifle_m=gl(pu_at),
        triangles=dict(first_person=sum(tris(o) for o in pu_meshes if not o.name.endswith('_LOD1')),
                       lod1=sum(tris(o) for o in pu_meshes if o.name.endswith('_LOD1'))),
        meshes={o.name: tris(o) for o in pu_meshes},
        markers_m={k: pu_rel(k) for k in ('ScopeEye', 'ScopeFront')},
        # центр заднего торца окуляра (метка ScopeEye) и радиус его стекла — для картинки оптики (CameraRig)
        ocular_r_m=0.0118, maps='атлас Optic винтовки: ../../weapons/mosin_pu/mosin_pu_Optic_20_*.png'),
        ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
report = dict(
    schema='mosin_pu_game_v02', variant=VARIANT, source_lp=str(WORK / 'lp/Mosin_Game_LP.blend'), sources=REC['sources'],
    state='20 % (особый ствол: одно состояние; текстуры приняты владельцем 2026-10-17, на форме v08 — tex20_v03)',
    axes='+Z дуло, +Y верх, −X правая сторона стрелка; начало — середина шейки ложи (хват правой рукой); метры',
    grip_origin_rifle_mm=[round(c * 1000, 2) for c in GRIP],
    triangles=dict(first_person=sum(tris(o) for o in rifle_meshes), lod1=lod_total, round=tris(O['Round_Mesh']),
                   spent_case=tris(O['SpentCase_Mesh'])),
    scope='съёмный обвес optic_pu_01: assets/models/attachments/pu_mosin/pu_mosin.gltf (pu_mosin.json)',
    meshes={o.name: tris(o) for o in rifle_meshes},
    markers_game_m={k: game(v) for k, v in MK.items()},
    pivots_game_m={k: game(v) for k, v in REC['pivots_mm'].items() if k not in ('Mosin_PU', 'Round', 'Frame')},
    rig={'Bolt': f'ход назад по −Z узла: 0 … −{R.BOLT_TRAVEL / 1000:.3f} м (отведён до упора)'.replace('.', ','),
         'Bolt_Rotor': 'поворот вокруг оси канала (Z узла): 0 закрыт … открыт — рукоять вверх на 90° (в осях винтовки −90° вокруг +X)',
         'Bolt_Cocking': 'взвод поворотом: смещение назад (−Z) на 0,0095 м × min(поворот/90°, 1); взведён после закрытия',
         'Interrupter': 'отсечка-отражатель: внутрь коробки на 0,0028 м (в покое), выходит (по +X игры к 0) за 2 мм до заднего '
                        'положения затвора: x затвора < −0,0564 м',
         'Trigger': 'ось спуска — начало узла', 'RearSight_Leaf': 'ось шарнира колодки — начало узла (подъём — поворот вокруг X)',
         'RearSight_Slider': 'хомутик скользит по планке', 'Follower': 'подаватель (магазин без патронов)'},
    materials={'GAME • Wood • 20': 'Wood_20', 'GAME • Steel • 20': 'Steel_20', 'GAME • Optic • 20': 'Optic_20',
               'GAME • Lens • 20': 'тёмное просветлённое стекло, непрозрачное (в прицеле — картинка оптики), шероховатость — Optic_20 ORM', 'GAME • Ammo': 'Ammo'},
    uv_margin_px=REC.get('uv_margin_px', 8),
    texel_px_mm=REC['texel_px_mm'], hidden_area_share=REC['hidden_area_share'],
    collision=list(COLLISION), skipped=REC['skipped'],
    # для подключения оптики (CameraRig: meta ocular / ocular_r): центр — метка ScopeEye, радиус стекла окуляра
    ocular_r_m=0.0118, removed_hidden_tris=REC.get('removed_hidden_tris', 0))
(OUT / f'{NAME}.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
log('SAVED', 'tris', main_total, 'lod1', lod_total)
