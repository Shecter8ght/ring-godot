"""Растровая укладка островов развёртки в квадратный атлас — чистый numpy, без Blender (её зовёт tools/asset_kit/uv.py;
так её можно гонять и на снятых данных вне Blender).

Остров здесь — что угодно с полями uvm (координаты петель в метрах, min = 0, повернуты к наименьшему прямоугольнику),
tri_local (треугольники — индексы в uvm), ext (размеры в метрах), k (множитель стороны), a3 (площадь, м²) и group
(группа «разрыва»). У каждого острова две маски пикселей: расширенная на половину отступа между деталями (r1) и на
половину отступа внутри группы (r2). Остров не пересекается маской r2 ни с чем (до любого соседа не меньше 2·r2)
и маской r1 — с островами чужих групп (до них не меньше 2·r1).

Укладка (pack): острова от крупных к мелким, каждый отдельно. «Тетрис»: нижний профиль маски опускается на линию
горизонта в четырёх поворотах (вогнутые края принимают соседей). Линий две: верх всех масок r2 и верх масок r1 — с
хозяином верхнего куска в столбце; над своей группой остров опускается до её маски r2 (свои куски детали встают на
половинный отступ), над чужой — до маски r1. Мелкие острова пробуются ещё и в пустоты под горизонтом: свободный от
масок r1 прямоугольник вдоль и поперёк (суммы площадей на сетке 2 × 2). Берётся место, где верх острова ниже.
Положения — целые пиксели. Масштаб (search) — наибольший, при котором всё легло, половинным делением.

Сшивка (stitch, по желанию): острова одной детали, разрезанные по жёсткому ребру, ставятся вдоль общего ребра с зазором
и кладутся одним блоком. На готовых сетках ВЕРАС (острова Smart UV после упрощения) блоки рваные и ложатся хуже,
чем выигрывают на отступах (сталь 61 % против 63,5 %); пригодится для ровной развёртки до упрощения.
"""
from __future__ import annotations

import math
import time

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

_BIG = 1 << 28


def raster(tri: np.ndarray, w: int, h: int, eps: float = 0.0) -> np.ndarray:
    """Пиксели (h, w), которых касается хоть один треугольник tri (T, 3, 2) в пикселях; строка 0 — низ (v = 0).
    eps — допуск: касание ближе eps к краю пикселя не считается (для проверки готовых UV во float32)."""
    if not len(tri):
        return np.zeros((h, w), bool)
    ys = tri[:, :, 1]
    r0 = np.floor(ys.min(1) + eps).astype(np.int64)
    r1 = np.ceil(ys.max(1) - eps).astype(np.int64)
    if eps > 0:
        tri, r0, r1 = tri[r1 > r0], r0[r1 > r0], r1[r1 > r0]     # касание границы строки в пределах eps — не в счёт
        if not len(tri):
            return np.zeros((h, w), bool)
    r0 = np.clip(r0, 0, h - 1)
    r1 = np.clip(np.maximum(r1, r0 + 1), 1, h)
    n = r1 - r0
    t = np.repeat(np.arange(len(tri)), n)
    row = r0[t] + (np.arange(int(n.sum())) - np.repeat(np.cumsum(n) - n, n))
    lo, hi = row + eps, row + 1.0 - eps
    P = tri[t]
    xmin = np.full(len(t), np.inf)
    xmax = np.full(len(t), -np.inf)
    for k in range(3):
        xa, ya = P[:, k, 0], P[:, k, 1]
        ok = (ya >= lo) & (ya <= hi)
        xmin = np.where(ok, np.minimum(xmin, xa), xmin)
        xmax = np.where(ok, np.maximum(xmax, xa), xmax)
        xb, yb = P[:, (k + 1) % 3, 0], P[:, (k + 1) % 3, 1]
        dy = yb - ya
        nz = np.abs(dy) > 1e-12
        for yl in (lo, hi):
            tt = np.where(nz, (yl - ya) / np.where(nz, dy, 1.0), -1.0)
            ok = nz & (tt >= 0.0) & (tt <= 1.0)
            xi = xa + tt * (xb - xa)
            xmin = np.where(ok, np.minimum(xmin, xi), xmin)
            xmax = np.where(ok, np.maximum(xmax, xi), xmax)
    good = np.isfinite(xmin)
    row, xmin, xmax = row[good], xmin[good], xmax[good]
    c0 = np.floor(xmin + eps).astype(np.int64)
    c1 = np.ceil(xmax - eps).astype(np.int64)
    if eps > 0:
        keep = c1 > c0                                             # то же для столбцов
        row, c0, c1 = row[keep], c0[keep], c1[keep]
    c0 = np.clip(c0, 0, w - 1)
    c1 = np.clip(np.maximum(c1, c0 + 1), 1, w)
    n = h * (w + 1)
    diff = np.bincount(row * (w + 1) + c0, minlength=n) - np.bincount(row * (w + 1) + c1, minlength=n)
    return np.cumsum(diff.reshape(h, w + 1)[:, :w], axis=1) > 0


