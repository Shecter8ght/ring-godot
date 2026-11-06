# -*- coding: utf-8 -*-
"""Карта «Вертолёт» v04 → данные серого стенда прогулки и замера (tools/heli_study.tscn).

Рельеф, места, дороги и маршрут вертолёта берутся из наброска tools/mission_helicopter_v04.py (один источник со схемами):
  data/terrain/heli_v04_heights.r32        — карта высот 2 × 3 км, шаг 4 м (float32, метры от уровня озера)
  data/terrain/heli_v04_splat.png          — маска земли шейдера рельефа: R грязь, G камень, B щебень, A лесная подстилка
  data/blockouts/heli_v04.json             — рамки, озеро, плотина, места, постройки-коробки, точки замера, вертолёт
  data/blockouts/heli_v04_vegetation.json  — лес (ели, сосны, берёзы) для DistrictScatter: ядро и фон отдельно
  python -X utf8 tools/mission_helicopter_v04_data.py
Это проба геометрии и производительности, не рейдовая карта и не утверждённый план.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission_helicopter_v04 as v4  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STEP = 4.0
# В мире Godot озеро на 300 м: дно ущелья (−265) остаётся выше нуля, прогулка не сбрасывает игрока.
Y_OFFSET = 300.0
RNG = np.random.default_rng(4)

ROADS = [
    [v4.A, (-520, -320), v4.WAREHOUSE, (-430, -150), (-470, -50), (-400, 40), v4.VILLAGE, (-360, 260), v4.SAWMILL,
     (-300, 380), (-225, 448)],
    [(-360, 260), (-460, 440), v4.W],
    [(225, 448), (300, 350), (330, 220), v4.SAN, (300, -60), (260, -200), (420, -300), v4.B],
    [v4.D, (520, 650), v4.AD],
    [(-400, 40), (-260, -150)],
    [(30, 520), (0, 560), (-40, 700), (-20, 900), v4.C],
    # вторая очередь — к мосту у хвоста озера
    [(-260, -150), (-280, -420), (-200, -650), (-90, -820), (-60, -880)],
    [(60, -880), (130, -780), (260, -560), (290, -330)],
]
TRAILS = [
    [v4.A, (-560, -200), v4.V1, (-560, 60), (-560, 300), v4.W],
    [v4.W, (-470, 560), (-330, 600), (-250, 480)],
    [v4.VILLAGE, (-470, 80), (-540, 0), v4.V1],
    [v4.B, (560, -250), v4.V3, (540, 100), (560, 350), v4.AD],
    [v4.AD, (400, 600), (340, 700)],
    [(225, 448), (290, 480), (330, 440), (380, 500), v4.AD],
    [(340, 0), (280, 30), (300, 70), (245, 80)],
    [(420, 150), (330, 140), (290, 110), (245, 100)],
    [(400, 20), (450, -20), (470, -80), (455, -140), (440, -200)],
]
CLEARCUT = [(-570, -115), (-480, -125), (-468, -55), (-560, -45)]


def xz(p):
    return float(p[0]), float(p[1])


def polyline_distance(X, Z, lines):
    best = np.full(X.shape, 1e9)
    for line in lines:
        pts = [xz(p) for p in line]
        for a, b in zip(pts, pts[1:]):
            dx, dz = b[0] - a[0], b[1] - a[1]
            t = np.clip(((X - a[0]) * dx + (Z - a[1]) * dz) / (dx * dx + dz * dz), 0, 1)
            best = np.minimum(best, np.hypot(X - a[0] - t * dx, Z - a[1] - t * dz))
    return best


def in_polygon(X, Z, poly):
    inside = np.zeros(X.shape, bool)
    n = len(poly)
    for i in range(n):
        x1, z1 = poly[i]
        x2, z2 = poly[(i + 1) % n]
        cross = ((z1 > Z) != (z2 > Z)) & (X < (x2 - x1) * (Z - z1) / (z2 - z1 + 1e-9) + x1)
        inside ^= cross
    return inside


def lake_bed(X, Z, h, lake):
    xw = np.interp(Z, v4.WEST[:, 0], v4.WEST[:, 1])
    xe = np.interp(Z, v4.EAST[:, 0], v4.EAST[:, 1])
    inside = np.minimum(X - xw, xe - X)
    return np.where(lake, -np.minimum(1.2 + inside * 0.3, 60.0), h)


def slope_of(X, Z):
    e = 2.0
    hx = (v4.heights(X + e, Z)[0] - v4.heights(X - e, Z)[0]) / (2 * e)
    hz = (v4.heights(X, Z + e)[0] - v4.heights(X, Z - e)[0]) / (2 * e)
    return np.hypot(hx, hz)


def terrain():
    xs = np.arange(v4.VIS[0], v4.VIS[1] + STEP / 2, STEP)
    zs = np.arange(v4.VIS[2], v4.VIS[3] + STEP / 2, STEP)
    X, Z = np.meshgrid(xs, zs)
    h, lake = v4.heights(X, Z)
    h = lake_bed(X, Z, h, lake)
    out = ROOT / 'data' / 'terrain'
    out.mkdir(parents=True, exist_ok=True)
    h.astype('<f4').tofile(out / 'heli_v04_heights.r32')
    # маска земли: грязь у воды и на тропах, камень высоко, щебень на дорогах и промплощадках, подстилка в лесу
    road = polyline_distance(X, Z, ROADS)
    trail = polyline_distance(X, Z, TRAILS)
    mud = np.clip(1 - np.abs(h - 1.0) / 3.0, 0, 1) * (~lake) + np.clip(1 - trail / 2.5, 0, 1)
    rock = np.clip((h - 660) / 80, 0, 1)
    gravel = np.clip(1 - (road - 3.5) / 2.5, 0, 1)
    for x, z, r in ((0, 520, 120), (-95, 620, 50), (115, 700, 70), (-480, -250, 80), (450, 520, 60), (-340, 300, 60),
                    (360, 320, 50), (-300, 490, 45)):
        gravel = np.maximum(gravel, np.clip(1 - (np.hypot(X - x, Z - z) - r) / 10, 0, 1) * 0.8)
    floor_ = np.clip((h - 8) / 20, 0, 1) * np.clip((700 - h) / 60, 0, 1) * (1 - gravel)
    rgba = np.stack([mud, rock, gravel, floor_], -1)
    Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), 'RGBA').save(out / 'heli_v04_splat.png')
    return xs.size, zs.size


SPECIES = {
    'spruce_a': ('spruce_forest_a', 0.3),
    'spruce_b': ('spruce_forest_b', 0.3),
    'spruce_young': ('spruce_young_a', 0.2),
    'pine': ('pine_forest', 0.3),
    'pine_slim': ('pine_slim_a', 0.25),
    'birch': ('birch_a', 0.21),
}


def forest():
    """Лес: дрожащая сетка, в ядре чаще (6,5 м — ~170 деревьев на га, как плотный ельник зоны 1), фоном реже (9 м);
    не на воде, дорогах, площадках, скалах. Стенд может прореживать (HELI_FOREST) — замер «лес гуще / реже»."""
    keep_out = [(x, z, r) for x, z, _, r, _ in v4.PADS] + [(e[3][0], e[3][1], 22.0) for e in v4.EXTRAS]
    keep_out += [(0, 485, 90), (-95, 620, 60), (115, 700, 80), (330, -40, 45), (490, 190, 45), (430, 70, 60)]
    points = {}
    totals = {'core': 0, 'bg': 0}
    for spacing, part in ((6.5, 'core'), (9.0, 'bg')):
        gx = np.arange(v4.VIS[0], v4.VIS[1], spacing)
        gz = np.arange(v4.VIS[2], v4.VIS[3], spacing)
        X, Z = np.meshgrid(gx, gz)
        X = X + RNG.uniform(-0.45, 0.45, X.shape) * spacing
        Z = Z + RNG.uniform(-0.45, 0.45, Z.shape) * spacing
        w = v4.WALKABLE
        core = (X > w[0] - 40) & (X < w[1] + 40) & (Z > w[2] - 40) & (Z < w[3] + 40)
        sel = core if part == 'core' else ~core
        X, Z = X[sel], Z[sel]
        h, lake = v4.heights(X, Z)
        slope = slope_of(X, Z)
        ok = (~lake) & (h > 1.5) & (h < 720) & (slope < (1.05 if part == 'core' else 1.2))
        ok &= polyline_distance(X, Z, ROADS) > 7.0
        ok &= polyline_distance(X, Z, TRAILS) > 2.5
        for x, z, r in keep_out:
            ok &= np.hypot(X - x, Z - z) > r + 6
        dam_zone = (np.abs(X) < 300) & (Z > 360) & (Z < 530)
        ok &= ~dam_zone
        ok &= ~in_polygon(X, Z, CLEARCUT)
        prob = np.full(X.shape, 0.85)
        for x, z in (xz(v4.VILLAGE), xz(v4.SAN), xz(v4.SAWMILL)):
            prob = np.where(np.hypot(X - x, Z - z) < 230, 0.3, prob)
        prob = np.where(h < -200, 0.12, prob)
        ok &= RNG.random(X.shape) < prob
        X, Z, h, slope = X[ok], Z[ok], h[ok], slope[ok]
        roll = RNG.random(X.shape)
        near_people = np.zeros(X.shape, bool)
        for x, z in (xz(v4.VILLAGE), xz(v4.SAN), xz(v4.SAWMILL)):
            near_people |= np.hypot(X - x, Z - z) < 420
        kind = np.where(roll < 0.35, 'spruce_a', np.where(roll < 0.7, 'spruce_b', 'spruce_young'))
        kind = np.where((h > 330) | (slope > 0.6), np.where(roll < 0.6, 'pine', 'pine_slim'), kind)
        kind = np.where(near_people & (h < 140) & (roll < 0.5), 'birch', kind)
        rot = RNG.uniform(0, 360, X.shape)
        scale = RNG.uniform(0.8, 1.2, X.shape)
        for k in SPECIES:
            m = kind == k
            key = k if part == 'core' else k + '_bg'
            points[key] = [[round(float(a), 2), round(float(b) + Y_OFFSET - 0.1, 2), round(float(c), 2),
                            round(float(r), 1), round(float(s), 3)] for a, b, c, r, s in
                           zip(X[m], h[m], Z[m], rot[m], scale[m])]
            totals[part] += int(m.sum())
    out = ROOT / 'data' / 'blockouts' / 'heli_v04_vegetation.json'
    out.write_text(json.dumps(points, ensure_ascii=False, separators=(',', ':')), encoding='utf-8', newline='\n')
    return totals


def box(x, z, w, l, h, mat='building', yaw=0.0, base=None, group=''):
    return {'kind': 'box', 'x': x, 'z': z, 'w': w, 'l': l, 'h': h, 'yaw': yaw, 'base': base, 'mat': mat, 'group': group}


def cyl(x, z, r, h, mat='concrete', base=None, group=''):
    return {'kind': 'cyl', 'x': x, 'z': z, 'r': r, 'h': h, 'base': base, 'mat': mat, 'group': group}


def beam(a, b, y, r, mat='metal', group=''):
    """Тонкая балка или трос между двумя точками на абсолютной высоте (от уровня озера)."""
    return {'kind': 'beam', 'a': [a[0], a[1], a[2] if len(a) > 2 else y], 'b': [b[0], b[1], b[2] if len(b) > 2 else y],
            'r': r, 'mat': mat, 'group': group}


def ring_wing(cx, cz, start_deg, end_deg, radius, group):
    """Крыло S-корпуса — дуга из коробок номерной полосы (8 м) и коридора (3 м), 3 этажа."""
    parts = []
    steps = 12
    for i in range(steps):
        a = math.radians(start_deg + (end_deg - start_deg) * (i + 0.5) / steps)
        x = cx + radius * math.cos(a)
        z = cz + radius * math.sin(a)
        seg = 2 * math.pi * radius * abs(end_deg - start_deg) / 360 / steps
        parts.append(box(round(x, 1), round(z, 1), 11.0, round(seg + 0.6, 1), 11.5, 'building',
                         round(-math.degrees(a), 1), None, group))
    return parts


def structures():
    s = []
    # 1 посёлок: 12 участков, дома, клуб
    for i in range(12):
        col, row = i % 2, i // 2
        x = -440 + col * 70 + (row % 2) * 12
        z = 20 + row * 38
        s.append(box(x - 4, z - 2, 10, 8, 6.5, 'house', 0, None, 'посёлок'))
        s.append(box(x + 9, z + 7, 4, 5, 2.6, 'wood', 0, None, 'посёлок'))
    s.append(box(-330, 70, 20, 12, 7.5, 'building', 0, None, 'посёлок'))
    # 2 лесопилка
    s += [box(-340, 312, 60, 20, 9, 'metal_shed', 0, None, 'лесопилка'), box(-395, 340, 28, 14, 6, 'wood', 0, None, 'лесопилка')]
    s += [box(-400 + i * 16, 272, 9, 24, 3, 'logs', 0, None, 'лесопилка') for i in range(4)]
    # 3 склад ПЗРК: ограда, три склада, вышка
    for a, b in (((-560, -310), (-400, -310)), ((-400, -310), (-400, -200)), ((-400, -200), (-560, -200)),
                 ((-560, -200), (-560, -310))):
        s.append({'kind': 'wall', 'a': list(a), 'b': list(b), 'h': 2.6, 't': 0.25, 'mat': 'concrete', 'group': 'склад'})
    s += [box(-510 + i * 50, -260, 40, 14, 7, 'military', 0, None, 'склад') for i in range(3)]
    s.append(box(-415, -295, 4, 4, 12, 'wood', 0, None, 'склад'))
    # 4 старая ПВО: антенна, пусковые, бункер
    s.append(cyl(v4.AD[0], v4.AD[1], 6, 9, 'metal', None, 'ПВО'))
    for ang in range(0, 360, 90):
        s.append(box(round(v4.AD[0] + 40 * math.cos(math.radians(ang + 45)), 1),
                     round(v4.AD[1] + 40 * math.sin(math.radians(ang + 45)), 1), 7, 7, 2.5, 'military', ang, None, 'ПВО'))
    s.append(box(v4.AD[0] + 10, v4.AD[1] - 55, 22, 10, 4, 'concrete', 0, None, 'ПВО'))
    # 5 санаторий: главный корпус, два S-корпуса (второй — на ремонте), стоянки
    s.append(box(430, 70, 26, 100, 13, 'building', 0, None, 'санаторий'))
    for cx, cz in ((330, -40), (490, 190)):
        s += ring_wing(cx, cz - 30, 40, 320, 25, 'санаторий')
        s += ring_wing(cx, cz + 30, 220, 500, 25, 'санаторий')
        s.append(box(cx, cz, 24, 20, 13, 'building', 0, None, 'санаторий'))
    # 6 плотина — отдельной сеткой (dam); 7 нижняя ГЭС: машзал, двор, ОРУ
    s.append(box(0, 488, 130, 26, 28, 'concrete', 0, None, 'ГЭС'))
    s += [box(-110, 610, 30, 18, 7, 'building', 0, None, 'ГЭС'), box(-80, 640, 24, 12, 5, 'metal_shed', 0, None, 'ГЭС')]
    for i in range(4):
        for j in range(3):
            s.append(box(70 + i * 30, 670 + j * 30, 6, 4, 5, 'metal', 0, None, 'ГЭС'))
    # 8 водоприёмная башня в озере, мостик к берегу
    s.append(cyl(150, 360, 8, 59, 'concrete', -45, 'остановки'))
    s.append({'kind': 'deck', 'a': [158, 359], 'b': [236, 350], 'y': 13.0, 'w': 3.0, 't': 0.6, 'mat': 'concrete',
              'group': 'остановки'})
    # лестница по западной стене ущелья (марши — наклонными настилами по точкам наброска)
    for a, b in zip(v4.STAIRS, v4.STAIRS[1:]):
        s.append({'kind': 'deck', 'a': list(map(float, a)), 'b': list(map(float, b)), 'w': 2.4, 't': 0.5, 'mat': 'metal',
                  'group': 'ГЭС'})
    # 9 бетонный завод: силосы, цех, транспортёр
    s += [cyl(x, 478, 6, 28, 'concrete', None, 'остановки') for x in (-322, -306, -290)]
    s.append(box(-300, 505, 44, 20, 12, 'metal_shed', 0, None, 'остановки'))
    s.append(beam((-290, 480, 30), (-228, 452, 14), 0, 1.5, 'metal', 'остановки'))
    # 10 кабель-кран: две башни, трос, бадья
    for x in (-290, 290):
        s.append(box(x, 540, 6, 6, 40, 'metal', 0, None, 'остановки'))
    s.append({'kind': 'tower_cable', 'a': [-290, 540], 'b': [290, 540], 'top': 40, 'r': 0.12, 'mat': 'metal',
              'group': 'остановки'})
    s.append(box(0, 540, 3, 3, 3, 'metal', 0, 20, 'остановки'))
    # 11 водонапорная башня, 12 пожарная вышка и ретранслятор
    s += [cyl(-470, 170, 2.5, 18, 'concrete', None, 'остановки'), cyl(-470, 170, 5, 6, 'metal', 'top+18', 'остановки')]
    s.append(box(-570, 330, 4, 4, 25, 'wood', 0, None, 'остановки'))
    s += [box(540, -120, 2, 2, 40, 'metal', 0, None, 'остановки'), box(546, -120, 4, 3, 3, 'building', 0, None, 'остановки')]
    # 13 служебный городок ГЭС
    s += [box(360, 315, 40, 18, 10, 'building', 0, None, 'остановки'), box(398, 300, 26, 14, 6, 'metal_shed', 0, None, 'остановки'),
          box(340, 352, 16, 8, 4, 'building', 0, None, 'остановки')]
    # 14 ЛЭП: опоры и провод
    towers = [(115, 700), (210, 706), (310, 712), (410, 716), (510, 712), (570, 705)]
    for t in towers[1:-1]:
        s.append(box(t[0], t[1], 4, 4, 30, 'metal', 0, None, 'остановки'))
    s.append({'kind': 'tower_cable', 'a': list(towers[1]), 'b': list(towers[-2]), 'top': 29, 'r': 0.08, 'mat': 'metal',
              'group': 'остановки', 'via': [list(t) for t in towers[2:-2]]})
    s.append(box(575, 705, 30, 24, 4, 'metal', 0, None, 'остановки'))
    # 15 ж/д ветка: вагоны
    s += [box(40, z, 3.2, 14, 4, 'metal', 0, None, 'остановки') for z in (775, 800, 825)]
    # 16 КПП, 17 казармы, 18 беседки терренкура
    s += [box(-440, -170, 4, 3, 3, 'building', 0, None, 'остановки'), box(-440, -160, 10, 0.3, 1.1, 'metal', 0, None, 'остановки')]
    s += [box(520, 582, 34, 12, 7, 'military', 0, None, 'остановки'), box(548, 605, 30, 12, 7, 'military', 0, None, 'остановки'),
          box(515, 620, 20, 10, 5, 'military', 0, None, 'остановки')]
    s += [box(x, z, 4, 4, 3, 'wood', 0, None, 'остановки') for x, z in ((450, -20), (470, -80), (455, -140))]
    # 19 пирс, лодочная станция, кафе; 20 дебаркадер с понтонами; 21 рыбацкие домики, гидропост
    s += [box(209, 92, 58, 3, 0.6, 'wood', 0, 0.3, 'остановки'), box(244, 60, 14, 10, 5, 'wood', 0, None, 'остановки'),
          box(262, 125, 12, 10, 4, 'building', 0, None, 'остановки')]
    s += [box(-120, -365, 40, 12, 4, 'metal', 0, -0.6, 'остановки'), box(-172, -362, 66, 2.2, 0.5, 'wood', 0, 0.0, 'остановки')]
    s += [box(255, -300, 8, 6, 3, 'wood', 0, None, 'остановки'), box(262, -278, 8, 6, 3, 'wood', 0, None, 'остановки'),
          cyl(235, -330, 1, 3, 'metal', None, 'остановки')]
    # 22 пункт сбора: автобусы, палатки; 23 лодочная станция посёлка; 24 делянка; 25 вагон-городок
    s += [box(x, 252, 2.5, 12, 3.2, 'bus', 0, None, 'остановки') for x in (-410, -390)]
    s += [box(x, z, 4, 4, 2.5, 'tent', 0, None, 'остановки') for x, z in ((-450, 228), (-438, 238), (-455, 248), (-443, 220))]
    s += [box(-262, 200, 14, 10, 4, 'wood', 0, None, 'остановки'), box(-238, 200, 26, 2.5, 0.6, 'wood', 0, 0.3, 'остановки')]
    s += [box(x, -90, 10, 4, 2, 'logs', 0, None, 'остановки') for x in (-540, -520, -500)]
    s += [box(-82, z, 22, 9, 3.5, 'wood', 0, None, 'остановки') for z in (975, 995, 1015)]
    # боны поперёк озера
    xw = float(np.interp(-400, v4.WEST[:, 0], v4.WEST[:, 1]))
    xe = float(np.interp(-400, v4.EAST[:, 0], v4.EAST[:, 1]))
    s += [box(round(x, 1), -400, 2.4, 1.2, 0.6, 'buoy', 0, -0.2, 'боны') for x in np.arange(xw + 4, xe - 2, 6)]
    return s


def places():
    out = [
        ('1 · Посёлок', v4.VILLAGE, (-360, 260)),
        ('2 · Лесопилка', v4.SAWMILL, (-225, 448)),
        ('3 · Склад ПЗРК', v4.WAREHOUSE, (-440, -170)),
        ('4 · Старая ПВО', v4.AD_BROW, (0, 200)),
        ('5 · Санаторий', (330, 70), (0, 420)),
        ('6 · Гребень плотины', (0, 397, 11.7), (0, -500)),
        ('7 · Машзал ГЭС', (-30, 560), (0, 430)),
        ('9 · Бетонный завод', (-270, 470), (0, 420)),
        ('8 · Мостик к водоприёмной башне', (230, 350, 15.0), (150, 360)),
        ('V1 · Смотровая, западный хребет', v4.V1, (150, 250)),
        ('V3 · Смотровая, восточный хребет', v4.V3, (-150, 250)),
        ('13 · Служебный городок ГЭС', (330, 330), (360, 315)),
        ('22 · Пункт сбора «эвакуации»', (-470, 250), (-400, 252)),
        ('24 · Делянка (K1)', (-520, -160), (-515, -85)),
        ('21 · Каменистый берег (K2)', (240, -260), (100, -260)),
        ('25 · Вагон-городок (K3)', (-60, 950), (-82, 995)),
        ('W · Выход', v4.W, (-360, 260)),
        ('B · Заход', v4.B, (300, 0)),
        ('C · Заход в ущелье', (-90, 1150), (0, 600)),
        ('A · Выход у склада', v4.A, (-480, -250)),
        ('D · Выход у ПВО', v4.D, (450, 520)),
    ]
    # точка: (x, z) — на земле; третье число только у гребня и мостика — высота глаз от уровня озера
    eye = {'6 · Гребень плотины', '8 · Мостик к водоприёмной башне'}
    return [{'name': n, 'at': [float(v) for v in (at if n in eye else at[:2])], 'look': [float(v) for v in look[:2]]}
            for n, at, look in out]


VIEWS = [
    ('гребень_на_озеро', (0, 397, 11.7), (0, -500, 60)),
    ('гребень_в_ущелье', (0, 408, 13.0), (-40, 900, -230)),
    ('пво_у_бровки', (v4.AD_BROW[0], v4.AD_BROW[1]), (0, 100, 40)),
    ('хребет_запад', (v4.V1[0], v4.V1[1]), (150, 250, 40)),
    ('хребет_восток', (v4.V3[0], v4.V3[1]), (-150, 250, 20)),
    ('санаторий_терраса', (330, 70), (0, 420, 10)),
    ('посёлок', (-400, 80), (-360, 260, 25)),
    ('ущелье_у_машзала', (-30, 700), (0, 430, -120)),
    ('лес_на_склоне', (-520, -170), (-430, -60, 140)),
    ('сверху', (0, 250, 1100), (0, 380, 0)),
]


def main():
    cols, rows = terrain()
    trees = forest()
    dam = {'apex': v4.APEX, 'radius': v4.R_ARC, 'half_angle_deg': math.degrees(math.asin(246 / v4.R_ARC)),
           'crest': 10.0, 'foot': -255.0, 'thick_top': 10.0, 'thick_base': 60.0, 'parapet': 1.1}
    plan = {
        'name': 'Вертолёт · v04 · серый стенд',
        'y_offset': Y_OFFSET,
        'terrain': {'heights': 'res://data/terrain/heli_v04_heights.r32', 'origin': [v4.VIS[0], v4.VIS[2]],
                    'grid': [cols, rows], 'step': STEP, 'layer_tiles': [3.0, 3.0, 2.5, 3.0, 4.0, 2.0],
                    'textures': {'albedo_array': 'res://assets/terrain/zone01_albedo.jpg',
                                 'normal_array': 'res://assets/terrain/zone01_normal.jpg',
                                 'arm_array': 'res://assets/terrain/zone01_arm.jpg',
                                 'noise': 'res://assets/terrain/zone01_noise.png'},
                    'splat_file': 'res://data/terrain/heli_v04_splat.png'},
        'walkable': list(v4.WALKABLE),
        'lake': {'west': v4.WEST.tolist(), 'east': v4.EAST.tolist(), 'tail_z': -820.0, 'boom_z': -400.0},
        'river_north': v4.NORTH_RIVER.tolist(),
        'river_gorge': v4.GORGE.tolist(),
        'dam': dam,
        'structures': structures(),
        'places': places(),
        'views': [{'name': n, 'at': list(map(float, at)), 'look': list(map(float, look))} for n, at, look in VIEWS],
        'heli': [list(map(float, q)) for q in v4.HELI],
        'heli_speed': v4.HELI_SPEED,
        'plan_image': 'res://docs/plans/mission_helicopter_v04_plan_core.png',
        'plan_image_rect': [v4.WALKABLE[0] - 20, v4.WALKABLE[2] - 30, v4.WALKABLE[1] + 20, v4.WALKABLE[3] + 20],
        'trees': trees,
    }
    out = ROOT / 'data' / 'blockouts' / 'heli_v04.json'
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    print(f'рельеф {cols}×{rows} (шаг {STEP:.0f} м), деревьев: ядро {trees["core"]}, фон {trees["bg"]}, '
          f'построек {len(plan["structures"])}')


if __name__ == '__main__':
    main()
