"""Транспорт «Проспекта»: колёсные диски v2 — колпак на стальном диске, литой, штамповка.

Владелец 2026-10-29: «колпаки машин выглядят процедурно — нужно 2–3 отличающихся варианта, должны быть и колпаки, и
литые диски, и штамповки». Прежние диски (carparts.hubcap / steel_face / alloy_face) — чаша с наложенными планками и
тёмные пятна вместо отверстий. Здесь диск — тело вращения по профилю настоящего диска, а окна, вентиляционные
отверстия и отверстия под шпильки — настоящие вырезы (булево вычитание Blender) со стенками и фаской по кромке;
гайки на конусе, ниппель, колпачок ступицы.

- steel — штамповка: глубокая чаша, выпуклое кольцо, 8 вентиляционных окон, площадка ступицы с 4 шпильками.
- cap   — пластиковый колпак «турбина» на той же штамповке: 10 изогнутых прорезей, выпуклый центр с пустой эмблемой,
          кольцо с канавкой по краю; сквозь прорези видна тёмная штамповка.
- alloy — литой: 5 сдвоенных спиц «вилкой», вогнутый профиль, спицы 46 → 30 мм шириной, гайки в колодцах, колпачок.

Ось колеса +X (наружная сторона), центр в нуле, x0 — плоскость наружной закраины обода (как в carparts).
Функции выполняются внутри Blender и возвращают детали [(имя, материал, V, F)], как carparts.wheel_parts.
Качество — vq (подробная форма — для просмотра и запекания; игровая сетка — меньше делений, без фасок: их несёт карта
нормалей).
"""
from __future__ import annotations

import math
from pathlib import Path

import bpy
import numpy as np

import parts as pt
from wheel import revolve


def _q(high, low):
    import vq
    return low if vq.low() else high


# --- 2D: окна в полярных координатах ---------------------------------------------------------------------------

def _chaikin(P: np.ndarray, n: int) -> np.ndarray:
    """Срезка углов замкнутого контура (скруглённые углы окон без отдельных дуг)."""
    for _ in range(n):
        Q = np.roll(P, -1, axis=0)
        P = np.vstack([0.75 * P + 0.25 * Q, 0.25 * P + 0.75 * Q]).reshape(2, -1, 2).transpose(1, 0, 2).reshape(-1, 2)
    return P


def _window(r: np.ndarray, left: np.ndarray, right: np.ndarray, n_arc: int, smooth: int) -> np.ndarray:
    """Окно между двумя кривыми угла left(r) < right(r) от r[0] до r[-1]: левый край вверх, наружная дуга, правый
    край вниз, внутренняя дуга. Возвращает контур (y, z)."""
    pts = [(rr, a) for rr, a in zip(r, left)]
    pts += [(r[-1], a) for a in np.linspace(left[-1], right[-1], n_arc)[1:-1]]
    pts += [(rr, a) for rr, a in zip(r[::-1], right[::-1])]
    pts += [(r[0], a) for a in np.linspace(right[0], left[0], n_arc)[1:-1]]
    P = np.array([(rr * math.cos(a), rr * math.sin(a)) for rr, a in pts])
    return _chaikin(P, smooth)


def _prism(loop: np.ndarray, x0: float, x1: float):
    """Призма-резак вдоль X по контуру (y, z): крышки — n-угольники."""
    n = len(loop)
    V = np.vstack([np.c_[np.full(n, x0), loop], np.c_[np.full(n, x1), loop]])
    F = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    F += [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    return V, F


def _circle(c, rad: float, n: int) -> np.ndarray:
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.c_[c[0] + rad * np.cos(t), c[1] + rad * np.sin(t)]


# --- Blender: тело, вырезы, фаска -------------------------------------------------------------------------------

def _obj(name: str, V, F) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [tuple(int(i) for i in f) for f in F])
    me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def _facing_plus_x(V, F):
    """Открытая чаша — нормалями наружу колеса (+X): толщина (Solidify внутрь) уходит к машине."""
    V = np.asarray(V, float)
    s = 0.0
    for f in F[: min(len(F), 400)]:
        a, b, c = V[f[0]], V[f[1]], V[f[2]]
        s += np.cross(b - a, c - a)[0]
    return F if s >= 0 else [tuple(reversed(f)) for f in F]