def _grow(p: np.ndarray, r: int, ax: int) -> np.ndarray:
    n = p.shape[ax]
    c = np.cumsum(p, axis=ax, dtype=np.int32)
    hi = np.minimum(np.arange(n) + r, n - 1)
    lo = np.arange(n) - r - 1
    a = np.take(c, hi, axis=ax)
    b = np.take(c, np.maximum(lo, 0), axis=ax)
    shape = (-1, 1) if ax == 0 else (1, -1)
    return (a - np.where((lo >= 0).reshape(shape), b, 0)) > 0


def dilate(m: np.ndarray, r: int) -> np.ndarray:
    """Расширение квадратом (2r+1)²: маска вырастает на r пикселей со всех сторон."""
    if r <= 0:
        return m.copy()
    h, w = m.shape
    p = np.zeros((h + 2 * r, w + 2 * r), bool)
    p[r:r + h, r:r + w] = m
    return _grow(_grow(p, r, 0), r, 1)


def rot_matrix(q: int, w: int, h: int, x: float = 0, y: float = 0) -> np.ndarray:
    """3 × 3: точка в рамке маски (w × h при q = 0) → рамка-родитель, где маска повёрнута на q × 90° против часовой
    и левым нижним углом стоит в (x, y)."""
    R = {0: ((1, 0), (0, 1)), 1: ((0, -1), (1, 0)), 2: ((-1, 0), (0, -1)), 3: ((0, 1), (-1, 0))}[q]
    t = {0: (0, 0), 1: (h, 0), 2: (w, h), 3: (0, w)}[q]
    M = np.eye(3)
    M[:2, :2] = R
    M[:2, 2] = (t[0] + x, t[1] + y)
    return M


def _profile(m: np.ndarray):
    any_ = m.any(0)
    b = np.where(any_, m.argmax(0), _BIG).astype(np.int32)
    t = np.where(any_, m.shape[0] - 1 - m[::-1].argmax(0), -_BIG).astype(np.int32)
    return b, t, np.flatnonzero(any_)


class Piece:
    """Остров для укладки: маска r1 (рамка куска) и маска r2 в той же рамке; members — [(остров, M 3 × 3: пиксели
    острова → рамка куска)]."""

    def __init__(self, raw: np.ndarray, r1: int, r2: int, group: int, members: list):
        self.mask = dilate(raw, r1)
        d = r1 - r2
        self.inner = np.zeros_like(self.mask)
        self.inner[d:self.mask.shape[0] - d, d:self.mask.shape[1] - d] = dilate(raw, r2)
        self.group = group
        self.members = members
        self.area = int(self.mask.sum())
        self.long, self.short = max(self.mask.shape), min(self.mask.shape)
        self._rot: dict = {}

    def rot(self, q: int):
        """В повороте q: маска r1, её профиль (низ b, верх t, непустые столбцы), профиль маски r2."""
        if q not in self._rot:
            k = (0, -1, 2, 1)[q]
            m, mi = np.rot90(self.mask, k), np.rot90(self.inner, k)
            self._rot[q] = (m,) + _profile(m) + _profile(mi)
        return self._rot[q]


