"""Транспорт «Проспекта»: колёсные диски v2 — колпак на стальном диске, литой, штамповка.

Владелец 2026-10-29: «колпаки машин выглядят процедурно — нужно 2–3 отличающихся варианта, должны быть и колпаки, и
литые диски, и штамповки». Прежние диски (carparts.hubcap / steel_face / alloy_face) — чаша с наложенными планками и
тёмные пятна вместо отверстий. Здесь диск — тело вращения по профилю настоящего диска, а окна, вентиляционные
отверстия и отверстия под шпильки — настоящие вырезы (булево вычитание Blender) со стенками и фаской по кромке;
гайки на конусе, ниппель, колпачок ступицы.

- steel — штамповка: глубокая чаша, выпуклое кольцо, 8 вентиляционных окон, площадка ступицы с 4 шпильками.
- cap   — пластиковый колпак «турбина» на той же штамповке: 10 изогнутых прорезей, выпуклый центр с пустой эмблемой,
          кольцо с канавкой по краю; сквозь прорези видна тёмная штамповка.
- alloy — литой: 5 сдвоенных спиц «вилкой», вогнутый профиль, спицы толщиной 30 мм, гайки в колодцах, колпачок.

Ось колеса +X (наружная сторона), центр в нуле, x0 — плоскость наружной закраины обода (как в carparts).
Функции выполняются внутри Blender и возвращают детали [(имя, материал, V, F)], как carparts.wheel_parts.
Качество — vq (подробная форма — для просмотра и запекания; игровая сетка — меньше делений, без фасок: их несёт карта
нормалей).
"""
from __future__ import annotations

import math

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
    v, f = revolve([(x_back, 0.0), (x_back, rh * 0.62), (x_back + 0.004, rh), (x_front - 0.002, rh),
                    (x_front, rh * 0.82), (x_front, 0.0)], 6, phase=math.pi / 6)
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
    V, F = revolve(prof, seg)
    cut = []
    xa, xb = x0 - 0.08, x0 + 0.02
    rr = np.linspace(rim_r * 0.585, rim_r * 0.765, _q(10, 4))
    for i in range(vents):
        c = (i + 0.5) * 2 * math.pi / vents
        half = 0.5 * 0.060 / rr                    # окно ~60 мм по дуге, края радиальные
        cut.append(_prism(_window(rr, c - half, c + half, _q(8, 3), _q(3, 1)), xa, xb))
    pins = [((pcd_r * math.cos(a), pcd_r * math.sin(a))) for a in np.arange(lugs) * 2 * math.pi / lugs + math.pi / lugs]
    for p in pins:
        cut.append(_prism(_circle(p, 0.0068, _q(16, 8)), xa, xb))
    face = _shape("steel_face", V, F, cut, thick=0.0042, bevel=_q(0.0012, 0.0))
    out = [("Rim_Face", "rim_steel", *face)]
    if with_nuts:
        out.append(("Lug_Nuts", "steel_dark", *pt.merge([_nut(p, x0 - 0.0172, x0 - 0.001) for p in pins])))
        grease = revolve([(x0 - 0.040, 0.0), (x0 - 0.040, 0.030), (x0 - 0.030, 0.029), (x0 - 0.024, 0.020),
                          (x0 - 0.022, 0.0)], _q(32, 12))
        out.append(("Hub_Cap", "steel_dark", *grease))
    stem, cap = _valve(rim_r, x0, math.radians(20.0))
    out += [("Valve", "rubber", *stem), ("Valve_Cap", "steel_dark", *cap)]
    return out


# --- колпак -----------------------------------------------------------------------------------------------------