def _shape(name: str, V, F, cutters: list, thick: float = 0.0, bevel: float = 0.0):
    """Тело (V, F) → толщина (если открытая чаша) → вычитание резаков → фаска по кромкам → (V, F)."""
    if thick:
        F = _facing_plus_x(V, F)
    else:                                        # замкнутое тело — нормалями наружу, иначе вычитание выворачивается
        Va = np.asarray(V, float)
        vol = sum(np.dot(Va[f[0]], np.cross(Va[f[i]], Va[f[i + 1]])) for f in F for i in range(1, len(f) - 1))
        if vol < 0:
            F = [tuple(reversed(f)) for f in F]
    ob = _obj(name, V, F)
    tmp = []
    if thick:
        s = ob.modifiers.new("thick", "SOLIDIFY")
        s.thickness = thick
        s.offset = -1.0
        s.use_even_offset = True
    if cutters:
        col = bpy.data.collections.new(name + "_cut")
        bpy.context.scene.collection.children.link(col)
        for k, (cv, cf) in enumerate(cutters):
            c = _obj(f"{name}_cut{k}", cv, cf)
            bpy.context.scene.collection.objects.unlink(c)
            col.objects.link(c)
            c.hide_render = True
            tmp.append(c)
        b = ob.modifiers.new("cut", "BOOLEAN")
        b.operation = "DIFFERENCE"
        b.operand_type = "COLLECTION"
        b.collection = col
        b.solver = "EXACT"
    if bevel:
        bv = ob.modifiers.new("edge", "BEVEL")
        bv.width = bevel
        bv.segments = 2
        bv.limit_method = "ANGLE"
        bv.angle_limit = math.radians(35.0)
        bv.use_clamp_overlap = True
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    me.validate()                                # у колпака после вырезов и толщины — дубли граней (выгрузка их ругала)
    import vq
    if vq.low():
        # игровая: изнанка лица диска (грани к машине) снаружи не видна — долой; окна и их стенки остаются
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.normal.x < -0.5], context="FACES")
        bm.to_mesh(me)
        bm.free()
    Vo = np.array([v.co[:] for v in me.vertices])
    Fo = [tuple(p.vertices) for p in me.polygons]
    bpy.data.meshes.remove(me)
    old = ob.data
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(old)
    for c in tmp:
        m = c.data
        bpy.data.objects.remove(c)
        bpy.data.meshes.remove(m)
    if cutters:
        bpy.data.collections.remove(col)
    return Vo, Fo


def _nut(pos_yz, x_back: float, x_front: float, af: float = 0.017):
    """Гайка колеса: шестигранник «под ключ» af и конус-седло сзади, торец со снятой фаской."""
    rh = af / 2 / math.cos(math.pi / 6)
    prof = _q([(x_back, 0.0), (x_back, rh * 0.62), (x_back + 0.004, rh), (x_front - 0.002, rh), (x_front, rh * 0.82),
               (x_front, 0.0)],
              [(x_back, 0.0), (x_back + 0.002, rh), (x_front, rh * 0.86), (x_front, 0.0)])    # игровая: седло и фаска — в карте
    v, f = revolve(prof, 6, phase=math.pi / 6)
    v[:, 1] += pos_yz[0]
    v[:, 2] += pos_yz[1]
    return v, f


def _valve(rim_r: float, x0: float, ang: float):
    """Ниппель у закраины: резиновая ножка и колпачок, наружу и чуть к центру колеса."""
    d = np.array([1.0, -0.35 * math.cos(ang), -0.35 * math.sin(ang)])
    d /= np.linalg.norm(d)
    p0 = np.array([x0 - 0.020, (rim_r - 0.010) * math.cos(ang), (rim_r - 0.010) * math.sin(ang)])
    stem = pt.loft(np.array([p0, p0 + d * 0.026]), *_frame(d), _circ(0.0055, _q(12, 6)), cap=True)
    cap = pt.loft(np.array([p0 + d * 0.026, p0 + d * 0.038]), *_frame(d), _circ(0.0042, _q(12, 6)), cap=True)
    return stem, cap


def _frame(d):
    up = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(d, up)
    u /= np.linalg.norm(u)
    w = np.cross(d, u)
    return np.broadcast_to(u, (2, 3)), np.broadcast_to(w, (2, 3))


def _circ(r: float, n: int) -> np.ndarray:
    t = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.c_[r * np.cos(t), r * np.sin(t)]


# --- штамповка --------------------------------------------------------------------------------------------------

