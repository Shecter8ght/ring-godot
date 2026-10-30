"""Печать и маркировка мусора и оставленного света — макеты (этап 1 текстур): вымышленные марки кириллицей.

  python -X utf8 tools/dorm_modules/print_designs.py      # → _asset_src/dorm_clutter/prints/*.png (10 пикс/мм)

Марки выдуманы (реальных нет): пиво «Хмельной посад» и «Северный вал», водка «Тихий берег», пиво «Заводское №3»,
сигареты «Кругозор», тушёнка Консервного комбината №4, фонарь «ЛУЧ-2», лампа «ТУРИСТ», химсвет «ХС-15», мигалка
«ФС-1». Эпохи вперемешку (решение владельца): банки и пачка — нынешние, водка — 90-е, тушёнка и фонари — советские.
Шрифты — DejaVu (свободная лицензия Bitstream Vera, _asset_src/fonts или matplotlib). Размер макета — настоящий размер
печати; накладывает их на карты print_apply.py.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_asset_src" / "dorm_clutter" / "prints"
FONTS = [ROOT / "_asset_src" / "fonts", Path("D:/ПРОГРАММЫ/python/Lib/site-packages/matplotlib/mpl-data/fonts/ttf")]
PX = 10  # пикселей на мм


def font(name: str, size_mm: float) -> ImageFont.FreeTypeFont:
    for d in FONTS:
        if (d / name).exists():
            return ImageFont.truetype(str(d / name), int(size_mm * PX))
    raise FileNotFoundError(name)


SANS_B, SANS, SERIF_B, SERIF_BI, SERIF, COND = ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "DejaVuSerif-Bold.ttf",
                                               "DejaVuSerif-BoldItalic.ttf", "DejaVuSerif.ttf", "DejaVuSansMono-Bold.ttf")


def canvas(w_mm: float, h_mm: float, color=(0, 0, 0, 0)) -> tuple:
    im = Image.new("RGBA", (int(w_mm * PX), int(h_mm * PX)), color)
    return im, ImageDraw.Draw(im)


def mm(v: float) -> int:
    return int(round(v * PX))


def text(d, x_mm, y_mm, s, f, fill, stroke=0.0, stroke_fill=None, anchor="mm") -> None:
    d.text((mm(x_mm), mm(y_mm)), s, font=f, fill=fill, anchor=anchor, stroke_width=mm(stroke),
           stroke_fill=stroke_fill)


def gradient(im, top, bottom, box=None) -> None:
    x0, y0, x1, y1 = box or (0, 0, im.width, im.height)
    d = ImageDraw.Draw(im)
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0 - 1)
        d.line([(x0, y), (x1, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))


def barcode(d, x_mm, y_mm, w_mm, h_mm, seed) -> None:
    rnd = random.Random(seed)
    d.rectangle([mm(x_mm - 1.5), mm(y_mm - 1), mm(x_mm + w_mm + 1.5), mm(y_mm + h_mm + 3)], fill=(250, 250, 248, 255))
    x = x_mm
    while x < x_mm + w_mm:
        bw = rnd.choice((0.13, 0.13, 0.26, 0.39))
        if rnd.random() < 0.55:
            d.rectangle([mm(x), mm(y_mm), mm(x + bw) - 1, mm(y_mm + h_mm)], fill=(10, 10, 10, 255))
        x += bw
    digits = "".join(str(rnd.randint(0, 9)) for _ in range(13))
    text(d, x_mm + w_mm / 2, y_mm + h_mm + 1.5, digits, font(SANS, 1.6), (10, 10, 10, 255))


def small(d, x_mm, y_mm, w_mm, lines, f, fill, lh_mm) -> None:
    """Мелкий текст абзацами с переносом по ширине."""
    y = y_mm
    for para in lines:
        words, line = para.split(), ""
        for w in words:
            t = (line + " " + w).strip()
            if d.textlength(t, font=f) > mm(w_mm) and line:
                d.text((mm(x_mm), mm(y)), line, font=f, fill=fill)
                y += lh_mm
                line = w
            else:
                line = t
        if line:
            d.text((mm(x_mm), mm(y)), line, font=f, fill=fill)
            y += lh_mm
        y += lh_mm * 0.3


def wheat(d, cx, cy, s, col) -> None:
    """Колос: стебель и зёрна парами (размеры в мм)."""
    d.line([(mm(cx), mm(cy + 10 * s)), (mm(cx), mm(cy - 9 * s))], fill=col, width=max(2, mm(0.5 * s)))
    for k in range(7):
        y = cy - 8 * s + k * 2.4 * s
        for side in (-1, 1):
            ex, ey = cx + side * 1.4 * s, y
            d.ellipse([mm(ex - 1.1 * s), mm(ey - 1.9 * s), mm(ex + 1.1 * s), mm(ey + 1.9 * s)], fill=col)
    d.ellipse([mm(cx - 1.0 * s), mm(cy - 11 * s), mm(cx + 1.0 * s), mm(cy - 7.2 * s)], fill=col)


COMPOSITION_BEER = ["Пиво светлое пастеризованное. Состав: вода питьевая, солод ячменный светлый, ячмень, хмелепродукты.",
                    "Энергетическая ценность 42 ккал. Хранить при температуре от 0 до 20 °С. Срок годности 9 месяцев.",
                    "Изготовитель: ООО «Пивоваренный завод Посадский», Россия. Чрезмерное употребление пива вредит вашему здоровью."]


# ---------------------------------------------------------------- банки 0,5 л (развёртка 208 × 138 мм)

def can_posad() -> Image.Image:
    im, d = canvas(208, 138, (24, 74, 46, 255))
    gradient(im, (20, 88, 52), (12, 46, 28))
    d.rectangle([0, mm(118), im.width, im.height], fill=(196, 160, 72, 255))
    d.rectangle([0, 0, im.width, mm(9)], fill=(196, 160, 72, 255))
    d.rectangle([0, mm(116), im.width, mm(118)], fill=(120, 20, 24, 255))
    for side in (0, 104):  # рисунок дважды по кругу — с любой стороны лицо
        c = side + 52
        for dx in (-44, 44):
            wheat(d, c + dx, 60, 1.7, (214, 176, 84, 255))
        text(d, c, 46, "ХМЕЛЬНОЙ", font(SERIF_B, 13), (232, 196, 102, 255), 0.6, (60, 30, 10, 255))
        text(d, c, 64, "ПОСАД", font(SERIF_B, 17), (232, 196, 102, 255), 0.7, (60, 30, 10, 255))
        d.rounded_rectangle([mm(c - 22), mm(76), mm(c + 22), mm(86)], radius=mm(3), fill=(120, 20, 24, 255))
        text(d, c, 81, "СВЕТЛОЕ", font(SANS_B, 6), (246, 236, 210, 255))
        text(d, c, 96, "ПИВО · 4,6 % об. · 0,5 л", font(SANS_B, 4.2), (236, 222, 180, 255))
        text(d, c, 127, "с 1987 года", font(SERIF_BI, 4), (80, 50, 18, 255))
    small(d, 94, 101, 22, COMPOSITION_BEER, font(SANS, 1.25), (225, 225, 215, 255), 1.6)
    barcode(d, 178, 98, 16, 9, 11)
    text(d, 4, 4.5, "ALU", font(SANS_B, 3), (80, 50, 18, 255), anchor="lm")
    return im


def can_val() -> Image.Image:
    im, d = canvas(208, 138, (18, 28, 60, 255))
    gradient(im, (30, 46, 92), (10, 14, 34))
    for k in range(0, 208, 13):  # серебристые полосы по высоте
        d.rectangle([mm(k), 0, mm(k + 2.2), im.height], fill=(160, 170, 186, 255))
    for side in (0, 104):
        c = side + 52
        d.rectangle([mm(c - 34), mm(30), mm(c + 34), mm(92)], fill=(14, 20, 46, 255))
        text(d, c, 44, "СЕВЕРНЫЙ", font(SANS_B, 10), (228, 232, 240, 255))
        text(d, c, 62, "ВАЛ", font(SANS_B, 20), (228, 232, 240, 255), 0.5, (90, 110, 150, 255))
        text(d, c, 80, "КРЕПКОЕ  8 %", font(SANS_B, 6.5), (230, 70, 50, 255))
        text(d, c, 104, "пиво светлое · 0,5 л", font(SANS, 4.2), (210, 216, 228, 255))
    small(d, 92, 108, 22, COMPOSITION_BEER[:2] + ["Изготовитель: АО «Северный вал», Россия."], font(SANS, 1.25),
          (210, 216, 228, 255), 1.6)
    barcode(d, 178, 112, 16, 9, 23)
    return im


# ---------------------------------------------------------------- водка «Тихий берег» (90-е)

def vodka_front() -> Image.Image:
    im, d = canvas(80, 85, (242, 240, 232, 255))
    gold, blue, red = (176, 140, 62, 255), (28, 52, 118, 255), (168, 24, 30, 255)
    d.rectangle([mm(2), mm(2), mm(78), mm(83)], outline=gold, width=mm(0.8))
    d.rectangle([mm(3.6), mm(3.6), mm(76.4), mm(81.4)], outline=gold, width=mm(0.3))
    for x, h in ((7, 30), (11.5, 36), (70, 34)):  # берёзки по краям, не по надписи
        d.rectangle([mm(x), mm(46 - h / 2), mm(x + 2.2), mm(58)], fill=(250, 250, 248, 255), outline=(60, 60, 60, 255))
        for k in range(5):
            y = 46 - h / 2 + 3 + k * h / 6
            d.line([(mm(x), mm(y)), (mm(x + 1.4), mm(y))], fill=(20, 20, 20, 255), width=mm(0.5))
    d.rectangle([mm(4), mm(52), mm(76), mm(58)], fill=(110, 150, 196, 255))
    text(d, 40, 14, "ВОДКА", font(SANS_B, 5.5), blue)
    text(d, 40, 28, "Тихий", font(SERIF_BI, 11), blue)
    text(d, 40, 42, "берег", font(SERIF_BI, 11), blue)
    d.ellipse([mm(32), mm(60), mm(48), mm(76)], fill=red)
    text(d, 40, 68, "ТБ", font(SERIF_B, 6), (246, 230, 200, 255))
    text(d, 16, 72, "40 % об.", font(SANS_B, 3.6), blue)
    text(d, 64, 72, "0,5 л", font(SANS_B, 3.6), blue)
    return im


def vodka_back() -> Image.Image:
    im, d = canvas(45, 50, (242, 240, 232, 255))
    d.rectangle([mm(1.5), mm(1.5), mm(43.5), mm(48.5)], outline=(176, 140, 62, 255), width=mm(0.4))
    text(d, 22.5, 6, "ВОДКА «ТИХИЙ БЕРЕГ»", font(SANS_B, 2.4), (28, 52, 118, 255))
    small(d, 4, 10, 37, ["Спирт этиловый ректификованный «Люкс», вода питьевая исправленная. Крепость 40 %.",
                         "Изготовитель: ЗАО «Ликёро-водочный завод Приречный», Россия.",
                         "Употребление алкоголя вредит вашему здоровью."], font(SANS, 1.6), (40, 40, 40, 255), 2.1)
    barcode(d, 8, 36, 29, 7, 37)
    return im


def vodka_neck() -> Image.Image:
    im, d = canvas(93, 13, (28, 52, 118, 255))
    d.rectangle([0, mm(1), im.width, mm(1.6)], fill=(176, 140, 62, 255))
    d.rectangle([0, mm(11.4), im.width, mm(12)], fill=(176, 140, 62, 255))
    for c in (23, 70):
        text(d, c, 6.6, "ТИХИЙ БЕРЕГ", font(SERIF_B, 4.2), (236, 220, 170, 255))
    return im


# ---------------------------------------------------------------- пиво «Заводское №3» в бутылке

def beer_front() -> Image.Image:
    im, d = canvas(92, 72, (230, 214, 168, 255))
    gradient(im, (236, 222, 180), (214, 192, 140))
    d.ellipse([mm(16), mm(6), mm(76), mm(66)], fill=(150, 30, 26, 255), outline=(60, 36, 14, 255), width=mm(0.8))
    d.ellipse([mm(19), mm(9), mm(73), mm(63)], outline=(226, 196, 120, 255), width=mm(0.5))
    text(d, 46, 26, "ЗАВОДСКОЕ", font(SERIF_B, 7.5), (240, 224, 186, 255))
    text(d, 46, 42, "№3", font(SERIF_B, 14), (240, 224, 186, 255))
    text(d, 46, 56, "светлое", font(SERIF_BI, 4.5), (240, 224, 186, 255))
    for x in (8, 84):
        wheat(d, x, 36, 1.3, (120, 80, 30, 255))
    text(d, 46, 69, "0,5 л · 4,5 % · ГОСТ", font(SANS_B, 2.6), (60, 36, 14, 255))
    return im


def beer_shoulder() -> Image.Image:
    im, d = canvas(52, 18, (150, 30, 26, 255))
    d.rectangle([mm(1), mm(1), mm(51), mm(17)], outline=(226, 196, 120, 255), width=mm(0.4))
    text(d, 26, 9.2, "ЗАВОДСКОЕ", font(SERIF_B, 5), (240, 224, 186, 255))
    return im


# ---------------------------------------------------------------- сигареты «Кругозор» (нынешние)

def pack_front() -> Image.Image:
    im, d = canvas(56, 88, (232, 230, 226, 255))
    d.rectangle([0, 0, im.width, mm(44)], fill=(18, 58, 112, 255))
    d.rectangle([0, mm(40), im.width, mm(44)], fill=(196, 160, 72, 255))
    d.ellipse([mm(18), mm(6), mm(38), mm(26)], outline=(232, 230, 226, 255), width=mm(0.8))
    d.line([(mm(18), mm(16)), (mm(38), mm(16))], fill=(232, 230, 226, 255), width=mm(0.5))
    d.arc([mm(22), mm(6), mm(34), mm(26)], 270, 90, fill=(232, 230, 226, 255), width=mm(0.5))
    d.arc([mm(22), mm(6), mm(34), mm(26)], 90, 270, fill=(232, 230, 226, 255), width=mm(0.5))
    text(d, 28, 33, "КРУГОЗОР", font(SANS_B, 6.2), (240, 238, 232, 255))
    # предупреждение — нижняя половина
    d.rectangle([mm(2), mm(47), mm(54), mm(86)], fill=(250, 250, 250, 255), outline=(10, 10, 10, 255), width=mm(0.8))
    text(d, 28, 60, "КУРЕНИЕ", font(SANS_B, 7), (10, 10, 10, 255))
    text(d, 28, 72, "УБИВАЕТ", font(SANS_B, 7), (10, 10, 10, 255))
    text(d, 28, 81, "Минздрав предупреждает", font(SANS, 2.4), (10, 10, 10, 255))
    return im


def pack_back() -> Image.Image:
    im, d = canvas(56, 88, (232, 230, 226, 255))
    d.rectangle([0, 0, im.width, mm(30)], fill=(18, 58, 112, 255))
    text(d, 28, 15, "КРУГОЗОР", font(SANS_B, 5), (240, 238, 232, 255))
    d.rectangle([mm(2), mm(33), mm(54), mm(66)], fill=(250, 250, 250, 255), outline=(10, 10, 10, 255), width=mm(0.8))
    text(d, 28, 44, "КУРЕНИЕ ВЫЗЫВАЕТ", font(SANS_B, 3.6), (10, 10, 10, 255))
    text(d, 28, 52, "РАК ЛЁГКИХ", font(SANS_B, 5), (10, 10, 10, 255))
    small(d, 4, 69, 48, ["20 сигарет с фильтром. Изготовитель: АО «Табачная фабрика Кругозор», Россия."],
          font(SANS, 1.8), (30, 30, 30, 255), 2.3)
    barcode(d, 16, 77, 24, 6, 53)
    return im


# ---------------------------------------------------------------- оставленный свет

def mark(w_mm, h_mm, lines, color) -> Image.Image:
    im, d = canvas(w_mm, h_mm)
    n = len(lines)
    for k, (s, f) in enumerate(lines):
        text(d, w_mm / 2, h_mm * (k + 0.5) / n, s, f, color)
    return im


def stew() -> Image.Image:
    """Этикетка тушёнки на банку Ø73 — обёртка 229 × 60 мм; выцветание и обрывы — при наложении."""
    im, d = canvas(229, 60, (226, 214, 176, 255))
    for side in (0, 114.5):
        c = side + 57
        d.rectangle([mm(side + 4), mm(4), mm(side + 110), mm(56)], outline=(140, 30, 26, 255), width=mm(0.7))
        text(d, c, 14, "ГОВЯДИНА", font(SANS_B, 9), (140, 30, 26, 255))
        text(d, c, 27, "ТУШЁНАЯ", font(SANS_B, 9), (140, 30, 26, 255))
        # бычок: тело, голова, ноги, рога — простыми фигурами
        bx, by = c, 42
        d.ellipse([mm(bx - 12), mm(by - 5), mm(bx + 8), mm(by + 4)], fill=(110, 60, 30, 255))
        d.ellipse([mm(bx + 6), mm(by - 7), mm(bx + 13), mm(by)], fill=(110, 60, 30, 255))
        for lx in (-10, -6, 2, 5):
            d.rectangle([mm(bx + lx), mm(by + 2), mm(bx + lx + 1.6), mm(by + 8)], fill=(110, 60, 30, 255))
        d.line([(mm(bx + 7), mm(by - 6)), (mm(bx + 5), mm(by - 9))], fill=(240, 230, 200, 255), width=mm(0.6))
        d.line([(mm(bx + 12), mm(by - 6)), (mm(bx + 14), mm(by - 9))], fill=(240, 230, 200, 255), width=mm(0.6))
        text(d, side + 22, 50, "ВЫСШИЙ СОРТ", font(SANS_B, 2.6), (140, 30, 26, 255))
        text(d, side + 92, 50, "ГОСТ 5284", font(SANS_B, 2.6), (140, 30, 26, 255))
    text(d, 114.5, 57, "Консервный комбинат №4 · масса нетто 338 г", font(SANS, 2.2), (90, 60, 40, 255))
    return im


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    white, black = (236, 236, 230, 255), (24, 24, 24, 255)
    items = {
        "can_posad": can_posad(), "can_val": can_val(),
        "vodka_front": vodka_front(), "vodka_back": vodka_back(), "vodka_neck": vodka_neck(),
        "beer_front": beer_front(), "beer_shoulder": beer_shoulder(),
        "pack_front": pack_front(), "pack_back": pack_back(),
        "luch2": mark(44, 9, [("ЛУЧ-2", font(SANS_B, 6))], white),
        "turist": mark(56, 14, [("ТУРИСТ", font(SANS_B, 7)), ("ЛАМПА КЕМПИНГОВАЯ", font(SANS, 2.6))], (232, 230, 220, 255)),
        "hs15": mark(96, 10, [("ХС-15  ·  ИСТОЧНИК СВЕТА ХИМИЧЕСКИЙ  ·  12 ч", font(SANS_B, 3.2))], black),
        "stew": stew(),
    }
    # мигалка: «ФС-1» и знак «внимание» — чёрным по корпусу
    im, d = canvas(64, 40)
    d.polygon([(mm(10), mm(4)), (mm(1), mm(20)), (mm(19), mm(20))], fill=black)
    d.polygon([(mm(10), mm(7.5)), (mm(4.2), mm(18)), (mm(15.8), mm(18))], fill=(222, 160, 40, 255))
    text(d, 10, 15, "!", font(SANS_B, 7), black)
    text(d, 42, 11, "ФС-1", font(SANS_B, 10), black)
    text(d, 32, 28, "ФОНАРЬ СИГНАЛЬНЫЙ  6 В", font(SANS_B, 3.2), black)
    text(d, 32, 34, "№ 0417", font(SANS, 2.8), black)
    items["fs1"] = im
    for name, img in items.items():
        img.save(OUT / f"{name}.png")
        print("PRINT", name, img.size)


if __name__ == "__main__":
    build()
