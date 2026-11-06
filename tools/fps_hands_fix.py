"""Пропорции кистей FPS-рук (владелец 2026-11-06: «у них пальцы длинные и сами руки здоровенные … надо руки в порядок
привести»). Исходные руки FPSArms (риг ВЕРАСа v13: hand, palm.01–04, f_*.01–03, thumb.01–03) крупнее реальных:
запястье → костяшка среднего 15.4 см (у взрослого мужчины 9.5–10.5), палец от костяшки до кончика 12.1 (~9), ширина по
костяшкам указательного и мизинца 9.2 (~6.5), запястье → кончик 26.2 (~19); предплечье 25.1 — в норме. До этой правки
игра уменьшала всю кисть с предплечьем до 80 % (Balance.FPS_HAND_SCALE), ладонь при этом оставалась длиннее на ~25 %.

Правка — деформация покоя (сетка и начала костей; веса, UV, оси костей и ключи клипов не меняются), её применяют
выгрузки рук, исходники не трогаются:
  ладонь (кости hand, palm.0N и сетка на них) — от запястья: длина × PALM_LEN, ширина и толщина плавно от WRIST_* у
    запястья к KNUCKLE_* у костяшек (манжета перчатки у запястья не сжимается ступенькой);
  пальцы и большой палец — целиком × FINGER от своего основания, основание — куда его увела ладонь;
  предплечье — длина та же, манжета у запястья тоньше (× CUFF, к середине предплечья — 1);
  плечо и прочее — как было.
Вершина на нескольких костях — средним по весам (как скиннинг), поэтому на стыках нет швов.

Использование (внутри Blender): fix = fps_hands_fix.warp(heads, tails, coords, weights) → новые начала, концы, сетка.
"""
from __future__ import annotations

import numpy as np

PALM_LEN = 0.70        # запястье → костяшка: 15.4 → 10.8 см
KNUCKLE_W = 0.76       # ширина по костяшкам: 9.2 → 7.0 см
KNUCKLE_T = 0.82       # толщина ладони у костяшек
WRIST_W = 0.86         # у запястья — мягче: манжета перчатки
WRIST_T = 0.86
FINGER = 0.74          # пальцы: 12.1 → 9.0 см (владелец 06.11: «пальцам не надо длины, а то ощущение, что мы у оружия
                       # точку G ищем, а не крючок») — запястье → кончик в перчатке ~18.8
CUFF = 0.86            # манжета на предплечье у запястья (к середине предплечья — 1)
PARAMS = {'palm_len': PALM_LEN, 'knuckle_w': KNUCKLE_W, 'knuckle_t': KNUCKLE_T, 'wrist_w': WRIST_W,
          'wrist_t': WRIST_T, 'finger': FINGER, 'cuff': CUFF}
CHAINS = ('f_index', 'f_middle', 'f_ring', 'f_pinky', 'thumb')


def _smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class Side:
    """Оси кисти одной стороны в покое: запястье W, вперёд f (к костяшке среднего), поперёк a, по нормали n."""

    def __init__(self, heads, side):
        s = '.' + side
        self.W = np.array(heads['hand' + s], float)
        k = np.array(heads['f_middle.01' + s], float)
        self.L = float(np.linalg.norm(k - self.W))
        self.f = (k - self.W) / self.L
        a = np.array(heads['f_index.01' + s], float) - np.array(heads['f_pinky.01' + s], float)
        a = a - self.f * a.dot(self.f)
        self.a = a / np.linalg.norm(a)
        self.n = np.cross(self.a, self.f)
        self.E = np.array(heads['forearm' + s], float)
        ax = self.W - self.E
        self.fl = float(np.linalg.norm(ax))
        self.fax = ax / self.fl
        self.base = {c: np.array(heads[f'{c}.01{s}'], float) for c in CHAINS}

    def palm(self, p):
        r = p - self.W
        d = r @ self.f
        x = r @ self.a
        z = r @ self.n
        t = np.clip(d / self.L, 0.0, 1.0)
        sw = WRIST_W + (KNUCKLE_W - WRIST_W) * t
        st = WRIST_T + (KNUCKLE_T - WRIST_T) * t
        d2 = np.where(d > 0.0, d * PALM_LEN, d)
        return self.W + np.outer(x * sw, self.a) + np.outer(d2, self.f) + np.outer(z * st, self.n)

    def finger(self, p, chain):
        k = self.base[chain]
        return self.palm(k[None, :])[0] + (p - k) * FINGER

    def palm_lin(self, p):
        """Линейная часть деформации ладони в точках p (для нормалей): (N, 3, 3)."""
        r = p - self.W
        d = r @ self.f
        t = np.clip(d / self.L, 0.0, 1.0)
        sw = WRIST_W + (KNUCKLE_W - WRIST_W) * t
        st = WRIST_T + (KNUCKLE_T - WRIST_T) * t
        sl = np.where(d > 0.0, PALM_LEN, 1.0)
        A = (sw[:, None, None] * np.outer(self.a, self.a)[None] + sl[:, None, None] * np.outer(self.f, self.f)[None] +
             st[:, None, None] * np.outer(self.n, self.n)[None])
        return A

    def forearm_lin(self, p):
        r = p - self.E
        along = r @ self.fax
        k = 1.0 + (CUFF - 1.0) * _smooth(0.55, 1.0, along / self.fl)
        P = np.outer(self.fax, self.fax)
        return P[None] + k[:, None, None] * (np.eye(3) - P)[None]

    def forearm(self, p):
        r = p - self.E
        along = r @ self.fax
        radial = r - np.outer(along, self.fax)
        k = 1.0 + (CUFF - 1.0) * _smooth(0.55, 1.0, along / self.fl)
        return self.E + np.outer(along, self.fax) + radial * k[:, None]


