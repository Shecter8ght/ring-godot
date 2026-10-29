"""Облупленная масляная краска общежития, v03: карты для материала с живым износом (тайл 2 × 2 м, бесшовно).

Устроено по тому, как стареет настоящая масляная краска на штукатурке:
- сетка трещин «крокодиловой кожи» — ячейки Вороного с искажёнными координатами: кромки кривые, стыки на три
  стороны, как при усадке краски. Куски ~1,6 см, участки трещин шире, волосяная сетка ~0,7 см — шире, где краска старше;
- порядок отслоения E (где E < износ — краски нет): крупные пятна с рваным краем (шум с искажением координат),
  сдвиг на целый кусок между трещинами (у кромки куски отпадают целиком, внутри голого места остаются островки),
  мелкие точки сколов впереди кромки. E выровнен по площади: износ 0,3 = снято 30 %;
- крутизна E и её направление: по ним материал считает расстояние до кромки в миллиметрах при любом износе —
  загнутая кромка со светлой изнанкой и тенью, приподнятые края кусков рядом с отслоением, тёмная грязь у ступеньки;
- тон краски: выцветание пятнами, мазки кисти, подтёки, мушиные точки; рельеф: мазки, скруглённые края кусков,
  бороздки трещин; под краской — шпаклёвка, местами старый слой и фотоскан штукатурки (Poly Haven, CC0).

  python -X utf8 tools/dorm_modules/gen_paint_v3.py [папка] [--size 4096] [--seed 7] [--preview]

Выход (папка по умолчанию — textures/paint_v3 комплекта модулей):
  peel.png         16 бит RGBA: E, log10 крутизны (на мм), направление крутизны x, y (0,5 + 0,5·n, ось v вверх);
  paint_masks.png  16 бит RGBA: расстояние до трещины в ширинах трещины / 4, высота «блюдца» куска (подъём краёв),
                   случайное число куска, где нет загиба (мелкие сколы);
  paint_tone.png   8 бит RGBA: тон (0,5 — средний), подтёки, мушиные точки, меление;
  paint_normal.png 8 бит RGB, OpenGL: мазки, скруглённые края кусков, бороздки трещин, точки;
  cup_normal.png   8 бит RGB, OpenGL: подъём краёв кусков при полном «блюдце» (материал масштабирует);
  under_masks.png  8 бит RGBA: пятна шпаклёвки, пятна старого слоя, грязь на штукатурке, где кромка загибается;
  under_cells.png  8 бит RGBA: кусок старого слоя (случайное), расстояние до его кромки (мм / 2),
                   кусок шпаклёвки, гладкая часть E (кромка большого поля краски);
  plaster_*.jpg    фотоскан штукатурки (копия, тайл тот же).
"""
import argparse
import os
import shutil
import time

import cv2
import numpy as np
from scipy import ndimage as ndi

TILE_MM = 2000.0
KIT = "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures/paint_v3"
PLASTER = "E:/Games/RING-godot/_asset_src/dorm_textures/ph_painted_plaster_wall_4k"


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def frac(x):
    return x - np.floor(x)


