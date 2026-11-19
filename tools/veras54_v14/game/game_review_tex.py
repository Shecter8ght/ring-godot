"""ВЕРАС-54 v14, игровая версия с перенесёнными картами: файл просмотра владельцу (студия в файле) и кадры сверки
«подробная | игровая» теми же камерами. Образец — «Частокол» (tools/pkp/game_review.py).

Файл просмотра:
"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/veras54_v14/game/game_review_tex.py -- build [<папка карт>] [<out.blend>]
→ «Игровая версия/Геометрия v14/ВЕРАС-54_игровая_v14_02.blend» (v14_01 — кандидат сетки без текстур — не трогается).
Игровая сетка — из _asset_src/veras54_v14/game/lp/VERAS54_Game_LP.blend, материал на атлас, карты — PNG переноса
(game_transfer.py, «Игровая версия/Карты v14») по относительным путям: перенёс заново — файл подхватит новые карты.
Коллекции: «GAME» — LOD0 на месте, «LOD1 (ниже)» — на 0,32 м ниже, «Сверка — подробная с износом v03 (выше)» — файл
просмотра износа `Карты v14/ВЕРАС-54_износ_v14_03.blend` ссылкой на 0,32 м выше. Ползунки — VERAS54_Controls.

Кадры:
"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/veras54_v14/game/game_review_tex.py -- shots [вид,…] [--samples N]
→ _asset_src/veras54_v14/game/shots_tex/raw/<вид>__{hp,lp,lod1,nrm}.png — файл просмотра износа (его студия и свет),
поверх — игровая сетка на том же месте; в каждом виде по очереди подробная и игровая (nrm — игровая с одной картой
нормалей на сером: швы). Листы и кропы 1:1 — game_review_sheets.py (системный Python, PIL).
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'tools/veras54_v14/geo'))
sys.path.insert(0, str(ROOT / 'tools/veras54_v14/tex'))
import game_lp as G  # noqa: E402
import game_review as GR  # noqa: E402
import tex_sets as T  # noqa: E402

LP_FILE = G.OUT / 'VERAS54_Game_LP.blend'
GAME_DIR = Path(T.MODEL_DIR) / 'Игровая версия'
MAPS = GAME_DIR / 'Карты v14'
OUT_BLEND = GAME_DIR / 'Геометрия v14' / 'ВЕРАС-54_игровая_v14_02.blend'
REF = Path(T.MODEL_DIR) / 'Карты v14' / 'ВЕРАС-54_износ_v14_03.blend'
SHOTS = G.WORK / 'shots_tex'
OFFSET_Z = 0.32
log = lambda *a: print('VERAS14_REVTEX', *a, flush=True)  # noqa: E731

# вид: (направление от точки к камере, расстояние, фокусное, точка | имя детали | None, разрешение) — как tex_review.py;
# 'hip' / 'ads' — камеры game_review.VIEWS (от бедра и в прицел)
VIEWS = {
    '01_справа': ((0.0, -1.0, 0.08), 1.55, 50, None, (1920, 1080)),
    '02_слева': ((0.0, 1.0, 0.08), 1.55, 50, None, (1920, 1080)),
    '03_от_бедра': 'hip',
    '04_в_прицел': 'ads',
    '05_клейма_слева': ((0.0, 1.0, 0.05), 0.16, 50, (0.195, 0.0, -0.006), (1920, 1080)),
    '06_переводчик_АВ_2_ОД': ((0.0, -1.0, 0.05), 0.16, 50, (0.160, 0.0, -0.012), (1920, 1080)),
    '07_коробка_справа': ((0.0, -1.0, 0.10), 0.30, 50, (0.150, 0.0, 0.0), (1920, 1080)),
    '08_затылок_сзади_слева_сверху': ((-0.75, 0.45, 0.65), 0.15, 50, (0.016, 0.0, 0.020), (1920, 1080)),
    '09_затылок_правый_угол': ((-0.55, -0.6, 0.6), 0.10, 50, (0.015, -0.013, 0.021), (1920, 1080)),
    '10_планка_сверху': ((0.0, -0.18, 1.0), 0.20, 50, (0.177, 0.0, 0.043), (1920, 1080)),
    '11_магазин': ((0.1, -1.0, 0.0), 0.30, 50, 'Magazine_Body', (1920, 1080)),
    '12_магазин_слева': ((0.1, 1.0, 0.0), 0.30, 50, 'Magazine_Body', (1920, 1080)),
    '13_приклад': ((0.05, -1.0, 0.15), 0.42, 50, 'Stock_Body', (1920, 1080)),
    '14_крышка_сверху': ((0.05, -0.12, 1.0), 0.46, 50, 'Dust_Cover', (1920, 1080)),
    '15_цевьё_и_газовый': ((0.2, -1.0, 0.3), 0.40, 50, (0.45, 0.0, 0.0), (1920, 1080)),
    '16_целик': ((-0.7, -0.45, 0.55), 0.20, 50, 'Rear_Sight_Leaf', (1920, 1080)),
}
LOD1_VIEWS = {'01_справа', '02_слева'}
NRM_VIEWS = {'01_справа', '02_слева', '07_коробка_справа', '14_крышка_сверху', '11_магазин'}


def material(name, atlas, maps, nrm_only=False):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs[0])
    out.location, b.location = (600, 0), (300, 0)
    tag = f'veras54_{atlas}_100'

    def img(suffix, noncolor, y):
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(str(maps / f'{tag}_{suffix}.png'), check_existing=True)
        t.image.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
        t.interpolation = 'Linear'
        t.location = (-500, y)
        return t
    if not (maps / f'{tag}_albedo.png').exists():
        b.inputs['Base Color'].default_value = (0.3, 0.3, 0.3, 1)
        log('нет карт атласа', atlas, '— серая глина')
        return m
    if nrm_only:
        b.inputs['Base Color'].default_value = (0.06, 0.06, 0.065, 1)
        b.inputs['Roughness'].default_value = 0.28
        b.inputs['Metallic'].default_value = 0.0
    else:
        bc = img('albedo', False, 300)
        orm = img('orm', True, 0)
        nt.links.new(bc.outputs[0], b.inputs['Base Color'])
        sp = nt.nodes.new('ShaderNodeSeparateColor')
        sp.location = (-150, 0)
        nt.links.new(orm.outputs[0], sp.inputs[0])
        nt.links.new(sp.outputs['Green'], b.inputs['Roughness'])
        nt.links.new(sp.outputs['Blue'], b.inputs['Metallic'])
    nm = img('normal', True, -300)
    nmap = nt.nodes.new('ShaderNodeNormalMap')
    nmap.uv_map = 'GameUV'
    nmap.location = (-150, -300)
    nt.links.new(nm.outputs[0], nmap.inputs['Color'])
    nt.links.new(nmap.outputs[0], b.inputs['Normal'])
    return m


def cycles(samples, gpu=True):
    S = bpy.context.scene
    S.render.engine = 'CYCLES'
    S.cycles.samples = samples
    S.cycles.preview_samples = 64
    S.cycles.use_denoising = True
    S.cycles.use_preview_denoising = True
    S.cycles.denoising_use_gpu = False
    if gpu:
        import addon_utils
        addon_utils.enable('cycles')
        cp = bpy.context.preferences.addons['cycles'].preferences
        for kind in ('OPTIX', 'CUDA'):
            try:
                cp.compute_device_type = kind
                cp.get_devices()
                for dv in cp.devices:
                    dv.use = dv.type != 'CPU'
                break
            except Exception:      # noqa: BLE001
                continue
        S.cycles.device = 'GPU'
    S.view_settings.view_transform = 'AgX'


README = """ВЕРАС-54 v14 — игровая версия с перенесёнными картами «Износ v03» (LOD0 36,3 тыс. треугольников без магазина)

