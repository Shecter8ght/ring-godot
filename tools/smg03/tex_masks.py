"""ИЗЛОМ-45, текстуры этап 1: маски набора Receiver по развёртке игровой сетки — без Painter и Blender.

    python -X utf8 tools/smg03/tex_masks.py
Берёт _asset_src/smg03/tex/Receiver_maps.npz и marks.json (tools/smg03/game_tex.py), пишет туда же в masks/:
  Receiver_upper.png — верх корпуса (металл под анодированием): область над линией шва корпуса — передний блок с нижней
                       планкой (X ≥ 22), выше Z 15 до проёма скобы и дальше назад, задний прилив (TANG); граница — по
                       середине канавки шва, край сглажен на ширину пикселя;
  Receiver_lower.png — остальное (полимер: шахта, спусковая коробка, рукоять, скоба, тяги);
  Receiver_red.png   — красная заливка меток предохранителя и переводчика (part_stamps.red_marks), обе стороны;
  Receiver_preview.png — всё вместе цветом (верх синий, низ серый, метки красные) — для глаза.
Точка пикселя проверяется со сдвигом внутрь детали вдоль нормали: днище коробки над проёмом скобы (Z 15, смотрит вниз),
низ переднего блока и стенки канавки шва попадают каждая на свою сторону.
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
PROF = json.loads((ROOT / 'tools/smg03/data/profiles.json').read_text(encoding='utf-8'))
HALF_W = float(re.search(r'^HALF_W = ([\d.]+)', (ROOT / 'tools/smg03/lib.py').read_text(encoding='utf-8'), re.M).group(1))
# задний прилив снизу коробки позади выреза за рукоятью — часть верха (tools/smg03/profiles.py: TANG_X, TANG_Z)
TANG_X, TANG_Z = -240.0, 8.0
FRONT_BLOCK_REAR_X = 22.0          # задняя грань переднего блока (lib.FRONT_BLOCK_REAR_X)
INSET_MM = 0.8                     # сдвиг точки внутрь детали вдоль нормали
EDGE_MM = 0.12                     # ширина сглаживания края (около пикселя развёртки)
RES = 10.0                         # пикс/мм растра областей (вид сбоку, XZ)
X0, X1, Z0, Z1 = -320.0, 140.0, -260.0, 110.0


def upper_polygon():
    """Верх корпуса на виде сбоку (мм): как «upper» в profiles.regions(), но с запасом наружу — сверху над планкой,
    спереди за торцом, сзади за торцом, снизу под передним блоком до низа нижней планки (шахта там уходит назад)."""
    p = PROF
    seam, seam_rear, step = p['seam_z'], p['seam_rear_z'], p['seam_step_x']
    front, rear = p['front_face_x'] + 20.0, p['rear_x'] - 30.0
    return [(front, 100.0), (front, -45.0), (FRONT_BLOCK_REAR_X, -45.0), (FRONT_BLOCK_REAR_X, seam), (step, seam),
            (step, seam_rear), (TANG_X, seam_rear), (TANG_X, TANG_Z), (rear, TANG_Z), (rear, 100.0)]


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


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = np.load(TEX / 'Receiver_maps.npz')
    pos, nrm, filled = d['pos'], d['nrm'].astype(np.float32), d['filled']
    size = pos.shape[0]
    q = pos - nrm * INSET_MM
    # верх / низ по линии шва
    sd = signed_distance(raster([upper_polygon()], X0, X1, Z0, Z1, RES), RES)
    up = np.clip(0.5 + sample(sd, q[..., 0], q[..., 2], X0, Z1, RES) / EDGE_MM, 0.0, 1.0)
    up[~filled] = 0.0
    low = np.where(filled, 1.0 - up, 0.0)
    # красные метки: лица букв на виде сбоку, со своей стороны и только у плоскости борта
    marks = json.loads((TEX / 'marks.json').read_text(encoding='utf-8'))
    red = np.zeros((size, size), np.float32)
    qr = pos - nrm * 0.15
    for side in (1, -1):
        tris = [t for m in marks if m['side'] == side for t in m['tris']]
        if not tris:
            continue
        xs = [p[0] for t in tris for p in t]
        zs = [p[1] for t in tris for p in t]
        bx0, bx1, bz0, bz1 = min(xs) - 2.0, max(xs) + 2.0, min(zs) - 2.0, max(zs) + 2.0
        r_res = 40.0
        img = raster(tris, bx0, bx1, bz0, bz1, r_res)
        sdr = signed_distance(img, r_res) + 0.1          # лицо буквы с фаской гравировки (0.1 мм наружу)
        near = filled & (side * pos[..., 1] > HALF_W - 1.0) & (qr[..., 0] > bx0) & (qr[..., 0] < bx1) & \
            (qr[..., 2] > bz0) & (qr[..., 2] < bz1)
        val = np.clip(0.5 + sample(sdr, qr[..., 0], qr[..., 2], bx0, bz1, r_res) / 0.08, 0.0, 1.0)
        red = np.maximum(red, np.where(near, val, 0.0))
    for name, a in (('upper', up), ('lower', low), ('red', red)):
        cv2.imwrite(str(OUT / f'Receiver_{name}.png'), np.round(a * 255).astype(np.uint8))
    prev = np.zeros((size, size, 3), np.float32)
    prev += up[..., None] * np.array([200, 120, 40], np.float32)       # BGR: синий
    prev += low[..., None] * np.array([110, 110, 110], np.float32)
    prev = prev * (1.0 - red[..., None]) + red[..., None] * np.array([30, 30, 230], np.float32)
    cv2.imwrite(str(OUT / 'Receiver_preview.png'), cv2.resize(prev.astype(np.uint8), (2048, 2048),
                                                               interpolation=cv2.INTER_AREA))
    n = filled.sum()
    print('MASKS', size, 'верх', round(float(up[filled].sum() / n), 3), 'низ', round(float(low[filled].sum() / n), 3),
          'красного, пикселей', int((red > 0.5).sum()), '→', OUT)


if __name__ == '__main__':
    main()
