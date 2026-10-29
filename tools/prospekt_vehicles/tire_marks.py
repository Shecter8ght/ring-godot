"""Транспорт «Проспекта»: рельеф наружной боковины шины — надписи, кольца, насечка, метки износа — картой высот.

    python -X utf8 tools/prospekt_vehicles/tire_marks.py <выход.npz> <ширина мм> <профиль %> <обод дюйм> <r обода мм> <H мм>

Карта — в полярной развёртке боковины: колонка — угол по часовой стрелке от верха колеса, если смотреть снаружи (+X),
строка — радиус от наружного края боковины (r обода + H) внутрь, шаг RES мм. Высота — мм над гладкой боковиной.
Надписи — как на настоящей шине: марка крупно дважды, модель, размер с индексами, «TUBELESS», «RADIAL», нагрузка и
давление мелко, код омологации, дата в овале; у обода — кольцо и полоса радиальной насечки; у плеча — метки износа.
Марка вымышленная («ВЕХА»), реальных марок и логотипов нет. Шрифт DejaVu (свободная лицензия, assets/CREDITS.md).
Карту читает vwheels.tire_high (Blender: в Python Blender нет PIL — отдельный процесс, как упаковщик uvpack.py).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

RES = 0.15                 # мм на пиксель карты по радиусу и по дуге у наружного края
TEXT_H = 0.9               # мм — высота выпуклых надписей
FONT_DIRS = (Path(__file__).resolve().parents[2] / "_asset_src" / "fonts",
             Path("D:/ПРОГРАММЫ/python/Lib/site-packages/matplotlib/mpl-data/fonts/ttf"))
BRAND, MODEL = "ВЕХА", "ГОРОД-2"


def font(name: str, cap_mm: float) -> ImageFont.FreeTypeFont:
    """Шрифт с высотой прописной cap_mm при шаге RES (кегль у шрифтов разный — меряем по «Н»)."""
    path = next(d / name for d in FONT_DIRS if (d / name).exists())
    probe = ImageFont.truetype(str(path), 200)
    l, t, r, b = probe.getbbox("Н")
    size = int(round(200 * (cap_mm / RES) / (b - t)))
    return ImageFont.truetype(str(path), size)


def text_img(text: str, f: ImageFont.FreeTypeFont, track: float = 0.06) -> np.ndarray:
    """Строка в картинку высот 0…1 (шаг RES, ровно по прописным): буквы по одной с разрядкой track (доля кегля)."""
    asc, desc = f.getmetrics()
    gap = f.size * track
    w = int(sum(f.getlength(c) for c in text) + gap * (len(text) - 1)) + 8
    img = Image.new("L", (w, asc + desc + 8), 0)
    d = ImageDraw.Draw(img)
    x = 4.0
    for c in text:
        d.text((x, 4), c, font=f, fill=255)
        x += f.getlength(c) + gap
    img = img.filter(ImageFilter.GaussianBlur(1.2))       # скруглённая кромка буквы (литьё пресс-формы)
    a = np.asarray(img, np.float32) / 255.0
    rows = np.where(a.max(1) > 0.02)[0]
    cols = np.where(a.max(0) > 0.02)[0]
    return a[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]


class Side:
    """Карта боковины: строки — радиус (сверху наружный край), колонки — угол по часовой от верха."""

    def __init__(self, r0: float, H: float):
        self.r0, self.H = r0, H
        self.r_top = r0 + H
        self.rows = int(math.ceil(H / RES))
        self.cols = int(math.ceil(2 * math.pi * self.r_top / RES))
        self.h = np.zeros((self.rows, self.cols), np.float32)
        self.r = self.r_top - (np.arange(self.rows) + 0.5) * RES          # радиус строки, мм
        self.a = (np.arange(self.cols) + 0.5) / self.cols * 2 * math.pi   # угол колонки, рад по часовой
        self.placed: list = []

    def put(self, img: np.ndarray, ang_deg: float, hc: float, height: float = TEXT_H, label: str = "") -> None:
        """Картинку высот (шаг RES) — центром на угол ang_deg (по часовой от верха) и высоту hc мм от обода, по дуге:
        ширина картинки — длина дуги на радиусе её середины."""
        rc = self.r0 + hc
        h_px, w_px = img.shape
        cols_per_mm = self.cols / (2 * math.pi * rc)
        new_w = max(1, int(round(w_px * RES * cols_per_mm)))
        im = Image.fromarray((img * 255).astype(np.uint8)).resize((new_w, h_px), Image.BILINEAR)
        a = np.asarray(im, np.float32) / 255.0 * height
        c0 = int(round(ang_deg / 360.0 * self.cols - new_w / 2))
        r_top_item = rc + h_px * RES / 2
        row0 = int(round((self.r_top - r_top_item) / RES))
        idx = (np.arange(new_w) + c0) % self.cols
        rr = slice(max(0, row0), min(self.rows, row0 + h_px))
        sub = a[rr.start - row0: rr.stop - row0]
        self.h[rr, idx] = np.maximum(self.h[rr, idx], sub)
        span = (new_w / self.cols * 360.0)
        self.placed.append((label, ang_deg - span / 2, ang_deg + span / 2, hc - h_px * RES / 2, hc + h_px * RES / 2))

    def ring(self, hc: float, width: float, height: float) -> None:
        """Кольцо по всей окружности: выпуклость с округлым сечением на высоте hc мм от обода."""
        d = np.abs(self.r - (self.r0 + hc)) / (width / 2)
        prof = np.where(d < 1.0, np.sqrt(np.clip(1 - d ** 2, 0, 1)), 0.0) * height
        self.h = np.maximum(self.h, prof[:, None].astype(np.float32))

    def knurl(self, h0: float, h1: float, period: float, height: float) -> None:
        """Полоса радиальной насечки между h0 и h1 мм от обода: рёбрышки шагом period мм по дуге середины полосы."""
        rc = self.r0 + (h0 + h1) / 2
        n = int(round(2 * math.pi * rc / period))
        ph = (self.a * n / (2 * math.pi)) % 1.0
        rib = (np.clip(1.0 - np.abs(ph - 0.5) * 4.0, 0, 1) ** 0.5) * height     # гребень трапецией
        band = (self.r >= self.r0 + h0) & (self.r <= self.r0 + h1)
        self.h[band] = np.maximum(self.h[band], rib[None, :])

    def triangle(self, ang_deg: float, hc: float, w: float, tall: float, height: float) -> None:
        """Метка износа протектора: треугольник вершиной к плечу."""
        px = int(w / RES) + 4
        py = int(tall / RES) + 4
        img = Image.new("L", (px, py), 0)
        ImageDraw.Draw(img).polygon([(2, py - 2), (px - 2, py - 2), (px / 2, 2)], fill=255)
        img = img.filter(ImageFilter.GaussianBlur(1.0))
        self.put(np.asarray(img, np.float32) / 255.0, ang_deg, hc, height, "TWI")

    def oval(self, text: str, f: ImageFont.FreeTypeFont, ang_deg: float, hc: float) -> None:
        """Дата выпуска в овальной рамке (неделя и год)."""
        t = text_img(text, f, 0.02)
        h, w = t.shape
        pad = int(1.8 / RES)
        img = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
        dr = ImageDraw.Draw(img)
        dr.rounded_rectangle((1, 1, w + 2 * pad - 2, h + 2 * pad - 2), radius=(h + 2 * pad) // 2, outline=255,
                             width=max(2, int(0.7 / RES)))
        img = img.filter(ImageFilter.GaussianBlur(1.0))
        a = np.asarray(img, np.float32) / 255.0
        a[pad:pad + h, pad:pad + w] = np.maximum(a[pad:pad + h, pad:pad + w], t)
        self.put(a, ang_deg, hc, TEXT_H, "date")


def build(width: int, aspect: int, rim_in: float, r0: float, H: float) -> Side:
    s = Side(r0, H)
    k = H / 120.0                                     # размеры надписей — от высоты боковины легковой 185/65 R15
    s.ring(7.0 * k, 3.4, 1.1)                         # кольцо у закраины обода (защита закраины)
    s.ring(11.5 * k, 0.8, 0.45)
    s.knurl(13.0 * k, 23.0 * k, 3.2, 0.35)            # полоса насечки
    s.ring(24.0 * k, 0.8, 0.45)
    s.ring(H - 15.0 * k, 0.7, 0.3)                    # линия разъёма пресс-формы у плеча
    bold, obl, reg = "DejaVuSans-Bold.ttf", "DejaVuSans-BoldOblique.ttf", "DejaVuSans.ttf"
    brand = text_img(BRAND, font(obl, 20.0 * k), 0.10)
    model = text_img(MODEL, font(bold, 8.5 * k), 0.06)
    size = text_img(f"{width}/{aspect} R{rim_in:g} 88T", font(bold, 12.0 * k), 0.04)
    tl = text_img("TUBELESS", font(bold, 6.0 * k), 0.08)
    rad = text_img("RADIAL", font(bold, 6.0 * k), 0.08)
    ms = text_img("M+S", font(bold, 7.0 * k), 0.06)
    load = text_img("MAX LOAD 560 kg (1235 lbs)   MAX PRESS 350 kPa (51 psi)", font(reg, 3.6 * k), 0.04)
    plies = text_img("TREAD 2 POLYESTER + 2 STEEL + 1 POLYAMIDE   SIDEWALL 2 POLYESTER", font(reg, 3.2 * k), 0.03)
    homol = text_img("Е22 0213459", font(reg, 4.0 * k), 0.04)
    hb, hs, hl = 0.64 * H, 0.43 * H, 0.27 * H
    rc_b, rc_s = r0 + hb, r0 + hs

    def deg(mm: float, rc: float) -> float:
        return math.degrees(mm / rc)
    for a0 in (0.0, 180.0):
        s.put(brand, a0, hb, label="brand")
        s.put(model, a0 + deg(brand.shape[1] * RES / 2 + 16 + model.shape[1] * RES / 2, rc_b), hb, label="model")
        s.put(size, a0 + 90.0, hs, label="size")
        s.put(tl, a0 + 90.0 + deg(size.shape[1] * RES / 2 + 12 + tl.shape[1] * RES / 2, rc_s), hs, label="tubeless")
        s.put(rad, a0 + 90.0 - deg(size.shape[1] * RES / 2 + 12 + rad.shape[1] * RES / 2, rc_s), hs, label="radial")
    s.put(ms, 140.0, hs, label="M+S")
    s.put(ms, 320.0, hs, label="M+S")
    s.put(load, 45.0, hl, label="load")
    s.put(plies, 225.0, hl, label="plies")
    s.put(homol, 300.0, hl, label="homol")
    s.oval("2319", font(bold, 4.5 * k), 328.0, hl)
    for i in range(6):                                # метки износа — у плеча, против выступов в канавках протектора
        s.triangle(30.0 + 60.0 * i, H - 9.0 * k, 6.0 * k, 5.0 * k, 0.6)
    return s


def main() -> None:
    out, width, aspect, rim_in, r0, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), \
        float(sys.argv[5]), float(sys.argv[6])
    s = build(width, aspect, rim_in, r0, H)
    q = np.clip(np.round(s.h / 2.0 * 255), 0, 255).astype(np.uint8)          # 0…2 мм в 8 бит
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out, h=q, scale=np.float32(2.0 / 255), res=np.float32(RES), r_top=np.float32(s.r_top),
                        cols=np.int32(s.cols))
    over = []
    pl = sorted(s.placed, key=lambda p: p[1])
    for i, a in enumerate(pl):
        for b in pl[i + 1:]:
            if b[1] < a[2] and a[1] < b[2] and b[3] < a[4] and a[3] < b[4]:
                over.append((a[0], b[0]))
    print(f"боковина {width}/{aspect} R{rim_in:g}: {s.cols}×{s.rows}, надписей {len(s.placed)}, наложений {over or 'нет'}")
    if len(sys.argv) > 7:                             # превью развёртки для себя
        prev = Image.fromarray(np.clip(s.h / 1.2 * 255, 0, 255).astype(np.uint8))
        prev.resize((prev.width // 4, prev.height // 4), Image.BILINEAR).save(sys.argv[7])


if __name__ == "__main__":
    main()
