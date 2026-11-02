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
        "paper": L.material("Бумага", (0.85, 0.84, 0.8), 0.8),
        "tape_clear": L.material("Скотч_прозрачный", (0.8, 0.8, 0.75), 0.2),
        "pin_metal": L.material("Кнопка_сталь", (0.6, 0.6, 0.58), 0.35, 1.0),
        "pin_plastic": L.material("Кнопка_пластик", (0.7, 0.1, 0.08), 0.3),
        "wood_slat": L.material("Рейка_дерево", (0.55, 0.42, 0.28), 0.6),
        "frame_wood": L.material("Багет_дерево", (0.35, 0.22, 0.12), 0.45),
        "frame_plastic": L.material("Рама_пластик", (0.55, 0.45, 0.25), 0.35),
        "glass": L.material("Стекло", (0.8, 0.85, 0.85), 0.05, 0.0, 0.3),
        "steel_pc": L.material("Сталь_корпус", (0.04, 0.04, 0.045), 0.45, 0.6),
        "mesh_pc": L.material("Сетка_фасад", (0.03, 0.03, 0.03), 0.6),
        "pcb": L.material("Плата", (0.03, 0.05, 0.04), 0.45),
        "glass_tint": L.material("Стекло_тёмное", (0.2, 0.22, 0.24), 0.04, 0.0, 0.45),
        "screen": L.material("Экран", (0.01, 0.01, 0.012), 0.08),
        "keycap": L.material("Клавиши", (0.025, 0.025, 0.025), 0.55),
        "laptop_alu": L.material("Корпус_ноутбук", (0.35, 0.35, 0.37), 0.35, 0.8),
        "tube_plastic": L.material("Тубус_пластик", (0.05, 0.05, 0.055), 0.4),
        "book_cover": L.material("Переплёт", (0.2, 0.25, 0.4), 0.6),
        "book_pages": L.material("Обрез", (0.85, 0.83, 0.77), 0.8),
        "notebook_cover": L.material("Обложка_тетради", (0.3, 0.5, 0.35), 0.5),
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



# ---------------------------------------------------------------- группа Б: бумага на стене, рамы

def sheet(bm, w: float, h: float, step: float, place, keep=None) -> None:
    """Лист сеткой (шаг step): place(x, z) → точка; x — поперёк (−w/2…w/2), z — от верха вниз (0…−h); keep(x, z) —
    оставить ли клетку (рваный край)."""
    nx, nz = max(2, round(w / step)), max(2, round(h / step))
    vs = {}

    def vert(i, j):
        if (i, j) not in vs:
            vs[(i, j)] = bm.verts.new(place(-w / 2 + w * i / nx, -h * j / nz))
        return vs[(i, j)]

    for j in range(nz):
        for i in range(nx):
            xc, zc = -w / 2 + w * (i + 0.5) / nx, -h * (j + 0.5) / nz
            if keep is not None and not keep(xc, zc):
                continue
            bm.faces.new((vert(i, j), vert(i + 1, j), vert(i + 1, j + 1), vert(i, j + 1)))


def buckle(x: float, z: float, w: float, h: float, pins: list, amp: float, seed: float) -> float:
    """Волна бумаги от сырости: плавные бугры (отход от стены, м), у кнопок и скотча — ноль."""
    a = math.sin(x * 9.0 + seed) * math.sin(z * 7.0 + seed * 1.7) * 0.6 + math.sin(x * 4.1 - z * 3.3 + seed * 0.7) * 0.4
    hold = 1.0
    for px, pz in pins:
        hold *= 1.0 - math.exp(-((x - px) ** 2 + (z - pz) ** 2) / 0.012)
    edge = min(1.0, (w / 2 - abs(x)) / 0.05, (h / 2 - abs(z + h / 2)) / 0.05)
    return amp * (0.55 + 0.45 * a) * hold * (0.6 + 0.4 * max(0.0, edge))


def curl(x: float, z: float, hinge_p, hinge_d, R: float, droop: float = 0.0, grow: float = 0.0015):
    """Отклеившийся угол заворачивается от стены: точки за линией отрыва (через hinge_p вдоль hinge_d) свёрнуты
    спиралью от радиуса R (каждый виток шире на grow — рулон не проходит сам в себя); возвращает (x, z, отход)."""
    px, pz = hinge_p
    dx, dz = hinge_d
    n = math.hypot(dx, dz)
    dx, dz = dx / n, dz / n
    nx_, nz_ = dz, -dx                        # нормаль к линии в плоскости листа
    s = (x - px) * nx_ + (z - pz) * nz_
    if s <= 0:
        return x, z, 0.0
    ang = s / R
    Rk = R + grow * ang / TAU
    along = Rk * math.sin(ang)
    off = Rk * (1 - math.cos(ang))
    bx, bz = x - nx_ * s, z - nz_ * s
    return bx + nx_ * along, bz + nz_ * along - droop * (s ** 2), off


def pushpin(bm, at, kind: str = "кнопка") -> None:
    """Кнопка: советская — плоская шляпка Ø11 с выпуклостью; канцелярская — пластиковая головка на ножке."""
    x, y, z = at
    if kind == "кнопка":
        lathe(bm, [(0.0, 0.0), (0.0055, 0.0), (0.0055, -0.0004), (0.0045, -0.001), (0.0, -0.0013)], segs=20, origin=(x, y, z),
              axis=(0, 1, 0))
    else:
        lathe(bm, [(0.0, 0.0), (0.0048, 0.0), (0.0048, -0.0015), (0.0028, -0.0025), (0.0026, -0.009), (0.004, -0.0105),
                   (0.004, -0.0125), (0.0, -0.013)], segs=16, origin=(x, y, z), axis=(0, 1, 0))


def tape_piece(bm, cx: float, cz: float, ang: float, y: float, lw=(0.045, 0.019), lift=None) -> None:
    """Кусок скотча на углу листа: тонкая сетка 6 × 3 с лёгкой морщиной; lift(x, z) — отход (отклеился)."""
    L_, W_ = lw
    ca, sa = math.cos(ang), math.sin(ang)
    rows = []
    for j in range(4):
        row = []
        for i in range(7):
            u, v = -L_ / 2 + L_ * i / 6, -W_ / 2 + W_ * j / 3
            x, z = cx + u * ca - v * sa, cz + u * sa + v * ca
            off = 0.00025 * math.sin(i * 1.9 + j * 2.3)
            if lift is not None:
                off += lift(x, z)
            row.append(V((x, y - off, z)))
        rows.append(row)
    strip(bm, rows)


def poster(coll, m, at, rng, name: str, w: float, h: float, mount: str, state: str = "целый", amp: float = 0.004):
    """Лист на стене (корень — середина верха у стены, лицо к −Y): волна от сырости, края чуть отходят. mount: «кнопки»
    (советские кнопки по углам и верху), «скотч» (куски по углам), «булавки» (канцелярские кнопки по углам).
    state: «надорван» — нижний угол оторван рваным краем, край отошёл; «угол» — верхний угол отклеился и завернулся;
    «свернулся» — верхние кнопки потеряны, лист свернулся сверху рулоном."""
    r = L.root(f"{name}{'' if state == 'целый' else '_' + state}", coll, at)
    seed = rng.uniform(0, 10)
    inset = 0.015
    pins = [(-w / 2 + inset, -inset), (w / 2 - inset, -inset), (-w / 2 + inset, -h + inset), (w / 2 - inset, -h + inset)]
    if mount == "кнопки" and w > 0.45:
        pins.append((0.0, -inset))
    lost = []
    if state == "угол":
        lost = [pins[1]]
    if state == "свернулся":
        lost = [pins[0], pins[1]] + ([pins[4]] if len(pins) > 4 else [])
    held = [p for p in pins if p not in lost]
    hinge = None
    if state == "угол":
        hinge = ((w / 2 - 0.16, 0.0), (-1.0, 1.25))
        R_ = 0.05
    if state == "свернулся":
        hinge = ((0.0, -h * 0.42), (-1.0, 0.0))
        R_ = 0.028
    tear_cx, tear_cz = w / 2, -h

    def keep(x, z):
        if state != "надорван":
            return True
        # оторван нижний угол: край рваный мелко (волокна), но линия отрыва одна
        jag = 0.006 * math.sin(x * 140 + seed) + 0.004 * math.sin(z * 210 + seed * 2) + 0.01 * math.sin((x - z) * 23 + seed)
        return (x - (w / 2 - 0.34)) / 0.34 + ((-h + 0.42) - z) / 0.42 < 1.0 + jag / 0.35

    def place(x, z):
        off = buckle(x, z, w, h, held, amp, seed)
        xx, zz = x, z
        if hinge is not None:
            xx, zz, c_off = curl(x, z, hinge[0], hinge[1], R_, droop=0.0)
            off += c_off
        if state == "надорван":
            # у рваного края лист отошёл от стены
            d = (x - (w / 2 - 0.34)) / 0.34 + ((-h + 0.42) - z) / 0.42
            off += 0.02 * max(0.0, d - 0.6) ** 2
        return V((xx, -0.0006 - off, zz))

    bm = bmesh.new()
    sheet(bm, w, h, 0.006 if state == "надорван" else 0.01, place, keep)
    ob = obj(bm, f"{name}_лист", coll, [m["paper"]], r, smooth=60)
    so = ob.modifiers.new("Бумага", "SOLIDIFY")
    so.thickness = 0.0003
    so.offset = 1
    hb = bmesh.new()
    if mount in ("кнопки", "булавки"):
        for px, pz in held:
            pushpin(hb, (px, -0.0006 - buckle(px, pz, w, h, held, amp, seed) - 0.0004, pz), "кнопка" if mount == "кнопки" else "булавка")
        # потерянные кнопки — дырочки от них остаются на текстуре; одна кнопка висит на углу (у «угла»)
    if mount == "скотч":
        tb = bmesh.new()
        for (px, pz), ang in zip(pins, (math.radians(45), math.radians(-45), math.radians(-45), math.radians(45))):
            if (px, pz) in lost:
                # отклеившийся кусок остался на завёрнутом углу
                xx, zz, c_off = curl(px, pz, hinge[0], hinge[1], R_)
                tape_piece(tb, xx, zz, ang, -0.0012 - c_off, lift=None)
                continue
            tape_piece(tb, px, pz, ang, -0.0012)
        obj(tb, f"{name}_скотч", coll, [m["tape_clear"]], r, smooth=50)
    if len(hb.verts):
        obj(hb, f"{name}_кнопки", coll, [m["pin_metal"] if mount == "кнопки" else m["pin_plastic"]], r, smooth=40)
    else:
        hb.free()
    return r


