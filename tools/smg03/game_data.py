"""ИЗЛОМ-45 в данные игры: модель с планками Picatinny, ствол, магазины на 13 и 30, хват рук — из отчёта экспорта
(assets/models/weapons/smg03/smg03.json, game_export.py). Как у ГРАНЬ-15 (tools/ar15/game_data.py).

python -X utf8 tools/smg03/game_data.py
Пишет в data/weapons.json (models.smg03, weapons.wpn_smg_03, magazines.mag_45_vector13 / mag_45_vector30 — id прежние
ради сохранений) и data/weapon_grips.json (smg03). Повторный запуск перезаписывает те же ключи.
Прежняя запись wpn_smg_03 была процедурной заглушкой с настоящим названием прототипа — маркировка у нас вымышленная.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REP = json.loads((ROOT / 'assets/models/weapons/smg03/smg03.json').read_text(encoding='utf-8'))
WEAPONS = ROOT / 'data/weapons.json'
GRIPS = ROOT / 'data/weapon_grips.json'
CLAMP_HALF = 0.015                      # половина зажима обвеса по умолчанию (weapon_build.gd: clamp_m 0,03)
ASSET = 'res://assets/models/weapons/smg03/'
GX = REP['grip_source_m'][0]
# глаз в прицеливании — над гребнем приклада за целиком; v1 — 12 см (как у ГРАНЬ-15), владелец 06.11: «ощущение, что
# он толстый» — у Vector за целиком высокий задний блок, вблизи он закрывал низ кадра: 17 см (сравнение A/B/C)
ADS_Z = 0.17
# у бедра — дальше и ниже общей позы (Balance.FPS_HIP_POSE 0.09, −0.12, −0.35): коробка Vector высокая и короткая,
# на общем месте она заслоняла пол-кадра
HIP_POSE = [0.11, -0.14, -0.42]
# клипы рук (tools/smg03/clips: риг на мастере FPS-рук v14, сценарии build_clips.py, выгрузка export_viewmodel.py) — сцена
# в осях камеры; рукоятка в Blender стоит там же, где у ВЕРАСа (0.14, −0.165, −0.343 от глаза), hip_offset уводит её на HIP_POSE
VIEWMODEL = {'scene': 'res://assets/models/weapons/smg03/smg03_viewmodel.gltf', 'fps': 30,
             'clips': {'idle': 'idle', 'reload': 'reload_tactical', 'reload_empty': 'reload_full', 'check': 'mag_check',
                       'clear': 'jam_clear', 'inspect': 'inspect'},
             'check_hold': [38, 56], 'swap_frame': {'reload_tactical': 38, 'reload_full': 38}, 'jam_open': 0.3,
             'inspect_sec': 4.0, 'hold_open': True, 'hands_fixed': True, 'ads_z': ADS_Z,
             'hip_offset': [round(HIP_POSE[0] - 0.14, 3), round(HIP_POSE[1] + 0.165, 3), round(HIP_POSE[2] + 0.343, 3)],
             'hip_pose': HIP_POSE}
# свободные участки верхней планки (оси игры z от хвата): за основанием целика (X −205 мм исходника) до середины коробки
# и от неё до основания мушки (X 80 мм) — откидные прицельные стоят на планке и занимают её концы
FREE_TOP = {'optic_primary': (-0.205 - GX, -0.040 - GX), 'top_front': (-0.025 - GX, 0.080 - GX)}
BORE_R = 0.0057                         # .45 ACP


def r5(v) -> float:
    return round(float(v), 5)


def rail(slots: list, lo: float, hi: float) -> list:
    """rail_z по пазам в [lo, hi]: зажим (±15 мм) не свисает, начало — середина первого паза − 15 мм."""
    ok = [z for z in slots if z - CLAMP_HALF >= lo - 0.001 and z + CLAMP_HALF <= hi + 0.001]
    if not ok:
        ok = [min(slots, key=lambda z: abs(z - 0.5 * (lo + hi)))]
    return [r5(ok[0] - CLAMP_HALF), r5(ok[-1] + CLAMP_HALF)]


def model() -> dict:
    rg = REP['rails_game']
    marks = REP['marks_game_m']
    piv = REP['pivots_game_m']
    top = rg['RailTop']
    top_y = r5(top['line_xy'][1])
    socks = {}
    for point, (lo, hi) in FREE_TOP.items():
        rz = rail(top['slots_z'], lo, hi)
        socks[point] = {'pos': [0.0, top_y, r5(0.5 * (rz[0] + rz[1]))], 'rail': False, 'rail_z': rz}
    for point, key in (('side_left', 'RailLeft'), ('side_right', 'RailRight')):
        r = rg[key]
        seg = r['z'][0]
        rz = rail(r['slots_z'], seg[0], seg[1])
        socks[point] = {'pos': [r5(r['line_xy'][0]), r5(r['line_xy'][1]), r5(0.5 * (rz[0] + rz[1]))], 'side': True,
                        'rail_z': rz, 'overhang': True}
    b = rg['RailBottom']
    seg = b['z'][0]
    rz = rail(b['slots_z'], seg[0], seg[1])
    socks['underbarrel'] = {'pos': [0.0, r5(b['line_xy'][1]), r5(0.5 * (rz[0] + rz[1]))], 'rail_z': rz}
    # обвес на резьбу — от конца резьбы (заглушка MuzzleDevice при этом прячется)
    t = marks['ThreadTip']
    socks['muzzle'] = {'pos': [r5(t[0]), r5(t[1]), r5(t[2])], 'bore_r': BORE_R}
    # приклад — на заднем торце коробки (REAR_X −266 мм исходника), по высоте шарнира штатного
    socks['stock'] = {'pos': [0.0, r5(piv['Stock_Stock'][1]), r5(-0.266 - GX)]}
    mm = [r5(v) for v in marks['MagMount']]
    socks['mag'] = {'pos': mm, 'asset_pos': mm}
    # откидные прицельные: прицел на верхней планке — целик ложится вперёд (+89° вокруг +X игры = +Y исходника, драйвер
    # Rear_sight_leaf), мушка назад (−89°)
    when = ['optic_primary', 'top_front']
    folds = {'RearSightLeaf_Steel': {'axis': [1, 0, 0], 'deg': 89.0, 'pivot': [r5(v) for v in piv['RearSightLeaf_Steel']],
                                     'when': when},
             'FrontSightLeaf_Steel': {'axis': [1, 0, 0], 'deg': -89.0,
                                      'pivot': [r5(v) for v in piv['FrontSightLeaf_Steel']], 'when': when}}
    sel = REP['action_game']['selector_deg']
    return {
        'anim': 'rifle',
        'fold_sights': folds,
        # затвор (Bolt_Steel; рама и затвор — один узел, отставания нет) на выстреле уходит назад на 45 мм, рукоятка
        # заряжания неподвижна; последний патрон —
        # затвор встаёт на задержку и стоит сзади до конца перезарядки (hold_open); флажки переводчика с обеих сторон
        # ходят по режиму огня (+X игры = +Y исходника: «ОД» 0°, «2» 30°, «АВ» 60°), спуск на выстреле выжат (−11°)
        'action': {'carrier': 'Bolt_Steel', 'bolt': 'Bolt_Steel', 'travel': REP['action_game']['bolt_travel_m'],
                   'bolt_lag': 0.0, 'unlock': [0.0, 0.0], 'unlock_deg': 0.0, 'hold_open': True,
                   'levers': {n: {'axis': [1, 0, 0], 'deg': sel} for n in ('SelectorL_Steel', 'SelectorR_Steel')},
                   'trigger': {'node': 'Trigger_Steel', 'axis': [1, 0, 0], 'deg': -11.0}},
        'sockets': socks,
    }


def mag(capacity: int, base: dict, item: str) -> dict:
    m = dict(base)
    m['name'] = f'Магазин ИЗЛОМ-45 .45 на {capacity}'
    m['mag'] = dict(base['mag'])
    m['mag'].update({'look': 'asset', 'asset': ASSET + item, 'asset_detail': ASSET + item})
    # на 30 в руках — своей моделью на метке MagAsset вьюмодели (клипы те же, что у штатного на 13)
    if capacity == 30:
        m['mag']['viewmodel_set'] = 'mag30'
    m['model'] = ASSET + item
    return m


def main():
    d = json.loads(WEAPONS.read_text(encoding='utf-8'))
    d['models']['smg03'] = model()
    w = d['weapons']['wpn_smg_03']
    w['name'] = 'ИЗЛОМ-45'
    w['code'] = 'ИЗЛОМ-45'
    w['desc'] = ('Пистолет-пулемёт .45 ACP с отводом отдачи вниз: очередь держится на цели. Планки Picatinny сверху, снизу '
                 'и по бокам переднего блока, откидные прицельные, складной вправо приклад, переводчик «ОД — 2 — АВ», '
                 'затворная задержка после последнего патрона.')
    ww = w['weapon']
    ww['model'] = 'smg03'
    ww['scale'] = 1.0
    ww['length'] = round(REP['size_game_m'][2], 3)
    # темп — около 1200 выстр./мин, как у прототипа: магазин на 13 уходит за две трети секунды
    ww['stats']['rpm'] = 1200
    ww['fire_modes'] = ['auto', 'burst', 'semi']
    ww['mounts'] = {'optic_primary': 'RAIL_TOP', 'top_front': 'RAIL_TOP', 'side_left': 'RAIL_SIDE',
                    'side_right': 'RAIL_SIDE', 'underbarrel': 'RAIL_BOTTOM', 'muzzle': 'THREAD_45', 'stock': 'STOCK_SMG'}
    ww['asset'] = ASSET + 'smg03.gltf'
    ww['asset_kind'] = 'static'
    ww['viewmodel'] = dict(VIEWMODEL)
    d['magazines']['mag_45_vector13'] = mag(13, d['magazines']['mag_45_vector13'], 'smg03_mag13.gltf')
    d['magazines']['mag_45_vector30'] = mag(30, d['magazines']['mag_45_vector30'], 'smg03_mag30.gltf')
    WEAPONS.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    # хват рук: правая — как у винтовок (рукоять в начале осей), левая — под передним блоком перед шахтой магазина,
    # ниже нижней планки (как у ГРАНЬ-15 относительно планки цевья)
    b = REP['rails_game']['RailBottom']
    lz = r5(0.5 * (b['z'][0][0] + b['z'][0][1]) - 0.026)
    ly = r5(b['line_xy'][1] - 0.022)
    g = GRIPS.read_text(encoding='utf-8')
    # фонарь снизу: ладонь — за его креплением, но перед шахтой магазина (передний блок короткий: 0.105, как у винтовок,
    # увёл бы ладонь на магазин)
    entry = ('  "smg03": {\n\t"underbarrel_clearance": 0.06,\n'
             '\t"right": {"pos": [-0.032, -0.026, -0.085], "fingers": [0, 0, 1], "thumb": [0, 1, 0], "curl": [5, 85, 55]},\n'
             f'\t"left": {{"pos": [0.100, {ly:.3f}, {lz:.3f}], "fingers": [-1, 0, 0], "thumb": [0, 0, 1], "curl": [5, 85, 55]}}\n  }},\n')
    if '"smg03"' not in g:
        g = g.replace('  "shotgun": {', entry + '  "shotgun": {', 1)
        GRIPS.write_text(g, encoding='utf-8', newline='\n')
    print('SMG03_DATA', json.dumps(d['models']['smg03']['sockets'], ensure_ascii=False))
    print('SMG03_DATA length', ww['length'], 'left grip', ly, lz)


main()
