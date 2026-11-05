"""ИЗЛОМ-45, износ v2 — маски МЕСТ по указанию владельца (05.11) в развёртке атласов: по картам положения и нормали
(game_tex.py, стадия maps → <набор>_maps.npz). Рисунок кромок в этих местах даёт генератор Painter (sp_smg03_wear.py),
а следы со своей формой (дуги флажков, бетонная царапина, разводы ладони, полоски вдоль паза) рисуются здесь же.

    python -X utf8 tools/smg03/wear_zones.py
→ _asset_src/smg03/tex/wear/<набор>_<место>.png (8 бит, белое — след есть) и <набор>_zones_preview.png.

Места (владелец, по пунктам):
 1. рукоятка заряжания — чуть-чуть (сеткой в Painter) и вдоль паза её хода: slot;
 2. планки чистые по всей длине, на верхней — три участка износа: rail_spots; rails — маска планок (из общего износа
    вычитается), в углублениях планок немного пыли;
 3. передний торец — правое ребро: front_r; слева — только верхний угол, чуть-чуть: front_tl;
 4. кнопки сброса магазина — сетками в Painter;
 5. цевьё (передний блок, где держат): разводы ладони и отпечатки hand_prints, светлее тоном hand_tone;
 6. рукоять — сзади, спереди и правая щёчка глаже и светлее градиентом от ладони: grip;
 7. кнопки задержки — сеткой в Painter;
 8. задний торец (крепление приклада), левое ребро — до металла, как о бетонную стену: rear_scrape;
 9. бороздки по ходу лепестков переводчика и предохранителя: arcs;
10. остальной износ корпуса — реже и слабее (в Painter).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / '_asset_src/smg03/tex'
OUT = TEX / 'wear'
MASKS = Path('E:/Models Blender/Маски_АЛЬФА/50_Скачанные_CC0_ambientCG_ShareTextures/ambientCG')
sys.path.insert(0, str(ROOT / 'tools/smg03'))

HALF_W = 21.75
RAIL_BASE = 46.5
RAIL_HALF_W = 10.6
FRONT_X = 107.8
REAR_X = -266.0
LOW_RAIL_X = (24.0, 102.5)
CH_SLOT_X = (-62.0, 74.0)
CH_SLOT_Z = (17.6, 23.4)
SAFETY_PIVOT = (-183.5, 39.0)
SELECTOR_PIVOT = (-72.0, 38.5)
RES = 20.0                         # пикс/мм полей узоров


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def field(seed, u0, u1, v0, v1, sig_u, sig_v, res=RES):
    """Гладкий шум 0..1 на прямоугольнике (мм) с разной длиной пятен по двум осям; выборка — sample()."""
    rng = np.random.default_rng(seed)
    w, h = int((u1 - u0) * res) + 8, int((v1 - v0) * res) + 8
    f = rng.standard_normal((h, w)).astype(np.float32)
    f = cv2.GaussianBlur(f, (0, 0), sigmaX=max(sig_u * res, 0.5), sigmaY=max(sig_v * res, 0.5))
    f = (f - f.mean()) / (f.std() + 1e-6)
    return (f, u0, v0, res)


def sample(fd, u, v):
    f, u0, v0, res = fd
    return cv2.remap(f, ((u - u0) * res).astype(np.float32), ((v - v0) * res).astype(np.float32), cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REFLECT)


def stamp_image(path, size_mm, u, v, cu, cv_, rot_deg=0.0, flip=False):
    """Картинка-маска (0..1) плоской проекцией: центр (cu, cv_) мм, сторона size_mm, поворот."""
    im = cv2.imdecode(np.fromfile(str(path), np.uint8), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255.0
    if flip:
        im = im[:, ::-1]
    h, w = im.shape
    a = math.radians(rot_deg)
    du, dv = u - cu, v - cv_
    ru = du * math.cos(a) + dv * math.sin(a)
    rv = -du * math.sin(a) + dv * math.cos(a)
    px = (ru / size_mm + 0.5) * w
    py = (0.5 - rv / size_mm * w / h) * h
    out = cv2.remap(im, px.astype(np.float32), py.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                    borderValue=0.0)
    return out


def side_face(pos, nrm, filled, sgn, tol=0.9):
    """Пиксели борта коробки со стороны sgn (+1 слева, −1 справа)."""
    return filled & (nrm[..., 1] * sgn > tol) & (pos[..., 1] * sgn > HALF_W - 0.8)


# ------------------------------------------------------------------------------------------------- места верха
def rails(pos, nrm, filled):
    """Верхняя и нижняя планки (зубья, пазы, бока) — из общего износа вычитаются."""
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    top = smooth(RAIL_BASE - 0.6, RAIL_BASE + 0.4, z) * (1 - smooth(RAIL_HALF_W + 0.3, RAIL_HALF_W + 1.3, np.abs(y)))
    low = (1 - smooth(-21.5, -20.5, z)) * smooth(LOW_RAIL_X[0] - 1.5, LOW_RAIL_X[0], x) * \
        (1 - smooth(LOW_RAIL_X[1], LOW_RAIL_X[1] + 1.5, x)) * (1 - smooth(RAIL_HALF_W + 0.3, RAIL_HALF_W + 1.3, np.abs(y)))
    return np.where(filled, np.maximum(top, low), 0.0)


def rail_spots(pos, nrm, filled):
    """Три участка износа на верхней планке (где ставят и снимают прицел, кольца и мушку): мягкие края по X."""
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    on = smooth(RAIL_BASE + 1.0, RAIL_BASE + 2.0, z) * (1 - smooth(RAIL_HALF_W + 0.3, RAIL_HALF_W + 1.3, np.abs(y)))
    m = np.zeros_like(x)
    for x0, x1, k in ((-229.0, -213.0, 0.8), (-118.0, -92.0, 1.0), (38.0, 58.0, 0.7)):
        m = np.maximum(m, k * smooth(x0 - 3.0, x0, x) * (1 - smooth(x1, x1 + 3.0, x)))
    return np.where(filled, m * on, 0.0)


def slot(pos, nrm, filled):
    """Вдоль паза рукоятки заряжания (слева): кромки паза и стенки у устья — продольные потёртости по ходу рукоятки."""
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    zc, zr = (CH_SLOT_Z[0] + CH_SLOT_Z[1]) / 2, (CH_SLOT_Z[1] - CH_SLOT_Z[0]) / 2
    # расстояние до контура паза (пилюля) в плоскости борта
    xc = np.clip(x, CH_SLOT_X[0] + zr, CH_SLOT_X[1] - zr)
    d = np.hypot(x - xc, z - zc) - zr                           # >0 снаружи паза
    face = (pos[..., 1] > HALF_W - 0.8) & (nrm[..., 1] > 0.5)
    rim = face * (1 - smooth(0.4, 1.8, d)) * (d > -0.2)
    depth = HALF_W - pos[..., 1]                                # от устья паза внутрь
    wall = (depth > -0.1) & (depth < 2.2) & (np.abs(nrm[..., 2]) > 0.5) & (d < 0.3)
    wall = wall * (1 - smooth(0.4, 2.2, depth))
    zone = np.maximum(rim, wall * 0.9)
    # полосы вдоль X: шум, вытянутый по ходу рукоятки; сильнее посередине хода, к концам паза слабее
    fd = field(11, -70.0, 80.0, 14.0, 27.0, 8.0, 0.12)
    s = np.clip(sample(fd, x, z) * 0.6 + 0.45, 0.0, 1.0)
    along = smooth(CH_SLOT_X[0], CH_SLOT_X[0] + 25.0, x) * (1 - smooth(CH_SLOT_X[1] - 25.0, CH_SLOT_X[1], x))
    return np.where(filled, zone * s * (0.35 + 0.65 * along), 0.0)


def front_r(pos, nrm, filled):
    """Передний торец — правое вертикальное ребро (с борта на торец) по всей высоте блока."""
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    e = (FRONT_X - x) + (y + HALF_W)                            # у ребра оба малы
    m = (1 - smooth(1.5, 5.0, e)) * smooth(-21.0, -18.0, z) * (1 - smooth(45.0, 48.0, z)) * (x > 98.0) * (y < -12.0)
    return np.where(filled, m, 0.0)


def front_tl(pos, nrm, filled):
    """Передний торец — слева только верхний угол, чуть-чуть."""
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    d = np.sqrt(np.maximum(FRONT_X - x, 0) ** 2 + np.maximum(HALF_W - y, 0) ** 2 + np.maximum(48.5 - z, 0) ** 2)
    m = 1 - smooth(2.0, 6.0, d)
    return np.where(filled & (x > 98.0), m * 0.6, 0.0)


def rear_scrape(pos, nrm, filled):
    """Задний торец (крепление приклада), левое ребро: ссадина до металла, будто прошлись о бетонную стену — от ребра
    на борт до ~6 мм и на торец до ~2 мм; частые короткие риски сверху вниз под небольшим углом, рваный край. Прямая
    сторона — только у самого ребра (владелец: такую отметину вести от ребра и в одном месте)."""
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    # расстояние от ребра: по борту — от торца, по торцу — от борта
    on_side = (nrm[..., 1] > 0.5)
    on_rear = (nrm[..., 0] < -0.5)
    dist = np.where(on_side, x - REAR_X, np.where(on_rear, HALF_W - y, 1e3))
    dist = np.where(on_side | on_rear, dist, (x - REAR_X) + (HALF_W - y))
    # рваный край: глубина ссадины меняется вдоль ребра
    fe = field(21, 10.0, 52.0, -4.0, 4.0, 2.5, 2.5)
    reach = 3.2 + 2.2 * np.clip(sample(fe, z, np.zeros_like(z)), -1.4, 1.4) + 1.2 * np.sin((z - 26.0) / 14.0 * math.pi)
    reach = np.where(on_rear, reach * 0.35, reach)
    band = smooth(24.0, 27.0, z) * (1 - smooth(39.0, 42.5, z))
    edge = (1 - smooth(reach * 0.6, reach, dist)) * band * (y > HALF_W - 4.0) * (x < REAR_X + 9.0)
    # риски: вдоль направления под 15° к вертикали, тонкие, частые; их обрывки
    a = math.radians(15.0)
    u = x * math.cos(a) - z * math.sin(a)
    v = x * math.sin(a) + z * math.cos(a)
    fs = field(22, -280.0, -240.0, -60.0, 60.0, 0.05, 1.6, res=40.0)
    lines = np.clip(sample(fs, u, v) * 0.9 + 0.2, 0.0, 1.0)
    fb = field(23, -280.0, -240.0, 0.0, 60.0, 0.8, 0.8)
    breaks = smooth(-0.6, 0.4, sample(fb, x, z))
    m = edge * np.clip(0.55 * lines + 0.45 * breaks, 0.0, 1.0)
    m = np.maximum(m, edge * (1 - smooth(0.0, 0.8, dist)))      # у самого ребра — сплошь
    return np.where(filled, m, 0.0)


def arcs(pos, nrm, filled):
    """Бороздки по ходу лепестков: дуги вокруг осей переводчика и предохранителя на обоих бортах, там, где ходит носок
    лепестка; тонкие, разной длины и силы."""
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    face = (np.abs(nrm[..., 1]) > 0.85) & (np.abs(y) > HALF_W - 0.8)
    out = np.zeros_like(x)
    rng = np.random.default_rng(31)
    for (px, pz), (r0, r1), (a0, a1) in ((SAFETY_PIVOT, (9.0, 15.5), (186.0, 252.0)),
                                         (SELECTOR_PIVOT, (8.5, 14.5), (-88.0, -6.0))):
        dx, dz = x - px, z - pz
        r = np.hypot(dx, dz)
        ang = np.degrees(np.arctan2(dz, dx))
        if a0 > 180.0:
            ang = np.where(ang < 0, ang + 360.0, ang)
        for k in range(11):
            rk = rng.uniform(r0, r1)
            wk = rng.uniform(0.05, 0.11)
            span = rng.uniform(0.35, 1.0) * (a1 - a0)
            s0 = rng.uniform(a0, a1 - span)
            ik = rng.uniform(0.45, 1.0)
            line = np.exp(-((r - rk) / wk) ** 2)
            along = smooth(s0, s0 + 6.0, ang) * (1 - smooth(s0 + span - 6.0, s0 + span, ang))
            out = np.maximum(out, ik * line * along)
    return np.where(filled & face, out, 0.0)


def hand(pos, nrm, filled):
    """Цевьё (передний блок под боковыми планками), где держит вторая рука: светлее тоном (вытерто) — мягкий градиент;
    разводы ладони (ambientCG Smear, CC0) и отпечатки (Fingerprints, CC0) плоской проекцией на борта."""
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    block = (x > 24.0) & (np.abs(nrm[..., 1]) > 0.7) & (np.abs(y) > HALF_W - 0.8) & (z < 14.0) & (z > -22.0)
    tone = np.exp(-(((x - 62.0) / 30.0) ** 2 + ((z + 3.0) / 13.0) ** 2))
    prints = np.zeros_like(x)
    left = y > 0
    for sgn, stamps in ((1, [("Smear004/Smear004_2K-JPG_Roughness.jpg", 55.0, 60.0, -2.0, 8.0, False),
                             ("Smear006/Smear006_2K-JPG_Roughness.jpg", 40.0, 82.0, 4.0, -20.0, True),
                             ("Fingerprints003/Fingerprints003_2K-PNG_Opacity.png", 34.0, 44.0, -8.0, 30.0, False)]),
                        (-1, [("Smear002/Smear002_2K-JPG_Roughness.jpg", 50.0, 64.0, -4.0, 170.0, False),
                              ("Fingerprints005/Fingerprints005_2K-PNG_Opacity.png", 30.0, 52.0, 2.0, -15.0, False),
                              ("Fingerprints007/Fingerprints007_2K-PNG_Opacity.png", 30.0, 78.0, -6.0, 10.0, True)])):
        sel = left if sgn > 0 else ~left
        for name, size, cu, cv_, rot, flip in stamps:
            p = MASKS / name
            if not p.exists():
                cand = sorted(p.parent.glob('*Opacity*')) + sorted(p.parent.glob('*Roughness*'))
                if not cand:
                    continue
                p = cand[0]
            im = stamp_image(p, size, x, z, cu, cv_, rot, flip)
            im = np.clip((im - 0.08) / 0.5, 0.0, 1.0)            # фото-маски тусклые (0.2–0.3) — растянуть уровни
            prints = np.maximum(prints, np.where(sel, im, 0.0))
    return np.where(filled & block, tone, 0.0), np.where(filled & block, prints * (0.4 + 0.6 * tone), 0.0)


# ------------------------------------------------------------------------------------------------- места низа
def grip(pos, nrm, filled):
    """Рукоять: задняя часть (спинка), передняя и правая щёчка — глаже и светлее градиентом от ладони."""
    prof = json.loads((ROOT / 'tools/smg03/data/profiles.json').read_text(encoding='utf-8'))
    poly = np.array(prof['parts']['th_grip'][0]['outer'] if isinstance(prof['parts']['th_grip'][0], dict)
                    else prof['parts']['th_grip'][0], np.float32)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    # внутри контура рукояти (по виду сбоку) с запасом 2 мм; ниже коробки
    res = 10.0
    x0, z0 = poly[:, 0].min() - 4, poly[:, 1].min() - 4
    w, h = int((poly[:, 0].max() + 4 - x0) * res), int((poly[:, 1].max() + 4 - z0) * res)
    img = np.zeros((h, w), np.uint8)
    cv2.fillPoly(img, [np.round((poly - [x0, z0]) * res).astype(np.int32)], 255)
    img = cv2.dilate(img, np.ones((41, 41), np.uint8))
    inside = cv2.remap(img.astype(np.float32) / 255.0, ((x - x0) * res).astype(np.float32),
                       ((z - z0) * res).astype(np.float32), cv2.INTER_LINEAR) > 0.5
    inside &= (z < 12.0)
    nx, ny = nrm[..., 0], nrm[..., 1]
    back = smooth(0.35, 0.65, -nx)
    front = smooth(0.35, 0.65, nx)
    right = smooth(0.6, 0.85, -ny)
    # градиент ладони: сильнее посередине высоты хвата
    zc = -40.0
    g = np.exp(-((z - zc) / 30.0) ** 2)
    gr = np.exp(-(((x + 212.0) / 24.0) ** 2 + ((z + 38.0) / 26.0) ** 2))
    m = np.maximum.reduce([back * g, front * g * 0.85, right * gr * 0.9])
    return np.where(filled & inside, m, 0.0)


def save(setname, name, m):
    OUT.mkdir(parents=True, exist_ok=True)
    m = np.clip(m, 0.0, 1.0)
    cv2.imwrite(str(OUT / f'{setname}_{name}.png'), np.round(m * 255).astype(np.uint8))
    return int((m > 0.3).sum())


def main():
    log = []
    d = np.load(TEX / 'Upper_maps.npz')
    pos, nrm, filled = d['pos'], d['nrm'].astype(np.float32), d['filled']
    prev = np.zeros(pos.shape[:2] + (3,), np.float32)
    prev[filled] = 0.25
    for name, fn, col in (('rails', rails, (0.2, 0.2, 0.6)), ('rail_spots', rail_spots, (0.2, 0.9, 0.2)),
                          ('slot', slot, (0.9, 0.9, 0.2)), ('front_r', front_r, (0.9, 0.3, 0.2)),
                          ('front_tl', front_tl, (0.9, 0.5, 0.2)), ('rear_scrape', rear_scrape, (1.0, 1.0, 1.0)),
                          ('arcs', arcs, (0.2, 0.9, 0.9))):
        m = fn(pos, nrm, filled)
        log.append(f'Upper {name}: {save("Upper", name, m)}')
        prev = prev * (1 - m[..., None]) + m[..., None] * np.array(col, np.float32)
    tone, prints = hand(pos, nrm, filled)
    log.append(f'Upper hand_tone: {save("Upper", "hand_tone", tone)}')
    log.append(f'Upper hand_prints: {save("Upper", "hand_prints", prints)}')
    prev = prev * (1 - prints[..., None]) + prints[..., None] * np.array((0.9, 0.2, 0.9), np.float32)
    cv2.imwrite(str(OUT / 'Upper_zones_preview.png'), cv2.resize((prev[..., ::-1] * 255).astype(np.uint8), (2048, 2048),
                                                                 interpolation=cv2.INTER_AREA))
    d = np.load(TEX / 'Lower_maps.npz')
    pos, nrm, filled = d['pos'], d['nrm'].astype(np.float32), d['filled']
    g = grip(pos, nrm, filled)
    log.append(f'Lower grip: {save("Lower", "grip", g)}')
    prev = np.zeros(pos.shape[:2] + (3,), np.float32)
    prev[filled] = 0.25
    prev = prev * (1 - g[..., None]) + g[..., None] * np.array((0.9, 0.6, 0.2), np.float32)
    cv2.imwrite(str(OUT / 'Lower_zones_preview.png'), cv2.resize((prev[..., ::-1] * 255).astype(np.uint8), (2048, 2048),
                                                                 interpolation=cv2.INTER_AREA))
    print('\n'.join(log))


if __name__ == '__main__':
    main()
