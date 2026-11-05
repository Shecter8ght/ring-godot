"""«Осока», износ этап 2 v1 — маски МЕСТ в развёртке наборов: где и почему появился след. Считаются по картам положения,
нормали и номера детали (game_tex.py, стадия maps → <набор>_maps.npz, parts.json); рисунок кромок в местах «до металла»
даёт генератор Painter (sp_osoka_wear.py), следы своей формы (дуги рычага, полоса ремня, отпечатки, риски) — здесь.

    python -X utf8 tools/osoka/wear_zones.py
→ _asset_src/osoka/tex/wear/<набор>_<место>.png (8 бит, белое — след есть) и <набор>_zones_preview.png.

Подход — по рекомендациям для ИЗЛОМ-45 (wpn_smg_03, 05.11) и ответу владельца: «Сделаем всё, но не пихай все везде,
нужно сделать аккуратно и дозированно. Очень нужны вариации base color, добавь и теплого и холодного, светлого и
темного». Его же урок по износу v1 ИЗЛОМ-45: «износа очень много» — следы только в местах с причиной, общий износ кромок
и Edge Damage не годятся (крап по всем рёбрам, пятна с ровной стороной не от ребра).

История (как у ИЗЛОМ-45: ЧВК, город): труба — новая с завода, пусковой механизм ставят на трубу много раз — он
потёрт сильнее. Ракета в запаянной трубе — без износа.

Тон и блеск (все крашеные детали):
  sun — сверху выгорело: светлее и теплее; low — снизу и в тени темнее и холоднее; пятна четырёх оттенков
  (warm_light / warm_dark / cool_light / cool_dark, ~4–12 см); part_a / part_b — детали покрашены разными партиями
  (у каждой детали своя доля чуть светлее-теплее или темнее-холоднее); wipe — разводы протирки тряпкой (только блеск);
  dust — пыль на верхних плоскостях пятнами.
Места (причина → след):
  Tube: shoulder — правое плечо под трубой (стрельба): заполировано, мелкие риски вдоль; cheek — щека у левого бока
        за целиком: жир кожи, глаже и темнее; sling — ремень трётся о трубу при переноске: полоса глаже и светлее;
        hand_left — левая рука держит источник питания: глаже, светлее, отпечатки и разводы (ambientCG, CC0);
        power_rub — источник вставляют в гнездо: продольные потёртости на его заходной части;
        ground — кладут на правый бок: ссадины на самых выступающих местах справа (крышки, обойма, рукав);
        rear_end — ставят на задний торец: кромка задней крышки, низ кронштейна; soil — земля внизу справа;
        stencil_rub / stencil_dirt — трафарет местами стёрт, краска в грязи; sling_grime — ремень засален и
        в грязи (накладка на плече сильнее); accent — длинная царапина на левом боку и ссадина снизу у заднего торца.
  Launcher: grip — рукоять от ладони глаже и светлее (спинка, правый бок, перёд); grip_prints — пальцы слева;
        grip_butt — низ рукояти о землю; lever_tip — головка рычага под большим пальцем; arcs — бороздки по ходу
        рычага на литье; button — центр кнопки заполирован, грязь кольцом у основания; latches — концы защёлок короба;
        box_bottom — низ короба о землю (кромки до алюминия, земля); ground — правые бобышки и плита (кладут на бок);
        lids — кромки крышек (открывают пальцами); leaves — верх прицельных щитков (откидывают); dust_cover — край
        крышки; slider — ползунок и полоса по его ходу; rings — грязь кольцом у головок винтов, осей, заклёпок;
        tool — следы отвёртки на шлицах трёх винтов; oil — масло у осей спуска и рычагов; plate_edge — грязь по
        краю таблички; accent — скол на заднем нижнем углу короба, царапина на левом боку короба.
"""
from __future__ import annotations

