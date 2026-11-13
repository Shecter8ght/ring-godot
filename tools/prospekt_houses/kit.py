"""Набор частей фасада жилых домов «Проспекта» (форма, без текстур) и общие помощники.

Модуль для Blender (bpy): запускается из house7.py. Оси модуля: X вдоль пролёта слева направо, Z вверх, фасад смотрит
в −Y: наружная плоскость облицовки y = 0, вглубь стены — +Y (глубина зоны стены D = 1,6 м). Начало — левый нижний угол
пролёта (вид снаружи). Пролёт выше нуля по высоте этажа (3,0 м) начинается на уровне пола этажа.

Слои вентфасада у панели: плита 20 мм (бежевая) → подсистема 180 мм (тёмная, видна в швах) → бетон до D.
Метры. Скругления — прямо в сетке (bmesh.bevel), модификаторов нет.
"""
import math
import bpy
import bmesh
from mathutils import Vector, Matrix

HF = 3.0          # высота жилого этажа
HG = 4.5          # высота первого этажа
D = 1.6           # глубина зоны стены (облицовка + подсистема + бетон / лоджия)
PT = 0.02         # плита облицовки
SUB = 0.2         # низ подсистемы (где начинается бетон)
JOINT = 0.010     # шов между плитами
LOG_H = 2.45      # высота проёма лоджии под тёмной полосой перекрытия
BAND_H = 0.55     # тёмная полоса перекрытия

# слоты материалов (простые цвета этапа формы; они же станут слотами отделки)
MATS = {
    "panel_beige": ((0.86, 0.60, 0.44, 1), 0.0, 0.70),
    "dark_panel":  ((0.085, 0.087, 0.095, 1), 0.2, 0.55),
    "alu_frame":   ((0.040, 0.042, 0.046, 1), 0.85, 0.38),
    "glass":       ((0.020, 0.040, 0.052, 1), 0.0, 0.04),
    "wood":        ((0.40, 0.19, 0.075, 1), 0.0, 0.60),
    "concrete":    ((0.34, 0.335, 0.32, 1), 0.0, 0.92),
    "steel":       ((0.58, 0.59, 0.61, 1), 1.0, 0.34),
    "perf_metal":  ((0.060, 0.062, 0.068, 1), 0.85, 0.50),
    "interior":    ((0.060, 0.040, 0.028, 1), 0.0, 0.95),
    "lamp":        ((1.0, 0.80, 0.50, 1), 0.0, 0.40),
}


def get_mat(name):
    m = bpy.data.materials.get(name)
    if m:
        return m
    col, met, rough = MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = col
    bsdf.inputs["Metallic"].default_value = met
    bsdf.inputs["Roughness"].default_value = rough
    if name == "lamp":
        bsdf.inputs["Emission Color"].default_value = col
        bsdf.inputs["Emission Strength"].default_value = 6.0
    if name == "glass":
        bsdf.inputs["Alpha"].default_value = 0.55
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            m.blend_method = "BLEND"
    m.diffuse_color = col
    m.metallic = met
    m.roughness = rough
    return m