def _kind(bone):
    """Как деформировать то, что висит на кости: ('palm'|'finger'|'forearm'|None, сторона, цепочка)."""
    if not (bone.endswith('.L') or bone.endswith('.R')):
        return None, None, None
    side = bone[-1]
    base = bone[:-2]
    if base == 'hand' or base.startswith('palm.') or base == 'ik_hand':
        return 'palm', side, None
    for c in CHAINS:
        if base.startswith(c + '.'):
            return 'finger', side, c
    if base == 'forearm':
        return 'forearm', side, None
    return None, side, None


def _apply(sides, bone, p):
    kind, side, chain = _kind(bone)
    if kind is None or side not in sides:
        return p
    sd = sides[side]
    if kind == 'palm':
        return sd.palm(p)
    if kind == 'finger':
        return sd.finger(p, chain)
    return sd.forearm(p)


def _lin(sides, bone, p):
    kind, side, _ = _kind(bone)
    if kind is None or side not in sides:
        return np.broadcast_to(np.eye(3), (len(p), 3, 3))
    sd = sides[side]
    if kind == 'palm':
        return sd.palm_lin(p)
    if kind == 'finger':
        return np.broadcast_to(np.eye(3) * FINGER, (len(p), 3, 3))
    return sd.forearm_lin(p)


def normal_maps(heads: dict, coords, weights: list[dict]):
    """Матрицы для нормалей по вершинам: (M⁻¹)ᵀ средней по весам линейной части деформации — (N, 3, 3);
    нормаль угла n' = normalize(M_v · n) (собственные нормали сетки переносятся, а не пересчитываются)."""
    sides = {s: Side(heads, s) for s in ('L', 'R') if f'hand.{s}' in heads}
    co = np.asarray(coords, float)
    M = np.zeros((len(co), 3, 3))
    total = np.zeros(len(co))
    by_bone: dict[str, list] = {}
    for i, w in enumerate(weights):
        for b, x in w.items():
            if x > 0.0:
                by_bone.setdefault(b, []).append((i, x))
    for b, items in by_bone.items():
        idx = np.array([i for i, _ in items])
        wv = np.array([x for _, x in items])
        M[idx] += _lin(sides, b, co[idx]) * wv[:, None, None]
        total[idx] += wv
    keep = total <= 0.0
    M[~keep] /= total[~keep][:, None, None]
    M[keep] = np.eye(3)
    return np.transpose(np.linalg.inv(M), (0, 2, 1))


def apply_to_mesh(me, new_coords, nmaps):
    """Сетка Blender: вершины — new_coords, собственные нормали углов — через матрицы normal_maps (если они были)."""
    custom = bool(getattr(me, 'has_custom_normals', False))
    loops = None
    if custom:
        cn = np.array([c.vector[:] for c in me.corner_normals])
        vidx = np.array([lp.vertex_index for lp in me.loops])
        loops = np.einsum('nij,nj->ni', nmaps[vidx], cn)
        loops /= np.linalg.norm(loops, axis=1, keepdims=True) + 1e-12
    me.vertices.foreach_set('co', np.asarray(new_coords, np.float32).ravel())
    me.update()
    if custom:
        me.normals_split_custom_set([tuple(v) for v in loops])
        me.update()
    return custom