def calendar(coll, m, at, rng):
    """Настенный календарь 300 × 450 на пружине: подложка-картон, двенадцать листов веером снизу, проволочная пружина
    по верху, отверстие и гвоздь."""
    r = L.root("КЛ_календарь", coll, at)
    w, h = 0.3, 0.45
    bm = bmesh.new()
    L.bm_box(bm, (-w / 2, -0.0015, -h - 0.01), (w / 2, -0.0003, -0.008))
    ob = obj(bm, "КЛ_подложка", coll, [m["paper"]], r, bevel=0.0004, segs=1)
    _ = ob
    pb = bmesh.new()
    for k in range(12):
        y = -0.0016 - k * 0.00022
        lift = 0.0009 * (12 - k)

        def place(x, z, y=y, lift=lift, k=k):
            t = min(1.0, -z / h)
            return V((x, y - lift * t ** 3 - 0.0004 * math.sin(x * 20 + k), z - 0.016))
        sheet(pb, w - 0.004, h - 0.02, 0.02, place)
    obj(pb, "КЛ_листы", coll, [m["paper"]], r, smooth=60)
    wb = bmesh.new()
    for i in range(24):
        x = -w / 2 + 0.012 + (w - 0.024) * i / 23
        pts = [V((x + 0.0008 * math.sin(a), -0.0045 + 0.0045 * math.cos(a), -0.012 + 0.0055 * math.sin(a)))
               for a in [TAU * q / 10 for q in range(10)]]
        pipe(wb, pts, 0.0006, segs=6, closed=True)
    pipe(wb, [(0, 0.0, 0.004), (0, -0.012, 0.004)], 0.0012, segs=8)
    lathe(wb, [(0.0, 0.0), (0.0028, 0.0), (0.0028, -0.0008), (0.0, -0.001)], segs=14, origin=(0, -0.012, 0.004), axis=(0, -1, 0))
    obj(wb, "КЛ_пружина_гвоздь", coll, [m["pin_metal"]], r, smooth=50)
    return r


def chart(coll, m, at, rng, fallen: bool = False):
    """Учебная таблица 700 × 1000 на рейках: лист зажат парой деревянных реек сверху и снизу, шнур от концов верхней
    рейки на гвоздь. Сорванная — шнур с одной стороны лопнул, таблица висит углом, обрывок шнура свисает."""
    r = L.root("УТ_таблица" + ("_сорвана" if fallen else ""), coll, at)
    w, h = 0.7, 1.0
    drop = 0.14                                    # гвоздь выше верхней рейки
    seed = rng.uniform(0, 10)
    pivot = V((-w / 2 - 0.01, -0.008, -drop))       # левый конец верхней рейки — за него висит сорванная
    grp = bpy.data.objects.new("УТ_полотно", None)
    coll.objects.link(grp)
    grp.parent = r
    grp.location = pivot

    def place(x, z):
        bow = 0.006 * math.sin(math.pi * (-z) / h) + 0.002 * math.sin(x * 8 + seed)
        return V((x, -0.008 - bow, z - drop)) - pivot
    bm = bmesh.new()
    sheet(bm, w, h, 0.02, place)
    sh = obj(bm, "УТ_лист", coll, [m["paper"]], grp, smooth=60)
    so = sh.modifiers.new("Бумага", "SOLIDIFY")
    so.thickness = 0.0005
    rb = bmesh.new()
    for z in (-drop + 0.004, -drop - h - 0.004):
        for y0, y1 in ((-0.0035, -0.0003), (-0.0158, -0.0126)):
            L.bm_box(rb, (-w / 2 - 0.012, y0 - 0.004, z - 0.011), (w / 2 + 0.012, y1 - 0.004, z + 0.011))
    for v in rb.verts:
        v.co -= pivot
    obj(rb, "УТ_рейки", coll, [m["wood_slat"]], grp, bevel=0.0012, segs=1)
    cb = bmesh.new()
    nail = V((0, 0.0, 0.0))
    ends = [V((-w / 2 - 0.004, -0.009, -drop + 0.012)), V((w / 2 + 0.004, -0.009, -drop + 0.012))]
    if not fallen:
        pipe(cb, [ends[0], nail + V((0, -0.006, 0.0)), ends[1]], 0.0013, segs=8, bend=0.01)
    else:
        pipe(cb, [ends[0], nail + V((0, -0.006, 0.0))], 0.0013, segs=8)
    pipe(cb, [nail + V((0, 0.002, 0)), nail + V((0, -0.012, 0))], 0.0013, segs=8)
    lathe(cb, [(0.0, 0.0), (0.0028, 0.0), (0.0028, -0.0008), (0.0, -0.001)], segs=14, origin=(0, -0.012, 0.0), axis=(0, -1, 0))
    obj(cb, "УТ_шнур_гвоздь", coll, [m["rope"]], r, smooth=50)
    if fallen:
        # висит на левом конце: полотно повёрнуто вокруг него, обрывок шнура свисает с правого конца
        grp.rotation_euler = (0, math.radians(38), 0)
        fb = bmesh.new()
        e = ends[1] - pivot
        rot = Matrix.Rotation(math.radians(38), 3, "Y")
        e = rot @ e + pivot
        pipe(fb, [e, e + V((0.01, -0.004, -0.05)), e + V((0.004, -0.002, -0.11))], 0.0013, segs=8, bend=0.02)
        obj(fb, "УТ_обрывок", coll, [m["rope"]], r, smooth=50)
    return r


def frame_picture(coll, m, at, rng, kind: str = "дерево", state: str = "висит"):
    """Картина в раме: багет протяжкой по контуру (дерево — фигурный профиль 42 × 24 мм, пластик — узкий 14 × 10),
    стекло, картинка с паспарту на картоне, задник; дерево — на тросике с двух колец за гвоздь (верх отходит от стены),
    пластик — на петле вплотную. state: «висит», «разбито» (стекло лучами от удара, двух осколков нет, остальные сдвинуты),
    «упала» (стоит на полу, прислонена к стене; корень — на полу у стены)."""
    name = "КР_картина" + ("_пластик" if kind == "пластик" else "")
    r = L.root(name + ("" if state == "висит" else "_" + state), coll, at)
    W, H = (0.4, 0.5) if kind == "дерево" else (0.3, 0.4)
    pw, pd = (0.042, 0.024) if kind == "дерево" else (0.014, 0.01)
    grp = bpy.data.objects.new(f"{name}_рама", None)
    coll.objects.link(grp)
    grp.parent = r
    hang = kind == "дерево"
    if state == "упала":
        # низ на полу в 13 см от стены, верх лёг на стену
        grp.location = (0, -0.13, 0.0)
        grp.rotation_euler = (-math.radians(14), 0, 0)
        base_z = 0.0
    else:
        base_z = -0.12 if hang else -0.01
        tilt = math.radians(4.5) if hang else 0.0
        grp.location = (0, -0.002, base_z - H)
        grp.rotation_euler = (tilt, 0, 0)   # верх на тросике отходит от стены
    # в осях группы: рама стоит низом в z = 0, задник у y = 0, лицо к −Y
    path = [V((x, 0.0, z)) for x, z in ((-W / 2 + pw / 2, pw / 2), (W / 2 - pw / 2, pw / 2), (W / 2 - pw / 2, H - pw / 2),
                                         (-W / 2 + pw / 2, H - pw / 2))]
    if kind == "дерево":
        prof = [(-pw / 2, 0.0), (pw / 2, 0.0), (pw / 2, pd * 0.55), (pw * 0.42, pd * 0.8), (pw * 0.2, pd), (-pw * 0.05, pd * 0.92),
                (-pw * 0.25, pd * 0.7), (-pw * 0.38, pd * 0.72), (-pw / 2, pd * 0.62), (-pw / 2, pd * 0.32), (-pw * 0.32, pd * 0.32),
                (-pw * 0.32, 0.0)]
    else:
        prof = [(-pw / 2, 0.0), (pw / 2, 0.0), (pw / 2, pd * 0.7), (pw * 0.2, pd), (-pw / 2, pd), (-pw / 2, pd * 0.5),
                (-pw * 0.25, pd * 0.5), (-pw * 0.25, 0.0)]
    bm = bmesh.new()
    L.bm_sweep(bm, path, [(-s_, v_) for s_, v_ in prof], closed=True, up=(0, -1, 0))
    obj(bm, f"{name}_багет", coll, [m["frame_wood"] if kind == "дерево" else m["frame_plastic"]], grp, smooth=35)
    inner_w, inner_h = W - 2 * pw + 0.012, H - 2 * pw + 0.012
    zc = H / 2
    glass_y = -pd * 0.3
    cb = bmesh.new()
    L.bm_box(cb, (-inner_w / 2, glass_y + 0.0012, zc - inner_h / 2), (inner_w / 2, glass_y + 0.0028, zc + inner_h / 2))
    L.bm_box(cb, (-inner_w / 2, glass_y + 0.0028, zc - inner_h / 2), (inner_w / 2, glass_y + 0.0058, zc + inner_h / 2))
    obj(cb, f"{name}_картинка_задник", coll, [m["paper"], m["cardboard"]], grp, smooth=30)
    gb = bmesh.new()
    if state != "разбито":
        L.bm_box(gb, (-inner_w / 2, glass_y - 0.001, zc - inner_h / 2), (inner_w / 2, glass_y + 0.001, zc + inner_h / 2))
    else:
        # лучи трещин из точки удара и кольцо: секторы-осколки, двух нет, остальные чуть сдвинуты
        P = V((-inner_w * 0.12, 0.0, zc + inner_h * 0.08))
        n_r = 7
        angs = sorted(rng.uniform(0, TAU) for _ in range(n_r))
        rr = 0.055

        def border(a):
            dx, dz = math.cos(a), math.sin(a)
            ts = []
            for lim, d in ((inner_w / 2 - P.x, dx), (-inner_w / 2 - P.x, dx)):
                if abs(d) > 1e-6 and lim / d > 0:
                    ts.append(lim / d)
            for lim, d in ((zc + inner_h / 2 - P.z, dz), (zc - inner_h / 2 - P.z, dz)):
                if abs(d) > 1e-6 and lim / d > 0:
                    ts.append(lim / d)
            t = min(ts)
            return V((P.x + dx * t, 0.0, P.z + dz * t))
        missing = {1, n_r + 4}
        k = 0
        for i in range(n_r):
            a0, a1 = angs[i], angs[(i + 1) % n_r] + (TAU if i == n_r - 1 else 0)
            inner = [P] + [P + V((math.cos(a0 + (a1 - a0) * q / 4), 0, math.sin(a0 + (a1 - a0) * q / 4))) * rr for q in range(5)]
            outer = [P + V((math.cos(a0 + (a1 - a0) * q / 4), 0, math.sin(a0 + (a1 - a0) * q / 4))) * rr for q in range(5)]
            # внешний сектор: от кольца до края (по лучам — граница; углы рамки между лучами — точки границы по дуге)
            far = [border(a0 + (a1 - a0) * q / 6) for q in range(7)]
            for piece in (inner, outer[::-1] + far):
                if k not in missing:
                    jit = Matrix.Translation((rng.uniform(-0.001, 0.001), rng.uniform(-0.0015, 0.0), rng.uniform(-0.001, 0.001)))
                    vs = [gb.verts.new(jit @ (V((p.x, glass_y - 0.001, p.z)))) for p in piece]
                    vb = [gb.verts.new(jit @ (V((p.x, glass_y + 0.001, p.z)))) for p in piece]
                    try:
                        f0 = gb.faces.new(vs)
                        f1 = gb.faces.new(vb[::-1])
                        for q in range(len(vs)):
                            gb.faces.new((vs[q], vs[(q + 1) % len(vs)], vb[(q + 1) % len(vs)], vb[q]))
                        _ = (f0, f1)
                    except ValueError:
                        pass
                k += 1
    obj(gb, f"{name}_стекло", coll, [m["glass"]], grp, smooth=10)
    hb = bmesh.new()
    if hang and state != "упала":
        # кольца на заднике, тросик к гвоздю; гвоздь — в стене
        rings = []
        for sx in (-1, 1):
            p = V((sx * (W / 2 - pw), 0.004, H * 0.74))
            lathe(hb, [(0.003, -0.0007), (0.0048, -0.0007), (0.0048, 0.0007), (0.003, 0.0007)], segs=12, origin=tuple(p), axis=(1, 0, 0),
                  closed=True)
            rings.append(p)
        # тросик: из осей группы в осях корня — через матрицу группы
        gm = Matrix.Translation(grp.location) @ grp.rotation_euler.to_matrix().to_4x4()
        nail = V((0.0, -0.012, 0.0))
        wire = bmesh.new()
        pa, pb_ = gm @ rings[0], gm @ rings[1]
        pipe(wire, [pa, nail + V((0, 0.0, -0.003)), pb_], 0.0007, segs=6, bend=0.004)
        pipe(wire, [V((0, 0.002, 0)), V((0, -0.014, 0.0))], 0.0012, segs=8)
        lathe(wire, [(0.0, 0.0), (0.0028, 0.0), (0.0028, -0.0008), (0.0, -0.001)], segs=14, origin=(0, -0.014, 0.0), axis=(0, -1, 0))
        obj(wire, f"{name}_тросик_гвоздь", coll, [m["pin_metal"]], r, smooth=50)
    if not hang:
        L.bm_box(hb, (-0.02, 0.0005, H - pw - 0.01), (0.02, 0.0015, H - pw + 0.005))
    if len(hb.verts):
        obj(hb, f"{name}_крепёж", coll, [m["pin_metal"]], grp, smooth=50)
    else:
        hb.free()
    return r


