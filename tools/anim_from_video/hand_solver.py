"""Решатель кисти FPS-рук (внутри Blender): анатомия суставов и смыкание пальцев на предмете по касанию кожи.

Опыт «анимация рук по видео» (владелец 2026-11-06: «пальцы то изломаны, то пересечения»). Причины в клипах были две:
  1. изломы — сустав повёрнут не вокруг своей оси (закручен, разведён у средних фаланг) или концевая фаланга согнута
     при прямой средней;
  2. пересечения — палец согнут «на глаз», без проверки, где поверхность.
Здесь: поза пальца сводится к сгибу и (только у основания) разводу, без кручения; концевая — вслед за средней; дальше
пальцы смыкаются от основания к кончику, пока кожа (вершины сетки рук своей кости) не коснётся оружия или магазина.

Ось сгиба у рига FPSArms (мастер v14) — локальная X кости, сгиб к ладони — плюс (проверено по хвату магазина); у
большого — локальная Z, его поза не правится.
Кожа — вершины сетки рук с весом кости > 0.5, движутся с костью жёстко (для проверки касания этого хватает).
"""
from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

FINGERS = ('thumb', 'f_index', 'f_middle', 'f_ring', 'f_pinky')
# пределы сгиба, градусы (минус — разгиб): основание, средняя, концевая
FLEX = {'f': ((-15.0, 90.0), (0.0, 105.0), (0.0, 80.0)), 'thumb': ((-30.0, 55.0), (-10.0, 65.0), (-10.0, 85.0))}
SPREAD = {'f': 15.0, 'thumb': 40.0}        # развод — только у основания
DIP_FROM_PIP = (0.0, 1.05)                # концевая: не больше 1.05 сгиба средней (+15°) — без сгиба средней она не гнётся;
                                          # прямая при согнутой средней бывает (кончик упёрся);
                                          # иначе сгиб делится между ними с той же суммой
CONTACT = 0.0015                          # касание: кожа (перчатка мягкая) входит не глубже 1.5 мм
STEP = math.radians(1.5)


def bones(rig, side, finger):
    return [rig.pose.bones[f'{finger}.{j:02d}.{side}'] for j in (1, 2, 3)]


# ------------------------------------------------------------------ анатомия
def swing(m3):
    """Поворот кости (matrix_basis 3×3) → (сгиб, развод, кручение) рад: R = Rx(сгиб) · Rz(развод) · Ry(кручение), ось
    кости — Y. Сгиб — через atan2 (у пальцев он бывает больше 90°), развод — малый, через asin."""
    d = m3 @ Vector((0.0, 1.0, 0.0))
    spread = math.asin(max(-1.0, min(1.0, -d.x)))
    flex = math.atan2(d.z, d.y)
    sw = Matrix.Rotation(flex, 3, 'X') @ Matrix.Rotation(spread, 3, 'Z')
    tw = sw.transposed() @ m3
    twist = math.atan2(tw[0][2], tw[0][0])
    return flex, spread, twist


def compose(flex, spread, twist=0.0):
    return (Matrix.Rotation(flex, 3, 'X') @ Matrix.Rotation(spread, 3, 'Z') @ Matrix.Rotation(twist, 3, 'Y')).to_4x4()


def read(rig, side, finger):
    return [swing(pb.matrix_basis.to_3x3()) for pb in bones(rig, side, finger)]


def anatomical(vals, finger):
    """[(сгиб, развод, кручение)] × 3 → то же в пределах сустава. Изменения — в градусах для отчёта."""
    kind = 'thumb' if finger == 'thumb' else 'f'
    if kind == 'thumb':
        # большой у рига FPSArms гнётся вокруг локальной Z (X ведёт его поперёк ладони) — правило «сгиб = X» к нему не
        # подходит: его «боковой изгиб» в позах и есть сгиб. Как есть.
        return [tuple(v) for v in vals]
    out = []
    for j, (fl, sp, tw) in enumerate(vals):
        lo, hi = FLEX[kind][j]
        fl2 = max(math.radians(lo), min(math.radians(hi), fl))
        sp2 = max(-math.radians(SPREAD[kind]), min(math.radians(SPREAD[kind]), sp)) if j == 0 else 0.0
        tw2 = 0.0
        out.append([fl2, sp2, tw2])
    if kind == 'f':
        # концевая — вслед за средней: если сгиб пальца весь в одной из них, он делится между ними, сумма сохраняется
        # (кончик почти на месте; срезать нельзя — палец выпрямится)
        lo_k, hi_k = DIP_FROM_PIP
        add = math.radians(15)
        pip, dip = max(out[1][0], 0.0), max(out[2][0], 0.0)
        total = pip + dip
        if dip > hi_k * pip + add:
            pip = max(0.0, (total - add) / (1.0 + hi_k))
            dip = total - pip
        elif dip < lo_k * pip:
            pip = total / (1.0 + lo_k)
            dip = total - pip
        pip = min(pip, math.radians(FLEX['f'][1][1]))
        dip = min(dip, math.radians(FLEX['f'][2][1]))
        out[1][0], out[2][0] = pip, dip
    return [tuple(v) for v in out]


