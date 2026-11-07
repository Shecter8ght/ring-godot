# -*- coding: utf-8 -*-
"""Санаторий — вид на плотину с парадной террасы, два варианта (docs/design/sanatorium_map.md, §3).

Владелец 2026-11-07: «плотину тоже должно быть видно как мега-гипер-структуру». В принятом мире «Вертолёта»
(mission_helicopter.md, пункты 24, 26, 47) плотина арочная, около 260 м, санаторий — на берегу водохранилища, то
есть выше плотины; огромная стена раскрывается только со стороны нижнего ущелья. Лист сравнивает:

  А — санаторий у нижнего озера, под плотиной: видна вся стена;
  Б — санаторий на водохранилище, вода сработана: над водой ≈ 80 м стены и светлая полоса «ванны» на скалах.

Перспектива честная: глаз на террасе +33,7 м над озером, поле зрения 80° по горизонтали (как в игре), плотина
в 1,2 км. Цвета и рельеф — эскиз, не проект.

    python -X utf8 tools/sanatorium_dam_view.py   → docs/plans/sanatorium_dam_view_v01.png
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/plans/sanatorium_dam_view_v01.png'

VW, VH = 1280, 720            # кадр одного вида
FOV_H = 80.0
FOC = VW / 2 / math.tan(math.radians(FOV_H / 2))
EYE = 33.7                    # глаз на парадной террасе: плато +32 + 1,7
DIST = 1200.0                 # до хорды гребня
HALF = 500.0                  # полухорда гребня (гребень ≈ 1 км)
SAG = 140.0                   # стрела арки
DAM_H = 260.0                 # высота плотины (принята в мире «Вертолёта»)
LOW_FREE = 80.0               # вариант Б: стены над сработанной водой
CAP_H = 92

PAPER = (247, 245, 239)
INK = (40, 42, 46)


def font(size, bold=False):
    return ImageFont.truetype(f'C:/Windows/Fonts/{"arialbd" if bold else "arial"}.ttf', size)


def wave(x, *pairs):
    return sum(a * math.sin(x / l + ph) for a, l, ph in pairs)


class Cam:
    def __init__(self, d, oy):
        self.d, self.oy = d, oy

    def p(self, u, y, z):
        return (VW / 2 + FOC * u / z, self.oy + VH / 2 - FOC * (y - EYE) / z)

    def poly(self, pts, fill):
        self.d.polygon([self.p(*q) for q in pts], fill=fill)

    def line(self, pts, fill, width=1):
        self.d.line([self.p(*q) for q in pts], fill=fill, width=width)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def sky(cam):
    for y in range(VH):
        t = y / VH
        cam.d.line([(0, cam.oy + y), (VW, cam.oy + y)], fill=mix((118, 146, 186), (244, 206, 168), min(1.0, t * 1.6)))


def mountains(cam, z, u0, u1, base, amp, color, seed):
    pts = [(u0, -50, z)]
    n = 90
    for i in range(n + 1):
        u = u0 + (u1 - u0) * i / n
        pts.append((u, base + amp * (0.55 + 0.45 * wave(u + seed, (0.6, 900, 0.3), (0.3, 340, 1.1), (0.12, 120, 2.0))), z))
    pts.append((u1, -50, z))
    cam.poly(pts, color)


def foundation(u):
    """Высота основания плотины над её подошвой по ширине ущелья (V-образное ущелье)."""
    return DAM_H * min(1.0, abs(u) / HALF) ** 1.6


def gorge_walls(cam, z_edge, top_extra, color, ring=None):
    """Склоны ущелья по бокам плотины: от примыкания гребня вверх и в стороны."""
    for sgn in (-1, 1):
        pts = []
        for i in range(31):
            t = i / 30
            u = sgn * (HALF - 40 + t * 1500)
            y = (cam.crest_y + 10) + top_extra * (t ** 0.7) + 40 * wave(u, (1.0, 70, 0.5), (0.6, 31, 1.7))
            pts.append((u, y, z_edge - t * 300))
        pts += [(sgn * 2400, -60, z_edge - 300), (sgn * (HALF - 120), -60, z_edge)]
        cam.poly(pts, color)
        if ring:  # светлая «ванна» — полоса скал от сработанной воды до прежнего уровня
            band = []
            for i in range(31):
                t = i / 30
                band.append((sgn * (cam.water_u + t * 1500), ring, z_edge - t * 300))
            for i in range(30, -1, -1):
                t = i / 30
                band.append((sgn * (cam.water_u + t * 1500), 0.0, z_edge - t * 300))
            cam.poly(band, (214, 200, 172))


def banks(cam, color_far, color_near, ring=None):
    """Лесистые берега озера по бокам — от ущелья к санаторию."""
    for sgn, near_u in ((-1, -480), (1, 560)):
        top, base = [], []
        for i in range(25):
            t = i / 24
            z = 1080 - t * 820
            u = sgn * (560 + t * (abs(near_u) - 560) + 30 * wave(z, (1, 60, 0.4)))
            top.append((u + sgn * 900, 120 + 160 * (1 - t) + 25 * wave(z, (1.0, 45, 1.0)), z))
            base.append((u, 0.0, z))
        cam.poly(top + list(reversed(base)), mix(color_far, color_near, 0.5))
        if ring:
            cam.poly([(u, ring, z) for u, _, z in base] + [(u, 0.0, z) for u, _, z in reversed(base)], (214, 200, 172))


def dam(cam, downstream):
    """Арка: со стороны нижнего бьефа центр дальше (арка выгнута вверх по течению), с водохранилища — ближе."""
    sgn = 1.0 if downstream else -1.0
    us = [HALF * (i / 60 * 2 - 1) for i in range(61)]

    def zc(u):
        return DIST + sgn * SAG * (1 - (u / HALF) ** 2)

    top = cam.crest_y
    bottom_of = (lambda u: foundation(u) + cam.foot_y) if downstream else (lambda u: max(0.0, foundation(u) + cam.foot_y))
    face = [(u, top, zc(u)) for u in us]
    base = [(u, bottom_of(u), zc(u) - (40 * (1 - foundation(u) / DAM_H) if downstream else 0)) for u in reversed(us)]
    cam.poly(face + base, (160, 160, 164) if downstream else (176, 176, 180))
    # швы блоков бетонирования и пятна стока
    for i, u in enumerate(us[1:-1]):
        z = zc(u)
        y0 = bottom_of(u)
        cam.line([(u, top, z), (u, y0, z)], (142, 142, 148) if downstream else (150, 148, 140))
        if downstream and abs(u) < 260 and i % 3 == 0:
            cam.line([(u + 6, top - 20, z), (u + 6, top - 20 - 90 * (1 - abs(u) / 260), z)], (128, 130, 136), 2)
    for k in range(1, 9):
        yy = top - k * 28
        cam.line([(u, max(yy, bottom_of(u)), zc(u)) for u in us], (150, 150, 156) if downstream else (158, 156, 148))
    if not downstream:  # следы прежнего уровня воды на верхней грани
        cam.poly([(u, LOW_FREE - 6, zc(u)) for u in us] + [(u, 0.0, zc(u)) for u in reversed(us)], (150, 146, 138))
    # водосбросные отверстия под гребнем
    for k in range(-2, 3):
        u = k * 34
        z = zc(u)
        cam.poly([(u - 11, top - 14, z), (u + 11, top - 14, z), (u + 11, top - 30, z), (u - 11, top - 30, z)], (70, 72, 80))
    # гребень: парапет, фонари, два козловых крана
    cam.line([(u, top + 2, zc(u)) for u in us], (226, 214, 190), 3)
    for u in us[::3]:
        cam.line([(u, top + 2, zc(u)), (u, top + 12, zc(u))], (90, 90, 96))
    for uc in (-140, 90):
        z = zc(uc)
        for du in (-14, 14):
            cam.line([(uc + du, top, z), (uc + du, top + 34, z)], (80, 82, 90), 2)
        cam.line([(uc - 20, top + 34, z), (uc + 20, top + 34, z)], (80, 82, 90), 3)


def hpp(cam):
    """Здание ГЭС у подошвы — указатель масштаба: 45 м высотой, 300 м длиной, и оно мелкое."""
    z = DIST - 30
    cam.poly([(-150, 0, z), (150, 0, z), (150, 45, z), (-150, 45, z)], (196, 186, 170))
    for k in range(10):
        u = -135 + k * 30
        cam.poly([(u, 12, z - 1), (u + 18, 12, z - 1), (u + 18, 34, z - 1), (u, 34, z - 1)], (120, 130, 140))
    cam.poly([(170, 0, z + 20), (260, 0, z + 20), (260, 14, z + 20), (170, 14, z + 20)], (150, 150, 150))


def water(cam, color):
    y_h = cam.p(0, 0, 1160)[1]
    for y in range(int(y_h), cam.oy + VH):
        t = max(0.0, (y - y_h) / max(1, cam.oy + VH - y_h))
        cam.d.line([(0, y), (VW, y)], fill=mix(color, (60, 92, 112), t ** 0.6))


def foreground(cam):
    """Балюстрада террасы и хвойные по краям (владелец: только ели и сосны)."""
    d, oy = cam.d, cam.oy
    d.rectangle([0, oy + VH - 46, VW, oy + VH], fill=(206, 196, 178))
    d.rectangle([0, oy + VH - 58, VW, oy + VH - 46], fill=(226, 218, 200))
    for x in range(10, VW, 26):
        d.rectangle([x, oy + VH - 46, x + 9, oy + VH - 10], fill=(232, 224, 206))
    for x0, h, kind in ((-20, 560, 'ель'), (90, 470, 'сосна'), (VW - 70, 600, 'ель'), (VW - 190, 430, 'сосна')):
        base = oy + VH - 50
        if kind == 'ель':
            for k in range(9):
                w = 30 + k * 18
                yt = base - h + k * h / 10
                d.polygon([(x0 + 60, yt), (x0 + 60 - w, yt + h / 6), (x0 + 60 + w, yt + h / 6)], fill=(36, 58, 44))
        else:
            d.rectangle([x0 + 56, base - h, x0 + 66, base], fill=(120, 70, 50))
            for cx, cy, r in ((0, 0, 70), (-50, 30, 50), (55, 25, 55), (10, 60, 45)):
                d.ellipse([x0 + 61 + cx - r, base - h + cy - r * 0.6, x0 + 61 + cx + r, base - h + cy + r * 0.6], fill=(52, 78, 52))


def angle(y, z):
    return math.degrees(math.atan2(y - EYE, z))


img = Image.new('RGB', (VW, (VH + CAP_H) * 2 + 60), PAPER)
d = ImageDraw.Draw(img)
d.text((20, 16), 'Санаторий · вид на плотину с парадной террасы (глаз +33,7 м, поле зрения 80°, плотина 260 м в 1,2 км)',
       font=font(20, True), fill=INK)

for idx, downstream in enumerate((True, False)):
    oy = 60 + idx * (VH + CAP_H)
    cam = Cam(d, oy)
    cam.d = d
    if downstream:
        cam.crest_y, cam.foot_y, cam.water_u = DAM_H, 0.0, HALF
    else:
        cam.crest_y, cam.foot_y = LOW_FREE, LOW_FREE - DAM_H
        cam.water_u = HALF * ((DAM_H - LOW_FREE) / DAM_H) ** (1 / 1.6)
    sky(cam)
    mountains(cam, 5200, -6000, 6000, 620, 520, (150, 166, 190), 0)
    mountains(cam, 3200, -4200, 4200, 380, 420, (128, 146, 164), 700)
    gorge_walls(cam, DIST + 40, 520 if downstream else 360, (118, 116, 108), None if downstream else LOW_FREE - 6)
    water(cam, (150, 170, 182) if downstream else (138, 160, 170))
    dam(cam, downstream)
    if downstream:
        hpp(cam)
    banks(cam, (64, 92, 66), (44, 70, 50), None if downstream else LOW_FREE * 0.55)
    foreground(cam)
    # подпись и угловые размеры
    z_top = DIST + (SAG if downstream else -SAG)
    top_deg = angle(cam.crest_y, z_top)
    bot_deg = angle(0.0, z_top - (40 if downstream else 0))
    wid = 2 * math.degrees(math.atan2(HALF, DIST))
    cy = oy + VH + 10
    if downstream:
        head = 'А. Санаторий у нижнего озера, под плотиной — видна вся стена (рекомендую)'
        body = (f'Стена {DAM_H:.0f} м — ≈ {top_deg - bot_deg:.0f}° по высоте (четверть кадра), гребень ≈ {wid:.0f}° из 80° по ширине. '
                f'Здание ГЭС у подошвы (45 × 300 м) рядом со стеной — сарай.')
        body2 = 'Мир «Вертолёта» меняется: санаторий переезжает с водохранилища на нижнее озеро (как Майнское под Саяно-Шушенской).'
    else:
        head = 'Б. Санаторий на водохранилище, как в мире «Вертолёта», — вода сработана'
        body = (f'Над водой ≈ {LOW_FREE:.0f} м верхней грани — ≈ {top_deg - bot_deg:.0f}° по высоте; светлая «ванна» на скалах показывает, '
                f'сколько воды ушло. При полной воде над озером торчал бы только гребень.')
        body2 = 'Мир «Вертолёта» не меняется; ощущения «мега» меньше — стена длинная, но низкая.'
    d.text((20, cy), head, font=font(17, True), fill=INK)
    d.text((20, cy + 26), body, font=font(14), fill=(60, 62, 66))
    d.text((20, cy + 48), body2, font=font(14), fill=(60, 62, 66))

img.save(OUT)
print(f'вид на плотину: {OUT.relative_to(ROOT)} · {img.size[0]}×{img.size[1]}')
