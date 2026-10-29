"""Клёны и тополя зоны 1: осенние листья (python, numpy + PIL + scipy).

    python -X utf8 tools/zone01_trees/leaf_textures.py

На вид и спелость (g — зелёный, y — жёлтый, o — оранжевый / бурый) — лист 2 × 2 разных листа 2048²: цвет с альфой и нормаль.
  maple    — настоящие осенние листья клёна остролистного (ambientCG LeafSet028, CC0): каждый лист поставлен по своей оси
             «прикрепление черешка → конец средней лопасти» в рамку FRAME (та же, что у сетки листа в species_z1.palmate_leaf,
             режим «alpha»): край листа — альфа скана. Листья разобраны по цвету; на части жёлтых и оранжевых — чёрные пятна
             «смоляной пятнистости» (Rhytisma acerinum), обычной у этого клёна осенью.
  negundo  — листочек сложного листа: сканы LeafSet006 (зеленовато-жёлтые) и LeafSet007 (жёлтые), переформованные по строкам
             под контур листочка (species_z1.NEG_LEAFLET) — как растения «Проспекта» (tools/prospekt_plants/textures.warp_leaf).
  poplar   — лист тополя (контур species.LEAF["poplar"]): зелёный — лист «Проспекта» с осенней желтизной и LeafSet006,
             жёлтый — LeafSet007, бурый — тот же жёлтый, побуревший, с некрозами.
→ _asset_src/zone01_trees/leaves/<вид>_<g|y|o>_leaf_{color,normal}.png (сырьё для PBR-файлов и атласа веточек).
"""
from __future__ import annotations

import colorsys
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/prospekt_plants"))
import textures as PT  # noqa: E402  (переформовка листа под контур, отступ цвета за край)

SRC = ROOT / "_asset_src/zone01_trees"
BIRCH = ROOT / "_asset_src/birch"
OUT = SRC / "leaves"
CELL = 1024
# рамка пальчатого листа в долях длины (прикрепление черешка — 0, конец средней лопасти — y = 1): x ∈ [−XH, XH], y ∈ [Y0, Y1].
# Та же рамка — в species_z1.MAPLE_FRAME (сетка листа и её развёртка).
XH, Y0, Y1 = 0.95, -0.42, 1.12
# контуры листочка ясенелистного и листа тополя — как в species_z1 / species «Проспекта»
NEG_HALF = [(0.0, 0.0), (0.12, 0.04), (0.22, 0.12), (0.28, 0.22), (0.31, 0.31), (0.27, 0.35), (0.31, 0.43), (0.26, 0.48),
            (0.27, 0.56), (0.21, 0.6), (0.2, 0.68), (0.14, 0.74), (0.11, 0.82), (0.05, 0.92), (0.0, 1.0)]
POPLAR_HALF = PT.HALF["poplar"]


# ------------------------------------------------------------------ источники

def unpack(set_name: str, base: Path) -> Path:
    """Набор ambientCG: распаковать архив рядом (один раз). → префикс файлов <набор>_2K-PNG_."""
    d = base / set_name
    zp = d / f"{set_name}_2K-PNG.zip"
    if zp.exists() and not (d / f"{set_name}_2K-PNG_Color.png").exists():
        with zipfile.ZipFile(zp) as z:
            for n in z.namelist():
                if n.endswith((".png", ".txt")) or "license" in n.lower():
                    z.extract(n, d)
    return d / f"{set_name}_2K-PNG_"


def load_set(set_name: str, base: Path) -> tuple:
    p = unpack(set_name, base)
    col = np.asarray(Image.open(str(p) + "Color.png").convert("RGB"), np.float32)
    op = np.asarray(Image.open(str(p) + "Opacity.png").convert("L"), np.float32) / 255.0
    nor = np.asarray(Image.open(str(p) + "NormalGL.png").convert("RGB"), np.float32) / 127.5 - 1.0
    return col, op, nor


def components(op: np.ndarray, min_area: int = 15000) -> list:
    lab, n = ndimage.label(op > 0.5)
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab)):
        m = lab[sl] == i + 1
        if m.sum() >= min_area:
            out.append((sl, m))
    return out


