"""Original Cyrillic stencil and thin neck paint mask, with measured projection."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / '_asset_src/grenade_codex'
FOLDER = OUT / 'textures/authoring'
FOLDER.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(5061210)
rows = []


def save(im, name, purpose):
    p = FOLDER / name
    im.save(p, compress_level=6)
    rows.append({'file': name, 'size': list(im.size), 'purpose': purpose,
                 'source': 'Original artwork, Codex 2026-10-12',
                 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()})


im = Image.new('L', (4096, 2048), 0)
d = ImageDraw.Draw(im)
cx, cy, radius = 2048, 530, 180
d.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=242)
for i in range(12):
    angle = i*math.pi/6
    dx, dy = math.cos(angle), math.sin(angle)
    d.line((cx+dx*252,cy+dy*252,cx+dx*372,cy+dy*372), fill=242,width=53)
font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 585)
d.text((2048, 1445), 'СЛНШК', font=font, anchor='mm', fill=242)
# Subtle sharp print abrasion leaves the exact Cyrillic readable.
for i in range(530):
    x, y = rng.uniform(140,3956), rng.uniform(170,1790)
    r = rng.uniform(1.2,7.5)
    d.ellipse((x-r,y-r*.7,x+r,y+r*.7),fill=0)
for i in range(17):
    x,y = rng.uniform(650,3300),rng.uniform(160,1810)
    d.line((x,y,x+rng.uniform(10,44),y+rng.uniform(-8,8)),fill=0,width=int(rng.integers(1,4)))
save(im, 'sun_slnshk_4kx2k.png', 'Dark sun icon and exact Cyrillic СЛНШК; StampProjection 22 x 11 mm')
band = np.zeros((4096,8192),np.uint8)
for y in range(4096):
    z = (1-y/4095)*86
    if 84.35 < z < 85.55:
        band[y] = 245
save(Image.fromarray(band), 'red_neck_seal_8kx4k.png', 'Thin red paint/seal line below head, 1.2 mm high; BandProjection')
(FOLDER/'marking_manifest_v06.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
approved = OUT/'checks/geometry_approved_v05.json'
path = Path('E:/Models Blender/From Scenario/Grenade/Codex_Geometry_v05/Grenade_MkII_geometry_review_v05.blend')
sha = hashlib.sha256(path.read_bytes()).hexdigest()
assert sha == '0c8a359c081355b889e0bd6ea77b2f40fc8faaac5eeb96aacc04ce9b84c14c03'
approved.write_text(json.dumps({'status':'explicitly_approved_by_owner','version':'v05',
    'owner_reply':'Да, v05 принята — делай текстуры','path':str(path),'sha256':sha,
    'texture_authorization':'Use highest quality materials; download whatever is required',
    'geometry_changes_authorized':False},ensure_ascii=False,indent=2),encoding='utf8')
print('GRENADE_MARKING_AND_APPROVAL_OK')
