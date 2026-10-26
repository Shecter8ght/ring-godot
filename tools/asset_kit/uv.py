"""Игровая развёртка оружия и обвесов от первого лица — общий модуль для Blender 5.2.

Нормы — навык godot-asset-preparation (tools/asset_skills/godot-asset-preparation/references/mesh-bake.md): плотность по
видимости (у глаза × 1,3–1,5, вдали × 0,8, скрытое × 0,1, просторное скрытое × 0,5), заполнение атласа от 80 %, острова
по осям UV, половинный отступ внутри группы одной детали, внахлёст одинаковое мелкое и скрытое, привязка к пикселю.
Прежде эта логика жила копиями в tools/veras54_v13/game_lp.py, tools/veras54_mags/mags_game_lp.py,
tools/mosin_pu/game_lp.py (eye_texels) и tools/pm_worn/common.py; встраивать модуль в скрипты стволов — по слову владельца.

Из скрипта Blender:
    sys.path.insert(0, str(ROOT / 'tools'))
    from asset_kit import uv as kit_uv
    kit_uv.smart_unwrap(objs)                                    # новая сетка: острова по изломам (как game_lp)
    cls = kit_uv.visibility(objs, poses, node_of)                # классы граней лучами (готовая сетка — classes_from_uv)
    eyes = [kit_uv.Eye((-0.33, 0.09, 0.12)), kit_uv.Eye((-0.22, 0, 0.057), k_max=kit_uv.ADS_K)]   # дуло по +X
    rep = kit_uv.layout(objs, 4096, classes=cls, eyes=eyes)     # плотность, группы, внахлёст, укладка, запись UV
    kit_uv.harden_on_seams(objs)
Проверка на копиях готовых сеток — tools/asset_kit/uv_check.py.

Что делает layout:
1. Острова — связь по общей кромке с теми же UV (и тем же классом видимости). Остров приводится к метрам (площадь
   в UV = площади в 3D), получает множитель стороны k (класс видимости, глаз) и поворачивается к наименьшему
   описанному прямоугольнику — кромки по осям UV.
2. Группы «разрыва»: острова одной детали, разрезанные по жёстким рёбрам (шов на остром ребре), стоят друг от друга
   не ближе group_margin (6 px), от остальных — не ближе margin (12 px). Острова кладутся по одному: блоки группы
   и сшивка вдоль общего ребра (stitch) на сетках из Smart UV после упрощения ложились хуже (проверка 2026-10-26).
3. Внахлёст: одинаковые мелкие острова (габарит до stack_max) ложатся на одно место без переворота; одинаковые
   и зеркальные скрытые — с переворотом. Одинаковость — по вершинам с точностью до движения или отражения при том же
   разбиении на треугольники. Копии помечены атрибутом граней uv_stack (1 — копия, 2 — перевёрнутая): на время
   запекания их уводят за квадрат (shift_stack_copies). Группа укладки — атрибут uv_group (номер + 1).
4. Растровая укладка (uv_pack): остров — маски пикселей при данном масштабе (пиксель, которого остров касается),
   расширенные на половину отступа между деталями и внутри группы. «Тетрис»: нижний профиль маски опускается на
   линию горизонта в четырёх поворотах (вогнутые края принимают соседей), место — ниже и левее; мелкие и средние
   острова — сначала в пустоты под горизонтом. Масштаб — наибольший, при котором всё легло (половинным делением).
   Положения — целые пиксели: края острова — по границам пикселей (привязка к пикселю).
5. Отчёт: заполнение, плотность видимого / у глаза / вдали, острова, группы, внахлёст, куда ушла площадь атласа
   (отступы, округление до пикселей, пустое).
"""
from __future__ import annotations

import math
import time

import bmesh
import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

from . import uv_pack

SHARP = math.radians(60)             # изломы Smart UV и острые рёбра игровой сетки (как game_lp)
HARD_ON_SEAM = math.radians(30)      # шов с изломом больше — жёсткое ребро, т. е. «разрыв»
MARGIN_PX = 12                       # отступ между деталями на 4K (норма проекта)
GROUP_MARGIN_PX = 6                  # внутри группы одной детали — половинный; меньше 6 края наезжают при запекании
HIDDEN_K, ROOMY_K = 0.1, 0.5         # сторона острова: скрытое, просторное скрытое
EYE_K, FAR_K, ADS_K = 1.4, 0.8, 2.0  # у глаза от бедра, вдали, прицельное у глаза при прицеливании
STACK_MAX_M = 0.025                  # «мелкое» для внахлёста: габарит острова до 25 мм (заклёпки, винты, оси)
FILL_MIN = 0.80                      # норма заполнения
SMALL_PX = 24                        # «мелкий» остров в отчёте: большая сторона меньше 24 px
CONTACT_M, ROOMY_M = 0.004, 0.008    # лучи видимости: прижатая грань, просторная скрытая (как game_lp)
VISIBLE, ROOMY, HIDDEN, CONTACT = 0, 1, 2, 3
CLASS_K = {VISIBLE: 1.0, ROOMY: ROOMY_K, HIDDEN: HIDDEN_K, CONTACT: HIDDEN_K}


class Eye:
    """Точка глаза камеры от первого лица в осях модели (м); k_max — предел прибавки у этого глаза. forward — куда
    смотрит камера (по оси ствола к дулу), fov_v / fov_h — поле зрения, градусы (Balance.FPS_VIEWMODEL_FOV = 54
    по вертикали; 16 : 9 — около 87 по горизонтали): что вне кадра (приклад под щекой в прицеле), то не прибавляется."""

    def __init__(self, pos, k_max: float = EYE_K, name: str = '', forward=(1.0, 0.0, 0.0), fov_v: float = 54.0,
                 fov_h: float = 87.0):
        self.pos = np.asarray(pos, np.float64)
        self.k_max = float(k_max)
        self.name = name or f'{tuple(round(float(c), 3) for c in self.pos)}'
        f = np.asarray(forward, np.float64)
        self.fwd = f / np.linalg.norm(f)
        up = np.array([0.0, 0.0, 1.0]) - self.fwd[2] * self.fwd
        self.up = up / np.linalg.norm(up)
        self.side = np.cross(self.fwd, self.up)
        self.tan_v, self.tan_h = math.tan(math.radians(fov_v / 2)), math.tan(math.radians(fov_h / 2))

    def in_view(self, pts: np.ndarray) -> np.ndarray:
        """Точки в кадре камеры этого глаза."""
        d = pts - self.pos
        f = d @ self.fwd
        return (f > 1e-3) & (np.abs(d @ self.up) <= f * self.tan_v) & (np.abs(d @ self.side) <= f * self.tan_h)


