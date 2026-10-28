"""Модули общежития, этап 2: форма для просмотра владельцем в Blender.

Запуск:
  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
      --python tools/dorm_modules/build_modules.py -- <выходной .blend>

Размеры — из принятого серого плана r4 (data/blockouts/dorm.json, docs/design/dorm_stage1.md):
проходы и помещения по правилу масштаба E, всё, что берут рукой, — 1:1.
Каждый модуль — пустышка-корень (её положение — начало координат модуля) с деталями внутри.
Оси модуля: X — вдоль стены, Y — поперёк (+Y — коридор у двери, комната у окна), Z — вверх от пола.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import mlib as L  # noqa: E402

V = Vector

# ---------------------------------------------------------------- размеры плана
WALL_LOAD, WALL_PART, WALL_FACADE = 0.38, 0.15, 0.64
CEIL = 3.0                      # потолок жилых этажей
SLAB = 0.24                     # плита перекрытия
CLEAR_W, CLEAR_H = 1.17, 2.415  # чистый проход двери (по притвору)
STOP = 0.012                    # притвор: насколько он выступает в проём
LINING = 0.025                  # толщина коробки / добора
LEAF_T = 0.04
CASING_W, CASING_GAP = 0.08, 0.006
WIN_W, WIN_SILL, WIN_TOP = 2.096, 0.85, 2.50
SILL_PROJ = 0.28


def mats() -> dict:
    return {
        "plaster": L.material("Штукатурка", (0.72, 0.73, 0.70), 0.9),
        "door": L.material("Дверь_краска", (0.33, 0.24, 0.16), 0.45),
        "frame": L.material("Коробка_наличник_краска", (0.40, 0.35, 0.29), 0.5),
        "alu": L.material("Алюминий", (0.62, 0.62, 0.64), 0.35, 1.0),
        "steel": L.material("Сталь_тёмная", (0.22, 0.22, 0.23), 0.45, 1.0),
        "glass": L.material("Стекло", (0.62, 0.70, 0.72), 0.05, 0.0, 0.25),
        "sash": L.material("Окно_краска_белая", (0.82, 0.81, 0.77), 0.45),
        "zinc": L.material("Отлив_оцинковка", (0.56, 0.58, 0.59), 0.5, 1.0),
        "radiator": L.material("Батарея_краска", (0.76, 0.75, 0.69), 0.5),
        "skirting": L.material("Плинтус_краска", (0.30, 0.25, 0.20), 0.5),
        "concrete": L.material("Бетон", (0.55, 0.55, 0.53), 0.95),
        "rail": L.material("Ограждение_краска", (0.20, 0.22, 0.22), 0.5),
        "handrail": L.material("Поручень_дерево", (0.34, 0.21, 0.12), 0.45),
    }


# ---------------------------------------------------------------- стена с проёмом

def wall_with_opening(name: str, coll, m: dict, w: float, h: float, t: float,
                      ox0: float, ox1: float, oz0: float, oz1: float, at=(0, 0, 0)) -> bpy.types.Object:
    r = L.root(name, coll, at)
    bm = bmesh.new()
    L.bm_wall_opening(bm, w, h, t, ox0, ox1, oz0, oz1, L.weight_layer(bm))
    L.finish_bm(bm, name + "_стена", coll, m["plaster"], r, bevel=0.012, segs=3, by_weight=True)
    return r


# ---------------------------------------------------------------- дверь комнаты

def door_room(coll, m: dict, t: float = WALL_LOAD, number: str = "204", at=(0, 0, 0)) -> bpy.types.Object:
    """Филёнчатая дверь в коробке с добором на всю толщину стены. Полотно — у комнатной грани (−Y),
    открывается в комнату; петли слева (−X), если смотреть из коридора."""
    r = L.root("M01_дверь_комнаты", coll, at)
    hw = CLEAR_W / 2 + STOP           # внутренняя грань коробки
    top_in = CLEAR_H + STOP
    # Наличники: протяжка по внутренней кромке, затем зеркально на комнатную грань.
    bm = bmesh.new()
    xi, zt = hw + CASING_GAP, top_in + CASING_GAP
    casing = [(0, 0), (CASING_W, 0), (CASING_W, 0.006), (0.077, 0.012), (0.07, 0.016), (0.03, 0.021),
              (0.012, 0.024), (0.005, 0.025), (0.001, 0.022), (0, 0.018)]
    L.bm_sweep(bm, [(xi, t / 2, 0), (xi, t / 2, zt), (-xi, t / 2, zt), (-xi, t / 2, 0)], casing, up=(0, 1, 0))
    L.mirror_copy(bm, "Y")
    # Коробка с добором на всю толщину стены и притвор.
    for s in (-1, 1):
        L.bm_box(bm, (min(s * hw, s * (hw + LINING)), -t / 2, 0), (max(s * hw, s * (hw + LINING)), t / 2, top_in))
        L.bm_box(bm, (min(s * hw, s * (hw - STOP)), -t / 2 + 0.044, 0), (max(s * hw, s * (hw - STOP)), -t / 2 + 0.074, top_in - STOP))
    L.bm_box(bm, (-hw - LINING, -t / 2, top_in), (hw + LINING, t / 2, top_in + LINING))
    L.bm_box(bm, (-hw, -t / 2 + 0.044, top_in - STOP), (hw, -t / 2 + 0.074, top_in))
    L.finish_bm(bm, "дверь_коробка_наличники", coll, m["frame"], r, bevel=0.0015, segs=2, angle=40)

    # Полотно: ось петель — начало координат объекта, чтобы его можно было поворачивать.
    pivot = L.root("дверь_полотно_ось_петель", coll, (-hw, -t / 2 - 0.004, 0))
    pivot.parent = r
    leaf_w, leaf_h, x0, z0 = 2 * hw - 0.006, top_in - 0.003 - 0.008, 0.003, 0.008
    yc = 0.006 + LEAF_T / 2           # средняя плоскость полотна в координатах оси петель
    stile, rail_top, rail_lock, rail_bot = 0.13, 0.13, 0.18, 0.22
    lock_z = 1.0
    x1 = x0 + leaf_w
    bm = bmesh.new()
    lt = LEAF_T / 2
    L.bm_box(bm, (x0, -lt, z0), (x0 + stile, lt, z0 + leaf_h))
    L.bm_box(bm, (x1 - stile, -lt, z0), (x1, lt, z0 + leaf_h))
    L.bm_box(bm, (x0 + stile, -lt, z0 + leaf_h - rail_top), (x1 - stile, lt, z0 + leaf_h))
    L.bm_box(bm, (x0 + stile, -lt, lock_z - rail_lock / 2), (x1 - stile, lt, lock_z + rail_lock / 2))
    L.bm_box(bm, (x0 + stile, -lt, z0), (x1 - stile, lt, z0 + rail_bot))
    panels = [(z0 + rail_bot, lock_z - rail_lock / 2), (lock_z + rail_lock / 2, z0 + leaf_h - rail_top)]
    moulding = [(0, -0.014), (0.016, -0.014), (0.016, -0.009), (0.012, -0.004), (0.006, -0.001), (0, 0)]
    for za, zb in panels:
        xa, xb = x0 + stile, x1 - stile
        _raised_panel(bm, xa, xb, za, zb)
        L.bm_sweep(bm, [(xb, lt, zb), (xb, lt, za), (xa, lt, za), (xa, lt, zb)], moulding, closed=True, up=(0, 1, 0))
        L.bm_sweep(bm, [(xa, -lt, zb), (xa, -lt, za), (xb, -lt, za), (xb, -lt, zb)], moulding, closed=True, up=(0, -1, 0))
    L.transform(bm, bm.verts, Matrix.Translation((0, yc, 0)))
    L.finish_bm(bm, "дверь_полотно", coll, m["door"], pivot, bevel=0.002, segs=2, angle=40)

    # Фурнитура полотна: ручки на планках с обеих сторон, скважина, петли.
    bm = bmesh.new()
    hx = x1 - 0.065
    for side in (1, -1):
        face = side * lt
        plate = L.rrect(0.05, 0.22, 0.012, 4)
        L.bm_prism(bm, [(hx + p[0], lock_z + 0.01 + p[1]) for p in plate], (0, face, 0), (1, 0, 0), (0, 0, 1), (0, side * 0.003, 0))
        L.bm_cyl(bm, (hx, face + side * 0.003, lock_z + 0.04), (hx, face + side * 0.016, lock_z + 0.04), 0.011, 20)
        y_out = face + side * 0.016
        arm = [(hx, y_out - side * 0.004, lock_z + 0.04), (hx, y_out + side * 0.042, lock_z + 0.04),
               (hx - 0.03, y_out + side * 0.054, lock_z + 0.04), (hx - 0.125, y_out + side * 0.05, lock_z + 0.032)]
        L.bm_sweep(bm, arm, L.rrect(0.014, 0.018, 0.0055, 3), up=(0, 0, 1))
    L.transform(bm, bm.verts, Matrix.Translation((0, yc, 0)))
    L.finish_bm(bm, "дверь_ручки", coll, m["alu"], pivot, bevel=0.0015, segs=2, angle=30)

    bm = bmesh.new()
    for side in (1, -1):
        face = side * (lt + 0.003)
        hole = [(hx + 0.004 * math.cos(a / 8 * 2 * math.pi), lock_z - 0.045 + 0.004 * math.sin(a / 8 * 2 * math.pi)) for a in range(8)]
        L.bm_prism(bm, hole, (0, face, 0), (1, 0, 0), (0, 0, 1), (0, side * 0.0006, 0))
        L.bm_box(bm, (hx - 0.0018, face, lock_z - 0.062), (hx + 0.0018, face + side * 0.0006, lock_z - 0.045))
    for zc in (0.28, 1.25, 2.17):
        for za, zb in ((zc - 0.05, zc - 0.0007), (zc + 0.0007, zc + 0.05)):
            L.bm_cyl(bm, (0, -yc, za), (0, -yc, zb), 0.0075, 20)
        L.bm_sphere(bm, (0, -yc, zc - 0.05), 0.006, 14, 7)
        L.bm_sphere(bm, (0, -yc, zc + 0.05), 0.006, 14, 7)
    L.transform(bm, bm.verts, Matrix.Translation((0, yc, 0)))
    L.finish_bm(bm, "дверь_петли_скважина", coll, m["steel"], pivot, bevel=0.0008, segs=1, angle=40)

    # Номерок над наличником, на коридорной грани.
    bm = bmesh.new()
    zc = top_in + CASING_GAP + CASING_W + 0.11
    plate = L.rrect(0.16, 0.08, 0.014, 5)
    L.bm_prism(bm, [(p[0], zc + p[1]) for p in plate], (0, t / 2, 0), (1, 0, 0), (0, 0, 1), (0, 0.003, 0))
    basis = Matrix(((-1, 0, 0), (0, 0, 1), (0, 1, 0)))
    L.text_mesh(bm, number, 0.05, 0.0016, (0, t / 2 + 0.0038, zc - 0.002), basis)
    L.finish_bm(bm, "дверь_номерок", coll, m["alu"], r, bevel=0.0006, segs=1, angle=40)
    return r


def _raised_panel(bm, xa: float, xb: float, za: float, zb: float) -> None:
    """Филёнка: тонкая кромка в пазах, к середине — поднятое поле со скосами (обе стороны)."""
    e, f, d = 0.005, 0.012, 0.055
    outer = [(xa, za), (xb, za), (xb, zb), (xa, zb)]
    inner = [(xa + d, za + d), (xb - d, za + d), (xb - d, zb - d), (xa + d, zb - d)]
    of = [bm.verts.new((x, e, z)) for x, z in outer]
    ob = [bm.verts.new((x, -e, z)) for x, z in outer]
    inf = [bm.verts.new((x, f, z)) for x, z in inner]
    inb = [bm.verts.new((x, -f, z)) for x, z in inner]
    bm.faces.new(inf)
    bm.faces.new(inb[::-1])
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((of[i], of[j], inf[j], inf[i]))
        bm.faces.new((ob[j], ob[i], inb[i], inb[j]))
        bm.faces.new((ob[i], ob[j], of[j], of[i]))


# ---------------------------------------------------------------- окно

def window(coll, m: dict, at=(0, 0, 0)) -> bpy.types.Object:
    """Деревянное окно с раздельными переплётами: наружные и внутренние створки, импост, форточка слева,
    подоконник с выступом 0,28 и отлив. Наружная грань стены — −Y, комната — +Y."""
    r = L.root("M03_окно", coll, at)
    t = WALL_FACADE
    ow = WIN_W / 2 - 0.005                          # коробка в проёме с зазором под конопатку
    zb, ztop = WIN_SILL - 0.04, WIN_TOP - 0.005
    y_out, y_in = -t / 2 + 0.11, -t / 2 + 0.25      # коробка 0,14 по глубине
    fw, mul = 0.065, 0.08
    # Коробка и импост.
    bm = bmesh.new()
    frame_prof = [(0, 0), (fw, 0), (fw, y_in - y_out), (0, y_in - y_out)]
    L.bm_sweep(bm, [(-ow, y_out, zb), (ow, y_out, zb), (ow, y_out, ztop), (-ow, y_out, ztop)],
               [(-s, v) for s, v in frame_prof], closed=True, up=(0, 1, 0))
    L.bm_box(bm, (-mul / 2, y_out, zb + fw), (mul / 2, y_in, ztop - fw))
    L.finish_bm(bm, "окно_коробка", coll, m["sash"], r, bevel=0.002, segs=2, angle=40)

    # Створки: две половины × два слоя; верх левой — форточка.
    sx = [(-ow + fw + 0.002, -mul / 2 - 0.002), (mul / 2 + 0.002, ow - fw - 0.002)]
    sz = (zb + fw + 0.002, ztop - fw - 0.002)
    bar_z = sz[1] - 0.43
    layers = [(y_out + 0.002, y_out + 0.047), (y_in - 0.047, y_in - 0.002)]
    bm_s, bm_g, bm_h = bmesh.new(), bmesh.new(), bmesh.new()
    sp, bar = 0.055, 0.045
    bead = [(0, 0), (0.012, 0), (0, 0.012)]
    for li, (ya, yb) in enumerate(layers):
        ym = (ya + yb) / 2
        for hi, (xa, xb) in enumerate(sx):
            _sash(bm_s, xa, xb, sz[0], sz[1], ya, yb, sp)
            L.bm_box(bm_s, (xa + sp, ya, bar_z - bar / 2), (xb - sp, yb, bar_z + bar / 2))
            panes = [(sz[0] + sp, bar_z - bar / 2), (bar_z + bar / 2, sz[1] - sp)]
            for pi, (pa, pb) in enumerate(panes):
                ax, bx = xa + sp, xb - sp
                if hi == 0 and pi == 1:
                    # Форточка: своя створка внутри верхнего поля левой половины.
                    _sash(bm_s, ax + 0.002, bx - 0.002, pa + 0.002, pb - 0.002, ya + 0.004, yb - 0.004, 0.042)
                    ax, bx, pa, pb = ax + 0.044, bx - 0.044, pa + 0.044, pb - 0.044
                    if li == 1:
                        _knob(bm_h, (bx - 0.03, yb - 0.004, (pa + pb) / 2), 0.022)
                L.bm_box(bm_g, (ax - 0.006, ym - 0.002, pa - 0.006), (bx + 0.006, ym + 0.002, pb + 0.006))
                face = yb if li == 1 else ya
                up = (0, 1, 0) if li == 1 else (0, -1, 0)
                path = [(bx, face, pb), (bx, face, pa), (ax, face, pa), (ax, face, pb)]
                if li == 0:
                    path = path[::-1]
                L.bm_sweep(bm_s, path, bead, closed=True, up=up)
            if li == 1:
                # Ручка-кнопка у притвора и шпингалеты сверху и снизу.
                kx = xb - 0.035 if hi == 0 else xa + 0.035
                _knob(bm_h, (kx, yb, (sz[0] + bar_z) / 2), 0.03)
                for zz, dz in ((sz[0] + 0.04, -1), (sz[1] - 0.04, 1)):
                    L.bm_box(bm_h, (kx - 0.011, yb, zz - 0.05), (kx + 0.011, yb + 0.004, zz + 0.05))
                    L.bm_cyl(bm_h, (kx, yb + 0.0085, zz - 0.06), (kx, yb + 0.0085, zz + 0.06 + dz * 0.02), 0.0045, 12)
            # Петли створки на наружной стороне коробки.
            hx = xa - 0.002 if hi == 0 else xb + 0.002
            for zz in (sz[0] + 0.15, sz[1] - 0.15):
                L.bm_cyl(bm_h, (hx, yb + 0.004, zz - 0.035), (hx, yb + 0.004, zz + 0.035), 0.005, 12)
    L.finish_bm(bm_s, "окно_створки", coll, m["sash"], r, bevel=0.0015, segs=2, angle=40)
    L.finish_bm(bm_g, "окно_стёкла", coll, m["glass"], r)
    L.finish_bm(bm_h, "окно_фурнитура", coll, m["steel"], r, bevel=0.0008, segs=1, angle=40)

    # Подоконник: внутри проёма — по его ширине, за гранью стены — с «ушами» по 0,08.
    bm = bmesh.new()
    hx, ex = WIN_W / 2, WIN_W / 2 + 0.08
    yi = t / 2
    plan = [(-hx, y_in), (hx, y_in), (hx, yi), (ex, yi), (ex, yi + SILL_PROJ), (-ex, yi + SILL_PROJ), (-ex, yi), (-hx, yi)]
    L.bm_prism(bm, plan, (0, 0, WIN_SILL - 0.04), (1, 0, 0), (0, 1, 0), (0, 0, 0.04))
    L.finish_bm(bm, "окно_подоконник", coll, m["sash"], r, bevel=0.006, segs=3, angle=40)

    # Отлив снаружи: согнутый лист под коробкой и над кладкой.
    bm = bmesh.new()
    path = [(0, y_out + 0.01, zb + 0.022), (0, -t / 2 - 0.045, zb + 0.004), (0, -t / 2 - 0.047, zb - 0.016)]
    L.bm_sweep(bm, path, [(0, -ow), (0.0015, -ow), (0.0015, ow), (0, ow)], up=(1, 0, 0))
    L.finish_bm(bm, "окно_отлив", coll, m["zinc"], r, bevel=0.0004, segs=1, angle=30)
    return r


def _sash(bm, xa, xb, za, zb, ya, yb, w) -> None:
    """Рамка створки из четырёх брусков (вертикальные — на всю высоту)."""
    L.bm_box(bm, (xa, ya, za), (xa + w, yb, zb))
    L.bm_box(bm, (xb - w, ya, za), (xb, yb, zb))
    L.bm_box(bm, (xa + w, ya, za), (xb - w, yb, za + w))
    L.bm_box(bm, (xa + w, ya, zb - w), (xb - w, yb, zb))


def _knob(bm, at, d: float) -> None:
    """Оконная ручка-кнопка: ножка и грибок."""
    x, y, z = at
    L.bm_cyl(bm, (x, y, z), (x, y + 0.016, z), 0.005, 12)
    L.bm_cyl(bm, (x, y + 0.016, z), (x, y + 0.024, z), d / 2, 20, r1=d / 2 * 0.8)


# ---------------------------------------------------------------- батарея МС-140

def radiator(coll, m: dict, sections: int = 9, at=(0, 0, 0)) -> bpy.types.Object:
    """Чугунный радиатор МС-140-500: шаг секций 108 мм, высота 588, глубина 140; подводка к стояку справа.
    Начало координат — на полу у грани стены, комната — +Y."""
    r = L.root("M05_батарея_МС140", coll, at)
    pitch, h, d, gap_wall, z0 = 0.108, 0.588, 0.14, 0.05, 0.15
    y0 = gap_wall
    yc = y0 + d / 2
    zb, zt = z0 + 0.044, z0 + h - 0.044
    half = sections * pitch / 2
    bm = bmesh.new()
    for i in range(sections):
        xc = -half + pitch * (i + 0.5)
        # Секция: две плоские колонки (лицевая и задняя) с перемычкой, вверху и внизу — «головы»
        # шире колонок вокруг ниппельных приливов; между секциями просвет только по высоте колонок.
        for ycol in (y0 + 0.025, y0 + d - 0.025):
            L.bm_prism(bm, L.rrect(0.078, 0.05, 0.012, 3, xc, ycol), (0, 0, z0 + 0.06), (1, 0, 0), (0, 1, 0), (0, 0, h - 0.12))
        L.bm_box(bm, (xc - 0.005, y0 + 0.045, z0 + 0.08), (xc + 0.005, y0 + d - 0.045, z0 + h - 0.08))
        for zz in (zb, zt):
            head = L.rrect(0.102, 0.105, 0.035, 5, xc, zz)
            L.bm_prism(bm, head, (0, y0 + 0.004, 0), (1, 0, 0), (0, 0, 1), (0, d - 0.008, 0))
            L.bm_cyl(bm, (xc - pitch / 2 + 0.002, yc, zz), (xc + pitch / 2 - 0.002, yc, zz), 0.034, 28)
    for zz in (zb, zt):
        L.bm_cyl(bm, (-half - 0.004, yc, zz), (half + 0.004, yc, zz), 0.024, 24)
        for s in (-1, 1):
            L.bm_cyl(bm, (s * half, yc, zz), (s * (half + 0.012), yc, zz), 0.027, 24)
            L.bm_cyl(bm, (s * (half + 0.012), yc, zz), (s * (half + 0.022), yc, zz), 0.021, 6)
    L.finish_bm(bm, "батарея_секции", coll, m["radiator"], r, bevel=0.006, segs=2, angle=40)

    # Подводка: стояк Ø33,5 за ухом подоконника, отводы Ø26,8 к верхней и нижней пробке, кран на верхнем.
    bm = bmesh.new()
    rx, ry = 1.20, 0.06
    L.bm_cyl(bm, (rx, ry, 0.0), (rx, ry, CEIL), 0.0168, 20)
    circle = [(0.0134 * math.cos(a * math.pi / 8), 0.0134 * math.sin(a * math.pi / 8)) for a in range(16)]
    for zz in (zb, zt):
        L.bm_sweep(bm, [(half + 0.02, yc, zz), (rx - 0.09, yc, zz), (rx - 0.02, ry, zz), (rx, ry, zz)], circle, up=(0, 0, 1))
        L.bm_cyl(bm, (rx, ry, zz - 0.03), (rx, ry, zz + 0.03), 0.022, 20)
    vx = half + 0.10
    L.bm_cyl(bm, (vx - 0.035, yc, zt), (vx + 0.035, yc, zt), 0.021, 20)
    L.bm_cyl(bm, (vx, yc, zt), (vx, yc, zt + 0.06), 0.008, 12)
    L.bm_cyl(bm, (vx, yc, zt + 0.06), (vx, yc, zt + 0.075), 0.024, 20)
    for xx in (-0.27, 0.27):
        L.bm_sweep(bm, [(xx, 0.0, zt + 0.06), (xx, yc - 0.01, zt + 0.06), (xx, yc - 0.01, zt + 0.035)],
                   [(0.006 * math.cos(a * math.pi / 4), 0.006 * math.sin(a * math.pi / 4)) for a in range(8)], up=(1, 0, 0))
    L.finish_bm(bm, "батарея_подводка", coll, m["radiator"], r, bevel=0.002, segs=1, angle=40)
    return r


# ---------------------------------------------------------------- плинтус

SKIRT = [(0, 0), (0.02, 0), (0.02, 0.052), (0.018, 0.064), (0.013, 0.073), (0.006, 0.079), (0, 0.08)]


def skirting(coll, m: dict, at=(0, 0, 0)) -> bpy.types.Object:
    """Деревянный плинтус 80 × 20: прямой метр, внутренний и наружный угол на ус."""
    r = L.root("M06_плинтус", coll, at)
    pieces = {
        "плинтус_1м": [(-0.5, 0, 0), (0.5, 0, 0)],
        "плинтус_угол_внутр": [(-0.2, 0, 0), (0, 0, 0), (0, 0.2, 0)],
        "плинтус_угол_наруж": [(-0.2, 0, 0), (0, 0, 0), (0, -0.2, 0)],
    }
    for i, (name, path) in enumerate(pieces.items()):
        bm = bmesh.new()
        L.bm_sweep(bm, path, SKIRT, up=(0, 0, 1))
        ob = L.finish_bm(bm, name, coll, m["skirting"], r, bevel=0.0015, segs=2, angle=40)
        ob.location.x = i * 0.9
    return r


# ---------------------------------------------------------------- лестница

TREAD, FLIGHT_W, LANDING_D, FLIGHT_SLAB = 0.30, 1.50, 1.60, 0.22
HANDRAIL = [(-0.03, 0.0), (0.03, 0.0), (0.03, 0.018), (0.027, 0.03), (0.02, 0.039), (0.01, 0.044), (0.0, 0.045),
            (-0.01, 0.044), (-0.02, 0.039), (-0.027, 0.03), (-0.03, 0.018)]


def stair_flight(coll, m: dict, n: int, riser: float, name: str, at=(0, 0, 0)) -> bpy.types.Object:
    """Сборный бетонный марш: n подступёнков и n проступей 0,30 (верхняя — на уровне площадки),
    низ — наклонная плита 0,12 по нормали. Начало координат — передняя кромка первой ступени у пола,
    середина ширины; подъём по +Y."""
    r = L.root(name, coll, at)
    k = riser / TREAD
    d = 0.12 / (TREAD / math.hypot(TREAD, riser))
    top = n * riser
    yb = d / k
    yt = (top - FLIGHT_SLAB + d) / k
    poly = [(0, 0), (yb, 0), (yt, top - FLIGHT_SLAB), (n * TREAD, top - FLIGHT_SLAB), (n * TREAD, top)]
    for j in range(n - 1, 0, -1):
        poly += [(j * TREAD, (j + 1) * riser), (j * TREAD, j * riser)]
    poly += [(0, riser)]
    bm = bmesh.new()
    L.bm_prism(bm, poly, (-FLIGHT_W / 2, 0, 0), (0, 1, 0), (0, 0, 1), (FLIGHT_W, 0, 0))
    L.finish_bm(bm, name + "_бетон", coll, m["concrete"], r, bevel=0.008, segs=2, angle=30)
    return r


def landing(coll, m: dict, at=(0, 0, 0)) -> bpy.types.Object:
    """Площадка во всю ширину клетки 3,30 × 1,60, толщина 0,22. Начало — передняя кромка, верх площадки."""
    r = L.root("M11_площадка", coll, at)
    bm = bmesh.new()
    L.bm_box(bm, (-1.65, 0, -FLIGHT_SLAB), (1.65, LANDING_D, 0))
    L.finish_bm(bm, "площадка_бетон", coll, m["concrete"], r, bevel=0.008, segs=2, angle=30)
    return r


def railing_flight(coll, m: dict, n: int, riser: float, name: str, at=(0, 0, 0)) -> bpy.types.Object:
    """Ограждение марша сбоку (+X): по две стойки 16 × 16 на ступень, приварены к закладным на боковой грани,
    поверху полоса 40 × 4 и деревянный поручень, понизу — полоса вдоль ступеней. Высота 0,90 от линии носков."""
    r = L.root(name, coll, at)
    k = riser / TREAD
    xb = FLIGHT_W / 2 + 0.03
    nose = lambda y: riser + k * y  # noqa: E731
    y0, y1 = 0.05, n * TREAD - 0.05
    hr = 0.90                                   # верх поручня над линией носков
    strip_top = hr - 0.045
    bm = bmesh.new()
    for j in range(n):
        for off in (0.075, 0.225):
            y = j * TREAD + off
            if y > y1:
                continue
            zt = nose(y) + strip_top - 0.004
            zb = (j + 1) * riser - 0.11            # закладная ниже проступи на боковой грани
            L.bm_sweep(bm, [(xb, y, zt), (xb, y, zb + 0.02), (FLIGHT_W / 2 + 0.004, y, zb + 0.02)],
                       L.rrect(0.016, 0.016, 0.002, 1), up=(0, 1, 0))
            L.bm_box(bm, (FLIGHT_W / 2, y - 0.03, zb), (FLIGHT_W / 2 + 0.006, y + 0.03, zb + 0.06))
    flat = [(-0.02, 0.0), (0.02, 0.0), (0.02, 0.004), (-0.02, 0.004)]
    L.bm_sweep(bm, [(xb, y0, nose(y0) + strip_top - 0.004), (xb, y1, nose(y1) + strip_top - 0.004)], flat, up=(0, 0, 1))
    L.bm_sweep(bm, [(xb, y0, nose(y0) + 0.06), (xb, y1, nose(y1) + 0.06)],
               [(-0.004, 0.0), (0.004, 0.0), (0.004, 0.04), (-0.004, 0.04)], up=(0, 0, 1))
    L.finish_bm(bm, name + "_сталь", coll, m["rail"], r, bevel=0.0015, segs=1, angle=40)
    bm = bmesh.new()
    L.bm_sweep(bm, [(xb, y0 - 0.06, nose(y0 - 0.06) + strip_top), (xb, y1 + 0.06, nose(y1 + 0.06) + strip_top)],
               HANDRAIL, up=(0, 0, 1))
    L.finish_bm(bm, name + "_поручень", coll, m["handrail"], r, bevel=0.002, segs=2, angle=30)
    return r


def railing_turn(coll, m: dict, p_low, p_high, landing_z: float, at=(0, 0, 0)) -> bpy.types.Object:
    """Поворот ограждения на площадке через просвет между маршами: от конца поручня нижнего марша
    к началу верхнего, две стойки на площадке."""
    r = L.root("M13_ограждение_поворот", coll, at)
    pl, ph = V(p_low), V(p_high)
    yt = max(pl.y, ph.y) + 0.18
    zm = (pl.z + ph.z) / 2
    path = [pl, V((pl.x, yt, zm)), V((ph.x, yt, zm)), ph]
    bm = bmesh.new()
    L.bm_sweep(bm, path, HANDRAIL, up=(0, 0, 1))
    L.finish_bm(bm, "поворот_поручень", coll, m["handrail"], r, bevel=0.002, segs=2, angle=30)
    bm = bmesh.new()
    flat = [(-0.02, -0.004), (0.02, -0.004), (0.02, 0.0), (-0.02, 0.0)]
    L.bm_sweep(bm, [V((p.x, p.y, p.z)) for p in path], flat, up=(0, 0, 1))
    for x in (pl.x, ph.x):
        L.bm_box(bm, (x - 0.008, yt - 0.008, landing_z), (x + 0.008, yt + 0.008, zm - 0.004))
        L.bm_box(bm, (x - 0.035, yt - 0.035, landing_z), (x + 0.035, yt + 0.035, landing_z + 0.006))
    L.finish_bm(bm, "поворот_сталь", coll, m["rail"], r, bevel=0.0015, segs=1, angle=40)
    return r


# ---------------------------------------------------------------- потолок, балки, пилястры

def ceiling_slab(coll, m: dict, length: float, name: str, at=(0, 0, 0)) -> bpy.types.Object:
    """Многопустотная плита шириной 1,19 (шаг 1,20): нижние продольные кромки сняты фаской 15 мм —
    соседние плиты дают на потолке рустованный шов. Начало — середина низа плиты; длина — по Y."""
    r = L.root(name, coll, at)
    bm = bmesh.new()
    L.bm_box(bm, (-0.595, -length / 2, 0), (0.595, length / 2, FLIGHT_SLAB))
    w = L.weight_layer(bm)
    for e in bm.edges:
        a, b = e.verts
        if abs(a.co.z) < 1e-6 and abs(b.co.z) < 1e-6 and abs(a.co.x - b.co.x) < 1e-6:
            e[w] = 1.0
    L.finish_bm(bm, name + "_бетон", coll, m["concrete"], r, bevel=0.015, segs=1, by_weight=True)
    return r


def beam(coll, m: dict, span: float = 3.4, at=(0, 0, 0)) -> bpy.types.Object:
    """Поперечная балка коридора 0,40 × 0,40 по ширине коридора. Начало — середина у потолка (верх балки)."""
    r = L.root("M16_балка", coll, at)
    bm = bmesh.new()
    L.bm_box(bm, (-0.2, -span / 2, -0.4), (0.2, span / 2, 0))
    w = L.weight_layer(bm)
    for e in bm.edges:
        a, b = e.verts
        if abs(a.co.z + 0.4) < 1e-6 and abs(b.co.z + 0.4) < 1e-6 and abs(a.co.x - b.co.x) < 1e-6:
            e[w] = 1.0
    L.finish_bm(bm, "балка_бетон", coll, m["concrete"], r, bevel=0.02, segs=2, by_weight=True)
    return r


def pilaster(coll, m: dict, height: float = CEIL - 0.4, at=(0, 0, 0)) -> bpy.types.Object:
    """Пилястра 0,45 × 0,18 под балкой. Начало — середина у пола на грани стены, выступ по +Y."""
    r = L.root("M17_пилястра", coll, at)
    bm = bmesh.new()
    L.bm_box(bm, (-0.225, 0, 0), (0.225, 0.18, height))
    w = L.weight_layer(bm)
    for e in bm.edges:
        a, b = e.verts
        if abs(a.co.y - 0.18) < 1e-6 and abs(b.co.y - 0.18) < 1e-6 and abs(a.co.x - b.co.x) < 1e-6:
            e[w] = 1.0
    L.finish_bm(bm, "пилястра_бетон", coll, m["plaster"], r, bevel=0.015, segs=2, by_weight=True)
    return r


# ---------------------------------------------------------------- остеклённая двустворчатая дверь

def glazed_double_door(coll, m: dict, t: float = WALL_PART, clear_w: float = 2.40, clear_h: float = 2.70,
                       at=(0, 0, 0)) -> bpy.types.Object:
    """Двустворчатая дверь в перегородке: створки с нижней филёнкой и остеклением в три стекла,
    над ними остеклённая фрамуга, ручки-скобы с обеих сторон, наличники с обеих сторон."""
    r = L.root("M07_дверь_двустворчатая", coll, at)
    fw = 0.06
    hw = clear_w / 2
    leaf_top = CLEAR_H
    bm = bmesh.new()
    casing = [(0, 0), (CASING_W, 0), (CASING_W, 0.006), (0.077, 0.012), (0.07, 0.016), (0.03, 0.021),
              (0.012, 0.024), (0.005, 0.025), (0.001, 0.022), (0, 0.018)]
    xi, zt = hw + fw + CASING_GAP, clear_h + fw + CASING_GAP
    L.bm_sweep(bm, [(xi, t / 2, 0), (xi, t / 2, zt), (-xi, t / 2, zt), (-xi, t / 2, 0)], casing, up=(0, 1, 0))
    L.mirror_copy(bm, "Y")
    for s in (-1, 1):
        L.bm_box(bm, (min(s * hw, s * (hw + fw)), -t / 2, 0), (max(s * hw, s * (hw + fw)), t / 2, clear_h + fw))
    L.bm_box(bm, (-hw, -t / 2, clear_h), (hw, t / 2, clear_h + fw))
    L.bm_box(bm, (-hw, -0.03, leaf_top), (hw, 0.03, leaf_top + 0.06))
    L.bm_box(bm, (-0.03, -0.03, leaf_top + 0.06), (0.03, 0.03, clear_h))
    L.finish_bm(bm, "двустворчатая_коробка_фрамуга", coll, m["frame"], r, bevel=0.0015, segs=2, angle=40)
    bm_g = bmesh.new()
    for s in (-1, 1):
        xa, xb = sorted((s * 0.03, s * hw))
        L.bm_box(bm_g, (xa, -0.003, leaf_top + 0.055), (xb, 0.003, clear_h + 0.005))

    L.finish_bm(bm_g, "двустворчатая_фрамуга_стёкла", coll, m["glass"], r)
    lt = 0.0225
    shift = Matrix.Translation((0, lt + 0.004, 0))   # ось петель — у грани створки со стороны −Y
    for hand in (-1, 1):
        tag = "лев" if hand < 0 else "прав"
        pivot = L.root(f"двустворчатая_ось_петель_{tag}", coll, (hand * hw, -lt - 0.004, 0))
        pivot.parent = r
        w = hw - 0.003 - 0.002
        sgn = -hand
        xs = lambda a: sgn * a  # noqa: E731
        z0, h = 0.008, leaf_top - 0.003 - 0.008
        stile, rail_top, mid0, mid1, rail_bot = 0.12, 0.12, 0.95, 1.15, 0.25
        bm = bmesh.new()
        bm_g = bmesh.new()

        def box(a0, a1, z_a, z_b, y0=-lt, y1=lt):
            L.bm_box(bm, (min(xs(a0), xs(a1)), y0, z_a), (max(xs(a0), xs(a1)), y1, z_b))
        box(0.002, 0.002 + stile, z0, z0 + h)
        box(w - stile, w, z0, z0 + h)
        box(0.002 + stile, w - stile, z0 + h - rail_top, z0 + h)
        box(0.002 + stile, w - stile, mid0, mid1)
        box(0.002 + stile, w - stile, z0, z0 + rail_bot)
        xa, xb = sorted((xs(0.002 + stile), xs(w - stile)))
        _raised_panel(bm, xa, xb, z0 + rail_bot, mid0)
        g0, g1 = mid1, z0 + h - rail_top
        bars = [g0 + (g1 - g0) * i / 3 for i in (1, 2)]
        for zb_ in bars:
            box(0.002 + stile, w - stile, zb_ - 0.02, zb_ + 0.02, -0.015, 0.015)
        cuts = [g0] + [b for zb_ in bars for b in (zb_ - 0.02, zb_ + 0.02)] + [g1]
        for i in range(0, len(cuts), 2):
            pa, pb = cuts[i], cuts[i + 1]
            L.bm_box(bm_g, (xa - 0.006, -0.0025, pa - 0.006), (xb + 0.006, 0.0025, pb + 0.006))
            path = [(xb, lt, pb), (xb, lt, pa), (xa, lt, pa), (xa, lt, pb)]
            L.bm_sweep(bm, path, [(0, -0.02), (0.014, -0.02), (0.014, -0.012), (0, 0)], closed=True, up=(0, 1, 0))
        L.transform(bm, bm.verts, shift)
        L.transform(bm_g, bm_g.verts, shift)
        L.finish_bm(bm, f"двустворчатая_створка_{tag}", coll, m["door"], pivot, bevel=0.002, segs=2, angle=40)
        L.finish_bm(bm_g, f"двустворчатая_стёкла_{tag}", coll, m["glass"], pivot)
        bm = bmesh.new()
        hx = xs(w - 0.06)
        for side in (1, -1):
            face = side * lt
            for zz in (0.95, 1.30):
                L.bm_cyl(bm, (hx, face, zz), (hx, face + side * 0.006, zz), 0.016, 20)
            L.bm_sweep(bm, [(hx, face + side * 0.004, 0.95), (hx, face + side * 0.055, 0.98), (hx, face + side * 0.055, 1.27),
                            (hx, face + side * 0.004, 1.30)],
                       [(0.011 * math.cos(a * math.pi / 8), 0.011 * math.sin(a * math.pi / 8)) for a in range(16)], up=(1, 0, 0))
        L.transform(bm, bm.verts, shift)
        L.finish_bm(bm, f"двустворчатая_ручка_{tag}", coll, m["alu"], pivot, bevel=0.001, segs=1, angle=40)
        bm = bmesh.new()
        for zc in (0.28, 1.25, 2.17):
            for za, zb_ in ((zc - 0.05, zc - 0.0007), (zc + 0.0007, zc + 0.05)):
                L.bm_cyl(bm, (0, 0, za), (0, 0, zb_), 0.0075, 20)
            L.bm_sphere(bm, (0, 0, zc - 0.05), 0.006, 14, 7)
            L.bm_sphere(bm, (0, 0, zc + 0.05), 0.006, 14, 7)
        L.finish_bm(bm, f"двустворчатая_петли_{tag}", coll, m["steel"], pivot, bevel=0.0008, segs=1, angle=40)
    return r


# ---------------------------------------------------------------- глухие стены

def plain_walls(coll, m: dict, at=(0, 0, 0)) -> bpy.types.Object:
    """Глухие отрезки 1 м: перегородка 0,15, несущая 0,38, фасад 0,64. Длина растягивается по X при сборке."""
    r = L.root("M18_стены_глухие", coll, at)
    for i, (t, h) in enumerate(((WALL_PART, CEIL), (WALL_LOAD, CEIL), (WALL_FACADE, CEIL + SLAB))):
        bm = bmesh.new()
        L.bm_box(bm, (-0.5, -t / 2, 0), (0.5, t / 2, h))
        ob = L.finish_bm(bm, f"стена_глухая_{int(round(t * 1000))}", coll, m["plaster"], r)
        ob.location.x = i * 1.4
    return r


# ---------------------------------------------------------------- сборки для просмотра

def instance(src_root, coll, at, rot_z: float = 0.0) -> bpy.types.Object:
    """Связанная копия модуля (сетки общие): правка модуля видна и в сборке."""
    new_root = src_root.copy()
    new_root.location = at
    new_root.rotation_euler = (0, 0, rot_z)
    coll.objects.link(new_root)

    def walk(src, dst):
        for ch in src.children:
            c = ch.copy()
            c.parent = dst
            c.matrix_parent_inverse = ch.matrix_parent_inverse.copy()
            coll.objects.link(c)
            walk(ch, c)
    walk(src_root, new_root)
    return new_root


def corridor_bay(top, mods: dict, m: dict, x0: float, y0: float) -> None:
    """Кусок коридора 6 м: слева стена с дверью комнаты, справа глухая, портал из пилястр и балки,
    плиты перекрытия, плинтусы. Пол — временная плита только для этой сборки."""
    c = L.collection("Сборка_коридор", top)
    half = 1.7
    xa, xb = x0 - 1.25, x0 + 5.95
    wy = y0 - half - WALL_LOAD / 2
    instance(mods["wall_door"], c, (x0 + 1.4, wy, 0))
    instance(mods["door"], c, (x0 + 1.4, wy, 0))
    for a, b in ((xa, x0 + 0.2), (x0 + 2.6, xb)):
        bm = bmesh.new()
        L.bm_box(bm, (a, y0 - half - WALL_LOAD, 0), (b, y0 - half, CEIL))
        L.finish_bm(bm, "сборка_стена_добор", c, m["plaster"])
    bm = bmesh.new()
    L.bm_box(bm, (xa, y0 + half, 0), (xb, y0 + half + WALL_LOAD, CEIL))
    L.finish_bm(bm, "сборка_стена_глухая", c, m["plaster"])
    bm = bmesh.new()
    L.bm_box(bm, (xa, y0 - half - WALL_LOAD, -0.1), (xb, y0 + half + WALL_LOAD, 0))
    L.finish_bm(bm, "сборка_пол_временный", c, L.material("Пол_временный", (0.42, 0.40, 0.37), 0.8))
    for i in range(6):
        instance(mods["slab_corridor"], c, (xa + 0.6 + i * 1.2, y0, CEIL))
    instance(mods["beam"], c, (x0 + 3.3, y0, CEIL))
    instance(mods["pilaster"], c, (x0 + 3.3, y0 - half, 0))
    instance(mods["pilaster"], c, (x0 + 3.3, y0 + half, 0), math.pi)
    # Плинтус метровыми отрезками: вдоль глухой стены до пилястры, вдоль стены с дверью — до наличника.
    for xc in (xa + 0.5, xa + 1.5, xa + 2.5, xa + 3.5):
        copy_obj(mods["skirt_straight"], c, (xc, y0 + half, 0), math.pi)
    for xc in (xa + 0.5, xa + 1.45):
        copy_obj(mods["skirt_straight"], c, (xc, y0 - half, 0))


def copy_obj(src, coll, at, rot_z: float = 0.0) -> bpy.types.Object:
    """Связанная копия одной детали без родителя."""
    c = src.copy()
    c.parent = None
    c.location = at
    c.rotation_euler = (0, 0, rot_z)
    coll.objects.link(c)
    return c


def stair_core(top, mods: dict, m: dict, x0: float, y0: float) -> None:
    """Межэтажная лестница жилого этажа: марш 10 вверх, площадка, марш 10 обратно, ограждение с поворотом.
    Поворот ограждения считается от концов поручней обоих маршей и строится здесь же (модуль M13)."""
    c = L.collection("Сборка_лестница", top)
    n, riser = 10, 0.162
    run, rise = n * TREAD, n * riser
    instance(mods["flight10"], c, (x0 - 0.9, y0, 0))
    instance(mods["landing"], c, (x0, y0 + run, rise))
    instance(mods["flight10"], c, (x0 + 0.9, y0 + run, rise), math.pi)
    instance(mods["rail10"], c, (x0 - 0.9, y0, 0))
    instance(mods["rail10"], c, (x0 + 0.9, y0 + run, rise), math.pi)
    k, xb, strip_top = riser / TREAD, FLIGHT_W / 2 + 0.03, 0.855
    y_end = run - 0.05 + 0.06
    p_low = (-0.9 + xb, y_end, riser + k * y_end + strip_top)
    y_start = 0.05 - 0.06
    p_high = (0.9 - xb, run - y_start, rise + riser + k * y_start + strip_top)
    railing_turn(L.collection("M13_ограждение_поворот", top), m, p_low, p_high, rise, at=(x0, y0, 0))


# ---------------------------------------------------------------- сборка

def clear_scene() -> None:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)


def build() -> None:
    clear_scene()
    bpy.context.scene.unit_settings.system = "METRIC"
    m = mats()
    top = L.collection("Модули_общежития_этап2")
    # Дверь комнаты в коридорной стене 0,38 (ширина куска стены 2,4 м — остальное доборные отрезки).
    c = L.collection("M01_дверь_комнаты", top)
    door_room(c, m)
    c = L.collection("M02_стена_с_дверью_380", top)
    wall_with_opening("M02_стена_с_дверью_380", c, m, 2.4, CEIL, WALL_LOAD, -(CLEAR_W / 2 + STOP + LINING),
                      CLEAR_W / 2 + STOP + LINING, 0.0, CLEAR_H + STOP + LINING)
    # Окно в фасаде 0,64; батарея у внутренней грани.
    x = 4.0
    c = L.collection("M03_окно", top)
    window(c, m, at=(x, 0, 0))
    c = L.collection("M04_стена_с_окном_640", top)
    wall_with_opening("M04_стена_с_окном_640", c, m, 3.0, CEIL + SLAB, WALL_FACADE, -WIN_W / 2, WIN_W / 2,
                      WIN_SILL - 0.04, WIN_TOP, at=(x, 0, 0))
    c = L.collection("M05_батарея", top)
    radiator(c, m, at=(x, WALL_FACADE / 2, 0))
    c = L.collection("M06_плинтус", top)
    skirting(c, m, at=(7.0, 0.6, 0))
    # Остеклённая двустворчатая дверь в поперечной перегородке.
    c = L.collection("M07_дверь_двустворчатая", top)
    glazed_double_door(c, m, at=(11.0, 0, 0))
    c = L.collection("M08_перегородка_с_двустворчатой_150", top)
    wall_with_opening("M08_перегородка_с_двустворчатой_150", c, m, 3.4, CEIL, WALL_PART, -1.26, 1.26, 0.0, 2.76,
                      at=(11.0, 0, 0))
    # Лестница: марши 12 (1-й этаж) и 10 (жилые), площадка, ограждения.
    c = L.collection("M09_марш_12", top)
    f12 = stair_flight(c, m, 12, 0.1642, "M09_марш_12", at=(15.0, -2.0, 0))
    c = L.collection("M10_марш_10", top)
    f10 = stair_flight(c, m, 10, 0.162, "M10_марш_10", at=(17.0, -2.0, 0))
    c = L.collection("M11_площадка", top)
    land = landing(c, m, at=(20.5, -2.0, 0.22))
    c = L.collection("M12_ограждение_марша", top)
    railing_flight(c, m, 12, 0.1642, "M12_ограждение_марша_12", at=(15.0, -2.0, 0))
    rail10 = railing_flight(c, m, 10, 0.162, "M12_ограждение_марша_10", at=(17.0, -2.0, 0))
    # Потолок: плиты по ширине коридора и по глубине комнаты, балка, пилястра.
    c = L.collection("M14_плита_коридор", top)
    slab_c = ceiling_slab(c, m, 3.64, "M14_плита_коридор", at=(24.0, 0, 0))
    c = L.collection("M15_плита_комната", top)
    ceiling_slab(c, m, 7.04, "M15_плита_комната", at=(25.5, 0, 0))
    c = L.collection("M16_балка", top)
    bm_root = beam(c, m, at=(27.0, 0, 0.4))
    c = L.collection("M17_пилястра", top)
    pil = pilaster(c, m, at=(28.0, 0, 0))
    c = L.collection("M18_стены_глухие", top)
    plain_walls(c, m, at=(30.0, 0, 0))

    mods = {"wall_door": bpy.data.objects["M02_стена_с_дверью_380"], "door": bpy.data.objects["M01_дверь_комнаты"],
            "slab_corridor": slab_c, "beam": bm_root, "pilaster": pil, "skirt_straight": bpy.data.objects["плинтус_1м"],
            "flight10": f10, "landing": land, "rail10": rail10}
    corridor_bay(top, mods, m, 0.0, -8.0)
    stair_core(top, mods, m, 12.0, -10.0)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = argv[0] if argv else os.path.join(os.path.dirname(__file__), "dorm_modules_test.blend")
    build()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)
