"""NPC: рюкзаки трёх видов — форма на мародёре v03, без брони и поверх каждой из трёх броней (решения владельца
2026-10-22: данные bp_daypack / bp_tourist / bp_raid не меняются, модели — заново, в одном стиле с бронёй;
рюкзак надевают и без брони, и с бронёй; docs/design/gear_v2.md).

- городской (bp_daypack, 30 ячеек, ~25 л, 47 × 30 × 20 см) — понравился владельцу: купол сверху, молния «подковой»,
  карман на молнии спереди, сетчатые боковые карманы, ручка, лямки S-формы с грудной перемычкой, две подушки спинки;
- туристический (bp_tourist, 45 ячеек) — по образцу владельца (штурмовой рюкзак с «бобровым хвостом»): мешок книзу
  шире, спереди панель-«хвост» (вверху уже, ряд стропы и полоса липучки, внизу карман
  с откинутым клапаном и квадратом липучки), стропы с фастексами сверху через верх, по бокам и снизу к углам хвоста,
  по бокам сетчатые карманы со шнуром и подсумки на молнии у спинки, лямки с «гирляндой» стропы и D-кольцами,
  поясная стропа с фастексом, молния основного отделения сверху, ручка;
- рейдовый (bp_raid, 60 ячеек) — по образцу владельца (большой армейский рюкзак): клапан-подушка с MOLLE спереди
  и сверху, спереди панель с MOLLE, по её краям две длинные стропы от клапана до дна с регуляторами, по бокам
  объёмные карманы с клапаном-«углом» на фастексе и двумя стяжками, внизу отдельный отсек (шов и молния), четыре
  петли на дне, спинка — две длинные подушки и поясничная сетка, лямки S-формы; поясного ремня и перемычки нет.

Мешок — горизонтальные сечения-суперэллипсы (спинка плоская по линии спины, лицевая сторона выпуклая, скругления
дна и верха радиусами, сужение и перехват по высоте); детали стоят на сторонах мешка через проекцию (лицевая,
боковые, верх, низ, спинка). Посадка (Body) — внешняя оболочка куртки и брони: лучи снаружи к оси торса, поэтому
на броне лямка ложится на броню, а не на куртку под ней; спинка рюкзака отходит на толщину брони сзади.
Посадок четыре (без брони, бомжовская, средняя, крутая) — у каждой свои сетки; в игре вариант выбирают по броне.
Марок нет. Коллекции: 07_Backpack_<вид> → 07_<вид> · <посадка>; брони — 06_Armor_* из примерочной.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/backpacks.py -- [render] [deliver=<папка>]
→ _asset_src/npc_kit/backpacks/backpacks.blend (читает примерочную брони armor_fitting_<версия мародёра>.blend)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Callable

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armor_kit as ak  # noqa: E402
import garment as gm  # noqa: E402
import kit_common as kc  # noqa: E402
import soft_goods as sg  # noqa: E402

OUT = kc.WORK / "backpacks"
VERSION = "v02"
WEB = 0.025                     # стропа 25 мм
MOLLE_PITCH = 0.0381            # шаг рядов MOLLE (1,5 дюйма)
CY = -0.01                      # ось торса (y) для «наружу»
SMOOTH_KEY = "Без складок"      # ключ формы мешка: гладкая форма до складок (по ней — кромки в текстурах)
FITS = (("none", "без брони", None, ""), ("poor", "бомжовская", "06_Armor_Poor", "_Poor"),
        ("mid", "средняя", "06_Armor_Mid", "_Mid"), ("top", "крутая", "06_Armor_Top", "_Top"))


# ---------- мешок ----------

def superellipse(t: float, a: float, b: float, n: float) -> tuple[float, float]:
    c, s = math.cos(t), math.sin(t)
    return (a * math.copysign(abs(c) ** (2.0 / n), c), b * math.copysign(abs(s) ** (2.0 / n), s))


class Bag:
    """Мешок: на высоте v сечение — суперэллипс шириной 2·hw и глубиной d (спинка у y_in, лицевая сторона дальше
    от тела, +Y). Спинку делает плоской большая степень n_back, лицевую — выпуклой bulge (подушка к середине
    высоты). Скругления: низ — радиусом rb, верх по ширине — rt_w (купол на виде спереди), по глубине — rt_d.
    hw1 — полуширина вверху (мешок книзу шире), pinch — (v, ширина, глубина) перехвата (шов отсека)."""

    def __init__(self, z0: float, H: float, hw: float, d0: float, d1: float, y_in: Callable[[float], float],
                 rb: float = 0.03, rt_w: float = 0.05, rt_d: float = 0.04, n_front: float = 3.5, n_back: float = 8.0,
                 bulge: float = 0.012, seg: int = 112, hw1: float | None = None,
                 pinch: tuple[float, float, float] | None = None, row_step: float = 0.012):
        self.z0, self.H, self.hw, self.d0, self.d1 = z0, H, hw, d0, d1
        self.y_in, self.rb, self.rt_w, self.rt_d = y_in, rb, rt_w, rt_d
        self.n_front, self.n_back, self.bulge, self.seg = n_front, n_back, bulge, seg
        self.hw1 = hw if hw1 is None else hw1
        self.pinch = pinch
        # высоты рядов: гуще на скруглениях
        vs = [rb * (1 - math.cos(math.pi / 2 * k / 8)) for k in range(9)]
        top0 = H - max(rt_w, rt_d)
        nm = max(2, int((top0 - rb) / row_step))
        vs += [rb + (top0 - rb) * k / nm for k in range(1, nm + 1)]
        rt = max(rt_w, rt_d)
        vs += [top0 + rt * math.sin(math.pi / 2 * k / 14) for k in range(1, 15)]
        self.vs = vs

    def section(self, v: float) -> tuple[float, float, float]:
        """(полуширина, глубина, y спинки) на высоте v."""
        def round_off(r: float, x: float) -> float:            # насколько сечение меньше на скруглении
            return r - math.sqrt(max(0.0, r * r - x * x)) if x > 0 else 0.0
        hw = self.hw + (self.hw1 - self.hw) * (v / self.H)
        hw = hw - round_off(self.rb, self.rb - v) - round_off(self.rt_w, v - (self.H - self.rt_w))
        d = self.d0 + (self.d1 - self.d0) * (v / self.H)
        d = d - round_off(self.rb, self.rb - v) - round_off(self.rt_d, v - (self.H - self.rt_d))
        if self.pinch:
            pv, pw, pd = self.pinch
            g = math.exp(-((v - pv) / pw) ** 2)
            hw -= pd * g
            d -= pd * g
        z = self.z0 + v
        return max(hw, 0.004), max(d, 0.004), self.y_in(z)

    def ring(self, v: float) -> list[Vector]:
        hw, d, yi = self.section(v)
        hd = d / 2
        yc = yi + hd
        prof = math.sin(math.pi * min(1.0, max(0.0, v / self.H)))
        out = []
        for i in range(self.seg):
            t = 2 * math.pi * i / self.seg + math.pi / 2         # от середины лицевой стороны (+Y)
            s = math.sin(t)
            n = self.n_front if s >= 0 else self.n_back
            x, y = superellipse(t, hw, hd, n)
            if s > 0:
                y += self.bulge * prof * s ** 2 * max(0.0, 1 - (abs(x) / hw) ** 4)
            out.append(Vector((x, yc + y, self.z0 + v)))
        return out

    def build(self, m: ak.Mesh, mat: int = 0) -> None:
        rows = [self.ring(v) for v in self.vs]
        # развёртка в метрах: u — по обхвату от середины лицевой стороны, v — по образующей
        acc_v = [0.0] * self.seg
        ids, uvs = [], []
        for j, row in enumerate(rows):
            if j:
                acc_v = [acc_v[i] + (row[i] - rows[j - 1][i]).length for i in range(self.seg)]
            per, u = [0.0], 0.0
            for i in range(1, self.seg + 1):
                u += (row[i % self.seg] - row[i - 1]).length
                per.append(u)
            ids.append([m.v(p) for p in row])
            uvs.append([(per[i] - per[-1] / 2 if per[i] > per[-1] / 2 else per[i], acc_v[i]) for i in range(self.seg)])
        m.grid(ids, uvs, mat, closed_u=True)
        for row, flip in ((rows[0], True), (rows[-1], False)):          # донце и верх — веером
            c = sum(row, Vector()) / len(row)
            ci = m.v(c)
            idx = [m.v(p) for p in row]
            for i in range(self.seg):
                f = [idx[i], idx[(i + 1) % self.seg], ci]
                uv = [(row[i].x, row[i].y), (row[(i + 1) % self.seg].x, row[(i + 1) % self.seg].y), (c.x, c.y)]
                m.f(f[::-1] if flip else f, uv[::-1] if flip else uv, mat)


def bvh_of(*bags: Bag) -> BVHTree:
    m = ak.Mesh()
    for b in bags:
        b.build(m)
    return BVHTree.FromPolygons(m.verts, m.faces)


class ProjFrame:
    """Сторона мешка лучом по оси: u, v — координаты в плоскости, поперёк луча (метры мира); off — по нормали.
    face: 'out' — лицевая (u = x, v = z), 'in' — спинка (u = x, v = z), 'side+'/'side-' — боковые (u = y, v = z),
    'top' — верх (u = x, v = y), 'bot' — низ (u = x, v = y)."""

    def __init__(self, bvh: BVHTree, face: str):
        self.bvh, self.face = bvh, face

    def _ray(self, u: float, v: float) -> tuple[Vector, Vector]:
        f = self.face
        if f == "out":
            return Vector((u, 3.0, v)), Vector((0, -1, 0))
        if f == "in":
            return Vector((u, -3.0, v)), Vector((0, 1, 0))
        if f == "side+":
            return Vector((3.0, u, v)), Vector((-1, 0, 0))
        if f == "side-":
            return Vector((-3.0, u, v)), Vector((1, 0, 0))
        if f == "bot":
            return Vector((u, v, -5.0)), Vector((0, 0, 1))
        return Vector((u, v, 5.0)), Vector((0, 0, -1))

    def _hit(self, u: float, v: float) -> Vector:
        o, d = self._ray(u, v)
        hit = self.bvh.ray_cast(o, d, 10.0)
        if hit[0] is not None:
            return hit[0]
        # луч прошёл мимо (у самого края стороны) — ближайшая к лучу точка мешка, а не точка в пустоте
        best = None
        for k in range(41):
            loc, _, _, dist = self.bvh.find_nearest(o + d * (10.0 * k / 40))
            if loc is not None and (best is None or dist < best[1]):
                best = (loc, dist)
        return best[0] if best else o + d * 3.0

    def normal(self, u: float, v: float) -> Vector:
        h = 0.002
        du = self._hit(u + h, v) - self._hit(u - h, v)
        dv = self._hit(u, v + h) - self._hit(u, v - h)
        n = du.cross(dv)
        _, d = self._ray(u, v)
        if n.length < 1e-12:
            return -d
        n.normalize()
        return n if n.dot(d) < 0 else -n

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        return self._hit(u, v) + self.normal(u, v) * off


class VarFrame:
    """Рамка со смещением, зависящим от точки: клапан отходит от кармана, стяжка обходит карман."""

    def __init__(self, base, off_fn: Callable[[float, float], float]):
        self.base, self.off_fn = base, off_fn

    def normal(self, u: float, v: float) -> Vector:
        return self.base.normal(u, v)

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        return self.base.point(u, v, self.off_fn(u, v) + off)


class ShiftFrame:
    """Рамка, сдвинутая по v на dv(u): ряды строп идут по провисшему клапану."""

    def __init__(self, base, dv: Callable[[float], float]):
        self.base, self.dv = base, dv

    def normal(self, u: float, v: float) -> Vector:
        return self.base.normal(u, v - self.dv(u))

    def point(self, u: float, v: float, off: float = 0.0) -> Vector:
        return self.base.point(u, v - self.dv(u), off)


# ---------- посадка: куртка и броня ----------

def radial(p: Vector) -> Vector:
    """«Наружу» от оси торса; выше плеч (z > 1,45) — с подъёмом: на плече наружу — вверх и вбок."""
    return Vector((p.x, p.y - CY, max(0.0, p.z - 1.45) * 2.0)).normalized()


class Body:
    """Внешняя оболочка одежды (и брони посадки): сетки без модификаторов, у куртки без рукавов (руки в A-позе
    не ловят лучи). Точки лямок кладутся лучом снаружи к оси торса — первое попадание и есть то, на чём лямка лежит."""

    def __init__(self, armor: str | None):
        jacket = bpy.data.objects["Jacket"]
        gi = {g.index for g in jacket.vertex_groups if g.name.startswith(("piece_sleeve", "piece_cuff"))}
        sleeve = {v.index for v in jacket.data.vertices if any(g.group in gi and g.weight > 0.5 for g in v.groups)}
        self.armor_objs = ([o for o in bpy.data.collections[armor].all_objects if o.type == "MESH"] if armor else [])
        co, faces = [], []
        parts = [(jacket, sleeve)] + [(bpy.data.objects[n], set()) for n in ("Pants", "Pants_Pocket_L", "Pants_Pocket_R")
                                      if n in bpy.data.objects] + [(o, set()) for o in self.armor_objs]
        for o, skip in parts:
            b = len(co)
            co += [o.matrix_world @ v.co for v in o.data.vertices]
            faces += [[b + i for i in p.vertices] for p in o.data.polygons if not any(i in skip for i in p.vertices)]
        self.bvh = BVHTree.FromPolygons(co, faces)
        self._hull = None

    @property
    def hull(self) -> ak.Hull:
        if self._hull is None:
            self._hull = ak.Hull([bpy.data.objects["Jacket"], bpy.data.objects["Pants"]] + self.armor_objs, 0.90, 1.12)
        return self._hull

    def envelope(self, p: Vector, reach: float = 0.10) -> tuple[Vector, Vector, Vector] | None:
        d = radial(p)
        hit = self.bvh.ray_cast(p + d * reach, -d, reach + 0.14)
        if hit[0] is None:
            return None
        n = hit[1] if hit[1].dot(d) > 0 else -hit[1]
        return hit[0], n, d

    def back_line(self, z_lo: float, z_hi: float) -> Callable[[float], float]:
        """Плоскость спинки рюкзака: прямая y(z), касающаяся спины (с бронёй — брони) сзади в двух точках. На каждой
        высоте берётся вторая по величине из пяти проб поперёк — узкая ручка эвакуации на броне не отодвигает рюкзак."""
        prof = []
        z = z_lo
        while z <= z_hi + 1e-9:
            ys = []
            for x in (-0.10, -0.05, 0.0, 0.05, 0.10):
                hit = self.bvh.ray_cast(Vector((x, 1.5, z)), Vector((0, -1, 0)), 3.0)
                if hit[0] is not None:
                    ys.append(hit[0].y)
            if len(ys) >= 2:
                prof.append((z, sorted(ys)[-2]))
            z += 0.01
        best = None
        zc = (z_lo + z_hi) / 2
        for k100 in range(-30, 31):
            k = k100 / 100
            a = max(y - k * (zz - zc) for zz, y in prof)
            gap = sum(a + k * (zz - zc) - y for zz, y in prof)
            if best is None or gap < best[0]:
                best = (gap, a, k)
        _, a, k = best
        return lambda zz: a + k * (zz - zc)

    def lay(self, pts: list[Vector], lift: float, n_seg: int = 12, passes: int = 8,
            free: int = 0) -> tuple[list[Vector], list[Vector]]:
        """Путь по оболочке: точки на ней + lift, сглажены поверх складок (только наружу). free — сколько первых
        опорных точек висят в воздухе (от рюкзака к плечу) — их не трогать."""
        dense, fixed = [], []
        for i, (a, b) in enumerate(zip(pts, pts[1:])):
            for k in range(n_seg):
                dense.append(a.lerp(b, k / n_seg))
                fixed.append(i < free)
        dense.append(pts[-1])
        fixed.append(len(pts) - 1 < free)

        def snap(q: Vector, i: int) -> Vector:
            if fixed[i]:
                return q
            e = self.envelope(q)
            return q if e is None else e[0] + e[1] * lift

        def press(q: Vector, i: int) -> Vector:
            if fixed[i]:
                return q
            e = self.envelope(q)
            if e is None:
                return q
            hit, n, d = e
            return q if (q - hit).dot(d) >= lift else hit + n * lift
        dense = [snap(p, i) for i, p in enumerate(dense)]
        for _ in range(passes):
            sm = [dense[0]] + [(dense[i - 1] + dense[i] * 2 + dense[i + 1]) / 4 for i in range(1, len(dense) - 1)] + [dense[-1]]
            dense = [press(p, i) for i, p in enumerate(sm)]
        nrm = []
        for p in dense:
            e = self.envelope(p)
            nrm.append(e[1] if e is not None and (p - e[0]).length < 0.03 else radial(p))
        for _ in range(4):                          # нормали — плавно вдоль пути: лента не скручивается на складках
            nrm = [nrm[0]] + [(nrm[i - 1] + nrm[i] * 2 + nrm[i + 1]).normalized() for i in range(1, len(nrm) - 1)] + [nrm[-1]]
        return dense, nrm


# ---------- детали ----------

def materials() -> dict:
    return {
        "cordura": kc.clay("Pack_Cordura", (0.20, 0.20, 0.17), 0.85),
        "webbing": kc.clay("Pack_Webbing", (0.12, 0.12, 0.10), 0.8),
        "plastic": kc.clay("Pack_Plastic", (0.04, 0.04, 0.04), 0.5),
        "mesh": kc.clay("Pack_Mesh", (0.08, 0.08, 0.08), 0.9),
        "metal": kc.clay("Pack_Metal", (0.30, 0.30, 0.30), 0.35),
        "velcro": kc.clay("Pack_Velcro", (0.06, 0.06, 0.05), 0.95),
        "molle": kc.clay("Pack_Molle", (0.12, 0.12, 0.10), 0.8),
    }


class Parts:
    """Сетки рюкзака по материалам."""

    def __init__(self):
        self.cordura, self.webbing, self.plastic, self.mesh = ak.Mesh(), ak.Mesh(), ak.Mesh(), ak.Mesh()
        self.metal, self.velcro, self.pads = ak.Mesh(), ak.Mesh(), ak.Mesh()
        self.molle = ak.Mesh()                         # ряды MOLLE: плоская тканая стропа с закрепками (свой материал)
        self.smooth: ak.Mesh | None = None             # ткань мешка до складок (та же топология, что cordura)

    def build(self, prefix: str, col: bpy.types.Collection, mats: dict) -> None:
        for name, mesh, mat in (("Bag", self.cordura, "cordura"), ("Padding", self.pads, "cordura"),
                                ("Webbing", self.webbing, "webbing"), ("Hardware", self.plastic, "plastic"),
                                ("Mesh", self.mesh, "mesh"), ("Metal", self.metal, "metal"),
                                ("Velcro", self.velcro, "velcro"), ("Molle", self.molle, "molle")):
            if mesh.faces:
                keys = {SMOOTH_KEY: self.smooth} if name == "Bag" and self.smooth else None
                obj = mesh.build(f"{prefix}_{name}", col, [mats[mat]], shape_keys=keys)
                if name == "Molle":
                    sharp_edges(obj, 60.0)


def sharp_edges(obj: bpy.types.Object, angle: float) -> None:
    """Острые кромки (угол граней больше angle): плоская стропа MOLLE со сглаживанием по рёбрам выглядела трубкой."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    lim = math.radians(angle)
    vals = [len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim for e in bm.edges]
    bm.free()
    attr = me.attributes.get("sharp_edge") or me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
    attr.data.foreach_set("value", vals)
    me.update()


