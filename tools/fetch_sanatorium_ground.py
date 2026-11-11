# -*- coding: utf-8 -*-
"""Грунты «Санатория» в 4K (владелец 2026-11-08: «супер чёткое, высокое качество»): CC0 Poly Haven и ambientCG
в _asset_src/textures/<id>/ — albedo, normal (OpenGL), arm (AO, шероховатость, металл) и height, license.txt.

    python -X utf8 tools/fetch_sanatorium_ground.py [id ...]
Дальше — python -X utf8 tools/build_sanatorium_ground.py (массивы слоёв для шейдера земли санатория).
"""
from __future__ import annotations

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / '_asset_src' / 'textures'
UA = {'User-Agent': 'RING-asset-tool/1.0 (github.com/Shecter8ght/ring-godot)'}
RES = '4k'

# слой земли санатория: (источник, id, роль); порядок — номер слоя в массиве (tools/build_sanatorium_ground.py)
GROUND = [
    ('ambientcg', 'Grass004', 'газон: густая летняя трава с сухими травинками (основа плато)'),
    ('ambientcg', 'Ground037', 'вытоптанный газон: трава с мхом и землёй (у дорожек, у построек, пятнами)'),
    ('polyhaven', 'forrest_ground_03', 'хвойная подстилка: иглы и мелкий сор (под соснами и елями, склон)'),
    ('polyhaven', 'forest_leaves_02', 'мох с ветками и сором (пятна в лесу, у валунов, северные склоны)'),
    ('polyhaven', 'forest_ground_04', 'грунт тропы: утоптанная земля с камешками (тропы, обочины грунтовок)'),
    ('polyhaven', 'lichen_rock', 'гранит с лишайником (скала под подиумом, обрывы, мыс)'),
    ('polyhaven', 'gravel_floor_02', 'щебень (хоздвор, стройплощадки)'),
    ('polyhaven', 'sand_03', 'песок пляжа'),
]


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        return r.read()


def fetch_polyhaven(asset_id: str, role: str, catalog: dict) -> None:
    out = SRC / asset_id
    out.mkdir(parents=True, exist_ok=True)
    files = json.loads(get(f'https://api.polyhaven.com/files/{asset_id}'))
    got = []
    for key, name in (('Diffuse', 'albedo'), ('nor_gl', 'normal'), ('arm', 'arm'), ('Displacement', 'height')):
        entry = files.get(key, {}).get(RES, {})
        variant = entry.get('jpg') or entry.get('png')
        if not variant:
            continue
        ext = 'png' if 'png' in entry and not entry.get('jpg') else 'jpg'
        dest = out / f'{name}_{RES}.{ext}'
        if not dest.exists():
            dest.write_bytes(get(variant['url']))
        got.append(dest.name)
    info = catalog.get(asset_id, {})
    authors = ', '.join(info.get('authors', {}).keys()) or 'Poly Haven'
    (out / 'license.txt').write_text(
        f"title: {info.get('name', asset_id)}\nauthor: {authors}\nlicense: CC0 1.0\n"
        f"source: https://polyhaven.com/a/{asset_id}\nmaps: {', '.join(got)}\nrole: {role}\n", encoding='utf-8')
    print(f'{asset_id}: {", ".join(got)}')


def fetch_ambientcg(asset_id: str, role: str) -> None:
    out = SRC / asset_id
    out.mkdir(parents=True, exist_ok=True)
    zname = f'{asset_id}_{RES.upper()}-JPG.zip'
    have = {p.name for p in out.glob(f'*_{RES}.*')}
    if not {f'albedo_{RES}.jpg', f'normal_{RES}.jpg', f'arm_{RES}.png', f'height_{RES}.png'} <= have:
        data = get(f'https://ambientcg.com/get?file={zname}')
        z = zipfile.ZipFile(io.BytesIO(data))
        names = z.namelist()

        def pick(tag: str):
            for n in names:
                if tag in n and n.lower().endswith(('.jpg', '.png')):
                    return Image.open(io.BytesIO(z.read(n)))
            return None
        color = pick('_Color')
        normal = pick('_NormalGL')
        rough = pick('_Roughness')
        ao = pick('_AmbientOcclusion')
        disp = pick('_Displacement')
        color.convert('RGB').save(out / f'albedo_{RES}.jpg', quality=95)
        normal.convert('RGB').save(out / f'normal_{RES}.jpg', quality=95)
        size = color.size
        r_ = rough.convert('L').resize(size) if rough else Image.new('L', size, 200)
        a_ = ao.convert('L').resize(size) if ao else Image.new('L', size, 255)
        Image.merge('RGB', (a_, r_, Image.new('L', size, 0))).save(out / f'arm_{RES}.png')
        (disp.convert('L') if disp else Image.new('L', size, 128)).resize(size).save(out / f'height_{RES}.png')
    (out / 'license.txt').write_text(
        f"title: {asset_id}\nauthor: ambientCG (Lennart Demes)\nlicense: CC0 1.0\n"
        f"source: https://ambientcg.com/view?id={asset_id}\nmaps: albedo, normal (OpenGL), arm (AO + Roughness), height\n"
        f"role: {role}\n", encoding='utf-8')
    print(f'{asset_id}: ok')


def main() -> None:
    want = set(sys.argv[1:])
    catalog = json.loads(get('https://api.polyhaven.com/assets?t=textures'))
    for src, asset_id, role in GROUND:
        if want and asset_id not in want:
            continue
        if src == 'polyhaven':
            fetch_polyhaven(asset_id, role, catalog)
        else:
            fetch_ambientcg(asset_id, role)


if __name__ == '__main__':
    main()