# ---------------------------------------------------------------------------------------------- сетка массивами
class _Mesh:
    """Сетка объекта массивами numpy в мировых координатах и её развёртка uv_name (копия; запись — write_uv)."""

    def __init__(self, o, uv_name: str):
        me = o.data
        self.obj, self.uv_name = o, uv_name
        nv, nl, npoly, ne = len(me.vertices), len(me.loops), len(me.polygons), len(me.edges)
        self.npoly = npoly
        co = np.empty(nv * 3, np.float32)
        me.vertices.foreach_get('co', co)
        mw = np.array(o.matrix_world, np.float64)
        self.co = co.reshape(-1, 3).astype(np.float64) @ mw[:3, :3].T + mw[:3, 3]
        self.lv = np.empty(nl, np.int32)
        me.loops.foreach_get('vertex_index', self.lv)
        self.le = np.empty(nl, np.int32)
        me.loops.foreach_get('edge_index', self.le)
        self.ls = np.empty(npoly, np.int32)
        me.polygons.foreach_get('loop_start', self.ls)
        self.lt = np.empty(npoly, np.int32)
        me.polygons.foreach_get('loop_total', self.lt)
        ev = np.empty(ne * 2, np.int32)
        me.edges.foreach_get('vertices', ev)
        self.ev = ev.reshape(-1, 2)
        sharp = np.zeros(ne, bool)
        if 'sharp_edge' in me.attributes and ne:
            me.attributes['sharp_edge'].data.foreach_get('value', sharp)
        self.sharp = sharp
        self.stack = np.zeros(npoly, np.int32)
        if 'uv_stack' in me.attributes and npoly:
            me.attributes['uv_stack'].data.foreach_get('value', self.stack)
        uv = np.empty(nl * 2, np.float32)
        me.uv_layers[uv_name].uv.foreach_get('vector', uv)
        self.uv = uv.reshape(-1, 2).astype(np.float64)
        self.poly_of_loop = np.repeat(np.arange(npoly, dtype=np.int32), self.lt)
        k = np.arange(nl) - self.ls[self.poly_of_loop]
        self.next_loop = self.ls[self.poly_of_loop] + (k + 1) % self.lt[self.poly_of_loop]
        # треугольники веером по многоугольникам (игровые сетки и так из треугольников)
        nt = self.lt - 2
        self.tri_poly = np.repeat(np.arange(npoly, dtype=np.int32), nt)
        j = np.arange(int(nt.sum())) - np.repeat(np.cumsum(nt) - nt, nt)
        base = self.ls[self.tri_poly]
        self.tri = np.stack([base, base + j + 1, base + j + 2], 1)
        self.tri_start = np.concatenate([[0], np.cumsum(nt)]).astype(np.int64)
        p = self.co[self.lv[self.tri]]
        cr = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
        self.tri_a3 = 0.5 * np.linalg.norm(cr, axis=1)
        self.tri_c3 = p.mean(1)
        self.poly_a3 = np.bincount(self.tri_poly, self.tri_a3, npoly)
        nrm = np.stack([np.bincount(self.tri_poly, cr[:, i], npoly) for i in range(3)], 1)
        self.poly_n = nrm / np.maximum(np.linalg.norm(nrm, axis=1), 1e-30)[:, None]
        self.poly_c = np.stack([np.bincount(self.poly_of_loop, self.co[self.lv, i], npoly) for i in range(3)], 1) \
            / np.maximum(self.lt, 1)[:, None]
        self.tri_a2s = self.tri_a2()

    def tri_a2(self, uv: np.ndarray | None = None) -> np.ndarray:
        """Площадь треугольников в UV со знаком (обход как у грани)."""
        q = (self.uv if uv is None else uv)[self.tri]
        return 0.5 * ((q[:, 1, 0] - q[:, 0, 0]) * (q[:, 2, 1] - q[:, 0, 1])
                      - (q[:, 2, 0] - q[:, 0, 0]) * (q[:, 1, 1] - q[:, 0, 1]))

    def write_uv(self, uv: np.ndarray) -> None:
        me = self.obj.data
        me.uv_layers[self.uv_name].uv.foreach_set('vector', uv.astype(np.float32).ravel())
        me.update()


def _ranges(starts: np.ndarray, lens: np.ndarray) -> np.ndarray:
    """Склеенные диапазоны [start, start + len)."""
    lens = np.asarray(lens, np.int64)
    if not len(lens):
        return np.zeros(0, np.int64)
    return np.arange(int(lens.sum())) - np.repeat(np.cumsum(lens) - lens, lens) + np.repeat(np.asarray(starts, np.int64), lens)


def _union_find(n: int, a, b) -> np.ndarray:
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for x, y in zip(a, b):
        rx, ry = find(int(x)), find(int(y))
        if rx != ry:
            parent[rx] = ry
    return np.array([find(i) for i in range(n)], np.int64)


def _components(roots: np.ndarray) -> list:
    order = np.argsort(roots, kind='stable')
    cuts = np.flatnonzero(np.diff(roots[order])) + 1
    return np.split(order, cuts)


def _poly_islands(m: _Mesh, split: np.ndarray | None = None) -> list:
    """Острова развёртки как массивы граней: связь — общая кромка с теми же UV у обеих вершин (и тот же класс)."""
    va, vb = m.lv, m.lv[m.next_loop]
    q = np.round(m.uv * 4194304.0).astype(np.int64)
    qa, qb = q, q[m.next_loop]
    sw = va > vb
    key = np.empty((len(va), 6), np.int64)
    key[:, 0] = np.where(sw, vb, va)
    key[:, 1] = np.where(sw, va, vb)
    key[:, 2:4] = np.where(sw[:, None], qb, qa)
    key[:, 4:6] = np.where(sw[:, None], qa, qb)
    order = np.lexsort(key.T[::-1])
    ks = key[order]
    same = np.all(ks[1:] == ks[:-1], axis=1)
    a = m.poly_of_loop[order[:-1][same]]
    b = m.poly_of_loop[order[1:][same]]
    if split is not None:
        keep = split[a] == split[b]
        a, b = a[keep], b[keep]
    return _components(_union_find(m.npoly, a, b))


