"""AR-15 «ГРАНЬ-15» в данные игры: модель с планками Picatinny, ствол, магазин, пресет, хват рук — из отчёта экспорта
(assets/models/weapons/ar15/ar15.json, game_export.py).

python -X utf8 tools/ar15/game_data.py
Пишет в data/weapons.json (models.ar15, weapons.wpn_ar_09, magazines.mag_556_30_gran, presets.GRAN15_BASE,
attachments.muzzle_supp_gran_01 — глушитель, tools/ar15/supp_game.py) и
data/weapon_grips.json (ar15); формат weapons.json не меняется (json с отступом 1, как у файла). Повторный запуск
перезаписывает те же ключи.
Планки (weapon_build.gd): обвес встаёт с шагом SLOT_M = 20 мм от начала rail_z, серединой зажима (clamp_m, по умолчанию
30 мм — полпоследнего 15 мм от начала). Начало планки ставится так, чтобы шаг игры попадал в настоящие пазы Picatinny
(у планок шаг 10,01 мм — каждый второй паз): rail_z[0] = середина паза − 15 мм, первый паз — тот, у которого зажим не
свисает с края планки. Планки сверху ограничены свободными участками: на ресивере — перед основанием целика, на цевье —
до основания мушки (откидные прицельные стоят на планках и занимают их). Все пазы — в отчёте экспорта (rails_game).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REP = json.loads((ROOT / 'assets/models/weapons/ar15/ar15.json').read_text(encoding='utf-8'))
WEAPONS = ROOT / 'data/weapons.json'
GRIPS = ROOT / 'data/weapon_grips.json'
CLAMP_HALF = 0.015                      # половина зажима обвеса по умолчанию (weapon_build.gd: clamp_m 0,03)
ASSET = 'res://assets/models/weapons/ar15/'
# свободные участки верхней планки, оси игры z (м от хвата): ресивер — от переднего края основания целика до конца
# планки ресивера; цевьё — от начала планки цевья до основания мушки. Края прицельных — из исходника (Rear_sight_base
# x −0,126; Front_sight_base x 0,252) минус хват
GX = REP['grip_source_m'][0]
# глаз в прицеливании — над гребнем приклада, ~12 см за целиком (целик стоит над рукоятью, z 0,0035): при 17 см глаз
# уходил за затыльник, диоптр был мелким, а рукоятка заряжания и трубка приклада закрывали низ кадра
ADS_Z = 0.12
FREE_TOP = {'optic_primary': (-0.126 - GX, 0.020 - GX), 'top_front': (0.0263 - GX, 0.252 - GX)}


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
        # боковые планки короткие (30 мм): по слову владельца ставится любой обвес — длиннее планки встаёт
        # посередине и свисает с концов (overhang, WeaponBuild.overhangs)
        socks[point] = {'pos': [r5(r['line_xy'][0]), r5(r['line_xy'][1]), r5(0.5 * (rz[0] + rz[1]))], 'side': True,
                        'rail_z': rz, 'overhang': True}
    b = rg['RailBottom']
    seg = b['z'][0]
    rz = rail(b['slots_z'], seg[0], seg[1])
    socks['underbarrel'] = {'pos': [0.0, r5(b['line_xy'][1]), r5(0.5 * (rz[0] + rz[1]))], 'rail_z': rz}
    m = marks['Muzzle']
    socks['muzzle'] = {'pos': [r5(m[0]), r5(m[1]), r5(m[2])], 'bore_r': 0.0028}
    # приклад — на трубке за гайкой ресивера (Castle_nut x −0,195 исходника), ось трубки — ось ствола
    socks['stock'] = {'pos': [0.0, r5(m[1]), r5(-0.195 - GX)]}
    mm = [r5(v) for v in marks['MagMount']]
    socks['mag'] = {'pos': mm, 'asset_pos': mm}
    act = REP['action_game']
    carrier = -act['charging_handle:BoltCarrier']['move'][2]
    bolt = -act['charging_handle:Bolt']['move'][2]
    # откидные прицельные (weapon_mods.gd: _fold_sights): прицел на верхней планке — целик ложится вперёд (+90° вокруг
    # +X игры = +Y исходника, драйвер Rear_sight_leaf), мушка назад (−90°); диоптр целика — вокруг шарнира целика
    piv = REP['pivots_game_m']
    when = ['optic_primary', 'top_front']
    rear = [r5(v) for v in piv['RearSightLeaf_Handguard']]
    folds = {'RearSightLeaf_Handguard': {'axis': [1, 0, 0], 'deg': 90.0, 'pivot': rear, 'when': when},
             'RearAperture_Handguard': {'axis': [1, 0, 0], 'deg': 90.0, 'pivot': rear, 'when': when},
             'FrontSightLeaf_Handguard': {'axis': [1, 0, 0], 'deg': -90.0,
                                          'pivot': [r5(v) for v in piv['FrontSightLeaf_Handguard']], 'when': when}}
    return {
        'anim': 'rifle',
        'fold_sights': folds,
        # рама уходит на 91 мм, затвор отстаёт на 12,5 мм и проворачивается на 22,5° (драйверы исходника, part_rig.py:
        # свободный ход 3 мм, поворот до 12 мм); рукоятка заряжания на выстреле стоит;
        # пылезащитная шторка: откидывается вокруг своей оси (+Z игры = +X исходника, драйвер Dust_cover_hinge) на 112°
        # — её откидывает рама (CameraRig._tick_cover, Player.dust_cover_open)
        'action': {'carrier': 'BoltCarrier_Steel', 'bolt': 'Bolt_Steel', 'travel': r5(carrier),
                   'bolt_lag': r5(carrier - bolt), 'unlock': [0.003, 0.012],
                   'unlock_deg': act['charging_handle:Bolt']['rot_deg'],
                   'cover': 'DustCover_Receiver', 'cover_deg': act['charging_handle:DustCover']['rot_deg']},
        'sockets': socks,
    }


WEAPON = {
    'name': 'ГРАНЬ-15', 'cat': 'weapon', 'size': [4, 2], 'value': 95000, 'stack': 1, 'weight': 3.0, 'tier': 3,
    'rarity': 'rare', 'tags': ['MILITARY', 'PERIMETER'], 'code': 'ГРАНЬ-15',
    'desc': 'Карабин 5.56 на платформе AR-15 в песочном покрытии: полноразмерные планки Picatinny сверху, снизу и по '
            'бокам цевья, откидные механические прицельные, переводчик «безопасно — одиночный — автомат».',
    'weapon': {
        'slot': 'primary', 'class': 'CARBINE', 'caliber': '556x45', 'model': 'ar15', 'scale': 1.0,
        'stats': {'spread': 1.6, 'ads_spread': 0.3, 'ads_fov': 58, 'kick': 0.017, 'kick_h': 0.009, 'kick_bias': 0.3,
                  'recover': 0.44, 'shake': 0.08, 'ergo': 60, 'rpm': 800, 'auto': True, 'reload': 2.15, 'range': 105,
                  'noise': 80, 'reliability': 0.978, 'wear': 0.02},
        'fire_modes': ['semi', 'auto'],
        'mounts': {'optic_primary': 'RAIL_TOP', 'top_front': 'RAIL_TOP', 'side_left': 'RAIL_SIDE',
                   'side_right': 'RAIL_SIDE', 'underbarrel': 'RAIL_BOTTOM', 'muzzle': 'QD_GRAN15',
                   'stock': 'STOCK_AR'},
        'mag_if': 'MAG_STANAG', 'default_mag': 'mag_556_30_gran', 'sound': 'shot_rifle', 'reload_sound': 'reload_rifle',
        'cycle_sound': '', 'asset': ASSET + 'ar15.gltf', 'asset_kind': 'static', 'viewmodel': {'ads_z': ADS_Z},
    },
    'flavor': 'Знакомая платформа без сюрпризов: планки под любой обвес, а песочное покрытие держит свою историю на кромках.',
}
MAG = {
    'name': 'Магазин «ГРАНЬ» 5.56 на 30 (полимер)', 'cat': 'mag', 'size': [1, 2], 'value': 3000, 'stack': 1,
    'weight': 0.14, 'tier': 2, 'rarity': 'uncommon', 'tags': ['MILITARY', 'PERIMETER'], 'short': '30',
    'mag': {'if': 'MAG_STANAG', 'capacity': 30, 'reload_k': 1, 'ergo': 0, 'reliability': 1, 'look': 'asset',
            'asset': ASSET + 'ar15_mag30.gltf', 'asset_detail': ASSET + 'ar15_mag30.gltf'},
    'flavor': 'Полимерный STANAG с окнами остатка: видно, сколько осталось, не вынимая магазин.',
    'model': ASSET + 'ar15_mag30.gltf',
}
# Глушитель ГРАНЬ (supp_game.py): быстросъёмный — надевается на дульный тормоз и защёлкивается на храповой муфте, поэтому
# у дула ГРАНЬ-15 своё крепление QD_GRAN15 (резьбовые насадки 5.56 сели бы перед тормозом, которого в модели не снять).
# Начало модели — задний торец: на тормозе он на 49,7 мм позади среза (part_muzzle: торец 290,3 мм, срез тормоза — 340 мм,
# метка Muzzle); длина 172 мм — срез выстрела на переднем торце. Действие — как у глушителя 5.56 (muzzle_supp_556_01).
SUPP_DIR = 'res://assets/models/attachments/supp_gran/'
SUPP = {
    'name': 'Глушитель «ГРАНЬ» 5.56', 'cat': 'mod', 'size': [2, 1], 'value': 28000, 'stack': 1, 'weight': 0.5, 'tier': 3,
    'rarity': 'rare', 'tags': ['MILITARY', 'PERIMETER'], 'short': 'Глуш. ГРАНЬ',
    'attach': {'type': 'SUPPRESSOR', 'fits': ['QD_GRAN15'], 'look': 'suppressor',
               'model': {'scene': SUPP_DIR + 'supp_gran.glb', 'offset': [0, 0, -0.0497], 'length_m': 0.172},
               'fx': {'noise': 0.35, 'db': -14, 'damage': 0.96, 'suppressed': True, 'ergo': -8, 'kick': 0.88, 'flash': 0},
               'size_m': [0.020, 0.172]},
    'flavor': 'Быстросъёмный: надевается на дульный тормоз ГРАНЬ-15 и защёлкивается на храповой муфте. На другие стволы не встаёт.',
}
PRESET = {'weapon': 'wpn_ar_09', 'mods': {}, 'ammo': [['ammo_556_std', 1]], 'dur': [70, 100], 'sight': 'primary',
          'mag': 'mag_556_30_gran'}


def main():
    d = json.loads(WEAPONS.read_text(encoding='utf-8'))
    d['models']['ar15'] = model()
    w = dict(WEAPON)
    w['weapon'] = dict(WEAPON['weapon'])
    sz = REP['size_game_m']
    w['weapon']['length'] = round(sz[2], 3)
    # wpn_ar_06…08 — псевдонимы старых сохранений (aliases: wpn_ar_06 → ВЕРАС-54), поэтому свой номер — 09
    d['weapons'].pop('wpn_ar_06', None)
    d['weapons']['wpn_ar_09'] = w
    d['magazines']['mag_556_30_gran'] = MAG
    d['presets']['GRAN15_BASE'] = PRESET
    d['attachments']['muzzle_supp_gran_01'] = SUPP
    WEAPONS.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    # хват рук: правая — как у винтовок (рукоять в начале осей), левая — на цевье за его началом, ниже оси ствола
    g = GRIPS.read_text(encoding='utf-8')
    entry = ('  "ar15": {\n\t"underbarrel_clearance": 0.105,\n'
             '\t"right": {"pos": [-0.032, -0.026, -0.085], "fingers": [0, 0, 1], "thumb": [0, 1, 0], "curl": [5, 85, 55]},\n'
             '\t"left": {"pos": [0.100, 0.034, 0.300], "fingers": [-1, 0, 0], "thumb": [0, 0, 1], "curl": [5, 85, 55]}\n  },\n')
    if '"ar15"' not in g:
        g = g.replace('  "shotgun": {', entry + '  "shotgun": {', 1)
        GRIPS.write_text(g, encoding='utf-8', newline='\n')
    print('AR15_DATA', json.dumps(d['models']['ar15']['sockets'], ensure_ascii=False))
    print('AR15_DATA action', d['models']['ar15']['action'], 'length', w['weapon']['length'])


main()
