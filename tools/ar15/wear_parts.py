# AR-15 «ГРАНЬ-15», этап 2 (износ): места износа остальных деталей — верхний ресивер с рукояткой заряжания, затворная
# группа, цевьё с планками, ствол с ДТК, приклад, трубка, прицелы, патроны — попиксельно по геометрическим картам
# наборов (tools/ar15/wear_maps.py). План — asset-state.md модели, «Этап 2 — карта износа по деталям» (рабочий лёгкий,
# ЧВК, город; сквозь FDE — точки чёрного анодирования только на местах удара; протёртый FDE — глаже и темнее; нагар
# только внутри).
# Владелец 30.10: «чтобы не было видно процедурности, чтобы было видно всё естественно». Поэтому:
#   - кромки — только выпуклые (острые и скруглённые), по выпуклости в пространстве, а не по кривизне развёртки; сила —
#     по месту (что чем трётся: правила деталей ниже) и по открытости (запечённое AO этапа 1), не одинаково везде;
#   - рисунок края, разрывы кромки, сколы, пыль — с фото-масок CC0 трипланарно по мировой точке (wear_masks.py), шума нет;
#   - царапины — редкие короткие штрихи с направлением движения (strokes() по якобиану карты положения);
#   - крупные вариации блеска и тона по всей детали — захватано, протёрто при чистке.
#   python -X utf8 tools/ar15/wear_parts.py [набор …]     (по умолчанию — все: upper bolt handguard barrel stock tube sights rounds)
# Пишет <набор>_zone_<зона>_L.png (ч/б 8 бит, по развёртке набора), <набор>_zones.json (какие зоны есть, для
# sp_ar15_wear.build_part()) и <набор>_zones_preview.png. Координаты, мм: X — к дулу, Y — влево, Z — вверх.
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import zoom
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wear_magazine  # noqa: E402
from mark_apply import photo, tri  # noqa: E402
from wear_lower import lint, sstep, window  # noqa: E402

WEAR = "E:/Games/RING-godot/_asset_src/ar15/tex/wear"
BASE = "E:/Models Blender/WEAPONS/AR-15 — модель/Текстуры_этап1_v6_песок"
SEED = 3007
SETS = ["upper", "bolt", "handguard", "barrel", "stock", "tube", "sights", "rounds"]
# класс отделки места: как оно стирается (asset-state.md, «Как стирается каждая отделка»)
CLS = {1: "fde", 2: "anod", 3: "phos", 4: "nit", 5: "poly", 6: "rubber", 7: "brass"}
MAT_CLS = {"Alu_anodized": 1, "Steel_black": 3, "Spring_steel": 3, "Steel_nitride": 4, "Steel_bare": 4,
           "Polymer": 5, "Rubber": 6, "Brass": 7, "Bullet_jacket": 7}


# ── геометрия набора ─────────────────────────────────────────────────────────────────────────────────────────────────
class Part:
    """Карты набора: положение, нормаль, деталь, класс отделки, открытость (AO этапа 1), пикселей на мм."""

    def __init__(self, name):
        d = np.load(os.path.join(WEAR, f"{name}_maps.npz"))
        self.name = name
        self.pos, self.nrm, self.ids = d["pos"], d["nrm"].astype(np.float32), d["ids"]
        self.names = list(d["ids_names"])
        mats = list(d["ids_mats"])
        self.size = self.ids.shape[0]
        lut = np.zeros(len(mats), dtype=np.uint8)
        for i, m in enumerate(mats):
            lut[i] = MAT_CLS.get(m, 3) if i else 0
        cls = lut[self.ids]
        base = self._img(f"{name}_baseColor.png")
        self.base = base
        # анодированный алюминий: песочный Cerakote или чёрное анодирование — по заводскому цвету этапа 1
        self.cls = np.where((cls == 1) & (base.mean(-1) < 0.25), 2, cls).astype(np.uint8)
        self.ao = self._img(f"{name}_occlusionRoughnessMetallic.png")[..., 0]
        self.on = self.ids > 0
        m = self.on
        dx = np.linalg.norm(self.pos[:, 1:] - self.pos[:, :-1], axis=-1)[m[:, 1:] & m[:, :-1]]
        self.px_mm = 1.0 / max(float(np.median(dx[dx > 0])), 1e-3)
        self.x, self.y, self.z = self.pos[..., 0], self.pos[..., 1], self.pos[..., 2]
        self.nx, self.ny, self.nz = self.nrm[..., 0], self.nrm[..., 1], self.nrm[..., 2]

    def _img(self, fname):
        im = Image.open(os.path.join(BASE, fname)).convert("RGB")
        if im.size != (self.size, self.size):
            im = im.resize((self.size, self.size), Image.BILINEAR)
        return np.asarray(im).astype(np.float32) / 255.0

    def part(self, *prefixes):
        """Маска деталей по началу имени."""
        ok = [i for i, n in enumerate(self.names) if i and any(n.startswith(p) for p in prefixes)]
        return np.isin(self.ids, ok)

    def is_cls(self, c):
        return self.cls == {v: k for k, v in CLS.items()}[c]