import fnmatch
import json
import math
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / '_asset_src/osoka/tex'
OUT = TEX / 'wear'
CC0 = Path('E:/Models Blender/Маски_АЛЬФА/50_Скачанные_CC0_ambientCG_ShareTextures/ambientCG')
SCENE = json.loads((TEX / 'scene.json').read_text(encoding='utf-8'))
LO = np.array(SCENE['min_mm']) - 30.0
HI = np.array(SCENE['max_mm']) + 30.0
TUBE_R = 38.47
LEVER_AXLE = (1454.6, -98.3)          # ось рычага «ИСХОДНОЕ / НАКОЛ» (x, z), левый борт литья y ≈ 26.5
PAINTED = ('tube', 'cast')            # слоты под краской: тон и блеск


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ------------------------------------------------------------------------------------------------- шум
def field2(seed, u0, u1, v0, v1, sig_u, sig_v, res):
    """Гладкий шум N(0,1) на прямоугольнике (мм) с разной длиной пятен по осям."""
    rng = np.random.default_rng(seed)
    w, h = int((u1 - u0) * res) + 8, int((v1 - v0) * res) + 8
    f = rng.standard_normal((h, w)).astype(np.float32)
    f = cv2.GaussianBlur(f, (0, 0), sigmaX=max(sig_u * res, 0.5), sigmaY=max(sig_v * res, 0.5))
    f = (f - f.mean()) / (f.std() + 1e-6)
    return f, u0, v0, res


def sample(fd, u, v):
    f, u0, v0, res = fd
    return cv2.remap(f, ((u - u0) * res).astype(np.float32), ((v - v0) * res).astype(np.float32), cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REFLECT)


class Maps:
    def __init__(self, setname):
        d = np.load(TEX / f'{setname}_maps.npz')
        self.name = setname
        self.pos = d['pos']
        self.nrm = d['nrm'].astype(np.float32)
        self.filled = d['filled']
        self.pid = d['pid'].astype(np.int32)
        self.x, self.y, self.z = self.pos[..., 0], self.pos[..., 1], self.pos[..., 2]
        self.nx, self.ny, self.nz = self.nrm[..., 0], self.nrm[..., 1], self.nrm[..., 2]
        self.parts = {p['pid']: p for p in json.loads((TEX / 'parts.json').read_text(encoding='utf-8'))}

    def of(self, *pats):
        """Пиксели деталей, чьи имена подходят под шаблоны."""
        ids = [i for i, p in self.parts.items() if any(fnmatch.fnmatchcase(p['name'], q) for q in pats)]
        return np.isin(self.pid, ids) & self.filled

    def slots(self, *slots):
        ids = [i for i, p in self.parts.items() if p['slot'] in slots]
        return np.isin(self.pid, ids) & self.filled

    def noise(self, seed, sig, aniso=(1.0, 1.0, 1.0)):
        """Трёхпроекционный шум N(0,1): длина пятен sig мм, по осям x / y / z — sig × aniso (полосы вдоль оси)."""
        out = np.zeros_like(self.x)
        wsum = np.zeros_like(self.x)
        s = [sig * a for a in aniso]
        res = min(3.0 / min(s), 4.0)
        for k, (a, b, w) in enumerate(((1, 2, self.nx), (0, 2, self.ny), (0, 1, self.nz))):
            fd = field2(seed * 7 + k, LO[a], HI[a], LO[b], HI[b], s[a], s[b], res)
            ww = w * w
            out += ww * sample(fd, self.pos[..., a], self.pos[..., b])
            wsum += ww
        return out / np.maximum(wsum, 1e-4)


def patches(m, seed, sig, cover, soft=0.35, mask=None):
    """Пятна с мягким краем, занимающие долю cover поверхности (по порогу шума)."""
    n = m.noise(seed, sig)
    sel = m.filled if mask is None else mask
    t = float(np.quantile(n[sel][::97], 1.0 - cover)) if sel.any() else 0.0
    return np.where(sel, smooth(t - soft, t + soft, n), 0.0)


def stamp_image(path, size_mm, u, v, cu, cv_, rot_deg=0.0, flip=False):
    """Фото-маска (0..1) плоской проекцией: центр (cu, cv_) мм, сторона size_mm, поворот."""
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
    return cv2.remap(im, px.astype(np.float32), py.astype(np.float32), cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)