ITEMS_B = [
    ("Плакат советский", lambda c, m, at, rng: poster(c, m, at, rng, "ПЛ_плакат", 0.6, 0.9, "кнопки"), 0.75),
    ("Плакат советский надорван", lambda c, m, at, rng: poster(c, m, at, rng, "ПЛ_плакат", 0.6, 0.9, "кнопки", "надорван"), 0.75),
    ("Плакат советский угол", lambda c, m, at, rng: poster(c, m, at, rng, "ПЛ_плакат", 0.6, 0.9, "кнопки", "угол"), 0.75),
    ("Плакат студенческий", lambda c, m, at, rng: poster(c, m, at, rng, "ПС_плакат", 0.42, 0.594, "скотч", amp=0.003), 0.55),
    ("Плакат студенческий угол", lambda c, m, at, rng: poster(c, m, at, rng, "ПС_плакат", 0.42, 0.594, "скотч", "угол", 0.003), 0.55),
    ("Вырезка", lambda c, m, at, rng: poster(c, m, at, rng, "ВР_вырезка", 0.21, 0.28, "скотч", amp=0.002), 0.35),
    ("Календарь", lambda c, m, at, rng: calendar(c, m, at, rng), 0.45),
    ("Таблица", lambda c, m, at, rng: chart(c, m, at, rng, False), 0.85),
    ("Таблица сорвана", lambda c, m, at, rng: chart(c, m, at, rng, True), 0.95),
    ("Чертёж", lambda c, m, at, rng: poster(c, m, at, rng, "ЧР_чертёж", 0.841, 0.594, "булавки", amp=0.003), 1.0),
    ("Чертёж свернулся", lambda c, m, at, rng: poster(c, m, at, rng, "ЧР_чертёж", 0.841, 0.594, "булавки", "свернулся", 0.003), 1.0),
    ("Картина", lambda c, m, at, rng: frame_picture(c, m, at, rng, "дерево", "висит"), 0.55),
    ("Картина разбита", lambda c, m, at, rng: frame_picture(c, m, at, rng, "дерево", "разбито"), 0.55),
    ("Картина упала", lambda c, m, at, rng: frame_picture(c, m, at, rng, "дерево", "упала"), 0.55),
    ("Картина пластик", lambda c, m, at, rng: frame_picture(c, m, at, rng, "пластик", "висит"), 0.45),
]



# ---------------------------------------------------------------- группа В: техника 2020-х

def placed_bm(bm, src, m: Matrix) -> None:
    """Перенос временной сетки в bm с преобразованием."""
    bmesh.ops.transform(src, matrix=m, verts=src.verts)
    me = bpy.data.meshes.new("tmp")
    src.to_mesh(me)
    src.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


def axis_matrix(center, axis) -> Matrix:
    """Матрица: локальная Z → axis, начало — center."""
    q = V(axis).normalized().to_track_quat("Z", "Y")
    return Matrix.Translation(V(center)) @ q.to_matrix().to_4x4()


def fan(bm_frame, bm_blades, center, axis, size: float = 0.12, depth: float = 0.025, blades: int = 7) -> None:
    """Корпусный вентилятор: рамка — скруглённый квадрат с круглым окном (лофт кольцами), ступица, лопасти с закруткой."""
    mtx = axis_matrix(center, axis)
    a = size / 2
    n = 48
    sq = B2.superellipse(a, a, 0, 0, 10.0, n)
    ci = [(a * 0.95 * math.cos(TAU * i / n - math.pi / 2), a * 0.95 * math.sin(TAU * i / n - math.pi / 2)) for i in range(n)]
    fb = bmesh.new()
    rings = [(-depth / 2, sq), (depth / 2, sq), (depth / 2, ci), (-depth / 2, ci)]
    vr = [[fb.verts.new((x, y, z)) for x, y in pts] for z, pts in rings]
    for k in range(4):
        r0, r1 = vr[k], vr[(k + 1) % 4]
        for i in range(n):
            j = (i + 1) % n
            fb.faces.new((r0[i], r0[j], r1[j], r1[i]))
    # стойки к моторчику сзади
    for k in range(4):
        ang = TAU * k / 4 + math.pi / 4
        p0 = V((math.cos(ang) * a * 0.33, math.sin(ang) * a * 0.33, depth / 2 - 0.002))
        p1 = V((math.cos(ang) * a * 0.95, math.sin(ang) * a * 0.95, depth / 2 - 0.002))
        L.bm_sweep(fb, [p0, p1], [(-0.0018, -0.002), (0.0018, -0.002), (0.0018, 0.002), (-0.0018, 0.002)], up=(0, 0, 1))
    L.bm_cyl(fb, (0, 0, depth / 2 - 0.004), (0, 0, depth / 2), a * 0.36, segs=24)
    placed_bm(bm_frame, fb, mtx)
    bb = bmesh.new()
    hub = a * 0.33
    lathe(bb, [(0.0, -depth / 2 + 0.003), (hub * 0.95, -depth / 2 + 0.003), (hub, -depth / 2 + 0.006), (hub, depth / 2 - 0.005),
               (0.0, depth / 2 - 0.005)], segs=24)
    for k in range(blades):
        base = TAU * k / blades
        rows = []
        for j in range(4):
            rr = hub + (a * 0.93 - hub) * j / 3
            sweep_ = 0.5 + 0.15 * j / 3
            row = []
            for i in range(3):
                t = (i / 2 - 0.5) * sweep_
                ang = base + t
                zz = -t * depth * 0.55
                row.append(V((math.cos(ang) * rr, math.sin(ang) * rr, zz)))
            rows.append(row)
        strip(bb, rows)
    placed_bm(bm_blades, bb, mtx)


