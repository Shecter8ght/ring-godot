"""ПМ v11: запечённые карты → игровые PNG (python -X utf8 tools/pm_v11_pack_maps.py).

Источник — _asset_src/pm_game/maps/<состояние>/<Атлас>_<канал>.png (tools: _asset_src/pm_game/work/bake_state.py).
Игра (WeaponCondition._apply_state_maps) ищет <state_maps>_<Поверхность>_<состояние>_albedo/normal/orm.png:
ORM — R: AO игровой сетки (одна на все состояния), G: шероховатость, B: металл.
  Steel, Grip — 100 / 60 / 20 (100 ещё и встраивается в pm.glb экспортом);
  Magazine, Ammo, Suppressor — одно состояние 60 (решение владельца 2026-10-14), имя с «60».
"""
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / '_asset_src/pm_game/maps'
OUT = ROOT / 'assets/models/weapons/pm/states'
OUT.mkdir(parents=True, exist_ok=True)


def load(path, mode):
    return np.asarray(Image.open(path).convert(mode))


def pack(atlas, state, src, ao_dir):
    color = Image.open(src / f'{atlas}_color.png').convert('RGB')
    color.save(OUT / f'pm_{atlas}_{state}_albedo.png', optimize=True)
    normal = Image.open(src / f'{atlas}_normal.png')
    if normal.mode not in ('RGB', 'RGBA'):
        normal = normal.convert('RGB')
    normal.convert('RGB').save(OUT / f'pm_{atlas}_{state}_normal.png', optimize=True)
    rough = load(src / f'{atlas}_rough.png', 'L')
    metal = load(src / f'{atlas}_metal.png', 'L')
    ao_path = ao_dir / f'{atlas}_ao.png'
    ao = load(ao_path, 'L') if ao_path.exists() else np.full_like(rough, 255)
    if ao.shape != rough.shape:
        ao = np.asarray(Image.fromarray(ao).resize(rough.shape[::-1], Image.LANCZOS))
    orm = np.dstack([ao, rough, metal]).astype(np.uint8)
    Image.fromarray(orm, 'RGB').save(OUT / f'pm_{atlas}_{state}_orm.png', optimize=True)
    print('PACKED', atlas, state, color.size)


for state in ('100', '60', '20'):
    for atlas in ('Steel', 'Grip'):
        pack(atlas, state, MAPS / state, MAPS / '100_ao')
pack('Magazine', '60', MAPS / 'mag', MAPS / 'mag')
pack('Ammo', '60', MAPS / 'ammo', MAPS / 'ammo')
pack('Suppressor', '60', MAPS / 'supp', MAPS / 'supp')
print('PM_MAPS_DONE', OUT)
