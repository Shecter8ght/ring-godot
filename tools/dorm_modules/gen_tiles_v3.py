"""Плитка душевых 200 × 200 v03: карты для материала пола и стен (тайл 2 × 2 м = 10 × 10 плиток, 4096², бесшовно).

Как выглядит старая глазурованная плитка:
- каждая плитка положена чуть косо (±1°) и стоит на своей высоте — блики на стене ломаются по плиткам;
- кромка глазури скруглена, шов 3 мм утоплен, в нём грязь, у пола — чёрная плесень;
- глазурь местами в сетке волосяных трещин (цек), на части плиток — сквозная трещина с изломом;
- сколы угла и кромки до черепка, выбитые плитки — клей со следами зубчатого шпателя;
- потёки ржавчины и известковый налёт пятнами, разводы мыла.

  python -X utf8 tools/dorm_modules/gen_tiles_v3.py [папка] [--size 4096] [--seed 2611]

Выход (папка по умолчанию — textures/tiles_v3 комплекта модулей):
  tile_masks.png   16 бит RGBA: случайное плитки, расстояние до края плитки (мм / 8), сквозная трещина, скол;
  tile_normal.png  8 бит RGB, OpenGL: наклон плитки, скругление глазури, утопленный шов, трещина, скол;
  tile_tone.png    8 бит RGBA: тон глазури (0,5 — средний), цек, потёки ржавчины, известковый налёт;
  tile_glue.png    8 бит RGBA: гребни шпателя, тон клея, тон черепка, грязь и плесень в шве.
"""
import argparse
import gc
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_floor_maps import hash01  # noqa: E402
from gen_paint_v3 import Gen, save8, save16, smoothstep  # noqa: E402

KIT = "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures/tiles_v3"
COUNT, TILE_MM, GROUT_MM = 10, 200.0, 3.0


