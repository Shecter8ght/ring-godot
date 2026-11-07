# -*- coding: utf-8 -*-
"""Санаторий — лист жилого S-корпуса v01 по картинке владельца 2026-11-07 (docs/design/sanatorium_s_corps.md).

Корпус — две полудуги, соединённые краями, сплошной двухэтажной лентой из 14 номеров; номер 10 × 6 м по внутренним
стенам, 2 этажа, свой вход с улицы. На листе: план корпуса С-1 с парковкой, номер — 1 и 2 этаж, разрез поперёк ленты.
Геометрия — tools/sanatorium_s_geom.py (та же, что на схеме участка).

    python -X utf8 tools/sanatorium_s_corps_plan.py   → docs/plans/sanatorium_s_corps_v01.png
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import sanatorium_s_geom as sg

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/plans/sanatorium_s_corps_v01.png'

W, H = 2060, 1400
PAPER = (247, 245, 239)
INK = (40, 42, 46)
MUTED = (110, 112, 118)
UNIT_C = (226, 234, 242)
UNIT_C2 = (210, 222, 234)
WOOD_C = (150, 110, 70)
DECK_C = (222, 198, 160)
PAVE_C = (218, 210, 196)
GRASS_C = (214, 226, 196)
GLASS_C = (120, 170, 210)
PARK_C = (190, 190, 186)
CAR_C = (96, 100, 112)
DOOR_C = (200, 60, 40)
TREE_C = (88, 118, 84)
ROCK_C = (168, 166, 160)

img = Image.new('RGB', (W, H), PAPER)
d = ImageDraw.Draw(img)


def font(size, bold=False):
    return ImageFont.truetype(f'C:/Windows/Fonts/{"arialbd" if bold else "arial"}.ttf', size)


class View:
    """Окно чертежа: метры → пиксели (y вверх)."""

    def __init__(self, x0, y0, xmin, ymax, scale):
        self.x0, self.y0, self.xmin, self.ymax, self.s = x0, y0, xmin, ymax, scale

    def p(self, x, y):
        return (self.x0 + (x - self.xmin) * self.s, self.y0 + (self.ymax - y) * self.s)

    def poly(self, pts, fill=None, outline=INK, width=1):
        d.polygon([self.p(*q) for q in pts], fill=fill, outline=outline, width=width)

    def rect(self, x0, y0, x1, y1, fill=None, outline=INK, width=1):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, outline, width)

    def line(self, pts, color=INK, width=1, dash=None):
        q = [self.p(*t) for t in pts]
        if not dash:
            d.line(q, fill=color, width=width)
            return
        on, off = dash
        for a, b in zip(q, q[1:]):
            n = math.dist(a, b)
            t = 0.0
            while t < n:
                t1 = min(t + on, n)
                d.line([(a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n),
                        (a[0] + (b[0] - a[0]) * t1 / n, a[1] + (b[1] - a[1]) * t1 / n)], fill=color, width=width)
                t = t1 + off

    def circle(self, x, y, r, fill=None, outline=INK, width=1):
        (ax, ay), (bx, by) = self.p(x - r, y + r), self.p(x + r, y - r)
        d.ellipse([ax, ay, bx, by], fill=fill, outline=outline, width=width)

    def text(self, x, y, s, size=13, color=INK, bold=False, anchor='mm'):
        d.text(self.p(x, y), s, font=font(size, bold), fill=color, anchor=anchor)


def title(x, y, s, size=18):
    d.text((x, y), s, font=font(size, True), fill=INK)


title(30, 18, 'Санаторий · жилой S-корпус v01 — по картинке владельца 2026-11-07 · две полудуги, соединённые краями,'
      ' 14 номеров по 2 этажа', 22)

# ================================================================ A. План корпуса С-1 и парковки
OX, OY = -52.0, 140.0
A = View(30, 120, -96.0, 196.0, 6.4)
title(30, 70, 'А. Корпус С-1 («S») и парковка между корпусами', 17)
d.text((30, 96), '1 этаж; пунктир — край балконов 2 этажа; С-2 — зеркально справа от парковки', font=font(13), fill=MUTED)
A.rect(-96, 80, 2, 196, fill=GRASS_C, outline=None)
rng = random.Random(5)

# парковка (половина ширины к С-2 — до проезда и второго ряда) и тротуары
LX0, LY0 = -19.6, 114.0
A.rect(LX0, LY0, LX0 + sg.TERRACE * 0 + 17.8, LY0 + 57.0, fill=PARK_C, outline=MUTED)
for k in range(20):
    for xa, xb in ((LX0, LX0 + 5.0), (LX0 + 12.8, LX0 + 17.8)):
        A.line([(xa, LY0 + k * 2.5), (xb, LY0 + k * 2.5)], color=(150, 150, 146))
        if rng.random() < 0.35:
            A.rect(xa + 0.4, LY0 + k * 2.5 + 0.35, xb - 0.4, LY0 + (k + 1) * 2.5 - 0.35, fill=CAR_C, outline=None)
A.text(LX0 + 8.9, LY0 + 28.5, 'P · 40', 15, MUTED, True)
A.text(LX0 + 8.9, LY0 + 60.5, 'к служебной дороге ↑', 12, MUTED)
A.rect(LX0 - 3.0, LY0 - 6, LX0, LY0 + 57, fill=PAVE_C, outline=None)

halves = sg.halves(OX, OY, False)
# дорожки вдоль фасада входа, террасы, газон дворов
for cx, cy, a0, a1, ent_inner in halves:
    r_ent, r_ter = sg.face_r(ent_inner, True), sg.face_r(ent_inner, False)
    s_ = 1.0 if r_ent > sg.R else -1.0
    A.poly(sg.ring_seg(cx, cy, r_ent, r_ent + s_ * sg.PATH_W, a0, a1, 2.0), fill=PAVE_C, outline=None)
    A.poly(sg.ring_seg(cx, cy, r_ter, r_ter - s_ * sg.TERRACE, a0, a1, 2.0), fill=DECK_C, outline=None)
    # фонари-столбики вдоль дорожки
    r_l = r_ent + s_ * (sg.PATH_W + 0.6)
    n_l = int(abs(a1 - a0) * math.pi / 180 * r_l / 8.0)
    for i in range(n_l + 1):
        a = math.radians(a0 + (a1 - a0) * i / n_l)
        A.circle(cx + r_l * math.cos(a), cy + r_l * math.sin(a), 0.35, fill=(240, 190, 80), outline=None)
# связки с парковкой
for xa, xb, y in ((LX0 - 3.0, OX + sg.R - sg.HALF_T - sg.PATH_W, OY + sg.R),
                  (LX0 - 3.0, OX + sg.R + sg.HALF_T + sg.PATH_W - 0.5, OY - sg.R)):
    A.rect(min(xa, xb), y - 1.5, max(xa, xb), y + 1.5, fill=PAVE_C, outline=None)
# дворы: ели и сосны, валуны (владелец: деревья только хвойные)
for cx, cy, r_in, a_c in ((OX, OY + sg.R, sg.R - sg.HALF_T - sg.PATH_W - 1.0, 0.0),
                          (OX, OY - sg.R, sg.R - sg.HALF_T - sg.TERRACE - 1.0, 180.0)):
    for _ in range(9):
        a = math.radians(a_c + rng.uniform(-70, 70))
        r = rng.uniform(8.0, r_in - 2.0)
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        if rng.random() < 0.6:
            A.circle(x, y, rng.uniform(1.6, 2.4), fill=TREE_C, outline=None)
        else:
            A.circle(x, y, rng.uniform(0.6, 1.1), fill=ROCK_C, outline=MUTED)
    # дорожка-ступени через газон к террасам / к двору
    A.line([(cx + 3 * math.cos(math.radians(a_c)), cy), (cx + (r_in - 1) * math.cos(math.radians(a_c)), cy)],
           color=PAVE_C, width=6, dash=(6, 4))
for _ in range(26):     # ели и сосны вокруг корпуса
    x, y = rng.uniform(-94, -2), rng.uniform(82, 194)
    near = min(abs(math.hypot(x - cx, y - cy) - sg.R) if (math.degrees(math.atan2(y - cy, x - cx)) - min(a0, a1)) % 360
               <= abs(a1 - a0) else 99 for cx, cy, a0, a1, _ in halves)
    inside_lot = LX0 - 4 <= x <= LX0 + 18 and LY0 - 7 <= y <= LY0 + 58
    in_yard = any(math.hypot(x - cx, y - cy) < sg.R for cx, cy, *_ in halves)
    if near > sg.HALF_T + sg.TERRACE + 3.5 and not inside_lot and not in_yard:
        A.circle(x, y, rng.uniform(1.8, 2.6), fill=TREE_C, outline=None)

# номера: лента, глухая зона над лестницей в доске, дверь, экраны террас, балконы 2 этажа
for u in sg.units(OX, OY, False):
    cx, cy, a0, a1 = u['cx'], u['cy'], u['a0'], u['a1']
    A.poly(sg.ring_seg(cx, cy, sg.R - sg.HALF_T, sg.R + sg.HALF_T, a0, a1, 1.5),
           fill=UNIT_C if u['n'] % 2 else UNIT_C2, outline=INK, width=2)
    sa = sg.stair_angle(u)
    A.poly(sg.ring_seg(cx, cy, sg.R - sg.HALF_T, sg.R + sg.HALF_T, a0, a0 + sa, 1.0), fill=WOOD_C, outline=None)
    r_ent, r_ter = sg.face_r(u['entrance_inner'], True), sg.face_r(u['entrance_inner'], False)
    s_ = 1.0 if r_ent > sg.R else -1.0
    # дверь: сразу за глухой зоной
    da = math.degrees(sg.DOOR_W / sg.R) * (1 if a1 > a0 else -1)
    door = sg.arc(cx, cy, r_ent, a0 + sa * 1.22, a0 + sa * 1.22 + da, 1.0)
    A.line(door, color=DOOR_C, width=5)
    # экраны террасы по стенам номеров и балкон 2 этажа
    for a in (a0, a1):
        ar = math.radians(a)
        A.line([(cx + r_ter * math.cos(ar), cy + r_ter * math.sin(ar)),
                (cx + (r_ter - s_ * 2.2) * math.cos(ar), cy + (r_ter - s_ * 2.2) * math.sin(ar))], color=WOOD_C, width=4)
    A.line(sg.arc(cx, cy, r_ter - s_ * sg.BALCONY, a0, a1, 1.5), color=INK, width=1, dash=(5, 4))
    am = math.radians((a0 + a1) / 2)
    A.text(cx + sg.R * math.cos(am), cy + sg.R * math.sin(am), str(u['n']), 13, INK, True)
for cx, cy, a0, a1, _ in halves:   # стык полудуг и торцы
    for a in (a0, a1):
        ar = math.radians(a)
        A.line([(cx + (sg.R - sg.HALF_T) * math.cos(ar), cy + (sg.R - sg.HALF_T) * math.sin(ar)),
                (cx + (sg.R + sg.HALF_T) * math.cos(ar), cy + (sg.R + sg.HALF_T) * math.sin(ar))], color=INK, width=4)
# размеры и подписи
A.line([(OX, OY + sg.R), (OX - sg.R * math.cos(math.radians(35)), OY + sg.R + sg.R * math.sin(math.radians(35)))], color=MUTED)
A.text(OX + 1.5, OY + sg.R + 3.5, f'R {sg.R:.1f} м по оси'.replace('.', ','), 12, MUTED, False, 'lm')
A.text(OX, OY + sg.R, 'двор', 13, MUTED)
A.text(OX - 2, OY - sg.R, 'двор к озеру', 13, MUTED)
A.text(-92, 192, 'С', 15, INK, True)
A.line([(-92, 186), (-92, 189.5)], width=3)
for k in range(0, 21, 5):
    A.line([(-90 + k, 84), (-90 + k, 85.2)], width=2)
A.line([(-90, 84), (-70, 84)], width=2)
A.text(-80, 86.8, '20 м', 12)
A.text(-46, 84, 'к озеру ←   склон', 12, MUTED)

LEG = [(UNIT_C, 'номер (1 и 2 этаж), цифра — его номер в корпусе'),
       (WOOD_C, 'глухая часть фасада над лестницей, в доске; экраны террас'),
       (DOOR_C, 'входная дверь с улицы'), (PAVE_C, 'мощёная дорожка вдоль входов, 3 м'), (DECK_C, 'терраса 1 этажа, 3 м'),
       (None, 'пунктир — край балкона 2 этажа (1,5 м)'), ((240, 190, 80), 'фонари-столбики'), (TREE_C, 'ели и сосны'),
       (ROCK_C, 'валуны'), (CAR_C, 'брошенные машины на парковке')]
ly = 890
for c, s_ in LEG:
    if c:
        d.rectangle([30, ly + 2, 52, ly + 18], fill=c, outline=INK)
    else:
        d.line([(30, ly + 10), (52, ly + 10)], fill=INK, width=1)
    d.text((62, ly + 2), s_, font=font(14), fill=INK)
    ly += 25

# ================================================================ Б, В. Номер: 1 и 2 этаж (план развёрнут в прямоугольник)
S_U = 44.0


def unit_frame(V, floor):
    """Стены номера: фасад входа внизу (y = 0), фасад террас вверху (y = 6), стены соседей слева и справа."""
    L, D, F, PW, SW = sg.UNIT_LEN, sg.UNIT_DEPTH, sg.FACADE, sg.PARTY_WALL, sg.STAIR_W
    V.rect(-PW, -F, L + PW, D + F, fill=(250, 250, 248), outline=None)
    V.rect(-PW, -F, 0, D + F, fill=(120, 120, 124), outline=INK)                  # стена соседа
    V.rect(L, -F, L + PW, D + F, fill=(120, 120, 124), outline=INK)
    for y0, y1 in ((-F, 0), (D, D + F)):
        V.rect(0, y0, SW, y1, fill=WOOD_C, outline=INK)                          # глухая часть в доске (над лестницей)
        V.rect(SW, y0, L, y1, fill=(214, 232, 246), outline=INK)                 # витраж
        for x in range(3, 10, 2):
            V.line([(x + 0.0, y0), (x + 0.0, y1)], color=GLASS_C)


def partition(V, pts):
    V.line(pts, color=INK, width=4)


def door_arc(V, x, y, w, ang0, hinge_left=True):
    """Дверь: полотно и дуга открывания (план)."""
    a = math.radians(ang0)
    hx, hy = (x, y) if hinge_left else (x + w * math.cos(a), y + w * math.sin(a))
    V.line([(hx, hy), (hx + w * math.cos(a + math.pi / 2 * (1 if hinge_left else -1)),
                       hy + w * math.sin(a + math.pi / 2 * (1 if hinge_left else -1)))], color=INK, width=2)


def stair(V, upper):
    """П-образная лестница у стены: марш 1 у прихожей вверх к террасе, площадка, марш 2 обратно ко входу."""
    n = sg.RISERS // 2 - 1                       # проступей в марше
    y0, y1 = 1.2, 1.2 + n * sg.STEP_RUN
    xa0, xa1 = sg.STAIR_W - sg.FLIGHT_W, sg.STAIR_W   # марш 1 — у прихожей
    xb0, xb1 = 0.0, sg.FLIGHT_W                       # марш 2 — у стены
    for k in range(n + 1):
        yy = y0 + k * sg.STEP_RUN
        V.line([(xa0, yy), (xa1, yy)], color=MUTED if upper else INK, dash=(3, 3) if upper else None)
        V.line([(xb0, yy), (xb1, yy)], color=INK if upper else MUTED, dash=None if upper else (3, 3))
    V.rect(0, y1, sg.STAIR_W, y1 + sg.FLIGHT_W + 0.01, fill=None, outline=MUTED)
    V.line([(xa0 + 0.58, y0 + 0.2), (xa0 + 0.58, y1 - 0.2)], color=DOOR_C, width=2)
    V.text(xa0 + 0.58, y0 + 0.05, 'вверх', 11, DOOR_C, False, 'mt')
    if upper:
        V.line([(sg.STAIR_W, y0), (sg.STAIR_W, y1 + sg.FLIGHT_W)], color=INK, width=2)      # ограждение проёма
        V.line([(0, y0), (sg.STAIR_W, y0)], color=INK, width=1, dash=(4, 3))


def furniture_rect(V, x0, y0, x1, y1, label=None, size=11):
    V.rect(x0, y0, x1, y1, fill=(236, 236, 230), outline=MUTED)
    if label:
        V.text((x0 + x1) / 2, (y0 + y1) / 2, label, size, MUTED)


B = View(700, 150, -1.0, 10.6, S_U)
title(700, 70, 'Б. Номер, 1 этаж — 10 × 6 м по внутренним стенам (≈ 60 м²)', 17)
d.text((700, 96), 'внизу — фасад входа (улица), вверху — фасад террасы; на дуге номер — клин', font=font(13), fill=MUTED)
# улица, терраса
B.rect(-0.3, -3.4, 10.3, -0.4, fill=PAVE_C, outline=None)
B.text(5.0, -2.0, 'мощёная дорожка вдоль фасада входа — 3 м, фонари-столбики', 12, MUTED)
B.rect(-0.3, 6.4, 10.3, 9.4, fill=DECK_C, outline=None)
for x in (-0.3, 10.15):
    B.rect(x, 6.4, x + 0.15, 8.6, fill=WOOD_C, outline=None)       # экраны террасы — укрытие
unit_frame(B, 1)
stair(B, False)
partition(B, [(sg.STAIR_W, 1.2), (sg.STAIR_W, 4.9)])
partition(B, [(0, 4.9), (sg.STAIR_W, 4.9)])
partition(B, [(5.0, 0), (5.0, 2.6), (7.4, 2.6), (7.4, 0)])
# входная дверь, двери, раздвижная к террасе
B.rect(3.0, -0.4, 3.0 + sg.DOOR_W, 0, fill=(30, 30, 34), outline=None)
door_arc(B, 3.0, 0.0, sg.DOOR_W, 0.0)
door_arc(B, 5.0, 1.35, sg.INNER_DOOR_W, 90.0, False)
B.rect(5.2, 6.0, 7.6, 6.4, fill=(170, 210, 236), outline=DOOR_C, width=2)
B.text(6.4, 6.9, 'раздвижная', 11, DOOR_C)
# мебель и подписи
furniture_rect(B, 7.4, 0.0, 10.0, 0.65)
furniture_rect(B, 9.35, 0.65, 10.0, 2.2)
B.text(8.7, 1.6, 'кухня', 13, INK, True)
furniture_rect(B, 6.4, 0.1, 7.3, 1.0, 'душ', 10)
furniture_rect(B, 5.15, 0.15, 5.75, 0.85)
B.text(6.2, 1.9, 'с/у', 13, INK, True)
B.text(3.75, 1.5, 'прихожая', 13, INK, True)
B.text(1.2, 0.6, 'площадка', 11, MUTED)
furniture_rect(B, 3.0, 5.0, 5.4, 5.9, 'диван', 11)
furniture_rect(B, 7.6, 3.6, 9.4, 4.6, 'стол', 11)
B.text(5.0, 4.2, 'гостиная-столовая ≈ 26 м²', 13, INK, True)
B.text(1.2, 5.45, 'шкаф', 11, MUTED)
furniture_rect(B, 1.5, 7.2, 4.2, 8.1, 'диван', 11)
furniture_rect(B, 5.0, 7.3, 6.0, 8.0)
B.text(7.8, 7.9, 'терраса 3 м', 13, INK, True)
# размеры
for x0, x1, y, lab in ((0, 10, -4.0, '10,0'), (0, 2.45, 10.0, '2,45 лестница'), (2.45, 10, 10.0, '7,55')):
    B.line([(x0, y), (x1, y)], color=MUTED)
    B.line([(x0, y - 0.15), (x0, y + 0.15)], color=MUTED)
    B.line([(x1, y - 0.15), (x1, y + 0.15)], color=MUTED)
    B.text((x0 + x1) / 2, y + 0.25, lab, 12, MUTED, False, 'mb')
B.line([(10.8, 0), (10.8, 6)], color=MUTED)
B.text(10.95, 3.0, '6,0', 12, MUTED, False, 'lm')

C = View(1330, 150, -1.0, 10.6, S_U)
title(1330, 70, 'В. Номер, 2 этаж (≈ 60 м²)', 17)
d.text((1330, 96), 'над фасадом входа окна, над террасой — балкон 1,5 м со стеклянным ограждением', font=font(13), fill=MUTED)
C.rect(-0.3, 6.4, 10.3, 7.9, fill=DECK_C, outline=None)
C.line([(-0.3, 7.9), (10.3, 7.9)], color=GLASS_C, width=4)
for x in (-0.3, 10.15):
    C.rect(x, 6.4, x + 0.15, 7.9, fill=WOOD_C, outline=None)
unit_frame(C, 2)
stair(C, True)
HX = 3.75                                    # холл — полоса 1,3 м вдоль лестницы (1,0 × 1,3)
partition(C, [(0, 4.9), (sg.STAIR_W, 4.9)])
partition(C, [(HX, 0), (HX, 0.8)])
partition(C, [(HX, 0.8 + sg.INNER_DOOR_W), (HX, 3.2)])
partition(C, [(HX, 3.2 + sg.INNER_DOOR_W), (HX, 4.9)])
partition(C, [(HX, 2.6), (8.0, 2.6)])
partition(C, [(8.0 + sg.INNER_DOOR_W, 2.6), (10.0, 2.6)])
partition(C, [(6.9, 0), (6.9, 2.6)])
door_arc(C, HX, 0.8, sg.INNER_DOOR_W, 90.0, False)
door_arc(C, HX, 3.2, sg.INNER_DOOR_W, 90.0, False)
door_arc(C, 8.0, 2.6, sg.INNER_DOOR_W, 0.0)
C.rect(5.2, 6.0, 7.6, 6.4, fill=(170, 210, 236), outline=DOOR_C, width=2)
furniture_rect(C, 7.0, 0.1, 8.7, 0.85, 'ванна', 10)
furniture_rect(C, 9.2, 0.15, 9.85, 0.85)
C.text(8.45, 1.75, 'ванная', 13, INK, True)
C.text(3.1, 2.2, 'холл', 12, INK, True)
furniture_rect(C, 5.6, 0.1, 6.8, 0.75, 'стол', 10)
C.text(5.3, 1.6, 'кабинет ≈ 8 м²', 12, INK, True)
furniture_rect(C, 6.4, 3.4, 8.0, 5.4, 'кровать', 11)
C.text(5.1, 4.4, 'спальня', 13, INK, True)
C.text(5.1, 3.95, '≈ 21 м²', 12, INK)
C.text(1.85, 5.45, 'гардероб', 11, MUTED)
C.text(1.2, 0.6, 'площадка', 11, MUTED)
C.text(7.8, 7.15, 'балкон 1,5 м', 13, INK, True)

# ================================================================ Г. Разрез поперёк ленты
G = View(700, 900, -4.5, 9.2, 40.0)
title(700, 830, 'Г. Разрез поперёк корпуса — по гостиной и спальне', 17)
ff = sg.FLOOR_TO_FLOOR
F, D = sg.FACADE, sg.UNIT_DEPTH
G.rect(-4.5, -0.6, 11.2, 0, fill=(214, 206, 186), outline=None)       # земля
G.line([(-4.5, 0), (11.2, 0)], width=2)
G.rect(-3.4, -0.05, -0.4, 0.0, fill=PAVE_C, outline=None)
G.text(-1.9, -0.35, 'дорожка', 12, MUTED)
z0 = 0.15
for lv in range(2):
    zb = z0 + lv * ff
    G.rect(-F, zb - 0.3 if lv else zb - 0.15, D + F, zb, fill=(170, 170, 168), outline=INK)    # плита
    G.rect(-F, zb, 0, zb + sg.FLOOR_CLEAR, fill=(214, 232, 246), outline=INK)                 # фасад входа — витраж
    G.rect(D, zb, D + F, zb + sg.FLOOR_CLEAR, fill=(214, 232, 246), outline=INK)              # фасад террасы — витраж
    G.text(D / 2, zb + sg.FLOOR_CLEAR / 2, ('1 этаж: гостиная' if lv == 0 else '2 этаж: спальня') + f' · {sg.FLOOR_CLEAR:.1f} м'.replace('.', ','), 13)
zr = z0 + 2 * ff - sg.SLAB
G.rect(-F - 0.7, zr, D + F + 0.7, zr + 0.4, fill=(70, 72, 78), outline=INK)            # кровля, фальц, свесы
G.rect(2.6, zr + 0.4, 3.0, zr + 0.9, fill=(70, 72, 78), outline=None)                  # вентвыход
G.rect(D + F, z0 - 0.15, D + F + sg.TERRACE, z0, fill=DECK_C, outline=INK)            # терраса
G.rect(D + F, z0 + ff - 0.3, D + F + sg.BALCONY, z0 + ff, fill=(170, 170, 168), outline=INK)   # балкон
G.line([(D + F + sg.BALCONY, z0 + ff), (D + F + sg.BALCONY, z0 + ff + 1.1)], color=GLASS_C, width=4)
G.rect(D + F + sg.TERRACE - 0.1, z0, D + F + sg.TERRACE + 0.05, z0 + 1.8, fill=None, outline=None)
G.line([(-F - 0.15, z0 + 2.6), (-F - 0.15, z0 + 2.9)], color=(240, 190, 80), width=5)   # бра у двери
for z, lab in ((z0, f'+{z0:.2f}'), (z0 + ff, f'+{z0 + ff:.2f}'), (zr + 0.4, f'+{zr + 0.4:.2f} кровля')):
    G.line([(D + F + 3.2, z), (D + F + 3.6, z)], color=MUTED)
    G.text(D + F + 3.7, z, lab.replace('.', ','), 12, MUTED, False, 'lm')
G.text(D + F + 1.5, z0 + 0.5, 'терраса 3 м', 12)
G.text(D + F + 0.75, z0 + ff + 1.45, 'балкон', 12)
G.text(-2.2, z0 + 1.6, 'улица →', 12, MUTED)
G.text(-2.2, z0 + 1.15, 'вход', 12, MUTED)
G.text(D / 2, -0.35, f'6,0 + стены {F:.1f} × 2'.replace('.', ','), 12, MUTED)

# ================================================================ Д. Числа и замечания
notes = [
    ('Решения владельца', True),
    ('· две полудуги, соединённые краями; лента номеров, как на картинке', False),
    ('· 2 этажа на номер, номер ≈ 6 × 10 м по внутренним стенам', False),
    ('· у каждого номера свой вход с улицы', False),
    ('· парковка между корпусами — от машины к любому номеру', False),
    ('· деревья только ели и сосны (берёз с картинки нет)', False),
    ('Предложение агента', True),
    (f'· 7 номеров в полудуге, 14 в корпусе, 28 в двух; ось R {sg.R:.1f} м'.replace('.', ','), False),
    ('· номер 10 м вдоль фасада × 6 м в глубину (как на картинке:', False),
    ('  фасад широкий, корпус неглубокий); на дуге — клин 8,7…11,3 м', False),
    ('· вход — с той стороны ленты, что к парковке; терраса и балкон —', False),
    ('  с другой: у С-1 террасы смотрят на озеро и закат', False),
    (f'· потолок {sg.FLOOR_CLEAR} м, этаж {sg.FLOOR_TO_FLOOR:.1f} м, {sg.RISERS} подъёмов по {sg.STEP_RISE} м;'.replace('.', ','), False),
    (f'  дверь {sg.DOOR_W} × {sg.DOOR_H} м, марш {sg.FLIGHT_W} м (правило масштаба E)'.replace('.', ','), False),
    ('· над лестницей фасад глухой, в вертикальной доске — те самые', False),
    ('  деревянные пилоны картинки; остальное — витражи в пол', False),
    ('· кровля плоская, фальц, тёмная; торцы глухие, в доске', False),
    ('Для боя', True),
    ('· два входа в номер: дверь с улицы и раздвижная с террасы', False),
    ('· стекло бьётся (как витрины ТЦ); в части номеров шторы', False),
    ('  и жалюзи закрыты — иначе всё видно насквозь', False),
    ('· укрытия: деревянные пилоны, экраны террас, валуны, ели', False),
    ('· до любой двери от машины ≤ 60 м пешком', False),
]
ny = 830
for s, bold in notes:
    d.text((1430, ny), s, font=font(14 if not bold else 15, bold), fill=INK if bold else (60, 62, 66))
    ny += 21 if not bold else 24

img.save(OUT)
print(f'S-корпус: {OUT.relative_to(ROOT)} · R оси {sg.R:.2f} м · подъёмов {sg.RISERS} · {W}×{H}')
