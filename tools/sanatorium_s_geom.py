# -*- coding: utf-8 -*-
"""Жилой S-корпус санатория — геометрия, общая для схемы участка и листа корпуса.

Замысел владельца 2026-11-07 (картинка — референсы/sanatorium/s_corps_owner_2026-11-07.webp, в git не входит):
корпус — две полудуги, соединённые краями, сплошной двухэтажной лентой из номеров; номер по внутренним стенам
около 6 × 10 м, свой вход с улицы, 2 этажа; 10 м вдоль фасада, 6 м поперёк ленты (подтверждено владельцем,
как на картинке: фасад широкий, корпус неглубокий). Остальные числа — предложение агента.

v02 (владелец 2026-11-07, после прогулки по серому блокауту: «очень тесные номера»): весь номер × 1,3 по правилу
масштаба E — 13 × 7,8 м по внутренним стенам, терраса и балкон тоже × 1,3. Лестница, марши, двери и потолок уже были
по правилу E и не меняются. Разбивка номера (UNIT_*) — лист номера v01 × 1,3; её берут лист корпуса
(tools/sanatorium_s_corps_plan.py) и блокаут (tools/build_sanatorium.py).

Координаты: x — на восток, y — на север, метры; углы — в градусах от +x против часовой.
"""
import math

K = 1.3                # номер × 1,3 по правилу E (решение владельца v02)
UNIT_LEN = 10.0 * K   # номер вдоль фасада по внутренним стенам (по оси ленты) — 13 м
UNIT_DEPTH = 6.0 * K  # номер поперёк ленты: от фасада входа до фасада террасы — 7,8 м
PARTY_WALL = 0.3      # стена между номерами (несущая, между квартирами)
FACADE = 0.4          # наружная стена: витраж в раме или глухая часть в доске
HALF_T = UNIT_DEPTH / 2 + FACADE            # от оси ленты до наружной грани
UNITS_HALF = 7                              # номеров в полудуге (решение владельца); крыша недоступна, корпус на одном уровне
R = UNITS_HALF * (UNIT_LEN + PARTY_WALL) / math.pi   # радиус оси ленты, ≈ 29,6 м
STAIR_W = 2.45        # лестница у стены номера — над ней фасад глухой, в доске (как на картинке)
TERRACE = 3.0 * K     # терраса первого этажа — 3,9 м
BALCONY = 1.5 * K     # балкон второго этажа — 1,95 м
PATH_W = 3.0          # мощёная дорожка вдоль фасада входа
FLOOR_CLEAR = 3.1     # потолок в чистоте (2,7 × 1,15 по правилу масштаба E)
SLAB = 0.3
STEP_RISE, STEP_RUN = 0.17, 0.28            # ступени 1:1
FLIGHT_W = 1.17       # марш 0,9 × 1,3
DOOR_W, DOOR_H = 1.17, 2.42                 # входная дверь 0,9 × 2,1 по правилу E
INNER_DOOR_W = 1.04   # межкомнатная 0,8 × 1,3

# ---- разбивка номера: u — вдоль фасада от лестничной стены (0…UNIT_LEN), v — от фасада входа (0) к террасе (UNIT_DEPTH)
STAIR_V0 = 1.2 * K                          # площадка у входа, начало марша 1
FLIGHT_RUN = 9 * STEP_RUN                   # марш: 10 подъёмов, 9 проступей
LANDING_V1 = STAIR_V0 + FLIGHT_RUN + FLIGHT_W   # конец разворотной площадки
CLOSET_V = LANDING_V1 + 0.05                # стенка шкафа (1 этаж) и гардероба (2 этаж) за лестницей
UTIL_V = 2.6 * K                            # глубина полосы санузла и кухни (1 этаж), кабинета и ванной (2 этаж)
WC_U = (5.0 * K, 7.4 * K)                   # санузел между прихожей и кухней
WC_DOOR_V = (1.35 * K, 1.35 * K + INNER_DOOR_W)
ENTRY_DOOR_U = (3.0 * K, 3.0 * K + DOOR_W)  # дверь с улицы
SLIDE_DOOR_U = (5.2 * K, 7.6 * K)           # раздвижная на террасу и на балкон
HALL_U = STAIR_W + 1.3                      # холл 2 этажа — полоса 1,3 м вдоль проёма лестницы (1,0 × 1,3)
CAB_DOOR_V = (0.8 * K, 0.8 * K + INNER_DOOR_W)
BED_DOOR_V = (3.2 * K, 3.2 * K + INNER_DOOR_W)
BATH_U = 6.9 * K                            # стенка между кабинетом и ванной
BATH_DOOR_U = (8.0 * K, 8.0 * K + INNER_DOOR_W)
# перегородки этажей (u0, v0, u1, v1) и проёмы межкомнатных дверей в них
UNIT_WALLS = {
    1: [(STAIR_W, STAIR_V0, STAIR_W, CLOSET_V), (0.0, CLOSET_V, STAIR_W, CLOSET_V),
        (WC_U[0], 0.0, WC_U[0], WC_DOOR_V[0]), (WC_U[0], WC_DOOR_V[1], WC_U[0], UTIL_V),
        (WC_U[0], UTIL_V, WC_U[1], UTIL_V), (WC_U[1], 0.0, WC_U[1], UTIL_V)],
    2: [(0.0, CLOSET_V, STAIR_W, CLOSET_V),
        (HALL_U, 0.0, HALL_U, CAB_DOOR_V[0]), (HALL_U, CAB_DOOR_V[1], HALL_U, BED_DOOR_V[0]),
        (HALL_U, BED_DOOR_V[1], HALL_U, UNIT_DEPTH),
        (HALL_U, UTIL_V, BATH_DOOR_U[0], UTIL_V), (BATH_DOOR_U[1], UTIL_V, UNIT_LEN, UTIL_V),
        (BATH_U, 0.0, BATH_U, UTIL_V)],
}
UNIT_DOORS = {
    1: [(WC_U[0], WC_DOOR_V[0], WC_U[0], WC_DOOR_V[1])],
    2: [(HALL_U, CAB_DOOR_V[0], HALL_U, CAB_DOOR_V[1]), (HALL_U, BED_DOOR_V[0], HALL_U, BED_DOOR_V[1]),
        (BATH_DOOR_U[0], UTIL_V, BATH_DOOR_U[1], UTIL_V)],
}
# помещения: код → (название, середина u, v) — подписи листа и точки обхода блокаута
UNIT_ROOMS = {
    1: {'HAL': ('прихожая', (STAIR_W + WC_U[0]) / 2, UTIL_V / 2), 'WC': ('санузел', sum(WC_U) / 2, UTIL_V / 2),
        'KIT': ('кухня', (WC_U[1] + UNIT_LEN) / 2, UTIL_V / 2),
        'LIV': ('гостиная-столовая', (STAIR_W + UNIT_LEN) / 2, (UTIL_V + UNIT_DEPTH) / 2),
        'CLO': ('шкаф', STAIR_W / 2, (CLOSET_V + UNIT_DEPTH) / 2)},
    2: {'HL2': ('холл', (STAIR_W + HALL_U) / 2, UTIL_V), 'CAB': ('кабинет', (HALL_U + BATH_U) / 2, UTIL_V / 2),
        'BTH': ('ванная', (BATH_U + UNIT_LEN) / 2, UTIL_V / 2),
        'BED': ('спальня', (HALL_U + UNIT_LEN) / 2, (UTIL_V + UNIT_DEPTH) / 2),
        'WRD': ('гардероб', STAIR_W / 2, (CLOSET_V + UNIT_DEPTH) / 2)},
}


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
