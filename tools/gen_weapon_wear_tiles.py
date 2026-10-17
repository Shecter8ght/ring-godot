"""Общие тайлы износа оружия → assets/textures/weapon_wear/wear_detail.png (python -X utf8 tools/gen_weapon_wear_tiles.py).

Одна бесшовная RGBA-карта 1024² (Non-Color) на все стволы; шейдер src/combat/weapon_wear.gdshader кладёт её
трипланарно в осях модели (размер плитки в метрах — его параметр):
  R — сеть мелких царапин, G — налёт и грязь пятнами, B — ржавчина: пятна и зерно, A — сколы покрытия.
Царапины, налёт и сколы — маски владельца (E:/Models Blender/Маски_АЛЬФА, собственные, не в git); их рисунок
не бесшовный, поэтому края сводятся наложением сдвинутой на полплитки копии с сохранением контраста.
Ржавчина — периодический шум (по построению бесшовный). Нет папки масок — эти каналы тоже из шума.
"""
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MASKS = Path('E:/Models Blender/Маски_АЛЬФА')
OUT = ROOT / 'assets/textures/weapon_wear'
SIZE = 1024
# у масок тёмная рамка по краю — срезается до сведения
MARGIN = 40
rng = np.random.default_rng(1707)


def periodic_noise(octaves, persistence=0.55, base=4):
    """Фрактальный шум, бесшовный по построению: сумма октав сглаженного случайного поля на торе."""
    acc = np.zeros((SIZE, SIZE), np.float64)
    amp = 1.0
    total = 0.0
    for o in range(octaves):
        cells = base * 2 ** o
        grid = rng.random((cells, cells))
        # билинейная интерполяция с заворотом — периодично на краях плитки
        t = np.arange(SIZE) * cells / SIZE
        i0 = np.floor(t).astype(int) % cells
        i1 = (i0 + 1) % cells
        f = t - np.floor(t)
        f = f * f * (3 - 2 * f)
        rows = grid[i0][:, i0] * (1 - f)[None, :] + grid[i0][:, i1] * f[None, :]
        rows1 = grid[i1][:, i0] * (1 - f)[None, :] + grid[i1][:, i1] * f[None, :]
        layer = rows * (1 - f)[:, None] + rows1 * f[:, None]
        acc += layer * amp
        total += amp
        amp *= persistence
    return acc / total


def levels(a, lo=1.0, hi=99.5):
    a0, a1 = np.percentile(a, lo), np.percentile(a, hi)
    return np.clip((a - a0) / max(a1 - a0, 1e-6), 0.0, 1.0)


def seamless(a):
    """Сведение краёв: копия, сдвинутая на полплитки, проявляется к краям; дисперсия сохраняется."""
    n = a.shape[0]
    x = np.arange(n) / n
    win = np.sin(np.pi * x) ** 2
    w = np.outer(win, win)
    b = np.roll(a, (n // 2, n // 2), axis=(0, 1))
    mean = a.mean()
    mix = (a - mean) * w + (b - mean) * (1 - w)
    # при смешении двух несвязанных рисунков контраст падает в √(w²+(1−w)²) раз — возвращаем
    mix /= np.sqrt(w * w + (1 - w) * (1 - w))
    return mix + mean


def owner_mask(rel, fallback):
    path = MASKS / rel
    if not path.exists():
        print('нет маски владельца', rel, '— шум')
        return fallback
    im = Image.open(path).convert('L')
    w, h = im.size
    im = im.crop((MARGIN, MARGIN, w - MARGIN, h - MARGIN)).resize((SIZE, SIZE), Image.LANCZOS)
    a = np.asarray(im, np.float64) / 255.0
    return levels(seamless(a))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scratches = owner_mask('09_Царапины/Царапины_мелкие_01.png', levels(periodic_noise(7, 0.8, 32)) ** 6)
    grime = owner_mask('04_Грязь_и_налёт/Налёт_мелкими_пятнами_01.png', levels(periodic_noise(6, 0.6)))
    chips = owner_mask('10_Сколы_и_потёртости_покрытия/Сколы_пятнами_01.png', levels(periodic_noise(6, 0.5)))
    # ржавчина: крупные очаги × мелкое зерно (раковины), периодично
    blotch = levels(periodic_noise(5, 0.6, 3))
    grain = levels(periodic_noise(4, 0.7, 64))
    rust = levels(blotch * 0.75 + grain * 0.25)
    rgba = np.dstack([scratches, grime, rust, chips])
    img = Image.fromarray((rgba * 255.0 + 0.5).astype(np.uint8), 'RGBA')
    img.save(OUT / 'wear_detail.png', optimize=True)
    # проверка шва: сумма скачков через край против среднего скачка внутри
    for i, name in enumerate('RGBA'):
        c = rgba[:, :, i]
        edge = np.abs(c[:, 0] - c[:, -1]).mean() + np.abs(c[0, :] - c[-1, :]).mean()
        inner = np.abs(np.diff(c, axis=1)).mean() * 2
        print(f'{name}: шов {edge:.4f}, внутри {inner:.4f}')
    print('WEAR_TILES', OUT / 'wear_detail.png')


main()
