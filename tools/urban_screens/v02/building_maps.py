"""Technical PBR inputs for R06. Never modifies the owner's photographs.

Reuses credited CC0 scan maps, separates packed roughness, crops a single brick
surface to avoid drawing a second mortar grid on the modelled brick courses.
Weather maps are explicitly synthetic, metrically placed at the actual openings.
"""
from pathlib import Path
import hashlib
import json
import random
import shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

PROJECT = Path(__file__).resolve().parents[3]
ROOT = PROJECT / '_asset_src/urban_realrefs_v02/assets/R06_building/pbr_v01'
TEX = ROOT / 'textures'
W, H = 34.8, 6.65


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def prepare_scans():
    items = []
    for key in ('painted_plaster_wall', 'red_bricks_04', 'rusty_metal_sheet', 'rough_concrete', 'wood_planks_grey'):
        folder = TEX / key
        folder.mkdir(parents=True, exist_ok=True)
        source = PROJECT / '_asset_src/textures' / key
        for kind in ('albedo', 'normal', 'arm'):
            path = folder / (kind + '.jpg')
            shutil.copy2(source / path.name, path)
            items.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path),
                source=f'https://polyhaven.com/a/{key}', license='CC0-1.0', operation='Unchanged cached source map'))
        shutil.copy2(source / 'license.txt', folder / 'license.txt')
        with Image.open(folder / 'arm.jpg') as im:
            im.getchannel('G').save(folder / 'roughness.png')
        items.append(dict(path=(folder / 'roughness.png').relative_to(ROOT).as_posix(),
            source=f'https://polyhaven.com/a/{key}', license='CC0-1.0', operation='Packed ARM green channel, no retouch'))
    # An orange-red brick near the top of the 2048 scan; crop stays inside its face.
    # The same pixel window is used for albedo/roughness/normal.
    for kind in ('albedo.jpg', 'normal.jpg', 'roughness.png'):
        with Image.open(TEX / 'red_bricks_04' / kind) as im:
            scale = im.width / 2048
            box = tuple(round(q * scale) for q in (130, 12, 245, 42))
            im.crop(box).save(TEX / 'red_bricks_04' / ('single_' + kind.replace('.jpg', '.png')))
    # User mask is preserved byte-for-byte, with provenance distinct from CC0.
    for name, path in {
        'owner_film.png': '04_Грязь_и_налёт/Налёт_мелкими_пятнами_01.png',
        'owner_dust.png': '03_Пыль_и_частицы/Пыль_редкая_01.png',
        'owner_hairline.png': '14_Микротрещины_покрытия/Микротрещины_09_Слабое_старение.png',
    }.items():
        dst = TEX / name
        src = Path('E:/Models Blender/Маски_АЛЬФА') / path
        shutil.copy2(src, dst)
        items.append(dict(path=dst.relative_to(ROOT).as_posix(), sha256=sha(dst), source=str(src),
            license='Owner supplied; no CC0 claim', operation='Unchanged mask; native layer sets scale and placement'))
    sky = TEX / 'kloofendal_overcast_puresky.hdr'
    shutil.copy2(PROJECT / 'assets/sky' / sky.name, sky)
    shutil.copy2(PROJECT / '_asset_src/sky/kloofendal_overcast_puresky/license.txt', TEX / 'sky_license.txt')
    items.append(dict(path=sky.relative_to(ROOT).as_posix(), sha256=sha(sky),
        source='https://polyhaven.com/a/kloofendal_overcast_puresky', license='CC0-1.0', operation='Unchanged cached HDRI'))
    (ROOT / 'sources.json').write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')


def noise_field(rng, width, height, cell_x, cell_y):
    a = rng.uniform(0, 255, (max(2, cell_y), max(2, cell_x))).astype('uint8')
    im = Image.fromarray(a).resize((width, height), Image.Resampling.BICUBIC)
    return np.asarray(im).astype(np.float32) / 255


