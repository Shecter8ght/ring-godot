"""Обойма Мосина на 5 патронов → игровая сетка, карты и GLB (заряжание обоймой, когда прицел ПУ снят).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/mosin_pu/game_clip.py
Источник — текстурированная обойма библиотеки (принята владельцем) models/05_Обойма/Mosin_StripperClip_v01_tex_v01.blend:
UCUPaint, 47 тыс. треугольников, лист 0,5 мм, почти весь плоский. Игровая сетка — слияние почти плоских граней (порог
ANGLE, ~600 треугольников, отклонение ~0,15 мм; вырезы под язычками остаются сквозными), своя развёртка и атлас Clip
512 — как у патрона: одно состояние, без маски износа; albedo, normal, ORM (R — AO самой сетки, G — шероховатость,
B — металл). Винтовка и патрон этим скриптом не трогаются.
Оси: начало — середина спинки изнутри (как у исходника); в файле экспорта и в GLB — оси игры, как у mosin_pu.glb:
+Z — к дулу (патроны в обойме — пулями туда), +Y — вверх вдоль обоймы, −X — правая сторона стрелка. В направляющих
коробки начало обоймы стоит в точке seat_game_m (mosin_pu_clip.json; от начала винтовки — середины шейки ложи).
→ assets/models/weapons/mosin_pu/mosin_pu_clip.glb, mosin_pu_clip.json;
  _asset_src/mosin_pu_game/fp/lp/Mosin_Clip_export.blend — Clip_Mesh для клипов рук (оси экспорта винтовки: дуло −Y);
  _asset_src/mosin_pu_game/fp/maps/{raw,game}/Clip_*.png (не в git).
После — `tools/godot.cmd --headless --import`, `python -X utf8 tools/mosin_pu/game_imports.py`, ещё раз --import.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_rifle as R  # noqa: E402  (где стоят направляющие обоймы — одно место)

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / '_asset_src/mosin_pu_game/fp'
SRC = Path('E:/Models Blender/WEAPONS/Мосин — винтовка и узлы/models/05_Обойма/Mosin_StripperClip_v01_tex_v01.blend')
OUT = ROOT / 'assets/models/weapons/mosin_pu'
RAW, GAME = WORK / 'maps/raw', WORK / 'maps/game'
SIZE = 512
ANGLE = 15.0                       # грани, сходящиеся круче, — сливаются (15°: ~600 треугольников, отклонение 0,15 мм)
SHARP = 60.0                       # жёсткое ребро и шов развёртки (как в game_lp.py)
MARGIN_PX = 8
SAMPLES = {'color': 16, 'mrh': 16, 'normal': 8, 'cov': 1, 'ao': 64}
# Обойма в направляющих (оси винтовки, мм; как в clip_guide_check.py): спинка — в гнёздах стоек, нижние концы стенок
# (наружная грань ±7,9) стоят на канале коробки r 9,35.
CLIP_HALF, CLIP_OUT_Y, RCV_R_IN = 35.0, 7.9, 9.35
SEAT_RIFLE_MM = Vector((R.CLIP_SPINE_X + 0.5, 0.0, (RCV_R_IN ** 2 - CLIP_OUT_Y ** 2) ** 0.5 + CLIP_HALF + 0.05))
# донца патронов в обойме (оси обоймы, мм; Mosin_Clip_loaded_check_v01): снизу вверх, через один на 1,65 вперёд
ROUNDS_MM = [(0.0, 0.0, -26.9), (1.65, 0.0, -13.45), (0.0, 0.0, 0.0), (1.65, 0.0, 13.45), (0.0, 0.0, 26.9)]
META = json.loads((OUT / 'mosin_pu.json').read_text(encoding='utf-8'))
GRIP = Vector(META['grip_origin_rifle_mm']) * 0.001          # начало игры в осях винтовки
TO_EXPORT = Matrix.Rotation(math.radians(-90.0), 4, 'Z')     # оси винтовки (дуло +X) → оси экспорта (дуло −Y)
log = lambda *a: print('MOSIN_CLIP', *a, flush=True)


def tris(me) -> int:
    me.calc_loop_triangles()
    return len(me.loop_triangles)


# ---------------------------------------------------------------- сетка
bpy.context.preferences.use_preferences_save = False
bpy.ops.wm.open_mainfile(filepath=str(SRC))
S = bpy.context.scene
for o in list(bpy.data.objects):
    if o.type in ('LIGHT', 'CAMERA'):
        bpy.data.objects.remove(o, do_unlink=True)
hp = bpy.data.objects['Clip_Body']
assert hp.matrix_world == Matrix.Identity(4), 'обойма исходника не в начале координат'
dg = bpy.context.evaluated_depsgraph_get()
src_me = hp.evaluated_get(dg).to_mesh()
hp_tris = tris(src_me)
hp_bvh = BVHTree.FromPolygons([v.co.copy() for v in src_me.vertices], [p.vertices[:] for p in src_me.polygons])
bm = bmesh.new()
bm.from_mesh(src_me)
hp_verts = [v.co.copy() for v in src_me.vertices]
hp.evaluated_get(dg).to_mesh_clear()
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(ANGLE), use_dissolve_boundaries=False, verts=bm.verts, edges=bm.edges)
bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='BEAUTY', ngon_method='BEAUTY')
non_manifold = sum(1 for e in bm.edges if not e.is_manifold)


def width(f) -> float:
    """Ширина треугольника поперёк длинной стороны: у торца листа — его толщина (0,5 мм)."""
    return 2.0 * f.calc_area() / max(e.calc_length() for e in f.edges)


def outer(f) -> bool:
    """Наружная сторона листа: нормаль от середины жёлоба обоймы (x 7,5 мм, y 0 — между спинкой и кромками стенок)."""
    c = f.calc_center_median()
    return f.normal.x * (c.x - 0.0075) + f.normal.y * c.y > 0.0


# Шов — по жёсткому ребру, кроме рёбер между торцом листа и его наружной стороной: торцы разворачиваются вместе с
# наружной стороной, а не россыпью островков в 0,5 мм (с полями атласа они съедали почти всю площадь).
strip = {f.index for f in bm.faces if width(f) < 0.0008}
bm.faces.ensure_lookup_table()
for e in bm.edges:
    sharp = (not e.is_manifold) or (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(SHARP))
    e.smooth = not sharp
    seam = sharp
    if sharp and len(e.link_faces) == 2:
        a, b = e.link_faces
        if (a.index in strip) != (b.index in strip):
            main = b if a.index in strip else a
            seam = not outer(main)
    e.seam = seam
for f in bm.faces:
    f.smooth = True
me = bpy.data.meshes.new('Clip_Mesh')
bm.to_mesh(me)
bm.free()
for a in ('Wear_Contact', 'Wear_Rest', 'Wood_Wear'):        # атрибуты износа исходника — игре не нужны
    if a in me.attributes:
        me.attributes.remove(me.attributes[a])
while me.uv_layers:
    me.uv_layers.remove(me.uv_layers[0])
me.uv_layers.new(name='GameUV')
lp = bpy.data.objects.new('Clip_Mesh', me)
S.collection.objects.link(lp)
lp_bvh = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [p.vertices[:] for p in me.polygons])
dev_out = max(lp_bvh.find_nearest(v)[3] for v in hp_verts)
dev_in = max(hp_bvh.find_nearest(v.co)[3] for v in me.vertices)
lp_tris = tris(me)
log('tris', hp_tris, '→', lp_tris, 'deviation mm', round(dev_out * 1000, 3), round(dev_in * 1000, 3),
    'non-manifold edges', non_manifold)

# ---------------------------------------------------------------- развёртка: острова по жёстким рёбрам, ровно по осям
bpy.ops.object.select_all(action='DESELECT')
lp.select_set(True)
bpy.context.view_layer.objects.active = lp
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.0)
bpy.ops.uv.select_all(action='SELECT')
bpy.ops.uv.pack_islands(rotate=True, rotate_method='AXIS_ALIGNED', scale=True, margin_method='FRACTION',
                        margin=MARGIN_PX / SIZE, shape_method='CONCAVE')
bpy.ops.object.mode_set(mode='OBJECT')
uv_area = 0.0
for p in me.polygons:
    uvs = [me.uv_layers['GameUV'].data[li].uv for li in p.loop_indices]
    for i in range(1, len(uvs) - 1):
        uv_area += abs((uvs[i] - uvs[0]).cross(uvs[i + 1] - uvs[0])) * 0.5
surf = sum(p.area for p in me.polygons)
texel = math.sqrt(uv_area * SIZE * SIZE / (surf * 1e6))
from bpy_extras.mesh_utils import mesh_linked_uv_islands  # noqa: E402
islands = len(mesh_linked_uv_islands(me))
log('uv area', round(uv_area, 3), 'px/mm', round(texel, 2), 'islands', islands)

# ---------------------------------------------------------------- запекание с high-poly (UCUPaint → Emission)
mat = bpy.data.materials.new('GAME • Clip')
mat.use_nodes = True
me.materials.append(mat)
lp.hide_render = False
lp.visible_camera = lp.visible_diffuse = lp.visible_glossy = lp.visible_transmission = False
lp.visible_volume_scatter = lp.visible_shadow = False
S.render.engine = 'CYCLES'
prefs = bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type != 'CPU'
    S.cycles.device = 'GPU'
except TypeError:
    S.cycles.device = 'CPU'
S.cycles.use_denoising = False
bk = S.render.bake
bk.margin = MARGIN_PX // 2 - 1
bk.margin_type = 'EXTEND'
bk.normal_space = 'TANGENT'
ext = min(4.0, max(0.4, dev_out * 1000 * 1.5 + 0.3))          # как game_lp.py: запас лучей от отклонения
max_ray = ext + dev_in * 1000 * 1.5 + 0.5
RAW.mkdir(parents=True, exist_ok=True)
GAME.mkdir(parents=True, exist_ok=True)
hp_mat = hp.active_material
hnt = hp_mat.node_tree
h_out = next(n for n in hnt.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
h_surface = h_out.inputs['Surface'].links[0].from_socket
h_bsdf = next(n for n in hnt.nodes if n.type == 'BSDF_PRINCIPLED')


def source(name: str):
    inp = h_bsdf.inputs[name]
    return (inp.links[0].from_socket, None) if inp.links else (None, inp.default_value)


def feed(sock_in, src) -> None:
    sock, value = src
    if sock is not None:
        hnt.links.new(sock, sock_in)
    elif hasattr(value, '__len__'):
        sock_in.default_value = value
    else:
        sock_in.default_value = (value, value, value, 1) if sock_in.type == 'RGBA' else value


def route(channel: str) -> None:
    """Канал high-poly → Emission (color — цвет; mrh — R металл, G шероховатость; cov — покрытие = 1)."""
    if channel == 'normal':
        hnt.links.new(h_surface, h_out.inputs['Surface'])
        return
    emit = hnt.nodes.get('BAKE_EMIT') or hnt.nodes.new('ShaderNodeEmission')
    emit.name = 'BAKE_EMIT'
    for l in list(emit.inputs['Color'].links):
        hnt.links.remove(l)
    if channel == 'color':
        feed(emit.inputs['Color'], source('Base Color'))
    else:
        comb = hnt.nodes.get('BAKE_COMB') or hnt.nodes.new('ShaderNodeCombineColor')
        comb.name = 'BAKE_COMB'
        for k in ('Red', 'Green', 'Blue'):
            for l in list(comb.inputs[k].links):
                hnt.links.remove(l)
            comb.inputs[k].default_value = 1.0 if channel == 'cov' else 0.0
        if channel == 'mrh':
            feed(comb.inputs['Red'], source('Metallic'))
            feed(comb.inputs['Green'], source('Roughness'))
        hnt.links.new(comb.outputs['Color'], emit.inputs['Color'])
    hnt.links.new(emit.outputs[0], h_out.inputs['Surface'])


def bake(channel: str) -> Path:
    im = bpy.data.images.new(f'Clip_{channel}', SIZE, SIZE, alpha=True, float_buffer=(channel == 'normal'))
    im.colorspace_settings.name = 'sRGB' if channel == 'color' else 'Non-Color'
    im.generated_color = (0.5, 0.5, 1.0, 0.0) if channel == 'normal' else (0, 0, 0, 0)
    nt = mat.node_tree
    node = nt.nodes.get('BAKE_TARGET') or nt.nodes.new('ShaderNodeTexImage')
    node.name = 'BAKE_TARGET'
    node.image = im
    nt.nodes.active = node
    S.cycles.samples = SAMPLES[channel]
    bpy.ops.object.select_all(action='DESELECT')
    if channel == 'ao':
        # AO самой игровой сетки: только она видна лучам (щели у спинки и под язычками)
        hp.hide_render = True
        lp.visible_camera = lp.visible_diffuse = lp.visible_glossy = lp.visible_shadow = True
        S.world = S.world or bpy.data.worlds.new('AO')
        S.world.light_settings.distance = 0.004
        lp.select_set(True)
        bpy.context.view_layer.objects.active = lp
        bpy.ops.object.bake(type='AO', use_clear=True, use_selected_to_active=False, margin=bk.margin)
    else:
        route(channel)
        hp.hide_render = False
        hp.select_set(True)
        lp.select_set(True)
        bpy.context.view_layer.objects.active = lp
        bpy.ops.object.bake(type='NORMAL' if channel == 'normal' else 'EMIT', use_clear=True, use_selected_to_active=True,
                            cage_extrusion=ext / 1000, max_ray_distance=max_ray / 1000, margin=bk.margin)
    path = RAW / f'Clip_{channel}.png'
    im.filepath_raw = str(path)
    im.file_format = 'PNG'
    im.save()
    log('baked', path.name)
    return path


for ch in ('cov', 'color', 'mrh', 'normal', 'ao'):
    bake(ch)
hnt.links.new(h_surface, h_out.inputs['Surface'])


# ---------------------------------------------------------------- упаковка (как game_pack.py)
def load(name: str) -> np.ndarray:
    im = bpy.data.images.load(str(RAW / f'Clip_{name}.png'))
    im.colorspace_settings.name = 'Non-Color'
    a = np.empty(SIZE * SIZE * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(SIZE, SIZE, 4)


def save(arr: np.ndarray, path: Path, srgb: bool) -> None:
    rgba = np.ones((SIZE, SIZE, 4), np.float32)
    rgba[..., :3] = arr[..., :3]
    im = bpy.data.images.new(path.stem, SIZE, SIZE, alpha=False, float_buffer=False)
    im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    im.pixels.foreach_set(np.clip(rgba, 0, 1).ravel())
    im.filepath_raw = str(path)
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)


def pushpull(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Пустые пиксели — из пирамиды средних по запечённому (дальние mip не тянут чёрный фон в швы)."""
    c = img * mask[..., None]
    wgt = mask.astype(np.float32)
    levels = []
    while c.shape[0] > 1:
        levels.append((c, wgt))
        h, w = c.shape[0] // 2, c.shape[1] // 2
        c = c[:h * 2, :w * 2].reshape(h, 2, w, 2, -1).sum(axis=(1, 3))
        wgt = wgt[:h * 2, :w * 2].reshape(h, 2, w, 2).sum(axis=(1, 3))
    fill = c / np.maximum(wgt, 1e-6)[..., None]
    for c_l, w_l in reversed(levels):
        up = np.repeat(np.repeat(fill, 2, axis=0), 2, axis=1)[:c_l.shape[0], :c_l.shape[1]]
        have = w_l > 1e-6
        fill = np.where(have[..., None], c_l / np.maximum(w_l, 1e-6)[..., None], up)
    return np.where(mask[..., None], img, fill)


