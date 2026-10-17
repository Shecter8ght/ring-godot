"""Синтетические маски царапин для ложи Мосина (бесшовная плитка, настоящий масштаб).

python -X utf8 tools/mosin_pu/gen_wood_scratches.py
→ <библиотека>/textures/gen/wood_scratches_deep.png  — редкие царапины сквозь лак до волокна и задиры (плитка 400 мм)
→ <библиотека>/textures/gen/wood_scratches_fine.png  — волосяные царапины в самом лаке (плитка 250 мм)

Маски владельца из «09_Царапины» — плотные поля мелких рисок (хороши для металла); на дереве при отсечке они дают
россыпь точек. Здесь — отдельные штрихи: длина 4–70 мм, ширина 0,06–0,6 мм, почти прямые, концы сходят на нет,
направления в основном вдоль ложи (о снаряжение и при переноске), часть — вразброс. Рисунок синтетический, seed
фиксирован — карта воспроизводится.
"""
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path("E:/Models Blender/WEAPONS/Мосин — винтовка и узлы/textures/gen")


def scratch_map(size_px: int, tile_mm: float, count: int, length_mm, width_mm, along: float, seed: int,
                gouges: int = 0) -> Image.Image:
    """count штрихов; along — доля штрихов вдоль оси u (±25°), остальные — в любую сторону."""
    rnd = random.Random(seed)
    ss = 2                                         # сглаживание: рисуем вдвое крупнее
    big = size_px * ss
    k = big / tile_mm                               # пикселей на миллиметр
    acc = np.zeros((big, big), np.float32)
    for i in range(count + gouges):
        gouge = i >= count
        layer = Image.new("L", (big, big), 0)
        d = ImageDraw.Draw(layer)
        ln = rnd.uniform(*((6.0, 18.0) if gouge else length_mm)) * k
        w = rnd.uniform(*((0.5, 1.1) if gouge else width_mm)) * k
        if rnd.random() < along:
            ang = rnd.gauss(0.0, math.radians(14))
        else:
            ang = rnd.uniform(0, math.pi)
        bend = rnd.gauss(0.0, 0.05)                  # лёгкий изгиб: боковое отклонение середины, доля длины
        x0, y0 = rnd.uniform(0, big), rnd.uniform(0, big)
        strength = rnd.uniform(0.45, 1.0)
        n = max(12, int(ln / (0.6 * k)))            # шаг ~0,6 мм: без ступенек по длине
        pts = []
        for j in range(n + 1):
            t = j / n
            s = (t - 0.5) * ln
            off = bend * ln * (1 - (2 * t - 1) ** 2) * 0.5
            pts.append((x0 + s * math.cos(ang) - off * math.sin(ang), y0 + s * math.sin(ang) + off * math.cos(ang), t))
        for (xa, ya, ta), (xb, yb, tb) in zip(pts[:-1], pts[1:]):
            tm = (ta + tb) / 2
            taper = min(1.0, min(tm, 1 - tm) / 0.22) ** 0.7     # концы сходят на нет
            wid = max(1.0, w * (0.35 + 0.65 * taper))
            val = int(255 * strength * (0.25 + 0.75 * taper))
            for dx in (-big, 0, big):                           # бесшовно: копии за краями плитки
                for dy in (-big, 0, big):
                    d.line([(xa + dx, ya + dy), (xb + dx, yb + dy)], fill=val, width=int(round(wid)))
        acc = np.maximum(acc, np.asarray(layer, np.float32))
    img = Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8), "L")
    img = img.filter(ImageFilter.GaussianBlur(radius=0.6 * ss))
    return img.resize((size_px, size_px), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    deep = scratch_map(6144, 400.0, 170, (6.0, 70.0), (0.10, 0.45), 0.7, seed=1891, gouges=14)
    deep.save(OUT / "wood_scratches_deep.png", optimize=True)
    fine = scratch_map(4096, 250.0, 420, (4.0, 45.0), (0.05, 0.14), 0.55, seed=1930)
    fine.save(OUT / "wood_scratches_fine.png", optimize=True)
    (OUT / "README.txt").write_text(
        "Синтетические маски царапин ложи (tools/mosin_pu/gen_wood_scratches.py в репозитории RING, seed 1891/1930).\n"
        "wood_scratches_deep.png — 6144 px на плитку 400 мм (15,4 px/мм): 170 царапин 6–70 мм × 0,10–0,45 мм и 14 задиров.\n"
        "wood_scratches_fine.png — 4096 px на плитку 250 мм (16,4 px/мм): 420 волосяных царапин 4–45 мм × 0,05–0,14 мм.\n"
        "Собственные, не скан и не маски владельца.\n"
        "stamp_halo_Barrel.png, stamp_halo_Bolt_Body.png — ореолы копоти вокруг клейм; строит texture_mosin.py при сборке\n"
        "из сетки букв (48 px/мм, поле 32 мм), не этим скриптом.\n", encoding="utf-8")
    print("SCRATCHES done", OUT)


if __name__ == "__main__":
    main()
