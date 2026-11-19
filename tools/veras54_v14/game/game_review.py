"""ВЕРАС-54 v14, игровая сетка (кандидат): файл просмотра владельцу и кадры сверки с high-poly.

Файл просмотра (студия в файле, нейтральный материал):
"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/veras54_v14/game/game_review.py -- build [<out.blend>]
→ «Игровая версия/Геометрия v14/ВЕРАС-54_игровая_v14_01.blend». Коллекции: «GAME» — LOD0 на месте (узлы игры —
пустышки, сетки «<Узел>__<Атлас>»), «LOD1 (ниже)» — экземпляр GAME_LOD1 на 0,32 м ниже, «Сверка — high-poly (выше)» —
принятая форма v14 ссылкой (файл не копируется, открывается быстро) на 0,32 м выше. Ползунки рига — пустышка
VERAS54_Controls игровой сетки (те же выражения part_rig на узлах; путь гильзы и подъём стопки — только у high-poly).

Кадры сверки (одинаковые камеры, нейтральный материал Workbench, маски силуэта наложением):
"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/veras54_v14/game/game_review.py -- shots [вид,…]
→ _asset_src/veras54_v14/game/shots/<вид>.png (сверху high-poly, ниже low-poly, внизу наложение масок: серое — общее,
красное — есть только у high-poly, голубое — только у low-poly) и shots/silhouette.json (расхождение силуэта, пикс и мм).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'tools/veras54_v14/geo'))
import game_lp as G  # noqa: E402
import part_rig as R  # noqa: E402

LP_FILE = G.OUT / 'VERAS54_Game_LP.blend'
GAME_DIR = Path('E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия/Геометрия v14')
OUT_BLEND = GAME_DIR / 'ВЕРАС-54_игровая_v14_01.blend'
SHOTS = G.WORK / 'shots'
OFFSET_Z = 0.32
log = lambda *a: print('VERAS14_REVIEW', *a, flush=True)  # noqa: E731


def look(cam, pos, target, up=(0.0, 0.0, 1.0)):
    """Камера в pos смотрит на target; up — что в кадре вверх."""
    f = (Vector(target) - Vector(pos)).normalized()
    u = Vector(up)
    if abs(f.dot(u.normalized())) > 0.999:
        u = Vector((1.0, 0.0, 0.0))
    r = f.cross(u).normalized()
    u = r.cross(f).normalized()
    m = Matrix((r, u, -f)).transposed().to_4x4()
    m.translation = Vector(pos)
    cam.matrix_world = m


# вид: (поза, тип, позиция, цель, up, ortho_scale | вертикальный угол °, разрешение)
C = (0.234, 0.0, -0.075)
VIEWS = {
    'left':        (None, 'O', (0.234, 1.5, -0.075), C, (0, 0, 1), 1.0, (2400, 1000)),
    'right':       (None, 'O', (0.234, -1.5, -0.075), C, (0, 0, 1), 1.0, (2400, 1000)),
    'top':         (None, 'O', (0.234, 0.0, 1.5), (0.234, 0.0, 0.0), (1, 0, 0), 1.0, (1000, 2400)),
    'front':       (None, 'O', (1.6, 0.0, -0.075), C, (0, 0, 1), 0.30, (1000, 1000)),
    'back':        (None, 'O', (-1.2, 0.0, -0.075), C, (0, 0, 1), 0.30, (1000, 1000)),
    'hip':         (None, 'P', (-0.15, 0.11, 0.13), (0.30, 0.0, -0.03), (0, 0, 1), 54.0, (1920, 1080)),
    'ads':         (None, 'P', (-0.16, 0.0, 0.0594), (0.60, 0.0, 0.0594), (0, 0, 1), 30.0, (1920, 1080)),
    'ads_peep':    (None, 'P', (-0.10, 0.0, 0.0594), (0.60, 0.0, 0.0594), (0, 0, 1), 3.2, (1200, 1200)),
    'peep_rear':   (None, 'P', (0.005, 0.0, 0.0594), (0.60, 0.0, 0.0594), (0, 0, 1), 9.0, (1200, 1200)),
    'peep_front':  (None, 'P', (0.095, 0.004, 0.0610), (0.0, 0.0, 0.0594), (0, 0, 1), 9.0, (1200, 1200)),
    'sight_right': (None, 'O', (0.076, -1.0, 0.050), (0.076, 0.0, 0.050), (0, 0, 1), 0.095, (1600, 1000)),
    'sight_q':     (None, 'P', (-0.06, -0.10, 0.13), (0.07, 0.0, 0.050), (0, 0, 1), 30.0, (1600, 1200)),
    'sight_far':   ('sight_far', 'P', (-0.06, -0.10, 0.13), (0.07, 0.0, 0.050), (0, 0, 1), 30.0, (1600, 1200)),
    'window':      (None, 'O', (0.195, -1.0, 0.018), (0.195, 0.0, 0.018), (0, 0, 1), 0.14, (1600, 1000)),
    'window_q':    (None, 'P', (0.32, -0.20, 0.14), (0.20, 0.0, 0.015), (0, 0, 1), 30.0, (1600, 1200)),
    'carrier_q':   (None, 'P', (0.215, -0.085, 0.075), (0.200, -0.010, 0.022), (0, 0, 1), 32.0, (1600, 1200)),
    'charged':     ('charged', 'O', (0.195, -1.0, 0.018), (0.195, 0.0, 0.018), (0, 0, 1), 0.14, (1600, 1000)),
    'selector':    (None, 'O', (0.10, -1.0, -0.005), (0.10, 0.0, -0.005), (0, 0, 1), 0.16, (1600, 1000)),
    'handle':      (None, 'P', (0.32, -0.16, 0.10), (0.235, -0.03, 0.010), (0, 0, 1), 30.0, (1600, 1200)),
    'muzzle':      (None, 'O', (0.645, -1.0, 0.0), (0.645, 0.0, 0.0), (0, 0, 1), 0.13, (1600, 1000)),
    'muzzle_q':    (None, 'P', (0.80, -0.12, 0.06), (0.66, 0.0, 0.0), (0, 0, 1), 30.0, (1600, 1200)),
    'gas':         (None, 'O', (0.50, -1.0, 0.02), (0.50, 0.0, 0.02), (0, 0, 1), 0.12, (1600, 1000)),
    'mag':         (None, 'O', (0.205, -1.0, -0.11), (0.205, 0.0, -0.11), (0, 0, 1), 0.24, (1200, 1200)),
    'grip':        (None, 'O', (0.03, -1.0, -0.09), (0.03, 0.0, -0.09), (0, 0, 1), 0.16, (1200, 1200)),
    'stock':       (None, 'O', (-0.13, -1.0, -0.07), (-0.13, 0.0, -0.07), (0, 0, 1), 0.26, (1600, 1200)),
    'folded_top':  ('folded', 'O', (0.234, 0.0, 1.5), (0.06, 0.0, 0.0), (1, 0, 0), 0.75, (1000, 2000)),
    'mag_out':     ('open', 'O', (0.234, -1.5, -0.12), (0.234, 0.0, -0.12), (0, 0, 1), 1.0, (2400, 1200)),
}
FULL = {'left', 'right', 'top', 'front', 'back'}


# ------------------------------------------------------------------------------------------------ кадры сверки
def setup_workbench(res):
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGBA'
    sc.display.render_aa = 'OFF'
    sh = sc.display.shading
    sh.color_type = 'SINGLE'
    sh.single_color = (0.62, 0.62, 0.64)
    sh.light = 'STUDIO'
    sh.show_cavity = False
    sh.show_shadows = False
    sh.show_specular_highlight = True
    sh.show_backface_culling = False


def load_png(path):
    img = bpy.data.images.load(str(path))
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)


def save_png(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new('tmp_sheet', w, h, alpha=False)
    img.pixels.foreach_set(arr.astype(np.float32).ravel())
    img.filepath_raw = str(path)
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def dist_to(mask_from, mask_to, kmax=80):
    """Для каждого пикселя mask_from — расстояние (шагов 8-соседства) до mask_to; дальше kmax — kmax."""
    d = np.full(mask_from.shape, kmax, np.int32)
    cur = mask_to.copy()
    d[mask_from & cur] = 0
    for k in range(1, kmax):
        nxt = cur.copy()
        nxt[1:, :] |= cur[:-1, :]
        nxt[:-1, :] |= cur[1:, :]
        nxt[:, 1:] |= cur[:, :-1]
        nxt[:, :-1] |= cur[:, 1:]
        nxt[1:, 1:] |= cur[:-1, :-1]
        nxt[:-1, :-1] |= cur[1:, 1:]
        nxt[1:, :-1] |= cur[:-1, 1:]
        nxt[:-1, 1:] |= cur[1:, :-1]
        new = nxt & ~cur & mask_from
        d[new] = k
        cur = nxt
        if not (mask_from & ~cur).any():
            break
    return d


def apply_pose(ctl, props, hp, nodes, base_world):
    G.set_props(ctl, {**G.rest_props(), **props})
    G.refresh()
    dg = bpy.context.evaluated_depsgraph_get()
    inv = {v: k for k, v in G.MOVERS.items()}
    def depth(o):
        k = 0
        while o.parent is not None:
            o, k = o.parent, k + 1
        return k
    order = sorted(nodes, key=lambda n: depth(nodes[n]))
    for n in order:
        e = nodes[n]
        src = inv.get(n)
        if n == 'MuzzleDevice' or src is None or src not in hp:
            e.matrix_world = base_world[n]
        else:
            d = hp[src].evaluated_get(dg).matrix_world @ base_world['__src__' + src].inverted()
            e.matrix_world = d @ base_world[n]
        bpy.context.view_layer.update()


def shots(only):
    SHOTS.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(G.SRC))
    hp = {o.name: o for o in bpy.data.objects}
    hp_objs = [o for o in bpy.data.objects if o.type == 'MESH']
    ctl = hp[G.CONTROLS]
    G.set_props(ctl, G.rest_props())
    G.refresh()
    with bpy.data.libraries.load(str(LP_FILE), link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c in ('GAME', 'GAME_LOD1')]
    cols = {c.name: c for c in dst.collections}
    for c in cols.values():
        bpy.context.scene.collection.children.link(c)
        c.hide_render = False
    lp0 = [o for o in cols['GAME'].all_objects if o.type == 'MESH']
    lp1 = [o for o in cols['GAME_LOD1'].all_objects if o.type == 'MESH'] if 'GAME_LOD1' in cols else []
    rec = json.loads((LP_FILE.parent / 'parts.json').read_text(encoding='utf-8'))
    # имена узлов совпадают с деталями исходника (Bolt, Trigger…) — при добавлении получают «.001»
    nodes = {}
    for o in cols['GAME'].all_objects:
        base = o.name.rsplit('.', 1)[0] if o.name not in rec['nodes'] else o.name
        if o.type == 'EMPTY' and base in rec['nodes']:
            nodes[base] = o
    log('узлов', len(nodes), 'из', len(rec['nodes']))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    base_world = {n: e.matrix_world.copy() for n, e in nodes.items()}
    for s in G.MOVERS:
        if s in hp:
            base_world['__src__' + s] = hp[s].evaluated_get(dg).matrix_world.copy()
    cd = bpy.data.cameras.new('cmp')
    cd.clip_start = 0.005
    cam = bpy.data.objects.new('cmp', cd)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    out = json.loads((SHOTS / 'silhouette.json').read_text(encoding='utf-8')) if (SHOTS / 'silhouette.json').exists() else {}
    tmp = SHOTS / '_tmp'
    tmp.mkdir(exist_ok=True)

    def show(objs_on):
        on = set(o.name for o in objs_on)
        for o in hp_objs + lp0 + lp1:
            o.hide_render = o.name not in on

    for name, (pose, kind, pos, tgt, up, sc_, res) in VIEWS.items():
        if only and name not in only:
            continue
        apply_pose(ctl, G.POSES.get(pose, {}) if pose else {}, hp, nodes, base_world)
        if pose == 'sight_far':
            apply_pose(ctl, {'sight_range': 1.0, 'windage': 0.5}, hp, nodes, base_world)
        setup_workbench(res)
        if kind == 'O':
            cd.type = 'ORTHO'
            cd.ortho_scale = sc_
        else:
            cd.type = 'PERSP'
            cd.sensor_fit = 'VERTICAL'
            cd.angle_y = math.radians(sc_)
        look(cam, pos, tgt, up)
        sets = [('hp', hp_objs), ('lp', lp0)] + ([('lod1', lp1)] if name in FULL and lp1 else [])
        img = {}
        for tag, objs in sets:
            show(objs)
            p = tmp / f'{name}_{tag}.png'
            bpy.context.scene.render.filepath = str(p)
            bpy.ops.render.render(write_still=True)
            img[tag] = load_png(p)
        mh = img['hp'][..., 3] > 0.5
        r = {'pose': pose or 'rest', 'kind': kind, 'res': list(res)}
        mm_px = sc_ * 1000.0 / max(res) if kind == 'O' else None
        for tag in [t for t, _ in sets if t != 'hp']:
            ml = img[tag][..., 3] > 0.5
            dh = dist_to(mh & ~ml, ml)      # есть у high-poly, нет у low: насколько далеко low
            dl = dist_to(ml & ~mh, mh)
            vh, vl = dh[mh & ~ml], dl[ml & ~mh]
            st = {'px_hp_only': int(len(vh)), 'px_lp_only': int(len(vl)), 'px_hp': int(mh.sum()),
                  'max_px_hp_only': int(vh.max()) if len(vh) else 0, 'max_px_lp_only': int(vl.max()) if len(vl) else 0,
                  'p99_px': int(np.percentile(np.concatenate([vh, vl]), 99)) if len(vh) + len(vl) else 0,
                  'xor_share': round((len(vh) + len(vl)) / max(int(mh.sum()), 1), 5)}
            if mm_px:
                st['mm_per_px'] = round(mm_px, 4)
                st['max_mm'] = round(max(st['max_px_hp_only'], st['max_px_lp_only']) * mm_px, 2)
                st['p99_mm'] = round(st['p99_px'] * mm_px, 2)
            r[tag] = st
            if True:
                ov = np.zeros(mh.shape + (4,), np.float32)
                ov[..., 3] = 1.0
                ov[..., :3] = 0.05
                ov[mh & ml, :3] = 0.55
                ov[mh & ~ml] = (1.0, 0.1, 0.1, 1.0)
                ov[ml & ~mh] = (0.1, 0.9, 1.0, 1.0)
                if tag == 'lp':
                    ov_lp = ov
                else:
                    save_png(ov, SHOTS / f'{name}_{tag}_overlay.png')
        def flat(a):
            b = a.copy()
            b[..., :3] = a[..., :3] * a[..., 3:4] + 0.10 * (1 - a[..., 3:4])
            b[..., 3] = 1.0
            return b
        # Blender хранит пиксели снизу вверх: сверху в листе — high-poly
        sheet = np.concatenate([ov_lp, flat(img['lp']), flat(img['hp'])], axis=0)
        save_png(sheet, SHOTS / f'{name}.png')
        out[name] = r
        log(name, {k: v for k, v in r.items() if k in ('lp', 'lod1')})
    (SHOTS / 'silhouette.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')


# ------------------------------------------------------------------------------------------------ файл просмотра
def neutral_material():
    m = bpy.data.materials.get('Сверка • нейтральный') or bpy.data.materials.new('Сверка • нейтральный')
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (0.32, 0.32, 0.33, 1)
    b.inputs['Roughness'].default_value = 0.42
    b.inputs['Metallic'].default_value = 0.0
    m.diffuse_color = (0.32, 0.32, 0.33, 1)
    return m


def studio(center):
    S = bpy.context.scene
    coll = bpy.data.collections.new('Студия просмотра')
    S.collection.children.link(coll)
    w = bpy.data.worlds.new('ВЕРАС-54 • студия')
    w.use_nodes = True
    bg = w.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.03, 0.03, 0.035, 1)
    bg.inputs['Strength'].default_value = 1.0
    S.world = w

    def light(name, direction, dist, energy, size):
        d = bpy.data.lights.new(name, 'AREA')
        d.energy = energy
        d.shape = 'DISK'
        d.size = size
        o = bpy.data.objects.new(name, d)
        coll.objects.link(o)
        o.location = center + Vector(direction).normalized() * dist
        o.rotation_euler = (center - o.location).to_track_quat('-Z', 'Y').to_euler()
    light('Студия • ключевой (справа спереди сверху)', (0.45, -0.75, 0.70), 2.0, 300, 1.2)
    light('Студия • заполняющий (слева)', (-0.30, 0.90, 0.20), 2.1, 130, 1.4)
    light('Студия • контровой (сзади сверху)', (-0.60, 0.30, 0.80), 1.9, 220, 0.8)
    light('Студия • снизу', (0.1, -0.3, -1.0), 2.0, 60, 1.5)
    cd = bpy.data.cameras.new('Студия • камера')
    cd.lens = 50
    cd.clip_start = 0.01
    cam = bpy.data.objects.new('Студия • камера', cd)
    coll.objects.link(cam)
    cam.location = center + Vector((-0.35, -0.80, 0.42)).normalized() * 1.9
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
    S.camera = cam
    S.render.engine = 'BLENDER_EEVEE'
    S.render.resolution_x, S.render.resolution_y = 1920, 1080
    S.view_settings.view_transform = 'AgX'


def rig(nodes):
    """Пустышка VERAS54_Controls и приводы part_rig на узлах игры (сетки сняты в позе умолчаний + патрон в патроннике)."""
    c = bpy.data.objects.new('VERAS54_Controls', None)
    c.empty_display_type = 'PLAIN_AXES'
    c.empty_display_size = 0.03
    bpy.context.scene.collection.objects.link(c)
    rest = G.rest_props()
    for k, tip, default in R.SLIDERS:
        c[k] = float(rest[k])
        ui = c.id_properties_ui(k)
        ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description=tip)
    n = 0
    for name, path, index, expr, props in R.drivers():
        o = nodes.get(G.MOVERS.get(name))
        if o is None:
            continue
        env = {'max': max, 'min': min, 'abs': abs, 'clamp': lambda x, a, b: min(max(x, a), b)}
        v0 = eval(expr, env, dict(rest))
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


README = """ВЕРАС-54 v14 — игровая сетка, КАНДИДАТ ретопологии (без текстур, нейтральный материал)

