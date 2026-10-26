"""Транспорт «Проспекта»: упаковка островов развёртки на растре — плотнее встроенной в Blender.

    python -X utf8 tools/prospekt_vehicles/uvpack.py <острова.json> <выход.json> [растр=1024] [отступ=0.003]

Вход (game_kit.py пишет его после развёртки и выравнивания плотности): {"islands": [{"tris": [[[u, v] ×3], …]}, …]} —
острова в общих единицах (относительные размеры уже верные). Выход: {"scale": s, "fill": доля, "place": [[k, x, y], …]} —
для каждого острова поворот k × 90°, затем масштаб s и сдвиг (x, y) в долях атласа: uv' = R_k · uv · s + (x, y).

Почему своя: на сотнях скруглённых островов кузова встроенная упаковка Blender оставляла пустоты (заполнение 33–54 %).
Здесь острова кладутся от крупных к мелким «вниз-влево» по растру занятости: крупные — по точной форме (свёртка
занятости с маской острова через БПФ, четыре поворота), мелкие — по прямоугольнику (суммы по площадям). Общий масштаб —
двоичным поиском: наибольший, при котором влезают все. Отступ между островами — `отступ` в долях атласа (норма проекта —
12 пикс на 4K = 0,003): маска каждого острова раздута на половину отступа.
"""
from __future__ import annotations

import json
import math
import sys
import time

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.signal import fftconvolve

BIG_PX = 1200          # острова больше стольких клеток растра — по точной форме, меньше — по прямоугольнику
CONTACT = False        # True — крупные по касанию с соседями (на кузове седана 75 % против 76,5 % у нижнего-левого)


def rot(tris: np.ndarray, k: int) -> np.ndarray:
    """Поворот на k × 90° вокруг начала координат (u, v)."""
    u, v = tris[..., 0], tris[..., 1]
    for _ in range(k % 4):
        u, v = -v, u
    return np.stack([u, v], -1)


def raster(tris: np.ndarray, s: float, n: int, pad: int):
    """Маска острова на растре: s — клеток растра на единицу острова; pad — раздувание (половина отступа).
    Возвращает (маска, начало в единицах острова) — клетка (0, 0) маски соответствует точке lo."""
    lo = tris.reshape(-1, 2).min(0)
    hi = tris.reshape(-1, 2).max(0)
    w = int(math.ceil((hi[0] - lo[0]) * s)) + 2 * pad + 1
    h = int(math.ceil((hi[1] - lo[1]) * s)) + 2 * pad + 1
    if w > n or h > n:
        return None, lo
    img = Image.new("1", (w, h), 0)
    d = ImageDraw.Draw(img)
    for t in tris:
        pts = [((p[0] - lo[0]) * s + pad, (p[1] - lo[1]) * s + pad) for p in t]
        d.polygon(pts, fill=1, outline=1)
    m = np.asarray(img, dtype=bool)
    if pad > 0:
        m = ndimage.binary_dilation(m, iterations=pad)
    return m, lo


def first_fit_shape(occ: np.ndarray, m: np.ndarray, contact: bool = False):
    """Свободное место для маски m. Обычно — самое нижнее-левое (меньше строка, затем столбец); contact — где кольцо
    вокруг маски больше всего касается занятого и краёв атласа (меньше щелей между скруглёнными островами), при равенстве
    — нижнее-левое. Возвращает ((строка, столбец), оценка) или None — не влезает."""
    h, w = m.shape
    n = occ.shape[0]
    if h > n or w > n:
        return None
    occ_f = occ.astype(np.float32)
    over = fftconvolve(occ_f, m[::-1, ::-1].astype(np.float32), mode="valid")
    ok = over < 0.5
    if not ok.any():
        return None
    if not contact:
        free = np.argwhere(ok)
        i = np.lexsort((free[:, 1], free[:, 0]))[0]
        return (int(free[i, 0]), int(free[i, 1])), 0.0
    ring = ndimage.binary_dilation(np.pad(m, 1), iterations=1) & ~np.pad(m, 1)
    walled = np.pad(occ_f, 1, constant_values=1.0)            # край атласа — тоже «занято»
    touch = fftconvolve(walled, ring[::-1, ::-1].astype(np.float32), mode="valid")[: ok.shape[0], : ok.shape[1]]
    score = np.where(ok, touch, -1.0)
    best = score.max()
    cand = np.argwhere(score >= best - 0.5)
    i = np.lexsort((cand[:, 1], cand[:, 0]))[0]
    return (int(cand[i, 0]), int(cand[i, 1])), float(best) / max(1.0, float(ring.sum()))


