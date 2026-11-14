# «Частокол»: маски маркировки в развёртку наборов (обычный Python: numpy, scipy, PIL).
#   python -X utf8 tools/pkp/tex_marks.py [папка geo] [папка масок]
# Вход — <Деталь>_geo.npz из tex_geo_dump.py (тексель знает своё положение на детали в мм). Выход — ч/б PNG размера
# набора (tex_sets.SETS), белое — знак:
#   receiver_fire_paint.png — белая краска в гравировке «ОГОНЬ» у флажка (образцы владельца 02, 04);
#   sight_scale_paint.png   — белая краска в цифрах и делениях планки прицела (образец 05);
#   belt_headstamp.png      — клеймо на донце гильзы: «ЧК» сверху, «27» снизу (выбор владельца 2026-11-14), вдавлено;
#   belt_sealant.png        — красный лак: кольцо на стыке капсюля с гильзой и полоска у дульца;
#   grip_checker.png        — поле насечки на щёчках рукоятки (на образце 04 насечка матовее гладкой рукоятки).
# Гравировка «ЧАСТОКОЛ», «7,62×54», «ЧК 2714» — в самой сетке, без заливки.
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tex_sets as T  # noqa: E402
from dims import RIM_R, font_path  # noqa: E402

GEO = sys.argv[1] if len(sys.argv) > 1 else T.WORK + "/geo"
OUT = sys.argv[2] if len(sys.argv) > 2 else T.WORK + "/masks"

PRIMER_R = 2.80          # радиус капсюля (part_ammo._primer_region)
STAMP_R = (5.55 + RIM_R - 0.25) / 2    # клеймо — на плоском поясе донца между канавкой и фаской закраины
STAMP_CAP = 1.15         # высота знака клейма, мм
SEAL_IN, SEAL_OUT = 0.32, 0.42         # кольцо лака: внутрь капсюля и наружу на гильзу от его края, мм
MOUTH_BAND = 0.7         # полоска лака у дульца, мм


def load(name):
    z = np.load(os.path.join(GEO, name + "_geo.npz"))
    return {k: z[k] for k in z.files}


class Canvas:
    """Маска набора res × res; рисуется только окно развёртки выбранных треугольников (8K целиком — 64 Мпикс)."""

    def __init__(self, res):
        self.res = res
        self.img = np.zeros((res, res), np.uint8)

    def raster(self, geo, sel, value):
        """Тексели треугольников sel получают value(положение текселя, мм) ∈ 0…1 (максимум с прежним)."""
        n = self.res
        uv, pos = geo["uv"][sel].astype(np.float64), geo["pos"][sel].astype(np.float64)
        for i in range(len(uv)):
            t = uv[i] * n
            x0, x1 = int(np.floor(t[:, 0].min())), int(np.ceil(t[:, 0].max())) + 1
            y0, y1 = int(np.floor(t[:, 1].min())), int(np.ceil(t[:, 1].max())) + 1
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, n), min(y1, n)
            if x1 <= x0 or y1 <= y0:
                continue
            px, py = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
            a, b, c = t
            den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(den) < 1e-14:
                continue
            w0 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / den
            w1 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / den
            w2 = 1.0 - w0 - w1
            e = -0.05                       # тексели на кромке треугольника не теряются (сетка мельче пикселя)
            ins = (w0 >= e) & (w1 >= e) & (w2 >= e)
            if not ins.any():
                continue
            p = w0[..., None] * pos[i, 0] + w1[..., None] * pos[i, 1] + w2[..., None] * pos[i, 2]
            v = np.uint8(np.clip(value(p), 0.0, 1.0) * 255)
            blk = self.img[n - y1:n - y0, x0:x1][::-1]           # v развёртки — снизу вверх
            blk[ins] = np.maximum(blk[ins], v[ins])

    def save(self, path):
        Image.fromarray(self.img).save(path)
        print("MASK", path, f"{(self.img > 127).mean():.5f} площади атласа")