def pc_tower(coll, m, at, rng, opened: bool = False):
    """Системный блок midi-tower 210 × 420 × 460 (+ ножки 15): стальной каркас, сетчатый фасад в пластиковой рамке, порты
    и кнопки сверху спереди, сзади — заглушка разъёмов платы, планки слотов, блок питания с решёткой и разъёмом, решётка
    вентилятора; слева — каленое стекло на четырёх винтах (узел), за ним видно: плата, башенный кулер с вентилятором,
    видеокарта с двумя вентиляторами, четыре планки памяти, кожух блока питания, три вентилятора на вдув за фасадом и
    один на выдув. Вскрытый — стекло снято и прислонено к корпусу, видеокарты и памяти нет."""
    r = L.root("ПК_системный_блок" + ("_вскрыт" if opened else ""), coll, at)
    W, D, H, ft = 0.21, 0.42, 0.46, 0.015
    z0, z1 = ft, ft + H
    hw, hd = W / 2, D / 2
    bm = bmesh.new()
    # каркас: правая стенка, верх, низ, задняя стенка — листом 1 мм
    rounded_box(bm, (0.001, D - 0.02, H - 0.004), 0.0008, cuts=1, center=(hw - 0.0005, 0.01, (z0 + z1) / 2))
    L.bm_box(bm, (-hw + 0.004, -hd + 0.02, z1 - 0.001), (hw, hd, z1))
    L.bm_box(bm, (-hw + 0.004, -hd + 0.02, z0), (hw, hd, z0 + 0.001))
    L.bm_box(bm, (-hw + 0.004, hd - 0.001, z0), (hw, hd, z1))
    # сверху — ниша фильтра (сетка в рамке, утоплена)
    L.bm_box(bm, (-hw + 0.02, -0.12, z1), (hw - 0.02, hd - 0.03, z1 + 0.003))
    # сзади: заглушка разъёмов платы, планки слотов, проём под блок питания, кольцо решётки вентилятора
    L.bm_box(bm, (-hw + 0.018, hd, z1 - 0.2), (-hw + 0.063, hd + 0.002, z1 - 0.038))
    for k in range(7):
        zz = z1 - 0.215 - k * 0.0203
        L.bm_box(bm, (-hw + 0.03, hd, zz - 0.0085), (hw - 0.07, hd + 0.0018, zz + 0.0085))
    L.bm_box(bm, (-hw + 0.012, hd, z0 + 0.005), (hw - 0.012, hd + 0.003, z0 + 0.09))
    obj(bm, "ПК_каркас", coll, [m["steel_pc"]], r, bevel=0.0006, segs=1)
    # фасад: пластиковая рамка и сетка, утопленная на 4 мм
    fb = bmesh.new()
    rounded_box(fb, (W, 0.012, H + 0.002), 0.004, cuts=3, center=(0, -hd + 0.006, (z0 + z1) / 2))
    fr = obj(fb, "ПК_фасад", coll, [m["plastic_black"]], r, smooth=35)
    cb = bmesh.new()
    L.bm_box(cb, (-hw + 0.014, -hd - 0.01, z0 + 0.018), (hw - 0.014, -hd + 0.004, z1 - 0.018))
    B.cut(fr, coll, r, "ПК_окно_сетки", cb)
    mb = bmesh.new()
    L.bm_box(mb, (-hw + 0.014, -hd + 0.004, z0 + 0.018), (hw - 0.014, -hd + 0.005, z1 - 0.018))
    obj(mb, "ПК_сетка_фасада", coll, [m["mesh_pc"]], r)
    # порты и кнопки сверху спереди
    pb = bmesh.new()
    yp = -hd + 0.03
    lathe(pb, [(0.0, 0.0), (0.0065, 0.0), (0.0065, 0.0015), (0.0055, 0.002), (0.0, 0.002)], segs=24, origin=(0.06, yp, z1))
    lathe(pb, [(0.0, 0.0), (0.0025, 0.0), (0.0025, 0.001), (0.0, 0.001)], segs=12, origin=(0.035, yp, z1))
    for k, x in enumerate((-0.07, -0.05)):
        L.bm_box(pb, (x - 0.0065, yp - 0.0025, z1 - 0.001), (x + 0.0065, yp + 0.0025, z1 + 0.0005))
    L.bm_box(pb, (-0.033, yp - 0.0016, z1 - 0.001), (-0.024, yp + 0.0016, z1 + 0.0005))
    for x in (-0.01, 0.003):
        L.bm_cyl(pb, (x, yp, z1 - 0.002), (x, yp, z1 + 0.0004), 0.0032, segs=14)
    obj(pb, "ПК_порты_кнопки", coll, [m["plastic_black"]], r, smooth=40)
    # ножки
    lb = bmesh.new()
    for sx in (-1, 1):
        for sy in (-1, 1):
            rounded_box(lb, (0.035, 0.05, ft), 0.004, cuts=2, center=(sx * (hw - 0.025), sy * (hd - 0.04), ft / 2))
    obj(lb, "ПК_ножки", coll, [m["rubber"]], r, smooth=40)
    # блок питания сзади: решётка кольцами, разъём и клавиша
    gb = bmesh.new()
    pc = V((-hw + 0.055, hd + 0.003, z0 + 0.047))
    for k in range(5):
        pipe(gb, [pc + V((math.cos(t) * (0.01 + k * 0.008), 0, math.sin(t) * (0.01 + k * 0.008))) for t in [TAU * i / 24 for i in range(24)]],
             0.0008, segs=6, closed=True)
    L.bm_box(gb, (0.035, hd + 0.003, z0 + 0.03), (0.062, hd + 0.012, z0 + 0.052))
    L.bm_box(gb, (0.068, hd + 0.003, z0 + 0.034), (0.08, hd + 0.009, z0 + 0.05))
    rc = V((-hw + 0.065, hd + 0.002, z1 - 0.075))
    for k in range(5):
        pipe(gb, [rc + V((math.cos(t) * (0.012 + k * 0.011), 0, math.sin(t) * (0.012 + k * 0.011))) for t in [TAU * i / 28 for i in range(28)]],
             0.0008, segs=6, closed=True)
    obj(gb, "ПК_решётки", coll, [m["steel_pc"]], r, smooth=50)
    # нутро: плата на поддоне у правой стенки, кулер, память, видеокарта, кожух БП, вентиляторы
    ib = bmesh.new()
    xb = hw - 0.025
    L.bm_box(ib, (xb - 0.0016, -0.1, z1 - 0.305), (xb, 0.144 + 0.05, z1 - 0.012))
    # радиаторы цепей питания и чипсета — бруски на плате
    L.bm_box(ib, (xb - 0.022, 0.03, z1 - 0.06), (xb - 0.0016, 0.13, z1 - 0.035))
    L.bm_box(ib, (xb - 0.02, 0.105, z1 - 0.14), (xb - 0.0016, 0.13, z1 - 0.05))
    L.bm_box(ib, (xb - 0.012, -0.05, z1 - 0.27), (xb - 0.0016, 0.0, z1 - 0.22))
    # кожух блока питания
    rounded_box(ib, (W - 0.006, D - 0.06, 0.09), 0.004, cuts=2, center=(0.0, 0.025, z0 + 0.046))
    obj(ib, "ПК_плата_кожух", coll, [m["pcb"]], r, bevel=0.0005, segs=1)
    kb = bmesh.new()
    cpu = V((xb - 0.0016, 0.06, z1 - 0.11))
    L.bm_box(kb, (cpu.x - 0.006, cpu.y - 0.03, cpu.z - 0.03), (cpu.x, cpu.y + 0.03, cpu.z + 0.03))
    for k in range(40):
        x = cpu.x - 0.025 - k * 0.0028
        if x < -hw + 0.03:
            break
        L.bm_box(kb, (x - 0.0004, cpu.y - 0.065, cpu.z - 0.075), (x, cpu.y + 0.065, cpu.z + 0.08))
    for k in range(4):
        y = cpu.y - 0.03 + k * 0.006
        pipe(kb, [(cpu.x - 0.005, y, cpu.z - 0.02), (cpu.x - 0.025, y, cpu.z - 0.02), (cpu.x - 0.12, y, cpu.z - 0.05)], 0.003, segs=8, bend=0.01)
    obj(kb, "ПК_кулер", coll, [m["alu"]], r, smooth=40)
    fanf, fanb = bmesh.new(), bmesh.new()
    fan(fanf, fanb, (cpu.x - 0.065, cpu.y + 0.08, cpu.z), (0, 1, 0))   # на заднем торце рёбер — память спереди свободна
    for k in range(3):
        fan(fanf, fanb, (0.0, -hd + 0.03, z0 + 0.13 + k * 0.125), (0, 1, 0))
    fan(fanf, fanb, (-hw + 0.065 + 0.0, hd - 0.02, z1 - 0.075), (0, 1, 0))
    obj(fanf, "ПК_вентиляторы", coll, [m["plastic_black"]], r, smooth=35)
    obj(fanb, "ПК_лопасти", coll, [m["plastic_black"]], r, smooth=35)
    if not opened:
        # память: четыре планки у кулера ближе к фасаду
        rb = bmesh.new()
        for k in range(4):
            y = cpu.y - 0.075 - k * 0.0095
            L.bm_box(rb, (xb - 0.033, y - 0.0035, cpu.z - 0.066), (xb - 0.0016, y + 0.0035, cpu.z + 0.067))
        obj(rb, "ПК_память", coll, [m["pcb"]], r, bevel=0.0006, segs=1)
        # видеокарта: от слота к стеклу, вентиляторы снизу, пластина сверху
        gpu = bmesh.new()
        gz = z1 - 0.235
        rounded_box(gpu, (0.055, 0.29, 0.12), 0.004, cuts=2, center=(xb - 0.03, -0.005, gz - 0.06))
        obj(gpu, "ПК_видеокарта", coll, [m["plastic_black"]], r, smooth=35)
        gf, gbl = bmesh.new(), bmesh.new()
        for y in (-0.075, 0.065):
            fan(gf, gbl, (xb - 0.03, y, gz - 0.122), (0, 0, -1), size=0.092, depth=0.012, blades=9)
        obj(gf, "ПК_видеокарта_вент", coll, [m["plastic_black"]], r, smooth=35)
        obj(gbl, "ПК_видеокарта_лопасти", coll, [m["plastic_black"]], r, smooth=35)
    # стекло слева на четырёх винтах (узел): у вскрытого снято и прислонено к корпусу
    glb = bmesh.new()
    L.bm_box(glb, (-hw, -hd + 0.012, z0 + 0.005), (-hw + 0.004, hd - 0.004, z1 - 0.005))
    gl = part_at(glb, "ПК_стекло", coll, [m["glass_tint"]], r, (-hw, 0.0, z0), bevel=0.0008, segs=1)
    sb = bmesh.new()
    for y in (-hd + 0.03, hd - 0.025):
        for z in (z0 + 0.02, z1 - 0.02):
            lathe(sb, [(0.0, 0.0), (0.0055, 0.0), (0.0055, -0.006), (0.004, -0.0075), (0.0, -0.0078)], segs=16,
                  origin=(-hw, y, z), axis=(1, 0, 0))
    screws = obj(sb, "ПК_винты", coll, [m["steel_pc"]], gl, smooth=40)
    screws.data.transform(Matrix.Translation(-V((-hw, 0.0, z0))))
    screws.matrix_parent_inverse = Matrix.Identity(4)
    if opened:
        # стоит на полу у левого бока, верхом опирается на корпус
        gl.location = (-hw - 0.11, -0.02, 0.0)
        gl.rotation_euler = (0, math.radians(13.5), math.radians(4))
    return r