class B:
    """Сборщик одного объекта: набор закрытых оболочек (коробки, призмы, цилиндры) с материалами."""

    def __init__(self, name, mirror_w=None):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []
        self.mx = mirror_w          # если задано — всё отражается по X вокруг w/2 (правая версия угла)

    def mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def _finish_shell(self, verts, mat, bev, seg):
        bm = self.bm
        edges = list({e for v in verts for e in v.link_edges})
        faces = list({f for v in verts for f in v.link_faces})
        mi = self.mi(mat)
        for f in faces:
            f.material_index = mi
        if bev > 0:
            r = bmesh.ops.bevel(bm, geom=edges, offset=bev, segments=seg, affect="EDGES", profile=0.5)
            for f in r["faces"]:
                f.material_index = mi
                f.smooth = True

    def box(self, x0, x1, y0, y1, z0, z1, mat, bev=0.0, seg=1, rot=None):
        """Коробка по границам; rot = (ось 'X'|'Y'|'Z', угол рад) вокруг центра коробки."""
        if self.mx is not None:
            x0, x1 = self.mx - x1, self.mx - x0
        dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
        if min(dx, dy, dz) < 1e-5:
            return
        bm = self.bm
        res = bmesh.ops.create_cube(bm, size=1.0)
        verts = res["verts"]
        c = Vector(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
        for v in verts:
            v.co = Vector((v.co.x * dx, v.co.y * dy, v.co.z * dz))
        if rot:
            bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(rot[1], 3, rot[0]), verts=verts)
        for v in verts:
            v.co += c
        b = min(bev, 0.45 * min(dx, dy, dz))
        self._finish_shell(verts, mat, b, seg)

    def hull(self, pts, mat, bev=0.0, seg=1):
        """Выпуклая оболочка точек (гранёные пилоны, козырьки-уголки)."""
        bm = self.bm
        if self.mx is not None:
            pts = [(self.mx - p[0], p[1], p[2]) for p in pts]
        verts = [bm.verts.new(p) for p in pts]
        r = bmesh.ops.convex_hull(bm, input=verts)
        geom = r["geom"]
        hv = [g for g in geom if isinstance(g, bmesh.types.BMVert)]
        he = [g for g in geom if isinstance(g, bmesh.types.BMEdge)]
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.6), verts=hv, edges=he)
        keep = [v for v in verts if v.is_valid and v.link_faces]
        self._finish_shell(keep, mat, bev, seg)

    def cyl(self, cx, cy, z0, z1, r, mat, seg=20, bev=0.0, r2=None):
        if self.mx is not None:
            cx = self.mx - cx
        bm = self.bm
        res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg,
                                    radius1=r, radius2=(r if r2 is None else r2), depth=z1 - z0)
        verts = res["verts"]
        for v in verts:
            v.co += Vector((cx, cy, (z0 + z1) / 2))
        self._finish_shell(verts, mat, bev, 1)

    def cyl_x(self, x0, x1, cy, cz, r, mat, seg=14):
        """Цилиндр вдоль X (поручни, рейки)."""
        if self.mx is not None:
            x0, x1 = self.mx - x1, self.mx - x0
        bm = self.bm
        res = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r, radius2=r, depth=x1 - x0)
        verts = res["verts"]
        bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"), verts=verts)
        for v in verts:
            v.co += Vector(((x0 + x1) / 2, cy, cz))
        self._finish_shell(verts, mat, 0, 1)

    def build(self):
        bm = self.bm
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(get_mat(m))
        ob = bpy.data.objects.new(self.name, me)
        return ob


# ---------- реестр модулей ----------
MODULES = {}      # имя -> коллекция
TRIS = {}         # имя -> треугольники
_root = {"col": None}


def set_root(col):
    _root["col"] = col


def register(name, builder):
    """Создаёт коллекцию-модуль и кладёт в неё объект."""
    if name in MODULES:
        return MODULES[name]
    ob = builder.build()
    col = bpy.data.collections.new(name)
    _root["col"].children.link(col)
    col.objects.link(ob)
    MODULES[name] = col
    me = ob.data
    TRIS[name] = sum(len(p.vertices) - 2 for p in me.polygons)
    return col


def wkey(w):
    return "%d" % round(w * 1000)


def inst(parent, module, loc, rotz=0.0, name=None, body=False):
    col = MODULES[module]
    e = bpy.data.objects.new(name or module, None)
    e.instance_type = "COLLECTION"
    e.instance_collection = col
    e.empty_display_size = 0.2
    e.location = loc
    e.rotation_euler = (0, 0, rotz)
    e["module"] = module
    if body:
        e["body"] = 1
    parent.objects.link(e)
    return e


# ---------- облицовка вентфасада ----------
def clad(b, x0, x1, z0, z1, mat="panel_beige", split=1.6, ret_left=False):
    """Участок стены: плиты 20 мм со швами 10 мм, подсистема, бетон. Плиты делятся на куски ~split."""
    nx = max(1, round((x1 - x0) / split))
    nz = max(1, round((z1 - z0) / (3.01)))
    sub_mat = "dark_panel"
    j = JOINT / 2
    for iz in range(nz):
        za = z0 + (z1 - z0) * iz / nz
        zb = z0 + (z1 - z0) * (iz + 1) / nz
        for ix in range(nx):
            xa = x0 + (x1 - x0) * ix / nx
            xb = x0 + (x1 - x0) * (ix + 1) / nx
            b.box(xa + j, xb - j, 0, PT, za + j, zb - j, mat, bev=0.004)
    b.box(x0, x1, PT, SUB, z0, z1, sub_mat)
    b.box(x0, x1, SUB, D, z0, z1, "concrete")


