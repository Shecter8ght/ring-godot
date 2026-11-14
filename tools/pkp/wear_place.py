"""«Частокол», этап 2 (износ): места следов в развёртке по геометрическим картам (tools/pkp/wear_maps.py) — кривизна
в 1/мм по соседним пикселям одной детали. Кромка — выпуклое скругление радиусом меньше ~1 мм (оси, спуск, рычаги
круглые целиком — они не «кромка»), угол и шов — вогнутое скругление или затенение этапа 1. Рисунок следа — умная
маска владельца в Painter (sp_pkp_wear.py), эти карты только умножают её на место.

    python -X utf8 tools/pkp/wear_place.py [набор …] [stats]   → _asset_src/pkp/tex/wear/<набор>_{edge,edge_wide,cavity,tops,deep,open,low}.png
    и места по деталям: touch (хват), cover_rear (задняя кромка крышки), charge_path (ход рукоятки
    перезаряжания), feet (пятки сошек), box_bottom (низ коробок)

Вес места по детали — WEIGHT (рукоятка перезаряжания и спуск трутся рукой больше, пружины не трутся)."""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_sets as T  # noqa: E402

ROOT = "E:/Games/RING-godot"
MAPS = ROOT + "/_asset_src/pkp/tex/wear_maps"
OUT = ROOT + "/_asset_src/pkp/tex/wear"
STAGE1 = T.MODEL_DIR + "/текстуры_этап1_v02"
Image.MAX_IMAGE_PIXELS = None

STEP = 2                 # шаг соседа, пикселей
SEAM_MM = 1.2            # дальше — уже другой остров (шов развёртки), не сосед
EDGE_R = (1.6, 0.6)      # радиус скругления, мм: больше первого — не кромка, меньше второго — кромка целиком
EDGE_WIDE_R = (25.0, 8.0)  # «широкая кромка» — краска коробок: у них скругления 9–12 мм, и об углы краска сходит
CAV_R = (2.0, 0.6)       # то же для вогнутого (угол, шов)
AO_CAV = (0.72, 0.45)    # затенение этапа 1: светлее первого — не угол, темнее второго — угол целиком
TOPS_R = (6.0, 2.5)      # купол: обе кривизны круче радиуса первого — верхушка, второго — целиком
DEEP_AO = (0.55, 0.3)    # чёрный нагар: затенение этапа 1 темнее первого
DEEP_R = (0.8, 0.4)      # и узкие вогнутые швы
OPEN_AO = (0.6, 0.9)     # открытые плоскости — затенение светлее
TOUCH = {"Pistol_Grip", "Rail_Forend", "Trigger", "Charging_Handle", "Bipod_Yoke", "Bipod_Leg_L", "Bipod_Leg_R",
         "Carry_Handle", "Stock", "Cover_Latch", "Safety_Lever"}
REAR_LEN = (35.0, 190.0)  # задняя кромка крышки: насколько износ тянется к дулу, мм (меняется по сечению крышки)
CHARGE_TRAVEL = 149.0     # ход рукоятки перезаряжания (tools/pkp/dims.py, CH_TRAVEL)
CHARGE_MARGIN = 6.0       # путь рукоятки шире её габарита, мм
FOOT_MM = 22.0            # пятка сошки: нижние мм
EDGE_VARY = ((60.0, 0.55), (18.0, 0.3), (6.0, 0.15))   # шум участков кромки: масштаб мм, вес
TOPS_VARY = ((25.0, 0.7), (9.0, 0.3))                   # шум заклёпок и винтов
EDGE_BLUR = 1.0          # растечь кромку на соседнюю плоскость (пикселей карты 4K)
WEIGHT = {"Charging_Handle": 1.0, "Trigger": 1.0, "Safety_Lever": 1.0, "Cover_Latch": 1.0,
          "Recoil_Spring": 0.0, "Cover_Lever_Spring": 0.0, "Retainer_Spring": 0.0, "Rear_Sight_Spring": 0.0,
          "Bipod_Spring": 0.0, "Box100_Latch_Spring": 0.0, "Box200_Latch_Spring": 0.0}