# ---------------------------------------------------------------------------------------------- острова
class Island:
    """Остров развёртки: грани одной сетки, его плотность и положение в атласе."""

    def __init__(self, mi: int, m: _Mesh, polys: np.ndarray):
        self.mi, self.polys = mi, np.sort(polys)
        self.loops = np.sort(_ranges(m.ls[self.polys], m.lt[self.polys]))
        self.tris = _ranges(m.tri_start[self.polys], m.tri_start[self.polys + 1] - m.tri_start[self.polys])
        self.tri_local = np.searchsorted(self.loops, m.tri[self.tris])
        self.verts = np.unique(m.lv[self.loops])
        a2s = m.tri_a2s[self.tris]
        self.a3 = float(m.tri_a3[self.tris].sum())
        self.a2 = float(np.abs(a2s).sum())
        self.sign = 1.0 if a2s.sum() >= 0 else -1.0
        w = m.tri_a3[self.tris]
        self.center = (m.tri_c3[self.tris] * w[:, None]).sum(0) / max(w.sum(), 1e-30)
        p = m.co[self.verts]
        self.size3 = float(np.linalg.norm(p.max(0) - p.min(0)))
        self.cls = VISIBLE
        self.k = 1.0
        self.group = -1
        self.owner: Island | None = None   # копия внахлёст → остров, чьё место она занимает
        self.flip = False
        self.loop_map: np.ndarray | None = None
        self.uvm: np.ndarray | None = None  # координаты петель в метрах, повернуты к наименьшему прямоугольнику, min = 0
        self.ext = (0.0, 0.0)

    def to_metres(self, m: _Mesh) -> None:
        """Остров в метрах (площадь UV = площади 3D) и поворот к наименьшему описанному прямоугольнику."""
        uv = m.uv[self.loops]
        if self.a2 > 1e-14 and self.a3 > 1e-14 and math.isfinite(self.a2):
            pts = (uv - uv.mean(0)) * math.sqrt(self.a3 / self.a2)
        else:
            # вырожденная развёртка — проекция на плоскость средней нормали
            n = (m.poly_n[self.polys] * m.poly_a3[self.polys][:, None]).sum(0)
            ln = np.linalg.norm(n)
            n = n / ln if ln > 1e-30 else np.array([0.0, 0.0, 1.0])
            e1 = np.cross(n, [1.0, 0.0, 0.0] if abs(n[0]) < 0.9 else [0.0, 1.0, 0.0])
            e1 /= np.linalg.norm(e1)
            e2 = np.cross(n, e1)
            p = m.co[m.lv[self.loops]] - self.center
            pts = np.stack([p @ e1, p @ e2], 1)
        ang = _min_rect_angle(pts)
        c, s = math.cos(ang), math.sin(ang)
        pts = pts @ np.array([[c, s], [-s, c]])        # поворот на ang против часовой
        pts -= pts.min(0)
        self.uvm = pts
        self.ext = (float(pts[:, 0].max()), float(pts[:, 1].max()))


