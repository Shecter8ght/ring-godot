"""Паркет «ёлочкой» v03: карты для материала пола общежития (тайл 2,1 × 2,1 м, 4096², бесшовно).

Раскладка — как в v02 (gen_floor_maps.py): планка 70 × 350 мм «лесенкой» вдоль осей, в материале повёрнута на 45°,
тайл = 30 ширин планки. Дерево — фотоскан шпона дуба Poly Haven oak_veneer_01 (CC0, 1,83 м): у каждой планки свой
кусок вдоль волокон, развёрнут или нет, свой оттенок. Как стареет штучный паркет под лаком:
- щели разной ширины (планки усохли по-разному), в щелях грязь; планки чуть выпуклые или прогнутые, на разной
  высоте, кромки скруглены; рельеф пор и годовых слоёв из тона шпона;
- лак: царапины всех направлений и длин, вмятины, разводы высохшей воды, затёртая грязь — материал по ним и по
  проходу вытирает лак;
- выбитые планки (материал по порогу случайного числа) — битумная мастика со следами гребёнки, прилипшие куски
  дерева и пыль; треснувшие — раскол вдоль волокон.

  python -X utf8 tools/dorm_modules/gen_floor_v3.py [папка] [--size 4096] [--seed 2610]

Выход (папка по умолчанию — textures/floor_v3 комплекта модулей):
  floor_wood.png   8 бит RGB (sRGB): дерево по планкам (без износа лака);
  floor_normal.png 8 бит RGB, OpenGL: высота планки, выпуклость, скругление кромок, щели, поры, вмятины;
  floor_masks.png  16 бит RGBA: случайное планки, расстояние до края планки (мм / 4), раскол вдоль волокон,
                   второе случайное планки;
  floor_wear.png   8 бит RGBA: царапины, вмятины, разводы воды, грязь;
  floor_mastic.png 8 бит RGBA: тон мастики, гребни шпателя, остатки дерева, пыль;
  floor_break.png  8 бит RGBA: отломанная часть планки (если она обломана), свежий излом у оставшейся части,
                   выбоина в лаке и верхнем слое, «плохое место» планки (одно число на планку, 0…1);
  floor_break_normal.png 8 бит RGB, OpenGL: рельеф выбоин и изломов (материал добавляет там, где они есть).
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

KIT = "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures/floor_v3"
OAK = "E:/Games/RING-godot/_asset_src/dorm_textures/ph_oak_veneer_01_4k/oak_veneer_01_diff_4k.jpg"
OAK_MM = 1830.0
TILE_MM = 2100.0
K, PERIOD, PLANK_W = 5, 30, 70.0


def layout(n: int):
    """Номер планки, её локальные координаты в мм (вдоль 0…350, поперёк 0…70) и ориентация."""
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    x = xs / n * PERIOD
    y = ys / n * PERIOD
    c = np.floor(x)
    yl = y - (c - K + 1)
    t = np.floor(yl / (2 * K))
    r = yl - 2 * K * t
    is_h = r < K
    m = np.floor(y) - 2 * K * t
    pid_a = np.mod(np.where(is_h, m, c), PERIOD).astype(np.int64)
    pid_b = np.mod(np.where(is_h, t * 2, t * 2 + 1), PERIOD // K).astype(np.int64)
    along = np.where(is_h, x - m, y - (c + 1 + 2 * K * t)) * PLANK_W
    across = np.where(is_h, y - (m + 2 * K * t), x - c) * PLANK_W
    return pid_a, pid_b, along.astype(np.float32), across.astype(np.float32), is_h


def draw_lines(n: int, rng, count: int, len_mm, mm: float, width_px, alpha):
    """Царапины: отрезки со сглаживанием, бесшовно (рисуем со сдвигами на тайл)."""
    canvas = np.zeros((n, n), np.float32)
    for _ in range(count):
        x0, y0 = rng.uniform(0, n, 2)
        ang = rng.uniform(0, np.pi)
        ln = rng.uniform(*len_mm) * mm
        bend = rng.uniform(-0.08, 0.08)
        a = float(rng.uniform(*alpha))
        w = int(rng.integers(width_px[0], width_px[1] + 1))
        pts = []
        for k in range(6):
            s = k / 5.0
            aa = ang + bend * (s - 0.5)
            pts.append((x0 + np.cos(aa) * ln * s, y0 + np.sin(aa) * ln * s))
        pts = np.array(pts)
        for ox in (-n, 0, n):
            for oy in (-n, 0, n):
                p = (pts + [ox, oy]) * 16
                if p[:, 0].max() < -16 * 8 or p[:, 0].min() > 16 * (n + 8) or p[:, 1].max() < -16 * 8 or p[:, 1].min() > 16 * (n + 8):
                    continue
                cv2.polylines(canvas, [p.astype(np.int32)], False, a, w, cv2.LINE_AA, 4)
    return np.clip(canvas, 0, 1)


def plank_hash(pidx, salt: float):
    """Случайное 0…1 планки (по номеру в тайле)."""
    ids = np.arange(PERIOD * PERIOD // K + PERIOD, dtype=np.float64)
    v = (np.sin(ids * 12.9898 + salt * 78.233) * 43758.5453) % 1.0
    return v.astype(np.float32)[pidx]


def hfrac(x, y, salt: float):
    return ((np.sin(x * 12.9898 + y * 78.233 + salt * 37.719) * 43758.5453) % 1.0).astype(np.float32)


def breaks(a, c, pidx, g, mm: float):
    """Маски облома планки (a — вдоль 0…350 мм, c — поперёк 0…70 мм): piece — отломанная часть (сквозь планку),
    fringe — свежий излом у оставшейся части, gouge — выбоина в лаке и верхнем слое, hb — их рельеф."""
    r_type = plank_hash(pidx, 1.1)
    r_pos = plank_hash(pidx, 2.3)
    r_side = plank_hash(pidx, 3.7)
    r_size = plank_hash(pidx, 4.9)
    r_end = plank_hash(pidx, 6.1)
    kind = np.floor(r_type * 4.0)
    pf = pidx.astype(np.float32)
    # Излом поперёк: зубья шириной 3–6 мм, длиной до 28 мм вдоль волокон, плюс плавный изгиб линии.
    tw = 3.0 + 3.0 * r_size
    ti = np.floor(c / tw)
    tri = 1.0 - np.abs(2.0 * (c / tw - ti) - 1.0)
    tlen = 6.0 + 22.0 * hfrac(ti, pf, 1.0)
    a0 = 50.0 + 250.0 * r_pos
    a_brk = a0 + 7.0 * np.sin(c * 0.09 + r_end * 6.28) + tlen * (tri - 0.5)
    end_side = r_side > 0.5
    cross = np.where(end_side, a > a_brk, a < a_brk)
    # Полоса вдоль: ширина 10–35 мм от одной кромки, на отрезке 60–250 мм, концы рваные.
    cw = 10.0 + 25.0 * r_size + 1.0 * np.sin(a * 0.04 + r_pos * 9.0) + 0.4 * np.sin(a * 0.23 + r_end * 5.0)
    side_c = np.where(end_side, c, 70.0 - c)
    s0 = 20.0 + 150.0 * r_end
    s1 = s0 + 60.0 + 190.0 * r_pos
    ej = 8.0 * hfrac(np.floor(c / 4.0), pf, 2.0)
    strip = (side_c < cw) & (a > s0 + ej) & (a < s1 - ej)
    # Угол: от торца La 25–110 мм, от кромки Lc 15–60 мм, край ломаный.
    da = np.where(r_end > 0.5, a, 350.0 - a)
    la = 25.0 + 85.0 * r_size
    lc = 15.0 + 45.0 * r_pos
    jag = 0.1 * np.sin(c * 0.5 + a * 0.13) + 0.12 * (tri - 0.5)
    corner = (da / la + side_c / lc) < (1.0 + jag)
    piece = np.where(kind == 0, cross, np.where(kind == 1, strip, np.where(kind == 2, corner, cross | strip)))
    piece = piece.astype(np.float32)
    del cross, strip, corner, da, side_c, a_brk, tri, ti, tlen, jag
    pa = g.blur(piece, 0.25)
    near = g.blur(piece, 1.4)
    fringe = np.clip(near * 3.0, 0, 1) * (1.0 - piece)
    # Выбоина в лаке и верхнем слое: вытянутая вдоль волокон, 20–80 × 4–14 мм, край рваный.
    ga = 30.0 + 290.0 * plank_hash(pidx, 8.3)
    gc_ = 8.0 + 54.0 * plank_hash(pidx, 9.7)
    gl = 10.0 + 30.0 * plank_hash(pidx, 10.9)
    gw = 2.0 + 5.0 * plank_hash(pidx, 12.1)
    fiber = g.noise(0.35, 6.0)
    d = ((a - ga) / gl) ** 2 + ((c - gc_) / gw) ** 2 + 0.35 * fiber + 0.25 * g.noise(1.5)
    gouge = np.clip(1.0 - d, 0.0, 1.0)
    gouge = np.clip(gouge * 5.0, 0.0, 1.0)
    # Рельеф: выбоина ниже на ~1 мм с волокнистым дном, у излома торчат занозы.
    hb = -0.9 * g.blur(gouge, 0.3) + 0.12 * gouge * fiber + 0.18 * fringe * fiber + 0.25 * fringe
    return pa, fringe, gouge, hb.astype(np.float32)


def build(out: str, n: int, seed: int) -> None:
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    g = Gen(n, seed)
    g.mm = n / TILE_MM
    mm = g.mm
    rng = np.random.default_rng(seed)

    def log(msg):
        print(f"[{time.time() - t0:6.1f} с] {msg}", flush=True)

    pid_a, pid_b, along, across, is_h = layout(n)
    rid = hash01(pid_a, pid_b).astype(np.float32)
    rid2 = hash01(pid_b + 17, pid_a + 5).astype(np.float32)
    rid3 = hash01(pid_a + 101, pid_b + 13).astype(np.float32)
    rid4 = hash01(pid_b + 211, pid_a + 37).astype(np.float32)
    rid5 = hash01(pid_a + 307, pid_b + 71).astype(np.float32)
    pidx = (pid_a + PERIOD * pid_b).astype(np.int32)                     # номер планки в тайле
    del pid_a, pid_b
    gc.collect()
    log("раскладка")

    # ---------------------------------------------------------- дерево: свой кусок шпона у каждой планки
    oak = cv2.imread(OAK, cv2.IMREAD_COLOR)[..., ::-1].astype(np.float32) / 255.0
    H, W = oak.shape[:2]
    s = W / OAK_MM
    flip = rid2 > 0.5
    a_mm = np.where(flip, 350.0 - along, along)
    c_mm = np.where(flip, 70.0 - across, across)
    # Паркет режут радиально: волокна прямые и частые — поперёк планки скан сжат в 2,4 раза.
    rows = np.mod(a_mm * s + rid3 * H, H).astype(np.float32)          # волокна вдоль строк скана
    cols = np.mod(c_mm * s * 2.4 + rid4 * W, W).astype(np.float32)
    wood = cv2.remap(oak, cols, rows, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    del oak, rows, cols, a_mm, c_mm
    gc.collect()
    lum = wood.mean(-1)
    # Оттенок планок: дуб из разных досок — светлее, темнее, теплее.
    tone = 0.78 + 0.34 * rid5
    warm = (rid3 - 0.5) * 0.08
    wood = wood * tone[..., None] * np.stack([1.0 + warm, np.ones_like(warm), 1.0 - warm], -1)
    save8(os.path.join(out, "floor_wood.png"), [wood[..., 0], wood[..., 1], wood[..., 2]])
    del wood
    gc.collect()
    log("дерево")

    # ---------------------------------------------------------- высота планок и щели
    gd = np.minimum(np.minimum(along, 350.0 - along), np.minimum(across, 70.0 - across))   # мм до края
    gw = 0.2 + 1.1 * rid5 ** 3                                           # усушка планки: своя щель
    bevel = np.clip((gd - gw) / 0.8, 0.0, 1.0)
    bevel = 1.0 - (1.0 - bevel) ** 2
    crown = (1.0 - ((2.0 * across / 70.0) - 1.0) ** 2) * (rid4 * 2.0 - 1.0) * 0.12
    level = (rid3 - 0.5) * 0.3
    grain = -(lum - g.blur(lum, 1.5)) * 0.25
    h = np.where(gd > gw, (level + crown) * bevel - 0.25 * (1.0 - bevel) + grain * bevel, -1.5)
    log("высота планок")

    # ---------------------------------------------------------- раскол вдоль волокон (у каждой планки свой)
    line = 35.0 + 18.0 * (rid2 - 0.5) + 0.9 * np.sin(along * 0.05 + rid * 6.3) + 0.25 * np.sin(along * 0.31 + rid3 * 9.0)
    a0 = 40.0 + rid * 120.0
    a1 = a0 + 80.0 + rid4 * 160.0
    seg = smoothstep(a0, a0 + 10.0, along) * (1.0 - smoothstep(a1 - 10.0, a1, along))
    split = np.exp(-((across - line) / 0.35) ** 2) * seg
    h = h - 0.4 * split

    # ---------------------------------------------------------- обломы: у каждой планки свой «как бы сломалась»
    # Какая планка в игре окажется обломанной, решает материал (доля — ползунок); здесь — форма облома:
    #  0 — конец отломан поперёк волокон: излом с зубьями-занозами, торчащими вдоль волокон;
    #  1 — отколота полоса вдоль волокон (по слою), с рваными концами;
    #  2 — отбит угол; 3 — конец и полоса вместе. Плюс у части планок лак с верхним слоем сорван выбоиной.
    piece, fringe, gouge, hb = breaks(along, across, pidx, g, mm)
    # «Плохие места» — одно число на планку (среднее гладкого шума ~0,4 м по планке): повреждения собираются
    # пятнами, а порог не режет планку посередине.
    from scipy import ndimage as ndi
    field = g.noise(170) + 0.4 * g.noise(60)
    nlab = int(pidx.max()) + 1
    per = np.asarray(ndi.mean(field, labels=pidx, index=np.arange(nlab)), np.float32)
    order = per.argsort()
    rk = np.empty(nlab, np.float32)
    rk[order] = np.linspace(0.0, 1.0, nlab, dtype=np.float32)
    cluster = rk[pidx]
    save8(os.path.join(out, "floor_break.png"), [piece, fringe, gouge, cluster])
    bn = g.normal_from_height(g.blur(hb, 0.35), 1.0)
    save8(os.path.join(out, "floor_break_normal.png"), [0.5 + 0.5 * bn[..., 0], 0.5 + 0.5 * bn[..., 1], 0.5 + 0.5 * bn[..., 2]])
    del piece, fringe, gouge, hb, bn, pidx
    gc.collect()
    log("обломы")

    # ---------------------------------------------------------- износ лака: царапины, вмятины, вода, грязь
    scratches = draw_lines(n, rng, 3500, (5, 40), mm, (1, 1), (0.1, 0.45))
    scratches = np.maximum(scratches, draw_lines(n, rng, 120, (60, 250), mm, (1, 1), (0.1, 0.4)))
    log("царапины")
    dents = np.clip(smoothstep(2.6, 3.3, g.noise(0.9)) + 0.6 * smoothstep(2.9, 3.6, g.noise(2.5)), 0, 1)
    st = g.noise(90) + 0.45 * g.noise(25) + 0.15 * g.noise(5)
    water = smoothstep(1.3, 1.4, st) * (1.0 - smoothstep(1.4, 1.75, st))
    water = g.blur(np.maximum(0.7 * water, 0.3 * smoothstep(1.38, 1.7, st)), 1.2)
    near_gap = np.exp(-np.maximum(gd - gw, 0.0) / 2.0)
    grime = np.clip(0.55 * near_gap + 0.45 * smoothstep(0.2, 1.8, 0.7 * g.noise(40) + 0.4 * g.noise(6)), 0, 1)
    save8(os.path.join(out, "floor_wear.png"), [scratches, dents, water, grime])
    h = h - 0.05 * dents - 0.006 * scratches
    del st, water, grime, near_gap
    gc.collect()
    log("износ")

    fn = g.normal_from_height(g.blur(h, 0.35), 1.0)
    save8(os.path.join(out, "floor_normal.png"), [0.5 + 0.5 * fn[..., 0], 0.5 + 0.5 * fn[..., 1], 0.5 + 0.5 * fn[..., 2]])
    del fn, h, lum, bevel, crown, level, grain
    gc.collect()
    save16(os.path.join(out, "floor_masks.png"), [rid, np.clip(gd / 4.0, 0, 1), np.clip(split, 0, 1), rid2])
    log("рельеф")

    # ---------------------------------------------------------- мастика под планками
    # Битум шпателем-гребёнкой: параллельные гребни, у каждой планки своя полоса и наклон; прилипшие куски
    # дерева и бумаги, пыль.
    ang = (rid3 - 0.5) * 0.6 + np.where(is_h, 0.0, np.pi / 2)
    ridge_pos = (along * np.cos(ang) + across * np.sin(ang)) / 6.0
    ridges = 0.5 + 0.5 * np.sin(ridge_pos * 2.0 * np.pi + g.noise(4.0) * 1.2)
    mastic_tone = smoothstep(-1.5, 1.5, 0.6 * g.noise(30) + 0.4 * g.noise(5))
    # Остатки: щепки дерева и клочки бумаги, мелко и редко.
    residue = smoothstep(1.7, 2.3, 0.6 * g.noise(4) + 0.5 * g.noise(1.2))
    dust = smoothstep(-0.5, 1.5, 0.7 * g.noise(60) + 0.4 * g.noise(10))
    save8(os.path.join(out, "floor_mastic.png"), [mastic_tone, ridges, residue, dust])
    log(f"готово → {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=KIT)
    ap.add_argument("--size", type=int, default=4096)
    ap.add_argument("--seed", type=int, default=2610)
    a = ap.parse_args()
    build(a.out, a.size, a.seed)