def monitor(coll, m, at, rng, cracked: bool = False):
    """Монитор 24″ (экран 531 × 299): тонкие рамки, подбородок 17 мм, корпус — тонкая панель и горб сзади с креплением
    VESA и разъёмами снизу, стойка-шея к овальному основанию, наклон 5°. Разбитый — экран лучами от удара, мелкие
    осколки сдвинуты, у удара — выбитый кусок."""
    r = L.root("МН_монитор" + ("_разбит" if cracked else ""), coll, at)
    Wp, Hp, tp = 0.541, 0.322, 0.009
    sw, sh = 0.531, 0.299
    panel = bpy.data.objects.new("МН_панель", None)
    coll.objects.link(panel)
    panel.parent = r
    panel.location = (0, 0.012, 0.105)
    panel.rotation_euler = (math.radians(5), 0, 0)
    bm = bmesh.new()
    rounded_box(bm, (Wp, tp, Hp), 0.003, cuts=3, center=(0, tp / 2, Hp / 2))
    # горб сзади: скруглённая коробка по нижней половине
    rounded_box(bm, (0.36, 0.035, 0.2), 0.03, cuts=5, center=(0, tp + 0.0175 - 0.004, 0.115))
    obj(bm, "МН_корпус", coll, [m["plastic_black"]], panel, smooth=35)
    xb = bmesh.new()
    for x in (-0.05, 0.05):
        for z in (0.065, 0.165):
            L.bm_cyl(xb, (x, tp + 0.031, z), (x, tp + 0.0325, z), 0.003, segs=12)
    for k, x in enumerate((-0.06, -0.03, 0.0, 0.035)):
        L.bm_box(xb, (x - 0.008, tp + 0.008, 0.012), (x + 0.008, tp + 0.02, 0.0155))
    obj(xb, "МН_винты_разъёмы", coll, [m["steel_pc"]], panel, smooth=40)
    sb = bmesh.new()
    zc = 0.017 + sh / 2
    if not cracked:
        L.bm_box(sb, (-sw / 2, -0.0006, zc - sh / 2), (sw / 2, 0.0004, zc + sh / 2))
    else:
        P = V((sw * 0.18, 0.0, zc - sh * 0.12))
        n_r = 9
        angs = sorted(rng.uniform(0, TAU) for _ in range(n_r))
        rr = 0.03

        def border(a):
            dx, dz = math.cos(a), math.sin(a)
            ts = [lim / d for lim, d in ((sw / 2 - P.x, dx), (-sw / 2 - P.x, dx), (zc + sh / 2 - P.z, dz), (zc - sh / 2 - P.z, dz))
                  if abs(d) > 1e-6 and lim / d > 0]
            t = min(ts)
            return V((P.x + dx * t, 0.0, P.z + dz * t))
        for i in range(n_r):
            a0 = angs[i]
            a1 = angs[(i + 1) % n_r] + (TAU if i == n_r - 1 else 0)
            arc = [P + V((math.cos(a0 + (a1 - a0) * q / 4), 0, math.sin(a0 + (a1 - a0) * q / 4))) * rr for q in range(5)]
            far = [border(a0 + (a1 - a0) * q / 8) for q in range(9)]
            for k, piece in enumerate(([P] + arc, arc[::-1] + far)):
                if k == 0 and i in (2, 5):
                    continue          # у удара кусков нет — видна подложка
                dep = 0.0008 if k == 0 else 0.0002
                jit = Matrix.Translation((rng.uniform(-0.0004, 0.0004), dep + rng.uniform(0, 0.0003), rng.uniform(-0.0004, 0.0004)))
                vs = [sb.verts.new(jit @ V((p.x, -0.0006, p.z))) for p in piece]
                vb = [sb.verts.new(jit @ V((p.x, 0.0004, p.z))) for p in piece]
                try:
                    sb.faces.new(vs)
                    sb.faces.new(vb[::-1])
                    for q in range(len(vs)):
                        sb.faces.new((vs[q], vs[(q + 1) % len(vs)], vb[(q + 1) % len(vs)], vb[q]))
                except ValueError:
                    pass
        # подложка под выбитым — матрица, тёмная
        L.bm_box(sb, (P.x - rr, 0.0012, P.z - rr), (P.x + rr, 0.002, P.z + rr))
    obj(sb, "МН_экран", coll, [m["screen"]], panel, smooth=10)
    # стойка: шея от горба к основанию, основание-овал
    nb = bmesh.new()
    loft(nb, [(0.012, B2.superellipse(0.034, 0.016, 0, 0.065, 2.6, 24)), (0.23, B2.superellipse(0.03, 0.014, 0, 0.055, 2.6, 24))],
         cap_first=True, cap_last=True)
    lathe(nb, [(0.0, 0.0), (0.112, 0.0), (0.115, 0.004), (0.11, 0.012), (0.0, 0.0125)], segs=48, origin=(0, 0.03, 0))
    for v in nb.verts:
        if v.co.z <= 0.0126 and abs(v.co.y - 0.03) > 0.001:
            v.co.y = 0.03 + (v.co.y - 0.03) * 0.82
    obj(nb, "МН_стойка", coll, [m["plastic_black"]], r, smooth=40)
    return r


KEY_ROWS = [
    # (ряд, [(ширина в u, зазор перед в u)…]) — основной блок, стрелки и цифровой блок вынесены отдельно
    (0, [(1, 0)] + [(1, 1 if i == 0 else (0.5 if i in (4, 8) else 0)) for i in range(12)]),
    (1, [(1, 0)] * 13 + [(2, 0)]),
    (2, [(1.5, 0)] + [(1, 0)] * 12 + [(1.5, 0)]),
    (3, [(1.75, 0)] + [(1, 0)] * 11 + [(2.25, 0)]),
    (4, [(2.25, 0)] + [(1, 0)] * 10 + [(2.75, 0)]),
    (5, [(1.25, 0)] * 3 + [(6.25, 0)] + [(1.25, 0)] * 4),
]


def keycap(bm, x: float, y: float, z: float, wu: float, hu: float = 1.0, u: float = 0.019, h: float = 0.0075) -> None:
    """Колпачок: сужается кверху, верх чуть вогнут; x, y — середина низа, z — низ."""
    bw, bd = wu * u - 0.0012, hu * u - 0.0012
    tw, td = bw - 0.0055, bd - 0.0045
    rings = [(z, L.rrect(bw, bd, 0.0012, 2, x, y)), (z + h * 0.85, L.rrect(tw + 0.001, td + 0.001, 0.0018, 2, x, y + 0.0006)),
             (z + h, L.rrect(tw, td, 0.0018, 2, x, y + 0.0006))]
    faces = loft(bm, rings, cap_first=False, cap_last=True)
    top = faces[-1]
    c = top.calc_center_median()
    res = bmesh.ops.poke(bm, faces=[top])
    for v in res["verts"]:
        v.co.z = c.z - 0.0006


def keyboard(coll, m, at, rng):
    """Клавиатура полноразмерная 440 × 135: корпус клином (спереди 18 мм, сзади 26), 104 колпачка раскладкой: основной
    блок, стрелки и блок управления, цифровой; ножки сзади, провод в оплётке с утолщением."""
    r = L.root("КВ_клавиатура", coll, at)
    W, Dk = 0.44, 0.135
    bm = bmesh.new()
    rounded_box(bm, (W, Dk, 0.026), 0.006, cuts=4, center=(0, 0, 0.013))
    for v in bm.verts:
        t = (v.co.y + Dk / 2) / Dk          # спереди 0 → сзади 1
        if v.co.z > 0.013:
            v.co.z = 0.013 + (v.co.z - 0.013) * (0.4 + 0.6 * t)
    obj(bm, "КВ_корпус", coll, [m["plastic_black"]], r, smooth=35)
    kb = bmesh.new()
    u = 0.019
    x0 = -W / 2 + 0.012

    def zk(y):
        return 0.0185 + 0.0075 * (y + Dk / 2) / Dk

    for row, keys in KEY_ROWS:
        y = Dk / 2 - 0.015 - row * u - (0.006 if row > 0 else 0)
        x = x0
        for wu, gap in keys:
            x += gap * u
            keycap(kb, x + wu * u / 2, y, zk(y), wu)
            x += wu * u
    # блок управления и стрелки
    xn = x0 + 15.25 * u
    for row in (0,):
        for i in range(3):
            keycap(kb, xn + (i + 0.5) * u, Dk / 2 - 0.015, zk(Dk / 2 - 0.015), 1)
    for row in (1, 2):
        y = Dk / 2 - 0.015 - row * u - 0.006
        for i in range(3):
            keycap(kb, xn + (i + 0.5) * u, y, zk(y), 1)
    for row, cols in ((4, (1,)), (5, (0, 1, 2))):
        y = Dk / 2 - 0.015 - row * u - 0.006
        for i in cols:
            keycap(kb, xn + (i + 0.5) * u, y, zk(y), 1)
    # цифровой блок
    xp = xn + 3.5 * u
    for row in range(1, 6):
        y = Dk / 2 - 0.015 - row * u - 0.006
        for i in range(4):
            if i == 3 and row in (3, 5):
                continue
            if row == 5 and i == 1:
                continue
            if i == 3 and row in (2, 4):
                keycap(kb, xp + (i + 0.5) * u, y - u / 2, zk(y), 1, hu=2)
                continue
            wu = 2 if (row == 5 and i == 0) else 1
            keycap(kb, xp + i * u + wu * u / 2, y, zk(y), wu)
    obj(kb, "КВ_клавиши", coll, [m["keycap"]], r, smooth=35)
    cb = bmesh.new()
    for sx in (-1, 1):
        L.bm_box(cb, (sx * (W / 2 - 0.05) - 0.02, Dk / 2 - 0.025, -0.006), (sx * (W / 2 - 0.05) + 0.02, Dk / 2 - 0.006, 0.0005))
    rounded_box(cb, (0.012, 0.022, 0.008), 0.003, cuts=2, center=(0.0, Dk / 2 + 0.008, 0.01))
    path = smooth_path([(0, Dk / 2 + 0.018, 0.01), (0, Dk / 2 + 0.06, 0.004), (0.06, Dk / 2 + 0.12, 0.0035), (0.2, Dk / 2 + 0.1, 0.0035),
                        (0.26, Dk / 2 + 0.2, 0.0035)], 6)
    pipe(cb, [V((p.x, p.y, max(p.z, 0.0035))) for p in path], 0.0018, segs=8)
    obj(cb, "КВ_ножки_провод", coll, [m["rubber"]], r, smooth=50)
    return r


