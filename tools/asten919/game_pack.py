"""АСТЕН-919: запечённые карты (game_bake.py) → игровые PNG (по образцу tools/ar15/game_pack.py).

python -X utf8 tools/asten919/game_pack.py [атлас …]
Источник — _asset_src/asten919/game/maps/raw/<Атлас>_{color,rough,metal,normal,ao}.png.
→ assets/models/weapons/asten919/asten919_<Атлас>_100_{albedo,normal,orm}.png; ORM — R: затенение игровой сетки,
G: шероховатость, B: металл. Вид один при любой прочности (владелец 2026-10-19), карт износа по состояниям нет;
жировые следы уже в шероховатости (отдельной маски плёнки _coat нет).
Поля островов добираются «push-pull» по пирамиде (среднее по запечённому): дальние mip-уровни не тянут чёрный фон
в швы. Запечённое — где записан хоть один канал.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / '_asset_src/asten919/game/maps/raw'
GAME = ROOT / 'assets/models/weapons/asten919'
GAME.mkdir(parents=True, exist_ok=True)
ATLASES = ['Slide', 'Frame', 'Magazine']


def read(path: Path) -> np.ndarray:
    im = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_UNCHANGED)
    if im is None:
        raise SystemExit(f'нет карты {path}')
    if im.ndim == 3:
        im = im[..., :3][..., ::-1]                       # BGR → RGB
    return im.astype(np.float32) / (65535.0 if im.dtype == np.uint16 else 255.0)


def write(path: Path, im: np.ndarray) -> None:
    out = np.clip(im * 255.0 + 0.5, 0, 255).astype(np.uint8)
    if out.ndim == 3:
        out = out[..., ::-1]
    ok, buf = cv2.imencode('.png', out)
    buf.tofile(str(path))


def push_pull(im: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Пустое (mask = 0) — средним запечённого по пирамиде; запечённое не меняется."""
    chans = im if im.ndim == 3 else im[..., None]
    levels = [(chans * mask[..., None], mask.astype(np.float32))]
    while min(levels[-1][1].shape) > 1:
        c, w = levels[-1]
        h2, w2 = (c.shape[0] + 1) // 2, (c.shape[1] + 1) // 2
        c = cv2.resize(c, (w2, h2), interpolation=cv2.INTER_AREA) * 4
        ww = cv2.resize(w, (w2, h2), interpolation=cv2.INTER_AREA) * 4
        c = c.reshape(h2, w2, -1)
        levels.append((c, ww))
    fill = levels[-1][0] / np.maximum(levels[-1][1], 1e-6)[..., None]
    for c, w in reversed(levels[:-1]):
        up = cv2.resize(fill, (c.shape[1], c.shape[0]), interpolation=cv2.INTER_LINEAR).reshape(c.shape)
        avg = c / np.maximum(w, 1e-6)[..., None]
        k = np.clip(w, 0, 1)[..., None]
        fill = avg * k + up * (1 - k)
    out = np.where(mask[..., None] > 0, chans, fill)
    return out if im.ndim == 3 else out[..., 0]


def pack(atlas: str) -> None:
    color, rough, metal = read(RAW / f'{atlas}_color.png'), read(RAW / f'{atlas}_rough.png'), read(RAW / f'{atlas}_metal.png')
    normal, ao = read(RAW / f'{atlas}_normal.png'), read(RAW / f'{atlas}_ao.png')
    g = lambda x: x[..., 0] if x.ndim == 3 else x
    # запечённое — где записан хоть один канал (у затенения внутренние стенки чёрные, у металла — ноль)
    mask = ((g(ao) > 0) | (g(rough) > 0) | (g(metal) > 0) | (color.max(-1) > 0)).astype(np.float32)
    orm = np.stack([g(ao), g(rough), g(metal)], -1)
    tag = f'asten919_{atlas}_100'
    write(GAME / f'{tag}_albedo.png', push_pull(color, mask))
    write(GAME / f'{tag}_orm.png', push_pull(orm, mask))
    n = push_pull(normal, mask)
    # нормаль после усреднения — снова единичная (поля)
    v = n * 2 - 1
    v /= np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-6)
    write(GAME / f'{tag}_normal.png', v * 0.5 + 0.5)
    print('ASTEN_PACK', atlas, 'запечено', round(float(mask.mean()), 3), flush=True)


if __name__ == '__main__':
    for a in (sys.argv[1:] or ATLASES):
        pack(a)