def convexity(P, step=2):
    """Выпуклость (1/мм) в каждом пикселе по соседям в пространстве: средняя ((n_q − n_p)·(q − p)) / |q − p|² — у сферы
    радиуса R это 1/R, у плоскости 0, у вогнутого угла меньше нуля. Соседи — своей детали (номер — четвёртая
    координата), в пространстве, а не в развёртке: рёбра лежат на швах развёртки. Считается через пиксель (step) и
    растягивается — на 4K иначе минуты."""
    pos, nrm, ids = P.pos[::step, ::step], P.nrm[::step, ::step], P.ids[::step, ::step]
    m = ids > 0
    pts, nn, ii = pos[m].astype(np.float64), nrm[m], ids[m].astype(np.float64)
    q = max(0.08, 0.7 / P.px_mm)
    _, u = np.unique(np.c_[np.round(pts / q).astype(np.int64), ii.astype(np.int64)], axis=0, return_index=True)
    big = 1.0e5
    tree = cKDTree(np.c_[pts[u], ii[u] * big])
    Nu, Pu = nn[u], pts[u]
    kap = np.zeros(len(pts), dtype=np.float32)
    r = max(0.6, 5.0 / P.px_mm)
    for a in range(0, len(pts), 400000):
        b = min(a + 400000, len(pts))
        Q = np.c_[pts[a:b], ii[a:b] * big]
        dd, jj = tree.query(Q, k=24, distance_upper_bound=r)
        ok = (jj < len(Pu)) & (dd > 1e-4)
        jj = np.where(ok, jj, 0)
        dp = Pu[jj] - pts[a:b, None, :]
        k = ((Nu[jj] - nn[a:b, None, :]) * dp).sum(-1) / np.maximum((dp * dp).sum(-1), 1e-8)
        kap[a:b] = np.where(ok, k, 0.0).sum(1) / np.maximum(ok.sum(1), 1)
    K = np.zeros(ids.shape, dtype=np.float32)
    K[m] = kap
    return K


def dist_field(P, sel_half, step=2, cap=8.0):
    """Расстояние (мм) от каждого пикселя до ближайшего отмеченного места (sel_half — через пиксель) той же детали."""
    pos, ids = P.pos[::step, ::step], P.ids[::step, ::step]
    m = ids > 0
    out = np.full(ids.shape, cap, dtype=np.float32)
    s = sel_half & m
    if s.sum() < 3:
        return zoom(out, step, order=0)[:P.size, :P.size]
    big = 1.0e5
    tree = cKDTree(np.c_[pos[s].astype(np.float64), ids[s].astype(np.float64) * big])
    Q = np.c_[pos[m].astype(np.float64), ids[m].astype(np.float64) * big]
    d, _ = tree.query(Q, k=1, distance_upper_bound=cap)
    out[m] = np.minimum(d, cap)
    return zoom(out, step, order=1)[:P.size, :P.size]


# ── рисунок ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def fields(P, seed):
    """Фото-маски CC0 трипланарно по мировой точке: облака (ширина и разрывы кромки), сколы покрытия, мелкие крапины,
    крупные облака (вариации блеска по детали)."""
    p, n = P.pos[P.on], P.nrm[P.on]
    F = {}
    for key, img, tile, blur in (("cloudy", "cloudy", 22.0, 2.0), ("chips", "chips", 26.0, 2.5), ("fine", "fine", 11.0, 0.0),
                                 ("big", "cloudy", 140.0, 6.0), ("big2", "polish_var", 90.0, 4.0)):
        v = np.zeros(P.ids.shape, dtype=np.float32)
        v[P.on] = tri(p, n, photo(img, blur), tile, seed + len(F) * 17)
        F[key] = v
    return F