def mouse(coll, m, at, rng):
    """Мышь 120 × 66 × 40: тело лофтом по сечениям (горб ближе к хвосту), щель между кнопками, колесо в прорези, две
    боковые кнопки слева, провод спереди."""
    r = L.root("МШ_мышь", coll, at)
    Lm = 0.12
    secs = []
    for k in range(13):
        t = k / 12                                   # 0 — нос (−Y), 1 — хвост
        y = -Lm / 2 + Lm * t
        wdt = 0.028 + 0.005 * math.sin(math.pi * min(1.0, t * 1.3)) + (0.002 if t > 0.5 else 0.0)
        wdt *= (0.35 + 0.65 * math.sin(math.pi * min(t * 1.1 + 0.08, 1.0)) ** 0.4)
        hgt = 0.04 * (0.55 + 0.45 * math.sin(math.pi * min(1.0, 0.15 + t * 0.9))) * (0.3 + 0.7 * math.sin(math.pi * min(t * 1.05 + 0.04, 1.0)) ** 0.5)
        ring = []
        n = 32
        for i in range(n):
            a = TAU * i / n
            c, s = math.cos(a), math.sin(a)
            x = wdt * math.copysign(abs(c) ** 0.8, c)
            z = (hgt * math.copysign(abs(s) ** 0.9, s) if s > 0 else 0.002 * s) + 0.002
            ring.append((x, y, max(z, 0.0)))
        secs.append(ring)
    bm = bmesh.new()
    vr = [[bm.verts.new(p) for p in ring] for ring in secs]
    n = 32
    for j in range(len(vr) - 1):
        for i in range(n):
            k = (i + 1) % n
            bm.faces.new((vr[j][i], vr[j][k], vr[j + 1][k], vr[j + 1][i]))
    bm.faces.new(vr[0][::-1])
    bm.faces.new(vr[-1])
    body = obj(bm, "МШ_корпус", coll, [m["plastic_black"]], r, smooth=60)
    md = body.modifiers.new("Гладкость", "SUBSURF")
    md.levels = 1
    md.render_levels = 2
    cb = bmesh.new()
    L.bm_box(cb, (-0.0004, -Lm / 2 - 0.01, 0.01), (0.0004, -0.005, 0.06))
    B.cut(body, coll, r, "МШ_щель", cb)
    sl = bmesh.new()
    L.bm_box(sl, (-0.0045, -0.035, 0.02), (0.0045, -0.012, 0.06))
    B.cut(body, coll, r, "МШ_прорезь", sl)
    wb = bmesh.new()
    lathe(wb, [(0.0, -0.0035), (0.0105, -0.0035), (0.011, -0.002), (0.011, 0.002), (0.0105, 0.0035), (0.0, 0.0035)], segs=28,
          origin=(0, -0.0235, 0.026), axis=(1, 0, 0))
    for y in (-0.01, 0.01):
        rounded_box(wb, (0.004, 0.016, 0.006), 0.0015, cuts=2, center=(-0.0325, y - 0.0, 0.017))
    path = smooth_path([(0, -Lm / 2, 0.012), (0, -Lm / 2 - 0.03, 0.004), (-0.04, -Lm / 2 - 0.1, 0.0025), (-0.02, -Lm / 2 - 0.2, 0.0025)], 6)
    pipe(wb, [V((p.x, p.y, max(p.z, 0.0025))) for p in path], 0.0016, segs=8)
    obj(wb, "МШ_колесо_провод", coll, [m["rubber"]], r, smooth=50)
    return r


def laptop(coll, m, at, rng, state: str = "открыт"):
    """Ноутбук 15,6″ (358 × 245 × 19): основание клином, клавиатура-островки с цифровым блоком, тачпад, порты по бокам,
    ножки-полосы снизу, петли сзади; крышка (узел с осью в петлях) — экран 344 × 194 в тонкой рамке, глазок камеры.
    state: «закрыт», «открыт» (115°), «разбит» (открыт, экран лучами от удара)."""
    r = L.root("НБ_ноутбук" + ("" if state == "открыт" else "_" + state), coll, at)
    W, Dn, hb = 0.358, 0.245, 0.018
    bm = bmesh.new()
    rounded_box(bm, (W, Dn, hb), 0.006, cuts=4, center=(0, 0, hb / 2))
    for v in bm.verts:
        t = (v.co.y + Dn / 2) / Dn
        if v.co.z > hb / 2:
            v.co.z = hb / 2 + (v.co.z - hb / 2) * (0.75 + 0.25 * t)
    base = obj(bm, "НБ_основание", coll, [m["laptop_alu"]], r, smooth=35)
    cut_b = bmesh.new()
    top_z = hb * (0.75 + 0.25 * 0.6)
    L.bm_box(cut_b, (-W / 2 + 0.012, -0.02, top_z - 0.0006), (W / 2 - 0.012, Dn / 2 - 0.015, top_z + 0.01))
    L.bm_box(cut_b, (-0.07 - 0.06, -Dn / 2 + 0.012, top_z - 0.0005), (-0.07 + 0.06, -Dn / 2 + 0.088, top_z + 0.01))
    B.cut(base, coll, r, "НБ_ниши", cut_b)
    kb = bmesh.new()
    u = 0.0185
    rows = [(0.75, [1] * 16), (1, [1] * 13 + [1.5] + [1] * 4), (1, [1.5] + [1] * 12 + [1.0] + [1] * 4), (1, [1.75] + [1] * 11 + [1.75] + [1] * 4),
            (1, [2.3] + [1] * 10 + [2.2] + [1] * 4), (1, [1] * 4 + [5.0] + [1] * 4 + [1] * 4)]
    y = Dn / 2 - 0.028
    for hgt, keys in rows:
        x = -W / 2 + 0.017
        for wu in keys:
            bw, bd = wu * u - 0.0032, hgt * u - 0.0032
            rounded_box(kb, (bw, bd, 0.0016), 0.0006, cuts=1, center=(x + wu * u / 2, y - hgt * u / 2, top_z - 0.0004))
            x += wu * u
        y -= hgt * u
    obj(kb, "НБ_клавиши", coll, [m["keycap"]], r, smooth=30)
    pb = bmesh.new()
    for k, (x, wdt) in enumerate(((-W / 2, 0.012), (-W / 2, 0.009))):
        L.bm_box(pb, (x - 0.0003, -0.03 - k * 0.025 - wdt / 2, 0.006), (x + 0.0012, -0.03 - k * 0.025 + wdt / 2, 0.0105))
    L.bm_box(pb, (W / 2 - 0.0012, 0.0, 0.006), (W / 2 + 0.0003, 0.014, 0.0115))
    L.bm_box(pb, (W / 2 - 0.0012, 0.025, 0.0065), (W / 2 + 0.0003, 0.034, 0.0095))
    for y in (-Dn / 2 + 0.02, Dn / 2 - 0.02):
        rounded_box(pb, (W - 0.07, 0.008, 0.0025), 0.0012, cuts=2, center=(0, y, -0.0005))
    for sx in (-1, 1):
        L.bm_cyl(pb, (sx * 0.1 - 0.025, Dn / 2 - 0.004, hb - 0.004), (sx * 0.1 + 0.025, Dn / 2 - 0.004, hb - 0.004), 0.0045, segs=16)
    obj(pb, "НБ_порты_ножки_петли", coll, [m["plastic_black"]], r, smooth=40)
    # крышка в закрытом положении: лежит на основании экраном вниз; узел — ось петель
    pivot = V((0, Dn / 2 - 0.004, hb - 0.004))
    lb = bmesh.new()
    Dl, tl = 0.235, 0.0055
    rounded_box(lb, (W, Dl, tl), 0.005, cuts=3, center=(0, Dn / 2 - 0.006 - Dl / 2, hb + tl / 2 + 0.0004))
    lid = part_at(lb, "НБ_крышка", coll, [m["laptop_alu"]], r, tuple(pivot), smooth=35)
    sb = bmesh.new()
    sw, sh = 0.344, 0.194
    ysc = Dn / 2 - 0.006 - 0.012 - sh / 2
    zs = hb + 0.0004 - 0.0001
    if state != "разбит":
        L.bm_box(sb, (-sw / 2, ysc - sh / 2, zs - 0.0002), (sw / 2, ysc + sh / 2, zs + 0.0003))
    else:
        P = V((-sw * 0.2, ysc + sh * 0.1, 0.0))
        n_r = 8
        angs = sorted(rng.uniform(0, TAU) for _ in range(n_r))
        rr = 0.02

        def border(a):
            dx, dy = math.cos(a), math.sin(a)
            ts = [lim / d for lim, d in ((sw / 2 - P.x, dx), (-sw / 2 - P.x, dx), (ysc + sh / 2 - P.y, dy), (ysc - sh / 2 - P.y, dy))
                  if abs(d) > 1e-6 and lim / d > 0]
            t = min(ts)
            return V((P.x + dx * t, P.y + dy * t, 0.0))
        for i in range(n_r):
            a0 = angs[i]
            a1 = angs[(i + 1) % n_r] + (TAU if i == n_r - 1 else 0)
            arc = [P + V((math.cos(a0 + (a1 - a0) * q / 4), math.sin(a0 + (a1 - a0) * q / 4), 0)) * rr for q in range(5)]
            far = [border(a0 + (a1 - a0) * q / 8) for q in range(9)]
            for k, piece in enumerate(([P] + arc, arc[::-1] + far)):
                if k == 0 and i == 3:
                    continue
                jit = Matrix.Translation((rng.uniform(-0.0003, 0.0003), rng.uniform(-0.0003, 0.0003), 0.0002 if k == 0 else 0.0))
                vs = [sb.verts.new(jit @ V((p.x, p.y, zs - 0.0002))) for p in piece]
                vt = [sb.verts.new(jit @ V((p.x, p.y, zs + 0.0003))) for p in piece]
                try:
                    sb.faces.new(vs[::-1])
                    sb.faces.new(vt)
                    for q in range(len(vs)):
                        sb.faces.new((vs[q], vs[(q + 1) % len(vs)], vt[(q + 1) % len(vs)], vt[q]))
                except ValueError:
                    pass
    L.bm_cyl(sb, (0, Dn / 2 - 0.0125, zs - 0.0002), (0, Dn / 2 - 0.0125, zs + 0.0002), 0.0012, segs=12)
    scr = obj(sb, "НБ_экран", coll, [m["screen"]], lid, smooth=10)
    scr.data.transform(Matrix.Translation(-pivot))
    scr.matrix_parent_inverse = Matrix.Identity(4)
    if state != "закрыт":
        lid.rotation_euler = (-math.radians(115), 0, 0)
    return r


ITEMS_C = [
    ("Системный блок", lambda c, m, at, rng: pc_tower(c, m, at, rng, False), 0.4),
    ("Системный блок вскрыт", lambda c, m, at, rng: pc_tower(c, m, at, rng, True), 0.6),
    ("Монитор", lambda c, m, at, rng: monitor(c, m, at, rng, False), 0.7),
    ("Монитор разбит", lambda c, m, at, rng: monitor(c, m, at, rng, True), 0.7),
    ("Клавиатура", lambda c, m, at, rng: keyboard(c, m, at, rng), 0.6),
    ("Мышь", lambda c, m, at, rng: mouse(c, m, at, rng), 0.3),
    ("Ноутбук", lambda c, m, at, rng: laptop(c, m, at, rng, "открыт"), 0.5),
    ("Ноутбук закрыт", lambda c, m, at, rng: laptop(c, m, at, rng, "закрыт"), 0.5),
    ("Ноутбук разбит", lambda c, m, at, rng: laptop(c, m, at, rng, "разбит"), 0.5),
]



# ---------------------------------------------------------------- группа Г: тубус, тетради, учебники

def extrude_profile(bm, prof: list, y0: float, y1: float, caps: bool = True) -> None:
    """Замкнутое сечение в плоскости XZ, вытянутое вдоль Y от y0 до y1."""
    a = [bm.verts.new((x, y0, z)) for x, z in prof]
    b = [bm.verts.new((x, y1, z)) for x, z in prof]
    n = len(prof)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], b[j], b[i]))
    if caps:
        bm.faces.new(a[::-1])
        bm.faces.new(b)