def rib_between(a: Vector, b: Vector, n_a: Vector, n_b: Vector, k: int = 12) -> ak.RibbonFrame:
    pts = [a.lerp(b, i / k) for i in range(k + 1)]
    nrm = [n_a.lerp(n_b, i / k).normalized() for i in range(k + 1)]
    return ak.RibbonFrame(pts, nrm)


def rib_on(frame, uvs: list[tuple[float, float]], off: float, k: int = 10) -> ak.RibbonFrame:
    """Лента по стороне мешка через точки (u, v)."""
    pts, nrm = [], []
    for (u0, v0), (u1, v1) in zip(uvs, uvs[1:]):
        for i in range(k):
            u, v = u0 + (u1 - u0) * i / k, v0 + (v1 - v0) * i / k
            pts.append(frame.point(u, v, off))
            nrm.append(frame.normal(u, v))
    u, v = uvs[-1]
    pts.append(frame.point(u, v, off))
    nrm.append(frame.normal(u, v))
    return ak.RibbonFrame(pts, nrm)


def extend(rib: ak.RibbonFrame, p: Vector, n: Vector, k: int = 4) -> ak.RibbonFrame:
    """Лента дальше до точки p (переход с мешка на «хвост», клапан и т. п.)."""
    a, na = rib.pts[-1], rib.nrm[-1]
    pts = rib.pts + [a.lerp(p, i / k) for i in range(1, k + 1)]
    nrm = rib.nrm + [na.lerp(n, i / k).normalized() for i in range(1, k + 1)]
    return ak.RibbonFrame(pts, nrm)


