"""Опоры под кассовый аппарат для карты «Проспект», форма без текстур (Blender 5, bmesh).

  ПТ_ — прилавок торговый (кассовая тумба небольшого магазина, ЛДСП 16 мм, 1500 × 600 × 900 мм);
  КБ_ — кассовый бокс супермаркета (транспортёр + накопитель, нержавеющая столешница, место кассира).

Соглашения партии 1 (lc.py): метры, Z вверх, лицо к −Y (покупатель), корень-пустышка на опоре (полу), у каждого предмета
пустышка socket_register — место и поворот кассы (дно кассы — в начале пустышки, касса клавиатурой к продавцу).
Соприкасающиеся детали разведены на G = 0,1 мм (швы настоящей сборки), чтобы пересечений не было.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import lc
from lc import L, V, B

G = 0.0001


# ---------------------------------------------------------------- материалы

def cmats() -> dict:
    M = L.material
    return {
        "lam": M("ЛДСП корпус", (0.58, 0.46, 0.30), 0.55),
        "lam_edge": M("Кромка ПВХ корпус", (0.48, 0.37, 0.23), 0.45),
        "trim": M("ЛДСП накладка", (0.10, 0.065, 0.05), 0.5),
        "top": M("Столешница", (0.13, 0.10, 0.085), 0.4),
        "top_edge": M("Кромка ПВХ столешница", (0.09, 0.065, 0.05), 0.45),
        "glam": M("ЛДСП графит", (0.13, 0.14, 0.15), 0.5),
        "gedge": M("Кромка ПВХ графит", (0.09, 0.1, 0.11), 0.45),
        "ss": M("Нержавейка", (0.72, 0.72, 0.71), 0.28, 1.0),
        "paint": M("Крашеная сталь", (0.17, 0.21, 0.23), 0.45, 0.3),
        "rubber": M("Чёрная резина лента", (0.015, 0.015, 0.015), 0.85),
        "plastic": M("Пластик", (0.30, 0.31, 0.32), 0.45),
        "pblack": M("Пластик чёрный", (0.03, 0.03, 0.03), 0.45),
        "pwhite": M("Пластик белый", (0.82, 0.82, 0.80), 0.4),
        "zinc": M("Оцинкованный крепёж", (0.6, 0.6, 0.58), 0.35, 1.0),
        "glass": M("Стекло сканера", (0.02, 0.03, 0.04), 0.05),
        "human": M("Фигура масштаб", (0.5, 0.52, 0.55), 0.8),
    }


# ---------------------------------------------------------------- помощники геометрии

def lam(bm, mn, mx, face: int = 0, edge: int = 1, g: float = G):
    """Плита ЛДСП: пласти — слот face, торцы (кромка) — слот edge; габарит уменьшен на шов g."""
    return B.board(bm, [a + g for a in mn], [a - g for a in mx], face, edge)


def bx(bm, mn, mx, g: float = G):
    return L.bm_box(bm, [a + g for a in mn], [a - g for a in mx])


def mk(bm, name, coll, mats, parent, bevel: float = 0.0, segs: int = 2, angle: float = 40.0, smooth: float = 40.0):
    return lc.obj(bm, name, coll, mats, parent, bevel=bevel, segs=segs, angle=angle, smooth=smooth)


def add_bevel(ob, width: float, segs: int = 2, angle: float = 40.0) -> None:
    md = ob.modifiers.new("Фаска", "BEVEL")
    md.width = width
    md.segments = segs
    md.limit_method = "ANGLE"
    md.angle_limit = math.radians(angle)
    md.harden_normals = True
    md.use_clamp_overlap = True


def cut(ob, cutters, coll, parent) -> None:
    """Вырезы булевой разностью (точный решатель); результат запекается в сетку — модификаторов и вспомогательных тел не остаётся.
    cutters: ("cyl", (cx, cy), r, z0, z1) или ("box", mn, mx)."""
    dummy = bpy.data.materials.get("Вырез_пустой") or bpy.data.materials.new("Вырез_пустой")
    for c in cutters:
        cb = bmesh.new()
        if c[0] == "cyl":
            L.bm_cyl(cb, (c[1][0], c[1][1], c[3]), (c[1][0], c[1][1], c[4]), c[2], segs=40)
        else:
            L.bm_box(cb, c[1], c[2])
        co = lc.obj(cb, "tmp_вырез", coll, [dummy], parent)
        md = ob.modifiers.new("Вырез", "BOOLEAN")
        md.object = co
        md.operation = "DIFFERENCE"
        md.solver = "EXACT"
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        old = ob.data
        ob.modifiers.remove(md)
        ob.data = me
        bpy.data.meshes.remove(old)
        try:
            me.set_sharp_from_angle(angle=math.radians(40))
        except AttributeError:
            pass
        bpy.data.objects.remove(co)


def ring_prism(bm, outer, inner, z0: float, z1: float) -> None:
    """Кольцо между двумя контурами с одинаковым числом точек, выдавленное от z0 до z1 (замкнутая оболочка)."""
    n = len(outer)
    ot = [bm.verts.new((x, y, z1)) for x, y in outer]
    ob_ = [bm.verts.new((x, y, z0)) for x, y in outer]
    it = [bm.verts.new((x, y, z1)) for x, y in inner]
    ib = [bm.verts.new((x, y, z0)) for x, y in inner]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((ot[i], ot[j], it[j], it[i]))
        bm.faces.new((ob_[j], ob_[i], ib[i], ib[j]))
        bm.faces.new((ob_[i], ob_[j], ot[j], ot[i]))
        bm.faces.new((it[i], it[j], ib[j], ib[i]))


def circle(cx: float, cy: float, r: float, n: int = 32):
    return [(cx + r * math.cos(math.tau * i / n), cy + r * math.sin(math.tau * i / n)) for i in range(n)]


def annulus(bm, cx, cy, r_out, r_in, z0, z1, n: int = 32) -> None:
    ring_prism(bm, circle(cx, cy, r_out, n), circle(cx, cy, r_in, n), z0, z1)


def revolve(bm, profile, cx: float, cy: float, z0: float, segs: int = 36) -> None:
    """Тело вращения вокруг вертикали: profile — замкнутый контур (r, z); точки на оси (r = 0) — одна вершина."""
    rings = []
    for r, z in profile:
        if r < 1e-9:
            rings.append([bm.verts.new((cx, cy, z0 + z))] * segs)
        else:
            rings.append([bm.verts.new((cx + r * math.cos(math.tau * k / segs), cy + r * math.sin(math.tau * k / segs), z0 + z)) for k in range(segs)])
    n = len(profile)
    for i in range(n):
        a, b = rings[i], rings[(i + 1) % n]
        for k in range(segs):
            k2 = (k + 1) % segs
            vs = []
            for v in (a[k], a[k2], b[k2], b[k]):
                if v not in vs:
                    vs.append(v)
            if len(vs) >= 3:
                bm.faces.new(vs)


def xcyl(bm, xf: float, sgn: int, y: float, z: float, r: float, ln: float, segs: int = 10) -> None:
    """Цилиндр вдоль X, стоящий на вертикальной грани x = xf и выступающий на ln в сторону sgn."""
    L.bm_cyl(bm, (xf + sgn * G, y, z), (xf + sgn * ln, y, z), r, segs=segs)


def ycyl(bm, yf: float, sgn: int, x: float, z: float, r: float, ln: float, segs: int = 12) -> None:
    L.bm_cyl(bm, (x, yf + sgn * G, z), (x, yf + sgn * ln, z), r, segs=segs)


def zcyl(bm, x, y, z0, z1, r, segs: int = 16, r1=None) -> None:
    L.bm_cyl(bm, (x, y, z0), (x, y, z1), r, segs=segs, r1=r1)


def grommet(bm, cx, cy, zt: float, thick: float, hole_r: float = 0.030, with_lid: bool = False) -> None:
    """Кабельный вывод Ø 60 в столешнице (верх столешницы — zt, толщина thick): фланец сверху, втулка в отверстии, у counter — полукрышка."""
    annulus(bm, cx, cy, 0.0375, 0.0265, zt + G, zt + 0.003)
    annulus(bm, cx, cy, hole_r - 0.0005, 0.0265, zt - thick + 0.004, zt - G)
    if with_lid:
        pts = [(cx + 0.026 * math.cos(math.radians(a)), cy + 0.026 * math.sin(math.radians(a))) for a in range(0, 181, 15)]
        n = len(pts)
        zb, zu = zt + 0.001, zt + 0.0035
        bot = [bm.verts.new((x, y, zb)) for x, y in pts]
        top = [bm.verts.new((x, y, zu)) for x, y in pts]
        bm.faces.new(bot[::-1])
        bm.faces.new(top)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((bot[i], bot[j], top[j], top[i]))


def human(coll, mat, at, yaw: float = 0.0, h: float = 1.75):
    """Простая фигура человека для масштаба (≈ 1,75 м), лицом к −Y; yaw — поворот вокруг Z, градусов."""
    r = L.root("Фигура_1_75", coll, at)
    r.rotation_euler = (0, 0, math.radians(yaw))
    bm = bmesh.new()
    for s in (-1, 1):
        zcyl(bm, s * 0.09, 0, 0.05, 0.88, 0.06, 14, r1=0.075)      # ноги
        L.bm_box(bm, (s * 0.09 - 0.05, -0.17, 0.0), (s * 0.09 + 0.05, 0.08, 0.05))   # ступни
        zcyl(bm, s * 0.22, 0, 0.88, 1.45, 0.045, 12)               # руки
    lc.rbox(bm, (0.40, 0.22, 0.64), 0.05, (0, 0, 1.20), seg=3)     # туловище
    zcyl(bm, 0, 0, 1.50, 1.56, 0.055, 12)                           # шея
    L.bm_sphere(bm, (0, 0, h - 0.11), 0.11, segs=20, rings=12)      # голова
    mk(bm, "Фигура_1_75_тело", coll, [mat], r, smooth=60)
    return r


# ---------------------------------------------------------------- А. прилавок торговый

def counter(coll, m, at):
    """Прилавок торговый 1500 × 600 × 900: ЛДСП 16 мм (боковины, глухая передняя панель с накладкой, перегородки, полки на штифтах),
    столешница 38 мм со свесом 35 мм к покупателю, цоколь 100 мм с утопленной планкой и регулируемые опоры. Со стороны продавца (+Y):
    открытые полки, ниша под системный блок / денежный ящик, один выдвижной ящик на телескопах со скобой, кабельный вывод Ø 60.
    Корень — середина основания на полу. socket_register — на столешнице."""
    r = L.root("ПТ_прилавок", coll, at)
    t = 0.016
    X, XI = 0.75, 0.75 - t
    YF, YB, YI0, YI1 = -0.265, 0.298, -0.249, 0.285
    ZT, ZTOP = 0.862, 0.90
    LAM = [m["lam"], m["lam_edge"]]
    ZB = 0.10                     # верх цоколя / низ дна
    # боковины
    bm = bmesh.new()
    for s in (-1, 1):
        lam(bm, (min(s * X, s * XI), YF, 0.01), (max(s * X, s * XI), YB, ZT))
    mk(bm, "ПТ_боковины", coll, LAM, r, bevel=0.001)
    # дно
    bm = bmesh.new()
    lam(bm, (-XI, YI0, ZB), (XI, YI1, ZB + t))
    mk(bm, "ПТ_дно", coll, LAM, r, bevel=0.001)
    # перегородки
    DX = 0.25
    bm = bmesh.new()
    for s in (-1, 1):
        lam(bm, (s * DX - t / 2, YI0, ZB + t), (s * DX + t / 2, YI1, ZT))
    mk(bm, "ПТ_перегородки", coll, LAM, r, bevel=0.001)
    # полки: слева 0,40 и 0,64, справа 0,36 и 0,60 (низ полки)
    SH_L, SH_R = (0.40, 0.64), (0.36, 0.60)
    bm = bmesh.new()
    for z in SH_L:
        lam(bm, (-XI, YI0, z), (-DX - t / 2, YI1, z + t))
    for z in SH_R:
        lam(bm, (DX + t / 2, YI0, z), (XI, YI1, z + t))
    mk(bm, "ПТ_полки", coll, LAM, r, bevel=0.001)
    # передняя панель (глухая) и накладка-полоса
    bm = bmesh.new()
    lam(bm, (-XI, YF, ZB), (XI, YI0, ZT))
    mk(bm, "ПТ_панель_передняя", coll, LAM, r, bevel=0.001)
    bm = bmesh.new()
    lam(bm, (-0.60, YF - 0.010, 0.40), (0.60, YF, 0.62), face=0, edge=1)
    mk(bm, "ПТ_накладка_полоса", coll, [m["trim"], m["lam_edge"]], r, bevel=0.0012)
    # цоколь: утопленная планка (пластиковый профиль на клипсах), 40 мм вглубь от лица
    bm = bmesh.new()
    bx(bm, (-XI, -0.225, 0.003), (XI, -0.209, ZB - 0.002))
    mk(bm, "ПТ_цоколь_планка", coll, [m["pblack"]], r, bevel=0.0012)
    # столешница 38 мм, скругление кромки R 2,5, отверстие под кабельный вывод
    bm = bmesh.new()
    lam(bm, (-X, -0.30, ZT), (X, 0.30, ZTOP), face=0, edge=1)
    top = mk(bm, "ПТ_столешница", coll, [m["top"], m["top_edge"]], r)
    GX, GY = -0.52, 0.20
    cut(top, [("cyl", (GX, GY), 0.030, ZT - 0.01, ZTOP + 0.01)], coll, r)
    add_bevel(top, 0.0025, 3)
    bm = bmesh.new()
    grommet(bm, GX, GY, ZTOP, 0.038, with_lid=True)
    mk(bm, "ПТ_кабельный_вывод", coll, [m["pblack"]], r, bevel=0.0004, segs=1)
    # штифты полок (оцинкованные)
    bm = bmesh.new()
    for z0, xf, sgn in [(z, -XI, 1) for z in SH_L] + [(z, -DX - t / 2, -1) for z in SH_L] + \
            [(z, DX + t / 2, 1) for z in SH_R] + [(z, XI, -1) for z in SH_R]:
        for y in (-0.20, 0.23):
            xcyl(bm, xf, sgn, y, z0 - 0.0025 - G, 0.0025, 0.008, 10)
    mk(bm, "ПТ_штифты_полок", coll, [m["zinc"]], r, smooth=60)
    # эксцентриковые стяжки на внутренних гранях (диск Ø15 с шлицем)
    bm = bmesh.new()
    faces = [(-XI, 1, (0.150, 0.450, 0.710)), (-DX - t / 2, -1, (0.150, 0.450, 0.710)), (-DX + t / 2, 1, (0.150,)),
             (DX - t / 2, -1, (0.150,)), (DX + t / 2, 1, (0.150, 0.410, 0.650)), (XI, -1, (0.150, 0.410, 0.650))]
    for xf, sgn, zs in faces:
        for z in zs:
            for y in (-0.20, 0.23):
                xcyl(bm, xf, sgn, y, z, 0.0075, 0.0015, 12)
                L.bm_box(bm, (min(xf + sgn * 0.0015, xf + sgn * 0.0021), y - 0.0065, z - 0.0012),
                         (max(xf + sgn * 0.0015, xf + sgn * 0.0021), y + 0.0065, z + 0.0012))
    mk(bm, "ПТ_эксцентрики", coll, [m["zinc"]], r, smooth=60)
    # заглушки конфирматов на наружных гранях боковин
    bm = bmesh.new()
    for xf, sgn, zs in ((-X, -1, (0.108, 0.408, 0.648, 0.846)), (X, 1, (0.108, 0.368, 0.608, 0.846))):
        for z in zs:
            for y in (-0.20, 0.22):
                xcyl(bm, xf, sgn, y, z, 0.0065, 0.001, 14)
    mk(bm, "ПТ_заглушки_конфирматов", coll, [m["lam_edge"]], r, smooth=60)
    # уголки-соединители под столешницей (оцинкованные L 25 × 30 × 2) и винты
    bm = bmesh.new()
    for xf, sgn in ((-XI, 1), (-DX - t / 2, -1), (-DX + t / 2, 1), (DX - t / 2, -1), (DX + t / 2, 1), (XI, -1)):
        for y in (-0.12, 0.20):
            x0, x1 = sorted((xf + sgn * G, xf + sgn * 0.002))
            L.bm_box(bm, (x0, y - 0.015, ZT - 0.025), (x1, y + 0.015, ZT - G))
            xa, xb = sorted((xf + sgn * 0.002, xf + sgn * 0.025))
            L.bm_box(bm, (xa + sgn * G, y - 0.015, ZT - 0.002), (xb, y + 0.015, ZT - G)) if False else \
                L.bm_box(bm, (min(xf + sgn * 0.0021, xf + sgn * 0.025), y - 0.015, ZT - 0.002 - G), (max(xf + sgn * 0.0021, xf + sgn * 0.025), y + 0.015, ZT - G))
            xcyl(bm, xf + sgn * 0.002, sgn, y, ZT - 0.0125, 0.003, 0.002, 10)
    mk(bm, "ПТ_уголки", coll, [m["zinc"]], r, bevel=0.0004, segs=1, smooth=60)
    # регулируемые опоры: пятка, штанга с гайкой, площадка под дном
    bm = bmesh.new()
    for fx in (-0.70, 0.70):
        for fy in (-0.17, 0.25):
            zcyl(bm, fx, fy, 0.0, 0.006, 0.025, 20, r1=0.022)
    mk(bm, "ПТ_опоры_пятки", coll, [m["pblack"]], r, bevel=0.0008, segs=1)
    bm = bmesh.new()
    for fx in (-0.70, 0.70):
        for fy in (-0.17, 0.25):
            zcyl(bm, fx, fy, 0.006 + G, 0.097, 0.006, 12)
            zcyl(bm, fx, fy, 0.034, 0.042, 0.0105, 6)
            L.bm_box(bm, (fx - 0.02, fy - 0.02, 0.097), (fx + 0.02, fy + 0.02, ZB - G))
    mk(bm, "ПТ_опоры_штанги", coll, [m["zinc"]], r, smooth=50)
    # ---- выдвижной ящик (под столешницей, средний отсек): лицо с началом в узле, ход 0,35 м к продавцу
    dpiv = (0.0, YI1, 0.7775)
    RZ0, RZ1 = 0.745, 0.790
    bm = bmesh.new()
    for s in (-1, 1):   # неподвижные рельсы на перегородках
        x0, x1 = sorted((s * (DX - t / 2), s * (DX - t / 2 - 0.0127)))
        bx(bm, (x0, -0.10, RZ0), (x1, 0.265, RZ1))
    mk(bm, "ПТ_ящик_рельсы_неподвижные", coll, [m["zinc"]], r, bevel=0.0004, segs=1, smooth=50)
    bm = bmesh.new()
    lam(bm, (-0.2405, YI1 - 0.016, 0.700), (0.2405, YI1, 0.855))
    drw = lc.part(bm, "ПТ_ящик_лицо", coll, LAM, r, (0, 0, 0), dpiv, bevel=0.001, mover=True)
    # скоба-ручка 128 мм, Ø 12, на двух бобышках
    bm = bmesh.new()
    B.pipe(bm, [(-0.064, YI1 + G, dpiv[2]), (-0.064, YI1 + 0.030, dpiv[2]), (0.064, YI1 + 0.030, dpiv[2]), (0.064, YI1 + G, dpiv[2])],
           0.006, segs=14, bend=0.008)
    lc.part(bm, "ПТ_ящик_ручка", coll, [m["zinc"]], drw, dpiv, dpiv, smooth=60)
    # короб: боковины и задняя стенка ЛДСП 16, дно ХДФ 3 мм
    bm = bmesh.new()
    for s in (-1, 1):
        lam(bm, (min(s * 0.2166, s * 0.2006), -0.131, 0.715), (max(s * 0.2166, s * 0.2006), YI1 - 0.016, 0.835))
    lam(bm, (-0.2006, -0.131, 0.715), (0.2006, -0.115, 0.835))
    lc.part(bm, "ПТ_ящик_короб", coll, LAM, drw, dpiv, dpiv, bevel=0.0008)
    bm = bmesh.new()
    bx(bm, (-0.2166, -0.131, 0.712), (0.2166, YI1 - 0.016, 0.715))
    lc.part(bm, "ПТ_ящик_дно_ХДФ", coll, [m["lam_edge"]], drw, dpiv, dpiv, bevel=0.0004, segs=1)
    bm = bmesh.new()
    for s in (-1, 1):   # подвижные рельсы
        x0, x1 = sorted((s * 0.2166, s * 0.2293))
        bx(bm, (x0, -0.12, RZ0), (x1, 0.25, RZ1))
    lc.part(bm, "ПТ_ящик_рельсы_подвижные", coll, [m["zinc"]], drw, dpiv, dpiv, bevel=0.0004, segs=1, smooth=50)
    # ---- на столешнице: монетница-тарелка и держатель пакетов
    bm = bmesh.new()
    prof = [(0.0, 0.0), (0.082, 0.0), (0.098, 0.016), (0.106, 0.024), (0.103, 0.026), (0.098, 0.021), (0.080, 0.0035), (0.0, 0.0035)]
    revolve(bm, prof, 0.30, -0.10, ZTOP + G, 40)
    mk(bm, "ПТ_монетница", coll, [m["pblack"]], r, smooth=50)
    bm = bmesh.new()
    zcyl(bm, 0.30, -0.10, ZTOP + 0.0038, ZTOP + 0.0048, 0.078, 36)
    mk(bm, "ПТ_монетница_коврик", coll, [m["rubber"]], r, smooth=50)
    hx, hy = 0.60, 0.12
    bm = bmesh.new()
    L.bm_box(bm, (hx - 0.06, hy - 0.05, ZTOP + G), (hx + 0.06, hy + 0.05, ZTOP + 0.003))
    zcyl(bm, hx, hy, ZTOP + 0.003 + G, 1.18, 0.004, 12)
    B.pipe(bm, [(hx - 0.095, hy - 0.05, 1.18), (hx - 0.095, hy, 1.18), (hx + 0.095, hy, 1.18), (hx + 0.095, hy - 0.05, 1.18)],
           0.0025, segs=8, bend=0.01)
    mk(bm, "ПТ_держатель_пакетов", coll, [m["zinc"]], r, bevel=0.0004, segs=1, smooth=60)
    bm = bmesh.new()
    L.bm_box(bm, (hx - 0.085, hy - 0.036, 0.95), (hx + 0.085, hy - 0.024, 1.17))
    mk(bm, "ПТ_пакеты_стопка", coll, [m["pwhite"]], r, bevel=0.0005, segs=1)
    # ---- пустышка под кассу: клавиатурой к продавцу (+Y), дисплеем покупателя к покупателю
    s = bpy.data.objects.new("socket_register", None)
    s.empty_display_type = "ARROWS"
    s.empty_display_size = 0.12
    s.parent = r
    s.location = (-0.25, 0.0, ZTOP)
    s.rotation_euler = (0, 0, math.pi)
    coll.objects.link(s)
    return r


# ---------------------------------------------------------------- Б. кассовый бокс супермаркета

def checkout(coll, m, at):
    """Кассовый бокс 2400 × 1100 × 870 (по образцам сетевых боксов с узким транспортёром и накопителем): корпус из крашеной стали с чёрным
    цоколем, нержавеющая столешница с лентой заподлицо, окном сканера и кабельными выводами, накопитель с пластиковым бортом, труба-отбойник,
    труба-ограждение конца, стол кассира на стойке-ногe и торцевой панели, подставка под кассу с нишей денежного ящика, полка для корзин,
    стойка с табличкой-номером и лампой. Корень — на полу в середине корпуса. socket_register — на подставке под кассу."""
    r = L.root("КБ_кассовый_бокс", coll, at)
    XL, XR, YF, YB = -1.15, 1.15, -0.55, 0.05
    ZB, ZD, ZS = 0.10, 0.80, 0.82      # верх цоколя, верх корпуса, верх нержавейки
    cy = (YF + YB) / 2
    # корпус и цоколь
    bm = bmesh.new()
    L.bm_prism(bm, L.rrect(2.30, 0.60, 0.014, 3, 0.0, cy), V((0, 0, ZB + G)), (1, 0, 0), (0, 1, 0), (0, 0, ZD - ZB - 2 * G))
    body = mk(bm, "КБ_корпус", coll, [m["paint"]], r, bevel=0.002, segs=2, angle=50.0)
    bm = bmesh.new()
    L.bm_prism(bm, L.rrect(2.33, 0.63, 0.02, 3, 0.0, cy), V((0, 0, 0.0)), (1, 0, 0), (0, 1, 0), (0, 0, ZB))
    mk(bm, "КБ_цоколь", coll, [m["pblack"]], r, bevel=0.003, segs=2, angle=50.0)
    # швы панелей и сервисная дверца на лицевой стороне (−Y)
    bm = bmesh.new()
    for x in (-0.65, 0.25):
        L.bm_box(bm, (x - 0.002, YF - 0.0006, ZB + 0.02), (x + 0.002, YF - G, ZD - 0.02))
    L.bm_box(bm, (-0.65 - 0.002, YB + G, ZB + 0.02), (-0.65 + 0.002, YB + 0.0006, ZD - 0.02))
    mk(bm, "КБ_швы_панелей", coll, [m["pblack"]], r)
    bm = bmesh.new()
    lc.hole_plate(bm, 0.50, 1.04, 0.20, 0.58, YF - 0.003, YF - G, (0.512, 1.028, 0.212, 0.568))
    lc.plug(bm, (0.985, YF - 0.003, 0.39), depth=0.002, r=0.009, axis="-y")
    mk(bm, "КБ_дверца_сервисная", coll, [m["plastic"]], r, bevel=0.0006, segs=1)
    # нержавеющая столешница: куски вокруг ленты, окна сканера и кабельных выводов; лента заподлицо
    bm = bmesh.new()
    bx(bm, (XL, YF, ZD), (-1.12, YB, ZS))
    bx(bm, (-1.12, YF, ZD), (-0.27, -0.51, ZS))
    bx(bm, (-1.12, 0.01, ZD), (-0.27, YB, ZS))
    bx(bm, (0.25, YF, ZD), (XR, YB, ZS))
    deck = mk(bm, "КБ_столешница_нержавейка", coll, [m["ss"]], r)
    add_bevel(deck, 0.0008, 2)
    bm = bmesh.new()
    bx(bm, (-0.27, YF, ZD), (0.25, YB, ZS))
    scan = mk(bm, "КБ_столешница_сканер", coll, [m["ss"]], r)
    WX, WY = 0.0, -0.26
    cut(scan, [("box", (WX - 0.1075, WY - 0.0675, ZD - 0.01), (WX + 0.1075, WY + 0.0675, ZS + 0.01)),
               ("cyl", (-0.17, -0.04), 0.030, ZD - 0.01, ZS + 0.01), ("cyl", (0.17, -0.04), 0.030, ZD - 0.01, ZS + 0.01)], coll, r)
    add_bevel(scan, 0.0008, 2)
    bm = bmesh.new()
    bx(bm, (-1.12, -0.51, ZD), (-0.27, 0.01, ZS))
    mk(bm, "КБ_лента_транспортёра", coll, [m["rubber"]], r, bevel=0.0006, segs=1)
    # рамка и стекло окна сканера
    bm = bmesh.new()
    ring_prism(bm, L.rrect(0.2145, 0.1345, 0.004, 3, WX, WY), L.rrect(0.19, 0.11, 0.002, 3, WX, WY), ZD + 0.0001, ZS + 0.0005)
    mk(bm, "КБ_сканер_рамка", coll, [m["pblack"]], r, bevel=0.0005, segs=1)
    bm = bmesh.new()
    bx(bm, (WX - 0.0940, WY - 0.0540, ZS - 0.004), (WX + 0.0940, WY + 0.0540, ZS - 0.001))
    mk(bm, "КБ_сканер_стекло", coll, [m["glass"]], r, smooth=60)
    bm = bmesh.new()
    for gx in (-0.17, 0.17):
        grommet(bm, gx, -0.04, ZS, 0.02)
    mk(bm, "КБ_кабельные_выводы", coll, [m["pblack"]], r, bevel=0.0004, segs=1)
    # пластиковые борта: приёмный стол (вход ленты) и накопитель — скруглённый профиль 30 × 50 мм по трём сторонам
    prof = L.rrect(0.030, 0.050, 0.008, 3, 0.0, 0.025)
    bm = bmesh.new()
    L.bm_sweep(bm, [(-0.25, -0.535, ZS + G), (-1.135, -0.535, ZS + G), (-1.135, 0.035, ZS + G), (-0.25, 0.035, ZS + G)], prof)
    L.bm_sweep(bm, [(0.25, -0.535, ZS + G), (1.135, -0.535, ZS + G), (1.135, 0.035, ZS + G), (0.25, 0.035, ZS + G)], prof)
    mk(bm, "КБ_борта_пластик", coll, [m["plastic"]], r, smooth=50)
    # стальной бортик накопителя (гнутый борт 20 мм по трём сторонам, внутри пластикового борта)
    bm = bmesh.new()
    bx(bm, (0.25, -0.514, ZS), (1.114, -0.511, ZS + 0.02))
    bx(bm, (1.114, -0.514, ZS), (1.117, 0.014, ZS + 0.02))
    bx(bm, (0.25, 0.011, ZS), (1.114, 0.014, ZS + 0.02))
    mk(bm, "КБ_накопитель_бортик", coll, [m["ss"]], r, bevel=0.0005, segs=1)
    # отбойник-труба Ø 33 вдоль лица накопителя и труба-ограждение конца прохода Ø 33
    bm = bmesh.new()
    B.pipe(bm, [(0.30, YF - 0.002, 0.20), (0.30, -0.62, 0.20), (1.10, -0.62, 0.20), (1.10, YF - 0.002, 0.20)], 0.0165, segs=16, bend=0.05)
    for fx in (0.30, 1.10):
        ycyl(bm, YF, -1, fx, 0.20, 0.032, 0.003, 20)
    mk(bm, "КБ_отбойник_труба", coll, [m["ss"]], r, smooth=50)
    bm = bmesh.new()
    B.pipe(bm, [(1.235, -0.48, 0.006), (1.235, -0.48, 0.95), (1.235, 0.0, 0.95), (1.235, 0.0, 0.006)], 0.0165, segs=16, bend=0.10)
    for fy in (-0.48, 0.0):
        zcyl(bm, 1.235, fy, 0.0, 0.006, 0.045, 24)
    mk(bm, "КБ_ограждение_труба", coll, [m["ss"]], r, smooth=50)
    # ---- место кассира: стол ЛДСП 25 мм на торцевой панели и ножке-трубе, ниша для корзин под столом
    TT0, TT1 = 0.755, 0.78
    TX0, TX1, TY1 = -0.05, 0.86, 0.55
    LAMG = [m["glam"], m["gedge"]]
    bm = bmesh.new()
    lam(bm, (TX0, YB, TT0), (TX1, TY1, TT1), face=0, edge=1)
    tab = mk(bm, "КБ_стол_кассира", coll, [m["top"], m["top_edge"]], r)
    add_bevel(tab, 0.0022, 3)
    bm = bmesh.new()
    lam(bm, (0.834, YB + 0.025, 0.015), (0.85, TY1 - 0.01, TT0))
    mk(bm, "КБ_стол_торцевая_панель", coll, LAMG, r, bevel=0.001)
    bm = bmesh.new()
    zcyl(bm, -0.025, 0.525, 0.008, TT0 - G, 0.019, 18)
    zcyl(bm, -0.025, 0.525, 0.0, 0.008, 0.045, 24, r1=0.040)
    mk(bm, "КБ_стол_ножка", coll, [m["ss"]], r, smooth=50)
    # полка для корзин и пакетов: лист с бортами, на уголках к корпусу и торцевой панели
    bm = bmesh.new()
    SZ = 0.28
    bx(bm, (0.0, YB + 0.03, SZ), (0.832, TY1 - 0.03, SZ + 0.003))
    bx(bm, (0.0, TY1 - 0.033, SZ + 0.003), (0.832, TY1 - 0.03, SZ + 0.035))
    bx(bm, (0.0, YB + 0.03, SZ + 0.003), (0.003, TY1 - 0.033, SZ + 0.035))
    mk(bm, "КБ_полка_корзин", coll, [m["paint"]], r, bevel=0.0006, segs=1)
    bm = bmesh.new()
    for bx_ in (0.12, 0.70):
        bx(bm, (bx_ - 0.02, YB + G, SZ - 0.03), (bx_ + 0.02, YB + 0.005, SZ))
        bx(bm, (bx_ - 0.02, YB + G, SZ - 0.003), (bx_ + 0.02, YB + 0.03, SZ))
    mk(bm, "КБ_полка_уголки", coll, [m["zinc"]], r, bevel=0.0004, segs=1)
    # подставка под кассу: стальной короб 460 × 440 × 140 с нишей денежного ящика со стороны кассира (+Y)
    SX, SY0, SY1, SZ1 = 0.40, 0.08, 0.52, TT1 + 0.14
    tp = 0.003
    bm = bmesh.new()
    bx(bm, (SX - 0.23, SY0, TT1), (SX + 0.23, SY1, TT1 + tp))
    bx(bm, (SX - 0.23, SY0, SZ1 - tp), (SX + 0.23, SY1, SZ1))
    for s in (-1, 1):
        x0, x1 = sorted((SX + s * 0.23, SX + s * (0.23 - tp)))
        bx(bm, (x0, SY0, TT1 + tp), (x1, SY1, SZ1 - tp))
    bx(bm, (SX - 0.23 + tp, SY0, TT1 + tp), (SX + 0.23 - tp, SY0 + tp, SZ1 - tp))
    bx(bm, (SX - 0.23 + tp, SY0 + tp, TT1 + 0.045), (SX + 0.23 - tp, SY1 - 0.02, TT1 + 0.045 + tp))    # полка ниши
    mk(bm, "КБ_подставка_кассы", coll, [m["paint"]], r, bevel=0.0007, segs=1)
    # стойка с табличкой-номером и лампой (стоит на полу у торца стола)
    px, py = 0.945, 0.48
    bm = bmesh.new()
    L.bm_box(bm, (px - 0.07, py - 0.07, 0.0), (px + 0.07, py + 0.07, 0.006))
    zcyl(bm, px, py, 0.006 + G, 1.78, 0.016, 16)
    mk(bm, "КБ_стойка_номера", coll, [m["ss"]], r, bevel=0.0008, segs=1, smooth=50)
    bm = bmesh.new()
    lc.rbox(bm, (0.060, 0.300, 0.220), 0.010, (px, py, 1.78 + G + 0.110), seg=3)
    mk(bm, "КБ_табличка_корпус", coll, [m["plastic"]], r, smooth=50)
    bm = bmesh.new()
    for sg in (-1, 1):
        xa, xb = sorted((px + sg * 0.0301, px + sg * 0.0309))
        bx(bm, (xa, py - 0.13, 1.78 + 0.03), (xb, py + 0.13, 1.78 + 0.19), g=0.0)
    mk(bm, "КБ_табличка_панели", coll, [m["pwhite"]], r)
    bm = bmesh.new()
    zcyl(bm, px, py, 2.0 + 0.0005, 2.05, 0.05, 24)
    L.bm_sphere(bm, (px, py, 2.0505), 0.045, segs=20, rings=10)
    mk(bm, "КБ_лампа", coll, [m["pwhite"]], r, smooth=60)
    # ---- пустышка под кассу
    s = bpy.data.objects.new("socket_register", None)
    s.empty_display_type = "ARROWS"
    s.empty_display_size = 0.12
    s.parent = r
    s.location = (SX, (SY0 + SY1) / 2, SZ1)
    s.rotation_euler = (0, 0, math.pi)
    coll.objects.link(s)
    return r