def ids(name, n):
    z = np.load(f"{ROOT}/_asset_src/pkp/tex/uv/{name}_tris.npz")
    names = [str(x) for x in np.atleast_1d(z["names"])]
    im = Image.new("I", (n, n), -1)
    dr = ImageDraw.Draw(im)
    for tri, o in zip(z["tri"], z["obj"]):
        dr.polygon([(float(u) * n, (1.0 - float(v)) * n) for u, v in tri], fill=int(o))
    return names, np.asarray(im)


def shift(a, dy, dx):
    """a[y + dy, x + dx] на месте (y, x); за краем — повтор края."""
    h, w = a.shape[:2]
    ys = np.clip(np.arange(h) + dy, 0, h - 1)
    xs = np.clip(np.arange(w) + dx, 0, w - 1)
    return a[ys][:, xs]


def curvature(pos, nrm, obj):
    """Нормальная кривизна (1/мм) по четырём направлениям: наибольшая выпуклая, наибольшая вогнутая и наименьшая
    со знаком (больше нуля во все стороны — купол: головка заклёпки, винта; у оси вдоль неё — ноль)."""
    kmax = np.zeros(obj.shape, np.float32)
    kmin = np.zeros(obj.shape, np.float32)
    klow = np.full(obj.shape, np.inf, np.float32)
    s = STEP
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
    """Объёмный шум 0…1 по положению (мм): решётка случайных значений с шагом scale, плавная интерполяция —
    одинаков по обе стороны шва развёртки."""
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
    """Где износ есть, где нет: шум нескольких масштабов (мм, вес) → порог с мягким переходом."""
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