def buckle_on(m: ak.Mesh, rib: ak.RibbonFrame, at: float, width: float, kind: str = "release", off: float = 0.004) -> None:
    p, tan, nn = rib._at(at)
    side = nn.cross(tan).normalized()
    c = p + nn * off
    if kind == "release":
        ak.side_release(m, c, side, tan, nn, width)
    else:
        ak.ladder_lock(m, c, side, tan, nn, width)


def buckle_box(rib: ak.RibbonFrame, at: float, width: float, kind: str, off: float
               ) -> tuple[Vector, Vector, Vector, Vector, float, float, float]:
    """Габарит пряжки buckle_on для продавливания ткани: центр, оси (поперёк, вдоль, от ткани), полуразмеры, дно."""
    p, tan, nn = rib._at(at)
    side = nn.cross(tan).normalized()
    c = p + nn * off
    if kind == "release":
        return c + tan * 0.007, side, tan, nn, (width + 0.010) / 2 + 0.0005, 0.0285, -0.0045
    return c, side, tan, nn, (width + 0.008) / 2 + 0.0005, 0.0125, -0.002


def shoulder_straps(P: Parts, body: Body, bag: Bag, inner: ProjFrame, side: dict, top_z: float, pad_w: float = 0.062,
                    pad_t: float = 0.013, sternum: bool = True, sternum_z: float = 1.37, daisy: bool = False,
                    tail_z: float | None = None) -> None:
    """Лямки S-формы: от верха спинки над серединой плеча вниз по груди (мягкая часть) и под мышку, дальше стропа под
    рукой к нижнему углу мешка с пряжкой-«лестницей». daisy — «гирлянда» стропы по лямке и два D-кольца."""
    ribs = []
    for sgn in (1.0, -1.0):
        a = inner.point(sgn * 0.052, top_z, -0.002)
        ctrl = [a, a + Vector((sgn * 0.03, -0.02, 0.03)),
                Vector((sgn * 0.128, 0.055, 1.515)), Vector((sgn * 0.135, -0.010, 1.548)),
                Vector((sgn * 0.138, -0.090, 1.495)), Vector((sgn * 0.142, -0.140, 1.400)),
                Vector((sgn * 0.155, -0.130, 1.285)), Vector((sgn * 0.172, -0.090, 1.205))]
        pts, nrm = body.lay(ctrl, pad_t / 2 + 0.004, free=2, passes=12)
        rib = ak.RibbonFrame(pts, nrm)
        ak.strap(P.pads, rib, pad_w, pad_t, step=0.005, taper=0.025)
        if daisy:
            ak.strap(P.webbing, rib, 0.020, 0.0018, base_off=pad_t, u0=rib.length * 0.30, u1=rib.length * 0.88, step=0.004)
            for f in (0.47, 0.72):
                p, tan, nn = rib._at(rib.length * f)
                ak.torus(P.plastic, p + nn * (pad_t + 0.004), nn, 0.011, 0.0022, seg=16, sides=6)
        ribs.append(rib)
        # стропа от низа мягкой части под рукой к нижнему углу мешка
        end = rib.point(rib.length - 0.01, 0.0, 0.0)
        cz = bag.z0 + 0.05 if tail_z is None else tail_z
        corner = side[sgn].point(bag.y_in(cz) + 0.03, cz, 0.002)
        tail_ctrl = [end, Vector((sgn * 0.190, -0.030, 1.135)), Vector((sgn * 0.185, 0.070, 1.070)), corner]
        tp, tn = body.lay(tail_ctrl, 0.004)
        tail = ak.RibbonFrame(tp, tn)
        ak.strap(P.webbing, tail, WEB, 0.0016, step=0.004)
        buckle_on(P.plastic, tail, 0.03, WEB, "ladder", 0.002)
    if not sternum:
        return
    ends = []
    for rib in ribs:
        best = min(range(len(rib.pts)), key=lambda i: abs(rib.pts[i].z - sternum_z) + (0 if rib.pts[i].y < -0.05 else 1))
        ends.append((rib.pts[best], rib.nrm[best]))
    (pa, na), (pb, nb) = ends
    ctrl = [pa + na * 0.010, (pa + pb) / 2 + ((na + nb) / 2).normalized() * 0.02, pb + nb * 0.010]
    sp, sn = body.lay(ctrl, 0.012, n_seg=10, passes=4)
    st = ak.RibbonFrame(sp, sn)
    ak.strap(P.webbing, st, 0.020, 0.0015, step=0.004)
    buckle_on(P.plastic, st, st.length / 2, 0.020, "release", 0.003)


