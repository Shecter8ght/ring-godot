"""Карты крови для BloodFx (assets/textures/blood): как растекается лужа, как стекают подтёки,
какой след оставляет капля. Собственные процедурные текстуры, без внешних источников.

Лужа — симуляция растекания по шероховатой поверхности (инвазивная перколяция): жидкость каждый
шаг занимает ту соседнюю клетку фронта, куда ей «проще» затечь, — порог клетки складывается из
шероховатости (шум нескольких масштабов), давления (дальше от источника — труднее) и уклона
(вниз — легче). Порядок, в котором клетки намокли, и есть время прихода фронта: шейдер
blood_decal проявляет лужу по нему, видеокарта ничего не считает.

pools.png  1024×512, клетки 256: верхний ряд — ровная поверхность, нижний — уклон (течёт к +v).
drips.png  512×256, клетки 128×256: подтёки на стене — пятно и струйки вниз (к +v) с каплей на конце.
  R — когда сюда придёт кровь (0 — сразу, 1 — никогда), G — толщина слоя, B — мелкая неровность.
spatter_N.png / spatter_N_n.png — следы капель для Decal: 0–3 упала отвесно (венчик и брызги),
  4–7 вскользь (эллипс с хвостом по ходу полёта к +x и отлетевшая капля). RGB — толщина (толще —
  темнее), A — где кровь; _n — нормали от толщины (блик по краю капли).

python tools/gen_blood_maps.py   (numpy, scipy, Pillow), затем tools/godot.cmd --headless --import
"""

import heapq
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "textures", "blood")


def fbm(rng, size, octaves, base=4, gain=0.55):
    """Шум нескольких масштабов 0..1, size = (h, w)."""
    h, w = size
    out = np.zeros(size, dtype=np.float64)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        cells = base * (2 ** o)
        g = rng.random((max(2, int(cells * h / max(h, w))) + 1, max(2, int(cells * w / max(h, w))) + 1))
        img = Image.fromarray((g * 65535).astype(np.uint16)).convert("I").convert("F")
        layer = np.asarray(img.resize((w, h), Image.BICUBIC), dtype=np.float64) / 65535.0
        out += layer * amp
        total += amp
        amp *= gain
    out /= total
    out -= out.min()
    out /= max(out.max(), 1e-6)
    return out


def percolate(prio, seeds, n_target, margin):
    """Инвазивная перколяция от seeds: каждый шаг — клетка фронта с наименьшим порогом.
    Возвращает порядок намокания (0..1, 1 — сухо) и маску."""
    h, w = prio.shape
    order = np.full((h, w), -1, dtype=np.int64)
    queued = np.zeros((h, w), dtype=bool)
    heap = []
    for (y, x) in seeds:
        heapq.heappush(heap, (prio[y, x], y, x))
        queued[y, x] = True
    n = 0
    while heap and n < n_target:
        _, y, x = heapq.heappop(heap)
        if y < margin or x < margin or y >= h - margin or x >= w - margin:
            continue
        order[y, x] = n
        n += 1
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w and not queued[yy, xx]:
                queued[yy, xx] = True
                heapq.heappush(heap, (prio[yy, xx], yy, xx))
    mask = order >= 0
    arrival = np.where(mask, order / max(n - 1, 1), 1.0)
    return arrival, mask


def thickness_from(mask, arrival, rng, clot):
    """Толщина: у края — тонкая плёнка (мениск), к середине и к источнику — толще; сгустки."""
    dist = ndimage.distance_transform_edt(mask)
    edge = np.clip(dist / 9.0, 0.0, 1.0) ** 0.6
    th = edge * (0.5 + 0.5 * (1.0 - arrival) ** 0.7)
    th *= 0.85 + 0.3 * clot
    th = ndimage.gaussian_filter(th, 1.2)
    return np.clip(np.where(mask, th, 0.0), 0.0, 1.0)