def edge_band(P, d, pres, F, width=0.3, chips=1.2, rag=0.2):
    """Протёртая полоса по выпуклой кромке. pres — насколько место трётся (0…1+): от него — какая доля кромки протёрта
    (кусками по облакам и сколам с фото: при малом — редкие короткие участки, при большом — почти вся кромка с
    разрывами). Ширина ~width мм, мягко меняется по облакам, заходы внутрь — формами сколов, край рваный по крапинам."""
    field = 0.65 * F["cloudy"] + 0.35 * F["chips"] + 0.15
    t = 1.0 - 0.75 * np.clip(pres, 0.0, 1.2)
    sel = sstep(t - 0.06, t + 0.06, field)
    wd = width * (0.6 + 0.8 * F["cloudy"]) * (1.0 + chips * F["chips"])
    jit = (F["fine"] - 0.1) * rag
    tw = max(0.05, 0.7 / P.px_mm)
    return (1.0 - sstep(wd - tw, wd + tw, d + jit)) * sel * (pres > 0.01)


def scratches(P, allowed, density, dir_fn, rng, length=(1.5, 6.0), deep=0.2):
    """Редкие короткие царапины с направлением движения: число — по площади разрешённого места × плотность (на см²)."""
    area = allowed.sum() / P.px_mm ** 2
    cnt = int(np.clip(area / 100.0 * density, 0, 1500))
    if cnt < 1:
        z = np.zeros(P.ids.shape, dtype=np.float32)
        return z, z
    wear_magazine.PX_MM = P.px_mm
    return wear_magazine.strokes(P.pos, P.nrm, P.ids, allowed, allowed, dir_fn, rng, count=cnt, length_mm=length,
                                 deep_frac=deep, width=(1, 2))


def dots(P, allowed, count, rng, r_mm=(0.15, 0.45), F=None):
    """Точки-тычки и вмятинки (мелкие отметины) в разрешённом месте, рваные по сколам."""
    out = np.zeros(P.ids.shape, dtype=np.float32)
    cand = np.argwhere(allowed)
    if len(cand) == 0:
        return out
    for k in rng.choice(len(cand), size=min(count, len(cand)), replace=False):
        r0, c0 = cand[k]
        rad = rng.uniform(*r_mm)
        h = int(rad * P.px_mm * 2.5) + 3
        y0, y1, x0, x1 = max(r0 - h, 0), min(r0 + h, P.size), max(c0 - h, 0), min(c0 + h, P.size)
        dd = np.linalg.norm(P.pos[y0:y1, x0:x1] - P.pos[r0, c0], axis=-1)
        sub = out[y0:y1, x0:x1]
        np.maximum(sub, (1.0 - sstep(rad * 0.5, rad, dd)) * (P.ids[y0:y1, x0:x1] == P.ids[r0, c0]), out=sub)
    if F is not None:
        out *= sstep(0.05, 0.35, F["chips"] + 0.3 * F["fine"])
    return out


def inwin(v, a0, a1, b0, b1):
    """Внутри окна по координате (середины плавных краёв) — для логических масок."""
    return window(v, a0, a1, b0, b1) > 0.5


def axis_dir(v):
    v = np.asarray(v, dtype=np.float64)
    return lambda p, n: v


def jitter_dir(v, rng, spread=0.35):
    v = np.asarray(v, dtype=np.float64)
    return lambda p, n: v + np.cross(n, v) * rng.normal(0.0, spread)


def random_dir(rng):
    return lambda p, n: np.cross(n, rng.normal(size=3))


# ── общие места ──────────────────────────────────────────────────────────────────────────────────────────────────────
def common(P, F, K, rng, rub_w, rub_width=0.35):
    """Кромки по месту и открытости, пыль в защищённых местах, крупные вариации блеска.
    Выборочно: первая раскладка протирала почти все кромки ровной линией и сыпала пыль везде — это и читается
    процедурой. Поэтому сила места rub_w за вычетом 0,3 (обычные кромки — едва, места контакта — заметно), только
    открытые места (AO этапа 1 выше 0,8), и крупными кусками: часть кромки цела целиком."""
    Z = {}
    convex = K > 0.18
    d_e = dist_field(P, convex)
    expo = sstep(0.78, 0.97, P.ao)
    patch = sstep(0.3, 0.7, 0.7 * F["big"] + 0.3 * F["chips"])
    pres = np.clip(rub_w - 0.3, 0.0, 1.2) * expo * (0.3 + 0.7 * patch)
    Z["rub"] = edge_band(P, d_e, pres, F, width=rub_width) * P.on
    # пыль: только во внутренних углах закрытых мест, частицами с фото; слабая (ЧВК — чистят)
    concave = K < -0.25
    d_c = dist_field(P, concave, cap=4.0)
    grain = np.zeros(P.ids.shape, dtype=np.float32)
    grain[P.on] = tri(P.pos[P.on], P.nrm[P.on], photo("dust_grain", 0.0), 9.0, SEED + 5)
    Z["dust"] = (1.0 - sstep(0.1, 0.9, d_c)) * sstep(0.8, 0.45, P.ao) * sstep(0.3, 0.75, grain) * P.on
    # крупные вариации блеска: захватано и протёрто при чистке — облаками с фото, по трети площади в обе стороны
    t = 0.6 * F["big"] + 0.4 * F["big2"]
    q = np.percentile(t[P.on], [20, 40, 60, 80])
    Z["tone_lo"] = sstep(q[2], q[3], t) * P.on          # глаже, чуть темнее
    Z["tone_hi"] = sstep(q[1], q[0], t) * P.on          # матовее, чуть светлее
    return Z, d_e, d_c, expo


