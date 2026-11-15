"""«Частокол», игровая версия: файл просмотра владельцу со студией прямо в файле (как tools/pkp/tex_review.py) и сверка
с подробной моделью в той же студии.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/pkp/game_review.py -- [<папка игровых карт>] [<out.blend>] [--ref <файл подробной модели>]

Игровая сетка — из _asset_src/pkp/game/lp/PKP_Game_LP.blend (game_lp.py): узлы, LOD1, развёртка GameUV. Материал на
атлас, карты — PNG переноса (game_transfer.py) по относительным путям: перенёс заново — файл просмотра показывает новое
без пересборки. Риг: пустышка PKP_Controls с теми же ползунками, что у подробной модели (part_rig.SLIDERS), приводы —
на узлах игры (те же выражения: начала узлов стоят в осях моверов исходника).
Сверка: подробная модель с картами износа подключена ссылкой (не копией — файл остаётся лёгким) из файла просмотра
износа и стоит рядом, слева от игровой (+Y). Коллекции: «Игровая — LOD0», «Игровая — LOD1» (выключена),
«Сверка — подробная»; переключаются галочкой в Outliner.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import part_rig as R  # noqa: E402
import tex_sets as T  # noqa: E402
import tex_review as TR  # noqa: E402

LP_FILE = Path(os.environ.get('PKP_GAME_WORK') or ROOT / '_asset_src/pkp/game') / 'lp/PKP_Game_LP.blend'
GAME_DIR = Path(T.MODEL_DIR) / 'игровая_версия'
MAPS = GAME_DIR / 'карты'
OUT = GAME_DIR / 'Частокол_игровая_v01.blend'
REF = Path(T.MODEL_DIR) / 'Частокол_износ_этап2_v04.blend'
REF_SKIP = {'Коробка 200', 'Патроны', 'Лента — отрезок', 'Кронштейн — планка на крышку', 'Кронштейн — цевьё'}
REF_OFFSET = Vector((0.0, 0.50, 0.0))
log = lambda *a: print('PKP_REVIEW', *a, flush=True)  # noqa: E731


def material(name, atlas, maps):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs[0])
    out.location, b.location = (600, 0), (300, 0)
    tag = f'pkp_{atlas}_100'

    def img(suffix, noncolor, y):
        p = maps / f'{tag}_{suffix}.png'
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = bpy.data.images.load(str(p), check_existing=True)
        t.image.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
        t.interpolation = 'Linear'
        t.location = (-500, y)
        return t
    if not (maps / f'{tag}_albedo.png').exists():
        b.inputs['Base Color'].default_value = (0.3, 0.3, 0.3, 1)
        log('нет карт атласа', atlas, '— серая глина')
        return m
    bc = img('albedo', False, 300)
    orm = img('orm', True, 0)
    nm = img('normal', True, -300)
    nt.links.new(bc.outputs[0], b.inputs['Base Color'])
    sp = nt.nodes.new('ShaderNodeSeparateColor')
    sp.location = (-150, 0)
    nt.links.new(orm.outputs[0], sp.inputs[0])
    nt.links.new(sp.outputs['Green'], b.inputs['Roughness'])
    nt.links.new(sp.outputs['Blue'], b.inputs['Metallic'])
    nmap = nt.nodes.new('ShaderNodeNormalMap')
    nmap.uv_map = 'GameUV'
    nmap.location = (-150, -300)
    nt.links.new(nm.outputs[0], nmap.inputs['Color'])
    nt.links.new(nmap.outputs[0], b.inputs['Normal'])
    return m


def rig(nodes):
    """Пустышка PKP_Controls и приводы на узлах игры (выражения part_rig, ползунки part_rig.SLIDERS)."""
    import game_lp as G
    c = bpy.data.objects.new('PKP_Controls', None)
    c.empty_display_type = 'PLAIN_AXES'
    c.empty_display_size = 0.03
    bpy.context.scene.collection.objects.link(c)
    for k, tip, default in R.SLIDERS:
        c[k] = float(default)
        ui = c.id_properties_ui(k)
        ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description=tip)
    n = 0
    rest = {k: float(v) for k, _t, v in R.SLIDERS}
    for name, path, index, expr, props in R.drivers():
        node = G.MOVERS.get(name)
        o = nodes.get(node)
        if o is None:
            continue
        # игровые сетки сняты в позе умолчаний рига (заслонка коробки откинута на 0,7): узел в этой позе — ноль
        v0 = eval(expr, {'max': max, 'min': min}, dict(rest))
        if path == 'delta_scale' and abs(v0 - 1.0) > 1e-9:
            expr = f'({expr})/{v0:.6f}'
        elif path != 'delta_scale' and abs(v0) > 1e-9:
            expr = f'({expr})-({v0:.6f})'
        fc = o.driver_add(path, index)
        dr = fc.driver
        dr.type = 'SCRIPTED'
        for p in props:
            v = dr.variables.new()
            v.name = p
            v.type = 'SINGLE_PROP'
            v.targets[0].id = c
            v.targets[0].data_path = f'["{p}"]'
        dr.expression = expr
        n += 1
    log('приводов', n)
    return c


def link_reference(ref: Path):
    """Подробная модель ссылкой: дочерние коллекции «ПКП» файла износа (кроме выключенных там) — экземплярами под
    пустышкой «Сверка — подробная» со сдвигом."""
    with bpy.data.libraries.load(str(ref), link=True, relative=True) as (src, dst):
        dst.collections = [c for c in src.collections if c not in REF_SKIP and c not in ('ПКП', 'Студия просмотра')]
    coll = bpy.data.collections.new('Сверка — подробная')
    bpy.context.scene.collection.children.link(coll)
    root = bpy.data.objects.new('Сверка — подробная (сдвиг)', None)
    root.empty_display_size = 0.05
    coll.objects.link(root)
    root.location = REF_OFFSET
    for c in dst.collections:
        if c is None:
            continue
        e = bpy.data.objects.new(f'Сверка • {c.name}', None)
        e.instance_type = 'COLLECTION'
        e.instance_collection = c
        e.empty_display_size = 0.01
        coll.objects.link(e)
        e.parent = root
    return coll


README = """«Частокол» — игровая версия (LOD0 до ~40 тыс. треугольников в руках, LOD1 ≈ ¼)

