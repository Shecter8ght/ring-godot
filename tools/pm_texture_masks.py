"""Author local physical-scale masks from owner alphas and licensed source maps.

This does not alter references or generate a presentation. Side projections have
independent left/right drawings; top and lens projections avoid stretched stamps.
"""
from pathlib import Path
import json, hashlib, shutil
import numpy as np
from PIL import Image, ImageOps, ImageChops, ImageDraw, ImageFilter

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / '_asset_src/pm_texturing'
OUT = ROOT / 'textures/masks'
OUT.mkdir(parents=True, exist_ok=True)
ALPHAS = json.loads((ROOT / 'sources/alpha_manifest.json').read_text(encoding='utf-8'))
USED = set()
RECORDS = []
TRANSFORMS = []
SOURCE_CACHE = {}
SIDE_SIZE = (8192, 4096)  # two 166 x 175 mm sides; about 43 micrometres/texel
TOP_SIZE = (4096, 2048)   # 166 x 50 mm
LENS_SIZE = (2048, 2048) # 32 x 24 mm

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def alpha(index):
    USED.add(index)
    if index not in SOURCE_CACHE:
        with Image.open(ALPHAS[index]['source']) as im:
            # RGB masks have no alpha. Luminance is the actual data.
            a = np.asarray(im.convert('L'), dtype=np.float32)
        a = np.clip((a - 5) / 250, 0, 1)
        SOURCE_CACHE[index] = Image.fromarray(np.uint8(a * 255), 'L')
    return SOURCE_CACHE[index].copy()

def canvas(projection):
    return Image.new('L', {'side': SIDE_SIZE, 'top': TOP_SIZE, 'lens': LENS_SIZE}[projection], 0)

def stamp(im, source, center, size_mm, angle=0, strength=1., side=0,
          projection='side', crop=None, label=''):
    src = alpha(source) if isinstance(source, int) else source.copy()
    if crop:
        src = src.crop(tuple(round(v * src.size[i % 2]) for i, v in enumerate(crop)))
    # Dense source patterns reach the border of their source image. The border
    # must disappear before placement: otherwise a rectangular decal is visible
    # in the reflection even though its fine scratches are plausible.
    yy, xx = np.mgrid[0:src.height, 0:src.width].astype(np.float32)
    sx0 = np.sin(np.pi * xx / max(1, src.width - 1))
    sy0 = np.sin(np.pi * yy / max(1, src.height - 1))
    envelope = np.maximum(sx0 * sy0, 0) ** .72
    src = Image.fromarray(np.uint8(np.asarray(src, dtype=np.float32) * envelope), 'L')
    if projection == 'side':
        sx, sy = 4096 / 166, 4096 / 175
        cx = (center[0] + 82) * sx + side * 4096
        cy = (175 - center[1]) * sy
    elif projection == 'top':
        sx, sy = 4096 / 166, 2048 / 50
        cx = (center[0] + 82) * sx
        cy = (25 - center[1]) * sy
    else:
        sx, sy = 2048 / 32, 2048 / 24
        cx = (center[0] + 16) * sx
        cy = (170 - center[1]) * sy
    src = src.resize((max(1, round(size_mm[0] * sx)), max(1, round(size_mm[1] * sy))), Image.Resampling.LANCZOS)
    src = src.rotate(angle, Image.Resampling.BICUBIC, expand=True)
    src = src.point(lambda p: round(p * strength))
    temp = Image.new('L', im.size)
    temp.paste(src, (round(cx - src.width / 2), round(cy - src.height / 2)))
    im.paste(ImageChops.lighter(im, temp))
    TRANSFORMS.append(dict(label=label, alpha=source if isinstance(source, int) else 'CC0 crop',
                           projection=projection, side=side, center_mm=center,
                           footprint_mm=size_mm, degrees=angle, strength=strength, crop=crop))

def save(im, condition, projection, kind):
    path = OUT / f'PM_{condition}_{projection}_{kind}.png'
    im.save(path, compress_level=6)
    RECORDS.append(dict(file=path.relative_to(ROOT).as_posix(), sha256=digest(path),
                        size=im.size, condition=condition, projection=projection,
                        purpose=kind, color_space='Non-Color', channel='luminance',
                        origin='Locally placed owner alphas / CC0; authored artistic mask'))