class Skyline:
    """Линии горизонта по столбцам: h2 — верх масок r2; top — верх масок r1, owner — группа верхнего куска,
    other — верх масок r1 чужих для owner групп (не ниже настоящего)."""

    def __init__(self, W: int):
        self.h2 = np.zeros(W, np.int32)
        self.top = np.zeros(W, np.int32)
        self.other = np.zeros(W, np.int32)
        self.owner = np.full(W, -1, np.int32)

    def floor1(self, g: int) -> np.ndarray:
        """Пол для маски r1 острова группы g: над своей группой — верх чужих под ней."""
        return np.where(self.owner == g, self.other, self.top)

    def add(self, x: int, y: int, piece: Piece, q: int) -> None:
        m, b1, t1, c1, b2, t2, c2 = piece.rot(q)
        cols = x + c1
        tn = y + t1[c1] + 1
        top, own, oth = self.top[cols], self.owner[cols], self.other[cols]
        above, same = tn > top, own == piece.group
        self.other[cols] = np.where(above & ~same, np.maximum(oth, top), np.where(~above & ~same, np.maximum(oth, tn), oth))
        self.owner[cols] = np.where(above, piece.group, own)
        self.top[cols] = np.maximum(top, tn)
        c = x + c2
        self.h2[c] = np.maximum(self.h2[c], y + t2[c2] + 1)


def drop(sky: Skyline, W: int, piece: Piece, lim: int, score: str = 'bl'):
    """Лучшее место «тетрисом»: (ключ, верх, x, y, q). score: top — ниже верх острова, затем меньше пустоты под ним;
    waste — меньше пустоты, затем ниже; bl — ниже низ, затем левее."""
    f1 = sky.floor1(piece.group)
    best = None
    for q in range(4):
        m, b1, t1, c1, b2, t2, c2 = piece.rot(q)
        hh, ww = m.shape
        if ww > W or hh > lim:
            continue
        D1 = sliding_window_view(f1, ww)[:, c1] - b1[c1]
        D2 = sliding_window_view(sky.h2, ww)[:, c2] - b2[c2]
        Y = np.maximum(np.maximum(D1.max(1), D2.max(1)), 0)
        top = Y + hh
        if score == 'bl':
            key = Y.astype(np.int64) * (1 << 34) + top
        else:
            waste = (Y[:, None] - D1).sum(1)
            key = (top.astype(np.int64) * (1 << 34) + waste) if score == 'top' else (waste * (1 << 20) + top)
        key = np.where(top <= lim, key, np.iinfo(np.int64).max)
        i = int(np.argmin(key))
        if top[i] > lim:
            continue
        cand = (int(key[i]), int(top[i]), i, int(Y[i]), q)
        if best is None or cand[0] < best[0]:
            best = cand
    return best


