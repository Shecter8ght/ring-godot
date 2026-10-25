"""Растения «Проспекта»: текстуры листьев и гладкой коры (python, numpy + PIL + scipy).

    python -X utf8 tools/prospekt_plants/textures.py

1) Листья: сканы ambientCG (CC0) переформованы по строкам под контур листа вида (species.LEAF): LeafSet023
   (сердцевидные цельнокрайные) — липа (с зубчиками по краю) и сирень; LeafSet024 (яйцевидные пильчатые) — берёза,
   тополь, кизильник (край сглажен контуром). На вид — лист 2 × 2 разных листа: цвет с альфой и нормаль.
   Развёртка листа в генераторе (plib.leaf_uv) та же, что здесь: v — от низа лопастей до кончика, x — в тех же долях.
   → _asset_src/prospekt_plants/leaves/<вид>_leaf_{color,normal}.png (сырьё для PBR-файлов и атласа веточек).
2) Гладкая кора 1 × 1 м, бесшовная: тополь (серо-зелёная, ромбические чечевички), сирень и кизильник (серая
   с продольными трещинками). Фактура — шум и трещиноватая кора ambientCG Bark001 внутри трещин.
   → _asset_src/prospekt_plants/textures/<имя>_{albedo,normal,arm}.png (в игру — WebP через godot_assets.py)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import build_birch_textures as bbt  # noqa: E402  (бесшовный шум и рисование с переносом)

SRC = ROOT / "_asset_src/birch"
LEAVES_OUT = ROOT / "_asset_src/prospekt_plants/leaves"
TEX_OUT = ROOT / "_asset_src/prospekt_plants/textures"     # PNG-сырьё; в игру — WebP (godot_assets.py)
CELL = 1024

# контуры листьев — те же, что у формы (species.LEAF): половина, x поперёк, y от черешка к кончику
HALF = {
    "birch": [(0.0, 0.0), (0.2, 0.02), (0.33, 0.12), (0.37, 0.25), (0.33, 0.42), (0.25, 0.6), (0.15, 0.77), (0.06, 0.92), (0.0, 1.0)],
    "linden": [(0.0, 0.0), (0.1, -0.07), (0.27, -0.07), (0.41, 0.06), (0.46, 0.27), (0.42, 0.5), (0.31, 0.7), (0.17, 0.86),
               (0.05, 0.96), (0.0, 1.0)],
    "poplar": [(0.0, 0.0), (0.15, 0.03), (0.27, 0.13), (0.31, 0.3), (0.28, 0.48), (0.21, 0.66), (0.12, 0.82), (0.04, 0.94), (0.0, 1.0)],
    "lilac": [(0.0, 0.0), (0.09, -0.05), (0.24, -0.03), (0.35, 0.1), (0.38, 0.28), (0.33, 0.48), (0.23, 0.67), (0.12, 0.84),
              (0.04, 0.95), (0.0, 1.0)],
    "cotoneaster": [(0.0, 0.0), (0.12, 0.05), (0.23, 0.2), (0.27, 0.4), (0.24, 0.6), (0.16, 0.78), (0.07, 0.92), (0.0, 1.0)],
}
# вид → (набор сканов, номера листьев, зубчики (число на сторону, глубина), доля ширины скана, сдвиг тона, яркость)
PLAN = {
    "birch": ("LeafSet024", [0, 3, 4, 1], (0, 0.0), 1.0),
    "linden": ("LeafSet023", [0, 1, 2, 4], (15, 0.045), 1.0),
    "poplar": ("LeafSet024", [1, 2, 5, 3], (0, 0.0), 1.0),
    "lilac": ("LeafSet023", [1, 3, 4, 5], (0, 0.0), 1.0),
    "cotoneaster": ("LeafSet024", [0, 4, 2, 5], (0, 0.0), 0.86),
}


def ymin(half: list) -> float:
    return min(0.0, min(y for _, y in half))


def width_at(half: list, y: float) -> float:
    """Полуширина контура на высоте y (наибольшее пересечение горизонтали с ломаной половины)."""
    best = 0.0
    for (x0, y0), (x1, y1) in zip(half, half[1:]):
        lo, hi = min(y0, y1), max(y0, y1)
        if lo <= y <= hi:
            x = max(x0, x1) if abs(y1 - y0) < 1e-9 else x0 + (x1 - x0) * (y - y0) / (y1 - y0)
            best = max(best, x)
    return best


def source_leaves(set_name: str) -> list:
    """Листья набора: вырезка RGBA, альфа, нормаль; черешок внизу, кончик вверху."""
    d = SRC / set_name / f"{set_name}_2K-PNG_"
    col = Image.open(str(d) + "Color.png").convert("RGB")
    op = Image.open(str(d) + "Opacity.png").convert("L")
    nor = Image.open(str(d) + "NormalGL.png").convert("RGB")
    a = np.asarray(op) > 128
    lab, n = ndimage.label(a)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab)):
        area = (lab[sl] == i + 1).sum()
        if area < 20000:
            continue
        box = (sl[1].start, sl[0].start, sl[1].stop, sl[0].stop)
        c, o, nm = col.crop(box), op.crop(box), nor.crop(box)
        m = Image.fromarray(((lab[sl] == i + 1) * 255).astype(np.uint8))
        o = Image.fromarray(np.minimum(np.asarray(o), np.asarray(m)))
        nmv = np.asarray(nm).astype(np.float32) / 127.5 - 1.0
        if set_name == "LeafSet023":
            # черешок слева, кончик справа → поворот на 90° против часовой: черешок вниз; нормаль поворачивается с ним
            c, o = c.rotate(90, expand=True), o.rotate(90, expand=True)
            nmv = np.rot90(nmv, 1)
            nmv = np.dstack([-nmv[..., 1], nmv[..., 0], nmv[..., 2]])
        out.append(dict(col=np.asarray(c).astype(np.float32), alpha=np.asarray(o).astype(np.float32) / 255.0, nrm=nmv,
                        cy=(box[1] + box[3]) * 0.5, cx=(box[0] + box[2]) * 0.5))
    # порядок: сверху вниз, слева направо
    out.sort(key=lambda L: (round(L["cy"] / 300), L["cx"]))
    return out


def warp_leaf(src: dict, half: list, teeth: tuple, inner: float, rng: np.random.Generator) -> tuple:
    """Лист в ячейке CELL × CELL: строки скана растянуты под полуширину контура вида."""
    alpha = src["alpha"]
    h, w = alpha.shape
    rows = np.where(alpha.max(axis=1) > 0.5)[0]
    widths = np.array([(np.where(alpha[r] > 0.5)[0].ptp() if (alpha[r] > 0.5).any() else 0) for r in range(h)], np.float32)
    wmax = widths.max()
    tip = rows.min()
    blade = [r for r in range(h) if widths[r] > 0.12 * wmax]
    base = max(blade)
    centers = np.array([(np.where(alpha[r] > 0.5)[0].min() + np.where(alpha[r] > 0.5)[0].max()) * 0.5 if (alpha[r] > 0.5).any() else w * 0.5
                        for r in range(h)], np.float32)
    centers = ndimage.uniform_filter1d(centers, 25)
    half_src = np.maximum(widths * 0.5, 1.0)
    y0 = ymin(half)
    span = 1.0 - y0
    vv = (np.arange(CELL)[::-1] + 0.5) / CELL                 # строка ячейки → v (0 — низ)
    xx = (np.arange(CELL) + 0.5) / CELL - 0.5                  # столбец → x в долях ячейки
    W = np.array([width_at(half, y0 + v * span) / span for v in vv], np.float32)
    # контур — ломаная; сгладить, чтобы у кончика и плеч не было прямых граней
    W = ndimage.gaussian_filter1d(W, CELL * 0.025, mode="nearest")
    n_teeth, depth = teeth
    if n_teeth:
        saw = (vv * n_teeth) % 1.0
        cut = depth * np.where(saw < 0.75, saw / 0.75, (1.0 - saw) / 0.25) * np.clip((vv - 0.06) / 0.12, 0, 1) * np.clip((0.97 - vv) / 0.1, 0, 1)
    else:
        cut = np.zeros_like(vv)
    src_row = base + vv * (tip - base)
    ri = np.clip(src_row.astype(int), 0, h - 1)
    Wc = np.maximum(W * 0.96, 1e-4)[:, None]
    tx = xx[None, :] / Wc                                      # −1..1 внутри листа
    sx = centers[ri][:, None] + tx * half_src[ri][:, None] * inner
    sy = np.repeat(src_row[:, None], CELL, axis=1)
    coords = np.array([sy, sx])
    col = np.dstack([ndimage.map_coordinates(src["col"][..., k], coords, order=1, mode="nearest") for k in range(3)])
    nrm = np.dstack([ndimage.map_coordinates(src["nrm"][..., k], coords, order=1, mode="nearest") for k in range(3)])
    a = ndimage.map_coordinates(alpha, coords, order=1, mode="constant", cval=0.0)
    inside = np.abs(tx) <= (1.0 - cut[:, None])
    edge = np.clip((1.0 - cut[:, None] - np.abs(tx)) * W[:, None] * CELL * 0.6, 0, 1)
    if inner < 1.0:
        # край — по контуру вида (скан внутри шире): гладкий, без зубцов скана
        a = np.where(a > 0.5, edge, 0.0)
    else:
        a = np.minimum(a, edge) * inside
    # всё, что вне контура вида (обрывки черешка в выемке у сердцевидных), — прозрачно
    poly = [(0.5 + x / span, y) for x, y in [(x, (y - y0) / span) for x, y in half]]
    full = poly + [(1.0 - px, py) for px, py in reversed(poly)]
    mimg = Image.new("L", (CELL, CELL), 0)
    ImageDraw.Draw(mimg).polygon([(px * CELL, (1.0 - py) * CELL) for px, py in full], fill=255)
    mimg = mimg.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(2))
    a = a * (np.asarray(mimg, np.float32) / 255.0)
    # нормаль: растяжение по x меняет наклон поперёк — подправить по коэффициенту
    k = (W[:, None] * 0.96 * CELL) / np.maximum(half_src[ri][:, None] * inner, 1.0)
    nrm[..., 0] = nrm[..., 0] / np.maximum(k, 0.3)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True) + 1e-6
    return col, a, nrm


def bleed(col: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Цвет за краем листа — от ближайшего пикселя листа (без светлой каймы фона при фильтрации)."""
    inside = alpha > 0.6
    if not inside.any():
        return col
    _, (iy, ix) = ndimage.distance_transform_edt(~inside, return_indices=True)
    return col[iy, ix]