def recess(geo, n, region, depth, depth_lo=0.015, depth_soft=0.05, near_mm=0.3):
    """Гравировка в грань с нормалью n (уточняется по граням: средняя по площади): уровень грани h — самый частый по
    площади уровень плоских граней области; знак — тексели ниже h больше чем на depth_lo (мягко на depth_soft), только
    рядом (near_mm) с дном гравировки — скругления кромок детали и пазы глубже резца не попадают. region(центры) → bool."""
    pos = geo["pos"].astype(np.float64)
    c = pos.mean(1)
    a = np.linalg.norm(np.cross(pos[:, 1] - pos[:, 0], pos[:, 2] - pos[:, 0]), axis=1) / 2
    nr = geo["nrm"].astype(np.float64)
    reg = region(c)
    n = np.asarray(n, np.float64) / np.linalg.norm(n)
    for _ in range(3):
        m = reg & (nr @ n > 0.985)
        n = (nr[m] * a[m, None]).sum(0)
        n /= np.linalg.norm(n)
    d = c @ n
    flat = reg & (nr @ n > 0.995)
    hist, edges = np.histogram(d[flat], bins=np.arange(d[flat].min() - 0.01, d[flat].max() + 0.02, 0.01),
                               weights=a[flat])
    k = int(np.argmax(hist))
    h = float(edges[k + 1])
    # дно гравировки — плоское, от 0,07 мм до глубины резца (узкий штрих полной глубины не достигает: стенки скошены)
    # и в окружении грани (в пределах 0,6 мм есть грань уровня h): верх скруглений кромок и пазы этим не проходят
    top = flat & (np.abs(d - h) < 0.02)
    bottom = reg & (nr @ n > 0.995) & (d < h - 0.07) & (d > h - depth - 0.04)
    if bottom.any():
        dt, _ = cKDTree(c[top]).query(c[bottom], distance_upper_bound=0.6)
        bottom[np.nonzero(bottom)[0][~np.isfinite(dt)]] = False
    if not bottom.any():
        raise RuntimeError("нет дна гравировки")
    tree = cKDTree(c[bottom])
    cand = reg & (d < h - depth_lo) & (d > h - depth - 0.06) & (nr @ n > 0.0)
    dist, _ = tree.query(c[cand], distance_upper_bound=near_mm)
    sel = np.nonzero(cand)[0][np.isfinite(dist)]
    print(f"   нормаль {np.round(n, 4)}, уровень грани {h:.3f}, дно {bottom.sum()} тр., знак {len(sel)} тр.")
    # заливка краской — сплошная по всему знаку (стенки и дно): с градиентом по глубине буквы выходили пятнистыми
    return sel, (lambda p: ((h - p @ n) > depth_lo * 0.5).astype(np.float32))


def fire_paint(res):
    g = load("Trigger_Housing")
    cv = Canvas(res)
    sel, val = recess(g, np.array([0.0, 1.0, 0.0]),
                      lambda c: (c[:, 0] > -264) & (c[:, 0] < -240) & (c[:, 2] > -58.5) & (c[:, 2] < -50.5) & (c[:, 1] > 11.9),
                      depth=0.25)
    cv.raster(g, sel, val)
    return cv


def sight_paint(res):
    g = load("Rear_Sight_Leaf")
    nr = g["nrm"].astype(np.float64)
    a = np.linalg.norm(np.cross(g["pos"][:, 1] - g["pos"][:, 0], g["pos"][:, 2] - g["pos"][:, 0]), axis=1) / 2
    # главная плоскость планки — направление нормали с наибольшей площадью; лицевая сторона — та, где гравировка
    q = np.round(nr * 8) / 8
    keys, inv = np.unique(q, axis=0, return_inverse=True)
    area = np.bincount(inv.ravel(), a)
    best = None
    for k in np.argsort(area)[::-1][:2]:
        n = keys[k] / np.linalg.norm(keys[k])
        c = g["pos"].mean(1).astype(np.float64)
        flat = nr @ n > 0.97
        d = c @ n
        h = np.percentile(d[flat], 90)
        cnt = int((flat & (d < h - 0.1) & (d > h - 0.3)).sum())
        if best is None or cnt > best[0]:
            best = (cnt, n)
    n = best[1]
    print("   нормаль лицевой стороны планки", np.round(n, 3), "дно гравировки", best[0], "тр.")
    cv = Canvas(res)
    sel, val = recess(g, n, lambda c: np.ones(len(c), bool), depth=0.18, near_mm=0.3)
    cv.raster(g, sel, val)
    return cv