def book_closed(bm_cover, bm_block, W: float, Lb: float, T: float, at=(0.0, 0.0, 0.0), yaw: float = 0.0, upright: bool = False,
                lean: float = 0.0) -> None:
    """Книга в твёрдом переплёте лежит (корешок — к −X): крышки 2,5 мм с канавками у корешка, скруглённый корешок,
    выступ крышек 3 мм над блоком, блок со слегка вогнутым передним обрезом. upright — стоит корешком наружу (к −Y)."""
    tb, sq = 0.0025, 0.003
    hz = T / 2
    rs = T / 2
    # наружный контур сечения: верхняя крышка → канавка → дуга корешка → нижняя крышка → передний край
    x_f, x_j = W / 2, -W / 2 + 0.008
    outer = [(x_f, T), (x_j + 0.004, T), (x_j, T - 0.0012), (x_j - 0.003, T)]
    for k in range(9):
        a = math.pi / 2 + math.pi * k / 8
        outer.append((-W / 2 + 0.002 + rs * 0.35 * math.cos(a) - 0.0, hz + rs * math.sin(a)))
    outer += [(x_j - 0.003, 0.0), (x_j, 0.0012), (x_j + 0.004, 0.0), (x_f, 0.0)]
    # внутренний контур — параллельно наружному на толщину картона
    inner = [(x_f, T - tb), (x_j + 0.004, T - tb), (x_j, T - tb - 0.0006), (x_j - 0.003, T - tb)]
    for k in range(9):
        a = math.pi / 2 + math.pi * k / 8
        inner.append((-W / 2 + 0.002 + tb + (rs - tb) * 0.35 * math.cos(a), hz + (rs - tb) * math.sin(a)))
    inner += [(x_j - 0.003, tb), (x_j, tb + 0.0006), (x_j + 0.004, tb), (x_f, tb)]
    cover = outer + inner[::-1]
    tmp = bmesh.new()
    extrude_profile(tmp, cover, -Lb / 2, Lb / 2)
    blk = bmesh.new()
    bx0 = -W / 2 + 0.006
    prof = [(bx0, tb + 0.0003), (W / 2 - sq - 0.002, tb + 0.0003)]
    for k in range(7):
        t = k / 6
        prof.append((W / 2 - sq - 0.0035 * math.sin(math.pi * t), tb + 0.0003 + (T - 2 * tb - 0.0006) * t))
    prof += [(W / 2 - sq - 0.002, T - tb - 0.0003), (bx0, T - tb - 0.0003)]
    extrude_profile(blk, prof, -Lb / 2 + sq, Lb / 2 - sq)
    m_ = Matrix.Translation(V(at)) @ Matrix.Rotation(yaw, 4, "Z")
    if upright:
        # стоит на нижнем обрезе, корешок наружу (к −Y): книга повёрнута так, что её Y → Z, корешок (−X) → −Y
        m_ = m_ @ Matrix.Rotation(lean, 4, "Y") @ Matrix.Translation((0, 0, Lb / 2)) @ Matrix.Rotation(math.pi / 2, 4, "Z") @ \
            Matrix.Rotation(math.pi / 2, 4, "X") @ Matrix.Translation((0, 0, -T / 2))
    placed_bm(bm_cover, tmp, m_)
    placed_bm(bm_block, blk, m_)


def book_open(bm_cover, bm_block, W: float, Lb: float, T: float) -> None:
    """Раскрытая книга на столе: крышки плашмя, корешок вогнут снизу, блок — две половины, листы горбом от корешка."""
    tb = 0.0025
    for s in (-1, 1):
        tmp = bmesh.new()
        L.bm_box(tmp, (min(0.004 * s, s * (W + 0.004)), -Lb / 2, 0.0), (max(0.004 * s, s * (W + 0.004)), Lb / 2, tb))
        placed_bm(bm_cover, tmp, Matrix.Identity(4))
        blk = bmesh.new()
        half = (T - 2 * tb) / 2
        prof = []
        for k in range(13):
            t = k / 12
            x = s * (0.006 + (W - 0.012) * t)
            z = tb + half * (0.35 + 0.65 * (1 - math.exp(-t * 7))) * (1 - 0.15 * t)
            prof.append((x, z))
        prof += [(s * (W - 0.004), tb + 0.0004), (s * 0.006, tb + 0.0004)]
        if s > 0:
            prof = prof[::-1]
        extrude_profile(blk, prof, -Lb / 2 + 0.003, Lb / 2 - 0.003)
        placed_bm(bm_block, blk, Matrix.Identity(4))
    sp = bmesh.new()
    L.bm_box(sp, (-0.008, -Lb / 2, -0.0015), (0.008, Lb / 2, 0.0006))
    placed_bm(bm_cover, sp, Matrix.Identity(4))


def textbook(coll, m, at, rng, state: str = "закрыт"):
    """Учебник 170 × 240 × 22 в твёрдом переплёте. state: «закрыт», «раскрыт», «стопка» (четыре книги разного формата
    вразнобой), «ряд» (шесть книг стоят корешками наружу, крайняя завалилась на соседнюю)."""
    r = L.root("УЧ_учебник" + ("" if state == "закрыт" else "_" + state), coll, at)
    cb, bb = bmesh.new(), bmesh.new()
    if state == "закрыт":
        book_closed(cb, bb, 0.17, 0.24, 0.022)
    elif state == "раскрыт":
        book_open(cb, bb, 0.17, 0.24, 0.022)
    elif state == "стопка":
        z = 0.0
        for W, Lb, T in ((0.2, 0.26, 0.02), (0.17, 0.24, 0.03), (0.15, 0.21, 0.014), (0.145, 0.2, 0.018)):
            book_closed(cb, bb, W, Lb, T, at=(rng.uniform(-0.012, 0.012), rng.uniform(-0.012, 0.012), z), yaw=math.radians(rng.uniform(-8, 8)))
            z += T
    else:
        x = -0.07
        sizes = [(0.17, 0.24, 0.022), (0.15, 0.21, 0.016), (0.17, 0.24, 0.03), (0.145, 0.2, 0.018), (0.2, 0.26, 0.02), (0.17, 0.24, 0.025)]
        for k, (W, Lb, T) in enumerate(sizes):
            # крайняя завалилась на соседку: верх к ней (−X), низ отъехал от ряда
            lean = -math.radians(18) if k == len(sizes) - 1 else 0.0
            book_closed(cb, bb, W, Lb, T, at=(x + T / 2 + (Lb * math.sin(-lean) * 0.95 if lean else 0.0), 0.0, 0.0), upright=True, lean=lean)
            x += T + 0.001
    obj(cb, "УЧ_переплёт", coll, [m["book_cover"]], r, smooth=40)
    obj(bb, "УЧ_блок", coll, [m["book_pages"]], r, smooth=30)
    return r


def notebook_closed(bm_cover, bm_block, bm_staple, W: float, Lb: float, T: float, m_: Matrix, curl_corner: bool = False) -> None:
    """Тетрадь лежит (сгиб — к −X): обложка — тонкий лист вокруг блока, две скрепки на сгибе, угол чуть загнут."""
    tc = 0.0003
    cv = bmesh.new()

    def corner(x, y, z):
        if curl_corner and x > W / 2 - 0.04 and y < -Lb / 2 + 0.04:
            d = ((x - (W / 2 - 0.04)) / 0.04) * ((-Lb / 2 + 0.04 - y) / 0.04)
            return z + 0.006 * d
        return z

    rows = []
    for j in range(9):
        y = -Lb / 2 + Lb * j / 8
        rows.append([V((x, y, corner(x, y, T))) for x in [-W / 2 + W * i / 8 for i in range(9)]])
    strip(cv, rows)
    rows2 = [[V((x, -Lb / 2 + Lb * j / 8, 0.0)) for x in [-W / 2 + W * i / 8 for i in range(9)][::-1]] for j in range(9)]
    strip(cv, rows2)
    # сгиб обложки — полукольцо по корешку
    rows3 = []
    for k in range(7):
        a = math.pi / 2 + math.pi * k / 6
        rows3.append([V((-W / 2 + (T / 2) * 0.6 * math.cos(a), y, T / 2 + (T / 2) * math.sin(a))) for y in (-Lb / 2, Lb / 2)])
    strip(cv, rows3)
    placed_bm(bm_cover, cv, m_)
    bl = bmesh.new()
    rounded_box(bl, (W - 0.003, Lb - 0.002, T - 2 * tc - 0.0004), 0.0005, cuts=1, center=(0.0005, 0, T / 2))
    placed_bm(bm_block, bl, m_)
    st = bmesh.new()
    for y in (-Lb / 4, Lb / 4):
        pipe(st, [(-W / 2 - T * 0.3 + 0.0006, y - 0.006, T * 0.55), (-W / 2 - T * 0.3, y - 0.006, T / 2), (-W / 2 - T * 0.3, y + 0.006, T / 2),
                  (-W / 2 - T * 0.3 + 0.0006, y + 0.006, T * 0.55)], 0.00035, segs=4)
    placed_bm(bm_staple, st, m_)


def notebook_open(bm_cover, bm_block, bm_staple, W: float, Lb: float, T: float) -> None:
    """Раскрытая тетрадь: обложка плашмя, листы двумя половинами горбом от сгиба, на развороте видны скрепки."""
    half = T / 2
    for s in (-1, 1):
        tmp = bmesh.new()
        rows = [[V((s * W * i / 8, -Lb / 2 + Lb * j / 8, 0.0)) for i in range(9)] for j in range(9)]
        if s < 0:
            rows = [r_[::-1] for r_ in rows]
        strip(tmp, rows)
        placed_bm(bm_cover, tmp, Matrix.Identity(4))
        blk = bmesh.new()
        prof = []
        for k in range(11):
            t = k / 10
            prof.append((s * (0.001 + (W - 0.004) * t), 0.0003 + half * (0.4 + 0.6 * (1 - math.exp(-t * 9))) + 0.0015 * math.sin(math.pi * t)))
        prof += [(s * (W - 0.003), 0.0003), (s * 0.001, 0.0003)]
        if s > 0:
            prof = prof[::-1]
        extrude_profile(blk, prof, -Lb / 2 + 0.001, Lb / 2 - 0.001)
        placed_bm(bm_block, blk, Matrix.Identity(4))
    st = bmesh.new()
    for y in (-Lb / 4, Lb / 4):
        pipe(st, [(-0.0006, y - 0.006, half * 0.5 + 0.0006), (0.0, y - 0.006, half * 0.5 + 0.0012), (0.0, y + 0.006, half * 0.5 + 0.0012),
                  (-0.0006, y + 0.006, half * 0.5 + 0.0006)], 0.00035, segs=4)
    placed_bm(bm_staple, st, Matrix.Identity(4))


