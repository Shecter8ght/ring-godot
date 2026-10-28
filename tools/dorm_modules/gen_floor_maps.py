"""Паркет «ёлочкой» и плитка 20 × 20: точная раскладка по элементам, бесшовные карты.

  python -X utf8 tools/dorm_modules/gen_floor_maps.py <папка textures> [размер, px]

Паркет: планка 70 × 350 мм (5 : 1), раскладка «лесенкой» вдоль осей; в материале поворачивается на 45°.
Тайл 2,1 × 2,1 м = 30 ширин планки (период ёлочки 2k по каждой оси).
  parquet_color   — шпон sapele (CC0, assets/textures) по каждой планке своим куском вдоль длины, тон планок разный;
  parquet_height  — планка 1, щели 0, лёгкая фаска; parquet_id — случайное значение планки (порог «выбита»);
  parquet_crack   — продольная трещина у каждой планки (материал покажет её у части планок);
  parquet_mastic  — битумная мастика и стяжка под планками (тон).
Плитка: 20 × 20, шов 3 мм; тайл 2 × 2 м.
  tile_id, tile_tone, tile_height, tile_crack (ломаная трещина через плитку), tile_chip (скол угла),
  tile_glue (клей со следами зубчатого шпателя под выбитой плиткой).
"""
import os
import sys

import numpy as np
from PIL import Image

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
rng = np.random.default_rng(2610)


def save(path: str, a: np.ndarray, bits16: bool = True) -> None:
    a = np.clip(a, 0.0, 1.0)
    if a.ndim == 3:
        Image.fromarray((a * 255).astype(np.uint8)).save(path)
    elif bits16:
        Image.fromarray((a * 65535).astype(np.uint16)).save(path)
    else:
        Image.fromarray((a * 255).astype(np.uint8)).save(path)


def hash01(*ids) -> np.ndarray:
    """Псевдослучайное 0..1 по целым номерам (одинаковое для всех пикселей элемента): ключ из номеров,
    затем перемешивание splitmix64 — у соседних номеров значения не связаны."""
    key = np.zeros(np.shape(ids[0]), dtype=np.uint64)
    for i, v in enumerate(ids):
        key = key * np.uint64(0x100000001B3) ^ (np.asarray(v).astype(np.int64).astype(np.uint64) + np.uint64(i * 40503 + 1))
    z = key + np.uint64(0x9E3779B97F4A7C15)
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    z = z ^ (z >> np.uint64(31))
    return (z >> np.uint64(40)).astype(np.float64) / float(1 << 24)


def smooth_noise(n: int, cells: int, seed: int) -> np.ndarray:
    """Бесшовный плавный шум (интерполяция решётки cells × cells)."""
    r = np.random.default_rng(seed).random((cells, cells))
    x = np.arange(n) * cells / n
    i0 = np.floor(x).astype(int) % cells
    i1 = (i0 + 1) % cells
    t = x - np.floor(x)
    t = t * t * (3 - 2 * t)
    a = r[i0][:, i0] * (1 - t)[None, :] + r[i0][:, i1] * t[None, :]
    b = r[i1][:, i0] * (1 - t)[None, :] + r[i1][:, i1] * t[None, :]
    return a * (1 - t)[:, None] + b * t[:, None]


def fbm(n: int, base: int, octaves: int, seed: int) -> np.ndarray:
    out, amp, tot = np.zeros((n, n)), 1.0, 0.0
    for o in range(octaves):
        out += amp * smooth_noise(n, base * 2 ** o, seed + o)
        tot += amp
        amp *= 0.5
    return out / tot


# ---------------------------------------------------------------- паркет