def hue_of(col: np.ndarray, mask: np.ndarray) -> tuple:
    c = col[mask].mean(0) / 255.0
    h, s, v = colorsys.rgb_to_hsv(*c)
    return h * 360.0, s, v


# ------------------------------------------------------------------ клён: настоящий лист по своей оси

def maple_axis(mask: np.ndarray) -> tuple:
    """Ось листа в вырезке: прикрепление черешка J и конец средней лопасти T (строка, столбец).
    Пластинка — маска после «открытия» (черешок тоньше и пропадает); J — где черешок входит в пластинку;
    T — дальняя точка пластинки в узком секторе по направлению J → центр пластинки."""
    r = 7
    blade = ndimage.binary_opening(mask, structure=np.ones((2 * r + 1, 2 * r + 1)))
    lab, n = ndimage.label(blade)
    if n > 1:
        sizes = ndimage.sum(blade, lab, range(1, n + 1))
        blade = lab == (int(np.argmax(sizes)) + 1)
    stalk = mask & ~ndimage.binary_dilation(blade, iterations=2)
    lab, n = ndimage.label(stalk)
    cy, cx = ndimage.center_of_mass(blade)
    if n:
        sizes = ndimage.sum(stalk, lab, range(1, n + 1))
        st = lab == (int(np.argmax(sizes)) + 1)
        near = st & ndimage.binary_dilation(blade, iterations=6)
        if near.sum() < 3:
            near = st
        jy, jx = ndimage.center_of_mass(near)
        # черешок вошёл — прикрепление чуть внутри пластинки, на её краю
        d = np.array([cy - jy, cx - jx])
        d /= np.linalg.norm(d) + 1e-6
        jy, jx = jy + d[0] * 4, jx + d[1] * 4
    else:
        # черешка нет — прикрепление в самой узкой «выемке» у края по наибольшей оси (запасной путь)
        ys, xs = np.nonzero(blade)
        k = int(np.argmax((ys - cy) ** 2 + (xs - cx) ** 2))
        jy, jx = cy + (cy - ys[k]) * 0.6, cx + (cx - xs[k]) * 0.6
    ys, xs = np.nonzero(blade)
    vy, vx = ys - jy, xs - jx
    dist = np.hypot(vy, vx)
    ay, ax = cy - jy, cx - jx
    na = np.hypot(ay, ax) + 1e-6
    cosang = (vy * ay + vx * ax) / (dist * na + 1e-6)
    sel = cosang > np.cos(np.radians(14))
    k = int(np.argmax(np.where(sel, dist, 0)))
    return (jy, jx), (ys[k], xs[k]), blade


def place_maple(col: np.ndarray, op: np.ndarray, nor: np.ndarray, sl, mask: np.ndarray) -> tuple:
    """Лист в ячейку CELL² по рамке FRAME: x вправо, y от прикрепления к концу средней лопасти."""
    (jy, jx), (ty, tx), blade = maple_axis(mask)
    oy, ox = sl[0].start, sl[1].start
    jy, jx, ty, tx = jy + oy, jx + ox, ty + oy, tx + ox
    L = np.hypot(ty - jy, tx - jx)
    a = np.array([(tx - jx) / L, (ty - jy) / L])          # +y листа в пикселях скана (столбец, строка)
    b = np.array([-a[1], a[0]])                            # +x листа
    u = (np.arange(CELL) + 0.5) / CELL
    x = -XH + u * 2 * XH
    y = Y1 - u * (Y1 - Y0)                                  # строка картинки сверху вниз = y сверху вниз
    X, Yy = np.meshgrid(x, y)
    sc = jx + (a[0] * Yy + b[0] * X) * L
    sr = jy + (a[1] * Yy + b[1] * X) * L
    coords = np.array([sr, sc])
    full = np.zeros_like(op)
    full[sl] = mask
    alpha = ndimage.map_coordinates(op * full, coords, order=1, mode="constant", cval=0.0)
    c = np.dstack([ndimage.map_coordinates(col[..., k], coords, order=1, mode="nearest") for k in range(3)])
    n = np.dstack([ndimage.map_coordinates(nor[..., k], coords, order=1, mode="nearest") for k in range(3)])
    # нормаль: в скане x — по столбцам, y — вверх (против строк); в ячейке x — вдоль b, y — вдоль a
    nc, nr = n[..., 0], -n[..., 1]
    nx = nc * b[0] + nr * b[1]
    ny = nc * a[0] + nr * a[1]
    nn = np.dstack([nx, ny, n[..., 2]])
    nn /= np.linalg.norm(nn, axis=-1, keepdims=True) + 1e-6
    return c, alpha, nn