Коллекции (галочка в Outliner):
  «GAME» — LOD0 (в руках): узлы игры — пустышки в осях подвижных деталей, сетки «<Узел>__<Атлас>» — их дочерние;
    патроны магазина — Round_01…30 (одна сетка), патрон в патроннике — Chamber_Round / Chamber_Bullet.
  «LOD1 (ниже)» — то же, упрощённое до ¼, на 0,32 м ниже.
  «Сверка — high-poly (выше)» — принятая форма v14 ссылкой на 0,32 м выше (тяжёлая: 9 млн треугольников —
    выключить галочкой, если вьюпорт тормозит).
Ползунки — пустышка VERAS54_Controls (Object → Custom Properties): рама, затвор, переводчик, спуск, защёлка, магазин,
приклад, целик и др. — те же выражения, что у high-poly (путь гильзы и подъём стопки патронов в игровой сетке не заданы).
Числа (треугольники по узлам, отклонения, развёртка) — retopo-report.json рядом; кадры сверки —
RING-godot/_asset_src/veras54_v14/game/shots.
"""


def build(out):
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(LP_FILE))
    rec = json.loads((LP_FILE.parent / 'parts.json').read_text(encoding='utf-8'))
    mat = neutral_material()
    nodes = {}
    for o in bpy.data.objects:
        if o.type == 'EMPTY' and o.name in rec['nodes']:
            nodes[o.name] = o
        if o.type == 'MESH' and 'atlas' in o:
            o.data.materials.clear()
            o.data.materials.append(mat)
    rig(nodes)
    # LOD1 — экземпляром ниже; сама коллекция исключена из слоя (объекты держатся на узлах GAME)
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
    # high-poly ссылкой
    with bpy.data.libraries.load(str(G.SRC), link=True, relative=True) as (src, dst):
        dst.collections = ['ВЕРАС-54']
    hc = bpy.data.collections.new('Сверка — high-poly (выше)')
    bpy.context.scene.collection.children.link(hc)
    h = bpy.data.objects.new('High-poly v14 • экземпляр', None)
    h.instance_type = 'COLLECTION'
    h.instance_collection = dst.collections[0]
    h.location = (0, 0, OFFSET_Z)
    hc.objects.link(h)
    studio(Vector((0.234, 0.0, -0.075)))
    txt = bpy.data.texts.get('Как смотреть') or bpy.data.texts.new('Как смотреть')
    txt.clear()
    txt.write(README)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True, relative_remap=True)
    log('файл просмотра →', out)


def report():
    """retopo-report.json рядом с файлом просмотра (навык weapon-retopology): по деталям, узлам и атласам."""
    import datetime
    rec = json.loads((LP_FILE.parent / 'parts.json').read_text(encoding='utf-8'))
    sil = json.loads((SHOTS / 'silhouette.json').read_text(encoding='utf-8')) if (SHOTS / 'silhouette.json').exists() else {}
    objs = []
    for name, p in rec['parts'].items():
        objs.append({'name': name, 'node': p['node'], 'atlas': p['atlas'], 'source_evaluated_tris': p['hp_tris'],
                     'candidate_evaluated_tris': p['tris'], 'budget': p.get('budget'), 'copies': p.get('copies', 1),
                     'deviation_mm': p['dev_mm'], 'change': 'tube' if p.get('uv') == 'cyl' else 'decimate_budget',
                     'plain_source': bool(p.get('plain_source')),
                     'deviation_note': 'упрощалась гладкая деталь (VERAS_PLAIN): отклонение от полной формы = высота снятого '
                                       'рельефа, он уйдёт в карту нормалей' if p.get('plain_source') else '',
                     'uv_transfer': 'new_unwrap'})
    nodes = {n: {'parent': v['parent'], 'pivot_m': v['pivot'], 'meshes': v.get('mesh_tris', {}),
                 'meshes_lod1': v.get('mesh_tris_lod1', {})} for n, v in rec['nodes'].items()}
    atl = {a: {k: v.get(k) for k in ('size', 'fill', 'px_mm', 'islands', 'report', 'verify')} for a, v in rec['atlases'].items()}
    out = {
        'schema_version': '1.0', 'asset': 'ВЕРАС-54 v14', 'date': datetime.date.today().isoformat(), 'status': 'CANDIDATE',
        'source_blend': str(G.SRC), 'derived_blend': str(OUT_BLEND), 'lp_work_blend': str(LP_FILE),
        'tools': ['tools/veras54_v14/game/game_lp.py', 'tools/veras54_v14/game/game_review.py'],
        'source_collection': 'ВЕРАС-54 (все дочерние)', 'candidate_collection': 'GAME (LOD0), GAME_LOD1',
        'target_context': 'fps_viewmodel', 'approved_geometry': True,
        'totals': {'source_tris': sum(p['hp_tris'] for n, p in rec['parts'].items() if not p.get('copies'))
                   + sum(p['hp_tris'] for p in rec['parts'].values() if p.get('copies')) * 30,
                   'weapon_lod0_tris': rec.get('tris_weapon_lod0'), 'rounds_lod0_tris': rec.get('tris_rounds_lod0'),
                   'round_tris': rec.get('tris_round_final'), 'weapon_lod1_tris': rec.get('tris_weapon_lod1'),
                   'rounds_lod1_tris': rec.get('tris_rounds_lod1'), 'removed_contact_faces': rec.get('removed_contact', {}),
                   'magazine_lod0_tris': sum(v for n in ('Magazine', 'Magazine_Follower')
                                             for k, v in rec['nodes'][n].get('mesh_tris', {}).items() if k != 'Round_01'),
                   'budget_hands': 40000, 'budget_weapon_no_mag': 38000, 'budget_magazine': 4000},
        'objects': objs,
        'plain_source': {'blend': str(G.PLAIN_BLEND), 'parts': list(G.PLAIN_PARTS),
                         'how': 'VERAS_PLAIN=1 VERAS_TAG=plain VERAS_BASE= bash tools/veras54_v14/geo/go.sh 1 "<детали>"; '
                                'game_lp.py -- --dump-plain'}, 'nodes': nodes, 'atlases': atl, 'marks': rec['marks'], 'rounds_fit': rec['rounds'],
        'visual_checks': {'camera_views': sorted(sil), 'measured': bool(sil), 'silhouette': sil,
                          'method': 'Workbench, нейтральный материал, без сглаживания; маски альфы high / low, расстояние '
                                    'пикселей несовпадения до другой маски (8-соседство); мм — только у ортокамер',
                          'shots_dir': str(SHOTS)},
        'unchanged_objects': ['исходник v14_04 не менялся (открыт только на чтение)'],
        'dependent_steps_to_rerun': ['UV (после приёмки low-poly)', 'normal_bake', 'Godot_import_validation'],
        'owner_review': 'pending', 'next_skill': 'weapon-asset-texturing',
    }
    p = GAME_DIR / 'retopo-report.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    log('отчёт →', p)


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    mode = a[0] if a else 'build'
    if mode == 'build':
        build(Path(a[1]) if len(a) > 1 else OUT_BLEND)
    elif mode == 'report':
        report()
    else:
        shots(set(a[1].split(',')) if len(a) > 1 else set())