def mod_panel(w, corner=None, dark=False):
    """Простенок: бежевая панель(и) 1,5 × 3,0 со швами; corner='L' — угол с возвратом на левый торец."""
    name = "H_Panel%s_%s" % ("Corner" + corner if corner else "", wkey(w))
    if name in MODULES:
        return name
    mat = "dark_panel" if dark else "panel_beige"
    b = B(name, mirror_w=(w if corner == "R" else None))
    j = JOINT / 2
    if corner:
        x_in = SUB            # главная часть стены начинается правее возврата
        # лицо
        nx = max(1, round((w - 0.0) / 1.6))
        for ix in range(nx):
            xa = w * ix / nx
            xb = w * (ix + 1) / nx
            b.box(xa + (0 if ix == 0 else j), xb - j, 0, PT, j, HF - j, mat, bev=0.004)
        # возврат на торец (стоит в плоскости x = 0, лицом к −X)
        b.box(0, PT, PT + JOINT, D - 0.1, j, HF - j, mat, bev=0.004)
        b.box(PT, x_in, PT, D, 0, HF, "dark_panel")
        b.box(PT, w, PT, SUB, 0, HF, "dark_panel")
        b.box(x_in, w, SUB, D, 0, HF, "concrete")
    else:
        clad(b, 0, w, 0, HF, mat)
    register(name, b)
    return name


def mod_ground(w, corner=None, h=HG):
    """Панель бетонного первого этажа: щитовая опалубка, русты 12 мм геометрией, вертикальное ребро. Доски — на текстуре."""
    name = "H_Ground%s_%s" % ("Corner" + corner if corner else "", wkey(w))
    if name in MODULES:
        return name
    b = B(name, mirror_w=(w if corner == "R" else None))
    # главное тело
    x0 = 0.06 if corner else 0.0
    b.box(x0, w, 0.20, D, 0, h, "concrete")
    ncourse = 3
    for i in range(ncourse):
        za = h * i / ncourse + 0.006
        zb = h * (i + 1) / ncourse - 0.006
        if i == 0:
            za = 0.0
        b.box(0.0, w, 0.14, 0.20, za, zb, "concrete", bev=0.010, seg=2)
        if corner:
            b.box(0.0, 0.06, 0.206, D - 0.1, za, zb, "concrete", bev=0.010, seg=2)
    # рёбра: у обычной панели — по левому краю, у угла — по внутреннему краю
    if corner:
        b.box(w - 0.30, w, 0.0, 0.14, 0.0, h, "concrete", bev=0.014, seg=2)
    else:
        b.box(0.0, 0.30, 0.0, 0.14, 0.0, h, "concrete", bev=0.014, seg=2)
    # цоколь: ступень-отлив 150 мм
    b.box(0.0, w, 0.0, 0.14, 0.0, 0.15, "concrete", bev=0.008, seg=2)
    register(name, b)
    return name


# ---------- окна ----------
def _frame_cells(b, x0, x1, z0, z1, y0, y1, fr, impost_x=None, transom_z=None, sash=None):
    """Алюминиевая рама с импостом и ригелем; стекло 8 мм в каждой ячейке; sash — (ячейка) створка с внутренней рамкой."""
    # наружная рама
    b.box(x0, x0 + fr, y0, y1, z0, z1, "alu_frame", bev=0.003)
    b.box(x1 - fr, x1, y0, y1, z0, z1, "alu_frame", bev=0.003)
    b.box(x0 + fr, x1 - fr, y0, y1, z0, z0 + fr, "alu_frame", bev=0.003)
    b.box(x0 + fr, x1 - fr, y0, y1, z1 - fr, z1, "alu_frame", bev=0.003)
    xs = [x0 + fr]
    zs = [z0 + fr]
    if impost_x is not None:
        b.box(impost_x - fr * 0.6, impost_x + fr * 0.6, y0, y1, z0 + fr, z1 - fr, "alu_frame", bev=0.003)
        xs += [impost_x - fr * 0.6, impost_x + fr * 0.6]
    xs.append(x1 - fr)
    if transom_z is not None:
        b.box(x0 + fr, x1 - fr, y0, y1, transom_z - fr * 0.5, transom_z + fr * 0.5, "alu_frame", bev=0.003)
        zs += [transom_z - fr * 0.5, transom_z + fr * 0.5]
    zs.append(z1 - fr)
    ym = (y0 + y1) / 2
    cells = []
    for i in range(0, len(xs), 2):
        for k in range(0, len(zs), 2):
            cells.append((xs[i], xs[i + 1], zs[k], zs[k + 1]))
            b.box(xs[i], xs[i + 1], zs[k], zs[k + 1], ym - 0.004, ym + 0.004, "glass")
    return cells