cov = load('cov')
mask = cov[..., 2] > 0.5
color = pushpull(load('color')[..., :3], mask)
save(color, GAME / 'Clip_albedo.png', True)
nrm = pushpull(load('normal')[..., :3], mask)
v = nrm * 2 - 1
v /= np.maximum(np.linalg.norm(v, axis=2, keepdims=True), 1e-6)
save(v * 0.5 + 0.5, GAME / 'Clip_normal.png', False)
mrh = pushpull(load('mrh')[..., :3], mask)
ao = pushpull(load('ao')[..., :1], mask)[..., 0]
save(np.dstack([ao, mrh[..., 1], mrh[..., 0]]), GAME / 'Clip_orm.png', False)
stats = {'coverage': round(float(mask.mean()), 3), 'rough': round(float(mrh[..., 1][mask].mean()), 3),
         'metal': round(float(mrh[..., 0][mask].mean()), 3), 'ao': round(float(ao[mask].mean()), 3),
         'albedo_srgb': [round(float(x), 3) for x in color[mask].mean(axis=0)]}
log('pack', stats)

# ---------------------------------------------------------------- игровой материал, оси экспорта, GLB
nt = mat.node_tree
nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputMaterial')
p = nt.nodes.new('ShaderNodeBsdfPrincipled')
nt.links.new(p.outputs['BSDF'], out.inputs['Surface'])
uvn = nt.nodes.new('ShaderNodeUVMap')
uvn.uv_map = 'GameUV'