def place_set(name, stats=False):
    z = np.load(f"{MAPS}/{name}_maps.npz")
    pos, nrm = z["pos"], z["nrm"].astype(np.float32)
    n = pos.shape[0]
    names, obj = ids(name, n)
    kmax, kmin, klow = curvature(pos, nrm, obj)
    if stats:
        for i, nm in enumerate(names):
            m = obj == i
            if m.sum() < 100:
                continue
            q = np.percentile(kmax[m], [50, 80, 90, 95, 99])
            print(f"  {nm:20s} кривизна выпуклая p50/80/90/95/99: " + " ".join(f"{x:.2f}" for x in q)
                  + f"   радиус p95 {1 / max(q[3], 1e-3):.2f} мм", flush=True)
    edge = smooth(kmax, 1.0 / EDGE_R[0], 1.0 / EDGE_R[1])
    cav = smooth(-kmin, 1.0 / CAV_R[0], 1.0 / CAV_R[1])
    ao_p = f"{STAGE1}/{name}_occlusionRoughnessMetallic.png"
    ao = np.ones(obj.shape, np.float32)
    if os.path.exists(ao_p):
        ao = np.asarray(Image.open(ao_p).convert("RGB").resize((n, n), Image.BILINEAR), np.float32)[..., 0] / 255.0
        cav = np.maximum(cav, smooth(-ao, -AO_CAV[0], -AO_CAV[1]))
    # v02 (образцы 02, 06): вытертые до блеска верхушки заклёпок и винтов, чёрный нагар в глубоких швах, открытые
    # плоскости (под пятна вытертого воронения), низ набора по высоте (грязь коробок копится снизу)
    tops = smooth(klow, 1.0 / TOPS_R[0], 1.0 / TOPS_R[1])
    deep = np.maximum(smooth(-ao, -DEEP_AO[0], -DEEP_AO[1]), smooth(-kmin, 1.0 / DEEP_R[0], 1.0 / DEEP_R[1]))
    used = obj >= 0
    zz = pos[..., 2]
    z0, z1 = (np.percentile(zz[used], [1, 99]) if used.any() else (0.0, 1.0))
    low = np.clip(1.0 - (zz - z0) / max(z1 - z0, 1e-3), 0.0, 1.0) ** 1.5
    w = np.ones(len(names), np.float32)
    for i, nm in enumerate(names):
        w[i] = WEIGHT.get(nm, 1.0)
    wm = np.where(obj >= 0, w[np.clip(obj, 0, None)], 0.0)
    edge_w = smooth(kmax, 1.0 / EDGE_WIDE_R[0], 1.0 / EDGE_WIDE_R[1]) * wm
    edge *= wm
    tops *= wm
    # владелец 2026-11-14 к v02: «стёртость до металла… слишком равномерно и одинаково, так в жизни не истирается,
    # должно быть как-то рандомно» — кромка вытерта участками разной длины, заклёпки — какие-то блестят, какие-то нет
    raw_edge, raw_edge_w = edge.copy(), edge_w.copy()
    vary = variation(pos, obj >= 0, EDGE_VARY, 11, 0.40, 0.58)
    edge = edge * vary
    edge_w = edge_w * (0.35 + 0.65 * vary)
    tops = tops * variation(pos, obj >= 0, TOPS_VARY, 23, 0.38, 0.62)
    one = np.where(obj >= 0, 1.0, 0.0)
    cav *= one
    deep *= one
    low *= one
    opn = smooth(ao, OPEN_AO[0], OPEN_AO[1]) * (1.0 - edge) * one
    os.makedirs(OUT, exist_ok=True)
    im = Image.fromarray(np.uint8(np.clip(edge, 0, 1) * 255))
    if EDGE_BLUR:
        im = Image.fromarray(np.maximum(np.asarray(im), np.asarray(im.filter(ImageFilter.GaussianBlur(EDGE_BLUR)))))
    im.save(f"{OUT}/{name}_edge.png")
    Image.fromarray(np.uint8(np.clip(cav, 0, 1) * 255)).save(f"{OUT}/{name}_cavity.png")
    Image.fromarray(np.uint8(np.clip(edge_w, 0, 1) * 255)).save(f"{OUT}/{name}_edge_wide.png")
    for kind, arr in (("tops", tops), ("deep", deep), ("open", opn), ("low", low)):
        Image.fromarray(np.uint8(np.clip(arr, 0, 1) * 255)).save(f"{OUT}/{name}_{kind}.png")
    print(f"PLACE {name}: кромка {float((edge[used] > 0.5).mean()):.3f}, углы {float((cav[used] > 0.5).mean()):.3f}, "
          f"верхушки {float((tops[used] > 0.5).mean()):.3f}, швы {float((deep[used] > 0.5).mean()):.3f}, "
          f"открытое {float((opn[used] > 0.5).mean()):.3f}", flush=True)
    special(name, names, obj, pos, nrm, raw_edge, raw_edge_w, low)
    return names, obj, edge, cav


def objmask(names, obj, wanted):
    """Пиксели деталей из списка (имя целиком)."""
    ids_ = [i for i, nm in enumerate(names) if nm in wanted]
    return np.isin(obj, ids_) if ids_ else np.zeros(obj.shape, bool)


def _save(name, kind, arr):
    Image.fromarray(np.uint8(np.clip(arr, 0, 1) * 255)).save(f"{OUT}/{name}_{kind}.png")
    print(f"  {name}_{kind}: {float((arr > 0.5).mean()):.4f}", flush=True)


def handle_box():
    """Габарит рукоятки перезаряжания (мм) в покое — из карт набора bolt."""
    z = np.load(f"{MAPS}/bolt_maps.npz")
    pos = z["pos"]
    names, obj = ids("bolt", pos.shape[0])
    m = objmask(names, obj, {"Charging_Handle"})
    p = pos[m]
    return p.min(0), p.max(0)


