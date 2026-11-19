"""ВЕРАС-54 v14, этап 2 (износ): места следов в развёртке по геометрическим картам (wear_maps.py) — по образцу
tools/pkp/wear_place.py («Частокол», износ принят владельцем). Рисунок следа — умная маска владельца в Painter
(sp_veras_wear.py), эти карты только умножают её на место.

Места по форме (кривизна в 1/мм по соседним пикселям одной детали):
  edge — выпуклое скругление радиусом меньше ~1 мм (оси, спуск и рычаги круглые целиком — не «кромка»),
  edge_wide — скругления до ~25 мм (полимер, магазин), cavity — вогнутое и затенённое этапа 1, tops — купола заклёпок
  и головок осей, deep — глубокие швы и самое тёмное затенение, open — открытые плоскости, low — низ набора по высоте,
  rust — у заклёпок (кольцо вокруг купола) и в глубоких швах (подгруппа ржавчины, по умолчанию слабо).
Кромки, выступы и ржавчина — только под редкими крупными пятнами (sparse, доли EDGE_SHARE и т. д.).
Места эксплуатации — данные wear_places.json (мм в осях автомата: +X к дулу, +Y влево стрелка, +Z вверх) →
  <набор>_z_<id>.png; описание полей — в самом файле.

    python -X utf8 tools/veras54_v14/tex/wear_place.py [набор …] [stats]
      → _asset_src/veras54_v14/tex/wear/<набор>_<место>.png (разрешение набора; превью — wear/preview/<набор>.jpg)
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_sets as T  # noqa: E402

ROOT = "E:/Games/RING-godot"
MAPS = ROOT + "/_asset_src/veras54_v14/tex/wear_maps"
UV = ROOT + "/_asset_src/veras54_v14/tex/uv"
OUT = ROOT + "/_asset_src/veras54_v14/tex/wear"
PLACES = os.path.dirname(os.path.abspath(__file__)) + "/wear_places.json"
STAGE1 = T.MODEL_DIR + "/Карты v14/Заводская отделка v01"
Image.MAX_IMAGE_PIXELS = None

STEP = 2                 # шаг соседа, пикселей (на 2K — 1)
SEAM_MM = 1.2            # дальше — уже другой остров (шов развёртки), не сосед
EDGE_R = (1.6, 0.6)      # радиус скругления, мм: больше первого — не кромка, меньше второго — кромка целиком
EDGE_WIDE_R = (25.0, 6.0)
CAV_R = (2.0, 0.6)       # то же для вогнутого (угол, шов)
AO_CAV = (0.72, 0.45)    # затенение этапа 1: светлее первого — не угол, темнее второго — угол целиком
AO_INNER = (0.22, 0.38)  # темнее — изнанка и нутро, пыль туда не кладётся
TOPS_R = (6.0, 2.5)      # купол: обе кривизны круче радиуса первого — верхушка, второго — целиком
DEEP_AO = (0.55, 0.3)    # нагар и грязь: затенение этапа 1 темнее первого
DEEP_R = (0.8, 0.4)      # и узкие вогнутые швы
OPEN_AO = (0.6, 0.9)     # открытые плоскости — затенение светлее
# «где износ вообще есть» (владелец 2026-11-19: лёгкие потёртости на углах и рёбрах, «но не на всех, а очень
# разбросанно и без прямых ровных границ»): крупные пятна, доля кромок под ними
SPARSE_SCALES = ((22.0, 0.6), (7.0, 0.4))   # было 45 / 15 мм — кромки вытирались длинными сплошными участками
EDGE_SHARE = 0.2         # доля массы кромок набора с потёртостью (15–30 % — указание владельца)
TOPS_SHARE = 0.3         # доля головок заклёпок и осей
RUST_SHARE = 0.2         # доля мест ржавчины (кольца у заклёпок, швы)
EDGE_BLUR = 1.0          # растечь кромку на соседнюю плоскость (пикселей карты 4K)
RUST_RING = 2.2          # кольцо ржавчины вокруг заклёпки, мм (ширина от края купола)
# вес кромок и выступов по детали: пружины и спрятанное не трутся
WEIGHT = {"Recoil spring • coil": 0.0, "Bolt_Extractor_Spring": 0.0, "Hinge_Spring": 0.0, "Magazine_Spring": 0.0,
          "Magazine_Follower": 0.3, "Recoil_Guide_Rod": 0.5, "Ejector": 0.4, "Hinge_Pin": 0.6,
          # верхняя планка: общие кромки рода обводили светлым почти каждый зуб (износ v01) — у планки свой след
          # (top_rail_wear: вытянутые вдоль автомата участки), общий род её не трогает
          "Top_Rail": 0.0}

# переводчик: ось (X, Z), ход от предохранителя до «ОД» (part_rig: −9° … +7,3° от «АВ»); в файле развёртки — предохранитель
SEL_AXIS = (60.0, -8.5)
SEL_SWING = 16.3
SEL_ARC_W = 0.9          # полуширина дуги-царапины, мм
SEL_ARC_IN = 5.0         # дуга — на столько ближе к оси, чем конец рычага (там у рычага выступ фиксатора)
WINDOW_X = (155.0, 241.0)   # окно крышки над рамой (asset-state, вторая выдача: X 157,5…238; с запасом)


def ids(name, n):
    z = np.load(f"{UV}/{name}_tris.npz")
    names = [str(x) for x in np.atleast_1d(z["names"])]
    im = Image.new("I", (n, n), -1)
    dr = ImageDraw.Draw(im)
    for tri, o in zip(z["tri"], z["obj"]):
        dr.polygon([(float(u) * n, (1.0 - float(v)) * n) for u, v in tri], fill=int(o))
    return names, np.asarray(im)


def shift(a, dy, dx):
    h, w = a.shape[:2]
    ys = np.clip(np.arange(h) + dy, 0, h - 1)
    xs = np.clip(np.arange(w) + dx, 0, w - 1)
    return a[ys][:, xs]


def curvature(pos, nrm, obj, step):
    """Нормальная кривизна (1/мм) по четырём направлениям: наибольшая выпуклая, наибольшая вогнутая и наименьшая
    со знаком (больше нуля во все стороны — купол заклёпки)."""
    kmax = np.zeros(obj.shape, np.float32)
    kmin = np.zeros(obj.shape, np.float32)
    klow = np.full(obj.shape, np.inf, np.float32)
    s = step
    for dy, dx in ((0, s), (s, 0), (s, s), (s, -s)):
        for sg in (1, -1):
            p2, n2, o2 = shift(pos, sg * dy, sg * dx), shift(nrm, sg * dy, sg * dx), shift(obj, sg * dy, sg * dx)
            dp = p2 - pos
            d2 = (dp * dp).sum(-1)
            ok = (obj >= 0) & (o2 == obj) & (d2 > 1e-8) & (d2 < SEAM_MM * SEAM_MM)
            k = np.where(ok, ((n2 - nrm) * dp).sum(-1) / np.maximum(d2, 1e-8), 0.0).astype(np.float32)
            np.maximum(kmax, k, out=kmax)
            np.minimum(kmin, k, out=kmin)
            np.minimum(klow, np.where(ok, k, np.inf), out=klow)
    klow[~np.isfinite(klow)] = 0.0
    return kmax, kmin, klow


def vnoise(p, scale, seed):
    """Объёмный шум 0…1 по положению (мм) — одинаков по обе стороны шва развёртки. Только место (где след есть),
    не рисунок: рисунок даёт умная маска."""
    lat = np.random.default_rng(seed).random((64, 64, 64)).astype(np.float32)
    q = p / scale
    i = np.floor(q).astype(np.int64)
    f = (q - i).astype(np.float32)
    f = f * f * (3.0 - 2.0 * f)
    i0, i1 = i % 64, (i + 1) % 64
    out = np.zeros(len(p), np.float32)
    for cx, wx in ((i0[:, 0], 1.0 - f[:, 0]), (i1[:, 0], f[:, 0])):
        for cy, wy in ((i0[:, 1], 1.0 - f[:, 1]), (i1[:, 1], f[:, 1])):
            for cz, wz in ((i0[:, 2], 1.0 - f[:, 2]), (i1[:, 2], f[:, 2])):
                out += lat[cx, cy, cz] * wx * wy * wz
    return out


def variation(pos, used, scales, seed, lo, hi):
    v = np.zeros(used.shape, np.float32)
    pu = pos[used]
    acc = np.zeros(len(pu), np.float32)
    for k, (sc, w) in enumerate(scales):
        acc += w * vnoise(pu, sc, seed + k)
    v[used] = smooth(acc, lo, hi)
    return v


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def band(x, a, b, soft):
    """1 внутри [a, b], мягкий спад шириной soft за краями."""
    return smooth(x, a - soft, a) * (1.0 - smooth(x, b, b + soft))


def objmask(names, obj, wanted):
    ids_ = [i for i, nm in enumerate(names) if nm in wanted]
    return np.isin(obj, ids_) if ids_ else np.zeros(obj.shape, bool)


def load(name):
    z = np.load(f"{MAPS}/{name}_maps.npz")
    pos, nrm = z["pos"], z["nrm"].astype(np.float32)
    n = pos.shape[0]
    names, obj = ids(name, n)
    lo = pos.reshape(-1, 3).min(0)
    empty = np.all(np.abs(pos - lo) < 1.0, axis=-1)        # пиксели, не попавшие в запекание (край острова)
    obj = np.where(empty, -1, obj)
    return names, obj, pos, nrm


class Saver:
    def __init__(self, name):
        self.name = name
        self.saved = {}

    def __call__(self, kind, arr, blur=0.0):
        im = Image.fromarray(np.uint8(np.clip(arr, 0, 1) * 255))
        if blur:
            im = Image.fromarray(np.maximum(np.asarray(im), np.asarray(im.filter(ImageFilter.GaussianBlur(blur)))))
        im.save(f"{OUT}/{self.name}_{kind}.png")
        self.saved[kind] = float((np.asarray(im) > 127).mean())


def sparse(pos, used, weight, share, seed, scales=SPARSE_SCALES, soft=0.05, stretch=1.0):
    """«Где износ вообще есть»: крупные пятна объёмного шума (десятки мм), порог подобран так, чтобы под пятнами
    оказалась доля share массы weight (кромок места). Владелец 2026-11-19: потёртости «не на всех, очень разбросанно».
    stretch < 1 — пятна вытянуты вдоль X (планка: съём вдоль автомата, а не по зубу)."""
    out = np.zeros(used.shape, np.float32)
    m = used & (weight > 0.05)
    if not m.any() or share >= 0.999:
        return np.where(used, 1.0, 0.0).astype(np.float32)
    pu = pos[used]
    if stretch != 1.0:
        pu = pu * np.array([stretch, 1.0, 1.0], np.float32)
    acc = np.zeros(len(pu), np.float32)
    for k, (sc, w) in enumerate(scales):
        acc += w * vnoise(pu, sc, seed + k)
    full = np.zeros(used.shape, np.float32)
    full[used] = acc
    a, wts = full[m], weight[m]
    order = np.argsort(-a)
    cum = np.cumsum(wts[order]) / wts.sum()
    t = a[order][min(len(order) - 1, int(np.searchsorted(cum, share)))]
    out[used] = smooth(acc, t - soft, t + soft)
    return out


def place_set(name, stats=False):
    names, obj, pos, nrm = load(name)
    n = pos.shape[0]
    step = max(1, round(STEP * n / 4096))
    kmax, kmin, klow = curvature(pos, nrm, obj, step)
    used = obj >= 0
    if stats:
        for i, nm in enumerate(names):
            m = obj == i
            if m.sum() < 100:
                continue
            q = np.percentile(kmax[m], [50, 80, 90, 95, 99])
            print(f"  {nm:28s} кривизна выпуклая p50/80/90/95/99: " + " ".join(f"{x:.2f}" for x in q)
                  + f"   радиус p95 {1 / max(q[3], 1e-3):.2f} мм", flush=True)
    edge = smooth(kmax, 1.0 / EDGE_R[0], 1.0 / EDGE_R[1])
    cav = smooth(-kmin, 1.0 / CAV_R[0], 1.0 / CAV_R[1])
    ao_p = f"{STAGE1}/{name}_occlusionRoughnessMetallic.png"
    ao = np.ones(obj.shape, np.float32)
    if os.path.exists(ao_p):
        ao = np.asarray(Image.open(ao_p).convert("RGB").resize((n, n), Image.BILINEAR), np.float32)[..., 0] / 255.0
        # углы по затенению — только средняя тень: глубокая (изнанка коробки, нутро цевья) — не угол, иначе светлая пыль
        # заливала изнутри целые оболочки (первый прогон 19.11: 60 % карты цвета коробки серое)
        cav = np.maximum(cav, smooth(-ao, -AO_CAV[0], -AO_CAV[1]) * smooth(ao, AO_INNER[0], AO_INNER[1]))
    tops = smooth(klow, 1.0 / TOPS_R[0], 1.0 / TOPS_R[1])
    deep = np.maximum(smooth(-ao, -DEEP_AO[0], -DEEP_AO[1]), smooth(-kmin, 1.0 / DEEP_R[0], 1.0 / DEEP_R[1]))
    zz = pos[..., 2]
    z0, z1 = (np.percentile(zz[used], [1, 99]) if used.any() else (0.0, 1.0))
    low = np.clip(1.0 - (zz - z0) / max(z1 - z0, 1e-3), 0.0, 1.0) ** 1.5
    w = np.array([WEIGHT.get(nm, 1.0) for nm in names], np.float32)
    wm = np.where(used, w[np.clip(obj, 0, None)], 0.0)
    one = np.where(used, 1.0, 0.0)
    raw = {"edge": edge * wm, "edge_wide": smooth(kmax, 1.0 / EDGE_WIDE_R[0], 1.0 / EDGE_WIDE_R[1]) * wm,
           "tops": tops * wm, "cavity": cav * one}
    # общие места рода: кромки и выступы — только под редкими крупными пятнами (доля EDGE_SHARE / TOPS_SHARE)
    edge_s = raw["edge"] * sparse(pos, used, raw["edge"], EDGE_SHARE, 11)
    edge_w = raw["edge_wide"] * sparse(pos, used, raw["edge_wide"], EDGE_SHARE, 13)
    tops_s = raw["tops"] * sparse(pos, used, raw["tops"], TOPS_SHARE, 23)
    deep *= one
    low *= one
    raw["deep"] = deep
    opn = smooth(ao, OPEN_AO[0], OPEN_AO[1]) * (1.0 - raw["edge"]) * one
    # ржавчина: кольцо вокруг купола заклёпки (расширение купола минус купол) и глубокие швы, редкими участками
    px_mm = n / 4096 * 12.0
    ring_im = Image.fromarray(np.uint8(np.clip(raw["tops"], 0, 1) * 255)).filter(
        ImageFilter.MaxFilter(1 + 2 * max(1, int(RUST_RING * px_mm / 2))))
    ring = np.asarray(ring_im, np.float32) / 255.0 * (1.0 - raw["tops"])
    seam = smooth(-kmin, 1.0 / DEEP_R[0], 1.0 / DEEP_R[1])        # узкие швы по форме (не тень этапа 1: она
    rust_w = np.maximum(ring * 0.9, seam * 0.6) * one             # закрывала изнанку коробки целиком)
    rust = rust_w * sparse(pos, used, rust_w, RUST_SHARE, 41, ((14.0, 0.6), (5.0, 0.4)))
    os.makedirs(OUT, exist_ok=True)
    save = Saver(name)
    save("edge", edge_s, EDGE_BLUR * n / 4096)
    save("edge_wide", edge_w)
    save("cavity", raw["cavity"])
    for kind, arr in (("tops", tops_s), ("deep", deep), ("open", opn), ("low", low), ("rust", rust)):
        save(kind, arr)
    places(name, names, obj, pos, nrm, raw, save)
    print(f"PLACE {name} {n}: " + ", ".join(f"{k} {v:.3f}" for k, v in save.saved.items()), flush=True)
    preview(name, save.saved)
    return save.saved


# --- места эксплуатации (wear_places.json) -----------------------------------------------------------------------------

def _maps_of(other):
    names, obj, pos, nrm = load(other)
    return names, obj, pos


def selector_lever():
    """Рычаг переводчика в позе файла (предохранитель): радиус конца от оси и нижняя кромка по радиусам (угол, рад)."""
    names, obj, pos = _maps_of("controls")
    m = objmask(names, obj, {"Selector_Lever"}) & (pos[..., 1] < -15.0)
    p = pos[m]
    dx, dz = p[:, 0] - SEL_AXIS[0], p[:, 2] - SEL_AXIS[1]
    r = np.hypot(dx, dz)
    th = np.arctan2(dz, dx)
    bins = np.arange(0.0, r.max() + 2.0, 1.0)
    low = np.full(len(bins), np.nan, np.float32)
    idx = np.clip(r.astype(int), 0, len(bins) - 1)
    for b in np.unique(idx):
        low[b] = th[idx == b].min()
    return float(np.percentile(r, 99.8)), bins, low


def magazine_box():
    names, obj, pos = _maps_of("magazine")
    m = objmask(names, obj, {"Magazine_Body"})
    p = pos[m]
    return np.percentile(p, 0.5, axis=0), np.percentile(p, 99.5, axis=0)


def special(sname, names, obj, pos, nrm, raw, part):
    """Места, которые считаются по форме, а не коробкой."""
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    if sname in ("selector_arc", "selector_rub"):
        r_tip, bins, lowth = selector_lever()
        dx, dz = x - SEL_AXIS[0], z - SEL_AXIS[1]
        r = np.hypot(dx, dz)
        th = np.arctan2(dz, dx)
        ok = np.isfinite(lowth)
        lim = np.interp(r, bins[ok], lowth[ok])
        sw = np.radians(SEL_SWING)
        side = part & (y < -14.0) & (nrm[..., 1] < -0.6)
        swept = band(th, lim - sw - np.radians(1.0), lim + np.radians(0.5), np.radians(1.0))
        if sname == "selector_arc":
            # серп по ходу конца рычага (образец АК-12): шире посередине хода, к концам сходит на нет; край чёткий
            # (мягкий край 0,5 мм и ровная ширина в v01 читались вертикальным мазком); рядом вторая тонкая риска
            rc = r_tip - SEL_ARC_IN
            t = np.clip((th - (lim - sw)) / max(sw, 1e-3), 0.0, 1.0)
            prof = np.sin(np.pi * t) ** 0.7
            w1 = SEL_ARC_W * (0.15 + 0.85 * prof)
            v1 = smooth(-np.abs(r - rc), -w1 - 0.12, -w1 + 0.12)
            rc2 = rc - 1.9
            w2 = 0.3 * SEL_ARC_W * prof
            v2 = 0.8 * smooth(-np.abs(r - rc2), -w2 - 0.1, -w2 + 0.1) * smooth(t, 0.15, 0.35) * (1 - smooth(t, 0.7, 0.9))
            v = np.maximum(v1, v2) * swept
        else:
            v = band(r, r_tip - 16.0, r_tip - 1.0, 3.0) * swept
        return np.where(side, v, 0.0)
    if sname == "well":
        lo, hi = magazine_box()
        zb = np.percentile(z[part], 0.5)
        well = part & (x > lo[0] - 6.0) & (x < hi[0] + 6.0) & (z < zb + 9.0)
        return np.where(well, np.maximum(raw["edge"], 0.5 * raw["edge_wide"]), 0.0)
    if sname == "mag_top":
        lo, hi = magazine_box()
        return np.where(part, smooth(z, hi[2] - 48.0, hi[2] - 20.0), 0.0)
    if sname == "mag_heel":
        lo, hi = magazine_box()
        return np.where(part, smooth(-z, -(lo[2] + 24.0), -(lo[2] + 4.0)), 0.0)
    raise SystemExit("нет особого места " + sname)


def load_places():
    with open(PLACES, encoding="utf-8") as f:
        return json.load(f)["places"]


# --- штампы владельца (растровые маски в мировых координатах) ---------------------------------------------------------
STAMPS = T.WORK + "/owner_masks"
_stamp_cache = {}


def _stamp_img(name, crop=None):
    key = (name, tuple(crop) if crop else None)
    if key not in _stamp_cache:
        im = Image.open(f"{STAMPS}/{name}").convert("L")
        if crop:
            w, h = im.size
            im = im.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
        _stamp_cache[key] = np.asarray(im, np.float32) / 255.0
    return _stamp_cache[key]


def stamp_basis(wh):
    """Проектор штампа: d — направление «из детали на зрителя» (кадр смотрит против d), u — ось картинки вправо
    (по умолчанию проекция +X на плоскость кадра), v = d × u — вверх; поворот rot (град, против часовой) — картинки
    в кадре."""
    d = np.array(wh.get("dir", [0, 0, 1]), np.float64)
    d /= np.linalg.norm(d)
    u0 = np.array(wh.get("u", [1, 0, 0]), np.float64)
    u = u0 - d * (u0 @ d)
    u /= np.linalg.norm(u)
    v = np.cross(d, u)
    a = np.radians(wh.get("rot", 0.0))
    u, v = u * np.cos(a) + v * np.sin(a), -u * np.sin(a) + v * np.cos(a)
    return d.astype(np.float32), u.astype(np.float32), v.astype(np.float32)


def stamp(wh, pos, nrm, footprint=False):
    """Штамп владельца на детали: картинка wh["file"] (часть crop [u0, v0, u1, v1] долями) размером size [ш, в] мм
    с центром center, проекция по dir (кадр смотрит на деталь против dir), слой глубиной depth мм вдоль dir от центра
    (±), только грани, повёрнутые к кадру (n·dir > min_dot). Билинейная выборка; плотность штампа должна быть не ниже
    плотности набора (проверяется печатью). footprint — прямоугольник кадра (для исключения других слоёв)."""
    img = _stamp_img(wh["file"], wh.get("crop"))
    h, w = img.shape
    d, u, v = stamp_basis(wh)
    c = np.array(wh["center"], np.float32)
    sw, sh = wh["size"][0], wh["size"][0] * h / w if len(wh["size"]) < 2 else wh["size"][1]
    q = pos - c
    pu, pv, pd = q @ u, q @ v, q @ d
    s = pu / sw + 0.5
    t = 0.5 - pv / sh
    inside = (s >= 0) & (s <= 1) & (t >= 0) & (t <= 1) & (np.abs(pd) <= wh.get("depth", 6.0))
    face = smooth(nrm @ d, wh.get("min_dot", 0.15) - 0.1, wh.get("min_dot", 0.15) + 0.1)
    if footprint:
        return np.where(inside, face, 0.0).astype(np.float32)
    x = np.clip(s * (w - 1), 0, w - 1.001)
    y = np.clip(t * (h - 1), 0, h - 1.001)
    x0, y0 = x.astype(np.int64), y.astype(np.int64)
    fx, fy = x - x0, y - y0
    val = (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy)
           + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)
    dens = min(w / sw, h / sh)
    if dens < 11.5:
        print(f"  ВНИМАНИЕ: плотность штампа {wh['file']} {dens:.1f} пикс/мм — ниже плотности набора", flush=True)
    return np.where(inside, val * face, 0.0).astype(np.float32)


def places(name, names, obj, pos, nrm, raw, save):
    used = obj >= 0
    for i, pl in enumerate(load_places()):
        if pl["set"] != name or pl.get("off"):
            continue
        part = objmask(names, obj, set(pl["parts"]))
        if not part.any():
            print("  НЕТ ДЕТАЛЕЙ места", pl["id"], pl["parts"], flush=True)
            continue
        wh = pl["where"]
        t = wh["type"]
        if t == "parts":
            v = part * 1.0
        elif t == "box":
            c, s, soft = np.array(wh["center"], np.float32), np.array(wh["size"], np.float32), wh.get("soft", 2.0)
            v = part * 1.0
            for a in range(3):
                v = v * band(pos[..., a], c[a] - s[a] / 2, c[a] + s[a] / 2, soft)
        elif t == "segment":
            a, b = np.array(wh["a"], np.float32), np.array(wh["b"], np.float32)
            ab = b - a
            tt = np.clip(((pos - a) * ab).sum(-1) / max(float((ab * ab).sum()), 1e-6), 0.0, 1.0)
            d = np.linalg.norm(pos - (a + tt[..., None] * ab), axis=-1)
            v = part * (1.0 - smooth(d, wh["radius"], wh["radius"] + wh.get("soft", 2.0)))
        elif t == "special":
            v = special(wh["name"], names, obj, pos, nrm, raw, part)
        elif t == "stamp":
            v = part * stamp(wh, pos, nrm)
        else:
            raise SystemExit("неизвестное место " + t)
        if "facing" in pl:
            f = np.array(pl["facing"], np.float32)
            f /= np.linalg.norm(f)
            md = pl.get("min_dot", 0.3)
            v = v * smooth((nrm * f).sum(-1), md - 0.15, md + 0.15)
        if pl.get("on"):
            v = v * raw[pl["on"]]
        # штампы владельца важнее: под их кадром прежний след этого места гасится (exclude — id штампов, k — насколько)
        if pl.get("exclude"):
            byid = {p["id"]: p for p in load_places()}
            for sid in pl["exclude"]:
                fp = stamp(byid[sid]["where"], pos, nrm, footprint=True)
                v = v * (1.0 - pl.get("exclude_k", 1.0) * fp)
        if pl.get("sparse", 1.0) < 1.0:
            sc = tuple(tuple(x) for x in pl.get("sparse_mm", SPARSE_SCALES))
            v = v * sparse(pos, used, v, pl["sparse"], 100 + i, sc, pl.get("sparse_soft", 0.05),
                           pl.get("sparse_stretch", 1.0))
        save("z_" + pl["id"], v, 1.0 if pl.get("on") == "edge" else 0.0)


def preview(name, saved):
    """Лист мест набора: каждая карта уменьшенной плиткой с подписью."""
    from PIL import ImageFont
    os.makedirs(f"{OUT}/preview", exist_ok=True)
    kinds = list(saved)
    tw = 384
    cols = 5
    rows = (len(kinds) + cols - 1) // cols
    sh = Image.new("RGB", (cols * tw, rows * (tw + 20)), (20, 20, 20))
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)
    dr = ImageDraw.Draw(sh)
    for i, k in enumerate(kinds):
        im = Image.open(f"{OUT}/{name}_{k}.png").convert("L").resize((tw, tw), Image.BILINEAR)
        cx, cy = (i % cols) * tw, (i // cols) * (tw + 20)
        sh.paste(im.convert("RGB"), (cx, cy + 20))
        dr.text((cx + 4, cy + 2), f"{name}_{k}  {saved[k]:.4f}", fill=(230, 230, 230), font=font)
    sh.save(f"{OUT}/preview/{name}.jpg", quality=88)


def main():
    a = sys.argv[1:]
    stats = "stats" in a
    names = [x for x in a if x != "stats"] or [s for s in T.SETS if os.path.exists(f"{MAPS}/{s}_maps.npz")]
    summary = {}
    for nm in names:
        summary[nm] = place_set(nm, stats)
    path = f"{OUT}/places.json"
    old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    old.update(summary)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(old, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