def steel_disc(rim_r: float, W: float, lugs: int = 4, pcd_r: float = 0.050, vents: int = 8, with_nuts: bool = True):
    """Штампованный диск: чаша вглубь на 35–40 мм, выпуклое кольцо у обода, конус с вентиляционными окнами, площадка
    ступицы с отверстиями под шпильки и центральным отверстием; гайки, колпачок ступицы, ниппель."""
    x0 = W / 2 * 0.86
    seg = _q(128, 32)
    prof = [(x0 - 0.036, rim_r - 0.008), (x0 - 0.040, rim_r * 0.93), (x0 - 0.035, rim_r * 0.865), (x0 - 0.028, rim_r * 0.82),
            (x0 - 0.027, rim_r * 0.56), (x0 - 0.019, rim_r * 0.47), (x0 - 0.013, rim_r * 0.42), (x0 - 0.013, 0.046),
            (x0 - 0.019, 0.036)]
    V, F = revolve(_q(prof, [prof[i] for i in (0, 1, 3, 4, 6, 7, 8)]), seg)
    cut = []
    xa, xb = x0 - 0.08, x0 + 0.02
    rr = np.linspace(rim_r * 0.585, rim_r * 0.765, _q(10, 3))
    for i in range(vents):
        c = (i + 0.5) * 2 * math.pi / vents
        half = 0.5 * 0.060 / rr                    # окно ~60 мм по дуге, края радиальные
        cut.append(_prism(_window(rr, c - half, c + half, _q(8, 2), _q(3, 1)), xa, xb))
    pins = [((pcd_r * math.cos(a), pcd_r * math.sin(a))) for a in np.arange(lugs) * 2 * math.pi / lugs + math.pi / lugs]
    for p in pins:
        cut.append(_prism(_circle(p, 0.0068, _q(16, 6)), xa, xb))
    face = _shape("steel_face", V, F, cut, thick=0.0042, bevel=_q(0.0012, 0.0))
    out = [("Rim_Face", "rim_steel", *face)]
    if with_nuts:
        out.append(("Lug_Nuts", "lug_nut", *pt.merge([_nut(p, x0 - 0.0172, x0 - 0.001) for p in pins])))
        grease = revolve([(x0 - 0.040, 0.0), (x0 - 0.040, 0.030), (x0 - 0.030, 0.029), (x0 - 0.024, 0.020),
                          (x0 - 0.022, 0.0)], _q(32, 12))
        out.append(("Hub_Cap", "lug_nut", *grease))
    stem, cap = _valve(rim_r, x0, math.radians(20.0))
    out += [("Valve", "rubber", *stem), ("Valve_Cap", "mesh_black", *cap)]
    return out


def truck_disc(rim_r: float, W: float, studs: int = 10):
    """Грузовая штамповка (автобус, ПАЗ, ГАЗель): глубокая чаша, 6 (на малых — 5) овальных окон, площадка с шпильками
    по кругу (у автобуса 10 гаек «на 32»), ступица с колпаком. Окна и отверстия — вырезы, как у легковой штамповки."""
    x0 = W / 2 * 0.86
    seg = _q(128, 32)
    big = rim_r > 0.25
    prof = [(x0 - 0.004, rim_r + 0.004), (x0 - 0.02, rim_r - 0.02), (x0 - 0.05, rim_r * 0.72), (x0 - 0.05, rim_r * 0.55),
            (x0 - 0.02, rim_r * 0.45), (x0 - 0.02, 0.105 if big else 0.07)]
    V, F = revolve(prof, seg)
    cut = []
    xa, xb = x0 - 0.12, x0 + 0.03
    n_vent = 6 if big else 5
    rr = np.linspace(rim_r * 0.565, rim_r * 0.705, _q(10, 3))
    for i in range(n_vent):
        c = (i + 0.5) * 2 * math.pi / n_vent
        half = 0.5 * rim_r * 0.24 / rr
        cut.append(_prism(_window(rr, c - half, c + half, _q(8, 2), _q(3, 1)), xa, xb))
    pcd = 0.142 if big else 0.09
    pins = [(pcd * math.cos(a), pcd * math.sin(a)) for a in np.arange(studs) * 2 * math.pi / studs]
    for p in pins:
        cut.append(_prism(_circle(p, 0.012 if big else 0.008, _q(16, 6)), xa, xb))
    face = _shape("truck_face", V, F, cut, thick=0.006, bevel=_q(0.0015, 0.0))
    nuts = pt.merge([_nut(p, x0 - 0.026, x0 + 0.012, af=0.032 if big else 0.019) for p in pins])
    hr = pcd * 0.62
    hub = revolve([(x0 - 0.02, 0.0), (x0 - 0.02, hr), (x0 + 0.03, hr * 0.92), (x0 + 0.06, hr * 0.64), (x0 + 0.07, 0.0)],
                  _q(48, 16))
    return [("Rim_Face", "rim_steel", *face), ("Lug_Nuts", "lug_nut", *nuts), ("Hub", "steel_dark", *hub)]