def cc0(name, kind):
    for k in (kind, 'Opacity', 'Roughness'):
        for p in (CC0 / name / f'{name}_2K-PNG_{k}.png', CC0 / name / f'{name}_2K-JPG_{k}.jpg'):
            if p.exists():
                return p
    raise FileNotFoundError(f'{name}: нет маски {kind}')


def prints(m, sel, stamps, u, v):
    """Отпечатки и разводы (ambientCG, CC0): фото-маски тусклые (0.2–0.3) — уровни растянуты."""
    out = np.zeros_like(m.x)
    for name, kind, size, cu, cv_, rot, flip in stamps:
        im = stamp_image(cc0(name, kind), size, u, v, cu, cv_, rot, flip)
        out = np.maximum(out, np.clip((im - 0.08) / 0.5, 0.0, 1.0))
    return np.where(sel, out, 0.0)


def line(m, p0, p1, w0, w1, u, v, seed=0):
    """Тонкая царапина от p0 до p1 (мм в плоскости u, v): ширина от w0 до w1, сила меняется по длине, рвётся."""
    (u0, v0), (u1, v1) = p0, p1
    du, dv = u1 - u0, v1 - v0
    L = math.hypot(du, dv)
    t = ((u - u0) * du + (v - v0) * dv) / (L * L)
    d = np.abs((u - u0) * dv - (v - v0) * du) / L
    w = w0 + (w1 - w0) * np.clip(t, 0, 1)
    rng = np.random.default_rng(seed)
    ph = rng.uniform(0, 6.28, 3)
    ins = 0.55 + 0.45 * np.sin(t * 9.0 + ph[0]) * np.sin(t * 23.0 + ph[1])
    ends = smooth(0.0, 0.06, t) * (1 - smooth(0.9, 1.0, t))
    return np.exp(-(d / np.maximum(w, 1e-3)) ** 2) * np.clip(ins, 0, 1) * ends


# ------------------------------------------------------------------------------------------------- общие: тон, блеск
def tone(m, log):
    paint = m.slots(*PAINTED)
    out = {}
    out['sun'] = np.where(paint, smooth(0.05, 0.95, m.nz) * np.clip(0.55 + 0.35 * m.noise(11, 90.0), 0, 1), 0.0)
    out['low'] = np.where(paint, (1 - smooth(-0.9, 0.0, m.nz)) * np.clip(0.55 + 0.35 * m.noise(12, 80.0), 0, 1), 0.0)
    # мягкий край (soft 0.9): с резким краем пятна ~5 см на мелких деталях читались камуфляжем (проба v1)
    for k, (nm, sig, cov) in enumerate((('warm_light', 95.0, 0.16), ('warm_dark', 70.0, 0.12),
                                         ('cool_light', 80.0, 0.12), ('cool_dark', 110.0, 0.18))):
        out[nm] = patches(m, 21 + k, sig, cov, soft=0.9, mask=paint)
        # на маленьком источнике питания (Ø66) пятна ~10 см ложились одним-двумя и читались камуфляжем — слабее
        out[nm] = out[nm] * np.where(m.of('Power_source'), 0.35, 1.0)
    # детали покрашены разными партиями: у каждой своя доля «светлее и теплее» (a) или «темнее и холоднее» (b);
    # труба и литьё механизма — основа (0)
    rng = np.random.default_rng(31)
    a = np.zeros_like(m.x)
    b = np.zeros_like(m.x)
    for i, p in sorted(m.parts.items()):
        if p['slot'] not in PAINTED or p['name'] in ('Tube_body', 'Launcher_cast', 'Saddle_body'):
            continue
        r = rng.uniform()
        k = rng.uniform(0.35, 1.0)
        sel = m.pid == i
        if r < 0.35:
            a[sel] = k
        elif r < 0.7:
            b[sel] = k
    out['part_a'] = np.where(paint, a, 0.0)
    out['part_b'] = np.where(paint, b, 0.0)
    # разводы протирки — только блеск: длинные вдоль трубы, на литье — по бортам вдоль x
    n = m.noise(41, 3.0, aniso=(16.0, 1.0, 1.0))
    out['wipe'] = np.where(paint & (m.nz > -0.5), smooth(0.9, 1.9, n) * np.clip(0.4 + 0.5 * m.noise(42, 120.0), 0, 1),
                           0.0)
    # пыль на верхних плоскостях — пятнами, у краёв уступов гуще (там её не протирают)
    up = smooth(0.55, 0.9, m.nz)
    out['dust'] = np.where(m.filled & ~m.of('Sling_*'), up * patches(m, 43, 22.0, 0.35), 0.0)
    # пыль в углах и щелях — по AO заводской выгрузки (генератор Dirt Painter заливал целиком затенённые детали:
    # грани у трубы, задние стороны короба — сплошной беж, проба v1): углы и щели — да, глубокая тень — слабее,
    # рвано, на горизонталях гуще
    ao = cv2.imread(str(TEX / f'maps_v6/{m.name}_occlusionRoughnessMetallic.png'))
    if ao is not None:
        ao = ao[..., 2].astype(np.float32) / 255.0
        if ao.shape != m.x.shape:
            ao = cv2.resize(ao, m.x.shape[::-1], interpolation=cv2.INTER_AREA)
        cav = smooth(0.85, 0.55, ao) * (1 - 0.7 * smooth(0.3, 0.12, ao))
        brk = smooth(-0.7, 0.6, m.noise(44, 3.0)) * (0.55 + 0.45 * smooth(-0.3, 0.7, m.nz))
        out['cavity'] = np.where(m.filled & ~m.of('Sling_*'), cav * brk, 0.0)
    return out


