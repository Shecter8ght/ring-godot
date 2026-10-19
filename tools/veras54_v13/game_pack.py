"""ВЕРАС-54 v13: запечённые карты (game_bake.py) → игровые PNG рядом с моделью.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/veras54_v13/game_pack.py
Источник — _asset_src/veras54_game_v13/maps/raw/<Атлас>_{color,normal,mrh,ecm,coat,emit,ao}.png.
→ _asset_src/veras54_game_v13/maps/game/veras54_<Атлас>_100_{albedo,normal,orm}.png (патрон — veras54_Ammo_{…}); ORM — R: AO
  игровой сетки, G: шероховатость, B: металл. Экспорт (export_veras54.py) кладёт их рядом с моделями .gltf под теми же именами —
  вьюмодель, мировая и подробная делят один набор.
→ assets/models/weapons/veras54/ (сразу в игру, их грузит код по имени карты цвета):
  veras54_<Атлас>_100_wear.png — маска износа шейдера (Non-Color, 2048): R — выпуклые кромки, G — углубления и укрытые
  места, B — места хвата и трения (формат — src/combat/weapon_wear.gdshader).
  veras54_<Атлас>_100_coat.png — жировая плёнка (Non-Color, 2048, R): отпечатки, ладони, масло — в шейдере слой Clearcoat
  (в Blender — канал стека Oil film → Coat Weight, Coat IOR 1,47, шероховатость 0,1): в лоб почти не видно, в отражении блестит.
  В maps/game ещё veras54_Magazine_100_emission.png — светонакопительные цифры магазина (sRGB).
Поля островов добираются «push-pull» по пирамиде (среднее по запечённому) до краёв атласа.
"""
from __future__ import annotations

from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / '_asset_src/veras54_game_v13/maps/raw'
ASSET = ROOT / 'assets/models/weapons/veras54'
ASSET.mkdir(parents=True, exist_ok=True)
GAME = ROOT / '_asset_src/veras54_game_v13/maps/game'
GAME.mkdir(parents=True, exist_ok=True)
ATLASES = {'Steel': '100', 'Polymer': '100', 'Magazine': '100', 'Ammo': ''}
MASK_SIZE = 2048
log = lambda *a: print('VERAS_PACK', *a, flush=True)


def load(name: str):
    path = RAW / f'{name}.png'
    if not path.exists():
        return None
    im = bpy.data.images.load(str(path))
    im.colorspace_settings.name = 'Non-Color'
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)


def save(arr: np.ndarray, path: Path, srgb: bool) -> None:
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = arr[..., :3] if arr.ndim == 3 and arr.shape[2] >= 3 else (arr[..., None] if arr.ndim == 2 else arr[..., :1])
    im = bpy.data.images.new(path.stem, w, h, alpha=False, float_buffer=False)
    im.colorspace_settings.name = 'sRGB' if srgb else 'Non-Color'
    im.pixels.foreach_set(np.clip(rgba, 0, 1).ravel())
    im.filepath_raw = str(path)
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
    log('saved', path.name, w)


def pushpull(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
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
    lit = a[mask & (a > 0.02)]
    hi = float(np.percentile(lit, 99.0)) if lit.size else 1.0
    return np.clip(a / max(hi, 1e-3), 0.0, 1.0)


for atlas, state in ATLASES.items():
    ecm = load(f'{atlas}_ecm')
    if ecm is None:
        log('skip', atlas, '(нет запекания)')
        continue
    mask = ecm[..., 2] > 0.5
    tag = f'veras54_{atlas}_{state}' if state else f'veras54_{atlas}'
    color = pushpull(load(f'{atlas}_color')[..., :3], mask)
    save(color, GAME / f'{tag}_albedo.png', True)
    nrm = pushpull(load(f'{atlas}_normal')[..., :3], mask)
    v = nrm * 2 - 1
    v /= np.maximum(np.linalg.norm(v, axis=2, keepdims=True), 1e-6)
    save(v * 0.5 + 0.5, GAME / f'{tag}_normal.png', False)
    mrh = load(f'{atlas}_mrh')
    rough = pushpull(mrh[..., 1:2], mask)[..., 0]
    metal = pushpull(mrh[..., 0:1], mask)[..., 0]
    ao_raw = load(f'{atlas}_ao')
    ao = pushpull(ao_raw[..., :1], mask)[..., 0] if ao_raw is not None else np.ones_like(rough)
    save(np.dstack([ao, rough, metal]), GAME / f'{tag}_orm.png', False)
    coat_raw = load(f'{atlas}_coat')
    coat = pushpull(coat_raw[..., :1], mask)[..., 0] if coat_raw is not None else np.zeros_like(rough)
    log(atlas, 'coverage', round(float(mask.mean()), 3), 'rough', round(float(rough[mask].mean()), 3),
        'metal', round(float(metal[mask].mean()), 3), 'ao', round(float(ao[mask].mean()), 3),
        'coat', round(float(coat[mask].mean()), 4), 'coat>0.2', round(float((coat[mask] > 0.2).mean()), 4))
    emit = load(f'{atlas}_emit')
    if emit is not None and float(emit[..., :3].max()) > 0.002:
        save(pushpull(emit[..., :3], mask), GAME / f'{tag}_emission.png', True)
    if not state:
        continue
    # жировая плёнка — отдельной маской (в шейдере Clearcoat)
    save(half(coat, MASK_SIZE), ASSET / f'{tag}_coat.png', False)
    # маска износа шейдера: каналы сглажены (шум лучей AO), уровни — по запечённому
    ec = pushpull(np.dstack([ecm[..., 0], ecm[..., 1], mrh[..., 2]]), mask)
    edge = level(blur(ec[..., 0], 1.2), mask) ** 1.2
    cavity = level(blur(ec[..., 1], 3.0), mask)
    shelter = np.clip((0.9 - blur(ao, 2.0)) / 0.55, 0.0, 1.0)
    shelter[~mask] = 0.0
    cavity = np.maximum(cavity, shelter)
    # хват: заданные места деталей + жировые следы рук (отпечатки и ладони — там, где берутся руками). У плёнки стека есть
    # ровный «пол» по всей детали (первая декаль слоя смешана с силой < 1 — так в принятом high-poly; в _coat он остаётся):
    # в хват идут только следы сверх пола, иначе «места хвата» были бы по всей поверхности (+0,2…0,4).
    floor = float(np.percentile(coat[mask], 40.0)) if mask.any() else 0.0
    prints = np.clip((coat - floor) / max(1.0 - floor, 1e-3), 0.0, 1.0)
    hand = np.maximum(blur(ec[..., 2], 2.0), np.clip(blur(prints, 6.0) * 1.6, 0.0, 0.85))
    log(atlas, 'coat floor', round(floor, 3))
    wear = pushpull(np.dstack([edge, cavity, np.clip(hand, 0.0, 1.0)]), mask)
    save(half(wear, MASK_SIZE), ASSET / f'{tag}_wear.png', False)
    log(atlas, 'wear edge', round(float(edge[mask].mean()), 3), 'cavity', round(float(cavity[mask].mean()), 3),
        'hand', round(float(hand[mask].mean()), 3))
print('VERAS_PACK_DONE', flush=True)