def tar_spots(col: np.ndarray, alpha: np.ndarray, rng: np.random.Generator, count: int) -> np.ndarray:
    """Смоляная пятнистость: чёрные блестящие пятна 1–2 см с жёлтой каймой, по пластинке."""
    ys, xs = np.nonzero(alpha > 0.8)
    if not len(ys):
        return col
    yy, xx = np.mgrid[0:CELL, 0:CELL]
    out = col.copy()
    px_per_leaf = CELL / (2 * XH) / 0.11                   # пикс. на метр при листе 11 см
    for k in range(count):
        i = rng.integers(0, len(ys))
        r = rng.uniform(0.003, 0.0055) * px_per_leaf
        d = np.hypot(yy - ys[i], xx - xs[i]) / r
        wob = 1.0 + 0.18 * np.sin(np.arctan2(yy - ys[i], xx - xs[i]) * rng.integers(3, 6) + rng.uniform(0, 6))
        d = d / wob
        halo = (np.clip(2.1 - d, 0, 1.1) / 1.1)[..., None]
        core = np.clip((1.0 - d) * 3.0, 0, 1)[..., None]
        out = out * (1 - halo * 0.55) + np.array([222, 182, 52]) * halo * 0.55
        out = out * (1 - core * 0.92) + np.array([30, 24, 18]) * core * 0.92
    return out


def maple() -> None:
    col, op, nor = load_set("LeafSet028", SRC)
    leaves = []
    for sl, m in components(op):
        hsv = rgb2hsv(col[sl][m] / 255.0)
        h = hsv[:, 0] * 360.0
        lit = hsv[:, 2] > 0.25
        # доли пластинки: зелёная (> 62°), жёлтая (40–62°), оранжево-красная и бурая (< 40°)
        leaves.append(dict(sl=sl, m=m, val=float(hsv[:, 2].mean()), green=float(((h > 62) & (h < 170) & lit).mean()),
                           yellow=float(((h >= 40) & (h <= 62) & lit).mean()), red=float(((h < 40) | (h > 300)).mean())))
    print("клён: листьев в скане", len(leaves), [(round(L["green"], 2), round(L["yellow"], 2), round(L["red"], 2)) for L in leaves])
    # зелёные — где зелени больше всего (поздней осенью и они с желтизной); оранжевые — где больше красного;
    # жёлтые — самые жёлтые из оставшихся
    g = sorted(leaves, key=lambda L: -L["green"])[:4]
    rest = [L for L in leaves if all(L is not x for x in g)]
    # почти чёрно-бордовые не берутся: издали в кроне они читаются дырой
    o = sorted([L for L in rest if L["val"] > 0.36] or rest, key=lambda L: -L["red"])[:4]
    rest = [L for L in rest if all(L is not x for x in o)]
    y = sorted(rest, key=lambda L: -L["yellow"])[:4]
    rng = np.random.default_rng(23)
    for ripe, pick in (("g", g), ("y", y), ("o", o)):
        while len(pick) < 4:
            pick = pick + pick
        sheet(f"maple_{ripe}", [place_maple(col, op, nor, L["sl"], L["m"]) for L in pick[:4]],
              spots=(ripe == "y"), rng=rng)


# ------------------------------------------------------------------ листочки и тополь: скан по строкам под контур