def tex(kind: str, cs: str):
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = bpy.data.images.load(str(GAME / f'Clip_{kind}.png'), check_existing=True)
    t.image.colorspace_settings.name = cs
    nt.links.new(uvn.outputs['UV'], t.inputs['Vector'])
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

# исходник и его материалы — прочь; сетка — в оси экспорта винтовки (поворот, начало — то же)
for o in list(bpy.data.objects):
    if o != lp:
        bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.materials):
    if m != mat:
        bpy.data.materials.remove(m)
me.transform(TO_EXPORT)
lp.visible_camera = lp.visible_diffuse = lp.visible_glossy = lp.visible_transmission = True
lp.visible_volume_scatter = lp.visible_shadow = True
root = bpy.data.objects.new('Clip', None)
root.empty_display_size = 0.02
S.collection.objects.link(root)
root['asset'] = 'Обойма Мосина на 5 патронов 7,62×54R (заряжание без прицела ПУ)'
root['source'] = str(SRC)
lp.parent = root
for im in list(bpy.data.images):
    if im.users == 0:
        bpy.data.images.remove(im)
bpy.ops.object.select_all(action='DESELECT')
root.select_set(True)
lp.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT / 'mosin_pu_clip.glb'), export_format='GLB', use_selection=True, export_yup=True,
                          export_apply=True, export_extras=True, export_animations=False, export_cameras=False,
                          export_lights=False, export_image_format='AUTO')
