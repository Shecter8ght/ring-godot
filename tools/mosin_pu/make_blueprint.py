"""Подложка-«чертёж» из бокового снимка в координатах модели винтовки.

python -X utf8 tools/mosin_pu/make_blueprint.py

Источник: RIA 5039/265 (правая сторона, 4800 px). Привязка: дульный срез — 728,8 мм от казённого
среза, затылок (пятка) — 1232 мм от дула; ось канала — через середину ствола у дула и середину конуса
ствола у коробки (грибок курка на снимке частично закрыт гребнем приклада, по нему ось уходила).
Пишет trace/blueprint_right.png (4 px/мм, x −510…740, z −165…+100),
trace/blueprint_right_grid.png (с сеткой 10/50 мм) и trace/blueprint.json.
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ASSET = r"E:\Models Blender\WEAPONS\Мосин — винтовка и узлы"
SRC = os.path.join(ASSET, "refs", "web", "ria_5039_265", "265.jpg")
OUT = os.path.join(ASSET, "trace")
PX = 4.0                                  # px на мм подложки
X0, X1, Z0, Z1 = -510.0, 740.0, -165.0, 100.0
MUZZLE_X, OAL = 728.8, 1232.0
# измерено на снимке: крайние пиксели силуэта и две точки оси
SRC_MUZZLE, SRC_HEEL = 4708.0, 83.0
AXIS_A, AXIS_B = (4670.0, 514.0), (2160.0, 522.8)   # B — середина конуса ствола у коробки (Ø30,1→27,8)


def main():
    os.makedirs(OUT, exist_ok=True)
    im = Image.open(SRC).convert("RGB")
    k = (SRC_MUZZLE - SRC_HEEL) / OAL                     # px снимка на мм
    ang = np.arctan2(AXIS_A[1] - AXIS_B[1], AXIS_A[0] - AXIS_B[0])
    W, H = int((X1 - X0) * PX), int((Z1 - Z0) * PX)
    # обратное отображение: пиксель подложки → мм модели → пиксель снимка
    xs = X0 + (np.arange(W) + 0.5) / PX
    zs = Z1 - (np.arange(H) + 0.5) / PX
    XX, ZZ = np.meshgrid(xs, zs)
    # точка AXIS_A лежит на оси у дула; её x в мм модели
    ax_mm = MUZZLE_X - (SRC_MUZZLE - AXIS_A[0]) / k
    # вдоль оси — от AXIS_A, поперёк — вверх (y снимка растёт вниз)
    along = (XX - ax_mm) * k
    up = ZZ * k
    ca, sa = np.cos(ang), np.sin(ang)
    px = AXIS_A[0] + along * ca + up * sa
    py = AXIS_A[1] + along * sa - up * ca
    src = np.asarray(im)
    pxi = np.clip(np.round(px).astype(int), 0, src.shape[1] - 1)
    pyi = np.clip(np.round(py).astype(int), 0, src.shape[0] - 1)
    bp = src[pyi, pxi]
    Image.fromarray(bp).save(os.path.join(OUT, "blueprint_right.png"))
    g = Image.fromarray(bp.copy())
    d = ImageDraw.Draw(g)
    for xm in range(int(X0), int(X1) + 1, 10):
        x = (xm - X0) * PX
        major = xm % 50 == 0
        d.line([(x, 0), (x, H)], fill=(0, 255, 255) if major else (0, 120, 140), width=1)
        if major:
            d.text((x + 2, 2), str(xm), fill=(255, 255, 0))
            d.text((x + 2, H - 12), str(xm), fill=(255, 255, 0))
    for zm in range(int(Z0), int(Z1) + 1, 10):
        y = (Z1 - zm) * PX
        major = zm % 50 == 0
        d.line([(0, y), (W, y)], fill=(255, 0, 255) if zm == 0 else ((0, 255, 255) if major else (0, 120, 140)))
        if major:
            d.text((2, y + 2), str(zm), fill=(255, 255, 0))
    g.save(os.path.join(OUT, "blueprint_right_grid.png"))
    meta = {"px_per_mm": PX, "x0": X0, "x1": X1, "z0": Z0, "z1": Z1, "src": SRC, "src_px_per_mm": k,
            "axis_angle_deg": float(np.degrees(ang)), "origin_px": [(-X0) * PX, Z1 * PX]}
    json.dump(meta, open(os.path.join(OUT, "blueprint.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(meta, ensure_ascii=False))


main()
