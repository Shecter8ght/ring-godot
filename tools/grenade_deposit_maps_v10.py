"""Task 2: derive deposition affinity from the accepted manufacturing height.

Maps constrain existing dust/soil layers. They add no new surface geometry,
manufacturing texture, random particle field or material-library abstraction.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v09_Task1_На_проверку')
OUT = ROOT / '_asset_src/grenade_codex/materials_v10_stage2/textures/deposition'


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def smoothstep(a, b, field):
    q = np.clip((field-a)/(b-a), 0, 1)
    return q*q*(3-2*q)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for family, rel, extent_mm, distance in [
        ('body', 'textures/authoring/casting_relief_8k_16bit.png', 160, .0008),
        ('head', 'textures/manufacturing/head_manufacturing_height_16.png', 51.2, .000080),
        ('lever', 'textures/manufacturing/lever_manufacturing_height_16.png', 51.2, .000012),
    ]:
        source = BASE / rel
        with Image.open(source) as image:
            encoded = np.asarray(image, dtype=np.float32) / 65535
        height = (encoded-.5)*distance
        size = height.shape[0]
        # Remove only slow underlying form. Retention follows local depressions,
        # not the whole darker/lower side of a cast flow or a lighting gradient.
        window_mm = .42 if family == 'body' else .14 if family == 'head' else .075
        down = max(16, round(extent_mm/window_mm))
        local = np.asarray(Image.fromarray(height).resize((down, down), Image.Resampling.BOX)
                           .resize((size, size), Image.Resampling.BICUBIC), dtype=np.float32)
        residual = height-local
        sigma = max(float(residual.std()), 1e-8)
        valleys = smoothstep(-.35, 1.4, -residual/sigma)
        # Soft affinity, never a binary cut of a grain footprint. The patch uses
        # a floor for film/dust; coarse grit is height-conditioned only on body.
        name = f'{family}_local_valley_retention_16.png'
        path = OUT / name
        Image.fromarray(np.round(valleys*65535).astype(np.uint16)).save(path)
        rows.append({'family': family, 'file': name, 'size': [size, size],
                     'sha256': sha(path), 'source': str(source), 'source_sha256': sha(source),
                     'physical_extent_mm': extent_mm, 'neighborhood_mm': window_mm,
                     'height_residual_rms_um': sigma*1e6, 'mean_affinity': float(valleys.mean()),
                     'authorship': 'Derived from accepted height; no added random noise',
                     'color_space': 'Non-Color', 'bit_depth': 16})
        print('VALLEY_MAP', family, sigma*1e6, flush=True)
    (OUT/'manifest.json').write_text(json.dumps({'scope':'task_2_deposition_only', 'maps':rows},
                                    ensure_ascii=False, indent=2), encoding='utf8')


if __name__ == '__main__':
    main()
