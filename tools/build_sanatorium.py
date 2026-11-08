# -*- coding: utf-8 -*-
"""Карта «Санаторий» — серый блокаут для прогулки (docs/design/sanatorium_map.md, §7 п. 6).

Источники приняты владельцем 2026-11-07 (решения 1–48): схема участка v09 (tools/sanatorium_map_plan.py — берег,
бровка, дороги, парковки, коттеджи, каскад, тропа, места, выходы), S-корпуса (tools/sanatorium_s_geom.py, номер —
лист tools/sanatorium_s_corps_plan.py), здания по помещениям и дверям (docs/design/data/sanatorium_*.json; «Ресторан и спа» — v03 с бассейном 32,5 × 22 м), спуски
(sanatorium_descents_v01.json). Генератор ничего не придумывает в планировке: он поднимает принятые планы в объём.

Что считает:
- рельеф с шагом 1 м: озеро 0, набережная +2, пляж, склон 30 м, плато +32…+37, овраг на севере, скальный мыс на юге;
  площадки под зданиями (главный корпус и «Ресторан и спа» на +32, S-корпуса каждый на своём уровне, коттеджи,
  хоздвор), врезки под тропы и служебную дорогу, вал за рядами амфитеатра;
- стены по классу (docs/building_standards.md): фасад 0,5 (отдельные малые постройки 0,4), стены лестниц и коридоров
  0,3, перегородки 0,15; проёмы — по дверям JSON (дверь 1,17 × 2,42 по правилу E); витражи — стеклом;
- лестницы ступенями 1:1 (П-образные, прямая в коттедже, винтовая в маяке, каскад по уровням JSON на подпорных
  стенках с террасированным склоном), тропы лентой по профилю с подпорной крепью;
- мол «Стрелка» с павильоном-кофейней, маяком, киосками, колоннадой, ротондой и стенками; амфитеатр 10 рядов с
  проходами, променадом, колоннадой и уровнем под сценой; детская площадка, корты, хоздвор, парковки с машинами;
- только ели и сосны (те же точки, что на схеме); дальний силуэт плотины (стена 260 м в ~1,2 км на юго-западе), горы;
- обходы всех помещений, лестниц, каскада и троп — точки для проверки пешком (tools/sanatorium_study.gd -- verify).

    SANATORIUM_OUT=<папка> python -X utf8 tools/build_sanatorium.py
      → в <папка>, по тем же относительным путям: data/blockouts/sanatorium.json (план: объёмы, места, обходы и метки
        групп — к какой постройке или куску участка относится каждая запись), data/blockouts/sanatorium_vegetation.json,
        data/blockouts/sanatorium_terrain.json + data/terrain/sanatorium_heights.r32 и _splat.png (рельеф 1 м),
        data/blockouts/sanatorium_far_terrain.json + data/terrain/sanatorium_far.r32 и _far_splat.png (горы 10 м),
        scenes/levels/sanatorium_study.tscn.
    С 2026-11-08 карта правится руками в редакторе (docs/level_editing.md): в проект генератор не пишет. Разовый перенос
    в сцены сделал tools/sanatorium_to_scenes.tscn; новая постройка — собрать здесь в отдельную папку и перенести
    её сцену руками или тем же переносчиком в отдельный файл.

Координаты генератора — как на схеме: x на восток, y на север, z вверх, метры над уровнем озера. В Godot: X = x,
Y = z, Z = −y (север — −Z). Отступления от листов (двери, сдвинутые там, где лестница иначе не встаёт) — DEVIATIONS,
печатаются в конце и пишутся в план.
"""
import bisect
import contextlib
import io
import json
import math
import os
import random
import runpy
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))
import sanatorium_s_geom as sg  # noqa: E402

DATA = ROOT / 'docs/design/data'
# С 2026-11-08 карта правится руками в редакторе (решение владельца, docs/design/editable_levels.md): постройки,
# коробки, лестницы, деревья — сохранённые узлы сцен scenes/levels/sanatorium/, земля — кистью. Генератор в проект
# больше не пишет: SANATORIUM_OUT=<папка> — всё (план с метками групп, деревья, рельеф, сцена) в эту папку, по тем же
# относительным путям; оттуда берут заготовки (новая постройка) и переносчик tools/sanatorium_to_scenes.gd.
_OUT_ENV = os.environ.get('SANATORIUM_OUT', '')
if not _OUT_ENV:
    print('«Санаторий» правится руками в редакторе (docs/design/editable_levels.md): генератор не перезаписывает сцену\n'
          'и землю. Заготовки — в отдельную папку: SANATORIUM_OUT=<папка> python -X utf8 tools/build_sanatorium.py')
    sys.exit(1)
OUT_ROOT = Path(_OUT_ENV).resolve()
OUT_PLAN = OUT_ROOT / 'data/blockouts/sanatorium.json'
OUT_VEG = OUT_ROOT / 'data/blockouts/sanatorium_vegetation.json'
OUT_TER = OUT_ROOT / 'data/blockouts/sanatorium_terrain.json'
OUT_FAR = OUT_ROOT / 'data/blockouts/sanatorium_far_terrain.json'
OUT_SCENE = OUT_ROOT / 'scenes/levels/sanatorium_study.tscn'
TERRAIN_DIR = OUT_ROOT / 'data/terrain'
for _p in (OUT_PLAN, OUT_SCENE, TERRAIN_DIR / 'x'):
    _p.parent.mkdir(parents=True, exist_ok=True)

DEVIATIONS = []
WARN = []


def load_plan():
    """Схема участка исполняется как есть (её числа — единственный источник), без записи картинки."""
    import PIL.Image as PI
    save = PI.Image.save
    PI.Image.save = lambda self, *a, **k: None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            ns = runpy.run_path(str(TOOLS / 'sanatorium_map_plan.py'), run_name='sanatorium_plan_data')
    finally:
        PI.Image.save = save
    return ns


PLAN = load_plan()
shore_x = PLAN['shore_x']
brow_x = PLAN['brow_x']
MAIN = json.loads((DATA / 'sanatorium_main_corps_v03.json').read_text(encoding='utf-8'))   # v03 — корпус к S-корпусам
SPA = json.loads((DATA / 'sanatorium_spa_restaurant_v03.json').read_text(encoding='utf-8'))
SMALL = json.loads((DATA / 'sanatorium_small_v01.json').read_text(encoding='utf-8'))
DESC = json.loads((DATA / 'sanatorium_descents_v03.json').read_text(encoding='utf-8'))   # v03 — общая сеть троп по рельефу
DS = float(PLAN['DS'])                 # урез воды на DS западнее, чем в v10 (схема v11)
QUAY_W, BEACH_W = float(PLAN['QUAY_W']), float(PLAN['BEACH_W'])

# ---------------------------------------------------------------- числа блокаута
CENTRAL = 32.0          # главный корпус, «Ресторан и спа», парадная терраса (верх каскада — +32 по листу спусков)
DOOR_H = 2.42           # дверь 0,9 × 2,1 → 1,17 × 2,42 (правило E)
WIDE_DOOR_H = 2.8       # двустворчатые и ворота до 3,5 м
OPEN_W = 3.9            # проём шире — во всю высоту этажа (сцена, ворота бокса, переходы)
EXT_T = 0.5             # фасад
SMALL_EXT_T = 0.4       # отдельно стоящая малая постройка
STRUCT_T = 0.3          # лестница, коридор, между номерами
PART_T = 0.15           # перегородка
SLAB_T = 0.3
RAIL_H = 1.1
STEP = 1.0              # шаг рельефа
GRID_X = (-390.0, 190.0)
GRID_Y = (-300.0, 300.0)

# ---------------------------------------------------------------- вывод объёмов
MATS = []


def mat(name):
    if name not in MATS:
        MATS.append(name)
    return MATS.index(name)


def r3(v):
    return round(float(v), 3)


def gpt(x, y, z):
    """Точка схемы → Godot."""
    return [r3(x), r3(z), r3(-y)]


# ---- метки групп: к чему относится каждая запись вывода (перенос карты в сцены, docs/design/editable_levels.md)
# Явная метка — item() (постройка, беседка, валун, машина); без неё — раздел генератора, в котором запись выпущена:
# ближайший заголовок «# ====» / «# ----» над исполняемой строкой верхнего уровня этого файла.
_G = globals()
SECTIONS = []          # (номер строки, заголовок)
for _n, _l in enumerate(Path(__file__).read_text(encoding='utf-8').splitlines(), 1):
    if _l.startswith('# ====') or _l.startswith('# ----'):
        _t = _l.lstrip('#=- ').strip()
        if _t:
            SECTIONS.append((_n, _t))
SECTION_LINES = [s[0] for s in SECTIONS]
ITEM = [None]          # явная метка (id, заголовок)
ITEM_COUNT = {}
GROUP_TITLES = {}


def item(gid=None, title=None):
    ITEM[0] = None if gid is None else (gid, title or gid)


def item_next(prefix, title):
    ITEM_COUNT[prefix] = ITEM_COUNT.get(prefix, 0) + 1
    item(f'{prefix}{ITEM_COUNT[prefix]:02d}', f'{title} {ITEM_COUNT[prefix]}')


def cur_group():
    if ITEM[0] is not None:
        gid, title = ITEM[0]
    else:
        f = sys._getframe(1)
        while f is not None and not (f.f_code.co_name == '<module>' and f.f_globals is _G):
            f = f.f_back
        k = bisect.bisect_right(SECTION_LINES, f.f_lineno if f else 0) - 1
        gid, title = (f'sec{k:02d}', SECTIONS[k][1]) if k >= 0 else ('sec00', 'прочее')
    GROUP_TITLES.setdefault(gid, title)
    return gid


class TaggedList(list):
    """Список вывода, который помнит группу каждой добавленной записи (tags — параллельно)."""

    def __init__(self):
        super().__init__()
        self.tags = []

    def append(self, x):
        super().append(x)
        self.tags.append(cur_group())