def _hull(pts: np.ndarray) -> np.ndarray:
    p = np.unique(np.round(pts, 9), axis=0)
    if len(p) < 3:
        return p
    p = p[np.lexsort((p[:, 1], p[:, 0]))]

    def half(seq):
        h = []
        for q in seq:
            while len(h) >= 2 and ((h[-1][0] - h[-2][0]) * (q[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (q[0] - h[-2][0])) <= 0:
                h.pop()
            h.append(q)
        return h
    lo, hi = half(p.tolist()), half(p[::-1].tolist())
    return np.array(lo[:-1] + hi[:-1])


def _min_rect_angle(pts: np.ndarray) -> float:
    """Поворот против часовой (рад), после которого описанный прямоугольник наименьший: одна из сторон оболочки
    ложится вдоль оси. При равенстве — без поворота."""
    h = _hull(pts)
    if len(h) < 2:
        return 0.0
    e = np.roll(h, -1, 0) - h
    ang = np.unique(np.round((-np.arctan2(e[:, 1], e[:, 0])) % (math.pi / 2), 9))
    ang = np.concatenate([[0.0], ang])
    c, s = np.cos(ang)[:, None], np.sin(ang)[:, None]
    x = h[:, 0][None] * c - h[:, 1][None] * s
    y = h[:, 0][None] * s + h[:, 1][None] * c
    area = (x.max(1) - x.min(1)) * (y.max(1) - y.min(1))
    i = int(np.flatnonzero(area <= area.min() * (1 + 1e-6))[0])
    return float(ang[i])


def islands_of(meshes: list, split: list | None = None) -> list:
    out = []
    for mi, m in enumerate(meshes):
        for polys in _poly_islands(m, None if split is None else split[mi]):
            out.append(Island(mi, m, polys))
    return out


# ---------------------------------------------------------------------------------------------- видимость и плотность
def classes_from_uv(objs, uv: str = 'GameUV', prior=None, hidden_below: float = 0.3, roomy_below: float = 0.75) -> list:
    """Классы граней готовой сетки по её развёртке: старые скрипты ужимали скрытое × 0,1 и просторное скрытое × 0,5,
    так что класс читается по плотности острова против медианной. prior(центр острова) → множитель, который скрипт
    добавил сам (у Мосина — прибавка у глаза), делится перед сравнением."""
    meshes = [_Mesh(o, uv) for o in objs]
    isl = islands_of(meshes)
    d = np.array([math.sqrt(i.a2 / i.a3) / (prior(i.center) if prior else 1.0) if i.a3 > 1e-14 else 0.0 for i in isl])
    a = np.array([i.a3 for i in isl])
    o = np.argsort(d)
    med = d[o][np.searchsorted(np.cumsum(a[o]), a.sum() / 2)]
    out = [np.zeros(m.npoly, np.int32) for m in meshes]
    for i, di in zip(isl, d):
        out[i.mi][i.polys] = HIDDEN if di < med * hidden_below else ROOMY if di < med * roomy_below else VISIBLE
    return out


def eye_factors(objs, eyes: list, occluders=None, far_k: float = FAR_K) -> dict:
    """Прибавка плотности по камере от первого лица. Для грани и каждого глаза: видна ли (в кадре, лицом к глазу, луч
    до глаза не упёрся в сборку), расстояние d и наклон. Нужная плотность текселей на экране ~ √cos / d; множитель — она против
    медианной по граням, видимым первому глазу (от бедра), в пределах [far_k, k_max глаза]. Невидимые из глаза грани —
    не больше 1 (ближние 1, дальние до far_k по расстоянию). Возврат: k граней, видна ли и расстояние до первого глаза."""
    occ = occluders if occluders is not None else [o for o in bpy.context.scene.objects
                                                   if o.type == 'MESH' and len(o.data.polygons)]
    verts, polys = [], []
    for o in occ:
        mw = o.matrix_world
        base = len(verts)
        verts += [mw @ v.co for v in o.data.vertices]
        polys += [[base + i for i in p.vertices] for p in o.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)
    meshes = [_Mesh(o, o.data.uv_layers.active.name) for o in objs]
    seen, gval, dist0 = [], [], []
    for m in meshes:
        n, c = m.poly_n, m.poly_c
        s_m = np.zeros((len(eyes), m.npoly), bool)
        g_m = np.zeros((len(eyes), m.npoly))
        d0 = None
        for ei, e in enumerate(eyes):
            v = e.pos[None] - c
            d = np.linalg.norm(v, axis=1)
            cos = (n * v).sum(1) / np.maximum(d, 1e-9)
            if ei == 0:
                d0 = d
            for p in np.flatnonzero((cos > 0.05) & e.in_view(c)):
                st = c[p] + n[p] * 1e-5
                hit = bvh.ray_cast(st.tolist(), (v[p] / d[p]).tolist(), float(d[p]) - 1e-4)
                if hit[0] is None:
                    s_m[ei, p] = True
            g_m[ei] = np.sqrt(np.clip(cos, 0.0, 1.0)) / np.maximum(d, 1e-3)
        seen.append(s_m)
        gval.append(g_m)
        dist0.append(d0)
    # опора — медиана по площади среди граней, видимых первому глазу
    g0 = np.concatenate([g[0][s[0]] for g, s in zip(gval, seen)])
    a0 = np.concatenate([m.poly_a3[s[0]] for m, s in zip(meshes, seen)])
    d00 = np.concatenate([d[s[0]] for d, s in zip(dist0, seen)])
    if not len(g0):
        return dict(k=[np.ones(m.npoly) for m in meshes], seen=[s.any(0) for s in seen], dist=dist0)
    o = np.argsort(g0)
    g_ref = g0[o][np.searchsorted(np.cumsum(a0[o]), a0.sum() / 2)]
    o = np.argsort(d00)
    d_ref = d00[o][np.searchsorted(np.cumsum(a0[o]), a0.sum() / 2)]
    ks = []
    for m, s_m, g_m, d0 in zip(meshes, seen, gval, dist0):
        k = np.clip(d_ref / np.maximum(d0, 1e-3), far_k, 1.0)          # не видна ни одному глазу
        seen_any = np.zeros(m.npoly, bool)
        for ei, e in enumerate(eyes):
            ke = np.clip(g_m[ei] / g_ref, far_k, e.k_max)
            k = np.where(s_m[ei], np.where(seen_any, np.maximum(k, ke), ke), k)
            seen_any |= s_m[ei]
        ks.append(k)
    return dict(k=ks, seen=[s.any(0) for s in seen], dist=dist0, g_ref=float(g_ref), d_ref=float(d_ref))


FIB_N = 320
_FIB = np.array([(math.cos(2.399963 * k) * math.sqrt(1 - (1 - (2 * k + 1) / FIB_N) ** 2),
                  math.sin(2.399963 * k) * math.sqrt(1 - (1 - (2 * k + 1) / FIB_N) ** 2),
                  1 - (2 * k + 1) / FIB_N) for k in range(FIB_N)])


def visibility(objs, poses: dict | None = None, node_of=None, contact: float = CONTACT_M, roomy: float = ROOMY_M) -> list:
    """Классы граней лучами, как в game_lp ВЕРАС-54: видимая — хоть в одной позе хоть один луч из полусферы уходит из
    сборки; прижатая (CONTACT, такие удаляют) — во всех позах медиана лучей ближе contact; просторная скрытая — медиана
    дальше roomy хоть в одной позе; остальное — скрытое. poses — {поза: {узел: Matrix}}, node_of(obj) → узел;
    без них — одна поза как есть."""
    from mathutils import Matrix, Vector
    poses = poses or {'rest': {}}
    eye4 = Matrix.Identity(4)
    vis = [set() for _ in objs]
    cont = [None for _ in objs]
    room = [set() for _ in objs]
    dirs = [Vector(d) for d in _FIB]
    for pose in poses.values():
        posed = [(o, pose.get(node_of(o), eye4) if node_of else eye4) for o in objs]
        verts, polys = [], []
        for o, mx in posed:
            m = mx @ o.matrix_world
            base = len(verts)
            verts += [m @ v.co for v in o.data.vertices]
            polys += [[base + i for i in pl.vertices] for pl in o.data.polygons]
        bvh = BVHTree.FromPolygons(verts, polys)
        for oi, (o, mx) in enumerate(posed):
            m = mx @ o.matrix_world
            nm = m.to_3x3().inverted().transposed()
            me = o.data
            c_set = set()
            for pl in me.polygons:
                n = (nm @ pl.normal).normalized()
                c = m @ pl.center
                starts = [c] + [c + ((m @ me.vertices[i].co) - c) * 0.85 for i in pl.vertices]
                ds = [d for d in dirs if d.dot(n) > 0.05]
                dist, seen = [], False
                for st in starts:
                    for d in ds:
                        hit = bvh.ray_cast(st + n * 1e-5, d, 2.0)
                        if hit[0] is None:
                            seen = True
                            break
                        dist.append(hit[3])
                    if seen:
                        break
                if seen:
                    vis[oi].add(pl.index)
                else:
                    med = sorted(dist)[len(dist) // 2]
                    if med < contact:
                        c_set.add(pl.index)
                    elif med > roomy:
                        room[oi].add(pl.index)
            cont[oi] = c_set if cont[oi] is None else cont[oi] & c_set
    out = []
    for oi, o in enumerate(objs):
        cls = np.full(len(o.data.polygons), HIDDEN, np.int32)
        cls[list(room[oi])] = ROOMY
        cls[list(cont[oi] or ())] = CONTACT
        cls[list(vis[oi])] = VISIBLE
        out.append(cls)
    return out


# ---------------------------------------------------------------------------------------------- группы и внахлёст
def _hard_pairs(m: _Mesh, isl_of_poly: np.ndarray, angle: float = HARD_ON_SEAM) -> tuple:
    """Пары островов одной сетки, разделённых жёстким ребром (атрибут sharp_edge; без него — излом больше angle)."""
    order = np.argsort(m.le, kind='stable')
    e = m.le[order]
    same = e[1:] == e[:-1]
    l1, l2 = order[:-1][same], order[1:][same]
    p1, p2 = m.poly_of_loop[l1], m.poly_of_loop[l2]
    i1, i2 = isl_of_poly[p1], isl_of_poly[p2]
    edge = m.le[l1]
    if m.sharp.any():
        hard = m.sharp[edge]
    else:
        hard = (m.poly_n[p1] * m.poly_n[p2]).sum(1) < math.cos(angle)
    keep = (i1 != i2) & hard & (i1 >= 0) & (i2 >= 0)
    return i1[keep], i2[keep], l1[keep], l2[keep]


def find_groups(meshes: list, isl: list, hidden_pool: bool = False) -> dict:
    """Группы «разрыва»: острова, соседние через жёсткое ребро (копии внахлёст не в счёт); hidden_pool — все скрытые
    (× 0,1) острова атласа ещё и одной группой. Возврат: число групп из 2+ островов и швы для сшивки —
    {(a, b): массив (n, 4) петель (a_u, a_w, b_u, b_w)} по номерам среди живых островов, петли — номера в uvm острова."""
    live = [n for n, i in enumerate(isl) if i.owner is None]
    pos = {n: j for j, n in enumerate(live)}
    a_all, b_all = [], []
    seams: dict = {}
    for mi, m in enumerate(meshes):
        iop = np.full(m.npoly, -1, np.int64)
        for n in live:
            if isl[n].mi == mi:
                iop[isl[n].polys] = pos[n]
        a, b, l1, l2 = _hard_pairs(m, iop)
        a_all.append(a)
        b_all.append(b)
        # шов: в грани A ребро идёт u → w; в грани B — та же пара вершин (обход обратный, если сетка согласована)
        u, w = m.lv[l1], m.lv[m.next_loop[l1]]
        nl2 = m.next_loop[l2]
        lb_u = np.where(m.lv[l2] == u, l2, nl2)
        lb_w = np.where(m.lv[l2] == u, nl2, l2)
        for ia, ib, au, aw, bu, bw in zip(a.tolist(), b.tolist(), l1.tolist(), m.next_loop[l1].tolist(),
                                          lb_u.tolist(), lb_w.tolist()):
            A, B = isl[live[ia]], isl[live[ib]]
            row = [int(np.searchsorted(A.loops, au)), int(np.searchsorted(A.loops, aw)),
                   int(np.searchsorted(B.loops, bu)), int(np.searchsorted(B.loops, bw))]
            seams.setdefault((ia, ib), []).append(row)
            seams.setdefault((ib, ia), []).append([row[2], row[3], row[0], row[1]])
    a = np.concatenate(a_all) if a_all else np.zeros(0, np.int64)
    b = np.concatenate(b_all) if b_all else np.zeros(0, np.int64)
    if hidden_pool:
        hid = [pos[n] for n in live if isl[n].cls == HIDDEN]
        a = np.concatenate([a, np.array(hid[1:], np.int64)])
        b = np.concatenate([b, np.array(hid[:-1], np.int64)])
    label = _union_find(len(live), a, b)
    for n in live:
        isl[n].group = int(label[pos[n]])
    for i in isl:
        if i.owner is not None:
            i.group = -1
    seams = {k: np.array(v, np.int64) for k, v in seams.items()}
    _PAIRS[:] = [a, b, seams]
    return dict(groups=int(sum(c > 1 for c in np.bincount(label))), seams=seams)


_PAIRS: list = []      # последние пары соседей find_groups (номера среди живых островов) — для выгрузки опытов


def _frame(p0, p1, p2) -> np.ndarray:
    e1 = p1 - p0
    e1 = e1 / np.linalg.norm(e1)
    v = p2 - p0
    e2 = v - (v @ e1) * e1
    e2 = e2 / np.linalg.norm(e2)
    return np.stack([e1, e2, np.cross(e1, e2)])


def _match(A: Island, B: Island, ma: _Mesh, mb: _Mesh, tol: float):
    """Вершины B — это вершины A после движения или отражения? Возврат (loop_map: петля B → петля A, перевёрнут ли)
    или None. Разбиение на треугольники должно совпасть."""
    PA, PB = ma.co[A.verts], mb.co[B.verts]
    XA, XB = PA - PA.mean(0), PB - PB.mean(0)
    ra, rb = np.linalg.norm(XA, axis=1), np.linalg.norm(XB, axis=1)
    if np.abs(np.sort(ra) - np.sort(rb)).max() > tol:
        return None
    i0 = int(np.argmax(ra))
    d0 = np.linalg.norm(XA - XA[i0], axis=1)
    i1 = int(np.argmax(d0))
    cn = np.linalg.norm(np.cross(XA[i1] - XA[i0], XA - XA[i0]), axis=1)
    i2 = int(np.argmax(cn))
    if d0[i1] < tol or cn[i2] < tol * d0[i1]:
        return None
    FA = _frame(XA[i0], XA[i1], XA[i2])
    d12 = float(np.linalg.norm(XA[i2] - XA[i1]))
    flipped = None
    tries = 0
    for j0 in np.flatnonzero(np.abs(rb - ra[i0]) < tol):
        db0 = np.linalg.norm(XB - XB[j0], axis=1)
        for j1 in np.flatnonzero((np.abs(rb - ra[i1]) < tol) & (np.abs(db0 - d0[i1]) < tol)):
            db1 = np.linalg.norm(XB - XB[j1], axis=1)
            for j2 in np.flatnonzero((np.abs(rb - ra[i2]) < tol) & (np.abs(db0 - d0[i2]) < tol) & (np.abs(db1 - d12) < tol)):
                tries += 1
                if tries > 240:
                    return flipped
                FB = _frame(XB[j0], XB[j1], XB[j2])
                for det in (1.0, -1.0):
                    FBd = FB.copy()
                    FBd[2] *= det
                    T = (XA - XA[i0]) @ (FBd.T @ FA).T + XB[j0]
                    D = np.linalg.norm(T[:, None] - XB[None], axis=2)
                    nn = D.argmin(1)
                    if D[np.arange(len(nn)), nn].max() > tol or len(np.unique(nn)) != len(nn):
                        continue
                    res = _loop_map(A, B, ma, mb, nn)
                    if res is None:
                        continue
                    if not res[1]:
                        return res
                    flipped = flipped or res
    return flipped


def _loop_map(A: Island, B: Island, ma: _Mesh, mb: _Mesh, nn: np.ndarray):
    """Соответствие петель B петлям A по соответствию вершин (nn: локальная вершина A → локальная B) и перевёрнут ли
    перенос развёртки A на B (знак площади в UV)."""
    a_local = {int(v): n for n, v in enumerate(A.verts)}
    b_global = B.verts
    faces = {}
    for p in A.polys:
        ls = range(ma.ls[p], ma.ls[p] + ma.lt[p])
        key = frozenset(int(b_global[nn[a_local[int(ma.lv[l])]]]) for l in ls)
        faces[key] = {int(b_global[nn[a_local[int(ma.lv[l])]]]): l for l in ls}
    out = np.empty(len(B.loops), np.int64)
    pos = {int(l): n for n, l in enumerate(B.loops)}
    for p in B.polys:
        ls = range(mb.ls[p], mb.ls[p] + mb.lt[p])
        f = faces.get(frozenset(int(mb.lv[l]) for l in ls))
        if f is None:
            return None
        for l in ls:
            out[pos[l]] = f[int(mb.lv[l])]
    q = ma.uv[out][B.tri_local]
    s = 0.5 * ((q[:, 1, 0] - q[:, 0, 0]) * (q[:, 2, 1] - q[:, 0, 1]) - (q[:, 2, 0] - q[:, 0, 0]) * (q[:, 1, 1] - q[:, 0, 1]))
    return out, bool((1.0 if s.sum() >= 0 else -1.0) != A.sign)


def find_stacks(meshes: list, isl: list, stack_max: float = STACK_MAX_M) -> dict:
    """Внахлёст: одинаковые острова. Без переворота — мелкие (габарит до stack_max) и скрытые; с переворотом (зеркальные)
    — только скрытые (просторные скрытые тоже). Хозяин — остров с наибольшей плотностью в своём классе одинаковых."""
    cand = [i for i in isl if (i.size3 <= stack_max or i.cls != VISIBLE) and len(i.verts) <= 600]
    by = {}
    for i in cand:
        by.setdefault((len(i.polys), len(i.verts)), []).append(i)
    rigid = mirror = 0
    for group in by.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda i: i.a3)
        run = [group[0]]
        runs = []
        for i in group[1:]:
            if i.a3 - run[-1].a3 <= 1e-4 * i.a3 + 1e-12:
                run.append(i)
            else:
                runs.append(run)
                run = [i]
        runs.append(run)
        for run in runs:
            if len(run) < 2:
                continue
            run.sort(key=lambda i: -i.k)
            owners = []
            for b in run:
                for a in owners:
                    tol = max(2e-5, 2e-3 * a.size3)
                    res = _match(a, b, meshes[a.mi], meshes[b.mi], tol)
                    if res is None:
                        continue
                    loop_map, flip = res
                    hidden = a.cls != VISIBLE and b.cls != VISIBLE
                    if (flip and hidden) or (not flip and (hidden or max(a.size3, b.size3) <= stack_max)):
                        b.owner, b.loop_map, b.flip = a, loop_map, flip
                        mirror += flip
                        rigid += not flip
                        break
                if b.owner is None:
                    owners.append(b)
    return dict(stacked_rigid=rigid, stacked_mirror=mirror)


# ---------------------------------------------------------------------------------------------- укладка целиком
def layout(objs, size: int, *, uv: str = 'GameUV', classes: list | None = None, eyes: list = (), occluders=None,
           margin: int = MARGIN_PX, group_margin: int = GROUP_MARGIN_PX, stack: bool = True, stack_max: float = STACK_MAX_M,
           groups: bool = True, stitch: bool = False, hidden_pool: bool = False, holes: bool = True, score: str = 'bl',
           order: str = 'area', fill_guess: float = 0.55, precision: float = 0.006, dump: str | None = None,
           log=None) -> dict:
    """Развёртка uv объектов objs (один атлас size × size) переложена по нормам; острова не перерезаются. classes —
    классы граней по объектам (VISIBLE / ROOMY / HIDDEN / CONTACT), eyes — точки глаза (Eye), occluders — что
    заслоняет глаз (по умолчанию вся сцена). Возврат — отчёт укладки; UV записаны, копии внахлёст помечены uv_stack.
    dump — путь .npz: острова для опытов с укладчиком вне Blender."""
    say = log or (lambda *a: None)
    t0 = time.time()
    meshes = [_Mesh(o, uv) for o in objs]
    isl = islands_of(meshes, classes)
    if classes is not None:
        for i in isl:
            c = classes[i.mi][i.polys]
            a = meshes[i.mi].poly_a3[i.polys]
            i.cls = int(max(CLASS_K, key=lambda k: float(a[c == k].sum())))
    ef = eye_factors(objs, list(eyes), occluders) if eyes else None
    for i in isl:
        m = meshes[i.mi]
        if i.cls != VISIBLE:
            i.k = CLASS_K[i.cls]
        elif ef is not None:
            a = m.poly_a3[i.polys]
            i.k = float((ef['k'][i.mi][i.polys] * a).sum() / max(a.sum(), 1e-30))
        i.to_metres(m)
    st = find_stacks(meshes, isl, stack_max) if stack else dict(stacked_rigid=0, stacked_mirror=0)
    live = [i for i in isl if i.owner is None]
    seams: dict = {}
    if groups:
        fg = find_groups(meshes, isl, hidden_pool)
        n_groups, seams = fg['groups'], fg['seams'] if stitch else {}
    else:
        n_groups = 0
        for n, i in enumerate(live):
            i.group = n
    sizes = np.bincount([i.group for i in live])
    if dump:
        _dump(dump, live)
    r1, r2 = (margin + 1) // 2, (group_margin + 1) // 2
    say('islands', len(isl), 'packed', len(live), 'groups', n_groups, st, f'{time.time() - t0:.1f}s')
    s, pieces, placed, stats, tries = uv_pack.search(live, size, r1, r2, fill_guess=fill_guess, precision=precision,
                                                    say=say, seams=seams, holes=holes, score=score, order=order)
    stats['footprint_px'] = uv_pack.footprint(pieces, placed, size, r1, r2)
    # запись: точка острова в метрах → пиксели атласа → UV
    out_uv = [m.uv.copy() for m in meshes]
    for p, (q, x, y) in zip(pieces, placed):
        Mp = uv_pack.rot_matrix(q, p.mask.shape[1], p.mask.shape[0], x, y)
        for i, Mi in p.members:
            M = Mp @ Mi
            px = i.uvm * (s * i.k)
            out_uv[i.mi][i.loops] = (px @ M[:2, :2].T + M[:2, 2]) / size
    for i in isl:
        if i.owner is not None:
            out_uv[i.mi][i.loops] = out_uv[i.owner.mi][i.loop_map]
    for mi, m in enumerate(meshes):
        m.write_uv(out_uv[mi])
        me = m.obj.data
        at = me.attributes.get('uv_stack') or me.attributes.new('uv_stack', 'INT', 'FACE')
        val = np.zeros(m.npoly, np.int32)
        grp = np.zeros(m.npoly, np.int32)
        for i in isl:
            if i.mi == mi and i.owner is not None:
                val[i.polys] = 2 if i.flip else 1
            elif i.mi == mi:
                grp[i.polys] = i.group + 1
        at.data.foreach_set('value', val)
        # группа укладки (номер + 1, у копий 0): внутри группы отступ половинный — для проверки и запекания
        at = me.attributes.get('uv_group') or me.attributes.new('uv_group', 'INT', 'FACE')
        at.data.foreach_set('value', grp)
    W2 = float(size * size)
    fill = sum(i.a3 * (s * i.k) ** 2 for i in live) / W2
    rep = dict(
        px_mm=round(s / 1000, 3), fill=round(fill, 4), islands=len(isl), packed_islands=len(live), pieces=len(pieces),
        groups=n_groups, group_members=int(sizes[sizes > 1].sum()), **st,
        margin_px=margin, group_margin_px=group_margin, stack=stack, stitch=bool(seams), hidden_pool=hidden_pool,
        holes=holes, score=score, order=order, stitched_islands=stats.get('stitched', 0), units=stats.get('units', 0),
        eyes=[dict(name=e.name, pos=[round(float(c), 4) for c in e.pos], k_max=e.k_max) for e in eyes],
        # куда ушла площадь атласа: острова, округление до пикселей, отступы, пустое (из него — пустоты под горизонтом)
        loss_pixel_round=round(stats['raw_px'] / W2 - fill, 4),
        loss_margins=round((stats['footprint_px'] - stats['raw_px']) / W2, 4),
        loss_empty=round(1.0 - stats['footprint_px'] / W2, 4),
        empty_below_skyline=round(stats.get('below_skyline_free_px', 0) / W2, 4), in_holes=stats.get('in_holes', 0),
        k_visible=[round(min((i.k for i in live if i.cls == VISIBLE), default=1.0), 3),
                   round(max((i.k for i in live if i.cls == VISIBLE), default=1.0), 3)],
        tries=tries, sec=round(time.time() - t0, 1))
    say('layout', {k: v for k, v in rep.items() if k not in ('tries', 'eyes')})
    return rep


def _dump(path: str, live: list) -> None:
    """Острова для опытов с укладчиком: координаты в метрах, треугольники, множитель, класс, группа."""
    np.savez_compressed(
        path, uvm=np.concatenate([i.uvm for i in live]), n_loops=np.array([len(i.uvm) for i in live]),
        tri=np.concatenate([i.tri_local for i in live]), n_tri=np.array([len(i.tri_local) for i in live]),
        ext=np.array([i.ext for i in live]), k=np.array([i.k for i in live]), a3=np.array([i.a3 for i in live]),
        cls=np.array([i.cls for i in live]), group=np.array([i.group for i in live]),
        pair_a=_PAIRS[0] if _PAIRS else np.zeros(0, np.int64), pair_b=_PAIRS[1] if _PAIRS else np.zeros(0, np.int64),
        seam_key=np.array(list(_PAIRS[2].keys()) if _PAIRS else np.zeros((0, 2)), np.int64).reshape(-1, 2),
        seam_n=np.array([len(v) for v in _PAIRS[2].values()] if _PAIRS else [], np.int64),
        seam_loops=np.concatenate(list(_PAIRS[2].values())) if _PAIRS and _PAIRS[2] else np.zeros((0, 4), np.int64))


# ---------------------------------------------------------------------------------------------- отчёт и проверка
def report(objs, size: int, *, uv: str = 'GameUV', classes: list | None = None, zones: list | None = None) -> dict:
    """Замер любой развёртки: заполнение (копии внахлёст не в счёт), плотность пикс/мм — всего, видимого, у глаза
    (zones = 1), вдали (zones = -1), скрытого; острова и мелкие острова; перевёрнутые и растянутые грани видимого."""
    meshes = [_Mesh(o, uv) for o in objs]
    isl = islands_of(meshes)
    acc = {k: [0.0, 0.0] for k in ('all', 'vis', 'eye', 'far', 'hid')}
    fill = fill_gross = 0.0
    n_isl = small = copies = flips = 0
    flip_a = stretch_a = vis_a = 0.0
    for i in isl:
        m = meshes[i.mi]
        a2s = m.tri_a2s[i.tris]
        a3 = m.tri_a3[i.tris]
        tp = m.tri_poly[i.tris]
        cl = classes[i.mi][tp] if classes is not None else np.zeros(len(tp), np.int32)
        zn = zones[i.mi][tp] if zones is not None else np.zeros(len(tp), np.int32)
        a2 = np.abs(a2s)
        fill_gross += a2.sum()
        is_copy = bool((m.stack[i.polys] > 0).all())
        if is_copy:
            copies += 1
        else:
            fill += a2.sum()
            n_isl += 1
            u = m.uv[i.loops] * size
            small += max(np.ptp(u[:, 0]), np.ptp(u[:, 1])) < SMALL_PX
        for key, sel in (('all', slice(None)), ('vis', cl == VISIBLE), ('eye', (cl == VISIBLE) & (zn == 1)),
                         ('far', (cl == VISIBLE) & (zn == -1)), ('hid', cl != VISIBLE)):
            acc[key][0] += a2[sel].sum()
            acc[key][1] += a3[sel].sum()
        v = cl == VISIBLE
        if v.any() and a3[v].sum() > 0:
            vis_a += a3[v].sum()
            dens = a2.sum() / max(a3.sum(), 1e-30)
            # растяжение грани против острова за пределами нормы 0,8–1,2 по стороне
            r = a2[v] / np.maximum(a3[v], 1e-30) / max(dens, 1e-30)
            stretch_a += a3[v][(r < 0.64) | (r > 1.44)].sum()
            bad = (np.sign(a2s[v]) != np.sign(a2s.sum())) & (a2[v] > 1e-14)
            flip_a += a3[v][bad].sum()
            flips += bool(bad.any())
    px = lambda k: round(math.sqrt(acc[k][0] / acc[k][1]) * size / 1000, 2) if acc[k][1] > 0 else None
    fill, fill_gross, stretch_a, flip_a, vis_a = map(float, (fill, fill_gross, stretch_a, flip_a, vis_a))
    return dict(fill=round(fill, 4), fill_with_copies=round(fill_gross, 4), islands=n_isl, islands_small=int(small),
                stacked_copies=copies, px_mm=px('all'), px_mm_visible=px('vis'), px_mm_eye=px('eye'), px_mm_far=px('far'),
                px_mm_hidden=px('hid'), stretch_share=round(stretch_a / max(vis_a, 1e-30), 5),
                flipped_share=round(flip_a / max(vis_a, 1e-30), 5), islands_with_flips=flips)


def verify(objs, size: int, *, uv: str = 'GameUV', margin: int = MARGIN_PX, group_margin: int = GROUP_MARGIN_PX,
           classes: list | None = None) -> dict:
    """Независимая проверка готовой укладки растром: острова внутри квадрата, между любыми двумя не меньше
    group_margin, между группами не меньше margin. Группы — атрибут граней uv_group, который пишет layout (без него —
    каждый остров сам по себе); копии внахлёст (uv_stack) не проверяются."""
    meshes = [_Mesh(o, uv) for o in objs]
    isl = islands_of(meshes, classes)
    live = []
    for n, i in enumerate(isl):
        me = objs[i.mi].data
        if (meshes[i.mi].stack[i.polys] > 0).all():
            continue
        live.append(i)
        if 'uv_group' in me.attributes:
            g = np.zeros(len(me.polygons), np.int32)
            me.attributes['uv_group'].data.foreach_get('value', g)
            i.group = int(np.bincount(g[i.polys]).argmax())
        else:
            i.group = n
    L1 = np.full((size, size), -1, np.int32)
    L2 = np.full((size, size), -1, np.int32)
    r2, r1 = group_margin // 2, margin // 2
    out_of_square = close_any = close_groups = 0
    for n, i in enumerate(live):
        m = meshes[i.mi]
        px = m.uv[i.loops] * size
        x0, y0 = int(math.floor(px[:, 0].min() + 0.01)), int(math.floor(px[:, 1].min() + 0.01))
        w = int(math.ceil(px[:, 0].max())) - x0 + 1
        h = int(math.ceil(px[:, 1].max())) - y0 + 1
        raw = uv_pack.raster((px - (x0, y0))[i.tri_local], w, h, eps=0.01)
        ry, rx = np.nonzero(raw)
        if not len(rx):
            continue                     # вырожденный остров: в пределах допуска ни одного пикселя
        # до края квадрата — не меньше половины отступа между деталями
        if x0 + rx.min() < r1 or y0 + ry.min() < r1 or x0 + rx.max() > size - 1 - r1 or y0 + ry.max() > size - 1 - r1:
            out_of_square += 1
        for lab, r, Lm in ((n, r2, L1), (i.group, r1, L2)):
            d = uv_pack.dilate(raw, r)
            ys, xs = np.nonzero(d)
            ys, xs = ys + y0 - r, xs + x0 - r
            ok = (ys >= 0) & (ys < size) & (xs >= 0) & (xs < size)
            ys, xs = ys[ok], xs[ok]
            prev = Lm[ys, xs]
            clash = (prev >= 0) & (prev != lab)
            if Lm is L1:
                close_any += int(clash.sum())
            else:
                close_groups += int(clash.sum())
            Lm[ys, xs] = lab
    return dict(out_of_square=out_of_square, px_closer_than_group_margin=close_any,
                px_groups_closer_than_margin=close_groups, checked_islands=len(live))


# ---------------------------------------------------------------------------------------------- развёртка новой сетки
def smart_unwrap(objs, uv: str = 'GameUV', angle: float = SHARP) -> None:
    """Smart UV по игровой сетке (острова по изломам) и ровная плотность — как начало unwrap в game_lp; дальше layout."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        if uv not in o.data.uv_layers:
            o.data.uv_layers.new(name=uv)
        o.data.uv_layers.active = o.data.uv_layers[uv]
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=angle, island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action='SELECT')
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode='OBJECT')


def harden_on_seams(objs, uv: str = 'GameUV', angle: float = HARD_ON_SEAM) -> None:
    """Жёсткое ребро — только на шве развёртки; шов с изломом больше angle — жёсткий (как game_lp)."""
    for o in objs:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        uvl = bm.loops.layers.uv[uv]
        for e in bm.edges:
            if len(e.link_faces) != 2:
                continue
            f1, f2 = e.link_faces
            u1 = {l.vert.index: l[uvl].uv for l in f1.loops}
            u2 = {l.vert.index: l[uvl].uv for l in f2.loops}
            seam = any((u1[v.index] - u2[v.index]).length > 1e-6 for v in e.verts)
            e.smooth = not (seam and e.calc_face_angle(0.0) > angle)
        bm.to_mesh(o.data)
        bm.free()


def shift_stack_copies(objs, du: float, uv: str = 'GameUV') -> int:
    """Копии внахлёст (uv_stack > 0) сдвинуть по U на du: перед запеканием +1 (за квадрат), после — обратно −1."""
    n = 0
    for o in objs:
        me = o.data
        if 'uv_stack' not in me.attributes:
            continue
        val = np.zeros(len(me.polygons), np.int32)
        me.attributes['uv_stack'].data.foreach_get('value', val)
        m = _Mesh(o, uv)
        loops = _ranges(m.ls[val > 0], m.lt[val > 0])
        m.uv[loops, 0] += du
        m.write_uv(m.uv)
        n += int((val > 0).sum())
    return n