def mod_window(w, end=False):
    """Пролёт «окно»: проём с откосами, рама с импостом, створка, отлив, ниша за стеклом, подоконник, карниз."""
    name = "H_Window%s_%s" % ("End" if end else "", wkey(w))
    if name in MODULES:
        return name
    b = B(name)
    mat = "dark_panel" if end else "panel_beige"
    ow = w - (0.5 if end else 1.0)
    x0 = (w - ow) / 2
    x1 = x0 + ow
    zs, ze = 0.9, 2.6
    clad(b, 0, w, 0, zs, mat)
    clad(b, 0, w, ze, HF, mat)
    clad(b, 0, x0, zs, ze, mat)
    clad(b, x1, w, zs, ze, mat)
    # откосы 20 мм (возврат облицовки в проём)
    rv = 0.20
    b.box(x0, x0 + PT, PT, rv, zs, ze, mat, bev=0.003)
    b.box(x1 - PT, x1, PT, rv, zs, ze, mat, bev=0.003)
    b.box(x0 + PT, x1 - PT, PT, rv, ze - PT, ze, mat, bev=0.003)
    # отлив
    b.box(x0 - 0.03, x1 + 0.03, -0.05, rv + 0.05, zs, zs + 0.03, "alu_frame", bev=0.004)
    # рама на глубине 250 мм
    fr = 0.065
    impost = x0 + ow * 0.52
    cells = _frame_cells(b, x0 + PT, x1 - PT, zs + 0.03, ze - PT, 0.25, 0.32, fr, impost_x=impost, transom_z=2.15)
    # створка: внутренняя рамка 40 мм вокруг левой нижней ячейки, чуть впереди
    ca = cells[0]
    sx0, sx1, sz0, sz1 = ca
    sf = 0.04
    for (a0, a1, c0, c1) in ((sx0, sx0 + sf, sz0, sz1), (sx1 - sf, sx1, sz0, sz1),
                             (sx0 + sf, sx1 - sf, sz0, sz0 + sf), (sx0 + sf, sx1 - sf, sz1 - sf, sz1)):
        b.box(a0, a1, 0.22, 0.25, c0, c1, "alu_frame", bev=0.002)
    b.box(sx1 - 0.16, sx1 - 0.12, 0.19, 0.22, sz0 + 0.55, sz0 + 0.75, "steel", bev=0.002)   # ручка
    # ниша за стеклом
    b.box(x0 + PT, x1 - PT, 0.90, 0.95, zs + 0.03, ze - PT, "interior")
    b.box(x0 + PT, x1 - PT, 0.34, 0.66, zs + 0.03, zs + 0.075, "interior", bev=0.004)    # подоконник
    b.box(x0 + PT + 0.05, x1 - PT - 0.05, 0.42, 0.50, ze - PT - 0.07, ze - PT - 0.03, "steel", bev=0.003)   # карниз для штор
    register(name, b)
    return name


# ---------- лоджии ----------
def _loggia_shell(b, w):
    sw = 0.15
    b.box(0, sw, 0, D, 0, LOG_H, "dark_panel", bev=0.003)
    b.box(w - sw, w, 0, D, 0, LOG_H, "dark_panel", bev=0.003)
    b.box(sw, w - sw, 1.40, D, 0, LOG_H, "concrete")
    b.box(sw, w - sw, 1.34, 1.40, 0.02, LOG_H, "dark_panel")
    b.box(sw, w - sw, 0.02, 1.34, 0, 0.02, "concrete")                # пол
    # остекление: рама на глубине 1,15…1,22, дверь слева 0,9 + окно, ригель 2,1
    fr = 0.06
    xa, xb = sw + 0.02, w - sw - 0.02
    impost = xa + (xb - xa) * 0.42
    _frame_cells(b, xa, xb, 0.02, LOG_H - 0.04, 1.15, 1.22, fr, impost_x=impost, transom_z=2.05)
    b.box(impost + 0.12, impost + 0.16, 1.10, 1.15, 0.95, 1.20, "steel", bev=0.002)   # ручка двери


