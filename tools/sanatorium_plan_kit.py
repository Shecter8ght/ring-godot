# -*- coding: utf-8 -*-
"""Общие функции поэтажных планов санатория: стены и двери по общим границам, проверка связей, рисование.

Помещение — кортеж (id, название, x0, y0, x1, y1, вид, признаки); дверь — (a, b, t, ширина), где b — другое
помещение или 'out' (тогда t = (сторона 'E'/'W'/'N'/'S', доля вдоль стены)). Координаты — метры игры на схеме
участка (x — на восток, y — на север).
"""
import math
from collections import deque

from PIL import ImageFont

EPS = 0.05
DOOR = 1.17          # проём 0,9 × 1,3
DOOR2 = 2.4          # двустворчатая
OPEN = 6.0           # открытый проём между общими зонами

PAPER = (247, 245, 239)
INK = (40, 42, 46)
MUTED = (110, 112, 118)
FILL = {'pub': (246, 232, 206), 'med': (214, 234, 222), 'admin': (222, 222, 240), 'serv': (234, 226, 214),
        'wc': (214, 228, 238), 'stair': (200, 200, 196), 'lift': (184, 184, 180), 'corr': (240, 238, 232),
        'void': (232, 232, 232), 'tech': (210, 206, 200), 'store': (226, 220, 206), 'wet': (206, 230, 238),
        'bath': (238, 214, 196), 'sport': (226, 236, 210)}
LOOT_C = (214, 140, 30)
LOCK_C = (200, 40, 40)
GLASS = (110, 160, 205)
EXIT_C = (40, 150, 70)


def font(size, bold=False):
    return ImageFont.truetype(f'C:/Windows/Fonts/{"arialbd" if bold else "arial"}.ttf', size)


def rect_of(r):
    return r[2], r[3], r[4], r[5]