def waist_strap(P: Parts, body: Body, z: float) -> None:
    """Поясная стропа: вокруг пояса поверх куртки (и брони), спереди фастекс."""
    band = ak.BandFrame(body.hull, z, WEB, -84.0, 264.0, 0.004, rows=4, samples=180, vsmooth=6, press=0.004)
    ak.padded_panel(P.webbing, band, ak.rounded_poly([(0.0, 0.0), (band.length, 0.0), (band.length, WEB), (0.0, WEB)],
                                                     [0.002] * 4), 0.0018, bulge=0.0, binding=0.0, step=0.006)
    front = ak.BandFrame(body.hull, z, WEB, -84.0, -96.0, 0.004, rows=2, samples=24)
    p = front.point(front.length / 2, WEB / 2, 0.005)
    nn = front.normal(front.length / 2, WEB / 2)
    tan = (front.point(front.length / 2 + 0.01, WEB / 2) - front.point(front.length / 2 - 0.01, WEB / 2)).normalized()
    ak.side_release(P.plastic, p, nn.cross(tan).normalized(), tan, nn, WEB)


def back_pads(P: Parts, inner: ProjFrame, bag: Bag, t: float = 0.018, length: float = 0.20, lumbar: bool = True,
              lumbar_mesh: bool = False) -> None:
    """Подушки спинки: две вертикальные под лопатки, внизу поясничная (у рейдового — сетка)."""
    zt = bag.z0 + bag.H - 0.07
    for sgn in (1.0, -1.0):
        x0, x1 = sorted((sgn * 0.030, sgn * 0.110))
        ak.padded_panel(P.pads, ak.OffsetFrame(inner, t / 2),
                        ak.rounded_poly([(x0, zt - length), (x1, zt - length), (x1, zt), (x0, zt)], [0.03] * 4), t,
                        bulge=0.004, binding=0.006, step=0.006)
    if lumbar_mesh:
        zb = bag.z0 + 0.04
        ak.padded_panel(P.mesh, ak.OffsetFrame(inner, 0.006),
                        ak.rounded_poly([(-0.05, zb), (0.05, zb), (0.05, zb + 0.20), (-0.05, zb + 0.20)], [0.01] * 4),
                        0.012, bulge=0.002, binding=0.004, step=0.006)
    elif lumbar:
        zb = bag.z0 + 0.04
        ak.padded_panel(P.pads, ak.OffsetFrame(inner, t / 2),
                        ak.rounded_poly([(-0.12, zb), (0.12, zb), (0.12, zb + 0.10), (-0.12, zb + 0.10)], [0.04] * 4), t,
                        bulge=0.004, binding=0.006, step=0.006)


def grab_handle(P: Parts, top: ProjFrame, bag: Bag) -> None:
    """Ручка — петля стропы сверху у спинки."""
    y = bag.y_in(bag.z0 + bag.H) + 0.03
    a = top.point(-0.04, y, 0.001)
    b = top.point(0.04, y, 0.001)
    pts = [a.lerp(b, k / 12) + Vector((0, 0, 0.022 * math.sin(math.pi * k / 12))) for k in range(13)]
    c0 = (a + b) / 2 - Vector((0, 0, 0.03))
    ak.strap(P.webbing, ak.RibbonFrame(pts, [(q - c0).normalized() for q in pts]), WEB, 0.003, step=0.004)


def zip_on(P: Parts, frame, uvs: list[tuple[float, float]], off: float, pull: float | None = 0.08) -> ak.RibbonFrame:
    rib = rib_on(frame, uvs, off)
    ak.zipper(P.webbing, P.plastic, rib, 0.0, pull_at=None if pull is None else rib.length * pull)
    return rib


def panel_face(poly: list[tuple[float, float]], half: float, bulge: float) -> Callable[[float, float], float]:
    """Высота лицевой стороны мягкой панели над её рамкой (как в padded_panel: толщина + выпуклость к середине)."""
    ring = ak.resample_closed(poly, 0.004)
    return lambda u, v: 2 * half + bulge * gm.smoothstep(ak.dist_to_poly((u, v), ring) / 0.05)


# ---------- рюкзаки ----------

def build_daypack(col, mats, body: Body, prefix: str) -> None:
    z0, H = 1.00, 0.47
    y_back = body.back_line(z0, z0 + H)
    gap = 0.018
    bag = Bag(z0, H, 0.150, 0.200, 0.165, lambda z: y_back(z) + gap, rb=0.035, rt_w=0.12, rt_d=0.06, bulge=0.014)
    P = Parts()
    bag.build(P.cordura)
    bvh = bvh_of(bag)
    out, inner, top = ProjFrame(bvh, "out"), ProjFrame(bvh, "in"), ProjFrame(bvh, "top")
    side = {1.0: ProjFrame(bvh, "side+"), -1.0: ProjFrame(bvh, "side-")}
    back_pads(P, inner, bag, gap)
    # главная молния «подковой» по лицевой стороне у краёв
    arch = [(-math.cos(math.pi * k / 24) * 0.118, z0 + H - 0.135 + math.sin(math.pi * k / 24) * 0.105) for k in range(25)]
    zip_on(P, out, [(-0.118, z0 + 0.20)] + arch + [(0.118, z0 + 0.20)], 0.0015, pull=0.42)
    # передний карман на молнии
    pk = ak.rounded_poly([(-0.110, z0 + 0.035), (0.110, z0 + 0.035), (0.105, z0 + 0.235), (-0.105, z0 + 0.235)],
                         [0.035, 0.035, 0.05, 0.05])
    ak.padded_panel(P.cordura, ak.OffsetFrame(out, 0.004), pk, 0.006, bulge=0.012, binding=0.007, step=0.006)
    arch = [(-0.085 + 0.17 * k / 16, z0 + 0.212 + 0.012 * math.sin(math.pi * k / 16)) for k in range(17)]
    zip_on(P, out, arch, 0.010, pull=0.15)
    # сетчатые боковые карманы с резинкой
    for sgn, fr in side.items():
        yi = bag.y_in(z0 + 0.1) + 0.02
        yo = yi + 0.15
        poly = ak.rounded_poly([(yi, z0 + 0.025), (yo, z0 + 0.025), (yo, z0 + 0.165), (yi, z0 + 0.165)], [0.01, 0.01, 0.004, 0.004])
        ak.padded_panel(P.mesh, ak.OffsetFrame(fr, 0.003), poly, 0.003, bulge=0.010, binding=0.0, step=0.006)
        rib = rib_on(fr, [(yi + 0.003, z0 + 0.158), (yo - 0.003, z0 + 0.158)], 0.010)
        ak.strap(P.webbing, rib, 0.012, 0.0025, step=0.004)
    grab_handle(P, top, bag)
    shoulder_straps(P, body, bag, inner, side, z0 + H - 0.05, sternum_z=1.37)
    P.build(prefix, col, mats)