def hubcap(rim_r: float, W: float, slots: int = 10, sweep_deg: float = 16.0):
    """Пластиковый колпак «турбина» на штамповке: край заходит на закраину, кольцо с канавкой, поле изогнутых прорезей,
    выпуклый центр с пустой площадкой эмблемы. Под ним — та же штамповка (видна в прорезях), без гаек."""
    x0 = W / 2 * 0.86
    seg = _q(128, 40)
    prof = [(x0 + 0.003, rim_r + 0.011), (x0 + 0.011, rim_r + 0.006), (x0 + 0.017, rim_r * 0.975),
            (x0 + 0.018, rim_r * 0.945), (x0 + 0.013, rim_r * 0.915), (x0 + 0.014, rim_r * 0.89),
            (x0 + 0.020, rim_r * 0.865), (x0 + 0.027, rim_r * 0.64), (x0 + 0.032, rim_r * 0.42),
            (x0 + 0.034, rim_r * 0.355), (x0 + 0.041, rim_r * 0.325), (x0 + 0.045, rim_r * 0.24),
            (x0 + 0.047, 0.058), (x0 + 0.047, 0.040)]
    V, F = revolve(prof, seg)
    cut = []
    rr = np.linspace(rim_r * 0.42, rim_r * 0.84, _q(14, 5))
    t = (rr - rr[0]) / (rr[-1] - rr[0])
    sw = math.radians(sweep_deg) * t ** 1.2           # прорезь закручена: внешний конец сдвинут по кругу
    width = 0.016 + 0.020 * t                         # уже у центра, шире у края, м по дуге
    for i in range(slots):
        c = i * 2 * math.pi / slots + sw
        half = 0.5 * width / rr
        cut.append(_prism(_window(rr, c - half, c + half, _q(6, 3), _q(3, 1)), x0 - 0.02, x0 + 0.08))
    cap = _shape("hubcap", V, F, cut, thick=0.0028, bevel=_q(0.0008, 0.0))
    badge = revolve([(x0 + 0.0505, 0.0), (x0 + 0.0505, 0.036), (x0 + 0.048, 0.042), (x0 + 0.045, 0.042)], _q(64, 24))
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
    seg = _q(160, 40)
    front = [(x0 + 0.005, rim_r - 0.001), (x0 - 0.003, rim_r * 0.94), (x0 - 0.012, rim_r * 0.82), (x0 - 0.024, rim_r * 0.62),
             (x0 - 0.032, rim_r * 0.44), (x0 - 0.034, rim_r * 0.36), (x0 - 0.027, 0.070), (x0 - 0.026, 0.034)]
    back = [(x0 - 0.064, 0.034), (x0 - 0.072, 0.075), (x0 - 0.066, rim_r * 0.44), (x0 - 0.058, rim_r * 0.62),
            (x0 - 0.048, rim_r * 0.82), (x0 - 0.040, rim_r * 0.94), (x0 - 0.034, rim_r - 0.006)]
    V, F = revolve(front + back, seg, closed=True)
    cut = []
    xa, xb = x0 - 0.12, x0 + 0.04
    r_hub, r_out = 0.082, rim_r * 0.885
    rr = np.linspace(r_hub, r_out, _q(18, 6))
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
        cut.append(_prism(_window(rr[ok], lo[ok], hi[ok], _q(10, 4), _q(3, 1)), xa, xb))
        # прорезь между спицами пары
        s = (d - w / 2) / rr
        ok = s > 0.004 / rr
        if ok.sum() > 2:
            cut.append(_prism(_window(rr[ok], c - s[ok], c + s[ok], _q(5, 3), _q(3, 1)), xa, xb))
    pins = [((pcd_r * math.cos(a), pcd_r * math.sin(a))) for a in np.arange(lugs) * 2 * math.pi / lugs + math.pi / lugs]
    for p in pins:
        cut.append(_prism(_circle(p, 0.0115, _q(20, 8)), x0 - 0.050, xb))   # колодец гайки до площадки
    face = _shape("alloy_face", V, F, cut, bevel=_q(0.0018, 0.0))
    nuts = pt.merge([_nut(p, x0 - 0.050, x0 - 0.030) for p in pins])
    cap = revolve([(x0 - 0.026, 0.0), (x0 - 0.026, 0.031), (x0 - 0.020, 0.031), (x0 - 0.016, 0.026), (x0 - 0.015, 0.0)],
                  _q(48, 16))
    stem, vcap = _valve(rim_r, x0, math.radians(20.0))
    return [("Rim_Spokes", "rim_alloy", *face), ("Lug_Nuts", "steel_dark", *nuts), ("Rim_Center_Cap", "rim_alloy", *cap),
            ("Valve", "rubber", *stem), ("Valve_Cap", "steel_dark", *vcap)]


def face(style: str, rim_r: float, W: float, spec: dict | None = None) -> list:
    """Лицо колеса нового образца по стилю: steel, cap, alloy."""
    spec = spec or {}
    if style == "steel":
        return steel_disc(rim_r, W, lugs=spec.get("lugs", 4), pcd_r=spec.get("pcd_r", 0.050))
    if style == "cap":
        return hubcap(rim_r, W, slots=spec.get("cap_slots", 10))
    return alloy(rim_r, W, pairs=spec.get("spoke_pairs", 5), lugs=spec.get("lugs", 5), pcd_r=spec.get("pcd_r", 0.0572))
