"""«Частокол», этап 2 (износ): места следов в развёртке по геометрическим картам (tools/pkp/wear_maps.py) — кривизна
в 1/мм по соседним пикселям одной детали. Кромка — выпуклое скругление радиусом меньше ~1 мм (оси, спуск, рычаги
круглые целиком — они не «кромка»), угол и шов — вогнутое скругление или затенение этапа 1. Рисунок следа — умная
маска владельца в Painter (sp_pkp_wear.py), эти карты только умножают её на место.

    python -X utf8 tools/pkp/wear_place.py [набор …] [stats]   → _asset_src/pkp/tex/wear/<набор>_{edge,edge_wide,cavity,tops,deep,open,low}.png

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
    return names, obj, edge, cav


def main():
    a = sys.argv[1:]
    stats = "stats" in a
    names = [x for x in a if x != "stats"] or [s for s in T.SETS if os.path.exists(f"{MAPS}/{s}_maps.npz")]
    for nm in names:
        place_set(nm, stats)


if __name__ == "__main__":
    main()
