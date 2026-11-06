"""ИЗЛОМ-45: игровая сетка только магазинов v2 (Glock 21 на 13 и на 30 с удлинителем, part_magazine.py) — из геометрии
v07; остальные узлы игровой сетки и их развёртка не меняются (корпус уже затекстурирован).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b -y --factory-startup --python-exit-code 1 --python tools/smg03/game_lp_mags.py
→ _asset_src/smg03/game/lp/SMG03_Game_LP_mags_v2.blend (узлы Mag13, Mag30: атлас = имя, узел игры Magazine) и
  parts_mags_v2.json. Как game_lp.py: упрощение схлопыванием по бюджету детали, классы граней лучами (магазины — сами по себе
  и в позах исходника), прижатое — прочь, развёртка tools/asset_kit/uv.py в свои атласы 2K, нормали по площади граней.
Дальше — game_tex.py с SMG03_TEX_LP (этот файл), SMG03_TEX_SRC (v07), SMG03_TEX_OUT (_asset_src/smg03/tex_mags).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/smg03'))
import game_lp as G  # noqa: E402

SRC = Path('E:/Models Blender/WEAPONS/Vector — модель/ПП-Vector_геометрия_v07.blend')
# корпуса и рукав для игровой сетки — та же сборка без контрольных окон и рифления (SMG03_LP_SOURCE=1 build.py --
# <файл> magazine): канавки в упрощённой сетке рвали развёртку рукава на сотни островов (заполнение 61 %), и запекание
# в них било изнанку (5 % дорисовано); рифление и окна — в карте нормалей с настоящей формы
LP_SOURCE = ROOT / '_asset_src/smg03/mags_v2/SMG03_mags_v2_lpsrc.blend'
LP_FROM_SOURCE = ('Magazine13_body', 'Magazine30_body', 'Magazine30_sleeve')
OUT_BLEND = G.OUT / 'SMG03_Game_LP_mags_v2.blend'
OUT_JSON = G.OUT / 'parts_mags_v2.json'
SIZE = 2048
# деталь → (атлас, бюджет): корпус Glock с окнами и вырезами, донышко, подаватель (виден у пустого), верхний патрон;
# у 30 — корпус выше рукава, рукав с рифлением (рифление и окна — геометрией с упрощением, мелочь — в нормаль)
PARTS = {
    'Magazine13_body': ('Mag13', 1800), 'Magazine13_floorplate': ('Mag13', 300), 'Magazine13_follower': ('Mag13', 120),
    'Magazine13_round_00_case': ('Mag13', 240), 'Magazine13_round_00_bullet': ('Mag13', 160),
    'Magazine30_body': ('Mag30', 1500), 'Magazine30_sleeve': ('Mag30', 1400), 'Magazine30_floorplate': ('Mag30', 300),
    'Magazine30_follower': ('Mag30', 120), 'Magazine30_round_00_case': ('Mag30', 240),
    'Magazine30_round_00_bullet': ('Mag30', 160),
}


def main():
    bpy.ops.wm.open_mainfile(filepath=str(SRC))
    G.log('магазины показаны без драйверов видимости:', G.show_hidden_mags())
    hp = {o.name: o for o in bpy.data.objects}
    lp_src = {}
    with bpy.data.libraries.load(str(LP_SOURCE)) as (src, dst):
        dst.objects = [n for n in LP_FROM_SOURCE if n in src.objects]
    for n, ob in zip(LP_FROM_SOURCE, dst.objects):
        if ob is not None:
            bpy.context.scene.collection.objects.link(ob)
            ob.name = 'lpsrc_' + n
            lp_src[n] = ob
    G.log('магазины для игровой сетки — из', LP_SOURCE.name, list(lp_src))
    poses, pivots = G.control_poses()
    coll = bpy.data.collections.new('LP_MAGS')
    bpy.context.scene.collection.children.link(coll)
    rec = {'source': str(SRC), 'parts': {}, 'nodes': {}, 'atlases': {}}
    pieces, sources = {}, {}
    for name, (atlas, budget) in PARTS.items():
        o = G.evaluated_copy(lp_src.get(name, hp[name]), 'lp_' + name, coll)
        n0 = G.tris(o.data)
        n = G.simplify(o, min(budget, n0))
        dev = G.deviation(o, hp[name])
        rec['parts'][name] = {'node': 'Magazine', 'atlas': atlas, 'hp_tris': n0, 'tris': n, 'dev_mm': dev}
        pieces.setdefault(atlas, []).append(o)
        sources[o.name] = [name]
        G.log('магазин', name, n0, '→', n, 'отклонение', dev)
    for o in list(bpy.data.objects):
        if o.name not in coll.objects:
            bpy.data.objects.remove(o, do_unlink=True)
    game = []
    for atlas, objs in pieces.items():
        hp_list = sum((sources[o.name] for o in objs), [])
        for k, o in enumerate(objs):
            a = o.data.attributes.new('hp_part', 'INT', 'FACE')
            a.data.foreach_set('value', [k] * len(o.data.polygons))
        j = G.join(objs, atlas) if len(objs) > 1 else objs[0]
        j.name = atlas
        j.data.name = atlas
        j.data.materials.clear()
        j.data.materials.append(G.material(atlas))
        for p in j.data.polygons:
            p.material_index = 0
        j['atlas'] = atlas
        j['node'] = 'Magazine'
        j['hp'] = hp_list
        game.append(j)
        rec['nodes'][atlas] = {'node': 'Magazine', 'atlas': atlas, 'tris': G.tris(j.data), 'hp': hp_list}
    G.kit_uv.smart_unwrap(game)
    cls = G.assembly_classes(game, poses)
    dropped = sum(G.drop_faces(o, [i for i, k in enumerate(cls[o.name]) if k == G.kit_uv.CONTACT]) for o in game)
    G.log('прижатых граней удалено:', dropped)
    cls = G.assembly_classes(game, poses)
    for o in game:
        c = [cls[o.name]]
        rep = G.kit_uv.layout([o], SIZE, classes=c, eyes=[], occluders=game, log=G.log)
        G.kit_uv.harden_on_seams([o])
        rep['report'] = G.kit_uv.report([o], SIZE, classes=c)
        rep['verify'] = G.kit_uv.verify([o], SIZE, classes=c)
        rec['atlases'][o.name] = {'size': SIZE, 'objects': [o.name], **rep}
        G.log('атлас', o.name, SIZE, rep['report'])
    for o in game:
        for p in o.data.polygons:
            p.use_smooth = True
        G.weighted_normals(o)
        rec['nodes'][o.name]['tris'] = G.tris(o.data)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND), compress=True)
    OUT_JSON.write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=list), encoding='utf-8', newline='\n')
    G.log('сохранено', OUT_BLEND, {k: v['tris'] for k, v in rec['nodes'].items()})


if __name__ == '__main__':
    main()