Коллекции (галочка в Outliner):
  «GAME» — игровая сетка LOD0: узлы игры — пустышки в осях подвижных деталей, сетки «<Узел>__<Атлас>» — их дочерние;
  «GAME_LOD1» — то же, упрощённое до ¼ (выключено; включить и выключить GAME — сравнить);
  «Сверка — подробная» — подробная модель с картами износа рядом, слева (+Y 0,5 м), та же студия.
Подвижные детали — ползунки пустышки PKP_Controls (вкладка Object → Custom Properties), как у подробной модели.
Карты — папка «карты» рядом (атласы Body, Front, Box по 4096): перенос с подробной модели командой
  python -X utf8 tools/pkp/game_transfer.py <папка карт Painter>
— файл просмотра подхватит новые карты при открытии.
"""


def main():
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ref = REF
    if '--ref' in a:
        i = a.index('--ref')
        ref = Path(a[i + 1])
        del a[i:i + 2]
    maps = Path(a[0]) if a else MAPS
    out = Path(a[1]) if len(a) > 1 else OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(LP_FILE))
    rec = json.loads((LP_FILE.parent / 'parts.json').read_text(encoding='utf-8'))
    mats = {}
    for atlas in rec['atlases']:
        mats[atlas] = material(f'Частокол • игра • {atlas}', atlas, maps)
    nodes = {}
    for o in bpy.data.objects:
        if o.type == 'EMPTY' and o.name in rec['nodes']:
            nodes[o.name] = o
        if o.type == 'MESH' and 'atlas' in o:
            o.data.materials.clear()
            o.data.materials.append(mats[o['atlas']])
    rig(nodes)
    if ref.exists():
        link_reference(ref)
    else:
        log('нет файла сверки', ref)
    TR.studio()
    txt = bpy.data.texts.get('Как смотреть') or bpy.data.texts.new('Как смотреть')
    txt.clear()
    txt.write(README)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True, relative_remap=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile(compress=True)
    log('файл просмотра →', out)


if __name__ == '__main__':
    main()
