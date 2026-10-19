"""Магазин ВЕРАС-54: запечённые карты (mags_game_bake.py) → игровые PNG, как game_pack.py автомата v13.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/veras54_mags/mags_game_pack.py -- m45|d60
Источник — _asset_src/veras54_game_mags/<m45|d60>/raw/<Атлас>_{color,normal,mrh,ecm,coat,emit,ao}.png.
→ _asset_src/veras54_game_mags/<m45|d60>/game/veras54_<Атлас>_100_{albedo,normal,orm,emission}.png — ORM: R — AO игровой
  сетки, G — шероховатость, B — металл; экспорт (mags_game_export.py) кладёт их рядом с моделью под теми же именами.
→ assets/models/weapons/veras54_mags/ (игра грузит по имени карты цвета; маски износа _wear нет — вид в игре один, 2026-10-19):
  veras54_<Атлас>_100_coat.png — жировая плёнка (R, без ровного «пола»; шейдер сглаживает ей основной слой, как у автомата).
Поля островов добираются «push-pull» по пирамиде до краёв атласа.
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mags_game_common as C  # noqa: E402

MID = sys.argv[sys.argv.index('--') + 1]
M = C.MAGS[MID]
RAW = C.work(MID) / 'raw'
GAME = C.work(MID) / 'game'
GAME.mkdir(parents=True, exist_ok=True)
C.ASSET.mkdir(parents=True, exist_ok=True)
MASK_SIZE = 2048
log = lambda *a: print('MAGS_PACK', MID, *a, flush=True)


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


def half(a: np.ndarray, size: int) -> np.ndarray:
    while a.shape[0] > size:
        h, w = a.shape[0] // 2, a.shape[1] // 2
        a = a[:h * 2, :w * 2].reshape(h, 2, w, 2, *a.shape[2:]).mean(axis=(1, 3))
    return a


atlas = M['atlas']
tag = C.tag(MID)
ecm = load(f'{atlas}_ecm')
if ecm is None:
    raise SystemExit('нет запекания ecm')
mask = ecm[..., 2] > 0.5
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
log('coverage', round(float(mask.mean()), 3), 'rough', round(float(rough[mask].mean()), 3),
    'metal', round(float(metal[mask].mean()), 3), 'ao', round(float(ao[mask].mean()), 3),
    'coat', round(float(coat[mask].mean()), 4), 'coat>0.2', round(float((coat[mask] > 0.2).mean()), 4))
emit = load(f'{atlas}_emit')
if emit is not None and float(emit[..., :3].max()) > 0.002:
    save(pushpull(emit[..., :3], mask), GAME / f'{tag}_emission.png', True)
else:
    log('emission: нет свечения в запекании')
# У стека текстур есть ровный «пол» плёнки по всей детали (первая декаль слоя смешивается MIX с силой < 1). В игре
# плёнка сглаживает основной слой (шейдер weapon_wear, film_roughness): с полом вся деталь выходила ровно глянцевой,
# «стеклянной» (владелец 2026-10-19) — пол вычитается; остаются сами следы.
floor = float(np.percentile(coat[mask], 40.0))
prints = np.clip((coat - floor) / max(1.0 - floor, 1e-3), 0.0, 1.0)
save(half(prints, MASK_SIZE), C.ASSET / f'{tag}_coat.png', False)
log('coat floor', round(floor, 3), 'prints>0.1', round(float((prints[mask] > 0.1).mean()), 4))
print('MAGS_PACK_DONE', MID, flush=True)