def fibers(P, where, n, rng):
    cand = np.argwhere(where)
    if len(cand) == 0 or n == 0:
        return np.zeros(P.ids.shape, dtype=np.float32)
    pick = cand[rng.choice(len(cand), size=min(n, len(cand)), replace=False)]
    ok = np.asarray(Image.fromarray(where.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(9))) > 0
    return lint(ok, [tuple(p) for p in pick], P.px_mm, rng, P.size)


# ── детали ───────────────────────────────────────────────────────────────────────────────────────────────────────────
PORT_X = (-74.2, 10.4)        # окно выброса (правый борт, Y < 0)


def upper(P, F, K, rng):
    x, y, z = P.x, P.y, P.z
    rec, rail = P.part("Upper_receiver"), P.part("Upper_rail")
    ch, latch = P.part("Charging_handle"), P.part("CH_latch_L", "CH_latch_R")
    fa, cover, rod = P.part("Forward_assist"), P.part("Dust_cover"), P.part("Dust_cover_rod", "Dust_cover_spring")
    # сила кромок по месту: защёлки и Т-ручка рукоятки заряжания (рука, одежда), досылатель, кромки окна и бугор
    # отражателя — сильнее; планка — средне; остальное — слабо (рабочее лёгкое)
    deflector = rec & (y < -17) & (z > 3) & inwin(x, -95, -93, -76, -74)     # бугор за окном: x −93…−76, борт до −21
    port_edge = rec & (y < -8) & inwin(x, PORT_X[0] - 4, PORT_X[0], PORT_X[1], PORT_X[1] + 4)
    cutout = rec & (x < -160) & (z > 14) & (y > 3)
    w = 0.55 + 0.9 * latch + 0.7 * (ch & (x < -176)) + 0.6 * fa + 0.5 * port_edge + 0.6 * deflector + 0.6 * cutout \
        + 0.2 * rail
    Z, d_e, d_c, expo = common(P, F, K, rng, w.astype(np.float32))
    # сквозь: FDE — точки чёрного анодирования на местах удара (бугор отражателя, вырез под защёлку, угол окна);
    # анодированные защёлки и Т-ручка — светлый алюминий на кончиках «ушей»
    thru_w = 0.45 * (deflector | cutout | (port_edge & (z < -2))) + 0.5 * (latch & (np.abs(y) > 26)) \
        + 0.3 * (ch & (x < -192))
    Z["thru"] = edge_band(P, d_e, thru_w * expo, F, width=0.2, chips=1.6) * P.on
    # хват: защёлки (пальцы тянут), Т-ручка сзади, торец досылателя (большой палец)
    Z["hand"] = (latch | (ch & (x < -190)) | (fa & (x < -165))).astype(np.float32)
    # латунные мазки на бугре отражателя (свежие жёлтые и старые бурые) и мелкие вмятинки от гильз
    smear = np.zeros(P.ids.shape, dtype=np.float32)
    smear[P.on] = tri(P.pos[P.on], P.nrm[P.on], photo("smear_oil", 1.0), 14.0, SEED + 41)
    Z["brass"] = deflector * sstep(0.25, 0.75, smear) * sstep(16.5, 19.5, -y)
    Z["dents"] = dots(P, deflector & (P.ny < -0.5), 14, rng, (0.2, 0.5), F)
    # масло: ось и пружина крышки окна, петля крышки, полоса масла у окна изнутри
    Z["oil"] = (rod | (cover & (z < 3))).astype(np.float32) * sstep(0.2, 0.6, F["cloudy"])
    # нагар — лёгкая дымка внутри (видно в окне): внутренние стенки ресивера у канала затвора
    r = np.hypot(y, z)
    inward = (P.ny * y + P.nz * z) / np.maximum(r, 1e-3) < -0.4
    Z["carbon"] = (rec & inward & (r < 16) & inwin(x, -90, -80, 20, 30)).astype(np.float32) * sstep(0.2, 0.7, F["big"])
    # вершины зубьев планки под основанием целика (и слабее — где стояла оптика) — примяты зажимами: глаже, поперечные
    # риски; по всей длине планки ровным пятнистым слоем читалось процедурой (проба 30.10)
    sight_seat = inwin(x, -173, -171, -126, -124)
    crest = rail & (P.nz > 0.95) & (z > 30.5) & (sight_seat | inwin(x, -112, -108, -72, -68))
    Z["crest"] = crest * (0.55 + 0.45 * sight_seat) * (0.6 + 0.4 * sstep(0.2, 0.6, F["cloudy"]))
    a, b = scratches(P, crest, 40.0, jitter_dir((0, 1, 0), rng, 0.15), rng, (1.0, 4.0), deep=0.25)
    Z["scr"] = a
    Z["scr_deep"] = b
    # крышка окна снаружи — короткие матовые царапины по ходу (бьёт по борту), борта — редкие в разные стороны
    a, b = scratches(P, cover & (P.ny < -0.7), 35.0, jitter_dir((1, 0, 0), rng, 0.2), rng, (1.0, 5.0), deep=0.0)
    Z["scr"] = np.maximum(Z["scr"], a)
    a, b = scratches(P, rec & (np.abs(P.ny) > 0.7) & (expo > 0.6), 1.2, random_dir(rng), rng, (1.5, 6.0), deep=0.2)
    Z["scr"], Z["scr_deep"] = np.maximum(Z["scr"], a), np.maximum(Z["scr_deep"], b)
    Z["lint"] = fibers(P, (Z["dust"] > 0.3) & (rec | rail), 3, rng)
    return Z