class Out:
    def __init__(self):
        self.boxes = TaggedList()
        self.stairs = TaggedList()
        self.beams = TaggedList()
        self.cyls = TaggedList()
        self.tris = {}
        self.tri_tags = {}
        self.labels = TaggedList()
        self.water = TaggedList()
        self.barriers = TaggedList()
        self.markers = TaggedList()

    def box(self, x0, y0, x1, y1, z0, z1, m, solid=True):
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        if x1 - x0 < 0.005 or y1 - y0 < 0.005 or z1 - z0 < 0.005:
            return
        self.boxes.append([r3((x0 + x1) / 2), r3((z0 + z1) / 2), r3(-(y0 + y1) / 2), r3(x1 - x0), r3(z1 - z0), r3(y1 - y0),
                           0.0, mat(m), 1 if solid else 0])

    def obox(self, cx, cy, length, width, z0, z1, ang_deg, m, solid=True):
        """Повёрнутая коробка: длина — вдоль направления ang_deg (от +x против часовой), ширина — поперёк."""
        if length < 0.005 or width < 0.005 or z1 - z0 < 0.005:
            return
        self.boxes.append([r3(cx), r3((z0 + z1) / 2), r3(-cy), r3(length), r3(z1 - z0), r3(width), r3(ang_deg), mat(m),
                           1 if solid else 0])

    def seg(self, p, q, t, z0, z1, m, solid=True, ext=0.0):
        """Стенка по отрезку p → q толщиной t."""
        dx, dy = q[0] - p[0], q[1] - p[1]
        length = math.hypot(dx, dy)
        if length < 0.01:
            return
        self.obox((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, length + ext * 2, t, z0, z1, math.degrees(math.atan2(dy, dx)), m, solid)

    def stair(self, bottom, top, width, count, fill, m):
        """Марш: bottom/top — середина нижнего и верхнего края (x, y, z); fill — до какой отметки ступени сплошные
        (None — тонкий марш 0,3 под ступенью, винтовая лестница маяка)."""
        self.stairs.append([*gpt(*bottom), *gpt(*top), r3(width), int(count), None if fill is None else r3(fill), mat(m)])

    def beam(self, p, q, width, depth, m, solid=True):
        """Наклонная лента по осевой верха p → q (x, y, z), толщина depth вниз. Коробка наклонена вдоль ленты, её верх
        отстоит от оси на depth/2 по нормали — ось опускаем на depth/2 / cos(уклона), чтобы верх шёл ровно через p и q."""
        run = math.hypot(q[0] - p[0], q[1] - p[1])
        cos_ = run / max(math.dist(p, q), 1e-6)
        dz = depth / 2 / max(cos_, 0.2)
        self.beams.append([*gpt(p[0], p[1], p[2] - dz), *gpt(q[0], q[1], q[2] - dz), r3(width), r3(depth), mat(m),
                           1 if solid else 0])

    def cyl(self, cx, cy, z0, z1, r, m, solid=True, sides=16):
        self.cyls.append([r3(cx), r3(z0), r3(-cy), r3(r), r3(z1 - z0), mat(m), 1 if solid else 0, int(sides)])

    def tri(self, m, a, b, c, solid=False):
        mat(m)
        key = f'{m}|{1 if solid else 0}'
        self.tris.setdefault(key, []).extend([*gpt(*a), *gpt(*b), *gpt(*c)])
        self.tri_tags.setdefault(key, []).append(cur_group())

    def quad(self, m, a, b, c, d, solid=False):
        self.tri(m, a, b, c, solid)
        self.tri(m, a, c, d, solid)

    def label(self, x, y, z, text, size=1.0, kind='room'):
        self.labels.append([*gpt(x, y, z), text, r3(size), kind])

    def barrier(self, p, q, z0, z1):
        self.barriers.append([r3(p[0]), r3(-p[1]), r3(q[0]), r3(-q[1]), r3(z0), r3(z1)])


O = Out()

# ---------------------------------------------------------------- рельеф: природный
XS = np.arange(GRID_X[0], GRID_X[1] + STEP / 2, STEP)
YS = GRID_Y[1] - np.arange(0, GRID_Y[1] - GRID_Y[0] + STEP / 2, STEP)   # строки сверху вниз: север → юг (Godot z растёт)
GX, GY = np.meshgrid(XS, YS)


def shore_v(y):
    """То же, что shore_x схемы, для массивов."""
    y = np.asarray(y, dtype=float)
    return (-150.0 - DS + 7.0 * np.sin(y / 45.0) + 5.0 * np.sin(y / 17.0 + 1.0)
            + np.where(y < -215, 14.0, 0.0) * np.minimum(1.0, (-215 - y) / 30.0))


def brow_v(y):
    return shore_v(y) + DS + 20.0 + 42.0 + 6.0 * np.sin(np.asarray(y, dtype=float) / 70.0 + 0.5)


for _y in (-260.0, -133.0, 0.0, 77.0, 240.0):
    assert abs(float(shore_v(_y)) - shore_x(_y)) < 1e-9 and abs(float(brow_v(_y)) - brow_x(_y)) < 1e-9

EAST = PLAN['east']
NY = EAST[-1][1]
SY = PLAN['ys'][0]


def north_v(x):
    return NY + 7.0 * np.sin(np.asarray(x, dtype=float) / 23.0) + 4.0 * np.sin(np.asarray(x, dtype=float) / 9.0)


def south_v(x):
    x = np.asarray(x, dtype=float)
    return SY - 10.0 - 12.0 * np.exp(-((x + 90.0) / 60.0) ** 2) + 3.0 * np.sin(x / 13.0)


def smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


BEACH = tuple(PLAN['BEACH_Y'])


def natural(x, y):
    """Природный рельеф: озеро, набережная +2 со стенкой у воды, пляж, склон, плато, овраг, мыс."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    s = shore_v(y)
    b = brow_v(y)
    wb = np.clip((y - BEACH[0]) / 8.0, 0.0, 1.0) * np.clip((BEACH[1] - y) / 8.0, 0.0, 1.0)
    q = s + QUAY_W + (BEACH_W - QUAY_W) * wb          # подошва склона: набережная 30 м, пляж 42 м (v11)
    d_out = s - x
    lake_quay = -2.5 - 3.5 * np.clip(d_out / 20.0, 0.0, 1.0)
    lake_beach = np.maximum(-6.0, -0.09 * d_out)
    lake = lake_quay * (1 - wb) + lake_beach * wb
    quay = np.full_like(x, 2.0)
    beach = 2.0 * smooth((x - s) / 24.0)
    shore_zone = quay * (1 - wb) + beach * wb
    t = np.clip((x - q) / (b - q), 0.0, 1.0)
    slope = 2.0 + 30.0 * (0.7 * t + 0.3 * smooth(t))
    e = np.maximum(x - b, 0.0)
    und = (0.45 * np.sin(x / 41.0 + 0.7) * np.cos(y / 57.0 - 0.3) + 0.25 * np.sin((x + y) / 23.0)) * smooth(e / 30.0)
    plateau = 32.0 + np.minimum(5.2, 0.022 * e) + und
    h = np.where(x < s, lake, np.where(x < q, shore_zone, np.where(x < b, slope, plateau)))
    # овраг с ручьём на севере (за кромкой карты), скальный мыс на юге
    ny = north_v(x)
    h = h - np.where(x > s, 14.0 * smooth((y - ny - 2.0) / 30.0), 0.0)
    sy = south_v(x)
    rock = 9.0 * smooth((sy - 2.0 - y) / 22.0)
    h = np.where(x > s, h + rock, np.maximum(h, -6.0 + 15.0 * smooth((sy - 6.0 - y) / 30.0)))
    return h


# скала под подвесным подиумом открытого бассейна (владелец, v11): у бровки обрыв ≈ 13 м, ниже скальный откос, к
# набережной выемка сходит на нет; по краям по y — переход 10 м (не котлован, а скальный выступ склона)
ROCK_Y = (-102.0, -66.0)         # ядро по y
FACE_X = (-103.0, -110.0)        # верх и низ обрыва
ROCK_D = 10.0                    # глубина выемки под подиумом
ROCK_FADE = (-122.0, -152.0)     # от — до: выемка сходит на нет к набережной


def rock_carve(x, y, h):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    face = smooth((FACE_X[0] - x) / (FACE_X[0] - FACE_X[1]))
    fade = 1.0 - smooth((ROCK_FADE[0] - x) / (ROCK_FADE[0] - ROCK_FADE[1]))
    depth = ROCK_D * np.where(x > FACE_X[1], face, np.where(x > ROCK_FADE[0], 1.0, fade))
    w = smooth((y - (ROCK_Y[0] - 10.0)) / 10.0) * smooth(((ROCK_Y[1] + 10.0) - y) / 10.0) * (x > shore_v(y) + 2.0)
    out = h - depth * w
    return np.where((out < 2.2) & (h >= 2.2), 2.2, out)


H_NAT = natural(GX, GY)
H0 = rock_carve(GX, GY, H_NAT)
CARVE = H_NAT - H0               # глубина выемки скалы — для текстуры камня
H = H0.copy()


def grid_window(x0, y0, x1, y1, pad=0.0):
    """Индексы сетки, покрывающие прямоугольник схемы (с запасом)."""
    i0 = max(0, int(math.floor((x0 - pad - GRID_X[0]) / STEP)))
    i1 = min(len(XS) - 1, int(math.ceil((x1 + pad - GRID_X[0]) / STEP)))
    j0 = max(0, int(math.floor((GRID_Y[1] - (y1 + pad)) / STEP)))
    j1 = min(len(YS) - 1, int(math.ceil((GRID_Y[1] - (y0 - pad)) / STEP)))
    return slice(j0, j1 + 1), slice(i0, i1 + 1)


def h_at(x, y, field=None):
    """Высота рельефа в точке (билинейно)."""
    f = H if field is None else field
    fx = (x - GRID_X[0]) / STEP
    fy = (GRID_Y[1] - y) / STEP
    i = int(np.clip(math.floor(fx), 0, len(XS) - 2))
    j = int(np.clip(math.floor(fy), 0, len(YS) - 2))
    tx, ty = fx - i, fy - j
    a, b_, c, d = f[j, i], f[j, i + 1], f[j + 1, i], f[j + 1, i + 1]
    return float(a * (1 - tx) * (1 - ty) + b_ * tx * (1 - ty) + c * (1 - tx) * ty + d * tx * ty)


def rect_stat(x0, y0, x1, y1, field=None, fn=np.mean):
    f = H if field is None else field
    sj, si = grid_window(x0, y0, x1, y1)
    m = (GX[sj, si] >= x0 - 1e-6) & (GX[sj, si] <= x1 + 1e-6) & (GY[sj, si] >= y0 - 1e-6) & (GY[sj, si] <= y1 + 1e-6)
    vals = f[sj, si][m]
    if vals.size == 0:
        return h_at((x0 + x1) / 2, (y0 + y1) / 2, f)
    return float(fn(vals))


def pad_rect(x0, y0, x1, y1, level, blend=(10, 10, 10, 10)):
    """Площадка: внутри — уровень (число или (xa, la, xb, lb) — уклон по x), снаружи — переход к рельефу.
    blend — запас перехода с запада, юга, востока, севера, м."""
    bw, bs, be, bn = blend
    sj, si = grid_window(x0 - bw, y0 - bs, x1 + be, y1 + bn)
    X, Y = GX[sj, si], GY[sj, si]
    dx = np.where(X < x0, (x0 - X) / max(bw, 1e-3), np.where(X > x1, (X - x1) / max(be, 1e-3), 0.0))
    dy = np.where(Y < y0, (y0 - Y) / max(bs, 1e-3), np.where(Y > y1, (Y - y1) / max(bn, 1e-3), 0.0))
    w = 1.0 - np.clip(np.hypot(dx, dy), 0.0, 1.0)
    w = smooth(w) if True else w
    if isinstance(level, tuple):
        xa, la, xb, lb = level
        lv = la + (lb - la) * np.clip((X - xa) / (xb - xa), 0.0, 1.0)
    else:
        lv = level
    H[sj, si] = H[sj, si] * (1 - w) + lv * w


def pad_ring(cx, cy, r0, r1, a0, a1, level, blend):
    """Кольцевая площадка (вал за рядами амфитеатра): радиусы r0…r1, углы a0…a1 (град)."""
    sj, si = grid_window(cx - r1 - blend, cy - r1 - blend, cx + r1 + blend, cy + r1 + blend)
    X, Y = GX[sj, si], GY[sj, si]
    r = np.hypot(X - cx, Y - cy)
    a = np.degrees(np.arctan2(Y - cy, X - cx))
    dr = np.where(r > r1, r - r1, 0.0)
    da = np.where(a < a0, (a0 - a) * np.pi / 180 * r, np.where(a > a1, (a - a1) * np.pi / 180 * r, 0.0))
    # внутрь (к рядам и оркестре) — без перехода: там ряды и оркестра на своём уровне
    w = np.where(r < r0, 0.0, smooth(1.0 - np.clip(np.hypot(dr, da) / blend, 0.0, 1.0)))
    H[sj, si] = H[sj, si] * (1 - w) + level * w


RING_CLAMPS = []     # (cx, cy, r0, r1, a0, a1, top) — выемки под рядами амфитеатра


def apply_ring_clamps():
    for cx, cy, r0, r1, a0, a1, top in RING_CLAMPS:
        sj, si = grid_window(cx - r1 - 1, cy - r1 - 1, cx + r1 + 1, cy + r1 + 1)
        X, Y = GX[sj, si], GY[sj, si]
        r = np.hypot(X - cx, Y - cy)
        a = np.degrees(np.arctan2(Y - cy, X - cx))
        m = (r >= r0) & (r <= r1) & (a >= a0) & (a <= a1)
        H[sj, si] = np.where(m, np.minimum(H[sj, si], top), H[sj, si])


CLAMPS = []      # (x0, y0, x1, y1, max) — выемки под постройками, ступенями, чашами
RIBBONS = []     # ленты троп и дороги: точки (x, y, z), ширина — врезка в рельеф


def clamp_rect(x0, y0, x1, y1, top, inset=0.0):
    """Рельеф в прямоугольнике не выше top; inset > 0 — только строго внутри (узлы на кромке пола остаются на уровне
    площадки, порог двери без ступеньки)."""
    CLAMPS.append((min(x0, x1) + inset, min(y0, y1) + inset, max(x0, x1) - inset, max(y0, y1) - inset, top))


def apply_clamps():
    for x0, y0, x1, y1, top in CLAMPS:
        sj, si = grid_window(x0, y0, x1, y1)
        X, Y = GX[sj, si], GY[sj, si]
        m = (X >= x0 - 1e-6) & (X <= x1 + 1e-6) & (Y >= y0 - 1e-6) & (Y <= y1 + 1e-6)
        H[sj, si] = np.where(m, np.minimum(H[sj, si], top), H[sj, si])


def seg_dist(X, Y, a, b):
    ax, ay = a[0], a[1]
    dx, dy = b[0] - ax, b[1] - ay
    L2 = dx * dx + dy * dy + 1e-12
    t = np.clip(((X - ax) * dx + (Y - ay) * dy) / L2, 0.0, 1.0)
    return np.hypot(X - ax - dx * t, Y - ay - dy * t), t


def apply_ribbon_clamp(pts, half, margin, joins=(True, True)):
    """Под лентой рельеф не выше её низа: врезка на ширину + запас (по сетке 1 м треугольники под лентой целиком ниже).
    У первой и последней точки (там лента сходит на землю) рельеф не трогается в радиусе 2,5 м."""
    ends = [e for e, j in zip((pts[0], pts[-1]), joins) if j]
    for a, b in zip(pts, pts[1:]):
        x0, x1 = min(a[0], b[0]), max(a[0], b[0])
        y0, y1 = min(a[1], b[1]), max(a[1], b[1])
        sj, si = grid_window(x0, y0, x1, y1, half + margin + 1)
        X, Y = GX[sj, si], GY[sj, si]
        d, t = seg_dist(X, Y, a, b)
        z = a[2] + (b[2] - a[2]) * t
        m = d <= half + margin
        for e in ends:
            m &= np.hypot(X - e[0], Y - e[1]) > 2.5
        H[sj, si] = np.where(m, np.minimum(H[sj, si], z - 0.22), H[sj, si])


def apply_ribbon_bench(pts, half, blend):
    """Тропа врезана в склон (v03): по ширине тропы рельеф на её уровне — срезка сверху, подсыпка снизу, дальше
    плавно к склону. Ходят по самому рельефу, отдельного тела у тропы нет."""
    for a, b in zip(pts, pts[1:]):
        x0, x1 = min(a[0], b[0]), max(a[0], b[0])
        y0, y1 = min(a[1], b[1]), max(a[1], b[1])
        sj, si = grid_window(x0, y0, x1, y1, half + blend + 1)
        X, Y = GX[sj, si], GY[sj, si]
        d, t = seg_dist(X, Y, a, b)
        z = a[2] + (b[2] - a[2]) * t
        w = np.clip(1.0 - (d - half) / blend, 0.0, 1.0)
        w = w * w * (3.0 - 2.0 * w)
        H[sj, si] = H[sj, si] * (1.0 - w) + z * w


# ---------------------------------------------------------------- поверхности построек (для ступеней у дверей)
SURFACES = []    # ('rect', x0, y0, x1, y1, z) | ('poly', pts, z) — верх настилов, где рельеф ниже


def in_poly(x, y, pts):
    c = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            c = not c
        j = i
    return c


def ground_at(x, y):
    g = h_at(x, y)
    for rb in RIBBONS:
        for a, b in zip(rb['pts'], rb['pts'][1:]):
            d, t = seg_dist(np.array([x]), np.array([y]), a, b)
            if d[0] <= rb['w'] / 2:
                g = max(g, a[2] + (b[2] - a[2]) * float(t[0]))
    for s in SURFACES:
        if s[0] == 'rect':
            _, x0, y0, x1, y1, z = s
            if x0 <= x <= x1 and y0 <= y <= y1:
                g = max(g, z)
        elif in_poly(x, y, s[1]):
            g = max(g, s[2])
    return g


# ---------------------------------------------------------------- прямоугольники
def rect_minus(r, holes):
    """Прямоугольник без прямоугольников → список прямоугольников (x0, y0, x1, y1)."""
    out = [r]
    for h in holes:
        nxt = []
        for a in out:
            ix0, iy0 = max(a[0], h[0]), max(a[1], h[1])
            ix1, iy1 = min(a[2], h[2]), min(a[3], h[3])
            if ix0 >= ix1 - 1e-6 or iy0 >= iy1 - 1e-6:
                nxt.append(a)
                continue
            if a[1] < iy0 - 1e-6:
                nxt.append((a[0], a[1], a[2], iy0))
            if iy1 < a[3] - 1e-6:
                nxt.append((a[0], iy1, a[2], a[3]))
            if a[0] < ix0 - 1e-6:
                nxt.append((a[0], iy0, ix0, iy1))
            if ix1 < a[2] - 1e-6:
                nxt.append((ix1, iy0, a[2], iy1))
        out = nxt
    return out


def inter_len(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def sub_intervals(a, b, cuts):
    """Интервал [a, b] без интервалов cuts."""
    out = [(a, b)]
    for c0, c1 in sorted(cuts):
        nxt = []
        for p, q in out:
            if c1 <= p + 1e-6 or c0 >= q - 1e-6:
                nxt.append((p, q))
                continue
            if c0 > p + 1e-6:
                nxt.append((p, c0))
            if c1 < q - 1e-6:
                nxt.append((c1, q))
        out = nxt
    return [(p, q) for p, q in out if q - p > 0.02]


# ---------------------------------------------------------------- рамки лестниц (прямоугольная и дуга номера)
class RectFrame:
    """Местная система: a — вдоль марша от стены входа, b — поперёк. origin — точка (a=0, b=0), ea/eb — орты схемы."""

    def __init__(self, origin, ea, eb):
        self.o, self.ea, self.eb = origin, ea, eb

    def pt(self, a, b):
        return (self.o[0] + self.ea[0] * a + self.eb[0] * b, self.o[1] + self.ea[1] * a + self.eb[1] * b)

    def rect(self, a0, a1, b0, b1):
        p, q = self.pt(a0, b0), self.pt(a1, b1)
        return (min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1]))

    def box(self, a0, a1, b0, b1, z0, z1, m, solid=True):
        x0, y0, x1, y1 = self.rect(a0, a1, b0, b1)
        O.box(x0, y0, x1, y1, z0, z1, m, solid)

    def stair(self, a_bot, a_top, b_c, width, z_bot, z_top, count, fill, m):
        p, q = self.pt(a_bot, b_c), self.pt(a_top, b_c)
        O.stair((p[0], p[1], z_bot), (q[0], q[1], z_top), width, count, fill, m)


class ArcFrame:
    """Номер S-корпуса: b = u вдоль фасада от лестничной стены (0…10), a = v от фасада входа (0) к террасе (6);
    дуга полудуги разбита на хорды не длиннее 1,6 м."""

    def __init__(self, unit):
        self.u = unit

    def ang(self, u):
        a0, a1 = self.u['a0'], self.u['a1']
        return a0 + (a1 - a0) * (u + sg.PARTY_WALL / 2) / (sg.UNIT_LEN + sg.PARTY_WALL)

    def rad(self, v):
        return sg.R - sg.UNIT_DEPTH / 2 + v if self.u['entrance_inner'] else sg.R + sg.UNIT_DEPTH / 2 - v

    def pt(self, a, b):
        ang = math.radians(self.ang(b))
        r = self.rad(a)
        return (self.u['cx'] + r * math.cos(ang), self.u['cy'] + r * math.sin(ang))

    def box(self, a0, a1, b0, b1, z0, z1, m, solid=True):
        if b1 < b0:
            b0, b1 = b1, b0
        if a1 < a0:
            a0, a1 = a1, a0
        n = max(1, int(math.ceil((b1 - b0) / 1.6)))
        for k in range(n):
            u0 = b0 + (b1 - b0) * k / n
            u1 = b0 + (b1 - b0) * (k + 1) / n
            um, vm = (u0 + u1) / 2, (a0 + a1) / 2
            c = self.pt(vm, um)
            r = self.rad(vm)
            arc = abs(math.radians(self.ang(u1) - self.ang(u0))) * r
            tang = self.ang(um) + 90.0
            O.obox(c[0], c[1], arc + 0.03, a1 - a0, z0, z1, tang, m, solid)

    def stair(self, a_bot, a_top, b_c, width, z_bot, z_top, count, fill, m):
        p, q = self.pt(a_bot, b_c), self.pt(a_top, b_c)
        O.stair((p[0], p[1], z_bot), (q[0], q[1], z_top), width, count, fill, m)


def stair_u(F, a_len, b0, b1, e, z_lo, z_hi, first_low=True, rise=0.165, run=0.3, landing_min=1.17,
            mat_='stair', rail='rail', divider=True):
    """П-образная лестница в рамке F: площадка входа a ∈ [0, e] на обоих уровнях (на верхнем — плита), марш 1
    уходит от входа в половине b (first_low — нижней по b), разворотная площадка у дальней стены, марш 2
    возвращается к входу. Возвращает путь от середины площадки входа внизу до неё же наверху и плиты верхнего
    уровня (в рамке)."""
    n = max(4, int(round((z_hi - z_lo) / rise)))
    n1 = n // 2
    n2 = n - n1
    h = (z_hi - z_lo) / n
    z_mid = z_lo + n1 * h
    L1 = (n1 - 1) * run
    L2 = (n2 - 1) * run
    L = max(L1, L2)
    if e + L + landing_min > a_len + 1e-6:
        WARN.append(f'лестница: марш {L:.2f} + вход {e:.2f} не умещается в {a_len:.2f}')
    bm = (b0 + b1) / 2
    ha = (b0, bm) if first_low else (bm, b1)
    hb = (bm, b1) if first_low else (b0, bm)
    ca, cb = (ha[0] + ha[1]) / 2, (hb[0] + hb[1]) / 2
    wa, wb = ha[1] - ha[0], hb[1] - hb[0]
    F.stair(e, e + L1, ca, wa - 0.08, z_lo, z_mid, n1, z_lo - 0.05, mat_)
    F.box(e + L, a_len, b0, b1, z_lo - 0.05, z_mid, mat_)                       # разворотная площадка
    F.box(e + L1, e + L, ha[0], ha[1], z_lo - 0.05, z_mid, mat_)
    F.stair(e + L2, e, cb, wb - 0.08, z_mid, z_hi, n2, z_lo - 0.05, mat_)
    F.box(e + L2, e + L, hb[0], hb[1], z_lo - 0.05, z_mid, mat_)
    F.box(0, e, b0, b1, z_hi - SLAB_T, z_hi, 'slab')                              # площадка входа наверху
    F.box(e - 0.04, e + 0.04, ha[0], ha[1], z_hi, z_hi + RAIL_H, rail)           # перила над маршем 1
    if divider:
        F.box(e, e + L, bm - 0.06, bm + 0.06, z_lo, z_hi + RAIL_H, rail)         # стенка между маршами
    path = [(e / 2, ca, z_lo), (e + 0.35, ca, z_lo + h), (e + L1 - 0.3, ca, z_mid - h * 0.5),
            (e + L + (a_len - e - L) / 2, ca, z_mid), (e + L + (a_len - e - L) / 2, cb, z_mid),
            (e + L2 - 0.3, cb, z_mid + h * 0.5), (e + 0.35, cb, z_hi - h), (e / 2, cb, z_hi)]
    return {'path': [(*F.pt(a, b), z) for a, b, z in path], 'z_mid': z_mid, 'hub': (e / 2, (b0 + b1) / 2)}


# ---------------------------------------------------------------- здания по помещениям и дверям
ROOMS = TaggedList()       # для проверки: {uid, building, name, floor, at}
ROUTES = TaggedList()
BUILDINGS = []   # подписи и краткий счёт


def door_geom(d):
    """Дверь: линия ('h' — y = c, 'v' — x = c), интервал, середина, ширина."""
    o, c, a, b = d['wall'][0], float(d['wall'][1]), float(d['wall'][2]), float(d['wall'][3])
    mid = (a + b) / 2
    return o, c, a, b, ((mid, c) if o == 'h' else (c, mid))


def room_side(rect, o, c):
    """С какой стороны линии двери лежит помещение: +1 — в сторону роста координаты."""
    if o == 'h':
        return 1 if abs(rect[1] - c) < 0.06 else (-1 if abs(rect[3] - c) < 0.06 else (1 if (rect[1] + rect[3]) / 2 > c else -1))
    return 1 if abs(rect[0] - c) < 0.06 else (-1 if abs(rect[2] - c) < 0.06 else (1 if (rect[0] + rect[2]) / 2 > c else -1))


def off_pt(pt, o, side, dist):
    return (pt[0], pt[1] + side * dist) if o == 'h' else (pt[0] + side * dist, pt[1])


def seg_hits_rect(p, q, r):
    """Пересекает ли отрезок прямоугольник (Лианг — Барски)."""
    x0, y0, x1, y1 = r
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pv, qv in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if abs(pv) < 1e-12:
            if qv < 0:
                return False
            continue
        t = qv / pv
        if pv < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def route_in_room(p, q, obstacles):
    """Путь внутри помещения от p к q в обход препятствий (прямоугольники, уже с запасом) — по углам."""
    if not any(seg_hits_rect(p, q, r) for r in obstacles):
        return [q]
    nodes = [p, q]
    for x0, y0, x1, y1 in obstacles:
        nodes += [(x0 - 0.05, y0 - 0.05), (x1 + 0.05, y0 - 0.05), (x1 + 0.05, y1 + 0.05), (x0 - 0.05, y1 + 0.05)]
    n = len(nodes)
    dist = [math.inf] * n
    prev = [-1] * n
    dist[0] = 0.0
    done = [False] * n
    for _ in range(n):
        u = min((i for i in range(n) if not done[i]), key=lambda i: dist[i], default=None)
        if u is None or dist[u] == math.inf:
            break
        done[u] = True
        if u == 1:
            break
        for v in range(n):
            if done[v] or any(seg_hits_rect(nodes[u], nodes[v], r) for r in obstacles):
                continue
            nd = dist[u] + math.dist(nodes[u], nodes[v])
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
    if prev[1] < 0:
        WARN.append(f'путь в помещении не найден {p} → {q}')
        return [q]
    path = []
    k = 1
    while k > 0:
        path.append(nodes[k])
        k = prev[k]
    return list(reversed(path))


class Building:
    """Здание из помещений и дверей по этажам (координаты схемы). Стены — по рёбрам помещений: ребро с помещением
    с одной стороны — фасад, с двух — перегородка (у лестницы и коридора — 0,3); проёмы — по дверям."""

    def __init__(self, bid, title, floors, levels, heights, ext_t=EXT_T, glass=(), open_rooms=(), room_h=None,
                 mat_ext='facade', start_door=0, roof_mat='roof', label_at=None):
        self.bid, self.title = bid, title
        self.floors = floors                 # {f: {'rooms': [...], 'doors': [...]}}
        self.order = sorted(floors.keys())
        self.levels = levels                 # {f: отметка пола}
        self.heights = heights               # {f: высота этажа}
        self.ext_t = ext_t
        self.glass = set(glass)
        self.open_rooms = set(open_rooms)
        self.room_h = room_h or {}
        self.mat_ext = mat_ext
        self.roof_mat = roof_mat
        self.start_door = start_door
        self.stairs = {}                     # id → {'lo', 'hi', 'res'}
        self.slab_override = {}              # (f, id) → список прямоугольников плиты пола
        self.obstacles = {}                  # (f, id) → прямоугольники
        self.hubs = {}                       # (f, id) → точка
        self.basins = []                     # чаши бассейнов: (x0, y0, x1, y1)
        self.label_at = label_at
        self.ext_doors = []

    def room(self, f, rid):
        for r in self.floors[f]['rooms']:
            if r['id'] == rid:
                return r
        return None

    def rect(self, r):
        return tuple(float(v) for v in r['rect'])

    def hgt(self, f, r):
        return float(self.room_h.get(r['id'], self.heights[f]))

    def wall_t(self, ka, kb):
        return STRUCT_T if ('stair' in (ka, kb) or 'corr' in (ka, kb)) else PART_T

    def emit(self):
        for f in self.order:
            self._walls(f)
            self._slabs(f)
        self._labels()

    # ---- стены
    def _walls(self, f):
        rooms = self.floors[f]['rooms']
        z0 = self.levels[f]
        lines = {}
        for r in rooms:
            x0, y0, x1, y1 = self.rect(r)
            for o, c, a, b, side in (('h', y0, x0, x1, 1), ('h', y1, x0, x1, -1), ('v', x0, y0, y1, 1), ('v', x1, y0, y1, -1)):
                lines.setdefault((o, round(c, 3)), []).append((a, b, side, r))
        doors = {}
        for d in self.floors[f]['doors']:
            o, c, a, b, _ = door_geom(d)
            doors.setdefault((o, round(c, 3)), []).append((a, b, d))
        for (o, c), edges in lines.items():
            pts = sorted({e for a, b, _, _ in edges for e in (a, b)})
            pieces = []
            for p, q in zip(pts, pts[1:]):
                mid = (p + q) / 2
                plus = [r for a, b, s, r in edges if s == 1 and a - 1e-6 <= mid <= b + 1e-6]
                minus = [r for a, b, s, r in edges if s == -1 and a - 1e-6 <= mid <= b + 1e-6]
                rp = plus[0] if plus else None
                rm = minus[0] if minus else None
                pieces.append((p, q, self._wall_class(f, rp, rm)))
            # слить соседние одного класса
            merged = []
            for p, q, cls in pieces:
                if cls is None:
                    continue
                if merged and merged[-1][2] == cls and abs(merged[-1][1] - p) < 1e-6:
                    merged[-1] = (merged[-1][0], q, cls)
                else:
                    merged.append((p, q, cls))
            cuts = [(a, b) for a, b, _ in doors.get((o, c), [])]
            for p, q, cls in merged:
                kind, t, top, m = cls
                ext = t / 2 if kind != 'rail' else 0.0
                for s0, s1 in sub_intervals(p - ext, q + ext, cuts):
                    self._wall_box(o, c, s0, s1, t, z0, z0 + top if kind != 'rail' else z0 + RAIL_H, m)
            # перемычки над дверями
            for a, b, d in doors.get((o, c), []):
                w = b - a
                hmax = 0.0
                hmin = 1e9
                for a2, b2, _, r in edges:
                    if inter_len(a, b, a2, b2) > 0.01:
                        hmax = max(hmax, self.hgt(f, r))
                        hmin = min(hmin, self.hgt(f, r))
                # широкий проём — во всю высоту низкого из двух помещений; выше, до потолка высокого, — перемычка
                dh = DOOR_H if w < 2.0 else (WIDE_DOOR_H if w < OPEN_W else hmin)
                if hmax - dh > 0.05:
                    cls = None
                    for p, q, c2 in merged:
                        if inter_len(a, b, p, q) > 0.01:
                            cls = c2
                    if cls is None or cls[0] == 'rail':
                        continue
                    self._wall_box(o, c, a, b, cls[1], z0 + dh, z0 + hmax, cls[3])

    def _wall_class(self, f, rp, rm):
        """(вид, толщина, высота, материал) ребра или None."""
        if rp is None and rm is None:
            return None
        if rp is not None and rm is not None:
            if rp['id'] == rm['id']:
                return None
            vp, vm = rp['kind'] == 'void', rm['kind'] == 'void'
            if vp and vm:
                return None
            if vp or vm:
                return ('rail', 0.06, RAIL_H, 'glass')
            op, om = rp['id'] in self.open_rooms, rm['id'] in self.open_rooms
            if op and om:
                return None
            h = max(self.hgt(f, rp), self.hgt(f, rm))
            if op or om:
                closed = rm if op else rp
                return ('wall', self.ext_t, self.hgt(f, closed), self.mat_ext)
            t = self.wall_t(rp['kind'], rm['kind'])
            return ('wall', t, h, 'struct' if t > 0.2 else 'partition')
        r = rp if rp is not None else rm
        if r['id'] in self.open_rooms:
            return ('rail', 0.25, RAIL_H, 'parapet')
        m = 'glass' if r['id'] in self.glass else self.mat_ext
        return ('wall', self.ext_t, self.hgt(f, r), m)

    def _wall_box(self, o, c, s0, s1, t, z0, z1, m):
        if o == 'h':
            O.box(s0, c - t / 2, s1, c + t / 2, z0, z1, m)
        else:
            O.box(c - t / 2, s0, c + t / 2, s1, z0, z1, m)

    # ---- плиты, кровля, основание
    def _slabs(self, f):
        rooms = self.floors[f]['rooms']
        z0 = self.levels[f]
        idx = self.order.index(f)
        above = self.floors[self.order[idx + 1]]['rooms'] if idx + 1 < len(self.order) else []
        above_rects = [self.rect(r) for r in above]
        lowest = idx == 0
        for r in rooms:
            rect = self.rect(r)
            if r['kind'] != 'void':
                parts = self.slab_override.get((f, r['id']))
                if parts is None:
                    holes = [b for b in self.basins if inter_len(rect[0], rect[2], b[0], b[2]) > 0 and inter_len(rect[1], rect[3], b[1], b[3]) > 0]
                    stair_lo = r['id'] in self.stairs and self.stairs[r['id']]['lo'] != f and not lowest
                    parts = [] if stair_lo else rect_minus(rect, holes)
                for p in parts:
                    O.box(p[0], p[1], p[2], p[3], z0 - SLAB_T, z0, 'slab' if not lowest else 'floor')
                if lowest:
                    self._plinth(rect, z0 - SLAB_T)
            # кровля над тем, что не накрыто этажом выше
            if r['id'] in self.open_rooms:
                continue
            top = z0 + self.hgt(f, r)
            for p in rect_minus(rect, above_rects):
                O.box(p[0] - 0.1, p[1] - 0.1, p[2] + 0.1, p[3] + 0.1, top, top + 0.35, self.roof_mat)

    def _plinth(self, rect, top):
        low = rect_stat(*rect, fn=np.min)
        if low < top - 0.05:
            O.box(*rect, low - 0.6, top, 'plinth')

    def _labels(self):
        f0 = self.order[0]
        for f in self.order:
            for r in self.floors[f]['rooms']:
                if r['kind'] == 'void':
                    continue
                x0, y0, x1, y1 = self.rect(r)
                hub = self.hubs.get((f, r['id']), ((x0 + x1) / 2, (y0 + y1) / 2))
                z = self.levels[f]
                O.label(hub[0], hub[1], z + 2.1, r['name'], 0.6, 'room')
                uid = f'{self.bid}/{f}/{r["id"]}'
                ROOMS.append({'uid': uid, 'building': self.title, 'name': r['name'], 'floor': f,
                              'at': gpt(hub[0], hub[1], z)})
        xs = [v for f in self.order for r in self.floors[f]['rooms'] for v in (r['rect'][0], r['rect'][2])]
        ys = [v for f in self.order for r in self.floors[f]['rooms'] for v in (r['rect'][1], r['rect'][3])]
        top = max(self.levels[f] + max(self.hgt(f, r) for r in self.floors[f]['rooms']) for f in self.order)
        at = self.label_at or ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
        O.label(at[0], at[1], top + 2.5, self.title, 2.4, 'building')
        BUILDINGS.append({'id': self.bid, 'title': self.title, 'rect': [min(xs), min(ys), max(xs), max(ys)],
                          'rooms': sum(1 for f in self.order for r in self.floors[f]['rooms'] if r['kind'] != 'void'),
                          'doors': sum(len(self.floors[f]['doors']) for f in self.order), 'floors': len(self.order)})
        self.f0 = f0

    # ---- двери наружу: ступени, если земля ниже пола
    def exterior_doors(self):
        out = []
        for f in self.order:
            for d in self.floors[f]['doors']:
                if d['b'] not in ('out', 'exit'):
                    continue
                r = self.room(f, d['a'])
                o, c, a, b, mid = door_geom(d)
                side = room_side(self.rect(r), o, c)
                out.append({'f': f, 'door': d, 'room': d['a'], 'o': o, 'c': c, 'a': a, 'b': b, 'mid': mid,
                            'out_side': -side, 'z': self.levels[f]})
        self.ext_doors = out
        return out

    def door_steps(self):
        for ed in self.ext_doors:
            z = ed['z']
            o, s = ed['o'], ed['out_side']
            front = off_pt(ed['mid'], o, s, 1.6)
            g = ground_at(*front)
            w = ed['b'] - ed['a'] + 0.6
            ed['ground'] = g
            ed['steps'] = None
            if 0.16 < z - g < 3.0:
                n = max(2, int(round((z - g) / 0.16)))
                run = 0.3
                land = 1.0
                L = (n - 1) * run
                p_land0 = off_pt(ed['mid'], o, s, self.ext_t / 2)
                p_land1 = off_pt(ed['mid'], o, s, self.ext_t / 2 + land)
                p_end = off_pt(ed['mid'], o, s, self.ext_t / 2 + land + L)
                if o == 'h':
                    O.box(ed['a'] - 0.3, min(p_land0[1], p_land1[1]), ed['b'] + 0.3, max(p_land0[1], p_land1[1]), g - 0.5, z, 'stair')
                else:
                    O.box(min(p_land0[0], p_land1[0]), ed['a'] - 0.3, max(p_land0[0], p_land1[0]), ed['b'] + 0.3, g - 0.5, z, 'stair')
                gb = ground_at(*off_pt(p_end, o, s, 0.5))
                O.stair((p_end[0], p_end[1], gb), (p_land1[0], p_land1[1], z), w, n, min(g, gb) - 0.5, 'stair')
                ed['steps'] = off_pt(p_end, o, s, 1.0)


def doors_out_clamps(b):
    """Дверь ниже земли — выемка перед ней (рельеф не выше пола)."""
    for ed in b.exterior_doors():
        o, s = ed['o'], ed['out_side']
        p0 = off_pt((ed['a'] - 0.6, ed['c']) if o == 'h' else (ed['c'], ed['a'] - 0.6), o, s, 0.0)
        p1 = off_pt((ed['b'] + 0.6, ed['c']) if o == 'h' else (ed['c'], ed['b'] + 0.6), o, s, 2.6)
        clamp_rect(p0[0], p0[1], p1[0], p1[1], ed['z'] - 0.03)


def make_tour(b, start=None, suffix='', title=None):
    """Обход здания: от двери наружу через все помещения (в глубину), между этажами — по лестницам.
    Возвращает множество обойдённых помещений (uid)."""
    exts = b.ext_doors
    if not exts:
        return set()
    ed = exts[start if start is not None else b.start_door]
    pts = []
    checks = []

    def add(p, z):
        pts.append(gpt(p[0], p[1], z))

    begin = ed.get('steps') or off_pt(ed['mid'], ed['o'], ed['out_side'], 1.8)
    add(begin, ed.get('ground', ed['z']))
    if ed.get('steps'):
        add(off_pt(ed['mid'], ed['o'], ed['out_side'], b.ext_t / 2 + 0.5), ed['z'])
    add(ed['mid'], ed['z'])
    graph = {}
    for f in b.order:
        for d in b.floors[f]['doors']:
            if d['b'] in ('out', 'exit'):
                continue
            graph.setdefault((f, d['a']), []).append(((f, d['b']), d))
            graph.setdefault((f, d['b']), []).append(((f, d['a']), d))
    for rid, st in b.stairs.items():
        graph.setdefault((st['lo'], rid), []).append(((st['hi'], rid), ('up', rid)))
        graph.setdefault((st['hi'], rid), []).append(((st['lo'], rid), ('down', rid)))
    visited = set()

    def hub(node):
        f, rid = node
        if node in b.hubs:
            return b.hubs[node]
        r = b.room(f, rid)
        x0, y0, x1, y1 = b.rect(r)
        return ((x0 + x1) / 2, (y0 + y1) / 2)

    def walk_in(node, frm, to):
        obs = b.obstacles.get(node, [])
        for p in route_in_room(frm, to, obs):
            add(p, b.levels[node[0]])

    def visit(node, entry_pt):
        visited.add(node)
        f = node[0]
        h = hub(node)
        walk_in(node, entry_pt, h)
        checks.append([len(pts) - 1, f'{b.bid}/{f}/{node[1]}', r3(b.levels[f])])
        for nb, d in graph.get(node, []):
            if nb in visited:
                continue
            if isinstance(d, tuple):
                st = b.stairs[d[1]]['res']
                path = st['path'] if d[0] == 'up' else list(reversed(st['path']))
                for p in path:
                    pts.append(gpt(*p))
                visit(nb, path[-1][:2])
                back = list(reversed(path))
                for p in back:
                    pts.append(gpt(*p))
                walk_in(node, back[-1][:2], h)
                continue
            if b.room(nb[0], nb[1]) is None:
                continue
            o, c, a, bb, mid = door_geom(d)
            r = b.room(f, node[1])
            side = room_side(b.rect(r), o, c)
            near = off_pt(mid, o, side, 0.75)
            far = off_pt(mid, o, -side, 0.75)
            walk_in(node, h, near)
            add(mid, b.levels[f])
            add(far, b.levels[f])
            visit(nb, far)
            walk_in(nb, hub(nb), far)
            add(mid, b.levels[f])
            add(near, b.levels[f])
            walk_in(node, near, h)

    first = (ed['f'], ed['room'])
    inside = off_pt(ed['mid'], ed['o'], -ed['out_side'], 0.75)
    add(inside, ed['z'])
    visit(first, inside)
    ROUTES.append({'id': f'tour_{b.bid}{suffix}', 'label': title or f'{b.title}: все помещения', 'kind': 'tour', 'points': pts,
                   'checks': checks, 'building': b.bid})
    return {c[1] for c in checks}


def tours(b, names=None):
    """Обходы, пока не пройдены все помещения: каждый следующий — от двери наружу ещё не обойдённой постройки."""
    expected = {f'{b.bid}/{f}/{r["id"]}' for f in b.order for r in b.floors[f]['rooms'] if r['kind'] != 'void'}
    seen = set()
    k = 0
    for i in [b.start_door] + [j for j in range(len(b.ext_doors)) if j != b.start_door]:
        ed = b.ext_doors[i]
        if f'{b.bid}/{ed["f"]}/{ed["room"]}' in seen:
            continue
        title = f'{b.title}: {names.get(ed["room"], ed["room"])}' if names else None
        seen |= make_tour(b, i, f'_{k}' if (names or k) else '', title)
        k += 1
        if seen >= expected:
            break
    missing = sorted(expected - seen)
    if missing:
        WARN.append(f'{b.title}: обход не дошёл до {missing}')


# ---------------------------------------------------------------- данные зданий
def copy_floor(fl):
    return {'rooms': [dict(r) for r in fl['rooms']], 'doors': [dict(d) for d in fl['doors']]}


def shift_mirror(fl, dx, mirror_y=None):
    """Сдвиг по x и зеркало относительно y = mirror_y (коттедж южного ряда)."""
    out = {'rooms': [], 'doors': []}
    for r in fl['rooms']:
        x0, y0, x1, y1 = r['rect']
        if mirror_y is not None:
            y0, y1 = 2 * mirror_y - y1, 2 * mirror_y - y0
        out['rooms'].append({**r, 'rect': [x0 + dx, y0, x1 + dx, y1]})
    for d in fl['doors']:
        o, c, a, b = d['wall']
        if o == 'h':
            c2 = 2 * mirror_y - c if mirror_y is not None else c
            w = ['h', c2, a + dx, b + dx]
        else:
            if mirror_y is not None:
                a, b = 2 * mirror_y - b, 2 * mirror_y - a
            w = ['v', c + dx, a, b]
        out['doors'].append({**d, 'wall': w})
    return out


def set_door(fl, a, b, wall, note):
    for d in fl['doors']:
        if {d['a'], d['b']} == {a, b} or (d['a'] == a and d['b'] == b):
            DEVIATIONS.append(f'{note}: дверь {a}–{b} {d["wall"]} → {wall}')
            d['wall'] = wall
            d['width'] = abs(wall[3] - wall[2])
            return
    raise KeyError((a, b))


# ================================================================ РАСКЛАДКА: уровни площадок
S_SITES = PLAN['S_SITES']
COTTAGES = PLAN['COTTAGES']
BAY_W, BAY_L, AISLE = PLAN['BAY_W'], PLAN['BAY_L'], PLAN['AISLE']
S_LOT = (PLAN['S_LOT_X0'], PLAN['S_LOT_Y0'], PLAN['S_LOT_X0'] + BAY_L * 2 + AISLE, PLAN['S_LOT_Y1'])

S_LEVELS = {}
for ox, oy, mirror, name in S_SITES:
    ex = sg.extent(ox, oy, mirror, sg.TERRACE + 0.5)
    S_LEVELS[name] = round(rect_stat(*[ex[0], ex[2], ex[1], ex[3]], field=H0) * 10) / 10
COT_ROT = PLAN['COT_ROT']
UNFINISHED = PLAN['UNFINISHED']
cot_pt, cot_rect = PLAN['cot_pt'], PLAN['cot_rect']
COT_LEVELS = [round(rect_stat(*cot_rect(cx, cy, k, 7.0, -205.0, 21.0, -193.0), field=H0) * 20) / 20
              for (cx, cy), k in zip(COTTAGES, COT_ROT)]
UNF_LEVELS = [round(rect_stat(*cot_rect(u[0], u[1], u[2], 7.0, -205.0, 21.0, -193.0), field=H0) * 20) / 20 for u in UNFINISHED]
HOZ_RECT = (94.0, 156.0, 146.0, 216.0)
HOZ_LEVEL = round(rect_stat(*HOZ_RECT, field=H0) * 10) / 10
SPORT_RECT = (96.0, 52.0, 140.0, 100.0)
PG_RECT = tuple(float(v) for v in SMALL['playground']['rect'])

# площадки (порядок важен: позже — сверху)
pad_rect(-96.0, -110.0, 18.0, 52.0, CENTRAL, blend=(3, 50, 60, 50))      # v11: и главный корпус на новом месте
SITE1 = [s for s in S_SITES if s[3] == 'С-1'][0]
SITE2 = [s for s in S_SITES if s[3] == 'С-2'][0]
ex1 = sg.extent(SITE1[0], SITE1[1], SITE1[2])
ex2 = sg.extent(SITE2[0], SITE2[1], SITE2[2])
pad_rect(ex1[0] - 3.0, min(ex1[2], ex2[2]) - 4.0, ex2[1] + 4.0, max(ex1[3], ex2[3]) + 4.0,
         (ex1[1], S_LEVELS['С-1'], ex2[0], S_LEVELS['С-2']), blend=(2, 16, 16, 16))
SPORT_LEVEL = round(rect_stat(*SPORT_RECT) * 10) / 10
pad_rect(*SPORT_RECT, SPORT_LEVEL, blend=(8, 8, 8, 8))
pad_rect(*HOZ_RECT, HOZ_LEVEL, blend=(10, 10, 6, 6))
PG_LEVEL = round(rect_stat(*PG_RECT) * 10) / 10
pad_rect(*PG_RECT, PG_LEVEL, blend=(6, 10, 10, 10))
# v13: площадка под домом и у входа (подъезд, место для машины) — у жилых и у стройплощадок
for pad_, lv in zip(PLAN['COT_PADS'], COT_LEVELS + UNF_LEVELS):
    pad_rect(*pad_, lv, blend=(6, 6, 6, 6))
# амфитеатр: оркестра и сцена на +32, вал за рядами на +36
AMPH = SMALL['amphitheatre_rows']
AC = (float(AMPH['center'][0]), float(AMPH['center'][1]))
ORCH = 32.0
ROW_R0, ROW_STEP, ROWS_N = float(AMPH['r0']), float(AMPH['step']), int(AMPH['rows'])
ROW_RISE = 0.4
PROM = ORCH + ROW_RISE * ROWS_N
pad_rect(AC[0] + 4.0, AC[1] - 17.0, AC[0] + 16.0, AC[1] + 17.0, ORCH, blend=(2, 6, 4, 6))
pad_ring(AC[0], AC[1], ROW_R0 + ROW_STEP * ROWS_N, ROW_R0 + ROW_STEP * ROWS_N + 8.0, -74.0, 74.0, PROM, 24.0)
RING_CLAMPS.append((AC[0], AC[1], ROW_R0 + 0.3, ROW_R0 + ROW_STEP * ROWS_N + 0.6, -63.5, 63.5, ORCH - 0.1))
RING_CLAMPS.append((AC[0], AC[1], ROW_R0 + ROW_STEP * ROWS_N, ROW_R0 + ROW_STEP * ROWS_N + 4.4, -67.0, 67.0, PROM - 0.1))
UNDER = 28.0      # под сценой −4 м от оркестры
STAGE = ORCH + 1.0
pad_rect(-101.5, -163.0, -96.0, -157.0, UNDER, blend=(0, 0, 0, 0))
H_PADS = H.copy()          # рельеф после площадок — до врезок (для подпорных стенок)

# ================================================================ ПОСТРОЙКИ
BLD = {}

# ---- главный корпус: 2 этажа, лобби в два света (+8,5), служебная лестница с краю
mf = {int(k): copy_floor(v) for k, v in MAIN['floors'].items()}
main = Building('main', 'Главный корпус', mf, {1: CENTRAL, 2: CENTRAL + float(MAIN['floor_to_floor']['1'])},
                {1: float(MAIN['floor_to_floor']['1']), 2: float(MAIN['floor_to_floor']['2'])},
                glass={'LOB', 'VOID', 'GLR'}, start_door=0)
BLD['main'] = main

# ---- «Ресторан и спа»: один этаж, высоты по назначению залов
spa_f = {1: {'rooms': [dict(r) for r in SPA['rooms']], 'doors': [dict(d) for d in SPA['doors']]}}
spa_h = {'POOL': 7.0, 'RLX': 4.5, 'REST': 5.0, 'LNG': 5.0, 'GYM': 5.0, 'STU': 4.5, 'VST': 5.0, 'GAL': 4.2, 'PEN': 4.2}
spa = Building('spa', '«Ресторан и спа»', spa_f, {1: CENTRAL}, {1: 3.6}, room_h=spa_h,
               glass={'VST', 'GAL', 'REST', 'LNG', 'POOL', 'RLX', 'GYM', 'LR', 'LP', 'LG'}, start_door=0)
spa.basins = [tuple(SPA['pool_indoor'])]
BLD['spa'] = spa

# ---- коттеджи: одна планировка на все 10, южный ряд зеркально; этаж 3,4
COT = {int(k): copy_floor(v) for k, v in SMALL['коттедж'].items()}
def rot_floor(fl, cx, cy, k):
    """Этаж коттеджа с листа (центр дома (14, −199)) — поворот на k × 90° и перенос на участок (схема v13)."""
    out = {'rooms': [], 'doors': []}
    for r in fl['rooms']:
        out['rooms'].append({**r, 'rect': list(cot_rect(cx, cy, k, *r['rect']))})
    for d in fl['doors']:
        o, c, a, b = d['wall']
        p0, q0 = ((a, c), (b, c)) if o == 'h' else ((c, a), (c, b))
        P0, Q0 = cot_pt(cx, cy, k, *p0), cot_pt(cx, cy, k, *q0)
        if abs(P0[1] - Q0[1]) < 1e-6:
            w = ['h', P0[1], min(P0[0], Q0[0]), max(P0[0], Q0[0])]
        else:
            w = ['v', P0[0], min(P0[1], Q0[1]), max(P0[1], Q0[1])]
        out['doors'].append({**d, 'wall': w})
    return out


def rot_vec(v, k):
    x, y = v
    for _ in range(k % 4):
        x, y = -y, x
    return (x, y)


cottages = []
for i, ((cx, cy), lv, k) in enumerate(zip(COTTAGES, COT_LEVELS, COT_ROT)):
    # планировка листа — дом с центром (14, −199); v13: дом развёрнут входом к своему подъезду
    fl = {f: rot_floor(COT[f], cx, cy, k) for f in COT}
    b = Building(f'cot{i + 1:02d}', f'Коттедж {i + 1}', fl, {1: lv, 2: lv + 3.4}, {1: 3.4, 2: 3.4}, ext_t=SMALL_EXT_T,
                 mat_ext='wood_dark', glass={'LIV'}, start_door=0)
    b.cot = (cx, cy, k)
    cottages.append(b)
    BLD[b.bid] = b

# ---- павильон-кофейня на «Стрелке»: 1 этаж и крыша-смотровая
MOLE = 1.5
pav_f = {int(k): shift_mirror(copy_floor(v), -DS) for k, v in SMALL['павильон'].items()}   # v11: мол к новому урезу
PAV_H = 4.2
pav = Building('pav', 'Павильон-кофейня', pav_f, {1: MOLE, 2: MOLE + PAV_H}, {1: PAV_H, 2: 3.0}, ext_t=SMALL_EXT_T,
               glass={'PH'}, open_rooms={'DECK'}, start_door=0)
BLD['pav'] = pav

# ---- маяк: дверь на галерею перенесена на север (винтовая лестница выходит в северо-западный угол), галерея кольцом
lh_f = {int(k): shift_mirror(copy_floor(v), -DS) for k, v in SMALL['маяк'].items()}
LH_GAL = MOLE + 12.0
lh_f[2]['rooms'] = [r for r in lh_f[2]['rooms'] if r['id'] != 'LHG']
lh_f[2]['rooms'].append({'id': 'LHG', 'name': 'Фонарный ярус и обходная галерея', 'rect': [-292.6 - DS, 13.0, -283.4 - DS, 15.0],
                         'kind': 'pub', 'flags': [], 'area': 18.4})
set_door(lh_f[2], 'LH0', 'LHG', ['h', 13.0, -289.4 - DS, -288.23 - DS], 'маяк: дверь на галерею с запада на север')
DEVIATIONS.append('маяк: обходная галерея — полоса 9,2 × 2 м с севера (в листе — с запада), выход с винтовой лестницы — в её угол')
lh = Building('lh', 'Маяк', lh_f, {1: MOLE, 2: LH_GAL}, {1: 12.0, 2: 3.0}, ext_t=SMALL_EXT_T, open_rooms={'LHG'},
              mat_ext='white', start_door=0)
BLD['lh'] = lh

# ---- амфитеатр: уровень под сценой −4 м (+28), сцена +33, аппаратная на променаде +36
am_f = {int(k): copy_floor(v) for k, v in SMALL['амфитеатр'].items()}
app = [dict(r) for r in am_f[0]['rooms'] if r['id'] == 'APP']
app[0]['rect'] = [app[0]['rect'][0] + 2.0, app[0]['rect'][1], app[0]['rect'][2] + 2.0, app[0]['rect'][3]]
DEVIATIONS.append('амфитеатр: аппаратная сдвинута на 2 м на восток (x −55…−51) — на месте листа она стояла в верхнем ряду и '
                  'закрывала выход среднего прохода на променад')
am_f[0]['rooms'] = [r for r in am_f[0]['rooms'] if r['id'] != 'APP']
app_doors = [dict(d, wall=[d['wall'][0], d['wall'][1] + 2.0, d['wall'][2], d['wall'][3]]) for d in am_f[0]['doors'] if d['a'] == 'APP']
am_f[0]['doors'] = [d for d in am_f[0]['doors'] if d['a'] != 'APP']
# лестницы кулис (марш вдоль y): дверь из коридора — к площадке у сцены, выход наружу — в восточную стену
set_door(am_f[-1], 'BCR', 'KUL1', ['v', -92.0, -149.85, -148.68], 'амфитеатр, кулисы север')
set_door(am_f[-1], 'BCR', 'KUL2', ['v', -92.0, -171.32, -170.15], 'амфитеатр, кулисы юг')
for fl_, rid, wall in ((am_f[0], 'KUL1', ['v', -84.0, -149.85, -148.68]), (am_f[0], 'KUL2', ['v', -84.0, -171.32, -170.15])):
    for d in fl_['doors']:
        if d['a'] == rid and d['b'] == 'out':
            DEVIATIONS.append(f'амфитеатр, {rid}: выход наружу {d["wall"]} → {wall} (над маршем)')
            d['wall'] = wall
amph = Building('amph', 'Амфитеатр: под сценой и кулисы', am_f, {-1: UNDER, 0: STAGE}, {-1: STAGE - UNDER, 0: 3.6},
                ext_t=EXT_T, open_rooms={'STG'}, mat_ext='struct', start_door=0, label_at=(-86.0, -160.0))
BLD['amph'] = amph
app_f = {0: {'rooms': app, 'doors': app_doors}}
appb = Building('app', 'Аппаратная', app_f, {0: PROM}, {0: 3.0}, ext_t=SMALL_EXT_T, start_door=0)
BLD['app'] = appb

# ---- хоздвор: одна сетка стен, обходы по постройкам
hz_f = {1: copy_floor(SMALL['хоздвор']['1'])}
hz_h = {'KB': 6.0, 'KP': 4.0, 'KM': 4.0, 'G1': 4.2, 'G2': 4.2, 'G3': 4.2, 'GS': 4.2, 'LR': 4.2, 'LW': 4.2, 'LC': 4.2,
        'SK': 4.2, 'SKK': 4.2, 'TR': 4.0, 'TRU': 4.0, 'WT': 4.0}
hoz = Building('hoz', 'Хоздвор', hz_f, {1: HOZ_LEVEL}, {1: 4.0}, ext_t=SMALL_EXT_T, room_h=hz_h, mat_ext='white')
BLD['hoz'] = hoz

# ---- малые постройки набережной, пляжа и въезда (по схеме: эллинг, прокат, склад ГСМ, спасатели, КПП)
QUAY = 2.0


def one_room(bid, title, rect, doors, level, h, kind='serv', glass=False):
    rid = 'R'
    fl = {1: {'rooms': [{'id': rid, 'name': title, 'rect': list(rect), 'kind': kind, 'flags': [], 'area': 0}],
              'doors': [{'a': rid, 'b': 'out', 'width': abs(w[3] - w[2]), 'wall': w} for w in doors]}}
    b = Building(bid, title, fl, {1: level}, {1: h}, ext_t=SMALL_EXT_T, glass={rid} if glass else (), start_door=0)
    BLD[bid] = b
    return b


Q = -DS     # v11: лодочная станция и прокат — к новому урезу
one_room('eling', 'Эллинг', (-152.0 + Q, 188.0, -134.0 + Q, 206.0), [['v', -134.0 + Q, 195.0, 198.5], ['v', -152.0 + Q, 192.0, 202.0]], QUAY, 6.0)
one_room('gsm', 'Склад ГСМ', (-146.0 + Q, 214.0, -136.0 + Q, 222.0), [['h', 214.0, -142.6 + Q, -141.4 + Q]], QUAY, 3.6)
one_room('rent', 'Прокат: домик выдачи', (-146.0 + Q, 134.0, -136.0 + Q, 144.0),
         [['v', -146.0 + Q, 138.4, 140.8], ['v', -136.0 + Q, 138.4, 139.6]], QUAY, 3.4, glass=True)
RS = tuple(PLAN['RESCUE'])
RESC_L = round(rect_stat(*RS, field=H0) * 20) / 20
pad_rect(RS[0] - 3.0, RS[1] - 3.0, RS[2] + 3.0, RS[3] + 3.0, RESC_L, blend=(4, 6, 8, 6))
one_room('resc', 'Спасательная станция', RS, [['v', RS[0], -122.6, -121.4], ['v', RS[2], -122.6, -121.4]],
         RESC_L, 3.4, glass=True)
KPP_RECT = (136.0, 6.5, 144.0, 12.5)
DEVIATIONS.append('КПП: будка с северной стороны выезда (на схеме нарисована поверх дороги), шлагбаум поперёк')
KPP_L = round(rect_stat(*KPP_RECT, field=H0) * 20) / 20
pad_rect(KPP_RECT[0] - 2.0, KPP_RECT[1] - 1.0, KPP_RECT[2] + 2.0, KPP_RECT[3] + 2.0, KPP_L, blend=(6, 3, 6, 6))
one_room('kpp', 'КПП', KPP_RECT, [['h', 6.5, 139.4, 140.6], ['v', 136.0, 9.0, 10.17]], KPP_L, 3.2, glass=True)

for bb in BLD.values():
    for f in bb.order:
        for r in bb.floors[f]['rooms']:
            if f == bb.order[0] and r['kind'] != 'void':
                clamp_rect(*r['rect'], bb.levels[f] - SLAB_T - 0.05, inset=0.05)
    doors_out_clamps(bb)
for bx in spa.basins:
    clamp_rect(bx[0] - 0.3, bx[1] - 0.3, bx[2] + 0.3, bx[3] + 0.3, CENTRAL - 1.75)
clamp_rect(-96.0, -176.0, -80.0, -144.0, UNDER - SLAB_T - 0.05, inset=0.05)

# ---- конструкции над склоном и на воде (верх настилов — для ступеней у дверей)
PODIUM = tuple(SPA['podium'])
RTER = tuple(SPA['terrace'])
SURFACES.append(('rect', *PODIUM, CENTRAL))
SURFACES.append(('rect', *RTER, CENTRAL))
SURFACES.append(('rect', -99.0, -30.0, -96.0, -24.0, CENTRAL))
# остриё мола по схеме — точка (−292, 10); башня маяка в блокауте квадратная 6 × 6 м и в острие не входит —
# конец мола расширен до площадки 11 × 8 м под башней
_mole = [(float(p[0]), float(p[1])) for p in PLAN['MOLE_PTS']]
_tip = max(range(len(_mole)), key=lambda i: -_mole[i][0])      # остриё — самая западная точка
MOLE_PTS = ([(-138.0 - DS, -26.0)] + _mole[:_tip - 1] + [(-284.0 - DS, 3.0), (-295.0 - DS, 6.0), (-295.0 - DS, 14.0), (-284.0 - DS, 17.0)]
            + _mole[_tip + 2:] + [(-138.0 - DS, 46.0)])
DEVIATIONS.append(f'«Стрелка»: остриё мола ({-286 - DS:.0f}, 4) → ({-292 - DS:.0f}, 10) → ({-286 - DS:.0f}, 16) расширено до площадки '
                  f'x {-295 - DS:.0f}…{-284 - DS:.0f}, y 3…17 — квадратная башня маяка 6 × 6 м в острие не входила')
SURFACES.append(('poly', MOLE_PTS, MOLE))
for r in (PODIUM, RTER):
    clamp_rect(*r, CENTRAL - SLAB_T - 0.05)
clamp_rect(PLAN['shore_x'](10) - 12, -26.5, -136.5 - DS, 46.5, MOLE - 0.3)

# ================================================================ КАСКАД
CAS = DESC['cascade']['elements']
CW = float(DESC['width'])
TOP_X, BOTTOM_X = float(DESC['top_x']), float(DESC['bottom_x'])
N_END, S_END = float(DESC['n_end']), float(DESC['s_end'])
CAS_ZONE = []      # прямоугольники, где рельеф возвращается к природному (террасы каскада)


def cascade_layout():
    """Галереи по номеру: площадки начала и конца, марши по y, ровная полоса."""
    gal = {}
    for e in CAS:
        if e['axis'] == 'x':
            continue
        g = gal.setdefault(e['index'], {'start': None, 'flights': [], 'end': None, 'walk': None})
        if e['kind'] == 'walk':
            g['walk'] = e['rect']
        elif e['kind'] == 'landing':
            if g['start'] is None:
                g['start'] = e
            else:
                g['end'] = e
        elif e['kind'] == 'flight':
            g['flights'].append(e)
    return [gal[k] for k in sorted(gal)]


GALLERIES = cascade_layout()
XFLIGHTS = [e for e in CAS if e['kind'] == 'flight' and e['axis'] == 'x']    # марши «вниз»: index — номер (0 — с террасы)
PADS = [e for e in CAS if e['kind'] == 'pad']                                # площадки над и под маршами «вниз»
LINK = {e['index']: e for e in XFLIGHTS}
for e in CAS:
    if e['kind'] in ('flight', 'landing', 'walk', 'pad'):
        CAS_ZONE.append(tuple(e['rect']))
# промежутки между галереями (террасированный склон) — тоже каскад
for k, g in enumerate(GALLERIES):
    x0, y0, x1, y1 = g['walk']
    up_x = GALLERIES[k - 1]['walk'][0] if k > 0 else TOP_X
    ys_ = (min(g['start']['rect'][1], g['end']['rect'][1]), max(g['start']['rect'][3], g['end']['rect'][3]))
    CAS_ZONE.append((x1, ys_[0], up_x, ys_[1]))
    g['gap'] = (x1, up_x)
    g['span'] = ys_


CD = DESC['cascade']
CAS_BENCH = tuple(CD['bench'])                  # лавка на южной площадке второй галереи (ротонды нет — владелец)
BALCONY = tuple(CD['balcony'])                  # смотровой балкон у третьей
KIOSK = tuple(CD['kiosk'])
CAS_ELEMS = []     # (прямоугольник, уровень, уровни сторон {W, E, S, N}) — под каждым рельеф ниже, по краю — подпорные стенки
for e in CAS:
    r_ = tuple(e['rect'])
    if e['kind'] in ('landing', 'pad'):
        CAS_ELEMS.append((r_, e['z_top'], {}))
    elif e['kind'] == 'flight' and e['axis'] == 'x':
        CAS_ELEMS.append((r_, e['z_bottom'], {'W': e['z_bottom'], 'E': e['z_top']}))
for g in GALLERIES:
    lv_ = [g['start']['z_top']] + [f['z_bottom'] for f in g['flights']] + [g['end']['z_top']]
    CAS_ELEMS.append((tuple(g['walk']), min(lv_), {}))
    CAS_ELEMS.append(((g['gap'][0], g['span'][0], g['gap'][1], g['span'][1]), min(lv_) + 0.45, {}))
CAS_ELEMS.append((BALCONY, GALLERIES[2]['end']['z_top'], {}))
CAS_ZONE += [BALCONY]
# склон под каскадом террасирован: рельеф под каждым элементом ниже его уровня (с запасом 1 м — треугольники сетки)
for r_, lv_, _ in CAS_ELEMS:
    clamp_rect(r_[0] - 1.0, r_[1] - 1.0, r_[2] + 1.0, r_[3] + 1.0, lv_ - 0.3)


# ================================================================ ТРОПЫ И СЛУЖЕБНАЯ ДОРОГА (ленты по профилю)
TR = DESC['trail']
CT = DESC['cottage']
TRAIL_W = 2.4


def rounded(xy, r=4.0):
    """Ломаная со скруглёнными поворотами: у каждой внутренней вершины — квадратичная кривая радиусом ~r."""
    out = [tuple(xy[0])]
    for i in range(1, len(xy) - 1):
        a, b, c = xy[i - 1], xy[i], xy[i + 1]
        la, lc = math.dist(a, b), math.dist(b, c)
        d_ = min(r, 0.45 * la, 0.45 * lc)
        p0 = (b[0] + (a[0] - b[0]) * d_ / la, b[1] + (a[1] - b[1]) * d_ / la)
        p2 = (b[0] + (c[0] - b[0]) * d_ / lc, b[1] + (c[1] - b[1]) * d_ / lc)
        for k in range(5):
            t = k / 4
            out.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * b[0] + t * t * p2[0],
                        (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * b[1] + t * t * p2[1]))
    out.append(tuple(xy[-1]))
    return out


def terrain_path(xy, step=2.0, win=3, z_end=None):
    """Тропа по рельефу: точки через ~2 м, высота — рельеф площадок, сглаженный по ходу; z_end — стык с другой тропой."""
    dense = [xy[0]]
    for a, b in zip(xy, xy[1:]):
        n = max(1, int(math.ceil(math.dist(a, b) / step)))
        for k in range(1, n + 1):
            dense.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
    z = [h_at(x, y, H_PADS) for x, y in dense]
    zs = []
    for i in range(len(z)):
        w_ = z[max(0, i - win):i + win + 1]
        zs.append(sum(w_) / len(w_))
    zs[0] = z[0]
    zs[-1] = z[-1] if z_end is None else z_end
    if z_end is not None:                       # к стыку — плавно на уровень другой тропы
        for k in range(1, min(6, len(zs) - 1)):
            t = k / 6.0
            zs[-1 - k] = zs[-1 - k] * t + z_end * (1 - t)
    return [(x, y, zz) for (x, y), zz in zip(dense, zs)]


def nearest_i(pts, xy):
    return min(range(len(pts)), key=lambda i: math.dist(pts[i][:2], xy))


# серпантин (17): от ларька у бровки три колена до пляжа; тропа от коттеджей (3) и тропка из-под сцены сходятся с ним
trail_pts = terrain_path(rounded([tuple(p) for p in TR['polyline']]))
JUNCTION = tuple(TR['polyline'][int(TR['junction'])])
J_I = nearest_i(trail_pts, JUNCTION)
cot_xy = [tuple(p) for p in CT['polyline']]
COT_BROW_I = int(CT['brow_index'])
cot_path = terrain_path(rounded(cot_xy[COT_BROW_I:]), z_end=trail_pts[J_I][2])
cot_path[-1] = trail_pts[J_I]
st_xy = [tuple(p) for p in TR['stage_path']]
ST_I = nearest_i(trail_pts, st_xy[-1])
STAGE_PATH = terrain_path(rounded(st_xy[:-1] + [trail_pts[ST_I][:2]]), z_end=trail_pts[ST_I][2])
SPRING = tuple(TR['spring'])
BENCH = tuple(TR['bench'])
GAZEBOS = [tuple(g['xy']) for g in TR['gazebos']]


def path_z_near(xy):
    best = None
    for pts_ in (trail_pts, cot_path, STAGE_PATH):
        i = nearest_i(pts_, xy)
        d_ = math.dist(pts_[i][:2], xy)
        if best is None or d_ < best[0]:
            best = (d_, pts_[i][2])
    return best[1]


for gx_, gy_ in GAZEBOS:
    clamp_rect(gx_ - 3.3, gy_ - 3.3, gx_ + 3.3, gy_ + 3.3, path_z_near((gx_, gy_)) - 0.3)
clamp_rect(-101.5, -163.0, -96.0, -157.0, UNDER)
# слип эллинга и пирсы: рельеф под ними ниже настила
clamp_rect(-171.0 - DS, 193.6, -152.0 - DS, 200.4, -1.3)


def densify(pts, step):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.ceil(math.dist(a[:2], b[:2]) / step)))
        for k in range(1, n + 1):
            t = k / n
            out.append(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))
    return out


# (id, подпись, точки, ширина, материал, концы сходят на землю: начало, конец); служебной дороги нет (владелец, v11)
RIBBON_SPECS = [
    ('trail', 'Тропа-серпантин: три колена по рельефу', trail_pts, TRAIL_W, 'trail', (True, True)),
    ('stage_path', 'Тропка из-под сцены к серпантину', STAGE_PATH, 2.0, 'trail', (True, False)),
    ('cottage_path', 'Тропа от коттеджей: от бровки к развилке у родника', cot_path, TRAIL_W, 'trail', (True, False)),
]
for rid, title, pts, w, m, joins in RIBBON_SPECS:
    RIBBONS.append({'id': rid, 'title': title, 'pts': pts, 'w': w, 'mat': m, 'joins': joins})

# ================================================================ РЕЛЬЕФ: итог
for rb in RIBBONS:
    apply_ribbon_bench(rb['pts'], rb['w'] / 2 + 0.3, 2.5)
# развилка у родника — ровная площадка на уровне тропы: лавка, родник в кладке у срезки склона
J_LAND = ((SPRING[0] + BENCH[0] + JUNCTION[0]) / 3 + 0.8, (SPRING[1] + BENCH[1] + JUNCTION[1]) / 3, trail_pts[J_I][2])
apply_ribbon_bench([J_LAND, (J_LAND[0] + 0.01, J_LAND[1], J_LAND[2])], 4.6, 2.5)
apply_clamps()
apply_ring_clamps()
H_FINAL = H

# ================================================================ ИЗЛУЧЕНИЕ: здания
for bb in BLD.values():
    item(bb.bid, bb.title)
    bb.exterior_doors()
item()

# ---- лестницы зданий
# главный корпус: П-образная в STA, вход с севера (y = −10), марш 1 в западной половине
item('main', main.title)
st = main.room(1, 'STA')
x0, y0, x1, y1 = st['rect']
F = RectFrame((x0, y1), (0.0, -1.0), (1.0, 0.0))
res = stair_u(F, y1 - y0, 0.0, x1 - x0, 2.2, main.levels[1], main.levels[2], first_low=True, rise=0.161, run=0.3)
main.stairs['STA'] = {'lo': 1, 'hi': 2, 'res': res}
main.slab_override[(2, 'STA')] = [F.rect(0, 2.2, 0, x1 - x0)]
main.hubs[(1, 'STA')] = F.pt(1.1, (x1 - x0) / 2)
main.hubs[(2, 'STA')] = F.pt(1.1, (x1 - x0) / 2)

# павильон: П-образная на крышу, вход с востока (x = −240), марш 1 в южной половине
item('pav', pav.title)
st = pav.room(1, 'PSR')
x0, y0, x1, y1 = st['rect']
F = RectFrame((x1, y0), (-1.0, 0.0), (0.0, 1.0))
res = stair_u(F, x1 - x0, 0.0, y1 - y0, 1.0, pav.levels[1], pav.levels[2], first_low=True, rise=0.162, run=0.3)
pav.stairs['PSR'] = {'lo': 1, 'hi': 2, 'res': res}
pav.slab_override[(2, 'PSR')] = [F.rect(0, 1.0, 0, y1 - y0)]
pav.hubs[(1, 'PSR')] = F.pt(0.5, (y1 - y0) / 2)
pav.hubs[(2, 'PSR')] = F.pt(0.5, (y1 - y0) / 2)

# кулисы амфитеатра: П вдоль y, площадка входа у сцены (1,4 м), марш 1 в западной половине
item('amph', amph.title)
for rid, north in (('KUL1', True), ('KUL2', False)):
    st = amph.room(-1, rid)
    x0, y0, x1, y1 = st['rect']
    F = RectFrame((x0, y0), (0.0, 1.0), (1.0, 0.0)) if north else RectFrame((x0, y1), (0.0, -1.0), (1.0, 0.0))
    res = stair_u(F, y1 - y0, 0.0, x1 - x0, 1.4, UNDER, STAGE, first_low=True, rise=0.179, run=0.26, landing_min=1.1)
    amph.stairs[rid] = {'lo': -1, 'hi': 0, 'res': res}
    amph.slab_override[(0, rid)] = [F.rect(0, 1.4, 0, x1 - x0)]
    amph.hubs[(-1, rid)] = F.pt(0.7, (x1 - x0) * 0.75)
    amph.hubs[(0, rid)] = F.pt(0.7, (x1 - x0) * 0.75)

# коттедж: прямая лестница у западной стены листа (v13 — повёрнута вместе с домом), 20 подъёмов по 0,17
STR_LOCAL = [r['rect'] for r in COT[1]['rooms'] if r['id'] == 'STR'][0]
for b in cottages:
    item(b.bid, b.title)
    cx, cy, k = b.cot
    x0, y0, x1, y1 = STR_LOCAL
    z_lo, z_hi = b.levels[1], b.levels[2]
    F = RectFrame(cot_pt(cx, cy, k, x0, y0), rot_vec((0.0, 1.0), k), rot_vec((1.0, 0.0), k))
    A = y1 - y0
    n, run, a0, w = 20, 0.25, 1.0, 1.17
    L = (n - 1) * run
    F.stair(a0, a0 + L, w / 2, w - 0.06, z_lo, z_hi, n, z_lo - 0.05, 'stair')
    F.box(a0 + L, A, 0, w, z_lo - 0.05, z_hi - 0.06, 'stair')
    F.box(0, a0, 0, w, z_lo - 0.05, z_lo, 'stair')
    F.box(0, A, w + 0.05, x1 - x0, z_hi - SLAB_T, z_hi, 'slab')
    F.box(a0 + L, A, 0, w + 0.05, z_hi - SLAB_T, z_hi, 'slab')
    F.box(0, a0 + L - 1.3, w + 0.02, w + 0.1, z_hi, z_hi + RAIL_H, 'rail')
    b.slab_override[(2, 'STR')] = []
    hub = F.pt(2.0, w + 1.25)
    b.hubs[(1, 'STR')] = hub
    b.hubs[(2, 'STR')] = F.pt(2.0, w + 1.25)
    h = (z_hi - z_lo) / n
    path = [(F.pt(2.0, w + 1.25), z_lo), (F.pt(0.55, w + 0.55), z_lo), (F.pt(0.55, w / 2), z_lo), (F.pt(a0 + 0.35, w / 2), z_lo + h),
            (F.pt(a0 + L - 0.15, w / 2), z_hi), (F.pt(a0 + L - 0.15, w + 0.85), z_hi), (F.pt(2.0, w + 1.25), z_hi)]
    b.stairs['STR'] = {'lo': 1, 'hi': 2, 'res': {'path': [(p[0], p[1], z) for p, z in path]}}
    b.obstacles[(1, 'STR')] = [F.rect(a0 - 0.45, A + 0.5, -0.5, w + 0.45)]

# маяк: винтовая (квадратная) лестница вокруг сплошного столба, 6 маршей по 12 подъёмов до галереи +12
item('lh', lh.title)
st = lh.room(1, 'LH0')
x0, y0, x1, y1 = [float(v) for v in st['rect']]
ix0, iy0, ix1, iy1 = x0 + SMALL_EXT_T / 2, y0 + SMALL_EXT_T / 2, x1 - SMALL_EXT_T / 2, y1 - SMALL_EXT_T / 2
fw = 1.1
O.box(ix0 + fw, iy0 + fw, ix1 - fw, iy1 - fw, MOLE - 0.05, LH_GAL, 'struct')           # столб
corners = [(ix1 - fw / 2, iy0 + fw / 2), (ix0 + fw / 2, iy0 + fw / 2), (ix0 + fw / 2, iy1 - fw / 2), (ix1 - fw / 2, iy1 - fw / 2)]
seq = [0, 1, 2, 3, 0, 1, 2]       # ЮВ → ЮЗ → СЗ → СВ → ЮВ → ЮЗ → СЗ
rise_f = (LH_GAL - MOLE) / 6
# ступени сплошные; под маршами второго витка — проход высотой не меньше 2,5 м над маршем первого витка
LH_FILL = [MOLE - 0.05, MOLE - 0.05, MOLE - 0.05, MOLE + 2.7, MOLE + rise_f + 2.5, MOLE + 2 * rise_f + 2.5]
lh_path = [((ix1 - fw / 2, (iy0 + iy1) / 2), MOLE), (corners[0], MOLE)]
for k in range(6):
    a_, b_ = corners[seq[k]], corners[seq[k + 1]]
    za, zb = MOLE + rise_f * k, MOLE + rise_f * (k + 1)
    dx, dy = b_[0] - a_[0], b_[1] - a_[1]
    Ls = math.hypot(dx, dy)
    ux, uy = dx / Ls, dy / Ls
    p0 = (a_[0] + ux * fw / 2, a_[1] + uy * fw / 2)
    p1 = (b_[0] - ux * fw / 2, b_[1] - uy * fw / 2)
    O.stair((p0[0], p0[1], za), (p1[0], p1[1], zb), fw - 0.04, 12, LH_FILL[k], 'stair')
    cx_, cy_ = b_
    O.box(cx_ - fw / 2, cy_ - fw / 2, cx_ + fw / 2, cy_ + fw / 2, zb - 0.3, zb, 'stair')
    lh_path += [((p0[0] + ux * 0.3, p0[1] + uy * 0.3), za + 0.17), ((p1[0] - ux * 0.25, p1[1] - uy * 0.25), zb - 0.17), (b_, zb)]
# пол фонарного яруса: северная и восточная полосы над маршами нижнего витка; над двумя последними маршами — проём
O.box(ix0, iy1 - fw, ix1, iy1, LH_GAL - SLAB_T, LH_GAL, 'slab')
O.box(ix1 - fw, iy0, ix1, iy1 - fw, LH_GAL - SLAB_T, LH_GAL, 'slab')
lh_path.append(((ix0 + fw + 0.6, iy1 - fw / 2), LH_GAL))
lh.stairs['LH0'] = {'lo': 1, 'hi': 2, 'res': {'path': [(p[0], p[1], z) for p, z in lh_path]}}
lh.slab_override[(2, 'LH0')] = []
lh.hubs[(1, 'LH0')] = (ix1 - fw / 2, (iy0 + iy1) / 2)
lh.hubs[(2, 'LH0')] = (ix0 + fw + 0.6, iy1 - fw / 2)
O.cyl(-288.0 - DS, 10.0, LH_GAL + 3.0, MOLE + 16.0, 2.2, 'glass', solid=False)          # фонарь
O.cyl(-288.0 - DS, 10.0, MOLE + 16.0, MOLE + 17.2, 2.6, 'roof', solid=False)

# крытый бассейн: чаша (дно −1,4), лестница в чашу, вода; препятствие для обхода
item('spa', spa.title)
bx = spa.basins[0]
O.box(bx[0], bx[1], bx[2], bx[3], CENTRAL - 1.9, CENTRAL - 1.4, 'tile')
for (p, q) in (((bx[0], bx[1]), (bx[2], bx[1])), ((bx[2], bx[1]), (bx[2], bx[3])), ((bx[2], bx[3]), (bx[0], bx[3])), ((bx[0], bx[3]), (bx[0], bx[1]))):
    O.seg(p, q, 0.3, CENTRAL - 1.9, CENTRAL - 0.02, 'tile', ext=0.15)
O.stair((bx[2] - 0.6, bx[1] + 3.0, CENTRAL - 1.4), (bx[2] - 0.6, bx[1] + 0.6, CENTRAL), 1.0, 9, CENTRAL - 1.45, 'tile')
O.water.append({'name': 'PoolIndoor', 'level': r3(CENTRAL - 0.25),
                'poly': [[r3(bx[0]), r3(-bx[1])], [r3(bx[2]), r3(-bx[1])], [r3(bx[2]), r3(-bx[3])], [r3(bx[0]), r3(-bx[3])]]})
spa.obstacles[(1, 'POOL')] = [(bx[0] - 0.7, bx[1] - 0.7, bx[2] + 0.7, bx[3] + 0.7)]
spa.hubs[(1, 'POOL')] = ((bx[0] + bx[2]) / 2, (bx[3] + (-66.0)) / 2)

for bb in BLD.values():
    item(bb.bid, bb.title)
    bb.door_steps()
    bb.emit()
HOZ_NAMES = {'KB': 'котельная', 'KM': 'котельная', 'LR': 'прачечная', 'LC': 'прачечная', 'G1': 'гаражи', 'G2': 'гаражи',
             'G3': 'гаражи', 'GS': 'гаражи', 'SK': 'склад', 'SKK': 'склад', 'TR': 'трансформаторная', 'TRU': 'трансформаторная',
             'WT': 'водонапорная башня'}
for bb in BLD.values():
    item(bb.bid, bb.title)
    tours(bb, HOZ_NAMES if bb.bid == 'hoz' else None)
item()

# ================================================================ S-КОРПУСА: номера на дугах
S_UNITS = []


def s_unit(u, level, corps):
    """Номер на 2 этажа по разбивке tools/sanatorium_s_geom.py (v02: 13 × 7,8 м — лист номера × 1,3): стены, плиты,
    П-образная лестница у стены соседа, двери, витражи, терраса и балкон. Возвращает обход номера."""
    F = ArcFrame(u)
    L, D, FW, PW = sg.UNIT_LEN, sg.UNIT_DEPTH, sg.FACADE, sg.PARTY_WALL
    z1 = level + 0.15
    ff = sg.FLOOR_TO_FLOOR
    z2 = z1 + ff
    top = z1 + 2 * ff
    # плиты: пол 1 этажа, 2 этажа (без лестничного проёма), кровля
    F.box(-FW, D + FW, -PW / 2, L + PW / 2, level - 0.45, z1, 'floor')
    F.box(0, sg.STAIR_V0, 0, sg.STAIR_W, z2 - SLAB_T, z2, 'slab')
    F.box(sg.LANDING_V1, D, 0, sg.STAIR_W, z2 - SLAB_T, z2, 'slab')
    F.box(0, D, sg.STAIR_W, L, z2 - SLAB_T, z2, 'slab')
    F.box(-FW - 0.7, D + FW + 0.7, -PW / 2, L + PW / 2, top - 0.05, top + 0.35, 'roof')
    # фасад входа (a = −FW…0) и фасад террас (a = D…D + FW): глухая часть над лестницей в доске, остальное — витраж
    for fa0, fa1, doors1, doors2 in ((-FW, 0.0, [sg.ENTRY_DOOR_U], []), (D, D + FW, [sg.SLIDE_DOOR_U], [sg.SLIDE_DOOR_U])):
        for z0_, z1_, dl in ((z1, z2, doors1), (z2, top, doors2)):
            F.box(fa0, fa1, -PW / 2, sg.STAIR_W, z0_, z1_, 'wood')
            for s0, s1 in sub_intervals(sg.STAIR_W, L + PW / 2, dl):
                F.box(fa0, fa1, s0, s1, z0_, z1_, 'glass')
            for s0, s1 in dl:
                F.box(fa0, fa1, s0, s1, z0_ + DOOR_H, z1_, 'glass')
    # перегородки и перемычки над межкомнатными дверями по этажам (рамка: a = v, b = u)
    pt = PART_T
    for floor, (zb, zt) in ((1, (z1, z2)), (2, (z2, top))):
        for u0, v0, u1, v1 in sg.UNIT_WALLS[floor]:
            if abs(u0 - u1) < 1e-6:
                F.box(min(v0, v1), max(v0, v1), u0 - pt / 2, u0 + pt / 2, zb, zt, 'partition')
            else:
                F.box(v0 - pt / 2, v0 + pt / 2, min(u0, u1), max(u0, u1), zb, zt, 'partition')
        for u0, v0, u1, v1 in sg.UNIT_DOORS[floor]:
            if abs(u0 - u1) < 1e-6:
                F.box(min(v0, v1), max(v0, v1), u0 - pt / 2, u0 + pt / 2, zb + DOOR_H, zt, 'partition')
            else:
                F.box(v0 - pt / 2, v0 + pt / 2, min(u0, u1), max(u0, u1), zb + DOOR_H, zt, 'partition')
    # лестница: марш 1 у прихожей от площадки входа вверх до разворотной, марш 2 у стены обратно к фасаду
    n = sg.RISERS // 2
    hh = ff / (2 * n)
    zm = z1 + n * hh
    L1 = sg.FLIGHT_RUN
    y0s = sg.STAIR_V0
    ca, cb = sg.STAIR_W - sg.FLIGHT_W / 2, sg.FLIGHT_W / 2
    F.stair(y0s, y0s + L1, ca, sg.FLIGHT_W - 0.06, z1, zm, n, z1 - 0.05, 'stair')
    F.box(y0s + L1, sg.LANDING_V1, 0, sg.STAIR_W, z1 - 0.05, zm, 'stair')
    F.stair(y0s + L1, y0s, cb, sg.FLIGHT_W - 0.06, zm, z2, n, z1 - 0.05, 'stair')
    F.box(y0s, y0s + L1, sg.FLIGHT_W, sg.STAIR_W - sg.FLIGHT_W, z1, z2 + RAIL_H, 'rail')
    F.box(y0s - 0.04, y0s + 0.04, sg.FLIGHT_W + 0.1, sg.STAIR_W, z2, z2 + RAIL_H, 'rail')
    F.box(y0s, sg.CLOSET_V, sg.STAIR_W - 0.04, sg.STAIR_W + 0.04, z2, z2 + RAIL_H, 'rail')
    # терраса с экранами между соседями, балкон со стеклянным ограждением
    F.box(D + FW, D + FW + sg.TERRACE, -PW / 2, L + PW / 2, level - 0.45, z1, 'deck')
    F.box(D + FW, D + FW + sg.BALCONY, -PW / 2, L + PW / 2, z2 - SLAB_T, z2, 'deck')
    F.box(D + FW + sg.BALCONY - 0.04, D + FW + sg.BALCONY + 0.04, -PW / 2, L + PW / 2, z2, z2 + RAIL_H, 'glass')
    for ue in (-PW / 2, L + PW / 2):
        F.box(D + FW, D + FW + 2.2, ue - 0.075, ue + 0.075, z1, z1 + 1.8, 'wood')
        F.box(D + FW, D + FW + sg.BALCONY, ue - 0.075, ue + 0.075, z2, z2 + RAIL_H, 'wood')
    # обход номера (точки в рамке: a = v, b = u) — середины помещений из разбивки, двери, лестница
    R1, R2 = sg.UNIT_ROOMS[1], sg.UNIT_ROOMS[2]

    def hub(rooms, code, z):
        return (rooms[code][2], rooms[code][1], z, code)

    ent_u = sum(sg.ENTRY_DOOR_U) / 2
    wc_v = sum(sg.WC_DOOR_V) / 2
    slide_u = sum(sg.SLIDE_DOOR_U) / 2
    cab_v, bed_v = sum(sg.CAB_DOOR_V) / 2, sum(sg.BED_DOOR_V) / 2
    bath_u = sum(sg.BATH_DOOR_U) / 2
    hall_u = (sg.STAIR_W + sg.HALL_U) / 2
    clo_v = (sg.CLOSET_V + D) / 2
    kit_u = R1['KIT'][1]
    inside, out_t, out_b = D - 0.6, D + 0.2, None
    P = [(-1.6, ent_u, level), (-0.2, ent_u, z1), hub(R1, 'HAL', z1),
         (wc_v, sg.WC_U[0] - 0.6, z1), (wc_v, sg.WC_U[0], z1), hub(R1, 'WC', z1), (wc_v, sg.WC_U[0], z1), (wc_v, sg.WC_U[0] - 0.6, z1),
         (3.0, sg.WC_U[0] - 1.2, z1), hub(R1, 'LIV', z1), (sg.UTIL_V + 1.0, kit_u, z1), hub(R1, 'KIT', z1), (sg.UTIL_V + 1.0, kit_u, z1),
         (inside, slide_u, z1), (out_t, slide_u, z1), (D + FW + sg.TERRACE / 2, slide_u, z1, 'TER'), (out_t, slide_u, z1),
         (inside, slide_u, z1), (clo_v, sg.STAIR_W + 0.85, z1), (clo_v, R1['CLO'][1], z1, 'CLO'), (clo_v, sg.STAIR_W + 0.85, z1),
         (2.6, sg.STAIR_W + 0.65, z1), (1.0, sg.STAIR_W + 0.65, z1), (0.85, ca, z1),
         (y0s + 0.35, ca, z1 + hh), (y0s + L1 - 0.3, ca, zm - hh * 0.5), ((y0s + L1 + sg.LANDING_V1) / 2, sg.STAIR_W / 2, zm, 'LND'),
         (y0s + L1 - 0.3, cb, zm + hh * 0.5), (y0s + 0.35, cb, z2 - hh), (y0s / 2, sg.STAIR_W / 2, z2, 'PL2'),
         (y0s / 2, hall_u, z2), hub(R2, 'HL2', z2), (cab_v, hall_u, z2), (cab_v, sg.HALL_U, z2), hub(R2, 'CAB', z2),
         (cab_v, sg.HALL_U, z2), (cab_v, hall_u, z2), (bed_v, hall_u, z2), (bed_v, sg.HALL_U, z2), hub(R2, 'BED', z2),
         (sg.UTIL_V + 0.8, bath_u, z2), (sg.UTIL_V, bath_u, z2), hub(R2, 'BTH', z2), (sg.UTIL_V, bath_u, z2),
         (sg.UTIL_V + 0.8, bath_u, z2), (inside, slide_u, z2), (out_t, slide_u, z2), (D + FW + sg.BALCONY / 2, slide_u, z2, 'BAL'),
         (out_t, slide_u, z2), (inside, slide_u, z2), hub(R2, 'BED', z2)[:3], (bed_v, sg.HALL_U, z2), (bed_v, hall_u, z2),
         (clo_v, hall_u, z2), (clo_v, R2['WRD'][1], z2, 'WRD')]
    names = {k: v[0] for k, v in list(R1.items()) + list(R2.items())}
    names.update({'TER': 'терраса', 'LND': 'площадка лестницы', 'PL2': 'площадка 2 этажа', 'BAL': 'балкон'})
    pts, checks = [], []
    bid = f'{corps}_{u["n"]:02d}'
    for p_ in P:
        x, y = F.pt(p_[0], p_[1])
        pts.append(gpt(x, y, p_[2]))
        if len(p_) > 3:
            fl = 1 if p_[2] < z2 - 0.5 else 2
            uid = f'{bid}/{fl}/{p_[3]}'
            checks.append([len(pts) - 1, uid, r3(p_[2])])
            ROOMS.append({'uid': uid, 'building': f'{corps}, номер {u["n"]}', 'name': names[p_[3]], 'floor': fl,
                          'at': gpt(x, y, p_[2])})
    ROUTES.append({'id': f'tour_{bid}', 'label': f'{corps}, номер {u["n"]}: все помещения, лестница', 'kind': 'tour',
                   'points': pts, 'checks': checks, 'building': bid})
    lx, ly = F.pt(D / 2, L / 2)
    O.label(lx, ly, top + 0.9, f'{corps} · {u["n"]}', 1.0, 'unit')
    S_UNITS.append({'id': bid, 'z': z1})


def sg_unit_point(corps, n, v, u):
    """Точка схемы внутри номера n корпуса по его рамке (v — от фасада входа, u — от лестничной стены)."""
    site = SITE1 if corps == 'С-1' else SITE2
    unit = [x for x in sg.units(site[0], site[1], site[2]) if x['n'] == n][0]
    return ArcFrame(unit).pt(v, u)


for ox, oy, mirror, name in S_SITES:
    item('s_corps_' + name[-1], f'Жилой корпус {name}')
    lv = S_LEVELS[name]
    units = sg.units(ox, oy, mirror)
    for u in units:
        s_unit(u, lv, name)
    # стены между номерами и торцы (0,3 / в доске 0,4)
    z1 = lv + 0.15
    top = z1 + 2 * sg.FLOOR_TO_FLOOR
    for k, u in enumerate(units):
        F = ArcFrame(u)
        F.box(-sg.FACADE, sg.UNIT_DEPTH + sg.FACADE, -sg.PARTY_WALL / 2, sg.PARTY_WALL / 2, z1, top, 'wood' if k == 0 else 'struct')
        if k == len(units) - 1:
            F.box(-sg.FACADE, sg.UNIT_DEPTH + sg.FACADE, sg.UNIT_LEN, sg.UNIT_LEN + sg.PARTY_WALL, z1, top, 'wood')
    # дорожка вдоль фасада входа (по рельефу — полосой)
    for cx, cy, a0, a1, ent_inner in sg.halves(ox, oy, mirror):
        r_ent = sg.face_r(ent_inner, True)
        sgn = 1.0 if r_ent > sg.R else -1.0
        r_a, r_b = r_ent, r_ent + sgn * sg.PATH_W
        n = int(abs(a1 - a0) / 3)
        for k in range(n):
            t0, t1 = math.radians(a0 + (a1 - a0) * k / n), math.radians(a0 + (a1 - a0) * (k + 1) / n)
            ps = [(cx + r * math.cos(t), cy + r * math.sin(t)) for r, t in ((r_a, t0), (r_b, t0), (r_b, t1), (r_a, t1))]
            O.quad('paving', *[(x, y, h_at(x, y) + 0.04) for x, y in ps])
    O.label(ox, oy, lv + 10.0, f'Жилой корпус {name}', 3.0, 'building')
    BUILDINGS.append({'id': name, 'title': f'Жилой корпус {name}', 'rooms': 14 * 14, 'units': 14})
item()

# ================================================================ КАСКАД: объёмы
BAL = 1.0      # балюстрада над площадкой


def gallery_level(g, y):
    """Уровень галереи в точке y (ровные куски — по нижней отметке предыдущего элемента)."""
    sy0 = (g['start']['rect'][1] + g['start']['rect'][3]) / 2
    sy1 = (g['end']['rect'][1] + g['end']['rect'][3]) / 2
    direction = 1.0 if sy1 > sy0 else -1.0
    z = g['start']['z_top']
    for f in g['flights']:
        fa = f['rect'][1] if direction > 0 else f['rect'][3]
        fb = f['rect'][3] if direction > 0 else f['rect'][1]
        if (y - fa) * direction <= 0:
            return z
        if (y - fb) * direction < 0:
            t = (y - fa) / (fb - fa)
            return f['z_top'] + (f['z_bottom'] - f['z_top']) * t
        z = f['z_bottom']
    return z


L0 = LINK[0]
cas_route = [(TOP_X + 6.0, 0.0, CENTRAL), (TOP_X + 1.0, 0.0, CENTRAL), (L0['rect'][2] - 0.4, 0.0, CENTRAL - 0.1),
             (L0['rect'][0] + 0.4, 0.0, L0['z_bottom'] + 0.1)]
cas_checks = [[0, 'cascade/терраса', CENTRAL]]
EXT_DECKS = {(int(g_['gallery']), g_['end']): tuple(g_['x']) for g_ in CD['ext_gaps']}   # проход к смотровому балкону
for e in XFLIGHTS:
    x0, y0, x1, y1 = e['rect']
    yc = (y0 + y1) / 2
    O.stair((x0, yc, e['z_bottom']), (x1, yc, e['z_top']), y1 - y0 - 0.1, e['risers'], h_at(x0, yc) - 1.0, 'stone')
    low = rect_stat(x0, y0, x1, y1, fn=np.min)
    for yy in (y0, y1):
        O.box(x0, yy - 0.1, x1, yy + 0.1, low - 0.5, e['z_top'] + BAL, 'parapet')
for e in PADS:                      # площадки марша «вниз»: плита и перила по обеим сторонам
    x0, y0, x1, y1 = e['rect']
    low = rect_stat(x0, y0, x1, y1, fn=np.min)
    O.box(x0, y0, x1, y1, low - 0.6, e['z_top'], 'stone')
    for yy in (y0, y1):
        O.box(x0, yy - 0.1, x1, yy + 0.1, e['z_top'] - 0.3, e['z_top'] + BAL, 'parapet')
for k, g in enumerate(GALLERIES):
    x0, _, x1, _ = g['walk']
    xc = (x0 + x1) / 2
    sy0 = (g['start']['rect'][1] + g['start']['rect'][3]) / 2
    sy1 = (g['end']['rect'][1] + g['end']['rect'][3]) / 2
    direction = 1.0 if sy1 > sy0 else -1.0
    # площадки
    for L_ in (g['start'], g['end']):
        lx0, ly0, lx1, ly1 = L_['rect']
        low = rect_stat(lx0, ly0, lx1, ly1, fn=np.min)
        O.box(lx0, ly0, lx1, ly1, low - 0.6, L_['z_top'], 'stone')
    # ровные куски и марши по y
    cursor = (g['start']['rect'][3] if direction > 0 else g['start']['rect'][1])
    z = g['start']['z_top']
    pieces = []
    for f in g['flights']:
        fa = f['rect'][1] if direction > 0 else f['rect'][3]
        fb = f['rect'][3] if direction > 0 else f['rect'][1]
        pieces.append(('flat', cursor, fa, z, z))
        pieces.append(('flight', fa, fb, f['z_top'], f['z_bottom'], f['risers']))
        cursor, z = fb, f['z_bottom']
    end_edge = g['end']['rect'][1] if direction > 0 else g['end']['rect'][3]
    pieces.append(('flat', cursor, end_edge, z, z))
    cas_route.append((g['start']['rect'][0] + CW / 2, sy0, g['start']['z_top']))
    cas_checks.append([len(cas_route) - 1, f'cascade/площадка {g["start"]["z_top"]:.2f}', r3(g['start']['z_top'])])
    for pc in pieces:
        a, b_ = sorted((pc[1], pc[2]))
        low = rect_stat(x0, a, x1, b_, fn=np.min)
        if pc[0] == 'flat':
            O.box(x0, a, x1, b_, low - 0.6, pc[3], 'stone')
        else:
            O.stair((xc, pc[2], pc[4]), (xc, pc[1], pc[3]), x1 - x0 - 0.1, pc[5], low - 0.6, 'stone')
            cas_route.append((xc, pc[1] + direction * 0.4, pc[3] - 0.1))
            cas_route.append((xc, pc[2] - direction * 0.4, pc[4] + 0.1))
    # низовая сторона — перила (кроме места, где уходит x-марш на следующую галерею), нагорная — бордюр цветника
    out_y = (LINK[k + 1]['rect'][1], LINK[k + 1]['rect'][3]) if (k + 1) in LINK else None
    ya, yb = sorted((sy0 - direction * CW / 2, sy1 + direction * CW / 2))
    for s0, s1 in sub_intervals(ya, yb, [out_y] if out_y else []):
        nb = max(1, int(math.ceil((s1 - s0) / 1.2)))
        for kk in range(nb):
            p0_, p1_ = s0 + (s1 - s0) * kk / nb, s0 + (s1 - s0) * (kk + 1) / nb
            zl = min(gallery_level(g, p0_), gallery_level(g, p1_))
            O.box(x0 - 0.12, p0_, x0 + 0.05, p1_, zl - 0.6, gallery_level(g, (p0_ + p1_) / 2) + BAL, 'parapet')
    # торцы галереи: перила поперёк (у третьей — проход на смотровой балкон)
    for which, L_ in (('start', g['start']), ('end', g['end'])):
        lx0, ly0, lx1, ly1 = L_['rect']
        edge = ly1 if (L_['rect'][1] + L_['rect'][3]) / 2 > 0 else ly0
        gap = EXT_DECKS.get((k, which))
        for s0, s1 in sub_intervals(lx0, lx1, [gap] if gap else []):
            O.box(s0, edge - 0.08, s1, edge + 0.08, L_['z_top'] - 0.6, L_['z_top'] + BAL, 'parapet')
    # цветники в промежутке до верхнего соседа (террасы склона): верх — уровень галереи + 0,45
    gx0, gx1 = g['gap']
    holes = [(LINK[k]['rect'][1], LINK[k]['rect'][3])]      # в промежутке — марш «вниз» с площадками
    for f in [g['start']] + g['flights'] + [g['end']]:
        pass
    span0, span1 = g['span']
    step_y = 2.0
    yy = span0
    while yy < span1 - 1e-6:
        y2 = min(span1, yy + step_y)
        for s0, s1 in sub_intervals(yy, y2, holes):
            zt = max(gallery_level(g, s0), gallery_level(g, s1)) + 0.45
            low = rect_stat(gx0, s0, gx1, s1, fn=np.min)
            O.box(gx0, s0, gx1, s1, low - 0.6, zt, 'planter')
        yy = y2
    cas_route.append((g['end']['rect'][0] + CW / 2, sy1, g['end']['z_top']))
    cas_checks.append([len(cas_route) - 1, f'cascade/площадка {g["end"]["z_top"]:.2f}', r3(g['end']['z_top'])])
    if (k + 1) in LINK:
        e = LINK[k + 1]
        yc = (e['rect'][1] + e['rect'][3]) / 2
        cas_route.append((e['rect'][2] - 0.4, yc, e['z_top'] - 0.1))
        cas_route.append((e['rect'][0] + 0.4, yc, e['z_bottom'] + 0.1))
cas_route.append((BOTTOM_X - 3.3, 0.0, QUAY))
cas_checks.append([len(cas_route) - 1, 'cascade/набережная', QUAY])
# подпорные стенки по внешнему краю каскада: где склон или терраса выше элемента — стенка 2 м шириной до верха земли
def in_cas(x, y, skip):
    for i_, (r_, _, _) in enumerate(CAS_ELEMS):
        if i_ != skip and r_[0] - 0.02 <= x <= r_[2] + 0.02 and r_[1] - 0.02 <= y <= r_[3] + 0.02:
            return True
    return False


CAS_WALLS = 0
for i_, (r_, lv_, side_lv) in enumerate(CAS_ELEMS):
    x0, y0, x1, y1 = r_
    for side, (ax, ay, bx, by, nx, ny) in (('W', (x0, y0, x0, y1, -1, 0)), ('E', (x1, y0, x1, y1, 1, 0)),
                                           ('S', (x0, y0, x1, y0, 0, -1)), ('N', (x0, y1, x1, y1, 0, 1))):
        L_ = math.hypot(bx - ax, by - ay)
        n_ = max(2, int(math.ceil(L_ / 0.5)))
        lvl = side_lv.get(side, lv_)
        run = []
        for k_ in range(n_ + 1):
            t_ = k_ / n_
            px, py = ax + (bx - ax) * t_, ay + (by - ay) * t_
            outside = not in_cas(px + nx * 0.3, py + ny * 0.3, i_)
            run.append((t_, outside, h_at(px + nx * 2.4, py + ny * 2.4, H_PADS)))
        k_ = 0
        while k_ < len(run):
            if not run[k_][1]:
                k_ += 1
                continue
            j_ = k_
            while j_ + 1 < len(run) and run[j_ + 1][1]:
                j_ += 1
            top = max(v[2] for v in run[k_:j_ + 1]) + 0.1
            if top > lvl + 0.3 and j_ > k_:
                t0_, t1_ = run[k_][0], run[j_][0]
                p0_ = (ax + (bx - ax) * t0_, ay + (by - ay) * t0_)
                p1_ = (ax + (bx - ax) * t1_, ay + (by - ay) * t1_)
                O.box(min(p0_[0], p1_[0] + nx * 2.0), min(p0_[1], p1_[1] + ny * 2.0), max(p0_[0], p1_[0] + nx * 2.0),
                      max(p0_[1], p1_[1] + ny * 2.0), min(lvl, lv_) - 0.6, top, 'stone')
                CAS_WALLS += 1
            k_ = j_ + 1
# подпорные стенки террасы (+32) у каскада: кромка земли уровня площадок — стенка с балюстрадой
first = GALLERIES[0]
gx0_1 = first['walk'][0]
TW = 1.0


def tw_box(x0, y0, x1, y1):
    O.box(x0, y0, x1, y1, rect_stat(x0, y0, x1, y1, fn=np.min) - 0.6, CENTRAL + BAL, 'stone')


tw_box(TOP_X - 1.0, CW / 2, TOP_X - 1.0 + TW, N_END + CW / 2 + TW)
tw_box(gx0_1, N_END + CW / 2, TOP_X, N_END + CW / 2 + TW)
tw_box(gx0_1, -CW / 2 - TW, TOP_X, -CW / 2)
tw_box(gx0_1 - 0.6, S_END - CW / 2, gx0_1 - 0.6 + TW, -CW / 2 - TW)
# фонтан на парадной террасе, киоск, лавка, смотровой балкон
O.cyl(-72.0, 0.0, CENTRAL, CENTRAL + 0.55, 5.0, 'stone')
O.cyl(-72.0, 0.0, CENTRAL + 0.55, CENTRAL + 2.6, 0.5, 'stone')
O.water.append({'name': 'FountainTerrace', 'level': r3(CENTRAL + 0.5), 'circle': [-72.0, 0.0, 4.6]})
kz_ = float(CD['kiosk_z'])
O.box(*KIOSK, kz_, kz_ + 2.6, 'kiosk')
O.label((KIOSK[0] + KIOSK[2]) / 2, (KIOSK[1] + KIOSK[3]) / 2, kz_ + 3.2, 'киоск', 0.8, 'object')
lv = GALLERIES[1]['end']['z_top']             # лавка у южного парапета, спинкой к парапету
bx0_, by0_, bx1_, by1_ = CAS_BENCH
O.box(bx0_, by0_, bx1_, by1_, lv + 0.4, lv + 0.48, 'wood')
O.box(bx0_, by0_ - 0.08, bx1_, by0_, lv + 0.48, lv + 0.9, 'wood', solid=False)
for bxx in (bx0_ + 0.1, bx1_ - 0.2):
    O.box(bxx, by0_ + 0.05, bxx + 0.1, by1_ - 0.05, lv, lv + 0.4, 'wood')
O.label((bx0_ + bx1_) / 2, (by0_ + by1_) / 2, lv + 1.6, 'лавка', 0.7, 'object')
bal = BALCONY
lv3 = GALLERIES[2]['end']['z_top']
O.box(*bal, rect_stat(*bal, fn=np.min) - 0.6, lv3, 'stone')
for (p, q) in (((bal[0], bal[3]), (bal[2], bal[3])), ((bal[0], bal[1]), (bal[0], bal[3])), ((bal[2], bal[1]), (bal[2], bal[3]))):
    O.seg(p, q, 0.16, lv3 - 0.3, lv3 + BAL, 'rail')
O.label((bal[0] + bal[2]) / 2, (bal[1] + bal[3]) / 2, lv3 + 2.0, 'смотровой балкон', 0.8, 'object')
ROUTES.append({'id': 'cascade', 'label': f'Лестница-каскад: терраса +32 → набережная +2, {CD["flights"]} маршей, марш {CW:g} м', 'kind': 'descent',
               'points': [gpt(*p) for p in cas_route], 'checks': cas_checks})

# ================================================================ ТРОПЫ: полоса грунта по врезанному склону
for rb in RIBBONS:
    pts = rb['pts']
    w = rb['w']
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        Ls = math.hypot(dx, dy) + 1e-9
        nx, ny = -dy / Ls * w / 2, dx / Ls * w / 2
        q = [(a[0] - nx, a[1] - ny), (a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny)]
        O.quad(rb['mat'], *[(x, y, ground_at(x, y) + 0.06) for x, y in q])
    route = densify(pts, 6.0)
    ROUTES.append({'id': rb['id'], 'label': rb['title'], 'kind': 'descent', 'points': [gpt(*p) for p in route],
                   'checks': [[0, f'{rb["id"]}/начало', r3(pts[0][2])], [len(route) - 1, f'{rb["id"]}/конец', r3(pts[-1][2])]]})
# беседки, развилка у родника (кладка с трубкой, лавка), ларёк у начала
for gx_, gy_ in GAZEBOS:
    item_next('gazebo', 'Беседка')
    zk = path_z_near((gx_, gy_))
    O.box(gx_ - 3.3, gy_ - 3.3, gx_ + 3.3, gy_ + 3.3, rect_stat(gx_ - 3.3, gy_ - 3.3, gx_ + 3.3, gy_ + 3.3, fn=np.min) - 0.5, zk, 'deck')
    for k in range(8):
        a = math.radians(22.5 + k * 45)
        if k in (4,):
            continue
        O.cyl(gx_ + 2.3 * math.cos(a), gy_ + 2.3 * math.sin(a), zk, zk + 2.4, 0.09, 'wood')
    O.cyl(gx_, gy_, zk + 2.4, zk + 2.7, 2.8, 'roof', solid=False, sides=8)
    O.label(gx_, gy_, zk + 3.3, 'беседка', 0.8, 'object')
item()
zs_ = J_LAND[2]
O.box(SPRING[0] - 1.2, SPRING[1] - 2.2, SPRING[0] + 1.2, SPRING[1] + 2.2, zs_ - 0.5, zs_ + 1.4, 'stone')       # кладка
O.box(SPRING[0] - 2.0, SPRING[1] - 0.8, SPRING[0] - 1.2, SPRING[1] + 0.8, zs_ - 0.3, zs_ + 0.45, 'stone')     # чаша
O.label(SPRING[0], SPRING[1], zs_ + 2.2, 'родник', 0.7, 'object')
zb_ = J_LAND[2]
O.box(BENCH[0] - 0.9, BENCH[1] - 0.25, BENCH[0] + 0.9, BENCH[1] + 0.25, zb_ + 0.4, zb_ + 0.48, 'wood', solid=False)
O.box(BENCH[0] - 0.9, BENCH[1] + 0.2, BENCH[0] + 0.9, BENCH[1] + 0.28, zb_ + 0.48, zb_ + 0.9, 'wood', solid=False)
for bx_ in (BENCH[0] - 0.8, BENCH[0] + 0.8):
    O.box(bx_ - 0.05, BENCH[1] - 0.2, bx_ + 0.05, BENCH[1] + 0.2, zb_, zb_ + 0.4, 'wood')
O.label(BENCH[0], BENCH[1], zb_ + 1.6, 'развилка: к коттеджам', 0.7, 'object')
O.box(-97.0, -105.0, -93.0, -101.0, CENTRAL - 0.2, CENTRAL + 2.6, 'kiosk')
O.label(-95.0, -103.0, CENTRAL + 3.2, 'ларёк у начала тропы', 0.8, 'object')

# ================================================================ ДОРОГИ И ПАРКОВКИ ПО РЕЛЬЕФУ
def strip(pts, w, m, lift=0.05, step=2.0):
    """Полоса по рельефу (асфальт, тротуар) — только вид, ходят по самому рельефу."""
    dense = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.ceil(math.dist(a, b) / step)))
        for k in range(n):
            t = k / n
            dense.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    dense.append(pts[-1])
    for i in range(len(dense) - 1):
        a, b = dense[i], dense[i + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        Ls = math.hypot(dx, dy) + 1e-9
        nx, ny = -dy / Ls * w / 2, dx / Ls * w / 2
        q = [(a[0] - nx, a[1] - ny), (a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny)]
        O.quad(m, *[(x, y, ground_at(x, y) + lift) for x, y in q])


for pts, w in PLAN['ROADS']:
    strip([tuple(p) for p in pts], w, 'asphalt')
strip(cot_xy[:COT_BROW_I + 1], 2.4, 'trail_strip', 0.06)       # тропа от коттеджей по плато
CIRCLE = tuple(PLAN['CIRCLE'])          # v11: круг с фонтаном у главного корпуса
TURN = tuple(PLAN['TURN'])              # разворот у «Ресторана и спа»
for cx_, cy_, rr in [CIRCLE, TURN] + [tuple(t_) for t_ in PLAN['TURNAROUNDS']]:
    n = 24
    for k in range(n):
        t0, t1 = 2 * math.pi * k / n, 2 * math.pi * (k + 1) / n
        ps = [(cx_, cy_), (cx_ + rr * math.cos(t0), cy_ + rr * math.sin(t0)), (cx_ + rr * math.cos(t1), cy_ + rr * math.sin(t1))]
        O.tri('asphalt', *[(x, y, ground_at(x, y) + 0.06) for x, y in ps])
_fz = h_at(CIRCLE[0], CIRCLE[1])
O.cyl(CIRCLE[0], CIRCLE[1], _fz, _fz + 0.6, 5.5, 'stone')
O.cyl(CIRCLE[0], CIRCLE[1], _fz, _fz + 3.0, 0.6, 'stone')
O.water.append({'name': 'FountainCircle', 'level': r3(_fz + 0.55), 'circle': [CIRCLE[0], -CIRCLE[1], 5.1]})

CAR_RNG = random.Random(11)
CARS = []


def lot(x0, y0, n_near, n_far, along_x):
    """Блок парковки: два ряда мест 2,5 × 5 по сторонам проезда 7,8 м (схема), машины — укрытия."""
    length = max(n_near, n_far) * BAY_W + 7.0
    if along_x:
        rect = (x0, y0, x0 + length, y0 + BAY_L * 2 + AISLE)
    else:
        rect = (x0, y0, x0 + BAY_L * 2 + AISLE, y0 + length)
    nx_, ny_ = int(math.ceil((rect[2] - rect[0]) / 2.5)), int(math.ceil((rect[3] - rect[1]) / 2.5))
    for i in range(nx_):
        for j in range(ny_):
            a0, a1 = rect[0] + (rect[2] - rect[0]) * i / nx_, rect[0] + (rect[2] - rect[0]) * (i + 1) / nx_
            b0, b1 = rect[1] + (rect[3] - rect[1]) * j / ny_, rect[1] + (rect[3] - rect[1]) * (j + 1) / ny_
            O.quad('asphalt', *[(x, y, ground_at(x, y) + 0.06) for x, y in ((a0, b0), (a1, b0), (a1, b1), (a0, b1))])
    for side, n in ((0, n_near), (1, n_far)):
        for k in range(n + 1):
            if along_x:
                x = x0 + k * BAY_W
                ya, yb = (y0, y0 + BAY_L) if side == 0 else (rect[3] - BAY_L, rect[3])
                O.quad('stripe', *[(xx, yy, ground_at(xx, yy) + 0.08) for xx, yy in ((x - 0.06, ya), (x + 0.06, ya), (x + 0.06, yb), (x - 0.06, yb))])
            else:
                y = y0 + k * BAY_W
                xa, xb = (x0, x0 + BAY_L) if side == 0 else (rect[2] - BAY_L, rect[2])
                O.quad('stripe', *[(xx, yy, ground_at(xx, yy) + 0.08) for xx, yy in ((xa, y - 0.06), (xb, y - 0.06), (xb, y + 0.06), (xa, y + 0.06))])
        for k in range(n):
            if CAR_RNG.random() >= 0.35:
                continue
            if along_x:
                cx_ = x0 + (k + 0.5) * BAY_W
                cy_ = y0 + BAY_L / 2 if side == 0 else rect[3] - BAY_L / 2
                CARS.append((cx_, cy_, 90.0 + CAR_RNG.uniform(-6, 6)))
            else:
                cy_ = y0 + (k + 0.5) * BAY_W
                cx_ = x0 + BAY_L / 2 if side == 0 else rect[2] - BAY_L / 2
                CARS.append((cx_, cy_, CAR_RNG.uniform(-6, 6)))
    return rect


LOTS = [lot(x0_, y0_, n0_, n1_, True) for x0_, y0_, n0_, n1_ in PLAN['MAIN_LOTS']] + \
       [lot(PLAN['S_LOT_X0'], PLAN['S_LOT_Y0'], 20, 20, False)]
for (bx0_, by0_, bx1_, by1_), odd_ in PLAN['COT_BAYS']:          # место для машины у входа (v13)
    O.quad('asphalt', *[(x, y, ground_at(x, y) + 0.06) for x, y in ((bx0_, by0_), (bx1_, by0_), (bx1_, by1_), (bx0_, by1_))])
    if CAR_RNG.random() < 0.5:
        CARS.append(((bx0_ + bx1_) / 2, (by0_ + by1_) / 2, (90.0 if odd_ else 0.0) + CAR_RNG.uniform(-4, 4)))
CAR_COLORS = ['car_a', 'car_b', 'car_c', 'car_d']
for i, (cx_, cy_, ang) in enumerate(CARS):
    item_next('car', 'Машина')
    g = min(h_at(cx_ + dx_, cy_ + dy_) for dx_ in (-2, 2) for dy_ in (-2, 2))
    m = CAR_COLORS[i % 4]
    if i % 3 == 1:                  # фургон 2,4 м — закрывает взгляд над парковкой (замер обзора, владелец: «ломать сейчас»)
        O.obox(cx_, cy_, 2.0, 5.2, g - 0.1, g + 2.4, ang, m)
        continue
    O.obox(cx_, cy_, 1.8, 4.4, g - 0.1, g + 0.75, ang, m)
    O.obox(cx_, cy_, 1.6, 2.5, g + 0.75, g + 1.45, ang, m)
item()
# шлагбаум КПП и тротуары S-корпусов
O.box(133.8, -4.8, 134.2, 4.8, h_at(134, 0) + 0.9, h_at(134, 0) + 1.05, 'barrier_red', solid=False)
O.box(133.6, 5.0, 134.4, 5.6, h_at(134, 5.3), h_at(134, 5.3) + 1.1, 'metal')
SX0, SY0, SX1, SY1 = S_LOT
for xs_ in (SX0 - 1.5, SX1 + 1.5):
    strip([(xs_, SY0 - 6), (xs_, SY1 + 3)], sg.PATH_W, 'paving', 0.07)
for xa, xb, y in ((SX0, SITE1[0] + sg.R - sg.HALF_T - sg.PATH_W, SITE1[1] + sg.R), (SX1, SITE2[0] - sg.R + sg.HALF_T + sg.PATH_W, SITE2[1] + sg.R),
                  (SX0, SITE1[0] + sg.R + sg.HALF_T + sg.PATH_W, SITE1[1] - sg.R), (SX1, SITE2[0] - sg.R - sg.HALF_T - sg.PATH_W, SITE2[1] - sg.R)):
    strip([(xa, y), (xb, y)], sg.PATH_W, 'paving', 0.07)
strip([(8.0, -9.0), (3.0, -42.0)], 3.0, 'paving', 0.07)
PAVED = [([tuple(q) for q in pts_], w_) for pts_, w_ in PLAN['PATHS']]   # v11: дорожки у главного корпуса
for pts_, w_ in PLAN['TRACKS']:                                          # v13: грунтовки к стройплощадкам
    strip([tuple(q) for q in pts_], w_, 'trail_strip', 0.06)
    PAVED.append(([tuple(q) for q in pts_], w_))
for pts_, w_ in PAVED:
    strip(pts_, w_, 'paving', 0.07)
strip([(-80.0, -16.0), (-86.0, -20.0)], 3.0, 'paving', 0.07)
strip([(-97.5, -30.0), (-97.5, -24.0), (-92.0, -20.5)], 3.0, 'paving', 0.07)

# ================================================================ «Ресторан и спа»: подиум, терраса, открытый бассейн
# v11 (владелец): не фундаментный блок, а подвесной подиум над скалой — плита 1,2 м с краевой балкой, чаша висит
# под плитой, от уступа под обрывом к плите — диагональные подкосы (два на раму, рамы через 6 м)
po = tuple(SPA['pool_outdoor'])
DECK_BOT = CENTRAL - 1.2
for p in rect_minus(PODIUM, [po]):
    O.box(*p, DECK_BOT, CENTRAL, 'floor')
for (bx0, by0, bx1, by1) in ((PODIUM[0], PODIUM[1], PODIUM[0] + 0.7, PODIUM[3]), (PODIUM[0], PODIUM[1], PODIUM[2], PODIUM[1] + 0.7),
                             (PODIUM[0], PODIUM[3] - 0.7, PODIUM[2], PODIUM[3])):
    O.box(bx0, by0, bx1, by1, DECK_BOT - 1.0, DECK_BOT, 'struct')          # краевая балка
O.box(po[0] - 0.4, po[1] - 0.4, po[2] + 0.4, po[3] + 0.4, CENTRAL - 2.4, CENTRAL - 1.9, 'struct')   # дно чаши снизу
for (p, q) in (((po[0], po[1]), (po[2], po[1])), ((po[2], po[1]), (po[2], po[3])), ((po[2], po[3]), (po[0], po[3])), ((po[0], po[3]), (po[0], po[1]))):
    O.seg(p, q, 0.4, CENTRAL - 2.4, DECK_BOT, 'struct', ext=0.2)                 # стенки чаши под плитой
STRUTS = []
for yk in np.arange(PODIUM[1] + 3.0, PODIUM[3] - 2.0, 6.0):
    yk = float(yk)
    zf = h_at(FACE_X[1] - 1.0, yk) + 0.3
    foot = (FACE_X[1] - 1.0, yk, zf + 0.5)
    O.box(FACE_X[1] - 2.2, yk - 0.8, FACE_X[1] + 0.2, yk + 0.8, zf - 1.0, zf + 1.0, 'stone')            # пята в скале
    for xt_, zt_ in ((PODIUM[0] + 0.5, DECK_BOT - 0.5), ((PODIUM[0] + PODIUM[2]) / 2, DECK_BOT - 0.3)):
        O.beam(foot, (xt_, yk, zt_), 0.6, 0.6, 'struct')
        STRUTS.append((foot, (xt_, yk, zt_)))
    O.beam((FACE_X[0] + 0.5, yk, DECK_BOT - 0.2), (PODIUM[0] + 0.5, yk, DECK_BOT - 0.2), 0.5, 0.6, 'struct')   # ригель рамы под плитой
O.box(*po, CENTRAL - 1.9, CENTRAL - 1.4, 'tile')
for (p, q) in (((po[0], po[1]), (po[2], po[1])), ((po[2], po[1]), (po[2], po[3])), ((po[2], po[3]), (po[0], po[3])), ((po[0], po[3]), (po[0], po[1]))):
    O.seg(p, q, 0.3, CENTRAL - 1.9, CENTRAL - 0.02, 'tile', ext=0.15)
O.stair((po[0] + 0.6, po[1] + 3.0, CENTRAL - 1.4), (po[0] + 0.6, po[1] + 0.6, CENTRAL), 1.0, 9, CENTRAL - 1.45, 'tile')
O.water.append({'name': 'PoolOutdoor', 'level': r3(CENTRAL - 0.25),
                'poly': [[r3(po[0]), r3(-po[1])], [r3(po[2]), r3(-po[1])], [r3(po[2]), r3(-po[3])], [r3(po[0]), r3(-po[3])]]})
ch = tuple(SPA['swim_channel'])
O.box(*ch, CENTRAL - 1.9, CENTRAL - 1.4, 'tile')
for yy in (ch[1], ch[3]):
    O.box(ch[0], yy - 0.15, ch[2], yy + 0.15, CENTRAL - 1.9, CENTRAL - 0.02, 'tile')
_hx0 = float(spa.room(1, 'POOL')['rect'][0])     # западная стена зала бассейна — над проплывом стекло до воды
O.box(_hx0 - 0.25, ch[1], _hx0 + 0.25, ch[3], CENTRAL - 0.4, CENTRAL + 7.0, 'glass')
O.water.append({'name': 'SwimChannel', 'level': r3(CENTRAL - 0.25),
                'poly': [[r3(ch[0]), r3(-ch[1])], [r3(ch[2]), r3(-ch[1])], [r3(ch[2]), r3(-ch[3])], [r3(ch[0]), r3(-ch[3])]]})
for (p, q) in (((PODIUM[0], PODIUM[1]), (PODIUM[2], PODIUM[1])), ((PODIUM[0], PODIUM[1]), (PODIUM[0], PODIUM[3])),
               ((PODIUM[0], PODIUM[3]), (PODIUM[2], PODIUM[3]))):
    O.seg(p, q, 0.25, CENTRAL - 0.2, CENTRAL + RAIL_H, 'glass')
for k in range(8):
    lx_ = po[0] - 2.0 + k * 2.6
    if po[0] - 1 < lx_ < po[2] + 1:
        for ly_ in (-92.5, -70.5):
            O.box(lx_, ly_ - 1.0, lx_ + 0.8, ly_ + 1.0, CENTRAL, CENTRAL + 0.45, 'deck')
O.label((PODIUM[0] + PODIUM[2]) / 2, -95.0, CENTRAL + 2.5, 'открытый бассейн на подвесном подиуме', 1.0, 'object')
O.label(FACE_X[1] - 6.0, -84.0, h_at(FACE_X[1] - 6.0, -84.0) + 4.0, 'скала и подкосы подиума', 1.0, 'object')
O.box(*RTER, rect_stat(*RTER, fn=np.min) - 0.6, CENTRAL, 'deck')
for (p, q) in (((RTER[0], RTER[1]), (RTER[2], RTER[1])), ((RTER[0], RTER[1]), (RTER[0], RTER[3])), ((RTER[0], RTER[3]), (RTER[2] - 3.0, RTER[3]))):
    O.seg(p, q, 0.2, CENTRAL - 0.2, CENTRAL + RAIL_H, 'rail')
O.box(-99.0, -30.0, -96.0, -24.0, rect_stat(-99, -30, -96, -24, fn=np.min) - 0.6, CENTRAL, 'deck')
O.seg((-99.0, -30.0), (-99.0, -24.0), 0.2, CENTRAL - 0.2, CENTRAL + RAIL_H, 'rail')
O.label(-104.0, -39.0, CENTRAL + 2.5, 'терраса ресторана', 1.0, 'object')

# ================================================================ НАБЕРЕЖНАЯ, ПЛЯЖ, «СТРЕЛКА»
ATTACH = [(-27.0, 47.0), (136.6, 143.4), (172.5, 177.5), (190.5, 203.5)]


def poly_ear(pts):
    """Треугольники простого многоугольника (отсечение ушей)."""
    pts = list(pts)
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    if area < 0:
        pts.reverse()
    idx = list(range(len(pts)))
    tris = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if cross(a, b, c) <= 1e-9:
                continue
            if any(in_poly(*pts[j], [a, b, c]) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((a, b, c))
            idx.pop(k)
            break
    if len(idx) == 3:
        tris.append(tuple(pts[i] for i in idx))
    return tris


def slab_poly(pts, z_top, z_bot, m, side_m=None):
    for a, b, c in poly_ear(pts):
        O.tri(m, (a[0], a[1], z_top), (b[0], b[1], z_top), (c[0], c[1], z_top), solid=True)
    for p, q in zip(pts, pts[1:] + pts[:1]):
        O.quad(side_m or m, (p[0], p[1], z_bot), (q[0], q[1], z_bot), (q[0], q[1], z_top), (p[0], p[1], z_top), solid=True)


def outline_parapet(pts, z, skip_last=False, h=0.9, t=0.3, m='parapet'):
    n = len(pts) - (1 if skip_last else 0)
    for i in range(n):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        O.seg(p, q, t, z - 0.2, z + h, m, solid=False, ext=t / 2)
        dx, dy = q[0] - p[0], q[1] - p[1]
        O.barrier(p, q, z - 0.5, z + 2.6)


# мол: плита, парапет по краю (кроме стыка с набережной)
mole_poly = MOLE_PTS
slab_poly(mole_poly, MOLE, -3.0, 'paving', 'stone')
mp = mole_poly[1:-1]
outline_parapet(mp + [], MOLE, skip_last=True)
# мол на 0,5 ниже набережной — три ступени во всю ширину у берега
O.stair((-138.0 - DS, 10.0, MOLE), (-136.0 - DS, 10.0, QUAY), 72.0, 3, MOLE - 0.3, 'stone')
O.label(-205.0 - DS, 10.0, MOLE + 7.5, '«Стрелка»', 3.0, 'building')
# фонтанная площадь, киоски, колоннада под навесом, ротонда, клумбы и стенки
O.cyl(-182.0 - DS, 10.0, MOLE, MOLE + 0.6, 9.0, 'stone', sides=32)
O.cyl(-182.0 - DS, 10.0, MOLE + 0.6, MOLE + 3.0, 0.7, 'stone')
O.water.append({'name': 'FountainMole', 'level': r3(MOLE + 0.55), 'circle': [-182.0 - DS, -10.0, 8.6]})
for kx, ky in ((-200.0 - DS, -8.0), (-262.0 - DS, 18.0), (-232.0 - DS, 30.0)):
    O.box(kx - 3, ky - 2.5, kx + 3, ky + 2.5, MOLE, MOLE + 3.0, 'kiosk')
    O.box(kx - 3.4, ky - 2.9, kx + 3.4, ky + 2.9, MOLE + 3.0, MOLE + 3.25, 'roof')
    O.label(kx, ky, MOLE + 4.0, 'киоск', 0.8, 'object')
col = [(-192.0 - DS - k * 5.5, 36.0 - k * 0.9) for k in range(10)]
for x_, y_ in col:
    O.cyl(x_, y_, MOLE, MOLE + 3.8, 0.4, 'white', sides=12)
ang = math.degrees(math.atan2(col[-1][1] - col[0][1], col[-1][0] - col[0][0]))
mid = ((col[0][0] + col[-1][0]) / 2, (col[0][1] + col[-1][1]) / 2)
O.obox(mid[0] + 1.6 * math.sin(math.radians(ang)), mid[1] - 1.6 * math.cos(math.radians(ang)), math.dist(col[0], col[-1]) + 2.0, 4.2,
       MOLE + 3.8, MOLE + 4.2, ang, 'roof', solid=False)
O.label(mid[0], mid[1], MOLE + 5.0, 'колоннада', 0.8, 'object')
for k in range(8):
    a = math.radians(k * 45 + 22.5)
    O.cyl(-270.0 - DS + 4.4 * math.cos(a), 10.0 + 4.4 * math.sin(a), MOLE, MOLE + 3.6, 0.3, 'white')
O.cyl(-270.0 - DS, 10.0, MOLE + 3.6, MOLE + 4.1, 5.0, 'white', solid=False, sides=24)
O.label(-270.0 - DS, 10.0, MOLE + 5.0, 'ротонда', 0.8, 'object')
for px_, py_ in ((-192, 2), (-206, 18), (-226, -6), (-252, 10), (-170, -8), (-240, 36), (-166, 30), (-172, 22), (-176, -16),
                 (-212, -12), (-196, -13)):
    O.box(px_ - DS - 3.5, py_ - 1.2, px_ - DS + 3.5, py_ + 1.2, MOLE, MOLE + 0.9, 'planter')
# моторка у маяка (выход В5)
O.obox(-291.5 - DS, 1.0, 5.5, 2.0, -0.2, 0.6, 0.0, 'boat', solid=False)
# наружная лестница с крыши павильона на мол
dk = [d for d in pav.floors[2]['doors'] if d['a'] == 'DECK'][0]
o_, c_, a_, b_, mid_ = door_geom(dk)
n_ = int(round(PAV_H / 0.16))
O.stair((mid_[0], c_ + 0.3 + (n_ - 1) * 0.3, MOLE), (mid_[0], c_ + 0.3, MOLE + PAV_H), b_ - a_ + 0.3, n_, MOLE - 0.05, 'stair')
for xx in (a_ - 0.25, b_ + 0.25):
    O.box(xx - 0.06, c_ + 0.3, xx + 0.06, c_ + 0.3 + (n_ - 1) * 0.3, MOLE, MOLE + PAV_H + RAIL_H, 'rail', solid=False)
pav_ext = {'top': (mid_[0], c_ + 0.8, MOLE + PAV_H), 'bottom': (mid_[0], c_ + 0.3 + (n_ - 1) * 0.3 + 1.0, MOLE)}

# набережная: стенка у воды с парапетом (кроме пляжа и примыканий мола, пирсов, слипа), невидимая преграда
ys_shore = np.arange(GRID_Y[0] + 4, GRID_Y[1] - 4 + 0.1, 4.0)


def attached(y):
    return any(a <= y <= b for a, b in ATTACH)


sh = [(float(shore_x(y)), float(y)) for y in ys_shore]
for p, q in zip(sh, sh[1:]):
    ym = (p[1] + q[1]) / 2
    if ym < SY - 4 or ym > NY - 2:
        continue
    beach = BEACH[0] + 4 <= ym <= BEACH[1] - 4
    if beach:
        O.barrier((p[0] - 4.0, p[1]), (q[0] - 4.0, q[1]), -6.0, 4.0)
        continue
    if attached(ym) or in_poly((p[0] + q[0]) / 2 - 0.5, ym, MOLE_PTS):
        continue
    O.seg(p, q, 0.8, -3.0, QUAY - 0.02, 'stone', ext=0.4)
    O.seg((p[0] + 0.2, p[1]), (q[0] + 0.2, q[1]), 0.3, QUAY - 0.1, QUAY + 0.9, 'parapet', solid=False, ext=0.2)
    O.barrier((p[0] + 0.2, p[1]), (q[0] + 0.2, q[1]), -6.0, QUAY + 2.6)
# лодочная станция: слип, стеллажи лодок, причальная стенка-пальчик, понтон проката, лодки (v11 — на DS западнее)
O.beam((-170.0 + Q, 197.0, -1.0), (-152.3 + Q, 197.0, QUAY), 7.6, 1.2, 'stone')         # слип в воду
for yy in (192.0, 202.0):
    O.seg((-152.0 + Q, yy), (-170.0 + Q, 194.0 if yy < 197 else 200.0), 0.3, -1.6, QUAY + 0.9, 'parapet', ext=0.15)
O.barrier((-168.0 + Q, 193.8), (-168.0 + Q, 200.2), -3.0, 4.0)
for k in range(4):
    O.box(-140.0 + Q, 160.0 + k * 6, -132.0 + Q, 163.0 + k * 6, QUAY, QUAY + 2.4, 'metal')
finger = [(-149.0 + Q, 173.0), (-186.0 + Q, 175.0), (-186.0 + Q, 177.0), (-149.0 + Q, 175.0)]
slab_poly(finger, QUAY + 0.02, -2.0, 'deck', 'stone')
outline_parapet(finger, QUAY, skip_last=True, h=0.9, t=0.15, m='rail')
pontoon = [(-149.0 + Q, 138.0), (-184.0 + Q, 140.0), (-184.0 + Q, 143.0), (-149.0 + Q, 141.0)]
slab_poly(pontoon, 0.55, -0.4, 'deck', 'deck')
O.stair((-149.5 + Q, 139.5, 0.55), (-146.6 + Q, 139.5, QUAY), 2.6, 9, -0.5, 'stone')
outline_parapet(pontoon, 0.55, skip_last=True, h=0.9, t=0.12, m='rail')
SURFACES.append(('poly', finger, QUAY))
SURFACES.append(('poly', pontoon, 0.55))
for k in range(4):
    for dy in (0.0, 2.6):
        O.box(-178.0 + Q + k * 8, 132.4 + dy, -173.0 + Q + k * 8, 133.6 + dy, -0.1, 0.5, 'boat', solid=False)
    O.box(-178.0 + Q + k * 8, 145.0, -172.0 + Q + k * 8, 147.5, -0.1, 0.5, 'boat', solid=False)
for k in range(5):
    O.box(-133.0 + Q, 133.0 + k * 3.2 - 0.3, -129.0 + Q, 133.0 + k * 3.2 + 0.3, QUAY, QUAY + 1.6, 'boat')
# пляж 42 м (v11): кабинки у подошвы склона, грибки двумя рядами ближе к воде, мороженое под зонтиком
for c_ in PLAN['CABINS']:
    cx_, cy_ = (c_[0] + c_[2]) / 2, (c_[1] + c_[3]) / 2
    O.box(*c_, h_at(cx_, cy_), h_at(cx_, cy_) + 2.3, 'kiosk')
for x_, y_ in PLAN['UMBRELLAS']:
    g_ = h_at(x_, y_)
    O.cyl(x_, y_, g_ - 0.3, g_ + 2.4, 0.07, 'metal')
    O.cyl(x_, y_, g_ + 2.4, g_ + 2.55, 2.0, 'umbrella', solid=False)
ix_, iy_ = PLAN['ICE']
O.cyl(ix_, iy_, h_at(ix_, iy_) + 2.2, h_at(ix_, iy_) + 2.35, 3.2, 'umbrella_pink', solid=False)
O.box(ix_ - 1.2, iy_ - 1.0, ix_ + 1.2, iy_ + 1.0, h_at(ix_, iy_), h_at(ix_, iy_) + 1.0, 'kiosk')
O.label(ix_, iy_, h_at(ix_, iy_) + 3.0, 'мороженое', 0.8, 'object')
O.label(-178.0, -165.0, 6.0, 'Пляж', 2.4, 'building')
O.label(-195.0, 175.0, 9.0, 'Лодочная станция', 2.4, 'building')

# ================================================================ АМФИТЕАТР: ряды, проходы, променад, колоннада
AISLES = [float(a) for a in AMPH['aisles_deg']]
SPAN = float(AMPH['span_deg'])
AISLE_W = 1.6


def arc_boxes(r0, r1, a0, a1, z0, z1, m, chord=2.2):
    rm = (r0 + r1) / 2
    n = max(1, int(math.ceil(math.radians(a1 - a0) * rm / chord)))
    for k in range(n):
        t0 = a0 + (a1 - a0) * k / n
        t1 = a0 + (a1 - a0) * (k + 1) / n
        tm = math.radians((t0 + t1) / 2)
        length = math.radians(t1 - t0) * rm + 0.05
        O.obox(AC[0] + rm * math.cos(tm), AC[1] + rm * math.sin(tm), length, r1 - r0, z0, z1, math.degrees(tm) + 90.0, m)


for k in range(ROWS_N):
    r0 = ROW_R0 + ROW_STEP * k
    r1 = r0 + ROW_STEP
    top = ORCH + ROW_RISE * (k + 1)
    cuts = []
    for a in AISLES:
        da = math.degrees(AISLE_W / 2 / ((r0 + r1) / 2))
        cuts.append((a - da, a + da))
    for s0, s1 in sub_intervals(-SPAN, SPAN, cuts):
        arc_boxes(r0, r1, s0, s1, ORCH - 0.6, top, 'stone')
rp0 = ROW_R0 + ROW_STEP * ROWS_N
arc_boxes(rp0, rp0 + 4.0, -SPAN - 4, SPAN + 4, ORCH - 0.6, PROM, 'paving')
for a in AISLES:
    ta = math.radians(a)
    p0 = (AC[0] + ROW_R0 * math.cos(ta), AC[1] + ROW_R0 * math.sin(ta))
    p1 = (AC[0] + rp0 * math.cos(ta), AC[1] + rp0 * math.sin(ta))
    O.stair((p0[0], p0[1], ORCH), (p1[0], p1[1], PROM), AISLE_W - 0.05, ROWS_N * 2, ORCH - 0.6, 'stone')
for k in range(17):
    if -64 + k * 8 == 0:
        continue        # по оси — аппаратная, колонна закрыла бы её дверь
    a = math.radians(-64 + k * 8)
    O.cyl(AC[0] + (rp0 + 3.6) * math.cos(a), AC[1] + (rp0 + 3.6) * math.sin(a), PROM, PROM + 3.6, 0.3, 'white')
for side in (-1, 1):
    a0_ = side * (SPAN + 0.5)
    for k in range(ROWS_N):
        pass
for x_ in (-92.0, -80.0):
    for y_ in (-170.0, -150.0):
        O.box(x_ - 0.3, y_ - 0.3, x_ + 0.3, y_ + 0.3, STAGE, STAGE + 7.0, 'metal', solid=True)
O.label(AC[0] + 22.0, AC[1], PROM + 4.0, 'Амфитеатр ≈ 660 мест', 2.4, 'building')
SURFACES.append(('rect', -92.0, -170.0, -80.0, -150.0, STAGE))
amph_rows_route = []
for a in (40.0,):
    ta = math.radians(a)
    for r, z in ((ROW_R0 - 3.0, ORCH), (ROW_R0 - 0.4, ORCH), (rp0 + 0.4, PROM), (rp0 + 2.0, PROM)):
        amph_rows_route.append((AC[0] + r * math.cos(ta), AC[1] + r * math.sin(ta), z))
ROUTES.append({'id': 'amph_rows', 'label': 'Амфитеатр: оркестра → проход по рядам → променад', 'kind': 'descent',
               'points': [gpt(*p) for p in amph_rows_route],
               'checks': [[0, 'amph_rows/оркестра', ORCH], [len(amph_rows_route) - 1, 'amph_rows/променад', PROM]]})

# ================================================================ ДЕТСКАЯ ПЛОЩАДКА, КОРТЫ, ХОЗДВОР
pg = SMALL['playground']
x0, y0, x1, y1 = PG_RECT
for rx in ((2, -138, 26, -98, 'rubber_red'), (24, -110, 52, -97, 'rubber_green'), (46, -150, 60, -124, 'rubber_blue')):
    O.quad(rx[4], *[(x, y, h_at(x, y) + 0.05) for x, y in ((rx[0], rx[1]), (rx[2], rx[1]), (rx[2], rx[3]), (rx[0], rx[3]))])
gates = [(x0, -125.0), (x1, -125.0)]
for p, q in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
    if p[0] == q[0]:
        for s0, s1 in sub_intervals(min(p[1], q[1]), max(p[1], q[1]), [(-126.0, -124.0)]):
            O.box(p[0] - 0.05, s0, p[0] + 0.05, s1, PG_LEVEL, PG_LEVEL + 1.2, 'fence_green')
    else:
        O.box(min(p[0], q[0]), p[1] - 0.05, max(p[0], q[0]), p[1] + 0.05, PG_LEVEL, PG_LEVEL + 1.2, 'fence_green')
for it in pg['items']:
    k = it['kind']
    g = it['geo']
    hgt = float(it['height'])
    if k == 'ship':
        gx0, gy0, gx1, gy1 = g
        O.box(gx0, gy0, gx1, gy1, PG_LEVEL, PG_LEVEL + hgt, 'play')
        for yy in (gy0, gy1):
            O.box(gx0, yy - 0.06, gx1, yy + 0.06, PG_LEVEL + hgt, PG_LEVEL + hgt + 1.2, 'play_red')
        O.box(gx0 + 4, gy0 + 1.2, gx0 + 7, gy1 - 1.2, PG_LEVEL + hgt, PG_LEVEL + hgt + 2.2, 'play_red')
        O.cyl(gx0 + 9.5, (gy0 + gy1) / 2, PG_LEVEL + hgt, PG_LEVEL + hgt + 5.0, 0.12, 'wood')
    elif k == 'plane':
        gx0, gy0, gx1, gy1 = g
        O.box(gx0, (gy0 + gy1) / 2 - 1.0, gx1, (gy0 + gy1) / 2 + 1.0, PG_LEVEL + 1.3, PG_LEVEL + hgt, 'play')
        O.box((gx0 + gx1) / 2 - 1.0, gy0, (gx0 + gx1) / 2 + 1.0, gy1, PG_LEVEL + 1.9, PG_LEVEL + 2.1, 'play_red')
        for xx in (gx0 + 2, gx1 - 2):
            O.cyl(xx, (gy0 + gy1) / 2, PG_LEVEL, PG_LEVEL + 1.3, 0.2, 'metal')
    elif k == 'truck':
        gx0, gy0, gx1, gy1 = g
        O.box(gx0, gy0, gx0 + 3.0, gy1, PG_LEVEL, PG_LEVEL + hgt, 'play_red')
        O.box(gx0 + 3.0, gy0, gx1, gy1, PG_LEVEL, PG_LEVEL + 1.1, 'play')
    elif k == 'pyramid':
        cx_, cy_, rr = g
        for kk in range(6):
            a = math.radians(kk * 60)
            O.beam((cx_ + rr * math.cos(a), cy_ + rr * math.sin(a), PG_LEVEL), (cx_, cy_, PG_LEVEL + hgt), 0.08, 0.08, 'rope', solid=False)
        O.cyl(cx_, cy_, PG_LEVEL, PG_LEVEL + hgt, 0.1, 'metal')
    elif k == 'swing':
        gx0, gy0, gx1, gy1 = g
        for xx in (gx0, gx1):
            O.box(xx - 0.1, gy0, xx + 0.1, gy1, PG_LEVEL, PG_LEVEL + hgt, 'metal')
        O.box(gx0, (gy0 + gy1) / 2 - 0.06, gx1, (gy0 + gy1) / 2 + 0.06, PG_LEVEL + hgt - 0.12, PG_LEVEL + hgt, 'metal', solid=False)
    elif k == 'tramp':
        for cx_, cy_ in g:
            O.cyl(cx_, cy_, PG_LEVEL - 0.02, PG_LEVEL + 0.06, 1.5, 'rubber_dark', solid=False)
    elif k == 'spring':
        for cx_, cy_ in g:
            O.box(cx_ - 0.2, cy_ - 0.5, cx_ + 0.2, cy_ + 0.5, PG_LEVEL, PG_LEVEL + hgt, 'play_red')
    elif k == 'carousel':
        cx_, cy_, rr = g
        O.cyl(cx_, cy_, PG_LEVEL, PG_LEVEL + hgt, rr, 'play')
    elif k == 'sand':
        gx0, gy0, gx1, gy1 = g
        for p, q in (((gx0, gy0), (gx1, gy0)), ((gx1, gy0), (gx1, gy1)), ((gx1, gy1), (gx0, gy1)), ((gx0, gy1), (gx0, gy0))):
            O.seg(p, q, 0.2, PG_LEVEL, PG_LEVEL + hgt, 'wood', ext=0.1)
        O.box(gx0, gy0, gx1, gy1, PG_LEVEL + 2.4, PG_LEVEL + 2.55, 'roof', solid=False)
        for xx, yy in ((gx0, gy0), (gx1, gy0), (gx1, gy1), (gx0, gy1)):
            O.cyl(xx, yy, PG_LEVEL, PG_LEVEL + 2.4, 0.06, 'wood')
O.label(30.0, -123.0, PG_LEVEL + 7.0, 'Детская площадка', 2.4, 'building')
# корты и волейбол за сеткой
sx0, sy0, sx1, sy1 = SPORT_RECT
O.quad('court', *[(x, y, SPORT_LEVEL + 0.04) for x, y in ((sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1))])
for p, q in (((sx0, sy0), (sx1, sy0)), ((sx1, sy0), (sx1, sy1)), ((sx1, sy1), (sx0, sy1)), ((sx0, sy1), (sx0, sy0))):
    if p[0] == q[0] and p[0] == sx0:
        for s0, s1 in sub_intervals(sy0, sy1, [(75.0, 77.4)]):
            O.box(sx0 - 0.04, s0, sx0 + 0.04, s1, SPORT_LEVEL, SPORT_LEVEL + 3.0, 'fence')
    elif p[0] == q[0]:
        O.box(p[0] - 0.04, min(p[1], q[1]), p[0] + 0.04, max(p[1], q[1]), SPORT_LEVEL, SPORT_LEVEL + 3.0, 'fence')
    else:
        O.box(min(p[0], q[0]), p[1] - 0.04, max(p[0], q[0]), p[1] + 0.04, SPORT_LEVEL, SPORT_LEVEL + 3.0, 'fence')
O.box(118.0 - 0.04, 52.0, 118.0 + 0.04, 100.0, SPORT_LEVEL, SPORT_LEVEL + 3.0, 'fence')
for yy in (64.0, 88.0):
    O.box(96.5, yy - 0.03, 117.5, yy + 0.03, SPORT_LEVEL + 0.9, SPORT_LEVEL + 1.0, 'white', solid=False)
O.box(118.5, 76.0 - 0.03, 139.5, 76.0 + 0.03, SPORT_LEVEL + 2.3, SPORT_LEVEL + 2.43, 'white', solid=False)
O.label(118.0, 76.0, SPORT_LEVEL + 5.0, 'Корты и волейбол', 2.0, 'building')
# хоздвор: труба котельной, водонапорная башня с баком, забор с воротами
O.cyl(123.0, 186.0, HOZ_LEVEL, HOZ_LEVEL + 30.0, 1.3, 'brick', sides=16)
O.cyl(122.0, 204.0, HOZ_LEVEL + 4.0, HOZ_LEVEL + 18.0, 2.0, 'struct', sides=16)
O.cyl(122.0, 204.0, HOZ_LEVEL + 18.0, HOZ_LEVEL + 23.5, 4.2, 'metal', sides=20)
hx0, hy0, hx1, hy1 = HOZ_RECT
for p, q, gap in (((hx0, hy0), (hx1, hy0), None), ((hx1, hy0), (hx1, hy1), None), ((hx1, hy1), (hx0, hy1), None),
                  ((hx0, hy1), (hx0, hy0), (192.5, 199.5))):
    if p[0] == q[0]:
        for s0, s1 in sub_intervals(min(p[1], q[1]), max(p[1], q[1]), [gap] if gap else []):
            O.box(p[0] - 0.12, s0, p[0] + 0.12, s1, HOZ_LEVEL - 0.3, HOZ_LEVEL + 2.2, 'fence')
    else:
        O.box(min(p[0], q[0]), p[1] - 0.12, max(p[0], q[0]), p[1] + 0.12, HOZ_LEVEL - 0.3, HOZ_LEVEL + 2.2, 'fence')
O.label(120.0, 186.0, HOZ_LEVEL + 33.0, 'труба котельной', 1.4, 'object')
for k, (ex_, ey_) in enumerate(((104.0, 175.0), (118.0, 176.0), (101.0, 197.0), (130.0, 192.0), (113.0, 214.0))):
    O.box(ex_ - 0.6, ey_ - 0.6, ex_ + 0.6, ey_ + 0.6, HOZ_LEVEL, HOZ_LEVEL + 1.2, 'eurocube')

# ================================================================ ДЕРЕВЬЯ: только ели и сосны (те же точки, что на схеме участка)
TREES = {'pine': [], 'pine_slim': [], 'spruce_a': [], 'spruce_b': [], 'spruce_young': [],
         'pine_bg': [], 'spruce_a_bg': [], 'spruce_b_bg': []}
BLOCK = []      # где деревьям не место: постройки, ленты, площадки (прямоугольники с запасом)
for bb in BLD.values():
    for f in bb.order:
        for r in bb.floors[f]['rooms']:
            x0, y0, x1, y1 = r['rect']
            BLOCK.append((x0 - 2.5, y0 - 2.5, x1 + 2.5, y1 + 2.5))
for rct in CAS_ZONE + [PODIUM, RTER, PG_RECT, SPORT_RECT, HOZ_RECT, (-100.0, -180.0, -50.0, -138.0)] + LOTS:
    BLOCK.append((rct[0] - 2.0, rct[1] - 2.0, rct[2] + 2.0, rct[3] + 2.0))
for pad_ in PLAN['COT_PADS']:                                   # v13: дома, стройплощадки и места у входа
    BLOCK.append((pad_[0] - 3.0, pad_[1] - 3.0, pad_[2] + 3.0, pad_[3] + 3.0))
for u_ in UNFINISHED:                                           # стройматериалы и бытовка вокруг стройплощадки
    BLOCK.append((u_[0] - 15.0, u_[1] - 15.0, u_[0] + 15.0, u_[1] + 15.0))
for gx_, gy_ in PLAN['GAZEBOS_PARK']:
    BLOCK.append((gx_ - 5.0, gy_ - 5.0, gx_ + 5.0, gy_ + 5.0))
for ox, oy, mirror, name in S_SITES:
    e_ = sg.extent(ox, oy, mirror, sg.TERRACE + 1.0)
    BLOCK.append((e_[0], e_[2], e_[1], e_[3]))
BLOCK.append((float(shore_x(10.0)) - 6.0, -30.0, BOTTOM_X + 4.0, 50.0))      # набережная у низа каскада и мола


def blocked(x, y):
    for x0, y0, x1, y1 in BLOCK:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return True
    for rb in RIBBONS:
        for a, b in zip(rb['pts'], rb['pts'][1:]):
            if seg_dist(np.array([x]), np.array([y]), a, b)[0][0] < rb['w'] / 2 + 2.2:
                return True
    for pts_, w_ in PAVED:
        for a, b in zip(pts_, pts_[1:]):
            if seg_dist(np.array([x]), np.array([y]), a, b)[0][0] < w_ / 2 + 1.5:
                return True
    return False


def in_s_courtyard_ok(x, y):
    return True


rng = random.Random(7)
kinds_plateau = ['pine', 'pine', 'pine_slim']
kinds_dark = ['spruce_a', 'spruce_b', 'spruce_young']
for k in range(1400):
    x = rng.uniform(-140, 165)
    y = rng.uniform(-258, 258)
    if not PLAN['in_poly'](x, y, PLAN['boundary']) or not PLAN['free'](x, y) or x < PLAN['brow_x'](y) - 34:
        continue
    rad = rng.uniform(2.2, 3.6)
    pine = rng.random() < 0.7
    if blocked(x, y):
        continue
    key = (kinds_plateau if pine else kinds_dark)[k % 3]
    TREES[key].append([r3(x), r3(h_at(x, y) - 0.1), r3(-y), r3((k * 47) % 360), r3(0.85 + (rad - 2.2) / 1.4 * 0.35)])
for k in range(420):                         # лес по склону (v11 — склон длиннее, деревьев больше)
    y = rng.uniform(-250, 250)
    x = rng.uniform(PLAN['foot_x'](y) + 1, PLAN['brow_x'](y) - 2)
    if -38 < y < 50 or (-230 < y < -60 and abs(x + 127) < 34 and rng.random() < 0.4) or (-110 < y < -56 and x > -142):
        continue
    rad = rng.uniform(2.0, 3.0)
    if blocked(x, y):
        continue
    key = ['spruce_a', 'pine', 'spruce_b', 'pine_slim', 'spruce_young'][k % 5]
    TREES[key].append([r3(x), r3(h_at(x, y) - 0.1), r3(-y), r3((k * 71) % 360), r3(0.8 + (rad - 2.0) * 0.3)])
# группы елей, ломающие длинные лучи обзора (места — замер tools/sanatorium_ld_plan.py --breaks; владелец 2026-11-07:
# «ломать сейчас»): большая ель в середине, вокруг молодые ели и ещё одна ель — подлесок, закрывающий взгляд от земли
BREAKS = DATA / 'sanatorium_view_breaks.json'
BREAK_TREES = 0


def near_road(x, y, pad=1.5):
    for pts_, w_ in PLAN['ROADS']:
        for a, b in zip(pts_, pts_[1:]):
            if seg_dist(np.array([x]), np.array([y]), a, b)[0][0] < w_ / 2 + pad:
                return True
    return False


if BREAKS.exists():
    brng = random.Random(31)
    for k_, (cx_, cy_, _) in enumerate(json.loads(BREAKS.read_text(encoding='utf-8'))['clusters']):
        a0_ = brng.uniform(0, 360)
        layout = [(0.0, 0.0, ('spruce_a', 'spruce_b')[k_ % 2], brng.uniform(1.05, 1.25))]
        for j_ in range(4):
            r_ = brng.uniform(3.0, 4.5)
            a_ = math.radians(a0_ + j_ * 90 + brng.uniform(-20, 20))
            layout.append((r_ * math.cos(a_), r_ * math.sin(a_), 'spruce_young', brng.uniform(0.9, 1.15)))
        a_ = math.radians(a0_ + 45)
        layout.append((5.5 * math.cos(a_), 5.5 * math.sin(a_), ('spruce_b', 'spruce_a')[k_ % 2], brng.uniform(0.85, 1.0)))
        for dx_, dy_, key_, sc_ in layout:
            x_, y_ = cx_ + dx_, cy_ + dy_
            if not PLAN['in_poly'](x_, y_, PLAN['boundary']) or blocked(x_, y_) or near_road(x_, y_):
                continue
            TREES[key_].append([r3(x_), r3(h_at(x_, y_) - 0.1), r3(-y_), r3(brng.uniform(0, 360)), r3(sc_)])
            BREAK_TREES += 1
# фон: лес за забором, за оврагом и на мысу (без коллизии)
bg = random.Random(21)
for k in range(5200):
    x = bg.uniform(-200, 600)
    y = bg.uniform(-620, 620)
    inside = PLAN['in_poly'](x, y, PLAN['boundary'])
    if inside or x < PLAN['shore_x'](max(-300.0, min(300.0, y))) + 4:
        continue
    if abs(x - 160) < 18 and abs(y) < 8:
        continue
    gx_ = x if GRID_X[0] < x < GRID_X[1] and GRID_Y[0] < y < GRID_Y[1] else None
    TREES[['pine_bg', 'spruce_a_bg', 'spruce_b_bg'][k % 3]].append([r3(x), None if gx_ is None else r3(h_at(x, y) - 0.2), r3(-y),
                                                                     r3((k * 37) % 360), r3(0.9 + (k % 7) * 0.05)])

# ================================================================ ДАЛЬНИЙ ПЛАН: плотина, горы, озеро
TERRACE_EYE = (-72.0, 0.0)
U = (-math.sqrt(0.5), -math.sqrt(0.5))
V_ = (math.sqrt(0.5), -math.sqrt(0.5))
C = (TERRACE_EYE[0] + U[0] * 1200.0, TERRACE_EYE[1] + U[1] * 1200.0)
E1 = (C[0] + V_[0] * 500.0, C[1] + V_[1] * 500.0)
E2 = (C[0] - V_[0] * 500.0, C[1] - V_[1] * 500.0)
M_ = (C[0] + U[0] * 140.0, C[1] + U[1] * 140.0)
# окружность через E1, M_, E2


def circle3(a, b, c):
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax ** 2 + ay ** 2) * (by - cy) + (bx ** 2 + by ** 2) * (cy - ay) + (cx ** 2 + cy ** 2) * (ay - by)) / d
    uy = ((ax ** 2 + ay ** 2) * (cx - bx) + (bx ** 2 + by ** 2) * (ax - cx) + (cx ** 2 + cy ** 2) * (bx - ax)) / d
    return (ux, uy), math.dist((ux, uy), a)


DC, DR = circle3(E1, M_, E2)
aE1 = math.atan2(E1[1] - DC[1], E1[0] - DC[0])
aE2 = math.atan2(E2[1] - DC[1], E2[0] - DC[0])
aM = math.atan2(M_[1] - DC[1], M_[0] - DC[0])
# дуга от E1 до E2 через M_
da = (aE2 - aE1 + math.pi) % (2 * math.pi) - math.pi
if abs(((aM - aE1 + math.pi) % (2 * math.pi) - math.pi)) > abs(da):
    da = da - math.copysign(2 * math.pi, da)
DAM_H = 260.0
NSEG = 36
dam_pts = []
for k in range(NSEG + 1):
    a = aE1 + da * k / NSEG
    dam_pts.append(a)


def dam_p(a, off, z):
    """Точка грани плотины: off — смещение к центру кривизны (к зрителю: низовая грань)."""
    r = DR - off
    return (DC[0] + r * math.cos(a), DC[1] + r * math.sin(a), z)


for a0, a1 in zip(dam_pts, dam_pts[1:]):
    for z0, z1 in ((-12.0, 60.0), (60.0, 140.0), (140.0, 210.0), (210.0, DAM_H)):
        o0 = 15.0 + 55.0 * (1 - z0 / DAM_H) if z0 > 0 else 70.0
        o1 = 15.0 + 55.0 * (1 - z1 / DAM_H)
        O.quad('dam', dam_p(a0, o0, z0), dam_p(a1, o0, z0), dam_p(a1, o1, z1), dam_p(a0, o1, z1))
    O.quad('dam', dam_p(a0, 15.0, DAM_H), dam_p(a1, 15.0, DAM_H), dam_p(a1, 0.0, DAM_H), dam_p(a0, 0.0, DAM_H))
    O.quad('dam', dam_p(a0, 0.0, DAM_H), dam_p(a1, 0.0, DAM_H), dam_p(a1, 0.0, DAM_H + 3.0), dam_p(a0, 0.0, DAM_H + 3.0))
mid_a = aE1 + da / 2
ges = dam_p(mid_a, 70.0 + 30.0, 0.0)
O.obox(ges[0], ges[1], 300.0, 45.0, -2.0, 42.0, math.degrees(mid_a) + 90.0, 'dam_dark', solid=False)
O.label(ges[0], ges[1], DAM_H + 40.0, 'плотина ГЭС · 260 м', 1.0, 'far')

LAKE_FAR = [(-150.0 - DS, 360.0), (-430.0, 440.0), (-780.0, 270.0), (-1080.0, -30.0), (-1300.0, -380.0)]
LAKE_FAR += [dam_p(a, 70.0, 0.0)[:2] for a in [aE1 + da * k / 12 for k in range(12, -1, -1)]]
LAKE_FAR += [(-420.0, -930.0), (-250.0, -620.0), (-150.0 - DS, -380.0)]
shore_line = [(float(shore_x(y)) + 6.0, float(y)) for y in np.arange(GRID_Y[0], GRID_Y[1] + 0.1, 8.0)]
# контур: от северного края берега по дальнему озеру (север → запад → плотина → юг), потом по берегу с юга на север
lake_poly = LAKE_FAR + shore_line
O.water.append({'name': 'Lake', 'level': 0.0, 'poly': [[r3(x), r3(-y)] for x, y in lake_poly]})

# горы и берега вокруг — грубая сетка 10 м (под подробной ниже на 4 м)
FX = np.arange(-2400.0, 1200.0 + 0.1, 10.0)
FY = 1400.0 - np.arange(0.0, 3400.0 + 0.1, 10.0)
FGX, FGY = np.meshgrid(FX, FY)


def lake_mask_dist(X, Y, poly):
    """Внутри озера (чётность пересечений) и расстояние до берега (по рёбрам многоугольника)."""
    inside = np.zeros(X.shape, bool)
    d = np.full(X.shape, np.inf)
    for a, b in zip(poly, poly[1:] + poly[:1]):
        (xi, yi), (xj, yj) = a, b
        cond = (yi > Y) != (yj > Y)
        xcross = (xj - xi) * (Y - yi) / (yj - yi + 1e-12) + xi
        inside ^= cond & (X < xcross)
        dd, _ = seg_dist(X, Y, a, b)
        d = np.minimum(d, dd)
    return inside, d


inside_l, dist_l = lake_mask_dist(FGX, FGY, lake_poly)
rect_d = np.hypot(np.maximum(0, np.maximum(GRID_X[0] - FGX, FGX - GRID_X[1])), np.maximum(0, np.maximum(GRID_Y[0] - FGY, FGY - GRID_Y[1])))
near = 1.0 - smooth(rect_d / 160.0)
nat_far = natural(FGX, np.clip(FGY, -300, 300))
hill = 40.0 + 0.16 * dist_l + 55.0 * (np.sin(FGX / 310.0 + 1.1) * np.cos(FGY / 270.0 - 0.4)) + 25.0 * np.sin((FGX - FGY) / 140.0)
# горы у концов плотины (держат стену 260 м) и за ней; пологие — на крутых склонах дальний рельеф рисуется скалой
for ex_, ey_, hh_ in ((E1[0] + V_[0] * 420, E1[1] + V_[1] * 420, 380.0), (E2[0] - V_[0] * 420, E2[1] - V_[1] * 420, 380.0),
                      (C[0] + U[0] * 900, C[1] + U[1] * 900, 360.0)):
    hill = np.maximum(hill, hh_ * np.exp(-((FGX - ex_) ** 2 + (FGY - ey_) ** 2) / (2 * 640.0 ** 2)))
hill = np.maximum(hill, 38.0)
far_h = np.where(inside_l, -10.0 + np.minimum(dist_l, 40.0) * 0.0, hill * (1 - near) + nat_far * near)
far_h = np.where(~inside_l & (dist_l < 40.0), np.minimum(far_h, 2.0 + dist_l * 1.2) * (1 - near) + far_h * near, far_h)
# под подробным рельефом дальний опущен глубоко: в выемках каскада, троп и чаш он не должен выглядывать
in_detail = (FGX > GRID_X[0] + 5.0) & (FGX < GRID_X[1] - 5.0) & (FGY > GRID_Y[0] + 5.0) & (FGY < GRID_Y[1] - 5.0)
far_h = np.where(in_detail, np.minimum(nat_far - 4.0, -14.0), far_h)


def far_at(x, y):
    fx = (x - FX[0]) / 10.0
    fy = (FY[0] - y) / 10.0
    i = int(np.clip(math.floor(fx), 0, len(FX) - 2))
    j = int(np.clip(math.floor(fy), 0, len(FY) - 2))
    tx, ty = fx - i, fy - j
    return float(far_h[j, i] * (1 - tx) * (1 - ty) + far_h[j, i + 1] * tx * (1 - ty) + far_h[j + 1, i] * (1 - tx) * ty
                 + far_h[j + 1, i + 1] * tx * ty)


for key in ('pine_bg', 'spruce_a_bg', 'spruce_b_bg'):
    for t_ in TREES[key]:
        if t_[1] is None:
            t_[1] = r3(far_at(t_[0], -t_[2]) - 0.3)
    TREES[key] = [t_ for t_ in TREES[key] if t_[1] > 3.0]
# за плотиной — водохранилище высоко (не видно)
# за плотиной (только в пределах её дуги) — водохранилище высоко, рельеф до гребня: с санатория не видно
behind = ((FGX - DC[0]) ** 2 + (FGY - DC[1]) ** 2) > (DR + 5) ** 2
ang_p = np.arctan2(FGY - DC[1], FGX - DC[0])
t_arc = (((ang_p - aE1) + np.pi) % (2 * np.pi) - np.pi) / da
behind &= (t_arc > 0.0) & (t_arc < 1.0) & (np.hypot(FGX - DC[0], FGY - DC[1]) < DR + 900.0)
far_h = np.where(behind, np.maximum(far_h, 240.0), far_h)

# ================================================================ ГРАНИЦА, ВЫХОДЫ, ЗАХОДЫ
bnd = PLAN['boundary']
n_s = len(PLAN['south'])
n_e = len(PLAN['east'])
n_n = len(PLAN['north'])
land_edge = bnd[:n_s + n_e + n_n]
GATES = [(150.0, 0.0, 10.0), (130.0, 238.0, 6.0)]


def near_gate(p):
    return any(math.dist(p, (gx_, gy_)) < r_ for gx_, gy_, r_ in GATES)


for p, q in zip(land_edge, land_edge[1:]):
    if near_gate(((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)):
        continue
    z0_ = min(h_at(*p), h_at(*q)) - 3.0
    O.barrier(p, q, z0_, z0_ + 30.0)
# забор по восточной кромке (опушка), ворота КПП
east_pts = PLAN['east']
for p, q in zip(east_pts, east_pts[1:]):
    m_ = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
    if near_gate(m_):
        continue
    O.seg((p[0] - 0.5, p[1]), (q[0] - 0.5, q[1]), 0.08, min(h_at(*p), h_at(*q)) - 0.2, max(h_at(*p), h_at(*q)) + 2.0, 'fence', solid=False, ext=0.05)
O.barrier((172.0, -12.0), (172.0, 12.0), 20.0, 70.0)
O.barrier((150.0, -10.0), (172.0, -12.0), 20.0, 70.0)
O.barrier((150.0, 10.0), (172.0, 12.0), 20.0, 70.0)
strip([(150.0, 0.0), (175.0, 0.0)], 9.0, 'asphalt')
EXIT_INFO = {
    'В1': ('КПП, выезд', 'всегда', (160.0, 0.0)),
    'В2': ('Лесная тропа к горам', 'по стороне захода', (128.0, 232.0)),
    'В3': ('Труба в овраг', 'без рюкзака', (30.0, 229.0)),
    'В4': ('Прокат: каяк или лодка', 'ключ от домика проката', (-181.0 - DS, 141.5)),
    'В5': ('Моторка у маяка', 'не каждый рейд, канистра со склада ГСМ', (-286.0 - DS, 5.5)),
    'В6': ('Берег за мысом', 'не каждый рейд', (-112.0 - DS, -254.0)),
}
EXITS = []
for key, (title, cond, (ex_, ey_)) in EXIT_INFO.items():
    g_ = ground_at(ex_, ey_)
    EXITS.append({'id': key, 'label': f'{key} · {title}', 'condition': cond, 'at': gpt(ex_, ey_, g_)})
    O.markers.append(['exit', *gpt(ex_, ey_, g_), f'{key} · {title} ({cond})'])
O.cyl(30.0, 231.5, h_at(30, 229) - 1.6, h_at(30, 229) + 0.2, 0.75, 'metal', solid=False)
SPAWNS = []
for i, (sx_, sy_) in enumerate(((150.0, 60.0), (150.0, -120.0), (40.0, 236.0), (100.0, -238.0))):
    g_ = h_at(sx_, sy_)
    SPAWNS.append({'id': f'З{i + 1}', 'at': gpt(sx_, sy_, g_)})
    O.markers.append(['spawn', *gpt(sx_, sy_, g_), f'заход З{i + 1}'])

# ================================================================ МЕСТА (1–9, 0, N/B) и маршруты по участку
S_AISLE = S_LOT[0] + BAY_L + AISLE / 2
PLACE_SPOTS = {
    1: ((-28.0, 39.0), (-28.0, 28.0)), 2: ((-60.0, -51.0), (-75.0, -39.0)), 3: ((-22.0, -66.0), (-22.0, -90.0)),
    4: ((-80.0, -68.0), (-80.0, -81.0)), 5: ((-117.5, -70.0), (-117.5, -82.0)), 6: ((-62.0, 8.0), (-110.0, -10.0)),
    7: ((SITE1[0] + 17.0, SITE1[1] + sg.R), (SITE1[0], SITE1[1] + sg.R)),
    8: ((SITE2[0] - sg.R - sg.HALF_T - sg.PATH_W / 2, SITE2[1] - sg.R), (SITE2[0], SITE2[1] - sg.R)),
    9: ((S_AISLE, S_LOT[1] - 18.0), (S_AISLE, S_LOT[1] + 30.0)),
    10: ((118.0, 3.0), (60.0, 16.0)), 11: ((S_AISLE, S_LOT[1] + 4.0), (S_AISLE, S_LOT[3])), 12: ((90.0, 196.0), (112.0, 190.0)),
    13: ((92.0, 76.0), (118.0, 76.0)), 14: ((-74.0, -160.0), (-86.0, -160.0)), 15: ((54.0, -197.5), (10.0, -215.0)),
    16: ((-82.0, 0.0), (-160.0, 0.0)), 17: ((-90.0, -106.5), (-110.0, -130.0)),
    20: ((-174.0, 200.0), (-205.0, 196.0)), 21: ((-158.0, -160.0), (-192.0, -160.0)), 22: ((-176.0, 10.0), (-245.0, 10.0)),
    23: ((-3.0, -123.0), (30.0, -123.0)),
}
# точки мест свободны: деревья (группы елей против обзора и прочие) — не ближе 2,5 м
for key_ in ('pine', 'pine_slim', 'spruce_a', 'spruce_b', 'spruce_young'):
    TREES[key_] = [t_ for t_ in TREES[key_] if all(math.hypot(t_[0] - sp_[0][0], -t_[2] - sp_[0][1]) > 2.5
                                                    for sp_ in PLACE_SPOTS.values())]
# ================================================================ v13: СТРОЙПЛОЩАДКИ, ВАЛУНЫ, БЕСЕДКИ
# недостроенные коттеджи (владелец): фундамент; стены по пояс; коробка первого этажа с лесами и частью второго.
# Стены — кирпич 0,4 м кусками разной высоты, проёмы окон и дверей; вокруг — поддоны кирпича, штабели досок и
# блоков, бетонные кольца, куча песка, арматура, контейнер, бытовка (координаты — по листу коттеджа, с поворотом).
UNF_WALLS = [  # (x0, y0, x1, y1) кусков стен по листу коттеджа: юг с дверью, север с выходом на террасу, запад, восток
    (7.0, -205.0, 8.3, -205.0), (9.7, -205.0, 12.0, -205.0), (13.2, -205.0, 15.8, -205.0), (17.0, -205.0, 21.0, -205.0),
    (7.0, -193.0, 11.0, -193.0), (12.2, -193.0, 15.6, -193.0), (18.4, -193.0, 21.0, -193.0),
    (7.0, -205.0, 7.0, -201.0), (7.0, -199.8, 7.0, -193.0),
    (21.0, -205.0, 21.0, -204.2), (21.0, -202.8, 21.0, -197.0), (21.0, -195.8, 21.0, -193.0),
    (11.0, -205.0, 11.0, -202.6), (11.0, -201.4, 11.0, -199.0), (12.0, -199.0, 16.0, -199.0)]
urng = random.Random(53)


def ubox(cx, cy, k, lx0, ly0, lx1, ly1, z0, z1, m, solid=True):
    O.box(*cot_rect(cx, cy, k, lx0, ly0, lx1, ly1), z0, z1, m, solid)


def useg(cx, cy, k, a, b, t, z0, z1, m, solid=True):
    O.seg(cot_pt(cx, cy, k, *a), cot_pt(cx, cy, k, *b), t, z0, z1, m, solid, ext=t / 2)


UNF_SITES = []
for (ux, uy, uk, kind), lv in zip(UNFINISHED, UNF_LEVELS):
    item_next('site', 'Стройплощадка')
    hr = cot_rect(ux, uy, uk, 7.0, -205.0, 21.0, -193.0)
    base = rect_stat(*hr, fn=np.min) - 0.4
    top = lv + 0.35                                             # верх фундаментной плиты
    O.box(hr[0] - 0.3, hr[1] - 0.3, hr[2] + 0.3, hr[3] + 0.3, base, top, 'struct')
    if kind == 'foundation':                                    # плита и выпуски арматуры по углам и стенам
        for q in ((7.2, -204.8), (20.8, -204.8), (7.2, -193.2), (20.8, -193.2), (14.0, -204.8), (14.0, -193.2), (11.0, -199.0)):
            ux_, uy_ = cot_pt(ux, uy, uk, *q)
            O.box(ux_ - 0.2, uy_ - 0.2, ux_ + 0.2, uy_ + 0.2, top, top + 0.9, 'metal', solid=False)
        ubox(ux, uy, uk, 9.0, -203.0, 11.4, -201.4, top, top + 1.2, 'brick')         # блоки на плите
        ubox(ux, uy, uk, 15.0, -197.0, 17.5, -195.6, top, top + 0.9, 'brick')
    else:
        for a_x, a_y, b_x, b_y in UNF_WALLS:
            h_ = 3.4 if kind == 'frame' else urng.choice((0.9, 1.3, 1.8, 2.2, 2.6))
            useg(ux, uy, uk, (a_x, a_y), (b_x, b_y), 0.4, top, top + h_, 'brick')
        if kind == 'frame':                                     # перекрытие над половиной дома, стены второго этажа кусками
            ubox(ux, uy, uk, 7.0, -205.0, 14.0, -193.0, top + 3.4, top + 3.7, 'slab')
            for a_x, a_y, b_x, b_y in UNF_WALLS[:2] + UNF_WALLS[4:5] + UNF_WALLS[7:9]:
                useg(ux, uy, uk, (a_x, a_y), (min(b_x, 14.0), b_y), 0.4, top + 3.7, top + 3.7 + urng.choice((1.0, 1.8, 2.6)), 'brick')
            for j_ in range(7):                                 # леса вдоль северной стены: стойки и два настила
                lx_ = 7.0 + j_ * 14.0 / 6.0
                for ly_ in (-192.6, -191.3):
                    x_, y_ = cot_pt(ux, uy, uk, lx_, ly_)
                    O.box(x_ - 0.04, y_ - 0.04, x_ + 0.04, y_ + 0.04, top - 0.3, top + 6.6, 'metal', solid=False)
            for zz_ in (2.0, 4.1):
                ubox(ux, uy, uk, 7.0, -192.7, 21.0, -191.2, top + zz_, top + zz_ + 0.06, 'wood')
    # стройматериалы и бытовка вокруг
    for (lx_, ly_, w_, d_, h_, m_) in ((3.0, -208.0, 1.0, 1.2, 0.95, 'brick'), (4.6, -208.0, 1.0, 1.2, 0.95, 'brick'),
                                        (3.0, -204.0, 1.0, 1.2, 1.9, 'brick'), (25.0, -201.0, 1.1, 4.2, 0.6, 'wood'),
                                        (25.0, -196.0, 1.6, 2.4, 1.2, 'struct'), (14.0, -210.0, 6.0, 0.45, 0.35, 'metal'),
                                        (26.5, -190.0, 2.2, 4.2, 1.5, 'metal'), (-1.5, -198.0, 2.5, 6.0, 2.7, 'kiosk')):
        x_, y_ = cot_pt(ux, uy, uk, lx_, ly_)
        wx_, wy_ = (w_, d_) if uk % 2 == 0 else (d_, w_)
        g_ = min(h_at(x_ + sx_ * wx_ / 2, y_ + sy_ * wy_ / 2) for sx_ in (-1, 1) for sy_ in (-1, 1))
        O.box(x_ - wx_ / 2, y_ - wy_ / 2, x_ + wx_ / 2, y_ + wy_ / 2, g_ - 0.1, g_ + h_, m_)
    for lx_, ly_ in ((23.5, -208.5), (25.3, -208.5)):          # бетонные кольца
        x_, y_ = cot_pt(ux, uy, uk, lx_, ly_)
        O.cyl(x_, y_, h_at(x_, y_) - 0.1, h_at(x_, y_) + 0.9, 0.75, 'struct', sides=12)
    x_, y_ = cot_pt(ux, uy, uk, 0.0, -211.0)                    # куча песка
    for r_, z0_, z1_ in ((2.4, -0.2, 0.45), (1.6, 0.45, 0.95), (0.8, 0.95, 1.35)):
        O.cyl(x_, y_, h_at(x_, y_) + z0_, h_at(x_, y_) + z1_, r_, 'trail', sides=10)
    lab_ = {'foundation': 'стройка: фундамент', 'walls': 'стройка: стены по пояс', 'frame': 'стройка: коробка в лесах'}[kind]
    O.label(ux, uy, top + 5.0, lab_, 1.2, 'building')
    UNF_SITES.append({'at': [r3(ux), r3(-uy)], 'kind': kind, 'level': r3(top)})

# большие камни и валуны (владелец): на склоне крупные, у мыса гуще, в парке плато — поменьше; не на дорогах,
# дорожках, тропах, площадках, постройках и не ближе 2,5 м к деревьям и точкам мест; на набережной и молу нет
item()
rock_rng = random.Random(61)
tree_pts = [(t_[0], -t_[2]) for key_ in ('pine', 'pine_slim', 'spruce_a', 'spruce_b', 'spruce_young') for t_ in TREES[key_]]
ROCKS = []


def rock_ok(x, y, clear):
    if not PLAN['in_poly'](x, y, PLAN['boundary']) or blocked(x, y) or near_road(x, y, 2.5):
        return False
    if x < float(PLAN['foot_x'](y)) + 2.0 and y > -205.0:          # набережная и пляж у маршрутов — свободны
        return False
    if any(math.hypot(x - sp_[0][0], y - sp_[0][1]) < 3.0 for sp_ in PLACE_SPOTS.values()):
        return False
    if any(math.hypot(x - tx_, y - ty_) < clear for tx_, ty_ in tree_pts):
        return False
    return all(math.hypot(x - rx_, y - ry_) > clear + 2.0 for rx_, ry_, _ in ROCKS)


for zone_, n_, size_ in (('slope', 34, (2.0, 4.2)), ('cape', 14, (1.8, 3.8)), ('park', 30, (1.3, 2.6))):
    placed_ = 0
    for _ in range(4000):
        if placed_ >= n_:
            break
        if zone_ == 'cape':
            x_, y_ = rock_rng.uniform(-150.0, -40.0), rock_rng.uniform(-258.0, -200.0)
        else:
            y_ = rock_rng.uniform(-250.0, 240.0)
            if zone_ == 'slope':
                x_ = rock_rng.uniform(float(PLAN['foot_x'](y_)) + 3.0, float(PLAN['brow_x'](y_)) - 3.0)
            else:
                x_ = rock_rng.uniform(float(PLAN['brow_x'](y_)) + 5.0, 140.0)
        if not rock_ok(x_, y_, 2.5):
            continue
        L_ = rock_rng.uniform(*size_)
        ROCKS.append((x_, y_, L_))
        placed_ += 1
for x_, y_, L_ in ROCKS:
    item_next('rock', 'Валун')
    ang_ = rock_rng.uniform(0, 180)
    W_ = L_ * rock_rng.uniform(0.6, 0.85)
    H_ = L_ * rock_rng.uniform(0.45, 0.7)
    base_ = min(h_at(x_ + dx_, y_ + dy_) for dx_ in (-L_ / 2, L_ / 2) for dy_ in (-L_ / 2, L_ / 2)) - 0.4
    O.obox(x_, y_, L_, W_, base_, base_ + H_, ang_, 'rock')
    a2_ = math.radians(ang_ + 60)
    O.obox(x_ + math.cos(a2_) * L_ * 0.25, y_ + math.sin(a2_) * L_ * 0.25, L_ * 0.6, W_ * 0.7, base_, base_ + H_ * 0.8, ang_ + 35, 'rock')
    if rock_rng.random() < 0.5:
        a3_ = math.radians(ang_ - 120)
        O.obox(x_ + math.cos(a3_) * L_ * 0.2, y_ + math.sin(a3_) * L_ * 0.2, L_ * 0.45, W_ * 0.5, base_, base_ + H_ * 1.15, ang_ - 25, 'rock')
item()

# беседки в парке, у бровки, у посёлка (владелец): настил, столбы, кровля — как у тропы
for gx_, gy_ in PLAN['GAZEBOS_PARK']:
    if near_road(gx_, gy_, 4.0):
        WARN.append(f'беседка ({gx_}, {gy_}) — на дороге')
    item_next('gazebo', 'Беседка')
    lo_ = rect_stat(gx_ - 3.3, gy_ - 3.3, gx_ + 3.3, gy_ + 3.3, fn=np.min)
    zk_ = rect_stat(gx_ - 3.3, gy_ - 3.3, gx_ + 3.3, gy_ + 3.3, fn=np.max) + 0.25
    O.box(gx_ - 3.3, gy_ - 3.3, gx_ + 3.3, gy_ + 3.3, lo_ - 0.5, zk_, 'deck')
    for j_ in range(8):
        if j_ == 6:
            continue                                            # проход
        a_ = math.radians(22.5 + j_ * 45)
        O.cyl(gx_ + 2.3 * math.cos(a_), gy_ + 2.3 * math.sin(a_), zk_, zk_ + 2.4, 0.09, 'wood')
    O.cyl(gx_, gy_, zk_ + 2.4, zk_ + 2.7, 2.8, 'roof', solid=False, sides=8)
    O.label(gx_, gy_, zk_ + 3.3, 'беседка', 0.8, 'object')
    SURFACES.append(('rect', gx_ - 3.3, gy_ - 3.3, gx_ + 3.3, gy_ + 3.3, zk_))
item()

PLACES = []
for n_, x_, y_, text_ in PLAN['PLACES']:
    (sx_, sy_), (lx_, ly_) = PLACE_SPOTS[n_]
    z_ = ground_at(sx_, sy_)
    if n_ == 1:
        z_ = CENTRAL
    if n_ == 4:
        z_ = CENTRAL
    if n_ == 5:
        z_ = CENTRAL
    PLACES.append({'n': n_, 'name': f'{n_} · {text_.split(":")[0].split(",")[0]}', 'text': text_,
                   'at': [r3(sx_), r3(-sy_)], 'floor': r3(z_), 'look': [r3(lx_), r3(-ly_)], 'marker': [r3(x_), r3(-y_)]})
# главная ось: КПП → аллея → парковка → круг → лобби → терраса → каскад → набережная → «Стрелка» → маяк
# v11: корпус севернее оси — ствол от развилки, проезд к корпусу, вокруг фонтана, лобби, дорожка к террасе
MR = PLAN['MAIN_RECT']
axis = [(160.0, 0.0), (90.0, -2.0), (81.5, 6.0), (80.5, 24.0), (74.0, CIRCLE[1]), (CIRCLE[0] + CIRCLE[2] + 2.0, CIRCLE[1] + 1.0),
        (CIRCLE[0], CIRCLE[1] + 8.5), (CIRCLE[0] - 9.0, CIRCLE[1] + 6.0)]
axis_pts = [(x, y, ground_at(x, y)) for x, y in axis]
md = [d for d in main.ext_doors if d['o'] == 'v' and abs(d['c'] - MR[2]) < 0.1][0]
yd = md['mid'][1]
axis_pts += [(md['mid'][0] + 0.8, yd, CENTRAL), (md['mid'][0], yd, CENTRAL), (-28.0, yd, CENTRAL), (MR[0], yd, CENTRAL),
             (MR[0] - 4.0, yd, CENTRAL), (-60.0, CIRCLE[1], CENTRAL), (-66.0, 16.0, CENTRAL), (-80.0, 3.0, CENTRAL)]
axis_pts += [tuple((p[0], -p[2], p[1])) for p in ROUTES[[r['id'] for r in ROUTES].index('cascade')]['points'][1:]]
axis_pts += [(-135.0 - DS, 1.0, QUAY), (-141.0 - DS, -1.0, MOLE), (-160.0 - DS, -3.0, MOLE), (-205.0 - DS, -3.0, MOLE),
             (-250.0 - DS, -3.0, MOLE), (-262.0 - DS, -1.0, MOLE), (-279.0 - DS, 6.0, MOLE), (-283.0 - DS, 10.0, MOLE),
             (-284.4 - DS, 10.0, MOLE)]
SITE_ROUTES = [
    ('axis', 'Главная ось: КПП → круг с фонтаном → лобби → терраса → каскад → «Стрелка» → маяк', axis_pts),
    ('north_road', 'Ствол → северная ветка → дорога к парковке S-корпусов',
     [tuple(p) for p in PLAN['ROADS'][2][0]] + [(40.0, 223.6), (S_AISLE, 224.0), (S_AISLE, S_LOT[3] + 2.0)]),
    ('s_parking', 'Парковка S-корпусов ↔ дворы обоих корпусов',
     [(S_AISLE, 224.0), (S_AISLE, S_LOT[3] - 3.5), (S_LOT[0] - 1.5, S_LOT[3] - 3.5), (S_LOT[0] - 1.5, SITE1[1] + sg.R),
      (SITE1[0] + 4.0, SITE1[1] + sg.R), (S_LOT[0] - 1.5, SITE1[1] + sg.R), (S_LOT[0] - 1.5, S_LOT[3] - 3.5),
      (S_LOT[2] + 1.5, S_LOT[3] - 3.5), (S_LOT[2] + 1.5, SITE2[1] + sg.R), (SITE2[0] - 4.0, SITE2[1] + sg.R),
      (S_LOT[2] + 1.5, SITE2[1] + sg.R), (S_LOT[2] + 1.5, SITE2[1]),
      (SITE2[0] - sg.R - sg.HALF_T - sg.PATH_W / 2, SITE2[1] - sg.R)]),
    ('cottages_beach', 'Лесная улица посёлка → тропа → развилка у родника → серпантин → пляж',
     [(72.0, -170.0), (64.0, -188.0), (44.0, -206.0), (18.0, -214.0), (-8.0, -212.0)] + cot_xy[:COT_BROW_I] + [p for p in cot_path]
     + [p for p in trail_pts[J_I + 1:]]),
    ('south_branch', 'Развилка → южная ветка → лесная улица посёлка на восток',
     [(82.0, 0.0), (88.0, -40.0), (90.0, -80.0), (76.0, -128.0), (72.0, -170.0), (96.0, -178.0), (116.0, -190.0), (124.0, -212.0)]),
    ('quay_north', 'Набережная: от каскада на север к прокату и эллингу',
     [(BOTTOM_X - 3.3, 0.0), (-170.0, 30.0), (-172.0, 80.0), (-175.0, 128.0), (-179.5, 133.0), (-179.5, 146.0), (-188.0, 150.0),
      (-188.0, 186.0)]),
    ('quay_south', 'Набережная: от каскада на юг под скалой подиума к пляжу и спасателям',
     [(BOTTOM_X - 3.3, 0.0), (-172.0, -40.0), (-176.0, -80.0), (-176.0, -110.0), (-171.0, -114.0), (-171.0, -131.0), (-157.5, -134.0),
      (-157.3, -152.0)]),
    ('stage_trail', 'Под сценой амфитеатра → тропка → серпантин → пляж',
     [(-94.0, -160.0), (-98.5, -160.0)] + [p for p in STAGE_PATH] + [p for p in trail_pts[ST_I + 1:]]),
]
for rid, title, pts in SITE_ROUTES:
    p3 = []
    for p in pts:
        if len(p) == 3:
            p3.append(p)
        else:
            p3.append((p[0], p[1], ground_at(p[0], p[1])))
    ROUTES.append({'id': rid, 'label': title, 'kind': 'site', 'points': [gpt(*p) for p in p3],
                   'checks': [[len(p3) - 1, f'{rid}/конец', r3(p3[-1][2])]]})
# пешком нельзя: с набережной в озеро, через забор на восток
NEG = [('quay_water', 'С набережной в озеро не сойти', (-180.0, 60.0), (-220.0, 60.0), float(shore_x(60.0)) - 0.6),
       ('fence_east', 'Через забор на восток не пройти', (140.0, 120.0), (190.0, 120.0),
        150.0 + 10.0 * math.sin(120.0 / 55.0) + 0.6)]


# ================================================================ ВИДЫ ДЛЯ СНИМКОВ (глаз на 1,62 над полом/землёй)
def eye(x, y, z=None):
    return gpt(x, y, (ground_at(x, y) if z is None else z) + 1.62)


SHOT_VIEWS = [
    {'id': '00_overview', 'at': gpt(-40, -260, 330), 'look': gpt(-40, 0, 20)},
    {'id': '00_from_lake', 'at': gpt(-375, -40, 40), 'look': gpt(-100, -10, 26)},
    {'id': '00_terrace_dam', 'at': eye(-74, 6), 'look': gpt(-700, -700, 120)},
    {'id': '00_cascade_below', 'at': eye(BOTTOM_X - 8.0, 0), 'look': gpt(-112, 4, 20)},
    {'id': '00_cascade_gallery', 'at': eye((GALLERIES[1]['walk'][0] + GALLERIES[1]['walk'][2]) / 2, N_END - 4.0, GALLERIES[1]['start']['z_top']),
     'look': gpt((GALLERIES[1]['walk'][0] + GALLERIES[1]['walk'][2]) / 2, S_END, GALLERIES[1]['end']['z_top'])},
    {'id': '00_mole_lighthouse', 'at': eye(-289.0 - DS, 14.0, LH_GAL), 'look': gpt(-170 - DS, 10, 3)},
    {'id': '00_s_courtyard', 'at': eye(SITE1[0] + 16.0, SITE1[1] + sg.R + 3.0), 'look': gpt(SITE1[0] - 10.0, SITE1[1] + sg.R, S_LEVELS['С-1'] + 3.0)},
    {'id': '00_s_unit_living', 'at': eye(*sg_unit_point('С-1', 3, 6.6, 3.2)), 'look': gpt(*sg_unit_point('С-1', 3, 4.2, 12.0), S_LEVELS['С-1'] + 1.6)},
    {'id': '00_s_unit_bedroom', 'at': eye(*sg_unit_point('С-1', 3, 6.9, 4.2), S_LEVELS['С-1'] + 0.15 + sg.FLOOR_TO_FLOOR),
     'look': gpt(*sg_unit_point('С-1', 3, 4.0, 12.5), S_LEVELS['С-1'] + 0.15 + sg.FLOOR_TO_FLOOR + 1.4)},
    {'id': '00_s_parking', 'at': eye(S_AISLE, S_LOT[1] - 4.0), 'look': gpt(S_AISLE, S_LOT[3] - 2.0, S_LEVELS['С-1'] + 2.0)},
    {'id': '00_amph_promenade', 'at': eye(AC[0] + 28.0, AC[1] + 18.0, PROM), 'look': gpt(AC[0] - 16, AC[1], ORCH)},
    {'id': '00_lobby', 'at': eye(MR[2] - 4.0, MR[1] + 32.0, CENTRAL), 'look': gpt(MR[0], MR[1] + 22.0, CENTRAL + 2.0)},
    {'id': '00_pool', 'at': eye(-62, -92, CENTRAL), 'look': gpt(-96, -80, CENTRAL + 1.0)},
    {'id': '00_pool_rock', 'at': eye(-166.0, -84.0), 'look': gpt(-114.0, -84.0, 22.0)},
    {'id': '00_cottages', 'at': eye(56.0, -199.0), 'look': gpt(4.0, -214.0, h_at(4.0, -214.0) + 3.0)},
    {'id': '00_construction', 'at': eye(77.0, -137.0), 'look': gpt(94.0, -150.0, h_at(94.0, -150.0) + 2.5)},
    {'id': '00_main_circle', 'at': eye(CIRCLE[0] + 26.0, CIRCLE[1] - 3.0), 'look': gpt(MR[0] + 10.0, MR[1] + 20.0, CENTRAL + 4.0)},
    {'id': '00_trail', 'at': eye(*trail_pts[J_I + 3][:2]), 'look': gpt(*trail_pts[min(len(trail_pts) - 1, J_I + 16)][:2], trail_pts[min(len(trail_pts) - 1, J_I + 16)][2] - 1.0)},
    {'id': '00_trail_spring', 'at': eye(*trail_pts[max(0, J_I - 6)][:2]), 'look': gpt(SPRING[0], SPRING[1], J_LAND[2] + 0.6)},
    # земля под ногами (владелец 2026-11-08: однообразно, виден повтор): газон плато, пляж, вид вниз, лесной склон
    {'id': '00_ground_lawn', 'at': eye(30.0, -150.0), 'look': gpt(4.0, -166.0, h_at(4.0, -166.0))},
    {'id': '00_ground_down', 'at': eye(30.0, -150.0), 'look': gpt(28.0, -153.0, h_at(28.0, -153.0))},
    {'id': '00_ground_beach', 'at': eye(float(shore_v((BEACH[0] + BEACH[1]) / 2)) + 7.0, (BEACH[0] + BEACH[1]) / 2 + 18.0), 'look': gpt(float(shore_v((BEACH[0] + BEACH[1]) / 2)) + 4.0, (BEACH[0] + BEACH[1]) / 2 - 30.0, 0.0)},
    {'id': '00_ground_shore', 'at': eye(float(shore_v((BEACH[0] + BEACH[1]) / 2 - 20.0)) + 2.5, (BEACH[0] + BEACH[1]) / 2 - 20.0), 'look': gpt(float(shore_v((BEACH[0] + BEACH[1]) / 2 - 26.0)) - 6.0, (BEACH[0] + BEACH[1]) / 2 - 26.0, -0.5)},
    {'id': '00_ground_slope', 'at': eye(float(brow_v(60.0)) - 6.0, 60.0), 'look': gpt(float(brow_v(60.0)) - 34.0, 52.0, h_at(float(brow_v(60.0)) - 34.0, 52.0))},
]

# ================================================================ ЗАПИСЬ
TERRAIN_DIR.mkdir(parents=True, exist_ok=True)
H_FINAL.astype('<f4').tofile(TERRAIN_DIR / 'sanatorium_heights.r32')
far_h.astype('<f4').tofile(TERRAIN_DIR / 'sanatorium_far.r32')


def splat_for(X, Y, Hf, detail):
    s = shore_v(np.clip(Y, -300, 300))
    wb = np.clip((Y - BEACH[0]) / 8.0, 0.0, 1.0) * np.clip((BEACH[1] - Y) / 8.0, 0.0, 1.0)
    q = s + QUAY_W + (BEACH_W - QUAY_W) * wb
    quay = (X >= s - 0.5) & (X < q) & (Hf < 3.0)
    gravel = np.where(quay, 1.0 - wb * 0.3, 0.0)
    mud = np.zeros_like(X)
    floor_ = np.clip((Hf - 4.0) / 6.0, 0.0, 1.0) * 0.55
    rock = np.where(Hf < -0.5, 0.6, 0.0)
    if detail:
        rock = np.maximum(rock, np.clip(CARVE / 3.0, 0.0, 0.95))       # скала под подиумом
        for rb in RIBBONS:
            for a, b in zip(rb['pts'], rb['pts'][1:]):
                x0, x1 = min(a[0], b[0]), max(a[0], b[0])
                y0, y1 = min(a[1], b[1]), max(a[1], b[1])
                sj, si = grid_window(x0, y0, x1, y1, 6)
                d, _ = seg_dist(X[sj, si], Y[sj, si], a, b)
                mud[sj, si] = np.maximum(mud[sj, si], np.clip(1 - (d - rb['w'] / 2) / 3.0, 0, 1))
    return np.stack([mud, rock, np.clip(gravel, 0, 1), floor_], -1)


def ground_masks():
    """Маски восьми грунтов земли «Санатория» (шейдер sanatorium_ground, владелец 2026-11-08: земля не однообразная):
    A — R вытоптанный газон, G хвоя, B мох, A тропа; B — R гранит, G щебень, B песок, A сырость у воды. Газон — всё
    остальное на плато. Хвоя — под кронами (по деревьям) и на лесном склоне; мох пятнами в лесу, у валунов и на северных
    склонах; вытоптано — у асфальта, дорожек, построек и пятнами; тропы — ленты троп и грунтовки; щебень — хоздвор,
    стройки, набережная до мощения, обочины; песок — пляж и дно у пляжа; гранит — скала под подиумом, у валунов, мыс."""
    from PIL import ImageDraw
    from scipy.ndimage import distance_transform_edt, gaussian_filter
    X, Y, Hf = GX, GY, H_FINAL
    shape = X.shape
    rng_ = np.random.default_rng(5)

    def smooth_noise(sigma):
        f = gaussian_filter(rng_.random(shape), sigma)
        return (f - f.min()) / (f.max() - f.min() + 1e-9)
    n_big, n_mid, n_fine = smooth_noise(16.0), smooth_noise(5.0), smooth_noise(2.0)
    sh = shore_v(np.clip(Y, -300, 300))
    wb = np.clip((Y - BEACH[0]) / 8.0, 0.0, 1.0) * np.clip((BEACH[1] - Y) / 8.0, 0.0, 1.0)
    foot = sh + QUAY_W + (BEACH_W - QUAY_W) * wb
    brow = brow_v(np.clip(Y, -300, 300))
    land = X > sh
    slope = (X > foot + 1.0) & (X < brow - 1.0)
    plateau = X >= brow - 1.0

    def to_px(x, y):
        return (x - GRID_X[0]) / STEP, (GRID_Y[1] - y) / STEP

    def raster(draw_fn):
        im = Image.new('L', (shape[1], shape[0]), 0)
        draw_fn(ImageDraw.Draw(im))
        return np.asarray(im, dtype=np.float32) / 255.0
    # твёрдое: асфальт, площадки, дорожки, постройки — от него «вытоптано» и обочины
    def draw_hard(d):
        for pts_, w_ in PLAN['ROADS']:
            d.line([to_px(*q_) for q_ in pts_], fill=255, width=max(1, int(round(w_ / STEP))), joint='curve')
        for pts_, w_ in PAVED:
            d.line([to_px(*q_) for q_ in pts_], fill=255, width=max(1, int(round(w_ / STEP))), joint='curve')
        for r_ in LOTS:
            d.rectangle([to_px(r_[0], r_[3]), to_px(r_[2], r_[1])], fill=255)
        for bb in BLD.values():
            for r_ in bb.floors[bb.order[0]]['rooms']:
                x0_, y0_, x1_, y1_ = r_['rect']
                d.rectangle([to_px(x0_, y1_), to_px(x1_, y0_)], fill=255)
    hard = raster(draw_hard) > 0.5
    d_hard = distance_transform_edt(~hard) * STEP
    def draw_roads(d):
        for pts_, w_ in PLAN['ROADS']:
            d.line([to_px(*q_) for q_ in pts_], fill=255, width=max(1, int(round(w_ / STEP))), joint='curve')
    d_road = distance_transform_edt(~(raster(draw_roads) > 0.5)) * STEP
    # кроны: точки деревьев, размытые до пятна подстилки
    canopy = np.zeros(shape, np.float32)
    for key_, k_ in (('pine', 1.0), ('pine_slim', 0.8), ('spruce_a', 1.3), ('spruce_b', 1.3), ('spruce_young', 0.7)):
        for t_ in TREES[key_]:
            c_, r_ = to_px(t_[0], -t_[2])
            ci, ri = int(round(c_)), int(round(r_))
            if 0 <= ri < shape[0] and 0 <= ci < shape[1]:
                canopy[ri, ci] += k_ * float(t_[4])
    canopy = np.clip(gaussian_filter(canopy, 3.0) * 30.0, 0.0, 1.0)
    # склон: подстилка с прогалинами травы (крупный шум), на плато — пятна под кронами
    glade = np.clip((n_big - 0.58) * 4.0, 0.0, 1.0)
    forest = np.maximum(canopy, np.where(slope, 0.85 * (1.0 - 0.8 * glade), 0.0)) * land
    forest = np.clip(forest * (0.75 + 0.5 * n_mid), 0.0, 1.0)
    # мох: пятна в лесу, у валунов, на северных склонах (высота растёт к югу — склон смотрит на север)
    grad_n = np.gradient(Hf, axis=0) / STEP
    moss = forest * np.clip((n_mid - 0.46) * 4.0, 0.0, 1.0) * np.clip((n_fine - 0.3) * 3.0, 0.0, 1.0)
    moss = np.maximum(moss, forest * np.clip(grad_n * 0.9, 0.0, 0.55))
    # дно озера: камень вперемешку со щебнем (горное озеро), у пляжа — песок (ниже)
    rock_m = np.where(Hf < -0.5, 0.35 + 0.5 * n_mid, 0.0) + np.clip(CARVE / 3.0, 0.0, 0.95)
    for rx_, ry_, rl_ in ROCKS:
        c_, r_ = to_px(rx_, ry_)
        sj, si = grid_window(rx_ - rl_ * 1.4, ry_ - rl_ * 1.4, rx_ + rl_ * 1.4, ry_ + rl_ * 1.4)
        dd = np.hypot(X[sj, si] - rx_, Y[sj, si] - ry_)
        moss[sj, si] = np.maximum(moss[sj, si], np.clip(1.0 - (dd - rl_ * 0.5) / (rl_ * 0.9), 0.0, 1.0) * 0.8)
        rock_m[sj, si] = np.maximum(rock_m[sj, si], np.clip(1.0 - dd / (rl_ * 0.7), 0.0, 1.0) * 0.55)
    # мыс: каменистые выходы у южной кромки
    cape = np.clip((south_v(X) + 22.0 - Y) / 14.0, 0.0, 1.0) * land
    rock_m = np.maximum(rock_m, cape * np.clip((n_mid - 0.45) * 3.0, 0.0, 0.8))
    # вытоптано: у твёрдого и пятнами на плато
    worn = np.clip(1.0 - d_hard / 3.0, 0.0, 1.0) * 0.75 * (0.7 + 0.6 * n_fine)
    worn = np.maximum(worn, np.clip((n_big - 0.56) * 3.0, 0.0, 0.75) * np.clip((n_fine - 0.25) * 2.5, 0.0, 1.0) * plateau)
    # тропы: ленты троп, грунтовки и тропа от коттеджей по плато, стройплощадки, обочины
    trail = np.zeros(shape, np.float32)
    lines_ = [(rb_['pts'], rb_['w']) for rb_ in RIBBONS] + [(pts_, w_) for pts_, w_ in PLAN['TRACKS']] + \
             [([tuple(q_) for q_ in cot_xy[:COT_BROW_I + 1]], 2.4)]
    for pts_, w_ in lines_:
        for a_, b_ in zip(pts_, pts_[1:]):
            sj, si = grid_window(min(a_[0], b_[0]), min(a_[1], b_[1]), max(a_[0], b_[0]), max(a_[1], b_[1]), 6)
            dd, _ = seg_dist(X[sj, si], Y[sj, si], a_, b_)
            trail[sj, si] = np.maximum(trail[sj, si], np.clip(1.0 - (dd - w_ / 2) / 1.6, 0.0, 1.0))
    trail = np.maximum(trail, np.clip(1.0 - np.abs(d_road - 1.2) / 1.2, 0.0, 1.0) * 0.35 * (0.6 + 0.8 * n_fine) * plateau)
    gravel = np.zeros(shape, np.float32)
    def rect_w(x0_, y0_, x1_, y1_, v_, soft=3.0):
        dx_ = np.maximum(np.maximum(x0_ - X, X - x1_), 0.0)
        dy_ = np.maximum(np.maximum(y0_ - Y, Y - y1_), 0.0)
        return np.clip(1.0 - np.hypot(dx_, dy_) / soft, 0.0, 1.0) * v_
    gravel = np.maximum(gravel, rect_w(*HOZ_RECT, 0.9))
    for u_ in UNFINISHED:
        gravel = np.maximum(gravel, rect_w(u_[0] - 12.0, u_[1] - 12.0, u_[0] + 12.0, u_[1] + 12.0, 0.75, 5.0) * (0.6 + 0.6 * n_fine))
        trail = np.maximum(trail, rect_w(u_[0] - 15.0, u_[1] - 15.0, u_[0] + 15.0, u_[1] + 15.0, 0.5, 4.0) * n_mid)
    quay = land & (X < foot) & (Hf < 3.0)
    gravel = np.maximum(gravel, np.where(quay, 0.85 * (1.0 - wb), 0.0))
    gravel = np.maximum(gravel, np.clip(1.0 - np.abs(d_road - 0.8) / 0.9, 0.0, 1.0) * 0.4 * plateau)
    sand = np.where((X < foot) & (X > sh - 30.0), wb, 0.0)
    sand = np.maximum(sand, np.where((Hf < 0.4) & (X > sh - 30.0) & (wb > 0.0), wb, 0.0))
    wet = np.clip(1.0 - (X - sh) / 5.0, 0.0, 1.0) * (Hf < 1.4) * (X > sh - 3.0)
    # лес не лежит на песке, щебне, тропах; мох — только в лесу
    gravel = np.maximum(gravel, np.where(Hf < -0.5, 0.75 * (1.0 - n_mid), 0.0))
    forest *= (1.0 - sand) * (1.0 - gravel * 0.8) * (1.0 - moss * 0.7)
    moss *= (1.0 - sand)
    A = np.stack([worn, forest, moss, trail], -1)
    B = np.stack([rock_m, gravel, sand, wet], -1)
    return np.clip(A, 0, 1), np.clip(B, 0, 1)


def grass_density(GA, GB):
    """Густота травяного покрова (DistrictGrass: травинки и пучки высокой травы, бурьян, одуванчики) — 1 пиксель = 1 м,
    та же сетка, что у масок. R — трава (до 0,22 — травинки гуще, дальше — больше пучков некошеной травы), G — сорняки.
    Растёт там, где газон и вытоптанный газон; нет — под постройками, лестницами, дорожками, площадками, на песке,
    щебне, гранитe, тропах, в лесной подстилке и у воды: всё, что стоит на земле или чуть выше (коробки, марши, ленты,
    цилиндры, треугольники генератора), вырезает траву своим следом (иначе травинки торчат из пола)."""
    from PIL import ImageDraw
    from scipy.ndimage import binary_dilation, gaussian_filter
    X, Y, Hf = GX, GY, H_FINAL
    rows, cols = X.shape
    im = Image.new('L', (cols, rows), 0)
    d = ImageDraw.Draw(im)

    def px(x, y):
        return (x - GRID_X[0]) / STEP, (GRID_Y[1] - y) / STEP

    def g_at(x, y):
        c = int(round((x - GRID_X[0]) / STEP))
        r = int(round((GRID_Y[1] - y) / STEP))
        return float(Hf[min(max(r, 0), rows - 1), min(max(c, 0), cols - 1)])

    def near_ground(z0, z1, x, y):
        g = g_at(x, y)
        return z0 <= g + 0.7 and z1 >= g - 0.15

    def strip(a, b, w):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        if ln < 1e-6:
            return
        nx, ny = -dy / ln * w / 2, dx / ln * w / 2
        d.polygon([px(a[0] + nx, a[1] + ny), px(b[0] + nx, b[1] + ny), px(b[0] - nx, b[1] - ny), px(a[0] - nx, a[1] - ny)], fill=255)
    for bx in O.boxes:
        cx, cz_, cy = bx[0], bx[1], -bx[2]
        lx, h, ly, ang = bx[3], bx[4], bx[5], math.radians(bx[6])
        if not near_ground(cz_ - h / 2, cz_ + h / 2, cx, cy):
            continue
        ux, uy = math.cos(ang) * lx / 2, math.sin(ang) * lx / 2
        vx, vy = -math.sin(ang) * ly / 2, math.cos(ang) * ly / 2
        d.polygon([px(cx + ux + vx, cy + uy + vy), px(cx - ux + vx, cy - uy + vy), px(cx - ux - vx, cy - uy - vy),
                   px(cx + ux - vx, cy + uy - vy)], fill=255)
    for st in O.stairs:
        a, b = (st[0], -st[2]), (st[3], -st[5])
        if min(st[1], st[4]) <= g_at(*a) + 0.7 or min(st[1], st[4]) <= g_at(*b) + 0.7:
            strip(a, b, st[6] + 0.6)
    for bm in O.beams:
        a, b = (bm[0], -bm[2]), (bm[3], -bm[5])
        if bm[1] <= g_at(*a) + 0.9 or bm[4] <= g_at(*b) + 0.9:
            strip(a, b, bm[6] + 0.4)
    for cyl in O.cyls:
        cx, cy, r_ = cyl[0], -cyl[2], cyl[3]
        if near_ground(cyl[1], cyl[1] + cyl[4], cx, cy):
            d.ellipse([px(cx - r_ - 0.3, cy + r_ + 0.3), px(cx + r_ + 0.3, cy - r_ - 0.3)], fill=255)
    for key, flat in O.tris.items():
        for k in range(0, len(flat), 9):
            pts = [(flat[k + j * 3], flat[k + j * 3 + 1], -flat[k + j * 3 + 2]) for j in range(3)]
            if min(p_[1] - g_at(p_[0], p_[2]) for p_ in pts) <= 0.7:
                d.polygon([px(p_[0], p_[2]) for p_ in pts], fill=255)
    covered = np.asarray(im) > 0
    covered = binary_dilation(covered, iterations=1)            # травинки у края пола не торчат сквозь плинтус
    worn, forest, moss, trail = (GA[..., i] for i in range(4))
    rock_m, gravel, sand, wet = (GB[..., i] for i in range(4))
    other = np.max(np.stack([worn, forest, moss, trail, rock_m, gravel, sand]), 0)
    lawn = 1.0 - other
    rng_ = np.random.default_rng(17)
    clumps = gaussian_filter(rng_.random(X.shape), 3.0)
    clumps = (clumps - clumps.min()) / (clumps.max() - clumps.min() + 1e-9)
    tall = gaussian_filter(rng_.random(X.shape), 9.0)
    tall = (tall - tall.min()) / (tall.max() - tall.min() + 1e-9)
    land = (X > shore_v(np.clip(Y, -300, 300)) + 1.5) & (Hf > 0.7)
    # газон: травинки сплошь, пучков некошеной травы — пятнами (крупный шум); вытоптанный — реже; лесная подстилка —
    # редкие пучки на прогалинах
    R = np.clip((lawn - 0.4) / 0.4, 0.0, 1.0) * (0.25 + 0.5 * tall)
    R = np.maximum(R, np.clip(worn - trail, 0.0, 1.0) * 0.16 * (0.5 + clumps))
    R = np.maximum(R, forest * (1.0 - moss) * np.clip((clumps - 0.62) * 3.0, 0.0, 1.0) * 0.12)
    G = np.clip((lawn - 0.3) / 0.5, 0.0, 1.0) * (0.15 + 0.45 * clumps) + worn * 0.25 * clumps
    # круче ~35° — камень и осыпь (шейдер кладёт гранит), травы нет
    gy_, gx_ = np.gradient(Hf, STEP)
    flat_k = np.clip((0.72 - np.hypot(gx_, gy_)) / 0.3, 0.0, 1.0)
    keep = (land & ~covered) * flat_k
    keep_k = keep * (1.0 - np.clip(sand + gravel + rock_m + trail * 1.5 + wet, 0.0, 1.0))
    R *= keep_k
    G *= keep_k
    return np.stack([R, G, np.zeros_like(R)], -1), float(covered.mean())


GA, GB = ground_masks()
GRASS, GRASS_COVER = grass_density(GA, GB)
Image.fromarray((np.clip(GRASS, 0, 1) * 255).astype(np.uint8), 'RGB').save(TERRAIN_DIR / 'sanatorium_grass.png')
Image.fromarray((GA * 255).astype(np.uint8), 'RGBA').save(TERRAIN_DIR / 'sanatorium_splat.png')
Image.fromarray((GB * 255).astype(np.uint8), 'RGBA').save(TERRAIN_DIR / 'sanatorium_splat2.png')
Image.fromarray((np.clip(splat_for(FGX, FGY, far_h, False), 0, 1) * 255).astype(np.uint8), 'RGBA').save(TERRAIN_DIR / 'sanatorium_far_splat.png')
TEX = {'albedo_array': 'res://assets/terrain/zone01_albedo.jpg', 'normal_array': 'res://assets/terrain/zone01_normal.jpg',
       'arm_array': 'res://assets/terrain/zone01_arm.jpg', 'noise': 'res://assets/terrain/zone01_noise.png'}
# земля «Санатория»: восемь грунтов 4K (tools/build_sanatorium_ground.py) — газон, вытоптанный газон, хвоя, мох, тропа,
# гранит, щебень, песок; плитка — по размеру скана, яркость фотографий выровнена (линейный множитель)
GROUND_TEX = {'albedo_array': 'res://assets/terrain/sanatorium_albedo.jpg', 'normal_array': 'res://assets/terrain/sanatorium_normal.jpg',
              'arm_array': 'res://assets/terrain/sanatorium_arm.jpg', 'noise': 'res://assets/terrain/zone01_noise.png'}
OUT_TER.write_text(json.dumps({'terrain': {
    'heights': 'res://data/terrain/sanatorium_heights.r32', 'origin': [GRID_X[0], -GRID_Y[1]], 'grid': [len(XS), len(YS)],
    'step': STEP, 'layer_tiles': [2.0, 2.4, 2.4, 3.0, 3.2, 4.0, 2.2, 2.6],
    'layer_gain': [0.86, 0.56, 0.6, 0.72, 1.0, 1.9, 0.58, 1.9], 'textures': GROUND_TEX,
    'splat_file': 'res://data/terrain/sanatorium_splat.png', 'splat2_file': 'res://data/terrain/sanatorium_splat2.png'}},
    ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
OUT_FAR.write_text(json.dumps({'terrain': {
    'heights': 'res://data/terrain/sanatorium_far.r32', 'origin': [float(FX[0]), float(-FY[0])], 'grid': [len(FX), len(FY)],
    'step': 10.0, 'layer_tiles': [3.0, 3.0, 2.5, 3.0, 4.0, 2.0], 'textures': TEX,
    'splat_file': 'res://data/terrain/sanatorium_far_splat.png'}}, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
OUT_VEG.write_text(json.dumps(TREES, ensure_ascii=False, separators=(',', ':')), encoding='utf-8', newline='\n')

PLAN_IMG = 'res://' + Path(PLAN['OUT']).resolve().relative_to(ROOT).as_posix()      # схема участка — текущей версии
pad_, top_, sc_ = PLAN['PAD'], PLAN['TOP'], PLAN['SCALE']
crop = [0, 0, int(pad_ * 2 + (PLAN['XMAX'] - PLAN['XMIN']) * sc_), int(top_ + pad_ * 2 + (PLAN['YMAX'] - PLAN['YMIN']) * sc_)]
x_left = PLAN['XMIN'] - pad_ / sc_
x_right = PLAN['XMIN'] + (crop[2] - pad_) / sc_
y_top = PLAN['YMAX'] + (top_ + pad_) / sc_
y_bottom = PLAN['YMAX'] - (crop[3] - top_ - pad_) / sc_

result = {
    'version': 1,
    'name': 'Санаторий',
    'purpose': 'Карта «Санаторий» — серый блокаут: участок v10 (номер S × 1,3, бассейн 32,5 × 22), здания по принятым планам, спуски, мол «Стрелка»',
    'north': '-Z',
    'y_offset': 0.0,
    'scale': {'width_k': 1.3, 'height_k': 1.15, 'door': [1.17, 2.42], 'rule': 'E'},
    'walkable': [GRID_X[0], GRID_X[1], -GRID_Y[1], -GRID_Y[0]],
    'mats': MATS,
    'boxes': O.boxes, 'stairs': O.stairs, 'beams': O.beams, 'cyls': O.cyls,
    'tris': O.tris, 'labels': O.labels, 'water': O.water, 'barriers': O.barriers, 'markers': O.markers,
    'rooms': ROOMS, 'routes': ROUTES, 'places': PLACES, 'exits': EXITS, 'spawns': SPAWNS,
    'negative': [{'id': i, 'label': t, 'from': [r3(a[0]), r3(-a[1])], 'to': [r3(b[0]), r3(-b[1])], 'stop_x': s} for i, t, a, b, s in NEG],
    'buildings': BUILDINGS,
    'levels': {'central': CENTRAL, 's_corps': S_LEVELS, 'cottages': COT_LEVELS, 'hozdvor': HOZ_LEVEL, 'playground': PG_LEVEL,
               'sport': SPORT_LEVEL, 'orchestra': ORCH, 'stage': STAGE, 'under_stage': UNDER, 'promenade': PROM, 'mole': MOLE,
               'quay': QUAY},
    'dam': {'center': [r3(DC[0]), r3(-DC[1])], 'radius': r3(DR), 'height': DAM_H, 'ends': [[r3(E1[0]), r3(-E1[1])], [r3(E2[0]), r3(-E2[1])]]},
    'views': SHOT_VIEWS,
    'plan_image': PLAN_IMG, 'plan_image_crop': crop, 'plan_image_rect': [r3(x_left), r3(-y_top), r3(x_right), r3(-y_bottom)],
    'deviations': DEVIATIONS,
    'stats': {'boxes': len(O.boxes), 'stairs': len(O.stairs), 'beams': len(O.beams), 'cyls': len(O.cyls),
              'tris': sum(len(v) // 9 for v in O.tris.values()), 'rooms': len(ROOMS), 'routes': len(ROUTES),
              'trees': sum(len(v) for v in TREES.values())},
    # метки групп (параллельно спискам выше) и их заголовки — для переноса в сцены построек
    'tags': {'boxes': O.boxes.tags, 'stairs': O.stairs.tags, 'beams': O.beams.tags, 'cyls': O.cyls.tags, 'tris': O.tri_tags,
             'labels': O.labels.tags, 'water': O.water.tags, 'barriers': O.barriers.tags, 'markers': O.markers.tags,
             'rooms': ROOMS.tags, 'routes': ROUTES.tags},
    'group_titles': GROUP_TITLES,
}
OUT_PLAN.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')), encoding='utf-8', newline='\n')

SCENE = f'''[gd_scene load_steps=6 format=3]

[ext_resource type="Script" path="res://src/blockout/sanatorium_level.gd" id="level"]
[ext_resource type="Script" path="res://src/blockout/heli_terrain.gd" id="terrain"]
[ext_resource type="Script" path="res://src/blockout/sanatorium_ground.gd" id="ground"]
[ext_resource type="Script" path="res://src/world/district_grass.gd" id="grass"]
[ext_resource type="Script" path="res://src/blockout/sanatorium_landscape.gd" id="land"]

[node name="SanatoriumStudy" type="Node3D"]
script = ExtResource("level")
metadata/purpose = "Карта «Санаторий» — серый блокаут (tools/build_sanatorium.py; прогулка — tools/sanatorium_study.cmd)"

[node name="Terrain" type="Node3D" parent="."]
script = ExtResource("ground")
data_path = "res://data/blockouts/sanatorium_terrain.json"
lod_ranges = Vector2(480, 1600)
tile_cells = 64
detail_rect = Rect2({GRID_X[0]}, {-GRID_Y[1]}, {GRID_X[1] - GRID_X[0]}, {GRID_Y[1] - GRID_Y[0]})
collision_rect = Rect2({GRID_X[0]}, {-GRID_Y[1]}, {GRID_X[1] - GRID_X[0]}, {GRID_Y[1] - GRID_Y[0]})

[node name="Grass" type="Node3D" parent="."]
script = ExtResource("grass")
density_map = "res://data/terrain/sanatorium_grass.png"
origin = Vector2({GRID_X[0] - STEP / 2}, {-GRID_Y[1] - STEP / 2})
models = PackedStringArray("res://assets/zone01/models/ug_grass_tall_a.glb", "res://assets/zone01/models/ug_grass_tall_b.glb", "res://assets/zone01/models/ug_grass_small.glb", "res://assets/zone01/models/ug_grass_mid_b.glb", "res://assets/zone01/models/ug_grass2_c.glb")
weed_models = PackedStringArray("res://assets/zone01/models/ug_weed_a.glb", "res://assets/zone01/models/ug_weed_b.glb", "res://assets/zone01/models/ug_dandelion_c.glb", "res://assets/zone01/models/ug_dandelion_e.glb")
tint = Color(0.7, 0.82, 0.52, 1)
lawn_dryness = 0.22

[node name="FarTerrain" type="Node3D" parent="."]
script = ExtResource("terrain")
data_path = "res://data/blockouts/sanatorium_far_terrain.json"
lod_ranges = Vector2(2600, 6000)
tile_cells = 32
detail_rect = Rect2(-2400, -1400, 3600, 3400)
collision_rect = Rect2(900000, 900000, 1, 1)

[node name="Landscape" type="Node3D" parent="."]
script = ExtResource("land")
'''
OUT_SCENE.write_text(SCENE, encoding='utf-8', newline='\n')

for w in WARN:
    print('ВНИМАНИЕ:', w)
for d_ in DEVIATIONS:
    print('ОТСТУПЛЕНИЕ:', d_)
st_ = result['stats']
print(f"санаторий: коробок {st_['boxes']}, маршей {st_['stairs']}, лент {st_['beams']}, цилиндров {st_['cyls']}, "
      f"треугольников {st_['tris']}, помещений {st_['rooms']}, обходов {st_['routes']}, деревьев {st_['trees']} (из них в группах елей против длинного обзора {BREAK_TREES})")
print(f"уровни: S {S_LEVELS}, коттеджи {COT_LEVELS}, хоздвор {HOZ_LEVEL}, площадка {PG_LEVEL}, корты {SPORT_LEVEL}")
print(f"→ {OUT_PLAN} ({OUT_PLAN.stat().st_size // 1024} КБ), {OUT_SCENE}; групп {len(GROUP_TITLES)}")