class Gen:
    def __init__(self, n: int, seed: int):
        self.n = n
        self.mm = n / TILE_MM                     # пикселей на миллиметр
        self.rng = np.random.default_rng(seed)
        self.fy = np.fft.fftfreq(n)[:, None]
        self.fx = np.fft.rfftfreq(n)[None, :]

    # -------------------------------------------------------------- шумы
    def noise(self, sx_mm: float, sy_mm: float = None):
        """Гладкий бесшовный шум: белый шум, сглаженный гауссом в частотах (sx, sy — по горизонтали и вертикали).
        Среднее 0, разброс 1."""
        sy_mm = sx_mm if sy_mm is None else sy_mm
        sx, sy = sx_mm * self.mm, sy_mm * self.mm
        w = self.rng.standard_normal((self.n, self.n)).astype(np.float32)
        k = np.exp(-2.0 * np.pi ** 2 * (sx * sx * self.fx ** 2 + sy * sy * self.fy ** 2))
        a = np.fft.irfft2(np.fft.rfft2(w) * k, s=(self.n, self.n)).astype(np.float32)
        a -= a.mean()
        a /= a.std() + 1e-9
        return a

    def warp(self, a, dx_mm, dy_mm):
        """Сдвиг координат (мм) с переносом через край тайла."""
        yy, xx = np.mgrid[0:self.n, 0:self.n].astype(np.float32)
        mx = (xx + dx_mm * self.mm).astype(np.float32)
        my = (yy + dy_mm * self.mm).astype(np.float32)
        return cv2.remap(a.astype(np.float32), mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)

    def blur(self, a, s_mm: float):
        return ndi.gaussian_filter(a, s_mm * self.mm, mode="wrap")

    def grad(self, a):
        """Градиент на мм по осям картинки (столбец, строка), с переносом через край."""
        gx = (np.roll(a, -1, 1) - np.roll(a, 1, 1)) * 0.5 * self.mm
        gy = (np.roll(a, -1, 0) - np.roll(a, 1, 0)) * 0.5 * self.mm
        return gx, gy

    def normal_from_height(self, h_mm, gain: float = 1.0):
        """Нормаль OpenGL из высоты в мм: n = (−∂h/∂u, −∂h/∂v, 1), v вверх (строки вниз)."""
        gx, gy = self.grad(h_mm)
        nx, ny = -gx * gain, gy * gain
        nz = np.ones_like(nx)
        ln = np.sqrt(nx * nx + ny * ny + nz * nz)
        return np.stack([nx / ln, ny / ln, nz / ln], -1)

    # -------------------------------------------------------------- сетка трещин
    def cells(self, cell_mm: float, warp: float = 0.3, jag: float = 0.06, chunk: int = 512):
        """Ячейки Вороного на решётке с полным разбросом точек, координаты искажены шумом на масштабе ячейки
        (кривые кромки) и в 7 раз мельче (рваность). Возвращает точное расстояние до ближайшей кромки (мм)
        и номер ячейки; решётка целая на тайл, поэтому всё бесшовно."""
        n = self.n
        m = max(2, int(round(TILE_MM / cell_mm)))
        c = n / m
        jit = self.rng.uniform(0.04, 0.96, (m, m, 2)).astype(np.float32)
        wx = (self.noise(cell_mm * 0.9) * warp + self.noise(cell_mm * 0.14) * jag) * c
        wy = (self.noise(cell_mm * 0.9) * warp + self.noise(cell_mm * 0.14) * jag) * c
        edge = np.empty((n, n), np.float32)
        ids = np.empty((n, n), np.int32)
        xs = np.arange(n, dtype=np.float32)[None, :]
        for r0 in range(0, n, chunk):
            r1 = min(n, r0 + chunk)
            ys = np.arange(r0, r1, dtype=np.float32)[:, None]
            X = xs + wx[r0:r1]
            Y = ys + wy[r0:r1]
            gi = np.floor(X / c).astype(np.int32)
            gj = np.floor(Y / c).astype(np.int32)
            f1 = np.full(X.shape, np.inf, np.float32)
            f2 = np.full(X.shape, np.inf, np.float32)
            p1x = np.zeros(X.shape, np.float32)
            p1y = np.zeros(X.shape, np.float32)
            p2x = np.zeros(X.shape, np.float32)
            p2y = np.zeros(X.shape, np.float32)
            i1 = np.zeros(X.shape, np.int32)
            for dj in (-1, 0, 1):
                for di in (-1, 0, 1):
                    ci, cj = gi + di, gj + dj
                    pi, pj = ci % m, cj % m
                    px = (ci + jit[pj, pi, 0]) * c
                    py = (cj + jit[pj, pi, 1]) * c
                    d = (X - px) ** 2 + (Y - py) ** 2
                    closer = d < f1
                    second = (~closer) & (d < f2)
                    f2 = np.where(closer, f1, np.where(second, d, f2))
                    p2x = np.where(closer, p1x, np.where(second, px, p2x))
                    p2y = np.where(closer, p1y, np.where(second, py, p2y))
                    f1 = np.where(closer, d, f1)
                    p1x = np.where(closer, px, p1x)
                    p1y = np.where(closer, py, p1y)
                    i1 = np.where(closer, pj * m + pi, i1)
            sep = np.sqrt((p2x - p1x) ** 2 + (p2y - p1y) ** 2) + 1e-6
            edge[r0:r1] = (f2 - f1) / (2.0 * sep) / self.mm
            ids[r0:r1] = i1
        return edge, ids, m * m