Коллекции (галочка в Outliner):
  «GAME» — LOD0 (в руках): узлы игры — пустышки в осях подвижных деталей, сетки «<Узел>__<Атлас>» — их дочерние;
    патроны магазина — Round_01…30 (одна сетка), патрон в патроннике — Chamber_Round / Chamber_Bullet.
  «LOD1 (ниже)» — то же, упрощённое до ¼, на 0,32 м ниже (развёртка та же, карты те же).
  «Сверка — подробная с износом v03 (выше)» — файл просмотра износа ссылкой на 0,32 м выше (тяжёлый, 9 млн
    треугольников — выключить галочкой, если вьюпорт тормозит).
Ползунки — пустышка VERAS54_Controls (Object → Custom Properties): двигают узлы игровой сетки.
Карты — папка «Игровая версия/Карты v14» (атласы Body, Front 4096, Mag 2048): перенос с подробной модели командой
  python -X utf8 tools/veras54_v14/game/game_transfer.py [<папка карт Painter>]
— файл просмотра подхватит новые карты при открытии. Числа — retopo-report.json рядом (раздел atlases, transfer).
"""


def build(maps, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(LP_FILE))
    rec = json.loads((LP_FILE.parent / 'parts.json').read_text(encoding='utf-8'))
    mats = {a: material(f'ВЕРАС-54 v14 • игра • {a}', a, maps) for a in rec['atlases']}
    nodes = {}
    for o in bpy.data.objects:
        if o.type == 'EMPTY' and o.name in rec['nodes']:
            nodes[o.name] = o
        if o.type == 'MESH' and 'atlas' in o:
            o.data.materials.clear()
            o.data.materials.append(mats[o['atlas']])
    for m in list(bpy.data.materials):
        if m.users == 0:
            bpy.data.materials.remove(m)
    GR.rig(nodes)
    lod = bpy.data.collections.get('GAME_LOD1')
    lod.hide_render = False
    lc = bpy.data.collections.new('LOD1 (ниже)')
    bpy.context.scene.collection.children.link(lc)
    e = bpy.data.objects.new('LOD1 • экземпляр', None)
    e.instance_type = 'COLLECTION'
    e.instance_collection = lod
    e.location = (0, 0, -OFFSET_Z)
    lc.objects.link(e)
    bpy.context.view_layer.layer_collection.children['GAME_LOD1'].exclude = True
    with bpy.data.libraries.load(str(REF), link=True, relative=True) as (src, dst):
        dst.collections = ['ВЕРАС-54']
    hc = bpy.data.collections.new('Сверка — подробная с износом v03 (выше)')
    bpy.context.scene.collection.children.link(hc)
    h = bpy.data.objects.new('Подробная v14 • износ v03 • экземпляр', None)
    h.instance_type = 'COLLECTION'
    h.instance_collection = dst.collections[0]
    h.location = (0, 0, OFFSET_Z)
    hc.objects.link(h)
    GR.studio(Vector((0.234, 0.0, -0.075)))
    cycles(128)
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == 'VIEW_3D':
                for sp in area.spaces:
                    if sp.type == 'VIEW_3D':
                        sp.shading.type = 'MATERIAL'
                        sp.clip_start = 0.005
    txt = bpy.data.texts.get('Как смотреть') or bpy.data.texts.new('Как смотреть')
    txt.clear()
    txt.write(README)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True, relative_remap=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile(compress=True)
    log('файл просмотра →', out)


def shots(only, samples):
    raw = SHOTS / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(REF))
    rec = json.loads((LP_FILE.parent / 'parts.json').read_text(encoding='utf-8'))
    ctl = bpy.data.objects[T.CONTROLS]
    for k, v in rec['base_props'].items():
        if k in ctl:
            ctl[k] = float(v)
    ctl.update_tag()
    S = bpy.context.scene
    S.frame_set(S.frame_current)
    hp_objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.name in bpy.data.collections['ВЕРАС-54'].all_objects]
    with bpy.data.libraries.load(str(LP_FILE), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c in ('GAME', 'GAME_LOD1')]
    cols = {c.name: c for c in dst.collections}
    for c in cols.values():
        S.collection.children.link(c)
        c.hide_render = False
    lp0 = [o for o in cols['GAME'].all_objects if o.type == 'MESH']
    lp1 = [o for o in cols['GAME_LOD1'].all_objects if o.type == 'MESH']
    maps = MAPS
    mats = {a: material(f'игра • {a}', a, maps) for a in rec['atlases']}
    nmats = {a: material(f'игра • нормаль • {a}', a, maps, nrm_only=True) for a in rec['atlases']}
    for o in lp0 + lp1:
        o.data.materials.clear()
        o.data.materials.append(mats[o['atlas']])
    bpy.context.view_layer.update()
    cycles(samples)
    cam = S.camera
    cam.data.clip_start = 0.004
    C = Vector((0.234, 0.0, -0.075))

    def show(objs):
        on = {o.name for o in objs}
        for o in hp_objs + lp0 + lp1:
            o.hide_render = o.name not in on

    for name, v in VIEWS.items():
        if only and name not in only:
            continue
        if isinstance(v, str):
            _pose, kind, pos, tgt, up, ang, res = GR.VIEWS[v]
            cam.data.type = 'PERSP'
            cam.data.sensor_fit = 'VERTICAL'
            cam.data.angle_y = math.radians(ang)
            GR.look(cam, pos, tgt, up)
        else:
            d, dist, lens, at, res = v
            if at is None:
                at = C
            elif isinstance(at, str):
                o = bpy.data.objects[at]
                bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
                at = sum(bb, Vector()) / 8.0
            else:
                at = Vector(at)
            cam.data.type = 'PERSP'
            cam.data.sensor_fit = 'AUTO'
            cam.data.lens = lens
            cam.location = at + Vector(d).normalized() * dist
            cam.rotation_euler = (at - cam.location).to_track_quat('-Z', 'Y').to_euler()
        S.render.resolution_x, S.render.resolution_y = res
        S.render.resolution_percentage = 100
        runs = [('hp', hp_objs), ('lp', lp0)]
        if name in LOD1_VIEWS:
            runs.append(('lod1', lp1))
        if name in NRM_VIEWS:
            runs.append(('nrm', lp0))
        for tag, objs in runs:
            for o in lp0:
                o.data.materials[0] = (nmats if tag == 'nrm' else mats)[o['atlas']]
            show(objs)
            S.render.filepath = str(raw / f'{name}__{tag}.png')
            bpy.ops.render.render(write_still=True)
            log('кадр', name, tag)
    for o in lp0:
        o.data.materials[0] = mats[o['atlas']]


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    mode = a[0] if a else 'build'
    if mode == 'build':
        build(Path(a[1]) if len(a) > 1 else MAPS, Path(a[2]) if len(a) > 2 else OUT_BLEND)
    else:
        smp = 48
        if '--samples' in a:
            smp = int(a[a.index('--samples') + 1])
            del a[a.index('--samples'):a.index('--samples') + 2]
        shots(set(a[1].split(',')) if len(a) > 1 else set(), smp)
