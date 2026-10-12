"""Physically scaled casting pores and rubbed paint from the owner's photos.

Reference photographs guide appearance only. Every pixel here is original.
"""
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_asset_src/grenade_codex'
MASKS = OUT / 'textures/authoring'
N = 8192
EXTENT = 160.0
RNG = np.random.default_rng(12010262)
manifest = []
SOFT = '--soft' in sys.argv


def save(arr, name, purpose, depth=None):
    path = MASKS / name
    if arr.dtype == np.float32:
        encoded = np.clip(arr * 65535, 0, 65535).astype(np.uint16)
    else:
        encoded = arr
    Image.fromarray(encoded).save(path, compress_level=6)
    manifest.append({'file': name, 'size': [N, N],
                     'physical_extent_mm': EXTENT, 'purpose': purpose,
                     'height_distance_mm': depth,
                     'source': 'Original synthetic mask, Codex, 2026-10-12',
                     'color_space': 'Non-Color',
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    print('PITTING_MASK_OK', name, flush=True)


def irregular_patch(canvas, cx, cy, radius, aspect, depth, kind='pit'):
    """A local asymmetrical depression; no spherical repeating stamps."""
    rx, ry = radius * N / EXTENT, radius * aspect * N / EXTENT
    angle = RNG.uniform(0, math.tau)
    bound = int(max(rx, ry) * 1.5 + 3)
    x0, x1 = max(0, int(cx)-bound), min(N, int(cx)+bound+1)
    y0, y1 = max(0, int(cy)-bound), min(N, int(cy)+bound+1)
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    dx, dy = xx-cx, yy-cy
    u = (dx*math.cos(angle)+dy*math.sin(angle))/rx
    v = (-dx*math.sin(angle)+dy*math.cos(angle))/ry
    theta = np.arctan2(v, u)
    phase = RNG.uniform(0, math.tau, 3)
    border = 1 + (.055 if SOFT else .15)*np.sin(3*theta+phase[0]) + (.025 if SOFT else .10)*np.sin(5*theta+phase[1]) + (.012 if SOFT else .06)*np.sin(9*theta+phase[2])
    radial = np.hypot(u, v)/border
    # Rounded but broken lips, slightly off-centre cast cavities.
    bowl = np.clip(1-radial**2, 0, 1)
    if kind == 'pit':
        shape = bowl**(1.6 if SOFT else 1.9) * (1+(.05 if SOFT else .12)*np.sin(4*u+phase[1])*np.sin(5*v+phase[2]))
        canvas[y0:y1, x0:x1] -= shape * depth
    else:
        edge = np.clip((1-radial)*6, 0, 1)
        grain = RNG.random(edge.shape, dtype=np.float32)
        mottled = edge * np.clip(.64+.42*grain+.12*np.sin(7*u)*np.sin(8*v), 0, 1)
        target = canvas[y0:y1, x0:x1]
        np.maximum(target, mottled*depth, out=target)


MASKS.mkdir(parents=True, exist_ok=True)
height = np.full((N, N), .5, np.float32)
for i in range(6600):
    cx, cy = RNG.uniform(0, N, 2)
    radius = RNG.uniform(.075, .33)
    amplitude = RNG.uniform(.055, .22)  # 44-176 microns at 0.8 mm bump distance.
    irregular_patch(height, cx, cy, radius, RNG.uniform(.60, 1.45), amplitude)
for i in range(135):
    cx, cy = RNG.uniform(0, N, 2)
    irregular_patch(height, cx, cy, RNG.uniform(.36, .90),
                    RNG.uniform(.55, 1.30), RNG.uniform(.16, .39))
save(np.clip(height, .055, .5), 'cast_pitting_soft_8k_16bit.png' if SOFT else 'cast_pitting_8k_16bit.png',
     'Irregular casting cavities: 0.15-0.66 mm pores and sparse 0.7-1.8 mm depressions; neutral 0.5', .8)
del height
if SOFT:
    (MASKS/'pitting_manifest_v06.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('ROUNDED_CAST_PORES_V06_OK',flush=True)
    sys.exit(0)

rubbed = np.zeros((N, N), np.float32)
# x and z in millimetres in the assembled prop; image BOX projection spans 160 mm.
centres = [(-21, 57, 2.8, .58), (-9, 58, 3.6, .48), (9, 58, 3.2, .55),
           (21, 59, 2.9, .63), (-22, 42, 3.1, .60), (-10, 40, 2.8, .42),
           (9, 40, 3.8, .58), (22, 42, 2.8, .70), (-16, 25, 2.9, .46),
           (4, 23, 2.8, .65), (20, 25, 2.1, .55), (-6, 13, 2.1, .44),
           (-11, 82.3, 1.2, .65), (5, 82.2, 1.6, .70), (12, 82.3, 1.3, .5)]
for x, z, radius, aspect in centres:
    # Image Y is top to bottom: v=.15+z/160.
    irregular_patch(rubbed, (80+x)*N/EXTENT, (136-z)*N/EXTENT,
                    radius, aspect, RNG.uniform(.73, 1), 'rub')
# A few random secondary rubbed specks, weaker than the visible contact patches.
for i in range(125):
    x, z = RNG.uniform(-28, 28), RNG.uniform(12, 74)
    irregular_patch(rubbed, (80+x)*N/EXTENT, (136-z)*N/EXTENT,
                    RNG.uniform(.15, .65), RNG.uniform(.4, 1.3),
                    RNG.uniform(.25, .65), 'rub')
save((np.clip(rubbed, 0, 1)*255).astype(np.uint8), 'rubbed_paint_patches_8k.png',
     'Irregular 3-8 mm wiped patches placed on raised body panels; no photograph projection')
polish = Image.fromarray((np.clip((rubbed-.43)/.57, 0, 1)*255).astype(np.uint8))
polish = polish.filter(ImageFilter.GaussianBlur(1.3))
save(np.asarray(polish), 'rubbed_iron_centres_8k.png',
     'Partial brighter iron centres inside paint-loss patches')
del rubbed

refs = OUT / 'references/owner'
refs.mkdir(parents=True, exist_ok=True)
attachment = Path('C:/Users/Schecter_8ght/.codex/codex-remote-attachments/01a13159-559d-7862-ae98-fbaf3bb01041/61FC58E2-79D9-418D-AE08-8E8C8D8BC402')
reference_rows = []
for i in range(1, 4):
    source = attachment / f'{i}-Фото-{i}.jpg'
    dest = refs / f'owner_cast_and_paint_{i}.jpg'
    shutil.copy2(source, dest)
    reference_rows.append({'file': dest.name,
                           'sha256': hashlib.sha256(dest.read_bytes()).hexdigest(),
                           'use': 'Owner-supplied visual reference; no pixels extracted into textures'})
(refs / 'manifest.json').write_text(json.dumps(reference_rows, indent=2), encoding='utf8')
(MASKS / 'pitting_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
print('OWNER_PHOTO_REVISION_MASKS_OK', len(manifest), flush=True)
