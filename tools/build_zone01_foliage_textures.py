"""Текстуры растительности для двора и лесополосы зоны 1 (своё, без внешних источников):
кора берёзы, гроздья осенних листьев (берёза, клён), пучки сухой травы — RGBA с альфой.

python tools/build_zone01_foliage_textures.py → assets/zone01/textures/*.png
Поздняя осень: деревья почти голые, на берёзах — редкие жёлтые листья, на клёнах — бурые; трава
выгоревшая, с остатками зелени у земли.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/zone01/textures"
RNG = np.random.default_rng(1957)


def bark_birch() -> None:
    """Кора берёзы 512×1024, бесшовно по горизонтали: белая с серым налётом, чёрные чечевички
    поперёк ствола, тёмные трещины (их больше к низу — его шейдер берёт по высоте UV)."""
    w, h = 512, 1024
    base = np.ones((h, w, 3), np.float32) * np.array([0.86, 0.85, 0.8])
    # серо-зелёный налёт пятнами
    noise = np.asarray(Image.fromarray((RNG.random((h // 32, w // 32)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
    base *= (0.82 + 0.22 * noise)[..., None]
    img = Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(900):
        x = RNG.integers(0, w)
        y = RNG.integers(0, h)
        length = int(RNG.integers(6, 40))
        thick = int(RNG.integers(1, 4))
        shade = int(RNG.integers(15, 60))
        for dx in (0, -w, w):
            d.line([(x + dx, y), (x + dx + length, y + int(RNG.integers(-1, 2)))], fill=(shade, shade, shade - 5), width=thick)
    for _ in range(14):
        x = RNG.integers(0, w)
        y = RNG.integers(0, h)
        rw, rh = int(RNG.integers(25, 70)), int(RNG.integers(5, 12))
        for dx in (0, -w, w):
            d.ellipse([x + dx, y, x + dx + rw, y + rh], fill=(35, 33, 30))
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.save(OUT / "bark_birch.png")


def leaf_cluster(name: str, palette: list[tuple[int, int, int]], count: int, size: tuple[int, int], shape: str) -> None:
    """Гроздь листьев на прозрачном фоне 512×512: веточки и листья нескольких оттенков."""
    w = h = 512
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # веточки от нижнего центра
    for _ in range(7):
        x0, y0 = w / 2 + RNG.normal(0, 20), h - 10
        ang = RNG.uniform(-2.3, -0.8)
        pts = [(x0, y0)]
        for k in range(6):
            ang += RNG.normal(0, 0.18)
            x0 += math.cos(ang) * 55
            y0 += math.sin(ang) * 55
            pts.append((x0, y0))
        d.line(pts, fill=(60, 45, 35, 255), width=4)
    for _ in range(count):
        cx, cy = RNG.uniform(40, w - 40), RNG.uniform(30, h - 60)
        r = RNG.uniform(*size)
        rot = RNG.uniform(0, math.pi)
        col = palette[RNG.integers(0, len(palette))]
        k = RNG.uniform(0.75, 1.1)
        c = tuple(int(min(255, v * k)) for v in col) + (255,)
        pts = []
        for t in np.linspace(0, 2 * math.pi, 18, endpoint=False):
            if shape == "birch":
                rr = r * (0.55 + 0.45 * abs(math.cos(t / 2)) ** 0.6)
                px, py = math.cos(t) * rr * 0.62, math.sin(t) * rr
            else:
                rr = r * (0.7 + 0.3 * abs(math.sin(t * 2.5)))
                px, py = math.cos(t) * rr, math.sin(t) * rr
            pts.append((cx + px * math.cos(rot) - py * math.sin(rot), cy + px * math.sin(rot) + py * math.cos(rot)))
        d.polygon(pts, fill=c)
        d.line([(cx, cy), (cx + math.cos(rot) * r * 0.8, cy + math.sin(rot) * r * 0.8)], fill=(c[0] // 2, c[1] // 2, c[2] // 2, 255), width=1)
    img.save(OUT / name)


def grass_tufts() -> None:
    """Атлас 1024×512: два пучка травы (сухой и с остатками зелени), стебли от низа, альфа."""
    w, h = 1024, 512
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for half, greens in ((0, 0.15), (1, 0.45)):
        ox = half * 512
        for _ in range(150):
            # стебли расходятся веером от редкого основания — без плотной тёмной «подошвы»
            x0 = ox + 256 + RNG.normal(0, 45)
            height = RNG.uniform(180, 480)
            lean = RNG.normal(0, 0.5) + (x0 - ox - 256) / 160
            green = RNG.random() < greens
            col = (int(RNG.uniform(70, 100)), int(RNG.uniform(85, 115)), int(RNG.uniform(35, 55))) if green else \
                (int(RNG.uniform(140, 190)), int(RNG.uniform(120, 160)), int(RNG.uniform(70, 100)))
            pts = []
            for t in np.linspace(0, 1, 8):
                pts.append((x0 + lean * height * t * t, h - height * t))
            for k in range(len(pts) - 1):
                width = max(1, int(4 * (1 - k / len(pts))))
                d.line([pts[k], pts[k + 1]], fill=col + (255,), width=width)
            if RNG.random() < 0.12:
                # метёлка семян
                tx, ty = pts[-1]
                d.ellipse([tx - 5, ty - 14, tx + 5, ty + 2], fill=(150, 125, 90, 255))
    img.save(OUT / "grass_tufts.png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bark_birch()
    leaf_cluster("leaves_birch.png", [(196, 160, 40), (210, 175, 55), (170, 130, 35), (150, 120, 45), (120, 120, 40)], 170, (9, 16), "birch")
    leaf_cluster("leaves_maple.png", [(140, 70, 30), (160, 95, 35), (110, 60, 30), (175, 120, 40), (95, 70, 40)], 90, (16, 28), "maple")
    grass_tufts()
    print("foliage textures:", ", ".join(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