def _stamp_image(ppm=80):
    """Клеймо в плоскости донца (u вправо глазами стрелка, v вверх), мм → картинка; возвращает функцию u, v → 0…1."""
    size = int(2 * (RIM_R + 0.5) * ppm)
    im = Image.new("L", (size, size), 0)
    dr = ImageDraw.Draw(im)
    font = ImageFont.truetype(font_path(True), 200)
    cap = font.getbbox("Н")
    font = ImageFont.truetype(font_path(True), max(8, int(round(200 * STAMP_CAP * ppm / (cap[3] - cap[1])))))
    cx = cy = size / 2
    for text, v in (("ЧК", STAMP_R), ("27", -STAMP_R)):
        bb = dr.textbbox((0, 0), text, font=font)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        dr.text((cx - w / 2 - bb[0], cy - v * ppm - h / 2 - bb[1]), text, fill=255, font=font)
    arr = np.asarray(im, np.float32) / 255.0

    def f(u, v):
        x = np.clip((u * ppm + cx).astype(int), 0, size - 1)
        y = np.clip((cy - v * ppm).astype(int), 0, size - 1)
        return arr[y, x]
    return f


def ammo(res):
    """Клеймо и лак на всех патронах набора ленты (патрон в ленте, отдельный патрон, стреляная гильза)."""
    stamp = _stamp_image()
    cv_st, cv_lq = Canvas(res), Canvas(res)
    for obj in ("Belt_Round_00", "Cartridge", "Case_Spent"):
        case = load(obj + "_Case_lacquer")
        prim = load(obj + "_Primer")
        pc = case["pos"].reshape(-1, 3).astype(np.float64)
        x_head = float(pc[:, 0].min())
        x_mouth = float(pc[:, 0].max())
        head = pc[pc[:, 0] < x_head + 0.05]
        y0, z0 = float(head[:, 1].mean()), float(head[:, 2].mean())

        def rr(p):
            return np.hypot(p[..., 1] - y0, p[..., 2] - z0)
        cc = case["pos"].mean(1).astype(np.float64)
        cn = case["nrm"].astype(np.float64)
        # клеймо — плоский пояс донца (нормаль назад), вдавлено
        face = (cn[:, 0] < -0.9) & (cc[:, 0] < x_head + 0.1) & (rr(cc) > 5.3) & (rr(cc) < RIM_R - 0.1)
        cv_st.raster(case, np.nonzero(face)[0], lambda p: stamp(-(p[..., 1] - y0), p[..., 2] - z0))
        # лак: кольцо у края капсюля (на гильзе и на капсюле) и полоска у дульца
        ring_c = (cc[:, 0] < x_head + 1.0) & (rr(cc) < PRIMER_R + SEAL_OUT + 0.3)
        cv_lq.raster(case, np.nonzero(ring_c)[0],
                     lambda p: ((rr(p) < PRIMER_R + SEAL_OUT) & (p[..., 0] < x_head + 0.8)).astype(np.float32))
        pcc = prim["pos"].mean(1).astype(np.float64)
        ring_p = rr(pcc) > PRIMER_R - SEAL_IN - 0.3
        cv_lq.raster(prim, np.nonzero(ring_p)[0], lambda p: (rr(p) > PRIMER_R - SEAL_IN).astype(np.float32))
        if obj != "Case_Spent":
            mouth = cc[:, 0] > x_mouth - MOUTH_BAND - 0.3
            cv_lq.raster(case, np.nonzero(mouth)[0], lambda p: (p[..., 0] > x_mouth - MOUTH_BAND).astype(np.float32))
        print(f"   {obj}: донце x {x_head:.2f}, дульце x {x_mouth:.2f}, ось ({y0:.2f}, {z0:.2f})")
    return cv_st, cv_lq


def grip_checker(res):
    """Поле насечки рукоятки (part_grip: рельеф в рамке x −352…−288, z −146…−78) — боковые грани в этой рамке."""
    g = load("Pistol_Grip")
    c = g["pos"].mean(1).astype(np.float64)
    nr = g["nrm"].astype(np.float64)
    sel = np.nonzero((c[:, 0] > -352) & (c[:, 0] < -288) & (c[:, 2] > -146) & (c[:, 2] < -78) & (np.abs(nr[:, 1]) > 0.3))[0]
    cv = Canvas(res)
    cv.raster(g, sel, lambda p: np.ones(p.shape[:-1], np.float32))
    return cv


def main():
    os.makedirs(OUT, exist_ok=True)
    fire_paint(T.SETS["receiver"][0]).save(f"{OUT}/receiver_fire_paint.png")
    sight_paint(T.SETS["sight"][0]).save(f"{OUT}/sight_scale_paint.png")
    st, lq = ammo(T.SETS["belt"][0])
    st.save(f"{OUT}/belt_headstamp.png")
    grip_checker(T.SETS["grip"][0]).save(f"{OUT}/grip_checker.png")
    lq.save(f"{OUT}/belt_sealant.png")


if __name__ == "__main__":
    main()
