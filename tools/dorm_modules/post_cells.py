"""Поле отслоения по готовой маске трещин (бесшовно): области между трещинами нумеруются с учётом
перехода через край тайла, каждая получает случайное значение; к нему — крупные зоны износа, расстояние
от трещины (отслоение ползёт от трещины внутрь куска) и мелкая рваность. Итог выравнивается по гистограмме:
износ 0,3 = отслоилось около 30 % площади.

  python -X utf8 tools/dorm_modules/post_cells.py <папка карт> [зерно]
  читает crack_mask, peel_patch, peel_ragged → пишет peel_field (16 бит)
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage


def load16(path: str) -> np.ndarray:
    a = np.asarray(Image.open(path)).astype(np.float64)
    a = a / (65535.0 if a.max() > 255 else 255.0)
    return a[..., 0] if a.ndim == 3 else a


def save16(path: str, a: np.ndarray) -> None:
    Image.fromarray(np.clip(a * 65535.0, 0, 65535).astype(np.uint16)).save(path)


def tiled_labels(free: np.ndarray) -> tuple:
    """Связные области свободного (не трещина) с учётом бесшовности: считаем на мозаике 3 × 3, берём центр."""
    h, w = free.shape
    big = np.tile(free, (3, 3))
    lab, n = ndimage.label(big)
    return lab[h:2 * h, w:2 * w], n


def tiled_distance(free: np.ndarray) -> np.ndarray:
    h, w = free.shape
    d = ndimage.distance_transform_edt(np.tile(free, (3, 3)))
    return d[h:2 * h, w:2 * w]


def rank(a: np.ndarray) -> np.ndarray:
    flat = a.ravel()
    order = flat.argsort(kind="stable")
    r = np.empty_like(flat)
    r[order] = np.linspace(0.0, 1.0, flat.size)
    return r.reshape(a.shape)


def peel_field(src: str, seed: int = 7, crack_name: str = "crack_mask", patch_name: str = "peel_patch",
               ragged_name: str = "peel_ragged", out_name: str = "peel_field") -> None:
    crack = load16(f"{src}/{crack_name}.png")
    free = crack < 0.5
    lab, n = tiled_labels(free)
    rng = np.random.default_rng(seed)
    vals = rng.random(n + 1)
    cell = vals[lab]
    # Пиксели самих трещин — значение ближайшего куска.
    idx = ndimage.distance_transform_edt(lab == 0, return_distances=False, return_indices=True)
    cell = cell[idx[0], idx[1]]
    dist = np.clip(tiled_distance(free) / 26.0, 0.0, 1.0)      # ~2,5 см при 2048 на 2 м
    patch = load16(f"{src}/{patch_name}.png")
    ragged = load16(f"{src}/{ragged_name}.png")
    field = 0.62 * cell + 0.24 * patch + 0.07 * dist + 0.07 * ragged
    save16(f"{src}/{out_name}.png", rank(field))


def loss_field(src: str) -> None:
    """Штукатурка до кирпича: крупные куски, край осыпается (рваность по crumble)."""
    field = 0.78 * load16(f"{src}/loss_patch.png") + 0.22 * load16(f"{src}/crumble.png")
    save16(f"{src}/loss_field.png", rank(field))


if __name__ == "__main__":
    kind = sys.argv[2] if len(sys.argv) > 2 else "paint"
    if kind == "paint":
        peel_field(sys.argv[1])
    elif kind == "plaster":
        peel_field(sys.argv[1], 11, "wash_crack", "wash_patch", "wash_ragged", "wash_field")
        loss_field(sys.argv[1])
    print("ok")
