"""ПМ «пошарпанный» v01: запечённые карты (bake.py) → игровые PNG рядом с моделью.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/pm_worn/pack.py
Источник — _asset_src/pm_worn_game/maps/raw/<Атлас>_{color,normal,mrh,coat,ao}.png.
→ assets/models/weapons/pm/pm_<Атлас>_100_{albedo,normal,orm,coat}.png (вид в игре один — «100»): ORM — R: AO игровой
  сетки, G: шероховатость, B: металл; coat — жировая плёнка (Non-Color, R): отпечатки, ладони, масло без ровного «пола»
  стека; шейдер оружия опускает по ней шероховатость — в лоб почти не видно, под углом блестит (как у ВЕРАС-54).
→ assets/models/attachments/supp_pm/supp_pm_100_{base_color,roughness,metallic,normal,coat}.png — те же карты глушителя
  в раскладке обвеса (WeaponMods._model_material) для предмета на полу и значка.
Поля островов добираются «push-pull» по пирамиде (среднее по запечённому) до краёв атласа.
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

log = lambda *a: C.log('PM_PACK', *a)  # noqa: E731


def load(name: str):
    path = C.RAW / f'{name}.png'
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
    path.parent.mkdir(parents=True, exist_ok=True)
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


bpy.context.preferences.use_preferences_save = False
for atlas in C.SIZE:
    mrh = load(f'{atlas}_mrh')
    if mrh is None:
        log('skip', atlas, '(нет запекания)')
        continue
    mask = mrh[..., 2] > 0.5
    tag = f'pm_{atlas}_100'
    color = pushpull(load(f'{atlas}_color')[..., :3], mask)
    save(color, C.ASSET / f'{tag}_albedo.png', True)
    nrm = pushpull(load(f'{atlas}_normal')[..., :3], mask)
    v = nrm * 2 - 1
    v /= np.maximum(np.linalg.norm(v, axis=2, keepdims=True), 1e-6)
    normal = v * 0.5 + 0.5
    save(normal, C.ASSET / f'{tag}_normal.png', False)
    rough = pushpull(mrh[..., 1:2], mask)[..., 0]
    metal = pushpull(mrh[..., 0:1], mask)[..., 0]
    ao_raw = load(f'{atlas}_ao')
    ao = pushpull(ao_raw[..., :1], mask)[..., 0] if ao_raw is not None else np.ones_like(rough)
    save(np.dstack([ao, rough, metal]), C.ASSET / f'{tag}_orm.png', False)
    coat_raw = load(f'{atlas}_coat')
    coat = pushpull(coat_raw[..., :1], mask)[..., 0] if coat_raw is not None else np.zeros_like(rough)
    # Плёнка — только сами следы: у стека есть ровный «пол» по всей детали (первая декаль с силой < 1); в игре он дал
    # бы ровный глянец по всей поверхности («стеклянный» вид, владелец 2026-10-19 о ВЕРАС-54).
    floor = float(np.percentile(coat[mask], 40.0)) if mask.any() else 0.0
    prints = np.clip((coat - floor) / max(1.0 - floor, 1e-3), 0.0, 1.0)
    save(prints, C.ASSET / f'{tag}_coat.png', False)
    log(atlas, 'coverage', round(float(mask.mean()), 3), 'rough', round(float(rough[mask].mean()), 3),
        'metal', round(float(metal[mask].mean()), 3), 'ao', round(float(ao[mask].mean()), 3),
        'coat floor', round(floor, 3), 'prints>0.1', round(float((prints[mask] > 0.1).mean()), 4))
    if atlas == 'Suppressor':
        save(color, C.ATT_SUPP / 'supp_pm_100_base_color.png', True)
        save(normal, C.ATT_SUPP / 'supp_pm_100_normal.png', False)
        save(np.dstack([rough, rough, rough]), C.ATT_SUPP / 'supp_pm_100_roughness.png', False)
        save(np.dstack([metal, metal, metal]), C.ATT_SUPP / 'supp_pm_100_metallic.png', False)
        save(prints, C.ATT_SUPP / 'supp_pm_100_coat.png', False)
print('PM_PACK_DONE', flush=True)