def warp(heads: dict, tails: dict, coords, weights: list[dict]):
    """heads / tails — {кость: (x, y, z)} в осях сетки (покой); coords — (N, 3); weights — [{кость: вес}] на вершину.
    → (новые heads, новые tails, новые coords (N, 3) numpy)."""
    sides = {s: Side(heads, s) for s in ('L', 'R') if f'hand.{s}' in heads}
    nh, nt = {}, {}
    for b in heads:
        nh[b] = tuple(_apply(sides, b, np.array(heads[b], float)[None, :])[0])
        nt[b] = tuple(_apply(sides, b, np.array(tails[b], float)[None, :])[0])
    co = np.asarray(coords, float)
    out = np.zeros_like(co)
    total = np.zeros(len(co))
    # по кости: все вершины с её весом разом
    by_bone: dict[str, list] = {}
    for i, w in enumerate(weights):
        for b, x in w.items():
            if x > 0.0:
                by_bone.setdefault(b, []).append((i, x))
    for b, items in by_bone.items():
        idx = np.array([i for i, _ in items])
        wv = np.array([x for _, x in items])
        out[idx] += _apply(sides, b, co[idx]) * wv[:, None]
        total[idx] += wv
    keep = total <= 0.0
    out[~keep] /= total[~keep][:, None]
    out[keep] = co[keep]
    return nh, nt, out


def measure(heads, coords=None, weights=None):
    """Замеры кисти (см) по началам костей: ладонь, палец до кончика (по сетке, если дана), ширина по костяшкам."""
    out = {}
    for s in ('L', 'R'):
        if f'hand.{s}' not in heads:
            continue
        W = np.array(heads[f'hand.{s}'])
        k = np.array(heads[f'f_middle.01.{s}'])
        rec = {'palm': float(np.linalg.norm(k - W) * 100),
               'span': float(np.linalg.norm(np.array(heads[f'f_index.01.{s}']) - np.array(heads[f'f_pinky.01.{s}'])) * 100)}
        if coords is not None and weights is not None:
            m3 = np.array(heads[f'f_middle.03.{s}'])
            d = (m3 - np.array(heads[f'f_middle.02.{s}']))
            d /= np.linalg.norm(d)
            idx = [i for i, w in enumerate(weights) if w and max(w, key=w.get) == f'f_middle.03.{s}']
            if idx:
                pts = np.asarray(coords)[idx]
                tip = pts[np.argmax((pts - m3) @ d)]
                rec['finger'] = float((np.linalg.norm(np.array(heads[f'f_middle.02.{s}']) - k) +
                                       np.linalg.norm(m3 - np.array(heads[f'f_middle.02.{s}'])) +
                                       np.linalg.norm(tip - m3)) * 100)
                rec['wrist_tip'] = float(np.linalg.norm(tip - W) * 100)
        out[s] = {k2: round(v, 1) for k2, v in rec.items()}
    return out


def fix_objects(rig, mesh):
    """Правка прямо в файле Blender (исходник рук): начала и концы костей рига (Edit Mode, крен сохраняется) и сетка
    с её нормалями — в осях рига (у рук владельца риг увеличен в 2.845 раза: правка от масштаба не зависит).
    → замеры кисти до и после (в единицах рига, переведённые в см по масштабу рига)."""
    import bpy
    from mathutils import Matrix, Vector
    bones = rig.data.bones
    heads = {b.name: tuple(b.head_local) for b in bones}
    tails = {b.name: tuple(b.tail_local) for b in bones}
    to_rig = rig.matrix_world.inverted() @ mesh.matrix_world
    lin = np.array(to_rig.to_3x3())
    vg = {g.index: g.name for g in mesh.vertex_groups}
    weights = [{vg[g.group]: g.weight for g in v.groups if g.group in vg} for v in mesh.data.vertices]
    co_mesh = np.array([v.co[:] for v in mesh.data.vertices])
    co = co_mesh @ lin.T + np.array(to_rig.translation)
    k = float(np.mean(rig.matrix_world.to_scale()))
    before = measure(heads, co * k, weights) if k == 1.0 else measure({n: tuple(np.array(h) * k) for n, h in heads.items()},
                                                                      co * k, weights)
    nh, nt, nco = warp(heads, tails, co, weights)
    maps = normal_maps(heads, co, weights)
    # нормали — из осей сетки в оси рига и обратно
    inv = np.linalg.inv(lin)
    maps_mesh = np.einsum('ij,njk,kl->nil', lin.T, maps, inv.T)
    new_mesh = (nco - np.array(to_rig.translation)) @ inv.T
    apply_to_mesh(mesh.data, new_mesh, maps_mesh)
    # кости: от корня к концам; крен — прежний
    view = bpy.context.view_layer
    for o in view.objects:
        o.select_set(False)
    view.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = rig.data.edit_bones

    def depth(b):
        d = 0
        while b.parent:
            b = b.parent
            d += 1
        return d
    for b in sorted(eb, key=depth):
        if b.name not in nh:
            continue
        roll = b.roll
        b.head = Vector(nh[b.name])
        b.tail = Vector(nt[b.name])
        b.roll = roll
    bpy.ops.object.mode_set(mode='OBJECT')
    after = measure({n: tuple(np.array(h) * k) for n, h in nh.items()}, nco * k, weights)
    rig['hands_fix'] = __import__('json').dumps(PARAMS)
    return before, after

