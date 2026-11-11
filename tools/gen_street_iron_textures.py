"""Карты чугуна и пластика улиц «Проспекта» — собственная работа генератором (без внешних картинок):
чугунный люк ГОСТ 3634-61 1968 года (по фото владельца, референсы/prospekt_paving/17), полимерный люк
(фото 18, без марки), решётка дождеприёмника у бордюра. Город брошен два года: чугун ржавый, выпуклое
затёрто подошвами до металла, в пазах грязь и песок, на крышке брызги раствора, в прорезях решётки — песок
и листья; вокруг рамы — неровный воротник раствора (вне его карта прозрачна: под ней видно покрытие).

Использование: python -X utf8 tools/gen_street_iron_textures.py
Выход: assets/textures/street_iron/<имя>_albedo.png (A — воротник), _normal.png (OpenGL), _orm.png
(R — затенение, G — шероховатость, B — металл), 1024 × 1024 на 1 × 1 м. Затем tools/godot.cmd --headless --import.
Надписи — DejaVu Sans Bold (лицензия Bitstream Vera, свободная): _asset_src/fonts.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import gaussian_filter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "textures" / "street_iron"
FONT = ROOT / "_asset_src" / "fonts" / "DejaVuSans-Bold.ttf"
N = 1024                 # пикселей на сторону
M = 1.0                  # метров на сторону
PX = N / M               # пикселей на метр
RELIEF_MM = 7.0          # перепад высоты 0…1, мм

IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="res://assets/textures/street_iron/{name}.png"

[params]

compress/mode=2
compress/high_quality=false
compress/lossy_quality=0.7
compress/uastc_level=0
compress/rdo_quality_loss=0.0
compress/hdr_compression=1
compress/normal_map={normal_map}
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode={rough_mode}
roughness/src_normal="{rough_src}"
process/channel_remap/red=0
process/channel_remap/green=1
process/channel_remap/blue=2
process/channel_remap/alpha=3
process/fix_alpha_border=true
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""

rng = np.random.default_rng(1968)
yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
# метры от центра карты: x вправо, y вниз по картинке
X = (xx + 0.5) / PX - M * 0.5
Y = (yy + 0.5) / PX - M * 0.5
R = np.hypot(X, Y)
A = np.arctan2(Y, X)


def noise(scale_m: float, seed: int, octaves: int = 4) -> np.ndarray:
    """Плавный шум 0…1 с размером пятна scale_m (сумма октав случайной сетки, растянутой билинейно)."""
    g = np.random.default_rng(seed)
    out = np.zeros((N, N), np.float32)
    amp = 1.0
    total = 0.0
    s = scale_m
    for _ in range(octaves):
        cells = max(2, int(M / s) + 2)
        grid = g.random((cells, cells)).astype(np.float32)
        img = Image.fromarray((grid * 255).astype(np.uint8)).resize((N, N), Image.BICUBIC)
        out += amp * (np.asarray(img, np.float32) / 255.0)
        total += amp
        amp *= 0.5
        s *= 0.5
    return out / total


def smooth(a: np.ndarray, e0: float, e1: float) -> np.ndarray:
    t = np.clip((a - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def blur(a: np.ndarray, px: float) -> np.ndarray:
    return gaussian_filter(a.astype(np.float32), px, mode="wrap")


def text_mask(items: list[tuple[str, float, float, float]], size_m: float) -> np.ndarray:
    """Буквы маской: (текст, угол дуги середины, радиус, м, 0 — по дуге; иначе — прямо в центре при радиусе 0)."""
    font = ImageFont.truetype(str(FONT), int(size_m * PX))
    mask = Image.new("L", (N, N), 0)
    for text, ang_deg, radius, _ in items:
        if radius <= 0.0:
            d = ImageDraw.Draw(mask)
            w = d.textlength(text, font=font)
            d.text((N / 2 - w / 2, N / 2 - size_m * PX * 0.62), text, fill=255, font=font)
            continue
        # по дуге: каждая буква отдельно, повёрнута по касательной (низ букв — к центру)
        widths = [ImageDraw.Draw(mask).textlength(ch, font=font) for ch in text]
        total = sum(widths) + 2.0 * (len(text) - 1)
        span = total / (radius * PX)
        a = math.radians(ang_deg) - span / 2.0
        for ch, w in zip(text, widths):
            mid = a + (w / 2.0) / (radius * PX)
            tile = Image.new("L", (int(size_m * PX * 2), int(size_m * PX * 2)), 0)
            td = ImageDraw.Draw(tile)
            td.text((tile.width / 2 - w / 2, tile.height / 2 - size_m * PX * 0.62), ch, fill=255, font=font)
            # буква «стоит» на окружности: верх — наружу
            rot = tile.rotate(-math.degrees(mid) - 90.0, resample=Image.BICUBIC)
            cx = N / 2 + math.cos(mid) * radius * PX
            cy = N / 2 + math.sin(mid) * radius * PX
            mask.paste(255, (int(cx - rot.width / 2), int(cy - rot.height / 2)), rot)
            a += (w + 2.0) / (radius * PX)
    return np.asarray(mask, np.float32) / 255.0


def collar(r_in: float, r_out: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Воротник раствора вокруг рамы: неровный край (маска 0…1) и его высота с трещинами и сколами."""
    edge = r_out + (noise(0.12, seed) - 0.5) * 0.09 + (noise(0.03, seed + 1) - 0.5) * 0.02
    alpha = (R < edge).astype(np.float32)
    cracks = 1.0 - smooth(np.abs(noise(0.08, seed + 2, 3) - 0.5), 0.0, 0.012)
    h = 0.35 + (noise(0.02, seed + 3) - 0.5) * 0.15 - cracks * 0.25
    return alpha, h * (R >= r_in)


