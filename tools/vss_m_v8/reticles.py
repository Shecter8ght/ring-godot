"""Сетки оптики ВСС-М v8 — свои текстуры окуляра (CameraRig: attach.model.reticle).

python -X utf8 tools/vss_m_v8/reticles.py [pso] [s432], затем `tools/godot.cmd --headless --import`
и python -X utf8 tools/vss_m_v8/game_imports.py (без сжатия, с mip-уровнями), ещё раз --import.
→ assets/models/attachments/pso_vss/pso_vss_reticle.png, assets/models/attachments/scope_4x32/scope_4x32_reticle.png

Квадрат текстуры — окно окуляра: край поля — круг радиусом в половину стороны (R), центр — точка прицеливания.
Каналы: R — нити (чёрные), G — что светится красным с подсветкой (T). Рисуется вчетверо крупнее и уменьшается —
сглаженные края; цифры — штриховой шрифт Hershey (OpenCV), как гравировка на сетке.
- pso — ПСО-1: главный угольник и шкала поправок по 0-01 (±10), три угольника ниже и вертикальная нить,
  дальномер по росту 1,7 м (кривая 2…10 сотен метров). Светится вся сетка, как у ПСО с подсветкой.
- s432 — 4×32: тонкое перекрестие через всё поле, толстые «пеньки» к центру, внутренний и внешний круг, шкала
  снижения 3–6 рисками и 7–10 кружками, дальномерная планка слева внизу. Светится точка в центре.
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SIZE = 2048                     # сторона итоговой текстуры
SS = 4                          # во сколько раз крупнее рисуем
N = SIZE * SS
R = N / 2                       # радиус поля, пикс. рисунка
FONT = cv2.FONT_HERSHEY_SIMPLEX


class Sheet:
    """Два слоя рисунка: нити и подсветка; координаты — в долях радиуса поля, y вниз."""

    def __init__(self):
        self.ink = np.zeros((N, N), np.uint8)
        self.glow = np.zeros((N, N), np.uint8)

    @staticmethod
    def p(x, y):
        return int(round(R + x * R)), int(round(R + y * R))

    @staticmethod
    def w(t):
        return max(1, int(round(t * R)))

    def _layers(self, glow):
        return (self.ink, self.glow) if glow else (self.ink,)

    def line(self, a, b, t, glow=False):
        for img in self._layers(glow):
            cv2.line(img, self.p(*a), self.p(*b), 255, self.w(t), cv2.LINE_AA)

    def circle(self, c, r, t, glow=False, fill=False):
        for img in self._layers(glow):
            cv2.circle(img, self.p(*c), int(round(r * R)), 255, -1 if fill else self.w(t), cv2.LINE_AA)

    def text(self, s, c, h, t, glow=False, align='c'):
        """Подпись высотой h (доля радиуса); c — середина (align c), левый (l) или правый (r) край по середине высоты."""
        (tw, th), _ = cv2.getTextSize(s, FONT, 1.0, self.w(t))
        k = h * R / th
        (tw, th), _ = cv2.getTextSize(s, FONT, k, self.w(t))
        x, y = self.p(*c)
        x = {'c': x - tw // 2, 'l': x, 'r': x - tw}[align]
        for img in self._layers(glow):
            cv2.putText(img, s, (x, y + th // 2), FONT, k, 255, self.w(t), cv2.LINE_AA)

    def save(self, path: Path):
        small = [cv2.resize(img, (SIZE, SIZE), interpolation=cv2.INTER_AREA) for img in (self.ink, self.glow)]
        rgb = np.dstack([np.zeros_like(small[0]), small[1], small[0]])          # BGR: B 0, G подсветка, R нити
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), rgb)
        print('RETICLE', path.relative_to(ROOT), 'нити', round(float((small[0] > 0).mean()) * 100, 2), '%')


def pso():
    """ПСО-1. Тысячная (0-01) — U доли радиуса: шкала ±10 занимает ~0,28 радиуса, как в поле зрения ПСО."""
    s = Sheet()
    U, T = 0.0283, 0.0065
    g = True                                    # подсветка ПСО — вся сетка
    # шкала боковых поправок: нить и риски через 0-01, длиннее на 5 и 10
    s.line((-10 * U, 0), (10 * U, 0), T, g)
    for i in range(-10, 11):
        if i == 0:
            continue
        lo, hi = (-0.015, 0.06) if abs(i) == 10 else (-0.01, 0.05) if abs(i) == 5 else (-0.01, 0.038)
        s.line((i * U, lo), (i * U, hi), T, g)
    for x in (-10 * U, 10 * U):
        s.text('10', (x, 0.105), 0.042, T * 0.8, g)
    # боковые нити от шкалы к краю поля
    for k in (-1, 1):
        s.line((k * 0.32, 0), (k * 0.80, 0), T * 1.3, g)
    # угольники: главный (точка прицеливания) и три ниже — на 1100, 1200, 1300 м
    for y in (0.0, 0.11, 0.187, 0.277):
        s.line((0, y), (-0.021, y + 0.034), T, g)
        s.line((0, y), (0.021, y + 0.034), T, g)
    s.line((0, 0.277 + 0.034), (0, 0.80), T * 1.3, g)                   # вертикальная нить — от низа третьего угольника
    # дальномер: цель ростом 1,7 м — ноги на нижней нити, голова касается кривой у её дальности (сотни метров)
    yb = 0.467
    s.line((-0.80, yb), (-0.143, yb), T * 1.2, g)
    s.text('1.7', (-0.143, yb + 0.06), 0.042, T * 0.8, g, align='r')
    for n in range(2, 11):
        x = -0.143 - (n - 2) * 0.0821
        y = yb - 1.7 * 10 / n * U
        s.line((x - 0.014, y), (x + 0.014, y), T, g)                         # «⊥» — опора риски
        # у 10 — «L»: риска с левого края опоры
        sx = x - 0.014 if n == 10 else x
        s.line((sx, y), (sx, y - (0.032 if n % 2 == 0 else 0.016)), T, g)
        if n == 2:
            for k in range(2):                                             # у «2» — пунктир вверх, подпись над ним
                s.line((x, y - 0.045 - k * 0.03), (x, y - 0.06 - k * 0.03), T, g)
            s.text('2', (x, y - 0.13), 0.042, T * 0.8, g)
        elif n % 2 == 0:
            s.text(str(n), (x, y - 0.07), 0.042, T * 0.8, g)
    s.save(ROOT / 'assets/models/attachments/pso_vss/pso_vss_reticle.png')


def s432():
    """4×32: тонкое перекрестие, толстые пеньки, два круга, шкала снижения, точка с подсветкой."""
    s = Sheet()
    T, P = 0.0052, 0.017                        # тонкая нить и толщина пеньков
    s.line((-1.0, 0), (1.0, 0), T)
    s.line((0, -1.0), (0, 1.0), T)
    for k in (-1, 1):
        s.line((k * 0.097, 0), (k * 0.38, 0), P)
    s.line((0, -0.38), (0, -0.097), P)
    s.line((0, 0.333), (0, 0.56), P)
    s.circle((0, 0), 0.845, T)
    s.circle((0, 0), 0.337, T)
    # шкала снижения: 3–6 — риски с цифрами справа, 7–10 — кружки с цифрами слева
    for n, y, half in ((3, 0.026, 0.016), (4, 0.046, 0.013), (5, 0.068, 0.011), (6, 0.092, 0.010)):
        s.line((-half, y), (half, y), T)
        s.text(str(n), (half + 0.012, y), 0.02, T * 0.7, align='l')
    for n, y, rr in ((7, 0.122, 0.022), (8, 0.174, 0.018), (9, 0.227, 0.015), (10, 0.288, 0.012)):
        s.circle((0, y), rr, T)
        s.line((-rr - 0.012, y), (-rr, y), T)
        s.line((rr, y), (rr + 0.012, y), T)
        s.text(str(n), (-rr - 0.02, y), 0.02, T * 0.7, align='r')
    # дальномерная планка: четыре штриха по 0,035 радиуса, подпись — рост цели
    for i in range(4):
        x0 = -0.36 + i * 0.05
        s.line((x0, 0.36), (x0 + 0.035, 0.36), T * 1.8)
    s.text('1.8', (-0.36, 0.395), 0.018, T * 0.6, align='l')
    # точка в центре — светится с подсветкой
    s.circle((0, 0), 0.0075, T, glow=True, fill=True)
    s.save(ROOT / 'assets/models/attachments/scope_4x32/scope_4x32_reticle.png')


if __name__ == '__main__':
    which = sys.argv[1:] or ['pso', 's432']
    if 'pso' in which:
        pso()
    if 's432' in which:
        s432()