def build_tourist(col, mats, body: Body, prefix: str) -> None:
    """По образцу владельца: штурмовой рюкзак с «бобровым хвостом» (скатка под ним убрана владельцем)."""
    z0, H = 0.99, 0.52
    y_back = body.back_line(z0, z0 + H)
    gap = 0.018
    y_in = lambda z: y_back(z) + gap               # noqa: E731
    bag = Bag(z0, H, 0.150, 0.200, 0.150, y_in, rb=0.04, rt_w=0.07, rt_d=0.05, n_front=3.0, bulge=0.008, hw1=0.118)
    P = Parts()
    bag.build(P.cordura)
    bvh = bvh_of(bag)
    out, inner, top, bot = ProjFrame(bvh, "out"), ProjFrame(bvh, "in"), ProjFrame(bvh, "top"), ProjFrame(bvh, "bot")
    side = {1.0: ProjFrame(bvh, "side+"), -1.0: ProjFrame(bvh, "side-")}
    back_pads(P, inner, bag, gap)
    grab_handle(P, top, bag)
    ym = y_in(z0 + H) + 0.065
    zip_on(P, top, [(-0.09, ym), (0.09, ym)], 0.0015, pull=0.8)          # молния основного отделения сверху

    # скатки под «хвостом» нет (владелец 2026-10-22: «жёлтую фигнюшку сзади полностью убрать») — хвост лежит на мешке
    bt = out

    # «хвост»: вверху уже, ряд стропы и полоса липучки
    bt_off, bt_t = 0.006, 0.007
    tail = ak.rounded_poly([(-0.125, z0 + 0.035), (0.125, z0 + 0.035), (0.125, z0 + 0.30), (0.078, z0 + H - 0.05),
                            (-0.078, z0 + H - 0.05), (-0.125, z0 + 0.30)], [0.03, 0.03, 0.05, 0.02, 0.02, 0.05])
    ak.padded_panel(P.cordura, ak.OffsetFrame(bt, bt_off), tail, bt_t, bulge=0.0, binding=0.008, step=0.006)
    face0 = bt_off + bt_t / 2
    ak.webbing_rows(P.molle, ak.OffsetFrame(bt, face0), -0.055, 0.055, [z0 + H - 0.095], 0.0005)
    ak.padded_panel(P.velcro, ak.OffsetFrame(bt, face0 + 0.0009),
                    ak.rounded_poly([(-0.07, z0 + H - 0.165), (0.07, z0 + H - 0.165), (0.07, z0 + H - 0.13),
                                     (-0.07, z0 + H - 0.13)], [0.004] * 4), 0.0016, bulge=0.0, binding=0.0, step=0.004)
    # карман внизу «хвоста»: на нём квадрат липучки, клапан откинут «козырьком»
    pk_t = 0.040
    pocket = ak.rounded_poly([(-0.108, z0 + 0.05), (0.108, z0 + 0.05), (0.108, z0 + 0.245), (-0.108, z0 + 0.245)], [0.03] * 4)
    ak.padded_panel(P.cordura, ak.OffsetFrame(bt, face0 + pk_t / 2), pocket, pk_t, bulge=0.0, binding=0.008, step=0.006)
    pface = face0 + pk_t
    ak.padded_panel(P.velcro, ak.OffsetFrame(bt, pface + 0.0009),
                    ak.rounded_poly([(-0.06, z0 + 0.07), (0.06, z0 + 0.07), (0.06, z0 + 0.19), (-0.06, z0 + 0.19)],
                                    [0.006] * 4), 0.0016, bulge=0.0, binding=0.0, step=0.004)
    flap_top, flap_bot = z0 + 0.290, z0 + 0.212

    class Flap:
        """Клапан-«козырёк»: от шва вверху выгибается наружу над карманом и к краю провисает вниз (мягкая ткань)."""

        def _t(self, v: float) -> float:
            return max(0.0, min(1.0, (flap_top - v) / (flap_top - flap_bot)))

        def normal(self, u: float, v: float) -> Vector:
            t = self._t(v)
            n = bt.normal(u, v - 0.03 * t * t)
            return (n + Vector((0, 0, 0.9 * t))).normalized()

        def point(self, u: float, v: float, off: float = 0.0) -> Vector:
            t = self._t(v)
            lift = face0 + 0.003 + (pk_t + 0.022) * math.sin(math.pi / 2 * min(1.0, t * 1.25))
            return bt.point(u, v - 0.03 * t * t, lift) + self.normal(u, v) * off
    ak.padded_panel(P.cordura, Flap(),
                    ak.rounded_poly([(-0.113, flap_bot), (0.113, flap_bot), (0.113, flap_top), (-0.113, flap_top)],
                                    [0.02, 0.02, 0.005, 0.005]), 0.005, bulge=0.0, binding=0.006, step=0.006)
    # стропы «хвоста» с фастексами: сверху через верх, по бокам на середине, снизу от дна
    for sgn in (1.0, -1.0):
        x = sgn * 0.068
        y_front_top = out.point(x, z0 + H - 0.035).y
        r = rib_on(top, [(x, y_in(z0 + H) + 0.025), (x, y_front_top - 0.012)], 0.003, k=14)
        r = extend(r, bt.point(x, z0 + H - 0.058, face0 + 0.002), bt.normal(x, z0 + H - 0.058))
        ak.strap(P.webbing, r, 0.020, 0.0016, step=0.004)
        buckle_on(P.plastic, r, r.length - 0.05, 0.020, "release", 0.004)
        zs = z0 + 0.30
        _, d_s, yi_s = bag.section(zs - z0)
        r = rib_on(side[sgn], [(yi_s + 0.03, zs), (yi_s + d_s - 0.012, zs)], 0.003, k=14)
        r = extend(r, bt.point(sgn * 0.121, zs, face0 + 0.002), bt.normal(sgn * 0.121, zs))
        ak.strap(P.webbing, r, 0.020, 0.0016, step=0.004)
        buckle_on(P.plastic, r, r.length - 0.04, 0.020, "release", 0.004)
        r = rib_on(bot, [(sgn * 0.10, y_in(z0) + 0.08), (sgn * 0.10, y_in(z0) + 0.14)], 0.003, k=10)
        r = extend(r, bt.point(sgn * 0.108, z0 + 0.045, face0 + 0.002), bt.normal(sgn * 0.108, z0 + 0.045))
        ak.strap(P.webbing, r, 0.020, 0.0016, step=0.004)
        buckle_on(P.plastic, r, r.length - 0.035, 0.020, "release", 0.004)
    # бока: подсумок на молнии у спинки и сетчатый карман со шнуром впереди
    for sgn, fr in side.items():
        _, d_s, yi_s = bag.section(0.15)
        ya, yb = yi_s + 0.022, yi_s + 0.107
        pz0, pz1 = z0 + 0.05, z0 + 0.31
        ak.padded_panel(P.cordura, ak.OffsetFrame(fr, 0.025),
                        ak.rounded_poly([(ya, pz0), (yb, pz0), (yb, pz1), (ya, pz1)], [0.02, 0.02, 0.025, 0.025]),
                        0.050, bulge=0.006, binding=0.007, step=0.007)
        zr = zip_on(P, ak.OffsetFrame(fr, 0.050), [(ya + 0.012, pz1 - 0.013), (yb - 0.012, pz1 - 0.013)], 0.002, pull=0.85)
        p, tan, nn = zr._at(zr.length * 0.85)
        ak.tube(P.webbing, [p + nn * 0.004, p + nn * 0.010 + Vector((0, 0, 0.012)), p + nn * 0.008 + Vector((0, 0, 0.03))],
                0.0018, sides=6)
        ma, mb = yb + 0.004, yi_s + d_s - 0.006
        poly = ak.rounded_poly([(ma, z0 + 0.03), (mb, z0 + 0.03), (mb, z0 + 0.30), (ma, z0 + 0.30)], [0.01, 0.02, 0.005, 0.005])
        ak.padded_panel(P.mesh, ak.OffsetFrame(fr, 0.003), poly, 0.003, bulge=0.022, binding=0.0, step=0.006)
        cord = rib_on(fr, [(ma + 0.003, z0 + 0.293), (mb - 0.003, z0 + 0.293)], 0.007)
        ak.tube(P.webbing, cord.pts, 0.0022, sides=6)
        p, tan, nn = cord._at(cord.length * 0.8)
        ak.cord_lock(P.plastic, p + nn * 0.006, nn.cross(tan).normalized(), tan, nn)
    shoulder_straps(P, body, bag, inner, side, z0 + H - 0.05, sternum=False, daisy=True)
    waist_strap(P, body, 1.00)
    P.build(prefix, col, mats)


