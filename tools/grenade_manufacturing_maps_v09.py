"""Deterministic, physically scaled manufacturing maps for grenade task 1.

These are authored procedural textures, not photographs or material scans.
Only the distributions of the existing CC0 roughness maps are retained;
the new spatial structure is distinct for compact head, rolled sheet and wire.
"""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_asset_src/grenade_codex/materials_v09_stage1/textures/manufacturing'
BASE = Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v08')
SEED = 901310
RNG = np.random.default_rng(SEED)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def field(shape, cells, blur=(1, 1)):
    """Periodic smooth field; no one-pixel white noise enters the material."""
    low = RNG.standard_normal(cells, dtype=np.float32)
    # Periodic padding makes the cubic reconstruction seamless at tile edges.
    padded = np.pad(low, ((3, 3), (3, 3)), mode='wrap')
    factors = (shape[0] / cells[0], shape[1] / cells[1])
    high = np.asarray(Image.fromarray(padded).resize(
        (round(padded.shape[1] * factors[1]), round(padded.shape[0] * factors[0])),
        Image.Resampling.BICUBIC), dtype=np.float32).copy()
    sy, sx = int(round(3 * factors[0])), int(round(3 * factors[1]))
    high = high[sy:sy + shape[0], sx:sx + shape[1]]
    for axis, sigma in enumerate(blur):
        radius = math.ceil(3 * sigma)
        positions = np.arange(-radius, radius + 1)
        kernel = np.exp(-.5 * (positions / sigma) ** 2)
        kernel /= kernel.sum()
        filtered = np.zeros_like(high)
        for offset, weight in zip(positions, kernel):
            filtered += np.roll(high, int(offset), axis=axis) * float(weight)
        high = filtered
    high -= high.mean()
    high /= max(float(high.std()), 1e-8)
    return high


def save16(name, pixels):
    path = OUT / name
    Image.fromarray(np.round(np.clip(pixels, 0, 1) * 65535).astype(np.uint16)).save(path)
    return {'file': name, 'sha256': sha(path), 'size': list(reversed(pixels.shape)),
            'bit_depth': 16, 'color_space': 'Non-Color'}


def legacy_roughness(family):
    name = 'Metal049C_8K-PNG_Roughness.png' if family == 'head' else 'Metal009_8K-PNG_Roughness.png'
    files = list((BASE / 'textures').rglob(name))
    if len(files) != 1:
        raise RuntimeError(f'Ambiguous retained roughness source: {name}')
    with Image.open(files[0]) as image:
        gray = np.asarray(image.convert('L'))
        histogram = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    cdf = np.cumsum(histogram) / histogram.sum()
    return files[0], cdf, histogram


def match_roughness(family, spatial):
    """Keep the previous overall gloss distribution, change only its structure."""
    path, cdf, histogram = legacy_roughness(family)
    spatial = (spatial - spatial.mean()) / spatial.std()
    bins = 8192
    histogram_new, edges = np.histogram(spatial, bins=bins)
    ranks = (np.cumsum(histogram_new) - .5 * histogram_new) / spatial.size
    mapped = np.interp(ranks, cdf, np.arange(256) / 255)
    rough = np.interp(spatial, (edges[:-1] + edges[1:]) * .5, mapped).astype(np.float32)
    levels = np.arange(256) / 255
    mean = float(np.sum(levels * histogram) / histogram.sum())
    old_std = float(np.sqrt(np.sum((levels - mean) ** 2 * histogram) / histogram.sum()))
    stats = {'source': str(path), 'source_sha256': sha(path), 'old_mean': mean,
             'old_std': old_std, 'new_mean': float(rough.mean()), 'new_std': float(rough.std()),
             'method': 'CDF matching; original layer intensity and material channel values retained'}
    if abs(stats['new_mean'] - mean) > .004 or abs(stats['new_std'] - old_std) > .004:
        raise RuntimeError(('Roughness distribution drift', family, stats))
    return rough, stats


def emit(family, height_m, distance, extent_mm, rough_field, note):
    # Relief amplitude is calibrated in metres, not a normalized arbitrary noise.
    height_m = np.clip(height_m, -.45 * distance, .45 * distance)
    height = save16(f'{family}_manufacturing_height_16.png', .5 + height_m / distance)
    rough, distribution = match_roughness(family, rough_field)
    reflectance = save16(f'{family}_manufacturing_roughness_16.png', rough)
    row = {'family': family, 'height': height, 'roughness': reflectance,
           'extent_mm_uv': extent_mm, 'bump_distance_m': distance,
           'height_min_um': float(height_m.min() * 1e6),
           'height_max_um': float(height_m.max() * 1e6),
           'height_rms_um': float(height_m.std() * 1e6),
           'roughness_distribution': distribution, 'intent': note}
    print('MAPS', family, row['height_rms_um'], distribution['new_mean'], flush=True)
    return row


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    # A 51.2 mm field at 12.5 um/texel: denser, lower, rounded grain than the body.
    shape = (4096, 4096)
    fine = field(shape, (800, 800), (1.1, 1.1))
    medium = field(shape, (280, 280), (1.1, 1.1))
    broad = field(shape, (60, 60), (1.1, 1.1))
    relief = fine * 1.1e-6 + medium * 3.0e-6 + broad * 1.3e-6
    # Small irregular depressions, made from the head's own compact grain field.
    relief -= np.maximum(-medium - 1.5, 0) ** 1.25 * 2.0e-6
    rows.append(emit('head', relief, 80e-6, [51.2, 51.2],
                     fine * .42 + medium * .38 + broad * .15,
                     'Compact rounded metal grain and shallow irregularities; no shared body casting image; no alloy/coating claim.'))
    del fine, medium, broad, relief

    # Rolled sheet: weak elongated grain, no deep machining furrows or cast pits.
    fine = field(shape, (900, 900), (1.0, 1.0))
    roll = field(shape, (900, 20), (1.2, 1.0))
    sheet = field(shape, (96, 96), (1.2, 1.2))
    relief = fine * .30e-6 + roll * .65e-6 + sheet * .32e-6
    rows.append(emit('lever', relief, 12e-6, [51.2, 51.2],
                     fine * .23 + roll * .52 + sheet * .25,
                     'Fine rolled sheet grain; weak directional texture follows the continuous strip through its bends.'))
    del fine, roll, sheet, relief

    # Wire: long shallow drawing marks. 15.6 um along / 3.1 um across per texel.
    shape = (2048, 4096)
    draw = field(shape, (450, 24), (1.2, 1.2))
    finer = field(shape, (900, 130), (1.0, 1.1))
    grain = field(shape, (280, 1280), (1.0, 1.0))
    relief = draw * .28e-6 + finer * .10e-6 + grain * .08e-6
    rows.append(emit('wire', relief, 6e-6, [64, 6.4],
                     draw * .6 + finer * .2 + grain * .15,
                     'Shallow longitudinal die-drawing marks; surface coordinates follow each wire curve, never world-axis scratches.'))
    manifest = {'seed': SEED, 'scope': 'High Poly manufacturing microtexture only, task 1',
                'authorship': 'Procedural authoring; no pixels copied from owner photographs',
                'body_maps': 'unchanged', 'maps': rows}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
