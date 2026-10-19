"""Купе Ильи: запечённые карты (game_bake.py) → игровые PNG.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
        --python tools/coupe_ilya/game_pack.py

Из _asset_src/coupe_ilya_game/maps/raw/<атлас>_{color,normal,mra,ao}.png →
_asset_src/coupe_ilya_game/maps/game/<атлас>_{albedo,normal,orm}.png (встраиваются в GLB экспортом; имя картинки
в GLB — имя файла, Godot извлекает её рядом с моделью как coupe_ilya_<атлас>_<канал>.png):
albedo — цвет (sRGB; у стёкол в альфе непрозрачность), normal — касательное пространство OpenGL, ORM — R: AO игровой
сетки (ослаблено: свет в игре и так даёт затенение), G: шероховатость, B: металл — как ждёт glTF.
Поля островов добираются «push-pull» по пирамиде средних запечённого до краёв атласа: дальние mip-уровни не тянут
чёрный фон в швы. Чтение и запись — через Blender (16-битные нормали без потерь).
"""
from __future__ import annotations

from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "_asset_src/coupe_ilya_game/maps/raw"
GAME = ROOT / "_asset_src/coupe_ilya_game/maps/game"
GAME.mkdir(parents=True, exist_ok=True)
ATLASES = ("body", "glass", "wheel", "bay", "interior")
AO_STRENGTH = 0.6
log = lambda *a: print("COUPE_PACK", *a, flush=True)


def load(name: str) -> np.ndarray | None:
    path = RAW / f"{name}.png"
    if not path.exists():
        return None
    im = bpy.data.images.load(str(path))
    im.colorspace_settings.name = "Non-Color"          # сырые значения файла, без преобразований
    w, h = im.size
    a = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(a)
    bpy.data.images.remove(im)
    return a.reshape(h, w, 4)


def save(arr: np.ndarray, path: Path, srgb: bool, alpha: np.ndarray | None = None) -> None:
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), np.float32)
    rgba[..., :3] = arr[..., :3]
    if alpha is not None:
        rgba[..., 3] = alpha
    im = bpy.data.images.new(path.stem, w, h, alpha=alpha is not None, float_buffer=False)
    im.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    im.pixels.foreach_set(np.clip(rgba, 0, 1).ravel())
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)
    log("сохранено", path.name, w)


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


for atlas in ATLASES:
    color = load(f"{atlas}_color")
    if color is None:
        log("нет запекания", atlas)
        continue
    mra = load(f"{atlas}_mra")
    # где запечено (с полями запекания): B прохода mra — 1 (у стёкол — непрозрачность > 0), пустота после очистки — 0
    # (альфу очистка заливает единицей — по ней покрытие не понять)
    mask = mra[..., 2] > 0.02
    tag = atlas
    alpha = pushpull(mra[..., 2:3], mask)[..., 0] if atlas == "glass" else None
    save(pushpull(color[..., :3], mask), GAME / f"{tag}_albedo.png", True, alpha)
    nrm = load(f"{atlas}_normal")[..., :3]
    # прозрачный шейдер стекла нормаль не отдаёт — запекание пишет нулевой вектор; там стекло плоское
    flat = (np.linalg.norm(nrm * 2 - 1, axis=2) < 0.5) & mask
    nrm[flat] = (0.5, 0.5, 1.0)
    nrm = pushpull(nrm, mask)
    v = nrm * 2 - 1
    v /= np.maximum(np.linalg.norm(v, axis=2, keepdims=True), 1e-6)
    save(v * 0.5 + 0.5, GAME / f"{tag}_normal.png", False)
    rough = pushpull(mra[..., 1:2], mask)[..., 0]
    metal = pushpull(mra[..., 0:1], mask)[..., 0]
    ao_raw = load(f"{atlas}_ao")
    ao = pushpull(ao_raw[..., :1], mask)[..., 0] if ao_raw is not None else np.ones_like(rough)
    ao = 1.0 - (1.0 - ao) * AO_STRENGTH
    save(np.dstack([ao, rough, metal]), GAME / f"{tag}_orm.png", False)
    log(atlas, "покрытие", round(float(mask.mean()), 3), "плоских нормалей", round(float(flat.sum() / max(mask.sum(), 1)), 3),
        "шероховатость", round(float(rough[mask].mean()), 3),
        "металл", round(float(metal[mask].mean()), 3), "AO", round(float(ao[mask].mean()), 3),
        "непрозрачность" if alpha is not None else "", round(float(alpha[mask].mean()), 3) if alpha is not None else "")
print("COUPE_PACK_DONE", flush=True)
