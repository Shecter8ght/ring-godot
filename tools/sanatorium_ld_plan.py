# -*- coding: utf-8 -*-
"""Левел-дизайн карты «Санаторий»: замер обзора по серому блокауту (data/blockouts/sanatorium.json + рельеф).

    python -X utf8 tools/sanatorium_ld_plan.py   → docs/design/sanatorium_sightlines.png + docs/screens/sanatorium/sightlines.json
    python -X utf8 tools/sanatorium_ld_plan.py --breaks 70   → ещё docs/design/data/sanatorium_view_breaks.json: места групп
        елей, которые ломают больше всего длинных лучей внутри территории (жадно: группа — туда, где таких лучей
        больше всего, их считаем сломанными, дальше — следующая; не на дорогах, дорожках, площадках и постройках).
        Генератор блокаута ставит туда группы (ель и молодые ели вокруг); потом замер — заново.

Правило владельца для «Проспекта» и концепция «Санатория» (docs/design/sanatorium_map.md, §5): внутри территории обзор
прерывается через 50–90 м. Замер — как на «Проспекте» (tools/prospekt_ld_plan.py), но с рельефом: из точек сетки 5 м,
где можно стоять, 24 луча; по лучу видно человека (голова на 1,7 м над его полом), если линия от глаза наблюдателя
(1,7 м) до неё не задета рельефом и постройками. Длина луча — до самого дальнего видимого человека, до 300 м.

Преграда — то, что стоит на земле или на других преградах и закрывает взгляд: стены, коробки, колонны, подпорные
стенки, сам склон. Стекло, перила, сетка, зонтики и всё, что висит выше роста (кровли на столбах, подвесной подиум),
взгляд не закрывают. Деревья — во втором варианте: ель — столб кроны от земли, сосна — только ствол (крона выше глаз).

Итог по зонам: внутри плато (оба конца выше +25), с плато к воде (наблюдатель на плато, человек ниже +8),
у воды (оба ниже +8: набережная, пляж, мол), остальное — склон и спуски. Длинные лучи с бровки к воде — по замыслу
(«сильная позиция над набережной»), правило 90 м — внутри территории.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import runpy
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
PLAN_JSON = ROOT / 'data/blockouts/sanatorium.json'
VEG_JSON = ROOT / 'data/blockouts/sanatorium_vegetation.json'
TER_JSON = ROOT / 'data/blockouts/sanatorium_terrain.json'
DESC_JSON = ROOT / 'docs/design/data/sanatorium_descents_v03.json'
SPA_JSON = ROOT / 'docs/design/data/sanatorium_spa_restaurant_v03.json'
OUT_PNG = ROOT / 'docs/design/sanatorium_sightlines.png'
OUT_JSON = ROOT / 'docs/screens/sanatorium/sightlines.json'
OUT_BREAKS = ROOT / 'docs/design/data/sanatorium_view_breaks.json'
DECALS = {'asphalt', 'paving', 'trail', 'trail_strip', 'stripe', 'rubber_red', 'rubber_green', 'rubber_blue', 'rubber_dark', 'court'}

EYE = 1.7
CELL = 0.5
STEP = 5.0            # шаг точек замера
RAYS = 24
MAX_RAY = 300.0
LONG = 90.0
SEE_THROUGH = {'glass', 'rail', 'fence', 'fence_green', 'rope', 'barrier_red', 'umbrella', 'umbrella_pink', 'stripe',
               'trail', 'trail_strip', 'paving', 'asphalt'}
X0, X1, Y0, Y1 = -390.0, 190.0, -300.0, 300.0
NX, NY = int((X1 - X0) / CELL), int((Y1 - Y0) / CELL)


def load_scheme():
    """Схема участка исполняется как есть (граница, мол, бровка), без записи картинки."""
    import PIL.Image as PI
    save = PI.Image.save
    PI.Image.save = lambda self, *a, **k: None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return runpy.run_path(str(ROOT / 'tools/sanatorium_map_plan.py'), run_name='sanatorium_plan_data')
    finally:
        PI.Image.save = save


def cell_ij(x, y):
    return ((np.asarray(x) - X0) / CELL).astype(int), ((Y1 - np.asarray(y)) / CELL).astype(int)


def cell_xy():
    xs = X0 + (np.arange(NX) + 0.5) * CELL
    ys = Y1 - (np.arange(NY) + 0.5) * CELL
    return np.meshgrid(xs, ys)


def terrain_raster():
    t = json.loads(TER_JSON.read_text(encoding='utf-8'))['terrain']
    gx, gy = t['grid']
    h = np.fromfile(ROOT / t['heights'].replace('res://', ''), dtype='<f4').reshape(gy, gx)
    ox, oy = t['origin']
    X, Y = cell_xy()
    fx = (X - ox) / t['step']
    fy = (oy + (gy - 1) * t['step'] - Y) / t['step']      # строки сверху вниз: север → юг
    i = np.clip(np.floor(fx).astype(int), 0, gx - 2)
    j = np.clip(np.floor(fy).astype(int), 0, gy - 2)
    tx, ty = fx - i, fy - j
    return (h[j, i] * (1 - tx) * (1 - ty) + h[j, i + 1] * tx * (1 - ty) + h[j + 1, i] * (1 - tx) * ty
            + h[j + 1, i + 1] * tx * ty)


def rect_cells(cx, cy, length, width, ang_deg, pad=0.0):
    """Ячейки повёрнутого прямоугольника (центр, длина вдоль ang, ширина поперёк) в плане."""
    a = math.radians(ang_deg)
    ca, sa = math.cos(a), math.sin(a)
    hl, hw = length / 2 + pad, width / 2 + pad
    r = abs(hl * ca) + abs(hw * sa), abs(hl * sa) + abs(hw * ca)
    i0, j1 = cell_ij(cx - r[0], cy - r[1])
    i1, j0 = cell_ij(cx + r[0], cy + r[1])
    i0, i1 = max(0, int(i0)), min(NX - 1, int(i1))
    j0, j1 = max(0, int(j0)), min(NY - 1, int(j1))
    if i1 < i0 or j1 < j0:
        return None
    ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1))
    px = X0 + (ii + 0.5) * CELL - cx
    py = Y1 - (jj + 0.5) * CELL - cy
    u = px * ca + py * sa
    v = -px * sa + py * ca
    m = (np.abs(u) <= hl + CELL * 0.5) & (np.abs(v) <= hw + CELL * 0.5)
    return jj[m], ii[m]


def raster_tris(flat):
    """Ячейки каждого треугольника (Godot-координаты в плоском списке) и высота плоскости в них."""
    a = np.asarray(flat, dtype=float).reshape(-1, 3, 3)
    for tri in a:
        xs, zs, ys = tri[:, 0], tri[:, 1], -tri[:, 2]
        i0, j1 = cell_ij(xs.min(), ys.min())
        i1, j0 = cell_ij(xs.max(), ys.max())
        i0, i1 = max(0, int(i0)), min(NX - 1, int(i1))
        j0, j1 = max(0, int(j0)), min(NY - 1, int(j1))
        if i1 < i0 or j1 < j0:
            continue
        ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1))
        px, py = X0 + (ii + 0.5) * CELL, Y1 - (jj + 0.5) * CELL
        (x1, y1), (x2, y2), (x3, y3) = zip(xs, ys)
        den = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(den) < 1e-9:
            continue
        l1 = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / den
        l2 = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / den
        l3 = 1 - l1 - l2
        m = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
        yield jj[m], ii[m], (l1 * zs[0] + l2 * zs[1] + l3 * zs[2])[m]


def plan_breaks(res, notree, n_max, target=0.10):
    """Жадно: группа елей — в клетку 2 м, через которую идёт больше всего живых длинных лучей внутри территории;
    лучи ближе 3,5 м к ней считаем сломанными. Группы — не ближе 14 м друг к другу."""
    geo = [g for g in res['long_geo'] if g[5] in ('внутри плато', 'склон и спуски')]
    plateau_rays = res['zones']['внутри плато']['rays'] + res['zones']['склон и спуски']['rays']
    BIN = 2.0
    nbx, nby = int((X1 - X0) / BIN), int((Y1 - Y0) / BIN)
    ok_bin = np.zeros((nby, nbx), dtype=bool)
    k = int(BIN / CELL)
    free = ~notree[:nby * k, :nbx * k].reshape(nby, k, nbx, k).any(axis=(1, 3))
    ok_bin[:, :] = free
    samp_ray, samp_bin = [], []
    for r_i, (px, py, dx, dy, d, z) in enumerate(geo):
        ts = np.arange(14.0, d - 14.0, 2.0)
        if ts.size == 0:
            continue
        bx = ((px + dx * ts - X0) / BIN).astype(int)
        by = ((Y1 - (py + dy * ts)) / BIN).astype(int)
        m = (bx >= 0) & (bx < nbx) & (by >= 0) & (by < nby)
        bx, by = bx[m], by[m]
        m = ok_bin[by, bx]
        b = by[m] * nbx + bx[m]
        samp_bin.append(b)
        samp_ray.append(np.full(b.size, r_i))
    if not samp_bin:
        return []
    samp_bin = np.concatenate(samp_bin)
    samp_ray = np.concatenate(samp_ray)
    alive = np.ones(len(geo), dtype=bool)
    banned = np.zeros(nbx * nby, dtype=bool)
    clusters = []
    ray_xy = np.array([(g[0], g[1], g[2], g[3], g[4]) for g in geo])
    for _ in range(n_max):
        sel = alive[samp_ray] & ~banned[samp_bin]
        if not sel.any():
            break
        counts = np.bincount(samp_bin[sel], minlength=nbx * nby)
        b = int(np.argmax(counts))
        if counts[b] < 25:
            break
        cx = X0 + (b % nbx + 0.5) * BIN
        cy = Y1 - (b // nbx + 0.5) * BIN
        # сломанные лучи: проходят ближе 3,5 м к центру группы (между 14 м от глаза и 14 м до цели)
        px, py, dx, dy, d = ray_xy[:, 0], ray_xy[:, 1], ray_xy[:, 2], ray_xy[:, 3], ray_xy[:, 4]
        t = (cx - px) * dx + (cy - py) * dy
        dist = np.abs(-(cx - px) * dy + (cy - py) * dx)
        hit = alive & (t > 14.0) & (t < d - 14.0) & (dist < 3.5)
        alive &= ~hit
        clusters.append([round(cx, 1), round(cy, 1), int(hit.sum())])
        bx0, by0 = b % nbx, b // nbx
        r = int(14.0 / BIN)
        for yy in range(max(0, by0 - r), min(nby, by0 + r + 1)):
            for xx in range(max(0, bx0 - r), min(nbx, bx0 + r + 1)):
                if (xx - bx0) ** 2 + (yy - by0) ** 2 <= r * r:
                    banned[yy * nbx + xx] = True
        left = (alive.sum()) / max(1, plateau_rays)
        if left < target:
            break
    print(f'группы елей: {len(clusters)}, длинных лучей внутри территории было {len(geo)} '
          f'({len(geo) / max(1, plateau_rays) * 100:.1f} %), осталось по оценке {alive.sum()} ({alive.sum() / max(1, plateau_rays) * 100:.1f} %)')
    return clusters


def main():
    plan = json.loads(PLAN_JSON.read_text(encoding='utf-8'))
    scheme = load_scheme()
    mats = plan['mats']
    T = terrain_raster()
    G = T.copy()                                   # пол: рельеф, марши, плиты (мол, пирсы)
    floor_from_tris = np.zeros_like(G, dtype=bool)
    # сплошные треугольники — настилы (мол, пирсы, плиты): пол; асфальт, дорожки, покрытия — где деревьям не место
    decal = np.zeros_like(G, dtype=bool)
    for key, flat in plan['tris'].items():
        name, solid = key.split('|')
        if solid != '1' and name not in DECALS:
            continue
        for jj, ii, z in raster_tris(flat):
            if solid == '1':
                G[jj, ii] = np.maximum(G[jj, ii], z)
                floor_from_tris[jj, ii] = True
            else:
                decal[jj, ii] = True
    # марши — пол (поверхность по наклону)
    for st in plan['stairs']:
        bx, bz, bmz, tx, tz, tmz, w = st[:7]
        by, ty = -bmz, -tmz
        L = math.hypot(tx - bx, ty - by)
        if L < 0.1:
            continue
        cells = rect_cells((bx + tx) / 2, (by + ty) / 2, L, w, math.degrees(math.atan2(ty - by, tx - bx)))
        if cells is None:
            continue
        jj, ii = cells
        px, py = X0 + (ii + 0.5) * CELL, Y1 - (jj + 0.5) * CELL
        t = np.clip(((px - bx) * (tx - bx) + (py - by) * (ty - by)) / (L * L), 0, 1)
        G[jj, ii] = np.maximum(G[jj, ii], bz + (tz - bz) * t)
    # преграды взгляда: коробки и колонны снизу вверх — берётся то, что стоит на полу или на уже взятом
    S = G.copy()
    items = []
    for b in plan['boxes']:
        cx, cyh, cmz, sx, sh, sz, ang, mi, solid = b
        if mats[mi] in SEE_THROUGH:
            continue
        items.append((cyh - sh / 2, 'box', b))
    for c in plan['cyls']:
        cx, z0, cmz, r, h, mi, solid, sides = c
        if mats[mi] in SEE_THROUGH or r < 0.18:
            continue
        items.append((z0, 'cyl', c))
    items.sort(key=lambda it: it[0])
    taken = 0
    for z0, kind, it in items:
        if kind == 'box':
            cx, cyh, cmz, sx, sh, sz, ang, mi, solid = it
            cells = rect_cells(cx, -cmz, sx, sz, ang)
            top = cyh + sh / 2
        else:
            cx, z0_, cmz, r, h, mi, solid, sides = it
            cells = rect_cells(cx, -cmz, r * 1.6, r * 1.6, 0.0)
            top = z0_ + h
        if cells is None:
            continue
        jj, ii = cells
        under = np.median(S[jj, ii])
        if z0 > under + 0.6:                       # висит выше роста: кровля на столбах, подиум, зонтик
            continue
        S[jj, ii] = np.maximum(S[jj, ii], top)
        taken += 1
    # где можно стоять
    X, Y = cell_xy()
    L_ = np.where((S - G < 0.6) & ((T > 0.15) | floor_from_tris), G, np.nan)
    desc = json.loads(DESC_JSON.read_text(encoding='utf-8'))
    floors = [e['rect'] for e in desc['cascade']['elements']] + [desc['cascade']['balcony']]
    for r in floors:                               # каскад: площадки, марши и полосы — стоять на их верху
        m = (X >= r[0]) & (X <= r[2]) & (Y >= r[1]) & (Y <= r[3])
        L_ = np.where(m, S, L_)
    spa = json.loads(SPA_JSON.read_text(encoding='utf-8'))
    po = spa['podium']
    m = (X >= po[0]) & (X <= po[2]) & (Y >= po[1]) & (Y <= po[3])
    L_ = np.where(m, 32.0, L_)
    S = np.where(m, np.maximum(S, 32.0), S)
    # стоять можно только внутри границы суши и на моле (отмели за мысом и лес за забором — не цели)
    mask = Image.new('L', (NX, NY), 0)
    md = ImageDraw.Draw(mask)
    for poly in (scheme['boundary'], [tuple(p) for p in scheme['MOLE_PTS']]):
        md.polygon([((x - X0) / CELL, (Y1 - y) / CELL) for x, y in poly], fill=255)
    inside = np.asarray(mask) > 0
    L_ = np.where(inside, L_, np.nan)
    for bld in plan['buildings']:                  # внутри зданий не меряем (там свой ближний бой); у S-корпусов — номера
        if not bld.get('rect'):
            continue
        x0_, y0_, x1_, y1_ = bld['rect']
        m = (X >= x0_ - 0.3) & (X <= x1_ + 0.3) & (Y >= y0_ - 0.3) & (Y <= y1_ + 0.3)
        L_ = np.where(m, np.nan, L_)
    # точки замера: сетка 5 м внутри границы суши и мола
    boundary = scheme['boundary']
    mole = [tuple(p) for p in scheme['MOLE_PTS']]
    in_poly = scheme['in_poly']
    pts = []
    x = X0 + STEP / 2
    while x < X1:
        y = Y0 + STEP / 2
        while y < Y1:
            if in_poly(x, y, boundary) or in_poly(x, y, mole):
                i, j = cell_ij(x, y)
                if 0 <= i < NX and 0 <= j < NY and not np.isnan(L_[j, i]):
                    pts.append((x, y, float(L_[j, i])))
            y += STEP
        x += STEP
    # деревья: ель — крона от земли, сосна — ствол
    veg = json.loads(VEG_JSON.read_text(encoding='utf-8'))
    S_tr = S.copy()
    for key, rad, hgt in (('spruce_a', 2.0, 14.0), ('spruce_b', 2.0, 14.0), ('spruce_young', 1.2, 7.0), ('spruce_a_bg', 2.0, 14.0),
                          ('spruce_b_bg', 2.0, 14.0), ('pine', 0.3, 12.0), ('pine_slim', 0.25, 12.0), ('pine_bg', 0.3, 12.0)):
        for t_ in veg.get(key, []):
            tx_, ground_, tmz = t_[0], t_[1], t_[2]
            sc = float(t_[4]) if len(t_) > 4 else 1.0
            if ground_ is None:
                continue
            cells = rect_cells(tx_, -tmz, rad * 2 * sc, rad * 2 * sc, 0.0)
            if cells is None:
                continue
            jj, ii = cells
            px, py = X0 + (ii + 0.5) * CELL - tx_, Y1 - (jj + 0.5) * CELL + tmz
            mm = px * px + py * py <= (rad * sc + CELL * 0.5) ** 2
            S_tr[jj[mm], ii[mm]] = np.maximum(S_tr[jj[mm], ii[mm]], ground_ + hgt * sc)
    results = {}
    for variant, Sv in (('без деревьев', S), ('с деревьями', S_tr)):
        results[variant] = cast(pts, Sv, L_)
    import sys
    if '--breaks' in sys.argv:
        from scipy.ndimage import binary_dilation
        n_max = int(sys.argv[sys.argv.index('--breaks') + 1])
        notree = (S - G > 0.3) | decal | ~inside | (T < 0.5)
        for r in floors + [po]:
            notree |= (X >= r[0]) & (X <= r[2]) & (Y >= r[1]) & (Y <= r[3])
        notree = binary_dilation(notree, iterations=int(2.5 / CELL))
        clusters = plan_breaks(results['с деревьями'], notree, n_max)
        OUT_BREAKS.write_text(json.dumps({
            'note': 'места групп елей, ломающих длинные лучи обзора внутри территории (tools/sanatorium_ld_plan.py --breaks); '
                    'x, y — схема участка, третье число — сколько длинных лучей ломает группа по оценке',
            'clusters': clusters}, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
        print(f'→ {OUT_BREAKS.relative_to(ROOT)}')
    zones = ['внутри плато', 'с плато к воде', 'у воды', 'склон и спуски']
    out = {'eye': EYE, 'step': STEP, 'rays': RAYS, 'long_m': LONG, 'points': len(pts), 'blockers_taken': taken, 'variants': {}}
    for variant, r in results.items():
        v = {'rays': r['rays'], 'long_rays': r['long'], 'long_share': round(r['long'] / max(1, r['rays']), 4),
             'points_with_long_view': r['pts_long'], 'max_m': round(r['max'], 1), 'zones': {}}
        for z in zones:
            zr = r['zones'][z]
            v['zones'][z] = {'rays': zr['rays'], 'long_rays': zr['long'], 'long_share': round(zr['long'] / max(1, zr['rays']), 4),
                             'max_m': round(zr['max'], 1)}
        v['longest_inside'] = [[round(a, 1) for a in ray] for ray in r['inside_longest'][:40]]
        v['areas'] = {}                            # доля точек, откуда дальше 90 м видно в 6+ направлениях, и без длинных
        for name, f in AREAS:
            sel = [pp for pp in r['per_point'] if f(pp[0], pp[1])]
            if sel:
                v['areas'][name] = {'points': len(sel), 'open6_share': round(sum(1 for pp in sel if pp[3] >= 6) / len(sel), 3),
                                    'closed_share': round(sum(1 for pp in sel if pp[3] == 0) / len(sel), 3)}
        out['variants'][variant] = v
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    draw(scheme, pts, results)
    for variant, v in out['variants'].items():
        print(f'{variant}: точек {len(pts)}, лучей {v["rays"]}, длиннее {LONG:.0f} м — {v["long_share"] * 100:.1f} %, '
              f'точек с таким обзором {v["points_with_long_view"]}, самый длинный {v["max_m"]} м')
        for z, zr in v['zones'].items():
            print(f'   {z}: лучей {zr["rays"]}, длиннее {LONG:.0f} м — {zr["long_share"] * 100:.1f} %, макс {zr["max_m"]} м')
        for name, ar in v['areas'].items():
            print(f'   район «{name}»: 6+ длинных направлений — {ar["open6_share"] * 100:.0f} % точек, без длинных — {ar["closed_share"] * 100:.0f} %')
    print(f'→ {OUT_PNG.relative_to(ROOT)}, {OUT_JSON.relative_to(ROOT)}')


AREAS = [('север: S-корпуса, хоздвор', lambda x, y: y > 60 and x > -80),
         ('центр: главный корпус, парковка, въезд', lambda x, y: -20 < y <= 60 and x > -80),
         ('юг: ресторан и спа, площадка, амфитеатр', lambda x, y: -170 < y <= -20 and x > -80),
         ('коттеджи', lambda x, y: y <= -170 and x > -80),
         ('склон и вода', lambda x, y: x <= -80)]


def zone_of(lo, lt):
    if lo > 25.0 and lt > 25.0:
        return 'внутри плато'
    if lo > 25.0 and lt < 8.0:
        return 'с плато к воде'
    if lo < 8.0 and lt < 8.0:
        return 'у воды'
    return 'склон и спуски'


def cast(pts, S, L):
    nsteps = int(MAX_RAY / CELL)
    ts = (np.arange(nsteps) + 1) * CELL
    angs = 2 * math.pi * np.arange(RAYS) / RAYS
    dx, dy = np.cos(angs), np.sin(angs)
    zones = {z: {'rays': 0, 'long': 0, 'max': 0.0} for z in ('внутри плато', 'с плато к воде', 'у воды', 'склон и спуски')}
    total = long_ = pts_long = 0
    vmax = 0.0
    per_point = []
    inside_longest = []
    long_geo = []
    for (px, py, lv) in pts:
        E = lv + EYE
        qx = px + dx[:, None] * ts[None, :]
        qy = py + dy[:, None] * ts[None, :]
        i = ((qx - X0) / CELL).astype(int)
        j = ((Y1 - qy) / CELL).astype(int)
        ok = (i >= 0) & (i < NX) & (j >= 0) & (j < NY)
        i = np.clip(i, 0, NX - 1)
        j = np.clip(j, 0, NY - 1)
        s = np.where(ok, S[j, i], -50.0)
        l = np.where(ok, L[j, i], np.nan)
        ang_obs = (s - E) / ts[None, :]
        prior = np.maximum.accumulate(ang_obs, axis=1)
        prior = np.concatenate([np.full((RAYS, 2), -1e9), prior[:, :-2]], axis=1)   # своя клетка и соседняя — не преграда
        head = (l + EYE - E) / ts[None, :]
        vis = (head >= prior) & ~np.isnan(l) & (ts[None, :] > 1.5)
        best = 0.0
        nlong = 0
        for k in range(RAYS):
            idx = np.nonzero(vis[k])[0]
            if idx.size == 0:
                continue
            far = idx[-1]
            d = float(ts[far])
            lt = float(l[k, far])
            z = zone_of(lv, lt)
            zones[z]['rays'] += 1
            total += 1
            if d > LONG:
                zones[z]['long'] += 1
                long_ += 1
                long_geo.append((px, py, float(dx[k]), float(dy[k]), d, z))
                if z != 'с плато к воде':
                    nlong += 1
                if z in ('внутри плато', 'склон и спуски', 'у воды'):
                    inside_longest.append((px, py, float(qx[k, far]), float(qy[k, far]), d, z))
            zones[z]['max'] = max(zones[z]['max'], d)
            best = max(best, d)
        vmax = max(vmax, best)
        if best > LONG:
            pts_long += 1
        per_point.append((px, py, best, nlong))
    inside_longest.sort(key=lambda r: -r[4])
    return {'rays': total, 'long': long_, 'pts_long': pts_long, 'max': vmax, 'zones': zones, 'per_point': per_point, 'long_geo': long_geo,
            'inside_longest': [r[:5] for r in inside_longest], 'inside_all': inside_longest}


def draw(scheme, pts, results):
    """Поверх схемы участка: точки по самому длинному обзору (с деревьями), длинные лучи внутри территории — красным."""
    src = Image.open(scheme['OUT']).convert('RGB')
    P = scheme['P']
    x0p, y0p = P(scheme['XMIN'], scheme['YMAX'])
    x1p, y1p = P(scheme['XMAX'], scheme['YMIN'])
    img = src.crop((int(x0p), int(y0p), int(x1p), int(y1p)))
    ox, oy = int(x0p), int(y0p)
    d = ImageDraw.Draw(img, 'RGBA')
    r = results['с деревьями']
    for (x, y, best, nl) in r['per_point']:
        c = (60, 160, 70, 210) if nl == 0 else ((230, 190, 40, 220) if nl <= 2 else ((235, 120, 30, 230) if nl <= 5 else (210, 30, 30, 240)))
        a = P(x, y)
        d.ellipse([a[0] - ox - 2.5, a[1] - oy - 2.5, a[0] - ox + 2.5, a[1] - oy + 2.5], fill=c)
    if OUT_BREAKS.exists():                         # группы елей против длинного обзора — тёмные кольца
        for cx, cy, _ in json.loads(OUT_BREAKS.read_text(encoding='utf-8'))['clusters']:
            a = P(cx, cy)
            d.ellipse([a[0] - ox - 6, a[1] - oy - 6, a[0] - ox + 6, a[1] - oy + 6], outline=(20, 70, 30, 255), width=3)
    for (x, y, x2, y2, dist, z) in r['inside_all'][:150]:
        a, b = P(x, y), P(x2, y2)
        d.line([(a[0] - ox, a[1] - oy), (b[0] - ox, b[1] - oy)], fill=(140, 0, 160, 110), width=1)
    W, H = img.size
    out = Image.new('RGB', (W, H + 150), (247, 245, 239))
    out.paste(img, (0, 0))
    dd = ImageDraw.Draw(out)
    f = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 18)
    f2 = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 14)
    dd.text((14, H + 10), '«Санаторий» · замер обзора по блокауту (схема v12): глаз 1,7 м, точки через 5 м, 24 луча, видно человека', font=f,
            fill=(40, 42, 46))
    y = H + 40
    for variant, rr in results.items():
        share = rr['long'] / max(1, rr['rays']) * 100
        zs = rr['zones']
        dd.text((14, y), f'{variant}: длиннее 90 м — {share:.1f} % лучей; внутри плато {zs["внутри плато"]["long"] / max(1, zs["внутри плато"]["rays"]) * 100:.1f} %, '
                f'с плато к воде {zs["с плато к воде"]["long"] / max(1, zs["с плато к воде"]["rays"]) * 100:.1f} %, '
                f'у воды {zs["у воды"]["long"] / max(1, zs["у воды"]["rays"]) * 100:.1f} %, склон {zs["склон и спуски"]["long"] / max(1, zs["склон и спуски"]["rays"]) * 100:.1f} %',
                font=f2, fill=(40, 42, 46))
        y += 22
    dd.text((14, y + 4), 'точки (с деревьями): сколько из 24 направлений видно дальше 90 м — зелёная 0, жёлтая 1–2, оранжевая 3–5, красная 6 и больше '
            '(без лучей с плато к воде); фиолетовые линии — 150 самых длинных лучей внутри территории; тёмные кольца — группы елей против обзора', font=f2, fill=(90, 92, 96))
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    out.save(OUT_PNG)


if __name__ == '__main__':
    main()
