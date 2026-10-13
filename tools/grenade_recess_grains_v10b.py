"""Original angular residue footprints, gated by body recesses in UCUPaint.

No reference pixels are copied. This is a particle footprint, not a uniform
noise normal: each angular footprint has a positive, masked height in Blender.
"""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_asset_src/grenade_codex/materials_v10b_stage2_recess/textures/deposition'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    size, extent_mm, seed = 8192, 160., 106213
    rng = np.random.default_rng(seed)
    pixels_mm = size / extent_mm
    # Groups of grains are interrupted at a few millimetres. Actual macro
    # placement, orientation and local casting valleys are separate native masks.
    coarse = rng.uniform(0, 1, (54, 54)).astype(np.float32)
    cluster = np.asarray(Image.fromarray(coarse).resize((size, size), Image.Resampling.BICUBIC))
    image = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(image)
    count = 0
    diameters = []
    for _ in range(round(extent_mm**2 * 10)):
        x, y = rng.uniform(0, size, 2)
        affinity = .08 + .82 * np.clip((cluster[int(y), int(x)]-.18)/.64, 0, 1)
        if rng.random() > affinity:
            continue
        diameter = rng.uniform(.065, .235)
        if rng.random() < .012:
            diameter *= 1.5
        radius = diameter * pixels_mm / 2
        rotation = rng.uniform(0, math.tau)
        angles = rotation + np.linspace(0, math.tau, 5, endpoint=False)
        points = [(x+math.cos(a)*radius*rng.uniform(.65,1.1),
                   y+math.sin(a)*radius*rng.uniform(.65,1.1)) for a in angles]
        draw.polygon(points, fill=int(rng.integers(185, 256)))
        count += 1
        diameters.append(diameter)
    image = image.filter(ImageFilter.GaussianBlur(.35))
    file = OUT / 'recess_angular_grit_8k.png'
    image.save(file)
    record = {'file':file.name, 'size':[size,size], 'extent_mm':extent_mm,
              'seed':seed, 'bit_depth':8, 'color_space':'Non-Color',
              'footprints':count, 'mean_density_per_mm2':count/extent_mm**2,
              'diameter_mm':[min(diameters),max(diameters)],
              'coverage_before_geometry_gating':float(np.mean(np.asarray(image)>100)),
              'positive_height_full_coverage_um':45, 'height_midlevel':.5,
              'authorship':'Original seeded angular footprints; no image-reference pixels',
              'license':'Project original',
              'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
    (OUT/'recess_grains_manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
    print('RECESS_GRAINS', count, record['coverage_before_geometry_gating'], flush=True)


if __name__ == '__main__':
    main()