def leaves() -> None:
    LEAVES_OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(31)
    cache = {}
    for kind, (set_name, idx, teeth, inner) in PLAN.items():
        if set_name not in cache:
            cache[set_name] = source_leaves(set_name)
        src = cache[set_name]
        sheet_c = np.zeros((CELL * 2, CELL * 2, 4), np.float32)
        sheet_n = np.zeros((CELL * 2, CELL * 2, 3), np.float32)
        sheet_n[..., 2] = 1.0
        for cell, i in enumerate(idx):
            col, a, nrm = warp_leaf(src[i % len(src)], HALF[kind], teeth, inner, rng)
            col = bleed(col, a)
            r, c = cell // 2, cell % 2
            # ячейки: (0,0) — левая нижняя в развёртке (v вверх) = левая нижняя четверть картинки
            ys = slice(CELL * (1 - r), CELL * (2 - r))
            xs = slice(CELL * c, CELL * (c + 1))
            sheet_c[ys, xs, :3] = col
            sheet_c[ys, xs, 3] = a * 255.0
            sheet_n[ys, xs] = nrm
        Image.fromarray(np.clip(sheet_c, 0, 255).astype(np.uint8), "RGBA").save(LEAVES_OUT / f"{kind}_leaf_color.png")
        Image.fromarray(((sheet_n * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)).save(LEAVES_OUT / f"{kind}_leaf_normal.png")
        print("лист", kind, set_name, idx)


# ------------------------------------------------------------------ гладкая кора

def save_bark(name: str, col: np.ndarray, height: np.ndarray, rough: np.ndarray, k: float = 3.0) -> None:
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * k
    gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * k
    n = np.dstack([-gx, gy, np.ones_like(gx)])
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    hn = (height - height.min()) / (np.ptp(height) + 1e-6)
    blur = ndimage.gaussian_filter(hn, 5, mode="wrap")
    ao = np.clip(1.0 - 2.0 * np.clip(blur - hn, 0, 1), 0.4, 1.0)
    TEX_OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).save(TEX_OUT / f"{name}_albedo.png")
    Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8)).save(TEX_OUT / f"{name}_normal.png")
    Image.fromarray((np.dstack([ao, np.clip(rough, 0, 1), np.zeros_like(ao)]) * 255).astype(np.uint8)).save(TEX_OUT / f"{name}_arm.png")
    print("кора", name)