def build_raid(col, mats, body: Body, prefix: str) -> None:
    """По образцу владельца: большой армейский рюкзак с клапаном, «ушами» и нижним отсеком. Ткань мятая
    (владелец 2026-10-22: «слишком примитивно, не хватает реалистичности»): гладкие формы — опора, по ним
    складки сжатия и бугры содержимого (soft_goods), клапан провисает спереди; стяжки натянуты поверх смятой
    ткани и перетягивают карманы, ткань под ними продавлена — сквозь неё стропа не проходит."""
    z0, H = 0.93, 0.58
    y_back = body.back_line(z0, z0 + H)
    gap = 0.020
    y_in = lambda z: y_back(z) + gap               # noqa: E731
    P = Parts()
    # ---- гладкие формы ----
    bag = Bag(z0, H, 0.165, 0.270, 0.240, y_in, rb=0.05, rt_w=0.05, rt_d=0.05, n_front=5.0, n_back=10.0,
              bulge=0.012, pinch=(0.14, 0.012, 0.010), seg=240, row_step=0.0045)
    m_bag = ak.Mesh()
    bag.build(m_bag)
    bvh_s = sg.bvh(m_bag)
    out_s, inner, bot_s = ProjFrame(bvh_s, "out"), ProjFrame(bvh_s, "in"), ProjFrame(bvh_s, "bot")
    side_s = {1.0: ProjFrame(bvh_s, "side+"), -1.0: ProjFrame(bvh_s, "side-")}
    lz0, LH = z0 + H - 0.075, 0.155
    y_top = y_in(z0 + H)
    lid = Bag(lz0, LH, 0.172, 0.300, 0.300, lambda z: y_top - 0.004, rb=0.055, rt_w=0.06, rt_d=0.06, n_front=3.5,
              n_back=6.0, bulge=0.010, seg=240, row_step=0.0045)
    m_lid = ak.Mesh()
    lid.build(m_lid)
    # клапан провисает: чем дальше от спинки, тем ниже, посередине сильнее
    y_mid = y_top + 0.15

    def droop(x: float) -> float:
        return 0.020 * max(0.0, 1 - (x / 0.19) ** 2)
    m_lid.verts = [p - Vector((0.0, 0.0, droop(p.x) * gm.smoothstep((p.y - y_mid) / 0.15))) for p in m_lid.verts]
    lbvh_s = sg.bvh(m_lid)
    lid_out_s, lid_top_s = ProjFrame(lbvh_s, "out"), ProjFrame(lbvh_s, "top")
    fp_t = 0.030
    fz0, fz1 = z0 + 0.17, z0 + H - 0.09
    m_fp = ak.Mesh()
    ak.padded_panel(m_fp, ak.OffsetFrame(out_s, fp_t / 2),
                    ak.rounded_poly([(-0.115, fz0), (0.115, fz0), (0.115, fz1), (-0.115, fz1)], [0.02] * 4), fp_t,
                    bulge=0.004, binding=0.008, step=0.0045)
    pk_t, pk_b = 0.095, 0.012
    ya = y_in(z0 + 0.35) + 0.035
    yb, pz0, pz1 = ya + 0.20, z0 + 0.19, z0 + 0.50
    ym = (ya + yb) / 2
    zs_side = (pz0 + 0.085, pz0 + 0.215)
    ears = {}
    for sgn, fr in side_s.items():
        ears[sgn] = ak.Mesh()
        ak.padded_panel(ears[sgn], ak.OffsetFrame(fr, pk_t / 2),
                        ak.rounded_poly([(ya, pz0), (yb, pz0), (yb, pz1), (ya, pz1)], [0.05] * 4),
                        pk_t, bulge=pk_b, binding=0.009, step=0.004)

    # ---- смятая ткань (гладкие формы запомнены — ключ формы «Без складок») ----
    smooth = {id(m): list(m.verts) for m in (m_bag, m_lid, m_fp, *ears.values())}

    def rect_out(a: float, b: float, a0: float, a1: float, b0: float, b1: float) -> float:
        return math.hypot(max(a0 - a, 0.0, a - a1), max(b0 - b, 0.0, b - b1))
    bag_lumps = sg.lumps(0.11, 0.008, 1.0)
    bag_folds = sg.folds(Vector((0, 0, 1)), 0.07, 0.012, 2.0)
    bag_wr = sg.folds(Vector((0.6, 0.3, 0.8)), 0.028, 0.003, 21.0, cover=0.5)
    low_folds = sg.folds(Vector((0.15, 0, 1)), 0.05, 0.014, 3.0, cover=0.7)
    bag_cr = sg.creases(0.07, 0.006, 22.0, stretch=Vector((0.6, 0.6, 1.4)))

    def bag_field(p: Vector, n: Vector) -> float:
        free = 1.0 - gm.smoothstep((-n.y - 0.2) / 0.4)              # спинка прижата к спине — гладкая
        if n.y > 0.3:                                               # под передней панелью ткани не видно
            free *= gm.smoothstep(rect_out(p.x, p.z, -0.115, 0.115, fz0, fz1) / 0.025)
        if abs(n.x) > 0.3:                                          # и под «ушами»
            free *= gm.smoothstep(rect_out(p.y, p.z, ya, yb, pz0, pz1) / 0.025)
        low = gm.smoothstep((z0 + 0.17 - p.z) / 0.05)              # нижний отсек — складки крупнее
        flat = 1.0 - 0.85 * gm.smoothstep((-n.z - 0.4) / 0.3)       # дно стоит на грузе — только бугры
        return free * (bag_lumps(p) + flat * (bag_folds(p) * (1.0 - low) + low_folds(p) * low + bag_wr(p) + bag_cr(p)))
    sg.displace(m_bag, bag_field)
    lid_lumps = sg.lumps(0.08, 0.006, 4.0)
    lid_drape = sg.folds(Vector((1, 0, 0.25)), 0.06, 0.014, 5.0, cover=0.65)
    lid_top_f = sg.folds(Vector((1, 0.7, 0)), 0.05, 0.008, 6.0)
    lid_cr = sg.creases(0.06, 0.006, 23.0, stretch=Vector((1.3, 1.0, 0.6)))

    def lid_field(p: Vector, n: Vector) -> float:
        top = gm.smoothstep((n.z - 0.4) / 0.4)
        under = gm.smoothstep((-n.z - 0.4) / 0.4)
        # под пришитыми рядами MOLLE ткань двойная и ровнее
        sewn = gm.smoothstep((0.125 - abs(p.x)) / 0.02) * (top * gm.smoothstep((p.y - y_top - 0.06) / 0.02)
                                                           + gm.smoothstep((n.y - 0.5) / 0.3))
        mild = 1.0 - 0.7 * sewn
        return (1.0 - under) * (lid_lumps(p) + mild * (top * lid_top_f(p) + (1.0 - top) * lid_drape(p) + lid_cr(p)))
    sg.displace(m_lid, lid_field)
    fp_lumps, fp_folds = sg.lumps(0.09, 0.004, 8.0), sg.folds(Vector((0, 0, 1)), 0.07, 0.003, 9.0)
    sg.displace(m_fp, lambda p, n: gm.smoothstep((n.y + 0.2) / 0.6) * (fp_lumps(p) + fp_folds(p)))
    for sgn, m_e in ears.items():
        e_lumps = sg.lumps(0.06, 0.007, 10.0 + sgn)
        e_pleats = sg.folds(Vector((0, 1, 0.2)), 0.05, 0.010, 12.0 + sgn, cover=0.6)
        e_cr = sg.creases(0.05, 0.005, 24.0 + sgn, stretch=Vector((1.0, 1.3, 0.6)))

        def ear_field(p: Vector, n: Vector, sgn=sgn, e_lumps=e_lumps, e_pleats=e_pleats, e_cr=e_cr) -> float:
            face = gm.smoothstep((n.x * sgn + 0.3) / 0.6)
            near = max(math.exp(-abs(p.z - z) / 0.035) for z in zs_side)     # у стяжек ткань собирается
            return face * (e_lumps(p) + e_pleats(p) * (0.6 + 1.2 * near) + e_cr(p))
        sg.displace(m_e, ear_field)
    bvh_bag = sg.bvh(m_bag)
    side_d = {sgn: sg.SurfFrame(fr, bvh_bag) for sgn, fr in side_s.items()}
    # клапаны «ушей» лежат на смятом кармане
    flaps = {}
    for sgn, fr in side_s.items():
        flaps[sgn] = ak.Mesh()
        ak.padded_panel(flaps[sgn], ak.OffsetFrame(sg.SurfFrame(fr, sg.bvh(ears[sgn]), reach=0.25), 0.004),
                        ak.rounded_poly([(ya + 0.004, pz1 - 0.004), (yb - 0.004, pz1 - 0.004), (yb - 0.004, pz1 - 0.065),
                                         (ym, pz1 - 0.098), (ya + 0.004, pz1 - 0.065)], [0.02, 0.02, 0.01, 0.01, 0.01]),
                        0.006, bulge=0.0, binding=0.006, step=0.005)
        smooth[id(flaps[sgn])] = list(flaps[sgn].verts)
    # шов нижнего отсека — валик по смятой ткани
    ring = bag.ring(0.14)
    cy = sum(p.y for p in ring) / len(ring)
    m_bead = ak.Mesh()
    bead = []
    for p in ring:
        n = Vector((p.x, p.y - cy, 0.0)).normalized()
        bead.append(sg.surface_point(bvh_bag, p, n) + n * 0.002)
    ak.tube(m_bead, bead + [bead[0]], 0.003, sides=6)
    smooth[id(m_bead)] = list(m_bead.verts)

    # ---- стяжки «ушей»: натянуты поверх кармана и клапана, ткань под ними продавлена ----
    pressed: list[tuple[sg.Path, list[ak.Mesh], float]] = []
    boxes: list[tuple[tuple, list[ak.Mesh]]] = []
    flap_ids = {id(m) for m in flaps.values()}

    def thick(m: ak.Mesh) -> float:
        return 0.006 if id(m) in flap_ids else 0.0

    def buckle(rib: ak.RibbonFrame, at: float, width: float, kind: str, off: float, meshes: list[ak.Mesh]) -> None:
        buckle_on(P.plastic, rib, at, width, kind, off)
        boxes.append((buckle_box(rib, at, width, kind, off), meshes))
    # пряжки как у образца: на нижней стяжке фастекс и регулятор, на верхней (её пересекает стропа клапана) —
    # только регулятор у переднего края, фастекс — на стропе клапана
    side_buckles = ([("release", ym - 0.012), ("ladder", ym + 0.040)], [("ladder", ym + 0.035)])
    for sgn in (1.0, -1.0):
        ax = Vector((sgn, 0.0, 0.0))
        cloth = sg.bvh(m_bag, ears[sgn], flaps[sgn])
        m_side = ak.Mesh()
        for zs, kinds in zip(zs_side, side_buckles):
            _, d_s, yi_s = bag.section(zs - z0)
            path = sg.planar_path(cloth, lambda s, zs=zs: Vector((0.0, s, zs)), ax, Vector((0, 1, 0)),
                                  yi_s + 0.008, yi_s + d_s - 0.008, 0.010, sink=0.004)
            meshes = [m_bag, ears[sgn], flaps[sgn]]
            for m in meshes:
                sg.press(m, path, rim=0.012, bulge=0.0015, thick=thick(m))
            pressed.append((path, meshes, 0.012))
            rib = path.rib(0.0003)
            ak.strap(m_side, rib, 0.020, 0.0016, step=0.004)
            for kind, y_b in kinds:
                buckle(rib, path.length_at(y_b), 0.020, kind, 0.004 if kind == "release" else 0.002, meshes)
        # стропа клапана: от его угла вниз по карману, поверх стяжек
        path = sg.planar_path(sg.bvh(ears[sgn], flaps[sgn], m_side), lambda s: Vector((0.0, ym, s)), ax,
                              Vector((0, 0, 1)), pz1 - 0.085, pz1 - 0.165, 0.010, sink=0.002)
        meshes = [ears[sgn], flaps[sgn]]
        for m in meshes:
            sg.press(m, path, rim=0.010, bulge=0.001, thick=thick(m))
        pressed.append((path, meshes, 0.010))
        rib = path.rib(0.0003)
        ak.strap(m_side, rib, 0.020, 0.0016, step=0.004)
        buckle(rib, path.length_at(pz1 - 0.140), 0.020, "release", 0.004, meshes)
        sg.merge(P.webbing, m_side)
    # ---- две длинные стропы от клапана до дна: натянуты через провисший клапан, валик и смятый низ ----
    cloth = sg.bvh(m_bag, m_lid, m_fp, m_bead)
    y_ref = y_in(z0)
    for sgn in (1.0, -1.0):
        x = sgn * 0.135
        path = sg.planar_path(cloth, lambda s, x=x: Vector((x, y_ref, s)), Vector((0, 1, 0)), Vector((0, 0, 1)),
                              lz0 + LH - 0.03, z0 + 0.015, WEB / 2, reach=0.8)
        for m in (m_bag, m_lid):
            sg.press(m, path, rim=0.010, bulge=0.0015)
        pressed.append((path, [m_bag, m_lid], 0.010))
        rib = path.rib(0.0003)
        ak.strap(P.webbing, rib, WEB, 0.0018, step=0.004)
        for z_b in (lz0 - 0.035, z0 + 0.09):
            buckle(rib, path.length_at(z_b), WEB, "ladder", 0.002, [m_bag, m_lid])
    # в конце ещё раз продавить без выдавливания: край одной стропы не поднимает ткань под другой и под пряжкой
    for path, meshes, rim in pressed:
        for m in meshes:
            sg.press(m, path, rim=rim, thick=thick(m))
    for box, meshes in boxes:
        for m in meshes:
            sg.press_box(m, *box, thick=thick(m))

    # ---- детали по смятой ткани ----
    bvh_bag, bvh_lid = sg.bvh(m_bag), sg.bvh(m_lid)
    out_d, bot_d = sg.SurfFrame(out_s, bvh_bag), sg.SurfFrame(bot_s, bvh_bag)
    lid_out_d = ShiftFrame(sg.SurfFrame(lid_out_s, bvh_lid), droop)
    lid_top_d = sg.SurfFrame(lid_top_s, bvh_lid)
    back_pads(P, inner, bag, gap, length=0.34, lumbar_mesh=True)
    ak.webbing_rows(P.molle, lid_out_d, -0.11, 0.11, [lz0 + 0.03 + k * MOLLE_PITCH for k in range(3)], 0.0005)
    ak.webbing_rows(P.molle, lid_top_d, -0.11, 0.11, [y_top + 0.07 + k * MOLLE_PITCH for k in range(4)], 0.0005)
    grab_handle(P, lid_top_d, lid)
    n_rows = int((fz1 - fz0 - 0.06) / MOLLE_PITCH) + 1
    ak.webbing_rows(P.molle, sg.SurfFrame(out_s, sg.bvh(m_fp), reach=0.1), -0.095, 0.095,
                    [fz0 + 0.03 + k * MOLLE_PITCH for k in range(n_rows)], 0.0005)
    zip_on(P, out_d, [(-0.112, z0 + 0.155), (0.112, z0 + 0.155)], 0.0015, pull=0.1)
    for sx in (-0.09, 0.09):
        for dy in (0.07, 0.19):
            r = rib_on(bot_d, [(sx - 0.03, y_in(z0) + dy), (sx + 0.03, y_in(z0) + dy)], 0.002)
            ak.strap(P.webbing, r, WEB, 0.003, step=0.004)
    shoulder_straps(P, body, bag, inner, side_d, 1.47, sternum=False)
    P.smooth = ak.Mesh()
    for m in (m_bag, m_lid, m_fp, m_bead, *ears.values(), *flaps.values()):
        sg.merge(P.cordura, m)
        flat = ak.Mesh()
        flat.verts, flat.faces, flat.uvs, flat.mats = smooth[id(m)], m.faces, m.uvs, m.mats
        sg.merge(P.smooth, flat)
    cloth = sg.solid(m_bag, m_lid, m_fp, *ears.values(), *flaps.values())
    bw, ww, where_w = sg.check_inside(cloth, P.webbing.verts)
    bp, wp, where_p = sg.check_inside(cloth, P.plastic.verts + P.molle.verts)
    kc.log(f"    {prefix}: внутри ткани — стропы {bw} верш. (до {ww * 1000:.1f} мм), "
           f"фурнитура и MOLLE {bp} (до {wp * 1000:.1f} мм)")
    for where in (where_w, where_p):
        for key, cnt in sorted(where.items(), key=lambda kv: -kv[1])[:8]:
            kc.log(f"      где: {key} — {cnt}")
    P.build(prefix, col, mats)