# Licensed secondary patterns, deliberately used as mask detail, not as a
# photograph of this pistol or an asserted physically measured material.
cc0_root = PROJECT / '_asset_src/pm_refinement/surface_sources'
cc0_manifest = json.loads((cc0_root / 'manifest.json').read_text(encoding='utf-8'))
cc0_files = ['Scratches004/Scratches004_4K-PNG_Opacity.png',
             'Smear002/Smear002_8K-JPG_Roughness.jpg']
cc0 = []
for rel in cc0_files:
    src = cc0_root / rel
    target = ROOT / 'sources/cc0' / Path(rel).name
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists(): shutil.copy2(src, target)
    assert digest(src) == digest(target)
    with Image.open(src) as im:
        cc0.append(ImageOps.autocontrast(im.convert('L').crop((64, 96, 1088, 1120))))

for condition in (60, 20):
    heavy = condition == 20
    rng = np.random.default_rng(6101 if heavy else 6003)
    side_maps = {k: canvas('side') for k in ('fingerprints', 'rub', 'scratches', 'deposit', 'fasteners', 'wipes', 'droplets')}
    for side in (0, 1):
        offset = 2.4 if side else 0.
        # A few separate finger pads on slide/control and partial palm on grip.
        pads = [(33 + offset, 108, 12, 19, 10, -18), (62 - offset, 91, 11, 16, 3, 14)]
        if heavy: pads += [(5, 108, 14, 21, 8, 26), (-53, 103, 10, 16, 4, -30)]
        for x, z, w, h, idx, ang in pads:
            stamp(side_maps['fingerprints'], idx, (x, z), (w, h), ang + side * 12,
                  .72 if heavy else .44, side, label='Finger contact')
        stamp(side_maps['fingerprints'], 14, (52 + offset, 47), (43, 47), 8 - side * 14,
              .43 if heavy else .20, side, crop=(.08, .2, .94, .92), label='Partial grip contact')
        # Broad scuffs have a contact history. Geometry edge masks are added
        # independently in the material; this atlas only supplies flat rubs.
        rubs = [(53 - offset, 106, 20, 10, .34), (-67 + offset, 107, 11, 13, .37), (21, 92, 8, 5, .45)]
        if heavy:
            rubs = [(48 - offset, 108, 37, 19, .72), (-66, 109, 24, 17, .8),
                    (65, 91, 27, 22, .75), (-32, 90, 17, 10, .6), (45, 7, 33, 7, .8)]
        for x, z, w, h, power in rubs:
            stamp(side_maps['rub'], 37 if heavy else 38, (x, z), (w, h),
                  rng.uniform(-15, 15), power, side, label='Slide/grip/holster rubbing')
        for x, z, w, h in ((49, 38, 28, 35), (66, 64, 16, 21)):
            stamp(side_maps['rub'], 37, (x + offset, z), (w, h), 30,
                  .65 if heavy else .19, side, label='Bakelite raised surface rubbing')
        # Sparse scratch patches use both owner and CC0 measured pattern detail.
        scratch_sites = [(27, 111, 29, 15), (-56, 106, 16, 12), (54, 59, 20, 19)]
        if heavy: scratch_sites += [(62, 90, 25, 21), (-22, 107, 35, 19), (49, 22, 28, 18)]
        for j, (x, z, w, h) in enumerate(scratch_sites):
            src = 35 if j % 2 else cc0[0]
            stamp(side_maps['scratches'], src, (x + offset, z), (w, h),
                  rng.uniform(-20, 20), .67 if heavy else .25, side, label='Local handling scratches')
        # Fastener rings are centred on actual geometry, not generic dotted panels.
        bolt_centers = [(9.04, 89.06, 3.4), (67.4, 92.6, 2.2),
                        (-15.88, 113.78, 5.8), (3.03, 113.78, 5.8),
                        (-27.77, 141.33, 7.4), (-8.17, 141.33, 7.4)]
        if side == 0: bolt_centers += [(-25.87, 129.06, 7.2), (2.73, 129.06, 7.2)]
        if side == 1: bolt_centers += [(5.43, 141.73, 8.8)]
        for x, z, d in bolt_centers:
            # Crop one ring from supplied multi-ring mask; the hole and seat
            # remain native geometry. Fine debris breaks up the ring.
            stamp(side_maps['fasteners'], 28, (x, z), (d, d), rng.uniform(0, 360),
                  .75 if heavy else .32, side, crop=(.09, .11, .42, .43), label='Actual fastener seat')
        deposits = [(52, 31, 41, 43), (59, 91, 26, 12), (-18, 130, 29, 6), (-15, 146, 29, 4)]
        for x, z, w, h in deposits:
            stamp(side_maps['deposit'], 21 if heavy else 18, (x + offset, z), (w, h),
                  rng.uniform(-30, 30), .62 if heavy else .20, side, label='Protected seam or recess')
        stamp(side_maps['wipes'], 27, (23 + offset, 109), (38, 15), 4,
              .43 if heavy else .23, side, label='Wiping along slide')
        stamp(side_maps['wipes'], ImageOps.invert(cc0[1]), (54, 72), (24, 15), -18,
              .27 if heavy else .12, side, label='Licensed smear roughness detail')
        if heavy:
            stamp(side_maps['droplets'], 24, (-26 + offset, 110), (24, 13), -8,
                  .31, side, label='Local dried thin drop rings')
    for kind, im in side_maps.items(): save(im, condition, 'side', kind)
    top_maps = {k: canvas('top') for k in ('fingerprints', 'scratches', 'deposit', 'wipes')}
    stamp(top_maps['fingerprints'], 10 if not heavy else 3, (-13, 0), (12, 17), -24,
          .65 if heavy else .36, projection='top', label='Battery lid fingertip')
    stamp(top_maps['wipes'], 27, (28, 0), (38, 17), 6,
          .44 if heavy else .17, projection='top', label='Slide crown wipe')
    stamp(top_maps['scratches'], cc0[0], (-17, 1), (42, 21), 12,
          .64 if heavy else .14, projection='top', label='Optic lid small scratches')
    for x, y in ((-26, 0), (5.5, 0), (-2.56, -9.6), (-2.56, 9.6)):
        stamp(top_maps['deposit'], 21, (x, y), (7, 7), 27,
              .62 if heavy else .18, projection='top', label='Lid joint protection')
    for kind, im in top_maps.items(): save(im, condition, 'top', kind)
    lens_maps = {k: canvas('lens') for k in ('fingerprints', 'deposit', 'scratches')}
    stamp(lens_maps['fingerprints'], 10 if not heavy else 3, (-8, 152), (9, 12), 28,
          .43 if heavy else .10, projection='lens', crop=(.13, .08, .8, .75), label='Partial edge contact on lens')
    for y in (-11.5, 11.5):
        stamp(lens_maps['deposit'], 21, (y, 157), (3.2, 16), 0,
              .53 if heavy else .18, projection='lens', label='Lens seat dust')
    if heavy:
        stamp(lens_maps['scratches'], 35, (8, 152), (6, 7), -27, .2,
              projection='lens', label='Fine edge cleaning marks, no crack')
    for kind, im in lens_maps.items(): save(im, condition, 'lens', kind)

used_sources = []
for i in sorted(USED):
    row = ALPHAS[i].copy()
    src = Path(row['source']); target = ROOT / 'sources/alphas' / row['relative']
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists(): shutil.copy2(src, target)
    assert digest(target) == row['sha256']
    row['copied_file'] = target.relative_to(ROOT).as_posix(); used_sources.append(row)
(ROOT / 'sources/used_alphas.json').write_text(json.dumps(used_sources, ensure_ascii=False, indent=2), encoding='utf-8')
(ROOT / 'sources/cc0_manifest.json').write_text(json.dumps(cc0_manifest, ensure_ascii=False, indent=2), encoding='utf-8')
(ROOT / 'textures/mask_manifest.json').write_text(json.dumps(dict(images=RECORDS, placements=TRANSFORMS), ensure_ascii=False, indent=2), encoding='utf-8')
print('PM_LOCAL_MASKS_READY', len(RECORDS), 'maps;', len(USED), 'owner alphas;', len(TRANSFORMS), 'physical placements')
