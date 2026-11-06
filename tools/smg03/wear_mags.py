"""ИЗЛОМ-45: износ магазинов v2 (этап 2) — места и рисунок в развёртке атласов Mag13 / Mag30 по картам положения и нормали
(game_tex.py, стадия maps → _asset_src/smg03/tex_mags/<набор>_maps.npz).

Ориентир владельца (06.11): кадр Road to Vostok, где игрок снаряжает магазин AR — у чёрного магазина в верхней части, где
он трётся о шахту, по всей длине светлые продольные полосы; на нижнем торце углы и рёбра потёрты не сплошь. «Не
процедурно, а художественно»: полосы и потёртости заданы списком руками — место по контуру сечения, высота от входа в
шахту, ширина, сила, где оборвана, где протёрто до стали вкладыша (у Glock полимер поверх стального вкладыша — у
сильно поношенных губки и кромки светлеют до металла); шум — только чтобы край полосы был рваным, а внутри —
продольная «шлифовка». Всё считается в осях магазина по положению пикселя (не по развёртке) — швов на стыках островов нет.

    python -X utf8 tools/smg03/wear_mags.py [--preview]
→ _asset_src/smg03/tex_mags/wear/<набор>_<место>.png (8 бит, белое — след есть); --preview — развёртка сечения
  (по кругу × по высоте) и карта развёртки с местами цветом → <набор>_wear_preview*.png.

Места (белое — сильнее):
  polish  — заглажено шахтой: широкие мягкие участки у рёбер граней (полимер светлее и глаже);
  streaks — продольные полосы (главное по ориентиру): по рёбрам и кромкам граней, рвано, разной длины и силы;
  bare    — сердцевины сильных полос, губки и кромки верха — протёрто до стального вкладыша;
  catch   — дорожка защёлки по борту снизу до окна и обтёртые кромки окон;
  lips    — верх губок — по ходу затвора заглажено; brass — латунь от гильз на внутренних кромках губок;
  bottom  — донышко: потёртые углы и рёбра участками; bottom_scr — царапины по донышку;
  rim     — (30) верхний срез рукава — упор в низ шахты, участками; hand — (30) рукав, где берут: вершины рифления и
            борта глаже.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / '_asset_src/smg03/tex_mags'
OUT = TEX / 'wear'

# геометрия магазинов — как tools/smg03/part_magazine.py (мм оружия; ось магазина наклонена на A)
A = math.radians(21.2)
SA, CA = math.sin(A), math.cos(A)
CX, CZ = -55.5, -110.0
D, W = 37.5 / 2, 25.5 / 2
WALL = 1.7
Z_TOP = -11.5
STEP, STEP_X = 5.0, 3.0
Z_BOT13, PLATE_H = -131.5, 5.5
Z_SLEEVE, SLEEVE_SLOPE = -111.2, 0.0925
U_BOT30, BASE_H, SLV_T = -139.6, 4.0, 2.2
SHIFT = {'Mag13': 350.0, 'Mag30': 750.0}       # game_tex.MAG_SHIFT: магазины опущены в FBX (мм по Z)


def zf(xg):
    """Низ шахты (верх рукава на 30) в мм оружия: спереди Z −111.2 у X −33.5, к заду ниже."""
    return Z_SLEEVE + (xg + 33.5) * SLEEVE_SLOPE


def u_at(z, x):
    return (z - CZ + x * SA) / CA


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ---------- сечение: скруглённый прямоугольник, координата по контуру ----------

class Section:
    """Контур поперёк оси: x от x0 (зад) до x1 (перёд), y ±hw, радиусы rr сзади и rf спереди. s — длина по контуру от
    середины задней грани через левый борт (+y), перёд, правый борт (−y); грани — по имени и доле t."""

    def __init__(self, x0, x1, hw, rr, rf, step=0.04):
        self.x0, self.x1, self.hw, self.rr, self.rf = x0, x1, hw, rr, rf
        segs = []

        def line(name, a, b):
            segs.append((name, 'line', a, b))

        def arc(name, c, r, a0, a1):
            segs.append((name, 'arc', (c, r), (a0, a1)))
        line('rear_l', (x0, 0.0), (x0, hw - rr))
        arc('arc_rl', (x0 + rr, hw - rr), rr, math.pi, math.pi / 2)
        line('left', (x0 + rr, hw), (x1 - rf, hw))
        arc('arc_fl', (x1 - rf, hw - rf), rf, math.pi / 2, 0.0)
        line('front', (x1, hw - rf), (x1, -hw + rf))
        arc('arc_fr', (x1 - rf, -hw + rf), rf, 0.0, -math.pi / 2)
        line('right', (x1 - rf, -hw), (x0 + rr, -hw))
        arc('arc_rr', (x0 + rr, -hw + rr), rr, -math.pi / 2, -math.pi)
        line('rear_r', (x0, -hw + rr), (x0, 0.0))
        pts, ss, self.seg = [], [], {}
        s = 0.0
        for name, kind, a, b in segs:
            if kind == 'line':
                ln = math.hypot(b[0] - a[0], b[1] - a[1])
                n = max(2, int(ln / step))
                t = np.linspace(0.0, 1.0, n, endpoint=False)
                p = np.stack([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t], 1)
            else:
                (c, r), (a0, a1) = a, b
                ln = abs(a1 - a0) * r
                n = max(2, int(ln / step))
                t = np.linspace(0.0, 1.0, n, endpoint=False)
                ang = a0 + (a1 - a0) * t
                p = np.stack([c[0] + r * np.cos(ang), c[1] + r * np.sin(ang)], 1)
            self.seg[name] = (s, ln)
            pts.append(p)
            ss.append(s + t * ln)
            s += ln
        self.P = s
        self.pts = np.concatenate(pts)
        self.s = np.concatenate(ss)
        self.tree = cKDTree(self.pts)

    def at(self, name, t):
        """Место на контуре: грань name, доля t от её начала (по ходу s)."""
        s0, ln = self.seg[name]
        return (s0 + t * ln) % self.P

    def param(self, x, y):
        _, i = self.tree.query(np.stack([x, y], 1))
        return self.s[i]

    def sd(self, x, y):
        """Расстояние до контура со знаком (снаружи +)."""
        xc = (self.x0 + self.x1) / 2
        hd = (self.x1 - self.x0) / 2
        r = np.where(x > xc, self.rf, self.rr)
        qx = np.abs(x - xc) - hd + r
        qy = np.abs(y) - self.hw + r
        out = np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0))
        return out + np.minimum(np.maximum(qx, qy), 0.0) - r

    def ds(self, s, s0):
        """Разность по контуру с переходом через начало."""
        d = (s - s0) % self.P
        return np.where(d > self.P / 2, d - self.P, d)


BODY = Section(-D, D, W, 3.0, 7.0)
SLEEVE = Section(-D - SLV_T, D + SLV_T, W + SLV_T, 4.5, 8.5)
PLATE13 = Section(-D - 1.4, D + 3.0, W + 1.4, 4.5, 8.0)
BASE30 = Section(-D - SLV_T - 0.4, D + SLV_T + 0.4, W + SLV_T + 0.4, 4.8, 8.8)


# ---------- шум ----------

class Field:
    """Гладкий шум (среднее 0, разброс 1) на сетке (a, b) мм, периодичный по a с периодом pa (по контуру), с разной
    длиной пятен по осям; спектральный фильтр — края сшиваются сами."""

    def __init__(self, seed, pa, b0, b1, sig_a, sig_b, res=8.0):
        rng = np.random.default_rng(seed)
        na = int(round(pa * res))
        nb = int(round((b1 - b0) * res)) + 16
        f = rng.standard_normal((nb, na))
        ka = np.fft.fftfreq(na, d=1.0 / res)
        kb = np.fft.fftfreq(nb, d=1.0 / res)
        g = np.exp(-2.0 * (math.pi ** 2) * ((ka[None, :] * sig_a) ** 2 + (kb[:, None] * sig_b) ** 2))
        f = np.real(np.fft.ifft2(np.fft.fft2(f) * g))
        f = (f - f.mean()) / (f.std() + 1e-9)
        self.f = f.astype(np.float32)
        self.res, self.pa, self.b0 = res * na / (pa * res), pa, b0 - 8.0 / res
        self.res_b = res

    def __call__(self, a, b):
        ma = ((np.asarray(a) % self.pa) * self.res).astype(np.float32).ravel()
        mb = ((np.asarray(b) - self.b0) * self.res_b).astype(np.float32).ravel()
        # remap берёт карты не больше 32767 строк — выборка листом по 4096
        n = ma.size
        cols = 4096
        rows = -(-n // cols)
        pad = rows * cols - n
        ma = np.pad(ma, (0, pad)).reshape(rows, cols)
        mb = np.pad(mb, (0, pad)).reshape(rows, cols)
        out = cv2.remap(self.f, ma, mb, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        return out.ravel()[:n].reshape(np.shape(a))


def noise3(p, scale, seed):
    """Гладкий шум 0..1 в пространстве (мм, масштаб пятна scale): значения в узлах решётки, кубическое сглаживание."""
    q = p / scale
    i = np.floor(q).astype(np.int64)
    f = q - i
    f = f * f * (3.0 - 2.0 * f)

    def h(ix, iy, iz):
        v = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
        v = (v ^ (v >> 13)) * 1274126177
        v = v ^ (v >> 16)
        return (v & 0xFFFF).astype(np.float32) / 65535.0
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = ((f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) *
                     (f[:, 2] if dz else 1 - f[:, 2]))
                out = out + w * h(i[:, 0] + dx, i[:, 1] + dy, i[:, 2] + dz)
    return out


# ---------- данные пикселей ----------

class Pix:
    def __init__(self, setname):
        d = np.load(TEX / f'{setname}_maps.npz')
        self.filled = d['filled']
        self.idx = np.nonzero(self.filled.ravel())[0]
        pos = d['pos'].reshape(-1, 3)[self.idx].astype(np.float64)
        nrm = d['nrm'].reshape(-1, 3)[self.idx].astype(np.float64)
        pos[:, 2] += SHIFT[setname]
        self.g = pos                                   # мм оружия
        self.gn = nrm
        rx, rz = pos[:, 0] - CX, pos[:, 2] - CZ
        self.x = rx * CA - rz * SA                     # вперёд поперёк оси
        self.y = pos[:, 1]                             # +y — левый борт
        self.u = rx * SA + rz * CA                     # вдоль оси вверх
        self.nx = nrm[:, 0] * CA - nrm[:, 2] * SA
        self.ny = nrm[:, 1]
        self.nu = nrm[:, 0] * SA + nrm[:, 2] * CA
        self.size = d['filled'].shape[0]

    def image(self, v):
        out = np.zeros(self.size * self.size, np.float32)
        out[self.idx] = v
        return out.reshape(self.size, self.size)


def outward(px, sec, x, y, tol=0.7):
    """Наружная поверхность контура sec: близко к контуру и нормаль наружу (от середины сечения)."""
    sd = sec.sd(x, y)
    eps = 0.05
    gx = (sec.sd(x + eps, y) - sec.sd(x - eps, y)) / (2 * eps)
    gy = (sec.sd(x, y + eps) - sec.sd(x, y - eps)) / (2 * eps)
    gl = np.hypot(gx, gy) + 1e-9
    dot = (px.nx * gx + px.ny * gy) / gl
    return (np.abs(sd) < tol) & (dot > 0.35), sd, dot


# ---------- полосы ----------

def streak(px, sec, s, h, spec, fd_edge, fd_grain, rng):
    """Одна продольная полоса: место по контуру spec['at'] = (грань, доля), высота h0…h1 (доля от входа в шахту до
    верха), ширина w мм, сила a, рваность broken (0 — сплошная), извилистость wob мм. → (полоса, сердцевина)."""
    face, t = spec['at']
    s0 = sec.at(face, t)
    w, a = spec['w'], spec['a']
    h0, h1 = spec['h']
    phase = rng.uniform(0, 500.0)
    # где по высоте: мягкие концы (у входа — короче, вверху — длиннее затухание)
    taper0, taper1 = spec.get('taper', (0.04, 0.10))
    env = smooth(h0 - taper0 * 0.3, h0 + taper0, h) * (1.0 - smooth(h1 - taper1, h1 + taper1 * 0.3, h))
    # извилистость и ширина по высоте — медленно
    hh = h * 100.0 + phase
    wob = spec.get('wob', 0.25) * fd_edge(np.full_like(hh, s0 + 37.0), hh * 0.35)
    wv = w * (0.75 + 0.25 * np.clip(fd_edge(np.full_like(hh, s0 + 11.0), hh * 0.6), -2, 2))
    d = sec.ds(s, s0 + wob)
    prof = np.exp(-0.5 * (d / np.maximum(wv * 0.5, 0.12)) ** 2)
    # рваность: обрывы по высоте и рваный край
    br = spec.get('broken', 0.3)
    if br > 0:
        # обрывы редкие и длинные (кусками по 1–3 см): частые короткие давали «дождь» штрихов (проба 1, 06.11)
        cut = fd_edge(np.full_like(hh, s0 + 71.0), hh * 0.25) + 0.35 * fd_edge(s * 0.0 + s0 + 5.0, hh * 0.6)
        env = env * smooth(br * 2.0 - 1.5, br * 2.0 - 0.9, cut)
    edge = 0.55 + 0.45 * fd_grain(s * 1.0, h * 100.0 + phase)
    val = a * env * prof * np.clip(edge, 0.0, 1.2)
    core = None
    if spec.get('bare', 0.0) > 0:
        bh0, bh1 = spec.get('bare_h', (h0, h0 + (h1 - h0) * 0.45))
        benv = smooth(bh0, bh0 + 0.03, h) * (1.0 - smooth(bh1 - 0.05, bh1, h))
        bcut = fd_edge(np.full_like(hh, s0 + 133.0), hh * 1.7)
        benv = benv * smooth(0.2, 0.7, bcut + spec['bare'] * 1.2 - 0.6)
        bprof = np.exp(-0.5 * (d / np.maximum(wv * 0.16, 0.1)) ** 2)
        core = spec['bare'] * benv * bprof * smooth(0.25, 0.6, fd_grain(s * 1.0 + 3.0, h * 100.0 + phase * 1.3) + 0.5)
    return val, core


# ---------- что где: списки руками ----------
# полоса: (грань, доля по грани, h0, h1, ширина мм, сила, рваность, до стали) — h: 0 — вход в шахту, 1 — верх губок.
# грани по ходу s: rear_l (середина зада → левый задний угол), arc_rl, left (левый борт, +y), arc_fl, front, arc_fr,
# right (правый борт), arc_rr, rear_r. Борта выше плечика сужения (узкая часть у губок) шахты не касаются — полосы на
# бортах кончаются у плечика сами.
STREAKS = {
    'Mag13': [
        # левый борт: задний угол — главная полоса, длинная, внизу протёрта до стали
        ('arc_rl', 0.55, 0.00, 0.93, 1.1, 0.95, 0.30, 0.55),
        ('left', 0.03, 0.02, 0.80, 0.7, 0.75, 0.35, 0.25),
        ('left', 0.12, 0.10, 0.55, 0.35, 0.45, 0.50, 0.0),
        ('left', 0.30, 0.04, 0.38, 0.5, 0.35, 0.45, 0.0),
        ('left', 0.47, 0.20, 0.74, 0.25, 0.30, 0.55, 0.0),
        ('left', 0.71, 0.00, 0.30, 0.6, 0.40, 0.40, 0.0),
        ('left', 0.86, 0.06, 0.58, 0.45, 0.50, 0.35, 0.0),
        # левый передний угол — длинная рваная
        ('arc_fl', 0.62, 0.00, 1.00, 1.4, 0.80, 0.40, 0.30),
        ('arc_fl', 0.90, 0.15, 0.95, 0.6, 0.55, 0.45, 0.0),
        # перёд: у углов сильнее, посередине широкая слабая
        ('front', 0.08, 0.00, 0.98, 0.8, 0.70, 0.35, 0.20),
        ('front', 0.35, 0.10, 0.70, 0.5, 0.35, 0.55, 0.0),
        ('front', 0.55, 0.00, 0.92, 1.8, 0.30, 0.30, 0.0),
        ('front', 0.90, 0.05, 1.00, 0.7, 0.65, 0.35, 0.15),
        # правый борт (сторона, что видна в руках у правши, — чуть богаче)
        ('arc_fr', 0.12, 0.00, 0.96, 0.9, 0.70, 0.35, 0.25),
        ('arc_fr', 0.45, 0.20, 0.85, 1.2, 0.50, 0.50, 0.0),
        ('right', 0.10, 0.04, 0.62, 0.5, 0.55, 0.40, 0.0),
        ('right', 0.33, 0.00, 0.45, 0.35, 0.40, 0.45, 0.0),
        ('right', 0.52, 0.12, 0.83, 0.6, 0.40, 0.40, 0.0),
        ('right', 0.76, 0.30, 0.66, 0.3, 0.30, 0.55, 0.0),
        ('right', 0.95, 0.00, 0.86, 0.8, 0.80, 0.30, 0.35),
        # правый задний угол — самая сильная
        ('arc_rr', 0.45, 0.00, 0.97, 1.0, 1.00, 0.25, 0.60),
        # зад
        ('rear_r', 0.85, 0.05, 0.95, 0.6, 0.55, 0.40, 0.0),
        ('rear_r', 0.30, 0.10, 0.80, 0.4, 0.35, 0.55, 0.0),
        ('rear_l', 0.10, 0.00, 0.60, 0.5, 0.30, 0.50, 0.0),
        ('rear_l', 0.70, 0.15, 1.00, 0.6, 0.50, 0.40, 0.15),
    ],
    # на 30 — другой экземпляр: зад вытерт сильнее (его чаще вставляли), передние углы слабее
    'Mag30': [
        ('arc_rl', 0.40, 0.00, 0.88, 1.3, 0.85, 0.35, 0.35),
        ('left', 0.06, 0.05, 0.70, 0.5, 0.60, 0.40, 0.0),
        ('left', 0.22, 0.00, 0.50, 0.3, 0.35, 0.50, 0.0),
        ('left', 0.55, 0.15, 0.62, 0.45, 0.35, 0.45, 0.0),
        ('left', 0.90, 0.00, 0.55, 0.6, 0.55, 0.35, 0.0),
        ('arc_fl', 0.50, 0.05, 0.98, 1.1, 0.60, 0.45, 0.15),
        ('front', 0.12, 0.00, 0.90, 0.6, 0.55, 0.40, 0.0),
        ('front', 0.48, 0.05, 0.96, 2.2, 0.28, 0.35, 0.0),
        ('front', 0.80, 0.20, 0.75, 0.5, 0.40, 0.50, 0.0),
        ('arc_fr', 0.30, 0.00, 0.94, 1.0, 0.65, 0.40, 0.20),
        ('right', 0.05, 0.10, 0.58, 0.6, 0.50, 0.40, 0.0),
        ('right', 0.40, 0.00, 0.40, 0.4, 0.40, 0.45, 0.0),
        ('right', 0.63, 0.08, 0.80, 0.3, 0.35, 0.50, 0.0),
        ('right', 0.92, 0.00, 0.84, 0.9, 0.85, 0.30, 0.45),
        ('arc_rr', 0.55, 0.00, 0.98, 1.2, 1.00, 0.25, 0.65),
        ('rear_r', 0.65, 0.00, 0.90, 0.8, 0.60, 0.35, 0.20),
        ('rear_r', 0.15, 0.20, 0.95, 0.5, 0.40, 0.45, 0.0),
        ('rear_l', 0.40, 0.00, 0.75, 0.6, 0.45, 0.40, 0.0),
        ('rear_l', 0.88, 0.05, 1.00, 0.7, 0.70, 0.35, 0.35),
    ],
}
# заглажено шахтой (широко и мягко): (грань, доля, ширина мм, сила)
POLISH = {
    'Mag13': [('arc_rl', 0.5, 7.0, 0.70), ('arc_fl', 0.55, 9.0, 0.55), ('front', 0.5, 9.0, 0.35),
              ('arc_fr', 0.4, 9.0, 0.55), ('arc_rr', 0.5, 7.5, 0.80), ('rear_r', 0.6, 6.0, 0.35),
              ('rear_l', 0.6, 5.0, 0.30), ('left', 0.15, 6.0, 0.30), ('right', 0.85, 7.0, 0.40)],
    'Mag30': [('arc_rl', 0.45, 7.0, 0.60), ('arc_fl', 0.5, 8.0, 0.40), ('front', 0.5, 8.0, 0.30),
              ('arc_fr', 0.4, 8.0, 0.45), ('arc_rr', 0.5, 8.0, 0.85), ('rear_r', 0.5, 7.0, 0.45),
              ('rear_l', 0.7, 6.0, 0.45), ('right', 0.9, 6.0, 0.40)],
}
# донышко: потёртые участки кромок (грань, доля, длина по контуру мм, сила, вверх по борту мм, внутрь по дну мм)
BOTTOM = {
    'Mag13': [('arc_rr', 0.5, 7.0, 0.95, 2.2, 2.0), ('rear_l', 0.6, 5.0, 0.50, 1.2, 1.2), ('arc_fl', 0.4, 9.0, 0.75, 1.8, 1.8),
              ('front', 0.5, 6.0, 0.60, 1.5, 2.5), ('left', 0.35, 4.0, 0.35, 1.0, 0.8), ('right', 0.7, 6.0, 0.45, 1.0, 1.2),
              ('arc_fr', 0.8, 3.0, 0.40, 1.0, 1.0)],
    'Mag30': [('arc_rl', 0.5, 8.0, 0.90, 2.0, 2.2), ('arc_fr', 0.5, 10.0, 0.80, 1.8, 2.0), ('front', 0.2, 4.0, 0.45, 1.2, 1.5),
              ('rear_r', 0.4, 6.0, 0.55, 1.4, 1.2), ('right', 0.3, 5.0, 0.40, 1.0, 0.9), ('left', 0.65, 7.0, 0.50, 1.2, 1.0),
              ('arc_rr', 0.6, 3.0, 0.45, 1.0, 1.0)],
}
# верхний срез рукава на 30 — упор в низ шахты: (грань, доля, длина мм, сила)
RIM = [('front', 0.5, 14.0, 0.70), ('arc_fl', 0.3, 6.0, 0.50), ('arc_rr', 0.5, 5.0, 0.60), ('left', 0.6, 8.0, 0.35),
       ('right', 0.25, 10.0, 0.45), ('rear_l', 0.5, 4.0, 0.30)]
SEED = {'Mag13': 1306, 'Mag30': 3006}


# ---------- места ----------

def band(sec, s, face, t, length, soft=0.35):
    """Участок контура: плоская середина длиной length, мягкие края (доля soft длины)."""
    d = np.abs(sec.ds(s, sec.at(face, t)))
    half = length / 2
    return 1.0 - smooth(half * (1 - soft), half * (1 + soft), d)


def side_of(face, t):
    """Полоса на борту (выше плечика борта шахты не касаются): борта и бортовые половины дуг."""
    return face in ('left', 'right') or (face in ('arc_rl', 'arc_fr') and t > 0.5) or \
        (face in ('arc_fl', 'arc_rr') and t < 0.5)


def well_h(px):
    """Высота в шахте: 0 — вход (низ шахты по линии верха рукава + 1 мм), 1 — верх губок (спереди ступенька ниже)."""
    ze = zf(px.g[:, 0]) + 1.0
    zt = np.where(px.x > STEP_X, Z_TOP - STEP, Z_TOP)
    return (px.g[:, 2] - ze) / (zt - ze)


def body_zones(px, setname, Z):
    rng = np.random.default_rng(SEED[setname])
    sec = BODY
    on, sd, _ = outward(px, sec, px.x, px.y)
    if setname == 'Mag30':
        on &= px.g[:, 2] > zf(px.g[:, 0]) - 0.3            # ниже — рукав
    else:
        on &= px.g[:, 2] > Z_BOT13 + 0.2                    # ниже — донышко
    s = sec.param(px.x, px.y)
    h = well_h(px)
    u_sh = u_at(Z_TOP, -D) - 16.0                          # плечико сужения к губкам (part_magazine.glock_body)
    fd_edge = Field(SEED[setname] + 1, sec.P, 0.0, 200.0, 3.0, 4.0, res=2.0)
    fd_grain = Field(SEED[setname] + 2, sec.P, 0.0, 200.0, 0.10, 2.5, res=10.0)
    fd_big = Field(SEED[setname] + 3, sec.P, 0.0, 200.0, 6.0, 10.0, res=1.0)
    ii = np.nonzero(on & (h > -0.15) & (h < 1.05))[0]
    sI, hI, uI = s[ii], h[ii], px.u[ii]
    streaks = np.zeros(len(ii), np.float32)
    bare = np.zeros(len(ii), np.float32)
    spec_list = list(STREAKS[setname])
    # тонкие следы скольжения: много слабых волосков по граням (случайно, но только вдоль оси)
    faces = ['left', 'right', 'front', 'rear_l', 'rear_r', 'left', 'right']
    for _ in range(22):
        h0 = rng.uniform(-0.02, 0.6)
        spec_list.append((faces[rng.integers(len(faces))], rng.uniform(0.02, 0.98), h0, h0 + rng.uniform(0.3, 0.8),
                          rng.uniform(0.10, 0.20), rng.uniform(0.10, 0.24), 0.3, 0.0))
    for face, t, h0, h1, w, a, br, bare_k in spec_list:
        if w >= 0.3:                                       # списочные (не волоски) — шире: в кадре читались нитками
            w = w * 1.6
        spec = {'at': (face, t), 'h': (h0, h1), 'w': w, 'a': a, 'broken': br, 'bare': bare_k, 'wob': 0.25 * w + 0.1}
        val, core = streak(px, sec, sI, hI, spec, fd_edge, fd_grain, rng)
        if side_of(face, t):
            k = 1.0 - smooth(u_sh - 2.0, u_sh + 2.5, uI)
            val = val * k
            core = core * k if core is not None else None
        streaks = np.maximum(streaks, val)
        if core is not None:
            bare = np.maximum(bare, core)
    # заглажено широко: у рёбер граней, рвано крупными пятнами; у входа в шахту мягко начинается
    pol = np.zeros(len(ii), np.float32)
    for face, t, w, a in POLISH[setname]:
        d = sec.ds(sI, sec.at(face, t))
        g = a * np.exp(-0.5 * (d / (w * 0.5)) ** 2)
        if side_of(face, t):
            g = g * (1.0 - smooth(u_sh - 3.0, u_sh + 3.0, uI))
        pol = np.maximum(pol, g)
    pol = pol * smooth(-0.04, 0.10, hI) * (1.0 - smooth(0.97, 1.03, hI))
    pol = pol * np.clip(0.55 + 0.45 * fd_big(sI, hI * 100.0), 0.0, 1.0) * (0.8 + 0.2 * fd_grain(sI + 7.0, hI * 100.0))
    Z['polish'][ii] = np.clip(pol, 0, 1)
    Z['streaks'][ii] = np.clip(streaks, 0, 1)
    Z['bare'][ii] = np.clip(bare, 0, 1)
    # дорожка защёлки: по борту от входа до окна (зуб защёлки скользит под пружиной) и обтёртые кромки окон
    uc = u_at(Z_TOP - STEP, D - 5.0) - 34.0
    xw0, xw1, uw0, uw1 = D - 8.5, D - 2.6, uc - 3.6, uc + 3.6
    side = on & (np.abs(px.y) > W - 4.0) & (np.abs(px.ny) > 0.35)
    xc = (xw0 + xw1) / 2
    track = side & (px.u < uw0 + 0.4) & (h > -0.05)
    tk = np.exp(-0.5 * ((px.x - xc) / 1.9) ** 4) * smooth(-0.05, 0.12, h) * smooth(uw0 - 30.0, uw0 - 2.0, px.u)
    grain = 0.7 + 0.3 * fd_grain(s, h * 100.0 + 31.0)
    sidek = np.where(px.y < 0, 1.0, 0.75)                     # справа — чуть сильнее
    catch = np.where(track, 0.65 * tk * grain * sidek, 0.0)
    # кромки окна: расстояние до прямоугольника (x, u) снаружи; нижняя кромка — сильнее
    dx = np.maximum(np.maximum(xw0 - px.x, px.x - xw1), 0.0)
    du = np.maximum(np.maximum(uw0 - px.u, px.u - uw1), 0.0)
    dist = np.hypot(dx, du)
    inside = (px.x > xw0) & (px.x < xw1) & (px.u > uw0) & (px.u < uw1)
    rim_w = np.where(px.u < uw0, 1.0, np.where(px.x > xw1, 0.7, 0.45))
    rim = side & ~inside & (dist < 1.6)
    catch = np.maximum(catch, np.where(rim, rim_w * np.exp(-dist / 0.5) * (0.6 + 0.4 * grain), 0.0))
    Z['catch'][:] = np.maximum(Z['catch'], np.clip(catch, 0, 1))
    # нижняя кромка окна местами до стали — там зуб защёлки бьёт при каждом заходе
    Z['bare'][:] = np.maximum(Z['bare'], np.where(rim & (px.u < uw0), 0.55 * np.exp(-dist / 0.3) *
                                                  smooth(0.1, 0.6, fd_grain(s * 1.3, px.u * 3.0)), 0.0))
    return on, s, h


def lips_zones(px, setname, Z, s, h):
    """Губки: верх заглажен затвором (по ходу затвора — вдоль X оружия), наружная кромка верха местами до стали;
    внутренние кромки горловины — латунь от гильз."""
    gz, gx = px.g[:, 2], px.g[:, 0]
    zt = np.where(px.x > STEP_X, Z_TOP - STEP, Z_TOP)
    sd = BODY.sd(px.x, px.y)
    # патроны в горловине — мимо (расстояние до оси верхнего патрона)
    on_round = np.abs(np.hypot(px.y, gz + 17.1) - 6.0) < 0.6
    top = (px.gn[:, 2] > 0.6) & (np.abs(gz - zt) < 0.7) & (sd > -WALL - 3.5) & (np.abs(px.y) > 4.4) & ~on_round
    fx = Field(SEED[setname] + 5, 400.0, -30.0, 30.0, 3.0, 0.08, res=12.0)   # полосы вдоль X оружия
    stripes = 0.8 + 0.2 * fx(gx + 200.0, px.y)
    fl = Field(SEED[setname] + 8, 400.0, -30.0, 30.0, 5.0, 2.0, res=4.0)
    patches = smooth(-0.5, 0.6, fl(gx + 200.0, px.y))           # затвор трёт не весь верх — местами
    lips = np.where(top, 0.6 * stripes * patches * (0.5 + 0.5 * smooth(-6.0, -1.0, sd)), 0.0)
    Z['lips'][:] = np.clip(lips, 0, 1)
    # наружная кромка верха: последние ~1.2 мм наружной стенки под верхом — местами до стали
    fd = Field(SEED[setname] + 6, BODY.P, 0.0, 100.0, 1.5, 0.6, res=8.0)
    edge = (np.abs(sd) < 0.7) & (zt - gz < 1.4) & (zt - gz > -0.3)
    k = smooth(0.15, 0.75, fd(s, gz))
    Z['bare'][:] = np.maximum(Z['bare'], np.where(edge, 0.85 * k * smooth(1.4, 0.2, zt - gz), 0.0))
    Z['streaks'][:] = np.maximum(Z['streaks'], np.where(edge, 0.7 * smooth(-0.3, 0.6, fd(s + 40.0, gz)), 0.0))
    # латунь — на внутренних кромках горловины (|y| 4.5…7.5), у самого верха, местами
    inner = (np.abs(px.y) > 4.3) & (np.abs(px.y) < 7.8) & (zt - gz < 2.8) & (zt - gz > -0.3) & ~on_round & \
        (px.ny * np.sign(px.y) < -0.3)
    fb = Field(SEED[setname] + 7, 400.0, -30.0, 30.0, 2.0, 0.6, res=10.0)
    brass = np.where(inner | (top & (np.abs(px.y) < 6.2)), smooth(-0.2, 0.8, fb(gx + 200.0, gz)) * 0.8, 0.0)
    Z['brass'][:] = np.clip(brass, 0, 1)


def bottom_zones(px, setname, Z):
    """Донышко: потёртые участки кромок по списку BOTTOM, по кромке вокруг — слабо и рвано; царапины по дну."""
    rng = np.random.default_rng(SEED[setname] + 11)
    if setname == 'Mag13':
        sec = PLATE13
        # горизонтальная пластина: контур поперёк оси растянут наклоном оси по X (part_magazine.floorplate13)
        xs = (px.g[:, 0] - CX - (Z_BOT13 - CZ) * math.tan(A)) * CA
        ys = px.y
        z = px.g[:, 2]
        z0, z1 = Z_BOT13 - PLATE_H, Z_BOT13
        nd = -px.gn[:, 2]                                    # нормаль «вниз»
    else:
        sec = BASE30
        xs, ys = px.x, px.y
        z = px.u
        z0, z1 = U_BOT30 - BASE_H, U_BOT30
        nd = -px.nu
    zone = (z > z0 - 0.6) & (z < z1 + 0.4) & (sec.sd(xs, ys) > -4.0)
    sd = sec.sd(xs, ys)
    s = sec.param(xs, ys)
    side = zone & (np.abs(sd) < 0.8) & (np.abs(nd) < 0.75)
    bot = zone & (nd > 0.6) & (z < z0 + 0.6)
    # расстояние до нижней кромки: по борту — вверх от низа, по дну — внутрь от контура
    d_edge = np.where(side, np.maximum(z - z0, 0.0), np.where(bot, np.maximum(-sd, 0.0), 99.0))
    d_top = np.where(side, np.maximum(z1 - z, 0.0), 99.0)
    fd = Field(SEED[setname] + 12, sec.P, -20.0, 20.0, 0.35, 0.35, res=10.0)
    fd_big = Field(SEED[setname] + 13, sec.P, -20.0, 20.0, 2.5, 2.5, res=4.0)
    zz = np.where(side, z - z0, -np.maximum(-sd, 0.0))
    speck = smooth(-0.35, 0.55, fd(s, zz * 1.0))
    val = np.zeros(len(s), np.float32)
    for face, t, length, a, up, inn in BOTTOM[setname]:
        along = band(sec, s, face, t, length * 1.6)
        reach = np.where(side, up * 2.0, inn * 1.8)
        # край участка рваный: досягаемость меняется вдоль контура
        reach = reach * (0.6 + 0.4 * np.clip(fd_big(s + 13.0 * t, 0.0 * s) + 0.5, 0, 1.5))
        val = np.maximum(val, min(1.0, a * 1.15) * along * np.exp(-d_edge / np.maximum(reach * 0.55, 0.2)) *
                         (0.45 + 0.55 * speck))
    # по всей нижней кромке — слабая рваная линия: углы и рёбра «потёрты, но не сплошняком»
    line = 0.38 * np.exp(-d_edge / 0.5) * smooth(0.25, 0.8, fd_big(s, 0.0 * s) * 0.5 + 0.5) * speck
    val = np.maximum(val, line)
    # верхняя кромка донышка (выступ по контуру) — едва-едва, местами
    val = np.maximum(val, 0.22 * np.exp(-d_top / 0.3) * smooth(0.4, 0.9, fd_big(s + 50.0, 0.0 * s) * 0.5 + 0.5))
    Z['bottom'][:] = np.maximum(Z['bottom'], np.clip(val, 0, 1))
    # царапины по дну — прямые отрезки разной длины, пара глубже у сильных углов
    scr = np.zeros(len(s), np.float32)
    bi = np.nonzero(bot)[0]
    bx, by = xs[bi], ys[bi]
    x0, x1, hw = sec.x0, sec.x1, sec.hw
    for k in range(16):
        cx_, cy_ = rng.uniform(x0 + 3, x1 - 3), rng.uniform(-hw + 2, hw - 2)
        ang = rng.uniform(0, math.pi)
        ln = rng.uniform(4.0, 16.0)
        wdt = rng.uniform(0.10, 0.22) if k < 13 else rng.uniform(0.3, 0.45)
        a = rng.uniform(0.25, 0.6) if k < 13 else 0.75
        dx_, dy_ = math.cos(ang), math.sin(ang)
        px_, py_ = bx - cx_, by - cy_
        tt = np.clip(px_ * dx_ + py_ * dy_, -ln / 2, ln / 2)
        dist = np.hypot(px_ - tt * dx_, py_ - tt * dy_)
        fade = 1.0 - smooth(ln * 0.3, ln * 0.5, np.abs(tt))
        scr[bi] = np.maximum(scr[bi], a * np.exp(-0.5 * (dist / (wdt * 0.5)) ** 2) * (0.4 + 0.6 * fade))
    Z['bottom_scr'][:] = np.maximum(Z['bottom_scr'], np.clip(scr, 0, 1))


def sleeve_zones(px, Z):
    """Рукав на 30: верхний срез — упор в низ шахты (участками), рифление и борта — где держат рукой."""
    sec = SLEEVE
    gz, gx = px.g[:, 2], px.g[:, 0]
    sd_b = BODY.sd(px.x, px.y)
    sd_s = sec.sd(px.x, px.y)
    s = sec.param(px.x, px.y)
    ztop = zf(gx)
    top = (np.abs(gz - ztop) < 0.6) & (sd_b > -0.4) & (sd_b < SLV_T + 0.5) & (px.gn[:, 2] > 0.5)
    outer = (np.abs(sd_s) < 0.7) & (gz < ztop + 0.3) & (px.u > U_BOT30 - 0.3)
    fd = Field(SEED['Mag30'] + 21, sec.P, -20.0, 20.0, 0.4, 0.4, res=10.0)
    speck = smooth(-0.4, 0.5, fd(s, gz))
    d_edge = np.where(top, np.maximum(SLV_T - sd_b, 0.0) * 0.6, np.where(outer, np.maximum(ztop - gz, 0.0), 99.0))
    val = np.zeros(len(s), np.float32)
    for face, t, length, a in RIM:
        val = np.maximum(val, min(1.0, a * 1.3) * band(sec, s, face, t, length * 1.3) * np.exp(-d_edge / 1.5) *
                         (0.45 + 0.55 * speck))
    Z['rim'][:] = np.clip(np.where(top | outer, val, 0.0), 0, 1)
    # рифление спереди — вершины между канавками глаже (пальцы), борта рукава — слабо (ладонь)
    ds, ws = D + SLV_T, W + SLV_T
    u_front = u_at(Z_SLEEVE, ds) - 5.0
    length = u_front - U_BOT30
    ph = np.mod(u_front - px.u + 1.6, 3.2) - 1.6             # 0 — середина канавки
    crest = smooth(0.95, 1.25, np.abs(ph))
    front = outer & (px.x > ds - 8.5 + 0.6) & (px.u < u_front + 1.0) & (px.u > u_front - 0.62 * length)
    fb = Field(SEED['Mag30'] + 22, sec.P, -200.0, 200.0, 4.0, 6.0, res=2.0)
    grip = smooth(-0.3, 0.6, fb(s, px.u))
    hand = np.where(front, 0.95 * crest * grip * (0.6 + 0.4 * speck), 0.0)
    # борта: ладонь и пальцы обхватывают рукав посередине высоты, ближе к переду — одно мягкое место, не пятна
    sides = outer & (np.abs(px.ny) > 0.7) & (px.u > U_BOT30 + 4.0)
    um = U_BOT30 + 0.55 * length
    palm = np.exp(-0.5 * ((px.u - um) / (0.22 * length)) ** 2) * smooth(-14.0, 6.0, px.x)
    hand = np.maximum(hand, np.where(sides, 0.22 * palm * (0.75 + 0.25 * np.clip(fb(s + 30.0, px.u), -1, 1)), 0.0))
    Z['hand'][:] = np.clip(hand, 0, 1)
    return s


NAMES = ('polish', 'streaks', 'bare', 'catch', 'lips', 'brass', 'bottom', 'bottom_scr', 'rim', 'hand')


def dilate(img, filled, n=6):
    """Края островов — продолжить значения наружу (мип-уровни не тянут чёрное с пустых мест)."""
    out = img.copy()
    mask = filled.astype(np.uint8)
    k = np.ones((3, 3), np.uint8)
    for _ in range(n):
        grown = cv2.dilate(out, k)
        m2 = cv2.dilate(mask, k)
        new = (m2 > 0) & (mask == 0)
        out[new] = grown[new]
        mask = m2
    return out


def build(setname, preview=False):
    px = Pix(setname)
    n = len(px.idx)
    Z = {k: np.zeros(n, np.float32) for k in NAMES}
    on, s, h = body_zones(px, setname, Z)
    lips_zones(px, setname, Z, s, h)
    bottom_zones(px, setname, Z)
    if setname == 'Mag30':
        sleeve_zones(px, Z)
    # полоса под сталью — светлее (сталь без полосы вокруг выглядела бы пятном без причины)
    Z['streaks'] = np.maximum(Z['streaks'], Z['bare'] * 0.9)
    OUT.mkdir(parents=True, exist_ok=True)
    log = []
    for k in NAMES:
        img = px.image(Z[k])
        if not img.any():
            continue
        img = dilate(img, px.filled)
        cv2.imwrite(str(OUT / f'{setname}_{k}.png'), np.round(np.clip(img, 0, 1) * 255).astype(np.uint8))
        log.append(f'{k} {int((Z[k] > 0.3).sum())}')
    print(setname, ' | '.join(log), flush=True)
    if preview:
        write_preview(px, setname, Z, s, on)


def write_preview(px, setname, Z, s, on):
    """Развёртка сечения корпуса: по горизонтали — контур s (мм), по вертикали — Z оружия (мм); и карта развёртки."""
    col = np.zeros((len(px.idx), 3), np.float32) + 0.09
    layers = (('polish', (0.20, 0.20, 0.21)), ('streaks', (0.42, 0.42, 0.43)), ('catch', (0.40, 0.40, 0.42)),
              ('lips', (0.36, 0.36, 0.37)), ('bottom', (0.45, 0.44, 0.42)), ('bottom_scr', (0.5, 0.5, 0.5)),
              ('rim', (0.45, 0.44, 0.42)), ('hand', (0.30, 0.30, 0.31)), ('brass', (0.55, 0.42, 0.22)),
              ('bare', (0.78, 0.78, 0.80)))
    for k, c in layers:
        m = Z[k][:, None]
        col = col * (1 - m) + m * np.array(c, np.float32)
    k = 6.0
    z0 = -260.0 if setname == 'Mag30' else -140.0
    hh = int((0.0 - z0) * k)
    ww = int(BODY.P * k) + 1
    img = np.zeros((hh, ww, 3), np.float32) + 0.5
    sel = np.nonzero(on)[0]
    cx = np.clip((s[sel] * k).astype(int), 0, ww - 1)
    cy = np.clip(((0.0 - px.g[sel, 2]) * k).astype(int), 0, hh - 1)
    img[cy, cx] = col[sel]
    for name in ('arc_rl', 'arc_fl', 'arc_fr', 'arc_rr'):
        s0, ln = BODY.seg[name]
        for xx in (s0, s0 + ln):
            img[:, min(int(xx * k), ww - 1)] = (0.9, 0.6, 0.3)
    cv2.imwrite(str(OUT / f'{setname}_wear_preview_unrolled.png'), (np.clip(img, 0, 1)[..., ::-1] * 255).astype(np.uint8))
    full = np.zeros((px.size * px.size, 3), np.float32) + 0.5
    full[px.idx] = col
    full = full.reshape(px.size, px.size, 3)
    cv2.imwrite(str(OUT / f'{setname}_wear_preview.png'), (np.clip(full, 0, 1)[..., ::-1] * 255).astype(np.uint8))


def main():
    preview = '--preview' in sys.argv
    sets = [a for a in sys.argv[1:] if not a.startswith('--')] or ['Mag13', 'Mag30']
    for setname in sets:
        build(setname, preview)


if __name__ == '__main__':
    main()