def save16(path, chans):
    """16-битный PNG из каналов 0..1 (1, 3 или 4 канала, порядок RGB(A))."""
    a = [np.clip(c, 0.0, 1.0) for c in chans]
    if len(a) == 1:
        img = a[0]
    else:
        a = [a[2], a[1], a[0]] + a[3:]          # cv2 пишет BGR(A)
        img = np.stack(a, -1)
    cv2.imwrite(path, (img * 65535.0 + 0.5).astype(np.uint16))


def save8(path, chans):
    a = [np.clip(c, 0.0, 1.0) for c in chans]
    if len(a) == 1:
        img = a[0]
    else:
        a = [a[2], a[1], a[0]] + a[3:]
        img = np.stack(a, -1)
    cv2.imwrite(path, (img * 255.0 + 0.5).astype(np.uint8))


def rank(a):
    flat = a.ravel()
    order = flat.argsort(kind="stable")
    r = np.empty(flat.size, np.float32)
    r[order] = np.linspace(0.0, 1.0, flat.size, dtype=np.float32)
    return r.reshape(a.shape)


def build(out: str, n: int, seed: int, preview: bool) -> None:
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    g = Gen(n, seed)
    mm = g.mm

    def log(msg):
        print(f"[{time.time() - t0:6.1f} с] {msg}", flush=True)

    # ---------------------------------------------------------- поле отслоения (гладкая часть)
    # Искажение координат — только у крупных составляющих (иначе мелочь вытягивается в косые щепки);
    # мелкая рваность кромки — добавкой без искажения и слабым мелким сдвигом.
    wx = g.noise(110) * 30 + g.noise(10) * 3.0
    wy = g.noise(110) * 30 + g.noise(10) * 3.0
    S = g.warp(g.noise(150) + 0.55 * g.noise(55), wx, wy) + 0.30 * g.noise(19) + 0.15 * g.noise(6.5)
    S = (S - S.mean()) / S.std()
    log("поле отслоения")

    # Где краска старее (трещины гуще) — ближе к местам отслоения.
    zone = -0.65 * g.blur(S, 25) + 0.75 * g.noise(120)
    zone = (zone - zone.mean()) / zone.std()

    # ---------------------------------------------------------- сетка трещин
    # Одна основная сетка кусков ~2,3 см; «крупные» трещины — непрерывные участки той же сетки шире (без крестовин,
    # как при росте трещин: тонкие упираются в толстые); волосяная сетка ~0,8 см — пятнами, где краска старше.
    e2, id2, k2 = g.cells(15.0, 0.34, 0.045)
    log(f"основные куски: {k2}")
    e3, id3, _ = g.cells(6.5, 0.3, 0.05)
    log("волосяная сетка")
    run = smoothstep(0.25, 1.0, 0.85 * g.noise(30) + 0.35 * g.noise(8))
    hw2 = (0.36 + 0.08 * np.clip(g.noise(12), -1.5, 1.5)) * (1.0 + 1.5 * run)
    # Сетка либо есть (не тоньше полутора пикселей), либо её нет: тонкая трещина в доли пикселя рисуется пунктиром.
    # Граница — по зоне старения, сетка обрывается на ней, как у настоящей краски.
    pres2 = smoothstep(-0.62, -0.5, zone + 0.3 * g.noise(15))
    # Волосяные — не тоньше пикселя (иначе пунктир), зато светлее: в середине линии не полная темнота.
    hw3 = 0.36 * smoothstep(-0.2, 0.7, zone + 0.4 * g.noise(40))
    q = e2 / np.maximum(hw2, 1e-3) + (1.0 - pres2) * 50.0
    # Волосяные тоньше пикселя: порог по ним даёт пунктир, поэтому это мягкая сглаженная линия в тоне краски.
    hair = np.exp(-(e3 / np.maximum(hw3, 1e-3)) ** 2) * smoothstep(0.02, 0.12, hw3)
    q = np.minimum(q, 50.0)
    log("ширина трещин")

    # ---------------------------------------------------------- куски между трещинами
    rnd = frac(np.sin(id2.astype(np.float64) * 12.9898 + 4.1) * 43758.5453).astype(np.float32)
    dflake = e2
    r_in = np.asarray(ndi.maximum(e2, labels=id2, index=np.arange(k2)), np.float32)[id2]

    # «Блюдце»: у кусков рядом с отслоением края поднимаются (материал включает по расстоянию до кромки).
    rc = np.clip(0.38 * r_in, 1.2, 7.0)
    cup = (1.0 - smoothstep(0.0, rc, dflake)) ** 1.6 * np.clip(r_in / 8.0, 0.35, 1.0)
    # Скругление края куска вниз, в трещину (подушка) — всегда.
    bevel = 1.0 - (1.0 - np.clip(dflake / 1.5, 0.0, 1.0)) ** 2
    bevel = 1.0 - (1.0 - bevel) * pres2

    spots = smoothstep(2.5, 3.3, g.noise(0.9)) + 0.6 * smoothstep(2.9, 3.6, g.noise(2.2))

    # ---------------------------------------------------------- порядок отслоения E
    u = 2.0 * rnd - 1.0
    jit = np.sign(u) * np.abs(u) ** 2.2
    raw = S + 0.5 * jit - 1.1 * np.clip(spots, 0.0, 1.0)
    E = rank(raw)
    # Крутизна — от гладкой части поля (без скачков между кусками и без точек сколов): иначе внутри голых мест
    # у каждой границы куска получалась ложная «кромка» со шпаклёвкой и загибом.
    Es = g.blur(rank(S), 1.0)
    gx, gy = g.grad(Es)
    G = np.sqrt(gx * gx + gy * gy) + 1e-7
    du, dv = gx / G, -gy / G
    lg = (np.log10(G) + 5.0) / 5.0            # крутизна 1e-5…1 на мм → 0…1
    log(f"E: крутизна {np.percentile(G, 5):.4f}…{np.percentile(G, 95):.4f} на мм")
    save16(os.path.join(out, "peel.png"), [E, lg, 0.5 + 0.5 * du, 0.5 + 0.5 * dv])

    # ---------------------------------------------------------- рельеф краски
    # Бороздка в рельефе — только у основных трещин (волосяные — тоном); профиль мягкий, шире 3 пикселей карты,
    # иначе на косых линиях нормаль идёт ступеньками («молния»).
    groove = np.exp(-(e2 / (1.4 * hw2 + 0.35)) ** 2) * pres2
    brush = g.noise(1.1, 32.0) * 0.6 + g.noise(0.6, 9.0) * 0.4
    orange = g.noise(0.45)
    pits = smoothstep(2.6, 3.4, g.noise(0.35))
    # Куски старой краски — «подушки»: край скруглён в трещину, середина чуть выпуклая (где сетка видна).
    aged = pres2
    dome = np.sqrt(np.clip(e2 / np.maximum(r_in, 0.5), 0.0, 1.0)) * aged
    h_paint = (0.009 * brush + 0.004 * orange - 0.05 * pits
               + 0.2 * bevel + 0.12 * dome - 0.32 * groove)
    # Сглаживание на полпикселя перед нормалями — без лесенки на косых бороздках.
    pn = g.normal_from_height(g.blur(h_paint, 0.45), 1.0)
    save8(os.path.join(out, "paint_normal.png"), [0.5 + 0.5 * pn[..., 0], 0.5 + 0.5 * pn[..., 1], 0.5 + 0.5 * pn[..., 2]])
    cn = g.normal_from_height(g.blur(0.45 * cup, 0.3), 1.0)
    save8(os.path.join(out, "cup_normal.png"), [0.5 + 0.5 * cn[..., 0], 0.5 + 0.5 * cn[..., 1], 0.5 + 0.5 * cn[..., 2]])
    # Мелкие сколы (точки) — без загиба кромки: вокруг дырки в пару миллиметров валик не скатывается.
    nocurl = np.clip(g.blur(np.clip(spots, 0, 1), 1.5) * 6.0, 0, 1)
    save16(os.path.join(out, "paint_masks.png"),
           [np.clip(q / 4.0, 0, 1), np.clip(cup, 0, 1), rnd.astype(np.float32), nocurl])
    log("рельеф краски")

    # ---------------------------------------------------------- тон краски
    fade = 0.15 * g.noise(220) + 0.2 * g.noise(70)
    mottle = 0.22 * g.noise(9) + 0.18 * g.noise(2.5) + 0.12 * g.noise(0.6)
    strokes = 0.10 * g.noise(1.4, 45.0)
    # Грязь затекает в трещины и темнит краску у их краёв.
    halo = np.exp(-e2 / 1.3) * pres2
    tone = 0.5 + 0.16 * (fade + mottle + strokes) - 0.16 * halo - 0.2 * hair
    drips = smoothstep(0.9, 2.2, g.noise(2.6, 160.0) + 0.6 * g.noise(60)) * smoothstep(-0.4, 0.8, g.noise(300))
    # Разводы от протечек: пятно чуть темнее и тёмная кайма по краю высохшей воды.
    st = g.noise(70) + 0.45 * g.noise(18) + 0.15 * g.noise(4)
    tide = smoothstep(1.25, 1.3, st) * (1.0 - smoothstep(1.3, 1.55, st))
    drips = np.maximum(drips, np.maximum(0.7 * tide, 0.25 * smoothstep(1.28, 1.4, st)))
    specks = np.clip(smoothstep(2.7, 3.3, g.noise(0.28)) + 0.7 * smoothstep(2.9, 3.5, g.noise(0.6)), 0, 1)
    chalk = smoothstep(-0.2, 1.6, 0.5 * g.noise(60) + 0.6 * g.noise(12) + 0.3 * g.noise(3))
    save8(os.path.join(out, "paint_tone.png"), [tone, drips, specks, chalk])
    log("тон краски")

    # ---------------------------------------------------------- под краской
    putty = smoothstep(-0.6, 1.2, 0.8 * g.noise(14) + 0.5 * g.noise(4) + 0.3 * g.noise(60))
    old = smoothstep(0.0, 1.4, 0.8 * g.noise(35) + 0.45 * g.noise(6))
    grime = smoothstep(-0.8, 1.8, 0.7 * g.noise(40) + 0.4 * g.noise(8) + 0.3 * g.noise(1.5))
    curl = smoothstep(-0.3, 0.6, 0.85 * g.noise(5.5) + 0.35 * g.noise(1.6))
    save8(os.path.join(out, "under_masks.png"), [putty, old, grime, curl])
    log("маски под краской")

    # Нижние слои тоже рвутся кусками: своя мелкая сетка у старого слоя (~8 мм) и у шпаклёвки (~12 мм) —
    # ступенька каждого слоя идёт по трещинам, а не плавным контуром вдоль кромки краски.
    e4, id4, _ = g.cells(12.0, 0.35, 0.06)
    r3 = frac(np.sin(id3.astype(np.float64) * 7.233 + 1.7) * 43758.5453).astype(np.float32)
    r4 = frac(np.sin(id4.astype(np.float64) * 9.871 + 2.9) * 43758.5453).astype(np.float32)
    # A — гладкая часть поля отслоения (без кусков и сколов): по ней материал отличает кромку большого поля краски
    # от островков и одиночных дырок — загиб бывает только на первой.
    save8(os.path.join(out, "under_cells.png"), [r3, np.clip(e3 / 2.0, 0, 1), r4, rank(S)])
    log("куски нижних слоёв")

    for src, dst in (("painted_plaster_wall_diff_4k.jpg", "plaster_albedo.jpg"),
                     ("painted_plaster_wall_nor_gl_4k.jpg", "plaster_normal.jpg"),
                     ("painted_plaster_wall_rough_4k.jpg", "plaster_rough.jpg"),
                     ("painted_plaster_wall_disp_4k.jpg", "plaster_height.jpg")):
        target = os.path.join(out, dst)
        if not os.path.exists(target):
            shutil.copy2(os.path.join(PLASTER, src), target)

    if preview:
        pv = os.path.join(out, "_preview")
        os.makedirs(pv, exist_ok=True)
        k = n // 4
        crack = 1.0 - smoothstep(0.7, 1.3, q)
        save8(os.path.join(pv, "cracks.png"), [1.0 - crack[:k, :k]])
        for wv in (0.15, 0.35):
            m = (E[:k, :k] > wv).astype(np.float32)
            save8(os.path.join(pv, f"peel_{int(wv * 100)}.png"), [m * (1.0 - 0.8 * crack[:k, :k])])
        save8(os.path.join(pv, "tone.png"), [tone[:k, :k]])
    log(f"готово → {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=KIT)
    ap.add_argument("--size", type=int, default=4096)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    build(a.out, a.size, a.seed, a.preview)