def bolt(P, F, K, rng):
    x, y, z = P.x, P.y, P.z
    car, blt = P.part("Bolt_carrier"), P.part("Bolt")
    r = np.hypot(y, z)
    w = 0.5 + 0.8 * (blt & (x > -10)) + 0.4 * P.part("Cam_pin") + 0.2 * car
    Z, d_e, d_c, expo = common(P, F, K, rng, w.astype(np.float32), rub_width=0.4)
    # полозья рамы и дорожка курка — продольные полированные полосы (трение о ресивер и курок каждый цикл)
    rails = car & (r > 11.5) & ((z < -8) | ((z > 8) & (np.abs(y) > 5)))
    track = car & (z < -10.5) & (np.abs(y) < 4.5) & (x > -160)
    a, b = scratches(P, rails | track, 900.0, jitter_dir((1, 0, 0), rng, 0.03), rng, (6.0, 30.0), deep=0.35)
    Z["polish"] = np.clip(0.55 * a + b + 0.6 * track * sstep(0.3, 0.7, F["cloudy"]), 0, 1)
    # масло: вся рама влажная, полозья и паз оси затвора — «мокро»
    Z["oil"] = ((car | blt) * (0.45 + 0.55 * sstep(0.35, 0.75, F["cloudy"]))).astype(np.float32) \
        * np.maximum(0.5, rails * 1.0)
    # нагар: зеркало затвора и тело затвора за упорами, хвост затвора
    Z["carbon"] = (blt & ((x > -1.8) | inwin(x, -16, -14, -6, -4))).astype(np.float32) * sstep(0.15, 0.6, F["big"] + 0.3)
    Z["lint"] = fibers(P, car & (expo > 0.3), 4, rng)
    return Z