# ------------------------------------------------------------------------------------------------- труба
def tube_places(m):
    out = {}
    x, y, z = m.x, m.y, m.z
    body = m.of('Tube_body', 'Tube_clamp_*')
    phi = np.degrees(np.arctan2(z, y))                 # 0 — левый бок (+Y), 90 — верх, ±180 — правый, −90 — низ
    arc = np.radians(phi) * TUBE_R

    def dphi(c):
        return (phi - c + 180.0) % 360.0 - 180.0

    # плечо (труба на правом плече при стрельбе): снизу-справа, x 780…960
    sh = np.exp(-((x - 870.0) / 80.0) ** 2 - (dphi(-125.0) / 32.0) ** 2)
    out['shoulder'] = np.where(body, sh, 0.0)
    fs = m.noise(51, 0.35, aniso=(40.0, 1.0, 1.0))
    out['shoulder_scuff'] = np.where(body, sh * smooth(1.2, 2.2, fs), 0.0)
    # щека у левого бока за целиком (глаз в 6–8 см за целиком)
    out['cheek'] = np.where(body, np.exp(-((x - 1075.0) / 48.0) ** 2 - (dphi(8.0) / 24.0) ** 2), 0.0)
    # ремень: сверху от антабки до накладки, дальше уходит к петле на левом борту; полоса чуть шире ремня
    pc = 90.0 - 66.0 * smooth(880.0, 1290.0, x)
    band = (1 - smooth(18.0, 30.0, np.abs(phi - pc))) * smooth(600.0, 650.0, x) * \
        (1 - smooth(1250.0, 1300.0, x))
    fsl = m.noise(52, 1.2, aniso=(30.0, 1.0, 1.0))
    out['sling'] = np.where(body, band * np.clip(0.45 + 0.35 * fsl, 0, 1), 0.0)
    # левая рука держит источник питания: бока и низ, сильнее посередине
    ps = m.of('Power_source')
    hand = np.exp(-((x - 1595.0) / 38.0) ** 2) * (1 - smooth(-0.2, 0.6, m.nz))
    out['hand_left'] = np.where(ps, hand, 0.0)
    side_l = ps & (m.ny > 0.5)
    side_r = ps & (m.ny < -0.5)
    pr = prints(m, side_l, [('Smear004', 'Roughness', 42.0, 1590.0, -112.0, 8.0, False),
                            ('Fingerprints003', 'Opacity', 40.0, 1612.0, -100.0, 25.0, False)], x, z)
    pr = np.maximum(pr, prints(m, side_r, [('Fingerprints005', 'Opacity', 36.0, 1585.0, -112.0, -15.0, True),
                                           ('Smear006', 'Roughness', 38.0, 1606.0, -124.0, 170.0, False)], x, z))
    out['hand_prints'] = pr * (0.4 + 0.6 * np.where(ps, hand, 0.0))
    # источник питания вставляют в гнездо: заходная часть — продольные потёртости (только по бокам цилиндра)
    fr = m.noise(53, 0.4, aniso=(25.0, 1.0, 1.0))
    out['power_rub'] = np.where(ps & (np.abs(m.nx) < 0.5), (1 - smooth(1548.0, 1572.0, x)) * smooth(0.6, 1.8, fr),
                                0.0)
    # кладут на правый бок: самые выступающие места справа — крышки, обойма, раструб, задний рукав
    ext = np.zeros_like(x)
    for pat, rmax in (('Front_cap', 57.0), ('Rear_cap', 48.6), ('Tube_collar', 55.0), ('Tube_bell', 51.1),
                      ('Tube_rear_sleeve', 40.1), ('Tube_sling_band', 40.3)):
        sel = m.of(pat)
        r = np.hypot(y, z)
        ext = np.maximum(ext, np.where(sel, smooth(rmax - 4.0, rmax - 0.5, r) * smooth(0.55, 0.95, -m.ny), 0.0))
    brk = m.noise(54, 1.2)
    out['ground'] = ext * smooth(-0.6, 0.5, brk) * np.where(m.slots('rubber'), 0.6, 1.0)
    # ставят на задний торец: кромка задней крышки по кругу, низ заднего кронштейна
    rc = m.of('Rear_cap')
    r = np.hypot(y, z)
    rim = smooth(42.0, 47.5, r) * (1 - smooth(-30.0, -24.0, x))
    br = m.of('Tube_rear_bracket') & (z < -52.0)
    out['rear_end'] = np.where(rc, rim, 0.0) * smooth(-0.8, 0.6, m.noise(55, 1.2)) + \
        np.where(br, smooth(-0.5, 0.8, m.noise(56, 1.5)), 0.0)
    # земля внизу справа: крышки, обойма, низ трубы у заднего торца
    lowr = (1 - smooth(-0.6, 0.1, m.nz)) * (1 - smooth(-0.5, 0.3, m.ny))
    ends = m.of('Front_cap', 'Rear_cap', 'Tube_collar', 'Tube_bell', 'Tube_rear_*', 'Power_*')
    out['soil'] = np.where(m.filled & ~m.of('Sling_*'), lowr * patches(m, 57, 12.0, 0.18), 0.0) * \
        np.where(ends, 1.0, 0.2 + 0.6 * (1 - smooth(150.0, 350.0, x)))
    # трафарет: местами стёрт (больше сверху — там трётся ремень), краска в грязи
    st = cv2.imdecode(np.fromfile(str(TEX / 'masks/Tube_stencil.png'), np.uint8), cv2.IMREAD_GRAYSCALE)
    st = cv2.resize(st, m.x.shape[::-1], interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0 \
        if st.shape != m.x.shape else st.astype(np.float32) / 255.0
    rub = smooth(0.4, 1.3, m.noise(58, 1.2) + 0.9 * smooth(30.0, 60.0, phi))
    out['stencil_rub'] = st * rub
    out['stencil_dirt'] = st * np.clip(0.3 + 0.5 * m.noise(59, 4.0), 0, 1)
    # ремень: засален и в грязи — накладка на плече сильнее, по ленте пятнами
    sl = m.of('Sling_*')
    pad = m.of('Sling_pad')
    g = np.where(pad, 0.55 + 0.45 * np.exp(-((x - 775.0) / 90.0) ** 2), 0.0)
    g = np.maximum(g, np.where(sl & ~pad, patches(m, 60, 30.0, 0.3, mask=sl & ~pad) * 0.8, 0.0))
    out['sling_grime'] = g * np.clip(0.6 + 0.4 * m.noise(61, 6.0), 0, 1)
    # акценты: длинная царапина на левом боку (протащили вдоль чего-то), ссадина снизу у заднего торца
    acc = np.where(body & (m.ny > 0.3), line(m, (330.0, 9.0),
                                              (565.0, 2.0), 0.10, 0.22, x, arc, seed=62), 0.0)
    sc = np.exp(-((x - 95.0) / 45.0) ** 2 - (dphi(-98.0) / 18.0) ** 2)
    fsc = m.noise(63, 0.25, aniso=(30.0, 1.0, 1.0))
    acc = np.maximum(acc, np.where(m.of('Tube_body', 'Tube_rear_sleeve'),
                                   sc * smooth(0.3, 1.5, fsc) * smooth(-0.4, 0.6, m.noise(64, 4.0)), 0.0))
    out['accent'] = acc
    return out


# ------------------------------------------------------------------------------------------------- пусковой механизм
def ring_around(m, names, inner=0.2, outer=2.6):
    """Кольцо вокруг головок крепежа по их габариту: ось — самая тонкая сторона, кольцо на поверхности под головкой."""
    out = np.zeros_like(m.x)
    for i, p in m.parts.items():
        if not any(fnmatch.fnmatchcase(p['name'], q) for q in names):
            continue
        lo, hi = np.array(p['lo']), np.array(p['hi'])
        ax = int(np.argmin(hi - lo))
        a, b = [k for k in range(3) if k != ax]
        ca, cb = (lo[a] + hi[a]) / 2, (lo[b] + hi[b]) / 2
        r = max(hi[a] - lo[a], hi[b] - lo[b]) / 2
        sgn = 1.0 if (lo[ax] + hi[ax]) / 2 > 0 else -1.0
        plane = lo[ax] if sgn > 0 else hi[ax]
        near = (np.abs(m.pos[..., ax] - plane) < 1.5) & (m.pid != i) & m.filled
        d = np.hypot(m.pos[..., a] - ca, m.pos[..., b] - cb) - r
        out = np.maximum(out, np.where(near, (1 - smooth(inner, outer, d)) * (d > -0.3), 0.0))
    return out


def launcher_places(m):
    out = {}
    x, y, z = m.x, m.y, m.z
    # рукоять: от ладони глаже и светлее — спинка, правый бок (ладонь), перёд (пальцы) слабее
    gr = m.of('Launcher_grip') & (z < -104.0)
    mid = np.exp(-((z + 165.0) / 38.0) ** 2)
    back = smooth(0.3, 0.7, -m.nx)
    front = smooth(0.3, 0.7, m.nx)
    right = smooth(0.55, 0.85, -m.ny)
    left = smooth(0.55, 0.85, m.ny)
    out['grip'] = np.where(gr, mid * np.maximum.reduce([back, right * 0.85, front * 0.6, left * 0.3]), 0.0)
    out['grip_prints'] = prints(m, gr & (m.ny > 0.5), [('Fingerprints007', 'Opacity', 30.0, 1262.0, -150.0, 80.0, False),
                                                       ('Fingerprints003', 'Opacity', 28.0, 1268.0, -182.0, 95.0, True)],
                                x, z) * 0.8
    # низ рукояти о землю
    out['grip_butt'] = np.where(m.of('Launcher_grip') & (z < -214.0), smooth(-0.2, 0.6, m.noise(71, 1.5)), 0.0)
    # головка рычага под большим пальцем
    lv = m.of('Lever')
    dl = np.hypot(x - LEVER_AXLE[0], z - LEVER_AXLE[1])
    out['lever_tip'] = np.where(lv, smooth(46.0, 58.0, dl), 0.0)
    # бороздки по ходу рычага: дуги вокруг оси на левом борту литья (ход 18° вверх от «ИСХОДНОЕ»)
    face = m.of('Launcher_cast', 'Launcher_boss_*') & (m.ny > 0.85)
    ang = np.degrees(np.arctan2(z - LEVER_AXLE[1], x - LEVER_AXLE[0]))
    rng = np.random.default_rng(72)
    arcs = np.zeros_like(x)
    for k in range(9):
        rk = rng.uniform(44.0, 67.0)
        wk = rng.uniform(0.1, 0.18)
        a0 = rng.uniform(136.0, 146.0)
        a1 = rng.uniform(158.0, 167.0)
        ik = rng.uniform(0.45, 1.0)
        along = smooth(a0, a0 + 3.0, ang) * (1 - smooth(a1 - 3.0, a1, ang))
        arcs = np.maximum(arcs, ik * np.exp(-((dl - rk) / wk) ** 2) * along)
    out['arcs'] = np.where(face, arcs, 0.0)
    # кнопка: центр заполирован, у основания грязь кольцом
    bc = m.of('Button_cap')
    cx, cz = 1432.1, -57.3
    db = np.hypot(x - cx, z - cz)
    out['button'] = np.where(bc & (m.ny > 0.6), 1 - smooth(2.0, 6.5, db), 0.0)
    out['button_ring'] = np.where(m.of('Button_boss') | (m.of('Launcher_cast') & (np.abs(y - 26.5) < 1.5)),
                                  (1 - smooth(7.0, 10.5, db)) * smooth(5.5, 7.2, db), 0.0)
    # концы защёлок короба (откидывают пальцами)
    out['latches'] = np.where(m.of('Box_latch_*'), smooth(-128.0, -134.0, z), 0.0)
    # низ короба о землю: нижние кромки и угол сзади
    bx = m.of('Box_lower', 'Box_rear_plate')
    out['box_bottom'] = np.where(bx, smooth(-176.0, -184.0, z), 0.0)
    out['box_soil'] = np.where(bx & (m.nz < -0.6), patches(m, 73, 10.0, 0.45, mask=bx), 0.0)
    # кладут на правый бок: правые бобышки, плита, отбортовка седла — самые выступающие места
    rg = m.of('Saddle_right_boss', 'Front_right_plate', 'Front_right_boss', 'Saddle_right_flange')
    out['ground'] = np.where(rg, smooth(-38.0, -43.5, y) * smooth(-0.5, 0.7, m.noise(74, 2.0)), 0.0)
    # крышки (открывают пальцами): кромки
    lids = np.zeros_like(x)
    for pat, ax, c, rr in (('Lid_mid', 1, (1361.4, 9.4), 28.0), ('Lid_front', 1, (1508.0, 3.7), 29.0),
                           ('Lid_top', 2, (1359.8, 0.0), 20.0)):
        sel = m.of(pat)
        if ax == 1:
            d = np.hypot(x - c[0], z - c[1])
        else:
            d = np.hypot(x - c[0], y - c[1])
        lids = np.maximum(lids, np.where(sel, smooth(rr - 3.5, rr - 0.6, d), 0.0))
    out['lids'] = lids * smooth(-0.5, 0.7, m.noise(75, 2.5))
    # верх прицельных щитков (откидывают пальцем)
    out['leaves'] = np.where(m.of('Rear_sight_leaf'), smooth(66.0, 74.0, z), 0.0) + \
        np.where(m.of('Front_sight_leaf'), smooth(28.0, 36.0, z), 0.0)
    out['dust_cover'] = np.where(m.of('Dust_cover'), smooth(1488.0, 1496.0, x), 0.0)
    # ползунок и полоса по его ходу на рамке
    fsd = m.noise(76, 0.4, aniso=(20.0, 1.0, 1.0))
    out['slider'] = np.where(m.of('Slider_knob'), 1.0, 0.0) + \
        np.where(m.of('Slider_frame') & (m.ny < -0.6), smooth(-117.5, -116.0, z) * (1 - smooth(-113.0, -111.5, z))
                 * np.clip(0.4 + 0.5 * fsd, 0, 1), 0.0)
    # грязь кольцом у головок винтов, осей, заклёпок (рвано — где-то протёрто)
    rings = ring_around(m, ['*screw*', '*rivet*', '*_pin*', 'Frame_lever_pivot_*', 'Lever_axle'])
    out['rings'] = rings * np.clip(0.35 + 0.65 * smooth(-0.5, 0.6, m.noise(77, 1.2)), 0, 1)
    # следы отвёртки на шлицах трёх винтов: короткие риски поперёк края шлица
    tool = np.zeros_like(x)
    for k, nm in enumerate(('Launcher_cover_screw_1', 'Launcher_tab_screw_2', 'Saddle_right_screw_1')):
        p = next((p for p in m.parts.values() if p['name'] == nm), None)
        if p is None:
            continue
        lo, hi = np.array(p['lo']), np.array(p['hi'])
        cx_, cz_ = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
        r = (hi[0] - lo[0]) / 2
        sel = m.pid == p['pid']
        a = math.radians(30.0 + 50.0 * k)
        for s in (-1.0, 1.0):
            p0 = (cx_ + s * 0.55 * r * math.cos(a) - 0.4 * math.sin(a), cz_ + s * 0.55 * r * math.sin(a))
            p1 = (cx_ + s * 0.95 * r * math.cos(a + 0.3), cz_ + s * 0.95 * r * math.sin(a + 0.3))
            tool = np.maximum(tool, np.where(sel, line(m, p0, p1, 0.12, 0.2, x, z, seed=80 + k), 0.0))
    out['tool'] = tool
    # масло у осей спуска и рычагов — тёмный ореол
    out['oil'] = ring_around(m, ['Trigger_pin', 'Frame_lever_pivot_*', 'Lever_axle', 'Launcher_boss_pin_*'],
                             inner=-0.2, outer=3.5) * np.clip(0.5 + 0.5 * m.noise(78, 1.0), 0, 1)
    # грязь по краю таблички
    pl = m.of('Nameplate')
    p = next(p for p in m.parts.values() if p['name'] == 'Nameplate')
    de = np.minimum.reduce([x - p['lo'][0], p['hi'][0] - x, z - p['lo'][2], p['hi'][2] - z])
    out['plate_edge'] = np.where(pl, (1 - smooth(0.3, 1.6, de)) * smooth(-0.6, 0.5, m.noise(79, 1.5)), 0.0)
    # акценты: скол на заднем нижнем углу короба справа, царапина на левом боку короба
    d = np.hypot(x - 991.0, z + 185.0)
    chip = np.where(bx & (y < -27.0), (1 - smooth(3.0, 7.5, d)) * smooth(-0.3, 0.5, m.noise(81, 0.8)), 0.0)
    scr = np.where(m.of('Box_upper') & (m.ny > 0.85),
                   line(m, (1012.0, -62.0), (1076.0, -96.0), 0.08, 0.18, x, z, seed=82), 0.0)
    out['accent'] = np.maximum(chip, scr)
    return out


# ------------------------------------------------------------------------------------------------- запись
def save(setname, name, a):
    OUT.mkdir(parents=True, exist_ok=True)
    a = np.clip(np.nan_to_num(a), 0.0, 1.0)
    cv2.imwrite(str(OUT / f'{setname}_{name}.png'), np.round(a * 255).astype(np.uint8))
    return float((a > 0.3).mean() * 100.0)


COLORS = [(0.9, 0.3, 0.2), (0.2, 0.9, 0.3), (0.3, 0.4, 1.0), (1.0, 0.9, 0.2), (0.9, 0.2, 0.9), (0.2, 0.9, 0.9),
          (1.0, 0.6, 0.2), (0.6, 1.0, 0.6), (1.0, 1.0, 1.0)]


def main():
    log = []
    for setname, places in (('Tube', tube_places), ('Launcher', launcher_places)):
        m = Maps(setname)
        prev = np.zeros(m.x.shape + (3,), np.float32)
        prev[m.filled] = 0.22
        for nm, a in tone(m, log).items():
            log.append(f'{setname} {nm}: {save(setname, nm, a):.1f} %')
        for k, (nm, a) in enumerate(places(m).items()):
            log.append(f'{setname} {nm}: {save(setname, nm, a):.2f} %')
            c = np.array(COLORS[k % len(COLORS)], np.float32)
            a = np.clip(a, 0, 1)[..., None]
            prev = prev * (1 - a) + a * c
        cv2.imwrite(str(OUT / f'{setname}_zones_preview.png'),
                    cv2.resize((prev[..., ::-1] * 255).astype(np.uint8), (2048, 2048), interpolation=cv2.INTER_AREA))
    print('\n'.join(log))


if __name__ == '__main__':
    main()
