"""Купе Ильи: свои картинки для отделки — карбон (саржа 2×2), подложки номеров, этикетка аккумулятора.

    python -X utf8 tools/coupe_ilya/gen_textures.py [папка]

Всё синтетическое (нарисовано кодом), без чужих логотипов: марка аккумулятора вымышленная.
По умолчанию — E:\\Models Blender\\VEHICLES\\Купе Ильи\\textures.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"E:\Models Blender\VEHICLES\Купе Ильи\textures")
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(1708)


def carbon_twill(size: int = 1024, tows: int = 8) -> None:
    """Саржа 2×2: жгуты по двум направлениям, перекрытие сдвигается на один жгут в ряду.

    Цвет (sRGB) — тёмный с волокнистым отливом вдоль жгута, высота (Non-Color, 0,5 — ноль) —
    горб жгута поперёк и спуск у переплетения. Плитка бесшовная.
    """
    t = size // tows
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    ci, cj = (y // t).astype(int), (x // t).astype(int)
    fy, fx = (y % t) / t, (x % t) / t
    warp_on_top = ((ci + cj) // 2) % 2 == 0            # 2×2: две клетки сверху основа, две — уток, со сдвигом
    # горб жгута: поперёк — косинус, вдоль — спад к переплетению
    across = np.where(warp_on_top, np.cos((fx - 0.5) * math.pi), np.cos((fy - 0.5) * math.pi))
    along = np.where(warp_on_top, np.sin(fy * math.pi) ** 0.35, np.sin(fx * math.pi) ** 0.35)
    height = 0.5 + 0.22 * across * along
    # волокна: мелкий шум, вытянутый вдоль жгута
    n = rng.random((size, size)).astype(np.float32)
    img = Image.fromarray((n * 255).astype(np.uint8))
    fib_h = np.asarray(img.filter(ImageFilter.BoxBlur(0)).resize((size // 8, size), Image.BILINEAR).resize((size, size), Image.BILINEAR), np.float32) / 255
    fib_v = np.asarray(img.resize((size, size // 8), Image.BILINEAR).resize((size, size), Image.BILINEAR), np.float32) / 255
    fibers = np.where(warp_on_top, fib_h, fib_v)
    # отлив: жгуты одного направления светлее (анизотропный блик лака)
    sheen = np.where(warp_on_top, 1.0, 0.72) * (0.55 + 0.45 * across * along)
    lum = 0.030 + 0.050 * sheen + 0.012 * (fibers - 0.5)
    rgb = np.stack([lum * 0.98, lum * 1.0, lum * 1.05], -1)
    srgb = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(np.clip(rgb, 0, 1), 1 / 2.4) - 0.055)
    Image.fromarray((np.clip(srgb, 0, 1) * 255).astype(np.uint8)).save(OUT / "carbon_twill_color.png")
    h = np.clip(height + 0.03 * (fibers - 0.5), 0, 1)
    Image.fromarray((h * 65535).astype(np.uint16)).save(OUT / "carbon_twill_height.png")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for name in (("arialbd.ttf" if bold else "arial.ttf"), "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def plate(name: str) -> None:
    """Подложка номера 520×112 мм (2 пикс/мм): белое поле, чёрная окантовка, поле региона, флаг и RUS.

    Сами знаки «К 417 МР» и «77» — объёмные (выдавленный текст в модели), здесь только подложка.
    """
    W, H = 1040, 224
    im = Image.new("RGB", (W, H), (236, 236, 232))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([3, 3, W - 4, H - 4], radius=16, outline=(18, 18, 18), width=7)
    x_reg = int(W * 0.765)
    d.line([(x_reg, 10), (x_reg, H - 10)], fill=(18, 18, 18), width=6)
    # флаг и RUS в поле региона снизу
    fx0, fy0, fw, fh = x_reg + 92, H - 58, 44, 30
    for k, col in enumerate(((245, 245, 245), (0, 57, 166), (213, 43, 30))):
        d.rectangle([fx0, fy0 + k * fh // 3, fx0 + fw, fy0 + (k + 1) * fh // 3], fill=col)
    d.rectangle([fx0, fy0, fx0 + fw, fy0 + fh], outline=(60, 60, 60), width=1)
    d.text((x_reg + 26, H - 60), "RUS", font=font(28, True), fill=(18, 18, 18))
    # отверстия крепления
    for cx in (int(W * 0.12), int(W * 0.66)):
        d.ellipse([cx - 9, 16, cx + 9, 34], fill=(150, 150, 150), outline=(90, 90, 90))
    im.save(OUT / f"{name}.png")


def battery_label() -> None:
    """Этикетка аккумулятора вымышленной марки «ТЕРМИТ»: тип 6СТ-80, 12 В, 80 А·ч, 760 А."""
    W, H = 800, 360
    im = Image.new("RGB", (W, H), (22, 34, 58))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 70], fill=(226, 138, 24))
    d.text((24, 8), "ТЕРМИТ", font=font(52, True), fill=(20, 20, 24))
    d.text((24, 96), "6СТ-80 VL", font=font(64, True), fill=(235, 235, 235))
    d.text((24, 182), "12V   80Ah   760A (EN)", font=font(40), fill=(210, 214, 220))
    d.text((24, 248), "Необслуживаемый. Не вскрывать. Беречь от огня.", font=font(26), fill=(170, 176, 188))
    for k in range(4):                                # значки предупреждений (простые знаки)
        x0 = 520 + k * 66
        d.regular_polygon((x0 + 26, 318, 26), 3, fill=(226, 190, 40))
        d.text((x0 + 20, 302), "!", font=font(26, True), fill=(20, 20, 20))
    im.save(OUT / "battery_label.png")


if __name__ == "__main__":
    carbon_twill()
    plate("plate_front")
    plate("plate_rear")
    battery_label()
    print("готово:", OUT, sorted(p.name for p in OUT.glob("*.png")))