def leaves_upright(set_name: str, base: Path) -> list:
    """Листья набора, черешок вниз (сканы 006/007/024 лежат черешком влево или вниз — повернуть по оси листа)."""
    col, op, nor = load_set(set_name, base)
    out = []
    for sl, m in components(op, 8000):
        (jy, jx), (ty, tx), _ = maple_axis(m)
        ang = np.degrees(np.arctan2(-(ty - jy), tx - jx))     # угол оси от +x (вверх — плюс)
        rot = 90.0 - ang                                      # повернуть так, чтобы ось смотрела вверх
        c = Image.fromarray(np.clip(col[sl], 0, 255).astype(np.uint8)).rotate(rot, Image.BILINEAR, expand=True)
        a = Image.fromarray((op[sl] * m * 255).astype(np.uint8)).rotate(rot, Image.BILINEAR, expand=True)
        nv = nor[sl]
        # нормаль поворачивается с картинкой: (x, y) на угол rot против часовой
        t = np.radians(rot)
        nx = nv[..., 0] * np.cos(t) - nv[..., 1] * np.sin(t)
        ny = nv[..., 0] * np.sin(t) + nv[..., 1] * np.cos(t)
        nimg = [Image.fromarray(((ch + 1) * 127.5).clip(0, 255).astype(np.uint8)).rotate(rot, Image.BILINEAR, expand=True)
                for ch in (nx, ny, nv[..., 2])]
        nn = np.dstack([np.asarray(i, np.float32) / 127.5 - 1.0 for i in nimg])
        h, s, v = hue_of(col[sl], m)
        out.append(dict(col=np.asarray(c, np.float32), alpha=np.asarray(a, np.float32) / 255.0, nrm=nn, hue=h))
    return out


def rgb2hsv(c: np.ndarray) -> np.ndarray:
    mx, mn = c.max(-1), c.min(-1)
    d = mx - mn + 1e-9
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6.0
    return np.stack([h % 1.0, np.where(mx > 0, (mx - mn) / (mx + 1e-9), 0), mx], -1)


def hsv2rgb(hsv: np.ndarray) -> np.ndarray:
    h, s, v = hsv[..., 0] * 6.0, hsv[..., 1], hsv[..., 2]
    i = np.floor(h).astype(int) % 6
    f = h - np.floor(h)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    sel = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)]
    out = np.zeros(h.shape + (3,))
    for k, (r, g, b) in enumerate(sel):
        m = i == k
        out[m] = np.stack([r[m], g[m], b[m]], -1)
    return out


def browned(col: np.ndarray, alpha: np.ndarray, rng: np.random.Generator, k: float = 1.0) -> np.ndarray:
    """Побуревший лист: тон к оранжево-бурому, темнее; некротические пятна с края."""
    hsv = rgb2hsv(col / 255.0)
    hsv[..., 0] = hsv[..., 0] * (1 - 0.6 * k) + 0.075 * 0.6 * k
    hsv[..., 1] *= 1.0 - 0.15 * k
    hsv[..., 2] *= 1.0 - 0.28 * k
    rgb = hsv2rgb(hsv)
    edge = ndimage.distance_transform_edt(alpha > 0.5)
    n = ndimage.gaussian_filter(rng.random(alpha.shape), 14)
    n = (n - n.min()) / (np.ptp(n) + 1e-6)
    necro = np.clip((0.45 - edge / 60.0) + (n - 0.55) * 1.2, 0, 1)[..., None] * k
    rgb = rgb * (1 - necro * 0.7) + np.array([0.24, 0.15, 0.08]) * necro * 0.7
    return np.clip(rgb * 255.0, 0, 255)


def yellowed(col: np.ndarray, k: float) -> np.ndarray:
    """Зелёный лист поздней осенью: желтеет от края, тускнеет."""
    c = col / 255.0
    tgt = np.array([0.62, 0.58, 0.2])
    lum = c.mean(-1, keepdims=True)
    return np.clip((c * (1 - k) + tgt * lum / tgt.mean() * k) * 255.0, 0, 255)