PACKS = (("Daypack", build_daypack, "городской"), ("Tourist", build_tourist, "туристический"),
         ("Raid", build_raid, "рейдовый"))


def fit_col(pack: str, label: str) -> str:
    return f"07_{pack} · {label}"


def show(pack: str | None, fit: str) -> None:
    """Видны один рюкзак в одной посадке и броня этой посадки."""
    vl = bpy.context.view_layer.layer_collection
    for key, _, armor, _ in FITS:
        if armor and armor in vl.children:
            vl.children[armor].hide_viewport = key != fit
            bpy.data.collections[armor].hide_render = key != fit
    for name, _, _ in PACKS:
        parent = f"07_Backpack_{name}"
        if parent not in vl.children:
            continue
        lp = vl.children[parent]
        lp.hide_viewport = name != pack
        bpy.data.collections[parent].hide_render = name != pack
        for key, label, _, _ in FITS:
            cn = fit_col(name, label)
            if cn in lp.children:
                lp.children[cn].hide_viewport = key != fit
                bpy.data.collections[cn].hide_render = key != fit


def render() -> None:
    import numpy as np
    kc.studio()
    kc.gpu_cycles(96)
    scene = bpy.context.scene
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    out = kc.WORK / "previews"
    cam34 = kc.camera("C_b_back34", (-1.15, 1.55, 1.55), (0.0, 0.10, 1.22), 50)
    cam_side = kc.camera("C_b_side", (1.75, 0.20, 1.35), (0.0, 0.10, 1.22), 50)
    paths = []
    for name, _, _ in PACKS:
        show(name, "none")
        p = out / f"backpack_{name.lower()}_back34.png"
        kc.render(cam34, p, (560, 680), 96)
        paths.append(p)
        for key, _, _, _ in FITS:
            show(name, key)
            p = out / f"backpack_{name.lower()}_side_{key}.png"
            kc.render(cam_side, p, (560, 680), 96)
            paths.append(p)
    imgs = [bpy.data.images.load(str(p)) for p in paths]
    w, h = imgs[0].size
    cols = 1 + len(FITS)
    grid = np.zeros((h * len(PACKS), w * cols, 4), np.float32)
    for k, im in enumerate(imgs):
        r, c = divmod(k, cols)
        px = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(px)
        grid[(len(PACKS) - 1 - r) * h:(len(PACKS) - r) * h, c * w:(c + 1) * w] = px.reshape(h, w, 4)
    res = bpy.data.images.new("backpacks_grid", w * cols, h * len(PACKS), alpha=False)
    res.pixels.foreach_set(grid.ravel())
    s = scene.render.image_settings
    s.file_format = "JPEG"
    s.quality = 90
    s.color_mode = "RGB"
    res.save_render(str(out / f"backpacks_{VERSION}.jpg"))