def handguard(P, F, K, rng):
    x, y, z = P.x, P.y, P.z
    hg, rail = P.part("Handguard"), P.part("Handguard_rail")
    bot, side = P.part("Bottom_rail"), P.part("Side_rail")
    screws = P.part("Handguard_screw", "Bottom_rail_screw", "Side_rail_screw", "Side_rail_R_screw")
    front = sstep(255, 285, x)
    hold = window(x, 120, 150, 270, 285) * ((z < -8) | (np.abs(y) > 14))
    w = 0.45 + 0.8 * front * (z < 0) + 0.4 * hold + 0.25 * (bot | side) + 0.3 * screws
    Z, d_e, d_c, expo = common(P, F, K, rng, w.astype(np.float32))
    # сквозь — нижняя передняя кромка и передний торец (упор, чехол)
    Z["thru"] = edge_band(P, d_e, 0.5 * front * (z < -5) * expo, F, width=0.2, chips=1.6) * P.on
    # левая рука — низ и бока передней половины: глаже и темнее
    Z["hand"] = (hold * sstep(0.2, 0.55, F["cloudy"] + 0.25)).astype(np.float32) * (hg | bot | side)
    # вершины зубьев нижней планки под рукояткой — примяты, поперечные риски
    crest = bot & (P.nz < -0.95) & (z < -37.5) & inwin(x, 150, 160, 245, 255)
    Z["crest"] = crest * sstep(0.2, 0.6, F["cloudy"] + 0.3 * F["chips"])
    a, b = scratches(P, crest, 120.0, jitter_dir((0, 1, 0), rng, 0.15), rng, (1.0, 4.0), deep=0.25)
    Z["scr"], Z["scr_deep"] = a, b
    a, b = scratches(P, (hg | rail) & (expo > 0.6), 2.0, random_dir(rng), rng, (1.5, 6.0), deep=0.15)
    Z["scr"], Z["scr_deep"] = np.maximum(Z["scr"], a), np.maximum(Z["scr_deep"], b)
    a, b = scratches(P, hg & (hold > 0.5) & (z < -15), 6.0, jitter_dir((1, 0, 0), rng, 0.5), rng, (2.0, 7.0), deep=0.1)
    Z["scr"], Z["scr_deep"] = np.maximum(Z["scr"], a), np.maximum(Z["scr_deep"], b)
    Z["lint"] = fibers(P, (Z["dust"] > 0.3) & hg, 5, rng)
    return Z


def barrel(P, F, K, rng):
    x, y, z = P.x, P.y, P.z
    brake = P.part("Muzzle_brake", "Muzzle_lock_collar", "Muzzle_jam_nut")
    w = 0.25 + 0.7 * brake + 0.3 * P.part("Gas_block")
    Z, d_e, d_c, expo = common(P, F, K, rng, w.astype(np.float32))
    # нагар — только внутри: окна и канал ДТК, торец дула
    r = np.hypot(y, z)
    inward = (P.ny * y + P.nz * z) / np.maximum(r, 1e-3) < 0.2
    Z["carbon"] = (brake & ((inward & (r < 12.4)) | (x > 338.5) | (P.ao < 0.55))).astype(np.float32) \
        * sstep(0.1, 0.6, F["big"] + 0.25)
    # лыски ДТК — следы ключа: короткие светлые риски
    flats = P.part("Muzzle_brake") & ((np.abs(P.ny) > 0.97) | (np.abs(P.nz) > 0.97)) & (r > 10)
    a, b = scratches(P, flats, 25.0, random_dir(rng), rng, (0.8, 3.0), deep=0.3)
    Z["scr"], Z["scr_deep"] = a, b
    return Z


def stock(P, F, K, rng):
    x, y, z = P.x, P.y, P.z
    body, pad, latch = P.part("Stock_body"), P.part("Stock_buttpad"), P.part("Stock_latch")
    cups = P.part("Stock_QD_cup")
    corners = body & (x < -340) & ((z < -88) | (z > 14))
    w = 0.5 + 0.9 * corners + 0.6 * latch + 0.5 * pad * (z < -90) + 0.3 * cups
    Z, d_e, d_c, expo = common(P, F, K, rng, w.astype(np.float32))
    # щека — гребень заглажен до блеска и жирный; рычаг фиксатора — палец
    comb = body & (z > 12) & (P.nz > 0.5) & inwin(x, -350, -335, -250, -235)
    # на чёрном полимере жир щеки серыми облаками читался грязью (проба 30.10) — вдвое слабее
    Z["hand"] = np.maximum(0.45 * comb * sstep(0.2, 0.6, F["cloudy"] + 0.2), latch * (z < -22)).astype(np.float32)
    # нижние углы носка и пятки, низ затыльника — потёртости о землю; царапины в разные стороны
    a, b = scratches(P, (corners | (pad & (z < -95))) & (expo > 0.4), 40.0, random_dir(rng), rng, (1.0, 5.0), deep=0.2)
    Z["scr"], Z["scr_deep"] = a, b
    a, b = scratches(P, body & (np.abs(P.ny) > 0.8) & (expo > 0.6), 2.0, random_dir(rng), rng, (1.5, 6.0), deep=0.1)
    Z["scr"], Z["scr_deep"] = np.maximum(Z["scr"], a), np.maximum(Z["scr_deep"], b)
    # пыль в рифлении затыльника и в гнёздах QD сильнее
    Z["dust"] = np.maximum(Z["dust"], (pad | cups) * Z["dust"] * 1.6).clip(0, 1)
    Z["lint"] = fibers(P, (Z["dust"] > 0.3) & (pad | cups), 4, rng)
    return Z


