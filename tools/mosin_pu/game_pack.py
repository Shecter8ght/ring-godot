"""Мосин ПУ: запечённые карты (game_bake.py) → игровые PNG.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/mosin_pu/game_pack.py -- [fp|detail]
Источник — _asset_src/mosin_pu_game/maps/raw/<Атлас>_{color,normal,mrh,ecm,ao}.png (mrh: металл, шероховатость,
хват; ecm: кромки, углубления, покрытие).
→ _asset_src/mosin_pu_game/maps/game/<Атлас>_20_{albedo,normal,orm}.png (встраиваются в GLB экспортом; патрон —
  Ammo_{albedo,normal,orm}); ORM — R: AO игровой сетки, G: шероховатость, B: металл.
→ assets/models/weapons/mosin_pu/mosin_pu_<Атлас>_20_wear.png — маска износа шейдера рядом с картами, которые Godot
  извлечёт из mosin_pu.glb (mosin_pu_<Атлас>_20_albedo.png): R — выпуклые кромки, G — углубления и укрытые места,
  B — места хвата (Non-Color, 2048; формат — src/combat/weapon_wear.gdshader).
Поля островов добираются «push-pull» по пирамиде (среднее по запечённому) до краёв атласа: дальние mip-уровни
не тянут чёрный фон в швы. Читается и пишется через Blender (16-битные нормали без потерь до записи).
"""
from __future__ import annotations

from pathlib import Path

import sys

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
VARIANT = (sys.argv[sys.argv.index('--') + 1:] + ['fp'])[0] if '--' in sys.argv else 'fp'
RAW = ROOT / '_asset_src/mosin_pu_game' / VARIANT / 'maps/raw'
GAME = ROOT / '_asset_src/mosin_pu_game' / VARIANT / 'maps/game'
# маска износа — рядом с картами, которые Godot извлечёт из GLB варианта: <имя GLB>_<карта>
PREFIX = 'mosin_pu' if VARIANT == 'fp' else 'mosin_pu_detail'
ASSET = ROOT / 'assets/models/weapons/mosin_pu' if VARIANT == 'fp' else Path('E:/Models Blender/WEAPONS/Мосин — винтовка и узлы/models/06_Игровая/detail')
GAME.mkdir(parents=True, exist_ok=True)
ASSET.mkdir(parents=True, exist_ok=True)
ATLASES = {'Wood': '20', 'Steel': '20', 'Optic': '20', 'Ammo': ''}
WEAR_SIZE = 2048
log = lambda *a: print('MOSIN_PACK', *a, flush=True)


def load(name: str) -> np.ndarray | None:
    path = RAW / f'{name}.png'
    if not path.exists():
        return None
    im = bpy.data.images.load(str(path))
    im.colorspace_settings.name = 'Non-Color'          # сырые значения файла, без преобразований
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)


def save(arr: np.ndarray, path: Path, srgb: bool) -> None:
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = arr[..., :3] if arr.shape[2] >= 3 else arr[..., :1]
    im = bpy.data.images.new(path.stem, w, h, alpha=False, float_buffer=False)
    im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    im.pixels.foreach_set(np.clip(rgba, 0, 1).ravel())
    im.filepath_raw = str(path)
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
    log('saved', path.name, w)