def first_fit_rect(sat: np.ndarray, h: int, w: int):
    """Свободный прямоугольник h × w по таблице сумм занятости sat (размер n+1)."""
    n = sat.shape[0] - 1
    if h > n or w > n:
        return None
    s = sat[h:, w:] - sat[:-h, w:] - sat[h:, :-w] + sat[:-h, :-w]
    free = np.argwhere(s == 0)
    if len(free) == 0:
        return None
    i = np.lexsort((free[:, 1], free[:, 0]))[0]
    return int(free[i, 0]), int(free[i, 1])


def try_pack(islands, s: float, n: int, pad: int):
    """Все острова при масштабе s (клеток на единицу). Возвращает список (k, строка, столбец, lo) или None."""
    occ = np.zeros((n, n), dtype=bool)
    out = [None] * len(islands)
    order = sorted(range(len(islands)), key=lambda i: -islands[i]["area"])
    sat = None
    dirty = True
    for i in order:
        tris = islands[i]["tris"]
        best = None
        big = islands[i]["area"] * s * s > BIG_PX
        for k in (0, 1, 2, 3) if big else (0, 1):
            rt = rot(tris, k)
            m, lo = raster(rt, s, n, pad)
            if m is None:
                continue
            if big:
                hit = first_fit_shape(occ, m, CONTACT)
                if hit is None:
                    continue
                pos, sc = hit
            else:
                if dirty:
                    sat = np.zeros((n + 1, n + 1), dtype=np.int32)
                    sat[1:, 1:] = occ.cumsum(0).cumsum(1)
                    dirty = False
                pos = first_fit_rect(sat, m.shape[0], m.shape[1])
            if pos is None:
                continue
            key = (-sc, pos[0], pos[1]) if big and CONTACT else (0.0, pos[0], pos[1])
            if best is None or key < best[0]:
                best = (key, pos, k, m, lo)
        if best is None:
            return None
        _, (r, c), k, m, lo = best
        if big:
            occ[r:r + m.shape[0], c:c + m.shape[1]] |= m
        else:
            occ[r:r + m.shape[0], c:c + m.shape[1]] = True      # мелкий занимает свой прямоугольник целиком
        dirty = True
        out[i] = (k, r, c, lo)
    return out


def pack(islands, n: int, margin: float):
    pad = max(1, int(round(margin * n / 2)))
    total = sum(isl["area"] for isl in islands)
    s_hi = math.sqrt(0.95 * n * n / total)            # больше 95 % не влезет точно
    s_lo = math.sqrt(0.30 * n * n / total)
    best = None
    t0 = time.time()
    res = try_pack(islands, s_lo, n, pad)
    while res is None:                                # совсем плохо — уменьшать, пока не влезет
        s_lo *= 0.85
        res = try_pack(islands, s_lo, n, pad)
    best = (s_lo, res)
    for _ in range(7):
        s = math.sqrt(s_lo * s_hi)
        res = try_pack(islands, s, n, pad)
        if res is None:
            s_hi = s
        else:
            s_lo, best = s, (s, res)
        if s_hi / s_lo < 1.012:
            break
    s, res = best
    fill = total * s * s / (n * n)
    print(f"uvpack: островов {len(islands)}, растр {n}, заполнение {fill * 100:.1f} %, {time.time() - t0:.0f} с")
    return s, res, fill


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 1024
    margin = float(sys.argv[4]) if len(sys.argv) > 4 else 0.003
    data = json.load(open(src, encoding="utf-8"))
    islands = []
    for isl in data["islands"]:
        t = np.asarray(isl["tris"], dtype=np.float64).reshape(-1, 3, 2)
        a = 0.5 * np.abs((t[:, 1, 0] - t[:, 0, 0]) * (t[:, 2, 1] - t[:, 0, 1]) - (t[:, 2, 0] - t[:, 0, 0]) * (t[:, 1, 1] - t[:, 0, 1]))
        islands.append({"tris": t, "area": float(a.sum()) + 1e-12})
    s, res, fill = pack(islands, n, margin)
    place = []
    for (k, r, c, lo) in res:
        # клетка (r, c) маски ↔ точка lo острова (после поворота) со сдвигом pad: uv' = (R·uv − lo)·s/n + (c, r)/n
        pad = max(1, int(round(margin * n / 2)))
        place.append([k, (c + pad) / n - lo[0] * s / n, (r + pad) / n - lo[1] * s / n])
    json.dump({"scale": s / n, "fill": fill, "place": place}, open(dst, "w", encoding="utf-8"))


if __name__ == "__main__":
    main()
