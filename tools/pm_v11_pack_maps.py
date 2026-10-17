"""ПМ v11: запечённые карты → игровые PNG (python -X utf8 tools/pm_v11_pack_maps.py).

Источник — _asset_src/pm_game/maps/<состояние>/<Атлас>_<канал>.png (tools: _asset_src/pm_game/work/bake_state.py).
Игра (WeaponCondition._apply_state_maps) ищет <state_maps>_<Поверхность>_<состояние>_albedo/normal/orm.png:
ORM — R: AO игровой сетки (одна на все состояния), G: шероховатость, B: металл.
  Steel, Grip — 100 / 60 / 20 (100 ещё и встраивается в pm.glb экспортом);
  Magazine, Ammo, Suppressor — одно состояние 60 (решение владельца 2026-10-14), имя с «60».
Аргумент wear — только маска процедурного износа (шейдер weapon_wear): maps/20_wear/<Атлас>_{edge,cavity,hand}.png
(tools/pm_v11_bake.py -- 20 --channels edge,cavity,hand --tag _wear) → рядом с картами pm.glb
pm_pm_<Атлас>_100_wear.png: R — выпуклые кромки, G — углубления, B — места хвата (Non-Color).
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter

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


WEAR_SIZE = {'Steel': 2048, 'Grip': 2048}


def wear_channel(path, size, blur):
    """Сырой канал запекания → 0..1: шум лучей AO сглажен, уровни — по заполненной части атласа."""
    im = Image.open(path).convert('L')
    if blur > 0:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    im = im.resize((size, size), Image.LANCZOS)
    a = np.asarray(im, np.float32) / 255.0
    lit = a[a > 0.02]
    hi = np.percentile(lit, 99.0) if lit.size else 1.0
    return np.clip(a / max(hi, 1e-3), 0.0, 1.0)


def pack_wear(atlas):
    src = MAPS / '20_wear'
    size = WEAR_SIZE[atlas]
    # кромки: AO изнутри даёт на ребре ~половину затенения — растянуть и чуть сжать к самой кромке
    edge = wear_channel(src / f'{atlas}_edge.png', size, 1.2) ** 1.2
    cavity = wear_channel(src / f'{atlas}_cavity.png', size, 3.0)
    # защищённые места между деталями — AO игровой сетки (то же, что R в ORM): открытое 1 → 0
    ao = Image.open(MAPS / '100_ao' / f'{atlas}_ao.png').convert('L').filter(ImageFilter.GaussianBlur(2.0)).resize((size, size), Image.LANCZOS)
    ao = np.asarray(ao, np.float32) / 255.0
    shelter = np.clip((0.9 - ao) / 0.55, 0.0, 1.0)
    # фон атласа (AO = 0, вне островов) — не «укрытое место»: иначе на дальних mip-уровнях грязь по швам UV
    shelter[ao < 0.03] = 0.0
    cavity = np.maximum(cavity, shelter)
    hand = wear_channel(src / f'{atlas}_hand.png', size, 2.0)
    rgb = np.dstack([edge, cavity, hand])
    out = ROOT / f'assets/models/weapons/pm/pm_pm_{atlas}_100_wear.png'
    Image.fromarray((rgb * 255.0 + 0.5).astype(np.uint8), 'RGB').save(out, optimize=True)
    print('WEAR', atlas, size, out.name, 'edge', round(float(edge.mean()), 3), 'cavity', round(float(cavity.mean()), 3),
          'hand', round(float(hand.mean()), 3))


if 'wear' in sys.argv[1:]:
    for atlas in WEAR_SIZE:
        pack_wear(atlas)
    print('PM_WEAR_DONE')
    sys.exit(0)

for state in ('100', '60', '20'):
    for atlas in ('Steel', 'Grip'):
        pack(atlas, state, MAPS / state, MAPS / '100_ao')
pack('Magazine', '60', MAPS / 'mag', MAPS / 'mag')
pack('Ammo', '60', MAPS / 'ammo', MAPS / 'ammo')
pack('Suppressor', '60', MAPS / 'supp', MAPS / 'supp')
print('PM_MAPS_DONE', OUT)
