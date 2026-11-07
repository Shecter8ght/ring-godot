# -*- coding: utf-8 -*-
"""Жилой S-корпус санатория — геометрия, общая для схемы участка и листа корпуса.

Замысел владельца 2026-11-07 (картинка — референсы/sanatorium/s_corps_owner_2026-11-07.webp, в git не входит):
корпус — две полудуги, соединённые краями, сплошной двухэтажной лентой из номеров; номер по внутренним стенам
около 6 × 10 м, свой вход с улицы, 2 этажа; 10 м вдоль фасада, 6 м поперёк ленты (подтверждено владельцем,
как на картинке: фасад широкий, корпус неглубокий). Остальные числа — предложение агента.

Координаты: x — на восток, y — на север, метры; углы — в градусах от +x против часовой.
"""
import math

UNIT_LEN = 10.0       # номер вдоль фасада по внутренним стенам (по оси ленты)
UNIT_DEPTH = 6.0      # номер поперёк ленты: от фасада входа до фасада террасы
PARTY_WALL = 0.3      # стена между номерами (несущая, между квартирами)
FACADE = 0.4          # наружная стена: витраж в раме или глухая часть в доске
HALF_T = UNIT_DEPTH / 2 + FACADE            # от оси ленты до наружной грани
UNITS_HALF = 7                              # номеров в полудуге (решение владельца); крыша недоступна, корпус на одном уровне
R = UNITS_HALF * (UNIT_LEN + PARTY_WALL) / math.pi   # радиус оси ленты, ≈ 23 м
STAIR_W = 2.45        # лестница у стены номера — над ней фасад глухой, в доске (как на картинке)
TERRACE = 3.0         # терраса первого этажа
BALCONY = 1.5         # балкон второго этажа
PATH_W = 3.0          # мощёная дорожка вдоль фасада входа
FLOOR_CLEAR = 3.1     # потолок в чистоте (2,7 × 1,15 по правилу масштаба E)
SLAB = 0.3
STEP_RISE, STEP_RUN = 0.17, 0.28            # ступени 1:1
FLIGHT_W = 1.17       # марш 0,9 × 1,3
DOOR_W, DOOR_H = 1.17, 2.42                 # входная дверь 0,9 × 2,1 по правилу E
INNER_DOOR_W = 1.04   # межкомнатная 0,8 × 1,3


def halves(ox, oy, mirror):
    """Две полудуги корпуса: (центр x, центр y, угол начала, угол конца, вход с вогнутой стороны).

    Корпус «S» (mirror=False): верхняя полудуга выгнута на запад, нижняя — на восток; «Ƨ» (mirror=True) — наоборот.
    Фасад входа — одна сплошная сторона ленты: у верхней полудуги вогнутая (двор раскрыт к парковке),
    у нижней — выпуклая (выгнута к парковке). Фасад террас — другая сторона.
    """
    top = (ox, oy + R, 90.0, -90.0 if mirror else 270.0, True)
    bottom = (ox, oy - R, 90.0, 270.0 if mirror else -90.0, False)
    return [top, bottom]


def arc(cx, cy, r, a0, a1, step=3.0):
    n = max(2, int(abs(a1 - a0) / step) + 1)
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / (n - 1))),
             cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / (n - 1)))) for i in range(n)]


def ring_seg(cx, cy, r0, r1, a0, a1, step=3.0):
    """Кольцевой сектор между радиусами r0 и r1 и углами a0…a1 — многоугольник."""
    return arc(cx, cy, r1, a0, a1, step) + arc(cx, cy, r0, a1, a0, step)


def face_r(entrance_inner, entrance):
    """Радиус наружной грани фасада входа (entrance=True) или фасада террас."""
    inner = entrance_inner if entrance else not entrance_inner
    return R - HALF_T if inner else R + HALF_T


def units(ox, oy, mirror):
    """Номера корпуса по порядку от северного торца к южному: словари с геометрией полудуги и углами номера."""
    out = []
    n = 0
    for h, (cx, cy, a0, a1, ent_inner) in enumerate(halves(ox, oy, mirror)):
        da = (a1 - a0) / UNITS_HALF
        for k in range(UNITS_HALF):
            n += 1
            out.append({'n': n, 'half': h, 'cx': cx, 'cy': cy, 'a0': a0 + k * da, 'a1': a0 + (k + 1) * da,
                        'entrance_inner': ent_inner})
    return out


def stair_angle(u):
    """Угловая ширина лестничной (глухой) зоны у начала номера."""
    return math.degrees(STAIR_W / R) * (1 if u['a1'] > u['a0'] else -1)


def extent(ox, oy, mirror, extra=TERRACE):
    """Габарит корпуса с террасами и дорожками: (xmin, xmax, ymin, ymax)."""
    xs, ys = [], []
    for cx, cy, a0, a1, _ in halves(ox, oy, mirror):
        for r in (R - HALF_T - extra, R + HALF_T + extra):
            for x, y in arc(cx, cy, r, a0, a1, 2.0):
                xs.append(x)
                ys.append(y)
    return min(xs), max(xs), min(ys), max(ys)


FLOOR_TO_FLOOR = FLOOR_CLEAR + SLAB
RISERS = round(FLOOR_TO_FLOOR / STEP_RISE)  # подъёмов на этаж