def mod_loggia_perf(w):
    name = "H_LoggiaPerf_%s" % wkey(w)
    if name in MODULES:
        return name
    b = B(name)
    _loggia_shell(b, w)
    sw = 0.15
    y0, y1 = 0.05, 0.10
    # ограждение: рама из труб 40 × 40 + лист 3 мм (перфорация — текстурой)
    xa, xb = sw + 0.005, w - sw - 0.005
    b.box(xa, xa + 0.04, y0, y1, 0.0, 1.10, "alu_frame", bev=0.004)
    b.box(xb - 0.04, xb, y0, y1, 0.0, 1.10, "alu_frame", bev=0.004)
    b.box(xa + 0.04, xb - 0.04, y0, y1, 1.06, 1.10, "alu_frame", bev=0.004)
    b.box(xa + 0.04, xb - 0.04, y0, y1, 0.02, 0.06, "alu_frame", bev=0.004)
    b.box(xa + 0.04, xb - 0.04, 0.060, 0.063, 0.06, 1.06, "perf_metal", bev=0.001)
    register(name, b)
    return name


def mod_loggia_glass(w):
    name = "H_LoggiaGlass_%s" % wkey(w)
    if name in MODULES:
        return name
    b = B(name)
    _loggia_shell(b, w)
    sw = 0.15
    y0, y1 = 0.05, 0.10
    n = 3
    xa, xb = sw + 0.005, w - sw - 0.005
    px = [xa + (xb - xa - 0.04) * i / n for i in range(n + 1)]
    for p in px:
        b.box(p, p + 0.04, y0, y1, 0.0, 1.10, "steel", bev=0.005, seg=2)
    b.box(xa, xb, 0.05, 0.11, 0.04, 0.10, "steel", bev=0.004)                 # прижимной профиль
    b.cyl_x(xa, xb, 0.075, 1.10, 0.025, "steel")                              # поручень ⌀ 50
    for i in range(n):
        b.box(px[i] + 0.06, px[i + 1] - 0.02, 0.070, 0.080, 0.10, 1.06, "glass", bev=0.001)   # триплекс 10
    register(name, b)
    return name


def mod_slabband(w):
    """Тёмная полоса перекрытия у лоджий: лицевая полоса 0,55 + бетонное перекрытие 350 мм."""
    name = "H_SlabBand_%s" % wkey(w)
    if name in MODULES:
        return name
    b = B(name)
    b.box(0, w, 0, 0.12, 0, BAND_H, "dark_panel", bev=0.004)
    b.box(0, w, 0.12, D, 0.20, BAND_H, "concrete")
    b.box(0.0, w, 0.12, D, 0.0, 0.20, "concrete")
    register(name, b)
    return name


def mod_wood(w=0.5):
    """Деревянная вставка: вертикальные рейки 45 × 30 на горизонтальной подсистеме."""
    name = "H_WoodInsert_%s" % wkey(w)
    if name in MODULES:
        return name
    b = B(name)
    b.box(0, w, PT + 0.03, SUB, 0, HF, "dark_panel")
    b.box(0, w, SUB, D, 0, HF, "concrete")
    for z in (0.45, 1.5, 2.55):
        b.box(0.01, w - 0.01, 0.03, 0.05, z - 0.02, z + 0.02, "alu_frame", bev=0.002)
    pitch = 0.06
    n = int((w - 0.02) / pitch)
    x0 = (w - ((n - 1) * pitch + 0.045)) / 2
    for i in range(n):
        xa = x0 + i * pitch
        b.box(xa, xa + 0.045, 0.0, 0.03, 0.012, HF - 0.012, "wood", bev=0.004)
    register(name, b)
    return name


# ---------- парапет ----------
def mod_parapet(L):
    name = "H_Parapet_%s" % wkey(L)
    if name in MODULES:
        return name
    b = B(name)
    b.box(0, L, 0.0, 0.25, 0.0, 0.41, "dark_panel", bev=0.004)
    b.box(0, L, 0.25, 0.45, 0.0, 0.10, "concrete")                          # кант кровли
    b.box(0, L, 0.0, 0.30, 0.41, 0.45, "alu_frame", bev=0.005)             # отлив-крышка
    for x in [i * 1.5 for i in range(1, int(L / 1.5))]:
        b.box(x - 0.005, x + 0.005, -0.004, 0.01, 0.0, 0.41, "alu_frame")    # шов листов
    register(name, b)
    return name


def mod_belt(L):
    """Пояс над бетонным первым этажом: тёмная полка 0,22 с выносом 60 мм и отливом."""
    name = "H_BaseBelt_%s" % wkey(L)
    if name in MODULES:
        return name
    b = B(name)
    b.box(0, L, -0.06, 0.20, 0.0, 0.18, "dark_panel", bev=0.006, seg=2)
    b.box(0, L, -0.07, 0.20, 0.18, 0.21, "alu_frame", bev=0.004)
    b.box(0, L, 0.0, 0.20, -0.05, 0.0, "concrete")
    register(name, b)
    return name