# --- колпак -----------------------------------------------------------------------------------------------------

def hubcap(rim_r: float, W: float, slots: int = 10, sweep_deg: float = 16.0):
    """Пластиковый колпак «турбина» на штамповке: край заходит на закраину, кольцо с канавкой, поле изогнутых прорезей,
    выпуклый центр с пустой площадкой эмблемы. Под ним — та же штамповка (видна в прорезях), без гаек."""
    x0 = W / 2 * 0.86
    seg = _q(128, 32)
    prof = [(x0 + 0.003, rim_r + 0.011), (x0 + 0.011, rim_r + 0.006), (x0 + 0.017, rim_r * 0.975),
            (x0 + 0.018, rim_r * 0.945), (x0 + 0.013, rim_r * 0.915), (x0 + 0.014, rim_r * 0.89),
            (x0 + 0.020, rim_r * 0.865), (x0 + 0.027, rim_r * 0.64), (x0 + 0.032, rim_r * 0.42),
            (x0 + 0.034, rim_r * 0.355), (x0 + 0.041, rim_r * 0.325), (x0 + 0.045, rim_r * 0.24),
            (x0 + 0.047, 0.058), (x0 + 0.047, 0.040)]
    V, F = revolve(_q(prof, [prof[i] for i in (0, 1, 2, 4, 6, 7, 8, 10, 12, 13)]), seg)
    cut = []
    rr = np.linspace(rim_r * 0.42, rim_r * 0.84, _q(14, 3))
    t = (rr - rr[0]) / (rr[-1] - rr[0])
    sw = math.radians(sweep_deg) * t ** 1.2           # прорезь закручена: внешний конец сдвинут по кругу
    width = 0.016 + 0.020 * t                         # уже у центра, шире у края, м по дуге
    for i in range(slots):
        c = i * 2 * math.pi / slots + sw
        half = 0.5 * width / rr
        cut.append(_prism(_window(rr, c - half, c + half, _q(6, 2), _q(3, 1)), x0 - 0.02, x0 + 0.08))
    cap = _shape("hubcap", V, F, cut, thick=0.0028, bevel=_q(0.0008, 0.0))
    badge = revolve([(x0 + 0.0505, 0.0), (x0 + 0.0505, 0.036), (x0 + 0.048, 0.042), (x0 + 0.045, 0.042)], _q(64, 16))
    out = [("Hubcap", "hubcap", *cap), ("Hubcap_Badge", "hubcap", *badge)]
    import vq
    if vq.low():
        # игровая сетка: под колпаком сквозь прорези видна только темнота — тёмная подложка вместо целой штамповки
        back = revolve([(x0 - 0.030, rim_r - 0.004), (x0 - 0.026, rim_r * 0.5), (x0 - 0.020, 0.0)], 24)
        out.append(("Hubcap_Back", "mesh_black", *back))
    else:
        out += steel_disc(rim_r, W, with_nuts=False)
    return out


# --- литой ------------------------------------------------------------------------------------------------------

