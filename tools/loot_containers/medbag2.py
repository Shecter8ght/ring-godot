"""Медицинская сумка-укладка v02: нейлоновая шитая сумка (форма, high-poly) — по образцам владельца 2026-11-13.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
      --python tools/loot_containers/medbag2.py -- build "<RING_Loot_MedBag_v02.blend>" [preview <папка>]

Ткань — не симуляция, а гладкая оболочка со смещением (раздутые панели, заломы у швов, провис верха), поэтому
все накладные детали (кант, молнии, стропы, строчки, ленты) кладутся на неё лучами и ближайшей точкой.
Состояния: закрыта и раскрыта (клапан 110°, ручки лежат). Всё в метрах, Z вверх, лицо к −Y, корень на полу.
Развёртка — в миллиметрах (слой UV «UVmm», номер острова — атрибут «isl»); упаковку в атласы делает lc3_bag_uv.py.
"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "dorm_modules"))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector as V, noise  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import mlib as L  # noqa: E402

TAU = 2 * math.pi
W, D, H = 0.536, 0.285, 0.300           # корпус: ширина (X), глубина (Y), высота (Z)
HX, HY, HZ = W / 2, D / 2, H / 2
RC = 0.022                              # скругление рёбер
ZB = 0.040                              # верх чёрной ленты низа
ZIPX = 0.234                            # молния клапана: боковые ветки x = ±ZIPX, спереди y = ZIPY0, у шарнира y = ZIPY1
ZIPY0, ZIPY1 = -0.112, 0.105
HINGE = V((0.0, ZIPY1, H))
CELL = 0.006
BEND_K = 0.9                          # провис раскрытого клапана, м на м²
TH = 0.0026                             # толщина ткани (Solidify)

SIM = {}


def rng(seed):
    return random.Random(seed)


# ======================================================================== материалы
def mats() -> dict:
    return {
        "fabric": L.material("Ткань_красная_оксфорд", (0.32, 0.03, 0.04), 0.55),
        "fabric_in": L.material("Подкладка_красная", (0.25, 0.03, 0.04), 0.7),
        "band": L.material("Ткань_чёрная_лента", (0.025, 0.025, 0.027), 0.6),
        "webbing": L.material("Стропа_красная", (0.30, 0.02, 0.035), 0.7),
        "piping": L.material("Кант_серый", (0.30, 0.30, 0.31), 0.6),
        "ztape": L.material("Тесьма_молнии_чёрная", (0.02, 0.02, 0.022), 0.75),
        "zcoil": L.material("Спираль_молнии", (0.02, 0.02, 0.022), 0.4),
        "metal": L.material("Металл_язычки", (0.6, 0.6, 0.6), 0.3, 1.0),
        "tip": L.material("Резиновый_наконечник", (0.05, 0.35, 0.35), 0.5),
        "reflect": L.material("Лента_светоотражающая", (0.75, 0.77, 0.72), 0.35),
        "pvc": L.material("ПВХ_окно", (0.7, 0.75, 0.8), 0.12, 0.0, 0.25),
        "patch": L.material("Нашивка", (0.04, 0.3, 0.2), 0.7),
        "label": L.material("Ярлык", (0.8, 0.8, 0.85), 0.6),
        "t_red": L.material("Нить_красная", (0.4, 0.04, 0.05), 0.6),
        "t_black": L.material("Нить_чёрная", (0.03, 0.03, 0.03), 0.6),
        "t_gray": L.material("Нить_серая", (0.5, 0.5, 0.5), 0.6),
        "t_white": L.material("Нить_белая", (0.85, 0.85, 0.85), 0.6),
        "mesh": L.material("Сетка_карманов", (0.03, 0.03, 0.03), 0.8, 0.0, 0.6),
        "elastic": L.material("Резинка_держателей", (0.02, 0.02, 0.02), 0.85),
        "hook": L.material("Липучка", (0.02, 0.02, 0.02), 0.9),
    }


MAT_ORDER = list(mats().keys()) if False else None
THREADS = ("t_red", "t_black", "t_gray", "t_white")


# ======================================================================== узлы сетки и смещение
def axis_nodes(h, r, seg, breaks, cell):
    t = [r * math.tan(math.radians(45.0 * k / seg)) for k in range(seg + 1)]
    lo = [-(h - r) - tk for tk in reversed(t)]
    hi = [(h - r) + tk for tk in t]
    a, b = -(h - r), (h - r)
    bp = sorted(set([a, b] + [x for x in breaks if a < x < b]))
    mid = [x for x in bp if a < x < b]
    for i in range(len(bp) - 1):
        n = max(1, round((bp[i + 1] - bp[i]) / cell))
        mid += [bp[i] + (bp[i + 1] - bp[i]) * k / n for k in range(1, n)]
    return lo + sorted(mid) + hi


def unfold(c, h, r):
    """Развёртка координаты вдоль скругления: на дуге — длина дуги."""
    a = abs(c)
    if a <= h - r:
        return c
    s = min(1.0, (a - (h - r)) / r)
    return math.copysign(h - r + r * math.asin(s), c)


def prof(c):
    return max(0.0, 1.0 - c * c) ** 0.6


FOLDS = [
    # центр (идеальный), нормаль грани, направление складки, амплитуда, ширина поперёк, длина вдоль
    ((-0.205, -HY, 0.212), (0, -1, 0), (0.45, 0, -0.9), 0.0042, 0.013, 0.055),
    ((0.212, -HY, 0.212), (0, -1, 0), (-0.40, 0, -0.9), 0.0036, 0.012, 0.050),
    ((-0.060, -HY, 0.262), (0, -1, 0), (0.1, 0, 1.0), 0.0030, 0.018, 0.040),
    ((0.058, -HY, 0.268), (0, -1, 0), (-0.1, 0, 1.0), 0.0034, 0.017, 0.045),
    ((HX, 0.015, 0.185), (1, 0, 0), (0.0, 0.35, -0.9), 0.0044, 0.016, 0.060),
    ((-HX, -0.04, 0.150), (-1, 0, 0), (0.0, -0.3, -0.9), 0.0038, 0.015, 0.070),
    ((-0.10, HY, 0.255), (0, 1, 0), (1.0, 0, 0.25), 0.0034, 0.015, 0.060),
    ((0.17, HY, 0.120), (0, 1, 0), (0.3, 0, -1.0), 0.0030, 0.016, 0.050),
]


def disp(p: V, n: V, seed: int = 0) -> V:
    """Смещение ткани: выпуклые наружу стенки, мягкая низкочастотная рябь, несколько крупных неравных складок, провис верха."""
    ax = (abs(n.x), abs(n.y), abs(n.z))
    cx, cy, cz = p.x / HX, p.y / HY, (p.z - HZ) / HZ
    bulge = (ax[1] ** 4) * 0.0062 * prof(cx) * prof(cz) + (ax[0] ** 4) * 0.0044 * prof(cy) * prof(cz) \
        + (ax[2] ** 4) * (0.0046 if n.z > 0 else 0.0010) * prof(cx) * prof(cy)
    q = V(p)
    w = 0.0019 * noise.noise(q * 8.0 + V((3.1, 1.7, 5.3))) + 0.0007 * noise.noise(q * 19.0 + V((7.7, 2.3, 1.1)))
    out = V(p) + n * (bulge + w)
    for c, fn, fd, amp, sp, sa in FOLDS:
        fn_, fd_ = V(fn), V(fd).normalized()
        if n.dot(fn_) < 0.5:
            continue
        r = V(p) - V(c)
        al = r.dot(fd_)
        u = fd_.cross(fn_).normalized()
        dp = r.dot(u)
        out += n * (amp * (dp / sp) * math.exp(-0.5 * (dp / sp) ** 2) * math.exp(-(al / sa) ** 2))
    out.z -= 0.0062 * prof(cx) * prof(cy) * max(0.0, n.z)
    return out


def build_shell():
    """Целая оболочка со всеми узлами; затем грани делятся по панелям. Возвращает {имя: bmesh} с идеальными данными."""
    ns = [axis_nodes(HX, RC, 4, [-ZIPX, ZIPX], CELL), axis_nodes(HY, RC, 4, [ZIPY0, ZIPY1], CELL),
          axis_nodes(HZ, RC, 4, [ZB - HZ], CELL)]
    ctr = V((0, 0, HZ))
    hs = (HX, HY, HZ)
    cache, info = {}, {}
    bm = bmesh.new()

    def vert(i, j, k):
        key = (i, j, k)
        if key not in cache:
            p = V((ns[0][i], ns[1][j], ns[2][k]))
            inner = V([max(-hs[a] + RC, min(hs[a] - RC, p[a])) for a in range(3)])
            d = p - inner
            nn = d.normalized() if d.length > 1e-9 else V((0, 0, 1))
            if d.length > 1e-9:
                p = inner + nn * RC
            v = bm.verts.new(p + ctr)
            cache[key] = v
            info[v] = (p + ctr, nn)
        return cache[key]
    n = [len(a) for a in ns]
    for ax in range(3):
        for sgn in (-1, 1):
            a1, a2 = [i for i in range(3) if i != ax]
            idx = [0, 0, 0]
            idx[ax] = 0 if sgn < 0 else n[ax] - 1
            for p in range(n[a1] - 1):
                for q in range(n[a2] - 1):
                    cs = []
                    for dp, dq in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        ii = list(idx)
                        ii[a1], ii[a2] = p + dp, q + dq
                        cs.append(vert(*ii))
                    bm.faces.new(cs)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm, info


def panel_of(f, info):
    nn = V((0, 0, 0))
    c = V((0, 0, 0))
    for v in f.verts:
        nn += info[v][1]
        c += info[v][0]
    nn /= len(f.verts)
    c /= len(f.verts)
    ax = max(range(3), key=lambda i: abs(nn[i]))
    side = {(0, -1): "left", (0, 1): "right", (1, -1): "front", (1, 1): "back", (2, -1): "bottom", (2, 1): "top"}[(ax, 1 if nn[ax] > 0 else -1)]
    return side, c


def uv_of(side, p):
    ux, uy, uz = unfold(p.x, HX, RC), unfold(p.y, HY, RC), unfold(p.z - HZ, HZ, RC) + HZ
    return {"front": (ux, uz), "back": (-ux, uz), "left": (-uy, uz), "right": (uy, uz), "top": (ux, uy), "bottom": (ux, -uy)}[side]


def split_shell(bm, info, seed=1):
    """Делит оболочку на корпус / ленту / клапан, смещает вершины, пишет UVmm и острова. Возвращает три bmesh."""
    groups = {"body": [], "band": [], "flap": []}
    for f in bm.faces:
        side, c = panel_of(f, info)
        if c.z < ZB - 1e-5:
            g = "band"
        elif side == "top" and abs(c.x) < ZIPX - 1e-5 and ZIPY0 + 1e-5 < c.y < ZIPY1 - 1e-5:
            g = "flap"
        else:
            g = "body"
        groups[g].append((f, side, c))
    out = {}
    for g, items in groups.items():
        nb = bmesh.new()
        uvl = nb.loops.layers.uv.new("UVmm")
        isl = nb.faces.layers.int.new("isl")
        names = {}
        vm = {}
        for f, side, c in items:
            vs = []
            for v in f.verts:
                if v not in vm:
                    p0, nn = info[v]
                    nv = nb.verts.new(disp(p0, nn, seed))
                    vm[v] = nv
                vs.append(vm[v])
            nf = nb.faces.new(vs)
            nn_i = V((0, 0, 0))
            for v in f.verts:
                nn_i += info[v][1]
            nf.normal_update()
            if nf.normal.dot(nn_i) < 0:
                nf.normal_flip()
            if g == "body" and side == "top":
                tag = "top_f" if c.y < ZIPY0 else ("top_b" if c.y > ZIPY1 else ("top_l" if c.x < 0 else "top_r"))
            elif g == "flap":
                tag = "flap"
            elif g == "band":
                tag = "band_" + side
            else:
                tag = side
            if tag not in names:
                names[tag] = len(names)
            nf[isl] = names[tag]
            for lp, v in zip(nf.loops, f.verts):
                u, w = uv_of(side, info[v][0])
                lp[uvl].uv = (u * 1000.0, w * 1000.0)
        nb.normal_update()
        out[g] = (nb, names)
    return out


# ======================================================================== поверхность для накладных деталей
class Surf:
    def __init__(self, bms):
        verts, polys, vn = [], [], []
        for bm in bms:
            bm.verts.index_update()
            bm.verts.ensure_lookup_table()
            bm.normal_update()
            base = len(verts)
            verts += [v.co.copy() for v in bm.verts]
            vn += [v.normal.copy() for v in bm.verts]
            polys += [tuple(base + v.index for v in f.verts) for f in bm.faces]
        self.verts, self.vn, self.polys = verts, vn, polys
        self.tree = BVHTree.FromPolygons(verts, polys)

    def _nrm(self, loc, fi):
        ws, acc = 0.0, V((0, 0, 0))
        for i in self.polys[fi]:
            w = 1.0 / ((self.verts[i] - loc).length + 1e-4)
            acc += self.vn[i] * w
            ws += w
        return (acc / ws).normalized()

    def ray(self, origin, direction, far=3.0):
        loc, nrm, fi, dist = self.tree.ray_cast(V(origin), V(direction), far)
        if loc is None:
            return None
        return loc, self._nrm(loc, fi)

    def near(self, p, far=0.05):
        loc, nrm, fi, dist = self.tree.find_nearest(V(p), far)
        if loc is None:
            return None
        return loc, self._nrm(loc, fi)


def resample(pts, step, closed=False):
    pts = [V(p) for p in pts]
    if closed:
        pts = pts + [pts[0]]
    out = [pts[0]]
    acc = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        seg = (b - a).length
        if seg < 1e-9:
            continue
        d = step - acc
        while d <= seg:
            out.append(a + (b - a) * (d / seg))
            d += step
        acc = seg - (d - step)
    if (out[-1] - pts[-1]).length > step * 0.3:
        out.append(pts[-1])
    if closed and (out[-1] - out[0]).length < step * 0.5:
        out.pop()
    return out


def smooth_pts(pts, iters=2, closed=False, keep_ends=True):
    pts = [V(p) for p in pts]
    n = len(pts)
    for _ in range(iters):
        new = []
        for i in range(n):
            if not closed and (i == 0 or i == n - 1) and keep_ends:
                new.append(pts[i])
                continue
            a, b = pts[(i - 1) % n], pts[(i + 1) % n]
            new.append(pts[i] * 0.5 + (a + b) * 0.25)
        pts = new
    return pts


def fillet_poly(pts, r, step=0.0015, closed=False):
    """Ломаная со скруглёнными углами (радиус r), плотные точки."""
    pts = [V(p) for p in pts]
    n = len(pts)
    path = []
    for i in range(n):
        if not closed and (i == 0 or i == n - 1):
            path.append(pts[i])
            continue
        p0, p1, p2 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n]
        a, b = (p0 - p1).normalized(), (p2 - p1).normalized()
        ang = math.acos(max(-1.0, min(1.0, a.dot(b))))
        if ang < 1e-3 or abs(ang - math.pi) < 1e-3:
            path.append(p1)
            continue
        tl = r / math.tan(ang / 2)
        tl = min(tl, (p0 - p1).length * 0.5, (p2 - p1).length * 0.5)
        rr = tl * math.tan(ang / 2)
        c = p1 + (a + b).normalized() * (rr / math.sin(ang / 2))
        s0, s1 = p1 + a * tl, p1 + b * tl
        e0, e1 = (s0 - c), (s1 - c)
        sweep = e0.angle(e1)
        axis = e0.cross(e1).normalized()
        k = max(3, int(sweep * rr / step))
        for j in range(k + 1):
            path.append(c + Matrix.Rotation(sweep * j / k, 3, axis) @ e0)
    return resample(path, step, closed)


# ======================================================================== лента по пути
def frames_on(pts, nrm, lateral=None):
    """Рамки (p, n, b): n — нормаль поверхности, b = t × n; lateral — желаемое направление b (знак)."""
    out = []
    m = len(pts)
    for i in range(m):
        t = (pts[min(i + 1, m - 1)] - pts[max(i - 1, 0)]).normalized()
        nn = (nrm[i] - t * nrm[i].dot(t)).normalized()
        b = t.cross(nn).normalized()
        if lateral is not None and b.dot(lateral[i]) < 0:
            b = -b
        out.append((pts[i], nn, b))
    return out


def ribbon(bm, frames, profile, isl0=0, mat=0, closed_profile=False, closed_path=False, chunk=0.9, caps=True, hfun=None,
           u_off=0.0, v_off=0.0):
    """Лента по рамкам. profile — [(поперёк b, высота по n)] в метрах. UVmm: u — длина пути, v — длина профиля (мм);
    слишком длинное режется на острова ≤ chunk. Возвращает число островов."""
    uvl = bm.loops.layers.uv.get("UVmm") or bm.loops.layers.uv.new("UVmm")
    isl = bm.faces.layers.int.get("isl") or bm.faces.layers.int.new("isl")
    m = len(frames)
    k = len(profile)
    rings = []
    for i, (p, n, b) in enumerate(frames):
        hs = hfun(i) if hfun else 1.0
        rings.append([bm.verts.new(p + b * v + n * (h * hs if h > 0.0004 else h)) for v, h in profile])
    # накопленные длины
    s = [0.0]
    for i in range(1, m):
        s.append(s[-1] + (frames[i][0] - frames[i - 1][0]).length)
    if closed_path:
        s.append(s[-1] + (frames[0][0] - frames[-1][0]).length)
    pl = [0.0]
    for j in range(1, k):
        pl.append(pl[-1] + math.hypot(profile[j][0] - profile[j - 1][0], profile[j][1] - profile[j - 1][1]))
    ptot = pl[-1] + (math.hypot(profile[0][0] - profile[-1][0], profile[0][1] - profile[-1][1]) if closed_profile else 0.0)
    chunk_of = [int(s[i] / chunk) if chunk else 0 for i in range(len(s))]
    nseg = m if closed_path else m - 1
    faces = []
    for i in range(nseg):
        j2 = (i + 1) % m
        ci = chunk_of[i]
        base = ci * chunk if chunk else 0.0
        ua, ub = (s[i] - base) * 1000.0, (s[i + 1] - base) * 1000.0
        for j in range(k if closed_profile else k - 1):
            q = (j + 1) % k
            f = bm.faces.new((rings[i][j], rings[i][q], rings[j2][q], rings[j2][j]))
            va = (pl[j] if j < k else 0.0) * 1000.0
            vb = (pl[q] if q > j else ptot) * 1000.0
            for lp, uv in zip(f.loops, ((ua, va), (ua, vb), (ub, vb), (ub, va))):
                lp[uvl].uv = (uv[0] + u_off, uv[1] + v_off)
            f[isl] = isl0 + ci
            f.material_index = mat
            faces.append(f)
    if caps and not closed_path:
        for ring, idx, rev in ((rings[0], 0, True), (rings[-1], m - 1, False)):
            if closed_profile and k >= 3:
                f = bm.faces.new(ring[::-1] if rev else ring)
                ci = chunk_of[idx]
                base = ci * chunk if chunk else 0.0
                for lp, (vv, hh) in zip(f.loops, (profile[::-1] if rev else profile)):
                    lp[uvl].uv = ((s[idx] - base) * 1000.0 + u_off, (vv + 0.05) * 1000.0 + v_off)
                f[isl] = isl0 + ci
                f.material_index = mat
    return (chunk_of[-1] if chunk else 0) + 1


# ======================================================================== мелкие вещи
FIXED_UV = {"t_red": (20.0, 4090.0), "t_black": (84.0, 4090.0), "t_gray": (148.0, 4090.0), "t_white": (212.0, 4090.0)}
UV_FIXED_ISL = 255


def stitches_on(bm, pts, nrms, thread, pitch=0.0032, length=0.0030, lift=0.0003, rnd=None, mat_index=0):
    """pts / nrms — готовые плотные точки (шаг уже ~pitch); ставит по призме на точку по касательной."""
    uvl = bm.loops.layers.uv.get("UVmm") or bm.loops.layers.uv.new("UVmm")
    isl = bm.faces.layers.int.get("isl") or bm.faces.layers.int.new("isl")
    uc = FIXED_UV[thread]
    m = len(pts)
    cnt = 0
    for i in range(m):
        p, n = pts[i], nrms[i]
        t = (pts[min(i + 1, m - 1)] - pts[max(i - 1, 0)])
        if t.length < 1e-9:
            continue
        t.normalize()
        b = t.cross(n).normalized()
        jit = (rnd.uniform(-1, 1) * 0.0002) if rnd else 0.0
        c = p + n * lift + b * jit
        hl, hw, ht = length / 2, 0.00055, 0.0007
        a0, a1 = c - t * hl, c + t * hl
        vs = [bm.verts.new(a0 + b * hw), bm.verts.new(a0 - b * hw), bm.verts.new(a0 + n * ht),
              bm.verts.new(a1 + b * hw), bm.verts.new(a1 - b * hw), bm.verts.new(a1 + n * ht)]
        for quad in ((0, 3, 5, 2), (1, 2, 5, 4), (0, 1, 4, 3)):
            f = bm.faces.new([vs[i_] for i_ in quad])
            f.material_index = mat_index
        for tri in ((0, 2, 1), (3, 4, 5)):
            f = bm.faces.new([vs[i_] for i_ in tri])
            f.material_index = mat_index
        cnt += 1
    for f in bm.faces:
        pass
    return cnt


def finalize_fixed_uv(bm, mat_threads):
    """Строчки: у всех граней с материалом-ниткой UV — в клетку своей нити, остров 255 (упаковщик не трогает)."""
    uvl = bm.loops.layers.uv.get("UVmm")
    isl = bm.faces.layers.int.get("isl")
    for f in bm.faces:
        thr = mat_threads.get(f.material_index)
        if thr is None:
            continue
        uc = FIXED_UV[thr]
        for lp in f.loops:
            lp[uvl].uv = (uc[0] + 0.0, uc[1] + 0.0)
        f[isl] = UV_FIXED_ISL


def new_bm():
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVmm")
    bm.faces.layers.int.new("isl")
    return bm


def to_obj(bm, name, coll, mlist, parent, origin=(0, 0, 0), parent_origin=(0, 0, 0), smooth=True, solid=None, names=None, recalc=True):
    """bmesh → объект; геометрия задана в осях корня, начало объекта — origin, родитель — с началом parent_origin."""
    if recalc:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    for m in mlist:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if names is not None:
        ob["isl_names"] = json.dumps(names, ensure_ascii=False)
    if tuple(origin) != (0, 0, 0):
        me.transform(Matrix.Translation(-V(origin)))
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.location = V(origin) - V(parent_origin)
    if solid:
        md = ob.modifiers.new("Ткань", "SOLIDIFY")
        md.thickness = solid[0]
        md.offset = -1
        md.material_offset = solid[1]
        md.material_offset_rim = 0
        md.use_even_offset = True
    return ob


# ======================================================================== накладка по поверхности
def smooth_nrm(nrm, it=2):
    n = len(nrm)
    for _ in range(it):
        nrm = [((nrm[max(i - 1, 0)] + nrm[i] * 2 + nrm[min(i + 1, n - 1)])).normalized() for i in range(n)]
    return nrm


def conform(surf, plan, mode, lift=0.0, it=2, clamp=True, closed=False):
    """Путь по плану (точки в осях корня) → точки на поверхности лучом по оси (mode: y- y+ x- x+ z+) или ближайшей."""
    pts, nrm, base = [], [], []
    for p in plan:
        p = V(p)
        if mode == "y-":
            r = surf.ray(V((p.x, -1.0, p.z)), V((0, 1, 0)))
        elif mode == "y+":
            r = surf.ray(V((p.x, 1.0, p.z)), V((0, -1, 0)))
        elif mode == "x-":
            r = surf.ray(V((-1.0, p.y, p.z)), V((1, 0, 0)))
        elif mode == "x+":
            r = surf.ray(V((1.0, p.y, p.z)), V((-1, 0, 0)))
        elif mode == "z+":
            r = surf.ray(V((p.x, p.y, 1.0)), V((0, 0, -1)))
        else:
            r = surf.near(p, 0.04)
        if r is None:
            continue
        pts.append(r[0])
        nrm.append(r[1])
    if len(pts) < 2:
        return pts, nrm
    sm = smooth_pts(pts, it, closed=closed) if it else pts
    if clamp and it:
        # сглаживание не должно уводить внутрь ткани: выталкиваем по нормали, если ушли глубже исходной точки
        fixed = []
        for a, b, nn in zip(sm, pts, nrm):
            dd = (a - b).dot(nn)
            fixed.append(a - nn * dd if dd < 0 else a)
        sm = fixed
    nr = smooth_nrm(nrm, 2)
    return [q + nn * lift for q, nn in zip(sm, nr)], nr


def offset_line(frames, ob, on):
    return [p + b * ob + n * on for p, n, b in frames], [n for p, n, b in frames]


def rect_path(x0, x1, z0, z1, r, y=0.0, step=0.0015):
    return fillet_poly([V((x0, y, z0)), V((x1, y, z0)), V((x1, y, z1)), V((x0, y, z1))], r, step, closed=True)


def circle_profile(r, k=8, h0=0.0):
    return [(r * math.cos(TAU * i / k), h0 + r * math.sin(TAU * i / k)) for i in range(k)]


def rect_profile(w, th, h0=0.0):
    return [(-w / 2, h0), (w / 2, h0), (w / 2, h0 + th), (-w / 2, h0 + th)]


_ISL = [1000]


def place_box(bm, size, r, matrix, mat=0, seg=2):
    """Скруглённая коробка размером size в осях matrix (столбцы — оси длины, ширины, толщины); у неё 6 островов по сторонам."""
    hs = [s / 2 for s in size]
    r = min(r, min(hs) - 1e-5)

    def axn(h):
        t = [r * math.tan(math.radians(45.0 * j / seg)) for j in range(seg + 1)]
        return [-(h - r) - tk for tk in reversed(t)] + [(h - r) + tk for tk in t]
    ns = [axn(h) for h in hs]
    cache, loc = {}, {}
    uvl = bm.loops.layers.uv.get("UVmm")
    isl = bm.faces.layers.int.get("isl")

    def vert(i, j, kk):
        key = (i, j, kk)
        if key not in cache:
            p = V((ns[0][i], ns[1][j], ns[2][kk]))
            inner = V([max(-hs[a] + r, min(hs[a] - r, p[a])) for a in range(3)])
            d = p - inner
            if d.length > 1e-9:
                p = inner + d.normalized() * r
            v = bm.verts.new(matrix @ p)
            cache[key] = v
            loc[v] = p
        return cache[key]
    n = [len(a) for a in ns]
    ids = {}
    fcs = []
    for ax in range(3):
        for sgn in (-1, 1):
            a1, a2 = [i for i in range(3) if i != ax]
            idx = [0, 0, 0]
            idx[ax] = 0 if sgn < 0 else n[ax] - 1
            ids[(ax, sgn)] = _ISL[0]
            _ISL[0] += 1
            for p in range(n[a1] - 1):
                for q in range(n[a2] - 1):
                    cs = []
                    for dp, dq in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        ii = list(idx)
                        ii[a1], ii[a2] = p + dp, q + dq
                        cs.append(vert(*ii))
                    f = bm.faces.new(cs)
                    f.material_index = mat
                    f[isl] = ids[(ax, sgn)]
                    for lp in f.loops:
                        q3 = loc[lp.vert]
                        lp[uvl].uv = (q3[a1] * 1000.0 * (1 if sgn > 0 else -1), q3[a2] * 1000.0)
                    fcs.append(f)
    return fcs


def frame_matrix(p, ex, ey, ez):
    ex, ey, ez = ex.normalized(), ey.normalized(), ez.normalized()
    m = Matrix(((ex.x, ey.x, ez.x, p.x), (ex.y, ey.y, ez.y, p.y), (ex.z, ey.z, ez.z, p.z), (0, 0, 0, 1)))
    return m


def set_uv_box(bm, faces, u0, v0, sx=1.0, sy=1.0, isl_id=0):
    """Плоская развёртка коробки (по мм) — для мелких деталей: все грани в один островок."""
    uvl = bm.loops.layers.uv.get("UVmm")
    isl = bm.faces.layers.int.get("isl")
    for f in faces:
        c = f.calc_center_median()
        for lp in f.loops:
            q = lp.vert.co - c
            lp[uvl].uv = (u0 + (q.x * 1000.0), v0 + (q.y * 1000.0))
        f[isl] = isl_id


def grid_surface(bm, surf, plan_xy, nu, nv, mode, lift, island, uvfun, mat=0, outward=None):
    """Сетка nu × nv по плану (функция (i, j) → точка плана), поднятая на lift над поверхностью."""
    uvl = bm.loops.layers.uv.get("UVmm")
    isl = bm.faces.layers.int.get("isl")
    vs = [[None] * (nv + 1) for _ in range(nu + 1)]
    for i in range(nu + 1):
        for j in range(nv + 1):
            p = plan_xy(i, j)
            if mode == "y-":
                r = surf.ray(V((p.x, -1.0, p.z)), V((0, 1, 0)))
            elif mode == "y+":
                r = surf.ray(V((p.x, 1.0, p.z)), V((0, -1, 0)))
            else:
                r = surf.ray(V((p.x, p.y, 1.0)), V((0, 0, -1)))
            if r is None:
                r = (p, V((0, -1, 0)))
            vs[i][j] = (bm.verts.new(r[0] + r[1] * lift(i, j) if callable(lift) else r[0] + r[1] * lift), p)
    for i in range(nu):
        for j in range(nv):
            quad = [vs[i][j], vs[i + 1][j], vs[i + 1][j + 1], vs[i][j + 1]]
            f = bm.faces.new([q[0] for q in quad])
            f.material_index = mat
            f[isl] = island
            for lp, q in zip(f.loops, quad):
                lp[uvl].uv = uvfun(q[1])
            if outward is not None:
                f.normal_update()
                if f.normal.dot(outward) < 0:
                    f.normal_flip()
    return vs


def resample2(pts, nrm, step, closed=False):
    """Ресэмпл пути вместе с нормалями (линейно)."""
    pts = [V(p) for p in pts]
    nrm = [V(n) for n in nrm]
    if closed:
        pts, nrm = pts + [pts[0]], nrm + [nrm[0]]
    out, on = [pts[0]], [nrm[0]]
    acc = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        seg = (b - a).length
        if seg < 1e-9:
            continue
        d = step - acc
        while d <= seg:
            k = d / seg
            out.append(a + (b - a) * k)
            on.append((nrm[i] * (1 - k) + nrm[i + 1] * k).normalized())
            d += step
        acc = seg - (d - step)
    if closed and (out[-1] - out[0]).length < step * 0.5:
        out.pop()
        on.pop()
    return out, on


class Acc:
    """Накопитель мелких деталей по (родитель, вид): один объект на вид."""
    KINDS = {
        "piping": ["piping"], "ztape": ["ztape"], "zcoil": ["zcoil"], "webbing": ["webbing"], "metal": ["metal"],
        "tip": ["tip"], "reflect": ["reflect"], "pvc": ["pvc", "label"], "patch": ["patch"], "label": ["label"],
        "stitch": ["t_red", "t_black", "t_gray", "t_white"], "mesh": ["mesh"], "elastic": ["elastic"], "hook": ["hook"],
        "divider": ["fabric_in"], "frame": ["ztape"],
    }
    TITLE = {"piping": "кант", "ztape": "молния_тесьма", "zcoil": "молния_спираль", "webbing": "стропы", "metal": "металл",
             "tip": "наконечники", "reflect": "лента_светоотр", "pvc": "окно_бирки", "patch": "эмблема", "label": "ярлык",
             "stitch": "строчки", "mesh": "сетка", "elastic": "резинки", "hook": "липучки", "divider": "перегородки",
             "frame": "рамка_окна"}

    def __init__(self):
        self.d = {}
        self.cur = {}

    def bm(self, parent, kind):
        k = (parent, kind)
        if k not in self.d:
            self.d[k] = new_bm()
            self.cur[k] = 0
        return self.d[k]

    def island(self, parent, kind):
        """Следующий свободный номер острова в объекте этого вида."""
        self.bm(parent, kind)
        k = (parent, kind)
        self.cur[k] += 1
        return self.cur[k] - 1

    def rib(self, parent, kind, frames, profile, mat=0, **kw):
        bm = self.bm(parent, kind)
        k = (parent, kind)
        n = ribbon(bm, frames, profile, self.cur[k], mat, **kw)
        self.cur[k] += n
        return n


def thread_mat_index(thread):
    return THREADS.index(thread)


def add_stitches(acc, parent, pts, nrm, thread, pitch=0.0032, closed=False, lift=0.0003, rnd=None, length=0.0030):
    if len(pts) < 2:
        return
    p2, n2 = resample2(pts, nrm, pitch, closed)
    stitches_on(acc.bm(parent, "stitch"), p2, n2, thread, pitch, length, lift, rnd, mat_index=thread_mat_index(thread))


def side_lines(acc, parent, frames, offs, thread, lift=0.0003, rnd=None, closed=False, pitch=0.0032):
    for ob in offs:
        pts, nrm = offset_line(frames, ob, 0.0)
        add_stitches(acc, parent, pts, nrm, thread, pitch, closed, lift, rnd)


def piping_ribbon(acc, parent, pts, nrm, closed, isl0=0, lateral=None):
    fr = frames_on(pts, nrm, lateral)
    arc = [(0.0020 * math.cos(math.radians(a)), 0.0012 + 0.0020 * math.sin(math.radians(a))) for a in range(160, 19, -20)]
    prof = [(-0.0045, -0.0002), (-0.0045, 0.0003), (-0.0026, 0.0003)] + arc + [(0.0026, 0.0003), (0.0045, 0.0003), (0.0045, -0.0002)]
    acc.rib(parent, "piping", fr, prof, 0, closed_profile=True, closed_path=closed, chunk=0.9)
    return fr


# ======================================================================== карман
def make_pocket(surf0):
    """Накладной карман на передней стенке: подушка с крутым ободом, поверхность — по передней стенке лучом."""
    bm = new_bm()
    x0, x1, z0, z1, rr = -0.236, 0.236, 0.052, 0.205, 0.026
    cxm, czm = 0.0, (z0 + z1) / 2
    hxw, hzw = (x1 - x0) / 2, (z1 - z0) / 2
    nu, nv = int((x1 - x0) / 0.006), int((z1 - z0) / 0.006)

    def plan(i, j):
        x = x0 + (x1 - x0) * i / nu
        z = z0 + (z1 - z0) * j / nv
        # скругление углов: тянем точки у углов на дугу
        ix = max(-hxw + rr, min(hxw - rr, x - cxm))
        iz = max(-hzw + rr, min(hzw - rr, z - czm))
        d = V((x - cxm - ix, 0, z - czm - iz))
        if d.length > rr:
            d = d.normalized() * rr
        return V((cxm + ix + d.x, 0.0, czm + iz + d.z))

    def dist_in(p):
        qx, qz = abs(p.x - cxm) - (hxw - rr), abs(p.z - czm) - (hzw - rr)
        outside = math.hypot(max(qx, 0), max(qz, 0)) + min(max(qx, qz), 0.0) - rr
        return -outside

    def lift(i, j):
        p = plan(i, j)
        d = max(0.0, dist_in(p))
        prof_ = 1.0 - math.exp(-d / 0.0065)
        dome = 0.0032 * prof((p.x - cxm) / hxw) * prof((p.z - czm) / hzw)
        w = 0.0008 * noise.noise(V((p.x * 14, p.z * 14, 4.4)))
        return 0.0009 + 0.0120 * prof_ + dome + w * prof_

    def uvf(p):
        return (p.x * 1000.0, p.z * 1000.0)
    grid_surface(bm, surf0, plan, nu, nv, "y-", lift, 0, uvf, outward=V((0, -1, 0)))
    return bm, {"pocket": 0}


# ======================================================================== молния
def zip_frames(surf, plan, mode, inward, step=0.0008, lift=0.0003):
    pts, nrm = conform(surf, plan, mode, lift=lift, it=1)
    lat = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        to = V(inward) - p
        to -= t * to.dot(t)
        to -= nrm[i] * to.dot(nrm[i])
        lat.append(to.normalized() if to.length > 1e-9 else V((1, 0, 0)))
    return frames_on(pts, nrm, lat)


def zip_halves(acc, par_in, par_out, fr, isl):
    """Тесьма и спираль двух половин молнии. par_in — родитель внутренней (b>0) половины, par_out — внешней."""
    alt = lambda i: 1.0 if i % 2 == 0 else 0.62
    for par, sgn in ((par_in, 1.0), (par_out, -1.0)):
        tape = [(sgn * 0.0022, 0.0), (sgn * 0.0105, 0.0), (sgn * 0.0105, 0.0008), (sgn * 0.0022, 0.0008)]
        coil = [(sgn * 0.0002, 0.0), (sgn * 0.0022, 0.0), (sgn * 0.0022, 0.0017), (sgn * 0.0002, 0.0017)]
        acc.rib(par, "ztape", fr, tape, 0, closed_profile=True, chunk=0.9)
        acc.rib(par, "zcoil", fr, coil, 0, closed_profile=True, chunk=0.9, hfun=alt)


def slider(acc, parent, fr, s_target, tab_dir, rnd, splay=0.0):
    """Бегунок ~12 x 9 x 5 мм с узким язычком 5 x 28 мм и коротким наконечником; язычок висит по направлению tab_dir."""
    acc_len = 0.0
    idx = 1
    for i in range(1, len(fr)):
        acc_len += (fr[i][0] - fr[i - 1][0]).length
        if acc_len >= s_target:
            idx = i
            break
    p, n, b = fr[idx]
    t = (fr[min(idx + 1, len(fr) - 1)][0] - fr[idx - 1][0]).normalized()
    bm = acc.bm(parent, "metal")
    place_box(bm, (0.0120, 0.0090, 0.0048), 0.0014, frame_matrix(p + n * 0.0030, t, b, n), 0)
    place_box(bm, (0.0075, 0.0060, 0.0024), 0.0008, frame_matrix(p + n * 0.0058, t, b, n), 0, seg=1)
    piv = p + n * 0.0050 - t * 0.0040
    d = (tab_dir - n * tab_dir.dot(n))
    d = d.normalized() if d.length > 0.2 else tab_dir.normalized()
    d = (d * math.cos(splay) + b * math.sin(splay)).normalized()
    ez = (n - d * n.dot(d)).normalized()
    ey = ez.cross(d)
    place_box(bm, (0.028, 0.0050, 0.0012), 0.0005, frame_matrix(piv + d * 0.0125 + ez * 0.0008, d, ey, ez), 0, seg=1)
    place_box(acc.bm(parent, "tip"), (0.011, 0.0058, 0.0032), 0.0014, frame_matrix(piv + d * 0.0335 + ez * 0.0010, d, ey, ez), 0)


# ======================================================================== стропы
def smooth01(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def strap_frames(path, phis, nrm0, ex, nloop):
    """Рамки стропы: ширина b поворачивается от ex (на стенке) к нормали петли (в дуге) — полузакрутка у основания."""
    m = len(path)
    fr = []
    pb = pn = None
    for i in range(m):
        t = (path[min(i + 1, m - 1)] - path[max(i - 1, 0)]).normalized()
        ph = phis[i]
        bref = ex * math.cos(ph) + nloop * math.sin(ph)
        b = bref - t * bref.dot(t)
        b = b.normalized() if b.length > 1e-6 else (pb if pb is not None else ex)
        if pb is not None and b.dot(pb) < 0:
            b = -b
        n = b.cross(t).normalized()
        if pn is None:
            if n.dot(nrm0) < 0:
                n = -n
        elif n.dot(pn) < 0:
            n = -n
        fr.append((path[i], n, b))
        pb, pn = b, n
    return fr


def strap_point(fr, z, u, off):
    i = min(range(len(fr)), key=lambda k: abs(fr[k][0].z - z))
    p, n, b = fr[i]
    return p + b * u + n * off, n


def stitch_rows(acc, parent, fr, w, th, z0, z1, rnd, thread="t_red", x_cross=True):
    """Прямоугольник с крестом на ленте стропы между высотами z0, z1 (по рамкам ноги)."""
    hw = w / 2 - 0.0042
    off = th / 2 + 0.0003
    lines = [((-hw, z0), (hw, z0)), ((-hw, z1), (hw, z1)), ((-hw, z0), (-hw, z1)), ((hw, z0), (hw, z1))]
    if x_cross:
        lines += [((-hw, z0), (hw, z1)), ((hw, z0), (-hw, z1))]
    for (ua, za), (ub, zb) in lines:
        L_ = math.hypot(ub - ua, zb - za)
        k = max(2, int(L_ / 0.0032))
        pts, nr = [], []
        for j in range(k + 1):
            a = j / k
            p, n = strap_point(fr, za + (zb - za) * a, ua + (ub - ua) * a, off)
            pts.append(p)
            nr.append(n)
        add_stitches(acc, parent, pts, nr, thread, 0.0032, False, 0.0, rnd)


def handle(acc, parent, surf, rnd, side, alpha, xl=0.058, w=0.038, th=0.0022, zbot=0.172, length=0.15):
    """Ручка из двух плоских строп 38 x 2,2 мм: ноги пришиты плашмя от zbot до верхнего ребра, выше — свободная петля ~180 мм,
    ложится мягкой дугой наружу (alpha — наклон от вертикали у ребра); концы сходятся и лежат друг на друге. Без закрутки."""
    mode = "y-" if side < 0 else "y+"
    zs = [zbot + i * 0.002 for i in range(int((0.287 - zbot) / 0.002) + 1)]
    o = V((0, side, 0))
    ex = V((1, 0, 0))
    out_frames = []
    for k, sx in enumerate((-1, 1)):
        pts, nrm = conform(surf, [V((sx * xl, 0, z)) for z in zs], mode, lift=th / 2 + 0.0012, it=10)
        P = pts[-1]
        n_steps = int(length / 0.002)
        dx = -sx * (xl - 0.012) / n_steps / 0.002
        free = []
        for i in range(1, n_steps + 1):
            s_ = i / n_steps
            ang = alpha + math.radians(42) * s_ * s_
            dv = V((dx, math.sin(ang) * side, math.cos(ang))).normalized()
            P = P + dv * 0.002
            free.append(P + o * (k * (th + 0.0004) * smooth01(s_ * 1.6)))
        path = smooth_pts(pts + free, 2)
        fr = strap_frames(path, [0.0] * len(path), nrm[0], ex, ex)
        acc.rib(parent, "webbing", fr, rect_profile(w, th, -th / 2), 0, closed_profile=True, chunk=1.2)
        lf = fr[:len(pts)]
        side_lines(acc, parent, lf, (-(w / 2 - 0.0042), w / 2 - 0.0042), "t_red", lift=th / 2 + 0.0003, rnd=rnd)
        stitch_rows(acc, parent, lf, w, th, zbot + 0.004, zbot + 0.034, rnd)
        stitch_rows(acc, parent, lf, w, th, 0.256, 0.284, rnd)
        out_frames.append(fr)
    return out_frames


def side_tab(acc, parent, surf, rnd, sx, w=0.038, th=0.0020):
    """Петля из стропы на торцевой стенке с треугольным кольцом для плечевого ремня."""
    mode = "x+" if sx > 0 else "x-"
    zs = [0.064 + i * 0.002 for i in range(int((0.200 - 0.064) / 0.002) + 1)]
    pts, nrm = conform(surf, [V((sx * HX, 0, z)) for z in zs], mode, lift=th / 2 + 0.0012, it=8)
    P0, N0 = pts[-1], nrm[-1]
    zdir = V((0, 0, 1))
    loop = []
    for i in range(1, 25):
        s_ = math.pi * i / 24
        loop.append(P0 + zdir * (0.040 * s_ / math.pi) + N0 * (0.017 * math.sin(s_)))
    path = smooth_pts(pts + loop, 2)
    fr = strap_frames(path, [0.0] * len(path), N0, V((0, 1, 0)), N0)
    acc.rib(parent, "webbing", fr, rect_profile(w, th, -th / 2), 0, closed_profile=True, chunk=1.2)
    lf = fr[:len(pts)]
    side_lines(acc, parent, lf, (-(w / 2 - 0.0042), w / 2 - 0.0042), "t_red", lift=th / 2 + 0.0003, rnd=rnd)
    stitch_rows(acc, parent, lf, w, th, 0.068, 0.104, rnd)
    stitch_rows(acc, parent, lf, w, th, 0.168, 0.198, rnd)
    # треугольное кольцо на нижней оси петли
    B0 = P0 + zdir * 0.020 + N0 * 0.0100
    A = B0 + V((0, 1, 0)) * 0.0225
    B = B0 - V((0, 1, 0)) * 0.0225
    C = B0 + N0 * 0.056 - zdir * 0.030
    ring = fillet_poly([A, B, C], 0.006, 0.0015, closed=True)
    pn = (B - A).cross(C - A).normalized()
    fr2 = frames_on(ring, [pn] * len(ring))
    acc.rib(parent, "metal", fr2, circle_profile(0.0022, 8), 0, closed_profile=True, closed_path=True, chunk=0.9)


def reflect_strip(acc, parent, surf, rnd):
    xs = [-0.228 + i * 0.002 for i in range(int(0.456 / 0.002) + 1)]
    pts, nrm = conform(surf, [V((x, 0, 0.083)) for x in xs], "y-", lift=0.0004, it=3)
    fr = frames_on(pts, nrm)
    acc.rib(parent, "reflect", fr, rect_profile(0.038, 0.0009), 0, closed_profile=True, chunk=0.9)
    side_lines(acc, parent, fr, (-0.0155, 0.0155), "t_white", lift=0.0009 + 0.0003, rnd=rnd)


def disc_patch(acc, parent, surf, rnd, c, R=0.040):
    """Круглая нашивка на кармане: диск на 1,3 мм с бортиком."""
    bm = acc.bm(parent, "patch")
    uvl = bm.loops.layers.uv.get("UVmm")
    isl = bm.faces.layers.int.get("isl")
    top, rim = acc.island(parent, "patch"), acc.island(parent, "patch")
    nr, ns = 8, 40
    rings = []

    def pt(rr, a, lift):
        x, z = c[0] + rr * math.cos(a), c[1] + rr * math.sin(a)
        r = surf.ray(V((x, -1.0, z)), V((0, 1, 0)))
        return r[0] + r[1] * lift, (x, z)
    for i in range(nr + 1):
        row = []
        for j in range(ns):
            a = TAU * j / ns
            p, xz = pt(R * i / nr, a, 0.0013)
            row.append((bm.verts.new(p), xz))
        rings.append(row)
    for i in range(nr):
        for j in range(ns):
            k = (j + 1) % ns
            q = [rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]]
            if i == 0:
                # у центра кольцо сходится в одну точку: все вершины нулевого кольца — одна позиция, склеиваем
                q = [rings[0][0], rings[1][k], rings[1][j]] if j > 0 and j < ns - 1 else None
                if q is None:
                    continue
            try:
                f = bm.faces.new([a[0] for a in q])
            except ValueError:
                continue
            f[isl] = top
            f.normal_update()
            if f.normal.y > 0:
                f.normal_flip()
            for lp, a in zip(f.loops, q):
                lp[uvl].uv = ((a[1][0] - c[0]) * 1000.0 + 40.0, (a[1][1] - c[1]) * 1000.0 + 40.0)
    low = []
    for j in range(ns):
        p, xz = pt(R, TAU * j / ns, 0.0001)
        low.append(bm.verts.new(p))
    for j in range(ns):
        k = (j + 1) % ns
        f = bm.faces.new((rings[nr][j][0], rings[nr][k][0], low[k], low[j]))
        f[isl] = rim
        f.normal_update()
        for lp, uu in zip(f.loops, ((j, 0), (j + 1, 0), (j + 1, 1.3), (j, 1.3))):
            lp[uvl].uv = (uu[0] * TAU * R * 1000.0 / ns, uu[1])
        c0 = f.calc_center_median()
        if (f.normal.x * (c0.x - c[0]) + f.normal.z * (c0.z - c[1])) < 0:
            f.normal_flip()
    ring = [V((c[0] + (R - 0.0015) * math.cos(TAU * j / (ns * 2)), 0, c[1] + (R - 0.0015) * math.sin(TAU * j / (ns * 2)))) for j in range(ns * 2)]
    pts, nrm = conform(surf, ring, "y-", lift=0.0013 + 0.0003, it=0, closed=True)
    add_stitches(acc, parent, pts, nrm, "t_white", 0.0028, True, 0.0, rnd)


def label_patch(acc, parent, surf, rnd, x0, x1, z0, z1):
    bm = acc.bm(parent, "label")
    nu, nv = int((x1 - x0) / 0.003), int((z1 - z0) / 0.003)
    grid_surface(bm, surf, lambda i, j: V((x0 + (x1 - x0) * i / nu, 0, z0 + (z1 - z0) * j / nv)), nu, nv, "y-", 0.0011,
                 acc.island(parent, "label"), lambda p: ((p.x - x0) * 1000.0, (p.z - z0) * 1000.0), 0, outward=V((0, -1, 0)))
    ring = rect_path(x0 + 0.0018, x1 - 0.0018, z0 + 0.0018, z1 - 0.0018, 0.002, 0.0)
    pts, nrm = conform(surf, ring, "y-", lift=0.0011 + 0.0003, it=0, closed=True)
    add_stitches(acc, parent, pts, nrm, "t_gray", 0.0028, True, 0.0, rnd)
    pts2, nrm2 = conform(surf, rect_path(x0, x1, z0, z1, 0.0008, 0.0), "y-", lift=0.0, it=0, closed=True)
    fr = frames_on(pts2, nrm2)
    acc.rib(parent, "label", fr, [(-0.0003, -0.0001), (0.0003, -0.0001), (0.0003, 0.0011), (-0.0003, 0.0011)], 0, closed_profile=True,
            closed_path=True, chunk=0.9)


def window_pocket(acc, parent, surf, rnd, x0, x1, y0, y1):
    """Прозрачный кармашек для бирки на клапане: чёрная рамка, белая карточка, плёнка."""
    ring = rect_path(x0 + 0.0035, x1 - 0.0035, y0 + 0.0035, y1 - 0.0035, 0.004, 0.0)
    ring = [V((p.x, p.z, 0)) for p in ring]
    pts, nrm = conform(surf, ring, "z+", lift=0.0, it=0, closed=True)
    fr = frames_on(pts, nrm)
    acc.rib(parent, "frame", fr, rect_profile(0.007, 0.0012), 0, closed_profile=True, closed_path=True, chunk=0.9)
    side_lines(acc, parent, fr, (-0.0044, 0.0044), "t_red", lift=0.0012 + 0.0003, rnd=rnd, closed=True, pitch=0.003)
    xa, xb, ya, yb = x0 + 0.007, x1 - 0.007, y0 + 0.007, y1 - 0.007
    nu, nv = int((xb - xa) / 0.004), int((yb - ya) / 0.004)
    bm = acc.bm(parent, "pvc")
    plan = lambda i, j: V((xa + (xb - xa) * i / nu, ya + (yb - ya) * j / nv, 0))
    grid_surface(bm, surf, plan, nu, nv, "z+", 0.0007, acc.island(parent, "pvc"), lambda p: ((p.x - xa) * 1000.0, (p.y - ya) * 1000.0), 1,
                 outward=V((0, 0, 1)))
    grid_surface(bm, surf, plan, nu, nv, "z+", 0.0020, acc.island(parent, "pvc"), lambda p: ((p.x - xa) * 1000.0, (p.y - ya) * 1000.0), 0,
                 outward=V((0, 0, 1)))


# ======================================================================== сборка состояния
def pocket_zip_plan():
    return fillet_poly([V((-0.226, 0, 0.112)), V((-0.226, 0, 0.185)), V((0.226, 0, 0.185)), V((0.226, 0, 0.112))], 0.022, 0.0008)


def main_zip_plan():
    return fillet_poly([V((-ZIPX, ZIPY1, H)), V((-ZIPX, ZIPY0, H)), V((ZIPX, ZIPY0, H)), V((ZIPX, ZIPY1, H))], 0.012, 0.0008)


def flap_bend(bm):
    """Раскрытый клапан слегка провисает: смещение по нормали пропорционально квадрату расстояния от шарнира + лёгкая волна."""
    for v in bm.verts:
        sd = max(0.0, HINGE.y - v.co.y)
        v.co.z += BEND_K * sd * sd + 0.0016 * math.sin(v.co.x * 22.0) * (sd / 0.2)


def init_shell():
    if "groups" in SIM:
        return
    bm, info = build_shell()
    groups = split_shell(bm, info)
    bm.free()
    surf0 = Surf([g[0] for g in groups.values()])
    pocket = make_pocket(surf0)
    SIM["groups"] = groups
    SIM["pocket"] = pocket
    SIM["surf"] = Surf([g[0] for g in groups.values()] + [pocket[0]])


def build_state(top, M, at, open_, label):
    init_shell()
    _ISL[0] = 1000
    surf = SIM["surf"]
    rnd = rng(7)
    coll = L.collection(label, top)
    root = L.root("МС_сумка_укладка" + ("_раскрыта" if open_ else ""), coll, at)

    def shell(g, name, mlist, parent, origin=(0, 0, 0), bend=False):
        bm, names = SIM["groups"][g]
        bm = bm.copy()
        if bend:
            flap_bend(bm)
        ob = to_obj(bm, name, coll, mlist, parent, origin=origin, solid=(TH, 1), names=names, recalc=False)
        ob["lc_set"] = "A"
        return ob
    body = shell("body", "МС_корпус", [M["fabric"], M["fabric_in"]], root)
    band = shell("band", "МС_лента_низа", [M["band"], M["band"]], root)
    flap = shell("flap", "МС_клапан", [M["fabric"], M["fabric_in"]], root, origin=HINGE, bend=open_)
    pbm, pnames = SIM["pocket"]
    pocket = to_obj(pbm.copy(), "МС_карман", coll, [M["fabric"], M["fabric_in"]], root, solid=(TH, 1), names=pnames, recalc=False)
    pocket["lc_set"] = "A"
    flap["mover"] = 1
    acc = Acc()
    R, F = "root", "flap"

    # ---- кант
    k = 0.2929 * RC
    for sx in (-1, 1):
        for sy in (-1, 1):
            plan = [V((sx * (HX - k), sy * (HY - k), z)) for z in [ZB + 0.004 + i * 0.002 for i in range(int((H - k - ZB - 0.004) / 0.002) + 1)]]
            pts, nrm = conform(surf, plan, "near", it=2)
            fr = piping_ribbon(acc, R, pts, nrm, False)
            side_lines(acc, R, fr, (-0.0060, 0.0060), "t_red", rnd=rnd)
    for name, a, b, z, rr, thr in (("top", HX - k, HY - k, H - k, 0.7071 * RC, "t_red"), ("band", HX, HY, ZB, RC, "t_black")):
        pl = fillet_poly([V((-a, -b, z)), V((a, -b, z)), V((a, b, z)), V((-a, b, z))], rr, 0.002, closed=True)
        pts, nrm = conform(surf, pl, "near", it=2, closed=True)
        fr = piping_ribbon(acc, R, pts, nrm, True)
        side_lines(acc, R, fr, (-0.0060, 0.0060), thr, rnd=rnd, closed=True)
    # кант по ободу кармана
    pl = rect_path(-0.236, 0.236, 0.052, 0.205, 0.026, 0.0, 0.002)
    pts, nrm = conform(surf, pl, "y-", lift=0.0, it=2, closed=True)
    fr = piping_ribbon(acc, R, pts, nrm, True)
    side_lines(acc, R, fr, (-0.0060, 0.0060), "t_red", rnd=rnd, closed=True)

    # ---- молния клапана
    mp = main_zip_plan()
    fr_m = zip_frames(surf, mp, "z+", V((0, (ZIPY0 + ZIPY1) / 2, H)))
    zip_halves(acc, F, R, fr_m, 0)
    side_lines(acc, F, fr_m, (0.0098, 0.0036), "t_black", lift=0.0011, rnd=rnd)
    side_lines(acc, R, fr_m, (-0.0098, -0.0036), "t_black", lift=0.0011, rnd=rnd)
    side_lines(acc, F, fr_m, (0.0142,), "t_red", lift=0.0004, rnd=rnd)
    side_lines(acc, R, fr_m, (-0.0142,), "t_red", lift=0.0004, rnd=rnd)
    total = sum((fr_m[i][0] - fr_m[i - 1][0]).length for i in range(1, len(fr_m)))
    if not open_:
        s1, s2 = 0.217 + 0.084, 0.217 + 0.099
        td = V((0, -0.45, -0.9))
        slider(acc, R, fr_m, s1, td, rnd, -0.05)
        slider(acc, R, fr_m, s2, td, rnd, 0.05)
    else:
        slider(acc, R, fr_m, 0.020, V((-0.8, 0, -0.5)), rnd, 0.0)
        slider(acc, R, fr_m, total - 0.020, V((0.8, 0, -0.5)), rnd, 0.0)

    # ---- молния кармана
    pz = pocket_zip_plan()
    fr_p = zip_frames(surf, pz, "y-", V((0, 0, 0.128)))
    zip_halves(acc, R, R, fr_p, 0)
    side_lines(acc, R, fr_p, (0.0098, 0.0036, -0.0098, -0.0036), "t_black", lift=0.0011, rnd=rnd)
    side_lines(acc, R, fr_p, (0.0142, -0.0142), "t_red", lift=0.0004, rnd=rnd)
    slider(acc, R, fr_p, 0.060, V((0, 0, -1)), rnd, -0.04)
    slider(acc, R, fr_p, 0.074, V((0, 0, -1)), rnd, 0.04)

    # ---- стропы, ленты, нашивки
    handle(acc, R, surf, rnd, -1, math.radians(72 if open_ else 7))
    handle(acc, R, surf, rnd, +1, math.radians(72 if open_ else 7))
    for sx in (-1, 1):
        side_tab(acc, R, surf, rnd, sx)
    reflect_strip(acc, R, surf, rnd)
    disc_patch(acc, R, surf, rnd, (-0.150, 0.128))
    label_patch(acc, R, surf, rnd, 0.112, 0.178, 0.140, 0.162)
    window_pocket(acc, F, surf, rnd, 0.098, 0.203, 0.000, 0.072)

    # ---- внутри клапана: сетчатые карманы и резинки
    panels = ((-0.215, -0.015, -0.100, -0.012), (0.015, 0.215, -0.100, -0.012), (-0.215, -0.015, 0.012, 0.094), (0.015, 0.215, 0.012, 0.094))
    bm = acc.bm(F, "mesh")
    for (xa, xb, ya, yb) in panels:
        nu, nv = 16, 7
        grid_surface(bm, surf, lambda i, j, xa=xa, xb=xb, ya=ya, yb=yb: V((xa + (xb - xa) * i / nu, ya + (yb - ya) * j / nv, 0)), nu, nv, "z+",
                     -(TH + 0.0040), acc.island(F, "mesh"), lambda p, xa=xa, ya=ya: ((p.x - xa) * 1000.0, (p.y - ya) * 1000.0), 0,
                     outward=V((0, 0, -1)))
    for x in (-0.115, 0.115):
        pts, nrm = conform(surf, [V((x, y, 0)) for y in [-0.103 + i * 0.002 for i in range(100)]], "z+", lift=-(TH + 0.0075), it=3)
        fr = frames_on(pts, nrm)
        acc.rib(F, "elastic", fr, rect_profile(0.012, 0.0014, -0.0007), 0, closed_profile=True, chunk=0.9)
        for yy in (pts[0].y + 0.004, pts[-1].y - 0.004):
            pp = [V((x - 0.005 + 0.0032 * i, yy, 0)) for i in range(4)]
            pt2, n2 = conform(surf, pp, "z+", lift=-(TH + 0.0075) - 0.0009, it=0)
            add_stitches(acc, F, pt2, [-n for n in n2], "t_black", 0.0032, False, 0.0, rnd)

    # ---- внутри корпуса: перегородки на липучке и резиновые держатели у задней стенки
    hs = 0.1415
    ax3 = (V((1, 0, 0)), V((0, 1, 0)), V((0, 0, 1)))
    for x in (-0.092, 0.092):
        place_box(acc.bm(R, "divider"), (0.010, 2 * hs, 0.225), 0.004, frame_matrix(V((x, 0, 0.1245)), *ax3), 0)
        for yy in (-hs, hs):
            place_box(acc.bm(R, "hook"), (0.011, 0.0032, 0.120), 0.0008, frame_matrix(V((x, yy, 0.125)), *ax3), 0, seg=1)
    for xc in (-0.19, -0.065, 0.065, 0.19):
        for zc in (0.100, 0.190):
            r_ = surf.ray(V((xc, 1.0, zc)), V((0, -1, 0)))
            if r_ is None:
                continue
            P, N = r_[0] - r_[1] * (TH + 0.0010), r_[1]
            pts = [P + V((1, 0, 0)) * (-0.015 + 0.030 * u / 14) - N * (0.0065 * math.sin(math.pi * u / 14)) for u in range(15)]
            fr = frames_on(pts, [-N] * 15)
            acc.rib(R, "elastic", fr, rect_profile(0.008, 0.0013, -0.0006), 0, closed_profile=True, chunk=0.9)

    # ---- вывод накопленных деталей
    for (par, kind), bm in acc.d.items():
        mlist = [M[n] for n in Acc.KINDS[kind]]
        if kind == "stitch":
            finalize_fixed_uv(bm, {i: t for i, t in enumerate(THREADS)})
        pobj = flap if par == F else root
        name = "МС_" + Acc.TITLE[kind] + ("_клапан" if par == F else "")
        keep = kind in ("label", "pvc", "patch", "mesh")
        org = tuple(HINGE) if par == F else (0, 0, 0)
        if par == F and open_:
            flap_bend(bm)
        ob = to_obj(bm, name, coll, mlist, pobj, origin=org, parent_origin=org, smooth=kind != "stitch", recalc=not keep)
        ob["lc_set"] = "B"
        ob["kind"] = kind
    if open_:
        flap.rotation_euler = (math.radians(-110), 0, 0)
    return root


def check(roots):
    dg = bpy.context.evaluated_depsgraph_get()
    for root in roots:
        pts, tri = [], 0
        for ob in root.children_recursive:
            if ob.type != "MESH":
                continue
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            tri += sum(len(p.vertices) - 2 for p in me.polygons)
            pts += [ev.matrix_world @ v.co for v in me.vertices]
            ev.to_mesh_clear()
        mn = V((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = V((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        sz = mx - mn
        print(f"SIZE {root.name}: {sz.x*1000:.0f} x {sz.z*1000:.0f}(в) x {sz.y*1000:.0f}(г) мм; tri {tri}")
        for ob in sorted(root.children_recursive, key=lambda o: o.name):
            if ob.type == "MESH":
                me = ob.evaluated_get(dg).to_mesh()
                print("   ", ob.name, len(me.polygons), "граней")
                ob.evaluated_get(dg).to_mesh_clear()


# ======================================================================== просмотр формы
def setup_render(neutral=True):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 1400, 1000
    sc.view_settings.view_transform = "AgX"
    w = bpy.data.worlds.get("Студия_МС") or bpy.data.worlds.new("Студия_МС")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.78, 0.78, 0.8, 1)
    bg.inputs[1].default_value = 0.35
    sc.world = w
    for ob in list(bpy.data.objects):
        if ob.type in ("LIGHT", "CAMERA"):
            bpy.data.objects.remove(ob)
    ld = bpy.data.lights.new("ключ", "AREA")
    ld.energy = 260
    ld.size = 1.2
    lo = bpy.data.objects.new("ключ", ld)
    lo.location = (-1.6, -1.8, 2.2)
    lo.rotation_euler = (math.radians(45), 0, math.radians(-40))
    bpy.context.scene.collection.objects.link(lo)
    ld2 = bpy.data.lights.new("заполняющий", "AREA")
    ld2.energy = 40
    ld2.size = 3.0
    lo2 = bpy.data.objects.new("заполняющий", ld2)
    lo2.location = (1.8, -1.2, 1.0)
    lo2.rotation_euler = (math.radians(75), 0, math.radians(50))
    bpy.context.scene.collection.objects.link(lo2)
    cd = bpy.data.cameras.new("кам")
    co = bpy.data.objects.new("кам", cd)
    bpy.context.scene.collection.objects.link(co)
    sc.camera = co
    if neutral:
        gm = bpy.data.materials.get("нейтральный") or bpy.data.materials.new("нейтральный")
        gm.use_nodes = True
        for n in gm.node_tree.nodes:
            if n.type == "BSDF_PRINCIPLED":
                n.inputs["Base Color"].default_value = (0.5, 0.5, 0.48, 1)
                n.inputs["Roughness"].default_value = 0.65
        bpy.context.view_layer.material_override = gm


FORM_VIEWS = [
    # имя, состояние, цель (в корне), дистанция, азимут, подъём, фокус
    ("34_closed", False, (0.0, 0.0, 0.16), 1.25, -22, 17, 45),
    ("open", True, (0.0, 0.0, 0.2), 1.45, -28, 32, 40),
    ("zip", False, (-0.12, -0.112, 0.30), 0.30, -18, 38, 50),
    ("strap", False, (0.0, -0.145, 0.10), 0.42, -22, 8, 50),
    ("piping", False, (-0.258, -0.133, 0.27), 0.30, -35, 20, 50),
]


def render_views(roots, folder, tag="form", views=FORM_VIEWS, only=None):
    os.makedirs(folder, exist_ok=True)
    sc = bpy.context.scene
    cam = sc.camera
    for name, open_, tgt, dist, az, el, lens in views:
        if only and name not in only:
            continue
        root = roots[1 if open_ else 0]
        for r in roots:
            for o in [r] + list(r.children_recursive):
                o.hide_render = r is not root
        c = V(root.location) + V(tgt)
        a, e = math.radians(az), math.radians(el)
        cam.location = c + V((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        cam.data.clip_start = 0.01
        sc.render.filepath = os.path.join(folder, f"{tag}_{name}.png")
        bpy.ops.render.render(write_still=True)
        print("render", name, flush=True)
    for r in roots:
        for o in [r] + list(r.children_recursive):
            o.hide_render = False


def build(out):
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    M = mats()
    top = L.collection("МедСумка_v02")
    r0 = build_state(top, M, (0, 0, 0), False, "Сумка закрыта")
    r1 = build_state(top, M, (0.95, 0, 0), True, "Сумка раскрыта")
    return [r0, r1]


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    roots = build(argv[1] if len(argv) > 1 else None)
    if "check" in argv:
        check(roots)
    if "preview" in argv:
        i = argv.index("preview")
        setup_render(True)
        only = set(argv[i + 2].split(",")) if len(argv) > i + 2 else None
        render_views(roots, argv[i + 1], "form", FORM_VIEWS, only)
    if argv and argv[0] == "build" and len(argv) > 1:
        bpy.context.view_layer.material_override = None
        os.makedirs(os.path.dirname(argv[1]), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=argv[1], compress=True)
        print("saved", argv[1])
