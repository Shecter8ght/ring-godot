"""ИЗЛОМ-45, текстуры этап 1: маска красной заливки меток и гравировка надписей в карте нормалей — по развёртке
игровой сетки, без Painter и Blender.

    python -X utf8 tools/smg03/tex_masks.py
Берёт _asset_src/smg03/tex/<набор>_maps.npz (верх и низ корпуса) и marks.json (tools/smg03/game_tex.py), пишет туда же
в masks/: <набор>_red.png — красная заливка меток предохранителя и переводчика (part_stamps.red_marks), обе стороны, и
<набор>_preview.png — для глаза. Верх и низ корпуса с v2 — разные атласы (граница по шву — разрезом сетки в game_lp.py),
отдельных масок верха и низа больше нет. Метка попадает в набор той половины, на которой лежит.

Гравировка надписей (v3, владелец 05.11: «веер вокруг всех надписей»): у букв high-poly ровное дно и отвесные стенки
0.25–0.3 мм, и честная карта нормалей (normals/<набор>_normal.png из Blender, game_tex.py) показывает от них лишь фаску
в 1–2 пикселя. Буквы добавляются в неё по своим контурам (part_stamps.text_stamps — по ним же вырезаны): высота со скатом
края по фаске → нормаль в пространстве развёртки → смешение с запечённой (UDN). → normals/<набор>_normal_eng.png.
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
BEVEL_MM = 0.18                    # фаска верхней кромки букв (part_receiver: bevel_edges w=0.18)
RAMP_IN_MM = 0.1                   # скат до полной глубины — внутрь от стенки


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
        tris = [t for m in marks if m['side'] == side and m.get('red', True) for t in m['tris']]
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


def engrave_height(pos, nrm, filled, marks):
    """Высота гравировки (мм, ≤ 0) в каждом пикселе: по контурам букв своей стороны у плоскости борта; от края фаски
    (−BEVEL_MM снаружи стенки) до полной глубины (RAMP_IN_MM внутрь)."""
    h = np.zeros(pos.shape[:2], np.float32)
    q = pos - nrm * INSET_MM
    for m in marks:
        if not m['tris']:
            continue
        side, depth = m['side'], float(m.get('depth_mm', 0.25))
        xs = [p[0] for t in m['tris'] for p in t]
        zs = [p[1] for t in m['tris'] for p in t]
        bx0, bx1, bz0, bz1 = min(xs) - 2.0, max(xs) + 2.0, min(zs) - 2.0, max(zs) + 2.0
        near = filled & (side * pos[..., 1] > HALF_W - 1.0) & (q[..., 0] > bx0) & (q[..., 0] < bx1) & \
            (q[..., 2] > bz0) & (q[..., 2] < bz1)
        if not near.any():
            continue
        sd = signed_distance(raster(m['tris'], bx0, bx1, bz0, bz1, R_RES), R_RES)
        v = sample(sd, q[..., 0], q[..., 2], bx0, bz1, R_RES)
        k = np.clip((v + BEVEL_MM) / (BEVEL_MM + RAMP_IN_MM), 0.0, 1.0)
        h = np.minimum(h, np.where(near, -depth * k, 0.0))
    return h


def engrave_normal(n_base, pos, h):
    """Гравировка в карте нормалей: уклон высоты вдоль осей развёртки (мм на мм — шаг пикселя по карте положения) →
    нормаль в пространстве развёртки (OpenGL: X — вдоль u, Y — вдоль v, вверх по картинке), смешение UDN с запечённой.
    На стыке островов (соседний пиксель далеко в пространстве) уклон не считается."""
    hp = np.pad(h, 1, mode='edge')
    pp = np.pad(pos, ((1, 1), (1, 1), (0, 0)), mode='edge')
    du_mm = np.linalg.norm(pp[1:-1, 2:] - pp[1:-1, :-2], axis=-1)       # вдоль u (столбцы)
    dv_mm = np.linalg.norm(pp[:-2, 1:-1] - pp[2:, 1:-1], axis=-1)       # вдоль v (строка выше — больше v)
    gu = (hp[1:-1, 2:] - hp[1:-1, :-2]) / np.maximum(du_mm, 1e-4)
    gv = (hp[:-2, 1:-1] - hp[2:, 1:-1]) / np.maximum(dv_mm, 1e-4)
    step = np.median(du_mm[du_mm > 0]) if (du_mm > 0).any() else 0.2
    gu[du_mm > 4 * step] = 0.0
    gv[dv_mm > 4 * step] = 0.0
    n2 = np.dstack([-gu, -gv, np.ones_like(gu)])
    n2 /= np.linalg.norm(n2, axis=-1, keepdims=True)
    n = np.dstack([n_base[..., 0] + n2[..., 0], n_base[..., 1] + n2[..., 1], n_base[..., 2]])
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n


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
        base_p = TEX / 'normals' / f'{name}_normal.png'
        if base_p.exists():
            b = cv2.imread(str(base_p), cv2.IMREAD_UNCHANGED).astype(np.float32)[..., ::-1] / 65535.0 * 2.0 - 1.0
            h = engrave_height(pos, nrm, filled, marks)
            n = engrave_normal(b, pos, h)
            out = np.clip(np.round((n * 0.5 + 0.5)[..., ::-1] * 65535.0), 0, 65535).astype(np.uint16)
            cv2.imwrite(str(TEX / 'normals' / f'{name}_normal_eng.png'), out)
            print('ENGRAVE', name, 'пикселей букв', int((h < -0.01).sum()), '→', TEX / 'normals' / f'{name}_normal_eng.png')


if __name__ == '__main__':
    main()