def alloy(rim_r: float, W: float, pairs: int = 5, lugs: int = 5, pcd_r: float = 0.0572):
    """Литой диск: 5 сдвоенных спиц «вилкой» (у ступицы сливаются, к ободу расходятся), профиль вогнутый к ступице,
    толщина спицы ~30 мм, у ступицы толще; колодцы гаек, колпачок с пустой эмблемой."""
    x0 = W / 2 * 0.86
    seg = _q(160, 32)
    front = [(x0 + 0.005, rim_r - 0.001), (x0 - 0.003, rim_r * 0.94), (x0 - 0.012, rim_r * 0.82), (x0 - 0.024, rim_r * 0.62),
             (x0 - 0.032, rim_r * 0.44), (x0 - 0.034, rim_r * 0.36), (x0 - 0.027, 0.070), (x0 - 0.026, 0.034)]
    back = [(x0 - 0.064, 0.034), (x0 - 0.072, 0.075), (x0 - 0.066, rim_r * 0.44), (x0 - 0.058, rim_r * 0.62),
            (x0 - 0.048, rim_r * 0.82), (x0 - 0.040, rim_r * 0.94), (x0 - 0.034, rim_r - 0.006)]
    if _q(False, True):                           # игровая: профиль реже, плавность — в карте нормалей
        front = [front[i] for i in (0, 1, 2, 3, 4, 6, 7)]
        back = [back[i] for i in (0, 1, 2, 4, 6)]
    V, F = revolve(front + back, seg, closed=True)
    cut = []
    xa, xb = x0 - 0.12, x0 + 0.04
    r_hub, r_out = 0.082, rim_r * 0.885
    rr = np.linspace(r_hub, r_out, _q(18, 4))
    t = (rr - r_hub) / (r_out - r_hub)
    w = 0.046 - 0.016 * t                             # ширина одной спицы, м: литая спица толще штампованной
    d = np.where(t > 0.12, 0.027 * ((t - 0.12) / 0.88) ** 0.8, 0.0)   # половина развода пары: щель у обода ~2 см
    step = 2 * math.pi / pairs
    for k in range(pairs):
        c = k * step
        # большое окно между парами k и k+1
        lo = c + (d + w / 2) / rr
        hi = c + step - (d + w / 2) / rr
        ok = hi - lo > 0.02
        cut.append(_prism(_window(rr[ok], lo[ok], hi[ok], _q(10, 3), _q(3, 1)), xa, xb))
        # прорезь между спицами пары
        s = (d - w / 2) / rr
        ok = s > 0.004 / rr
        if ok.sum() > 2:
            cut.append(_prism(_window(rr[ok], c - s[ok], c + s[ok], _q(5, 2), _q(3, 1)), xa, xb))
    pins = [((pcd_r * math.cos(a), pcd_r * math.sin(a))) for a in np.arange(lugs) * 2 * math.pi / lugs + math.pi / lugs]
    for p in pins:
        cut.append(_prism(_circle(p, 0.0115, _q(20, 6)), x0 - 0.050, xb))   # колодец гайки до площадки
    face = _shape("alloy_face", V, F, cut, bevel=_q(0.0018, 0.0))
    nuts = pt.merge([_nut(p, x0 - 0.050, x0 - 0.030) for p in pins])
    cap = revolve([(x0 - 0.026, 0.0), (x0 - 0.026, 0.031), (x0 - 0.020, 0.031), (x0 - 0.016, 0.026), (x0 - 0.015, 0.0)],
                  _q(48, 16))
    stem, vcap = _valve(rim_r, x0, math.radians(20.0))
    return [("Rim_Spokes", "rim_alloy", *face), ("Lug_Nuts", "lug_nut", *nuts), ("Rim_Center_Cap", "hubcap", *cap),
            ("Valve", "rubber", *stem), ("Valve_Cap", "mesh_black", *vcap)]


# --- шина -------------------------------------------------------------------------------------------------------
# Подробная шина — сетка по углу × длине профиля, смещённая по нормали профиля: канавки протектора (рисунок
# «ёлочкой» с переменным шагом, ламели, выступы-индикаторы износа) и рельеф наружной боковины (tire_marks.py).
# Её запекают в карту нормалей гладкой игровой шины; у игровой — протектор и боковина разными сетками (свои слои
# в Painter: протектор вытерт и в пыли в канавках, боковина матовая, побуревшая).

TREAD_DEPTH = 6.5          # мм — остаток протектора у брошенной городской машины
SIPE = 2.2                 # мм — ширина ламели: настоящие ~1 мм, но тоньше шага сетки и пикселя карты они рвутся
MARKS_DIR = Path(__file__).resolve().parents[2] / "_asset_src" / "prospekt_vehicles" / "wheels"


def _tire_curve(R: float, W: float, rim_r: float):
    """Замкнутый гладкий профиль шины (x, r) в порядке carparts.tire: внутренняя боковина вверх, протектор от −x к +x,
    наружная боковина вниз, посадка борта. Возвращает плотную кривую и индексы границ: протектор, наружная боковина,
    борт, внутренняя боковина."""
    H, hw = R - rim_r, W / 2
    side = [(0.80, 0.03), (0.90, 0.13), (0.97, 0.30), (1.00, 0.50), (0.985, 0.68), (0.94, 0.82), (0.87, 0.92)]
    keys = {"tread0": (-0.80 * hw, R - 0.012), "side0": (0.80 * hw, R - 0.012), "bead0": (0.80 * hw, rim_r + 0.004),
            "inner0": (-0.80 * hw, rim_r + 0.004)}
    P = [(-k * hw, rim_r + q * H) for k, q in side]
    P += [keys["tread0"], (-0.76 * hw, R - 0.004), (-0.72 * hw, R), (0.72 * hw, R), (0.76 * hw, R - 0.004), keys["side0"]]
    P += [(k * hw, rim_r + q * H) for k, q in reversed(side)]
    P += [keys["bead0"], keys["inner0"]]
    C = _chaikin(np.array(P), 4)
    idx = {k: int(np.argmin(np.hypot(C[:, 0] - v[0], C[:, 1] - v[1]))) for k, v in keys.items()}
    return C, idx