def tube(P, F, K, rng):
    x, y, z = P.x, P.y, P.z
    tb, nut = P.part("Buffer_tube"), P.part("Castle_nut")
    w = 0.4 + 0.8 * nut + 0.3 * P.part("End_plate")
    Z, d_e, d_c, expo = common(P, F, K, rng, w.astype(np.float32))
    # трубка вдоль хода приклада — продольная полированная полоса снизу, риски вдоль
    stripe = tb & (P.nz < -0.6) & (x < -195) & (x > -400)
    a, b = scratches(P, stripe, 300.0, jitter_dir((1, 0, 0), rng, 0.04), rng, (5.0, 25.0), deep=0.2)
    Z["polish"] = np.clip(0.6 * a + b + 0.5 * stripe * sstep(0.35, 0.7, F["cloudy"]), 0, 1)
    # гайка — следы ключа в прорезях: короткие риски
    a, b = scratches(P, nut, 40.0, random_dir(rng), rng, (0.6, 2.5), deep=0.4)
    Z["scr"], Z["scr_deep"] = a, b
    return Z


def sights(P, F, K, rng):
    x, y, z = P.x, P.y, P.z
    leaf, base = P.part("Front_sight_leaf", "Rear_sight_leaf"), P.part("Front_sight_base", "Rear_sight_base")
    fingers = P.part("Front_sight_drum", "Rear_sight_drum", "Front_sight_base_button", "Rear_sight_base_button")
    ears = (leaf & (z > 60)) | (base & (z > 40))
    w = 0.6 + 0.7 * ears + 0.5 * fingers
    Z, d_e, d_c, expo = common(P, F, K, rng, w.astype(np.float32))
    Z["thru"] = edge_band(P, d_e, 0.4 * ears * expo, F, width=0.2, chips=1.6) * P.on
    Z["hand"] = fingers.astype(np.float32)
    Z["dust"] = np.clip(Z["dust"] * (1.0 + 0.8 * fingers), 0, 1)
    a, b = scratches(P, (leaf | base) & (expo > 0.6), 4.0, random_dir(rng), rng, (1.0, 4.0), deep=0.2)
    Z["scr"], Z["scr_deep"] = a, b
    return Z


def rounds(P, F, K, rng):
    Z, d_e, d_c, expo = common(P, F, K, rng, np.full(P.ids.shape, 0.4, dtype=np.float32))
    Z.pop("dust")
    # латунь — руки при снаряжении: отпечатки и пятна потускнения по всей гильзе
    Z["hand"] = P.on.astype(np.float32) * sstep(0.3, 0.7, F["cloudy"])
    Z["tarnish"] = P.on * sstep(0.45, 0.8, F["big2"] * 0.6 + F["chips"] * 0.4 + 0.1)
    return Z


RULES = {"upper": upper, "bolt": bolt, "handguard": handguard, "barrel": barrel, "stock": stock, "tube": tube,
         "sights": sights, "rounds": rounds}
# зоны, которые делятся по классу отделки (вид в Painter зависит от материала под местом)
BY_CLASS = ("rub", "thru", "scr", "scr_deep", "polish", "crest", "hand")


