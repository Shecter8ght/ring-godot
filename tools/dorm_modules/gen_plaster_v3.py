"""Побелка и штукатурка до кирпича, v03: карты для материала верха стен и потолка с живым износом
(тайл 2 × 2 м, 4096², бесшовно). Приёмы те же, что у краски v03 (gen_paint_v3.py).

Как стареет побелённая штукатурка:
- побелка (мел / известь, слоями) облетает мелкими чешуйками 5–15 мм — порядок облетания Ew с рваным краем, чешуйки
  у кромки отпадают целиком; толстая побелка местами растрескивается мелкой сеткой; под верхним слоем — старый
  с синькой (голубоватый), под ним штукатурка (фотоскан);
- штукатурка отваливается редко, крупными кусками с осыпающимся краем — порядок El; у края видна толщина слоя
  (~2 см) и тень на кирпиче; на кирпиче остатки раствора;
- длинные трещины штукатурки, разводы протечек с каймой, плесень пятнами точек, полосы от кисти.

  python -X utf8 tools/dorm_modules/gen_plaster_v3.py [папка] [--size 4096] [--seed 11]

Выход (папка по умолчанию — textures/plaster_v3 комплекта модулей):
  wash_peel.png    16 бит RGBA: Ew, log10 крутизны (на мм), направление крутизны x, y (0,5 + 0,5·n, ось v вверх);
  loss_peel.png    16 бит RGBA: El, log10 крутизны, направление x, y — то же для кусков штукатурки до кирпича;
  wash_masks.png   16 бит RGBA: сетка трещин побелки (расстояние в ширинах / 4), «блюдце» чешуйки, случайное чешуйки,
                   длинные трещины штукатурки (расстояние в ширинах / 4);
  wash_tone.png    8 бит RGBA: тон побелки (0,5 — средний), разводы протечек (кайма), плесень, просвет (тонкая побелка);
  wash_normal.png  8 бит RGB, OpenGL: мазки кисти, бугорки, бороздки сетки и длинных трещин;
  wash_cup_normal.png 8 бит RGB: подъём краёв чешуек при полном «блюдце»;
  loss_masks.png   8 бит RGBA: остатки раствора на кирпиче, ширина осыпающегося края, гладкая часть El (кромка
                   большого куска), гладкая часть Ew;
  brick_*.jpg      фотоскан кирпича Poly Haven red_bricks_04 (тайл 2,5 м — материал масштабирует).
"""
import argparse
import gc
import os
import shutil
import sys
import time

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_paint_v3 import Gen, frac, rank, save8, save16, smoothstep  # noqa: E402

KIT = "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures/plaster_v3"
BRICK = "E:/Games/RING-godot/_asset_src/dorm_textures/ph_red_bricks_04_4k"


def peel_field(g, S, jitter, spots, k_jit: float, k_spot: float):
    """Порядок облетания: гладкое поле + сдвиг на кусок + точки; крутизна — от гладкой части."""
    raw = S + k_jit * jitter - k_spot * np.clip(spots, 0.0, 1.0)
    E = rank(raw)
    Es = g.blur(rank(S), 1.0)
    gx, gy = g.grad(Es)
    G = np.sqrt(gx * gx + gy * gy) + 1e-7
    du, dv = gx / G, -gy / G
    lg = (np.log10(G) + 5.0) / 5.0
    return E, lg, du, dv, G