def _arc_samples(C: np.ndarray, i0: int, i1: int, step: float) -> np.ndarray:
    """Точки кривой C от индекса i0 до i1 (по кругу) равномерно по длине с шагом не больше step."""
    n = len(C)
    seg = C[[(i0 + k) % n for k in range((i1 - i0) % n + 1)]]
    s = np.r_[0.0, np.cumsum(np.hypot(*np.diff(seg, axis=0).T))]
    m = max(2, int(math.ceil(s[-1] / step)) + 1)
    t = np.linspace(0.0, s[-1], m)
    return np.c_[np.interp(t, s, seg[:, 0]), np.interp(t, s, seg[:, 1])]


def _normals2d(P: np.ndarray) -> np.ndarray:
    """Наружные нормали профиля (x, r): обход по часовой — нормаль (−dr, dx)."""
    d = np.gradient(P, axis=0)
    nrm = np.c_[-d[:, 1], d[:, 0]]
    return nrm / np.linalg.norm(nrm, axis=1, keepdims=True)


def _grid(P: np.ndarray, n_theta: int, h: np.ndarray | None = None):
    """Тело вращения профиля P (открытого) с n_theta делениями, смещённое по нормали профиля на h (м, n_theta × len(P));
    порядок вершин и граней — как у wheel.revolve (нормали наружу)."""
    k = len(P)
    nrm = _normals2d(P)
    a = np.linspace(0, 2 * math.pi, n_theta, endpoint=False)
    hh = np.zeros((n_theta, k)) if h is None else h
    x = P[None, :, 0] + hh * nrm[None, :, 0]
    r = P[None, :, 1] + hh * nrm[None, :, 1]
    V = np.stack([x, r * np.cos(a)[:, None], r * np.sin(a)[:, None]], axis=-1).reshape(-1, 3)
    i = np.arange(n_theta)[:, None]
    j = np.arange(k - 1)[None, :]
    i2 = (i + 1) % n_theta
    F = np.stack([i * k + j, i * k + j + 1, i2 * k + j + 1, i2 * k + j], axis=-1).reshape(-1, 4)
    return V, [tuple(f) for f in F]


def _groove(d, w: float, depth: float, wall: float = 0.45):
    """Сечение канавки: полная глубина внутри, стенка шириной 2·wall мм с плавным переходом."""
    t = np.clip((w / 2 + wall - d) / (2 * wall), 0.0, 1.0)
    return depth * t * t * (3 - 2 * t)


