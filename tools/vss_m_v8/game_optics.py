"""Прицелы ВСС-М v8 (ПСО 4×24 и 4×32, отделка Painter) → обвесы игры: сетка, развёртка, запекание, карты, glTF.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/vss_m_v8/game_optics.py -- [pso] [s432]
Источник — _asset_src/vss_m_v8/sights_sp.blend (наборы optic_* с картами sp_sights/export; стёкла — свои материалы).
→ assets/models/attachments/<id>/<id>.gltf + <id>_100_{base_color,roughness,metallic,normal}.png — схема обвесов-моделей
  игры (WeaponMods._model_part): сетки Body* получают материал из этих карт, Lens — стекло со своим материалом.
  Начало модели — место посадки: у ПСО — точка на «ласточкином хвосте» ВСС (в комбо 361, 22, −1.75 мм от начала
  винтовки), у 4×32 — середина зажима на верху планки Пикатинни. Оси игры: +Z — к дулу, +Y — вверх, −X — вправо.
  Окуляр (центр задней линзы), высота оси и смещение оси вбок — в <id>.json для данных игры (attach.model).
Один атлас на прицел (2048): корпус, ободки, гравировка, резина. Развёртка — tools/asset_kit/uv.py.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools/vss_m_v8'))
from asset_kit import uv as kit_uv  # noqa: E402
import sp_apply  # noqa: E402

SRC = ROOT / '_asset_src/vss_m_v8/sights_sp.blend'
SIGHTS_EXPORT = str(ROOT / '_asset_src/vss_m_v8/sp_sights/export')
WORK = ROOT / '_asset_src/vss_m_v8_game/optics'
WORK.mkdir(parents=True, exist_ok=True)
SIZE = 2048
SCOPES = {
    # id: (корень исходника, бюджет корпуса, глубокие детали сжать сильнее, вынос глаза, мм)
    'pso_vss': ('PSO_VSS_4x24', 8000, {'Rubber_eyecup': 900}, 68.0),
    'scope_4x32': ('Rail_4x32', 7000, {}, 75.0),
}
log = lambda *a: print('VSS_OPTICS', *a, flush=True)


def tris(me) -> int:
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def select_only(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def decimate(o, budget):
    n = tris(o.data)
    if n <= budget:
        return
    select_only(o)
    d = o.modifiers.new('budget', 'DECIMATE')
    d.ratio = budget / n
    d.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier=d.name)


def build(sid):
    root_name, budget, special, eye_relief = SCOPES[sid]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(SRC), link=False) as (src, dst):
        dst.objects = list(src.objects)
    coll = bpy.context.scene.collection
    hp = []
    for o in dst.objects:
        if o is None:
            continue
        r = o
        while r.parent is not None:
            r = r.parent
        if r.name.split('.')[0] == root_name:
            coll.objects.link(o)
            hp.append(o)
        else:
            bpy.data.objects.remove(o, do_unlink=True)
    dg = bpy.context.evaluated_depsgraph_get()
    body, lens, sources = [], [], []
    for o in hp:
        if o.type != 'MESH':
            continue
        mats = [s.material.name.split('.')[0] for s in o.material_slots if s.material]
        eo = o.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(eo, depsgraph=dg)
        me.transform(eo.matrix_world)
        c = bpy.data.objects.new('lp_' + o.name, me)
        coll.objects.link(c)
        if any('glass' in m.lower() for m in mats):
            lens.append(c)
            continue
        key = o.name.replace(root_name + '_', '')
        if key in special:
            decimate(c, special[key])
        body.append(c)
        sources.append(o)
    total = sum(tris(o.data) for o in body)
    if total > budget:
        for o in body:
            n = tris(o.data)
            if n > 400:
                decimate(o, int(n * budget / total))
    for o in body + lens:
        for uv in list(o.data.uv_layers):
            o.data.uv_layers.remove(uv)
        o.data.materials.clear()
    select_only(body[0])
    for o in body:
        o.select_set(True)
    bpy.ops.object.join()
    b = bpy.context.view_layer.objects.active
    b.name = 'Body'
    select_only(lens[0])
    for o in lens:
        o.select_set(True)
    bpy.ops.object.join()
    ln = bpy.context.view_layer.objects.active
    ln.name = 'Lens'
    kit_uv.smart_unwrap([b])
    cls = kit_uv.visibility([b])
    # прицел осматривают в руках и в конструкторе — плотность ровная, без глаза
    rep = kit_uv.layout([b], SIZE, classes=cls, log=log)
    kit_uv.harden_on_seams([b])
    rep['report'] = kit_uv.report([b], SIZE, classes=cls)
    for p in b.data.polygons:
        p.use_smooth = True
    # запекание с исходника (материалы Painter): цвет / шероховатость / металл свечением, нормали
    for o in sources:
        for s in o.material_slots:
            nm = s.material.name.split('.')[0] if s.material else ''
            if nm.startswith('optic_'):
                s.material = sp_apply.material(nm, SIGHTS_EXPORT)
    mat = bpy.data.materials.new(f'{sid}_bake')
    mat.use_nodes = True
    b.data.materials.append(mat)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == 'OPTIX'
        sc.cycles.device = 'GPU'
    except Exception:
        sc.cycles.device = 'CPU'
    bk = sc.render.bake
    bk.use_clear = True
    bk.margin = 6
    bk.use_selected_to_active = True
    bk.cage_extrusion = 0.0015
    bk.max_ray_distance = 0.004
    kit_uv.shift_stack_copies([b], 1.0)
    maps = {}
    for ch, kind in (('base_color', 'color'), ('roughness', 'rough'), ('metallic', 'metal'), ('normal', 'normal')):
        img = bpy.data.images.new(f'{sid}_{ch}', SIZE, SIZE, alpha=False)
        img.colorspace_settings.name = 'sRGB' if ch == 'base_color' else 'Non-Color'
        if ch == 'normal':
            img.generated_color = (0.5, 0.5, 1, 1)
        nt = mat.node_tree
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = img
        nt.nodes.active = t
        swaps = []
        if kind != 'normal':
            for o in sources:
                for s in o.material_slots:
                    m = s.material
                    if m is None or not m.use_nodes or any(x[0] == m for x in swaps):
                        continue
                    mnt = m.node_tree
                    out = next(n for n in mnt.nodes if n.type == 'OUTPUT_MATERIAL')
                    bsdf = next((n for n in mnt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                    if bsdf is None:
                        continue
                    keep = out.inputs['Surface'].links[0].from_socket if out.inputs['Surface'].links else None
                    em = mnt.nodes.new('ShaderNodeEmission')
                    src = {'color': bsdf.inputs['Base Color'], 'rough': bsdf.inputs['Roughness'], 'metal': bsdf.inputs['Metallic']}[kind]
                    if src.links:
                        mnt.links.new(src.links[0].from_socket, em.inputs['Color'])
                    else:
                        v = src.default_value
                        em.inputs['Color'].default_value = (v[0], v[1], v[2], 1) if kind == 'color' else (v, v, v, 1)
                    mnt.links.new(em.outputs[0], out.inputs['Surface'])
                    swaps.append((m, em, keep, out))
        sc.cycles.samples = 16 if kind == 'normal' else 1
        bpy.ops.object.select_all(action='DESELECT')
        for o in sources:
            o.select_set(True)
        b.select_set(True)
        bpy.context.view_layer.objects.active = b
        bpy.ops.object.bake(type='NORMAL' if kind == 'normal' else 'EMIT', normal_space='TANGENT')
        for m, em, keep, out in swaps:
            m.node_tree.nodes.remove(em)
            if keep is not None:
                m.node_tree.links.new(keep, out.inputs['Surface'])
        maps[ch] = img
        nt.nodes.remove(t)
    kit_uv.shift_stack_copies([b], -1.0)
    out_dir = ROOT / 'assets/models/attachments' / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    for ch, img in maps.items():
        img.filepath_raw = str(out_dir / f'{sid}_100_{ch}.png')
        img.file_format = 'PNG'
        img.save()
    # игровой материал корпуса (для glTF; в игре его заменяет материал из тех же карт) и стекло
    b.data.materials.clear()
    gm = bpy.data.materials.new(f'{sid}_body')
    gm.use_nodes = True
    nt = gm.node_tree
    pr = next(n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED')
    for ch, sock, cs in (('base_color', 'Base Color', 'sRGB'), ('roughness', 'Roughness', 'Non-Color'), ('metallic', 'Metallic', 'Non-Color')):
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = maps[ch]
        t.image.colorspace_settings.name = cs
        nt.links.new(t.outputs['Color'], pr.inputs[sock])
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = maps['normal']
    nm = nt.nodes.new('ShaderNodeNormalMap')
    nt.links.new(t.outputs['Color'], nm.inputs['Color'])
    nt.links.new(nm.outputs['Normal'], pr.inputs['Normal'])
    b.data.materials.append(gm)
    lm = bpy.data.materials.new(f'{sid}_lens')
    lm.use_nodes = True
    lp = next(n for n in lm.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    lp.inputs['Base Color'].default_value = (0.02, 0.03, 0.035, 1)
    lp.inputs['Roughness'].default_value = 0.04
    lp.inputs['Alpha'].default_value = 0.55
    lm.surface_render_method = 'BLENDED'
    ln.data.materials.clear()
    ln.data.materials.append(lm)
    # метки оптики (оси исходника, м): окуляр — центр задней линзы; ось — середина главной трубы
    tube = [o for o in hp if o.type == 'MESH' and o.name.endswith('Main_tube')][0]
    tp = [tube.matrix_world @ Vector(c) for c in tube.bound_box]
    axis_y = (min(p.y for p in tp) + max(p.y for p in tp)) / 2
    axis_z = (min(p.z for p in tp) + max(p.z for p in tp)) / 2
    ocl = [o for o in hp if o.type == 'MESH' and o.name.endswith('Ocular_lens')][0]
    op = [ocl.matrix_world @ Vector(c) for c in ocl.bound_box]
    oc_x = (min(p.x for p in op) + max(p.x for p in op)) / 2
    oc_r = (max(p.y for p in op) - min(p.y for p in op)) / 2
    to_game = Matrix.Rotation(math.radians(-90), 4, 'Z')
    for o in (b, ln):
        o.data.transform(to_game)
        o.matrix_world = Matrix.Identity(4)
    g = lambda p: [round(p[1], 5), round(p[2], 5), round(p[0], 5)]          # (x, y, z)_исх → оси игры
    info = {'id': sid, 'source': str(SRC), 'root': root_name, 'tris': tris(b.data), 'tris_lens': tris(ln.data),
            'ocular': g((oc_x, axis_y, axis_z)), 'ocular_r': round(oc_r, 5), 'sight_h': round(axis_z, 5),
            'sight_x': round(axis_y, 5), 'eye_relief': eye_relief / 1000.0, 'uv': rep['report']}
    select_only(b)
    ln.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(out_dir / f'{sid}.gltf'), export_format='GLTF_SEPARATE', use_selection=True,
                              export_apply=True, export_yup=True, export_animations=False, export_image_format='AUTO',
                              export_texture_dir='')
    (out_dir / f'{sid}.json').write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    log(sid, info['tris'], 'окуляр', info['ocular'], 'r', info['ocular_r'], 'ось', info['sight_x'], info['sight_h'],
        'развёртка', rep['report']['fill'], rep['report']['px_mm'])


args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
names = [n for n in SCOPES if not args or n in args or ('pso' in args and n == 'pso_vss') or ('s432' in args and n == 'scope_4x32')]
for n in names:
    build(n)