def elevation(name, span, windows, seed, front=False):
    """176 px/m with unique runoff placement; white is effect, black intact paint."""
    rng = random.Random(seed)
    nprng = np.random.default_rng(seed)
    width, height = int(span * 176), int(H * 176)
    target = TEX / 'weather'
    target.mkdir(exist_ok=True)
    def xy(x, z):
        return ((x + span / 2) * width / span, (H - z) * height / H)
    rain = Image.new('L', (width, height))
    d = ImageDraw.Draw(rain)
    for x, z, w in windows:
        # Broad but faint dust washed from each ledge, broken into irregular ribbons.
        for _ in range(rng.randint(19, 37)):
            px = x + rng.uniform(-w * .51, w * .51)
            length = rng.uniform(.035, .34) * (1.3 if rng.random() < .12 else 1)
            wd = rng.uniform(.009, .035)
            val = rng.randint(22, 100)
            walk = px
            pts = []
            for j in range(12):
                walk += rng.uniform(-.003, .003)
                pts.append(xy(walk, z - .052 - length * j / 11))
            d.line(pts, fill=val, width=max(1, round(wd * 176)))
        # Drip ends discharge more dirt, but neither side is an identical stamp.
        for side in (-1, 1):
            px = x + side * (w / 2 + .055)
            length = rng.uniform(.13, .60)
            for t in range(5):
                wd = .030 - t * .004
                d.line([xy(px, z - .03), xy(px + rng.uniform(-.012, .012), z - length)],
                    fill=35 + t * 20, width=max(1, round(wd * 176)))
    rain = rain.filter(ImageFilter.GaussianBlur(.85))
    arr = np.asarray(rain).astype(np.float32) / 255
    grain = noise_field(nprng, width, height, width // 20, height // 9)
    arr *= .70 + .6 * grain
    Image.fromarray(np.uint8(np.clip(arr * 255, 0, 255))).save(target / (name + '_runoff.png'))
    # Dirt under the roof edge and capillary dampness at ground level.
    z = H - (np.arange(height, dtype=np.float32) + .5)[:, None] / height * H
    large = noise_field(nprng, width, height, int(span * 1.1), 6)
    fine = noise_field(nprng, width, height, int(span * 12), 60)
    edge = np.exp(-((z - 6.55) / (.11 + .17 * large)) ** 2) * (.16 + .38 * fine)
    damp = np.exp(-z / (.14 + .27 * large)) * (.40 + .48 * fine)
    Image.fromarray(np.uint8(np.clip(edge * 255, 0, 255))).save(target / (name + '_eaves.png'))
    Image.fromarray(np.uint8(np.clip(damp * 255, 0, 255))).save(target / (name + '_damp.png'))
    # Small tonal repairs and isolated soft lime bloom, no painted war damage.
    patch = np.clip((large - .40) * 1.5, 0, .48) * (.6 + .4 * fine)
    Image.fromarray(np.uint8(patch * 255)).save(target / (name + '_lime.png'))
    # Photo 2: old hand-trowelled and locally swollen coating between floors.
    # A support mask for a native directional height layer, not mesh displacement.
    band = np.exp(-((z - 3.55) / .72) ** 4) * (.55 + .45 * large)
    Image.fromarray(np.uint8(np.clip(band * 255, 0, 255))).save(target / (name + '_swelling.png'))
    # Fine branching stress cracks at selected openings. Geometry already owns
    # the major cracks, so this map is sparse and low-depth.
    hair = Image.new('L', (width, height))
    hd = ImageDraw.Draw(hair)
    for x, sill, w in windows:
        if rng.random() > .32:
            continue
        side = rng.choice((-1, 1))
        start = (x + side * (w / 2 + .025), sill - .01)
        walkx, walkz = start
        pts = [xy(*start)]
        for j in range(rng.randint(4, 7)):
            walkx += side * rng.uniform(.01, .055) + rng.uniform(-.035, .035)
            walkz -= rng.uniform(.035, .085)
            pts.append(xy(walkx, walkz))
        hd.line(pts, fill=rng.randint(65, 150), width=1)
    if front:
        # Irregular intermittent hairline in the old horizontal repair band seen
        # on photo 2; no periodic waves and no embossed universal crack network.
        x = -17.2
        zc = 3.46
        pts = []
        while x < 17.2:
            zc += rng.uniform(-.008, .008)
            zc = max(3.43, min(3.51, zc))
            pts.append(xy(x, zc))
            x += rng.uniform(.06, .19)
        hd.line(pts, fill=85, width=1)
    hair.save(target / (name + '_hairline.png'))


def main():
    TEX.mkdir(parents=True, exist_ok=True)
    prepare_scans()
    bays = [-15.6 + i * 2.6 for i in range(13)]
    front = []
    for i, x in enumerate(bays):
        if i in (3, 9):
            front.append((x, 3.03, 1.53))
        else:
            w = 1.62 if i in (0, 2, 4, 8, 12) else 1.91
            front += [(x, 1.0, w), (x, 4.10, w)]
    elevation('front', W, front, 6411, True)
    elevation('rear', W, [(x, z, 1.62) for x in (-13, -7.8, -2.6, 2.6, 7.8, 13) for z in (1, 4.1)], 6532)
    elevation('side', 10.5, [(x, z, 1.62) for x in (-2.7, 0, 2.7) for z in (1, 4.1)], 6653)
    print('R06_TEXTURE_INPUTS_READY', ROOT)


if __name__ == '__main__':
    main()