def _tread_depth(n_theta: int, T: np.ndarray, Rmm: float, TW: float, t_end: float, twi_theta: list) -> np.ndarray:
    """Глубина рисунка протектора, мм (n_theta × len(T)): T — мм поперёк от середины по дуге профиля, TW — половина
    ширины беговой дорожки. Четыре продольные канавки; плечевые блоки с открытыми поперечными канавками, в средних
    рёбрах — слепые косые канавки «ёлочкой» (направленный рисунок), в рёбрах и блоках — поперечные ламели, шаг переменный 26–34 мм,
    правая половина сдвинута на полшага; в канавках — выступы-индикаторы износа против меток на боковине."""
    C = 2 * math.pi * Rmm
    du = C / n_theta
    D = np.zeros((n_theta, len(T)), np.float32)
    grooves = ((0.19 * TW, 0.135 * TW), (0.60 * TW, 0.12 * TW))
    for c, w in grooves:
        for s in (-1, 1):
            D = np.maximum(D, _groove(np.abs(T - s * c), w, TREAD_DEPTH)[None, :])

    def seg(u0, t0, u1, t1, w, depth, fade=False):
        i0 = int(math.floor((min(u0, u1) - w - 2) / du))
        i1 = int(math.ceil((max(u0, u1) + w + 2) / du)) + 1
        cols = np.where((T >= min(t0, t1) - w - 2) & (T <= max(t0, t1) + w + 2))[0]
        if not len(cols):
            return
        uu = (np.arange(i0, i1) * du)[:, None]
        tt = T[cols][None, :]
        dx, dy = u1 - u0, t1 - t0
        p = np.clip(((uu - u0) * dx + (tt - t0) * dy) / (dx * dx + dy * dy), 0.0, 1.0)
        # стенка косых канавок положе шага сетки: иначе их кромка на сетке «лесенкой» (ламели — бахромой)
        v = _groove(np.hypot(uu - u0 - p * dx, tt - t0 - p * dy), w, depth, wall=1.0)
        if fade:                                   # плечевая канавка мелеет к боковине и сходит на нет до её начала
            v = v * np.clip((t_end - np.abs(tt)) / 5.0, 0.0, 1.0)
        rows = np.arange(i0, i1) % n_theta
        D[np.ix_(rows, cols)] = np.maximum(D[np.ix_(rows, cols)], v)
    rng = np.random.default_rng(7)
    n = int(round(C / 30.0))
    p = rng.choice([0.87, 1.0, 1.13], size=n)
    p = p / p.sum() * C
    starts = np.r_[0.0, np.cumsum(p)[:-1]]
    for u0, pk in zip(starts, p):
        for s in (-1, 1):
            b = u0 + (0.5 * pk if s > 0 else 0.0)
            # плечо: открытая канавка от продольной к боковине, у края загибается поперёк
            ta, tb, tc = 0.66 * TW, 0.66 * TW + 0.55 * (TW - 0.66 * TW), t_end - 1.0
            seg(b, s * ta, b + 0.25 * (tb - ta), s * tb, 4.8, 0.92 * TREAD_DEPTH, fade=True)
            seg(b + 0.25 * (tb - ta), s * tb, b + 0.25 * (tb - ta) + 0.05 * (tc - tb), s * tc, 4.8, 0.92 * TREAD_DEPTH,
                fade=True)
            ub = b + 0.5 * pk
            seg(ub, s * (0.66 * TW + 4.0), ub, s * (TW - 3.0), SIPE, 2.5)   # ламель
            # среднее ребро: слепая косая канавка от наружной продольной внутрь и ламель от внутренней
            ua = b + 0.35 * pk
            seg(ua, s * 0.36 * TW, ua + 0.7 * 0.18 * TW, s * 0.54 * TW, 4.2, 0.8 * TREAD_DEPTH)
            uc = b + 0.85 * pk
            seg(uc, s * 0.2575 * TW, uc, s * 0.40 * TW, SIPE, 2.5)
            # центральное ребро — ламели; все ламели поперёк, вдоль рядов сетки: узкая косая канавка на сетке — зигзагом
            ue = b + 0.15 * pk
            seg(ue, s * 0.02 * TW, ue, s * 0.1225 * TW, SIPE, 2.5)
    for th in twi_theta:                          # индикаторы износа: дно канавки поднято на 1,6 мм на длине 12 мм
        u = (th % (2 * math.pi)) * Rmm
        rows = np.arange(int((u - 6.0) / du), int((u + 6.0) / du) + 1) % n_theta
        for c, w in grooves:
            for s in (-1, 1):
                cols = np.where(np.abs(T - s * c) < w / 2)[0]
                D[np.ix_(rows, cols)] = np.minimum(D[np.ix_(rows, cols)], TREAD_DEPTH - 1.6)
    return D


def _marks(R: float, W: float, rim_r: float) -> dict:
    """Карта рельефа наружной боковины (tire_marks.py, системный Python с PIL) — из кэша или построить."""
    import subprocess
    width = int(round(W * 1000 / 5) * 5)
    aspect = int(round((R - rim_r) / W * 100 / 5) * 5)
    rim_in = round(rim_r / 0.0127 * 2) / 2
    path = MARKS_DIR / f"marks_{width}_{aspect}_{rim_in:g}.npz"
    src = Path(__file__).resolve().parent / "tire_marks.py"
    if not path.exists() or path.stat().st_mtime < src.stat().st_mtime:
        r = subprocess.run(["python", "-X", "utf8", str(src), str(path), str(width), str(aspect), f"{rim_in:g}",
                            f"{rim_r * 1000:.2f}", f"{(R - rim_r) * 1000:.2f}"], capture_output=True, text=True,
                           encoding="utf-8")
        print(r.stdout.strip(), r.stderr.strip()[-400:])
    z = np.load(path)
    return {"h": z["h"].astype(np.float32) * float(z["scale"]), "res": float(z["res"]), "r_top": float(z["r_top"])}


