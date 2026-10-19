"""Магазины ВЕРАС-54 (на 45 и барабан на 60) в игру: общие данные и помощники этапов mags_game_*.py.

Конвейер — как у автомата v13 (tools/veras54_v13: game_lp → game_bake → game_pack → экспорт), но отдельный: каждый магазин —
своя игровая сетка и один атлас 4096 (корпус, подаватель / ключ, патроны), свои карты; файлы автомата не трогаются.
Источник — текстурированные high-poly v01, принятые владельцем 2026-10-19 («можно перегонять в лоу-поле»).
Оси исходников — оси автомата (+X к дулу, +Y влево стрелка, +Z вверх, метры); начало — точка крепления магазина
(в автомате корень магазина стоит в (0,179; 0; −0,037) от начала VERAS54).
"""
from __future__ import annotations

import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = Path('E:/Models Blender/WEAPONS/ВЕРАС-54 — модель и обвесы')
ASSET = ROOT / 'assets/models/weapons/veras54_mags'
ROUND_HI = {'case': 110, 'projectile': 70}      # верхние патроны — видны у губок (как патрон автомата)
ROUND_LO = {'case': 36, 'projectile': 20}       # остальные — внутри корпуса, их не видно ни в одном ракурсе
ROUNDS_HI = 2
ATTACH_IN_VERAS54 = (0.179, 0.0, -0.037)        # где корень магазина стоит в осях автомата (м)

MAGS = {
    'm45': dict(
        title='Магазин 5,45 на 45', item='mag_545_45',
        src=LIB / 'Магазин 45/Актуальное/Magazine45_Loaded_State100_Textured_v01.blend',
        sha='df769b60748dd50953b0f85ed36affa3079759128da0585f261df0ff721f5dca',
        root='Magazine45_Loaded', prefix='Magazine45', atlas='Mag45', size=4096, rounds=45, sharp_deg=40,
        lib_dir=LIB / 'Магазин 45/Игровая версия',
        # игровая деталь (узел) → детали исходника
        parts={'Magazine': ['Magazine45_Body', 'Magazine45_Floorplate', 'Magazine45_Indicator_Channel -1',
                            'Magazine45_Indicator_Channel 1'],
               'MagazineFollower': ['Magazine45_Follower']},
        budget={'Magazine45_Body': 5000, 'Magazine45_Floorplate': 200, 'Magazine45_Indicator_Channel': 80,
                'Magazine45_Follower': 160},
        organic=set(),
        # места хвата (канал B маски износа), как у штатного магазина в конвейере автомата
        hand={'Magazine45_Body': 0.55, 'Magazine45_Floorplate': 0.6},
        world_ratio=0.35),
    'd60': dict(
        title='Барабан 5,45 на 60', item='mag_545_60',
        src=LIB / 'Барабан 60/Актуальное/Drum60_Loaded_State100_Textured_v01.blend',
        sha='ae769714395314f8423ade2bf23ca6359efe960af241a0c7f0e3974c5055db4f',
        root='Drum60_Loaded', prefix='Drum60', atlas='Drum60', size=4096, rounds=8, sharp_deg=60,
        lib_dir=LIB / 'Барабан 60/Игровая версия',
        parts={'Magazine': ['Drum60_Body', 'Drum60 • front cover rim', 'Drum60 • winding hub', 'Drum60 • lock button'],
               'DrumKey': ['Drum60 • folding key']},
        budget={'Drum60_Body': 5000, 'Drum60 • front cover rim': 400, 'Drum60 • winding hub': 240,
                'Drum60 • lock button': 40, 'Drum60 • folding key': 300},
        organic=set(),
        hand={'Drum60_Body': 0.55, 'Drum60 • folding key': 1.0, 'Drum60 • winding hub': 0.7, 'Drum60 • lock button': 0.9,
              'Drum60 • front cover rim': 0.5},
        world_ratio=0.35),
}


def work(mid: str) -> Path:
    p = ROOT / '_asset_src/veras54_game_mags' / mid
    p.mkdir(parents=True, exist_ok=True)
    return p


def base_name(n: str) -> str:
    """Имя детали без стороны и номера в конце («…_Indicator_Channel -1» → «…_Indicator_Channel»)."""
    parts = n.split(' ')
    while len(parts) > 1 and re.fullmatch(r'[+-]?\d+(\.\d+)?', parts[-1]):
        parts.pop()
    return ' '.join(parts)


def tag(mid: str) -> str:
    return f'veras54_{MAGS[mid]["atlas"]}_100'


def matname(mid: str) -> str:
    return f'GAME • {MAGS[mid]["atlas"]} • 100'


# Ось барабана и ступицы (для узла ключа): как в d60_build.py / mags_look.py
_a = math.radians(-161.0)
_tow = (-math.sin(_a), math.cos(_a))
DRUM_TILT = math.atan2(_tow[0], -_tow[1])
_P = (623.4 + math.cos(_a) * 450.9, 34.79 + math.sin(_a) * 450.9)
DRUM_C_MM = (_P[0] + _tow[0] * 29.0 - 179.0, 0.0, _P[1] + _tow[1] * 29.0 + 37.0)
DRUM_AXIS = (math.cos(DRUM_TILT), 0.0, math.sin(DRUM_TILT))
HUB_FACE_MM = tuple(DRUM_C_MM[i] + DRUM_AXIS[i] * 32.0 for i in range(3))   # центр передней крышки (ось ступицы)