def shared_edge(a, b):
    """Общий отрезок стены: ('v', x, y0, y1) или ('h', y, x0, x1); None — не соседи."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    for xa, xb in ((ax1, bx0), (ax0, bx1)):
        if abs(xa - xb) < EPS:
            lo, hi = max(ay0, by0), min(ay1, by1)
            if hi - lo > EPS:
                return ('v', xa, lo, hi)
    for ya, yb in ((ay1, by0), (ay0, by1)):
        if abs(ya - yb) < EPS:
            lo, hi = max(ax0, bx0), min(ax1, bx1)
            if hi - lo > EPS:
                return ('h', ya, lo, hi)
    return None


def door_geom(rooms, d):
    a, b, t, w = d
    ra = rect_of(rooms[a])
    if b == 'out':
        side, frac = t
        x0, y0, x1, y1 = ra
        if side in ('E', 'W'):
            x = x1 if side == 'E' else x0
            return ('v', x, y0 + (y1 - y0) * frac - w / 2, y0 + (y1 - y0) * frac + w / 2)
        y = y1 if side == 'N' else y0
        return ('h', y, x0 + (x1 - x0) * frac - w / 2, x0 + (x1 - x0) * frac + w / 2)
    e = shared_edge(ra, rect_of(rooms[b]))
    if e is None:
        raise SystemExit(f'дверь {a} — {b}: помещения не соседи')
    kind, c, lo, hi = e
    w = min(w, hi - lo - 0.3)
    mid = lo + (hi - lo) * t
    mid = min(max(mid, lo + w / 2 + 0.15), hi - w / 2 - 0.15)
    return (kind, c, mid - w / 2, mid + w / 2)


def overlaps(a, b):
    return min(a[2], b[2]) - max(a[0], b[0]) > EPS and min(a[3], b[3]) - max(a[1], b[1]) > EPS


def check_floor(rooms, doors, locked=(), keep_out=()):
    """Пересечения, двери по общим стенам, достижимость от наружных дверей (и без ключей)."""
    problems = []
    by_id = {r[0]: r for r in rooms}
    for i, a in enumerate(rooms):
        for b in rooms[i + 1:]:
            if overlaps(rect_of(a), rect_of(b)):
                problems.append(f'{a[0]} и {b[0]} пересекаются')
        for k in keep_out:
            if overlaps(rect_of(a), k):
                problems.append(f'{a[0]} заходит в запретный прямоугольник {k}')
    for d in doors:
        for rid in (d[0], d[1]):
            if rid != 'out' and rid not in by_id:
                problems.append(f'дверь в несуществующее {rid}')
        door_geom(by_id, d)

    def reach(skip_locked):
        adj = {}
        for a, b, t, w in doors:
            if b == 'out' or (skip_locked and ((a, b) in locked or (b, a) in locked)):
                continue
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
        start = {a for a, b, t, w in doors if b == 'out'}
        seen, q = set(start), deque(start)
        while q:
            n = q.popleft()
            for m in adj.get(n, ()):
                if m not in seen:
                    seen.add(m)
                    q.append(m)
        return seen
    allr = {r[0] for r in rooms if r[6] != 'void'}
    for n in sorted(allr - reach(False)):
        problems.append(f'не дойти: {n}')
    lock_rooms = {r[0] for r in rooms if 'lock' in r[7]}
    for n in sorted(allr - reach(True) - lock_rooms):
        problems.append(f'без ключей не дойти: {n}')
    return problems, by_id


class Plan:
    """Окно плана: метры → пиксели (y вверх)."""

    def __init__(self, d, x0, y0, xmin, ymax, scale):
        self.d, self.x0, self.y0, self.xmin, self.ymax, self.s = d, x0, y0, xmin, ymax, scale

    def p(self, x, y):
        return (self.x0 + (x - self.xmin) * self.s, self.y0 + (self.ymax - y) * self.s)

    def rect(self, x0, y0, x1, y1, fill=None, outline=INK, width=1):
        self.d.rectangle([*self.p(x0, y1), *self.p(x1, y0)], fill=fill, outline=outline, width=width)

    def poly(self, pts, fill=None, outline=INK, width=1):
        self.d.polygon([self.p(*q) for q in pts], fill=fill, outline=outline, width=width)

    def line(self, pts, fill=INK, width=1):
        self.d.line([self.p(*q) for q in pts], fill=fill, width=width)

    def circle(self, x, y, r, fill=None, outline=INK, width=1):
        (ax, ay), (bx, by) = self.p(x - r, y + r), self.p(x + r, y - r)
        self.d.ellipse([ax, ay, bx, by], fill=fill, outline=outline, width=width)

    def text(self, x, y, s, size=12, color=INK, bold=False, anchor='mm'):
        self.d.text(self.p(x, y), s, font=font(size, bold), fill=color, anchor=anchor)

    def rooms(self, rooms, by_id, doors, number, locked=(), no_windows=('stair', 'lift', 'tech', 'store', 'wc', 'void', 'corr')):
        rects = [rect_of(r) for r in rooms]
        for r in rooms:
            self.rect(*rect_of(r), fill=FILL[r[6]], outline=INK, width=1)
        # окна на наружных стенах
        for r in rooms:
            if r[6] in no_windows:
                continue
            x0, y0, x1, y1 = rect_of(r)
            for (ax, ay), (bx, by), (nx, ny) in (((x0, y0), (x1, y0), (0, -1)), ((x1, y0), (x1, y1), (1, 0)),
                                                 ((x1, y1), (x0, y1), (0, 1)), ((x0, y1), (x0, y0), (-1, 0))):
                n = int(math.hypot(bx - ax, by - ay) / 3.0)
                for k in range(n):
                    t0, t1 = (k + 0.25) / n, (k + 0.75) / n
                    mx, my = ax + (bx - ax) * (t0 + t1) / 2, ay + (by - ay) * (t0 + t1) / 2
                    ox, oy = mx + nx * 0.4, my + ny * 0.4
                    if any(q[0] < ox < q[2] and q[1] < oy < q[3] for q in rects):
                        continue
                    self.line([(ax + (bx - ax) * t0, ay + (by - ay) * t0), (ax + (bx - ax) * t1, ay + (by - ay) * t1)],
                              fill=GLASS, width=4)
        for dd in doors:
            kind, c, lo, hi = door_geom(by_id, dd)
            col = LOCK_C if (dd[0], dd[1]) in locked else (250, 250, 250)
            if kind == 'v':
                self.rect(c - 0.35, lo, c + 0.35, hi, fill=col, outline=None)
            else:
                self.rect(lo, c - 0.35, hi, c + 0.35, fill=col, outline=None)
            if dd[1] == 'out':
                cx, cy = (c, (lo + hi) / 2) if kind == 'v' else ((lo + hi) / 2, c)
                dx, dy = {'E': (1, 0), 'W': (-1, 0), 'N': (0, 1), 'S': (0, -1)}[dd[2][0]]
                self.poly([(cx + dx * 2.6, cy + dy * 2.6), (cx + dx * 0.8 - dy * 1.0, cy + dy * 0.8 + dx * 1.0),
                           (cx + dx * 0.8 + dy * 1.0, cy + dy * 0.8 - dx * 1.0)], fill=EXIT_C, outline=None)

    def labels(self, rooms, number, at=None):
        at = at or {}
        for r in rooms:
            if r[6] == 'void':
                continue
            x0, y0, x1, y1 = rect_of(r)
            cx, cy = at.get(r[0], ((x0 + x1) / 2, (y0 + y1) / 2))
            self.text(cx, cy, number[r[0]], 12, INK, True)
            if 'loot' in r[7]:
                px, py = self.p(cx, cy)
                self.d.ellipse([px + 14, py - 12, px + 22, py - 4], fill=LOOT_C)
            if 'lock' in r[7]:
                self.rect(x0, y0, x1, y1, outline=LOCK_C, width=3)


def schedule(d, rooms, number, x, y, title, area_fn=None, name_w=470):
    d.text((x, y), title, font=font(16, True), fill=INK)
    y += 26
    total = 0.0
    for r in rooms:
        if r[6] == 'void':
            continue
        x0, y0, x1, y1 = rect_of(r)
        a = area_fn(r) if area_fn else (x1 - x0) * (y1 - y0)
        total += a
        flags = (['лут'] if 'loot' in r[7] else []) + (['ключ'] if 'lock' in r[7] else [])
        d.text((x, y), number[r[0]], font=font(12, True), fill=INK)
        d.text((x + 44, y), r[1] + (f'  [{", ".join(flags)}]' if flags else ''), font=font(12),
               fill=LOCK_C if 'lock' in r[7] else INK)
        d.text((x + name_w, y), f'{a:.0f} м²', font=font(12), fill=MUTED)
        y += 16
    d.text((x, y + 4), f'Итого по полу ≈ {total:.0f} м²', font=font(12, True), fill=INK)
    return y + 26, total


def legend(d, x, y, kinds):
    names = {'pub': 'общие зоны', 'med': 'лечебные', 'admin': 'администрация', 'serv': 'хозяйственные, кухня',
             'wc': 'санузлы, раздевалки', 'stair': 'лестницы, лифты', 'store': 'кладовые, склады', 'wet': 'влажная зона спа',
             'bath': 'сауны и хамамы', 'sport': 'спортзал, ЛФК', 'tech': 'техника', 'corr': 'коридоры'}
    for k in kinds:
        d.rectangle([x, y + 2, x + 18, y + 16], fill=FILL[k], outline=INK)
        d.text((x + 26, y + 2), names[k], font=font(12), fill=INK)
        y += 20
    d.line([(x, y + 9), (x + 18, y + 9)], fill=GLASS, width=4)
    d.text((x + 26, y + 2), 'окна, витражи', font=font(12), fill=INK)
    y += 20
    d.polygon([(x + 2, y + 2), (x + 2, y + 16), (x + 16, y + 9)], fill=EXIT_C)
    d.text((x + 26, y + 2), 'наружный вход', font=font(12), fill=INK)
    y += 20
    d.ellipse([x + 4, y + 4, x + 14, y + 14], fill=LOOT_C)
    d.text((x + 26, y + 2), 'лут по смыслу места', font=font(12), fill=INK)
    return y + 24