def bark001(N: int) -> tuple:
    d = SRC / "Bark001/Bark001_2K-JPG_"
    bc = np.asarray(Image.open(str(d) + "Color.jpg").convert("RGB").resize((N, N)), np.float32) / 255
    bd = np.asarray(Image.open(str(d) + "Displacement.jpg").convert("L").resize((N, N)), np.float32) / 255
    return bc, bd


def poplar_young() -> None:
    """Гладкая кора тополя (верх ствола и ветви): серо-зелёная с оливковыми разводами, ромбические чечевички
    поперёк ствола, редкие тёмные «ромбы» трещин; в трещинах — фактура Bark001."""
    N = 1024
    rng = np.random.default_rng(77)
    base = np.ones((N, N, 3), np.float32) * np.array([0.47, 0.49, 0.43])
    n1 = bbt.tile_noise(N, N, 2.4, 11, aspect=0.6)
    n2 = bbt.tile_noise(N, N, 1.6, 12, aspect=0.5)
    base *= (1.0 + 0.07 * n1)[..., None]
    olive = np.clip(n2 * 0.5 - 0.2, 0, 1)
    base = base * (1 - olive[..., None] * 0.3) + np.array([0.42, 0.45, 0.3]) * olive[..., None] * 0.3
    height = 0.12 * n1 + 0.04 * bbt.tile_noise(N, N, 1.0, 13, aspect=0.3)
    lent = Image.new("L", (N, N), 0)
    dia = Image.new("L", (N, N), 0)
    for _ in range(900):
        x, y = rng.uniform(0, N), rng.uniform(0, N)
        w, h = rng.uniform(4, 11), rng.uniform(1.5, 3.5)
        pts = [(x - w, y), (x, y - h), (x + w, y), (x, y + h)]
        v = int(rng.uniform(150, 255))
        bbt.wrap_draw(lent, lambda d, dx, dy: d.polygon([(px + dx, py + dy) for px, py in pts], fill=v))
    for _ in range(26):
        x, y = rng.uniform(0, N), rng.uniform(0, N)
        w, h = rng.uniform(5, 13), rng.uniform(8, 20)
        pts = [(x - w, y), (x, y - h), (x + w, y), (x, y + h)]
        bbt.wrap_draw(dia, lambda d, dx, dy: d.polygon([(px + dx, py + dy) for px, py in pts], fill=255))
    le = np.asarray(lent.filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255
    dm = ndimage.gaussian_filter(np.asarray(dia, np.float32) / 255, 1.2, mode="wrap")
    dm = bbt.smooth((dm + 0.2 * bbt.tile_noise(N, N, 1.0, 14) - 0.35) / 0.25) * 0.85
    bc, bd = bark001(N)
    dark = bc.mean(-1, keepdims=True) * 0.45 * np.array([0.95, 0.95, 0.9])
    col = base * (1 - le[..., None] * 0.7) + np.array([0.22, 0.2, 0.17]) * le[..., None] * 0.7
    col = col * (1 - dm[..., None]) + dark * dm[..., None]
    height = height - 0.35 * le + dm * (bd - 0.5) * 1.0 - 0.15 * dm
    rough = 0.62 + 0.25 * dm + 0.08 * le
    save_bark("poplar_bark_young", col, height, rough)


def shrub_bark() -> None:
    """Кора сирени и кизильника: серая с буроватым, мелкие продольные трещинки, редкие чечевички."""
    N = 1024
    rng = np.random.default_rng(91)
    base = np.ones((N, N, 3), np.float32) * np.array([0.44, 0.42, 0.39])
    n1 = bbt.tile_noise(N, N, 2.2, 21, aspect=0.25)
    n2 = bbt.tile_noise(N, N, 1.4, 22, aspect=0.15)
    base *= (1.0 + 0.08 * n1)[..., None]
    brown = np.clip(n2 * 0.5 - 0.1, 0, 1)
    base = base * (1 - brown[..., None] * 0.35) + np.array([0.4, 0.33, 0.27]) * brown[..., None] * 0.35
    cracks = Image.new("L", (N, N), 0)
    for _ in range(420):
        x, y = rng.uniform(0, N), rng.uniform(0, N)
        ln = rng.uniform(20, 140)
        wob = rng.uniform(-6, 6)
        th = int(rng.choice([1, 1, 2]))
        bbt.wrap_draw(cracks, lambda d, dx, dy: d.line([(x + dx, y + dy), (x + wob * 0.5 + dx, y + ln * 0.5 + dy), (x + wob + dx, y + ln + dy)],
                                                       fill=int(rng.uniform(140, 255)), width=th))
    lent = Image.new("L", (N, N), 0)
    for _ in range(300):
        x, y = rng.uniform(0, N), rng.uniform(0, N)
        w = rng.uniform(2, 5)
        bbt.wrap_draw(lent, lambda d, dx, dy: d.line([(x - w + dx, y + dy), (x + w + dx, y + dy)], fill=200, width=2))
    cr = np.asarray(cracks.filter(ImageFilter.GaussianBlur(0.7)), np.float32) / 255
    le = np.asarray(lent.filter(ImageFilter.GaussianBlur(0.6)), np.float32) / 255
    col = base * (1 - cr[..., None] * 0.6) + np.array([0.16, 0.14, 0.12]) * cr[..., None] * 0.6
    col = col * (1 - le[..., None] * 0.4) + np.array([0.62, 0.58, 0.5]) * le[..., None] * 0.4
    height = 0.1 * n1 - 0.4 * cr + 0.1 * le
    rough = 0.7 + 0.15 * cr
    save_bark("shrub_bark", col, height, rough)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or "leaves" in args:
        leaves()
    if not args or "bark" in args:
        poplar_young()
        shrub_bark()
