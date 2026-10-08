"""Текстуры берёзы (Betula pendula) для зоны 1 — по фото-референсам владельца 2026-10-08.

python tools/build_birch_textures.py

1) Листья: скан ambientCG LeafSet024 (CC0, зубчатые яйцевидные листья) переформован по строкам в
   берёзовый лист — широкий клиновидный низ у черешка (~25 % длины), прямые стороны и вытянутый
   острый кончик. → _asset_src/birch/birch_leaves_{color,opacity,normal}.png + leaves_birch.json
   (сырьё для атласа веточек, tools/build_birch.py).
2) Береста 1 × 2 м (бесшовная): тёплая белая с серыми разводами, горизонтальные чечевички,
   полосы отслоившейся бересты (под ней рыжий луб, светлый завиток с тенью), чёрные пятна и
   «ромбы» — трещиноватая кора ambientCG Bark001 внутри. → assets/zone01/textures/birch_bark_{albedo,normal,arm}.png
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_asset_src/birch"
OUT = ROOT / "assets/zone01/textures"
RNG = np.random.default_rng(2408)

IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="res://assets/zone01/textures/{name}"

[params]

compress/mode=2
compress/high_quality=true
compress/normal_map={nm}
mipmaps/generate=true
process/fix_alpha_border=true
process/size_limit=0
detect_3d/compress_to=0
"""


def smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ листья

def birch_profile(t: np.ndarray) -> np.ndarray:
    """Полуширина берёзового листа (доля от максимума) по длине t: 0 — черешок, 1 — кончик."""
    rise = 0.12 + 0.88 * smooth((t - 0.02) / 0.27) ** 0.7
    fall = np.where(t < 0.24, 1.0, (1.0 - (t - 0.24) / 0.76) ** 1.12)
    tip = 1.0 - 0.35 * smooth((t - 0.8) / 0.2)
    return np.where(t < 0.03, 0.0, rise * fall * tip)


def leaves() -> None:
    d = "LeafSet024/LeafSet024_2K-PNG_"
    col = np.asarray(Image.open(SRC / (d + "Color.png")).convert("RGB")).astype(np.float32)
    op = np.asarray(Image.open(SRC / (d + "Opacity.png")).convert("L")).astype(np.float32)
    nor = np.asarray(Image.open(SRC / (d + "NormalGL.png")).convert("RGB")).astype(np.float32)
    info = json.loads((SRC / "leaves.json").read_text(encoding="utf-8"))["LeafSet024"]
    oc, oo, on = np.zeros_like(col), np.zeros_like(op), np.zeros_like(nor)
    on[...] = (128, 128, 255)
    out = []
    for lf in info:
        x0, y0, x1, y1 = lf["box"]
        bx, by = lf["base"]
        tx, ty = lf["tip"]
        if by < ty:
            # в наборе черешок всегда снизу
            bx, by, tx, ty = tx, ty, bx, by
        L = by - ty
        if L <= 0:
            continue
        cx = (bx + tx) * 0.5
        mask = op[y0:y1, x0:x1] > 128
        # полуширина исходника по строкам
        rows = np.arange(y0, y1)
        t = np.clip((by - rows) / L, 0, 1)
        src_w = np.array([max(1.0, max(abs(np.where(mask[i])[0] + x0 - cx).max(), 1.0)) if mask[i].any() else 1.0 for i in range(len(rows))])
        wmax = src_w[(t > 0.3) & (t < 0.7)].max() * 1.05
        tgt_w = birch_profile(t) * wmax
        for i, y in enumerate(rows):
            if t[i] < 0.03 or tgt_w[i] < 0.5:
                # черешок — как есть, выше кончика — пусто
                if t[i] < 0.03:
                    oc[y, x0:x1], oo[y, x0:x1], on[y, x0:x1] = col[y, x0:x1], op[y, x0:x1], nor[y, x0:x1]
                continue
            # растяжение не больше ×2.5 — иначе край размазывается полосами
            k = max(src_w[i] / tgt_w[i], 0.4)
            xs = np.arange(x0, x1)
            sx = cx + (xs - cx) * k
            ok = (sx >= x0) & (sx < x1 - 1)
            sxi = np.clip(sx.astype(int), x0, x1 - 2)
            f = (sx - sxi)[:, None]
            for dst, srcimg in ((oc, col), (on, nor)):
                v = srcimg[y, sxi] * (1 - f) + srcimg[y, sxi + 1] * f
                dst[y, xs[ok]] = v[ok]
            v = op[y, sxi] * (1 - f[:, 0]) + op[y, sxi + 1] * f[:, 0]
            oo[y, xs[ok]] = v[ok]
        out.append(dict(box=[x0, y0, x1, y1], base=[bx, by], tip=[tx, ty], size=2048))
    Image.fromarray(oc.astype(np.uint8)).save(SRC / "birch_leaves_color.png")
    Image.fromarray(oo.astype(np.uint8)).save(SRC / "birch_leaves_opacity.png")
    Image.fromarray(on.astype(np.uint8)).save(SRC / "birch_leaves_normal.png")
    (SRC / "leaves_birch.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("листья берёзы:", len(out))


# ------------------------------------------------------------------ береста

def tile_noise(h: int, w: int, beta: float, seed: int, aspect: float = 1.0) -> np.ndarray:
    """Бесшовный шум 1/f^β; aspect > 1 — пятна вытянуты по горизонтали."""
    rng = np.random.default_rng(seed)
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :] * aspect
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1
    spec = (rng.normal(size=(h, w)) + 1j * rng.normal(size=(h, w))) / f ** (beta / 2)
    spec[0, 0] = 0
    n = np.real(np.fft.ifft2(spec))
    return (n - n.mean()) / (n.std() + 1e-6)


