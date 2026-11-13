"""Сумка v02, отделка v03: карты «нейтрон-нейлон со следами службы» по картам геометрии (numpy, без Painter).

  python -X utf8 tools/loot_containers/lc3_bag_maps.py [A|B|AIN]

Вход (после lc3_bag_uv.py pack / bake): _asset_src/loot_containers/maps_v03/lc_bag/{A,B}_{pos,nrm,part,ao}.npy, layout.json.
Основа ткани — фото-скан полотняного плетения ambientCG Fabric041 (CC0): его карта высоты, приведённая к шагу нити
~0,85 мм, с лёгким искажением координат, неровностью пряжи и крупным «плавающим» оттенком; цвет — множителем
(плетение остаётся и в цвете, и в блеске, и в нормали). Металл — царапины и сколы по фото-основе Metal044A (CC0),
резина — Rubber002 (CC0). Остальное (ребристая стропа, микропризма ленты, сетка, нашивка, ярлыки) — рассчитано
в мм-координатах островов. Износ: грязь по AO и кривизне, залоснение низа и углов, выгорание верхних плоскостей,
пушащиеся кромки, засаленные ручки, пыль на чёрном, царапины металла.
"""
import json
import math
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WORK = "E:/Games/RING-godot/_asset_src/loot_containers/maps_v03/lc_bag"
TEX = "E:/Games/RING-godot/_asset_src/textures"
OUT_COPY = "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/textures/finish_v03/lc_bag"
FONT_B = "C:/Windows/Fonts/arialbd.ttf"
FONT = "C:/Windows/Fonts/arial.ttf"
SIZE = 4096
rs = np.random.RandomState(20261113)

THREAD_CELLS = {"t_red": (20, 4090), "t_black": (84, 4090), "t_gray": (148, 4090), "t_white": (212, 4090)}
PRINT_CYR = {}


def lin(c):
    c = np.asarray(c, np.float32) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)


def srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055).astype(np.float32)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0, 1)
    return t * t * (3 - 2 * t)


def noise2(shape, cell, seed, octaves=3):
    """Гладкий шум: сетка случайных значений, растянутая кубически; cell — размер ячейки в пикселях (может быть (cy, cx))."""
    r = np.random.RandomState(seed)
    h, w = shape
    cy, cx = (cell, cell) if np.isscalar(cell) else cell
    out = np.zeros(shape, np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        gh, gw = max(2, int(h / (cy / (2 ** o))) + 2), max(2, int(w / (cx / (2 ** o))) + 2)
        g = r.rand(gh, gw).astype(np.float32)
        out += amp * cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)
        tot += amp
        amp *= 0.5
    return out / tot


def load_gray(path):
    return np.asarray(Image.open(path).convert("L"), np.float32) / 255.0


def load_rgb(path):
    return np.asarray(Image.open(path).convert("RGB"), np.float32) / 255.0


class Ctx:
    pass


def weave_tile(tex_id="Fabric041", pitch_px_src=8.0):
    h = load_gray(f"{TEX}/{tex_id}/height_2k.jpg")
    return (h - h.mean()) / (h.std() + 1e-6)


