"""Вещи общежития, партия 3 — форма для просмотра владельцем. Группа А: ящики для лута и вещи жильцов.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
      --python tools/dorm_modules/build_items3.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Items/models/RING_Dorm_Items_v01.blend" [preview <папка> [номера]]

Интервью владельца 2026-11-02 (RING_Dorm_Items/asset-state.md): ящики для лута — военные деревянные (дощатые, зелёные,
верёвочные ручки, защёлки), металлические (стальной сундук с проушиной под замок, ящик для инструментов), вещи жильцов
(чемодан, спортивная сумка, картонные коробки); варианты формы вперемешку — закрыто и открыто.
Размеры, мм: ящик под патроны 490 × 370 × 170 (19–20 × 14–15 × 6–7,5″ у советских ящиков; внутри два цинка), ящик ЗИП
1000 × 420 × 330, сундук 800 × 450 × 400 (листовая сталь с выдавленными рёбрами, уголки, откидные ручки, проушина и
два замка-лягушки), ящик для инструментов 460 × 200 × 210 (раскладной: два лотка на рычагах), чемодан 430 × 260 × 650
(жёсткий, на четырёх колёсах, выдвижная ручка), сумка 600 × 300 × 300 (ткань симуляцией), коробка 600 × 400 × 400
(гофрокартон 4 мм, клапаны, скотч).
Корень — середина опоры на полу, Z вверх, лицо к −Y. Крышки, лотки, створки чемодана, клапаны — узлами с осью в шарнире
(как дверцы мебели: будущий обыск), внутри пусто. Материалы — нейтральные слоты по будущим отделкам.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import build_furniture as B  # noqa: E402
import build_furniture2 as B2  # noqa: E402
import mlib as L  # noqa: E402
from build_found_lights import lathe  # noqa: E402

V = Vector
TAU = 2 * math.pi
pipe, rounded_box, set_mat, obj = B.pipe, B.rounded_box, B.set_mat, B.obj
part_at, loft = B2.part_at, B2.loft


def mats() -> dict:
    return {
        "wood": L.material("Дерево_окраска", (0.22, 0.27, 0.16), 0.75),
        "wood_end": L.material("Дерево_торец", (0.45, 0.36, 0.24), 0.85),
        "hardware": L.material("Фурнитура_сталь", (0.3, 0.3, 0.29), 0.5, 0.8),
        "rope": L.material("Верёвка", (0.55, 0.48, 0.36), 0.9),
        "tin": L.material("Цинк_банка", (0.62, 0.62, 0.6), 0.35, 1.0),
        "steel_paint": L.material("Сталь_окраска", (0.18, 0.24, 0.2), 0.45),
        "tool_paint": L.material("Ящик_краска", (0.55, 0.1, 0.07), 0.4),
        "plastic_black": L.material("Пластик_чёрный", (0.03, 0.03, 0.03), 0.5),
        "shell": L.material("Пластик_корпус", (0.12, 0.2, 0.3), 0.25),
        "zip": L.material("Молния", (0.02, 0.02, 0.02), 0.6),
        "rubber": L.material("Резина", (0.02, 0.02, 0.02), 0.85),
        "alu": L.material("Алюминий", (0.7, 0.7, 0.68), 0.3, 1.0),
        "lining": L.material("Подкладка_ткань", (0.08, 0.08, 0.09), 0.9),
        "fabric": L.material("Ткань_сумка", (0.05, 0.07, 0.12), 0.75),
        "webbing": L.material("Стропа", (0.03, 0.03, 0.03), 0.85),
        "cardboard": L.material("Картон", (0.55, 0.4, 0.25), 0.85),
        "cardboard_cut": L.material("Картон_срез", (0.62, 0.5, 0.34), 0.9),
        "tape": L.material("Скотч", (0.6, 0.48, 0.3), 0.25),
    }


def plank(bm, mn, mx, end_idx: int = 1) -> None:
    """Доска: пласти — краска (0), торцы вдоль длинной оси — неокрашенный срез (end_idx)."""
    fs = L.bm_box(bm, mn, mx)
    d = [abs(mx[i] - mn[i]) for i in range(3)]
    long_axis = d.index(max(d))
    bm.normal_update()
    for f in fs:
        f.material_index = end_idx if abs(f.normal[long_axis]) > 0.9 else 0


def nails(bm, pts, axis: str, r: float = 0.0028, h: float = 0.0012) -> None:
    """Шляпки гвоздей на грани (axis — наружу: «+x», «-y» …), чуть утоплены — край у самой доски."""
    sgn = 1 if axis[0] == "+" else -1
    i = "xyz".index(axis[1])
    for p in pts:
        a, b = V(p), V(p)
        b[i] += sgn * h
        a[i] -= sgn * 0.0003
        L.bm_cyl(bm, a, b, r, segs=10, r1=r * 0.85)


# ---------------------------------------------------------------- военные деревянные ящики

def crate(coll, m, at, rng, name: str, L_: float, W: float, H: float, n_latch: int, cans: bool, open_lid: bool):
    """Дощатый ящик: дно и стенки из досок с зазорами, торцы — сплошные щиты с вертикальными брусками и верёвочной
    ручкой через проушины, крышка из досок на поперечных планках снизу, две петли сзади, защёлки-накладки спереди
    (накладка на крышке, скоба на стенке, проволочная чека), шляпки гвоздей по концам досок."""
    r = L.root(name + ("_открыт" if open_lid else ""), coll, at)
    t, gap = 0.018, 0.0015
    lid_t = 0.02
    hb = H - lid_t
    hl, hw = L_ / 2, W / 2
    bm = bmesh.new()
    # дно — три доски поперёк Y
    nb = 3
    wb = (W - (nb - 1) * gap) / nb
    for k in range(nb):
        y0 = -hw + k * (wb + gap)
        plank(bm, (-hl + 0.003, y0, 0.0), (hl - 0.003, y0 + wb, t))
    # торцы — сплошной щит
    for s in (-1, 1):
        x0, x1 = (-hl, -hl + t) if s < 0 else (hl - t, hl)
        plank(bm, (x0, -hw, t), (x1, hw, hb), end_idx=0)
    # длинные стенки — по две доски по высоте
    rows = [(t, t + (hb - t) * 0.52 - gap / 2), (t + (hb - t) * 0.52 + gap / 2, hb)]
    for s in (-1, 1):
        y0, y1 = (-hw, -hw + t) if s < 0 else (hw - t, hw)
        for z0, z1 in rows:
            plank(bm, (-hl - 0.002, y0, z0), (hl + 0.002, y1, z1))
    # бруски торцов (снаружи, вертикально) и поперечина с проушинами под верёвку
    cleat_t = 0.022
    for s in (-1, 1):
        xo = s * hl
        for ys in (-1, 1):
            plank(bm, (min(xo, xo + s * cleat_t), ys * (hw - 0.05) - 0.022, 0.0),
                  (max(xo, xo + s * cleat_t), ys * (hw - 0.05) + 0.022, hb - 0.002))
        zc = hb * 0.62
        plank(bm, (min(xo, xo + s * cleat_t * 1.4), -hw + 0.075, zc - 0.022), (max(xo, xo + s * cleat_t * 1.4), hw - 0.075, zc + 0.022))
    # гвозди — по концам досок длинных стенок и дна
    pts = []
    for s in (-1, 1):
        for z0, z1 in rows:
            for x in (-hl + t / 2, hl - t / 2):
                pts.append((x, s * hw, (z0 + z1) / 2))
    nails(bm, [p for p in pts if p[1] < 0], "-y")
    nails(bm, [p for p in pts if p[1] > 0], "+y")
    body = obj(bm, f"{name}_корпус", coll, [m["wood"], m["wood_end"]], r, bevel=0.0018, segs=2)
    # верёвочные ручки — петля из проушины в проушину под поперечиной
    rb = bmesh.new()
    for s in (-1, 1):
        xo = s * (hl + cleat_t * 1.4 + 0.004)
        zc = hb * 0.62
        span = min(0.075, hw - 0.1)
        pts_r = [(s * (hl + cleat_t * 0.7), -span, zc), (xo, -span, zc - 0.006), (xo + s * 0.012, -span * 0.7, zc - 0.05),
                 (xo + s * 0.016, 0.0, zc - 0.062), (xo + s * 0.012, span * 0.7, zc - 0.05), (xo, span, zc - 0.006),
                 (s * (hl + cleat_t * 0.7), span, zc)]
        pipe(rb, pts_r, 0.006, segs=10, bend=0.018)
    obj(rb, f"{name}_ручки", coll, [m["rope"]], r, smooth=60)
    # фурнитура корпуса: пластины петель на задней стенке, скобы защёлок на передней
    hb_ = bmesh.new()
    hinge_x = [-(hl - 0.09), hl - 0.09]
    for x in hinge_x:
        L.bm_box(hb_, (x - 0.03, hw, hb - 0.05), (x + 0.03, hw + 0.002, hb - 0.004))
        nails(hb_, [(x - 0.018, hw + 0.002, hb - 0.035), (x + 0.018, hw + 0.002, hb - 0.035)], "+y", r=0.0022, h=0.0008)
        L.bm_cyl(hb_, (x - 0.03, hw + 0.004, hb + 0.002), (x - 0.01, hw + 0.004, hb + 0.002), 0.0045, segs=12)
        L.bm_cyl(hb_, (x + 0.01, hw + 0.004, hb + 0.002), (x + 0.03, hw + 0.004, hb + 0.002), 0.0045, segs=12)
    latch_x = [((k + 0.5) / n_latch - 0.5) * (L_ - 0.16) for k in range(n_latch)]
    for x in latch_x:
        # скоба (проволочная петля) торчит вперёд под накладкой
        L.bm_box(hb_, (x - 0.018, -hw - 0.002, hb - 0.045), (x + 0.018, -hw, hb - 0.012))
        pipe(hb_, [(x - 0.008, -hw - 0.002, hb - 0.03), (x - 0.008, -hw - 0.016, hb - 0.03), (x + 0.008, -hw - 0.016, hb - 0.03),
                   (x + 0.008, -hw - 0.002, hb - 0.03)], 0.0018, segs=8, bend=0.003)
    obj(hb_, f"{name}_фурнитура", coll, [m["hardware"]], r, smooth=50)
    # крышка: доски вдоль X, поперечные планки снизу (входят между стенок), листы петель и накладки защёлок
    pivot = (0.0, hw + 0.004, hb + 0.002)
    lb = bmesh.new()
    nl = 3 if W < 0.4 else 4
    wl = (W - (nl - 1) * gap) / nl
    for k in range(nl):
        y0 = -hw + k * (wl + gap)
        plank(lb, (-hl, y0, hb + 0.001), (hl, y0 + wl, hb + 0.001 + lid_t))
    nbat = 2 if L_ < 0.7 else 3
    for k in range(nbat):
        x = ((k + 0.5) / nbat - 0.5) * (L_ - 0.12)
        plank(lb, (x - 0.03, -hw + t + 0.003, hb - 0.017), (x + 0.03, hw - t - 0.003, hb + 0.001))
    nails(lb, [(x, y, hb + 0.001 + lid_t) for x in (-hl + 0.012, hl - 0.012) for y in (-hw + wl / 2, hw - wl / 2)], "+z")
    lid = part_at(lb, f"{name}_крышка", coll, [m["wood"], m["wood_end"]], r, pivot, bevel=0.0018, segs=2)
    hl_ = bmesh.new()
    for x in hinge_x:
        # лист петли по верху крышки и кулак в середине
        L.bm_box(hl_, (x - 0.01, hw - 0.1, hb + 0.001 + lid_t), (x + 0.01, hw + 0.002, hb + 0.003 + lid_t))
        L.bm_box(hl_, (x - 0.01, hw, hb + 0.002), (x + 0.01, hw + 0.002, hb + 0.003 + lid_t))
        L.bm_cyl(hl_, (x - 0.01, hw + 0.004, hb + 0.002), (x + 0.01, hw + 0.004, hb + 0.002), 0.0045, segs=12)
        L.bm_cyl(hl_, (x - 0.032, hw + 0.004, hb + 0.002), (x + 0.032, hw + 0.004, hb + 0.002), 0.0016, segs=8)
    for x in latch_x:
        # накладка: полоса по крышке и вниз по передней стенке с прорезью под скобу
        L.bm_box(hl_, (x - 0.014, -hw - 0.002, hb + 0.001 + lid_t), (x + 0.014, -hw + 0.04, hb + 0.003 + lid_t))
        face = L.bm_box(hl_, (x - 0.014, -hw - 0.004, hb - 0.045), (x + 0.014, -hw - 0.002, hb + 0.003 + lid_t))
        _ = face
        L.bm_cyl(hl_, (x - 0.014, -hw - 0.003, hb + 0.0025 + lid_t), (x + 0.014, -hw - 0.003, hb + 0.0025 + lid_t), 0.003, segs=10)
    hw_ob = obj(hl_, f"{name}_фурнитура_крышки", coll, [m["hardware"]], lid, smooth=50)
    hw_ob.data.transform(Matrix.Translation(-V(pivot)))
    hw_ob.matrix_parent_inverse = Matrix.Identity(4)
    # прорези накладок под скобу — вырезом
    for x in latch_x:
        cb = bmesh.new()
        L.bm_box(cb, (x - 0.011, -hw - 0.01, hb - 0.036), (x + 0.011, -hw + 0.004, hb - 0.024))
        cb.verts.ensure_lookup_table()
        for v in cb.verts:
            v.co -= V(pivot)
        B.cut(hw_ob, coll, lid, f"{name}_прорезь", cb)
    # проволочная чека — сквозь скобу (у закрытого)
    if not open_lid:
        pb = bmesh.new()
        for x in latch_x:
            pipe(pb, [(x - 0.016, -hw - 0.012, hb - 0.03), (x + 0.014, -hw - 0.012, hb - 0.03), (x + 0.02, -hw - 0.016, hb - 0.05)],
                 0.0009, segs=6, bend=0.004)
        obj(pb, f"{name}_чека", coll, [m["hardware"]], r, smooth=60)
    if cans:
        tin_cans(coll, m, r, hl - t, hw - t, t)
    if open_lid:
        lid.rotation_euler = (-math.radians(108), 0, 0)
    return r


def tin_cans(coll, m, r, ix: float, iy: float, z0: float) -> None:
    """Два цинка в ящике под патроны: короб с закатанным швом по верху, полоса вскрытия, нож-открывашка на крышке."""
    bm = bmesh.new()
    cl, cw, ch = 2 * ix - 0.01, iy - 0.006, 0.098
    for s in (-1, 1):
        cy = s * (iy / 2 + 0.0)
        rounded_box(bm, (cl, cw, ch), 0.004, cuts=4, center=(0, cy, z0 + ch / 2 + 0.001))
        # закатанный шов по периметру крышки
        ring = [V((x, cy + y, z0 + ch - 0.004)) for x, y in L.rrect(cl + 0.003, cw + 0.003, 0.006, 3)]
        L.bm_sweep(bm, ring, [(0, 0.0), (0.0016, 0.0016), (0, 0.0032), (-0.0016, 0.0016)], closed=True)
        # нож-открывашка: пластина с кольцом, припаяна к крышке
        L.bm_box(bm, (-0.07, cy - 0.008, z0 + ch + 0.001), (0.03, cy + 0.008, z0 + ch + 0.0025))
        lathe(bm, [(0.004, 0.0), (0.009, 0.0), (0.009, 0.0015), (0.004, 0.0015)], segs=16,
              origin=(0.042, cy, z0 + ch + 0.001), closed=True)
    obj(bm, "ЯП_цинки", coll, [m["tin"]], r, smooth=50)


# ---------------------------------------------------------------- стальной сундук

def trunk(coll, m, at, rng, open_lid: bool = False):
    """Сундук из листовой стали: стенки со скруглёнными вертикальными углами и выдавленными рёбрами, завальцованный
    верх, накладные уголки, крышка-колпак с напуском и рёбрами, две петли, проушина под навесной замок посередине и
    два замка-лягушки, откидные ручки на торцах."""
    r = L.root("МС_сундук" + ("_открыт" if open_lid else ""), coll, at)
    w, d, hb, hl_ = 0.8, 0.45, 0.31, 0.09
    rc = 0.02
    n = 6
    # стенки лофтом по высоте: рёбра — кольца, выдвинутые наружу на 3 мм
    def ring(z, off=0.0):
        return (z, [(x, y) for x, y in L.rrect(w + 2 * off, d + 2 * off, rc + off, n)])
    rings = [ring(0.006, -0.004), ring(0.012)]
    for zr in (0.07, 0.24):
        rings += [ring(zr - 0.018), ring(zr - 0.012, 0.003), ring(zr + 0.012, 0.003), ring(zr + 0.018)]
    rings += [ring(hb - 0.004)]
    bm = bmesh.new()
    loft(bm, rings, cap_first=True)
    body = obj(bm, "МС_корпус", coll, [m["steel_paint"]], r, smooth=40)
    sol = body.modifiers.new("Лист", "SOLIDIFY")
    sol.thickness = 0.0012
    sol.offset = -1
    # завальцованный верх — трубка по периметру
    eb = bmesh.new()
    L.bm_sweep(eb, [V((x, y, hb - 0.004)) for x, y in L.rrect(w + 0.004, d + 0.004, rc + 0.002, n)],
               [(0.004 * math.cos(a), 0.004 * math.sin(a)) for a in [TAU * i / 10 for i in range(10)]], closed=True)
    obj(eb, "МС_кант", coll, [m["steel_paint"]], r, smooth=45)
    # уголки: гнутые накладки по нижним углам снаружи, загиб под дно
    ub = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            corner_cap(ub, sx * (w / 2 - rc), sy * (d / 2 - rc), sx, sy, rc, 0.004, 0.065)
    caps = obj(ub, "МС_уголки", coll, [m["hardware"]], r, smooth=40)
    cs = caps.modifiers.new("Лист", "SOLIDIFY")
    cs.thickness = 0.0012
    cs.offset = 1
    # откидные ручки на торцах: две скобы-кронштейна и П-образная дужка, висит вниз
    hb2 = bmesh.new()
    for s in (-1, 1):
        x = s * (w / 2 + 0.002)
        for y in (-0.06, 0.06):
            L.bm_box(hb2, (min(x, x + s * 0.004), y - 0.014, hb * 0.62 - 0.018), (max(x, x + s * 0.004), y + 0.014, hb * 0.62 + 0.018))
            L.bm_cyl(hb2, (x + s * 0.008, y - 0.012, hb * 0.62), (x + s * 0.008, y + 0.012, hb * 0.62), 0.006, segs=12)
        pipe(hb2, [(x + s * 0.008, -0.06, hb * 0.62), (x + s * 0.012, -0.06, hb * 0.62 - 0.07),
                   (x + s * 0.012, 0.06, hb * 0.62 - 0.07), (x + s * 0.008, 0.06, hb * 0.62)], 0.0045, segs=10, bend=0.015)
    # петли сзади (листы на корпусе) и скобы замков-лягушек спереди
    for x in (-0.25, 0.25):
        L.bm_box(hb2, (x - 0.035, d / 2 + 0.001, hb - 0.06), (x + 0.035, d / 2 + 0.0035, hb - 0.006))
        L.bm_cyl(hb2, (x - 0.035, d / 2 + 0.006, hb + 0.002), (x - 0.012, d / 2 + 0.006, hb + 0.002), 0.005, segs=12)
        L.bm_cyl(hb2, (x + 0.012, d / 2 + 0.006, hb + 0.002), (x + 0.035, d / 2 + 0.006, hb + 0.002), 0.005, segs=12)
        # замок-лягушка: основание, рычаг, проволочная дужка вверх
        L.bm_box(hb2, (x - 0.022, -d / 2 - 0.004, hb - 0.075), (x + 0.022, -d / 2, hb - 0.03))
        L.bm_box(hb2, (x - 0.014, -d / 2 - 0.013, hb - 0.07), (x + 0.014, -d / 2 - 0.004, hb - 0.035))
        pipe(hb2, [(x - 0.012, -d / 2 - 0.01, hb - 0.04), (x - 0.012, -d / 2 - 0.009, hb + 0.012), (x + 0.012, -d / 2 - 0.009, hb + 0.012),
                   (x + 0.012, -d / 2 - 0.01, hb - 0.04)], 0.0018, segs=8, bend=0.004)
    # проушина посередине: планка на корпусе с ушком
    L.bm_box(hb2, (-0.02, -d / 2 - 0.004, hb - 0.07), (0.02, -d / 2, hb - 0.035))
    lathe(hb2, [(0.006, -0.005), (0.011, -0.005), (0.011, 0.005), (0.006, 0.005)], segs=16, origin=(0, -d / 2 - 0.012, hb - 0.035),
          axis=(1, 0, 0), closed=True)
    obj(hb2, "МС_фурнитура", coll, [m["hardware"]], r, smooth=50)
    # крышка-колпак: напуск 5 мм на корпус, верх чуть выпуклый, два ребра вдоль
    pivot = (0.0, d / 2 + 0.006, hb + 0.002)
    lb = bmesh.new()
    off = 0.005
    rr = [ring(hb - 0.022, off), ring(hb + hl_ - 0.012, off)]
    rr += [(hb + hl_ - 0.002, [(x, y) for x, y in L.rrect(w + 2 * off - 0.016, d + 2 * off - 0.016, rc, n)])]
    loft(lb, rr, cap_last=True)
    lid = part_at(lb, "МС_крышка", coll, [m["steel_paint"]], r, pivot, smooth=40)
    sl = lid.modifiers.new("Лист", "SOLIDIFY")
    sl.thickness = 0.0012
    sl.offset = -1
    tb = bmesh.new()
    for y in (-0.08, 0.08):
        rounded_box(tb, (w - 0.16, 0.03, 0.006), 0.0028, cuts=3, center=(0, y, hb + hl_ - 0.002))
    # на крышке: листы петель, накладка проушины с прорезью, крючки лягушек
    for x in (-0.25, 0.25):
        L.bm_box(tb, (x - 0.035, d / 2 + off - 0.0005, hb - 0.004), (x + 0.035, d / 2 + off + 0.002, hb + 0.05))
        L.bm_cyl(tb, (x - 0.012, d / 2 + 0.006, hb + 0.002), (x + 0.012, d / 2 + 0.006, hb + 0.002), 0.005, segs=12)
        L.bm_box(tb, (x - 0.016, -d / 2 - off - 0.003, hb + 0.002), (x + 0.016, -d / 2 - off, hb + 0.03))
    L.bm_box(tb, (-0.018, -d / 2 - off - 0.003, hb - 0.03), (0.018, -d / 2 - off, hb + 0.045))
    tob = obj(tb, "МС_крышка_рёбра", coll, [m["steel_paint"]], lid, smooth=45)
    tob.data.transform(Matrix.Translation(-V(pivot)))
    tob.matrix_parent_inverse = Matrix.Identity(4)
    cb = bmesh.new()
    L.bm_box(cb, (-0.007, -d / 2 - off - 0.01, hb - 0.022), (0.007, -d / 2 - off + 0.004, hb - 0.004))
    for v in cb.verts:
        v.co -= V(pivot)
    B.cut(tob, coll, lid, "МС_прорезь", cb)
    if open_lid:
        lid.rotation_euler = (-math.radians(102), 0, 0)
    return r


# ---------------------------------------------------------------- картонная коробка

def carton(coll, m, at, rng, open_top: bool = False, size=(0.6, 0.4, 0.4), name: str = "КК_коробка"):
    """Коробка из гофрокартона 4 мм: стенки чуть выпучены, рёбра скруглены сгибом, дно — клапаны внахлёст под скотчем,
    верх — четыре клапана на сгибах (у закрытой — сложены и заклеены скотчем вдоль шва с заходом на торцы; у открытой —
    скотч разрезан по шву, клапаны откинуты и прогнуты)."""
    r = L.root(name + ("_открыта" if open_top else ""), coll, at)
    w, d, h = size
    t = 0.004

    def pillow(x, y):
        return 0.007 * math.cos(min(abs(x) / (w / 2), 1.0) * math.pi / 2) * math.cos(min(abs(y) / (d / 2), 1.0) * math.pi / 2)

    bm = bmesh.new()
    # стенки — подразделённая оболочка: середина граней выпучена на 5 мм (содержимое давит), рёбра по сгибу
    rounded_box(bm, (w, d, h), 0.004, cuts=10, center=(0, 0, h / 2))
    for v in bm.verts:
        nx, ny = 2 * v.co.x / w, 2 * v.co.y / d
        nz = 2 * (v.co.z - h / 2) / h
        bulge = 0.005 * (1 - nz * nz)
        if abs(abs(nx) - 1) < 0.02:
            v.co.x += math.copysign(bulge * (1 - ny * ny), nx)
        if abs(abs(ny) - 1) < 0.02:
            v.co.y += math.copysign(bulge * (1 - nx * nx), ny)
    # картон не ровный: мягкая волна по стенкам ±1 мм
    ph = rng.uniform(0, TAU)
    for v in bm.verts:
        n_ = V((v.co.x / w, v.co.y / d, 0)).normalized() if abs(v.co.z - h / 2) < h / 2 - 0.004 else V((0, 0, 0))
        v.co += n_ * 0.001 * math.sin(v.co.z * 23 + ph) * math.cos((v.co.x + v.co.y) * 17 + ph)
    top = [f for f in bm.faces if f.calc_center_median().z > h - 0.002]
    bmesh.ops.delete(bm, geom=top, context="FACES")
    body = obj(bm, f"{name}_корпус", coll, [m["cardboard"], m["cardboard_cut"]], r, smooth=35)
    so = body.modifiers.new("Картон", "SOLIDIFY")
    so.thickness = t
    so.offset = -1
    so.material_offset_rim = 1
    # клапаны: длинные — по половине ширины, короткие — тоже до середины; узлы с осью на сгибе
    flaps = [("клапан_перед", (0, -d / 2, h), "X", d / 2, w, -1), ("клапан_зад", (0, d / 2, h), "X", d / 2, w, 1),
             ("клапан_лев", (-w / 2, 0, h), "Y", w / 2, d, -1), ("клапан_прав", (w / 2, 0, h), "Y", w / 2, d, 1)]
    for tag, pivot, axis, reach, span, s in flaps:
        fb = bmesh.new()
        n_u, n_v = 10, 8
        z_lay = h - (0.0 if tag in ("клапан_перед", "клапан_зад") else t)
        verts = []
        for j in range(n_v + 1):
            row = []
            for i in range(n_u + 1):
                a = -span / 2 + 0.003 + (span - 0.006) * i / n_u
                b = (reach - 0.003) * j / n_v
                if axis == "X":
                    p = V((a, pivot[1] - s * b, z_lay))
                else:
                    p = V((pivot[0] - s * b, a, z_lay))
                row.append(fb.verts.new(p))
            verts.append(row)
        for j in range(n_v):
            for i in range(n_u):
                fb.faces.new((verts[j][i], verts[j][i + 1], verts[j + 1][i + 1], verts[j + 1][i]))
        fl = part_at(fb, f"{name}_{tag}", coll, [m["cardboard"], m["cardboard_cut"]], r, pivot, smooth=35)
        so = fl.modifiers.new("Картон", "SOLIDIFY")
        so.thickness = t
        # толщина клапанов — вниз: короткие лежат под длинными (толщиной вверх выходили вровень с ними и проступали
        # зубцами по швам)
        so.offset = -1
        so.material_offset_rim = 1
        if not open_top:
            # закрытый: клапаны вспучены содержимым к середине — одна выпуклость на всех (по месту в плане)
            for v in fl.data.vertices:
                wx, wy = v.co.x + pivot[0], v.co.y + pivot[1]
                v.co.z += pillow(wx, wy)
        if open_top:
            ang = math.radians(rng.uniform(105, 135))
            # откинут наружу и прогнут: дальний край провисает
            for v in fl.data.vertices:
                dist = abs(v.co.y) if axis == "X" else abs(v.co.x)
                v.co.z += -0.03 * (dist / reach) ** 2
            if axis == "X":
                fl.rotation_euler = (s * ang, 0, 0)
            else:
                fl.rotation_euler = (0, -s * ang, 0)
    # скотч: по шву вдоль X с заходом на торцы (у открытой — разрезан по шву, лоскуты на клапанах)
    tb = bmesh.new()
    tw, tt = 0.048, 0.0003
    ztop = h + (0.0 if open_top else 0.0)
    if not open_top:
        path = [V((-w / 2 - 0.004, 0, h - 0.07)), V((-w / 2 - 0.004, 0, h + 0.0005))]
        path += [V((x, 0, h + pillow(x, 0.0) + 0.0004)) for x in [-w / 2 + w * k / 16 for k in range(1, 16)]]
        path += [V((w / 2 + 0.004, 0, h + 0.0005)), V((w / 2 + 0.004, 0, h - 0.07))]
        L.bm_sweep(tb, path, [(-tw / 2, 0), (tw / 2, 0), (tw / 2, tt), (-tw / 2, tt)], up=(0, 1, 0))
    else:
        for s in (-1, 1):
            path = [V((s * (w / 2 + 0.004), 0, h - 0.07)), V((s * (w / 2 + 0.004), 0, h - 0.003))]
            L.bm_sweep(tb, path, [(-tw / 2, 0), (tw / 2, 0), (tw / 2, tt), (-tw / 2, tt)], up=(0, 1, 0))
    # дно: скотч вдоль шва снизу
    path = [V((-w / 2 - 0.004, 0, 0.07)), V((-w / 2 - 0.004, 0, -0.0005)), V((w / 2 + 0.004, 0, -0.0005)), V((w / 2 + 0.004, 0, 0.07))]
    L.bm_sweep(tb, path, [(-tw / 2, -tt), (tw / 2, -tt), (tw / 2, 0), (-tw / 2, 0)], up=(0, 1, 0))
    _ = ztop
    obj(tb, f"{name}_скотч", coll, [m["tape"]], r, smooth=30)
    return r



# ---------------------------------------------------------------- общие: полоса-сетка, сечение сетки плоскостью

def strip(bm, rows: list) -> list:
    """Поверхность по рядам точек одинаковой длины (не замкнутая): rows[j][i]."""
    vs = [[bm.verts.new(p) for p in row] for row in rows]
    faces = []
    for j in range(len(vs) - 1):
        for i in range(len(vs[j]) - 1):
            faces.append(bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i])))
    return faces


def corner_cap(bm, cx: float, cy: float, sx: int, sy: int, rc: float, z0: float, z1: float, wing: float = 0.045,
               bottom: bool = True) -> None:
    """Штампованный уголок поверх скруглённого угла корпуса (центр дуги — cx, cy): крыло по торцу, дуга, крыло по
    длинной стороне; снизу — загиб под дно веером к центру дуги."""
    ro = rc + 0.0015
    pts = [(cx + sx * ro, cy - sy * wing * (1 - k / 4)) for k in range(5)]
    pts += [(cx + sx * ro * math.cos(a), cy + sy * ro * math.sin(a)) for a in [(math.pi / 2) * k / 8 for k in range(1, 8)]]
    pts += [(cx - sx * wing * k / 4, cy + sy * ro) for k in range(5)]
    rows = [[V((x, y, z)) for x, y in pts] for z in (z0, (z0 + z1) / 2, z1)]
    strip(bm, rows)
    if bottom:
        c = V((cx, cy, z0))
        rim = [V((x, y, z0)) for x, y in pts]
        strip(bm, [rim, [c + (p - c) * 0.6 for p in rim]])


def smooth_path(points: list, n: int = 6) -> list:
    """Сглаженный путь (Катмулл — Ром) через точки: ремни и стропы без изломов."""
    pts = [V(p) for p in points]
    out = []
    for i in range(len(pts) - 1):
        p0, p1, p2 = pts[max(i - 1, 0)], pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return out


def section(me, x0: float) -> list:
    """Сечение сетки плоскостью x = x0: точки на рёбрах, упорядочены по углу вокруг центра сечения (y, z)."""
    pts = []
    for e in me.edges:
        a, b = me.vertices[e.vertices[0]].co, me.vertices[e.vertices[1]].co
        if (a.x - x0) * (b.x - x0) < 0:
            t = (x0 - a.x) / (b.x - a.x)
            pts.append(a.lerp(b, t))
    if not pts:
        return []
    cy = sum(p.y for p in pts) / len(pts)
    cz = sum(p.z for p in pts) / len(pts)
    pts.sort(key=lambda p: math.atan2(p.z - cz, p.y - cy))
    return pts


# ---------------------------------------------------------------- ящик для инструментов (раскладной)

def toolbox(coll, m, at, rng, open_: bool = False):
    """Стальной раскладной ящик: корпус с завальцованным верхом, два лотка с перегородками сверху; каждый лоток на двух
    параллельных рычагах с каждого торца (параллелограмм: лоток выходит наружу и чуть вверх, не наклоняясь), скоба-ручка
    на торцах, защёлка спереди. Открытый — лотки разведены."""
    r = L.root("ИЯ_ящик_инструменты" + ("_открыт" if open_ else ""), coll, at)
    Lx, Wy, Hb = 0.46, 0.2, 0.15
    tray_h, R = 0.055, 0.08
    alpha, beta = math.radians(50), math.radians(25)
    bm = bmesh.new()
    rings = [(0.004, L.rrect(Lx - 0.008, Wy - 0.008, 0.01, 3)), (0.01, L.rrect(Lx, Wy, 0.012, 3)), (Hb, L.rrect(Lx, Wy, 0.012, 3))]
    loft(bm, rings, cap_first=True)
    body = obj(bm, "ИЯ_корпус", coll, [m["tool_paint"]], r, smooth=40)
    sol = body.modifiers.new("Лист", "SOLIDIFY")
    sol.thickness = 0.001
    sol.offset = -1
    eb = bmesh.new()
    L.bm_sweep(eb, [V((x, y, Hb)) for x, y in L.rrect(Lx + 0.004, Wy + 0.004, 0.014, 3)],
               [(0.0025 * math.cos(a), 0.0025 * math.sin(a)) for a in [TAU * i / 8 for i in range(8)]], closed=True)
    # скоба-ручка на торцах: ось у верха торцов, дуга над ящиком
    for s in (-1, 1):
        L.bm_box(eb, (s * Lx / 2 - (0.003 if s > 0 else 0), -0.012, Hb - 0.03), (s * Lx / 2 + (0.003 if s < 0 else 0), 0.012, Hb - 0.005))
    pipe(eb, [(-Lx / 2 - 0.006, 0, Hb - 0.018), (-Lx / 2 - 0.008, 0, Hb + 0.13), (-0.05, 0, Hb + 0.16), (0.05, 0, Hb + 0.16),
              (Lx / 2 + 0.008, 0, Hb + 0.13), (Lx / 2 + 0.006, 0, Hb - 0.018)], 0.004, segs=10, bend=0.04)
    obj(eb, "ИЯ_кант_ручка", coll, [m["tool_paint"]], r, smooth=50)
    gb = bmesh.new()
    B.pipe(gb, [(-0.05, 0, Hb + 0.16), (0.05, 0, Hb + 0.16)], 0.011, segs=14)
    obj(gb, "ИЯ_накладка_ручки", coll, [m["plastic_black"]], r, smooth=60)
    for s, tag in ((-1, "лоток_перед"), (1, "лоток_зад")):
        # рычаги: точки на корпусе (B) и на лотке (T = B + a); лоток — узел у своей точки T1 закрытого
        b1, b2 = V((0, s * 0.073, 0.119)), V((0, s * 0.096, 0.119))
        a0 = V((0, -s * math.sin(alpha), math.cos(alpha))) * R
        a1 = V((0, s * math.sin(beta), math.cos(beta))) * R
        t1 = b1 + a0
        tb = bmesh.new()
        y0, y1 = sorted((s * 0.003, s * 0.099))
        z0 = Hb + 0.002
        rings = [(z0, L.rrect(Lx - 0.004, y1 - y0, 0.008, 3, 0, (y0 + y1) / 2)),
                 (z0 + tray_h, L.rrect(Lx - 0.004, y1 - y0, 0.008, 3, 0, (y0 + y1) / 2))]
        loft(tb, rings, cap_first=True)
        for k in (-1, 0, 1):
            L.bm_box(tb, (k * 0.115 - 0.0006, y0 + 0.004, z0 + 0.002), (k * 0.115 + 0.0006, y1 - 0.004, z0 + tray_h - 0.008))
        tray = part_at(tb, f"ИЯ_{tag}", coll, [m["tool_paint"]], r, tuple(t1), smooth=40)
        ts = tray.modifiers.new("Лист", "SOLIDIFY")
        ts.thickness = 0.001
        ts.offset = -1
        # рычаги снаружи торцов: плоские полосы от B к T (у открытого — повёрнуты)
        a = a1 if open_ else a0
        ab = bmesh.new()
        for sx in (-1, 1):
            x = sx * (Lx / 2 + 0.004 + (0.004 if s > 0 else 0))
            for b in (b1, b2):
                p0, p1 = V((x, b.y, b.z)), V((x, b.y + a.y, b.z + a.z))
                L.bm_sweep(ab, [p0, p1], [(-0.0012, -0.007), (0.0012, -0.007), (0.0012, 0.007), (-0.0012, 0.007)], up=(1, 0, 0))
                for p in (p0, p1):
                    L.bm_cyl(ab, p - V((0.003 * sx, 0, 0)), p + V((0.003 * sx, 0, 0)), 0.004, segs=10)
        obj(ab, f"ИЯ_рычаги_{tag}", coll, [m["hardware"]], r, smooth=50)
        if open_:
            tray.location = tray.location + (a1 - a0)
    # защёлка спереди: язычок на корпусе
    lb = bmesh.new()
    L.bm_box(lb, (-0.015, -Wy / 2 - 0.003, Hb - 0.04), (0.015, -Wy / 2, Hb - 0.008))
    L.bm_box(lb, (-0.008, -Wy / 2 - 0.009, Hb - 0.034), (0.008, -Wy / 2 - 0.003, Hb + 0.012))
    obj(lb, "ИЯ_защёлка", coll, [m["hardware"]], r, smooth=50)
    return r


# ---------------------------------------------------------------- чемодан

def shell_half(bm, W: float, D2: float, Hb: float, zc: float, y_plane: float, side: int, rr: float, grooves: list,
               cuts: int = 15) -> None:
    """Половина жёсткого корпуса: скруглённая коробка глубиной 2·D2, срез по плоскости разъёма; на лице — продольные
    канавки (вдавлены на 3 мм)."""
    tmp = bmesh.new()
    rounded_box(tmp, (W, 2 * D2, Hb), rr, cuts=cuts, center=(0, y_plane, zc))
    drop = [v for v in tmp.verts if (v.co.y - y_plane) * side < -1e-5]
    bmesh.ops.delete(tmp, geom=drop, context="VERTS")
    for v in tmp.verts:
        face = (v.co.y - y_plane) * side
        if face > D2 - 0.02:
            k = min(1.0, (face - (D2 - 0.02)) / 0.012)
            for gx in grooves:
                d = abs(v.co.x - gx) / 0.01
                if d < 1.0:
                    edge = min(1.0, (Hb / 2 - abs(v.co.z - zc)) / 0.06)
                    v.co.y -= side * 0.0045 * (1 - d * d) * k * max(0.0, edge)
    me = bpy.data.meshes.new("tmp")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


def suitcase(coll, m, at, rng, open_: bool = False):
    """Жёсткий чемодан на четырёх колёсах: две створки из поликарбоната (передняя 110 мм, задняя 130 мм) с продольными
    канавками, молния по разъёму с бегунками, колёса — по паре на поворотной вилке в корпусах по углам, выдвижная ручка
    в нише сверху, ручки сверху и сбоку, кодовый замок; внутри подкладка, ремни крест-накрест и перегородка на молнии.
    Раскрытый — лежит на спине, передняя створка откинута на петле (по длинной стороне) лицом вниз."""
    r = L.root("ЧМ_чемодан" + ("_раскрыт" if open_ else ""), coll, at)
    W, Hb, z_low = 0.43, 0.6, 0.058
    zc = z_low + Hb / 2
    dF, dB, band = 0.11, 0.13, 0.016
    yF, yB = -band / 2, band / 2
    grooves = [-0.13, -0.065, 0.0, 0.065, 0.13]
    bb = bmesh.new()
    shell_half(bb, W, dB, Hb, zc, yB, 1, 0.05, grooves)
    back = obj(bb, "ЧМ_створка_зад", coll, [m["shell"], m["lining"]], r, smooth=50)
    hinge = V((-W / 2 + 0.012, yF, zc))
    fb = bmesh.new()
    shell_half(fb, W, dF, Hb, zc, yF, -1, 0.05, grooves)
    front = part_at(fb, "ЧМ_створка", coll, [m["shell"], m["lining"]], r, tuple(hinge), smooth=50)
    for ob in (back, front):
        so = ob.modifiers.new("Корпус", "SOLIDIFY")
        so.thickness = 0.0025
        so.offset = -1
        so.material_offset = 1
        md = ob.modifiers.new("Гладкость", "SUBSURF")
        md.levels = 1
        md.render_levels = 2
    # молния по разъёму: лента и зубья — валик вдоль кольца; бегунки сверху
    ring = [V((x, 0.0, zc + z)) for x, z in L.rrect(W - 0.002, Hb - 0.002, 0.05, 8)]
    zb = bmesh.new()
    L.bm_sweep(zb, ring, [(-band / 2, -0.003), (band / 2, -0.003), (band / 2, 0.0), (0.003, 0.0016), (-0.003, 0.0016),
                          (-band / 2, 0.0)], closed=True, up=(0, 1, 0))
    for x in (-0.03, 0.03):
        L.bm_box(zb, (x - 0.006, -0.004, z_low + Hb + 0.001), (x + 0.006, 0.004, z_low + Hb + 0.006))
        rounded_box(zb, (0.012, 0.004, 0.03), 0.0018, cuts=2, center=(x, -0.006, z_low + Hb - 0.012))
    obj(zb, "ЧМ_молния", coll, [m["zip"]], r, smooth=40)
    # колёса: корпус на углу, поворотная вилка, пара колёс на оси; у передней створки — её деталями (раскрытый чемодан
    # уносит их вместе со створкой)
    parts = {}
    for side_tag in ("зад", "перед"):
        parts[side_tag] = (bmesh.new(), bmesh.new())
    for sx in (-1, 1):
        for side_tag, yy in (("перед", yF - dF + 0.045), ("зад", yB + dB - 0.05)):
            wb, cb = parts[side_tag]
            x = sx * (W / 2 - 0.045)
            rounded_box(cb, (0.07, 0.06, 0.035), 0.012, cuts=3, center=(x, yy, z_low + 0.012))
            L.bm_cyl(cb, (x, yy, z_low - 0.006), (x, yy, z_low - 0.012), 0.016, segs=16)
            L.bm_box(cb, (x - 0.02, yy - 0.012, z_low - 0.03), (x + 0.02, yy + 0.012, z_low - 0.01))
            for dx in (-0.011, 0.011):
                lathe(wb, [(0.0, -0.007), (0.016, -0.007), (0.022, -0.006), (0.024, 0.0), (0.022, 0.006), (0.016, 0.007), (0.0, 0.007)],
                      segs=24, origin=(x + dx, yy + 0.008, 0.024), axis=(1, 0, 0))
            L.bm_cyl(cb, (x - 0.02, yy + 0.008, 0.024), (x + 0.02, yy + 0.008, 0.024), 0.0035, segs=10)
    # ниша выдвижной ручки сверху задней створки; ручка сверху и сбоку — на передней; замок
    zt = z_low + Hb
    wb, cb = parts["зад"]
    rounded_box(cb, (0.22, 0.04, 0.012), 0.006, cuts=3, center=(0, yB + 0.035, zt + 0.002))
    rounded_box(cb, (0.2, 0.026, 0.02), 0.009, cuts=3, center=(0, yB + 0.035, zt + 0.012))
    for z in (zc - 0.06, zc + 0.06):
        rounded_box(cb, (0.012, 0.03, 0.03), 0.005, cuts=2, center=(W / 2 + 0.003, yB + 0.05, z))
    pipe(cb, [(W / 2 + 0.006, yB + 0.05, zc - 0.06), (W / 2 + 0.022, yB + 0.05, zc - 0.05), (W / 2 + 0.022, yB + 0.05, zc + 0.05),
              (W / 2 + 0.006, yB + 0.05, zc + 0.06)], 0.008, segs=12, bend=0.012)
    rounded_box(cb, (0.008, 0.05, 0.035), 0.003, cuts=2, center=(-W / 2 - 0.002, yB + 0.03, zc + 0.15))
    wb, cb = parts["перед"]
    for x in (-0.06, 0.06):
        rounded_box(cb, (0.03, 0.03, 0.012), 0.005, cuts=2, center=(x, yF - 0.04, zt + 0.003))
    pipe(cb, [(-0.06, yF - 0.04, zt + 0.006), (-0.05, yF - 0.04, zt + 0.022), (0.05, yF - 0.04, zt + 0.022), (0.06, yF - 0.04, zt + 0.006)],
         0.008, segs=12, bend=0.012)
    for side_tag, parent in (("зад", r), ("перед", front)):
        wb, cb = parts[side_tag]
        o1 = obj(wb, f"ЧМ_колёса_{side_tag}", coll, [m["rubber"]], parent, smooth=50)
        o2 = obj(cb, f"ЧМ_фурнитура_{side_tag}", coll, [m["plastic_black"]], parent, smooth=45)
        if parent is front:
            for o in (o1, o2):
                o.data.transform(Matrix.Translation(-hinge))
                o.matrix_parent_inverse = Matrix.Identity(4)
    # внутри: ремни крест-накрест в задней створке, перегородка на молнии в передней
    ib = bmesh.new()
    for a in (-1, 1):
        p0, p1 = V((-W / 2 + 0.05, yB + 0.06, zc - a * (Hb / 2 - 0.08))), V((W / 2 - 0.05, yB + 0.06, zc + a * (Hb / 2 - 0.08)))
        L.bm_sweep(ib, [p0, p0.lerp(p1, 0.5) + V((0, -0.01, 0)), p1], [(-0.0125, -0.001), (0.0125, -0.001), (0.0125, 0.001),
                                                                       (-0.0125, 0.001)], up=(0, 1, 0))
    rounded_box(ib, (0.04, 0.008, 0.03), 0.003, cuts=2, center=(0, yB + 0.047, zc))
    straps = obj(ib, "ЧМ_ремни", coll, [m["webbing"]], r, smooth=40)
    _ = straps
    pb = bmesh.new()
    rows = []
    for j in range(9):
        z = zc - (Hb / 2 - 0.035) + (Hb - 0.07) * j / 8
        rows.append([V((x, yF - 0.012 - 0.004 * math.sin(math.pi * j / 8) * math.sin(math.pi * (x + W / 2 - 0.035) / (W - 0.07)), z))
                     for x in [-W / 2 + 0.035 + (W - 0.07) * i / 10 for i in range(11)]])
    strip(pb, rows)
    panel = obj(pb, "ЧМ_перегородка", coll, [m["lining"]], front, smooth=40)
    panel.data.transform(Matrix.Translation(-hinge))
    panel.matrix_parent_inverse = Matrix.Identity(4)
    if open_:
        # лежит на спине: задняя створка — на полу, середина — над исходной точкой
        r.rotation_euler = (-math.radians(90), 0, 0)
        r.location = V(at) + V((0, -zc, dB + yB))
        front.rotation_euler = (0, 0, -math.radians(176))
    return r


# ---------------------------------------------------------------- спортивная сумка (ткань)

def duffel(coll, m, at, rng, half: bool = False):
    """Спортивная сумка 600 × 300 × 300 из полиэстера: рукав со скруглёнными торцами, симуляция ткани с внутренним
    давлением на полу (полная — давление выше, полупустая — осела), затем молния по верху, две стропы вокруг корпуса
    с ручками над ним, D-кольца на торцах и плечевой ремень на полу."""
    r = L.root("СС_сумка" + ("_полупустая" if half else ""), coll, at)
    Lx, R0 = 0.6, 0.15
    n_ring, n_len = 64, 40
    bm = bmesh.new()
    rings = []
    for j in range(n_len + 1):
        x = -Lx / 2 + Lx * j / n_len
        ring = []
        for i in range(n_ring):
            a = TAU * i / n_ring
            c, s = math.cos(a), math.sin(a)
            p = 2.6
            y = R0 * math.copysign(abs(c) ** (2 / p), c)
            z = R0 * math.copysign(abs(s) ** (2 / p), s) + R0 + 0.03
            ring.append(bm.verts.new((x, y, z)))
        rings.append(ring)
    for j in range(n_len):
        for i in range(n_ring):
            k = (i + 1) % n_ring
            bm.faces.new((rings[j][i], rings[j][k], rings[j + 1][k], rings[j + 1][i]))
    # торцы — концентрическими кольцами (веер из одной вершины под давлением выстреливал иглой)
    for ring, flip in ((rings[0], True), (rings[-1], False)):
        prev = ring
        x0 = ring[0].co.x
        for f_ in (0.8, 0.6, 0.4, 0.2):
            cur = [bm.verts.new((x0, v.co.y * f_, (v.co.z - R0 - 0.03) * f_ + R0 + 0.03)) for v in ring]
            for i in range(n_ring):
                k = (i + 1) % n_ring
                q = (prev[i], prev[k], cur[k], cur[i])
                bm.faces.new(q[::-1] if flip else q)
            prev = cur
        c = bm.verts.new((x0, 0.0, R0 + 0.03))
        for i in range(n_ring):
            k = (i + 1) % n_ring
            bm.faces.new((prev[k], prev[i], c) if flip else (prev[i], prev[k], c))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("СС_ткань")
    bm.to_mesh(me)
    bm.free()
    bag = bpy.data.objects.new("СС_корпус", me)
    coll.objects.link(bag)
    # в начале корня: matrix_world здесь брать нельзя — матрица корня ещё не пересчитана, сумка встала бы на 2·at,
    # мимо пола
    bag.parent = r
    bag.matrix_parent_inverse = Matrix.Identity(4)
    bag.location = (0, 0, 0)
    # пол — коллайдер
    gb = bmesh.new()
    L.bm_box(gb, (-1, -1, -0.3), (1, 1, -0.012))
    gm = bpy.data.meshes.new("пол")
    gb.to_mesh(gm)
    ground = bpy.data.objects.new("СС_пол", gm)
    bpy.context.scene.collection.objects.link(ground)
    ground.matrix_world = Matrix.Translation(V(at))
    ground.modifiers.new("Столкновение", "COLLISION")
    # пол опущен на поле столкновения (2 см пола + 6 мм ткани ≈ 12 мм над верхом коробки пола — ткань ляжет на z ≈ 0);
    # тонкое поле (2 + 3 мм) ткань проскакивала насквозь
    ground.collision.thickness_outer = 0.006
    ground.collision.cloth_friction = 8.0
    cl = bag.modifiers.new("Ткань", "CLOTH")
    s = cl.settings
    s.quality = 8
    s.mass = 0.004
    s.tension_stiffness, s.compression_stiffness, s.shear_stiffness = 40.0, 40.0, 20.0
    s.bending_stiffness = 0.15
    s.air_damping = 2.0
    s.use_pressure = True
    s.uniform_pressure_force = 0.0 if half else 0.25
    stuff = None
    if True:
        # вещи внутри: у полной — почти во весь объём (ткань облегает буханкой), у полупустой — внизу (верх без давления
        # ложится на них складками); коллайдер после симуляции удаляется
        sb = bmesh.new()
        if half:
            rounded_box(sb, (Lx - 0.12, 2 * R0 - 0.07, 0.14), 0.04, cuts=4, center=(0, 0, 0.075))
        else:
            rounded_box(sb, (Lx - 0.07, 2 * R0 - 0.035, 0.235), 0.07, cuts=5, center=(0, 0, 0.122))
        smesh = bpy.data.meshes.new("вещи")
        sb.to_mesh(smesh)
        stuff = bpy.data.objects.new("СС_вещи", smesh)
        bpy.context.scene.collection.objects.link(stuff)
        stuff.matrix_world = Matrix.Translation(V(at))
        stuff.modifiers.new("Столкновение", "COLLISION")
        stuff.collision.thickness_outer = 0.004
        stuff.collision.cloth_friction = 6.0
    s.pressure_factor = 1.0
    cl.collision_settings.use_collision = True
    cl.collision_settings.distance_min = 0.006
    cl.collision_settings.use_self_collision = False
    cl.collision_settings.collision_quality = 4
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, 90
    cl.point_cache.frame_start, cl.point_cache.frame_end = 1, 90
    for f in range(1, 91):
        sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    done = bpy.data.meshes.new_from_object(bag.evaluated_get(dg), depsgraph=dg)
    bag.modifiers.clear()
    old = bag.data
    bag.data = done
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(ground)
    if stuff is not None:
        bpy.data.objects.remove(stuff)
    sc.frame_set(1)
    bag.matrix_parent_inverse = Matrix.Identity(4)
    bag.location = (0, 0, 0)
    bag.data.materials.append(m["fabric"])
    for p in bag.data.polygons:
        p.use_smooth = True
    sd = bag.modifiers.new("Ткань", "SOLIDIFY")
    sd.thickness = 0.0015
    sd.offset = -1
    ss = bag.modifiers.new("Гладкость", "SUBSURF")
    ss.levels = 1
    ss.render_levels = 1
    me = bag.data
    # молния по гребню: самые верхние точки вдоль длины
    top = []
    for j in range(1, n_len):
        x = -Lx / 2 + Lx * j / n_len
        cand = [v.co for v in me.vertices if abs(v.co.x - x) < Lx / n_len * 0.5]
        if cand:
            best = max(cand, key=lambda c: c.z - 2.0 * abs(c.y))
            top.append(V((x, best.y, best.z + 0.002)))
    # гребень сглажен: у осевшей ткани верхние точки скачут складками
    top = [V((p.x, sum(q.y for q in top[max(0, i - 3):i + 4]) / len(top[max(0, i - 3):i + 4]),
              sum(q.z for q in top[max(0, i - 3):i + 4]) / len(top[max(0, i - 3):i + 4]) + 0.002)) for i, p in enumerate(top)]
    zb = bmesh.new()
    L.bm_sweep(zb, top, [(-0.016, -0.001), (0.016, -0.001), (0.016, 0.0006), (0.003, 0.0022), (-0.003, 0.0022), (-0.016, 0.0006)],
               up=(0, 0, 1))
    tab = top[len(top) // 3]
    rounded_box(zb, (0.035, 0.012, 0.004), 0.0018, cuts=2, center=(tab.x, tab.y - 0.01, tab.z + 0.003))
    obj(zb, "СС_молния", coll, [m["zip"]], r, smooth=40)
    # стропы вокруг корпуса и ручки над ним; D-кольца на торцах; плечевой ремень
    wbm = bmesh.new()
    prof = [(-0.019, 0.0), (0.019, 0.0), (0.019, 0.0018), (-0.019, 0.0018)]
    tops = []
    for xs in (-0.13, 0.13):
        sec = section(me, xs)
        if len(sec) > 8:
            cy = sum(p.y for p in sec) / len(sec)
            cz = sum(p.z for p in sec) / len(sec)
            ring_p = [p + (V((0, p.y - cy, p.z - cz)).normalized() * 0.0025) for p in sec[::2]]
            L.bm_sweep(wbm, ring_p, prof, closed=True, up=(1, 0, 0))
            topp = max(ring_p, key=lambda p: p.z)
            tops.append(topp)
    if len(tops) == 2:
        for dy in (-0.035, 0.035):
            p0, p1 = tops[0] + V((0, dy, 0)), tops[1] + V((0, dy, 0))
            mid = (p0 + p1) / 2 + V((0, -dy * 0.3, 0.09))
            L.bm_sweep(wbm, smooth_path([p0, p0 + V((0.02, 0, 0.05)), mid, p1 + V((-0.02, 0, 0.05)), p1], 6), prof, up=(0, 1, 0))
        gx = (tops[0] + tops[1]) / 2 + V((0, 0, 0.095))
        rounded_box(wbm, (0.12, 0.05, 0.03), 0.012, cuts=3, center=(gx.x, gx.y, gx.z))
    ends = []
    for s_ in (-1, 1):
        cand = [v.co for v in me.vertices if v.co.x * s_ > Lx / 2 - 0.02]
        if cand:
            e = max(cand, key=lambda c: c.z)
            ends.append(V((s_ * (Lx / 2 + 0.006), e.y, e.z - 0.03)))
    for e in ends:
        lathe(wbm, [(0.012, -0.002), (0.016, -0.002), (0.016, 0.002), (0.012, 0.002)], segs=14, origin=tuple(e), axis=(0, 1, 0),
              closed=True)
    if len(ends) == 2:
        p0, p1 = ends[0] + V((-0.02, 0, -0.01)), ends[1] + V((0.02, 0, -0.01))
        path = [p0, p0 + V((-0.04, -0.05, -e.z + 0.012)), V((-0.2, -0.32, 0.003)), V((0.15, -0.28, 0.003)),
                p1 + V((0.04, -0.05, -e.z + 0.012)), p1]
        flat = [V((q.x, q.y, max(q.z, 0.0015))) for q in smooth_path(path, 8)]  # сглаженная кривая не уходит под пол
        L.bm_sweep(wbm, flat, [(-0.019, 0.0), (0.019, 0.0), (0.019, 0.002), (-0.019, 0.002)], up=(0, 0, 1))
        rounded_box(wbm, (0.16, 0.06, 0.012), 0.006, cuts=3, center=(-0.03, -0.31, 0.007))
    obj(wbm, "СС_стропы", coll, [m["webbing"]], r, smooth=35)
    return r


# ---------------------------------------------------------------- состав группы А

ITEMS_A = [
    ("Ящик для инструментов", lambda c, m, at, rng: toolbox(c, m, at, rng, False), 0.55),
    ("Ящик для инструментов открыт", lambda c, m, at, rng: toolbox(c, m, at, rng, True), 0.75),
    ("Чемодан", lambda c, m, at, rng: suitcase(c, m, at, rng, False), 0.55),
    ("Чемодан раскрыт", lambda c, m, at, rng: suitcase(c, m, at, rng, True), 1.0),
    ("Сумка", lambda c, m, at, rng: duffel(c, m, at, rng, False), 0.75),
    ("Сумка полупустая", lambda c, m, at, rng: duffel(c, m, at, rng, True), 0.75),
    ("Ящик под патроны", lambda c, m, at, rng: crate(c, m, at, rng, "ЯП_ящик_патроны", 0.49, 0.37, 0.17, 2, True, False), 0.6),
    ("Ящик под патроны открыт", lambda c, m, at, rng: crate(c, m, at, rng, "ЯП_ящик_патроны", 0.49, 0.37, 0.17, 2, True, True), 0.6),
    ("Ящик ЗИП", lambda c, m, at, rng: crate(c, m, at, rng, "ЯЗ_ящик_ЗИП", 1.0, 0.42, 0.33, 3, False, False), 1.15),
    ("Ящик ЗИП открыт", lambda c, m, at, rng: crate(c, m, at, rng, "ЯЗ_ящик_ЗИП", 1.0, 0.42, 0.33, 3, False, True), 1.15),
    ("Сундук", lambda c, m, at, rng: trunk(c, m, at, rng, False), 0.9),
    ("Сундук открыт", lambda c, m, at, rng: trunk(c, m, at, rng, True), 0.9),
    ("Коробка", lambda c, m, at, rng: carton(c, m, at, rng, False), 0.7),
    ("Коробка открыта", lambda c, m, at, rng: carton(c, m, at, rng, True), 0.9),
]


def build(out: str) -> list:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    top = L.collection("Партия3_А_ящики_вещи_v01")
    m = mats()
    rng = random.Random(33)
    x = 0.0
    placed = []
    for label, fn, width in ITEMS_A:
        c = L.collection(label, top)
        root = fn(c, m, (x + width / 2, 0.0, 0.0), rng)
        placed.append((label, c, root))
        x += width + 0.4
    B.studio(L.collection("Студия"), x)
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


def preview(placed: list, folder: str, only: set | None = None) -> None:
    wall = bpy.data.objects.get("студия_стена")
    if wall:
        wall.hide_render = True
    os.makedirs(folder, exist_ok=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 900, 700
    cam = sc.camera
    dg = bpy.context.evaluated_depsgraph_get()
    for i, (label, coll, root) in enumerate(placed):
        if only and i not in only:
            continue
        pts = []
        for ob in coll.all_objects:
            if ob.type == "MESH" and not ob.hide_render:
                ev = ob.evaluated_get(dg)
                pts += [ev.matrix_world @ V(c) for c in ev.bound_box]
        mn = V((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = V((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        c = (mn + mx) / 2
        size = (mx - mn).length
        for k, (az, el) in enumerate(((-35, 24), (40, 40))):
            a, e = math.radians(az), math.radians(el)
            dist = size * 1.25 + 0.2
            cam.location = c + V((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
            cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
            cam.data.lens = 40
            sc.render.filepath = os.path.join(folder, f"{i:02d}_{k}.png")
            bpy.ops.render.render(write_still=True)
        print("preview", label, flush=True)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    placed = build(argv[0])
    if len(argv) >= 3 and argv[1] == "preview":
        only = {int(s) for s in argv[3].split(",")} if len(argv) >= 4 and argv[3] else None
        preview(placed, argv[2], only)
