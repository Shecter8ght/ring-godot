# -*- coding: utf-8 -*-
"""Массивы слоёв земли «Санатория» из 4K-наборов tools/fetch_sanatorium_ground.py (8 грунтов):

    assets/terrain/sanatorium_albedo.jpg  4096 × 8 слоёв (BC1 при импорте)
    assets/terrain/sanatorium_normal.jpg  4096 × 8 (OpenGL, BC7 — без «квадратиков» на рельефе)
    assets/terrain/sanatorium_arm.jpg     2048 × 8: R — AO, G — шероховатость, B — высота (для смешения грунтов по высоте)

    python -X utf8 tools/build_sanatorium_ground.py

Порядок слоёв — как GROUND в fetch_sanatorium_ground.py: 0 газон, 1 вытоптанный газон, 2 хвоя, 3 мох, 4 тропа,
5 гранит, 6 щебень, 7 песок. Высота растянута на весь диапазон у каждого слоя (смешение сравнивает формы, не метры).
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_sanatorium_ground import GROUND, RES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / '_asset_src' / 'textures'
OUT = ROOT / 'assets' / 'terrain'
Image.MAX_IMAGE_PIXELS = None
FULL, ARM = 4096, 2048

IMPORT = '''[remap]

importer="2d_array_texture"
type="CompressedTexture2DArray"

[deps]

source_file="res://assets/terrain/{name}"

[params]

compress/mode=2
compress/high_quality={hq}
compress/lossy_quality=0.7
compress/uastc_level=0
compress/rdo_quality_loss=0.0
compress/hdr_compression=1
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
slices/horizontal=1
slices/vertical={layers}
'''


def find(folder: Path, stem: str) -> Path:
    for ext in ('jpg', 'png'):
        p = folder / f'{stem}_{RES}.{ext}'
        if p.exists():
            return p
    raise FileNotFoundError(folder / stem)


def main() -> None:
    n = len(GROUND)
    alb = Image.new('RGB', (FULL, FULL * n))
    nrm = Image.new('RGB', (FULL, FULL * n))
    arm = Image.new('RGB', (ARM, ARM * n))
    for i, (_src, asset_id, role) in enumerate(GROUND):
        folder = SRC / asset_id
        a = Image.open(find(folder, 'albedo')).convert('RGB').resize((FULL, FULL), Image.LANCZOS)
        nm = Image.open(find(folder, 'normal')).convert('RGB').resize((FULL, FULL), Image.LANCZOS)
        packed = Image.open(find(folder, 'arm')).convert('RGB').resize((ARM, ARM), Image.LANCZOS)
        ao, rough, _metal = packed.split()
        h = ImageOps.autocontrast(Image.open(find(folder, 'height')).convert('L').resize((ARM, ARM), Image.LANCZOS), cutoff=0.5)
        alb.paste(a, (0, FULL * i))
        nrm.paste(nm, (0, FULL * i))
        arm.paste(Image.merge('RGB', (ao, rough, h)), (0, ARM * i))
        lum = sum(a.convert('L').resize((64, 64)).getdata()) / 4096.0 / 255.0
        print(f'{i} {asset_id}: средняя яркость {lum:.3f} — {role}')
    OUT.mkdir(parents=True, exist_ok=True)
    for img, name, hq in ((alb, 'sanatorium_albedo.jpg', 'false'), (nrm, 'sanatorium_normal.jpg', 'true'),
                          (arm, 'sanatorium_arm.jpg', 'false')):
        img.save(OUT / name, quality=92, subsampling=0 if 'normal' in name else 2)
        imp = OUT / f'{name}.import'
        if not imp.exists():
            imp.write_text(IMPORT.format(name=name, hq=hq, layers=n), encoding='utf-8', newline='\n')
        print(f'→ assets/terrain/{name} ({(OUT / name).stat().st_size // (1024 * 1024)} МБ)')


if __name__ == '__main__':
    main()