def tile_sample(tile, shape, pitch_mm, d, src_pitch=8.0, warp=0.35, seed=1, off=(0, 0)):
    """Плетение, повторённое по атласу: шаг нити pitch_mm·d пикселей; тайл заранее уменьшен площадью (без муара),
    координаты слегка искажены гладким шумом (нить не идёт по линейке)."""
    H, W = shape
    s = src_pitch / (pitch_mm * d)                      # пикселей тайла на пиксель атласа
    n = max(16, int(round(tile.shape[0] / s)))
    tile = cv2.resize(tile, (n, n), interpolation=cv2.INTER_AREA if s > 1 else cv2.INTER_CUBIC)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    wy = (noise2(shape, 120, seed, 2) - 0.5) * 2 * warp * pitch_mm * d
    wx = (noise2(shape, 120, seed + 7, 2) - 0.5) * 2 * warp * pitch_mm * d
    mx = ((xx + wx + off[0]) * 1.0) % tile.shape[1]
    my = ((yy + wy + off[1]) * 1.0) % tile.shape[0]
    return cv2.remap(tile, mx.astype(np.float32), my.astype(np.float32), interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def height_to_normal(h, strength):
    """h в относительных единицах, strength — наклон на пиксель; нормаль OpenGL (G вверх по v)."""
    gx = cv2.Sobel(h, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(h, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    nx, ny = -gx * strength, gy * strength
    nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    return np.stack([nx / ln, ny / ln, nz / ln], -1)


def curvature(pos, nrm, mask, d):
    """Выпуклость (+) / вогнутость (−) по картам положения и нормали; сглаженно, у границ островов — нуль."""
    p = cv2.GaussianBlur(pos, (0, 0), 1.6)
    lap = cv2.Laplacian(p, cv2.CV_32F, ksize=1)
    c = -(lap * nrm).sum(-1) / ((1.0 / (d * 1000.0)) ** 2)      # 1/м
    m = cv2.erode(mask.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    return np.where(m, c, 0.0).astype(np.float32)


def load_layout():
    with open(f"{WORK}/layout.json", encoding="utf-8") as fh:
        return json.load(fh)


def island_maps(layout_set, parts):
    """По раскладке: номер острова и локальные мм-координаты (u, v) в каждом пикселе; –1 вне островов."""
    d = layout_set["density"]
    iid = np.full((SIZE, SIZE), -1, np.int32)
    um = np.zeros((SIZE, SIZE), np.float32)
    vm = np.zeros((SIZE, SIZE), np.float32)
    info = []
    pad = 12
    for k, it in enumerate(layout_set["islands"]):
        x0, y0, w, h = it["x"], it["y"], it["w"], it["h"]
        xa, xb, ya, yb = max(0, x0 - pad), min(SIZE, x0 + w + pad), max(0, y0 - pad), min(SIZE, y0 + h + pad)
        reg = iid[ya:yb, xa:xb]
        free = reg < 0
        reg[free] = k
        xs = np.arange(xa, xb, dtype=np.float32)[None, :]
        ys = np.arange(ya, yb, dtype=np.float32)[:, None]
        um[ya:yb, xa:xb] = np.where(free, it["umin"] + (xs - x0) / d, um[ya:yb, xa:xb])
        vm[ya:yb, xa:xb] = np.where(free, it["vmax"] - (ys - y0) / d, vm[ya:yb, xa:xb])
        info.append(it)
    return iid, um, vm, info


def to_u8(x):
    return (np.clip(x, 0, 1) * 255 + 0.5).astype(np.uint8)


def save_png(path, arr):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(arr).save(path, optimize=False)


def dilate_fill(img, mask, iters=12):
    """Заливка вне покрытия значениями с края (запас на мипы и фильтрацию)."""
    out = img.copy()
    m = mask.copy()
    k = np.ones((3, 3), np.uint8)
    for _ in range(iters):
        grown = cv2.dilate(m.astype(np.uint8), k) > 0
        new = grown & ~m
        if not new.any():
            break
        if out.ndim == 3:
            acc = cv2.blur(out * m[..., None], (3, 3)) / np.maximum(cv2.blur(m.astype(np.float32), (3, 3)), 1e-3)[..., None]
        else:
            acc = cv2.blur(out * m, (3, 3)) / np.maximum(cv2.blur(m.astype(np.float32), (3, 3)), 1e-3)
        out = np.where(new[..., None] if out.ndim == 3 else new, acc, out)
        m = grown
    return out


def text_mask(size, items):
    """Маска печати: items — [(текст, (x, y) центр, размер_px, жирный, угол)]; возвращает float [0,1]."""
    im = Image.new("L", (size[1], size[0]), 0)
    dr = ImageDraw.Draw(im)
    for text, (cx, cy), px, bold, ang in items:
        f = ImageFont.truetype(FONT_B if bold else FONT, int(px))
        bb = dr.textbbox((0, 0), text, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        t = Image.new("L", (tw + 8, th + 8), 0)
        ImageDraw.Draw(t).text((4 - bb[0], 4 - bb[1]), text, fill=255, font=f)
        if ang:
            t = t.rotate(ang, expand=True)
        im.paste(255, (int(cx - t.width / 2), int(cy - t.height / 2)), t)
    return np.asarray(im, np.float32) / 255.0


# ======================================================================== маски износа владельца (фото)
import glob
LIB = "E:/Models Blender/Маски_АЛЬФА"
USED_MASKS = {}


def _dir(prefix):
    return next(p for p in sorted(glob.glob(LIB + "/*")) if os.path.isdir(p) and os.path.basename(p).startswith(prefix))


def mask_files(group):
    """Файлы маски по группе: папки владельца 02…18 и CC0-фото (Smear, SurfaceImperfections, Scratches)."""
    if group in ("smear", "imperf", "scratchcc"):
        pre = {"smear": "Smear", "imperf": "SurfaceImperfections", "scratchcc": "Scratches"}[group]
        root = _dir("50_") + "/ambientCG"
        out = []
        for dd in sorted(glob.glob(f"{root}/{pre}0*")):
            if "Substance" in dd:
                continue
            c = glob.glob(dd + "/*_Color.*")
            if c:
                out.append(c[0])
        return out
    folder = {"dirt": "04_", "dust": "03_", "splash": "05_", "wipe": "06_", "fibre": "16_", "rubber": "18_", "palm": "02_Отпечатки_ладоней",
              "scratch": "09_", "weavemark": "17_", "oil": "20_", "edge": "11_", "chip": "10_"}[group]
    return sorted(glob.glob(_dir(folder) + "/*.png"))


_MCACHE = {}


def load_mask(path):
    if path in _MCACHE:
        return _MCACHE[path]
    g = np.asarray(Image.open(path).convert("L"), np.float32) / 255.0
    lo, hi = np.percentile(g, 4), np.percentile(g, 99.6)
    g = np.clip((g - lo) / (hi - lo + 1e-6), 0, 1)
    if g.mean() > 0.5:          # рисунок — меньшинство: чёрное на белом переворачиваем
        g = 1 - g
    _MCACHE[path] = g
    return g


def mask_field(shape, info, d, group, tile_mm, seed, second=None):
    """Рисунок из фото-масок: на каждом острове свой файл, поворот и сдвиг, масштаб tile_mm на плитку; second — вторая маска
    другого масштаба, перемножается (против видимой плитки)."""
    rn = np.random.RandomState(seed)
    files = mask_files(group)
    out = np.zeros(shape, np.float32)
    for it in info:
        f = files[rn.randint(len(files))]
        USED_MASKS.setdefault(group, set()).add(os.path.basename(f))
        m = load_mask(f)
        pad = 12
        x0, y0 = max(0, it["x"] - pad), max(0, it["y"] - pad)
        x1, y1 = min(SIZE, it["x"] + it["w"] + pad), min(SIZE, it["y"] + it["h"] + pad)
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        a = rn.uniform(0, 2 * math.pi)
        ca, sa = math.cos(a), math.sin(a)
        sc = m.shape[0] / (tile_mm * d)
        ox, oy = rn.uniform(0, m.shape[1]), rn.uniform(0, m.shape[0])
        u = ((xx - x0) * ca - (yy - y0) * sa) * sc + ox
        v = ((xx - x0) * sa + (yy - y0) * ca) * sc + oy
        reg = cv2.remap(m, (u % m.shape[1]).astype(np.float32), (v % m.shape[0]).astype(np.float32),
                        interpolation=cv2.INTER_AREA if sc > 1.5 else cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        out[y0:y1, x0:x1] = np.maximum(out[y0:y1, x0:x1], reg)
    if second:
        g2, t2 = second
        out = out * (0.35 + 0.65 * mask_field(shape, info, d, g2, t2, seed + 91))
    return out


# ======================================================================== набор A: ткань корпуса
def compose_A():
    lay = load_layout()["A"]
    d = lay["density"]
    pos = np.load(f"{WORK}/A_pos.npy")
    nrm = np.load(f"{WORK}/A_nrm.npy")
    part = np.rint(np.load(f"{WORK}/A_part.npy")[..., 0]).astype(np.int32)
    ao = np.clip(np.load(f"{WORK}/A_ao.npy"), 0, 1)
    parts = json.load(open(f"{WORK}/A_parts.json", encoding="utf-8"))
    cover = part > 0
    iid, um, vm, info = island_maps(lay, parts)
    nrm = nrm / np.maximum(np.linalg.norm(nrm, axis=-1, keepdims=True), 1e-6)
    cur = curvature(pos, nrm, cover, d)
    shape = (SIZE, SIZE)
    tile = weave_tile("Fabric041")
    wv = tile_sample(tile, shape, 0.85, d, seed=3)
    wv = np.clip(wv, -2.5, 2.5)
    yarn = np.clip(tile_sample(tile, shape, 2.6, d, seed=8), -2, 2) * 0.35        # неровность пряжи — тот же фото-скан в другом масштабе
    big = mask_field(shape, info, d, 'smear', 420, 5)
    mid = mask_field(shape, info, d, 'imperf', 160, 6)
    rub = mask_field(shape, info, d, 'rubber', 180, 7)
    dpat = mask_field(shape, info, d, 'dirt', 150, 9, second=('dust', 60))
    name_of = {int(k): v for k, v in parts.items()}
    is_band = np.zeros(shape, bool)
    for k, v in name_of.items():
        if "лента" in v:
            is_band |= part == k
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    nz = nrm[..., 2]
    # ---- цвет
    red = lin((166, 22, 32))
    col = np.empty(shape + (3,), np.float32)
    col[:] = red
    shade = 1.0 + 0.16 * wv + 0.07 * yarn
    col *= shade[..., None]
    col *= (0.93 + 0.14 * big)[..., None]
    # выгорание верхних плоскостей и светлые вытертые кромки
    fade = smoothstep(0.35, 0.95, nz) * (0.45 + 0.55 * mid)
    col = col * (1 - 0.40 * fade[..., None]) + (col * np.array([1.5, 2.6, 2.3], np.float32) + 0.012) * (0.40 * fade[..., None])
    edge = smoothstep(80.0, 260.0, cur) * (0.3 + 0.7 * mid)
    col = col * (1 - 0.65 * edge[..., None]) + lin((205, 120, 118)) * (0.65 * edge[..., None])
    # залоснение и грязь низа: тёмный, жирный
    low = smoothstep(0.17, 0.045, z) * (0.35 + 0.9 * rub)
    dirt_c = lin((46, 36, 30))
    col = col * (1 - 0.62 * low[..., None]) + dirt_c * (0.62 * low[..., None]) * (0.7 + 0.3 * wv[..., None] * 0.3)
    # грязь в складках и у швов
    conc = smoothstep(0.0, -60.0, cur) * 0.0 + smoothstep(8.0, 55.0, -cur)
    dirt = np.clip((1 - ao) * 1.3 + conc * 0.9, 0, 1) * (0.4 + 1.0 * dpat)
    col = col * (1 - 0.55 * dirt[..., None]) + lin((60, 46, 36)) * (0.55 * dirt[..., None]) * 0.8
    # пятна
    st = smoothstep(0.35, 0.8, mask_field(shape, info, d, 'splash', 260, 21)) * 0.35
    col = col * (1 - st[..., None]) + lin((70, 40, 34)) * st[..., None] * 0.9
    # чёрная лента низа
    blk = lin((30, 30, 32))
    bandc = np.empty_like(col)
    bandc[:] = blk
    rib = 0.5 + 0.5 * np.cos(2 * math.pi * vm / 1.5)
    bandc *= (1.0 + 0.2 * wv + 0.15 * rib - 0.07)[..., None]
    dust = np.clip((1 - ao) * 0.5 + smoothstep(0.1, 0.6, mid) * 0.3 + edge * 0.5 + low * 0.2, 0, 1)
    bandc = bandc * (1 - 0.6 * dust[..., None]) + lin((54, 50, 47)) * (0.6 * dust[..., None])
    col = np.where(is_band[..., None], bandc, col)
    # ---- печать «ПЕРВАЯ ПОМОЩЬ» на клапане (белая краска, потёртая)
    pr = np.zeros(shape, np.float32)
    for k, it in enumerate(info):
        if it["tag"] == "flap" and it["obj"].startswith("МС_клапан"):
            x0, y0, w, h = it["x"], it["y"], it["w"], it["h"]
            # u = x(мм), v = y(мм) корпуса: текст у шарнира, по центру левой половины
            cu, cv = -75.0, 55.0
            px, py = x0 + (cu - it["umin"]) * d, y0 + (it["vmax"] - cv) * d
            tm = text_mask(shape, [("ПЕРВАЯ ПОМОЩЬ", (px, py), 16.5 * d, True, 0)])
            wear = smoothstep(0.3, 0.8, mask_field(shape, info, d, 'scratch', 45, 31)) * 0.6 + smoothstep(0.55, 0.9, mid) * 0.3
            pr = tm * (0.85 - wear * 0.5) * (0.82 + 0.18 * np.clip(0.5 - 0.2 * wv, 0, 1))
    pcol = lin((222, 220, 214))
    col = col * (1 - pr[..., None]) + pcol * pr[..., None] * (0.9 + 0.1 * shade[..., None])
    # ---- яркость чёрного — не выше ~45/255
    capb = lin((45, 45, 46))
    col = np.where(is_band[..., None], np.minimum(col, capb), col)
    # ---- шероховатость
    rough = 0.50 + 0.12 * (-wv) * 0.5 + 0.08 * yarn
    rough = rough + 0.12 * fade + 0.25 * dirt - 0.20 * low - 0.15 * edge * 0 
    rough = np.where(is_band, 0.58 + 0.1 * wv * 0.5 + 0.2 * dust, rough)
    rough = np.where(pr > 0.3, 0.75, rough)
    rough = np.clip(rough, 0.22, 0.92)
    # ---- нормаль: плетение + рёбра ленты + мелкая рябь
    hgt = wv * 0.5 + 0.12 * yarn
    hgt = np.where(is_band, hgt + 0.9 * rib, hgt)
    nm = height_to_normal(hgt.astype(np.float32), 0.45)
    nm = np.where(cover[..., None], nm, np.array([0, 0, 1], np.float32))
    for arr_name, arr in (("col", col),):
        pass
    col = dilate_fill(col, cover)
    rough = dilate_fill(rough, cover)
    nm = dilate_fill(nm, cover)
    aoo = dilate_fill(ao, cover)
    save_png(f"{WORK}/lc_bag_basecolor.png", to_u8(srgb(col)))
    save_png(f"{WORK}/lc_bag_roughness.png", to_u8(rough))
    save_png(f"{WORK}/lc_bag_normal.png", to_u8(nm * 0.5 + 0.5))
    save_png(f"{WORK}/lc_bag_ao.png", to_u8(aoo))
    # ---- подкладка 2K: красная тафта, грязь в складках
    lc = lin((128, 22, 30)) * np.ones(shape + (3,), np.float32)
    lc *= (0.92 + 0.12 * mid + 0.04 * yarn)[..., None]
    lc = lc * (1 - 0.6 * dirt[..., None]) + lin((50, 40, 34)) * (0.6 * dirt[..., None])
    lc = lc * (1 - 0.5 * low[..., None]) + lin((40, 32, 28)) * (0.5 * low[..., None])
    lc = np.where(is_band[..., None], np.minimum(lc * 0 + lin((34, 32, 33)), capb), lc)
    lr = np.clip(0.62 + 0.15 * mid + 0.15 * dirt, 0, 1)
    ln = height_to_normal((0.25 * yarn).astype(np.float32), 0.3)
    r2 = lambda a: cv2.resize(a, (2048, 2048), interpolation=cv2.INTER_AREA)
    save_png(f"{WORK}/lc_bag_in_basecolor.png", to_u8(srgb(r2(dilate_fill(lc, cover)))))
    save_png(f"{WORK}/lc_bag_in_roughness.png", to_u8(r2(lr)))
    save_png(f"{WORK}/lc_bag_in_normal.png", to_u8(r2(ln) * 0.5 + 0.5))
    print("A готов", flush=True)


# ======================================================================== набор B: фурнитура, стропы, ленты
def compose_B():
    lay = load_layout()["B"]
    d = lay["density"]
    pos = np.load(f"{WORK}/B_pos.npy")
    nrm = np.load(f"{WORK}/B_nrm.npy")
    part = np.rint(np.load(f"{WORK}/B_part.npy")[..., 0]).astype(np.int32)
    ao = np.clip(np.load(f"{WORK}/B_ao.npy"), 0, 1)
    parts = {int(k): v for k, v in json.load(open(f"{WORK}/B_parts.json", encoding="utf-8")).items()}
    cover = part > 0
    iid, um, vm, info = island_maps(lay, parts)
    nrm = nrm / np.maximum(np.linalg.norm(nrm, axis=-1, keepdims=True), 1e-6)
    cur = curvature(pos, nrm, cover, d)
    shape = (SIZE, SIZE)
    tile = weave_tile("Fabric041")
    wv = np.clip(tile_sample(tile, shape, 0.7, d, seed=4), -2.5, 2.5)
    mid = mask_field(shape, info, d, "imperf", 90, 8)
    big = mask_field(shape, info, d, "smear", 300, 9)
    fine = np.clip(tile_sample(tile, shape, 0.5, d, seed=10) * 0.3 + 0.5, 0, 1)
    dpat = mask_field(shape, info, d, "dirt", 70, 12, second=("dust", 35))
    fibre = mask_field(shape, info, d, "fibre", 40, 13)
    palm = mask_field(shape, info, d, "palm", 85, 14)
    wipe = mask_field(shape, info, d, "wipe", 120, 15)
    scr = mask_field(shape, info, d, "scratch", 45, 33, second=("scratchcc", 30))
    dirt = np.clip((1 - ao) * 1.2, 0, 1) * (0.4 + 1.0 * dpat)
    edge = smoothstep(60.0, 220.0, cur) * (0.4 + 0.9 * fibre)
    scratch = smoothstep(0.35, 0.8, scr)

    def kind_mask(sub):
        m = np.zeros(shape, bool)
        for k, v in parts.items():
            if sub in v:
                m |= part == k
        return m
    M = {n: kind_mask(n) for n in ("кант", "тесьма", "спираль", "стропы", "металл", "наконечники", "светоотр", "окно", "эмблема", "ярлык",
                                  "сетка", "резинки", "липучки", "перегородки", "рамка", "строчки")}
    isl_of = np.full(shape, -1, np.int32)
    for k, it in enumerate(info):
        isl_of[iid == k] = it["isl"]
    col = np.empty(shape + (3,), np.float32)
    col[:] = lin((60, 60, 60))
    rough = np.full(shape, 0.6, np.float32)
    metal = np.zeros(shape, np.float32)
    alpha = np.ones(shape, np.float32)
    hgt = (wv * 0.4).astype(np.float32)
    ones3 = np.ones(shape + (3,), np.float32)

    def put(m, c, r=None, h=None):
        nonlocal col, rough, hgt
        col = np.where(m[..., None], c, col)
        if r is not None:
            rough = np.where(m, r, rough)
        if h is not None:
            hgt = np.where(m, h, hgt)

    # стропа: красная, ребристая вдоль длины; дуга ручки засалена отпечатками ладоней; пушащиеся кромки — маски ворса
    rib = 0.5 + 0.5 * np.cos(2 * math.pi * vm / 1.6)
    c = lin((148, 20, 34)) * ones3 * (0.86 + 0.2 * rib + 0.1 * wv)[..., None] * (0.92 + 0.16 * big)[..., None]
    arch = smoothstep(235, 270, um) * smoothstep(510, 475, um)
    greasy = np.clip(arch * (0.35 + 0.9 * palm) + smoothstep(60, 0, um) * 0.5 * (0.4 + wipe), 0, 1)
    c = c * (1 - 0.65 * greasy[..., None]) + lin((44, 22, 22)) * (0.65 * greasy[..., None])
    fuzz = np.clip(edge * 0.6 + smoothstep(14.5, 18.0, np.abs(vm)) * fibre * 1.2, 0, 1)
    c = c * (1 - 0.6 * fuzz[..., None]) + lin((205, 112, 114)) * (0.6 * fuzz[..., None])
    c = c * (1 - 0.5 * dirt[..., None]) + lin((58, 44, 36)) * (0.5 * dirt[..., None])
    put(M["стропы"], c, np.clip(0.58 + 0.1 * rib - 0.3 * greasy + 0.2 * fuzz + 0.2 * dirt, 0.2, 0.9), rib * 0.9 + wv * 0.3 + fibre * 0.3)
    # кант
    c = lin((122, 123, 126)) * ones3 * (0.85 + 0.15 * wv)[..., None]
    c = c * (1 - 0.6 * dirt[..., None]) + lin((62, 52, 44)) * (0.6 * dirt[..., None])
    c = c * (1 - 0.4 * edge[..., None]) + lin((170, 168, 166)) * (0.4 * edge[..., None])
    put(M["кант"], c, 0.6 + 0.2 * dirt)
    # чёрные тесьмы
    blk = lin((24, 24, 26))
    for nm_ in ("тесьма", "рамка", "резинки", "липучки"):
        r2 = 0.5 + 0.5 * np.cos(2 * math.pi * um / (1.1 if nm_ == "тесьма" else 0.9))
        c = blk * ones3 * (0.9 + 0.25 * wv + 0.2 * r2)[..., None]
        du = np.clip(dirt * 0.8 + edge * 0.5 + 0.5 * mask_field(shape, info, d, "dust", 50, 17), 0, 1)
        c = c * (1 - 0.6 * du[..., None]) + lin((52, 48, 45)) * (0.6 * du[..., None])
        put(M[nm_], np.minimum(c, lin((46, 46, 47))), 0.62 + 0.2 * du, wv * 0.3 + r2 * 0.6)
    c = blk * ones3 * (0.9 + 0.2 * fine)[..., None]
    c = np.minimum(c * (1 + 0.8 * edge[..., None]) + 0.01 * dirt[..., None], lin((46, 46, 47)))
    put(M["спираль"], c, 0.33 + 0.2 * dirt)
    # металл: никель, царапины — маски Scratches/«Царапины» владельца
    m = M["металл"]
    c = lin((176, 178, 180)) * ones3 * (0.9 + 0.1 * big)[..., None]
    c = c * (1 - 0.4 * scratch[..., None])
    c = c * (1 - 0.7 * dirt[..., None]) + lin((40, 36, 32)) * (0.7 * dirt[..., None])
    c = c * (1 - 0.5 * edge[..., None]) + lin((210, 212, 214)) * (0.5 * edge[..., None])
    put(m, c, np.clip(0.34 + 0.4 * scratch + 0.3 * dirt, 0.2, 0.9), -scratch * 0.8)
    metal = np.where(m, np.clip(1.0 - 0.6 * dirt, 0.4, 1.0), metal)
    # бирюзовая резина
    rb = load_gray(f"{TEX}/Rubber002/height_2k.jpg")
    rb = cv2.resize(rb, (SIZE, SIZE), interpolation=cv2.INTER_AREA)
    c = lin((36, 138, 126)) * ones3 * (0.85 + 0.3 * rb)[..., None]
    c = c * (1 - 0.5 * dirt[..., None]) + lin((50, 46, 40)) * (0.5 * dirt[..., None])
    put(M["наконечники"], c, 0.42 + 0.3 * dirt, rb * 0.3)
    # светоотражающая лента: микропризма, потёртости по маскам грязи/протирания
    p = 0.9
    a = um / p
    b = vm / (p * 0.866)
    hx = np.abs(((a + (np.floor(b) % 2) * 0.5) % 1) - 0.5)
    hy = np.abs((b % 1) - 0.5)
    prism = np.clip(1 - 2 * np.maximum(hx * 1.7 + hy * 0.6, hy * 1.2), 0, 1)
    wear = np.clip(smoothstep(0.3, 0.8, wipe) * 0.55 + dirt * 0.5 + edge * 0.3, 0, 1)
    c = lin((196, 200, 196)) * ones3 * (0.9 + 0.15 * prism)[..., None]
    c = c * (1 - 0.7 * wear[..., None]) + lin((98, 88, 78)) * (0.7 * wear[..., None])
    put(M["светоотр"], c, np.clip(0.28 + 0.55 * wear, 0.2, 0.9), prism * 1.2 * (1 - wear))
    # ярлык
    im_cache = {}
    lab = np.zeros(shape + (3,), np.float32)
    for k, it in enumerate(info):
        if "ярлык" in it["obj"] and it["isl"] == 0:
            x0, y0, w, h = it["x"], it["y"], it["w"], it["h"]
            im = Image.new("RGB", (w, h), (230, 230, 232))
            dr = ImageDraw.Draw(im)
            dr.rectangle([0, 0, w - 1, h - 1], outline=(20, 40, 110), width=max(2, int(1.2 * d)))
            dr.text((w / 2, h * 0.38), "АРГО-МЕД", fill=(20, 40, 110), font=ImageFont.truetype(FONT_B, int(8.5 * d)), anchor="mm")
            dr.text((w / 2, h * 0.76), "укладка УМ-3 · арт. 4417", fill=(70, 70, 78), font=ImageFont.truetype(FONT, int(3.4 * d)), anchor="mm")
            lab[y0:y0 + h, x0:x0 + w] = np.asarray(im, np.float32) / 255.0
    m = M["ярлык"]
    lm = m & (isl_of == 0)
    c = lin(lab * 255) * (0.88 + 0.1 * wv)[..., None]
    c = c * (1 - 0.5 * dirt[..., None]) + lin((70, 58, 48)) * (0.5 * dirt[..., None])
    put(lm, c)
    put(m & ~lm, lin((200, 200, 204)))
    rough = np.where(m, 0.7, rough)
    # нашивка: зелёная, белое кольцо и равноконечный крест; вышивка гладью (диагональные нити)
    pm = M["эмблема"]
    ptop = pm & (isl_of == 0)
    ru = np.hypot(um - 40.0, vm - 40.0)
    cross = ((np.abs(um - 40) < 4.6) & (np.abs(vm - 40) < 21)) | ((np.abs(vm - 40) < 4.6) & (np.abs(um - 40) < 21))
    pat = cross | ((ru > 28.5) & (ru < 33.5))
    thr = 0.5 + 0.5 * np.cos(2 * math.pi * (um + vm) / 1.4 / 1.414)
    pat = cv2.GaussianBlur(pat.astype(np.float32), (0, 0), 0.8)
    c = lin((226, 226, 222)) * (0.88 + 0.16 * thr)[..., None] * pat[..., None] + lin((18, 92, 60)) * (0.85 + 0.22 * thr)[..., None] * (1 - pat[..., None])
    c = c * (1 - 0.5 * dirt[..., None]) + lin((60, 50, 40)) * (0.5 * dirt[..., None])
    put(ptop, c, 0.55 + 0.2 * dirt, np.where(pat, 0.6, 0.0) + thr * 0.4)
    put(pm & ~ptop, lin((215, 215, 212)))
    # окно бирки: карточка (остров 0), плёнка (остров 1); сетка
    wm = M["окно"]
    card, pane = wm & (isl_of == 0), wm & (isl_of == 1)
    lines = (np.abs(((vm / 6.0) % 1) - 0.5) > 0.44) & (um > 8) & (um < 85)
    txt = np.zeros(shape, np.float32)
    for k, it in enumerate(info):
        if "окно" in it["obj"] and it["isl"] == 0:
            x0, y0, w, h = it["x"], it["y"], it["w"], it["h"]
            txt[y0:y0 + h, x0:x0 + w] = text_mask((h, w), [("СПИСОК ВЛОЖЕНИЯ", (w / 2, h * 0.88), 6.2 * d, True, 0), ("дата ____  № ____", (w / 2, h * 0.64), 4.2 * d, False, 0)])
    ct = np.clip(txt + lines * 0.5, 0, 1)
    c = lin((232, 230, 222)) * (1 - ct[..., None]) + lin((40, 40, 60)) * ct[..., None]
    c = c * (1 - 0.5 * dirt[..., None]) + lin((88, 76, 60)) * (0.5 * dirt[..., None])
    put(card, c, 0.7)
    sc2 = np.clip(scratch * 0.8 + 0.5 * dirt + 0.3 * wipe, 0, 1)
    put(pane, lin((225, 232, 238)) * ones3, 0.12 + 0.4 * sc2, -scratch * 0.5)
    alpha = np.where(pane, np.clip(0.12 + 0.5 * sc2, 0, 0.7), alpha)
    sm = M["сетка"]
    q = (np.abs(((um + vm) / 3.0 % 1) - 0.5) > 0.40) | (np.abs(((um - vm) / 3.0 % 1) - 0.5) > 0.40)
    put(sm, lin((26, 26, 28)) * ones3 * (0.9 + 0.2 * fine)[..., None], 0.8)
    alpha = np.where(sm, np.where(q, 1.0, 0.0), alpha)
    # перегородки — красная подкладка
    c = lin((130, 22, 30)) * ones3 * (0.88 + 0.16 * wv + 0.08 * big)[..., None]
    c = c * (1 - 0.5 * dirt[..., None]) + lin((50, 40, 34)) * (0.5 * dirt[..., None])
    put(M["перегородки"], c, 0.7)
    cols = {"t_red": (150, 22, 34), "t_black": (30, 30, 32), "t_gray": (140, 140, 142), "t_white": (205, 205, 200)}
    nm = height_to_normal(hgt.astype(np.float32), 0.5)
    nm = np.where(cover[..., None], nm, np.array([0, 0, 1], np.float32))
    col = dilate_fill(col, cover)
    rough = dilate_fill(rough, cover)
    nm = dilate_fill(nm, cover)
    metal = dilate_fill(metal, cover)
    alpha = dilate_fill(alpha, cover)
    for nm_, (cx, cy) in THREAD_CELLS.items():
        sel = np.zeros(shape, bool)
        sel[cy - 40:SIZE, cx - 20:cx + 60] = True
        col = np.where(sel[..., None], lin(cols[nm_]), col)
        rough = np.where(sel, 0.75, rough)
    save_png(f"{WORK}/lc_bag_trim_basecolor.png", to_u8(srgb(col)))
    save_png(f"{WORK}/lc_bag_trim_roughness.png", to_u8(rough))
    save_png(f"{WORK}/lc_bag_trim_normal.png", to_u8(nm * 0.5 + 0.5))
    save_png(f"{WORK}/lc_bag_trim_metallic.png", to_u8(metal))
    save_png(f"{WORK}/lc_bag_trim_alpha.png", to_u8(alpha))
    save_png(f"{WORK}/lc_bag_trim_ao.png", to_u8(dilate_fill(ao, cover)))
    print("B готов", flush=True)


if __name__ == "__main__":
    which = sys.argv[1:] or ["A", "B"]
    if "A" in which:
        compose_A()
    if "B" in which:
        compose_B()
    with open(f"{WORK}/masks_used.json", "w", encoding="utf-8") as fh:
        json.dump({k: sorted(v) for k, v in USED_MASKS.items()}, fh, ensure_ascii=False, indent=1)
    if "copy" in which:
        import shutil
        os.makedirs(OUT_COPY, exist_ok=True)
        for f in os.listdir(WORK):
            if f.startswith("lc_bag") and f.endswith(".png"):
                shutil.copy(os.path.join(WORK, f), OUT_COPY)