def pool(rng, size, slope):
    h = w = size
    rough = fbm(rng, (h, w), 5, base=3, gain=0.6)
    fine = fbm(rng, (h, w), 3, base=24, gain=0.5)
    cy, cx = (int(h * 0.24), w // 2) if slope > 0 else (h // 2, w // 2)
    yy, xx = np.mgrid[0:h, 0:w]
    r0 = size * 0.36
    # порог: шероховатость + давление (дальше от источника — труднее); на уклоне вниз (к +y)
    # «расстояние» короче, вверх — длиннее: лужа вытягивается языком вниз, но не убегает
    dy = (yy - cy).astype(np.float64)
    if slope > 0:
        dy = np.where(dy > 0, dy / (1.0 + slope * 1.6), dy * (1.0 + slope))
    d = np.hypot(dy, (xx - cx) * (1.0 + 0.25 * slope)) / r0
    prio = rough * 1.0 + fine * 0.22 + d * 1.5
    seeds = [(cy + dy, cx + dx) for dy in range(-3, 4) for dx in range(-3, 4) if dy * dy + dx * dx <= 9]
    arrival, mask = percolate(prio, seeds, int(h * w * (0.42 if slope <= 0 else 0.3)), 6)
    # шум ступенек порядка сглаживаем — фронт идёт ровно, края остаются рваными
    arrival = np.where(mask, ndimage.gaussian_filter(arrival, 1.0), 1.0)
    clot = fbm(rng, (h, w), 3, base=10)
    th = thickness_from(mask, arrival, rng, clot)
    return arrival, th, fbm(rng, (h, w), 2, base=32)


def drips(rng, w, h):
    yy, xx = np.mgrid[0:h, 0:w]
    arrival = np.ones((h, w))
    th = np.zeros((h, w))
    # пятно, откуда стекает: маленькая лужица перколяцией
    cy, cx = 22, w // 2 + int(rng.integers(-8, 9))
    rough = fbm(rng, (h, w), 4, base=4)
    blob_r = rng.uniform(9.0, 14.0)
    prio = rough + np.hypot(yy - cy, (xx - cx) * 0.8) / blob_r * 1.6
    seeds = [(cy, cx)]
    a_blob, m_blob = percolate(prio, seeds, int(np.pi * blob_r * blob_r * 1.1), 3)
    blob_t = 0.12
    arrival = np.where(m_blob, a_blob * blob_t, arrival)
    rows = np.where(m_blob.any(axis=1))[0]
    bottom = rows.max() if len(rows) else cy + 8
    cols = np.where(m_blob[bottom - 2:bottom + 1].any(axis=0))[0]
    n_riv = int(rng.integers(2, 5))
    for i in range(n_riv):
        x0 = float(rng.choice(cols)) if len(cols) else float(cx)
        y0 = float(bottom - 2)
        length = rng.uniform(60.0, h - y0 - 14.0) if i == 0 else rng.uniform(24.0, h - y0 - 14.0)
        end_k = 1.0 if i == 0 else rng.uniform(0.45, 1.0)
        w0 = rng.uniform(2.2, 4.2) if i == 0 else rng.uniform(1.5, 3.2)
        amp = rng.uniform(0.5, 2.5)
        freq = rng.uniform(0.03, 0.09)
        ph = rng.uniform(0, 6.28)
        walk = 0.0
        steps = int(length)
        for s in range(steps):
            k = s / max(steps - 1, 1)
            y = y0 + s
            walk += rng.normal(0.0, 0.18)
            x = x0 + amp * np.sin(y * freq + ph) + walk
            ww = w0 * (1.0 - 0.35 * k)
            t = blob_t + (1.0 - blob_t) * end_k * k ** 1.7
            y_lo, y_hi = int(y) - 1, int(y) + 2
            x_lo, x_hi = int(x - ww) - 1, int(x + ww) + 2
            for py in range(max(y_lo, 0), min(y_hi, h)):
                for px in range(max(x_lo, 0), min(x_hi, w)):
                    dd = abs(px - x) / ww
                    if dd <= 1.0 and abs(py - y) <= 1.0:
                        arrival[py, px] = min(arrival[py, px], t)
                        th[py, px] = max(th[py, px], (1.0 - dd * dd) * (0.55 + 0.25 * (1.0 - k)))
        # капля на конце: толще, круглая
        bx = x0 + amp * np.sin((y0 + steps) * freq + ph) + walk
        by = y0 + steps
        br = w0 * 1.35
        dist = np.hypot(yy - by, xx - bx) / br
        bead = dist <= 1.0
        t_end = blob_t + (1.0 - blob_t) * end_k
        arrival = np.where(bead, np.minimum(arrival, t_end), arrival)
        th = np.where(bead, np.maximum(th, (1.0 - dist ** 2) * 0.95), th)
    clot = fbm(rng, (h, w), 3, base=10)
    th_blob = thickness_from(m_blob, a_blob * blob_t, rng, clot)
    th = np.maximum(th, th_blob)
    mask = arrival < 1.0
    arrival = np.where(mask, ndimage.gaussian_filter(arrival, 0.6), 1.0)
    th = ndimage.gaussian_filter(th, 0.7)
    return arrival, np.clip(th, 0.0, 1.0), fbm(rng, (h, w), 2, base=24)


def spatter(rng, size, oblique):
    """След капли: A — где кровь, толщина — для оттенка и нормалей."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    c = size / 2.0
    cov = np.zeros((size, size))
    hgt = np.zeros((size, size))

    def disc(cx, cy, r, sx=1.0, height=1.0):
        d = np.hypot((xx - cx) / sx, yy - cy) / max(r, 0.5)
        m = np.clip(1.0 - d, 0.0, 1.0)
        prof = np.sqrt(np.clip(1.0 - d * d, 0.0, 1.0)) * height
        np.maximum(hgt, prof, out=hgt)
        np.maximum(cov, (d <= 1.0).astype(np.float64), out=cov)
        return m

    ang = np.arctan2(yy - c, xx - c)
    if not oblique:
        r0 = size * rng.uniform(0.16, 0.22)
        # венчик: край с зубцами и шипами
        n_sp = int(rng.integers(10, 19))
        edge = np.ones_like(ang)
        for _ in range(n_sp):
            a = rng.uniform(-np.pi, np.pi)
            ln = rng.uniform(0.08, 0.45)
            wdt = rng.uniform(0.05, 0.12)
            da = np.angle(np.exp(1j * (ang - a)))
            edge += ln * np.exp(-(da / wdt) ** 2)
            if rng.random() < 0.7:
                rr = r0 * (1.0 + ln + rng.uniform(0.25, 0.9))
                disc(c + np.cos(a) * rr, c + np.sin(a) * rr, rng.uniform(0.8, 2.6))
        edge += (fbm(rng, (size, size), 3, base=6) - 0.5) * 0.15
        d = np.hypot(xx - c, yy - c) / (r0 * edge)
        main = d <= 1.0
        np.maximum(cov, main.astype(np.float64), out=cov)
        np.maximum(hgt, np.sqrt(np.clip(1.0 - d * d, 0.0, 1.0)) * 0.8, out=hgt)
        for _ in range(int(rng.integers(4, 12))):
            a = rng.uniform(-np.pi, np.pi)
            rr = r0 * rng.uniform(1.5, 2.3)
            disc(c + np.cos(a) * rr, c + np.sin(a) * rr, rng.uniform(0.6, 2.0))
    else:
        # эллипс сдвинут назад, хвост и отлетевшая капля — по ходу (+x)
        ratio = rng.uniform(1.6, 2.6)
        r0 = size * rng.uniform(0.1, 0.14)
        ex = c - r0 * ratio * 0.6
        edge = 1.0 + (fbm(rng, (size, size), 3, base=6) - 0.5) * 0.12
        d = np.hypot((xx - ex) / ratio, yy - c) / (r0 * edge)
        np.maximum(cov, (d <= 1.0).astype(np.float64), out=cov)
        np.maximum(hgt, np.sqrt(np.clip(1.0 - d * d, 0.0, 1.0)) * 0.75, out=hgt)
        # хвост: сужается от края эллипса вперёд
        tail_len = r0 * rng.uniform(1.3, 2.4)
        x_start = ex + r0 * ratio * 0.85
        k = np.clip((xx - x_start) / tail_len, 0.0, 1.0)
        half = r0 * 0.55 * (1.0 - k) ** 1.4 + 0.4
        tail = (xx >= x_start - 2) & (xx <= x_start + tail_len) & (np.abs(yy - c) <= half)
        np.maximum(cov, tail.astype(np.float64), out=cov)
        np.maximum(hgt, np.where(tail, 0.45 * (1.0 - k), 0.0), out=hgt)
        disc(x_start + tail_len + r0 * rng.uniform(0.4, 1.0), c + rng.normal(0, 1.2), r0 * rng.uniform(0.25, 0.45), 1.3, 0.8)
        for _ in range(int(rng.integers(2, 6))):
            disc(x_start + rng.uniform(0.0, tail_len * 1.8), c + rng.normal(0, r0 * 0.9), rng.uniform(0.5, 1.6))
    cov = ndimage.gaussian_filter(cov, 0.6)
    hgt = ndimage.gaussian_filter(hgt, 0.8)
    shade = 1.0 - 0.5 * np.clip(hgt, 0.0, 1.0)
    # нормали от толщины: блик по краю капли
    gy, gx = np.gradient(hgt * 2.2)
    n = np.dstack([-gx, -gy, np.ones_like(gx)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    alb = np.dstack([shade, shade, shade, np.clip(cov, 0.0, 1.0)])
    nrm = np.dstack([n[..., 0] * 0.5 + 0.5, -n[..., 1] * 0.5 + 0.5, n[..., 2] * 0.5 + 0.5])
    return alb, nrm


def to8(a):
    return (np.clip(a, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(int(sys.argv[1]) if len(sys.argv) > 1 else 20261015)
    cell = 256
    atlas = np.zeros((cell * 2, cell * 4, 4), dtype=np.uint8)
    for row, slope in enumerate((0.0, 1.15)):
        for col in range(4):
            arr, th, nz = pool(rng, cell, slope)
            atlas[row * cell:(row + 1) * cell, col * cell:(col + 1) * cell] = np.dstack([to8(arr), to8(th), to8(nz), np.full_like(to8(th), 255)])
            print("лужа", row, col, "покрыто %.0f %%" % (100.0 * (arr < 1.0).mean()))
    Image.fromarray(atlas, "RGBA").save(os.path.join(OUT, "pools.png"))
    dw, dh = 128, 256
    datlas = np.zeros((dh, dw * 4, 4), dtype=np.uint8)
    for col in range(4):
        arr, th, nz = drips(rng, dw, dh)
        datlas[:, col * dw:(col + 1) * dw] = np.dstack([to8(arr), to8(th), to8(nz), np.full_like(to8(th), 255)])
        print("подтёк", col)
    Image.fromarray(datlas, "RGBA").save(os.path.join(OUT, "drips.png"))
    for i in range(8):
        alb, nrm = spatter(rng, 128, i >= 4)
        Image.fromarray(to8(alb), "RGBA").save(os.path.join(OUT, "spatter_%d.png" % i))
        Image.fromarray(to8(nrm), "RGB").save(os.path.join(OUT, "spatter_%d_n.png" % i))
        print("след капли", i)
    # общая ORM для следов: гладкая блестящая плёнка (смешивается по альфе следа)
    orm = np.zeros((8, 8, 3), dtype=np.uint8)
    orm[..., 0] = 255
    orm[..., 1] = 26
    Image.fromarray(orm, "RGB").save(os.path.join(OUT, "spatter_orm.png"))
    print("готово:", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
