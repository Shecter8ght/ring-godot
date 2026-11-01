"""Разбор стенда нормалей: насколько low с картой нормалей отличается от high в Blender и в Godot.

Сравниваются только пиксели, где видна и low, и high, с отступом от силуэта (силуэты у пар разные по построению).
Яркость 0–255: средняя ошибка, 95-й процентиль и «волны» — ошибка после размытия (плавные пятна, которые и видны
глазом как кривое затенение). Картинки разницы × 4 — diff_<движок>_<вариант>_<деталь>.png в той же папке.

python -X utf8 tools/asset_kit/normal_probe_report.py <папка стенда>
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

DIR = Path(sys.argv[1])
PARTS = ['box_smooth', 'box_hard', 'oct', 'cyl', 'blob']
GODOT = ['tan', 'tan_nocomp', 'gen', 'tan_s3tc', 'tan_rgtc', 'tan_bptc', 'tan_pp']
ERODE = 9                                           # пикселей от силуэта


def load(name: str) -> tuple:
    im = Image.open(DIR / name).convert('RGBA')
    a = np.asarray(im, dtype=np.float32)
    lum = a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722
    mask = Image.fromarray(((a[..., 3] > 250) * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(ERODE))
    return lum, np.asarray(mask) > 0


def blur(x: np.ndarray, sigma: float = 6.0) -> np.ndarray:
    """Гаусс по двум осям (PIL не размывает картинки с плавающей точкой)."""
    r = int(sigma * 3)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    x = np.apply_along_axis(lambda v: np.convolve(v, k, mode='same'), 0, x)
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode='same'), 1, x)


def compare(low_name: str, high_name: str, tag: str) -> dict:
    lo, ml = load(low_name)
    hi, mh = load(high_name)
    m = ml & mh
    d = lo - hi
    w =np.abs(blur(np.where(m, d, 0).astype(np.float32)) / np.maximum(blur(m.astype(np.float32)), 1e-3))
    Image.fromarray(np.clip(np.where(m, 128 + d * 4, 0), 0, 255).astype(np.uint8)).save(DIR / f'diff_{tag}.png')
    ad = np.abs(d[m])
    return {'mean': round(float(ad.mean()), 2), 'p95': round(float(np.percentile(ad, 95)), 2),
            'waves': round(float(w[m].mean()), 2), 'px': int(m.sum())}


def main() -> None:
    rows = {}
    for part in PARTS:
        rows[f'blender/{part}'] = compare(f'blender_{part}_low.png', f'blender_{part}_high.png', f'blender_{part}')
        for v in GODOT:
            ref = 'highpp' if v == 'tan_pp' else 'high'      # свой шейдер сверяется с high тем же шейдером
            rows[f'{v}/{part}'] = compare(f'godot_{v}_{part}.png', f'godot_{ref}_{part}.png', f'godot_{v}_{part}')
    (DIR / 'report.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{"вариант":<12}' + ''.join(f'{p:>22}' for p in PARTS))
    for v in ['blender'] + GODOT:
        print(f'{v:<12}' + ''.join(f'{rows[f"{v}/{p}"]["mean"]:>8}{rows[f"{v}/{p}"]["p95"]:>7}{rows[f"{v}/{p}"]["waves"]:>7}'
                                   for p in PARTS))
    print('столбцы на деталь: средняя ошибка, 95-й процентиль, «волны» (яркость 0–255)')


main()