def notebook(coll, m, at, rng, kind: str = "школьная", state: str = "закрыта"):
    """Тетрадь: школьная 12 л (170 × 205 × 2,5) или общая 48 л (165 × 205 × 6). state: «закрыта» (угол чуть загнут),
    «раскрыта», «стопка» (пять школьных вразнобой)."""
    name = "ТТ_тетрадь" if kind == "школьная" else "ТО_тетрадь_общая"
    r = L.root(name + ("" if state == "закрыта" else "_" + state), coll, at)
    W, Lb, T = (0.17, 0.205, 0.0025) if kind == "школьная" else (0.165, 0.205, 0.006)
    cb, bb, sb = bmesh.new(), bmesh.new(), bmesh.new()
    if state == "закрыта":
        notebook_closed(cb, bb, sb, W, Lb, T, Matrix.Identity(4), curl_corner=True)
    elif state == "раскрыта":
        notebook_open(cb, bb, sb, W, Lb, T)
    else:
        z = 0.0
        for k in range(5):
            m_ = Matrix.Translation((rng.uniform(-0.015, 0.015), rng.uniform(-0.015, 0.015), z)) @ \
                Matrix.Rotation(math.radians(rng.uniform(-14, 14)), 4, "Z")
            notebook_closed(cb, bb, sb, W, Lb, T, m_, curl_corner=k == 4)
            z += T + 0.0002
    obj(cb, f"{name}_обложка", coll, [m["notebook_cover"]], r, smooth=40)
    obj(bb, f"{name}_листы", coll, [m["paper"]], r, smooth=30)
    obj(sb, f"{name}_скрепки", coll, [m["pin_metal"]], r, smooth=40)
    return r


def drawing_tube(coll, m, at, rng, opened: bool = False):
    """Тубус для чертежей телескопический: корпус Ø 90 × 650 с рёбрами, внутренняя труба Ø 84 выдвинута на 60 мм,
    донце и крышка с насечкой, клипсы и ремень (лежит петлёй). Открытый — крышка снята и лежит рядом, из горловины
    торчат свёрнутые листы."""
    r = L.root("ТБ_тубус" + ("_открыт" if opened else ""), coll, at)
    R, Lt = 0.045, 0.65
    tb = bmesh.new()
    x0 = -Lt / 2
    # корпус (ось вдоль X, лежит): кольцевые рёбра у концов
    prof = [(R - 0.002, 0.0), (R, 0.002)]
    for k in range(3):
        zz = 0.02 + k * 0.012
        prof += [(R, zz), (R + 0.0015, zz + 0.002), (R + 0.0015, zz + 0.006), (R, zz + 0.008)]
    prof += [(R, Lt * 0.62 - 0.03)]
    for k in range(3):
        zz = Lt * 0.62 - 0.028 + k * 0.012
        prof += [(R, zz), (R + 0.0015, zz + 0.002), (R + 0.0015, zz + 0.006), (R, zz + 0.008)]
    prof += [(R, Lt * 0.62), (R - 0.002, Lt * 0.62 + 0.001), (R - 0.004, Lt * 0.62), (R - 0.004, 0.003), (R - 0.002, 0.0)]
    lathe(tb, prof, segs=48, origin=(x0, 0, R), axis=(1, 0, 0), closed=True)
    # внутренняя труба: из корпуса до горловины
    lathe(tb, [(R - 0.0045, Lt * 0.55), (R - 0.0045, Lt + 0.01), (R - 0.0065, Lt + 0.01), (R - 0.0065, Lt * 0.55)], segs=48,
          origin=(x0, 0, R), axis=(1, 0, 0), closed=True)
    obj(tb, "ТБ_корпус", coll, [m["tube_plastic"]], r, smooth=40)
    cpb = bmesh.new()
    cap_prof = [(0.0, -0.012), (R + 0.002, -0.012), (R + 0.003, -0.01)]
    for k in range(10):
        cap_prof += [(R + 0.003, -0.01 + k * 0.0026), (R + 0.0022, -0.01 + k * 0.0026 + 0.0013)]
    cap_prof += [(R + 0.003, 0.016), (R + 0.0005, 0.018), (0.0, 0.018)]
    lathe(cpb, cap_prof, segs=48, origin=(x0 - 0.006, 0, R), axis=(1, 0, 0))
    obj(cpb, "ТБ_донце", coll, [m["tube_plastic"]], r, smooth=40)
    lid_prof = [(0.0, 0.026), (R - 0.0015, 0.026), (R - 0.0005, 0.024)]
    for k in range(10):
        lid_prof += [(R - 0.0005, 0.024 - k * 0.0024), (R - 0.0013, 0.024 - k * 0.0024 - 0.0012)]
    lid_prof += [(R - 0.0005, 0.0), (R - 0.0045, 0.0), (R - 0.0045, 0.022), (0.0, 0.022)]
    lb = bmesh.new()
    xe = x0 + Lt + 0.01
    lathe(lb, lid_prof, segs=48, origin=(0, 0, 0), axis=(1, 0, 0))
    if opened:
        # крышка лежит рядом на боку, горловиной вниз
        mL = Matrix.Translation((xe + 0.09, -0.12, R + 0.0015)) @ Matrix.Rotation(math.radians(70), 4, "Z")
    else:
        mL = Matrix.Translation((xe - 0.022, 0, R))
    bmesh.ops.transform(lb, matrix=mL, verts=lb.verts)
    obj(lb, "ТБ_крышка", coll, [m["tube_plastic"]], r, smooth=40)
    # клипсы и ремень: от клипс у концов — петлёй по полу рядом
    sb = bmesh.new()
    clips = [V((x0 + 0.05, 0.0, 2 * R + 0.002)), V((x0 + Lt * 0.62 - 0.04, 0.0, 2 * R + 0.002))]
    for c_ in clips:
        rounded_box(sb, (0.03, 0.02, 0.006), 0.002, cuts=2, center=tuple(c_))
    path = [clips[0] + V((0, -0.012, 0)), clips[0] + V((-0.03, -0.06, -0.06)), V((x0 - 0.04, -0.13, 0.002)), V((0.0, -0.22, 0.002)),
            V((x0 + Lt * 0.75, -0.14, 0.002)), clips[1] + V((0.03, -0.06, -0.06)), clips[1] + V((0, -0.012, 0))]
    flat = [V((q.x, q.y, max(q.z, 0.0015))) for q in smooth_path(path, 8)]
    L.bm_sweep(sb, flat, [(-0.0125, 0.0), (0.0125, 0.0), (0.0125, 0.0018), (-0.0125, 0.0018)], up=(0, 0, 1))
    obj(sb, "ТБ_ремень", coll, [m["webbing"]], r, smooth=35)
    if opened:
        # свёрнутые листы торчат из горловины: рулоны спиралью
        pb = bmesh.new()
        for k, (dy, dz, rr, out) in enumerate(((-0.012, R - 0.008, 0.016, 0.12), (0.014, R + 0.004, 0.014, 0.08), (0.0, R + 0.016, 0.012, 0.15))):
            prof = []
            turns = 1.6
            n_ = 40
            for i in range(n_):
                a = TAU * turns * i / (n_ - 1)
                rad = rr * (0.45 + 0.55 * i / (n_ - 1))
                prof.append((rad * math.cos(a), rad * math.sin(a)))
            rows = []
            for xx in (x0 + 0.2, x0 + Lt + out):
                rows.append([V((xx, dy + py, dz + pz)) for py, pz in prof])
            strip(pb, rows)
        pp = obj(pb, "ТБ_чертежи", coll, [m["paper"]], r, smooth=50)
        so = pp.modifiers.new("Бумага", "SOLIDIFY")
        so.thickness = 0.0003
    return r


ITEMS_D = [
    ("Тубус", lambda c, m, at, rng: drawing_tube(c, m, at, rng, False), 0.85),
    ("Тубус открыт", lambda c, m, at, rng: drawing_tube(c, m, at, rng, True), 0.95),
    ("Тетрадь", lambda c, m, at, rng: notebook(c, m, at, rng, "школьная", "закрыта"), 0.25),
    ("Тетрадь раскрыта", lambda c, m, at, rng: notebook(c, m, at, rng, "школьная", "раскрыта"), 0.4),
    ("Тетради стопкой", lambda c, m, at, rng: notebook(c, m, at, rng, "школьная", "стопка"), 0.3),
    ("Тетрадь общая", lambda c, m, at, rng: notebook(c, m, at, rng, "общая", "закрыта"), 0.25),
    ("Учебник", lambda c, m, at, rng: textbook(c, m, at, rng, "закрыт"), 0.25),
    ("Учебник раскрыт", lambda c, m, at, rng: textbook(c, m, at, rng, "раскрыт"), 0.4),
    ("Учебники стопкой", lambda c, m, at, rng: textbook(c, m, at, rng, "стопка"), 0.3),
    ("Учебники в ряд", lambda c, m, at, rng: textbook(c, m, at, rng, "ряд"), 0.3),
]


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


WALL_Y = 1.4          # стена студии (build_furniture.studio): у навесного корень — у неё
# высота корня навесного: плакаты, календарь — верх листа; таблица и картины на гвозде — гвоздь; упавшая — пол
TOP_Z = {"Таблица": 2.25, "Таблица сорвана": 2.25, "Картина": 1.85, "Картина разбита": 1.85, "Картина упала": 0.0,
         "Картина пластик": 1.75, "Вырезка": 1.7, "Календарь": 1.75}


def build(out: str) -> list:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    m = mats()
    x = 0.0
    placed = []
    for top_name, items, wall in (("Партия3_А_ящики_вещи_v01", ITEMS_A, False), ("Партия3_Б_плакаты_картины_v01", ITEMS_B, True),
                                  ("Партия3_В_компьютеры_v01", ITEMS_C, False), ("Партия3_Г_учебное_v01", ITEMS_D, False)):
        top = L.collection(top_name)
        rng = random.Random({ITEMS_A[0][0]: 33, ITEMS_B[0][0]: 34, ITEMS_D[0][0]: 36}.get(items[0][0], 35))
        for label, fn, width in items:
            c = L.collection(label, top)
            at = (x + width / 2, WALL_Y, TOP_Z.get(label, 2.0)) if wall else (x + width / 2, 0.0, 0.0)
            root = fn(c, m, at, rng)
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
    wall_labels = {lb for lb, _, _ in ITEMS_B}
    os.makedirs(folder, exist_ok=True)
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = 900, 700
    cam = sc.camera
    dg = bpy.context.evaluated_depsgraph_get()
    for i, (label, coll, root) in enumerate(placed):
        if only and i not in only:
            continue
        if wall:
            wall.hide_render = label not in wall_labels
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