def warped(srcs: list, half: list, idx: list, rng: np.random.Generator, fn=None) -> list:
    out = []
    for i in idx:
        s = srcs[i % len(srcs)]
        c, a, n = PT.warp_leaf(s, half, (0, 0.0), 1.0, rng)
        if fn is not None:
            c = fn(c, a)
        out.append((c, a, n))
    return out


def compound_and_poplar() -> None:
    rng = np.random.default_rng(41)
    s006 = sorted(leaves_upright("LeafSet006", SRC), key=lambda L: -L["hue"])
    s007 = leaves_upright("LeafSet007", BIRCH)
    print("листочки: LeafSet006", len(s006), [round(L["hue"]) for L in s006], "LeafSet007", len(s007))
    # ясенелистный: зелёные — самые зелёные листья 006, жёлтые — 007, бурые — 007 побуревшие
    sheet("negundo_g", warped(s006, NEG_HALF, [0, 1, 2, 3], rng, lambda c, a: yellowed(c, 0.12)))
    sheet("negundo_y", warped(s007, NEG_HALF, [0, 1, 2, 3], rng))
    sheet("negundo_o", warped(s007, NEG_HALF, [4, 5, 2, 0], rng, lambda c, a: browned(c, a, rng, 0.85)))
    # тополь: зелёный — лист «Проспекта» (два) с желтизной и 006 (два), жёлтый — 007, бурый — побуревший 007
    pc = np.asarray(Image.open(ROOT / "_asset_src/prospekt_plants/leaves/poplar_leaf_color.png").convert("RGBA"), np.float32)
    pn = np.asarray(Image.open(ROOT / "_asset_src/prospekt_plants/leaves/poplar_leaf_normal.png").convert("RGB"), np.float32) / 127.5 - 1.0
    green = []
    for r, c in ((0, 0), (0, 1)):
        ys, xs = slice(CELL * (1 - r), CELL * (2 - r)), slice(CELL * c, CELL * (c + 1))
        green.append((yellowed(pc[ys, xs, :3], 0.22), pc[ys, xs, 3] / 255.0, pn[ys, xs]))
    green += warped(s006, POPLAR_HALF, [1, 3], rng, lambda c, a: yellowed(c, 0.1))
    sheet("poplar_g", green)
    sheet("poplar_y", warped(s007, POPLAR_HALF, [1, 3, 0, 5], rng))
    sheet("poplar_o", warped(s007, POPLAR_HALF, [2, 4, 1, 3], rng, lambda c, a: browned(c, a, rng, 0.75)))


# ------------------------------------------------------------------ лист 2 × 2

def sheet(name: str, cells: list, spots: bool = False, rng: np.random.Generator | None = None) -> None:
    """Ячейки — как развёртка листа: (0,0) — левая нижняя в развёртке = левая нижняя четверть картинки."""
    OUT.mkdir(parents=True, exist_ok=True)
    sc = np.zeros((CELL * 2, CELL * 2, 4), np.float32)
    sn = np.zeros((CELL * 2, CELL * 2, 3), np.float32)
    sn[..., 2] = 1.0
    for cell, (col, a, nrm) in enumerate(cells[:4]):
        if spots and rng is not None and cell == 2:
            col = tar_spots(col, a, rng, int(rng.integers(1, 4)))
        col = PT.bleed(col, a)
        r, c = cell // 2, cell % 2
        ys = slice(CELL * (1 - r), CELL * (2 - r))
        xs = slice(CELL * c, CELL * (c + 1))
        sc[ys, xs, :3] = col
        sc[ys, xs, 3] = a * 255.0
        sn[ys, xs] = nrm
    Image.fromarray(np.clip(sc, 0, 255).astype(np.uint8), "RGBA").save(OUT / f"{name}_leaf_color.png")
    Image.fromarray(((sn * 0.5 + 0.5) * 255).clip(0, 255).astype(np.uint8)).save(OUT / f"{name}_leaf_normal.png")
    print("лист", name)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or "maple" in args:
        maple()
    if not args or "other" in args:
        compound_and_poplar()