def violations(vals, finger):
    """Сколько градусов отличается поза от анатомической (наибольшее по суставам) — мера «излома»."""
    fixed = anatomical(vals, finger)
    return max(math.degrees(max(abs(a - b) for a, b in zip(v, w))) for v, w in zip(vals, fixed))


def write(rig, side, finger, vals):
    """Поза пальца углами: порядок Эйлера YZX = Rx(сгиб) · Rz(развод) · Ry(кручение) — ключи между позами идут прямо
    по сгибу и разводу (в XYZ большой сгиб перескакивает на равный поворот через 180° и между ключами ломается)."""
    for pb, (fl, sp, tw) in zip(bones(rig, side, finger), vals):
        pb.rotation_mode = 'YZX'
        pb.rotation_euler = (fl, tw, sp)


# ------------------------------------------------------------------ кожа и поверхность
class Skin:
    """Вершины сетки рук по костям пальцев и кисти — в осях кости покоя; положение в позе = поза кости × они."""

    def __init__(self, rig, mesh_ob, side, step=2):
        self.rig = rig
        names = [f'{f}.{j:02d}.{side}' for f in FINGERS for j in (1, 2, 3)] + [f'hand.{side}']
        gi = {g.name: g.index for g in mesh_ob.vertex_groups if g.name in names}
        me = mesh_ob.data
        # покой сетки в осях арматуры: родитель — объект арматуры
        to_arm = rig.matrix_world.inverted() @ mesh_ob.matrix_world
        rest_inv = {n: rig.data.bones[n].matrix_local.inverted() for n in names}
        self.local = {n: [] for n in names}
        for i, v in enumerate(me.vertices):
            if i % step:
                continue
            best, w = None, 0.5
            for g in v.groups:
                for n, idx in gi.items():
                    if g.group == idx and g.weight > w:
                        best, w = n, g.weight
            if best:
                self.local[best].append(rest_inv[best] @ (to_arm @ v.co))

    def points(self, name):
        m = self.rig.matrix_world @ self.rig.pose.bones[name].matrix
        return [m @ p for p in self.local[name]]

    def knuckle(self, name, frac=0.4):
        """Кожа у основания кости (доля длины от головы) — костяшка; она движется с кистью, пальцем её не убрать."""
        ln = self.rig.data.bones[name].length
        m = self.rig.matrix_world @ self.rig.pose.bones[name].matrix
        return [m @ p for p in self.local[name] if p.y < ln * frac]


class Surface:
    """Оружие и магазин на текущем кадре: общее BVH — для ближайшей точки, по детали — для проверки «внутри»
    (чётность пересечений лучами в трёх направлениях; ближайшая грань у тонких стенок и вложенных деталей врёт)."""
    DIRS = (Vector((0.57, 0.62, 0.54)).normalized(), Vector((-0.71, 0.23, 0.66)).normalized(),
            Vector((0.18, -0.69, -0.70)).normalized())

    def __init__(self, objs, depsgraph):
        verts, polys = [], []
        self.parts = []
        for ob in objs:
            eo = ob.evaluated_get(depsgraph)
            me = eo.to_mesh()
            mw = eo.matrix_world
            vs = [mw @ v.co for v in me.vertices]
            ps = [list(p.vertices) for p in me.polygons]
            base = len(verts)
            verts.extend(vs)
            polys.extend([base + i for i in p] for p in ps)
            lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
            hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
            self.parts.append((BVHTree.FromPolygons(vs, ps, all_triangles=False), lo, hi))
            eo.to_mesh_clear()
        self.bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False)

    @staticmethod
    def _hits(bvh, p, d):
        n, o = 0, p.copy()
        for _ in range(48):
            loc, _, _, _ = bvh.ray_cast(o, d, 1.0)
            if loc is None:
                break
            n += 1
            o = loc + d * 1e-5
        return n

    def inside(self, p):
        return self.inside_part(p) >= 0

    def inside_part(self, p):
        """Номер детали, внутри которой точка, или −1."""
        for i, (bvh, lo, hi) in enumerate(self.parts):
            if lo.x <= p.x <= hi.x and lo.y <= p.y <= hi.y and lo.z <= p.z <= hi.z:
                if sum(self._hits(bvh, p, d) % 2 for d in self.DIRS) >= 2:
                    return i
        return -1


def surface(objs, depsgraph):
    return Surface(objs, depsgraph)