def _side_height(m: dict, r_mm: np.ndarray, n_theta: int) -> np.ndarray:
    """Рельеф боковины, мм (n_theta × len(r_mm)): угол сетки θ (от +Y к +Z) → колонка карты (по часовой от верха,
    взгляд снаружи — справа +Y), радиус → строка; билинейно."""
    h = m["h"]
    rows, cols = h.shape
    th = np.linspace(0, 2 * math.pi, n_theta, endpoint=False)
    c = ((math.pi / 2 - th) % (2 * math.pi)) / (2 * math.pi) * cols - 0.5
    rr = np.clip((m["r_top"] - r_mm) / m["res"] - 0.5, 0, rows - 1.001)
    c0 = np.floor(c).astype(int)
    fc = (c - c0)[:, None]
    r0 = np.floor(rr).astype(int)
    fr = (rr - r0)[None, :]
    a = h[r0][:, c0 % cols].T
    b = h[r0][:, (c0 + 1) % cols].T
    cc = h[r0 + 1][:, c0 % cols].T
    d = h[r0 + 1][:, (c0 + 1) % cols].T
    return (a * (1 - fc) * (1 - fr) + b * fc * (1 - fr) + cc * (1 - fc) * fr + d * fc * fr)


def tire_high(R: float, W: float, rim_r: float):
    """Подробная шина для запекания: протектор (шаг сетки ~1,1 мм) и наружная боковина с надписями (~0,8 мм),
    внутренняя боковина и борт — гладкие и редкие."""
    C, ix = _tire_curve(R, W, rim_r)
    tread = _arc_samples(C, ix["tread0"], ix["side0"], 0.0011)
    side = _arc_samples(C, ix["side0"], ix["bead0"], 0.0007)
    bead = _arc_samples(C, ix["bead0"], ix["inner0"], 0.004)
    inner = _arc_samples(C, ix["inner0"], ix["tread0"], 0.003)
    s = np.r_[0.0, np.cumsum(np.hypot(*np.diff(tread, axis=0).T))]
    s0 = np.interp(0.0, tread[:, 0], s)                 # середина протектора (x = 0)
    T = (s - s0) * 1000.0
    TW = 0.72 * W / 2 * 1000.0
    t_end = min(-T[0], T[-1]) - 2.0
    twi = [math.pi / 2 - math.radians(30.0 + 60.0 * i) for i in range(6)]      # против меток на боковине
    nt = 1700
    Dt = _tread_depth(nt, T, R * 1000.0, TW, t_end, twi)
    Vt, Ft = _grid(tread, nt, -Dt / 1000.0)
    ns = 1900
    Hs = _side_height(_marks(R, W, rim_r), side[:, 1] * 1000.0, ns)
    Vs, Fs = _grid(side, ns, Hs / 1000.0)
    rest = pt.merge([_grid(bead, 120), _grid(inner, 360)])
    return [("Tire_Tread", "tire_tread", Vt, Ft), ("Tire", "rubber", *pt.merge([(Vs, Fs), rest]))]


def tire_low(R: float, W: float, rim_r: float, seg: int = 32):
    """Игровая шина: гладкий профиль (vq.tire_profile_low), протектор и боковины — разными сетками (свои слои Painter);
    рельеф — в карте нормалей. seg — деления по кругу (силуэт колеса у LOD0)."""
    import vq
    prof = vq.tire_profile_low(R, W, rim_r)
    tread = prof[5:9]
    outer = prof[8:15]                          # наружная боковина — до борта
    inner = prof[14:] + [prof[i] for i in (0, 2, 4, 5)]   # борт и внутренняя боковина (к машине, не видна) — реже
    return [("Tire_Tread", "tire_tread", *revolve(tread, seg)), ("Tire", "rubber", *revolve(outer, seg)),
            ("Tire_Inner", "rubber", *revolve(inner, seg))]


def tire(R: float, W: float, rim_r: float, seg: int = 32):
    import vq
    return tire_low(R, W, rim_r, seg) if vq.low() else tire_high(R, W, rim_r)


def face(style: str, rim_r: float, W: float, spec: dict | None = None) -> list:
    """Лицо колеса нового образца по стилю: steel, cap, alloy."""
    spec = spec or {}
    if style == "steel":
        return steel_disc(rim_r, W, lugs=spec.get("lugs", 4), pcd_r=spec.get("pcd_r", 0.050))
    if style == "cap":
        return hubcap(rim_r, W, slots=spec.get("cap_slots", 10))
    return alloy(rim_r, W, pairs=spec.get("spoke_pairs", 5), lugs=spec.get("lugs", 5), pcd_r=spec.get("pcd_r", 0.0572))