log('exported', 'mosin_pu_clip.glb')
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=str(WORK / 'lp/Mosin_Clip_export.blend'))

gl = lambda v: [round(v[0], 5), round(v[2], 5), round(-v[1], 5)]          # Blender (Z-up) → glTF (Y-up)
seat = TO_EXPORT @ (SEAT_RIFLE_MM * 0.001 - GRIP)
rounds = [TO_EXPORT @ (Vector(r) * 0.001) for r in ROUNDS_MM]
record = dict(
    schema='ring.weapon_part.v1', part='mosin_pu_clip', source=str(SRC),
    axes='как у mosin_pu.glb: +Z дуло (патроны в обойме пулями туда), +Y вверх вдоль обоймы, −X правая сторона стрелка; '
         'начало — середина спинки изнутри; метры',
    triangles=lp_tris, source_triangles=hp_tris, deviation_mm=[round(dev_out * 1000, 3), round(dev_in * 1000, 3)],
    seat_game_m=gl(seat), seat_rifle_mm=[round(c, 2) for c in SEAT_RIFLE_MM],
    seat_note='начало обоймы в направляющих коробки (затвор отведён на 110 мм), в осях mosin_pu.glb от середины шейки',
    rounds_base_game_m=[gl(r) for r in rounds],
    rounds_note='донца пяти патронов в обойме снизу вверх (оси обоймы); через один на 1,65 мм вперёд — закраины не цепляются',
    atlas_px=SIZE, texel_px_mm=round(texel, 2), uv_margin_px=MARGIN_PX, maps=stats,
    material={'GAME • Clip': 'mosin_pu_clip_Clip_{albedo,normal,orm}.png (Godot извлекает из GLB); ORM — R AO, G шероховатость, B металл'},
)
(OUT / 'mosin_pu_clip.json').write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
log('SAVED tris', lp_tris, 'seat game m', gl(seat))