def build(out: str, n: int, seed: int) -> None:
    t0 = time.time()
    os.makedirs(out, exist_ok=True)
    g = Gen(n, seed)

    def log(msg):
        print(f"[{time.time() - t0:6.1f} с] {msg}", flush=True)

    # ---------------------------------------------------------- побелка: чешуйки и поле облетания
    ef, idf, kf = g.cells(9.0, 0.36, 0.06)          # чешуйки ~1 см
    rf = frac(np.sin(idf.astype(np.float64) * 12.9898 + 7.3) * 43758.5453).astype(np.float32)
    r_in = np.asarray(ndi.maximum(ef, labels=idf, index=np.arange(kf)), np.float32)[idf]
    log(f"чешуйки: {kf}")
    wx = g.noise(130) * 35 + g.noise(9) * 2.5
    wy = g.noise(130) * 35 + g.noise(9) * 2.5
    Sw = g.warp(g.noise(170) + 0.55 * g.noise(60), wx, wy) + 0.3 * g.noise(18) + 0.18 * g.noise(5)
    Sw = (Sw - Sw.mean()) / Sw.std()
    u = 2.0 * rf - 1.0
    jit_w = np.sign(u) * np.abs(u) ** 2.0
    spots_w = smoothstep(2.4, 3.2, g.noise(1.2)) + 0.6 * smoothstep(2.8, 3.5, g.noise(3.0))
    Ew, lgw, duw, dvw, _ = peel_field(g, Sw, jit_w, spots_w, 0.55, 1.0)
    save16(os.path.join(out, "wash_peel.png"), [Ew, lgw, 0.5 + 0.5 * duw, 0.5 + 0.5 * dvw])
    # Память: параллельно работают Painter и Blender других сессий — держим в памяти только нужное дальше.
    del idf, wx, wy, u, jit_w, spots_w, Ew, lgw, duw, dvw
    gc.collect()
    log("поле облетания побелки")

    # ---------------------------------------------------------- штукатурка: крупные куски до кирпича
    ec, idc, kc = g.cells(55.0, 0.4, 0.08)          # куски ~5–6 см, по ним крошится край
    rc = frac(np.sin(idc.astype(np.float64) * 9.3711 + 2.1) * 43758.5453).astype(np.float32)
    lx = g.noise(200) * 60 + g.noise(25) * 6
    ly = g.noise(200) * 60 + g.noise(25) * 6
    # Куски компактные: крупный шум главный, мелочь слабая — край рвётся по сетке кусков, а не россыпью дыр.
    Sl = g.warp(g.noise(260) + 0.45 * g.noise(90), lx, ly) + 0.12 * g.noise(30) + 0.05 * g.noise(8)
    Sl = (Sl - Sl.mean()) / Sl.std()
    u = 2.0 * rc - 1.0
    jit_l = np.sign(u) * np.abs(u) ** 1.6
    spots_l = smoothstep(2.9, 3.6, g.noise(6.0))
    El, lgl, dul, dvl, _ = peel_field(g, Sl, jit_l, spots_l, 0.16, 0.0)
    save16(os.path.join(out, "loss_peel.png"), [El, lgl, 0.5 + 0.5 * dul, 0.5 + 0.5 * dvl])
    del ec, idc, rc, lx, ly, u, jit_l, spots_l, El, lgl, dul, dvl
    gc.collect()
    log(f"куски штукатурки: {kc}")

    # ---------------------------------------------------------- трещины побелки и длинные трещины штукатурки
    zone = -0.6 * g.blur(Sw, 30) + 0.8 * g.noise(140)
    zone = (zone - zone.mean()) / zone.std()
    pres = smoothstep(0.2, 0.32, zone + 0.3 * g.noise(15))            # толстая побелка растрескалась
    hw = (0.32 + 0.06 * np.clip(g.noise(10), -1.5, 1.5)) * pres
    qw = ef / np.maximum(hw, 1e-3) + (1.0 - pres) * 50.0
    # Длинные трещины штукатурки: кромки крупных ячеек, участками, извилистые.
    el, _, _ = g.cells(380.0, 0.45, 0.06)
    seg = smoothstep(0.35, 0.6, 0.8 * g.noise(120) + 0.4 * g.noise(30))
    hl = (0.35 + 0.15 * np.clip(g.noise(40), -1.5, 1.5)) * seg
    ql = el / np.maximum(hl, 1e-3) + (1.0 - seg) * 50.0
    cupw = (1.0 - smoothstep(0.0, np.clip(0.4 * r_in, 1.0, 3.5), ef)) ** 1.5
    save16(os.path.join(out, "wash_masks.png"),
           [np.clip(qw / 4.0, 0, 1), np.clip(cupw, 0, 1), rf, np.clip(ql / 4.0, 0, 1)])
    del r_in, rf
    gc.collect()
    log("трещины")

    # ---------------------------------------------------------- рельеф побелки
    # Побелку наносят широкой кистью: полосы-валики вдоль мазка, бугорки, натёки на неровностях.
    # Широкая кисть: мазки 5–10 см во все стороны — слабые валики, без штриховки одного направления.
    brush = 0.5 * g.noise(14.0, 30.0) + 0.5 * g.noise(30.0, 12.0) + 0.3 * g.noise(1.0, 6.0)
    bumps = g.noise(0.7) * 0.5 + g.noise(2.5) * 0.5
    groove_w = np.exp(-(ef / (1.4 * np.maximum(hw, 0.05) + 0.35)) ** 2) * pres
    groove_l = np.exp(-(el / (1.4 * np.maximum(hl, 0.05) + 0.4)) ** 2) * seg
    h = 0.012 * brush + 0.012 * bumps - 0.12 * groove_w - 0.35 * groove_l
    wn = g.normal_from_height(g.blur(h, 0.45), 1.0)
    save8(os.path.join(out, "wash_normal.png"), [0.5 + 0.5 * wn[..., 0], 0.5 + 0.5 * wn[..., 1], 0.5 + 0.5 * wn[..., 2]])
    cn = g.normal_from_height(g.blur(0.3 * cupw, 0.3), 1.0)
    save8(os.path.join(out, "wash_cup_normal.png"), [0.5 + 0.5 * cn[..., 0], 0.5 + 0.5 * cn[..., 1], 0.5 + 0.5 * cn[..., 2]])
    del brush, bumps, groove_w, groove_l, h, wn, cn, cupw, ef, el, qw, ql
    gc.collect()
    log("рельеф побелки")

    # ---------------------------------------------------------- тон, разводы, плесень
    tone = 0.5 + 0.12 * (0.4 * g.noise(160) + 0.6 * g.noise(40) + 0.35 * g.noise(14, 30) + 0.35 * g.noise(30, 12)
                         + 0.3 * g.noise(1.5))
    # Протечки: пятно темнее, кайма высохшей воды по краю, местами вертикальный потёк.
    st = g.noise(110) + 0.45 * g.noise(30) + 0.15 * g.noise(6)
    tide = smoothstep(1.2, 1.26, st) * (1.0 - smoothstep(1.26, 1.5, st))
    stain = np.maximum(0.8 * tide, 0.35 * smoothstep(1.24, 1.5, st))
    stain = np.maximum(stain, 0.3 * smoothstep(1.5, 2.4, g.noise(4.0, 140.0) + 0.7 * g.noise(80)))
    # Плесень: колонии из точек — пятно-область, внутри густые точки разного размера.
    colony = smoothstep(0.6, 1.6, g.noise(70) + 0.5 * g.noise(20))
    dots = np.clip(smoothstep(1.4, 2.4, g.noise(0.5)) + smoothstep(1.8, 2.8, g.noise(1.4)), 0, 1)
    mold = np.clip(colony * (0.25 + dots), 0, 1)
    # Просвет: тонкая побелка у кисти — сквозь неё видна штукатурка.
    thin = smoothstep(0.6, 1.8, 0.6 * g.noise(25) + 0.5 * g.noise(10, 30))
    save8(os.path.join(out, "wash_tone.png"), [tone, stain, mold, thin])
    log("тон, протечки, плесень")

    # ---------------------------------------------------------- кирпич: остатки раствора, край
    residue = smoothstep(0.1, 1.3, 0.7 * g.noise(25) + 0.4 * g.noise(6) + 0.3 * g.noise(1.5))
    crumble = smoothstep(-1.0, 1.5, 0.7 * g.noise(12) + 0.5 * g.noise(3))
    save8(os.path.join(out, "loss_masks.png"), [residue, crumble, rank(Sl), rank(Sw)])
    log("кирпич")

    for src, dst in (("red_bricks_04_diff_4k.jpg", "brick_albedo.jpg"),
                     ("red_bricks_04_nor_gl_4k.jpg", "brick_normal.jpg"),
                     ("red_bricks_04_rough_4k.jpg", "brick_rough.jpg")):
        target = os.path.join(out, dst)
        if not os.path.exists(target):
            shutil.copy2(os.path.join(BRICK, src), target)
    log(f"готово → {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out", nargs="?", default=KIT)
    ap.add_argument("--size", type=int, default=4096)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    build(a.out, a.size, a.seed)
