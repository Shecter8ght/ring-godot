"""ИЗЛОМ-45: магазины v2 (игровая сетка game_lp_mags.py, приняты владельцем 06.11 вместе с износом v2) — в игровую сетку
оружия вместо прежних: узлы Mag13 и Mag30 в SMG03_Game_LP.blend заменяются узлами из SMG03_Game_LP_mags_v2.blend,
записи атласов, узлов и деталей магазинов в parts.json — из parts_mags_v2.json. Остальные узлы не трогаются. Прежний
файл — копией SMG03_Game_LP_mags_v1.blend (и parts_mags_v1.json), если копии ещё нет.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/smg03/game_lp_mags_merge.py
Дальше — game_export.py (карты магазинов — из «Текстуры_магазины_v2_износ_v2»).
"""
import json
import shutil
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
LPD = ROOT / '_asset_src/smg03/game/lp'
GAME = LPD / 'SMG03_Game_LP.blend'
MAGS = LPD / 'SMG03_Game_LP_mags_v2.blend'
ATLASES = ('Mag13', 'Mag30')


def log(*a):
    print('SMG03_MERGE', *a, flush=True)


def main():
    if not (LPD / 'SMG03_Game_LP_mags_v1.blend').exists():
        shutil.copy2(GAME, LPD / 'SMG03_Game_LP_mags_v1.blend')
        shutil.copy2(LPD / 'parts.json', LPD / 'parts_mags_v1.json')
        log('прежние — копией _mags_v1')
    bpy.ops.wm.open_mainfile(filepath=str(GAME))
    colls = {}
    for at in ATLASES:
        old = bpy.data.objects.get(at)
        if old is not None:
            colls[at] = list(old.users_collection)
            log('прежний', at, len(old.data.polygons), 'граней')
            bpy.data.objects.remove(old, do_unlink=True)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    with bpy.data.libraries.load(str(MAGS)) as (src, dst):
        dst.objects = [n for n in ATLASES if n in src.objects]
    for o in dst.objects:
        for c in colls.get(o.name) or [bpy.context.scene.collection]:
            c.objects.link(o)
        o.data.calc_loop_triangles()
        log('новый', o.name, len(o.data.loop_triangles), 'треугольников, развёртки', [u.name for u in o.data.uv_layers],
            'узел', o.get('node'), 'атлас', o.get('atlas'))
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(GAME), compress=True)
    rec = json.loads((LPD / 'parts.json').read_text(encoding='utf-8'))
    new = json.loads((LPD / 'parts_mags_v2.json').read_text(encoding='utf-8'))
    rec['parts'] = {k: v for k, v in rec['parts'].items() if not k.startswith(('Magazine13', 'Magazine30'))}
    rec['parts'].update(new['parts'])
    for at in ATLASES:
        node = dict(new['nodes'][at])
        node['pivot'] = rec['nodes'].get(at, {}).get('pivot', [0.0, 0.0, 0.0])
        rec['nodes'][at] = node
        rec['atlases'][at] = new['atlases'][at]
    rec['mag30_tris_final'] = new['nodes']['Mag30']['tris']
    rec['mags_source'] = new['source']
    (LPD / 'parts.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1, default=list), encoding='utf-8',
                                    newline='\n')
    log('parts.json обновлён:', {at: rec['nodes'][at]['tris'] for at in ATLASES})


if __name__ == '__main__':
    main()