class Holes:
    """Пустоты под линией горизонта: левые нижние углы свободных от масок r1 прямоугольников L × S и S × L, целиком
    под горизонтом. Суммы площадей — на сетке 2 × 2 (клетка занята, если занят хоть один её пиксель), места — чётные
    пиксели. Занятое после постройки вычёркивается прямоугольниками (cover)."""

    def __init__(self, occ: np.ndarray, top_line: np.ndarray, L: int, S: int, placed: int, cap: int = 300000):
        self.L, self.S, self.placed = L, S, placed
        self.lists = []
        top = int(top_line.max())
        Wd = occ.shape[1]
        if top < S:
            return
        t2 = (top + 1) // 2
        c = occ[:t2 * 2].reshape(t2, 2, Wd // 2, 2).any(axis=(1, 3))
        Sm = np.zeros((t2 + 1, Wd // 2 + 1), np.int32)
        np.cumsum(np.cumsum(c, axis=0, dtype=np.int32), axis=1, out=Sm[1:, 1:])
        for bw, bh in ((L, S), (S, L)) if L != S else ((L, L),):
            cw, ch = (bw + 1) // 2, (bh + 1) // 2
            if ch > t2 or cw > Wd // 2:
                continue
            tot = Sm[ch:, cw:] - Sm[:-ch, cw:] - Sm[ch:, :-cw] + Sm[:-ch, :-cw]
            ys, xs = np.nonzero(tot == 0)
            ys, xs = ys * 2, xs * 2
            ok = xs + bw <= Wd
            ys, xs = ys[ok], xs[ok]
            under = sliding_window_view(top_line, bw).min(1)
            keep = ys + bh <= under[xs]
            ys, xs = ys[keep][:cap].astype(np.int64), xs[keep][:cap].astype(np.int64)
            self.lists.append([bw, bh, ys, xs, np.ones(len(ys), bool), 0])

    def take(self, piece: Piece):
        """Самое низкое свободное место, куда остров входит в каком-нибудь повороте: (y, x, q) или None."""
        best = None
        for lst in self.lists:
            bw, bh, ys, xs, ok, ptr = lst
            qs = [q for q in range(4) if piece.rot(q)[0].shape[1] <= bw and piece.rot(q)[0].shape[0] <= bh]
            if not qs:
                continue
            n = len(ys)
            while ptr < n and not ok[ptr]:
                nxt = np.flatnonzero(ok[ptr:ptr + 4096])
                ptr = ptr + int(nxt[0]) if len(nxt) else min(n, ptr + 4096)
            lst[5] = ptr
            if ptr >= n:
                continue
            y, x = int(ys[ptr]), int(xs[ptr])
            q = min(qs, key=lambda q: piece.rot(q)[0].shape[0])
            if best is None or y + piece.rot(q)[0].shape[0] < best[0] + piece.rot(best[2])[0].shape[0]:
                best = (y, x, q)
        return best

    def spent(self) -> bool:
        """Свободных мест в списках не осталось."""
        return all(not lst[4][lst[5]:].any() for lst in self.lists)

    def cover(self, y: int, x: int, hh: int, ww: int) -> None:
        for lst in self.lists:
            bw, bh, ys, xs, ok, ptr = lst
            if len(ys):
                ok &= ~((ys > y - bh) & (ys < y + hh) & (xs > x - bw) & (xs < x + ww))


def _settle(occ: np.ndarray, m: np.ndarray, y: int, x: int) -> tuple:
    """Место из пустоты — на чётной сетке: дотолкнуть вниз и влево по пикселю, пока свободно."""
    hh, ww = m.shape
    for _ in range(2):
        if y > 0 and not (occ[y - 1:y - 1 + hh, x:x + ww] & m).any():
            y -= 1
        if x > 0 and not (occ[y:y + hh, x - 1:x - 1 + ww] & m).any():
            x -= 1
    return y, x


def pack(pieces: list, W: int, *, holes: bool = True, hole_long_max: int = 1024, rebuild_every: int = 120,
         score: str = 'bl', order: str = 'area', stats: dict | None = None):
    """Укладка островов в квадрат W × W. Возврат [(q, x, y)] по кускам или None, если что-то не легло."""
    if order == 'side':
        key = lambda i: (-pieces[i].long, -pieces[i].area)
    else:
        key = lambda i: (-pieces[i].area, -pieces[i].long)
    seq = sorted(range(len(pieces)), key=key)
    sky = Skyline(W)
    occ = np.zeros((W, W), bool)
    out = [None] * len(pieces)
    hl = None
    n_holes = 0
    for n, i in enumerate(seq):
        p = pieces[i]
        best = drop(sky, W, p, W, score)
        place = None
        if holes and p.long <= hole_long_max and sky.top.max() >= p.short:
            fits = hl is not None and p.long <= hl.L and p.short <= hl.S
            coarse = hl is not None and p.long * 1.5 < hl.L and p.short * 1.5 < hl.S
            spent = hl is not None and hl.spent()
            if hl is None or n - hl.placed >= rebuild_every or ((coarse or not fits or spent) and n - hl.placed >= 24):
                ahead = [pieces[j] for j in seq[n:n + 48] if pieces[j].long <= hole_long_max]
                L = int(np.percentile([a.long for a in ahead], 80))
                S = int(np.percentile([a.short for a in ahead], 80))
                hl = Holes(occ, sky.top, max(L, p.long), max(S, p.short), n)
            got = hl.take(p)
            if got is not None:
                y, x, q = got
                y, x = _settle(occ, p.rot(q)[0], y, x)
                if best is None or y + p.rot(q)[0].shape[0] <= best[1]:
                    place = (q, x, y)
                    n_holes += 1
        if place is None:
            if best is None:
                return None
            place = (best[4], best[2], best[3])
        q, x, y = place
        m = p.rot(q)[0]
        hh, ww = m.shape
        occ[y:y + hh, x:x + ww] |= m
        sky.add(x, y, p, q)
        if hl is not None:
            hl.cover(y, x, hh, ww)
        out[i] = place
    if stats is not None:
        stats['in_holes'] = n_holes
        stats['below_skyline_free_px'] = int(sky.top.sum() - occ.sum())
    return out


def island_raster(isl, scale: float) -> np.ndarray:
    k = scale * isl.k
    w = max(1, int(math.ceil(isl.ext[0] * k - 1e-6)))
    h = max(1, int(math.ceil(isl.ext[1] * k - 1e-6)))
    return raster(isl.uvm[isl.tri_local] * k, w, h)


class _Placed:
    """Остров в блоке сшивки: преобразование (2 × 2, сдвиг) пикселей острова в рамку блока, растр и маска r2."""

    def __init__(self, isl, R: np.ndarray, t: np.ndarray, scale: float, r2: int):
        self.isl, self.R, self.t = isl, R, t
        self.pts = (isl.uvm * (scale * isl.k)) @ R.T + t
        lo = np.floor(self.pts.min(0)).astype(np.int64)
        hi = np.ceil(self.pts.max(0)).astype(np.int64)
        w, h = max(1, int(hi[0] - lo[0])), max(1, int(hi[1] - lo[1]))
        self.o = lo
        self.raw = raster(self.pts[isl.tri_local] - lo, w, h)
        self.m2 = dilate(self.raw, r2)
        self.o2 = lo - r2

    def clash(self, other: '_Placed') -> bool:
        a0, b0 = self.o2, other.o2
        a1, b1 = a0 + self.m2.shape[::-1], b0 + other.m2.shape[::-1]
        x0, y0 = max(a0[0], b0[0]), max(a0[1], b0[1])
        x1, y1 = min(a1[0], b1[0]), min(a1[1], b1[1])
        if x0 >= x1 or y0 >= y1:
            return False
        sa = self.m2[y0 - a0[1]:y1 - a0[1], x0 - a0[0]:x1 - a0[0]]
        sb = other.m2[y0 - b0[1]:y1 - b0[1], x0 - b0[0]:x1 - b0[0]]
        return bool((sa & sb).any())


def _kabsch2(P: np.ndarray, Q: np.ndarray):
    """Поворот R (без отражения) и сдвиг t: R·P + t ≈ Q."""
    cp, cq = P.mean(0), Q.mean(0)
    U, _s, Vt = np.linalg.svd((P - cp).T @ (Q - cq))
    d = np.sign(np.linalg.det(Vt.T @ U.T)) or 1.0
    R = Vt.T @ np.diag([1.0, d]) @ U.T
    return R, cq - R @ cp


def stitch(islands: list, seams: dict, scale: float, r2: int, max_side: float, k_tol: float = 0.15) -> list:
    """Сшивка групп «разрыва»: острова одной детали, разрезанные по жёсткому ребру, ставятся вдоль общего ребра (поворот
    по точкам шва) и отодвигаются поперёк него на 2·r2 + 2 px — так между растрами не меньше половинного отступа при
    любом округлении. Сшивается, если плотности близки (k в пределах k_tol), остров лёг по другую сторону шва, не
    задел маской r2 уже сшитые и блок не вышел за max_side. Возврат — блоки: списки _Placed (у одиночного — один)."""
    n = len(islands)
    adj: dict = {}
    for (ia, ib), L in seams.items():
        adj.setdefault(ia, []).append((ib, L))
    eye = np.eye(2)
    done = np.zeros(n, bool)
    units = []
    gap = 2 * r2 + 2
    for root in sorted(range(n), key=lambda i: -islands[i].a3 * islands[i].k ** 2):
        if done[root]:
            continue
        done[root] = True
        unit = {root: _Placed(islands[root], eye, np.zeros(2), scale, r2)}
        lo, hi = unit[root].pts.min(0), unit[root].pts.max(0)
        queue = [root]
        while queue:
            ia = queue.pop(0)
            A = unit[ia]
            for ib, L in adj.get(ia, ()):
                if done[ib]:
                    continue
                B = islands[ib]
                if abs(B.k / A.isl.k - 1.0) > k_tol:
                    continue
                pb = B.uvm * (scale * B.k)
                P = np.concatenate([pb[L[:, 2]], pb[L[:, 3]]])
                Q = np.concatenate([A.pts[L[:, 0]], A.pts[L[:, 1]]])
                if np.ptp(Q, axis=0).max() < 1.0:
                    continue
                R, t = _kabsch2(P, Q)
                if np.abs(P @ R.T + t - Q).max() > max(2.0, 0.05 * np.ptp(Q, axis=0).max()):
                    continue                     # шов не совпал (разная длина / изгиб): не сшивать
                # поперёк шва: главное направление точек шва, сторона — где центр B после поворота
                c = Q.mean(0)
                d = np.linalg.svd(Q - c)[2][0]
                nrm = np.array([-d[1], d[0]])
                sb = (pb.mean(0) @ R.T + t - c) @ nrm
                sa = (A.pts.mean(0) - c) @ nrm
                if sb * sa >= 0:
                    continue                     # лёг бы поверх A — нужен переворот, не сшивать
                ok = None
                for extra in (0, 2, 4):
                    cand = _Placed(B, R, t + nrm * np.sign(sb) * (gap + extra), scale, r2)
                    nlo, nhi = np.minimum(lo, cand.pts.min(0)), np.maximum(hi, cand.pts.max(0))
                    if (nhi - nlo).max() > max_side:
                        break
                    if not any(cand.clash(o) for o in unit.values()):
                        ok = cand
                        break
                if ok is None:
                    continue
                unit[ib] = ok
                lo, hi = nlo, nhi
                done[ib] = True
                queue.append(ib)
        units.append(list(unit.values()))
    return units


def pieces_at(scale: float, islands: list, r1: int, r2: int, stats: dict | None = None, seams: dict | None = None,
              max_side: float = 1024) -> list:
    """Куски укладки при масштабе scale (пикс/м при k = 1): сшитые блоки и одиночные острова, маски r1 и r2."""
    raw_px = 0
    pieces = []
    stitched = 0
    for unit in stitch(islands, seams or {}, scale, r2, max_side):
        o = np.min([u.o for u in unit], axis=0)
        e = np.max([u.o + u.raw.shape[::-1] for u in unit], axis=0) - o
        raw = np.zeros((int(e[1]), int(e[0])), bool)
        members = []
        for u in unit:
            x, y = u.o - o
            raw[y:y + u.raw.shape[0], x:x + u.raw.shape[1]] |= u.raw
            M = np.eye(3)
            M[:2, :2] = u.R
            M[:2, 2] = u.t - o + r1
            members.append((u.isl, M))
        raw_px += int(raw.sum())
        stitched += len(unit) if len(unit) > 1 else 0
        pieces.append(Piece(raw, r1, r2, unit[0].isl.group, members))
    if stats is not None:
        stats['raw_px'] = raw_px
        stats['mask_px'] = sum(p.area for p in pieces)
        stats['stitched'] = stitched
        stats['units'] = sum(len(p.members) > 1 for p in pieces)
    return pieces


def search(islands: list, size: int, r1: int, r2: int, *, seams: dict | None = None, max_side: float = 0.05,
           fill_guess: float = 0.55, precision: float = 0.006, max_tries: int = 18, say=None, **opts):
    """Наибольший масштаб (пикс/м), при котором всё легло: (масштаб, куски, места, статистика, пробы)."""
    need = sum(i.a3 * i.k * i.k for i in islands)
    s = size * math.sqrt(fill_guess / need)
    lo = hi = best = None
    tries = []
    for _ in range(max_tries):
        t1 = time.time()
        stats: dict = {}
        pieces = pieces_at(s, islands, r1, r2, stats, seams, max_side=size * max_side)
        t2 = time.time()
        placed = pack(pieces, size, stats=stats, **opts)
        tries.append((round(s / 1000, 3), placed is not None, round(time.time() - t1, 1)))
        if say:
            say('scale px/mm', round(s / 1000, 3), 'ok' if placed else 'no', f'pieces {t2 - t1:.1f}s pack {time.time() - t2:.1f}s')
        if placed is not None:
            lo, best = s, (s, pieces, placed, stats)
        else:
            hi = s
        if lo is None:
            s *= 0.85
        elif hi is None:
            s *= 1.08
        elif hi / lo < 1 + precision:
            break
        else:
            s = math.sqrt(lo * hi)
    if best is None:
        raise RuntimeError('UV: не легло даже на малом масштабе')
    return best + (tries,)


def footprint(pieces: list, placed: list, W: int, r1: int, r2: int) -> int:
    """Пиксели атласа под островами с их отступами после укладки: острова одной группы, стоящие в половинном отступе,
    делят полосу между собой — так считается настоящая потеря на отступы."""
    occ = np.zeros((W, W), bool)
    for p, (q, x, y) in zip(pieces, placed):
        m = p.rot(q)[0]
        occ[y:y + m.shape[0], x:x + m.shape[1]] |= m
    return int(occ.sum())