def normal_from_height(h: np.ndarray) -> np.ndarray:
    hm = h * RELIEF_MM / 1000.0
    dx = (np.roll(hm, -1, 1) - np.roll(hm, 1, 1)) * PX * 0.5
    dy = (np.roll(hm, -1, 0) - np.roll(hm, 1, 0)) * PX * 0.5
    # OpenGL: зелёный — вверх по картинке; высота растёт вниз по картинке → минус
    n = np.dstack([-dx, dy, np.ones_like(hm)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return ((n * 0.5 + 0.5) * 255.0).astype(np.uint8)


def srgb(c: tuple[int, int, int]) -> np.ndarray:
    return np.array(c, np.float32) / 255.0


def save(name: str, albedo: np.ndarray, alpha: np.ndarray, height: np.ndarray, ao: np.ndarray,
         rough: np.ndarray, metal: np.ndarray) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rgba = np.dstack([np.clip(albedo, 0.0, 1.0), np.clip(alpha, 0.0, 1.0)])
    Image.fromarray((rgba * 255.0).astype(np.uint8), "RGBA").save(OUT / f"{name}_albedo.png")
    Image.fromarray(normal_from_height(height), "RGB").save(OUT / f"{name}_normal.png")
    orm = np.dstack([np.clip(ao, 0, 1), np.clip(rough, 0, 1), np.clip(metal, 0, 1)])
    Image.fromarray((orm * 255.0).astype(np.uint8), "RGB").save(OUT / f"{name}_orm.png")
    for part, normal, rmode, rsrc in (("albedo", 0, 0, ""), ("normal", 1, 1, f"res://assets/textures/street_iron/{name}_normal.png"),
                                      ("orm", 0, 3, f"res://assets/textures/street_iron/{name}_normal.png")):
        imp = OUT / f"{name}_{part}.png.import"
        if not imp.exists():
            imp.write_text(IMPORT.format(name=f"{name}_{part}", normal_map=normal, rough_mode=rmode, rough_src=rsrc),
                           encoding="utf-8", newline="\n")
    print("street_iron:", name)


def rust_colors(raised: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Чугун двух лет без людей: всё в ржавчине, выпуклое затёрто подошвами (темнее, гладже, местами металл)."""
    n1 = noise(0.05, seed)
    n2 = noise(0.015, seed + 1)
    rust = srgb((146, 78, 36))[None, None, :] * (0.75 + 0.5 * n1[..., None])
    dark_rust = srgb((82, 46, 24))[None, None, :] * (0.8 + 0.4 * n2[..., None])
    iron = srgb((58, 50, 45))[None, None, :] * (0.85 + 0.3 * n2[..., None])
    worn = smooth(raised, 0.55, 0.95) * smooth(n1, 0.3, 0.6)
    col = rust * (1.0 - smooth(n2, 0.4, 0.7)[..., None] * 0.5) + dark_rust * smooth(n2, 0.4, 0.7)[..., None] * 0.5
    col = col * (1.0 - worn[..., None]) + iron * worn[..., None]
    rough = 0.85 - worn * 0.35
    metal = worn * 0.45
    return col, rough, metal


def manhole_gost() -> None:
    rc, gap, rf, r_col = 0.31, 0.004, 0.375, 0.47
    cover = R < rc
    frame = (R >= rc + gap) & (R < rf)
    # уши рамы — по оси X
    ears = (np.abs(Y) < 0.045) & (np.abs(X) < rf + 0.035) & (R >= rf - 0.01)
    frame |= ears
    h = np.zeros((N, N), np.float32)
    # рама — ровный пояс с бортиком у крышки
    h[frame] = 0.55 + smooth(R, rc + gap, rc + gap + 0.012)[frame] * 0.0 + 0.1 * (R[frame] < rc + gap + 0.01)
    # крышка: наружный бортик, пояс надписей, сетка квадратных выступов
    lip = (R > rc - 0.022) & cover
    band = (R > 0.235) & (R <= rc - 0.022)
    grid_zone = R <= 0.225
    h[cover] = 0.5
    h[lip] = 0.9
    h[band] = 0.55
    pitch, stud = 0.032, 0.021
    gx = np.abs(((X + pitch * 0.5) % pitch) - pitch * 0.5)
    gy = np.abs(((Y + pitch * 0.5) % pitch) - pitch * 0.5)
    studs = (gx < stud * 0.5) & (gy < stud * 0.5) & grid_zone
    # середина без выступов — под «ГК»
    centre = (np.abs(Y) < 0.034) & (np.abs(X) < 0.075)
    studs &= ~centre
    h[studs] = 0.95
    # скос выступов — мягче
    h = np.where(cover, blur(h, 1.2), h)
    letters = text_mask([("ГОСТ 3634-61", -140.0, 0.262, 0), ("1968", -42.0, 0.262, 0), ("57", 40.0, 0.262, 0)], 0.034)
    letters = np.maximum(letters, text_mask([("ГК", 0.0, 0.0, 0)], 0.05))
    h = np.where(cover & (letters > 0.3), 0.95, h)
    h = np.where(cover, blur(h, 0.7), h)
    # зазор крышка — рама: глубокая щель
    slot = (R >= rc) & (R < rc + gap)
    h[slot] = 0.0
    alpha, ch = collar(rf + 0.005, r_col, 31)
    outside = ~(cover | frame | slot)
    h = np.where(outside, ch, h)
    # износ: мелкие раковины литья
    h += (noise(0.006, 7, 2) - 0.5) * 0.06 * (cover | frame)
    col, rough, metal = rust_colors(h, 11)
    # в пазах грязь и песок
    low = (cover | frame) & (h < 0.6)
    dirt = srgb((96, 80, 60))[None, None, :] * (0.7 + 0.5 * noise(0.02, 12)[..., None])
    dk = smooth(0.62 - h, 0.0, 0.12) * smooth(noise(0.07, 13), 0.35, 0.65) * low
    col = col * (1.0 - dk[..., None] * 0.8) + dirt * dk[..., None] * 0.8
    rough = np.where(low, np.maximum(rough, 0.9 * dk + rough * (1 - dk)), rough)
    # брызги раствора на крышке (как на фото: белёсое пятно снизу слева)
    smear = smooth(noise(0.06, 14), 0.62, 0.7) * smooth(-X - Y, 0.05, 0.25) * cover
    col = col * (1.0 - smear[..., None] * 0.85) + srgb((176, 170, 158))[None, None, :] * smear[..., None] * 0.85
    rough = rough * (1 - smear) + 0.95 * smear
    metal = metal * (1 - smear)
    # воротник раствора: цементный серый, грязный, трещины тёмные
    cem = srgb((128, 124, 116))[None, None, :] * (0.75 + 0.45 * noise(0.04, 15)[..., None])
    cem *= (0.55 + 0.45 * smooth(ch, 0.15, 0.3))[..., None]
    col = np.where(outside[..., None], cem, col)
    rough = np.where(outside, 0.95, rough)
    metal = np.where(outside, 0.0, metal)
    ao = 1.0 - smooth(0.6 - blur(h, 3.0), 0.0, 0.5) * 0.7
    ao = np.where(slot, 0.05, ao)
    col = np.where(slot[..., None], srgb((10, 8, 7))[None, None, :], col)
    save("manhole_gost", col, alpha, h, ao, rough, metal)


def manhole_polymer() -> None:
    rc, gap, rf, r_col = 0.30, 0.004, 0.36, 0.44
    cover = R < rc
    frame = ((R >= rc + gap) & (R < rf)) | ((np.abs(Y) < 0.05) & (np.abs(X) < rf + 0.03) & (R >= rf - 0.01))
    h = np.zeros((N, N), np.float32)
    h[frame] = 0.6
    h[cover] = 0.45
    # кольца брусков «под брусчатку»: радиальные пояса, в каждом — бруски по дуге
    rings = [(0.07, 0.115, 10), (0.125, 0.17, 16), (0.18, 0.225, 22), (0.235, 0.28, 28)]
    blocks = np.zeros((N, N), bool)
    for r0, r1, count in rings:
        zone = (R > r0) & (R < r1)
        seg = ((A + math.pi) / (2 * math.pi) * count) % 1.0
        blocks |= zone & (seg > 0.08) & (seg < 0.92)
    h[blocks & cover] = 0.85
    centre = R < 0.055
    h[centre] = 0.8
    h = np.where(cover, blur(h, 1.5), h)
    h[(R >= rc) & (R < rc + gap)] = 0.0
    alpha, ch = collar(rf + 0.005, r_col, 41)
    outside = ~(cover | frame | ((R >= rc) & (R < rc + gap)))
    h = np.where(outside, ch, h)
    h += (noise(0.004, 8, 2) - 0.5) * 0.03 * (cover | frame)
    plastic = srgb((22, 22, 24))[None, None, :] * (0.85 + 0.3 * noise(0.03, 42)[..., None])
    # пыль и песок в пазах, затёртые светлые потёртости на брусках
    dust = smooth(0.7 - h, 0.0, 0.2) * (cover | frame) * smooth(noise(0.05, 43), 0.3, 0.6)
    scuff = smooth(h, 0.75, 0.9) * smooth(noise(0.01, 44), 0.6, 0.75)
    col = plastic * (1 - dust[..., None]) + srgb((110, 98, 80))[None, None, :] * dust[..., None]
    col = col + scuff[..., None] * 0.06
    rough = 0.6 + dust * 0.35
    cem = srgb((120, 117, 110))[None, None, :] * (0.7 + 0.5 * noise(0.04, 45)[..., None])
    col = np.where(outside[..., None], cem, col)
    rough = np.where(outside, 0.95, rough)
    ao = 1.0 - smooth(0.6 - blur(h, 3.0), 0.0, 0.5) * 0.6
    save("manhole_polymer", col, alpha, h, ao, rough, np.zeros((N, N), np.float32))


def drain_grate() -> None:
    # решётка 0,8 × 0,45 м (длинная сторона — вдоль бордюра, ось X), рама 0,9 × 0,55, прорези вдоль X
    gw, gh, fw, fh = 0.40, 0.225, 0.45, 0.275
    ax, ay = np.abs(X), np.abs(Y)
    grate = (ax < gw) & (ay < gh)
    frame = (ax < fw) & (ay < fh) & ~grate
    h = np.zeros((N, N), np.float32)
    h[frame] = 0.6
    slot_pitch, slot_w = 0.05, 0.03
    sy = np.abs(((Y + slot_pitch * 0.5) % slot_pitch) - slot_pitch * 0.5)
    ribs = (np.abs(X) < 0.015) | (np.abs(np.abs(X) - 0.2) < 0.012)
    slots = grate & (sy < slot_w * 0.5) & ~ribs & (ax < gw - 0.02) & (ay < gh - 0.015)
    h[grate] = 0.65
    h[slots] = 0.0
    h = np.where(grate | frame, blur(h, 0.8), h)
    # в прорезях — песок и листья (забились за два года), в части — пусто и темно
    fill = slots & (noise(0.06, 51) > 0.5)
    h = np.where(fill, 0.25 + noise(0.01, 52) * 0.15, h)
    alpha, ch = collar(0.0, 0.0, 53)
    edge = np.maximum(ax - fw, ay - fh)
    rim = edge + (noise(0.1, 54) - 0.5) * 0.06 + (noise(0.025, 55) - 0.5) * 0.015
    alpha = (rim < 0.07).astype(np.float32)
    outside = ~(grate | frame)
    h = np.where(outside, 0.35 + (noise(0.02, 56) - 0.5) * 0.12, h)
    col, rough, metal = rust_colors(h, 57)
    leaves = srgb((92, 70, 40))[None, None, :] * (0.6 + 0.6 * noise(0.012, 58)[..., None])
    col = np.where(fill[..., None], leaves, col)
    col = np.where((slots & ~fill)[..., None], srgb((8, 7, 6))[None, None, :], col)
    rough = np.where(slots, 1.0, rough)
    metal = np.where(slots, 0.0, metal)
    cem = srgb((70, 68, 64))[None, None, :] * (0.75 + 0.45 * noise(0.03, 59)[..., None])
    col = np.where(outside[..., None], cem, col)
    rough = np.where(outside, 0.95, rough)
    metal = np.where(outside, 0.0, metal)
    ao = 1.0 - smooth(0.6 - blur(h, 2.0), 0.0, 0.6) * 0.8
    ao = np.where(slots & ~fill, 0.03, ao)
    save("drain_grate", col, alpha, h, ao, rough, metal)


if __name__ == "__main__":
    manhole_gost()
    manhole_polymer()
    drain_grate()
