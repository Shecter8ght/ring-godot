"""«Осока» (ПЗРК) в данные игры — из отчёта экспорта (assets/models/weapons/osoka/osoka.json, game_export.py); как у
ИЗЛОМ-45 (tools/smg03/game_data.py).

python -X utf8 tools/osoka/game_data.py
Пишет в data/weapons.json: calibers.zr36, ammo.msl_zr36 (ракета ЗР-36 в транспортно-пусковой трубе — «патрон»:
R ставит пусковой механизм на новую трубу), models.osoka (метки, рычаг, лампа индикатора, что прячется после пуска),
weapons.wpn_mp_01; в data/weapon_grips.json — хват osoka (правая на рукояти, левая под источником питания).
Продаётся у Михалыча (владелец 2026-11-06: «пока что её можно сделать доступной для покупки») — каталог 5,
tools/gen_trader_catalogs.py; цены — Balance.TRADER_BUY_PRICES. Повторный запуск перезаписывает те же ключи.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REP = json.loads((ROOT / 'assets/models/weapons/osoka/osoka.json').read_text(encoding='utf-8'))
WEAPONS = ROOT / 'data/weapons.json'
GRIPS = ROOT / 'data/weapon_grips.json'
ASSET = 'res://assets/models/weapons/osoka/'
# глаз в прицеливании — в 8 см за диоптром целика (метка SightRear; вынос ads_z — от хвата до глаза)
ADS_Z = round(-REP['marks_game_m']['SightRear'][2] + 0.08, 3)
# не вскинутый к глазу комплекс лежит на плече: хват правее, ниже и ближе, чем у винтовки (Balance.FPS_HIP_POSE)
HIP_POSE = [0.12, -0.27, -0.2]


def r3(v) -> float:
    return round(float(v), 3)


def model() -> dict:
    m = REP['marks_game_m']
    return {
        'anim': 'rifle',
        # спуск на выстреле выжат (+10° вокруг +X игры, part_rig.TRIGGER_DEG); «рама» — неподвижный корпус: хода нет
        'action': {'carrier': 'Body_Launcher', 'bolt': 'Body_Launcher', 'travel': 0.0, 'bolt_lag': 0.0, 'unlock': [0.0, 0.0],
                   'unlock_deg': 0.0, 'trigger': {'node': 'Trigger_Launcher', 'axis': [1, 0, 0], 'deg': 10.0}},
        'sockets': {'muzzle': {'pos': [r3(v) for v in m['Muzzle']], 'bore_r': 0.036}},
        # ПЗРК в руках (CameraRig._tick_osoka_view): передняя крышка снята; задняя и нос ракеты — пока в трубе ракета;
        # рычаг «ИСХОДНОЕ» → «НАКОЛ» (+18°), пока головка включена; колпачок светового индикатора светится при захвате
        # вскинут к глазу — целик и лампа у самого глаза прячутся (видно кольцо мушки с точкой)
        'manpads': {'hidden': ['FrontCap_Tube'], 'loaded': ['RearCap_Tube', 'MissileNose_Missile'],
                    'hide_ads': ['RearSight_Launcher', 'SightLamp_Launcher'],
                    'lever': 'Lever_Launcher', 'lever_turn': {'axis': [1, 0, 0], 'deg': 18.0},
                    'lamp': 'SightLamp_Launcher', 'missile': ASSET + 'osoka_missile.gltf'},
    }


def main():
    d = json.loads(WEAPONS.read_text(encoding='utf-8'))
    d['calibers']['zr36'] = {'name': 'Ракета ЗР-36 (ПЗРК)'}
    d['ammo']['msl_zr36'] = {
        'name': 'Ракета ЗР-36 в трубе', 'cat': 'ammo', 'cells': 6, 'size': [6, 1], 'value': 300000, 'stack': 1,
        'weight': 12.5, 'tier': 5, 'rarity': 'rare', 'tags': [], 'short': 'ЗР-36',
        'desc': ('Зенитная ракета с тепловой головкой самонаведения в транспортно-пусковой трубе ТП-36 — выстрел '
                 'к ПЗРК «Осока». R с комплексом в руках — пусковой механизм ставят на новую трубу.'),
        'ammo': {'caliber': 'zr36', 'effect': 'missile', 'damage': 0, 'pen': 0, 'armor_dmg': 0, 'pellets': 1,
                 'velocity': 28},
    }
    d['models']['osoka'] = model()
    d['weapons']['wpn_mp_01'] = {
        'name': 'ПЗРК «Осока»', 'cat': 'weapon', 'size': [6, 2], 'value': 1200000, 'stack': 1, 'weight': 17.3,
        'tier': 5, 'rarity': 'rare', 'tags': [], 'code': 'ТП-36 / ПМ-52', 'short': 'ОСОКА',
        'desc': ('Переносной зенитный ракетный комплекс: труба ТП-36 с ракетой ЗР-36, пусковой механизм ПМ-52 с '
                 'источником питания. Тепловая головка самонаведения: вскинь к прицелу (ПКМ) — рычаг на «НАКОЛ», '
                 'головка готовится; держи цель в кольце мушки — писк учащается, через пару секунд захват: ровный '
                 'писк, лампа на целике, метка зеленеет. ЛКМ — пуск, дальше ракета летит на цель сама. Без захвата '
                 'пуска нет. Цели — вертолёты и горящие осветительные ракеты. R — новая труба с ракетой.'),
        'weapon': {
            'slot': 'primary', 'class': 'SPECIAL', 'caliber': 'zr36', 'model': 'osoka', 'scale': 1.0,
            'length': r3(REP['size_game_m'][2]), 'internal_mag': 1, 'manpads': True,
            'stats': {'spread': 0.0, 'ads_spread': 0.0, 'ads_fov': 66, 'kick': 0.006, 'kick_h': 0.002,
                      'kick_bias': 0.0, 'recover': 0.6, 'shake': 0.3, 'ergo': 22, 'rpm': 20, 'auto': False,
                      'reload': 9.0, 'range': 5500, 'noise': 140, 'reliability': 1.0, 'wear': 0.0},
            'mounts': {}, 'sound': '', 'reload_sound': 'reload_rifle', 'cycle_sound': '',
            'asset': ASSET + 'osoka.gltf', 'asset_kind': 'static',
            'viewmodel': {'ads_z': ADS_Z, 'hip_pose': HIP_POSE},
            'carry': False,
        },
        'flavor': 'Тяжёлая, неудобная и честная: пищит — значит видит.',
    }
    WEAPONS.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    # хват: правая — на рукояти ПМ-52 (начало осей — середина хвата, как у винтовок); левая — снизу под источником
    # питания перед механизмом (цилиндр Ø65 вниз-вперёд на 8°): запястье слева, пальцы обхватывают его справа
    pw = REP['pivots_game_m']['Power_Tube']
    ly = round(pw[1] - 0.033 - 0.022, 3)
    lz = round(pw[2] + 0.085, 3)          # начало узла — у шара-гнезда; ладонь — на середине цилиндра
    entry = ('  "osoka": {\n'
             '\t"right": {"pos": [-0.032, -0.026, -0.085], "fingers": [0, 0, 1], "thumb": [0, 1, 0], "curl": [5, 85, 55]},\n'
             f'\t"left": {{"pos": [0.100, {ly:.3f}, {lz:.3f}], "fingers": [-1, 0, 0], "thumb": [0, 0, 1], "curl": [5, 85, 55]}}\n  }},\n')
    g = GRIPS.read_text(encoding='utf-8')
    if '"osoka"' not in g:
        g = g.replace('  "shotgun": {', entry + '  "shotgun": {', 1)
        GRIPS.write_text(g, encoding='utf-8', newline='\n')
    print('OSOKA_DATA ads_z', ADS_Z, 'left grip', ly, lz, 'length', d['weapons']['wpn_mp_01']['weapon']['length'])


main()