def parquet(out: str, n: int) -> None:
    k, period = 5, 30                                  # длина = 5 ширин; тайл — 30 ширин (кратно 2k)
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float64)
    x = xs / n * period
    y = ys / n * period
    c = np.floor(x)
    yl = y - (c - k + 1)
    t = np.floor(yl / (2 * k))
    r = yl - 2 * k * t
    is_h = r < k
    m = np.floor(y) - 2 * k * t
    # Номер планки и её локальные координаты (вдоль 0..k, поперёк 0..1).
    pid_a = np.where(is_h, m, c)
    pid_b = np.where(is_h, t * 2, t * 2 + 1)
    along = np.where(is_h, x - m, y - (c + 1 + 2 * k * t))
    across = np.where(is_h, y - (m + 2 * k * t), x - c)
    # Бесшовность: номер по модулю периода решётки.
    pid_a = np.mod(pid_a, period)
    pid_b = np.mod(pid_b, period // k)
    rid = hash01(pid_a.astype(np.int64), pid_b.astype(np.int64))
    rid2 = hash01(pid_b.astype(np.int64) + 17, pid_a.astype(np.int64) + 5)
    # Шпон: свой кусок текстуры у каждой планки, волокна вдоль длины.
    wood = np.asarray(Image.open(os.path.join(REPO, "assets/textures/sapele_veneer/albedo.jpg")).convert("RGB")).astype(np.float64) / 255
    wh, ww = wood.shape[:2]
    plank_w = 0.07
    tex_m = 1.0                                         # шпон Poly Haven: около 1 м на кадр
    u = (along * plank_w / tex_m + rid * 0.73) % 1.0
    v = (across * plank_w / tex_m + rid2 * 0.91) % 1.0
    # Волокна вдоль планки: вдоль — ось v текстуры (полосы sapele вертикальные).
    col = wood[(u * (wh - 1)).astype(int), (v * (ww - 1)).astype(int)]
    lum = col.mean(axis=2, keepdims=True)
    oak = np.array([0.47, 0.36, 0.25])                  # старый дуб под потёртым лаком, не рыжий
    col = oak * (0.45 + 1.0 * lum) * (0.7 + 0.45 * rid[..., None])
    gap = np.minimum(np.minimum(along, k - along), np.minimum(across, 1 - across)) * plank_w   # м до края
    edge = np.clip(gap / 0.0012, 0, 1)
    height = edge * (0.9 + 0.1 * rid) * (1 - 0.04 * (np.abs(across - 0.5) * 2) ** 2)
    # Грязь, забитая в щели и у краёв планок.
    grime = np.clip(gap / 0.006, 0, 1)
    col *= (0.55 + 0.45 * grime)[..., None] * (0.75 + 0.25 * edge)[..., None]
    # Продольная трещина (раскол по волокну) на участке планки.
    line = 0.5 + 0.28 * (rid2 - 0.5) + 0.05 * np.sin(along * 3.1 + rid * 6.3)
    a0, a1 = rid * 2.0, rid * 2.0 + 1.5 + rid2 * 1.5
    crack = (np.abs(across - line) < 0.035) & (along > a0) & (along < a1)
    mastic = 0.25 + 0.5 * fbm(n, 6, 5, 31) + 0.2 * (np.sin((x + y) * 9.0) > 0.85)
    save(f"{out}/parquet_color.png", col)
    save(f"{out}/parquet_height.png", height)
    save(f"{out}/parquet_id.png", rid)
    save(f"{out}/parquet_crack.png", crack.astype(np.float64))
    save(f"{out}/parquet_mastic.png", np.clip(mastic, 0, 1))


# ---------------------------------------------------------------- плитка

def tiles(out: str, n: int) -> None:
    count, size_m, grout = 10, 0.2, 0.003
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float64)
    x = xs / n * count
    y = ys / n * count
    tx, ty = np.floor(x), np.floor(y)
    u, v = x - tx, y - ty
    rid = hash01(tx.astype(np.int64), ty.astype(np.int64))
    r2 = hash01(ty.astype(np.int64) + 3, tx.astype(np.int64) + 11)
    r3 = hash01(tx.astype(np.int64) + 29, ty.astype(np.int64) + 7)
    gw = grout / size_m / 2
    dist = np.minimum(np.minimum(u, 1 - u), np.minimum(v, 1 - v))
    body = np.clip((dist - gw) / 0.012, 0, 1)
    height = body * (0.92 + 0.08 * np.clip((dist - gw) / 0.05, 0, 1))
    tone = 0.85 + 0.15 * rid + 0.06 * (fbm(n, 20, 3, 5) - 0.5)
    # Трещина: ломаная от края до края с изломом и тонкой веткой у части.
    p = 0.2 + 0.6 * r2
    q = 0.2 + 0.6 * r3
    kink = 0.35 + 0.3 * rid
    swap = r2 > 0.5                                    # трещина вдоль или поперёк плитки
    cu, cv = np.where(swap, v, u), np.where(swap, u, v)
    line = np.where(cu < kink, p + (0.5 - p) * cu / kink, 0.5 + (q - 0.5) * (cu - kink) / (1 - kink))
    line = line + 0.011 * np.sin(cu * 23 + rid * 40) + 0.007 * np.sin(cu * 67 + r2 * 50) + 0.004 * np.sin(cu * 151 + r3 * 70)
    crack = np.abs(cv - line) < 0.008
    branch = (np.abs((cu - kink) - (cv - 0.5) * (1.2 + r3)) < 0.006) & (cu > kink) & (cu < kink + 0.25) & (r3 > 0.5)
    crack = (crack | branch) & (body > 0.5)
    # Скол угла: угол по r3, радиус 0,12…0,3 плитки, неровный край.
    cx = np.where(r3 < 0.5, 0.0, 1.0)
    cy = np.where((r3 * 4) % 1.0 < 0.5, 0.0, 1.0)
    cd = np.hypot(u - cx, v - cy)
    rough = 0.03 * np.sin(np.arctan2(v - cy, u - cx) * 9 + rid * 30)
    chip = (cd < 0.12 + 0.18 * r2 + rough).astype(np.float64)
    # Клей под плиткой: гребни зубчатого шпателя (свой угол на участке) и пятна.
    ang = np.floor(rid * 4) * 0.5
    ridges = 0.5 + 0.5 * np.sin((x * np.cos(ang) + y * np.sin(ang)) * size_m / 0.008 * np.pi)
    glue = 0.55 * ridges + 0.45 * fbm(n, 8, 4, 77)
    save(f"{out}/tile_id.png", rid)
    save(f"{out}/tile_tone.png", np.clip(tone, 0, 1))
    save(f"{out}/tile_height.png", height)
    save(f"{out}/tile_crack.png", crack.astype(np.float64))
    save(f"{out}/tile_chip.png", chip)
    save(f"{out}/tile_glue.png", np.clip(glue, 0, 1))


if __name__ == "__main__":
    base = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 2048
    for sub in ("parquet", "tiles"):
        os.makedirs(os.path.join(base, sub), exist_ok=True)
    parquet(os.path.join(base, "parquet"), n)
    tiles(os.path.join(base, "tiles"), n)
    print("ok")
