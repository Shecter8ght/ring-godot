"""Мосин 1891/30 ПУ в данные игры: модель (затвор, дуло, встроенный ПУ), ствол, пресет, хват рук — из отчёта экспорта
(assets/models/weapons/mosin_pu/mosin_pu.json, game_export.py).

python -X utf8 tools/mosin_pu/game_data.py
Пишет в data/weapons.json (models.mosin_pu, weapons.wpn_sr_03, presets.MOSIN_PU_BASE) и data/weapon_grips.json
(mosin_pu); формат weapons.json не меняется (json с отступом 1, как у файла). Повторный запуск перезаписывает те же ключи.
Торговец — tools/gen_trader_catalogs.py (каталог «Армейское»), цена покупки — Balance.TRADER_BUY_PRICES.

Магазин у Мосина постоянный на 5 патронов (internal_mag, как у помпового ружья): снаряжается из патронов 7.62×54R
рюкзака целиком за перезарядку (обойма — сама модель mosin_pu_clip.glb, как отдельный предмет пока не заведена).
ПУ — часть ассета: встроенная оптика 3,5× (integral.zoom), окуляр — метка ScopeEye, своя сетка — mosin_pu_reticle.png
(tools/mosin_pu/reticle.py). Затвор — продольно-скользящий (action.kind = "bolt", CameraRig._tick_bolt_action).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REP = json.loads((ROOT / 'assets/models/weapons/mosin_pu/mosin_pu.json').read_text(encoding='utf-8'))
WEAPONS = ROOT / 'data/weapons.json'
GRIPS = ROOT / 'data/weapon_grips.json'
ASSET = 'res://assets/models/weapons/mosin_pu/'
GRIP_MM = REP['grip_origin_rifle_mm']        # начало осей игры — середина шейки ложи, в осях винтовки, мм


def r5(v) -> float:
    return round(float(v), 5)


def rifle_to_game(p_mm) -> list:
    """Точка в осях винтовки (мм: дуло +X, верх +Z, правая сторона −Y) → оси игры (м: дуло +Z, верх +Y, правая −X)."""
    return [r5((p_mm[1] - GRIP_MM[1]) / 1000), r5((p_mm[2] - GRIP_MM[2]) / 1000), r5((p_mm[0] - GRIP_MM[0]) / 1000)]


def model() -> dict:
    m = REP['markers_game_m']
    rig = REP['pivots_game_m']
    # шар рукояти затвора (build_rifle._bolt_handle: центр −89,5 + HANDLE_DX, −30, −48 мм) — сюда правая кисть
    # переходит на цикле затвора
    knob = rifle_to_game((-89.5 + 4.5, -30.0, -48.0))
    return {
        'anim': 'bolt',
        'action': {
            'kind': 'bolt', 'carrier': 'Bolt', 'bolt': 'Bolt_Rotor', 'cocking': 'Bolt_Cocking',
            'interrupter': 'Interrupter',
            # ход затвора до упора 110 мм, рукоять вверх на 90° (в осях игры — вокруг +Z на −90°), взвод курка 9,5 мм,
            # отсечка-отражатель выходит на 2,8 мм после 56,4 мм хода (mosin_pu.json, rig)
            'travel': 0.110, 'turn_deg': -90.0, 'cock': 0.0095, 'interrupter_in': 0.0028, 'interrupter_from': 0.0564,
            # к шару, вверх, назад, вперёд, вниз, на шейку — секунды; звук затвора — через 0,35 с после выстрела
            'cycle_sec': [0.14, 0.12, 0.16, 0.15, 0.12, 0.14], 'knob': knob, 'hand_follow': 0.35,
        },
        'sockets': {'muzzle': {'pos': [r5(v) for v in m['Muzzle']], 'bore_r': 0.00381}},
        'pivots': {k: [r5(v) for v in rig[k]] for k in ('Bolt', 'Trigger', 'RearSight_Leaf')},
    }


WEAPON = {
    'name': 'Мосин 1891/30 ПУ', 'cat': 'weapon', 'size': [5, 2], 'value': 55000, 'stack': 1, 'weight': 4.5, 'tier': 2,
    'rarity': 'uncommon', 'tags': ['MILITARY', 'SCAV', 'PRECISION'], 'code': '91/30 ПУ',
    'desc': 'Снайперская трёхлинейка с прицелом ПУ 3,5× на боковом кронштейне: 7.62×54R, постоянный магазин на пять '
            'патронов, продольно-скользящий затвор. Старая, тяжёлая и точная; ложа и металл видели не одну войну.',
    'weapon': {
        'slot': 'primary', 'class': 'SNIPER', 'caliber': '762x54r', 'model': 'mosin_pu', 'scale': 1.0,
        'length': 1.232,
        'stats': {'spread': 1.5, 'ads_spread': 0.06, 'ads_fov': 40, 'kick': 0.075, 'kick_h': 0.016, 'kick_bias': 0.1,
                  'recover': 0.7, 'shake': 0.3, 'ergo': 30, 'rpm': 35, 'auto': False, 'reload': 3.4, 'range': 190,
                  'noise': 120, 'reliability': 0.99, 'wear': 0.02},
        'mounts': {}, 'internal_mag': 5,
        'sound': 'shot_bolt', 'reload_sound': 'reload_rifle', 'cycle_sound': 'bolt',
        'integral': {'zoom': 3.5},
        'asset': ASSET + 'mosin_pu.glb', 'asset_kind': 'static',
        # глаз в прицеле — на выносе выходного зрачка ПУ (72 мм) за окуляром
        'viewmodel': {'ads_z': 0.12, 'scope': {'ocular_r': r5(REP['ocular_r_m']), 'eye_relief': 0.072,
                                              'reticle': ASSET + 'mosin_pu_reticle.png'}},
    },
    'flavor': 'Пять патронов, один выдох и долгий ход затвора: этой винтовке не нужно спешить.',
}
PRESET = {'weapon': 'wpn_sr_03', 'mods': {}, 'ammo': [['ammo_76254_std', 1]], 'dur': [45, 90], 'sight': 'primary'}


def main():
    d = json.loads(WEAPONS.read_text(encoding='utf-8'))
    d['models']['mosin_pu'] = model()
    d['weapons']['wpn_sr_03'] = WEAPON
    d['presets']['MOSIN_PU_BASE'] = PRESET
    WEAPONS.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    # хват рук: правая — на шейке ложи (начало осей), как у болтовки; левая — под цевьём перед магазином
    g = GRIPS.read_text(encoding='utf-8')
    entry = ('  "mosin_pu": {\n\t"underbarrel_clearance": 0.105,\n'
             '\t"right": {"pos": [-0.032, -0.012, -0.100], "fingers": [0, 0.23, 1], "thumb": [0, 1, -0.23], "curl": [5, 85, 55]},\n'
             '\t"left": {"pos": [0.105, 0.012, 0.310], "fingers": [-1, 0, 0], "thumb": [0, 0, 1], "curl": [5, 85, 55]}\n  },\n')
    if '"mosin_pu"' not in g:
        g = g.replace('  "shotgun": {', entry + '  "shotgun": {', 1)
        GRIPS.write_text(g, encoding='utf-8', newline='\n')
    print('MOSIN_DATA model', json.dumps(d['models']['mosin_pu'], ensure_ascii=False))


main()