def wrap_draw(img: Image.Image, fn) -> None:
    """Рисовать с переносом через края (бесшовность)."""
    w, h = img.size
    d = ImageDraw.Draw(img)
    for dx in (-w, 0, w):
        for dy in (-h, 0, h):
            fn(d, dx, dy)


def bark() -> None:
    W, H = 1024, 2048
    base = np.ones((H, W, 3), np.float32) * np.array([0.87, 0.86, 0.82])
    n1 = tile_noise(H, W, 2.6, 1, aspect=2.5)
    n2 = tile_noise(H, W, 1.8, 2, aspect=4.0)
    base *= (1.0 + 0.05 * n1)[..., None]
    grey = np.clip(n2 * 0.5 - 0.3, 0, 1)
    base = base * (1 - grey[..., None] * 0.35) + np.array([0.62, 0.63, 0.6]) * grey[..., None] * 0.35
    pink = np.clip(tile_noise(H, W, 2.4, 3, aspect=2.0) * 0.6 - 0.5, 0, 1)
    base = base * (1 - pink[..., None] * 0.25) + np.array([0.9, 0.8, 0.74]) * pink[..., None] * 0.25
    height = 0.15 * n2 + 0.08 * tile_noise(H, W, 1.2, 4, aspect=6.0)
    # тонкие горизонтальные слои бересты
    layers = np.sin(np.arange(H)[:, None] * 2 * math.pi / H * 160 + 3 * n1) * 0.5 + 0.5
    base *= (0.97 + 0.03 * layers)[..., None]
    height += 0.05 * layers

    # слои-маски: рисуем в PIL с переносом
    def layer() -> Image.Image:
        return Image.new("L", (W, H), 0)

    lent, peel_in, peel_edge, black = layer(), layer(), layer(), layer()
    for _ in range(2200):
        x, y = RNG.uniform(0, W), RNG.uniform(0, H)
        ln = RNG.choice([RNG.uniform(4, 14), RNG.uniform(14, 45)], p=[0.75, 0.25])
        th = RNG.uniform(1.0, 2.6)
        v = int(RNG.uniform(140, 255))
        wrap_draw(lent, lambda d, dx, dy: d.line([(x + dx, y + dy), (x + ln + dx, y + dy + RNG.uniform(-1, 1))], fill=v, width=int(round(th))))
    for _ in range(16):
        x, y = RNG.uniform(0, W), RNG.uniform(0, H)
        w, h = RNG.uniform(40, 220), RNG.uniform(4, 14)
        pts = [(x + w * math.cos(a) * (0.8 + 0.4 * RNG.random()), y + h * math.sin(a) * (0.6 + 0.6 * RNG.random()))
               for a in np.linspace(0, 2 * math.pi, 14, endpoint=False)]
        wrap_draw(peel_in, lambda d, dx, dy: d.polygon([(px + dx, py + dy) for px, py in pts], fill=255))
        top = [(px, py) for px, py in pts if py < y]
        top.sort()
        wrap_draw(peel_edge, lambda d, dx, dy: d.line([(px + dx, py + dy) for px, py in top], fill=255, width=3))
    # чёрные пятна — горизонтальные, и «ромбы» (как под отпавшими сучьями)
    for _ in range(26):
        x, y = RNG.uniform(0, W), RNG.uniform(0, H)
        w, h = RNG.uniform(30, 200), RNG.uniform(5, 26)
        pts = [(x + w * math.cos(a) * (0.6 + 0.6 * RNG.random()), y + h * math.sin(a) * (0.5 + 0.7 * RNG.random()))
               for a in np.linspace(0, 2 * math.pi, 18, endpoint=False)]
        wrap_draw(black, lambda d, dx, dy: d.polygon([(px + dx, py + dy) for px, py in pts], fill=255))
    for _ in range(5):
        x, y = RNG.uniform(0, W), RNG.uniform(0, H)
        s = RNG.uniform(40, 90)
        pts = [(x - s, y - s * 0.15), (x, y + s * 0.55), (x + s, y - s * 0.15), (x + s * 0.7, y - s * 0.05), (x, y + s * 0.3), (x - s * 0.7, y - s * 0.05)]
        wrap_draw(black, lambda d, dx, dy: d.polygon([(px + dx, py + dy) for px, py in pts], fill=255))
    edge_noise = tile_noise(H, W, 1.0, 9)
    # края пятен рваные и вытянуты поперёк ствола (размытие сильнее по горизонтали)
    bl = black.resize((W // 4, H)).filter(ImageFilter.GaussianBlur(1.5)).resize((W, H))
    blk = np.asarray(bl, np.float32) / 255
    blk = smooth((blk + 0.22 * tile_noise(H, W, 1.0, 9, aspect=4.0) - 0.4) / 0.2)
    le = np.asarray(lent, np.float32) / 255
    pin = np.asarray(peel_in.filter(ImageFilter.GaussianBlur(1.5)), np.float32) / 255
    ped = np.asarray(peel_edge.filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255

    # трещиноватая кора в чёрных пятнах — Bark001 (тайлится сама)
    d = SRC / "Bark001/Bark001_2K-JPG_"
    bc = np.asarray(Image.open(str(d) + "Color.jpg").convert("RGB").resize((W, W)), np.float32) / 255
    bd = np.asarray(Image.open(str(d) + "Displacement.jpg").convert("L").resize((W, W)), np.float32) / 255
    bc = np.vstack([bc, bc])
    bd = np.vstack([bd, bd])
    lum = bc.mean(-1, keepdims=True)
    dark = (lum * 0.35 + 0.06) * np.array([0.92, 0.92, 0.9])

    col = base
    col = col * (1 - pin[..., None] * 0.8) + (np.array([0.78, 0.66, 0.57]) * (0.9 + 0.1 * n1[..., None])) * pin[..., None] * 0.8
    col = col * (1 - le[..., None] * 0.85) + np.array([0.24, 0.2, 0.19]) * le[..., None] * 0.85
    col = col * (1 - ped[..., None] * 0.6) + np.array([0.97, 0.96, 0.93]) * ped[..., None] * 0.6
    col = col * (1 - blk[..., None]) + dark * blk[..., None]
    height = height - 0.6 * le - 0.15 * pin + 0.35 * ped + blk * (bd - 0.5) * 1.2 - blk * 0.2
    rough = 0.55 + 0.1 * n1 * 0.2 + 0.35 * blk + 0.1 * le
    # нормаль по бесшовному градиенту
    k = 3.5
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * k
    gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * k
    n = np.dstack([-gx, gy, np.ones_like(gx)])
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    hn = (height - height.min()) / (np.ptp(height) + 1e-6)
    blur = np.asarray(Image.fromarray((hn * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32) / 255
    ao = np.clip(1.0 - 1.8 * np.clip(blur - hn, 0, 1), 0.45, 1.0)
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).save(OUT / "birch_bark_albedo.png")
    Image.fromarray(((n * 0.5 + 0.5) * 255).astype(np.uint8)).save(OUT / "birch_bark_normal.png")
    arm = np.dstack([ao, np.clip(rough, 0, 1), np.zeros_like(ao)])
    Image.fromarray((arm * 255).astype(np.uint8)).save(OUT / "birch_bark_arm.png")
    for name, nm in (("birch_bark_albedo.png", 0), ("birch_bark_normal.png", 1), ("birch_bark_arm.png", 0)):
        imp = OUT / (name + ".import")
        imp.write_text(IMPORT.format(name=name, nm=nm), encoding="utf-8")
    print("береста готова")


if __name__ == "__main__":
    leaves()
    bark()