def pushpull(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Пустые пиксели — из пирамиды средних по запечённому; запечённые не меняются."""
    c = img * mask[..., None]
    wgt = mask.astype(np.float32)
    levels = []
    while c.shape[0] > 1:
        levels.append((c, wgt))
        h, w = c.shape[0] // 2, c.shape[1] // 2
        c = c[:h * 2, :w * 2].reshape(h, 2, w, 2, -1).sum(axis=(1, 3))
        wgt = wgt[:h * 2, :w * 2].reshape(h, 2, w, 2).sum(axis=(1, 3))
    fill = c / np.maximum(wgt, 1e-6)[..., None]
    for c_l, w_l in reversed(levels):
        up = np.repeat(np.repeat(fill, 2, axis=0), 2, axis=1)[:c_l.shape[0], :c_l.shape[1]]
        have = w_l > 1e-6
        fill = np.where(have[..., None], c_l / np.maximum(w_l, 1e-6)[..., None], up)
    return np.where(mask[..., None], img, fill)


def blur(a: np.ndarray, r: float) -> np.ndarray:
    """≈ гаусс: три прохода прямоугольника по обеим осям (r — радиус в пикселях)."""
    k = max(1, int(round(r)))
    out = a.astype(np.float32)
    for _ in range(3):
        for ax in (0, 1):
            pad = [(0, 0)] * out.ndim
            pad[ax] = (k, k)
            p = np.pad(out, pad, mode='edge')
            cs = np.cumsum(p, axis=ax, dtype=np.float64)
            cs = np.concatenate([np.zeros_like(np.take(cs, [0], axis=ax)), cs], axis=ax)
            n = out.shape[ax]
            hi = np.take(cs, np.arange(2 * k + 1, 2 * k + 1 + n), axis=ax)
            lo = np.take(cs, np.arange(0, n), axis=ax)
            out = ((hi - lo) / (2 * k + 1)).astype(np.float32)
    return out


def half(a: np.ndarray, size: int) -> np.ndarray:
    while a.shape[0] > size:
        h, w = a.shape[0] // 2, a.shape[1] // 2
        a = a[:h * 2, :w * 2].reshape(h, 2, w, 2, *a.shape[2:]).mean(axis=(1, 3))
    return a


def level(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """0..1 по заполненной части атласа (99-й перцентиль запечённого = 1)."""
    lit = a[mask & (a > 0.02)]
    hi = float(np.percentile(lit, 99.0)) if lit.size else 1.0
    return np.clip(a / max(hi, 1e-3), 0.0, 1.0)


for atlas, state in ATLASES.items():
    ecm = load(f'{atlas}_ecm')
    if ecm is None:
        log('skip', atlas, '(нет запекания)')
        continue
    mask = ecm[..., 2] > 0.5                       # B прохода ecm — покрытие (где запечено, с полями запекания)
    mrh = load(f'{atlas}_mrh')
    tag = f'{atlas}_{state}' if state else atlas
    color = pushpull(load(f'{atlas}_color')[..., :3], mask)
    save(color, GAME / f'{tag}_albedo.png', True)
    nrm = load(f'{atlas}_normal')[..., :3]
    nrm = pushpull(nrm, mask)
    v = nrm * 2 - 1
    v /= np.maximum(np.linalg.norm(v, axis=2, keepdims=True), 1e-6)
    save(v * 0.5 + 0.5, GAME / f'{tag}_normal.png', False)
    rough = pushpull(mrh[..., 1:2], mask)[..., 0]
    metal = pushpull(mrh[..., 0:1], mask)[..., 0]
    ao_raw = load(f'{atlas}_ao')
    ao = pushpull(ao_raw[..., :1], mask)[..., 0] if ao_raw is not None else np.ones_like(rough)
    save(np.dstack([ao, rough, metal]), GAME / f'{tag}_orm.png', False)
    log(atlas, 'coverage', round(float(mask.mean()), 3), 'rough', round(float(rough[mask].mean()), 3),
        'metal', round(float(metal[mask].mean()), 3), 'ao', round(float(ao[mask].mean()), 3))
    if not state:
        continue
    # маска износа шейдера: каналы сглажены (шум лучей AO), уровни — по запечённому
    # сначала поля островов (иначе размытие тянет чёрный фон в края островов), потом сглаживание
    ec = pushpull(np.dstack([ecm[..., 0], ecm[..., 1], mrh[..., 2]]), mask)
    edge = level(blur(ec[..., 0], 1.2), mask) ** 1.2      # AO изнутри даёт на ребре ~половину — к самой кромке
    cavity = level(blur(ec[..., 1], 3.0), mask)
    # укрытые места между деталями — AO игровой сетки: открытое 1 → 0; фон атласа укрытым не считается
    shelter = np.clip((0.9 - blur(ao, 2.0)) / 0.55, 0.0, 1.0)
    shelter[~mask] = 0.0
    cavity = np.maximum(cavity, shelter)
    hand_raw = ec[..., 2]
    if atlas == 'Wood':
        hand_raw = np.clip((hand_raw - 0.28) / 0.72, 0.0, 1.0)   # Wood_Wear: фон 0,28 — лак цел
    hand = level(blur(hand_raw, 2.0), mask)
    wear = np.dstack([edge, cavity, hand])
    wear = pushpull(wear, mask)
    wear = half(wear, WEAR_SIZE)
    save(wear, ASSET / f'{PREFIX}_{tag}_wear.png', False)
    log(atlas, 'wear edge', round(float(edge[mask].mean()), 3), 'cavity', round(float(cavity[mask].mean()), 3),
        'hand', round(float(hand[mask].mean()), 3))
print('MOSIN_PACK_DONE', flush=True)