# Слои Painter по виду, а не по месту: места одного вида сводятся в одну маску с весами (раньше — слой на каждую зону
# и класс, 21 слой на ресивер: проект Painter упёрся в видеопамять 16 ГБ, и ресивер с цевьём выгрузились сплошным
# белым, проба 30.10). Мягкие маски — 2K. (вид: размер маски, [(зона, класс отделки или None — любой, вес)])
FAMILIES = {
    # заглажено и чуть темнее: захватано, хват, масло, примятые вершины зубьев, кромки и царапины песка, полоса трубки
    "smooth": (4096, [("tone_lo", None, 0.25), ("hand", None, 0.5), ("oil", None, 1.0), ("crest", None, 0.5),
                      ("rub", "fde", 0.75), ("scr", "fde", 0.6), ("polish", "fde", 0.9), ("rub", "brass", 0.3)]),
    "matte": (2048, [("tone_hi", None, 1.0)]),                       # протёрто при чистке — матовее
    "dust": (2048, [("dust", None, 1.0)]),
    # затёрто светлее: фосфат на кромках, царапины по анодированию и стали
    "light": (4096, [("rub", "phos", 0.8), ("scr", "anod", 0.9), ("scr", "phos", 0.9), ("scr", "nit", 0.9),
                     ("rub", "brass", 0.6)]),
    "scuff": (4096, [("rub", "poly", 0.8), ("rub", "rubber", 0.8), ("scr", "poly", 0.8), ("scr", "rubber", 0.8),
                     ("scr_deep", "poly", 1.0), ("scr_deep", "rubber", 1.0)]),   # полимер и резина — светлее, матовее
    "under_fde": (4096, [("thru", "fde", 1.0), ("scr_deep", "fde", 0.9), ("dents", None, 0.9)]),   # сквозь песок
    "alu": (4096, [("thru", "anod", 1.0), ("scr_deep", "anod", 0.9)]),                            # сквозь анодирование
    "steel": (4096, [("thru", "phos", 0.9), ("thru", "nit", 0.9), ("scr_deep", "phos", 0.85), ("scr_deep", "nit", 0.85)]),
    "polish": (4096, [("polish", "nit", 0.9), ("polish", "phos", 0.9), ("polish", "anod", 0.9)]),  # полозья рамы
    "anod_grey": (4096, [("rub", "anod", 0.85)]),
    "nit_satin": (4096, [("rub", "nit", 0.85)]),
    "brass": (4096, [("brass", None, 0.85)]),
    "carbon": (2048, [("carbon", None, 0.55)]),
    "lint": (4096, [("lint", None, 0.9)]),
    "tarnish": (2048, [("tarnish", None, 0.6)]),
    "prints": (2048, [("hand", None, 1.0)]),
}
CODE = {v: k for k, v in CLS.items()}


def save(P, Z):
    """Маски видов (FAMILIES) — наибольший из весов мест; какие есть — в <набор>_zones.json."""
    index = {}
    for fam, (size, items) in FAMILIES.items():
        v = np.zeros(P.ids.shape, dtype=np.float32)
        for zone, c, w in items:
            if zone not in Z:
                continue
            a = np.clip(np.nan_to_num(Z[zone]), 0.0, 1.0) * w
            if c is not None:
                a = a * (P.cls == CODE[c])
            np.maximum(v, a, out=v)
        if (v > 0.05).sum() < 30:
            continue
        img = Image.fromarray((v * 255.0 + 0.5).astype(np.uint8))
        if size != P.size:
            img = img.resize((size, size), Image.BILINEAR)
        img.save(os.path.join(WEAR, f"{P.name}_zone_f_{fam}_L.png"))
        index[fam] = int((v > 0.05).sum())
    with open(os.path.join(WEAR, f"{P.name}_zones.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    return index


COLORS = {"rub": (1.0, 0.2, 0.2), "thru": (0.0, 0.0, 0.0), "hand": (0.2, 0.5, 1.0), "dust": (0.9, 0.9, 0.3),
          "oil": (0.6, 0.0, 0.9), "carbon": (0.15, 0.15, 0.15), "brass": (1.0, 0.75, 0.1), "crest": (0.0, 1.0, 0.6),
          "scr": (1.0, 1.0, 1.0), "scr_deep": (1.0, 0.5, 0.0), "polish": (0.0, 0.9, 1.0), "lint": (1.0, 1.0, 1.0),
          "dents": (0.4, 0.2, 0.0), "tarnish": (0.3, 0.6, 0.2)}


def preview(P, Z):
    img = P.base.copy() * 0.6
    for k, col in COLORS.items():
        if k in Z:
            a = np.clip(Z[k], 0, 1)[..., None]
            img = img * (1 - a) + np.asarray(col) * a
    Image.fromarray((img * 255).astype(np.uint8)).resize((2048, 2048), Image.BILINEAR).save(
        os.path.join(WEAR, f"{P.name}_zones_preview.png"))


def main():
    names = [a for a in sys.argv[1:] if a in RULES] or SETS
    for name in names:
        rng = np.random.default_rng(SEED + sum(map(ord, name)))
        P = Part(name)
        K = convexity(P)
        F = fields(P, SEED + len(name))
        Z = RULES[name](P, F, K, rng)
        idx = save(P, Z)
        preview(P, Z)
        meds = {CLS[c]: tuple(np.round(np.median(P.base[P.cls == c], 0), 3)) for c in np.unique(P.cls) if c}
        print(name, f"{P.px_mm:.1f} пикс/мм", "| цвет основы:", meds)
        print("  зоны:", ", ".join(f"{k} {v}" for k, v in idx.items()))


if __name__ == "__main__":
    main()