def build(out: str, n: int, seed: int) -> None:
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    g = Gen(n, seed)
    mm = g.mm
    rng = np.random.default_rng(seed)

    def log(msg):
        print(f"[{time.time() - t0:6.1f} с] {msg}", flush=True)

    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    x = xs / n * COUNT
    y = ys / n * COUNT
    tx, ty = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    u = (x - tx) * TILE_MM                      # мм внутри плитки
    v = (y - ty) * TILE_MM
    rid = hash01(tx, ty).astype(np.float32)
    r2 = hash01(ty + 3, tx + 11).astype(np.float32)
    r3 = hash01(tx + 29, ty + 7).astype(np.float32)
    r4 = hash01(ty + 41, tx + 59).astype(np.float32)
    del xs, ys, x, y
    gw = GROUT_MM / 2.0
    d = np.minimum(np.minimum(u, TILE_MM - u), np.minimum(v, TILE_MM - v))   # мм до оси шва
    de = d - gw                                                                 # мм до края глазури
    log("раскладка")

    # ---------------------------------------------------------- трещины и сколы — рисуем по плиткам
    crack = np.zeros((n, n), np.float32)
    chip = np.zeros((n, n), np.float32)
    px = n / COUNT
    for j in range(COUNT):
        for i in range(COUNT):
            x0, y0 = i * px, j * px
            # Сквозная трещина: от кромки к кромке с изломом и мелкой дрожью, иногда ветка.
            side = rng.integers(0, 2)
            a = rng.uniform(0.15, 0.85)
            b = rng.uniform(0.15, 0.85)
            k = rng.uniform(0.3, 0.7)
            kk = rng.uniform(0.25, 0.75)
            pts = []
            for t in np.linspace(0, 1, 40):
                base = a + (kk - a) * (t / k) if t < k else kk + (b - kk) * ((t - k) / (1 - k))
                wob = 0.006 * np.sin(t * 37 + i) + 0.003 * np.sin(t * 113 + j)
                pu, pv = (t, base + wob) if side else (base + wob, t)
                pts.append((x0 + pu * px, y0 + pv * px))
            p = (np.array(pts) * 16).astype(np.int32)
            cv2.polylines(crack, [p], False, 1.0, 1, cv2.LINE_AA, 4)
            if rng.random() < 0.4:
                t0b = int(len(pts) * k)
                q = np.array(pts[t0b:t0b + 1] * 1, np.float32)
                ang = rng.uniform(0, 2 * np.pi)
                ln = rng.uniform(0.15, 0.35) * px
                q2 = np.array([q[0], q[0] + [np.cos(ang) * ln * 0.5, np.sin(ang) * ln * 0.5],
                               q[0] + [np.cos(ang + 0.3) * ln, np.sin(ang + 0.3) * ln]])
                cv2.polylines(crack, [(q2 * 16).astype(np.int32)], False, 0.8, 1, cv2.LINE_AA, 4)
            # Скол: у угла или кромки, рваный многоугольник 8–35 мм.
            cx = rng.choice([0.0, 1.0]) if rng.random() < 0.7 else rng.uniform(0.2, 0.8)
            cy = rng.choice([0.0, 1.0]) if cx in (0.0, 1.0) else rng.choice([0.0, 1.0])
            rad = rng.uniform(8, 35) * mm
            angs = np.linspace(0, 2 * np.pi, 18, endpoint=False)
            rr = rad * (0.6 + 0.4 * rng.random(18))
            poly = np.stack([x0 + cx * px + np.cos(angs) * rr, y0 + cy * px + np.sin(angs) * rr], -1)
            poly[:, 0] = np.clip(poly[:, 0], x0, x0 + px)
            poly[:, 1] = np.clip(poly[:, 1], y0, y0 + px)
            cv2.fillPoly(chip, [(poly * 16).astype(np.int32)], 1.0, cv2.LINE_AA, 4)
    crack *= (de > 0.3)
    chip *= (de > -0.5)
    log("трещины и сколы")

    # ---------------------------------------------------------- рельеф: наклон плитки, глазурь, шов
    tilt_u = (r2 - 0.5) * 0.035                       # наклон ±1°
    tilt_v = (r3 - 0.5) * 0.035
    h_tile = 0.3 * (r4 - 0.5) + tilt_u * (u - TILE_MM / 2) + tilt_v * (v - TILE_MM / 2)
    round_ = np.clip(de / 1.2, 0.0, 1.0)
    round_ = np.sqrt(round_ * (2.0 - round_))
    glaze_wave = 0.01 * g.noise(25) + 0.004 * g.noise(6)
    h = np.where(de > 0, h_tile + 0.6 * round_ + glaze_wave, -0.8 + 0.05 * g.noise(1.0))
    chip_s = g.blur(chip, 0.4)
    h = h - 0.9 * chip_s * (de > 0) - 0.05 * crack
    tn = g.normal_from_height(g.blur(h, 0.4), 1.0)
    save8(os.path.join(out, "tile_normal.png"), [0.5 + 0.5 * tn[..., 0], 0.5 + 0.5 * tn[..., 1], 0.5 + 0.5 * tn[..., 2]])
    del h, h_tile, round_, glaze_wave, tn
    gc.collect()
    save16(os.path.join(out, "tile_masks.png"), [rid, np.clip(de / 8.0, 0, 1), np.clip(crack, 0, 1), np.clip(chip_s, 0, 1)])
    log("рельеф")

    # ---------------------------------------------------------- тон глазури, цек, ржавчина, известь
    tone = 0.5 + 0.18 * (r4 - 0.5) + 0.05 * g.noise(30) + 0.03 * g.noise(4)
    ec, _, _ = g.cells(9.0, 0.35, 0.06)
    craze_zone = smoothstep(0.3, 0.9, g.noise(90) + 0.6 * (rid - 0.5))
    craze = np.exp(-(ec / 0.45) ** 2) * craze_zone
    del ec
    # Потёки ржавчины: от редких источников (дюбель, шуруп, труба) вниз по стене 0,2–1 м, к низу шире и бледнее,
    # с подтёками-«пальцами»; v карты — вверх, строки картинки — вниз.
    rust = np.zeros((n, n), np.float32)
    for _ in range(22):
        x0, y0 = rng.uniform(0, n, 2)
        ln = rng.uniform(200, 1000) * mm
        w0, w1 = rng.uniform(2, 5) * mm, rng.uniform(10, 30) * mm
        a0 = rng.uniform(0.5, 0.95)
        fingers = rng.integers(1, 4)
        for fi in range(fingers):
            off = (fi - (fingers - 1) / 2) * w1 * 0.6
            ys_ = np.linspace(0, ln * rng.uniform(0.5, 1.0), 24)
            drift = np.cumsum(rng.normal(0, 0.8 * mm, 24))
            for k in range(23):
                t = ys_[k] / ln
                w = w0 + (w1 - w0) * t
                alpha = a0 * (1 - t) ** 1.3
                for ox in (-n, 0, n):
                    for oy in (-n, 0, n):
                        cx = x0 + off * t + drift[k] + ox
                        cy = y0 + ys_[k] + oy
                        if -w1 < cx < n + w1 and -ln < cy < n + ln:
                            p0 = (int(cx * 16), int(cy * 16))
                            p1 = (int((x0 + off * t + drift[k + 1] + ox) * 16), int((y0 + ys_[k + 1] + oy) * 16))
                            cv2.line(rust, p0, p1, float(alpha), max(1, int(w)), cv2.LINE_AA, 4)
    rust = np.clip(g.blur(rust, 1.5) * (0.75 + 0.25 * g.noise(3)) * 1.4, 0, 1)
    lime = smoothstep(0.6, 1.8, 0.7 * g.noise(50) + 0.4 * g.noise(12) + 0.2 * g.noise(2))
    save8(os.path.join(out, "tile_tone.png"), [tone, craze, rust, lime])
    log("тон")

    # ---------------------------------------------------------- клей, черепок, грязь в шве
    ang = np.floor(rid * 4) * 0.5
    ridges = 0.5 + 0.5 * np.sin((u * np.cos(ang) + v * np.sin(ang)) / 10.0 * 2 * np.pi + g.noise(6) * 0.8)
    glue_t = smoothstep(-1.5, 1.5, 0.6 * g.noise(20) + 0.4 * g.noise(3))
    biscuit = smoothstep(-1.5, 1.5, 0.5 * g.noise(5) + 0.5 * g.noise(1))
    gdirt = np.clip(smoothstep(-0.8, 1.6, 0.7 * g.noise(30) + 0.4 * g.noise(5)) * 0.7 + 0.3 * g.noise(1.0) * 0.5 + 0.3, 0, 1)
    save8(os.path.join(out, "tile_glue.png"), [ridges, glue_t, biscuit, gdirt])
    log(f"готово → {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=KIT)
    ap.add_argument("--size", type=int, default=4096)
    ap.add_argument("--seed", type=int, default=2611)
    a = ap.parse_args()
    build(a.out, a.size, a.seed)
