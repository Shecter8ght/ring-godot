"""ИЗЛОМ-45, текстуры этап 1: маска красной заливки меток по развёртке игровой сетки — без Painter и Blender.

    python -X utf8 tools/smg03/tex_masks.py
Берёт _asset_src/smg03/tex/<набор>_maps.npz (верх и низ корпуса) и marks.json (tools/smg03/game_tex.py), пишет туда же
в masks/: <набор>_red.png — красная заливка меток предохранителя и переводчика (part_stamps.red_marks), обе стороны, и
<набор>_preview.png — для глаза. Верх и низ корпуса с v2 — разные атласы (граница по шву — разрезом сетки в game_lp.py),
отдельных масок верха и низа больше нет. Метка попадает в набор той половины, на которой лежит.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / '_asset_src/smg03/tex'
OUT = TEX / 'masks'
SETS = ('Upper', 'Lower')
HALF_W = float(re.search(r'^HALF_W = ([\d.]+)', (ROOT / 'tools/smg03/lib.py').read_text(encoding='utf-8'), re.M).group(1))
R_RES = 40.0                       # пикс/мм растра букв
GROW_MM = 0.1                      # лицо буквы с фаской гравировки — наружу
INSET_MM = 0.15                    # точка пикселя — чуть внутрь детали (дно канавки)
EDGE_MM = 0.08                     # сглаживание края заливки


def raster(polys, x0, x1, z0, z1, res):
    h, w = int(round((z1 - z0) * res)), int(round((x1 - x0) * res))
    img = np.zeros((h, w), np.uint8)
    pts = [np.array([[(x - x0) * res, (z1 - z) * res] for x, z in poly], np.float64) for poly in polys]
    cv2.fillPoly(img, [np.round(p * 16).astype(np.int32) for p in pts], 255, lineType=cv2.LINE_8, shift=4)
    return img


def signed_distance(img, res):
    """Расстояние до края области в мм: внутри «+», снаружи «−»."""
    inside = cv2.distanceTransform((img > 0).astype(np.uint8), cv2.DIST_L2, 5)
    outside = cv2.distanceTransform((img == 0).astype(np.uint8), cv2.DIST_L2, 5)
    return (inside - outside) / res


def sample(field, x, z, x0, z1, res):
    """Значение поля в точках (x, z) мм — билинейно."""
    u = ((x - x0) * res - 0.5).astype(np.float32)
    v = ((z1 - z) * res - 0.5).astype(np.float32)
    return cv2.remap(field.astype(np.float32), u, v, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def red_mask(pos, nrm, filled, marks):
    """Лица букв на виде сбоку, со своей стороны и только у плоскости борта."""
    red = np.zeros(pos.shape[:2], np.float32)
    q = pos - nrm * INSET_MM
    for side in (1, -1):
        tris = [t for m in marks if m['side'] == side for t in m['tris']]
        if not tris:
            continue
        xs = [p[0] for t in tris for p in t]
        zs = [p[1] for t in tris for p in t]
        bx0, bx1, bz0, bz1 = min(xs) - 2.0, max(xs) + 2.0, min(zs) - 2.0, max(zs) + 2.0
        sd = signed_distance(raster(tris, bx0, bx1, bz0, bz1, R_RES), R_RES) + GROW_MM
        near = filled & (side * pos[..., 1] > HALF_W - 1.0) & (q[..., 0] > bx0) & (q[..., 0] < bx1) & \
            (q[..., 2] > bz0) & (q[..., 2] < bz1)
        val = np.clip(0.5 + sample(sd, q[..., 0], q[..., 2], bx0, bz1, R_RES) / EDGE_MM, 0.0, 1.0)
        red = np.maximum(red, np.where(near, val, 0.0))
    return red


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    marks = json.loads((TEX / 'marks.json').read_text(encoding='utf-8'))
    for name in SETS:
        d = np.load(TEX / f'{name}_maps.npz')
        pos, nrm, filled = d['pos'], d['nrm'].astype(np.float32), d['filled']
        red = red_mask(pos, nrm, filled, marks)
        cv2.imwrite(str(OUT / f'{name}_red.png'), np.round(red * 255).astype(np.uint8))
        prev = np.where(filled[..., None], np.array([110, 110, 110], np.float32), 0.0)
        prev = prev * (1.0 - red[..., None]) + red[..., None] * np.array([30, 30, 230], np.float32)
        cv2.imwrite(str(OUT / f'{name}_preview.png'), cv2.resize(prev.astype(np.uint8), (2048, 2048),
                                                                 interpolation=cv2.INTER_AREA))
        print('MASK', name, pos.shape[0], 'красного, пикселей', int((red > 0.5).sum()), '→', OUT)


if __name__ == '__main__':
    main()
