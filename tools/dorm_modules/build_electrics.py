"""Электрика общежития, партия 1 — форма для просмотра владельцем: люминесцентные светильники, плафон, патрон на шнуре,
выключатели и розетки, распаечная коробка, проводка модулями.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
      --python tools/dorm_modules/build_electrics.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Electrics/models/RING_Dorm_Electrics_v01.blend" [preview <папка>]

Владелец 2026-10-31: на потолке люминесцентные лампы с проводами к ним, на стенах выключатели, в комнатах так же; кое-где
лампы тускло горят; плафоны и патроны на шнуре; провода по стенам. Интервью 2026-11-01: светильники — вперемешку
(открытые на две трубки и с рассеивателем), проводка — вперемешку (в основном плоский провод на гвоздиках с распаечными
коробками, кое-где старый витой на фарфоровых роликах и висящие обрывки), горят — мигающие люминесцентные, выключатели и
розетки — вперемешку (старые круглые накладные из карболита и поздние белые квадратные).
Размеры, мм: трубка ЛБ-40 — 1213,6 × Ø40 (цоколь G13: штырьки Ø2,3 через 12,7); открытый светильник (по мотивам ЛСП) —
1240 × 236 × 115; с рассеивателем (по мотивам ЛПО) — 1290 × 188 × 93; стартер — Ø21 × 36; плафон-«таблетка» — Ø250 × 95;
патрон Е27 карболитовый — Ø42 × 62, лампа А60 — Ø60 × 105; выключатель и розетка накладные круглые — Ø58; белые
утопленные — рамка 80 × 80; распаечная коробка — Ø75 × 28; провод плоский ППВ 2×1,5 — 8,2 × 3,6 (прибит гвоздиками
через перемычку через 250); витой — две жилы Ø3,2 с шагом скрутки 30 на роликах Ø22 × 24 через 500.
Корни: потолочное — точка крепления на потолке (z = 0, вниз −Z, длинная ось — X); настенное — середина на стене (y = 0,
лицо к −Y); модули провода — начало на стене, вдоль +X. Подвижное — отдельными объектами с осью в шарнире: рычажок и
клавиша выключателя, рассеиватель (ось — длинная кромка). Материалы — нейтральные слоты по будущим отделкам.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import mlib as L  # noqa: E402
from build_found_lights import lathe  # noqa: E402
from build_furniture import cut, obj, pipe, rounded_box, set_mat  # noqa: E402

V = Vector
TAU = 2 * math.pi
CEIL = 2.7   # потолок студии
WALL_Y = 0.0  # стена студии — плоскость y = 0, комната в −Y


def mats() -> dict:
    return {
        "enamel": L.material("Светильник_эмаль", (0.78, 0.78, 0.75), 0.35),
        "reflector": L.material("Отражатель_эмаль", (0.82, 0.82, 0.8), 0.25),
        "tube": L.material("Трубка_люминофор", (0.92, 0.92, 0.9), 0.25),
        "cap": L.material("Цоколь_алюминий", (0.7, 0.7, 0.68), 0.35, 1.0),
        "pin": L.material("Штырьки_латунь", (0.7, 0.55, 0.3), 0.3, 1.0),
        "holder": L.material("Ламподержатель_пластик", (0.85, 0.84, 0.8), 0.45),
        "starter": L.material("Стартер_корпус", (0.72, 0.72, 0.7), 0.35, 1.0),
        "diffuser": L.material("Рассеиватель_опал", (0.9, 0.9, 0.88), 0.3, 0.0, 0.7),
        "glass_opal": L.material("Плафон_стекло", (0.92, 0.92, 0.9), 0.15, 0.0, 0.75),
        "plaf_base": L.material("Плафон_основание", (0.75, 0.75, 0.72), 0.4, 0.5),
        "carbolite": L.material("Карболит", (0.12, 0.07, 0.04), 0.35),
        "bulb_glass": L.material("Лампа_стекло", (0.95, 0.95, 0.95), 0.05, 0.0, 0.25),
        "bulb_base": L.material("Лампа_цоколь", (0.7, 0.68, 0.62), 0.35, 1.0),
        "insul": L.material("Лампа_изолятор", (0.03, 0.03, 0.03), 0.5),
        "filament": L.material("Нить_вольфрам", (0.55, 0.55, 0.55), 0.3, 1.0),
        "cord": L.material("Шнур_витой", (0.06, 0.05, 0.045), 0.7),
        "white_plastic": L.material("Пластик_белый", (0.85, 0.84, 0.8), 0.4),
        "box_plastic": L.material("Коробка_пластик", (0.62, 0.62, 0.6), 0.55),
        "wire": L.material("Провод_ПВХ", (0.86, 0.86, 0.83), 0.45),
        "nail": L.material("Гвоздик_сталь", (0.35, 0.34, 0.32), 0.45, 1.0),
        "screw": L.material("Винт_сталь", (0.45, 0.44, 0.42), 0.35, 1.0),
        "porcelain": L.material("Ролик_фарфор", (0.9, 0.89, 0.85), 0.12),
        "twisted": L.material("Провод_витой_оплётка", (0.1, 0.07, 0.05), 0.85),
        "copper": L.material("Медь", (0.75, 0.42, 0.25), 0.3, 1.0),
    }


# ---------------------------------------------------------------- общие помощники

def offset_poly(points, t):
    """Лист толщиной t по средней линии (ломаная в 2D) — замкнутый многоугольник со сдвигом по нормалям в изломах."""
    pts = [V((p[0], p[1], 0)) for p in points]
    n = len(pts)

    def normal(i):
        if i == 0:
            d = pts[1] - pts[0]
        elif i == n - 1:
            d = pts[-1] - pts[-2]
        else:
            d = (pts[i + 1] - pts[i]).normalized() + (pts[i] - pts[i - 1]).normalized()
        d.normalize()
        return V((-d.y, d.x, 0))
    a = [pts[i] + normal(i) * t / 2 for i in range(n)]
    b = [pts[i] - normal(i) * t / 2 for i in range(n)]
    return [(p.x, p.y) for p in a] + [(p.x, p.y) for p in reversed(b)]


def prism_x(bm, poly_yz, x0, x1):
    """Многоугольник в плоскости YZ, вытянутый вдоль X от x0 до x1."""
    return L.bm_prism(bm, poly_yz, (x0, 0, 0), (0, 1, 0), (0, 0, 1), (x1 - x0, 0, 0))


def frames(path, n0):
    """Рамки переносом без скручивания: (касательная, нормаль, бинормаль) в каждой точке, n0 — начальная нормаль."""
    path = [V(p) for p in path]
    out = []
    t_prev = (path[1] - path[0]).normalized()
    nrm = (V(n0) - t_prev * V(n0).dot(t_prev)).normalized()
    for i in range(len(path)):
        if i == 0:
            t = t_prev
        elif i == len(path) - 1:
            t = (path[-1] - path[-2]).normalized()
        else:
            t = ((path[i + 1] - path[i]).normalized() + (path[i] - path[i - 1]).normalized()).normalized()
        ax = t_prev.cross(t)
        if ax.length > 1e-9:
            nrm = Matrix.Rotation(math.atan2(ax.length, t_prev.dot(t)), 3, ax.normalized()) @ nrm
        t_prev = t
        b = t.cross(nrm).normalized()
        out.append((t, b.cross(t).normalized(), b))
    return path, out


def sweep(bm, path, profile, n0, caps=True):
    """Профиль (a — по нормали n0, b — по бинормали) вдоль пути — плоский провод, жгуты."""
    path, fr = frames(path, n0)
    rings = []
    for p, (t, n, b) in zip(path, fr):
        rings.append([bm.verts.new(p + n * a + b * c) for a, c in profile])
    k = len(profile)
    faces = []
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(k):
            j = (i + 1) % k
            faces.append(bm.faces.new((r0[i], r0[j], r1[j], r1[i])))
    if caps:
        faces.append(bm.faces.new(rings[0][::-1]))
        faces.append(bm.faces.new(rings[-1]))
    return faces


def helix_pair(center_path, r, pitch, phase=0.0, n0=(0, -1, 0)):
    """Две жилы, свитые вокруг средней линии: пути обеих."""
    path, fr = frames(center_path, n0)
    s = 0.0
    a, b = [], []
    for i, (p, (t, n, bn)) in enumerate(zip(path, fr)):
        if i:
            s += (path[i] - path[i - 1]).length
        ang = phase + TAU * s / pitch
        off = n * math.cos(ang) + bn * math.sin(ang)
        a.append(p + off * r)
        b.append(p - off * r)
    return a, b


def resample(points, step):
    pts = [V(p) for p in points]
    out = [pts[0]]
    for p0, p1 in zip(pts, pts[1:]):
        n = max(1, int((p1 - p0).length / step))
        for k in range(1, n + 1):
            out.append(p0.lerp(p1, k / n))
    return out


def screw_head(bm, at, normal, r=0.0035, h=0.0012):
    """Винт с полукруглой головкой и шлицем — головка по нормали."""
    n = V(normal).normalized()
    lathe(bm, [(0, 0), (r, 0), (r * 0.95, h * 0.5), (r * 0.6, h * 0.95), (0, h)], segs=12, origin=at, axis=n)


# ---------------------------------------------------------------- люминесцентные: трубка, держатель, стартер

def tube(bm_glass, bm_cap, bm_pin, x0, x1, y, z, broken_at=None, rng=None):
    """Трубка ЛБ-40 вдоль X: стекло Ø40,5, цоколи G13 по 22 мм, два штырька Ø2,3 через 12,7 на каждом торце;
    broken_at — стекло обломано на этой X (рваный край), второй цоколь и штырьки — только у целого конца."""
    r = 0.02025
    cap = 0.022
    gx0, gx1 = x0 + cap, x1 - cap
    if broken_at is not None:
        gx1 = broken_at
    segs = 24
    rings = []
    n = 24
    for i in range(n + 1):
        x = gx0 + (gx1 - gx0) * i / n
        ring = []
        for k in range(segs):
            a = TAU * k / segs
            xx = x
            if broken_at is not None and i == n:
                xx = x - rng.uniform(0.0, 0.05) * (0.5 + 0.5 * math.sin(a * 3 + 1.0)) ** 2
            ring.append(bm_glass.verts.new((xx, y + r * math.cos(a), z + r * math.sin(a))))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(segs):
            j = (k + 1) % segs
            bm_glass.faces.new((r0[k], r0[j], r1[j], r1[k]))
    bm_glass.faces.new(rings[0][::-1])
    if broken_at is None:
        bm_glass.faces.new(rings[-1])
    ends = [(x0, 1)] + ([(x1, -1)] if broken_at is None else [])
    for xe, s in ends:
        lathe(bm_cap, [(0, 0), (r * 0.82, 0), (r * 0.99, 0.004), (r * 1.0, cap), (0, cap)], segs=24,
              origin=(xe, y, z), axis=(s, 0, 0))
        for dy in (-0.00635, 0.00635):
            L.bm_cyl(bm_pin, (xe, y + dy, z), (xe - s * 0.0066, y + dy, z), 0.00115, segs=8)


def holder(bm, x, y, z, s):
    """Ламподержатель G13 («надгробие»): скруглённый сверху брусок с прорезью, стоит на торцевом щитке."""
    w, d, h = 0.018, 0.03, 0.044
    f = rounded_box(bm, (w, d, h), 0.004, cuts=4, center=(x + s * w / 2, y, z + 0.006))
    return f


def starter(bm_body, bm_sock, at):
    """Стартер: алюминиевый стаканчик Ø21 × 36 в пластмассовом гнезде на корпусе (вниз)."""
    x, y, z = at
    L.bm_cyl(bm_sock, (x, y, z), (x, y, z - 0.008), 0.0135, segs=16)
    lathe(bm_body, [(0, 0), (0.0105, 0), (0.0105, 0.033), (0.0095, 0.036), (0, 0.036)], segs=20,
          origin=(x, y, z - 0.008), axis=(0, 0, -1))


# ---------------------------------------------------------------- светильник открытый на две трубки (ЛСП)

def lsp(coll, m, at, rng, variant="две"):
    """Открытый: хребет-короб с ПРА 1240 × 70 × 55 под потолком, отражатель из листа 0,8 мм крыльями вниз-наружу,
    торцевые щитки с ламподержателями, две трубки ЛБ-40, стартеры снизу хребта, ввод провода сверху."""
    r = L.root(f"СВ_ЛСП_{variant}", coll, at)
    hl = 0.62
    bm = bmesh.new()
    # хребет (короб ПРА) и крепёжные лапки
    rounded_box(bm, (2 * hl, 0.07, 0.052), 0.004, cuts=6, center=(0, 0, -0.03))
    for sx in (-1, 1):
        L.bm_box(bm, (sx * 0.45 - 0.025, -0.03, -0.004), (sx * 0.45 + 0.025, 0.03, -0.001))
    set_mat(bm.faces, 0)
    for x in (-0.3, 0.0, 0.3):
        screw_head(bm, V((x, 0, -0.056)), (0, 0, -1), 0.003, 0.001)
    obj(bm, f"ЛСП_корпус_{variant}", coll, [m["enamel"]], r, bevel=0.0008, segs=1, angle=40)
    # отражатель: лист по средней линии, загиб кромок
    mid = [(-0.118, -0.098), (-0.113, -0.106), (-0.036, -0.057), (0.036, -0.057), (0.113, -0.106), (0.118, -0.098)]
    bm = bmesh.new()
    prism_x(bm, offset_poly(mid, 0.0008), -hl, hl)
    # торцевые щитки — трапеция под отражателем, с отгибом
    for sx in (-1, 1):
        plate = [(-0.112, -0.105), (-0.036, -0.058), (0.036, -0.058), (0.112, -0.105), (0.08, -0.112), (-0.08, -0.112)]
        x0 = sx * hl - (0.0008 if sx > 0 else 0)
        prism_x(bm, plate, x0, x0 + 0.0008)
    obj(bm, f"ЛСП_отражатель_{variant}", coll, [m["reflector"]], r, bevel=0.0, segs=1)
    # ламподержатели на щитках
    bm = bmesh.new()
    yt, zt = 0.045, -0.092
    for sx in (-1, 1):
        for y in (-yt, yt):
            holder(bm, sx * (hl - 0.0008), y, zt, -sx)
    obj(bm, f"ЛСП_держатели_{variant}", coll, [m["holder"]], r, bevel=0.0, segs=1)
    # трубки
    bg, bc, bp = bmesh.new(), bmesh.new(), bmesh.new()
    lx = 1.2136 / 2
    if variant == "две":
        for y in (-yt, yt):
            tube(bg, bc, bp, -lx, lx, y, zt)
    elif variant == "одна_и_обломок":
        tube(bg, bc, bp, -lx, lx, -yt, zt)
        tube(bg, bc, bp, -lx, lx, yt, zt, broken_at=-lx + 0.31, rng=rng)
    if variant != "пусто":
        obj(bg, f"ЛСП_трубки_{variant}", coll, [m["tube"]], r, smooth=80)
        obj(bc, f"ЛСП_цоколи_{variant}", coll, [m["cap"]], r, smooth=60)
        obj(bp, f"ЛСП_штырьки_{variant}", coll, [m["pin"]], r, smooth=60)
    # стартеры у одного конца хребта, ввод провода сверху
    b1, b2 = bmesh.new(), bmesh.new()
    for x in (0.47, 0.53):
        starter(b1, b2, (x, 0.0, -0.056))
    obj(b1, f"ЛСП_стартеры_{variant}", coll, [m["starter"]], r, smooth=60)
    obj(b2, f"ЛСП_гнёзда_стартеров_{variant}", coll, [m["holder"]], r, smooth=60)
    return r


# ---------------------------------------------------------------- светильник с рассеивателем (ЛПО)

def lpo(coll, m, at, rng, variant="закрыт"):
    """Короб из листа 1290 × 188 × 93 с отбортовкой снизу, внутри — держатели и две трубки, рассеиватель-корыто из
    молочного пластика с торцевыми заглушками; ось рассеивателя — длинная кромка (+Y): «висит» — повёрнут на ней."""
    r = L.root(f"СВ_ЛПО_{variant}", coll, at)
    hl, hw, h = 0.645, 0.094, 0.093
    t = 0.0008
    bm = bmesh.new()
    L.bm_box(bm, (-hl, -hw, -0.004), (hl, hw, -0.001))                      # дно короба к потолку
    for s in (-1, 1):
        L.bm_box(bm, (-hl, s * hw - (t if s > 0 else 0), -h), (hl, s * hw + (0 if s > 0 else t), -0.001))
        L.bm_box(bm, (s * hl - (t if s > 0 else 0), -hw, -h), (s * hl + (0 if s > 0 else t), hw, -0.001))
        # отбортовка снизу внутрь
        L.bm_box(bm, (-hl, s * hw - (0.008 if s > 0 else -0.0), -h), (hl, s * hw + (0 if s > 0 else 0.008), -h + t))
    obj(bm, f"ЛПО_корпус_{variant}", coll, [m["enamel"]], r, bevel=0.0006, segs=1, angle=40)
    bm = bmesh.new()
    yt, zt = 0.045, -0.042
    for sx in (-1, 1):
        for y in (-yt, yt):
            holder(bm, sx * (hl - t), y, zt, -sx)
    obj(bm, f"ЛПО_держатели_{variant}", coll, [m["holder"]], r)
    bg, bc, bp = bmesh.new(), bmesh.new(), bmesh.new()
    for y in (-yt, yt):
        tube(bg, bc, bp, -1.2136 / 2, 1.2136 / 2, y, zt)
    obj(bg, f"ЛПО_трубки_{variant}", coll, [m["tube"]], r, smooth=80)
    obj(bc, f"ЛПО_цоколи_{variant}", coll, [m["cap"]], r, smooth=60)
    obj(bp, f"ЛПО_штырьки_{variant}", coll, [m["pin"]], r, smooth=60)
    if variant == "сорван":
        return r
    # рассеиватель: корыто по дуге, толщина 1,5 мм, торцы — заглушки
    arc = [(-hw + 0.002 + (2 * hw - 0.004) * i / 16, -h - 0.004 - 0.03 * math.sin(math.pi * i / 16)) for i in range(17)]
    bm = bmesh.new()
    prism_x(bm, offset_poly(arc, 0.0015), -hl + 0.004, hl - 0.004)
    for sx in (-1, 1):
        x0 = sx * (hl - 0.004) - (0.0015 if sx > 0 else 0)
        prism_x(bm, [(p[0], p[1]) for p in arc], x0, x0 + 0.0015)
    pivot = V((0, hw - 0.002, -h - 0.004))
    for v in bm.verts:
        v.co -= pivot
    me = bpy.data.meshes.new(f"ЛПО_рассеиватель_{variant}")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m["diffuser"])
    d = bpy.data.objects.new(f"ЛПО_рассеиватель_{variant}", me)
    coll.objects.link(d)
    d.parent = r
    d.location = pivot
    if variant == "висит":
        d.rotation_euler = (math.radians(68), 0, math.radians(1.5))
    for p in d.data.polygons:
        p.use_smooth = True
    return r


# ---------------------------------------------------------------- плафон, лампа, патрон

def bulb(coll, m, r, origin, axis, name, broken=False, rng=None):
    """Лампа А60: резьбовой цоколь Е27 с чёрным изолятором и контактом, колба Ø60 × 105, ножка-штенгель и нить на
    держателях; broken — колба отбита, у цоколя рваное кольцо стекла."""
    o, ax = V(origin), V(axis).normalized()
    bm = bmesh.new()
    # цоколь: резьба — волна по профилю
    prof = [(0, 0), (0.004, 0), (0.0045, 0.0015)]
    lathe(bm, prof, segs=16, origin=o, axis=ax)
    thread = [(0.0128 + 0.0008 * math.sin(TAU * k / 6), 0.004 + 0.0215 * k / 30) for k in range(31)]
    lathe(bm, [(0.0045, 0.0015), (0.012, 0.0035)] + thread + [(0.0132, 0.026), (0.0128, 0.028)], segs=24, origin=o, axis=ax)
    obj(bm, f"{name}_цоколь", coll, [m["bulb_base"]], r, smooth=80)
    bm = bmesh.new()
    lathe(bm, [(0, -0.0005), (0.0035, -0.0005), (0.0042, 0.0015), (0.0, 0.0018)], segs=16, origin=o, axis=ax)
    obj(bm, f"{name}_изолятор", coll, [m["insul"]], r, smooth=60)
    # колба по профилю А60 (r, h от торца цоколя)
    env = [(0.0128, 0.028), (0.0135, 0.034), (0.017, 0.045), (0.024, 0.056), (0.029, 0.068), (0.030, 0.08), (0.029, 0.092),
           (0.025, 0.101), (0.017, 0.107), (0.0, 0.1095)]
    bm = bmesh.new()
    if broken:
        # рваное кольцо стекла у цоколя
        ring = env[:3]
        segs = 28
        rows = []
        for i, (rr, hh) in enumerate(ring):
            row = []
            for k in range(segs):
                a = TAU * k / segs
                h2 = hh + (rng.uniform(0.0, 0.012) * (0.4 + 0.6 * abs(math.sin(a * 2.5))) if i == len(ring) - 1 else 0)
                ref = V((1, 0, 0)) if abs(ax.x) < 0.9 else V((0, 1, 0))
                u = (ref - ax * ref.dot(ax)).normalized()
                w = ax.cross(u)
                row.append(bm.verts.new(o + ax * h2 + (u * math.cos(a) + w * math.sin(a)) * rr))
            rows.append(row)
        for r0, r1 in zip(rows, rows[1:]):
            for k in range(segs):
                j = (k + 1) % segs
                bm.faces.new((r0[k], r0[j], r1[j], r1[k]))
    else:
        lathe(bm, env, segs=32, origin=o, axis=ax)
    obj(bm, f"{name}_колба", coll, [m["bulb_glass"]], r, smooth=80)
    # штенгель, держатели и спираль
    bm = bmesh.new()
    lathe(bm, [(0, 0.028), (0.005, 0.028), (0.0035, 0.05), (0.002, 0.056), (0, 0.057)], segs=12, origin=o, axis=ax)
    obj(bm, f"{name}_штенгель", coll, [m["bulb_glass"]], r, smooth=80)
    bm = bmesh.new()
    ref = V((1, 0, 0)) if abs(ax.x) < 0.9 else V((0, 1, 0))
    u = (ref - ax * ref.dot(ax)).normalized()
    for s in (-1, 1):
        pipe(bm, [o + ax * 0.05 + u * s * 0.0015, o + ax * 0.07 + u * s * 0.006], 0.0003, segs=4)
    coil = []
    for k in range(80):
        tt = k / 79
        a = TAU * 14 * tt
        w = ax.cross(u)
        coil.append(o + ax * (0.07 + 0.0008 * math.cos(a)) + u * (-0.006 + 0.012 * tt) + w * 0.0008 * math.sin(a))
    pipe(bm, coil, 0.00012, segs=4)
    obj(bm, f"{name}_нить", coll, [m["filament"]], r, smooth=60)


def e27_socket(bm, origin, axis):
    """Патрон Е27 карболитовый: крышка с вводом шнура, корпус Ø42, кольцо абажурное с накаткой; от точки подвеса вдоль axis."""
    lathe(bm, [(0, 0), (0.006, 0), (0.0065, 0.004), (0.015, 0.007), (0.018, 0.012), (0.019, 0.022), (0.0205, 0.024),
               (0.021, 0.05), (0.0215, 0.052)] + [(0.0225 + 0.0006 * (k % 2), 0.052 + 0.001 * k) for k in range(9)]
          + [(0.0215, 0.061), (0.0155, 0.062), (0.0145, 0.058), (0.0145, 0.045)], segs=32, origin=origin, axis=axis)


def pendant(coll, m, at, rng, variant="лампа"):
    """Патрон на шнуре: потолочная чашка с крюком, витой шнур 0,65 м, патрон Е27, лампа А60 (целая / разбита / нет)."""
    r = L.root(f"СВ_патрон_{variant}", coll, at)
    bm = bmesh.new()
    lathe(bm, [(0, 0), (0.026, 0), (0.026, -0.003), (0.024, -0.012), (0.012, -0.016), (0.006, -0.02), (0, -0.02)][::-1],
          segs=28, origin=(0, 0, 0), axis=(0, 0, 1))
    screw_head(bm, V((0.017, 0, -0.0005)), (0, 0, -1), 0.003, 0.001)
    screw_head(bm, V((-0.017, 0, -0.0005)), (0, 0, -1), 0.003, 0.001)
    obj(bm, f"Патрон_чашка_{variant}", coll, [m["carbolite"]], r, smooth=60)
    # шнур: чуть изогнут (висел, перекручивался), две жилы свиты
    drop = 0.65
    center = [V((0.004 * math.sin(k * 0.7 + 1), 0.003 * math.sin(k * 0.45), -0.02 - drop * k / 40)) for k in range(41)]
    a, b = helix_pair(center, 0.0016, 0.026, n0=(1, 0, 0))
    bm = bmesh.new()
    for path in (a, b):
        pipe(bm, path, 0.0015, segs=6)
    obj(bm, f"Патрон_шнур_{variant}", coll, [m["cord"]], r, smooth=70)
    top = V((0, 0, -0.02 - drop))
    bm = bmesh.new()
    e27_socket(bm, top, (0, 0, -1))
    obj(bm, f"Патрон_корпус_{variant}", coll, [m["carbolite"]], r, smooth=50)
    if variant != "нет_лампы":
        bulb(coll, m, r, top + V((0, 0, -0.033)), (0, 0, -1), f"Патрон_лампа_{variant}", broken=variant == "разбита", rng=rng)
    return r


def plafond(coll, m, at, rng, variant="стекло"):
    """Плафон-«таблетка»: штампованное основание Ø250 с бортиком, патрон и лампа лёжа, стекло молочное куполом
    Ø220 × 72 на трёх винтах-барашках (нет стекла — видно лампу)."""
    r = L.root(f"СВ_плафон_{variant}", coll, at)
    bm = bmesh.new()
    lathe(bm, [(0, -0.002), (0.125, -0.002), (0.125, -0.012), (0.121, -0.016), (0.117, -0.014), (0.112, -0.006), (0.0, -0.006)],
          segs=48, origin=(0, 0, 0), axis=(0, 0, 1))
    for k in range(3):
        a = TAU * k / 3 + 0.3
        L.bm_cyl(bm, (0.114 * math.cos(a), 0.114 * math.sin(a), -0.012), (0.114 * math.cos(a), 0.114 * math.sin(a), -0.03),
                 0.0035, segs=10)
        L.bm_box(bm, (0.114 * math.cos(a) - 0.006, 0.114 * math.sin(a) - 0.0012, -0.034),
                 (0.114 * math.cos(a) + 0.006, 0.114 * math.sin(a) + 0.0012, -0.028))
    obj(bm, f"Плафон_основание_{variant}", coll, [m["plaf_base"]], r, smooth=50)
    bm = bmesh.new()
    e27_socket(bm, V((-0.06, 0, -0.03)), (1, 0, 0))
    L.bm_box(bm, (-0.075, -0.02, -0.03), (-0.06, 0.02, -0.006))
    obj(bm, f"Плафон_патрон_{variant}", coll, [m["carbolite"]], r, smooth=50)
    bulb(coll, m, r, V((-0.027, 0, -0.03)), (1, 0, 0), f"Плафон_лампа_{variant}", rng=rng)
    if variant == "стекло":
        bm = bmesh.new()
        outer = [(0.111, -0.012), (0.112, -0.02), (0.109, -0.04), (0.097, -0.06), (0.075, -0.075), (0.04, -0.083), (0.0, -0.085)]
        inner = [(0.0, -0.082), (0.04, -0.08), (0.074, -0.072), (0.095, -0.058), (0.106, -0.04), (0.109, -0.02), (0.108, -0.012)]
        lathe(bm, outer + inner, segs=48, origin=(0, 0, 0), axis=(0, 0, 1), closed=True)
        obj(bm, f"Плафон_стекло_{variant}", coll, [m["glass_opal"]], r, smooth=80)
    return r


# ---------------------------------------------------------------- выключатели, розетки, коробка

def wall_lathe(bm, prof, at, segs=40):
    lathe(bm, prof, segs=segs, origin=at, axis=(0, -1, 0))


def switch_round(coll, m, at, rng):
    """Выключатель накладной круглый, карболит: основание Ø58, крышка куполом, рычажок в прорези (ось — поперёк,
    «вверх — включено»), винт крышки."""
    r = L.root("ВК_круглый", coll, at)
    bm = bmesh.new()
    wall_lathe(bm, [(0, 0), (0.029, 0), (0.029, 0.007), (0.0285, 0.009), (0.027, 0.01), (0.026, 0.018), (0.022, 0.026),
                    (0.015, 0.0295), (0.0, 0.031)], V((0, 0, 0)))
    body = obj(bm, "ВК_круглый_корпус", coll, [m["carbolite"]], r, smooth=50)
    cutter = bmesh.new()
    L.bm_box(cutter, (-0.003, -0.04, -0.009), (0.003, -0.022, 0.009))
    cut(body, coll, r, "ВК_круглый_прорезь", cutter)
    bm = bmesh.new()
    rounded_box(bm, (0.0045, 0.0045, 0.016), 0.0018, cuts=4, center=(0, 0, 0.007))
    me = bpy.data.meshes.new("ВК_круглый_рычажок")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m["carbolite"])
    lever = bpy.data.objects.new("ВК_круглый_рычажок", me)
    coll.objects.link(lever)
    lever.parent = r
    lever.location = (0, -0.026, 0)
    lever.rotation_euler = (math.radians(60), 0, 0)  # наклонён вверх-наружу: «включено»
    for p in me.polygons:
        p.use_smooth = True
    bm = bmesh.new()
    screw_head(bm, V((0, -0.0305, -0.016)), (0, -1, 0), 0.0025, 0.0008)
    obj(bm, "ВК_круглый_винт", coll, [m["screw"]], r, smooth=50)
    return r


def socket_round(coll, m, at, rng):
    """Розетка накладная круглая, карболит: Ø58 × 22, два гнезда Ø4,6 через 19, винт посередине."""
    r = L.root("РЗ_круглая", coll, at)
    bm = bmesh.new()
    wall_lathe(bm, [(0, 0), (0.029, 0), (0.029, 0.007), (0.0285, 0.009), (0.0275, 0.01), (0.027, 0.019), (0.0255, 0.022),
                    (0.0, 0.022)], V((0, 0, 0)))  # лицо ровное: на выпуклом вырезы гнёзд давали полосы затенения
    body = obj(bm, "РЗ_круглая_корпус", coll, [m["carbolite"]], r, smooth=50)
    cutter = bmesh.new()
    for x in (-0.0095, 0.0095):
        L.bm_cyl(cutter, (x, -0.03, 0), (x, -0.008, 0), 0.0023, segs=14)
    cut(body, coll, r, "РЗ_круглая_гнёзда", cutter)
    bm = bmesh.new()
    screw_head(bm, V((0, -0.0225, 0)), (0, -1, 0), 0.003, 0.0009)
    obj(bm, "РЗ_круглая_винт", coll, [m["screw"]], r, smooth=50)
    return r


def switch_white(coll, m, at, rng):
    """Выключатель утопленный белый (поздний): рамка 80 × 80, клавиша 54 × 54 качается на поперечной оси (±4°)."""
    r = L.root("ВК_белый", coll, at)
    bm = bmesh.new()
    rounded_box(bm, (0.08, 0.009, 0.08), 0.004, cuts=8, center=(0, -0.0045, 0))
    frame = obj(bm, "ВК_белый_рамка", coll, [m["white_plastic"]], r, smooth=35)
    cutter = bmesh.new()
    L.bm_box(cutter, (-0.028, -0.02, -0.028), (0.028, -0.004, 0.028))
    cut(frame, coll, r, "ВК_белый_проём", cutter)
    bm = bmesh.new()
    rounded_box(bm, (0.054, 0.006, 0.054), 0.0025, cuts=6, center=(0, 0, 0))
    for v in bm.verts:
        v.co.y -= 0.0012 * (1 - (v.co.x / 0.027) ** 2) * (1 - (v.co.z / 0.027) ** 2) * (v.co.y < 0)
    me = bpy.data.meshes.new("ВК_белый_клавиша")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(m["white_plastic"])
    key = bpy.data.objects.new("ВК_белый_клавиша", me)
    coll.objects.link(key)
    key.parent = r
    key.location = (0, -0.0095, 0)
    key.rotation_euler = (math.radians(4), 0, 0)
    for p in me.polygons:
        p.use_smooth = True
    return r


def socket_white(coll, m, at, rng):
    """Розетка утопленная белая (поздняя): рамка 80 × 80 толщиной 12, круглое углубление Ø40 × 14 с двумя гнёздами."""
    r = L.root("РЗ_белая", coll, at)
    bm = bmesh.new()
    rounded_box(bm, (0.08, 0.012, 0.08), 0.004, cuts=8, center=(0, -0.006, 0))
    body = obj(bm, "РЗ_белая_корпус", coll, [m["white_plastic"]], r, smooth=35)
    cutter = bmesh.new()
    L.bm_cyl(cutter, (0, -0.02, 0), (0, -0.0035, 0), 0.02, segs=40)
    for x in (-0.0095, 0.0095):
        L.bm_cyl(cutter, (x, -0.006, 0), (x, 0.002, 0), 0.0023, segs=12)
    cut(body, coll, r, "РЗ_белая_углубление", cutter)
    bm = bmesh.new()
    screw_head(bm, V((0, -0.0036, 0.0)), (0, -1, 0), 0.0028, 0.0006)
    obj(bm, "РЗ_белая_винт", coll, [m["screw"]], r, smooth=50)
    return r


def junction_box(coll, m, at, rng):
    """Распаечная коробка накладная круглая: Ø75 × 28, крышка с бортиком и винтом, четыре ввода-патрубка (вверх,
    вниз, в стороны) — к ним подходят провода."""
    r = L.root("КР_распаечная", coll, at)
    bm = bmesh.new()
    wall_lathe(bm, [(0, 0), (0.0375, 0), (0.0375, 0.019), (0.0365, 0.02), (0.0, 0.02)], V((0, 0, 0)))
    for a in (0, 90, 180, 270):
        d = V((math.cos(math.radians(a)), 0, math.sin(math.radians(a))))
        L.bm_cyl(bm, d * 0.034 + V((0, -0.006, 0)), d * 0.046 + V((0, -0.006, 0)), 0.0055, segs=12)
    obj(bm, "КР_корпус", coll, [m["box_plastic"]], r, smooth=40)
    bm = bmesh.new()
    wall_lathe(bm, [(0, 0.0195), (0.0385, 0.0195), (0.0385, 0.025), (0.036, 0.027), (0.02, 0.0285), (0, 0.029)], V((0, 0, 0)))
    obj(bm, "КР_крышка", coll, [m["box_plastic"]], r, smooth=50)
    bm = bmesh.new()
    screw_head(bm, V((0, -0.029, 0)), (0, -1, 0), 0.0035, 0.001)
    obj(bm, "КР_винт", coll, [m["screw"]], r, smooth=50)
    return r


# ---------------------------------------------------------------- проводка: плоский провод, витой на роликах

FLAT = [(0.0, 0.0041), (0.0011, 0.0039), (0.0028, 0.0033), (0.0036, 0.0023), (0.0028, 0.0013), (0.0013, 0.0007),
        (0.0013, -0.0007), (0.0028, -0.0013), (0.0036, -0.0023), (0.0028, -0.0033), (0.0011, -0.0039), (0.0, -0.0041),
        (0.0, -0.0028), (0.0, 0.0028)]
# сечение ППВ 2×1,5: (от стены, поперёк) — две жилы-валика и перемычка между ними, плоской стороной к стене


def flat_run(bm, pts, n0, rng, nails_bm, nail_every=0.25, bulge=0.0007, wobble=0.0012):
    """Плоский провод по ломаной на плоскости (стена / потолок): между гвоздиками чуть отходит и гуляет вбок;
    гвоздик — шляпка на перемычке, прижимает провод."""
    path = resample(pts, 0.01)
    _, fr = frames(path, n0)
    length = 0.0
    out = []
    phase = rng.uniform(0, 6)
    for i, (p, (t, n, b)) in enumerate(zip(path, fr)):
        if i:
            length += (path[i] - path[i - 1]).length
        k = (length % nail_every) / nail_every
        lift = bulge * math.sin(math.pi * k) ** 2
        side = wobble * math.sin(length * 9.0 + phase) * math.sin(math.pi * k)
        out.append(p + n * lift + b * side)
    sweep(bm, out, FLAT, n0)
    s = nail_every * 0.5
    length = 0.0
    for i in range(1, len(path)):
        seg = (path[i] - path[i - 1]).length
        while s <= length + seg:
            q = path[i - 1].lerp(path[i], (s - length) / seg)
            nn = V(n0).normalized()
            lathe(nails_bm, [(0, 0), (0.0023, 0), (0.0021, 0.0005), (0.0012, 0.0009), (0, 0.001)], segs=10,
                  origin=q + nn * 0.0036, axis=nn)
            s += nail_every
        length += seg


def wire_modules(coll, m, at, rng):
    """Плоский провод модулями: прямой метр, загиб с заломом (поворот на стене вниз), переход со стены на потолок."""
    r = L.root("ПР_плоский", coll, at)
    pieces = []
    # прямой метр по стене (вдоль +X), плоской стороной к стене (нормаль −Y)
    bm, nb = bmesh.new(), bmesh.new()
    flat_run(bm, [(0, 0, 0), (1.0, 0, 0)], (0, -1, 0), rng, nb)
    pieces.append(("прямой_1м", bm, nb))
    # залом: провод идёт по X и, сложенный под 45°, уходит вниз; на сгибе — двойная толщина
    bm, nb = bmesh.new(), bmesh.new()
    flat_run(bm, [(1.3, 0, 0), (1.55, 0, 0)], (0, -1, 0), rng, nb)
    flat_run(bm, [(1.55, -0.0036, 0.004), (1.55, -0.0036, -0.004), (1.55, -0.0036, -0.3)], (0, -1, 0), rng, nb, nail_every=0.2)
    pieces.append(("залом_вниз", bm, nb))
    # переход: снизу по стене вверх, в углу на потолок (радиус 6 мм), по потолку в комнату (−Y)
    bm, nb = bmesh.new(), bmesh.new()
    path = [(1.9, 0, -0.35), (1.9, 0, -0.006)] + [(1.9, -0.006 + 0.006 * math.cos(a), -0.006 + 0.006 * math.sin(a))
                                                  for a in [math.radians(d) for d in range(0, 91, 15)]] + [(1.9, -0.35, 0)]
    path = [(p[0], p[1], p[2]) for p in path]
    sweep_path = resample(path, 0.01)
    sweep(bm, [V(p) + V((0, -0.0001, 0)) for p in sweep_path], FLAT, (0, -1, 0))
    for z in (-0.3, -0.05):
        lathe(nb, [(0, 0), (0.0023, 0), (0.0021, 0.0005), (0.0012, 0.0009), (0, 0.001)], segs=10,
              origin=(1.9, -0.0036, z), axis=(0, -1, 0))
    lathe(nb, [(0, 0), (0.0023, 0), (0.0021, 0.0005), (0.0012, 0.0009), (0, 0.001)], segs=10,
          origin=(1.9, -0.2, -0.0036), axis=(0, 0, -1))
    pieces.append(("стена_потолок", bm, nb))
    for name, bm, nb in pieces:
        obj(bm, f"ПР_плоский_{name}", coll, [m["wire"]], r, smooth=50)
        obj(nb, f"ПР_гвоздики_{name}", coll, [m["nail"]], r, smooth=50)
    return r


def roller(bm, at):
    """Ролик фарфоровый Ø22 × 24: основание, шейка-канавка под провод, верх со скруглением, отверстие с шурупом."""
    lathe(bm, [(0.004, 0), (0.011, 0), (0.0112, 0.002), (0.0105, 0.007), (0.0078, 0.011), (0.0078, 0.014), (0.0103, 0.018),
               (0.011, 0.022), (0.0095, 0.024), (0.004, 0.024)], segs=24, origin=at, axis=(0, -1, 0))
    lathe(bm, [(0.004, 0.024), (0.0035, 0.0), (0.004, 0.0)], segs=12, origin=at, axis=(0, -1, 0))


def twisted_modules(coll, m, at, rng):
    """Витой провод на роликах: метр с роликами через 500 (жгут в канавке, примотан вязальной проволокой, между
    роликами чуть провисает), обрывок — свисает с ролика, на конце медные жилы растрёпаны."""
    r = L.root("ПР_витой", coll, at)
    bm_r, bm_s = bmesh.new(), bmesh.new()
    for x in (0.0, 0.5, 1.0, 1.5):
        roller(bm_r, V((x, 0, 0)))
        screw_head(bm_s, V((x, -0.0242, 0)), (0, -1, 0), 0.0032, 0.0012)
    obj(bm_r, "ПР_ролики", coll, [m["porcelain"]], r, smooth=40)
    obj(bm_s, "ПР_ролики_шурупы", coll, [m["screw"]], r, smooth=50)
    yg = -0.0125
    # жгут метра: от ролика 0 до ролика 1,0 с провисом 4 мм посередине пролёта
    center = []
    for k in range(101):
        x = k / 100
        sag = 0.004 * math.sin(math.pi * ((x % 0.5) / 0.5))
        center.append(V((x, yg, 0.0078 + 0.0034 - sag)))
    a, b = helix_pair(center, 0.0017, 0.03, n0=(0, -1, 0))
    bm = bmesh.new()
    pipe(bm, a, 0.0016, segs=8)
    pipe(bm, b, 0.0016, segs=8)
    # обрывок: от ролика 1,5 жгут идёт и свисает вниз дугой 0,45 м
    hang = [V((1.0, yg, 0.0112))] + [V((1.0 + 0.5 * k / 10, yg, 0.0112 - 0.004 * math.sin(math.pi * k / 10))) for k in range(1, 11)]
    for k in range(1, 26):
        tt = k / 25
        hang.append(V((1.5 + 0.06 * math.sin(tt * 1.6), yg - 0.02 * tt, 0.011 - 0.45 * tt ** 1.2)))
    a2, b2 = helix_pair(resample(hang, 0.005), 0.0017, 0.03, phase=0.4, n0=(0, -1, 0))
    pipe(bm, a2, 0.0016, segs=8)
    pipe(bm, b2, 0.0016, segs=8)
    obj(bm, "ПР_витой_жгут", coll, [m["twisted"]], r, smooth=70)
    # вязка у роликов и растрёпанные медные жилы на конце обрывка
    bm = bmesh.new()
    # вязка: виток вокруг шейки ролика, поверху — через жгут
    for x in (0.0, 0.5, 1.0, 1.5):
        loop = []
        for k in range(33):
            t = TAU * k / 32
            rr = 0.0083 + 0.0068 * max(0.0, math.sin(t)) ** 4
            loop.append(V((x + rr * math.cos(t), yg + 0.0012 * math.sin(2 * t), rr * math.sin(t))))
        pipe(bm, loop, 0.0005, segs=5)
    obj(bm, "ПР_витой_вязка", coll, [m["nail"]], r, smooth=60)
    bm = bmesh.new()
    for end in (a2[-1], b2[-1]):
        for k in range(7):
            d = V((rng.uniform(-1, 1), rng.uniform(-1, 1), -2.5)).normalized()
            pipe(bm, [end, end + d * 0.006 + V((0, 0, -0.004)), end + d * rng.uniform(0.012, 0.02)], 0.00022, segs=4)
    obj(bm, "ПР_витой_жилы", coll, [m["copper"]], r, smooth=60)
    return r


# ---------------------------------------------------------------- сборка файла

CEILING = [  # (метка, построитель, вариант, ширина по X)
    ("ЛСП — две трубки", lsp, "две", 1.4), ("ЛСП — одна и обломок", lsp, "одна_и_обломок", 1.4),
    ("ЛСП — без трубок", lsp, "пусто", 1.4),
    ("ЛПО — рассеиватель на месте", lpo, "закрыт", 1.45), ("ЛПО — рассеиватель висит", lpo, "висит", 1.45),
    ("ЛПО — рассеиватель сорван", lpo, "сорван", 1.45),
    ("Плафон", plafond, "стекло", 0.4), ("Плафон без стекла", plafond, "без_стекла", 0.4),
    ("Патрон на шнуре — лампа", pendant, "лампа", 0.3), ("Патрон на шнуре — разбита", pendant, "разбита", 0.3),
    ("Патрон на шнуре — без лампы", pendant, "нет_лампы", 0.3),
]
WALL = [
    ("Выключатель круглый", switch_round, 0.14), ("Розетка круглая", socket_round, 0.14),
    ("Выключатель белый", switch_white, 0.16), ("Розетка белая", socket_white, 0.16),
    ("Коробка распаечная", junction_box, 0.18),
]


def studio(span: float, coll) -> None:
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.get("Студия") or bpy.data.worlds.new("Студия")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.34, 0.35, 0.37, 1.0)
    bg.inputs[1].default_value = 0.6
    sc.world = world
    bm = bmesh.new()
    L.bm_box(bm, (-1.0, -3.5, -0.02), (span + 1.0, 0.1, 0.0))
    L.finish_bm(bm, "студия_пол", coll, L.material("Студия_пол", (0.22, 0.21, 0.2), 0.9))
    bm = bmesh.new()
    L.bm_box(bm, (-1.0, 0.0, 0.0), (span + 1.0, 0.1, CEIL + 0.1))
    L.finish_bm(bm, "студия_стена", coll, L.material("Студия_стена", (0.34, 0.35, 0.36), 0.9))
    bm = bmesh.new()
    L.bm_box(bm, (-1.0, -2.0, CEIL), (span + 1.0, 0.1, CEIL + 0.1))
    L.finish_bm(bm, "студия_потолок", coll, L.material("Студия_потолок", (0.4, 0.4, 0.41), 0.9))
    for i, (x, e) in enumerate(((span * 0.2, 500), (span * 0.5, 500), (span * 0.8, 500))):
        ld = bpy.data.lights.new(f"Студия_свет_{i}", "AREA")
        ld.energy = e
        ld.size = 3.0
        lo = bpy.data.objects.new(f"Студия_свет_{i}", ld)
        lo.location = (x, -2.6, 1.2)
        lo.rotation_euler = (math.radians(70), 0, 0)
        coll.objects.link(lo)
    cd = bpy.data.cameras.new("Камера_обзор")
    cd.lens = 24
    co = bpy.data.objects.new("Камера_обзор", cd)
    co.location = (span / 2, -3.2, 1.5)
    co.rotation_euler = (V((span / 2, 0.0, 1.8)) - V(co.location)).to_track_quat("-Z", "Y").to_euler()
    coll.objects.link(co)
    sc.camera = co


def build(out: str) -> list:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    top = L.collection("Электрика_v01")
    m = mats()
    rng = random.Random(41)
    placed = []
    x = 0.0
    for label, fn, variant, width in CEILING:
        c = L.collection(label, top)
        root = fn(c, m, (x + width / 2, -0.7, CEIL), rng, variant)
        placed.append((label, c, root, "ceil"))
        x += width + 0.3
    span = x
    x = 0.4
    for label, fn, width in WALL:
        c = L.collection(label, top)
        root = fn(c, m, (x, WALL_Y, 1.3), rng)
        placed.append((label, c, root, "wall"))
        x += width + 0.15
    c = L.collection("Провод плоский", top)
    placed.append(("Провод плоский", c, wire_modules(c, m, (x + 0.2, WALL_Y, CEIL), rng), "wall"))
    c = L.collection("Провод витой на роликах", top)
    placed.append(("Провод витой на роликах", c, twisted_modules(c, m, (x + 0.2, WALL_Y, 1.0), rng), "wall"))
    studio(max(span, x + 2.6), L.collection("Студия"))
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)
    return placed


# крупные планы мелкого: точка в осях корня, азимут, наклон, расстояние
CLOSE = {
    "Провод плоский": [((0.5, 0, 0), -25, -10, 0.25), ((1.55, 0, -0.03), -20, -5, 0.22), ((1.9, -0.03, -0.03), -60, -25, 0.25),
                       ((0.25, 0, 0), -35, -15, 0.07)],
    "Провод витой на роликах": [((0.5, -0.01, 0.005), -30, 10, 0.12), ((1.0, -0.01, 0.0), -10, 5, 0.9),
                                ((1.52, -0.02, -0.43), -30, 5, 0.12)],
    "Выключатель круглый": [((0, -0.02, 0), -35, 15, 0.16), ((0, -0.02, 0), 60, 5, 0.14)],
    "ЛСП — одна и обломок": [((0.0, -0.7 + 0.7, -0.09), -30, -25, 1.4), ((-0.3, 0.045, -0.092), -60, -20, 0.3)],
    "ЛСП — две трубки": [((0.0, 0.0, -0.08), -30, -25, 1.4), ((0.55, 0.0, -0.07), -50, -20, 0.3)],
}


def preview(placed: list, folder: str, only=None, zoom: float = 1.2) -> None:
    """Самопроверка: потолочное — снизу сбоку, настенное — спереди 3/4 (Eevee)."""
    os.makedirs(folder, exist_ok=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 900, 700
    cam = sc.camera
    dg = bpy.context.evaluated_depsgraph_get()
    for i, (label, coll, root, kind) in enumerate(placed):
        if only and i not in only:
            continue
        pts = []
        for ob in coll.objects:
            if ob.type == "MESH" and not ob.hide_render:
                ev = ob.evaluated_get(dg)
                pts += [ev.matrix_world @ V(c) for c in ev.bound_box]
        mn = V((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = V((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        c = (mn + mx) / 2
        size = max((mx - mn).length, 0.12)
        views = [(-30, -25), (25, -55)] if kind == "ceil" else [(-30, 15), (35, 25)]
        shots = [(c, az, el, size * zoom + 0.08) for az, el in views]
        if label in CLOSE:
            shots = [(root.matrix_world @ V(p), az, el, d) for p, az, el, d in CLOSE[label]]
        for k, (c, az, el, dist) in enumerate(shots):
            a, e = math.radians(az), math.radians(el)
            cam.location = c + V((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
            cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
            cam.data.lens = 40
            cam.data.clip_start = 0.005
            sc.render.filepath = os.path.join(folder, f"{i:02d}_{k}.png")
            bpy.ops.render.render(write_still=True)
            print("preview", label, k, flush=True)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    placed = build(argv[0])
    if len(argv) >= 3 and argv[1] == "preview":
        only = {int(s) for s in argv[3].split(",")} if len(argv) >= 4 and argv[3] else None
        preview(placed, argv[2], only)