def closeups(name: str, fit: str) -> None:
    """Пробные кадры формы: 3/4 сзади, «ухо» вблизи (как на снимке владельца), сбоку."""
    kc.studio()
    show(name, fit)
    out = kc.WORK / "previews"
    for tag, pos, tgt in (("back34", (-0.95, 1.30, 1.50), (0.0, 0.18, 1.22)),
                          ("ear", (-0.80, 0.80, 1.38), (-0.24, 0.26, 1.26)),
                          ("side", (1.75, 0.20, 1.35), (0.0, 0.10, 1.22))):
        kc.render(kc.camera("C_c_" + tag, pos, tgt, 50), out / f"{name.lower()}_{fit}_{tag}.png", (900, 1000), 64)


README = (
    "Рюкзаки трёх видов — ФОРМА {ver} на согласование (нейтральный материал), на мародёре v03 и поверх каждой брони.\n"
    "Данные не менялись: городской (bp_daypack, 30 ячеек), туристический (bp_tourist, 45), рейдовый (bp_raid, 60).\n"
    "Туристический и рейдовый — по образцам владельца (Sketchfab), городской — прежний, понравился.\n"
    "Коллекции: 07_Backpack_<вид> → внутри четыре посадки «07_<вид> · без брони / бомжовская / средняя / крутая»;\n"
    "брони — 06_Armor_Poor / _Mid / _Top. Смотреть: включить (глаз) один рюкзак, одну его посадку и ту же броню\n"
    "(для «без брони» все 06_Armor_* выключить). Спинка отходит на толщину брони, лямки лежат поверх неё —\n"
    "в игре вариант рюкзака выбирается по надетой броне. Смотреть в Rendered (Cycles).\n"
    "У рейдового ткань мятая: на объекте мешка (Raid*_Bag) ключ формы «Без складок» = 1 — гладкая форма для сравнения.\n"
    "Скрипт: tools/npc_kit/backpacks.py (мятая ткань и стропы поверх неё — tools/npc_kit/soft_goods.py).\n")


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / f"armor_fitting_{kc.VERSION}.blend"))
    mats = materials()
    only = next((a.split("=", 1)[1] for a in args if a.startswith("only=")), None)
    only_fit = next((a.split("=", 1)[1] for a in args if a.startswith("fit=")), None)
    bodies = {key: Body(armor) for key, _, armor, _ in FITS if only_fit in (None, key)}
    for name, fn, label in PACKS:
        if only and name != only:
            continue
        parent = kc.collection(f"07_Backpack_{name}")
        for key, fit_label, _, suffix in FITS:
            if key not in bodies:
                continue
            col = kc.collection(fit_col(name, fit_label), parent)
            fn(col, mats, bodies[key], name + suffix)
            kc.log(f"  рюкзак {label} · {fit_label}: {sum(len(o.data.polygons) for o in col.objects)} граней")
    OUT.mkdir(parents=True, exist_ok=True)
    if only or only_fit:                    # проба — в отдельный файл, собранный не трогаем
        show(only or "Daypack", only_fit or "none")
        kc.save(OUT / "backpacks_test.blend")
        if "closeups" in args:
            closeups(only or "Raid", only_fit or "none")
        return
    show("Daypack", "none")
    kc.save(OUT / "backpacks.blend")
    if "render" in args:
        render()
        show("Daypack", "none")
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        import armor_mid as am
        show("Daypack", "none")
        am.deliver(Path(dest), f"Рюкзаки_{VERSION}_форма.blend", README.format(ver=VERSION), focus_z=1.25, near=0.75)


if __name__ == "__main__":
    main()