def special(name, names, obj, pos, nrm, edge, edge_w, low):
    """Места по деталям: хват (жир и пятна блеска), задняя кромка крышки, путь рукоятки перезаряжания, пятки сошек,
    низ коробок для ленты."""
    nz = nrm[..., 2]
    # 4 — хват: рукоятка, цевьё, спуск, рукоятка перезаряжания, сошки, ручка переноски, верх приклада (и защёлка
    # крышки, флажок предохранителя — интервью)
    touch = objmask(names, obj, TOUCH).astype(np.float32)
    st = objmask(names, obj, {"Stock"})
    touch = np.where(st, smooth(nz, 0.2, 0.6), touch)
    if touch.max() > 0:
        _save(name, "touch", touch)
    # 3 — задняя кромка крышки: левое, верхнее и правое рёбра и кнопка; вдоль крышки к дулу — на разную длину
    if name == "cover":
        tc = objmask(names, obj, {"Top_Cover"})
        x = pos[..., 0]
        x0 = np.percentile(x[tc], 0.5)
        yc, zc = np.median(pos[..., 1][tc]), np.median(pos[..., 2][tc])
        ang = np.arctan2(pos[..., 2] - zc, pos[..., 1] - yc)
        length = REAR_LEN[0] + (REAR_LEN[1] - REAR_LEN[0]) * (
            0.5 + 0.3 * np.sin(3.0 * ang + 0.7) + 0.2 * np.sin(7.0 * ang + 2.1))
        fall = np.clip(1.0 - (x - x0) / np.maximum(length, 1.0), 0.0, 1.0) ** 1.4
        rim = np.maximum(edge, edge_w)
        rear = np.where(tc, rim * fall, 0.0)
        rear = np.where(objmask(names, obj, {"Cover_Latch"}), rim, rear)
        _save(name, "cover_rear", rear)
    # 5 — вдоль хода рукоятки перезаряжания по правому борту ствольной коробки
    if name == "receiver":
        lo, hi = handle_box()
        rc = objmask(names, obj, {"Receiver"})
        x, y, zz = pos[..., 0], pos[..., 1], pos[..., 2]
        zc, zh = 0.5 * (lo[2] + hi[2]), 0.5 * (hi[2] - lo[2]) + CHARGE_MARGIN
        along = (x > lo[0] - CHARGE_TRAVEL - CHARGE_MARGIN) & (x < hi[0] + CHARGE_MARGIN)
        across = np.clip(1.0 - np.abs(zz - zc) / zh, 0.0, 1.0)
        side = (y < hi[1] + 3.0) & (nrm[..., 1] < 0.2)
        path = np.where(rc & along & side, smooth(across, 0.0, 0.6), 0.0)
        _save(name, "charge_path", path)
    # 2 — пятки сошек, где касаются земли
    if name == "bipod":
        feet = np.zeros(obj.shape, np.float32)
        for nm in ("Bipod_Foot_L", "Bipod_Foot_R"):
            m = objmask(names, obj, {nm})
            if m.any():
                z0 = np.percentile(pos[..., 2][m], 0.5)
                feet = np.where(m, smooth(-pos[..., 2], -(z0 + FOOT_MM), -(z0 + 2.0)), feet)
        _save(name, "feet", feet)
    # 6 — низ коробки для ленты и соседние рёбра и углы
    if name in ("box100", "box200"):
        bd = objmask(names, obj, {"Box100_Body", "Box200_Body"})
        bottom = np.maximum(smooth(-nz, 0.5, 0.85), edge_w * smooth(low, 0.7, 0.92))
        _save(name, "box_bottom", np.where(bd, bottom, 0.0))


def main():
    a = sys.argv[1:]
    stats = "stats" in a
    names = [x for x in a if x != "stats"] or [s for s in T.SETS if os.path.exists(f"{MAPS}/{s}_maps.npz")]
    for nm in names:
        place_set(nm, stats)


if __name__ == "__main__":
    main()