def depth(surf, pts, near=0.03):
    """Наибольшая глубина вхождения точек кожи в оружие (м, > 0 — внутри); точки дальше near не считаются."""
    worst = -near
    for p in pts:
        loc, _, _, dist = surf.bvh.find_nearest(p, near)
        if loc is None:
            continue
        s = dist if surf.inside(p) else -dist
        worst = max(worst, s)
    return worst


def finger_depth(skin, bvh, side, finger, joints=(0, 1, 2)):
    return max(depth(bvh, skin.points(f'{finger}.{j + 1:02d}.{side}')) for j in joints)


def update():
    bpy.context.view_layer.update()


# ------------------------------------------------------------------ смыкание
def close(rig, side, finger, target, skin, surf, wrap=0.008, wrap_max=math.radians(15.0)):
    """Палец по фалангам от основания к кончику, начиная с цели target (анатомической): фаланга вошла в предмет — её
    сустав поворачивается к ближайшему углу, при котором она снаружи (сначала пробуя разгиб, потом сгиб, в пределах
    сустава); фаланга снаружи, но ближе wrap — догибается до касания (не больше wrap_max сверх цели) — обхват. Положение
    фаланги зависит только от суставов ближе к ладони, поэтому одного прохода хватает. Концевая после средней — снова
    по правилу «вслед за средней». → (глубина до, после) мм."""
    kind = 'thumb' if finger == 'thumb' else 'f'
    vals = [list(t) for t in target]
    write(rig, side, finger, vals)
    update()
    before = finger_depth(skin, surf, side, finger)
    for j in range(3):
        if kind == 'thumb' and j == 0:
            continue                                     # основание большого — часть ладони, его не крутим
        lo, hi = (math.radians(x) for x in FLEX[kind][j])
        if j == 2 and kind == 'f':
            pip = max(vals[1][0], 0.0)
            vals[2][0] = max(DIP_FROM_PIP[0] * pip, min(vals[2][0], DIP_FROM_PIP[1] * pip + math.radians(15)))
        ph = f'{finger}.{j + 1:02d}.{side}'

        def at(th):
            vals[j][0] = th
            write(rig, side, finger, vals)
            update()
            return depth(surf, skin.points(ph))

        t0 = vals[j][0]
        d0 = at(t0)
        if d0 > CONTACT:
            best, best_d = t0, d0
            found = None
            for k in range(1, 61):
                for sgn in (-1, 1):                      # сначала разогнуть
                    th = t0 + sgn * k * STEP
                    if th < lo or th > hi:
                        continue
                    d = at(th)
                    if d < best_d:
                        best, best_d = th, d
                    if d <= CONTACT:
                        found = th
                        break
                if found is not None:
                    break
            if found is None and j == 0:
                # основание (у большого — запястно-пястный): сгиб и развод вместе, ближайшее к цели снаружи
                sp0 = vals[0][1]
                lim_sp = math.radians(SPREAD[kind])
                cands = []
                for kf in range(-20, 21, 2):
                    for ks in range(-12, 13, 2):
                        th, sp = t0 + kf * STEP, sp0 + ks * STEP
                        if lo <= th <= hi and -lim_sp <= sp <= lim_sp:
                            cands.append((kf * kf + ks * ks, th, sp))
                for _, th, sp in sorted(cands):
                    vals[0][1] = sp
                    d = at(th)
                    if d < best_d:
                        best, best_d = (th, sp), d
                    if d <= CONTACT:
                        found = (th, sp)
                        break
                th, sp = found if found is not None else (best if isinstance(best, tuple) else (best, sp0))
                vals[0][1] = sp
                at(th)
            else:
                at(found if found is not None else best)
        elif d0 > -wrap:
            th = t0
            while th + STEP <= min(hi, t0 + wrap_max):
                if at(th + STEP) > -CONTACT * 0.5:
                    break
                th += STEP
            at(th)
    after = finger_depth(skin, surf, side, finger)
    return round(before * 1000, 1), round(after * 1000, 1)


# ------------------------------------------------------------------ ладонь
def palm_points(skin, side):
    pts = skin.points(f'hand.{side}') + skin.points(f'thumb.01.{side}')
    for f in FINGERS[1:]:
        pts += skin.knuckle(f'{f}.01.{side}')
    return pts


def palm_push(skin, surf, side, near=0.03):
    """Куда и насколько вытолкнуть кисть, чтобы ладонь (и основание большого) вышла из предмета: средняя нормаль у
    вошедших точек, взвешенная глубиной; → (направление, глубина м) или (None, 0)."""
    acc, worst = Vector(), 0.0
    for p in palm_points(skin, side):
        loc, nrm, _, dist = surf.bvh.find_nearest(p, near)
        if loc is None or not surf.inside(p):
            continue
        acc += (loc - p).normalized() * dist if dist > 1e-6 else nrm * 1e-6
        worst = max(worst, dist)
    if worst <= 0.0 or acc.length < 1e-9:
        return None, 0.0
    return acc.normalized(), worst
